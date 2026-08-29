"""Strict readers shared by V6.1 offline reducers."""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def load_trace(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, list) or not value or not all(isinstance(row, dict) for row in value):
        raise TypeError(f"trace must be a non-empty JSON list of objects: {path}")
    return value


def required(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise KeyError(f"missing {where}.{key}")
    return mapping[key]


def nested(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for index, key in enumerate(keys):
        if not isinstance(value, dict):
            raise TypeError(f"{'.'.join(keys[:index])} must be a mapping")
        value = required(value, key, ".".join(keys[:index]) or "row")
    return value


def first_episode_rows(rows: Iterable[dict[str, Any]], env_id: int) -> list[dict[str, Any]]:
    selected = [
        row for row in rows
        if required(row, "env_id", "row") == env_id
        and required(row, "episode_index", "row") == 0
        and required(row, "first_episode_active", "row") is True
    ]
    if not selected:
        raise ValueError(f"trace has no first-episode rows for env_id={env_id}")
    selected.sort(key=lambda row: required(row, "step_index", "row"))
    return selected


def episode_rows(rows: Iterable[dict[str, Any]]) -> dict[tuple[int, int], list[dict[str, Any]]]:
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (required(row, "env_id", "row"), required(row, "episode_index", "row"))
        groups[key].append(row)
    for group in groups.values():
        group.sort(key=lambda row: required(row, "step_index", "row"))
    return groups


def scalar_reward(row: dict[str, Any]) -> float:
    reward = required(row, "reward_scaled", "row")
    if not isinstance(reward, dict):
        raise TypeError("row.reward_scaled must be a mapping")
    return float(sum(float(value) for value in reward.values()))


def first_step_with(rows: list[dict[str, Any]], predicate) -> int | None:
    for index, row in enumerate(rows):
        if predicate(row):
            return index
    return None


def optional_event_step(value: Any, label: str) -> int | None:
    if value is None or value == "N/A":
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer step or N/A")
    return value


def summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    last = rows[-1]
    episode = nested(last, "pull_v0_episode")
    if not isinstance(episode, dict):
        raise TypeError("pull_v0_episode must be a mapping")
    events = required(episode, "first_event_step", "pull_v0_episode")
    if not isinstance(events, dict):
        raise TypeError("pull_v0_episode.first_event_step must be a mapping")
    traverse = nested(last, "pull_v3_traversal")
    v6 = nested(last, "pull_v0", "pull_v6")
    if not isinstance(traverse, dict) or not isinstance(v6, dict):
        raise TypeError("pull trace subrecords must be mappings")
    clean_release_index = first_step_with(rows, lambda row: bool(nested(row, "pull_v0", "pull_v6", "clean_release")))
    if clean_release_index is None:
        clean_release_step = None
        k25_step = None
    else:
        clean_release_step = required(rows[clean_release_index], "step_index", "row")
        k25_index = first_step_with(
            rows[clean_release_index:],
            lambda row: int(nested(row, "pull_v0", "pull_v6", "release_persistence_steps")) >= 25,
        )
        k25_step = None if k25_index is None else required(rows[clean_release_index + k25_index], "step_index", "row")
    release_rows = [] if clean_release_index is None else rows[clean_release_index:]
    running_peak = None
    reclosure = 0.0
    for row in release_rows:
        hinge = float(required(row, "door_hinge_joint_pos", "row"))
        running_peak = hinge if running_peak is None else max(running_peak, hinge)
        reclosure = max(reclosure, running_peak - hinge)
    contact_steps = {"arm_panel": 0, "body_panel": 0, "arm_frame": 0, "body_frame": 0}
    for row in release_rows:
        panel = nested(row, "pull_v0", "panel_contact_force_by_body_N")
        frame = nested(row, "pull_v0", "frame_contact_force_by_body_N")
        contact_steps["arm_panel"] += int(any(float(value) > 0.0 for name, value in panel.items() if name.startswith("arm_")))
        contact_steps["body_panel"] += int(any(float(value) > 0.0 for name, value in panel.items() if not name.startswith("arm_")))
        contact_steps["arm_frame"] += int(any(float(value) > 0.0 for name, value in frame.items() if name.startswith("arm_")))
        contact_steps["body_frame"] += int(any(float(value) > 0.0 for name, value in frame.items() if not name.startswith("arm_")))
    e5_step = optional_event_step(events.get("E5_CLEARANCE_DECISION"), "E5 step")
    e6_step = optional_event_step(events.get("E6_PATH_REVERSAL_ENTRY"), "E6 step")
    e7_step = optional_event_step(events.get("E7_WHOLE_BODY_CLEAR"), "E7 step")
    return {
        "env_id": required(last, "env_id", "row"),
        "control_dt_s": float(required(last, "control_dt", "row")),
        "terminal_step": required(last, "step_index", "row"),
        "terminal_reason_post_step": required(last, "terminal_reasons", "row"),
        "terminal_complete_post_step": bool(nested(last, "pull_v0_episode", "whole_body_clear")),
        "e5_step": e5_step,
        "clean_release_step": clean_release_step,
        "release_persistence_k25_step": k25_step,
        "frame_passage_step": traverse.get("frame_passage_step"),
        "e6_step": e6_step,
        "e7_step": e7_step,
        "clean_release_to_e7_s": (
            None if clean_release_step is None or not isinstance(e7_step, int)
            else (e7_step - clean_release_step) * float(required(last, "control_dt", "row"))
        ),
        "base_path_length_m": traverse.get("base_path_length_m"),
        "base_reversal_count": traverse.get("base_reversal_count"),
        "post_release_recontact_count": traverse.get("post_release_recontact_count"),
        "hinge_reclosure_after_release_rad": None if running_peak is None else reclosure,
        "post_release_contact_steps": contact_steps,
        "e5_to_e7_s": (
            required(episode, "e5_to_whole_body_clear_s", "pull_v0_episode")
            if "e5_to_whole_body_clear_s" in episode
            else required(episode, "release_to_whole_body_clear_s", "pull_v0_episode")
        ),
        "timing_semantics": (
            "pull_v61_clean_release_and_explicit_e5"
            if "e5_to_whole_body_clear_s" in episode
            else "legacy_trace_release_field_is_e5"
        ),
    }
