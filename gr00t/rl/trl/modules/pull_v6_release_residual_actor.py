"""Frozen pull-v6 recurrent carrier with a learned release-mode gripper residual."""

from __future__ import annotations

import torch
from torch import nn

from gr00t.rl.trl.modules.actor_critic_modules_recurrent import RecurrentActor
from gr00t.rl.trl.utils.rl import unsplit_trajectories


class PullV6ReleaseResidualActor(RecurrentActor):
    """Keep the r6ad carrier fixed while learning only the two release-mode offsets."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        self.release_mode_gripper_mean_residual = nn.Parameter(torch.zeros(2))
        if self.running_mean_std is not None:
            self.running_mean_std.freeze()

    def _release_mode(self, obs_dict, masks=None, original_dones=None) -> torch.Tensor:
        release_mode = obs_dict[self.input_key][..., -2:]
        if release_mode.ndim == 3 and masks is not None and original_dones is not None:
            release_mode = unsplit_trajectories(release_mode, masks, original_dones)
        return release_mode

    def _apply_release_residual(
        self, mean: torch.Tensor, release_mode: torch.Tensor
    ) -> torch.Tensor:
        mean = mean.clone()
        mean[..., 11] += release_mode @ self.release_mode_gripper_mean_residual
        return mean

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
        mean = super().forward(
            obs_dict,
            masks=masks,
            hidden_states=hidden_states,
            episode_attnmask=episode_attnmask,
            original_dones=original_dones,
            **kwargs,
        )
        return self._apply_release_residual(mean, release_mode)

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        episode_attnmask = self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        release_mode = self._release_mode(obs_dict)

        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict = obs_dict.copy()
                obs_dict[self.input_key] = self.running_mean_std(obs_dict[self.input_key])

        memory_out = self.memory(obs_dict[self.input_key])
        if len(memory_out.shape) == 3:
            memory_out = memory_out.squeeze(0)

        mean = self._apply_release_residual(self.actor_module(memory_out, **kwargs), release_mode)
        if self.clamp_noise_std:
            with torch.no_grad():
                self.std.clamp_(max=self.max_noise_std)
        self.distribution = torch.distributions.Normal(mean, mean * 0.0 + self.std)

        self.steps += 1
        from tensordict import TensorDict

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

        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict = obs_dict.copy()
                obs_dict[self.input_key] = self.running_mean_std(obs_dict[self.input_key])

        memory_out = self.memory(obs_dict[self.input_key])
        if len(memory_out.shape) == 3:
            memory_out = memory_out.squeeze(0)

        self.steps += 1
        return self._apply_release_residual(self.actor_module(memory_out, **kwargs), release_mode)
