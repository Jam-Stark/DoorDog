"""Pure v21-B arm-effort evidence contracts.

The A2 arm uses IsaacLab ``ImplicitActuatorCfg``.  Consequently the values in
this module are PD-effort estimates (and the configured effort-limit clipping
state), never a claim about a PhysX drive-force readback.  The helpers are
device-local and intentionally strict: malformed shape, dtype, device, or
non-finite telemetry raises at the boundary instead of being repaired.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import torch


V21B_EVIDENCE_SCHEMA = "a2_piper_base_v21B_arm_evidence_v1"
V21B_STEP_SCHEMA = "a2_piper_base_v21B_arm_step_evidence_v1"
V21B_TERMINAL_RECORD_SCHEMA = "a2_piper_base_v21B_terminal_arm_record_v1"
V21B_AUTHORITY_LABEL = "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE"
V21B_CENSUS_RIGHT_CENSORED = "CENSUS_RIGHT_CENSORED"
V21B_BOUNDARY_CREATED = "BOUNDARY_CREATED"
V21B_BOUNDARY_ABSENT = "BOUNDARY_ABSENT"
V21B_BOUNDARY_SATURATED_EVERYWHERE = "BOUNDARY_SATURATED_EVERYWHERE"
V21B_BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED = "BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED"
V21B_ARM_JOINT_NAMES = ("arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6")
V21B_CANDIDATE_LIMITS_NM = (40.0, 30.0, 25.0, 20.0)


def _require_digest(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase sha256 digest")
    return value


def _require_matrix(value: torch.Tensor, *, name: str, columns: int = 6) -> tuple[int, torch.dtype, torch.device]:
    if not torch.is_tensor(value) or value.ndim != 2 or value.shape[1] != columns:
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{name} requires a floating tensor shape (N,{columns}); got {shape}.")
    if not value.is_floating_point():
        raise ValueError(f"{name} requires a floating tensor; got {value.dtype}.")
    if not torch.all(torch.isfinite(value)):
        raise ValueError(f"{name} contains non-finite values.")
    return value.shape[0], value.dtype, value.device


def _require_vector(value: torch.Tensor, *, name: str, n: int, dtype: torch.dtype | None = None) -> None:
    if not torch.is_tensor(value) or tuple(value.shape) != (n,):
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{name} requires shape ({n},); got {shape}.")
    if dtype is not None and value.dtype != dtype:
        raise ValueError(f"{name} requires dtype {dtype}; got {value.dtype}.")
    if value.is_floating_point() and not torch.all(torch.isfinite(value)):
        raise ValueError(f"{name} contains non-finite values.")


def _require_same(value: torch.Tensor, *, name: str, n: int, dtype: torch.dtype, device: torch.device) -> None:
    _require_matrix(value, name=name)
    if value.shape[0] != n or value.dtype != dtype or value.device != device:
        raise ValueError(f"{name} must share shape, dtype, and device with arm_j1..arm_j6 inputs.")


def _finite_scalar(value: Any, *, name: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number.")
    result = float(value)
    if positive and result <= 0.0:
        raise ValueError(f"{name} must be strictly positive.")
    return result


def a2_v21b_arm_pd_effort_estimates(
    joint_pos: torch.Tensor,
    joint_vel: torch.Tensor,
    joint_pos_target: torch.Tensor,
    stiffness: torch.Tensor,
    damping: torch.Tensor,
    effort_limit: torch.Tensor,
) -> dict[str, torch.Tensor]:
    """Compute unclipped/clipped implicit-PD estimates for arm_j1..arm_j6."""

    n, dtype, device = _require_matrix(joint_pos, name="arm joint_pos")
    for value, name in (
        (joint_vel, "arm joint_vel"),
        (joint_pos_target, "arm joint_pos_target"),
        (stiffness, "arm joint_stiffness"),
        (damping, "arm joint_damping"),
        (effort_limit, "arm joint_effort_limit"),
    ):
        _require_same(value, name=name, n=n, dtype=dtype, device=device)
    if torch.any(effort_limit <= 0.0):
        raise ValueError("arm joint effort limits must be strictly positive.")
    unclipped = stiffness * (joint_pos_target - joint_pos) - damping * joint_vel
    clipped = torch.clamp(unclipped, min=-effort_limit, max=effort_limit)
    saturated = torch.abs(unclipped) > effort_limit
    for value, name in ((unclipped, "unclipped"), (clipped, "clipped")):
        if not torch.all(torch.isfinite(value)):
            raise RuntimeError(f"arm {name} PD effort estimate is non-finite.")
    return {
        "arm_pd_effort_estimate_unclipped_6d": unclipped,
        "arm_pd_effort_estimate_clipped_6d": clipped,
        "arm_pd_effort_estimated_saturation_6d": saturated,
        "arm_joint_effort_limit_6d": effort_limit,
    }


def a2_v21b_arm_tracking_error(
    joint_pos_target: torch.Tensor,
    joint_pos: torch.Tensor,
    joint_vel: torch.Tensor,
) -> dict[str, torch.Tensor]:
    """Return target-minus-actual position error and velocity corroboration."""

    n, dtype, device = _require_matrix(joint_pos_target, name="arm joint_pos_target")
    _require_same(joint_pos, name="arm joint_pos", n=n, dtype=dtype, device=device)
    _require_same(joint_vel, name="arm joint_vel", n=n, dtype=dtype, device=device)
    position_error = joint_pos_target - joint_pos
    if not torch.all(torch.isfinite(position_error)):
        raise RuntimeError("arm joint position tracking error is non-finite.")
    return {
        "arm_joint_position_error_6d": position_error,
        "arm_joint_velocity_6d": joint_vel,
    }


def a2_v21b_build_step_evidence(
    *,
    pd_estimates: Mapping[str, torch.Tensor],
    tracking: Mapping[str, torch.Tensor],
    valid_mask: torch.Tensor,
    step_index: torch.Tensor | None = None,
) -> dict[str, Any]:
    """Build one strict step row for the v21-B accumulator."""

    required_pd = (
        "arm_pd_effort_estimate_unclipped_6d",
        "arm_pd_effort_estimate_clipped_6d",
        "arm_pd_effort_estimated_saturation_6d",
        "arm_joint_effort_limit_6d",
    )
    if not isinstance(pd_estimates, Mapping) or any(key not in pd_estimates for key in required_pd):
        raise ValueError("v21-B arm step requires all three PD estimate fields.")
    n, dtype, device = _require_matrix(pd_estimates[required_pd[0]], name=required_pd[0])
    _require_same(pd_estimates[required_pd[1]], name=required_pd[1], n=n, dtype=dtype, device=device)
    saturation = pd_estimates[required_pd[2]]
    if not torch.is_tensor(saturation) or tuple(saturation.shape) != (n, 6) or saturation.dtype != torch.bool or saturation.device != device:
        raise ValueError("arm PD saturation requires bool shape (N,6) on the estimate device.")
    _require_same(pd_estimates[required_pd[3]], name=required_pd[3], n=n, dtype=dtype, device=device)
    if torch.any(pd_estimates[required_pd[3]] <= 0.0):
        raise ValueError("arm joint effort limits must be strictly positive.")
    if not isinstance(tracking, Mapping) or "arm_joint_position_error_6d" not in tracking or "arm_joint_velocity_6d" not in tracking:
        raise ValueError("v21-B arm step requires position-error and velocity corroboration.")
    _require_same(tracking["arm_joint_position_error_6d"], name="arm_joint_position_error_6d", n=n, dtype=dtype, device=device)
    _require_same(tracking["arm_joint_velocity_6d"], name="arm_joint_velocity_6d", n=n, dtype=dtype, device=device)
    _require_vector(valid_mask, name="arm telemetry valid_mask", n=n, dtype=torch.bool)
    if valid_mask.device != device:
        raise ValueError("arm telemetry valid_mask must share the estimate device.")
    if step_index is not None:
        _require_vector(step_index, name="arm telemetry step_index", n=n, dtype=torch.long)
        if step_index.device != device:
            raise ValueError("arm telemetry step_index must share the estimate device.")
    result = {
        "schema": V21B_STEP_SCHEMA,
        "joint_names": list(V21B_ARM_JOINT_NAMES),
        **{key: value for key, value in pd_estimates.items() if key in required_pd},
        "isaaclab_implicit_effort_estimate_authority": V21B_AUTHORITY_LABEL,
        **{key: value for key, value in tracking.items() if key in ("arm_joint_position_error_6d", "arm_joint_velocity_6d")},
        "valid_mask": valid_mask,
    }
    if step_index is not None:
        result["step_index"] = step_index
    return result


def a2_v21b_init_arm_episode_accumulator(
    num_envs: int,
    *,
    dtype: torch.dtype = torch.float32,
    device: torch.device | str = "cpu",
    max_episode_length: int | None = None,
) -> dict[str, torch.Tensor]:
    """Allocate reset-safe per-env arm telemetry accumulators."""

    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs <= 0:
        raise ValueError("num_envs must be a positive integer.")
    if max_episode_length is not None and (
        isinstance(max_episode_length, bool)
        or not isinstance(max_episode_length, int)
        or max_episode_length <= 0
    ):
        raise ValueError("max_episode_length must be a positive integer when provided.")
    dev = torch.device(device)
    zeros = lambda: torch.zeros((num_envs, 6), dtype=dtype, device=dev)
    state: dict[str, torch.Tensor] = {
        "valid_frames": torch.zeros(num_envs, dtype=torch.long, device=dev),
        "unclipped_abs_sum_6d": zeros(),
        "unclipped_abs_max_6d": zeros(),
        "clipped_abs_max_6d": zeros(),
        "saturation_frames_6d": torch.zeros((num_envs, 6), dtype=torch.long, device=dev),
        "ge_090_frames_6d": torch.zeros((num_envs, 6), dtype=torch.long, device=dev),
        "ge_098_frames_6d": torch.zeros((num_envs, 6), dtype=torch.long, device=dev),
        "position_error_abs_sum_6d": zeros(),
        "position_error_abs_max_6d": zeros(),
        "velocity_abs_sum_6d": zeros(),
        "velocity_abs_max_6d": zeros(),
        "frame_ge_090_count": torch.zeros(num_envs, dtype=torch.long, device=dev),
        "frame_ge_098_count": torch.zeros(num_envs, dtype=torch.long, device=dev),
    }
    if max_episode_length is not None:
        state["unclipped_abs_samples_6d"] = torch.zeros(
            (num_envs, max_episode_length, 6), dtype=dtype, device=dev
        )
        state["unclipped_abs_sample_mask"] = torch.zeros(
            (num_envs, max_episode_length), dtype=torch.bool, device=dev
        )
    return state


def _validate_accumulator(state: Mapping[str, torch.Tensor], *, num_envs: int, dtype: torch.dtype, device: torch.device) -> None:
    required = (
        "valid_frames", "unclipped_abs_sum_6d", "unclipped_abs_max_6d", "clipped_abs_max_6d",
        "saturation_frames_6d", "ge_090_frames_6d", "ge_098_frames_6d",
        "position_error_abs_sum_6d", "position_error_abs_max_6d",
        "velocity_abs_sum_6d", "velocity_abs_max_6d", "frame_ge_090_count", "frame_ge_098_count",
    )
    if not isinstance(state, Mapping) or any(key not in state for key in required):
        raise ValueError("v21-B arm accumulator is missing required fields.")
    if tuple(state["valid_frames"].shape) != (num_envs,) or state["valid_frames"].dtype != torch.long or state["valid_frames"].device != device:
        raise ValueError("v21-B valid_frames has an invalid tensor contract.")
    for key in required[1:]:
        value = state[key]
        expected_shape = (num_envs,) if key.startswith("frame_ge_") else (num_envs, 6)
        if not torch.is_tensor(value) or tuple(value.shape) != expected_shape or value.device != device:
            raise ValueError(f"v21-B accumulator field {key} has an invalid shape/device.")
        if key.endswith("frames_6d") or key.startswith("frame_ge_"):
            if value.dtype != torch.long:
                raise ValueError(f"v21-B accumulator field {key} must be torch.long.")
        elif value.dtype != dtype or not value.is_floating_point():
            raise ValueError(f"v21-B accumulator field {key} must use dtype {dtype}.")
    history_keys = ("unclipped_abs_samples_6d", "unclipped_abs_sample_mask")
    history_present = tuple(key in state for key in history_keys)
    if any(history_present) and not all(history_present):
        raise ValueError("v21-B per-sample history requires both sample and mask fields.")
    if all(history_present):
        samples = state[history_keys[0]]
        sample_mask = state[history_keys[1]]
        if (
            not torch.is_tensor(samples)
            or samples.ndim != 3
            or samples.shape[0] != num_envs
            or samples.shape[2] != 6
            or samples.dtype != dtype
            or not samples.is_floating_point()
            or samples.device != device
        ):
            raise ValueError("v21-B unclipped_abs_samples_6d has an invalid tensor contract.")
        if (
            not torch.is_tensor(sample_mask)
            or sample_mask.ndim != 2
            or sample_mask.shape[0] != num_envs
            or sample_mask.shape[1] != samples.shape[1]
            or sample_mask.dtype != torch.bool
            or sample_mask.device != device
        ):
            raise ValueError("v21-B unclipped_abs_sample_mask has an invalid tensor contract.")


def a2_v21b_reset_arm_episode_accumulator(state: Mapping[str, torch.Tensor], env_ids: torch.Tensor) -> None:
    """Reset exactly selected env rows; staged reset therefore cannot leak telemetry."""

    if not torch.is_tensor(env_ids) or env_ids.ndim != 1 or env_ids.dtype != torch.long:
        raise ValueError("v21-B reset env_ids requires a one-dimensional torch.long tensor.")
    num_envs = state["valid_frames"].shape[0]
    _validate_accumulator(state, num_envs=num_envs, dtype=state["unclipped_abs_sum_6d"].dtype, device=state["valid_frames"].device)
    if env_ids.device != state["valid_frames"].device or torch.any(env_ids < 0) or torch.any(env_ids >= num_envs):
        raise ValueError("v21-B reset env_ids are outside the accumulator device/range.")
    for key, value in state.items():
        value[env_ids] = 0


def a2_v21b_accumulate_arm_step(state: Mapping[str, torch.Tensor], step: Mapping[str, Any]) -> None:
    """Accumulate one post-physics sample for all environments."""

    if not isinstance(step, Mapping) or step.get("schema") != V21B_STEP_SCHEMA:
        raise ValueError("v21-B accumulator requires a v21-B step schema.")
    if tuple(step.get("joint_names", ())) != V21B_ARM_JOINT_NAMES:
        raise ValueError("v21-B accumulator requires exactly one arm_j1..arm_j6 step multiplicity.")
    if step.get("isaaclab_implicit_effort_estimate_authority") != V21B_AUTHORITY_LABEL:
        raise ValueError("v21-B accumulator requires the estimate-only authority label.")
    unclipped = step["arm_pd_effort_estimate_unclipped_6d"]
    clipped = step["arm_pd_effort_estimate_clipped_6d"]
    saturation = step["arm_pd_effort_estimated_saturation_6d"]
    position_error = step["arm_joint_position_error_6d"]
    velocity = step["arm_joint_velocity_6d"]
    effort_limit = step["arm_joint_effort_limit_6d"]
    valid_mask = step["valid_mask"]
    n, dtype, device = _require_matrix(unclipped, name="step unclipped effort")
    for value, name in ((clipped, "step clipped effort"), (position_error, "step position error"), (velocity, "step velocity")):
        _require_same(value, name=name, n=n, dtype=dtype, device=device)
    _require_same(effort_limit, name="step arm_joint_effort_limit_6d", n=n, dtype=dtype, device=device)
    if torch.any(effort_limit <= 0.0):
        raise ValueError("step arm joint effort limits must be strictly positive.")
    if not torch.is_tensor(saturation) or tuple(saturation.shape) != (n, 6) or saturation.dtype != torch.bool or saturation.device != device:
        raise ValueError("step saturation requires bool shape (N,6) on the estimate device.")
    _require_vector(valid_mask, name="step valid_mask", n=n, dtype=torch.bool)
    if valid_mask.device != device:
        raise ValueError("step valid_mask must share device with telemetry tensors.")
    _validate_accumulator(state, num_envs=n, dtype=dtype, device=device)
    has_history = "unclipped_abs_samples_6d" in state
    step_index = step.get("step_index")
    if has_history:
        if step_index is None:
            raise ValueError("v21-B per-sample history requires step_index in every step.")
        _require_vector(step_index, name="step step_index", n=n, dtype=torch.long)
        if step_index.device != device:
            raise ValueError("step step_index must share device with telemetry tensors.")
        history_length = state["unclipped_abs_samples_6d"].shape[1]
        valid_indices = step_index[valid_mask]
        if torch.any(valid_indices < 0) or torch.any(valid_indices >= history_length):
            raise ValueError("valid v21-B step_index values are outside retained history.")
    active = valid_mask[:, None]
    abs_unclipped = torch.abs(unclipped)
    abs_clipped = torch.abs(clipped)
    utilization_6d = abs_clipped / effort_limit
    frame_utilization = torch.amax(utilization_6d, dim=1)
    abs_position_error = torch.abs(position_error)
    abs_velocity = torch.abs(velocity)
    state["valid_frames"] += valid_mask.to(torch.long)
    state["unclipped_abs_sum_6d"] += torch.where(active, abs_unclipped, torch.zeros_like(abs_unclipped))
    state["unclipped_abs_max_6d"] = torch.where(active, torch.maximum(state["unclipped_abs_max_6d"], abs_unclipped), state["unclipped_abs_max_6d"])
    state["clipped_abs_max_6d"] = torch.where(active, torch.maximum(state["clipped_abs_max_6d"], abs_clipped), state["clipped_abs_max_6d"])
    state["saturation_frames_6d"] += (saturation & active).to(torch.long)
    state["ge_090_frames_6d"] += ((utilization_6d >= 0.90) & active).to(torch.long)
    state["ge_098_frames_6d"] += ((utilization_6d >= 0.98) & active).to(torch.long)
    state["position_error_abs_sum_6d"] += torch.where(active, abs_position_error, torch.zeros_like(abs_position_error))
    state["position_error_abs_max_6d"] = torch.where(active, torch.maximum(state["position_error_abs_max_6d"], abs_position_error), state["position_error_abs_max_6d"])
    state["velocity_abs_sum_6d"] += torch.where(active, abs_velocity, torch.zeros_like(abs_velocity))
    state["velocity_abs_max_6d"] = torch.where(active, torch.maximum(state["velocity_abs_max_6d"], abs_velocity), state["velocity_abs_max_6d"])
    state["frame_ge_090_count"] += (valid_mask & (frame_utilization >= 0.90)).to(torch.long)
    state["frame_ge_098_count"] += (valid_mask & (frame_utilization >= 0.98)).to(torch.long)
    if has_history:
        active_env_ids = torch.nonzero(valid_mask, as_tuple=False).squeeze(1)
        if active_env_ids.numel():
            active_step_indices = step_index[active_env_ids]
            state["unclipped_abs_samples_6d"][active_env_ids, active_step_indices] = abs_unclipped[active_env_ids]
            state["unclipped_abs_sample_mask"][active_env_ids, active_step_indices] = True


def _na(reason: str, denominator: int) -> dict[str, Any]:
    if denominator < 0:
        raise ValueError("N/A denominator must be non-negative.")
    return {"status": "N/A", "reason": reason, "denominator": denominator}


def _ratio_or_na(numerator: float, denominator: int, *, reason: str) -> float | dict[str, Any]:
    return float(numerator / denominator) if denominator else _na(reason, denominator)


def a2_v21b_finalize_arm_episode(
    state: Mapping[str, torch.Tensor],
    env_id: int,
    *,
    p50_abs_unclipped_6d: Sequence[float] | None = None,
    p95_abs_unclipped_6d: Sequence[float] | None = None,
    effort_limit_6d: torch.Tensor | None = None,
) -> dict[str, Any]:
    """Finalize one episode with typed N/A metrics for absent denominators."""

    if isinstance(env_id, bool) or not isinstance(env_id, int):
        raise ValueError("env_id must be an integer.")
    num_envs = state["valid_frames"].shape[0]
    if env_id < 0 or env_id >= num_envs:
        raise ValueError("env_id is outside the v21-B accumulator.")
    dtype = state["unclipped_abs_sum_6d"].dtype
    device = state["valid_frames"].device
    _validate_accumulator(state, num_envs=num_envs, dtype=dtype, device=device)
    count = int(state["valid_frames"][env_id].item())
    if count == 0:
        p50: Any = _na("no valid arm telemetry frames", 0)
        p95: Any = _na("no valid arm telemetry frames", 0)
        mean_position: Any = _na("no valid arm telemetry frames", 0)
        mean_velocity: Any = _na("no valid arm telemetry frames", 0)
        utilization = _na("no valid arm telemetry frames", 0)
        unclipped_utilization_p50 = _na("no valid arm telemetry frames", 0)
        unclipped_utilization_p95 = _na("no valid arm telemetry frames", 0)
        frame_utilization_ge_090 = _na("no valid arm telemetry frames", 0)
        frame_utilization_ge_098 = _na("no valid arm telemetry frames", 0)
        unclipped_utilization_max = _na("no valid arm telemetry frames", 0)
    else:
        if "unclipped_abs_samples_6d" in state:
            sample_mask = state["unclipped_abs_sample_mask"][env_id]
            samples = state["unclipped_abs_samples_6d"][env_id][sample_mask]
            if samples.shape[0] != count:
                raise RuntimeError(
                    "v21-B per-sample history count disagrees with valid_frames; "
                    f"history={samples.shape[0]}, valid_frames={count}."
                )
            p50 = torch.quantile(samples, 0.50, dim=0).detach().cpu().tolist()
            p95 = torch.quantile(samples, 0.95, dim=0).detach().cpu().tolist()
        elif p50_abs_unclipped_6d is None or p95_abs_unclipped_6d is None:
            p50 = _na("per-sample history not retained by live accumulator", count)
            p95 = _na("per-sample history not retained by live accumulator", count)
        else:
            if len(p50_abs_unclipped_6d) != 6 or len(p95_abs_unclipped_6d) != 6:
                raise ValueError("episode p50/p95 arrays must have exactly six arm joints.")
            p50 = [float(_finite_scalar(value, name="p50")) for value in p50_abs_unclipped_6d]
            p95 = [float(_finite_scalar(value, name="p95")) for value in p95_abs_unclipped_6d]
        mean_position = (state["position_error_abs_sum_6d"][env_id] / count).detach().cpu().tolist()
        mean_velocity = (state["velocity_abs_sum_6d"][env_id] / count).detach().cpu().tolist()
        if effort_limit_6d is None:
            utilization = _na("effort-limit field was not retained by live accumulator", count)
            unclipped_utilization_p50 = _na("effort-limit field was not retained by live accumulator", count)
            unclipped_utilization_p95 = _na("effort-limit field was not retained by live accumulator", count)
            frame_utilization_ge_090 = _na("effort-limit field was not retained by live accumulator", count)
            frame_utilization_ge_098 = _na("effort-limit field was not retained by live accumulator", count)
            unclipped_utilization_max = _na("effort-limit field was not retained by live accumulator", count)
        else:
            _require_matrix(effort_limit_6d, name="episode effort_limit_6d")
            if effort_limit_6d.shape != (num_envs, 6) or effort_limit_6d.dtype != dtype or effort_limit_6d.device != device:
                raise ValueError("episode effort_limit_6d must have shape (N,6), matching dtype/device.")
            if torch.any(effort_limit_6d[env_id] <= 0.0):
                raise ValueError("episode effort_limit_6d must be strictly positive.")
            limits = effort_limit_6d[env_id].detach().cpu().tolist()
            utilization = (state["clipped_abs_max_6d"][env_id] / effort_limit_6d[env_id]).detach().cpu().tolist()
            unclipped_utilization_max = (state["unclipped_abs_max_6d"][env_id] / effort_limit_6d[env_id]).detach().cpu().tolist()
            frame_utilization_ge_090 = float(state["frame_ge_090_count"][env_id].item()) / count
            frame_utilization_ge_098 = float(state["frame_ge_098_count"][env_id].item()) / count
            if isinstance(p50, list) and isinstance(p95, list):
                unclipped_utilization_p50 = [float(value) / limit for value, limit in zip(p50, limits)]
                unclipped_utilization_p95 = [float(value) / limit for value, limit in zip(p95, limits)]
            else:
                unclipped_utilization_p50 = _na("unclipped p50 unavailable", count)
                unclipped_utilization_p95 = _na("unclipped p95 unavailable", count)
    return {
        "schema": V21B_EVIDENCE_SCHEMA,
        "joint_names": list(V21B_ARM_JOINT_NAMES),
        "valid_frame_count": count,
        "arm_pd_effort_estimate_unclipped_p50_6d": p50,
        "arm_pd_effort_estimate_unclipped_p95_6d": p95,
        "arm_pd_effort_estimate_unclipped_max_6d": state["unclipped_abs_max_6d"][env_id].detach().cpu().tolist() if count else _na("no valid arm telemetry frames", 0),
        "arm_pd_effort_estimate_clipped_max_6d": state["clipped_abs_max_6d"][env_id].detach().cpu().tolist() if count else _na("no valid arm telemetry frames", 0),
        "arm_pd_effort_estimate_unclipped_utilization_p50_6d": unclipped_utilization_p50,
        "arm_pd_effort_estimate_unclipped_utilization_p95_6d": unclipped_utilization_p95,
        "arm_pd_effort_estimated_saturation_fraction_6d": (state["saturation_frames_6d"][env_id].to(dtype) / count).detach().cpu().tolist() if count else _na("no valid arm telemetry frames", 0),
        "fraction_of_valid_frames_ge_0.90_6d": (state["ge_090_frames_6d"][env_id].to(dtype) / count).detach().cpu().tolist() if count else _na("no valid arm telemetry frames", 0),
        "fraction_of_valid_frames_ge_0.98_6d": (state["ge_098_frames_6d"][env_id].to(dtype) / count).detach().cpu().tolist() if count else _na("no valid arm telemetry frames", 0),
        "arm_joint_position_error_abs_mean_6d": mean_position,
        "arm_joint_position_error_abs_max_6d": state["position_error_abs_max_6d"][env_id].detach().cpu().tolist() if count else _na("no valid arm telemetry frames", 0),
        "arm_joint_velocity_abs_mean_6d": mean_velocity,
        "arm_joint_velocity_abs_max_6d": state["velocity_abs_max_6d"][env_id].detach().cpu().tolist() if count else _na("no valid arm telemetry frames", 0),
        "arm_pd_effort_estimate_clipped_utilization_max": utilization,
        "arm_pd_effort_estimate_clipped_utilization_max_6d": utilization,
        "arm_pd_effort_estimate_unclipped_utilization_max_6d": unclipped_utilization_max,
        "fraction_of_valid_frames_max_utilization_ge_0.90": frame_utilization_ge_090,
        "fraction_of_valid_frames_max_utilization_ge_0.98": frame_utilization_ge_098,
        "isaaclab_implicit_effort_estimate_authority": V21B_AUTHORITY_LABEL,
    }


def a2_v21b_build_census_frames_from_episode(
    state: Mapping[str, torch.Tensor],
    env_id: int,
    *,
    scenario_id: str,
    topology: str,
    episode_id: str,
    source_checkpoint_sha256: str,
    source_lock_sha256: str,
    source_config_sha256: str,
    materialization_sha256: str,
    materialized_config_sha256: str,
    door_weight_kg: float,
    hinge_force_nm: float,
    phase: str,
) -> list[dict[str, Any]]:
    """Export real per-frame unclipped estimates retained by the live accumulator."""

    if phase != "CENSUS_PRE_K":
        raise ValueError("census frame export is only valid during CENSUS_PRE_K")
    if topology not in ("canonical16", "heavy16"):
        raise ValueError("census frame topology must be canonical16 or heavy16")
    if not isinstance(scenario_id, str) or not scenario_id or not isinstance(episode_id, str) or not episode_id:
        raise ValueError("census frame scenario_id and episode_id are required")
    for value, name in ((source_checkpoint_sha256, "source checkpoint"), (source_lock_sha256, "source lock"), (source_config_sha256, "source config"), (materialization_sha256, "materialization"), (materialized_config_sha256, "materialized config")):
        _require_digest(value, name=f"census frame {name}")
    for value, name in ((door_weight_kg, "door_weight_kg"), (hinge_force_nm, "hinge_force_nm")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"census frame {name} must be finite and strictly positive")
    if "unclipped_abs_samples_6d" not in state or "unclipped_abs_sample_mask" not in state:
        raise ValueError("census frame export requires retained per-frame history")
    num_envs = int(state["valid_frames"].shape[0])
    dtype = state["unclipped_abs_samples_6d"].dtype
    device = state["unclipped_abs_samples_6d"].device
    _validate_accumulator(state, num_envs=num_envs, dtype=dtype, device=device)
    if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < num_envs:
        raise ValueError("census frame env_id is invalid")
    sample_mask = state["unclipped_abs_sample_mask"][env_id]
    samples = state["unclipped_abs_samples_6d"][env_id][sample_mask]
    steps = torch.nonzero(sample_mask, as_tuple=False).squeeze(1).detach().cpu().tolist()
    if samples.shape[0] == 0:
        raise ValueError("census frame export requires at least one valid frame")
    frames: list[dict[str, Any]] = []
    for step, values in zip(steps, samples.detach().cpu().tolist()):
        frames.append({
            "frame_id": f"{episode_id}:env{env_id}:step{step}",
            "episode_id": episode_id,
            "env_id": env_id,
            "step_index": int(step),
            "scenario_id": scenario_id,
            "topology": topology,
            "door_weight_kg": float(door_weight_kg),
            "hinge_force_nm": float(hinge_force_nm),
            "heavy_bucket": topology == "heavy16",
            "valid": True,
            "arm_pd_effort_estimate_unclipped_6d": [float(value) for value in values],
            "source_checkpoint_sha256": source_checkpoint_sha256,
            "source_lock_sha256": source_lock_sha256,
            "source_config_sha256": source_config_sha256,
            "phase": phase,
            "materialization_phase": phase,
            "materialization_sha256": materialization_sha256,
            "materialized_config_sha256": materialized_config_sha256,
            "authority": V21B_AUTHORITY_LABEL,
        })
    return frames


def a2_v21b_export_census_frames(path: str | Path, frames: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Write bounded raw census rows with no-overwrite semantics."""

    if not isinstance(frames, Sequence) or isinstance(frames, (str, bytes, bytearray)) or not frames:
        raise ValueError("census frame export requires a non-empty sequence")
    rows = [dict(frame) for frame in frames]
    frame_ids = [row.get("frame_id") for row in rows]
    if any(not isinstance(frame_id, str) or not frame_id for frame_id in frame_ids) or len(set(frame_ids)) != len(frame_ids):
        raise ValueError("census frame export requires unique non-empty frame_id values")
    for row in rows:
        if row.get("valid") is not True or row.get("phase") != "CENSUS_PRE_K" or row.get("materialization_phase") != "CENSUS_PRE_K" or row.get("authority") != V21B_AUTHORITY_LABEL:
            raise ValueError("census frame export requires valid CENSUS_PRE_K estimate-only rows")
        raw = row.get("arm_pd_effort_estimate_unclipped_6d")
        if not isinstance(raw, list) or len(raw) != 6 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in raw):
            raise ValueError("census frame export requires finite six-joint raw effort rows")
        for key in ("episode_id", "scenario_id"):
            if not isinstance(row.get(key), str) or not row.get(key):
                raise ValueError(f"census frame export requires {key}")
        if row.get("topology") not in ("canonical16", "heavy16"):
            raise ValueError("census frame export topology must be canonical16 or heavy16")
        for key in ("door_weight_kg", "hinge_force_nm"):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"census frame export requires positive finite {key}")
        for key in ("source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256"):
            _require_digest(row.get(key), name=f"census frame {key}")
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"census frame export path already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    with target.open("xb") as handle:
        handle.write(payload)
        handle.flush()
    return {"path": str(target), "frame_count": len(rows), "frame_ids": frame_ids}


def _require_rows(values: torch.Tensor, *, name: str, columns: int = 6) -> tuple[int, torch.dtype, torch.device]:
    return _require_matrix(values, name=name, columns=columns)


def a2_v21b_census_from_unclipped(
    unclipped_abs_effort: torch.Tensor,
    heavy_frame_mask: torch.Tensor,
    *,
    candidate_limits_nm: Sequence[float] = V21B_CANDIDATE_LIMITS_NM,
    census_limit_nm: float = 100.0,
    right_censor_threshold: float = 0.05,
    raw_heavy_valid_frame_count: int | None = None,
    right_censored_heavy_frame_count_at_100Nm: int | None = None,
) -> dict[str, Any]:
    """Select k from per-episode peaks while optionally guarding on raw frames.

    ``unclipped_abs_effort`` is the candidate-selection input.  Callers that
    reduced raw telemetry to one peak per episode must provide the raw heavy
    frame counts so the 100 N*m right-censor guard cannot accidentally become
    an episode-level statistic.
    """

    rows, dtype, device = _require_rows(unclipped_abs_effort, name="census unclipped absolute effort")
    _require_vector(heavy_frame_mask, name="census heavy_frame_mask", n=rows, dtype=torch.bool)
    if heavy_frame_mask.device != device:
        raise ValueError("census heavy_frame_mask must share device with effort rows.")
    limits = tuple(_finite_scalar(value, name="candidate limit", positive=True) for value in candidate_limits_nm)
    if not limits or any(left <= right for left, right in zip(limits, limits[1:])):
        raise ValueError("candidate limits must be a non-empty strictly descending sequence.")
    census_limit = _finite_scalar(census_limit_nm, name="census limit", positive=True)
    censor_threshold = _finite_scalar(right_censor_threshold, name="right-censor threshold")
    if not 0.0 <= censor_threshold <= 1.0:
        raise ValueError("right-censor threshold must lie in [0,1].")
    heavy_count = int(heavy_frame_mask.sum().item())
    light_count = rows - heavy_count
    if heavy_count == 0 or light_count == 0:
        raise ValueError(
            "v21-B census requires at least one heavy and one light telemetry frame; "
            f"heavy={heavy_count}, light={light_count}."
        )
    abs_effort = torch.abs(unclipped_abs_effort)
    heavy_frame_peaks = torch.amax(abs_effort[heavy_frame_mask], dim=-1)
    light_frame_peaks = torch.amax(abs_effort[~heavy_frame_mask], dim=-1)
    if (raw_heavy_valid_frame_count is None) != (right_censored_heavy_frame_count_at_100Nm is None):
        raise ValueError("raw heavy-frame count and right-censored count must be supplied together")
    if raw_heavy_valid_frame_count is None:
        raw_heavy_valid_frame_count = heavy_count
    if isinstance(raw_heavy_valid_frame_count, bool) or not isinstance(raw_heavy_valid_frame_count, int) or raw_heavy_valid_frame_count <= 0:
        raise ValueError("raw_heavy_valid_frame_count must be a positive integer")
    if right_censored_heavy_frame_count_at_100Nm is None:
        right_censored_heavy_frame_count_at_100Nm = int((heavy_frame_peaks >= census_limit).sum().item())
    if isinstance(right_censored_heavy_frame_count_at_100Nm, bool) or not isinstance(right_censored_heavy_frame_count_at_100Nm, int) or right_censored_heavy_frame_count_at_100Nm < 0 or right_censored_heavy_frame_count_at_100Nm > raw_heavy_valid_frame_count:
        raise ValueError("right_censored_heavy_frame_count_at_100Nm must be an integer in the raw heavy-frame range")
    right_censored_fraction = float(right_censored_heavy_frame_count_at_100Nm / raw_heavy_valid_frame_count)
    if right_censored_fraction > censor_threshold:
        return {
            "schema": V21B_EVIDENCE_SCHEMA,
            "status": V21B_CENSUS_RIGHT_CENSORED,
            "selection": "N/A",
            "heavy_episode_count": heavy_count,
            "light_episode_count": light_count,
            "raw_heavy_valid_frame_count": raw_heavy_valid_frame_count,
            "right_censored_heavy_frame_count_at_100Nm": right_censored_heavy_frame_count_at_100Nm,
            "right_censored_heavy_frame_fraction_at_100Nm": right_censored_fraction,
            "right_censor_threshold": censor_threshold,
            "authority": V21B_AUTHORITY_LABEL,
        }
    heavy_episode_peaks = heavy_frame_peaks
    light_episode_peaks = light_frame_peaks
    candidates: list[dict[str, Any]] = []
    selected: float | None = None
    for limit in limits:
        heavy_fraction = float((heavy_episode_peaks >= limit).to(torch.float64).mean().item()) if heavy_episode_peaks.numel() else None
        light_fraction = float((light_episode_peaks <= 0.85 * limit).to(torch.float64).mean().item()) if light_episode_peaks.numel() else None
        satisfies = heavy_fraction is not None and light_fraction is not None and heavy_fraction >= 0.30 and light_fraction >= 0.80
        candidates.append({"limit_nm": limit, "heavy_peak_ge_limit_fraction": heavy_fraction, "light_peak_le_0.85_limit_fraction": light_fraction, "heavy_episode_peak_ge_limit_fraction": heavy_fraction, "light_episode_peak_le_0.85_limit_fraction": light_fraction, "satisfies": satisfies})
        if selected is None and satisfies:
            selected = limit
    return {
        "schema": V21B_EVIDENCE_SCHEMA,
        "status": "CENSUS_PASS" if selected is not None else "BOUNDARY_NOT_SEPARABLE",
        "selection": selected if selected is not None else "N/A",
        "candidate_grid_nm": list(limits),
        "candidates": candidates,
        "heavy_episode_count": heavy_count,
        "light_episode_count": light_count,
        "raw_heavy_valid_frame_count": raw_heavy_valid_frame_count,
        "right_censored_heavy_frame_count_at_100Nm": right_censored_heavy_frame_count_at_100Nm,
        "right_censored_heavy_frame_fraction_at_100Nm": right_censored_fraction,
        "right_censor_threshold": censor_threshold,
        "authority": V21B_AUTHORITY_LABEL,
    }


def a2_v21b_adjudicate_dv2(
    clipped_abs_effort: torch.Tensor,
    heavy_frame_mask: torch.Tensor,
    matched_v20_position_error_abs: torch.Tensor | None,
    realistic_position_error_abs: torch.Tensor,
    *,
    effort_limit_nm: float,
) -> dict[str, Any]:
    """Adjudicate saturation plus tracking-error corroboration for DV2."""

    rows, dtype, device = _require_rows(clipped_abs_effort, name="DV2 clipped absolute effort")
    _require_vector(heavy_frame_mask, name="DV2 heavy_frame_mask", n=rows, dtype=torch.bool)
    if heavy_frame_mask.device != device:
        raise ValueError("DV2 heavy_frame_mask must share device with clipped effort.")
    limit = _finite_scalar(effort_limit_nm, name="DV2 effort limit", positive=True)
    if not torch.is_tensor(realistic_position_error_abs) or realistic_position_error_abs.ndim != 2 or realistic_position_error_abs.shape != (rows, 6) or realistic_position_error_abs.device != device or realistic_position_error_abs.dtype != dtype or not realistic_position_error_abs.is_floating_point() or not torch.all(torch.isfinite(realistic_position_error_abs)):
        raise ValueError("DV2 realistic tracking error requires finite shape (N,6) on the effort device.")
    if matched_v20_position_error_abs is not None:
        if not torch.is_tensor(matched_v20_position_error_abs) or matched_v20_position_error_abs.shape != (rows, 6) or matched_v20_position_error_abs.device != device or matched_v20_position_error_abs.dtype != dtype or not torch.all(torch.isfinite(matched_v20_position_error_abs)):
            raise ValueError("DV2 matched v20 tracking error must match the realistic tensor contract.")
    utilization = torch.abs(clipped_abs_effort) / limit
    heavy_count = int(heavy_frame_mask.sum().item())
    light_count = rows - heavy_count
    if heavy_count == 0 or light_count == 0:
        raise ValueError(
            "DV2 adjudication requires both heavy and light frames; "
            f"heavy={heavy_count}, light={light_count}."
        )
    heavy_frame_utilization = torch.amax(utilization[heavy_frame_mask], dim=-1)
    light_frame_utilization = torch.amax(utilization[~heavy_frame_mask], dim=-1)
    saturation_fraction = float((heavy_frame_utilization >= 0.98).to(torch.float64).mean().item())
    light_saturation_fraction = float((light_frame_utilization >= 0.98).to(torch.float64).mean().item())
    if matched_v20_position_error_abs is None:
        corroborated: bool | None = None
    else:
        heavy_real = torch.amax(torch.abs(realistic_position_error_abs[heavy_frame_mask]), dim=-1).mean()
        heavy_v20 = torch.amax(torch.abs(matched_v20_position_error_abs[heavy_frame_mask]), dim=-1).mean()
        corroborated = bool((heavy_real > heavy_v20).item())
    # A light-bucket saturation pattern is adjudicated first: it means the
    # configured limit is globally binding, so it cannot support a heavy-only
    # feasibility boundary even when tracking error happens to corroborate.
    if matched_v20_position_error_abs is None:
        label = V21B_BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED
    elif light_saturation_fraction >= 0.30:
        label = V21B_BOUNDARY_SATURATED_EVERYWHERE
    elif saturation_fraction >= 0.30 and corroborated:
        label = V21B_BOUNDARY_CREATED
    elif saturation_fraction >= 0.30:
        label = V21B_BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED
    elif saturation_fraction <= 0.05:
        label = V21B_BOUNDARY_ABSENT
    else:
        label = V21B_BOUNDARY_ABSENT
    return {
        "schema": V21B_EVIDENCE_SCHEMA,
        "label": label,
        "effort_limit_nm": limit,
        "heavy_valid_frame_count": heavy_count,
        "light_valid_frame_count": light_count,
        "heavy_clipped_utilization_ge_0.98_fraction": saturation_fraction,
        "light_clipped_utilization_ge_0.98_fraction": light_saturation_fraction,
        "tracking_error_corroborated": corroborated,
        "authority": V21B_AUTHORITY_LABEL,
    }


def a2_v21b_validate_evidence_record(
    record: Mapping[str, Any],
    *,
    require_implicit_effort_estimates: bool = False,
) -> None:
    """Reject malformed v21-B evidence and unsupported torque claims.

    Base accumulator finalizer records may omit live implicit-effort snapshots;
    enriched terminal records opt into their strict three-field contract.
    """

    if not isinstance(record, Mapping) or record.get("schema") != V21B_EVIDENCE_SCHEMA:
        raise ValueError(f"v21-B arm evidence requires schema {V21B_EVIDENCE_SCHEMA!r}.")
    if not isinstance(require_implicit_effort_estimates, bool):
        raise ValueError("v21-B evidence implicit-effort strict selector must be boolean.")
    if tuple(record.get("joint_names", ())) != V21B_ARM_JOINT_NAMES:
        raise ValueError("v21-B arm evidence requires exact arm_j1..arm_j6 joint order.")
    if record.get("isaaclab_implicit_effort_estimate_authority") != V21B_AUTHORITY_LABEL and record.get("authority") != V21B_AUTHORITY_LABEL:
        raise ValueError("v21-B arm evidence requires the exact estimate-only authority label.")
    valid_frame_count = record.get("valid_frame_count")
    if isinstance(valid_frame_count, bool) or not isinstance(valid_frame_count, int) or valid_frame_count < 0:
        raise ValueError("v21-B arm evidence valid_frame_count must be a non-negative integer.")
    implicit_field_names = (
        "isaaclab_implicit_computed_effort_estimate_6d",
        "isaaclab_implicit_applied_effort_estimate_6d",
        "isaaclab_implicit_effort_estimate_crosscheck_error_6d",
    )
    present_implicit_fields = tuple(field_name for field_name in implicit_field_names if field_name in record)
    if present_implicit_fields and len(present_implicit_fields) != len(implicit_field_names):
        raise ValueError("v21-B arm evidence requires all three implicit effort estimate fields together.")
    if require_implicit_effort_estimates and len(present_implicit_fields) != len(implicit_field_names):
        raise ValueError("v21-B terminal evidence requires all three implicit effort estimate fields.")
    if present_implicit_fields:
        for field_name in implicit_field_names:
            value = record[field_name]
            if valid_frame_count == 0:
                denominator = value.get("denominator") if isinstance(value, Mapping) else None
                if (
                    not isinstance(value, Mapping)
                    or set(value) != {"status", "reason", "denominator"}
                    or value.get("status") != "N/A"
                    or value.get("reason") != "no valid arm telemetry frames"
                    or isinstance(denominator, bool)
                    or not isinstance(denominator, int)
                    or denominator != 0
                ):
                    raise ValueError(
                        f"v21-B arm evidence {field_name} must be typed N/A when valid_frame_count is zero."
                    )
            elif (
                not isinstance(value, list)
                or len(value) != 6
                or any(
                    isinstance(component, bool)
                    or not isinstance(component, (int, float))
                    or not math.isfinite(float(component))
                    for component in value
                )
            ):
                raise ValueError(
                    f"v21-B arm evidence {field_name} must be a finite numeric six-joint vector."
                )
    forbidden = ("true_physx_torque", "actual_physx_drive_torque", "incoming_joint_force")
    if any(key in record for key in forbidden):
        raise ValueError("v21-B evidence cannot claim true PhysX torque or implement incoming-joint force.")


def a2_v21b_build_terminal_record(
    evidence: Mapping[str, Any],
    *,
    plan_id: str,
    cell: str,
    group: str,
    seed: int,
    source_checkpoint_sha256: str,
    adaptation_bundle_sha256: str | None,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the versioned v21-B terminal export consumed before reset."""

    a2_v21b_validate_evidence_record(evidence, require_implicit_effort_estimates=True)
    if plan_id != "base_v21B_theta_arm_ablation_v1":
        raise ValueError("v21-B terminal record requires the v21-B plan id.")
    if cell not in {"B1", "B2", "B3", "B4", "B5", "B6", "B7"}:
        raise ValueError("v21-B terminal record cell must be one of B1-B7.")
    if not isinstance(group, str) or not group:
        raise ValueError("v21-B terminal record group is required.")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed not in (0, 1):
        raise ValueError("v21-B terminal record seed must be an integer.")
    _require_digest(source_checkpoint_sha256, name="v21-B terminal record source checkpoint")
    if not isinstance(provenance, Mapping):
        raise ValueError("v21-B terminal record requires phase-correct provenance")
    phase = provenance.get("materialization_phase", provenance.get("phase"))
    if phase not in ("POST_CENSUS", "FORMAL_PROMOTED"):
        raise ValueError("v21-B terminal record phase must be POST_CENSUS or FORMAL_PROMOTED")
    for key in ("source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256"):
        _require_digest(provenance.get(key), name=f"v21-B terminal provenance {key}")
    if phase == "POST_CENSUS":
        if adaptation_bundle_sha256 is not None:
            raise ValueError("POST_CENSUS terminal records must not fabricate an adaptation bundle digest")
    else:
        _require_digest(adaptation_bundle_sha256, name="v21-B terminal record adaptation bundle")
    if not isinstance(provenance.get("scenario_id"), str) or not provenance["scenario_id"]:
        raise ValueError("v21-B terminal provenance requires scenario_id")
    if provenance.get("topology") not in ("canonical16", "heavy16"):
        raise ValueError("v21-B terminal provenance requires canonical16/heavy16 topology")
    if not isinstance(provenance.get("episode_id"), str) or not provenance["episode_id"]:
        raise ValueError("v21-B terminal provenance requires episode_id")
    body = {
        "schema": V21B_TERMINAL_RECORD_SCHEMA,
        "plan_id": plan_id,
        "cell": cell,
        "group": group,
        "seed": seed,
        "source_checkpoint_sha256": source_checkpoint_sha256,
        "adaptation_bundle_sha256": adaptation_bundle_sha256,
        "materialization_phase": phase,
        "authority": V21B_AUTHORITY_LABEL,
        "evidence": dict(evidence),
    }
    if provenance is not None:
        if not isinstance(provenance, Mapping):
            raise ValueError("v21-B terminal provenance must be a mapping.")
        provenance_body = dict(provenance)
        provenance_body["source_checkpoint_sha256"] = source_checkpoint_sha256
        body["provenance"] = provenance_body
    body["record_id"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    a2_v21b_validate_terminal_record(body)
    return body


def a2_v21b_validate_terminal_record(record: Mapping[str, Any]) -> None:
    if not isinstance(record, Mapping) or record.get("schema") != V21B_TERMINAL_RECORD_SCHEMA:
        raise ValueError("v21-B terminal record schema is invalid.")
    if record.get("authority") != V21B_AUTHORITY_LABEL:
        raise ValueError("v21-B terminal record authority is invalid.")
    if record.get("plan_id") != "base_v21B_theta_arm_ablation_v1" or record.get("cell") not in {"B1", "B2", "B3", "B4", "B5", "B6", "B7"} or record.get("group") != record.get("cell") or isinstance(record.get("seed"), bool) or record.get("seed") not in (0, 1):
        raise ValueError("v21-B terminal record plan/cell/group/seed binding is invalid")
    _require_digest(record.get("source_checkpoint_sha256"), name="v21-B terminal source checkpoint")
    evidence = record.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError("v21-B terminal record evidence is missing.")
    a2_v21b_validate_evidence_record(evidence, require_implicit_effort_estimates=True)
    phase = record.get("materialization_phase")
    if phase not in ("POST_CENSUS", "FORMAL_PROMOTED"):
        raise ValueError("v21-B terminal record materialization phase is invalid")
    adaptation = record.get("adaptation_bundle_sha256")
    if phase == "POST_CENSUS":
        if adaptation is not None:
            raise ValueError("POST_CENSUS terminal record contains an adaptation digest")
    else:
        _require_digest(adaptation, name="v21-B terminal adaptation bundle")
    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping) or provenance.get("materialization_phase") != phase:
        raise ValueError("v21-B terminal provenance phase is not bound")
    if provenance.get("source_checkpoint_sha256") not in (None, record.get("source_checkpoint_sha256")):
        raise ValueError("v21-B terminal provenance source checkpoint is not bound")
    if not isinstance(provenance.get("scenario_id"), str) or not provenance["scenario_id"] or provenance.get("topology") not in ("canonical16", "heavy16") or not isinstance(provenance.get("episode_id"), str) or not provenance["episode_id"]:
        raise ValueError("v21-B terminal provenance identity is incomplete")
    for key in ("source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256"):
        _require_digest(provenance.get(key), name=f"v21-B terminal provenance {key}")
    record_id = record.get("record_id")
    if not isinstance(record_id, str) or len(record_id) != 64:
        raise ValueError("v21-B terminal record id is missing.")
    unsigned = dict(record)
    unsigned.pop("record_id", None)
    expected = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    if record_id != expected:
        raise ValueError("v21-B terminal record id does not bind its payload.")


def a2_v21b_export_terminal_record(path: str | Path, record: Mapping[str, Any]) -> dict[str, Any]:
    """Write one terminal record with no-overwrite semantics before reset."""

    a2_v21b_validate_terminal_record(record)
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"v21-B terminal export path already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    with target.open("xb") as handle:
        handle.write(payload)
        handle.flush()
    return dict(record)


__all__ = [
    "V21B_EVIDENCE_SCHEMA", "V21B_STEP_SCHEMA", "V21B_TERMINAL_RECORD_SCHEMA", "V21B_AUTHORITY_LABEL", "V21B_CENSUS_RIGHT_CENSORED",
    "V21B_BOUNDARY_CREATED", "V21B_BOUNDARY_ABSENT", "V21B_BOUNDARY_SATURATED_EVERYWHERE",
    "V21B_BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED", "V21B_ARM_JOINT_NAMES", "V21B_CANDIDATE_LIMITS_NM",
    "a2_v21b_arm_pd_effort_estimates", "a2_v21b_arm_tracking_error", "a2_v21b_build_step_evidence",
    "a2_v21b_init_arm_episode_accumulator", "a2_v21b_reset_arm_episode_accumulator",
    "a2_v21b_accumulate_arm_step", "a2_v21b_finalize_arm_episode", "a2_v21b_census_from_unclipped",
    "a2_v21b_build_census_frames_from_episode", "a2_v21b_export_census_frames",
    "a2_v21b_adjudicate_dv2", "a2_v21b_validate_evidence_record", "a2_v21b_build_terminal_record",
    "a2_v21b_validate_terminal_record", "a2_v21b_export_terminal_record",
]
