"""Raw-record P0.5 feasibility certificate.

The certificate consumes the three actual 16-episode producer exports.  It
never admits legacy scalar/aggregate summaries, external prefix booleans, or
pair-only artifacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import V23Error, artifact_payload, emit_payload, finite_number, read_json
except ImportError:  # direct script invocation
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        V23Error,
        artifact_payload,
        emit_payload,
        finite_number,
        read_json,
    )

from gr00t.rl.envs.door.a2_v23_evidence import (
    V23_P05_EPISODE_SCHEMA,
    V23_P05_FAILURE_FLAGS,
    V23_P05_MODES,
    V23_P05_RESCUE_NOT_APPLICABLE_BASELINE_AT_MAX,
    V23_P05_STEP_SCHEMA,
    V23_P05_WINDOW_SCHEMA,
    a2_v23_build_p05_window_record,
    a2_v23_validate_p05_bands,
    a2_v23_validate_p05_prefix,
)


P05_EPISODE_EXPORT_SCHEMA = "a2_piper_v23_episode_records_export_v1"
P05_BUNDLE_SCHEMAS = frozenset(
    (
        "a2_piper_v23_p05_producer_bundle_v1",
        "a2_piper_v23_p05_producer_bundle_v2",
        "a2_piper_v23_p05_producer_bundle_v3",
    )
)
P05_PAIR_SCHEMAS = frozenset(
    (
        "a2_piper_v23_p05_pair_export_v1",
        "a2_piper_v23_p05_pair_export_v2",
        "a2_piper_v23_p05_pair_export_v3",
    )
)


def _identity(record: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    fields = ("checkpoint", "config", "scenario", "topology", "seed", "episode_id")
    if any(field not in record for field in fields):
        raise V23Error(f"{label} identity is incomplete")
    if isinstance(record["seed"], bool) or not isinstance(record["seed"], int):
        raise V23Error(f"{label}.seed must be an integer")
    if any(
        not isinstance(record[field], str) or not record[field]
        for field in fields
        if field != "seed"
    ):
        raise V23Error(f"{label} identity fields must be non-empty strings")
    return {field: record[field] for field in fields}


def _group_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    identity = _identity(record, label="episode")
    prefix = record.get("plain_prefix_id")
    if not isinstance(prefix, str) or not prefix:
        raise V23Error("episode plain_prefix_id is required")
    return tuple(identity[field] for field in identity) + (prefix,)


def _record_windows(episode: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    windows = episode.get("window_rows")
    if not isinstance(windows, list) or any(not isinstance(item, Mapping) for item in windows):
        raise V23Error("episode window_rows must be a list of objects")
    return list(windows)


def _episode_provenance(episode: Mapping[str, Any]) -> tuple[int, int]:
    """Return the env/episode coordinates already checked on every raw row."""

    rows = episode.get("step_rows")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        raise V23Error("episode step_rows must expose a first row for provenance")
    return rows[0]["env_id"], rows[0]["episode_index"]


def _validate_step_rows(
    episode: Mapping[str, Any], *, identity: Mapping[str, Any], mode: str, prefix_id: str
) -> list[Mapping[str, Any]]:
    rows = episode.get("step_rows")
    if isinstance(rows, (str, bytes)) or not isinstance(rows, list) or not rows:
        raise V23Error(f"{mode} step_rows must be a non-empty list")
    control_steps: list[int] = []
    first_env_id: int | None = None
    first_episode_index: int | None = None
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or row.get("schema") != V23_P05_STEP_SCHEMA:
            raise V23Error(f"{mode} step_rows[{index}] has an unsupported schema")
        if row.get("mode") != mode or row.get("plain_prefix_id") != prefix_id:
            raise V23Error(f"{mode} step_rows[{index}] source identity does not match the episode")
        if _identity(row, label=f"{mode} step_rows[{index}]") != identity:
            raise V23Error(f"{mode} step_rows[{index}] source identity does not match the episode")
        required = (
            "env_id",
            "episode_index",
            "control_step",
            "switch_step",
            "stable_grasp_predicates",
            "stable_grasp_streak",
            "stable_grasp",
            "hinge_position_rad",
            "hinge_velocity_rad_s",
            "arm_nominal_torque_nm",
            "arm_clipped_torque_nm",
            "arm_effort_limit_nm",
            "clipped_utilization_min",
            "clipped_utilization_fraction",
            "failure_flags",
            "requested_rescue_profile",
            "applied_rescue_profile",
            "state_clone_supported",
            "forward_only",
        )
        if any(field not in row for field in required):
            raise V23Error(f"{mode} step_rows[{index}] is missing a raw evidence field")
        env_id = row["env_id"]
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < 16:
            raise V23Error(f"{mode} step_rows[{index}] env_id must be within 0..15")
        episode_index = row["episode_index"]
        if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
            raise V23Error(f"{mode} step_rows[{index}] episode_index is malformed")
        if index == 0:
            first_env_id = env_id
            first_episode_index = episode_index
        elif env_id != first_env_id or episode_index != first_episode_index:
            raise V23Error(
                f"{mode} step_rows must preserve immutable env_id and episode_index"
            )
        predicates = row["stable_grasp_predicates"]
        if not isinstance(predicates, Mapping) or not predicates or any(
            not isinstance(value, bool) for value in predicates.values()
        ):
            raise V23Error(f"{mode} step_rows[{index}] stable_grasp_predicates are malformed")
        streak = row["stable_grasp_streak"]
        if isinstance(streak, bool) or not isinstance(streak, int) or streak < 0:
            raise V23Error(f"{mode} step_rows[{index}] stable_grasp_streak is malformed")
        if not isinstance(row["stable_grasp"], bool):
            raise V23Error(f"{mode} step_rows[{index}] stable_grasp must be bool")
        control_step = row["control_step"]
        if isinstance(control_step, bool) or not isinstance(control_step, int) or control_step < 0:
            raise V23Error(f"{mode} step_rows[{index}] control_step is malformed")
        control_steps.append(control_step)
        if row["state_clone_supported"] is not False or row["forward_only"] is not True:
            raise V23Error(f"{mode} step_rows[{index}] violates forward-only provenance")
    if control_steps != list(range(control_steps[0], control_steps[0] + len(control_steps))) or control_steps[0] != 0:
        raise V23Error(f"{mode} step_rows must be ordered and contiguous from control_step 0")
    return rows


def _validate_episode(episode: Mapping[str, Any]) -> Mapping[str, Any]:
    if episode.get("schema") != V23_P05_EPISODE_SCHEMA:
        raise V23Error("producer episode has an unsupported schema")
    if episode.get("state_clone_supported") is not False or episode.get("forward_only") is not True:
        raise V23Error("producer episode violates forward-only provenance")
    mode = episode.get("mode")
    if mode not in V23_P05_MODES:
        raise V23Error(f"producer episode has unsupported mode {mode!r}")
    identity = _identity(episode, label=f"{mode} episode")
    prefix_id = episode.get("plain_prefix_id")
    if not isinstance(prefix_id, str) or not prefix_id:
        raise V23Error(f"{mode} episode plain_prefix_id is required")
    _validate_step_rows(episode, identity=identity, mode=mode, prefix_id=prefix_id)
    for index, window in enumerate(_record_windows(episode)):
        if (
            window.get("schema") != V23_P05_WINDOW_SCHEMA
            or window.get("mode") != mode
            or window.get("plain_prefix_id") != prefix_id
            or _identity(window, label=f"{mode} window_rows[{index}]") != identity
            or window.get("state_clone_supported") is not False
        ):
            raise V23Error(f"{mode} window_rows[{index}] schema/identity/provenance is invalid")
    switch_step = episode.get("switch_step")
    if isinstance(switch_step, bool) or not isinstance(switch_step, int) or switch_step < -1:
        raise V23Error(f"{mode} switch_step must be -1 or non-negative")
    rescue_status = episode.get("rescue_status")
    if not isinstance(rescue_status, str) or not rescue_status:
        raise V23Error(f"{mode} rescue_status is required")
    return episode


def _payload_episodes(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    schema = payload.get("schema")
    if schema == P05_EPISODE_EXPORT_SCHEMA:
        records = payload.get("records")
    elif schema in P05_BUNDLE_SCHEMAS:
        records = payload.get("episodes")
    elif schema == V23_P05_EPISODE_SCHEMA:
        records = [payload]
    elif schema in P05_PAIR_SCHEMAS:
        raise V23Error("pair-only artifact is incomplete without ACUTE_RP0 records")
    else:
        raise V23Error("P0.5 input must use a registered producer, bundle, or raw episode schema")
    if not isinstance(records, list) or any(not isinstance(record, Mapping) for record in records):
        raise V23Error("P0.5 episode records must be a list of objects")
    return list(records)


def _validate_episode_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    episodes = _payload_episodes(payload)
    mode_records: dict[str, list[Mapping[str, Any]]] = {mode: [] for mode in V23_P05_MODES}
    for episode in episodes:
        validated = _validate_episode(episode)
        mode_records[validated["mode"]].append(validated)
    if any(len(mode_records[mode]) != 16 for mode in V23_P05_MODES):
        raise V23Error("certificate requires exactly 16 records for each registered mode")
    grouped: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = {}
    provenance: dict[tuple[Any, ...], dict[str, tuple[int, int]]] = {}
    for mode in V23_P05_MODES:
        env_ids = []
        for episode in mode_records[mode]:
            rows = episode["step_rows"]
            env_ids.append(rows[0]["env_id"])
            key = _group_key(episode)
            if key in grouped and mode in grouped[key]:
                raise V23Error(f"duplicate {mode} experimental identity")
            grouped.setdefault(key, {})[mode] = episode
            provenance.setdefault(key, {})[mode] = _episode_provenance(episode)
        if sorted(env_ids) != list(range(16)) or len(set(env_ids)) != 16:
            raise V23Error(f"{mode} env ids must be exactly 0..15 once each")
    if len(grouped) != 16 or any(set(group) != set(V23_P05_MODES) for group in grouped.values()):
        raise V23Error("FULL, ACUTE_RP0, and rescue identity sets must match exactly")
    groups = []
    for key in sorted(grouped, key=str):
        mode_group = grouped[key]
        env_id, episode_index = provenance[key]["FULL"]
        for mode in V23_P05_MODES[1:]:
            if provenance[key][mode] != (env_id, episode_index):
                raise V23Error(
                    "FULL, ACUTE_RP0, and rescue records must share exact env_id and episode_index"
                )
        groups.append(
            {
                "identity": _identity(mode_group["FULL"], label="group"),
                "plain_prefix_id": mode_group["FULL"]["plain_prefix_id"],
                "env_id": env_id,
                "episode_index": episode_index,
                "modes": mode_group,
            }
        )
    group_env_ids = [group["env_id"] for group in groups]
    if sorted(group_env_ids) != list(range(16)) or len(set(group_env_ids)) != 16:
        raise V23Error("cross-mode groups must cover env ids exactly 0..15 once each")
    source_records = payload.get("source_records")
    if source_records is not None:
        if not isinstance(source_records, Mapping) or set(source_records) != set(V23_P05_MODES):
            raise V23Error("source_records must preserve all three registered mode lists")
        flattened = []
        for mode in V23_P05_MODES:
            values = source_records[mode]
            if not isinstance(values, list) or len(values) != 16 or any(not isinstance(value, Mapping) for value in values):
                raise V23Error(f"source_records.{mode} must contain exactly 16 objects")
            flattened.extend(values)
        if sorted(flattened, key=lambda item: str(_group_key(item))) != sorted(episodes, key=lambda item: str(_group_key(item))):
            raise V23Error("source_records do not equal the validated episode records")
    if payload.get("pair") is not None:
        raise V23Error("legacy singular pair field is not admitted")
    for key in ("aggregate", "metrics", "prefix_equal", "clipped_effort_ratios"):
        if key in payload:
            raise V23Error(f"legacy aggregate field {key!r} is not admitted")
    return groups


def _recomputed_windows(episode: Mapping[str, Any], bands: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = episode["step_rows"]
    end_step = rows[-1]["control_step"]
    supplied_by_length: dict[int, Mapping[str, Any]] = {}
    for window in _record_windows(episode):
        length = window.get("window_steps")
        if isinstance(length, bool) or not isinstance(length, int) or length in supplied_by_length:
            raise V23Error("episode window_rows must contain unique integer lengths")
        supplied_by_length[length] = window
    expected_lengths = {
        length
        for length in range(bands["low_progress_window_min_steps"], bands["low_progress_window_max_steps"] + 1)
        if end_step - length + 1 >= 0
    }
    if set(supplied_by_length) != expected_lengths:
        raise V23Error("episode window_rows must cover every complete configured length exactly")
    result = []
    for length in sorted(expected_lengths):
        recomputed = a2_v23_build_p05_window_record(
            rows,
            start_step=end_step - length + 1,
            end_step=end_step,
            window_id=f"recomputed-{episode['mode']}-{length}",
        )
        supplied = supplied_by_length[length]
        for field in (
            "start_step", "end_step", "window_steps", "mode", "plain_prefix_id",
            "clipped_utilization_min", "stable_grasp_streak_max", "stable_grasp_all_rows",
            "hinge_position_start_rad", "hinge_position_end_rad", "progress_rad",
            "clipped_window_fraction", "clipped_utilization_max", "failure_flags", "rescue_status",
        ):
            if supplied.get(field) != recomputed.get(field):
                raise V23Error(f"{episode['mode']} supplied window disagrees with raw rows: {field}")
        result.append(recomputed)
    return result


def _window_condition(window: Mapping[str, Any], bands: Mapping[str, Any]) -> dict[str, Any]:
    failures = window.get("failure_flags")
    if (
        not isinstance(failures, Mapping)
        or set(failures) != set(V23_P05_FAILURE_FLAGS)
        or any(not isinstance(failures[flag], bool) for flag in V23_P05_FAILURE_FLAGS)
    ):
        raise V23Error("window failure_flags are malformed")
    threshold = finite_number(window.get("clipped_utilization_min"), name="window.clipped_utilization_min")
    if threshold != bands["clipped_utilization_min"]:
        raise V23Error("window selected utilization threshold disagrees with bands")
    stable_ok = (
        window.get("stable_grasp_all_rows") is True
        and window.get("stable_grasp_streak_max", 0) >= bands["stable_grasp_min_steps"]
    )
    low_ok = (
        bands["low_progress_window_min_steps"] <= window["window_steps"] <= bands["low_progress_window_max_steps"]
        and bands["low_progress_min_rad"]
        <= finite_number(window["progress_rad"], name="window.progress_rad")
        <= bands["low_progress_max_rad"]
    )
    effort_ok = (
        finite_number(window["clipped_window_fraction"], name="window.clipped_window_fraction")
        >= bands["clipped_fraction_min"]
        and finite_number(window["clipped_utilization_max"], name="window.clipped_utilization_max")
        >= bands["clipped_utilization_min"]
    )
    failure_ok = not any(failures.values())
    return {
        "status": "PASS" if stable_ok and low_ok and effort_ok and failure_ok else "FAIL",
        "window_id": window.get("window_id"),
        "window_steps": window["window_steps"],
        "progress_rad": window["progress_rad"],
        "stable_grasp_streak_max": window["stable_grasp_streak_max"],
        "stable_grasp_all_rows": window["stable_grasp_all_rows"],
        "clipped_utilization_min": threshold,
        "clipped_window_fraction": window["clipped_window_fraction"],
        "clipped_utilization_max": window["clipped_utilization_max"],
        "failure_flags": dict(failures),
        "predicate_flags": {
            "stable_grasp": stable_ok,
            "low_progress": low_ok,
            "high_effort": effort_ok,
            "failure_exclusion": failure_ok,
        },
    }


def _first_passing_window(windows: Sequence[Mapping[str, Any]], bands: Mapping[str, Any]) -> dict[str, Any] | None:
    for window in windows:
        result = _window_condition(window, bands)
        if result["status"] == "PASS":
            return result
    return None


def _rescue_progress(episode: Mapping[str, Any], bands: Mapping[str, Any]) -> dict[str, Any]:
    status = episode.get("rescue_status")
    if status == V23_P05_RESCUE_NOT_APPLICABLE_BASELINE_AT_MAX:
        return {"status": "RESCUE_NOT_EXECUTED", "reason": V23_P05_RESCUE_NOT_APPLICABLE_BASELINE_AT_MAX}
    if status != "APPLIED":
        return {"status": "RESCUE_NOT_EXECUTED", "reason": status or "MISSING_RESCUE_STATUS"}
    switch_step = episode.get("switch_step")
    if isinstance(switch_step, bool) or not isinstance(switch_step, int) or switch_step < 0:
        raise V23Error("APPLIED rescue requires a non-negative switch_step")
    by_step = {row["control_step"]: row for row in episode["step_rows"]}
    candidates = []
    for length in range(bands["low_progress_window_min_steps"], bands["low_progress_window_max_steps"] + 1):
        selected = [by_step.get(step) for step in range(switch_step, switch_step + length)]
        if any(row is None for row in selected):
            continue
        progress = finite_number(selected[-1]["hinge_position_rad"], name="rescue raw end hinge") - finite_number(selected[0]["hinge_position_rad"], name="rescue raw start hinge")
        candidates.append((length, progress))
    if not candidates:
        return {"status": "NOT_AVAILABLE", "reason": "NO_POST_SWITCH_PROGRESS_WINDOW"}
    in_band = [item for item in candidates if bands["rescue_progress_min_rad"] <= item[1] <= bands["rescue_progress_max_rad"]]
    selected_length, observed = in_band[0] if in_band else candidates[0]
    return {
        "status": "PASS" if bands["rescue_progress_min_rad"] <= observed <= bands["rescue_progress_max_rad"] else "FAIL",
        "observed_progress_rad": observed,
        "window_steps": selected_length,
        "band": [bands["rescue_progress_min_rad"], bands["rescue_progress_max_rad"]],
    }


def _evaluate_group(group: Mapping[str, Any], bands: Mapping[str, Any]) -> dict[str, Any]:
    modes = group["modes"]
    windows = {mode: _recomputed_windows(modes[mode], bands) for mode in V23_P05_MODES}
    full_window = _first_passing_window(windows["FULL"], bands)
    acute_window = _first_passing_window(windows["ACUTE_RP0"], bands)
    rescue_result = _rescue_progress(modes["HIGHER_EFFORT_RESCUE"], bands)
    try:
        pair = a2_v23_validate_p05_prefix(modes["FULL"], modes["HIGHER_EFFORT_RESCUE"])
        pair["env_id"] = group["env_id"]
        pair["episode_index"] = group["episode_index"]
        pair["plain_prefix_id"] = group["plain_prefix_id"]
        pair["status"] = "NO_RESCUE_LATCH" if pair.get("pair_status") == "NO_RESCUE_LATCH" else "PASS"
    except (ValueError, KeyError) as exc:
        pair = {"status": "FAIL", "reason": str(exc), "prefix_equal": False}
    qualified = (
        full_window is not None
        and acute_window is not None
        and rescue_result.get("status") == "PASS"
        and pair.get("prefix_equal") is True
    )
    conditions = {
        "stable_grasp": {"status": "PASS" if qualified else "FAIL", "full_window": full_window, "acute_rp0_window": acute_window},
        "low_progress": {"status": "PASS" if qualified else "FAIL", "band_rad": [bands["low_progress_min_rad"], bands["low_progress_max_rad"]]},
        "high_effort": {"status": "PASS" if qualified else "FAIL", "authority": "CLIPPED_COMMAND_TORQUE", "ratio_minimum": bands["clipped_utilization_min"], "window_fraction_minimum": bands["clipped_fraction_min"]},
        "rescue_progress": rescue_result,
        "failure_exclusion": {"status": "PASS" if qualified else "FAIL", "excluded_failure_types": list(V23_P05_FAILURE_FLAGS)},
        "same_forward_prefix": pair,
    }
    if qualified:
        status = "PASS"
    elif rescue_result.get("status") == "RESCUE_NOT_EXECUTED":
        status = "RESCUE_NOT_EXECUTED"
    elif windows["FULL"] and windows["ACUTE_RP0"]:
        status = "COMPLETED_TYPED_NEGATIVE"
    else:
        status = "PENDING"
    return {
        "identity": dict(group["identity"]),
        "plain_prefix_id": group["plain_prefix_id"],
        "env_id": group["env_id"],
        "episode_index": group["episode_index"],
        "status": status,
        "formal_admission": status == "PASS",
        "conditions": conditions,
    }


def _validate_bundle_metadata(
    payload: Mapping[str, Any],
    groups: Sequence[Mapping[str, Any]],
    evaluations: Sequence[Mapping[str, Any]],
) -> None:
    groups_metadata = payload.get("groups")
    if payload.get("schema") in P05_BUNDLE_SCHEMAS:
        if not isinstance(groups_metadata, list):
            raise V23Error("registered bundle requires exact groups metadata")
    if groups_metadata is not None:
        if not isinstance(groups_metadata, list) or len(groups_metadata) != len(groups):
            raise V23Error("bundle groups do not match validated identity groups")
        expected_groups = [
            {
                "identity": {
                    **dict(group["identity"]),
                    "plain_prefix_id": group["plain_prefix_id"],
                    "checkpoint_load_mode": group["modes"]["FULL"]["checkpoint_load_mode"],
                    "cell_id": group["modes"]["FULL"]["cell_id"],
                    "geometry_id": group["modes"]["FULL"]["geometry_id"],
                },
                "plain_prefix_id": group["plain_prefix_id"],
                "env_id": group["env_id"],
                "episode_index": group["episode_index"],
                "modes": {mode: group["modes"][mode] for mode in V23_P05_MODES},
            }
            for group in groups
        ]
        if groups_metadata != expected_groups:
            raise V23Error("bundle groups metadata disagrees with recomputed source records")

    pairs = payload.get("pairs")
    if pairs is not None:
        if not isinstance(pairs, list) or len(pairs) != len(groups):
            raise V23Error("pairs must contain one result per identity group")
        expected = {
            tuple(item["identity"][field] for field in ("checkpoint", "config", "scenario", "topology", "seed", "episode_id"))
            + (item["plain_prefix_id"],): {
                **item["conditions"]["same_forward_prefix"],
                "plain_prefix_id": item["plain_prefix_id"],
                "env_id": item["env_id"],
                "episode_index": item["episode_index"],
            }
            for item in evaluations
        }
        actual = set()
        for pair in pairs:
            if not isinstance(pair, Mapping):
                raise V23Error("external pair claims are not admitted")
            if pair.get("pair_status") == "NO_RESCUE_LATCH":
                if (
                    pair.get("prefix_equal") is not None
                    or pair.get("prefix_row_count") != 0
                    or pair.get("rescue_status") != "NOT_APPLICABLE_NO_SWITCH"
                    or pair.get("qualification_status") != "NONQUALIFYING"
                    or pair.get("reason") != "NO_VALID_RESCUE_LATCH"
                ):
                    raise V23Error("external no-latch pair does not preserve the typed terminal contract")
            elif pair.get("prefix_equal") is not True:
                raise V23Error("external pair claims are not admitted")
            identity = pair.get("identity")
            if not isinstance(identity, Mapping):
                raise V23Error("external pair identity is missing")
            key = tuple(identity.get(field) for field in ("checkpoint", "config", "scenario", "topology", "seed", "episode_id")) + (
                pair.get("plain_prefix_id"),
            )
            if key in actual or key not in expected:
                raise V23Error("external pair identity set does not match recomputed groups")
            recomputed = expected[key]
            for field in (
                "plain_prefix_id",
                "env_id",
                "episode_index",
                "prefix_row_count",
                "rescue_status",
                "prefix_equal",
                "pair_status",
                "qualification_status",
                "reason",
            ):
                if pair.get(field) != recomputed.get(field):
                    raise V23Error("external pair result disagrees with raw prefix recomputation")
            actual.add(key)
        if actual != set(expected):
            raise V23Error("external pair identity set does not match recomputed groups")


def evaluate_probe_artifacts(payload: Mapping[str, Any], *, bands: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate all complete 16-env FULL/ACUTE/rescue identity groups."""

    if not isinstance(payload, Mapping):
        raise V23Error("P0.5 producer artifact must be an object")
    selected_bands = a2_v23_validate_p05_bands(bands)
    groups = _validate_episode_records(payload)
    evaluations = [_evaluate_group(group, selected_bands) for group in groups]
    _validate_bundle_metadata(payload, groups, evaluations)
    pass_count = sum(item["status"] == "PASS" for item in evaluations)
    terminal_statuses = {"PASS", "COMPLETED_TYPED_NEGATIVE", "RESCUE_NOT_EXECUTED"}
    completion_terminal = all(item["status"] in terminal_statuses for item in evaluations)
    status = ("PASS" if pass_count else "COMPLETED_TYPED_NEGATIVE") if completion_terminal else "PENDING"
    return {
        "schema": "a2_piper_v23_feasibility_certificate_evaluation_v4",
        "status": status,
        "formal_admission": pass_count > 0,
        "completion_terminal": completion_terminal,
        "identity_count": len(evaluations),
        "pass_count": pass_count,
        "bands": selected_bands,
        "modes_present": {mode: 16 for mode in V23_P05_MODES},
        "per_identity_evaluations": evaluations,
        "state_clone_supported": False,
        "source": "actual_p05_producer_records_only",
    }


def build_certificate(metrics: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a pending certificate or evaluate only registered raw artifacts."""

    evaluated = None
    if metrics is not None:
        if not isinstance(metrics, Mapping):
            raise V23Error("certificate input must be an object")
        schema = metrics.get("schema")
        accepted = {P05_EPISODE_EXPORT_SCHEMA, V23_P05_EPISODE_SCHEMA, *P05_BUNDLE_SCHEMAS}
        if schema in P05_PAIR_SCHEMAS:
            raise V23Error("pair-only artifact cannot produce a certificate without ACUTE_RP0")
        if schema not in accepted:
            raise V23Error("legacy/untyped aggregate certificate input is not admitted")
        bands = metrics.get("bands")
        if isinstance(bands, Mapping) and isinstance(bands.get("values"), Mapping):
            bands = bands["values"]
        if not isinstance(bands, Mapping):
            raise V23Error("registered producer certificate requires explicit bands")
        evaluated = evaluate_probe_artifacts(metrics, bands=bands)
    return artifact_payload(
        "feasibility_certificate",
        status="NOT_RUN_PENDING" if metrics is None else evaluated["status"],
        authority="CLIPPED_COMMAND_TORQUE",
        evaluation=evaluated,
        confirmed_e2_training_samples=False,
        p0_numeric_state="PENDING_UNTIL_MEASURED",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--full-input", type=Path, default=None)
    parser.add_argument("--acute-input", type=Path, default=None)
    parser.add_argument("--rescue-input", type=Path, default=None)
    parser.add_argument("--bands", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    three_inputs = (args.full_input, args.acute_input, args.rescue_input)
    if any(path is not None for path in three_inputs):
        if args.input is not None or any(path is None for path in three_inputs):
            raise V23Error("three-file certificate mode requires exactly FULL, ACUTE_RP0, and rescue inputs")
        from scriptsFORhuman.v23.p0_rescue_probe import build_three_mode_bundle

        bands = read_json(args.bands) if args.bands is not None else None
        metrics = build_three_mode_bundle(
            read_json(args.full_input),
            read_json(args.acute_input),
            read_json(args.rescue_input),
            bands=bands,
        )
    elif args.input is not None:
        if args.input.is_dir():
            bundle_path = args.input / "a2_v23_p05_bundle.json"
            if not bundle_path.is_file():
                raise V23Error("certificate directory must contain an explicit complete three-mode bundle")
            metrics = read_json(bundle_path)
        else:
            metrics = read_json(args.input)
        if args.bands is not None:
            metrics["bands"] = read_json(args.bands)
    else:
        metrics = None
    emit_payload(build_certificate(metrics), args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 FEASIBILITY CERTIFICATE FAIL: {exc}")
