"""Physics-step gait clock matching the A2_Base observation surface."""

from __future__ import annotations

import torch


class SensorClock:
    def __init__(
        self,
        *,
        batch_size: int,
        physics_dt: float,
        device: torch.device | str,
        dtype: torch.dtype,
        frequency_hz: float = 2.0,
        initial_phase: float = 0.0,
    ):
        self.physics_dt = physics_dt
        self.frequency_hz = frequency_hz
        self.phase = torch.full((batch_size,), initial_phase, device=device, dtype=dtype)
        self.standing_thresholds = torch.tensor((0.1, 0.1, 0.2), device=device, dtype=dtype)

    def reset(self, env_ids: torch.Tensor) -> None:
        if env_ids.dtype != torch.long or env_ids.device != self.phase.device:
            raise ValueError("env_ids must be a long tensor on the clock device.")
        self.phase[env_ids] = 0.0

    def advance(self, physical_base_command: torch.Tensor) -> torch.Tensor:
        if (
            tuple(physical_base_command.shape) != (self.phase.shape[0], 3)
            or physical_base_command.dtype != self.phase.dtype
            or physical_base_command.device != self.phase.device
        ):
            raise ValueError("Clock command must be (batch, 3) on the clock dtype and device.")
        standing = (physical_base_command.abs() < self.standing_thresholds).all(dim=1)
        moving = ~standing
        self.phase[moving] = torch.remainder(
            self.phase[moving] + self.physics_dt * self.frequency_hz, 1.0
        )
        self.phase[standing] = 0.0
        return self.signal()

    def signal(self) -> torch.Tensor:
        return torch.stack(
            (torch.sin(2.0 * torch.pi * self.phase), torch.cos(2.0 * torch.pi * self.phase)),
            dim=1,
        )
