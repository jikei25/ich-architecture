"""Mock of the AI segmentation service for staging tests: answers with the CT-ICH ground-truth mask of the received volume.

Contract: POST /segment with a gzip NIfTI CT volume; the response is a gzip NIfTI uint8 mask on the same grid.
The volume is matched by a hash of its voxels in RAS orientation, so only a geometrically correct DICOM to NIfTI
conversion finds its mask (status 422 otherwise).

Usage: mock_ai.py --dataset /data/CT-ICH-PhysioNet [--port 8000]
"""
import argparse
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel import orientations


def fingerprint(image) -> str:
    canonical = nib.as_closest_canonical(image)
    return hashlib.sha1(np.ascontiguousarray(np.asanyarray(canonical.dataobj).astype(np.int16))).hexdigest()


def build_index(dataset: Path) -> dict:
    index = {}
    for scan in sorted((dataset / "ct_scans").glob("*.nii")):
        index[fingerprint(nib.load(scan))] = dataset / "masks" / scan.name
    return index


def mask_on_grid(mask_path: Path, volume):
    canonical = nib.as_closest_canonical(nib.load(mask_path))
    transform = orientations.ornt_transform(orientations.axcodes2ornt("RAS"), orientations.io_orientation(volume.affine))
    labels = (np.asanyarray(canonical.as_reoriented(transform).dataobj) > 0).astype(np.uint8)
    return nib.Nifti1Image(labels, volume.affine)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/segment":
            self.send_error(404)
            return
        volume = nib.Nifti1Image.from_bytes(gzip.decompress(self.rfile.read(int(self.headers["Content-Length"]))))
        mask_path = self.server.index.get(fingerprint(volume))
        if mask_path is None:
            self.send_error(422, "volume not found in the dataset")
            return
        payload = gzip.compress(mask_on_grid(mask_path, volume).to_bytes())
        self.send_response(200)
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.log_message("%s -> mask %s", volume.shape, mask_path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.index = build_index(args.dataset)
    print(f"indexed {len(server.index)} volumes, listening on port {args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
