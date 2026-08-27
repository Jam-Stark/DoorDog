#!/usr/bin/env python3
"""Verify the registered C/A/R/W resolved-config factor seams."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", action="append", required=True, metavar="CELL=PATH")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        leaves: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise RuntimeError(f"resolved config has non-string key at {prefix!r}")
            leaves.update(flatten(child, f"{prefix}.{key}" if prefix else key))
        return leaves
    return {prefix: value}


IDENTITY = frozenset({"v26_cell", "v26_phase", "experiment_name", "experiment_dir", "output_dir", "env.config.experiment_name", "callbacks.autoresume.save_dir", "callbacks.model_save.save_dir", "save_dir", "wandb.wandb_dir"})
RAW = "rewards.reward_scales.push_door_handle"
GATED = "rewards.reward_scales.a2_stage3_handle_depression"
RAW_MIRROR = "env.config.rewards.reward_scales.push_door_handle"
GATED_MIRROR = "env.config.rewards.reward_scales.a2_stage3_handle_depression"
GATED_BINDING = "env.config.a2_v26_2_handle_depression_scale"
THRESHOLD = "env.config.a2_stage3_unlatch_near_closed_hinge_threshold"


def diff(left: dict[str, Any], right: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    keys = set(left) | set(right)
    return {key: (left.get(key), right.get(key)) for key in sorted(keys) if left.get(key) != right.get(key)}


def verify_pair(name: str, observed: dict[str, tuple[Any, Any]], allowed: set[str]) -> list[str]:
    unexpected = sorted(set(observed) - IDENTITY - allowed)
    missing = sorted(allowed - set(observed))
    if unexpected or missing:
        raise RuntimeError(f"{name} resolved leaf diff violates the registered seam; unexpected={unexpected}, missing={missing}")
    return sorted(observed)


def main() -> None:
    args = parse_args()
    paths = {}
    for raw in args.config:
        cell, separator, filename = raw.partition("=")
        if not separator or cell not in {"C", "A", "R", "W"} or cell in paths:
            raise ValueError("--config must provide each unique C/A/R/W as CELL=PATH")
        paths[cell] = Path(filename)
    if set(paths) != {"C", "A", "R", "W"}:
        raise RuntimeError("resolved matrix needs exactly C, A, R, W configs")
    configs = {cell: yaml.safe_load(path.read_text(encoding="utf-8")) for cell, path in paths.items()}
    leaves = {cell: flatten(config) for cell, config in configs.items()}
    required = (RAW, GATED, RAW_MIRROR, GATED_MIRROR, GATED_BINDING, THRESHOLD, "checkpoint_load_mode", "policy_only_load_actor_rms", "seed", "num_envs", "algo.trl.num_total_batches", "callbacks.model_save.save_frequency", "env.config.a2_v26_side_permutation_seed", *IDENTITY)
    for cell, table in leaves.items():
        missing = [path for path in required if path not in table]
        if missing:
            raise RuntimeError(f"{cell} resolved config misses required leaves: {missing}")
    expected = {"C": (6, 0, 0.1), "A": (0, 0, 0.1), "R": (0, 6, 0.1), "W": (0, 6, 0.25)}
    for cell, (raw, depression, threshold) in expected.items():
        actual = leaves[cell]
        if (actual[RAW], actual[GATED], actual[RAW_MIRROR], actual[GATED_MIRROR], actual[THRESHOLD]) != (raw, depression, raw, depression, threshold) or actual[GATED_BINDING] != depression:
            raise RuntimeError(f"{cell} factor/binding tuple is not registered")
        if (actual["checkpoint_load_mode"], actual["policy_only_load_actor_rms"], actual["seed"], actual["num_envs"], actual["algo.trl.num_total_batches"], actual["callbacks.model_save.save_frequency"], actual["env.config.a2_v26_side_permutation_seed"]) != ("policy_only", True, 1, 4096, 750, 250, 1):
            raise RuntimeError(f"{cell} does not have the frozen Wave1 continuation contract")
    pair_diffs = {"A_to_R": diff(leaves["A"], leaves["R"]), "R_to_W": diff(leaves["R"], leaves["W"]), "C_to_R": diff(leaves["C"], leaves["R"])}
    verified = {"A_to_R": verify_pair("A→R", pair_diffs["A_to_R"], {GATED, GATED_MIRROR, GATED_BINDING}), "R_to_W": verify_pair("R→W", pair_diffs["R_to_W"], {THRESHOLD}), "C_to_R": verify_pair("C↔R", pair_diffs["C_to_R"], {RAW, RAW_MIRROR, GATED, GATED_MIRROR, GATED_BINDING})}
    payload = {"schema": "a2_piper_base_v26_2_resolved_matrix_v3", "required_leaves": list(required), "pairwise_changed_leaves": verified, "causal_diffs": {"A_to_R": [GATED, GATED_MIRROR, GATED_BINDING], "R_to_W": [THRESHOLD], "C_to_R": [RAW, RAW_MIRROR, GATED, GATED_MIRROR, GATED_BINDING], "A_to_W": "NOT_SINGLE_FACTOR"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
