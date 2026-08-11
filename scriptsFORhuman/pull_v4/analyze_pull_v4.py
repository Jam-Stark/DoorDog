#!/usr/bin/env python3
"""Fail-closed pull-v4 D0 and twelve-cell analysis.

The analyzer is intentionally strict: a report is written only after every
expected A/B × seed0/seed1 × step250/500/750 cell has metrics, terminal
diagnostics, and a stage2–5 conditional trace with zero integrity violations.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
V4_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "logs_eval/a2_piper_pull_v4"
DEFAULT_OUTPUT = V4_DIR / "PULL_V4_ANALYSIS.json"
DEFAULT_G6_OUTPUT = V4_DIR / "PULL_V4_G6_ANALYSIS.json"
DEFAULT_D0_OUTPUT = V4_DIR / "D0_LITE_RECEIPT.json"
PLAN_ID = "a2_piper_pull_v4_annuity_removal_and_frame_approach"
STEPS = (250, 500, 750)
VARIANTS = ("A", "B")
SEEDS = (0, 1)
TRACE_STAGE_DOMAIN = frozenset((2, 3, 4, 5))
G6_WINDOW_STEPS = (20, 50)
G6_TERMINAL_STAGE_DOMAIN = frozenset((4, 5))
G6_CELL_NAMES = frozenset(
    f"pull_v4_B_wave1_seed{seed}_step{step}_g6_budget"
    for seed in SEEDS
    for step in STEPS
)
WARM_CHECKPOINT = (
    ROOT
    / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    / "pull_v2_W_wave2_relay_seed1/model_step_000750.pt"
)
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
APERTURE_EVENTS = frozenset(EVENT_NAMES[5:])
INVARIANT_KEYS = (
    "fake_e4",
    "stage4_snapshot_below_hinge_gate",
    "dont_push_before_true_stage3_to4",
    "target_root_before_aperture_ready",
    "corridor_active_before_aperture_ready",
    "complete_without_frame_passage",
    "frame_approach_active_before_aperture_ready",
    "frame_approach_active_after_frame_passage",
)
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
    "frame_approach_active": ("frame_approach_active",),
    "frame_approach_reward_executed": ("frame_approach_reward_executed",),
    "corridor_door_wide_reward_executed": ("corridor_door_wide_reward_executed",),
}
TRACE_FINITE_ALIASES = {
    "minimum_clearance_margin_m": ("minimum_clearance_margin_m",),
    "swept_arc_clearance_margin_current_m": (
        "swept_arc_clearance_margin_current_m",
        "swept_arc_clearance_margin_m",
    ),
    "swept_arc_clearance_margin_min_m": ("swept_arc_clearance_margin_min_m",),
    "base_path_length_m": ("base_path_length_m",),
    "corridor_door_wide_raw": (
        "corridor_door_wide_raw",
        "corridor_door_wide_raw_last",
    ),
    "corridor_clean_passage_raw": ("corridor_clean_passage_raw",),
    "frame_approach_raw": (
        "frame_approach_raw",
        "frame_approach_raw_last",
    ),
    "frame_midpoint_distance_m": ("frame_midpoint_distance_m",),
    "frame_midpoint_distance_min_m": ("frame_midpoint_distance_min_m",),
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
V3_TERMINAL_BOOL_FIELDS = (
    "frame_passage",
    "planar_crossing",
    "detour",
    "deliberate_release",
    "frame_approach",
    "frame_approach_active",
    "frame_approach_reward_executed",
    "corridor_door_wide_reward_executed",
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
    "frame_approach_raw_last",
    "frame_midpoint_distance_min_m",
    "corridor_door_wide_raw_last",
)
V3_TERMINAL_INT_FIELDS = (
    "base_reversal_count",
    "post_release_recontact_count",
    "corridor_door_wide_pre_aperture_steps",
    "corridor_clean_passage_pre_aperture_steps",
    "frame_approach_active_before_aperture_steps",
    "frame_approach_active_after_frame_passage_steps",
)
REWARD_INCOME_KEYS = (
    "dont_push_door_handle",
    "target_root_distance",
    "pull_door_handle",
    "pull_door_hinge",
    "a2_corridor_clean_passage",
)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object; got {type(value).__name__}")
    return value


def _bool(mapping: Mapping[str, Any], key: str, label: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{label}.{key} must be bool; got {value!r}")
    return value


def _number(mapping: Mapping[str, Any], key: str, label: str) -> float:
    value = _finite(mapping.get(key))
    if value is None:
        raise ValueError(f"{label}.{key} must be finite; got {mapping.get(key)!r}")
    return value


def _nonnegative_int(mapping: Mapping[str, Any], key: str, label: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label}.{key} must be a non-negative int; got {value!r}")
    return value


def _step(mapping: Mapping[str, Any], key: str, label: str) -> int | None:
    value = mapping.get(key)
    if value is None or value == "N/A":
        return None
    return _nonnegative_int(mapping, key, label)


def _alias(mapping: Mapping[str, Any], aliases: tuple[str, ...], label: str) -> Any:
    present = [key for key in aliases if key in mapping]
    if not present:
        raise ValueError(f"{label} is missing required field {aliases[0]!r}")
    values = [mapping[key] for key in present]
    if any(value != values[0] for value in values[1:]):
        raise ValueError(f"{label} contains conflicting aliases {present!r}")
    return values[0]


def _validate_terminal(record: Any, index: int, variant: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    label = f"terminal episode record {index}"
    terminal = _mapping(record, label)
    _nonnegative_int(terminal, "env_id", label)
    _nonnegative_int(terminal, "stage_buf", label)
    episode = _mapping(terminal.get("pull_v0_episode"), f"{label}.pull_v0_episode")
    events = _mapping(episode.get("event_reached"), f"{label}.pull_v0_episode.event_reached")
    if set(events) != set(EVENT_NAMES):
        raise ValueError(f"{label}.event_reached must contain exactly E0-E7")
    for name in EVENT_NAMES:
        _bool(events, name, f"{label}.event_reached")
    traversal = _mapping(terminal.get("pull_v3_traversal"), f"{label}.pull_v3_traversal")
    for key in V3_TERMINAL_BOOL_FIELDS:
        _bool(traversal, key, f"{label}.pull_v3_traversal")
    if variant == "A" and traversal["frame_approach_reward_executed"]:
        raise ValueError(f"{label} A arm must not execute frame_approach reward")
    if variant == "B" and not traversal["frame_approach_reward_executed"]:
        raise ValueError(f"{label} B arm must execute frame_approach reward")
    if traversal["corridor_door_wide_reward_executed"]:
        raise ValueError(f"{label} door-wide reward must be removed in v4")
    for key in V3_TERMINAL_STEP_FIELDS:
        _step(traversal, key, f"{label}.pull_v3_traversal")
    for key in V3_TERMINAL_FINITE_FIELDS:
        value = traversal.get(key)
        if value is None and key == "swept_arc_clearance_margin_min_m":
            continue
        _number(traversal, key, f"{label}.pull_v3_traversal")
    for key in V3_TERMINAL_INT_FIELDS:
        _nonnegative_int(traversal, key, f"{label}.pull_v3_traversal")
    sums = _mapping(terminal.get("reward_episode_sums"), f"{label}.reward_episode_sums")
    for key in REWARD_INCOME_KEYS:
        _number(sums, key, f"{label}.reward_episode_sums")
    if variant == "A" and "a2_pull_frame_approach" in sums:
        raise ValueError(f"{label} A arm must omit inactive frame_approach income")
    if variant == "B":
        _number(sums, "a2_pull_frame_approach", f"{label}.reward_episode_sums")
    return episode, traversal


def _validate_trace_row(row: Any, index: int, variant: str) -> Mapping[str, Any]:
    label = f"step trace row {index}"
    top = _mapping(row, label)
    _nonnegative_int(top, "env_id", label)
    _nonnegative_int(top, "step_index", label)
    _nonnegative_int(top, "episode_index", label)
    threshold = _number(top, "stage3_to4_door_hinge_threshold", label)
    if threshold <= 0.0:
        raise ValueError(f"{label}.stage3_to4_door_hinge_threshold must be positive")
    pull = _mapping(top.get("pull_v0"), f"{label}.pull_v0")
    for key in (
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
    ):
        if key not in pull:
            raise ValueError(f"{label}.pull_v0 is missing {key!r}")
    _nonnegative_int(pull, "stage", f"{label}.pull_v0")
    if pull["event_state"] not in EVENT_NAMES:
        raise ValueError(f"{label}.pull_v0.event_state is not an E0-E7 value")
    for key in (
        "root_x_rel_door_m",
        "handle_position_rad",
        "latch_position_m",
        "hinge_position_rad",
        "target_tcp_position_error_m",
        "gripper_handle_separation_m",
    ):
        _number(pull, key, f"{label}.pull_v0")
    slip = pull["handle_local_slip_xyz_mps"]
    if slip != "N/A" and (
        not isinstance(slip, list)
        or len(slip) != 3
        or any(_finite(value) is None for value in slip)
    ):
        raise ValueError(f"{label}.pull_v0.handle_local_slip_xyz_mps must be a finite 3-vector/N/A")
    for key in ("finger_effort_utilization_estimate", "arm_pd_effort_utilization_estimate"):
        estimate = _mapping(pull[key], f"{label}.pull_v0.{key}")
        values = estimate.get("value")
        if not isinstance(values, list) or not values or any(_finite(value) is None for value in values):
            raise ValueError(f"{label}.pull_v0.{key}.value must be a non-empty finite list")
        if not isinstance(estimate.get("provenance"), str) or not estimate["provenance"]:
            raise ValueError(f"{label}.pull_v0.{key}.provenance must be non-empty")
    rewards = _mapping(pull["reward_component_raw"], f"{label}.pull_v0.reward_component_raw")
    for key in ("dont_push_door_handle", "target_root_distance", "a2_corridor_clean_passage"):
        _number(rewards, key, f"{label}.pull_v0.reward_component_raw")
    if variant == "A" and "a2_pull_frame_approach" in rewards:
        raise ValueError(f"{label} A trace must omit frame_approach reward component")
    if variant == "B":
        _number(rewards, "a2_pull_frame_approach", f"{label}.pull_v0.reward_component_raw")
    traversal = _mapping(pull.get("pull_v3_traversal"), f"{label}.pull_v0.pull_v3_traversal")
    normalized = dict(top)
    normalized_traversal = dict(traversal)
    for key, aliases in TRACE_BOOL_ALIASES.items():
        value = _alias(traversal, aliases, f"{label}.pull_v3_traversal.{key}")
        if not isinstance(value, bool):
            raise ValueError(f"{label}.pull_v3_traversal.{key} must be bool")
        normalized_traversal[key] = value
    if variant == "A" and normalized_traversal["frame_approach_reward_executed"]:
        raise ValueError(f"{label} A trace executes inactive frame_approach reward")
    if variant == "B" and not normalized_traversal["frame_approach_reward_executed"]:
        raise ValueError(f"{label} B trace does not execute frame_approach reward")
    if normalized_traversal["corridor_door_wide_reward_executed"]:
        raise ValueError(f"{label} trace executes removed door-wide reward")
    for key, aliases in TRACE_FINITE_ALIASES.items():
        value = _alias(traversal, aliases, f"{label}.pull_v3_traversal.{key}")
        if value is None and key in {"minimum_clearance_margin_m", "swept_arc_clearance_margin_current_m"}:
            continue
        _finite_value = _finite(value)
        if _finite_value is None:
            raise ValueError(f"{label}.pull_v3_traversal.{key} must be finite")
        normalized_traversal[key] = _finite_value
    for key, aliases in TRACE_INT_ALIASES.items():
        value = _alias(traversal, aliases, f"{label}.pull_v3_traversal.{key}")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{label}.pull_v3_traversal.{key} must be a non-negative int")
        normalized_traversal[key] = value
    normalized["pull_v0"] = dict(pull)
    normalized["pull_v0"]["pull_v3_traversal"] = normalized_traversal
    return normalized


def _validate_trace_coverage(terminals: list[Mapping[str, Any]], rows: list[Mapping[str, Any]]) -> None:
    terminal_ids: dict[int, int] = {}
    for index, terminal in enumerate(terminals):
        env_id = terminal["env_id"]
        stage_buf = terminal["stage_buf"]
        if env_id in terminal_ids:
            raise ValueError(f"duplicate terminal env_id {env_id}")
        terminal_ids[env_id] = stage_buf
    trace_episode_ids: dict[int, set[int]] = {}
    for row in rows:
        trace_episode_ids.setdefault(row["env_id"], set()).add(row["episode_index"])
    expected = {env_id for env_id, stage in terminal_ids.items() if stage in TRACE_STAGE_DOMAIN}
    observed = set(trace_episode_ids)
    if observed != expected:
        raise ValueError(
            "trace coverage must match terminal stage2-5 env_ids; "
            f"missing={sorted(expected - observed)}, unexpected={sorted(observed - expected)}"
        )
    invalid = {env: sorted(ids) for env, ids in trace_episode_ids.items() if len(ids) != 1}
    if invalid:
        raise ValueError(f"trace coverage requires one episode identity per env_id; got {invalid}")


def _load_payload(metrics_path: Path, variant: str) -> tuple[dict[str, Any], list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    payload = _mapping(json.loads(metrics_path.read_text(encoding="utf-8")), str(metrics_path))
    terminals_raw = payload.get("episode_terminal_diagnostics")
    if not isinstance(terminals_raw, list) or len(terminals_raw) != 16:
        raise ValueError(f"{metrics_path} must contain exactly 16 terminal diagnostics")
    episodes: list[Mapping[str, Any]] = []
    traversal: list[Mapping[str, Any]] = []
    for index, record in enumerate(terminals_raw):
        episode, v3 = _validate_terminal(record, index, variant)
        episodes.append(episode)
        traversal.append(v3)
    trace_path = metrics_path.parent / "stage2_5_step_trace.json"
    if not trace_path.is_file():
        raise FileNotFoundError(f"required diagnostic trace is missing: {trace_path}")
    rows_raw = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(rows_raw, list) or not rows_raw:
        raise ValueError(f"required diagnostic trace must be a non-empty list: {trace_path}")
    rows = [_validate_trace_row(row, index, variant) for index, row in enumerate(rows_raw)]
    _validate_trace_coverage(terminals_raw, rows)
    return dict(payload), episodes, traversal, rows


def _rate(numerator: int | float, denominator: int | float) -> float | None:
    return None if denominator == 0 else float(numerator) / float(denominator)


def _summary(values: Iterable[float]) -> dict[str, Any]:
    finite = [float(value) for value in values if _finite(value) is not None]
    return {
        "count": len(finite),
        "median": median(finite) if finite else None,
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
    }


def _event_rate(episodes: list[Mapping[str, Any]], name: str) -> float | None:
    return _rate(sum(bool(episode["event_reached"][name]) for episode in episodes), len(episodes))


def _first_stage4_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    first: dict[int, tuple[int, Mapping[str, Any]]] = {}
    for row in rows:
        pull = row["pull_v0"]
        if pull["stage"] < 4:
            continue
        prior = first.get(row["env_id"])
        candidate = (row["step_index"], row)
        if prior is None or candidate[0] < prior[0]:
            first[row["env_id"]] = candidate
    return [item[1] for _env, item in sorted(first.items())]


def _invariants(rows: list[Mapping[str, Any]], episodes: list[Mapping[str, Any]], traversal: list[Mapping[str, Any]]) -> dict[str, Any]:
    fake_e4 = sum(bool(episode["event_reached"]["E4_POSITIVE_HINGE_RETAINED"]) and not bool(episode["event_reached"]["E2_TENSILE_CAPTURE"]) for episode in episodes)
    stage4_snapshot = sum(
        row["pull_v0"]["hinge_position_rad"] < row["stage3_to4_door_hinge_threshold"]
        for row in _first_stage4_rows(rows)
    )
    dont_push = 0
    target_root = 0
    corridor = 0
    frame_before = 0
    frame_after = 0
    for row in rows:
        pull = row["pull_v0"]
        rewards = pull["reward_component_raw"]
        state = pull["pull_v3_traversal"]
        if rewards["dont_push_door_handle"] != 0.0 and pull["stage"] < 4:
            dont_push += 1
        if rewards["target_root_distance"] != 0.0 and pull["event_state"] not in APERTURE_EVENTS:
            target_root += 1
        if not state["aperture_ready_latched"]:
            corridor += int(state["corridor_door_wide_pre_aperture_steps"])
            corridor += int(state["corridor_clean_passage_pre_aperture_steps"])
            corridor += int(state["corridor_door_wide_raw"] != 0.0)
            if state["frame_approach_active"]:
                frame_before += 1
        if state["frame_approach_active"] and state["frame_passage_latched"]:
            frame_after += 1
    corridor += sum(int(item["corridor_door_wide_pre_aperture_steps"]) for item in traversal)
    frame_before += sum(int(item["frame_approach_active_before_aperture_steps"]) for item in traversal)
    frame_after += sum(int(item["frame_approach_active_after_frame_passage_steps"]) for item in traversal)
    complete_without = sum(bool(item["complete_without_frame_passage"]) for item in traversal)
    result = {
        "fake_e4": int(fake_e4),
        "stage4_snapshot_below_hinge_gate": int(stage4_snapshot),
        "dont_push_before_true_stage3_to4": int(dont_push),
        "target_root_before_aperture_ready": int(target_root),
        "corridor_active_before_aperture_ready": int(corridor),
        "complete_without_frame_passage": int(complete_without),
        "frame_approach_active_before_aperture_ready": int(frame_before),
        "frame_approach_active_after_frame_passage": int(frame_after),
    }
    result["all_zero"] = all(result[key] == 0 for key in INVARIANT_KEYS)
    return result


def _primary(payload: Mapping[str, Any], episodes: list[Mapping[str, Any]]) -> dict[str, Any]:
    completed = payload.get("episode_goal_reached")
    if not isinstance(completed, list) or len(completed) != 16 or any(not isinstance(value, bool) for value in completed):
        raise ValueError("episode_goal_reached must be a bool list of length 16")
    return {
        "episode_count": 16,
        "event_rates": {name: _event_rate(episodes, name) for name in EVENT_NAMES},
        "true_stage3_to4_rate": _event_rate(episodes, "E4_POSITIVE_HINGE_RETAINED"),
        "E6_rate": _event_rate(episodes, "E6_PATH_REVERSAL_ENTRY"),
        "E7_rate": _event_rate(episodes, "E7_WHOLE_BODY_CLEAR"),
        "complete_rate": _rate(sum(completed), len(completed)),
    }


def _income(terminal_records: list[Mapping[str, Any]], variant: str) -> dict[str, Any]:
    keys = list(REWARD_INCOME_KEYS) + (["a2_pull_frame_approach"] if variant == "B" else [])
    result = {}
    for key in keys:
        result[key] = _summary(
            _number(_mapping(record["reward_episode_sums"], "reward_episode_sums"), key, "reward_episode_sums")
            for record in terminal_records
        )
    return result


def _funnel(traversal: list[Mapping[str, Any]], episodes: list[Mapping[str, Any]]) -> dict[str, Any]:
    release_steps = [item["deliberate_release_step"] for item in traversal if item["deliberate_release_step"] is not None]
    negative_steps = [item["first_negative_x_motion_step"] for item in traversal if item["first_negative_x_motion_step"] is not None]
    release_latency = [item["release_to_first_negative_x_motion_steps"] for item in traversal if item["release_to_first_negative_x_motion_steps"] is not None]
    e5_e7 = [item["e5_to_e7_steps"] for item in traversal if item["e5_to_e7_steps"] is not None]
    panel = [float(value) for value in (episode.get("body_panel_contact_steps_per_20s") for episode in episodes) if _finite(value) is not None]
    return {
        "deliberate_release_rate": _rate(sum(bool(item["deliberate_release"]) for item in traversal), 16),
        "deliberate_release_step": _summary(release_steps),
        "release_to_first_negative_x_motion_steps": _summary(release_latency),
        "first_negative_x_motion_rate": _rate(len(negative_steps), 16),
        "frame_approach_rate": _rate(sum(bool(item["frame_approach"]) for item in traversal), 16),
        "frame_passage_rate": _rate(sum(bool(item["frame_passage"]) for item in traversal), 16),
        "planar_crossing_rate": _rate(sum(bool(item["planar_crossing"]) for item in traversal), 16),
        "detour_rate": _rate(sum(bool(item["detour"]) for item in traversal), 16),
        "E5_to_E7_steps": _summary(e5_e7),
        "panel_contact_steps": _summary(panel),
        "frame_midpoint_distance_m": _summary(item["frame_midpoint_distance_min_m"] for item in traversal),
        "swept_arc_clearance_margin_m": _summary(item["swept_arc_clearance_margin_min_m"] for item in traversal),
        "base_path_length_m": _summary(item["base_path_length_m"] for item in traversal),
        "base_reversal_count": _summary(item["base_reversal_count"] for item in traversal),
        "post_release_recontact_count": _summary(item["post_release_recontact_count"] for item in traversal),
    }


def _g6_evidence(
    payload: Mapping[str, Any],
    traversal: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
    variant: str,
) -> dict[str, Any]:
    """Measure diagnostic-neutral terminal progress in corroborating W20/W50 windows.

    G6 is deliberately narrower than terminal overtime: an affected episode must
    have a stage-overtime terminal in stage 4/5, complete conditional trace rows,
    active/executed frame reward telemetry, positive signed raw income, and a
    strict root-to-frame distance decrease in both terminal windows.
    """

    rows_by_env: dict[int, list[Mapping[str, Any]]] = {}
    for row in rows:
        rows_by_env.setdefault(int(row["env_id"]), []).append(row)
    for env_rows in rows_by_env.values():
        env_rows.sort(key=lambda row: int(row["step_index"]))

    per_episode: list[dict[str, Any]] = []
    affected_env_ids: list[int] = []
    eligible_count = 0
    window_positive_counts = {str(window): 0 for window in G6_WINDOW_STEPS}
    window_distance_decrease_counts = {str(window): 0 for window in G6_WINDOW_STEPS}

    terminals = payload["episode_terminal_diagnostics"]
    if not isinstance(terminals, list) or len(terminals) != len(traversal):
        raise ValueError("G6 terminal/traversal records must remain one-to-one")
    for index, terminal_raw in enumerate(terminals):
        terminal = _mapping(terminal_raw, f"terminal episode record {index}")
        env_id = _nonnegative_int(terminal, "env_id", f"terminal episode record {index}")
        stage = _nonnegative_int(terminal, "stage_buf", f"terminal episode record {index}")
        reason = terminal.get("terminal_reasons")
        if not isinstance(reason, str) or not reason:
            raise ValueError(f"terminal episode record {index}.terminal_reasons must be a non-empty string")
        if reason != "stage_overtime" or stage not in G6_TERMINAL_STAGE_DOMAIN:
            continue
        eligible_count += 1
        env_rows = rows_by_env.get(env_id, [])
        if len(env_rows) < max(G6_WINDOW_STEPS):
            raise ValueError(
                f"G6 requires at least {max(G6_WINDOW_STEPS)} conditional trace rows for terminal env {env_id}; "
                f"got {len(env_rows)}"
            )
        terminal_window_rows = env_rows[-max(G6_WINDOW_STEPS):]
        if any(row["pull_v0"]["stage"] not in G6_TERMINAL_STAGE_DOMAIN for row in terminal_window_rows):
            raise ValueError(f"G6 terminal window for env {env_id} contains a non-stage4/5 trace row")
        terminal_state = traversal[index]
        if variant == "B" and not terminal_state["frame_approach_reward_executed"]:
            raise ValueError(f"G6 terminal env {env_id} is missing executed frame-approach reward telemetry")

        windows: dict[str, dict[str, Any]] = {}
        corroborating = True
        for window_size in G6_WINDOW_STEPS:
            window = env_rows[-window_size:]
            step_indices = [int(row["step_index"]) for row in window]
            if step_indices != list(range(step_indices[0], step_indices[0] + window_size)):
                raise ValueError(f"G6 trace window W{window_size} for env {env_id} is not contiguous")
            states = [row["pull_v0"]["pull_v3_traversal"] for row in window]
            raw_values = [_finite(state.get("frame_approach_raw")) for state in states]
            distance_values = [_finite(state.get("frame_midpoint_distance_m")) for state in states]
            if any(value is None for value in raw_values + distance_values):
                raise ValueError(f"G6 trace window W{window_size} for env {env_id} has missing frame raw/distance data")
            active_executed = bool(terminal_state["frame_approach_active"]) and all(
                bool(state["frame_approach_active"]) and bool(state["frame_approach_reward_executed"])
                for state in states
            )
            raw_sum = float(sum(raw_values))
            distance_decrease = float(distance_values[0] - distance_values[-1])
            positive_raw = active_executed and raw_sum > 0.0
            decreased = active_executed and distance_decrease > 0.0
            passes = positive_raw and decreased
            window_positive_counts[str(window_size)] += int(positive_raw)
            window_distance_decrease_counts[str(window_size)] += int(decreased)
            corroborating = corroborating and passes
            windows[f"W{window_size}"] = {
                "trace_row_count": len(window),
                "step_start": step_indices[0],
                "step_end": step_indices[-1],
                "frame_reward_active_and_executed": active_executed,
                "signed_frame_approach_raw_sum": raw_sum,
                "signed_frame_approach_raw_mean": raw_sum / window_size,
                "positive_signed_raw": positive_raw,
                "frame_midpoint_distance_start_m": float(distance_values[0]),
                "frame_midpoint_distance_end_m": float(distance_values[-1]),
                "distance_decrease_m": distance_decrease,
                "distance_decreased": decreased,
                "passes": passes,
            }
        if corroborating:
            affected_env_ids.append(env_id)
        per_episode.append({
            "env_id": env_id,
            "terminal_stage": stage,
            "terminal_reason": reason,
            "frame_approach_reward_executed": bool(terminal_state["frame_approach_reward_executed"]),
            "corroborating_W20_W50": corroborating,
            "windows": windows,
        })

    return {
        "window_steps": list(G6_WINDOW_STEPS),
        "terminal_stage_domain": sorted(G6_TERMINAL_STAGE_DOMAIN),
        "eligible_terminal_stage4_5_overtime_count": eligible_count,
        "affected_count": len(affected_env_ids),
        "affected_rate": _rate(len(affected_env_ids), eligible_count),
        "affected_env_ids": affected_env_ids,
        "window_positive_signed_raw_counts": window_positive_counts,
        "window_distance_decrease_counts": window_distance_decrease_counts,
        "per_episode_evidence": per_episode,
        "status": "TRIGGERED" if affected_env_ids else "NOT_TRIGGERED",
        "variant": variant,
    }


def _identity(metrics_path: Path, input_root: Path) -> tuple[str, int, int]:
    relative = metrics_path.resolve().relative_to(input_root.resolve())
    expected = re.fullmatch(
        r"pull_v4_(A|B)_wave1_seed([01])_step(250|500|750)/eval/metrics_eval\.json",
        str(relative),
    )
    if expected is None:
        raise ValueError(f"metrics path is not a canonical v4 Wave1 cell: {metrics_path}")
    return expected.group(1), int(expected.group(2)), int(expected.group(3))


def _cell(metrics_path: Path, input_root: Path) -> dict[str, Any]:
    variant, seed, step = _identity(metrics_path, input_root)
    payload, episodes, traversal, rows = _load_payload(metrics_path, variant)
    invariants = _invariants(rows, episodes, traversal)
    if not invariants["all_zero"]:
        raise ValueError(f"integrity invariant failure at {metrics_path}: {invariants}")
    income = _income(
        [_mapping(record, "terminal") for record in payload["episode_terminal_diagnostics"]],
        variant,
    )
    income["a2_corridor_door_wide"] = _summary(item["corridor_door_wide_raw_last"] for item in traversal)
    return {
        "variant": variant,
        "seed": seed,
        "step": step,
        "source": str(metrics_path.relative_to(ROOT)),
        "primary": _primary(payload, episodes),
        "funnel": _funnel(traversal, episodes),
        "income": income,
        "invariants": invariants,
        "g6": _g6_evidence(payload, traversal, rows, variant),
        "terminal_reason_counts": {
            str(reason): sum(1 for reason_value in payload.get("episode_terminal_reasons", []) if reason_value == reason)
            for reason in sorted(set(payload.get("episode_terminal_reasons", [])))
        },
    }


def _all_cells(input_root: Path) -> list[dict[str, Any]]:
    expected_names = {
        f"pull_v4_{variant}_wave1_seed{seed}_step{step}"
        for variant in VARIANTS
        for seed in SEEDS
        for step in STEPS
    }
    observed_names = {
        path.name
        for path in input_root.glob("pull_v4_*_wave1_seed*_step*")
        if path.is_dir()
    }
    unexpected = observed_names - expected_names - G6_CELL_NAMES
    if unexpected:
        raise ValueError(f"unexpected v4 Wave1 cell directories are present: {sorted(unexpected)}")
    cells = []
    for variant in VARIANTS:
        for seed in SEEDS:
            for step in STEPS:
                metrics = input_root / f"pull_v4_{variant}_wave1_seed{seed}_step{step}/eval/metrics_eval.json"
                if not metrics.is_file():
                    raise FileNotFoundError(f"required v4 metrics cell is missing: {metrics}")
                cells.append(_cell(metrics, input_root))
    return cells


def _g6_identity(metrics_path: Path, input_root: Path) -> tuple[str, int, int]:
    relative = metrics_path.resolve().relative_to(input_root.resolve())
    expected = re.fullmatch(
        r"pull_v4_B_wave1_seed([01])_step(250|500|750)_g6_budget/eval/metrics_eval\.json",
        str(relative),
    )
    if expected is None:
        raise ValueError(f"metrics path is not a canonical v4 B G6 cell: {metrics_path}")
    return "B", int(expected.group(1)), int(expected.group(2))


def _g6_cell(metrics_path: Path, input_root: Path) -> dict[str, Any]:
    variant, seed, step = _g6_identity(metrics_path, input_root)
    payload, episodes, traversal, rows = _load_payload(metrics_path, variant)
    invariants = _invariants(rows, episodes, traversal)
    if not invariants["all_zero"]:
        raise ValueError(f"integrity invariant failure at {metrics_path}: {invariants}")
    income = _income(
        [_mapping(record, "terminal") for record in payload["episode_terminal_diagnostics"]],
        variant,
    )
    income["a2_corridor_door_wide"] = _summary(item["corridor_door_wide_raw_last"] for item in traversal)
    return {
        "variant": variant,
        "seed": seed,
        "step": step,
        "source": str(metrics_path.relative_to(ROOT)),
        "primary": _primary(payload, episodes),
        "funnel": _funnel(traversal, episodes),
        "income": income,
        "invariants": invariants,
        "g6": _g6_evidence(payload, traversal, rows, variant),
        "terminal_reason_counts": {
            str(reason): sum(1 for reason_value in payload.get("episode_terminal_reasons", []) if reason_value == reason)
            for reason in sorted(set(payload.get("episode_terminal_reasons", [])))
        },
    }


def _all_g6_cells(input_root: Path) -> list[dict[str, Any]]:
    expected_names = G6_CELL_NAMES
    observed_names = {
        path.name
        for path in input_root.glob("pull_v4_*_wave1_seed*_step*_g6_budget*")
        if path.is_dir()
    }
    unexpected = observed_names - expected_names
    if unexpected:
        raise ValueError(f"unexpected v4 G6 cell directories are present: {sorted(unexpected)}")
    cells = []
    for seed in SEEDS:
        for step in STEPS:
            metrics = input_root / f"pull_v4_B_wave1_seed{seed}_step{step}_g6_budget/eval/metrics_eval.json"
            if not metrics.is_file():
                raise FileNotFoundError(f"required v4 G6 metrics cell is missing: {metrics}")
            cells.append(_g6_cell(metrics, input_root))
    return cells


def _decision(cells: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant = {variant: [cell for cell in cells if cell["variant"] == variant] for variant in VARIANTS}
    e6 = {variant: max((cell["primary"]["E6_rate"] or 0.0 for cell in items), default=0.0) for variant, items in by_variant.items()}
    detour = {variant: max((cell["funnel"]["detour_rate"] or 0.0 for cell in items), default=0.0) for variant, items in by_variant.items()}
    seed_e6 = {
        variant: {
            seed: max(
                (cell["primary"]["E6_rate"] or 0.0 for cell in items if cell["seed"] == seed),
                default=0.0,
            )
            for seed in SEEDS
        }
        for variant, items in by_variant.items()
    }
    seed_split = {
        variant: seed_values[0] != seed_values[1]
        for variant, seed_values in seed_e6.items()
    }
    panel = [cell["funnel"]["panel_contact_steps"]["median"] or 0.0 for cell in cells]
    recontact = [cell["funnel"]["post_release_recontact_count"]["max"] or 0.0 for cell in cells]
    frame_income = [cell["income"].get("a2_pull_frame_approach", {}).get("max") or 0.0 for cell in cells if cell["variant"] == "B"]
    g6_cells = [cell for cell in cells if cell["variant"] == "B" and cell["g6"]["affected_count"] > 0]
    frame_net_mismatch = any(
        abs(cell["income"].get("a2_pull_frame_approach", {}).get("max") or 0.0) > 0.0
        and (cell["funnel"]["base_path_length_m"]["max"] is None or cell["funnel"]["base_path_length_m"]["max"] <= 0.0)
        for cell in cells
        if cell["variant"] == "B"
    )
    rules = {
        "G1": (any(value > 0.0 for value in e6.values()), e6),
        "G2": (all(value == 0.0 for value in e6.values()), e6),
        "G3": (any(value > 0.0 for value in detour.values()), detour),
        "G4": (any(seed_split.values()), seed_e6),
        "G5": (any(value > 0.0 for value in panel), {"panel_contact_median_max": max(panel, default=0.0)}),
        "G6": (
            bool(g6_cells),
            {
                "affected_cell_count": len(g6_cells),
                "per_cell": {
                    f"{cell['variant']}_seed{cell['seed']}_step{cell['step']}": cell["g6"]
                    for cell in cells
                    if cell["variant"] == "B"
                },
            },
        ),
        "G7": (False, "all twelve cells have complete metrics/trace/diagnostics"),
        "G8": (False, "canonical cell set is complete; GPU occupancy is launch evidence"),
        "G9": (False, "analysis completed from the required cell set"),
        "G10": (any(value > 0.0 for value in recontact), {"post_release_recontact_max": max(recontact, default=0.0)}),
        "G11": (frame_net_mismatch, {"frame_approach_income_max": max(frame_income, default=0.0), "net_input_contract": "signed raw telemetry compared with base path length"}),
    }
    return {
        rule: {"status": "TRIGGERED" if triggered else "NOT_TRIGGERED", "evidence": evidence}
        for rule, (triggered, evidence) in rules.items()
    }


def _comparison(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [{
        "label": "v3 T Wave1 baseline",
        "variant": "v3",
        "E6_rate": 0.0,
        "E7_rate": 0.0,
        "complete_rate": 0.0,
        "deliberate_release_rate": "see scriptsFORhuman/pull_v3/PULL_V3_ANALYSIS_WAVE1.json",
    }]
    rows.extend({
        "label": f"v4 {cell['variant']} seed{cell['seed']} step{cell['step']}",
        "variant": cell["variant"],
        "seed": cell["seed"],
        "step": cell["step"],
        "E6_rate": cell["primary"]["E6_rate"],
        "E7_rate": cell["primary"]["E7_rate"],
        "complete_rate": cell["primary"]["complete_rate"],
        "deliberate_release_rate": cell["funnel"]["deliberate_release_rate"],
        "frame_midpoint_distance_m": cell["funnel"]["frame_midpoint_distance_m"],
        "invariants": cell["invariants"],
    } for cell in cells)
    return rows


def analyze(input_root: Path) -> dict[str, Any]:
    cells = _all_cells(input_root.resolve())
    result = {
        "schema": "pull_v4_analysis_v2_fail_closed",
        "status": "PASS",
        "plan_id": PLAN_ID,
        "warm_checkpoint": str(WARM_CHECKPOINT),
        "expected_cells": [
            {"variant": variant, "seed": seed, "step": step}
            for variant in VARIANTS for seed in SEEDS for step in STEPS
        ],
        "trace_stage_domain": sorted(TRACE_STAGE_DOMAIN),
        "cells": cells,
        "main_comparison_table": _comparison(cells),
        "dv": {
            "release_curve": {variant: [cell["funnel"]["deliberate_release_rate"] for cell in cells if cell["variant"] == variant] for variant in VARIANTS},
            "frame_midpoint_distance_distribution": {variant: [cell["funnel"]["frame_midpoint_distance_m"] for cell in cells if cell["variant"] == variant] for variant in VARIANTS},
            "frame_approach_rate": {variant: [cell["funnel"]["frame_approach_rate"] for cell in cells if cell["variant"] == variant] for variant in VARIANTS},
            "reward_income": {variant: [cell["income"] for cell in cells if cell["variant"] == variant] for variant in VARIANTS},
            "E6_rate": {variant: [cell["primary"]["E6_rate"] for cell in cells if cell["variant"] == variant] for variant in VARIANTS},
            "E7_rate": {variant: [cell["primary"]["E7_rate"] for cell in cells if cell["variant"] == variant] for variant in VARIANTS},
            "complete_rate": {variant: [cell["primary"]["complete_rate"] for cell in cells if cell["variant"] == variant] for variant in VARIANTS},
        },
        "invariants": {key: 0 for key in INVARIANT_KEYS} | {"all_zero": True},
        "g1_g11": _decision(cells),
        "evidence_boundary": "PASS is limited to validated JSON metrics, terminal diagnostics, and conditional stage2-5 traces; no runtime claim is inferred.",
    }
    return result


def analyze_g6(input_root: Path, baseline_input_root: Path = DEFAULT_INPUT) -> dict[str, Any]:
    g6_cells = _all_g6_cells(input_root.resolve())
    baseline_cells = _all_cells(baseline_input_root.resolve())
    baseline_by_key = {
        (cell["variant"], cell["seed"], cell["step"]): cell
        for cell in baseline_cells
    }
    extra_time: dict[str, Any] = {}
    for cell in g6_cells:
        key = ("B", cell["seed"], cell["step"])
        baseline = baseline_by_key.get(key)
        if baseline is None:
            raise ValueError(f"G6 baseline cell is missing for B seed{cell['seed']} step{cell['step']}")
        outcome_fields = ("E6_rate", "E7_rate", "complete_rate")
        baseline_outcome = {field: baseline["primary"][field] for field in outcome_fields}
        extended_outcome = {field: cell["primary"][field] for field in outcome_fields}
        label = f"B_seed{cell['seed']}_step{cell['step']}"
        extra_time[label] = {
            "baseline": baseline_outcome,
            "g6_extended": extended_outcome,
            "outcome_changed": baseline_outcome != extended_outcome,
            "baseline_release_rate": baseline["funnel"]["deliberate_release_rate"],
            "g6_release_rate": cell["funnel"]["deliberate_release_rate"],
            "baseline_frame_approach_rate": baseline["funnel"]["frame_approach_rate"],
            "g6_frame_approach_rate": cell["funnel"]["frame_approach_rate"],
            "baseline_frame_midpoint_distance_m": baseline["funnel"]["frame_midpoint_distance_m"],
            "g6_frame_midpoint_distance_m": cell["funnel"]["frame_midpoint_distance_m"],
        }
    changed_count = sum(item["outcome_changed"] for item in extra_time.values())
    return {
        "schema": "pull_v4_g6_analysis_v1_fail_closed",
        "status": "PASS",
        "plan_id": PLAN_ID,
        "input_root": str(input_root.resolve()),
        "baseline_input_root": str(baseline_input_root.resolve()),
        "expected_cells": [
            {"variant": "B", "seed": seed, "step": step, "budget": "g6_extended"}
            for seed in SEEDS for step in STEPS
        ],
        "cells": g6_cells,
        "main_comparison_table": _comparison(g6_cells),
        "dv": {
            "E6_rate": [cell["primary"]["E6_rate"] for cell in g6_cells],
            "E7_rate": [cell["primary"]["E7_rate"] for cell in g6_cells],
            "complete_rate": [cell["primary"]["complete_rate"] for cell in g6_cells],
            "release_rate": [cell["funnel"]["deliberate_release_rate"] for cell in g6_cells],
            "frame_approach_rate": [cell["funnel"]["frame_approach_rate"] for cell in g6_cells],
            "frame_midpoint_distance_m": [cell["funnel"]["frame_midpoint_distance_m"] for cell in g6_cells],
        },
        "invariants": {key: 0 for key in INVARIANT_KEYS} | {"all_zero": True},
        "g6": {
            "window_steps": list(G6_WINDOW_STEPS),
            "affected_counts_by_cell": {
                f"B_seed{cell['seed']}_step{cell['step']}": cell["g6"]["affected_count"]
                for cell in g6_cells
            },
            "evidence_by_cell": {
                f"B_seed{cell['seed']}_step{cell['step']}": cell["g6"]
                for cell in g6_cells
            },
        },
        "extra_time_outcome": {
            "outcome_fields": ["E6_rate", "E7_rate", "complete_rate"],
            "changed_cell_count": changed_count,
            "any_outcome_changed": bool(changed_count),
            "per_cell": extra_time,
        },
        "evidence_boundary": "PASS is limited to validated six-cell JSON metrics, terminal diagnostics, and conditional stage2-5 traces; no runtime claim is inferred.",
    }


def _checkpoint_binding(run_dir: Path) -> None:
    candidates = [
        run_dir / "hydra/.hydra/overrides.yaml",
        run_dir / "hydra/.hydra/config.yaml",
        run_dir / "hydra/.hydra/runtime_config.yaml",
    ]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise FileNotFoundError(f"D0 checkpoint binding metadata is missing under {run_dir}")
    text = "\n".join(path.read_text(encoding="utf-8") for path in existing)
    if str(WARM_CHECKPOINT) not in text and str(WARM_CHECKPOINT.relative_to(ROOT)) not in text:
        raise ValueError(f"D0 must bind exactly the canonical warm checkpoint: {WARM_CHECKPOINT}")
    if "pull_v4_B_frame_approach" not in text:
        raise ValueError("D0 checkpoint metadata is not bound to the v4 B arm")


def validate_d0_metrics(metrics_path: Path, trace_path: Path) -> dict[str, Any]:
    if metrics_path.parent.name != "eval" or metrics_path.parent.parent.name != "D0_lite_B_seed1_step750":
        raise ValueError(f"D0 metrics path must be D0_lite_B_seed1_step750/eval/metrics_eval.json: {metrics_path}")
    run_dir = metrics_path.parents[1]
    _checkpoint_binding(run_dir)
    payload, episodes, traversal, rows = _load_payload(metrics_path, "B")
    if trace_path.resolve() != metrics_path.parent.joinpath("stage2_5_step_trace.json").resolve():
        raise ValueError("D0 trace path must be the sibling stage2_5_step_trace.json")
    invariants = _invariants(rows, episodes, traversal)
    if not invariants["all_zero"]:
        raise ValueError(f"D0 invariant failure: {invariants}")
    e6 = sum(bool(episode["event_reached"]["E6_PATH_REVERSAL_ENTRY"]) for episode in episodes)
    e7 = sum(bool(episode["event_reached"]["E7_WHOLE_BODY_CLEAR"]) for episode in episodes)
    if e6 != 0 or e7 != 0:
        raise ValueError(f"D0 frozen actor must retain E6/E7=0; got E6={e6}, E7={e7}")
    wide_values = [item["corridor_door_wide_raw_last"] for item in traversal]
    if any(value != 0.0 for value in wide_values) or any(item["corridor_door_wide_reward_executed"] for item in traversal):
        raise ValueError("D0 removed door-wide term must have raw=0 and executed=false")
    signed = [row["pull_v0"]["pull_v3_traversal"]["frame_approach_raw"] for row in rows]
    if not signed or any(_finite(value) is None for value in signed):
        raise ValueError("D0 requires finite signed frame-approach raw telemetry")
    if not any(value > 0.0 for value in signed) or not any(value < 0.0 for value in signed):
        raise ValueError("D0 frame-approach telemetry must contain both positive and negative signed steps")
    frame_income = [
        _number(_mapping(record["reward_episode_sums"], "reward_episode_sums"), "a2_pull_frame_approach", "reward_episode_sums")
        for record in payload["episode_terminal_diagnostics"]
    ]
    lengths = [float(value) for value in payload.get("episode_lengths", []) if _finite(value) is not None]
    if len(lengths) != 16 or max(lengths) <= 654.0:
        raise ValueError(f"D0 requires measured episode length above the v2 baseline; got {lengths}")
    return {
        "schema": "pull_v4_d0_lite_receipt_v2",
        "status": "PASS",
        "plan_id": PLAN_ID,
        "variant": "B",
        "checkpoint": str(WARM_CHECKPOINT),
        "episode_count": 16,
        "E6_count": e6,
        "E7_count": e7,
        "invariants": invariants,
        "corridor_door_wide_raw": {"min": min(wide_values), "max": max(wide_values), "executed": False},
        "frame_approach_raw": _summary(signed),
        "frame_approach_episode_income": _summary(frame_income),
        "episode_length_steps": _summary(lengths),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--g6-input", type=Path, help="analyze the six B-only _g6_budget cells into a separate report")
    parser.add_argument("--baseline-input-root", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--d0-lite", action="store_true")
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--trace", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.g6_input is not None and args.d0_lite:
        raise ValueError("--g6-input cannot be combined with --d0-lite")
    if args.d0_lite:
        metrics = args.metrics or (args.input_root / "D0_lite_B_seed1_step750/eval/metrics_eval.json")
        trace = args.trace or metrics.parent / "stage2_5_step_trace.json"
        receipt = validate_d0_metrics(metrics.resolve(), trace.resolve())
        output = args.output or DEFAULT_D0_OUTPUT
    elif args.g6_input is not None:
        if args.metrics is not None or args.trace is not None:
            raise ValueError("--metrics/--trace are only valid with --d0-lite")
        receipt = analyze_g6(args.g6_input.resolve(), args.baseline_input_root.resolve())
        output = args.output or DEFAULT_G6_OUTPUT
    else:
        if args.metrics is not None or args.trace is not None:
            raise ValueError("--metrics/--trace are only valid with --d0-lite")
        receipt = analyze(args.input_root.resolve())
        output = args.output or DEFAULT_OUTPUT
    if output.exists():
        raise FileExistsError(f"refusing to overwrite analysis output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
