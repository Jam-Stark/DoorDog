"""Frozen H5 actor with a nonlinear LEFT Stage3 recurrent-state adapter."""

from __future__ import annotations

import torch
from torch import nn

from gr00t.rl.trl.modules.pull_v6_left_stage3_obs_residual_actor import (
    PullV6LeftStage3ObsResidualActor,
)


class PullV6LeftStage3NonlinearAdapterActor(PullV6LeftStage3ObsResidualActor):
    """Train a zero-final nonlinear base-planar+arm adapter across LEFT Stage3."""

    _ADAPTER_ACTION_INDICES = (0, 1, 2, 5, 6, 7, 8, 9, 10)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        self.left_stage3_nonlinear_adapter = nn.Sequential(
            nn.Linear(391, 16),
            nn.SiLU(),
            nn.Linear(16, len(self._ADAPTER_ACTION_INDICES)),
        )
        nn.init.zeros_(self.left_stage3_nonlinear_adapter[2].weight)
        nn.init.zeros_(self.left_stage3_nonlinear_adapter[2].bias)

    def _mean_from_memory(
        self,
        memory_out: torch.Tensor,
        current_obs: torch.Tensor,
        release_mode: torch.Tensor,
        post_release_control: torch.Tensor,
        additional_context=None,
        **kwargs,
    ) -> torch.Tensor:
        result = super()._mean_from_memory(
            memory_out,
            current_obs,
            release_mode,
            post_release_control,
            additional_context,
            **kwargs,
        )
        _, gate = additional_context
        left = (gate[..., 5] == 1.0) & (gate[..., 6] == 0.0)
        stage3 = gate[..., 11] == 1.0
        active = (left & stage3).unsqueeze(-1)
        indices = self._ADAPTER_ACTION_INDICES
        base = result[..., indices]
        features = torch.cat((current_obs, memory_out), dim=-1)
        if features.shape[-1] != 391:
            raise RuntimeError("LEFT nonlinear adapter requires 135-D obs + 256-D memory.")
        candidate = base + self.left_stage3_nonlinear_adapter(features)
        updated = result.clone()
        updated[..., indices] = torch.where(active, candidate, base)
        return updated
