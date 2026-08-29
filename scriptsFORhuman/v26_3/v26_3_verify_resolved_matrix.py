#!/usr/bin/env python3
"""Verify the frozen M0/M1 x seed0/1 v26-3 resolved-config seams."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise RuntimeError(f"non-string resolved-config key below {prefix!r}")
            result.update(flatten(child, f"{prefix}.{key}" if prefix else key))
        return result
    return {prefix: value}


def changed(left: dict[str, Any], right: dict[str, Any]) -> set[str]:
    return {
        key
        for key in set(left) | set(right)
        if left.get(key) != right.get(key)
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", action="append", required=True, metavar="CELL=PATH")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


IDENTITY = {
    "v26_cell",
    "experiment_name",
    "experiment_dir",
    "output_dir",
    "env.config.experiment_name",
    "callbacks.autoresume.save_dir",
    "callbacks.model_save.save_dir",
    "save_dir",
    "wandb.wandb_dir",
    "timestamp",
    "eval_timestamp",
}
OLD = "rewards.reward_scales.a2_stage3_handle_depression"
NEW = "rewards.reward_scales.a2_stage3_handle_creation"
LEGACY = "rewards.reward_scales.push_door_handle"
OLD_MIRROR = "env.config.rewards.reward_scales.a2_stage3_handle_depression"
NEW_MIRROR = "env.config.rewards.reward_scales.a2_stage3_handle_creation"
LEGACY_MIRROR = "env.config.rewards.reward_scales.push_door_handle"
OLD_BINDING = "env.config.a2_v26_2_handle_depression_scale"
NEW_BINDING = "env.config.a2_v26_3_handle_creation_scale"
SEED_LEAVES = {"seed", "env.config.a2_v26_side_permutation_seed"}
REWARD_LEAVES = {OLD, NEW, OLD_MIRROR, NEW_MIRROR, OLD_BINDING, NEW_BINDING}


def assert_exact_diff(
    label: str,
    left: dict[str, Any],
    right: dict[str, Any],
    expected: set[str],
) -> list[str]:
    observed = changed(left, right) - IDENTITY
    if observed != expected:
        raise RuntimeError(
            f"{label} violates frozen seam: observed={sorted(observed)}, "
            f"expected={sorted(expected)}"
        )
    return sorted(observed)


def main() -> None:
    args = parse_args()
    paths: dict[str, Path] = {}
    expected_cells = {"M0S0", "M0S1", "M1S0", "M1S1"}
    for item in args.config:
        cell, separator, raw_path = item.partition("=")
        if not separator or cell not in expected_cells or cell in paths:
            raise ValueError("--config requires unique M0S0/M0S1/M1S0/M1S1=PATH")
        paths[cell] = Path(raw_path)
    if set(paths) != expected_cells:
        raise RuntimeError("resolved matrix requires exactly four frozen cells")
    leaves = {
        cell: flatten(yaml.safe_load(path.read_text(encoding="utf-8")))
        for cell, path in paths.items()
    }
    required = {
        LEGACY,
        OLD,
        NEW,
        LEGACY_MIRROR,
        OLD_MIRROR,
        NEW_MIRROR,
        OLD_BINDING,
        NEW_BINDING,
        "checkpoint",
        "checkpoint_load_mode",
        "policy_only_load_actor_rms",
        "auto_load_latest",
        "seed",
        "num_envs",
        "algo.trl.num_total_batches",
        "callbacks.model_save.save_frequency",
        "env.config.a2_v26_side_permutation_seed",
        "env.config.a2_v26_door_open_lr",
        "env.config.a2_v26_3_telemetry_enabled",
        "env.config.a2_stage3_unlatch_near_closed_hinge_threshold",
        "robot.control.stiffness.arm_j7",
        "robot.control.stiffness.arm_j8",
        "robot.control.damping.arm_j7",
        "robot.control.damping.arm_j8",
        "simulator.config.sim.physx.num_velocity_iterations",
    }
    source_suffix = (
        "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/"
        "V26A_LR_S1_POLICY800/model_step_002000.pt"
    )
    factor_table = {}
    for cell, table in leaves.items():
        missing = sorted(required - set(table))
        if missing:
            raise RuntimeError(f"{cell} misses required leaves: {missing}")
        seed = int(cell[-1])
        is_m1 = cell.startswith("M1")
        expected_old = 0.0 if is_m1 else 6.0
        expected_new = 6.0 if is_m1 else 0.0
        actual = (
            table[LEGACY],
            table[OLD],
            table[NEW],
            table[LEGACY_MIRROR],
            table[OLD_MIRROR],
            table[NEW_MIRROR],
            table[OLD_BINDING],
            table[NEW_BINDING],
        )
        expected = (0.0, expected_old, expected_new, 0.0, expected_old, expected_new, expected_old, expected_new)
        if actual != expected:
            raise RuntimeError(f"{cell} reward/binding tuple mismatch: {actual}")
        fixed = (
            table["checkpoint_load_mode"],
            table["policy_only_load_actor_rms"],
            table["auto_load_latest"],
            table["seed"],
            table["num_envs"],
            table["algo.trl.num_total_batches"],
            table["callbacks.model_save.save_frequency"],
            table["env.config.a2_v26_side_permutation_seed"],
            table["env.config.a2_v26_door_open_lr"],
            table["env.config.a2_v26_3_telemetry_enabled"],
            table["env.config.a2_stage3_unlatch_near_closed_hinge_threshold"],
            table["robot.control.stiffness.arm_j7"],
            table["robot.control.stiffness.arm_j8"],
            table["robot.control.damping.arm_j7"],
            table["robot.control.damping.arm_j8"],
            table["simulator.config.sim.physx.num_velocity_iterations"],
        )
        if fixed != ("policy_only", True, False, seed, 4096, 750, 125, seed, "bilateral", True, 0.1, 800.0, 800.0, 25.0, 25.0, 2):
            raise RuntimeError(f"{cell} violates fixed formal contract: {fixed}")
        if not str(table["checkpoint"]).endswith(source_suffix):
            raise RuntimeError(f"{cell} source checkpoint is not CONT_STEP2000")
        factor_table[cell] = {
            "old_scale": expected_old,
            "creation_scale": expected_new,
            "seed": seed,
            "bilateral_runtime_count": {"left": 2048, "right": 2048},
        }
    diffs = {
        "M0S0_to_M1S0": assert_exact_diff(
            "M0S0->M1S0", leaves["M0S0"], leaves["M1S0"], REWARD_LEAVES
        ),
        "M0S1_to_M1S1": assert_exact_diff(
            "M0S1->M1S1", leaves["M0S1"], leaves["M1S1"], REWARD_LEAVES
        ),
        "M0S0_to_M0S1": assert_exact_diff(
            "M0S0->M0S1", leaves["M0S0"], leaves["M0S1"], SEED_LEAVES
        ),
        "M1S0_to_M1S1": assert_exact_diff(
            "M1S0->M1S1", leaves["M1S0"], leaves["M1S1"], SEED_LEAVES
        ),
    }
    payload = {
        "schema": "a2_piper_base_v26_3_resolved_matrix_v1",
        "status": "STATIC_PASS",
        "load_contract": {
            "mode": "policy_only",
            "actor_rms_loaded": True,
            "optimizer_value_scheduler_episode_state": "FRESH",
            "source": "CONT_STEP2000",
        },
        "cells": factor_table,
        "verified_changed_leaves": diffs,
        "zero_scale_registry_contract": "zero-scale reward keys are removed before reward registry preparation",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
