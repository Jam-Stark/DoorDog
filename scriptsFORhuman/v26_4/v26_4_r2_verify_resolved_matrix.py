#!/usr/bin/env python3
"""Verify the four R2 static resolved configs before any GPU allocation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


CELLS = ("C0S0", "C0S1", "C1S0", "C1S1")
SEAM = "env.config.a2_v26_4_side_canonicalization_enabled"
IDENTITY = {"v26_cell", "experiment_name", "experiment_dir", "output_dir"}


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise RuntimeError(f"non-string config key below {prefix}")
            result.update(flatten(child, f"{prefix}.{key}" if prefix else key))
        return result
    return {prefix: value}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", action="append", required=True, metavar="CELL=PATH")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-against", type=Path)
    args = parser.parse_args()
    require((args.output is None) != (args.verify_against is None), "choose exactly one of --output or --verify-against")
    paths = {}
    for value in args.config:
        cell, separator, raw = value.partition("=")
        require(separator and cell in CELLS and cell not in paths, "configs must be unique C0S0/C0S1/C1S0/C1S1")
        paths[cell] = Path(raw)
    require(set(paths) == set(CELLS), "exactly four R2 resolved configs are required")
    tables = {cell: flatten(yaml.safe_load(path.read_text(encoding="utf-8"))) for cell, path in paths.items()}
    fixed = {
        "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True,
        "auto_load_latest": False, "num_envs": 4096, "algo.trl.num_total_batches": 750,
        "callbacks.model_save.save_frequency": 125, "env.config.a2_v26_door_open_lr": "bilateral",
        "env.config.a2_v26_2_telemetry_enabled": True, "env.config.a2_v26_3_telemetry_enabled": True,
        "env.config.a2_v26_2_handle_depression_scale": 0.0,
        "env.config.a2_v26_3_handle_creation_scale": 6.0,
        "rewards.reward_scales.push_door_handle": 0.0,
        "rewards.reward_scales.a2_stage3_handle_depression": 0.0,
        "rewards.reward_scales.a2_stage3_handle_creation": 6.0,
    }
    for cell, table in tables.items():
        seed = int(cell[-1])
        expected_on = cell.startswith("C1")
        for key, expected in fixed.items():
            require(table.get(key) == expected, f"{cell} violates {key}: {table.get(key)!r}")
        require(table.get("seed") == seed and table.get("env.config.a2_v26_side_permutation_seed") == seed, f"{cell} seed contract mismatch")
        require(table.get(SEAM) is expected_on, f"{cell} canonical seam mismatch")
        checkpoint = table.get("checkpoint")
        require(isinstance(checkpoint, str) and checkpoint.endswith("continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"), f"{cell} source checkpoint mismatch")

    def difference(left: str, right: str) -> list[str]:
        changed = {key for key in set(tables[left]) | set(tables[right]) if tables[left].get(key) != tables[right].get(key)} - IDENTITY
        return sorted(changed)

    expected_seed = ["env.config.a2_v26_side_permutation_seed", "seed"]
    diffs = {
        "C0S0_to_C1S0": difference("C0S0", "C1S0"), "C0S1_to_C1S1": difference("C0S1", "C1S1"),
        "C0S0_to_C0S1": difference("C0S0", "C0S1"), "C1S0_to_C1S1": difference("C1S0", "C1S1"),
    }
    require(diffs["C0S0_to_C1S0"] == [SEAM] and diffs["C0S1_to_C1S1"] == [SEAM], f"C0/C1 differs beyond C seam: {diffs}")
    require(diffs["C0S0_to_C0S1"] == expected_seed and diffs["C1S0_to_C1S1"] == expected_seed, f"seed pairs differ beyond seed: {diffs}")
    payload = {"schema": "a2_piper_base_v26_4_r2_resolved_matrix_v1", "status": "STATIC_PASS", "seam_key": SEAM, "cells": {cell: {"seed": int(cell[-1]), "canonicalization_enabled": cell.startswith("C1"), "bilateral_runtime_count": {"left": 2048, "right": 2048}} for cell in CELLS}, "verified_changed_leaves": diffs}
    if args.verify_against:
        require(args.verify_against.is_file(), f"resolved matrix artifact is missing: {args.verify_against}")
        require(json.loads(args.verify_against.read_text(encoding="utf-8")) == payload, "resolved matrix artifact differs from current four-cell compose")
        print(args.verify_against)
        return
    require(not args.output.exists(), f"refusing to overwrite resolved matrix artifact: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
