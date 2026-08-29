#!/usr/bin/env python3
"""Verify that v26-4 C0/C1 resolved configs differ only at the frozen seam."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


CELLS = ("C0S0", "C0S1", "C1S0", "C1S1")
IDENTITY = {
    "v26_cell", "experiment_name", "experiment_dir", "output_dir", "env.config.experiment_name",
    "callbacks.autoresume.save_dir", "callbacks.model_save.save_dir", "save_dir", "wandb.wandb_dir",
    "timestamp", "eval_timestamp",
}
SEED_LEAVES = {"seed", "env.config.a2_v26_side_permutation_seed"}
SOURCE_SUFFIX = "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise RuntimeError(f"non-string resolved config key below {prefix!r}")
            result.update(flatten(child, f"{prefix}.{key}" if prefix else key))
        return result
    return {prefix: value}


def changed(left: dict[str, Any], right: dict[str, Any]) -> set[str]:
    return {key for key in set(left) | set(right) if left.get(key) != right.get(key)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def assert_exact_diff(label: str, left: dict[str, Any], right: dict[str, Any], expected: set[str]) -> list[str]:
    observed = changed(left, right) - IDENTITY
    if observed != expected:
        raise RuntimeError(f"{label} violates frozen seam: observed={sorted(observed)}, expected={sorted(expected)}")
    return sorted(observed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", action="append", required=True, metavar="CELL=PATH")
    parser.add_argument("--canonical-key", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.canonical_key.startswith("env.config."), "canonical key must be env.config leaf")
    paths: dict[str, Path] = {}
    for item in args.config:
        cell, separator, raw_path = item.partition("=")
        if not separator or cell not in CELLS or cell in paths:
            raise ValueError("--config requires unique C0S0/C0S1/C1S0/C1S1=PATH")
        paths[cell] = Path(raw_path)
    require(set(paths) == set(CELLS), "resolved matrix requires exactly four frozen cells")
    leaves = {cell: flatten(yaml.safe_load(path.read_text(encoding="utf-8"))) for cell, path in paths.items()}
    required = {
        args.canonical_key, "checkpoint", "checkpoint_load_mode", "policy_only_load_actor_rms",
        "auto_load_latest", "seed", "num_envs", "algo.trl.num_total_batches",
        "callbacks.model_save.save_frequency", "env.config.a2_v26_side_permutation_seed",
        "env.config.a2_v26_door_open_lr", "env.config.a2_v26_2_telemetry_enabled",
        "env.config.a2_v26_2_handle_depression_scale", "env.config.a2_v26_3_telemetry_enabled",
        "env.config.a2_v26_3_handle_creation_scale", "env.config.a2_stage3_unlatch_near_closed_hinge_threshold",
        "rewards.reward_scales.push_door_handle", "rewards.reward_scales.a2_stage3_handle_depression",
        "rewards.reward_scales.a2_stage3_handle_creation",
        "robot.control.stiffness.arm_j7", "robot.control.stiffness.arm_j8",
        "robot.control.damping.arm_j7", "robot.control.damping.arm_j8",
        "simulator.config.sim.physx.num_velocity_iterations",
    }
    cells = {}
    for cell, table in leaves.items():
        missing = sorted(required - set(table))
        require(not missing, f"{cell} misses required leaves: {missing}")
        seed = int(cell[-1])
        canonical_on = cell.startswith("C1")
        fixed = (
            table["checkpoint_load_mode"], table["policy_only_load_actor_rms"], table["auto_load_latest"],
            table["seed"], table["num_envs"], table["algo.trl.num_total_batches"],
            table["callbacks.model_save.save_frequency"], table["env.config.a2_v26_side_permutation_seed"],
            table["env.config.a2_v26_door_open_lr"], table["env.config.a2_v26_2_telemetry_enabled"],
            table["env.config.a2_v26_2_handle_depression_scale"], table["env.config.a2_v26_3_telemetry_enabled"],
            table["env.config.a2_v26_3_handle_creation_scale"], table["env.config.a2_stage3_unlatch_near_closed_hinge_threshold"],
            table["rewards.reward_scales.push_door_handle"], table["rewards.reward_scales.a2_stage3_handle_depression"],
            table["rewards.reward_scales.a2_stage3_handle_creation"],
            table["robot.control.stiffness.arm_j7"], table["robot.control.stiffness.arm_j8"],
            table["robot.control.damping.arm_j7"], table["robot.control.damping.arm_j8"], table["simulator.config.sim.physx.num_velocity_iterations"],
        )
        require(fixed == ("policy_only", True, False, seed, 4096, 750, 125, seed, "bilateral", True, 0.0, True, 6.0, 0.1, 0.0, 0.0, 6.0, 800.0, 800.0, 25.0, 25.0, 2), f"{cell} violates fixed formal contract: {fixed}")
        require(str(table["checkpoint"]).endswith(SOURCE_SUFFIX), f"{cell} source checkpoint is not CONT_STEP2000")
        require(table[args.canonical_key] is canonical_on, f"{cell} canonical switch mismatch")
        cells[cell] = {"seed": seed, "canonicalization_enabled": canonical_on, "bilateral_runtime_count": {"left": 2048, "right": 2048}}
    diffs = {
        "C0S0_to_C1S0": assert_exact_diff("C0S0->C1S0", leaves["C0S0"], leaves["C1S0"], {args.canonical_key}),
        "C0S1_to_C1S1": assert_exact_diff("C0S1->C1S1", leaves["C0S1"], leaves["C1S1"], {args.canonical_key}),
        "C0S0_to_C0S1": assert_exact_diff("C0S0->C0S1", leaves["C0S0"], leaves["C0S1"], SEED_LEAVES),
        "C1S0_to_C1S1": assert_exact_diff("C1S0->C1S1", leaves["C1S0"], leaves["C1S1"], SEED_LEAVES),
    }
    payload = {
        "schema": "a2_piper_base_v26_4_resolved_matrix_v1", "status": "STATIC_PASS",
        "canonicalization_key": args.canonical_key,
        "load_contract": {"mode": "policy_only", "actor_rms_loaded": True, "optimizer_value_scheduler_episode_state": "FRESH", "source": "CONT_STEP2000"},
        "cells": cells, "verified_changed_leaves": diffs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
