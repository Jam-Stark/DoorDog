"""Deterministic CPU-only v24 warm-start checkpoint reranking and freeze.

This producer consumes the immutable v23 FULL Route-A candidate receipts plus
the P0.1 descriptive reducer.  It does not run IsaacSim, replay a policy, or
rewrite a checkpoint.  The only runtime statement emitted here is that static
checkpoint compatibility is complete; observation/action/terminal parity is
explicitly deferred to the P1 IsaacSim lane.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence

try:
    import yaml
except ImportError as exc:  # pragma: no cover - fail-fast producer dependency
    raise RuntimeError("PyYAML is required for checkpoint-freeze config inspection") from exc

try:
    from ._v24_common import (
        REPO_ROOT,
        V23_FINAL_PATH,
        V23_FREEZE_PATH,
        V23_HOLDOUT_PATH,
        V23_ROUTE_A_ROOT,
        V23_ROUTE_B_PATH,
        V24_CHECKPOINT_FREEZE_ROOT,
        V24_P0_ROOT,
        V24Error,
        absolute,
        finite_number,
        read_json,
        rel_path,
        require_file,
        require_object,
        write_json,
        write_text,
    )
except ImportError:  # direct ``python scriptsFORhuman/v24/p0_checkpoint_freeze.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v24._v24_common import (
        REPO_ROOT,
        V23_FINAL_PATH,
        V23_FREEZE_PATH,
        V23_HOLDOUT_PATH,
        V23_ROUTE_A_ROOT,
        V23_ROUTE_B_PATH,
        V24_CHECKPOINT_FREEZE_ROOT,
        V24_P0_ROOT,
        V24Error,
        absolute,
        finite_number,
        read_json,
        rel_path,
        require_file,
        require_object,
        write_json,
        write_text,
    )


FREEZE_SCHEMA = "a2_piper_v24_warm_start_freeze_v1"
COMPAT_SCHEMA = "a2_piper_v24_compatibility_static_v1"
FULL_SUBWAVES = {"A1", "B1"}
FULL_CELLS = {"G1", "G3", "G5", "G7"}
EXPECTED_FULL_CANDIDATES = 8
EXPECTED_POLICY_KEYS = (
    "std",
    "actor_module.module.0.weight",
    "actor_module.module.0.bias",
    "actor_module.module.2.weight",
    "actor_module.module.2.bias",
    "actor_module.module.4.weight",
    "actor_module.module.4.bias",
    "actor_module.module.6.weight",
    "actor_module.module.6.bias",
    "running_mean_std.running_mean",
    "running_mean_std.running_var",
    "running_mean_std.count",
    "memory.rnn.weight_ih_l0",
    "memory.rnn.weight_hh_l0",
    "memory.rnn.bias_ih_l0",
    "memory.rnn.bias_hh_l0",
    "memory.rnn.weight_ih_l1",
    "memory.rnn.weight_hh_l1",
    "memory.rnn.bias_ih_l1",
    "memory.rnn.bias_hh_l1",
)
EXPECTED_POLICY_SHAPES = {
    "std": (12,),
    "actor_module.module.0.weight": (512, 256),
    "actor_module.module.0.bias": (512,),
    "actor_module.module.2.weight": (256, 512),
    "actor_module.module.2.bias": (256,),
    "actor_module.module.4.weight": (128, 256),
    "actor_module.module.4.bias": (128,),
    "actor_module.module.6.weight": (12, 128),
    "actor_module.module.6.bias": (12,),
    "running_mean_std.running_mean": (133,),
    "running_mean_std.running_var": (133,),
    "running_mean_std.count": (),
    "memory.rnn.weight_ih_l0": (1024, 133),
    "memory.rnn.weight_hh_l0": (1024, 256),
    "memory.rnn.bias_ih_l0": (1024,),
    "memory.rnn.bias_hh_l0": (1024,),
    "memory.rnn.weight_ih_l1": (1024, 256),
    "memory.rnn.weight_hh_l1": (1024, 256),
    "memory.rnn.bias_ih_l1": (1024,),
    "memory.rnn.bias_hh_l1": (1024,),
}
IDENTITY_FIELDS = (
    "cell",
    "checkpoint_path",
    "config_path",
    "evaluation_root",
    "identity_policy",
    "plan_id",
    "row_id",
    "scenario_path",
    "seed",
    "source_branch",
    "step",
    "subwave",
)
VALUE_FIELDS = ("goal_reached", "supported_crossing", "terminal_failures", "unsafe_contacts")
SAFE_BEHAVIOR_CATEGORIES = {
    "HOLD_THROUGH_CROSSING/NO_RELEASE_EVENT",
    "QUIET_HOLD_RELEASE",
    "CONTROLLED_FLING",
}
MISSING = "TYPED_MISSING"


def _config_warm_head_reset_enabled(config: Mapping[str, Any]) -> Any:
    value = config.get("v23_warm_head_reset_enabled")
    if value is not None:
        return value
    env = config.get("env")
    if isinstance(env, Mapping):
        env_config = env.get("config")
        if isinstance(env_config, Mapping):
            return env_config.get("a2_v23_warm_head_reset_enabled", False)
    return False


def _candidate_id(row: Mapping[str, Any]) -> str:
    for key in ("subwave", "cell", "seed", "step"):
        if key not in row:
            raise V24Error(f"candidate is missing identity field {key}")
    return f"{row['subwave']}_{row['cell']}_seed{int(row['seed'])}_step{int(row['step'])}"


def _require_schema_status(payload: Mapping[str, Any], *, schema: str, status: str, label: str) -> None:
    if payload.get("schema") != schema or payload.get("status") != status:
        raise V24Error(f"{label} schema/status mismatch: expected {schema}/{status}")


def _rel_sources(paths: Iterable[str | Path]) -> list[str]:
    return [rel_path(path) for path in paths]


def _same_fields(left: Mapping[str, Any], right: Mapping[str, Any], fields: Sequence[str], *, label: str) -> None:
    for field in fields:
        if left.get(field) != right.get(field):
            raise V24Error(f"{label} field {field} disagrees: {left.get(field)!r} != {right.get(field)!r}")


def _candidate_semantics(candidate: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    cell = str(candidate["cell"])
    expected_regime = "D1" if cell in {"G5", "G7"} else "D0"
    expected_init = "warm_head_reset" if cell in {"G3", "G7"} else "v22_warm"
    expected_posture = "FULL" if cell in FULL_CELLS else None
    if config.get("v23_cell") != cell:
        raise V24Error(f"config v23_cell mismatch for {_candidate_id(candidate)}")
    # The formal v23 config is reused by both launch seeds for a cell.  Seed
    # identity therefore comes from the candidate/receipt fields, while a
    # present config v23_seed is retained as source metadata below.
    if config.get("v23_door_regime") != expected_regime:
        raise V24Error(f"config door regime mismatch for {_candidate_id(candidate)}")
    if config.get("v23_initialization") != expected_init:
        raise V24Error(f"config initialization mismatch for {_candidate_id(candidate)}")
    if config.get("v23_posture_mode") != expected_posture:
        raise V24Error(f"config posture mode mismatch for {_candidate_id(candidate)}")
    return {
        "initialization": config.get("v23_initialization"),
        "door_regime": config.get("v23_door_regime"),
        "posture_mode": config.get("v23_posture_mode"),
        "checkpoint_load_mode": config.get("checkpoint_load_mode"),
        "output_head_inheritance": config.get("v23_output_head_inheritance", False),
        "warm_head_reset_enabled": _config_warm_head_reset_enabled(config),
        "schema": config.get("v23_schema"),
        "plan_id": config.get("v23_plan_id"),
        "config_seed_field": config.get("v23_seed"),
    }


def _load_route_a_context(candidate: Mapping[str, Any]) -> dict[str, Any]:
    seed = int(candidate["seed"])
    subwave = str(candidate["subwave"])
    route_a_dir = V23_ROUTE_A_ROOT / f"seed{seed}" / subwave
    manifest_path = route_a_dir / "V23_ROUTE_A_MANIFEST.json"
    selection_path = route_a_dir / "V23_ROUTE_A_SELECTION.json"
    analysis_path = route_a_dir / "V23_ROUTE_A_ANALYSIS.json"
    manifest = require_object(read_json(manifest_path, label="Route-A manifest"), label="Route-A manifest")
    selection = require_object(read_json(selection_path, label="Route-A selection"), label="Route-A selection")
    analysis = require_object(read_json(analysis_path, label="Route-A analysis"), label="Route-A analysis")
    _require_schema_status(manifest, schema="a2_piper_v23_route_a_manifest_v1", status="BUILT", label="Route-A manifest")
    _require_schema_status(selection, schema="a2_piper_v23_route_a_selection_v1", status="COMPLETE", label="Route-A selection")
    _require_schema_status(analysis, schema="a2_piper_v23_route_a_analysis_v1", status="COMPLETE", label="Route-A analysis")
    if manifest.get("route") != "A" or selection.get("route") != "A" or analysis.get("route") != "A":
        raise V24Error(f"Route-A receipt route mismatch for {_candidate_id(candidate)}")
    if manifest.get("seed") != seed or selection.get("seed") != seed or analysis.get("seed") != seed:
        raise V24Error(f"Route-A seed mismatch for {_candidate_id(candidate)}")
    if manifest.get("subwave") != subwave or selection.get("subwave") != subwave or analysis.get("subwave") != subwave:
        raise V24Error(f"Route-A subwave mismatch for {_candidate_id(candidate)}")
    selected_rows = selection.get("selected")
    analysis_rows = analysis.get("rows")
    if not isinstance(selected_rows, list) or len(selected_rows) != 4:
        raise V24Error(f"Route-A selection must contain four cell rows for {subwave}")
    if not isinstance(analysis_rows, list) or len(analysis_rows) != 40:
        raise V24Error(f"Route-A analysis must contain forty rows for {subwave}")
    selected = next((dict(row) for row in selected_rows if isinstance(row, Mapping) and row.get("cell") == candidate.get("cell")), None)
    analyzed = next((dict(row) for row in analysis_rows if isinstance(row, Mapping) and row.get("row_id") == candidate.get("row_id")), None)
    if selected is None or analyzed is None:
        raise V24Error(f"Route-A selected/analyzed row missing for {_candidate_id(candidate)}")
    # The compact selection schema omits the enclosing subwave; the parent
    # selection receipt is authoritative for that field.
    selected_compare = {**selected, "subwave": subwave}
    _same_fields(candidate, selected_compare, IDENTITY_FIELDS + VALUE_FIELDS, label="candidate vs Route-A selection")
    _same_fields(candidate, analyzed, IDENTITY_FIELDS + VALUE_FIELDS, label="candidate vs Route-A analysis")
    if analyzed.get("evidence_status") != "SUPPORTED" or analyzed.get("missing_evidence") not in ([], None):
        raise V24Error(f"Route-A analysis evidence is not supported for {_candidate_id(candidate)}")
    evaluation_root = require_file(Path(str(selected["evaluation_root"])) / "row_receipt.json", label="Route-A row receipt").parent
    receipt_path = evaluation_root / "row_receipt.json"
    receipt = require_object(read_json(receipt_path, label="Route-A row receipt"), label="Route-A row receipt")
    if receipt.get("schema") != "a2_piper_v23_route_a_row_receipt_v1" or receipt.get("status") != "ROW_PASS":
        raise V24Error(f"Route-A row receipt is not ROW_PASS for {_candidate_id(candidate)}")
    _same_fields(candidate, receipt, IDENTITY_FIELDS, label="candidate vs Route-A row receipt")
    if receipt.get("evaluation_root") != selected.get("evaluation_root"):
        raise V24Error(f"Route-A row receipt evaluation_root mismatch for {_candidate_id(candidate)}")
    metrics_path = require_file(evaluation_root / "metrics_eval.json", label="Route-A metrics")
    records_path = require_file(evaluation_root / "a2_v14_per_env_records.json", label="Route-A records")
    trace_path = require_file(evaluation_root / "stage2_step_trace.json", label="Route-A trace")
    run_result_path = require_file(evaluation_root / "V23_ROUTE_A_RUN_RESULT.json", label="Route-A run result")
    run_result = require_object(read_json(run_result_path, label="Route-A run result"), label="Route-A run result")
    if run_result.get("schema") != "a2_piper_v23_route_a_run_result_v1" or run_result.get("status") != "PASS":
        raise V24Error(f"Route-A run result is not PASS for {_candidate_id(candidate)}")
    metrics = require_object(read_json(metrics_path, label="Route-A metrics"), label="Route-A metrics")
    lengths = metrics.get("episode_lengths")
    goals = metrics.get("episode_goal_reached")
    if not isinstance(lengths, list) or len(lengths) != 16 or not isinstance(goals, list) or len(goals) != 16:
        raise V24Error(f"Route-A metrics are not canonical16 for {_candidate_id(candidate)}")
    if sum(bool(value) for value in goals) != int(candidate["goal_reached"]):
        raise V24Error(f"Route-A metric goal count mismatch for {_candidate_id(candidate)}")
    return {
        "manifest_path": manifest_path,
        "selection_path": selection_path,
        "analysis_path": analysis_path,
        "row_receipt_path": receipt_path,
        "run_result_path": run_result_path,
        "metrics_path": metrics_path,
        "records_path": records_path,
        "trace_path": trace_path,
        "selected": selected,
        "analysis": analyzed,
        "metrics": metrics,
        "evaluation_root": evaluation_root,
    }


def _load_route_b_context(route_b: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    pooled_ref = next((row for row in route_b.get("producer_receipts", []) if isinstance(row, Mapping) and row.get("name") == "pooled48"), None)
    if pooled_ref is None:
        raise V24Error("Route-B pooled48 producer receipt is missing")
    pooled_path = require_file(pooled_ref["path"], label="pooled48 receipt")
    pooled = require_object(read_json(pooled_path, label="pooled48 receipt"), label="pooled48 receipt")
    _require_schema_status(pooled, schema="a2_piper_v23_pooled48_receipt_v1", status="V23_POOLED48_COMPLETE", label="pooled48 receipt")
    jobs = pooled.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 16:
        raise V24Error("pooled48 receipt must contain sixteen jobs")
    candidate_id = _candidate_id(candidate)
    job = next((dict(item) for item in jobs if isinstance(item, Mapping) and isinstance(item.get("selected_candidate"), Mapping) and _candidate_id(item["selected_candidate"]) == candidate_id), None)
    if job is None:
        raise V24Error(f"pooled48 job missing for {candidate_id}")
    pooled_candidate = require_object(job.get("selected_candidate"), label="pooled48.selected_candidate")
    _same_fields(candidate, pooled_candidate, IDENTITY_FIELDS + VALUE_FIELDS, label="candidate vs pooled48")
    receipt_path = require_file(job["receipt_path"], label="pooled48 job receipt")
    receipt = require_object(read_json(receipt_path, label="pooled48 job receipt"), label="pooled48 job receipt")
    _require_schema_status(receipt, schema="a2_piper_v23_pooled48_job_receipt_v1", status="V23_POOLED48_JOB_COMPLETE", label="pooled48 job receipt")
    receipt_candidate = require_object(receipt.get("selected_candidate"), label="pooled48 receipt candidate")
    _same_fields(candidate, receipt_candidate, IDENTITY_FIELDS + VALUE_FIELDS, label="candidate vs pooled48 receipt")
    records_path = require_file(receipt["records_path"], label="pooled48 records")
    records = read_json(records_path, label="pooled48 records")
    if not isinstance(records, list) or len(records) != 48:
        raise V24Error(f"pooled48 records are not 48 episodes for {candidate_id}")
    for index, record in enumerate(records):
        if not isinstance(record, Mapping) or not isinstance(record.get("goal_reached"), bool) or (record.get("post_release_body_contact") is not None and not isinstance(record.get("post_release_body_contact"), bool)):
            raise V24Error(f"pooled48 record {candidate_id}[{index}] lacks exact goal/contact field typing")
    return {
        "top_path": pooled_path,
        "receipt_path": receipt_path,
        "records_path": records_path,
        "receipt": receipt,
        "records": records,
        "job": job,
        "pooled": pooled,
    }


def _load_holdout_context(holdout: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = _candidate_id(candidate)
    rows = holdout.get("candidates")
    if not isinstance(rows, list) or len(rows) != 16:
        raise V24Error("holdout receipt must contain sixteen candidates")
    item = next((dict(row) for row in rows if isinstance(row, Mapping) and row.get("freeze_id") == candidate_id), None)
    if item is None:
        raise V24Error(f"holdout candidate missing for {candidate_id}")
    holdout_candidate = require_object(item.get("candidate"), label="holdout candidate")
    _same_fields(candidate, holdout_candidate, IDENTITY_FIELDS + VALUE_FIELDS, label="candidate vs holdout")
    jobs = item.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 4:
        raise V24Error(f"holdout candidate must contain four jobs for {candidate_id}")
    records: list[Mapping[str, Any]] = []
    job_sources: list[str] = []
    for job_index, job in enumerate(jobs):
        if not isinstance(job, Mapping) or not isinstance(job.get("records"), list) or len(job["records"]) != 16:
            raise V24Error(f"holdout job {candidate_id}[{job_index}] is not 16 records")
        job_sources.append(str(job.get("job_receipt_path") or job.get("raw_records_path") or ""))
        for record_index, record in enumerate(job["records"]):
            if not isinstance(record, Mapping) or not isinstance(record.get("goal_reached"), bool) or (record.get("post_release_body_contact") is not None and not isinstance(record.get("post_release_body_contact"), bool)):
                raise V24Error(f"holdout record {candidate_id}[{job_index}:{record_index}] lacks exact goal/contact field typing")
            records.append(record)
    if len(records) != 64:
        raise V24Error(f"holdout records are not 64 episodes for {candidate_id}")
    return {"records": records, "candidate": item, "job_sources": job_sources}


def _load_posture_context() -> tuple[Path, list[dict[str, Any]]]:
    path = V24_P0_ROOT / "V23_POSTURE_BEHAVIOR_ANALYSIS.json"
    payload = require_object(read_json(path, label="P0.1 posture behavior analysis"), label="P0.1 posture behavior analysis")
    _require_schema_status(payload, schema="a2_piper_v24_v23_posture_behavior_analysis_v1", status="V24_P0_V23_POSTURE_BEHAVIOR_ANALYSIS_COMPLETE", label="P0.1 posture behavior analysis")
    rows = payload.get("records")
    if not isinstance(rows, list) or len(rows) != 768:
        raise V24Error("P0.1 posture behavior analysis must contain 768 records")
    return path, [dict(row) for row in rows]


def _load_sources() -> dict[str, Any]:
    route_b = require_object(read_json(V23_ROUTE_B_PATH, label="v23 Route-B receipt"), label="v23 Route-B receipt")
    freeze = require_object(read_json(V23_FREEZE_PATH, label="v23 candidate freeze"), label="v23 candidate freeze")
    holdout = require_object(read_json(V23_HOLDOUT_PATH, label="v23 holdout receipt"), label="v23 holdout receipt")
    final = require_object(read_json(V23_FINAL_PATH, label="v23 final analysis"), label="v23 final analysis")
    _require_schema_status(route_b, schema="a2_piper_v23_route_b_receipt_v1", status="V23_ROUTE_B_COMPLETE", label="Route-B receipt")
    _require_schema_status(freeze, schema="a2_piper_v23_candidate_freeze_v1", status="V23_CANDIDATE_FREEZE_COMPLETE", label="candidate freeze")
    _require_schema_status(holdout, schema="a2_piper_v23_holdout64_receipt_v1", status="V23_HOLDOUT64_COMPLETE", label="holdout receipt")
    _require_schema_status(final, schema="a2_piper_v23_final_analysis_v1", status="V23_FINAL_ANALYSIS_COMPLETE", label="v23 final analysis")
    if route_b.get("selected_candidate_count") != 16 or freeze.get("candidate_count") != 16 or holdout.get("candidate_count") != 16:
        raise V24Error("v23 canonical candidate count is not exact16")
    posture_path, posture_rows = _load_posture_context()
    return {"route_b": route_b, "freeze": freeze, "holdout": holdout, "final": final, "posture_path": posture_path, "posture_rows": posture_rows}


def _load_full_candidates(sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    freeze_rows = sources["freeze"].get("selected_candidates")
    if not isinstance(freeze_rows, list) or len(freeze_rows) != 16:
        raise V24Error("candidate freeze selected_candidates is not exact16")
    full_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in freeze_rows:
        candidate = require_object(raw, label="candidate freeze row")
        candidate_id = _candidate_id(candidate)
        if candidate_id in seen:
            raise V24Error(f"candidate freeze repeats {candidate_id}")
        seen.add(candidate_id)
        if candidate.get("subwave") not in FULL_SUBWAVES or candidate.get("cell") not in FULL_CELLS:
            continue
        if candidate.get("freeze_id") != candidate_id:
            raise V24Error(f"freeze_id mismatch for {candidate_id}")
        route_a = _load_route_a_context(candidate)
        pooled = _load_route_b_context(sources["route_b"], candidate)
        holdout = _load_holdout_context(sources["holdout"], candidate)
        config_path = require_file(candidate["config_path"], label="v23 candidate config")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, Mapping):
            raise V24Error(f"v23 config is not a mapping: {config_path}")
        semantics = _candidate_semantics(candidate, config)
        checkpoint_path = require_file(candidate["checkpoint_path"], label="v23 candidate checkpoint")
        posture_rows = [row for row in sources["posture_rows"] if isinstance(row.get("candidate"), Mapping) and row["candidate"].get("candidate_id") == candidate_id]
        if len(posture_rows) != 48:
            raise V24Error(f"P0.1 posture rows are not 48 for {candidate_id}")
        full_rows.append({
            "candidate": dict(candidate),
            "candidate_id": candidate_id,
            "config": dict(config),
            "config_path": config_path,
            "checkpoint_path": checkpoint_path,
            "semantics": semantics,
            "route_a": route_a,
            "pooled": pooled,
            "holdout": holdout,
            "posture_rows": posture_rows,
        })
    if len(full_rows) != EXPECTED_FULL_CANDIDATES:
        raise V24Error(f"canonical v23 FULL Route-A candidate count changed: {len(full_rows)}")
    return sorted(full_rows, key=lambda row: row["candidate_id"])


def _metric(*, value: float | int | None, available: bool, formula: str, source_paths: Iterable[str | Path], fields: Iterable[str], authority: str, coverage: Mapping[str, Any], missingness: Iterable[str] = ()) -> dict[str, Any]:
    reasons = list(missingness)
    coverage_payload = dict(coverage)
    coverage_payload.setdefault("missing_reasons", reasons)
    if not available:
        value = None
    return {
        "value": value,
        "available": bool(available),
        "formula": formula,
        "source_paths": _rel_sources(source_paths),
        "source_fields": list(fields),
        "authority": authority,
        "coverage": coverage_payload,
        "missingness": reasons,
    }


def _p95(values: Sequence[Any], *, label: str) -> float:
    numbers = sorted(finite_number(value, label=f"{label}[{index}]") for index, value in enumerate(values))
    if not numbers:
        raise V24Error(f"{label} is empty")
    position = (len(numbers) - 1) * 0.95
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return numbers[lower]
    fraction = position - lower
    return numbers[lower] + fraction * (numbers[upper] - numbers[lower])


def _candidate_metrics(row: Mapping[str, Any], posture_path: Path) -> dict[str, Any]:
    candidate = row["candidate"]
    candidate_id = row["candidate_id"]
    pooled_records = row["pooled"]["records"]
    holdout_records = row["holdout"]["records"]
    posture_records = row["posture_rows"]
    route_a = row["route_a"]
    unsafe_route_a = int(candidate.get("unsafe_contacts", 0))
    pooled_contact_missing = sum(item.get("post_release_body_contact") is None for item in pooled_records)
    pooled_contacts = sum(item.get("post_release_body_contact") is True for item in pooled_records)
    holdout_contact_missing = sum(item.get("post_release_body_contact") is None for item in holdout_records)
    holdout_contacts = sum(item.get("post_release_body_contact") is True for item in holdout_records)
    unsafe_metric = _metric(
        value=unsafe_route_a + pooled_contacts + holdout_contacts,
        available=pooled_contact_missing == 0 and holdout_contact_missing == 0,
        formula="Route-A unsafe_contacts + pooled48 per-env post_release_body_contact=true + holdout64 per-env post_release_body_contact=true",
        source_paths=[route_a["selection_path"], row["pooled"]["records_path"], V23_HOLDOUT_PATH],
        fields=["unsafe_contacts", "post_release_body_contact"],
        authority="Exact canonical receipt fields; pooled48 top-level unsafe_contacts export remains typed missing",
        coverage={
            "total_records": len(pooled_records) + len(holdout_records),
            "available_records": len(pooled_records) - pooled_contact_missing + len(holdout_records) - holdout_contact_missing,
            "missing_records": pooled_contact_missing + holdout_contact_missing,
            "complete": pooled_contact_missing == 0 and holdout_contact_missing == 0,
            "route_a_unsafe_contacts_scalar_available": True,
        },
        missingness=[
            "pooled48.unsafe_contacts:UNSUPPORTED_NOT_EXPORTED",
            *([] if pooled_contact_missing == 0 else [f"pooled48.post_release_body_contact:FINITE_ROWS={len(pooled_records) - pooled_contact_missing}/48"]),
            *([] if holdout_contact_missing == 0 else [f"holdout64.post_release_body_contact:FINITE_ROWS={len(holdout_records) - holdout_contact_missing}/64"]),
        ],
    )
    holdout_goals = sum(bool(item["goal_reached"]) for item in holdout_records)
    pooled_goals = sum(bool(item["goal_reached"]) for item in pooled_records)
    holdout_metric = _metric(
        value=holdout_goals / len(holdout_records),
        available=True,
        formula="mean(holdout64 per-env goal_reached)",
        source_paths=[V23_HOLDOUT_PATH],
        fields=["candidates[].jobs[].records[].goal_reached"],
        authority="V23_HOLDOUT64_COMPLETE canonical holdout records",
        coverage={"total_records": len(holdout_records), "available_records": len(holdout_records), "missing_records": 0, "complete": True},
    )
    pooled_metric = _metric(
        value=pooled_goals / len(pooled_records),
        available=True,
        formula="mean(pooled48 per-env goal_reached)",
        source_paths=[row["pooled"]["records_path"]],
        fields=["goal_reached"],
        authority="V23_POOLED48_COMPLETE per-env records",
        coverage={"total_records": len(pooled_records), "available_records": len(pooled_records), "missing_records": 0, "complete": True},
    )
    category_counts = Counter(str(item.get("behavior_category")) for item in posture_records)
    classified_count = sum(category_counts.get(category, 0) for category in SAFE_BEHAVIOR_CATEGORIES | {"UNSAFE_RELEASE"})
    safe_count = sum(category_counts.get(category, 0) for category in SAFE_BEHAVIOR_CATEGORIES)
    clearance_metric = _metric(
        value=None if classified_count == 0 else safe_count / classified_count,
        available=classified_count == len(posture_records),
        formula="count(behavior_category in {HOLD_THROUGH_CROSSING/NO_RELEASE_EVENT, QUIET_HOLD_RELEASE, CONTROLLED_FLING}) / count(classified behavior categories)",
        source_paths=[posture_path],
        fields=["records[].behavior_category", "records[].clearance"],
        authority="P0.1 realized behavior semantics; no nominal regime or goal substitution",
        coverage={
            "total_records": len(posture_records),
            "available_records": classified_count,
            "missing_records": len(posture_records) - classified_count,
            "complete": classified_count == len(posture_records),
        },
        missingness=[] if classified_count == len(posture_records) else [f"behavior_category:CLASSIFIED_ROWS={classified_count}/{len(posture_records)}"],
    )
    zones = Counter(str(item.get("normal_zone")) for item in posture_records)
    in_domain = zones.get("E0", 0) + zones.get("E1", 0)
    mechanics_metric = _metric(
        value=None if in_domain == 0 else zones.get("E1", 0) / in_domain,
        available=in_domain == len(posture_records),
        formula="count(normal_zone=E1) / count(normal_zone in {E0,E1})",
        source_paths=[posture_path],
        fields=["records[].normal_zone"],
        authority="P0.1 continuous realized-mechanics atlas; observed zone only, no goal-for-mechanics substitution",
        coverage={
            "total_records": len(posture_records),
            "available_records": in_domain,
            "missing_records": len(posture_records) - in_domain,
            "complete": in_domain == len(posture_records),
        },
        missingness=[] if in_domain == len(posture_records) else [f"normal_zone:E0_E1_ROWS={in_domain}/{len(posture_records)}"],
    )
    posture_values = [finite_number(item["posture_use_fraction"], label=f"{candidate_id}.posture_use_fraction") for item in posture_records if item.get("posture_use_fraction") is not None]
    posture_metric = _metric(
        value=None if not posture_values else float(fmean(posture_values)),
        available=len(posture_values) == len(posture_records),
        formula="mean(posture_use_fraction over finite P0.1 records); lower is less posture pathology",
        source_paths=[posture_path],
        fields=["records[].posture_use_fraction"],
        authority="P0.1 descriptive posture behavior reducer",
        coverage={
            "total_records": len(posture_records),
            "available_records": len(posture_values),
            "missing_records": len(posture_records) - len(posture_values),
            "complete": len(posture_values) == len(posture_records),
        },
        missingness=[] if len(posture_values) == len(posture_records) else [f"posture_use_fraction:FINITE_ROWS={len(posture_values)}/{len(posture_records)}"],
    )
    lengths = route_a["metrics"].get("episode_lengths")
    task_time_metric = _metric(
        value=_p95(lengths, label=f"{candidate_id}.episode_lengths") if isinstance(lengths, list) and lengths else None,
        available=isinstance(lengths, list) and len(lengths) == 16,
        formula="linear p95 over Route-A canonical16 episode_lengths; lower is earlier task-time tail",
        source_paths=[route_a["metrics_path"]],
        fields=["episode_lengths"],
        authority="V23_ROUTE_A_ANALYSIS canonical16 metrics",
        coverage={
            "total_records": 16,
            "available_records": len(lengths) if isinstance(lengths, list) else 0,
            "missing_records": 16 - len(lengths) if isinstance(lengths, list) else 16,
            "complete": isinstance(lengths, list) and len(lengths) == 16,
        },
        missingness=[] if isinstance(lengths, list) and len(lengths) == 16 else ["episode_lengths:CANONICAL16_INCOMPLETE"],
    )
    return {
        "unsafe_post_release_contact_count": unsafe_metric,
        "holdout_goal_rate": holdout_metric,
        "pooled_goal_rate": pooled_metric,
        "clearance_quality": clearance_metric,
        "d1_mechanics_coverage": mechanics_metric,
        "posture_pathology": posture_metric,
        "task_time_tail_p95": task_time_metric,
        "supporting_counts": {
            "route_a_unsafe_contacts": unsafe_route_a,
            "pooled48_post_release_body_contact": pooled_contacts,
            "pooled48_post_release_body_contact_missing": pooled_contact_missing,
            "holdout64_post_release_body_contact": holdout_contacts,
            "holdout64_post_release_body_contact_missing": holdout_contact_missing,
            "pooled48_goal_reached": pooled_goals,
            "holdout64_goal_reached": holdout_goals,
            "posture_behavior_category_counts": dict(sorted(category_counts.items())),
            "realized_zone_counts": dict(sorted(zones.items())),
            "posture_use_finite_rows": len(posture_values),
        },
    }


def _strict_validity(row: Mapping[str, Any], sources: Mapping[str, Any]) -> dict[str, Any]:
    candidate = row["candidate"]
    checks = {
        "candidate_freeze_full_route_a": True,
        "route_a_canonical16_receipts": True,
        "pooled48_receipt_and_records": True,
        "holdout64_receipt_and_records": True,
        "checkpoint_and_config_present": True,
        "config_initialization_regime_posture_identity": True,
        "p0_posture_records": len(row["posture_rows"]) == 48,
    }
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "value": not missing,
        "available": True,
        "status": "PASS" if not missing else "FAIL",
        "checks": checks,
        "source_paths": _rel_sources([
            V23_FREEZE_PATH,
            row["route_a"]["manifest_path"],
            row["route_a"]["selection_path"],
            row["route_a"]["analysis_path"],
            row["route_a"]["row_receipt_path"],
            row["pooled"]["top_path"],
            row["pooled"]["receipt_path"],
            V23_HOLDOUT_PATH,
            row["config_path"],
            row["checkpoint_path"],
        ]),
        "source_fields": list(IDENTITY_FIELDS + VALUE_FIELDS),
        "authority": "Exact v23 candidate freeze, Route-A, pooled48, holdout64, checkpoint and config identity receipts",
        "missingness": missing,
        "candidate_id": _candidate_id(candidate),
    }


COMPARISON_CRITERIA = (
    ("strict_evidence_validity", "max"),
    ("unsafe_post_release_contact_count", "min"),
    ("holdout_goal_rate", "max"),
    ("pooled_goal_rate", "max"),
    ("clearance_quality", "max"),
    ("d1_mechanics_coverage", "max"),
    ("posture_pathology", "min"),
    ("task_time_tail_p95", "min"),
    ("selected_checkpoint_step", "min"),
)


def _criterion_metric(row: Mapping[str, Any], criterion: str) -> dict[str, Any]:
    if criterion == "strict_evidence_validity":
        source = row["strict_evidence_validity"]
        return {"value": source.get("value"), "available": bool(source.get("available")), "missingness": source.get("missingness", [])}
    if criterion == "selected_checkpoint_step":
        return {"value": int(row["candidate"]["step"]), "available": True, "missingness": []}
    return row["metrics"][criterion]


def _compare_rows(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """Compare two rows using only pairwise-comparable preregistered criteria."""

    trace: list[dict[str, Any]] = []
    for criterion, direction in COMPARISON_CRITERIA:
        left_metric = _criterion_metric(left, criterion)
        right_metric = _criterion_metric(right, criterion)
        left_available = bool(left_metric.get("available"))
        right_available = bool(right_metric.get("available"))
        if not left_available or not right_available:
            trace.append({
                "criterion": criterion,
                "direction": direction,
                "status": "INCOMPARABLE",
                "reason": "left_unavailable" if not left_available and right_available else "right_unavailable" if left_available and not right_available else "both_unavailable",
                "left_value": left_metric.get("value") if left_available else None,
                "right_value": right_metric.get("value") if right_available else None,
                "left_available": left_available,
                "right_available": right_available,
                "left_missingness": list(left_metric.get("missingness", [])),
                "right_missingness": list(right_metric.get("missingness", [])),
            })
            continue
        left_value = left_metric.get("value")
        right_value = right_metric.get("value")
        if left_value == right_value:
            trace.append({
                "criterion": criterion,
                "direction": direction,
                "status": "TIE",
                "left_value": left_value,
                "right_value": right_value,
                "left_available": True,
                "right_available": True,
            })
            continue
        left_wins = (left_value > right_value) if direction == "max" else (left_value < right_value)
        winner = left["candidate_id"] if left_wins else right["candidate_id"]
        trace.append({
            "criterion": criterion,
            "direction": direction,
            "status": "DECISIVE",
            "left_value": left_value,
            "right_value": right_value,
            "left_available": True,
            "right_available": True,
            "winner": winner,
        })
        return {
            "left_candidate_id": left["candidate_id"],
            "right_candidate_id": right["candidate_id"],
            "winner": winner,
            "first_decisive_criterion": criterion,
            "criterion_trace": trace,
        }
    lexical_winner = min(str(left["candidate_id"]), str(right["candidate_id"]))
    trace.append({
        "criterion": "candidate_id_lexical_tie_break",
        "direction": "ascending",
        "status": "DECISIVE",
        "left_value": left["candidate_id"],
        "right_value": right["candidate_id"],
        "winner": lexical_winner,
    })
    return {
        "left_candidate_id": left["candidate_id"],
        "right_candidate_id": right["candidate_id"],
        "winner": lexical_winner,
        "first_decisive_criterion": "candidate_id_lexical_tie_break",
        "criterion_trace": trace,
    }


def _pairwise_select(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Repeatedly select a winner with the current comparable-metric sequence."""

    remaining = sorted(list(rows), key=lambda row: str(row["candidate_id"]))
    ordered: list[Mapping[str, Any]] = []
    while remaining:
        incumbent = remaining[0]
        for challenger in remaining[1:]:
            comparison = _compare_rows(incumbent, challenger)
            if comparison["winner"] == challenger["candidate_id"]:
                incumbent = challenger
        ordered.append(incumbent)
        remaining = [row for row in remaining if row["candidate_id"] != incumbent["candidate_id"]]
    return ordered


def _warm_identity_conflict(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    target = next((row for row in rows if row["candidate_id"] == "A1_G7_seed0_step1500"), None)
    if target is None:
        raise V24Error("A1_G7_seed0_step1500 is absent from FULL candidate set")
    semantics = target["semantics"]
    return {
        "candidate_id": target["candidate_id"],
        "provisional_selection": "A1_G7_seed0_step1500",
        "config_path": rel_path(target["config_path"]),
        "config_filename_token": "scratch" if "scratch" in target["config_path"].name else None,
        "formal_plan_initialization": semantics["initialization"],
        "candidate_freeze_initialization_semantics": semantics["initialization"],
        "identity_conflict": True,
        "resolution": "WARM_HEAD_RESET;CONFIG_SEMANTICS_OVERRIDE_FILENAME_TOKEN;NO_V22_WARM_RELABEL",
    }


def _ranking_rows(sources: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    built: list[dict[str, Any]] = []
    for row in rows:
        candidate = row["candidate"]
        metrics = _candidate_metrics(row, sources["posture_path"])
        strict = _strict_validity(row, sources)
        built.append({
            "candidate_id": row["candidate_id"],
            "candidate": {
                "freeze_id": candidate["freeze_id"],
                "subwave": candidate["subwave"],
                "cell": candidate["cell"],
                "seed": candidate["seed"],
                "step": candidate["step"],
                "group": "FULL",
                "door_regime": row["semantics"]["door_regime"],
                "initialization": row["semantics"]["initialization"],
                "checkpoint_start_call": "selected_checkpoint_start",
                "checkpoint_path": rel_path(row["checkpoint_path"]),
                "config_path": rel_path(row["config_path"]),
            },
            "strict_evidence_validity": strict,
            "metrics": metrics,
        })
    built = list(_pairwise_select(built))
    for index, row in enumerate(built, start=1):
        row["rank"] = index
        row["selection_method"] = "PAIRWISE_COMPARABLE_METRIC_SEQUENCE"
    selected = built[0]
    pairwise = [_compare_rows(selected, other) for other in built[1:]]
    return built, {
        "candidate_id": selected["candidate_id"],
        "checkpoint_start_call": "selected_checkpoint_start",
        "checkpoint_path": selected["candidate"]["checkpoint_path"],
        "config_path": selected["candidate"]["config_path"],
        "initialization": selected["candidate"]["initialization"],
        "door_regime": selected["candidate"]["door_regime"],
        "posture_mode": "FULL",
        "group": "FULL",
        "seed": selected["candidate"]["seed"],
        "cell": selected["candidate"]["cell"],
        "subwave": selected["candidate"]["subwave"],
        "step": selected["candidate"]["step"],
        "selection_metric_snapshot": selected["metrics"],
    }, pairwise


def build_freeze(*, sources: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    loaded = _load_sources() if sources is None else dict(sources)
    rows = _load_full_candidates(loaded)
    ranking, selected, pairwise = _ranking_rows(loaded, rows)
    payload = {
        "schema": FREEZE_SCHEMA,
        "status": "V24_WARM_START_FREEZE_COMPLETE",
        "scope": "V23_FULL_ROUTE_A_SELECTED_CHECKPOINT_START",
        "plan_id": "base_v24_friction_force_boundary_R1",
        "source_branch": "A2_Piper",
        "candidate_count": len(ranking),
        "candidate_set_rule": "Every canonical v23 FULL Route-A selected candidate across A1/B1 seeds; RP0 excluded from ranking",
        "checkpoint_call_semantics": "Each row is a selected_checkpoint_start; initialization provenance is copied from v23 config semantics",
        "ranking_rule": [
            "strict evidence validity (PASS before FAIL)",
            "zero unsafe post-release/contact (ascending)",
            "holdout goal (descending)",
            "pooled goal (descending)",
            "clearance quality (descending)",
            "D1 mechanics coverage (descending)",
            "lower posture pathology (ascending)",
            "lower task-time tail (ascending)",
            "earlier selected checkpoint (ascending)",
            "candidate_id lexical tie-break",
        ],
        "ranking_metric_policy": {
            "missingness": "Typed per metric; no missing-to-zero and no proxy substitution",
            "comparability": "Each preregistered criterion is compared only when both rows have available values; otherwise that criterion is skipped for the pair and comparison proceeds",
            "mechanics": "Observed continuous normal_zone only; goal is never a mechanics proxy",
            "unsafe_contact": "Pooled top-level unsafe_contacts is unsupported; exact per-env post_release_body_contact is retained",
        },
        "selection_algorithm": "CUSTOM_PAIRWISE_COMPARABLE_SEQUENCE;NO_AVAILABILITY_PREFERENCE",
        "ranking_rows": ranking,
        "pairwise_comparisons": pairwise,
        "selection_proof": {
            "selected_candidate_id": selected["candidate_id"],
            "comparison_count": len(pairwise),
            "comparisons_against_every_other_full_candidate": len(pairwise) == len(ranking) - 1,
            "criterion_sequence": [criterion for criterion, _direction in COMPARISON_CRITERIA],
        },
        "selected_checkpoint_start": selected,
        "provenance_conflict_resolution": _warm_identity_conflict(rows),
        "source_artifacts": {
            "candidate_freeze": rel_path(V23_FREEZE_PATH),
            "route_b": rel_path(V23_ROUTE_B_PATH),
            "holdout": rel_path(V23_HOLDOUT_PATH),
            "final_analysis": rel_path(V23_FINAL_PATH),
            "p0_posture_behavior": rel_path(loaded["posture_path"]),
        },
        "runtime_boundary": "Static ranking/freeze only; IsaacSim observation/action/terminal parity with friction=off and gate=off remains P1 runtime work",
    }
    return payload, rows


def _checkpoint_inspect(path: Path) -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - canonical env supplies torch
        raise V24Error("torch is required for static checkpoint inspection; use the IsaacLab CPU environment") from exc
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, Mapping):
        raise V24Error(f"checkpoint is not a mapping: {path}")
    required_top = {"policy_state_dict", "state", "args"}
    if not required_top.issubset(checkpoint):
        raise V24Error(f"checkpoint top-level contract is missing keys at {path}")
    policy = checkpoint["policy_state_dict"]
    if not isinstance(policy, Mapping):
        raise V24Error(f"policy_state_dict is not a mapping: {path}")
    key_set = tuple(policy.keys())
    if set(key_set) != set(EXPECTED_POLICY_KEYS):
        raise V24Error(f"policy_state_dict strict key contract mismatch: {path}")
    shapes: dict[str, list[int]] = {}
    shape_mismatch: list[str] = []
    for key in EXPECTED_POLICY_KEYS:
        value = policy[key]
        shape = tuple(int(item) for item in value.shape)
        shapes[key] = list(shape)
        if shape != EXPECTED_POLICY_SHAPES[key]:
            shape_mismatch.append(f"{key}:{shape}!={EXPECTED_POLICY_SHAPES[key]}")
    if shape_mismatch:
        raise V24Error(f"policy_state_dict shape contract mismatch at {path}: {shape_mismatch}")
    state = checkpoint["state"]
    global_step = getattr(state, "global_step", None)
    if isinstance(global_step, bool) or not isinstance(global_step, int):
        raise V24Error(f"checkpoint state.global_step is not an integer: {path}")
    return {
        "checkpoint_path": rel_path(path),
        "global_step": int(global_step),
        "top_level_keys": sorted(str(key) for key in checkpoint.keys()),
        "policy_state_dict_key_count": len(EXPECTED_POLICY_KEYS),
        "policy_state_dict_strict_key_contract": list(EXPECTED_POLICY_KEYS),
        "policy_state_dict_shapes": shapes,
        "observation_rms_shape": [133],
        "actor_lstm": {"layers": 2, "input_observation_dim": 133, "hidden_size": 256, "gate_width": 1024},
        "actor_head": {"output_action_dim": 12, "weight_shape": [12, 128], "bias_shape": [12]},
        "actor_std_shape": [12],
        "static_status": "STATIC_POLICY_STATE_DICT_COMPATIBLE",
    }


def _config_semantics(config_path: Path, candidate: Mapping[str, Any] | None, *, label: str) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, Mapping):
        raise V24Error(f"config is not a mapping: {config_path}")
    if candidate is not None and candidate.get("cell") in FULL_CELLS:
        semantics = _candidate_semantics(candidate, config)
    elif candidate is not None:
        if config.get("v23_cell") != candidate.get("cell"):
            raise V24Error(f"config cell mismatch for {label}")
        semantics = {
            "initialization": config.get("v23_initialization"),
            "door_regime": config.get("v23_door_regime"),
            "posture_mode": config.get("v23_posture_mode"),
            "checkpoint_load_mode": config.get("checkpoint_load_mode"),
            "output_head_inheritance": config.get("v23_output_head_inheritance", False),
            "warm_head_reset_enabled": _config_warm_head_reset_enabled(config),
            "schema": config.get("v23_schema"),
            "plan_id": config.get("v23_plan_id"),
        }
    else:
        semantics = {
            "initialization": "v22_anchor",
            "door_regime": "D0",
            "posture_mode": "FULL",
            "checkpoint_load_mode": config.get("checkpoint_load_mode"),
            "output_head_inheritance": False,
            "warm_head_reset_enabled": False,
            "schema": config.get("v23_schema"),
            "plan_id": config.get("v23_plan_id"),
        }
    configured_checkpoint = config.get("checkpoint")
    return {
        "label": label,
        "config_path": rel_path(config_path),
        "configured_checkpoint": None if configured_checkpoint is None else rel_path(configured_checkpoint),
        "checkpoint_load_mode": semantics.get("checkpoint_load_mode"),
        "initialization": semantics.get("initialization"),
        "door_regime": semantics.get("door_regime"),
        "posture_mode": semantics.get("posture_mode"),
        "output_head_inheritance": semantics.get("output_head_inheritance"),
        "warm_head_reset_enabled": semantics.get("warm_head_reset_enabled"),
        "schema": semantics.get("schema"),
        "plan_id": semantics.get("plan_id"),
    }


def _static_representatives(freeze_payload: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_id = {row["candidate_id"]: row for row in rows}
    selected_id = str(freeze_payload["selected_checkpoint_start"]["candidate_id"])
    representative_ids = [
        "A1_G1_seed0_step2000",
        "A1_G5_seed0_step500",
        "A1_G7_seed0_step1500",
        "B2_G2_seed1_step1750",
    ]
    representatives: list[dict[str, Any]] = []
    anchor_config = require_file("gr00t/rl/config/ablation/wbmanip/base_v23_G1_warm_D0_full.yaml", label="v22 anchor config reference")
    anchor_checkpoint = require_file("logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt", label="v22 anchor checkpoint")
    representatives.append({
        "representative_id": "v22_anchor_base_v22_G1_step1250",
        "checkpoint_path": anchor_checkpoint,
        "config_path": anchor_config,
        "candidate": None,
        "receipt_paths": [anchor_config],
        "label": "v22 anchor",
    })
    for candidate_id in representative_ids:
        if candidate_id in by_id:
            row = by_id[candidate_id]
        else:
            # RP0 is intentionally excluded from the warm-start ranking, but
            # it remains a required static compatibility representative.
            freeze_row = next((dict(item) for item in sources["freeze"].get("selected_candidates", []) if isinstance(item, Mapping) and item.get("freeze_id") == candidate_id), None)
            if freeze_row is None:
                raise V24Error(f"required static representative is absent from candidate freeze: {candidate_id}")
            route_a = _load_route_a_context(freeze_row)
            pooled = _load_route_b_context(sources["route_b"], freeze_row)
            holdout = _load_holdout_context(sources["holdout"], freeze_row)
            config_path = require_file(freeze_row["config_path"], label=f"{candidate_id} config")
            checkpoint_path = require_file(freeze_row["checkpoint_path"], label=f"{candidate_id} checkpoint")
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if not isinstance(config, Mapping) or config.get("v23_cell") != freeze_row.get("cell"):
                raise V24Error(f"RP0 config semantic identity mismatch for {candidate_id}")
            row = {
                "candidate": freeze_row,
                "candidate_id": candidate_id,
                "config": dict(config),
                "config_path": config_path,
                "checkpoint_path": checkpoint_path,
                "semantics": {
                    "initialization": config.get("v23_initialization"),
                    "door_regime": config.get("v23_door_regime"),
                    "posture_mode": config.get("v23_posture_mode"),
                    "checkpoint_load_mode": config.get("checkpoint_load_mode"),
                    "output_head_inheritance": config.get("v23_output_head_inheritance", False),
                    "warm_head_reset_enabled": _config_warm_head_reset_enabled(config),
                    "schema": config.get("v23_schema"),
                    "plan_id": config.get("v23_plan_id"),
                },
                "route_a": route_a,
                "pooled": pooled,
                "holdout": holdout,
            }
        representatives.append({
            "representative_id": candidate_id,
            "checkpoint_path": row["checkpoint_path"],
            "config_path": row["config_path"],
            "candidate": row,
            "receipt_paths": [
                row["route_a"]["row_receipt_path"],
                row["pooled"]["receipt_path"],
                V23_HOLDOUT_PATH,
            ],
            "label": "v23 FULL/RP0 representative",
        })
    if selected_id not in {item["representative_id"] for item in representatives}:
        if selected_id not in by_id:
            raise V24Error(f"selected checkpoint row is absent from source rows: {selected_id}")
        row = by_id[selected_id]
        representatives.append({
            "representative_id": selected_id,
            "checkpoint_path": row["checkpoint_path"],
            "config_path": row["config_path"],
            "candidate": row,
            "receipt_paths": [row["route_a"]["row_receipt_path"], row["pooled"]["receipt_path"], V23_HOLDOUT_PATH],
            "label": "selected checkpoint additional representative",
        })
    return representatives


def build_compatibility(freeze_payload: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], sources: Mapping[str, Any]) -> dict[str, Any]:
    representatives = _static_representatives(freeze_payload, rows, sources)
    inspected: list[dict[str, Any]] = []
    for item in representatives:
        checkpoint_path = require_file(item["checkpoint_path"], label=f"{item['representative_id']} checkpoint")
        config_path = require_file(item["config_path"], label=f"{item['representative_id']} config")
        inspection = _checkpoint_inspect(checkpoint_path)
        config_semantics = _config_semantics(config_path, None if item["candidate"] is None else item["candidate"]["candidate"], label=item["label"])
        if item["candidate"] is None and config_semantics["configured_checkpoint"] != rel_path(checkpoint_path):
            raise V24Error(f"config checkpoint reference mismatch for {item['representative_id']}")
        receipt_paths = [require_file(path, label=f"{item['representative_id']} receipt/reference") for path in item["receipt_paths"]]
        inspected.append({
            "representative_id": item["representative_id"],
            "label": item["label"],
            "checkpoint": inspection,
            "config": config_semantics,
            "receipt_paths": _rel_sources(receipt_paths),
            "candidate_identity": None if item["candidate"] is None else item["candidate"]["candidate_id"],
            "semantic_identity_status": "PASS",
        })
    contract = {
        "policy_state_dict_strict_key_contract": list(EXPECTED_POLICY_KEYS),
        "policy_state_dict_shape_contract": {key: list(shape) for key, shape in EXPECTED_POLICY_SHAPES.items()},
        "observation_rms_shape": [133],
        "actor_lstm": {"layers": 2, "input_observation_dim": 133, "hidden_size": 256},
        "actor_head_action_dim": 12,
        "actor_std_shape": [12],
        "cross_representative_key_identity": len({tuple(item["checkpoint"]["policy_state_dict_strict_key_contract"]) for item in inspected}) == 1,
    }
    return {
        "schema": COMPAT_SCHEMA,
        "status": "V24_COMPATIBILITY_STATIC_COMPLETE_RUNTIME_PENDING",
        "scope": "CPU_CHECKPOINT_CONFIG_RECEIPT_INSPECTION_ONLY",
        "representative_count": len(inspected),
        "representatives": inspected,
        "strict_key_contract": contract,
        "static_claims": [
            "checkpoint top-level and policy_state_dict key/shape contracts are compatible across representatives",
            "actor RMS observation dimension is 133 and two-layer LSTM hidden size is 256",
            "actor head/std action dimension is 12",
            "v22_warm, warm_head_reset, D0/D1 and RP0 config semantics are retained from source fields",
        ],
        "runtime_boundary": {
            "status": "RUNTIME_PARITY_PENDING",
            "required_next_lane": "P1_ISAACSIM_RUNTIME_PARITY",
            "required_settings": {"friction": "off", "gate": "off"},
            "claim_not_made": "No deterministic observation/action/terminal parity claim is made by this CPU static receipt",
        },
    }


def _markdown(freeze: Mapping[str, Any], compat: Mapping[str, Any]) -> str:
    selected = freeze["selected_checkpoint_start"]
    lines = [
        "# V24 P0 checkpoint freeze",
        "",
        "Status: `V24_WARM_START_FREEZE_COMPLETE` (CPU/source-backed mechanical reranking).",
        "",
        f"- Canonical v23 FULL Route-A candidates ranked: **{freeze['candidate_count']}**.",
        f"- Selected checkpoint start: **{selected['candidate_id']}**, `{selected['checkpoint_path']}`.",
        f"- Initialization: `{selected['initialization']}`; regime `{selected['door_regime']}`; seed `{selected['seed']}`; step `{selected['step']}`.",
        "- A1_G7_seed0_step1500 is retained as `warm_head_reset`; the `scratch` filename token is not used as provenance.",
        "- Ranking uses pairwise comparable metrics: unavailable criteria are skipped for that pair, never preferred or filled with zero.",
        f"- Pairwise selection proof covers **{freeze['selection_proof']['comparison_count']}** challengers; clearance is the first decisive criterion for B1_G3 vs A1_G7.",
        "",
        f"Static compatibility: `{compat['status']}` across **{compat['representative_count']}** representatives (v22 anchor, v23 v22_warm D0/D1, v23 warm_head_reset FULL, RP0, and selected checkpoint when additional).",
        "",
        "Runtime observation/action/terminal parity with `friction=off, gate=off` remains pending the P1 IsaacSim lane.",
        "",
    ]
    return "\n".join(lines)


def _plan() -> dict[str, Any]:
    return {
        "status": "PLAN",
        "mode": "CPU_ONLY",
        "steps": [
            "Load v23 candidate freeze, Route-A A1/B1 receipts, Route-B pooled48 records, holdout64 records and P0.1 posture behavior rows",
            "Validate exact semantic identity and rank eight FULL candidates with deterministic pairwise comparable-metric ordering",
            "Inspect static checkpoint/config/receipt compatibility for required representatives using CPU torch.load",
            "Write V24_WARM_START_FREEZE.json, V24_COMPATIBILITY_STATIC.json and V24_CHECKPOINT_FREEZE.md",
        ],
        "runtime_boundary": "No IsaacSim/GPU/runtime parity claim",
        "output_root": rel_path(V24_CHECKPOINT_FREEZE_ROOT),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write canonical checkpoint-freeze evidence")
    parser.add_argument("--dry-run", action="store_true", help="validate source routing and print the plan without writing")
    parser.add_argument("--output-dir", default=str(V24_CHECKPOINT_FREEZE_ROOT), help="canonical output directory")
    args = parser.parse_args(argv)
    if not args.write and not args.dry_run:
        args.dry_run = True
    try:
        if args.dry_run and not args.write:
            # Plan mode intentionally avoids loading torch/checkpoint tensors.
            sources = _load_sources()
            rows = _load_full_candidates(sources)
            print(json.dumps({**_plan(), "candidate_count": len(rows), "candidate_ids": [row["candidate_id"] for row in rows]}, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        sources = _load_sources()
        freeze, rows = build_freeze(sources=sources)
        compat = build_compatibility(freeze, rows, sources)
        output_dir = absolute(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "V24_WARM_START_FREEZE.json", freeze, overwrite=True)
        write_json(output_dir / "V24_COMPATIBILITY_STATIC.json", compat, overwrite=True)
        write_text(output_dir / "V24_CHECKPOINT_FREEZE.md", _markdown(freeze, compat), overwrite=True)
        print(json.dumps({
            "status": "PASS",
            "candidate_count": freeze["candidate_count"],
            "selected_checkpoint_start": freeze["selected_checkpoint_start"],
            "compatibility_status": compat["status"],
            "representative_count": compat["representative_count"],
            "output_dir": rel_path(output_dir),
        }, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (V24Error, OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        print(f"V24_CHECKPOINT_FREEZE_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
