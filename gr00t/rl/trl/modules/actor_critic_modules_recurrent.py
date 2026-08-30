# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from __future__ import annotations

from collections.abc import Sequence

import torch
import torch.nn as nn
from tensordict import TensorDict
from torch.distributions import Normal

from gr00t.rl.trl.modules.actor_critic_modules import Actor, Critic
from gr00t.rl.trl.modules.memory import Memory
from gr00t.rl.trl.utils.common import custom_instantiate


class RecurrentActor(Actor):
    """Recurrent Actor that adds LSTM/GRU memory to the base Actor class."""

    is_recurrent = True

    def __init__(
        self,
        env_config,
        algo_config,
        backbone,
        module_dim_dict={},
        running_mean_std=False,
        max_rollout_history=1,
        input_key="actor_obs",
        rnn_type="lstm",
        rnn_hidden_dim=256,
        rnn_num_layers=1,
    ):
        super(RecurrentActor, self).__init__(
            env_config=env_config,
            algo_config=algo_config,
            backbone=backbone,
            module_dim_dict=module_dim_dict,
            running_mean_std=running_mean_std,
            max_rollout_history=max_rollout_history,
            input_key=input_key,
        )

        obs_dim_dict = env_config.robot.algo_obs_dim_dict
        input_dim = obs_dim_dict[self.input_key]

        # Add memory module
        self.memory = Memory(
            input_size=input_dim,
            type=rnn_type,
            num_layers=rnn_num_layers,
            hidden_size=rnn_hidden_dim,
        )

        # Replace the actor module to take rnn_hidden_dim as input instead of obs_dim
        module_dim_dict_recurrent = module_dim_dict.copy()
        module_dim_dict_recurrent[self.input_key] = rnn_hidden_dim
        self.actor_module = custom_instantiate(
            backbone,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict={self.input_key: rnn_hidden_dim},
            module_dim_dict=module_dim_dict_recurrent,
            _resolve=False,
        )

        print(f"RecurrentActor RNN: {self.memory}")
        print(f"RecurrentActor MLP: {self.actor_module}")

    def reset(self, dones=None):
        """Reset memory hidden states for done environments."""
        self.memory.reset(dones)

    def forward(
        self,
        obs_dict,
        masks=None,
        hidden_states=None,
        episode_attnmask=None,
        original_dones=None,
        **kwargs,
    ):
        obs_dict = obs_dict.copy()
        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict[self.input_key] = self.running_mean_std(obs_dict[self.input_key])

        # Pass through memory module
        # For batch training mode, obs_dict[self.input_key] should have shape [batch_size, seq_len, obs_dim]
        # For rollout mode, it should have shape [batch_size, obs_dim]
        input_obs = obs_dict[self.input_key]

        if len(input_obs.shape) == 2:  # Rollout mode: [batch_size, obs_dim]
            memory_out = self.memory(input_obs)
        else:  # Batch training mode: [batch_size, seq_len, ...] where ... might be multi-dimensional
            batch_size = input_obs.shape[0]
            seq_len = input_obs.shape[1]
            # Flatten all dimensions after seq_len into a single obs_dim
            # [batch_size, seq_len, *extra_dims] -> [batch_size, seq_len, obs_dim]
            input_obs = input_obs.reshape(batch_size, seq_len, -1)
            # Reshape for RNN: [seq_len, batch_size, obs_dim]
            input_obs = input_obs.transpose(0, 1)

            # Process sequences through Memory module
            # If masks provided (trajectory-based training), uses proper episode boundaries
            # If masks=None (non-trajectory training), processes full sequences
            if masks is not None and original_dones is not None:
                # Trajectory-based: use masks and initialize hidden states to zeros
                # Input is already in trajectory format: [seq=max_traj_len, batch=num_trajectories, obs_dim]
                memory_out = self.memory(input_obs, masks=masks, hidden_states=hidden_states)
                # memory_out: [num_trajectories, max_traj_len, hidden_dim]

                # Unsplit back to original [num_envs, num_steps, hidden_dim] format
                from gr00t.rl.trl.utils.rl import unsplit_trajectories

                memory_out = unsplit_trajectories(memory_out, masks, original_dones)
                # memory_out: [num_envs, num_steps, hidden_dim]
            else:
                # CRITICAL: This path should NOT be taken during training!
                # If masks is None during training, hidden states are reset to zeros for every batch
                # which breaks LSTM's ability to learn temporal dependencies
                if self.training:
                    raise RuntimeError(
                        "RecurrentActor: masks and original_dones must be provided during training! "
                        f"Got masks={masks}, original_dones={original_dones}. "
                        "This indicates a bug in _get_mb_rollout_data where trajectory splitting failed."
                    )
                # Non-trajectory: only for inference/rollout
                memory_out = self.memory(input_obs)  # hx=None as positional arg
                # Reshape back: [batch_size, seq_len, hidden_dim]
                memory_out = memory_out.transpose(0, 1)

        if self.algo_config.get("use_clampped_std", False):
            self.std.clamp_(min=self.algo_config.std_clamp_min, max=self.algo_config.std_clamp_max)

        return self.actor_module(memory_out, **kwargs)

    def get_hidden_states(self):
        """Get current hidden states from memory."""
        return self.memory.hidden_states

    def clear_rollout(self):
        """Clear rollout state and detach hidden states for proper TBPTT.

        CRITICAL for TBPTT: After rollout, hidden states must be detached to prevent
        backpropagation through the entire rollout history during training.
        """
        super().clear_rollout()
        # Detach all hidden states to truncate backprop through time
        self.memory.detach_hidden_states()

    def act(
        self,
        obs_dict,
        episode_attnmask=None,
        masks=None,
        hidden_states=None,
        original_dones=None,
        **kwargs,
    ):
        """Forward pass for sampling actions during training."""
        self.update_distribution(
            obs_dict,
            episode_attnmask=episode_attnmask,
            last_step_only=False,
            masks=masks,
            hidden_states=hidden_states,
            original_dones=original_dones,
            **kwargs,
        )
        actions = self._sample_actions()
        return TensorDict(
            {
                "actions": actions,
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

        if self.clamp_noise_std:
            with torch.no_grad():
                self.std.clamp_(max=self.max_noise_std)

        self.distribution = self._build_distribution(mean)

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        """Rollout method for recurrent actor during environment interaction."""
        episode_attnmask = self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)

        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict = obs_dict.copy()
                obs_dict[self.input_key] = self.running_mean_std(obs_dict[self.input_key])

        # For recurrent models, we use the memory hidden states rather than obs buffer
        # Pass current obs through memory and get output
        memory_out = self.memory(obs_dict[self.input_key])

        # Remove sequence dimension added by memory module during inference
        if len(memory_out.shape) == 3:  # [seq_len=1, batch_size, hidden_dim]
            memory_out = memory_out.squeeze(0)  # [batch_size, hidden_dim]

        # Update distribution using memory output
        mean = self.actor_module(memory_out, **kwargs)
        if self.clamp_noise_std:
            with torch.no_grad():
                self.std.clamp_(max=self.max_noise_std)
        self.distribution = self._build_distribution(mean)

        self.steps += 1
        return TensorDict(
            {
                "actions": self._sample_actions(),
                "action_mean": self.action_mean,
                "action_sigma": self.action_std,
            }
        )

    def act_inference(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        """Inference method for recurrent actor."""
        episode_attnmask = self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)

        # For recurrent models, pass through memory
        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict = obs_dict.copy()
                obs_dict[self.input_key] = self.running_mean_std(obs_dict[self.input_key])

        memory_out = self.memory(obs_dict[self.input_key])

        # Remove sequence dimension added by memory module during inference
        if len(memory_out.shape) == 3:  # [seq_len=1, batch_size, hidden_dim]
            memory_out = memory_out.squeeze(0)  # [batch_size, hidden_dim]

        actions_mean = self._mask_inference_actions(self.actor_module(memory_out, **kwargs))

        self.steps += 1
        return actions_mean


class A2V26_5PolicyResidualRecurrentActor(RecurrentActor):
    """Frozen legacy recurrent actor plus a stage-3 manipulation residual."""

    is_v26_5_policy_residual = True

    def __init__(
        self,
        *args,
        residual_hidden_dim=128,
        residual_stage_obs_slice=(127, 133),
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if isinstance(residual_hidden_dim, bool) or not isinstance(residual_hidden_dim, int):
            raise ValueError(
                "residual_hidden_dim must be a positive integer; "
                f"got {residual_hidden_dim!r}."
            )
        if residual_hidden_dim <= 0:
            raise ValueError(
                f"residual_hidden_dim must be positive; got {residual_hidden_dim}."
            )
        if (
            isinstance(residual_stage_obs_slice, (str, bytes))
            or not isinstance(residual_stage_obs_slice, Sequence)
            or len(residual_stage_obs_slice) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in residual_stage_obs_slice)
        ):
            raise ValueError(
                "residual_stage_obs_slice must be exactly two integer offsets; "
                f"got {residual_stage_obs_slice!r}."
            )
        self.residual_stage_obs_slice = tuple(residual_stage_obs_slice)
        stage_start, stage_end = self.residual_stage_obs_slice
        if stage_start < 0 or stage_end <= stage_start or stage_end - stage_start < 4:
            raise ValueError(
                "residual_stage_obs_slice must contain stage ids 0 through 3; "
                f"got {self.residual_stage_obs_slice!r}."
            )
        if self.running_mean_std is None:
            raise RuntimeError(
                "A2 v26-5 policy residual requires the legacy actor RunningMeanStd."
            )
        actor_obs_dim = self.running_mean_std.mean_size
        if stage_end > actor_obs_dim:
            raise ValueError(
                "residual_stage_obs_slice exceeds actor observation width: "
                f"slice={self.residual_stage_obs_slice}, width={actor_obs_dim}."
            )
        if self.num_actions != 12:
            raise RuntimeError(
                "A2 v26-5 policy residual requires exactly 12 high-level actions; "
                f"got {self.num_actions}."
            )

        # This actor is constructed on CPU before ``.to(device)``. Preserve the
        # surrounding experiment's CPU RNG timeline while retaining PyTorch's
        # standard Linear initialization for the learnable residual hidden layer.
        cpu_rng_state = torch.random.get_rng_state()
        try:
            self.residual_module = nn.Sequential(
                nn.Linear(actor_obs_dim + self.num_actions, residual_hidden_dim),
                nn.SiLU(),
                nn.Linear(residual_hidden_dim, 7),
            )
        finally:
            torch.random.set_rng_state(cpu_rng_state)
        nn.init.zeros_(self.residual_module[-1].weight)
        nn.init.zeros_(self.residual_module[-1].bias)

        for module in (self.memory, self.actor_module):
            for parameter in module.parameters():
                parameter.requires_grad_(False)
            module.eval()
        self.std.requires_grad_(False)
        self.running_mean_std.freeze()

    def train(self, mode=True):
        super().train(mode)
        self.memory.eval()
        self.actor_module.eval()
        return self

    def residual_state_keys(self):
        return frozenset(
            key for key in self.state_dict() if key.startswith("residual_module.")
        )

    def assert_residual_zero_initialized(self):
        final_layer = self.residual_module[-1]
        if not torch.equal(final_layer.weight, torch.zeros_like(final_layer.weight)):
            raise RuntimeError("A2 v26-5 residual final weight must be zero initialized.")
        if not torch.equal(final_layer.bias, torch.zeros_like(final_layer.bias)):
            raise RuntimeError("A2 v26-5 residual final bias must be zero initialized.")

    def _normalize_frozen_actor_obs(self, actor_obs):
        with torch.no_grad():
            return self.running_mean_std(actor_obs)

    def _stage3_or_later_mask(self, raw_actor_obs):
        stage_start, stage_end = self.residual_stage_obs_slice
        stage_one_hot = raw_actor_obs[..., stage_start:stage_end]
        if stage_one_hot.shape[-1] != stage_end - stage_start:
            raise RuntimeError(
                "A2 v26-5 residual stage slice does not match actor observation: "
                f"slice={self.residual_stage_obs_slice}, shape={tuple(raw_actor_obs.shape)}."
            )
        return torch.argmax(stage_one_hot, dim=-1) >= 3

    def _add_residual(self, normalized_actor_obs, raw_actor_obs, base_mean):
        residual_input = torch.cat((normalized_actor_obs, base_mean.detach()), dim=-1)
        residual = self.residual_module(residual_input)
        stage_mask = self._stage3_or_later_mask(raw_actor_obs).unsqueeze(-1)
        mean = base_mean.clone()
        mean[..., 5:12] = mean[..., 5:12] + torch.where(
            stage_mask, residual, torch.zeros_like(residual)
        )
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
        raw_actor_obs = obs_dict[self.input_key]
        normalized_actor_obs = self._normalize_frozen_actor_obs(raw_actor_obs)

        if normalized_actor_obs.ndim == 2:
            with torch.no_grad():
                memory_out = self.memory(normalized_actor_obs)
                expected_memory_shape = (
                    1,
                    normalized_actor_obs.shape[0],
                    self.memory.rnn.hidden_size,
                )
                if tuple(memory_out.shape) != expected_memory_shape:
                    raise RuntimeError(
                        "A2 v26-5 residual recurrent rollout memory output shape mismatch: "
                        f"expected {expected_memory_shape}, got {tuple(memory_out.shape)}."
                    )
                memory_out = memory_out.squeeze(0)
                base_mean = self.actor_module(memory_out, **kwargs)
            return self._add_residual(normalized_actor_obs, raw_actor_obs, base_mean)

        if normalized_actor_obs.ndim != 3:
            raise RuntimeError(
                "A2 v26-5 recurrent residual expects actor observations shaped [B,D] or [B,T,D]; "
                f"got {tuple(normalized_actor_obs.shape)}."
            )
        batch_size, seq_len = normalized_actor_obs.shape[:2]
        rnn_input = normalized_actor_obs.reshape(batch_size, seq_len, -1).transpose(0, 1)
        if masks is not None and original_dones is not None:
            with torch.no_grad():
                memory_out = self.memory(rnn_input, masks=masks, hidden_states=hidden_states)
                base_mean = self.actor_module(memory_out, **kwargs)
            residual_mean = self._add_residual(normalized_actor_obs, raw_actor_obs, base_mean)
            from gr00t.rl.trl.utils.rl import unsplit_trajectories

            return unsplit_trajectories(residual_mean, masks, original_dones)
        if self.training:
            raise RuntimeError(
                "A2 v26-5 residual recurrent training requires masks and original_dones."
            )
        with torch.no_grad():
            memory_out = self.memory(rnn_input).transpose(0, 1)
            base_mean = self.actor_module(memory_out, **kwargs)
        return self._add_residual(normalized_actor_obs, raw_actor_obs, base_mean)

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        raw_actor_obs = obs_dict[self.input_key]
        normalized_actor_obs = self._normalize_frozen_actor_obs(raw_actor_obs)
        with torch.no_grad():
            memory_out = self.memory(normalized_actor_obs)
            if memory_out.ndim == 3:
                memory_out = memory_out.squeeze(0)
            base_mean = self.actor_module(memory_out, **kwargs)
        mean = self._add_residual(normalized_actor_obs, raw_actor_obs, base_mean)
        if self.clamp_noise_std:
            with torch.no_grad():
                self.std.clamp_(max=self.max_noise_std)
        self.distribution = self._build_distribution(mean)
        self.steps += 1
        return TensorDict(
            {
                "actions": self._sample_actions(),
                "action_mean": self.action_mean,
                "action_sigma": self.action_std,
            }
        )

    def act_inference(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        raw_actor_obs = obs_dict[self.input_key]
        normalized_actor_obs = self._normalize_frozen_actor_obs(raw_actor_obs)
        with torch.no_grad():
            memory_out = self.memory(normalized_actor_obs)
            if memory_out.ndim == 3:
                memory_out = memory_out.squeeze(0)
            base_mean = self.actor_module(memory_out, **kwargs)
        self.steps += 1
        return self._mask_inference_actions(
            self._add_residual(normalized_actor_obs, raw_actor_obs, base_mean)
        )


class RecurrentCritic(Critic):
    """Recurrent Critic that adds LSTM/GRU memory to the base Critic class."""

    is_recurrent = True

    def __init__(
        self,
        env_config,
        algo_config,
        backbone,
        module_dim_dict={},
        running_mean_std=False,
        rnn_type="lstm",
        rnn_hidden_dim=256,
        rnn_num_layers=1,
    ):
        super(RecurrentCritic, self).__init__(
            env_config=env_config,
            algo_config=algo_config,
            backbone=backbone,
            module_dim_dict=module_dim_dict,
            running_mean_std=running_mean_std,
        )

        obs_dim_dict = env_config.robot.algo_obs_dim_dict
        input_dim = obs_dim_dict["critic_obs"]

        # Add memory module
        self.memory = Memory(
            input_size=input_dim,
            type=rnn_type,
            num_layers=rnn_num_layers,
            hidden_size=rnn_hidden_dim,
        )

        # Replace the critic module to take rnn_hidden_dim as input instead of obs_dim
        module_dim_dict_recurrent = module_dim_dict.copy()
        module_dim_dict_recurrent["critic_obs"] = rnn_hidden_dim
        self.critic_module = custom_instantiate(
            backbone,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict={"critic_obs": rnn_hidden_dim},
            module_dim_dict=module_dim_dict_recurrent,
            _resolve=False,
        )

        print(f"RecurrentCritic RNN: {self.memory}")
        print(f"RecurrentCritic MLP: {self.critic_module}")

    def reset(self, dones=None):
        """Reset memory hidden states for done environments."""
        self.memory.reset(dones)

    def get_hidden_states(self):
        """Get current hidden states from memory."""
        return self.memory.hidden_states

    def clear_rollout(self):
        """Clear rollout state and detach hidden states for proper TBPTT.

        CRITICAL for TBPTT: After rollout, hidden states must be detached to prevent
        backpropagation through the entire rollout history during training.
        """
        super().clear_rollout()
        # Detach all hidden states to truncate backprop through time
        self.memory.detach_hidden_states()

    def evaluate(
        self,
        obs_dict,
        masks=None,
        hidden_states=None,
        episode_attnmask=None,
        original_dones=None,
        **kwargs,
    ):
        obs_dict = obs_dict.copy()
        if self.running_mean_std is not None:
            with torch.no_grad():
                obs_dict["critic_obs"] = self.running_mean_std(obs_dict["critic_obs"])

        # Pass through memory module
        # For batch training mode, obs_dict['critic_obs'] should have shape [batch_size, seq_len, obs_dim]
        # For rollout mode, it should have shape [batch_size, obs_dim]
        input_obs = obs_dict["critic_obs"]

        if len(input_obs.shape) == 2:  # Rollout mode: [batch_size, obs_dim]
            memory_out = self.memory(input_obs)
            # Remove sequence dimension added by memory module during inference
            if len(memory_out.shape) == 3:  # [seq_len=1, batch_size, hidden_dim]
                memory_out = memory_out.squeeze(0)  # [batch_size, hidden_dim]
        else:  # Batch training mode: [batch_size, seq_len, ...] where ... might be multi-dimensional
            batch_size = input_obs.shape[0]
            seq_len = input_obs.shape[1]
            # Flatten all dimensions after seq_len into a single obs_dim
            # [batch_size, seq_len, *extra_dims] -> [batch_size, seq_len, obs_dim]
            input_obs = input_obs.reshape(batch_size, seq_len, -1)
            # Reshape for RNN: [seq_len, batch_size, obs_dim]
            input_obs = input_obs.transpose(0, 1)

            # Process sequences through Memory module
            # If masks provided (trajectory-based training), uses proper episode boundaries
            # If masks=None (non-trajectory training), processes full sequences
            if masks is not None and original_dones is not None:
                # Trajectory-based: use masks and initialize hidden states to zeros
                # Input is already in trajectory format: [seq=max_traj_len, batch=num_trajectories, obs_dim]
                memory_out = self.memory(input_obs, masks=masks, hidden_states=hidden_states)
                # memory_out: [num_trajectories, max_traj_len, hidden_dim]

                # Unsplit back to original [num_envs, num_steps, hidden_dim] format
                from gr00t.rl.trl.utils.rl import unsplit_trajectories

                memory_out = unsplit_trajectories(memory_out, masks, original_dones)
                # memory_out: [num_envs, num_steps, hidden_dim]
            else:
                # CRITICAL: This path should NOT be taken during training!
                # If masks is None during training, hidden states are reset to zeros for every batch
                # which breaks LSTM's ability to learn temporal dependencies
                if self.training:
                    raise RuntimeError(
                        "RecurrentCritic: masks and original_dones must be provided during training! "
                        f"Got masks={masks}, original_dones={original_dones}. "
                        "This indicates a bug in _get_mb_rollout_data where trajectory splitting failed."
                    )
                # Non-trajectory: only for inference/rollout
                memory_out = self.memory(input_obs)  # hx=None as positional arg
                # Reshape back: [batch_size, seq_len, hidden_dim]
                memory_out = memory_out.transpose(0, 1)

        value = self.critic_module(memory_out, **kwargs)
        return value
