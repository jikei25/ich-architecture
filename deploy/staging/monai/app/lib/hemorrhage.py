"""Hemorrhage segmentation with one small 3D UNet, used by both hemorrhage_approved and hemorrhage_dev."""
import os
from datetime import datetime

import nibabel as nib
import numpy as np
import torch
from monai.inferers import SlidingWindowInferer
from monai.losses import DiceCELoss
from monai.networks.nets import UNet
from monai.transforms import (
    Activationsd,
    AsDiscreted,
    EnsureChannelFirstd,
    EnsureTyped,
    LoadImaged,
    Orientationd,
    RandCropByPosNegLabeld,
    RandFlipd,
    ScaleIntensityRanged,
    SelectItemsd,
    Spacingd,
    SqueezeDimd,
)
from monailabel.interfaces.tasks.infer_v2 import InferType
from monailabel.tasks.infer.basic_infer import BasicInferTask
from monailabel.tasks.train.basic_train import BasicTrainTask

LABELS = {"hemorrhage": 1}
SPACING = (1.5, 1.5, 5.0)
ROI = (96, 96, 16)


def network():
    return UNet(spatial_dims=3, in_channels=1, out_channels=2, channels=(16, 32, 64, 128), strides=(2, 2, 2),
                num_res_units=2)


def load_transforms(keys, modes):
    """Load, reorient to RAS, resample to SPACING and window the CT to 0-100 HU (blood is about 50-90 HU)."""
    return [
        LoadImaged(keys=keys),
        EnsureChannelFirstd(keys=keys),
        Orientationd(keys=keys, axcodes="RAS"),
        Spacingd(keys=keys, pixdim=SPACING, mode=modes),
        ScaleIntensityRanged(keys="image", a_min=0, a_max=100, b_min=0.0, b_max=1.0, clip=True),
    ]


class HemorrhageInfer(BasicInferTask):
    """NIfTI CT in, uint8 mask out on the input grid; the NIfTI `descrip` field names the model version."""

    def __init__(self, paths, version, description):
        super().__init__(path=None, network=network(), type=InferType.SEGMENTATION, labels=LABELS, dimension=3,
                         description=description, roi_size=ROI)
        self._paths = paths
        self._version = version

    def get_path(self, validate=True):
        existing = [p for p in self._paths() if p and (not validate or os.path.exists(p))]
        return existing[-1] if existing else None

    def is_valid(self):
        return self.get_path() is not None

    def pre_transforms(self, data=None):
        return load_transforms("image", "bilinear")

    def inferer(self, data=None):
        return SlidingWindowInferer(roi_size=ROI, sw_batch_size=4, overlap=0.25)

    def inverse_transforms(self, data=None):
        return []  # undo every invertible pre-transform (Spacingd, Orientationd): the mask keeps the input grid

    def post_transforms(self, data=None):
        return [
            EnsureTyped(keys="pred"),
            Activationsd(keys="pred", softmax=True),
            AsDiscreted(keys="pred", argmax=True),
            SqueezeDimd(keys="pred", dim=0),
        ]

    def writer(self, data, extension=None, dtype=None):
        result_file, result_json = super().writer(data, extension=".nii.gz", dtype="uint8")
        mask = nib.load(result_file)
        tagged = nib.Nifti1Image(np.asanyarray(mask.dataobj), mask.affine, mask.header)
        tagged.header["descrip"] = f"hemorrhage {self._version()}".encode()
        nib.save(tagged, result_file)
        return result_file, result_json


class HemorrhageTrain(BasicTrainTask):
    """Trains on a frozen copy of the reviewed labels, then publishes the best model to the registry as a candidate."""

    def __init__(self, model_dir, publish_path, registry, datasets_root, description):
        self._network = network()
        self._registry = registry
        self._datasets_root = datasets_root
        self._dataset_version = None
        super().__init__(model_dir, description, amp=False, publish_path=publish_path, labels=LABELS,
                         config={"max_epochs": 40, "val_split": 0.2})

    def network(self, context):
        return self._network

    def optimizer(self, context):
        return torch.optim.AdamW(context.network.parameters(), lr=1e-3, weight_decay=1e-5)

    def loss_function(self, context):
        return DiceCELoss(to_onehot_y=True, softmax=True)

    def pre_process(self, request, datastore):
        self._dataset_version = datetime.now().strftime("dataset-%Y%m%d-%H%M%S")
        return datastore.freeze_reviewed(os.path.join(self._datasets_root, self._dataset_version))

    def train_pre_transforms(self, context):
        keys = ("image", "label")
        return [
            *load_transforms(keys, ("bilinear", "nearest")),
            RandCropByPosNegLabeld(keys=keys, label_key="label", spatial_size=ROI, pos=3, neg=1, num_samples=4,
                                   image_key="image", image_threshold=0),
            RandFlipd(keys=keys, prob=0.5, spatial_axis=0),
            SelectItemsd(keys=keys),
        ]

    def train_post_transforms(self, context):
        return [
            EnsureTyped(keys="pred"),
            Activationsd(keys="pred", softmax=True),
            AsDiscreted(keys=("pred", "label"), argmax=(True, False), to_onehot=(2, 2)),
        ]

    def val_pre_transforms(self, context):
        keys = ("image", "label")
        return [*load_transforms(keys, ("bilinear", "nearest")), SelectItemsd(keys=keys)]

    def val_inferer(self, context):
        return SlidingWindowInferer(roi_size=ROI, sw_batch_size=4, overlap=0.25)

    def __call__(self, request, datastore):
        stats = super().__call__(request, datastore)
        metrics = {k: stats[k] for k in ("best_metric", "best_metric_epoch", "epochs", "total_time") if k in stats}
        version = self._registry.publish(self._publish_path, {"dataset": self._dataset_version, "metrics": metrics})
        return {**stats, "registry_version": version}
