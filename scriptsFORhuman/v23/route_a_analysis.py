"""Strict mechanical analysis for one v23 Route-A evidence index.

The analysis reads the 40 sealed canonical16 rows produced by ``m22.py`` and
extracts only the preregistered selection fields: goal reached, supported
crossing, unsafe contacts, terminal failures, and checkpoint step.  Missing
fields are typed evidence failures; they are never converted to zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23_GPU_SUBWAVES, V23_PLAN_ID, V23_ROUTE_A_STEPS, V23Error, write_json
    from .m22 import INDEX_SCHEMA, ROUTE_A_ROOT, ROUTE_A_ENVS, _load_object, _route_root
except ImportError:  # direct ``python scriptsFORhuman/v23/route_a_analysis.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23_GPU_SUBWAVES, V23_PLAN_ID, V23_ROUTE_A_STEPS, V23Error, write_json
    from scriptsFORhuman.v23.m22 import INDEX_SCHEMA, ROUTE_A_ROOT, ROUTE_A_ENVS, _load_object, _route_root


ANALYSIS_SCHEMA = "a2_piper_v23_route_a_analysis_v1"
ANALYSIS_STATUS = "COMPLETE"
V23_UNSAFE_CONTACT_FIELD = "v23_unsafe_contact"


class RouteAAnalysisError(V23Error):
    """Typed Route-A evidence absence or schema mismatch."""


def _json_any(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RouteAAnalysisError(f"Route-A evidence is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RouteAAnalysisError(f"Route-A evidence is not valid JSON: {path}") from exc


def _bool_value(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise RouteAAnalysisError(f"Route-A field {field} must be boolean, got {value!r}")
    return value


def _terminal_reason_failed(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        raise RouteAAnalysisError(f"Route-A field {field} is missing")
    if not isinstance(value, str):
        raise RouteAAnalysisError(f"Route-A field {field} must be boolean or reason text")
    normalized = value.strip().lower()
    if not normalized:
        raise RouteAAnalysisError(f"Route-A field {field} is empty")
    return normalized not in {"none", "success", "goal", "goal_reached", "completed", "complete"}


def _trace_by_env(trace: Any, *, path: Path) -> dict[int, list[Mapping[str, Any]]]:
    if not isinstance(trace, list) or not trace:
        raise RouteAAnalysisError(f"Route-A raw trace is empty: {path}")
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for index, entry in enumerate(trace):
        if not isinstance(entry, Mapping):
            raise RouteAAnalysisError(f"Route-A trace row {index} is not an object: {path}")
        env_id = entry.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in range(ROUTE_A_ENVS):
            raise RouteAAnalysisError(f"Route-A trace row {index} has invalid env_id: {path}")
        grouped.setdefault(env_id, []).append(entry)
    if sorted(grouped) != list(range(ROUTE_A_ENVS)):
        raise RouteAAnalysisError(f"Route-A trace does not cover env ids 0..15: {path}")
    return grouped


def _unsafe_for_env(record: Mapping[str, Any], *, row_id: str, env_id: int) -> bool:
    if V23_UNSAFE_CONTACT_FIELD not in record:
        raise RouteAAnalysisError(
            f"{row_id} env{env_id} is missing direct {V23_UNSAFE_CONTACT_FIELD} evidence"
        )
    return _bool_value(
        record[V23_UNSAFE_CONTACT_FIELD],
        field=f"{row_id}.env{env_id}.{V23_UNSAFE_CONTACT_FIELD}",
    )


def _terminal_failure_for_env(
    record: Mapping[str, Any],
    trace_rows: Sequence[Mapping[str, Any]],
    terminal_reasons: Sequence[Any] | None,
    *,
    row_id: str,
    env_id: int,
) -> bool:
    for field in ("terminal_failure", "terminal_failed", "failure", "failed", "terminal_reason"):
        if field in record:
            return _terminal_reason_failed(record[field], field=f"{row_id}.env{env_id}.{field}")
    found = False
    failure = False
    for entry in trace_rows:
        for field in ("terminal_failure", "terminal_failed", "terminal_reason"):
            if field in entry:
                found = True
                failure = failure or _terminal_reason_failed(entry[field], field=f"{row_id}.env{env_id}.{field}")
    if found:
        return failure
    if terminal_reasons is not None:
        return _terminal_reason_failed(terminal_reasons[env_id], field=f"{row_id}.metrics.episode_terminal_reasons[{env_id}]")
    raise RouteAAnalysisError(f"{row_id} env{env_id} has no terminal-failure evidence")


def analyze_row(row: Mapping[str, Any]) -> dict[str, Any]:
    row_id = row.get("row_id")
    if not isinstance(row_id, str) or not row_id:
        raise RouteAAnalysisError("Route-A row has no row_id")
    root = Path(row.get("evaluation_root", ""))
    records_path = root / "a2_v14_per_env_records.json"
    trace_path = root / "stage2_step_trace.json"
    metrics_path = root / "metrics_eval.json"
    records = _json_any(records_path)
    trace = _trace_by_env(_json_any(trace_path), path=trace_path)
    metrics = _json_any(metrics_path)
    if not isinstance(records, list) or len(records) != ROUTE_A_ENVS:
        raise RouteAAnalysisError(f"{row_id} must contain exactly 16 episode records")
    by_env = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise RouteAAnalysisError(f"{row_id} contains a non-object episode record")
        env_id = record.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id in by_env or env_id not in range(ROUTE_A_ENVS):
            raise RouteAAnalysisError(f"{row_id} episode env ids are invalid or duplicated")
        by_env[env_id] = record
    if sorted(by_env) != list(range(ROUTE_A_ENVS)):
        raise RouteAAnalysisError(f"{row_id} episode records do not cover env ids 0..15")
    terminal_reasons = None
    if isinstance(metrics, Mapping) and "episode_terminal_reasons" in metrics:
        value = metrics["episode_terminal_reasons"]
        if not isinstance(value, list) or len(value) != ROUTE_A_ENVS:
            raise RouteAAnalysisError(f"{row_id} episode_terminal_reasons is not a length-16 list")
        terminal_reasons = value

    goals = []
    crossings = []
    unsafe = []
    failures = []
    for env_id in range(ROUTE_A_ENVS):
        record = by_env[env_id]
        if "goal_reached" not in record:
            raise RouteAAnalysisError(f"{row_id} env{env_id} missing goal_reached")
        if "crossing_while_holding" not in record:
            raise RouteAAnalysisError(f"{row_id} env{env_id} missing crossing_while_holding")
        goals.append(_bool_value(record["goal_reached"], field=f"{row_id}.env{env_id}.goal_reached"))
        crossings.append(_bool_value(record["crossing_while_holding"], field=f"{row_id}.env{env_id}.crossing_while_holding"))
        unsafe.append(_unsafe_for_env(record, row_id=row_id, env_id=env_id))
        failures.append(_terminal_failure_for_env(record, trace[env_id], terminal_reasons, row_id=row_id, env_id=env_id))
    return {
        "row_id": row_id,
        "source_branch": row["source_branch"],
        "plan_id": row["plan_id"],
        "identity_policy": row["identity_policy"],
        "subwave": row["subwave"],
        "seed": row["seed"],
        "cell": row["cell"],
        "step": row["step"],
        "topology": row["topology"],
        "physical_gpu": row["physical_gpu"],
        "checkpoint_path": row["checkpoint_path"],
        "config_path": row["config_path"],
        "scenario_path": row["scenario_path"],
        "evaluation_root": row["evaluation_root"],
        "episode_count": ROUTE_A_ENVS,
        "goal_reached": sum(goals),
        "supported_crossing": sum(crossings),
        "unsafe_contacts": sum(unsafe),
        "terminal_failures": sum(failures),
        "missing_evidence": [],
        "evidence_status": "SUPPORTED",
        "records_path": str(records_path),
        "raw_trace_path": str(trace_path),
        "metrics_path": str(metrics_path),
    }


def analyze(subwave: str, *, index_path: Path | None = None) -> dict[str, Any]:
    if subwave not in V23_GPU_SUBWAVES:
        raise RouteAAnalysisError(f"unknown scientific sub-wave: {subwave}")
    root = _route_root(subwave)
    source = index_path or (root / "V23_ROUTE_A_EVIDENCE_INDEX.json")
    index = _load_object(source)
    if index.get("schema") != INDEX_SCHEMA or index.get("status") != "COMPLETE":
        raise RouteAAnalysisError(f"Route-A evidence index is not complete: {source}")
    spec = V23_GPU_SUBWAVES[subwave]
    if index.get("subwave") != subwave or index.get("seed") != spec["seed"]:
        raise RouteAAnalysisError(f"Route-A index identity does not match requested sub-wave: {source}")
    if (
        index.get("source_branch") != "A2_Piper"
        or index.get("plan_id") != V23_PLAN_ID
        or index.get("identity_policy") != "OWNER_NO_HASH_PATH_IDENTITY"
    ):
        raise RouteAAnalysisError(f"Route-A index provenance disagrees with the v23 plan: {source}")
    if index.get("topology") != "canonical16":
        raise RouteAAnalysisError(f"Route-A index topology is not canonical16: {source}")
    rows = index.get("rows")
    if not isinstance(rows, list) or len(rows) != 40:
        raise RouteAAnalysisError(f"Route-A evidence index must contain exactly 40 rows: {source}")
    expected_pairs = {
        (cell, step)
        for cell in spec["cells"]
        for step in V23_ROUTE_A_STEPS
    }
    observed_pairs = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise RouteAAnalysisError(f"Route-A index contains a non-object row: {source}")
        if (
            row.get("subwave") != subwave
            or row.get("seed") != spec["seed"]
            or row.get("topology") != "canonical16"
            or row.get("source_branch") != "A2_Piper"
            or row.get("plan_id") != V23_PLAN_ID
            or row.get("identity_policy") != "OWNER_NO_HASH_PATH_IDENTITY"
            or row.get("cell") not in spec["cells"]
            or row.get("step") not in V23_ROUTE_A_STEPS
        ):
            raise RouteAAnalysisError(f"Route-A row identity disagrees with requested sub-wave: {row.get('row_id')!r}")
        pair = (row["cell"], row["step"])
        if pair in observed_pairs:
            raise RouteAAnalysisError(f"Route-A index contains a duplicate checkpoint identity: {pair!r}")
        observed_pairs.add(pair)
    if observed_pairs != expected_pairs:
        raise RouteAAnalysisError("Route-A index must contain exactly cells x steps 250..2500")
    analyzed = [analyze_row(row) for row in rows]
    payload = {
        "schema": ANALYSIS_SCHEMA,
        "status": ANALYSIS_STATUS,
        "recorded_at_utc": datetime_now(),
        "route": "A",
        "subwave": subwave,
        "seed": spec["seed"],
        "cells": list(spec["cells"]),
        "steps": list(V23_ROUTE_A_STEPS),
        "topology": "canonical16",
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "row_count": len(analyzed),
        "episode_record_count": sum(row["episode_count"] for row in analyzed),
        "missing_evidence": [],
        "rows": analyzed,
        "source_index": str(source),
    }
    target = root / "V23_ROUTE_A_ANALYSIS.json"
    write_json(target, payload)
    return payload


def datetime_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subwave", required=True, choices=tuple(V23_GPU_SUBWAVES))
    parser.add_argument("--index")
    args = parser.parse_args(argv)
    try:
        payload = analyze(args.subwave, index_path=Path(args.index) if args.index else None)
    except V23Error as exc:
        print(f"V23 ROUTE_A_ANALYSIS FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
