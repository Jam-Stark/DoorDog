#!/usr/bin/env python3
"""Capture or verify v26-4 M source identity without content hashes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCKED = (
    "gr00t/rl/envs/door/a2_v26_3_creation.py",
    "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t/rl/envs/base_task/a2_base.py",
    "gr00t/rl/config/robot/A2_Piper/a2_piper.yaml",
    "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v26_acquisition.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_bilateral_grasp_foundation.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_C0_CANONICAL_OFF.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_C1_CANONICAL_ON.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_eval_natural_start.yaml",
    "scriptsFORhuman/v26_4/orchestrate_base_v26_4.sh",
    "scriptsFORhuman/v26_4/run_base_v26_4_train_cell.sh",
    "scriptsFORhuman/v26_4/run_base_v26_4_eval_lane.sh",
    "scriptsFORhuman/v26_4/run_base_v26_4_main_eval_cell.sh",
    "scriptsFORhuman/v26_4/v26_4_analyze_bilateral_foundation.py",
    "scriptsFORhuman/v26_4/v26_4_verify_resolved_matrix.py",
    "scriptsFORhuman/v26_4/v26_4_verify_command_registry.py",
    "logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/C/canonical_identity_proof.json",
)
RECEIPTS = (
    "v26_4_main_c0_canonical_off_s0",
    "v26_4_main_c0_canonical_off_s1",
    "v26_4_main_c1_canonical_on_s0",
    "v26_4_main_c1_canonical_on_s1",
)


def lock_files() -> dict[str, dict[str, int]]:
    result = {}
    for relative in LOCKED:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"source-lock path is missing: {path}")
        stat = path.stat()
        result[relative] = {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    return result


def receipt_path(name: str) -> Path:
    return ROOT / ".ai/runtime/runs" / name / "RUN_RECEIPT.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-against", type=Path)
    args = parser.parse_args()
    files = lock_files()
    if args.verify_against is not None:
        captured = json.loads(args.verify_against.read_text(encoding="utf-8"))
        if captured.get("locked_files") != files:
            raise RuntimeError("formal source/config identity changed after source-lock capture")
        receipts = {}
        for name in RECEIPTS:
            receipt = json.loads(receipt_path(name).read_text(encoding="utf-8"))
            if receipt.get("state") != "PASS" or receipt.get("process_returncode") != 0:
                raise RuntimeError(f"formal receipt did not close PASS: {name}")
            receipts[name] = {"state": receipt["state"], "process_returncode": receipt["process_returncode"], "finished_at": receipt.get("finished_at")}
        payload = {
            "schema": "a2_piper_base_v26_4_source_lock_verification_v1", "status": "SOURCE_LOCK_VERIFIED",
            "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "identity_method": "path_size_mtime_no_content_hash", "capture_receipt": str(args.verify_against),
            "locked_files": files, "formal_receipts": receipts,
        }
    else:
        receipts = {}
        for name in RECEIPTS:
            receipt = json.loads(receipt_path(name).read_text(encoding="utf-8"))
            if receipt.get("state") != "RUNNING":
                raise RuntimeError(f"formal receipt is not RUNNING at source-lock capture: {name}")
            receipts[name] = {"state": receipt["state"], "launched_at": receipt.get("launched_at"), "command": receipt.get("command"), "resources": receipt.get("resources")}
        payload = {
            "schema": "a2_piper_base_v26_4_source_lock_v1", "status": "SOURCE_LOCK_CAPTURED",
            "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "identity_method": "path_size_mtime_no_content_hash", "locked_files": files,
            "formal_receipts": receipts, "mutation_boundary": "do not modify locked source/config until all M processes exit",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
