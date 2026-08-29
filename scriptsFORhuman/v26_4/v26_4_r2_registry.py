#!/usr/bin/env python3
"""Emit the admitted R2 four-cell command registry without starting a run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828"
SEAM_KEY = "env.config.a2_v26_4_side_canonicalization_enabled"
CELLS = (
    ("C0_CANONICAL_OFF_S0", 0, 0, False),
    ("C0_CANONICAL_OFF_S1", 1, 1, False),
    ("C1_CANONICAL_ON_S0", 2, 0, True),
    ("C1_CANONICAL_ON_S1", 3, 1, True),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"artifact must be an object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", type=Path, default=STAGE / "M/k_gate_receipt.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite R2 registry: {args.output}")
    gate = load(args.gate)
    require(gate.get("schema") == "a2_piper_base_v26_4_r2_wave_m_k_gate_v1", "R2 gate schema mismatch")
    require(gate.get("status") == "K_C_GATE_ADMITTED_READY_FOR_R2_RUNNER", "R2 K/C gate is not admitted")
    require(gate.get("k_typed_outcome") == "BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET", "R2 K outcome does not admit C0/C1")
    require(gate.get("seam_key") == SEAM_KEY, "R2 gate seam mismatch")
    train_root = ROOT / "logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main"
    eval_root = STAGE / "eval"
    commands = []
    for cell, gpu, seed, canonical in CELLS:
        stem = cell.rsplit("_S", 1)[0]
        seam = f"++{SEAM_KEY}={'true' if canonical else 'false'}"
        commands.append({
            "cell": cell, "gpu": gpu, "seed": seed, "canonicalization_enabled": canonical,
            "seam_override": seam,
            "train_command": f"scriptsFORhuman/v26_4/v26_4_r2_orchestrate_train_cell.sh {gpu} {stem} {train_root / cell} {seed} {seam}",
            "eval_command": f"scriptsFORhuman/v26_4/v26_4_r2_orchestrate_main_eval_cell.sh {gpu} {cell} {train_root / cell} {eval_root} {seed} {seam}",
            "train_receipt": f".ai/runtime/runs/v26_4_r2_main_{cell.lower()}/RUN_RECEIPT.json",
            "eval_receipt": f".ai/runtime/runs/v26_4_r2_eval_{cell.lower()}/RUN_RECEIPT.json",
        })
    payload = {
        "schema": "a2_piper_base_v26_4_r2_command_registry_v1",
        "status": "K_C_GATE_ADMITTED_READY_FOR_R2_RUNNER",
        "gate": str(args.gate.resolve()), "seam_key": SEAM_KEY,
        "source_checkpoint": str((ROOT / "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt").resolve()),
        "training_contract": {"num_envs": 4096, "batches": 750, "save_frequency": 125, "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True, "visible_physical_gpus": [0, 1, 2, 3]},
        "m1_reward_contract": {"env_handle_depression_scale": 0.0, "reward_handle_depression": 0.0, "env_handle_creation_scale": 6.0, "reward_handle_creation": 6.0, "reward_push_door_handle": 0.0},
        "evaluation_contract": {"checkpoints": [125, 250, 500, 750], "sides": ["left", "right"], "episodes_per_side": 64, "natural_first_episode_only": True, "checkpoint_load_mode": "full"},
        "cells": commands,
        "preregistered_section_7": {
            "population": "LEFT and RIGHT exact64 natural first episodes at checkpoints 125/250/500/750",
            "k5_admission_absolute_gap_max": 0.15,
            "stage3_conditional_contact_stability_absolute_gap_max": 0.05,
            "handle_highwater_left_right_ratio": [0.5, 2.0],
            "zero_rules": "0/0 undefined; one-sided zero is a high-water band failure; no epsilon",
            "seed_direction": "C1 must strictly lower C0 nonnegative asymmetry loss for each metric on seed0 and seed1",
            "not_admission": ["Stage4", "goal"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
