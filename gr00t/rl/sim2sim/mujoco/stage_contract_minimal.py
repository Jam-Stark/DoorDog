"""Deployable subset of the production A2 door stage contract.

Only stage predicates that alter the normal Student action path belong here.
The production environment gates the six accumulated Piper deltas in stage 0;
later stages do not rewrite the normal base, arm, leg, or gripper actions.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


STAGE_CONTRACT_NAME = "STAGE_CONTRACT_MINIMAL"
STAGE_WALK_TO_DOOR = 0
STAGE_PREGRASP = 1


@dataclass(frozen=True)
class Stage0ObservableState:
    root_position_m: torch.Tensor
    grasp_target_position_m: torch.Tensor
    arm_position_rad: torch.Tensor
    arm_default_position_rad: torch.Tensor
    physical_base_command: torch.Tensor


@dataclass(frozen=True)
class StageActionResult:
    raw_high_level_action: torch.Tensor
    effective_high_level_action: torch.Tensor
    raw_arm_delta_echo: torch.Tensor
    accumulated_arm_delta: torch.Tensor
    stage_used_for_action: int


class StageContractMinimal:
    """One-environment stage tracker matching the deployable production path.

    Stage advancement is evaluated after the action/physics/observation cycle,
    as in ``StagedTaskBase._post_compute_observations_callback``.  Therefore the
    action that reaches the staging band still uses stage 0; arm delta becomes
    effective on the following policy step.
    """

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
        delta_scale: float = 0.3,
        delta_clip: float = 15.0,
    ):
        self.dtype = dtype
        self.device = torch.device(device)
        self.staging_x_min_m = float(staging_x_min_m)
        self.staging_x_max_m = float(staging_x_max_m)
        self.staging_y_tolerance_m = float(staging_y_tolerance_m)
        self.arm_default_max_deviation_rad = float(arm_default_max_deviation_rad)
        self.base_still_norm_max = float(base_still_norm_max)
        self.delta_scale = float(delta_scale)
        self.delta_clip = float(delta_clip)
        self.stage = STAGE_WALK_TO_DOOR
        self.accumulated_arm_delta = torch.zeros((1, 6), dtype=dtype, device=self.device)

    def reset(self) -> None:
        self.stage = STAGE_WALK_TO_DOOR
        self.accumulated_arm_delta.zero_()

    def apply_high_level_action(self, raw_action: torch.Tensor) -> StageActionResult:
        if tuple(raw_action.shape) != (1, 12):
            raise ValueError("STAGE_CONTRACT_MINIMAL requires high-level action shape (1, 12).")
        if raw_action.dtype != self.dtype or raw_action.device != self.device:
            raise ValueError("STAGE_CONTRACT_MINIMAL action dtype/device mismatch.")
        stage_used = self.stage
        raw_delta = raw_action[:, 5:11].clone()
        self.accumulated_arm_delta += self.delta_scale * raw_delta
        self.accumulated_arm_delta.clamp_(-self.delta_clip, self.delta_clip)
        if stage_used == STAGE_WALK_TO_DOOR:
            self.accumulated_arm_delta.zero_()
        effective = raw_action.clone()
        effective[:, 5:11] = self.accumulated_arm_delta
        return StageActionResult(
            raw_high_level_action=raw_action.clone(),
            effective_high_level_action=effective,
            raw_arm_delta_echo=raw_delta,
            accumulated_arm_delta=self.accumulated_arm_delta.clone(),
            stage_used_for_action=stage_used,
        )

    def stage0_to_stage1_predicate(self, state: Stage0ObservableState) -> bool:
        for name, value, shape in (
            ("root_position_m", state.root_position_m, (1, 3)),
            ("grasp_target_position_m", state.grasp_target_position_m, (1, 3)),
            ("arm_position_rad", state.arm_position_rad, (1, 6)),
            ("arm_default_position_rad", state.arm_default_position_rad, (1, 6)),
            ("physical_base_command", state.physical_base_command, (1, 5)),
        ):
            if tuple(value.shape) != shape or value.dtype != self.dtype or value.device != self.device:
                raise ValueError(f"{name} must have shape {shape} on tracker dtype/device.")
        dx = state.grasp_target_position_m[:, 0] - state.root_position_m[:, 0]
        dy = state.root_position_m[:, 1] - state.grasp_target_position_m[:, 1]
        max_arm_deviation = torch.max(
            torch.abs(state.arm_position_rad - state.arm_default_position_rad), dim=1
        ).values
        base_norm = torch.linalg.vector_norm(state.physical_base_command[:, :3], dim=1)
        predicate = (
            (dx >= self.staging_x_min_m)
            & (dx <= self.staging_x_max_m)
            & (torch.abs(dy) < self.staging_y_tolerance_m)
            & (max_arm_deviation < self.arm_default_max_deviation_rad)
            & (base_norm <= self.base_still_norm_max)
        )
        return bool(predicate.item())

    def observe_after_step(self, state: Stage0ObservableState) -> bool:
        if self.stage != STAGE_WALK_TO_DOOR:
            return False
        if not self.stage0_to_stage1_predicate(state):
            return False
        self.stage = STAGE_PREGRASP
        return True

    @staticmethod
    def gripper_target(raw_gripper_primitive: torch.Tensor) -> torch.Tensor:
        """Production A2 primitive: positive opens, zero/negative closes, all stages."""

        if tuple(raw_gripper_primitive.shape) != (1, 1):
            raise ValueError("gripper primitive must have shape (1, 1).")
        open_target = torch.tensor(
            (0.035, -0.035),
            dtype=raw_gripper_primitive.dtype,
            device=raw_gripper_primitive.device,
        ).unsqueeze(0)
        return torch.where(raw_gripper_primitive > 0.0, open_target, torch.zeros_like(open_target))


STAGE_ACTION_BRANCH_AUDIT = {
    "normal_student_deploy_path": {
        "stage0_arm_delta_gate": "IMPLEMENTED_EXACTLY",
        "stage0_to_stage1": "IMPLEMENTED_FROM_OBSERVABLE_STATE",
        "stage1_plus_base_action_override": "NONE",
        "stage1_plus_arm_action_override": "NONE",
        "stage1_plus_leg_action_override": "NONE",
        "stage1_plus_gripper_action_override": "NONE",
        "gripper_primitive_all_stages": "RAW_GT_ZERO_OPEN_ELSE_CLOSE",
    },
    "excluded_non_deploy_paths": [
        "teacher-only zero_vel branch (READY config disabled)",
        "teacher-only zero_finger branch (READY config disabled)",
        "evaluation oracle/intervention actions",
        "reward, termination, and staged-reset-only branches",
    ],
}
