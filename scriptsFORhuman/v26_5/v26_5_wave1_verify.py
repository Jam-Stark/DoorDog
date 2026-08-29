#!/usr/bin/env python3
"""Verify Wave1 registry and resolved O-by-A configs before GPU allocation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


CELLS = ("O1A0_S0", "O1A0_S1", "O1A1_S0", "O1A1_S1")
IDENTITY = {
    "v26_cell", "v26_phase", "v26_schema", "v26_5_plan_id",
    "timestamp", "experiment_dir", "output_dir", "save_dir",
    "callbacks.autoresume.save_dir", "callbacks.model_save.save_dir",
    "wandb.wandb_dir", "experiment_name", "project_name",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            require(isinstance(key, str), f"non-string config key below {prefix}")
            result.update(flatten(child, f"{prefix}.{key}" if prefix else key))
        return result
    return {prefix: value}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--config", action="append", required=True, metavar="CELL=PATH")
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    require(registry.get("schema") == "a2_piper_base_v26_5_wave1_registry_v1", "Wave1 registry schema mismatch")
    require(registry.get("status") == "PREREGISTERED_NOT_RUN", "Wave1 registry must remain preregistered")
    contract = registry.get("formal_training_contract")
    require(isinstance(contract, dict), "formal training contract missing")
    require(contract == {
        "cells": "O1A0/O1A1 x seed0/1", "physical_gpus": [0, 1, 2, 3], "num_envs": 4096,
        "batches": 750, "save_frequency": 125, "source": "CONT_STEP2000",
        "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True,
        "canonicalization": False, "reward_physics_rms": "frozen from v26-4 C0",
    }, "formal training contract mismatch")
    paths: dict[str, Path] = {}
    for entry in args.config:
        cell, separator, raw = entry.partition("=")
        require(separator and cell in CELLS and cell not in paths, "configs must uniquely name every Wave1 cell")
        paths[cell] = Path(raw)
    require(set(paths) == set(CELLS), "exactly four Wave1 resolved configs are required")
    tables = {cell: flatten(yaml.safe_load(path.read_text(encoding="utf-8"))) for cell, path in paths.items()}
    frozen = {
        "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True, "auto_load_latest": False,
        "num_envs": 4096, "algo.trl.num_total_batches": 750, "callbacks.model_save.save_frequency": 125,
        "env.config.a2_v26_door_open_lr": "bilateral", "env.config.a2_v26_4_side_canonicalization_enabled": False,
        "env.config.a2_v26_2_telemetry_enabled": True, "env.config.a2_v26_3_telemetry_enabled": True,
        "env.config.a2_v26_2_handle_depression_scale": 0.0, "env.config.a2_v26_3_handle_creation_scale": 6.0,
        "rewards.reward_scales.push_door_handle": 0.0, "rewards.reward_scales.a2_stage3_handle_depression": 0.0,
        "rewards.reward_scales.a2_stage3_handle_creation": 6.0,
    }
    for cell, table in tables.items():
        for key, expected in frozen.items():
            require(table.get(key) == expected, f"{cell} violates frozen field {key}: {table.get(key)!r}")
        seed = int(cell[-1])
        require(table.get("seed") == seed and table.get("env.config.a2_v26_side_permutation_seed") == seed, f"{cell} seed contract mismatch")
        require(table.get("env.config.a2_v26_5_geometry_target_enabled") is True, f"{cell} must enable O1 geometry target")
        require(table.get("env.config.a2_v26_5_stage3_delta_rebase_enabled") is cell.startswith("O1A1"), f"{cell} A factor mismatch")
        source = table.get("checkpoint")
        require(isinstance(source, str) and source.endswith("continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"), f"{cell} source checkpoint mismatch")
    def changed(left: str, right: str) -> list[str]:
        return sorted(key for key in set(tables[left]) | set(tables[right]) if tables[left].get(key) != tables[right].get(key) and key not in IDENTITY)
    expected_seed = ["env.config.a2_v26_side_permutation_seed", "seed"]
    require(changed("O1A0_S0", "O1A0_S1") == expected_seed, "O1A0 seed pair differs beyond seed")
    require(changed("O1A1_S0", "O1A1_S1") == expected_seed, "O1A1 seed pair differs beyond seed")
    expected_factor = ["env.config.a2_v26_5_stage3_delta_rebase_enabled"]
    require(changed("O1A0_S0", "O1A1_S0") == expected_factor, "O1 A comparison differs beyond rebase factor")
    print(args.registry)


if __name__ == "__main__":
    main()
