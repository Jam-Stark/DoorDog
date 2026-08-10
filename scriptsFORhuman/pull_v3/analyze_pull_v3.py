#!/usr/bin/env python3
"""Fail-closed pull-v3 checkpoint analysis and D0-lite acceptance checker."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
V3_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "logs_eval/a2_piper_pull_v3"
DEFAULT_OUTPUT = V3_DIR / "PULL_V3_ANALYSIS.json"
STEPS = (250, 500, 750)
V2_BASELINE = {
    "label": "v2 Wave2 seed1 step750",
    "seed": 1,
    "step": 750,
    "episode_count": 16,
    "events": {
        "E0_RESET_VALID": "16/16",
        "E1_OUTSIDE_FACE_PREGRASP": "16/16",
        "E2_TENSILE_CAPTURE": "16/16",
        "E3_LATCH_RELEASE": "16/16",
        "E4_POSITIVE_HINGE_RETAINED": "16/16",
        "E5_CLEARANCE_DECISION": "16/16",
        "E6_PATH_REVERSAL_ENTRY": "0/16",
        "E7_WHOLE_BODY_CLEAR": "0/16",
    },
    "terminal_episode_length_steps": 654,
    "true_stage3_to4": {"seed0": [13, 14, 15], "seed1": [11, 16, 16]},
    "panel_contact_steps_median": 0,
    "panel_contact_steps_max": 21,
    "integrity_invariants": {"all_zero": True},
}
EVENT_NAMES = (
    "E0_RESET_VALID",
    "E1_OUTSIDE_FACE_PREGRASP",
    "E2_TENSILE_CAPTURE",
    "E3_LATCH_RELEASE",
    "E4_POSITIVE_HINGE_RETAINED",
    "E5_CLEARANCE_DECISION",
    "E6_PATH_REVERSAL_ENTRY",
    "E7_WHOLE_BODY_CLEAR",
)
APERTURE_READY_EVENTS = frozenset(EVENT_NAMES[5:])
TRACE_PULL_REQUIRED = (
    "stage",
    "event_state",
    "root_x_rel_door_m",
    "handle_position_rad",
    "latch_position_m",
    "hinge_position_rad",
    "target_tcp_position_error_m",
    "gripper_handle_separation_m",
    "handle_local_slip_xyz_mps",
    "finger_effort_utilization_estimate",
    "arm_pd_effort_utilization_estimate",
    "reward_component_raw",
)
TRACE_REWARD_REQUIRED = ("dont_push_door_handle", "target_root_distance")
V3_TERMINAL_BOOL_FIELDS = (
    "frame_passage",
    "planar_crossing",
    "detour",
    "deliberate_release",
    "frame_approach",
    "complete_without_frame_passage",
)
V3_TERMINAL_STEP_FIELDS = (
    "frame_passage_step",
    "deliberate_release_step",
    "first_negative_x_motion_step",
    "e5_to_e7_steps",
)
V3_TERMINAL_FINITE_FIELDS = (
    "swept_arc_clearance_margin_min_m",
    "base_path_length_m",
)
V3_TERMINAL_INT_FIELDS = (
    "base_reversal_count",
    "post_release_recontact_count",
    "corridor_door_wide_pre_aperture_steps",
    "corridor_clean_passage_pre_aperture_steps",
)
FORMAL_INVARIANT_KEYS = (
    "fake_e4",
    "stage4_snapshot_below_hinge_gate",
    "dont_push_before_true_stage3_to4",
    "target_root_before_aperture_ready",
    "corridor_active_before_aperture_ready",
    "complete_without_frame_passage",
)

# The writer emits the simple field name and, for control-step state, may add
# an explicit ``_current``/``_latched`` suffix.  Each semantic value still has
# one required canonical value; a missing semantic field is a hard failure.
TRACE_BOOL_ALIASES = {
    "aperture_ready_current": ("aperture_ready_current",),
    "aperture_ready_latched": ("aperture_ready",),
    "frame_approach_current": ("frame_approach_current",),
    "frame_approach_latched": ("frame_approach",),
    "frame_passage_current": ("frame_passage_current",),
    "frame_passage_latched": ("frame_passage",),
    "planar_crossing_current": ("planar_crossing_current",),
    "planar_crossing_latched": ("planar_crossing",),
    "detour_current": ("detour_current",),
    "detour_latched": ("detour",),
    "deliberate_release_current": ("deliberate_release_current",),
    "deliberate_release_latched": ("deliberate_release",),
    "panel_contact_current": ("bilateral_handle_contact",),
    "panel_clear": ("panel_clear",),
}
TRACE_FINITE_ALIASES = {
    "minimum_clearance_margin_m": ("minimum_clearance_margin_m",),
    "swept_arc_clearance_margin_current_m": (
        "swept_arc_clearance_margin_current_m",
        "swept_arc_clearance_margin_m",
        "minimum_clearance_m",
    ),
    "swept_arc_clearance_margin_min_m": ("swept_arc_clearance_margin_min_m",),
    "base_path_length_m": ("base_path_length_m",),
    "corridor_door_wide_raw": ("corridor_door_wide_raw",),
    "corridor_clean_passage_raw": ("corridor_clean_passage_raw",),
}
TRACE_INT_ALIASES = {
    "base_reversal_count": ("base_reversal_count",),
    "post_release_recontact_count": ("post_release_recontact_count",),
    "corridor_door_wide_pre_aperture_steps": (
        "corridor_door_wide_pre_aperture_steps",
    ),
    "corridor_clean_passage_pre_aperture_steps": (
        "corridor_clean_passage_pre_aperture_steps",
    ),
}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object; got {type(value).__name__}")
    return value


def _require_finite(mapping: Mapping[str, Any], key: str, label: str) -> float:
    value = _finite(mapping.get(key))
    if value is None:
        raise ValueError(f"{label}.{key} must be a finite number; got {mapping.get(key)!r}")
    return value


def _require_bool(mapping: Mapping[str, Any], key: str, label: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{label}.{key} must be bool; got {value!r}")
    return value


def _require_nonnegative_int(mapping: Mapping[str, Any], key: str, label: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label}.{key} must be a non-negative int; got {value!r}")
    return value


def _step_or_na(mapping: Mapping[str, Any], key: str, label: str) -> int | None:
    value = mapping.get(key)
    if value in ("N/A", "NA", None):
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label}.{key} must be a non-negative int or N/A; got {value!r}")
    return value


def _alias_value(mapping: Mapping[str, Any], aliases: tuple[str, ...], label: str) -> Any:
    present = [key for key in aliases if key in mapping]
    if not present:
        raise ValueError(f"{label} is missing required field {aliases[0]!r}")
    if len(present) > 1:
        values = [mapping[key] for key in present]
        if any(value != values[0] for value in values[1:]):
            raise ValueError(f"{label} has conflicting aliases {present!r}")
    return mapping[present[0]]


def _validate_v3_terminal(record: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    v3 = _require_mapping(record.get("pull_v3_traversal"), f"{label}.pull_v3_traversal")
    for key in V3_TERMINAL_BOOL_FIELDS:
        _require_bool(v3, key, f"{label}.pull_v3_traversal")
    for key in V3_TERMINAL_STEP_FIELDS:
        _step_or_na(v3, key, f"{label}.pull_v3_traversal")
    for key in V3_TERMINAL_FINITE_FIELDS:
        value = _finite(v3.get(key))
        if value is None and key == "swept_arc_clearance_margin_min_m" and v3.get(key) is None:
            continue
        if value is None or (key == "base_path_length_m" and value < 0.0):
            raise ValueError(f"{label}.pull_v3_traversal.{key} must be finite and non-negative")
    for key in V3_TERMINAL_INT_FIELDS:
        _require_nonnegative_int(v3, key, f"{label}.pull_v3_traversal")
    return v3


def _validate_v3_trace_row(row: Any, index: int) -> Mapping[str, Any]:
    label = f"step trace row {index}"
    top = _require_mapping(row, label)
    env_id = top.get("env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0:
        raise ValueError(f"{label}.env_id must be a non-negative int; got {env_id!r}")
    step_index = top.get("step_index")
    if isinstance(step_index, bool) or not isinstance(step_index, int) or step_index < 0:
        raise ValueError(f"{label}.step_index must be a non-negative int; got {step_index!r}")
    episode_index = top.get("episode_index")
    if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
        raise ValueError(f"{label}.episode_index must be a non-negative int; got {episode_index!r}")
    threshold = _require_finite(top, "stage3_to4_door_hinge_threshold", label)
    if threshold <= 0.0:
        raise ValueError(f"{label}.stage3_to4_door_hinge_threshold must be positive")
    pull = _require_mapping(top.get("pull_v0"), f"{label}.pull_v0")
    for key in TRACE_PULL_REQUIRED:
        if key not in pull:
            raise ValueError(f"{label}.pull_v0 is missing required field {key!r}")
    stage = pull["stage"]
    if isinstance(stage, bool) or not isinstance(stage, int) or stage < 0:
        raise ValueError(f"{label}.pull_v0.stage must be a non-negative int; got {stage!r}")
    if pull["event_state"] not in EVENT_NAMES:
        raise ValueError(f"{label}.pull_v0.event_state is not a known event")
    for key in (
        "root_x_rel_door_m",
        "handle_position_rad",
        "latch_position_m",
        "hinge_position_rad",
        "target_tcp_position_error_m",
        "gripper_handle_separation_m",
    ):
        _require_finite(pull, key, f"{label}.pull_v0")
    slip = pull["handle_local_slip_xyz_mps"]
    if slip != "N/A" and (
        not isinstance(slip, list) or len(slip) != 3 or any(_finite(value) is None for value in slip)
    ):
        raise ValueError(f"{label}.pull_v0.handle_local_slip_xyz_mps must be finite 3-vector/N/A")
    for key in ("finger_effort_utilization_estimate", "arm_pd_effort_utilization_estimate"):
        estimate = _require_mapping(pull[key], f"{label}.pull_v0.{key}")
        values = estimate.get("value")
        if not isinstance(values, list) or not values or any(_finite(value) is None for value in values):
            raise ValueError(f"{label}.pull_v0.{key}.value must be a non-empty finite list")
        if not isinstance(estimate.get("provenance"), str) or not estimate["provenance"]:
            raise ValueError(f"{label}.pull_v0.{key}.provenance must be a non-empty string")
    rewards = _require_mapping(pull["reward_component_raw"], f"{label}.pull_v0.reward_component_raw")
    for key in TRACE_REWARD_REQUIRED:
        _require_finite(rewards, key, f"{label}.pull_v0.reward_component_raw")
    if "pull_v3_traversal" not in pull:
        raise ValueError(f"{label}.pull_v0 is missing required field 'pull_v3_traversal'")
    v3 = _require_mapping(
        pull["pull_v3_traversal"],
        f"{label}.pull_v0.pull_v3_traversal",
    )
    for key, aliases in TRACE_BOOL_ALIASES.items():
        value = _alias_value(v3, aliases, f"{label}.pull_v3_traversal.{key}")
        if not isinstance(value, bool):
            raise ValueError(f"{label}.pull_v3_traversal.{key} must be bool; got {value!r}")
    for key, aliases in TRACE_FINITE_ALIASES.items():
        value = _alias_value(v3, aliases, f"{label}.pull_v3_traversal.{key}")
        if value is None and key in {
            "minimum_clearance_margin_m",
            "swept_arc_clearance_margin_current_m",
            "swept_arc_clearance_margin_min_m",
        }:
            continue
        if _finite(value) is None:
            raise ValueError(f"{label}.pull_v3_traversal.{key} must be finite; got {value!r}")
    for key, aliases in TRACE_INT_ALIASES.items():
        value = _alias_value(v3, aliases, f"{label}.pull_v3_traversal.{key}")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{label}.pull_v3_traversal.{key} must be a non-negative int")
    for key in ("a2_corridor_door_wide", "a2_corridor_clean_passage"):
        if key not in rewards:
            raise ValueError(f"{label}.pull_v0.reward_component_raw is missing {key!r}")
        _require_finite(rewards, key, f"{label}.pull_v0.reward_component_raw")
    normalized = dict(top)
    normalized_v3 = dict(v3)
    for key, aliases in TRACE_BOOL_ALIASES.items():
        normalized_v3[key] = _alias_value(v3, aliases, f"{label}.pull_v3_traversal.{key}")
    for key, aliases in TRACE_FINITE_ALIASES.items():
        normalized_v3[key] = _alias_value(v3, aliases, f"{label}.pull_v3_traversal.{key}")
    for key, aliases in TRACE_INT_ALIASES.items():
        normalized_v3[key] = _alias_value(v3, aliases, f"{label}.pull_v3_traversal.{key}")
    normalized["pull_v3_traversal"] = normalized_v3
    return normalized


def _validate_trace_coverage(
    terminals: list[Mapping[str, Any]],
    trace_rows: list[Mapping[str, Any]],
) -> None:
    terminal_env_ids: list[int] = []
    terminal_stage_by_env: dict[int, int] = {}
    for index, terminal in enumerate(terminals):
        env_id = terminal.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0:
            raise ValueError(f"terminal episode record {index}.env_id must be a non-negative int")
        stage_buf = terminal.get("stage_buf")
        if isinstance(stage_buf, bool) or not isinstance(stage_buf, int) or stage_buf < 0:
            raise ValueError(
                f"terminal episode record {index}.stage_buf must be a non-negative int"
            )
        terminal_env_ids.append(env_id)
        terminal_stage_by_env[env_id] = stage_buf
    if len(terminal_env_ids) != 16 or len(set(terminal_env_ids)) != 16:
        raise ValueError(
            "trace coverage requires exactly 16 distinct terminal episode env_id values; "
            f"got {terminal_env_ids!r}"
        )
    trace_identity_by_env: dict[int, set[int]] = {}
    for row in trace_rows:
        env_id = row["env_id"]
        episode_index = row["episode_index"]
        trace_identity_by_env.setdefault(env_id, set()).add(episode_index)
    terminal_ids = {
        env_id
        for env_id, stage_buf in terminal_stage_by_env.items()
        if stage_buf in {2, 3, 4, 5}
    }
    trace_ids = set(trace_identity_by_env)
    if trace_ids != terminal_ids:
        raise ValueError(
            "trace coverage must match expected stage2-5 terminal episode env_id values; "
            f"missing={sorted(terminal_ids - trace_ids)}, unexpected={sorted(trace_ids - terminal_ids)}"
        )
    multi_episode_envs = {
        env_id: sorted(episode_indices)
        for env_id, episode_indices in trace_identity_by_env.items()
        if len(episode_indices) != 1
    }
    if multi_episode_envs:
        raise ValueError(
            "trace coverage must contain exactly one producer episode identity per terminal env_id; "
            f"got {multi_episode_envs}"
        )


def _validate_episode(record: Any, index: int) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    label = f"terminal episode record {index}"
    terminal = _require_mapping(record, label)
    episode = _require_mapping(terminal.get("pull_v0_episode"), f"{label}.pull_v0_episode")
    events = _require_mapping(episode.get("event_reached"), f"{label}.pull_v0_episode.event_reached")
    if set(events) != set(EVENT_NAMES):
        raise ValueError(f"{label}.event_reached must contain exactly E0-E7")
    for name in EVENT_NAMES:
        _require_bool(events, name, f"{label}.event_reached")
    v3 = _validate_v3_terminal(terminal, label)
    return episode, v3


def _load_payload(
    metrics_path: Path,
    trace_path: Path | None = None,
) -> tuple[
    dict[str, Any],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
]:
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"metrics payload must be an object: {metrics_path}")
    terminals = payload.get("episode_terminal_diagnostics")
    if not isinstance(terminals, list) or len(terminals) != 16:
        raise ValueError(f"{metrics_path} must contain exactly 16 terminal diagnostics")
    episodes: list[Mapping[str, Any]] = []
    terminal_v3: list[Mapping[str, Any]] = []
    for index, record in enumerate(terminals):
        episode, v3 = _validate_episode(record, index)
        episodes.append(episode)
        terminal_v3.append(v3)
    if trace_path is None:
        trace_path = metrics_path.parent / "stage2_5_step_trace.json"
    if not trace_path.is_file():
        raise FileNotFoundError(f"required diagnostic trace is missing: {trace_path}")
    trace_rows = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(trace_rows, list) or not trace_rows:
        raise ValueError(f"required diagnostic trace must be a non-empty list: {trace_path}")
    validated_trace = [_validate_v3_trace_row(row, index) for index, row in enumerate(trace_rows)]
    _validate_trace_coverage(terminals, validated_trace)
    return payload, episodes, terminal_v3, validated_trace


def _rate(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _summary(values: Iterable[float]) -> dict[str, Any]:
    finite = [float(value) for value in values if _finite(value) is not None]
    return {
        "count": len(finite),
        "median": median(finite) if finite else None,
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
    }


def _event_rate(episodes: list[Mapping[str, Any]], name: str) -> float | None:
    return _rate(sum(bool(row["event_reached"][name]) for row in episodes), len(episodes))


def _first_stage4_rows(trace_rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    first: dict[int, tuple[int, Mapping[str, Any]]] = {}
    for row in trace_rows:
        pull = row["pull_v0"]
        if pull["stage"] < 4:
            continue
        candidate = (row["step_index"], row)
        prior = first.get(row["env_id"])
        if prior is None or candidate[0] < prior[0]:
            first[row["env_id"]] = candidate
    return [value[1] for _env, value in sorted(first.items())]


def _invariants(trace_rows: list[Mapping[str, Any]], episodes: list[Mapping[str, Any]], terminal_v3: list[Mapping[str, Any]]) -> dict[str, Any]:
    fake_e4 = sum(
        bool(row["event_reached"]["E4_POSITIVE_HINGE_RETAINED"])
        and not bool(row["event_reached"]["E2_TENSILE_CAPTURE"])
        for row in episodes
    )
    lower_gate = 0
    for row in _first_stage4_rows(trace_rows):
        pull = row["pull_v0"]
        if pull["hinge_position_rad"] < row["stage3_to4_door_hinge_threshold"]:
            lower_gate += 1
    dont_push_before = 0
    target_root_before = 0
    corridor_pre_aperture = 0
    for row in trace_rows:
        pull = row["pull_v0"]
        rewards = pull["reward_component_raw"]
        aperture = row["pull_v3_traversal"]
        if rewards["dont_push_door_handle"] != 0.0 and pull["stage"] < 4:
            dont_push_before += 1
        if rewards["target_root_distance"] != 0.0 and pull["event_state"] not in APERTURE_READY_EVENTS:
            target_root_before += 1
        corridor_pre_aperture += int(aperture["corridor_door_wide_pre_aperture_steps"])
        corridor_pre_aperture += int(aperture["corridor_clean_passage_pre_aperture_steps"])
        if not bool(aperture["aperture_ready_latched"]):
            corridor_pre_aperture += int(
                _finite(aperture["corridor_door_wide_raw"]) > 0.0
                or _finite(aperture["corridor_clean_passage_raw"]) > 0.0
            )
    complete_without_frame = sum(bool(row["complete_without_frame_passage"]) for row in terminal_v3)
    result = {
        "fake_e4": int(fake_e4),
        "stage4_snapshot_below_hinge_gate": int(lower_gate),
        "dont_push_before_true_stage3_to4": int(dont_push_before),
        "target_root_before_aperture_ready": int(target_root_before),
        "corridor_active_before_aperture_ready": int(corridor_pre_aperture),
        "complete_without_frame_passage": int(complete_without_frame),
        "all_zero": all(
            value == 0
            for value in (
                fake_e4,
                lower_gate,
                dont_push_before,
                target_root_before,
                corridor_pre_aperture,
                complete_without_frame,
            )
        ),
        "stage4_admission_count": len(_first_stage4_rows(trace_rows)),
    }
    return result


def _funnel(episodes: list[Mapping[str, Any]], terminal_v3: list[Mapping[str, Any]]) -> dict[str, Any]:
    release_steps = [value for value in (_step_or_na(row, "deliberate_release_step", "terminal") for row in terminal_v3) if value is not None]
    negative_steps = [value for value in (_step_or_na(row, "first_negative_x_motion_step", "terminal") for row in terminal_v3) if value is not None]
    release_latency = []
    for release, negative in zip(terminal_v3, terminal_v3):
        release_step = _step_or_na(release, "deliberate_release_step", "terminal")
        negative_step = _step_or_na(negative, "first_negative_x_motion_step", "terminal")
        if release_step is not None and negative_step is not None:
            release_latency.append(max(0, negative_step - release_step))
    e5_e7 = [value for value in (_step_or_na(row, "e5_to_e7_steps", "terminal") for row in terminal_v3) if value is not None]
    panel_steps = []
    for episode in episodes:
        value = _finite(episode.get("body_panel_contact_steps_per_20s"))
        if value is not None:
            panel_steps.append(value)
    detour = sum(bool(row["detour"]) for row in terminal_v3)
    crossing = sum(bool(row["planar_crossing"]) for row in terminal_v3)
    return {
        "episode_count": len(episodes),
        "deliberate_release_rate": _rate(sum(bool(row["deliberate_release"]) for row in terminal_v3), len(terminal_v3)),
        "deliberate_release_step": _summary(release_steps),
        "release_to_first_negative_x_motion_steps": _summary(release_latency),
        "first_negative_x_motion_rate": _rate(len(negative_steps), len(terminal_v3)),
        "frame_approach_rate": _rate(sum(bool(row["frame_approach"]) for row in terminal_v3), len(terminal_v3)),
        "frame_passage_rate": _rate(sum(bool(row["frame_passage"]) for row in terminal_v3), len(terminal_v3)),
        "planar_crossing_rate": _rate(crossing, len(terminal_v3)),
        "detour_rate": _rate(detour, len(terminal_v3)),
        "E5_to_E7_steps": _summary(e5_e7),
        "panel_contact_steps": _summary(panel_steps),
        "swept_arc_clearance_margin_m": _summary(row["swept_arc_clearance_margin_min_m"] for row in terminal_v3),
        "base_path_length_m": _summary(row["base_path_length_m"] for row in terminal_v3),
        "base_reversal_count": _summary(row["base_reversal_count"] for row in terminal_v3),
        "post_release_recontact_count": _summary(row["post_release_recontact_count"] for row in terminal_v3),
        "corridor_door_wide_pre_aperture_steps": _summary(row["corridor_door_wide_pre_aperture_steps"] for row in terminal_v3),
        "corridor_clean_passage_pre_aperture_steps": _summary(row["corridor_clean_passage_pre_aperture_steps"] for row in terminal_v3),
    }


def _primary(episodes: list[Mapping[str, Any]], payload: Mapping[str, Any]) -> dict[str, Any]:
    completion = payload.get("episode_goal_reached")
    if not isinstance(completion, list) or len(completion) != len(episodes) or any(
        not isinstance(value, bool) for value in completion
    ):
        raise ValueError(
            "metrics payload episode_goal_reached must be a bool list matching the 16 terminal episodes"
        )
    return {
        "episode_count": len(episodes),
        "event_rates": {name: _event_rate(episodes, name) for name in EVENT_NAMES},
        "true_stage3_to4_rate": _event_rate(episodes, "E4_POSITIVE_HINGE_RETAINED"),
        "E6_rate": _event_rate(episodes, "E6_PATH_REVERSAL_ENTRY"),
        "E7_rate": _event_rate(episodes, "E7_WHOLE_BODY_CLEAR"),
        "complete_rate": _rate(sum(completion), len(completion)),
    }


def _cell(metrics_path: Path) -> dict[str, Any]:
    payload, episodes, terminal_v3, trace_rows = _load_payload(metrics_path)
    match = re.search(r"seed(?P<seed>[0-2])_step(?P<step>250|500|750)(?:/|$)", str(metrics_path))
    if match is None:
        raise ValueError(f"metrics path must expose seed and checkpoint step: {metrics_path}")
    source = str(metrics_path.relative_to(ROOT)) if metrics_path.is_relative_to(ROOT) else str(metrics_path)
    return {
        "source": source,
        "seed": int(match.group("seed")),
        "step": int(match.group("step")),
        "primary": _primary(episodes, payload),
        "funnel": _funnel(episodes, terminal_v3),
        "invariants": _invariants(trace_rows, episodes, terminal_v3),
        "terminal_reason_counts": {
            str(reason): sum(1 for episode in episodes if episode.get("terminal_reason") == reason)
            for reason in sorted({str(episode.get("terminal_reason", "UNKNOWN")) for episode in episodes})
        },
        "episode_lengths_steps": _summary(
            float(value)
            for value in payload.get("episode_lengths", [])
            if _finite(value) is not None
        ),
    }


def _walk_metrics(inputs: Iterable[Path]) -> list[Path]:
    def is_preserved_d0(path: Path) -> bool:
        return any(part.startswith("D0_lite") for part in path.parts)

    paths: set[Path] = set()
    for raw in inputs:
        path = raw.resolve()
        if path.is_file() and path.name == "metrics_eval.json":
            if not is_preserved_d0(path):
                paths.add(path)
        elif path.is_dir():
            paths.update(
                candidate
                for candidate in path.rglob("metrics_eval.json")
                if not is_preserved_d0(candidate)
            )
        else:
            raise FileNotFoundError(path)
    if not paths:
        raise ValueError("pull-v3 analysis requires at least one metrics_eval.json input")
    return sorted(paths)


def _family(path: Path) -> str:
    match = re.search(r"/(?P<run>[^/]*seed[0-2])_step(?:250|500|750)/eval/metrics_eval\.json$", str(path))
    if match is None:
        raise ValueError(f"metrics path does not expose a v3 run family: {path}")
    return re.sub(r"_seed[0-2]$", "", match.group("run"))


def _decision(cells: list[dict[str, Any]], seeds: tuple[int, ...]) -> dict[str, Any]:
    for cell in cells:
        nonzero = {
            key: cell["invariants"].get(key)
            for key in FORMAL_INVARIANT_KEYS
            if cell["invariants"].get(key) != 0
        }
        if nonzero:
            raise ValueError(
                f"formal cell invariant failure before decision at {cell['source']}: {nonzero}"
            )
    expected = {(seed, step) for seed in seeds for step in STEPS}
    observed = {(cell["seed"], cell["step"]) for cell in cells}
    if observed != expected:
        raise ValueError(f"analysis requires complete cells; missing={sorted(expected - observed)}, unexpected={sorted(observed - expected)}")
    by_seed = {seed: [cell for cell in cells if cell["seed"] == seed] for seed in seeds}
    classes: dict[str, str] = {}
    inputs: dict[str, Any] = {}
    for seed, items in by_seed.items():
        e6 = max((cell["primary"]["E6_rate"] or 0.0 for cell in items), default=0.0)
        e7 = max((cell["primary"]["E7_rate"] or 0.0 for cell in items), default=0.0)
        detour = max((cell["funnel"]["detour_rate"] or 0.0 for cell in items), default=0.0)
        inputs[str(seed)] = {"max_E6_rate": e6, "max_E7_rate": e7, "max_detour_rate": detour}
        classes[str(seed)] = "G1" if e6 > 0.0 else ("G3" if detour > 0.0 else "G2")
    g1 = any(label == "G1" for label in classes.values())
    g4 = len(set(classes.values())) > 1 and "G1" in classes.values()
    g3 = any(label == "G3" for label in classes.values()) and not g1
    branch = "G4" if g4 else ("G1" if g1 else ("G3" if g3 else "G2"))
    pooled_panel = [cell["funnel"]["panel_contact_steps"]["median"] for cell in cells if cell["funnel"]["panel_contact_steps"]["median"] is not None]
    pooled_recontact = [cell["funnel"]["post_release_recontact_count"]["max"] for cell in cells]
    log = [
        {"rule": "G1", "status": "TRIGGERED" if g1 else "NOT_TRIGGERED", "evidence": inputs},
        {"rule": "G2", "status": "TRIGGERED" if not g1 else "NOT_TRIGGERED", "evidence": "release/negative-X/frame funnel retained"},
        {"rule": "G3", "status": "TRIGGERED" if g3 else "NOT_TRIGGERED", "evidence": inputs},
        {"rule": "G4", "status": "TRIGGERED" if g4 else "NOT_TRIGGERED", "evidence": classes},
        {"rule": "G5", "status": "TRIGGERED" if any(value > 0.0 for value in pooled_panel) else "NOT_TRIGGERED", "evidence": {"v2_panel_contact_median": 0, "observed_medians": pooled_panel}},
        {"rule": "G6", "status": "NOT_TRIGGERED", "evidence": "requires runtime overtime-progress adjudication"},
        {"rule": "G7", "status": "NOT_TRIGGERED", "evidence": "analysis input is complete"},
        {"rule": "G8", "status": "NOT_TRIGGERED", "evidence": "GPU occupancy is orchestration evidence"},
        {"rule": "G9", "status": "NOT_TRIGGERED", "evidence": "timing is not inferred from metrics"},
        {"rule": "G10", "status": "TRIGGERED" if any((value or 0.0) > 1.0 for value in pooled_recontact) else "NOT_TRIGGERED", "evidence": {"max_recontact": max(pooled_recontact, default=None)}},
    ]
    return {"decision_seeds": list(seeds), "seed_inputs": inputs, "seed_classes": classes, "selected_branch": branch, "G1_G10_decision_log": log}


def _comparison_rows(experiments: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(V2_BASELINE)]
    for family, result in experiments.items():
        for cell in result["cells"]:
            rows.append({
                "label": f"{family} seed{cell['seed']} step{cell['step']}",
                "seed": cell["seed"],
                "step": cell["step"],
                "true_stage3_to4_rate": cell["primary"]["true_stage3_to4_rate"],
                "E6_rate": cell["primary"]["E6_rate"],
                "E7_rate": cell["primary"]["E7_rate"],
                "complete_rate": cell["primary"]["complete_rate"],
                "E5_to_E7_steps": cell["funnel"]["E5_to_E7_steps"],
                "deliberate_release_rate": cell["funnel"]["deliberate_release_rate"],
                "first_negative_x_motion_rate": cell["funnel"]["first_negative_x_motion_rate"],
                "release_to_first_negative_x_motion_steps": cell["funnel"]["release_to_first_negative_x_motion_steps"],
                "detour_rate": cell["funnel"]["detour_rate"],
                "frame_passage_rate": cell["funnel"]["frame_passage_rate"],
                "panel_contact_steps": cell["funnel"]["panel_contact_steps"],
                "clearance_margin_m": cell["funnel"]["swept_arc_clearance_margin_m"],
                "base_path_length_m": cell["funnel"]["base_path_length_m"],
                "base_reversal_count": cell["funnel"]["base_reversal_count"],
                "post_release_recontact_count": cell["funnel"]["post_release_recontact_count"],
                "invariants": cell["invariants"],
            })
    return rows


def analyze(inputs: Iterable[Path], seeds: tuple[int, ...] = (0, 1)) -> dict[str, Any]:
    metrics_paths = _walk_metrics(inputs)
    grouped: dict[str, list[Path]] = {}
    for path in metrics_paths:
        grouped.setdefault(_family(path), []).append(path)
    experiments: dict[str, Any] = {}
    for family, paths in sorted(grouped.items()):
        cells = []
        observed: set[tuple[int, int]] = set()
        for path in paths:
            cell = _cell(path)
            key = (cell["seed"], cell["step"])
            if key in observed:
                raise ValueError(f"duplicate metrics cell {key} in family {family}")
            observed.add(key)
            cells.append(cell)
        expected = {(seed, step) for seed in seeds for step in STEPS}
        if observed != expected:
            raise ValueError(f"family {family} is incomplete; missing={sorted(expected - observed)}, unexpected={sorted(observed - expected)}")
        cells.sort(key=lambda cell: (cell["seed"], cell["step"]))
        experiments[family] = {"cells": cells, "decision": _decision(cells, seeds)}
    return {
        "schema": "pull_v3_analysis_v1_fail_closed",
        "plan_id": "a2_piper_pull_v3_release_then_cross_traversal",
        "checkpoint_steps_required": list(STEPS),
        "v2_wave2_baseline": V2_BASELINE,
        "experiments": experiments,
        "cells": [cell for result in experiments.values() for cell in result["cells"]],
        "main_comparison_table": _comparison_rows(experiments),
        "G1_G10_decision_log": {family: result["decision"] for family, result in experiments.items()},
    }


def validate_d0_metrics(metrics_path: Path, trace_path: Path) -> dict[str, Any]:
    payload, episodes, terminal_v3, trace_rows = _load_payload(metrics_path, trace_path)
    invariants = _invariants(trace_rows, episodes, terminal_v3)
    if not invariants["all_zero"]:
        raise ValueError(f"D0-lite invariant failure: {invariants}")
    lengths = [float(value) for value in payload.get("episode_lengths", []) if _finite(value) is not None]
    if len(lengths) != 16:
        lengths = [float(episode.get("episode_length_steps", 0)) for episode in episodes if _finite(episode.get("episode_length_steps")) is not None]
    if len(lengths) != 16 or max(lengths) <= 654.0:
        raise ValueError(f"D0-lite requires a measured episode length above 654 steps; got {lengths}")
    e6 = sum(bool(episode["event_reached"]["E6_PATH_REVERSAL_ENTRY"]) for episode in episodes)
    e7 = sum(bool(episode["event_reached"]["E7_WHOLE_BODY_CLEAR"]) for episode in episodes)
    if e6 != 0 or e7 != 0:
        raise ValueError(f"D0-lite frozen actor must retain E6/E7 negative baseline; got E6={e6}, E7={e7}")
    return {
        "episode_count": len(episodes),
        "invariants": invariants,
        "episode_length_steps": _summary(lengths),
        "max_episode_length_steps": max(lengths),
        "E6_count": e6,
        "E7_count": e7,
        "corridor_raw_pre_aperture": 0,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", default=[DEFAULT_INPUT])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--include-seed2", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    seeds = (0, 1, 2) if args.include_seed2 else (0, 1)
    result = analyze(args.input, seeds=seeds)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite analysis output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
