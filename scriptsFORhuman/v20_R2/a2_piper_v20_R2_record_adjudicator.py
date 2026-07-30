"""Strict consumer for the sole R2 M48 episode-record chain.

This module accepts only records emitted by the production finalizer and the
referenced JSONL trace.  It never trusts producer-declared status or counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping
import math

from gr00t.rl.envs.door.a2_v20_r2_evidence import (
    _R2_FORBIDDEN_FIELDS,
    _R2_RECORD_SCHEMA,
    _R2_RECORD_SET_SCHEMA,
    a2_v20_r2_canonical_json_bytes,
    a2_v20_r2_finalize_record_id,
    a2_v20_r2_validate_trace_rows,
)


_RECORD_KEYS = frozenset(
    {
        "schema",
        "record_id",
        "provenance",
        "topology",
        "scenario",
        "factor",
        "phase",
        "task",
        "safety",
        "send",
        "task_space",
        "smoothness",
        "income",
        "release",
        "trace",
        "accumulator_audit",
    }
)
_PROVENANCE_DIGEST_FIELDS = (
    "source_lock_sha256",
    "plan_sha256",
    "r1_plan_sha256",
    "b0_json_sha256",
    "b0_csv_sha256",
    "urdf_sha256",
    "checkpoint_sha256",
    "source_config_sha256",
    "resolved_config_sha256",
    "runtime_config_sha256",
    "command_sha256",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA_ROOT = Path(__file__).with_name("schemas")


def _validate_schema(payload: object, schema_name: str, *, path: str) -> None:
    try:
        from jsonschema import Draft202012Validator, RefResolver
        schema_path = _SCHEMA_ROOT / schema_name
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        from urllib.parse import urljoin
        base_uri = schema_path.as_uri()
        store = {base_uri: schema}
        if isinstance(schema.get("$id"), str):
            store[schema["$id"]] = schema
            store[urljoin(base_uri, schema["$id"])] = schema
        if schema_name == "record_set_v1.schema.json":
            episode_path = _SCHEMA_ROOT / "episode_record_v1.schema.json"
            episode_schema = json.loads(episode_path.read_text(encoding="utf-8"))
            store[episode_path.as_uri()] = episode_schema
            store[urljoin(base_uri, "episode_record_v1.schema.json")] = episode_schema
            if isinstance(episode_schema.get("$id"), str):
                store[episode_schema["$id"]] = episode_schema
                store[urljoin(episode_path.as_uri(), episode_schema["$id"])] = episode_schema
        resolver = RefResolver(base_uri, schema, store=store)
        validator = Draft202012Validator(schema, resolver=resolver)
        error = next(iter(sorted(validator.iter_errors(payload), key=lambda item: list(item.path))), None)
    except (OSError, UnicodeError, json.JSONDecodeError, ImportError) as exc:
        raise R2RecordAdjudicationError(f"cannot load schema {schema_name}") from exc
    except Exception as exc:
        raise R2RecordAdjudicationError(f"schema {schema_name} resolution failed") from exc
    if error is not None:
        location = path + "".join(f"[{item!r}]" for item in error.path)
        raise R2RecordAdjudicationError(f"schema {schema_name} violation at {location}: {error.message}")


class R2RecordAdjudicationError(ValueError):
    """A strict M48 record or trace contract violation."""


def _reject_forbidden(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key.lower() in _R2_FORBIDDEN_FIELDS:
                raise R2RecordAdjudicationError(f"forbidden producer/adjudicator field at {path}.{key}")
            _reject_forbidden(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden(child, path=f"{path}[{index}]")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R2RecordAdjudicationError(f"invalid JSON artifact: {path}") from exc


def _require_digest(value: object, name: str, length: int = 64) -> str:
    if not isinstance(value, str) or not (len(value) == length and ( _HEX64 if length == 64 else _HEX40).fullmatch(value)):
        raise R2RecordAdjudicationError(f"{name} must be lowercase hexadecimal length {length}")
    return value


_R2_METRIC_STATES = frozenset({
    "DEFINED", "NO_VALID_REFERENCE", "NO_VALID_HOLD", "NO_PRE_SEND_INTERVAL",
    "INSUFFICIENT_CONSECUTIVE_SAMPLES", "NO_ACTIVE_TANGENT_SAMPLES", "NO_POSITIVE_INCOME", "NO_RELEASE",
})


def _validate_metric(value: object, *, path: str) -> None:
    if not isinstance(value, Mapping):
        raise R2RecordAdjudicationError(f"{path} must be a metric object")
    allowed = {"state", "sample_count", "value", "p10", "p50", "p95", "max"}
    if set(value) - allowed:
        raise R2RecordAdjudicationError(f"{path} has unknown metric fields")
    state = value.get("state")
    count = value.get("sample_count")
    if state not in _R2_METRIC_STATES:
        raise R2RecordAdjudicationError(f"{path}.state is not an approved reason code")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise R2RecordAdjudicationError(f"{path}.sample_count must be non-negative integer")
    distribution = any(key in value for key in ("p10", "p50", "p95", "max"))
    if distribution:
        fields = ("p10", "p50", "p95", "max")
        if "value" in value:
            raise R2RecordAdjudicationError(f"{path} cannot mix scalar and distribution fields")
    else:
        fields = ("value",)
    for key in fields:
        if key not in value:
            raise R2RecordAdjudicationError(f"{path}.{key} is required")
        child = value[key]
        if state == "DEFINED":
            if isinstance(child, bool) or not isinstance(child, (int, float)) or not math.isfinite(float(child)):
                raise R2RecordAdjudicationError(f"{path}.{key} must be finite when defined")
            if count <= 0:
                raise R2RecordAdjudicationError(f"{path}.sample_count must be positive when defined")
        elif child is not None:
            raise R2RecordAdjudicationError(f"{path}.{key} must be null for state {state}")
    if state != "DEFINED" and count != 0:
        raise R2RecordAdjudicationError(f"{path}.sample_count must be zero when state={state}")


def _validate_distribution_group(group: object, *, path: str) -> None:
    if not isinstance(group, Mapping) or not group:
        raise R2RecordAdjudicationError(f"{path} must be a non-empty metric mapping")
    for name, metric in group.items():
        if not isinstance(name, str) or name == "N/A":
            raise R2RecordAdjudicationError(f"{path} has invalid metric name")
        _validate_metric(metric, path=f"{path}.{name}")


def _validate_record(record: object, *, record_set_dir: Path) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise R2RecordAdjudicationError("record must be an object")
    _validate_schema(record, "episode_record_v1.schema.json", path="$.records[]")
    _reject_forbidden(record)
    if set(record) != _RECORD_KEYS:
        raise R2RecordAdjudicationError(
            f"record top-level fields mismatch; missing={sorted(_RECORD_KEYS - set(record))}, "
            f"extra={sorted(set(record) - _RECORD_KEYS)}"
        )
    if record.get("schema") != _R2_RECORD_SCHEMA:
        raise R2RecordAdjudicationError("record schema identifier mismatch")
    record_id = record.get("record_id")
    if not isinstance(record_id, str) or not _HEX64.fullmatch(record_id):
        raise R2RecordAdjudicationError("record_id must be lowercase SHA-256")
    without_id = dict(record)
    del without_id["record_id"]
    if a2_v20_r2_finalize_record_id(without_id) != record_id:
        raise R2RecordAdjudicationError("record_id does not match canonical non-id record")

    provenance = record["provenance"]
    if not isinstance(provenance, Mapping):
        raise R2RecordAdjudicationError("provenance must be an object")
    if provenance.get("scientific_plan_id") != "base_v20_R1_policy_behavior_v1":
        raise R2RecordAdjudicationError("scientific plan identity mismatch")
    if provenance.get("admission_plan_id") != "base_v20_R2_admission_execution_v1":
        raise R2RecordAdjudicationError("admission plan identity mismatch")
    for name in _PROVENANCE_DIGEST_FIELDS:
        _require_digest(provenance.get(name), f"provenance.{name}")
    _require_digest(provenance.get("git_commit"), "provenance.git_commit", 40)
    for name in ("urdf_path", "checkpoint_path", "source_config_path"):
        if not isinstance(provenance.get(name), str) or not provenance[name]:
            raise R2RecordAdjudicationError(f"provenance.{name} is required")
    for name in ("checkpoint_step", "seed"):
        if isinstance(provenance.get(name), bool) or not isinstance(provenance.get(name), int) or provenance[name] < 0:
            raise R2RecordAdjudicationError(f"provenance.{name} must be a non-negative integer")
    if isinstance(provenance.get("episode_ordinal"), bool) or provenance.get("episode_ordinal") != 0:
        raise R2RecordAdjudicationError("only first-episode records are admissible")
    if isinstance(provenance.get("env_id"), bool) or not isinstance(provenance.get("env_id"), int) or provenance["env_id"] < 0:
        raise R2RecordAdjudicationError("provenance.env_id is invalid")
    run_uuid = provenance.get("run_uuid")
    if not isinstance(run_uuid, str) or not run_uuid:
        raise R2RecordAdjudicationError("provenance.run_uuid is required")

    topology = record["topology"]
    if not isinstance(topology, Mapping) or topology.get("first_episode_only") is not True or topology.get("single_process") is not True:
        raise R2RecordAdjudicationError("topology must be first-episode single-process")
    physical_gpu = topology.get("physical_gpu")
    if isinstance(physical_gpu, bool) or not isinstance(physical_gpu, int) or not 0 <= physical_gpu <= 6:
        raise R2RecordAdjudicationError("topology physical_gpu must be 0-6")
    trace = record["trace"]
    if not isinstance(trace, Mapping):
        raise R2RecordAdjudicationError("trace must be an object")
    trace_path_value = trace.get("path")
    if not isinstance(trace_path_value, str) or not trace_path_value:
        raise R2RecordAdjudicationError("trace.path is required")
    trace_path = Path(trace_path_value)
    if not trace_path.is_absolute():
        trace_path = record_set_dir / trace_path
    if trace_path.is_symlink() or not trace_path.is_file():
        raise R2RecordAdjudicationError(f"trace file is missing or symlinked: {trace_path}")
    try:
        trace_bytes = trace_path.read_bytes()
        actual_trace_hash = hashlib.sha256(trace_bytes).hexdigest()
        if actual_trace_hash != trace.get("sha256"):
            raise R2RecordAdjudicationError("trace SHA-256 does not match record")
        rows = [json.loads(line) for line in trace_bytes.decode("utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R2RecordAdjudicationError(f"invalid trace artifact: {trace_path}") from exc
    task = record["task"]
    if not isinstance(task, Mapping) or not isinstance(task.get("terminal_reason"), str) or not task["terminal_reason"]:
        raise R2RecordAdjudicationError("task.terminal_reason is required")
    for row_index, row in enumerate(rows):
        _validate_schema(row, "step_trace_v1.schema.json", path=f"$.trace[{row_index}]")
    trace_summary = a2_v20_r2_validate_trace_rows(
        rows,
        run_uuid=run_uuid,
        env_id=provenance["env_id"],
        terminal_reason=task["terminal_reason"],
    )
    for key, expected in trace_summary.items():
        if trace.get(key) != expected:
            raise R2RecordAdjudicationError(f"trace.{key} disagrees with actual JSONL rows")

    for section_name in ("task_space", "smoothness"):
        _validate_distribution_group(record[section_name], path=section_name)
    income = record["income"]
    if not isinstance(income, Mapping) or not isinstance(income.get("reward_component_sums"), Mapping):
        raise R2RecordAdjudicationError("income reward_component_sums is required")
    for name, metric in income["reward_component_sums"].items():
        if not isinstance(name, str) or not name:
            raise R2RecordAdjudicationError("income reward component name is invalid")
        _validate_metric(metric, path=f"income.reward_component_sums.{name}")
    for audit_name, audit_value in record["accumulator_audit"].items():
        if audit_name == "snapshot_rejections_by_reason":
            if not isinstance(audit_value, Mapping):
                raise R2RecordAdjudicationError(
                    "accumulator_audit.snapshot_rejections_by_reason must be an object"
                )
            for reason, count in audit_value.items():
                if not isinstance(reason, str) or not reason.isdigit():
                    raise R2RecordAdjudicationError(
                        "accumulator_audit.snapshot_rejections_by_reason keys must be numeric strings"
                    )
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise R2RecordAdjudicationError(
                        "accumulator_audit.snapshot_rejections_by_reason values must be non-negative integer"
                    )
            continue
        if isinstance(audit_value, bool) or not isinstance(audit_value, int) or audit_value < 0:
            raise R2RecordAdjudicationError(f"accumulator_audit.{audit_name} must be non-negative integer")
    from copy import deepcopy

    _ = deepcopy(record)
    return dict(record)


def adjudicate_record_set(source: Path | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        payload = dict(source)
        record_set_dir = Path.cwd()
    else:
        source_path = Path(source)
        payload = _load_json(source_path)
        record_set_dir = source_path.parent
    if not isinstance(payload, Mapping):
        raise R2RecordAdjudicationError("record set must be an object")
    _validate_schema(payload, "record_set_v1.schema.json", path="$")
    _reject_forbidden(payload)
    allowed_record_set_keys = {"schema", "producer_state", "run_uuid", "records", "record_count", "trace_paths"}
    if set(payload) - allowed_record_set_keys or not {"schema", "producer_state", "run_uuid", "records", "record_count"}.issubset(payload):
        raise R2RecordAdjudicationError("record set top-level fields are not exact")
    if payload.get("schema") != _R2_RECORD_SET_SCHEMA or payload.get("producer_state") != "RECORD_SET_COMPLETE":
        raise R2RecordAdjudicationError("record set must be an exact R2 RECORD_SET_COMPLETE producer artifact")
    if not isinstance(payload.get("run_uuid"), str) or not payload["run_uuid"]:
        raise R2RecordAdjudicationError("record-set run_uuid is required")
    records = payload.get("records")
    if not isinstance(records, list) or payload.get("record_count") != len(records):
        raise R2RecordAdjudicationError("record_count must equal actual record rows")
    seen = set()
    checked = []
    for record in records:
        checked_record = _validate_record(record, record_set_dir=record_set_dir)
        provenance = checked_record["provenance"]
        if provenance["run_uuid"] != payload["run_uuid"]:
            raise R2RecordAdjudicationError("record provenance run_uuid disagrees with record-set run_uuid")
        key = (provenance["run_uuid"], provenance["env_id"])
        if key in seen:
            raise R2RecordAdjudicationError("duplicate (run_uuid, env_id) record")
        seen.add(key)
        checked.append(checked_record)
    return {
        "schema": "a2_piper_v20_R2_record_adjudication_v1",
        "adjudicator_state": "STRICT_VALID",
        "record_count": len(checked),
        "record_ids": [record["record_id"] for record in checked],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-set", required=True, type=Path)
    parser.add_argument("--output", required=False, type=Path)
    args = parser.parse_args(argv)
    result = adjudicate_record_set(args.record_set)
    if args.output is not None:
        from scriptsFORhuman.v20_R2._r2_common import write_json_exclusive

        write_json_exclusive(args.output, result)
    else:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except R2RecordAdjudicationError as exc:
        raise SystemExit(f"STRICT_INVALID: {exc}") from exc
