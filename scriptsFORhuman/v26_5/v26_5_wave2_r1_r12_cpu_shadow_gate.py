#!/usr/bin/env python3
"""CPU shadow gate for the real CONT_STEP2000 v26-5 R12 actor contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import torch
from omegaconf import OmegaConf

from gr00t.rl.trl.modules.actor_critic_modules_recurrent import (
    A2V26_5PolicyResidualRecurrentActor,
    RecurrentActor,
)
from gr00t.rl.utils.config_utils import register_rl_resolvers


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / (
    "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/"
    "V26A_LR_S1_POLICY800"
)
SOURCE_CHECKPOINT = SOURCE_DIR / "model_step_002000.pt"
SOURCE_CONFIG = SOURCE_DIR / "config.yaml"
R12_SELECTOR = ROOT / (
    "gr00t/rl/config/ablation/wbmanip/base_v26_5_wave2_R1_policy_residual.yaml"
)
R12_COMPOSER = ROOT / "scriptsFORhuman/v26_5/v26_5_wave2_r1_compose.py"
ACTOR_STATE_KEY = "policy_state_dict"
IDENTITY_TOLERANCE = 1e-6


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _max_abs(lhs: torch.Tensor, rhs: torch.Tensor) -> float:
    return float((lhs - rhs).abs().max().item())


def _sorted_observation_slot(obs_terms, obs_dims, target_term: str) -> list[int]:
    ordered_terms = sorted(obs_terms)
    _require(
        target_term in ordered_terms,
        f"R12 actor observation is missing target term {target_term!r}.",
    )
    start = sum(obs_dims[term] for term in ordered_terms[:ordered_terms.index(target_term)])
    return [start, start + obs_dims[target_term]]


def _load_r12_config():
    _require(SOURCE_CONFIG.is_file(), f"missing CONT_STEP2000 config: {SOURCE_CONFIG}")
    _require(R12_SELECTOR.is_file(), f"missing R12 selector: {R12_SELECTOR}")
    _require(R12_COMPOSER.is_file(), f"missing R12 composer: {R12_COMPOSER}")
    register_rl_resolvers()
    spec = importlib.util.spec_from_file_location("r12_compose", R12_COMPOSER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import R12 composer: {R12_COMPOSER}")
    composer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(composer)
    selector = composer.compose(R12_SELECTOR)
    config = OmegaConf.merge(OmegaConf.load(SOURCE_CONFIG), OmegaConf.create(selector))
    actor_config = OmegaConf.create(
        OmegaConf.to_container(config.algo.config.actor, resolve=True)
    )
    algo_config = OmegaConf.create(
        OmegaConf.to_container(config.algo.config, resolve=True)
    )
    robot_config = OmegaConf.to_container(config.robot, resolve=True)
    obs_dims = {}
    for entry in config.obs.obs_dims:
        _require(len(entry) == 1, f"R12 obs_dims entry must have one key: {entry!r}")
        key, value = next(iter(entry.items()))
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RuntimeError(f"R12 obs dim must resolve to a positive int: {key}={value!r}")
        obs_dims[key] = value
    obs_dict = OmegaConf.to_container(config.obs.obs_dict, resolve=True)
    _require(
        actor_config.get("_target_")
        == "gr00t.rl.trl.modules.actor_critic_modules_recurrent.A2V26_5PolicyResidualRecurrentActor",
        "R12 selector did not resolve the residual actor target.",
    )
    _require(actor_config.get("input_key") == "actor_obs", "R12 base input key is not actor_obs.")
    _require(
        actor_config.get("residual_input_key") == "residual_actor_obs",
        "R12 residual input key is not residual_actor_obs.",
    )
    _require(
        config.env.config.a2_v26_5_geometry_target_enabled is False,
        "R12 main transformer geometry target must be false.",
    )
    raw_pose_slice = _sorted_observation_slot(
        obs_dict["actor_obs"], obs_dims, "gripper_handle_transform"
    )
    residual_pose_slice = _sorted_observation_slot(
        obs_dict["residual_actor_obs"], obs_dims, "gripper_handle_transform_gauge"
    )
    _require(
        raw_pose_slice == residual_pose_slice == [83, 101],
        "R12 sorted actor/residual target pose slice must be [83,101]; "
        f"got raw={raw_pose_slice}, residual={residual_pose_slice}.",
    )
    for key in ("actor_obs", "residual_actor_obs"):
        width = sum(obs_dims[term] for term in obs_dict[key])
        _require(width == 133, f"R12 {key} width must be 133; got {width}.")
        robot_config.setdefault("algo_obs_dim_dict", {})[key] = width
    runtime_env_config = OmegaConf.create({"robot": robot_config})
    return config, actor_config, algo_config, runtime_env_config, residual_pose_slice


def _construct_real_actors():
    config, actor_config, algo_config, runtime_env_config, residual_pose_slice = _load_r12_config()
    _require(SOURCE_CHECKPOINT.is_file(), f"missing CONT_STEP2000 checkpoint: {SOURCE_CHECKPOINT}")
    checkpoint = torch.load(SOURCE_CHECKPOINT, map_location="cpu", weights_only=False)
    _require(ACTOR_STATE_KEY in checkpoint, f"checkpoint missing {ACTOR_STATE_KEY}.")
    actor_state = checkpoint[ACTOR_STATE_KEY]
    _require(isinstance(actor_state, dict), f"checkpoint {ACTOR_STATE_KEY} is not a mapping.")
    for key in (
        "running_mean_std.running_mean",
        "running_mean_std.running_var",
        "running_mean_std.count",
        "memory.rnn.weight_ih_l0",
        "memory.rnn.weight_ih_l1",
    ):
        _require(key in actor_state, f"CONT_STEP2000 actor state missing {key}.")
    _require(tuple(actor_state["memory.rnn.weight_ih_l0"].shape) == (1024, 133), "CONT_STEP2000 LSTM input shape is not 133D.")
    _require(tuple(actor_state["memory.rnn.weight_ih_l1"].shape) == (1024, 256), "CONT_STEP2000 LSTM layer-1 shape mismatch.")

    actor_kwargs = dict(actor_config)
    actor_kwargs.pop("_target_", None)
    legacy_kwargs = dict(actor_kwargs)
    for key in ("residual_input_key", "residual_hidden_dim", "residual_stage_obs_slice"):
        legacy_kwargs.pop(key, None)
    legacy = RecurrentActor(env_config=runtime_env_config, algo_config=algo_config, **legacy_kwargs)
    residual = A2V26_5PolicyResidualRecurrentActor(
        env_config=runtime_env_config, algo_config=algo_config, **actor_kwargs
    )
    _require(
        set(legacy.state_dict()) == set(actor_state),
        "CONT_STEP2000 actor keyset does not exactly match constructed legacy actor. "
        f"missing={sorted(set(legacy.state_dict()) - set(actor_state))}, "
        f"unexpected={sorted(set(actor_state) - set(legacy.state_dict()))}.",
    )
    legacy_result = legacy.load_state_dict(actor_state, strict=True)
    _require(
        not legacy_result.missing_keys and not legacy_result.unexpected_keys,
        "strict CONT_STEP2000 legacy load returned key differences.",
    )
    residual_result = residual.load_state_dict(actor_state, strict=False)
    _require(
        set(residual_result.missing_keys) == set(residual.residual_state_keys())
        and not residual_result.unexpected_keys,
        "CONT_STEP2000 legacy-to-residual load did not miss exactly residual keys: "
        f"missing={residual_result.missing_keys}, unexpected={residual_result.unexpected_keys}.",
    )
    residual.assert_residual_zero_initialized()
    rms_keys = (
        "running_mean_std.running_mean",
        "running_mean_std.running_var",
        "running_mean_std.count",
    )
    for key in rms_keys:
        _require(
            torch.equal(actor_state[key], legacy.state_dict()[key])
            and torch.equal(actor_state[key], residual.state_dict()[key]),
            f"CONT_STEP2000 RMS field lost source identity: {key}.",
        )
    legacy.eval()
    residual.eval()
    return legacy, residual, config, rms_keys, residual_pose_slice


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"R12 CPU shadow gate refuses to overwrite: {args.output}")

    torch.manual_seed(20260830)
    legacy, residual, config, rms_keys, residual_pose_slice = _construct_real_actors()
    zero_residual_contract = residual.runtime_dual_input_contract_facts()
    base_obs = torch.randn(3, 133)
    base_obs[:, 127:133] = 0.0
    base_obs[:, 130] = 1.0
    gauge_obs = base_obs.clone()
    gauge_obs[:, residual_pose_slice[0]:residual_pose_slice[1]] += 0.4
    dual_obs = {"actor_obs": base_obs, "residual_actor_obs": gauge_obs}

    legacy.reset(); residual.reset()
    legacy_2d = legacy.forward({"actor_obs": base_obs}).squeeze(0)
    residual_2d = residual.forward(dual_obs)
    two_d_mean_max_abs = _max_abs(legacy_2d, residual_2d)

    seq_base = base_obs[:2].unsqueeze(1).repeat(1, 3, 1)
    seq_gauge = gauge_obs[:2].unsqueeze(1).repeat(1, 3, 1)
    masks = torch.ones(2, 3, dtype=torch.bool)
    dones = torch.zeros(2, 3, dtype=torch.bool)
    legacy.reset(); residual.reset()
    legacy_sequence = legacy.forward({"actor_obs": seq_base}, masks=masks, original_dones=dones)
    residual_sequence = residual.forward(
        {"actor_obs": seq_base, "residual_actor_obs": seq_gauge}, masks=masks, original_dones=dones
    )
    sequence_mean_max_abs = _max_abs(legacy_sequence, residual_sequence)

    legacy.reset(); residual.reset()
    cur_dones = torch.zeros(3, dtype=torch.bool)
    legacy_rollout = legacy.rollout({"actor_obs": base_obs}, cur_dones=cur_dones)
    residual_rollout = residual.rollout(dual_obs, cur_dones=cur_dones)
    rollout_mean_max_abs = _max_abs(legacy_rollout["action_mean"], residual_rollout["action_mean"])
    rollout_std_max_abs = _max_abs(legacy_rollout["action_sigma"], residual_rollout["action_sigma"])

    missing_residual_key_rejected = False
    try:
        residual.forward({"actor_obs": base_obs})
    except KeyError:
        missing_residual_key_rejected = True
    wrong_stage = gauge_obs.clone(); wrong_stage[:, 127] = 1.0; wrong_stage[:, 130] = 0.0
    stage_mismatch_rejected = False
    try:
        residual.forward({"actor_obs": base_obs, "residual_actor_obs": wrong_stage})
    except RuntimeError:
        stage_mismatch_rejected = True

    residual.train(); residual.reset(); residual.residual_module[-1].weight.data.fill_(0.1)
    residual.forward(dual_obs).sum().backward()
    frozen_base_grad_free = all(
        parameter.grad is None
        for module in (residual.memory, residual.actor_module)
        for parameter in module.parameters()
    ) and residual.std.grad is None
    residual_grad_present = all(
        parameter.requires_grad and parameter.grad is not None
        for parameter in residual.residual_module.parameters()
    )
    comparisons = (two_d_mean_max_abs, sequence_mean_max_abs, rollout_mean_max_abs, rollout_std_max_abs)
    measured = {
        "schema": "a2_piper_base_v26_5_r12_cpu_shadow_gate_v2",
        "status": "PASS",
        "checkpoint_path": str(SOURCE_CHECKPOINT.resolve()),
        "source_config_path": str(SOURCE_CONFIG.resolve()),
        "r12_selector_path": str(R12_SELECTOR.resolve()),
        "actor_state_key": ACTOR_STATE_KEY,
        "state_transfer": "legacy_exact_without_residual",
        "comparison_hidden_state": "both_actors_reset_to_none_before_each_comparison",
        "residual_pose_slice": residual_pose_slice,
        "rms_source_fields": list(rms_keys),
        "identity_tolerance": IDENTITY_TOLERANCE,
        "two_d_mean_max_abs": two_d_mean_max_abs,
        "sequence_mean_max_abs": sequence_mean_max_abs,
        "rollout_mean_max_abs": rollout_mean_max_abs,
        "rollout_std_max_abs": rollout_std_max_abs,
        "zero_identity_within_tolerance": all(value <= IDENTITY_TOLERANCE for value in comparisons),
        "missing_residual_key_rejected": missing_residual_key_rejected,
        "stage_mismatch_rejected": stage_mismatch_rejected,
        "frozen_base_grad_free": frozen_base_grad_free,
        "residual_grad_present": residual_grad_present,
        "zero_residual_contract": zero_residual_contract,
        "resolved_main_geometry_target_enabled": bool(config.env.config.a2_v26_5_geometry_target_enabled),
    }
    if not (
        measured["zero_identity_within_tolerance"] and missing_residual_key_rejected
        and stage_mismatch_rejected and frozen_base_grad_free and residual_grad_present
    ):
        raise RuntimeError(f"R12 CPU shadow gate failed: {measured}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(measured, handle, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
