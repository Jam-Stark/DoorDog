"""Exact 54D A2_Base frame and 30-frame history construction."""

from __future__ import annotations

import torch

from .names import A2PiperJointMap


A2_BASE_FRAME_DIM = 54
A2_BASE_HISTORY_LENGTH = 30
_COMMAND_MULTIPLIERS = (2.0, 2.0, 0.25, 1.0, 1.0)


def _require_tensor(name: str, value: torch.Tensor, width: int, batch: int, ref: torch.Tensor) -> None:
    if value.ndim != 2 or tuple(value.shape) != (batch, width):
        raise ValueError(f"{name} must have shape ({batch}, {width}); got {tuple(value.shape)}.")
    if value.dtype != ref.dtype or value.device != ref.device:
        raise ValueError(f"{name} must share projected_gravity dtype and device.")


class A2BaseFrameBuilder:
    """Build the frozen A2_Base dog frame in policy-leg order."""

    def __init__(self, joint_map: A2PiperJointMap):
        self.joint_map = joint_map

    def build(
        self,
        *,
        projected_gravity: torch.Tensor,
        dof_pos: torch.Tensor,
        default_dof_pos: torch.Tensor,
        dof_vel: torch.Tensor,
        previous_leg_action: torch.Tensor,
        physical_base_command: torch.Tensor,
        base_roll_pitch: torch.Tensor,
        gait_clock: torch.Tensor,
    ) -> torch.Tensor:
        if projected_gravity.ndim != 2 or projected_gravity.shape[1] != 3:
            raise ValueError(
                "projected_gravity must have shape (batch, 3); "
                f"got {tuple(projected_gravity.shape)}."
            )
        batch = projected_gravity.shape[0]
        width = len(self.joint_map.sim_joint_names)
        _require_tensor("dof_pos", dof_pos, width, batch, projected_gravity)
        _require_tensor("default_dof_pos", default_dof_pos, width, batch, projected_gravity)
        _require_tensor("dof_vel", dof_vel, width, batch, projected_gravity)
        _require_tensor("previous_leg_action", previous_leg_action, 12, batch, projected_gravity)
        _require_tensor("physical_base_command", physical_base_command, 5, batch, projected_gravity)
        _require_tensor("base_roll_pitch", base_roll_pitch, 2, batch, projected_gravity)
        _require_tensor("gait_clock", gait_clock, 2, batch, projected_gravity)

        frame = torch.zeros(
            (batch, A2_BASE_FRAME_DIM), dtype=projected_gravity.dtype, device=projected_gravity.device
        )
        frame[:, 0:3] = projected_gravity
        frame[:, 3:15] = self.joint_map.gather_policy_legs(dof_pos - default_dof_pos)
        frame[:, 15:27] = 0.05 * self.joint_map.gather_policy_legs(dof_vel)
        frame[:, 27:39] = previous_leg_action
        command_multiplier = torch.tensor(
            _COMMAND_MULTIPLIERS, dtype=projected_gravity.dtype, device=projected_gravity.device
        )
        frame[:, 39:44] = physical_base_command * command_multiplier
        frame[:, 50:52] = base_roll_pitch
        frame[:, 52:54] = gait_clock
        return frame


class A2BaseHistory:
    """Frame-major `[obs(t-29), ..., obs(t)]` history state."""

    def __init__(self, *, batch_size: int, device: torch.device | str, dtype: torch.dtype):
        self.history = torch.zeros(
            (batch_size, A2_BASE_HISTORY_LENGTH, A2_BASE_FRAME_DIM), device=device, dtype=dtype
        )
        self.initialized = torch.zeros((batch_size,), device=device, dtype=torch.bool)

    def reset(self, env_ids: torch.Tensor) -> None:
        if env_ids.dtype != torch.long or env_ids.device != self.history.device:
            raise ValueError("env_ids must be a long tensor on the history device.")
        self.history[env_ids] = 0.0
        self.initialized[env_ids] = False

    def append(self, frame: torch.Tensor) -> torch.Tensor:
        expected = (self.history.shape[0], A2_BASE_FRAME_DIM)
        if tuple(frame.shape) != expected or frame.dtype != self.history.dtype or frame.device != self.history.device:
            raise ValueError(
                "A2_Base history frame must match history batch, frame dimension, dtype, and device; "
                f"got shape={tuple(frame.shape)}, dtype={frame.dtype}, device={frame.device}."
            )
        initialized = self.initialized
        if initialized.any():
            self.history[initialized, :-1] = self.history[initialized, 1:].clone()
            self.history[initialized, -1] = frame[initialized]
        uninitialized = ~initialized
        if uninitialized.any():
            self.history[uninitialized] = frame[uninitialized, None, :].expand(
                -1, A2_BASE_HISTORY_LENGTH, -1
            )
            self.initialized[uninitialized] = True
        return self.history.reshape(self.history.shape[0], -1)
