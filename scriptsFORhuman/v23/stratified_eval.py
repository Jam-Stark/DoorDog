"""Realized-dynamics stratification for the pooled48 Route-B evidence.

The v23 evaluator does not expose a D1 global-step sampler hook.  Route-B
therefore classifies the already-realized pooled traces post hoc, using the
R190 physics-first labels and the measured external-atlas parameter tuples.
Naturally sparse stage traces and realized tuples without an exact atlas match
remain typed unclassified episodes; they are never mapped to a nearest/default
zone and never filled with zero.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
    from .pooled48 import (
        POOLED48_JOB_SCHEMA,
        POOLED48_JOB_STATUS,
        POOLED48_RECEIPT_PATH,
        POOLED48_SCHEMA,
        POOLED48_STATUS,
        PHYSICAL_GPU_DOMAIN,
        PHYSICAL_GPU_MAPPING_POLICY,
        _absolute as _pooled_absolute,
        validate_physical_gpus,
        load_selected_candidates,
        validate_selected_candidates,
    )
except ImportError:  # direct ``python scriptsFORhuman/v23/stratified_eval.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
    from scriptsFORhuman.v23.pooled48 import (
        POOLED48_JOB_SCHEMA,
        POOLED48_JOB_STATUS,
        POOLED48_RECEIPT_PATH,
        POOLED48_SCHEMA,
        POOLED48_STATUS,
        PHYSICAL_GPU_DOMAIN,
        PHYSICAL_GPU_MAPPING_POLICY,
        _absolute as _pooled_absolute,
        validate_physical_gpus,
        load_selected_candidates,
        validate_selected_candidates,
    )


STRATIFIED_SCHEMA = "a2_piper_v23_stratified_eval_receipt_v1"
STRATIFIED_STATUS = "V23_STRATIFIED_EVAL_COMPLETE"
STRATIFIED_JOB_SCHEMA = "a2_piper_v23_stratified_job_record_v1"
STRATIFIED_JOB_STATUS = "V23_STRATIFIED_JOB_COMPLETE"
STRATIFIED_PLAN_SCHEMA = "a2_piper_v23_stratified_plan_v1"
STRATIFIED_ROOT = REPO_ROOT / "logs_eval/base_v23/stratified/R7_F8_NULL_LEGACY_MODE"
STRATIFIED_RECEIPT_PATH = STRATIFIED_ROOT / "V23_STRATIFIED_EVAL.json"
STRATIFIED_PLAN_PATH = STRATIFIED_ROOT / "V23_STRATIFIED_EVAL_PLAN.json"

R190_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/p04_d1_physics_first_20260810/p04_d1_physics_first.json"
R190_SCHEMA = "a2_piper_v23_p04_d1_physics_first_v1"
R190_STATUS = "P0_4_D1_PHYSICS_FIRST_FREEZE_ADMITTED"
REALIZED_ATLAS_PATH = REPO_ROOT / "logs_eval/base_v23/p0/r26_p02_p04_p05_runtime_20260809/p04/door_external_torque_threshold.json"

ALLOWED_ZONES = ("E0", "E1", "near-E2")
EXPECTED_CELLS = {f"A{i}" for i in range(9)}
EXPECTED_LITE_CELLS = {"A0", "A1", "A4", "A5", "A6", "A8"}
REALIZED_FIELDS = (
    "door_weight_kg",
    "hinge_damping_native",
    "hinge_stiffness_native",
    "hinge_effort_limit_nm",
)
TRACE_FIELDS = {
    "door_weight_kg": "door_weight",
    "hinge_damping_native": "door_hinge_drive_damping_native",
    "hinge_stiffness_native": "door_hinge_drive_stiffness_native",
    "hinge_effort_limit_nm": "door_hinge_drive_max_force_nm",
}
MATCH_REL_TOL = 1e-6
MATCH_ABS_TOL = 1e-5


class StratifiedEvalError(V23Error):
    """A realized-dynamics stratification input is missing or inconsistent."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    return _pooled_absolute(path)


def _load_any(path: str | Path) -> Any:
    target = _absolute(path)
    if target.is_symlink() or not target.is_file():
        raise StratifiedEvalError(f"required stratified input is missing: {target}")
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StratifiedEvalError(f"stratified input is not valid JSON: {target}") from exc


def _load_object(path: str | Path) -> dict[str, Any]:
    value = _load_any(path)
    if not isinstance(value, dict):
        raise StratifiedEvalError(f"stratified input must be an object: {_absolute(path)}")
    return value


def _finite(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise StratifiedEvalError(f"{field} must be a finite number")
    return float(value)


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=MATCH_REL_TOL, abs_tol=MATCH_ABS_TOL)


def _load_r190(path: str | Path = R190_RECEIPT_PATH) -> dict[str, Any]:
    payload = _load_object(path)
    if payload.get("schema") != R190_SCHEMA or payload.get("status") != R190_STATUS:
        raise StratifiedEvalError(f"R190 physics-first receipt is not admitted: {_absolute(path)}")
    if payload.get("confirmed_E2") is not False:
        raise StratifiedEvalError("R190 confirmed_E2 must remain false for this stratifier")
    zones = payload.get("zones")
    if not isinstance(zones, Mapping):
        raise StratifiedEvalError("R190 receipt has no zone map")
    confirmed = zones.get("confirmed_E2")
    if confirmed != []:
        raise StratifiedEvalError("R190 confirmed_E2 zone must remain an empty held-out list")
    lite_excluded = zones.get("lite_not_in_curriculum")
    if not isinstance(lite_excluded, list) or len(set(lite_excluded)) != len(lite_excluded):
        raise StratifiedEvalError("R190 lite_not_in_curriculum must be a unique list")
    if set(lite_excluded) != {"A2", "A3", "A7"}:
        raise StratifiedEvalError("R190 lite_not_in_curriculum disagrees with the canonical sparse lite boundary")
    lite_admitted = EXPECTED_CELLS - set(lite_excluded)
    for variant in ("normal", "lite"):
        mapping = zones.get(variant)
        if not isinstance(mapping, Mapping):
            raise StratifiedEvalError(f"R190 zone map is missing {variant}")
        observed: list[str] = []
        for zone in (*ALLOWED_ZONES, "confirmed-E2"):
            cells = mapping.get(zone)
            if not isinstance(cells, list):
                raise StratifiedEvalError(f"R190 {variant} zone {zone} must be a list")
            if any(not isinstance(cell, str) or cell not in EXPECTED_CELLS for cell in cells):
                raise StratifiedEvalError(f"R190 {variant} zone {zone} contains an unknown cell")
            observed.extend(cells)
        if len(set(observed)) != len(observed):
            raise StratifiedEvalError(f"R190 {variant} zones assign a cell to multiple zones")
        observed_set = set(observed)
        if mapping["confirmed-E2"]:
            raise StratifiedEvalError(f"R190 {variant} contains confirmed-E2 cells")
        if variant == "normal" and observed_set != EXPECTED_CELLS:
            raise StratifiedEvalError("R190 normal zones must cover A0..A8 exactly")
        if variant == "lite" and observed_set != lite_admitted:
            raise StratifiedEvalError("R190 lite zones must cover the admitted lite cells exactly")
        if variant == "lite" and observed_set != EXPECTED_LITE_CELLS:
            raise StratifiedEvalError("R190 lite zones must be exactly A0/A1/A4/A5/A6/A8")
    return payload


def _zone_for_cell(mapping: Mapping[str, Any], cell: str, *, variant: str, env_id: int) -> str:
    matches = [zone for zone in ALLOWED_ZONES if cell in mapping[zone]]
    if len(matches) != 1:
        raise StratifiedEvalError(
            f"R190 {variant} zone assignment for atlas cell {cell} is not unique (env {env_id})"
        )
    return matches[0]


def _load_atlas(path: str | Path = REALIZED_ATLAS_PATH) -> dict[str, tuple[float, float, float, float]]:
    payload = _load_object(path)
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise StratifiedEvalError(f"realized dynamics atlas has no rows: {_absolute(path)}")
    result: dict[str, tuple[float, float, float, float]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise StratifiedEvalError(f"realized atlas row {index} is not an object")
        cell = row.get("cell_id")
        params = row.get("realized_params")
        if not isinstance(cell, str) or not cell or not isinstance(params, Mapping):
            raise StratifiedEvalError(f"realized atlas row {index} lacks cell_id/realized_params")
        values = tuple(_finite(params.get(field), field=f"atlas.{cell}.{field}") for field in REALIZED_FIELDS)
        previous = result.get(cell)
        if previous is not None and any(not _close(left, right) for left, right in zip(previous, values)):
            raise StratifiedEvalError(f"realized atlas has changing parameters for {cell}")
        result[cell] = values
    expected = {f"A{i}" for i in range(9)}
    if set(result) != expected:
        raise StratifiedEvalError("realized atlas must cover cells A0..A8 exactly")
    return result


def _episode_dynamics(trace_rows: Sequence[Mapping[str, Any]], *, env_id: int) -> tuple[float, float, float, float]:
    if not trace_rows:
        raise StratifiedEvalError(f"REALIZED_DYNAMICS_UNAVAILABLE: env {env_id} has no trace rows")
    observed: list[tuple[float, float, float, float]] = []
    for row_index, row in enumerate(trace_rows):
        values = tuple(
            _finite(row.get(TRACE_FIELDS[field]), field=f"trace.env{env_id}.row{row_index}.{TRACE_FIELDS[field]}")
            for field in REALIZED_FIELDS
        )
        observed.append(values)
    reference = observed[0]
    if any(any(not _close(left, right) for left, right in zip(reference, values)) for values in observed[1:]):
        raise StratifiedEvalError(f"REALIZED_DYNAMICS_NOT_CONSTANT: env {env_id}")
    return reference


def _match_cell(
    dynamics: tuple[float, float, float, float],
    atlas: Mapping[str, tuple[float, float, float, float]],
    *,
    env_id: int,
) -> str | None:
    matches = [
        cell
        for cell, expected in atlas.items()
        if all(_close(observed, reference) for observed, reference in zip(dynamics, expected))
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise StratifiedEvalError(f"REALIZED_DYNAMICS_AMBIGUOUS: env {env_id} matches {matches}")
    return matches[0]


def _validate_zone_counts(value: Any, *, field: str, expected_sum: int | None = None) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != set(ALLOWED_ZONES):
        raise StratifiedEvalError(f"{field} must contain exactly the zones {list(ALLOWED_ZONES)}")
    normalized: dict[str, int] = {}
    for zone in ALLOWED_ZONES:
        count = value[zone]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise StratifiedEvalError(f"{field}.{zone} must be a non-bool non-negative integer")
        normalized[zone] = count
    if expected_sum is not None and sum(normalized.values()) != expected_sum:
        raise StratifiedEvalError(f"{field} must sum to {expected_sum}")
    return normalized


def _validate_job_record_counts(
    record: Mapping[str, Any], *, path: str
) -> tuple[dict[str, int], dict[str, int], int, Counter[str]]:
    episodes = record.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != 48:
        raise StratifiedEvalError(f"stratified job episodes must contain exactly 48 rows: {path}")
    admitted = 0
    for index, episode in enumerate(episodes):
        if not isinstance(episode, Mapping):
            raise StratifiedEvalError(f"stratified episode row {index} is not an object: {path}")
        if set(episode) != {
            "env_id",
            "atlas_cell",
            "realized_dynamics",
            "normal_zone",
            "lite_zone",
            "lite_adjudication",
            "goal_reached",
            "classification_status",
        }:
            raise StratifiedEvalError(f"stratified episode row {index} key set is invalid: {path}")
        classification_status = episode.get("classification_status")
        if classification_status == "CLASSIFIED_EXACT_ATLAS_MATCH":
            if episode.get("atlas_cell") not in EXPECTED_CELLS:
                raise StratifiedEvalError(f"stratified episode row {index} classified atlas cell is invalid: {path}")
            if not isinstance(episode.get("realized_dynamics"), Mapping):
                raise StratifiedEvalError(f"stratified episode row {index} classified dynamics are missing: {path}")
            if episode.get("normal_zone") not in ALLOWED_ZONES:
                raise StratifiedEvalError(f"stratified episode row {index} classified normal zone is invalid: {path}")
        elif classification_status == "UNCLASSIFIED_NO_TRACE":
            if any(episode.get(field) is not None for field in ("atlas_cell", "realized_dynamics", "normal_zone", "lite_zone")):
                raise StratifiedEvalError(f"stratified episode row {index} no-trace fields must remain null: {path}")
        elif classification_status == "UNCLASSIFIED_NO_ATLAS_MATCH":
            if episode.get("atlas_cell") is not None or not isinstance(episode.get("realized_dynamics"), Mapping):
                raise StratifiedEvalError(f"stratified episode row {index} unmatched dynamics are malformed: {path}")
            if episode.get("normal_zone") is not None or episode.get("lite_zone") is not None:
                raise StratifiedEvalError(f"stratified episode row {index} unmatched zones must remain null: {path}")
        else:
            raise StratifiedEvalError(f"stratified episode row {index} classification status is invalid: {path}")
        if episode.get("lite_adjudication") == "ADMITTED":
            admitted += 1
        elif episode.get("lite_adjudication") not in {"EXCLUDED_FROM_LITE_CURRICULUM", "UNCLASSIFIED"}:
            raise StratifiedEvalError(f"stratified episode row {index} lite adjudication is invalid: {path}")
    classified = record.get("classified_episode_count")
    unclassified = record.get("unclassified_episode_count")
    if (
        isinstance(classified, bool)
        or not isinstance(classified, int)
        or isinstance(unclassified, bool)
        or not isinstance(unclassified, int)
        or classified < 0
        or unclassified < 0
        or classified + unclassified != 48
    ):
        raise StratifiedEvalError(f"stratified classified/unclassified counts are invalid: {path}")
    reasons_value = record.get("unclassified_reason_counts")
    if not isinstance(reasons_value, Mapping):
        raise StratifiedEvalError(f"stratified unclassified reason counts are missing: {path}")
    reasons: Counter[str] = Counter()
    for reason, count in reasons_value.items():
        if reason not in {"UNCLASSIFIED_NO_TRACE", "UNCLASSIFIED_NO_ATLAS_MATCH"} or isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise StratifiedEvalError(f"stratified unclassified reason count is invalid: {path}")
        reasons[reason] = count
    if sum(reasons.values()) != unclassified:
        raise StratifiedEvalError(f"stratified unclassified reason counts disagree: {path}")
    normal = _validate_zone_counts(
        record.get("normal_zone_counts"),
        field=f"{path}.normal_zone_counts",
        expected_sum=classified,
    )
    lite = _validate_zone_counts(record.get("lite_zone_counts"), field=f"{path}.lite_zone_counts", expected_sum=admitted)
    return normal, lite, classified, reasons


def classify_trace(
    records: Sequence[Mapping[str, Any]],
    trace: Sequence[Mapping[str, Any]],
    *,
    r190: Mapping[str, Any],
    atlas: Mapping[str, tuple[float, float, float, float]],
) -> dict[str, Any]:
    """Classify every pooled episode from its realized trace dynamics."""

    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or len(records) != 48:
        raise StratifiedEvalError("stratified pooled records must contain exactly 48 episodes")
    if not isinstance(trace, Sequence) or isinstance(trace, (str, bytes)) or not trace:
        raise StratifiedEvalError("stratified pooled trace must be a non-empty sequence")
    by_env: dict[int, list[Mapping[str, Any]]] = {env_id: [] for env_id in range(48)}
    for index, row in enumerate(trace):
        if not isinstance(row, Mapping):
            raise StratifiedEvalError(f"stratified trace row {index} is not an object")
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in by_env:
            raise StratifiedEvalError(f"stratified trace row {index} has invalid env_id")
        by_env[env_id].append(row)
    record_by_env: dict[int, Mapping[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise StratifiedEvalError(f"stratified episode row {index} is not an object")
        env_id = record.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in by_env or env_id in record_by_env:
            raise StratifiedEvalError(f"stratified episode row {index} has duplicate/invalid env_id")
        record_by_env[env_id] = record
    if set(record_by_env) != set(by_env):
        raise StratifiedEvalError("stratified episode records must cover env ids 0..47")
    zones = r190["zones"]
    episodes: list[dict[str, Any]] = []
    normal_counts: Counter[str] = Counter()
    lite_counts: Counter[str] = Counter()
    unclassified_counts: Counter[str] = Counter()
    for env_id in range(48):
        if not by_env[env_id]:
            status = "UNCLASSIFIED_NO_TRACE"
            unclassified_counts[status] += 1
            episodes.append(
                {
                    "env_id": env_id,
                    "atlas_cell": None,
                    "realized_dynamics": None,
                    "normal_zone": None,
                    "lite_zone": None,
                    "lite_adjudication": "UNCLASSIFIED",
                    "goal_reached": record_by_env[env_id].get("goal_reached"),
                    "classification_status": status,
                }
            )
            continue
        dynamics = _episode_dynamics(by_env[env_id], env_id=env_id)
        cell = _match_cell(dynamics, atlas, env_id=env_id)
        realized_dynamics = {
            field: dynamics[index] for index, field in enumerate(REALIZED_FIELDS)
        }
        if cell is None:
            status = "UNCLASSIFIED_NO_ATLAS_MATCH"
            unclassified_counts[status] += 1
            episodes.append(
                {
                    "env_id": env_id,
                    "atlas_cell": None,
                    "realized_dynamics": realized_dynamics,
                    "normal_zone": None,
                    "lite_zone": None,
                    "lite_adjudication": "UNCLASSIFIED",
                    "goal_reached": record_by_env[env_id].get("goal_reached"),
                    "classification_status": status,
                }
            )
            continue
        normal_zone = _zone_for_cell(zones["normal"], cell, variant="normal", env_id=env_id)
        lite_admitted = cell in {
            admitted_cell
            for zone in ALLOWED_ZONES
            for admitted_cell in zones["lite"][zone]
        }
        lite_zone = (
            _zone_for_cell(zones["lite"], cell, variant="lite", env_id=env_id)
            if lite_admitted
            else None
        )
        normal_counts[normal_zone] += 1
        if lite_zone is not None:
            lite_counts[lite_zone] += 1
        episodes.append(
            {
                "env_id": env_id,
                "atlas_cell": cell,
                "realized_dynamics": realized_dynamics,
                "normal_zone": normal_zone,
                "lite_zone": lite_zone,
                "lite_adjudication": "ADMITTED" if lite_zone is not None else "EXCLUDED_FROM_LITE_CURRICULUM",
                "goal_reached": record_by_env[env_id].get("goal_reached"),
                "classification_status": "CLASSIFIED_EXACT_ATLAS_MATCH",
            }
        )
    classified_count = len(episodes) - sum(unclassified_counts.values())
    normal_zone_counts = _validate_zone_counts(
        {zone: normal_counts[zone] for zone in ALLOWED_ZONES},
        field="normal_zone_counts",
        expected_sum=classified_count,
    )
    lite_admitted_count = sum(
        episode["lite_adjudication"] == "ADMITTED" for episode in episodes
    )
    lite_zone_counts = _validate_zone_counts(
        {zone: lite_counts[zone] for zone in ALLOWED_ZONES},
        field="lite_zone_counts",
        expected_sum=lite_admitted_count,
    )
    return {
        "episode_count": len(episodes),
        "classified_episode_count": classified_count,
        "unclassified_episode_count": sum(unclassified_counts.values()),
        "unclassified_reason_counts": dict(unclassified_counts),
        "episodes": episodes,
        "normal_zone_counts": normal_zone_counts,
        "lite_zone_counts": lite_zone_counts,
        "classification_source": "POOLED_TRACE_REALIZED_DYNAMICS_EXACT_R190_ATLAS_WITH_TYPED_UNCLASSIFIED",
        "confirmed_E2": False,
        "missing_evidence": ["realized_dynamics_unclassified"] if unclassified_counts else [],
    }


def _load_pooled_receipt(path: str | Path = POOLED48_RECEIPT_PATH) -> dict[str, Any]:
    payload = _load_object(path)
    if payload.get("schema") != POOLED48_SCHEMA or payload.get("status") != POOLED48_STATUS:
        raise StratifiedEvalError(f"pooled48 upstream receipt is not complete: {_absolute(path)}")
    if payload.get("topology") != "pooled48" or payload.get("job_count") != 16:
        raise StratifiedEvalError("pooled48 upstream topology/cardinality is invalid")
    if payload.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
        raise StratifiedEvalError("pooled48 upstream physical_gpu_domain is not exactly 0..7")
    physical_gpus = validate_physical_gpus(payload.get("physical_gpus"))
    if payload.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise StratifiedEvalError("pooled48 upstream physical GPU mapping policy is unsupported")
    selected = validate_selected_candidates(payload.get("selected_candidates"), require_sources=False)
    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != len(selected):
        raise StratifiedEvalError("pooled48 upstream jobs must contain exactly 16 entries")
    seen_ids: set[str] = set()
    for ordinal, (candidate, job) in enumerate(zip(selected, jobs)):
        if not isinstance(job, Mapping):
            raise StratifiedEvalError(f"pooled48 upstream job {ordinal} is not an object")
        expected_id = f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}"
        if job.get("job_id") != expected_id or job.get("job_ordinal") != ordinal:
            raise StratifiedEvalError(f"pooled48 upstream job {ordinal} identity/order disagrees")
        if job.get("selected_candidate") != candidate:
            raise StratifiedEvalError(f"pooled48 upstream job {expected_id} candidate disagrees")
        expected_gpu = physical_gpus[ordinal % len(physical_gpus)]
        if job.get("physical_gpu") != expected_gpu:
            raise StratifiedEvalError(f"pooled48 upstream job {expected_id} physical_gpu disagrees")
        if expected_id in seen_ids:
            raise StratifiedEvalError(f"pooled48 upstream duplicate job {expected_id}")
        seen_ids.add(expected_id)
    payload["selected_candidates"] = selected
    payload["physical_gpus"] = list(physical_gpus)
    return payload


def _job_record_path(candidate: Mapping[str, Any]) -> Path:
    return (
        STRATIFIED_ROOT
        / f"seed{candidate['seed']}"
        / str(candidate["cell"])
        / f"step{int(candidate['step']):04d}"
        / "stratified_record.json"
    )


def _classify_candidate(
    candidate: Mapping[str, Any],
    *,
    pooled_job: Mapping[str, Any],
    physical_gpus: Sequence[int],
    r190: Mapping[str, Any],
    atlas: Mapping[str, tuple[float, float, float, float]],
    r190_receipt_path: str | Path,
    realized_atlas_path: str | Path,
) -> dict[str, Any]:
    receipt_path = pooled_job.get("receipt_path", pooled_job.get("run_receipt_path"))
    if not isinstance(receipt_path, str) or not receipt_path:
        raise StratifiedEvalError(f"pooled48 upstream job has no receipt path: {candidate['cell']}")
    job_receipt = _load_object(receipt_path)
    if job_receipt.get("schema") != POOLED48_JOB_SCHEMA or job_receipt.get("status") != POOLED48_JOB_STATUS:
        raise StratifiedEvalError(f"pooled48 job receipt is incomplete: {receipt_path}")
    if job_receipt.get("selected_candidate") != dict(candidate):
        raise StratifiedEvalError(f"pooled48 job receipt identity disagrees: {receipt_path}")
    if job_receipt.get("physical_gpu") != pooled_job.get("physical_gpu") or job_receipt.get("logical_gpu") != "cuda:0":
        raise StratifiedEvalError(f"pooled48 job receipt GPU provenance disagrees: {receipt_path}")
    records = _load_any(job_receipt["records_path"])
    trace = _load_any(job_receipt["raw_trace_path"])
    if not isinstance(records, list) or not isinstance(trace, list):
        raise StratifiedEvalError(f"pooled48 raw evidence paths must contain lists: {candidate['cell']}")
    classified = classify_trace(records, trace, r190=r190, atlas=atlas)
    return {
        "schema": STRATIFIED_JOB_SCHEMA,
        "status": STRATIFIED_JOB_STATUS,
        "recorded_at_utc": _now(),
        "source_branch": candidate["source_branch"],
        "plan_id": candidate["plan_id"],
        "identity_policy": candidate["identity_policy"],
        "selected_candidate": dict(candidate),
        "topology": "pooled48",
        "physical_gpu": pooled_job["physical_gpu"],
        "logical_gpu": "cuda:0",
        "physical_gpus": list(physical_gpus),
        "pooled_job_receipt_path": str(_absolute(receipt_path)),
        "r190_receipt_path": str(_absolute(r190_receipt_path)),
        "realized_atlas_path": str(_absolute(realized_atlas_path)),
        **classified,
        "missing_evidence": list(classified["missing_evidence"]),
    }


def build_plan(
    *,
    pooled_receipt: str | Path = POOLED48_RECEIPT_PATH,
    r190_receipt: str | Path = R190_RECEIPT_PATH,
    realized_atlas: str | Path = REALIZED_ATLAS_PATH,
    physical_gpus: Sequence[int] | str | None = None,
    output: str | Path | None = None,
) -> dict[str, Any]:
    pooled = _load_pooled_receipt(pooled_receipt)
    _load_r190(r190_receipt)
    _load_atlas(realized_atlas)
    selected = pooled["selected_candidates"]
    pooled_gpus = validate_physical_gpus(pooled["physical_gpus"])
    selected_gpus = validate_physical_gpus(physical_gpus) if physical_gpus is not None else pooled_gpus
    if selected_gpus != pooled_gpus:
        raise StratifiedEvalError("stratified physical GPU mapping must match pooled48 provenance exactly")
    if len(selected) != 16:
        raise StratifiedEvalError("stratified plan requires exactly 16 selected candidates")
    jobs = [
        {
            "job_id": f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}",
            "job_ordinal": ordinal,
            "selected_candidate": dict(candidate),
            "physical_gpu": pooled["jobs"][ordinal]["physical_gpu"],
            "physical_gpus": list(selected_gpus),
            "pooled_job_receipt_path": str(_absolute(pooled["jobs"][ordinal]["receipt_path"])),
            "output_path": str(_job_record_path(candidate)),
            "runtime_mode": "POOLED_TRACE_REALIZED_DYNAMICS_REDUCE",
            "logical_gpu": "cuda:0",
            "no_retry": True,
        }
        for ordinal, candidate in enumerate(selected)
    ]
    payload = {
        "schema": STRATIFIED_PLAN_SCHEMA,
        "status": "BUILT",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "stage": "STRATIFIED_EVAL",
        "selected_candidates": selected,
        "selected_candidate_count": len(selected),
        "topology": "pooled48_posthoc_realized_dynamics",
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": list(selected_gpus),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "zones": list(ALLOWED_ZONES),
        "r190_receipt_path": str(_absolute(r190_receipt)),
        "realized_atlas_path": str(_absolute(realized_atlas)),
        "pooled_receipt_path": str(_absolute(pooled_receipt)),
        "jobs": jobs,
        "missing_evidence_policy": "TYPED_FAILURE_NO_ZERO_FILL",
    }
    if output is not None:
        write_json(_absolute(output), payload)
    return payload


def _assert_persisted_path(
    supplied: str | Path | None,
    persisted: str | Path,
    *,
    field: str,
) -> None:
    if supplied is not None and _absolute(supplied) != _absolute(persisted):
        raise StratifiedEvalError(
            f"stratified {field} disagrees with the persisted plan path: "
            f"{_absolute(supplied)} != {_absolute(persisted)}"
        )


def _load_plan(
    path: str | Path,
    *,
    pooled_receipt: str | Path | None = None,
    r190_receipt: str | Path | None = None,
    realized_atlas: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, tuple[float, float, float, float]]]:
    """Load one persisted stratification plan and all of its bound parents.

    RUN and REDUCE must consume the paths and GPU mapping recorded by BUILD;
    they never rebuild a manifest from live defaults.
    """

    manifest = _load_object(path)
    if manifest.get("schema") != STRATIFIED_PLAN_SCHEMA or manifest.get("status") != "BUILT":
        raise StratifiedEvalError("stratified manifest schema/status is not BUILT")
    if manifest.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
        raise StratifiedEvalError("stratified manifest physical_gpu_domain is not exactly 0..7")
    manifest_gpus = validate_physical_gpus(manifest.get("physical_gpus"))
    if manifest.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise StratifiedEvalError("stratified manifest physical GPU mapping policy is unsupported")
    persisted_pooled = manifest.get("pooled_receipt_path")
    persisted_r190 = manifest.get("r190_receipt_path")
    persisted_atlas = manifest.get("realized_atlas_path")
    for field, value in (
        ("pooled_receipt_path", persisted_pooled),
        ("r190_receipt_path", persisted_r190),
        ("realized_atlas_path", persisted_atlas),
    ):
        if not isinstance(value, str) or not value:
            raise StratifiedEvalError(f"stratified manifest {field} must be a persisted path")
    _assert_persisted_path(pooled_receipt, persisted_pooled, field="pooled_receipt")
    _assert_persisted_path(r190_receipt, persisted_r190, field="r190_receipt")
    _assert_persisted_path(realized_atlas, persisted_atlas, field="realized_atlas")
    pooled = _load_pooled_receipt(persisted_pooled)
    r190 = _load_r190(persisted_r190)
    atlas = _load_atlas(persisted_atlas)
    if manifest.get("selected_candidates") != pooled["selected_candidates"]:
        raise StratifiedEvalError("stratified manifest selected_candidates disagree with pooled provenance")
    if manifest_gpus != tuple(pooled["physical_gpus"]):
        raise StratifiedEvalError("stratified manifest GPU mapping disagrees with pooled provenance")
    selected = pooled["selected_candidates"]
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != len(selected) or len(selected) != 16:
        raise StratifiedEvalError("stratified manifest must contain exactly 16 jobs")
    for ordinal, (candidate, job, pooled_job) in enumerate(zip(selected, jobs, pooled["jobs"])):
        if not isinstance(job, Mapping):
            raise StratifiedEvalError(f"stratified manifest job {ordinal} must be an object")
        expected_id = f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}"
        if job.get("job_id") != expected_id or job.get("job_ordinal") != ordinal:
            raise StratifiedEvalError(f"stratified manifest job {ordinal} identity/order disagrees")
        if job.get("selected_candidate") != candidate:
            raise StratifiedEvalError(f"stratified manifest job {expected_id} candidate disagrees")
        if job.get("physical_gpu") != pooled_job.get("physical_gpu"):
            raise StratifiedEvalError(f"stratified manifest job {expected_id} physical_gpu disagrees")
        if job.get("physical_gpus") != list(manifest_gpus):
            raise StratifiedEvalError(f"stratified manifest job {expected_id} physical_gpus disagrees")
        if _absolute(job.get("pooled_job_receipt_path")) != _absolute(pooled_job.get("receipt_path")):
            raise StratifiedEvalError(f"stratified manifest job {expected_id} pooled receipt path disagrees")
        if not isinstance(job.get("output_path"), str) or not job["output_path"]:
            raise StratifiedEvalError(f"stratified manifest job {expected_id} lacks output_path")
    manifest["selected_candidates"] = selected
    manifest["physical_gpus"] = list(manifest_gpus)
    return manifest, pooled, r190, atlas


def run(
    *,
    pooled_receipt: str | Path | None = None,
    r190_receipt: str | Path | None = None,
    realized_atlas: str | Path | None = None,
    only_job: str | None = None,
    plan_path: str | Path | None = None,
) -> dict[str, Any]:
    if plan_path is None:
        raise StratifiedEvalError("RUN requires a persisted stratified plan path")
    manifest, pooled, r190, atlas = _load_plan(
        plan_path,
        pooled_receipt=pooled_receipt,
        r190_receipt=r190_receipt,
        realized_atlas=realized_atlas,
    )
    manifest_gpus = validate_physical_gpus(manifest["physical_gpus"])
    manifest_jobs = manifest["jobs"]
    jobs = []
    for ordinal, candidate in enumerate(pooled["selected_candidates"]):
        job_id = f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}"
        if only_job is not None and job_id != only_job:
            continue
        manifest_job = manifest_jobs[ordinal]
        if manifest_job.get("physical_gpu") != pooled["jobs"][ordinal]["physical_gpu"]:
            raise StratifiedEvalError(f"stratified manifest physical_gpu disagrees for {job_id}")
        output = _absolute(manifest_job["output_path"])
        if output.exists():
            raise StratifiedEvalError(f"stratified output exists; refusing overwrite: {output}")
        output.parent.mkdir(parents=True, exist_ok=False)
        record = _classify_candidate(
            candidate,
            pooled_job=pooled["jobs"][ordinal],
            physical_gpus=manifest_gpus,
            r190=r190,
            atlas=atlas,
            r190_receipt_path=manifest["r190_receipt_path"],
            realized_atlas_path=manifest["realized_atlas_path"],
        )
        write_json(output, record)
        jobs.append(job_id)
    if only_job is not None and not jobs:
        raise StratifiedEvalError(f"unknown stratified job: {only_job}")
    return {
        "schema": "a2_piper_v23_stratified_run_result_v1",
        "status": "PASS",
        "recorded_at_utc": _now(),
        "job_count": len(jobs),
        "completed_jobs": jobs,
        "runtime_mode": "POOLED_TRACE_REALIZED_DYNAMICS_REDUCE",
        "stratified_plan_path": str(_absolute(plan_path)),
        "pooled_receipt_path": manifest["pooled_receipt_path"],
        "r190_receipt_path": manifest["r190_receipt_path"],
        "realized_atlas_path": manifest["realized_atlas_path"],
        "no_retry": True,
    }


def reduce(
    *,
    pooled_receipt: str | Path | None = None,
    r190_receipt: str | Path | None = None,
    realized_atlas: str | Path | None = None,
    output: str | Path = STRATIFIED_RECEIPT_PATH,
    plan_path: str | Path | None = None,
) -> dict[str, Any]:
    if plan_path is None:
        raise StratifiedEvalError("REDUCE requires a persisted stratified plan path")
    manifest, pooled, _r190, _atlas = _load_plan(
        plan_path,
        pooled_receipt=pooled_receipt,
        r190_receipt=r190_receipt,
        realized_atlas=realized_atlas,
    )
    selected = validate_selected_candidates(pooled["selected_candidates"], require_sources=False)
    pooled_gpus = validate_physical_gpus(pooled["physical_gpus"])
    manifest_jobs = manifest["jobs"]
    if len(selected) != 16:
        raise StratifiedEvalError("stratified reduction requires exactly 16 selected candidates")
    jobs: list[dict[str, Any]] = []
    normal_counts: Counter[str] = Counter()
    lite_counts: Counter[str] = Counter()
    unclassified_counts: Counter[str] = Counter()
    classified_total = 0
    for ordinal, candidate in enumerate(selected):
        path = _absolute(manifest_jobs[ordinal]["output_path"])
        record = _load_object(path)
        if record.get("schema") != STRATIFIED_JOB_SCHEMA or record.get("status") != STRATIFIED_JOB_STATUS:
            raise StratifiedEvalError(f"stratified job record is incomplete: {path}")
        if record.get("selected_candidate") != dict(candidate):
            raise StratifiedEvalError(f"stratified job identity disagrees: {path}")
        if record.get("pooled_job_receipt_path") != manifest_jobs[ordinal]["pooled_job_receipt_path"]:
            raise StratifiedEvalError(f"stratified job pooled receipt path disagrees: {path}")
        if record.get("r190_receipt_path") != manifest["r190_receipt_path"]:
            raise StratifiedEvalError(f"stratified job R190 receipt path disagrees: {path}")
        if record.get("realized_atlas_path") != manifest["realized_atlas_path"]:
            raise StratifiedEvalError(f"stratified job realized atlas path disagrees: {path}")
        expected_gpu = pooled["jobs"][ordinal]["physical_gpu"]
        if record.get("physical_gpu") != expected_gpu or record.get("physical_gpus") != list(pooled_gpus):
            raise StratifiedEvalError(f"stratified job GPU provenance disagrees: {path}")
        if manifest_jobs[ordinal].get("physical_gpu") != expected_gpu:
            raise StratifiedEvalError(f"stratified manifest physical_gpu disagrees: {path}")
        if record.get("episode_count") != 48:
            raise StratifiedEvalError(f"stratified job episode cardinality is incomplete: {path}")
        # Re-validate the typed result shape without re-running the simulator.
        normal, lite, classified, reasons = _validate_job_record_counts(record, path=str(path))
        classified_total += classified
        unclassified_counts.update(reasons)
        for zone in ALLOWED_ZONES:
            normal_counts[zone] += normal[zone]
            lite_counts[zone] += lite[zone]
        jobs.append(
            {
                "job_id": f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}",
                "job_ordinal": ordinal,
                "selected_candidate": dict(candidate),
                "physical_gpu": record["physical_gpu"],
                "record_path": str(path),
                "episode_count": record["episode_count"],
                "classified_episode_count": record["classified_episode_count"],
                "unclassified_episode_count": record["unclassified_episode_count"],
                "unclassified_reason_counts": dict(record["unclassified_reason_counts"]),
                "normal_zone_counts": dict(record["normal_zone_counts"]),
                "lite_zone_counts": dict(record["lite_zone_counts"]),
                "missing_evidence": list(record["missing_evidence"]),
            }
        )
    if len(jobs) != 16:
        raise StratifiedEvalError("stratified reduction requires exactly 16 complete jobs")
    episode_total = len(jobs) * 48
    unclassified_total = sum(unclassified_counts.values())
    if classified_total + unclassified_total != episode_total:
        raise StratifiedEvalError("stratified classified/unclassified totals must equal 16 x 48 episodes")
    if sum(normal_counts.values()) != classified_total:
        raise StratifiedEvalError("stratified normal zone totals must equal the classified episode count")
    payload = {
        "schema": STRATIFIED_SCHEMA,
        "status": STRATIFIED_STATUS,
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "stage": "STRATIFIED_EVAL",
        "topology": "pooled48_posthoc_realized_dynamics",
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": list(pooled_gpus),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "logical_gpu": "cuda:0",
        "zones": list(ALLOWED_ZONES),
        "confirmed_E2": False,
        "selected_candidates": selected,
        "candidate_count": len(selected),
        "job_count": len(jobs),
        "episode_count": episode_total,
        "classified_episode_count": classified_total,
        "unclassified_episode_count": unclassified_total,
        "unclassified_reason_counts": dict(unclassified_counts),
        "normal_zone_counts": dict(normal_counts),
        "lite_zone_counts": dict(lite_counts),
        "r190_receipt_path": manifest["r190_receipt_path"],
        "realized_atlas_path": manifest["realized_atlas_path"],
        "pooled_receipt_path": manifest["pooled_receipt_path"],
        "stratified_plan_path": str(_absolute(plan_path)),
        "jobs": jobs,
        "missing_evidence": ["realized_dynamics_unclassified"] if unclassified_total else [],
        "no_retry": True,
    }
    write_json(_absolute(output), payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "BUILD", "RUN", "REDUCE"), required=True)
    parser.add_argument("--pooled48", type=Path, default=None)
    parser.add_argument("--r190", type=Path, default=None)
    parser.add_argument("--atlas", type=Path, default=None)
    parser.add_argument("--job", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--plan", type=Path, default=STRATIFIED_PLAN_PATH)
    parser.add_argument(
        "--physical-gpus",
        type=lambda value: validate_physical_gpus(value),
        default=None,
        help="ordered unique local physical GPU ids, subset of 0..7; PLAN/BUILD only",
    )
    args = parser.parse_args(argv)
    try:
        if args.mode not in {"PLAN", "BUILD"} and args.physical_gpus is not None:
            raise StratifiedEvalError("--physical-gpus is valid only for PLAN and BUILD")
        if args.mode in {"PLAN", "BUILD"}:
            payload = build_plan(
                pooled_receipt=args.pooled48 or POOLED48_RECEIPT_PATH,
                r190_receipt=args.r190 or R190_RECEIPT_PATH,
                realized_atlas=args.atlas or REALIZED_ATLAS_PATH,
                physical_gpus=args.physical_gpus,
                output=args.output if args.mode == "BUILD" else None,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            payload = run(
                pooled_receipt=args.pooled48,
                r190_receipt=args.r190,
                realized_atlas=args.atlas,
                only_job=args.job,
                plan_path=args.plan,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            payload = reduce(
                pooled_receipt=args.pooled48,
                r190_receipt=args.r190,
                realized_atlas=args.atlas,
                plan_path=args.plan,
                output=args.output or STRATIFIED_RECEIPT_PATH,
            )
            print(json.dumps({"status": "WRITTEN", "path": str(_absolute(args.output or STRATIFIED_RECEIPT_PATH))}, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 STRATIFIED_EVAL {args.mode} FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
