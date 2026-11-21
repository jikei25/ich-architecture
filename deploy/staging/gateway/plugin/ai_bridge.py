"""Orthanc plugin: sends each stable CT series to the AI segmentation service as NIfTI and stores the
returned mask in the PACS as DICOM SEG.

AI service contract: POST AI_SEGMENT_URL with a gzip NIfTI volume (int16 HU, RAS affine); the response is a
gzip NIfTI mask on the same grid (non-zero voxels are hemorrhage).
"""
import gzip
import io
import json
import os
import queue
import threading
import time
import urllib.request

import nibabel as nib
import orthanc
import pydicom

from nifti_bridge import mask_to_seg, series_to_nifti, volume_ml

AI_SEGMENT_URL = os.environ.get("AI_SEGMENT_URL", "")
ALGORITHM_NAME = "ich-segmentation"
ALGORITHM_VERSION = "0.1"
RESULT_MODALITY = "pacs"
AI_TIMEOUT_SECONDS = 600

# shortcut: in-memory queue, so series pending at restart are not processed; use a persistent queue before production.
series_queue = queue.Queue()


def on_change(change_type, level, resource_id):
    if change_type == orthanc.ChangeType.STABLE_SERIES:
        series_queue.put(resource_id)


def segment(volume):
    request = urllib.request.Request(
        AI_SEGMENT_URL, data=gzip.compress(volume.to_bytes()),
        headers={"Content-Type": "application/gzip"}, method="POST")
    with urllib.request.urlopen(request, timeout=AI_TIMEOUT_SECONDS) as response:
        return nib.Nifti1Image.from_bytes(gzip.decompress(response.read()))


def process(series_id):
    series = json.loads(orthanc.RestApiGet(f"/series/{series_id}"))
    if series["MainDicomTags"].get("Modality") != "CT":
        return
    started = time.monotonic()
    datasets = [pydicom.dcmread(io.BytesIO(orthanc.RestApiGet(f"/instances/{instance}/file")))
                for instance in series["Instances"]]
    ordered, volume = series_to_nifti(datasets)
    converted = time.monotonic()
    mask = segment(volume)
    inferred = time.monotonic()

    seg = mask_to_seg(ordered, volume, mask, ALGORITHM_NAME, ALGORITHM_VERSION)
    buffer = io.BytesIO()
    seg.save_as(buffer)
    stored = json.loads(orthanc.RestApiPost("/instances", buffer.getvalue()))
    orthanc.RestApiPost(f"/modalities/{RESULT_MODALITY}/store",
                        json.dumps({"Resources": [stored["ID"]], "Synchronous": True}))
    orthanc.LogWarning(
        f"AI bridge: series {series_id} ({len(ordered)} slices) -> SEG {seg.SOPInstanceUID}, "
        f"hemorrhage {volume_ml(mask):.1f} mL; convert {converted - started:.1f} s, "
        f"AI {inferred - converted:.1f} s, SEG and store {time.monotonic() - inferred:.1f} s")


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
