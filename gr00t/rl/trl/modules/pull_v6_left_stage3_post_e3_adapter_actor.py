"""Frozen H9 actor with an independent post-E3 LEFT Stage3 adapter."""

from __future__ import annotations

import torch
from torch import nn

from gr00t.rl.trl.modules.pull_v6_left_stage3_nonlinear_adapter_actor import (
    PullV6LeftStage3NonlinearAdapterActor,
)


class PullV6LeftStage3PostE3AdapterActor(PullV6LeftStage3NonlinearAdapterActor):
    """Train only a zero-final recurrent adapter after natural LEFT E3."""

    _ADAPTER_ACTION_INDICES = (0, 1, 2, 5, 6, 7, 8, 9, 10)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        # Keep the parent policy's stochastic action stream unchanged before
        # this gate activates; checkpoint loading happens after construction.
        with torch.random.fork_rng():
            torch.manual_seed(0)
            self.left_stage3_post_e3_adapter = nn.Sequential(
                nn.Linear(391, 16),
                nn.SiLU(),
                nn.Linear(16, len(self._ADAPTER_ACTION_INDICES)),
            )
        nn.init.zeros_(self.left_stage3_post_e3_adapter[2].weight)
        nn.init.zeros_(self.left_stage3_post_e3_adapter[2].bias)

    def _mean_from_memory(
        self,
        memory_out: torch.Tensor,
        current_obs: torch.Tensor,
        release_mode: torch.Tensor,
        post_release_control: torch.Tensor,
        additional_context=None,
        **kwargs,
    ) -> torch.Tensor:
        current_obs, gate = additional_context
        result = super()._mean_from_memory(
            memory_out,
            current_obs,
            release_mode,
            post_release_control,
            (current_obs, gate),
            **kwargs,
        )
        left = (gate[..., 5] == 1.0) & (gate[..., 6] == 0.0)
        stage3 = gate[..., 11] == 1.0
        active = (left & stage3 & (gate[..., 7] == 1.0)).unsqueeze(-1)
        indices = self._ADAPTER_ACTION_INDICES
        base = result[..., indices]
        features = torch.cat((current_obs, memory_out), dim=-1)
        if features.shape[-1] != 391:
            raise RuntimeError("LEFT post-E3 adapter requires 135-D obs + 256-D memory.")
        candidate = base + self.left_stage3_post_e3_adapter(features)
        updated = result.clone()
        updated[..., indices] = torch.where(active, candidate, base)
        return updated
