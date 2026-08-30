#!/usr/bin/env python3
"""Emit the immutable Wave2 R1 preregistration without allocating a GPU."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "v26_5_wave2_r1_policy_residual_20260830_r12"
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
        "K1": {"control_selector": "wbmanip/base_v26_5_eval_O0A0", "dual_view_selector": "wbmanip/base_v26_5_wave2_R1_eval_policy_residual", "checkpoint_load_mode": "policy_only", "runtime_load_contract": {"control": {"checkpoint_load_mode": "policy_only", "a2_v23_p06_policy_only": False, "a2_v26_5_policy_only_identity_control": True, "a2_v26_5_policy_only_residual": False, "actor_keyset_contract": "legacy_identity_control_exact", "actor_strict": True}, "dual": {"checkpoint_load_mode": "policy_only", "a2_v23_p06_policy_only": False, "a2_v26_5_policy_only_identity_control": False, "a2_v26_5_policy_only_residual": True, "actor_keyset_contract": "legacy_exact_without_residual", "actor_strict": False}, "receipt_schema": "a2_piper_base_v26_5_runtime_load_receipt_v1", "required_artifacts": ["a2_v26_5_runtime_load_receipt.json", "a2_eval_diagnostic_metadata.json"], "metadata_reward_terms": ["push_door_handle", "a2_stage3_unlatch_hold", "push_door_hinge", "a2_stage3_stage4_hold_and_drive"]}, "pre_k1_wiring_gate": {"view": "dual", "seed": 0, "side": "right", "physical_gpu": 4, "num_envs": 64, "max_episode_length_s": 0.02, "control_ticks": 2, "required_artifacts": ["a2_v26_5_runtime_load_receipt.json", "a2_eval_diagnostic_metadata.json", "a2_v14_per_env_records.json", "metrics_eval.json"]}, "cells": [{"label": "K1_S0", "seed": 0, "physical_gpu": 4}, {"label": "K1_S1", "seed": 1, "physical_gpu": 5}], "sides": ["left", "right"], "episodes_per_side": 64, "natural_first_episode_only": True, "identity_tolerance": 1e-6, "runtime_identity_observables": ["policy_mean_raw_action", "discrete_trajectory"], "std_evidence": "static_actor_selector_loader_contract_plus_actual_load_receipt", "view_trace_contract": {"control": {"terms": ["push_door_handle", "a2_stage3_unlatch_hold", "push_door_hinge", "a2_stage3_stage4_hold_and_drive"], "a2_v26_2_handle_depression_scale": 0.0, "a2_v26_3_handle_creation_scale": 0.0}, "dual": {"terms": ["push_door_handle", "a2_stage3_unlatch_hold", "push_door_hinge", "a2_stage3_stage4_hold_and_drive"], "a2_v26_2_handle_depression_scale": 0.0, "a2_v26_3_handle_creation_scale": 0.0}}},
        "R1": {"train_selector": "wbmanip/base_v26_5_wave2_R1_policy_residual", "eval_selector": "wbmanip/base_v26_5_wave2_R1_eval_policy_residual", "main_geometry_target_enabled": False, "dual_input_contract": {"base_input_key": "actor_obs", "residual_input_key": "residual_actor_obs", "base_pose_term": "gripper_handle_transform", "residual_pose_term": "gripper_handle_transform_gauge", "width": 133, "residual_action_slice": [5, 12]}, "actor_hydra_listconfig_contract": {"selector_value": [127, 133], "validator_sequence_type": "collections.abc.Sequence", "forbidden_sequence_types": ["str", "bytes"], "required_length": 2, "required_element_type": "int"}, "static_eval_compose": {"ablation_partial": "R1_eval_ablation_partial.yaml", "host_entrypoint": "gr00t.rl.eval_agent_trl", "host_hydra_config_path": str(SOURCE.parent), "host_hydra_config_name": "config", "host_resolve_args": ["--cfg", "job", "--resolve"], "runtime_merge": "OmegaConf.merge(train_config, override_config)", "checkpoint_load_mode": "policy_only"}, "cells": [{"label": "R1_S0", "seed": 0, "physical_gpu": 4}, {"label": "R1_S1", "seed": 1, "physical_gpu": 5}], "num_envs": 4096, "batches": 250, "save_steps": [125, 250], "episodes_per_side": 64},
        "frozen": {"geometry_target": False, "actor_gauge": True, "canonicalization": False, "stage3_delta_rebase": False, "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True, "residual_mean_indices": [5, 12], "residual_stage_obs_slice": [127, 133]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)

if __name__ == "__main__":
    main()
