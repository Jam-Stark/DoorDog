# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""C-B2H tri-view recurrent Student actor.

The two portrait D435 views intentionally share one ResNet18 instance.  The
OEM A2 Head has a separate ResNet18 because its optics, aspect ratio and frame
rate are different.  All contracts are explicit and invalid inputs fail fast.
"""

from __future__ import annotations

from collections.abc import Mapping

import torch
import torch.nn as nn
from hydra.utils import instantiate
from torch.distributions import Normal

from gr00t.rl.trl.modules.memory import Memory
from gr00t.rl.utils.running_mean_std import RunningMeanStd


class TriViewContextSharedEncoderVisionRecurrentActor(nn.Module):
    """Tri-view C-B2H policy with shared D435 encoder and two-layer LSTM."""

    is_recurrent = True

    def __init__(
        self,
        env_config,
        algo_config,
        backbone,
        module_dim_dict=None,
        running_mean_std=False,
        max_rollout_history=1,
        input_key="actor_obs",
        manipulation_vision_key="vision_obs",
        context_vision_key="context_vision_obs",
        camera_meta_key="camera_meta",
        rnn_type="lstm",
        rnn_hidden_dim=256,
        rnn_num_layers=2,
        view_contract=None,
    ):
        super().__init__()
        module_dim_dict = {} if module_dim_dict is None else dict(module_dim_dict)
        self.input_key = input_key
        self.manipulation_vision_key = manipulation_vision_key
        self.context_vision_key = context_vision_key
        self.camera_meta_key = camera_meta_key
        self.max_rollout_history = int(max_rollout_history)
        if self.max_rollout_history <= 0:
            raise ValueError("max_rollout_history must be positive")

        obs_dim_dict = env_config.robot.algo_obs_dim_dict
        required_dims = {
            input_key: 81,
            manipulation_vision_key: 384 * 216 * 6,
            context_vision_key: 136 * 384 * 3,
            camera_meta_key: 6,
        }
        for key, expected in required_dims.items():
            actual = obs_dim_dict.get(key)
            if actual is None or int(actual) != expected:
                raise ValueError(f"C-B2H {key} dimension must be {expected}; got {actual!r}")

        contract = view_contract or {}
        if isinstance(contract, Mapping):
            manipulation_shape = tuple(int(value) for value in contract.get("manipulation_shape", (384, 216, 6)))
            context_shape = tuple(int(value) for value in contract.get("context_shape", (136, 384, 3)))
            meta_dim = int(contract.get("camera_meta_dim", 6))
            view_order = tuple(contract.get("d435i_view_order", ("left", "right")))
            d435i_feature_dim = int(contract.get("d435i_feature_dim", 128))
            head_feature_dim = int(contract.get("head_feature_dim", 128))
            fused_feature_dim = int(contract.get("fused_feature_dim", 128))
        else:
            raise TypeError("view_contract must be a mapping")
        if manipulation_shape != (384, 216, 6) or context_shape != (136, 384, 3):
            raise ValueError(f"C-B2H view shapes are fixed; got {manipulation_shape=} {context_shape=}")
        if meta_dim != 6 or view_order != ("left", "right"):
            raise ValueError(f"C-B2H camera metadata/view order drifted: {meta_dim=} {view_order=}")
        if (d435i_feature_dim, head_feature_dim, fused_feature_dim) != (128, 128, 128):
            raise ValueError("C-B2H encoder and fused feature dimensions must each be 128")
        if int(rnn_hidden_dim) != 256 or int(rnn_num_layers) != 2 or rnn_type.lower() != "lstm":
            raise ValueError("C-B2H recurrent contract requires LSTM hidden=256 layers=2")

        self.d435i_vision_module = instantiate(
            backbone.d435i_vision_module,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict=obs_dim_dict,
            module_dim_dict=module_dim_dict,
            _recursive_=False,
        )
        self.head_vision_module = instantiate(
            backbone.head_vision_module,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict=obs_dim_dict,
            module_dim_dict=module_dim_dict,
            _recursive_=False,
        )
        if int(self.d435i_vision_module.output_dim) != 128:
            raise ValueError(f"shared D435 encoder output must be 128; got {self.d435i_vision_module.output_dim}")
        if int(self.head_vision_module.output_dim) != 128:
            raise ValueError(f"head encoder output must be 128; got {self.head_vision_module.output_dim}")
        self.d435i_vision_module_config_dict = backbone.d435i_vision_module.module_config_dict
        self.head_vision_module_config_dict = backbone.head_vision_module.module_config_dict
        for name, config in (("d435i", self.d435i_vision_module_config_dict), ("head", self.head_vision_module_config_dict)):
            layer_type = config.layer_config.type if hasattr(config.layer_config, "type") else config.layer_config["type"]
            if layer_type != "ResNet":
                raise ValueError(f"C-B2H {name} encoder must use ResNet, got {layer_type!r}")

        self.left_view_embedding = nn.Parameter(torch.zeros(128))
        self.right_view_embedding = nn.Parameter(torch.zeros(128))
        self.head_view_embedding = nn.Parameter(torch.zeros(128))
        self.left_view_norm = nn.LayerNorm(128)
        self.right_view_norm = nn.LayerNorm(128)
        self.head_view_norm = nn.LayerNorm(128)
        self.manipulation_norm = nn.LayerNorm(128)
        self.context_norm = nn.LayerNorm(128)
        self.manipulation_residual = nn.Sequential(
            nn.Linear(384, 256),
            nn.SiLU(),
            nn.LayerNorm(256),
            nn.Linear(256, 128),
        )
        self.context_residual = nn.Sequential(
            nn.Linear(390, 256),
            nn.SiLU(),
            nn.LayerNorm(256),
            nn.Linear(256, 128),
        )
        self.context_gate = nn.Sequential(
            nn.Linear(390, 64),
            nn.SiLU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )
        nn.init.zeros_(self.manipulation_residual[-1].weight)
        nn.init.zeros_(self.manipulation_residual[-1].bias)
        nn.init.zeros_(self.context_residual[-1].weight)
        nn.init.zeros_(self.context_residual[-1].bias)
        self.manipulation_tau_s = 0.05
        self.context_tau_s = 0.10
        self.head_base_weight = 0.25

        concat_dim = 81 + 128
        if concat_dim != 209:
            raise RuntimeError(f"C-B2H recurrent input contract drifted: {concat_dim}")
        self.memory = Memory(
            input_size=concat_dim,
            type=rnn_type,
            num_layers=int(rnn_num_layers),
            hidden_size=int(rnn_hidden_dim),
        )
        recurrent_module_dim = dict(module_dim_dict)
        recurrent_module_dim[input_key] = int(rnn_hidden_dim)
        self.mlp_module = instantiate(
            backbone.mlp_module,
            env_config=env_config,
            algo_config=algo_config,
            obs_dim_dict={input_key: int(rnn_hidden_dim)},
            module_dim_dict=recurrent_module_dim,
            _recursive_=False,
        )
        if int(self.mlp_module.output_dim) != 12:
            raise ValueError(f"C-B2H action output must be 12; got {self.mlp_module.output_dim}")

        self.running_mean_std = None
        if running_mean_std:
            self.running_mean_std = RunningMeanStd((81,), per_channel=True)
        init_noise_std = float(algo_config.init_noise_std)
        self.num_actions = int(self.mlp_module.output_dim)
        self.std = nn.Parameter(init_noise_std * torch.ones(self.num_actions))
        if algo_config.get("freeze_noise_std", False):
            self.std.requires_grad = False
        self.clamp_noise_std = bool(algo_config.get("clamp_noise_std", False))
        self.max_noise_std = float(algo_config.get("max_noise_std", 1.0))
        self.distribution = None
        Normal.set_default_validate_args(False)
        self.obs_dict_buffer = {}
        self.dones_buffer = None
        self.steps = 0
        self.is_eval_mode = False

    @staticmethod
    def _require_tensor(name, value, ndim, last_dim=None):
        if not torch.is_tensor(value) or value.ndim != ndim:
            raise ValueError(f"{name} must be a {ndim}D tensor; got {getattr(value, 'shape', None)}")
        if last_dim is not None and value.shape[-1] != last_dim:
            raise ValueError(f"{name} last dimension must be {last_dim}; got {tuple(value.shape)}")
        if not torch.is_floating_point(value) or not bool(torch.all(torch.isfinite(value)).item()):
            raise ValueError(f"{name} must be a finite floating tensor")

    def _validate_views(self, dual, head, meta, masks):
        if not torch.is_tensor(dual) or not torch.is_tensor(head) or not torch.is_tensor(meta):
            raise ValueError("C-B2H vision_obs, context_vision_obs, and camera_meta must be tensors")
        if dual.ndim not in (4, 5):
            raise ValueError(
                "C-B2H image observations must be rank 4 [B,H,W,C] or "
                f"rank 5 [B,T,H,W,C]; got rank {dual.ndim}"
            )
        expected_meta_ndim = dual.ndim - 2
        if head.ndim != dual.ndim or meta.ndim != expected_meta_ndim:
            raise ValueError(
                "C-B2H ranks must be image rank 4/meta rank 2 or image rank 5/meta rank 3; "
                f"got dual={dual.ndim} head={head.ndim} meta={meta.ndim}"
            )
        self._require_tensor("vision_obs", dual, dual.ndim)
        self._require_tensor("context_vision_obs", head, head.ndim)
        self._require_tensor("camera_meta", meta, expected_meta_ndim, 6)
        expected_dual = (384, 216, 6)
        expected_head = (136, 384, 3)
        if tuple(dual.shape[-3:]) != expected_dual or tuple(head.shape[-3:]) != expected_head:
            raise ValueError(f"C-B2H image shapes must be {expected_dual} and {expected_head}; got {tuple(dual.shape)} and {tuple(head.shape)}")
        if dual.shape[:-3] != head.shape[:-3] or dual.shape[:-3] != meta.shape[:-1]:
            raise ValueError("C-B2H view leading shapes must match")
        if dual.device != head.device or dual.device != meta.device:
            raise ValueError("C-B2H view tensors must share one device")
        if dual.ndim == 4:
            if masks is not None:
                raise ValueError("C-B2H rollout observations do not accept recurrent masks")
        else:
            if masks is None or not torch.is_tensor(masks) or masks.dtype != torch.bool or masks.shape != dual.shape[:2]:
                raise ValueError("C-B2H sequence observations require boolean masks with shape [B,T]")
            if masks.device != dual.device or not bool(masks.any().item()):
                raise ValueError("C-B2H recurrent masks must share device and contain a valid timestep")
        ages = meta[..., :3]
        valid = meta[..., 3:]
        if bool((ages < 0.0).any().item()) or bool((ages > 1.0).any().item()):
            raise ValueError("C-B2H normalized camera ages must lie in [0,1]")
        if not bool(torch.all((valid == 0.0) | (valid == 1.0)).item()):
            raise ValueError("C-B2H camera validity metadata must be exactly 0 or 1")

    def _fuse(self, f_left, f_right, f_head, camera_meta):
        left = self.left_view_norm(f_left + self.left_view_embedding)
        right = self.right_view_norm(f_right + self.right_view_embedding)
        age_s = camera_meta[:, :3] * 0.1
        left_conf = camera_meta[:, 3] * torch.exp(-age_s[:, 0] / self.manipulation_tau_s)
        right_conf = camera_meta[:, 4] * torch.exp(-age_s[:, 1] / self.manipulation_tau_s)
        if not bool(((left_conf + right_conf) > 0.0).all().item()):
            raise ValueError("C-B2H requires at least one valid D435 view per row")
        manipulation_base = (left_conf[:, None] * left + right_conf[:, None] * right) / (left_conf + right_conf).clamp_min(torch.finfo(left.dtype).eps)[:, None]
        manipulation_input = torch.cat((left, right, (left - right).abs()), dim=-1)
        manipulation = self.manipulation_norm(manipulation_base + self.manipulation_residual(manipulation_input))

        head = self.head_view_norm(f_head + self.head_view_embedding)
        head_conf = camera_meta[:, 5] * torch.exp(-age_s[:, 2] / self.context_tau_s)
        context_input = torch.cat((manipulation, head, (manipulation - head).abs(), camera_meta), dim=-1)
        context_residual = self.context_residual(context_input)
        gate = self.context_gate(context_input)
        return self.context_norm(manipulation + head_conf[:, None] * (self.head_base_weight * head + gate * context_residual))

    def _encode_views(self, dual, head, meta, masks):
        self._validate_views(dual, head, meta, masks)
        sequence = dual.ndim == 5
        if sequence:
            batch_size, seq_len = dual.shape[:2]
            dual_flat, head_flat, meta_flat = dual.reshape(-1, *dual.shape[2:]), head.reshape(-1, *head.shape[2:]), meta.reshape(-1, 6)
            valid_mask = masks.reshape(-1)
            if not bool(valid_mask.any().item()):
                raise ValueError("C-B2H recurrent masks contain no valid frames")
            dual_flat, head_flat, meta_flat = dual_flat[valid_mask], head_flat[valid_mask], meta_flat[valid_mask]
        else:
            batch_size, seq_len, valid_mask = dual.shape[0], None, None
            dual_flat, head_flat, meta_flat = dual, head, meta
        left = dual_flat[..., :3].permute(0, 3, 1, 2).contiguous()
        right = dual_flat[..., 3:6].permute(0, 3, 1, 2).contiguous()
        f_left = self.d435i_vision_module(left).reshape(left.shape[0], 128)
        f_right = self.d435i_vision_module(right).reshape(right.shape[0], 128)
        count = left.shape[0]
        f_head = self.head_vision_module(head_flat.permute(0, 3, 1, 2).contiguous()).reshape(count, 128)
        fused = self._fuse(f_left, f_right, f_head, meta_flat)
        if not sequence:
            return fused
        latent_flat = fused.new_zeros((batch_size * seq_len, 128))
        latent_flat[valid_mask] = fused
        return latent_flat.reshape(batch_size, seq_len, 128).contiguous()

    def forward(self, obs_dict, masks=None, hidden_states=None, episode_attnmask=None, **kwargs):
        del episode_attnmask, kwargs
        obs_dict = obs_dict.copy()
        actor_obs = self._normalize_actor_obs(obs_dict[self.input_key], masks)
        dual = obs_dict[self.manipulation_vision_key]
        head = obs_dict[self.context_vision_key]
        meta = obs_dict[self.camera_meta_key]
        latent = self._encode_views(dual, head, meta, masks)
        recurrent_input = torch.cat((actor_obs, latent), dim=-1)
        if recurrent_input.ndim == 2:
            memory_out = self.memory(recurrent_input)
            if memory_out.ndim == 3:
                memory_out = memory_out.squeeze(0)
        elif recurrent_input.ndim == 3:
            memory_out = self.memory(recurrent_input.transpose(0, 1), masks=masks, hidden_states=hidden_states)
        else:
            raise ValueError("C-B2H recurrent input must be 2D or 3D")
        return self.mlp_module(memory_out)

    @property
    def has_normalized_actions(self):
        return False

    def _normalize_actor_obs(self, actor_obs, masks):
        if not torch.is_tensor(actor_obs) or actor_obs.ndim not in (2, 3):
            raise ValueError(
                "C-B2H actor_obs must be a finite [B,81] or [B,T,81] tensor; "
                f"got {getattr(actor_obs, 'shape', None)}"
            )
        self._require_tensor("actor_obs", actor_obs, actor_obs.ndim, 81)
        if actor_obs.ndim == 2:
            if masks is not None:
                raise ValueError("C-B2H recurrent masks are only valid for sequence observations")
            return self.running_mean_std(actor_obs) if self.running_mean_std is not None else actor_obs
        if actor_obs.ndim != 3 or masks is None or masks.dtype != torch.bool or masks.shape != actor_obs.shape[:2]:
            raise ValueError("C-B2H actor_obs must be [B,81] or [B,T,81] with matching boolean masks")
        if self.running_mean_std is None:
            return torch.where(masks[..., None], actor_obs, torch.zeros_like(actor_obs))
        flat = actor_obs.reshape(-1, 81)
        flat_mask = masks.reshape(-1)
        mean = self.running_mean_std.running_mean.to(actor_obs)
        var = self.running_mean_std.running_var.to(actor_obs)
        normalized = (flat - mean) / torch.sqrt(var + self.running_mean_std.epsilon)
        normalized = torch.clamp(normalized, -5.0, 5.0)
        return torch.where(flat_mask[:, None], normalized, torch.zeros_like(normalized)).reshape_as(actor_obs)

    def _update_obs_buffer(self, obs_dict, episode_attnmask=None, cur_dones=None):
        del cur_dones
        update_episode_attnmask = False
        for key, value in obs_dict.items():
            if key not in self.obs_dict_buffer:
                self.obs_dict_buffer[key] = value.unsqueeze(1)
            else:
                self.obs_dict_buffer[key] = torch.cat((self.obs_dict_buffer[key], value.unsqueeze(1)), dim=1)
            if self.obs_dict_buffer[key].shape[1] > self.max_rollout_history:
                update_episode_attnmask = True
                self.obs_dict_buffer[key] = self.obs_dict_buffer[key][:, -self.max_rollout_history:]
        if episode_attnmask is not None and update_episode_attnmask:
            return episode_attnmask[:, -self.max_rollout_history:, -self.max_rollout_history:]
        return episode_attnmask

    def init_rollout(self):
        """Initialize rollout-only buffers without resetting recurrent state."""
        self.obs_dict_buffer = {}
        self.dones_buffer = None
        self.steps = 0

    def clear_rollout(self):
        """Clear rollout buffers and detach/reset transient distribution state."""
        self.obs_dict_buffer = {}
        self.dones_buffer = None
        self.steps = 0
        self.distribution = None
        self.memory.detach_hidden_states()

    def reset(self, dones=None):
        self.memory.reset(dones)

    def get_hidden_states(self):
        return self.memory.hidden_states

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        episode_attnmask = self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        del episode_attnmask, kwargs
        obs_dict = obs_dict.copy()
        with torch.no_grad():
            actor_obs = self._normalize_actor_obs(obs_dict[self.input_key], None)
            latent = self._encode_views(obs_dict[self.manipulation_vision_key], obs_dict[self.context_vision_key], obs_dict[self.camera_meta_key], None)
            memory_out = self.memory(torch.cat((actor_obs, latent), dim=-1))
            if memory_out.ndim == 3:
                memory_out = memory_out.squeeze(0)
            mean = self.mlp_module(memory_out)
        if self.clamp_noise_std:
            with torch.no_grad():
                self.std.clamp_(max=self.max_noise_std)
        self.distribution = Normal(mean, mean * 0.0 + self.std)
        self.steps += 1
        return {"actions": self.distribution.sample(), "action_mean": self.action_mean, "action_sigma": self.action_std}

    def act_inference(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        episode_attnmask = self._update_obs_buffer(obs_dict, episode_attnmask, cur_dones)
        del episode_attnmask, kwargs
        obs_dict = obs_dict.copy()
        actor_obs = self._normalize_actor_obs(obs_dict[self.input_key], None)
        latent = self._encode_views(obs_dict[self.manipulation_vision_key], obs_dict[self.context_vision_key], obs_dict[self.camera_meta_key], None)
        memory_out = self.memory(torch.cat((actor_obs, latent), dim=-1))
        if memory_out.ndim == 3:
            memory_out = memory_out.squeeze(0)
        self.steps += 1
        return self.mlp_module(memory_out)

    def act(self, obs_dict, episode_attnmask=None, masks=None, hidden_states=None, **kwargs):
        mean = self.forward(obs_dict, masks=masks, hidden_states=hidden_states, episode_attnmask=episode_attnmask, **kwargs)
        if self.clamp_noise_std:
            with torch.no_grad():
                self.std.clamp_(max=self.max_noise_std)
        self.distribution = Normal(mean, mean * 0.0 + self.std)
        return {"actions": self.distribution.sample(), "action_mean": self.action_mean, "action_sigma": self.action_std}

    def update_distribution(self, obs_dict, episode_attnmask=None, last_step_only=False, masks=None, hidden_states=None, **kwargs):
        mean = self.forward(obs_dict, masks=masks, hidden_states=hidden_states, episode_attnmask=episode_attnmask, **kwargs)
        if last_step_only:
            mean = mean[:, -1]
        if self.clamp_noise_std:
            with torch.no_grad():
                self.std.clamp_(max=self.max_noise_std)
        self.distribution = Normal(mean, mean * 0.0 + self.std)

    @property
    def action_mean(self):
        if self.distribution is None:
            raise RuntimeError("C-B2H action distribution is unavailable before forward")
        return self.distribution.mean

    @property
    def action_std(self):
        if self.distribution is None:
            raise RuntimeError("C-B2H action distribution is unavailable before forward")
        return self.distribution.stddev

    def get_actions_log_prob(self, actions):
        if self.distribution is None:
            raise RuntimeError("C-B2H action distribution is unavailable before sampling")
        return self.distribution.log_prob(actions).sum(dim=-1)


__all__ = ["TriViewContextSharedEncoderVisionRecurrentActor"]
