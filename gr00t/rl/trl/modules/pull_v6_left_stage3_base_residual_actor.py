"""Frozen H4 arm residual plus a LEFT Stage3 base-planar residual."""

from __future__ import annotations

import torch
from torch import nn

from gr00t.rl.trl.modules.pull_v6_left_stage3_obs_residual_actor import (
    PullV6LeftStage3ObsResidualActor,
)


class PullV6LeftStage3BaseResidualActor(PullV6LeftStage3ObsResidualActor):
    """Train only a zero-init base x/y/yaw residual on the frozen H5 actor."""

    _BASE_ACTION_INDICES = (0, 1, 2)
    _E3_GATE_KEY = "left_stage3_base_gate_obs"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        self.left_stage3_base_residual = nn.Linear(135, 3)
        nn.init.zeros_(self.left_stage3_base_residual.weight)
        nn.init.zeros_(self.left_stage3_base_residual.bias)

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
            from gr00t.rl.trl.utils.rl import unsplit_trajectories

            e3_gate = unsplit_trajectories(e3_gate, masks, original_dones)
        if e3_gate.shape[-1] != 1:
            raise RuntimeError("LEFT Stage3 base gate must be one E3-latched value.")
        return current_obs, gate, e3_gate

    def _apply_additional_post_release_override(self, mean: torch.Tensor, context):
        current_obs, gate, e3_gate = context
        result = super()._apply_additional_post_release_override(
            mean, (current_obs, gate)
        )
        left = (gate[..., 5] == 1.0) & (gate[..., 6] == 0.0)
        stage3 = gate[..., 11] == 1.0
        active = (left & stage3 & (e3_gate[..., 0] == 1.0)).unsqueeze(-1)
        base = result[..., self._BASE_ACTION_INDICES]
        candidate = base + self.left_stage3_base_residual(current_obs)
        updated = result.clone()
        updated[..., self._BASE_ACTION_INDICES] = torch.where(
            active, candidate, base
        )
        return updated
