"""Pure base_v23 core contracts.

The helpers in this module are intentionally small and device-local.  They
provide the shared contracts used by the actor mask, forward-only evaluation
interventions, and estimate-only arm telemetry.  Nothing here reads solver
torque or clones simulator state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

import torch


V23_TORQUE_SCHEMA = "a2_piper_base_v23_torque_step_v1"
V23_TORQUE_EPISODE_SCHEMA = "a2_piper_base_v23_torque_episode_v1"
V23_TORQUE_AUTHORITY_NOMINAL_PD = "ESTIMATE_ONLY/NOMINAL_PD"
V23_TORQUE_AUTHORITY_CLIPPED_COMMAND = "ESTIMATE_ONLY/CLIPPED_COMMAND_TORQUE"
V23_TORQUE_SOURCE_AUTHORITY = "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE"

V23_FORWARD_INTERVENTION_MODES = (
    "FULL",
    "ACUTE_RP0",
    "BASE0_AT_GRASP",
    "HIGHER_EFFORT_RESCUE",
    "ORACLE_TANGENTIAL_ASSIST",
)

# P0.5 is deliberately narrower than the historical v23 intervention helper.
# Keeping a separate mode tuple prevents a producer from mixing unrelated
# intervention records into the rescue certificate.
V23_P05_STEP_SCHEMA = "a2_piper_v23_step_trace_v1"
V23_P05_WINDOW_SCHEMA = "a2_piper_v23_window_record_v1"
V23_P05_EPISODE_SCHEMA = "a2_piper_v23_episode_record_v1"
V23_P05_PAIR_SCHEMA = "a2_piper_v23_prefix_pair_v2"
V23_P05_MODES = ("FULL", "ACUTE_RP0", "HIGHER_EFFORT_RESCUE")
V23_P05_PURPOSES = ("P05_CERTIFICATE", "D1_CAPABILITY_SOURCE")
V23_P05_FAILURE_FLAGS = (
    "FALL",
    "LOST_GRASP",
    "DOOR_FRAME_COLLISION",
    "TIMEOUT_WRONG_STAGE",
)
V23_P05_RESCUE_NOT_APPLICABLE_BASELINE_AT_MAX = (
    "RESCUE_NOT_APPLICABLE_BASELINE_AT_MAX"
)

# P0.2 temporal evidence is deliberately separate from the terminal aggregate
# telemetry above.  A reducer may select a rung only from these raw rows; the
# old max-over-terminal aggregate remains a pending artifact and is never a
# substitute for temporal evidence.
V23_TEMPORAL_STEP_SCHEMA = "a2_piper_base_v23_p0_temporal_step_v1"
V23_TEMPORAL_EPISODE_SCHEMA = "a2_piper_base_v23_p0_temporal_episode_v1"
V23_TEMPORAL_EXPORT_SCHEMA = "a2_piper_base_v23_p0_temporal_records_v1"
V23_TEMPORAL_TOPOLOGIES = ("canonical16", "heavy16")
V23_TEMPORAL_WINDOW_STEPS = 25
V23_TEMPORAL_STABLE_MIN_STEPS = 20
V23_TEMPORAL_PD_REVERSALS = 4
V23_TEMPORAL_PD_LOBE_FRACTION = 0.10
V23_TEMPORAL_CLIPPED_FRACTION = 0.90
V23_TEMPORAL_SATURATION_FRACTION = 0.30
V23_TEMPORAL_PROGRESS_THRESHOLD_RAD = 0.02


def _temporal_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number; got {value!r}.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite; got {value!r}.")
    return result


def _temporal_vector(value: Any, *, name: str, length: int = 6) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != length:
        raise ValueError(f"{name} requires exactly {length} values.")
    return [_temporal_number(item, name=f"{name}[{index}]") for index, item in enumerate(value)]


def _temporal_failures(value: Any) -> dict[str, bool]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("temporal failure_flags must be a mapping.")
    result = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, bool):
            raise ValueError("temporal failure_flags must map names to bool values.")
        result[key] = item
    return result


def a2_v23_build_temporal_step_record(
    *,
    effort_nm: float,
    topology: str,
    env_id: int,
    episode_index: int,
    episode_id: str,
    control_step: int,
    stage: int,
    stable_grasp_streak: int,
    hinge_angle_rad: float,
    nominal_torque_nm: Sequence[float],
    clipped_torque_nm: Sequence[float],
    effort_limit_nm: Sequence[float],
    joint_velocity_rad_s: Sequence[float],
    joint_velocity_limit_rad_s: Sequence[float],
    joint_target_rad: Sequence[float],
    failure_flags: Mapping[str, bool] | None = None,
    physics_frames: Sequence[Mapping[str, Any]] | None = None,
    joint_target_increment_rad: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Build one raw control-step row for the temporal ladder materializer.

    The producer carries raw vectors and optional per-physics-frame rows.  No
    aggregate or inferred label is written here; the temporary A0 label is
    attached at episode/export level only.
    """

    effort = _temporal_number(effort_nm, name="effort_nm")
    if effort <= 0.0:
        raise ValueError("effort_nm must be positive.")
    if topology not in V23_TEMPORAL_TOPOLOGIES:
        raise ValueError(f"temporal topology must be one of {V23_TEMPORAL_TOPOLOGIES}.")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (env_id, episode_index, control_step)):
        raise ValueError("temporal env_id, episode_index, and control_step must be non-negative integers.")
    if not isinstance(episode_id, str) or not episode_id:
        raise ValueError("temporal episode_id must be non-empty.")
    if isinstance(stage, bool) or not isinstance(stage, int):
        raise ValueError("temporal stage must be an integer.")
    if isinstance(stable_grasp_streak, bool) or not isinstance(stable_grasp_streak, int) or stable_grasp_streak < 0:
        raise ValueError("stable_grasp_streak must be a non-negative integer.")
    nominal = _temporal_vector(nominal_torque_nm, name="nominal_torque_nm")
    clipped = _temporal_vector(clipped_torque_nm, name="clipped_torque_nm")
    limits = _temporal_vector(effort_limit_nm, name="effort_limit_nm")
    velocity = _temporal_vector(joint_velocity_rad_s, name="joint_velocity_rad_s")
    velocity_limits = _temporal_vector(joint_velocity_limit_rad_s, name="joint_velocity_limit_rad_s")
    target = _temporal_vector(joint_target_rad, name="joint_target_rad")
    if any(value <= 0.0 for value in limits + velocity_limits):
        raise ValueError("temporal effort and velocity limits must be positive.")
    if (
        physics_frames is None
        or isinstance(physics_frames, (str, bytes))
        or not isinstance(physics_frames, Sequence)
        or not physics_frames
    ):
        raise ValueError("physics_frames must contain every real physics substep; no synthetic frame is allowed.")
    frame_rows = []
    for frame_index, frame in enumerate(physics_frames):
        if not isinstance(frame, Mapping):
            raise ValueError(f"physics_frames[{frame_index}] must be an object.")
        declared_index = frame.get("physics_frame_index")
        if declared_index != frame_index:
            raise ValueError(
                "physics_frames must carry contiguous physics_frame_index values starting at zero."
            )
        frame_nominal = _temporal_vector(
            frame.get("nominal_torque_nm"), name=f"physics_frames[{frame_index}].nominal_torque_nm"
        )
        frame_clipped = _temporal_vector(
            frame.get("clipped_torque_nm"), name=f"physics_frames[{frame_index}].clipped_torque_nm"
        )
        frame_limits = _temporal_vector(
            frame.get("effort_limit_nm"), name=f"physics_frames[{frame_index}].effort_limit_nm"
        )
        frame_velocity = _temporal_vector(
            frame.get("joint_velocity_rad_s"), name=f"physics_frames[{frame_index}].joint_velocity_rad_s"
        )
        frame_velocity_limits = _temporal_vector(
            frame.get("joint_velocity_limit_rad_s"),
            name=f"physics_frames[{frame_index}].joint_velocity_limit_rad_s",
        )
        frame_target = _temporal_vector(
            frame.get("joint_target_rad"), name=f"physics_frames[{frame_index}].joint_target_rad"
        )
        frame_target_increment = _temporal_vector(
            frame.get("joint_target_increment_rad"),
            name=f"physics_frames[{frame_index}].joint_target_increment_rad",
        )
        if any(value <= 0.0 for value in frame_limits + frame_velocity_limits):
            raise ValueError("physics-frame effort and velocity limits must be positive.")
        frame_rows.append(
            {
                "physics_frame_index": declared_index,
                "nominal_torque_nm": frame_nominal,
                "clipped_torque_nm": frame_clipped,
                "effort_limit_nm": frame_limits,
                "joint_velocity_rad_s": frame_velocity,
                "joint_velocity_limit_rad_s": frame_velocity_limits,
                "joint_target_rad": frame_target,
                "joint_target_increment_rad": frame_target_increment,
            }
        )
    if joint_target_increment_rad is None:
        target_increment = list(frame_rows[0]["joint_target_increment_rad"])
    else:
        target_increment = _temporal_vector(
            joint_target_increment_rad, name="joint_target_increment_rad"
        )
    return {
        "schema": V23_TEMPORAL_STEP_SCHEMA,
        "effort_nm": effort,
        "topology": topology,
        "env_id": env_id,
        "episode_index": episode_index,
        "episode_id": episode_id,
        "control_step": control_step,
        "stage": stage,
        "stable_grasp_streak": stable_grasp_streak,
        "stable_grasp": stable_grasp_streak >= V23_TEMPORAL_STABLE_MIN_STEPS,
        "hinge_angle_rad": _temporal_number(hinge_angle_rad, name="hinge_angle_rad"),
        "nominal_torque_nm": nominal,
        "clipped_torque_nm": clipped,
        "effort_limit_nm": limits,
        "joint_velocity_rad_s": velocity,
        "joint_velocity_limit_rad_s": velocity_limits,
        "joint_target_rad": target,
        "joint_target_increment_rad": target_increment,
        "failure_flags": _temporal_failures(failure_flags),
        "physics_frames": frame_rows,
    }


def a2_v23_build_temporal_episode_record(
    *, effort_nm: float, topology: str, env_id: int, episode_index: int, episode_id: str,
    step_rows: Sequence[Mapping[str, Any]], temporary_label: str = "A0_CANONICAL16_P0_REFERENCE",
    source_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if temporary_label != "A0_CANONICAL16_P0_REFERENCE":
        raise ValueError("temporal episode temporary_label must be A0_CANONICAL16_P0_REFERENCE.")
    if not isinstance(step_rows, Sequence) or isinstance(step_rows, (str, bytes)) or not step_rows:
        raise ValueError("temporal episode requires non-empty raw step_rows.")
    expected_steps = []
    for index, row in enumerate(step_rows):
        if not isinstance(row, Mapping) or row.get("schema") != V23_TEMPORAL_STEP_SCHEMA:
            raise ValueError(f"temporal step_rows[{index}] must use the temporal step schema.")
        if row.get("effort_nm") != float(effort_nm) or row.get("topology") != topology:
            raise ValueError("temporal episode step rung/topology disagrees with identity.")
        if row.get("env_id") != env_id or row.get("episode_index") != episode_index or row.get("episode_id") != episode_id:
            raise ValueError("temporal episode step identity disagrees with declaration.")
        control_step = row.get("control_step")
        if isinstance(control_step, bool) or not isinstance(control_step, int) or control_step < 0:
            raise ValueError("temporal control_step must be a non-negative integer.")
        expected_steps.append(control_step)
    if expected_steps != sorted(expected_steps) or len(set(expected_steps)) != len(expected_steps):
        raise ValueError("temporal step_rows must be sorted by unique control_step.")
    result = {
        "schema": V23_TEMPORAL_EPISODE_SCHEMA,
        "effort_nm": _temporal_number(effort_nm, name="effort_nm"),
        "topology": topology,
        "env_id": env_id,
        "episode_index": episode_index,
        "episode_id": episode_id,
        "temporary_label": temporary_label,
        "step_rows": [dict(row) for row in step_rows],
        "raw_temporal": True,
        "selection_authority": "TEMPORAL_REDUCER_REQUIRED",
    }
    if source_provenance is not None:
        if not isinstance(source_provenance, Mapping):
            raise ValueError("temporal source_provenance must be a mapping when supplied.")
        result["source_provenance"] = dict(source_provenance)
    return result


def a2_v23_select_temporal_window(
    step_rows: Sequence[Mapping[str, Any]], *, window_steps: int = V23_TEMPORAL_WINDOW_STEPS,
) -> dict[str, Any] | None:
    """Select the lexicographically first valid 25-control-step window."""

    if window_steps != V23_TEMPORAL_WINDOW_STEPS:
        raise ValueError("P0.2 temporal windows are fixed at exactly 25 control steps.")
    rows = sorted(step_rows, key=lambda row: row.get("control_step", -1))
    for start in range(0, len(rows) - window_steps + 1):
        window = rows[start : start + window_steps]
        steps = [row.get("control_step") for row in window]
        if steps != list(range(steps[0], steps[0] + window_steps)):
            continue
        if any(row.get("stage") not in (3, 4) for row in window):
            continue
        stable_steps = sum(
            bool(row.get("stable_grasp", False)) or int(row.get("stable_grasp_streak", 0)) >= V23_TEMPORAL_STABLE_MIN_STEPS
            for row in window
        )
        if stable_steps < V23_TEMPORAL_STABLE_MIN_STEPS:
            continue
        if any(any(bool(flag) for flag in (row.get("failure_flags") or {}).values()) for row in window):
            continue
        return {
            "start_control_step": steps[0],
            "end_control_step": steps[-1],
            "rows": list(window),
            "stable_grasp_steps": stable_steps,
            "selection_rule": "LEXICOGRAPHIC_FIRST_FAILURE_FREE_CONSECUTIVE_25_CONTROL_STEPS_STAGE3_OR4_STABLE_GRASP_GE20",
        }
    return None


def a2_v23_temporal_window_metrics(window: Mapping[str, Any]) -> dict[str, Any]:
    rows = window.get("rows") if isinstance(window, Mapping) else None
    if not isinstance(rows, list) or len(rows) != V23_TEMPORAL_WINDOW_STEPS:
        raise ValueError("temporal window metrics require exactly 25 rows.")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("temporal window rows must be mappings.")
    physics_frames = []
    frame_counts = set()
    ordered_rows = sorted(rows, key=lambda row: row.get("control_step", -1))
    if [row.get("control_step") for row in ordered_rows] != list(
        range(ordered_rows[0].get("control_step"), ordered_rows[0].get("control_step") + len(ordered_rows))
    ):
        raise ValueError("temporal window control steps must be contiguous and ordered.")
    first, last = ordered_rows[0], ordered_rows[-1]
    progress = _temporal_number(last.get("hinge_angle_rad"), name="window.end.hinge_angle_rad") - _temporal_number(first.get("hinge_angle_rad"), name="window.start.hinge_angle_rad")
    for row in ordered_rows:
        if not isinstance(row, Mapping) or row.get("schema") != V23_TEMPORAL_STEP_SCHEMA:
            raise ValueError("temporal window rows require the exact temporal-step schema.")
        frames = row.get("physics_frames")
        if not isinstance(frames, list) or not frames:
            raise ValueError("temporal window rows require non-empty physics_frames.")
        frame_counts.add(len(frames))
        for expected_index, frame in enumerate(frames):
            if not isinstance(frame, Mapping) or frame.get("physics_frame_index") != expected_index:
                raise ValueError("temporal physics-frame indices must be contiguous per control step.")
            # Validate every frame before any reduction.  The producer's frame
            # vectors are the sole source for the PD predicate below.
            _temporal_vector(frame.get("nominal_torque_nm"), name="physics_frame.nominal_torque_nm")
            _temporal_vector(frame.get("clipped_torque_nm"), name="physics_frame.clipped_torque_nm")
            _temporal_vector(frame.get("effort_limit_nm"), name="physics_frame.effort_limit_nm")
            _temporal_vector(frame.get("joint_velocity_rad_s"), name="physics_frame.joint_velocity_rad_s")
            _temporal_vector(
                frame.get("joint_velocity_limit_rad_s"),
                name="physics_frame.joint_velocity_limit_rad_s",
            )
            _temporal_vector(frame.get("joint_target_rad"), name="physics_frame.joint_target_rad")
            _temporal_vector(
                frame.get("joint_target_increment_rad"),
                name="physics_frame.joint_target_increment_rad",
            )
        physics_frames.extend(frames)
    if len(frame_counts) != 1:
        raise ValueError("temporal window physics-frame counts must be identical for every control step.")
    saturated_frames = 0
    for frame in physics_frames:
        nominal = _temporal_vector(frame.get("nominal_torque_nm"), name="physics_frame.nominal_torque_nm")
        clipped = _temporal_vector(frame.get("clipped_torque_nm"), name="physics_frame.clipped_torque_nm")
        limits = _temporal_vector(frame.get("effort_limit_nm"), name="physics_frame.effort_limit_nm")
        saturated = any(
            abs(n) > limit and abs(c) / limit >= V23_TEMPORAL_CLIPPED_FRACTION
            for n, c, limit in zip(nominal, clipped, limits)
        )
        saturated_frames += int(saturated)
    saturation_fraction = saturated_frames / len(physics_frames)

    def _sign_lobes(values: Sequence[float]) -> list[tuple[int, list[float]]]:
        lobes: list[tuple[int, list[float]]] = []
        for value in values:
            sign = 1 if value > 0.0 else -1 if value < 0.0 else 0
            if not sign:
                continue
            if not lobes or lobes[-1][0] != sign:
                lobes.append((sign, [float(value)]))
            else:
                lobes[-1][1].append(float(value))
        return lobes

    frame_by_joint = {
        "velocity": list(zip(*[_temporal_vector(frame["joint_velocity_rad_s"], name="physics_frame.joint_velocity_rad_s") for frame in physics_frames])),
        "velocity_limit": list(zip(*[_temporal_vector(frame["joint_velocity_limit_rad_s"], name="physics_frame.joint_velocity_limit_rad_s") for frame in physics_frames])),
        "clipped": list(zip(*[_temporal_vector(frame["clipped_torque_nm"], name="physics_frame.clipped_torque_nm") for frame in physics_frames])),
        "effort_limit": list(zip(*[_temporal_vector(frame["effort_limit_nm"], name="physics_frame.effort_limit_nm") for frame in physics_frames])),
        "target_increment": list(zip(*[_temporal_vector(frame["joint_target_increment_rad"], name="physics_frame.joint_target_increment_rad") for frame in physics_frames])),
    }
    if any(
        limit <= 0.0
        for joint_limits in (frame_by_joint["velocity_limit"], frame_by_joint["effort_limit"])
        for limits in joint_limits
        for limit in limits
    ):
        raise ValueError("temporal physics-frame velocity/effort limits must be strictly positive.")
    pd_joint_predicates = []
    for joint, velocities in enumerate(frame_by_joint["velocity"]):
        velocity_lobes: list[tuple[int, list[int]]] = []
        for frame_index, value in enumerate(velocities):
            sign = 1 if value > 0.0 else -1 if value < 0.0 else 0
            if not sign:
                continue
            if not velocity_lobes or velocity_lobes[-1][0] != sign:
                velocity_lobes.append((sign, [frame_index]))
            else:
                velocity_lobes[-1][1].append(frame_index)
        reversal_count = max(0, len(velocity_lobes) - 1)
        lobe_peaks: list[tuple[int, float, float]] = []
        for sign, indices in velocity_lobes:
            peak_index = max(indices, key=lambda item: abs(velocities[item]))
            velocity_ratio = abs(velocities[peak_index]) / frame_by_joint["velocity_limit"][joint][peak_index]
            clipped_index = max(indices, key=lambda item: abs(frame_by_joint["clipped"][joint][item]))
            clipped_value = frame_by_joint["clipped"][joint][clipped_index]
            clipped_ratio = abs(clipped_value) / frame_by_joint["effort_limit"][joint][clipped_index]
            lobe_peaks.append((1 if clipped_value > 0.0 else -1 if clipped_value < 0.0 else 0, velocity_ratio, clipped_ratio))
        lobe_ok = len(lobe_peaks) >= V23_TEMPORAL_PD_REVERSALS + 1 and all(
            velocity_ratio >= V23_TEMPORAL_PD_LOBE_FRACTION and clipped_ratio >= V23_TEMPORAL_CLIPPED_FRACTION
            for _torque_sign, velocity_ratio, clipped_ratio in lobe_peaks
        )
        torque_signs = [item[0] for item in lobe_peaks]
        torque_alternates = len(torque_signs) >= V23_TEMPORAL_PD_REVERSALS + 1 and all(
            sign != 0 and sign != previous
            for previous, sign in zip(torque_signs, torque_signs[1:])
        )
        target_increments = frame_by_joint["target_increment"][joint]
        target_signs = _sign_lobes(target_increments)
        target_reversals = max(0, len(target_signs) - 1)
        pd_joint_predicates.append(
            reversal_count >= V23_TEMPORAL_PD_REVERSALS and lobe_ok and torque_alternates and target_reversals <= 1
        )
    return {
        "progress_rad": progress,
        "physics_frame_count": len(physics_frames),
        "saturated_physics_frame_count": saturated_frames,
        "saturation_fraction": saturation_fraction,
        "meaningful_saturation": saturation_fraction >= V23_TEMPORAL_SATURATION_FRACTION,
        "obvious_pd_predicate_by_joint": pd_joint_predicates,
        "obvious_pd": any(pd_joint_predicates),
        "stable_grasp_steps": window.get("stable_grasp_steps"),
        "window_start_hinge_angle_rad": first.get("hinge_angle_rad"),
        "window_end_hinge_angle_rad": last.get("hinge_angle_rad"),
    }


def _require_matrix(value: torch.Tensor, *, name: str, columns: int) -> tuple[int, torch.dtype, torch.device]:
    if not torch.is_tensor(value) or value.ndim != 2 or value.shape[1] != columns:
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{name} requires a floating tensor with shape (N,{columns}); got {shape}.")
    if not value.is_floating_point() or not torch.all(torch.isfinite(value)):
        raise ValueError(f"{name} requires finite floating values.")
    return value.shape[0], value.dtype, value.device


def _require_same_matrix(
    value: torch.Tensor,
    *,
    name: str,
    rows: int,
    columns: int,
    dtype: torch.dtype,
    device: torch.device,
) -> None:
    n, value_dtype, value_device = _require_matrix(value, name=name, columns=columns)
    if (n, value_dtype, value_device) != (rows, dtype, device):
        raise ValueError(f"{name} must share shape, dtype, and device with the primary tensor.")


def _require_env_mask(value: torch.Tensor, *, name: str, rows: int, device: torch.device) -> None:
    if (
        not torch.is_tensor(value)
        or tuple(value.shape) != (rows,)
        or value.dtype != torch.bool
        or value.device != device
    ):
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{name} requires bool shape ({rows},) on the action device; got {shape}.")


def _require_mode(mode: str | None) -> str:
    if mode is None:
        return "FULL"
    if not isinstance(mode, str) or mode not in V23_FORWARD_INTERVENTION_MODES:
        raise ValueError(
            "base_v23 forward intervention mode must be one of "
            f"{V23_FORWARD_INTERVENTION_MODES}; got {mode!r}."
        )
    return mode


def _require_p05_mode(mode: str) -> str:
    if not isinstance(mode, str) or mode not in V23_P05_MODES:
        raise ValueError(f"P0.5 mode must be one of {V23_P05_MODES}; got {mode!r}.")
    return mode


def _p05_finite_float(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number; got {value!r}.")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite; got {value!r}.")
    return result


def _p05_positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer; got {value!r}.")
    return int(value)


def _p05_arm_vector(value: Any, *, name: str) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 6:
        raise ValueError(f"{name} requires six arm-joint values.")
    result = [_p05_finite_float(item, name=f"{name}[{index}]") for index, item in enumerate(value)]
    return result


def _p05_failure_map(value: Any, *, name: str = "failure_flags") -> dict[str, bool]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} requires all four typed failure flags.")
    keys = set(value)
    if keys != set(V23_P05_FAILURE_FLAGS):
        raise ValueError(
            f"{name} must contain exactly {V23_P05_FAILURE_FLAGS}; got {sorted(keys)!r}."
        )
    result = {}
    for flag in V23_P05_FAILURE_FLAGS:
        item = value[flag]
        if not isinstance(item, bool):
            raise ValueError(f"{name}.{flag} must be bool; got {item!r}.")
        result[flag] = item
    return result


def a2_v23_validate_p05_bands(bands: Mapping[str, Any]) -> dict[str, Any]:
    """Validate explicitly selected P0.5 certificate bands.

    The producer/certificate must receive measured bands; this function never
    chooses a threshold when one is absent.  Flat keys are the canonical
    representation, while the two nested range forms are accepted to make the
    CLI input readable without changing the resulting record.
    """

    if not isinstance(bands, Mapping):
        raise ValueError("P0.5 bands must be an explicit mapping.")
    raw = dict(bands)
    conditions = raw.get("conditions")
    if isinstance(conditions, Mapping):
        raw = {**dict(conditions), **{key: value for key, value in raw.items() if key != "conditions"}}
    stable = raw.get("stable_grasp")
    if isinstance(stable, Mapping):
        raw.setdefault("stable_grasp_min_steps", stable.get("minimum_steps", stable.get("min_steps")))
    low_progress = raw.get("low_progress")
    if isinstance(low_progress, Mapping):
        progress_band = low_progress.get("progress_rad_per_window", low_progress.get("progress_rad"))
        window_band = low_progress.get("window_steps")
        if isinstance(progress_band, Sequence) and not isinstance(progress_band, (str, bytes)) and len(progress_band) == 2:
            raw.setdefault("low_progress_min_rad", progress_band[0])
            raw.setdefault("low_progress_max_rad", progress_band[1])
        else:
            raw.setdefault("low_progress_min_rad", low_progress.get("min_rad"))
            raw.setdefault("low_progress_max_rad", low_progress.get("max_rad"))
        if isinstance(window_band, Sequence) and not isinstance(window_band, (str, bytes)) and len(window_band) == 2:
            raw.setdefault("low_progress_window_min_steps", window_band[0])
            raw.setdefault("low_progress_window_max_steps", window_band[1])
        else:
            raw.setdefault("low_progress_window_min_steps", low_progress.get("window_min_steps"))
            raw.setdefault("low_progress_window_max_steps", low_progress.get("window_max_steps"))
    high_effort = raw.get("high_effort")
    if isinstance(high_effort, Mapping):
        raw.setdefault("clipped_utilization_min", high_effort.get("ratio_minimum"))
        raw.setdefault("clipped_fraction_min", high_effort.get("window_fraction_minimum"))
    rescue_progress = raw.get("rescue_progress")
    if isinstance(rescue_progress, Mapping):
        progress_band = rescue_progress.get("progress_rad_per_window", rescue_progress.get("progress_rad"))
        if isinstance(progress_band, Sequence) and not isinstance(progress_band, (str, bytes)) and len(progress_band) == 2:
            raw.setdefault("rescue_progress_min_rad", progress_band[0])
            raw.setdefault("rescue_progress_max_rad", progress_band[1])
        else:
            raw.setdefault("rescue_progress_min_rad", rescue_progress.get("min_rad"))
            raw.setdefault("rescue_progress_max_rad", rescue_progress.get("max_rad"))

    required = (
        "stable_grasp_min_steps",
        "low_progress_min_rad",
        "low_progress_max_rad",
        "low_progress_window_min_steps",
        "low_progress_window_max_steps",
        "clipped_utilization_min",
        "clipped_fraction_min",
        "rescue_progress_min_rad",
        "rescue_progress_max_rad",
    )
    missing = [key for key in required if key not in raw or raw[key] is None]
    if missing:
        raise ValueError(f"P0.5 bands require measured explicit values: {missing!r}.")

    grasp_steps = _p05_positive_int(raw["stable_grasp_min_steps"], name="stable_grasp_min_steps")
    if grasp_steps < 20:
        raise ValueError("stable_grasp_min_steps must be at least 20.")
    low_min = _p05_finite_float(raw["low_progress_min_rad"], name="low_progress_min_rad")
    low_max = _p05_finite_float(raw["low_progress_max_rad"], name="low_progress_max_rad")
    if not (0.02 <= low_min <= low_max <= 0.04):
        raise ValueError("low progress band must be within [0.02, 0.04] rad.")
    window_min = _p05_positive_int(
        raw["low_progress_window_min_steps"], name="low_progress_window_min_steps"
    )
    window_max = _p05_positive_int(
        raw["low_progress_window_max_steps"], name="low_progress_window_max_steps"
    )
    if not (25 <= window_min <= window_max <= 40):
        raise ValueError("low progress window must be within 25..40 control steps.")
    clipped_min = _p05_finite_float(raw["clipped_utilization_min"], name="clipped_utilization_min")
    clipped_fraction = _p05_finite_float(raw["clipped_fraction_min"], name="clipped_fraction_min")
    if not (0.0 < clipped_min <= 1.0) or clipped_min < 0.90:
        raise ValueError("clipped_utilization_min must be at least 0.90 and at most 1.0.")
    if not (0.0 < clipped_fraction <= 1.0) or clipped_fraction < 0.30:
        raise ValueError("clipped_fraction_min must be at least 0.30 and at most 1.0.")
    rescue_min = _p05_finite_float(raw["rescue_progress_min_rad"], name="rescue_progress_min_rad")
    rescue_max = _p05_finite_float(raw["rescue_progress_max_rad"], name="rescue_progress_max_rad")
    if not (0.10 <= rescue_min <= rescue_max <= 0.15):
        raise ValueError("rescue progress band must be within [0.10, 0.15] rad.")
    return {
        "stable_grasp_min_steps": grasp_steps,
        "low_progress_min_rad": low_min,
        "low_progress_max_rad": low_max,
        "low_progress_window_min_steps": window_min,
        "low_progress_window_max_steps": window_max,
        "clipped_utilization_min": clipped_min,
        "clipped_fraction_min": clipped_fraction,
        "rescue_progress_min_rad": rescue_min,
        "rescue_progress_max_rad": rescue_max,
    }


def _p05_identity(record: Mapping[str, Any], *, name: str) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError(f"{name} identity requires a mapping.")
    required = (
        "checkpoint",
        "config",
        "scenario",
        "topology",
        "seed",
        "episode_id",
        "checkpoint_load_mode",
        "cell_id",
        "geometry_id",
        "canonical_geometry",
    )
    missing = [key for key in required if key not in record]
    if missing:
        raise ValueError(f"{name} identity is missing {missing!r}; no provenance fallback is allowed.")
    if isinstance(record["seed"], bool) or not isinstance(record["seed"], int):
        raise ValueError(f"{name}.seed must be an integer.")
    if record["checkpoint_load_mode"] != "policy_only":
        raise ValueError(f"{name}.checkpoint_load_mode must be policy_only.")
    for key in ("checkpoint", "config", "scenario", "topology", "episode_id", "cell_id", "geometry_id"):
        if not isinstance(record[key], str) or not record[key]:
            raise ValueError(f"{name}.{key} must be a non-empty string.")
    if not isinstance(record["canonical_geometry"], Mapping):
        raise ValueError(f"{name}.canonical_geometry must be a mapping.")
    return {key: record[key] for key in required}


def a2_v23_build_p05_step_record(
    *,
    scenario: str,
    topology: str,
    env_id: int,
    episode_index: int,
    episode_id: str,
    checkpoint: str,
    config: str,
    seed: int,
    checkpoint_load_mode: str,
    mode: str,
    plain_prefix_id: str,
    control_step: int,
    switch_step: int,
    stable_grasp_predicates: Mapping[str, bool],
    stable_grasp_streak: int,
    hinge_position_rad: float,
    hinge_velocity_rad_s: float,
    window_progress_rad: float,
    arm_nominal_torque_nm: Sequence[float],
    arm_clipped_torque_nm: Sequence[float],
    arm_effort_limit_nm: Sequence[float],
    failure_flags: Mapping[str, bool],
    requested_rescue_profile: Mapping[str, Any],
    applied_rescue_profile: Mapping[str, Any],
    clipped_utilization_min: float,
    post_switch_progress_rad: float | None = None,
    capability_sample: Mapping[str, Any] | None = None,
    purpose: str = "P05_CERTIFICATE",
) -> dict[str, Any]:
    """Create one JSON-safe producer row with every P0.5 denominator explicit."""

    _require_p05_mode(mode)
    if purpose not in V23_P05_PURPOSES:
        raise ValueError(f"P0.5 purpose must be one of {V23_P05_PURPOSES}; got {purpose!r}.")
    for name, value in (
        ("scenario", scenario),
        ("topology", topology),
        ("episode_id", episode_id),
        ("checkpoint", checkpoint),
        ("config", config),
        ("plain_prefix_id", plain_prefix_id),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string.")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0:
        raise ValueError("env_id must be a non-negative integer.")
    if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
        raise ValueError("episode_index must be a non-negative integer.")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer.")
    if checkpoint_load_mode != "policy_only":
        raise ValueError("checkpoint_load_mode must be policy_only.")
    if isinstance(control_step, bool) or not isinstance(control_step, int) or control_step < 0:
        raise ValueError("control_step must be a non-negative integer.")
    if isinstance(switch_step, bool) or not isinstance(switch_step, int) or switch_step < -1:
        raise ValueError("switch_step must be -1 or a non-negative integer.")
    if not isinstance(stable_grasp_predicates, Mapping) or not stable_grasp_predicates:
        raise ValueError("stable_grasp_predicates must preserve raw predicate fields.")
    predicates = {}
    for key, value in stable_grasp_predicates.items():
        if not isinstance(key, str) or not key or not isinstance(value, bool):
            raise ValueError("stable_grasp_predicates must map non-empty names to bool values.")
        predicates[key] = value
    if isinstance(stable_grasp_streak, bool) or not isinstance(stable_grasp_streak, int) or stable_grasp_streak < 0:
        raise ValueError("stable_grasp_streak must be a non-negative integer.")
    values = {
        "hinge_position_rad": _p05_finite_float(hinge_position_rad, name="hinge_position_rad"),
        "hinge_velocity_rad_s": _p05_finite_float(hinge_velocity_rad_s, name="hinge_velocity_rad_s"),
        "window_progress_rad": _p05_finite_float(window_progress_rad, name="window_progress_rad"),
    }
    nominal = _p05_arm_vector(arm_nominal_torque_nm, name="arm_nominal_torque_nm")
    clipped = _p05_arm_vector(arm_clipped_torque_nm, name="arm_clipped_torque_nm")
    limits = _p05_arm_vector(arm_effort_limit_nm, name="arm_effort_limit_nm")
    if any(limit <= 0.0 or limit > 100.0 for limit in limits):
        raise ValueError("arm_effort_limit_nm must be positive and never exceed 100 Nm.")
    selected_utilization_min = _p05_finite_float(
        clipped_utilization_min, name="clipped_utilization_min"
    )
    if not 0.90 <= selected_utilization_min <= 1.0:
        raise ValueError("clipped_utilization_min must be within [0.90, 1.0].")
    failures = _p05_failure_map(failure_flags)
    if not isinstance(requested_rescue_profile, Mapping) or not isinstance(applied_rescue_profile, Mapping):
        raise ValueError("requested_rescue_profile and applied_rescue_profile are typed mappings.")
    requested = dict(requested_rescue_profile)
    applied = dict(applied_rescue_profile)
    for profile_name, profile in (("requested_rescue_profile", requested), ("applied_rescue_profile", applied)):
        if "status" not in profile or not isinstance(profile["status"], str) or not profile["status"]:
            raise ValueError(f"{profile_name}.status is required and typed.")
    if post_switch_progress_rad is not None:
        values["post_switch_progress_rad"] = _p05_finite_float(
            post_switch_progress_rad, name="post_switch_progress_rad"
        )
    else:
        values["post_switch_progress_rad"] = {"status": "NOT_SWITCHED"}
    utilization = [abs(item) / limit for item, limit in zip(clipped, limits)]
    clipped_fraction = sum(item >= selected_utilization_min for item in utilization) / 6.0
    if capability_sample is None or not isinstance(capability_sample, Mapping):
        raise ValueError("P0.4 capability_sample is required on every P0.5 raw step row.")
    cell_id = capability_sample.get("cell_id")
    geometry_id = capability_sample.get("geometry_id")
    canonical_geometry = capability_sample.get("canonical_geometry")
    if (
        not isinstance(cell_id, str)
        or not isinstance(geometry_id, str)
        or not isinstance(canonical_geometry, Mapping)
        or capability_sample.get("checkpoint_load_mode") != checkpoint_load_mode
    ):
        raise ValueError("capability_sample must carry exact cell/geometry/canonical/load-mode provenance.")
    result = {
        "schema": V23_P05_STEP_SCHEMA,
        "scenario": scenario,
        "topology": topology,
        "env_id": env_id,
        "episode_index": episode_index,
        "episode_id": episode_id,
        "checkpoint": checkpoint,
        "config": config,
        "seed": seed,
        "checkpoint_load_mode": checkpoint_load_mode,
        "cell_id": cell_id,
        "geometry_id": geometry_id,
        "canonical_geometry": dict(canonical_geometry),
        "mode": mode,
        "purpose": purpose,
        "plain_prefix_id": plain_prefix_id,
        "control_step": control_step,
        "switch_step": switch_step,
        "stable_grasp_predicates": predicates,
        "stable_grasp_streak": stable_grasp_streak,
        "stable_grasp": all(predicates.values()) and stable_grasp_streak >= 20,
        **values,
        "arm_nominal_torque_nm": nominal,
        "arm_clipped_torque_nm": clipped,
        "arm_effort_limit_nm": limits,
        "arm_utilization": utilization,
        "clipped_utilization_min": selected_utilization_min,
        "clipped_utilization_fraction": clipped_fraction,
        "effort_authority": "ESTIMATE_ONLY/CLIPPED_COMMAND_TORQUE",
        "torque_source_authority": "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE",
        "failure_flags": failures,
        "requested_rescue_profile": requested,
        "applied_rescue_profile": applied,
        "state_clone_supported": False,
        "forward_only": True,
    }
    result["capability_sample"] = dict(capability_sample)
    return result


def _p05_prefix_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping) or row.get("schema") != V23_P05_STEP_SCHEMA:
        raise ValueError("P0.5 prefix rows require the step-trace schema.")
    excluded = {
        "mode",
        "switch_step",
        "requested_rescue_profile",
        "applied_rescue_profile",
        "post_switch_progress_rad",
    }
    projected = {key: row[key] for key in row if key not in excluded}
    capability_sample = projected.get("capability_sample")
    if isinstance(capability_sample, Mapping):
        capability_identity = capability_sample.get("identity")
        if isinstance(capability_identity, Mapping) and "mode" in capability_identity:
            projected_capability = dict(capability_sample)
            projected_capability["identity"] = {
                key: value for key, value in capability_identity.items() if key != "mode"
            }
            projected["capability_sample"] = projected_capability
    return projected


def a2_v23_validate_p05_prefix(
    full_record: Mapping[str, Any], rescue_record: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare registered pre-switch rows directly; no clone or filename proof."""

    if not isinstance(full_record, Mapping) or not isinstance(rescue_record, Mapping):
        raise ValueError("P0.5 prefix comparison requires two episode mappings.")
    if full_record.get("mode") != "FULL" or rescue_record.get("mode") != "HIGHER_EFFORT_RESCUE":
        raise ValueError("P0.5 prefix comparison requires FULL and HIGHER_EFFORT_RESCUE records.")
    if full_record.get("state_clone_supported") is not False or rescue_record.get("state_clone_supported") is not False:
        raise ValueError("P0.5 pairing forbids state-clone provenance.")
    full_identity = _p05_identity(full_record, name="FULL")
    rescue_identity = _p05_identity(rescue_record, name="HIGHER_EFFORT_RESCUE")
    if full_identity != rescue_identity:
        raise ValueError("P0.5 paired records do not share checkpoint/config/scenario/topology/seed/episode.")
    full_switch = full_record.get("switch_step")
    rescue_switch = rescue_record.get("switch_step")
    for label, switch_step in (("FULL", full_switch), ("HIGHER_EFFORT_RESCUE", rescue_switch)):
        if isinstance(switch_step, bool) or not isinstance(switch_step, int) or switch_step < -1:
            raise ValueError(f"{label} switch_step must be -1 or a non-negative integer.")
    full_rows = full_record.get("step_rows")
    rescue_rows = rescue_record.get("step_rows")
    if isinstance(full_rows, (str, bytes)) or not isinstance(full_rows, Sequence) or not full_rows:
        raise ValueError("FULL step_rows must be a non-empty sequence.")
    if isinstance(rescue_rows, (str, bytes)) or not isinstance(rescue_rows, Sequence) or not rescue_rows:
        raise ValueError("HIGHER_EFFORT_RESCUE step_rows must be a non-empty sequence.")
    for label, rows, mode in (
        ("FULL", full_rows, "FULL"),
        ("HIGHER_EFFORT_RESCUE", rescue_rows, "HIGHER_EFFORT_RESCUE"),
    ):
        steps = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping) or row.get("schema") != V23_P05_STEP_SCHEMA:
                raise ValueError(f"{label} step_rows[{index}] must use the P0.5 step schema.")
            if row.get("mode") != mode:
                raise ValueError(f"{label} step_rows[{index}] mode does not match its episode.")
            control_step = row.get("control_step")
            if isinstance(control_step, bool) or not isinstance(control_step, int) or control_step < 0:
                raise ValueError(f"{label} step_rows[{index}] control_step must be non-negative.")
            steps.append(control_step)
        if steps != list(range(steps[0], steps[0] + len(steps))):
            raise ValueError(f"{label} step_rows must be ordered and contiguous.")
        if steps[0] != 0:
            raise ValueError(f"{label} step_rows must begin at control_step 0.")
    if full_switch != -1:
        raise ValueError("FULL rescue identity must remain unswitched with switch_step=-1.")
    if rescue_switch == -1:
        if rescue_record.get("rescue_status") != "NOT_REQUESTED":
            raise ValueError("unswitched rescue identity must use rescue_status=NOT_REQUESTED.")
        if rescue_record.get("requested_rescue_profile") != {"status": "NOT_REQUESTED"}:
            raise ValueError("unswitched rescue identity must use a NOT_REQUESTED request profile.")
        if rescue_record.get("applied_rescue_profile") != {"status": "NOT_EXECUTED"}:
            raise ValueError("unswitched rescue identity must use a NOT_EXECUTED applied profile.")
        for index, row in enumerate(rescue_rows):
            if row.get("switch_step") != -1:
                raise ValueError(f"unswitched rescue row {index} must use switch_step=-1.")
            if row.get("requested_rescue_profile") != {"status": "NOT_REQUESTED"}:
                raise ValueError(f"unswitched rescue row {index} has a rescue request profile.")
            if row.get("applied_rescue_profile") != {"status": "NOT_EXECUTED"}:
                raise ValueError(f"unswitched rescue row {index} has an applied rescue profile.")
        return {
            "schema": V23_P05_PAIR_SCHEMA,
            "pair_status": "NO_RESCUE_LATCH",
            "prefix_equal": None,
            "prefix_row_count": 0,
            "identity": full_identity,
            "full_mode": "FULL",
            "rescue_mode": "HIGHER_EFFORT_RESCUE",
            "rescue_status": "NOT_APPLICABLE_NO_SWITCH",
            "qualification_status": "NONQUALIFYING",
            "reason": "NO_VALID_RESCUE_LATCH",
            "state_clone_supported": False,
            "comparison": "no_valid_rescue_latch_no_prefix",
        }
    rescue_status = rescue_record.get("rescue_status")
    if rescue_status not in ("APPLIED", V23_P05_RESCUE_NOT_APPLICABLE_BASELINE_AT_MAX):
        raise ValueError("P0.5 rescue pair requires APPLIED or typed baseline-at-max status.")
    expected_applied_status = (
        "APPLIED"
        if rescue_status == "APPLIED"
        else V23_P05_RESCUE_NOT_APPLICABLE_BASELINE_AT_MAX
    )
    for index, row in enumerate(rescue_rows):
        if row["control_step"] <= rescue_switch:
            if row.get("switch_step") != -1:
                raise ValueError(f"switched rescue prefix row {index} must use switch_step=-1.")
            if row.get("requested_rescue_profile") != {"status": "NOT_REQUESTED"}:
                raise ValueError(f"switched rescue prefix row {index} has a rescue request profile.")
            if row.get("applied_rescue_profile") != {"status": "NOT_EXECUTED"}:
                raise ValueError(f"switched rescue prefix row {index} has an applied rescue profile.")
        else:
            if row.get("switch_step") != rescue_switch:
                raise ValueError(f"switched rescue row {index} must preserve its latch step.")
            if row.get("requested_rescue_profile", {}).get("status") != "REQUESTED":
                raise ValueError(f"switched rescue row {index} must expose a REQUESTED profile.")
            if row.get("applied_rescue_profile", {}).get("status") != expected_applied_status:
                raise ValueError(f"switched rescue row {index} applied profile disagrees with rescue status.")
    full_prefix = [row for row in full_rows if row["control_step"] <= rescue_switch]
    rescue_prefix = [row for row in rescue_rows if row["control_step"] <= rescue_switch]
    projected_full = [_p05_prefix_projection(row) for row in full_prefix]
    projected_rescue = [_p05_prefix_projection(row) for row in rescue_prefix]
    if projected_full != projected_rescue:
        raise ValueError("P0.5 pre-switch rows are not directly equal.")
    if not projected_full:
        raise ValueError("P0.5 prefix equality requires at least one registered pre-switch row.")
    return {
        "schema": V23_P05_PAIR_SCHEMA,
        "pair_status": "PREFIX_EQUAL",
        "prefix_equal": True,
        "prefix_row_count": len(projected_full),
        "identity": full_identity,
        "full_mode": "FULL",
        "rescue_mode": "HIGHER_EFFORT_RESCUE",
        "rescue_status": rescue_status,
        "state_clone_supported": False,
        "comparison": "direct_python_equality_of_registered_pre_switch_rows",
    }


def a2_v23_build_p05_window_record(
    rows: Sequence[Mapping[str, Any]],
    *,
    start_step: int,
    end_step: int,
    window_id: str,
) -> dict[str, Any]:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence) or not rows:
        raise ValueError("P0.5 window requires non-empty step rows.")
    if isinstance(start_step, bool) or not isinstance(start_step, int) or start_step < 0:
        raise ValueError("window start_step must be a non-negative integer.")
    if isinstance(end_step, bool) or not isinstance(end_step, int) or end_step < start_step:
        raise ValueError("window end_step must be an integer >= start_step.")
    selected = [row for row in rows if isinstance(row, Mapping) and start_step <= row.get("control_step", -1) <= end_step]
    if len(selected) != end_step - start_step + 1:
        raise ValueError("P0.5 window rows must cover every control step in the selected interval.")
    selected.sort(key=lambda row: row["control_step"])
    if [row["control_step"] for row in selected] != list(range(start_step, end_step + 1)):
        raise ValueError("P0.5 window rows must be ordered and contiguous.")
    first, last = selected[0], selected[-1]
    identity = _p05_identity(first, name="window")
    if any(_p05_identity(row, name="window row") != identity for row in selected[1:]):
        raise ValueError("P0.5 window rows do not share episode identity.")
    if any(row.get("mode") != first.get("mode") for row in selected[1:]):
        raise ValueError("P0.5 window rows must share one intervention mode.")
    if any(row.get("plain_prefix_id") != first.get("plain_prefix_id") for row in selected[1:]):
        raise ValueError("P0.5 window rows must share one plain prefix identity.")
    selected_threshold = _p05_finite_float(
        first.get("clipped_utilization_min"), name="window clipped_utilization_min"
    )
    if not 0.90 <= selected_threshold <= 1.0:
        raise ValueError("window clipped_utilization_min must be within [0.90, 1.0].")
    if any(
        _p05_finite_float(row.get("clipped_utilization_min"), name="window clipped_utilization_min")
        != selected_threshold
        for row in selected[1:]
    ):
        raise ValueError("P0.5 window rows must share the selected utilization threshold.")
    failure_flags = {
        flag: any(_p05_failure_map(row["failure_flags"])[flag] for row in selected)
        for flag in V23_P05_FAILURE_FLAGS
    }
    stable_rows = []
    for row in selected:
        predicates = row.get("stable_grasp_predicates")
        if not isinstance(predicates, Mapping) or not predicates:
            raise ValueError("window stable_grasp_predicates must be a non-empty mapping")
        if any(not isinstance(value, bool) for value in predicates.values()):
            raise ValueError("window stable_grasp_predicates values must be bool")
        streak = row.get("stable_grasp_streak")
        if isinstance(streak, bool) or not isinstance(streak, int) or streak < 0:
            raise ValueError("window stable_grasp_streak must be a non-negative integer")
        stable_rows.append(all(predicates.values()) and streak >= 20)
    row_fractions = []
    utilization_max = 0.0
    for row in selected:
        clipped = _p05_arm_vector(row.get("arm_clipped_torque_nm"), name="window arm_clipped_torque_nm")
        limits = _p05_arm_vector(row.get("arm_effort_limit_nm"), name="window arm_effort_limit_nm")
        utilization = [abs(value) / limit for value, limit in zip(clipped, limits)]
        row_fractions.append(sum(value >= selected_threshold for value in utilization) / 6.0)
        utilization_max = max(utilization_max, max(utilization))
    util_fraction = sum(row_fractions) / len(row_fractions)
    progress = _p05_finite_float(last["hinge_position_rad"], name="window last hinge") - _p05_finite_float(first["hinge_position_rad"], name="window first hinge")
    stable_streak = max(int(row["stable_grasp_streak"]) for row in selected)
    if not isinstance(window_id, str) or not window_id:
        raise ValueError("window_id must be a non-empty string.")
    return {
        "schema": V23_P05_WINDOW_SCHEMA,
        "window_id": window_id,
        **identity,
        "mode": first["mode"],
        "plain_prefix_id": first["plain_prefix_id"],
        "start_step": start_step,
        "end_step": end_step,
        "window_steps": end_step - start_step + 1,
        "stable_grasp_streak_max": stable_streak,
        "stable_grasp_all_rows": all(stable_rows),
        "hinge_position_start_rad": first["hinge_position_rad"],
        "hinge_position_end_rad": last["hinge_position_rad"],
        "progress_rad": progress,
        "clipped_utilization_min": selected_threshold,
        "clipped_window_fraction": util_fraction,
        "clipped_utilization_max": utilization_max,
        "failure_flags": failure_flags,
        "rescue_status": last["applied_rescue_profile"]["status"],
        "state_clone_supported": False,
    }


def a2_v23_build_p05_episode_record(
    *,
    identity: Mapping[str, Any],
    mode: str,
    plain_prefix_id: str,
    step_rows: Sequence[Mapping[str, Any]],
    window_rows: Sequence[Mapping[str, Any]],
    switch_step: int,
    rescue_status: str,
    requested_rescue_profile: Mapping[str, Any],
    applied_rescue_profile: Mapping[str, Any],
    purpose: str = "P05_CERTIFICATE",
) -> dict[str, Any]:
    _require_p05_mode(mode)
    if purpose not in V23_P05_PURPOSES:
        raise ValueError(f"P0.5 purpose must be one of {V23_P05_PURPOSES}; got {purpose!r}.")
    canonical_identity = _p05_identity(identity, name="episode")
    if not isinstance(plain_prefix_id, str) or not plain_prefix_id:
        raise ValueError("plain_prefix_id must be a non-empty string.")
    if isinstance(step_rows, (str, bytes)) or not isinstance(step_rows, Sequence):
        raise ValueError("step_rows must be a sequence.")
    if isinstance(window_rows, (str, bytes)) or not isinstance(window_rows, Sequence):
        raise ValueError("window_rows must be a sequence.")
    if isinstance(switch_step, bool) or not isinstance(switch_step, int) or switch_step < -1:
        raise ValueError("switch_step must be -1 or a non-negative integer.")
    for index, row in enumerate(step_rows):
        if not isinstance(row, Mapping) or row.get("schema") != V23_P05_STEP_SCHEMA:
            raise ValueError(f"episode step_rows[{index}] must use the P0.5 step schema.")
        row_purpose = row.get("purpose", "P05_CERTIFICATE")
        if (
            row.get("mode") != mode
            or row_purpose != purpose
            or row.get("plain_prefix_id") != plain_prefix_id
        ):
            raise ValueError("episode step rows must share the selected mode and plain prefix identity.")
        if _p05_identity(row, name=f"step_rows[{index}]") != canonical_identity:
            raise ValueError("episode step rows do not share the declared episode identity.")
    for index, window in enumerate(window_rows):
        if not isinstance(window, Mapping) or window.get("schema") != V23_P05_WINDOW_SCHEMA:
            raise ValueError(f"episode window_rows[{index}] must use the P0.5 window schema.")
        if window.get("mode") != mode or window.get("plain_prefix_id") != plain_prefix_id:
            raise ValueError("episode windows must share the selected mode and plain prefix identity.")
        if _p05_identity(window, name=f"window_rows[{index}]") != canonical_identity:
            raise ValueError("episode windows do not share the declared episode identity.")
    if not isinstance(rescue_status, str) or not rescue_status:
        raise ValueError("rescue_status must be typed and non-empty.")
    if not isinstance(requested_rescue_profile, Mapping) or not isinstance(applied_rescue_profile, Mapping):
        raise ValueError("episode rescue profiles must be mappings.")
    if (
        not isinstance(requested_rescue_profile.get("status"), str)
        or not requested_rescue_profile.get("status")
        or not isinstance(applied_rescue_profile.get("status"), str)
        or not applied_rescue_profile.get("status")
    ):
        raise ValueError("episode rescue profiles require typed non-empty status fields.")
    return {
        "schema": V23_P05_EPISODE_SCHEMA,
        **canonical_identity,
        "mode": mode,
        "purpose": purpose,
        "plain_prefix_id": plain_prefix_id,
        "switch_step": switch_step,
        "step_rows": list(step_rows),
        "window_rows": list(window_rows),
        "rescue_status": rescue_status,
        "requested_rescue_profile": dict(requested_rescue_profile),
        "applied_rescue_profile": dict(applied_rescue_profile),
        "state_clone_supported": False,
        "forward_only": True,
    }



def a2_v23_apply_forward_intervention(
    raw_base_action: torch.Tensor,
    *,
    mode: str | None,
    stable_grasp_mask: torch.Tensor | None = None,
    oracle_tangential_delta_raw: torch.Tensor | None = None,
    oracle_active_mask: torch.Tensor | None = None,
    higher_effort_profile_applied: bool = False,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Apply an evaluation-only intervention before action execution.

    ``HIGHER_EFFORT_RESCUE`` is a forward-only marker: actuator/gain changes
    belong to the caller's explicitly leased evaluation setup.  The helper
    therefore requires proof that the profile was actually applied before it
    leaves the policy action unchanged.  Oracle tangential assistance is an
    explicit action delta supplied by the caller; no state clone or implicit
    fallback is performed.
    """

    rows, dtype, device = _require_matrix(raw_base_action, name="base_v23 raw base action", columns=5)
    resolved_mode = _require_mode(mode)
    result = raw_base_action.clone()
    metadata: dict[str, Any] = {
        "mode": resolved_mode,
        "forward_only": True,
        "state_clone_supported": False,
        "stable_grasp_mask": None,
    }
    if resolved_mode == "FULL":
        if stable_grasp_mask is not None:
            _require_env_mask(stable_grasp_mask, name="stable_grasp_mask", rows=rows, device=device)
        if oracle_tangential_delta_raw is not None or oracle_active_mask is not None:
            raise ValueError("FULL intervention does not accept oracle action inputs.")
        return result, metadata

    if resolved_mode == "ACUTE_RP0":
        if stable_grasp_mask is not None:
            raise ValueError("ACUTE_RP0 does not accept a stable grasp mask.")
        result[:, 3:5] = 0.0
        metadata["neutralized_raw_indices"] = [3, 4]
        return result, metadata

    if resolved_mode == "BASE0_AT_GRASP":
        if stable_grasp_mask is None:
            raise ValueError("BASE0_AT_GRASP requires a stable grasp mask.")
        _require_env_mask(stable_grasp_mask, name="stable_grasp_mask", rows=rows, device=device)
        result[stable_grasp_mask, 3:5] = 0.0
        metadata["stable_grasp_mask"] = stable_grasp_mask.clone()
        metadata["neutralized_raw_indices"] = [3, 4]
        return result, metadata

    if resolved_mode == "HIGHER_EFFORT_RESCUE":
        if stable_grasp_mask is not None:
            _require_env_mask(stable_grasp_mask, name="stable_grasp_mask", rows=rows, device=device)
        if oracle_tangential_delta_raw is not None or oracle_active_mask is not None:
            raise ValueError("HIGHER_EFFORT_RESCUE does not accept oracle action inputs.")
        if higher_effort_profile_applied is not True:
            raise RuntimeError(
                "HIGHER_EFFORT_RESCUE requires an explicit applied effort-profile proof."
            )
        metadata["requires_explicit_effort_profile"] = True
        metadata["effort_profile_applied"] = True
        return result, metadata

    if stable_grasp_mask is not None:
        _require_env_mask(stable_grasp_mask, name="stable_grasp_mask", rows=rows, device=device)
    if oracle_tangential_delta_raw is None or oracle_active_mask is None:
        raise ValueError(
            "ORACLE_TANGENTIAL_ASSIST requires both oracle_tangential_delta_raw and oracle_active_mask."
        )
    _require_same_matrix(
        oracle_tangential_delta_raw,
        name="oracle_tangential_delta_raw",
        rows=rows,
        columns=5,
        dtype=dtype,
        device=device,
    )
    _require_env_mask(oracle_active_mask, name="oracle_active_mask", rows=rows, device=device)
    result[oracle_active_mask] = result[oracle_active_mask] + oracle_tangential_delta_raw[oracle_active_mask]
    metadata["oracle_active_mask"] = oracle_active_mask.clone()
    metadata["oracle_tangential_delta_raw"] = oracle_tangential_delta_raw.clone()
    return result, metadata


def a2_v23_build_torque_step_telemetry(
    *,
    joint_pos: torch.Tensor,
    joint_vel: torch.Tensor,
    joint_pos_target: torch.Tensor,
    stiffness: torch.Tensor,
    damping: torch.Tensor,
    effort_limit: torch.Tensor,
    implicit_computed_torque: torch.Tensor,
    implicit_applied_torque: torch.Tensor,
    joint_names: Sequence[str],
    valid_mask: torch.Tensor,
    step_index: torch.Tensor | None = None,
) -> dict[str, Any]:
    """Build one estimate-only torque row for any selected arm joint set."""

    if not joint_names or any(not isinstance(name, str) or not name for name in joint_names):
        raise ValueError("v23 torque telemetry requires non-empty joint_names.")
    columns = len(joint_names)
    rows, dtype, device = _require_matrix(joint_pos, name="v23 joint_pos", columns=columns)
    for value, name in (
        (joint_vel, "joint_vel"),
        (joint_pos_target, "joint_pos_target"),
        (stiffness, "stiffness"),
        (damping, "damping"),
        (effort_limit, "effort_limit"),
        (implicit_computed_torque, "implicit_computed_torque"),
        (implicit_applied_torque, "implicit_applied_torque"),
    ):
        _require_same_matrix(
            value,
            name=f"v23 {name}",
            rows=rows,
            columns=columns,
            dtype=dtype,
            device=device,
        )
    if torch.any(effort_limit <= 0.0):
        raise ValueError("v23 joint effort limits must be strictly positive.")
    _require_env_mask(valid_mask, name="v23 torque valid_mask", rows=rows, device=device)
    if step_index is not None:
        if (
            not torch.is_tensor(step_index)
            or tuple(step_index.shape) != (rows,)
            or step_index.dtype != torch.long
            or step_index.device != device
        ):
            raise ValueError("v23 torque step_index requires long shape (N,) on the telemetry device.")

    nominal_pd = stiffness * (joint_pos_target - joint_pos) - damping * joint_vel
    clipped_command = torch.clamp(nominal_pd, min=-effort_limit, max=effort_limit)
    saturation = torch.abs(nominal_pd) > effort_limit
    # Keep the v21-B tracking contract verbatim: target-minus-actual position
    # error with the measured joint velocity carried as corroborating context.
    arm_joint_position_error = joint_pos_target - joint_pos
    arm_joint_velocity = joint_vel
    if not torch.all(torch.isfinite(nominal_pd)) or not torch.all(torch.isfinite(clipped_command)):
        raise RuntimeError("v23 nominal/clipped PD torque estimates are non-finite.")
    if not torch.all(torch.isfinite(arm_joint_position_error)) or not torch.all(torch.isfinite(arm_joint_velocity)):
        raise RuntimeError("v23 arm tracking-error telemetry is non-finite.")
    return {
        "schema": V23_TORQUE_SCHEMA,
        "joint_names": list(joint_names),
        "nominal_pd_torque_estimate": nominal_pd,
        "clipped_command_torque_estimate": clipped_command,
        "estimated_saturation": saturation,
        "effort_limit": effort_limit,
        "isaaclab_computed_torque_estimate": implicit_computed_torque,
        "isaaclab_applied_torque_estimate": implicit_applied_torque,
        "arm_joint_position_error_6d": arm_joint_position_error,
        "arm_joint_velocity_6d": arm_joint_velocity,
        "tracking_error_formula": "v21B: joint_pos_target - joint_pos",
        "tracking_error_source_fields": {
            "position_error": "joint_pos_target - joint_pos",
            "velocity": "joint_vel",
        },
        "authority_nominal_pd": V23_TORQUE_AUTHORITY_NOMINAL_PD,
        "authority_clipped_command": V23_TORQUE_AUTHORITY_CLIPPED_COMMAND,
        "isaaclab_torque_source_authority": V23_TORQUE_SOURCE_AUTHORITY,
        "valid_mask": valid_mask,
        **({"step_index": step_index} if step_index is not None else {}),
    }


def a2_v23_init_torque_accumulator(
    num_envs: int,
    num_joints: int,
    *,
    dtype: torch.dtype = torch.float32,
    device: torch.device | str = "cpu",
) -> dict[str, torch.Tensor]:
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs <= 0:
        raise ValueError("v23 torque accumulator num_envs must be positive.")
    if isinstance(num_joints, bool) or not isinstance(num_joints, int) or num_joints <= 0:
        raise ValueError("v23 torque accumulator num_joints must be positive.")
    dev = torch.device(device)
    zeros = torch.zeros((num_envs, num_joints), dtype=dtype, device=dev)
    return {
        "valid_frames": torch.zeros(num_envs, dtype=torch.long, device=dev),
        "nominal_pd_abs_sum": zeros.clone(),
        "nominal_pd_abs_max": zeros.clone(),
        "clipped_command_abs_max": zeros.clone(),
        "saturation_frames": torch.zeros((num_envs, num_joints), dtype=torch.long, device=dev),
        "implicit_computed_abs_max": zeros.clone(),
        "implicit_applied_abs_max": zeros.clone(),
        "position_error_abs_sum_6d": zeros.clone(),
        "position_error_abs_max_6d": zeros.clone(),
        "velocity_abs_sum_6d": zeros.clone(),
        "velocity_abs_max_6d": zeros.clone(),
        "last_nominal_pd": zeros.clone(),
        "last_clipped_command": zeros.clone(),
        "last_implicit_computed": zeros.clone(),
        "last_implicit_applied": zeros.clone(),
        "last_position_error_6d": zeros.clone(),
        "last_velocity_6d": zeros.clone(),
    }


def a2_v23_reset_torque_accumulator(state: Mapping[str, torch.Tensor], env_ids: torch.Tensor) -> None:
    if not isinstance(state, Mapping) or "valid_frames" not in state:
        raise ValueError("v23 torque accumulator is missing valid_frames.")
    num_envs = state["valid_frames"].shape[0]
    if (
        not torch.is_tensor(env_ids)
        or env_ids.ndim != 1
        or env_ids.dtype != torch.long
        or env_ids.device != state["valid_frames"].device
        or torch.any(env_ids < 0)
        or torch.any(env_ids >= num_envs)
    ):
        raise ValueError("v23 torque reset env_ids must be device-local long indices.")
    for value in state.values():
        value[env_ids] = 0


def a2_v23_accumulate_torque_step(state: Mapping[str, torch.Tensor], step: Mapping[str, Any]) -> None:
    if not isinstance(step, Mapping) or step.get("schema") != V23_TORQUE_SCHEMA:
        raise ValueError("v23 torque accumulator requires a v23 torque step schema.")
    nominal = step["nominal_pd_torque_estimate"]
    rows, dtype, device = _require_matrix(nominal, name="v23 nominal_pd_torque_estimate", columns=nominal.shape[1])
    if state["valid_frames"].shape[0] != rows or state["valid_frames"].device != device:
        raise ValueError("v23 torque accumulator and step rows/device do not match.")
    columns = nominal.shape[1]
    for key in (
        "clipped_command_torque_estimate",
        "effort_limit",
        "isaaclab_computed_torque_estimate",
        "isaaclab_applied_torque_estimate",
        "arm_joint_position_error_6d",
        "arm_joint_velocity_6d",
    ):
        _require_same_matrix(
            step[key],
            name=f"v23 {key}",
            rows=rows,
            columns=columns,
            dtype=dtype,
            device=device,
        )
    saturation = step["estimated_saturation"]
    valid_mask = step["valid_mask"]
    _require_env_mask(valid_mask, name="v23 step valid_mask", rows=rows, device=device)
    if (
        not torch.is_tensor(saturation)
        or tuple(saturation.shape) != (rows, columns)
        or saturation.dtype != torch.bool
        or saturation.device != device
    ):
        raise ValueError("v23 estimated_saturation requires bool shape (N,joints) on telemetry device.")
    active = valid_mask[:, None]
    nominal_abs = torch.abs(nominal)
    clipped_abs = torch.abs(step["clipped_command_torque_estimate"])
    computed_abs = torch.abs(step["isaaclab_computed_torque_estimate"])
    applied_abs = torch.abs(step["isaaclab_applied_torque_estimate"])
    position_error_abs = torch.abs(step["arm_joint_position_error_6d"])
    velocity_abs = torch.abs(step["arm_joint_velocity_6d"])
    state["valid_frames"] += valid_mask.to(torch.long)
    state["nominal_pd_abs_sum"] += torch.where(active, nominal_abs, torch.zeros_like(nominal_abs))
    state["nominal_pd_abs_max"] = torch.where(active, torch.maximum(state["nominal_pd_abs_max"], nominal_abs), state["nominal_pd_abs_max"])
    state["clipped_command_abs_max"] = torch.where(active, torch.maximum(state["clipped_command_abs_max"], clipped_abs), state["clipped_command_abs_max"])
    state["saturation_frames"] += (saturation & active).to(torch.long)
    state["implicit_computed_abs_max"] = torch.where(active, torch.maximum(state["implicit_computed_abs_max"], computed_abs), state["implicit_computed_abs_max"])
    state["implicit_applied_abs_max"] = torch.where(active, torch.maximum(state["implicit_applied_abs_max"], applied_abs), state["implicit_applied_abs_max"])
    state["position_error_abs_sum_6d"] += torch.where(active, position_error_abs, torch.zeros_like(position_error_abs))
    state["position_error_abs_max_6d"] = torch.where(active, torch.maximum(state["position_error_abs_max_6d"], position_error_abs), state["position_error_abs_max_6d"])
    state["velocity_abs_sum_6d"] += torch.where(active, velocity_abs, torch.zeros_like(velocity_abs))
    state["velocity_abs_max_6d"] = torch.where(active, torch.maximum(state["velocity_abs_max_6d"], velocity_abs), state["velocity_abs_max_6d"])
    state["last_nominal_pd"][valid_mask] = nominal[valid_mask]
    state["last_clipped_command"][valid_mask] = step["clipped_command_torque_estimate"][valid_mask]
    state["last_implicit_computed"][valid_mask] = step["isaaclab_computed_torque_estimate"][valid_mask]
    state["last_implicit_applied"][valid_mask] = step["isaaclab_applied_torque_estimate"][valid_mask]
    state["last_position_error_6d"][valid_mask] = step["arm_joint_position_error_6d"][valid_mask]
    state["last_velocity_6d"][valid_mask] = step["arm_joint_velocity_6d"][valid_mask]


def a2_v23_finalize_torque_episode(
    state: Mapping[str, torch.Tensor],
    env_id: int,
    *,
    joint_names: Sequence[str],
) -> dict[str, Any]:
    if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < state["valid_frames"].shape[0]:
        raise ValueError("v23 torque episode env_id is invalid.")
    columns = len(joint_names)
    if columns <= 0 or state["nominal_pd_abs_sum"].shape[1] != columns:
        raise ValueError("v23 torque episode joint_names do not match accumulator width.")
    count = int(state["valid_frames"][env_id].item())
    denominator = max(count, 1)
    no_valid: dict[str, Any] = {
        "status": "N/A",
        "reason": "NO_VALID_TORQUE_TELEMETRY",
        "denominator": 0,
    }
    mean = (
        (state["nominal_pd_abs_sum"][env_id] / denominator).detach().cpu().tolist()
        if count
        else no_valid
    )
    nominal_max = state["nominal_pd_abs_max"][env_id].detach().cpu().tolist() if count else no_valid
    clipped_max = state["clipped_command_abs_max"][env_id].detach().cpu().tolist() if count else no_valid
    saturation = (
        (state["saturation_frames"][env_id].to(dtype=state["nominal_pd_abs_sum"].dtype) / denominator)
        .detach()
        .cpu()
        .tolist()
        if count
        else no_valid
    )
    computed_max = state["implicit_computed_abs_max"][env_id].detach().cpu().tolist() if count else no_valid
    applied_max = state["implicit_applied_abs_max"][env_id].detach().cpu().tolist() if count else no_valid
    position_error_mean = (
        (state["position_error_abs_sum_6d"][env_id] / denominator).detach().cpu().tolist()
        if count
        else no_valid
    )
    position_error_max = state["position_error_abs_max_6d"][env_id].detach().cpu().tolist() if count else no_valid
    velocity_mean = (
        (state["velocity_abs_sum_6d"][env_id] / denominator).detach().cpu().tolist()
        if count
        else no_valid
    )
    velocity_max = state["velocity_abs_max_6d"][env_id].detach().cpu().tolist() if count else no_valid
    last_nominal = state["last_nominal_pd"][env_id].detach().cpu().tolist() if count else no_valid
    last_clipped = state["last_clipped_command"][env_id].detach().cpu().tolist() if count else no_valid
    last_computed = state["last_implicit_computed"][env_id].detach().cpu().tolist() if count else no_valid
    last_applied = state["last_implicit_applied"][env_id].detach().cpu().tolist() if count else no_valid
    last_position_error = state["last_position_error_6d"][env_id].detach().cpu().tolist() if count else no_valid
    last_velocity = state["last_velocity_6d"][env_id].detach().cpu().tolist() if count else no_valid
    return {
        "schema": V23_TORQUE_EPISODE_SCHEMA,
        "joint_names": list(joint_names),
        "valid_frame_count": count,
        "nominal_pd_torque_abs_mean": mean,
        "nominal_pd_torque_abs_max": nominal_max,
        "clipped_command_torque_abs_max": clipped_max,
        "estimated_saturation_fraction": saturation,
        "isaaclab_computed_torque_estimate_abs_max": computed_max,
        "isaaclab_applied_torque_estimate_abs_max": applied_max,
        "arm_joint_position_error_abs_mean_6d": position_error_mean,
        "arm_joint_position_error_abs_max_6d": position_error_max,
        "arm_joint_velocity_abs_mean_6d": velocity_mean,
        "arm_joint_velocity_abs_max_6d": velocity_max,
        "last_nominal_pd_torque_estimate": last_nominal,
        "last_clipped_command_torque_estimate": last_clipped,
        "last_isaaclab_computed_torque_estimate": last_computed,
        "last_isaaclab_applied_torque_estimate": last_applied,
        "last_arm_joint_position_error_6d": last_position_error,
        "last_arm_joint_velocity_6d": last_velocity,
        "tracking_error_formula": "v21B: joint_pos_target - joint_pos",
        "tracking_error_source_fields": {
            "position_error": "joint_pos_target - joint_pos",
            "velocity": "joint_vel",
        },
        "authority_nominal_pd": V23_TORQUE_AUTHORITY_NOMINAL_PD,
        "authority_clipped_command": V23_TORQUE_AUTHORITY_CLIPPED_COMMAND,
        "isaaclab_torque_source_authority": V23_TORQUE_SOURCE_AUTHORITY,
    }
