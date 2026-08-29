#!/usr/bin/env python3
"""Capture or verify a no-hash source/config identity receipt for v26-3 M."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCKED = (
    "gr00t/rl/envs/door/a2_v26_3_creation.py",
    "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py",
    "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v26_acquisition.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_3_event_time_creation.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_3_M0_OLD.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_3_M1_CREATE.yaml",
    "scriptsFORhuman/v26_3/run_base_v26_3_train_cell.sh",
)
RECEIPTS = (
    "v26_3_main_m0_s0",
    "v26_3_main_m0_s1",
    "v26_3_main_m1_s0",
    "v26_3_main_m1_s1",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-against", type=Path)
    args = parser.parse_args()
    files = {}
    for relative in LOCKED:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"source-lock path is missing: {path}")
        stat = path.stat()
        files[relative] = {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if args.verify_against is not None:
        captured = json.loads(args.verify_against.read_text(encoding="utf-8"))
        if captured.get("locked_files") != files:
            raise RuntimeError("formal source/config identity changed after source-lock capture")
        receipts = {}
        for name in RECEIPTS:
            path = ROOT / ".ai/runtime/runs" / name / "RUN_RECEIPT.json"
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if receipt.get("state") != "PASS" or receipt.get("process_returncode") != 0:
                raise RuntimeError(f"formal receipt did not close PASS: {name}")
            receipts[name] = {
                "state": receipt["state"],
                "process_returncode": receipt["process_returncode"],
                "finished_at": receipt.get("finished_at"),
            }
        payload = {
            "schema": "a2_piper_base_v26_3_source_lock_verification_v1",
            "status": "SOURCE_LOCK_VERIFIED",
            "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "identity_method": "path_size_mtime_no_content_hash",
            "capture_receipt": str(args.verify_against),
            "locked_files": files,
            "formal_receipts": receipts,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(args.output)
        return

    receipts = {}
    for name in RECEIPTS:
        path = ROOT / ".ai/runtime/runs" / name / "RUN_RECEIPT.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("state") != "RUNNING":
            raise RuntimeError(f"formal receipt is not running at source-lock capture: {name}")
        receipts[name] = {
            "state": payload["state"],
            "launched_at": payload.get("launched_at"),
            "command": payload.get("command"),
            "resources": payload.get("resources"),
        }
    payload = {
        "schema": "a2_piper_base_v26_3_source_lock_v1",
        "status": "SOURCE_LOCK_CAPTURED",
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "identity_method": "path_size_mtime_no_content_hash",
        "locked_files": files,
        "formal_receipts": receipts,
        "mutation_boundary": "do not modify locked source/config until M processes exit",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
