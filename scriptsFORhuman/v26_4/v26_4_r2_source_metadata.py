#!/usr/bin/env python3
"""Capture or verify R2 execution provenance using path, size, and mtime only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCKED = (
    "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t/rl/envs/door/a2_v26_4_canonicalization.py",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_bilateral_grasp_foundation.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_C0_CANONICAL_OFF.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_C1_CANONICAL_ON.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_eval_natural_start.yaml",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/C/canonical_identity_proof.json",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/C/c_route.json",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/M/k_gate_receipt.json",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/M/static/resolved_configs/C0S0.yaml",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/M/static/resolved_configs/C0S1.yaml",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/M/static/resolved_configs/C1S0.yaml",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/M/static/resolved_configs/C1S1.yaml",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/M/static/resolved_matrix.json",
    "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/M/static/command_registry.json",
    "scriptsFORhuman/v26_4/v26_4_r2_orchestration_gate.py",
    "scriptsFORhuman/v26_4/v26_4_r2_orchestrate.sh",
    "scriptsFORhuman/v26_4/v26_4_r2_orchestrate_train_cell.sh",
    "scriptsFORhuman/v26_4/v26_4_r2_orchestrate_eval_lane.sh",
    "scriptsFORhuman/v26_4/v26_4_r2_orchestrate_main_eval_cell.sh",
    "scriptsFORhuman/v26_4/v26_4_r2_analyze_bilateral_foundation.py",
    "scriptsFORhuman/v26_4/v26_4_r2_registry.py",
    "scriptsFORhuman/v26_4/v26_4_r2_compose_matrix.py",
    "scriptsFORhuman/v26_4/v26_4_r2_source_metadata.py",
    "scriptsFORhuman/v26_4/v26_4_r2_verify_resolved_matrix.py",
    "scriptsFORhuman/v26_4/v26_4_r2_verify_registry.py",
    "scriptsFORhuman/v26_4/v26_4_analyze_bilateral_foundation.py",
    "scriptsFORhuman/v26_4/run_base_v26_4_train_cell.sh",
    "scriptsFORhuman/v26_4/run_base_v26_4_eval_lane.sh",
)


def metadata() -> dict[str, dict[str, int]]:
    result = {}
    for relative in LOCKED:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"required R2 source-metadata path is missing: {path}")
        stat = path.stat()
        result[relative] = {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-against", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite source metadata artifact: {args.output}")
    current = metadata()
    if args.verify_against:
        prior = json.loads(args.verify_against.read_text(encoding="utf-8"))
        if prior.get("locked_files") != current:
            raise RuntimeError("R2 source metadata changed after capture")
        payload = {"schema": "a2_piper_base_v26_4_r2_source_metadata_verification_v1", "status": "SOURCE_METADATA_VERIFIED", "identity_method": "path_size_mtime_no_content_hash", "capture": str(args.verify_against.resolve()), "locked_files": current}
    else:
        payload = {"schema": "a2_piper_base_v26_4_r2_source_metadata_v1", "status": "SOURCE_METADATA_CAPTURED", "identity_method": "path_size_mtime_no_content_hash", "locked_files": current}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
