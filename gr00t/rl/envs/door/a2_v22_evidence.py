"""Pure v22 posture / clearance / hinge-routing evidence contracts.

Every helper is device-local and strict: malformed shape, dtype, device, or
non-finite telemetry raises at the boundary instead of being repaired.  The
module never invents a value — a quantity that has not been measured on the
host is a required input, not a defaulted one.

Two prohibitions from the plan are structural here:

* commanded posture and achieved posture are distinct arguments with distinct
  names and are never interchangeable (plan §7.1, negative test 2);
* a hinge bucket is derived from runtime drive values, never from a scenario
  label (plan §5A.5, negative test 22).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real

import torch


V22_EVIDENCE_SCHEMA = "a2_piper_base_v22_evidence_v1"
V22_STEP_TRACE_SCHEMA = "a2_piper_base_v22_step_trace_v1"
V22_POSTURE_BASELINE_SCHEMA = "a2_piper_base_v22_posture_baseline_v1"

# a2_base high-level base command layout is [x, y, yaw, pitch, roll]
# (gr00t/rl/envs/base_task/a2_base.py, a2_base_command == 5).
V22_COMMAND_PITCH_INDEX = 3
V22_COMMAND_ROLL_INDEX = 4
# self.rpy is [roll, pitch, yaw]; the achieved-side ordering is deliberately the
# reverse of the command-side ordering and must never be assumed symmetric.
V22_ACHIEVED_ROLL_INDEX = 0
V22_ACHIEVED_PITCH_INDEX = 1

V22_CLEARANCE_NONE = 0
V22_CLEARANCE_FLING = 1
V22_CLEARANCE_HAND_HOLD = 2
V22_CLEARANCE_BODY_HOLD = 3
V22_CLEARANCE_UNSAFE = 4
V22_CLEARANCE_STRATEGY_NAMES = {
    V22_CLEARANCE_NONE: "NO_CLEARANCE_EVENT",
    V22_CLEARANCE_FLING: "FLING_CLEARANCE",
    V22_CLEARANCE_HAND_HOLD: "HAND_HOLD_CLEARANCE",
    V22_CLEARANCE_BODY_HOLD: "BODY_HOLD_CLEARANCE",
    V22_CLEARANCE_UNSAFE: "UNSAFE_RELEASE",
}

V22_FREE_RETURN_CLASSES = (
    "CORE",
    "HIGH_DAMPING",
    "FAST_REBOUND",
    "HIGH_RESISTIVE",
    "COMPOUND",
    "UNCLASSIFIED",
)
V22_HINGE_BUCKETS = ("H0", "H1", "H2", "H3", "H4")

# Plan-registered constants (plan §7.3, §7.4, §8.3, §8.4, §8.5, §9.2).  These are
# the pre-registered numbers of revision 3, not tolerant defaults.
V22_NEED_ON_THRESHOLD = 0.70
V22_NEED_ON_STEPS = 5
V22_NEED_OFF_THRESHOLD = 0.35
V22_NEED_OFF_STEPS = 10
V22_WORKSPACE_MARGIN_THRESHOLD = 0.15
"""Revision-3 pre-registered workspace margin.  Superseded per run by the measured
P0-C lower tail; kept here as the documented pre-registered value."""
V22_FORCE_NEED_HINGE_VEL = 0.03
V22_FORCE_NEED_EFFORT_UTILIZATION = 0.85
V22_FORCE_NEED_STEPS = 10
V22_TRACKING_NEED_HINGE_VEL = 0.05
V22_TRACKING_NEED_STEPS = 10
V22_POSTURE_DEADBAND_PITCH = 0.05
V22_POSTURE_DEADBAND_ROLL = 0.04
V22_POSTURE_SOFT_PITCH = 0.30
V22_POSTURE_SOFT_ROLL = 0.20
V22_POSTURE_HUBER_DELTA = 0.10
V22_NOMINAL_PITCH_ABS_MAX = 0.15
V22_NOMINAL_ROLL_ABS_MAX = 0.10
V22_FLING_MIN_RELEASE_HINGE = 1.45
V22_CLEARANCE_MIN_HINGE = 1.10
V22_RELEASE_VELOCITY_GLOBAL_SOFT_MAX = 0.75
V22_ARM_FAILURE_HINGE_VEL = 0.03
V22_ARM_FAILURE_EFFORT_UTILIZATION = 0.90
V22_ARM_FAILURE_JOINT_MARGIN = 0.10
V22_ARM_FAILURE_STEPS = 15
V22_POSTURE_ATTEMPT_STEPS = 10

# Response-conditioned controlled-fling velocity bands (plan §8.5).
V22_FLING_BANDS = {
    "CORE": (0.10, 0.40),
    "FAST_REBOUND": (0.20, 0.55),
    "HIGH_DAMPING": (0.0, 0.55),
    "HIGH_RESISTIVE": (0.0, 0.55),
    "COMPOUND": (0.0, 0.55),
    "UNCLASSIFIED": (0.0, 0.55),
}


def _require_vector(value: torch.Tensor, *, name: str, n: int, dtype: torch.dtype | None = None) -> None:
    if not torch.is_tensor(value) or tuple(value.shape) != (n,):
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"v22 {name} requires shape ({n},); got {shape}.")
    if dtype is not None and value.dtype != dtype:
        raise ValueError(f"v22 {name} requires dtype {dtype}; got {value.dtype}.")
    if value.is_floating_point() and not torch.all(torch.isfinite(value)):
        raise ValueError(f"v22 {name} contains non-finite values.")


def v22_require_float_vector(value: torch.Tensor, *, name: str, n: int) -> torch.Tensor:
    if not torch.is_tensor(value) or tuple(value.shape) != (n,) or not value.is_floating_point():
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"v22 {name} requires a floating tensor shape ({n},); got {shape}.")
    if not torch.all(torch.isfinite(value)):
        raise ValueError(f"v22 {name} contains non-finite values.")
    return value


def v22_require_bool_vector(value: torch.Tensor, *, name: str, n: int) -> torch.Tensor:
    _require_vector(value, name=name, n=n, dtype=torch.bool)
    return value


def v22_validate_height_nominal_table(table: Mapping) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Validate the P0-C height-conditioned nominal posture table."""
    if not isinstance(table, Mapping):
        raise ValueError("v22 height-nominal table must be a mapping with heights/pitch/roll")
    return v22_validate_height_nominal_series(
        table.get("heights"), table.get("pitch"), table.get("roll")
    )


def v22_validate_height_nominal_series(
    heights, pitch, roll
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Validate the three P0-C nominal-posture series supplied as separate keys."""
    for label, series in (("heights", heights), ("pitch", pitch), ("roll", roll)):
        if isinstance(series, (str, bytes)) or not isinstance(series, Sequence) or len(series) < 2:
            raise ValueError(f"v22 height-nominal table {label} must be a sequence with >=2 entries")
        if any(isinstance(item, bool) or not isinstance(item, Real) or not math.isfinite(float(item)) for item in series):
            raise ValueError(f"v22 height-nominal table {label} must contain finite real numbers")
    if not (len(heights) == len(pitch) == len(roll)):
        raise ValueError("v22 height-nominal table series must have equal length")
    heights_t = tuple(float(item) for item in heights)
    if any(heights_t[i] >= heights_t[i + 1] for i in range(len(heights_t) - 1)):
        raise ValueError("v22 height-nominal table heights must be strictly increasing")
    pitch_t = tuple(float(item) for item in pitch)
    roll_t = tuple(float(item) for item in roll)
    if any(abs(item) > V22_NOMINAL_PITCH_ABS_MAX + 1e-9 for item in pitch_t):
        raise ValueError(f"v22 nominal pitch exceeds the frozen |pitch| <= {V22_NOMINAL_PITCH_ABS_MAX} bound")
    if any(abs(item) > V22_NOMINAL_ROLL_ABS_MAX + 1e-9 for item in roll_t):
        raise ValueError(f"v22 nominal roll exceeds the frozen |roll| <= {V22_NOMINAL_ROLL_ABS_MAX} bound")
    return heights_t, pitch_t, roll_t


def v22_height_nominal_posture(
    handle_height: torch.Tensor,
    heights: torch.Tensor,
    nominal_pitch: torch.Tensor,
    nominal_roll: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Piecewise-linear height-conditioned nominal posture, clamped at the table ends."""
    n = handle_height.shape[0]
    v22_require_float_vector(handle_height, name="handle_height", n=n)
    knots = heights.shape[0]
    for label, series in (("nominal_pitch", nominal_pitch), ("nominal_roll", nominal_roll)):
        v22_require_float_vector(series, name=label, n=knots)
    v22_require_float_vector(heights, name="nominal_heights", n=knots)
    clamped = torch.clamp(handle_height, heights[0], heights[-1])
    upper = torch.clamp(torch.searchsorted(heights, clamped, right=True), 1, knots - 1)
    lower = upper - 1
    span = heights[upper] - heights[lower]
    alpha = (clamped - heights[lower]) / span
    pitch = nominal_pitch[lower] + alpha * (nominal_pitch[upper] - nominal_pitch[lower])
    roll = nominal_roll[lower] + alpha * (nominal_roll[upper] - nominal_roll[lower])
    return pitch, roll


def v22_posture_need_components(
    *,
    nominal_pitch: torch.Tensor,
    nominal_roll: torch.Tensor,
    joint_position_margin: torch.Tensor,
    workspace_margin_threshold: float,
    directional_wrench: torch.Tensor,
    directional_wrench_threshold: float,
    valid_hold: torch.Tensor,
    hinge_velocity: torch.Tensor,
    effort_utilization: torch.Tensor,
    arm_tracking_error: torch.Tensor,
    arm_tracking_error_p90: float,
    force_need_streak: torch.Tensor,
    tracking_need_streak: torch.Tensor,
) -> dict[str, torch.Tensor]:
    """Compute the four v22 posture-need components (plan §7.3).

    ``force_need_streak`` / ``tracking_need_streak`` are updated in place by the
    caller from the returned per-step condition masks.
    """
    n = nominal_pitch.shape[0]
    for label, value in (
        ("nominal_pitch", nominal_pitch),
        ("nominal_roll", nominal_roll),
        ("joint_position_margin", joint_position_margin),
        ("directional_wrench", directional_wrench),
        ("hinge_velocity", hinge_velocity),
        ("effort_utilization", effort_utilization),
        ("arm_tracking_error", arm_tracking_error),
    ):
        v22_require_float_vector(value, name=label, n=n)
    v22_require_bool_vector(valid_hold, name="valid_hold", n=n)
    for label, value in (("force_need_streak", force_need_streak), ("tracking_need_streak", tracking_need_streak)):
        _require_vector(value, name=label, n=n, dtype=torch.long)
    for label, value in (
        ("directional_wrench_threshold", directional_wrench_threshold),
        ("arm_tracking_error_p90", arm_tracking_error_p90),
        ("workspace_margin_threshold", workspace_margin_threshold),
    ):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"v22 {label} must be a finite positive measured value; got {value!r}")

    height_need = (nominal_pitch.abs() > 0.0) | (nominal_roll.abs() > 0.0)
    workspace_need = (joint_position_margin < float(workspace_margin_threshold)) | (
        directional_wrench < float(directional_wrench_threshold)
    )
    force_condition = (
        valid_hold
        & (hinge_velocity < V22_FORCE_NEED_HINGE_VEL)
        & (effort_utilization > V22_FORCE_NEED_EFFORT_UTILIZATION)
    )
    tracking_condition = (
        valid_hold
        & (arm_tracking_error > float(arm_tracking_error_p90))
        & (hinge_velocity < V22_TRACKING_NEED_HINGE_VEL)
    )
    force_need_streak.copy_(torch.where(force_condition, force_need_streak + 1, torch.zeros_like(force_need_streak)))
    tracking_need_streak.copy_(
        torch.where(tracking_condition, tracking_need_streak + 1, torch.zeros_like(tracking_need_streak))
    )
    force_need = force_need_streak >= V22_FORCE_NEED_STEPS
    tracking_need = tracking_need_streak >= V22_TRACKING_NEED_STEPS
    return {
        "height_need": height_need,
        "workspace_need": workspace_need,
        "force_need": force_need,
        "tracking_need": tracking_need,
    }


def v22_posture_need_score(components: Mapping[str, torch.Tensor]) -> torch.Tensor:
    """posture_need = max(height, workspace, force, tracking) (plan §7.3)."""
    keys = ("height_need", "workspace_need", "force_need", "tracking_need")
    if set(components) != set(keys):
        raise ValueError(f"v22 posture-need components must be exactly {keys}; got {sorted(components)}")
    stacked = torch.stack([components[key].to(torch.float32) for key in keys], dim=0)
    return stacked.amax(dim=0)


def v22_apply_need_hysteresis(
    score: torch.Tensor,
    active: torch.Tensor,
    on_streak: torch.Tensor,
    off_streak: torch.Tensor,
) -> torch.Tensor:
    """Latch posture-need with the frozen ON/OFF hysteresis (plan §7.3)."""
    n = score.shape[0]
    v22_require_float_vector(score, name="posture_need_score", n=n)
    v22_require_bool_vector(active, name="posture_need_active", n=n)
    for label, value in (("on_streak", on_streak), ("off_streak", off_streak)):
        _require_vector(value, name=label, n=n, dtype=torch.long)
    above = score >= V22_NEED_ON_THRESHOLD
    below = score <= V22_NEED_OFF_THRESHOLD
    on_streak.copy_(torch.where(above, on_streak + 1, torch.zeros_like(on_streak)))
    off_streak.copy_(torch.where(below, off_streak + 1, torch.zeros_like(off_streak)))
    turn_on = (~active) & (on_streak >= V22_NEED_ON_STEPS)
    turn_off = active & (off_streak >= V22_NEED_OFF_STEPS)
    active.copy_((active | turn_on) & ~turn_off)
    return active


def v22_huber(error: torch.Tensor, delta: float) -> torch.Tensor:
    if isinstance(delta, bool) or not isinstance(delta, Real) or not math.isfinite(float(delta)) or float(delta) <= 0.0:
        raise ValueError(f"v22 huber delta must be finite and positive; got {delta!r}")
    magnitude = error.abs()
    quadratic = torch.clamp(magnitude, max=float(delta))
    return 0.5 * quadratic * quadratic + float(delta) * (magnitude - quadratic)


def v22_deadband(error: torch.Tensor, width: float) -> torch.Tensor:
    if isinstance(width, bool) or not isinstance(width, Real) or not math.isfinite(float(width)) or float(width) < 0.0:
        raise ValueError(f"v22 deadband width must be finite and non-negative; got {width!r}")
    return torch.sign(error) * torch.clamp(error.abs() - float(width), min=0.0)


def v22_excess_posture_penalty(
    *,
    command_pitch: torch.Tensor,
    command_roll: torch.Tensor,
    nominal_pitch: torch.Tensor,
    nominal_roll: torch.Tensor,
    posture_need: torch.Tensor,
) -> torch.Tensor:
    """-(1 - posture_need) * Huber(command - height_nominal) with frozen deadbands."""
    n = command_pitch.shape[0]
    for label, value in (
        ("command_pitch", command_pitch),
        ("command_roll", command_roll),
        ("nominal_pitch", nominal_pitch),
        ("nominal_roll", nominal_roll),
        ("posture_need", posture_need),
    ):
        v22_require_float_vector(value, name=label, n=n)
    pitch_error = v22_deadband(command_pitch - nominal_pitch, V22_POSTURE_DEADBAND_PITCH)
    roll_error = v22_deadband(command_roll - nominal_roll, V22_POSTURE_DEADBAND_ROLL)
    excess = v22_huber(pitch_error, V22_POSTURE_HUBER_DELTA) + v22_huber(roll_error, V22_POSTURE_HUBER_DELTA)
    return (1.0 - posture_need) * excess


def v22_saturation_penalty(command_pitch: torch.Tensor, command_roll: torch.Tensor) -> torch.Tensor:
    """Continuous penalty outside the soft posture boundaries (plan §7.4)."""
    n = command_pitch.shape[0]
    v22_require_float_vector(command_pitch, name="command_pitch", n=n)
    v22_require_float_vector(command_roll, name="command_roll", n=n)
    pitch_excess = torch.clamp(command_pitch.abs() - V22_POSTURE_SOFT_PITCH, min=0.0)
    roll_excess = torch.clamp(command_roll.abs() - V22_POSTURE_SOFT_ROLL, min=0.0)
    return pitch_excess * pitch_excess + roll_excess * roll_excess


def v22_posture_feasibility_reward(
    *,
    posture_need: torch.Tensor,
    valid_hold: torch.Tensor,
    hinge_velocity: torch.Tensor,
    arm_margin_quality: torch.Tensor,
    arc_tracking_quality: torch.Tensor,
) -> torch.Tensor:
    """Reward the result of posture use, never posture magnitude (plan §7.4)."""
    n = posture_need.shape[0]
    for label, value in (
        ("posture_need", posture_need),
        ("hinge_velocity", hinge_velocity),
        ("arm_margin_quality", arm_margin_quality),
        ("arc_tracking_quality", arc_tracking_quality),
    ):
        v22_require_float_vector(value, name=label, n=n)
    v22_require_bool_vector(valid_hold, name="valid_hold", n=n)
    positive_progress = torch.clamp(hinge_velocity, min=0.0) > 0.0
    return (
        posture_need
        * (valid_hold & positive_progress).to(posture_need.dtype)
        * torch.clamp(arm_margin_quality, 0.0, 1.0)
        * torch.clamp(arc_tracking_quality, 0.0, 1.0)
    )


def v22_arm_margin_quality(joint_position_margin: torch.Tensor, effort_utilization: torch.Tensor) -> torch.Tensor:
    """Normalized arm-headroom quality in [0, 1] from margin and effort utilization."""
    n = joint_position_margin.shape[0]
    v22_require_float_vector(joint_position_margin, name="joint_position_margin", n=n)
    v22_require_float_vector(effort_utilization, name="effort_utilization", n=n)
    margin_quality = torch.clamp(joint_position_margin / V22_WORKSPACE_MARGIN_THRESHOLD, 0.0, 1.0)
    effort_quality = torch.clamp(1.0 - effort_utilization, 0.0, 1.0)
    return margin_quality * effort_quality


def v22_fling_band(free_return_class: str) -> tuple[float, float]:
    if free_return_class not in V22_FLING_BANDS:
        raise ValueError(f"v22 free-return class {free_return_class!r} is not registered")
    return V22_FLING_BANDS[free_return_class]


def v22_fling_band_tensors(
    free_return_class_index: torch.Tensor, device: torch.device, dtype: torch.dtype
) -> tuple[torch.Tensor, torch.Tensor]:
    """Map a per-env measured free-return class index onto its release-velocity band."""
    _require_vector(free_return_class_index, name="free_return_class_index", n=free_return_class_index.shape[0], dtype=torch.long)
    if torch.any(free_return_class_index < 0) or torch.any(free_return_class_index >= len(V22_FREE_RETURN_CLASSES)):
        raise ValueError("v22 free-return class index is outside the registered class table")
    low = torch.tensor(
        [V22_FLING_BANDS[name][0] for name in V22_FREE_RETURN_CLASSES], device=device, dtype=dtype
    )
    high = torch.tensor(
        [V22_FLING_BANDS[name][1] for name in V22_FREE_RETURN_CLASSES], device=device, dtype=dtype
    )
    return low[free_return_class_index], high[free_return_class_index]


def v22_validate_bucket_table(table: Sequence[Mapping]) -> tuple[dict, ...]:
    """Validate the frozen H0-H4 runtime-value table used to label records."""
    if isinstance(table, (str, bytes)) or not isinstance(table, Sequence) or not table:
        raise ValueError("v22 bucket table must be a non-empty sequence")
    validated = []
    seen = set()
    for index, entry in enumerate(table):
        if not isinstance(entry, Mapping):
            raise ValueError(f"v22 bucket table entry {index} must be a mapping")
        name = entry.get("bucket")
        if name not in V22_HINGE_BUCKETS:
            raise ValueError(f"v22 bucket table entry {index} bucket {name!r} is not registered")
        if name in seen:
            raise ValueError(f"v22 bucket table repeats {name!r}")
        seen.add(name)
        bounds = {}
        for field in ("damping", "stiffness", "max_force_nm"):
            pair = entry.get(field)
            if isinstance(pair, (str, bytes)) or not isinstance(pair, Sequence) or len(pair) != 2:
                raise ValueError(f"v22 bucket table entry {index} field {field} must be a two-bound sequence")
            low, high = (float(item) for item in pair)
            if not math.isfinite(low) or not math.isfinite(high) or low > high:
                raise ValueError(f"v22 bucket table entry {index} field {field} bounds are invalid")
            bounds[field] = (low, high)
        validated.append({"bucket": name, **bounds})
    return tuple(validated)


def v22_bucket_index_from_runtime(
    damping: torch.Tensor,
    stiffness: torch.Tensor,
    max_force: torch.Tensor,
    bucket_table: Sequence[Mapping],
) -> torch.Tensor:
    """Label every environment from its actual runtime hinge-drive values.

    A record that matches no registered bucket gets ``-1``; the caller decides
    whether that is an evidence failure for its node.  Membership is never
    derived from a scenario name (plan §5A.5).
    """
    n = damping.shape[0]
    for label, value in (("damping", damping), ("stiffness", stiffness), ("max_force", max_force)):
        v22_require_float_vector(value, name=f"hinge_{label}", n=n)
    table = v22_validate_bucket_table(bucket_table)
    index = torch.full((n,), -1, dtype=torch.long, device=damping.device)
    for position, entry in enumerate(table):
        match = (
            (damping >= entry["damping"][0])
            & (damping <= entry["damping"][1])
            & (stiffness >= entry["stiffness"][0])
            & (stiffness <= entry["stiffness"][1])
            & (max_force >= entry["max_force_nm"][0])
            & (max_force <= entry["max_force_nm"][1])
        )
        index = torch.where(match & (index < 0), torch.full_like(index, position), index)
    return index


def v22_classify_free_return(
    *,
    half_time_s: float,
    peak_closing_velocity_radps: float,
    stayed_force_capped: bool,
    fixed_torque_progress_rad: Mapping[str, float],
    core_half_time_s: float,
    core_peak_closing_velocity_radps: float,
    core_progress_rad: float,
) -> str:
    """Classify a measured hinge tuple from response, never from parameters (§6.3)."""
    for label, value in (
        ("half_time_s", half_time_s),
        ("peak_closing_velocity_radps", peak_closing_velocity_radps),
        ("core_half_time_s", core_half_time_s),
        ("core_peak_closing_velocity_radps", core_peak_closing_velocity_radps),
        ("core_progress_rad", core_progress_rad),
    ):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
            raise ValueError(f"v22 free-return classification requires a finite {label}; got {value!r}")
    if not isinstance(fixed_torque_progress_rad, Mapping) or not fixed_torque_progress_rad:
        raise ValueError("v22 free-return classification requires fixed-torque progress samples")
    highest_torque = max(fixed_torque_progress_rad, key=lambda key: float(key))
    progress = float(fixed_torque_progress_rad[highest_torque])
    if not math.isfinite(progress):
        raise ValueError("v22 fixed-torque progress must be finite")

    slow_return = half_time_s > 1.5 * core_half_time_s
    fast_return = (
        half_time_s < 0.7 * core_half_time_s
        and peak_closing_velocity_radps > 1.3 * core_peak_closing_velocity_radps
    )
    resistive = progress < 0.7 * core_progress_rad

    if slow_return and resistive:
        return "COMPOUND"
    if fast_return and resistive:
        return "COMPOUND"
    if slow_return:
        return "HIGH_DAMPING"
    if fast_return:
        return "FAST_REBOUND"
    if resistive:
        return "HIGH_RESISTIVE"
    if stayed_force_capped and progress < 0.85 * core_progress_rad:
        return "HIGH_RESISTIVE"
    if (
        0.7 * core_half_time_s <= half_time_s <= 1.5 * core_half_time_s
        and progress >= 0.7 * core_progress_rad
    ):
        return "CORE"
    return "UNCLASSIFIED"


__all__ = [
    "V22_EVIDENCE_SCHEMA",
    "V22_STEP_TRACE_SCHEMA",
    "V22_POSTURE_BASELINE_SCHEMA",
    "V22_COMMAND_PITCH_INDEX",
    "V22_COMMAND_ROLL_INDEX",
    "V22_ACHIEVED_ROLL_INDEX",
    "V22_ACHIEVED_PITCH_INDEX",
    "V22_CLEARANCE_NONE",
    "V22_CLEARANCE_FLING",
    "V22_CLEARANCE_HAND_HOLD",
    "V22_CLEARANCE_BODY_HOLD",
    "V22_CLEARANCE_UNSAFE",
    "V22_CLEARANCE_STRATEGY_NAMES",
    "V22_FREE_RETURN_CLASSES",
    "V22_HINGE_BUCKETS",
    "V22_FLING_BANDS",
    "V22_FLING_MIN_RELEASE_HINGE",
    "V22_CLEARANCE_MIN_HINGE",
    "V22_RELEASE_VELOCITY_GLOBAL_SOFT_MAX",
    "V22_ARM_FAILURE_HINGE_VEL",
    "V22_ARM_FAILURE_EFFORT_UTILIZATION",
    "V22_ARM_FAILURE_JOINT_MARGIN",
    "V22_ARM_FAILURE_STEPS",
    "V22_POSTURE_ATTEMPT_STEPS",
    "V22_NEED_OFF_THRESHOLD",
    "v22_apply_need_hysteresis",
    "v22_arm_margin_quality",
    "v22_bucket_index_from_runtime",
    "v22_classify_free_return",
    "v22_deadband",
    "v22_excess_posture_penalty",
    "v22_fling_band",
    "v22_fling_band_tensors",
    "v22_height_nominal_posture",
    "v22_huber",
    "v22_posture_feasibility_reward",
    "v22_posture_need_components",
    "v22_posture_need_score",
    "v22_require_bool_vector",
    "v22_require_float_vector",
    "v22_saturation_penalty",
    "v22_validate_bucket_table",
    "v22_validate_height_nominal_table",
    "v22_validate_height_nominal_series",
]
