#!/usr/bin/env python3
"""Emit the preregistered v26-5 O-by-A Wave1 command registry without running it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "v26_5_wave1_stage5_20260830_r1"
TRAIN_ROOT = ROOT / f"logs_rl/by_batch/base_v26/{RUN_ID}/formal"
EVAL_ROOT = ROOT / f"logs_eval/base_v26/{RUN_ID}/eval"
R2_TRAIN_ROOT = ROOT / "logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main"
SOURCE = ROOT / "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"

FORMAL = (
    ("O1A0_S0", "O1A0", 0, 2, "wbmanip/base_v26_5_O1A0_geometry", "wbmanip/base_v26_5_eval_O1A0"),
    ("O1A0_S1", "O1A0", 1, 4, "wbmanip/base_v26_5_O1A0_geometry", "wbmanip/base_v26_5_eval_O1A0"),
    ("O1A1_S0", "O1A1", 0, 5, "wbmanip/base_v26_5_O1A1_geometry_rebase", "wbmanip/base_v26_5_eval_O1A1"),
    ("O1A1_S1", "O1A1", 1, 6, "wbmanip/base_v26_5_O1A1_geometry_rebase", "wbmanip/base_v26_5_eval_O1A1"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite Wave1 registry: {args.output}")
    cells = []
    for label, factor, seed, gpu, ablation, selector in FORMAL:
        cells.append(
            {
                "label": label,
                "factor": factor,
                "seed": seed,
                "gpu": gpu,
                "training_ablation": ablation,
                "eval_selector": selector,
                "train_root": str(TRAIN_ROOT / label),
                "checkpoint_step750": str(TRAIN_ROOT / label / "model_step_000750.pt"),
                "eval_root": str(EVAL_ROOT),
                "train_receipt": f".ai/runtime/runs/v26_5_wave1_r1_train_{label.lower()}/RUN_RECEIPT.json",
                "eval_receipt": f".ai/runtime/runs/v26_5_wave1_r1_eval_{label.lower()}/RUN_RECEIPT.json",
            }
        )
    diagnostics = []
    for seed in (0, 1):
        checkpoint = R2_TRAIN_ROOT / f"C0_CANONICAL_OFF_S{seed}/model_step_000750.pt"
        for side in ("left", "right"):
            diagnostics.append(
                {
                    "label": f"O0A1_DIAG_R2_C0_S{seed}_STEP0750",
                    "seed": seed,
                    "side": side,
                    "gpu": 7,
                    "execution": "serial_in_one_GPU7_supervisor_receipt",
                    "checkpoint": str(checkpoint),
                    "selector": "wbmanip/base_v26_5_eval_O0A1",
                    "output": str(EVAL_ROOT / "diagnostic" / f"O0A1_DIAG_R2_C0_S{seed}_STEP0750" / side),
                    "supervisor_receipt": ".ai/runtime/runs/v26_5_wave1_r1_diagnostic_gpu7/RUN_RECEIPT.json",
                }
            )
    payload = {
        "schema": "a2_piper_base_v26_5_wave1_registry_v1",
        "status": "PREREGISTERED_NOT_RUN",
        "run_id": RUN_ID,
        "source_checkpoint": str(SOURCE),
        "formal_training_contract": {
            "cells": "O1A0/O1A1 x seed0/1",
            "physical_gpus": [2, 4, 5, 6],
            "num_envs": 4096,
            "batches": 750,
            "save_frequency": 125,
            "source": "CONT_STEP2000",
            "checkpoint_load_mode": "policy_only",
            "policy_only_load_actor_rms": True,
            "canonicalization": False,
            "reward_physics_rms": "frozen from v26-4 C0",
        },
        "runtime_smoke_contract": {
            "factor": "O1A1",
            "physical_gpu": 2,
            "num_envs": 64,
            "batches": 1,
            "save_frequency": 1,
            "source": "CONT_STEP2000",
            "checkpoint_load_mode": "policy_only",
            "policy_only_load_actor_rms": True,
            "required_checkpoint": "model_step_000001.pt",
        },
        "diagnostic_contract": {
            "matched_prefix_not_snapshot_clone": True,
            "R2_checkpoints": "C0 canonical-off seed0/1 step750",
            "factor": "O0A1 only; active rebase is an eval-time diagnostic intervention",
            "physical_gpus": [7],
            "execution": "four exact64 side lanes serially in one GPU7 tmux receipt",
            "episodes_per_side": 64,
            "sides": ["left", "right"],
        },
        "formal_cells": cells,
        "diagnostic_lanes": diagnostics,
        "formal_eval_contract": {
            "checkpoint": 750,
            "episodes_per_side": 64,
            "sides": ["left", "right"],
            "natural_first_episode_only": True,
            "trace_filename": "stage2_5_step_trace.json",
        },
        "reducer_contract": {
            "required": [
                "exact_episode_count",
                "K5",
                "contact_stability",
                "handle_highwater",
                "handle_ge_0_1_and_current_K5_for_5_controls_rate_and_TTE",
                "hinge_ge_0_1_and_0_25",
                "stage4_stage5_goal",
            ],
            "promotion": "requires policy-generated Stage4 or later on both natural sides in each O1 seed; contact alone cannot promote",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
