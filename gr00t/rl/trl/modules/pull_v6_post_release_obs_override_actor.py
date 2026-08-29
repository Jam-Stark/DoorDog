"""Frozen pull-v6 carrier with a current-observation D-only mean override."""

from __future__ import annotations

import torch
from tensordict import TensorDict
from torch import nn
from torch.distributions import Normal

from gr00t.rl.trl.modules.pull_v6_release_mode_actor import PullV6ReleaseModeActor
from gr00t.rl.trl.utils.rl import unsplit_trajectories


class PullV6PostReleaseObsOverrideActor(PullV6ReleaseModeActor):
    """Train a current-observation D-only mean override on the frozen r6ag carrier."""

    _D_ACTION_INDICES = (0, 1, 2, 5, 6, 7, 8, 9, 10)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        self.post_release_obs_override = nn.Linear(
            self.memory.rnn.input_size, len(self._D_ACTION_INDICES)
        )
        nn.init.zeros_(self.post_release_obs_override.weight)
        nn.init.zeros_(self.post_release_obs_override.bias)

    def _release_mode(self, obs_dict, masks=None, original_dones=None) -> torch.Tensor:
        release_mode = obs_dict[self.input_key][..., -2:]
        if release_mode.ndim == 3 and masks is not None and original_dones is not None:
            release_mode = unsplit_trajectories(release_mode, masks, original_dones)
        return release_mode

    def _current_obs(self, input_obs: torch.Tensor, masks=None, original_dones=None) -> torch.Tensor:
        if input_obs.ndim == 3 and masks is not None and original_dones is not None:
            return unsplit_trajectories(input_obs, masks, original_dones)
        return input_obs

    def _post_release_features(
        self, obs_dict, input_obs: torch.Tensor, masks=None, original_dones=None
    ) -> torch.Tensor:
        return self._current_obs(input_obs, masks=masks, original_dones=original_dones)

    def _additional_post_release_context(
        self, obs_dict, input_obs: torch.Tensor, masks=None, original_dones=None
    ):
        return None

    def _apply_additional_post_release_override(self, mean: torch.Tensor, context) -> torch.Tensor:
        del context
        return mean

    def _post_release_control(
        self, obs_dict, release_mode: torch.Tensor, masks=None, original_dones=None
    ) -> torch.Tensor:
        return release_mode[..., 1:2]

    def _apply_post_release_override(
        self, mean: torch.Tensor, current_obs: torch.Tensor, post_release_control: torch.Tensor
    ) -> torch.Tensor:
        mean = mean.clone()
        d_mask = post_release_control == 1
        mean[..., self._D_ACTION_INDICES] = torch.where(
            d_mask,
            self.post_release_obs_override(current_obs),
            mean[..., self._D_ACTION_INDICES],
        )
        return mean

    def _mean_from_memory(
        self,
        memory_out: torch.Tensor,
        current_obs: torch.Tensor,
        release_mode: torch.Tensor,
        post_release_control: torch.Tensor,
        additional_context=None,
        **kwargs,
    ) -> torch.Tensor:
        mean = self._apply_release_mode_override(self.actor_module(memory_out, **kwargs), release_mode)
        mean = self._apply_post_release_override(mean, current_obs, post_release_control)
        return self._apply_additional_post_release_override(mean, additional_context)

    def forward(
        self,
        obs_dict,
        masks=None,
        hidden_states=None,
        episode_attnmask=None,
        original_dones=None,
        **kwargs,
    ):
        release_mode = self._release_mode(obs_dict, masks=masks, original_dones=original_dones)
        post_release_control = self._post_release_control(
            obs_dict, release_mode, masks=masks, original_dones=original_dones
        )
        obs_dict = obs_dict.copy()
        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict[self.input_key] = self.running_mean_std(obs_dict[self.input_key])

        input_obs = obs_dict[self.input_key]
        current_obs = self._post_release_features(
            obs_dict, input_obs, masks=masks, original_dones=original_dones
        )
        additional_context = self._additional_post_release_context(
            obs_dict, input_obs, masks=masks, original_dones=original_dones
        )
        if len(input_obs.shape) == 2:
            memory_out = self.memory(input_obs)
        else:
            batch_size = input_obs.shape[0]
            seq_len = input_obs.shape[1]
            input_obs = input_obs.reshape(batch_size, seq_len, -1).transpose(0, 1)
            if masks is not None and original_dones is not None:
                memory_out = self.memory(input_obs, masks=masks, hidden_states=hidden_states)
                memory_out = unsplit_trajectories(memory_out, masks, original_dones)
            else:
                if self.training:
                    raise RuntimeError(
                        "PullV6PostReleaseObsOverrideActor: masks and original_dones must be provided during training!"
                    )
                memory_out = self.memory(input_obs).transpose(0, 1)

        if self.algo_config.get("use_clampped_std", False):
            self.std.clamp_(min=self.algo_config.std_clamp_min, max=self.algo_config.std_clamp_max)
        return self._mean_from_memory(
            memory_out, current_obs, release_mode, post_release_control, additional_context, **kwargs
        )

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        episode_attnmask = self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        release_mode = self._release_mode(obs_dict)
        post_release_control = self._post_release_control(obs_dict, release_mode)

        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict = obs_dict.copy()
                obs_dict[self.input_key] = self.running_mean_std(obs_dict[self.input_key])

        current_obs = self._post_release_features(obs_dict, obs_dict[self.input_key])
        additional_context = self._additional_post_release_context(
            obs_dict, obs_dict[self.input_key]
        )
        memory_out = self.memory(current_obs)
        if len(memory_out.shape) == 3:
            memory_out = memory_out.squeeze(0)

        mean = self._mean_from_memory(
            memory_out, current_obs, release_mode, post_release_control, additional_context, **kwargs
        )
        if self.clamp_noise_std:
            with torch.no_grad():
                self.std.clamp_(max=self.max_noise_std)
        self.distribution = Normal(mean, mean * 0.0 + self.std)

        self.steps += 1
        return TensorDict(
            {
                "actions": self.distribution.sample(),
                "action_mean": self.action_mean,
                "action_sigma": self.action_std,
            }
        )

    def act_inference(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        episode_attnmask = self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        release_mode = self._release_mode(obs_dict)
        post_release_control = self._post_release_control(obs_dict, release_mode)

        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict = obs_dict.copy()
                obs_dict[self.input_key] = self.running_mean_std(obs_dict[self.input_key])

        current_obs = self._post_release_features(obs_dict, obs_dict[self.input_key])
        additional_context = self._additional_post_release_context(
            obs_dict, obs_dict[self.input_key]
        )
        memory_out = self.memory(current_obs)
        if len(memory_out.shape) == 3:
            memory_out = memory_out.squeeze(0)

        self.steps += 1
        return self._mean_from_memory(
            memory_out, current_obs, release_mode, post_release_control, additional_context, **kwargs
        )
