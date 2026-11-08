"""Simulated AI inference service (Flow 2), stand-in for the real model.

PoC shortcut: in the architecture the PACS pushes series to the Orthanc gateway
and the AI never talks to the PACS. Here the worker polls the PACS over
DICOMweb instead, because the gateway is not what this PoC is about. What it
writes back is what the real pipeline must write back:

  * a priority flag and result metadata to the AI results service (triage API),
    sent first so the alert does not wait for the mask;
  * a DICOM SEG mask and a TID 1500 SR with the bleed volume, C-STOREd to the
    PACS next to the original study, so any DICOMweb viewer can show them.

"Inference" is a threshold on Hounsfield units (fresh blood is about 50-90 HU),
which is enough to find the lesion the synthetic scanner puts in the phantom.
"""
import hashlib
import logging
import os
import threading
import time

import highdicom as hd
import numpy as np
import requests
from dicomweb_client.api import DICOMwebClient
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid
from pynetdicom import AE
from pynetdicom.sop_class import Comprehensive3DSRStorage, SegmentationStorage
from scipy import ndimage

DICOMWEB = os.environ.get("DICOMWEB_URL", "http://arc:8080/dcm4chee-arc/aets/DCM4CHEE/rs")
TRIAGE = os.environ.get("TRIAGE_URL", "http://triage:8000/api")
PACS_HOST = os.environ.get("PACS_HOST", "arc")
PACS_PORT = int(os.environ.get("PACS_DICOM_PORT", "11112"))
PACS_AET = os.environ.get("PACS_AET", "DCM4CHEE")
RESULT_AE = os.environ.get("RESULT_AE", "AI_RESULTS")
SETTLE_S = float(os.environ.get("SETTLE_SECONDS", "6"))
INFER_S = float(os.environ.get("INFERENCE_SECONDS", "8"))
POLL_S = 3.0

MODEL_VERSION = "ich-sim-0.1"
PARAMS = dict(hu_low=55, hu_high=95, bone_hu=300, bone_margin_px=4, min_voxels=200, min_ml=0.5)
PREPROC_HASH = hashlib.sha256(repr(sorted(PARAMS.items())).encode()).hexdigest()[:12]

log = logging.getLogger("ai")
dw = DICOMwebClient(url=DICOMWEB)


def tag(obj, t, default=None):
    v = obj.get(t, {}).get("Value")
    return v[0] if v else default


def post(path, body):
    try:
        requests.post(f"{TRIAGE}{path}", json=body, timeout=5)
    except requests.RequestException as e:
        log.warning("triage API unreachable: %s", e)


BOOT = time.time()


def heartbeat():
    while True:
        post("/heartbeat", {"model_version": MODEL_VERSION, "boot": BOOT})
        time.sleep(POLL_S)


def eligible_series(study_uid):
    """Return the UID of a thin axial non-contrast CT series, or None."""
    for s in dw.search_for_series(study_uid):
        if tag(s, "00080060") != "CT":
            continue
        uid = tag(s, "0020000E")
        meta = dw.retrieve_series_metadata(study_uid, uid)
        first = meta[0]
        image_type = first.get("00080008", {}).get("Value", [])
        thickness = float(tag(first, "00180050", 99))
        contrast = tag(first, "00180010")
        if "AXIAL" in image_type and thickness <= 2.5 and not contrast and len(meta) >= 20:
            return uid
    return None


def segment(datasets):
    vol = np.stack([d.pixel_array.astype(np.float32) * float(d.RescaleSlope)
                    + float(d.RescaleIntercept) for d in datasets])
    bone = vol > PARAMS["bone_hu"]
    struct = np.zeros((1, 3, 3), bool)
    struct[0] = ndimage.generate_binary_structure(2, 1)
    near_bone = ndimage.binary_dilation(bone, structure=struct, iterations=PARAMS["bone_margin_px"])
    cand = (vol >= PARAMS["hu_low"]) & (vol <= PARAMS["hu_high"]) & ~near_bone
    labels, n = ndimage.label(cand)
    if n:
        sizes = ndimage.sum(cand, labels, range(1, n + 1))
        keep = [i + 1 for i, sz in enumerate(sizes) if sz >= PARAMS["min_voxels"]]
        mask = np.isin(labels, keep)
    else:
        mask = np.zeros_like(cand)
    ps = [float(x) for x in datasets[0].PixelSpacing]
    voxel_ml = ps[0] * ps[1] * float(datasets[0].SliceThickness) / 1000.0
    return mask, float(mask.sum() * voxel_ml)


def build_seg(datasets, mask):
    desc = hd.seg.SegmentDescription(
        segment_number=1,
        segment_label="ICH (AI) - CHUA XAC NHAN",
        segmented_property_category=codes.SCT.MorphologicallyAbnormalStructure,
        segmented_property_type=codes.SCT.Hemorrhage,
        algorithm_type=hd.seg.SegmentAlgorithmTypeValues.AUTOMATIC,
        algorithm_identification=hd.AlgorithmIdentificationSequence(
            name="ICH PoC threshold", version=MODEL_VERSION,
            family=codes.cid7162.ArtificialIntelligence),
        display_color=hd.color.CIELabColor(54.3, 80.8, 69.9),   # red
    )
    return hd.seg.Segmentation(
        source_images=datasets,
        pixel_array=mask.astype(np.uint8),
        segmentation_type=hd.seg.SegmentationTypeValues.BINARY,
        segment_descriptions=[desc],
        series_instance_uid=generate_uid(),
        series_number=900,
        sop_instance_uid=generate_uid(),
        instance_number=1,
        manufacturer="ICH-PoC",
        manufacturer_model_name="threshold-sim",
        software_versions=MODEL_VERSION,
        device_serial_number="0",
        series_description="AI ICH mask - CHUA XAC NHAN",
        content_label="AI_ICH",
        omit_empty_frames=True,
    )


def build_sr(datasets, seg, volume_ml):
    ref = hd.sr.ReferencedSegment(
        sop_class_uid=seg.SOPClassUID, sop_instance_uid=seg.SOPInstanceUID, segment_number=1,
        source_series=hd.sr.SourceSeriesForSegmentation(datasets[0].SeriesInstanceUID))
    group = hd.sr.VolumetricROIMeasurementsAndQualitativeEvaluations(
        tracking_identifier=hd.sr.TrackingIdentifier(uid=generate_uid(), identifier="ICH-1"),
        referenced_segment=ref,
        finding_type=codes.SCT.Hemorrhage,
        measurements=[hd.sr.Measurement(name=codes.SCT.Volume, value=round(volume_ml, 2),
                                        unit=hd.sr.CodedConcept("ml", "UCUM", "milliliter"))],
    )
    ctx = hd.sr.ObservationContext(observer_device_context=hd.sr.ObserverContext(
        observer_type=codes.DCM.Device,
        observer_identifying_attributes=hd.sr.DeviceObserverIdentifyingAttributes(
            uid=generate_uid(), name="ICH PoC AI", model_name=MODEL_VERSION)))
    report = hd.sr.MeasurementReport(
        observation_context=ctx,
        procedure_reported=codes.LN.CTUnspecifiedBodyRegion,
        imaging_measurements=[group],
    )
    return hd.sr.Comprehensive3DSR(
        evidence=[*datasets, seg], content=report, series_instance_uid=generate_uid(), series_number=901,
        sop_instance_uid=generate_uid(), instance_number=1, manufacturer="ICH-PoC",
        series_description="AI ICH report - CHUA XAC NHAN", is_complete=True, is_final=False,
        is_verified=False)


def store(objs):
    ae = AE(ae_title=RESULT_AE)
    ae.add_requested_context(SegmentationStorage)
    ae.add_requested_context(Comprehensive3DSRStorage)
    assoc = ae.associate(PACS_HOST, PACS_PORT, ae_title=PACS_AET)
    if not assoc.is_established:
        raise RuntimeError("PACS refused the association")
    try:
        for o in objs:
            st = assoc.send_c_store(o)
            if not st or st.Status != 0:
                raise RuntimeError(f"C-STORE failed: {st}")
    finally:
        assoc.release()


def process(study_uid):
    t0 = time.time()
    post(f"/results/{study_uid}", {"state": "RUNNING"})
    meta = {"model_version": MODEL_VERSION, "preprocessing_hash": PREPROC_HASH}
    series_uid = eligible_series(study_uid)
    if not series_uid:
        log.info("%s: no thin axial CT series, unanalyzable", study_uid)
        post(f"/results/{study_uid}", {"state": "UNANALYZABLE", **meta})
        return
    datasets = dw.retrieve_series(study_uid, series_uid)
    datasets.sort(key=lambda d: float(d.ImagePositionPatient[2]))
    mask, volume = segment(datasets)
    time.sleep(max(0.0, INFER_S - (time.time() - t0)))   # stand-in for GPU time
    if volume < PARAMS["min_ml"]:
        post(f"/results/{study_uid}", {"state": "NEGATIVE", "volume_ml": 0, **meta})
        log.info("%s: negative", study_uid)
        return
    # Priority flag first, so the alert does not wait for the mask (Flow 2.5).
    post(f"/results/{study_uid}", {"state": "POSITIVE", "volume_ml": round(volume, 1), **meta})
    seg = build_seg(datasets, mask)
    objs = [seg]
    try:
        objs.append(build_sr(datasets, seg, volume))
    except Exception:
        log.exception("SR not built, sending the mask only")
    store(objs)
    post(f"/results/{study_uid}", {"state": "POSITIVE", "volume_ml": round(volume, 1),
                                   "seg_series_uid": seg.SeriesInstanceUID, **meta})
    log.info("%s: positive, %.1f mL, SEG stored in %.1fs", study_uid, volume, time.time() - t0)


def known_studies():
    try:
        return set(requests.get(f"{TRIAGE}/results", timeout=5).json())
    except requests.RequestException:
        return None


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    for noisy in ("pynetdicom", "highdicom", "dicomweb_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    log.info("AI worker %s up, preprocessing %s", MODEL_VERSION, PREPROC_HASH)
    threading.Thread(target=heartbeat, daemon=True).start()
    seen = {}   # study UID -> (instance count, time the count last changed)
    while True:
        try:
            done = known_studies()
            if done is not None:
                for s in dw.search_for_studies(search_filters={"ModalitiesInStudy": "CT"},
                                               fields=["00201208"]):
                    uid = tag(s, "0020000D")
                    if uid in done:
                        continue
                    n = int(tag(s, "00201208", 0))
                    prev = seen.get(uid)
                    if prev is None or prev[0] != n:
                        seen[uid] = (n, time.time())
                    elif time.time() - prev[1] >= SETTLE_S:
                        # No new image for SETTLE_S seconds: the series is complete
                        # (the dcmDuration of a dcm4chee export rule plays this role).
                        try:
                            process(uid)
                        except Exception as e:
                            log.exception("%s failed", uid)
                            post(f"/results/{uid}", {"state": "FAILED", "error": str(e)[:200]})
                        seen.pop(uid, None)
        except Exception as e:
            log.warning("poll failed: %s", e)
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
