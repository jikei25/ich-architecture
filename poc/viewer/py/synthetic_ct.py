"""Synthetic non-contrast head CT, so the PoC never touches real patient data.

The phantom is an ellipse of skull around brain tissue with two ventricles. A
"positive" study adds a hyperdense ellipsoid (about 70 HU, the density of fresh
blood) that the simulated AI can find by thresholding.
"""
import datetime as dt

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

ROWS = COLS = 256
PIXEL_MM = 0.9


def _phantom(n_slices, thickness_mm, bleed, rng):
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    cy, cx = ROWS / 2, COLS / 2
    vol = np.full((n_slices, ROWS, COLS), -1000.0)
    for z in range(n_slices):
        # Head gets smaller towards the top of the volume.
        k = 1.0 - 0.25 * (z / max(n_slices - 1, 1)) ** 2
        a, b = 92 * k, 112 * k
        r = ((xx - cx) / a) ** 2 + ((yy - cy) / b) ** 2
        inner = ((xx - cx) / (a - 8)) ** 2 + ((yy - cy) / (b - 8)) ** 2
        sl = vol[z]
        sl[r <= 1] = 1000.0                       # skull
        sl[inner <= 1] = 35.0                     # brain
        for dx in (-14, 14):                      # lateral ventricles
            v = ((xx - cx - dx) / 7) ** 2 + ((yy - cy + 8) / 22) ** 2
            if 0.3 < z / n_slices < 0.7:
                sl[v <= 1] = 8.0
        sl[inner <= 1] += rng.normal(0, 4, size=sl.shape)[inner <= 1]
    if bleed:
        zc = n_slices * 0.5
        rz = 15.0 / thickness_mm      # about 3 cm high
        zz = np.arange(n_slices)[:, None, None]
        e = (((xx - cx - 40) / 22) ** 2 + ((yy - cy + 18) / 16) ** 2)[None] + ((zz - zc) / rz) ** 2
        vol[e <= 1] = 72.0 + rng.normal(0, 3, size=int((e <= 1).sum()))
    return vol


def make_series(patient, study, *, positive, thickness_mm=1.25, n_slices=48,
                description="Head non-contrast AXIAL 1.25mm", seed=0):
    """Return a list of CT datasets for one series.

    patient: dict with PatientName, PatientID, PatientBirthDate, PatientSex
    study:   dict with StudyInstanceUID, AccessionNumber, StudyDescription
    """
    rng = np.random.default_rng(seed)
    vol = _phantom(n_slices, thickness_mm, positive, rng)
    stored = np.clip(vol + 1024, 0, 4095).astype(np.uint16)

    series_uid = generate_uid()
    frame_uid = generate_uid()
    now = dt.datetime.now()
    out = []
    for i in range(n_slices):
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = CTImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian

        ds = Dataset()
        ds.file_meta = meta
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        for k, v in patient.items():
            setattr(ds, k, v)
        ds.StudyInstanceUID = study["StudyInstanceUID"]
        ds.AccessionNumber = study.get("AccessionNumber", "")
        ds.StudyDescription = study.get("StudyDescription", "CT head")
        ds.StudyID = "1"
        ds.StudyDate = ds.SeriesDate = ds.ContentDate = now.strftime("%Y%m%d")
        ds.StudyTime = ds.SeriesTime = ds.ContentTime = now.strftime("%H%M%S")
        ds.ReferringPhysicianName = ""
        ds.Modality = "CT"
        ds.Manufacturer = "ICH-PoC synthetic"
        ds.InstitutionName = "PoC"
        ds.StationName = "CT01"
        ds.BodyPartExamined = "HEAD"
        ds.SeriesInstanceUID = series_uid
        ds.SeriesNumber = 2 if thickness_mm < 3 else 3
        ds.SeriesDescription = description
        ds.FrameOfReferenceUID = frame_uid
        ds.PositionReferenceIndicator = ""
        ds.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
        ds.InstanceNumber = i + 1
        ds.SliceThickness = thickness_mm
        ds.SpacingBetweenSlices = thickness_mm
        ds.KVP = 120
        ds.ContrastBolusAgent = None
        ds.PatientPosition = "HFS"
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.ImagePositionPatient = [-COLS * PIXEL_MM / 2, -ROWS * PIXEL_MM / 2, i * thickness_mm]
        ds.SliceLocation = i * thickness_mm
        ds.PixelSpacing = [PIXEL_MM, PIXEL_MM]
        ds.Rows, ds.Columns = ROWS, COLS
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated = 16
        ds.BitsStored = 12
        ds.HighBit = 11
        ds.PixelRepresentation = 0
        ds.RescaleIntercept = -1024
        ds.RescaleSlope = 1
        ds.RescaleType = "HU"
        ds.WindowCenter = 40
        ds.WindowWidth = 80
        ds.BurnedInAnnotation = "NO"
        ds.PixelData = stored[i].tobytes()
        out.append(ds)
    return out
