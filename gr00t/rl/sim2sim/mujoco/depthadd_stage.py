"""Faithful single-environment DepthADD v3 six-stage tracker.

The MuJoCo runner owns state collection and the four 200 Hz physics steps.  It
must call :meth:`apply_high_level_action` before those physics steps, then pass
the resulting post-physics contact and pose data to :meth:`observe_after_step`.
This keeps the policy control order explicit:

``old-stage action -> four physics steps -> contact/pose -> overtime -> transition``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

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
    goal_reached: bool
    goal_event: bool
    time_since_goal_control_steps: int
    terminal_reason: str | None
    stage4_release_gate: bool
    stage5_hold_continuity: bool
    stage2_reason_bits: dict[str, bool | float | int]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready episode receipt for the MuJoCo runner."""

        return {
            "stage": self.stage,
            "total_control_steps": self.total_control_steps,
            "time_in_stage_budget": self.time_in_stage_budget,
            "stage_control_steps": list(self.stage_control_steps),
            "stage_times_s": list(self.stage_times_s),
            "transition_steps": list(self.transition_steps),
            "goal_reached": self.goal_reached,
            "goal_event": self.goal_event,
            "time_since_goal_control_steps": self.time_since_goal_control_steps,
            "terminal_reason": self.terminal_reason,
            "stage4_release_gate": self.stage4_release_gate,
            "stage5_hold_continuity": self.stage5_hold_continuity,
            "stage2_reason_bits": self.stage2_reason_bits,
        }


class DepthAddStageTracker:
    """Stateful faithful tracker for DepthADD v3's six-stage task contract."""

    @classmethod
    def from_task_config(
        cls,
        task_config: Mapping[str, object],
        *,
        dtype: torch.dtype = torch.float32,
        device: torch.device | str = "cpu",
    ) -> "DepthAddStageTracker":
        """Build the evaluator from the resolved production task surface."""

        if task_config["a2_grasp_gate_mode"] != "control_streak":
            raise NotImplementedError("DepthAddStageTracker implements only control_streak grasp gating")
        return cls(
            dtype=dtype,
            device=device,
            staging_x_min_m=float(task_config["a2_stage0_staging_x_min"]),
            staging_x_max_m=float(task_config["a2_stage0_staging_x_max"]),
            staging_y_tolerance_m=float(task_config["a2_stage0_staging_y_tol"]),
            arm_default_max_deviation_rad=float(
                task_config["a2_stage0_arm_default_max_deviation"]
            ),
            contact_force_threshold_n=float(task_config["a2_stage2_contact_force_threshold"]),
            squeeze_force_min_n=float(task_config["a2_stage2_squeeze_force_min"]),
            squeeze_force_max_n=float(task_config["a2_stage2_squeeze_force_max"]),
            over_force_threshold_n=float(task_config["a2_stage2_over_force_threshold"]),
            completion_close_gate_required=bool(
                task_config["a2_stage2_completion_close_gate_required"]
            ),
            close_command_threshold=float(
                task_config["a2_stage2_completion_gripper_close_command_threshold"]
            ),
            close_progress_min=float(
                task_config["a2_stage2_completion_gripper_close_progress_min"]
            ),
            grasp_streak_control_steps=int(task_config["a2_grasp_streak_control_steps"]),
            stage3_to4_requires_grasp_streak=bool(
                task_config["a2_stage3_to4_requires_grasp_streak"]
            ),
            stage3_to4_hinge_threshold_rad=float(
                task_config["a2_stage3_to4_door_hinge_threshold"]
            ),
            stage4_release_hinge_threshold_rad=float(
                task_config["a2_stage4_release_hinge_threshold"]
            ),
            stage4_to5_hinge_threshold_rad=float(
                task_config["a2_stage4_to5_door_hinge_threshold"]
            ),
            reset_on_complete=bool(task_config["reset_on_complete"]),
            reset_on_complete_delay_control_steps=int(task_config["reset_on_complete_delay"]),
            max_stage_time_control_steps=tuple(
                int(value) for value in task_config["max_stage_time"]  # type: ignore[union-attr]
            ),
            reset_on_overtime=bool(task_config["reset_on_overtime"]),
        )

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
        squeeze_force_max_n: float = 30.0,
        over_force_threshold_n: float = 55.0,
        completion_close_gate_required: bool = False,
        close_command_threshold: float = -0.2,
        close_progress_min: float = 0.45,
        grasp_streak_control_steps: int = 5,
        stage3_to4_requires_grasp_streak: bool = True,
        stage3_to4_hinge_threshold_rad: float = 0.25,
        stage4_release_hinge_threshold_rad: float = 1.6,
        stage4_to5_hinge_threshold_rad: float = 1.25,
        handle_up_threshold_rad: float = 0.2,
        stage5_complete_root_x_m: float = 1.5,
        reset_on_complete: bool = True,
        reset_on_complete_delay_control_steps: int = 50,
        max_stage_time_control_steps: tuple[int, int, int, int, int, int] = (
            MAX_STAGE_TIME_CONTROL_STEPS
        ),
        delta_scale: float = 0.3,
        delta_clip: float = 15.0,
        reset_on_overtime: bool = True,
    ):
        if not isinstance(reset_on_overtime, bool):
            raise ValueError("reset_on_overtime must be bool.")
        if not isinstance(reset_on_complete, bool):
            raise ValueError("reset_on_complete must be bool.")
        if not isinstance(completion_close_gate_required, bool):
            raise ValueError("completion_close_gate_required must be bool.")
        if completion_close_gate_required:
            raise NotImplementedError(
                "the exact axis-wise Stage2 close-gate state is not present in "
                "DepthAddStageObservation; refusing an approximate hard completion gate"
            )
        if not isinstance(stage3_to4_requires_grasp_streak, bool):
            raise ValueError("stage3_to4_requires_grasp_streak must be bool.")
        if (
            not isinstance(reset_on_complete_delay_control_steps, int)
            or reset_on_complete_delay_control_steps < 0
        ):
            raise ValueError("reset_on_complete_delay_control_steps must be a non-negative integer.")
        if not isinstance(grasp_streak_control_steps, int) or grasp_streak_control_steps <= 0:
            raise ValueError("grasp_streak_control_steps must be a positive integer.")
        if (
            len(max_stage_time_control_steps) != 6
            or any(not isinstance(value, int) or value <= 0 for value in max_stage_time_control_steps)
        ):
            raise ValueError("max_stage_time_control_steps must contain six positive integers.")
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
        self.squeeze_force_max_n = float(squeeze_force_max_n)
        self.over_force_threshold_n = float(over_force_threshold_n)
        self.completion_close_gate_required = completion_close_gate_required
        self.close_command_threshold = float(close_command_threshold)
        self.close_progress_min = float(close_progress_min)
        self.grasp_streak_control_steps = grasp_streak_control_steps
        self.stage3_to4_requires_grasp_streak = stage3_to4_requires_grasp_streak
        self.stage3_to4_hinge_threshold_rad = float(stage3_to4_hinge_threshold_rad)
        self.stage4_release_hinge_threshold_rad = float(stage4_release_hinge_threshold_rad)
        self.stage4_to5_hinge_threshold_rad = float(stage4_to5_hinge_threshold_rad)
        self.handle_up_threshold_rad = float(handle_up_threshold_rad)
        self.stage5_complete_root_x_m = float(stage5_complete_root_x_m)
        self.reset_on_complete = reset_on_complete
        self.reset_on_complete_delay_control_steps = reset_on_complete_delay_control_steps
        self.max_stage_time_control_steps = max_stage_time_control_steps
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
        self.goal_reached = False
        self.goal_event = False
        self.time_since_goal_control_steps = 0
        self.terminal_reason: str | None = None
        self.stage2_squeeze_streak = 0
        self.stage34_both_contact_streak = 0
        self.stage4_release_gate = False
        self.stage5_hold_continuity = False
        self.stage2_reason_bits: dict[str, bool | float | int] = {}
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
        stage2_current = self._stage2_completion_current(
            observation, action, both_contact=both_contact, valid_squeeze=valid_squeeze
        )
        self._update_contact_streaks(both_contact, stage2_current)
        self.stage2_reason_bits = {
            **stage2_current,
            "streak": self.stage2_squeeze_streak,
            "streak_ge_required": self.stage2_squeeze_streak >= self.grasp_streak_control_steps,
        }
        self._update_stage4_release_gate(observation.door_hinge_rad)
        complete = (
            self.stage == STAGE_THROUGH
            and self._root_x_rel(observation) > self.stage5_complete_root_x_m
        )
        advance = self.stage < STAGE_THROUGH and self._advance_predicate(observation, both_contact)
        if self.stage == STAGE_THROUGH:
            self._update_stage5_hold_continuity(both_contact)

        prior_stage = self.stage
        prior_time_since_goal = self.time_since_goal_control_steps
        self.goal_event = complete and not self.goal_reached
        self.goal_reached |= complete
        self.total_control_steps += 1
        self.stage_control_steps[prior_stage] += 1
        self.time_in_stage_budget += 1
        is_overtime = (
            self.time_in_stage_budget >= self.max_stage_time_control_steps[prior_stage]
        )
        reset_after_complete = complete and self.reset_on_complete and (
            self.reset_on_complete_delay_control_steps == 0
            or prior_time_since_goal >= self.reset_on_complete_delay_control_steps
        )
        if reset_after_complete:
            self.terminal_reason = "complete"
        elif is_overtime and self.reset_on_overtime:
            self.terminal_reason = "stage_overtime"
        elif advance:
            self.time_in_stage_budget -= self.max_stage_time_control_steps[prior_stage]
            self.stage += 1
            self.transition_steps[prior_stage] = self.total_control_steps
            if prior_stage == STAGE_SWING:
                self.stage5_hold_continuity = (
                    self.stage34_both_contact_streak >= self.grasp_streak_control_steps
                )
        if prior_time_since_goal > 0:
            self.time_since_goal_control_steps = prior_time_since_goal + 1
        elif complete:
            self.time_since_goal_control_steps = 1
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
            goal_reached=self.goal_reached,
            goal_event=self.goal_event,
            time_since_goal_control_steps=self.time_since_goal_control_steps,
            terminal_reason=self.terminal_reason,
            stage4_release_gate=self.stage4_release_gate,
            stage5_hold_continuity=self.stage5_hold_continuity,
            stage2_reason_bits=dict(self.stage2_reason_bits),
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
                and (
                    not self.stage3_to4_requires_grasp_streak
                    or self.stage34_both_contact_streak >= self.grasp_streak_control_steps
                )
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

    def _stage2_completion_current(
        self,
        state: DepthAddStageObservation,
        action: DepthAddStageAction,
        *,
        both_contact: bool,
        valid_squeeze: bool,
    ) -> dict[str, bool | float]:
        span = torch.abs(state.gripper_open_target_rad - state.gripper_close_target_rad)
        progress = torch.abs(state.gripper_open_target_rad - state.gripper_position_rad) / span
        progress_min = float(torch.min(progress).item())
        forces = torch.linalg.vector_norm(state.gripper_handle_forces_source_n, dim=-1)
        squeeze_y = state.gripper_handle_forces_source_n[:, :, 1]
        squeeze_window = bool(
            (
                torch.all(torch.abs(squeeze_y) >= self.squeeze_force_min_n)
                & torch.all(torch.abs(squeeze_y) <= self.squeeze_force_max_n)
            ).item()
        )
        opposite = bool((squeeze_y[:, 0] * squeeze_y[:, 1] < 0.0).item())
        over_force = bool(torch.any(forces > self.over_force_threshold_n).item())
        close_command = bool(
            (action.effective_high_level_action[:, 11] < self.close_command_threshold).item()
        )
        progress_complete = progress_min >= self.close_progress_min
        base_completion_current = (
            self.stage == STAGE_GRASP
            and both_contact
            and valid_squeeze
        )
        completion_current = base_completion_current
        if self.completion_close_gate_required:
            completion_current &= close_command and progress_complete
        return {
            "stage2_active": self.stage == STAGE_GRASP,
            "completion_close_gate_required": self.completion_close_gate_required,
            "close_command": close_command,
            "close_progress_min": progress_min,
            "close_progress_complete": progress_complete,
            "left_contact": bool(forces[0, 0] > self.contact_force_threshold_n),
            "right_contact": bool(forces[0, 1] > self.contact_force_threshold_n),
            "both_contact": both_contact,
            "squeeze_window": squeeze_window,
            "opposite_squeeze": opposite,
            "over_force": over_force,
            "base_completion_current": base_completion_current,
            "completion_current": completion_current,
        }

    def _update_contact_streaks(
        self, both_contact: bool, stage2_current: Mapping[str, bool | float]
    ) -> None:
        if self.stage == STAGE_GRASP:
            self.stage2_squeeze_streak = (
                self.stage2_squeeze_streak + 1
                if bool(stage2_current["completion_current"])
                else 0
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
