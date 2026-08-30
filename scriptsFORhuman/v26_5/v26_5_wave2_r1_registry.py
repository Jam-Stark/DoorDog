#!/usr/bin/env python3
"""Emit the immutable Wave2 R1 preregistration without allocating a GPU."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "v26_5_wave2_r1_policy_residual_20260830_r2"
SOURCE = ROOT / "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"

def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite R1 registry: {args.output}")
    require(SOURCE.is_file(), f"CONT_STEP2000 source checkpoint missing: {SOURCE}")
    payload = {
        "schema": "a2_piper_base_v26_5_wave2_r1_registry_v1",
        "status": "PREREGISTERED_NOT_RUN", "run_id": RUN_ID,
        "source_checkpoint": str(SOURCE),
        "K1": {"control_selector": "wbmanip/base_v26_5_eval_O0A0", "dual_view_selector": "wbmanip/base_v26_5_wave2_R1_eval_policy_residual", "checkpoint_load_mode": "policy_only", "seeds": [0, 1], "sides": ["left", "right"], "episodes_per_side": 64, "natural_first_episode_only": True, "identity_tolerance": 1e-6, "runtime_identity_observables": ["policy_mean_raw_action", "discrete_trajectory"], "std_evidence": "static_actor_selector_loader_contract_plus_actual_load_receipt"},
        "R1": {"train_selector": "wbmanip/base_v26_5_wave2_R1_policy_residual", "eval_selector": "wbmanip/base_v26_5_wave2_R1_eval_policy_residual", "cells": [{"label": "R1_S0", "seed": 0, "physical_gpu": 2}, {"label": "R1_S1", "seed": 1, "physical_gpu": 3}], "num_envs": 4096, "batches": 250, "save_steps": [125, 250], "episodes_per_side": 64},
        "frozen": {"geometry_target": True, "actor_gauge": True, "canonicalization": False, "stage3_delta_rebase": False, "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True, "residual_mean_indices": [5, 12], "residual_stage_obs_slice": [127, 133]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)

if __name__ == "__main__":
    main()
