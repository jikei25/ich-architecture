"""Self-checks of the MONAI Label app, run in its image:

docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD/monai/test_app.py:/test_app.py:ro" --entrypoint python \
  medical-ai/monai-label:0.8.8 /test_app.py
"""
import os
import sys
import tempfile

import nibabel as nib
import numpy as np
import torch

sys.path.insert(0, "/app")
from lib.hemorrhage import HemorrhageInfer, network  # noqa: E402
from lib.registry import Registry  # noqa: E402


def test_mask_keeps_the_input_grid():
    # Same axis layout as the gateway's series_to_nifti output for an axial head CT: x flipped, y flipped.
    affine = np.array([[-0.45, 0, 0, 115.0], [0, -0.45, 0, 100.0], [0, 0, 5.0, -20.0], [0, 0, 0, 1]])
    volume = np.random.default_rng(0).integers(-1000, 100, size=(128, 120, 12)).astype(np.int16)
    with tempfile.TemporaryDirectory() as tmp:
        image_path = os.path.join(tmp, "ct.nii.gz")
        nib.save(nib.Nifti1Image(volume, affine), image_path)
        model_path = os.path.join(tmp, "model.pt")
        torch.save(network().state_dict(), model_path)

        task = HemorrhageInfer(paths=lambda: [model_path], version=lambda: "v-test", description="")
        result_file, _ = task({"image": image_path, "device": "cpu"})
        mask = nib.load(result_file)

        assert mask.shape == volume.shape, mask.shape
        assert np.allclose(mask.affine, affine, atol=1e-3), mask.affine
        assert mask.get_data_dtype() == np.uint8
        assert set(np.unique(np.asanyarray(mask.dataobj))) <= {0, 1}
        assert mask.header["descrip"].item().decode() == "hemorrhage v-test"


def test_registry_serves_only_the_approved_version():
    with tempfile.TemporaryDirectory() as tmp:
        registry = Registry(tmp)
        model = os.path.join(tmp, "trained.pt")
        open(model, "wb").write(b"weights")
        assert registry.approved_model() is None
        assert registry.publish(model, {"dataset": "d1"}) == "v1"
        assert registry.publish(model, {"dataset": "d2"}) == "v2"
        assert registry.approved_model() is None
        registry.approve("v1")
        assert registry.approved_model() == os.path.join(tmp, "hemorrhage", "v1", "model.pt")
        assert registry.versions() == ["v1", "v2"]


if __name__ == "__main__":
    for name, check in list(globals().items()):
        if name.startswith("test_"):
            check()
            print(f"ok  {name}")
