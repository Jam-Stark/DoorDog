"""Frozen bilateral parent with a shared raw-absolute Stage3 action head."""

from __future__ import annotations

import torch
from tensordict import TensorDict
from torch import nn
from torch.distributions import Normal

from gr00t.rl.trl.modules.pull_v6_population_output_actor import (
    PullV6PopulationOutputActor,
)


class PullV6BilateralStage3AbsoluteActor(PullV6PopulationOutputActor):
    """Learn canonical base and absolute cumulative arm targets only in Stage3."""

    _OBS_DIM = 135
    _BASE_COMMAND = slice(0, 5)
    _BASE_ANG_VEL = slice(29, 32)
    _BASE_LIN_VEL = slice(32, 35)
    _DOF_POS = slice(41, 61)
    _DOF_VEL = slice(61, 81)
    _DOOR_Q = slice(81, 83)
    _HANDLE_POSE = slice(83, 92)
    _HAND_FORCE = slice(101, 107)
    _DOOR_METADATA = slice(107, 115)
    _GRAVITY = slice(115, 118)
    _RELATIVE_DOOR = slice(118, 127)
    _STAGE = slice(127, 133)
    _ARM_DOF = slice(53, 59)
    _GRIPPER_DOF = slice(59, 61)
    _ARM_DOF_VEL = slice(73, 79)
    _GRIPPER_DOF_VEL = slice(79, 81)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        if self.running_mean_std is None:
            raise RuntimeError("Bilateral absolute actor requires a frozen 135-D RMS.")
        if self.memory.rnn.input_size != self._OBS_DIM:
            raise RuntimeError("Bilateral absolute actor requires a 135-D parent carrier.")
        with torch.random.fork_rng():
            torch.manual_seed(0)
            self.bilateral_stage3_absolute_head = nn.Sequential(
                nn.Linear(58, 256),
                nn.SiLU(),
                nn.Linear(256, 256),
                nn.SiLU(),
                nn.Linear(256, 9),
            )
        nn.init.zeros_(self.bilateral_stage3_absolute_head[4].weight)
        nn.init.zeros_(self.bilateral_stage3_absolute_head[4].bias)
        self._absolute_clamp_noise_std = self.clamp_noise_std
        self.clamp_noise_std = False

    @staticmethod
    def _require_onehot(value: torch.Tensor, name: str) -> None:
        if not value.is_floating_point() or not torch.all(torch.isfinite(value)):
            raise RuntimeError(f"{name} must be finite floating-point.")
        tolerance = torch.finfo(value.dtype).eps * 8.0
        binary = (torch.abs(value) <= tolerance) | (
            torch.abs(value - 1.0) <= tolerance
        )
        if not torch.all(binary) or not torch.all(
            torch.abs(value.sum(dim=-1) - 1.0) <= tolerance
        ):
            raise RuntimeError(f"{name} must be one-hot.")

    @staticmethod
    def _polar(vector: torch.Tensor, mirror: torch.Tensor) -> torch.Tensor:
        return vector * torch.stack(
            (torch.ones_like(mirror), mirror, torch.ones_like(mirror)), dim=-1
        )

    @staticmethod
    def _axial(vector: torch.Tensor, mirror: torch.Tensor) -> torch.Tensor:
        return vector * torch.stack(
            (mirror, torch.ones_like(mirror), mirror), dim=-1
        )

    def _canonical_features(
        self, current_obs: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if current_obs.shape[-1] != self._OBS_DIM:
            raise RuntimeError(
                "Bilateral absolute actor requires a 135-D current observation."
            )
        raw = self.running_mean_std(current_obs, unnorm=True)
        if raw.shape != current_obs.shape:
            raise RuntimeError("RMS unnormalization changed current observation shape.")
        metadata = raw[..., self._DOOR_METADATA]
        side = metadata[..., 5:7]
        stage = raw[..., self._STAGE]
        self._require_onehot(side, "door handedness")
        self._require_onehot(stage, "stage")
        mirror = side[..., 1] - side[..., 0]
        tolerance = torch.finfo(mirror.dtype).eps * 8.0
        if not torch.all(torch.abs(torch.abs(mirror) - 1.0) <= tolerance):
            raise RuntimeError("door handedness must resolve to LEFT or RIGHT.")
        mirror = torch.where(
            mirror > 0.0, torch.ones_like(mirror), -torch.ones_like(mirror)
        )
        relative = raw[..., self._RELATIVE_DOOR]
        handle_pose = raw[..., self._HANDLE_POSE]
        force_norms = torch.linalg.vector_norm(
            raw[..., self._HAND_FORCE].reshape(*raw.shape[:-1], 2, 3), dim=-1
        ).sort(dim=-1).values
        base_command = raw[..., self._BASE_COMMAND]
        canonical_base_command = torch.stack(
            (
                base_command[..., 0],
                mirror * base_command[..., 1],
                mirror * base_command[..., 2],
                base_command[..., 3],
                base_command[..., 4],
            ),
            dim=-1,
        )
        features = torch.cat(
            (
                raw[..., self._ARM_DOF],
                raw[..., self._ARM_DOF_VEL],
                raw[..., self._GRIPPER_DOF],
                raw[..., self._GRIPPER_DOF_VEL],
                torch.cat(
                    tuple(self._polar(relative[..., i : i + 3], mirror) for i in (0, 3, 6)),
                    dim=-1,
                ),
                self._polar(raw[..., self._GRAVITY], mirror),
                self._polar(raw[..., self._BASE_LIN_VEL], mirror),
                self._axial(raw[..., self._BASE_ANG_VEL], mirror),
                raw[..., self._DOOR_Q],
                force_norms,
                torch.cat(
                    tuple(self._polar(handle_pose[..., i : i + 3], mirror) for i in (0, 3, 6)),
                    dim=-1,
                ),
                torch.cat((metadata[..., :5], metadata[..., 7:8]), dim=-1),
                canonical_base_command,
            ),
            dim=-1,
        )
        if features.shape[-1] != 58:
            raise RuntimeError("Bilateral absolute canonical feature contract must be 58-D.")
        return features, mirror, stage[..., 3] > 0.5

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
        features, mirror, stage3 = self._canonical_features(current_obs)
        head = self.bilateral_stage3_absolute_head(features)
        base = torch.stack(
            (head[..., 0], mirror * head[..., 1], mirror * head[..., 2]), dim=-1
        )
        updated = result.clone()
        updated[..., :3] = torch.where(stage3.unsqueeze(-1), base, result[..., :3])
        updated[..., 5:11] = torch.where(
            stage3.unsqueeze(-1), head[..., 3:], result[..., 5:11]
        )
        return updated

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
        current_obs = self._post_release_features(obs_dict, obs_dict[self.input_key])
        additional_context = self._additional_post_release_context(
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
            additional_context,
            **kwargs,
        )
        distribution_std = (
            self.std.clamp(max=self.max_noise_std)
            if self._absolute_clamp_noise_std
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
            if self._absolute_clamp_noise_std
            else self.std
        )
        self.distribution = Normal(mean, mean * 0.0 + distribution_std)
