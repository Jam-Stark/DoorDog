"""P0.2 effort-ladder preparation and selection logic.

The ladder is intentionally a pure-data tool.  It records the six registered
rungs and can classify caller-supplied observations, but it never invents a
selected effort profile when measurements are absent.  Historical v21B
canonical/heavy16 material is retained as prior context only.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from gr00t.rl.envs.door.a2_v23_evidence import (
    V23_TEMPORAL_EPISODE_SCHEMA,
    V23_TEMPORAL_EXPORT_SCHEMA,
    V23_TEMPORAL_STEP_SCHEMA,
    V23_TEMPORAL_PROGRESS_THRESHOLD_RAD,
    a2_v23_select_temporal_window,
    a2_v23_temporal_window_metrics,
)

from ._v23_common import (
    REPO_ROOT,
    V23_EFFORT_RUNGS,
    V23Error,
    artifact_payload,
    emit_payload,
    finite_number,
    read_json,
)


PRIOR_EVIDENCE = (
    {
        "kind": "canonical16",
        "path": "logs_eval/base_v21B/preformal_20260802_r10/V21B_CENSUS_PLAN.json",
        "role": "prior_only",
    },
    {
        "kind": "heavy16",
        "path": "logs_eval/base_v21B/preformal_20260802_r10/V21B_HEAVY16_MANIFEST.json",
        "role": "prior_only",
    },
    {
        "kind": "census_summary",
        "path": "logs_eval/base_v21B/preformal_20260802_r10/V21B_CENSUS_PRE_MATERIALIZATION.json",
        "role": "prior_only",
    },
)

DECISION_FLAGS = (
    "meaningful_clipped_saturation",
    "e0_not_collapsed",
    "heavy_door_deteriorates_first",
    "pd_oscillation_absent",
)
EFFORT_FREEZE_SCHEMA = "a2_piper_v23_effort_freeze_v1"
EFFORT_FREEZE_SELECTION_OUTCOMES = (
    "NORMAL_BOUNDARY_SELECTED",
    "LADDER_INCONCLUSIVE",
    "F2_100_SELECTED",
)
EFFORT_FREEZE_PROVENANCE_FIELDS = (
    "checkpoint",
    "config",
    "scenario",
    "topology",
    "seed",
    "plain_prefix_id",
    "env_id",
    "episode_index",
    "episode_id",
    "effort_nm",
    "checkpoint_load_mode",
)

MATERIALIZER_TOPOLOGIES = ("canonical16", "heavy16")
MATERIALIZER_FILES = {
    "manifest": "v23_p0_plain_scenario_manifest.json",
    "metrics": "metrics_eval.json",
    "per_env": "a2_v14_per_env_records.json",
    "terminal_torque": "a2_v23_p0_torque_terminal_records.json",
    "effort_observation": "a2_v23_p0_effort_observations.json",
}
MATERIALIZER_FLAG_REASONS = {
    "meaningful_clipped_saturation": (
        "requires an approved E0 predicate and temporal telemetry; aggregate materialization does not infer it"
    ),
    "e0_not_collapsed": "the E0 predicate is not supplied by these artifacts",
    "heavy_door_deteriorates_first": (
        "requires an approved topology-ordering predicate; canonical16 and heavy16 remain separate"
    ),
    "pd_oscillation_absent": "requires temporal oscillation telemetry and an approved predicate",
}
TERMINAL_SUMMARY_FIELDS = (
    "nominal_pd_torque_abs_mean",
    "nominal_pd_torque_abs_max",
    "clipped_command_torque_abs_max",
    "arm_joint_position_error_abs_mean_6d",
    "arm_joint_position_error_abs_max_6d",
    "arm_joint_velocity_abs_mean_6d",
    "arm_joint_velocity_abs_max_6d",
)

MATERIALIZER_JOINT_NAMES = (
    "arm_j1",
    "arm_j2",
    "arm_j3",
    "arm_j4",
    "arm_j5",
    "arm_j6",
)
MATERIALIZER_VECTOR_FIELDS = (
    "nominal_pd_torque_abs_mean",
    "nominal_pd_torque_abs_max",
    "clipped_command_torque_abs_max",
    "estimated_saturation_fraction",
    "isaaclab_computed_torque_estimate_abs_max",
    "isaaclab_applied_torque_estimate_abs_max",
    "arm_joint_position_error_abs_mean_6d",
    "arm_joint_position_error_abs_max_6d",
    "arm_joint_velocity_abs_mean_6d",
    "arm_joint_velocity_abs_max_6d",
    "last_nominal_pd_torque_estimate",
    "last_clipped_command_torque_estimate",
    "last_isaaclab_computed_torque_estimate",
    "last_isaaclab_applied_torque_estimate",
    "last_arm_joint_position_error_6d",
    "last_arm_joint_velocity_6d",
)
MATERIALIZER_AUTHORITY_FIELDS = (
    "authority_nominal_pd",
    "authority_clipped_command",
    "isaaclab_torque_source_authority",
)
MATERIALIZER_AUTHORITY_VALUES = {
    "authority_nominal_pd": "ESTIMATE_ONLY/NOMINAL_PD",
    "authority_clipped_command": "ESTIMATE_ONLY/CLIPPED_COMMAND_TORQUE",
    "isaaclab_torque_source_authority": "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE",
}
MATERIALIZER_OBSERVATION_AUTHORITY = "ESTIMATE_ONLY; max_over_terminal_envs_and_arm_joints"
MATERIALIZER_TERMINAL_IDENTITY_CONTRACT = {
    "episode_id_authority": "EVALUATOR_ASSIGNED_ENV_EPISODE_ID",
    "fields": ["env_id", "episode_index", "episode_id"],
}
MATERIALIZER_TRACKING_ERROR_CONTRACT = {
    "aggregation": "per-joint mean/max over valid terminal frames",
    "formula": "v21B: joint_pos_target - joint_pos",
    "position_error_field": "arm_joint_position_error_6d",
    "velocity_field": "arm_joint_velocity_6d",
}
MATERIALIZER_AGGREGATION_CONTRACT = {
    "operator": "max",
    "scope": "terminal_envs_and_six_arm_joints",
    "tracking_error_formula": MATERIALIZER_TRACKING_ERROR_CONTRACT["formula"],
}
MATERIALIZER_PARAMETER_TOLERANCE = 1e-5
MATERIALIZER_REWARD_TOLERANCE = 1e-3


def _input_rows(payload: Mapping[str, Any]) -> dict[float, Mapping[str, Any]]:
    rows = payload.get("rows", payload.get("rungs", []))
    if not isinstance(rows, list):
        raise V23Error("effort observations must contain a list under rows or rungs")
    result: dict[float, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise V23Error("each effort observation must be an object")
        if "effort_nm" not in row:
            raise V23Error("each effort observation requires effort_nm")
        effort = finite_number(row["effort_nm"], name="effort_nm")
        if effort not in V23_EFFORT_RUNGS:
            raise V23Error(f"effort observation uses an unregistered rung: {effort}")
        if effort in result:
            raise V23Error(f"duplicate effort observation for rung {effort}")
        result[effort] = row
    return result


def _classify(effort: float, row: Mapping[str, Any] | None) -> dict[str, Any]:
    base = {
        "effort_nm": effort,
        "status": "NOT_RUN",
        "decision_flags": {name: "PENDING" for name in DECISION_FLAGS},
        "nominal_clipped_tracking": {
            "nominal_pd_torque": "PENDING",
            "clipped_command_torque": "PENDING",
            "tracking_error": "PENDING",
            "authority": "P0_MEASURED_REQUIRED",
        },
    }
    if row is None:
        return base

    flags = row.get("decision_flags")
    if not isinstance(flags, Mapping):
        flags = {name: row.get(name, "PENDING") for name in DECISION_FLAGS}
    normalized: dict[str, Any] = {}
    for name in DECISION_FLAGS:
        value = flags.get(name, "PENDING")
        if value not in (True, False, "PENDING"):
            raise V23Error(f"{name} must be true, false, or PENDING")
        normalized[name] = value
    base["decision_flags"] = normalized

    evidence = row.get("nominal_clipped_tracking", {})
    if evidence and not isinstance(evidence, Mapping):
        raise V23Error("nominal_clipped_tracking must be an object")
    for field in ("nominal_pd_torque", "clipped_command_torque", "tracking_error"):
        value = evidence.get(field, row.get(field, "PENDING"))
        if value != "PENDING":
            finite_number(value, name=field)
        base["nominal_clipped_tracking"][field] = value

    values = list(normalized.values())
    if all(value is True for value in values):
        base["status"] = "ELIGIBLE_BOUNDARY_CANDIDATE"
    elif any(value is False for value in values):
        base["status"] = "REJECTED_BY_BEHAVIOR_FLAGS"
    else:
        base["status"] = "PENDING_INCOMPLETE_OBSERVATION"
    return base


def _materializer_json(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise V23Error(f"{label} is not a regular file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V23Error(f"invalid JSON for {label}: {path}") from exc


def _materializer_object(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V23Error(f"{name} must be an object")
    return value


def _materializer_numeric_list(value: Any, *, name: str, length: int | None = None) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, list):
        raise V23Error(f"{name} must be a numeric list")
    if length is not None and len(value) != length:
        raise V23Error(f"{name} must contain {length} values; got {len(value)}")
    return [finite_number(item, name=f"{name}[{index}]") for index, item in enumerate(value)]


def _materializer_range(values: Sequence[float], *, name: str) -> dict[str, Any]:
    if not values:
        raise V23Error(f"{name} cannot be empty")
    return {"min": min(values), "max": max(values), "count": len(values)}


def _materializer_distribution(values: Sequence[Any], *, name: str) -> dict[str, int]:
    if not values:
        raise V23Error(f"{name} cannot be empty")
    counts = Counter(str(value) for value in values)
    return {key: counts[key] for key in sorted(counts)}


def _materializer_close(left: Any, right: Any, *, name: str, tolerance: float = MATERIALIZER_PARAMETER_TOLERANCE) -> None:
    left_value = finite_number(left, name=f"{name}.left")
    right_value = finite_number(right, name=f"{name}.right")
    if not math.isclose(left_value, right_value, rel_tol=0.0, abs_tol=tolerance):
        raise V23Error(f"{name} disagrees: {left_value!r} != {right_value!r}")


def _materializer_integer(value: Any, *, name: str, minimum: int = 0) -> int:
    result = finite_number(value, name=name)
    if not result.is_integer() or result < minimum:
        raise V23Error(f"{name} must be an integer >= {minimum}")
    return int(result)


def _materializer_params(
    item: Mapping[str, Any],
    *,
    weight_key: str,
    handle_key: str,
    hinge_key: str,
    path: str,
) -> dict[str, float]:
    return {
        "door_weight_kg": finite_number(item.get(weight_key), name=f"{path}.{weight_key}"),
        "handle_height_m": finite_number(item.get(handle_key), name=f"{path}.{handle_key}"),
        "hinge_force_nm": finite_number(item.get(hinge_key), name=f"{path}.{hinge_key}"),
    }


def _materializer_find_manifest_record(
    records: Sequence[Mapping[str, Any]],
    params: Mapping[str, float],
    *,
    label: str,
) -> Mapping[str, Any]:
    matches = []
    for record in records:
        candidate = record["params"]
        if all(
            math.isclose(params[field], candidate[field], rel_tol=0.0, abs_tol=MATERIALIZER_PARAMETER_TOLERANCE)
            for field in ("door_weight_kg", "handle_height_m", "hinge_force_nm")
        ):
            matches.append(record)
    if len(matches) != 1:
        raise V23Error(f"{label} must match exactly one manifest scenario; matches={len(matches)}")
    return matches[0]


def _validate_materializer_manifest(payload: Any, *, topology: str, path: Path) -> dict[str, Any]:
    manifest = _materializer_object(payload, name=f"{path}.manifest")
    if manifest.get("schema") != "a2_piper_base_v23_p0_plain_scenario_manifest_v1":
        raise V23Error(f"manifest schema mismatch: {path}")
    if manifest.get("status") != "STATIC_PLAIN" or manifest.get("topology") != topology:
        raise V23Error(f"manifest status/topology mismatch: {path}")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != 16:
        raise V23Error(f"{topology} manifest must contain exactly 16 rows: {path}")
    scenario_ids = []
    scenario_records = []
    weights = []
    handles = []
    hinges = []
    for index, row in enumerate(rows):
        item = _materializer_object(row, name=f"{path}.rows[{index}]")
        scenario_id = item.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise V23Error(f"{path}.rows[{index}] has no scenario_id")
        if scenario_id in scenario_ids:
            raise V23Error(f"{path}.rows[{index}] duplicates scenario_id {scenario_id!r}")
        params = _materializer_params(
            item,
            weight_key="door_weight_kg",
            handle_key="handle_height_m",
            hinge_key="hinge_force_nm",
            path=f"{path}.rows[{index}]",
        )
        if any(
            all(
                math.isclose(params[field], previous["params"][field], rel_tol=0.0, abs_tol=MATERIALIZER_PARAMETER_TOLERANCE)
                for field in params
            )
            for previous in scenario_records
        ):
            raise V23Error(f"{path}.rows[{index}] duplicates a scenario parameter tuple")
        scenario_ids.append(scenario_id)
        weights.append(params["door_weight_kg"])
        handles.append(params["handle_height_m"])
        hinges.append(params["hinge_force_nm"])
        scenario_records.append(
            {
                "scenario_id": scenario_id,
                "params": params,
                "source_index": index,
                "manifest_row": dict(item),
            }
        )
    return {
        "schema": manifest["schema"],
        "status": manifest["status"],
        "topology": topology,
        "row_count": 16,
        "scenario_ids": scenario_ids,
        "rows": [dict(row) for row in rows],
        "scenario_records": scenario_records,
        "ranges": {
            "door_weight_kg": _materializer_range(weights, name=f"{path}.door_weight_kg"),
            "handle_height_m": _materializer_range(handles, name=f"{path}.handle_height_m"),
            "hinge_force_nm": _materializer_range(hinges, name=f"{path}.hinge_force_nm"),
        },
    }


def _validate_materializer_metrics(payload: Any, *, path: Path) -> dict[str, Any]:
    metrics = _materializer_object(payload, name=f"{path}.metrics")
    required = (
        "episode_lengths",
        "episode_rewards",
        "episode_goal_reached",
        "episode_max_stage_reached",
        "episode_terminal_reasons",
        "episode_terminal_diagnostics",
        "goal_reached_buffer",
    )
    for field in required:
        if field not in metrics or not isinstance(metrics[field], list) or len(metrics[field]) != 16:
            raise V23Error(f"{path}.{field} must contain exactly 16 values")
    if metrics.get("completed_episodes") != 16:
        raise V23Error(f"{path}.completed_episodes must equal 16")
    lengths = [
        _materializer_integer(value, name=f"{path}.episode_lengths[{index}]")
        for index, value in enumerate(metrics["episode_lengths"])
    ]
    rewards = _materializer_numeric_list(metrics["episode_rewards"], name=f"{path}.episode_rewards", length=16)
    goals = metrics["episode_goal_reached"]
    goal_buffer = metrics["goal_reached_buffer"]
    if any(not isinstance(value, bool) for value in goals + goal_buffer):
        raise V23Error(f"{path} goal fields must contain booleans")
    if goals != goal_buffer:
        raise V23Error(f"{path} episode_goal_reached disagrees with goal_reached_buffer")
    max_stages = [
        _materializer_integer(value, name=f"{path}.episode_max_stage_reached[{index}]")
        for index, value in enumerate(metrics["episode_max_stage_reached"])
    ]
    reasons = metrics["episode_terminal_reasons"]
    if any(not isinstance(value, str) or not value for value in reasons):
        raise V23Error(f"{path}.episode_terminal_reasons must contain non-empty strings")
    diagnostic_rows = []
    diagnostic_by_env = {}
    for index, diagnostic in enumerate(metrics["episode_terminal_diagnostics"]):
        item = _materializer_object(diagnostic, name=f"{path}.episode_terminal_diagnostics[{index}]")
        env_id = item.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0 or env_id >= 16:
            raise V23Error(f"{path}.episode_terminal_diagnostics[{index}].env_id must be an integer in 0..15")
        if env_id in diagnostic_by_env:
            raise V23Error(f"{path}.episode_terminal_diagnostics duplicates env_id {env_id}")
        params = _materializer_params(
            item,
            weight_key="door_weight",
            handle_key="door_handle_height",
            hinge_key="door_hinge_drive_max_force",
            path=f"{path}.episode_terminal_diagnostics[{index}]",
        )
        duplicate_hinge = finite_number(
            item.get("door_hinge_drive_max_force_nm"),
            name=f"{path}.episode_terminal_diagnostics[{index}].door_hinge_drive_max_force_nm",
        )
        _materializer_close(
            params["hinge_force_nm"],
            duplicate_hinge,
            name=f"{path}.episode_terminal_diagnostics[{index}].hinge_force_nm",
        )
        reason = item.get("terminal_reasons")
        if not isinstance(reason, str) or not reason:
            raise V23Error(f"{path}.episode_terminal_diagnostics[{index}].terminal_reasons must be non-empty")
        stage = _materializer_integer(item.get("stage_buf"), name=f"{path}.episode_terminal_diagnostics[{index}].stage_buf")
        length = _materializer_integer(
            item.get("episode_length_buf"),
            name=f"{path}.episode_terminal_diagnostics[{index}].episode_length_buf",
        )
        reward_sums = _materializer_object(
            item.get("reward_episode_sums"),
            name=f"{path}.episode_terminal_diagnostics[{index}].reward_episode_sums",
        )
        reward_sum = 0.0
        for reward_name, reward_value in reward_sums.items():
            reward_sum += finite_number(
                reward_value,
                name=f"{path}.episode_terminal_diagnostics[{index}].reward_episode_sums.{reward_name}",
            )
        if reasons[index] != reason:
            raise V23Error(f"{path} metrics terminal reason disagrees with diagnostic index {index}")
        if max_stages[index] != stage:
            raise V23Error(f"{path} metrics max stage disagrees with diagnostic index {index}")
        if lengths[index] != length:
            raise V23Error(f"{path} metrics episode length disagrees with diagnostic index {index}")
        if not math.isclose(rewards[index], reward_sum, rel_tol=0.0, abs_tol=MATERIALIZER_REWARD_TOLERANCE):
            raise V23Error(f"{path} episode reward disagrees with diagnostic reward sum at index {index}")
        row = {
            "env_id": env_id,
            "source_index": index,
            "scenario_params": params,
            "goal_reached": goals[index],
            "terminal_reason": reason,
            "max_stage": stage,
            "episode_length": length,
            "episode_reward": rewards[index],
            "diagnostic_reward_sum": reward_sum,
        }
        diagnostic_rows.append(row)
        diagnostic_by_env[env_id] = row
    if sorted(diagnostic_by_env) != list(range(16)):
        raise V23Error(f"{path}.episode_terminal_diagnostics env_id values must cover 0..15 exactly")
    return {
        "completed_episodes": 16,
        "episode_lengths": lengths,
        "episode_rewards": rewards,
        "goal_reached_count": sum(goals),
        "goal_reached": list(goals),
        "terminal_reason_counts": _materializer_distribution(reasons, name=f"{path}.episode_terminal_reasons"),
        "max_stage_distribution": _materializer_distribution(max_stages, name=f"{path}.episode_max_stage_reached"),
        "diagnostic_rows": diagnostic_rows,
        "diagnostic_by_env": diagnostic_by_env,
    }


def _validate_materializer_per_env(payload: Any, *, path: Path) -> dict[str, Any]:
    if not isinstance(payload, list) or len(payload) != 16:
        raise V23Error(f"{path} must contain exactly 16 per-environment rows")
    rows = []
    by_env = {}
    goals = []
    max_stages = []
    weights = []
    hinges = []
    handles = []
    parameter_rows = []
    for index, row in enumerate(payload):
        item = _materializer_object(row, name=f"{path}[{index}]")
        env_id = item.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0 or env_id >= 16:
            raise V23Error(f"{path}[{index}].env_id must be an integer in 0..15")
        if env_id in by_env:
            raise V23Error(f"{path} duplicates env_id {env_id}")
        goal = item.get("goal_reached")
        if not isinstance(goal, bool):
            raise V23Error(f"{path}[{index}].goal_reached must be bool")
        goals.append(goal)
        max_stage = _materializer_integer(item.get("max_stage"), name=f"{path}[{index}].max_stage")
        final_stage = _materializer_integer(item.get("final_stage"), name=f"{path}[{index}].final_stage")
        params = _materializer_params(
            item,
            weight_key="door_weight",
            handle_key="door_handle_height",
            hinge_key="door_hinge_drive_max_force",
            path=f"{path}[{index}]",
        )
        max_stages.append(max_stage)
        weights.append(params["door_weight_kg"])
        hinges.append(params["hinge_force_nm"])
        handles.append(params["handle_height_m"])
        normalized = {
            "env_id": env_id,
            "source_index": index,
            "goal_reached": goal,
            "final_stage": final_stage,
            "max_stage": max_stage,
            "scenario_params": params,
        }
        rows.append(normalized)
        by_env[env_id] = normalized
        parameter_rows.append(params)
    if sorted(by_env) != list(range(16)):
        raise V23Error(f"{path} env_id values must cover 0..15 exactly")
    for index, params in enumerate(parameter_rows):
        if any(
            all(
                math.isclose(params[field], previous[field], rel_tol=0.0, abs_tol=MATERIALIZER_PARAMETER_TOLERANCE)
                for field in params
            )
            for previous in parameter_rows[:index]
        ):
            raise V23Error(f"{path}[{index}] duplicates a scenario parameter tuple")
    return {
        "row_count": 16,
        "rows": rows,
        "by_env": by_env,
        "goal_reached_count": sum(goals),
        "max_stage_distribution": _materializer_distribution(max_stages, name=f"{path}.max_stage"),
        "ranges": {
            "door_weight": _materializer_range(weights, name=f"{path}.door_weight"),
            "door_hinge_drive_max_force": _materializer_range(hinges, name=f"{path}.door_hinge_drive_max_force"),
            "door_handle_height": _materializer_range(handles, name=f"{path}.door_handle_height"),
        },
    }


def _validate_materializer_terminal(payload: Any, *, effort: float, path: Path) -> dict[str, Any]:
    terminal = _materializer_object(payload, name=f"{path}.terminal")
    if terminal.get("schema") != "a2_piper_base_v23_p0_torque_terminal_records_v1":
        raise V23Error(f"terminal torque schema mismatch: {path}")
    if finite_number(terminal.get("effort_nm"), name=f"{path}.effort_nm") != effort:
        raise V23Error(f"terminal torque effort disagrees with path: {path}")
    if terminal.get("terminal_identity_contract") != MATERIALIZER_TERMINAL_IDENTITY_CONTRACT:
        raise V23Error(f"{path}.terminal_identity_contract diverges from the identity contract")
    if terminal.get("tracking_error_contract") != MATERIALIZER_TRACKING_ERROR_CONTRACT:
        raise V23Error(f"{path}.tracking_error_contract diverges from the tracking contract")
    records = terminal.get("records")
    if not isinstance(records, list) or len(records) != 16:
        raise V23Error(f"{path}.records must contain exactly 16 terminal records")
    preserved_records = []
    records_by_env = {}
    saturation = []
    summaries = {field: [] for field in TERMINAL_SUMMARY_FIELDS}
    vector_summaries = {field: [] for field in MATERIALIZER_VECTOR_FIELDS}
    for index, record in enumerate(records):
        item = _materializer_object(record, name=f"{path}.records[{index}]")
        if item.get("schema") != "a2_piper_base_v23_torque_episode_v1":
            raise V23Error(f"{path}.records[{index}] schema mismatch")
        identity = _materializer_object(item.get("terminal_identity"), name=f"{path}.records[{index}].terminal_identity")
        env_id = identity.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0 or env_id >= 16:
            raise V23Error(f"{path}.records[{index}] terminal env_id must be in 0..15")
        if env_id in records_by_env:
            raise V23Error(f"{path}.records duplicates env_id {env_id}")
        episode_index = _materializer_integer(identity.get("episode_index"), name=f"{path}.records[{index}].episode_index")
        episode_id = identity.get("episode_id")
        expected_episode_id = f"a2-v23-eval-env{env_id}-episode{episode_index}"
        if episode_id != expected_episode_id:
            raise V23Error(f"{path}.records[{index}].episode_id does not match env/episode identity")
        if identity.get("authority") != MATERIALIZER_TERMINAL_IDENTITY_CONTRACT["episode_id_authority"]:
            raise V23Error(f"{path}.records[{index}] terminal identity authority diverges")
        valid_frames = _materializer_integer(item.get("valid_frame_count"), name=f"{path}.records[{index}].valid_frame_count")
        if list(item.get("joint_names", [])) != list(MATERIALIZER_JOINT_NAMES):
            raise V23Error(f"{path}.records[{index}].joint_names diverges from the six-joint order")
        if item.get("tracking_error_formula") != MATERIALIZER_TRACKING_ERROR_CONTRACT["formula"]:
            raise V23Error(f"{path}.records[{index}].tracking_error_formula diverges")
        if item.get("tracking_error_source_fields") != {"position_error": "joint_pos_target - joint_pos", "velocity": "joint_vel"}:
            raise V23Error(f"{path}.records[{index}].tracking_error_source_fields diverges")
        if item.get("evidence_state") != "TERMINAL_SNAPSHOT":
            raise V23Error(f"{path}.records[{index}].evidence_state must be TERMINAL_SNAPSHOT")
        for field, expected in MATERIALIZER_AUTHORITY_VALUES.items():
            if item.get(field) != expected:
                raise V23Error(f"{path}.records[{index}].{field} diverges from estimate-only authority")
        live_record = _materializer_object(item.get("live_record"), name=f"{path}.records[{index}].live_record")
        if live_record.get("schema") != item["schema"] or list(live_record.get("joint_names", [])) != list(MATERIALIZER_JOINT_NAMES):
            raise V23Error(f"{path}.records[{index}].live_record identity contract diverges")
        if live_record.get("tracking_error_formula") != MATERIALIZER_TRACKING_ERROR_CONTRACT["formula"]:
            raise V23Error(f"{path}.records[{index}].live_record tracking formula diverges")
        if live_record.get("tracking_error_source_fields") != {"position_error": "joint_pos_target - joint_pos", "velocity": "joint_vel"}:
            raise V23Error(f"{path}.records[{index}].live_record tracking source fields diverge")
        for field, expected in MATERIALIZER_AUTHORITY_VALUES.items():
            if live_record.get(field) != expected:
                raise V23Error(f"{path}.records[{index}].live_record.{field} diverges from estimate-only authority")
        for field in MATERIALIZER_VECTOR_FIELDS:
            values = _materializer_numeric_list(item.get(field), name=f"{path}.records[{index}].{field}", length=6)
            vector_summaries[field].append(values)
            if field == "estimated_saturation_fraction" and any(value < 0.0 or value > 1.0 for value in values):
                raise V23Error(f"{path}.records[{index}].estimated_saturation_fraction must be in [0,1]")
        for field in TERMINAL_SUMMARY_FIELDS:
            summaries[field].append(vector_summaries[field][-1])
        saturation.append(vector_summaries["estimated_saturation_fraction"][-1])
        preserved = dict(item)
        preserved["source_index"] = index
        preserved_records.append(preserved)
        records_by_env[env_id] = preserved
    if sorted(records_by_env) != list(range(16)):
        raise V23Error(f"{path} terminal records must cover env_id 0..15 exactly")
    aggregate = {
        "nominal_pd_torque": max(max(values) for values in vector_summaries["nominal_pd_torque_abs_max"]),
        "clipped_command_torque": max(max(values) for values in vector_summaries["clipped_command_torque_abs_max"]),
        "tracking_error": max(max(values) for values in vector_summaries["arm_joint_position_error_abs_max_6d"]),
    }
    return {
        "schema": terminal["schema"],
        "effort_nm": effort,
        "record_count": 16,
        "joint_names": list(MATERIALIZER_JOINT_NAMES),
        "terminal_identity_contract": dict(terminal["terminal_identity_contract"]),
        "tracking_error_contract": dict(terminal["tracking_error_contract"]),
        "authority_fields": dict(MATERIALIZER_AUTHORITY_VALUES),
        "records": preserved_records,
        "records_by_env": records_by_env,
        "saturation_fraction_distribution": saturation,
        "nominal_clipped_tracking_summaries": summaries,
        "aggregate_maxima": aggregate,
        "aggregation_contract": dict(MATERIALIZER_AGGREGATION_CONTRACT),
    }


def _validate_materializer_observation(
    payload: Any,
    *,
    effort: float,
    path: Path,
    terminal: Mapping[str, Any],
) -> dict[str, Any]:
    observation = _materializer_object(payload, name=f"{path}.effort_observation")
    if observation.get("schema") != "a2_piper_base_v23_p0_effort_observations_v1":
        raise V23Error(f"effort observation schema mismatch: {path}")
    rows = observation.get("rows")
    rungs = observation.get("rungs")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rungs, list) or len(rungs) != 1:
        raise V23Error(f"{path}.rows and {path}.rungs must each contain exactly one aggregate")
    row = _materializer_object(rows[0], name=f"{path}.rows[0]")
    rung = _materializer_object(rungs[0], name=f"{path}.rungs[0]")
    registered = _materializer_object(observation.get("registered_rung_observation"), name=f"{path}.registered_rung_observation")
    if row != rung or row != registered:
        raise V23Error(f"{path} rows/rungs/registered_rung_observation diverge")
    if finite_number(row.get("effort_nm"), name=f"{path}.rows[0].effort_nm") != effort:
        raise V23Error(f"effort observation rung disagrees with path: {path}")
    if row.get("status") != "OBSERVED":
        raise V23Error(f"{path}.rows[0] must have status OBSERVED")
    flags = _materializer_object(row.get("decision_flags"), name=f"{path}.rows[0].decision_flags")
    if set(flags) != set(DECISION_FLAGS) or any(flags[name] != "PENDING" for name in DECISION_FLAGS):
        raise V23Error(f"{path}.rows[0] contains a resolved decision flag; materialization remains pending")
    evidence = _materializer_object(row.get("nominal_clipped_tracking"), name=f"{path}.rows[0].nominal_clipped_tracking")
    for field in ("nominal_pd_torque", "clipped_command_torque", "tracking_error"):
        finite_number(evidence.get(field), name=f"{path}.rows[0].nominal_clipped_tracking.{field}")
    if evidence.get("authority") != MATERIALIZER_OBSERVATION_AUTHORITY:
        raise V23Error(f"{path}.rows[0].nominal_clipped_tracking.authority diverges from estimate-only aggregation")
    aggregation = _materializer_object(row.get("aggregation"), name=f"{path}.rows[0].aggregation")
    if aggregation != MATERIALIZER_AGGREGATION_CONTRACT:
        raise V23Error(f"{path}.rows[0].aggregation diverges from the aggregation contract")
    aggregate = terminal["aggregate_maxima"]
    for field in ("nominal_pd_torque", "clipped_command_torque", "tracking_error"):
        if finite_number(evidence[field], name=f"{path}.rows[0].nominal_clipped_tracking.{field}") != aggregate[field]:
            raise V23Error(f"{path}.rows[0].nominal_clipped_tracking.{field} disagrees with terminal maxima")
    return {
        "schema": observation["schema"],
        "status": "OBSERVED",
        "source": observation.get("source"),
        "prior_evidence": observation.get("prior_evidence"),
        "aggregate": dict(row),
        "rows": [dict(row)],
        "rungs": [dict(rung)],
        "registered_rung_observation": dict(registered),
        "nominal_clipped_tracking": dict(evidence),
        "aggregation": dict(aggregation),
        "aggregation_contract": dict(aggregation),
        "missing_metric_state": row.get("missing_metric_state"),
        "recomputed_terminal_maxima": dict(aggregate),
    }


def _validate_materializer_identity_join(
    manifest: Mapping[str, Any],
    metrics: Mapping[str, Any],
    per_env: Mapping[str, Any],
    terminal: Mapping[str, Any],
    *,
    path: Path,
) -> dict[str, Any]:
    manifest_records = manifest["scenario_records"]
    per_by_env = per_env["by_env"]
    diagnostic_by_env = metrics["diagnostic_by_env"]
    terminal_by_env = terminal["records_by_env"]
    if set(per_by_env) != set(diagnostic_by_env) or set(per_by_env) != set(terminal_by_env):
        raise V23Error(f"{path} identity join env sets diverge across per-env, terminal diagnostics, and torque records")
    joined_rows = []
    identity_keys = set()
    for env_id in sorted(per_by_env):
        per_row = per_by_env[env_id]
        diagnostic = diagnostic_by_env[env_id]
        terminal_record = terminal_by_env[env_id]
        per_params = per_row["scenario_params"]
        diagnostic_params = diagnostic["scenario_params"]
        for field in ("door_weight_kg", "handle_height_m", "hinge_force_nm"):
            _materializer_close(per_params[field], diagnostic_params[field], name=f"{path}.env{env_id}.{field}")
        scenario_record = _materializer_find_manifest_record(
            manifest_records,
            per_params,
            label=f"{path}.env{env_id}",
        )
        for field in ("door_weight_kg", "handle_height_m", "hinge_force_nm"):
            _materializer_close(
                per_params[field],
                scenario_record["params"][field],
                name=f"{path}.env{env_id}.{field}.manifest_join",
            )
            _materializer_close(
                diagnostic_params[field],
                scenario_record["params"][field],
                name=f"{path}.env{env_id}.{field}.diagnostic_manifest_join",
            )
        scenario_id = scenario_record["scenario_id"]
        identity_key = (env_id, scenario_id)
        if identity_key in identity_keys:
            raise V23Error(f"{path} duplicate joined identity {identity_key}")
        identity_keys.add(identity_key)
        if per_row["goal_reached"] != diagnostic["goal_reached"]:
            raise V23Error(f"{path}.{scenario_id}/env{env_id} goal mismatch after identity join")
        if per_row["max_stage"] != per_row["final_stage"] or per_row["max_stage"] != diagnostic["max_stage"]:
            raise V23Error(f"{path}.{scenario_id}/env{env_id} stage mismatch after identity join")
        if terminal_record["valid_frame_count"] != diagnostic["episode_length"]:
            raise V23Error(f"{path}.{scenario_id}/env{env_id} terminal frame count mismatches episode length")
        joined_rows.append(
            {
                "identity": {"env_id": env_id, "scenario_id": scenario_id},
                "source_indices": {
                    "manifest": scenario_record["source_index"],
                    "per_env": per_row["source_index"],
                    "terminal_diagnostic": diagnostic["source_index"],
                    "terminal_record": terminal_record["source_index"],
                },
                "manifest": {
                    "scenario_id": scenario_id,
                    "door_weight_kg": scenario_record["params"]["door_weight_kg"],
                    "handle_height_m": scenario_record["params"]["handle_height_m"],
                    "hinge_force_nm": scenario_record["params"]["hinge_force_nm"],
                },
                "per_env": {
                    "env_id": env_id,
                    "goal_reached": per_row["goal_reached"],
                    "final_stage": per_row["final_stage"],
                    "max_stage": per_row["max_stage"],
                    "scenario_params": dict(per_params),
                },
                "terminal_diagnostic": {
                    "env_id": env_id,
                    "goal_reached": diagnostic["goal_reached"],
                    "terminal_reason": diagnostic["terminal_reason"],
                    "max_stage": diagnostic["max_stage"],
                    "episode_length": diagnostic["episode_length"],
                    "scenario_params": dict(diagnostic_params),
                },
                "metrics": {
                    "goal_reached": diagnostic["goal_reached"],
                    "terminal_reason": diagnostic["terminal_reason"],
                    "max_stage": diagnostic["max_stage"],
                    "episode_length": diagnostic["episode_length"],
                    "episode_reward": diagnostic["episode_reward"],
                },
                "scenario_params": dict(scenario_record["params"]),
                "goal_reached": per_row["goal_reached"],
                "terminal_reason": diagnostic["terminal_reason"],
                "max_stage": per_row["max_stage"],
                "episode_length": diagnostic["episode_length"],
                "episode_reward": diagnostic["episode_reward"],
                "diagnostic_reward_sum": diagnostic["diagnostic_reward_sum"],
                "terminal_identity": {
                    "env_id": env_id,
                    "episode_index": terminal_record["terminal_identity"]["episode_index"],
                    "episode_id": terminal_record["terminal_identity"]["episode_id"],
                    "authority": terminal_record["terminal_identity"]["authority"],
                },
            }
        )
    if len(identity_keys) != 16:
        raise V23Error(f"{path} joined identity set must contain exactly 16 keys")
    joined_goal_count = sum(row["goal_reached"] for row in joined_rows)
    if joined_goal_count != metrics["goal_reached_count"] or joined_goal_count != per_env["goal_reached_count"]:
        raise V23Error(f"{path} goal totals disagree after identity joins")
    return {
        "join_key_fields": ["env_id", "scenario_id"],
        "row_count": 16,
        "source_order": {
            "manifest": [record["scenario_id"] for record in manifest_records],
            "per_env": [row["env_id"] for row in per_env["rows"]],
            "terminal_diagnostics": [row["env_id"] for row in metrics["diagnostic_rows"]],
            "terminal_records": [record["terminal_identity"]["env_id"] for record in terminal["records"]],
        },
        "rows": joined_rows,
        "goal_reached_count": joined_goal_count,
    }


def _materialize_runtime_root(root: Path) -> dict[str, Any]:
    if not root.is_absolute():
        raise V23Error(f"runtime materializer root must be absolute: {root}")
    if root.is_symlink() or not root.is_dir():
        raise V23Error(f"runtime materializer root is not a regular directory: {root}")
    if root.name == "torque":
        artifact_root = root
    else:
        artifact_root = root / "torque"
    if artifact_root.is_symlink() or not artifact_root.is_dir():
        raise V23Error(f"runtime materializer root must contain a regular torque artifact directory: {root}")
    expected_efforts = {f"effort_{effort:g}" for effort in V23_EFFORT_RUNGS}
    actual_efforts = {path.name for path in artifact_root.iterdir() if path.is_dir() and not path.is_symlink()}
    if actual_efforts != expected_efforts:
        raise V23Error(f"runtime torque effort directories mismatch: expected {sorted(expected_efforts)}, got {sorted(actual_efforts)}")

    cells = []
    rows = []
    for effort in V23_EFFORT_RUNGS:
        effort_dir = artifact_root / f"effort_{effort:g}"
        actual_topologies = {path.name for path in effort_dir.iterdir() if path.is_dir() and not path.is_symlink()}
        if actual_topologies != set(MATERIALIZER_TOPOLOGIES):
            raise V23Error(f"{effort_dir} topology directories must be canonical16 and heavy16")
        topology_cells = []
        for topology in MATERIALIZER_TOPOLOGIES:
            cell_dir = effort_dir / topology
            source_paths = {name: cell_dir / filename for name, filename in MATERIALIZER_FILES.items()}
            payloads = {
                name: _materializer_json(path, label=f"{effort:g}/{topology}/{name}")
                for name, path in source_paths.items()
            }
            manifest = _validate_materializer_manifest(payloads["manifest"], topology=topology, path=source_paths["manifest"])
            metrics = _validate_materializer_metrics(payloads["metrics"], path=source_paths["metrics"])
            per_env = _validate_materializer_per_env(payloads["per_env"], path=source_paths["per_env"])
            terminal = _validate_materializer_terminal(payloads["terminal_torque"], effort=effort, path=source_paths["terminal_torque"])
            observation = _validate_materializer_observation(
                payloads["effort_observation"],
                effort=effort,
                path=source_paths["effort_observation"],
                terminal=terminal,
            )
            identity_join = _validate_materializer_identity_join(
                manifest,
                metrics,
                per_env,
                terminal,
                path=cell_dir,
            )
            metrics_public = {key: value for key, value in metrics.items() if key != "diagnostic_by_env"}
            per_env_public = {key: value for key, value in per_env.items() if key != "by_env"}
            terminal_public = {key: value for key, value in terminal.items() if key != "records_by_env"}
            cell = {
                "cell_id": f"effort_{effort:g}/{topology}",
                "effort_nm": effort,
                "topology": topology,
                "status": "OBSERVED",
                "source_paths": {name: str(path) for name, path in source_paths.items()},
                "manifest": manifest,
                "metrics": metrics_public,
                "per_env": per_env_public,
                "terminal_torque": terminal_public,
                "effort_observation": observation,
                "identity_join": identity_join,
                "decision_flags": {
                    name: {"status": "PENDING", "reason": MATERIALIZER_FLAG_REASONS[name]}
                    for name in DECISION_FLAGS
                },
            }
            topology_cells.append(cell)
            cells.append(cell)
        if len(topology_cells) != len(MATERIALIZER_TOPOLOGIES):
            raise V23Error(f"effort_{effort:g} must contain exactly two topology subrecords")
        rows.append(
            {
                "effort_nm": effort,
                "status": "OBSERVED",
                "topologies": topology_cells,
                "topology_count": len(topology_cells),
                "decision_flags": {
                    name: {"status": "PENDING", "reason": MATERIALIZER_FLAG_REASONS[name]}
                    for name in DECISION_FLAGS
                },
            }
        )
    if len(rows) != len(V23_EFFORT_RUNGS) or len(cells) != len(V23_EFFORT_RUNGS) * len(MATERIALIZER_TOPOLOGIES):
        raise V23Error("materialized effort ladder row/cell count diverges")
    return artifact_payload(
        "effort_ladder_materialized",
        status="PENDING_DECISION_FLAGS",
        source_root=str(root),
        materialized_artifact_root=str(artifact_root),
        registered_rungs_nm=list(V23_EFFORT_RUNGS),
        topologies=list(MATERIALIZER_TOPOLOGIES),
        row_count=len(rows),
        topology_count_per_row=len(MATERIALIZER_TOPOLOGIES),
        cell_count=len(cells),
        rows=rows,
        cells=cells,
        decision_flags={
            name: {"status": "PENDING", "reason": MATERIALIZER_FLAG_REASONS[name]}
            for name in DECISION_FLAGS
        },
        selected_effort_nm=None,
        selection_state="PENDING_DECISION_FLAGS",
        selection_policy={
            "topology_preserved": True,
            "automatic_selection": False,
            "predicate_inference": False,
            "selection_requires_explicit_decision_flags": list(DECISION_FLAGS),
        },
        p0_numeric_state="PENDING_UNTIL_APPROVED_PREDICATES_AND_TEMPORAL_TELEMETRY",
    )


def _temporal_episode_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    records = payload.get("records", payload.get("episodes", payload.get("raw_temporal_records")))
    if not isinstance(records, list):
        return [{"_invalid_temporal_record": "payload requires records/episodes list"}]
    episodes = []
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            episodes.append({"_invalid_temporal_record": f"record {index} is not an object"})
            continue
        episode = item.get("temporal_episode") if isinstance(item.get("temporal_episode"), Mapping) else item
        if episode.get("schema") != V23_TEMPORAL_EPISODE_SCHEMA:
            episodes.append({"_invalid_temporal_record": f"record {index} does not preserve the exact raw temporal episode schema"})
            continue
        episodes.append(episode)
    return episodes


def reduce_temporal_ladder(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Reduce raw rung/topology episode rows using the registered P0.2 rules."""

    if not isinstance(payload, Mapping):
        payload = {"records": [{"_invalid_temporal_record": "payload must be an object"}]}
    elif payload.get("schema") not in (
        V23_TEMPORAL_EXPORT_SCHEMA,
        "a2_piper_base_v23_p0_temporal_combined_v1",
    ):
        payload = {
            **dict(payload),
            "records": [
                {
                    "_invalid_temporal_record": "payload schema is not a registered raw/combined temporal schema"
                }
            ],
        }
    records = _temporal_episode_rows(payload)
    grouped: dict[tuple[float, str], list[Mapping[str, Any]]] = {}
    duplicate_keys: set[tuple[float, str, int, int]] = set()
    invalid_identity: list[str] = []
    invalid_schema = [
        str(item["_invalid_temporal_record"])
        for item in records
        if isinstance(item, Mapping) and "_invalid_temporal_record" in item
    ]
    for index, episode in enumerate(records):
        if "_invalid_temporal_record" in episode:
            invalid_identity.append(f"schema:{index}")
            continue
        try:
            effort = finite_number(episode.get("effort_nm"), name=f"records[{index}].effort_nm")
        except (TypeError, ValueError, V23Error) as exc:
            invalid_identity.append(f"effort:{index}:{exc}")
            continue
        if effort not in V23_EFFORT_RUNGS:
            invalid_identity.append(f"unregistered_effort:{index}:{effort}")
            continue
        topology = episode.get("topology")
        if topology not in MATERIALIZER_TOPOLOGIES:
            invalid_identity.append(f"topology:{index}:{topology!r}")
            continue
        env_id = episode.get("env_id")
        episode_index = episode.get("episode_index")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (env_id, episode_index)):
            invalid_identity.append(f"records[{index}]")
            continue
        if episode.get("episode_id") != f"a2-v23-temporal-env{env_id}-episode{episode_index}":
            invalid_identity.append(f"episode_id:{effort}/{topology}/{env_id}/{episode_index}")
            continue
        provenance = episode.get("source_provenance")
        if not isinstance(provenance, Mapping):
            invalid_identity.append(f"missing_provenance:{effort}/{topology}/{env_id}/{episode_index}")
            continue
        required_provenance = (
            "checkpoint", "config", "scenario", "topology", "seed", "plain_prefix_id",
            "env_id", "episode_index", "episode_id", "effort_nm", "checkpoint_load_mode",
        )
        if any(key not in provenance for key in required_provenance):
            invalid_identity.append(f"provenance_schema:{effort}/{topology}/{env_id}/{episode_index}")
            continue
        try:
            provenance_effort = finite_number(provenance.get("effort_nm"), name="provenance.effort_nm")
        except (TypeError, ValueError, V23Error):
            invalid_identity.append(f"provenance_effort:{effort}/{topology}/{env_id}/{episode_index}")
            continue
        if (
            any(not isinstance(provenance.get(key), str) or not provenance.get(key) for key in ("checkpoint", "config", "scenario", "plain_prefix_id"))
            or isinstance(provenance.get("seed"), bool)
            or not isinstance(provenance.get("seed"), int)
            or provenance.get("checkpoint_load_mode") != "policy_only"
            or provenance.get("topology") != topology
            or provenance.get("env_id") != env_id
            or provenance.get("episode_index") != episode_index
            or provenance.get("episode_id") != episode.get("episode_id")
            or provenance_effort != effort
        ):
            invalid_identity.append(f"provenance_identity:{effort}/{topology}/{env_id}/{episode_index}")
            continue
        key = (effort, topology, env_id, episode_index)
        if key in duplicate_keys:
            invalid_identity.append(f"duplicate:{key!r}")
        duplicate_keys.add(key)
        grouped.setdefault((effort, topology), []).append(episode)

    rows = []
    by_rung: dict[float, dict[str, Any]] = {}
    for effort in V23_EFFORT_RUNGS:
        topology_rows = []
        for topology in MATERIALIZER_TOPOLOGIES:
            episodes = grouped.get((effort, topology), [])
            episode_metrics = []
            pending_reasons = []
            if len(episodes) != 16:
                pending_reasons.append(f"EXPECTED_EXACTLY_16_EPISODES_GOT_{len(episodes)}")
            env_ids = [episode.get("env_id") for episode in episodes]
            if set(env_ids) != set(range(16)) or len(env_ids) != len(set(env_ids)):
                pending_reasons.append("ENV_IDS_MUST_COVER_0_TO_15_EXACTLY_ONCE")
            if any(episode.get("temporary_label") != "A0_CANONICAL16_P0_REFERENCE" for episode in episodes):
                pending_reasons.append("TEMPORARY_LABEL_NOT_A0_CANONICAL16_P0_REFERENCE")
            for episode in sorted(episodes, key=lambda value: (value.get("env_id", -1), value.get("episode_index", -1))):
                try:
                    raw_steps = episode.get("step_rows", [])
                    if episode.get("raw_temporal") is not True or not isinstance(raw_steps, list):
                        raise V23Error("raw temporal step_rows/schema marker is missing")
                    if any(
                        not isinstance(row, Mapping)
                        or row.get("schema") != V23_TEMPORAL_STEP_SCHEMA
                        or row.get("effort_nm") != effort
                        or row.get("topology") != topology
                        or row.get("env_id") != episode.get("env_id")
                        or row.get("episode_index") != episode.get("episode_index")
                        or row.get("episode_id") != episode.get("episode_id")
                        for row in raw_steps
                    ):
                        raise V23Error("temporal step schema or immutable identity mismatch")
                    step_numbers = sorted(row.get("control_step") for row in raw_steps if isinstance(row, Mapping))
                    if not step_numbers or len(set(step_numbers)) != len(step_numbers) or step_numbers != list(range(step_numbers[0], step_numbers[-1] + 1)):
                        pending_reasons.append(f"MISSING_OR_DUPLICATE_CONTROL_STEPS_ENV_{episode.get('env_id')}")
                        continue
                    window = a2_v23_select_temporal_window(raw_steps)
                    if window is None:
                        pending_reasons.append(f"NO_VALID_WINDOW_ENV_{episode.get('env_id')}")
                        continue
                    metrics = a2_v23_temporal_window_metrics(window)
                except (TypeError, ValueError, KeyError) as exc:
                    pending_reasons.append(f"INVALID_WINDOW_ENV_{episode.get('env_id')}_{exc}")
                    continue
                episode_metrics.append(
                    {
                        "env_id": episode["env_id"],
                        "episode_index": episode["episode_index"],
                        "window": window,
                        "metrics": metrics,
                    }
                )
            complete = len(episodes) == 16 and len(episode_metrics) == 16 and not pending_reasons
            topology_rows.append(
                {
                    "topology": topology,
                    "episode_count": len(episodes),
                    "evaluable_episode_count": len(episode_metrics),
                    "complete": complete,
                    "status": "OBSERVED" if complete else "PENDING",
                    "pending_reasons": pending_reasons,
                    "episodes": episode_metrics,
                    "progress_rad": None if not complete else sorted(item["metrics"]["progress_rad"] for item in episode_metrics),
                    "saturation_fraction": None if not complete else sorted(item["metrics"]["saturation_fraction"] for item in episode_metrics),
                    "obvious_pd_count": None if not complete else sum(bool(item["metrics"]["obvious_pd"]) for item in episode_metrics),
                }
            )
        row = {"effort_nm": effort, "topologies": topology_rows, "temporary_label": "A0_CANONICAL16_P0_REFERENCE"}
        by_rung[effort] = row
        rows.append(row)

    def median(values: Sequence[float]) -> float | None:
        if not values:
            return None
        ordered = sorted(float(value) for value in values)
        mid = len(ordered) // 2
        return ordered[mid] if len(ordered) % 2 else 0.5 * (ordered[mid - 1] + ordered[mid])

    for effort, row in by_rung.items():
        by_topology = {item["topology"]: item for item in row["topologies"]}
        if not all(item["complete"] for item in by_topology.values()):
            row.update({"status": "PENDING", "complete32": False, "P_ref": None, "P_heavy": None, "S_ref": None, "D": None})
            continue
        pref = median(by_topology["canonical16"]["progress_rad"])
        pheavy = median(by_topology["heavy16"]["progress_rad"])
        sref = median(by_topology["canonical16"]["saturation_fraction"])
        row.update(
            {
                "status": "OBSERVED",
                "complete32": True,
                "P_ref": pref,
                "P_heavy": pheavy,
                "S_ref": sref,
                "pd_count_32": by_topology["canonical16"]["obvious_pd_count"] + by_topology["heavy16"]["obvious_pd_count"],
            }
        )
    baseline = by_rung[100.0]
    if baseline.get("complete32"):
        for effort, row in by_rung.items():
            if row.get("complete32"):
                row["D"] = (baseline["P_heavy"] - row["P_heavy"]) - (baseline["P_ref"] - row["P_ref"])
                row["response_norm_ref"] = row["P_ref"] / baseline["P_ref"] if baseline["P_ref"] != 0.0 else None
                row["response_norm_heavy"] = row["P_heavy"] / baseline["P_heavy"] if baseline["P_heavy"] != 0.0 else None
                row["loss_norm_ref"] = 1.0 - row["response_norm_ref"] if row["response_norm_ref"] is not None else None
                row["loss_norm_heavy"] = 1.0 - row["response_norm_heavy"] if row["response_norm_heavy"] is not None else None
            else:
                row.update({"D": None, "response_norm_ref": None, "response_norm_heavy": None, "loss_norm_ref": None, "loss_norm_heavy": None})
    else:
        for row in by_rung.values():
            row.update({"D": None, "response_norm_ref": None, "response_norm_heavy": None, "loss_norm_ref": None, "loss_norm_heavy": None})

    complete_all = (
        not invalid_identity
        and not invalid_schema
        and all(row.get("complete32") is True for row in rows)
    )
    no_pd_all = complete_all and all(row.get("pd_count_32") == 0 for row in rows)
    normal_eligible = []
    for effort in (20.0, 25.0, 30.0, 40.0, 60.0, 100.0):
        row = by_rung[effort]
        if complete_all and row.get("complete32") and row.get("P_ref", -1.0) >= V23_TEMPORAL_PROGRESS_THRESHOLD_RAD and row.get("pd_count_32") == 0 and row.get("D", -float("inf")) >= V23_TEMPORAL_PROGRESS_THRESHOLD_RAD and row.get("S_ref", -1.0) >= 0.30:
            normal_eligible.append(effort)
    lower_collapse = all(
        by_rung[effort].get("complete32") and by_rung[effort].get("P_ref", float("inf")) < V23_TEMPORAL_PROGRESS_THRESHOLD_RAD and by_rung[effort].get("S_ref", -1.0) >= 0.30 and by_rung[effort].get("pd_count_32") == 0
        for effort in (20.0, 25.0, 30.0, 40.0, 60.0)
    )
    f2_100 = complete_all and lower_collapse and by_rung[100.0].get("complete32") and by_rung[100.0].get("P_ref", -1.0) >= V23_TEMPORAL_PROGRESS_THRESHOLD_RAD and by_rung[100.0].get("pd_count_32") == 0
    f2_40 = complete_all and no_pd_all and all(row.get("P_ref", -1.0) >= V23_TEMPORAL_PROGRESS_THRESHOLD_RAD and row.get("D", float("inf")) < V23_TEMPORAL_PROGRESS_THRESHOLD_RAD for row in rows)
    candidate_requested = bool(payload.get("candidate_promotion_requested", False))
    labels = {episode.get("temporary_label") for episode in records}
    candidate_zone = payload.get("candidate_e_zone")
    if candidate_requested and (labels != {"A0_CANONICAL16_P0_REFERENCE"} or candidate_zone != "E0"):
        outcome, selected = "A0_NOT_E0_AT_CANDIDATE", None
    elif f2_100:
        outcome, selected = "F2_100_SELECTED", 100.0
    elif f2_40:
        outcome, selected = "LADDER_INCONCLUSIVE", 40.0
    elif normal_eligible:
        selected = normal_eligible[0]
        outcome = "NORMAL_BOUNDARY_SELECTED"
    else:
        selected = None
        outcome = "PENDING" if not complete_all else "INCONCLUSIVE"
    reduction = {
        "schema": "a2_piper_base_v23_p0_effort_temporal_reduction_v1",
        "status": outcome,
        "outcome": outcome,
        "temporary_label": "A0_CANONICAL16_P0_REFERENCE",
        "registered_rungs_nm": list(V23_EFFORT_RUNGS),
        "topologies": list(MATERIALIZER_TOPOLOGIES),
        "rows": rows,
        "selected_effort_nm": selected,
        "selection_state": "P0_CANDIDATE" if selected is not None else "PENDING",
        "exact_episode_contract": {"episodes_per_topology": 16, "total_per_rung": 32, "required_total_for_selection": 32},
        "window_contract": {"control_steps": 25, "stage": [3, 4], "stable_grasp_min_steps": 20, "selection": "lexicographically_first"},
        "authority": "RAW_TEMPORAL_TELEMETRY_REQUIRED_NO_AGGREGATE_FALLBACK",
        "invalid_evidence_policy": "PENDING; missing/nonfinite/oscillation_never_implies_collapse_or_selection",
        "candidate_promotion_policy": "P0.4_REQUIRED",
        "duplicate_or_invalid_identity_count": len(invalid_identity),
        "schema_invalid_records": invalid_schema,
    }
    provenance_records = []
    for episode in records:
        provenance = episode.get("source_provenance") if isinstance(episode, Mapping) else None
        if isinstance(provenance, Mapping) and all(key in provenance for key in EFFORT_FREEZE_PROVENANCE_FIELDS):
            provenance_records.append(dict(provenance))
    run_provenance = []
    for effort in V23_EFFORT_RUNGS:
        for topology in MATERIALIZER_TOPOLOGIES:
            candidates = [
                item for item in provenance_records
                if item.get("effort_nm") == effort and item.get("topology") == topology
            ]
            if not candidates:
                continue
            run_provenance.append(
                {
                    "effort_nm": effort,
                    "topology": topology,
                    "record_count": len(candidates),
                    "checkpoint": candidates[0]["checkpoint"],
                    "config": candidates[0]["config"],
                    "scenario": candidates[0]["scenario"],
                    "seed": candidates[0]["seed"],
                    "plain_prefix_id": candidates[0]["plain_prefix_id"],
                    "checkpoint_load_mode": candidates[0]["checkpoint_load_mode"],
                    "env_ids": sorted(int(item["env_id"]) for item in candidates),
                }
            )
    selected = reduction["selected_effort_nm"]
    selection_outcome = reduction["outcome"] if selected is not None else "PENDING"
    freeze_status = "MEASURED_FREEZE" if selection_outcome in EFFORT_FREEZE_SELECTION_OUTCOMES else "PENDING"
    source_complete = (
        not invalid_identity
        and not invalid_schema
        and len(provenance_records) == len(records) == len(V23_EFFORT_RUNGS) * len(MATERIALIZER_TOPOLOGIES) * 16
        and all(row.get("complete32") is True for row in rows)
    )
    reduction["schema"] = EFFORT_FREEZE_SCHEMA
    reduction["reduction_schema"] = "a2_piper_base_v23_p0_effort_temporal_reduction_v1"
    reduction["status"] = freeze_status
    reduction["selection_outcome"] = selection_outcome
    reduction["selection_state"] = "MEASURED_FREEZE" if freeze_status == "MEASURED_FREEZE" else "PENDING"
    reduction["effort_profile"] = (
        {"name": f"base_v23_p0_effort_{float(selected):g}", "effort_nm": float(selected)}
        if selected is not None
        else None
    )
    reduction["source_provenance"] = {
        "schema": V23_TEMPORAL_EXPORT_SCHEMA,
        "complete": source_complete,
        "record_count": len(provenance_records),
        "required_fields": list(EFFORT_FREEZE_PROVENANCE_FIELDS),
        "runs": run_provenance,
    }
    reduction["authorities"] = {
        "selection": "RAW_TEMPORAL_REDUCER_ONLY",
        "temporal_measurement": "GENUINE_PHYSICS_SUBSTEP_FRAMES",
        "checkpoint_load_mode": "policy_only",
        "historical_prior": "PRIOR_ONLY_NOT_SELECTION_INPUT",
    }
    return reduction


def select_boundary(rows: Sequence[Mapping[str, Any]]) -> float | None:
    """Select the first fully eligible rung in the registered descending order."""

    by_effort = {finite_number(row["effort_nm"], name="effort_nm"): row for row in rows}
    for effort in V23_EFFORT_RUNGS:
        row = by_effort.get(effort)
        if row is None:
            continue
        flags = row.get("decision_flags")
        if isinstance(flags, Mapping) and all(flags.get(name) is True for name in DECISION_FLAGS):
            return effort
    return None


def build_ladder(observations: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if observations is not None and isinstance(observations, Mapping):
        raw_schema = observations.get("schema")
        has_raw_records = any(
            key in observations for key in ("raw_temporal_records", "episodes")
        ) or raw_schema == V23_TEMPORAL_EXPORT_SCHEMA
        if has_raw_records:
            return reduce_temporal_ladder(observations)
    observed = _input_rows(observations) if observations is not None else {}
    rows = [_classify(effort, observed.get(effort)) for effort in V23_EFFORT_RUNGS]
    # Aggregate terminal observations preserve the historical artifact shape,
    # but they are intentionally never sufficient for rung selection.  P0.2
    # selection requires the raw temporal reducer above.
    selected = None
    return artifact_payload(
        "effort_ladder",
        status="NOT_RUN_PENDING" if observations is None else "INCONCLUSIVE_OR_PENDING",
        registered_rungs_nm=list(V23_EFFORT_RUNGS),
        rows=rows,
        rungs=rows,
        selected_effort_nm=selected,
        selection_state="PENDING",
        selection_rule={
            "order": "100_to_60_to_40_to_30_to_25_to_20",
            "requires_all_flags": list(DECISION_FLAGS),
            "shared_across_all_cells": True,
            "d0_d1_effort_difference_forbidden": True,
        },
        prior_evidence=[
            {**item, "available": (REPO_ROOT / item["path"]).is_file()}
            for item in PRIOR_EVIDENCE
        ],
        prior_use="context_only; never selects the v23 rung",
        p0_numeric_state="PENDING_UNTIL_MEASURED",
    )


# Descriptive aliases keep the small module convenient for callers without
# adding another execution path.
build_effort_ladder = build_ladder
choose_boundary = select_boundary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, default=None)
    parser.add_argument(
        "--materialize-root",
        type=Path,
        default=None,
        help="absolute six-rung/canonical16/heavy16 runtime artifact root",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.materialize_root is not None:
        if args.observations is not None:
            raise V23Error("--materialize-root cannot be combined with --observations")
        emit_payload(_materialize_runtime_root(args.materialize_root), args.out)
        return 0
    observations = read_json(args.observations) if args.observations is not None else None
    emit_payload(build_ladder(observations), args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 EFFORT LADDER FAIL: {exc}")
