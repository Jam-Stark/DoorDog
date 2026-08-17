"""HOMIE/A2 dog specialist for the pull-v5.6 terminal-hold rung."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

import torch
from torch import nn
from torch.distributions import Normal


SPECIALIST_OBS_DIM = 1620
SPECIALIST_LATENT_DIM = 25
SPECIALIST_ACTION_DIM = 12
SPECIALIST_ACTOR_INPUT_DIM = SPECIALIST_OBS_DIM + SPECIALIST_LATENT_DIM
SPECIALIST_RAW_CHECKPOINT = (
    "/home/baoquanc/workspace/LMP/logs/manager_dual_rl/lmp_dual_policy/"
    "stage1_locomotion_a2_piper/2026-06-05_16-12-09/checkpoints_dog/ac_weights_last.pt"
)
FRESH_DOG_STD = 1.0
REGISTERED_MAX_NOISE_STD = 1.0


def _elu_mlp(input_dim: int, hidden_dims: tuple[int, ...], output_dim: int) -> nn.Sequential:
    layers: list[nn.Module] = []
    last_dim = input_dim
    for width in hidden_dims:
        layers.extend((nn.Linear(last_dim, width), nn.ELU()))
        last_dim = width
    layers.append(nn.Linear(last_dim, output_dim))
    return nn.Sequential(*layers)


def _state_dict_from_checkpoint(path: Path) -> Mapping[str, torch.Tensor]:
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"v5.6 specialist source checkpoint is missing: {path}")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping):
        raise TypeError("v5.6 specialist source checkpoint must contain a mapping")
    state = payload.get("dog_model", payload.get("state_dict", payload))
    if not isinstance(state, Mapping):
        raise TypeError("v5.6 specialist source checkpoint state must be a mapping")
    return state


class PullV56HoldSpecialistActor(nn.Module):
    """Eager reconstruction of the original dog actor with trainable leg noise.

    The raw A2 dog actor is loaded into the adaptation and actor branches.  The
    source ``std`` tensor is intentionally ignored: rung-3 fine-tuning starts
    with the original fresh-training standard deviation of one.
    """

    is_recurrent = False
    has_normalized_actions = False
    num_actions = SPECIALIST_ACTION_DIM
    action_dim = SPECIALIST_ACTION_DIM

    def __init__(
        self,
        raw_checkpoint_path: str = SPECIALIST_RAW_CHECKPOINT,
        obs_dim: int = SPECIALIST_OBS_DIM,
        latent_dim: int = SPECIALIST_LATENT_DIM,
        num_actions: int = SPECIALIST_ACTION_DIM,
        init_noise_std: float = FRESH_DOG_STD,
        max_noise_std: float | None = None,
        algo_config: Mapping[str, object] | None = None,
        **_,
    ) -> None:
        super().__init__()
        if obs_dim != SPECIALIST_OBS_DIM or latent_dim != SPECIALIST_LATENT_DIM:
            raise ValueError("v5.6 specialist requires the exact 1620/25 dog contract")
        if num_actions != SPECIALIST_ACTION_DIM:
            raise ValueError("v5.6 specialist requires exactly twelve leg actions")
        if not math.isfinite(float(init_noise_std)) or float(init_noise_std) != FRESH_DOG_STD:
            raise ValueError("v5.6 specialist std must reset to the original fresh value 1.0")
        if max_noise_std is None and isinstance(algo_config, Mapping):
            max_noise_std = algo_config.get("max_noise_std", REGISTERED_MAX_NOISE_STD)
        if max_noise_std is None:
            max_noise_std = REGISTERED_MAX_NOISE_STD
        if (
            isinstance(max_noise_std, bool)
            or not isinstance(max_noise_std, (int, float))
            or not math.isfinite(float(max_noise_std))
            or float(max_noise_std) <= 0.0
            or float(max_noise_std) > REGISTERED_MAX_NOISE_STD
        ):
            raise ValueError("v5.6 max_noise_std must be finite, positive, and no greater than 1.0")
        self.max_noise_std = float(max_noise_std)

        self.adaptation_module = _elu_mlp(SPECIALIST_OBS_DIM, (256, 128), SPECIALIST_LATENT_DIM)
        self.actor_body = _elu_mlp(SPECIALIST_ACTOR_INPUT_DIM, (512, 256, 128), SPECIALIST_ACTION_DIM)
        self.log_std = nn.Parameter(
            torch.full((SPECIALIST_ACTION_DIM,), math.log(FRESH_DOG_STD), dtype=torch.float32)
        )
        self.raw_checkpoint_path = str(Path(raw_checkpoint_path).expanduser().resolve())
        state = _state_dict_from_checkpoint(Path(self.raw_checkpoint_path))
        actor_state = {
            key: value
            for key, value in state.items()
            if key.startswith("adaptation_module.") or key.startswith("actor_body.")
        }
        missing, unexpected = self.load_state_dict(actor_state, strict=False)
        if missing != ["log_std"] or unexpected:
            raise RuntimeError(
                "v5.6 specialist actor warm-start keys are incompatible: "
                f"missing={missing}, unexpected={unexpected}"
            )
        self._distribution: Normal | None = None
        self._current_entropy: torch.Tensor | None = None
        self._last_log_prob: torch.Tensor | None = None
        self.steps = 0
        self.is_eval_mode = False

    @property
    def fresh_std(self) -> torch.Tensor:
        return self.log_std.exp().clamp(max=self.max_noise_std)

    @property
    def distribution(self) -> Normal:
        if self._distribution is None:
            raise RuntimeError("v5.6 specialist distribution is not initialized")
        return self._distribution

    @staticmethod
    def _observation(obs_dict: torch.Tensor | Mapping[str, torch.Tensor]) -> torch.Tensor:
        if isinstance(obs_dict, Mapping):
            if "actor_obs" not in obs_dict:
                raise KeyError("v5.6 specialist requires obs_dict['actor_obs']")
            observation = obs_dict["actor_obs"]
        else:
            observation = obs_dict
        if (
            not torch.is_tensor(observation)
            or observation.shape[-1] != SPECIALIST_OBS_DIM
            or not observation.is_floating_point()
            or not torch.all(torch.isfinite(observation))
        ):
            raise ValueError("v5.6 specialist observations must be finite floating 1620-D tensors")
        return observation

    def update_distribution(self, obs_dict: torch.Tensor | Mapping[str, torch.Tensor]) -> Normal:
        observation = self._observation(obs_dict)
        latent = self.adaptation_module(observation)
        mean = self.actor_body(torch.cat((observation, latent), dim=-1))
        std = self.fresh_std.to(device=mean.device, dtype=mean.dtype).expand_as(mean)
        self._distribution = Normal(mean, std)
        self._current_entropy = self._distribution.entropy().sum(dim=-1)
        return self._distribution

    @property
    def action_mean(self) -> torch.Tensor:
        return self.distribution.mean

    @property
    def action_sigma(self) -> torch.Tensor:
        return self.distribution.stddev

    @property
    def action_std(self) -> torch.Tensor:
        return self.action_sigma

    @property
    def entropy(self) -> torch.Tensor:
        if self._current_entropy is None:
            return self.distribution.entropy().sum(dim=-1)
        return self._current_entropy

    def get_actions_log_prob(self, actions: torch.Tensor) -> torch.Tensor:
        if (
            not torch.is_tensor(actions)
            or actions.shape[-1] != SPECIALIST_ACTION_DIM
            or actions.shape[:-1] != self.distribution.mean.shape[:-1]
        ):
            raise ValueError("v5.6 specialist likelihood actions must match the 12-D sampled legs")
        if not actions.is_floating_point() or not torch.all(torch.isfinite(actions)):
            raise ValueError("v5.6 specialist likelihood actions must be finite floating point")
        self._last_log_prob = self.distribution.log_prob(actions).sum(dim=-1)
        return self._last_log_prob

    def act(self, obs_dict=None, *, observation=None, deterministic: bool = False, **_) -> dict[str, torch.Tensor]:
        source = obs_dict if obs_dict is not None else observation
        self.update_distribution(source)
        actions = self.distribution.mean if deterministic else self.distribution.rsample()
        log_prob = self.get_actions_log_prob(actions)
        return {
            "actions": actions,
            "action_mean": self.action_mean,
            "action_sigma": self.action_sigma,
            "action_std": self.action_sigma,
            "logprobs": log_prob,
            "entropy": self.entropy,
        }

    def rollout(self, obs_dict, **_) -> dict[str, torch.Tensor]:
        self.steps += 1
        return self.act(obs_dict=obs_dict, deterministic=False)

    def act_inference(self, obs_dict, **_) -> torch.Tensor:
        self.steps += 1
        return self.act(obs_dict=obs_dict, deterministic=True)["actions"]

    def init_rollout(self) -> None:
        return None

    def clear_rollout(self) -> None:
        return None

    def reset(self, _dones=None) -> None:
        return None

    def train_mode(self) -> None:
        self.is_eval_mode = False
        self.train()

    def eval_mode(self) -> None:
        self.is_eval_mode = True
        self.eval()


class PullV56HoldSpecialistCritic(nn.Module):
    """Fresh critic for the non-privileged holdtrack observations."""

    is_recurrent = False

    def __init__(self, obs_dim: int = 12, hidden_dims: tuple[int, ...] = (128, 64), **_) -> None:
        super().__init__()
        if obs_dim != 12:
            raise ValueError("v5.6 holdtrack critic expects twelve non-privileged features")
        self.value_body = _elu_mlp(obs_dim, hidden_dims, 1)

    def evaluate(self, obs_dict: Mapping[str, torch.Tensor], **_) -> torch.Tensor:
        observation = obs_dict["critic_obs"]
        if observation.shape[-1] != 12:
            raise ValueError("v5.6 critic observation must expose twelve features")
        return self.value_body(observation)

    def forward(self, obs_dict: Mapping[str, torch.Tensor], **_) -> torch.Tensor:
        return self.evaluate(obs_dict)

    def reset(self, _dones=None) -> None:
        return None


__all__ = [
    "FRESH_DOG_STD",
    "REGISTERED_MAX_NOISE_STD",
    "SPECIALIST_ACTION_DIM",
    "SPECIALIST_LATENT_DIM",
    "SPECIALIST_OBS_DIM",
    "SPECIALIST_RAW_CHECKPOINT",
    "PullV56HoldSpecialistActor",
    "PullV56HoldSpecialistCritic",
]
