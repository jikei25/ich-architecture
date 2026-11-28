"""Model registry: hemorrhage/<version>/model.pt with meta.json, and an `approved` file naming the approved version.

Usage: python registry.py --root /registry approve v2
"""
import argparse
import json
import os
import shutil
from datetime import datetime, timezone

MODEL = "hemorrhage"


class Registry:
    def __init__(self, root):
        self.model_dir = os.path.join(root, MODEL)

    def approved_version(self):
        pointer = os.path.join(self.model_dir, "approved")
        if not os.path.exists(pointer):
            return None
        with open(pointer) as f:
            return f.read().strip()

    def approved_model(self):
        version = self.approved_version()
        return os.path.join(self.model_dir, version, "model.pt") if version else None

    def versions(self):
        if not os.path.isdir(self.model_dir):
            return []
        return sorted((v for v in os.listdir(self.model_dir) if v.startswith("v")), key=lambda v: int(v[1:]))

    def publish(self, model_file, meta):
        versions = self.versions()
        version = f"v{int(versions[-1][1:]) + 1 if versions else 1}"
        target = os.path.join(self.model_dir, version)
        os.makedirs(target)
        # copyfile gives the new file a new mtime, which makes the inference task reload the network
        shutil.copyfile(model_file, os.path.join(target, "model.pt"))
        meta = {"version": version, "status": "candidate", "published": now(), **meta}
        write_json(os.path.join(target, "meta.json"), meta)
        return version

    def approve(self, version):
        meta_file = os.path.join(self.model_dir, version, "meta.json")
        with open(meta_file) as f:
            meta = json.load(f)
        meta.update(status="approved", approved=now())
        write_json(meta_file, meta)
        with open(os.path.join(self.model_dir, "approved"), "w") as f:
            f.write(version)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Approve a registered model version for inference.")
    parser.add_argument("--root", default="/registry")
    parser.add_argument("command", choices=["approve"])
    parser.add_argument("version")
    args = parser.parse_args()
    Registry(args.root).approve(args.version)
    print(f"approved {MODEL} {args.version}")
