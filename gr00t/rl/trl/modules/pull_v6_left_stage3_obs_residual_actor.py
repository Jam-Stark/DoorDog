"""Frozen pull-v6 carrier with a LEFT Stage3 current-observation residual."""

from __future__ import annotations

import torch
from tensordict import TensorDict
from torch import nn
from torch.distributions import Normal

from gr00t.rl.trl.modules.pull_v6_post_release_obs_override_actor import (
    PullV6PostReleaseObsOverrideActor,
)
from gr00t.rl.trl.utils.rl import unsplit_trajectories


class PullV6LeftStage3ObsResidualActor(PullV6PostReleaseObsOverrideActor):
    """Add one zero-init residual only on raw-LEFT Stage3 rows."""

    _GATE_KEY = "left_stage3_gate_obs"
    _ALLOWED_ACTION_INDICES = {
        (5, 6, 7, 8, 9, 10),
        (0, 1, 2, 5, 6, 7, 8, 9, 10),
    }

    def __init__(
        self, *args, left_stage3_residual_action_indices, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        if self.memory.rnn.input_size != 135:
            raise ValueError(
                "PullV6LeftStage3ObsResidualActor requires a 135-D carrier."
            )
        indices = tuple(int(index) for index in left_stage3_residual_action_indices)
        if indices not in self._ALLOWED_ACTION_INDICES:
            raise ValueError(
                "left_stage3_residual_action_indices must be arm6 or base-planar+arm9; "
                f"got {indices!r}."
            )
        self.left_stage3_residual_action_indices = indices
        self.left_stage3_obs_residual = nn.Linear(135, len(indices))
        nn.init.zeros_(self.left_stage3_obs_residual.weight)
        nn.init.zeros_(self.left_stage3_obs_residual.bias)
        if self.running_mean_std is not None:
            self.running_mean_std.freeze()
        if self.algo_config.get("use_clampped_std", False):
            raise ValueError(
                "H4 frozen carrier does not permit in-place use_clampped_std."
            )
        self._h4_clamp_noise_std = self.clamp_noise_std
        self.clamp_noise_std = False

    def _gate_obs(self, obs_dict, masks=None, original_dones=None) -> torch.Tensor:
        gate = obs_dict[self._GATE_KEY]
        if gate.ndim == 3 and masks is not None and original_dones is not None:
            gate = unsplit_trajectories(gate, masks, original_dones)
        if gate.shape[-1] != 14:
            raise RuntimeError(
                "LEFT Stage3 gate observation must be privileged_door_info(8)+stage(6)."
            )
        return gate

    def _additional_post_release_context(
        self, obs_dict, input_obs: torch.Tensor, masks=None, original_dones=None
    ):
        current_obs = self._current_obs(
            input_obs, masks=masks, original_dones=original_dones
        )
        gate = self._gate_obs(
            obs_dict, masks=masks, original_dones=original_dones
        )
        return current_obs, gate

    def _apply_additional_post_release_override(self, mean: torch.Tensor, context):
        current_obs, gate = context
        left = (gate[..., 5] == 1.0) & (gate[..., 6] == 0.0)
        stage3 = gate[..., 11] == 1.0
        active = (left & stage3).unsqueeze(-1)
        indices = self.left_stage3_residual_action_indices
        base = mean[..., indices]
        candidate = base + self.left_stage3_obs_residual(current_obs)
        result = mean.clone()
        result[..., indices] = torch.where(active, candidate, base)
        return result

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        episode_attnmask = self._update_obs_buffer(
            obs_dict, episode_attnmask, cur_dones
        )
        release_mode = self._release_mode(obs_dict)
        post_release_control = self._post_release_control(obs_dict, release_mode)

        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict = obs_dict.copy()
                obs_dict[self.input_key] = self.running_mean_std(
                    obs_dict[self.input_key]
                )
        current_obs = self._post_release_features(
            obs_dict, obs_dict[self.input_key]
        )
        context = self._additional_post_release_context(
            obs_dict, obs_dict[self.input_key]
        )
        memory_out = self.memory(current_obs)
        if len(memory_out.shape) == 3:
            memory_out = memory_out.squeeze(0)
        mean = self._mean_from_memory(
            memory_out,
            current_obs,
            release_mode,
            post_release_control,
            context,
            **kwargs,
        )
        distribution_std = (
            self.std.clamp(max=self.max_noise_std)
            if self._h4_clamp_noise_std
            else self.std
        )
        self.distribution = Normal(mean, mean * 0.0 + distribution_std)
        self.steps += 1
        return TensorDict(
            {
                "actions": self.distribution.sample(),
                "action_mean": self.action_mean,
                "action_sigma": self.action_std,
            }
        )

    def update_distribution(
        self,
        obs_dict,
        episode_attnmask=None,
        last_step_only=False,
        masks=None,
        hidden_states=None,
        original_dones=None,
        **kwargs,
    ):
        mean = self.forward(
            obs_dict,
            masks=masks,
            hidden_states=hidden_states,
            episode_attnmask=episode_attnmask,
            original_dones=original_dones,
            **kwargs,
        )
        if last_step_only:
            mean = mean[:, -1]
        distribution_std = (
            self.std.clamp(max=self.max_noise_std)
            if self._h4_clamp_noise_std
            else self.std
        )
        self.distribution = Normal(mean, mean * 0.0 + distribution_std)
