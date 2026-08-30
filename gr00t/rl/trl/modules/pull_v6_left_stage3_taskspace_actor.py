"""Frozen H9 actor with a LEFT Stage3 task-space arm head."""

from __future__ import annotations

import torch
from torch import nn

from gr00t.rl.trl.modules.pull_v6_left_stage3_nonlinear_adapter_actor import (
    PullV6LeftStage3NonlinearAdapterActor,
)


class PullV6LeftStage3TaskspaceActor(PullV6LeftStage3NonlinearAdapterActor):
    """Train only a normalized handle-frame twist head on raw LEFT Stage3."""

    _ARM_ACTION_INDICES = (5, 6, 7, 8, 9, 10)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        with torch.random.fork_rng():
            torch.manual_seed(0)
            self.left_stage3_taskspace_head = nn.Sequential(
                nn.Linear(391, 16),
                nn.SiLU(),
                nn.Linear(16, len(self._ARM_ACTION_INDICES)),
            )
        nn.init.zeros_(self.left_stage3_taskspace_head[2].weight)
        nn.init.zeros_(self.left_stage3_taskspace_head[2].bias)

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
        features = torch.cat((current_obs, memory_out), dim=-1)
        if features.shape[-1] != 391:
            raise RuntimeError("LEFT task-space head requires 135-D obs + 256-D memory.")
        indices = self._ARM_ACTION_INDICES
        base = result[..., indices]
        replacement = self.left_stage3_taskspace_head(features)
        updated = result.clone()
        updated[..., indices] = torch.where(active, replacement, base)
        return updated
