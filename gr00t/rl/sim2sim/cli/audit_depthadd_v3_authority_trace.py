#!/usr/bin/env python3
"""Offline Gate1/Gate3 audit against one successful DepthADD authority trace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml

from gr00t.rl.sim2sim.mujoco.action_warp_r5 import (
    FullActionWarpR5,
    ResolvedActionWarpContractR5,
)
from gr00t.rl.sim2sim.mujoco.depthadd_stage import (
    DepthAddStageObservation,
    DepthAddStageTracker,
)
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap


def _load_rows(paths: tuple[Path, Path], *, env_id: int, episode_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
        rows.extend(
            row
            for row in payload
            if int(row.get("env_id", -1)) == env_id
            and int(row.get("episode_index", -1)) == episode_index
        )
    rows.sort(key=lambda row: int(row["step_index"]))
    steps = [int(row["step_index"]) for row in rows]
    if not rows or steps != list(range(steps[0], steps[0] + len(steps))):
        raise RuntimeError("authority trace rows must form one non-empty contiguous control prefix")
    return rows


def _tensor(value: Any, width: int) -> torch.Tensor:
    result = torch.tensor([value], dtype=torch.float32)
    if tuple(result.shape) != (1, width) or not torch.all(torch.isfinite(result)):
        raise ValueError(f"authority value must be finite with shape (1, {width})")
    return result


def _contact_source(row: Mapping[str, Any]) -> list[list[float]]:
    history = row.get("stage2_completion_contact_force_source_history")
    if history is not None:
        return history[0]
    return row["contact_force_arm_body7_8_w"]


def _observation(
    row: Mapping[str, Any], *, arm_default: torch.Tensor, gripper_open: tuple[float, float]
) -> DepthAddStageObservation:
    root_world = _tensor(row["root_pos_w"], 3)
    root_relative = _tensor(row["root_pos_rel"], 3)
    staging = row.get("stage0_staging")
    grasp_world = (
        _tensor(staging["grasp_target_pos_w"], 3)
        if isinstance(staging, Mapping)
        else root_world.clone()
    )
    return DepthAddStageObservation(
        root_position_m=root_world,
        env_origin_m=root_world - root_relative,
        grasp_target_position_m=grasp_world,
        arm_position_rad=_tensor(row["arm_joint_pos"], 6),
        arm_default_position_rad=arm_default,
        physical_base_command=_tensor(row["physical_base_command"], 5),
        tcp_pregrasp_distance_m=torch.tensor(
            [row["target_pos_source_pregrasp_distance"]], dtype=torch.float32
        ),
        opening_alignment=torch.tensor([row["pregrasp_opening_alignment"]], dtype=torch.float32),
        approach_alignment=torch.tensor([row["pregrasp_approach_alignment"]], dtype=torch.float32),
        gripper_position_rad=_tensor(row["gripper_joint_pos"], 2),
        gripper_close_target_rad=_tensor(row["arm_j7_j8_close_target"], 2),
        gripper_open_target_rad=_tensor(gripper_open, 2),
        gripper_handle_forces_source_n=torch.tensor(
            [_contact_source(row)], dtype=torch.float32
        ),
        door_hinge_rad=torch.tensor([row["door_hinge_joint_pos"]], dtype=torch.float32),
        handle_hinge_rad=torch.tensor([row["door_handle_joint_pos"]], dtype=torch.float32),
    )


def _expected_post_stage(rows: list[dict[str, Any]], index: int) -> int:
    row = rows[index]
    if "post_stage" in row:
        return int(row["post_stage"])
    if index + 1 < len(rows):
        return int(rows[index + 1]["stage_buf"])
    return int(row["stage_buf"])


def run(args: argparse.Namespace) -> None:
    rows = _load_rows(
        (args.stage0_1_trace, args.stage2_5_trace),
        env_id=args.env_id,
        episode_index=args.episode_index,
    )
    runtime = ResolvedActionWarpContractR5.from_config(args.resolved_config)
    runtime_config = yaml.safe_load(
        args.resolved_config.resolve(strict=True).read_text(encoding="utf-8")
    )
    task_config = runtime_config["env"]["config"]
    resolved = json.loads(args.robot_contract.resolve(strict=True).read_text(encoding="utf-8"))
    names = tuple(resolved["sim_joint_names"])
    if tuple(rows[0]["joint_names"]) != names:
        raise RuntimeError("authority trace and MuJoCo contract joint order disagree")
    default = _tensor(resolved["default_dof_pos"], 20)
    tracker = DepthAddStageTracker.from_task_config(task_config)
    warp = FullActionWarpR5(
        contract=runtime,
        joint_map=A2PiperJointMap.from_sim_joint_names(names, device="cpu"),
        stage_tracker=tracker,
    )
    arm_default = default[:, 12:18]
    transitions: list[dict[str, int]] = []
    stage_divergences: list[dict[str, int]] = []
    max_post_delta_error = 0.0
    max_target_error = 0.0
    goal_event_step: int | None = None
    terminal_step: int | None = None
    stage2_transition_reason_bits: dict[str, bool | float | int] | None = None
    for index, row in enumerate(rows):
        step = int(row["step_index"])
        if tracker.terminal_reason is not None:
            raise RuntimeError(f"local evaluator terminated before authority control step {step}")
        if tracker.stage != int(row["stage_buf"]):
            raise RuntimeError(
                f"local pre-stage {tracker.stage} disagrees with authority stage {row['stage_buf']} at step {step}"
            )
        warped = warp.apply(
            raw_high_level_action=_tensor(row["post_forced_override_pre_env_action"], 12),
            policy_leg_action=_tensor(row["a2_base_leg_action12"], 12),
            default_dof_pos=default,
        )
        post_delta_error = float(
            torch.max(
                torch.abs(
                    warped.stage_action.effective_high_level_action
                    - _tensor(row["post_delta_post_warp_env_action"], 12)
                )
            ).item()
        )
        target_error = float(
            torch.max(
                torch.abs(warped.position_target - _tensor(row["final_joint_position_target20"], 20))
            ).item()
        )
        max_post_delta_error = max(max_post_delta_error, post_delta_error)
        max_target_error = max(max_target_error, target_error)
        before = tracker.stage
        status = tracker.observe_after_step(
            _observation(row, arm_default=arm_default, gripper_open=runtime.gripper_open_target),
            warped.stage_action,
        )
        expected = _expected_post_stage(rows, index)
        if status.stage != expected:
            stage_divergences.append(
                {"step": step, "pre_stage": before, "expected_post_stage": expected, "actual_post_stage": status.stage}
            )
        if status.stage != before:
            transitions.append({"step": step, "from": before, "to": status.stage})
            if before == 2 and status.stage == 3:
                stage2_transition_reason_bits = status.stage2_reason_bits
        if status.goal_event:
            goal_event_step = step
        if status.terminal_reason is not None:
            terminal_step = step
    final = tracker.status()
    source_terminal = str(rows[-1]["terminal_reasons"])
    gate1_pass = (
        not stage_divergences
        and goal_event_step is not None
        and terminal_step == int(rows[-1]["step_index"])
        and source_terminal == "complete"
        and final.terminal_reason == "complete"
    )
    gate3_pass = max_post_delta_error == 0.0 and max_target_error == 0.0
    receipt = {
        "schema": "doordog.sim2sim.depthadd_v3.authority_trace_audit.v1",
        "result": "PASS" if gate1_pass and gate3_pass else "FAIL",
        "authority": {
            "stage0_1_trace": str(args.stage0_1_trace.resolve(strict=True)),
            "stage2_5_trace": str(args.stage2_5_trace.resolve(strict=True)),
            "env_id": args.env_id,
            "episode_index": args.episode_index,
            "rows": len(rows),
            "control_step_range": [int(rows[0]["step_index"]), int(rows[-1]["step_index"])],
        },
        "gate1_stage_goal_reset": {
            "status": "PASS_SUCCESS_TRACE" if gate1_pass else "FAIL_SUCCESS_TRACE",
            "stage_divergences": stage_divergences,
            "transitions": transitions,
            "goal_event_step": goal_event_step,
            "terminal_step": terminal_step,
            "complete_delay_control_steps": tracker.reset_on_complete_delay_control_steps,
            "stage2_transition_reason_bits": stage2_transition_reason_bits,
            "resolved_stage_contract": {
                "completion_close_gate_required": tracker.completion_close_gate_required,
                "contact_force_threshold_n": tracker.contact_force_threshold_n,
                "squeeze_force_min_n": tracker.squeeze_force_min_n,
                "squeeze_force_max_diagnostic_n": tracker.squeeze_force_max_n,
                "over_force_diagnostic_threshold_n": tracker.over_force_threshold_n,
                "grasp_streak_control_steps": tracker.grasp_streak_control_steps,
                "stage3_to4_hinge_threshold_rad": tracker.stage3_to4_hinge_threshold_rad,
                "stage4_to5_hinge_threshold_rad": tracker.stage4_to5_hinge_threshold_rad,
                "goal_root_x_m": tracker.stage5_complete_root_x_m,
            },
            "goal_event_authority": "source _stage_5_to_complete_condition root_x_rel > 1.5",
            "terminal_authority": "trace terminal_reasons=complete after resolved reset_on_complete_delay",
            "failure_trace": "NOT_RUN_NO_AUTHORITY_FAILURE_TRACE",
        },
        "gate3_action_adapter": {
            "status": "PASS_EXACT" if gate3_pass else "FAIL",
            "input_surface": "post_forced_override_pre_env_action12 + a2_base_leg_action12",
            "post_delta_action12_max_abs_error": max_post_delta_error,
            "final_target20_max_abs_error": max_target_error,
            "steps": len(rows),
            "policy_raw_to_forced_override": "OUTSIDE_ADAPTER_AUDIT_BUT_PRESERVED_IN_AUTHORITY_TRACE",
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if receipt["result"] != "PASS":
        raise RuntimeError(f"authority trace audit failed; inspect {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage0-1-trace", type=Path, required=True)
    parser.add_argument("--stage2-5-trace", type=Path, required=True)
    parser.add_argument("--resolved-config", type=Path, required=True)
    parser.add_argument("--robot-contract", type=Path, required=True)
    parser.add_argument("--env-id", type=int, default=13)
    parser.add_argument("--episode-index", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
