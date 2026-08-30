#!/usr/bin/env python3
"""Emit the preregistered Wave2 K0 source-control registry without running it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "v26_5_wave2_k0_identity_20260830_r2"
SOURCE = ROOT / "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
STAGE = ROOT / "logs_eval/base_v26" / RUN_ID

CELLS = (
    ("K0_CONT_STEP2000_O0A0_S0", 0, 0),
    ("K0_CONT_STEP2000_O0A0_S1", 1, 1),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite Wave2 K0 registry: {args.output}")
    require(SOURCE.is_file(), f"CONT_STEP2000 source checkpoint is missing: {SOURCE}")
    cells = [
        {
            "label": label,
            "seed": seed,
            "physical_gpu": gpu,
            "checkpoint": str(SOURCE),
            "checkpoint_load_mode": "full",
            "eval_selector": "wbmanip/base_v26_5_wave2_K0_eval_O0A0",
            "output": str(STAGE / "eval" / label),
            "receipt": f".ai/runtime/runs/{RUN_ID}_eval_s{seed}/RUN_RECEIPT.json",
        }
        for label, seed, gpu in CELLS
    ]
    payload = {
        "schema": "a2_piper_base_v26_5_wave2_k0_registry_v1",
        "status": "PREREGISTERED_NOT_RUN",
        "run_id": RUN_ID,
        "question": "Does unchanged CONT_STEP2000 satisfy bilateral natural-start acquisition vitals under the Wave2 evaluator?",
        "source_control": {
            "checkpoint": str(SOURCE),
            "checkpoint_load_mode": "full",
            "auto_load_latest": False,
            "factor": "O0A0",
            "canonicalization": False,
            "geometry_target": False,
            "stage3_delta_rebase": False,
            "num_envs": 64,
            "episodes_per_side": 64,
            "natural_first_episode_only": True,
            "enable_staged_reset": False,
            "sides": ["left", "right"],
            "seeds": [0, 1],
        },
        "cells": cells,
        "admission_gate": {
            "per_stratum": {
                "Stage3_admission_count_min": 16,
                "K5_episode_count_min": 16,
                "contact_stability_rate_min": 0.90,
                "integrity_violations": 0,
            },
            "all_four_seed_by_side_strata_required": True,
            "stage4_stage5_goal": "reported_only",
        },
        "dual_view_identity": {
            "status": "NOT_RUN",
            "reason": "K0 is an O0A0 source control and defines no dual-view actor implementation or view mapping.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
