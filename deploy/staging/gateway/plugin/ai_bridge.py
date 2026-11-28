"""Orthanc plugin: sends each stable CT series to the AI segmentation service as NIfTI, stores the returned mask in
the PACS as DICOM SEG, and stores a de-identified copy of the series with the mask as a draft on the research Orthanc.

AI service contract (MONAI Label /infer/<model>?output=image): multipart field `file` with a gzip NIfTI volume
(int16 HU, RAS affine); the response is a gzip NIfTI mask on the same grid whose `descrip` is "hemorrhage <version>".
"""
import base64
import gzip
import hashlib
import hmac
import io
import json
import os
import queue
import threading
import time
import urllib.request
import uuid

import nibabel as nib
import orthanc
import pydicom

from nifti_bridge import mask_to_seg, series_to_nifti, volume_ml

AI_SEGMENT_URL = os.environ.get("AI_SEGMENT_URL", "")
ALGORITHM_NAME = "ich-segmentation"
RESULT_MODALITY = "pacs"
AI_TIMEOUT_SECONDS = 600
RESEARCH_URL = os.environ.get("RESEARCH_URL", "")
RESEARCH_AUTH = "Basic " + base64.b64encode(
    f"{os.environ.get('RESEARCH_USER', '')}:{os.environ.get('RESEARCH_PASSWORD', '')}".encode()).decode()
DEID_KEY = os.environ.get("DEID_KEY", "").encode()
UID_TAGS = ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "FrameOfReferenceUID")

# shortcut: in-memory queue, so series pending at restart are not processed; use a persistent queue before production.
series_queue = queue.Queue()


def on_change(change_type, level, resource_id):
    if change_type == orthanc.ChangeType.STABLE_SERIES:
        series_queue.put(resource_id)


def segment(volume):
    """Returns the AI mask and the version of the model that produced it."""
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="volume.nii.gz"\r\n'
            f"Content-Type: application/gzip\r\n\r\n").encode() + gzip.compress(volume.to_bytes()) + \
        f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{AI_SEGMENT_URL}?output=image", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=AI_TIMEOUT_SECONDS) as response:
        mask = nib.Nifti1Image.from_bytes(gzip.decompress(response.read()))
    return mask, mask.header["descrip"].item().decode().removeprefix("hemorrhage ").strip() or "unknown"


def pseudonym_uid(uid, key):
    return "2.25." + str(int.from_bytes(hmac.new(key, uid.encode(), hashlib.sha256).digest()[:16], "big"))


def anonymize_request(ds, key):
    """Orthanc basic-profile anonymization, with UIDs and patient ID replaced by the keyed-hash rule.

    The same rule applied to the CT and to every later mask of that CT keeps their references consistent.
    """
    patient = "ANON-" + hmac.new(key, str(ds.PatientID).encode(), hashlib.sha256).hexdigest()[:12]
    uids = {tag: pseudonym_uid(str(ds.get(tag)), key) for tag in UID_TAGS if ds.get(tag)}
    return {"Replace": {**uids, "PatientID": patient, "PatientName": patient}, "Force": True}


def research_call(method, path, body=b""):
    request = urllib.request.Request(f"{RESEARCH_URL}{path}", data=body, method=method,
                                     headers={"Authorization": RESEARCH_AUTH})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read() or b"null")


def copy_to_research(instance_ids, datasets, mask, model_version):
    """Stores the de-identified series and the AI mask as a draft SEG on the research Orthanc.

    Every instance is de-identified before anything is sent, so a failure leaves nothing on the research side.
    """
    if any(ds.get("BurnedInAnnotation", "NO") != "NO" for ds in datasets):
        orthanc.LogWarning("AI bridge: series may carry burned-in text, no research copy")
        return
    copies = [orthanc.RestApiPost(f"/instances/{instance}/anonymize", json.dumps(anonymize_request(ds, DEID_KEY)))
              for instance, ds in zip(instance_ids, datasets)]
    ordered, volume = series_to_nifti([pydicom.dcmread(io.BytesIO(copy)) for copy in copies])
    draft = mask_to_seg(ordered, volume, mask, ALGORITHM_NAME, model_version)
    buffer = io.BytesIO()
    draft.save_as(buffer)
    for copy in copies:
        research_call("POST", "/instances", copy)
    series = research_call("POST", "/instances", buffer.getvalue())["ParentSeries"]
    research_call("PUT", f"/series/{series}/labels/draft")
    research_call("PUT", f"/series/{series}/metadata/DraftModel", f"hemorrhage_approved {model_version}".encode())


def process(series_id):
    series = json.loads(orthanc.RestApiGet(f"/series/{series_id}"))
    if series["MainDicomTags"].get("Modality") != "CT":
        return
    started = time.monotonic()
    datasets = [pydicom.dcmread(io.BytesIO(orthanc.RestApiGet(f"/instances/{instance}/file")))
                for instance in series["Instances"]]
    ordered, volume = series_to_nifti(datasets)
    converted = time.monotonic()
    mask, model_version = segment(volume)
    inferred = time.monotonic()

    seg = mask_to_seg(ordered, volume, mask, ALGORITHM_NAME, model_version)
    buffer = io.BytesIO()
    seg.save_as(buffer)
    stored = json.loads(orthanc.RestApiPost("/instances", buffer.getvalue()))
    orthanc.RestApiPost(f"/modalities/{RESULT_MODALITY}/store",
                        json.dumps({"Resources": [stored["ID"]], "Synchronous": True}))
    returned = time.monotonic()
    # shortcut: every CT series is copied; the architecture copies only the cases selected for research.
    if RESEARCH_URL:
        copy_to_research(series["Instances"], datasets, mask, model_version)
    orthanc.LogWarning(
        f"AI bridge: series {series_id} ({len(ordered)} slices) -> SEG {seg.SOPInstanceUID}, model {model_version}, "
        f"hemorrhage {volume_ml(mask):.1f} mL; convert {converted - started:.1f} s, AI {inferred - converted:.1f} s, "
        f"SEG and store {returned - inferred:.1f} s, research copy {time.monotonic() - returned:.1f} s")


def work():
    while True:
        series_id = series_queue.get()
        try:
            process(series_id)
        except Exception as error:
            orthanc.LogError(f"AI bridge: series {series_id} failed: {error!r}")


if AI_SEGMENT_URL:
    threading.Thread(target=work, name="ai-bridge", daemon=True).start()
    orthanc.RegisterOnChangeCallback(on_change)
    orthanc.LogWarning(f"AI bridge: sending stable CT series to {AI_SEGMENT_URL}")
else:
    orthanc.LogWarning("AI bridge: AI_SEGMENT_URL is not set, plugin disabled")
