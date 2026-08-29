#!/usr/bin/env python3
"""Validate admitted R2 registry ownership, commands, and four-cell mapping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path) -> dict:
    require(path.is_file(), f"missing registry artifact: {path}")
    result = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(result, dict), f"registry artifact must be an object: {path}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    gate, registry = load(args.gate), load(args.registry)
    require(gate.get("status") == "K_C_GATE_ADMITTED_READY_FOR_R2_RUNNER", "K/C gate not admitted")
    require(registry.get("schema") == "a2_piper_base_v26_4_r2_command_registry_v1", "R2 registry schema mismatch")
    require(registry.get("status") == "K_C_GATE_ADMITTED_READY_FOR_R2_RUNNER", "R2 registry not admitted")
    require(registry.get("gate") == str(args.gate.resolve()), "registry gate provenance mismatch")
    contract = registry.get("training_contract")
    require(contract == {"num_envs": 4096, "batches": 750, "save_frequency": 125, "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True, "visible_physical_gpus": [0, 1, 2, 3]}, "R2 training contract mismatch")
    require(registry.get("m1_reward_contract") == {"env_handle_depression_scale": 0.0, "reward_handle_depression": 0.0, "env_handle_creation_scale": 6.0, "reward_handle_creation": 6.0, "reward_push_door_handle": 0.0}, "R2 M1 0/0/6/0 reward contract mismatch")
    cells = registry.get("cells")
    require(isinstance(cells, list) and len(cells) == 4, "R2 requires four registry cells")
    expected = [("C0_CANONICAL_OFF_S0", 0, 0, False), ("C0_CANONICAL_OFF_S1", 1, 1, False), ("C1_CANONICAL_ON_S0", 2, 0, True), ("C1_CANONICAL_ON_S1", 3, 1, True)]
    for cell, (name, gpu, seed, enabled) in zip(cells, expected, strict=True):
        require((cell.get("cell"), cell.get("gpu"), cell.get("seed"), cell.get("canonicalization_enabled")) == (name, gpu, seed, enabled), f"R2 cell mapping mismatch: {cell}")
        require(cell.get("seam_override") == f"++env.config.a2_v26_4_side_canonicalization_enabled={'true' if enabled else 'false'}", f"R2 seam mismatch: {name}")
        require(f" {gpu} " in cell.get("train_command", "") and f" {gpu} " in cell.get("eval_command", ""), f"R2 command GPU mismatch: {name}")
    print(args.registry)


if __name__ == "__main__":
    main()
