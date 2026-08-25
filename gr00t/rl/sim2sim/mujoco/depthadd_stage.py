"""Faithful single-environment DepthADD v3 six-stage tracker.

The MuJoCo runner owns state collection and the four 200 Hz physics steps.  It
must call :meth:`apply_high_level_action` before those physics steps, then pass
the resulting post-physics contact and pose data to :meth:`observe_after_step`.
This keeps the policy control order explicit:

``old-stage action -> four physics steps -> contact/pose -> overtime -> transition``.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


CONTROL_HZ = 50
PHYSICS_STEPS_PER_CONTROL = 4
MAX_STAGE_TIME_CONTROL_STEPS = (250, 100, 100, 100, 100, 200)

STAGE_WALK_TO_DOOR = 0
STAGE_PREGRASP = 1
STAGE_GRASP = 2
STAGE_OPEN = 3
STAGE_SWING = 4
STAGE_THROUGH = 5


@dataclass(frozen=True)
class DepthAddStageObservation:
    """Post-physics state for one MuJoCo control step.

    All tensors are one-environment tensors.  ``gripper_handle_forces_source_n``
    contains the two fingertip forces expressed in the handle/source frame;
    consequently its y component is the squeeze axis used by the IsaacLab
    transition contract.
    """

    root_position_m: torch.Tensor
    env_origin_m: torch.Tensor
    grasp_target_position_m: torch.Tensor
    arm_position_rad: torch.Tensor
    arm_default_position_rad: torch.Tensor
    physical_base_command: torch.Tensor
    tcp_pregrasp_distance_m: torch.Tensor
    opening_alignment: torch.Tensor
    approach_alignment: torch.Tensor
    gripper_position_rad: torch.Tensor
    gripper_close_target_rad: torch.Tensor
    gripper_open_target_rad: torch.Tensor
    gripper_handle_forces_source_n: torch.Tensor
    door_hinge_rad: torch.Tensor
    handle_hinge_rad: torch.Tensor


@dataclass(frozen=True)
class DepthAddStageAction:
    """High-level action after the stage-0 arm-delta gate."""

    raw_high_level_action: torch.Tensor
    effective_high_level_action: torch.Tensor
    raw_arm_delta_echo: torch.Tensor
    accumulated_arm_delta: torch.Tensor
    stage_used_for_action: int


@dataclass(frozen=True)
class DepthAddStageStatus:
    """Episode-local stage receipt, in control steps and seconds."""

    stage: int
    total_control_steps: int
    time_in_stage_budget: int
    stage_control_steps: tuple[int, int, int, int, int, int]
    stage_times_s: tuple[float, float, float, float, float, float]
    transition_steps: tuple[int | None, int | None, int | None, int | None, int | None]
    terminal_reason: str | None
    stage4_release_gate: bool
    stage5_hold_continuity: bool

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready episode receipt for the MuJoCo runner."""

        return {
            "stage": self.stage,
            "total_control_steps": self.total_control_steps,
            "time_in_stage_budget": self.time_in_stage_budget,
            "stage_control_steps": list(self.stage_control_steps),
            "stage_times_s": list(self.stage_times_s),
            "transition_steps": list(self.transition_steps),
            "terminal_reason": self.terminal_reason,
            "stage4_release_gate": self.stage4_release_gate,
            "stage5_hold_continuity": self.stage5_hold_continuity,
        }


class DepthAddStageTracker:
    """Stateful faithful tracker for DepthADD v3's six-stage task contract."""

    def __init__(
        self,
        *,
        dtype: torch.dtype = torch.float32,
        device: torch.device | str = "cpu",
        staging_x_min_m: float = 0.5,
        staging_x_max_m: float = 0.8,
        staging_y_tolerance_m: float = 0.15,
        arm_default_max_deviation_rad: float = 0.1,
        base_still_norm_max: float = 0.1,
        pregrasp_distance_max_m: float = 0.1,
        alignment_min: float = 0.8,
        contact_force_threshold_n: float = 1.0,
        squeeze_force_min_n: float = 2.0,
        grasp_streak_control_steps: int = 5,
        stage3_to4_hinge_threshold_rad: float = 0.25,
        stage4_release_hinge_threshold_rad: float = 1.6,
        stage4_to5_hinge_threshold_rad: float = 1.25,
        handle_up_threshold_rad: float = 0.2,
        stage5_complete_root_x_m: float = 1.5,
        delta_scale: float = 0.3,
        delta_clip: float = 15.0,
        reset_on_overtime: bool = True,
    ):
        if not isinstance(reset_on_overtime, bool):
            raise ValueError("reset_on_overtime must be bool.")
        if not isinstance(grasp_streak_control_steps, int) or grasp_streak_control_steps <= 0:
            raise ValueError("grasp_streak_control_steps must be a positive integer.")
        self.dtype = dtype
        self.device = torch.device(device)
        self.staging_x_min_m = float(staging_x_min_m)
        self.staging_x_max_m = float(staging_x_max_m)
        self.staging_y_tolerance_m = float(staging_y_tolerance_m)
        self.arm_default_max_deviation_rad = float(arm_default_max_deviation_rad)
        self.base_still_norm_max = float(base_still_norm_max)
        self.pregrasp_distance_max_m = float(pregrasp_distance_max_m)
        self.alignment_min = float(alignment_min)
        self.contact_force_threshold_n = float(contact_force_threshold_n)
        self.squeeze_force_min_n = float(squeeze_force_min_n)
        self.grasp_streak_control_steps = grasp_streak_control_steps
        self.stage3_to4_hinge_threshold_rad = float(stage3_to4_hinge_threshold_rad)
        self.stage4_release_hinge_threshold_rad = float(stage4_release_hinge_threshold_rad)
        self.stage4_to5_hinge_threshold_rad = float(stage4_to5_hinge_threshold_rad)
        self.handle_up_threshold_rad = float(handle_up_threshold_rad)
        self.stage5_complete_root_x_m = float(stage5_complete_root_x_m)
        self.delta_scale = float(delta_scale)
        self.delta_clip = float(delta_clip)
        self.reset_on_overtime = reset_on_overtime
        self.accumulated_arm_delta = torch.zeros((1, 6), dtype=dtype, device=self.device)
        self.reset()

    def reset(self) -> None:
        self.stage = STAGE_WALK_TO_DOOR
        self.total_control_steps = 0
        self.time_in_stage_budget = 0
        self.stage_control_steps = [0] * 6
        self.transition_steps = [None] * 5
        self.terminal_reason: str | None = None
        self.stage2_squeeze_streak = 0
        self.stage34_both_contact_streak = 0
        self.stage4_release_gate = False
        self.stage5_hold_continuity = False
        self.accumulated_arm_delta.zero_()

    def apply_high_level_action(self, raw_action: torch.Tensor) -> DepthAddStageAction:
        """Apply the current stage's arm-delta gate before four physics steps."""

        if self.terminal_reason is not None:
            raise RuntimeError("cannot apply an action after terminal state.")
        self._require_tensor("raw_action", raw_action, (1, 12))
        stage_used = self.stage
        raw_delta = raw_action[:, 5:11].clone()
        self.accumulated_arm_delta.add_(self.delta_scale * raw_delta).clamp_(
            -self.delta_clip, self.delta_clip
        )
        if stage_used == STAGE_WALK_TO_DOOR:
            self.accumulated_arm_delta.zero_()
        effective = raw_action.clone()
        effective[:, 5:11] = self.accumulated_arm_delta
        return DepthAddStageAction(
            raw_high_level_action=raw_action.clone(),
            effective_high_level_action=effective,
            raw_arm_delta_echo=raw_delta,
            accumulated_arm_delta=self.accumulated_arm_delta.clone(),
            stage_used_for_action=stage_used,
        )

    def observe_after_step(
        self,
        observation: DepthAddStageObservation,
        action: DepthAddStageAction,
    ) -> DepthAddStageStatus:
        """Consume post-physics state, then enforce overtime before transition."""

        if self.terminal_reason is not None:
            raise RuntimeError("cannot observe after terminal state.")
        if action.stage_used_for_action != self.stage:
            raise RuntimeError(
                "action stage does not match tracker stage; use one action and one observation per control step."
            )
        self._validate_observation(observation)
        both_contact, valid_squeeze = self._contact_masks(observation)
        self._update_contact_streaks(both_contact, valid_squeeze)
        self._update_stage4_release_gate(observation.door_hinge_rad)
        complete = (
            self.stage == STAGE_THROUGH
            and self._root_x_rel(observation) > self.stage5_complete_root_x_m
        )
        advance = self.stage < STAGE_THROUGH and self._advance_predicate(observation, both_contact)
        if self.stage == STAGE_THROUGH:
            self._update_stage5_hold_continuity(both_contact)

        prior_stage = self.stage
        self.total_control_steps += 1
        self.stage_control_steps[prior_stage] += 1
        self.time_in_stage_budget += 1
        is_overtime = (
            self.time_in_stage_budget >= MAX_STAGE_TIME_CONTROL_STEPS[prior_stage]
        )
        if complete:
            self.terminal_reason = "complete"
        elif is_overtime and self.reset_on_overtime:
            self.terminal_reason = "stage_overtime"
        elif advance:
            self.time_in_stage_budget -= MAX_STAGE_TIME_CONTROL_STEPS[prior_stage]
            self.stage += 1
            self.transition_steps[prior_stage] = self.total_control_steps
            if prior_stage == STAGE_SWING:
                self.stage5_hold_continuity = (
                    self.stage34_both_contact_streak >= self.grasp_streak_control_steps
                )
        return self.status()

    def status(self) -> DepthAddStageStatus:
        stage_steps = tuple(self.stage_control_steps)
        return DepthAddStageStatus(
            stage=self.stage,
            total_control_steps=self.total_control_steps,
            time_in_stage_budget=self.time_in_stage_budget,
            stage_control_steps=stage_steps,
            stage_times_s=tuple(steps / CONTROL_HZ for steps in stage_steps),
            transition_steps=tuple(self.transition_steps),
            terminal_reason=self.terminal_reason,
            stage4_release_gate=self.stage4_release_gate,
            stage5_hold_continuity=self.stage5_hold_continuity,
        )

    def _advance_predicate(self, state: DepthAddStageObservation, both_contact: bool) -> bool:
        if self.stage == STAGE_WALK_TO_DOOR:
            return self._stage0_to1(state)
        if self.stage == STAGE_PREGRASP:
            return self._stage1_to2(state)
        if self.stage == STAGE_GRASP:
            return self.stage2_squeeze_streak >= self.grasp_streak_control_steps
        if self.stage == STAGE_OPEN:
            return (
                self._scalar(state.door_hinge_rad) > self.stage3_to4_hinge_threshold_rad
                and self.stage34_both_contact_streak >= self.grasp_streak_control_steps
            )
        if self.stage == STAGE_SWING:
            return (
                self._root_x_rel(state) > 0.0
                and self._scalar(state.door_hinge_rad) > self.stage4_to5_hinge_threshold_rad
                and self._scalar(state.handle_hinge_rad) < self.handle_up_threshold_rad
            )
        raise RuntimeError(f"unsupported stage {self.stage}.")

    def _stage0_to1(self, state: DepthAddStageObservation) -> bool:
        dx = state.grasp_target_position_m[:, 0] - state.root_position_m[:, 0]
        dy = state.root_position_m[:, 1] - state.grasp_target_position_m[:, 1]
        max_arm_deviation = torch.max(
            torch.abs(state.arm_position_rad - state.arm_default_position_rad), dim=1
        ).values
        base_norm = torch.linalg.vector_norm(state.physical_base_command[:, :3], dim=1)
        return bool(
            (
                (dx >= self.staging_x_min_m)
                & (dx <= self.staging_x_max_m)
                & (torch.abs(dy) < self.staging_y_tolerance_m)
                & (max_arm_deviation < self.arm_default_max_deviation_rad)
                & (base_norm <= self.base_still_norm_max)
            ).item()
        )

    def _stage1_to2(self, state: DepthAddStageObservation) -> bool:
        span = torch.abs(state.gripper_open_target_rad - state.gripper_close_target_rad)
        if torch.any(span <= 1.0e-4):
            raise ValueError("gripper open/close targets must have a non-zero span.")
        lower = torch.minimum(state.gripper_close_target_rad, state.gripper_open_target_rad) - 0.25 * span
        upper = torch.maximum(state.gripper_close_target_rad, state.gripper_open_target_rad) + 0.25 * span
        gripper_ready = torch.all(
            (state.gripper_position_rad >= lower) & (state.gripper_position_rad <= upper), dim=1
        )
        base_norm = torch.linalg.vector_norm(state.physical_base_command[:, :3], dim=1)
        return bool(
            (
                (state.tcp_pregrasp_distance_m < self.pregrasp_distance_max_m)
                & (state.opening_alignment >= self.alignment_min)
                & (state.approach_alignment >= self.alignment_min)
                & (base_norm <= self.base_still_norm_max)
                & gripper_ready
            ).item()
        )

    def _contact_masks(self, state: DepthAddStageObservation) -> tuple[bool, bool]:
        contact_force = torch.linalg.vector_norm(state.gripper_handle_forces_source_n, dim=-1)
        squeeze_y = state.gripper_handle_forces_source_n[:, :, 1]
        both_contact = bool(torch.all(contact_force > self.contact_force_threshold_n).item())
        valid_squeeze = bool(
            (
                torch.all(torch.abs(squeeze_y) > self.squeeze_force_min_n)
                & (squeeze_y[:, 0] * squeeze_y[:, 1] < 0.0)
            ).item()
        )
        return both_contact, valid_squeeze

    def _update_contact_streaks(self, both_contact: bool, valid_squeeze: bool) -> None:
        if self.stage == STAGE_GRASP:
            self.stage2_squeeze_streak = (
                self.stage2_squeeze_streak + 1 if both_contact and valid_squeeze else 0
            )
        elif self.stage in (STAGE_OPEN, STAGE_SWING):
            self.stage34_both_contact_streak = (
                self.stage34_both_contact_streak + 1 if both_contact else 0
            )

    def _update_stage4_release_gate(self, hinge_rad: torch.Tensor) -> None:
        if self.stage in (STAGE_SWING, STAGE_THROUGH):
            self.stage4_release_gate |= self._scalar(hinge_rad) >= self.stage4_release_hinge_threshold_rad

    def _update_stage5_hold_continuity(self, both_contact: bool) -> None:
        self.stage5_hold_continuity = self.stage5_hold_continuity and both_contact

    def _root_x_rel(self, state: DepthAddStageObservation) -> float:
        return self._scalar(state.root_position_m[:, 0] - state.env_origin_m[:, 0])

    def _scalar(self, value: torch.Tensor) -> float:
        return float(value.item())

    def _validate_observation(self, state: DepthAddStageObservation) -> None:
        for name, value, shape in (
            ("root_position_m", state.root_position_m, (1, 3)),
            ("env_origin_m", state.env_origin_m, (1, 3)),
            ("grasp_target_position_m", state.grasp_target_position_m, (1, 3)),
            ("arm_position_rad", state.arm_position_rad, (1, 6)),
            ("arm_default_position_rad", state.arm_default_position_rad, (1, 6)),
            ("physical_base_command", state.physical_base_command, (1, 5)),
            ("tcp_pregrasp_distance_m", state.tcp_pregrasp_distance_m, (1,)),
            ("opening_alignment", state.opening_alignment, (1,)),
            ("approach_alignment", state.approach_alignment, (1,)),
            ("gripper_position_rad", state.gripper_position_rad, (1, 2)),
            ("gripper_close_target_rad", state.gripper_close_target_rad, (1, 2)),
            ("gripper_open_target_rad", state.gripper_open_target_rad, (1, 2)),
            ("gripper_handle_forces_source_n", state.gripper_handle_forces_source_n, (1, 2, 3)),
            ("door_hinge_rad", state.door_hinge_rad, (1,)),
            ("handle_hinge_rad", state.handle_hinge_rad, (1,)),
        ):
            self._require_tensor(name, value, shape)

    def _require_tensor(self, name: str, value: torch.Tensor, shape: tuple[int, ...]) -> None:
        if (
            not torch.is_tensor(value)
            or tuple(value.shape) != shape
            or value.dtype != self.dtype
            or value.device != self.device
            or not torch.all(torch.isfinite(value))
        ):
            raise ValueError(
                f"{name} must be finite with shape {shape}, dtype={self.dtype}, device={self.device}."
            )
