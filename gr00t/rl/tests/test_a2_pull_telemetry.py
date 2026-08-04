"""Regression tests for pull-v0 event and telemetry contracts."""

from __future__ import annotations

import ast
from copy import deepcopy
import math
from pathlib import Path

import pytest
import torch

from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2_PULL_ESTIMATE_ONLY,
    A2_PULL_EVENT_NAMES,
    A2_PULL_NA,
    A2_PULL_PRE_E0,
    a2_pull_event_funnel,
    a2_pull_event_state_names,
    advance_a2_pull_events,
    validate_a2_pull_control_step,
    validate_a2_pull_episode,
)
from gr00t.rl.envs.door.a2_pull_direction import (
    A2DoorDirection,
    a2_signed_stage0_nearest_staging_target,
    a2_signed_stage0_staging_band_mask,
)
from gr00t.rl.isaac_utils.rotations import quat_rotate_inverse
from scriptsFORhuman.pull_v0 import build_p1_anchor_stop_receipts as anchor_receipts


PUSH_ENV_SOURCE = Path(__file__).resolve().parents[3] / "gr00t/rl/envs/door/door_open_a2_base.py"
PULL_V0_ROOT = Path(__file__).resolve().parents[3] / "scriptsFORhuman/pull_v0"


def _control_step() -> dict:
    estimate = {"value": [1.0, 2.0], "provenance": A2_PULL_ESTIMATE_ONLY}
    return {
        "door_open_io_sign": 1,
        "door_open_lr_sign": -1,
        "active_handle_face_x_sign": 1,
        "travel_dir_x": -1,
        "stage": 2,
        "event_state": A2_PULL_EVENT_NAMES[2],
        "root_x_rel_door_m": 0.8,
        "signed_crossing_progress_m": -0.8,
        "root_velocity_toward_door_mps": 0.1,
        "root_velocity_yield_outward_mps": 0.02,
        "root_velocity_final_travel_mps": 0.1,
        "root_yaw_error_rad": 0.05,
        "handle_position_rad": 0.1,
        "handle_velocity_radps": 0.2,
        "latch_position_m": 0.002,
        "hinge_position_rad": 0.01,
        "hinge_velocity_radps": 0.03,
        "target_tcp_position_error_m": 0.02,
        "target_tcp_orientation_error_rad": 0.1,
        "bilateral_handle_contact": True,
        "hook_contact": A2_PULL_NA,
        "handle_local_slip_xyz_mps": [0.01, -0.02, 0.0],
        "gripper_handle_separation_m": 0.02,
        "finger_pd_effort_estimate_N": estimate,
        "finger_effort_utilization_estimate": {
            "value": [0.1, 0.2],
            "provenance": A2_PULL_ESTIMATE_ONLY,
        },
        "arm_pd_effort_utilization_estimate": {
            "value": [0.3] * 6,
            "provenance": A2_PULL_ESTIMATE_ONLY,
        },
        "panel_contact_force_by_body_N": {"torso_link": 0.0},
        "frame_contact_force_by_body_N": {"torso_link": 0.0},
        "minimum_panel_robot_clearance_m": A2_PULL_NA,
        "reward_component_raw": {"pull_door_hinge": 0.1},
    }


def _episode(max_event: int, terminal_reason: str = "episode_timeout") -> dict:
    reached = {
        event_name: event_index <= max_event
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    first_steps = {
        event_name: event_index * 10 if event_index <= max_event else A2_PULL_NA
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    first_times = {
        event_name: event_index * 0.2 if event_index <= max_event else A2_PULL_NA
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    reached_e2 = max_event >= 2
    reached_e4 = max_event >= 4
    reached_e5 = max_event >= 5
    reached_e6 = max_event >= 6
    reached_e7 = max_event >= 7
    return {
        "event_reached": reached,
        "first_event_step": first_steps,
        "first_event_time_s": first_times,
        "proof_hold_duration_s": 0.2 if reached_e2 else A2_PULL_NA,
        "proof_retreat_displacement_m": 0.01 if reached_e2 else A2_PULL_NA,
        "max_tensile_retreat_before_loss_m": 0.02 if reached_e2 else A2_PULL_NA,
        "hinge_at_first_positive_progress_rad": 0.01 if reached_e4 else A2_PULL_NA,
        "hinge_at_first_grip_loss_rad": A2_PULL_NA,
        "held_hinge_max_rad": 0.1 if reached_e4 else A2_PULL_NA,
        "hinge_at_release_or_hold_decision_rad": 0.1 if reached_e5 else A2_PULL_NA,
        "root_outward_excursion_before_clear_m": 0.1 if reached_e5 else A2_PULL_NA,
        "first_path_reversal_step": 60 if reached_e6 else A2_PULL_NA,
        "release_to_whole_body_clear_s": 0.4 if reached_e7 else A2_PULL_NA,
        "hinge_reclosure_after_release_rad": A2_PULL_NA,
        "body_panel_contact_steps_per_20s": 0,
        "body_panel_contact_impulse_Ns": 0.0,
        "crossing_while_valid_capture": reached_e6,
        "whole_body_clear": reached_e7,
        "terminal_reason": terminal_reason,
        "spawn_hook": True,
        "hinge_drive_max_force_nm": 7.25,
    }


def test_control_step_schema_and_estimate_provenance() -> None:
    record = _control_step()
    validate_a2_pull_control_step(record)

    missing_provenance = deepcopy(record)
    missing_provenance["finger_pd_effort_estimate_N"]["provenance"] = "MEASURED"
    with pytest.raises(ValueError, match="ESTIMATE_ONLY"):
        validate_a2_pull_control_step(missing_provenance)


def test_event_advancement_is_contiguous_and_records_first_steps() -> None:
    reached = torch.zeros(2, 8, dtype=torch.bool)
    first_steps = torch.full((2, 8), -1, dtype=torch.long)
    evidence = torch.zeros_like(reached)
    evidence[0, :5] = True
    evidence[1, 4] = True
    updated, updated_first = advance_a2_pull_events(
        reached,
        evidence,
        first_steps,
        torch.tensor([12, 13], dtype=torch.long),
    )
    assert updated[0].tolist() == [True] * 5 + [False] * 3
    assert updated_first[0].tolist() == [12] * 5 + [-1] * 3
    assert updated[1].tolist() == [False] * 8
    assert a2_pull_event_state_names(updated) == [A2_PULL_EVENT_NAMES[4], A2_PULL_PRE_E0]


def test_episode_schema_rejects_e4_before_e3() -> None:
    episode = _episode(4)
    episode["event_reached"][A2_PULL_EVENT_NAMES[3]] = False
    episode["first_event_step"][A2_PULL_EVENT_NAMES[3]] = A2_PULL_NA
    episode["first_event_time_s"][A2_PULL_EVENT_NAMES[3]] = A2_PULL_NA
    with pytest.raises(ValueError, match="cannot be reached"):
        validate_a2_pull_episode(episode)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (("first_event_step", -1), ("first_event_time_s", -0.1)),
)
def test_episode_schema_rejects_negative_reached_event_step_or_time(field_name, value):
    episode = _episode(0)
    episode[field_name][A2_PULL_EVENT_NAMES[0]] = value
    with pytest.raises(ValueError, match="non-negative"):
        validate_a2_pull_episode(episode)


def test_event_funnel_uses_na_for_zero_conditioning_denominator() -> None:
    episode = _episode(0)
    validate_a2_pull_episode(episode)
    funnel = a2_pull_event_funnel([episode])
    assert funnel["P(E1)"] == 0.0
    assert funnel["P(E2 | E1)"] == A2_PULL_NA
    assert funnel["P(E3 | E2)"] == A2_PULL_NA


def test_paired_out_in_handle_local_slip_is_mirror_consistent() -> None:
    out_target_orientation_wxyz = torch.tensor([[0.5, 0.5, 0.5, 0.5]])
    in_target_orientation_wxyz = torch.tensor([[-0.5, -0.5, 0.5, 0.5]])
    out_world_slip = torch.tensor([[0.01, 0.02, 0.03]])
    in_world_slip = torch.tensor([[-0.01, -0.02, 0.03]])
    out_local = quat_rotate_inverse(
        out_target_orientation_wxyz,
        out_world_slip,
        w_last=False,
    )
    in_local = quat_rotate_inverse(
        in_target_orientation_wxyz,
        in_world_slip,
        w_last=False,
    )
    assert torch.allclose(out_local, in_local, atol=1.0e-7, rtol=0.0)


def test_push_anchor_step_trace_carries_candidate_applied_and_contact_fields() -> None:
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    for field in (
        "phase_before",
        "phase_after",
        "stage_before",
        "stage_after",
        "dls_candidate_action",
        "dls_candidate_mask",
        "dls_applied_action",
        "dls_finally_applied",
        "base_candidate_action",
        "base_applied_action",
        "final_action",
        "body_panel_contact_per_filter_n",
        "body_panel_contact_total_n",
        "terminal_snapshot",
    ):
        assert f'"{field}"' in source


def test_attempt10_timeout_budget_matches_immutable_stage0_residual_and_response_contract() -> None:
    plan = anchor_receipts._read_json(
        PULL_V0_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_PLAN.json"
    )
    summary = anchor_receipts._read_json(
        anchor_receipts.LOG_ROOT / "attempt10/eval/a2_hold_oracle_summary.json"
    )
    metrics = anchor_receipts._read_json(
        anchor_receipts.LOG_ROOT / "attempt10/eval/metrics_eval.json"
    )
    admission = anchor_receipts._validate_actual_push_anchor_schema(
        summary=summary,
        metrics=metrics,
        require_stage0_response=True,
        attempt=10,
    )
    rows = [row for row in admission["trace"] if "stage0_predicates" in row]
    analysis = anchor_receipts._attempt10_budget_analysis(
        attempt=10,
        plan=plan,
        stage0_rows=rows,
        response_summary=admission["stage0_command_response"],
    )
    assert analysis["initial_stage0_horizontal_m"] == 0.9215447306632996
    assert analysis["terminal_stage0_horizontal_m"] == 0.5063455700874329
    assert analysis["residual_monotonic_nonincreasing"] is True
    assert analysis["residual_increase_count"] == 0
    assert analysis["kinematic_lower_bound_steps"] == 308
    assert analysis["minimum_steps_including_settle"] == 313
    assert analysis["configured_timeout_steps"] == 120
    assert analysis["timeout_shortfall_vs_kinematic_lower_bound_steps"] == 188
    assert analysis["r9_timeout_steps"] == 360
    assert analysis["r9_nominal_horizon_s"] == 7.2
    assert analysis["r9_nominal_travel_m"] == 1.08
    assert admission["stage0_predicates"] == {
        "staging_band": False,
        "settle_count": 0,
        "timed_out": True,
    }
    response = admission["stage0_command_response"]
    assert response["response_count"] == 120
    assert response["anti_alignment_count"] == 0


def _qualification_state(contact: list[float], *, valid: bool = True) -> list[dict]:
    tree = ast.parse(PUSH_ENV_SOURCE.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "a2_pull_p1_reset_contact_qualification_step"
    )
    namespace = {"torch": torch, "math": math}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(PUSH_ENV_SOURCE), "exec"), namespace)
    a2_pull_p1_reset_contact_qualification_step = namespace[function.name]
    streak = torch.zeros(1, dtype=torch.long)
    step = torch.zeros(1, dtype=torch.long)
    states = []
    for value in contact:
        result = a2_pull_p1_reset_contact_qualification_step(
            torch.tensor([value]),
            streak,
            step,
            torch.tensor([valid]),
            torch.tensor([True]),
            contact_threshold_n=1.0,
            qualification_streak_steps=2,
            qualification_window_steps=3,
        )
        streak = result["updated_streak"]
        step = result["updated_window_step"]
        states.append(result)
    return states


def _generic_relief_mask_function():
    tree = ast.parse(PUSH_ENV_SOURCE.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "a2_pull_p1_generic_relief_active_mask"
    )
    namespace = {"torch": torch}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(PUSH_ENV_SOURCE), "exec"), namespace)
    return namespace[function.name]


def test_p1_acquisition_wait_never_enters_generic_relief_over_long_window() -> None:
    mask_fn = _generic_relief_mask_function()
    active = torch.ones(1, dtype=torch.bool)
    acquisition_wait = torch.ones(1, dtype=torch.bool)
    for _ in range(61):
        generic_active = mask_fn(active, True, acquisition_wait)
        assert generic_active.tolist() == [False]
    assert mask_fn(active, False, acquisition_wait).tolist() == [True]
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    assert "stage0_timeout = acquisition_wait & (" in source
    assert "pull_p1_stage0_timeout_steps" in source


def _stage0_command_response_metrics_function():
    tree = ast.parse(PUSH_ENV_SOURCE.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "a2_pull_p1_stage0_command_response_metrics"
    )
    namespace = {"torch": torch, "math": math}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(PUSH_ENV_SOURCE), "exec"), namespace)
    return namespace[function.name]


def _stage0_base_command_function():
    tree = ast.parse(PUSH_ENV_SOURCE.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"a2_hold_base_relief_command", "a2_pull_p1_stage0_base_command"}
    }

    def yaw_quat_wxyz(quat: torch.Tensor) -> torch.Tensor:
        qw, qx, qy, qz = quat.unbind(dim=-1)
        yaw = torch.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))
        result = torch.zeros_like(quat)
        result[:, 0] = torch.cos(yaw / 2.0)
        result[:, 3] = torch.sin(yaw / 2.0)
        return result

    def quat_apply_wxyz(quat: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
        xyz = quat[:, 1:]
        scalar = quat[:, 0:1]
        cross_twice = xyz.cross(vector, dim=-1) * 2.0
        return vector + scalar * cross_twice + xyz.cross(cross_twice, dim=-1)

    def quat_apply_inverse_wxyz(quat: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
        conjugate = torch.cat((quat[:, 0:1], -quat[:, 1:]), dim=-1)
        return quat_apply_wxyz(conjugate, vector)

    namespace = {
        "torch": torch,
        "math": math,
        "A2DoorDirection": A2DoorDirection,
        "a2_signed_stage0_nearest_staging_target": a2_signed_stage0_nearest_staging_target,
        "a2_signed_stage0_staging_band_mask": a2_signed_stage0_staging_band_mask,
        "yaw_quat": yaw_quat_wxyz,
        "quat_apply_inverse": quat_apply_inverse_wxyz,
    }
    module = ast.Module(body=[functions[name] for name in ("a2_hold_base_relief_command", "a2_pull_p1_stage0_base_command")], type_ignores=[])
    exec(compile(module, str(PUSH_ENV_SOURCE), "exec"), namespace)
    return namespace["a2_pull_p1_stage0_base_command"]


def test_stage0_base_command_uses_wxyz_quaternion_and_reprojects_yaw_zero_and_pi():
    command_fn = _stage0_base_command_function()
    root_pos = torch.tensor([[-1.5, 0.0, 0.5], [-1.5, 0.0, 0.5]])
    grasp_target = torch.tensor([[-0.4, -0.5, 0.5], [-0.4, -0.5, 0.5]])
    root_quat_w = torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]])
    result = command_fn(
        root_pos,
        root_quat_w,
        grasp_target,
        torch.tensor([True, True]),
        x_min=0.55,
        x_max=0.60,
        y_tol=0.15,
        direction=A2DoorDirection("out", "right"),
        physical_speed_mps=0.2,
        base_command_scale=0.25,
    )
    target_delta = result["target_w"][:, :2] - root_pos[:, :2]
    desired_world = target_delta / torch.linalg.norm(target_delta, dim=-1, keepdim=True) * 0.2
    body_velocity = result["body_velocity"][:, :2]
    raw_body_velocity = result["raw_command"][:, :2] * 0.25
    assert desired_world[0, 0] > 0.0 and desired_world[0, 1] < 0.0
    assert body_velocity[0, 0] > 0.0 and body_velocity[0, 1] < 0.0
    assert body_velocity[1, 0] < 0.0 and body_velocity[1, 1] > 0.0
    assert torch.allclose(body_velocity, raw_body_velocity)
    yaw = torch.tensor([0.0, math.pi])
    cos_yaw = torch.cos(yaw)
    sin_yaw = torch.sin(yaw)
    reprojected = torch.stack(
        (
            cos_yaw * body_velocity[:, 0] - sin_yaw * body_velocity[:, 1],
            sin_yaw * body_velocity[:, 0] + cos_yaw * body_velocity[:, 1],
        ),
        dim=-1,
    )
    assert torch.allclose(reprojected, desired_world, atol=1.0e-6, rtol=0.0)


def test_stage0_command_response_reconstructs_world_xy_at_yaw_pi() -> None:
    metrics_fn = _stage0_command_response_metrics_function()
    raw = torch.tensor([[-0.5018707514, 0.3288249075, 0.0, 0.0, 0.0]])
    physical = torch.cat((raw[:, :3] * 0.25, raw[:, 3:5] * 0.4), dim=-1)
    metrics = metrics_fn(
        raw,
        physical,
        torch.tensor([-math.pi]),
        torch.tensor([[0.1, -0.02]]),
        torch.tensor([[0.01, -0.01]]),
        base_command_scale=0.25,
        body_pitch_roll_scale=0.4,
    )
    desired = metrics["desired_world_xy_velocity"][0]
    assert torch.allclose(
        desired,
        torch.tensor([0.1254676878, -0.0822062269]),
        atol=1.0e-6,
        rtol=0.0,
    )
    assert torch.allclose(metrics["expected_scaled_body_command"], physical)


def test_stage0_target_inference_preserves_signed_fixed_target_and_band() -> None:
    direction = A2DoorDirection("out", "right")
    grasp_target = torch.tensor([[-0.0975, -0.1475, 0.5]])
    root = torch.tensor([[-0.95, -0.1475, 0.5]])
    target = a2_signed_stage0_nearest_staging_target(
        root,
        grasp_target,
        0.55,
        0.60,
        0.15,
        direction,
    )
    assert torch.allclose(target, torch.tensor([[-0.6975, -0.1475, 0.5]]), atol=1.0e-7)
    assert not a2_signed_stage0_staging_band_mask(
        root, grasp_target, 0.55, 0.60, 0.15, direction
    )[0]


def test_stage0_progress_metrics_are_finite_for_zero_motion_and_report_anti_alignment() -> None:
    metrics_fn = _stage0_command_response_metrics_function()
    zero = torch.zeros(1, 5)
    zero_metrics = metrics_fn(
        zero,
        zero,
        torch.zeros(1),
        torch.zeros(1, 2),
        torch.zeros(1, 2),
        base_command_scale=0.25,
        body_pitch_roll_scale=0.4,
    )
    for name in (
        "progress_velocity_dot",
        "progress_velocity_cosine",
        "progress_displacement_dot",
        "progress_displacement_cosine",
    ):
        assert torch.isfinite(zero_metrics[name]).all()
    assert zero_metrics["progress_velocity_defined"].tolist() == [False]
    assert zero_metrics["progress_displacement_defined"].tolist() == [False]

    anti_aligned = metrics_fn(
        torch.tensor([[1.0, 0.0, 0.0, 0.0, 0.0]]),
        torch.tensor([[1.0, 0.0, 0.0, 0.0, 0.0]]),
        torch.zeros(1),
        torch.tensor([[-0.2, 0.0]]),
        torch.tensor([[-0.1, 0.0]]),
        base_command_scale=1.0,
        body_pitch_roll_scale=0.4,
    )
    assert anti_aligned["progress_velocity_defined"].tolist() == [True]
    assert anti_aligned["progress_velocity_cosine"].item() == pytest.approx(-1.0)
    assert anti_aligned["progress_displacement_cosine"].item() == pytest.approx(-1.0)


def test_stage0_response_preserves_a2base_action_channel_order_and_report_only_semantics() -> None:
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    base_source = Path(PUSH_ENV_SOURCE.parents[1] / "base_task/a2_base.py").read_text(
        encoding="utf-8"
    )
    assert "raw_base_action = high_level_actions[:, layout[\"base_start\"] : layout[\"base_end\"]]" in base_source
    assert "leg_actions = actions[:, -self._a2_leg_action_dim :]" in base_source
    assert "stage0_command_response" in source
    assert '"threshold_mode": "report_only"' in source


def test_r7_two_phase_latch_uses_exact_executor_and_next_post_physics_boundary() -> None:
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    base_source = Path(PUSH_ENV_SOURCE.parents[1] / "base_task/a2_base.py").read_text(
        encoding="utf-8"
    )
    callback_call = base_source.index("self._a2_base_pre_physics_command_callback(")
    physics_call = base_source.index("self._pre_physics_step(final_actions)")
    assert callback_call < physics_call
    assert "getattr(self, \"_a2_base_pre_physics_command_callback\"" not in base_source
    for field in (
        '"episode_generation"',
        '"trace_row_index"',
        '"control_step"',
        '"response_control_step"',
        '"base_command_scale"',
        '"body_pitch_roll_scale"',
        '"physical_command_clipped"',
        '"pre_executor_root_pos_w"',
    ):
        assert field in source
    assert "_complete_a2_pull_p1_stage0_command_response" in source
    assert "post_physics" in source and "self._use_a2_base" in source
    assert "reset cannot clear an environment with a pending command response" in source


def test_reset_step0_transient_contact_does_not_reach_hard_collision() -> None:
    states = _qualification_state([2.0, 0.0, 0.0])
    assert states[0]["persistent"].item() is False
    assert states[-1]["completed"].item() is True
    assert states[-1]["persistent"].item() is False


def test_reset_persistent_qualifying_contact_reaches_hard_collision_gate() -> None:
    states = _qualification_state([2.0, 2.0])
    assert states[0]["persistent"].item() is False
    assert states[1]["persistent"].item() is True
    assert states[1]["completed"].item() is False


def test_reset_invalid_state_cannot_complete_or_pass_admission() -> None:
    states = _qualification_state([0.0, 0.0, 0.0], valid=False)
    assert all(state["invalid"].item() for state in states)
    assert not states[-1]["completed"].item()


def test_reset_preflight_precedes_staging_and_dls_and_records_before_failure() -> None:
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    preflight = source.index("def _step_a2_pull_p1_reset_contact_qualification")
    action_override = source.index("def apply_a2_eval_hold_oracle_action_override")
    staging_call = source.index("a2_pull_p1_stage0_base_command", action_override)
    dls_call = source.index("a2_hold_apply_oracle_branch_actions", action_override)
    assert preflight < action_override < staging_call
    assert preflight < dls_call
    assert source.index("Record the sample first") < source.index(
        '"PULL_P1_BODY_COLLISION"', action_override
    )
    assert '"staging_started": False' in source
    assert '"dls_started": False' in source


def test_cleared_transient_admits_staging_without_stage_promotion() -> None:
    state = _qualification_state([2.0, 0.0, 0.0])[-1]
    assert state["completed"].item() is True
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    assert "active = active & ~reset_qualification_mask" in source
    assert "stage0_admission = a2_pull_p1_stage0_base_command" in source
    assert "self.stage_buf[" not in source[source.index("def a2_pull_p1_reset_contact_qualification_step"):source.index("def a2_pull_p1_reset_contact_qualification_step") + 2000]


def test_terminal_current_contact_is_separate_from_running_max() -> None:
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    assert '"terminal_body_panel_contact_total_current_n"' in source
    assert '"body_panel_contact_total_max_n"' in source
    assert '"body_panel_contact_total_current_n"' in source


def test_reset_qualification_latch_is_shared_by_terminal_and_summary_exports() -> None:
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    terminal_start = source.index("def _get_a2_push_anchor_admission_terminal_record")
    summary_start = source.index("def get_a2_hold_oracle_summary")
    reset_state_helper = "_get_a2_pull_p1_reset_qualification_state"
    assert source.index(reset_state_helper, terminal_start) < summary_start
    assert source.index("reset_qualification =", terminal_start) < summary_start
    assert source.index("reset_states =", summary_start) > summary_start
    assert '"per_env_reset_contact_qualification_complete": reset_complete' in source
    assert '"reset_contact_qualification": reset_qualification' in source
    assert "_latch_a2_pull_p1_reset_qualification_before_reset(env_ids)" in source


def test_host_stage_overtime_outcome_is_appended_and_summary_keeps_non_overtime_latches():
    source = PUSH_ENV_SOURCE.read_text(encoding="utf-8")
    names_start = source.index("A2_HOLD_OUTCOME_NAMES = (")
    names_end = source.index(")\nA2_HOLD_OUTCOME_TO_ID", names_start)
    names_text = source[names_start:names_end]
    assert '"PULL_P1_RESET_STATE_INVALID"' in names_text
    assert names_text.rstrip().endswith('"PULL_P1_STAGE0_HOST_STAGE_OVERTIME",')
    summary_start = source.index("def get_a2_hold_oracle_summary")
    summary = source[summary_start:]
    host_assignment = summary.index('"PULL_P1_STAGE0_HOST_STAGE_OVERTIME"')
    proof_assignment = summary.index('"PULL_P1_PROOF_TIMEOUT"')
    latch_assignment = summary.index('"PULL_P1_LATCH_NOT_RELEASED"')
    arc_assignment = summary.index('"ARC_PROBE_TIMEOUT"')
    assert host_assignment < proof_assignment < latch_assignment < arc_assignment
    host_region = summary[:proof_assignment]
    assert "pending" in host_region
    assert "A2_HOLD_PHASE_PULL_P1_ACQUIRE" in host_region
    assert "self.actual_time_in_stage_buf" in host_region
    assert "self.max_stage_time[self.stage_buf]" in host_region
    assert "latched_stage_time_valid" in host_region
    assert "expected_stage_time = (400, 100, 100, 100, 100, 200)" in source
    assert "Pull P1 push-anchor host stage budget must exceed reset qualification" in source
    assert "proof_pending = pending &" in summary
    assert "latch_pending = pending &" in summary


def test_attempt11_raw_runtime_and_canonical_receipt_preserve_measured_host_overtime():
    import json

    root = Path(__file__).resolve().parents[3]
    metrics_path = root / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt11/eval/metrics_eval.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    terminal = metrics["episode_terminal_diagnostics"][0]
    admission = terminal["push_anchor_admission"]
    assert metrics["episode_max_stage_reached"] == [0]
    assert metrics["episode_terminal_reasons"] == ["stage_overtime"]
    assert terminal["stage_buf"] == 0
    assert terminal["time_in_stage_buf"] == 250
    assert admission["stage0_predicates"] == {
        "staging_band": False,
        "settle_count": 0,
        "timed_out": False,
    }
    assert admission["stage0_command_response"]["response_count"] == 247
    assert admission["stage0_command_response"]["anti_alignment_count"] == 0
    receipt = json.loads(
        (root / "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT11_RECEIPT.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["observed"]["raw_summary_outcome"] == "ARC_PROBE_TIMEOUT"
    assert receipt["observed"]["classified_outcome"] == "PULL_P1_STAGE0_HOST_STAGE_OVERTIME"
    assert receipt["host_stage_timer"]["actual_device_local_stage_timer_steps"] == 250
    assert receipt["host_stage_timer"]["local_stage0_watchdog_steps"] == 360
    assert receipt["host_stage_timer"]["reset_qualification_steps"] == 3


def test_pull_guard_remains_byte_contract_for_pull_plan_while_anchor_keeps_guard_disabled():
    root = Path(__file__).resolve().parents[3]
    guard_source = (root / "gr00t/rl/envs/door/a2_pull_v0_guard.py").read_text(encoding="utf-8")
    assert "A2_PULL_V0_STAGE_TIME_BUDGET_STEPS = (250, 100, 100, 100, 100, 200)" in guard_source
    anchor_source = (
        root / "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml"
    ).read_text(encoding="utf-8")
    assert "a2_v20_R1_plan_id: disabled" in anchor_source
