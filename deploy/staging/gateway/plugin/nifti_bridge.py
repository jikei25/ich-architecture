"""Conversion of a DICOM CT series to a NIfTI volume, and of a NIfTI mask on that volume to DICOM SEG."""
import highdicom as hd
import nibabel as nib
import numpy as np
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid

# DICOM patient coordinates are LPS, NIfTI world coordinates are RAS.
LPS_TO_RAS = np.diag([-1.0, -1.0, 1.0, 1.0])


def series_to_nifti(datasets):
    """Return the slices sorted along the slice normal and the volume as an int16 HU NIfTI image.

    Voxel (i, j, k) is column i, row j of the k-th sorted slice.
    """
    orientation = np.array(datasets[0].ImageOrientationPatient, dtype=float)
    normal = np.cross(orientation[:3], orientation[3:])
    ordered = sorted(datasets, key=lambda ds: float(np.dot(normal, ds.ImagePositionPatient)))
    if any(not np.allclose(ds.ImageOrientationPatient, orientation, atol=1e-4) for ds in ordered):
        raise ValueError("slices have different orientations")
    positions = np.array([ds.ImagePositionPatient for ds in ordered], dtype=float)
    steps = np.diff(positions, axis=0)
    if len(ordered) < 2 or not np.allclose(steps, steps[0], atol=1e-2):
        raise ValueError("slices are not evenly spaced")

    row_spacing, column_spacing = (float(v) for v in ordered[0].PixelSpacing)
    affine = np.eye(4)
    affine[:3, 0] = orientation[:3] * column_spacing
    affine[:3, 1] = orientation[3:] * row_spacing
    affine[:3, 2] = steps[0]
    affine[:3, 3] = positions[0]

    hu = [ds.pixel_array * float(ds.get("RescaleSlope", 1)) + float(ds.get("RescaleIntercept", 0)) for ds in ordered]
    volume = np.round(np.stack([slice_hu.T for slice_hu in hu], axis=-1)).astype(np.int16)
    image = nib.Nifti1Image(volume, LPS_TO_RAS @ affine)
    image.header.set_xyzt_units("mm")
    return ordered, image


def mask_to_seg(ordered, image, mask, algorithm_name, algorithm_version):
    """Build a binary hemorrhage SEG from a mask on the grid of `image`; UIDs depend only on the source and algorithm."""
    if mask.shape[:3] != image.shape or not np.allclose(mask.affine, image.affine, atol=1e-3):
        raise ValueError(f"mask grid {mask.shape} does not match the volume grid {image.shape}")
    labels = np.asanyarray(mask.dataobj).reshape(image.shape) > 0
    frames = labels.transpose(2, 1, 0).astype(np.uint8)

    algorithm = hd.AlgorithmIdentificationSequence(
        name=algorithm_name, version=algorithm_version, family=codes.cid7162.ArtificialIntelligence)
    segment = hd.seg.SegmentDescription(
        segment_number=1,
        segment_label="Hemorrhage",
        segmented_property_category=codes.SCT.MorphologicallyAbnormalStructure,
        segmented_property_type=codes.SCT.Hemorrhage,
        algorithm_type=hd.seg.SegmentAlgorithmTypeValues.AUTOMATIC,
        algorithm_identification=algorithm,
    )
    key = [ordered[0].SeriesInstanceUID, algorithm_name, algorithm_version]
    return hd.seg.Segmentation(
        source_images=ordered,
        pixel_array=frames,
        segmentation_type=hd.seg.SegmentationTypeValues.BINARY,
        segment_descriptions=[segment],
        series_instance_uid=generate_uid(entropy_srcs=key + ["series"]),
        series_number=900,
        sop_instance_uid=generate_uid(entropy_srcs=key + ["instance"]),
        instance_number=1,
        manufacturer="medical-ai",
        manufacturer_model_name=algorithm_name,
        software_versions=algorithm_version,
        device_serial_number="gateway",
        series_description=f"AI hemorrhage {algorithm_name} {algorithm_version}",
    )


def volume_ml(mask):
    return float((np.asanyarray(mask.dataobj) > 0).sum() * np.prod(mask.header.get_zooms()[:3]) / 1000)
