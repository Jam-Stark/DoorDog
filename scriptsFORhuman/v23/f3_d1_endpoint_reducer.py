"""Adjudicate the pre-registered v23 F3 D1 endpoint rule.

F3 is intentionally a small, pure-data reducer.  It reads the sealed A1
Route-A evidence index and the two endpoint rows for seed 0, cells G5 and G7,
at checkpoint step 2500.  The sole criterion is:

    trigger iff both endpoint cells have never entered stage 3.

The authoritative stage-3 evidence is the raw ``stage_buf`` field in
``stage2_step_trace.json``.  The v23 producer names stage 3 ``STAGE_OPEN`` and
captures the buffer before staged-task advancement; staged-task advancement
increments the integer stage by one.  Therefore an entry with
``stage_buf == 3`` is a direct stage-3 observation.  Aggregate success,
intermediate checkpoints, symmetry, and completeness are not F3 criteria.

This module never launches training or evaluation.  A receipt is written only
after all endpoint identity and evidence checks pass, and an existing receipt
is never overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23_PLAN_ID, V23_ROUTE_A_STEPS
except ImportError:  # direct ``python scriptsFORhuman/v23/f3_d1_endpoint_reducer.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23_PLAN_ID, V23_ROUTE_A_STEPS


TASK_ID = "V23-F3-ENDPOINT-REDUCER-R274"
REVISION = "R274"
INDEX_SCHEMA = "a2_piper_v23_route_a_evidence_index_v1"
ROW_SCHEMA = "a2_piper_v23_route_a_row_receipt_v1"
RECEIPT_SCHEMA = "a2_piper_v23_f3_d1_endpoint_reducer_v1"
RECEIPT_STATUS = "COMPLETE"
SOURCE_BRANCH = "A2_Piper"
IDENTITY_POLICY = "OWNER_NO_HASH_PATH_IDENTITY"
SUBWAVE = "A1"
SEED = 0
ENDPOINT_STEP = 2500
TOPOLOGY = "canonical16"
ENDPOINT_CELLS = ("G5", "G7")
ALL_A1_CELLS = ("G1", "G3", "G5", "G7")
STAGE_TRACE_FILENAME = "stage2_step_trace.json"
RECORDS_FILENAME = "a2_v14_per_env_records.json"
ROW_RECEIPT_FILENAME = "row_receipt.json"
STAGE3_VALUE = 3
VALID_TRACE_STAGES = frozenset({2, 3, 4, 5})

DEFAULT_INDEX = REPO_ROOT / "logs_eval/base_v23/route_a/seed0/A1/V23_ROUTE_A_EVIDENCE_INDEX.json"
DEFAULT_OUTPUT = REPO_ROOT / "logs_eval/base_v23/route_a/seed0/A1/V23_F3_D1_ENDPOINT_REDUCER.json"


class F3EndpointError(ValueError):
    """Raised when the strict F3 endpoint evidence is absent or ambiguous."""


def _regular_file(path: Path, *, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise F3EndpointError(f"{label} is not a regular file: {path}")
    return path


def _read_json(path: Path, *, label: str) -> Any:
    _regular_file(path, label=label)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise F3EndpointError(f"{label} is not valid JSON: {path}") from exc


def _read_object(path: Path, *, label: str) -> dict[str, Any]:
    value = _read_json(path, label=label)
    if not isinstance(value, dict):
        raise F3EndpointError(f"{label} must be a JSON object: {path}")
    return value


def _require_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise F3EndpointError(f"{name} must be an integer; got {value!r}")
    return value


def _resolve_path(raw: Any, *, base: Path, name: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise F3EndpointError(f"{name} must be a non-empty path string")
    path = Path(raw)
    return path if path.is_absolute() else base / path


def _expected_row_id(cell: str, step: int) -> str:
    return f"{cell}:step{step:04d}"


def _validate_index(index: Mapping[str, Any], *, source: Path) -> list[Mapping[str, Any]]:
    expected = {
        "schema": INDEX_SCHEMA,
        "status": "COMPLETE",
        "source_branch": SOURCE_BRANCH,
        "plan_id": V23_PLAN_ID,
        "identity_policy": IDENTITY_POLICY,
        "route": "A",
        "subwave": SUBWAVE,
        "seed": SEED,
        "topology": TOPOLOGY,
    }
    for key, wanted in expected.items():
        if index.get(key) != wanted:
            raise F3EndpointError(
                f"Route-A index {source} field {key} disagrees: "
                f"expected {wanted!r}, got {index.get(key)!r}"
            )

    raw_rows = index.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise F3EndpointError(f"Route-A index must contain endpoint row evidence: {source}")

    rows: list[Mapping[str, Any]] = []
    for row_index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, Mapping):
            raise F3EndpointError(f"Route-A index row {row_index} is not an object: {source}")
        cell = raw_row.get("cell")
        step = raw_row.get("step")
        if cell not in ENDPOINT_CELLS or step != ENDPOINT_STEP:
            continue
        identity = {
            "schema": ROW_SCHEMA,
            "status": "ROW_PASS",
            "source_branch": SOURCE_BRANCH,
            "plan_id": V23_PLAN_ID,
            "identity_policy": IDENTITY_POLICY,
            "subwave": SUBWAVE,
            "seed": SEED,
            "cell": cell,
            "step": step,
            "topology": TOPOLOGY,
            "row_id": _expected_row_id(cell, step),
            "checkpoint_load_mode": "policy_only",
            "episode_record_count": 16,
            "metrics_completed_episodes": 16,
            "trace_env_ids": list(range(16)),
        }
        for key, wanted in identity.items():
            if raw_row.get(key) != wanted:
                raise F3EndpointError(
                    f"Route-A index row {row_index} field {key} disagrees: "
                    f"expected {wanted!r}, got {raw_row.get(key)!r}"
                )
        rows.append(raw_row)
    return rows


def _endpoint_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    selected: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if row.get("cell") in ENDPOINT_CELLS and row.get("step") == ENDPOINT_STEP:
            cell = row["cell"]
            if cell in selected:
                raise F3EndpointError(f"Route-A index has duplicate endpoint row for {cell}")
            selected[cell] = row
    if set(selected) != set(ENDPOINT_CELLS):
        missing = sorted(set(ENDPOINT_CELLS) - set(selected))
        raise F3EndpointError(f"A1 endpoint evidence is missing for cells: {missing}")
    return selected


def _validate_row_receipt(
    row: Mapping[str, Any],
    *,
    index_source: Path,
) -> tuple[Path, Path, Path, Path]:
    root = _resolve_path(row.get("evaluation_root"), base=index_source.parent, name=f"{row['row_id']}.evaluation_root")
    row_receipt_path = root / ROW_RECEIPT_FILENAME
    row_receipt = _read_object(row_receipt_path, label=f"{row['row_id']} row receipt")
    for key in (
        "schema",
        "status",
        "row_id",
        "source_branch",
        "plan_id",
        "identity_policy",
        "subwave",
        "seed",
        "cell",
        "step",
        "topology",
        "checkpoint_load_mode",
        "episode_record_count",
        "metrics_completed_episodes",
        "trace_env_ids",
    ):
        if row_receipt.get(key) != row.get(key):
            raise F3EndpointError(
                f"{row['row_id']} row receipt field {key} disagrees with the sealed index"
            )
    records_path = root / RECORDS_FILENAME
    trace_path = root / STAGE_TRACE_FILENAME
    if row.get("records_path") != str(records_path) or row.get("raw_trace_path") != str(trace_path):
        raise F3EndpointError(f"{row['row_id']} sealed evidence paths disagree with its evaluation root")
    return row_receipt_path, records_path, trace_path, root


def _validate_records(path: Path, *, cell: str) -> int:
    records = _read_json(path, label=f"{cell} strict episode records")
    if not isinstance(records, list) or len(records) != 16:
        raise F3EndpointError(f"{cell} strict episode records must contain exactly 16 rows: {path}")
    seen: set[int] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise F3EndpointError(f"{cell} strict episode record {index} is not an object: {path}")
        env_id = _require_int(record.get("env_id"), name=f"{cell}.records[{index}].env_id")
        if env_id not in range(16) or env_id in seen:
            raise F3EndpointError(f"{cell} strict episode records have invalid/duplicate env_id={env_id}")
        if record.get("seed") != SEED:
            raise F3EndpointError(f"{cell} strict episode record env{env_id} is not seed0")
        seen.add(env_id)
    if seen != set(range(16)):
        raise F3EndpointError(f"{cell} strict episode records do not cover env ids 0..15")
    return len(records)


def _stage3_evidence(path: Path, *, cell: str) -> tuple[int, int, list[int], int]:
    trace = _read_json(path, label=f"{cell} raw Route-A trace")
    if not isinstance(trace, list) or not trace:
        raise F3EndpointError(f"{cell} raw Route-A trace is empty: {path}")
    trace_env_ids: set[int] = set()
    stage3_env_ids: set[int] = set()
    stage3_trace_entry_count = 0
    for index, entry in enumerate(trace):
        if not isinstance(entry, Mapping):
            raise F3EndpointError(f"{cell} raw trace row {index} is not an object: {path}")
        env_id = _require_int(entry.get("env_id"), name=f"{cell}.trace[{index}].env_id")
        if env_id not in range(16):
            raise F3EndpointError(f"{cell} raw trace row {index} has invalid env_id={env_id}")
        stage_buf = _require_int(entry.get("stage_buf"), name=f"{cell}.trace[{index}].stage_buf")
        if stage_buf not in VALID_TRACE_STAGES:
            raise F3EndpointError(
                f"{cell} raw trace row {index} has stage_buf outside strict stage2-5 trace: {stage_buf}"
            )
        trace_env_ids.add(env_id)
        if stage_buf == STAGE3_VALUE:
            stage3_trace_entry_count += 1
            stage3_env_ids.add(env_id)
    if trace_env_ids != set(range(16)):
        raise F3EndpointError(f"{cell} raw Route-A trace does not cover env ids 0..15: {path}")
    return stage3_trace_entry_count, len(stage3_env_ids), sorted(stage3_env_ids), len(trace)


def reduce_endpoint(index_path: Path, *, output_path: Path | None = None) -> dict[str, Any]:
    """Validate A1 endpoint evidence and optionally append the F3 receipt."""

    source = _regular_file(index_path, label="Route-A evidence index")
    index = _read_object(source, label="Route-A evidence index")
    rows = _validate_index(index, source=source)
    endpoint_rows = _endpoint_rows(rows)

    endpoint_evidence: dict[str, dict[str, Any]] = {}
    for cell in ENDPOINT_CELLS:
        row = endpoint_rows[cell]
        row_receipt_path, records_path, trace_path, root = _validate_row_receipt(row, index_source=source)
        record_count = _validate_records(records_path, cell=cell)
        stage3_trace_entry_count, stage3_env_count, stage3_env_ids, trace_row_count = _stage3_evidence(
            trace_path, cell=cell
        )
        endpoint_evidence[cell] = {
            "row_id": row["row_id"],
            "cell": cell,
            "seed": SEED,
            "step": ENDPOINT_STEP,
            "topology": TOPOLOGY,
            "evaluation_root": str(root),
            "row_receipt_path": str(row_receipt_path),
            "records_path": str(records_path),
            "raw_trace_path": str(trace_path),
            "episode_record_count": record_count,
            "trace_row_count": trace_row_count,
            "stage3_trace_entry_count": stage3_trace_entry_count,
            "stage3_env_count": stage3_env_count,
            "stage3_env_ids": stage3_env_ids,
        }

    triggered = all(endpoint_evidence[cell]["stage3_env_count"] == 0 for cell in ENDPOINT_CELLS)
    payload: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": RECEIPT_STATUS,
        "task_id": TASK_ID,
        "revision": REVISION,
        "plan_id": V23_PLAN_ID,
        "source_branch": SOURCE_BRANCH,
        "identity_policy": IDENTITY_POLICY,
        "route": "A",
        "subwave": SUBWAVE,
        "seed": SEED,
        "cells": list(ENDPOINT_CELLS),
        "endpoint_step": ENDPOINT_STEP,
        "topology": TOPOLOGY,
        "authoritative_criterion": (
            "F3 triggers iff BOTH A1 seed0 D1 FULL cells G5 and G7 at endpoint "
            "step2500 never entered stage3 in their canonical16 Route-A evaluation."
        ),
        "stage3_definition": (
            "A stage3 observation is a raw stage2_step_trace.json entry with "
            "stage_buf == 3 (producer STAGE_OPEN=3; stage buffer is captured "
            "pre-advance and staged-task advancement increments by one)."
        ),
        "result": "F3_TRIGGERED_D1_LITE" if triggered else "F3_NOT_TRIGGERED",
        "a1_evidence_preserved": True,
        "source_index": str(source),
        "endpoint_evidence": endpoint_evidence,
        "no_training_or_eval_launched": True,
    }
    if triggered:
        payload["label"] = "D1_PRIME_NOT_REPLICATION"

    if output_path is not None:
        target = output_path
        if target.exists():
            raise F3EndpointError(f"refusing to overwrite existing F3 receipt: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
                handle.write("\n")
        except FileExistsError as exc:
            raise F3EndpointError(f"refusing to overwrite existing F3 receipt: {target}") from exc
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="sealed A1 Route-A evidence index")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="new append-only F3 receipt path")
    args = parser.parse_args(argv)
    try:
        payload = reduce_endpoint(args.index, output_path=args.output)
    except F3EndpointError as exc:
        print(f"V23 F3 D1 ENDPOINT REDUCER FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
