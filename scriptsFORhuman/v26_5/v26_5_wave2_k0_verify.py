#!/usr/bin/env python3
"""Verify Wave2 K0 registry and composed O0A0 selector configs before GPU allocation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


CELLS = ("K0_CONT_STEP2000_O0A0_S0", "K0_CONT_STEP2000_O0A0_S1")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
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
    require(registry.get("schema") == "a2_piper_base_v26_5_wave2_k0_registry_v1", "Wave2 K0 registry schema mismatch")
    require(registry.get("status") == "PREREGISTERED_NOT_RUN", "Wave2 K0 registry must remain preregistered")
    source = registry.get("source_control")
    require(isinstance(source, dict) and source.get("checkpoint_load_mode") == "full", "K0 must be full-load")
    require(source.get("factor") == "O0A0" and source.get("num_envs") == 64 and source.get("episodes_per_side") == 64, "K0 source-control contract mismatch")
    require(source.get("natural_first_episode_only") is True and source.get("enable_staged_reset") is False, "K0 natural-first contract mismatch")
    require(registry.get("dual_view_identity", {}).get("status") == "NOT_RUN", "K0 must not claim a dual-view identity")
    paths: dict[str, Path] = {}
    for entry in args.config:
        label, separator, raw = entry.partition("=")
        require(separator and label in CELLS and label not in paths, "configs must uniquely name every K0 cell")
        paths[label] = Path(raw)
    require(set(paths) == set(CELLS), "exactly two K0 composed configs are required")
    for label, path in paths.items():
        table = flatten(yaml.safe_load(path.read_text(encoding="utf-8")))
        seed = int(label[-1])
        expected = {
            "seed": seed,
            "env.config.a2_v26_side_permutation_seed": seed,
            "checkpoint": None,
            "checkpoint_load_mode": "policy_only",
            "auto_load_latest": False,
            "num_envs": 64,
            "algo.config.eval.num_eval_episodes": 64,
            "algo.config.eval.eval_num_envs_episodes": True,
            "env.config.enable_staged_reset": False,
            "env.config.a2_v26_4_side_canonicalization_enabled": False,
            "env.config.a2_v26_5_geometry_target_enabled": False,
            "env.config.a2_v26_5_stage3_delta_rebase_enabled": False,
        }
        for key, value in expected.items():
            require(table.get(key) == value, f"{label} violates K0 selector field {key}: {table.get(key)!r}")
    print(args.registry)


if __name__ == "__main__":
    main()
