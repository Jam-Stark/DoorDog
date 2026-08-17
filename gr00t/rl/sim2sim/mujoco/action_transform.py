"""A2+Piper high-level action, delta, and MuJoCo target transforms."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .names import A2PiperJointMap


A2_HIGH_LEVEL_ACTION_DIM = 12
A2_LEG_ACTION_DIM = 12
LOGICAL_ACTION_DIM = 19


class ArmDeltaAccumulator:
    """Production arm-delta surface: indices 5:11, scale 0.3, cap +/-15."""

    def __init__(self, *, batch_size: int, device: torch.device | str, dtype: torch.dtype):
        self.values = torch.zeros((batch_size, 6), device=device, dtype=dtype)

    def reset(self, env_ids: torch.Tensor) -> None:
        if env_ids.dtype != torch.long or env_ids.device != self.values.device:
            raise ValueError("env_ids must be a long tensor on the accumulator device.")
        self.values[env_ids] = 0.0

    def apply(self, high_level_action: torch.Tensor, stage: torch.Tensor) -> torch.Tensor:
        if (
            tuple(high_level_action.shape) != (self.values.shape[0], A2_HIGH_LEVEL_ACTION_DIM)
            or high_level_action.dtype != self.values.dtype
            or high_level_action.device != self.values.device
        ):
            raise ValueError("High-level action must be (batch, 12) on the accumulator dtype and device.")
        if tuple(stage.shape) != (self.values.shape[0],) or stage.device != self.values.device:
            raise ValueError("stage must be a (batch,) tensor on the accumulator device.")
        self.values += 0.3 * high_level_action[:, 5:11]
        self.values.clamp_(-15.0, 15.0)
        self.values[stage == 0] = 0.0
        result = high_level_action.clone()
        result[:, 5:11] = self.values
        return result


@dataclass(frozen=True)
class A2ActionTransformResult:
    high_level_action: torch.Tensor
    logical_action: torch.Tensor
    simulator_raw_action: torch.Tensor
    position_target: torch.Tensor


class A2ActionTransform:
    """Transforms `[base5, arm6, grip1] + policy-leg12` into 20 joint targets."""

    def __init__(self, joint_map: A2PiperJointMap, *, action_scale: float = 0.25):
        self.joint_map = joint_map
        self.action_scale = action_scale

    def compose(
        self,
        *,
        high_level_action: torch.Tensor,
        policy_leg_action: torch.Tensor,
        default_dof_pos: torch.Tensor,
    ) -> A2ActionTransformResult:
        batch = high_level_action.shape[0]
        width = len(self.joint_map.sim_joint_names)
        if high_level_action.ndim != 2 or tuple(high_level_action.shape) != (batch, 12):
            raise ValueError("high_level_action must have shape (batch, 12).")
        for name, value, shape in (
            ("policy_leg_action", policy_leg_action, (batch, 12)),
            ("default_dof_pos", default_dof_pos, (batch, width)),
        ):
            if tuple(value.shape) != shape or value.dtype != high_level_action.dtype or value.device != high_level_action.device:
                raise ValueError(f"{name} must match action dtype/device and have shape {shape}.")
        if self.joint_map.policy_leg_indices.device != high_level_action.device:
            raise ValueError("Action tensor and joint map must share a device.")

        logical_action = torch.cat(
            (policy_leg_action, high_level_action[:, 5:11], high_level_action[:, 11:12]), dim=1
        )
        simulator_raw_action = torch.zeros_like(default_dof_pos)
        simulator_raw_action[:, self.joint_map.policy_leg_indices] = policy_leg_action
        simulator_raw_action[:, self.joint_map.arm_indices] = high_level_action[:, 5:11]
        grip_targets = torch.where(
            high_level_action[:, 11:12] > 0.0,
            torch.tensor((0.035, -0.035), dtype=high_level_action.dtype, device=high_level_action.device),
            torch.zeros((2,), dtype=high_level_action.dtype, device=high_level_action.device),
        )
        simulator_raw_action[:, self.joint_map.gripper_indices] = (
            grip_targets - default_dof_pos[:, self.joint_map.gripper_indices]
        ) / self.action_scale
        position_target = default_dof_pos + self.action_scale * simulator_raw_action
        return A2ActionTransformResult(
            high_level_action=high_level_action,
            logical_action=logical_action,
            simulator_raw_action=simulator_raw_action,
            position_target=position_target,
        )
