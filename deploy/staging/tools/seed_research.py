"""Seeds the research Orthanc with CT-ICH cases and their ground-truth masks as reviewed SEG labels.

The public dataset is already de-identified, so it enters the label store directly; later labels come from the
gateway (AI drafts) and from MONAI Label (annotator saves). Runs in the MONAI Label image:

docker run --rm --network host -e RESEARCH_USER=gateway -e RESEARCH_PASSWORD \
  -v "$PWD/tools:/tools:ro" -v "$PWD/gateway/plugin:/plugin:ro" -v /path/to/CT-ICH-PhysioNet:/data:ro \
  --entrypoint python medical-ai/monai-label:0.8.8 /tools/seed_research.py --orthanc http://<host>:8043 \
  --dataset /data --exclude 054 070 078
"""
import argparse
import io
import os
import sys
from pathlib import Path

import requests

sys.path += ["/tools", "/plugin"]
from load_nifti import slices  # noqa: E402
from mock_ai import mask_on_grid  # noqa: E402
from nifti_bridge import mask_to_seg, series_to_nifti  # noqa: E402


def upload(session, url, dataset):
    buffer = io.BytesIO()
    dataset.save_as(buffer, enforce_file_format=True)
    response = session.post(f"{url}/instances", data=buffer.getvalue())
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--orthanc", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--exclude", nargs="*", default=[], help="case numbers kept for the clinical path")
    args = parser.parse_args()

    session = requests.Session()
    session.auth = (os.environ["RESEARCH_USER"], os.environ["RESEARCH_PASSWORD"])
    for ct in sorted((args.dataset / "ct_scans").glob("*.nii")):
        if ct.stem in args.exclude:
            continue
        datasets = list(slices(ct, "CTICH"))
        ordered, volume = series_to_nifti(datasets)
        seg = mask_to_seg(ordered, volume, mask_on_grid(args.dataset / "masks" / ct.name, volume),
                          "CT-ICH ground truth", "1.0")
        for dataset in datasets:
            upload(session, args.orthanc, dataset)
        series = upload(session, args.orthanc, seg)["ParentSeries"]
        for path, body in (("labels/reviewed", ""), ("metadata/Author", "PhysioNet CT-ICH"), ("metadata/Role", "dataset")):
            session.put(f"{args.orthanc}/series/{series}/{path}", data=body).raise_for_status()
        print(f"{ct.stem}: {len(datasets)} slices + reviewed SEG", flush=True)


if __name__ == "__main__":
    main()
