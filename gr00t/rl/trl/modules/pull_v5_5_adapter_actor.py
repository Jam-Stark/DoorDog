"""Three-axis adapter policy with a deterministic A2 high-level carrier."""

from __future__ import annotations

import math
from collections.abc import Mapping

import torch
from torch import nn
from torch.distributions import Normal


ADAPTER_OBS_DIM = 12
ADAPTER_ACTION_DIM = 3
HIGH_LEVEL_ACTION_DIM = 12
FROZEN_LEG_ACTION_DIM = 12
A2_BASE_OBS_DIM = 1620
A2_BASE_FRAME_DIM = 54
A2_BASE_COMMAND_SCALE = 0.25
A2_BASE_COMMAND_MULTIPLIERS = (2.0, 2.0, 0.25, 1.0, 1.0)
RAW_ACTION_LOW = (-0.30, 0.0, -2.0)
RAW_ACTION_HIGH = (0.0, 0.24, 2.0)
# Use a representable binary margin shared by tanh, atanh, and action
# round-trips (including float16), rather than letting endpoint rounding
# produce a raw-action/log-prob mismatch.
TANH_INVERSE_EPS = 2.0 ** -10
TANH_RAW_LIMIT = math.atanh(1.0 - TANH_INVERSE_EPS)


def _validate_observation(observation: torch.Tensor, obs_dim: int = ADAPTER_OBS_DIM) -> None:
    if not torch.is_tensor(observation) or observation.shape[-1] != obs_dim:
        raise ValueError(f"adapter observation must end with dimension {obs_dim}")
    if not observation.is_floating_point() or not torch.all(torch.isfinite(observation)):
        raise ValueError("adapter observation must be finite floating point")


class PullV55AdapterActor(nn.Module):
    """A non-recurrent actor exposing 12 carrier axes and 3 stochastic axes.

    The first three carrier values are tanh-bounded adapter commands.  Carrier
    indices 3:11 are fixed zeros and index 11 is the fixed open-gripper
    primitive.  Their reported mean/std are constant (0/1, except gripper
    mean 1) so the inherited PPO KL has no padded-axis contribution.
    """

    is_recurrent = False
    has_normalized_actions = False
    num_actions = HIGH_LEVEL_ACTION_DIM
    action_dim = HIGH_LEVEL_ACTION_DIM

    def __init__(
        self,
        obs_dim: int = ADAPTER_OBS_DIM,
        hidden_dims: tuple[int, ...] = (128, 64),
        init_log_std: float = -0.5,
        action_low: tuple[float, float, float] = RAW_ACTION_LOW,
        action_high: tuple[float, float, float] = RAW_ACTION_HIGH,
        num_actions: int = HIGH_LEVEL_ACTION_DIM,
        frozen_a2_base_model: nn.Module | None = None,
        env_config=None,
        algo_config=None,
        module_dim_dict=None,
        **_,
    ) -> None:
        super().__init__()
        del env_config, module_dim_dict
        if obs_dim != ADAPTER_OBS_DIM:
            raise ValueError(f"pull-v5.5 adapter observation contract is exactly 12, got {obs_dim}")
        if num_actions != HIGH_LEVEL_ACTION_DIM:
            raise ValueError(f"adapter carrier action contract is exactly 12, got {num_actions}")
        if not isinstance(algo_config, Mapping) or "max_noise_std" not in algo_config:
            raise ValueError("pull-v5.5 adapter actor requires algo.config.max_noise_std")
        configured_max_noise_std = algo_config["max_noise_std"]
        if isinstance(configured_max_noise_std, bool):
            raise ValueError("algo.config.max_noise_std must be a positive finite number")
        try:
            configured_max_noise_std = float(configured_max_noise_std)
        except (TypeError, ValueError) as exc:
            raise ValueError("algo.config.max_noise_std must be a positive finite number") from exc
        if not math.isfinite(configured_max_noise_std) or configured_max_noise_std <= 0.0:
            raise ValueError("algo.config.max_noise_std must be a positive finite number")
        self.max_noise_std = configured_max_noise_std
        if len(hidden_dims) == 0 or any(int(width) <= 0 for width in hidden_dims):
            raise ValueError("adapter hidden_dims must contain positive widths")
        if len(action_low) != ADAPTER_ACTION_DIM or len(action_high) != ADAPTER_ACTION_DIM:
            raise ValueError("adapter bounds must contain exactly three trainable values")
        action_low = tuple(float(value) for value in action_low)
        action_high = tuple(float(value) for value in action_high)
        if any(not math.isfinite(value) for value in action_low + action_high):
            raise ValueError("adapter bounds must be finite")
        if any(low >= high for low, high in zip(action_low, action_high)):
            raise ValueError("adapter bounds must be strictly ordered")

        layers: list[nn.Module] = []
        input_dim = ADAPTER_OBS_DIM
        for width in hidden_dims:
            layers.extend((nn.Linear(input_dim, int(width)), nn.SiLU()))
            input_dim = int(width)
        layers.append(nn.Linear(input_dim, ADAPTER_ACTION_DIM))
        self.backbone = nn.Sequential(*layers)
        self.log_std = nn.Parameter(torch.full((ADAPTER_ACTION_DIM,), float(init_log_std)))
        self.register_buffer("action_low", torch.tensor(action_low, dtype=torch.float32))
        self.register_buffer("action_high", torch.tensor(action_high, dtype=torch.float32))
        self._distribution: Normal | None = None
        self._last_log_prob: torch.Tensor | None = None
        self._current_entropy: torch.Tensor | None = None
        self._frozen_a2_base_model = frozen_a2_base_model
        if frozen_a2_base_model is not None:
            for parameter in frozen_a2_base_model.parameters():
                parameter.requires_grad_(False)
            frozen_a2_base_model.eval()
        self.steps = 0
        self.is_eval_mode = False

    @staticmethod
    def _observation_from_input(obs_or_dict: torch.Tensor | Mapping[str, torch.Tensor]) -> torch.Tensor:
        if isinstance(obs_or_dict, Mapping):
            if "actor_obs" not in obs_or_dict:
                raise KeyError("adapter actor requires obs_dict['actor_obs']")
            return obs_or_dict["actor_obs"]
        return obs_or_dict

    def raw_mean(self, observation: torch.Tensor) -> torch.Tensor:
        _validate_observation(observation)
        return self.backbone(observation)

    def _bounded_from_raw(self, raw_action: torch.Tensor) -> torch.Tensor:
        if raw_action.shape[-1] != ADAPTER_ACTION_DIM:
            raise ValueError("raw adapter action must expose exactly three values")
        raw_action = self._clip_raw_action(raw_action)
        low = self.action_low.to(device=raw_action.device, dtype=raw_action.dtype)
        high = self.action_high.to(device=raw_action.device, dtype=raw_action.dtype)
        return low + 0.5 * (torch.tanh(raw_action) + 1.0) * (high - low)

    def _clip_raw_action(self, raw_action: torch.Tensor) -> torch.Tensor:
        if raw_action.shape[-1] != ADAPTER_ACTION_DIM:
            raise ValueError("raw adapter action must expose exactly three values")
        if not torch.all(torch.isfinite(raw_action)):
            raise ValueError("raw adapter action must be finite floating point")
        return raw_action.clamp(min=-TANH_RAW_LIMIT, max=TANH_RAW_LIMIT)

    @staticmethod
    def _bound_raw_mean(raw_mean: torch.Tensor) -> torch.Tensor:
        # Smoothly map arbitrary network outputs into the finite inverse-tanh
        # interval used by rollout actions and their recovered log-probabilities.
        return torch.tanh(raw_mean) * TANH_RAW_LIMIT

    def _carrier(self, adapter_values: torch.Tensor, *, bounded: bool) -> torch.Tensor:
        if adapter_values.shape[-1] != ADAPTER_ACTION_DIM:
            raise ValueError("adapter values must expose exactly three axes")
        carrier = torch.zeros(
            *adapter_values.shape[:-1],
            HIGH_LEVEL_ACTION_DIM,
            dtype=adapter_values.dtype,
            device=adapter_values.device,
        )
        carrier[..., :3] = self._bounded_from_raw(adapter_values) if bounded else adapter_values
        carrier[..., 11] = 1.0
        return carrier

    def _carrier_std(self, raw_std: torch.Tensor) -> torch.Tensor:
        carrier = torch.ones(
            *raw_std.shape[:-1],
            HIGH_LEVEL_ACTION_DIM,
            dtype=raw_std.dtype,
            device=raw_std.device,
        )
        carrier[..., :3] = raw_std
        return carrier

    def _validate_carrier_padding(self, actions: torch.Tensor) -> torch.Tensor:
        if actions.shape[-1] == ADAPTER_ACTION_DIM:
            return actions
        if actions.shape[-1] != HIGH_LEVEL_ACTION_DIM:
            raise ValueError("adapter actions must have three axes or a canonical 12-D carrier")
        expected = torch.zeros_like(actions[..., 3:11])
        if not torch.equal(actions[..., 3:11], expected) or not torch.all(actions[..., 11] == 1.0):
            raise ValueError("adapter carrier padded axes must be deterministic zeros/open-gripper")
        return actions[..., :3]

    def _raw_from_bounded(self, actions: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        adapter_actions = self._validate_carrier_padding(actions)
        if not adapter_actions.is_floating_point() or not torch.all(torch.isfinite(adapter_actions)):
            raise ValueError("adapter actions must be finite floating point")
        low = self.action_low.to(device=adapter_actions.device, dtype=adapter_actions.dtype)
        high = self.action_high.to(device=adapter_actions.device, dtype=adapter_actions.dtype)
        span = high - low
        normalized = (adapter_actions - low) / span
        squashed = (normalized * 2.0 - 1.0).clamp(
            min=-1.0 + TANH_INVERSE_EPS,
            max=1.0 - TANH_INVERSE_EPS,
        )
        raw = self._clip_raw_action(torch.atanh(squashed))
        correction = torch.log(span * 0.5) + torch.log1p(-squashed.square())
        return raw, correction.sum(dim=-1)

    def update_distribution(
        self,
        obs_dict: torch.Tensor | Mapping[str, torch.Tensor],
        *,
        last_step_only: bool = False,
        **_,
    ) -> Normal:
        observation = self._observation_from_input(obs_dict)
        if last_step_only and observation.ndim > 2:
            observation = observation[:, -1]
        _validate_observation(observation)
        mean = self._bound_raw_mean(self.raw_mean(observation))
        std = self.log_std.exp().to(device=mean.device, dtype=mean.dtype)
        std = std.clamp(max=self.max_noise_std).expand_as(mean)
        self._distribution = Normal(mean, std)
        self._current_entropy = self._distribution.entropy().sum(dim=-1)
        return self._distribution

    @property
    def distribution(self) -> Normal:
        if self._distribution is None:
            raise RuntimeError("adapter distribution is not initialized")
        return self._distribution

    @property
    def raw_action_mean(self) -> torch.Tensor:
        return self._carrier(self.distribution.mean, bounded=False)

    @property
    def raw_action_std(self) -> torch.Tensor:
        return self._carrier_std(self.distribution.stddev)

    @property
    def action_mean(self) -> torch.Tensor:
        # Base PPO uses this property for old/new KL.  It is intentionally the
        # raw pre-tanh carrier, while rollout execution uses bounded actions.
        return self.raw_action_mean

    @property
    def action_std(self) -> torch.Tensor:
        return self.raw_action_std

    @property
    def bounded_action_mean(self) -> torch.Tensor:
        return self._carrier(self.distribution.mean, bounded=True)

    @property
    def entropy(self) -> torch.Tensor:
        if self._current_entropy is None:
            return self.distribution.entropy().sum(dim=-1)
        return self._current_entropy

    def _raw_log_prob(self, raw_action: torch.Tensor) -> torch.Tensor:
        if raw_action.shape[-1] != ADAPTER_ACTION_DIM:
            raise ValueError("raw adapter action must expose exactly three values")
        raw_action = self._clip_raw_action(raw_action)
        low = self.action_low.to(device=raw_action.device, dtype=raw_action.dtype)
        high = self.action_high.to(device=raw_action.device, dtype=raw_action.dtype)
        return (
            self.distribution.log_prob(raw_action)
            - torch.log(high - low)
            - math.log(0.5)
            - torch.log1p(-torch.tanh(raw_action).square())
        ).sum(dim=-1)

    def get_actions_log_prob(self, actions: torch.Tensor) -> torch.Tensor:
        raw_action, _ = self._raw_from_bounded(actions)
        self._last_log_prob = self._raw_log_prob(raw_action)
        return self._last_log_prob

    def act(self, obs_dict=None, *, observation=None, deterministic: bool = False, **kwargs):
        source = obs_dict if obs_dict is not None else observation
        self.update_distribution(source, **kwargs)
        raw_action = self.distribution.mean if deterministic else self.distribution.rsample()
        raw_action = self._clip_raw_action(raw_action)
        bounded_action = self._bounded_from_raw(raw_action)
        self._last_log_prob = self._raw_log_prob(raw_action)
        return {
            "actions": self._carrier(bounded_action, bounded=False),
            "action_mean": self.action_mean,
            "action_sigma": self.action_std,
            "action_std": self.action_std,
            "logprobs": self._last_log_prob,
            "entropy": self.entropy,
        }

    def rollout(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        del episode_attnmask, cur_dones
        result = self.act(obs_dict=obs_dict, deterministic=False, **kwargs)
        self.steps += 1
        return result

    def act_inference(self, obs_dict, episode_attnmask=None, cur_dones=None, **kwargs):
        del episode_attnmask, cur_dones
        result = self.act(obs_dict=obs_dict, deterministic=True, **kwargs)
        self.steps += 1
        return result["actions"]

    def sample(self, observation: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        result = self.act(observation=observation, deterministic=False)
        return result["actions"][..., :3], result["logprobs"]

    def pack_high_level_action(self, adapter_action: torch.Tensor) -> torch.Tensor:
        if adapter_action.shape[-1] == HIGH_LEVEL_ACTION_DIM:
            adapter_values = self._validate_carrier_padding(adapter_action)
            return adapter_action
        if adapter_action.shape[-1] != ADAPTER_ACTION_DIM:
            raise ValueError("adapter_action must expose exactly three axes or a canonical carrier")
        if not torch.is_tensor(adapter_action) or not torch.all(torch.isfinite(adapter_action)):
            raise ValueError("adapter_action must be finite floating point")
        return self._carrier(adapter_action, bounded=False)

    def infer_frozen_legs(self, a2_base_obs: torch.Tensor, high_level_action: torch.Tensor) -> torch.Tensor:
        if not torch.is_tensor(a2_base_obs) or a2_base_obs.shape[-1] != A2_BASE_OBS_DIM:
            raise ValueError(f"A2_Base observation must end with {A2_BASE_OBS_DIM}")
        if high_level_action.shape[-1] != HIGH_LEVEL_ACTION_DIM:
            raise ValueError("high_level_action must be the canonical 12-D carrier")
        if a2_base_obs.shape[:-1] != high_level_action.shape[:-1]:
            raise ValueError("A2_Base observation and carrier leading shapes must match")
        if self._frozen_a2_base_model is None:
            raise RuntimeError("frozen A2_Base model is required for leg inference")
        flat_obs = a2_base_obs.reshape(-1, A2_BASE_OBS_DIM).clone()
        flat_carrier = high_level_action.reshape(-1, HIGH_LEVEL_ACTION_DIM)
        frame_start = A2_BASE_OBS_DIM - A2_BASE_FRAME_DIM
        physical = torch.cat(
            (flat_carrier[:, :3] * A2_BASE_COMMAND_SCALE, flat_carrier[:, 3:5].clamp(-1.0, 1.0) * 0.4),
            dim=-1,
        )
        multipliers = torch.tensor(
            A2_BASE_COMMAND_MULTIPLIERS, device=flat_obs.device, dtype=flat_obs.dtype
        )
        flat_obs[:, frame_start + 39 : frame_start + 44] = physical * multipliers
        with torch.no_grad():
            legs = self._frozen_a2_base_model(flat_obs)
        if legs.shape[-1] != FROZEN_LEG_ACTION_DIM:
            raise ValueError("frozen A2_Base inference must return exactly twelve leg actions")
        return legs.reshape(*high_level_action.shape[:-1], FROZEN_LEG_ACTION_DIM)

    def build_executor_action(self, observation, a2_base_obs, *, deterministic: bool = False):
        result = self.act(observation=observation, deterministic=deterministic)
        high_level = result["actions"]
        legs = self.infer_frozen_legs(a2_base_obs, high_level)
        result["high_level_action"] = high_level
        result["frozen_leg_action"] = legs
        result["executor_actions"] = torch.cat((high_level, legs), dim=-1)
        result["adapter_active"] = torch.ones(
            observation.shape[:-1], dtype=torch.bool, device=observation.device
        )
        result["adapter_provenance"] = "pull_v5_5_terminal_probe"
        return result

    def reset(self, dones=None):
        if dones is not None and (not torch.is_tensor(dones) or dones.ndim != 1):
            raise ValueError("adapter actor reset dones must be a one-dimensional tensor")
        self._distribution = None
        self._last_log_prob = None
        self._current_entropy = None

    def init_rollout(self):
        self.steps = 0
        self._last_log_prob = None
        self._current_entropy = None

    def clear_rollout(self):
        self.steps = 0
        self._distribution = None
        self._last_log_prob = None
        self._current_entropy = None

    def eval_mode(self):
        self.is_eval_mode = True

    def train_mode(self):
        self.is_eval_mode = False

    forward = raw_mean
    pack_action = pack_high_level_action


class PullV55AdapterCritic(nn.Module):
    """State-value head for the 12-D non-privileged adapter observation."""

    is_recurrent = False

    def __init__(
        self,
        obs_dim: int = ADAPTER_OBS_DIM,
        hidden_dims: tuple[int, ...] = (128, 64),
        env_config=None,
        algo_config=None,
        module_dim_dict=None,
        **_,
    ) -> None:
        super().__init__()
        del env_config, algo_config, module_dim_dict
        if obs_dim != ADAPTER_OBS_DIM:
            raise ValueError("pull-v5.5 critic observation contract is exactly 12")
        layers: list[nn.Module] = []
        input_dim = ADAPTER_OBS_DIM
        for width in hidden_dims:
            layers.extend((nn.Linear(input_dim, int(width)), nn.SiLU()))
            input_dim = int(width)
        layers.append(nn.Linear(input_dim, 1))
        self.network = nn.Sequential(*layers)

    def reset(self, dones=None):
        pass

    def forward(self, observation: torch.Tensor) -> torch.Tensor:
        _validate_observation(observation)
        return self.network(observation)

    def evaluate(self, obs_dict: Mapping[str, torch.Tensor], **_) -> torch.Tensor:
        if "critic_obs" not in obs_dict:
            raise KeyError("adapter critic requires obs_dict['critic_obs']")
        return self.forward(obs_dict["critic_obs"])


__all__ = [
    "ADAPTER_OBS_DIM",
    "ADAPTER_ACTION_DIM",
    "HIGH_LEVEL_ACTION_DIM",
    "FROZEN_LEG_ACTION_DIM",
    "RAW_ACTION_LOW",
    "RAW_ACTION_HIGH",
    "TANH_INVERSE_EPS",
    "TANH_RAW_LIMIT",
    "PullV55AdapterActor",
    "PullV55AdapterCritic",
]
