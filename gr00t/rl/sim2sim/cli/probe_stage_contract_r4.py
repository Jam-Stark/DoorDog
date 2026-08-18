#!/usr/bin/env python3
"""Scripted approach proof for STAGE_CONTRACT_MINIMAL."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import torch

from gr00t.rl.sim2sim.mujoco.stage_contract_minimal import (
    STAGE_ACTION_BRANCH_AUDIT,
    STAGE_CONTRACT_NAME,
    Stage0ObservableState,
    StageContractMinimal,
)


def _state(*, root_x: float, base_x: float) -> Stage0ObservableState:
    return Stage0ObservableState(
        root_position_m=torch.tensor([[root_x, 0.0, 0.55]], dtype=torch.float32),
        grasp_target_position_m=torch.tensor([[1.0, 0.0, 0.9]], dtype=torch.float32),
        arm_position_rad=torch.zeros((1, 6), dtype=torch.float32),
        arm_default_position_rad=torch.zeros((1, 6), dtype=torch.float32),
        physical_base_command=torch.tensor([[base_x, 0.0, 0.0, 0.0, 0.0]], dtype=torch.float32),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tracker = StageContractMinimal()
    raw = torch.zeros((1, 12), dtype=torch.float32)
    raw[:, 5:11] = 1.0
    rows = []

    action = tracker.apply_high_level_action(raw)
    advanced = tracker.observe_after_step(_state(root_x=0.1, base_x=0.0))
    rows.append({
        "label": "BEFORE_STAGING_BAND",
        "stage_used": action.stage_used_for_action,
        "advanced_after_step": advanced,
        "effective_arm_delta": action.accumulated_arm_delta.squeeze(0).tolist(),
        "raw_arm_delta_echo": action.raw_arm_delta_echo.squeeze(0).tolist(),
    })

    action = tracker.apply_high_level_action(raw)
    advanced = tracker.observe_after_step(_state(root_x=0.4, base_x=0.2))
    rows.append({
        "label": "IN_BAND_BASE_NOT_STILL",
        "stage_used": action.stage_used_for_action,
        "advanced_after_step": advanced,
        "effective_arm_delta": action.accumulated_arm_delta.squeeze(0).tolist(),
    })

    action = tracker.apply_high_level_action(raw)
    advanced = tracker.observe_after_step(_state(root_x=0.4, base_x=0.1))
    rows.append({
        "label": "IN_BAND_BASE_STILL_ADVANCE_AFTER_ACTION",
        "stage_used": action.stage_used_for_action,
        "advanced_after_step": advanced,
        "stage_after_observation": tracker.stage,
        "effective_arm_delta": action.accumulated_arm_delta.squeeze(0).tolist(),
    })

    post = tracker.apply_high_level_action(raw)
    rows.append({
        "label": "FIRST_STAGE1_ACTION",
        "stage_used": post.stage_used_for_action,
        "effective_arm_delta": post.accumulated_arm_delta.squeeze(0).tolist(),
        "hit_delta_clip": bool(torch.any(torch.abs(post.accumulated_arm_delta) >= 15.0)),
        "gripper_positive_target": tracker.gripper_target(torch.ones((1, 1))).squeeze(0).tolist(),
        "gripper_zero_target": tracker.gripper_target(torch.zeros((1, 1))).squeeze(0).tolist(),
    })

    passed = (
        rows[0]["effective_arm_delta"] == [0.0] * 6
        and rows[0]["raw_arm_delta_echo"] == [1.0] * 6
        and rows[1]["advanced_after_step"] is False
        and rows[2]["advanced_after_step"] is True
        and rows[2]["effective_arm_delta"] == [0.0] * 6
        and rows[3]["stage_used"] == 1
        and rows[3]["hit_delta_clip"] is False
    )
    if not passed:
        raise RuntimeError("STAGE_CONTRACT_MINIMAL scripted approach proof failed")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "schema": "doordog.sim2sim.stage_contract_minimal_probe.v1",
        "result": "PASS",
        "contract": STAGE_CONTRACT_NAME,
        "production_sources": {
            "delta_gate": "gr00t/rl/envs/door/door_open_a2_base.py:_apply_delta_action_overrides",
            "delta_accumulator": "gr00t/rl/envs/base_task/delta_action_base.py:DeltaActionBase.step",
            "stage0_advance": "gr00t/rl/envs/door/door_open_a2_base.py:_stage_0_to_1_advance_condition",
            "transition_order": "gr00t/rl/envs/base_task/staged_task_base.py:_post_compute_observations_callback",
            "gripper_primitive": "gr00t/rl/envs/base_task/a2_base.py:_step_a2_base",
            "resolved_config": "scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10_ready_r2/config_snapshot.yaml",
        },
        "exact_thresholds": {
            "staging_x_min_m": 0.5,
            "staging_x_max_m": 0.8,
            "staging_y_tolerance_m_strict": 0.15,
            "arm_default_max_deviation_rad_strict": 0.1,
            "base_still_norm_max_inclusive": 0.1,
            "arm_delta_scale": 0.3,
            "arm_delta_clip": 15.0,
        },
        "scripted_approach": rows,
        "stage_action_branch_audit": STAGE_ACTION_BRANCH_AUDIT,
        "producer_identity": {
            "git_commit_before_phase_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/probe_stage_contract_r4.py",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "contract": STAGE_CONTRACT_NAME}, sort_keys=True))


if __name__ == "__main__":
    main()
