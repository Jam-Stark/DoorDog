"""CPU deployment boundary for the DepthADD v3 Student policy bundle."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from omegaconf import OmegaConf


DEFAULT_SOURCE_WORKSPACE = Path(
    "/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103"
)
DEFAULT_BUNDLE_DIR = (
    DEFAULT_SOURCE_WORKSPACE
    / "logs_eval/by_batch/depthadd_v3_20260825/sim2sim_handoff_step12000"
)
ACTOR_TARGET = (
    "gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent."
    "DualRGBDHeadVisionRecurrentDepthADDActor"
)
EXPECTED_GLOBAL_STEP = 12000
EXPECTED_POLICY_TENSOR_COUNT = 293
_REQUIRED_OBS_SHAPES = {
    "actor_obs": (81,),
    "vision_obs": (384, 216, 8),
    "context_vision_obs": (136, 384, 3),
    "camera_meta": (6,),
}


def _required(mapping: Any, *path: str) -> Any:
    value = mapping
    for key in path:
        try:
            value = value[key]
        except (KeyError, TypeError) as error:
            raise KeyError(f"resolved config is missing {'.'.join(path)}") from error
    return value


def _global_step(payload: Mapping[str, Any]) -> int:
    state = payload.get("state")
    global_step = getattr(state, "global_step", None)
    if global_step is None and isinstance(state, Mapping):
        global_step = state.get("global_step")
    if isinstance(global_step, bool) or not isinstance(global_step, int):
        raise RuntimeError("Student checkpoint state.global_step is missing or non-integer")
    if global_step != EXPECTED_GLOBAL_STEP:
        raise RuntimeError(
            f"Student checkpoint state.global_step must be {EXPECTED_GLOBAL_STEP}, got {global_step}"
        )
    return global_step


def _validate_contract(config: Any) -> None:
    actor = _required(config, "algo", "config", "actor")
    if actor.get("_target_") != ACTOR_TARGET:
        raise RuntimeError(f"DepthADD actor target mismatch: {actor.get('_target_')!r}")
    if int(actor.get("dual_d435_channels", -1)) != 8:
        raise RuntimeError("DepthADD actor requires dual_d435_channels=8")
    if int(_required(actor, "view_contract", "camera_meta_dim")) != 6:
        raise RuntimeError("DepthADD actor requires camera_meta_dim=6")
    if _required(actor, "view_contract", "d435i_forward_mode") != "packed":
        raise RuntimeError("DepthADD actor requires packed D435 forwarding")
    if int(_required(actor, "backbone", "d435i_vision_module", "module_config_dict", "layer_config", "in_channels")) != 4:
        raise RuntimeError("DepthADD shared encoder must use a 4-channel RGB-D view")
    if list(_required(actor, "backbone", "mlp_module", "module_config_dict", "output_dim")) != [12]:
        raise RuntimeError("DepthADD actor MLP must output 12 actions")
    algo = _required(config, "algo", "config")
    if int(algo.get("student_action_dim", -1)) != 12 or int(algo.get("rollout_action_dim", -1)) != 24:
        raise RuntimeError("DepthADD Student/rollout action contract must be 12D/24D")
    obs_dims = _required(config, "env", "config", "robot", "algo_obs_dim_dict")
    expected_flat_dims = {"actor_obs": 81, "vision_obs": 384 * 216 * 8, "context_vision_obs": 136 * 384 * 3, "camera_meta": 6}
    for key, expected in expected_flat_dims.items():
        if int(obs_dims.get(key, -1)) != expected:
            raise RuntimeError(f"DepthADD {key} contract must be {expected}, got {obs_dims.get(key)!r}")
    camera_output = _required(config, "simulator", "config", "cameras", "policy_multiview", "output_shape")
    if list(camera_output) != [384, 216, 8]:
        raise RuntimeError(f"DepthADD packed D435 shape must be [384, 216, 8], got {camera_output!r}")


def _inject_source_workspace(source_workspace: Path) -> None:
    source_root = source_workspace.resolve(strict=True)
    source_rl = source_root / "gr00t" / "rl"
    if not source_rl.is_dir():
        raise FileNotFoundError(f"DepthADD source workspace lacks gr00t/rl: {source_rl}")
    import gr00t.rl

    source_rl_string = str(source_rl)
    gr00t.rl.__path__ = [source_rl_string, *(item for item in gr00t.rl.__path__ if item != source_rl_string)]
    source_root_string = str(source_root)
    if source_root_string not in sys.path:
        sys.path.insert(0, source_root_string)


@dataclass
class DepthADDV3Policy:
    """Loaded recurrent Student plus frozen A2_Base leg controller."""

    actor: torch.nn.Module
    a2_base: torch.jit.ScriptModule
    bundle_dir: Path
    global_step: int
    device: torch.device

    def reset(self) -> None:
        self.actor.init_rollout()
        self.actor.reset()

    def act_inference(self, obs: Mapping[str, torch.Tensor]) -> torch.Tensor:
        if set(obs) != set(_REQUIRED_OBS_SHAPES):
            raise ValueError(f"DepthADD observations must be exactly {tuple(_REQUIRED_OBS_SHAPES)}, got {tuple(obs)}")
        batch_size = None
        for name, trailing_shape in _REQUIRED_OBS_SHAPES.items():
            value = obs[name]
            if value.dtype != torch.float32 or value.device != self.device:
                raise ValueError(
                    f"DepthADD {name} must be {self.device} float32, got {value.device} {value.dtype}"
                )
            if value.ndim != len(trailing_shape) + 1 or tuple(value.shape[1:]) != trailing_shape:
                raise ValueError(f"DepthADD {name} must have shape [B,{','.join(map(str, trailing_shape))}], got {tuple(value.shape)}")
            if batch_size is None:
                batch_size = value.shape[0]
            elif value.shape[0] != batch_size:
                raise ValueError("DepthADD observation batches differ")
        with torch.inference_mode():
            action_mean = self.actor.act_inference(dict(obs))
        if tuple(action_mean.shape) != (batch_size, 12) or not bool(torch.isfinite(action_mean).all()):
            raise RuntimeError(f"DepthADD actor returned invalid deterministic action {tuple(action_mean.shape)}")
        return action_mean

    def act_a2_base(self, history: torch.Tensor) -> torch.Tensor:
        if history.dtype != torch.float32 or history.device != self.device or history.ndim != 2 or history.shape[1] != 1620:
            raise ValueError(
                f"A2_Base history must be {self.device} float32 [B,1620], "
                f"got {history.device} {history.dtype} {tuple(history.shape)}"
            )
        with torch.inference_mode():
            leg_action = self.a2_base(history)
        if tuple(leg_action.shape) != (history.shape[0], 12) or not bool(torch.isfinite(leg_action).all()):
            raise RuntimeError(f"A2_Base returned invalid leg action {tuple(leg_action.shape)}")
        return leg_action


def load_depthadd_v3_policy(
    bundle_dir: Path = DEFAULT_BUNDLE_DIR,
    *,
    source_workspace: Path = DEFAULT_SOURCE_WORKSPACE,
    device: torch.device | str = "cpu",
) -> DepthADDV3Policy:
    """Rebuild and strict-load the handoff's DepthADD v3 policy pair."""
    bundle_dir = Path(bundle_dir).resolve(strict=True)
    device = torch.device(device)
    config_path = bundle_dir / "resolved_config.yaml"
    checkpoint_path = bundle_dir / "student_model_step_012000.pt"
    a2_base_path = bundle_dir / "a2_base_policy.pt"
    config = OmegaConf.load(config_path)
    _validate_contract(config)
    _inject_source_workspace(Path(source_workspace))
    from gr00t.rl.trl.utils.common import custom_instantiate

    actor = custom_instantiate(
        config.algo.config.actor,
        env_config=config.env.config,
        algo_config=config.algo.config,
        module_dim_dict=config.algo.config.module_dim,
        _resolve=False,
        _recursive_=False,
    ).to(device)
    payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if not isinstance(payload, Mapping):
        raise TypeError("Student checkpoint payload must be a mapping")
    global_step = _global_step(payload)
    state_dict = payload.get("policy_state_dict")
    if not isinstance(state_dict, Mapping) or len(state_dict) != EXPECTED_POLICY_TENSOR_COUNT:
        raise RuntimeError(
            f"DepthADD checkpoint policy_state_dict must contain {EXPECTED_POLICY_TENSOR_COUNT} tensors"
        )
    incompatibility = actor.load_state_dict(state_dict, strict=True)
    if incompatibility.missing_keys or incompatibility.unexpected_keys:
        raise RuntimeError(f"DepthADD strict load mismatch: {incompatibility}")
    actor.eval()
    a2_base = torch.jit.load(str(a2_base_path), map_location=device).to(device).eval()
    loaded = DepthADDV3Policy(
        actor=actor,
        a2_base=a2_base,
        bundle_dir=bundle_dir,
        global_step=global_step,
        device=device,
    )
    loaded.reset()
    loaded.act_a2_base(torch.zeros((1, 1620), dtype=torch.float32, device=device))
    return loaded


__all__ = ["DepthADDV3Policy", "load_depthadd_v3_policy"]
