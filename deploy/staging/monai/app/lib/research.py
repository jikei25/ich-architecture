"""MONAI Label datastore on the research Orthanc, which holds only de-identified CT series and every SEG label version.

Each SEG series carries one Orthanc label with its status: draft (an AI result), unreviewed (a person's save) or
reviewed (picked by a reviewer for training). Author, role and drafting model are Orthanc user metadata.

Usage (inside the research MONAI Label container): python research.py list | review <SEG SeriesInstanceUID>
"""
import argparse
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone

import requests
import SimpleITK as sitk
from monailabel.datastore.dicom import DICOMWebDatastore
from monailabel.datastore.local import LocalDatastore
from monailabel.datastore.utils.convert import dicom_seg_to_itk_image
from monailabel.datastore.utils.dicom import dicom_web_download_series
from monailabel.interfaces.datastore import DefaultLabelTag

logger = logging.getLogger(__name__)

DRAFT, UNREVIEWED, REVIEWED = "draft", "unreviewed", "reviewed"
STATUSES = (DRAFT, UNREVIEWED, REVIEWED)


class Orthanc:
    def __init__(self, url, session):
        self.url = url.rstrip("/")
        self.session = session

    def call(self, method, path, **kwargs):
        response = self.session.request(method, f"{self.url}{path}", **kwargs)
        response.raise_for_status()
        return response.json() if "json" in response.headers.get("content-type", "") else response.text

    def label_versions(self):
        """Every SEG series with the CT series it labels, its status and provenance, oldest first."""
        query = {"Level": "Series", "Query": {"Modality": "SEG"}, "Expand": True}
        versions = []
        for series in self.call("POST", "/tools/find", json=query):
            instance = series["Instances"][0]
            image = self.call("GET", f"/instances/{instance}/content/0008-1115/0/0020-000e").strip("\x00 ")
            meta = self.call("GET", f"/series/{series['ID']}/metadata?expand")
            status = next((label for label in series.get("Labels", []) if label in STATUSES), UNREVIEWED)
            versions.append({
                "seg": series["MainDicomTags"]["SeriesInstanceUID"],
                "image": image,
                "status": status,
                "author": meta.get("Author", ""),
                "role": meta.get("Role", ""),
                "draft_model": meta.get("DraftModel", ""),
                "saved": series["LastUpdate"],
            })
        return sorted(versions, key=lambda v: v["saved"])

    def mark(self, seg_uid, status, **metadata):
        found = self.call("POST", "/tools/lookup", data=seg_uid)
        series_id = next(r["ID"] for r in found if r["Type"] == "Series")
        for label in self.call("GET", f"/series/{series_id}/labels"):
            if label in STATUSES and label != status:
                self.call("DELETE", f"/series/{series_id}/labels/{label}")
        self.call("PUT", f"/series/{series_id}/labels/{status}")
        for name, value in metadata.items():
            self.call("PUT", f"/series/{series_id}/metadata/{name}", data=value)


class ResearchDatastore(DICOMWebDatastore):
    def __init__(self, client, orthanc, cache_path=None):
        self.orthanc = orthanc
        super().__init__(client, search_filter={"Modality": "CT"}, cache_path=cache_path)

    def get_labeled_images(self, label_tag=None, labels=None):
        """A CT counts as labeled once a person has saved a label for it; a draft alone does not."""
        return sorted({v["image"] for v in self.orthanc.label_versions() if v["status"] != DRAFT})

    def get_image_uri(self, image_id):
        if image_id not in self.list_images():
            raise ValueError(f"{image_id!r} is not a CT series of this datastore")
        uri = super().get_image_uri(image_id)
        self._attach_draft(image_id, uri)
        return uri

    def save_label(self, image_id, label_filename, label_tag, label_info, label_id=""):
        """A person's save is uploaded as a new SEG series, so no earlier version is overwritten."""
        saved = super().save_label(image_id, label_filename, label_tag, label_info, label_id)
        if label_tag == DefaultLabelTag.FINAL:
            draft = self.get_label_by_image_id(image_id, DefaultLabelTag.ORIGINAL)
            draft_model = self.get_label_info(draft, DefaultLabelTag.ORIGINAL).get("model", "") if draft else ""
            # shortcut: the author comes from the request params; with MONAI Label auth on, take the logged-in user.
            self.orthanc.mark(label_info["SeriesInstanceUID"], UNREVIEWED, Author=label_info.get("author", "unknown"),
                              Role=label_info.get("role", "annotator"), DraftModel=draft_model)
        return saved

    def freeze_reviewed(self, dataset_dir):
        """Copies the newest reviewed label of each CT, with the CT, into dataset_dir and returns the datalist."""
        reviewed = {v["image"]: v for v in self.orthanc.label_versions() if v["status"] == REVIEWED}
        for sub in ("images", "labels"):
            os.makedirs(os.path.join(dataset_dir, sub))
        datalist = []
        for image_id, version in sorted(reviewed.items()):
            image_uri = DICOMWebDatastore.get_image_uri(self, image_id)
            image = os.path.join(dataset_dir, "images", f"{image_id}.nii.gz")
            label = os.path.join(dataset_dir, "labels", f"{image_id}.nii.gz")
            shutil.copyfile(image_uri, image)
            shutil.move(self._seg_on_grid(version["seg"], image_uri), label)
            datalist.append({"image": image, "label": label})
        manifest = {"created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cases": list(reviewed.values())}
        with open(os.path.join(dataset_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        return datalist

    def _attach_draft(self, image_id, image_uri):
        """Caches the newest draft of a CT as its "original" label, which the Slicer extension opens with the image."""
        if self.get_label_by_image_id(image_id, DefaultLabelTag.ORIGINAL):
            return
        drafts = [v for v in self.orthanc.label_versions() if v["image"] == image_id and v["status"] == DRAFT]
        if not drafts:
            return
        label = self._seg_on_grid(drafts[-1]["seg"], image_uri)
        info = {"seg": drafts[-1]["seg"], "model": drafts[-1]["draft_model"]}
        LocalDatastore.save_label(self, image_id, label, DefaultLabelTag.ORIGINAL, info)
        os.unlink(label)

    def _seg_on_grid(self, seg_uid, image_uri):
        """Downloads a SEG series and resamples it onto the CT grid, because a SEG keeps only its non-empty frames."""
        seg_dir = tempfile.mkdtemp()
        try:
            dicom_web_download_series(None, seg_uid, seg_dir, self._client, self._fetch_by_frame)
            seg_file = dicom_seg_to_itk_image(seg_dir)
        finally:
            shutil.rmtree(seg_dir)
        label = sitk.Resample(sitk.ReadImage(seg_file), sitk.ReadImage(image_uri), sitk.Transform(),
                              sitk.sitkNearestNeighbor, 0, sitk.sitkUInt8)
        os.unlink(seg_file)
        output = tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False).name
        sitk.WriteImage(label, output)
        return output


def orthanc_from_env():
    session = requests.Session()
    session.auth = (os.environ["MONAI_LABEL_DATASTORE_USERNAME"], os.environ["MONAI_LABEL_DATASTORE_PASSWORD"])
    return Orthanc(os.environ["RESEARCH_ORTHANC_URL"], session)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List label versions, or mark one as reviewed.")
    parser.add_argument("command", choices=["list", "review"])
    parser.add_argument("seg", nargs="?")
    args = parser.parse_args()
    orthanc = orthanc_from_env()
    if args.command == "review":
        orthanc.mark(args.seg, REVIEWED, ReviewedAt=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    for v in orthanc.label_versions():
        print(f"{v['saved']}  {v['status']:<10}  image ...{v['image'][-12:]}  seg ...{v['seg'][-12:]}  "
              f"author={v['author']} role={v['role']} draft_model={v['draft_model']}")
