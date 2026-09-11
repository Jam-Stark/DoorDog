"""Snapshot v28 execution inputs and verify their bytes without digests."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from v28_contract import ROOT, HERE


def execution_inputs():
    paths = set((ROOT / "gr00t/rl").rglob("*.py"))
    paths.update((ROOT / "gr00t/rl/config").rglob("*.yaml"))
    paths.update(HERE.glob("*.py"))
    paths.update(HERE.glob("a2_piper_base_v28_*.md"))
    paths.add(HERE / "camera/U3_F39_H140.json")
    paths.add(HERE / "camera/d435_native_sim_parameters_20260907.json")
    paths.add(HERE / "planner_evidence_20260909/asset/mount_clearance_check.py")
    paths.add(HERE / "planner_evidence_20260909/camera/t4_clearance.py")
    asset = ROOT / "gr00t/rl/data/robots/a2_piper_v28_merged_20260909"
    suffixes = {".urdf", ".usd", ".usda", ".usdc", ".stl", ".obj", ".mtl", ".png", ".jpg", ".json", ".yaml"}
    paths.update(path for path in asset.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)
    policy = ROOT / "gr00t/rl/data/policies/A2_Base"
    paths.update(path for path in policy.iterdir() if path.is_file() and path.suffix in {".pt", ".json", ".yaml"})
    return sorted(paths)


def create(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    entries = []
    for source in execution_inputs():
        relative = source.relative_to(ROOT)
        copied = directory / "files" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, copied)
        if source.read_bytes() != copied.read_bytes():
            raise RuntimeError(f"snapshot bytes differ: {source}")
        entries.append({"path": str(relative), "bytes": source.stat().st_size})
    manifest = {"schema": "a2_piper_v28_source_bytes_v1", "state": "BYTE_COPY_VERIFIED",
                "created_at": datetime.now(timezone.utc).isoformat(), "source_root": str(ROOT),
                "isaaclab_root": "/home/baoquanc/workspace/IsaacLab", "files": entries}
    (directory / "source_lock.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def check(directory: Path):
    manifest = json.loads((directory / "source_lock.json").read_text())
    changed = [entry["path"] for entry in manifest["files"]
               if (ROOT / entry["path"]).read_bytes() != (directory / "files" / entry["path"]).read_bytes()]
    if changed:
        raise RuntimeError(f"source bytes changed: {changed}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["create", "check"])
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    result = create(args.directory) if args.mode == "create" else check(args.directory)
    print(json.dumps({"state": result["state"], "files": len(result["files"]), "directory": str(args.directory.resolve())}))
