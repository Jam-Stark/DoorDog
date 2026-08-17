"""Per-physics-step, torque-clipped external position PD."""

from __future__ import annotations

import torch


class ExternalPdController:
    def __init__(self, *, stiffness: torch.Tensor, damping: torch.Tensor, torque_limit: torch.Tensor):
        if stiffness.ndim != 1 or damping.shape != stiffness.shape or torque_limit.shape != stiffness.shape:
            raise ValueError("PD gains and torque limits must be equally shaped 1D tensors.")
        if stiffness.dtype != damping.dtype or stiffness.dtype != torque_limit.dtype:
            raise ValueError("PD gains and torque limits must share a dtype.")
        if stiffness.device != damping.device or stiffness.device != torque_limit.device:
            raise ValueError("PD gains and torque limits must share a device.")
        self.stiffness = stiffness
        self.damping = damping
        self.torque_limit = torque_limit

    def compute(self, *, position_target: torch.Tensor, position: torch.Tensor, velocity: torch.Tensor) -> torch.Tensor:
        expected = (position_target.shape[0], self.stiffness.numel())
        for name, value in (("position_target", position_target), ("position", position), ("velocity", velocity)):
            if tuple(value.shape) != expected or value.dtype != self.stiffness.dtype or value.device != self.stiffness.device:
                raise ValueError(f"{name} must have shape {expected} on the controller dtype and device.")
        torque = self.stiffness[None, :] * (position_target - position) - self.damping[None, :] * velocity
        return torch.clamp(torque, -self.torque_limit[None, :], self.torque_limit[None, :])
