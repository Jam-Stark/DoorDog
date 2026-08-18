#!/usr/bin/env python3
"""Scripted full-path probe and receipt for the r5 action warp."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import torch

from gr00t.rl.sim2sim.mujoco.action_warp_r5 import (
    ACTION_WARP_AUDIT_R5,
    FullActionWarpR5,
    ResolvedActionWarpContractR5,
)
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.stage_contract_minimal import (
    Stage0ObservableState,
    StageContractMinimal,
)
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    contract = ResolvedActionWarpContractR5.from_config(args.resolved_config)
    robot = resolved_a2_piper_contract()
    joint_map = A2PiperJointMap.from_sim_joint_names(robot.sim_joint_names, device="cpu")
    tracker = StageContractMinimal(
        dtype=torch.float32,
        device="cpu",
        delta_scale=contract.delta_action_scale,
        delta_clip=contract.delta_action_clip,
    )
    warp = FullActionWarpR5(contract=contract, joint_map=joint_map, stage_tracker=tracker)
    default = torch.tensor(robot.default_dof_pos, dtype=torch.float32).unsqueeze(0)
    raw = torch.tensor(
        [[4.0, -4.0, 4.0, 2.0, -2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]],
        dtype=torch.float32,
    )
    legs = torch.tensor(
        [[150.0, -150.0] * 6], dtype=torch.float32
    )
    stage0 = warp.apply(
        raw_high_level_action=raw,
        policy_leg_action=legs,
        default_dof_pos=default,
    )
    expected_physical = torch.tensor(
        [[0.5, -0.5, 0.5, 0.4, -0.4]], dtype=torch.float32
    )
    if not torch.equal(stage0.base.physical, expected_physical):
        raise RuntimeError("raw scripted base action did not reach the resolved physical caps")
    if not torch.equal(stage0.stage_action.accumulated_arm_delta, torch.zeros((1, 6))):
        raise RuntimeError("stage0 arm hold failed")
    if int(stage0.simulator_action_clipped.sum()) != 12:
        raise RuntimeError("scripted final 20D action clip did not clip all twelve leg actions")
    still_raw = torch.tensor(
        [[0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0]],
        dtype=torch.float32,
    )
    still = warp.apply(
        raw_high_level_action=still_raw,
        policy_leg_action=torch.zeros((1, 12)),
        default_dof_pos=default,
    )
    advanced = tracker.observe_after_step(
        Stage0ObservableState(
            root_position_m=torch.tensor([[0.3, 0.0, 0.5]], dtype=torch.float32),
            grasp_target_position_m=torch.tensor([[1.0, 0.0, 1.0]], dtype=torch.float32),
            arm_position_rad=default[:, 12:18].clone(),
            arm_default_position_rad=default[:, 12:18].clone(),
            physical_base_command=still.base.physical,
        )
    )
    if not advanced:
        raise RuntimeError("full-warp staging probe did not advance after a clipped-zero command")
    stage1 = warp.apply(
        raw_high_level_action=still_raw,
        policy_leg_action=torch.zeros((1, 12)),
        default_dof_pos=default,
    )
    expected_arm = torch.full((1, 6), contract.delta_action_scale)
    if not torch.allclose(stage1.stage_action.accumulated_arm_delta, expected_arm):
        raise RuntimeError("first stage1 arm delta does not match resolved scale")
    if any(item["status"] not in {
        "MATCH",
        "MATCH_DISABLED",
        "MATCH_WITH_D5_DECLARED_NATIVE_ACTUATOR_DEVIATION",
    } for item in ACTION_WARP_AUDIT_R5):
        raise RuntimeError("action warp audit contains an unresolved node")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "schema": "doordog.sim2sim.action_warp_contract.r5.v1",
        "result": "PASS",
        "coverage": "NONE_MISSING",
        "resolved_config": contract.config_path,
        "resolved_values": {
            "base_command_scale": contract.base_command_scale,
            "body_pitch_roll_scale": contract.body_pitch_roll_scale,
            "base_clip_low": list(contract.base_low),
            "base_clip_high": list(contract.base_high),
            "command_obs_multipliers": list(contract.command_obs_multipliers),
            "command_deadband_norm": contract.command_deadband_norm,
            "delta_action_scale": contract.delta_action_scale,
            "delta_action_clip": contract.delta_action_clip,
            "robot_action_scale": contract.robot_action_scale,
            "robot_action_clip": contract.robot_action_clip,
        },
        "transform_chain": ACTION_WARP_AUDIT_R5,
        "scripted_full_path": {
            "input_is_raw_high_level_action": True,
            "raw_base": raw[0, :5].tolist(),
            "scaled_unclipped": stage0.base.scaled_unclipped.squeeze(0).tolist(),
            "pre_final_clip": stage0.base.pre_final_clip.squeeze(0).tolist(),
            "physical_clipped": stage0.base.physical.squeeze(0).tolist(),
            "axis_clipped": stage0.base.axis_clipped.squeeze(0).tolist(),
            "axis_at_cap": stage0.base.axis_at_cap.squeeze(0).tolist(),
            "observation_echo": warp.observation_command_echo(
                stage0.base.physical
            ).squeeze(0).tolist(),
            "stage0_effective_arm": stage0.stage_action.accumulated_arm_delta.squeeze(0).tolist(),
            "final_20d_clip_count": int(stage0.simulator_action_clipped.sum()),
            "staging_zero_physical_command": still.base.physical.squeeze(0).tolist(),
            "advanced_after_zero_command": advanced,
            "first_stage1_effective_arm": stage1.stage_action.accumulated_arm_delta.squeeze(0).tolist(),
        },
        "producer_identity": {
            "git_commit_before_phase_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/probe_action_warp_r5.py",
        },
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": receipt["result"], "coverage": receipt["coverage"]}))


if __name__ == "__main__":
    main()
