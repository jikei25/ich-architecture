"""Self-checks of nifti_bridge, run inside the gateway image:
docker run --rm -v "$PWD:/staging" --entrypoint python3 medical-ai/orthanc-ai:26.9.1 /staging/gateway/plugin/test_nifti_bridge.py
"""
import random
import sys
import tempfile
import types
from pathlib import Path

import nibabel as nib
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "tools")]
# The loader imports pynetdicom only to send C-STORE, which these checks do not use.
sys.modules.setdefault("pynetdicom", types.SimpleNamespace(AE=None))

from load_nifti import slices  # noqa: E402
from nifti_bridge import mask_to_seg, series_to_nifti  # noqa: E402

# Same orientation and spacing as the CT-ICH scans (LAS, 0.45 mm pixels, 5 mm slices), reduced grid.
SOURCE_AFFINE = np.array([[-0.45, 0, 0, 115.0], [0, 0.45, 0, -96.0], [0, 0, 5.0, -40.0], [0, 0, 0, 1]])
SHAPE = (16, 12, 5)


def source_series(directory: Path):
    rng = np.random.default_rng(7)
    volume = rng.integers(-1024, 2000, SHAPE).astype(np.int16)
    path = directory / "001.nii"
    nib.save(nib.Nifti1Image(volume, SOURCE_AFFINE), path)
    datasets = list(slices(path, "TEST"))
    random.Random(3).shuffle(datasets)
    return nib.load(path), datasets


def ras_voxels(image):
    canonical = nib.as_closest_canonical(image)
    return np.asanyarray(canonical.dataobj), canonical.affine


def mask_on_grid(mask: np.ndarray, image):
    """Reorient a mask drawn on the source grid onto the grid of `image`, as the AI service returns it."""
    source = nib.as_closest_canonical(nib.Nifti1Image(mask, SOURCE_AFFINE))
    transform = nib.orientations.ornt_transform(
        nib.orientations.axcodes2ornt("RAS"), nib.orientations.io_orientation(image.affine))
    return nib.Nifti1Image(np.asanyarray(source.as_reoriented(transform).dataobj), image.affine)


def frame_sources(seg):
    return [frame.DerivationImageSequence[0].SourceImageSequence[0].ReferencedSOPInstanceUID
            for frame in seg.PerFrameFunctionalGroupsSequence]


def test_volume_keeps_voxels_and_world_geometry(source, datasets):
    ordered, image = series_to_nifti(datasets)
    expected_voxels, expected_affine = ras_voxels(source)
    voxels, affine = ras_voxels(image)
    assert image.get_data_dtype() == np.int16
    assert np.array_equal(voxels, expected_voxels), "voxel values or order differ"
    assert np.allclose(affine, expected_affine, atol=1e-3), f"affine differs:\n{affine}\n{expected_affine}"
    assert [ds.InstanceNumber for ds in ordered] == sorted(ds.InstanceNumber for ds in ordered)


def test_seg_frames_reference_the_masked_slices(source, datasets):
    ordered, image = series_to_nifti(datasets)
    mask = np.zeros(SHAPE, np.uint8)
    mask[3:7, 2:5, 1] = 1
    mask[10, 8, 3] = 1
    seg = mask_to_seg(ordered, image, mask_on_grid(mask, image), "test-model", "1")

    by_uid = {ds.SOPInstanceUID: ds for ds in datasets}
    referenced = [by_uid[uid] for uid in frame_sources(seg)]
    assert seg.Modality == "SEG"
    assert sorted(ds.InstanceNumber for ds in referenced) == [2, 4]
    for frame, ds in zip(seg.pixel_array, referenced):
        k = ds.InstanceNumber - 1
        # Same pixel layout as the CT slice written by the loader.
        assert np.array_equal(frame, mask[:, ::-1, k].T), f"mask pixels misplaced on slice {k}"


def test_seg_uids_are_stable_across_runs(source, datasets):
    ordered, image = series_to_nifti(datasets)
    mask = mask_on_grid(np.ones(SHAPE, np.uint8), image)
    first = mask_to_seg(ordered, image, mask, "test-model", "1")
    second = mask_to_seg(ordered, image, mask, "test-model", "1")
    assert (first.SeriesInstanceUID, first.SOPInstanceUID) == (second.SeriesInstanceUID, second.SOPInstanceUID)
    assert mask_to_seg(ordered, image, mask, "test-model", "2").SOPInstanceUID != first.SOPInstanceUID


def test_empty_mask_still_produces_a_seg(source, datasets):
    ordered, image = series_to_nifti(datasets)
    seg = mask_to_seg(ordered, image, nib.Nifti1Image(np.zeros(SHAPE, np.uint8), image.affine), "test-model", "1")
    assert seg.Modality == "SEG"


def test_mask_on_another_grid_is_rejected(source, datasets):
    ordered, image = series_to_nifti(datasets)
    shifted = image.affine.copy()
    shifted[0, 3] += 5
    for mask in (nib.Nifti1Image(np.zeros(SHAPE, np.uint8), shifted),
                 nib.Nifti1Image(np.zeros((16, 12, 4), np.uint8), image.affine)):
        try:
            mask_to_seg(ordered, image, mask, "test-model", "1")
        except ValueError:
            continue
        raise AssertionError("a mask on another grid was accepted")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        source, datasets = source_series(Path(tmp))
        tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
        for test in tests:
            test(source, datasets)
            print(f"ok {test.__name__}")
