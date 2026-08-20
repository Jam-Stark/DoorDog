"""CPU-only P2 harness-bisection diagnostic.

This reducer compares a future fresh P2 compatibility/stage trace with the
frozen P0 compatibility trace and the v23 G7 Route-A canonical16 evidence.  It
does not import IsaacSim or modify any runtime/configuration code.  The output
is one append-only JSON receipt for the owner-approved vitals diagnostic.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency is part of the repo environment
    raise RuntimeError("PyYAML is required for the P2 vitals diagnostic") from exc


SCHEMA = "a2_piper_v24_p2_harness_diagnostic_v1"
TASK_ID = "V24-P2-VITALS"
REVISION = "R5-HARNESS-BISECTION-SEMANTICS-FIX"
TRACE_SCHEMA = "a2_piper_v24_p0_compatibility_trace_v1"
TRACE_ENV_COUNT = 16
TRACE_ENV_IDS = tuple(range(TRACE_ENV_COUNT))
ACTOR_OBS_DIM = 133
ACTION_DIM = 12
FINAL_ACTION_DIM = 24
ATOL = 1.0e-6
CONTROL_DT_S = 0.005
CONTROL_DECIMATION = 4
CONTROL_PERIOD_S = 0.02
EPISODE_HORIZON_S = 20.0
EXPECTED_CHECKPOINT_SUFFIX = "logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
EXPECTED_P0_CHECKPOINT_SUFFIX = "logs_eval/base_v24/p1/reset_persistence/r6/producer_runtime/current/G7/model_step_001500.pt"
EXPECTED_TRAINING_WARM_START_SUFFIX = "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt"
EXPECTED_LOAD_MODE = "policy_only"
EXPECTED_STEP1_IDENTITY = {
    "checkpoint": EXPECTED_CHECKPOINT_SUFFIX,
    "checkpoint_load_mode": "selected_policy_only",
    "continuity_id": "VITALS_STEP1_CURRENT_HARNESS",
    "cap_nm": 40.0,
    "d1_sampler_enabled": False,
    "mode": "HI_FULL",
    "num_envs": TRACE_ENV_COUNT,
    "profile": "F00",
    "r2_evidence_enabled": False,
    "scenario_ids": [f"S{env_id:02d}" for env_id in TRACE_ENV_IDS],
    "seed": 24021,
}
EXPECTED_STEP1_OUTCOME = "STEP1_ZERO_REPRODUCED_PROCEED_HARNESS_BISECTION"
REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_OUTPUT_PATH = (
    REPO_ROOT
    / "logs_eval/base_v24/p2/force_boundary/vitals_r1/step2_harness/P2_HARNESS_DIAGNOSTIC_RECEIPT_R2.json"
).resolve()
SUPERSEDED_OUTPUT_PATH = (
    REPO_ROOT
    / "logs_eval/base_v24/p2/force_boundary/vitals_r1/step2_harness/P2_HARNESS_DIAGNOSTIC_RECEIPT.json"
).resolve()
STAGING_FIELDS = (
    "stage0_to1_staging_standoff",
    "stage0_actual_root_height",
    "stage1_actual_root_height",
)
POSE_VECTOR_FIELDS = {
    "root_pos_w": 3,
    "root_quat_w": 4,
    "root_pos_rel": 3,
    "tcp_to_handle_pos": 3,
    "tcp_to_handle_quat": 4,
    "target_pos_source_handle": 3,
    "target_pos_source_pregrasp": 3,
    "target_quat_source_handle": 4,
    "target_quat_source_pregrasp": 4,
}
POSE_SCALAR_FIELDS = (
    "target_pos_source_handle_distance",
    "target_pos_source_pregrasp_distance",
    *STAGING_FIELDS,
)
AUTHORITY_CONTRACT = {
    "door_friction": "MODELED_FROM_PARAMS",
    "solver_applied": False,
}
R10_SCIENTIFIC_STATUS = "SUSPECTED_INVALID_MEASUREMENT_PENDING_VITALS"


class DiagnosticError(ValueError):
    """Raised for malformed authoritative diagnostic inputs."""


def _require_regular_file(raw_path: str | Path, *, label: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if path.is_symlink() or not path.is_file():
        raise DiagnosticError(f"{label} must be a regular file: {path}")
    return path


def _read_json(raw_path: str | Path, *, label: str) -> Any:
    path = _require_regular_file(raw_path, label=label)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiagnosticError(f"{label} is not valid JSON: {path}") from exc


def _read_mapping(raw_path: str | Path, *, label: str) -> dict[str, Any]:
    payload = _read_json(raw_path, label=label)
    if not isinstance(payload, Mapping):
        raise DiagnosticError(f"{label} root must be a mapping")
    return dict(payload)


def _read_yaml_mapping(raw_path: str | Path, *, label: str) -> dict[str, Any]:
    path = _require_regular_file(raw_path, label=label)
    try:
        # Hydra's resolved runtime config contains pathlib.PosixPath tags.
        # This file is a local authoritative run artifact, so retain those
        # typed values rather than silently coercing or dropping them.
        payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.UnsafeLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise DiagnosticError(f"{label} is not valid YAML: {path}") from exc
    if not isinstance(payload, Mapping):
        raise DiagnosticError(f"{label} root must be a mapping")
    return dict(payload)


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DiagnosticError(f"{label} must be a finite number; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise DiagnosticError(f"{label} must be a finite number; got {value!r}")
    return result


def _integer(value: Any, *, label: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DiagnosticError(f"{label} must be an integer; got {value!r}")
    if minimum is not None and value < minimum:
        raise DiagnosticError(f"{label} must be >= {minimum}; got {value!r}")
    return value


def _finite_vector(value: Any, *, length: int, label: str) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != length:
        raise DiagnosticError(f"{label} must contain exactly {length} numeric values")
    return [_finite(item, label=f"{label}[{index}]") for index, item in enumerate(value)]


def _checkpoint_identity(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DiagnosticError(f"{label} must be a non-empty checkpoint path")
    return Path(value).expanduser().resolve(strict=False).as_posix()


def _checkpoint_has_exact_suffix(actual: str, expected_suffix: str) -> bool:
    suffix = Path(expected_suffix).as_posix().lstrip("/")
    return actual == suffix or actual.endswith(f"/{suffix}")


def _validate_compatibility_trace(payload: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    if payload.get("schema") != TRACE_SCHEMA or payload.get("status") != "RUNTIME_VERIFIED":
        raise DiagnosticError(f"{label} has an unexpected compatibility trace schema/status")
    topology = payload.get("topology")
    if not isinstance(topology, Mapping):
        raise DiagnosticError(f"{label}.topology must be a mapping")
    expected_topology = {
        "name": "canonical16",
        "episode_count": TRACE_ENV_COUNT,
        "first_episode_only": True,
        "single_process": True,
    }
    for key, expected in expected_topology.items():
        if topology.get(key) != expected:
            raise DiagnosticError(f"{label}.topology.{key} must be {expected!r}")
    if (
        payload.get("actor_obs_dim") != ACTOR_OBS_DIM
        or payload.get("raw_action_dim") != ACTION_DIM
        or payload.get("final_action_dim") != FINAL_ACTION_DIM
    ):
        raise DiagnosticError(f"{label} actor/action dimensions do not match the frozen 133/12/24 contract")
    source = payload.get("source_identity")
    if not isinstance(source, Mapping):
        raise DiagnosticError(f"{label}.source_identity must be a mapping")
    _checkpoint_identity(source.get("checkpoint_path"), label=f"{label}.source_identity.checkpoint_path")
    if not isinstance(source.get("resolved_config_path"), str) or not source["resolved_config_path"]:
        raise DiagnosticError(f"{label}.source_identity.resolved_config_path must be a path")
    if _integer(source.get("seed"), label=f"{label}.source_identity.seed", minimum=0) != 0:
        raise DiagnosticError(f"{label}.source_identity.seed must be 0")
    if _integer(source.get("num_envs"), label=f"{label}.source_identity.num_envs", minimum=0) != TRACE_ENV_COUNT:
        raise DiagnosticError(f"{label}.source_identity.num_envs must be {TRACE_ENV_COUNT}")
    if not isinstance(payload.get("foot_force_feature"), Mapping):
        raise DiagnosticError(f"{label}.foot_force_feature must be retained as a typed mapping")
    rows_by_env = payload.get("rows_by_env")
    if not isinstance(rows_by_env, list) or len(rows_by_env) != TRACE_ENV_COUNT:
        raise DiagnosticError(f"{label}.rows_by_env must contain exactly 16 environment traces")
    for env_id, rows in enumerate(rows_by_env):
        if not isinstance(rows, list) or not rows:
            raise DiagnosticError(f"{label} env_id={env_id} has no compatibility rows")
        seen_steps: set[int] = set()
        for row_index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise DiagnosticError(f"{label} env_id={env_id} row={row_index} is not a mapping")
            if row.get("env_id") != env_id or row.get("episode_index") != 0:
                raise DiagnosticError(f"{label} env_id={env_id} has non-canonical environment/episode identity")
            step = _integer(row.get("control_step"), label=f"{label} env={env_id} row={row_index}.control_step", minimum=0)
            if step in seen_steps:
                raise DiagnosticError(f"{label} env_id={env_id} has duplicate control_step={step}")
            seen_steps.add(step)
            _finite_vector(row.get("actor_obs"), length=ACTOR_OBS_DIM, label=f"{label} env={env_id} row={row_index}.actor_obs")
            _finite_vector(row.get("raw_action_mean"), length=ACTION_DIM, label=f"{label} env={env_id} row={row_index}.raw_action_mean")
            _finite_vector(row.get("final_action"), length=FINAL_ACTION_DIM, label=f"{label} env={env_id} row={row_index}.final_action")
            if not isinstance(row.get("done"), bool):
                raise DiagnosticError(f"{label} env_id={env_id} row={row_index}.done must be bool")
        terminal = rows[-1].get("terminal_facts")
        if rows[-1].get("done") is not True or not isinstance(terminal, Mapping):
            raise DiagnosticError(f"{label} env_id={env_id} final row lacks typed terminal facts")
        if not isinstance(terminal.get("terminal_reasons"), str) or not terminal["terminal_reasons"]:
            raise DiagnosticError(f"{label} env_id={env_id} terminal reason is missing")
        if not isinstance(terminal.get("goal_reached"), bool):
            raise DiagnosticError(f"{label} env_id={env_id} terminal goal_reached must be bool")
        _integer(terminal.get("max_stage_reached"), label=f"{label} env={env_id}.max_stage_reached")
        _integer(terminal.get("episode_length"), label=f"{label} env={env_id}.episode_length", minimum=1)
    return dict(payload)


def _first_control_zero_rows(trace: Mapping[str, Any], *, label: str) -> dict[int, Mapping[str, Any]]:
    selected: dict[int, Mapping[str, Any]] = {}
    for env_id, rows in enumerate(trace["rows_by_env"]):
        for row in rows:
            if row.get("control_step") == 0:
                selected[env_id] = row
                break
        if env_id not in selected:
            raise DiagnosticError(f"{label} env_id={env_id} has no control_step==0 row")
    if set(selected) != set(TRACE_ENV_IDS):
        raise DiagnosticError(f"{label} step-zero selection is not exactly env_ids 0..15")
    return selected


def _lookup_mapping(root: Mapping[str, Any], path: Sequence[str], *, label: str) -> Any:
    value: Any = root
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            raise DiagnosticError(f"{label} is missing config path {'.'.join(path)}")
        value = value[key]
    return value


def _source_contract(
    fresh_trace: Mapping[str, Any],
    p0_trace: Mapping[str, Any],
    fresh_config: Mapping[str, Any],
    g7_config: Mapping[str, Any],
) -> dict[str, Any]:
    fresh_source = fresh_trace["source_identity"]
    p0_source = p0_trace["source_identity"]
    mismatches: list[dict[str, Any]] = []

    def compare(field: str, fresh_value: Any, expected: Any) -> None:
        if fresh_value != expected:
            mismatches.append({"field": field, "fresh": fresh_value, "expected": expected})

    training_warm_start_checkpoint = _checkpoint_identity(
        g7_config.get("checkpoint"), label="G7 training warm-start checkpoint"
    )
    fresh_checkpoint = _checkpoint_identity(fresh_source.get("checkpoint_path"), label="fresh trace checkpoint")
    p0_checkpoint = _checkpoint_identity(p0_source.get("checkpoint_path"), label="P0 trace checkpoint")
    if not _checkpoint_has_exact_suffix(training_warm_start_checkpoint, EXPECTED_TRAINING_WARM_START_SUFFIX):
        mismatches.append(
            {
                "field": "training_warm_start_checkpoint",
                "actual": training_warm_start_checkpoint,
                "expected_suffix": EXPECTED_TRAINING_WARM_START_SUFFIX,
            }
        )
    if not _checkpoint_has_exact_suffix(fresh_checkpoint, EXPECTED_CHECKPOINT_SUFFIX):
        mismatches.append(
            {
                "field": "fresh_checkpoint_path",
                "actual": fresh_checkpoint,
                "expected_suffix": EXPECTED_CHECKPOINT_SUFFIX,
            }
        )
    if not _checkpoint_has_exact_suffix(p0_checkpoint, EXPECTED_P0_CHECKPOINT_SUFFIX):
        mismatches.append(
            {
                "field": "p0_checkpoint_path",
                "actual": p0_checkpoint,
                "expected_suffix": EXPECTED_P0_CHECKPOINT_SUFFIX,
            }
        )
    compare("seed", fresh_source.get("seed"), p0_source.get("seed"))
    compare("num_envs", fresh_source.get("num_envs"), p0_source.get("num_envs"))
    compare("topology", fresh_trace.get("topology"), p0_trace.get("topology"))
    compare("actor_obs_dim", fresh_trace.get("actor_obs_dim"), p0_trace.get("actor_obs_dim"))
    compare("raw_action_dim", fresh_trace.get("raw_action_dim"), p0_trace.get("raw_action_dim"))
    compare("final_action_dim", fresh_trace.get("final_action_dim"), p0_trace.get("final_action_dim"))
    expected_load_mode = g7_config.get("checkpoint_load_mode")
    if expected_load_mode != EXPECTED_LOAD_MODE:
        raise DiagnosticError(f"G7 config checkpoint_load_mode must be {EXPECTED_LOAD_MODE!r}")
    fresh_load_mode = fresh_source.get("checkpoint_load_mode", fresh_config.get("checkpoint_load_mode"))
    compare("checkpoint_load_mode", fresh_load_mode, expected_load_mode)
    fresh_config_checkpoint = _checkpoint_identity(fresh_config.get("checkpoint"), label="fresh config checkpoint")
    compare("fresh_runtime_checkpoint", fresh_config_checkpoint, fresh_checkpoint)
    if fresh_config.get("checkpoint_load_mode") != expected_load_mode:
        mismatches.append({"field": "fresh_config_checkpoint_load_mode", "fresh": fresh_config.get("checkpoint_load_mode"), "expected": expected_load_mode})
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "expected_checkpoint_suffix": EXPECTED_CHECKPOINT_SUFFIX,
        "expected_p0_checkpoint_suffix": EXPECTED_P0_CHECKPOINT_SUFFIX,
        "training_warm_start_checkpoint": training_warm_start_checkpoint,
        "training_warm_start_expected_suffix": EXPECTED_TRAINING_WARM_START_SUFFIX,
        "fresh_checkpoint": fresh_checkpoint,
        "fresh_runtime_checkpoint": fresh_config_checkpoint,
        "p0_checkpoint": p0_checkpoint,
        "expected_checkpoint_load_mode": expected_load_mode,
        "fresh_source_identity": dict(fresh_source),
        "p0_source_identity": dict(p0_source),
        "mismatches": mismatches,
    }


def diagnose_action_identity(
    fresh_trace: Mapping[str, Any],
    p0_trace: Mapping[str, Any],
    *,
    fresh_config: Mapping[str, Any],
    g7_config: Mapping[str, Any],
) -> dict[str, Any]:
    fresh = _validate_compatibility_trace(fresh_trace, label="fresh P2 compatibility trace")
    reference = _validate_compatibility_trace(p0_trace, label="P0 current-off compatibility trace")
    fresh_rows = _first_control_zero_rows(fresh, label="fresh P2 compatibility trace")
    reference_rows = _first_control_zero_rows(reference, label="P0 current-off compatibility trace")
    max_obs = 0.0
    max_action = 0.0
    per_env: list[dict[str, Any]] = []
    for env_id in TRACE_ENV_IDS:
        obs_diffs = [abs(float(left) - float(right)) for left, right in zip(fresh_rows[env_id]["actor_obs"], reference_rows[env_id]["actor_obs"])]
        action_diffs = [abs(float(left) - float(right)) for left, right in zip(fresh_rows[env_id]["raw_action_mean"], reference_rows[env_id]["raw_action_mean"])]
        env_obs = max(obs_diffs)
        env_action = max(action_diffs)
        max_obs = max(max_obs, env_obs)
        max_action = max(max_action, env_action)
        per_env.append({"env_id": env_id, "max_abs_actor_obs_diff": env_obs, "max_abs_raw_action_mean_diff": env_action})
    source = _source_contract(fresh, reference, fresh_config, g7_config)
    status = "PASS" if source["status"] == "PASS" and max_obs <= ATOL and max_action <= ATOL else "FAIL"
    return {
        "status": status,
        "atol": ATOL,
        "compared_env_ids": list(TRACE_ENV_IDS),
        "max_abs_actor_obs_diff": max_obs,
        "max_abs_raw_action_mean_diff": max_action,
        "per_env": per_env,
        "source_contract": source,
        "interior_recurrent_rows_compared": False,
    }


def _validate_stage_trace(payload: Any, *, label: str, detector_fields: bool = False) -> dict[int, list[dict[str, Any]]]:
    if not isinstance(payload, list) or not payload:
        raise DiagnosticError(f"{label} must be a non-empty JSON list of stage rows")
    grouped: dict[int, list[dict[str, Any]]] = {env_id: [] for env_id in TRACE_ENV_IDS}
    for row_index, raw in enumerate(payload):
        if not isinstance(raw, Mapping):
            raise DiagnosticError(f"{label} row={row_index} is not a mapping")
        env_id = _integer(raw.get("env_id"), label=f"{label} row={row_index}.env_id", minimum=0)
        if env_id not in grouped:
            raise DiagnosticError(f"{label} row={row_index} env_id must be 0..15")
        if "episode_index" in raw and raw.get("episode_index") is not None and raw.get("episode_index") != 0:
            raise DiagnosticError(f"{label} row={row_index}.episode_index must be 0 when present")
        _integer(raw.get("step_index"), label=f"{label} row={row_index}.step_index", minimum=0)
        stage = _integer(raw.get("stage_buf"), label=f"{label} row={row_index}.stage_buf", minimum=2)
        if stage not in (2, 3, 4, 5):
            raise DiagnosticError(f"{label} row={row_index}.stage_buf must be 2, 3, 4, or 5")
        _integer(raw.get("time_in_stage_buf"), label=f"{label} row={row_index}.time_in_stage_buf", minimum=0)
        _finite(raw.get("control_dt"), label=f"{label} row={row_index}.control_dt")
        if detector_fields:
            for key in ("both_contact", "squeeze_window", "contact_stability"):
                if raw.get(key) is not True and raw.get(key) is not False:
                    raise DiagnosticError(f"{label} row={row_index}.{key} must be bool")
            _integer(raw.get("a2_stage3_stage4_both_contact_streak"), label=f"{label} row={row_index}.a2_stage3_stage4_both_contact_streak", minimum=0)
            _integer(raw.get("a2_grasp_streak_control_steps"), label=f"{label} row={row_index}.a2_grasp_streak_control_steps", minimum=1)
        grouped[env_id].append(dict(raw))
    if any(not rows for rows in grouped.values()):
        missing = [env_id for env_id, rows in grouped.items() if not rows]
        raise DiagnosticError(f"{label} is missing complete env rows: {missing}")
    for env_id, rows in grouped.items():
        rows.sort(key=lambda row: row["step_index"])
        steps = [row["step_index"] for row in rows]
        if len(set(steps)) != len(steps):
            raise DiagnosticError(f"{label} env_id={env_id} has duplicate step_index values")
    return grouped


def _find_detector_windows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    index = 0
    while index < len(rows):
        row = rows[index]
        eligible = (
            row["stage_buf"] in (3, 4)
            and row["both_contact"] is True
            and row["squeeze_window"] is True
            and row["contact_stability"] is True
            and row["a2_stage3_stage4_both_contact_streak"] >= row["a2_grasp_streak_control_steps"]
        )
        if not eligible:
            index += 1
            continue
        end = index
        while (
            end + 1 < len(rows)
            and rows[end + 1]["step_index"] == rows[end]["step_index"] + 1
            and rows[end + 1]["stage_buf"] in (3, 4)
            and rows[end + 1]["both_contact"] is True
            and rows[end + 1]["squeeze_window"] is True
            and rows[end + 1]["contact_stability"] is True
            and rows[end + 1]["a2_stage3_stage4_both_contact_streak"] >= rows[end + 1]["a2_grasp_streak_control_steps"]
        ):
            end += 1
        run_length = end - index + 1
        if run_length >= 25:
            windows.append(
                {
                    "start_step": rows[index]["step_index"],
                    "end_step": rows[index + 24]["step_index"],
                    "run_length": run_length,
                    "window_rows": 25,
                }
            )
        index = end + 1
    return windows


def diagnose_detector_replay(known_grasp_trace: Any) -> dict[str, Any]:
    grouped = _validate_stage_trace(known_grasp_trace, label="v23 known-grasp stage2 trace", detector_fields=True)
    by_env = {env_id: _find_detector_windows(rows) for env_id, rows in grouped.items()}
    triggered = [env_id for env_id in TRACE_ENV_IDS if by_env[env_id]]
    windows = [
        {"env_id": env_id, **window}
        for env_id in TRACE_ENV_IDS
        for window in by_env[env_id]
    ]
    return {
        "status": "PASS" if triggered else "FAIL",
        "predicate": {
            "stage_buf_in": [3, 4],
            "both_contact": True,
            "squeeze_window": True,
            "contact_stability": True,
            "streak_field": "a2_stage3_stage4_both_contact_streak",
            "streak_threshold_field": "a2_grasp_streak_control_steps",
            "window_rows": 25,
        },
        "triggered_env_ids": triggered,
        "triggered_env_count": len(triggered),
        "windows": windows,
        "window_count": len(windows),
    }


def _compare_scalar_field(
    mismatches: list[dict[str, Any]],
    *,
    env_id: int,
    field: str,
    fresh_value: Any,
    reference_value: Any,
) -> None:
    if fresh_value is None or reference_value is None:
        mismatches.append({"env_id": env_id, "field": field, "kind": "MISSING", "fresh": fresh_value, "reference": reference_value})
        return
    left = _finite(fresh_value, label=f"fresh env={env_id}.{field}")
    right = _finite(reference_value, label=f"reference env={env_id}.{field}")
    delta = abs(left - right)
    if delta > ATOL:
        mismatches.append({"env_id": env_id, "field": field, "kind": "VALUE", "fresh": left, "reference": right, "abs_diff": delta})


def diagnose_horizon_stage_staging(
    fresh_stage_trace: Any,
    reference_stage_trace: Any,
    fresh_config: Mapping[str, Any],
) -> dict[str, Any]:
    fresh = _validate_stage_trace(fresh_stage_trace, label="fresh P2 stage2 trace")
    reference = _validate_stage_trace(reference_stage_trace, label="v23 G7 Route-A stage2 trace")
    mismatches: list[dict[str, Any]] = []
    env_rows: list[dict[str, Any]] = []
    max_episode = _finite(_lookup_mapping(fresh_config, ("env", "config", "max_episode_length_s"), label="fresh runtime config"), label="max_episode_length_s")
    fps = _finite(_lookup_mapping(fresh_config, ("simulator", "config", "sim", "fps"), label="fresh runtime config"), label="sim.fps")
    decimation = _finite(_lookup_mapping(fresh_config, ("simulator", "config", "sim", "control_decimation"), label="fresh runtime config"), label="sim.control_decimation")
    timing = {
        "max_episode_length_s": max_episode,
        "sim_fps": fps,
        "sim_dt_s": 1.0 / fps,
        "control_decimation": decimation,
        "control_period_s": (1.0 / fps) * decimation,
        "declared_contract": {
            "max_episode_length_s": EPISODE_HORIZON_S,
            "sim_dt_s": CONTROL_DT_S,
            "control_decimation": CONTROL_DECIMATION,
            "control_period_s": CONTROL_PERIOD_S,
        },
    }
    timing_mismatches: list[dict[str, Any]] = []
    for field, actual, expected in (
        ("max_episode_length_s", max_episode, EPISODE_HORIZON_S),
        ("sim_dt_s", timing["sim_dt_s"], CONTROL_DT_S),
        ("control_decimation", decimation, float(CONTROL_DECIMATION)),
        ("control_period_s", timing["control_period_s"], CONTROL_PERIOD_S),
    ):
        if abs(actual - expected) > ATOL:
            timing_mismatches.append({"field": field, "actual": actual, "expected": expected, "abs_diff": abs(actual - expected)})
    for env_id in TRACE_ENV_IDS:
        fresh_row = fresh[env_id][0]
        reference_row = reference[env_id][0]
        env_rows.append({"env_id": env_id, "fresh_step": fresh_row["step_index"], "reference_step": reference_row["step_index"]})
        for field in ("env_id", "step_index", "stage_buf", "time_in_stage_buf"):
            if fresh_row.get(field) != reference_row.get(field):
                mismatches.append({"env_id": env_id, "field": field, "kind": "VALUE", "fresh": fresh_row.get(field), "reference": reference_row.get(field)})
        _compare_scalar_field(mismatches, env_id=env_id, field="control_dt", fresh_value=fresh_row.get("control_dt"), reference_value=reference_row.get("control_dt"))
        for field in STAGING_FIELDS:
            _compare_scalar_field(mismatches, env_id=env_id, field=field, fresh_value=fresh_row.get(field), reference_value=reference_row.get(field))
    return {
        "status": "PASS" if not mismatches and not timing_mismatches else "FAIL",
        "timing_contract": timing,
        "timing_mismatches": timing_mismatches,
        "first_rows_by_env": env_rows,
        "mismatches": mismatches,
        "atol": ATOL,
    }


def _compare_pose_vector(
    mismatches: list[dict[str, Any]],
    *,
    env_id: int,
    field: str,
    fresh_value: Any,
    reference_value: Any,
    length: int,
) -> None:
    if fresh_value is None or reference_value is None:
        mismatches.append({"env_id": env_id, "field": field, "kind": "MISSING", "fresh": fresh_value, "reference": reference_value})
        return
    fresh_vector = _finite_vector(fresh_value, length=length, label=f"fresh env={env_id}.{field}")
    reference_vector = _finite_vector(reference_value, length=length, label=f"reference env={env_id}.{field}")
    for index, (left, right) in enumerate(zip(fresh_vector, reference_vector)):
        delta = abs(left - right)
        if delta > ATOL:
            mismatches.append({"env_id": env_id, "field": field, "index": index, "kind": "VALUE", "fresh": left, "reference": right, "abs_diff": delta})


def diagnose_scenario_pose_binding(fresh_stage_trace: Any, reference_stage_trace: Any) -> dict[str, Any]:
    fresh = _validate_stage_trace(fresh_stage_trace, label="fresh P2 stage2 trace")
    reference = _validate_stage_trace(reference_stage_trace, label="v23 G7 Route-A stage2 trace")
    mismatches: list[dict[str, Any]] = []
    for env_id in TRACE_ENV_IDS:
        fresh_row = fresh[env_id][0]
        reference_row = reference[env_id][0]
        for field, length in POSE_VECTOR_FIELDS.items():
            _compare_pose_vector(
                mismatches,
                env_id=env_id,
                field=field,
                fresh_value=fresh_row.get(field),
                reference_value=reference_row.get(field),
                length=length,
            )
        for field in POSE_SCALAR_FIELDS:
            _compare_scalar_field(mismatches, env_id=env_id, field=field, fresh_value=fresh_row.get(field), reference_value=reference_row.get(field))
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "compared_env_ids": list(TRACE_ENV_IDS),
        "env_complete": True,
        "scenario_labels_used": False,
        "mismatches": mismatches,
        "atol": ATOL,
    }


def _validate_owner_decision(path: str | Path) -> dict[str, Any]:
    target = _require_regular_file(path, label="owner decision")
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DiagnosticError(f"owner decision is unreadable: {target}") from exc
    required_markers = (
        "P2_TERMINAL_RECLASSIFIED",
        "DIAGNOSE_THEN_RERUN",
        R10_SCIENTIFIC_STATUS,
        "诊断阶梯",
    )
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise DiagnosticError(f"owner decision is missing required authorization markers: {missing}")
    return {
        "path": target.as_posix(),
        "decision": "P2_TERMINAL_RECLASSIFIED + DIAGNOSE_THEN_RERUN",
        "scientific_status": R10_SCIENTIFIC_STATUS,
        "diagnostic_route": "HARNESS_BISECTION",
    }


def _validate_step1_receipt(path: str | Path) -> dict[str, Any]:
    payload = _read_mapping(path, label="Step1 sham reproduction receipt")
    if payload.get("schema") != "a2_piper_v24_p2_sham_repro_receipt_v1" or payload.get("status") != "EXECUTED":
        raise DiagnosticError("Step1 sham reproduction receipt schema/status is invalid")
    if payload.get("evidentiary") is not False:
        raise DiagnosticError("Step1 receipt evidentiary must be exactly false")
    if payload.get("current_canonical16_physical_binding") != "UNVERIFIED":
        raise DiagnosticError("Step1 current canonical16 physical binding must be exactly UNVERIFIED")
    if payload.get("outcome") != EXPECTED_STEP1_OUTCOME:
        raise DiagnosticError(f"Step1 outcome must be exactly {EXPECTED_STEP1_OUTCOME!r}")
    rows = _integer(payload.get("rows"), label="Step1.rows", minimum=0)
    stable = _integer(payload.get("stable_grasp_count"), label="Step1.stable_grasp_count", minimum=0)
    slip = _integer(payload.get("foot_slip_valid_count"), label="Step1.foot_slip_valid_count", minimum=0)
    if rows != TRACE_ENV_COUNT:
        raise DiagnosticError(f"Step1 receipt rows must be {TRACE_ENV_COUNT}; got {rows}")
    if stable != 0 or slip != 0:
        raise DiagnosticError("Step1 stable_grasp_count and foot_slip_valid_count must both be exactly 0")
    authority = payload.get("authority_contract")
    if authority != AUTHORITY_CONTRACT:
        raise DiagnosticError("Step1 authority contract must preserve MODELED_FROM_PARAMS and solver_applied=false")
    identity = payload.get("identity")
    if not isinstance(identity, Mapping) or dict(identity) != EXPECTED_STEP1_IDENTITY:
        raise DiagnosticError("Step1 identity must exactly bind G7/F00/cap40/HI_FULL/seed24021/canonical16/S00..S15/D1=false")
    return {
        "schema": payload["schema"],
        "status": payload["status"],
        "evidentiary": payload["evidentiary"],
        "current_canonical16_physical_binding": payload["current_canonical16_physical_binding"],
        "rows": rows,
        "stable_grasp_count": stable,
        "foot_slip_valid_count": slip,
        "outcome": payload["outcome"],
        "identity": dict(identity),
        "authority_contract": dict(authority),
    }


def build_receipt(
    *,
    fresh_compatibility_trace: Mapping[str, Any],
    fresh_stage_trace: Any,
    p0_current_off_trace: Mapping[str, Any],
    known_grasp_stage_trace: Any,
    g7_route_a_trace: Any,
    fresh_config: Mapping[str, Any],
    g7_config: Mapping[str, Any],
    owner_decision: Mapping[str, Any],
    step1_receipt: Mapping[str, Any],
    input_paths: Mapping[str, str],
) -> dict[str, Any]:
    action = diagnose_action_identity(
        fresh_compatibility_trace,
        p0_current_off_trace,
        fresh_config=fresh_config,
        g7_config=g7_config,
    )
    detector = diagnose_detector_replay(known_grasp_stage_trace)
    horizon = diagnose_horizon_stage_staging(fresh_stage_trace, g7_route_a_trace, fresh_config)
    pose = diagnose_scenario_pose_binding(fresh_stage_trace, g7_route_a_trace)
    sections = {
        "action_identity": action,
        "detector_replay": detector,
        "horizon_stage_staging": horizon,
        "scenario_pose_binding": pose,
    }
    overall = "PASS" if all(section["status"] == "PASS" for section in sections.values()) else "FAIL"
    return {
        "schema": SCHEMA,
        "status": overall,
        "task_id": TASK_ID,
        "revision": REVISION,
        "supersedes_diagnostic_receipt": SUPERSEDED_OUTPUT_PATH.as_posix(),
        "supersedes_reason": "R4 misclassified training warm-start provenance as evaluated checkpoint identity.",
        "training_warm_start_checkpoint": sections["action_identity"]["source_contract"]["training_warm_start_checkpoint"],
        "training_warm_start_checkpoint_role": "G7 training-config warm-start provenance; not evaluated checkpoint identity",
        "owner_decision": dict(owner_decision),
        "owner_decision_path": owner_decision["path"],
        "diagnostic_route": "PROCEED_HARNESS_BISECTION",
        "r10_scientific_status": R10_SCIENTIFIC_STATUS,
        "scientific_p2_verdict": "NONE",
        "authority_contract": dict(AUTHORITY_CONTRACT),
        "solver_torque_claim": "NONE; solver_applied=false and actual generalized torque is unavailable",
        "step1_zero_counts": {
            "rows": step1_receipt["rows"],
            "stable_grasp_count": step1_receipt["stable_grasp_count"],
            "foot_slip_valid_count": step1_receipt["foot_slip_valid_count"],
            "outcome": step1_receipt.get("outcome"),
        },
        "input_paths": dict(sorted(input_paths.items())),
        "sections": sections,
    }


def _validate_output_path(path: str | Path) -> Path:
    requested = Path(path).expanduser()
    lexical = Path(os.path.abspath(os.fspath(requested)))
    probe = lexical
    while True:
        if probe.is_symlink():
            raise DiagnosticError(f"diagnostic output path must not contain symlinks: {lexical}")
        if probe == probe.parent:
            break
        probe = probe.parent
    target = lexical.resolve(strict=False)
    if target != CANONICAL_OUTPUT_PATH:
        raise DiagnosticError(f"diagnostic output must be exactly {CANONICAL_OUTPUT_PATH}; got {target}")
    if target.is_dir():
        raise DiagnosticError(f"diagnostic output path must be a file, not a directory: {target}")
    return target


def _write_receipt(path: str | Path, receipt: Mapping[str, Any]) -> Path:
    target = _validate_output_path(path)
    if target.exists() or target.is_symlink():
        raise DiagnosticError(f"append-only diagnostic output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump(receipt, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise DiagnosticError(f"append-only diagnostic output already exists: {target}") from exc
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-compatibility-trace", required=True)
    parser.add_argument("--fresh-stage-trace", required=True)
    parser.add_argument("--p0-current-off-trace", required=True)
    parser.add_argument("--known-grasp-stage-trace", required=True)
    parser.add_argument("--g7-route-a-trace", required=True)
    parser.add_argument("--g7-route-a-config", required=True)
    parser.add_argument("--owner-decision", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fresh-config", required=False)
    parser.add_argument("--step1-receipt", required=False)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    fresh_stage_path = _require_regular_file(args.fresh_stage_trace, label="fresh P2 stage trace")
    fresh_config_path = (
        _require_regular_file(args.fresh_config, label="fresh P2 runtime config")
        if args.fresh_config
        else _require_regular_file(fresh_stage_path.parent / ".hydra" / "runtime_config.yaml", label="fresh P2 runtime config")
    )
    step1_path = (
        _require_regular_file(args.step1_receipt, label="Step1 sham reproduction receipt")
        if args.step1_receipt
        else _require_regular_file(fresh_stage_path.parent / "P2_SHAM_REPRO_RECEIPT.json", label="Step1 sham reproduction receipt")
    )
    fresh_compat_path = _require_regular_file(args.fresh_compatibility_trace, label="fresh P2 compatibility trace")
    p0_path = _require_regular_file(args.p0_current_off_trace, label="P0 current-off compatibility trace")
    known_path = _require_regular_file(args.known_grasp_stage_trace, label="v23 known-grasp stage trace")
    g7_trace_path = _require_regular_file(args.g7_route_a_trace, label="v23 G7 Route-A stage trace")
    g7_config_path = _require_regular_file(args.g7_route_a_config, label="v23 G7 Route-A config")
    owner_path = _require_regular_file(args.owner_decision, label="owner decision")
    fresh_compat = _validate_compatibility_trace(_read_mapping(fresh_compat_path, label="fresh P2 compatibility trace"), label="fresh P2 compatibility trace")
    p0_compat = _validate_compatibility_trace(_read_mapping(p0_path, label="P0 current-off compatibility trace"), label="P0 current-off compatibility trace")
    fresh_stage = _read_json(fresh_stage_path, label="fresh P2 stage trace")
    known_stage = _read_json(known_path, label="v23 known-grasp stage trace")
    g7_stage = _read_json(g7_trace_path, label="v23 G7 Route-A stage trace")
    fresh_config = _read_yaml_mapping(fresh_config_path, label="fresh P2 runtime config")
    g7_config = _read_yaml_mapping(g7_config_path, label="v23 G7 Route-A config")
    owner = _validate_owner_decision(owner_path)
    step1 = _validate_step1_receipt(step1_path)
    input_paths = {
        "fresh_compatibility_trace": fresh_compat_path.as_posix(),
        "fresh_stage_trace": fresh_stage_path.as_posix(),
        "p0_current_off_trace": p0_path.as_posix(),
        "known_grasp_stage_trace": known_path.as_posix(),
        "g7_route_a_trace": g7_trace_path.as_posix(),
        "fresh_config": fresh_config_path.as_posix(),
        "g7_route_a_config": g7_config_path.as_posix(),
        "owner_decision": owner_path.as_posix(),
        "step1_receipt": step1_path.as_posix(),
    }
    receipt = build_receipt(
        fresh_compatibility_trace=fresh_compat,
        fresh_stage_trace=fresh_stage,
        p0_current_off_trace=p0_compat,
        known_grasp_stage_trace=known_stage,
        g7_route_a_trace=g7_stage,
        fresh_config=fresh_config,
        g7_config=g7_config,
        owner_decision=owner,
        step1_receipt=step1,
        input_paths=input_paths,
    )
    output = _write_receipt(args.output, receipt)
    print(f"WROTE {output}")


if __name__ == "__main__":
    main()
