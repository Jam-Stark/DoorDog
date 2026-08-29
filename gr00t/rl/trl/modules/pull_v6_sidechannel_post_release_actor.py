"""Bit-identical 135D carrier plus a D25-gated two-value D-head side channel."""

from __future__ import annotations

import torch
from torch import nn

from gr00t.rl.trl.modules.pull_v6_post_release_obs_override_actor import (
    PullV6PostReleaseObsOverrideActor,
)
from gr00t.rl.trl.utils.rl import unsplit_trajectories


class PullV6SidechannelPostReleaseActor(PullV6PostReleaseObsOverrideActor):
    """Preserve the immediate-D head and switch to a trainable side-channel head at D25."""

    _DYNAMICS_KEY = "v6_dynamics_obs"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        self.post_release_late_override = nn.Linear(137, len(self._D_ACTION_INDICES))
        nn.init.zeros_(self.post_release_late_override.weight)
        nn.init.zeros_(self.post_release_late_override.bias)

    def _dynamics(self, obs_dict, masks=None, original_dones=None) -> torch.Tensor:
        dynamics = obs_dict[self._DYNAMICS_KEY]
        if dynamics.ndim == 3 and masks is not None and original_dones is not None:
            dynamics = unsplit_trajectories(dynamics, masks, original_dones)
        return dynamics

    def _additional_post_release_context(
        self, obs_dict, input_obs: torch.Tensor, masks=None, original_dones=None
    ) -> torch.Tensor:
        carrier_obs = self._current_obs(input_obs, masks=masks, original_dones=original_dones)
        dynamics = self._dynamics(obs_dict, masks=masks, original_dones=original_dones)
        return torch.cat((carrier_obs, dynamics), dim=-1)

    def _apply_additional_post_release_override(
        self, mean: torch.Tensor, context: torch.Tensor
    ) -> torch.Tensor:
        mean = mean.clone()
        # Observation groups are concatenated by sorted term key: v61 control precedes v6 hinge.
        d25_mask = context[..., -2:-1] == 1
        mean[..., self._D_ACTION_INDICES] = torch.where(
            d25_mask,
            self.post_release_late_override(context),
            mean[..., self._D_ACTION_INDICES],
        )
        return mean
