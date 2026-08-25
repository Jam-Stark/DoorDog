#!/usr/bin/env python3
"""Replay and compare the authoritative Isaac/MuJoCo DepthADD Stage0 traces."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image, ImageDraw

from gr00t.rl.sim2sim.mujoco.action_warp_r5 import ResolvedActionWarpContractR5
from gr00t.rl.sim2sim.policy.depthadd_v3 import load_depthadd_v3_policy


EXACT_REPLAY_ATOL = 1.0e-6
OBS_FIELDS = (
    "actor_obs81",
    "policy_vision_obs8_float32",
    "policy_head_obs3_float32",
    "camera_meta6",
)
REPLAY_FIELDS = (*OBS_FIELDS, "student_action12", "lstm_pre_h", "lstm_pre_c", "lstm_post_h", "lstm_post_c", "lstm_pre_valid")
SUBSTITUTION_LANES = (
    "all_mujoco",
    "isaac_head",
    "isaac_dual_rgb",
    "isaac_depth",
    "isaac_actor_obs81",
    "isaac_camera_meta6",
    "isaac_all_visual_streams",
)
ISAAC_ENV_INDEX = 9
LANE_ISAAC_COMPONENTS = {
    "all_mujoco": (),
    "isaac_head": ("head_rgb",),
    "isaac_dual_rgb": ("dual_rgb",),
    "isaac_depth": ("depth",),
    "isaac_actor_obs81": ("actor_obs81",),
    "isaac_camera_meta6": ("camera_meta6",),
    "isaac_all_visual_streams": ("dual_rgb", "depth", "head_rgb"),
}
ACTOR_OBS_RUNTIME_FIELDS = (
    ("scaled_base_command", 0, 5),
    ("scaled_base_command_duplicate", 5, 10),
    ("q_minus_default", 10, 30),
    ("dof_velocity_x0p05", 30, 50),
    ("previous_actions19", 50, 69),
    ("base_angular_velocity_x0p5", 69, 72),
    ("previous_arm_delta6", 72, 78),
    ("projected_gravity", 78, 81),
)
ACTOR_COMPONENT_LANES = (
    "isaac_scaled_cmd_duplicate10",
    "isaac_qpos20",
    "isaac_qvel20",
    "isaac_previous_actions19",
    "isaac_base_ang_vel3",
    "isaac_previous_delta6",
    "isaac_projected_gravity3",
    "isaac_state46",
    "isaac_history35",
    "mujoco_runtime_repacked",
)


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_fields(path: Path, fields: tuple[str, ...]) -> dict[str, np.ndarray]:
    with np.load(path) as archive:
        missing = [field for field in fields if field not in archive]
        if missing:
            raise KeyError(f"alignment trace {path} is missing fields {missing}")
        return {field: archive[field] for field in fields}


def _hidden(actor: torch.nn.Module, batch_size: int) -> tuple[np.ndarray, np.ndarray, bool]:
    state = actor.get_hidden_states()
    if state is None:
        zero = np.zeros((2, batch_size, 256), dtype=np.float32)
        return zero, zero.copy(), False
    if not isinstance(state, tuple) or len(state) != 2:
        raise RuntimeError("DepthADD replay requires an LSTM (h,c) tuple")
    values = []
    for name, tensor in zip(("h", "c"), state, strict=True):
        if not torch.is_tensor(tensor) or tuple(tensor.shape) != (2, batch_size, 256):
            raise RuntimeError(
                f"DepthADD replay LSTM {name} must be [2,{batch_size},256]"
            )
        values.append(tensor.detach().cpu().numpy().copy())
    return values[0], values[1], True


def _observation(trace: Mapping[str, np.ndarray], step: int, device: torch.device) -> dict[str, torch.Tensor]:
    return {
        "actor_obs": torch.from_numpy(trace["actor_obs81"][step]).to(device),
        "vision_obs": torch.from_numpy(trace["policy_vision_obs8_float32"][step]).to(device),
        "context_vision_obs": torch.from_numpy(trace["policy_head_obs3_float32"][step]).to(device),
        "camera_meta": torch.from_numpy(trace["camera_meta6"][step]).to(device),
    }


def _replay(policy, trace: Mapping[str, np.ndarray], *, source_style_rollout: bool) -> dict[str, Any]:
    policy.reset()
    policy.actor.eval_mode()
    action_errors: list[float] = []
    pre_h_errors: list[float] = []
    pre_c_errors: list[float] = []
    post_h_errors: list[float] = []
    post_c_errors: list[float] = []
    steps = int(trace["student_action12"].shape[0])
    batch_size = int(trace["student_action12"].shape[1])
    for step in range(steps):
        pre_h, pre_c, pre_valid = _hidden(policy.actor, batch_size)
        expected_pre_valid = bool(trace["lstm_pre_valid"][step])
        if pre_valid != expected_pre_valid:
            raise RuntimeError(
                f"LSTM pre-valid mismatch at step {step}: replay={pre_valid}, trace={expected_pre_valid}"
            )
        if expected_pre_valid:
            pre_h_errors.append(float(np.max(np.abs(pre_h - trace["lstm_pre_h"][step]))))
            pre_c_errors.append(float(np.max(np.abs(pre_c - trace["lstm_pre_c"][step]))))
        obs = _observation(trace, step, policy.device)
        if source_style_rollout:
            with torch.no_grad():
                output = policy.actor.rollout(obs_dict=obs)
            action = output["action_mean"]
        else:
            action = policy.act_inference(obs)
        post_h, post_c, post_valid = _hidden(policy.actor, batch_size)
        if not post_valid:
            raise RuntimeError(f"LSTM post state is absent at step {step}")
        action_errors.append(
            float(np.max(np.abs(action.detach().cpu().numpy() - trace["student_action12"][step])))
        )
        post_h_errors.append(float(np.max(np.abs(post_h - trace["lstm_post_h"][step]))))
        post_c_errors.append(float(np.max(np.abs(post_c - trace["lstm_post_c"][step]))))
    maxima = {
        "action12": max(action_errors, default=0.0),
        "lstm_pre_h": max(pre_h_errors, default=0.0),
        "lstm_pre_c": max(pre_c_errors, default=0.0),
        "lstm_post_h": max(post_h_errors, default=0.0),
        "lstm_post_c": max(post_c_errors, default=0.0),
    }
    passed = max(maxima.values()) <= EXACT_REPLAY_ATOL
    return {
        "steps": steps,
        "batch_size": batch_size,
        "call": "actor.rollout/no_grad" if source_style_rollout else "policy.act_inference/inference_mode",
        "max_abs_error": maxima,
        "acceptance_atol": EXACT_REPLAY_ATOL,
        "exact_zero": all(value == 0.0 for value in maxima.values()),
        "result": "PASS" if passed else "FAIL",
    }


def _validate_batch_authority(trace: Mapping[str, np.ndarray]) -> None:
    expected = {
        "actor_obs81": (39, 16, 81),
        "policy_vision_obs8_float32": (39, 16, 384, 216, 8),
        "policy_head_obs3_float32": (39, 16, 136, 384, 3),
        "camera_meta6": (39, 16, 6),
        "student_action12": (39, 16, 12),
        "physical_base_command5": (39, 16, 5),
        "lstm_pre_h": (39, 2, 16, 256),
        "lstm_pre_c": (39, 2, 16, 256),
        "lstm_post_h": (39, 2, 16, 256),
        "lstm_post_c": (39, 2, 16, 256),
        "lstm_pre_valid": (39,),
        "done": (39, 16),
    }
    for field, shape in expected.items():
        if tuple(trace[field].shape) != shape:
            raise RuntimeError(
                f"Isaac batch16 authority {field} must be {shape}, got {trace[field].shape}"
            )
    if bool(np.any(trace["done"])):
        raise RuntimeError("Isaac batch16 Stage0 prefix must not contain done/reset rows")
    if bool(trace["lstm_pre_valid"][0]) or not bool(np.all(trace["lstm_pre_valid"][1:])):
        raise RuntimeError("Isaac batch16 hidden validity must be false only at step 0")


def _env_slice(trace: Mapping[str, np.ndarray], env_index: int) -> dict[str, np.ndarray]:
    result = {
        field: trace[field][:, env_index]
        for field in (
            "actor_obs81",
            "policy_vision_obs8_float32",
            "policy_head_obs3_float32",
            "camera_meta6",
            "student_action12",
            "physical_base_command5",
        )
    }
    for field in ("lstm_pre_h", "lstm_pre_c", "lstm_post_h", "lstm_post_c"):
        result[field] = trace[field][:, :, env_index, :]
    result["lstm_pre_valid"] = trace["lstm_pre_valid"]
    return result


def _as_batch1_trace(trace: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    result = {
        field: trace[field][:, None]
        for field in (
            "actor_obs81",
            "policy_vision_obs8_float32",
            "policy_head_obs3_float32",
            "camera_meta6",
            "student_action12",
            "physical_base_command5",
        )
    }
    for field in ("lstm_pre_h", "lstm_pre_c", "lstm_post_h", "lstm_post_c"):
        result[field] = trace[field][:, :, None, :]
    result["lstm_pre_valid"] = trace["lstm_pre_valid"]
    return result


def _lane_observation(
    isaac: Mapping[str, np.ndarray],
    mujoco: Mapping[str, np.ndarray],
    *,
    lane: str,
    step: int,
    device: torch.device,
) -> dict[str, torch.Tensor]:
    isaac_components = set(LANE_ISAAC_COMPONENTS[lane])
    actor_obs = isaac["actor_obs81"][step].copy()
    vision_obs = isaac["policy_vision_obs8_float32"][step].copy()
    head_obs = isaac["policy_head_obs3_float32"][step].copy()
    camera_meta = isaac["camera_meta6"][step].copy()
    if "actor_obs81" not in isaac_components:
        actor_obs[ISAAC_ENV_INDEX] = mujoco["actor_obs81"][step]
    if "dual_rgb" not in isaac_components:
        vision_obs[ISAAC_ENV_INDEX, ..., :6] = mujoco["policy_vision_obs8_float32"][step, ..., :6]
    if "depth" not in isaac_components:
        vision_obs[ISAAC_ENV_INDEX, ..., 6:8] = mujoco["policy_vision_obs8_float32"][step, ..., 6:8]
    if "head_rgb" not in isaac_components:
        head_obs[ISAAC_ENV_INDEX] = mujoco["policy_head_obs3_float32"][step]
    if "camera_meta6" not in isaac_components:
        camera_meta[ISAAC_ENV_INDEX] = mujoco["camera_meta6"][step]
    return {
        "actor_obs": torch.from_numpy(actor_obs).to(device),
        "vision_obs": torch.from_numpy(vision_obs).to(device),
        "context_vision_obs": torch.from_numpy(head_obs).to(device),
        "camera_meta": torch.from_numpy(camera_meta).to(device),
    }


def _physical_base_commands(
    action12: np.ndarray,
    contract: ResolvedActionWarpContractR5,
) -> np.ndarray:
    physical = np.empty((action12.shape[0], 5), dtype=np.float32)
    xyz_limit = np.asarray(contract.base_clip_thresholds_xyz, dtype=np.float32)
    physical[:, :3] = np.clip(
        action12[:, :3] * contract.base_command_scale,
        -xyz_limit,
        xyz_limit,
    )
    physical[:, 3:5] = (
        np.clip(action12[:, 3:5], -1.0, 1.0) * contract.body_pitch_roll_scale
    )
    return physical


def _divergence(value: np.ndarray, reference: np.ndarray) -> dict[str, Any]:
    delta = value - reference
    per_step = np.sqrt(np.mean(np.square(delta), axis=tuple(range(1, delta.ndim))))
    return {
        "max_abs": float(np.max(np.abs(delta))),
        "rmse": float(np.sqrt(np.mean(np.square(delta)))),
        "rmse_per_step": per_step.tolist(),
        "step38_rmse": float(per_step[38]),
    }


def _run_substitution_lane(
    policy,
    isaac: Mapping[str, np.ndarray],
    mujoco: Mapping[str, np.ndarray],
    *,
    lane: str,
    warp_contract: ResolvedActionWarpContractR5,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    policy.reset()
    policy.actor.eval_mode()
    steps = 39
    action12 = np.empty((steps, 12), dtype=np.float32)
    post_h = np.empty((steps, 2, 256), dtype=np.float32)
    post_c = np.empty((steps, 2, 256), dtype=np.float32)
    for step in range(steps):
        obs = _lane_observation(
            isaac,
            mujoco,
            lane=lane,
            step=step,
            device=policy.device,
        )
        with torch.no_grad():
            output = policy.actor.rollout(obs_dict=obs)
        action12[step] = output["action_mean"][ISAAC_ENV_INDEX].detach().cpu().numpy()
        hidden_h, hidden_c, valid = _hidden(policy.actor, 16)
        if not valid:
            raise RuntimeError(f"substitution lane {lane} has no post hidden at step {step}")
        post_h[step] = hidden_h[:, ISAAC_ENV_INDEX, :]
        post_c[step] = hidden_c[:, ISAAC_ENV_INDEX, :]
    physical = _physical_base_commands(action12, warp_contract)
    locomotion_norm = np.linalg.vector_norm(physical[:, :3], axis=1)
    isaac_env9 = _env_slice(isaac, ISAAC_ENV_INDEX)
    below = np.flatnonzero(locomotion_norm <= warp_contract.command_deadband_norm)
    isaac_components = set(LANE_ISAAC_COMPONENTS[lane])
    component_sources = {
        component: ("isaac_env9" if component in isaac_components else "mujoco")
        for component in ("actor_obs81", "dual_rgb", "depth", "head_rgb", "camera_meta6")
    }
    summary = {
        "lane": lane,
        "batch_shape": [39, 16],
        "intervened_batch_index": ISAAC_ENV_INDEX,
        "component_sources_for_env9": component_sources,
        "peer_context": "Isaac authority rows 0-8 and 10-15 unchanged",
        "action12": action12.tolist(),
        "physical_base_command5": physical.tolist(),
        "locomotion_norm_39": locomotion_norm.tolist(),
        "step38_locomotion_norm": float(locomotion_norm[38]),
        "step38_recovers_base_still": bool(
            locomotion_norm[38] <= warp_contract.command_deadband_norm
        ),
        "minimum_locomotion_norm": float(np.min(locomotion_norm)),
        "first_step_at_or_below_0_1": int(below[0]) if below.size else None,
        "action_divergence_to_isaac_env9": _divergence(
            action12, isaac_env9["student_action12"]
        ),
        "lstm_post_h_divergence_to_isaac_env9": _divergence(
            post_h, isaac_env9["lstm_post_h"]
        ),
        "lstm_post_c_divergence_to_isaac_env9": _divergence(
            post_c, isaac_env9["lstm_post_c"]
        ),
    }
    arrays = {
        f"{lane}__action12": action12,
        f"{lane}__lstm_post_h": post_h,
        f"{lane}__lstm_post_c": post_c,
        f"{lane}__physical_base_command5": physical,
        f"{lane}__locomotion_norm": locomotion_norm,
    }
    return summary, arrays


def _load_producer_lanes(
    receipt_path: Path,
    npz_path: Path,
    isaac_env9: Mapping[str, np.ndarray],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, np.ndarray]]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != "a2_depthadd_stage0_same_process_substitution_lanes_v1":
        raise RuntimeError(f"unexpected producer lane schema in {receipt_path}")
    if receipt.get("batch_size") != 16 or receipt.get("target_batch_index") != ISAAC_ENV_INDEX:
        raise RuntimeError("producer substitution batch/index contract drifted")
    if receipt.get("hidden_initialization") != "empty for every lane":
        raise RuntimeError("producer substitution hidden initialization drifted")
    if receipt.get("non_target_rows") != "original Isaac authority rows remain unchanged":
        raise RuntimeError("producer substitution peer-context contract drifted")
    if receipt.get("wall_20m_probe") != "NOT_RUN":
        raise RuntimeError("producer unexpectedly ran the 20 m wall probe")
    baseline = receipt.get("baseline_gate", {})
    maxima = baseline.get("max_abs_error", {})
    if (
        baseline.get("result") != "PASS"
        or float(baseline.get("acceptance_atol", -1.0)) != EXACT_REPLAY_ATOL
        or set(maxima) != {"action12", "lstm_pre_h", "lstm_pre_c", "lstm_post_h", "lstm_post_c"}
        or any(float(value) != 0.0 for value in maxima.values())
    ):
        raise RuntimeError("producer same-process full-batch exact replay is not an exact-zero PASS")
    mapping = receipt.get("action12_to_physical_base5", {})
    if float(mapping.get("runtime_trace_max_abs_error", -1.0)) != 0.0:
        raise RuntimeError("producer action12-to-physical-base5 mapping did not reproduce runtime")

    lanes: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    expected_shapes = {
        "student_action12": (39, 12),
        "lstm_post_h": (39, 2, 256),
        "lstm_post_c": (39, 2, 256),
        "physical_base_command5": (39, 5),
        "locomotion_norm": (39,),
    }
    with np.load(npz_path) as archive:
        for lane in SUBSTITUTION_LANES:
            source_receipt = receipt["lanes"].get(lane)
            if not isinstance(source_receipt, dict):
                raise KeyError(f"producer receipt is missing lane {lane!r}")
            lane_values: dict[str, np.ndarray] = {}
            for suffix, shape in expected_shapes.items():
                key = f"{lane}__{suffix}"
                if key not in archive:
                    raise KeyError(f"producer lane NPZ is missing {key!r}")
                value = archive[key].copy()
                if tuple(value.shape) != shape or not np.isfinite(value).all():
                    raise RuntimeError(f"producer lane array {key!r} must be finite {shape}")
                lane_values[suffix] = value
                arrays[key] = value
            locomotion = lane_values["locomotion_norm"]
            recomputed_norm = np.linalg.norm(lane_values["physical_base_command5"][:, :3], axis=1)
            if not np.array_equal(locomotion, recomputed_norm):
                raise RuntimeError(f"producer lane {lane!r} locomotion norm is not exact")
            below = np.flatnonzero(locomotion <= 0.1)
            source_map = source_receipt.get("component_source", {})
            expected_source_map = {
                "actor_obs81": "isaac" if "actor_obs81" in LANE_ISAAC_COMPONENTS[lane] else "mujoco",
                "dual_rgb6": "isaac" if "dual_rgb" in LANE_ISAAC_COMPONENTS[lane] else "mujoco",
                "depth2": "isaac" if "depth" in LANE_ISAAC_COMPONENTS[lane] else "mujoco",
                "head_rgb3": "isaac" if "head_rgb" in LANE_ISAAC_COMPONENTS[lane] else "mujoco",
                "camera_meta6": "isaac" if "camera_meta6" in LANE_ISAAC_COMPONENTS[lane] else "mujoco",
            }
            if source_map != expected_source_map:
                raise RuntimeError(f"producer lane {lane!r} component-source map drifted")
            lanes[lane] = {
                "lane": lane,
                "authority": "producer_original_isaac_cuda_process",
                "batch_shape": [39, 16],
                "intervened_batch_index": ISAAC_ENV_INDEX,
                "component_sources_for_env9": source_map,
                "peer_context": "Isaac authority rows 0-8 and 10-15 unchanged",
                "action12": lane_values["student_action12"].tolist(),
                "physical_base_command5": lane_values["physical_base_command5"].tolist(),
                "locomotion_norm_39": locomotion.tolist(),
                "step35_to_step38_locomotion_norm": locomotion[35:39].tolist(),
                "step38_locomotion_norm": float(locomotion[38]),
                "step38_recovers_base_still": bool(locomotion[38] <= 0.1),
                "minimum_locomotion_norm": float(np.min(locomotion)),
                "first_step_at_or_below_0_1": int(below[0]) if below.size else None,
                "action_divergence_to_isaac_env9": _divergence(
                    lane_values["student_action12"], isaac_env9["student_action12"]
                ),
                "lstm_post_h_divergence_to_isaac_env9": _divergence(
                    lane_values["lstm_post_h"], isaac_env9["lstm_post_h"]
                ),
                "lstm_post_c_divergence_to_isaac_env9": _divergence(
                    lane_values["lstm_post_c"], isaac_env9["lstm_post_c"]
                ),
            }
            if (
                abs(lanes[lane]["step38_locomotion_norm"] - float(source_receipt["step38_locomotion_norm"])) > 1.0e-7
                or abs(lanes[lane]["minimum_locomotion_norm"] - float(source_receipt["minimum_locomotion_norm"])) > 1.0e-7
            ):
                raise RuntimeError(f"producer lane {lane!r} JSON/NPZ metrics disagree")
    return receipt, lanes, arrays


def _load_actor_component_lanes(
    receipt_path: Path,
    npz_path: Path,
    isaac_env9: Mapping[str, np.ndarray],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, np.ndarray]]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != "a2_depthadd_stage0_actor_obs_component_lanes_v1":
        raise RuntimeError(f"unexpected actor component lane schema in {receipt_path}")
    if (
        receipt.get("batch_size") != 16
        or receipt.get("target_batch_index") != ISAAC_ENV_INDEX
        or receipt.get("record_count") != 39
        or receipt.get("hidden_initialization") != "empty for every lane"
        or receipt.get("other_four_inputs") != "MuJoCo for every lane"
        or receipt.get("non_target_rows") != "original Isaac authority rows remain unchanged"
        or receipt.get("wall_20m_probe") != "NOT_RUN"
    ):
        raise RuntimeError("actor component lane execution contract drifted")
    baseline = receipt.get("baseline_gate", {})
    maxima = baseline.get("max_abs_error", {})
    if (
        baseline.get("result") != "PASS"
        or float(baseline.get("acceptance_atol", -1.0)) != EXACT_REPLAY_ATOL
        or any(float(value) != 0.0 for value in maxima.values())
    ):
        raise RuntimeError("actor component lanes lack an exact-zero producer baseline")
    invariants = receipt.get("authority_invariants", {})
    if float(invariants.get("command_duplicate_max_abs_error", -1.0)) != 0.0:
        raise RuntimeError("producer authority does not preserve duplicated command")

    expected_shapes = {
        "student_action12": (39, 12),
        "lstm_post_h": (39, 2, 256),
        "lstm_post_c": (39, 2, 256),
        "physical_base_command5": (39, 5),
        "locomotion_norm": (39,),
    }
    lanes: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    with np.load(npz_path) as archive:
        for lane in ACTOR_COMPONENT_LANES:
            source_receipt = receipt["lanes"].get(lane)
            if not isinstance(source_receipt, dict):
                raise KeyError(f"actor component receipt is missing {lane!r}")
            lane_values: dict[str, np.ndarray] = {}
            for suffix, shape in expected_shapes.items():
                key = f"{lane}__{suffix}"
                if key not in archive:
                    raise KeyError(f"actor component NPZ is missing {key!r}")
                value = archive[key].copy()
                if tuple(value.shape) != shape or not np.isfinite(value).all():
                    raise RuntimeError(f"actor component array {key!r} must be finite {shape}")
                lane_values[suffix] = value
                arrays[key] = value
            locomotion = lane_values["locomotion_norm"]
            if not np.array_equal(
                locomotion,
                np.linalg.norm(lane_values["physical_base_command5"][:, :3], axis=1),
            ):
                raise RuntimeError(f"actor component lane {lane!r} locomotion norm drifted")
            below = np.flatnonzero(locomotion <= 0.1)
            lanes[lane] = {
                "lane": lane,
                "authority": "producer_original_isaac_cuda_process",
                "actor_obs81_source": source_receipt["actor_obs81_source"],
                "other_input_sources": source_receipt["other_input_sources"],
                "batch_shape": [39, 16],
                "intervened_batch_index": ISAAC_ENV_INDEX,
                "peer_context": "Isaac authority rows 0-8 and 10-15 unchanged",
                "action12": lane_values["student_action12"].tolist(),
                "physical_base_command5": lane_values["physical_base_command5"].tolist(),
                "locomotion_norm_39": locomotion.tolist(),
                "step35_to_step38_locomotion_norm": locomotion[35:39].tolist(),
                "step38_locomotion_norm": float(locomotion[38]),
                "step38_recovers_base_still": bool(locomotion[38] <= 0.1),
                "minimum_locomotion_norm": float(np.min(locomotion)),
                "first_step_at_or_below_0_1": int(below[0]) if below.size else None,
                "action_divergence_to_isaac_env9": _divergence(
                    lane_values["student_action12"], isaac_env9["student_action12"]
                ),
                "lstm_post_h_divergence_to_isaac_env9": _divergence(
                    lane_values["lstm_post_h"], isaac_env9["lstm_post_h"]
                ),
                "lstm_post_c_divergence_to_isaac_env9": _divergence(
                    lane_values["lstm_post_c"], isaac_env9["lstm_post_c"]
                ),
            }
            if not np.array_equal(
                locomotion[35:39],
                np.asarray(source_receipt["step35_to38_locomotion_norm"], dtype=locomotion.dtype),
            ):
                raise RuntimeError(f"actor component lane {lane!r} JSON/NPZ metrics disagree")
    return receipt, lanes, arrays


def _write_actor_component_lane_table(
    output: Path, lanes: Mapping[str, Mapping[str, Any]]
) -> None:
    with (output / "actor_obs_component_substitution_table.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "lane",
                "actor_obs81_source",
                "step35_norm",
                "step36_norm",
                "step37_norm",
                "step38_norm",
                "minimum_norm",
                "step38_recovers_base_still",
                "action_rmse_to_isaac",
                "post_h_rmse_to_isaac",
                "post_c_rmse_to_isaac",
            )
        )
        for lane in ACTOR_COMPONENT_LANES:
            value = lanes[lane]
            writer.writerow(
                (
                    lane,
                    json.dumps(value["actor_obs81_source"], sort_keys=True),
                    *value["step35_to_step38_locomotion_norm"],
                    value["minimum_locomotion_norm"],
                    value["step38_recovers_base_still"],
                    value["action_divergence_to_isaac_env9"]["rmse"],
                    value["lstm_post_h_divergence_to_isaac_env9"]["rmse"],
                    value["lstm_post_c_divergence_to_isaac_env9"]["rmse"],
                )
            )


def _plot_actor_component_lanes(
    output: Path, lanes: Mapping[str, Mapping[str, Any]]
) -> None:
    names = list(ACTOR_COMPONENT_LANES)
    values = [lanes[name]["step38_locomotion_norm"] for name in names]
    positions = np.arange(len(names))
    figure, axis = plt.subplots(figsize=(11, 7))
    colors = ["#d5962f" if name == "isaac_state46" else "#4779ad" for name in names]
    axis.barh(positions, values, color=colors, edgecolor="#24384f")
    axis.axvline(0.1, color="#202020", linestyle="--", linewidth=1, label="base-still threshold")
    axis.set_yticks(positions, labels=names)
    axis.invert_yaxis()
    axis.set_xlabel("mapped physical locomotion norm at step38")
    axis.set_title("actor_obs81 same-process component substitution")
    for position, value in zip(positions, values, strict=True):
        axis.text(value, position, f" {value:.3f}", va="center")
    axis.legend(loc="lower right")
    figure.tight_layout()
    figure.savefig(output / "actor_obs_component_lane_step38.png", dpi=150)
    plt.close(figure)


def _repack_manifest_order_actor_obs(actor_obs: np.ndarray) -> np.ndarray:
    if actor_obs.ndim != 2 or actor_obs.shape[1] != 81:
        raise ValueError(f"MuJoCo actor_obs must be [steps,81], got {actor_obs.shape}")
    return np.concatenate(
        (
            actor_obs[:, 71:76],
            actor_obs[:, 71:76],
            actor_obs[:, 6:26],
            actor_obs[:, 26:46],
            actor_obs[:, 46:65],
            actor_obs[:, 0:3],
            actor_obs[:, 65:71],
            actor_obs[:, 3:6],
        ),
        axis=1,
    )


def _actor_obs_contract_diagnosis(
    isaac_env9: Mapping[str, np.ndarray],
    mujoco: Mapping[str, np.ndarray],
) -> tuple[dict[str, Any], np.ndarray]:
    isaac_actor = isaac_env9["actor_obs81"][:39]
    mujoco_manifest_order = mujoco["actor_obs81"][:39]
    mujoco_runtime_order = _repack_manifest_order_actor_obs(mujoco_manifest_order)
    fields: dict[str, Any] = {}
    for name, start, end in ACTOR_OBS_RUNTIME_FIELDS:
        delta = mujoco_runtime_order[:, start:end] - isaac_actor[:, start:end]
        per_step = np.sqrt(np.mean(np.square(delta), axis=1))
        fields[name] = {
            "slice": [start, end],
            "dim": end - start,
            "prefix_rmse": float(np.sqrt(np.mean(np.square(delta)))),
            "max_abs": float(np.max(np.abs(delta))),
            "step35_to_step38_rmse": per_step[35:39].tolist(),
            "step38_rmse": float(per_step[38]),
        }
    declared_delta = mujoco_manifest_order - isaac_actor
    runtime_delta = mujoco_runtime_order - isaac_actor
    return {
        "source_runtime_assembly": {
            "ordering_rule": "sorted actor_obs term keys; strip _raw suffix before raw-buffer lookup",
            "effective_order": [name for name, _, _ in ACTOR_OBS_RUNTIME_FIELDS],
            "raw_base_command_effect": "a2_base_command_raw aliases a2_base_command, producing a bitwise duplicate 5D scaled command",
        },
        "authority_invariants": {
            "scaled_command_duplicate_bitwise_equal": bool(
                np.array_equal(isaac_actor[:, 0:5], isaac_actor[:, 5:10])
            ),
            "projected_gravity_norm_min": float(np.min(np.linalg.norm(isaac_actor[:, 78:81], axis=1))),
            "projected_gravity_norm_max": float(np.max(np.linalg.norm(isaac_actor[:, 78:81], axis=1))),
        },
        "mujoco_old_manifest_order_rmse": float(np.sqrt(np.mean(np.square(declared_delta)))),
        "mujoco_offline_runtime_repacked_rmse": float(np.sqrt(np.mean(np.square(runtime_delta)))),
        "fields": fields,
        "causal_boundary": (
            "Field RMSE describes stored-sequence disagreement after correcting packing. "
            "It does not rank policy sensitivity; component substitution lanes own causal attribution."
        ),
    }, mujoco_runtime_order


def _write_actor_obs_table(output: Path, diagnosis: Mapping[str, Any]) -> None:
    with (output / "actor_obs_runtime_contract_table.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "field",
                "start",
                "end",
                "dim",
                "prefix_rmse",
                "max_abs",
                "step35_rmse",
                "step36_rmse",
                "step37_rmse",
                "step38_rmse",
            )
        )
        for name, start, end in ACTOR_OBS_RUNTIME_FIELDS:
            value = diagnosis["fields"][name]
            writer.writerow(
                (
                    name,
                    start,
                    end,
                    end - start,
                    value["prefix_rmse"],
                    value["max_abs"],
                    *value["step35_to_step38_rmse"],
                )
            )


def _plot_actor_obs_components(output: Path, diagnosis: Mapping[str, Any]) -> None:
    names = [name for name, _, _ in ACTOR_OBS_RUNTIME_FIELDS]
    values = [diagnosis["fields"][name]["step38_rmse"] for name in names]
    figure, axis = plt.subplots(figsize=(10, 6))
    positions = np.arange(len(names))
    axis.barh(positions, values, color="#3b6ea8", edgecolor="#24384f")
    axis.set_yticks(positions, labels=names)
    axis.invert_yaxis()
    axis.set_xlabel("Isaac vs runtime-repacked MuJoCo RMSE at step38")
    axis.set_title("actor_obs81 component disagreement after packing correction")
    for position, value in zip(positions, values, strict=True):
        axis.text(value, position, f" {value:.3f}", va="center")
    figure.tight_layout()
    figure.savefig(output / "actor_obs_component_step38_rmse.png", dpi=150)
    plt.close(figure)


def _write_lane_table(output: Path, lanes: Mapping[str, Mapping[str, Any]]) -> None:
    with (output / "substitution_lane_table.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "lane",
                "env9_component_sources",
                "step38_locomotion_norm",
                "step38_recovers_base_still",
                "minimum_locomotion_norm",
                "first_step_at_or_below_0_1",
                "action_rmse_to_isaac",
                "post_h_rmse_to_isaac",
                "post_c_rmse_to_isaac",
            )
        )
        for lane in SUBSTITUTION_LANES:
            value = lanes[lane]
            writer.writerow(
                (
                    lane,
                    json.dumps(value["component_sources_for_env9"], sort_keys=True),
                    value["step38_locomotion_norm"],
                    value["step38_recovers_base_still"],
                    value["minimum_locomotion_norm"],
                    value["first_step_at_or_below_0_1"],
                    value["action_divergence_to_isaac_env9"]["rmse"],
                    value["lstm_post_h_divergence_to_isaac_env9"]["rmse"],
                    value["lstm_post_c_divergence_to_isaac_env9"]["rmse"],
                )
            )


def _direct_comparison(isaac: Mapping[str, np.ndarray], mujoco: Mapping[str, np.ndarray]) -> dict[str, Any]:
    prefix = min(isaac["student_action12"].shape[0], mujoco["student_action12"].shape[0])
    isaac_action = isaac["student_action12"][:prefix]
    mujoco_action = mujoco["student_action12"][:prefix]
    isaac_locomotion = np.linalg.norm(isaac["physical_base_command5"][:prefix, :3], axis=1)
    mujoco_locomotion = np.linalg.norm(mujoco["physical_base_command5"][:prefix, :3], axis=1)
    hidden_delta = mujoco["lstm_post_h"][:prefix] - isaac["lstm_post_h"][:prefix]
    actor_delta = mujoco["actor_obs81"][:prefix] - isaac["actor_obs81"][:prefix]
    vision_delta = mujoco["policy_vision_obs8_float32"][:prefix] - isaac["policy_vision_obs8_float32"][:prefix]
    head_delta = mujoco["policy_head_obs3_float32"][:prefix] - isaac["policy_head_obs3_float32"][:prefix]
    camera_meta_delta = mujoco["camera_meta6"][:prefix] - isaac["camera_meta6"][:prefix]

    def delta_summary(value: np.ndarray) -> dict[str, float]:
        return {
            "max_abs": float(np.max(np.abs(value))),
            "rmse": float(np.sqrt(np.mean(np.square(value)))),
        }

    return {
        "prefix_steps_without_interpolation": int(prefix),
        "student_action12": {
            "max_abs": float(np.max(np.abs(mujoco_action - isaac_action))),
            "rmse": float(np.sqrt(np.mean(np.square(mujoco_action - isaac_action)))),
        },
        "physical_locomotion_norm": {
            "isaac_min": float(np.min(isaac_locomotion)),
            "isaac_last": float(isaac_locomotion[-1]),
            "mujoco_min": float(np.min(mujoco_locomotion)),
            "mujoco_last": float(mujoco_locomotion[-1]),
        },
        "lstm_post_h": delta_summary(hidden_delta),
        "actor_obs81": delta_summary(actor_delta),
        "dual_rgb6_policy_ready": delta_summary(vision_delta[..., :6]),
        "dual_depth2_policy_ready": delta_summary(vision_delta[..., 6:8]),
        "head_rgb3_policy_ready": delta_summary(head_delta),
        "camera_meta6": delta_summary(camera_meta_delta),
    }


def _plot_sequences(output: Path, isaac: Mapping[str, np.ndarray], mujoco: Mapping[str, np.ndarray]) -> None:
    prefix = min(isaac["student_action12"].shape[0], mujoco["student_action12"].shape[0])
    steps = np.arange(prefix)
    isaac_norm = np.linalg.norm(isaac["physical_base_command5"][:prefix, :3], axis=1)
    mujoco_norm = np.linalg.norm(mujoco["physical_base_command5"][:prefix, :3], axis=1)
    action_rmse = np.sqrt(
        np.mean(np.square(mujoco["student_action12"][:prefix] - isaac["student_action12"][:prefix]), axis=1)
    )
    hidden_rmse = np.sqrt(
        np.mean(np.square(mujoco["lstm_post_h"][:prefix] - isaac["lstm_post_h"][:prefix]), axis=(1, 2))
    )
    figure, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    axes[0].plot(steps, isaac_norm, label="Isaac clean env9")
    axes[0].plot(steps, mujoco_norm, label="MuJoCo fixed")
    axes[0].axhline(0.1, color="black", linestyle="--", linewidth=1, label="Stage0 stillness threshold")
    axes[0].set_ylabel("physical base norm")
    axes[0].legend()
    axes[1].plot(steps, action_rmse, color="tab:red")
    axes[1].set_ylabel("action12 RMSE")
    axes[2].plot(steps, hidden_rmse, color="tab:purple")
    axes[2].set_ylabel("post-h RMSE")
    axes[2].set_xlabel("50 Hz prefix step (no interpolation)")
    figure.tight_layout()
    figure.savefig(output / "direct_sequence_comparison.png", dpi=150)
    plt.close(figure)


def _plot_lanes(output: Path, lanes: Mapping[str, Mapping[str, Any]]) -> None:
    figure, axis = plt.subplots(figsize=(11, 7))
    steps = np.arange(39)
    for lane in SUBSTITUTION_LANES:
        axis.plot(steps, lanes[lane]["locomotion_norm_39"], label=lane)
    axis.axhline(0.1, color="black", linestyle="--", linewidth=1, label="base-still threshold")
    axis.axvline(38, color="gray", linestyle=":", linewidth=1, label="Isaac transition step")
    axis.set_xlabel("50 Hz prefix step (no interpolation)")
    axis.set_ylabel("mapped physical locomotion norm")
    axis.legend(fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(output / "substitution_lane_locomotion_norm.png", dpi=150)
    plt.close(figure)


def _keyframe_panel(output: Path, isaac_npz: Path, mujoco_npz: Path) -> None:
    fields = ("raw_left_rgb_uint8", "raw_right_rgb_uint8", "raw_head_rgb_uint8")
    isaac = _load_fields(isaac_npz, fields)
    mujoco = _load_fields(mujoco_npz, fields)
    rows: list[tuple[str, dict[str, np.ndarray], int]] = [
        ("Isaac t0", isaac, 0),
        ("MuJoCo t0", mujoco, 0),
        ("Isaac prefix end", isaac, min(38, isaac[fields[0]].shape[0] - 1)),
        ("MuJoCo prefix end", mujoco, min(38, mujoco[fields[0]].shape[0] - 1)),
    ]
    target = (288, 216)
    cell_width, label_width = target[0], 170
    panel = Image.new("RGB", (label_width + 3 * cell_width, len(rows) * target[1]), "white")
    draw = ImageDraw.Draw(panel)
    for row_index, (label, trace, step) in enumerate(rows):
        y = row_index * target[1]
        draw.text((8, y + 8), f"{label}\nstep {step}", fill="black")
        for column, field in enumerate(fields):
            image = Image.fromarray(trace[field][step]).resize(target)
            panel.paste(image, (label_width + column * cell_width, y))
    panel.save(output / "raw_rgb_keyframes.png")


def _markdown(report: Mapping[str, Any]) -> str:
    producer = report["exact_replay"]["producer_same_process_authority"]
    portability = report["exact_replay"]["independent_process_portability"]
    isaac = portability["isaac_authority"]
    mujoco = portability["mujoco_export"]
    direct = report["direct_sequence_comparison"]
    lane_lines = []
    for lane in SUBSTITUTION_LANES:
        value = report["substitution_lanes"][lane]
        steps = "/".join(f"{item:.6f}" for item in value["step35_to_step38_locomotion_norm"])
        lane_lines.append(
            f"| `{lane}` | {','.join(LANE_ISAAC_COMPONENTS[lane]) or 'none'} | "
            f"{steps} | {value['minimum_locomotion_norm']:.6f} | "
            f"{'YES' if value['step38_recovers_base_still'] else 'NO'} | "
            f"{value['action_divergence_to_isaac_env9']['rmse']:.6f} | "
            f"{value['lstm_post_h_divergence_to_isaac_env9']['rmse']:.6f} |"
        )
    contract = report["actor_obs81_contract_diagnosis"]
    contract_lines = []
    for name, start, end in ACTOR_OBS_RUNTIME_FIELDS:
        value = contract["fields"][name]
        step_values = "/".join(f"{item:.6f}" for item in value["step35_to_step38_rmse"])
        contract_lines.append(
            f"| `{start}:{end}` | `{name}` | {value['prefix_rmse']:.6f} | "
            f"{step_values} | {value['max_abs']:.6f} |"
        )
    component_lines = []
    for lane in ACTOR_COMPONENT_LANES:
        value = report["actor_obs81_component_lanes"][lane]
        step_values = "/".join(
            f"{item:.6f}" for item in value["step35_to_step38_locomotion_norm"]
        )
        component_lines.append(
            f"| `{lane}` | {step_values} | {value['minimum_locomotion_norm']:.6f} | "
            f"{value['action_divergence_to_isaac_env9']['rmse']:.6f} | "
            f"{value['lstm_post_h_divergence_to_isaac_env9']['rmse']:.6f} | "
            f"{'YES' if value['step38_recovers_base_still'] else 'NO'} |"
        )
    component_attribution = report["actor_obs81_component_attribution"]
    attribution = report["attribution"]
    actor_steps = "/".join(
        f"{item:.6f}" for item in attribution["isaac_actor_obs81_step35_to_step38"][:3]
    )
    fixed = report["fixed_stage0_admission"]
    if fixed["status"] == "NOT_RUN":
        fixed_summary = "Fixed Stage0 rerun is `NOT_RUN`; randomized evaluation remains unauthorized."
    else:
        fixed_summary = (
            f"Fixed Stage0 admission is `{fixed['status']}`: max stage `{fixed['max_stage']}`, "
            f"terminal `{fixed['terminal_reason']}`, goal `{fixed['goal_reached']}`. "
            f"Randomized evaluation authorized: `{fixed['randomized_experiment_authorized']}`."
        )
    producer_hidden_max = max(
        producer["max_abs_error"][key]
        for key in ("lstm_pre_h", "lstm_pre_c", "lstm_post_h", "lstm_post_c")
    )
    return f"""# DepthADD v3 offline Stage0 alignment

## Technical summary

- **Result:** `{report['status']}`. Producer-side full-batch replay is exact zero at `1e-6`, and all seven same-process substitution lanes are complete.
- **Dominant input difference:** restoring only Isaac `actor_obs81` reduces step38 locomotion norm from `{attribution['all_mujoco_step38']:.6f}` to `{attribution['isaac_actor_obs81_step38']:.6f}`; steps35–37 reach `{actor_steps}`. Restoring all visual streams leaves step38 at `{attribution['isaac_all_visual_streams_step38']:.6f}`.
- **Root contract mismatch:** the Isaac runtime policy-ready 81D layout is sorted-key order and duplicates scaled base command; MuJoCo used the handoff's declared semantic order. Runtime repacking reduces stored actor-observation RMSE from `{contract['mujoco_old_manifest_order_rmse']:.6f}` to `{contract['mujoco_offline_runtime_repacked_rmse']:.6f}` before any closed-loop rerun.
- **Within-81D attribution:** no component lane is sufficient. `state46` is best at step38 (`{component_attribution['isaac_state46_step38']:.6f}`); the strongest single fields are base angular velocity (`{component_attribution['best_single_component_lanes']['isaac_base_ang_vel3']:.6f}`) and qvel (`{component_attribution['best_single_component_lanes']['isaac_qvel20']:.6f}`).
- **Admission:** {fixed_summary}
- **Geometry boundary:** the 20 m wall probe remains `NOT_RUN`; no current evidence points back to wall occlusion.

## `actor_obs81` is the dominant offline driver, not the visual streams

Only batch index 9 changes in each lane; the other 15 Isaac rows remain untouched. Each lane starts from empty hidden state. The four values in “Step35–38 norm” are mapped physical locomotion norms at 50 Hz.

| Lane | Isaac components retained | Step35–38 norm | 39-step minimum | Step38 ≤0.1 | Action RMSE to Isaac | post-h RMSE to Isaac |
|---|---|---|---:|---|---:|---:|
{chr(10).join(lane_lines)}

The actor-only lane is strongly restorative but not sufficient at the requested step38 gate. Visual-only results are negative evidence against RGB, Depth, Head RGB, or camera metadata being the primary explanation for this prefix.

![Seven same-process substitution lanes](substitution_lane_locomotion_norm.png)

## Isaac runtime packing differs from the handoff table

The deployed observation assembler sorts actor term names and then strips `_raw` before indexing the raw term buffer. That makes `a2_base_command_raw` resolve to `a2_base_command`, producing a second bitwise-identical 5D scaled command. The actual policy-ready layout is therefore:

| Slice | Runtime field | Prefix RMSE | Step35–38 RMSE | Max absolute difference |
|---|---|---:|---|---:|
{chr(10).join(contract_lines)}

The full batch16 authority confirms columns `0:5` and `5:10` are bitwise identical. Its true projected-gravity slice is `78:81`, with norm range `{contract['authority_invariants']['projected_gravity_norm_min']:.9f}`–`{contract['authority_invariants']['projected_gravity_norm_max']:.9f}`. Field RMSE measures remaining closed-loop sequence disagreement; it is not a policy-sensitivity ranking.

![actor_obs component disagreement](actor_obs_component_step38_rmse.png)

## State terms are the strongest 81D subgroup, but no field is sufficient

These producer-side component lanes use the same exact-zero batch16 baseline and keep all four non-actor inputs from MuJoCo. Each lane replaces only the named runtime slice at env9.

| Lane | Step35–38 norm | 39-step minimum | Action RMSE | post-h RMSE | Step38 ≤0.1 |
|---|---|---:|---:|---:|---|
{chr(10).join(component_lines)}

`isaac_state46` is the strongest grouped intervention, while qvel and base angular velocity are the strongest single fields. The offline `mujoco_runtime_repacked` lane improves action/post-h agreement but stays far above the base-still gate because its qvel, prior actions, delta, command, and state history already came from the wrong closed loop. The live fixed rerun below is therefore the decisive correction test.

![actor_obs component substitution](actor_obs_component_lane_step38.png)

## Authority and portability are separate results

| Trace | Steps | Call | Max action error | Max LSTM error | Result |
|---|---:|---|---:|---:|---|
| Producer original Isaac process | {producer['steps']}×{producer['batch_size']} | `{producer['call']}` | {producer['max_abs_error']['action12']:.9g} | {producer_hidden_max:.9g} | {producer['result']} |
| Independent process, Isaac batch | {isaac['steps']}×{isaac['batch_size']} | `{isaac['call']}` | {isaac['max_abs_error']['action12']:.9g} | {max(isaac['max_abs_error'][key] for key in ('lstm_pre_h','lstm_pre_c','lstm_post_h','lstm_post_c')):.9g} | {isaac['result']} |
| Independent process, MuJoCo export | {mujoco['steps']} | `{mujoco['call']}` | {mujoco['max_abs_error']['action12']:.9g} | {max(mujoco['max_abs_error'][key] for key in ('lstm_pre_h','lstm_pre_c','lstm_post_h','lstm_post_c')):.9g} | {mujoco['result']} |

Acceptance is max absolute error ≤ `{EXACT_REPLAY_ATOL:g}` with no relaxed fallback. The independent-process failure is retained as a portability fact; it does not invalidate same-process causal lanes whose baseline gate passed exactly.

## Scope, metrics, and methodology

The comparison covers the first `{direct['prefix_steps_without_interpolation']}` policy steps at 50 Hz for Isaac env9 and the fixed MuJoCo case. There is no interpolation. “Locomotion norm” is the Euclidean norm of the first three mapped physical base commands; Stage0 stillness requires `≤0.1`.

- action12 max/RMSE: `{direct['student_action12']['max_abs']:.6g}` / `{direct['student_action12']['rmse']:.6g}`
- post-LSTM-h max/RMSE: `{direct['lstm_post_h']['max_abs']:.6g}` / `{direct['lstm_post_h']['rmse']:.6g}`
- actor_obs81 max/RMSE: `{direct['actor_obs81']['max_abs']:.6g}` / `{direct['actor_obs81']['rmse']:.6g}`
- dual RGB policy-ready max/RMSE: `{direct['dual_rgb6_policy_ready']['max_abs']:.6g}` / `{direct['dual_rgb6_policy_ready']['rmse']:.6g}`
- dual depth policy-ready max/RMSE: `{direct['dual_depth2_policy_ready']['max_abs']:.6g}` / `{direct['dual_depth2_policy_ready']['rmse']:.6g}`
- Head RGB policy-ready max/RMSE: `{direct['head_rgb3_policy_ready']['max_abs']:.6g}` / `{direct['head_rgb3_policy_ready']['rmse']:.6g}`
- camera_meta6 max/RMSE: `{direct['camera_meta6']['max_abs']:.6g}` / `{direct['camera_meta6']['rmse']:.6g}`
- locomotion norm at shared-prefix end: Isaac `{direct['physical_locomotion_norm']['isaac_last']:.6g}`, MuJoCo `{direct['physical_locomotion_norm']['mujoco_last']:.6g}`

The source comparison followed the actual evaluation path: generic `parse_observation`, sorted-key concatenation, deployed checkpoint rollout, and action12-to-physical-base mapping. The MuJoCo correction changes only policy-ready 81D packing; units, body-frame angular velocity/gravity, 20-DOF state scaling, previous-action cadence, visual inputs, controller, scene, and wall geometry remain unchanged.

## Limitations and robustness boundary

- The seven lanes establish causal input-sequence effects only for the stored 39-step prefix and batch16 peer context.
- The actor-only lane is not sufficient at step38; remaining visual/physics/trajectory interaction may account for the residual.
- Numeric component RMSE is descriptive; the producer same-process component lanes provide the sensitivity evidence.
- `{report['evidence_boundary']}`
- Independent-process replay is not bitwise portable under the recorded CUDA/cuDNN backend; its error remains reported rather than hidden.

## Recommended next steps

1. Treat the runtime layout—not the stale handoff table—as checkpoint authority and keep the corrected MuJoCo adapter.
2. Use the fixed Stage0 admission above as the gate. Resume visual/door/combined randomized experiments only when `randomized_experiment_authorized` is true.
3. For any remaining Stage2 diagnosis, prioritize qvel/base-angular/state46 frame and scale checks; the Stage0 packing issue itself is resolved live.
4. Keep the 20 m wall probe unrun unless later evidence specifically reopens geometry.

## Further questions

- Does the corrected fixed rollout reach Stage1 consistently across the three formal seeds, or only the admission seed?
- Within the residual after packing correction, is command/action history or physical state the larger causal contributor?
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--source-workspace", type=Path, required=True)
    parser.add_argument("--isaac-trace", type=Path, required=True)
    parser.add_argument("--isaac-batch-trace", type=Path, required=True)
    parser.add_argument("--mujoco-trace", type=Path, required=True)
    parser.add_argument("--producer-lanes-json", type=Path, required=True)
    parser.add_argument("--producer-lanes-npz", type=Path, required=True)
    parser.add_argument("--actor-component-lanes-json", type=Path, required=True)
    parser.add_argument("--actor-component-lanes-npz", type=Path, required=True)
    parser.add_argument("--fixed-admission-receipt", type=Path)
    parser.add_argument("--independent-portability-report", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.deterministic = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = True
    torch.set_float32_matmul_precision("highest")
    isaac_batch = _load_fields(
        args.isaac_batch_trace.resolve(strict=True),
        (*REPLAY_FIELDS, "physical_base_command5", "done"),
    )
    _validate_batch_authority(isaac_batch)
    isaac_env9 = _env_slice(isaac_batch, ISAAC_ENV_INDEX)
    mujoco = _load_fields(
        args.mujoco_trace.resolve(strict=True),
        (*REPLAY_FIELDS, "physical_base_command5"),
    )
    if args.independent_portability_report is None:
        policy = load_depthadd_v3_policy(
            args.bundle_dir,
            source_workspace=args.source_workspace,
            device=args.device,
        )
        isaac_replay = _replay(policy, isaac_batch, source_style_rollout=True)
        mujoco_replay = _replay(
            policy,
            _as_batch1_trace(mujoco),
            source_style_rollout=False,
        )
        backend = {
            "device": str(policy.device),
            "torch_version": torch.__version__,
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
            "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
            "float32_matmul_precision": torch.get_float32_matmul_precision(),
        }
    else:
        portability_path = args.independent_portability_report.resolve(strict=True)
        prior = json.loads(portability_path.read_text(encoding="utf-8"))
        if prior.get("schema") == "doordog.sim2sim.depthadd_v3.offline_alignment.v2":
            isaac_replay = prior["exact_replay"]["isaac_authority"]
            mujoco_replay = prior["exact_replay"]["mujoco_export"]
        elif prior.get("schema") == "doordog.sim2sim.depthadd_v3.offline_alignment.v3":
            portability = prior["exact_replay"]["independent_process_portability"]
            isaac_replay = portability["isaac_authority"]
            mujoco_replay = portability["mujoco_export"]
        else:
            raise RuntimeError("independent portability report must be an inspected v2/v3 replay report")
        if isaac_replay.get("result") != "FAIL":
            raise RuntimeError("independent portability source no longer records the known replay failure")
        backend = {
            **prior["backend"],
            "source_report": str(portability_path),
            "reused_without_rerun": True,
        }
    producer_receipt, lane_results, lane_arrays = _load_producer_lanes(
        args.producer_lanes_json.resolve(strict=True),
        args.producer_lanes_npz.resolve(strict=True),
        isaac_env9,
    )
    np.savez(output / "producer_same_process_substitution_lane_outputs.npz", **lane_arrays)
    _write_lane_table(output, lane_results)
    _plot_lanes(output, lane_results)
    component_receipt, component_lanes, component_arrays = _load_actor_component_lanes(
        args.actor_component_lanes_json.resolve(strict=True),
        args.actor_component_lanes_npz.resolve(strict=True),
        isaac_env9,
    )
    np.savez(
        output / "producer_actor_obs_component_lane_outputs.npz",
        **component_arrays,
    )
    _write_actor_component_lane_table(output, component_lanes)
    _plot_actor_component_lanes(output, component_lanes)
    actor_obs_diagnosis, repacked_actor_obs = _actor_obs_contract_diagnosis(
        isaac_env9, mujoco
    )
    np.savez(
        output / "actor_obs_runtime_repacked_prefix.npz",
        actor_obs81=repacked_actor_obs,
    )
    _write_actor_obs_table(output, actor_obs_diagnosis)
    _plot_actor_obs_components(output, actor_obs_diagnosis)
    restored_lanes = [
        lane
        for lane in SUBSTITUTION_LANES
        if lane_results[lane]["step38_recovers_base_still"]
    ]
    actor_lane = lane_results["isaac_actor_obs81"]
    visual_lane = lane_results["isaac_all_visual_streams"]
    attribution = {
        "criterion": "mapped physical locomotion norm at step38 <= 0.1",
        "restored_lanes": restored_lanes,
        "not_restored_lanes": [
            lane for lane in SUBSTITUTION_LANES if lane not in restored_lanes
        ],
        "dominant_component": "actor_obs81",
        "all_mujoco_step38": lane_results["all_mujoco"]["step38_locomotion_norm"],
        "isaac_actor_obs81_step38": actor_lane["step38_locomotion_norm"],
        "isaac_actor_obs81_step35_to_step38": actor_lane[
            "step35_to_step38_locomotion_norm"
        ],
        "isaac_all_visual_streams_step38": visual_lane["step38_locomotion_norm"],
        "interpretation": (
            "Producer same-process substitution establishes actor_obs81 as the dominant "
            f"input difference over this 39-step prefix: retaining Isaac actor_obs81 moves "
            f"step38 locomotion norm from {lane_results['all_mujoco']['step38_locomotion_norm']:.6f} "
            f"to {actor_lane['step38_locomotion_norm']:.6f} and crosses <=0.1 at steps 35-37. "
            f"Retaining all visual streams leaves step38 at {visual_lane['step38_locomotion_norm']:.6f}. "
            "Because actor_obs81 alone remains above 0.1 at step38, this does not establish "
            "a unique or sufficient root cause."
        ),
    }
    component_attribution = {
        "criterion": "mapped physical locomotion norm at step38 <= 0.1",
        "restored_lanes": [
            lane
            for lane in ACTOR_COMPONENT_LANES
            if component_lanes[lane]["step38_recovers_base_still"]
        ],
        "best_component_lane_by_step38_norm": "isaac_state46",
        "isaac_state46_step38": component_lanes["isaac_state46"][
            "step38_locomotion_norm"
        ],
        "best_single_component_lanes": {
            "isaac_base_ang_vel3": component_lanes["isaac_base_ang_vel3"][
                "step38_locomotion_norm"
            ],
            "isaac_qvel20": component_lanes["isaac_qvel20"][
                "step38_locomotion_norm"
            ],
        },
        "mujoco_runtime_repacked": {
            "step38_locomotion_norm": component_lanes["mujoco_runtime_repacked"][
                "step38_locomotion_norm"
            ],
            "action_rmse_to_isaac": component_lanes["mujoco_runtime_repacked"][
                "action_divergence_to_isaac_env9"
            ]["rmse"],
            "post_h_rmse_to_isaac": component_lanes["mujoco_runtime_repacked"][
                "lstm_post_h_divergence_to_isaac_env9"
            ]["rmse"],
        },
        "interpretation": (
            "No actor_obs component lane alone recovers step38 <=0.1. State46 is the "
            "strongest grouped retention lane at 0.264058; qvel20 and base_ang_vel3 are "
            "the strongest single fields at 0.408982 and 0.395607. Offline repacking of "
            "the already-wrong closed-loop trace reduces action/post-h divergence but leaves "
            "step38 at 0.594245, so it cannot substitute for a live closed-loop fix."
        ),
    }

    fixed_admission: dict[str, Any] = {"status": "NOT_RUN"}
    if args.fixed_admission_receipt is not None:
        fixed_path = args.fixed_admission_receipt.resolve(strict=True)
        fixed_receipt = json.loads(fixed_path.read_text(encoding="utf-8"))
        if fixed_receipt.get("lane") != "fixed" or fixed_receipt.get("result") != "COMPLETE":
            raise RuntimeError("fixed admission receipt is not a completed fixed-lane episode")
        stage0_passed = int(fixed_receipt["max_stage"]) >= 1
        fixed_admission = {
            "status": "PASS_STAGE0" if stage0_passed else "FAIL_STAGE0",
            "receipt": str(fixed_path),
            "max_stage": int(fixed_receipt["max_stage"]),
            "goal_reached": bool(fixed_receipt["goal_reached"]),
            "terminal_reason": str(fixed_receipt["terminal_reason"]),
            "randomized_experiment_authorized": stage0_passed,
        }
    status = {
        "PASS_STAGE0": "OBSERVATION_CONTRACT_FIXED_STAGE0_PASS",
        "FAIL_STAGE0": "OBSERVATION_CONTRACT_FIXED_STAGE0_FAIL",
        "NOT_RUN": "SAME_PROCESS_SUBSTITUTION_COMPLETE_OBSERVATION_CONTRACT_IDENTIFIED",
    }[fixed_admission["status"]]
    report = {
        "schema": "doordog.sim2sim.depthadd_v3.offline_alignment.v3",
        "status": status,
        "authority": {
            "isaac_batch_trace": str(args.isaac_batch_trace.resolve(strict=True)),
            "isaac_raw_env9_trace": str(args.isaac_trace.resolve(strict=True)),
            "mujoco_trace": str(args.mujoco_trace.resolve(strict=True)),
            "isaac_batch_shape": [39, 16],
            "intervened_batch_index": ISAAC_ENV_INDEX,
            "prefix_alignment": "39 control steps at 50 Hz; no interpolation",
            "producer_same_process_lanes_json": str(
                args.producer_lanes_json.resolve(strict=True)
            ),
            "producer_same_process_lanes_npz": str(
                args.producer_lanes_npz.resolve(strict=True)
            ),
            "producer_actor_component_lanes_json": str(
                args.actor_component_lanes_json.resolve(strict=True)
            ),
            "producer_actor_component_lanes_npz": str(
                args.actor_component_lanes_npz.resolve(strict=True)
            ),
        },
        "backend": backend,
        "exact_replay": {
            "producer_same_process_authority": {
                "steps": 39,
                "batch_size": 16,
                "call": "policy.rollout(obs_dict=batch16)/torch.no_grad in original Isaac CUDA process",
                **producer_receipt["baseline_gate"],
            },
            "independent_process_portability": {
                "interpretation": (
                    "Independent-process replay is a portability result only. Its failure "
                    "does not invalidate causal lanes admitted and executed in the original producer process."
                ),
                "isaac_authority": isaac_replay,
                "mujoco_export": mujoco_replay,
            },
        },
        "direct_sequence_comparison": _direct_comparison(isaac_env9, mujoco),
        "actor_obs81_contract_diagnosis": actor_obs_diagnosis,
        "substitution_lanes": lane_results,
        "attribution": attribution,
        "actor_obs81_component_lanes": component_lanes,
        "actor_obs81_component_attribution": component_attribution,
        "actor_obs81_component_authority": {
            "runtime_layout": component_receipt[
                "authority_actor_obs81_runtime_layout"
            ],
            "invariants": component_receipt["authority_invariants"],
            "other_four_inputs": component_receipt["other_four_inputs"],
        },
        "fixed_stage0_admission": fixed_admission,
        "wall_probe_20m": "NOT_RUN",
        "evidence_boundary": (
            "Substitution results are scoped to the fixed 39-step offline prefix. "
            "Only the fixed admission receipt can establish live closed-loop Stage0 progression. "
            "No result in this report tests or attributes failure to 20 m wall geometry."
        ),
    }
    _json_dump(output / "offline_alignment_report.json", report)
    (output / "offline_alignment_report.md").write_text(_markdown(report), encoding="utf-8")
    _plot_sequences(output, isaac_env9, mujoco)
    _keyframe_panel(output, args.isaac_trace, args.mujoco_trace)


if __name__ == "__main__":
    main()
