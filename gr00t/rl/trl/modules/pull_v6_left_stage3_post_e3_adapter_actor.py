"""Frozen H9 actor with an independent post-E3 LEFT Stage3 adapter."""

from __future__ import annotations

import torch
from torch import nn

from gr00t.rl.trl.modules.pull_v6_left_stage3_nonlinear_adapter_actor import (
    PullV6LeftStage3NonlinearAdapterActor,
)
from gr00t.rl.trl.utils.rl import unsplit_trajectories


class PullV6LeftStage3PostE3AdapterActor(PullV6LeftStage3NonlinearAdapterActor):
    """Train only a zero-final recurrent adapter after natural LEFT E3."""

    _ADAPTER_ACTION_INDICES = (0, 1, 2, 5, 6, 7, 8, 9, 10)
    _E3_GATE_KEY = "left_stage3_post_e3_gate_obs"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        self.left_stage3_post_e3_adapter = nn.Sequential(
            nn.Linear(391, 16),
            nn.SiLU(),
            nn.Linear(16, len(self._ADAPTER_ACTION_INDICES)),
        )
        nn.init.zeros_(self.left_stage3_post_e3_adapter[2].weight)
        nn.init.zeros_(self.left_stage3_post_e3_adapter[2].bias)

    def _additional_post_release_context(
        self, obs_dict, input_obs: torch.Tensor, masks=None, original_dones=None
    ):
        current_obs, gate = super()._additional_post_release_context(
            obs_dict,
            input_obs,
            masks=masks,
            original_dones=original_dones,
        )
        e3_gate = obs_dict[self._E3_GATE_KEY]
        if e3_gate.ndim == 3 and masks is not None and original_dones is not None:
            e3_gate = unsplit_trajectories(e3_gate, masks, original_dones)
        if e3_gate.shape[-1] != 1:
            raise RuntimeError(
                "LEFT post-E3 Stage3 gate must be one E3-latched value."
            )
        return current_obs, gate, e3_gate

    def _mean_from_memory(
        self,
        memory_out: torch.Tensor,
        current_obs: torch.Tensor,
        release_mode: torch.Tensor,
        post_release_control: torch.Tensor,
        additional_context=None,
        **kwargs,
    ) -> torch.Tensor:
        current_obs, gate, e3_gate = additional_context
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
        active = (left & stage3 & (e3_gate[..., 0] == 1.0)).unsqueeze(-1)
        indices = self._ADAPTER_ACTION_INDICES
        base = result[..., indices]
        features = torch.cat((current_obs, memory_out), dim=-1)
        if features.shape[-1] != 391:
            raise RuntimeError("LEFT post-E3 adapter requires 135-D obs + 256-D memory.")
        candidate = base + self.left_stage3_post_e3_adapter(features)
        updated = result.clone()
        updated[..., indices] = torch.where(active, candidate, base)
        return updated
