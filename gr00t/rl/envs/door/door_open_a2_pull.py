"""Pull-only A2+Piper environment with immutable signed door semantics."""

from __future__ import annotations

import math
import json
from collections.abc import Mapping
from collections import Counter
from pathlib import Path

import torch
from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from isaaclab.sensors import ContactSensor, ContactSensorCfg
from isaaclab.utils.math import (
    apply_delta_pose,
    axis_angle_from_quat,
    combine_frame_transforms,
    euler_xyz_from_quat,
    quat_apply,
    quat_apply_inverse,
    quat_from_euler_xyz,
    quat_inv,
    quat_mul,
    subtract_frame_transforms,
    wrap_to_pi,
    yaw_quat,
)
from typing_extensions import override

from gr00t.rl.envs.base_task.a2_base import A2Base
from gr00t.rl.envs.base_task.staged_task_base import StagedTaskBase
from gr00t.rl.envs.door.a2_pull_direction import (
    A2DoorDirection,
    a2_pull_proof_world_offset_x,
    a2_signed_stage0_nearest_staging_target,
    a2_signed_stage0_staging_band_mask,
)
from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2PullEvent,
    A2_PULL_ESTIMATE_ONLY,
    A2_PULL_EVENT_NAMES,
    A2_PULL_HARD_GATE_EVENT_PREDECESSORS,
    A2_PULL_NA,
    a2_pull_event_state_names,
    advance_a2_pull_events,
    a2_pull_v5_release_tuck_override,
    validate_a2_pull_control_step,
    validate_a2_pull_episode,
    validate_a2_pull_v6_control_extension,
)
from gr00t.rl.envs.door.a2_pull_v0_guard import (
    A2_PULL_V0_TARGET_ORIENTATION_WXYZ,
    A2_PULL_V3_PLAN_ID,
    A2_PULL_V4_PLAN_ID,
    A2_PULL_V5_PLAN_ID,
    A2_PULL_V5_CLOSER_BUCKETS,
    A2_PULL_V5_RESET_SOURCES,
    A2_PULL_V5_STATE_BANK_SCHEMA,
    A2_PULL_V5_STATE_BANK_SOURCE_SCHEMA,
    A2_PULL_V5_RELEASE_STREAK_STEPS,
    A2_PULL_V5_START_OVERRIDE_STEPS,
    A2_PULL_V6_PLAN_ID,
)
from gr00t.rl.envs.door.door_open_a2_base import (
    A2_HOLD_OUTCOME_TO_ID,
    DoorPregrasp,
    a2_hold_absolute_target_to_cumulative_action,
    a2_hold_apply_source_offset_to_jacobian,
    a2_hold_base_relief_command,
    a2_hold_capture_handoff_relative_orientation,
    a2_hold_rotate_jacobian_to_root,
    a2_v20_arc_tracking_quality,
    a2_v20_handle_opening_tangent,
    a2_hold_pd_effort_estimates,
    a2_v20_mask_stage_overtime_for_arc_probe,
)
from gr00t.rl.envs.door.a2_v20_r2_evidence import a2_v20_r2_taskspace_arm_carry
from gr00t.rl.isaac_utils.rotations import xyzw_to_wxyz
from gr00t.rl.utils.torch_utils import torch_rand_float


# v5.4 measured-model scheduler contract.  Every value is paired with its
# Stage-A receipt location; these are intentionally constants rather than
# config knobs.
A2_PULL_V5_4_SCHEDULER_CONSTANTS = {
    "dt_s": {
        "value": 0.02,
        "receipt_jsonpath": "$.scheduler_derived.constants.dt_s.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "planning_a_rad": {
        "value": 0.10,
        "receipt_jsonpath": "$.scheduler_derived.constants.planning_a_rad.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "b_trim_rad": {
        "value": 0.22435537973512823,
        "receipt_jsonpath": "$.scheduler_derived.constants.b_trim_rad.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "coarse_raw_negative": {
        "value": -2.0,
        "receipt_jsonpath": "$.scheduler_derived.constants.coarse_raw_negative.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "coarse_raw_positive": {
        "value": 2.0,
        "receipt_jsonpath": "$.scheduler_derived.constants.coarse_raw_positive.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "coarse_rate_negative_rad_s": {
        "value": -0.463556439676557,
        "receipt_jsonpath": "$.scheduler_derived.constants.coarse_rate_negative_rad_s.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "coarse_rate_positive_rad_s": {
        "value": 0.4286859929561615,
        "receipt_jsonpath": "$.scheduler_derived.constants.coarse_rate_positive_rad_s.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "coarse_stop_drift_negative_rad": {
        "value": -0.2168513536453247,
        "receipt_jsonpath": "$.scheduler_derived.constants.coarse_stop_drift_negative_rad.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "coarse_stop_drift_positive_rad": {
        "value": 0.03908896446228027,
        "receipt_jsonpath": "$.scheduler_derived.constants.coarse_stop_drift_positive_rad.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "minimum_settle_steps_negative": {
        "value": 56,
        "receipt_jsonpath": "$.scheduler_derived.constants.minimum_settle_steps_negative.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "minimum_settle_steps_positive": {
        "value": 53,
        "receipt_jsonpath": "$.scheduler_derived.constants.minimum_settle_steps_positive.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "settle_deadline_steps": {
        "value": 100,
        "receipt_jsonpath": "$.scheduler_derived.constants.settle_deadline_steps.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "settle_velocity_threshold_rad_s": {
        "value": 0.05,
        "receipt_jsonpath": "$.scheduler_derived.constants.settle_velocity_threshold_rad_s.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "coarse_cutoff_negative_e_rad": {
        "value": -0.4412067333804529,
        "receipt_jsonpath": "$.scheduler_derived.constants.coarse_cutoff_negative_e_rad.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "coarse_cutoff_positive_e_rad": {
        "value": -0.18526641527284796,
        "receipt_jsonpath": "$.scheduler_derived.constants.coarse_cutoff_positive_e_rad.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "trim_raw": {
        "value": 0.05,
        "receipt_jsonpath": "$.scheduler_derived.constants.trim_raw.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "trim_realized_rate_rad_s": {
        "value": -0.030965522923741773,
        "receipt_jsonpath": "$.scheduler_derived.constants.trim_realized_rate_rad_s.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "trim_one_step_rad": {
        "value": -0.0006193104584748354,
        "receipt_jsonpath": "$.scheduler_derived.constants.trim_one_step_rad.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "trim_stop_drift_rad": {
        "value": -0.0004932880401611328,
        "receipt_jsonpath": "$.scheduler_derived.constants.trim_stop_drift_rad.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "trim_step_cap": {
        "value": 200,
        "receipt_jsonpath": "$.scheduler_derived.constants.trim_step_cap.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
    "terminal_hold_steps": {
        "value": 100,
        "receipt_jsonpath": "$.scheduler_derived.constants.terminal_hold_steps.value",
        "source": "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
    },
}


_A2_PULL_SHARED_STAGED_RESET_BUFFER_NAMES = (
    "a2_pull_event_reached",
    "a2_pull_stable_unlatch_handle_ever",
    "a2_pull_stable_unlatch_latch_ever",
    "a2_pull_relock_handle_ever",
    "a2_pull_relock_latch_ever",
    "a2_pull_prev_handle_unlatched",
    "a2_pull_prev_latch_unlatched",
    "a2_pull_first_event_step",
    "a2_pull_first_event_time_s",
    "a2_pull_capture_root_x",
    "a2_pull_capture_valid",
    "a2_pull_max_tensile_retreat_m",
    "a2_pull_release_or_hold_decision",
    "a2_pull_proof_active",
    "a2_pull_proof_start_root_x",
    "a2_pull_proof_last_root_x",
    "a2_pull_proof_duration_s",
    "a2_pull_proof_displacement_m",
    "a2_pull_proof_streak",
    "a2_pull_proof_valid",
    "a2_pull_minimum_panel_robot_clearance_m",
    "a2_pull_clearance_ready",
    "a2_pull_aperture_ready",
    "a2_pull_frame_passage",
    "a2_pull_frame_passage_step",
    "a2_pull_planar_crossing",
    "a2_pull_planar_crossing_step",
    "a2_pull_detour",
    "a2_pull_frame_approach",
    "a2_pull_frame_approach_active",
    "a2_pull_frame_approach_pre_aperture_steps",
    "a2_pull_frame_approach_post_frame_passage_steps",
    "a2_pull_frame_midpoint_distance_min_m",
    "a2_pull_deliberate_release",
    "a2_pull_deliberate_release_step",
    "a2_pull_first_negative_x_motion_step",
    "a2_pull_prev_stable_contact",
    "a2_pull_prev_panel_contact",
    "a2_pull_post_release_recontact_count",
    "a2_pull_base_path_length_m",
    "a2_pull_prev_base_pos_xy",
    "a2_pull_base_reversal_count",
    "a2_pull_prev_travel_velocity",
    "a2_pull_swept_arc_clearance_margin_current_m",
    "a2_pull_swept_arc_clearance_margin_min_m",
    "a2_pull_corridor_door_wide_pre_aperture_steps",
    "a2_pull_corridor_clean_passage_pre_aperture_steps",
    "a2_pull_stage0_staging_band",
    "a2_pull_stage0_arm_default",
    "a2_pull_stage0_base_still",
    "a2_pull_first_scripted_activation_step",
    "a2_pull_hinge_at_first_positive_progress_rad",
    "a2_pull_held_hinge_max_rad",
    "a2_pull_hinge_at_decision_rad",
    "a2_pull_root_outward_excursion_m",
    "a2_pull_first_path_reversal_step",
    "a2_pull_body_panel_contact_steps",
    "a2_pull_body_panel_contact_impulse_ns",
    "a2_pull_prev_handle_to_tcp_pos",
    "a2_pull_handle_local_slip_xyz_mps",
    "a2_pull_handle_local_slip_valid",
)

_A2_PULL_V5_STAGED_RESET_EXTRA_BUFFER_NAMES = (
    "a2_pull_v5_persistent_release_streak",
    "a2_pull_v5_persistent_release",
    "a2_pull_v5_intervention_elapsed_steps",
    "a2_pull_v5_intervention_active",
)

_A2_PULL_V6_STAGED_RESET_EXTRA_BUFFER_NAMES = (
    "last_delta_actions",
    "last_a2_leg_actions",
    "last_a2_arm_actions",
    "a2_gripper_primitive_raw",
    "unwarped_actions",
    "homie_commands",
    "homie_actions",
    "a2_base_obs_history",
    "a2_base_obs_history_initialized",
    "a2_gait_phase",
    "a2_gait_last_update_step",
    "a2_pull_v6_subphase",
    "a2_pull_v6_pivot_xy",
    "a2_pull_v6_pivot_valid",
    "a2_pull_v6_handle_y_capture",
    "a2_pull_v6_handle_y_current",
    "a2_pull_v6_handle_y_prev",
    "a2_pull_v6_handle_y_best",
    "a2_pull_v6_handle_side_progress",
    "a2_pull_v6_handle_crossed",
    "a2_pull_v6_handle_cross_bonus",
    "a2_pull_v6_release_side_qualified",
    "a2_pull_v6_handoff_active",
    "a2_pull_v6_handoff_reached",
    "a2_pull_v6_handoff_active_steps",
    "a2_pull_v6_handoff_reward_window",
    "a2_pull_v6_handle_to_tcp_capture_pos",
    "a2_pull_v6_handle_to_tcp_capture_quat",
    "a2_pull_v6_handle_to_tcp_valid",
    "a2_pull_v6_prev_tcp_pos_w",
    "a2_pull_v6_prev_tcp_valid",
    "a2_pull_v6_positive_arm_tangent",
    "a2_pull_v6_positive_base_tangent",
    "a2_pull_v6_positive_total_tangent",
    "a2_pull_v6_instantaneous_arm_tangent_share",
    "a2_pull_v6_arm_tangent_integral_m",
    "a2_pull_v6_total_tangent_integral_m",
    "a2_pull_v6_arm_tangent_share",
    "a2_pull_v6_last_held_arm_tangent_share",
    "a2_pull_v6_arc_error_m",
    "a2_pull_v6_arc_quality",
    "a2_pull_v6_pivot_displacement_m",
    "a2_pull_v6_workspace_margin",
    "a2_pull_v6_release_ready",
    "a2_pull_v6_prev_release_ready",
    "a2_pull_v6_release_event",
    "a2_pull_v6_clean_release",
    "a2_pull_v6_premature_release",
    "a2_pull_v6_clean_release_event",
    "a2_pull_v6_premature_release_event",
    "a2_pull_v6_release_quality",
    "a2_pull_v6_release_persistence",
    "a2_pull_v6_persistence_income_active",
    "a2_pull_v6_persistence_income_consumed",
    "a2_pull_v6_hinge_at_release",
    "a2_pull_v6_hinge_velocity_at_release",
    "a2_pull_v6_root_yaw_at_capture",
    "a2_pull_v6_root_yaw_delta",
    "a2_pull_v6_prev_bilateral_contact",
    "a2_pull_v6_e5_snapshot_pending",
    "a2_pull_v6_pre_release_snapshot_pending",
)

A2_PULL_V6_STATE_BANK_V3_SCHEMA = "a2_piper_pull_v6_state_bank_v3"
A2_PULL_V61_LATE_STATE_BANK_V1_SCHEMA = "a2_piper_pull_v61_late_state_bank_v1"
A2_PULL_V61_LATE_STATE_BANK_LABELS = (
    "post_release_d25",
    "frame_passage",
    "e6_stage5_entry",
)

A2_PULL_V5_4_SCHEDULER_SCHEMA = "a2_piper_pull_v5_4_terminal_yaw_scheduler_v1"


def _a2_pull_v5_4_wrap_error(target_yaw: float, measured_yaw: float) -> float:
    """Return the registered scheduler sign e=wrap(target-measured)."""

    return math.remainder(float(target_yaw) - float(measured_yaw), 2.0 * math.pi)


class A2PullV54TerminalYawScheduler:
    """Scalar reference state machine used by dry-run fixtures and the env hook."""

    XY_TRACK = "XY_TRACK"
    PLAN_YAW = "PLAN_YAW"
    COARSE = "COARSE"
    SETTLE = "SETTLE"
    TRIM = "TRIM"
    FINAL = "FINAL"
    TERMINAL_HOLD = "TERMINAL_HOLD"
    DONE = "DONE"
    FAILED = "FAILED"

    def __init__(self, target_yaw: float, measured_yaw: float = 0.0) -> None:
        self.target_yaw = float(target_yaw)
        self.state = self.XY_TRACK
        self.coarse_raw = 0.0
        self.coarse_cutoff = 0.0
        self.minimum_settle_steps = 0
        self.settle_steps = 0
        self.trim_steps = 0
        self.terminal_hold_steps = 0
        self.failure_reason: str | None = None
        self.last_error = _a2_pull_v5_4_wrap_error(target_yaw, measured_yaw)

    @staticmethod
    def _constant(name: str) -> float:
        return float(A2_PULL_V5_4_SCHEDULER_CONSTANTS[name]["value"])

    def _fail(self, reason: str, error: float) -> dict[str, object]:
        self.state = self.FAILED
        self.failure_reason = reason
        self.last_error = float(error)
        return self.telemetry(raw=0.0, error=error)

    def telemetry(self, *, raw: float, error: float) -> dict[str, object]:
        return {
            "schema": A2_PULL_V5_4_SCHEDULER_SCHEMA,
            "state": self.state,
            "raw_yaw_command": float(raw),
            "error_rad": float(error),
            "failure_reason": self.failure_reason,
            "settle_steps": int(self.settle_steps),
            "trim_steps": int(self.trim_steps),
            "terminal_hold_steps": int(self.terminal_hold_steps),
            "terminal": self.state == self.DONE,
        }

    def step(
        self,
        measured_yaw: float,
        *,
        waypoint_arrived: bool,
        yaw_rate_rad_s: float,
    ) -> dict[str, object]:
        error = _a2_pull_v5_4_wrap_error(self.target_yaw, measured_yaw)
        self.last_error = error
        if (
            isinstance(yaw_rate_rad_s, bool)
            or not isinstance(yaw_rate_rad_s, (int, float))
            or not math.isfinite(float(yaw_rate_rad_s))
        ):
            raise ValueError("scheduler yaw_rate_rad_s must be a finite numeric world-frame rate")
        yaw_rate_rad_s = float(yaw_rate_rad_s)
        if self.state == self.XY_TRACK:
            if waypoint_arrived:
                self.state = self.PLAN_YAW
            return self.telemetry(raw=0.0, error=error)
        if self.state == self.PLAN_YAW:
            band = self._constant("b_trim_rad")
            if abs(error) <= band:
                if error > 0.0:
                    return self._fail("positive_error_inside_trim_band", error)
                self.state = self.TRIM
                return self.telemetry(raw=0.0, error=error)
            if error > 0.0:
                self.coarse_raw = self._constant("coarse_raw_positive")
                self.coarse_cutoff = self._constant("coarse_cutoff_positive_e_rad")
                self.minimum_settle_steps = int(self._constant("minimum_settle_steps_positive"))
            else:
                self.coarse_raw = self._constant("coarse_raw_negative")
                self.coarse_cutoff = self._constant("coarse_cutoff_negative_e_rad")
                self.minimum_settle_steps = int(self._constant("minimum_settle_steps_negative"))
            self.state = self.COARSE
            return self.telemetry(raw=self.coarse_raw, error=error)
        if self.state == self.COARSE:
            reached_cutoff = (
                error <= self.coarse_cutoff if self.coarse_raw > 0.0 else error >= self.coarse_cutoff
            )
            if reached_cutoff:
                self.state = self.SETTLE
                self.settle_steps = 0
                return self.telemetry(raw=0.0, error=error)
            return self.telemetry(raw=self.coarse_raw, error=error)
        if self.state == self.SETTLE:
            self.settle_steps += 1
            settle_ready = (
                self.settle_steps >= self.minimum_settle_steps
                and abs(yaw_rate_rad_s)
                <= self._constant("settle_velocity_threshold_rad_s")
            )
            if (
                self.settle_steps >= int(self._constant("settle_deadline_steps"))
                and not settle_ready
            ):
                return self._fail("settle_deadline_exceeded", error)
            if settle_ready:
                self.state = self.TRIM
            return self.telemetry(raw=0.0, error=error)
        if self.state == self.TRIM:
            band = self._constant("b_trim_rad")
            if error > 0.0 and abs(error) <= band:
                return self._fail("positive_error_inside_trim_band", error)
            predicted = error - self._constant("trim_one_step_rad") - self._constant("trim_stop_drift_rad")
            if abs(predicted) <= self._constant("planning_a_rad"):
                self.state = self.FINAL
                return self.telemetry(raw=0.0, error=error)
            if self.trim_steps >= int(self._constant("trim_step_cap")):
                return self._fail("trim_step_cap_exceeded", error)
            self.trim_steps += 1
            return self.telemetry(raw=self._constant("trim_raw"), error=error)
        if self.state == self.FINAL:
            self.state = self.TERMINAL_HOLD
            self.terminal_hold_steps = 0
            return self.telemetry(raw=0.0, error=error)
        if self.state == self.TERMINAL_HOLD:
            self.terminal_hold_steps += 1
            if self.terminal_hold_steps >= int(self._constant("terminal_hold_steps")):
                if abs(error) <= 0.15 and waypoint_arrived:
                    self.state = self.DONE
                else:
                    return self._fail("terminal_hold_yaw_error", error)
            return self.telemetry(raw=0.0, error=error)
        if self.state == self.DONE:
            return self.telemetry(raw=0.0, error=error)
        return self._fail(self.failure_reason or "scheduler_failed", error)


def _a2_pull_v5_characterization_termination(
    reset_after_super: torch.Tensor,
    terminal_reason_bufs: Mapping[str, torch.Tensor],
    characterization_active: torch.Tensor,
    episode_length_buf: torch.Tensor,
    window_steps: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Mask only stage overtime until the diagnostic first-episode window ends."""

    if (
        not torch.is_tensor(reset_after_super)
        or reset_after_super.ndim != 1
        or reset_after_super.dtype != torch.long
        or not torch.is_tensor(characterization_active)
        or characterization_active.shape != reset_after_super.shape
        or characterization_active.dtype != torch.bool
        or not torch.is_tensor(episode_length_buf)
        or episode_length_buf.shape != reset_after_super.shape
        or episode_length_buf.dtype not in (torch.int32, torch.int64)
        or isinstance(window_steps, bool)
        or not isinstance(window_steps, int)
        or window_steps <= 0
    ):
        raise RuntimeError("HOMIE characterization termination tensors have invalid contracts.")
    expected_device = reset_after_super.device
    if (
        characterization_active.device != expected_device
        or episode_length_buf.device != expected_device
    ):
        raise RuntimeError("HOMIE characterization termination tensors must share a device.")
    if not isinstance(terminal_reason_bufs, Mapping) or "stage_overtime" not in terminal_reason_bufs:
        raise RuntimeError("HOMIE characterization requires the stage_overtime terminal reason buffer.")
    stage_overtime_reason = terminal_reason_bufs["stage_overtime"]
    if (
        not torch.is_tensor(stage_overtime_reason)
        or stage_overtime_reason.shape != reset_after_super.shape
        or stage_overtime_reason.dtype != torch.bool
        or stage_overtime_reason.device != expected_device
    ):
        raise RuntimeError("HOMIE characterization stage_overtime reason has an invalid contract.")
    other_terminal_reason = torch.zeros_like(stage_overtime_reason)
    for reason_name, reason_buf in terminal_reason_bufs.items():
        if reason_name == "stage_overtime":
            continue
        if (
            not torch.is_tensor(reason_buf)
            or reason_buf.shape != reset_after_super.shape
            or reason_buf.dtype != torch.bool
            or reason_buf.device != expected_device
        ):
            raise RuntimeError(
                "HOMIE characterization terminal reason buffers must share the reset contract."
            )
        other_terminal_reason |= reason_buf
    if torch.any(characterization_active & (episode_length_buf > window_steps)):
        raise RuntimeError("HOMIE characterization overran its exact first-episode window.")
    pending_window = characterization_active & (episode_length_buf < window_steps)
    updated_reset, updated_stage_overtime, _ = a2_v20_mask_stage_overtime_for_arc_probe(
        reset_after_super,
        stage_overtime_reason,
        other_terminal_reason,
        pending_window,
    )
    diagnostic_done = characterization_active & (episode_length_buf == window_steps)
    updated_stage_overtime &= ~diagnostic_done
    return updated_reset, updated_stage_overtime, diagnostic_done


def _a2_pull_v5_scheduler_termination(
    reset_after_super: torch.Tensor,
    terminal_reason_bufs: Mapping[str, torch.Tensor],
    scheduler_episode_indices: torch.Tensor,
    scheduler_state: torch.Tensor,
    scheduler_state_ids: Mapping[str, int],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Mask stage overtime only while the first scheduler episode is live."""

    if (
        not torch.is_tensor(reset_after_super)
        or reset_after_super.ndim != 1
        or reset_after_super.dtype != torch.long
        or not torch.is_tensor(scheduler_episode_indices)
        or scheduler_episode_indices.shape != reset_after_super.shape
        or scheduler_episode_indices.dtype != torch.long
        or not torch.is_tensor(scheduler_state)
        or scheduler_state.shape != reset_after_super.shape
        or scheduler_state.dtype != torch.long
        or not isinstance(scheduler_state_ids, Mapping)
    ):
        raise RuntimeError("Pull-v5.4 scheduler termination tensors have invalid contracts.")
    expected_device = reset_after_super.device
    if (
        scheduler_episode_indices.device != expected_device
        or scheduler_state.device != expected_device
    ):
        raise RuntimeError("Pull-v5.4 scheduler termination tensors must share a device.")
    if not isinstance(terminal_reason_bufs, Mapping) or "stage_overtime" not in terminal_reason_bufs:
        raise RuntimeError("Pull-v5.4 scheduler termination requires the stage_overtime reason buffer.")
    stage_overtime_reason = terminal_reason_bufs["stage_overtime"]
    if (
        not torch.is_tensor(stage_overtime_reason)
        or stage_overtime_reason.shape != reset_after_super.shape
        or stage_overtime_reason.dtype != torch.bool
        or stage_overtime_reason.device != expected_device
    ):
        raise RuntimeError("Pull-v5.4 scheduler stage_overtime reason has an invalid contract.")
    try:
        done_state = int(scheduler_state_ids["DONE"])
        failed_state = int(scheduler_state_ids["FAILED"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Pull-v5.4 scheduler state IDs require DONE and FAILED integers.") from exc
    known_state = torch.zeros_like(scheduler_state, dtype=torch.bool)
    for state_value in scheduler_state_ids.values():
        if isinstance(state_value, bool) or not isinstance(state_value, int):
            raise RuntimeError("Pull-v5.4 scheduler state IDs must be integers.")
        known_state |= scheduler_state == state_value
    if torch.any(~known_state):
        raise RuntimeError("Pull-v5.4 scheduler state contains an unknown state ID.")
    other_terminal_reason = torch.zeros_like(stage_overtime_reason)
    for reason_name, reason_buf in terminal_reason_bufs.items():
        if reason_name == "stage_overtime":
            continue
        if (
            not torch.is_tensor(reason_buf)
            or reason_buf.shape != reset_after_super.shape
            or reason_buf.dtype != torch.bool
            or reason_buf.device != expected_device
        ):
            raise RuntimeError(
                "Pull-v5.4 scheduler terminal reason buffers must share the reset contract."
            )
        other_terminal_reason |= reason_buf
    first_episode = scheduler_episode_indices == 0
    scheduler_terminal = first_episode & (
        (scheduler_state == done_state) | (scheduler_state == failed_state)
    )
    scheduler_live = first_episode & ~scheduler_terminal
    updated_reset, updated_stage_overtime, _ = a2_v20_mask_stage_overtime_for_arc_probe(
        reset_after_super,
        stage_overtime_reason,
        other_terminal_reason,
        scheduler_live,
    )
    updated_reset |= scheduler_terminal.to(dtype=updated_reset.dtype)
    non_scheduler_terminal = scheduler_live & other_terminal_reason
    return updated_reset, updated_stage_overtime, scheduler_terminal, non_scheduler_terminal


class DoorOpenA2Pull(DoorPregrasp):
    """Pull-v0 specialization that leaves the push environment namespace unchanged."""

    A2_PREGRASP_OFFSET = (0.10, 0.0, 0.0)
    A2_PUSH_ANCHOR_TARGET_ORIENTATION_WXYZ = (0.5, 0.5, 0.5, 0.5)
    A2_PULL_DOOR_BODY_FRAME_CONTACT_SENSOR = "a2_pull_door_body_frame_contact_sensor"
    A2_PULL_DOOR_ARM_FRAME_CONTACT_SENSOR = "a2_pull_door_arm_frame_contact_sensor"
    # Source-grounded panel geometry from door.py: the panel cube has a 0.02 m
    # half-thickness and the builder's end gap is gap_width=0.002 m.
    _A2_PULL_PANEL_HALF_THICKNESS_M = 0.02
    _A2_PULL_PANEL_END_GAP_M = 0.002
    _A2_PULL_DOOR_HINGE_LOCAL_X_M = 0.02
    # The A2_Piper trunk URDF (data/robots/A2_Piper/a2_piper.urdf) horizontal
    # envelope is approximately 0.398 m;
    # use the source-grounded 0.40 m circular footprint for report-only clearance.
    _A2_PULL_TRUNK_FOOTPRINT_RADIUS_M = 0.40
    _A2_PULL_V6_PHASE_A = 0
    _A2_PULL_V6_PHASE_B = 1
    _A2_PULL_V6_PHASE_C = 2
    _A2_PULL_V6_PHASE_D = 3
    _A2_PULL_V5_PROBE_WAYPOINT_TOLERANCE_M = 0.20
    _A2_PULL_V5_PROBE_YAW_TOLERANCE_RAD = 0.25
    _A2_PULL_V5_PROBE_SEQUENCES = {
        "S1": ("straight_minus_x",),
        "S2": ("side_step",),
        "S3": ("side_step", "straight_minus_x"),
        "S4": ("straight_minus_x", "side_step"),
    }
    _A2_PULL_V5_PROBE_PRIMITIVES = {
        "straight_minus_x": (-0.30, 0.0, 0.0),
        "turn_then_forward": (0.0, 0.0, -0.55),
        "side_step": (-0.18, 0.24, 0.0),
        "arc": (-0.22, 0.0, 0.35),
    }
    _A2_PULL_V5_CHARACTERIZATION_RAW_YAW_LIMIT = 2.0
    _A2_PULL_V5_CHARACTERIZATION_YAW_MAGNITUDES = (0.05, 0.1, 0.2, 0.4, 0.8, 2.0)
    _A2_PULL_V5_CHARACTERIZATION_DURATIONS_S = (1.0, 2.0, 4.0)
    _A2_PULL_V5_CHARACTERIZATION_PRIMITIVES = ("none", "straight_minus_x", "side_step")
    _A2_PULL_V5_CHARACTERIZATION_TRACE_SCHEMA = (
        "a2_piper_pull_v5_interface_characterization_trace_v1"
    )
    _A2_PULL_V5_CHARACTERIZATION_PLAN_ID = (
        "a2_piper_pull_v5_3_locomotion_interface_probe"
    )
    _A2_PULL_V5_4_SCHEDULER_SCHEMA = A2_PULL_V5_4_SCHEDULER_SCHEMA
    _A2_PULL_V5_4_SCHEDULER_CONSTANTS = A2_PULL_V5_4_SCHEDULER_CONSTANTS
    _A2_PULL_V5_4_SCHEDULER_STATES = {
        "XY_TRACK": 0,
        "PLAN_YAW": 1,
        "COARSE": 2,
        "SETTLE": 3,
        "TRIM": 4,
        "FINAL": 5,
        "TERMINAL_HOLD": 6,
        "DONE": 7,
        "FAILED": 8,
    }

    def __init__(self, config, device):
        config_mapping = config.get("config", config)
        if not isinstance(config_mapping, Mapping):
            raise RuntimeError("Pull-v0 config must expose a mapping for env.config.")
        self._pull_direction = A2DoorDirection(
            door_open_io=config_mapping["a2_pull_door_open_io"],
            door_open_lr=config_mapping["a2_pull_door_open_lr"],
        )
        super().__init__(config, device)

    @override
    def step(self, actor_state):
        """Apply the canonical bank-start arm release before DeltaActionBase accumulation."""

        if self._is_a2_pull_v6():
            self._a2_pull_v6_pre_action_arm_delta_targets[:] = self._delta_actions
        if self._a2_pull_stage3_taskspace_action_enabled:
            actor_state = self._apply_a2_pull_stage3_taskspace_action(actor_state)
        if not self._is_a2_pull_v5():
            return super().step(actor_state)
        enabled = self.config.get("a2_pull_v5_start_override_enabled", False)
        if not isinstance(enabled, bool):
            raise RuntimeError("a2_pull_v5_start_override_enabled must be bool.")
        steps = self.config.get("a2_pull_v5_start_override_steps", A2_PULL_V5_START_OVERRIDE_STEPS)
        if isinstance(steps, bool) or not isinstance(steps, int):
            raise RuntimeError("a2_pull_v5_start_override_steps must be an integer.")
        if enabled and steps != A2_PULL_V5_START_OVERRIDE_STEPS:
            raise RuntimeError(
                "a2_pull_v5_start_override_steps must be exactly 50 when enabled; "
                f"got {steps!r}."
            )
        if not enabled:
            self._a2_pull_v5_start_override_active[:] = False
            return super().step(actor_state)

        actions = actor_state["actions"]
        expected_dim = self._a2_high_level_action_dim + self._a2_leg_action_dim
        if (
            not torch.is_tensor(actions)
            or tuple(actions.shape) != (self.num_envs, expected_dim)
            or actions.device != torch.device(self.device)
            or not actions.is_floating_point()
            or not torch.all(torch.isfinite(actions))
        ):
            raise RuntimeError(
                "Pull-v5 start override requires a finite device-local trainer action with "
                f"shape ({self.num_envs}, {expected_dim})."
            )
        if tuple(self._delta_actions.shape) != (self.num_envs, 6):
            raise RuntimeError(
                "Pull-v5 start override requires cumulative arm state shape "
                f"({self.num_envs}, 6); got {tuple(self._delta_actions.shape)}."
            )
        if not isinstance(self._delta_action_scale, (int, float)) or self._delta_action_scale <= 0.0:
            raise RuntimeError("Pull-v5 start override requires a positive delta_action_scale.")

        reset_source = torch.tensor(
            [source == "bank_natural_e5_override" for source in self._a2_pull_v5_reset_source],
            dtype=torch.bool,
            device=self.device,
        )
        episode_step = self.episode_length_buf.to(dtype=torch.long)
        in_window = (episode_step >= 0) & (episode_step < steps)
        requested = torch.full_like(reset_source, enabled) & reset_source
        active = requested & in_window
        self._a2_pull_v5_start_override_active[:] = active
        self._a2_pull_v5_start_override_active_steps += active.long()
        self._a2_pull_v5_start_override_outside_window |= active & ~in_window

        applied_actions = actions.clone()
        if torch.any(active):
            applied_actions[active, 5:11] = (
                -self._delta_actions[active] / float(self._delta_action_scale)
            )
            applied_actions[active, 11] = 1.0
            base_equal = torch.all(applied_actions[:, :5] == actions[:, :5], dim=-1)
            self._a2_pull_v5_start_override_base_slice_equal &= torch.where(
                active, base_equal, torch.ones_like(base_equal)
            )

        next_actor_state = dict(actor_state)
        next_actor_state["actions"] = applied_actions
        return super().step(next_actor_state)

    def _apply_a2_pull_stage3_taskspace_action(self, actor_state):
        actions = actor_state["actions"]
        expected_dim = self._a2_high_level_action_dim + self._a2_leg_action_dim
        if (
            not torch.is_tensor(actions)
            or tuple(actions.shape) != (self.num_envs, expected_dim)
            or not actions.is_floating_point()
            or actions.device != torch.device(self.device)
            or not torch.all(torch.isfinite(actions))
        ):
            raise RuntimeError(
                "Stage3 task-space executor requires finite trainer actions "
                f"shape ({self.num_envs},{expected_dim}) on {self.device}."
            )
        stage3 = self.stage_buf == self.STAGE_OPEN
        active = (
            stage3
            if self._a2_pull_stage3_taskspace_side_mode == "bilateral_canonical"
            else stage3 & (self.door_open_lr == 1.0)
        )
        self._a2_pull_stage3_taskspace_active[:] = active
        self._a2_pull_stage3_taskspace_raw.zero_()
        self._a2_pull_stage3_taskspace_scaled.zero_()
        self._a2_pull_stage3_taskspace_joint_raw.zero_()
        self._a2_pull_stage3_taskspace_predicted_twist.zero_()
        self._a2_pull_stage3_taskspace_commanded_root_twist.zero_()
        self._a2_pull_stage3_taskspace_relative_residual.zero_()
        self._a2_pull_stage3_taskspace_condition.fill_(float("nan"))
        if not torch.any(active):
            return actor_state

        arm_slice = slice(5, 11)
        raw_twist = torch.clamp(actions[:, arm_slice], min=-1.0, max=1.0)
        physical_twist = raw_twist.clone()
        scaled_twist = torch.zeros_like(physical_twist)
        scaled_twist[:, :3] = physical_twist[:, :3] * float(
            self.config.a2_pull_stage3_taskspace_translation_scale_m
        )
        scaled_twist[:, 3:] = physical_twist[:, 3:] * float(
            self.config.a2_pull_stage3_taskspace_rotation_scale_rad
        )
        scaled_twist[~active] = 0.0

        piper = self._get_a2_v20_piper_frame_data(
            "Stage3 task-space action"
        )
        handle_pos_w = piper["target_pos_w"][:, 0, :]
        handle_quat_w = piper["target_quat_w"][:, 0, :]
        source_pos_w = piper["source_pos_w"]
        source_quat_w = piper["source_quat_w"]
        source_pos_handle, source_quat_handle = subtract_frame_transforms(
            handle_pos_w,
            handle_quat_w,
            source_pos_w,
            source_quat_w,
        )
        target_pos_handle, target_quat_handle = apply_delta_pose(
            source_pos_handle,
            source_quat_handle,
            scaled_twist,
        )
        target_pos_w, target_quat_w = combine_frame_transforms(
            handle_pos_w,
            handle_quat_w,
            target_pos_handle,
            target_quat_handle,
        )

        robot = self.simulator.scene.articulations["robot"]
        root_pos_w = robot.data.root_pos_w
        root_quat_w = robot.data.root_quat_w
        body_pos_w = robot.data.body_pos_w[:, self._a2_pull_stage3_taskspace_body_id]
        body_quat_w = robot.data.body_quat_w[:, self._a2_pull_stage3_taskspace_body_id]
        source_pos_root, source_quat_root = subtract_frame_transforms(
            root_pos_w, root_quat_w, source_pos_w, source_quat_w
        )
        body_pos_root, _ = subtract_frame_transforms(
            root_pos_w, root_quat_w, body_pos_w, body_quat_w
        )
        target_pos_root, target_quat_root = subtract_frame_transforms(
            root_pos_w, root_quat_w, target_pos_w, target_quat_w
        )
        jacobian = robot.root_physx_view.get_jacobians()[
            :,
            self._a2_pull_stage3_taskspace_body_id,
            :,
            self._a2_pull_stage3_taskspace_jacobian_joint_ids,
        ]
        if tuple(jacobian.shape) != (self.num_envs, 6, 6) or not torch.all(
            torch.isfinite(jacobian)
        ):
            raise RuntimeError(
                "Stage3 task-space executor requires a finite (N,6,6) Jacobian."
            )
        jacobian_root = a2_hold_rotate_jacobian_to_root(jacobian, root_quat_w)
        jacobian_root = a2_hold_apply_source_offset_to_jacobian(
            jacobian_root, source_pos_root - body_pos_root
        )
        singular_values = torch.linalg.svdvals(jacobian_root)
        condition = singular_values[:, 0] / singular_values[:, -1]
        command = torch.cat((target_pos_root, target_quat_root), dim=-1)
        self._a2_pull_stage3_taskspace_controller.set_command(command)
        joint_ids = self._a2_pull_stage3_taskspace_joint_ids
        q_current = robot.data.joint_pos[:, joint_ids]
        q_dls = self._a2_pull_stage3_taskspace_controller.compute(
            source_pos_root,
            source_quat_root,
            jacobian_root,
            q_current,
        )
        if not torch.all(torch.isfinite(q_dls)):
            raise RuntimeError("Stage3 task-space DLS returned non-finite joint targets.")
        joint_step_max = float(
            self.config.a2_pull_stage3_taskspace_joint_step_max_rad
        )
        correction = torch.clamp(
            q_dls - q_current, min=-joint_step_max, max=joint_step_max
        )

        hard_limits = robot.data.joint_pos_limits[:, joint_ids]
        soft_limits = robot.data.soft_joint_pos_limits[:, joint_ids]
        margin = 1.0e-4
        hard_lower = hard_limits[..., 0] + margin
        hard_upper = hard_limits[..., 1] - margin
        soft_lower = soft_limits[..., 0] + margin
        soft_upper = soft_limits[..., 1] - margin
        for lower, upper in ((hard_lower, hard_upper), (soft_lower, soft_upper)):
            correction = torch.where(
                (q_current < lower) & (correction < 0.0),
                torch.zeros_like(correction),
                correction,
            )
            correction = torch.where(
                (q_current > upper) & (correction > 0.0),
                torch.zeros_like(correction),
                correction,
            )
            inside = (q_current >= lower) & (q_current <= upper)
            projected = torch.clamp(q_current + correction, min=lower, max=upper)
            correction = torch.where(inside, projected - q_current, correction)
        q_target = q_current + correction
        hard_progress_valid = torch.where(
            (q_current >= hard_lower) & (q_current <= hard_upper),
            (q_target >= hard_lower) & (q_target <= hard_upper),
            torch.where(
                q_current < hard_lower,
                q_target >= q_current,
                q_target <= q_current,
            ),
        )
        soft_progress_valid = torch.where(
            (q_current >= soft_lower) & (q_current <= soft_upper),
            (q_target >= soft_lower) & (q_target <= soft_upper),
            torch.where(
                q_current < soft_lower,
                q_target >= q_current,
                q_target <= q_current,
            ),
        )
        limit_valid = torch.all(
            hard_progress_valid & soft_progress_valid, dim=-1
        )
        q_default = robot.data.default_joint_pos[:, joint_ids]
        if q_default.shape[0] == 1:
            q_default = q_default.repeat(self.num_envs, 1)
        d_des, converted_joint_raw = a2_hold_absolute_target_to_cumulative_action(
            q_target, q_default, self._delta_actions.clone()
        )
        delta_valid = torch.all(
            torch.abs(d_des) <= float(self.config.delta_action_clip), dim=-1
        )
        raw_valid = torch.all(
            torch.abs(converted_joint_raw)
            <= float(self.config.a2_pull_stage3_taskspace_raw_action_abs_max),
            dim=-1,
        )
        finite_valid = (
            torch.all(torch.isfinite(singular_values), dim=-1)
            & torch.isfinite(condition)
            & torch.all(torch.isfinite(converted_joint_raw), dim=-1)
        )
        invalid = active & ~(
            finite_valid & limit_valid & delta_valid & raw_valid
        )
        if torch.any(invalid):
            env_ids = torch.where(invalid)[0]
            raise RuntimeError(
                "Stage3 task-space executor rejected active rows: "
                f"env_ids={env_ids.tolist()}, "
                f"finite_invalid={env_ids[~finite_valid[env_ids]].tolist()}, "
                f"limit_invalid={env_ids[~limit_valid[env_ids]].tolist()}, "
                f"delta_invalid={env_ids[~delta_valid[env_ids]].tolist()}, "
                f"raw_invalid={env_ids[~raw_valid[env_ids]].tolist()}, "
                f"side={self.door_open_lr[env_ids].tolist()}, "
                f"policy_twist={raw_twist[env_ids].tolist()}, "
                f"condition={condition[env_ids].tolist()}, "
                f"converted_joint_raw={converted_joint_raw[env_ids].tolist()}."
            )

        position_delta_root = target_pos_root - source_pos_root
        orientation_delta_root = axis_angle_from_quat(
            quat_mul(target_quat_root, quat_inv(source_quat_root))
        )
        commanded_twist_root = torch.cat(
            (position_delta_root, orientation_delta_root), dim=-1
        )
        predicted_twist = torch.bmm(
            jacobian_root, correction.unsqueeze(-1)
        ).squeeze(-1)
        command_norm = torch.linalg.vector_norm(commanded_twist_root, dim=-1)
        residual = torch.linalg.vector_norm(
            predicted_twist - commanded_twist_root, dim=-1
        ) / command_norm.clamp_min(torch.finfo(command_norm.dtype).eps)

        applied_actions = actions.clone()
        applied_actions[active, arm_slice] = converted_joint_raw[active]
        self._a2_pull_stage3_taskspace_raw[active] = raw_twist[active]
        self._a2_pull_stage3_taskspace_scaled[active] = scaled_twist[active]
        self._a2_pull_stage3_taskspace_joint_raw[active] = converted_joint_raw[active]
        self._a2_pull_stage3_taskspace_predicted_twist[active] = predicted_twist[active]
        self._a2_pull_stage3_taskspace_commanded_root_twist[active] = (
            commanded_twist_root[active]
        )
        self._a2_pull_stage3_taskspace_relative_residual[active] = residual[active]
        self._a2_pull_stage3_taskspace_condition[active] = condition[active]
        self._a2_pull_stage3_taskspace_action_count[active] += 1
        self.log_dict["a2_pull_stage3_taskspace_active_count"] = active.float().sum()
        self.log_dict["a2_pull_stage3_taskspace_left_active_count"] = (
            active & (self.door_open_lr == 1.0)
        ).float().sum()
        self.log_dict["a2_pull_stage3_taskspace_right_active_count"] = (
            active & (self.door_open_lr == -1.0)
        ).float().sum()
        self.log_dict["a2_pull_stage3_taskspace_nonzero_count"] = (
            active & (torch.linalg.vector_norm(scaled_twist, dim=-1) > 0.0)
        ).float().sum()
        self.log_dict["a2_pull_stage3_taskspace_relative_residual_mean"] = (
            residual[active].mean()
        )
        next_actor_state = dict(actor_state)
        next_actor_state["actions"] = applied_actions
        return next_actor_state

    @override
    def _check_termination(self):
        super()._check_termination()
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if cfg is not None and cfg.get("v6_p1_oracle_enabled", False):
            oracle_failure = (
                (self._a2_pull_v6_p1_phase == 1)
                & self._a2_hold_oracle_activated
                & (self._a2_hold_oracle_outcome != A2_HOLD_OUTCOME_TO_ID["PENDING"])
            )
            self._mark_terminal_reason("stage_overtime", oracle_failure)
            self.reset_buf |= oracle_failure
            pending = (self._a2_pull_v6_p1_phase == 1) | (
                self._a2_pull_v6_p1_phase == 2
            ) | (self._a2_pull_v6_p1_phase == 3)
            timeout = pending & (
                self._a2_pull_v6_p1_steps >= cfg["v6_p1_phase_timeout_steps"]
            )
            self._mark_terminal_reason("stage_overtime", timeout)
            self.reset_buf |= timeout
        if getattr(self, "_a2_pull_v5_scheduler_enabled", False):
            (
                updated_reset,
                updated_stage_overtime,
                _scheduler_terminal,
                non_scheduler_terminal,
            ) = _a2_pull_v5_scheduler_termination(
                self.reset_buf,
                self._terminal_reason_bufs,
                self._a2_pull_v5_scheduler_episode_indices,
                self._a2_pull_v5_scheduler_state,
                self._A2_PULL_V5_4_SCHEDULER_STATES,
            )
            self.reset_buf[:] = updated_reset
            self._terminal_reason_bufs["stage_overtime"][:] = updated_stage_overtime
            if torch.any(non_scheduler_terminal):
                failed_state = self._A2_PULL_V5_4_SCHEDULER_STATES["FAILED"]
                self._a2_pull_v5_scheduler_state[non_scheduler_terminal] = failed_state
                for env_id in torch.where(non_scheduler_terminal)[0].tolist():
                    reasons = "+".join(
                        name
                        for name, reason_buf in self._terminal_reason_bufs.items()
                        if name != "stage_overtime" and bool(reason_buf[env_id].item())
                    )
                    if not reasons:
                        raise RuntimeError(
                            "Pull-v5.4 scheduler non-scheduler termination has no terminal reason."
                        )
                    self._a2_pull_v5_scheduler_failure_reason[env_id] = (
                        f"non_scheduler_terminal:{reasons}"
                    )
                self._mark_a2_pull_v5_scheduler_trace_failures(non_scheduler_terminal)
        if not self._a2_pull_v5_characterization_enabled:
            return
        contract = self._get_a2_pull_v5_characterization_contract()
        updated_reset, updated_stage_overtime, diagnostic_done = (
            _a2_pull_v5_characterization_termination(
                self.reset_buf,
                self._terminal_reason_bufs,
                self._a2_pull_v5_characterization_active,
                self.episode_length_buf,
                int(contract["window_steps"]),
            )
        )
        self.reset_buf[:] = updated_reset
        self._terminal_reason_bufs["stage_overtime"][:] = updated_stage_overtime
        self._mark_terminal_reason("complete", diagnostic_done)
        self.reset_buf |= diagnostic_done.to(dtype=self.reset_buf.dtype)

    def _is_a2_pull_v5(self) -> bool:
        return self.config.get("a2_v20_R1_plan_id") == A2_PULL_V5_PLAN_ID

    def _is_a2_pull_v6(self) -> bool:
        return self.config.get("a2_v20_R1_plan_id") == A2_PULL_V6_PLAN_ID

    def _get_a2_pull_stage3_e3_snapshot_curriculum_enabled(self) -> bool:
        enabled = self.config.get(
            "a2_pull_stage3_e3_snapshot_curriculum_enabled", False
        )
        if not isinstance(enabled, bool):
            raise RuntimeError(
                "a2_pull_stage3_e3_snapshot_curriculum_enabled must be a boolean."
            )
        return enabled

    def _is_a2_pull_v3(self) -> bool:
        return self.config.get("a2_v20_R1_plan_id") == A2_PULL_V3_PLAN_ID

    def _is_a2_pull_v4(self) -> bool:
        return self.config.get("a2_v20_R1_plan_id") == A2_PULL_V4_PLAN_ID

    def _is_a2_pull_traversal(self) -> bool:
        return self._is_a2_pull_v3() or self._is_a2_pull_v4() or self._is_a2_pull_v5() or self._is_a2_pull_v6()

    def _get_a2_pull_threshold_mode(self) -> str:
        mode = self.config.get("a2_pull_threshold_mode")
        if mode not in ("report_only", "hard_gate"):
            raise RuntimeError(
                "Pull threshold mode must be exactly 'report_only' or 'hard_gate'; "
                f"got {mode!r}."
            )
        return mode

    def _get_a2_pull_e3_latch_threshold_m(self) -> float:
        return self._get_required_positive_float_config(
            "a2_pull_e3_latch_threshold_m",
            "pull E3 latch release telemetry",
        )

    @override
    def _get_a2_grasp_target_orientation_wxyz(self) -> tuple[float, float, float, float]:
        configured = self.config.get("a2_pull_target_orientation_wxyz")
        expected = (
            A2_PULL_V0_TARGET_ORIENTATION_WXYZ
            if self._pull_direction.door_open_io == "in"
            else self.A2_PUSH_ANCHOR_TARGET_ORIENTATION_WXYZ
        )
        if configured is None or tuple(float(value) for value in configured) != expected:
            raise RuntimeError(
                "Pull-v0 target orientation must match the direction-selected overlay "
                f"{expected}; got {configured!r}."
            )
        return expected

    @override
    def _init_door_metadata(self):
        super()._init_door_metadata()
        self.door_open_io.fill_(float(self._pull_direction.io_sign))

    @override
    def _init_buffers(self):
        super()._init_buffers()
        door_articulation = self.simulator.scene.articulations["door"]
        door_panel_body_ids, door_panel_body_names = door_articulation.find_bodies(
            "door_panel", preserve_order=True
        )
        if door_panel_body_names != ["door_panel"] or len(door_panel_body_ids) != 1:
            raise RuntimeError(
                "Pull clearance requires exactly one door_panel articulation body; "
                f"got ids={door_panel_body_ids!r}, names={door_panel_body_names!r}."
            )
        robot_articulation = self.simulator.scene.articulations["robot"]
        trunk_body_ids, trunk_body_names = robot_articulation.find_bodies(
            "trunk", preserve_order=True
        )
        if trunk_body_names != ["trunk"] or len(trunk_body_ids) != 1:
            raise RuntimeError(
                "Pull clearance requires exactly one trunk articulation body; "
                f"got ids={trunk_body_ids!r}, names={trunk_body_names!r}."
            )
        self._a2_pull_door_panel_body_id = door_panel_body_ids[0]
        self._a2_pull_trunk_body_id = trunk_body_ids[0]
        self._a2_pull_event_reached = torch.zeros(
            self.num_envs,
            len(A2PullEvent),
            dtype=torch.bool,
            device=self.device,
        )
        self._a2_pull_stage3_e3_manual_snapshot_count = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_stage3_e3_loaded_snapshot_count = torch.zeros(
            (), dtype=torch.long, device=self.device
        )
        self._a2_pull_stable_unlatch_handle_ever = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_stable_unlatch_latch_ever = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_relock_handle_ever = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_relock_latch_ever = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_prev_handle_unlatched = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_prev_latch_unlatched = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_first_event_step = torch.full(
            (self.num_envs, len(A2PullEvent)),
            -1,
            dtype=torch.long,
            device=self.device,
        )
        self._a2_pull_first_event_time_s = torch.full(
            (self.num_envs, len(A2PullEvent)),
            float("nan"),
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_capture_root_x = torch.full(
            (self.num_envs,),
            float("nan"),
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_capture_valid = torch.zeros(
            self.num_envs,
            dtype=torch.bool,
            device=self.device,
        )
        self._a2_pull_max_tensile_retreat_m = torch.zeros(
            self.num_envs,
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_release_or_hold_decision = torch.zeros(
            self.num_envs,
            dtype=torch.bool,
            device=self.device,
        )
        self._a2_pull_proof_active = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_proof_start_root_x = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_proof_last_root_x = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_proof_duration_s = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_proof_displacement_m = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_proof_streak = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_proof_valid = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_minimum_panel_robot_clearance_m = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_clearance_ready = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_aperture_ready = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_passage = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_passage_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_planar_crossing = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_planar_crossing_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_detour = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_approach = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_approach_active = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_approach_pre_aperture_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_frame_approach_post_frame_passage_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_frame_midpoint_distance_min_m = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_deliberate_release = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_deliberate_release_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_first_negative_x_motion_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_prev_stable_contact = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_prev_panel_contact = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_post_release_recontact_count = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_base_path_length_m = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_prev_base_pos_xy = torch.full(
            (self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_base_reversal_count = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_prev_travel_velocity = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_swept_arc_clearance_margin_current_m = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_swept_arc_clearance_margin_min_m = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_corridor_door_wide_pre_aperture_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_corridor_clean_passage_pre_aperture_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_stage0_staging_band = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_stage0_arm_default = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_stage0_base_still = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_first_scripted_activation_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_hinge_at_first_positive_progress_rad = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_held_hinge_max_rad = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_hinge_at_decision_rad = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_root_outward_excursion_m = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_first_path_reversal_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_body_panel_contact_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_body_panel_contact_impulse_ns = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_prev_handle_to_tcp_pos = torch.full(
            (self.num_envs, 3),
            float("nan"),
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_handle_local_slip_xyz_mps = torch.full(
            (self.num_envs, 3),
            float("nan"),
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_handle_local_slip_valid = torch.zeros(
            self.num_envs,
            dtype=torch.bool,
            device=self.device,
        )
        self._a2_pull_passage_attempt_hinge_rad = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_last_raw_reward_components: dict[str, torch.Tensor] = {}
        self._a2_pull_runtime_telemetry_contract_checked = False
        self._a2_pull_runtime_telemetry_contract_sample: list[dict] = []
        if self._is_a2_pull_v6():
            self._a2_pull_v6_subphase = torch.zeros(self.num_envs, dtype=torch.long, device=self.device)
            self._a2_pull_v6_pivot_xy = torch.full((self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_pivot_valid = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_handle_y_capture = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_handle_y_current = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_handle_y_prev = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_handle_y_best = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_handle_side_progress = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_handle_crossed = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_handle_cross_bonus = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_release_side_qualified = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_handoff_active = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_handoff_reached = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_handoff_active_steps = torch.zeros(self.num_envs, dtype=torch.long, device=self.device)
            self._a2_pull_v6_handoff_reward_window = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_handle_to_tcp_capture_pos = torch.zeros((self.num_envs, 3), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_handle_to_tcp_capture_quat = torch.zeros((self.num_envs, 4), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_handle_to_tcp_capture_quat[:, 0] = 1.0
            self._a2_pull_v6_handle_to_tcp_valid = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_prev_tcp_pos_w = torch.full((self.num_envs, 3), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_prev_tcp_valid = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_positive_arm_tangent = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_positive_base_tangent = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_positive_total_tangent = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_instantaneous_arm_tangent_share = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_arm_tangent_integral_m = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_total_tangent_integral_m = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_arm_tangent_share = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_last_held_arm_tangent_share = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_arc_error_m = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_arc_quality = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_pivot_displacement_m = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_workspace_margin = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_workspace_margin_progress = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v6_workspace_margin_progress_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_frame_lateral_delta_y_m = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v6_frame_lateral_deficit_m = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v6_frame_passage_ready = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_pre_release_except_passage = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_passage_alignment_progress = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v6_passage_alignment_progress_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_passage_command_alignment = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v6_passage_command_alignment_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_post_release_lateral_command_alignment = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v6_post_release_lateral_command_alignment_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_post_release_arm_tuck_progress = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v6_post_release_arm_tuck_progress_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_pre_action_arm_delta_targets = torch.zeros(
                (self.num_envs, 6), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v6_release_action_started_ready = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_release_ready = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_prev_release_ready = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_release_event = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_clean_release = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_premature_release = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_clean_release_event = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_premature_release_event = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_release_quality = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
            self._a2_pull_v6_release_persistence = torch.zeros(self.num_envs, dtype=torch.long, device=self.device)
            self._a2_pull_v61_post_release_control_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_persistence_income_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_persistence_income_consumed = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_persistence_recontact_event = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_hinge_at_release = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_hinge_velocity_at_release = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_root_yaw_at_capture = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_root_yaw_delta = torch.full((self.num_envs,), float("nan"), dtype=torch.float32, device=self.device)
            self._a2_pull_v6_prev_bilateral_contact = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            self._a2_pull_v6_e5_snapshot_pending = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_pre_release_snapshot_pending = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_d1_snapshot_captured = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_d5_snapshot_captured = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_d25_snapshot_captured = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v61_clean_release_step = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            self._a2_pull_v61_hinge_running_peak_after_release = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v61_hinge_reclosure_after_release_rad = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v61_e6_event_pulse = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v61_e7_event_pulse = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v61_d25_snapshot_captured = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v61_frame_snapshot_captured = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v61_e6_snapshot_captured = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v61_d25_snapshot_slot = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            self._a2_pull_v61_frame_snapshot_slot = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            self._a2_pull_v61_e6_snapshot_slot = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            self._a2_pull_v61_d25_snapshot_step = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            self._a2_pull_v61_frame_snapshot_step = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            self._a2_pull_v61_e6_snapshot_step = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            capture_path = self.config.get("a2_pull_v61_late_state_bank_capture_path")
            if capture_path is not None and (not isinstance(capture_path, str) or not capture_path):
                raise RuntimeError("Pull-v6.1 late-state bank capture path must be a non-empty string when supplied.")
            self._a2_pull_v61_late_state_bank_capture_enabled = capture_path is not None
            capture_target = self.config.get("a2_pull_v61_late_state_bank_capture_target_env_id")
            capture_checkpoint = self.config.get("a2_pull_v61_late_state_bank_capture_source_checkpoint")
            capture_config = self.config.get("a2_pull_v61_late_state_bank_capture_source_config")
            capture_overlay_base = self.config.get("a2_pull_v61_late_state_bank_overlay_base_path")
            if capture_overlay_base is not None and (
                not isinstance(capture_overlay_base, str) or not capture_overlay_base
            ):
                raise RuntimeError("Pull-v6.1 late-state overlay base path must be a non-empty string when supplied.")
            if self._a2_pull_v61_late_state_bank_capture_enabled:
                if (
                    isinstance(capture_target, bool)
                    or not isinstance(capture_target, int)
                    or not 0 <= capture_target < self.num_envs
                    or not isinstance(capture_checkpoint, str)
                    or not capture_checkpoint
                    or not isinstance(capture_config, str)
                    or not capture_config
                ):
                    raise RuntimeError(
                        "Pull-v6.1 late-state capture requires target env, source checkpoint, and source config provenance."
                    )
            elif any(value is not None for value in (capture_target, capture_checkpoint, capture_config)):
                raise RuntimeError("Pull-v6.1 late-state capture provenance requires an explicit capture path.")
            if capture_overlay_base is not None and not self._a2_pull_v61_late_state_bank_capture_enabled:
                raise RuntimeError("Pull-v6.1 late-state overlay requires an explicit capture path.")
            self._a2_pull_v61_late_state_bank_capture_target_env_id = capture_target
            self._a2_pull_v61_late_state_bank_capture_source_checkpoint = capture_checkpoint
            self._a2_pull_v61_late_state_bank_capture_source_config = capture_config
            self._a2_pull_v61_late_state_bank_overlay_base_path = capture_overlay_base
            self._a2_pull_v61_late_state_bank_enabled = False
            self._a2_pull_v6_stage4_bank_loaded = False
            self._a2_pull_v6_broadcast_first_natural_c_enabled = self.config.get(
                "a2_pull_v6_broadcast_first_natural_c_enabled", False
            )
            if not isinstance(self._a2_pull_v6_broadcast_first_natural_c_enabled, bool):
                raise RuntimeError(
                    "Pull-v6 first-natural-C broadcast enablement must be an explicit bool."
                )
            self._a2_pull_v6_first_natural_c_broadcast_done = False
            self._a2_pull_v6_near_c_capture_mode = self.config[
                "a2_pull_v6_near_c_capture_mode"
            ]
            if self._a2_pull_v6_near_c_capture_mode not in {
                "none",
                "workspace_missing",
                "handle_side_missing",
            }:
                raise RuntimeError(
                    "Pull-v6 near-C capture mode must be none, workspace_missing, "
                    "or handle_side_missing."
                )
            self._a2_pull_v6_near_c_snapshot_pending = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_near_c_snapshot_captured = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v6_near_c_snapshot_slot = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
        if self._is_a2_pull_v5():
            self._a2_pull_v5_persistent_release_streak = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_persistent_release = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_intervention_elapsed_steps = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_intervention_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_intervention_fired = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_start_override_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_start_override_active_steps = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_start_override_base_slice_equal = torch.ones(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_start_override_outside_window = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_solvable = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_anchor_initialized = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_waypoint_target_xy = torch.full(
                (self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_yaw_target = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_original_yaw_target = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_waypoint_error_m = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_yaw_error_rad = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_waypoint_arrived = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_yaw_arrived = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_anchor_pass = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_phase_index = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_probe_phase_initialized = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_phase_waypoint_arrived = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_phase_yaw_arrived = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_sequence_complete = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_scheduler_enabled = self.config.get(
                "a2_pull_v5_scheduler_enabled", False
            )
            if not isinstance(self._a2_pull_v5_scheduler_enabled, bool):
                raise RuntimeError("Pull-v5.4 scheduler_enabled must be bool.")
            self._a2_pull_v5_scheduler_state = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_scheduler_coarse_raw = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_scheduler_cutoff = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_scheduler_min_settle_steps = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_scheduler_settle_steps = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_scheduler_trim_steps = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_scheduler_terminal_hold_steps = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_scheduler_raw_yaw_command = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_scheduler_failure_reason = [
                None for _ in range(self.num_envs)
            ]
            self._a2_pull_v5_scheduler_episode_indices = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_scheduler_trace_rows: list[dict[str, object]] = []
            self._a2_pull_v5_probe_sequence_id: str | None = None
            self._a2_pull_v5_probe_sequence_phases: tuple[str, ...] = ()
            self._a2_pull_v5_capture_e5_seen = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_capture_pending = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_capture_recorded = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_capture_target_step = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_source_b_capture_frozen = False
            declared_reset_source = self.config.get("a2_pull_v5_reset_source", "natural")
            if declared_reset_source not in A2_PULL_V5_RESET_SOURCES:
                raise RuntimeError(
                    "Pull-v5 declared reset_source must be one of "
                    f"{A2_PULL_V5_RESET_SOURCES!r}; got {declared_reset_source!r}."
                )
            self._a2_pull_v5_declared_reset_source = [
                str(declared_reset_source) for _ in range(self.num_envs)
            ]
            self._a2_pull_v5_reset_source = ["natural" for _ in range(self.num_envs)]
            self._a2_pull_v5_pending_reset_source = ["natural" for _ in range(self.num_envs)]
            self._a2_pull_v5_bank_slot_sources: list[str] = []
            self._a2_pull_v5_bank_slot_indices: list[int] = []
            self._a2_pull_v5_bank_metadata: dict[str, object] = {}
            self._a2_pull_v5_bank_eval_indices: list[int] = []
            self._a2_pull_v5_bank_cursor = 0
            self._a2_pull_v5_bank_loaded = False

        characterization_enabled = self.config.get(
            "a2_pull_v5_characterization_enabled", False
        )
        if not isinstance(characterization_enabled, bool):
            raise RuntimeError("a2_pull_v5_characterization_enabled must be bool.")
        if characterization_enabled and not self._is_a2_pull_v5():
            raise RuntimeError("HOMIE characterization requires the v5 plan guard.")
        self._a2_pull_v5_characterization_enabled = characterization_enabled
        self._a2_pull_v5_characterization_pending = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v5_characterization_active = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v5_characterization_xy_target_initialized = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v5_characterization_xy_target = torch.full(
            (self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_episode_indices = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_v5_characterization_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_v5_characterization_requested_u = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_phase_u = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_raw_base = torch.zeros(
            self.num_envs, 5, dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_physical_base = torch.zeros(
            self.num_envs, 5, dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_pre_root_pos = torch.full(
            (self.num_envs, 3), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_pre_root_yaw = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_phase = ["inactive" for _ in range(self.num_envs)]
        self._a2_pull_v5_characterization_trace_rows: list[dict[str, object]] = []
        self._init_a2_pull_stage3_taskspace_executor()

    def _init_a2_pull_stage3_taskspace_executor(self) -> None:
        enabled = self.config.get("a2_pull_stage3_taskspace_action_enabled", False)
        if not isinstance(enabled, bool):
            raise RuntimeError("a2_pull_stage3_taskspace_action_enabled must be bool.")
        self._a2_pull_stage3_taskspace_action_enabled = enabled
        if not enabled:
            return
        side_mode = self.config.get("a2_pull_stage3_taskspace_side_mode")
        if side_mode not in {"left", "bilateral_canonical"}:
            raise RuntimeError(
                "a2_pull_stage3_taskspace_side_mode must be left or bilateral_canonical."
            )
        self._a2_pull_stage3_taskspace_side_mode = side_mode
        if not self._is_a2_pull_v6():
            raise RuntimeError("Stage3 task-space actions require the pull-v6 plan.")
        exact = {
            "a2_pull_stage3_taskspace_translation_scale_m": (
                0.004 if side_mode == "bilateral_canonical" else 0.008
            ),
            "a2_pull_stage3_taskspace_rotation_scale_rad": (
                0.04 if side_mode == "bilateral_canonical" else 0.08
            ),
            "a2_pull_stage3_taskspace_dls_lambda": 0.01,
            "a2_pull_stage3_taskspace_joint_step_max_rad": 0.05,
            "a2_pull_stage3_taskspace_raw_action_abs_max": (
                12.0 if side_mode == "bilateral_canonical" else 10.0
            ),
        }
        mismatched = {
            key: (float(self.config[key]), expected)
            for key, expected in exact.items()
            if float(self.config[key]) != expected
        }
        if mismatched:
            raise RuntimeError(
                f"Stage3 task-space executor requires its preregistered tuple: {mismatched}."
            )
        robot = self.simulator.scene.articulations["robot"]
        body_ids, body_names = robot.find_bodies(
            "arm_body6_to_gripper", preserve_order=True
        )
        if len(body_ids) != 1 or body_names != ["arm_body6_to_gripper"]:
            raise RuntimeError(
                "Stage3 task-space executor requires exactly one arm_body6_to_gripper."
            )
        joint_ids, joint_names = robot.find_joints(
            [f"arm_j{i}" for i in range(1, 7)], preserve_order=True
        )
        if joint_names != [f"arm_j{i}" for i in range(1, 7)]:
            raise RuntimeError(
                f"Stage3 task-space executor arm joint order mismatch: {joint_names}."
            )
        self._a2_pull_stage3_taskspace_body_id = body_ids[0]
        self._a2_pull_stage3_taskspace_joint_ids = joint_ids
        self._a2_pull_stage3_taskspace_jacobian_joint_ids = [
            joint_id + 6 for joint_id in joint_ids
        ]
        self._a2_pull_stage3_taskspace_controller = DifferentialIKController(
            DifferentialIKControllerCfg(
                command_type="pose",
                use_relative_mode=False,
                ik_method="dls",
                ik_params={
                    "lambda_val": self.config[
                        "a2_pull_stage3_taskspace_dls_lambda"
                    ]
                },
            ),
            num_envs=self.num_envs,
            device=self.device,
        )
        self._a2_pull_stage3_taskspace_active = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_stage3_taskspace_raw = torch.zeros(
            self.num_envs, 6, dtype=torch.float32, device=self.device
        )
        self._a2_pull_stage3_taskspace_scaled = torch.zeros_like(
            self._a2_pull_stage3_taskspace_raw
        )
        self._a2_pull_stage3_taskspace_joint_raw = torch.zeros_like(
            self._a2_pull_stage3_taskspace_raw
        )
        self._a2_pull_stage3_taskspace_predicted_twist = torch.zeros_like(
            self._a2_pull_stage3_taskspace_raw
        )
        self._a2_pull_stage3_taskspace_commanded_root_twist = torch.zeros_like(
            self._a2_pull_stage3_taskspace_raw
        )
        self._a2_pull_stage3_taskspace_relative_residual = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_stage3_taskspace_condition = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_stage3_taskspace_action_count = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )

    @override
    def _init_a2_door_pregrasp_state(self):
        super()._init_a2_door_pregrasp_state()
        if self._get_a2_pull_stage3_e3_snapshot_curriculum_enabled():
            if not self._is_a2_pull_v6():
                raise RuntimeError(
                    "LEFT Stage-3 E3 snapshot curriculum requires the pull-v6 plan."
                )
            if not self.enable_staged_reset:
                raise RuntimeError(
                    "LEFT Stage-3 E3 snapshot curriculum requires staged reset."
                )
        if self.config.get("a2_pull_v5_census_enabled", False) and "a2_pull_prev_stable_contact" not in self.staged_reset_buf:
            self._register_buffer_to_track(
                "a2_pull_prev_stable_contact",
                tuple(self._a2_pull_prev_stable_contact.shape),
                lambda env_ids: self._a2_pull_prev_stable_contact[env_ids].clone(),
                lambda env_ids, data: self._load_a2_pull_named_buffer(
                    "a2_pull_prev_stable_contact", env_ids, data
                ),
                dtype=self._a2_pull_prev_stable_contact.dtype,
            )
        if self._is_a2_pull_v6():
            self._register_a2_pull_v6_staged_reset_buffers()
            bank_enabled = self.config.get("a2_pull_v6_stage4_bank_enabled", False)
            if not isinstance(bank_enabled, bool):
                raise RuntimeError("Pull-v6 Stage-4 bank enablement must be an explicit bool.")
            bank_row_label = self.config["a2_pull_v6_stage4_bank_row_label"]
            valid_bank_row_labels = {
                "uniform",
                "e5_phase_b",
                "pre_release_phase_c",
                "post_release_d1",
                "post_release_d5",
                "post_release_d25",
            }
            if not isinstance(bank_row_label, str) or bank_row_label not in valid_bank_row_labels:
                raise RuntimeError("Pull-v6 Stage-4 bank row selector must be a canonical v3 label or 'uniform'.")
            self._a2_pull_v6_stage4_bank_row_index: int | None = None
            if bank_enabled:
                self._load_a2_pull_v6_pre_release_bank()
            elif bank_row_label != "uniform":
                raise RuntimeError("Pull-v6 Stage-4 bank row selection requires external bank enablement.")
            v61_bank_enabled = self.config.get("a2_pull_v61_late_state_bank_enabled", False)
            if not isinstance(v61_bank_enabled, bool):
                raise RuntimeError("Pull-v6.1 late-state bank enablement must be an explicit bool.")
            self._a2_pull_v61_late_state_bank_enabled = v61_bank_enabled
            if v61_bank_enabled:
                self._load_a2_pull_v61_late_state_bank()
        if self._is_a2_pull_v5():
            self._register_a2_pull_v5_staged_reset_buffers()
            injection_enabled = self.config["a2_pull_v5_stage4_bank_injection_enabled"]
            if not isinstance(injection_enabled, bool):
                raise RuntimeError("Pull-v5 stage4 bank injection must be an explicit bool.")
            if injection_enabled:
                self._load_a2_pull_v5_state_bank()
            elif self.config.get("a2_pull_v5_reset_source", "natural") != "natural":
                self._load_a2_pull_v5_eval_state_bank()

    def _register_a2_pull_v5_staged_reset_buffers(self) -> None:
        """Track every pull telemetry tensor restored with a Stage-4 bank state."""

        self._register_a2_pull_staged_reset_buffers(
            _A2_PULL_SHARED_STAGED_RESET_BUFFER_NAMES
            + _A2_PULL_V5_STAGED_RESET_EXTRA_BUFFER_NAMES,
            variant="v5",
        )

    def _register_a2_pull_v6_staged_reset_buffers(self) -> None:
        """Track every post-E5 pull-v6 state restored by a specialist reset."""

        self._register_a2_pull_staged_reset_buffers(
            _A2_PULL_SHARED_STAGED_RESET_BUFFER_NAMES
            + _A2_PULL_V6_STAGED_RESET_EXTRA_BUFFER_NAMES,
            variant="v6",
        )

    def _register_a2_pull_staged_reset_buffers(
        self, names: tuple[str, ...], *, variant: str
    ) -> None:
        if not self.enable_staged_reset:
            raise RuntimeError(
                f"Pull-{variant} staged reset requires enable_staged_reset=true."
            )
        for name in names:
            tensor = getattr(self, f"_{name}")
            if not torch.is_tensor(tensor) or tensor.shape[0] != self.num_envs:
                raise RuntimeError(
                    f"Pull-{variant} staged buffer {name} must be a tensor with leading env axis; "
                    f"got {getattr(tensor, 'shape', None)}."
                )
            if name in self.staged_reset_buf:
                raise RuntimeError(
                    f"Pull-{variant} staged buffer name collides with existing entry: {name}"
                )
            self._register_buffer_to_track(
                name,
                tuple(tensor.shape),
                lambda env_ids, name=name: self._store_a2_pull_named_buffer(name, env_ids),
                lambda env_ids, data, name=name: self._load_a2_pull_named_buffer(name, env_ids, data),
                dtype=tensor.dtype,
            )

    def _store_a2_pull_named_buffer(self, name: str, env_ids: torch.Tensor) -> torch.Tensor:
        value = getattr(self, f"_{name}")
        if name == "a2_pull_first_event_step":
            reached = self._a2_pull_event_reached[env_ids]
            return torch.where(
                reached,
                torch.zeros_like(value[env_ids]),
                torch.full_like(value[env_ids], -1),
            )
        if name == "a2_pull_first_event_time_s":
            reached = self._a2_pull_event_reached[env_ids]
            return torch.where(
                reached,
                torch.zeros_like(value[env_ids]),
                torch.full_like(value[env_ids], float("nan")),
            )
        return value[env_ids].clone()

    def _load_a2_pull_named_buffer(self, name: str, env_ids: torch.Tensor, data: torch.Tensor) -> None:
        value = getattr(self, f"_{name}")
        expected = (len(env_ids), *value.shape[1:])
        if tuple(data.shape) != expected or data.dtype != value.dtype or data.device != value.device:
            raise RuntimeError(
                f"Pull staged buffer {name} shape/dtype/device mismatch: "
                f"expected={expected}/{value.dtype}/{value.device}, got={tuple(data.shape)}/{data.dtype}/{data.device}."
            )
        if name == "a2_gait_last_update_step":
            # The stored value belongs to the source rollout's absolute
            # common-step clock.  Preserve gait phase/history, but bind its
            # update timestamp to the receiving rollout so the low-level A2
            # controller advances on the next control step.
            value[env_ids] = self._get_a2_gait_current_step()
        else:
            value[env_ids] = data

    def apply_a2_pull_v5_intervention(self, policy_action: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Apply the paired P2 one-second arm/gripper override to a high-level action."""

        if not self._is_a2_pull_v5():
            raise RuntimeError("Pull-v5 intervention is only available under the v5 plan guard.")
        enabled = self.config["a2_pull_v5_intervention_enabled"]
        if not isinstance(enabled, bool):
            raise RuntimeError("a2_pull_v5_intervention_enabled must be bool.")
        hinge = self._get_door_joint_pos("pull-v5 intervention", 3)[:, 0]
        aperture = self._a2_pull_aperture_ready
        trigger = aperture & (hinge >= 1.60)
        newly_active = enabled & trigger & ~self._a2_pull_v5_intervention_fired
        self._a2_pull_v5_intervention_fired |= newly_active
        self._a2_pull_v5_intervention_elapsed_steps[newly_active] = 0
        self._a2_pull_v5_intervention_active |= newly_active
        # Keep the one-second window latched after the trigger even if the
        # instantaneous aperture predicate flickers on the next control step.
        latched_hinge = torch.where(
            self._a2_pull_v5_intervention_active,
            torch.full_like(hinge, 1.60),
            hinge,
        )
        latched_aperture = aperture | self._a2_pull_v5_intervention_active
        if (
            not torch.is_tensor(self._delta_actions)
            or tuple(self._delta_actions.shape) != (self.num_envs, 6)
            or self._delta_actions.device != torch.device(self.device)
            or not torch.all(torch.isfinite(self._delta_actions))
        ):
            raise RuntimeError(
                "Pull-v5 intervention requires finite cumulative arm targets with shape (N,6)."
            )
        if not isinstance(self._delta_action_scale, (int, float)) or self._delta_action_scale <= 0:
            raise RuntimeError("Pull-v5 intervention requires a positive delta_action_scale.")
        # DeltaActionBase applies this raw arm command before writing the
        # cumulative target.  Driving by -d_prev/scale lands at the actual
        # Piper default pose (d_des=0), rather than holding the current target.
        default_arm_action = -self._delta_actions / float(self._delta_action_scale)
        applied, active = a2_pull_v5_release_tuck_override(
            policy_action,
            latched_hinge,
            latched_aperture,
            self._a2_pull_v5_intervention_elapsed_steps,
            dt=float(self.dt),
            enabled=enabled,
            arm_action=default_arm_action,
        )
        self._a2_pull_v5_intervention_elapsed_steps[active] += 1
        self._a2_pull_v5_intervention_active &= active
        return applied, active

    def set_a2_pull_v5_scheduler_episode_indices(self, episode_indices: torch.Tensor) -> None:
        """Bind scheduler telemetry to the trainer's first-episode index."""

        if (
            not self._a2_pull_v5_scheduler_enabled
            or not torch.is_tensor(episode_indices)
            or tuple(episode_indices.shape) != (self.num_envs,)
            or episode_indices.dtype != torch.long
            or episode_indices.device != torch.device(self.device)
            or torch.any(episode_indices < 0)
        ):
            raise RuntimeError(
                "Pull-v5.4 scheduler episode indices require a device-local long tensor of shape (N,)."
            )
        self._a2_pull_v5_scheduler_episode_indices[:] = episode_indices

    def apply_a2_pull_v5_probe_command(
        self,
        policy_action: torch.Tensor,
        command_name: str,
        fixture: str,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Apply one registered P1 sequence through the A2 action path."""

        if not self._is_a2_pull_v5():
            raise RuntimeError("Pull-v5 probe commands require the v5 plan guard.")
        if fixture not in {"anchor", "door", "rehearsal"}:
            raise RuntimeError(
                f"Pull-v5 probe fixture must be anchor, door, or rehearsal; got {fixture!r}."
            )
        if command_name in self._A2_PULL_V5_PROBE_SEQUENCES:
            sequence_id = command_name
            sequence_phases = self._A2_PULL_V5_PROBE_SEQUENCES[command_name]
        elif command_name in self._A2_PULL_V5_PROBE_PRIMITIVES:
            sequence_id = command_name
            sequence_phases = (command_name,)
        else:
            raise RuntimeError(f"Pull-v5 probe command is not registered: {command_name!r}.")
        if self._a2_pull_v5_probe_sequence_id not in (None, sequence_id):
            raise RuntimeError(
                "Pull-v5 probe sequence cannot change while phase state is live; "
                f"got {self._a2_pull_v5_probe_sequence_id!r} then {sequence_id!r}."
            )
        self._a2_pull_v5_probe_sequence_id = sequence_id
        self._a2_pull_v5_probe_sequence_phases = tuple(sequence_phases)
        if (
            not torch.is_tensor(policy_action)
            or tuple(policy_action.shape) != (self.num_envs, 12)
            or not policy_action.is_floating_point()
            or policy_action.device != torch.device(self.device)
            or not torch.all(torch.isfinite(policy_action))
        ):
            raise RuntimeError("Pull-v5 probe requires a finite device-local high-level action (N,12).")
        lattice_scale = self.config.get("a2_pull_v5_lattice_scale", 1.0)
        if (
            isinstance(lattice_scale, bool)
            or not isinstance(lattice_scale, (int, float))
            or not math.isfinite(float(lattice_scale))
            or float(lattice_scale) <= 0.0
        ):
            raise RuntimeError("Pull-v5 probe lattice scale must be a finite positive number.")
        lattice_scale = float(lattice_scale)
        waypoint_tolerance = self.config.get(
            "a2_pull_v5_probe_waypoint_tolerance_m",
            self._A2_PULL_V5_PROBE_WAYPOINT_TOLERANCE_M,
        )
        if (
            isinstance(waypoint_tolerance, bool)
            or not isinstance(waypoint_tolerance, (int, float))
            or not math.isfinite(float(waypoint_tolerance))
            or float(waypoint_tolerance) <= 0.0
        ):
            raise RuntimeError("Pull-v5 probe waypoint tolerance must be a finite positive number.")
        waypoint_tolerance = float(waypoint_tolerance)
        yaw_tolerance = self.config.get(
            "a2_pull_v5_probe_yaw_tolerance_rad",
            self._A2_PULL_V5_PROBE_YAW_TOLERANCE_RAD,
        )
        if (
            isinstance(yaw_tolerance, bool)
            or not isinstance(yaw_tolerance, (int, float))
            or not math.isfinite(float(yaw_tolerance))
            or float(yaw_tolerance) <= 0.0
        ):
            raise RuntimeError("Pull-v5 probe yaw tolerance must be a finite positive number.")
        yaw_tolerance = float(yaw_tolerance)
        phase_commands = torch.tensor(
            [self._A2_PULL_V5_PROBE_PRIMITIVES[name] for name in sequence_phases],
            device=self.device,
            dtype=policy_action.dtype,
        ) * lattice_scale
        original_phase_commands = phase_commands.clone()
        rehearsal_delta = self.config.get("a2_pull_v5_scheduler_rehearsal_target_yaw_delta")
        rehearsal_original_delta = self.config.get(
            "a2_pull_v5_scheduler_rehearsal_original_target_yaw_delta"
        )
        if rehearsal_delta is not None:
            if (
                fixture != "rehearsal"
                or isinstance(rehearsal_delta, bool)
                or not isinstance(rehearsal_delta, (int, float))
                or not math.isfinite(float(rehearsal_delta))
            ):
                raise RuntimeError(
                    "Rehearsal yaw target override is finite and only valid for fixture='rehearsal'."
                )
            phase_commands[0, 2] = float(rehearsal_delta)
            if (
                isinstance(rehearsal_original_delta, bool)
                or not isinstance(rehearsal_original_delta, (int, float))
                or not math.isfinite(float(rehearsal_original_delta))
            ):
                raise RuntimeError(
                    "Rehearsal original yaw target must be finite when planning target is overridden."
                )
            original_phase_commands[0, 2] = float(rehearsal_original_delta)
        elif rehearsal_original_delta is not None:
            raise RuntimeError(
                "Rehearsal original target is only valid with a rehearsal planning target override."
            )
        phase_xy_commands = phase_commands[:, :2]
        phase_yaw_commands = phase_commands[:, 2]
        phase_index = self._a2_pull_v5_probe_phase_index
        if torch.any(phase_index >= len(sequence_phases)):
            raise RuntimeError("Pull-v5 probe phase index exceeded the configured sequence.")
        robot = self.simulator.scene.articulations["robot"]
        if fixture in {"anchor", "rehearsal"}:
            uninitialized = ~self._a2_pull_v5_probe_anchor_initialized
            if torch.any(uninitialized):
                env_ids = torch.where(uninitialized)[0]
                anchor_root = robot.data.default_root_state[env_ids].clone()
                anchor_root[:, :3] += self.env_origins[env_ids]
                anchor_root[:, 0] = self.env_origins[env_ids, 0] + (
                    float(self._pull_direction.approach_side_x) * 1.0
                )
                anchor_root[:, 1] = self.env_origins[env_ids, 1]
                anchor_roll, anchor_pitch, _ = euler_xyz_from_quat(anchor_root[:, 3:7])
                anchor_root[:, 3:7] = quat_from_euler_xyz(
                    anchor_roll,
                    anchor_pitch,
                    torch.full_like(anchor_roll, math.pi),
                )
                anchor_root[:, 7:13] = 0.0
                robot.write_root_state_to_sim(anchor_root, env_ids)
                anchor_dof_pos = self.default_dof_pos.to(self.device).expand(len(env_ids), -1).clone()
                anchor_dof_pos[:, self._upper_non_gripper_dof_idx] = self._get_a2_arm_default_dof_pos(
                    env_ids
                )
                anchor_dof_pos[:, self._a2_gripper_dof_indices] = self._a2_gripper_open_target
                robot.write_joint_state_to_sim(
                    anchor_dof_pos,
                    torch.zeros_like(anchor_dof_pos),
                    env_ids=env_ids,
                )
                robot.reset(env_ids)
                self._refresh_sim_tensors()
                _, _, anchor_root_yaw = euler_xyz_from_quat(anchor_root[:, 3:7])
                self._a2_pull_v5_probe_waypoint_target_xy[env_ids] = (
                    anchor_root[:, :2] + phase_xy_commands[0]
                )
                self._a2_pull_v5_probe_yaw_target[env_ids] = (
                    anchor_root_yaw + phase_yaw_commands[0]
                )
                self._a2_pull_v5_probe_original_yaw_target[env_ids] = (
                    anchor_root_yaw + original_phase_commands[0, 2]
                )
                self._a2_pull_v5_probe_anchor_initialized[env_ids] = True
        root_pos = self.simulator.scene.articulations["robot"].data.root_pos_w
        root_quat_w = self.simulator.scene.articulations["robot"].data.root_quat_w
        if (
            tuple(root_pos.shape) != (self.num_envs, 3)
            or tuple(root_quat_w.shape) != (self.num_envs, 4)
            or root_pos.device != policy_action.device
            or root_quat_w.device != policy_action.device
            or root_quat_w.dtype != policy_action.dtype
            or not torch.all(torch.isfinite(root_pos))
            or not torch.all(torch.isfinite(root_quat_w))
        ):
            raise RuntimeError("Pull-v5 probe requires finite robot root state tensors on the action device.")
        _, _, root_yaw = euler_xyz_from_quat(root_quat_w)
        phase_xy = phase_xy_commands[phase_index]
        phase_yaw = phase_yaw_commands[phase_index]
        initialize_target = ~self._a2_pull_v5_probe_phase_initialized
        self._a2_pull_v5_probe_waypoint_target_xy[initialize_target] = (
            root_pos[initialize_target, :2] + phase_xy[initialize_target]
        )
        self._a2_pull_v5_probe_yaw_target[initialize_target] = (
            root_yaw[initialize_target] + phase_yaw[initialize_target]
        )
        self._a2_pull_v5_probe_original_yaw_target[initialize_target] = (
            root_yaw[initialize_target] + original_phase_commands[phase_index[initialize_target], 2]
        )
        self._a2_pull_v5_probe_phase_initialized[initialize_target] = True
        waypoint_error = self._a2_pull_v5_probe_waypoint_target_xy - root_pos[:, :2]
        waypoint_error_m = torch.linalg.norm(waypoint_error, dim=-1)
        yaw_error = wrap_to_pi(self._a2_pull_v5_probe_yaw_target - root_yaw)
        root_yaw_rate = robot.data.root_ang_vel_w[:, 2]
        if (
            tuple(root_yaw_rate.shape) != (self.num_envs,)
            or root_yaw_rate.device != policy_action.device
            or not torch.all(torch.isfinite(root_yaw_rate))
        ):
            raise RuntimeError("Pull-v5.4 scheduler requires finite world-frame root yaw angular velocity.")
        waypoint_arrived = waypoint_error_m <= waypoint_tolerance
        if self._a2_pull_v5_scheduler_enabled:
            states = self._a2_pull_v5_scheduler_state
            state_ids = self._A2_PULL_V5_4_SCHEDULER_STATES
            constants = self._A2_PULL_V5_4_SCHEDULER_CONSTANTS
            in_live = ~self._a2_pull_v5_probe_sequence_complete
            plan = in_live & (states == state_ids["XY_TRACK"]) & waypoint_arrived
            states[plan] = state_ids["PLAN_YAW"]
            plan = in_live & (states == state_ids["PLAN_YAW"])
            trim_band = float(constants["b_trim_rad"]["value"])
            positive_fail = plan & (torch.abs(yaw_error) <= trim_band) & (yaw_error > 0.0)
            if torch.any(positive_fail):
                states[positive_fail] = state_ids["FAILED"]
                for env_id in torch.where(positive_fail)[0].tolist():
                    self._a2_pull_v5_scheduler_failure_reason[env_id] = "positive_error_inside_trim_band"
            trim_plan = plan & ~positive_fail & (torch.abs(yaw_error) <= trim_band)
            states[trim_plan] = state_ids["TRIM"]
            coarse_plan = plan & ~positive_fail & ~trim_plan
            positive_coarse = coarse_plan & (yaw_error > 0.0)
            negative_coarse = coarse_plan & ~positive_coarse
            self._a2_pull_v5_scheduler_coarse_raw[positive_coarse] = float(constants["coarse_raw_positive"]["value"])
            self._a2_pull_v5_scheduler_cutoff[positive_coarse] = float(constants["coarse_cutoff_positive_e_rad"]["value"])
            self._a2_pull_v5_scheduler_min_settle_steps[positive_coarse] = int(constants["minimum_settle_steps_positive"]["value"])
            self._a2_pull_v5_scheduler_coarse_raw[negative_coarse] = float(constants["coarse_raw_negative"]["value"])
            self._a2_pull_v5_scheduler_cutoff[negative_coarse] = float(constants["coarse_cutoff_negative_e_rad"]["value"])
            self._a2_pull_v5_scheduler_min_settle_steps[negative_coarse] = int(constants["minimum_settle_steps_negative"]["value"])
            states[positive_coarse | negative_coarse] = state_ids["COARSE"]

            coarse = in_live & (states == state_ids["COARSE"])
            reached_positive = coarse & (self._a2_pull_v5_scheduler_coarse_raw > 0.0) & (yaw_error <= self._a2_pull_v5_scheduler_cutoff)
            reached_negative = coarse & (self._a2_pull_v5_scheduler_coarse_raw < 0.0) & (yaw_error >= self._a2_pull_v5_scheduler_cutoff)
            reached = reached_positive | reached_negative
            states[reached] = state_ids["SETTLE"]
            self._a2_pull_v5_scheduler_settle_steps[reached] = 0

            settle = in_live & (states == state_ids["SETTLE"])
            self._a2_pull_v5_scheduler_settle_steps[settle] += 1
            settle_rate_ok = torch.abs(root_yaw_rate) <= float(
                constants["settle_velocity_threshold_rad_s"]["value"]
            )
            settle_ready = settle & (
                self._a2_pull_v5_scheduler_settle_steps
                >= self._a2_pull_v5_scheduler_min_settle_steps
            ) & settle_rate_ok
            settle_deadline = settle & (
                self._a2_pull_v5_scheduler_settle_steps
                >= int(constants["settle_deadline_steps"]["value"])
            ) & ~settle_ready
            if torch.any(settle_deadline):
                states[settle_deadline] = state_ids["FAILED"]
                for env_id in torch.where(settle_deadline)[0].tolist():
                    self._a2_pull_v5_scheduler_failure_reason[env_id] = "settle_deadline_exceeded"
            states[settle_ready] = state_ids["TRIM"]

            # A settle-completing invocation must remain a full zero-command
            # physics step; trim is eligible only on the following invocation.
            trim = in_live & (states == state_ids["TRIM"]) & ~settle_ready
            trim_positive_fail = trim & (yaw_error > 0.0) & (torch.abs(yaw_error) <= trim_band)
            if torch.any(trim_positive_fail):
                states[trim_positive_fail] = state_ids["FAILED"]
                for env_id in torch.where(trim_positive_fail)[0].tolist():
                    self._a2_pull_v5_scheduler_failure_reason[env_id] = "positive_error_inside_trim_band"
            predicted_error = yaw_error - float(constants["trim_one_step_rad"]["value"]) - float(constants["trim_stop_drift_rad"]["value"])
            trim_final = trim & ~trim_positive_fail & (
                torch.abs(predicted_error) <= float(constants["planning_a_rad"]["value"])
            )
            states[trim_final] = state_ids["FINAL"]
            trim_cap = trim & ~trim_positive_fail & ~trim_final & (
                self._a2_pull_v5_scheduler_trim_steps
                >= int(constants["trim_step_cap"]["value"])
            )
            if torch.any(trim_cap):
                states[trim_cap] = state_ids["FAILED"]
                for env_id in torch.where(trim_cap)[0].tolist():
                    self._a2_pull_v5_scheduler_failure_reason[env_id] = "trim_step_cap_exceeded"
            trim_pulse = trim & ~trim_positive_fail & ~trim_final & ~trim_cap
            self._a2_pull_v5_scheduler_trim_steps[trim_pulse] += 1

            final = in_live & (states == state_ids["FINAL"])
            states[final] = state_ids["TERMINAL_HOLD"]
            self._a2_pull_v5_scheduler_terminal_hold_steps[final] = 0
            hold = in_live & (states == state_ids["TERMINAL_HOLD"])
            self._a2_pull_v5_scheduler_terminal_hold_steps[hold] += 1
            hold_done = hold & (
                self._a2_pull_v5_scheduler_terminal_hold_steps
                >= int(constants["terminal_hold_steps"]["value"])
            )
            hold_pass = hold_done & waypoint_arrived & (torch.abs(yaw_error) <= yaw_tolerance)
            hold_fail = hold_done & ~hold_pass
            states[hold_pass] = state_ids["DONE"]
            if torch.any(hold_fail):
                states[hold_fail] = state_ids["FAILED"]
                for env_id in torch.where(hold_fail)[0].tolist():
                    self._a2_pull_v5_scheduler_failure_reason[env_id] = "terminal_hold_yaw_error"
            scheduler_yaw_command = torch.zeros(self.num_envs, dtype=policy_action.dtype, device=policy_action.device)
            coarse_active = states == state_ids["COARSE"]
            scheduler_yaw_command[coarse_active] = self._a2_pull_v5_scheduler_coarse_raw[coarse_active].to(policy_action.dtype)
            scheduler_yaw_command[trim_pulse] = float(constants["trim_raw"]["value"])
            phase_complete = (
                (states == state_ids["DONE"])
                & waypoint_arrived
                & (torch.abs(yaw_error) <= yaw_tolerance)
                & ~self._a2_pull_v5_probe_sequence_complete
            )
        else:
            phase_complete = (
                self._a2_pull_v5_probe_phase_initialized
                & waypoint_arrived
                & (torch.abs(yaw_error) <= yaw_tolerance)
                & ~self._a2_pull_v5_probe_sequence_complete
            )
        next_phase = phase_index + 1
        advance_phase = phase_complete & (next_phase < len(sequence_phases))
        if torch.any(advance_phase):
            next_phase_index = next_phase[advance_phase]
            self._a2_pull_v5_probe_phase_index[advance_phase] = next_phase_index
            self._a2_pull_v5_probe_phase_waypoint_arrived[advance_phase] = False
            self._a2_pull_v5_probe_phase_yaw_arrived[advance_phase] = False
            self._a2_pull_v5_probe_waypoint_target_xy[advance_phase] = (
                root_pos[advance_phase, :2] + phase_xy_commands[next_phase_index]
            )
            self._a2_pull_v5_probe_yaw_target[advance_phase] = (
                root_yaw[advance_phase] + phase_yaw_commands[next_phase_index]
            )
            self._a2_pull_v5_probe_original_yaw_target[advance_phase] = (
                root_yaw[advance_phase] + original_phase_commands[next_phase_index, 2]
            )
            if getattr(self, "_a2_pull_v5_scheduler_enabled", False):
                self._a2_pull_v5_scheduler_state[advance_phase] = self._A2_PULL_V5_4_SCHEDULER_STATES["XY_TRACK"]
                self._a2_pull_v5_scheduler_settle_steps[advance_phase] = 0
                self._a2_pull_v5_scheduler_trim_steps[advance_phase] = 0
                self._a2_pull_v5_scheduler_terminal_hold_steps[advance_phase] = 0
                self._a2_pull_v5_scheduler_failure_reason = [
                    None if bool(mask) else reason
                    for mask, reason in zip(advance_phase.detach().cpu().tolist(), self._a2_pull_v5_scheduler_failure_reason)
                ]
            phase_index = self._a2_pull_v5_probe_phase_index
            phase_xy = phase_xy_commands[phase_index]
            phase_yaw = phase_yaw_commands[phase_index]
            waypoint_error = self._a2_pull_v5_probe_waypoint_target_xy - root_pos[:, :2]
            waypoint_error_m = torch.linalg.norm(waypoint_error, dim=-1)
            yaw_error = wrap_to_pi(self._a2_pull_v5_probe_yaw_target - root_yaw)
            waypoint_arrived = waypoint_error_m <= waypoint_tolerance
        _residual, solvable, _body_velocity, raw_base = a2_hold_base_relief_command(
            waypoint_error,
            root_quat_w,
            torch.ones(self.num_envs, dtype=torch.bool, device=self.device),
            physical_speed_mps=0.30,
            base_command_scale=self._a2_base_command_scale,
            min_solvable_horizontal_error_m=1.0e-3,
        )
        if self._a2_pull_v5_scheduler_enabled:
            solvable |= self._a2_pull_v5_scheduler_state != self._A2_PULL_V5_4_SCHEDULER_STATES["XY_TRACK"]
        if self._a2_pull_v5_scheduler_enabled:
            yaw_command = scheduler_yaw_command
            solvable |= torch.abs(yaw_error) >= 1.0e-3
        else:
            registered_yaw_limit = max(
                abs(command[2]) for command in self._A2_PULL_V5_PROBE_PRIMITIVES.values()
            )
            yaw_command_limit = torch.where(
                torch.abs(phase_yaw) > 0.0,
                torch.abs(phase_yaw),
                torch.full_like(phase_yaw, registered_yaw_limit),
            )
            yaw_command = -torch.sign(yaw_error) * torch.minimum(
                torch.abs(yaw_error), yaw_command_limit
            )
            solvable |= torch.abs(yaw_error) >= 1.0e-3
        if self._a2_pull_v5_scheduler_enabled:
            self._a2_pull_v5_scheduler_raw_yaw_command[:] = yaw_command
        applied = policy_action.clone()
        applied[:, :5] = raw_base
        # v5.4 scheduler constants are already raw action units.  Preserve the
        # existing base slice/order and write only the scheduler yaw index.
        applied[:, 2] = yaw_command
        waypoint_arrived = waypoint_error_m <= waypoint_tolerance
        yaw_arrived = torch.abs(yaw_error) <= yaw_tolerance
        if self._a2_pull_v5_scheduler_enabled:
            final_phase_arrived = (
                (self._a2_pull_v5_scheduler_state == self._A2_PULL_V5_4_SCHEDULER_STATES["DONE"])
                & waypoint_arrived
                & yaw_arrived
                & (phase_index == len(sequence_phases) - 1)
                & self._a2_pull_v5_probe_phase_initialized
            )
        else:
            final_phase_arrived = (
                waypoint_arrived
                & yaw_arrived
                & (phase_index == len(sequence_phases) - 1)
                & self._a2_pull_v5_probe_phase_initialized
            )
        self._a2_pull_v5_probe_phase_waypoint_arrived[:] = waypoint_arrived
        self._a2_pull_v5_probe_phase_yaw_arrived[:] = yaw_arrived
        self._a2_pull_v5_probe_sequence_complete |= final_phase_arrived
        self._a2_pull_v5_probe_waypoint_error_m[:] = waypoint_error_m
        self._a2_pull_v5_probe_yaw_error_rad[:] = torch.abs(yaw_error)
        self._a2_pull_v5_probe_waypoint_arrived[:] = waypoint_arrived
        self._a2_pull_v5_probe_yaw_arrived[:] = yaw_arrived
        if fixture in {"anchor", "rehearsal"}:
            self._a2_pull_v5_probe_anchor_pass[:] = (
                self._a2_pull_v5_probe_sequence_complete
                & waypoint_arrived
                & yaw_arrived
                & (phase_index == len(sequence_phases) - 1)
            )
        self._a2_pull_v5_probe_solvable |= solvable
        return applied, solvable

    def _append_a2_pull_v5_scheduler_trace_rows(self) -> None:
        """Append one scheduler row from the current post-physics state."""

        if not self._a2_pull_v5_scheduler_enabled:
            raise RuntimeError("Pull-v5.4 scheduler trace requires scheduler_enabled=true.")
        sequence_id = self._a2_pull_v5_probe_sequence_id
        if not isinstance(sequence_id, str) or not sequence_id:
            raise RuntimeError("Pull-v5.4 scheduler trace requires an active probe sequence.")
        fixture = self.config.get("a2_pull_v5_probe_fixture")
        if not isinstance(fixture, str) or not fixture:
            raise RuntimeError("Pull-v5.4 scheduler trace requires a configured probe fixture.")
        robot = self.simulator.scene.articulations["robot"]
        root_pos = robot.data.root_pos_w
        root_quat_w = robot.data.root_quat_w
        root_yaw_rate = robot.data.root_ang_vel_w[:, 2]
        expected_shape = (self.num_envs,)
        if (
            not torch.is_tensor(root_pos)
            or tuple(root_pos.shape) != (self.num_envs, 3)
            or not torch.is_tensor(root_quat_w)
            or tuple(root_quat_w.shape) != (self.num_envs, 4)
            or not torch.is_tensor(root_yaw_rate)
            or tuple(root_yaw_rate.shape) != expected_shape
            or root_pos.device != torch.device(self.device)
            or root_quat_w.device != torch.device(self.device)
            or root_yaw_rate.device != torch.device(self.device)
            or not torch.all(torch.isfinite(root_pos))
            or not torch.all(torch.isfinite(root_quat_w))
            or not torch.all(torch.isfinite(root_yaw_rate))
        ):
            raise RuntimeError("Pull-v5.4 scheduler trace requires finite post-physics root state tensors.")
        if (
            self._a2_pull_v5_probe_yaw_target.shape != expected_shape
            or self._a2_pull_v5_probe_original_yaw_target.shape != expected_shape
            or self._a2_pull_v5_scheduler_raw_yaw_command.shape != expected_shape
            or not torch.all(torch.isfinite(self._a2_pull_v5_probe_yaw_target))
            or not torch.all(torch.isfinite(self._a2_pull_v5_probe_original_yaw_target))
            or not torch.all(torch.isfinite(self._a2_pull_v5_scheduler_raw_yaw_command))
        ):
            raise RuntimeError("Pull-v5.4 scheduler trace requires finite target and action tensors.")
        _, _, root_yaw = euler_xyz_from_quat(root_quat_w)
        yaw_error = wrap_to_pi(self._a2_pull_v5_probe_yaw_target - root_yaw)
        original_error = wrap_to_pi(self._a2_pull_v5_probe_original_yaw_target - root_yaw)
        if not torch.all(torch.isfinite(yaw_error)) or not torch.all(torch.isfinite(original_error)):
            raise RuntimeError("Pull-v5.4 scheduler trace requires finite post-physics yaw errors.")
        state_names = {value: key for key, value in self._A2_PULL_V5_4_SCHEDULER_STATES.items()}
        for env_id in range(self.num_envs):
            state_name = state_names[int(self._a2_pull_v5_scheduler_state[env_id].item())]
            episode_index = int(self._a2_pull_v5_scheduler_episode_indices[env_id].item())
            self._a2_pull_v5_scheduler_trace_rows.append(
                {
                    "schema": self._A2_PULL_V5_4_SCHEDULER_SCHEMA,
                    "record_class": "interface_characterization",
                    "env_id": env_id,
                    "episode_index": episode_index,
                    "episode_id": f"{fixture}:env{env_id}:episode{episode_index}",
                    "step_index": int(self.episode_length_buf[env_id].item()),
                    "sequence": sequence_id,
                    "phase_index": int(self._a2_pull_v5_probe_phase_index[env_id].item()),
                    "state": state_name,
                    "requested_yaw_rad": float(self._a2_pull_v5_probe_yaw_target[env_id].item()),
                    "original_target_yaw_rad": float(
                        self._a2_pull_v5_probe_original_yaw_target[env_id].item()
                    ),
                    "realized_yaw_rad": float(root_yaw[env_id].item()),
                    "error_rad": float(yaw_error[env_id].item()),
                    "terminal_error_original_target_rad": float(original_error[env_id].item()),
                    "abs_error_rad": float(torch.abs(yaw_error[env_id]).item()),
                    "yaw_rate_rad_s": float(root_yaw_rate[env_id].item()),
                    "raw_yaw_command": float(self._a2_pull_v5_scheduler_raw_yaw_command[env_id].item()),
                    "settle_steps": int(self._a2_pull_v5_scheduler_settle_steps[env_id].item()),
                    "trim_steps": int(self._a2_pull_v5_scheduler_trim_steps[env_id].item()),
                    "terminal_hold_steps": int(
                        self._a2_pull_v5_scheduler_terminal_hold_steps[env_id].item()
                    ),
                    "failure_reason": self._a2_pull_v5_scheduler_failure_reason[env_id],
                    "terminal_after_step": None,
                    "terminal_current_state": state_name == "DONE",
                    "scientific_denominator_included": False,
                    "denominator_scope": "none",
                }
            )

    def _mark_a2_pull_v5_scheduler_trace_failures(self, failed_mask: torch.Tensor) -> None:
        """Reflect non-scheduler terminal failure in the just-appended row."""

        if (
            not torch.is_tensor(failed_mask)
            or failed_mask.shape != (self.num_envs,)
            or failed_mask.dtype != torch.bool
            or failed_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("Pull-v5.4 scheduler trace failure mask has an invalid contract.")
        state_name = "FAILED"
        for env_id in torch.where(failed_mask)[0].tolist():
            episode_index = int(self._a2_pull_v5_scheduler_episode_indices[env_id].item())
            step_index = int(self.episode_length_buf[env_id].item())
            matching_rows = [
                row
                for row in reversed(self._a2_pull_v5_scheduler_trace_rows)
                if row.get("env_id") == env_id
                and row.get("episode_index") == episode_index
                and row.get("step_index") == step_index
            ]
            if len(matching_rows) != 1:
                raise RuntimeError(
                    "Pull-v5.4 scheduler non-scheduler termination requires exactly one current trace row."
                )
            row = matching_rows[0]
            row["state"] = state_name
            row["failure_reason"] = self._a2_pull_v5_scheduler_failure_reason[env_id]
            row["terminal_current_state"] = False

    def consume_a2_pull_v5_scheduler_trace_rows(self) -> list[dict[str, object]]:
        """Transfer evaluator-owned v5.4 scheduler rows without writing artifacts."""

        if not self._a2_pull_v5_scheduler_enabled:
            raise RuntimeError("Pull-v5.4 scheduler trace consumer requires scheduler_enabled=true.")
        rows = list(self._a2_pull_v5_scheduler_trace_rows)
        self._a2_pull_v5_scheduler_trace_rows.clear()
        return rows

    def _get_a2_pull_v5_characterization_contract(self) -> dict[str, object]:
        """Resolve the preregistered open-field characterization cell contract."""

        if not self._a2_pull_v5_characterization_enabled:
            raise RuntimeError("HOMIE characterization is not enabled for this evaluator.")
        if not self._is_a2_pull_v5():
            raise RuntimeError("HOMIE characterization requires the v5 plan guard.")
        characterization_plan_id = self.config.get("a2_pull_v5_characterization_plan_id")
        if characterization_plan_id != self._A2_PULL_V5_CHARACTERIZATION_PLAN_ID:
            raise RuntimeError(
                "HOMIE characterization requires characterization_plan_id="
                f"{self._A2_PULL_V5_CHARACTERIZATION_PLAN_ID!r}; "
                f"got {characterization_plan_id!r}."
            )
        fixture = self.config.get("a2_pull_v5_characterization_fixture")
        if fixture != "open_field":
            raise RuntimeError(
                "HOMIE characterization fixture must be exactly 'open_field'; "
                f"got {fixture!r}."
            )
        cell_id = self.config.get("a2_pull_v5_characterization_cell_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise RuntimeError("HOMIE characterization requires a non-empty cell_id.")
        requested_u = self.config.get("a2_pull_v5_characterization_requested_u")
        if (
            isinstance(requested_u, bool)
            or not isinstance(requested_u, (int, float))
            or not math.isfinite(float(requested_u))
            or abs(float(requested_u)) > self._A2_PULL_V5_CHARACTERIZATION_RAW_YAW_LIMIT
            or abs(float(requested_u)) < 0.05
        ):
            raise RuntimeError(
                "HOMIE characterization requested_u must be finite and within the "
                f"registered raw range +/-{self._A2_PULL_V5_CHARACTERIZATION_RAW_YAW_LIMIT}; "
                f"got {requested_u!r}."
            )
        requested_u = float(requested_u)
        if not any(
            math.isclose(abs(requested_u), magnitude, rel_tol=0.0, abs_tol=1.0e-9)
            for magnitude in self._A2_PULL_V5_CHARACTERIZATION_YAW_MAGNITUDES
        ):
            raise RuntimeError(
                "HOMIE characterization requested_u is outside the preregistered grid; "
                f"got {requested_u!r}."
            )
        duration_s = self.config.get("a2_pull_v5_characterization_duration_s")
        if (
            isinstance(duration_s, bool)
            or not isinstance(duration_s, (int, float))
            or not math.isfinite(float(duration_s))
            or not any(
                math.isclose(float(duration_s), value, rel_tol=0.0, abs_tol=1.0e-9)
                for value in self._A2_PULL_V5_CHARACTERIZATION_DURATIONS_S
            )
        ):
            raise RuntimeError(
                "HOMIE characterization duration_s must be one of "
                f"{self._A2_PULL_V5_CHARACTERIZATION_DURATIONS_S}; got {duration_s!r}."
            )
        duration_s = float(duration_s)
        hold_s = self.config.get("a2_pull_v5_characterization_hold_s", 2.0)
        if (
            isinstance(hold_s, bool)
            or not isinstance(hold_s, (int, float))
            or not math.isfinite(float(hold_s))
            or float(hold_s) < 2.0
        ):
            raise RuntimeError(
                "HOMIE characterization hold_s must be a finite duration >= 2.0s; "
                f"got {hold_s!r}."
            )
        hold_s = float(hold_s)
        primitive = self.config.get("a2_pull_v5_characterization_xy_primitive", "none")
        if primitive not in self._A2_PULL_V5_CHARACTERIZATION_PRIMITIVES:
            raise RuntimeError(
                "HOMIE characterization XY primitive is not registered; "
                f"got {primitive!r}."
            )
        if primitive != "none" and not any(
            math.isclose(abs(requested_u), magnitude, rel_tol=0.0, abs_tol=1.0e-9)
            for magnitude in (0.2, 0.8)
        ):
            raise RuntimeError(
                "HOMIE characterization coupling cells only permit |u| in {0.2, 0.8}; "
                f"got u={requested_u!r}, primitive={primitive!r}."
            )
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"HOMIE characterization requires finite positive dt; got {dt!r}.")
        command_steps = max(1, math.ceil(duration_s / dt))
        hold_steps = max(1, math.ceil(hold_s / dt))
        window_steps = command_steps + hold_steps
        return {
            "schema": self._A2_PULL_V5_CHARACTERIZATION_TRACE_SCHEMA,
            "record_class": "interface_characterization",
            "fixture": fixture,
            "cell_id": cell_id,
            "requested_u": requested_u,
            "duration_s": duration_s,
            "hold_s": hold_s,
            "command_steps": command_steps,
            "hold_steps": hold_steps,
            "window_steps": window_steps,
            "xy_primitive": primitive,
            "dt": dt,
            "num_envs": self.num_envs,
            "plan_id": characterization_plan_id,
        }

    def get_a2_pull_v5_characterization_contract(self) -> dict[str, object]:
        """Return the evaluator-facing characterization schema and timing contract."""

        return dict(self._get_a2_pull_v5_characterization_contract())

    def apply_a2_pull_v5_characterization_command(
        self,
        policy_action: torch.Tensor,
        first_episode_active_mask: torch.Tensor,
        episode_indices: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Write the open-loop yaw command at the final high-level action mapping."""

        contract = self._get_a2_pull_v5_characterization_contract()
        expected_action_shape = (self.num_envs, 12)
        if (
            not torch.is_tensor(policy_action)
            or tuple(policy_action.shape) != expected_action_shape
            or not policy_action.is_floating_point()
            or policy_action.device != torch.device(self.device)
            or not torch.all(torch.isfinite(policy_action))
        ):
            raise RuntimeError(
                "HOMIE characterization requires a finite device-local high-level action "
                f"shape {expected_action_shape}."
            )
        for name, value in (
            ("first_episode_active_mask", first_episode_active_mask),
            ("episode_indices", episode_indices),
        ):
            expected_dtype = torch.bool if name == "first_episode_active_mask" else torch.long
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != (self.num_envs,)
                or value.dtype != expected_dtype
                or value.device != policy_action.device
            ):
                raise RuntimeError(
                    f"HOMIE characterization {name} requires shape ({self.num_envs},) "
                    f"with dtype {expected_dtype} on {policy_action.device}."
                )
        if not self._use_a2_base:
            raise RuntimeError("HOMIE characterization requires the A2_Base high-level action path.")

        robot_data = self.simulator.scene.articulations["robot"].data
        root_pos = robot_data.root_pos_w
        root_quat_w = robot_data.root_quat_w
        if (
            tuple(root_pos.shape) != (self.num_envs, 3)
            or tuple(root_quat_w.shape) != (self.num_envs, 4)
            or root_pos.device != policy_action.device
            or root_quat_w.device != policy_action.device
            or root_quat_w.dtype != policy_action.dtype
            or not torch.all(torch.isfinite(root_pos))
            or not torch.all(torch.isfinite(root_quat_w))
        ):
            raise RuntimeError(
                "HOMIE characterization requires finite WXYZ robot root tensors on the action device."
            )
        _, _, root_yaw = euler_xyz_from_quat(root_quat_w)
        episode_step = self.episode_length_buf.to(dtype=torch.long)
        command_active = first_episode_active_mask & (
            episode_step < int(contract["command_steps"])
        )
        window_active = first_episode_active_mask & (
            episode_step < int(contract["window_steps"])
        )
        phase_u = torch.where(
            command_active,
            torch.full_like(episode_step, float(contract["requested_u"]), dtype=policy_action.dtype),
            torch.zeros_like(episode_step, dtype=policy_action.dtype),
        )
        raw_base = torch.zeros(
            self.num_envs, 5, dtype=policy_action.dtype, device=policy_action.device
        )
        primitive = str(contract["xy_primitive"])
        if primitive != "none":
            primitive_xy = torch.tensor(
                self._A2_PULL_V5_PROBE_PRIMITIVES[primitive][:2],
                dtype=policy_action.dtype,
                device=policy_action.device,
            )
            initialize_target = command_active & ~self._a2_pull_v5_characterization_xy_target_initialized
            if torch.any(initialize_target):
                self._a2_pull_v5_characterization_xy_target[initialize_target] = (
                    root_pos[initialize_target, :2] + primitive_xy
                )
                self._a2_pull_v5_characterization_xy_target_initialized[initialize_target] = True
            waypoint_target = torch.where(
                command_active[:, None],
                self._a2_pull_v5_characterization_xy_target,
                root_pos[:, :2],
            )
            waypoint_error = waypoint_target - root_pos[:, :2]
            _, _, _, raw_base = a2_hold_base_relief_command(
                waypoint_error,
                root_quat_w,
                command_active,
                physical_speed_mps=0.30,
                base_command_scale=self._a2_base_command_scale,
                min_solvable_horizontal_error_m=1.0e-3,
            )
        raw_base = torch.where(window_active[:, None], raw_base, torch.zeros_like(raw_base))
        raw_base[:, 2] = phase_u
        applied = policy_action.clone()
        applied[:, :5] = raw_base
        # This is deliberately a direct raw high-level write.  No waypoint/yaw
        # error, sign, or closed-loop assignment is used in characterization.

        self._a2_pull_v5_characterization_pending[:] = window_active
        self._a2_pull_v5_characterization_active[:] = window_active
        self._a2_pull_v5_characterization_episode_indices[:] = episode_indices
        self._a2_pull_v5_characterization_step[:] = episode_step
        self._a2_pull_v5_characterization_requested_u[:] = float(contract["requested_u"])
        self._a2_pull_v5_characterization_phase_u[:] = phase_u
        self._a2_pull_v5_characterization_pre_root_pos[:] = root_pos
        self._a2_pull_v5_characterization_pre_root_yaw[:] = root_yaw
        self._a2_pull_v5_characterization_raw_base[:] = raw_base
        for env_id in range(self.num_envs):
            if not window_active[env_id]:
                self._a2_pull_v5_characterization_phase[env_id] = "inactive"
            elif command_active[env_id]:
                self._a2_pull_v5_characterization_phase[env_id] = "command"
            else:
                self._a2_pull_v5_characterization_phase[env_id] = "zero_hold"
        return applied, window_active

    @override
    def _a2_base_pre_physics_command_callback(
        self,
        raw_base_action: torch.Tensor,
        physical_base_command: torch.Tensor,
        lower_body_action: torch.Tensor,
    ) -> None:
        super()._a2_base_pre_physics_command_callback(
            raw_base_action, physical_base_command, lower_body_action
        )
        if self._is_a2_pull_v6():
            self._a2_pull_v6_release_action_started_ready[:] = (
                self._a2_pull_v6_release_ready
            )
            self._a2_pull_v6_passage_command_alignment.zero_()
            self._a2_pull_v6_passage_command_alignment_active.zero_()
            robot_data = self.simulator.scene.articulations["robot"].data
            body_velocity = torch.zeros(
                self.num_envs, 3, dtype=physical_base_command.dtype, device=self.device
            )
            body_velocity[:, :2] = physical_base_command[:, :2]
            world_velocity = quat_apply(yaw_quat(robot_data.root_quat_w), body_velocity)
            _body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
            _arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
            panel_clear = (body_total + arm_total) == 0.0
            active = (
                (self.stage_buf == self.STAGE_SWING)
                & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
                & self._a2_pull_v6_pivot_valid
                & self._a2_pull_v6_prev_bilateral_contact
                & panel_clear
                & (self._a2_pull_v6_frame_lateral_deficit_m > 0.0)
            )
            self._a2_pull_v6_passage_command_alignment_active[:] = active
            clip_y = float(self.config.clip_homie_linvel_y_threshold)
            self._a2_pull_v6_passage_command_alignment[:] = torch.where(
                active,
                (
                    torch.sign(self._a2_pull_v6_frame_lateral_delta_y_m)
                    * world_velocity[:, 1]
                    / clip_y
                ).clamp(-1.0, 1.0),
                torch.zeros_like(world_velocity[:, 1]),
            )
            door_root_xy = self.simulator.get_task_root_state("door")[:, :2]
            root_xy = robot_data.root_pos_w[:, :2]
            waypoint_xy = door_root_xy.clone()
            waypoint_xy[:, 0] += self._pull_direction.travel_dir_x * 2.2
            clip_x = float(self.config.clip_homie_linvel_x_threshold)
            clip_y = float(self.config.clip_homie_linvel_y_threshold)
            velocity_clip_xy = torch.tensor(
                (clip_x, clip_y), dtype=world_velocity.dtype, device=self.device
            )
            target_world_xy = torch.clamp(
                waypoint_xy - root_xy,
                min=-velocity_clip_xy,
                max=velocity_clip_xy,
            )
            self._a2_pull_v6_post_release_lateral_command_alignment[:] = (
                1.0
                - torch.linalg.vector_norm(
                    (world_velocity[:, :2] - target_world_xy) / velocity_clip_xy,
                    dim=-1,
                )
            ).clamp(-1.0, 1.0)
            self._a2_pull_v6_post_release_lateral_command_alignment_active[:] = (
                ((self.stage_buf == self.STAGE_SWING) | (self.stage_buf == self.STAGE_THROUGH))
                & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
                & self._a2_pull_v6_clean_release
                & self._a2_pull_v6_release_event
                & self._a2_pull_aperture_ready
            )
            arm_target_after = self._delta_actions
            arm_target_before = self._a2_pull_v6_pre_action_arm_delta_targets
            self._a2_pull_v6_post_release_arm_tuck_progress[:] = (
                torch.sum(torch.abs(arm_target_before), dim=-1)
                - torch.sum(torch.abs(arm_target_after), dim=-1)
            ).clamp(-1.0, 1.0)
            self._a2_pull_v6_post_release_arm_tuck_progress_active[:] = (
                (self.stage_buf == self.STAGE_SWING)
                & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
                & self._a2_pull_v6_clean_release
                & self._a2_pull_v6_release_event
                & ~self._a2_pull_frame_passage
            )
        if self._a2_pull_v5_characterization_enabled:
            active = self._a2_pull_v5_characterization_pending
            self._a2_pull_v5_characterization_physical_base[active] = physical_base_command[active]

    def _finalize_a2_pull_v5_characterization_step(self) -> None:
        if not self._a2_pull_v5_characterization_enabled:
            return
        pending = self._a2_pull_v5_characterization_pending
        if not torch.any(pending):
            return
        robot_data = self.simulator.scene.articulations["robot"].data
        post_root_pos = robot_data.root_pos_w
        post_root_quat_w = robot_data.root_quat_w
        if (
            tuple(post_root_pos.shape) != (self.num_envs, 3)
            or tuple(post_root_quat_w.shape) != (self.num_envs, 4)
            or not torch.all(torch.isfinite(post_root_pos))
            or not torch.all(torch.isfinite(post_root_quat_w))
        ):
            raise RuntimeError("HOMIE characterization post-physics root tensors must be finite.")
        _, _, post_root_yaw = euler_xyz_from_quat(post_root_quat_w)
        dt = float(self.dt)
        for env_id in torch.where(pending)[0].tolist():
            pre_pos = self._a2_pull_v5_characterization_pre_root_pos[env_id]
            post_pos = post_root_pos[env_id]
            yaw_delta = wrap_to_pi(
                post_root_yaw[env_id] - self._a2_pull_v5_characterization_pre_root_yaw[env_id]
            )
            xy_delta = post_pos[:2] - pre_pos[:2]
            phase = self._a2_pull_v5_characterization_phase[env_id]
            row = {
                "record_class": "interface_characterization",
                "schema": self._A2_PULL_V5_CHARACTERIZATION_TRACE_SCHEMA,
                "cell_id": self.config["a2_pull_v5_characterization_cell_id"],
                "fixture": self.config["a2_pull_v5_characterization_fixture"],
                "env_id": int(env_id),
                "episode_index": int(self._a2_pull_v5_characterization_episode_indices[env_id].item()),
                "episode_id": (
                    f"{self.config['a2_pull_v5_characterization_cell_id']}:env{env_id}:"
                    f"episode{int(self._a2_pull_v5_characterization_episode_indices[env_id].item())}"
                ),
                "step_index": int(self._a2_pull_v5_characterization_step[env_id].item()),
                "command_phase": phase == "command",
                "zero_hold_phase": phase == "zero_hold",
                "phase": phase,
                "requested_u": float(self._a2_pull_v5_characterization_phase_u[env_id].item()),
                "cell_requested_u": float(self._a2_pull_v5_characterization_requested_u[env_id].item()),
                "xy_primitive": self.config.get(
                    "a2_pull_v5_characterization_xy_primitive", "none"
                ),
                "applied_raw_base_slice": self._a2_pull_v5_characterization_raw_base[
                    env_id
                ].detach().cpu().tolist(),
                "scaled_clipped_physical_base_command": self._a2_pull_v5_characterization_physical_base[
                    env_id
                ].detach().cpu().tolist(),
                "realized_world_yaw_pre": float(
                    self._a2_pull_v5_characterization_pre_root_yaw[env_id].item()
                ),
                "realized_world_yaw_post": float(post_root_yaw[env_id].item()),
                "yaw_delta_rad": float(yaw_delta.item()),
                "yaw_velocity_rad_s": float(yaw_delta.item() / dt),
                "root_pos_pre_world": pre_pos.detach().cpu().tolist(),
                "root_pos_post_world": post_pos.detach().cpu().tolist(),
                "root_motion_xy_world": xy_delta.detach().cpu().tolist(),
                "root_motion_m": float(torch.linalg.norm(xy_delta).item()),
                "control_dt": dt,
            }
            self._a2_pull_v5_characterization_trace_rows.append(row)
        self._a2_pull_v5_characterization_pending[:] = False

    def consume_a2_pull_v5_characterization_trace_rows(self) -> list[dict[str, object]]:
        """Transfer evaluator rows without writing any artifact from the environment."""

        if not self._a2_pull_v5_characterization_enabled:
            raise RuntimeError("HOMIE characterization is not enabled for this evaluator.")
        rows = list(self._a2_pull_v5_characterization_trace_rows)
        self._a2_pull_v5_characterization_trace_rows.clear()
        return rows

    @override
    def _reset_robot_states_callback(self, env_ids, target_states=None):
        super()._reset_robot_states_callback(env_ids, target_states)
        if not self._a2_pull_v5_characterization_enabled:
            return
        root_state = self.target_robot_root_states[env_ids].clone()
        roll, pitch, _ = euler_xyz_from_quat(root_state[:, 3:7])
        root_state[:, 3:7] = quat_from_euler_xyz(
            roll, pitch, torch.full_like(roll, math.pi)
        )
        root_state[:, 7:13] = 0.0
        self.target_robot_root_states[env_ids] = root_state

    @staticmethod
    def _pull_v5_repo_path(raw_path: str, label: str) -> Path:
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
            raise RuntimeError(f"Pull-v5 {label} must be a non-empty repository-relative path.")
        root = Path(__file__).resolve().parents[4]
        path = (root / raw_path).resolve()
        if not path.is_relative_to(root):
            raise RuntimeError(f"Pull-v5 {label} escapes the repository: {raw_path!r}.")
        return path

    @staticmethod
    def _pull_v6_repo_path(raw_path: str, label: str) -> Path:
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
            raise RuntimeError(f"Pull-v6 {label} must be a non-empty repository-relative path.")
        root = Path(__file__).resolve().parents[4]
        path = (root / raw_path).resolve()
        if not path.is_relative_to(root):
            raise RuntimeError(f"Pull-v6 {label} escapes the repository: {raw_path!r}.")
        return path

    def _load_a2_pull_v6_pre_release_bank(self, *, raw_path: str | None = None) -> None:
        bank_path = self._pull_v6_repo_path(
            self.config["a2_pull_v6_stage4_bank_path"] if raw_path is None else raw_path,
            "pre-release bank path",
        )
        if not bank_path.is_file():
            raise FileNotFoundError(f"Pull-v6 pre-release bank is required before construction: {bank_path}")
        payload = torch.load(bank_path, map_location=self.device, weights_only=False)
        if (
            not isinstance(payload, Mapping)
            or payload.get("schema") != A2_PULL_V6_STATE_BANK_V3_SCHEMA
        ):
            raise RuntimeError(
                f"Pull-v6 state bank schema must be {A2_PULL_V6_STATE_BANK_V3_SCHEMA}."
            )
        required = (
            "robot_root_state",
            "robot_dof_pos",
            "robot_dof_vel",
            "door_root_state",
            "door_dof_pos",
            "door_dof_vel",
            "source_env_origin",
            "labels",
            "buffers",
        )
        missing = [name for name in required if name not in payload]
        if missing:
            raise RuntimeError(f"Pull-v6 pre-release bank is missing required fields: {missing}")
        labels = payload["labels"]
        if not isinstance(labels, (list, tuple)):
            raise RuntimeError("Pull-v6 state bank labels must be a row sequence.")
        labels = [str(label) for label in labels]
        expected_labels = [
            "e5_phase_b",
            "pre_release_phase_c",
            "post_release_d1",
            "post_release_d5",
            "post_release_d25",
        ]
        if labels != expected_labels:
            raise RuntimeError("Pull-v6 state bank must contain exactly ordered B/C/D1/D5/D25 rows.")
        bank_row_label = self.config["a2_pull_v6_stage4_bank_row_label"]
        if bank_row_label != "uniform":
            matching_slots = [slot for slot, label in enumerate(labels) if label == bank_row_label]
            if len(matching_slots) != 1:
                raise RuntimeError(
                    f"Pull-v6 Stage-4 bank row selector {bank_row_label!r} must resolve to exactly one slot."
                )
            self._a2_pull_v6_stage4_bank_row_index = matching_slots[0]
        bank_size = len(labels)
        if bank_size > int(self.staged_reset_max_samples_per_stage):
            raise RuntimeError("Pull-v6 pre-release bank exceeds the Stage-4 reset capacity.")
        robot_case = self.staged_reset_buf.get("robot")
        door_case = self.staged_reset_buf.get("door")
        if not isinstance(robot_case, Mapping) or not isinstance(door_case, Mapping):
            raise RuntimeError("Pull-v6 pre-release bank requires tracked robot and door state.")
        expected_tensors = {
            "robot_root_state": robot_case["root_state"].shape[3:],
            "robot_dof_pos": robot_case["dof_state"].shape[3:-1],
            "robot_dof_vel": robot_case["dof_state"].shape[3:-1],
            "door_root_state": door_case["root_state"].shape[3:],
            "door_dof_pos": door_case["dof_state"].shape[3:-1],
            "door_dof_vel": door_case["dof_state"].shape[3:-1],
        }
        expected_dtypes = {
            "robot_root_state": robot_case["root_state"].dtype,
            "robot_dof_pos": robot_case["dof_state"].dtype,
            "robot_dof_vel": robot_case["dof_state"].dtype,
            "door_root_state": door_case["root_state"].dtype,
            "door_dof_pos": door_case["dof_state"].dtype,
            "door_dof_vel": door_case["dof_state"].dtype,
        }
        tensors: dict[str, torch.Tensor] = {}
        for name, row_shape in expected_tensors.items():
            value = payload[name]
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != (bank_size, *row_shape)
                or value.dtype != expected_dtypes[name]
                or value.device != torch.device(self.device)
                or not value.is_floating_point()
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(
                    f"Pull-v6 pre-release bank {name} must be finite with shape "
                    f"{(bank_size, *row_shape)} on {self.device}."
                )
            tensors[name] = value
        source_origin = payload["source_env_origin"]
        if (
            not torch.is_tensor(source_origin)
            or tuple(source_origin.shape) != (bank_size, 3)
            or source_origin.dtype != self.env_origins.dtype
            or source_origin.device != torch.device(self.device)
            or not source_origin.is_floating_point()
            or not torch.all(torch.isfinite(source_origin))
        ):
            raise RuntimeError("Pull-v6 pre-release bank source_env_origin must be finite [bank,3].")
        buffers = payload["buffers"]
        if not isinstance(buffers, Mapping):
            raise RuntimeError("Pull-v6 pre-release bank buffers must be a mapping.")
        registered = {
            name for name, state_case in self.staged_reset_buf.items() if state_case["type"] == "buffer"
        }
        if set(buffers) != registered:
            raise RuntimeError("Pull-v6 pre-release bank buffers must exactly match registered buffers.")
        for name in registered:
            state_case = self.staged_reset_buf[name]
            value = buffers[name]
            expected = (bank_size, *state_case["data"].shape[3:])
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != expected
                or value.dtype != state_case["data"].dtype
                or value.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    f"Pull-v6 pre-release bank buffer {name} must match "
                    f"{expected}/{state_case['data'].dtype}/{self.device}."
                )
            tensors[f"buffer:{name}"] = value
        stage = self.STAGE_SWING
        for env_id in range(self.num_envs):
            target_origin = self.env_origins[env_id]
            for slot in range(bank_size):
                source_origin_row = source_origin[slot]
                origin_delta = target_origin - source_origin_row
                robot_root = tensors["robot_root_state"][slot].clone()
                door_root = tensors["door_root_state"][slot].clone()
                robot_root[:3] += origin_delta
                door_root[:3] += origin_delta
                robot_case["root_state"][stage, slot, env_id] = robot_root
                robot_case["dof_state"][stage, slot, env_id, :, 0] = tensors["robot_dof_pos"][slot]
                robot_case["dof_state"][stage, slot, env_id, :, 1] = tensors["robot_dof_vel"][slot]
                door_case["root_state"][stage, slot, env_id] = door_root
                door_case["dof_state"][stage, slot, env_id, :, 0] = tensors["door_dof_pos"][slot]
                door_case["dof_state"][stage, slot, env_id, :, 1] = tensors["door_dof_vel"][slot]
                for name in registered:
                    value = tensors[f"buffer:{name}"][slot].clone()
                    if name in {"a2_pull_prev_base_pos_xy", "a2_pull_v6_pivot_xy"}:
                        value = value + origin_delta[:2]
                    elif name in {
                        "a2_pull_proof_start_root_x",
                        "a2_pull_proof_last_root_x",
                        "a2_pull_capture_root_x",
                    }:
                        value = value + origin_delta[0]
                    elif name == "a2_pull_v6_prev_tcp_pos_w":
                        value = value + origin_delta
                    elif name == "a2_pull_first_event_step":
                        reached = tensors["buffer:a2_pull_event_reached"][slot]
                        value = torch.where(
                            reached,
                            torch.zeros_like(value),
                            torch.full_like(value, -1),
                        )
                    elif name == "a2_pull_first_event_time_s":
                        reached = tensors["buffer:a2_pull_event_reached"][slot]
                        value = torch.where(
                            reached,
                            torch.zeros_like(value),
                            torch.full_like(value, float("nan")),
                        )
                    self.staged_reset_buf[name]["data"][stage, slot, env_id] = value
        self.staged_reset_num_samples[stage, :] = bank_size
        self._a2_pull_v6_e5_snapshot_pending.zero_()
        self._a2_pull_v6_pre_release_snapshot_pending.zero_()
        self._a2_pull_v6_stage4_bank_loaded = True

    def _load_a2_pull_v61_late_state_bank(self) -> None:
        """Load exact v6.1 late rows into Stage-4/Stage-5 reset slots."""

        if not self._is_a2_pull_v6() or not self.enable_staged_reset:
            raise RuntimeError("Pull-v6.1 late-state bank requires an enabled v6 staged-reset environment.")
        if self.config.get("a2_pull_v6_stage4_bank_enabled", False):
            raise RuntimeError("Pull-v6.1 late-state bank owns Stage-4 injection; disable the legacy v6 bank path.")
        late_path = self._pull_v6_repo_path(
            self.config["a2_pull_v61_late_state_bank_path"], "late-state bank path"
        )
        if not late_path.is_file():
            raise FileNotFoundError(f"Pull-v6.1 late-state bank is required before construction: {late_path}")

        def validate_weights(name: str, allowed: set[str]) -> dict[str, float]:
            raw = self.config[name]
            if not isinstance(raw, Mapping) or not raw or set(raw).difference(allowed):
                raise RuntimeError(f"Pull-v6.1 {name} must be a non-empty canonical row-weight mapping.")
            weights: dict[str, float] = {}
            for label, value in raw.items():
                if (
                    not isinstance(label, str)
                    or isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or float(value) < 0.0
                ):
                    raise RuntimeError(f"Pull-v6.1 {name} has an invalid weight for {label!r}.")
                weights[label] = float(value)
            if not math.isclose(sum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1.0e-6):
                raise RuntimeError(f"Pull-v6.1 {name} weights must sum exactly to 1 within 1e-6.")
            return weights

        stage4_weights = validate_weights(
            "a2_pull_v61_stage4_row_weights",
            {"e5_phase_b", "pre_release_phase_c", "post_release_d25", "frame_passage"},
        )
        stage5_weights = validate_weights(
            "a2_pull_v61_stage5_row_weights", {"e6_stage5_entry"}
        )
        if stage5_weights != {"e6_stage5_entry": 1.0}:
            raise RuntimeError("Pull-v6.1 Stage-5 sampling must select the sole E6 entry row.")
        use_pre_release = any(
            stage4_weights.get(label, 0.0) > 0.0
            for label in ("e5_phase_b", "pre_release_phase_c")
        )
        pre_release_path = self.config.get("a2_pull_v61_pre_release_bank_path")
        if use_pre_release:
            if not isinstance(pre_release_path, str) or not pre_release_path:
                raise RuntimeError("Pull-v6.1 positive B/C row weights require an exact v3 pre-release bank path.")
            self._load_a2_pull_v6_pre_release_bank(raw_path=pre_release_path)
        elif pre_release_path is not None:
            raise RuntimeError("Pull-v6.1 pre-release bank path is only valid when B/C rows have positive weight.")

        payload = torch.load(late_path, map_location=self.device, weights_only=False)
        required = {
            "schema", "robot_root_state", "robot_dof_pos", "robot_dof_vel",
            "door_root_state", "door_dof_pos", "door_dof_vel", "source_env_origin",
            "labels", "buffers", "provenance", "door_metadata",
        }
        if not isinstance(payload, Mapping) or set(payload) != required:
            raise RuntimeError("Pull-v6.1 late-state bank must be an exact v1 payload.")
        if payload["schema"] != A2_PULL_V61_LATE_STATE_BANK_V1_SCHEMA:
            raise RuntimeError(f"Pull-v6.1 late-state bank schema must be {A2_PULL_V61_LATE_STATE_BANK_V1_SCHEMA}.")
        if not isinstance(payload["labels"], (list, tuple)) or tuple(payload["labels"]) != A2_PULL_V61_LATE_STATE_BANK_LABELS:
            raise RuntimeError("Pull-v6.1 late-state bank labels must be ordered D25/frame/E6.")
        bank_size = len(A2_PULL_V61_LATE_STATE_BANK_LABELS)
        if not isinstance(payload["provenance"], (list, tuple)) or len(payload["provenance"]) != bank_size:
            raise RuntimeError("Pull-v6.1 late-state bank provenance must have one row per label.")
        if not isinstance(payload["door_metadata"], (list, tuple)) or len(payload["door_metadata"]) != bank_size:
            raise RuntimeError("Pull-v6.1 late-state bank door metadata must have one row per label.")
        for label, provenance, metadata in zip(
            A2_PULL_V61_LATE_STATE_BANK_LABELS, payload["provenance"], payload["door_metadata"]
        ):
            if (
                not isinstance(provenance, Mapping)
                or set(provenance) != {
                    "source_env_id", "source_control_step", "event_label",
                    "source_checkpoint", "source_config",
                }
                or isinstance(provenance["source_env_id"], bool)
                or not isinstance(provenance["source_env_id"], int)
                or isinstance(provenance["source_control_step"], bool)
                or not isinstance(provenance["source_control_step"], int)
                or provenance["source_control_step"] < 0
                or provenance["event_label"] != label
                or not isinstance(provenance["source_checkpoint"], str)
                or not provenance["source_checkpoint"]
                or not isinstance(provenance["source_config"], str)
                or not provenance["source_config"]
                or not isinstance(metadata, Mapping)
                or set(metadata) != {"door_open_io_sign", "door_open_lr_sign", "travel_dir_x", "hinge_drive_max_force_nm"}
            ):
                raise RuntimeError("Pull-v6.1 late-state bank provenance or door metadata is invalid.")

        robot_case = self.staged_reset_buf.get("robot")
        door_case = self.staged_reset_buf.get("door")
        if not isinstance(robot_case, Mapping) or not isinstance(door_case, Mapping):
            raise RuntimeError("Pull-v6.1 late-state bank requires tracked robot and door state.")
        tensor_specs = {
            "robot_root_state": (robot_case["root_state"].shape[3:], robot_case["root_state"].dtype),
            "robot_dof_pos": (robot_case["dof_state"].shape[3:-1], robot_case["dof_state"].dtype),
            "robot_dof_vel": (robot_case["dof_state"].shape[3:-1], robot_case["dof_state"].dtype),
            "door_root_state": (door_case["root_state"].shape[3:], door_case["root_state"].dtype),
            "door_dof_pos": (door_case["dof_state"].shape[3:-1], door_case["dof_state"].dtype),
            "door_dof_vel": (door_case["dof_state"].shape[3:-1], door_case["dof_state"].dtype),
        }
        for name, (row_shape, dtype) in tensor_specs.items():
            value = payload[name]
            if (
                not torch.is_tensor(value) or tuple(value.shape) != (bank_size, *row_shape)
                or value.dtype != dtype or value.device != torch.device(self.device)
                or not value.is_floating_point() or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(f"Pull-v6.1 late-state bank {name} must be finite {(bank_size, *row_shape)}/{dtype}.")
        source_origin = payload["source_env_origin"]
        if (
            not torch.is_tensor(source_origin) or tuple(source_origin.shape) != (bank_size, 3)
            or source_origin.dtype != self.env_origins.dtype or source_origin.device != torch.device(self.device)
            or not torch.all(torch.isfinite(source_origin))
        ):
            raise RuntimeError("Pull-v6.1 late-state bank source_env_origin must be finite [3,3].")
        buffers = payload["buffers"]
        registered = {name for name, case in self.staged_reset_buf.items() if case["type"] == "buffer"}
        if not isinstance(buffers, Mapping) or set(buffers) != registered:
            raise RuntimeError("Pull-v6.1 late-state bank buffers must exactly match registered buffers.")
        for name in registered:
            value = buffers[name]
            expected = (bank_size, *self.staged_reset_buf[name]["data"].shape[3:])
            if (
                not torch.is_tensor(value) or tuple(value.shape) != expected
                or value.dtype != self.staged_reset_buf[name]["data"].dtype
                or value.device != torch.device(self.device)
            ):
                raise RuntimeError(f"Pull-v6.1 late-state bank buffer {name} must match {expected}.")

        stage4_slots: dict[str, int] = {}
        if use_pre_release:
            stage4_slots.update({"e5_phase_b": 0, "pre_release_phase_c": 1})
        stage4_start = int(self.staged_reset_num_samples[self.STAGE_SWING, 0].item())
        if stage4_start + 2 > int(self.staged_reset_max_samples_per_stage):
            raise RuntimeError("Pull-v6.1 late-state bank exceeds Stage-4 reset capacity.")
        if int(self.staged_reset_num_samples[self.STAGE_THROUGH, 0].item()) + 1 > int(self.staged_reset_max_samples_per_stage):
            raise RuntimeError("Pull-v6.1 late-state bank exceeds Stage-5 reset capacity.")

        def write_row(stage: int, slot: int, row: int) -> None:
            for env_id in range(self.num_envs):
                origin_delta = self.env_origins[env_id] - source_origin[row]
                robot_root = payload["robot_root_state"][row].clone()
                door_root = payload["door_root_state"][row].clone()
                robot_root[:3] += origin_delta
                door_root[:3] += origin_delta
                robot_case["root_state"][stage, slot, env_id] = robot_root
                robot_case["dof_state"][stage, slot, env_id, :, 0] = payload["robot_dof_pos"][row]
                robot_case["dof_state"][stage, slot, env_id, :, 1] = payload["robot_dof_vel"][row]
                door_case["root_state"][stage, slot, env_id] = door_root
                door_case["dof_state"][stage, slot, env_id, :, 0] = payload["door_dof_pos"][row]
                door_case["dof_state"][stage, slot, env_id, :, 1] = payload["door_dof_vel"][row]
                for name in registered:
                    value = buffers[name][row].clone()
                    if name in {"a2_pull_prev_base_pos_xy", "a2_pull_v6_pivot_xy"}:
                        value = value + origin_delta[:2]
                    elif name in {"a2_pull_proof_start_root_x", "a2_pull_proof_last_root_x", "a2_pull_capture_root_x"}:
                        value = value + origin_delta[0]
                    elif name == "a2_pull_v6_prev_tcp_pos_w":
                        value = value + origin_delta
                    elif name == "a2_pull_first_event_step":
                        reached = buffers["a2_pull_event_reached"][row]
                        value = torch.where(reached, torch.zeros_like(value), torch.full_like(value, -1))
                    elif name == "a2_pull_first_event_time_s":
                        reached = buffers["a2_pull_event_reached"][row]
                        value = torch.where(reached, torch.zeros_like(value), torch.full_like(value, float("nan")))
                    self.staged_reset_buf[name]["data"][stage, slot, env_id] = value

        write_row(self.STAGE_SWING, stage4_start, 0)
        write_row(self.STAGE_SWING, stage4_start + 1, 1)
        write_row(self.STAGE_THROUGH, 0, 2)
        self.staged_reset_num_samples[self.STAGE_SWING, :] = stage4_start + 2
        self.staged_reset_num_samples[self.STAGE_THROUGH, :] = 1
        stage4_slots.update({"post_release_d25": stage4_start, "frame_passage": stage4_start + 1})
        self._a2_pull_v61_stage4_bank_slots = stage4_slots
        self._a2_pull_v61_stage4_row_weights = stage4_weights
        self._a2_pull_v61_stage5_row_weights = stage5_weights
        self._a2_pull_v61_last_reset_source = [
            {"label": "not_sampled", "stage": None, "sample_index": None}
            for _ in range(self.num_envs)
        ]

    def _broadcast_a2_pull_v6_first_natural_c_snapshot(
        self, source_env_id: int, source_slot: int
    ) -> None:
        """Copy the first natural Phase-C Stage-4 row into every environment's slot zero."""

        stage = self.STAGE_SWING
        robot_case = self.staged_reset_buf["robot"]
        door_case = self.staged_reset_buf["door"]
        source_origin = self.env_origins[source_env_id]
        source_robot_root = robot_case["root_state"][stage, source_slot, source_env_id].clone()
        source_door_root = door_case["root_state"][stage, source_slot, source_env_id].clone()
        source_robot_dof = robot_case["dof_state"][stage, source_slot, source_env_id].clone()
        source_door_dof = door_case["dof_state"][stage, source_slot, source_env_id].clone()
        for target_env_id in range(self.num_envs):
            origin_delta = self.env_origins[target_env_id] - source_origin
            robot_root = source_robot_root.clone()
            door_root = source_door_root.clone()
            robot_root[:3] += origin_delta
            door_root[:3] += origin_delta
            robot_case["root_state"][stage, 0, target_env_id] = robot_root
            robot_case["dof_state"][stage, 0, target_env_id] = source_robot_dof
            door_case["root_state"][stage, 0, target_env_id] = door_root
            door_case["dof_state"][stage, 0, target_env_id] = source_door_dof
            for name, state_case in self.staged_reset_buf.items():
                if state_case["type"] != "buffer":
                    continue
                value = state_case["data"][stage, source_slot, source_env_id].clone()
                if name in {"a2_pull_prev_base_pos_xy", "a2_pull_v6_pivot_xy"}:
                    value = value + origin_delta[:2]
                elif name in {
                    "a2_pull_proof_start_root_x",
                    "a2_pull_proof_last_root_x",
                    "a2_pull_capture_root_x",
                }:
                    value = value + origin_delta[0]
                elif name == "a2_pull_v6_prev_tcp_pos_w":
                    value = value + origin_delta
                state_case["data"][stage, 0, target_env_id] = value
        self.staged_reset_num_samples[stage, :] = 1
        self._a2_pull_v6_e5_snapshot_pending.zero_()
        self._a2_pull_v6_pre_release_snapshot_pending.zero_()
        self._a2_pull_v6_d1_snapshot_captured.fill_(True)
        self._a2_pull_v6_d5_snapshot_captured.fill_(True)
        self._a2_pull_v6_d25_snapshot_captured.fill_(True)
        self._a2_pull_v6_first_natural_c_broadcast_done = True

    def export_a2_pull_v6_pre_release_bank(self, output_path: str) -> dict[str, object]:
        if not self._is_a2_pull_v6():
            raise RuntimeError("Pull-v6 pre-release export requires the v6 pull plan.")
        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError("Pull-v6 pre-release export requires staged-reset snapshots.")
        stage = self.STAGE_SWING
        counts = self.staged_reset_num_samples[stage]
        if torch.any(counts < 0) or torch.any(counts > self.staged_reset_max_samples_per_stage):
            raise RuntimeError("Pull-v6 pre-release export has invalid Stage-4 snapshot counts.")
        robot_case = self.staged_reset_buf.get("robot")
        door_case = self.staged_reset_buf.get("door")
        subphase_case = self.staged_reset_buf.get("a2_pull_v6_subphase")
        persistence_case = self.staged_reset_buf.get("a2_pull_v6_release_persistence")
        if (
            not isinstance(robot_case, Mapping)
            or not isinstance(door_case, Mapping)
            or not isinstance(subphase_case, Mapping)
            or not isinstance(persistence_case, Mapping)
        ):
            raise RuntimeError("Pull-v6 state-bank export requires tracked robot, door, subphase, and persistence state.")
        rows: list[tuple[int, int, str]] = []
        for env_id in torch.where(counts > 0)[0].tolist():
            for slot in range(int(counts[env_id].item())):
                phase = int(subphase_case["data"][stage, slot, env_id].item())
                if phase == self._A2_PULL_V6_PHASE_B:
                    label = "e5_phase_b"
                elif phase == self._A2_PULL_V6_PHASE_C:
                    label = "pre_release_phase_c"
                elif phase == self._A2_PULL_V6_PHASE_D:
                    persistence = int(persistence_case["data"][stage, slot, env_id].item())
                    d_labels = {
                        1: "post_release_d1",
                        5: "post_release_d5",
                        25: "post_release_d25",
                    }
                    if persistence not in d_labels:
                        raise RuntimeError("Pull-v6 state-bank export encountered an unsupported Phase-D persistence row.")
                    label = d_labels[persistence]
                else:
                    raise RuntimeError("Pull-v6 state-bank export encountered an unsupported subphase row.")
                rows.append((env_id, slot, label))
        if not rows:
            raise RuntimeError("Pull-v6 pre-release export has no Stage-4 rows.")
        labels = [label for _, _, label in rows]
        expected_labels = [
            "e5_phase_b",
            "pre_release_phase_c",
            "post_release_d1",
            "post_release_d5",
            "post_release_d25",
        ]
        registered = {
            name for name, state_case in self.staged_reset_buf.items() if state_case["type"] == "buffer"
        }
        overlay_base_path = self.config.get("a2_pull_v6_bank_overlay_base_path")
        near_c_capture_mode = self._a2_pull_v6_near_c_capture_mode
        if near_c_capture_mode != "none" and overlay_base_path is None:
            raise RuntimeError("Pull-v6 near-C capture export requires an overlay base path.")
        def stack(case: Mapping[str, object], key: str) -> torch.Tensor:
            return torch.stack([case[key][stage, slot, env_id] for env_id, slot, _ in rows])
        if overlay_base_path is None:
            if labels != expected_labels:
                raise RuntimeError("Pull-v6 state-bank export requires exactly ordered B/C/D1/D5/D25 rows.")
            payload: dict[str, object] = {
                "schema": A2_PULL_V6_STATE_BANK_V3_SCHEMA,
                "robot_root_state": stack(robot_case, "root_state").detach().cpu(),
                "robot_dof_pos": torch.stack(
                    [robot_case["dof_state"][stage, slot, env_id, :, 0] for env_id, slot, _ in rows]
                ).detach().cpu(),
                "robot_dof_vel": torch.stack(
                    [robot_case["dof_state"][stage, slot, env_id, :, 1] for env_id, slot, _ in rows]
                ).detach().cpu(),
                "door_root_state": stack(door_case, "root_state").detach().cpu(),
                "door_dof_pos": torch.stack(
                    [door_case["dof_state"][stage, slot, env_id, :, 0] for env_id, slot, _ in rows]
                ).detach().cpu(),
                "door_dof_vel": torch.stack(
                    [door_case["dof_state"][stage, slot, env_id, :, 1] for env_id, slot, _ in rows]
                ).detach().cpu(),
                "source_env_origin": torch.stack(
                    [self.env_origins[env_id] for env_id, _, _ in rows]
                ).detach().cpu(),
                "labels": labels,
                "buffers": {},
            }
            buffers = payload["buffers"]
            assert isinstance(buffers, dict)
            for name in registered:
                state_case = self.staged_reset_buf[name]
                buffers[name] = torch.stack(
                    [state_case["data"][stage, slot, env_id] for env_id, slot, _ in rows]
                ).detach().cpu()
        else:
            if near_c_capture_mode != "none":
                source_ids = torch.where(
                    self._a2_pull_v6_near_c_snapshot_captured
                    & (self._a2_pull_v6_near_c_snapshot_slot >= 0)
                )[0]
                if source_ids.numel() == 0:
                    raise RuntimeError("Pull-v6 near-C capture export found no marked natural Phase-B snapshot.")
                source_env_id = int(source_ids[0].item())
                source_slot = int(self._a2_pull_v6_near_c_snapshot_slot[source_env_id].item())
                if source_slot >= int(counts[source_env_id].item()):
                    raise RuntimeError("Pull-v6 near-C capture snapshot slot is outside the stored Stage-4 count.")
                if int(subphase_case["data"][stage, source_slot, source_env_id].item()) != self._A2_PULL_V6_PHASE_B:
                    raise RuntimeError("Pull-v6 near-C capture marker must point to a Phase-B snapshot.")
                replacement_rows = ((0, source_slot),)
            else:
                source_env_id = None
                source_b_slot = None
                source_c_slot = None
                for env_id in torch.where(counts > 0)[0].tolist():
                    b_slot = None
                    for slot in range(int(counts[env_id].item())):
                        phase = int(subphase_case["data"][stage, slot, env_id].item())
                        if phase == self._A2_PULL_V6_PHASE_B and b_slot is None:
                            b_slot = slot
                        elif phase == self._A2_PULL_V6_PHASE_C and b_slot is not None:
                            source_env_id = env_id
                            source_b_slot = b_slot
                            source_c_slot = slot
                            break
                    if source_env_id is not None:
                        break
                if source_env_id is None or source_b_slot is None or source_c_slot is None:
                    raise RuntimeError("Pull-v6 overlay export requires natural Phase-B then Phase-C snapshots from one environment.")
                replacement_rows = ((0, source_b_slot), (1, source_c_slot))
            base_path = self._pull_v6_repo_path(overlay_base_path, "overlay base path")
            if not base_path.is_file():
                raise FileNotFoundError(f"Pull-v6 overlay base bank is required: {base_path}")
            base = torch.load(base_path, map_location="cpu", weights_only=False)
            required = {
                "schema", "robot_root_state", "robot_dof_pos", "robot_dof_vel", "door_root_state",
                "door_dof_pos", "door_dof_vel", "source_env_origin", "labels", "buffers",
            }
            if not isinstance(base, Mapping) or set(base) != required:
                raise RuntimeError("Pull-v6 overlay base bank must be an exact v3 payload.")
            if (
                base["schema"] != A2_PULL_V6_STATE_BANK_V3_SCHEMA
                or not isinstance(base["labels"], (list, tuple))
                or list(base["labels"]) != expected_labels
            ):
                raise RuntimeError("Pull-v6 overlay base bank must carry ordered v3 B/C/D1/D5/D25 labels.")
            base_buffers = base["buffers"]
            if not isinstance(base_buffers, Mapping) or set(base_buffers) != registered:
                raise RuntimeError("Pull-v6 overlay base bank buffers must exactly match registered buffers.")
            tensor_shapes = {
                "robot_root_state": robot_case["root_state"].shape[3:],
                "robot_dof_pos": robot_case["dof_state"].shape[3:-1],
                "robot_dof_vel": robot_case["dof_state"].shape[3:-1],
                "door_root_state": door_case["root_state"].shape[3:],
                "door_dof_pos": door_case["dof_state"].shape[3:-1],
                "door_dof_vel": door_case["dof_state"].shape[3:-1],
            }
            for name, row_shape in tensor_shapes.items():
                value = base[name]
                expected = (len(expected_labels), *row_shape)
                state_case = robot_case if name.startswith("robot_") else door_case
                expected_dtype = state_case["root_state"].dtype if name.endswith("root_state") else state_case["dof_state"].dtype
                if (
                    not torch.is_tensor(value)
                    or tuple(value.shape) != expected
                    or value.dtype != expected_dtype
                    or not torch.all(torch.isfinite(value))
                ):
                    raise RuntimeError(f"Pull-v6 overlay base bank {name} must be finite {expected}/{expected_dtype}.")
            source_origin = base["source_env_origin"]
            if (
                not torch.is_tensor(source_origin)
                or tuple(source_origin.shape) != (len(expected_labels), 3)
                or source_origin.dtype != self.env_origins.dtype
                or not torch.all(torch.isfinite(source_origin))
            ):
                raise RuntimeError("Pull-v6 overlay base bank source_env_origin must be finite [5,3].")
            for name in registered:
                state_case = self.staged_reset_buf[name]
                expected = (len(expected_labels), *state_case["data"].shape[3:])
                value = base_buffers[name]
                if (
                    not torch.is_tensor(value)
                    or tuple(value.shape) != expected
                    or value.dtype != state_case["data"].dtype
                ):
                    raise RuntimeError(
                        f"Pull-v6 overlay base bank buffer {name} must match "
                        f"{expected}/{state_case['data'].dtype}."
                    )
            payload = {
                "schema": A2_PULL_V6_STATE_BANK_V3_SCHEMA,
                "robot_root_state": base["robot_root_state"].clone(),
                "robot_dof_pos": base["robot_dof_pos"].clone(),
                "robot_dof_vel": base["robot_dof_vel"].clone(),
                "door_root_state": base["door_root_state"].clone(),
                "door_dof_pos": base["door_dof_pos"].clone(),
                "door_dof_vel": base["door_dof_vel"].clone(),
                "source_env_origin": source_origin.clone(),
                "labels": list(expected_labels),
                "buffers": {name: base_buffers[name].clone() for name in registered},
            }
            for row, slot in replacement_rows:
                payload["robot_root_state"][row] = robot_case["root_state"][stage, slot, source_env_id].detach().cpu()
                payload["robot_dof_pos"][row] = robot_case["dof_state"][stage, slot, source_env_id, :, 0].detach().cpu()
                payload["robot_dof_vel"][row] = robot_case["dof_state"][stage, slot, source_env_id, :, 1].detach().cpu()
                payload["door_root_state"][row] = door_case["root_state"][stage, slot, source_env_id].detach().cpu()
                payload["door_dof_pos"][row] = door_case["dof_state"][stage, slot, source_env_id, :, 0].detach().cpu()
                payload["door_dof_vel"][row] = door_case["dof_state"][stage, slot, source_env_id, :, 1].detach().cpu()
                payload["source_env_origin"][row] = self.env_origins[source_env_id].detach().cpu()
                buffers = payload["buffers"]
                assert isinstance(buffers, dict)
                for name in registered:
                    buffers[name][row] = self.staged_reset_buf[name]["data"][stage, slot, source_env_id].detach().cpu()
        path = self._pull_v6_repo_path(output_path, "pre-release bank capture path")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Pull-v6 pre-release bank capture refuses to overwrite {path}.")
        torch.save(payload, path)
        return {
            "schema": A2_PULL_V6_STATE_BANK_V3_SCHEMA,
            "status": "PASS",
            "samples": len(rows),
            "output": str(path),
        }

    def export_a2_pull_v61_late_state_bank(self, output_path: str) -> dict[str, object]:
        """Export the exact D25/frame/E6 post-physics bank without LSTM state."""

        if not self._is_a2_pull_v6() or not self._a2_pull_v61_late_state_bank_capture_enabled:
            raise RuntimeError("Pull-v6.1 late-state export requires its explicit capture mode.")
        captures = (
            (
                "post_release_d25", self.STAGE_SWING, self._a2_pull_v61_d25_snapshot_captured,
                self._a2_pull_v61_d25_snapshot_slot, self._a2_pull_v61_d25_snapshot_step,
            ),
            (
                "frame_passage", self.STAGE_SWING, self._a2_pull_v61_frame_snapshot_captured,
                self._a2_pull_v61_frame_snapshot_slot, self._a2_pull_v61_frame_snapshot_step,
            ),
            (
                "e6_stage5_entry", self.STAGE_THROUGH, self._a2_pull_v61_e6_snapshot_captured,
                self._a2_pull_v61_e6_snapshot_slot, self._a2_pull_v61_e6_snapshot_step,
            ),
        )
        overlay_base_path = self._a2_pull_v61_late_state_bank_overlay_base_path
        selected_captures = captures[:1] if overlay_base_path is not None else captures
        rows: list[tuple[str, int, int, int, int]] = []
        for label, stage, captured, slots, steps in selected_captures:
            env_ids = torch.where(captured & (slots >= 0) & (steps >= 0))[0]
            if env_ids.numel() != 1:
                raise RuntimeError(f"Pull-v6.1 late-state export requires exactly one captured {label} row.")
            env_id = int(env_ids.item())
            rows.append((label, stage, env_id, int(slots[env_id].item()), int(steps[env_id].item())))
        robot_case = self.staged_reset_buf.get("robot")
        door_case = self.staged_reset_buf.get("door")
        if not isinstance(robot_case, Mapping) or not isinstance(door_case, Mapping):
            raise RuntimeError("Pull-v6.1 late-state export requires tracked robot and door state.")
        registered = {name for name, case in self.staged_reset_buf.items() if case["type"] == "buffer"}
        captured_payload: dict[str, object] = {
            "schema": A2_PULL_V61_LATE_STATE_BANK_V1_SCHEMA,
            "robot_root_state": torch.stack([
                robot_case["root_state"][stage, slot, env_id] for _, stage, env_id, slot, _ in rows
            ]).detach().cpu(),
            "robot_dof_pos": torch.stack([
                robot_case["dof_state"][stage, slot, env_id, :, 0] for _, stage, env_id, slot, _ in rows
            ]).detach().cpu(),
            "robot_dof_vel": torch.stack([
                robot_case["dof_state"][stage, slot, env_id, :, 1] for _, stage, env_id, slot, _ in rows
            ]).detach().cpu(),
            "door_root_state": torch.stack([
                door_case["root_state"][stage, slot, env_id] for _, stage, env_id, slot, _ in rows
            ]).detach().cpu(),
            "door_dof_pos": torch.stack([
                door_case["dof_state"][stage, slot, env_id, :, 0] for _, stage, env_id, slot, _ in rows
            ]).detach().cpu(),
            "door_dof_vel": torch.stack([
                door_case["dof_state"][stage, slot, env_id, :, 1] for _, stage, env_id, slot, _ in rows
            ]).detach().cpu(),
            "source_env_origin": torch.stack([
                self.env_origins[env_id] for _, _, env_id, _, _ in rows
            ]).detach().cpu(),
            "labels": [label for label, _, _, _, _ in rows],
            "buffers": {
                name: torch.stack([
                    self.staged_reset_buf[name]["data"][stage, slot, env_id]
                    for _, stage, env_id, slot, _ in rows
                ]).detach().cpu()
                for name in registered
            },
            "provenance": [
                {
                    "source_env_id": env_id,
                    "source_control_step": step,
                    "event_label": label,
                    "source_checkpoint": self._a2_pull_v61_late_state_bank_capture_source_checkpoint,
                    "source_config": self._a2_pull_v61_late_state_bank_capture_source_config,
                }
                for label, _, env_id, _, step in rows
            ],
            "door_metadata": [
                {
                    "door_open_io_sign": self._pull_direction.io_sign,
                    "door_open_lr_sign": self._pull_direction.door_open_lr_sign,
                    "travel_dir_x": self._pull_direction.travel_dir_x,
                    "hinge_drive_max_force_nm": float(self.door_hinge_drive_max_force[env_id].item()),
                }
                for _, _, env_id, _, _ in rows
            ],
        }
        if overlay_base_path is None:
            payload = captured_payload
        else:
            base_path = self._pull_v6_repo_path(overlay_base_path, "late-state overlay base path")
            if not base_path.is_file():
                raise FileNotFoundError(f"Pull-v6.1 late-state overlay base bank is required: {base_path}")
            base = torch.load(base_path, map_location="cpu", weights_only=False)
            required = {
                "schema", "robot_root_state", "robot_dof_pos", "robot_dof_vel", "door_root_state",
                "door_dof_pos", "door_dof_vel", "source_env_origin", "labels", "buffers",
                "provenance", "door_metadata",
            }
            if not isinstance(base, Mapping) or set(base) != required:
                raise RuntimeError("Pull-v6.1 late-state overlay base bank must be an exact v1 payload.")
            if (
                base["schema"] != A2_PULL_V61_LATE_STATE_BANK_V1_SCHEMA
                or list(base["labels"]) != list(A2_PULL_V61_LATE_STATE_BANK_LABELS)
                or len(base["provenance"]) != len(A2_PULL_V61_LATE_STATE_BANK_LABELS)
                or len(base["door_metadata"]) != len(A2_PULL_V61_LATE_STATE_BANK_LABELS)
            ):
                raise RuntimeError("Pull-v6.1 late-state overlay base bank labels/provenance are invalid.")
            if set(base["buffers"]) != registered:
                raise RuntimeError("Pull-v6.1 late-state overlay base bank buffers must match registered buffers.")
            payload = {
                "schema": A2_PULL_V61_LATE_STATE_BANK_V1_SCHEMA,
                "robot_root_state": base["robot_root_state"].clone(),
                "robot_dof_pos": base["robot_dof_pos"].clone(),
                "robot_dof_vel": base["robot_dof_vel"].clone(),
                "door_root_state": base["door_root_state"].clone(),
                "door_dof_pos": base["door_dof_pos"].clone(),
                "door_dof_vel": base["door_dof_vel"].clone(),
                "source_env_origin": base["source_env_origin"].clone(),
                "labels": list(base["labels"]),
                "buffers": {name: base["buffers"][name].clone() for name in registered},
                "provenance": [dict(item) for item in base["provenance"]],
                "door_metadata": [dict(item) for item in base["door_metadata"]],
            }
            for name in (
                "robot_root_state", "robot_dof_pos", "robot_dof_vel", "door_root_state",
                "door_dof_pos", "door_dof_vel", "source_env_origin",
            ):
                payload[name][0] = captured_payload[name][0]
            for name in registered:
                payload["buffers"][name][0] = captured_payload["buffers"][name][0]
            payload["provenance"][0] = captured_payload["provenance"][0]
            payload["door_metadata"][0] = captured_payload["door_metadata"][0]
        path = self._pull_v6_repo_path(output_path, "late-state bank capture path")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Pull-v6.1 late-state bank capture refuses to overwrite {path}.")
        torch.save(payload, path)
        return {"schema": A2_PULL_V61_LATE_STATE_BANK_V1_SCHEMA, "status": "PASS", "output": str(path)}

    def _load_a2_pull_v5_state_bank(self) -> None:
        enabled = self.config["a2_pull_v5_stage4_bank_injection_enabled"]
        if not isinstance(enabled, bool):
            raise RuntimeError("Pull-v5 stage4 bank injection must be an explicit bool.")
        if enabled is False:
            return
        self._load_a2_pull_v5_bank_payload(eval_mode=False)

    def _load_a2_pull_v5_eval_state_bank(self) -> None:
        """Load canonical evaluation rows without enabling training injection."""

        enabled = self.config["a2_pull_v5_stage4_bank_injection_enabled"]
        if enabled is not False:
            raise RuntimeError("Canonical evaluation bank provider requires injection=false.")
        reset_source = self.config.get("a2_pull_v5_reset_source")
        if reset_source not in {
            "bank_natural_e5",
            "bank_natural_e5_plus",
            "bank_constructed",
            "bank_natural_e5_override",
        }:
            raise RuntimeError(
                "Canonical evaluation requires reset_source bank_natural_e5, "
                f"bank_natural_e5_plus, bank_constructed, or bank_natural_e5_override; got {reset_source!r}."
            )
        self._load_a2_pull_v5_bank_payload(eval_mode=True)

    @staticmethod
    def _pull_v5_metadata_sequence(payload: Mapping[str, object], key: str, count: int) -> list[object]:
        value = payload.get(key)
        if not isinstance(value, (list, tuple)) or len(value) != count:
            raise RuntimeError(f"Pull-v5 state bank metadata {key!r} must have one entry per row.")
        return list(value)

    def _select_a2_pull_v5_eval_bank_indices(
        self,
        provenance: list[str],
        closer_buckets: list[str],
    ) -> list[int]:
        requested_bucket = self.config.get("a2_pull_v5_eval_closer_bucket", "all")
        if requested_bucket != "all" and requested_bucket not in A2_PULL_V5_CLOSER_BUCKETS:
            raise RuntimeError(
                "Pull-v5 eval closer bucket must be 'all' or one of "
                f"{A2_PULL_V5_CLOSER_BUCKETS!r}; got {requested_bucket!r}."
            )
        count = self.config.get("a2_pull_v5_eval_state_count", 16)
        if isinstance(count, bool) or not isinstance(count, int) or count != 16:
            raise RuntimeError("Pull-v5 canonical evaluation requires exactly 16 bank rows.")
        candidates = [
            index
            for index, bucket in enumerate(closer_buckets)
            if requested_bucket == "all" or bucket == requested_bucket
        ]
        if len(candidates) < count:
            raise RuntimeError(
                f"Pull-v5 canonical evaluation requires 16 rows for bucket {requested_bucket!r}; "
                f"got {len(candidates)}."
            )
        by_group: dict[tuple[str, str], list[int]] = {}
        for index in candidates:
            by_group.setdefault((provenance[index], closer_buckets[index]), []).append(index)
        selected: list[int] = []
        group_order = tuple(sorted(by_group))
        while len(selected) < count:
            progressed = False
            for group in group_order:
                rows = by_group[group]
                if rows:
                    selected.append(rows.pop(0))
                    progressed = True
                    if len(selected) == count:
                        break
            if not progressed:
                raise RuntimeError("Pull-v5 canonical evaluation bank selection exhausted rows.")
        return selected

    @staticmethod
    def _select_a2_pull_v5_training_bank_indices(
        provenance: list[str], closer_buckets: list[str], count: int
    ) -> list[int]:
        if count <= 0:
            raise RuntimeError("Pull-v5 training bank selection requires a positive count.")
        groups: dict[tuple[str, str], list[int]] = {}
        for index, key in enumerate(zip(provenance, closer_buckets)):
            groups.setdefault(key, []).append(index)
        selected: list[int] = []
        for rows in groups.values():
            rows.sort()
        while len(selected) < count:
            progressed = False
            for key in sorted(groups):
                rows = groups[key]
                if rows:
                    selected.append(rows.pop(0))
                    progressed = True
                    if len(selected) == count:
                        break
            if not progressed:
                raise RuntimeError("Pull-v5 training bank selection exhausted rows.")
        return selected

    def _load_a2_pull_v5_bank_payload(self, *, eval_mode: bool) -> None:
        bank_path = self._pull_v5_repo_path(
            self.config["a2_pull_v5_state_bank_path"], "state bank path"
        )
        if not bank_path.is_file():
            raise FileNotFoundError(f"Pull-v5 state bank is required before v5 construction: {bank_path}")
        payload = torch.load(bank_path, map_location=self.device, weights_only=False)
        if not isinstance(payload, Mapping) or payload.get("schema") != A2_PULL_V5_STATE_BANK_SCHEMA:
            raise RuntimeError(f"Pull-v5 state bank schema must be {A2_PULL_V5_STATE_BANK_SCHEMA}.")
        required = (
            "robot_root_state",
            "robot_dof_pos",
            "robot_dof_vel",
            "door_root_state",
            "door_dof_pos",
            "door_dof_vel",
            "source_env_origin",
            "provenance",
            "buffers",
            "hinge_drive_max_force_nm",
            "closer_bucket",
            "capture_tier",
            "capture_delay_steps",
            "settle_valid",
            "settle_steps",
            "source_row",
        )
        missing = [name for name in required if name not in payload]
        if missing:
            raise RuntimeError(f"Pull-v5 state bank is missing required fields: {missing}")
        bank_size = len(payload["provenance"])
        minimum = int(self.config["a2_pull_v5_state_bank_min_samples"])
        if bank_size < minimum:
            raise RuntimeError(f"Pull-v5 state bank has {bank_size} samples; minimum is {minimum}.")
        if bank_size < 1 or not isinstance(payload["provenance"], (list, tuple)):
            raise RuntimeError("Pull-v5 state bank provenance must be a non-empty sequence.")
        provenance = [str(item) for item in payload["provenance"]]
        if provenance[0] != "bank_natural_e5":
            raise RuntimeError("Pull-v5 state bank must prioritize source A bank_natural_e5 entries first.")
        if any(item not in {"bank_natural_e5", "bank_natural_e5_plus", "bank_constructed"} for item in provenance):
            raise RuntimeError(
                "Pull-v5 state bank provenance must use only bank_natural_e5, "
                "bank_natural_e5_plus, or bank_constructed."
            )
        force_values = self._pull_v5_metadata_sequence(payload, "hinge_drive_max_force_nm", bank_size)
        bucket_values = [str(item) for item in self._pull_v5_metadata_sequence(payload, "closer_bucket", bank_size)]
        capture_tiers = [str(item) for item in self._pull_v5_metadata_sequence(payload, "capture_tier", bank_size)]
        capture_delay_steps = self._pull_v5_metadata_sequence(payload, "capture_delay_steps", bank_size)
        settle_valid = self._pull_v5_metadata_sequence(payload, "settle_valid", bank_size)
        settle_steps = self._pull_v5_metadata_sequence(payload, "settle_steps", bank_size)
        source_rows = self._pull_v5_metadata_sequence(payload, "source_row", bank_size)
        if any(bucket not in A2_PULL_V5_CLOSER_BUCKETS for bucket in bucket_values):
            raise RuntimeError("Pull-v5 state bank closer_bucket metadata contains an unsupported bucket.")
        if any(tier not in {"e5", "e5_plus_2s", "e5_plus_4s", "constructed"} for tier in capture_tiers):
            raise RuntimeError("Pull-v5 state bank capture_tier metadata contains an unsupported tier.")
        for index, (source, tier) in enumerate(zip(provenance, capture_tiers)):
            expected_tiers = {
                "bank_natural_e5": {"e5"},
                "bank_natural_e5_plus": {"e5_plus_2s", "e5_plus_4s"},
                "bank_constructed": {"constructed"},
            }[source]
            if tier not in expected_tiers:
                raise RuntimeError(
                    f"Pull-v5 bank row {index} capture tier {tier!r} contradicts provenance {source!r}."
                )
        for index, (force, valid, steps, capture_delay, source_row) in enumerate(
            zip(force_values, settle_valid, settle_steps, capture_delay_steps, source_rows)
        ):
            if isinstance(force, bool) or not isinstance(force, (int, float)) or not math.isfinite(float(force)):
                raise RuntimeError(f"Pull-v5 bank closer force row {index} must be finite numeric.")
            if not isinstance(valid, bool) or not valid:
                raise RuntimeError(f"Pull-v5 bank row {index} is not settle-valid.")
            if isinstance(steps, bool) or not isinstance(steps, int) or steps < 50:
                raise RuntimeError(f"Pull-v5 bank settle_steps row {index} must be >=50.")
            if isinstance(capture_delay, bool) or not isinstance(capture_delay, int) or capture_delay < 0:
                raise RuntimeError(
                    f"Pull-v5 bank capture_delay_steps row {index} must be a non-negative integer."
                )
            if isinstance(source_row, bool) or not isinstance(source_row, int) or source_row < 0:
                raise RuntimeError(f"Pull-v5 bank source_row {index} must be a non-negative integer.")
        counts = Counter(provenance)
        allow_g8_pure_a = self.config["a2_pull_v5_state_bank_allow_g8_pure_a"]
        if not isinstance(allow_g8_pure_a, bool):
            raise RuntimeError("Pull-v5 G8 pure-Source-A allowance must be an explicit bool.")
        if counts["bank_natural_e5_plus"] < 8 and not allow_g8_pure_a:
            raise RuntimeError("Pull-v5 state bank does not satisfy G13 natural_e5_plus count.")
        if counts["bank_constructed"] < 16 and not allow_g8_pure_a:
            raise RuntimeError("Pull-v5 state bank does not satisfy G13 provenance counts.")
        if set(bucket_values) != set(A2_PULL_V5_CLOSER_BUCKETS):
            raise RuntimeError("Pull-v5 state bank must populate all closer buckets.")
        source_origin = payload["source_env_origin"]
        if (
            not torch.is_tensor(source_origin)
            or tuple(source_origin.shape) != (bank_size, 3)
            or source_origin.device != torch.device(self.device)
            or not torch.is_floating_point(source_origin)
            or not torch.all(torch.isfinite(source_origin))
        ):
            raise RuntimeError("Pull-v5 source_env_origin must have shape [bank, 3].")
        tensors: dict[str, torch.Tensor] = {}
        expected_shapes = {
            "robot_root_state": (bank_size, 13),
            "robot_dof_pos": (bank_size, self.simulator.scene.articulations["robot"].num_joints),
            "robot_dof_vel": (bank_size, self.simulator.scene.articulations["robot"].num_joints),
            "door_root_state": (bank_size, 13),
            "door_dof_pos": (bank_size, self.simulator.scene.articulations["door"].num_joints),
            "door_dof_vel": (bank_size, self.simulator.scene.articulations["door"].num_joints),
        }
        for name, shape in expected_shapes.items():
            value = payload[name]
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != shape
                or value.device != torch.device(self.device)
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(
                    f"Pull-v5 bank {name} must match shape/device {shape}/{self.device}; "
                    f"got {getattr(value, 'shape', None)}/{getattr(value, 'device', None)}."
                )
            tensors[name] = value
        buffers = payload["buffers"]
        if not isinstance(buffers, Mapping):
            raise RuntimeError("Pull-v5 state bank buffers must be a mapping keyed by every registered buffer.")
        for name, state_case in self.staged_reset_buf.items():
            if state_case["type"] != "buffer":
                continue
            if name not in buffers:
                raise RuntimeError(f"Pull-v5 state bank is missing registered buffer {name!r}.")
            value = buffers[name]
            expected = (bank_size, *state_case["data"].shape[3:])
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != expected
                or value.dtype != state_case["data"].dtype
                or value.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    f"Pull-v5 bank buffer {name} must match {expected}/{state_case['data'].dtype}; "
                    f"got {getattr(value, 'shape', None)}/{getattr(value, 'dtype', None)}."
                )
            tensors[f"buffer:{name}"] = value
        if eval_mode:
            selected_indices = self._select_a2_pull_v5_eval_bank_indices(provenance, bucket_values)
        else:
            selected_indices = self._select_a2_pull_v5_training_bank_indices(
                provenance,
                bucket_values,
                min(int(self.staged_reset_max_samples_per_stage), bank_size),
            )
        self._a2_pull_v5_bank = {**tensors, "source_env_origin": source_origin}
        self._a2_pull_v5_bank_metadata = {
            "hinge_drive_max_force_nm": [float(value) for value in force_values],
            "closer_bucket": bucket_values,
            "capture_tier": capture_tiers,
            "capture_delay_steps": [int(value) for value in capture_delay_steps],
            "settle_valid": settle_valid,
            "settle_steps": settle_steps,
            "source_row": source_rows,
        }
        self._a2_pull_v5_bank_slot_indices = selected_indices
        self._a2_pull_v5_bank_slot_sources = [provenance[index] for index in selected_indices]
        self._a2_pull_v5_bank_eval_indices = selected_indices if eval_mode else []
        self._inject_a2_pull_v5_stage4_bank()
        self._a2_pull_v5_bank_loaded = True

    def _inject_a2_pull_v5_stage4_bank(self) -> None:
        bank = getattr(self, "_a2_pull_v5_bank", None)
        if bank is None:
            raise RuntimeError("Pull-v5 stage4 bank injection requires a loaded state bank.")
        capacity = int(self.staged_reset_max_samples_per_stage)
        bank_size = len(self._a2_pull_v5_bank_slot_indices)
        eval_selected_count = len(self._a2_pull_v5_bank_eval_indices)
        if eval_selected_count:
            if eval_selected_count != 16:
                raise RuntimeError(
                    "Pull-v5 canonical evaluation injection requires exactly 16 selected rows; "
                    f"got {eval_selected_count}."
                )
            if bank_size != eval_selected_count:
                raise RuntimeError(
                    "Pull-v5 canonical evaluation bank slot count must match selected rows; "
                    f"got {bank_size} for {eval_selected_count} selected rows."
                )
            if capacity < eval_selected_count:
                raise RuntimeError(
                    "Pull-v5 canonical evaluation staged-reset capacity is smaller than the "
                    f"selected row count: capacity={capacity}, selected={eval_selected_count}."
                )
            count = eval_selected_count
        else:
            count = min(capacity, bank_size)
            if count < int(self.config["a2_pull_v5_state_bank_min_samples"]):
                raise RuntimeError("Pull-v5 staged-reset capacity is smaller than the required bank minimum.")
        stage = self.STAGE_SWING
        source_origin = bank["source_env_origin"]
        for env_id in range(self.num_envs):
            target_origin = self.env_origins[env_id]
            for slot in range(count):
                bank_index = self._a2_pull_v5_bank_slot_indices[slot]
                robot_root = bank["robot_root_state"][bank_index].clone()
                door_root = bank["door_root_state"][bank_index].clone()
                robot_root[:3] = robot_root[:3] - source_origin[bank_index] + target_origin
                door_root[:3] = door_root[:3] - source_origin[bank_index] + target_origin
                robot_case = self.staged_reset_buf["robot"]
                robot_case["root_state"][stage, slot, env_id] = robot_root
                robot_case["dof_state"][stage, slot, env_id, :, 0] = bank["robot_dof_pos"][bank_index]
                robot_case["dof_state"][stage, slot, env_id, :, 1] = bank["robot_dof_vel"][bank_index]
                door_case = self.staged_reset_buf["door"]
                door_case["root_state"][stage, slot, env_id] = door_root
                door_case["dof_state"][stage, slot, env_id, :, 0] = bank["door_dof_pos"][bank_index]
                door_case["dof_state"][stage, slot, env_id, :, 1] = bank["door_dof_vel"][bank_index]
                for name, state_case in self.staged_reset_buf.items():
                    if state_case["type"] == "buffer":
                        value = bank[f"buffer:{name}"][bank_index].clone()
                        origin_delta = target_origin - source_origin[bank_index]
                        if name == "a2_pull_prev_base_pos_xy":
                            if tuple(value.shape) != (2,) or not value.is_floating_point():
                                raise RuntimeError(
                                    "Pull-v5 a2_pull_prev_base_pos_xy bank payload must be finite floating [2]."
                                )
                            value = value + origin_delta[:2]
                        elif name in {
                            "a2_pull_proof_start_root_x",
                            "a2_pull_proof_last_root_x",
                            "a2_pull_capture_root_x",
                        }:
                            if tuple(value.shape) != () or not value.is_floating_point():
                                raise RuntimeError(
                                    f"Pull-v5 {name} bank payload must be a finite floating scalar."
                                )
                            value = value + origin_delta[0]
                        state_case["data"][stage, slot, env_id] = value
        self.staged_reset_num_samples[stage, :] = count
        ratio = float(self.config["a2_pull_v5_stage4_bank_injection_ratio"])
        if not 0.0 <= ratio <= 1.0:
            raise RuntimeError(f"Pull-v5 Stage-4 bank ratio must be in [0,1]; got {ratio}.")
        if self.config.get("a2_pull_v5_reset_source", "natural") != "natural" and not self.config.get(
            "a2_pull_v5_stage4_bank_injection_enabled", False
        ):
            ratio = 1.0
        # Training uses [1-p, 0, 0, 0, p, 0]; canonical evaluation uses bank-only
        # Stage-4 rows while the training injection flag remains false.
        self.staged_reset_ratios.zero_()
        self.staged_reset_ratios[0] = 1.0 - ratio
        self.staged_reset_ratios[stage] = ratio

    def export_a2_pull_v5_state_bank(
        self,
        output_path: str,
        *,
        provenance: str,
        settle_valid: bool,
        settle_steps: int,
        capture_tier: str | None = None,
        source_row: int | None = None,
    ) -> dict[str, object]:
        """Export stage-4 snapshots through the existing high-level state writers.

        The source runner calls this after its settle window; no USD prim edits
        or synthetic state construction are permitted here.  ``provenance`` is
        deliberately explicit so source-A and source-B payloads cannot be
        silently mixed.
        """

        if provenance not in {"bank_natural_e5", "bank_natural_e5_plus", "bank_constructed"}:
            raise RuntimeError(f"Pull-v5 bank export provenance is unsupported: {provenance!r}.")
        if not isinstance(settle_valid, bool) or not settle_valid:
            raise RuntimeError("Pull-v5 bank export requires an explicitly valid settle window.")
        if isinstance(settle_steps, bool) or not isinstance(settle_steps, int) or settle_steps < 50:
            raise RuntimeError("Pull-v5 bank export requires settle_steps >= 50.")
        if capture_tier is None:
            capture_tier = {
                "bank_natural_e5": "e5",
                "bank_natural_e5_plus": "e5_plus_2s",
                "bank_constructed": "constructed",
            }[provenance]
        if capture_tier not in {"e5", "e5_plus_2s", "e5_plus_4s", "constructed"}:
            raise RuntimeError(f"Pull-v5 bank capture tier is unsupported: {capture_tier!r}.")
        if source_row is None:
            source_row = int(self.config.get("a2_pull_v5_bank_capture_source_row", 0))
        if isinstance(source_row, bool) or not isinstance(source_row, int) or source_row < 0:
            raise RuntimeError("Pull-v5 bank export source_row must be a non-negative integer.")
        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError("Pull-v5 bank export requires staged reset snapshots.")
        stage = self.STAGE_SWING
        counts = self.staged_reset_num_samples[stage]
        if torch.any(counts < 0) or torch.any(counts > self.staged_reset_max_samples_per_stage):
            raise RuntimeError("Pull-v5 bank export encountered invalid per-environment snapshot counts.")
        valid_env_ids = torch.where(counts > 0)[0]
        if len(valid_env_ids) == 0:
            raise RuntimeError("Pull-v5 bank export has no Stage-4 snapshots after settle.")
        robot_case = self.staged_reset_buf.get("robot")
        door_case = self.staged_reset_buf.get("door")
        if not isinstance(robot_case, Mapping) or not isinstance(door_case, Mapping):
            raise RuntimeError("Pull-v5 bank export requires tracked robot and door states.")
        robot_root_chunks: list[torch.Tensor] = []
        robot_dof_pos_chunks: list[torch.Tensor] = []
        robot_dof_vel_chunks: list[torch.Tensor] = []
        door_root_chunks: list[torch.Tensor] = []
        door_dof_pos_chunks: list[torch.Tensor] = []
        door_dof_vel_chunks: list[torch.Tensor] = []
        origin_chunks: list[torch.Tensor] = []
        force_chunks: list[torch.Tensor] = []
        rows = 0
        for env_id in valid_env_ids.tolist():
            count = int(counts[env_id].item())
            robot_root_chunks.append(robot_case["root_state"][stage, :count, env_id])
            robot_dof_pos_chunks.append(robot_case["dof_state"][stage, :count, env_id, :, 0])
            robot_dof_vel_chunks.append(robot_case["dof_state"][stage, :count, env_id, :, 1])
            door_root_chunks.append(door_case["root_state"][stage, :count, env_id])
            door_dof_pos_chunks.append(door_case["dof_state"][stage, :count, env_id, :, 0])
            door_dof_vel_chunks.append(door_case["dof_state"][stage, :count, env_id, :, 1])
            origin_chunks.append(self.env_origins[env_id].expand(count, 3))
            force_chunks.append(self.door_hinge_drive_max_force[env_id].expand(count))
            rows += count
        robot_root = torch.cat(robot_root_chunks, dim=0)
        robot_dof_pos = torch.cat(robot_dof_pos_chunks, dim=0)
        robot_dof_vel = torch.cat(robot_dof_vel_chunks, dim=0)
        door_root = torch.cat(door_root_chunks, dim=0)
        door_dof_pos = torch.cat(door_dof_pos_chunks, dim=0)
        door_dof_vel = torch.cat(door_dof_vel_chunks, dim=0)
        source_origins = torch.cat(origin_chunks, dim=0)
        force_values = torch.cat(force_chunks, dim=0)
        delay_seconds = {
            "e5": 0.0,
            "e5_plus_2s": 2.0,
            "e5_plus_4s": 4.0,
            "constructed": 0.0,
        }[capture_tier]
        capture_delay_steps = int(round(delay_seconds / float(self.dt))) if delay_seconds else 0
        payload: dict[str, object] = {
            "schema": A2_PULL_V5_STATE_BANK_SOURCE_SCHEMA,
            "robot_root_state": robot_root.detach().cpu(),
            "robot_dof_pos": robot_dof_pos.detach().cpu(),
            "robot_dof_vel": robot_dof_vel.detach().cpu(),
            "door_root_state": door_root.detach().cpu(),
            "door_dof_pos": door_dof_pos.detach().cpu(),
            "door_dof_vel": door_dof_vel.detach().cpu(),
            "source_env_origin": source_origins.detach().cpu(),
            "provenance": [provenance] * rows,
            "settle_valid": torch.ones(rows, dtype=torch.bool),
            "settle_steps": torch.full((rows,), settle_steps, dtype=torch.long),
            "capture_delay_steps": torch.full((rows,), capture_delay_steps, dtype=torch.long),
            "hinge_drive_max_force_nm": force_values.detach().cpu(),
            "closer_bucket": [],
            "capture_tier": [capture_tier] * rows,
            "source_row": [source_row] * rows,
            "buffers": {},
        }
        force_values = payload["hinge_drive_max_force_nm"]
        if not torch.is_tensor(force_values) or tuple(force_values.shape) != (rows,):
            raise RuntimeError("Pull-v5 bank export closer-force metadata shape mismatch.")
        closer_buckets: list[str] = []
        for force in force_values.tolist():
            value = float(force)
            if 2.5 <= value < 5.0:
                closer_buckets.append("2.5-5")
            elif 5.0 <= value < 9.0:
                closer_buckets.append("5-9")
            elif 9.0 <= value <= 12.0:
                closer_buckets.append("9-12")
            else:
                raise RuntimeError(f"Pull-v5 closer force outside planned buckets: {value!r}")
        payload["closer_bucket"] = closer_buckets
        buffers = payload["buffers"]
        assert isinstance(buffers, dict)
        for name, state_case in self.staged_reset_buf.items():
            if state_case["type"] != "buffer":
                continue
            chunks = [
                state_case["data"][stage, : int(counts[env_id].item()), env_id]
                for env_id in valid_env_ids.tolist()
            ]
            buffers[name] = torch.cat(chunks, dim=0).detach().cpu()
        path = self._pull_v5_repo_path(output_path, "bank capture path")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Pull-v5 bank capture refuses to overwrite {path}.")
        torch.save(payload, path)
        return {"schema": payload["schema"], "status": "PASS", "samples": rows, "output": str(path)}

    def capture_a2_pull_v5_source_snapshot(self, output_path: str) -> dict[str, object]:
        """Capture one configured E5/holding/constructed source tier.

        Source-A replay uses the same 86-buffer payload for E5, E5+2 s, and
        E5+4 s windows; only provenance/capture metadata changes.
        """

        tier = self.config.get("a2_pull_v5_bank_capture_tier", "e5")
        provenance = {
            "e5": "bank_natural_e5",
            "e5_plus_2s": "bank_natural_e5_plus",
            "e5_plus_4s": "bank_natural_e5_plus",
            "constructed": "bank_constructed",
        }.get(tier)
        if provenance is None:
            raise RuntimeError(f"Pull-v5 bank capture tier is unsupported: {tier!r}.")
        return self.export_a2_pull_v5_state_bank(
            output_path,
            provenance=provenance,
            settle_valid=True,
            settle_steps=int(self.config.get("a2_pull_v5_bank_capture_settle_steps", 50)),
            capture_tier=tier,
            source_row=int(self.config.get("a2_pull_v5_bank_capture_source_row", 0)),
        )

    def update_a2_pull_v5_capture_window(self) -> None:
        """Capture natural Source-A rows at E5 or the configured delayed hold tier."""

        if not self._is_a2_pull_v5():
            raise RuntimeError("Pull-v5 source capture requires the v5 plan guard.")
        if self.config.get("a2_pull_v5_bank_capture_provenance") == "bank_constructed":
            raise RuntimeError("Natural capture-window updates cannot run for Source-B.")
        if self.config.get("a2_pull_v5_bank_capture_only") is not True:
            raise RuntimeError("Pull-v5 capture-window updates require capture_only=true.")
        tier = self.config.get("a2_pull_v5_bank_capture_tier", "e5")
        delay_seconds = {
            "e5": 0.0,
            "e5_plus_2s": 2.0,
            "e5_plus_4s": 4.0,
        }.get(tier)
        if delay_seconds is None:
            raise RuntimeError(f"Pull-v5 natural capture tier is unsupported: {tier!r}.")
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError("Pull-v5 capture-window updates require a positive finite dt.")
        delay_steps = int(round(delay_seconds / dt)) if delay_seconds else 0
        e5 = self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
        new_e5 = e5 & ~self._a2_pull_v5_capture_e5_seen
        self._a2_pull_v5_capture_e5_seen |= e5
        self._a2_pull_v5_capture_pending[new_e5] = True
        self._a2_pull_v5_capture_target_step[new_e5] = (
            self.episode_length_buf[new_e5] + delay_steps
        )
        due = self._a2_pull_v5_capture_pending & (
            self.episode_length_buf >= self._a2_pull_v5_capture_target_step
        )
        due &= ~self._a2_pull_v5_capture_recorded
        if torch.any(due):
            if torch.any(self.stage_buf[due] != self.STAGE_SWING):
                raise RuntimeError("Pull-v5 Source-A capture reached its tier outside Stage-4 swing.")
            self._take_snapshot_of_buffered_states(due)
            self._a2_pull_v5_capture_pending[due] = False
            self._a2_pull_v5_capture_recorded[due] = True

    def construct_a2_pull_v5_source_b_states(self) -> None:
        """Capture Source-B states with direct IsaacLab articulation writers.

        This route intentionally bypasses staged-reset sampling.  It writes a
        world-frame robot/door template, settles the articulations, and only
        then snapshots valid rows.  ``staged_reset_ratios`` is never touched.
        """

        if not self._is_a2_pull_v5():
            raise RuntimeError("Source-B construction requires the v5 plan guard.")

        settle_steps = self.config.get("a2_pull_v5_bank_capture_settle_steps")
        if (
            isinstance(settle_steps, bool)
            or not isinstance(settle_steps, int)
            or settle_steps < 50
        ):
            raise RuntimeError(
                "Source-B construction requires a2_pull_v5_bank_capture_settle_steps >= 50."
            )

        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError("Source-B capture requires staged reset buffers for snapshot export.")
        if self.config.get("a2_pull_v5_bank_capture_only") is not True:
            raise RuntimeError("Source-B capture requires bank_capture_only=true.")
        env_ids = torch.arange(self.num_envs, device=self.device, dtype=torch.long)
        robot = self.simulator.scene.articulations["robot"]
        door = self.simulator.scene.articulations["door"]
        robot.reset(env_ids)
        door.reset(env_ids)

        # Build a local template, translate roots by each environment origin,
        # and zero every velocity before the high-level writes.
        robot_root = self.base_init_state.to(device=self.device).expand(self.num_envs, -1).clone()
        robot_root[:, 3:7] = xyzw_to_wxyz(robot_root[:, 3:7])
        robot_root[:, :3] += self.env_origins
        robot_root[:, 0] = self.env_origins[:, 0] + self._pull_direction.approach_side_x * 0.9
        robot_root[:, 1] = self.env_origins[:, 1]
        robot_root[:, 7:13] = 0.0
        robot.write_root_state_to_sim(robot_root, env_ids)

        robot_dof_pos = self.default_dof_pos.to(device=self.device).expand(self.num_envs, -1).clone()
        robot_dof_pos[:, self._upper_non_gripper_dof_idx] = self._get_a2_arm_default_dof_pos(env_ids)
        robot_dof_pos[:, self._a2_gripper_dof_indices] = self._a2_gripper_open_target
        robot_dof_vel = torch.zeros_like(robot_dof_pos)
        robot.write_joint_state_to_sim(robot_dof_pos, robot_dof_vel, env_ids=env_ids)

        door_root = door.data.default_root_state[env_ids].clone()
        door_root[:, :3] += self.env_origins
        door_root[:, 7:13] = 0.0
        door.write_root_state_to_sim(door_root, env_ids)
        door_joint_pos = torch.zeros(
            (self.num_envs, door.num_joints), device=self.device, dtype=door.data.joint_pos.dtype
        )
        door_joint_pos[:, 0] = torch.linspace(1.6, 2.1, self.num_envs, device=self.device)
        door_joint_vel = torch.zeros_like(door_joint_pos)
        door.write_joint_state_to_sim(door_joint_pos, door_joint_vel, env_ids=env_ids)
        robot.reset(env_ids)
        door.reset(env_ids)
        self._refresh_sim_tensors()
        self._reset_buffers_callback(env_ids, None)
        self.set_to_stage(env_ids, torch.full_like(env_ids, self.STAGE_SWING))
        self.staged_reset_num_samples[self.STAGE_SWING, :] = 0
        self.reset_buf[:] = 0
        self.need_to_refresh_envs[env_ids] = False

        gravity_x_limit = float(self.config.termination_scales.termination_gravity_x)
        gravity_y_limit = float(self.config.termination_scales.termination_gravity_y)
        minimum_base_height = float(self.config.termination_scales.termination_min_base_height)
        settle_valid_mask = torch.ones(self.num_envs, dtype=torch.bool, device=self.device)
        for _ in range(settle_steps):
            hold_action = self._action_backmap()
            expected_action_dim = self._a2_high_level_action_dim + self._a2_leg_action_dim
            if (
                not torch.is_tensor(hold_action)
                or tuple(hold_action.shape) != (self.num_envs, expected_action_dim)
                or hold_action.device != torch.device(self.device)
                or not hold_action.is_floating_point()
                or not torch.all(torch.isfinite(hold_action))
            ):
                shape = None if not torch.is_tensor(hold_action) else tuple(hold_action.shape)
                raise RuntimeError(
                    "Source-B settle requires a finite high-level A2 hold action with "
                    f"shape ({self.num_envs}, {expected_action_dim}); got {shape}."
                )
            desired_arm_action = hold_action[:, self._delta_action_indices].clone()
            hold_action[:, self._delta_action_indices] = (
                desired_arm_action - self._delta_actions
            ) / self._delta_action_scale
            self.step({"actions": hold_action})

            root_state = self.simulator.robot_root_states
            robot_dof_pos = self.simulator.dof_pos
            robot_dof_vel = self.simulator.dof_vel
            door_state = self.simulator.get_task_root_state("door")
            door_data = self.simulator.scene.articulations["door"].data
            door_dof_pos = door_data.joint_pos
            door_dof_vel = door_data.joint_vel
            finite_state = all(
                torch.all(torch.isfinite(value))
                for value in (
                    root_state,
                    robot_dof_pos,
                    robot_dof_vel,
                    door_state,
                    door_dof_pos,
                    door_dof_vel,
                )
            )
            root_height = root_state[:, 2] - self.ground_height
            root_speed = torch.linalg.norm(root_state[:, 7:10], dim=-1)
            root_ang_speed = torch.linalg.norm(root_state[:, 10:13], dim=-1)
            gravity = self.projected_gravity
            unstable = (
                torch.full((self.num_envs,), not finite_state, dtype=torch.bool, device=self.device)
                | (root_height < minimum_base_height)
                | (torch.abs(gravity[:, 0]) > gravity_x_limit)
                | (torch.abs(gravity[:, 1]) > gravity_y_limit)
                | (root_speed > 1.0)
                | (root_ang_speed > 1.0)
                | (self.reset_buf != 0)
            )
            clearance = self._get_a2_pull_minimum_panel_robot_clearance()
            frame_contact = self._get_door_frame_contact_force_per_env("Pull-v5 Source-B settle")
            unstable |= (clearance < 0.0) | (frame_contact > 0.0)
            settle_valid_mask &= ~unstable

        final_door_data = self.simulator.scene.articulations["door"].data
        final_hinge = final_door_data.joint_pos[:, 0]
        arm_default = self._get_a2_arm_default_dof_pos()
        arm_tolerance = self._get_required_positive_float_config(
            "a2_stage0_arm_default_max_deviation", "Pull-v5 Source-B final admission"
        )
        arm_near_default = torch.abs(
            self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx] - arm_default
        ).amax(dim=-1) <= arm_tolerance
        gripper_near_open = torch.abs(
            self.simulator.dof_pos[:, self._a2_gripper_dof_indices] - self._a2_gripper_open_target
        ).amax(dim=-1) <= arm_tolerance
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "Pull-v5 Source-B final admission"
        )
        no_handle_contact = ~torch.any(contact_masks["contacting"], dim=-1)
        settle_valid_mask &= (
            (final_hinge >= 1.6)
            & (final_hinge <= 2.1)
            & (torch.abs(final_door_data.joint_vel) <= 0.05).all(dim=-1)
            & (torch.abs(self.simulator.dof_vel) <= 0.05).all(dim=-1)
            & (torch.linalg.norm(self.simulator.robot_root_states[:, 7:10], dim=-1) <= 0.05)
            & (torch.linalg.norm(self.simulator.robot_root_states[:, 10:13], dim=-1) <= 0.05)
            & arm_near_default
            & gripper_near_open
            & no_handle_contact
        )
        if not bool(torch.any(settle_valid_mask).item()):
            raise RuntimeError("Source-B settle rejected every constructed row.")
        self.staged_reset_num_samples[self.STAGE_SWING, :] = 0
        self._take_snapshot_of_buffered_states(settle_valid_mask)
        stage_counts = self.staged_reset_num_samples[self.STAGE_SWING, env_ids]
        if torch.any(stage_counts[settle_valid_mask] < 1):
            raise RuntimeError("Source-B settle did not produce a Stage-4 snapshot for every valid row.")
        self._a2_pull_v5_source_b_capture_frozen = True

    def export_a2_pull_v5_census(self, output_path: str, *, variant: str, seed: int) -> dict[str, object]:
        """Export staged-reset occupancy and state summaries for the census runner."""

        if variant not in {"v4_B", "v5"}:
            raise RuntimeError(f"Pull-v5 census variant is unsupported: {variant!r}.")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise RuntimeError("Pull-v5 census seed must be an integer.")
        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError("Pull-v5 census requires staged reset state snapshots.")
        stages: dict[str, object] = {}
        for stage in range(self.num_stages):
            count_by_env = self.staged_reset_num_samples[stage]
            sample_count = int(count_by_env.sum().item())
            source_counts: dict[str, int] = {"natural": sample_count}
            if variant == "v5" and stage == self.STAGE_SWING and self._a2_pull_v5_bank_slot_sources:
                source_counts = dict(Counter(self._a2_pull_v5_bank_slot_sources[: int(count_by_env.max().item())]))
            row: dict[str, object] = {
                "snapshot_count": sample_count,
                "reset_source_counts": source_counts,
                "hinge_rad": {},
                "root_state": {},
                "contact": {},
                "arm_state": {},
            }
            if sample_count:
                door_case = self.staged_reset_buf.get("door")
                robot_case = self.staged_reset_buf.get("robot")
                if not isinstance(door_case, Mapping) or not isinstance(robot_case, Mapping):
                    raise RuntimeError("Pull-v5 census requires tracked robot and door states.")
                hinge = door_case["dof_state"][stage, : int(count_by_env.max().item()), :, 0, 0]
                root = robot_case["root_state"][stage, : int(count_by_env.max().item()), :, :3]
                arm = robot_case["dof_state"][stage, : int(count_by_env.max().item()), :, :, 0]
                finite_hinge = hinge[torch.isfinite(hinge)]
                finite_root = root[torch.isfinite(root).all(dim=-1)]
                finite_arm = arm[torch.isfinite(arm).all(dim=-1)]
                if finite_hinge.numel() == 0 or finite_root.numel() == 0 or finite_arm.numel() == 0:
                    raise RuntimeError(f"Pull-v5 census stage {stage} has no finite state samples.")
                row["hinge_rad"] = {
                    "min": float(finite_hinge.min().item()),
                    "max": float(finite_hinge.max().item()),
                    "mean": float(finite_hinge.mean().item()),
                }
                row["root_state"] = {"mean_xyz": finite_root.mean(dim=0).detach().cpu().tolist()}
                row["arm_state"] = {"mean": finite_arm.mean(dim=0).detach().cpu().tolist()}
                contact_case = self.staged_reset_buf.get("a2_pull_prev_stable_contact")
                if isinstance(contact_case, Mapping):
                    contact = contact_case["data"][stage, : int(count_by_env.max().item())]
                    row["contact"] = {"stable_contact_count": int(contact.bool().sum().item())}
                else:
                    raise RuntimeError("Pull-v5 census requires tracked stable-contact snapshots.")
            stages[str(stage)] = row
        payload = {
            "schema": "a2_piper_pull_v5_census_v2",
            "variant": variant,
            "seed": seed,
            "stages": stages,
        }
        path = self._pull_v5_repo_path(output_path, "census output path")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Pull-v5 census refuses to overwrite {path}.")
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"schema": payload["schema"], "status": "PASS", "output": str(path), "stages": stages}

    @override
    def _filter_staged_reset_snapshot_mask(self, advance_mask: torch.Tensor) -> torch.Tensor:
        filtered = super()._filter_staged_reset_snapshot_mask(advance_mask)
        capture_only = self.config.get("a2_pull_v5_bank_capture_only", False)
        if not isinstance(capture_only, bool):
            raise RuntimeError("a2_pull_v5_bank_capture_only must be a boolean.")
        if self._is_a2_pull_v5() and capture_only:
            return torch.zeros_like(filtered)
        if (
            self._is_a2_pull_v5()
            and self.config["a2_pull_v5_snapshot_freeze_enabled"]
            and not capture_only
        ):
            filtered &= self.stage_buf != self.STAGE_SWING
        if self._is_a2_pull_v6():
            filtered &= self.stage_buf != self.STAGE_SWING
        if self._get_a2_pull_stage3_e3_snapshot_curriculum_enabled():
            filtered &= ~(
                (self.stage_buf == self.STAGE_OPEN) & (self.door_open_lr == 1.0)
            )
        return filtered

    @override
    def _validate_loaded_staged_reset_sample(
        self,
        selected_env_ids: torch.Tensor,
        selected_stages: torch.Tensor,
        selected_sample_indices: torch.Tensor,
    ) -> None:
        super()._validate_loaded_staged_reset_sample(
            selected_env_ids, selected_stages, selected_sample_indices
        )
        if not self._get_a2_pull_stage3_e3_snapshot_curriculum_enabled():
            return
        left_stage3 = (
            (selected_stages == self.STAGE_OPEN)
            & (self.door_open_lr[selected_env_ids] == 1.0)
        )
        if not torch.any(left_stage3):
            return
        env_ids = selected_env_ids[left_stage3]
        if torch.any(~self._a2_pull_event_reached[env_ids, A2PullEvent.E3_LATCH_RELEASE]):
            raise RuntimeError(
                "LEFT Stage-3 E3 curriculum loaded a snapshot without E3 evidence."
            )
        if torch.any(
            self._a2_pull_first_event_step[env_ids, A2PullEvent.E3_LATCH_RELEASE] != 0
        ) or torch.any(
            self._a2_pull_first_event_time_s[env_ids, A2PullEvent.E3_LATCH_RELEASE] != 0.0
        ):
            raise RuntimeError(
                "LEFT Stage-3 E3 curriculum requires rebased E3 step/time equal to zero."
            )
        self._a2_pull_stage3_e3_loaded_snapshot_count += env_ids.numel()
        self.log_dict["a2_pull_stage3_e3_loaded_snapshot_count"] = (
            self._a2_pull_stage3_e3_loaded_snapshot_count.float()
        )

    @override
    def _sample_reset_sample_indices(self, env_ids: torch.Tensor, selected_stages: torch.Tensor) -> torch.Tensor:
        selected = super()._sample_reset_sample_indices(env_ids, selected_stages)
        if getattr(self, "_a2_pull_v61_late_state_bank_enabled", False):
            stage4_slots = self._a2_pull_v61_stage4_bank_slots
            stage4_weights = self._a2_pull_v61_stage4_row_weights
            labels = tuple(stage4_weights)
            weights = torch.tensor(
                [stage4_weights[label] for label in labels],
                dtype=torch.float32,
                device=self.device,
            )
            stage4_mask = selected_stages == self.STAGE_SWING
            if torch.any(stage4_mask):
                sampled_labels = torch.multinomial(
                    weights.expand(int(stage4_mask.sum().item()), -1), 1
                ).squeeze(-1)
                selected[stage4_mask] = torch.tensor(
                    [stage4_slots[labels[index]] for index in sampled_labels.tolist()],
                    dtype=torch.long,
                    device=self.device,
                )
            stage5_mask = selected_stages == self.STAGE_THROUGH
            if torch.any(stage5_mask):
                selected[stage5_mask] = 0
            stage4_labels_by_slot = {slot: label for label, slot in stage4_slots.items()}
            for env_id, stage, sample in zip(
                env_ids.tolist(), selected_stages.tolist(), selected.tolist()
            ):
                if stage == self.STAGE_SWING:
                    label = stage4_labels_by_slot[sample]
                elif stage == self.STAGE_THROUGH:
                    label = "e6_stage5_entry"
                else:
                    label = "natural"
                self._a2_pull_v61_last_reset_source[env_id] = {
                    "label": label,
                    "stage": stage,
                    "sample_index": sample,
                }
        if self._is_a2_pull_v6():
            selected_bank_row = self._a2_pull_v6_stage4_bank_row_index
            if selected_bank_row is not None:
                stage4_mask = selected_stages == self.STAGE_SWING
                selected[stage4_mask] = selected_bank_row
        if self._is_a2_pull_v5():
            for env_id, stage, sample in zip(env_ids.tolist(), selected_stages.tolist(), selected.tolist()):
                if stage == self.STAGE_SWING:
                    if sample < 0 or sample >= len(self._a2_pull_v5_bank_slot_sources):
                        raise RuntimeError(
                            f"Pull-v5 canonical bank sample index is out of range: {sample}."
                        )
                    self._a2_pull_v5_pending_reset_source[env_id] = self._a2_pull_v5_bank_slot_sources[sample]
                else:
                    self._a2_pull_v5_pending_reset_source[env_id] = "natural"
        return selected

    @override
    def _reset_buffers_callback(self, env_ids, target_buf=None):
        result = super()._reset_buffers_callback(env_ids, target_buf)
        self._a2_pull_event_reached[env_ids] = False
        self._a2_pull_stable_unlatch_handle_ever[env_ids] = False
        self._a2_pull_stable_unlatch_latch_ever[env_ids] = False
        self._a2_pull_relock_handle_ever[env_ids] = False
        self._a2_pull_relock_latch_ever[env_ids] = False
        self._a2_pull_prev_handle_unlatched[env_ids] = False
        self._a2_pull_prev_latch_unlatched[env_ids] = False
        self._a2_pull_first_event_step[env_ids] = -1
        self._a2_pull_first_event_time_s[env_ids] = float("nan")
        self._a2_pull_capture_root_x[env_ids] = float("nan")
        self._a2_pull_capture_valid[env_ids] = False
        self._a2_pull_max_tensile_retreat_m[env_ids] = 0.0
        self._a2_pull_release_or_hold_decision[env_ids] = False
        self._a2_pull_proof_active[env_ids] = False
        self._a2_pull_proof_start_root_x[env_ids] = float("nan")
        self._a2_pull_proof_last_root_x[env_ids] = float("nan")
        self._a2_pull_proof_duration_s[env_ids] = 0.0
        self._a2_pull_proof_displacement_m[env_ids] = 0.0
        self._a2_pull_proof_streak[env_ids] = 0
        self._a2_pull_proof_valid[env_ids] = False
        self._a2_pull_minimum_panel_robot_clearance_m[env_ids] = float("nan")
        self._a2_pull_clearance_ready[env_ids] = False
        self._a2_pull_aperture_ready[env_ids] = False
        self._a2_pull_frame_passage[env_ids] = False
        self._a2_pull_frame_passage_step[env_ids] = -1
        self._a2_pull_planar_crossing[env_ids] = False
        self._a2_pull_planar_crossing_step[env_ids] = -1
        self._a2_pull_detour[env_ids] = False
        self._a2_pull_frame_approach[env_ids] = False
        self._a2_pull_frame_approach_active[env_ids] = False
        self._a2_pull_frame_approach_pre_aperture_steps[env_ids] = 0
        self._a2_pull_frame_approach_post_frame_passage_steps[env_ids] = 0
        self._a2_pull_frame_midpoint_distance_min_m[env_ids] = float("nan")
        self._a2_pull_deliberate_release[env_ids] = False
        self._a2_pull_deliberate_release_step[env_ids] = -1
        if self._is_a2_pull_v5():
            self._a2_pull_v5_persistent_release_streak[env_ids] = 0
            self._a2_pull_v5_persistent_release[env_ids] = False
            self._a2_pull_v5_intervention_elapsed_steps[env_ids] = 0
            self._a2_pull_v5_intervention_active[env_ids] = False
            self._a2_pull_v5_intervention_fired[env_ids] = False
            self._a2_pull_v5_probe_solvable[env_ids] = False
            self._a2_pull_v5_probe_anchor_initialized[env_ids] = False
            self._a2_pull_v5_probe_waypoint_target_xy[env_ids] = float("nan")
            self._a2_pull_v5_probe_yaw_target[env_ids] = float("nan")
            self._a2_pull_v5_probe_original_yaw_target[env_ids] = float("nan")
            self._a2_pull_v5_probe_waypoint_error_m[env_ids] = float("nan")
            self._a2_pull_v5_probe_yaw_error_rad[env_ids] = float("nan")
            self._a2_pull_v5_probe_waypoint_arrived[env_ids] = False
            self._a2_pull_v5_probe_yaw_arrived[env_ids] = False
            self._a2_pull_v5_probe_anchor_pass[env_ids] = False
            self._a2_pull_v5_capture_e5_seen[env_ids] = False
            self._a2_pull_v5_capture_pending[env_ids] = False
            self._a2_pull_v5_capture_recorded[env_ids] = False
            self._a2_pull_v5_capture_target_step[env_ids] = -1
            for env_id in env_ids.tolist():
                source = self._a2_pull_v5_pending_reset_source[env_id]
                if self.config.get("a2_pull_v5_start_override_enabled", False) and source.startswith(
                    "bank_"
                ):
                    source = "bank_natural_e5_override"
                self._a2_pull_v5_reset_source[env_id] = source
                if self._a2_pull_v5_reset_source[env_id] not in A2_PULL_V5_RESET_SOURCES:
                    raise RuntimeError(
                        "Pull-v5 reset_source must be exactly natural, bank_natural_e5, "
                        "bank_natural_e5_plus, or bank_constructed."
                    )
        self._a2_pull_first_negative_x_motion_step[env_ids] = -1
        self._a2_pull_prev_stable_contact[env_ids] = False
        self._a2_pull_prev_panel_contact[env_ids] = False
        self._a2_pull_post_release_recontact_count[env_ids] = 0
        self._a2_pull_base_path_length_m[env_ids] = 0.0
        self._a2_pull_prev_base_pos_xy[env_ids] = float("nan")
        self._a2_pull_base_reversal_count[env_ids] = 0
        self._a2_pull_prev_travel_velocity[env_ids] = float("nan")
        self._a2_pull_swept_arc_clearance_margin_current_m[env_ids] = float("nan")
        self._a2_pull_swept_arc_clearance_margin_min_m[env_ids] = float("nan")
        self._a2_pull_corridor_door_wide_pre_aperture_steps[env_ids] = 0
        self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_ids] = 0
        self._a2_pull_stage0_staging_band[env_ids] = False
        self._a2_pull_stage0_arm_default[env_ids] = False
        self._a2_pull_stage0_base_still[env_ids] = False
        self._a2_pull_first_scripted_activation_step[env_ids] = -1
        self._a2_pull_hinge_at_first_positive_progress_rad[env_ids] = float("nan")
        self._a2_pull_held_hinge_max_rad[env_ids] = float("nan")
        self._a2_pull_hinge_at_decision_rad[env_ids] = float("nan")
        self._a2_pull_root_outward_excursion_m[env_ids] = 0.0
        self._a2_pull_first_path_reversal_step[env_ids] = -1
        self._a2_pull_body_panel_contact_steps[env_ids] = 0
        self._a2_pull_body_panel_contact_impulse_ns[env_ids] = 0.0
        self._a2_pull_prev_handle_to_tcp_pos[env_ids] = float("nan")
        self._a2_pull_handle_local_slip_xyz_mps[env_ids] = float("nan")
        self._a2_pull_handle_local_slip_valid[env_ids] = False
        self._a2_pull_passage_attempt_hinge_rad[env_ids] = float("nan")
        if self._is_a2_pull_v6():
            self._a2_pull_v61_e6_event_pulse[env_ids] = False
            self._a2_pull_v61_e7_event_pulse[env_ids] = False
            self._a2_pull_v6_subphase[env_ids] = self._A2_PULL_V6_PHASE_A
            self._a2_pull_v6_pivot_xy[env_ids] = float("nan")
            self._a2_pull_v6_pivot_valid[env_ids] = False
            self._a2_pull_v6_handle_y_capture[env_ids] = float("nan")
            self._a2_pull_v6_handle_y_current[env_ids] = float("nan")
            self._a2_pull_v6_handle_y_prev[env_ids] = float("nan")
            self._a2_pull_v6_handle_y_best[env_ids] = float("nan")
            self._a2_pull_v6_handle_side_progress[env_ids] = 0.0
            self._a2_pull_v6_handle_crossed[env_ids] = False
            self._a2_pull_v6_handle_cross_bonus[env_ids] = False
            self._a2_pull_v6_release_side_qualified[env_ids] = False
            self._a2_pull_v6_handoff_active[env_ids] = False
            self._a2_pull_v6_handoff_reached[env_ids] = False
            self._a2_pull_v6_handoff_active_steps[env_ids] = 0
            self._a2_pull_v6_handoff_reward_window[env_ids] = False
            self._a2_pull_v6_handle_to_tcp_capture_pos[env_ids] = 0.0
            self._a2_pull_v6_handle_to_tcp_capture_quat[env_ids] = 0.0
            self._a2_pull_v6_handle_to_tcp_capture_quat[env_ids, 0] = 1.0
            self._a2_pull_v6_handle_to_tcp_valid[env_ids] = False
            self._a2_pull_v6_prev_tcp_pos_w[env_ids] = float("nan")
            self._a2_pull_v6_prev_tcp_valid[env_ids] = False
            self._a2_pull_v6_positive_arm_tangent[env_ids] = 0.0
            self._a2_pull_v6_positive_base_tangent[env_ids] = 0.0
            self._a2_pull_v6_positive_total_tangent[env_ids] = 0.0
            self._a2_pull_v6_instantaneous_arm_tangent_share[env_ids] = 0.0
            self._a2_pull_v6_arm_tangent_integral_m[env_ids] = 0.0
            self._a2_pull_v6_total_tangent_integral_m[env_ids] = 0.0
            self._a2_pull_v6_arm_tangent_share[env_ids] = 0.0
            self._a2_pull_v6_last_held_arm_tangent_share[env_ids] = 0.0
            self._a2_pull_v6_arc_error_m[env_ids] = float("nan")
            self._a2_pull_v6_arc_quality[env_ids] = 0.0
            self._a2_pull_v6_pivot_displacement_m[env_ids] = float("nan")
            self._a2_pull_v6_workspace_margin[env_ids] = float("nan")
            self._a2_pull_v6_workspace_margin_progress[env_ids] = 0.0
            self._a2_pull_v6_workspace_margin_progress_active[env_ids] = False
            self._a2_pull_v6_frame_lateral_delta_y_m[env_ids] = float("nan")
            self._a2_pull_v6_frame_lateral_deficit_m[env_ids] = float("nan")
            self._a2_pull_v6_frame_passage_ready[env_ids] = False
            self._a2_pull_v6_pre_release_except_passage[env_ids] = False
            self._a2_pull_v6_passage_alignment_progress[env_ids] = 0.0
            self._a2_pull_v6_passage_alignment_progress_active[env_ids] = False
            self._a2_pull_v6_passage_command_alignment[env_ids] = 0.0
            self._a2_pull_v6_passage_command_alignment_active[env_ids] = False
            self._a2_pull_v6_post_release_lateral_command_alignment[env_ids] = 0.0
            self._a2_pull_v6_post_release_lateral_command_alignment_active[env_ids] = False
            self._a2_pull_v6_post_release_arm_tuck_progress[env_ids] = 0.0
            self._a2_pull_v6_post_release_arm_tuck_progress_active[env_ids] = False
            self._a2_pull_v6_pre_action_arm_delta_targets[env_ids] = 0.0
            self._a2_pull_v6_release_action_started_ready[env_ids] = False
            self._a2_pull_v6_release_ready[env_ids] = False
            self._a2_pull_v6_prev_release_ready[env_ids] = False
            self._a2_pull_v6_release_event[env_ids] = False
            self._a2_pull_v6_clean_release[env_ids] = False
            self._a2_pull_v6_premature_release[env_ids] = False
            self._a2_pull_v6_clean_release_event[env_ids] = False
            self._a2_pull_v6_premature_release_event[env_ids] = False
            self._a2_pull_v6_release_quality[env_ids] = 0.0
            self._a2_pull_v6_release_persistence[env_ids] = 0
            self._a2_pull_v61_post_release_control_active[env_ids] = False
            self._a2_pull_v6_persistence_income_active[env_ids] = False
            self._a2_pull_v6_persistence_income_consumed[env_ids] = False
            self._a2_pull_v6_persistence_recontact_event[env_ids] = False
            self._a2_pull_v6_hinge_at_release[env_ids] = float("nan")
            self._a2_pull_v6_hinge_velocity_at_release[env_ids] = float("nan")
            self._a2_pull_v6_root_yaw_at_capture[env_ids] = float("nan")
            self._a2_pull_v6_root_yaw_delta[env_ids] = float("nan")
            self._a2_pull_v6_prev_bilateral_contact[env_ids] = False
            self._a2_pull_v6_e5_snapshot_pending[env_ids] = False
            self._a2_pull_v6_pre_release_snapshot_pending[env_ids] = False
            self._a2_pull_v6_d1_snapshot_captured[env_ids] = False
            self._a2_pull_v6_d5_snapshot_captured[env_ids] = False
            self._a2_pull_v6_d25_snapshot_captured[env_ids] = False
            self._a2_pull_v61_clean_release_step[env_ids] = -1
            self._a2_pull_v61_hinge_running_peak_after_release[env_ids] = float("nan")
            self._a2_pull_v61_hinge_reclosure_after_release_rad[env_ids] = 0.0
            if not self._a2_pull_v61_late_state_bank_capture_enabled:
                self._a2_pull_v61_d25_snapshot_captured[env_ids] = False
                self._a2_pull_v61_frame_snapshot_captured[env_ids] = False
                self._a2_pull_v61_e6_snapshot_captured[env_ids] = False
                self._a2_pull_v61_d25_snapshot_slot[env_ids] = -1
                self._a2_pull_v61_frame_snapshot_slot[env_ids] = -1
                self._a2_pull_v61_e6_snapshot_slot[env_ids] = -1
                self._a2_pull_v61_d25_snapshot_step[env_ids] = -1
                self._a2_pull_v61_frame_snapshot_step[env_ids] = -1
                self._a2_pull_v61_e6_snapshot_step[env_ids] = -1
            oracle_cfg = getattr(self, "_a2_hold_oracle_cfg", None)
            if oracle_cfg is not None and oracle_cfg.get("v6_p1_oracle_enabled", False):
                self._a2_pull_v6_p1_yaw_pivot_target_reached[env_ids] = False
                self._a2_pull_v6_p1_yaw_pivot_complete[env_ids] = False
                self._a2_pull_v6_p1_entry_settled[env_ids] = False
        if self._is_a2_pull_v5():
            self._a2_pull_v5_start_override_active[env_ids] = False
            self._a2_pull_v5_start_override_active_steps[env_ids] = 0
            self._a2_pull_v5_start_override_base_slice_equal[env_ids] = True
            self._a2_pull_v5_start_override_outside_window[env_ids] = False
            self._a2_pull_v5_probe_phase_index[env_ids] = 0
            self._a2_pull_v5_probe_phase_initialized[env_ids] = False
            self._a2_pull_v5_probe_phase_waypoint_arrived[env_ids] = False
            self._a2_pull_v5_probe_phase_yaw_arrived[env_ids] = False
            self._a2_pull_v5_probe_sequence_complete[env_ids] = False
            self._a2_pull_v5_scheduler_state[env_ids] = self._A2_PULL_V5_4_SCHEDULER_STATES["XY_TRACK"]
            self._a2_pull_v5_scheduler_coarse_raw[env_ids] = 0.0
            self._a2_pull_v5_scheduler_cutoff[env_ids] = 0.0
            self._a2_pull_v5_scheduler_min_settle_steps[env_ids] = 0
            self._a2_pull_v5_scheduler_settle_steps[env_ids] = 0
            self._a2_pull_v5_scheduler_trim_steps[env_ids] = 0
            self._a2_pull_v5_scheduler_terminal_hold_steps[env_ids] = 0
            self._a2_pull_v5_scheduler_raw_yaw_command[env_ids] = 0.0
            for env_id in env_ids.tolist():
                self._a2_pull_v5_scheduler_failure_reason[env_id] = None
        if self._a2_pull_v5_characterization_enabled:
            self._a2_pull_v5_characterization_pending[env_ids] = False
            self._a2_pull_v5_characterization_active[env_ids] = False
            self._a2_pull_v5_characterization_xy_target_initialized[env_ids] = False
            self._a2_pull_v5_characterization_xy_target[env_ids] = float("nan")
            self._a2_pull_v5_characterization_episode_indices[env_ids] = 0
            self._a2_pull_v5_characterization_step[env_ids] = -1
            self._a2_pull_v5_characterization_requested_u[env_ids] = 0.0
            self._a2_pull_v5_characterization_phase_u[env_ids] = 0.0
            self._a2_pull_v5_characterization_raw_base[env_ids] = 0.0
            self._a2_pull_v5_characterization_physical_base[env_ids] = 0.0
            self._a2_pull_v5_characterization_pre_root_pos[env_ids] = float("nan")
            self._a2_pull_v5_characterization_pre_root_yaw[env_ids] = float("nan")
            for env_id in env_ids.tolist():
                self._a2_pull_v5_characterization_phase[env_id] = "inactive"
        return result

    def record_a2_pull_release_or_hold_decision(self, decision_mask: torch.Tensor) -> None:
        """Latch an explicit E5 decision supplied by a probe or policy evaluator."""

        if (
            not torch.is_tensor(decision_mask)
            or decision_mask.shape != (self.num_envs,)
            or decision_mask.dtype != torch.bool
            or decision_mask.device != torch.device(self.device)
        ):
            raise RuntimeError(
                "Pull E5 decision requires a device-local bool vector with one value per env."
            )
        before_e4 = decision_mask & ~self._a2_pull_event_reached[
            :, A2PullEvent.E4_POSITIVE_HINGE_RETAINED
        ]
        if torch.any(before_e4):
            raise RuntimeError("Pull E5 decision cannot be recorded before E4.")
        if self._get_a2_pull_threshold_mode() == "report_only":
            before_clearance = decision_mask & ~self._a2_pull_clearance_ready
            if torch.any(before_clearance):
                raise RuntimeError("Pull E5 decision cannot be recorded before measured clearance.")
        self._a2_pull_release_or_hold_decision |= decision_mask

    def _get_obs_z_a2_pull_v6_release_mode(self) -> torch.Tensor:
        """Expose the live v6 release decision state without history."""

        if self.config.get("completion_stage") == self.STAGE_GRASP:
            return torch.zeros((self.num_envs, 2), device=self.device)

        return torch.stack(
            (
                self._a2_pull_v6_release_ready,
                self._a2_pull_v6_release_event,
            ),
            dim=-1,
        ).float()

    def _get_obs_z_a2_pull_v6_hinge_velocity(self) -> torch.Tensor:
        """Expose current hinge velocity for post-release door-dynamics disambiguation."""

        return self.simulator.get_task_dof_vel("door")[:, :1]

    def _get_obs_z_a2_pull_e3_latched(self) -> torch.Tensor:
        return self._a2_pull_event_reached[
            :, A2PullEvent.E3_LATCH_RELEASE
        ].float().unsqueeze(-1)

    def _get_obs_a2_pull_h10_gate_info(self) -> torch.Tensor:
        """Reuse the 8-D gate shape while replacing unused IO with live E3."""

        gate = self._get_obs_privileged_door_info().clone()
        gate[:, 7] = self._a2_pull_event_reached[
            :, A2PullEvent.E3_LATCH_RELEASE
        ].float()
        return gate

    def _get_obs_z_a2_pull_v61_post_release_control(self) -> torch.Tensor:
        """Expose the latched D25 controller handoff without changing release semantics."""

        required = self.config["a2_pull_v6_release_persistence_steps"]
        active = self._a2_pull_v6_clean_release & (
            self._a2_pull_v61_post_release_control_active
            | (self._a2_pull_v6_release_persistence >= required)
        )
        return active[:, None].float()

    def _get_a2_pull_whole_body_clear_mask(self, door_x: torch.Tensor) -> torch.Tensor:
        """Use every robot body position for the single E7 completion predicate."""

        robot_body_pos_w = self.simulator.scene.articulations["robot"].data.body_pos_w
        if (
            not torch.is_tensor(robot_body_pos_w)
            or robot_body_pos_w.ndim != 3
            or robot_body_pos_w.shape[0] != self.num_envs
            or robot_body_pos_w.shape[2] != 3
            or not torch.all(torch.isfinite(robot_body_pos_w))
            or tuple(door_x.shape) != (self.num_envs,)
            or door_x.device != robot_body_pos_w.device
        ):
            raise RuntimeError("Pull E7 requires finite high-level robot body_pos_w and door_x.")
        signed_body_progress = self._pull_direction.signed_crossing_progress(
            robot_body_pos_w[:, :, 0], door_x[:, None]
        )
        return torch.all(signed_body_progress > 1.5, dim=-1)

    def _get_a2_pull_door_frame_midpoint(self, door_states: torch.Tensor) -> torch.Tensor:
        """Return the shared world XY midpoint used by frame-passage predicates."""

        return door_states[:, 0:2]

    def _get_a2_pull_frame_approach_active_mask(self) -> torch.Tensor:
        """Return the exact v4 frame-approach reward activation mask."""
        active = (
            self._make_mask([self.STAGE_SWING, self.STAGE_THROUGH])
            & self._a2_pull_aperture_ready
            & ~self._a2_pull_frame_passage
        )
        if self._is_a2_pull_v6():
            active &= self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D
        return active

    def _get_a2_pull_minimum_panel_robot_clearance(self) -> torch.Tensor:
        """Return the signed trunk-footprint clearance to the current door-panel slab."""

        door_states = self.simulator.get_task_root_state("door")
        door_data = self.simulator.scene.articulations["door"].data
        robot_data = self.simulator.scene.articulations["robot"].data
        panel_body_quat_w = door_data.body_quat_w[:, self._a2_pull_door_panel_body_id]
        trunk_body_pos_w = robot_data.body_pos_w[:, self._a2_pull_trunk_body_id]
        if (
            not torch.is_tensor(door_states)
            or door_states.ndim != 2
            or door_states.shape[0] != self.num_envs
            or door_states.shape[1] < 7
            or not door_states.is_floating_point()
            or door_states.device != torch.device(self.device)
            or not torch.all(torch.isfinite(door_states))
            or not torch.is_tensor(panel_body_quat_w)
            or tuple(panel_body_quat_w.shape) != (self.num_envs, 4)
            or panel_body_quat_w.dtype != door_states.dtype
            or panel_body_quat_w.device != door_states.device
            or not torch.all(torch.isfinite(panel_body_quat_w))
            or not torch.is_tensor(trunk_body_pos_w)
            or tuple(trunk_body_pos_w.shape) != (self.num_envs, 3)
            or trunk_body_pos_w.dtype != door_states.dtype
            or trunk_body_pos_w.device != door_states.device
            or not torch.all(torch.isfinite(trunk_body_pos_w))
            or tuple(self.door_width.shape) != (self.num_envs,)
            or self.door_width.dtype != door_states.dtype
            or self.door_width.device != door_states.device
            or not torch.all(torch.isfinite(self.door_width))
            or tuple(self.door_open_lr.shape) != (self.num_envs,)
            or self.door_open_lr.dtype != door_states.dtype
            or self.door_open_lr.device != door_states.device
            or not torch.all(torch.isfinite(self.door_open_lr))
        ):
            raise RuntimeError(
                "Pull E5 signed clearance requires finite floating root, panel, trunk, "
                "and door metadata tensors on the simulation device."
            )
        if torch.any(self.door_width <= 2.0 * self._A2_PULL_PANEL_END_GAP_M):
            raise RuntimeError(
                "Pull E5 signed clearance requires door width greater than both panel "
                "gaps."
            )
        if torch.any(torch.abs(self.door_open_lr) != 1.0):
            raise RuntimeError("Pull E5 signed clearance requires door_open_lr exactly +/-1.")

        _, _, door_root_yaw = euler_xyz_from_quat(door_states[:, 3:7])
        _, _, panel_yaw = euler_xyz_from_quat(panel_body_quat_w)
        root_cos = torch.cos(door_root_yaw)
        root_sin = torch.sin(door_root_yaw)
        hinge_local_x = torch.full_like(self.door_width, self._A2_PULL_DOOR_HINGE_LOCAL_X_M)
        hinge_local_y = -0.5 * self.door_width * self.door_open_lr
        hinge_world_xy = door_states[:, :2] + torch.stack(
            (
                root_cos * hinge_local_x - root_sin * hinge_local_y,
                root_sin * hinge_local_x + root_cos * hinge_local_y,
            ),
            dim=-1,
        )
        panel_axis_world = self.door_open_lr[:, None] * torch.stack(
            (-torch.sin(panel_yaw), torch.cos(panel_yaw)), dim=-1
        )
        panel_end_gap = torch.full_like(self.door_width, self._A2_PULL_PANEL_END_GAP_M)
        panel_end_distance = self.door_width - panel_end_gap
        panel_p0 = hinge_world_xy + panel_axis_world * panel_end_gap[:, None]
        panel_p1 = hinge_world_xy + panel_axis_world * panel_end_distance[:, None]
        panel_segment = panel_p1 - panel_p0
        segment_length_sq = torch.sum(panel_segment * panel_segment, dim=-1)
        if torch.any(segment_length_sq <= torch.finfo(door_states.dtype).eps):
            raise RuntimeError("Pull E5 signed clearance requires a non-degenerate panel segment.")

        trunk_center_xy = trunk_body_pos_w[:, :2]
        segment_projection = torch.sum(
            (trunk_center_xy - panel_p0) * panel_segment, dim=-1
        ) / segment_length_sq
        closest_panel_xy = panel_p0 + segment_projection.clamp(0.0, 1.0)[:, None] * panel_segment
        raw_signed = (
            torch.linalg.norm(trunk_center_xy - closest_panel_xy, dim=-1)
            - self._A2_PULL_PANEL_HALF_THICKNESS_M
            - self._A2_PULL_TRUNK_FOOTPRINT_RADIUS_M
        )
        body_panel_per_filter, _ = self._get_a2_door_body_panel_contact_forces()
        contact_with_ordered_trunk = body_panel_per_filter[:, 0] > 0.0
        minimum_clearance = torch.where(
            contact_with_ordered_trunk,
            torch.minimum(raw_signed, torch.zeros_like(raw_signed)),
            raw_signed,
        )
        if not torch.all(torch.isfinite(minimum_clearance)):
            raise RuntimeError("Pull E5 signed clearance must be finite.")
        return minimum_clearance

    def _get_a2_pull_control_proof_thresholds(self) -> tuple[float, float, float, int]:
        duration = self._get_required_positive_float_config(
            "a2_pull_control_proof_min_duration_s", "pull E2 proof duration"
        )
        retreat = self._get_required_positive_float_config(
            "a2_pull_control_proof_min_retreat_m", "pull E2 proof retreat"
        )
        tolerance = self._get_required_positive_float_config(
            "a2_pull_control_proof_monotone_tolerance_m", "pull E2 proof monotone tolerance"
        )
        steps_value = self.config.get("a2_pull_control_proof_min_streak_steps")
        if isinstance(steps_value, bool) or not isinstance(steps_value, int) or steps_value <= 0:
            raise RuntimeError(
                "a2_pull_control_proof_min_streak_steps must be a positive integer."
            )
        return duration, retreat, tolerance, steps_value

    def _get_a2_pull_load_bearing_income_mask(self) -> torch.Tensor:
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
            & self._a2_pull_capture_valid
            & self._a2_pull_proof_active
            & self._a2_pull_proof_valid
        )

    def _update_a2_pull_v6_state(
        self,
        *,
        bilateral_contact: torch.Tensor,
        no_handle_contact: torch.Tensor,
        panel_clear: torch.Tensor,
        door_joint_pos: torch.Tensor,
        door_joint_vel: torch.Tensor,
    ) -> None:
        """Update v6 post-E5 send/release state from live high-level tensors."""

        if not self._is_a2_pull_v6():
            return
        expected = (self.num_envs,)
        for name, value in (("bilateral_contact", bilateral_contact), ("no_handle_contact", no_handle_contact), ("panel_clear", panel_clear)):
            if not torch.is_tensor(value) or tuple(value.shape) != expected or value.dtype != torch.bool or value.device != torch.device(self.device):
                raise RuntimeError(f"Pull-v6 {name} must be a device-local bool vector {expected}.")
        for name, value in (("door_joint_pos", door_joint_pos), ("door_joint_vel", door_joint_vel)):
            if not torch.is_tensor(value) or tuple(value.shape) != (self.num_envs, 3) or value.device != torch.device(self.device) or not value.is_floating_point() or not torch.all(torch.isfinite(value)):
                raise RuntimeError(f"Pull-v6 {name} must be a finite device-local ({self.num_envs}, 3) tensor.")
        frame = self._get_a2_v20_piper_frame_data("Pull-v6 state update")
        tcp_pos_w = frame["source_pos_w"]
        tcp_quat_w = frame["source_quat_w"]
        handle_pos_w = frame["target_pos_w"][:, 0, :]
        handle_quat_w = frame["target_quat_w"][:, 0, :]
        robot_data = self.simulator.scene.articulations["robot"].data
        trunk_pos_w = robot_data.body_pos_w[:, self._a2_pull_trunk_body_id]
        trunk_quat_w = robot_data.body_quat_w[:, self._a2_pull_trunk_body_id]
        trunk_link_vel_w = robot_data.body_link_vel_w[:, self._a2_pull_trunk_body_id]
        for name, value, shape in (
            ("trunk_pos_w", trunk_pos_w, (self.num_envs, 3)),
            ("trunk_quat_w", trunk_quat_w, (self.num_envs, 4)),
            ("trunk_link_vel_w", trunk_link_vel_w, (self.num_envs, 6)),
        ):
            if not torch.is_tensor(value) or tuple(value.shape) != shape or value.device != tcp_pos_w.device or value.dtype != tcp_pos_w.dtype or not torch.all(torch.isfinite(value)):
                raise RuntimeError(f"Pull-v6 requires finite {name} with shape {shape} matching Piper frame dtype/device.")
        handle_in_trunk, _ = subtract_frame_transforms(trunk_pos_w, trunk_quat_w, handle_pos_w, handle_quat_w)
        handle_send_y = -self.door_open_lr * handle_in_trunk[:, 1]
        handle_to_tcp_pos, handle_to_tcp_quat = subtract_frame_transforms(handle_pos_w, handle_quat_w, tcp_pos_w, tcp_quat_w)
        door_frame = self._get_a2_v20_frame_data("Pull-v6 opening tangent")
        opening_tangent_w = a2_v20_handle_opening_tangent(
            door_frame["source_pos_w"],
            door_frame["source_quat_w"],
            door_frame["target_pos_source"][:, int(door_frame["grasp_target_idx"]), :],
            self.door_width,
            self.door_open_lr,
        )
        e5 = self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
        previous_phase_b = self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B
        capture = e5 & ~self._a2_pull_v6_pivot_valid
        root_states = self.simulator.robot_root_states
        _, _, root_yaw = euler_xyz_from_quat(trunk_quat_w)
        self._a2_pull_v6_pivot_xy[capture] = trunk_pos_w[capture, :2]
        self._a2_pull_v6_pivot_valid |= capture
        self._a2_pull_v6_handle_y_capture[capture] = handle_send_y[capture]
        self._a2_pull_v6_handle_y_best[capture] = handle_send_y[capture]
        self._a2_pull_v6_handle_to_tcp_capture_pos[capture] = handle_to_tcp_pos[capture]
        self._a2_pull_v6_handle_to_tcp_capture_quat[capture] = handle_to_tcp_quat[capture]
        self._a2_pull_v6_handle_to_tcp_valid |= capture
        self._a2_pull_v6_root_yaw_at_capture[capture] = root_yaw[capture]
        self._a2_pull_v6_subphase[capture] = self._A2_PULL_V6_PHASE_B
        self._a2_pull_v6_e5_snapshot_pending |= capture
        self._a2_pull_v6_handle_y_current[:] = handle_send_y
        self._a2_pull_v6_pivot_displacement_m[:] = torch.where(
            self._a2_pull_v6_pivot_valid,
            torch.linalg.vector_norm(trunk_pos_w[:, :2] - self._a2_pull_v6_pivot_xy, dim=-1),
            torch.full_like(self._a2_pull_v6_pivot_displacement_m, float("nan")),
        )
        self._a2_pull_v6_root_yaw_delta[:] = torch.where(
            self._a2_pull_v6_pivot_valid,
            wrap_to_pi(root_yaw - self._a2_pull_v6_root_yaw_at_capture),
            torch.full_like(root_yaw, float("nan")),
        )
        if self.dt <= 0.0 or not math.isfinite(float(self.dt)):
            raise RuntimeError(f"Pull-v6 requires positive finite dt; got {self.dt!r}.")
        best_y_valid = self._a2_pull_v6_pivot_valid & torch.isfinite(
            self._a2_pull_v6_handle_y_best
        )
        new_best_y = best_y_valid & (
            handle_send_y < self._a2_pull_v6_handle_y_best
        )
        self._a2_pull_v6_handle_side_progress[:] = torch.where(
            new_best_y,
            (self._a2_pull_v6_handle_y_best - handle_send_y) / float(self.dt),
            torch.zeros_like(handle_send_y),
        )
        self._a2_pull_v6_handle_y_best[:] = torch.where(
            new_best_y,
            handle_send_y,
            self._a2_pull_v6_handle_y_best,
        )
        target_y = self.config["a2_pull_v6_target_handle_y_m"]
        if isinstance(target_y, bool) or not isinstance(target_y, (int, float)) or not math.isfinite(float(target_y)) or float(target_y) >= 0.0:
            raise RuntimeError("Pull-v6 target-side threshold must be a finite negative Y coordinate.")
        crossed_now = self._a2_pull_v6_pivot_valid & (handle_send_y <= float(target_y))
        self._a2_pull_v6_handle_crossed |= crossed_now
        self._a2_pull_v6_handle_y_prev[:] = handle_send_y

        tcp_vel_w = torch.where(
            self._a2_pull_v6_prev_tcp_valid[:, None],
            (tcp_pos_w - self._a2_pull_v6_prev_tcp_pos_w) / float(self.dt),
            torch.zeros_like(tcp_pos_w),
        )
        send_phase = (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B) | (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C)
        taskspace = a2_v20_r2_taskspace_arm_carry(
            trunk_pos_w,
            trunk_link_vel_w[:, :3],
            trunk_link_vel_w[:, 3:],
            tcp_pos_w,
            tcp_vel_w,
            opening_tangent_w,
            self._a2_pull_v6_pivot_valid,
            bilateral_contact,
            send_phase,
            door_joint_vel[:, 0] > 0.0,
            self._get_required_positive_float_config("a2_pull_v6_tangent_activity_floor_mps", "Pull-v6 tangent activity floor"),
        )
        self._a2_pull_v6_positive_arm_tangent[:] = taskspace["positive_arm_tangent"]
        self._a2_pull_v6_positive_base_tangent[:] = taskspace["positive_base_tangent"]
        self._a2_pull_v6_positive_total_tangent[:] = taskspace["positive_total_tangent"]
        self._a2_pull_v6_instantaneous_arm_tangent_share[:] = taskspace[
            "arm_tangent_share"
        ]
        held_send = send_phase & bilateral_contact
        self._a2_pull_v6_arm_tangent_integral_m += torch.where(
            held_send,
            taskspace["positive_arm_tangent"] * float(self.dt),
            torch.zeros_like(taskspace["positive_arm_tangent"]),
        )
        self._a2_pull_v6_total_tangent_integral_m += torch.where(
            held_send,
            taskspace["positive_total_tangent"] * float(self.dt),
            torch.zeros_like(taskspace["positive_total_tangent"]),
        )
        accumulated_share = torch.where(
            self._a2_pull_v6_total_tangent_integral_m > 0.0,
            self._a2_pull_v6_arm_tangent_integral_m
            / self._a2_pull_v6_total_tangent_integral_m,
            torch.zeros_like(self._a2_pull_v6_total_tangent_integral_m),
        ).clamp(0.0, 1.0)
        self._a2_pull_v6_arm_tangent_share[:] = accumulated_share
        self._a2_pull_v6_last_held_arm_tangent_share[:] = torch.where(
            held_send,
            accumulated_share,
            self._a2_pull_v6_last_held_arm_tangent_share,
        )
        handoff_active = (
            (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
            & self._a2_pull_v6_pivot_valid
            & bilateral_contact
            & panel_clear
            & (self._a2_pull_v6_pivot_displacement_m <= self._get_required_positive_float_config(
                "a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"
            ))
            & (accumulated_share >= self._get_required_positive_float_config(
                "a2_pull_v6_release_min_arm_tangent_share",
                "Pull-v6 release minimum arm tangent share",
            ))
            & (door_joint_vel[:, 0] > 0.0)
        )
        self._a2_pull_v6_handoff_active[:] = handoff_active
        self._a2_pull_v6_handoff_reached |= handoff_active
        self._a2_pull_v6_handoff_active_steps += handoff_active.long()
        self._a2_pull_v6_handoff_reward_window[:] = (
            self._a2_pull_v6_handoff_reached
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
            & bilateral_contact
            & panel_clear
            & (self._a2_pull_v6_pivot_displacement_m <= self._get_required_positive_float_config(
                "a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"
            ))
            & (accumulated_share >= self._get_required_positive_float_config(
                "a2_pull_v6_release_min_arm_tangent_share",
                "Pull-v6 release minimum arm tangent share",
            ))
            & (door_joint_vel[:, 0] > 0.0)
        )
        release_side_qualified = (
            self._a2_pull_v6_pivot_valid
            & (handle_send_y <= self._get_required_positive_float_config(
                "a2_pull_v6_release_handle_y_m", "Pull-v6 release handle Y"
            ))
            & bilateral_contact
            & panel_clear
            & (self._a2_pull_v6_pivot_displacement_m <= self._get_required_positive_float_config(
                "a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"
            ))
            & (accumulated_share >= self._get_required_positive_float_config(
                "a2_pull_v6_release_min_arm_tangent_share",
                "Pull-v6 release minimum arm tangent share",
            ))
        )
        self._a2_pull_v6_release_side_qualified[:] = release_side_qualified
        arc = a2_v20_arc_tracking_quality(
            self._a2_pull_v6_handle_to_tcp_capture_pos,
            self._a2_pull_v6_handle_to_tcp_capture_quat,
            handle_to_tcp_pos,
            handle_to_tcp_quat,
            self._a2_pull_v6_handle_to_tcp_valid,
            position_tolerance_m=self._get_required_positive_float_config("a2_pull_v6_arc_position_tolerance_m", "Pull-v6 arc position tolerance"),
            orientation_tolerance_rad=self._get_required_positive_float_config("a2_pull_v6_arc_orientation_tolerance_rad", "Pull-v6 arc orientation tolerance"),
        )
        self._a2_pull_v6_arc_error_m[:] = torch.where(
            arc["valid"], arc["position_error_m"], torch.full_like(arc["position_error_m"], float("nan"))
        )
        self._a2_pull_v6_arc_quality[:] = arc["quality"]
        arm_pos = self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx]
        lower = self.dof_pos_humanly_lower_limit[:, self._upper_non_gripper_dof_idx]
        upper = self.dof_pos_humanly_upper_limit[:, self._upper_non_gripper_dof_idx]
        if not torch.all(torch.isfinite(arm_pos)) or not torch.all(torch.isfinite(lower)) or not torch.all(torch.isfinite(upper)) or torch.any(upper <= lower):
            raise RuntimeError("Pull-v6 arm workspace margin requires finite ordered A2 arm limits.")
        previous_workspace_margin = self._a2_pull_v6_workspace_margin.clone()
        current_workspace_margin = torch.minimum(
            (arm_pos - lower) / (upper - lower), (upper - arm_pos) / (upper - lower)
        ).amin(dim=-1)
        workspace_progress_valid = torch.isfinite(previous_workspace_margin) & torch.isfinite(
            current_workspace_margin
        )
        workspace_progress_ref = self._get_required_positive_float_config(
            "a2_pull_v6_release_min_arm_margin", "Pull-v6 workspace margin progress"
        )
        self._a2_pull_v6_workspace_margin_progress[:] = torch.where(
            workspace_progress_valid,
            ((current_workspace_margin - previous_workspace_margin) / workspace_progress_ref).clamp(
                -1.0, 1.0
            ),
            torch.zeros_like(current_workspace_margin),
        )
        self._a2_pull_v6_workspace_margin[:] = current_workspace_margin
        clearance = self._get_a2_pull_minimum_panel_robot_clearance()
        frame_delta_xy = self._get_a2_pull_door_frame_midpoint(
            self.simulator.get_task_root_state("door")
        ) - root_states[:, :2]
        previous_frame_lateral_deficit_m = self._a2_pull_v6_frame_lateral_deficit_m.clone()
        frame_lateral_delta_y_m = frame_delta_xy[:, 1]
        frame_lateral_deficit_m = torch.relu(
            torch.abs(frame_lateral_delta_y_m) - 0.5 * self.door_width
        )
        passage_ready = (frame_lateral_deficit_m == 0.0) & panel_clear
        self._a2_pull_v6_frame_lateral_delta_y_m[:] = frame_lateral_delta_y_m
        self._a2_pull_v6_frame_lateral_deficit_m[:] = frame_lateral_deficit_m
        self._a2_pull_v6_frame_passage_ready[:] = passage_ready
        passage_progress_valid = torch.isfinite(previous_frame_lateral_deficit_m) & torch.isfinite(
            frame_lateral_deficit_m
        )
        self._a2_pull_v6_passage_alignment_progress[:] = torch.where(
            passage_progress_valid,
            ((previous_frame_lateral_deficit_m - frame_lateral_deficit_m) / 0.10).clamp(
                -1.0, 1.0
            ),
            torch.zeros_like(frame_lateral_deficit_m),
        )
        pre_release_except_passage = (
            release_side_qualified
            & bilateral_contact
            & panel_clear
            & (door_joint_pos[:, 0] >= self._get_required_positive_float_config("a2_pull_v6_release_hinge_rad", "Pull-v6 release hinge"))
            & (door_joint_vel[:, 0] >= self._get_required_positive_float_config("a2_pull_v6_release_min_hinge_velocity_radps", "Pull-v6 release hinge velocity"))
            & (clearance >= self._get_required_positive_float_config("a2_pull_v6_release_min_clearance_m", "Pull-v6 release clearance"))
            & (self._a2_pull_v6_workspace_margin >= self._get_required_positive_float_config("a2_pull_v6_release_min_arm_margin", "Pull-v6 release arm margin"))
            & (self._a2_pull_v6_pivot_displacement_m <= self._get_required_positive_float_config("a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"))
        )
        self._a2_pull_v6_pre_release_except_passage[:] = pre_release_except_passage
        pre_release_ready = pre_release_except_passage
        self._a2_pull_v6_passage_alignment_progress_active[:] = (
            (self.stage_buf == self.STAGE_SWING)
            & previous_phase_b
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
            & self._a2_pull_v6_pivot_valid
            & self._a2_pull_v6_prev_bilateral_contact
            & bilateral_contact
            & panel_clear
            & passage_progress_valid
        )
        near_c_common = (
            (self.stage_buf == self.STAGE_SWING)
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
            & self._a2_pull_v6_pivot_valid
            & bilateral_contact
            & panel_clear
            & (door_joint_pos[:, 0] >= self._get_required_positive_float_config(
                "a2_pull_v6_release_hinge_rad", "Pull-v6 release hinge"
            ))
            & (door_joint_vel[:, 0] >= self._get_required_positive_float_config(
                "a2_pull_v6_release_min_hinge_velocity_radps", "Pull-v6 release hinge velocity"
            ))
            & (clearance >= self._get_required_positive_float_config(
                "a2_pull_v6_release_min_clearance_m", "Pull-v6 release clearance"
            ))
            & (self._a2_pull_v6_pivot_displacement_m <= self._get_required_positive_float_config(
                "a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"
            ))
            & (accumulated_share >= self._get_required_positive_float_config(
                "a2_pull_v6_release_min_arm_tangent_share", "Pull-v6 release minimum arm tangent share"
            ))
        )
        workspace_pass = self._a2_pull_v6_workspace_margin >= self._get_required_positive_float_config(
            "a2_pull_v6_release_min_arm_margin", "Pull-v6 release arm margin"
        )
        handle_side_pass = handle_send_y <= self._get_required_positive_float_config(
            "a2_pull_v6_release_handle_y_m", "Pull-v6 release handle Y"
        )
        if self._a2_pull_v6_near_c_capture_mode == "workspace_missing":
            near_c_snapshot_candidate = near_c_common & handle_side_pass & ~workspace_pass
        elif self._a2_pull_v6_near_c_capture_mode == "handle_side_missing":
            near_c_snapshot_candidate = near_c_common & workspace_pass & ~handle_side_pass
        else:
            near_c_snapshot_candidate = torch.zeros_like(near_c_common)
        self._a2_pull_v6_near_c_snapshot_pending |= (
            near_c_snapshot_candidate & ~self._a2_pull_v6_near_c_snapshot_captured
        )
        new_release_side_qualification = (
            (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
            & pre_release_ready
            & ~capture
        )
        self._a2_pull_v6_handle_cross_bonus[:] = new_release_side_qualification
        self._a2_pull_v6_subphase[new_release_side_qualification] = self._A2_PULL_V6_PHASE_C
        self._a2_pull_v6_pre_release_snapshot_pending |= new_release_side_qualification
        release_ready = (
            (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C)
            & pre_release_ready
        )
        self._a2_pull_v6_release_ready[:] = release_ready
        workspace_progress_phase = (
            previous_phase_b & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
        )
        if torch.any(workspace_progress_phase & ~torch.isfinite(self._a2_pull_v6_pivot_displacement_m)):
            raise RuntimeError("Pull-v6 workspace margin progress requires finite captured pivot displacement.")
        self._a2_pull_v6_workspace_margin_progress_active[:] = (
            (self.stage_buf == self.STAGE_SWING)
            & workspace_progress_phase
            & bilateral_contact
            & self._a2_pull_v6_prev_bilateral_contact
            & (self._a2_pull_v6_pivot_displacement_m <= self._get_required_positive_float_config(
                "a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"
            ))
        )
        release_event = self._a2_pull_v6_prev_bilateral_contact & no_handle_contact & ~self._a2_pull_v6_release_event
        self._a2_pull_v6_release_event |= release_event
        clean_event = release_event & self._a2_pull_v6_prev_release_ready
        premature_event = release_event & ~self._a2_pull_v6_prev_release_ready
        self._a2_pull_v6_clean_release_event[:] = clean_event
        self._a2_pull_v6_premature_release_event[:] = premature_event
        self._a2_pull_v6_clean_release |= clean_event
        self._a2_pull_v6_premature_release |= premature_event
        self._a2_pull_v61_clean_release_step[clean_event] = self.episode_length_buf[clean_event]
        self._a2_pull_v61_hinge_running_peak_after_release[clean_event] = door_joint_pos[
            clean_event, 0
        ]
        self._a2_pull_v6_release_quality[clean_event] = (
            self._a2_pull_v6_last_held_arm_tangent_share[clean_event]
        )
        self._a2_pull_v6_hinge_at_release[release_event] = door_joint_pos[release_event, 0]
        self._a2_pull_v6_hinge_velocity_at_release[release_event] = door_joint_vel[release_event, 0]
        self._a2_pull_v6_subphase[release_event] = self._A2_PULL_V6_PHASE_D
        post_clean_release = self._a2_pull_v6_clean_release & ~clean_event
        if torch.any(post_clean_release):
            running_peak = torch.maximum(
                self._a2_pull_v61_hinge_running_peak_after_release[post_clean_release],
                door_joint_pos[post_clean_release, 0],
            )
            self._a2_pull_v61_hinge_running_peak_after_release[post_clean_release] = running_peak
            self._a2_pull_v61_hinge_reclosure_after_release_rad[post_clean_release] = torch.maximum(
                self._a2_pull_v61_hinge_reclosure_after_release_rad[post_clean_release],
                running_peak - door_joint_pos[post_clean_release, 0],
            )
        phase_c_revert = (
            (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C)
            & ~pre_release_ready
            & ~release_event
        )
        self._a2_pull_v6_subphase[phase_c_revert] = self._A2_PULL_V6_PHASE_B
        clean_no_contact = self._a2_pull_v6_clean_release & no_handle_contact
        required_persistence = self.config["a2_pull_v6_release_persistence_steps"]
        self._a2_pull_v61_post_release_control_active |= (
            self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_release_persistence >= required_persistence)
        )
        self._a2_pull_v6_release_persistence[:] = torch.where(
            clean_no_contact,
            self._a2_pull_v6_release_persistence + 1,
            torch.zeros_like(self._a2_pull_v6_release_persistence),
        )
        self._a2_pull_v61_post_release_control_active |= (
            self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_release_persistence >= required_persistence)
        )
        self._a2_pull_v6_persistence_income_active |= (
            clean_event & ~self._a2_pull_v6_persistence_income_consumed
        )
        persistence_income_recontact = (
            self._a2_pull_v6_persistence_income_active & ~no_handle_contact
        )
        self._a2_pull_v6_persistence_recontact_event[:] = persistence_income_recontact
        persistence_income_complete = (
            self._a2_pull_v6_persistence_income_active
            & (
                self._a2_pull_v6_release_persistence
                > self.config["a2_pull_v6_release_persistence_steps"]
            )
        )
        self._a2_pull_v6_persistence_income_consumed |= (
            persistence_income_recontact | persistence_income_complete
        )
        self._a2_pull_v6_persistence_income_active &= (
            ~self._a2_pull_v6_persistence_income_consumed
        )
        oracle_cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if oracle_cfg is not None and oracle_cfg.get("v6_p1_oracle_enabled", False):
            released = self._a2_pull_v6_p1_release_commanded
            self._a2_pull_v6_p1_no_contact_seen |= released & no_handle_contact
            recontact = (
                released
                & self._a2_pull_v6_p1_no_contact_seen
                & self._a2_pull_v6_p1_prev_no_handle_contact
                & ~no_handle_contact
            )
            self._a2_pull_v6_p1_handle_recontact_count += recontact.long()
            self._a2_pull_v6_p1_prev_no_handle_contact[:] = no_handle_contact
        self._a2_pull_v6_prev_release_ready[:] = release_ready
        self._a2_pull_v6_prev_bilateral_contact[:] = bilateral_contact
        self._a2_pull_v6_prev_tcp_pos_w[:] = tcp_pos_w
        self._a2_pull_v6_prev_tcp_valid[:] = True
        if self._a2_pull_v6_stage4_bank_loaded:
            self._a2_pull_v6_e5_snapshot_pending.zero_()
            self._a2_pull_v6_pre_release_snapshot_pending.zero_()
        elif self.enable_staged_reset:
            if (
                self._a2_pull_v6_broadcast_first_natural_c_enabled
                and self._a2_pull_v6_first_natural_c_broadcast_done
            ):
                self._a2_pull_v6_e5_snapshot_pending.zero_()
                self._a2_pull_v6_pre_release_snapshot_pending.zero_()
            else:
                e5_snapshot = (
                    self._a2_pull_v6_e5_snapshot_pending
                    & (self.stage_buf == self.STAGE_SWING)
                    & self._a2_pull_v6_pivot_valid
                )
                self._a2_pull_v6_e5_snapshot_pending[e5_snapshot] = False
                if torch.any(e5_snapshot):
                    self._take_snapshot_of_buffered_states(e5_snapshot)
                near_c_snapshot = (
                    self._a2_pull_v6_near_c_snapshot_pending
                    & (self.stage_buf == self.STAGE_SWING)
                    & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
                    & self._a2_pull_v6_pivot_valid
                )
                self._a2_pull_v6_near_c_snapshot_pending[near_c_snapshot] = False
                self._a2_pull_v6_near_c_snapshot_captured |= near_c_snapshot
                if torch.any(near_c_snapshot):
                    self._take_snapshot_of_buffered_states(near_c_snapshot)
                    self._a2_pull_v6_near_c_snapshot_slot[near_c_snapshot] = (
                        self.staged_reset_num_samples[self.STAGE_SWING, near_c_snapshot] - 1
                    ).remainder(self.staged_reset_max_samples_per_stage)
                pre_release_snapshot = (
                    self._a2_pull_v6_pre_release_snapshot_pending
                    & (self.stage_buf == self.STAGE_SWING)
                    & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C)
                    & self._a2_pull_v6_release_ready
                    & self._a2_pull_v6_prev_release_ready
                )
                self._a2_pull_v6_pre_release_snapshot_pending[pre_release_snapshot] = False
                if torch.any(pre_release_snapshot):
                    self._take_snapshot_of_buffered_states(pre_release_snapshot)
                    if self._a2_pull_v6_broadcast_first_natural_c_enabled:
                        source_env_id = int(torch.where(pre_release_snapshot)[0][0].item())
                        source_slot = int(
                            (
                                self.staged_reset_num_samples[self.STAGE_SWING, source_env_id] - 1
                            ).remainder(self.staged_reset_max_samples_per_stage).item()
                        )
                        self._broadcast_a2_pull_v6_first_natural_c_snapshot(
                            source_env_id, source_slot
                        )
                if self._a2_pull_v6_first_natural_c_broadcast_done:
                    return
                d_snapshot_base = (
                    (self.stage_buf == self.STAGE_SWING)
                    & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
                    & self._a2_pull_v6_clean_release
                    & no_handle_contact
                    & self._a2_pull_v6_persistence_income_active
                    & ~self._a2_pull_v6_persistence_income_consumed
                )
                d1_snapshot = (
                    d_snapshot_base
                    & (self._a2_pull_v6_release_persistence == 1)
                    & ~self._a2_pull_v6_d1_snapshot_captured
                )
                self._a2_pull_v6_d1_snapshot_captured |= d1_snapshot
                if torch.any(d1_snapshot):
                    self._take_snapshot_of_buffered_states(d1_snapshot)
                d5_snapshot = (
                    d_snapshot_base
                    & (self._a2_pull_v6_release_persistence == 5)
                    & ~self._a2_pull_v6_d5_snapshot_captured
                )
                self._a2_pull_v6_d5_snapshot_captured |= d5_snapshot
                if torch.any(d5_snapshot):
                    self._take_snapshot_of_buffered_states(d5_snapshot)
                d25_snapshot = (
                    d_snapshot_base
                    & (self._a2_pull_v6_release_persistence == 25)
                    & ~self._a2_pull_v6_d25_snapshot_captured
                )
                self._a2_pull_v6_d25_snapshot_captured |= d25_snapshot
                if torch.any(d25_snapshot):
                    self._take_snapshot_of_buffered_states(d25_snapshot)

    @override
    def _pre_compute_observations_callback(self, env_ids=None, *, post_physics=False):
        super()._pre_compute_observations_callback(env_ids, post_physics=post_physics)
        if post_physics:
            self._update_a2_pull_event_telemetry(env_ids)
            self._finalize_a2_pull_v5_characterization_step()
            if getattr(self, "_a2_pull_v5_scheduler_enabled", False):
                if env_ids is not None:
                    raise RuntimeError(
                        "Pull-v5.4 scheduler trace requires the full post-physics callback."
                    )
                self._append_a2_pull_v5_scheduler_trace_rows()

    @override
    def _get_a2_route_crossing_coordinate(self, root_x: torch.Tensor) -> torch.Tensor:
        return self._pull_direction.signed_crossing_progress(root_x)

    @override
    def _update_a2_v20_state(self, env_ids=None) -> None:
        selectors = {
            "a2_v20_R1_send_curriculum_enabled": self._get_a2_v20_r1_send_curriculum_enabled(),
            "a2_v20_send_latch_enabled": self._get_a2_v20_send_latch_enabled(),
            "a2_v20_telemetry_enabled": self._get_a2_v20_telemetry_enabled(),
            "a2_v20_traversal_economics_enabled": self._get_a2_v20_traversal_economics_enabled(),
            "a2_v20_arm_tie_enabled": self._get_a2_v20_arm_tie_enabled(),
            "a2_corridor_enabled": self._get_a2_corridor_enabled(),
        }
        active = {name: value for name, value in selectors.items() if value}
        crossing_mode = self._get_a2_v20_pre_send_crossing_mode()
        if active or crossing_mode != "disabled":
            raise RuntimeError(
                "Pull-v0 keeps v20 send/crossing/corridor behavior disabled; "
                f"active={active}, crossing_mode={crossing_mode!r}."
            )
        return None

    def _update_a2_pull_event_telemetry(self, env_ids=None) -> None:
        selected = (
            torch.arange(self.num_envs, dtype=torch.long, device=self.device)
            if env_ids is None
            else env_ids
        )
        if (
            not torch.is_tensor(selected)
            or selected.ndim != 1
            or selected.dtype != torch.long
            or selected.device != torch.device(self.device)
            or torch.any(selected < 0)
            or torch.any(selected >= self.num_envs)
        ):
            raise RuntimeError("Pull event telemetry requires valid device-local env ids.")
        if self._is_a2_pull_v6():
            self._a2_pull_v61_e6_event_pulse[selected] = False
            self._a2_pull_v61_e7_event_pulse[selected] = False

        root_states = self.simulator.robot_root_states
        door_states = self.simulator.get_task_root_state("door")
        if (
            not torch.is_tensor(root_states)
            or root_states.ndim != 2
            or root_states.shape[0] != self.num_envs
            or root_states.shape[1] < 13
            or not torch.all(torch.isfinite(root_states))
            or not torch.is_tensor(door_states)
            or door_states.ndim != 2
            or door_states.shape[0] != self.num_envs
            or door_states.shape[1] < 7
            or not torch.all(torch.isfinite(door_states))
        ):
            raise RuntimeError("Pull event telemetry requires finite robot and door root states.")
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"Pull event telemetry requires positive finite dt; got {dt!r}.")
        control_step = self.episode_length_buf.to(dtype=torch.long)
        root_x = root_states[:, 0]
        door_x = door_states[:, 0]
        frame_midpoint_xy = self._get_a2_pull_door_frame_midpoint(door_states)
        frame_delta_xy = frame_midpoint_xy - root_states[:, 0:2]
        frame_midpoint_distance = torch.linalg.vector_norm(frame_delta_xy, dim=-1)
        frame_approach_now = torch.abs(frame_delta_xy[:, 0]) < 0.3
        in_frame_opening_now = torch.abs(frame_delta_xy[:, 1]) <= 0.5 * self.door_width
        self._a2_pull_frame_midpoint_distance_min_m[:] = torch.where(
            torch.isfinite(self._a2_pull_frame_midpoint_distance_min_m),
            torch.minimum(
                self._a2_pull_frame_midpoint_distance_min_m,
                frame_midpoint_distance,
            ),
            frame_midpoint_distance,
        )
        _, _, root_yaw = euler_xyz_from_quat(root_states[:, 3:7])
        _, _, door_yaw = euler_xyz_from_quat(door_states[:, 3:7])
        expected_approach_yaw = (1.0 + self._pull_direction.io_sign) * 0.5 * math.pi
        yaw_error = torch.abs(wrap_to_pi(root_yaw - door_yaw - expected_approach_yaw))

        # Stage-0 predicates are report-only telemetry and intentionally remain
        # separate from the oracle admission gate.
        grasp_target = self._compute_grasp_target()
        x_min, x_max, y_tol = self._get_a2_stage0_staging_band()
        self._a2_pull_stage0_staging_band[:] = a2_signed_stage0_staging_band_mask(
            root_states[:, :3], grasp_target, x_min, x_max, y_tol, self._pull_direction
        )
        arm_default = self._get_a2_arm_default_dof_pos()
        arm_deviation = torch.abs(
            self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx] - arm_default
        ).amax(dim=-1)
        arm_tolerance = self._get_required_positive_float_config(
            "a2_stage0_arm_default_max_deviation", "pull stage0 predicate telemetry"
        )
        self._a2_pull_stage0_arm_default[:] = arm_deviation < arm_tolerance
        base_command = self.get_physical_homie_commands()
        if (
            not torch.is_tensor(base_command)
            or tuple(base_command.shape) != (self.num_envs, 5)
            or base_command.device != torch.device(self.device)
            or not torch.all(torch.isfinite(base_command))
        ):
            raise RuntimeError("Pull stage0 predicate telemetry requires finite physical commands.")
        self._a2_pull_stage0_base_still[:] = torch.linalg.norm(
            base_command[:, :3], dim=-1
        ) <= 0.1

        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "pull event telemetry"
        )
        bilateral_contact = contact_masks["both_contact"]
        no_handle_contact = ~torch.any(contact_masks["contacting"], dim=-1)
        stable_contact = bilateral_contact & (
            self._get_a2_stage2_contact_stability_mask()
            | self._get_a2_hold_streak_ok_mask()
        )
        body_panel_per_filter, body_panel_total = self._get_a2_door_body_panel_contact_forces()
        arm_panel_per_filter, arm_panel_total = self._get_a2_door_arm_panel_contact_forces()
        del body_panel_per_filter, arm_panel_per_filter
        panel_clear = (body_panel_total + arm_panel_total) == 0.0

        # v3 traversal telemetry is pull-local and does not alter v0/v1/v2
        # predicates.  A frame passage is latched only inside the measured
        # door opening and while the panel-contact gate is clear.
        if self._is_a2_pull_traversal():
            frame_passage_now = (
                frame_approach_now & in_frame_opening_now & panel_clear
            )
            new_frame_passage = frame_passage_now & ~self._a2_pull_frame_passage
            self._a2_pull_frame_passage |= frame_passage_now
            self._a2_pull_frame_passage_step[new_frame_passage] = control_step[
                new_frame_passage
            ]
            self._a2_pull_frame_approach |= frame_approach_now & in_frame_opening_now
        else:
            frame_passage_now = torch.zeros_like(panel_clear)
            new_frame_passage = torch.zeros_like(panel_clear)

        # Report-only base path/reversal metrics use high-level root state and
        # the pull travel direction; they are never reward or stage inputs.
        base_pos_xy = root_states[:, :2]
        previous_base_valid = torch.all(
            torch.isfinite(self._a2_pull_prev_base_pos_xy), dim=-1
        )
        self._a2_pull_base_path_length_m += torch.where(
            previous_base_valid,
            torch.linalg.norm(base_pos_xy - self._a2_pull_prev_base_pos_xy, dim=-1),
            torch.zeros_like(self._a2_pull_base_path_length_m),
        )
        self._a2_pull_prev_base_pos_xy[:] = base_pos_xy
        travel_velocity = self._pull_direction.travel_dir_x * root_states[:, 7]
        previous_velocity_valid = torch.isfinite(self._a2_pull_prev_travel_velocity)
        velocity_reversal = (
            previous_velocity_valid
            & ((self._a2_pull_prev_travel_velocity > 0.0) != (travel_velocity > 0.0))
            & (travel_velocity != 0.0)
            & (self._a2_pull_prev_travel_velocity != 0.0)
        )
        self._a2_pull_base_reversal_count += velocity_reversal.long()
        self._a2_pull_prev_travel_velocity[:] = travel_velocity
        proof_duration_min, proof_retreat_min, monotone_tolerance, proof_steps_min = (
            self._get_a2_pull_control_proof_thresholds()
        )
        previous_root_valid = torch.isfinite(self._a2_pull_proof_last_root_x)
        root_outward_step = self._pull_direction.approach_side_x * (
            root_x - self._a2_pull_proof_last_root_x
        )
        monotone_break = (
            self._a2_pull_proof_active
            & previous_root_valid
            & (root_outward_step < -monotone_tolerance)
        )
        contact_loss = ~stable_contact
        reset_proof = contact_loss | monotone_break
        self._a2_pull_proof_active[reset_proof] = False
        self._a2_pull_proof_start_root_x[reset_proof] = float("nan")
        self._a2_pull_proof_duration_s[reset_proof] = 0.0
        self._a2_pull_proof_displacement_m[reset_proof] = 0.0
        self._a2_pull_proof_streak[reset_proof] = 0
        self._a2_pull_proof_valid[reset_proof] = False
        self._a2_pull_capture_valid[reset_proof] = False
        self._a2_pull_capture_root_x[reset_proof] = float("nan")
        self._a2_pull_max_tensile_retreat_m[reset_proof] = 0.0
        proof_start = stable_contact & ~self._a2_pull_proof_active & ~monotone_break
        self._a2_pull_proof_active[proof_start] = True
        self._a2_pull_proof_start_root_x[proof_start] = root_x[proof_start]
        self._a2_pull_capture_root_x[proof_start] = root_x[proof_start]
        self._a2_pull_capture_valid[proof_start] = True
        proof_live = self._a2_pull_proof_active & stable_contact
        self._a2_pull_proof_duration_s[proof_live] += dt
        proof_displacement = self._pull_direction.approach_side_x * (
            root_x - self._a2_pull_proof_start_root_x
        )
        finite_displacement = torch.isfinite(proof_displacement) & self._a2_pull_proof_active
        self._a2_pull_proof_displacement_m[:] = torch.where(
            finite_displacement,
            torch.clamp_min(proof_displacement, 0.0),
            torch.zeros_like(proof_displacement),
        )
        self._a2_pull_proof_streak[:] = torch.where(
            proof_live & (root_outward_step >= -monotone_tolerance),
            self._a2_pull_proof_streak + 1,
            torch.zeros_like(self._a2_pull_proof_streak),
        )
        self._a2_pull_proof_valid[:] = (
            proof_live
            & (self._a2_pull_proof_duration_s >= proof_duration_min)
            & (self._a2_pull_proof_displacement_m >= proof_retreat_min)
            & (self._a2_pull_proof_streak >= proof_steps_min)
        )
        self._a2_pull_proof_last_root_x[:] = root_x
        self._a2_pull_max_tensile_retreat_m[:] = torch.maximum(
            self._a2_pull_max_tensile_retreat_m,
            self._a2_pull_proof_displacement_m,
        )
        self._a2_pull_root_outward_excursion_m[:] = torch.maximum(
            self._a2_pull_root_outward_excursion_m,
            self._a2_pull_proof_displacement_m,
        )
        tensile_capture = self._a2_pull_proof_valid

        door_joint_pos = self._get_door_joint_pos("pull event telemetry", 3)
        threshold_mode = self._get_a2_pull_threshold_mode()
        latch_threshold_m = self._get_a2_pull_e3_latch_threshold_m()
        self._a2_pull_passage_attempt_hinge_rad[new_frame_passage] = door_joint_pos[
            new_frame_passage, 0
        ]
        handle_unlatched = door_joint_pos[:, 1] >= 0.3
        latch_released = door_joint_pos[:, 2] >= latch_threshold_m
        stable_unlatch_handle_now = stable_contact & handle_unlatched
        stable_unlatch_latch_now = stable_contact & latch_released
        stage3_to4_hinge_threshold = self._get_a2_stage3_to4_door_hinge_threshold()
        relock_handle_now = (
            self._a2_pull_prev_handle_unlatched
            & ~handle_unlatched
            & (door_joint_pos[:, 0] < stage3_to4_hinge_threshold)
        )
        relock_latch_now = (
            self._a2_pull_prev_latch_unlatched
            & ~latch_released
            & (door_joint_pos[:, 0] < stage3_to4_hinge_threshold)
        )
        self._a2_pull_stable_unlatch_handle_ever |= stable_unlatch_handle_now
        self._a2_pull_stable_unlatch_latch_ever |= stable_unlatch_latch_now
        self._a2_pull_relock_handle_ever |= relock_handle_now
        self._a2_pull_relock_latch_ever |= relock_latch_now
        self._a2_pull_prev_handle_unlatched[:] = handle_unlatched
        self._a2_pull_prev_latch_unlatched[:] = latch_released
        positive_hinge = door_joint_pos[:, 0] > 0.0
        first_positive = positive_hinge & torch.isnan(
            self._a2_pull_hinge_at_first_positive_progress_rad
        )
        self._a2_pull_hinge_at_first_positive_progress_rad[first_positive] = door_joint_pos[
            first_positive, 0
        ]
        held_hinge = stable_contact & positive_hinge
        self._a2_pull_held_hinge_max_rad[held_hinge] = torch.where(
            torch.isnan(self._a2_pull_held_hinge_max_rad[held_hinge]),
            door_joint_pos[held_hinge, 0],
            torch.maximum(
                self._a2_pull_held_hinge_max_rad[held_hinge], door_joint_pos[held_hinge, 0]
            ),
        )
        send_hinge_threshold = self._get_a2_v20_send_hinge_threshold()
        aperture_ready_now = stable_contact & (door_joint_pos[:, 0] >= send_hinge_threshold)
        self._a2_pull_aperture_ready |= aperture_ready_now
        if self._is_a2_pull_v5():
            # Persistent release is a K-step no-handle-contact latch after
            # aperture; panel-clear remains a separate diagnostic and must not
            # gate this release predicate.
            persistent_candidate = self._a2_pull_aperture_ready & no_handle_contact
            self._a2_pull_v5_persistent_release_streak[:] = torch.where(
                persistent_candidate,
                self._a2_pull_v5_persistent_release_streak + 1,
                torch.zeros_like(self._a2_pull_v5_persistent_release_streak),
            )
            self._a2_pull_v5_persistent_release |= (
                self._a2_pull_v5_persistent_release_streak
                >= A2_PULL_V5_RELEASE_STREAK_STEPS
            )
        signed_crossing = self._pull_direction.signed_crossing_progress(root_x, door_x)
        planar_crossing_now = signed_crossing > 0.0
        new_planar_crossing = planar_crossing_now & ~self._a2_pull_planar_crossing
        self._a2_pull_planar_crossing |= planar_crossing_now
        self._a2_pull_planar_crossing_step[new_planar_crossing] = control_step[
            new_planar_crossing
        ]
        detour_now = self._is_a2_pull_traversal() & planar_crossing_now & ~self._a2_pull_frame_passage
        self._a2_pull_detour |= detour_now
        whole_body_crossing = self._get_a2_pull_whole_body_clear_mask(door_x)
        minimum_clearance = self._get_a2_pull_minimum_panel_robot_clearance()
        clearance_min = self._get_required_positive_float_config(
            "a2_pull_control_clearance_min_m", "pull E5 measured clearance"
        )
        self._a2_pull_minimum_panel_robot_clearance_m[:] = minimum_clearance
        self._a2_pull_clearance_ready[:] = minimum_clearance >= clearance_min
        self._a2_pull_swept_arc_clearance_margin_current_m[:] = minimum_clearance
        margin_valid = torch.isfinite(minimum_clearance)
        self._a2_pull_swept_arc_clearance_margin_min_m[:] = torch.where(
            torch.isfinite(self._a2_pull_swept_arc_clearance_margin_min_m),
            torch.minimum(
                self._a2_pull_swept_arc_clearance_margin_min_m,
                minimum_clearance,
            ),
            torch.where(
                margin_valid,
                minimum_clearance,
                self._a2_pull_swept_arc_clearance_margin_min_m,
            ),
        )
        body_contact_now = body_panel_total + arm_panel_total > 0.0
        self._a2_pull_body_panel_contact_steps[:] += body_contact_now.long()
        self._a2_pull_body_panel_contact_impulse_ns[:] += (
            (body_panel_total + arm_panel_total) * dt
        )
        deliberate_release_now = (
            self._is_a2_pull_traversal()
            & self._a2_pull_aperture_ready
            & self._a2_pull_prev_stable_contact
            & no_handle_contact
            & self._a2_pull_release_or_hold_decision
            & panel_clear
        )
        new_deliberate_release = deliberate_release_now & ~self._a2_pull_deliberate_release
        self._a2_pull_deliberate_release |= deliberate_release_now
        self._a2_pull_deliberate_release_step[new_deliberate_release] = control_step[
            new_deliberate_release
        ]
        post_release_recontact = (
            self._a2_pull_deliberate_release
            & body_contact_now
            & ~self._a2_pull_prev_panel_contact
        )
        self._a2_pull_post_release_recontact_count += post_release_recontact.long()
        self._a2_pull_prev_panel_contact[:] = body_contact_now
        self._a2_pull_prev_stable_contact[:] = stable_contact
        first_negative_x_motion = (
            (self._a2_pull_first_negative_x_motion_step < 0)
            & self._a2_pull_deliberate_release
            & (root_states[:, 7] < 0.0)
        )
        self._a2_pull_first_negative_x_motion_step[first_negative_x_motion] = control_step[
            first_negative_x_motion
        ]

        reached = self._a2_pull_event_reached
        if threshold_mode == "report_only":
            decision_mask = (
                reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
                & stable_contact
                & panel_clear
                & self._a2_pull_clearance_ready
            )
            self.record_a2_pull_release_or_hold_decision(decision_mask)
            decision_latched = decision_mask & ~torch.isfinite(
                self._a2_pull_hinge_at_decision_rad
            )
            self._a2_pull_hinge_at_decision_rad[decision_latched] = door_joint_pos[
                decision_latched, 0
            ]

        evidence = torch.zeros_like(reached)
        evidence[:, A2PullEvent.E0_RESET_VALID] = (
            (self._pull_direction.signed_distance_to_door(root_x, door_x) > 0.0)
            & (yaw_error < math.pi / 2.0)
            & panel_clear
        )
        evidence[:, A2PullEvent.E1_OUTSIDE_FACE_PREGRASP] = (
            (self.stage_buf >= self.STAGE_PREGRASP) & panel_clear
        )
        evidence[:, A2PullEvent.E2_TENSILE_CAPTURE] = tensile_capture
        if threshold_mode == "hard_gate":
            evidence[:, A2PullEvent.E3_LATCH_RELEASE] = (
                latch_released
                & stable_contact
            )
            evidence[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED] = (
                reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
                & (door_joint_pos[:, 0] > self._get_a2_stage3_to4_door_hinge_threshold())
                & stable_contact
                & panel_clear
            )
            evidence[:, A2PullEvent.E5_CLEARANCE_DECISION] = (
                self._a2_pull_aperture_ready & panel_clear
            )
        else:
            evidence[:, A2PullEvent.E3_LATCH_RELEASE] = (
                reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
                & latch_released
                & stable_contact
                & panel_clear
            )
            evidence[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED] = (
                reached[:, A2PullEvent.E3_LATCH_RELEASE]
                & positive_hinge
                & stable_contact
                & panel_clear
            )
            evidence[:, A2PullEvent.E5_CLEARANCE_DECISION] = (
                reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
                & self._a2_pull_release_or_hold_decision
                & self._a2_pull_clearance_ready
                & panel_clear
            )
        prior_reached = reached.clone()
        prior_first_event_step = self._a2_pull_first_event_step.clone()
        prior_first_event_time_s = self._a2_pull_first_event_time_s.clone()
        preview_reached, preview_first_event_step = advance_a2_pull_events(
            prior_reached[selected],
            evidence[selected],
            prior_first_event_step[selected],
            control_step[selected],
            event_predecessors=(
                A2_PULL_HARD_GATE_EVENT_PREDECESSORS
                if threshold_mode == "hard_gate"
                else None
            ),
        )
        self._a2_pull_event_reached[selected] = preview_reached
        self._a2_pull_first_event_step[selected] = preview_first_event_step
        preview_newly_reached = preview_reached & ~prior_reached[selected]
        preview_time = control_step[selected].to(dtype=torch.float32) * dt
        self._a2_pull_first_event_time_s[selected] = torch.where(
            preview_newly_reached,
            preview_time[:, None].expand_as(preview_newly_reached),
            prior_first_event_time_s[selected],
        )
        if self._is_a2_pull_v6():
            self._update_a2_pull_v6_state(
                bilateral_contact=bilateral_contact,
                no_handle_contact=no_handle_contact,
                panel_clear=panel_clear,
                door_joint_pos=self._get_door_joint_pos("Pull-v6 state update", 3),
                door_joint_vel=self._get_door_joint_vel("Pull-v6 state update", 3),
            )
        frame_requirement = (
            self._a2_pull_frame_passage
            if self._is_a2_pull_traversal()
            else torch.ones_like(self._a2_pull_event_reached[:, 0])
        )
        release_requirement = (
            self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_release_persistence >= 25)
            if self._is_a2_pull_v6()
            else torch.ones_like(self._a2_pull_event_reached[:, 0])
        )
        evidence[:, A2PullEvent.E6_PATH_REVERSAL_ENTRY] = (
            prior_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
            & (signed_crossing > 0.0)
            & (self._pull_direction.travel_dir_x * root_states[:, 7] > 0.0)
            & panel_clear
            & frame_requirement
            & release_requirement
        )
        evidence[:, A2PullEvent.E7_WHOLE_BODY_CLEAR] = (
            prior_reached[:, A2PullEvent.E6_PATH_REVERSAL_ENTRY]
            & whole_body_crossing
            & panel_clear
            & frame_requirement
        )
        old_reached = prior_reached[selected].clone()
        updated_reached, updated_first = advance_a2_pull_events(
            old_reached,
            evidence[selected],
            prior_first_event_step[selected],
            control_step[selected],
            event_predecessors=(
                A2_PULL_HARD_GATE_EVENT_PREDECESSORS
                if threshold_mode == "hard_gate"
                else None
            ),
        )
        newly_reached = updated_reached & ~old_reached
        self._a2_pull_event_reached[selected] = updated_reached
        if self._is_a2_pull_v6():
            self._a2_pull_v61_e6_event_pulse[selected] = newly_reached[
                :, A2PullEvent.E6_PATH_REVERSAL_ENTRY
            ]
            self._a2_pull_v61_e7_event_pulse[selected] = newly_reached[
                :, A2PullEvent.E7_WHOLE_BODY_CLEAR
            ]
        self._a2_pull_first_event_step[selected] = updated_first
        selected_time = control_step[selected].to(dtype=torch.float32) * dt
        self._a2_pull_first_event_time_s[selected] = torch.where(
            newly_reached,
            selected_time[:, None].expand_as(newly_reached).to(dtype=torch.float32),
            prior_first_event_time_s[selected],
        )
        if threshold_mode == "hard_gate":
            decision_mask = torch.zeros_like(self._a2_pull_release_or_hold_decision)
            decision_mask[selected] = (
                updated_reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
                & self._a2_pull_aperture_ready[selected]
                & panel_clear[selected]
            )
            self.record_a2_pull_release_or_hold_decision(decision_mask)
            decision_latched = decision_mask & ~torch.isfinite(
                self._a2_pull_hinge_at_decision_rad
            )
            self._a2_pull_hinge_at_decision_rad[decision_latched] = door_joint_pos[
                decision_latched, 0
            ]
        new_reversal = (
            (self._a2_pull_first_path_reversal_step[selected] < 0)
            & updated_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
            & (signed_crossing[selected] > 0.0)
        )
        self._a2_pull_first_path_reversal_step[selected[new_reversal]] = control_step[
            selected[new_reversal]
        ]
        self._update_a2_eval_pull_v61_post_release_intervention_after_post_physics()
        self._capture_a2_pull_v61_late_state_rows()

        frame_data = self._get_a2_gripper_handle_frame_transformer().data
        handle_to_tcp_pos = frame_data.target_pos_source[:, 0, :]
        if (
            not torch.is_tensor(handle_to_tcp_pos)
            or handle_to_tcp_pos.shape != (self.num_envs, 3)
            or not torch.all(torch.isfinite(handle_to_tcp_pos))
        ):
            raise RuntimeError("Pull slip telemetry requires finite handle-local TCP position.")
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"Pull slip telemetry requires positive finite dt; got {dt!r}.")
        derivative_valid = torch.all(
            torch.isfinite(self._a2_pull_prev_handle_to_tcp_pos), dim=-1
        )
        self._a2_pull_handle_local_slip_xyz_mps[:] = torch.where(
            derivative_valid[:, None],
            (handle_to_tcp_pos - self._a2_pull_prev_handle_to_tcp_pos) / dt,
            torch.full_like(handle_to_tcp_pos, float("nan")),
        )
        self._a2_pull_handle_local_slip_valid[:] = derivative_valid
        self._a2_pull_prev_handle_to_tcp_pos[:] = handle_to_tcp_pos
        self._capture_a2_pull_stage3_e3_snapshot(
            selected,
            newly_reached[:, A2PullEvent.E3_LATCH_RELEASE],
        )

    def _capture_a2_pull_stage3_e3_snapshot(
        self,
        selected_env_ids: torch.Tensor,
        newly_reached_e3: torch.Tensor,
    ) -> None:
        """Store same-env LEFT Stage3 states at the first natural E3 transition."""

        if not self._get_a2_pull_stage3_e3_snapshot_curriculum_enabled():
            return
        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError(
                "LEFT Stage-3 E3 snapshot capture requires staged-reset buffers."
            )
        if (
            not torch.is_tensor(selected_env_ids)
            or selected_env_ids.ndim != 1
            or selected_env_ids.dtype != torch.long
            or selected_env_ids.device != torch.device(self.device)
        ):
            raise RuntimeError(
                "LEFT Stage-3 E3 snapshot capture requires device-local env ids."
            )
        if (
            not torch.is_tensor(newly_reached_e3)
            or newly_reached_e3.shape != selected_env_ids.shape
            or newly_reached_e3.dtype != torch.bool
            or newly_reached_e3.device != torch.device(self.device)
        ):
            raise RuntimeError(
                "LEFT Stage-3 E3 snapshot capture requires a matching bool event mask."
            )
        capture = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        capture[selected_env_ids] = newly_reached_e3
        capture &= (
            (self.stage_buf == self.STAGE_OPEN)
            & (self.door_open_lr == 1.0)
            & ~self._a2_pull_event_reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
        )
        if torch.any(capture):
            if torch.any(
                ~self._a2_pull_event_reached[capture, A2PullEvent.E3_LATCH_RELEASE]
            ):
                raise RuntimeError(
                    "LEFT Stage-3 E3 snapshot capture lost its E3 event evidence."
                )
            self._take_snapshot_of_buffered_states(capture)
            self._a2_pull_stage3_e3_manual_snapshot_count[capture] += 1
        self.log_dict["a2_pull_stage3_e3_snapshot_count"] = (
            self._a2_pull_stage3_e3_manual_snapshot_count.float().sum()
        )
        self.log_dict["a2_pull_stage3_e3_snapshot_env_count"] = (
            (self._a2_pull_stage3_e3_manual_snapshot_count > 0).float().sum()
        )
        self.log_dict["a2_pull_stage3_e3_snapshot_right_count"] = (
            self._a2_pull_stage3_e3_manual_snapshot_count[
                self.door_open_lr == -1.0
            ].float().sum()
        )

    def _capture_a2_pull_v61_late_state_rows(self) -> None:
        """Capture canonical v6.1 rows from post-physics event state only."""

        if not self._is_a2_pull_v6() or not self._a2_pull_v61_late_state_bank_capture_enabled:
            return
        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError("Pull-v6.1 late-state capture requires staged-reset snapshots.")
        first_episode_mask = getattr(self, "_a2_eval_first_episode_active_mask", None)
        if (
            not torch.is_tensor(first_episode_mask)
            or tuple(first_episode_mask.shape) != (self.num_envs,)
            or first_episode_mask.dtype != torch.bool
            or first_episode_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("Pull-v6.1 late-state capture requires the evaluator first-episode mask.")
        capture_eligible = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        capture_eligible[self._a2_pull_v61_late_state_bank_capture_target_env_id] = True
        capture_eligible &= first_episode_mask

        def capture(
            mask: torch.Tensor, stage: int, captured: torch.Tensor,
            slots: torch.Tensor, control_steps: torch.Tensor,
        ) -> None:
            pending = mask & capture_eligible & ~captured
            if not torch.any(pending):
                return
            if torch.any(
                self.staged_reset_num_samples[stage, pending]
                >= self.staged_reset_max_samples_per_stage
            ):
                raise RuntimeError("Pull-v6.1 late-state capture exhausted the selected stage capacity.")
            self._take_snapshot_of_buffered_states(pending)
            slots[pending] = (
                self.staged_reset_num_samples[stage, pending] - 1
            ).remainder(self.staged_reset_max_samples_per_stage)
            captured[pending] = True
            control_steps[pending] = self.episode_length_buf[pending]

        capture(
            (self.stage_buf == self.STAGE_SWING)
            & self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_release_persistence == 25),
            self.STAGE_SWING,
            self._a2_pull_v61_d25_snapshot_captured,
            self._a2_pull_v61_d25_snapshot_slot,
            self._a2_pull_v61_d25_snapshot_step,
        )
        capture(
            (self.stage_buf == self.STAGE_SWING) & self._a2_pull_frame_passage,
            self.STAGE_SWING,
            self._a2_pull_v61_frame_snapshot_captured,
            self._a2_pull_v61_frame_snapshot_slot,
            self._a2_pull_v61_frame_snapshot_step,
        )

    @override
    def _post_compute_observations_callback(self):
        """Bind v6.1 E6 provenance to StagedTaskBase's exact Stage-5 snapshot."""

        previous_stage = self.stage_buf.clone()
        result = super()._post_compute_observations_callback()
        if not self._is_a2_pull_v6() or not self._a2_pull_v61_late_state_bank_capture_enabled:
            return result
        first_episode_mask = getattr(self, "_a2_eval_first_episode_active_mask", None)
        if first_episode_mask is None:
            return result
        if (
            not torch.is_tensor(first_episode_mask)
            or tuple(first_episode_mask.shape) != (self.num_envs,)
            or first_episode_mask.dtype != torch.bool
            or first_episode_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("Pull-v6.1 E6 capture requires the evaluator first-episode mask.")
        capture_eligible = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        capture_eligible[self._a2_pull_v61_late_state_bank_capture_target_env_id] = True
        capture_eligible &= first_episode_mask
        entered_stage5 = (
            (previous_stage == self.STAGE_SWING)
            & (self.stage_buf == self.STAGE_THROUGH)
            & self._a2_pull_event_reached[:, A2PullEvent.E6_PATH_REVERSAL_ENTRY]
            & capture_eligible
            & ~self._a2_pull_v61_e6_snapshot_captured
        )
        if not torch.any(entered_stage5):
            return result
        counts = self.staged_reset_num_samples[self.STAGE_THROUGH, entered_stage5]
        if torch.any(counts <= 0):
            raise RuntimeError("Pull-v6.1 E6 capture requires the automatic Stage-5 snapshot.")
        self._a2_pull_v61_e6_snapshot_slot[entered_stage5] = (
            counts - 1
        ).remainder(self.staged_reset_max_samples_per_stage)
        self._a2_pull_v61_e6_snapshot_step[entered_stage5] = self.episode_length_buf[entered_stage5]
        self._a2_pull_v61_e6_snapshot_captured[entered_stage5] = True
        return result

    def _update_a2_eval_pull_v61_post_release_intervention_after_post_physics(self) -> None:
        """Close active evaluator intervention from the authoritative post-step E7 latch."""

        if getattr(self, "_a2_pull_v61_post_release_intervention_cfg", None) is None:
            return
        reached_e7 = self._a2_pull_event_reached[:, A2PullEvent.E7_WHOLE_BODY_CLEAR]
        stopped = self._a2_pull_v61_post_release_intervention_active & reached_e7
        self._a2_pull_v61_post_release_intervention_active[stopped] = False
        for env_id in torch.where(stopped)[0].tolist():
            self._a2_pull_v61_post_release_intervention_stop_reason[env_id] = "e7"

    @override
    def _after_reward_components(self, raw_components, scaled_components):
        result = super()._after_reward_components(raw_components, scaled_components)
        if set(raw_components) != set(scaled_components) or not raw_components:
            raise RuntimeError("Pull telemetry requires complete non-empty reward component maps.")
        captured = {}
        for name, raw_value in raw_components.items():
            if (
                not torch.is_tensor(raw_value)
                or raw_value.shape != (self.num_envs,)
                or raw_value.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    f"Pull raw reward component {name!r} must be a device-local env vector."
                )
            value = raw_value.float() if raw_value.dtype == torch.bool else raw_value
            if not value.is_floating_point() or not torch.all(torch.isfinite(value)):
                raise RuntimeError(f"Pull raw reward component {name!r} must be finite.")
            captured[name] = value.detach().clone()
        self._a2_pull_last_raw_reward_components = captured
        if (self._is_a2_pull_v4() or self._is_a2_pull_v5() or self._is_a2_pull_v6()) and "a2_pull_frame_approach" not in self.reward_scales:
            self._a2_pull_frame_approach_active[:] = False
        if self._is_a2_pull_v4() or self._is_a2_pull_v5() or self._is_a2_pull_v6():
            self._a2_pull_frame_approach_pre_aperture_steps += (
                self._a2_pull_frame_approach_active & ~self._a2_pull_aperture_ready
            ).long()
            self._a2_pull_frame_approach_post_frame_passage_steps += (
                self._a2_pull_frame_approach_active & self._a2_pull_frame_passage
            ).long()
        if self._is_a2_pull_traversal():
            for reward_name in (
                "a2_corridor_door_wide",
                "a2_corridor_clean_passage",
            ):
                raw_value = captured.get(reward_name)
                if (
                    raw_value is None
                    and reward_name == "a2_corridor_door_wide"
                    and (self._is_a2_pull_v4() or self._is_a2_pull_v5() or self._is_a2_pull_v6())
                    and reward_name not in self.reward_scales
                ):
                    raw_value = torch.zeros(self.num_envs, device=self.device)
                if (
                    not torch.is_tensor(raw_value)
                    or tuple(raw_value.shape) != (self.num_envs,)
                    or raw_value.device != torch.device(self.device)
                    or not raw_value.is_floating_point()
                    or not torch.all(torch.isfinite(raw_value))
                ):
                    raise RuntimeError(
                        f"Pull-v3 telemetry requires finite raw reward component {reward_name!r}."
                    )
                pre_aperture = raw_value > 0.0
                if reward_name == "a2_corridor_door_wide":
                    self._a2_pull_corridor_door_wide_pre_aperture_steps += (
                        pre_aperture & ~self._a2_pull_aperture_ready
                    ).long()
                else:
                    self._a2_pull_corridor_clean_passage_pre_aperture_steps += (
                        pre_aperture & ~self._a2_pull_aperture_ready
                    ).long()
        if not self._a2_pull_runtime_telemetry_contract_checked:
            self._a2_pull_runtime_telemetry_contract_sample = (
                self.get_a2_pull_control_step_telemetry()
            )
            self._a2_pull_runtime_telemetry_contract_checked = True
        return result

    def _get_a2_pull_v5_terminal_invariants(
        self, env_id: int, reached: Mapping[str, bool]
    ) -> dict[str, bool]:
        source = self._a2_pull_v5_reset_source[env_id]
        declared_source = self._a2_pull_v5_declared_reset_source[env_id]
        declared_group = "bank" if declared_source.startswith("bank_") else "natural"
        actual_group = "bank" if source.startswith("bank_") else "natural"
        e2 = bool(reached[A2PullEvent.E2_TENSILE_CAPTURE.name])
        e4 = bool(reached[A2PullEvent.E4_POSITIVE_HINGE_RETAINED.name])
        e7 = bool(reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name])
        first_e4_step = int(self._a2_pull_first_event_step[env_id, A2PullEvent.E4_POSITIVE_HINGE_RETAINED].item())
        first_activation_step = int(self._a2_pull_first_scripted_activation_step[env_id].item())
        hinge_at_decision = self._a2_pull_hinge_at_decision_rad[env_id]
        override_steps = self.config.get(
            "a2_pull_v5_start_override_steps", A2_PULL_V5_START_OVERRIDE_STEPS
        )
        episode_step = int(self.episode_length_buf[env_id].item())
        override_active_now = bool(self._a2_pull_v5_start_override_active[env_id].item())
        override_active_outside_window = override_active_now and not (
            0 <= episode_step < int(override_steps)
        )
        stage4_below_gate = source != "natural" and (
            not torch.isfinite(hinge_at_decision) or hinge_at_decision < 1.60
        )
        return {
            "fake_e4": e4 and not e2,
            "stage4_snapshot_below_hinge_gate": bool(stage4_below_gate),
            "dont_push_before_true_stage3_to4": bool(
                e4 and first_activation_step >= 0 and first_e4_step >= 0 and first_activation_step < first_e4_step
            ),
            "target_root_before_aperture_ready": bool(
                not self._a2_pull_aperture_ready[env_id].item()
                and self._a2_pull_frame_approach_active[env_id].item()
            ),
            "corridor_active_before_aperture_ready": bool(
                self._a2_pull_corridor_door_wide_pre_aperture_steps[env_id].item() > 0
                or self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_id].item() > 0
            ),
            "complete_without_frame_passage": bool(
                e7 and not self._a2_pull_frame_passage[env_id].item()
            ),
            "frame_approach_active_before_aperture_ready": bool(
                self._a2_pull_frame_approach_pre_aperture_steps[env_id].item() > 0
            ),
            "frame_approach_active_after_frame_passage": bool(
                self._a2_pull_frame_approach_post_frame_passage_steps[env_id].item() > 0
            ),
            "canonical_not_counted_as_natural_start": bool(
                declared_group != actual_group
            ),
            "failed_settle_not_in_bank": bool(
                source != "natural" and self._get_a2_pull_v5_bank_settle_valid(env_id) is not True
            ),
            "override_active_outside_canonical_start": bool(
                (
                    source != "bank_natural_e5_override"
                    and self._a2_pull_v5_start_override_active_steps[env_id].item() > 0
                )
                or (
                    source != "bank_natural_e5_override" and override_active_now
                )
                or override_active_outside_window
                or self._a2_pull_v5_start_override_outside_window[env_id].item()
                or not self._a2_pull_v5_start_override_base_slice_equal[env_id].item()
            ),
        }

    def _get_a2_pull_v5_bank_settle_valid(self, env_id: int) -> bool | None:
        return True if self._a2_pull_v5_reset_source[env_id] != "natural" else None

    @override
    def init_a2_eval_hold_oracle(self, eval_config, *, diagnostic_enabled: bool) -> dict:
        cfg = super().init_a2_eval_hold_oracle(
            eval_config, diagnostic_enabled=diagnostic_enabled
        )
        if cfg["pull_h10m_live_pose_probe_enabled"]:
            if not self._is_a2_pull_v6():
                raise RuntimeError("H10-M live-pose probe requires the pull-v6 plan.")
            if self.num_envs != 16 or torch.any(self.door_open_lr != 1.0):
                raise RuntimeError(
                    "H10-M live-pose probe requires exactly 16 fixed-LEFT environments."
                )
            self._a2_pull_h10m_captured_handle_to_tcp_pos = torch.full(
                (self.num_envs, 3),
                float("nan"),
                dtype=torch.float32,
                device=self.device,
            )
            self._a2_pull_h10m_dls_correction_raw = torch.zeros(
                self.num_envs, 6, dtype=torch.float32, device=self.device
            )
            self._a2_pull_h10m_action_count = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_h10m_complete = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            return cfg
        if not cfg["v6_p1_oracle_enabled"]:
            return cfg
        if not self._is_a2_pull_v6():
            raise RuntimeError("A2 pull v6 P1 oracle requires the v6 pull plan.")
        self._a2_pull_v6_p1_phase = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_v6_p1_arc_reached = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v6_p1_release_commanded = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v6_p1_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_v6_p1_no_contact_seen = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v6_p1_handle_recontact_count = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_v6_p1_prev_no_handle_contact = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v6_p1_translation_relief_pending = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v6_p1_yaw_pivot_complete = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v6_p1_yaw_pivot_target_reached = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v6_p1_entry_settled = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        return cfg

    def init_a2_eval_r6u_passage_lateral_counterfactual(self, cfg: Mapping[str, object]) -> None:
        if not self._is_a2_pull_v6() or not getattr(self, "is_evaluating", False):
            raise RuntimeError("Pull-v6 passage lateral counterfactual requires an evaluating v6 pull env.")
        if set(cfg) != {
            "enabled",
            "target_env_id",
            "gain_s_inv",
            "max_world_y_speed_mps",
            "trigger_max_deficit_m",
            "pivot_guard_m",
        } or cfg["enabled"] is not True:
            raise RuntimeError("Pull-v6 passage lateral counterfactual requires its validated enabled config.")
        target_env_id = cfg["target_env_id"]
        if isinstance(target_env_id, bool) or not isinstance(target_env_id, int) or target_env_id >= self.num_envs:
            raise RuntimeError("Pull-v6 passage lateral target env must index this evaluation batch.")
        pivot_guard_m = cfg["pivot_guard_m"]
        relief_radius_m = self._get_required_positive_float_config(
            "a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"
        )
        if not isinstance(pivot_guard_m, float) or pivot_guard_m > relief_radius_m:
            raise RuntimeError("Pull-v6 passage lateral pivot guard must fit the configured relief radius.")
        if not self._clip_homie_command:
            raise RuntimeError("Pull-v6 passage lateral counterfactual requires configured HOMIE XY clips.")
        for key in ("clip_homie_linvel_x_threshold", "clip_homie_linvel_y_threshold"):
            value = float(self.config[key])
            if not math.isfinite(value) or value <= 0.0:
                raise RuntimeError(f"Pull-v6 passage lateral counterfactual requires positive {key}.")
        self._a2_pull_v6_r6u_passage_lateral_cfg = cfg
        self._a2_pull_v6_r6u_passage_lateral_started = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v6_r6u_passage_lateral_stopped = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )

    def init_a2_eval_pull_v61_post_release_intervention(self, cfg: Mapping[str, object]) -> None:
        """Register the evaluator-only v6.1 post-clean-release intervention."""

        required = {
            "enabled", "mode", "target_env_id", "arm_rate_rad_per_step",
            "base_waypoint_progress_m", "base_xy_gain_s_inv", "base_max_world_speed_mps",
        }
        if not self._is_a2_pull_v6() or not getattr(self, "is_evaluating", False):
            raise RuntimeError("Pull-v6.1 post-release intervention requires an evaluating v6 pull env.")
        if not isinstance(cfg, Mapping) or set(cfg) != required or cfg["enabled"] is not True:
            raise RuntimeError("Pull-v6.1 post-release intervention requires its exact enabled config.")
        if cfg["mode"] not in {"policy", "arm_reset", "base_corridor", "both"}:
            raise RuntimeError("Pull-v6.1 intervention mode must be policy, arm_reset, base_corridor, or both.")
        target_env_id = cfg["target_env_id"]
        if isinstance(target_env_id, bool) or not isinstance(target_env_id, int) or not 0 <= target_env_id < self.num_envs:
            raise RuntimeError("Pull-v6.1 intervention target env must index this evaluation batch.")
        for key in (
            "arm_rate_rad_per_step", "base_waypoint_progress_m",
            "base_xy_gain_s_inv", "base_max_world_speed_mps",
        ):
            value = cfg[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0.0:
                raise RuntimeError(f"Pull-v6.1 intervention {key} must be finite and positive.")
        if not isinstance(self._a2_base_command_scale, (int, float)) or self._a2_base_command_scale <= 0.0:
            raise RuntimeError("Pull-v6.1 intervention requires a positive base_command_scale.")
        if not self._clip_homie_command:
            raise RuntimeError("Pull-v6.1 corridor intervention requires configured HOMIE XY clips.")
        clip_x = float(self.config.clip_homie_linvel_x_threshold)
        clip_y = float(self.config.clip_homie_linvel_y_threshold)
        if not math.isfinite(clip_x) or not math.isfinite(clip_y) or clip_x <= 0.0 or clip_y <= 0.0:
            raise RuntimeError("Pull-v6.1 corridor intervention requires finite positive HOMIE XY clips.")
        if float(cfg["base_max_world_speed_mps"]) > min(clip_x, clip_y):
            raise RuntimeError("Pull-v6.1 corridor speed exceeds the configured HOMIE XY clips.")
        self._a2_pull_v61_post_release_intervention_cfg = dict(cfg)
        self._a2_pull_v61_post_release_intervention_started = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v61_post_release_intervention_active = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v61_post_release_intervention_start_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_v61_post_release_intervention_stop_reason = [None for _ in range(self.num_envs)]
        self._a2_pull_v61_post_release_policy_action = torch.zeros(
            (self.num_envs, 12), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v61_post_release_applied_action = torch.zeros(
            (self.num_envs, 12), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v61_post_release_waypoint_error_xy = torch.full(
            (self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v61_post_release_desired_world_xy = torch.full(
            (self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v61_post_release_arm_target = torch.full(
            (self.num_envs, 6), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v61_post_release_arm_target_change = torch.zeros(
            (self.num_envs, 6), dtype=torch.float32, device=self.device
        )

    def apply_a2_eval_pull_v61_post_release_intervention(
        self, policy_action: torch.Tensor, first_episode_mask: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Apply only post-release arm/base slices while retaining policy yaw and gripper."""

        cfg = getattr(self, "_a2_pull_v61_post_release_intervention_cfg", None)
        if cfg is None:
            raise RuntimeError("Pull-v6.1 post-release intervention requires initialization.")
        if (
            not torch.is_tensor(policy_action) or tuple(policy_action.shape) != (self.num_envs, 12)
            or not policy_action.is_floating_point() or policy_action.device != torch.device(self.device)
            or not torch.all(torch.isfinite(policy_action))
            or not torch.is_tensor(first_episode_mask) or tuple(first_episode_mask.shape) != (self.num_envs,)
            or first_episode_mask.dtype != torch.bool or first_episode_mask.device != policy_action.device
        ):
            raise RuntimeError("Pull-v6.1 post-release action hook input contract mismatch.")
        self._a2_pull_v61_post_release_policy_action[:] = policy_action
        self._a2_pull_v61_post_release_applied_action[:] = policy_action
        target_mask = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        target_mask[int(cfg["target_env_id"])] = True
        active = (
            target_mask & first_episode_mask & self._a2_pull_v6_clean_release
            & ~self._a2_pull_event_reached[:, A2PullEvent.E7_WHOLE_BODY_CLEAR]
        )
        starting = active & ~self._a2_pull_v61_post_release_intervention_started
        self._a2_pull_v61_post_release_intervention_started |= starting
        self._a2_pull_v61_post_release_intervention_active[:] = active
        self._a2_pull_v61_post_release_intervention_start_step[starting] = self.episode_length_buf[starting]
        if cfg["mode"] == "policy":
            return policy_action, active
        action = policy_action.clone()
        if cfg["mode"] in {"arm_reset", "both"}:
            if (
                not torch.is_tensor(self._delta_actions)
                or tuple(self._delta_actions.shape) != (self.num_envs, 6)
                or self._delta_actions.dtype != action.dtype
                or self._delta_actions.device != action.device
                or not torch.all(torch.isfinite(self._delta_actions))
                or not isinstance(self._delta_action_scale, (int, float))
                or self._delta_action_scale <= 0.0
            ):
                raise RuntimeError("Pull-v6.1 arm reset requires finite current delta targets and a positive scale.")
            delta_change = torch.clamp(
                -self._delta_actions,
                min=-float(cfg["arm_rate_rad_per_step"]),
                max=float(cfg["arm_rate_rad_per_step"]),
            )
            d_next = self._delta_actions + delta_change
            action[active, 5:11] = delta_change[active] / float(self._delta_action_scale)
            self._a2_pull_v61_post_release_arm_target[:] = d_next
            self._a2_pull_v61_post_release_arm_target_change[:] = delta_change
        if cfg["mode"] in {"base_corridor", "both"}:
            door_root = self.simulator.get_task_root_state("door")
            robot_root = self.simulator.scene.articulations["robot"].data.root_pos_w
            robot_quat = self.simulator.scene.articulations["robot"].data.root_quat_w
            if (
                not torch.is_tensor(door_root) or tuple(door_root.shape) != (self.num_envs, 13)
                or not torch.is_tensor(robot_root) or tuple(robot_root.shape) != (self.num_envs, 3)
                or not torch.is_tensor(robot_quat) or tuple(robot_quat.shape) != (self.num_envs, 4)
                or not torch.all(torch.isfinite(door_root)) or not torch.all(torch.isfinite(robot_root))
                or not torch.all(torch.isfinite(robot_quat))
            ):
                raise RuntimeError("Pull-v6.1 corridor intervention requires finite door and robot root state.")
            local_progress = torch.zeros((self.num_envs, 3), dtype=action.dtype, device=self.device)
            local_progress[:, 0] = self._pull_direction.travel_dir_x * float(cfg["base_waypoint_progress_m"])
            waypoint_xy = door_root[:, :2] + quat_apply(yaw_quat(door_root[:, 3:7]), local_progress)[:, :2]
            waypoint_error = waypoint_xy - robot_root[:, :2]
            desired_world = float(cfg["base_xy_gain_s_inv"]) * waypoint_error
            desired_speed = torch.linalg.vector_norm(desired_world, dim=-1)
            desired_world *= torch.clamp(
                float(cfg["base_max_world_speed_mps"]) / desired_speed, max=1.0
            )[:, None]
            desired_body = quat_apply_inverse(
                yaw_quat(robot_quat),
                torch.cat((desired_world, torch.zeros_like(desired_speed[:, None])), dim=-1),
            )[:, :2]
            clip_x = float(self.config.clip_homie_linvel_x_threshold)
            clip_y = float(self.config.clip_homie_linvel_y_threshold)
            if torch.any(active & ((torch.abs(desired_body[:, 0]) > clip_x) | (torch.abs(desired_body[:, 1]) > clip_y))):
                raise RuntimeError("Pull-v6.1 corridor command violates the configured HOMIE XY clip contract.")
            action[active, :2] = desired_body[active] / float(self._a2_base_command_scale)
            self._a2_pull_v61_post_release_waypoint_error_xy[:] = waypoint_error
            self._a2_pull_v61_post_release_desired_world_xy[:] = desired_world
        self._a2_pull_v61_post_release_applied_action[:] = action
        return action, active

    def apply_a2_eval_r6u_passage_lateral_counterfactual(
        self, policy_action: torch.Tensor, first_episode_active_mask: torch.Tensor
    ):
        cfg = getattr(self, "_a2_pull_v6_r6u_passage_lateral_cfg", None)
        if cfg is None:
            raise RuntimeError("Pull-v6 passage lateral action hook requires initialization.")
        layout = self.get_a2_high_level_action_layout()
        if (
            tuple(policy_action.shape) != (self.num_envs, layout["dim"])
            or not policy_action.is_floating_point()
            or policy_action.device != torch.device(self.device)
            or tuple(first_episode_active_mask.shape) != (self.num_envs,)
            or first_episode_active_mask.dtype != torch.bool
            or first_episode_active_mask.device != policy_action.device
        ):
            raise RuntimeError("Pull-v6 passage lateral action hook input contract mismatch.")
        target_mask = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        target_mask[int(cfg["target_env_id"])] = True
        deficit = self._a2_pull_v6_frame_lateral_deficit_m
        pivot_displacement = self._a2_pull_v6_pivot_displacement_m
        gate = (
            target_mask
            & first_episode_active_mask
            & (self.stage_buf == self.STAGE_SWING)
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
            & self._a2_pull_v6_pre_release_except_passage
            & ~self._a2_pull_v6_frame_passage_ready
            & self._a2_pull_v6_pivot_valid
            & torch.isfinite(deficit)
            & torch.isfinite(pivot_displacement)
            & (deficit > 0.0)
            & (deficit <= float(cfg["trigger_max_deficit_m"]))
            & (pivot_displacement < float(cfg["pivot_guard_m"]))
        )
        starting = gate & ~self._a2_pull_v6_r6u_passage_lateral_started & ~self._a2_pull_v6_r6u_passage_lateral_stopped
        self._a2_pull_v6_r6u_passage_lateral_started |= starting
        active = self._a2_pull_v6_r6u_passage_lateral_started & ~self._a2_pull_v6_r6u_passage_lateral_stopped
        self._a2_pull_v6_r6u_passage_lateral_stopped |= active & ~gate
        active &= ~self._a2_pull_v6_r6u_passage_lateral_stopped
        if not torch.any(active):
            return policy_action, torch.zeros_like(active)

        robot_data = self.simulator.scene.articulations["robot"].data
        root_pos_w = robot_data.root_pos_w
        root_quat_w = robot_data.root_quat_w
        trunk_pos_w = robot_data.body_pos_w[:, self._a2_pull_trunk_body_id]
        pivot_xy = self._a2_pull_v6_pivot_xy
        yaw_rotation = yaw_quat(root_quat_w)
        body_velocity = torch.zeros(
            self.num_envs, 3, dtype=policy_action.dtype, device=self.device
        )
        body_velocity[:, :2] = policy_action[:, :2] * self._a2_base_command_scale
        world_velocity = quat_apply(yaw_rotation, body_velocity)
        desired_world_y = torch.clamp(
            float(cfg["gain_s_inv"]) * self._a2_pull_v6_frame_lateral_delta_y_m,
            min=-float(cfg["max_world_y_speed_mps"]),
            max=float(cfg["max_world_y_speed_mps"]),
        )
        q = trunk_pos_w[:, :2] - pivot_xy
        r = trunk_pos_w[:, :2] - root_pos_w[:, :2]
        omega = self._a2_base_command_scale * policy_action[:, 2]
        yaw_trunk_velocity = omega[:, None] * torch.stack((-r[:, 1], r[:, 0]), dim=-1)
        base_q_next = q + float(self.dt) * (
            torch.stack((world_velocity[:, 0], torch.zeros_like(world_velocity[:, 0])), dim=-1)
            + yaw_trunk_velocity
        )
        radial_sq = float(cfg["pivot_guard_m"]) ** 2 - base_q_next[:, 0].square()
        feasible_radius = radial_sq >= 0.0
        radial_y = torch.sqrt(torch.clamp_min(radial_sq, 0.0))
        lower_world_y = (-radial_y - base_q_next[:, 1]) / float(self.dt)
        upper_world_y = (radial_y - base_q_next[:, 1]) / float(self.dt)
        feasible_world_y = torch.clamp(desired_world_y, lower_world_y, upper_world_y)
        candidate_world_velocity = world_velocity.clone()
        candidate_world_velocity[:, 1] = feasible_world_y
        candidate_body_velocity = quat_apply_inverse(yaw_rotation, candidate_world_velocity)
        clip_x = float(self.config.clip_homie_linvel_x_threshold)
        clip_y = float(self.config.clip_homie_linvel_y_threshold)
        command_valid = (
            active
            & feasible_radius
            & (self._a2_pull_v6_frame_lateral_delta_y_m * feasible_world_y > 0.0)
            & (torch.abs(candidate_body_velocity[:, 0]) <= clip_x)
            & (torch.abs(candidate_body_velocity[:, 1]) <= clip_y)
        )
        self._a2_pull_v6_r6u_passage_lateral_stopped |= active & ~command_valid
        if not torch.any(command_valid):
            return policy_action, command_valid
        action = policy_action.clone()
        action[command_valid, :2] = (
            candidate_body_velocity[command_valid, :2] / self._a2_base_command_scale
        )
        return action, command_valid

    @override
    def update_a2_eval_hold_oracle_after_step(
        self, first_episode_active_mask: torch.Tensor, done_mask: torch.Tensor
    ) -> None:
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if cfg is not None and cfg.get("pull_h10m_live_pose_probe_enabled", False):
            hinge = self._get_door_joint_pos("H10-M post-step outcome", 1)[:, 0]
            pending = (
                self._a2_hold_oracle_outcome
                == A2_HOLD_OUTCOME_TO_ID["PENDING"]
            )
            self._set_a2_hold_outcome(
                pending
                & self._a2_hold_oracle_activated
                & (hinge >= cfg["pull_h10m_hinge_target_rad"]),
                "RETAINED",
            )
            pending = (
                self._a2_hold_oracle_outcome
                == A2_HOLD_OUTCOME_TO_ID["PENDING"]
            )
            self._set_a2_hold_outcome(
                pending & done_mask & ~self._a2_hold_oracle_activated,
                "NO_GATE",
            )
            self._set_a2_hold_outcome(
                pending & done_mask & self._a2_hold_oracle_activated,
                "PUSH_TIMEOUT",
            )
            return
        if cfg is None or not cfg["v6_p1_oracle_enabled"]:
            return super().update_a2_eval_hold_oracle_after_step(
                first_episode_active_mask, done_mask
            )
        _, contact_masks = self._a2_v20_arc_probe_bilateral_gate()
        bilateral = (
            contact_masks["both_contact"]
            & self._get_a2_stage3_stage4_contact_stability_mask()
            & ~contact_masks["over_force"]
        )
        wait_e5 = self._a2_pull_v6_p1_phase == 0
        qualifying = (
            wait_e5
            & first_episode_active_mask
            & ~done_mask
            & self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
            & self._a2_pull_v6_pivot_valid
            & self._a2_pull_v6_handle_to_tcp_valid
            & bilateral
            & self._get_a2_hold_streak_ok_mask()
        )
        self._a2_v20_arc_probe_handoff_streak[:] = torch.where(
            qualifying,
            self._a2_v20_arc_probe_handoff_streak + 1,
            torch.zeros_like(self._a2_v20_arc_probe_handoff_streak),
        )
        ready = qualifying & (
            self._a2_v20_arc_probe_handoff_streak
            >= cfg["v20_arc_probe_handoff_streak_steps"]
        )
        self._a2_v20_arc_probe_handoff_ready |= ready
        self._a2_pull_v6_p1_phase[
            self._a2_pull_event_reached[:, A2PullEvent.E7_WHOLE_BODY_CLEAR]
        ] = 4

    @override
    def apply_a2_eval_hold_oracle_action_override(
        self, policy_action: torch.Tensor, first_episode_active_mask: torch.Tensor
    ):
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if cfg is not None and cfg.get("pull_h10m_live_pose_probe_enabled", False):
            return self._apply_a2_pull_h10m_live_pose_probe(
                policy_action, first_episode_active_mask
            )
        if cfg is None or not cfg["v6_p1_oracle_enabled"]:
            return super().apply_a2_eval_hold_oracle_action_override(
                policy_action, first_episode_active_mask
            )
        activate = (
            (self._a2_pull_v6_p1_phase == 0)
            & first_episode_active_mask
            & self._a2_v20_arc_probe_handoff_ready
        )
        if torch.any(activate):
            self._a2_hold_oracle_activated[activate] = True
            self._a2_pull_v6_p1_phase[activate] = 1
        arc = self._a2_pull_v6_p1_phase == 1
        if torch.any(arc):
            robot_data = self.simulator.scene.articulations["robot"].data
            planar_root_speed = torch.linalg.vector_norm(
                robot_data.root_lin_vel_w[:, :2], dim=-1
            )
            self._a2_pull_v6_p1_entry_settled |= (
                arc
                & (planar_root_speed <= 0.10)
                & (torch.abs(robot_data.root_ang_vel_w[:, 2]) <= 0.10)
            )
            self._a2_pull_v6_p1_yaw_pivot_target_reached |= (
                arc
                & self._a2_pull_v6_p1_entry_settled
            )
            self._a2_pull_v6_p1_yaw_pivot_complete |= (
                arc
                & self._a2_pull_v6_p1_entry_settled
            )
            action, mask = self._apply_a2_v20_arc_probe_action(
                policy_action, first_episode_active_mask, activate
            )
            pre_entry_settle_rows = (
                arc & mask & ~self._a2_pull_v6_p1_entry_settled
            )
            action[pre_entry_settle_rows, :3] = 0.0
            self._a2_hold_oracle_base_relief_body_velocity_command[
                pre_entry_settle_rows, :3
            ] = 0.0
            self._a2_hold_oracle_base_relief_raw_command[
                pre_entry_settle_rows, :3
            ] = 0.0
            self._a2_v20_arc_probe_f1_physical_yaw_command[
                pre_entry_settle_rows
            ] = 0.0
            self._a2_v20_arc_probe_f1_raw_yaw_command[pre_entry_settle_rows] = 0.0
            self._a2_hold_oracle_post_override_action = action
            self._a2_pull_v6_p1_steps[arc] += 1
            return action, mask
        controlled = (self._a2_pull_v6_p1_phase == 2) | (
            self._a2_pull_v6_p1_phase == 3
        )
        if not torch.any(controlled):
            self._a2_hold_oracle_last_override_mask.zero_()
            self._a2_hold_oracle_post_override_action = policy_action
            return policy_action, self._a2_hold_oracle_last_override_mask
        action = policy_action.clone()
        action[controlled, :11] = 0.0
        action[controlled, 5:11] = (
            -self._delta_actions[controlled] / self._delta_action_scale
        )
        desired_world = torch.zeros(
            self.num_envs, 2, dtype=action.dtype, device=action.device
        )
        desired_world[:, 0] = self._pull_direction.travel_dir_x
        door_root_y = self.simulator.get_task_root_state("door")[:, 1]
        robot_root_y = self.simulator.scene.articulations["robot"].data.root_pos_w[:, 1]
        desired_world[:, 1] = torch.clamp(
            2.0 * (door_root_y - robot_root_y), min=-0.5, max=0.5
        )
        _, _, _, through_raw = a2_hold_base_relief_command(
            desired_world,
            self.simulator.scene.articulations["robot"].data.root_quat_w,
            controlled,
            cfg["v6_p1_through_speed_mps"],
            self._a2_base_command_scale,
            1.0e-6,
        )
        action[controlled, :2] = through_raw[controlled, :2]
        action[controlled, 11] = 1.0
        release = controlled & (self._a2_pull_v6_p1_phase == 2)
        self._a2_pull_v6_p1_release_commanded |= release
        self._a2_pull_v6_p1_phase[release] = 3
        self._a2_pull_v6_p1_steps[release] = 0
        self._a2_pull_v6_p1_steps[controlled] += 1
        self._a2_hold_oracle_last_override_mask = controlled.clone()
        self._a2_hold_oracle_post_override_action = action
        return action, controlled

    def _apply_a2_pull_h10m_live_pose_probe(
        self,
        policy_action: torch.Tensor,
        first_episode_active_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Apply an eval-only LEFT Stage3 DLS arm target at the live handle pose."""

        cfg = self._a2_hold_oracle_cfg
        if not cfg["enabled"] or not getattr(self, "is_evaluating", False):
            raise RuntimeError("H10-M live-pose probe requires an evaluating hold oracle.")
        if torch.any(self.door_open_lr != 1.0):
            raise RuntimeError("H10-M live-pose probe requires a fixed-LEFT evaluation.")
        layout = self.get_a2_high_level_action_layout()
        if tuple(policy_action.shape) != (self.num_envs, layout["dim"]):
            raise RuntimeError("H10-M live-pose probe policy action shape mismatch.")
        eligible = (
            first_episode_active_mask
            & (self.stage_buf == self.STAGE_OPEN)
        )
        entering = eligible & ~self._a2_hold_oracle_activated
        if torch.any(entering):
            if torch.any(
                ~self._a2_pull_event_reached[
                    entering, A2PullEvent.E2_TENSILE_CAPTURE
                ]
            ):
                raise RuntimeError("H10-M Stage3 entry requires prior E2 evidence.")
            piper_frame = self._get_a2_v20_piper_frame_data(
                "H10-M Stage3-entry capture"
            )
            self._a2_pull_h10m_captured_handle_to_tcp_pos[entering] = (
                piper_frame["handle_to_tcp_pos"][entering]
            )
            frames = self._get_a2_hold_oracle_world_frames()
            relative_quat, captured = a2_hold_capture_handoff_relative_orientation(
                frames["handle_pos_w"],
                frames["handle_quat_w"],
                frames["source_pos_w"],
                frames["source_quat_w"],
                entering,
                self._a2_hold_oracle_handoff_relative_quat,
                self._a2_hold_oracle_handoff_orientation_captured,
            )
            self._a2_hold_oracle_handoff_relative_quat = relative_quat
            self._a2_hold_oracle_handoff_orientation_captured = captured
            self._a2_hold_oracle_activated |= entering
            first_activation = entering & (
                self._a2_pull_first_scripted_activation_step < 0
            )
            self._a2_pull_first_scripted_activation_step[first_activation] = (
                self.episode_length_buf[first_activation]
            )
        hinge = self._get_door_joint_pos("H10-M live-pose probe", 1)[:, 0]
        reached_target = hinge >= cfg["pull_h10m_hinge_target_rad"]
        timed_out = (
            self._a2_pull_h10m_action_count >= cfg["pull_h10m_timeout_steps"]
        )
        pending = (
            self._a2_hold_oracle_outcome
            == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        )
        self._set_a2_hold_outcome(
            pending & self._a2_hold_oracle_activated & reached_target,
            "RETAINED",
        )
        self._set_a2_hold_outcome(
            pending & self._a2_hold_oracle_activated & timed_out,
            "PUSH_TIMEOUT",
        )
        self._a2_pull_h10m_complete |= reached_target | timed_out
        active = (
            eligible
            & self._a2_hold_oracle_activated
            & ~self._a2_pull_h10m_complete
        )
        if not torch.any(active):
            self._a2_hold_oracle_last_override_mask.zero_()
            self._a2_hold_oracle_post_override_action = policy_action
            return policy_action, self._a2_hold_oracle_last_override_mask

        captured_offset = self._a2_pull_h10m_captured_handle_to_tcp_pos.to(
            dtype=policy_action.dtype
        )
        local_offset = torch.where(
            active[:, None], captured_offset, torch.zeros_like(captured_offset)
        )
        if torch.any(~torch.isfinite(local_offset[active])):
            raise RuntimeError("H10-M active rows require a captured handle-to-TCP position.")
        (
            q_correction_target,
            ik_valid,
            singular_values,
            condition,
            target_pos_root,
            target_quat_root,
            position_residual,
            orientation_residual,
            bounded_command_pos_root,
            bounded_command_quat_root,
            bounded_position_step,
            bounded_orientation_step,
            _,
            _,
            _,
        ) = self._compute_a2_hold_oracle_joint_target(local_offset, active)
        ik_valid = (
            torch.all(torch.isfinite(q_correction_target), dim=-1)
            & torch.all(torch.isfinite(singular_values), dim=-1)
            & torch.isfinite(condition)
        )
        robot = self.simulator.scene.articulations["robot"]
        joint_ids = self._a2_hold_oracle_joint_ids
        q_current = robot.data.joint_pos[:, joint_ids]
        correction = torch.clamp(
            q_correction_target - q_current,
            min=-cfg["pull_h10m_joint_correction_step_max_rad"],
            max=cfg["pull_h10m_joint_correction_step_max_rad"],
        )
        arm_slice = slice(layout["arm_start"], layout["arm_end"])
        d_prev = self._delta_actions.clone()
        d_policy_next = d_prev + (
            policy_action[:, arm_slice] * float(self.config.delta_action_scale)
        )
        q_default = robot.data.default_joint_pos[:, joint_ids]
        if q_default.shape[0] == 1:
            q_default = q_default.repeat(self.num_envs, 1)
        q_policy_next = q_default + (
            float(self.config.robot.control.action_scale) * d_policy_next
        )
        hard_limits = robot.data.joint_pos_limits[:, joint_ids]
        soft_limits = robot.data.soft_joint_pos_limits[:, joint_ids]
        hard_lower = hard_limits[..., 0] + cfg["joint_limit_margin"]
        hard_upper = hard_limits[..., 1] - cfg["joint_limit_margin"]
        soft_lower = soft_limits[..., 0] + cfg["joint_limit_margin"]
        soft_upper = soft_limits[..., 1] - cfg["joint_limit_margin"]
        correction = torch.where(
            (q_current < hard_lower) & (correction < 0.0),
            torch.zeros_like(correction),
            correction,
        )
        correction = torch.where(
            (q_current > hard_upper) & (correction > 0.0),
            torch.zeros_like(correction),
            correction,
        )
        current_inside_hard = (
            (q_current >= hard_lower) & (q_current <= hard_upper)
        )
        projected_hard_target = torch.clamp(
            q_current + correction, min=hard_lower, max=hard_upper
        )
        correction = torch.where(
            current_inside_hard,
            projected_hard_target - q_current,
            correction,
        )
        correction = torch.where(
            (q_current < soft_lower) & (correction < 0.0),
            torch.zeros_like(correction),
            correction,
        )
        correction = torch.where(
            (q_current > soft_upper) & (correction > 0.0),
            torch.zeros_like(correction),
            correction,
        )
        policy_inside_soft = (
            (q_current >= soft_lower) & (q_current <= soft_upper)
        )
        projected_inside_target = torch.clamp(
            q_current + correction, min=soft_lower, max=soft_upper
        )
        correction = torch.where(
            policy_inside_soft,
            projected_inside_target - q_current,
            correction,
        )
        q_correction_next = q_current + correction
        q_applied_next = q_policy_next + correction
        hard_progress_valid = torch.where(
            current_inside_hard,
            (q_correction_next >= hard_lower) & (q_correction_next <= hard_upper),
            torch.where(
                q_current < hard_lower,
                q_correction_next >= q_current,
                q_correction_next <= q_current,
            ),
        )
        soft_progress_valid = torch.where(
            policy_inside_soft,
            (q_correction_next >= soft_lower) & (q_correction_next <= soft_upper),
            torch.where(
                q_current < soft_lower,
                q_correction_next >= q_current,
                q_correction_next <= q_current,
            ),
        )
        limit_valid = torch.all(hard_progress_valid & soft_progress_valid, dim=-1)
        correction_raw = correction / (
            float(self.config.robot.control.action_scale)
            * float(self.config.delta_action_scale)
        )
        applied_arm_raw = policy_action[:, arm_slice] + correction_raw
        d_des = d_prev + (
            applied_arm_raw * float(self.config.delta_action_scale)
        )
        delta_ok = torch.all(
            torch.abs(correction)
            <= (
                cfg["pull_h10m_joint_correction_step_max_rad"]
                + torch.finfo(correction.dtype).eps
            ),
            dim=-1,
        )
        raw_ok = torch.all(
            torch.abs(applied_arm_raw) <= cfg["raw_action_abs_max"], dim=-1
        )
        invalid = active & ~(ik_valid & limit_valid & delta_ok & raw_ok)
        if torch.any(invalid):
            env_ids = torch.where(invalid)[0]
            raise RuntimeError(
                "H10-M live-pose DLS rejected active rows: "
                f"env_ids={env_ids.tolist()}, "
                f"ik_invalid={env_ids[~ik_valid[env_ids]].tolist()}, "
                f"limit_invalid={env_ids[~limit_valid[env_ids]].tolist()}, "
                f"delta_invalid={env_ids[~delta_ok[env_ids]].tolist()}, "
                f"raw_invalid={env_ids[~raw_ok[env_ids]].tolist()}, "
                f"condition={condition[env_ids].tolist()}, "
                f"max_abs_raw={torch.abs(applied_arm_raw[env_ids]).amax(dim=-1).tolist()}, "
                f"q_current={q_current[env_ids].tolist()}, "
                f"q_policy_next={q_policy_next[env_ids].tolist()}, "
                f"correction={correction[env_ids].tolist()}, "
                f"q_applied_next={q_applied_next[env_ids].tolist()}, "
                f"hard_limits={hard_limits[env_ids].tolist()}, "
                f"soft_limits={soft_limits[env_ids].tolist()}."
            )
        action = policy_action.clone()
        action[active, arm_slice] = applied_arm_raw[active]
        self._a2_pull_h10m_dls_correction_raw.zero_()
        self._a2_pull_h10m_dls_correction_raw[active] = (
            applied_arm_raw - policy_action[:, arm_slice]
        )[active]
        self._a2_pull_h10m_action_count[active] += 1
        self._a2_hold_oracle_q_des[:] = q_applied_next
        self._a2_hold_oracle_d_des[:] = d_des
        self._a2_hold_oracle_d_prev[:] = d_prev
        self._a2_hold_oracle_a_raw.zero_()
        self._a2_hold_oracle_a_raw[active] = applied_arm_raw[active]
        self._a2_hold_oracle_target_pos_root[:] = target_pos_root
        self._a2_hold_oracle_target_quat_root[:] = target_quat_root
        self._a2_hold_oracle_bounded_command_pos_root[:] = bounded_command_pos_root
        self._a2_hold_oracle_bounded_command_quat_root[:] = bounded_command_quat_root
        self._a2_hold_oracle_bounded_position_step[:] = bounded_position_step
        self._a2_hold_oracle_bounded_orientation_step[:] = bounded_orientation_step
        self._a2_hold_oracle_position_residual[:] = position_residual
        self._a2_hold_oracle_orientation_residual[:] = orientation_residual
        self._a2_hold_oracle_singular_values[:] = singular_values
        self._a2_hold_oracle_jacobian_condition[:] = condition
        self._a2_hold_oracle_ik_valid[:] = ik_valid
        self._a2_hold_oracle_limit_valid[:] = limit_valid
        self._a2_hold_oracle_delta_ok[:] = delta_ok
        self._a2_hold_oracle_raw_ok[:] = raw_ok
        self._a2_hold_oracle_arm_dls_branch[:] = active
        self._a2_hold_oracle_base_relief_branch_applied.zero_()
        self._a2_hold_oracle_last_override_mask = active.clone()
        self._a2_hold_oracle_post_override_action = action
        return action, active

    @override
    def _get_a2_hold_oracle_trace_fields(self, env_ids: torch.Tensor):
        records = super()._get_a2_hold_oracle_trace_fields(env_ids)
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if cfg is None or not cfg.get("pull_h10m_live_pose_probe_enabled", False):
            return records
        for env_id, record in zip(env_ids.tolist(), records):
            captured_pos = self._a2_pull_h10m_captured_handle_to_tcp_pos[env_id]
            record["pull_lr_h10m_captured_handle_to_tcp_pos"] = (
                captured_pos.detach().cpu().tolist()
                if torch.all(torch.isfinite(captured_pos))
                else None
            )
            record["pull_lr_h10m_dls_correction_raw"] = (
                self._a2_pull_h10m_dls_correction_raw[env_id]
                .detach()
                .cpu()
                .tolist()
            )
            record["pull_lr_h10m_action_count"] = int(
                self._a2_pull_h10m_action_count[env_id].item()
            )
            record["pull_lr_h10m_complete"] = bool(
                self._a2_pull_h10m_complete[env_id].item()
            )
        return records

    @override
    def _get_a2_terminal_diagnostics(self, env_ids):
        records = super()._get_a2_terminal_diagnostics(env_ids)
        pull_records = self.get_a2_pull_control_step_telemetry(env_ids)
        episode_records = self.get_a2_pull_episode_records(env_ids, records)
        if len(records) != len(pull_records):
            raise RuntimeError(
                "Pull terminal diagnostics requires one E0-E7 telemetry record per env."
            )
        selected = (
            torch.arange(self.num_envs, dtype=torch.long, device=self.device)
            if env_ids is None
            else env_ids
        )
        for env_id, record, pull_record, episode_record in zip(
            selected.tolist(), records, pull_records, episode_records
        ):
            if "pull_v0" in record:
                raise RuntimeError("Pull terminal diagnostic field pull_v0 already exists.")
            record["pull_v0"] = pull_record
            record["pull_v0_episode"] = episode_record
            record["pull_v0_stage0_predicates"] = {
                "staging_band": bool(self._a2_pull_stage0_staging_band[env_id].item()),
                "arm_default": bool(self._a2_pull_stage0_arm_default[env_id].item()),
                "base_still": bool(self._a2_pull_stage0_base_still[env_id].item()),
                "event_admission": "report_only",
            }
            record["pull_v0_scripted_activation"] = {
                "first_control_step": (
                    int(self._a2_pull_first_scripted_activation_step[env_id].item())
                    if int(self._a2_pull_first_scripted_activation_step[env_id].item()) >= 0
                    else A2_PULL_NA
                ),
                "admission_stage2_grasp_gate": False,
                "proof_world_direction": "+X",
            }
            cfg = getattr(self, "_a2_hold_oracle_cfg", None)
            if cfg is not None and cfg.get("v6_p1_oracle_enabled", False):
                reached = episode_record["event_reached"]
                record["pull_v6_oracle"] = {
                    "cell": [
                        self.config["a2_pull_v6_release_hinge_rad"],
                        cfg["v6_p1_target_hinge_velocity_radps"],
                        cfg["v6_p1_xy_relief_m"],
                    ],
                    "phase": ("WAIT_E5", "ARC_DLS", "RELEASE", "THROUGH", "DONE")[
                        4 if reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]
                        else int(self._a2_pull_v6_p1_phase[env_id].item())
                    ],
                    "activated": bool(self._a2_hold_oracle_activated[env_id].item()),
                    "arc_reached": bool(self._a2_pull_v6_p1_arc_reached[env_id].item()),
                    "yaw_pivot_complete": bool(
                        self._a2_pull_v6_p1_yaw_pivot_complete[env_id].item()
                    ),
                    "yaw_pivot_target_reached": bool(
                        self._a2_pull_v6_p1_yaw_pivot_target_reached[env_id].item()
                    ),
                    "entry_settled": bool(
                        self._a2_pull_v6_p1_entry_settled[env_id].item()
                    ),
                    "release_commanded": bool(self._a2_pull_v6_p1_release_commanded[env_id].item()),
                    "steps": int(self._a2_pull_v6_p1_steps[env_id].item()),
                    "handle_crossed": bool(self._a2_pull_v6_handle_crossed[env_id].item()),
                    "clean_release": bool(self._a2_pull_v6_clean_release[env_id].item()),
                    "release_persistence": int(self._a2_pull_v6_release_persistence[env_id].item()),
                    "recontact": int(self._a2_pull_v6_p1_handle_recontact_count[env_id].item()),
                    "frame_passage": bool(self._a2_pull_frame_passage[env_id].item()),
                    "E6": bool(reached[A2PullEvent.E6_PATH_REVERSAL_ENTRY.name]),
                    "E7": bool(reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]),
                    "whole_clear": bool(self._get_a2_pull_whole_body_clear_mask(
                        self.simulator.get_task_root_state("door")[env_id : env_id + 1, 0]
                    )[0].item()),
                    "pivot_displacement_m": (
                        float(self._a2_pull_v6_pivot_displacement_m[env_id].item())
                        if torch.isfinite(self._a2_pull_v6_pivot_displacement_m[env_id])
                        else A2_PULL_NA
                    ),
                    "root_yaw_delta_rad": (
                        float(self._a2_pull_v6_root_yaw_delta[env_id].item())
                        if torch.isfinite(self._a2_pull_v6_root_yaw_delta[env_id])
                        else A2_PULL_NA
                    ),
                }
            v61_cfg = getattr(self, "_a2_pull_v61_post_release_intervention_cfg", None)
            if v61_cfg is not None:
                reached = episode_record["event_reached"]
                terminal_reason = episode_record["terminal_reason"]
                stop_reason = self._a2_pull_v61_post_release_intervention_stop_reason[env_id]
                if (
                    stop_reason is None
                    and terminal_reason != "UNKNOWN"
                    and bool(self._a2_pull_v61_post_release_intervention_started[env_id].item())
                ):
                    stop_reason = f"terminal:{terminal_reason}"
                record["pull_v61_post_release_terminal_snapshot"] = {
                    "mode": v61_cfg["mode"],
                    "active": bool(self._a2_pull_v61_post_release_intervention_active[env_id].item()),
                    "started": bool(self._a2_pull_v61_post_release_intervention_started[env_id].item()),
                    "complete": bool(reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]),
                    "e7": bool(reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]),
                    "terminal_reason": terminal_reason,
                    "stop_reason": stop_reason,
                }
            record["pull_v2_unlatch"] = {
                "stable_unlatch_handle_based": bool(
                    self._a2_pull_stable_unlatch_handle_ever[env_id].item()
                ),
                "stable_unlatch_latch_based": bool(
                    self._a2_pull_stable_unlatch_latch_ever[env_id].item()
                ),
                "relock_handle_based": bool(self._a2_pull_relock_handle_ever[env_id].item()),
                "relock_latch_based": bool(self._a2_pull_relock_latch_ever[env_id].item()),
                "handle_unlatch_threshold_rad": 0.3,
                "latch_unlatch_threshold_m": self._get_a2_pull_e3_latch_threshold_m(),
                "relock_definition": (
                    "prior stable threshold crossing, then threshold loss while "
                    "hinge remains below the Stage3-to4 gate"
                ),
            }
            if self._is_a2_pull_traversal():
                reached = episode_record["event_reached"]
                first_steps = episode_record["first_event_step"]
                e5_to_e7_steps = (
                    int(first_steps[A2PullEvent.E7_WHOLE_BODY_CLEAR.name])
                    - int(first_steps[A2PullEvent.E5_CLEARANCE_DECISION.name])
                    if reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]
                    and reached[A2PullEvent.E5_CLEARANCE_DECISION.name]
                    else None
                )
                release_step = int(self._a2_pull_deliberate_release_step[env_id].item())
                first_negative_step = int(
                    self._a2_pull_first_negative_x_motion_step[env_id].item()
                )
                record["pull_v3_traversal"] = {
                    "frame_passage": bool(self._a2_pull_frame_passage[env_id].item()),
                    "frame_passage_step": (
                        int(self._a2_pull_frame_passage_step[env_id].item())
                        if int(self._a2_pull_frame_passage_step[env_id].item()) >= 0
                        else None
                    ),
                    "planar_crossing": bool(self._a2_pull_planar_crossing[env_id].item()),
                    "detour": bool(self._a2_pull_detour[env_id].item()),
                    "deliberate_release": bool(
                        self._a2_pull_deliberate_release[env_id].item()
                    ),
                    "deliberate_release_step": (
                        int(self._a2_pull_deliberate_release_step[env_id].item())
                        if int(self._a2_pull_deliberate_release_step[env_id].item()) >= 0
                        else None
                    ),
                    "first_negative_x_motion_step": (
                        first_negative_step
                        if first_negative_step >= 0
                        else None
                    ),
                    "release_to_first_negative_x_motion_steps": (
                        first_negative_step - release_step
                        if release_step >= 0 and first_negative_step >= release_step
                        else None
                    ),
                    "frame_approach": bool(self._a2_pull_frame_approach[env_id].item()),
                    "frame_approach_active": bool(
                        self._a2_pull_frame_approach_active[env_id].item()
                    ),
                    "frame_approach_reward_executed": (
                        "a2_pull_frame_approach" in self.reward_scales
                    ),
                    "frame_approach_raw_last": float(
                        self._a2_pull_last_raw_reward_components.get(
                            "a2_pull_frame_approach",
                            torch.zeros(self.num_envs, device=self.device),
                        )[env_id].item()
                    ),
                    "frame_midpoint_distance_min_m": float(
                        self._a2_pull_frame_midpoint_distance_min_m[env_id].item()
                    ),
                    "panel_clear": bool(not self._a2_pull_prev_panel_contact[env_id].item()),
                    "e5_to_e7_steps": e5_to_e7_steps,
                    "swept_arc_clearance_margin_min_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_min_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_min_m[env_id]
                        )
                        else None
                    ),
                    "swept_arc_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "signed_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "base_path_length_m": float(
                        self._a2_pull_base_path_length_m[env_id].item()
                    ),
                    "base_reversal_count": int(
                        self._a2_pull_base_reversal_count[env_id].item()
                    ),
                    "post_release_recontact_count": int(
                        self._a2_pull_post_release_recontact_count[env_id].item()
                    ),
                    "corridor_door_wide_pre_aperture_steps": int(
                        self._a2_pull_corridor_door_wide_pre_aperture_steps[env_id].item()
                    ),
                    "corridor_door_wide_reward_executed": (
                        "a2_corridor_door_wide" in self.reward_scales
                    ),
                    "corridor_door_wide_raw_last": float(
                        self._a2_pull_last_raw_reward_components.get(
                            "a2_corridor_door_wide",
                            torch.zeros(self.num_envs, device=self.device),
                        )[env_id].item()
                    ),
                    "corridor_clean_passage_pre_aperture_steps": int(
                        self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_id].item()
                    ),
                    "frame_approach_active_before_aperture_steps": int(
                        self._a2_pull_frame_approach_pre_aperture_steps[env_id].item()
                    ),
                    "frame_approach_active_after_frame_passage_steps": int(
                        self._a2_pull_frame_approach_post_frame_passage_steps[env_id].item()
                    ),
                    "complete_without_frame_passage": bool(
                        reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]
                        and not self._a2_pull_frame_passage[env_id].item()
                    ),
                }
                if self._is_a2_pull_v5():
                    record["pull_v5"] = {
                        "reset_source": self._a2_pull_v5_reset_source[env_id],
                        "declared_reset_source": self._a2_pull_v5_declared_reset_source[env_id],
                        "settle_valid": True,
                        "bank_settle_valid": self._get_a2_pull_v5_bank_settle_valid(env_id),
                        "hinge_drive_max_force_nm": float(
                            self.door_hinge_drive_max_force[env_id].item()
                        ),
                        "invariants": self._get_a2_pull_v5_terminal_invariants(
                            env_id, episode_record["event_reached"]
                        ),
                        "persistent_release": bool(
                            self._a2_pull_v5_persistent_release[env_id].item()
                        ),
                        "persistent_release_streak_steps": int(
                            self._a2_pull_v5_persistent_release_streak[env_id].item()
                        ),
                        "release_streak_required_steps": A2_PULL_V5_RELEASE_STREAK_STEPS,
                        "start_override_active": bool(
                            self._a2_pull_v5_start_override_active_steps[env_id].item() > 0
                        ),
                        "start_override_active_steps": int(
                            self._a2_pull_v5_start_override_active_steps[env_id].item()
                        ),
                        "start_override_base_slice_equal": bool(
                            self._a2_pull_v5_start_override_base_slice_equal[env_id].item()
                        ),
                        "passage_attempt_hinge_rad": (
                            float(self._a2_pull_passage_attempt_hinge_rad[env_id].item())
                            if torch.isfinite(self._a2_pull_passage_attempt_hinge_rad[env_id])
                            else None
                        ),
                        "intervention_active": bool(
                            self._a2_pull_v5_intervention_active[env_id].item()
                        ),
                        "intervention_fired": bool(
                            self._a2_pull_v5_intervention_fired[env_id].item()
                        ),
                        "intervention_elapsed_steps": int(
                            self._a2_pull_v5_intervention_elapsed_steps[env_id].item()
                        ),
                        "deliberate_release_semantics": "report_only_one_step_contact_transition",
                    }
                    if self.config.get("a2_pull_v5_probe_enabled", False):
                        probe_root_xy = self.simulator.robot_root_states[env_id, :2]
                        probe_root_quat_w = xyzw_to_wxyz(
                            self.simulator.robot_root_states[env_id, 3:7].unsqueeze(0)
                        )
                        _, _, probe_root_yaw = euler_xyz_from_quat(probe_root_quat_w)
                        if (
                            not torch.isfinite(self._a2_pull_v5_probe_waypoint_target_xy[env_id]).all()
                            or not torch.isfinite(self._a2_pull_v5_probe_yaw_target[env_id])
                            or not torch.isfinite(self._a2_pull_v5_probe_original_yaw_target[env_id])
                            or not torch.isfinite(probe_root_xy).all()
                            or not torch.isfinite(probe_root_yaw).all()
                        ):
                            raise RuntimeError("Pull-v5 probe terminal telemetry requires a measured target and root pose.")
                        terminal_scheduler_error = float(
                            wrap_to_pi(
                                self._a2_pull_v5_probe_yaw_target[env_id] - probe_root_yaw.squeeze(0)
                            ).item()
                        )
                        terminal_original_error = float(
                            wrap_to_pi(
                                self._a2_pull_v5_probe_original_yaw_target[env_id]
                                - probe_root_yaw.squeeze(0)
                            ).item()
                        )
                        record["pull_v5_probe"] = {
                            "fixture": self.config["a2_pull_v5_probe_fixture"],
                            "command": self.config["a2_pull_v5_probe_command"],
                            "command_primitive": self.config["a2_pull_v5_probe_command"],
                            "sequence": self._a2_pull_v5_probe_sequence_id
                            or self.config["a2_pull_v5_probe_command"],
                            "sequence_phases": list(self._a2_pull_v5_probe_sequence_phases),
                            "sequence_phase_index": int(
                                self._a2_pull_v5_probe_phase_index[env_id].item()
                            ),
                            "sequence_complete": bool(
                                self._a2_pull_v5_probe_sequence_complete[env_id].item()
                            ),
                            "command_solvable": bool(self._a2_pull_v5_probe_solvable[env_id].item()),
                            "waypoint_arrived": bool(self._a2_pull_v5_probe_waypoint_arrived[env_id].item()),
                            "yaw_arrived": bool(self._a2_pull_v5_probe_yaw_arrived[env_id].item()),
                            "waypoint_position_error_m": float(
                                self._a2_pull_v5_probe_waypoint_error_m[env_id].item()
                            ),
                            "yaw_error_rad": float(self._a2_pull_v5_probe_yaw_error_rad[env_id].item()),
                            "anchor_pass": bool(
                                self.config["a2_pull_v5_probe_fixture"] in {"anchor", "rehearsal"}
                                and self._a2_pull_v5_probe_anchor_pass[env_id].item()
                            ),
                            "requested_waypoint_xy": self._a2_pull_v5_probe_waypoint_target_xy[
                                env_id
                            ].detach().cpu().tolist(),
                            "realized_waypoint_xy": probe_root_xy.detach().cpu().tolist(),
                            "requested_base_motion_xy": self._a2_pull_v5_probe_waypoint_target_xy[
                                env_id
                            ].detach().cpu().tolist(),
                            "realized_base_motion_xy": probe_root_xy.detach().cpu().tolist(),
                            "requested_yaw_rad": float(self._a2_pull_v5_probe_yaw_target[env_id].item()),
                            "original_target_yaw_rad": float(self._a2_pull_v5_probe_original_yaw_target[env_id].item()),
                            "realized_yaw_rad": float(probe_root_yaw.item()),
                            "lattice_scale": float(self.config.get("a2_pull_v5_lattice_scale", 1.0)),
                        }
                        if self._a2_pull_v5_scheduler_enabled:
                            state_names = {
                                value: key for key, value in self._A2_PULL_V5_4_SCHEDULER_STATES.items()
                            }
                            record["pull_v5_probe"]["scheduler"] = {
                                "schema": self._A2_PULL_V5_4_SCHEDULER_SCHEMA,
                                "state": state_names[int(self._a2_pull_v5_scheduler_state[env_id].item())],
                                "failure_reason": self._a2_pull_v5_scheduler_failure_reason[env_id],
                                "settle_steps": int(self._a2_pull_v5_scheduler_settle_steps[env_id].item()),
                                "trim_steps": int(self._a2_pull_v5_scheduler_trim_steps[env_id].item()),
                                "terminal_hold_steps": int(self._a2_pull_v5_scheduler_terminal_hold_steps[env_id].item()),
                                "error_rad": terminal_scheduler_error,
                                "planning_error_rad": terminal_scheduler_error,
                                "terminal_error_original_target_rad": terminal_original_error,
                                "episode_index": int(self._a2_pull_v5_scheduler_episode_indices[env_id].item()),
                                "episode_id": (
                                    f"{self.config['a2_pull_v5_probe_fixture']}:env{env_id}:episode"
                                    f"{int(self._a2_pull_v5_scheduler_episode_indices[env_id].item())}"
                                ),
                                "terminal_current_state": (
                                    state_names[int(self._a2_pull_v5_scheduler_state[env_id].item())]
                                    == "DONE"
                                ),
                                "scientific_denominator_included": False,
                                "denominator_scope": "none",
                            }
                            record["episode_index"] = int(
                                self._a2_pull_v5_scheduler_episode_indices[env_id].item()
                            )
                            record["episode_id"] = (
                                f"{self.config['a2_pull_v5_probe_fixture']}:env{env_id}:episode"
                                f"{int(self._a2_pull_v5_scheduler_episode_indices[env_id].item())}"
                            )
        return records

    def get_a2_pull_episode_records(self, env_ids, terminal_records=None) -> list[dict]:
        """Build complete E0-E7 episode summaries for terminal funnel consumers."""

        selected = (
            torch.arange(self.num_envs, dtype=torch.long, device=self.device)
            if env_ids is None
            else env_ids
        )
        if (
            not torch.is_tensor(selected)
            or selected.ndim != 1
            or selected.dtype != torch.long
            or selected.device != torch.device(self.device)
            or torch.any(selected < 0)
            or torch.any(selected >= self.num_envs)
        ):
            raise RuntimeError("Pull episode diagnostics requires valid device-local env ids.")
        if terminal_records is not None and len(terminal_records) != len(selected):
            raise RuntimeError("Pull terminal records and episode ids must have equal length.")
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"Pull episode diagnostics requires positive finite dt; got {dt!r}.")
        threshold_mode = self._get_a2_pull_threshold_mode()
        records: list[dict] = []
        for record_index, env_id in enumerate(selected.tolist()):
            reached = {
                event.name: bool(self._a2_pull_event_reached[env_id, event].item())
                for event in A2PullEvent
            }
            first_steps = {
                event.name: (
                    int(self._a2_pull_first_event_step[env_id, event].item())
                    if reached[event.name]
                    else A2_PULL_NA
                )
                for event in A2PullEvent
            }
            first_times = {
                event.name: (
                    float(self._a2_pull_first_event_time_s[env_id, event].item())
                    if reached[event.name]
                    else A2_PULL_NA
                )
                for event in A2PullEvent
            }
            terminal_reason = (
                terminal_records[record_index].get("terminal_reason", "UNKNOWN")
                if terminal_records is not None
                else "UNKNOWN"
            )
            if not isinstance(terminal_reason, str) or not terminal_reason:
                raise RuntimeError("Pull terminal reason must be a non-empty string.")
            e2 = reached[A2PullEvent.E2_TENSILE_CAPTURE.name]
            e4 = reached[A2PullEvent.E4_POSITIVE_HINGE_RETAINED.name]
            e5 = reached[A2PullEvent.E5_CLEARANCE_DECISION.name]
            e6 = reached[A2PullEvent.E6_PATH_REVERSAL_ENTRY.name]
            record = {
                "event_reached": reached,
                "first_event_step": first_steps,
                "first_event_time_s": first_times,
                "proof_hold_duration_s": float(self._a2_pull_proof_duration_s[env_id].item())
                if e2
                else A2_PULL_NA,
                "proof_retreat_displacement_m": float(
                    self._a2_pull_proof_displacement_m[env_id].item()
                )
                if e2
                else A2_PULL_NA,
                "max_tensile_retreat_before_loss_m": float(
                    self._a2_pull_max_tensile_retreat_m[env_id].item()
                )
                if e2
                else A2_PULL_NA,
                "hinge_at_first_positive_progress_rad": float(
                    self._a2_pull_hinge_at_first_positive_progress_rad[env_id].item()
                )
                if torch.isfinite(
                    self._a2_pull_hinge_at_first_positive_progress_rad[env_id]
                )
                else A2_PULL_NA,
                "hinge_at_first_grip_loss_rad": A2_PULL_NA,
                "held_hinge_max_rad": float(self._a2_pull_held_hinge_max_rad[env_id].item())
                if torch.isfinite(self._a2_pull_held_hinge_max_rad[env_id])
                else A2_PULL_NA,
                "hinge_at_release_or_hold_decision_rad": float(
                    self._a2_pull_hinge_at_decision_rad[env_id].item()
                )
                if e4 and torch.isfinite(self._a2_pull_hinge_at_decision_rad[env_id])
                else A2_PULL_NA,
                "root_outward_excursion_before_clear_m": float(
                    self._a2_pull_root_outward_excursion_m[env_id].item()
                )
                if e5
                else A2_PULL_NA,
                "first_path_reversal_step": int(
                    self._a2_pull_first_path_reversal_step[env_id].item()
                )
                if e6 and int(self._a2_pull_first_path_reversal_step[env_id].item()) >= 0
                else A2_PULL_NA,
                "release_to_whole_body_clear_s": (
                    float(
                        self._a2_pull_first_event_time_s[
                            env_id, A2PullEvent.E7_WHOLE_BODY_CLEAR
                        ].item()
                        - self._a2_pull_v61_clean_release_step[env_id].item() * dt
                    )
                    if self._is_a2_pull_v6()
                    and reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]
                    and int(self._a2_pull_v61_clean_release_step[env_id].item()) >= 0
                    else A2_PULL_NA
                ),
                "e5_to_whole_body_clear_s": (
                    float(
                        self._a2_pull_first_event_time_s[
                            env_id, A2PullEvent.E7_WHOLE_BODY_CLEAR
                        ].item()
                        - self._a2_pull_first_event_time_s[
                            env_id, A2PullEvent.E5_CLEARANCE_DECISION
                        ].item()
                    )
                    if reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name] and e5
                    else A2_PULL_NA
                ),
                "hinge_reclosure_after_release_rad": (
                    float(self._a2_pull_v61_hinge_reclosure_after_release_rad[env_id].item())
                    if self._is_a2_pull_v6()
                    and int(self._a2_pull_v61_clean_release_step[env_id].item()) >= 0
                    else A2_PULL_NA
                ),
                "body_panel_contact_steps_per_20s": int(
                    self._a2_pull_body_panel_contact_steps[env_id].item()
                ),
                "body_panel_contact_impulse_Ns": float(
                    self._a2_pull_body_panel_contact_impulse_ns[env_id].item()
                ),
                "crossing_while_valid_capture": bool(
                    e5
                    and self._a2_pull_capture_valid[env_id].item()
                    and self._a2_pull_event_reached[
                        env_id, A2PullEvent.E6_PATH_REVERSAL_ENTRY
                    ].item()
                ),
                "whole_body_clear": reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name],
                "terminal_reason": terminal_reason,
                "spawn_hook": bool(self.door_spawn_hook[env_id].item()),
                "hinge_drive_max_force_nm": float(self.door_hinge_drive_max_force[env_id].item()),
            }
            validate_a2_pull_episode(
                record,
                event_predecessors=(
                    A2_PULL_HARD_GATE_EVENT_PREDECESSORS
                    if threshold_mode == "hard_gate"
                    else None
                ),
            )
            if self._is_a2_pull_v5():
                record["pull_v5"] = {
                    "reset_source": self._a2_pull_v5_reset_source[env_id],
                    "declared_reset_source": self._a2_pull_v5_declared_reset_source[env_id],
                    "settle_valid": True,
                    "bank_settle_valid": self._get_a2_pull_v5_bank_settle_valid(env_id),
                    "hinge_drive_max_force_nm": float(
                        self.door_hinge_drive_max_force[env_id].item()
                    ),
                    "invariants": self._get_a2_pull_v5_terminal_invariants(env_id, reached),
                    "persistent_release": bool(
                        self._a2_pull_v5_persistent_release[env_id].item()
                    ),
                    "persistent_release_streak_steps": int(
                        self._a2_pull_v5_persistent_release_streak[env_id].item()
                    ),
                    "release_streak_required_steps": A2_PULL_V5_RELEASE_STREAK_STEPS,
                    "start_override_active": bool(
                        self._a2_pull_v5_start_override_active_steps[env_id].item() > 0
                    ),
                    "start_override_active_steps": int(
                        self._a2_pull_v5_start_override_active_steps[env_id].item()
                    ),
                    "start_override_base_slice_equal": bool(
                        self._a2_pull_v5_start_override_base_slice_equal[env_id].item()
                    ),
                    "passage_attempt_hinge_rad": (
                        float(self._a2_pull_passage_attempt_hinge_rad[env_id].item())
                        if torch.isfinite(self._a2_pull_passage_attempt_hinge_rad[env_id])
                        else None
                    ),
                    "deliberate_release_semantics": "report_only_one_step_contact_transition",
                }
            records.append(record)
        return records

    def _get_a2_pull_pd_effort_telemetry(self) -> dict[str, torch.Tensor]:
        robot = self.simulator.scene.articulations["robot"]
        data = robot.data
        ordered_joint_ids = torch.tensor(
            self.simulator.dof_ids,
            dtype=torch.long,
            device=self.device,
        )
        field_values = {
            "joint_pos": data.joint_pos,
            "joint_vel": data.joint_vel,
            "joint_pos_target": data.joint_pos_target,
            "joint_stiffness": data.joint_stiffness,
            "joint_damping": data.joint_damping,
            "joint_effort_limits": data.joint_effort_limits,
        }
        articulation_joint_count = data.joint_pos.shape[1]
        for field_name, value in field_values.items():
            if (
                not torch.is_tensor(value)
                or value.shape != (self.num_envs, articulation_joint_count)
                or not torch.all(torch.isfinite(value))
            ):
                shape = None if not torch.is_tensor(value) else tuple(value.shape)
                raise RuntimeError(
                    f"Pull PD telemetry requires finite Articulation.data.{field_name} "
                    f"shape ({self.num_envs}, {articulation_joint_count}); got {shape}."
                )
        ordered = {
            name: value[:, ordered_joint_ids]
            for name, value in field_values.items()
        }

        def estimate(indices: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            unclipped, clipped, _saturated = a2_hold_pd_effort_estimates(
                ordered["joint_pos"][:, indices],
                ordered["joint_vel"][:, indices],
                ordered["joint_pos_target"][:, indices],
                ordered["joint_stiffness"][:, indices],
                ordered["joint_damping"][:, indices],
                ordered["joint_effort_limits"][:, indices],
            )
            utilization = torch.abs(clipped) / ordered["joint_effort_limits"][:, indices]
            if not torch.all(torch.isfinite(unclipped)) or not torch.all(torch.isfinite(utilization)):
                raise RuntimeError("Pull PD effort telemetry produced non-finite estimates.")
            return clipped, utilization

        finger_effort, finger_utilization = estimate(self._a2_gripper_dof_indices)
        _arm_effort, arm_utilization = estimate(self._a2_arm_dof_indices)
        return {
            "finger_effort": finger_effort,
            "finger_utilization": finger_utilization,
            "arm_utilization": arm_utilization,
        }

    def get_a2_pull_control_step_telemetry(self, env_ids=None) -> list[dict]:
        """Return schema-validated records after the current reward step."""

        selected = (
            torch.arange(self.num_envs, dtype=torch.long, device=self.device)
            if env_ids is None
            else env_ids
        )
        if (
            not torch.is_tensor(selected)
            or selected.ndim != 1
            or selected.dtype != torch.long
            or selected.device != torch.device(self.device)
            or torch.any(selected < 0)
            or torch.any(selected >= self.num_envs)
        ):
            raise RuntimeError("Pull control-step telemetry requires valid env ids.")
        if not self._a2_pull_last_raw_reward_components:
            raise RuntimeError("Pull control-step telemetry must be collected after reward computation.")

        root_states = self.simulator.robot_root_states
        door_states = self.simulator.get_task_root_state("door")
        root_x = root_states[:, 0]
        door_x = door_states[:, 0]
        root_x_rel = root_x - door_x
        root_velocity_x = root_states[:, 7]
        frame_midpoint_xy = self._get_a2_pull_door_frame_midpoint(door_states)
        frame_delta_xy = frame_midpoint_xy - root_states[:, 0:2]
        frame_midpoint_distance = torch.linalg.vector_norm(frame_delta_xy, dim=-1)
        _, _, root_yaw = euler_xyz_from_quat(root_states[:, 3:7])
        _, _, door_yaw = euler_xyz_from_quat(door_states[:, 3:7])
        expected_approach_yaw = (1.0 + self._pull_direction.io_sign) * 0.5 * math.pi
        root_yaw_error = torch.abs(wrap_to_pi(root_yaw - door_yaw - expected_approach_yaw))
        door_joint_pos = self._get_door_joint_pos("pull control-step telemetry", 3)
        door_joint_vel = self._get_door_joint_vel("pull control-step telemetry", 3)
        frame_data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = frame_data.target_pos_source[:, 0, :]
        target_quat_source = frame_data.target_quat_source[:, 0, :]
        target_position_error = torch.linalg.norm(target_pos_source, dim=-1)
        target_orientation_error = torch.linalg.norm(
            axis_angle_from_quat(target_quat_source), dim=-1
        )
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "pull control-step telemetry"
        )
        stable_contact_current = contact_masks["both_contact"] & (
            self._get_a2_stage2_contact_stability_mask()
            | self._get_a2_hold_streak_ok_mask()
        )
        aperture_ready_current = stable_contact_current & (
            door_joint_pos[:, 0] >= self._get_a2_v20_send_hinge_threshold()
        )
        body_panel_forces, body_panel_total = self._get_a2_door_body_panel_contact_forces()
        arm_panel_forces, arm_panel_total = self._get_a2_door_arm_panel_contact_forces()
        body_frame_forces, _ = self._get_a2_door_panel_contact_force_components(
            self.A2_PULL_DOOR_BODY_FRAME_CONTACT_SENSOR,
            self.A2_DOOR_BODY_PANEL_FILTER_NAMES,
            "pull door-body frame contact",
        )
        arm_frame_forces, _ = self._get_a2_door_panel_contact_force_components(
            self.A2_PULL_DOOR_ARM_FRAME_CONTACT_SENSOR,
            self.A2_DOOR_ARM_PANEL_FILTER_NAMES,
            "pull door-arm frame contact",
        )
        effort = self._get_a2_pull_pd_effort_telemetry()
        event_states = a2_pull_event_state_names(
            self._a2_pull_event_reached,
            event_predecessors=(
                A2_PULL_HARD_GATE_EVENT_PREDECESSORS
                if self._get_a2_pull_threshold_mode() == "hard_gate"
                else None
            ),
        )
        panel_names = (
            *self.A2_DOOR_BODY_PANEL_FILTER_NAMES,
            *self.A2_DOOR_ARM_PANEL_FILTER_NAMES,
        )
        corridor_wide_raw_component = self._a2_pull_last_raw_reward_components.get(
            "a2_corridor_door_wide",
            torch.zeros(self.num_envs, device=self.device),
        )
        frame_approach_raw_component = self._a2_pull_last_raw_reward_components.get(
            "a2_pull_frame_approach",
            torch.zeros(self.num_envs, device=self.device),
        )
        records = []
        for env_id in selected.tolist():
            panel_values = torch.cat(
                (body_panel_forces[env_id], arm_panel_forces[env_id])
            ).detach().cpu().tolist()
            frame_values = torch.cat(
                (body_frame_forces[env_id], arm_frame_forces[env_id])
            ).detach().cpu().tolist()
            slip = (
                self._a2_pull_handle_local_slip_xyz_mps[env_id].detach().cpu().tolist()
                if bool(self._a2_pull_handle_local_slip_valid[env_id].item())
                else A2_PULL_NA
            )
            record = {
                "door_open_io_sign": self._pull_direction.io_sign,
                "door_open_lr_sign": int(self.door_open_lr[env_id].item()),
                "active_handle_face_x_sign": self._pull_direction.active_handle_face_x,
                "travel_dir_x": self._pull_direction.travel_dir_x,
                "stage": int(self.stage_buf[env_id].item()),
                "event_state": event_states[env_id],
                "root_x_rel_door_m": float(root_x_rel[env_id].item()),
                "signed_crossing_progress_m": float(
                    self._pull_direction.signed_crossing_progress(
                        root_x[env_id], door_x[env_id]
                    ).item()
                ),
                "root_velocity_toward_door_mps": float(
                    self._pull_direction.signed_velocity_toward_door(
                        root_velocity_x[env_id]
                    ).item()
                ),
                "root_velocity_yield_outward_mps": float(
                    self._pull_direction.signed_velocity_yield_outward(
                        root_velocity_x[env_id]
                    ).item()
                ),
                "root_velocity_final_travel_mps": float(
                    (self._pull_direction.travel_dir_x * root_velocity_x[env_id]).item()
                ),
                "root_yaw_error_rad": float(root_yaw_error[env_id].item()),
                "handle_position_rad": float(door_joint_pos[env_id, 1].item()),
                "handle_velocity_radps": float(door_joint_vel[env_id, 1].item()),
                "latch_position_m": float(door_joint_pos[env_id, 2].item()),
                "hinge_position_rad": float(door_joint_pos[env_id, 0].item()),
                "hinge_velocity_radps": float(door_joint_vel[env_id, 0].item()),
                "target_tcp_position_error_m": float(target_position_error[env_id].item()),
                "target_tcp_orientation_error_rad": float(
                    target_orientation_error[env_id].item()
                ),
                "bilateral_handle_contact": bool(
                    contact_masks["both_contact"][env_id].item()
                ),
                "tensile_proof_active": bool(
                    self._a2_pull_proof_active[env_id].item()
                ),
                "tensile_proof_duration_s": float(
                    self._a2_pull_proof_duration_s[env_id].item()
                ),
                "tensile_proof_displacement_m": float(
                    self._a2_pull_proof_displacement_m[env_id].item()
                ),
                "tensile_proof_streak_steps": int(
                    self._a2_pull_proof_streak[env_id].item()
                ),
                "tensile_proof_valid": bool(
                    self._a2_pull_proof_valid[env_id].item()
                ),
                "hook_contact": A2_PULL_NA,
                "handle_local_slip_xyz_mps": slip,
                "gripper_handle_separation_m": float(target_position_error[env_id].item()),
                "finger_pd_effort_estimate_N": {
                    "value": effort["finger_effort"][env_id].detach().cpu().tolist(),
                    "provenance": A2_PULL_ESTIMATE_ONLY,
                },
                "finger_effort_utilization_estimate": {
                    "value": effort["finger_utilization"][env_id].detach().cpu().tolist(),
                    "provenance": A2_PULL_ESTIMATE_ONLY,
                },
                "arm_pd_effort_utilization_estimate": {
                    "value": effort["arm_utilization"][env_id].detach().cpu().tolist(),
                    "provenance": A2_PULL_ESTIMATE_ONLY,
                },
                "panel_contact_force_by_body_N": dict(zip(panel_names, panel_values)),
                "frame_contact_force_by_body_N": dict(zip(panel_names, frame_values)),
                "minimum_panel_robot_clearance_m": (
                    float(self._a2_pull_minimum_panel_robot_clearance_m[env_id].item())
                    if bool(
                        torch.isfinite(
                            self._a2_pull_minimum_panel_robot_clearance_m[env_id]
                        ).item()
                    )
                    else A2_PULL_NA
                ),
                "reward_component_raw": {
                    name: float(value[env_id].item())
                    for name, value in self._a2_pull_last_raw_reward_components.items()
                },
            }
            validate_a2_pull_control_step(record)
            if self._a2_pull_stage3_taskspace_action_enabled:
                condition = self._a2_pull_stage3_taskspace_condition[env_id]
                record["pull_lr_stage3_taskspace_action"] = {
                    "active": bool(
                        self._a2_pull_stage3_taskspace_active[env_id].item()
                    ),
                    "policy_raw_twist": self._a2_pull_stage3_taskspace_raw[
                        env_id
                    ].detach().cpu().tolist(),
                    "scaled_handle_frame_twist": self._a2_pull_stage3_taskspace_scaled[
                        env_id
                    ].detach().cpu().tolist(),
                    "converted_joint_raw": self._a2_pull_stage3_taskspace_joint_raw[
                        env_id
                    ].detach().cpu().tolist(),
                    "predicted_root_frame_twist": (
                        self._a2_pull_stage3_taskspace_predicted_twist[env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "commanded_root_frame_twist": (
                        self._a2_pull_stage3_taskspace_commanded_root_twist[env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "relative_realization_residual": float(
                        self._a2_pull_stage3_taskspace_relative_residual[env_id].item()
                    ),
                    "jacobian_condition": (
                        float(condition.item())
                        if torch.isfinite(condition)
                        else None
                    ),
                    "action_count": int(
                        self._a2_pull_stage3_taskspace_action_count[env_id].item()
                    ),
                }
            if self._is_a2_pull_v6():
                record["pull_v6"] = {
                    "stage4_subphase": int(self._a2_pull_v6_subphase[env_id].item()),
                    "pivot_valid": bool(self._a2_pull_v6_pivot_valid[env_id].item()),
                    "pivot_displacement_m": float(self._a2_pull_v6_pivot_displacement_m[env_id].item()) if torch.isfinite(self._a2_pull_v6_pivot_displacement_m[env_id]) else A2_PULL_NA,
                    "handle_send_y_current_m": float(self._a2_pull_v6_handle_y_current[env_id].item()) if torch.isfinite(self._a2_pull_v6_handle_y_current[env_id]) else A2_PULL_NA,
                    "handle_send_y_capture_m": float(self._a2_pull_v6_handle_y_capture[env_id].item()) if torch.isfinite(self._a2_pull_v6_handle_y_capture[env_id]) else A2_PULL_NA,
                    "handle_crossed": bool(self._a2_pull_v6_handle_crossed[env_id].item()),
                    "release_side_qualified": bool(self._a2_pull_v6_release_side_qualified[env_id].item()),
                    "handoff_active": bool(self._a2_pull_v6_handoff_active[env_id].item()),
                    "handoff_reached": bool(self._a2_pull_v6_handoff_reached[env_id].item()),
                    "handoff_active_steps": int(self._a2_pull_v6_handoff_active_steps[env_id].item()),
                    "positive_arm_tangent_mps": float(self._a2_pull_v6_positive_arm_tangent[env_id].item()),
                    "positive_base_tangent_mps": float(self._a2_pull_v6_positive_base_tangent[env_id].item()),
                    "positive_total_tangent_mps": float(self._a2_pull_v6_positive_total_tangent[env_id].item()),
                    "arm_tangent_share": float(self._a2_pull_v6_arm_tangent_share[env_id].item()),
                    "arc_error_m": float(self._a2_pull_v6_arc_error_m[env_id].item()) if torch.isfinite(self._a2_pull_v6_arc_error_m[env_id]) else A2_PULL_NA,
                    "arc_quality": float(self._a2_pull_v6_arc_quality[env_id].item()),
                    "panel_clearance_m": float(self._a2_pull_minimum_panel_robot_clearance_m[env_id].item()) if torch.isfinite(self._a2_pull_minimum_panel_robot_clearance_m[env_id]) else A2_PULL_NA,
                    "workspace_margin": float(self._a2_pull_v6_workspace_margin[env_id].item()) if torch.isfinite(self._a2_pull_v6_workspace_margin[env_id]) else A2_PULL_NA,
                    "frame_lateral_delta_y_m": float(self._a2_pull_v6_frame_lateral_delta_y_m[env_id].item()) if torch.isfinite(self._a2_pull_v6_frame_lateral_delta_y_m[env_id]) else A2_PULL_NA,
                    "frame_lateral_deficit_m": float(self._a2_pull_v6_frame_lateral_deficit_m[env_id].item()) if torch.isfinite(self._a2_pull_v6_frame_lateral_deficit_m[env_id]) else A2_PULL_NA,
                    "passage_ready": bool(self._a2_pull_v6_frame_passage_ready[env_id].item()),
                    "release_ready": bool(self._a2_pull_v6_release_ready[env_id].item()),
                    "release_event": bool(self._a2_pull_v6_release_event[env_id].item()),
                    "clean_release": bool(self._a2_pull_v6_clean_release[env_id].item()),
                    "release_quality": float(self._a2_pull_v6_release_quality[env_id].item()),
                    "release_persistence_steps": int(self._a2_pull_v6_release_persistence[env_id].item()),
                    "hinge_at_release_rad": float(self._a2_pull_v6_hinge_at_release[env_id].item()) if torch.isfinite(self._a2_pull_v6_hinge_at_release[env_id]) else A2_PULL_NA,
                    "hinge_velocity_at_release_radps": float(self._a2_pull_v6_hinge_velocity_at_release[env_id].item()) if torch.isfinite(self._a2_pull_v6_hinge_velocity_at_release[env_id]) else A2_PULL_NA,
                    "root_yaw_delta_rad": float(self._a2_pull_v6_root_yaw_delta[env_id].item()) if torch.isfinite(self._a2_pull_v6_root_yaw_delta[env_id]) else A2_PULL_NA,
                }
                validate_a2_pull_v6_control_extension(record["pull_v6"])
            if getattr(self, "_a2_pull_v61_late_state_bank_enabled", False):
                record["pull_v61_late_state_bank_reset"] = dict(
                    self._a2_pull_v61_last_reset_source[env_id]
                )
            v61_cfg = getattr(self, "_a2_pull_v61_post_release_intervention_cfg", None)
            if v61_cfg is not None:
                record["a2_pull_v61_post_release_intervention_active"] = bool(
                    self._a2_pull_v61_post_release_intervention_active[env_id].item()
                )
                record["pull_v61_post_release_intervention"] = {
                    "mode": v61_cfg["mode"],
                    "target_env_id": int(v61_cfg["target_env_id"]),
                    "active": bool(self._a2_pull_v61_post_release_intervention_active[env_id].item()),
                    "started": bool(self._a2_pull_v61_post_release_intervention_started[env_id].item()),
                    "start_step": (
                        int(self._a2_pull_v61_post_release_intervention_start_step[env_id].item())
                        if int(self._a2_pull_v61_post_release_intervention_start_step[env_id].item()) >= 0
                        else None
                    ),
                    "stop_reason": self._a2_pull_v61_post_release_intervention_stop_reason[env_id],
                    "policy_action": self._a2_pull_v61_post_release_policy_action[env_id].detach().cpu().tolist(),
                    "applied_action": self._a2_pull_v61_post_release_applied_action[env_id].detach().cpu().tolist(),
                    "base_policy_action": self._a2_pull_v61_post_release_policy_action[env_id, :3].detach().cpu().tolist(),
                    "base_applied_action": self._a2_pull_v61_post_release_applied_action[env_id, :3].detach().cpu().tolist(),
                    "arm_policy_action": self._a2_pull_v61_post_release_policy_action[env_id, 5:11].detach().cpu().tolist(),
                    "arm_applied_action": self._a2_pull_v61_post_release_applied_action[env_id, 5:11].detach().cpu().tolist(),
                    "waypoint_error_xy_m": (
                        self._a2_pull_v61_post_release_waypoint_error_xy[env_id].detach().cpu().tolist()
                        if torch.all(torch.isfinite(self._a2_pull_v61_post_release_waypoint_error_xy[env_id]))
                        else None
                    ),
                    "desired_world_xy_mps": (
                        self._a2_pull_v61_post_release_desired_world_xy[env_id].detach().cpu().tolist()
                        if torch.all(torch.isfinite(self._a2_pull_v61_post_release_desired_world_xy[env_id]))
                        else None
                    ),
                    "arm_target_delta_rad": (
                        self._a2_pull_v61_post_release_arm_target[env_id].detach().cpu().tolist()
                        if torch.all(torch.isfinite(self._a2_pull_v61_post_release_arm_target[env_id]))
                        else None
                    ),
                    "arm_target_change_rad": self._a2_pull_v61_post_release_arm_target_change[env_id].detach().cpu().tolist(),
                    "clean_release_step": (
                        int(self._a2_pull_v61_clean_release_step[env_id].item())
                        if int(self._a2_pull_v61_clean_release_step[env_id].item()) >= 0
                        else None
                    ),
                    "hinge_running_peak_after_release_rad": (
                        float(self._a2_pull_v61_hinge_running_peak_after_release[env_id].item())
                        if torch.isfinite(self._a2_pull_v61_hinge_running_peak_after_release[env_id])
                        else None
                    ),
                    "hinge_reclosure_after_release_rad": float(
                        self._a2_pull_v61_hinge_reclosure_after_release_rad[env_id].item()
                    ),
                    "frame_passage": bool(self._a2_pull_frame_passage[env_id].item()),
                    "e6": bool(self._a2_pull_event_reached[env_id, A2PullEvent.E6_PATH_REVERSAL_ENTRY].item()),
                    "e7": bool(self._a2_pull_event_reached[env_id, A2PullEvent.E7_WHOLE_BODY_CLEAR].item()),
                }
            if self._is_a2_pull_v5():
                record["pull_v5"] = {
                    "reset_source": self._a2_pull_v5_reset_source[env_id],
                    "declared_reset_source": self._a2_pull_v5_declared_reset_source[env_id],
                    "persistent_release": bool(
                        self._a2_pull_v5_persistent_release[env_id].item()
                    ),
                    "persistent_release_streak_steps": int(
                        self._a2_pull_v5_persistent_release_streak[env_id].item()
                    ),
                    "release_streak_required_steps": A2_PULL_V5_RELEASE_STREAK_STEPS,
                    "start_override_active": bool(
                        self._a2_pull_v5_start_override_active[env_id].item()
                    ),
                    "start_override_active_steps": int(
                        self._a2_pull_v5_start_override_active_steps[env_id].item()
                    ),
                    "start_override_base_slice_equal": bool(
                        self._a2_pull_v5_start_override_base_slice_equal[env_id].item()
                    ),
                    "passage_attempt_hinge_rad": (
                        float(self._a2_pull_passage_attempt_hinge_rad[env_id].item())
                        if torch.isfinite(self._a2_pull_passage_attempt_hinge_rad[env_id])
                        else None
                    ),
                    "intervention_active": bool(
                        self._a2_pull_v5_intervention_active[env_id].item()
                    ),
                    "intervention_elapsed_steps": int(
                        self._a2_pull_v5_intervention_elapsed_steps[env_id].item()
                    ),
                }
                if self.config.get("a2_pull_v5_probe_enabled", False):
                    record["pull_v5_probe"] = {
                        "fixture": self.config["a2_pull_v5_probe_fixture"],
                        "command": self.config["a2_pull_v5_probe_command"],
                        "command_primitive": self.config["a2_pull_v5_probe_command"],
                        "sequence": self._a2_pull_v5_probe_sequence_id
                        or self.config["a2_pull_v5_probe_command"],
                        "sequence_phases": list(self._a2_pull_v5_probe_sequence_phases),
                        "sequence_phase_index": int(
                            self._a2_pull_v5_probe_phase_index[env_id].item()
                        ),
                        "sequence_complete": bool(
                            self._a2_pull_v5_probe_sequence_complete[env_id].item()
                        ),
                    }
                    if self._a2_pull_v5_scheduler_enabled:
                        state_names = {
                            value: key for key, value in self._A2_PULL_V5_4_SCHEDULER_STATES.items()
                        }
                        record["pull_v5_probe"]["scheduler"] = {
                            "schema": self._A2_PULL_V5_4_SCHEDULER_SCHEMA,
                            "state": state_names[int(self._a2_pull_v5_scheduler_state[env_id].item())],
                            "failure_reason": self._a2_pull_v5_scheduler_failure_reason[env_id],
                            "settle_steps": int(self._a2_pull_v5_scheduler_settle_steps[env_id].item()),
                            "trim_steps": int(self._a2_pull_v5_scheduler_trim_steps[env_id].item()),
                            "terminal_hold_steps": int(self._a2_pull_v5_scheduler_terminal_hold_steps[env_id].item()),
                            "terminal_current_state": (
                                state_names[int(self._a2_pull_v5_scheduler_state[env_id].item())]
                                == "DONE"
                            ),
                            "scientific_denominator_included": False,
                            "denominator_scope": "none",
                        }
            record["pull_v2_unlatch"] = {
                "stable_unlatch_handle_based": bool(
                    self._a2_pull_stable_unlatch_handle_ever[env_id].item()
                ),
                "stable_unlatch_latch_based": bool(
                    self._a2_pull_stable_unlatch_latch_ever[env_id].item()
                ),
                "relock_handle_based": bool(self._a2_pull_relock_handle_ever[env_id].item()),
                "relock_latch_based": bool(self._a2_pull_relock_latch_ever[env_id].item()),
                "handle_unlatch_threshold_rad": 0.3,
                "latch_unlatch_threshold_m": self._get_a2_pull_e3_latch_threshold_m(),
                "relock_definition": (
                    "prior stable threshold crossing, then threshold loss while "
                    "hinge remains below the Stage3-to4 gate"
                ),
            }
            if self._is_a2_pull_traversal():
                frame_approach_current = bool(
                    (abs(float(frame_delta_xy[env_id, 0].item())) < 0.3)
                    and (
                        abs(float(frame_delta_xy[env_id, 1].item()))
                        <= 0.5 * float(self.door_width[env_id].item())
                    )
                )
                panel_clear_current = bool(
                    (body_panel_total[env_id] + arm_panel_total[env_id]).item() == 0.0
                )
                frame_passage_current = bool(
                    frame_approach_current and panel_clear_current
                )
                planar_crossing_current = bool(
                    self._pull_direction.signed_crossing_progress(
                        root_x[env_id], door_x[env_id]
                    ).item()
                    > 0.0
                )
                corridor_wide_raw = self._a2_pull_last_raw_reward_components[
                    "a2_corridor_door_wide"
                ][env_id] if "a2_corridor_door_wide" in self._a2_pull_last_raw_reward_components else corridor_wide_raw_component[env_id]
                corridor_clean_raw = self._a2_pull_last_raw_reward_components[
                    "a2_corridor_clean_passage"
                ][env_id]
                frame_approach_raw = frame_approach_raw_component[env_id]
                current_step = int(self.episode_length_buf[env_id].item())
                release_step = int(self._a2_pull_deliberate_release_step[env_id].item())
                record["pull_v3_traversal"] = {
                    "aperture_ready": bool(self._a2_pull_aperture_ready[env_id].item()),
                    "aperture_ready_current": bool(aperture_ready_current[env_id].item()),
                    "frame_approach": bool(self._a2_pull_frame_approach[env_id].item()),
                    "frame_approach_current": frame_approach_current,
                    "frame_approach_active": bool(
                        self._a2_pull_frame_approach_active[env_id].item()
                    ),
                    "frame_approach_reward_executed": (
                        "a2_pull_frame_approach" in self.reward_scales
                    ),
                    "frame_approach_raw": float(frame_approach_raw.item()),
                    "frame_midpoint_distance_m": float(
                        frame_midpoint_distance[env_id].item()
                    ),
                    "frame_midpoint_distance_min_m": float(
                        self._a2_pull_frame_midpoint_distance_min_m[env_id].item()
                    ),
                    "frame_passage": bool(self._a2_pull_frame_passage[env_id].item()),
                    "frame_passage_current": frame_passage_current,
                    "planar_crossing": bool(self._a2_pull_planar_crossing[env_id].item()),
                    "planar_crossing_current": planar_crossing_current,
                    "detour": bool(self._a2_pull_detour[env_id].item()),
                    "detour_current": planar_crossing_current
                    and not bool(self._a2_pull_frame_passage[env_id].item()),
                    "deliberate_release": bool(
                        self._a2_pull_deliberate_release[env_id].item()
                    ),
                    "deliberate_release_current": release_step == current_step,
                    "panel_clear": panel_clear_current,
                    "panel_contact_ever": bool(
                        self._a2_pull_body_panel_contact_steps[env_id].item() > 0
                    ),
                    "bilateral_handle_contact": bool(
                        contact_masks["both_contact"][env_id].item()
                    ),
                    "no_handle_contact": bool(
                        (~torch.any(contact_masks["contacting"][env_id])).item()
                    ),
                    "minimum_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "swept_arc_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "signed_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "swept_arc_clearance_margin_min_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_min_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_min_m[env_id]
                        )
                        else None
                    ),
                    "base_path_length_m": float(
                        self._a2_pull_base_path_length_m[env_id].item()
                    ),
                    "base_reversal_count": int(
                        self._a2_pull_base_reversal_count[env_id].item()
                    ),
                    "post_release_recontact_count": int(
                        self._a2_pull_post_release_recontact_count[env_id].item()
                    ),
                    "corridor_door_wide_raw": float(corridor_wide_raw.item()),
                    "corridor_clean_passage_raw": float(corridor_clean_raw.item()),
                    "corridor_door_wide_raw_component": float(corridor_wide_raw.item()),
                    "corridor_door_wide_reward_executed": (
                        "a2_corridor_door_wide" in self.reward_scales
                    ),
                    "corridor_clean_passage_raw_component": float(corridor_clean_raw.item()),
                    "corridor_door_wide_pre_aperture_steps": int(
                        self._a2_pull_corridor_door_wide_pre_aperture_steps[env_id].item()
                    ),
                    "corridor_clean_passage_pre_aperture_steps": int(
                        self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_id].item()
                    ),
                }
            records.append(record)
        return records

    @override
    def scene_creation_callback(self, simulator):
        result = super().scene_creation_callback(simulator)
        target_obj = simulator.task_config.get("target_obj")
        if not isinstance(target_obj, str) or not target_obj:
            raise RuntimeError("Pull frame telemetry requires task.target_obj.")
        body_filters = tuple(
            f"/World/envs/env_.*/Robot/{body_name}"
            for body_name in self.A2_DOOR_BODY_PANEL_FILTER_NAMES
        )
        arm_filters = tuple(
            f"/World/envs/env_.*/Robot/{body_name}"
            for body_name in self.A2_DOOR_ARM_PANEL_FILTER_NAMES
        )
        simulator.scene.sensors[self.A2_PULL_DOOR_BODY_FRAME_CONTACT_SENSOR] = ContactSensor(
            ContactSensorCfg(
                prim_path=f"/World/envs/env_.*/{target_obj}/root",
                filter_prim_paths_expr=body_filters,
            )
        )
        simulator.scene.sensors[self.A2_PULL_DOOR_ARM_FRAME_CONTACT_SENSOR] = ContactSensor(
            ContactSensorCfg(
                prim_path=f"/World/envs/env_.*/{target_obj}/root",
                filter_prim_paths_expr=arm_filters,
            )
        )
        return result

    @override
    def _reset_root_states(self, env_ids, target_root_states=None):
        if not self._use_a2_base:
            raise RuntimeError("DoorOpenA2Pull requires env.config.a2_base.enabled=true.")
        if target_root_states is not None:
            return A2Base._reset_root_states(self, env_ids, target_root_states)

        self.target_robot_root_states[env_ids] = self.base_init_state
        self.target_robot_root_states[env_ids, :3] += self.env_origins[env_ids]
        self.target_robot_root_states[env_ids, 0:1] = (
            self._pull_direction.approach_side_x
            * torch_rand_float(0.6, 1.5, (len(env_ids), 1), device=str(self.device))
            + self.env_origins[env_ids, 0:1]
        )
        self.target_robot_root_states[env_ids, 1:2] = (
            torch_rand_float(-0.5, 0.5, (len(env_ids), 1), device=str(self.device))
            + self.env_origins[env_ids, 1:2]
        )
        roll, pitch, _yaw = euler_xyz_from_quat(self.target_robot_root_states[env_ids, 3:7])
        initial_yaw = self.config.get("a2_pull_robot_initial_yaw_rad")
        if (
            isinstance(initial_yaw, bool)
            or not isinstance(initial_yaw, (int, float))
            or not math.isfinite(float(initial_yaw))
        ):
            raise RuntimeError(
                "a2_pull_robot_initial_yaw_rad must be a finite configured float."
            )
        random_yaw = torch.full(
            (len(env_ids),), float(initial_yaw), device=self.device, dtype=roll.dtype
        )
        self.target_robot_root_states[env_ids, 3:7] = quat_from_euler_xyz(
            roll,
            pitch,
            random_yaw,
        )
        self.target_robot_root_states[env_ids, 7:13] = 0.0

    @override
    def _record_a2_stage0_to1_staging_standoff(
        self,
        advance_mask: torch.Tensor,
        grasp_target: torch.Tensor,
        root_pos: torch.Tensor,
    ) -> None:
        valid = self._a2_stage0_to1_staging_valid
        standoff_buffer = self._a2_stage0_to1_staging_standoff
        expected_shape = (self.num_envs,)
        if (
            advance_mask.shape != expected_shape
            or advance_mask.dtype != torch.bool
            or valid.shape != expected_shape
            or valid.dtype != torch.bool
            or standoff_buffer.shape != expected_shape
            or advance_mask.device != torch.device(self.device)
            or valid.device != advance_mask.device
            or standoff_buffer.device != advance_mask.device
        ):
            raise RuntimeError("Pull-v0 staging telemetry requires device-local vector buffers.")
        signed_standoff = self._pull_direction.approach_side_x * (
            root_pos[:, 0] - grasp_target[:, 0]
        )
        if not torch.all(torch.isfinite(signed_standoff)):
            raise RuntimeError("Pull-v0 signed staging standoff must be finite.")
        first_advance = advance_mask & ~valid
        standoff_buffer[first_advance] = signed_standoff[first_advance]
        valid[first_advance] = True

    @StagedTaskBase.effective_in_stage(DoorPregrasp.STAGE_WALK_TO_DOOR)
    def _reward_walk_to_door(self):
        current_root_pos = self.simulator.robot_root_states[:, :3].clone()
        grasp_target_pos = self._compute_grasp_target().clone()
        x_min, x_max, y_tol = self._get_a2_stage0_staging_band()
        stage0_target_pos = a2_signed_stage0_nearest_staging_target(
            current_root_pos,
            grasp_target_pos,
            x_min,
            x_max,
            y_tol,
            self._pull_direction,
        )
        target_direction = stage0_target_pos - current_root_pos
        target_distance = torch.linalg.norm(target_direction, dim=-1, keepdim=True)
        nonzero_distance = target_distance > 0.0
        target_dir = torch.where(
            nonzero_distance,
            target_direction / torch.where(
                nonzero_distance,
                target_distance,
                torch.ones_like(target_distance),
            ),
            torch.zeros_like(target_direction),
        )
        current_root_vel = self.simulator.robot_root_states[:, 7:10].clone()
        target_vel = self.config.get("target_root_vel", 0.3) * target_dir
        return self._tracking_reward_util(
            torch.linalg.norm(current_root_vel - target_vel, dim=-1),
            std=0.15,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

    @override
    def _stage_0_to_1_advance_condition(self):
        grasp_target = self._compute_grasp_target()
        root_pos = self.simulator.robot_root_states[:, :3]
        x_min, x_max, y_tol = self._get_a2_stage0_staging_band()
        condition = a2_signed_stage0_staging_band_mask(
            root_pos,
            grasp_target,
            x_min,
            x_max,
            y_tol,
            self._pull_direction,
        )
        arm_target_pos = self._get_a2_arm_default_dof_pos()
        arm_max_deviation = self._get_required_positive_float_config(
            "a2_stage0_arm_default_max_deviation",
            "pull stage0->1 arm default transition",
        )
        max_deviation = (
            torch.abs(
                self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx] - arm_target_pos
            )
            .max(dim=-1)
            .values
        )
        condition &= max_deviation < arm_max_deviation
        base_command = self.get_physical_homie_commands()
        if (
            not torch.is_tensor(base_command)
            or base_command.shape != (self.num_envs, 5)
            or base_command.device != torch.device(self.device)
            or not torch.all(torch.isfinite(base_command))
        ):
            raise RuntimeError(
                "Pull stage0->1 base-still gate requires finite physical commands "
                f"shape ({self.num_envs}, 5) on {self.device}."
            )
        condition &= torch.norm(base_command[:, :3], dim=1) <= 0.1
        self._record_a2_stage0_to1_staging_standoff(condition, grasp_target, root_pos)
        return condition

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_PREGRASP, DoorPregrasp.STAGE_GRASP]
    )
    def _reward_penalty_a2_stage1_stage2_base_forward_creep(self):
        deadband = self._get_required_positive_float_config(
            "a2_stage1_stage2_base_forward_creep_deadband",
            "pull stage1/stage2 base creep",
        )
        scale = self._get_required_positive_float_config(
            "a2_stage1_stage2_base_forward_creep_scale",
            "pull stage1/stage2 base creep",
        )
        grasp_target = self._compute_grasp_target()
        x_min, _x_max, _y_tol = self._get_a2_stage0_staging_band()
        near_boundary_x = (
            grasp_target[:, 0] + self._pull_direction.approach_side_x * x_min
        )
        root_x = self.simulator.robot_root_states[:, 0]
        penetration_toward_door = self._pull_direction.travel_dir_x * (
            root_x - near_boundary_x
        )
        return ((penetration_toward_door - deadband) / scale).clamp(0.0, 1.0)

    @StagedTaskBase.effective_in_stage(
        [
            DoorPregrasp.STAGE_WALK_TO_DOOR,
            DoorPregrasp.STAGE_PREGRASP,
            DoorPregrasp.STAGE_GRASP,
        ]
    )
    def _reward_penalty_face_door(self):
        relative_door_quat = xyzw_to_wxyz(self.relative_door_rot_buf)
        zeros = torch.zeros(self.num_envs, device=self.device)
        desired_relative_quat = quat_from_euler_xyz(
            zeros,
            zeros,
            torch.full_like(zeros, math.pi),
        )
        orientation_error = quat_mul(quat_inv(desired_relative_quat), relative_door_quat)
        return wrap_to_pi(axis_angle_from_quat(orientation_error).norm(dim=-1))

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_OPEN, DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH]
    )
    def _reward_pull_door_handle(self):
        handle_velocity = self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
        handle_position = (
            self.simulator.scene.articulations["door"]
            .data.joint_pos[:, 1]
            .clamp(min=0.0, max=0.785398)
            / 0.785398
        )
        reward = (handle_velocity + handle_position).clamp(max=1.0, min=-1.0)
        income_mask = self._get_a2_pull_load_bearing_income_mask()
        income_mode = self.config["a2_pull_stage3_handle_income_mode"]
        if income_mode == "e2_latched_k_hold":
            income_mask |= (
                (self.stage_buf == self.STAGE_OPEN)
                & self._a2_pull_event_reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
                & self._get_a2_hold_streak_ok_mask()
            )
        elif income_mode != "live_proof":
            raise RuntimeError(
                "a2_pull_stage3_handle_income_mode must be live_proof or "
                f"e2_latched_k_hold; got {income_mode!r}."
            )
        result = reward * income_mask.float()
        if self._is_a2_pull_v6():
            result = torch.where(
                self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION],
                torch.zeros_like(result),
                result,
            )
        return result

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_OPEN, DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH]
    )
    @override
    def _reward_a2_stage3_stage4_hold_and_drive(self):
        reward = super()._reward_a2_stage3_stage4_hold_and_drive()
        if not self._is_a2_pull_v6():
            return reward
        return torch.where(
            self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION],
            torch.zeros_like(reward),
            reward,
        )

    @override
    def _get_a2_stage34_hold_income_mask(self) -> torch.Tensor:
        hold_income = super()._get_a2_stage34_hold_income_mask()
        if not self._is_a2_pull_v6():
            return hold_income
        return hold_income & (self._a2_pull_v6_subphase != self._A2_PULL_V6_PHASE_D)

    @StagedTaskBase.effective_in_stage(
        [
            DoorPregrasp.STAGE_PREGRASP,
            DoorPregrasp.STAGE_GRASP,
            DoorPregrasp.STAGE_OPEN,
            DoorPregrasp.STAGE_SWING,
        ]
    )
    @override
    def _reward_grasp(self):
        reward = super()._reward_grasp()
        if not self._is_a2_pull_v6():
            return reward
        return torch.where(
            self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D,
            torch.zeros_like(reward),
            reward,
        )

    @StagedTaskBase.effective_in_stage(DoorPregrasp.STAGE_SWING)
    @override
    def _reward_penalty_a2_stage4_arm_default_pose_l1(self):
        reward = super()._reward_penalty_a2_stage4_arm_default_pose_l1()
        if not self._is_a2_pull_v6():
            return reward
        active = (
            self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
            & (self.stage_buf == self.STAGE_SWING)
        )
        return torch.where(active, reward, torch.zeros_like(reward))

    @StagedTaskBase.effective_in_stage(DoorPregrasp.STAGE_SWING)
    def _reward_penalty_a2_pull_v6_post_release_gripper_open_l1(self):
        gripper_pos = self.simulator.dof_pos[:, self._a2_gripper_dof_indices]
        open_target = self._a2_gripper_open_target
        close_target = self._a2_gripper_close_target
        normalized = torch.linalg.vector_norm(gripper_pos - open_target, dim=-1) / torch.linalg.vector_norm(
            close_target - open_target
        )
        active = (
            self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
            & (self.stage_buf == self.STAGE_SWING)
        )
        return normalized * active.float()

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_OPEN, DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH]
    )
    def _reward_pull_door_hinge(self):
        hinge_velocity = self.simulator.scene.articulations["door"].data.joint_vel[:, 0] * 10.0
        hinge_position = (
            self.simulator.scene.articulations["door"]
            .data.joint_pos[:, 0]
            .clamp(min=0.0, max=1.5708)
            / 1.5708
        )
        income_mask = (
            self._get_a2_stage34_hold_income_mask()
            & self._get_a2_pull_load_bearing_income_mask()
        )
        income_mode = self.config["a2_pull_stage3_hinge_income_mode"]
        if income_mode == "left_e3_latched_k_hold":
            income_mask |= (
                (self.stage_buf == self.STAGE_OPEN)
                & (self.door_open_lr == 1.0)
                & self._a2_pull_event_reached[:, A2PullEvent.E3_LATCH_RELEASE]
                & self._get_a2_hold_streak_ok_mask()
            )
        elif income_mode != "live_proof":
            raise RuntimeError(
                "a2_pull_stage3_hinge_income_mode must be live_proof or "
                f"left_e3_latched_k_hold; got {income_mode!r}."
            )
        reward = (hinge_velocity + hinge_position).clamp(max=1.0, min=-1.0)
        result = reward * income_mask.float()
        if self._is_a2_pull_v6():
            result = torch.where(
                self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION],
                torch.zeros_like(result),
                result,
            )
        return result

    @StagedTaskBase.effective_in_stage(DoorPregrasp.STAGE_OPEN)
    def _reward_a2_pull_stage3_opening_tangent_creation(self):
        if not self._is_a2_pull_v6():
            raise RuntimeError("Stage3 opening-tangent creation requires pull-v6.")
        contact = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "Stage3 opening-tangent creation"
        )["both_contact"]
        latch_position = self._get_door_joint_pos(
            "Stage3 opening-tangent creation", 3
        )[:, 2]
        active = (
            (self.door_open_lr == 1.0)
            & contact
            & self._get_a2_hold_streak_ok_mask()
            & (latch_position >= self._get_a2_pull_e3_latch_threshold_m())
        )
        target_speed = self._get_required_positive_float_config(
            "a2_pull_stage3_tangent_creation_speed_mps",
            "Stage3 opening-tangent creation speed",
        )
        return (
            self._a2_pull_v6_positive_arm_tangent / target_speed
        ).clamp(0.0, 1.0) * active.float()

    def _get_a2_pull_stage3_pose_quality(self) -> torch.Tensor:
        if not self._is_a2_pull_v6():
            raise RuntimeError("Stage3 pose quality requires pull-v6.")
        distance_quality = self._get_a2_grasp_target_distance_reward(
            "Stage3 pose quality"
        )
        opening_alignment, approach_alignment = (
            self._get_a2_gripper_handle_orientation_metrics()
        )
        opening_quality = self._tracking_reward_util(
            1.0 - opening_alignment,
            std=0.25,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )
        approach_quality = self._tracking_reward_util(
            1.0 - approach_alignment,
            std=0.25,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )
        return distance_quality * opening_quality * approach_quality

    @StagedTaskBase.effective_in_stage(DoorPregrasp.STAGE_OPEN)
    def _reward_a2_pull_stage3_pose_quality(self):
        active = (self.door_open_lr == 1.0) & (
            self.stage_buf == self.STAGE_OPEN
        )
        return self._get_a2_pull_stage3_pose_quality() * active.float()

    @StagedTaskBase.effective_in_stage(DoorPregrasp.STAGE_OPEN)
    def _reward_a2_pull_stage3_bilateral_pose_quality(self):
        return self._get_a2_pull_stage3_pose_quality()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_OPEN, DoorPregrasp.STAGE_SWING])
    @override
    def _reward_a2_stage3_stage4_keep_close_command(self):
        reward = super()._reward_a2_stage3_stage4_keep_close_command()
        if not self._is_a2_pull_v6():
            return reward
        active = (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_A) | (
            self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B
        )
        return torch.where(active, reward, torch.zeros_like(reward))

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_OPEN, DoorPregrasp.STAGE_SWING])
    @override
    def _reward_penalty_a2_stage3_stage4_open_command(self):
        if not self._is_a2_pull_traversal():
            return super()._reward_penalty_a2_stage3_stage4_open_command()
        primitive = self._get_a2_gripper_primitive_raw_column(
            "pull-v3 penalty_a2_stage3_stage4_open_command"
        )
        reward = ((primitive - 0.2) / 0.8).clamp(0.0, 1.0)
        pull_v3_hold_mask = (self.stage_buf == self.STAGE_OPEN) | (
            (self.stage_buf == self.STAGE_SWING) & ~self._a2_pull_aperture_ready
        )
        if self._is_a2_pull_v6():
            pull_v3_hold_mask = (self.stage_buf == self.STAGE_OPEN) | (
                (self.stage_buf == self.STAGE_SWING)
                & (
                    (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_A)
                    | (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
                )
            )
        return reward * pull_v3_hold_mask.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    @override
    def _reward_a2_corridor_door_wide(self):
        if not self._is_a2_pull_traversal():
            return super()._reward_a2_corridor_door_wide()
        door_joint_pos = self._get_door_joint_pos("pull-v3 corridor door-wide reward", 1)
        door_states = self.simulator.get_task_root_state("door")
        whole_body_clear = self._get_a2_pull_whole_body_clear_mask(door_states[:, 0])
        return (
            (door_joint_pos[:, 0] / 1.5).clamp(0.0, 1.0)
            * self._a2_pull_aperture_ready.float()
            * (~whole_body_clear).float()
        )

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_frame_approach(self):
        frame_midpoint_xy = self._get_a2_pull_door_frame_midpoint(
            self.simulator.get_task_root_state("door")
        )
        root_states = self.simulator.robot_root_states
        delta_xy = frame_midpoint_xy - root_states[:, 0:2]
        distance = torch.linalg.vector_norm(delta_xy, dim=-1, keepdim=True)
        if not torch.all(torch.isfinite(distance)) or torch.any(distance <= 0.0):
            raise RuntimeError(
                "Pull v4 frame-approach reward requires a finite nonzero root-to-frame-midpoint distance."
            )
        toward = delta_xy / distance
        v_toward = torch.sum(root_states[:, 7:9] * toward, dim=-1)
        raw = (v_toward / 0.3).clamp(-1.0, 1.0)
        active = self._get_a2_pull_frame_approach_active_mask()
        self._a2_pull_frame_approach_active[:] = active
        return raw * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_arm_tangent_progress(self):
        active = (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B) | (
            self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C
        )
        return self._a2_pull_v6_positive_arm_tangent * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_base_tangent_penalty(self):
        active = (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B) | (
            self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C
        )
        return self._a2_pull_v6_positive_base_tangent * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_handle_side_progress(self):
        active = (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B) | (
            self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C
        )
        return (
            self._a2_pull_v6_handle_side_progress
            * self._a2_pull_v6_instantaneous_arm_tangent_share
            * active.float()
        )

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_handoff_side_progress(self):
        pivot_quality = self._get_a2_pull_v6_handoff_pivot_quality()
        return (
            self._a2_pull_v6_handle_side_progress
            * self._a2_pull_v6_instantaneous_arm_tangent_share
            * pivot_quality
            * self._a2_pull_v6_handoff_reward_window.float()
        )

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_handle_side_bonus(self):
        return self._a2_pull_v6_handle_cross_bonus.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_arc_tracking(self):
        active = (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B) | (
            self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C
        )
        return self._a2_pull_v6_arc_quality * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_pivot_excess_penalty(self):
        active = (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B) | (
            self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C
        )
        radius = self._get_required_positive_float_config("a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius")
        if torch.any(active & ~torch.isfinite(self._a2_pull_v6_pivot_displacement_m)):
            raise RuntimeError("Pull-v6 active send phase requires finite captured pivot displacement.")
        excess = torch.relu(
            torch.where(
                active,
                self._a2_pull_v6_pivot_displacement_m,
                torch.zeros_like(self._a2_pull_v6_pivot_displacement_m),
            ) - radius
        )
        return torch.where(active, excess, torch.zeros_like(excess))

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_hinge_momentum(self):
        active = self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_C
        hinge_vel = self._get_door_joint_vel("Pull-v6 hinge momentum reward", 1)[:, 0]
        return torch.relu(hinge_vel) * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_handoff_hinge_momentum(self):
        _body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
        _arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
        panel_clear = (body_total + arm_total) == 0.0
        active = (
            self._a2_pull_v6_handoff_reached
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
            & self._a2_pull_v6_pivot_valid
            & self._a2_pull_v6_prev_bilateral_contact
            & panel_clear
            & (self._a2_pull_v6_pivot_displacement_m <= self._get_required_positive_float_config(
                "a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"
            ))
            & (self._a2_pull_v6_arm_tangent_share >= self._get_required_positive_float_config(
                "a2_pull_v6_release_min_arm_tangent_share",
                "Pull-v6 release minimum arm tangent share",
            ))
        )
        hinge_vel = self._get_door_joint_vel("Pull-v6 handoff hinge momentum reward", 1)[:, 0]
        return hinge_vel * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_handoff_hinge_angle_deficit(self):
        hinge_pos = self._get_door_joint_pos("Pull-v6 handoff hinge-angle deficit reward", 1)[:, 0]
        active = (
            self._a2_pull_v6_handoff_reached
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_B)
            & self._a2_pull_v6_release_side_qualified
        )
        deficit = torch.relu(
            self._get_required_positive_float_config(
                "a2_pull_v6_release_hinge_rad", "Pull-v6 release hinge"
            )
            - hinge_pos
        )
        return deficit * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING])
    def _reward_a2_pull_v6_workspace_margin_progress(self):
        return (
            self._a2_pull_v6_workspace_margin_progress
            * self._a2_pull_v6_workspace_margin_progress_active.float()
        )

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING])
    def _reward_a2_pull_v6_passage_alignment_progress(self):
        return (
            self._a2_pull_v6_passage_alignment_progress
            * self._a2_pull_v6_passage_alignment_progress_active.float()
        )

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING])
    def _reward_a2_pull_v6_passage_command_alignment(self):
        return (
            self._a2_pull_v6_passage_command_alignment
            * self._a2_pull_v6_passage_command_alignment_active.float()
        )

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_post_release_lateral_command_alignment(self):
        return (
            self._a2_pull_v6_post_release_lateral_command_alignment
            * self._a2_pull_v6_post_release_lateral_command_alignment_active.float()
        )

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING])
    def _reward_a2_pull_v6_post_release_arm_tuck_progress(self):
        return (
            self._a2_pull_v6_post_release_arm_tuck_progress
            * self._a2_pull_v6_post_release_arm_tuck_progress_active.float()
        )

    def _get_a2_pull_v6_handoff_pivot_quality(self):
        reward_window = self._a2_pull_v6_handoff_reward_window
        pivot_displacement = self._a2_pull_v6_pivot_displacement_m
        if torch.any(reward_window & ~torch.isfinite(pivot_displacement)):
            raise RuntimeError(
                "Pull-v6 handoff reward window requires finite pivot displacement."
            )
        radius = self._get_required_positive_float_config(
            "a2_pull_v6_base_relief_radius_m", "Pull-v6 base relief radius"
        )
        active_displacement = torch.where(
            reward_window,
            pivot_displacement,
            torch.zeros_like(pivot_displacement),
        )
        return torch.exp(-0.5 * (active_displacement / radius).square())

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_clean_release_quality(self):
        return self._a2_pull_v6_release_quality * self._a2_pull_v6_clean_release_event.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_release_open_command_quality(self):
        primitive = self._get_a2_gripper_primitive_raw_column(
            "Pull-v6 release open-command quality"
        )
        negative = (primitive / 3.0).clamp(-1.0, 0.0)
        positive = primitive.clamp(0.0, 1.0)
        quality = negative + positive
        active = (
            self._a2_pull_v6_release_action_started_ready
            | self._a2_pull_v6_clean_release_event
        )
        return quality * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_post_release_persistence(self):
        required_steps = self.config["a2_pull_v6_release_persistence_steps"]
        active = (
            self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
            & self._a2_pull_v6_persistence_income_active
            & (self._a2_pull_v6_release_persistence > 0)
            & (self._a2_pull_v6_release_persistence <= required_steps)
        )
        return active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_post_release_arm_default_target_quality(self):
        active = (
            self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
            & self._a2_pull_v6_release_event
        )
        reference = self._get_required_positive_float_config(
            "a2_pull_v6_arm_default_l1_reference", "Pull-v6 arm-default L1 reference"
        )
        quality = (
            1.0 - torch.sum(torch.abs(self._delta_actions), dim=-1) / reference
        ).clamp(-1.0, 1.0)
        return quality * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_post_release_open_command_quality(self):
        required_steps = self.config["a2_pull_v6_release_persistence_steps"]
        active = (
            self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
            & self._a2_pull_v6_persistence_income_active
            & (self._a2_pull_v6_release_persistence > 0)
            & (self._a2_pull_v6_release_persistence <= required_steps)
        )
        primitive = self._get_a2_gripper_primitive_raw_column(
            "Pull-v6 post-release open-command quality"
        )
        quality = ((primitive - 0.2) / 0.8).clamp(0.0, 1.0)
        return quality * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_post_release_recontact_penalty(self):
        return self._a2_pull_v6_persistence_recontact_event.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v6_premature_release_penalty(self):
        return self._a2_pull_v6_premature_release_event.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING])
    def _reward_a2_pull_v61_e6_event_credit(self):
        return self._a2_pull_v61_e6_event_pulse.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v61_e7_event_credit(self):
        return self._a2_pull_v61_e7_event_pulse.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_v61_post_release_heading_error(self):
        active = (
            self._a2_pull_v61_post_release_control_active
            & self._a2_pull_v6_clean_release
            & (self._a2_pull_v6_subphase == self._A2_PULL_V6_PHASE_D)
        )
        root_yaw = euler_xyz_from_quat(self.simulator.robot_root_states[:, 3:7])[2]
        target_yaw = math.pi if self._pull_direction.travel_dir_x < 0.0 else 0.0
        error = torch.abs(wrap_to_pi(root_yaw - target_yaw))
        return (error / (0.5 * math.pi)).clamp(max=1.0) * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    @override
    def _reward_a2_corridor_clean_passage(self):
        if not self._is_a2_pull_traversal():
            return super()._reward_a2_corridor_clean_passage()
        _body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
        _arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
        no_panel_contact = (body_total + arm_total) == 0.0
        return self._a2_pull_aperture_ready.float() * no_panel_contact.float()

    @override
    def _stage_2_to_3_advance_condition(self):
        gate_mode = self.config["a2_pull_stage2_to3_gate_mode"]
        if gate_mode == "grasp_completion":
            return super()._stage_2_to_3_advance_condition()
        if gate_mode != "tensile_proof":
            raise RuntimeError(
                "a2_pull_stage2_to3_gate_mode must be tensile_proof or grasp_completion; "
                f"got {gate_mode!r}."
            )
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "pull stage2 to stage3 advance"
        )
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
            & self._a2_pull_proof_valid
            & contact_masks["both_contact"]
        )

    @override
    def _stage_3_to_4_advance_condition(self):
        threshold_mode = self._get_a2_pull_threshold_mode()
        if threshold_mode == "hard_gate":
            body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
            arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
            del body_forces, arm_forces
            panel_clear = (body_total + arm_total) == 0.0
            advance = super()._stage_3_to_4_advance_condition() & panel_clear
            if self.config["a2_pull_stage2_to3_gate_mode"] == "grasp_completion":
                advance &= self._a2_pull_event_reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
            return advance
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "pull stage3 to stage4 advance"
        )
        body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
        arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
        del body_forces, arm_forces
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
            & contact_masks["both_contact"]
            & ((body_total + arm_total) == 0.0)
        )

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH]
    )
    @override
    def _reward_target_root_distance(self):
        reward = super()._reward_target_root_distance()
        if self._is_a2_pull_v6():
            masked = self._a2_pull_v6_subphase != self._A2_PULL_V6_PHASE_A
            return torch.where(masked, torch.zeros_like(reward), reward)
        if self._get_a2_pull_threshold_mode() == "hard_gate":
            return torch.where(
                self._a2_pull_aperture_ready,
                reward,
                torch.zeros_like(reward),
            )
        measured_e5 = (
            self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
            & self._a2_pull_clearance_ready
        )
        return torch.where(measured_e5, reward, torch.zeros_like(reward))

    @override
    def _stage_4_to_5_advance_condition(self):
        door_states = self.simulator.get_task_root_state("door")
        root_states = self.simulator.robot_root_states
        signed_crossing = self._pull_direction.signed_crossing_progress(
            root_states[:, 0], door_states[:, 0]
        )
        body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
        arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
        del body_forces, arm_forces
        frame_requirement = (
            self._a2_pull_frame_passage
            if self._is_a2_pull_traversal()
            else torch.ones_like(self._a2_pull_event_reached[:, 0])
        )
        result = (
            self._a2_pull_event_reached[:, A2PullEvent.E6_PATH_REVERSAL_ENTRY]
            & (signed_crossing > 0.0)
            & (self._pull_direction.travel_dir_x * root_states[:, 7] > 0.0)
            & ((body_total + arm_total) == 0.0)
            & frame_requirement
        )
        if self._is_a2_pull_v6():
            result &= (
                self._a2_pull_v6_clean_release
                & (self._a2_pull_v6_release_persistence >= 25)
            )
        return result

    @override
    def _stage_5_to_complete_condition(self):
        door_states = self.simulator.get_task_root_state("door")
        frame_requirement = (
            self._a2_pull_frame_passage
            if self._is_a2_pull_traversal()
            else torch.ones_like(self._a2_pull_event_reached[:, 0])
        )
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E7_WHOLE_BODY_CLEAR]
            & self._get_a2_pull_whole_body_clear_mask(door_states[:, 0])
            & frame_requirement
        )


__all__ = ["DoorOpenA2Pull"]
