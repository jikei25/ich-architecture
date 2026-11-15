"""Convert NIfTI head CT volumes into DICOM CT series and store them to the PACS with C-STORE.

UIDs are derived from the file name, so loading the same file again resends identical instances and the
archive keeps a single copy. Patient identity is synthetic (dataset name plus file number).

Usage: load_nifti.py --host PACS_HOST [--port 11112] [--calling DATASET_LOADER] [--dataset CTICH] FILE.nii ...
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import nibabel as nib
import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE

RAS_TO_LPS = np.array([-1.0, -1.0, 1.0])


def uid(*parts: str) -> str:
    return generate_uid(entropy_srcs=list(parts))


def unit(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)


def slices(path: Path, dataset: str):
    image = nib.load(path)
    volume = np.asanyarray(image.dataobj).astype(np.int16)
    affine = image.affine
    columns, rows, depth = volume.shape
    spacing_i, spacing_j, thickness = (float(z) for z in image.header.get_zooms()[:3])

    # DICOM rows run along -j so that the image is displayed with the anterior side at the top.
    row_direction = unit(affine[:3, 0] * RAS_TO_LPS)
    column_direction = unit(-affine[:3, 1] * RAS_TO_LPS)

    number = path.name.split(".")[0]
    key = f"{dataset}-{number}"
    now = datetime.now()
    study_uid, series_uid, frame_uid = uid(key, "study"), uid(key, "series"), uid(key, "frame")

    for k in range(depth):
        origin = (affine @ np.array([0, rows - 1, k, 1.0]))[:3] * RAS_TO_LPS
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = uid(key, "instance", str(k))
        ds.PatientID = key
        ds.PatientName = f"{dataset}^{number}"
        ds.PatientBirthDate = ""
        ds.PatientSex = ""
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.FrameOfReferenceUID = frame_uid
        ds.StudyDate = ds.SeriesDate = now.strftime("%Y%m%d")
        ds.StudyTime = ds.SeriesTime = now.strftime("%H%M%S")
        ds.AccessionNumber = f"{dataset}{number}"
        ds.StudyID = number
        ds.StudyDescription = f"{dataset} head CT {number}"
        ds.SeriesDescription = f"AXIAL {thickness:g}mm"
        ds.ReferringPhysicianName = ""
        ds.Modality = "CT"
        ds.Manufacturer = "dataset import"
        ds.BodyPartExamined = "HEAD"
        ds.SeriesNumber = 1
        ds.InstanceNumber = k + 1
        ds.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
        ds.PatientPosition = "HFS"
        ds.ImageOrientationPatient = [round(float(v), 6) for v in (*row_direction, *column_direction)]
        ds.ImagePositionPatient = [round(float(v), 4) for v in origin]
        ds.SliceLocation = round(float(origin[2]), 4)
        ds.SliceThickness = thickness
        ds.PixelSpacing = [spacing_j, spacing_i]
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows, ds.Columns = rows, columns
        ds.BitsAllocated = ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1
        ds.RescaleIntercept = 0
        ds.RescaleSlope = 1
        ds.WindowCenter = 40
        ds.WindowWidth = 80
        ds.PixelData = np.ascontiguousarray(volume[:, ::-1, k].T).tobytes()
        yield ds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=11112)
    parser.add_argument("--called", default="DCM4CHEE")
    parser.add_argument("--calling", default="DATASET_LOADER")
    parser.add_argument("--dataset", default="CTICH")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    ae = AE(ae_title=args.calling)
    ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
    failed = 0
    for path in args.files:
        assoc = ae.associate(args.host, args.port, ae_title=args.called)
        if not assoc.is_established:
            print(f"{path.name}: association refused or aborted", file=sys.stderr)
            return 1
        sent = 0
        for ds in slices(path, args.dataset):
            status = assoc.send_c_store(ds)
            if status and status.Status == 0x0000:
                sent += 1
            else:
                failed += 1
        assoc.release()
        print(f"{path.name}: stored {sent} slices")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
