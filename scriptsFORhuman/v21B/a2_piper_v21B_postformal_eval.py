"""CPU-only v21-B post-formal evaluation contracts.

This module is intentionally a data-contract tool.  It validates completed
training, builds an immutable Route-A queue, and adjudicates supplied Route-B
evidence.  It never starts Isaac Sim, touches a GPU, or silently substitutes a
checkpoint/metric when an identity is missing.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import statistics
import sys
from copy import deepcopy
from datetime import datetime
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

# Direct script execution does not put the repository root on ``sys.path``;
# keep the CLI usable both as ``python -m`` and by its checked-in path.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from gr00t.rl.envs.door.a2_v21b_evidence import (
    V21B_EVAL_SEEDS,
    V21B_EVAL_TOPOLOGIES,
    V21B_TASK_RECORD_SCHEMA,
    V21B_TERMINAL_RECORD_SCHEMA,
    a2_v21b_validate_task_trace_rows,
    a2_v21b_validate_task_record,
    a2_v21b_validate_terminal_record,
)
from scriptsFORhuman.v21B._v21b_common import (
    V21B_CELL_FACTORS,
    V21B_CELL_ORDER,
    V21B_EXECUTION_ID,
    V21B_FORMAL_CHECKPOINT_STEPS,
    V21B_FORMAL_ITERATIONS,
    V21B_F3_THETA_LADDER,
    V21B_PLAN_ID,
    V21B_ROUTE_A_TOPOLOGY,
    V21B_ROUTE_B_ENVS_PER_SEED,
    V21B_ROUTE_B_HOLDOUT_SEEDS,
    V21B_ROUTE_B_POOLED_SEEDS,
    V21B_ROUTE_B_RENDER_CAMERAS,
    V21B_ROUTE_B_RENDER_CASES,
    V21B_WARM_START_PATH,
    V21B_WARM_START_SHA256,
    V21BError,
    canonical_json_bytes,
    command_sha256,
    hydra_string_value,
    read_yaml,
    require_digest,
    sha256_file,
    validate_v21b_config,
)


FORMAL_METRIC_SCHEMA = "a2_piper_base_v21B_training_metric_v1"
FORMAL_COMPLETION_SCHEMA = "a2_piper_base_v21B_formal_completion_v1"
ROUTE_A_MANIFEST_SCHEMA = "a2_piper_base_v21B_route_a_manifest_v1"
ROUTE_A_QUEUE_SCHEMA = "a2_piper_base_v21B_route_a_queue_v1"
ROUTE_A_METRICS_SCHEMA = "a2_piper_base_v21B_route_a_metrics_v1"
ROUTE_B_QUEUE_SCHEMA = "a2_piper_base_v21B_route_b_queue_v1"
SELECTION_SCHEMA = "a2_piper_base_v21B_selection_v1"
POOLED_REPORT_SCHEMA = "a2_piper_base_v21B_route_b_adjudication_v1"
RELEASE_FREEZE_SCHEMA = "a2_piper_base_v21B_release_freeze_v1"
HOLDOUT_SCHEMA = "a2_piper_base_v21B_holdout64_report_v1"
RENDER_QUEUE_SCHEMA = "a2_piper_base_v21B_render_queue_v1"
RENDER_QA_SCHEMA = "a2_piper_base_v21B_render_qa_v1"
FINAL_ANALYSIS_SCHEMA = "a2_piper_base_v21B_final_analysis_v1"
RELEASE_FREEZE_KEYS = frozenset(
    {
        "schema",
        "status",
        "plan_id",
        "cell",
        "mechanism_checkpoint",
        "release_checkpoint",
        "f3_mode",
        "full_hashes",
        "acceptance_profile",
        "selection_sha256",
        "selection_snapshot",
        "pooled_report_sha256",
        "pooled_report_snapshot",
        "pooled_queue_sha256",
        "pooled_queue_snapshot",
        "pooled_queue_receipt_sha256",
        "pooled_report_topology",
        "post_freeze_intervention_change",
        "freeze_sha256",
    }
)
# Process completion is deliberately distinct from the per-episode bundle
# marker.  The latter is emitted by the evidence producer and never certifies
# the natural exit of its parent process.
PROCESS_RECEIPT_SCHEMA = "a2_piper_base_v21B_process_receipt_v1"
COMPLETION_SEAL_SCHEMA = "a2_piper_base_v21B_process_completion_seal_v1"
EPISODE_BUNDLE_COMPLETE_SCHEMA = "a2_piper_base_v21B_episode_bundle_complete_v1"
POSTFORMAL_PROCESS_RECEIPT_SCHEMA = PROCESS_RECEIPT_SCHEMA
POSTFORMAL_COMPLETION_SEAL_SCHEMA = COMPLETION_SEAL_SCHEMA

FORMAL_CHECKPOINT_RE = re.compile(r"^model_step_(?P<step>[0-9]+)\.pt$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TOPOLOGY_EPISODES = {
    "canonical16": 16,
    "pooled_seed16": 48,
    "holdout_seed16": 64,
    "render1": 1,
}
RUNTIME_SCENARIO_TOPOLOGIES = ("canonical16", "heavy16")
EVIDENCE_AGGREGATION_TOPOLOGIES = ("canonical16", "pooled_seed16", "holdout_seed16", "render1")
RENDER_EXPECTED_CAMERAS = tuple(V21B_ROUTE_B_RENDER_CAMERAS)
ROUTE_A_DIAGNOSTIC_REWARD_TERMS = (
    "gripper_handle_orientation",
    "grasp_target_distance",
    "grasp",
    "penalty_not_standing_still",
    "a2_stage3_unlatch_hold",
    "a2_stage3_stage4_hold_and_drive",
    "push_door_hinge",
    "dont_push_door_handle",
    "target_root_distance",
    "penalty_standing_still",
    "stage",
    "penalty_door_frame_contact",
    "penalty_door_panel_contact",
    "penalty_a2_door_body_contact",
    "penalty_undesired_contact",
    "penalty_base_roll_pitch_l2",
    "a2_corridor_door_wide",
    "a2_corridor_clean_passage",
    "penalty_a2_posture_command_l1",
    "complete",
)
HOLDOUT_REQUIRED_GATES = frozenset(
    {
        "goal",
        "held_crossing",
        "crossing_p50_absolute",
        "crossing_p50_theta_shortfall",
        "crossing_p10_theta_shortfall",
        "opening_slip_p95",
        "pre_send_planar_p95",
        "pre_send_yaw_p95",
        "task_time_p95",
        "stage_overtime",
        "upper_dof_overspeed",
    }
)
POOLED_REQUIRED_GATES = frozenset(
    {
        "goal",
        "held_crossing",
        "crossing_p50_absolute",
        "crossing_p50_theta_shortfall",
        "crossing_p10_theta_shortfall",
        "opening_slip_p95",
        "pre_send_planar_p95",
        "pre_send_yaw_p95",
        "task_time_p95",
        "stage_overtime",
        "upper_dof_overspeed",
        "non_regression_goal",
        "non_regression_overspeed",
        "non_regression_task_time",
    }
)
POOLED_REQUIRED_METRICS = (
    "goal_rate",
    "held_crossing_rate",
    "overspeed_rate",
    "hinge_at_crossing_p10",
    "hinge_at_crossing_p50",
    "opening_slip_p95",
    "pre_send_planar_p95",
    "pre_send_yaw_p95",
    "task_time_p95",
)
SELECTION_NO_RELEASE_REASONS = frozenset(
    {
        "INSUFFICIENT_STRICT_VALID_CHECKPOINTS",
        "UNRANKABLE_MECHANISM_METRIC",
        "NO_PROMOTABLE_ROUTE_A_CHECKPOINT",
        "MECHANISM_RELEASE_NOT_DISTINCT",
    }
)
ROUTE_B_CANDIDATE_KEYS = (
    "evaluated_checkpoint_path",
    "evaluated_checkpoint_sha256",
    "config_path",
    "config_sha256",
    "source_lock_sha256",
    "source_config_sha256",
    "materialization_sha256",
    "materialized_config_sha256",
    "adaptation_bundle_sha256",
)
CANDIDATE_IDENTITY_KEYS = (
    "source_checkpoint_path",
    "source_checkpoint_sha256",
    "evaluated_checkpoint_path",
    "evaluated_checkpoint_sha256",
    "config_path",
    "config_sha256",
    "evaluation_command_sha256",
    "source_lock_sha256",
    "source_config_sha256",
    "materialization_sha256",
    "materialized_config_sha256",
    "adaptation_bundle_sha256",
)
RECORD_CANDIDATE_KEYS = (
    "source_checkpoint_path",
    "source_checkpoint_sha256",
    "evaluated_checkpoint_path",
    "evaluated_checkpoint_sha256",
    "source_lock_sha256",
    "source_config_sha256",
    "materialization_sha256",
    "materialized_config_sha256",
    "adaptation_bundle_sha256",
)

DV_NA_CENSUS_REASON = "CENSUS_RIGHT_CENSORED"
DV_NA_F3_REASON = "THETA_ONLY_FALLBACK_F3"
COMMAND_IDENTITY_OVERRIDE = "+env.config.a2_v21B_evaluation_command_sha256="
DEFAULT_SCENARIO_MANIFEST = Path(
    "logs_eval/base_v21B/preformal_20260802_r10/V21B_HEAVY16_MANIFEST.json"
)

# Evaluation-only resource policy.  ``V21B_CELL_FACTORS[cell]["gpu"]`` is
# historical formal-training provenance and must not be reused for eval
# scheduling.
V21B_EVAL_GPUS = (0, 1, 2, 3)
V21B_EVAL_GPU_BY_CELL = {
    "B1": 0,
    "B2": 1,
    "B3": 2,
    "B4": 3,
    "B5": 0,
    "B6": 1,
    "B7": 2,
}


class PostformalEvalError(ValueError):
    """Fail-fast post-formal contract violation."""


def _queue_receipt(payload: Mapping[str, Any]) -> str:
    """Hash the immutable queue payload, excluding its self-referential receipt."""

    unsigned = dict(payload)
    unsigned.pop("receipt_sha256", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def _queue_row_receipt(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(row))).hexdigest()


def _candidate_projection(candidate: Mapping[str, Any], *, keys: Sequence[str] = CANDIDATE_IDENTITY_KEYS) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise PostformalEvalError("candidate identity must be a mapping")
    projected: dict[str, Any] = {}
    for key in keys:
        value = candidate.get(key)
        if not isinstance(value, str) or not value:
            raise PostformalEvalError(f"candidate identity field {key} is missing")
        if key.endswith("sha256"):
            _digest(value, name=f"candidate identity {key}")
        projected[key] = value
    return projected


def _validate_eval_gpu(gpu: int, *, name: str = "evaluation GPU") -> int:
    if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu not in V21B_EVAL_GPUS:
        raise PostformalEvalError(f"{name} must be one of physical GPUs {V21B_EVAL_GPUS}; got {gpu!r}")
    return gpu


def validate_signed_runtime_topology(config: Mapping[str, Any], *, num_envs: int) -> dict[str, str]:
    """Pure admission check used by CPU-only queue tests and no-sim composition."""

    if not isinstance(config, Mapping) or config.get("a2_v21B_signed_probe_scenarios_enabled") is not True:
        raise PostformalEvalError("signed runtime topology admission requires enabled signed probes")
    if isinstance(num_envs, bool) or num_envs != 16:
        raise PostformalEvalError("signed runtime topology admission requires num_envs=16")
    runtime = config.get("a2_v21B_census_topology")
    aggregation = config.get("a2_v21B_evidence_aggregation_topology")
    if runtime not in RUNTIME_SCENARIO_TOPOLOGIES:
        raise PostformalEvalError("signed runtime topology must be canonical16 or heavy16")
    if aggregation not in EVIDENCE_AGGREGATION_TOPOLOGIES:
        raise PostformalEvalError("signed evidence aggregation topology is invalid")
    run_uuid = config.get("a2_v21B_run_uuid")
    if not isinstance(run_uuid, str) or not run_uuid or any(char.isspace() for char in run_uuid):
        raise PostformalEvalError("signed runtime topology requires a non-empty run_uuid")
    return {"runtime_scenario_topology": runtime, "evidence_aggregation_topology": aggregation, "run_uuid": run_uuid}


def _yaml_path_exists(config: Mapping[str, Any], key: str) -> bool:
    """Return whether a dotted Hydra key is present in the adjacent config."""

    current: Any = config
    for component in key.split("."):
        if not isinstance(current, Mapping) or component not in current:
            return False
        current = current[component]
    return True


def _hydra_override(config: Mapping[str, Any], key: str, value: Any, *, string: bool = False) -> str:
    """Compose an override using ``key=`` for existing keys and ``+key=`` otherwise."""

    if not isinstance(key, str) or not key or any(not part for part in key.split(".")):
        raise PostformalEvalError(f"invalid Hydra override key: {key!r}")
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, str):
        rendered = hydra_string_value(value) if string else value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        rendered = str(value)
    else:
        raise PostformalEvalError(f"Hydra override {key} requires a scalar value")
    prefix = "" if _yaml_path_exists(config, key) else "+"
    return f"{prefix}{key}={rendered}"


def _load_adjacent_config(path: Path) -> dict[str, Any]:
    try:
        return read_yaml(Path(path))
    except V21BError as exc:
        raise PostformalEvalError(str(exc)) from exc


def _validate_signed_manifest(
    path: Path,
    *,
    source_checkpoint_sha256: str,
    source_lock_sha256: str,
    source_config_sha256: str | None = None,
) -> dict[str, Any]:
    """Load the signed heavy16 manifest used by every post-formal probe."""

    path = _regular_file(path, name="signed v21-B scenario manifest")
    manifest = _load_json(path)
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("schema") != "a2_piper_base_v21B_heavy16_manifest_v1"
        or manifest.get("status") != "STATIC_PASS"
    ):
        raise PostformalEvalError("signed scenario manifest schema/status is invalid")
    canonical = manifest.get("canonical_manifest_rows")
    heavy = manifest.get("manifest_rows")
    if not isinstance(canonical, list) or len(canonical) != 32 or not isinstance(heavy, list) or len(heavy) != 16:
        raise PostformalEvalError("signed scenario manifest must contain 32 canonical and 16 heavy rows")
    heavy_hash = hashlib.sha256(canonical_json_bytes(heavy)).hexdigest()
    canonical_hash = hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()
    if manifest.get("manifest_sha256") != heavy_hash or manifest.get("heavy_manifest_sha256", heavy_hash) != heavy_hash:
        raise PostformalEvalError("signed scenario heavy row hash is invalid")
    if manifest.get("canonical_manifest_sha256") != canonical_hash:
        raise PostformalEvalError("signed scenario canonical row hash is invalid")
    for key, expected in (
        ("source_checkpoint_sha256", source_checkpoint_sha256),
        ("source_lock_sha256", source_lock_sha256),
        ("source_config_sha256", source_config_sha256),
    ):
        _digest(manifest.get(key), name=f"signed scenario {key}")
        if expected is not None and manifest[key] != expected:
            raise PostformalEvalError(f"signed scenario {key} does not bind the candidate")
    _digest(manifest.get("materialization_sha256"), name="signed scenario materialization_sha256")
    _digest(manifest.get("materialized_config_sha256"), name="signed scenario materialized_config_sha256")
    manifest_json = canonical_json_bytes(dict(manifest)).decode("utf-8")
    return {
        "path": str(path),
        "file_sha256": sha256_file(path),
        "manifest": dict(manifest),
        "manifest_json": manifest_json,
        "manifest_json_sha256": hashlib.sha256(manifest_json.encode("utf-8")).hexdigest(),
        "manifest_sha256": heavy_hash,
        "canonical_manifest_sha256": canonical_hash,
        "materialization_sha256": manifest["materialization_sha256"],
    }


def _finite(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise PostformalEvalError(f"{name} must be a finite number")
    return float(value)


def _load_json(path: Path) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PostformalEvalError(f"cannot read JSON {path}: {exc}") from exc
    return value


def _regular_file(path: Path, *, name: str) -> Path:
    path = Path(path).expanduser().resolve()
    if path.is_symlink() or not path.is_file():
        raise PostformalEvalError(f"{name} must be an existing regular file: {path}")
    return path


def _regular_dir(path: Path, *, name: str) -> Path:
    path = Path(path).expanduser().resolve()
    if path.is_symlink() or not path.is_dir():
        raise PostformalEvalError(f"{name} must be an existing regular directory: {path}")
    return path


def _digest(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise PostformalEvalError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _canonical_path(value: Any, *, name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PostformalEvalError(f"{name} must be a non-empty path string")
    return Path(value).expanduser().resolve()


def _immutable_json(path: Path, value: Mapping[str, Any]) -> Path:
    path = Path(path).expanduser()
    payload = canonical_json_bytes(dict(value)) + b"\n"
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.read_bytes() != payload:
            raise PostformalEvalError(f"immutable artifact differs: {path}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
    return path


def _declared_command_identity(argv: Sequence[str], env: Mapping[str, str]) -> str:
    """Validate a command's self-declared hash without a cyclic self-hash."""

    if not isinstance(argv, list) or not isinstance(env, Mapping):
        raise PostformalEvalError("evaluation command identity requires argv/env")
    declarations = [item for item in argv if isinstance(item, str) and item.startswith(COMMAND_IDENTITY_OVERRIDE)]
    if len(declarations) != 1:
        raise PostformalEvalError("evaluation command must carry exactly one command-hash override")
    declared = declarations[0][len(COMMAND_IDENTITY_OVERRIDE):]
    _digest(declared, name="evaluation command declared sha256")
    base = [item for item in argv if item != declarations[0]]
    if command_sha256(base, env) != declared:
        raise PostformalEvalError("evaluation command declaration does not bind argv/environment")
    return declared


def _read_metric_rows(path: Path, *, cell: str) -> list[dict[str, Any]]:
    path = _regular_file(path, name=f"{cell} training metric stream")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise PostformalEvalError(f"{path}:{line_number} contains an empty metric line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PostformalEvalError(f"{path}:{line_number} is not JSON") from exc
        if not isinstance(row, dict):
            raise PostformalEvalError(f"{path}:{line_number} metric row must be an object")
        rows.append(row)
    if len(rows) != V21B_FORMAL_ITERATIONS:
        raise PostformalEvalError(
            f"{cell} requires exactly {V21B_FORMAL_ITERATIONS} metric rows; got {len(rows)}"
        )
    for expected_batch, row in enumerate(rows, start=1):
        if row.get("schema") != FORMAL_METRIC_SCHEMA:
            raise PostformalEvalError(f"{cell} metric row {expected_batch} schema is invalid")
        if row.get("scientific_plan_id") != V21B_PLAN_ID or row.get("cell") != cell:
            raise PostformalEvalError(f"{cell} metric row {expected_batch} identity is invalid")
        if row.get("batch_index") != expected_batch:
            raise PostformalEvalError(f"{cell} metric rows must be contiguous 1..2500")
        if row.get("producer_state") != "PROCESS_COMPLETED":
            raise PostformalEvalError(f"{cell} metric row {expected_batch} producer_state is not PROCESS_COMPLETED")
        for identity_key in (
            "source_checkpoint_sha256",
            "source_config_sha256",
            "source_lock_sha256",
            "source_lock_file_sha256",
            "materialization_sha256",
            "materialized_config_sha256",
            "adaptation_bundle_sha256",
        ):
            _digest(row.get(identity_key), name=f"{cell} metric {identity_key}")
        if row.get("materialization_phase") != "FORMAL_PROMOTED":
            raise PostformalEvalError(f"{cell} formal metric materialization phase is not FORMAL_PROMOTED")
        metrics = row.get("metrics")
        if not isinstance(metrics, Mapping):
            raise PostformalEvalError(f"{cell} metric row {expected_batch} metrics mapping is missing")
        finite_data = metrics.get("finite_data")
        if isinstance(finite_data, bool) or not isinstance(finite_data, (int, float)) or float(finite_data) != 1.0:
            raise PostformalEvalError(f"{cell} metric row {expected_batch} finite_data must be numeric 1.0")
        for key, value in metrics.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and not math.isfinite(float(value)):
                raise PostformalEvalError(f"{cell} metric row {expected_batch} contains non-finite {key}")
    if rows[-1].get("producer_state") != "PROCESS_COMPLETED":
        raise PostformalEvalError(f"{cell} final producer_state is not PROCESS_COMPLETED")
    return rows


def _find_output_logs(cell_root: Path) -> list[Path]:
    return sorted(path for path in cell_root.rglob("output.log") if path.is_file() and not path.is_symlink())


def _validate_formal_output_log(cell_root: Path, *, cell: str) -> Path:
    logs = _find_output_logs(cell_root)
    if len(logs) != 1:
        raise PostformalEvalError(f"{cell} requires exactly one output.log; got {len(logs)}")
    content = logs[0].read_text(encoding="utf-8", errors="strict")
    if re.search(r"Learning iteration\s+2500", content) is None:
        raise PostformalEvalError(f"{cell} output.log does not contain Learning iteration 2500")
    if "model_step_002500.pt" not in content or "last.pt" not in content:
        raise PostformalEvalError(f"{cell} output.log does not record both final numbered and last saves")
    return logs[0]


def _checkpoint_rows(cell_root: Path, *, cell: str) -> list[dict[str, Any]]:
    observed: dict[int, Path] = {}
    for path in sorted(cell_root.iterdir(), key=lambda item: item.name):
        match = FORMAL_CHECKPOINT_RE.fullmatch(path.name)
        if match is None:
            continue
        step = int(match.group("step"))
        if step not in V21B_FORMAL_CHECKPOINT_STEPS:
            raise PostformalEvalError(f"{cell} contains an unexpected numbered checkpoint step {step}")
        if step in observed:
            raise PostformalEvalError(f"{cell} contains duplicate checkpoint step {step}")
        observed[step] = _regular_file(path, name=f"{cell} checkpoint {step}")
    if set(observed) != set(V21B_FORMAL_CHECKPOINT_STEPS):
        raise PostformalEvalError(
            f"{cell} requires exact numbered checkpoints {list(V21B_FORMAL_CHECKPOINT_STEPS)}; got {sorted(observed)}"
        )
    last_path = cell_root / "last.pt"
    _regular_file(last_path, name=f"{cell} last.pt")
    rows = []
    for step in V21B_FORMAL_CHECKPOINT_STEPS:
        path = observed[step]
        rows.append({"step": step, "path": str(path), "sha256": sha256_file(path), "candidate": path.name})
    return rows


def _flatten_config(value: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten YAML mappings/lists for signed materialization parity checks."""

    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten_config(child, child_prefix))
        return result
    if isinstance(value, list):
        result = {}
        for index, child in enumerate(value):
            result.update(_flatten_config(child, f"{prefix}[{index}]"))
        return result
    return {prefix: value}


def _validate_signed_materialized_parity(
    formal_config: Mapping[str, Any],
    *,
    cell: str,
    formal_root: Path,
    f3_context: Mapping[str, Any],
) -> None:
    paths = f3_context.get("materialized_config_path_by_cell")
    hashes = f3_context.get("materialized_config_sha256_by_cell")
    if not isinstance(paths, Mapping) or not isinstance(hashes, Mapping):
        raise PostformalEvalError("F3 context lacks signed materialized config paths")
    signed_path = _regular_file(Path(paths.get(cell, "")), name=f"{cell} signed materialized config")
    signed_sha = _digest(hashes.get(cell), name=f"{cell} signed materialized config sha256")
    if sha256_file(signed_path) != signed_sha:
        raise PostformalEvalError(f"{cell} signed materialized config hash changed")
    try:
        signed_config = yaml.safe_load(signed_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PostformalEvalError(f"{cell} signed materialized config is invalid YAML") from exc
    if not isinstance(signed_config, Mapping):
        raise PostformalEvalError(f"{cell} signed materialized config must be a mapping")
    signed_leaves = _flatten_config(signed_config)
    formal_leaves = _flatten_config(formal_config)
    allowed_formal_only = {
        "env.config.a2_v21B_census_topology",
        "env.config.a2_v21B_materialization_sha256",
        "env.config.a2_v21B_materialized_config_sha256",
        "r2_evidence_enabled",
        "r2_source_lock_path",
        "r2_training_metrics_path",
        "v21b_adaptation_bundle_sha256",
        "v21b_materialization_sha256",
        "v21b_materialized_config_sha256",
    }
    allowed_different = {"algo.trl.output_dir", "experiment_dir"}
    missing = sorted(set(signed_leaves) - set(formal_leaves))
    extra = sorted(set(formal_leaves) - set(signed_leaves) - allowed_formal_only)
    different = sorted(key for key in signed_leaves.keys() & formal_leaves.keys() if signed_leaves[key] != formal_leaves[key] and key not in allowed_different)
    if missing or extra or different:
        raise PostformalEvalError(f"{cell} formal config diverges from signed materialization: missing={missing}, extra={extra}, different={different}")
    expected_root = str(formal_root.resolve())
    if formal_leaves.get("algo.trl.output_dir") != expected_root or formal_leaves.get("experiment_dir") != expected_root:
        raise PostformalEvalError(f"{cell} formal output/experiment roots are not bound to its adjacent run root")
    expected_extra = {
        "env.config.a2_v21B_census_topology": "canonical16",
        "env.config.a2_v21B_materialization_sha256": f3_context.get("materialization_sha256"),
        "env.config.a2_v21B_materialized_config_sha256": signed_sha,
        "r2_evidence_enabled": True,
        "r2_training_metrics_path": str((formal_root / "r2_training_metrics.jsonl").resolve()),
        "v21b_adaptation_bundle_sha256": f3_context.get("adaptation_bundle_sha256"),
        "v21b_materialization_sha256": f3_context.get("materialization_sha256"),
        "v21b_materialized_config_sha256": signed_sha,
    }
    for key, expected in expected_extra.items():
        if expected is not None and formal_leaves.get(key) != expected:
            raise PostformalEvalError(f"{cell} formal-only config value {key} is not bound to the signed F3 identity/path")
    lock_path = _regular_file(Path(formal_leaves.get("r2_source_lock_path", "")), name=f"{cell} r2 source lock")
    lock_payload = _load_json(lock_path)
    if lock_payload.get("source_lock_sha256") != f3_context.get("source_lock_sha256"):
        raise PostformalEvalError(f"{cell} r2 source lock path is not bound to F3 source lock")


def validate_formal_cell(cell_root: Path, *, cell: str | None = None, f3_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Independently validate one formal run to iteration 2500."""

    cell_root = _regular_dir(cell_root, name="formal cell root")
    actual_cell = cell or cell_root.name
    if actual_cell not in V21B_CELL_ORDER:
        raise PostformalEvalError(f"formal cell must be one of {V21B_CELL_ORDER}; got {actual_cell!r}")
    metrics_path = cell_root / "r2_training_metrics.jsonl"
    metric_rows = _read_metric_rows(metrics_path, cell=actual_cell)
    output_log = _validate_formal_output_log(cell_root, cell=actual_cell)
    checkpoint_rows = _checkpoint_rows(cell_root, cell=actual_cell)
    config_path = _regular_file(cell_root / "config.yaml", name=f"{actual_cell} adjacent config")
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PostformalEvalError(f"{actual_cell} config is invalid YAML") from exc
    if not isinstance(config, Mapping):
        raise PostformalEvalError(f"{actual_cell} config must be a mapping")
    try:
        validate_v21b_config(config, cell=actual_cell, require_launchable=True)
    except V21BError as exc:
        raise PostformalEvalError(f"{actual_cell} checkpoint-adjacent config violates the frozen v21-B contract: {exc}") from exc
    factors = V21B_CELL_FACTORS[actual_cell]
    env_config = config.get("env", {}).get("config", {})
    if not isinstance(env_config, Mapping):
        raise PostformalEvalError(f"{actual_cell} env.config is not a mapping")
    if env_config.get("a2_v20_send_hinge_threshold") != V21B_F3_THETA_LADDER[actual_cell]:
        raise PostformalEvalError(f"{actual_cell} formal config theta is not bound to the F3 ladder")
    if env_config.get("a2_v21B_target_root_ramp_theta_rad") != V21B_F3_THETA_LADDER[actual_cell]:
        raise PostformalEvalError(f"{actual_cell} target-root ramp theta is not bound to F3")
    if env_config.get("a2_v21B_arm_profile") != "ARM_V20" or env_config.get("a2_v20_arm_tie_enabled") is not False:
        raise PostformalEvalError(f"{actual_cell} formal config arm profile/tie admission is invalid")
    effort_limits = config.get("robot", {}).get("dof_effort_limit_list")
    if not isinstance(effort_limits, list) or effort_limits[12:18] != [100.0] * 6:
        raise PostformalEvalError(f"{actual_cell} formal config must retain ARM_V20 100 N.m six-joint effort semantics")
    if config.get("v21b_materialization_phase") != "FORMAL_PROMOTED" or config.get("v21b_f3_fallback") is not True:
        raise PostformalEvalError(f"{actual_cell} formal config is not the signed F3 FORMAL_PROMOTED materialization")
    if config.get("seed") != factors["seed"]:
        raise PostformalEvalError(f"{actual_cell} config seed does not match factor matrix")
    if config.get("num_envs") != 4096 or config.get("checkpoint_load_mode") != "policy_only" or config.get("auto_load_latest") is not False:
        raise PostformalEvalError(f"{actual_cell} formal config dimensions/load mode are invalid")
    if config.get("algo", {}).get("trl", {}).get("num_total_batches") != V21B_FORMAL_ITERATIONS:
        raise PostformalEvalError(f"{actual_cell} formal config num_total_batches is not 2500")
    if config.get("callbacks", {}).get("model_save", {}).get("save_frequency") != 250:
        raise PostformalEvalError(f"{actual_cell} formal config save_frequency is not 250")
    last = metric_rows[-1]
    identity_keys = (
        "source_checkpoint_sha256",
        "source_config_sha256",
        "source_lock_sha256",
        "source_lock_file_sha256",
        "materialization_sha256",
        "materialized_config_sha256",
        "adaptation_bundle_sha256",
    )
    first = metric_rows[0]
    for identity_key in identity_keys:
        if any(row.get(identity_key) != first.get(identity_key) for row in metric_rows):
            raise PostformalEvalError(f"{actual_cell} formal metric {identity_key} changed across the run")
    config_identity = {
        "source_checkpoint_sha256": config.get("v21b_source_checkpoint_sha256"),
        "source_lock_sha256": config.get("v21b_source_lock_sha256"),
        "materialization_sha256": config.get("v21b_materialization_sha256"),
        "materialized_config_sha256": config.get("v21b_materialized_config_sha256"),
        "adaptation_bundle_sha256": config.get("v21b_adaptation_bundle_sha256"),
    }
    for identity_key, expected in config_identity.items():
        _digest(expected, name=f"{actual_cell} adjacent config {identity_key}")
        if expected != first[identity_key]:
            raise PostformalEvalError(f"{actual_cell} adjacent config {identity_key} does not bind formal metric identity")
    if config.get("v21b_source_checkpoint_sha256") != V21B_WARM_START_SHA256:
        raise PostformalEvalError(f"{actual_cell} adjacent config warm-start SHA is not the registered v20 G4 checkpoint")
    if f3_context is not None:
        _validate_signed_materialized_parity(config, cell=actual_cell, formal_root=cell_root, f3_context=f3_context)
    return {
        "schema": "a2_piper_base_v21B_formal_cell_completion_v1",
        "status": "FORMAL_COMPLETION_PASS",
        "cell": actual_cell,
        "seed": V21B_CELL_FACTORS[actual_cell]["seed"],
        "formal_root": str(cell_root),
        "metrics_path": str(metrics_path.resolve()),
        "metric_row_count": len(metric_rows),
        "first_batch_index": metric_rows[0]["batch_index"],
        "last_batch_index": last["batch_index"],
        "last_producer_state": last["producer_state"],
        "finite_data_final": last["metrics"]["finite_data"],
        "output_log_path": str(output_log.resolve()),
        "checkpoint_rows": checkpoint_rows,
        "last_checkpoint_path": str((cell_root / "last.pt").resolve()),
        "config_path": str(config_path.resolve()),
        "config_sha256": sha256_file(config_path),
        "warm_start_path": str(config.get("checkpoint")) if isinstance(config.get("checkpoint"), str) else None,
        "warm_start_sha256": next(
            (row.get("source_checkpoint_sha256") for row in metric_rows if isinstance(row.get("source_checkpoint_sha256"), str)),
            None,
        ),
        **{identity_key: first[identity_key] for identity_key in identity_keys},
    }


def validate_formal_completion(formal_root: Path, *, f3_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate all seven cells and the exact 70-checkpoint topology."""

    formal_root = _regular_dir(formal_root, name="v21-B formal root")
    if not isinstance(f3_context, Mapping) or f3_context.get("status") != "F3_VALIDATED":
        raise PostformalEvalError("formal completion requires a validated signed F3 context")
    f3_root = f3_context.get("root")
    if not isinstance(f3_root, str) or not f3_root:
        raise PostformalEvalError("formal completion requires the authenticated F3 root receipt")
    authenticated_f3 = validate_f3_promotion(Path(f3_root))
    required_f3 = (
        "root", "adaptation_path", "adaptation_sha256", "materialization_path", "materialization_file_sha256",
        "adaptation_bundle_sha256",
        "materialization_sha256", "config_sha256_by_cell", "materialized_config_sha256_by_cell",
        "materialized_config_path_by_cell", "source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256",
    )
    if any(key not in f3_context for key in required_f3):
        raise PostformalEvalError("formal completion F3 context is missing signed materialization identity")
    for key in required_f3:
        if f3_context.get(key) != authenticated_f3.get(key):
            raise PostformalEvalError(f"formal completion F3 receipt field {key} does not match authenticated artifacts")
    f3_context = authenticated_f3
    cells = {
        cell: validate_formal_cell(formal_root / cell, cell=cell, f3_context=f3_context)
        for cell in V21B_CELL_ORDER
    }
    if len(cells) != 7 or len(set(cells)) != 7 or set(cells) != set(V21B_CELL_ORDER):
        raise PostformalEvalError("formal completion requires exactly seven unique B1..B7 cells")
    checkpoint_ids = {(cell, row["step"]) for cell, report in cells.items() for row in report["checkpoint_rows"]}
    if len(checkpoint_ids) != 70:
        raise PostformalEvalError(f"formal completion checkpoint topology must contain exactly 70 rows; got {len(checkpoint_ids)}")
    return {
        "schema": FORMAL_COMPLETION_SCHEMA,
        "status": "FORMAL_COMPLETION_PASS",
        "plan_id": V21B_PLAN_ID,
        "execution_id": V21B_EXECUTION_ID,
        "formal_root": str(formal_root),
        "iterations": V21B_FORMAL_ITERATIONS,
        "checkpoint_steps": list(V21B_FORMAL_CHECKPOINT_STEPS),
        "cell_count": len(cells),
        "checkpoint_count": len(checkpoint_ids),
        "cells": cells,
    }


def validate_f3_promotion(f3_root: Path) -> dict[str, Any]:
    """Validate the signed F3 adaptation/materialization contract."""

    f3_root = _regular_dir(f3_root, name="v21-B F3 root")
    adaptation_path = f3_root / "V21B_F3_ADAPTATION_FROZEN.json"
    materialization_path = f3_root / "V21B_FORMAL_PROMOTION_MATERIALIZATION.json"
    adaptation = _load_json(_regular_file(adaptation_path, name="F3 adaptation"))
    materialization = _load_json(_regular_file(materialization_path, name="F3 materialization"))
    if adaptation.get("schema") != "a2_piper_base_v21B_adaptation_freeze_v1" or adaptation.get("status") != "ADAPTATION_FROZEN":
        raise PostformalEvalError("F3 adaptation schema/status is invalid")
    decision = adaptation.get("decision")
    if not isinstance(decision, Mapping) or decision.get("mode") != "THETA_ONLY_FALLBACK_F3" or decision.get("census_status") not in {"CENSUS_RIGHT_CENSORED", "BOUNDARY_NOT_SEPARABLE"}:
        raise PostformalEvalError("F3 adaptation does not carry the signed theta-only fallback")
    if decision.get("dv4_tested") is not False:
        raise PostformalEvalError("F3 adaptation must bind dv4_tested=false")
    adaptation_sha = hashlib.sha256(canonical_json_bytes(dict(adaptation))).hexdigest()
    if materialization.get("schema") != "a2_piper_base_v21B_runtime_config_materialization_v1" or materialization.get("status") != "MATERIALIZATION_PASS":
        raise PostformalEvalError("F3 formal materialization schema/status is invalid")
    if materialization.get("phase") != "FORMAL_PROMOTED" or materialization.get("immutable_after_write") is not True:
        raise PostformalEvalError("F3 formal materialization must be immutable FORMAL_PROMOTED")
    materialization_unsigned = dict(materialization)
    declared_materialization = materialization_unsigned.pop("materialization_sha256", None)
    materialization_self_hash = hashlib.sha256(canonical_json_bytes(materialization_unsigned)).hexdigest()
    if declared_materialization != materialization_self_hash:
        raise PostformalEvalError("F3 materialization self-hash is invalid")
    source_artifacts = adaptation.get("source_artifacts")
    if not isinstance(source_artifacts, Mapping):
        raise PostformalEvalError("F3 adaptation source_artifacts are required")
    expected_source_artifacts = {
        "p0_admission": ("a2_piper_base_v21B_p0_admission_v1", "STATIC_PASS"),
        "source_lock": ("a2_piper_base_v21B_source_lock_v1", "STATIC_PASS"),
        "census": ("a2_piper_base_v21B_torque_census_v1", "CENSUS_RIGHT_CENSORED"),
    }
    for name, (schema_name, status_name) in expected_source_artifacts.items():
        artifact = source_artifacts.get(name)
        if not isinstance(artifact, Mapping) or artifact.get("schema") != schema_name or artifact.get("status") != status_name:
            raise PostformalEvalError(f"F3 source artifact {name} schema/status is invalid")
    if adaptation_sha != materialization.get("adaptation_bundle_sha256"):
        raise PostformalEvalError("F3 materialization adaptation bundle does not bind the canonical frozen adaptation artifact")
    configs = materialization.get("configs")
    if (
        not isinstance(configs, list)
        or len(configs) != 7
        or any(not isinstance(row, Mapping) for row in configs)
        or len({row.get("cell") for row in configs}) != 7
        or {row.get("cell") for row in configs} != set(V21B_CELL_ORDER)
    ):
        raise PostformalEvalError("F3 materialization must contain exactly B1..B7 configs")
    for row in configs:
        if not isinstance(row, Mapping):
            raise PostformalEvalError("F3 materialization config row must be an object")
        if row.get("f3_fallback") is not True or row.get("selected_limit_nm") is not None:
            raise PostformalEvalError("F3 materialization must keep ARM_V20 and no realistic numeric limit")
        _digest(row.get("sha256"), name="F3 materialized config sha256")
        materialized_path = _regular_file(Path(row.get("path", "")), name=f"F3 {row.get('cell')} materialized config")
        if sha256_file(materialized_path) != row.get("sha256"):
            raise PostformalEvalError(f"F3 {row.get('cell')} materialized config file hash changed")
    source_checkpoint = adaptation.get("source_checkpoint_sha256")
    source_lock = adaptation.get("source_lock_sha256")
    source_artifacts = adaptation.get("source_artifacts")
    census_source = source_artifacts.get("census") if isinstance(source_artifacts, Mapping) else None
    source_config = adaptation.get("source_config_sha256")
    if source_config is None and isinstance(census_source, Mapping):
        source_config = census_source.get("source_config_sha256")
    adaptation_digest = materialization.get("adaptation_bundle_sha256")
    materialization_digest = materialization.get("materialization_sha256")
    _digest(adaptation_digest, name="F3 adaptation bundle sha256")
    _digest(materialization_digest, name="F3 materialization sha256")
    _digest(source_checkpoint, name="F3 source checkpoint sha256")
    _digest(source_lock, name="F3 source lock sha256")
    _digest(source_config, name="F3 source config sha256")
    p0_cells = source_artifacts["p0_admission"].get("cells")
    if (
        not isinstance(p0_cells, list)
        or len(p0_cells) != 7
        or any(not isinstance(row, Mapping) for row in p0_cells)
        or len({row.get("cell") for row in p0_cells}) != 7
        or {row.get("cell") for row in p0_cells} != set(V21B_CELL_ORDER)
    ):
        raise PostformalEvalError("F3 P0 source artifact must contain exact per-cell source configs")
    config_sha256_by_cell: dict[str, str] = {}
    for row in p0_cells:
        if not isinstance(row, Mapping) or row.get("cell") not in V21B_CELL_ORDER:
            raise PostformalEvalError("F3 P0 source config row is invalid")
        source_config_digest = _digest(row.get("config_sha256"), name=f"F3 {row.get('cell')} source config sha256")
        config_sha256_by_cell[str(row["cell"])] = source_config_digest
    if dict(adaptation.get("config_sha256_by_cell", {})) != config_sha256_by_cell:
        raise PostformalEvalError("F3 adaptation source config hash map is not bound to P0 files")
    return {
        "schema": "a2_piper_base_v21B_f3_context_v1",
        "status": "F3_VALIDATED",
        "root": str(f3_root),
        "adaptation_path": str(adaptation_path.resolve()),
        "adaptation_sha256": adaptation_sha,
        "adaptation_bundle_sha256": adaptation_digest,
        "materialization_path": str(materialization_path.resolve()),
        "materialization_sha256": declared_materialization,
        "materialization_file_sha256": sha256_file(materialization_path),
        "mode": decision["mode"],
        "census_status": decision["census_status"],
        "dv4_tested": False,
        "theta_ladder": dict(V21B_F3_THETA_LADDER),
        "source_checkpoint_sha256": source_checkpoint,
        "source_lock_sha256": source_lock,
        "source_config_sha256": source_config,
        "config_sha256_by_cell": dict(adaptation.get("config_sha256_by_cell", {})),
        "materialized_config_sha256_by_cell": {
            row["cell"]: row["sha256"] for row in configs
        },
        "materialized_config_path_by_cell": {
            row["cell"]: row["path"] for row in configs if isinstance(row.get("path"), str)
        },
    }


def _eval_command(
    *,
    checkpoint_path: Path,
    config_path: Path,
    output_root: Path,
    cell: str,
    seed: int,
    gpu: int,
    evaluated_checkpoint_sha256: str,
    source_lock_sha256: str,
    source_config_sha256: str,
    materialization_sha256: str,
    materialized_config_sha256: str,
    adaptation_bundle_sha256: str,
    legacy_strict_telemetry: bool,
    topology: str = "canonical16",
    aggregation_topology: str = "canonical16",
    queue_row_id: str | None = None,
    evaluation_root: Path | str | None = None,
    run_uuid: str | None = None,
    scenario_manifest: Mapping[str, Any] | None = None,
    step: int | None = None,
) -> tuple[list[str], dict[str, str]]:
    if not isinstance(legacy_strict_telemetry, bool):
        raise PostformalEvalError("legacy_strict_telemetry must be an exact bool")
    _validate_eval_gpu(gpu, name="Route-A evaluation GPU")
    if topology not in RUNTIME_SCENARIO_TOPOLOGIES:
        raise PostformalEvalError("runtime scenario topology must be canonical16 or heavy16")
    if aggregation_topology not in EVIDENCE_AGGREGATION_TOPOLOGIES:
        raise PostformalEvalError("evidence aggregation topology is not registered")
    if not isinstance(queue_row_id, str) or not queue_row_id:
        raise PostformalEvalError("postformal evaluation command requires queue_row_id")
    evaluation_root = str(Path(evaluation_root or output_root).expanduser().resolve())
    if not evaluation_root:
        raise PostformalEvalError("postformal evaluation command requires evaluation_root")
    if not isinstance(run_uuid, str) or not run_uuid:
        step_match = FORMAL_CHECKPOINT_RE.fullmatch(checkpoint_path.name)
        derived_step = int(step_match.group("step")) if step_match else 0
        run_uuid = f"v21B-routeA-{cell}-step{derived_step:04d}-seed{seed}-{topology}"
    if any(char.isspace() for char in run_uuid):
        raise PostformalEvalError("evaluation run_uuid must not contain whitespace")
    config = _load_adjacent_config(config_path)
    if scenario_manifest is None:
        scenario_manifest = _validate_signed_manifest(
            DEFAULT_SCENARIO_MANIFEST,
            source_checkpoint_sha256=V21B_WARM_START_SHA256,
            source_lock_sha256=source_lock_sha256,
        )
    if not isinstance(scenario_manifest, Mapping) or not isinstance(scenario_manifest.get("manifest"), Mapping):
        raise PostformalEvalError("signed scenario manifest bindings are required")
    for key in (
        "path", "file_sha256", "manifest_sha256", "canonical_manifest_sha256",
        "manifest_json", "manifest_json_sha256", "materialization_sha256",
    ):
        if key not in scenario_manifest:
            raise PostformalEvalError(f"signed scenario manifest binding is missing {key}")
    manifest = scenario_manifest["manifest"]
    overrides: list[str] = []

    def add(key: str, value: Any, *, string: bool = False) -> None:
        overrides.append(_hydra_override(config, key, value, string=string))

    add("checkpoint", str(checkpoint_path), string=True)
    add("checkpoint_load_mode", "full")
    add("auto_load_latest", False)
    add("headless", True)
    add("num_envs", 16)
    add("seed", seed)
    add("use_wandb", False)
    add("simulator.config.cameras.enable_cameras", False)
    add("simulator.config.render_results", False)
    add("algo.config.eval.num_eval_episodes", 16)
    add("algo.config.eval.eval_num_envs_episodes", True)
    add("algo.config.eval.a2_diagnostic_trace_enabled", True)
    diagnostic_terms = "[" + ",".join(ROUTE_A_DIAGNOSTIC_REWARD_TERMS) + "]"
    add("algo.config.eval.a2_diagnostic_reward_terms", diagnostic_terms)
    add("algo.config.eval.a2_eval_v20_strict_telemetry", legacy_strict_telemetry)
    add("algo.config.eval.a2_eval_m41_strict_telemetry", legacy_strict_telemetry)
    add("algo.config.eval.save_videos", False)
    add("algo.config.eval.save_trajectories", False)
    add("env.config.a2_v21B_cell", cell)
    add("env.config.a2_v21B_source_checkpoint_path", V21B_WARM_START_PATH, string=True)
    add("env.config.a2_v21B_source_checkpoint_sha256", V21B_WARM_START_SHA256)
    add("env.config.a2_v21B_source_lock_sha256", source_lock_sha256)
    add("env.config.a2_v21B_source_config_sha256", source_config_sha256)
    add("env.config.a2_v21B_materialization_sha256", materialization_sha256)
    add("env.config.a2_v21B_materialized_config_sha256", materialized_config_sha256)
    add("env.config.a2_v21B_adaptation_bundle_sha256", adaptation_bundle_sha256)
    add("env.config.a2_v21B_evaluated_checkpoint_path", str(checkpoint_path), string=True)
    add("env.config.a2_v21B_evaluated_checkpoint_sha256", evaluated_checkpoint_sha256)
    add("env.config.a2_v21B_terminal_export_root", str(output_root), string=True)
    add("env.config.a2_v21B_run_uuid", run_uuid, string=True)
    add("env.config.a2_v21B_census_topology", topology)
    add("env.config.a2_v21B_evidence_aggregation_topology", aggregation_topology)
    add("env.config.a2_v21B_queue_row_id", queue_row_id, string=True)
    add("env.config.a2_v21B_evaluation_root", evaluation_root, string=True)
    add("env.config.a2_v21B_signed_probe_scenarios_enabled", True)
    add("env.config.a2_v21B_scenario_manifest_path", scenario_manifest["path"], string=True)
    add("env.config.a2_v21B_scenario_manifest_sha256", scenario_manifest["manifest_sha256"])
    add("env.config.a2_v21B_scenario_manifest_file_sha256", scenario_manifest["file_sha256"])
    add("env.config.a2_v21B_canonical_manifest_sha256", scenario_manifest["canonical_manifest_sha256"])
    add("env.config.a2_v21B_scenario_manifest_source_checkpoint_sha256", manifest["source_checkpoint_sha256"])
    add("env.config.a2_v21B_scenario_manifest_source_lock_sha256", manifest["source_lock_sha256"])
    add("env.config.a2_v21B_scenario_manifest_source_config_sha256", manifest["source_config_sha256"])
    add("env.config.a2_v21B_scenario_manifest_materialization_sha256", scenario_manifest["materialization_sha256"])
    add("env.config.a2_v21B_scenario_manifest_json_sha256", scenario_manifest["manifest_json_sha256"])
    add("env.config.a2_v21B_scenario_manifest_json", scenario_manifest["manifest_json"], string=True)
    add("env.config.a2_v20_R2_seed", seed)
    add("env.config.a2_v20_R2_full_evidence", True)
    add("env.config.a2_v20_R2_evidence_enabled", True)
    add("env.config.a2_v21B_evidence_enabled", True)
    step_match = FORMAL_CHECKPOINT_RE.fullmatch(checkpoint_path.name)
    derived_step = int(step_match.group("step")) if step_match else 0
    if step is None:
        step = derived_step
    if isinstance(step, bool) or not isinstance(step, int) or step <= 0:
        raise PostformalEvalError("evaluation command step must be a positive integer")
    if step_match is not None and step != derived_step:
        raise PostformalEvalError("evaluation command step does not match evaluated checkpoint filename")
    add("eval_name", f"v21B_{cell}_step{step:04d}_{topology}_seed{seed}", string=True)
    add("eval_output_dir", str(output_root), string=True)
    argv = [
        "/home/baoquanc/anaconda3/envs/isaaclab/bin/python",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"--config-dir={config_path.parent}",
        f"--config-name={config_path.stem}",
        *overrides,
    ]
    env = {
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
    }
    argv.append(COMMAND_IDENTITY_OVERRIDE + command_sha256(argv, env))
    return argv, env


def build_route_a_manifest(
    formal_completion: Mapping[str, Any],
    *,
    evaluation_root: Path | None = None,
    f3_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build exactly 70 immutable B×checkpoint Route-A rows."""

    if formal_completion.get("schema") != FORMAL_COMPLETION_SCHEMA or formal_completion.get("status") != "FORMAL_COMPLETION_PASS":
        raise PostformalEvalError("Route-A manifest requires a validated formal completion report")
    cells = formal_completion.get("cells")
    if not isinstance(cells, Mapping) or set(cells) != set(V21B_CELL_ORDER):
        raise PostformalEvalError("Route-A manifest requires exact B1..B7 formal cells")
    base_root = Path(evaluation_root or Path("route_a")).expanduser().resolve()
    scenario_manifest = _validate_signed_manifest(
        DEFAULT_SCENARIO_MANIFEST,
        source_checkpoint_sha256=V21B_WARM_START_SHA256,
        source_lock_sha256=(f3_context or {}).get("source_lock_sha256") or str(formal_completion["cells"]["B1"]["source_lock_sha256"]),
    )
    rows: list[dict[str, Any]] = []
    for cell in V21B_CELL_ORDER:
        report = cells[cell]
        checkpoint_rows = report.get("checkpoint_rows")
        if not isinstance(checkpoint_rows, list) or len(checkpoint_rows) != len(V21B_FORMAL_CHECKPOINT_STEPS):
            raise PostformalEvalError(f"{cell} formal checkpoint rows are incomplete")
        config_path = _regular_file(Path(report["config_path"]), name=f"{cell} checkpoint-adjacent config")
        config_sha = sha256_file(config_path)
        identity = {
            key: report.get(key)
            for key in (
                "source_lock_sha256",
                "source_config_sha256",
                "materialization_sha256",
                "materialized_config_sha256",
                "adaptation_bundle_sha256",
            )
        }
        for key, value in identity.items():
            _digest(value, name=f"{cell} formal {key}")
        if f3_context is not None:
            if f3_context.get("status") != "F3_VALIDATED":
                raise PostformalEvalError("Route-A manifest f3_context is not validated")
            expected_identity = {
                "source_lock_sha256": f3_context.get("source_lock_sha256"),
                "adaptation_bundle_sha256": f3_context.get("adaptation_bundle_sha256"),
            }
            for key, expected in expected_identity.items():
                _digest(expected, name=f"F3 {key}")
                if identity[key] != expected:
                    raise PostformalEvalError(f"{cell} Route-A {key} is not bound to F3")
            expected_source_config = f3_context.get("config_sha256_by_cell", {}).get(cell)
            _digest(expected_source_config, name=f"F3 {cell} source config sha256")
            if identity["source_config_sha256"] != expected_source_config:
                raise PostformalEvalError(f"{cell} Route-A source config is not bound to F3")
            expected_materialized = f3_context.get("materialized_config_sha256_by_cell", {}).get(cell)
            _digest(expected_materialized, name=f"F3 {cell} materialized config sha256")
            if identity["materialized_config_sha256"] != expected_materialized:
                raise PostformalEvalError(f"{cell} Route-A materialized config is not bound to F3")
        seed = V21B_CELL_FACTORS[cell]["seed"]
        training_gpu = V21B_CELL_FACTORS[cell]["gpu"]
        gpu = V21B_EVAL_GPU_BY_CELL[cell]
        for checkpoint in checkpoint_rows:
            step = checkpoint.get("step")
            if step not in V21B_FORMAL_CHECKPOINT_STEPS:
                raise PostformalEvalError(f"{cell} Route-A checkpoint step is invalid")
            evaluated = _regular_file(Path(checkpoint["path"]), name=f"{cell} evaluated checkpoint {step}")
            evaluated_sha = _digest(checkpoint.get("sha256"), name=f"{cell} evaluated checkpoint sha256")
            if evaluated_sha != sha256_file(evaluated):
                raise PostformalEvalError(f"{cell} evaluated checkpoint hash changed after formal validation")
            output_root = base_root / cell / f"step{int(step):04d}" / "canonical16" / f"seed{seed}"
            run_uuid = f"v21B-routeA-{cell}-step{int(step):04d}-seed{seed}-canonical16"
            argv, env = _eval_command(
                checkpoint_path=evaluated,
                config_path=config_path,
                output_root=output_root,
                cell=cell,
                seed=seed,
                gpu=gpu,
                evaluated_checkpoint_sha256=evaluated_sha,
                source_lock_sha256=identity["source_lock_sha256"],
                source_config_sha256=identity["source_config_sha256"],
                materialization_sha256=identity["materialization_sha256"],
                materialized_config_sha256=identity["materialized_config_sha256"],
                adaptation_bundle_sha256=identity["adaptation_bundle_sha256"],
                legacy_strict_telemetry=False,
                topology="canonical16",
                aggregation_topology="canonical16",
                queue_row_id=f"{cell}:step{int(step):04d}",
                evaluation_root=output_root,
                run_uuid=run_uuid,
                scenario_manifest=scenario_manifest,
            )
            rows.append({
                "row_id": f"{cell}:step{int(step):04d}",
                "cell": cell,
                "step": int(step),
                "topology": "canonical16",
                "runtime_scenario_topology": "canonical16",
                "evidence_aggregation_topology": "canonical16",
                "seed": seed,
                "physical_gpu": gpu,
                "training_gpu": training_gpu,
                "source_checkpoint_path": V21B_WARM_START_PATH,
                "source_checkpoint_sha256": V21B_WARM_START_SHA256,
                **identity,
                "materialization_phase": "FORMAL_PROMOTED",
                "arm_profile": "ARM_V20",
                "theta_send_rad": V21B_F3_THETA_LADDER[cell],
                "evaluated_checkpoint_path": str(evaluated),
                "evaluated_checkpoint_sha256": evaluated_sha,
                "checkpoint_path": str(evaluated),
                "checkpoint_sha256": evaluated_sha,
                "config_path": str(config_path),
                "config_sha256": config_sha,
                "evaluation_root": str(output_root),
                "run_uuid": run_uuid,
                "scenario_manifest_path": scenario_manifest["path"],
                "scenario_manifest_sha256": scenario_manifest["manifest_sha256"],
                "scenario_manifest_file_sha256": scenario_manifest["file_sha256"],
                "canonical_manifest_sha256": scenario_manifest["canonical_manifest_sha256"],
                "first_episode_only": True,
                "episodes": 16,
                "argv": argv,
                "env": env,
                "evaluation_command_sha256": _declared_command_identity(argv, env),
                "expected_env_ids": list(range(16)),
                "queue_row_id": f"{cell}:step{int(step):04d}",
            })
    manifest = {
        "schema": ROUTE_A_MANIFEST_SCHEMA,
        "plan_id": V21B_PLAN_ID,
        "execution_id": V21B_EXECUTION_ID,
        "route": "A",
        "topology": "7 cells x 10 numeric checkpoints",
        "row_count": len(rows),
        "source_checkpoint_path": V21B_WARM_START_PATH,
        "source_checkpoint_sha256": V21B_WARM_START_SHA256,
        "f3_mode": None if f3_context is None else f3_context.get("mode"),
        "f3_census_status": None if f3_context is None else f3_context.get("census_status"),
        "checkpoint_steps": list(V21B_FORMAL_CHECKPOINT_STEPS),
        "eval_allowed_gpus": list(V21B_EVAL_GPUS),
        "eval_gpu_by_cell": dict(V21B_EVAL_GPU_BY_CELL),
        "last_pt_excluded": True,
        "rows": rows,
    }
    validate_route_a_manifest(manifest, check_files=True)
    manifest["manifest_sha256"] = hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
    return manifest


def validate_route_a_manifest(manifest: Mapping[str, Any], *, check_files: bool = True) -> None:
    if not isinstance(manifest, Mapping) or manifest.get("schema") != ROUTE_A_MANIFEST_SCHEMA:
        raise PostformalEvalError("Route-A manifest schema is invalid")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != 70:
        raise PostformalEvalError("Route-A manifest requires exactly 70 rows")
    if manifest.get("row_count") != 70 or manifest.get("topology") != "7 cells x 10 numeric checkpoints":
        raise PostformalEvalError("Route-A manifest cardinality metadata is invalid")
    if manifest.get("last_pt_excluded") is not True:
        raise PostformalEvalError("Route-A manifest must exclude last.pt")
    if tuple(manifest.get("eval_allowed_gpus", ())) != V21B_EVAL_GPUS or manifest.get("eval_gpu_by_cell") != V21B_EVAL_GPU_BY_CELL:
        raise PostformalEvalError("Route-A manifest evaluation GPU policy is not the current physical 0..3 mapping")
    identities: set[tuple[str, int]] = set()
    roots: set[str] = set()
    run_uuids: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise PostformalEvalError("Route-A rows must be mappings")
        cell, step = row.get("cell"), row.get("step")
        if cell not in V21B_CELL_ORDER or isinstance(step, bool) or step not in V21B_FORMAL_CHECKPOINT_STEPS:
            raise PostformalEvalError("Route-A row cell/step is invalid")
        if (cell, step) in identities:
            raise PostformalEvalError("Route-A B×step identities are duplicated")
        identities.add((cell, step))
        factors = V21B_CELL_FACTORS[cell]
        if row.get("topology") != "canonical16" or row.get("runtime_scenario_topology") != "canonical16" or row.get("evidence_aggregation_topology") != "canonical16" or row.get("seed") != factors["seed"] or row.get("training_gpu") != factors["gpu"] or row.get("physical_gpu") != V21B_EVAL_GPU_BY_CELL[cell]:
            raise PostformalEvalError(f"Route-A {cell} step{step} factor binding is invalid")
        _validate_eval_gpu(row.get("physical_gpu"), name=f"Route-A {cell} eval GPU")
        if row.get("first_episode_only") is not True or row.get("episodes") != 16:
            raise PostformalEvalError("Route-A row must be first-episode canonical16")
        if row.get("expected_env_ids") != list(range(16)):
            raise PostformalEvalError("Route-A row must bind exact env IDs 0..15")
        if row.get("queue_row_id") != row.get("row_id") or row.get("evaluation_root") is None:
            raise PostformalEvalError("Route-A row queue identity is incomplete")
        if row.get("source_checkpoint_path") != V21B_WARM_START_PATH or row.get("source_checkpoint_sha256") != V21B_WARM_START_SHA256:
            raise PostformalEvalError("Route-A warm-start lineage is not bound")
        for identity_key in (
            "source_lock_sha256",
            "source_config_sha256",
            "materialization_sha256",
            "materialized_config_sha256",
            "adaptation_bundle_sha256",
        ):
            _digest(row.get(identity_key), name=f"Route-A {identity_key}")
        if row.get("materialization_phase") != "FORMAL_PROMOTED" or row.get("arm_profile") != "ARM_V20":
            raise PostformalEvalError("Route-A F3 materialization/profile binding is invalid")
        if row.get("theta_send_rad") != V21B_F3_THETA_LADDER[cell]:
            raise PostformalEvalError("Route-A theta is not bound to the F3 ladder")
        evaluated_path = _canonical_path(row.get("evaluated_checkpoint_path"), name="Route-A evaluated checkpoint")
        if evaluated_path.name == "last.pt" or FORMAL_CHECKPOINT_RE.fullmatch(evaluated_path.name) is None:
            raise PostformalEvalError("Route-A evaluated checkpoint must be a numbered model_step file")
        expected_step = int(FORMAL_CHECKPOINT_RE.fullmatch(evaluated_path.name).group("step"))
        if expected_step != step:
            raise PostformalEvalError("Route-A evaluated checkpoint path/step mismatch")
        evaluated_sha = _digest(row.get("evaluated_checkpoint_sha256"), name="Route-A evaluated checkpoint sha256")
        if row.get("checkpoint_path") != row.get("evaluated_checkpoint_path") or row.get("checkpoint_sha256") != evaluated_sha:
            raise PostformalEvalError("Route-A checkpoint aliases do not bind evaluated identity")
        config_path = _canonical_path(row.get("config_path"), name="Route-A config")
        config_sha = _digest(row.get("config_sha256"), name="Route-A config sha256")
        argv = row.get("argv")
        env = row.get("env")
        if not isinstance(argv, list) or not isinstance(env, Mapping):
            raise PostformalEvalError("Route-A command identity is incomplete")
        if row.get("evaluation_command_sha256") != _declared_command_identity(argv, env):
            raise PostformalEvalError("Route-A command sha256 does not bind argv/environment")
        output_root = row.get("evaluation_root")
        if not isinstance(output_root, str) or not output_root:
            raise PostformalEvalError("Route-A evaluation root is required")
        roots.add(output_root)
        run_uuid = row.get("run_uuid")
        if not isinstance(run_uuid, str) or not run_uuid or any(char.isspace() for char in run_uuid):
            raise PostformalEvalError("Route-A run_uuid must be a unique non-empty token")
        if run_uuid in run_uuids:
            raise PostformalEvalError("Route-A run_uuid values must be unique per invocation")
        run_uuids.add(run_uuid)
        if not any(
            item.startswith(("env.config.a2_v21B_run_uuid=", "+env.config.a2_v21B_run_uuid="))
            and item.split("=", 1)[1].strip("'") == run_uuid
            for item in argv
        ):
            raise PostformalEvalError("Route-A command does not bind its run_uuid")
        if not any(item.split("=", 1)[1].strip("'\"") == row.get("row_id") and item.split("=", 1)[0].lstrip("+") == "env.config.a2_v21B_queue_row_id" for item in argv if "=" in item):
            raise PostformalEvalError("Route-A command does not bind its queue row ID")
        if not any(item.split("=", 1)[1].strip("'\"") == str(row.get("evaluation_root")) and item.split("=", 1)[0].lstrip("+") == "env.config.a2_v21B_evaluation_root" for item in argv if "=" in item):
            raise PostformalEvalError("Route-A command does not bind its evaluation root")
        if not any(item in argv for item in (f"seed={row.get('seed')}", f"+seed={row.get('seed')}")):
            raise PostformalEvalError("Route-A command does not bind the global seed")
        if not any(item in argv for item in (f"env.config.a2_v20_R2_seed={row.get('seed')}", f"+env.config.a2_v20_R2_seed={row.get('seed')}")):
            raise PostformalEvalError("Route-A command does not bind env.config.a2_v20_R2_seed")
        if any("a2_v21B_strict_task_trace" in item for item in argv):
            raise PostformalEvalError("Route-A command uses an unconsumed strict-task-trace override")
        if not any("a2_v21B_signed_probe_scenarios_enabled=true" in item for item in argv):
            raise PostformalEvalError("Route-A command does not bind signed probe admission")
        for key in ("scenario_manifest_path", "scenario_manifest_sha256", "scenario_manifest_file_sha256", "canonical_manifest_sha256"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise PostformalEvalError(f"Route-A scenario manifest binding {key} is missing")
        for key in ("scenario_manifest_sha256", "scenario_manifest_file_sha256", "canonical_manifest_sha256"):
            _digest(row[key], name=f"Route-A {key}")
        if check_files:
            if sha256_file(evaluated_path) != evaluated_sha:
                raise PostformalEvalError("Route-A evaluated checkpoint SHA-256 mismatch")
            if sha256_file(config_path) != config_sha:
                raise PostformalEvalError("Route-A checkpoint-adjacent config SHA-256 mismatch")
            scenario_path = _regular_file(Path(row["scenario_manifest_path"]), name="Route-A signed scenario manifest")
            if sha256_file(scenario_path) != row["scenario_manifest_file_sha256"]:
                raise PostformalEvalError("Route-A signed scenario manifest file hash mismatch")
    if identities != {(cell, step) for cell in V21B_CELL_ORDER for step in V21B_FORMAL_CHECKPOINT_STEPS}:
        raise PostformalEvalError("Route-A manifest does not contain exact B1..B7 × 250..2500")
    if len(roots) != 70:
        raise PostformalEvalError("Route-A evaluation roots must be unique per B×step row")


def build_route_a_queue(manifest: Mapping[str, Any]) -> dict[str, Any]:
    validate_route_a_manifest(manifest, check_files=False)
    rows = [dict(row) for row in manifest["rows"]]
    queue = {
        "schema": ROUTE_A_QUEUE_SCHEMA,
        "plan_id": V21B_PLAN_ID,
        "manifest_sha256": manifest.get("manifest_sha256") or hashlib.sha256(canonical_json_bytes(dict(manifest))).hexdigest(),
        "serial": True,
        "gpu7_forbidden": True,
        "eval_allowed_gpus": list(V21B_EVAL_GPUS),
        "eval_gpu_by_cell": dict(V21B_EVAL_GPU_BY_CELL),
        "row_count": len(rows),
        "rows": rows,
    }
    queue["receipt_sha256"] = _queue_receipt(queue)
    validate_route_a_queue(queue)
    return queue


def validate_route_a_queue(queue: Mapping[str, Any]) -> None:
    if queue.get("schema") != ROUTE_A_QUEUE_SCHEMA or tuple(queue.get("eval_allowed_gpus", ())) != V21B_EVAL_GPUS or queue.get("eval_gpu_by_cell") != V21B_EVAL_GPU_BY_CELL:
        raise PostformalEvalError("Route-A queue evaluation GPU policy is invalid")
    rows = queue.get("rows")
    if not isinstance(rows, list) or len(rows) != 70:
        raise PostformalEvalError("Route-A queue requires exactly 70 rows")
    _digest(queue.get("receipt_sha256"), name="Route-A queue receipt_sha256")
    if queue.get("receipt_sha256") != _queue_receipt(queue):
        raise PostformalEvalError("Route-A queue receipt does not bind immutable payload")
    for row in rows:
        if not isinstance(row, Mapping):
            raise PostformalEvalError("Route-A queue rows must be mappings")
        cell = row.get("cell")
        if cell not in V21B_EVAL_GPU_BY_CELL:
            raise PostformalEvalError("Route-A queue row cell is invalid")
        _validate_eval_gpu(row.get("physical_gpu"), name=f"Route-A queue {cell} eval GPU")
        if row.get("physical_gpu") != V21B_EVAL_GPU_BY_CELL[cell] or row.get("training_gpu") != V21B_CELL_FACTORS[cell]["gpu"]:
            raise PostformalEvalError("Route-A queue row conflates evaluation and historical training GPU identity")
        if row.get("runtime_scenario_topology", "canonical16") != "canonical16" or row.get("evidence_aggregation_topology", "canonical16") != "canonical16" or row.get("expected_env_ids", list(range(16))) != list(range(16)):
            raise PostformalEvalError("Route-A queue row topology/env coverage is invalid")
        if row.get("queue_row_id") != row.get("row_id") or not isinstance(row.get("evaluation_root"), str) or not row.get("evaluation_root"):
            raise PostformalEvalError("Route-A queue row queue identity is incomplete")
        argv = row.get("argv")
        if not isinstance(argv, list):
            raise PostformalEvalError("Route-A queue row command argv is missing")
        if row.get("evaluation_command_sha256") != _declared_command_identity(argv, row.get("env")):
            raise PostformalEvalError("Route-A queue row command identity is invalid")
        if not any(
            "=" in item
            and item.split("=", 1)[0].lstrip("+") == "env.config.a2_v21B_queue_row_id"
            and item.split("=", 1)[1].strip("'\"") == row.get("row_id")
            for item in argv
        ):
            raise PostformalEvalError("Route-A queue row command does not bind queue_row_id")
        if not any(
            "=" in item
            and item.split("=", 1)[0].lstrip("+") == "env.config.a2_v21B_evaluation_root"
            and item.split("=", 1)[1].strip("'\"") == str(row.get("evaluation_root"))
            for item in argv
        ):
            raise PostformalEvalError("Route-A queue row command does not bind evaluation_root")
        env = row.get("env")
        if not isinstance(env, Mapping) or env.get("CUDA_VISIBLE_DEVICES") != str(row.get("physical_gpu")) or env.get("ACCELERATE_TORCH_DEVICE") != "cuda:0":
            raise PostformalEvalError("Route-A queue row CUDA environment is not physically bound")


build_route_a_eval_queue = build_route_a_queue


def build_route_b_queue(
    candidate: Mapping[str, Any],
    *,
    cell: str,
    topology: str,
    output_root: Path,
    config_path: Path | None = None,
    gpu: int = 0,
    scenario_manifest_path: Path = DEFAULT_SCENARIO_MANIFEST,
) -> dict[str, Any]:
    """Build pooled/holdout command rows bound to one immutable candidate."""

    if topology not in {"pooled_seed16", "holdout_seed16"}:
        raise PostformalEvalError("Route-B command queue topology must be pooled_seed16 or holdout_seed16")
    if cell not in V21B_CELL_ORDER:
        raise PostformalEvalError(f"Route-B queue cell is invalid: {cell!r}")
    _validate_eval_gpu(gpu, name="Route-B evaluation GPU")
    required = (
        "evaluated_checkpoint_path", "evaluated_checkpoint_sha256", "config_path", "config_sha256",
        "source_lock_sha256", "source_config_sha256", "materialization_sha256",
        "materialized_config_sha256", "adaptation_bundle_sha256",
    )
    if not isinstance(candidate, Mapping):
        raise PostformalEvalError("Route-B queue requires a frozen candidate mapping")
    for key in required:
        if key not in candidate:
            raise PostformalEvalError(f"Route-B candidate is missing {key}")
        if key.endswith("sha256"):
            _digest(candidate[key], name=f"Route-B candidate {key}")
    checkpoint = _regular_file(Path(candidate["evaluated_checkpoint_path"]), name="Route-B evaluated checkpoint")
    if candidate["evaluated_checkpoint_path"] != str(checkpoint):
        raise PostformalEvalError("Route-B evaluated checkpoint path must be canonical")
    if sha256_file(checkpoint) != candidate["evaluated_checkpoint_sha256"]:
        raise PostformalEvalError("Route-B evaluated checkpoint hash changed")
    step = _route_b_checkpoint_step(candidate, checkpoint)
    config = _regular_file(Path(config_path or candidate["config_path"]), name="Route-B adjacent config")
    if candidate["config_path"] != str(config):
        raise PostformalEvalError("Route-B adjacent config path must be canonical")
    if sha256_file(config) != candidate["config_sha256"]:
        raise PostformalEvalError("Route-B adjacent config hash changed")
    scenario = _validate_signed_manifest(
        scenario_manifest_path,
        source_checkpoint_sha256=V21B_WARM_START_SHA256,
        source_lock_sha256=candidate["source_lock_sha256"],
    )
    base = Path(output_root).expanduser().resolve()
    rows: list[dict[str, Any]] = []
    for seed in _route_b_seed_contract(topology):
        run_uuid = f"v21B-routeB-{cell}-{topology}-seed{seed}"
        root = base / cell / topology / f"seed{seed}" / "canonical16"
        argv, env = _eval_command(
            checkpoint_path=checkpoint,
            config_path=config,
            output_root=root,
            cell=cell,
            seed=seed,
            gpu=gpu,
            evaluated_checkpoint_sha256=candidate["evaluated_checkpoint_sha256"],
            source_lock_sha256=candidate["source_lock_sha256"],
            source_config_sha256=candidate["source_config_sha256"],
            materialization_sha256=candidate["materialization_sha256"],
            materialized_config_sha256=candidate["materialized_config_sha256"],
            adaptation_bundle_sha256=candidate["adaptation_bundle_sha256"],
            legacy_strict_telemetry=True,
            topology="canonical16",
            aggregation_topology=topology,
            queue_row_id=f"{cell}:{topology}:seed{seed}",
            evaluation_root=root,
            run_uuid=run_uuid,
            scenario_manifest=scenario,
            step=step,
        )
        rows.append({
            "row_id": f"{cell}:{topology}:seed{seed}",
            "cell": cell,
            "step": step,
            "topology": topology,
            "runtime_topology": "canonical16",
            "runtime_scenario_topology": "canonical16",
            "evidence_aggregation_topology": topology,
            "seed": seed,
            "physical_gpu": gpu,
            "episodes": V21B_ROUTE_B_ENVS_PER_SEED,
            "first_episode_only": True,
            "run_uuid": run_uuid,
            "evaluation_root": str(root),
            "expected_env_ids": list(range(16)),
            "queue_row_id": f"{cell}:{topology}:seed{seed}",
            "candidate_identity": {**{key: candidate[key] for key in required}, "step": step},
            "source_checkpoint_path": V21B_WARM_START_PATH,
            "source_checkpoint_sha256": V21B_WARM_START_SHA256,
            "evaluated_checkpoint_path": candidate["evaluated_checkpoint_path"],
            "evaluated_checkpoint_sha256": candidate["evaluated_checkpoint_sha256"],
            "checkpoint_path": candidate["evaluated_checkpoint_path"],
            "checkpoint_sha256": candidate["evaluated_checkpoint_sha256"],
            "config_path": candidate["config_path"],
            "config_sha256": candidate["config_sha256"],
            "source_lock_sha256": candidate["source_lock_sha256"],
            "source_config_sha256": candidate["source_config_sha256"],
            "materialization_sha256": candidate["materialization_sha256"],
            "materialized_config_sha256": candidate["materialized_config_sha256"],
            "adaptation_bundle_sha256": candidate["adaptation_bundle_sha256"],
            "argv": argv,
            "env": env,
            "evaluation_command_sha256": _declared_command_identity(argv, env),
        })
    queue = {
        "schema": ROUTE_B_QUEUE_SCHEMA,
        "status": "ROUTE_B_QUEUE_READY",
        "cell": cell,
        "topology": topology,
        "step": step,
        "row_count": len(rows),
        "rows": rows,
        "candidate_identity": {**{key: candidate[key] for key in required}, "step": step},
        "eval_allowed_gpus": list(V21B_EVAL_GPUS),
        "eval_gpu": gpu,
    }
    for row in rows:
        row["row_receipt_sha256"] = _queue_row_receipt(row)
    queue["receipt_sha256"] = _queue_receipt(queue)
    validate_route_b_queue(queue)
    return queue


def validate_route_b_queue(queue: Mapping[str, Any]) -> None:
    if queue.get("schema") != ROUTE_B_QUEUE_SCHEMA or queue.get("topology") not in {"pooled_seed16", "holdout_seed16"} or tuple(queue.get("eval_allowed_gpus", ())) != V21B_EVAL_GPUS:
        raise PostformalEvalError("Route-B queue schema/topology is invalid")
    _validate_eval_gpu(queue.get("eval_gpu"), name="Route-B queue evaluation GPU")
    _digest(queue.get("receipt_sha256"), name="Route-B queue receipt_sha256")
    if queue.get("receipt_sha256") != _queue_receipt(queue):
        raise PostformalEvalError("Route-B queue receipt does not bind immutable payload")
    rows = queue.get("rows")
    expected_seeds = _route_b_seed_contract(str(queue["topology"]))
    if not isinstance(rows, list) or len(rows) != len(expected_seeds):
        raise PostformalEvalError("Route-B queue seed cardinality is invalid")
    queue_step = queue.get("step")
    if isinstance(queue_step, bool) or not isinstance(queue_step, int) or queue_step <= 0:
        raise PostformalEvalError("Route-B queue step must be a positive integer")
    queue_candidate = queue.get("candidate_identity")
    _candidate_projection(queue_candidate, keys=ROUTE_B_CANDIDATE_KEYS)
    candidate_step = queue_candidate.get("step") if isinstance(queue_candidate, Mapping) else None
    if isinstance(candidate_step, bool) or not isinstance(candidate_step, int) or candidate_step <= 0 or candidate_step != queue_step:
        raise PostformalEvalError("Route-B queue candidate step is not bound to the queue step")
    seen: set[str] = set()
    expected_row_ids = {f"{queue.get('cell')}:{queue.get('topology')}:seed{seed}" for seed in expected_seeds}
    if {row.get("row_id") for row in rows if isinstance(row, Mapping)} != expected_row_ids:
        raise PostformalEvalError("Route-B queue row IDs do not bind the declared seed queue")
    for row in rows:
        if not isinstance(row, Mapping) or row.get("seed") not in expected_seeds or row.get("episodes") != 16:
            raise PostformalEvalError("Route-B queue row seed/episode contract is invalid")
        if row.get("step") != queue_step or row.get("first_episode_only") is not True:
            raise PostformalEvalError("Route-B queue row step/first-episode contract is invalid")
        if row.get("topology") != queue.get("topology") or row.get("runtime_scenario_topology") != "canonical16" or row.get("runtime_topology") != "canonical16" or row.get("evidence_aggregation_topology") != queue.get("topology"):
            raise PostformalEvalError("Route-B queue separates runtime and evidence aggregation topology incorrectly")
        if row.get("expected_env_ids") != list(range(16)):
            raise PostformalEvalError("Route-B queue row must bind exact env IDs 0..15")
        _digest(row.get("row_receipt_sha256"), name="Route-B queue row receipt_sha256")
        unsigned_row = dict(row)
        unsigned_row.pop("row_receipt_sha256", None)
        if row.get("row_receipt_sha256") != _queue_row_receipt(unsigned_row):
            raise PostformalEvalError("Route-B queue row receipt does not bind immutable row")
        run_uuid = row.get("run_uuid")
        if not isinstance(run_uuid, str) or not run_uuid or run_uuid in seen:
            raise PostformalEvalError("Route-B queue run_uuid values must be unique")
        seen.add(run_uuid)
        if row.get("evaluation_command_sha256") != _declared_command_identity(row.get("argv"), row.get("env")):
            raise PostformalEvalError("Route-B queue command identity is invalid")
        argv = row["argv"]
        seed = row["seed"]
        _validate_eval_gpu(row.get("physical_gpu"), name="Route-B queue row evaluation GPU")
        if row.get("physical_gpu") != queue["eval_gpu"]:
            raise PostformalEvalError("Route-B queue row evaluation GPU differs from queue declaration")
        if not any(item in argv for item in (f"seed={seed}", f"+seed={seed}")) or not any(item in argv for item in (f"env.config.a2_v20_R2_seed={seed}", f"+env.config.a2_v20_R2_seed={seed}")):
            raise PostformalEvalError("Route-B queue command does not bind both seed controls")
        if not any("a2_v21B_signed_probe_scenarios_enabled=true" in item for item in argv):
            raise PostformalEvalError("Route-B queue command lacks signed probe admission")
        if row.get("env", {}).get("CUDA_VISIBLE_DEVICES") != str(queue["eval_gpu"]) or row.get("env", {}).get("ACCELERATE_TORCH_DEVICE") != "cuda:0":
            raise PostformalEvalError("Route-B queue CUDA environment is not physically bound")
        if not any(item in argv for item in (f"env.config.a2_v21B_evidence_aggregation_topology={queue['topology']}", f"+env.config.a2_v21B_evidence_aggregation_topology={queue['topology']}")):
            raise PostformalEvalError("Route-B queue command does not bind evidence aggregation topology")
        if not any(item in argv for item in ("env.config.a2_v21B_census_topology=canonical16", "+env.config.a2_v21B_census_topology=canonical16")):
            raise PostformalEvalError("Route-B queue command does not bind canonical16 runtime scenario topology")
        if row.get("queue_row_id") != row.get("row_id") or not any(item.split("=", 1)[1].strip("'\"") == row.get("row_id") and item.split("=", 1)[0].lstrip("+") == "env.config.a2_v21B_queue_row_id" for item in argv if "=" in item):
            raise PostformalEvalError("Route-B queue command does not bind its queue row ID")
        if not any(item.split("=", 1)[1].strip("'\"") == str(row.get("evaluation_root")) and item.split("=", 1)[0].lstrip("+") == "env.config.a2_v21B_evaluation_root" for item in argv if "=" in item):
            raise PostformalEvalError("Route-B queue command does not bind its evaluation root")
        candidate = queue_candidate
        if row.get("candidate_identity") != candidate:
            raise PostformalEvalError("Route-B queue row candidate identity differs from queue candidate")
        expected_row_identity = {
            "source_checkpoint_path": V21B_WARM_START_PATH,
            "source_checkpoint_sha256": V21B_WARM_START_SHA256,
            "evaluated_checkpoint_path": candidate["evaluated_checkpoint_path"],
            "evaluated_checkpoint_sha256": candidate["evaluated_checkpoint_sha256"],
            "config_path": candidate["config_path"],
            "config_sha256": candidate["config_sha256"],
            "evaluation_command_sha256": row["evaluation_command_sha256"],
            "source_lock_sha256": candidate["source_lock_sha256"],
            "source_config_sha256": candidate["source_config_sha256"],
            "materialization_sha256": candidate["materialization_sha256"],
            "materialized_config_sha256": candidate["materialized_config_sha256"],
            "adaptation_bundle_sha256": candidate["adaptation_bundle_sha256"],
        }
        if _candidate_projection(row, keys=CANDIDATE_IDENTITY_KEYS) != expected_row_identity:
            raise PostformalEvalError("Route-B queue row top-level candidate identity is not bound")
        if _candidate_projection(row, keys=RECORD_CANDIDATE_KEYS) != {
            key: expected_row_identity[key]
            for key in RECORD_CANDIDATE_KEYS
        }:
            raise PostformalEvalError("Route-B queue row record candidate identity is not bound")
        if row.get("checkpoint_path") != row.get("evaluated_checkpoint_path") or row.get("checkpoint_sha256") != row.get("evaluated_checkpoint_sha256"):
            raise PostformalEvalError("Route-B queue checkpoint aliases are not bound")


def _typed_na(reason: str) -> dict[str, Any]:
    return {"status": "N/A", "reason": reason, "denominator": 0}


def f3_dv_readout(f3_context: Mapping[str, Any]) -> dict[str, Any]:
    if f3_context.get("status") != "F3_VALIDATED":
        raise PostformalEvalError("F3 DV readout requires validated F3 context")
    reason = f3_context["census_status"] if f3_context["census_status"] in {"CENSUS_RIGHT_CENSORED", "BOUNDARY_NOT_SEPARABLE"} else DV_NA_CENSUS_REASON
    return {
        "arm_profile": "ARM_V20",
        "arm_effort_limit_nm": None,
        "dv2": _typed_na(reason),
        "dv3": _typed_na(DV_NA_F3_REASON),
        "dv4": {"value": _typed_na(DV_NA_F3_REASON), "dv4_tested": False},
        "authority": "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE",
        "real_hardware_force_claim": False,
    }


def _record_checkpoint_identity(record: Mapping[str, Any], row: Mapping[str, Any]) -> None:
    if record.get("source_checkpoint_path") != row.get("source_checkpoint_path"):
        raise PostformalEvalError("evaluation record is not bound to the warm-start checkpoint path")
    if record.get("evaluated_checkpoint_path") != row.get("evaluated_checkpoint_path") or record.get("evaluated_checkpoint_sha256") != row.get("evaluated_checkpoint_sha256"):
        raise PostformalEvalError("evaluation record is not bound to the evaluated checkpoint")
    if record.get("source_checkpoint_sha256") != row.get("source_checkpoint_sha256"):
        raise PostformalEvalError("evaluation record warm-start lineage is not bound")
    if record.get("evaluation_command_sha256") != row.get("evaluation_command_sha256"):
        raise PostformalEvalError("evaluation record command identity is not bound")
    if "run_uuid" in record and record.get("run_uuid") != row.get("run_uuid"):
        raise PostformalEvalError("evaluation record run_uuid is not bound to the queue row")


def _record_eval_identity(record: Mapping[str, Any], row: Mapping[str, Any]) -> None:
    """Require the complete source/materialization/F3 identity on each record."""

    _record_checkpoint_identity(record, row)
    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping):
        raise PostformalEvalError("evaluation record provenance is required")
    for key in (
        "source_lock_sha256",
        "source_config_sha256",
        "materialization_sha256",
        "materialized_config_sha256",
        "adaptation_bundle_sha256",
    ):
        expected = row.get(key)
        actual = provenance.get(key)
        _digest(expected, name=f"Route-A row {key}")
        if actual != expected:
            raise PostformalEvalError(f"evaluation record {key} is not bound")
    if provenance.get("cell") != row.get("cell") or provenance.get("seed") != row.get("seed"):
        raise PostformalEvalError("evaluation record cell/seed provenance is not bound")
    if provenance.get("run_uuid") not in (None, row.get("run_uuid")):
        raise PostformalEvalError("evaluation record provenance run_uuid is not bound")
    # Task records carry a top-level env_id.  ARM_V20 terminal records bind
    # env_id in provenance only; an absent top-level field remains valid.  If
    # the optional field is present, it must be an exact Python int before its
    # value is compared with provenance (bool and float 0 are not identities).
    if "env_id" in record:
        record_env_id = record["env_id"]
        if isinstance(record_env_id, bool) or not isinstance(record_env_id, int):
            raise PostformalEvalError("evaluation record top-level env_id must be a non-boolean int")
        if provenance.get("env_id") != record_env_id:
            raise PostformalEvalError("evaluation record provenance env_id is not bound")
    if row.get("row_id") is not None:
        if provenance.get("queue_row_id") != row.get("row_id") or provenance.get("evaluation_root") != row.get("evaluation_root"):
            raise PostformalEvalError("evaluation record queue_row_id/evaluation_root is not bound")
    expected_runtime = row.get("runtime_scenario_topology", row.get("runtime_topology"))
    expected_evidence = row.get("evidence_aggregation_topology", row.get("topology"))
    if provenance.get("topology") != expected_evidence or provenance.get("evidence_aggregation_topology") != expected_evidence or provenance.get("runtime_scenario_topology") != expected_runtime:
        raise PostformalEvalError("evaluation record runtime/evidence topology is not bound")


def _record_candidate_identity(record: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    """Bind immutable checkpoint/materialization identity across invocations."""

    actual = _candidate_identity_from_record(record)
    for key, value in actual.items():
        if key in candidate and candidate.get(key) != value:
            raise PostformalEvalError(f"record candidate identity {key} is not bound to the frozen candidate")
    for key in ("evaluated_checkpoint_path", "evaluated_checkpoint_sha256", "source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256", "adaptation_bundle_sha256"):
        if key not in candidate:
            raise PostformalEvalError(f"frozen candidate identity is missing {key}")


def _validate_task_identity(record: Mapping[str, Any]) -> None:
    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping):
        raise PostformalEvalError("strict task record provenance is required")
    for key in (
        "source_lock_sha256",
        "source_config_sha256",
        "materialization_sha256",
        "materialized_config_sha256",
        "adaptation_bundle_sha256",
    ):
        _digest(provenance.get(key), name=f"strict task record {key}")
    if provenance.get("cell") not in V21B_CELL_ORDER or provenance.get("seed") != record.get("seed"):
        raise PostformalEvalError("strict task record cell/seed provenance is not bound")
    if provenance.get("run_uuid") not in (None, record.get("run_uuid")):
        raise PostformalEvalError("strict task record provenance run_uuid is not bound")
    if provenance.get("env_id") not in (None, record.get("env_id")):
        raise PostformalEvalError("strict task record provenance env_id is not bound")


def _task_identity_tuple(record: Mapping[str, Any]) -> tuple[str, ...]:
    """Return immutable candidate identity, excluding invocation identity."""

    provenance = record["provenance"]
    return tuple(
        str(record.get(key))
        for key in (
            "source_checkpoint_path",
            "source_checkpoint_sha256",
            "evaluated_checkpoint_path",
            "evaluated_checkpoint_sha256",
        )
    ) + tuple(str(provenance[key]) for key in (
        "source_lock_sha256",
        "source_config_sha256",
        "materialization_sha256",
        "materialized_config_sha256",
        "adaptation_bundle_sha256",
    ))


def _candidate_identity_from_record(record: Mapping[str, Any]) -> dict[str, str]:
    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping):
        raise PostformalEvalError("candidate identity requires provenance")
    keys = (
        "source_checkpoint_path", "source_checkpoint_sha256", "evaluated_checkpoint_path",
        "evaluated_checkpoint_sha256", "source_lock_sha256", "source_config_sha256",
        "materialization_sha256", "materialized_config_sha256", "adaptation_bundle_sha256",
    )
    result: dict[str, str] = {}
    for key in keys:
        value = record.get(key) if key in {"source_checkpoint_path", "source_checkpoint_sha256", "evaluated_checkpoint_path", "evaluated_checkpoint_sha256"} else provenance.get(key)
        if not isinstance(value, str) or not value:
            raise PostformalEvalError(f"candidate identity field {key} is missing")
        if key.endswith("sha256"):
            _digest(value, name=f"candidate identity {key}")
        result[key] = value
    return result


def _validate_process_evidence_row(
    row: Mapping[str, Any],
    *,
    task_records: Sequence[Mapping[str, Any]],
    arm_records: Sequence[Mapping[str, Any]],
    expected_topologies: Sequence[str],
    route_name: str,
) -> dict[str, Any]:
    """Validate one 16-env first-episode process row for either route."""

    evidence_topology = row.get("evidence_aggregation_topology", row.get("topology"))
    runtime_topology = row.get("runtime_scenario_topology", row.get("runtime_topology"))
    if row.get("topology") not in expected_topologies or evidence_topology != row.get("topology") or runtime_topology != "canonical16" or row.get("runtime_topology", "canonical16") != "canonical16" or row.get("episodes") != 16 or row.get("first_episode_only") is not True:
        raise PostformalEvalError(f"{route_name} evidence row topology/runtime is not a canonical16 first-episode contract")
    if not isinstance(task_records, Sequence) or len(task_records) != 16:
        raise PostformalEvalError(f"{route_name} evidence requires exactly 16 strict task records")
    if not isinstance(arm_records, Sequence) or len(arm_records) != 16:
        raise PostformalEvalError(f"{route_name} evidence requires exactly 16 arm terminal records")
    task_envs: set[int] = set()
    arm_envs: set[int] = set()
    task_by_env: dict[int, Mapping[str, Any]] = {}
    arm_by_env: dict[int, Mapping[str, Any]] = {}
    for task in task_records:
        a2_v21b_validate_task_record(task)
        _record_eval_identity(task, row)
        if task.get("topology") != evidence_topology or task.get("evidence_aggregation_topology") != evidence_topology or task.get("runtime_scenario_topology") != runtime_topology or task.get("seed") != row.get("seed"):
            raise PostformalEvalError(f"{route_name} task record topology/seed mismatch")
        env_id = task.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in range(16) or env_id in task_envs:
            raise PostformalEvalError(f"{route_name} task env coverage is duplicated or malformed")
        task_envs.add(env_id)
        task_by_env[env_id] = task
    for arm in arm_records:
        a2_v21b_validate_terminal_record(arm)
        _record_eval_identity(arm, row)
        provenance = arm.get("provenance")
        if not isinstance(provenance, Mapping) or provenance.get("topology") != evidence_topology or provenance.get("evidence_aggregation_topology") != evidence_topology or provenance.get("runtime_scenario_topology") != runtime_topology or arm.get("seed") != row.get("seed"):
            raise PostformalEvalError(f"{route_name} arm record topology/seed mismatch")
        env_id = provenance.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in range(16) or env_id in arm_envs:
            raise PostformalEvalError(f"{route_name} arm env coverage is duplicated or malformed")
        arm_envs.add(env_id)
        arm_by_env[env_id] = arm
    if task_envs != set(range(16)) or arm_envs != set(range(16)):
        raise PostformalEvalError(f"{route_name} task/arm env coverage must be exactly 0..15")
    if task_envs != arm_envs:
        raise PostformalEvalError(f"{route_name} task and arm env identities differ")
    for env_id in sorted(task_envs):
        task = task_by_env[env_id]
        arm = arm_by_env[env_id]
        task_provenance = task.get("provenance")
        provenance = arm.get("provenance")
        if not isinstance(task_provenance, Mapping) or not isinstance(provenance, Mapping):
            raise PostformalEvalError(f"{route_name} task/arm provenance is required for cross-binding")
        if provenance.get("run_uuid") != row.get("run_uuid") or provenance.get("env_id") != env_id or task.get("run_uuid") != row.get("run_uuid") or task.get("env_id") != env_id:
            raise PostformalEvalError(f"{route_name} task/arm run_uuid/env_id cross-binding failed")
        for key in ("cell", "seed", "source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256", "adaptation_bundle_sha256"):
            task_value = task.get(key) if key == "source_checkpoint_sha256" else task_provenance.get(key)
            arm_value = arm.get(key) if key == "source_checkpoint_sha256" else provenance.get(key)
            row_value = row.get(key)
            if task_value != arm_value or task_value != row_value:
                raise PostformalEvalError(f"{route_name} task/arm {key} cross-binding failed")
        for key in ("source_checkpoint_path", "evaluated_checkpoint_path", "evaluated_checkpoint_sha256", "evaluation_command_sha256"):
            if task.get(key) != arm.get(key) or task.get(key) != row.get(key):
                raise PostformalEvalError(f"{route_name} task/arm {key} cross-binding failed")
        if task_provenance.get("cell") != row.get("cell") or provenance.get("cell") != row.get("cell") or task_provenance.get("seed") != row.get("seed") or provenance.get("seed") != row.get("seed"):
            raise PostformalEvalError(f"{route_name} task/arm cell/seed cross-binding failed")
        if task_provenance.get("topology") != evidence_topology or provenance.get("topology") != evidence_topology or task_provenance.get("runtime_scenario_topology") != runtime_topology or provenance.get("runtime_scenario_topology") != runtime_topology:
            raise PostformalEvalError(f"{route_name} task/arm topology cross-binding failed")
        task_meta = arm.get("task_record")
        if task_meta is not None:
            if not isinstance(task_meta, Mapping) or task_meta.get("record_id") != task.get("record_id") or task_meta.get("trace_path") != task.get("trace", {}).get("path") or task_meta.get("trace_sha256") != task.get("trace", {}).get("sha256"):
                raise PostformalEvalError(f"{route_name} arm task_record metadata does not bind the task record")
    return {
        "row_id": row.get("row_id"),
        "cell": row.get("cell"),
        "step": row.get("step"),
        "topology": evidence_topology,
        "runtime_scenario_topology": runtime_topology,
        "evidence_aggregation_topology": evidence_topology,
        "first_episode_only": True,
        "strict_status": "STRICT_VALID",
        "task_record_count": len(task_records),
        "arm_record_count": len(arm_records),
        "task_records": [dict(record) for record in task_records],
        "arm_records": [dict(record) for record in arm_records],
    }


def validate_route_a_evidence_row(
    row: Mapping[str, Any],
    *,
    task_records: Sequence[Mapping[str, Any]],
    arm_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate exactly 16 strict task records and 16 arm records for Route-A."""

    return _validate_process_evidence_row(
        row,
        task_records=task_records,
        arm_records=arm_records,
        expected_topologies=("canonical16",),
        route_name="Route-A",
    )


def validate_route_b_evidence_row(
    row: Mapping[str, Any],
    *,
    task_records: Sequence[Mapping[str, Any]],
    arm_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate exactly 16 strict records for one pooled/holdout Route-B row."""

    return _validate_process_evidence_row(
        row,
        task_records=task_records,
        arm_records=arm_records,
        expected_topologies=("pooled_seed16", "holdout_seed16"),
        route_name="Route-B",
    )


def _postformal_root(path: Any) -> Path:
    """Resolve an evaluation root without accepting a symlinked directory."""

    if not isinstance(path, (str, Path)) or not str(path):
        raise PostformalEvalError("process completion evaluation_root is required")
    raw = Path(path).expanduser()
    absolute = raw.absolute()
    if any(candidate.is_symlink() for candidate in (absolute, *absolute.parents)):
        raise PostformalEvalError(f"process completion evaluation_root must not contain symlinks: {raw}")
    if not raw.is_dir():
        raise PostformalEvalError(f"process completion evaluation_root must be a regular directory: {raw}")
    return raw.resolve()


def _postformal_file(path: Any, *, root: Path, name: str) -> Path:
    """Resolve one artifact and reject symlinks/path escape before reading it."""

    if not isinstance(path, (str, Path)) or not str(path):
        raise PostformalEvalError(f"{name} must be a non-empty path")
    raw = Path(path).expanduser()
    absolute = raw.absolute()
    if any(candidate.is_symlink() for candidate in (absolute, *absolute.parents)):
        raise PostformalEvalError(f"{name} must not contain symlinks: {raw}")
    try:
        resolved = raw.resolve()
    except OSError as exc:
        raise PostformalEvalError(f"{name} cannot be resolved: {raw}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PostformalEvalError(f"{name} escapes evaluation_root: {resolved}") from exc
    if resolved.is_symlink() or not resolved.is_file():
        raise PostformalEvalError(f"{name} must be an existing regular file: {resolved}")
    return resolved


def _postformal_hash_size(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}


def _postformal_json_file(path: Any, *, root: Path, name: str) -> tuple[Path, Any, bytes]:
    target = _postformal_file(path, root=root, name=name)
    payload = target.read_bytes()
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PostformalEvalError(f"{name} is not valid UTF-8 JSON: {target}") from exc
    return target, value, payload


def _postformal_validate_row_identity(row: Mapping[str, Any]) -> tuple[Path, dict[str, str]]:
    if not isinstance(row, Mapping):
        raise PostformalEvalError("process completion queue row must be a mapping")
    if not isinstance(row.get("row_id"), str) or not row["row_id"]:
        raise PostformalEvalError("process completion row_id is required")
    if not isinstance(row.get("run_uuid"), str) or not row["run_uuid"]:
        raise PostformalEvalError("process completion run_uuid is required")
    evidence_topology = row.get("evidence_aggregation_topology", row.get("topology"))
    runtime_topology = row.get("runtime_scenario_topology", row.get("runtime_topology"))
    if row.get("topology") not in {"canonical16", "pooled_seed16", "holdout_seed16"} or evidence_topology != row.get("topology") or runtime_topology != "canonical16" or row.get("runtime_topology", "canonical16") != "canonical16" or row.get("episodes") != 16 or row.get("first_episode_only") is not True:
        raise PostformalEvalError("process completion row topology/runtime/first-episode binding is invalid")
    if row.get("expected_env_ids", list(range(16))) != list(range(16)):
        raise PostformalEvalError("process completion row must bind exact env IDs 0..15")
    step = row.get("step")
    if isinstance(step, bool) or not isinstance(step, int) or step <= 0:
        raise PostformalEvalError("process completion row step must be a positive integer")
    if row.get("queue_row_id") != row.get("row_id"):
        raise PostformalEvalError("process completion queue row identity is not self-bound")
    root = _postformal_root(row.get("evaluation_root"))
    argv = row.get("argv")
    env = row.get("env")
    declared_command = _declared_command_identity(argv, env)
    if row.get("evaluation_command_sha256") != declared_command:
        raise PostformalEvalError("process completion command identity is not bound to the queue row")
    candidate_identity = _candidate_projection(row, keys=CANDIDATE_IDENTITY_KEYS)
    return root, candidate_identity


def _postformal_validate_route_b_queue_row(row: Mapping[str, Any]) -> None:
    """Authenticate the immutable Route-B queue-row payload before sealing it."""

    row_receipt = row.get("row_receipt_sha256")
    _digest(row_receipt, name="Route-B process completion row receipt_sha256")
    unsigned_row = dict(row)
    unsigned_row.pop("row_receipt_sha256", None)
    if row_receipt != _queue_row_receipt(unsigned_row):
        raise PostformalEvalError("Route-B process completion row receipt does not bind the queue row")

    candidate = row.get("candidate_identity")
    expected_candidate_keys = set(ROUTE_B_CANDIDATE_KEYS) | {"step"}
    if not isinstance(candidate, Mapping) or set(candidate) != expected_candidate_keys:
        raise PostformalEvalError("Route-B process completion nested candidate identity is incomplete")
    candidate_step = candidate.get("step")
    row_step = row.get("step")
    if isinstance(candidate_step, bool) or not isinstance(candidate_step, int) or candidate_step <= 0:
        raise PostformalEvalError("Route-B process completion nested candidate step is invalid")
    if isinstance(row_step, bool) or not isinstance(row_step, int) or row_step <= 0 or row_step != candidate_step:
        raise PostformalEvalError("Route-B process completion top-level step differs from nested candidate step")

    evaluated_path = row.get("evaluated_checkpoint_path")
    if not isinstance(evaluated_path, str) or not evaluated_path:
        raise PostformalEvalError("Route-B process completion evaluated checkpoint path is missing")
    checkpoint_step = _route_b_checkpoint_step(candidate, Path(evaluated_path))
    if checkpoint_step != row_step:
        raise PostformalEvalError("Route-B process completion step does not match evaluated checkpoint identity")

    if row.get("source_checkpoint_path") != V21B_WARM_START_PATH or row.get("source_checkpoint_sha256") != V21B_WARM_START_SHA256:
        raise PostformalEvalError("Route-B process completion warm-start identity is not canonical")
    for key in ROUTE_B_CANDIDATE_KEYS:
        if row.get(key) != candidate.get(key):
            raise PostformalEvalError(f"Route-B process completion top-level/nested identity diverges for {key}")


def _postformal_candidate_id(value: Any) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None or value != value.lower():
        raise PostformalEvalError("candidate_id must be a lowercase 64-hex digest")
    return value


def _postformal_process_result(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PostformalEvalError("process_result must be a mapping")
    required = ("pid", "started_at", "ended_at", "natural_exit", "exit_code")
    if any(key not in value for key in required):
        raise PostformalEvalError("process_result requires pid/timestamps/natural_exit/exit_code")
    pid = value.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise PostformalEvalError("process_result pid must be a positive integer")
    timestamps: dict[str, str] = {}
    for key in ("started_at", "ended_at"):
        timestamp = value.get(key)
        if not isinstance(timestamp, str) or not timestamp:
            raise PostformalEvalError(f"process_result {key} must be a non-empty ISO timestamp")
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PostformalEvalError(f"process_result {key} is not an ISO timestamp") from exc
        timestamps[key] = timestamp
    if value.get("natural_exit") is not True:
        raise PostformalEvalError("process completion requires natural_exit=True")
    exit_code = value.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code != 0:
        raise PostformalEvalError("process completion requires exit_code=0")
    return {"pid": pid, **timestamps, "natural_exit": True, "exit_code": 0}


def _postformal_load_episode_bundles(
    row: Mapping[str, Any],
    *,
    root: Path,
    marker_paths: Sequence[Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(marker_paths, Sequence) or isinstance(marker_paths, (str, bytes)) or len(marker_paths) != 16:
        raise PostformalEvalError("process completion requires exactly 16 episode bundle markers")
    expected_evidence_topology = row.get("evidence_aggregation_topology", row.get("topology"))
    expected_runtime_topology = row.get("runtime_scenario_topology", row.get("runtime_topology"))
    task_records: list[dict[str, Any]] = []
    arm_records: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    seen_markers: set[Path] = set()
    seen_artifacts: set[Path] = set()
    seen_envs: set[int] = set()
    for marker_path in marker_paths:
        marker, marker_payload, marker_bytes = _postformal_json_file(marker_path, root=root, name="episode bundle marker")
        if marker in seen_markers:
            raise PostformalEvalError("process completion episode bundle markers are duplicated")
        seen_markers.add(marker)
        if not isinstance(marker_payload, Mapping) or marker_payload.get("schema") != EPISODE_BUNDLE_COMPLETE_SCHEMA:
            raise PostformalEvalError("episode bundle marker schema is not the current per-episode schema")
        env_id = marker_payload.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in range(16) or env_id in seen_envs:
            raise PostformalEvalError("episode bundle marker env coverage is not exactly 0..15")
        seen_envs.add(env_id)
        if marker_payload.get("run_uuid") != row.get("run_uuid") or marker_payload.get("seed") != row.get("seed") or marker_payload.get("topology") != expected_evidence_topology:
            raise PostformalEvalError("episode bundle marker row/run/seed/topology identity is not bound")
        artifact_paths: list[Path] = []
        for key in ("trace_path", "task_record_path", "arm_record_path"):
            artifact = _postformal_file(marker_payload.get(key), root=root, name=f"episode bundle {key}")
            if artifact in seen_artifacts or artifact == marker:
                raise PostformalEvalError("episode bundle artifacts are duplicated")
            seen_artifacts.add(artifact)
            artifact_paths.append(artifact)
        trace_path, task_path, arm_path = artifact_paths
        trace_bytes = trace_path.read_bytes()
        task_bytes = task_path.read_bytes()
        arm_bytes = arm_path.read_bytes()
        if marker_payload.get("trace_sha256") != hashlib.sha256(trace_bytes).hexdigest() or marker_payload.get("task_record_sha256") != hashlib.sha256(task_bytes).hexdigest() or marker_payload.get("arm_record_sha256") != hashlib.sha256(arm_bytes).hexdigest():
            raise PostformalEvalError("episode bundle artifact digest changed")
        try:
            task = json.loads(task_bytes.decode("utf-8"))
            arm = json.loads(arm_bytes.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise PostformalEvalError("episode bundle task/arm artifact is not valid JSON") from exc
        if not isinstance(task, Mapping) or not isinstance(arm, Mapping):
            raise PostformalEvalError("episode bundle task/arm artifacts must be mappings")
        try:
            a2_v21b_validate_task_record(task)
            a2_v21b_validate_terminal_record(arm)
        except ValueError as exc:
            raise PostformalEvalError(f"episode bundle strict record is invalid: {exc}") from exc
        if task.get("run_uuid") != row.get("run_uuid") or task.get("env_id") != env_id or task.get("seed") != row.get("seed") or task.get("topology") != expected_evidence_topology or task.get("evidence_aggregation_topology") != expected_evidence_topology or task.get("runtime_scenario_topology") != expected_runtime_topology or task.get("first_episode_only") is not True:
            raise PostformalEvalError("episode bundle task row/run/seed/topology identity is not bound")
        arm_provenance = arm.get("provenance")
        if not isinstance(arm_provenance, Mapping) or arm_provenance.get("run_uuid") != row.get("run_uuid") or arm_provenance.get("env_id") != env_id or arm_provenance.get("seed") != row.get("seed") or arm_provenance.get("topology") != expected_evidence_topology or arm_provenance.get("evidence_aggregation_topology") != expected_evidence_topology or arm_provenance.get("runtime_scenario_topology") != expected_runtime_topology:
            raise PostformalEvalError("episode bundle arm provenance row/run/seed/topology identity is not bound")
        if marker_payload.get("task_record_id") != task.get("record_id") or marker_payload.get("arm_record_id") != arm.get("record_id"):
            raise PostformalEvalError("episode bundle record_id does not match its marker")
        trace_meta = task.get("trace")
        if not isinstance(trace_meta, Mapping) or trace_meta.get("path") != str(trace_path) or trace_meta.get("sha256") != marker_payload.get("trace_sha256"):
            raise PostformalEvalError("episode bundle task trace metadata does not match its marker")
        trace_rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(trace_bytes.decode("utf-8").splitlines(), start=1):
            if not line.strip():
                raise PostformalEvalError(f"episode bundle trace contains an empty line at {line_number}")
            try:
                trace_row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PostformalEvalError(f"episode bundle trace line {line_number} is invalid JSON") from exc
            if not isinstance(trace_row, Mapping):
                raise PostformalEvalError("episode bundle trace rows must be mappings")
            trace_rows.append(dict(trace_row))
        try:
            a2_v21b_validate_task_trace_rows(
                trace_rows,
                run_uuid=str(row["run_uuid"]),
                env_id=env_id,
                terminal_reason=str(task["terminal_reason"]),
            )
        except ValueError as exc:
            raise PostformalEvalError(f"episode bundle trace is invalid: {exc}") from exc
        task_records.append(dict(task))
        arm_records.append(dict(arm))
        marker_identity = {
            "marker_path": str(marker),
            "marker_sha256": hashlib.sha256(marker_bytes).hexdigest(),
            "marker_size": len(marker_bytes),
            "run_uuid": marker_payload["run_uuid"],
            "env_id": env_id,
            "topology": marker_payload["topology"],
            "runtime_scenario_topology": expected_runtime_topology,
            "evidence_aggregation_topology": expected_evidence_topology,
            "seed": marker_payload["seed"],
            "trace_path": str(trace_path),
            "task_record_path": str(task_path),
            "arm_record_path": str(arm_path),
            "trace_sha256": marker_payload["trace_sha256"],
            "task_record_sha256": marker_payload["task_record_sha256"],
            "arm_record_sha256": marker_payload["arm_record_sha256"],
            "task_record_id": marker_payload["task_record_id"],
            "arm_record_id": marker_payload["arm_record_id"],
        }
        identities.append(marker_identity)
    if seen_envs != set(range(16)):
        raise PostformalEvalError("episode bundle marker env coverage is not exactly 0..15")
    order = sorted(range(16), key=lambda index: identities[index]["env_id"])
    identities = [identities[index] for index in order]
    task_records = [task_records[index] for index in order]
    arm_records = [arm_records[index] for index in order]
    return identities, task_records, arm_records


def _postformal_strict_summary(strict: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row_id": strict.get("row_id"),
        "cell": strict.get("cell"),
        "step": strict.get("step"),
        "topology": strict.get("topology"),
        "runtime_scenario_topology": strict.get("runtime_scenario_topology"),
        "evidence_aggregation_topology": strict.get("evidence_aggregation_topology"),
        "first_episode_only": strict.get("first_episode_only"),
        "strict_status": strict.get("strict_status"),
        "task_record_count": strict.get("task_record_count"),
        "arm_record_count": strict.get("arm_record_count"),
    }


def _postformal_write_exclusive_json(path: Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    if target.is_symlink():
        raise PostformalEvalError(f"process completion artifact must not be a symlink: {target}")
    encoded = canonical_json_bytes(dict(payload)) + b"\n"
    if target.exists():
        if not target.is_file() or target.read_bytes() != encoded:
            raise PostformalEvalError(f"process completion artifact differs: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.part")
    if temporary.exists() or temporary.is_symlink():
        if temporary.is_symlink() or not temporary.is_file() or temporary.read_bytes() != encoded:
            raise PostformalEvalError(f"process completion temporary artifact differs: {temporary}")
    else:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    try:
        os.link(temporary, target)
    except FileExistsError:
        if target.is_symlink() or not target.is_file() or target.read_bytes() != encoded:
            raise PostformalEvalError(f"process completion artifact appeared with different bytes: {target}")
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _postformal_receipt_body(
    row: Mapping[str, Any],
    *,
    candidate_id: str,
    process_result: Mapping[str, Any],
    stdout: Mapping[str, Any],
    stderr: Mapping[str, Any],
    bundles: Sequence[Mapping[str, Any]],
    strict_summary: Mapping[str, Any],
    root: Path,
    candidate_identity: Mapping[str, Any],
) -> dict[str, Any]:
    argv = list(row["argv"])
    env = dict(row["env"])
    command = {
        "argv": argv,
        "env": env,
        "argv_sha256": hashlib.sha256(canonical_json_bytes(argv)).hexdigest(),
        "env_sha256": hashlib.sha256(canonical_json_bytes(env)).hexdigest(),
        "evaluation_command_sha256": row["evaluation_command_sha256"],
    }
    f3_identity = {key: row[key] for key in RECORD_CANDIDATE_KEYS if key not in {"source_checkpoint_path", "source_checkpoint_sha256", "evaluated_checkpoint_path", "evaluated_checkpoint_sha256"}}
    body: dict[str, Any] = {
        "schema": PROCESS_RECEIPT_SCHEMA,
        "producer_state": "PROCESS_COMPLETED",
        "row_id": row["row_id"],
        "queue_row_id": row["queue_row_id"],
        "run_uuid": row["run_uuid"],
        "evaluation_root": str(root),
        "receipt_path": str(root / "process_receipt.json"),
        "seal_path": str(root / "PROCESS_COMPLETED.seal.json"),
        "candidate_id": candidate_id,
        "candidate_identity": dict(candidate_identity),
        "source_checkpoint_identity": {"path": row["source_checkpoint_path"], "sha256": row["source_checkpoint_sha256"]},
        "evaluated_checkpoint_identity": {"path": row["evaluated_checkpoint_path"], "sha256": row["evaluated_checkpoint_sha256"]},
        "f3_identity": f3_identity,
        "command": command,
        "process": dict(process_result),
        "stdout": dict(stdout),
        "stderr": dict(stderr),
        "episode_bundles": [dict(bundle) for bundle in bundles],
        "strict_evidence": dict(strict_summary),
    }
    body["receipt_sha256"] = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    return body


def _postformal_seal_body(receipt: Mapping[str, Any]) -> dict[str, Any]:
    receipt_bytes = canonical_json_bytes(dict(receipt)) + b"\n"
    body = {
        "schema": COMPLETION_SEAL_SCHEMA,
        "producer_state": "PROCESS_COMPLETED_SEALED",
        "receipt_path": receipt["receipt_path"],
        "receipt_sha256": receipt["receipt_sha256"],
        "receipt_file_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "row_id": receipt["row_id"],
        "queue_row_id": receipt["queue_row_id"],
        "run_uuid": receipt["run_uuid"],
        "evaluation_root": receipt["evaluation_root"],
        "candidate_id": receipt["candidate_id"],
        "candidate_identity": receipt["candidate_identity"],
        "command": receipt["command"],
        "stdout": receipt["stdout"],
        "stderr": receipt["stderr"],
        "episode_bundles": receipt["episode_bundles"],
        "strict_evidence": receipt["strict_evidence"],
    }
    body["seal_sha256"] = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    return body


def write_route_a_process_completion(
    row: Mapping[str, Any],
    *,
    candidate_id: str,
    process_result: Mapping[str, Any],
    stdout_path: str | Path,
    stderr_path: str | Path,
    episode_bundle_marker_paths: Sequence[str | Path],
    _allowed_topologies: Sequence[str] = ("canonical16",),
) -> dict[str, Any]:
    """Validate a completed process, then publish one idempotent receipt/seal."""

    root, candidate_identity = _postformal_validate_row_identity(row)
    allowed_topologies = tuple(_allowed_topologies)
    if row.get("topology") not in allowed_topologies:
        raise PostformalEvalError("process completion entry point does not admit this evidence topology")
    if allowed_topologies == ("pooled_seed16", "holdout_seed16"):
        _postformal_validate_route_b_queue_row(row)
    elif allowed_topologies != ("canonical16",):
        raise PostformalEvalError("process completion entry point topology dispatch is invalid")
    candidate_id = _postformal_candidate_id(candidate_id)
    process = _postformal_process_result(process_result)
    stdout = _postformal_hash_size(_postformal_file(stdout_path, root=root, name="stdout log"))
    stderr = _postformal_hash_size(_postformal_file(stderr_path, root=root, name="stderr log"))
    bundles, task_records, arm_records = _postformal_load_episode_bundles(
        row, root=root, marker_paths=episode_bundle_marker_paths
    )
    strict = _validate_process_evidence_row(
        row,
        task_records=task_records,
        arm_records=arm_records,
        expected_topologies=_allowed_topologies,
        route_name="Route-A" if tuple(_allowed_topologies) == ("canonical16",) else "Route-B",
    )
    strict_summary = _postformal_strict_summary(strict)
    receipt = _postformal_receipt_body(
        row,
        candidate_id=candidate_id,
        process_result=process,
        stdout=stdout,
        stderr=stderr,
        bundles=bundles,
        strict_summary=strict_summary,
        root=root,
        candidate_identity=candidate_identity,
    )
    seal = _postformal_seal_body(receipt)
    receipt_path = root / "process_receipt.json"
    seal_path = root / "PROCESS_COMPLETED.seal.json"
    _postformal_write_exclusive_json(receipt_path, receipt)
    _postformal_write_exclusive_json(seal_path, seal)
    return {"status": "PROCESS_COMPLETED_SEALED", "receipt_path": str(receipt_path), "seal_path": str(seal_path), "receipt": receipt, "seal": seal, "strict_evidence": strict_summary}


def write_route_b_process_completion(
    row: Mapping[str, Any],
    *,
    candidate_id: str,
    process_result: Mapping[str, Any],
    stdout_path: str | Path,
    stderr_path: str | Path,
    episode_bundle_marker_paths: Sequence[str | Path],
) -> dict[str, Any]:
    """Validate and seal one pooled/holdout Route-B process row."""

    return write_route_a_process_completion(
        row,
        candidate_id=candidate_id,
        process_result=process_result,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        episode_bundle_marker_paths=episode_bundle_marker_paths,
        _allowed_topologies=("pooled_seed16", "holdout_seed16"),
    )


def validate_route_a_process_completion(
    row: Mapping[str, Any],
    *,
    candidate_id: str,
    evaluation_root: str | Path | None = None,
    _allowed_topologies: Sequence[str] = ("canonical16",),
) -> dict[str, Any]:
    """Re-read and authenticate one sealed process completion."""

    root, candidate_identity = _postformal_validate_row_identity(row)
    allowed_topologies = tuple(_allowed_topologies)
    if row.get("topology") not in allowed_topologies:
        raise PostformalEvalError("process completion entry point does not admit this evidence topology")
    if allowed_topologies == ("pooled_seed16", "holdout_seed16"):
        _postformal_validate_route_b_queue_row(row)
    elif allowed_topologies != ("canonical16",):
        raise PostformalEvalError("process completion entry point topology dispatch is invalid")
    if evaluation_root is not None and _postformal_root(evaluation_root) != root:
        raise PostformalEvalError("process completion evaluation_root argument differs from queue row")
    candidate_id = _postformal_candidate_id(candidate_id)
    receipt_path, receipt, receipt_bytes = _postformal_json_file(root / "process_receipt.json", root=root, name="process receipt")
    seal_path, seal, seal_bytes = _postformal_json_file(root / "PROCESS_COMPLETED.seal.json", root=root, name="completion seal")
    if not isinstance(receipt, Mapping) or receipt.get("schema") != PROCESS_RECEIPT_SCHEMA or receipt.get("producer_state") != "PROCESS_COMPLETED":
        raise PostformalEvalError("process receipt schema/state is invalid")
    receipt_unsigned = dict(receipt)
    receipt_digest = receipt_unsigned.pop("receipt_sha256", None)
    _digest(receipt_digest, name="process receipt self digest")
    if receipt_digest != hashlib.sha256(canonical_json_bytes(receipt_unsigned)).hexdigest():
        raise PostformalEvalError("process receipt self digest is invalid")
    if not isinstance(seal, Mapping) or seal.get("schema") != COMPLETION_SEAL_SCHEMA or seal.get("producer_state") != "PROCESS_COMPLETED_SEALED":
        raise PostformalEvalError("completion seal schema/state is invalid")
    seal_unsigned = dict(seal)
    seal_digest = seal_unsigned.pop("seal_sha256", None)
    _digest(seal_digest, name="completion seal self digest")
    if seal_digest != hashlib.sha256(canonical_json_bytes(seal_unsigned)).hexdigest():
        raise PostformalEvalError("completion seal self digest is invalid")
    if receipt.get("receipt_path") != str(receipt_path) or receipt.get("seal_path") != str(seal_path) or receipt.get("evaluation_root") != str(root):
        raise PostformalEvalError("process receipt path/root identity is invalid")
    for payload in (receipt, seal):
        if payload.get("row_id") != row.get("row_id") or payload.get("queue_row_id") != row.get("queue_row_id") or payload.get("run_uuid") != row.get("run_uuid") or payload.get("candidate_id") != candidate_id:
            raise PostformalEvalError("process completion row/candidate identity is not bound")
    if receipt.get("candidate_identity") != candidate_identity:
        raise PostformalEvalError("process receipt candidate identity differs from queue row")
    if seal.get("candidate_identity") != receipt.get("candidate_identity"):
        raise PostformalEvalError("completion seal candidate identity differs from receipt")
    expected_source_identity = {"path": row["source_checkpoint_path"], "sha256": row["source_checkpoint_sha256"]}
    expected_evaluated_identity = {"path": row["evaluated_checkpoint_path"], "sha256": row["evaluated_checkpoint_sha256"]}
    expected_f3_identity = {key: row[key] for key in RECORD_CANDIDATE_KEYS if key not in {"source_checkpoint_path", "source_checkpoint_sha256", "evaluated_checkpoint_path", "evaluated_checkpoint_sha256"}}
    if receipt.get("source_checkpoint_identity") != expected_source_identity or receipt.get("evaluated_checkpoint_identity") != expected_evaluated_identity or receipt.get("f3_identity") != expected_f3_identity:
        raise PostformalEvalError("process receipt source/evaluated/F3 identity differs from queue row")
    command = receipt.get("command")
    if not isinstance(command, Mapping) or command.get("argv") != list(row["argv"]) or command.get("env") != dict(row["env"]) or command.get("evaluation_command_sha256") != row.get("evaluation_command_sha256") or command.get("argv_sha256") != hashlib.sha256(canonical_json_bytes(list(row["argv"]))).hexdigest() or command.get("env_sha256") != hashlib.sha256(canonical_json_bytes(dict(row["env"]))).hexdigest():
        raise PostformalEvalError("process completion command identity is not bound")
    if seal.get("command") != command:
        raise PostformalEvalError("completion seal command identity differs from receipt")
    process = receipt.get("process")
    if not isinstance(process, Mapping) or _postformal_process_result(process) != dict(process):
        raise PostformalEvalError("process receipt result is not a natural exit0")
    if seal.get("stdout") != receipt.get("stdout") or seal.get("stderr") != receipt.get("stderr"):
        raise PostformalEvalError("completion seal log identities differ from receipt")
    for key, name in (("stdout", "stdout log"), ("stderr", "stderr log")):
        identity = receipt.get(key)
        if not isinstance(identity, Mapping):
            raise PostformalEvalError(f"process receipt {key} identity is missing")
        log = _postformal_file(identity.get("path"), root=root, name=name)
        actual = _postformal_hash_size(log)
        if actual.get("sha256") != identity.get("sha256") or actual.get("size") != identity.get("size"):
            raise PostformalEvalError(f"{name} changed after process completion")
    marker_identities = receipt.get("episode_bundles")
    if not isinstance(marker_identities, list) or len(marker_identities) != 16 or seal.get("episode_bundles") != marker_identities:
        raise PostformalEvalError("process completion requires exactly 16 bound bundle identities")
    bundles, task_records, arm_records = _postformal_load_episode_bundles(
        row, root=root, marker_paths=[item.get("marker_path") if isinstance(item, Mapping) else None for item in marker_identities]
    )
    if bundles != marker_identities:
        raise PostformalEvalError("episode bundle marker/artifact identity changed")
    strict = _validate_process_evidence_row(
        row,
        task_records=task_records,
        arm_records=arm_records,
        expected_topologies=_allowed_topologies,
        route_name="Route-A" if tuple(_allowed_topologies) == ("canonical16",) else "Route-B",
    )
    strict_summary = _postformal_strict_summary(strict)
    if receipt.get("strict_evidence") != strict_summary or seal.get("strict_evidence") != strict_summary:
        raise PostformalEvalError("strict evidence summary changed after process completion")
    if seal.get("receipt_path") != str(receipt_path) or seal.get("receipt_sha256") != receipt.get("receipt_sha256"):
        raise PostformalEvalError("completion seal receipt identity is invalid")
    receipt_file_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    if seal.get("receipt_file_sha256") != receipt_file_sha256:
        raise PostformalEvalError("completion seal receipt file digest is invalid")
    return {"status": "PROCESS_COMPLETED_SEALED", "receipt_path": str(receipt_path), "seal_path": str(seal_path), "receipt": dict(receipt), "seal": dict(seal), "strict_evidence": strict_summary, "receipt_sha256": receipt.get("receipt_sha256"), "receipt_file_sha256": receipt_file_sha256, "seal_sha256": hashlib.sha256(seal_bytes).hexdigest()}


def validate_route_b_process_completion(
    row: Mapping[str, Any],
    *,
    candidate_id: str,
    evaluation_root: str | Path | None = None,
) -> dict[str, Any]:
    """Re-read and authenticate one sealed pooled/holdout Route-B row."""

    return validate_route_a_process_completion(
        row,
        candidate_id=candidate_id,
        evaluation_root=evaluation_root,
        _allowed_topologies=("pooled_seed16", "holdout_seed16"),
    )


# Explicit aliases keep the producer/validator names discoverable to callers
# that use either "receipt" or "completion" terminology.
produce_route_a_process_completion = write_route_a_process_completion
write_route_a_process_receipt = write_route_a_process_completion
validate_route_a_process_receipt = validate_route_a_process_completion
produce_route_b_process_completion = write_route_b_process_completion
write_route_b_process_receipt = write_route_b_process_completion
validate_route_b_process_receipt = validate_route_b_process_completion


def _record_metric(record: Mapping[str, Any], names: Sequence[str], *, required: bool = False) -> float | None:
    containers = [record.get("metrics"), record.get("task"), record.get("safety"), record.get("send"), record.get("release")]
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for name in names:
            if name in container:
                value = container[name]
                if isinstance(value, Mapping) and value.get("status") == "N/A":
                    continue
                return _finite(value, name=name)
    if required:
        raise PostformalEvalError(f"strict evaluation record is missing metric {names[0]}")
    return None


def _record_bool(record: Mapping[str, Any], names: Sequence[str]) -> bool:
    containers = [record.get("task"), record.get("safety"), record.get("send"), record.get("release"), record]
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for name in names:
            if name in container:
                value = container[name]
                if not isinstance(value, bool):
                    raise PostformalEvalError(f"record boolean metric {name} must be bool")
                return value
    raise PostformalEvalError(f"strict evaluation record is missing boolean metric {names[0]}")


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise PostformalEvalError("cannot compute a percentile from an empty metric set")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    return float(statistics.quantiles(ordered, n=100, method="inclusive")[max(0, min(99, int(round(probability * 100)) - 1))])


def _percentile_or_na(values: Sequence[float], probability: float) -> float | None:
    """Return no metric when its valid denominator is empty; never zero-fill."""

    return _percentile(values, probability) if values else None


def _metric_or_na(value: float | None, *, reason: str = "NO_VALID_DENOMINATOR") -> float | dict[str, Any]:
    if value is None:
        return {"status": "N/A", "reason": reason, "denominator": 0}
    return value


def _route_b_seed_contract(topology: str) -> tuple[int, ...]:
    if topology == "canonical16":
        return (0,)
    if topology == "pooled_seed16":
        return V21B_ROUTE_B_POOLED_SEEDS
    if topology == "holdout_seed16":
        return V21B_ROUTE_B_HOLDOUT_SEEDS
    if topology == "render1":
        return tuple(range(7))
    raise PostformalEvalError(f"unsupported v21-B evaluation topology: {topology!r}")


def _route_b_checkpoint_step(candidate: Mapping[str, Any], checkpoint: Path) -> int:
    """Resolve one exact checkpoint step for every Route-B invocation.

    A numbered ``model_step_*.pt`` filename is authoritative when present.
    Synthetic or otherwise renamed checkpoints must carry an explicit integer
    ``step`` in the frozen candidate; silently treating an unknown filename as
    step zero would make queue rows impossible to cross-bind to their receipt.
    """

    checkpoint_match = FORMAL_CHECKPOINT_RE.fullmatch(checkpoint.name)
    checkpoint_step = None if checkpoint_match is None else int(checkpoint_match.group("step"))
    candidate_step = candidate.get("step")
    if candidate_step is None:
        if checkpoint_step is None:
            raise PostformalEvalError(
                "Route-B evaluated checkpoint step is not derivable; frozen candidate step is required"
            )
        candidate_step = checkpoint_step
    if isinstance(candidate_step, bool) or not isinstance(candidate_step, int) or candidate_step <= 0:
        raise PostformalEvalError("Route-B candidate step must be a positive integer")
    if checkpoint_step is not None and candidate_step != checkpoint_step:
        raise PostformalEvalError("Route-B candidate step does not match evaluated checkpoint filename")
    return candidate_step


def adjudicate_route_b(
    records: Sequence[Mapping[str, Any]],
    *,
    topology: str,
    theta_send_rad: float,
    baseline: Mapping[str, Any] | None = None,
    candidate_identity: Mapping[str, Any] | None = None,
    expected_seed: int | None = None,
    queue: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply preregistered pooled/holdout/canonical gates to strict records."""

    if topology not in TOPOLOGY_EPISODES:
        raise PostformalEvalError(f"unsupported v21-B evaluation topology: {topology!r}")
    expected_count = TOPOLOGY_EPISODES[topology]
    if not isinstance(records, Sequence) or len(records) != expected_count:
        raise PostformalEvalError(f"{topology} requires exactly {expected_count} strict records")
    if topology == "canonical16":
        admitted_seed = 0 if expected_seed is None else expected_seed
        if isinstance(admitted_seed, bool) or not isinstance(admitted_seed, int) or admitted_seed not in V21B_EVAL_SEEDS:
            raise PostformalEvalError("canonical16 expected_seed must be an int in 0..6")
        admitted_seeds = (admitted_seed,)
    else:
        if expected_seed is not None:
            raise PostformalEvalError(f"{topology} does not accept expected_seed")
        admitted_seeds = _route_b_seed_contract(topology)
    if topology in {"pooled_seed16", "holdout_seed16"}:
        if queue is None:
            raise PostformalEvalError(f"{topology} adjudication requires its declared immutable queue")
        validate_route_b_queue(queue)
        if queue.get("topology") != topology:
            raise PostformalEvalError("Route-B adjudication queue topology does not match requested topology")
    queue_by_run_uuid = {row.get("run_uuid"): row for row in (queue or {}).get("rows", []) if isinstance(row, Mapping)}
    theta = _finite(theta_send_rad, name="theta_send_rad")
    if not 0.90 <= theta <= 1.30:
        raise PostformalEvalError("theta_send_rad is outside v21-B closed interval")
    seen_episodes: set[str] = set()
    seed_counts: Counter[int] = Counter()
    goals = held = overtime = overspeed = 0
    hinge_cross: list[float] = []
    opening_slip: list[float] = []
    planar: list[float] = []
    yaw: list[float] = []
    task_time: list[float] = []
    candidate_identity_tuple: tuple[str, ...] | None = None
    observed_candidate_identity: dict[str, str] | None = None
    for record in records:
        if not isinstance(record, Mapping):
            raise PostformalEvalError("strict evaluation records must be mappings")
        if record.get("schema") != V21B_TASK_RECORD_SCHEMA:
            raise PostformalEvalError("Route-B requires v21-B task records, not fallback summaries")
        a2_v21b_validate_task_record(record)
        _validate_task_identity(record)
        if record.get("topology") != topology:
            raise PostformalEvalError(f"Route-B record topology {record.get('topology')!r} does not match {topology!r}")
        if record.get("seed") not in admitted_seeds:
            raise PostformalEvalError("Route-B record seed is not admitted for the requested topology")
        if queue is not None:
            provenance = record.get("provenance")
            if not isinstance(provenance, Mapping):
                raise PostformalEvalError("Route-B queued record provenance is required")
            run_uuid = record.get("run_uuid")
            queue_row = queue_by_run_uuid.get(run_uuid)
            if not isinstance(queue_row, Mapping):
                raise PostformalEvalError("Route-B record run_uuid is not present in the declared queue")
            for key, actual in (
                ("row_id", provenance.get("queue_row_id", record.get("queue_row_id"))),
                ("evaluation_root", provenance.get("evaluation_root", record.get("evaluation_root"))),
                ("evaluation_command_sha256", record.get("evaluation_command_sha256")),
                ("run_uuid", record.get("run_uuid")),
                ("seed", record.get("seed")),
                ("runtime_scenario_topology", record.get("runtime_scenario_topology", provenance.get("runtime_scenario_topology"))),
                ("evidence_aggregation_topology", record.get("evidence_aggregation_topology", provenance.get("evidence_aggregation_topology", record.get("topology")))),
            ):
                expected = queue_row.get(key)
                if actual != expected:
                    raise PostformalEvalError(f"Route-B record is not bound to queue row {key}")
            env_ids = provenance.get("env_ids", provenance.get("expected_env_ids", record.get("expected_env_ids")))
            if env_ids is not None and env_ids != list(range(16)):
                raise PostformalEvalError("Route-B record expected env IDs must be exactly 0..15")
            if record.get("env_id") not in queue_row.get("expected_env_ids", list(range(16))):
                raise PostformalEvalError("Route-B record env_id is outside queued env IDs")
            _record_candidate_identity(record, queue_row.get("candidate_identity", {}))
        identity_tuple = _task_identity_tuple(record)
        if candidate_identity_tuple is None:
            candidate_identity_tuple = identity_tuple
        elif candidate_identity_tuple != identity_tuple:
            raise PostformalEvalError("Route-B records do not share one frozen checkpoint/materialization identity")
        current_candidate = _candidate_identity_from_record(record)
        if observed_candidate_identity is None:
            observed_candidate_identity = current_candidate
        elif observed_candidate_identity != current_candidate:
            raise PostformalEvalError("Route-B records do not share one frozen candidate identity")
        if candidate_identity is not None:
            expected_candidate = {
                key: candidate_identity.get(key)
                for key in current_candidate
            }
            if expected_candidate != current_candidate:
                raise PostformalEvalError("Route-B record candidate identity does not match the frozen release candidate")
        episode_id = f"{record['run_uuid']}:{record['env_id']}"
        if episode_id in seen_episodes:
            raise PostformalEvalError("Route-B episode identities are duplicated")
        seen_episodes.add(episode_id)
        seed = record["seed"]
        seed_counts[seed] += 1
        if _record_bool(record, ("goal", "complete")):
            goals += 1
        if _record_bool(record, ("held_crossing", "crossing_while_holding")):
            held += 1
        if _record_bool(record, ("stage_overtime",)):
            overtime += 1
        if _record_bool(record, ("upper_dof_overspeed", "overspeed")):
            overspeed += 1
        for values, names in (
            (hinge_cross, ("hinge_at_crossing_rad", "hinge_at_first_crossing_rad")),
            (opening_slip, ("opening_slip_p95_m", "opening_slip_m", "opening_slip_max_m")),
            (planar, ("pre_send_planar_p95_m", "max_planar_displacement_m")),
            (yaw, ("pre_send_yaw_p95_rad", "max_abs_yaw_change_rad")),
            (task_time, ("task_time_p95_s", "task_time_s")),
        ):
            metric = _record_metric(record, names, required=False)
            if metric is not None:
                values.append(metric)
    if topology == "canonical16":
        if seed_counts != Counter({admitted_seeds[0]: 16}):
            raise PostformalEvalError(f"canonical16 requires seed{admitted_seeds[0]} x16; got {dict(seed_counts)}")
    if topology in {"pooled_seed16", "holdout_seed16"} and seed_counts != Counter({seed: 16 for seed in admitted_seeds}):
        raise PostformalEvalError(f"{topology} requires exact seeds x16; got {dict(seed_counts)}")
    if topology == "render1" and len(seed_counts) != 1:
        raise PostformalEvalError("render1 requires one seed")
    threshold = {
        "canonical16": {"goal": 15, "held": 15},
        "pooled_seed16": {"goal": 46, "held": 46, "overtime": 6, "overspeed": 3},
        "holdout_seed16": {"goal": 61, "held": 61, "overtime": 8, "overspeed": 4},
        "render1": {"goal": 1, "held": 1},
    }[topology]
    hinge_p50 = _percentile_or_na(hinge_cross, 0.50)
    hinge_p10 = _percentile_or_na(hinge_cross, 0.10)
    opening_slip_p95 = _percentile_or_na(opening_slip, 0.95)
    planar_p95 = _percentile_or_na(planar, 0.95)
    yaw_p95 = _percentile_or_na(yaw, 0.95)
    task_time_p95 = _percentile_or_na(task_time, 0.95)
    gates: dict[str, bool] = {
        "goal": goals >= threshold["goal"],
        "held_crossing": held >= threshold["held"],
        "crossing_p50_absolute": hinge_p50 is not None and hinge_p50 >= 1.10,
        "crossing_p50_theta_shortfall": hinge_p50 is not None and hinge_p50 >= theta - 0.10,
        "crossing_p10_theta_shortfall": hinge_p10 is not None and hinge_p10 >= theta - 0.20,
        "opening_slip_p95": opening_slip_p95 is not None and opening_slip_p95 <= 0.035,
        "pre_send_planar_p95": planar_p95 is not None and planar_p95 <= 0.90,
        "pre_send_yaw_p95": yaw_p95 is not None and yaw_p95 <= 0.70,
        "task_time_p95": task_time_p95 is not None and task_time_p95 <= 19.0,
    }
    if topology in {"pooled_seed16", "holdout_seed16"}:
        gates["stage_overtime"] = overtime <= threshold["overtime"]
        gates["upper_dof_overspeed"] = overspeed <= threshold["overspeed"]
    if baseline is not None:
        if topology != "pooled_seed16":
            raise PostformalEvalError("non-regression baseline is only defined for pooled48")
        base_goal_rate = _finite(baseline.get("goal_rate"), name="baseline.goal_rate")
        base_overspeed_rate = _finite(baseline.get("overspeed_rate"), name="baseline.overspeed_rate")
        base_task_p95 = _finite(baseline.get("task_time_p95"), name="baseline.task_time_p95")
        gates["non_regression_goal"] = goals / expected_count >= base_goal_rate - 0.04
        gates["non_regression_overspeed"] = overspeed / expected_count <= base_overspeed_rate + 0.02
        gates["non_regression_task_time"] = task_time_p95 is not None and task_time_p95 <= base_task_p95 + 3.0
    failed = [name for name, passed in gates.items() if not passed]
    return {
        "schema": "a2_piper_base_v21B_route_b_adjudication_v1",
        "topology": topology,
        "theta_send_rad": theta,
        "episode_count": expected_count,
        "seed_counts": dict(sorted(seed_counts.items())),
        "goal_count": goals,
        "held_crossing_count": held,
        "stage_overtime_count": overtime,
        "upper_dof_overspeed_count": overspeed,
        "metrics": {
            "goal_rate": goals / expected_count,
            "held_crossing_rate": held / expected_count,
            "overspeed_rate": overspeed / expected_count,
            "hinge_at_crossing_p10": _metric_or_na(hinge_p10),
            "hinge_at_crossing_p50": _metric_or_na(hinge_p50),
            "opening_slip_p95": _metric_or_na(opening_slip_p95),
            "pre_send_planar_p95": _metric_or_na(planar_p95),
            "pre_send_yaw_p95": _metric_or_na(yaw_p95),
            "task_time_p95": _metric_or_na(task_time_p95),
        },
        "gates": gates,
        "failed_gates": failed,
        "status": "PASS" if not failed else "FAIL",
        "candidate_identity": observed_candidate_identity,
    }


adjudicate_route_b_evidence = adjudicate_route_b


def build_route_a_metrics(
    evidence_rows: Sequence[Mapping[str, Any]],
    *,
    f3_context: Mapping[str, Any] | None = None,
    route_a_queue: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate the exact 70 Route-A canonical16 evidence rows."""

    if not isinstance(evidence_rows, Sequence) or len(evidence_rows) != 70:
        raise PostformalEvalError("Route-A metrics require exactly 70 evidence rows")
    if route_a_queue is not None:
        validate_route_a_queue(route_a_queue)
        queue_rows = {row.get("row_id"): row for row in route_a_queue["rows"]}
    else:
        queue_rows = {}
    outputs: list[dict[str, Any]] = []
    identities: set[tuple[str, int]] = set()
    for item in evidence_rows:
        if not isinstance(item, Mapping):
            raise PostformalEvalError("Route-A evidence row must be a mapping")
        row = item.get("manifest_row", item.get("row"))
        if not isinstance(row, Mapping):
            raise PostformalEvalError("Route-A evidence item must include manifest_row")
        row_seed = row.get("seed")
        if isinstance(row_seed, bool) or not isinstance(row_seed, int) or row_seed not in V21B_EVAL_SEEDS:
            raise PostformalEvalError("Route-A metrics row seed must be an int in 0..6")
        task_records = item.get("task_records")
        arm_records = item.get("arm_records")
        strict = validate_route_a_evidence_row(row, task_records=task_records, arm_records=arm_records)
        if route_a_queue is not None:
            queued_row = queue_rows.get(row.get("row_id"))
            if not isinstance(queued_row, Mapping) or queued_row.get("evaluation_command_sha256") != row.get("evaluation_command_sha256") or queued_row.get("run_uuid") != row.get("run_uuid"):
                raise PostformalEvalError("Route-A evidence row is not bound to the declared immutable queue")
        identity = (str(row["cell"]), int(row["step"]))
        if identity in identities:
            raise PostformalEvalError("Route-A metrics contain duplicate cell/step identity")
        identities.add(identity)
        adjudication = adjudicate_route_b(
            strict["task_records"],
            topology="canonical16",
            theta_send_rad=float(row["theta_send_rad"]),
            expected_seed=row_seed,
        )
        release_gates = {
            "goal": adjudication["gates"]["goal"],
            "held_crossing": adjudication["gates"]["held_crossing"],
        }
        outputs.append({
            "row_id": row.get("row_id"),
            "cell": row["cell"],
            "step": int(row["step"]),
            "topology": row["topology"],
            "seed": row["seed"],
            "strict_status": strict["strict_status"],
            "release_gate_status": "PASS" if all(release_gates.values()) else "FAIL",
            "metrics": dict(adjudication["metrics"]),
            "gates": dict(adjudication["gates"]),
            "goal_count": adjudication["goal_count"],
            "held_crossing_count": adjudication["held_crossing_count"],
            "task_record_count": strict["task_record_count"],
            "arm_record_count": strict["arm_record_count"],
            "identity": {key: row.get(key) for key in (
                "source_checkpoint_sha256", "evaluated_checkpoint_sha256", "config_sha256",
                "source_lock_sha256", "source_config_sha256", "materialization_sha256",
                "materialized_config_sha256", "adaptation_bundle_sha256", "evaluation_command_sha256",
            )},
            **{key: row.get(key) for key in (
                "source_checkpoint_path", "source_checkpoint_sha256", "evaluated_checkpoint_path", "evaluated_checkpoint_sha256",
                "config_path", "config_sha256", "source_lock_sha256", "source_config_sha256", "materialization_sha256",
                "materialized_config_sha256", "adaptation_bundle_sha256", "evaluation_command_sha256",
            )},
            "evaluated_checkpoint_path": row.get("evaluated_checkpoint_path"),
            "config_path": row.get("config_path"),
            "evaluation_root": row.get("evaluation_root"),
            "run_uuid": row.get("run_uuid"),
            "physical_gpu": row.get("physical_gpu"),
            "training_gpu": row.get("training_gpu"),
            "runtime_scenario_topology": row.get("runtime_scenario_topology", "canonical16"),
            "evidence_aggregation_topology": row.get("evidence_aggregation_topology", "canonical16"),
            "expected_env_ids": list(row.get("expected_env_ids", range(16))),
        })
    if identities != {(cell, step) for cell in V21B_CELL_ORDER for step in V21B_FORMAL_CHECKPOINT_STEPS}:
        raise PostformalEvalError("Route-A metrics do not contain exact B1..B7 × 250..2500")
    return {
        "schema": ROUTE_A_METRICS_SCHEMA,
        "status": "PASS",
        "row_count": len(outputs),
        "rows": outputs,
        "f3_dv_readout": None if f3_context is None else f3_dv_readout(f3_context),
        "strict_valid_rows": len(outputs),
        "route_a_queue_receipt_sha256": route_a_queue.get("receipt_sha256") if route_a_queue is not None else None,
    }


def _canonical_snapshot(value: Mapping[str, Any], *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PostformalEvalError(f"{name} must be a mapping")
    try:
        canonical_json_bytes(value)
    except (TypeError, ValueError, UnicodeError, V21BError) as exc:
        raise PostformalEvalError(f"{name} is not canonical JSON") from exc
    return deepcopy(dict(value))


def _canonical_sha256(value: Mapping[str, Any], *, name: str) -> str:
    return hashlib.sha256(canonical_json_bytes(_canonical_snapshot(value, name=name))).hexdigest()


def _validate_selection_row(row: Any, *, cell: str, name: str) -> None:
    if not isinstance(row, Mapping):
        raise PostformalEvalError(f"{name} row is required")
    if row.get("cell") != cell:
        raise PostformalEvalError(f"{name} row is not bound to {cell}")
    if row.get("strict_status") != "STRICT_VALID":
        raise PostformalEvalError(f"{name} row must be STRICT_VALID")
    if not isinstance(row.get("row_id"), str) or not row["row_id"]:
        raise PostformalEvalError(f"{name} row_id is required")


def validate_selection(selection: Mapping[str, Any]) -> None:
    """Validate the complete, ordered Route-A selection contract."""

    if not isinstance(selection, Mapping):
        raise PostformalEvalError("selection must be a mapping")
    status = selection.get("status")
    if status not in {"SELECTION_PASS", "NO_RELEASE"}:
        raise PostformalEvalError("selection status is invalid")
    expected_keys = {
        "schema", "status", "completed", "cells", "eligible_release_cells",
        "ineligible_release_cells", "no_release_reasons",
    }
    if status == "NO_RELEASE":
        expected_keys.add("reason")
    if set(selection) != expected_keys:
        raise PostformalEvalError("selection schema keys are not exact")
    if selection.get("schema") != SELECTION_SCHEMA or selection.get("completed") is not True:
        raise PostformalEvalError("selection schema/completed contract is invalid")
    cells = selection.get("cells")
    if not isinstance(cells, Mapping) or list(cells) != list(V21B_CELL_ORDER):
        raise PostformalEvalError("selection cells must be exactly B1..B7 in order")

    def validate_cell_list(value: Any, *, name: str) -> list[str]:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise PostformalEvalError(f"selection {name} must be a list of cell names")
        if len(set(value)) != len(value) or any(item not in V21B_CELL_ORDER for item in value):
            raise PostformalEvalError(f"selection {name} contains duplicate or unknown cells")
        order = {item: index for index, item in enumerate(V21B_CELL_ORDER)}
        if value != sorted(value, key=order.__getitem__):
            raise PostformalEvalError(f"selection {name} is not in V21B_CELL_ORDER")
        return value

    eligible = validate_cell_list(selection.get("eligible_release_cells"), name="eligible_release_cells")
    ineligible = validate_cell_list(selection.get("ineligible_release_cells"), name="ineligible_release_cells")
    if set(eligible) & set(ineligible) or set(eligible) | set(ineligible) != set(V21B_CELL_ORDER):
        raise PostformalEvalError("selection eligible/ineligible cell lists are not a disjoint complete partition")
    if bool(eligible) != (status == "SELECTION_PASS"):
        raise PostformalEvalError("selection global status does not match eligible cells")
    if eligible:
        if "reason" in selection:
            raise PostformalEvalError("SELECTION_PASS selection must not carry a global reason")
    elif selection.get("reason") != "NO_RELEASE_ELIGIBLE_CELL":
        raise PostformalEvalError("NO_RELEASE selection requires NO_RELEASE_ELIGIBLE_CELL")

    reasons = selection.get("no_release_reasons")
    if not isinstance(reasons, Mapping) or set(reasons) != set(ineligible):
        raise PostformalEvalError("selection no_release_reasons keys do not match ineligible cells")
    if any(not isinstance(reasons[cell], str) or reasons[cell] not in SELECTION_NO_RELEASE_REASONS for cell in ineligible):
        raise PostformalEvalError("selection no_release_reasons values are invalid")
    for cell in V21B_CELL_ORDER:
        entry = cells[cell]
        if not isinstance(entry, Mapping):
            raise PostformalEvalError(f"selection entry {cell} is not a mapping")
        expected_status = "RELEASE_ELIGIBLE" if cell in eligible else "NO_RELEASE"
        if entry.get("status") != expected_status:
            raise PostformalEvalError(f"selection entry {cell} status is not bound to its list")
        required_entry_keys = {"status", "mechanism", "release", "distinct", "dv_readout"}
        if expected_status == "NO_RELEASE":
            required_entry_keys.add("reason")
        if set(entry) != required_entry_keys:
            raise PostformalEvalError(f"selection entry {cell} schema keys are not exact")
        mechanism = entry.get("mechanism")
        release = entry.get("release")
        if expected_status == "RELEASE_ELIGIBLE":
            _validate_selection_row(mechanism, cell=cell, name=f"{cell} mechanism")
            _validate_selection_row(release, cell=cell, name=f"{cell} release")
            if mechanism.get("row_id") == release.get("row_id"):
                raise PostformalEvalError(f"selection entry {cell} mechanism/release are not distinct")
            if release.get("release_gate_status", release.get("gate_status")) != "PASS":
                raise PostformalEvalError(f"selection entry {cell} release gate is not PASS")
            if entry.get("distinct") is not True:
                raise PostformalEvalError(f"selection entry {cell} distinct flag is invalid")
        else:
            if release is not None or entry.get("distinct") is not False:
                raise PostformalEvalError(f"selection entry {cell} ineligible release contract is invalid")
            if entry.get("reason") != reasons[cell]:
                raise PostformalEvalError(f"selection entry {cell} reason is not bound")
            if mechanism is not None:
                _validate_selection_row(mechanism, cell=cell, name=f"{cell} mechanism")


def validate_pooled_report_for_freeze(
    report: Mapping[str, Any],
    *,
    cell: str,
    release: Mapping[str, Any],
    pooled_queue: Mapping[str, Any],
) -> None:
    """Validate the exact pooled48 evidence contract required by release freeze."""

    if not isinstance(report, Mapping) or report.get("schema") != POOLED_REPORT_SCHEMA:
        raise PostformalEvalError("pooled freeze report schema is invalid")
    if report.get("status") != "PASS" or report.get("topology") != "pooled_seed16" or report.get("episode_count") != 48:
        raise PostformalEvalError("pooled freeze report status/topology/cardinality is invalid")
    if report.get("seed_counts") != {0: 16, 1: 16, 2: 16}:
        raise PostformalEvalError("pooled freeze report seed counts are invalid")
    if report.get("cell") != cell or cell not in V21B_CELL_ORDER:
        raise PostformalEvalError("pooled freeze report cell is not bound")
    if report.get("baseline_cell") != "B1":
        raise PostformalEvalError("pooled freeze report baseline must be B1")
    if not isinstance(release, Mapping) or release.get("cell") != cell or not isinstance(release.get("row_id"), str):
        raise PostformalEvalError("pooled freeze release row is invalid")
    if report.get("selected_release_row_id") != release.get("row_id"):
        raise PostformalEvalError("pooled freeze report selected release row is not bound")
    if not isinstance(pooled_queue, Mapping):
        raise PostformalEvalError("pooled freeze queue is required")
    validate_route_b_queue(pooled_queue)
    if pooled_queue.get("topology") != "pooled_seed16" or pooled_queue.get("cell") != cell:
        raise PostformalEvalError("pooled freeze queue cell/topology is invalid")
    if report.get("queue_receipt_sha256") != pooled_queue.get("receipt_sha256"):
        raise PostformalEvalError("pooled freeze report queue receipt is not bound")
    _digest(report.get("queue_receipt_sha256"), name="pooled freeze report queue receipt sha256")
    gates = report.get("gates")
    if not isinstance(gates, Mapping) or set(gates) != set(POOLED_REQUIRED_GATES) or any(value is not True for value in gates.values()):
        raise PostformalEvalError("pooled freeze report gates are not the exact all-true pooled contract")
    metrics = report.get("metrics")
    if not isinstance(metrics, Mapping):
        raise PostformalEvalError("pooled freeze report metrics are required")
    for name in POOLED_REQUIRED_METRICS:
        _finite(metrics.get(name), name=f"pooled freeze report metric {name}")
    failed_gates = report.get("failed_gates")
    if failed_gates != []:
        raise PostformalEvalError("pooled freeze report failed_gates must be empty")
    report_identity = report.get("candidate_identity")
    if not isinstance(report_identity, Mapping) or set(report_identity) != set(RECORD_CANDIDATE_KEYS):
        raise PostformalEvalError("pooled freeze report candidate identity is incomplete")
    release_record_identity = _candidate_projection(release, keys=RECORD_CANDIDATE_KEYS)
    if _candidate_projection(report_identity, keys=RECORD_CANDIDATE_KEYS) != release_record_identity:
        raise PostformalEvalError("pooled freeze report candidate identity is not bound to release")
    release_queue_identity = _candidate_projection(release, keys=ROUTE_B_CANDIDATE_KEYS)
    if _candidate_projection(pooled_queue.get("candidate_identity", {}), keys=ROUTE_B_CANDIDATE_KEYS) != release_queue_identity:
        raise PostformalEvalError("pooled freeze queue candidate identity is not bound to release")
    for row in pooled_queue.get("rows", ()):
        if not isinstance(row, Mapping) or row.get("cell") != cell:
            raise PostformalEvalError("pooled freeze queue row cell is not bound")
        if _candidate_projection(row.get("candidate_identity", {}), keys=ROUTE_B_CANDIDATE_KEYS) != release_queue_identity:
            raise PostformalEvalError("pooled freeze queue row candidate identity is not bound")


def select_mechanism_release(
    route_a_rows: Sequence[Mapping[str, Any]],
    *,
    f3_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Select distinct mechanism and release checkpoints per cell."""

    if not isinstance(route_a_rows, Sequence) or len(route_a_rows) != 70:
        raise PostformalEvalError("mechanism/release selection requires exactly 70 Route-A metric rows")
    grouped: dict[str, list[Mapping[str, Any]]] = {cell: [] for cell in V21B_CELL_ORDER}
    for row in route_a_rows:
        cell = row.get("cell")
        if cell not in grouped:
            raise PostformalEvalError("Route-A metric row has an unknown cell")
        grouped[cell].append(row)
    selected: dict[str, Any] = {}
    no_release_reasons: dict[str, str] = {}
    eligible_release_cells: list[str] = []
    ineligible_release_cells: list[str] = []
    for cell, rows in grouped.items():
        if len(rows) != 10:
            raise PostformalEvalError(f"{cell} requires exactly 10 Route-A rows for selection")
        candidates = [row for row in rows if row.get("strict_status") == "STRICT_VALID"]
        def score(row: Mapping[str, Any]) -> tuple[float, float, int]:
            metrics = row.get("metrics", {})
            if not isinstance(metrics, Mapping):
                raise PostformalEvalError("Route-A selection metrics mapping is missing")
            hinge_value = metrics.get("hinge_at_crossing_p50")
            task_value = metrics.get("task_time_p95")
            if isinstance(hinge_value, Mapping) or isinstance(task_value, Mapping) or hinge_value is None or task_value is None:
                raise PostformalEvalError("Route-A mechanism selection cannot rank a typed N/A or missing metric")
            hinge = _finite(hinge_value, name="mechanism hinge")
            task = _finite(task_value, name="mechanism task time")
            return (-hinge, task, int(row["step"]))
        mechanism: Mapping[str, Any] | None = None
        reason: str | None = None
        if not candidates:
            reason = "INSUFFICIENT_STRICT_VALID_CHECKPOINTS"
        else:
            try:
                mechanism = sorted(candidates, key=score)[0]
            except PostformalEvalError:
                reason = "UNRANKABLE_MECHANISM_METRIC"
        promotable = [row for row in candidates if row.get("release_gate_status", row.get("gate_status", "FAIL")) == "PASS"]
        release: Mapping[str, Any] | None = None
        if mechanism is not None:
            if len(candidates) < 2:
                reason = "INSUFFICIENT_STRICT_VALID_CHECKPOINTS"
            elif not promotable:
                reason = "NO_PROMOTABLE_ROUTE_A_CHECKPOINT"
            else:
                release = sorted(promotable, key=lambda row: (int(row["step"]),))[0]
                if release.get("row_id") == mechanism.get("row_id"):
                    alternatives = [row for row in promotable if row.get("row_id") != mechanism.get("row_id")]
                    if not alternatives:
                        reason = "MECHANISM_RELEASE_NOT_DISTINCT"
                        release = None
                    else:
                        release = sorted(alternatives, key=lambda row: (int(row["step"]),))[0]
        if mechanism is not None and release is not None:
            eligible_release_cells.append(cell)
            selected[cell] = {
                "status": "RELEASE_ELIGIBLE",
                "mechanism": dict(mechanism),
                "release": dict(release),
                "distinct": True,
                "dv_readout": f3_dv_readout(f3_context) if f3_context is not None else None,
            }
        else:
            ineligible_release_cells.append(cell)
            if reason is None:
                reason = "UNRANKABLE_MECHANISM_METRIC"
            no_release_reasons[cell] = reason
            selected[cell] = {
                "status": "NO_RELEASE",
                "mechanism": None if mechanism is None else dict(mechanism),
                "release": None,
                "distinct": False,
                "reason": reason,
                "dv_readout": f3_dv_readout(f3_context) if f3_context is not None else None,
            }
    result = {
        "schema": SELECTION_SCHEMA,
        "status": "SELECTION_PASS" if eligible_release_cells else "NO_RELEASE",
        "completed": True,
        "cells": selected,
        "eligible_release_cells": eligible_release_cells,
        "ineligible_release_cells": ineligible_release_cells,
        "no_release_reasons": no_release_reasons,
    }
    if not eligible_release_cells:
        result["reason"] = "NO_RELEASE_ELIGIBLE_CELL"
    return result


def freeze_release_candidate(
    selection: Mapping[str, Any],
    *,
    cell: str,
    f3_context: Mapping[str, Any] | None = None,
    pooled_report: Mapping[str, Any] | None = None,
    pooled_queue: Mapping[str, Any] | None = None,
    acceptance_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze exactly one release candidate with full identity hashes."""

    validate_selection(selection)
    if selection.get("schema") != "a2_piper_base_v21B_selection_v1" or selection.get("status") != "SELECTION_PASS":
        raise PostformalEvalError("release freeze requires a valid selection")
    if cell not in V21B_CELL_ORDER:
        raise PostformalEvalError("release freeze cell is invalid")
    eligible_release_cells = selection.get("eligible_release_cells")
    if not isinstance(eligible_release_cells, Sequence) or cell not in eligible_release_cells:
        raise PostformalEvalError("release freeze requires the requested cell to be release-eligible")
    cells = selection.get("cells")
    if not isinstance(cells, Mapping):
        raise PostformalEvalError("release selection cells mapping is missing")
    cell_selection = cells.get(cell)
    if not isinstance(cell_selection, Mapping):
        raise PostformalEvalError(f"release selection is missing {cell}")
    if cell_selection.get("status") != "RELEASE_ELIGIBLE":
        raise PostformalEvalError("release freeze requires a RELEASE_ELIGIBLE cell")
    release = cell_selection.get("release")
    mechanism = cell_selection.get("mechanism")
    if not isinstance(release, Mapping) or not isinstance(mechanism, Mapping) or release.get("row_id") == mechanism.get("row_id"):
        raise PostformalEvalError("release freeze requires distinct mechanism/release rows")
    if release.get("cell") != cell or mechanism.get("cell") != cell:
        raise PostformalEvalError("release freeze mechanism/release rows must belong to the requested cell")
    if release.get("strict_status") != "STRICT_VALID" or mechanism.get("strict_status") != "STRICT_VALID":
        raise PostformalEvalError("release freeze requires strict-valid mechanism/release rows")
    if release.get("release_gate_status", release.get("gate_status")) != "PASS":
        raise PostformalEvalError("release freeze requires a release-gate PASS checkpoint")
    validate_pooled_report_for_freeze(
        pooled_report,
        cell=cell,
        release=release,
        pooled_queue=pooled_queue,
    )
    if acceptance_profile is None or not isinstance(acceptance_profile, Mapping):
        raise PostformalEvalError("release freeze requires the frozen acceptance profile")
    required = (
        "evaluated_checkpoint_path",
        "evaluated_checkpoint_sha256",
        "config_path",
        "config_sha256",
        "evaluation_command_sha256",
        "source_lock_sha256",
        "source_config_sha256",
        "materialization_sha256",
        "materialized_config_sha256",
        "adaptation_bundle_sha256",
    )
    for key in required:
        if key not in release:
            raise PostformalEvalError(f"release candidate is missing {key}")
        if key.endswith("sha256"):
            _digest(release[key], name=f"release candidate {key}")
    pooled_report_sha = _canonical_sha256(pooled_report, name="pooled report")
    pooled_queue_sha = _canonical_sha256(pooled_queue, name="pooled queue")
    selection_sha = _canonical_sha256(selection, name="selection")
    freeze = {
        "schema": RELEASE_FREEZE_SCHEMA,
        "status": "RELEASE_FROZEN",
        "plan_id": V21B_PLAN_ID,
        "cell": cell,
        "mechanism_checkpoint": _canonical_snapshot(mechanism, name="mechanism checkpoint"),
        "release_checkpoint": _canonical_snapshot(release, name="release checkpoint"),
        "f3_mode": None if f3_context is None else f3_context.get("mode"),
        "full_hashes": {key: release[key] for key in required},
        "acceptance_profile": _canonical_snapshot(acceptance_profile, name="acceptance profile"),
        "selection_sha256": selection_sha,
        "selection_snapshot": _canonical_snapshot(selection, name="selection"),
        "pooled_report_sha256": pooled_report_sha,
        "pooled_report_snapshot": _canonical_snapshot(pooled_report, name="pooled report"),
        "pooled_queue_sha256": pooled_queue_sha,
        "pooled_queue_snapshot": _canonical_snapshot(pooled_queue, name="pooled queue"),
        "pooled_queue_receipt_sha256": pooled_queue.get("receipt_sha256"),
        "pooled_report_topology": pooled_report.get("topology"),
        "post_freeze_intervention_change": False,
    }
    freeze["freeze_sha256"] = hashlib.sha256(canonical_json_bytes(freeze)).hexdigest()
    return freeze


def validate_release_freeze(freeze: Mapping[str, Any]) -> None:
    if not isinstance(freeze, Mapping) or freeze.get("schema") != RELEASE_FREEZE_SCHEMA or freeze.get("status") != "RELEASE_FROZEN":
        raise PostformalEvalError("release freeze schema/status is invalid")
    if set(freeze) != set(RELEASE_FREEZE_KEYS):
        raise PostformalEvalError("release freeze top-level keys are not exact")
    if freeze.get("plan_id") != V21B_PLAN_ID:
        raise PostformalEvalError("release freeze plan_id is not bound to v21-B")
    if freeze.get("post_freeze_intervention_change") is not False:
        raise PostformalEvalError("release freeze records a post-freeze intervention")
    cell = freeze.get("cell")
    if cell not in V21B_CELL_ORDER:
        raise PostformalEvalError("release freeze cell is invalid")
    release = freeze.get("release_checkpoint")
    mechanism = freeze.get("mechanism_checkpoint")
    hashes = freeze.get("full_hashes")
    if not isinstance(release, Mapping) or not isinstance(mechanism, Mapping) or not isinstance(hashes, Mapping):
        raise PostformalEvalError("release freeze identity is incomplete")
    required = (
        "evaluated_checkpoint_path",
        "evaluated_checkpoint_sha256",
        "config_path",
        "config_sha256",
        "evaluation_command_sha256",
        "source_lock_sha256",
        "source_config_sha256",
        "materialization_sha256",
        "materialized_config_sha256",
        "adaptation_bundle_sha256",
    )
    if set(hashes) != set(required):
        raise PostformalEvalError("release freeze full_hashes keys are not exact")
    for key in required:
        if release.get(key) != hashes.get(key):
            raise PostformalEvalError(f"release freeze {key} is not bound")
    if not isinstance(freeze.get("acceptance_profile"), Mapping):
        raise PostformalEvalError("release freeze acceptance profile is missing")

    selection_snapshot = freeze.get("selection_snapshot")
    pooled_report_snapshot = freeze.get("pooled_report_snapshot")
    pooled_queue_snapshot = freeze.get("pooled_queue_snapshot")
    for snapshot, digest_key, name in (
        (selection_snapshot, "selection_sha256", "selection snapshot"),
        (pooled_report_snapshot, "pooled_report_sha256", "pooled report snapshot"),
        (pooled_queue_snapshot, "pooled_queue_sha256", "pooled queue snapshot"),
    ):
        if not isinstance(snapshot, Mapping):
            raise PostformalEvalError(f"release freeze {name} is missing")
        _digest(freeze.get(digest_key), name=f"release freeze {digest_key}")
        if _canonical_sha256(snapshot, name=name) != freeze.get(digest_key):
            raise PostformalEvalError(f"release freeze {name} digest does not bind payload")

    validate_selection(selection_snapshot)
    selection_cells = selection_snapshot["cells"]
    if cell not in selection_snapshot["eligible_release_cells"]:
        raise PostformalEvalError("release freeze selected cell is not eligible in its selection snapshot")
    selected = selection_cells[cell]
    if selected.get("status") != "RELEASE_ELIGIBLE":
        raise PostformalEvalError("release freeze selected cell status is not RELEASE_ELIGIBLE")
    if canonical_json_bytes(selected.get("mechanism")) != canonical_json_bytes(mechanism):
        raise PostformalEvalError("release freeze mechanism snapshot is not bound to selection")
    if canonical_json_bytes(selected.get("release")) != canonical_json_bytes(release):
        raise PostformalEvalError("release freeze release snapshot is not bound to selection")

    validate_route_b_queue(pooled_queue_snapshot)
    validate_pooled_report_for_freeze(
        pooled_report_snapshot,
        cell=cell,
        release=release,
        pooled_queue=pooled_queue_snapshot,
    )
    if freeze.get("pooled_report_topology") != pooled_report_snapshot.get("topology"):
        raise PostformalEvalError("release freeze pooled report topology is not bound")
    _digest(freeze.get("pooled_queue_receipt_sha256"), name="release freeze pooled queue receipt sha256")
    if freeze.get("pooled_queue_receipt_sha256") != pooled_queue_snapshot.get("receipt_sha256"):
        raise PostformalEvalError("release freeze pooled queue receipt is not bound")
    if pooled_report_snapshot.get("queue_receipt_sha256") != pooled_queue_snapshot.get("receipt_sha256"):
        raise PostformalEvalError("release freeze report/queue receipt binding is invalid")
    digest = freeze.get("freeze_sha256")
    _digest(digest, name="release freeze sha256")
    unsigned = dict(freeze)
    unsigned.pop("freeze_sha256", None)
    if hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest() != digest:
        raise PostformalEvalError("release freeze sha256 does not bind payload")


def build_holdout64_report(
    records: Sequence[Mapping[str, Any]],
    *,
    frozen_release: Mapping[str, Any],
    theta_send_rad: float,
    baseline: Mapping[str, Any] | None = None,
    queue: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validate_release_freeze(frozen_release)
    if not isinstance(queue, Mapping):
        raise PostformalEvalError("holdout64 report requires its immutable holdout queue")
    validate_route_b_queue(queue)
    if queue.get("topology") != "holdout_seed16":
        raise PostformalEvalError("holdout64 report queue topology is invalid")
    release = frozen_release["release_checkpoint"]
    for record in records:
        a2_v21b_validate_task_record(record)
        _validate_task_identity(record)
        _record_candidate_identity(record, release)
        if record.get("topology") != "holdout_seed16":
            raise PostformalEvalError("holdout record topology is not holdout_seed16")
    result = adjudicate_route_b(records, topology="holdout_seed16", theta_send_rad=theta_send_rad, baseline=baseline, candidate_identity=release, queue=queue)
    queue_sha256 = hashlib.sha256(canonical_json_bytes(dict(queue))).hexdigest()
    return {
        "schema": HOLDOUT_SCHEMA,
        "frozen_release": dict(release),
        "queue_receipt_sha256": queue.get("receipt_sha256"),
        "queue_sha256": queue_sha256,
        **result,
    }


def build_render_queue(
    cases: Sequence[Mapping[str, Any]],
    *,
    output_root: Path,
    gpu: int = 3,
    scenario_manifest_path: Path = DEFAULT_SCENARIO_MANIFEST,
) -> dict[str, Any]:
    """Build five executions; each execution must emit all three configured cameras."""

    if not isinstance(cases, Sequence) or len(cases) != V21B_ROUTE_B_RENDER_CASES:
        raise PostformalEvalError("render queue requires exactly five predeclared cases")
    _validate_eval_gpu(gpu, name="render evaluation GPU")
    case_ids = [case.get("case_id") for case in cases if isinstance(case, Mapping)]
    if len(case_ids) != 5 or any(not isinstance(case_id, str) or not case_id for case_id in case_ids) or len(set(case_ids)) != 5:
        raise PostformalEvalError("render case IDs must be exactly five unique non-empty strings")
    output_root = Path(output_root).expanduser().resolve()
    rows: list[dict[str, Any]] = []
    expectations: list[dict[str, Any]] = []
    run_uuids: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise PostformalEvalError("render case must be a mapping")
        selected_env_id = case.get("selected_env_id")
        if isinstance(selected_env_id, bool) or not isinstance(selected_env_id, int) or not 0 <= selected_env_id < 16:
            raise PostformalEvalError("render case selected_env_id must be an integer in 0..15")
        checkpoint = _regular_file(Path(case.get("evaluated_checkpoint_path", "")), name="render evaluated checkpoint")
        evaluated_sha = _digest(case.get("evaluated_checkpoint_sha256"), name="render evaluated checkpoint sha256")
        config_path = _regular_file(Path(case.get("config_path", "")), name="render adjacent config")
        config_sha = _digest(case.get("config_sha256"), name="render config sha256")
        identity = {key: _digest(case.get(key), name=f"render {key}") for key in ("source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256", "adaptation_bundle_sha256")}
        scenario = _validate_signed_manifest(scenario_manifest_path, source_checkpoint_sha256=V21B_WARM_START_SHA256, source_lock_sha256=identity["source_lock_sha256"])
        config = _load_adjacent_config(config_path)
        render_root = output_root / str(case["case_id"])
        renderings_dir = render_root / "renderings"
        run_uuid = f"v21B-render-{case['case_id']}"
        if run_uuid in run_uuids:
            raise PostformalEvalError("render run_uuid values must be unique")
        run_uuids.add(run_uuid)
        overrides: list[str] = []

        def add(key: str, value: Any, *, string: bool = False) -> None:
            overrides.append(_hydra_override(config, key, value, string=string))

        for key, value, string in (
            ("checkpoint", str(checkpoint), True), ("checkpoint_load_mode", "full", False), ("auto_load_latest", False, False),
            ("headless", True, False), ("num_envs", 16, False), ("seed", 0, False), ("use_wandb", False, False),
            ("simulator.config.cameras.enable_cameras", True, False), ("simulator.config.render_results", True, False),
            ("algo.config.eval.eval_num_envs_episodes", True, False), ("algo.config.eval.num_eval_episodes", 16, False),
            ("algo.config.eval.a2_diagnostic_trace_enabled", True, False),
            ("algo.config.eval.a2_diagnostic_reward_terms", "[" + ",".join(ROUTE_A_DIAGNOSTIC_REWARD_TERMS) + "]", False),
            ("algo.config.eval.a2_eval_v20_strict_telemetry", True, False),
            ("algo.config.eval.a2_eval_m41_strict_telemetry", True, False), ("algo.config.eval.save_videos", True, False),
            ("algo.config.eval.save_trajectories", False, False), ("env.config.a2_v21B_render_case_id", case["case_id"], False),
            ("env.config.a2_v21B_render_env_id", selected_env_id, False),
            ("env.config.a2_v21B_cell", case.get("cell", "B1"), False),
            ("env.config.a2_v21B_source_checkpoint_path", case.get("source_checkpoint_path", V21B_WARM_START_PATH), True),
            ("env.config.a2_v21B_source_checkpoint_sha256", case.get("source_checkpoint_sha256", V21B_WARM_START_SHA256), False),
            ("env.config.a2_v21B_source_lock_sha256", identity["source_lock_sha256"], False), ("env.config.a2_v21B_source_config_sha256", identity["source_config_sha256"], False),
            ("env.config.a2_v21B_materialization_sha256", identity["materialization_sha256"], False), ("env.config.a2_v21B_materialized_config_sha256", identity["materialized_config_sha256"], False),
            ("env.config.a2_v21B_adaptation_bundle_sha256", identity["adaptation_bundle_sha256"], False), ("env.config.a2_v21B_evaluated_checkpoint_path", str(checkpoint), True),
            ("env.config.a2_v21B_evaluated_checkpoint_sha256", evaluated_sha, False), ("env.config.a2_v21B_terminal_export_root", str(render_root), True),
            ("env.config.a2_v21B_run_uuid", run_uuid, True), ("env.config.a2_v21B_queue_row_id", f"render:{case['case_id']}", True), ("env.config.a2_v21B_evaluation_root", str(render_root), True),
            ("env.config.save_rendering_dir", str(renderings_dir), True), ("env.config.a2_v21B_census_topology", "canonical16", False),
            ("env.config.a2_v21B_evidence_aggregation_topology", "render1", False), ("env.config.a2_v21B_signed_probe_scenarios_enabled", True, False),
            ("env.config.a2_v21B_scenario_manifest_path", scenario["path"], True), ("env.config.a2_v21B_scenario_manifest_sha256", scenario["manifest_sha256"], False),
            ("env.config.a2_v21B_scenario_manifest_file_sha256", scenario["file_sha256"], False), ("env.config.a2_v21B_canonical_manifest_sha256", scenario["canonical_manifest_sha256"], False),
            ("env.config.a2_v21B_scenario_manifest_source_checkpoint_sha256", scenario["manifest"]["source_checkpoint_sha256"], False), ("env.config.a2_v21B_scenario_manifest_source_lock_sha256", scenario["manifest"]["source_lock_sha256"], False),
            ("env.config.a2_v21B_scenario_manifest_source_config_sha256", scenario["manifest"]["source_config_sha256"], False), ("env.config.a2_v21B_scenario_manifest_materialization_sha256", scenario["materialization_sha256"], False),
            ("env.config.a2_v21B_scenario_manifest_json_sha256", scenario["manifest_json_sha256"], False), ("env.config.a2_v21B_scenario_manifest_json", scenario["manifest_json"], True),
            ("env.config.a2_v20_R2_seed", 0, False), ("env.config.a2_v20_R2_full_evidence", True, False), ("env.config.a2_v20_R2_evidence_enabled", True, False),
            ("env.config.a2_v21B_evidence_enabled", True, False), ("eval_output_dir", str(render_root), True),
        ):
            add(key, value, string=string)
        argv = ["/home/baoquanc/anaconda3/envs/isaaclab/bin/python", "-m", "gr00t.rl.eval_agent_trl", f"--config-dir={config_path.parent}", f"--config-name={config_path.stem}", *overrides]
        env = {"CUDA_VISIBLE_DEVICES": str(gpu), "ACCELERATE_TORCH_DEVICE": "cuda:0", "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json"}
        argv.append(COMMAND_IDENTITY_OVERRIDE + command_sha256(argv, env))
        row = {
            "row_id": f"render:{case['case_id']}", "case_id": case["case_id"], "topology": "render1", "runtime_scenario_topology": "canonical16", "evidence_aggregation_topology": "render1", "seed": 0, "physical_gpu": gpu,
            "source_checkpoint_path": case.get("source_checkpoint_path", V21B_WARM_START_PATH), "source_checkpoint_sha256": case.get("source_checkpoint_sha256", V21B_WARM_START_SHA256),
            "evaluated_checkpoint_path": str(checkpoint), "evaluated_checkpoint_sha256": evaluated_sha, "config_path": str(config_path), "config_sha256": config_sha, **identity,
            "materialization_phase": "FORMAL_PROMOTED", "arm_profile": "ARM_V20", "output_root": str(render_root), "argv": argv, "env": env,
            "evaluation_command_sha256": _declared_command_identity(argv, env), "run_uuid": run_uuid, "expected_env_ids": list(range(16)), "selected_env_id": selected_env_id, "queue_row_id": f"render:{case['case_id']}", "strict_binding": True,
            "renderings_dir": str(renderings_dir),
            "scenario_manifest_path": scenario["path"], "scenario_manifest_sha256": scenario["manifest_sha256"], "scenario_manifest_file_sha256": scenario["file_sha256"], "canonical_manifest_sha256": scenario["canonical_manifest_sha256"],
            "candidate_identity": {**identity, "evaluated_checkpoint_path": str(checkpoint), "evaluated_checkpoint_sha256": evaluated_sha, "config_path": str(config_path), "config_sha256": config_sha},
        }
        row["camera_expectation_ids"] = [f"{case['case_id']}:{camera}" for camera in RENDER_EXPECTED_CAMERAS]
        rows.append(row)
        for camera in RENDER_EXPECTED_CAMERAS:
            camera_suffix = "" if camera == "main" else f"_{camera}"
            artifact_glob = f"*_env{selected_env_id:04d}_episode????{camera_suffix}_len*_reason-*.mp4"
            expectations.append({"expectation_id": f"{case['case_id']}:{camera}", "case_id": case["case_id"], "camera": camera, "row_id": row["row_id"], "run_uuid": run_uuid, "selected_env_id": selected_env_id, "evaluation_command_sha256": row["evaluation_command_sha256"], "candidate_identity": row["candidate_identity"], "renderings_dir": str(renderings_dir), "artifact_glob": artifact_glob})
    queue = {"schema": RENDER_QUEUE_SCHEMA, "status": "RENDER_QUEUE_READY", "row_count": 5, "case_count": 5, "camera_expectation_count": 15, "cameras": list(RENDER_EXPECTED_CAMERAS), "eval_allowed_gpus": list(V21B_EVAL_GPUS), "eval_gpu": gpu, "rows": rows, "camera_artifact_expectations": expectations}
    queue["receipt_sha256"] = _queue_receipt(queue)
    validate_render_queue(queue)
    return queue


def validate_render_queue(queue: Mapping[str, Any]) -> None:
    if queue.get("schema") != RENDER_QUEUE_SCHEMA or queue.get("row_count") != 5 or queue.get("case_count") != 5 or queue.get("camera_expectation_count") != 15 or tuple(queue.get("eval_allowed_gpus", ())) != V21B_EVAL_GPUS:
        raise PostformalEvalError("render queue schema/cardinality is invalid")
    _digest(queue.get("receipt_sha256"), name="render queue receipt_sha256")
    if queue.get("receipt_sha256") != _queue_receipt(queue):
        raise PostformalEvalError("render queue receipt does not bind immutable payload")
    _validate_eval_gpu(queue.get("eval_gpu"), name="render queue evaluation GPU")
    rows = queue.get("rows")
    expectations = queue.get("camera_artifact_expectations")
    if not isinstance(rows, list) or len(rows) != 5 or not isinstance(expectations, list) or len(expectations) != 15:
        raise PostformalEvalError("render queue requires five executions and fifteen camera expectations")
    expected_cases = {row.get("case_id") for row in rows if isinstance(row, Mapping)}
    if len(expected_cases) != 5 or {(item.get("case_id"), item.get("camera")) for item in expectations if isinstance(item, Mapping)} != {(case, camera) for case in expected_cases for camera in RENDER_EXPECTED_CAMERAS}:
        raise PostformalEvalError("render queue case/camera expectation topology is incomplete")
    row_by_id = {row.get("row_id"): row for row in rows if isinstance(row, Mapping)}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("topology") != "render1" or row.get("runtime_scenario_topology") != "canonical16" or row.get("evidence_aggregation_topology") != "render1" or row.get("strict_binding") is not True:
            raise PostformalEvalError("render queue row strict topology binding is invalid")
        if any("a2_v21B_render_camera" in token for token in row.get("argv", [])):
            raise PostformalEvalError("render queue must not use an unused per-camera override")
        if row.get("evaluation_command_sha256") != _declared_command_identity(row.get("argv"), row.get("env")):
            raise PostformalEvalError("render queue command hash mismatch")
        _validate_eval_gpu(row.get("physical_gpu"), name="render queue row evaluation GPU")
        if row.get("physical_gpu") != queue["eval_gpu"] or row.get("expected_env_ids") != list(range(16)):
            raise PostformalEvalError("render queue physical/env binding is invalid")
        selected_env_id = row.get("selected_env_id")
        if isinstance(selected_env_id, bool) or not isinstance(selected_env_id, int) or not 0 <= selected_env_id < 16:
            raise PostformalEvalError("render queue selected_env_id is invalid")
        if row.get("queue_row_id") != row.get("row_id") or row.get("renderings_dir") != str(Path(row.get("output_root", "")) / "renderings"):
            raise PostformalEvalError("render queue output/queue identity is invalid")
        if row.get("env", {}).get("CUDA_VISIBLE_DEVICES") != str(queue["eval_gpu"]) or row.get("env", {}).get("ACCELERATE_TORCH_DEVICE") != "cuda:0":
            raise PostformalEvalError("render queue CUDA environment is not physically bound")
        if not any("a2_v21B_signed_probe_scenarios_enabled=true" in item for item in row["argv"]):
            raise PostformalEvalError("render queue command lacks signed probe admission")
        if not any(item in row["argv"] for item in ("env.config.a2_v21B_census_topology=canonical16", "+env.config.a2_v21B_census_topology=canonical16")) or not any(item in row["argv"] for item in ("env.config.a2_v21B_evidence_aggregation_topology=render1", "+env.config.a2_v21B_evidence_aggregation_topology=render1")):
            raise PostformalEvalError("render queue command topology binding is invalid")
        if not any(item.split("=", 1)[1].strip("'\"") == str(selected_env_id) and item.split("=", 1)[0].lstrip("+") == "env.config.a2_v21B_render_env_id" for item in row["argv"] if "=" in item):
            raise PostformalEvalError("render queue command does not bind selected env_id")
        if not any(item.split("=", 1)[1].strip("'\"") == str(Path(row["output_root"]).resolve()) and item.split("=", 1)[0].lstrip("+") == "env.config.a2_v21B_evaluation_root" for item in row["argv"] if "=" in item):
            raise PostformalEvalError("render queue command does not bind evaluation root")
        if not any(item.split("=", 1)[1].strip("'\"") == str(Path(row["renderings_dir"]).resolve()) and item.split("=", 1)[0].lstrip("+") == "env.config.save_rendering_dir" for item in row["argv"] if "=" in item):
            raise PostformalEvalError("render queue command does not bind save_rendering_dir")
        if set(row.get("camera_expectation_ids", ())) != {f"{row.get('case_id')}:{camera}" for camera in RENDER_EXPECTED_CAMERAS}:
            raise PostformalEvalError("render queue row does not declare all three camera expectations")
    for item in expectations:
        if not isinstance(item, Mapping) or item.get("row_id") not in row_by_id or item.get("camera") not in RENDER_EXPECTED_CAMERAS:
            raise PostformalEvalError("render camera expectation is outside the execution queue")
        row = row_by_id[item["row_id"]]
        if item.get("run_uuid") != row.get("run_uuid") or item.get("selected_env_id") != row.get("selected_env_id") or item.get("evaluation_command_sha256") != row.get("evaluation_command_sha256") or item.get("candidate_identity") != row.get("candidate_identity") or item.get("renderings_dir") != row.get("renderings_dir"):
            raise PostformalEvalError("render camera expectation is not bound to execution identity")
        if not isinstance(item.get("artifact_glob"), str) or f"_env{row['selected_env_id']:04d}_" not in item["artifact_glob"]:
            raise PostformalEvalError("render camera expectation does not bind selected env filename")


def validate_render_qa(queue: Mapping[str, Any], qa: Mapping[str, Any]) -> dict[str, Any]:
    validate_render_queue(queue)
    if not isinstance(qa, Mapping) or qa.get("schema") != RENDER_QA_SCHEMA:
        raise PostformalEvalError("render QA schema is invalid")
    rows = qa.get("rows")
    if not isinstance(rows, list) or len(rows) != 15:
        raise PostformalEvalError("render QA requires exactly 15 decoded rows")
    expected = {item["expectation_id"]: item for item in queue["camera_artifact_expectations"]}
    seen: set[str] = set()
    row_by_id = {row["row_id"]: row for row in queue["rows"]}
    for row in rows:
        expectation_id = row.get("expectation_id", f"{row.get('case_id')}:{row.get('camera')}") if isinstance(row, Mapping) else None
        if expectation_id in seen or expectation_id not in expected:
            raise PostformalEvalError("render QA row is duplicated or outside the predeclared queue")
        seen.add(expectation_id)
        expected_row = expected[expectation_id]
        execution_row = row_by_id[expected_row["row_id"]]
        if row.get("case_id") != expected_row.get("case_id") or row.get("camera") != expected_row.get("camera") or row.get("run_uuid") != expected_row.get("run_uuid") or row.get("selected_env_id") != expected_row.get("selected_env_id") or row.get("evaluation_command_sha256") != expected_row.get("evaluation_command_sha256") or row.get("candidate_identity") != expected_row.get("candidate_identity"):
            raise PostformalEvalError("render QA row does not bind queued execution/candidate identity")
        if any(row.get(key) != "PASS" for key in ("decode_status", "contact_sheet_status", "strict_task_record_status", "strict_trace_status")):
            raise PostformalEvalError("render QA requires strict record/trace and media PASS for every camera")
        artifact_path = row.get("artifact_path")
        if not isinstance(artifact_path, str) or not artifact_path:
            raise PostformalEvalError("render QA requires exactly one discovered artifact per camera")
        artifact = _regular_file(Path(artifact_path), name="render QA artifact")
        renderings_dir = Path(expected_row["renderings_dir"]).expanduser().resolve()
        if artifact.parent != renderings_dir:
            raise PostformalEvalError("render QA artifact is outside the declared renderings directory")
        if not fnmatch.fnmatch(artifact.name, expected_row["artifact_glob"]):
            raise PostformalEvalError("render QA artifact filename does not match selected env/camera glob")
        discovered = sorted(path for path in renderings_dir.glob(expected_row["artifact_glob"]) if path.is_file() and not path.is_symlink())
        if len(discovered) != 1 or discovered[0].resolve() != artifact:
            raise PostformalEvalError("render QA requires exactly one artifact per camera with no extras")
        if row.get("artifact_env_id") != expected_row.get("selected_env_id") or row.get("artifact_camera") != expected_row.get("camera"):
            raise PostformalEvalError("render QA artifact env/camera identity is invalid")
        artifact_sha = _digest(row.get("artifact_sha256"), name="render QA artifact sha256")
        if sha256_file(artifact) != artifact_sha:
            raise PostformalEvalError("render QA artifact hash changed")
    if seen != set(expected):
        raise PostformalEvalError("render QA coverage is incomplete")
    return {"schema": RENDER_QA_SCHEMA, "status": "PASS", "row_count": 15, "queue_schema": queue["schema"], "queue_sha256": hashlib.sha256(canonical_json_bytes(dict(queue))).hexdigest(), "rows": [dict(row) for row in rows]}


def build_final_analysis(
    *,
    route_a_metrics: Mapping[str, Any],
    release_freeze: Mapping[str, Any] | None,
    holdout_report: Mapping[str, Any] | None,
    render_qa: Mapping[str, Any] | None,
    f3_context: Mapping[str, Any] | None = None,
    render_queue: Mapping[str, Any] | None = None,
    holdout_queue: Mapping[str, Any] | None = None,
    route_a_queue: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce a terminal report with explicit, fail-closed release gates.

    A release is only possible when every immutable queue and every signed
    evidence artifact is present and mutually bound.  Missing or malformed
    post-formal artifacts are represented as ``NO_RELEASE`` in the terminal
    report; they are never treated as deferred passes.
    """

    if not isinstance(route_a_metrics, Mapping) or route_a_metrics.get("schema") != ROUTE_A_METRICS_SCHEMA:
        raise PostformalEvalError("final analysis Route-A metrics schema is invalid")
    failed: list[str] = []
    route_a_status = route_a_metrics.get("status")
    route_a_rows = route_a_metrics.get("rows")
    expected_route_a_ids = {(cell, step) for cell in V21B_CELL_ORDER for step in V21B_FORMAL_CHECKPOINT_STEPS}
    actual_route_a_ids = {
        (row.get("cell"), row.get("step"))
        for row in route_a_rows
        if isinstance(row, Mapping)
    } if isinstance(route_a_rows, list) else set()
    route_a_rows_valid = False
    if isinstance(route_a_rows, list) and len(route_a_rows) == 70 and actual_route_a_ids == expected_route_a_ids:
        try:
            for row in route_a_rows:
                if not isinstance(row, Mapping):
                    raise PostformalEvalError("Route-A metric row is not a mapping")
                if row.get("strict_status") != "STRICT_VALID" or row.get("task_record_count") != 16 or row.get("arm_record_count") != 16:
                    raise PostformalEvalError("Route-A metric row strict cardinality is invalid")
                if row.get("runtime_scenario_topology", "canonical16") != "canonical16" or row.get("evidence_aggregation_topology", "canonical16") != "canonical16" or row.get("expected_env_ids", list(range(16))) != list(range(16)):
                    raise PostformalEvalError("Route-A metric row topology/env coverage is invalid")
                if not isinstance(row.get("evaluation_root"), str) or not row.get("evaluation_root") or not isinstance(row.get("run_uuid"), str) or not row.get("run_uuid"):
                    raise PostformalEvalError("Route-A metric row invocation identity is missing")
                _candidate_projection(row)
                if row.get("identity") != {key: row.get(key) for key in (
                    "source_checkpoint_sha256", "evaluated_checkpoint_sha256", "config_sha256",
                    "source_lock_sha256", "source_config_sha256", "materialization_sha256",
                    "materialized_config_sha256", "adaptation_bundle_sha256", "evaluation_command_sha256",
                )}:
                    raise PostformalEvalError("Route-A metric row identity projection is not exact")
            route_a_rows_valid = True
        except PostformalEvalError:
            route_a_rows_valid = False
    route_a_queue_valid = False
    if route_a_queue is None:
        failed.append("route_a_queue_missing")
    else:
        try:
            validate_route_a_queue(route_a_queue)
            queue_rows = {row.get("row_id"): row for row in route_a_queue["rows"] if isinstance(row, Mapping)}
            route_a_queue_valid = (
                route_a_metrics.get("route_a_queue_receipt_sha256") == route_a_queue.get("receipt_sha256")
                and len(queue_rows) == 70
                and all(
                    isinstance(row, Mapping)
                    and queue_rows.get(row.get("row_id"), {}).get("evaluation_command_sha256") == row.get("identity", {}).get("evaluation_command_sha256")
                    for row in route_a_rows
                )
            )
        except (PostformalEvalError, KeyError, TypeError):
            route_a_queue_valid = False
    if route_a_status != "PASS" or route_a_metrics.get("row_count") != 70 or route_a_metrics.get("strict_valid_rows") != 70 or not route_a_rows_valid or not route_a_queue_valid:
        failed.append("route_a_not_pass")

    frozen: dict[str, Any] | None = None
    freeze_valid = False
    if release_freeze is None:
        failed.append("release_not_frozen")
    else:
        try:
            validate_release_freeze(release_freeze)
            frozen = dict(release_freeze)
            freeze_valid = True
        except PostformalEvalError:
            failed.append("release_freeze_invalid")

    if not freeze_valid:
        holdout_status = "NOT_TESTED"
        render_status = "NOT_TESTED"
        final_status = "NO_RELEASE"
    else:
        assert frozen is not None
        frozen_release = frozen["release_checkpoint"]

        # Holdout queue/report are both mandatory for a frozen release.
        holdout_status = "FAIL"
        holdout_queue_valid = False
        if holdout_queue is None:
            failed.append("holdout64:queue_missing")
        else:
            try:
                validate_route_b_queue(holdout_queue)
                queue_candidate = _candidate_projection(holdout_queue.get("candidate_identity", {}), keys=ROUTE_B_CANDIDATE_KEYS)
                frozen_candidate = _candidate_projection(frozen_release, keys=ROUTE_B_CANDIDATE_KEYS)
                seeds = {row.get("seed") for row in holdout_queue["rows"] if isinstance(row, Mapping)}
                holdout_queue_valid = (
                    holdout_queue.get("topology") == "holdout_seed16"
                    and holdout_queue.get("cell") == frozen.get("cell")
                    and len(holdout_queue["rows"]) == 4
                    and seeds == set(V21B_ROUTE_B_HOLDOUT_SEEDS)
                    and queue_candidate == frozen_candidate
                    and all(_candidate_projection(row.get("candidate_identity", {}), keys=ROUTE_B_CANDIDATE_KEYS) == frozen_candidate for row in holdout_queue["rows"])
                )
            except (PostformalEvalError, KeyError, TypeError):
                holdout_queue_valid = False
            if not holdout_queue_valid:
                failed.append("holdout64:queue_invalid")

        report_valid = False
        if holdout_report is None:
            failed.append("holdout64:report_missing")
        elif isinstance(holdout_report, Mapping):
            try:
                gates = holdout_report.get("gates")
                report_candidate = _candidate_projection(holdout_report.get("candidate_identity", {}), keys=RECORD_CANDIDATE_KEYS)
                frozen_record_candidate = _candidate_projection(frozen_release, keys=RECORD_CANDIDATE_KEYS)
                report_queue_sha = _digest(holdout_report.get("queue_sha256"), name="holdout report queue sha256")
                report_queue_receipt = _digest(holdout_report.get("queue_receipt_sha256"), name="holdout report queue receipt sha256")
                expected_queue_sha = hashlib.sha256(canonical_json_bytes(dict(holdout_queue))).hexdigest() if holdout_queue is not None else None
                report_valid = (
                    holdout_report.get("schema") == HOLDOUT_SCHEMA
                    and holdout_report.get("status") == "PASS"
                    and holdout_report.get("topology") == "holdout_seed16"
                    and holdout_report.get("episode_count") == 64
                    and holdout_report.get("seed_counts") == {seed: 16 for seed in V21B_ROUTE_B_HOLDOUT_SEEDS}
                    and isinstance(gates, Mapping)
                    and set(gates) == set(HOLDOUT_REQUIRED_GATES)
                    and all(value is True for value in gates.values())
                    and report_candidate == frozen_record_candidate
                    and holdout_report.get("frozen_release") == frozen_release
                    and holdout_queue_valid
                    and report_queue_receipt == holdout_queue.get("receipt_sha256")
                    and report_queue_sha == expected_queue_sha
                )
            except (PostformalEvalError, KeyError, TypeError):
                report_valid = False
        if not report_valid:
            failed.append("holdout64:report_invalid")
        elif holdout_queue_valid:
            holdout_status = "PASS"
        if holdout_status != "PASS":
            failed.append(f"holdout64:{holdout_status}")

        # Render queue and QA are also mandatory and are validated against the
        # frozen candidate before media is considered a release artifact.
        render_status = "FAIL"
        render_queue_valid = False
        if render_queue is None:
            failed.append("render:queue_missing")
        else:
            try:
                validate_render_queue(render_queue)
                frozen_render_candidate = _candidate_projection(frozen_release, keys=ROUTE_B_CANDIDATE_KEYS)
                render_queue_valid = all(
                    _candidate_projection(row.get("candidate_identity", {}), keys=ROUTE_B_CANDIDATE_KEYS) == frozen_render_candidate
                    for row in render_queue["rows"]
                )
            except (PostformalEvalError, KeyError, TypeError):
                render_queue_valid = False
            if not render_queue_valid:
                failed.append("render:queue_invalid")
        render_qa_valid = False
        if render_queue_valid and render_qa is not None:
            try:
                validate_render_qa(render_queue, render_qa)
                expected_render_queue_sha = hashlib.sha256(canonical_json_bytes(dict(render_queue))).hexdigest()
                render_qa_valid = (
                    render_qa.get("schema") == RENDER_QA_SCHEMA
                    and render_qa.get("status") == "PASS"
                    and render_qa.get("queue_schema") == RENDER_QUEUE_SCHEMA
                    and render_qa.get("queue_sha256") == expected_render_queue_sha
                )
            except (PostformalEvalError, KeyError, TypeError):
                render_qa_valid = False
        elif render_qa is None:
            failed.append("render:qa_missing")
        if not render_qa_valid and render_qa is not None:
            failed.append("render:qa_invalid")
        if render_queue_valid and render_qa_valid:
            render_status = "PASS"
        if render_status != "PASS":
            failed.append(f"render:{render_status}")
        final_status = "RELEASE" if not failed else "NO_RELEASE"
    return {
        "schema": FINAL_ANALYSIS_SCHEMA,
        "status": final_status,
        "route_a_status": route_a_status,
        "release_freeze": frozen,
        "holdout64_status": holdout_status,
        "render_status": render_status,
        "failed_gates": failed,
        "f3_dv_readout": None if f3_context is None else f3_dv_readout(f3_context),
        "scientific_terminal_state": "RELEASE" if final_status == "RELEASE" else "NO_RELEASE",
        "runtime_evaluation_executed_by_tool": False,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--formal-root", type=Path, required=True)
    parser.add_argument("--f3-root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.validate_only:
        raise PostformalEvalError("only --validate-only is available before runtime evaluation artifacts exist")
    f3 = validate_f3_promotion(args.f3_root)
    completion = validate_formal_completion(args.formal_root, f3_context=f3)
    manifest = build_route_a_manifest(completion, f3_context=f3)
    validate_route_a_manifest(manifest, check_files=True)
    print(json.dumps({
        "status": "PASS",
        "formal_completion": completion["status"],
        "f3": f3["status"],
        "route_a_manifest_rows": manifest["row_count"],
        "route_a_topology": "exact B1..B7 × 250..2500 canonical16 first-episode queue",
        "gpu_evaluation_executed": False,
    }, sort_keys=True))
    return 0


__all__ = [
    "PostformalEvalError", "FORMAL_COMPLETION_SCHEMA", "ROUTE_A_MANIFEST_SCHEMA", "ROUTE_A_QUEUE_SCHEMA", "ROUTE_A_METRICS_SCHEMA", "SELECTION_SCHEMA", "POOLED_REPORT_SCHEMA", "RELEASE_FREEZE_SCHEMA", "RELEASE_FREEZE_KEYS", "HOLDOUT_SCHEMA", "RENDER_QUEUE_SCHEMA", "RENDER_QA_SCHEMA", "FINAL_ANALYSIS_SCHEMA", "TOPOLOGY_EPISODES", "DV_NA_CENSUS_REASON", "DV_NA_F3_REASON",
    "V21B_EVAL_GPUS", "V21B_EVAL_GPU_BY_CELL", "ROUTE_A_DIAGNOSTIC_REWARD_TERMS", "PROCESS_RECEIPT_SCHEMA", "COMPLETION_SEAL_SCHEMA", "EPISODE_BUNDLE_COMPLETE_SCHEMA", "POSTFORMAL_PROCESS_RECEIPT_SCHEMA", "POSTFORMAL_COMPLETION_SEAL_SCHEMA", "validate_signed_runtime_topology", "validate_formal_cell", "validate_formal_completion", "validate_f3_promotion", "build_route_a_manifest", "validate_route_a_manifest", "build_route_a_queue", "build_route_a_eval_queue", "validate_route_a_queue", "build_route_b_queue", "validate_route_b_queue", "validate_route_a_evidence_row", "validate_route_b_evidence_row", "write_route_a_process_completion", "produce_route_a_process_completion", "write_route_a_process_receipt", "validate_route_a_process_completion", "validate_route_a_process_receipt", "write_route_b_process_completion", "produce_route_b_process_completion", "write_route_b_process_receipt", "validate_route_b_process_completion", "validate_route_b_process_receipt", "build_route_a_metrics", "validate_selection", "validate_pooled_report_for_freeze", "f3_dv_readout", "adjudicate_route_b", "adjudicate_route_b_evidence", "select_mechanism_release", "freeze_release_candidate", "validate_release_freeze", "build_holdout64_report", "build_render_queue", "validate_render_queue", "validate_render_qa", "build_final_analysis", "main",
]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PostformalEvalError, V21BError) as exc:
        print(f"v21-B POSTFORMAL FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
