"""Build strict v20 canonical16/pooled48 evidence from typed telemetry artifacts."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v20_m22_evidence_v1"
MANIFEST_SCHEMA = "a2_piper_v20_m22_candidate_manifest_v1"
QUEUE_SCHEMA = "a2_piper_v20_m22_queue_v1"
TELEMETRY_FILENAME = "a2_v20_strict_telemetry.json"
EXIT_FILENAME = "eval_exit_code.txt"
TRACE_TOPOLOGY_SCHEMA = "a2_piper_v20_trace_topology_v2"
TYPED_GROUPS = {
    "send": (
        "send_ready",
        "first_send_ready_step",
        "pre_send_root_crossing",
        "first_pre_send_crossing_step",
        "hinge_at_first_root_crossing",
        "root_x_at_first_crossing",
        "root_displacement_se2",
    ),
    "crossing": ("valid", "crossing_while_holding", "hinge_at_crossing", "root_x_at_crossing"),
    "release": (
        "valid",
        "hinge_at_release",
        "root_x_at_release",
        "post_release_body_contact",
        "post_release_body_force_max",
    ),
    "carry": (
        "valid_hold",
        "arm_tangent_share",
        "handle_arc_position_error_m",
        "handle_arc_orientation_error_rad",
        "arc_tracking_quality",
        "along_handle_slip_m",
        "orthogonal_arc_residual_m",
    ),
    "smoothness": (
        "hinge_acceleration_p95",
        "hinge_jerk_p95",
        "arm_action_rate_p95",
        "arm_action_jerk_p95",
    ),
}
REQUIRED_EPISODE_METRICS = (
    "pre_crossing_bilateral",
    "pre_crossing_coasting",
    "pre_crossing_over_force",
    "held_hinge",
    "opening_slip_m",
    "positive_hinge_velocity_p95",
    "task_time_s",
)


class V20EvidenceError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V20EvidenceError(f"cannot read JSON {path}: {exc}") from exc
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V20EvidenceError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise V20EvidenceError(f"{name} must be finite")
    return result


def _typed(value: Any, name: str) -> Any:
    if isinstance(value, Mapping) and value.get("status") == "N/A":
        if (
            not isinstance(value.get("reason"), str)
            or not value["reason"]
            or isinstance(value.get("denominator"), bool)
            or not isinstance(value.get("denominator"), (int, float))
            or _finite(value["denominator"], f"{name}.denominator") < 0
            or value.get("value") is not None
        ):
            raise V20EvidenceError(f"{name} has malformed typed N/A")
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return _finite(value, name)
    if isinstance(value, list) and value:
        return [_typed(component, f"{name}[{index}]") for index, component in enumerate(value)]
    raise V20EvidenceError(f"{name} is not a typed scalar/vector/N/A")


def _validate_record(
    row: Mapping[str, Any],
    *,
    env_ids: set[int],
    checkpoint_path: str,
    checkpoint_sha256: str,
    config_hash: str,
    seed: int,
    topology: Mapping[str, Any],
) -> None:
    env_id = row.get("env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id in env_ids:
        raise V20EvidenceError(f"invalid/duplicate env_id {env_id!r}")
    env_ids.add(env_id)
    if (
        row.get("checkpoint_path") != checkpoint_path
        or row.get("checkpoint_sha256") != checkpoint_sha256
        or row.get("config_hash") != config_hash
        or row.get("seed") != seed
        or row.get("topology") != topology
    ):
        raise V20EvidenceError(f"env{env_id} provenance mismatch")
    if not isinstance(row.get("goal_reached"), bool):
        raise V20EvidenceError(f"env{env_id} goal_reached must be bool")
    if not isinstance(row.get("terminal_reason"), str) or not row["terminal_reason"]:
        raise V20EvidenceError(f"env{env_id} terminal_reason must be non-empty")
    groups = row.get("groups")
    if not isinstance(groups, Mapping) or set(groups) != set(TYPED_GROUPS):
        raise V20EvidenceError(f"env{env_id} typed group topology mismatch")
    for group_name, fields in TYPED_GROUPS.items():
        group = groups[group_name]
        if not isinstance(group, Mapping) or any(field not in group for field in fields):
            raise V20EvidenceError(f"env{env_id} group {group_name} is incomplete")
        for field in fields:
            _typed(group[field], f"env{env_id}.{group_name}.{field}")
    for group_name, validity_field in (("crossing", "valid"), ("release", "valid"), ("carry", "valid_hold")):
        group = groups[group_name]
        valid = group[validity_field]
        if not isinstance(valid, bool):
            raise V20EvidenceError(f"env{env_id} {group_name}.{validity_field} must be bool")
        fields = [field for field in TYPED_GROUPS[group_name] if field != validity_field]
        na_fields = [field for field in fields if isinstance(group[field], Mapping) and group[field].get("status") == "N/A"]
        if valid and na_fields:
            raise V20EvidenceError(f"env{env_id} valid {group_name} contains N/A fields")
        if not valid and len(na_fields) != len(fields):
            raise V20EvidenceError(f"env{env_id} invalid {group_name} must be all typed N/A")
    metrics = row.get("episode_metrics")
    if not isinstance(metrics, Mapping):
        raise V20EvidenceError(f"env{env_id} episode_metrics must be a mapping")
    for field in REQUIRED_EPISODE_METRICS:
        if field not in metrics:
            raise V20EvidenceError(f"env{env_id} missing episode metric {field}")
        _typed(metrics[field], f"env{env_id}.episode_metrics.{field}")
    units = row.get("reward_units")
    if not isinstance(units, Mapping) or not units or any(
        not isinstance(key, str) or not key or not isinstance(unit, str) or not unit
        for key, unit in units.items()
    ):
        raise V20EvidenceError(f"env{env_id} reward_units are malformed")
    trace = row.get("trace_topology")
    if (
        not isinstance(trace, Mapping)
        or trace.get("schema") != TRACE_TOPOLOGY_SCHEMA
        or trace.get("mode") not in {"full_episode", "stage_window"}
        or trace.get("first_episode_identity") is not True
        or trace.get("ordered_unique_contiguous") is not True
        or trace.get("terminal_consistent") is not True
        or trace.get("episode_length_buf_equals_step_index_plus_one") is not True
        or trace.get("captured_span_matches_trace_count") is not True
    ):
        raise V20EvidenceError(f"env{env_id} trace topology is invalid")


def load_typed_records(
    artifact: Path,
    *,
    expected_count: int,
    checkpoint_path: str,
    checkpoint_sha256: str,
    expected_seed: int,
    expected_topology_name: str,
) -> list[dict[str, Any]]:
    telemetry_path = artifact / TELEMETRY_FILENAME
    payload = _load_json(telemetry_path)
    if not isinstance(payload, Mapping) or payload.get("schema") != "a2_piper_v20_strict_telemetry_v1":
        raise V20EvidenceError(f"strict telemetry schema is invalid: {telemetry_path}")
    config_hash = payload.get("config_hash")
    topology = payload.get("topology")
    records = payload.get("records")
    if (
        not isinstance(config_hash, str)
        or not config_hash
        or not isinstance(topology, Mapping)
        or topology.get("name") != expected_topology_name
        or topology.get("episode_count") != expected_count
        or not isinstance(records, list)
        or len(records) != expected_count
    ):
        raise V20EvidenceError(f"strict telemetry header/topology is invalid: {telemetry_path}")
    seen: set[int] = set()
    for row in records:
        if not isinstance(row, Mapping):
            raise V20EvidenceError("strict telemetry records must be mappings")
        _validate_record(
            row,
            env_ids=seen,
            checkpoint_path=checkpoint_path,
            checkpoint_sha256=checkpoint_sha256,
            config_hash=config_hash,
            seed=expected_seed,
            topology=topology,
        )
    if seen != set(range(expected_count)):
        raise V20EvidenceError(f"telemetry env coverage must be 0..{expected_count - 1}")
    return [dict(row) for row in records]


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    index = max(0, min(99, int(round(probability * 100)) - 1))
    return statistics.quantiles(sorted(values), n=100, method="inclusive")[index]


def _numbers(rows: Sequence[Mapping[str, Any]], group: str, field: str) -> list[float]:
    result = []
    for row in rows:
        value = _typed(row["groups"][group][field], f"{group}.{field}")
        if value is not None and not isinstance(value, (bool, list)):
            result.append(float(value))
    return result


def _metric_numbers(rows: Sequence[Mapping[str, Any]], field: str) -> list[float]:
    result = []
    for row in rows:
        value = _typed(row["episode_metrics"][field], f"episode_metrics.{field}")
        if value is not None and not isinstance(value, (bool, list)):
            result.append(float(value))
    return result


def aggregate_records(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    send = [bool(_typed(row["groups"]["send"]["send_ready"], "send_ready")) for row in rows]
    pre_send = [
        bool(_typed(row["groups"]["send"]["pre_send_root_crossing"], "pre_send_root_crossing"))
        for row in rows
    ]
    crossing = [
        bool(_typed(row["groups"]["crossing"]["crossing_while_holding"], "crossing_while_holding"))
        for row in rows
    ]
    arm_share = _numbers(rows, "carry", "arm_tangent_share")
    arc_pos = _numbers(rows, "carry", "handle_arc_position_error_m")
    arc_ori = _numbers(rows, "carry", "handle_arc_orientation_error_rad")
    along_slip = _numbers(rows, "carry", "along_handle_slip_m")
    orthogonal_residual = _numbers(rows, "carry", "orthogonal_arc_residual_m")
    hinge_cross = _numbers(rows, "send", "hinge_at_first_root_crossing")
    root_displacement = []
    for row in rows:
        value = _typed(row["groups"]["send"]["root_displacement_se2"], "root_displacement_se2")
        if isinstance(value, list) and value:
            root_displacement.append(float(value[0]))
    release_contacts = [
        bool(_typed(row["groups"]["release"]["post_release_body_contact"], "post_release_body_contact"))
        for row in rows
        if _typed(row["groups"]["release"]["valid"], "release.valid") is True
    ]
    result = {
        "episode_count": count,
        "goal_count": sum(bool(row["goal_reached"]) for row in rows),
        "crossing_while_holding_count": sum(crossing),
        "send_ready_count": sum(send),
        "pre_send_root_crossing_count": sum(pre_send),
        "goal_with_pre_send_crossing_count": sum(
            bool(row["goal_reached"]) and event for row, event in zip(rows, pre_send)
        ),
        "upper_dof_overspeed_count": sum(
            row["terminal_reason"] == "upper_dof_overspeed" for row in rows
        ),
        "stage4_overtime_count": sum(row["terminal_reason"] == "stage_overtime" for row in rows),
        "post_release_body_contact_count": sum(release_contacts),
        "post_release_body_force_max_p95_n": _percentile(
            _numbers(rows, "release", "post_release_body_force_max"), 0.95
        ),
        "pre_crossing_bilateral_rate": statistics.mean(_metric_numbers(rows, "pre_crossing_bilateral")),
        "pre_crossing_coasting_rate": statistics.mean(_metric_numbers(rows, "pre_crossing_coasting")),
        "pre_crossing_over_force_rate": statistics.mean(_metric_numbers(rows, "pre_crossing_over_force")),
        "hinge_at_first_crossing_p10": _percentile(hinge_cross, 0.10),
        "hinge_at_first_crossing_p50": _percentile(hinge_cross, 0.50),
        "pre_send_forward_displacement_p95": _percentile(root_displacement, 0.95),
        "held_hinge_p50": _percentile(_metric_numbers(rows, "held_hinge"), 0.50),
        "held_hinge_p95": _percentile(_metric_numbers(rows, "held_hinge"), 0.95),
        "opening_slip_p95_m": _percentile(_metric_numbers(rows, "opening_slip_m"), 0.95),
        "arm_tangent_share_p10": _percentile(arm_share, 0.10),
        "arm_tangent_share_p50": _percentile(arm_share, 0.50),
        "arc_position_error_p95_m": _percentile(arc_pos, 0.95),
        "arc_orientation_error_p95_rad": _percentile(arc_ori, 0.95),
        "along_handle_slip_p95_m": _percentile(along_slip, 0.95),
        "orthogonal_arc_residual_p95_m": _percentile(orthogonal_residual, 0.95),
        "positive_hinge_velocity_p95": _percentile(
            _metric_numbers(rows, "positive_hinge_velocity_p95"), 0.95
        ),
        "hinge_acceleration_p95": _percentile(_numbers(rows, "smoothness", "hinge_acceleration_p95"), 0.95),
        "hinge_jerk_p95": _percentile(_numbers(rows, "smoothness", "hinge_jerk_p95"), 0.95),
        "arm_action_rate_p95": _percentile(_numbers(rows, "smoothness", "arm_action_rate_p95"), 0.95),
        "arm_action_jerk_p95": _percentile(_numbers(rows, "smoothness", "arm_action_jerk_p95"), 0.95),
        "median_task_time_s": _percentile(_metric_numbers(rows, "task_time_s"), 0.50),
    }
    return result


def _exit_code(artifact: Path) -> int:
    try:
        text = (artifact / EXIT_FILENAME).read_text(encoding="utf-8").strip()
        value = int(text)
    except (OSError, ValueError) as exc:
        raise V20EvidenceError(f"missing/invalid {EXIT_FILENAME}: {artifact}") from exc
    if text != str(value) or value < 0:
        raise V20EvidenceError(f"non-canonical exit code: {artifact}")
    return value


def build_evidence(manifest: Mapping[str, Any], queue: Mapping[str, Any]) -> dict[str, Any]:
    if manifest.get("schema") != MANIFEST_SCHEMA or queue.get("schema") != QUEUE_SCHEMA:
        raise V20EvidenceError("manifest/queue schema mismatch")
    candidates = {row["candidate_id"]: row for row in manifest.get("candidates", [])}
    queue_rows = {row["candidate"]["candidate_id"]: row for row in queue.get("rows", [])}
    if len(candidates) != 10 or set(candidates) != set(queue_rows):
        raise V20EvidenceError("canonical M22 evidence requires exact ten candidate bindings")
    rows = []
    for candidate_id, candidate in candidates.items():
        queue_row = queue_rows[candidate_id]
        if queue_row.get("candidate") != candidate:
            raise V20EvidenceError(f"queue binding mismatch for {candidate_id}")
        artifact = Path(queue_row["artifact"]).expanduser().resolve()
        row = {
            "candidate_id": candidate_id,
            "artifact": str(artifact),
            "checkpoint_path": candidate["path"],
            "checkpoint_sha256": candidate["sha256"],
            "evaluation_topology": "canonical16",
            "evaluation_seed": 0,
        }
        try:
            exit_code = _exit_code(artifact)
            if exit_code != 0:
                raise V20EvidenceError(f"eval exit code {exit_code}")
            records = load_typed_records(
                artifact,
                expected_count=16,
                checkpoint_path=candidate["path"],
                checkpoint_sha256=candidate["sha256"],
                expected_seed=0,
                expected_topology_name="canonical16",
            )
            row["metrics"] = aggregate_records(records)
        except V20EvidenceError as exc:
            row["strict_status"] = "STRICT_INVALID"
            row["reason"] = str(exc)
        else:
            row["strict_status"] = "STRICT_VALID"
        rows.append(row)
    return {"schema": SCHEMA, "rows": rows}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output.exists():
        raise V20EvidenceError(f"refusing to overwrite evidence: {args.output}")
    evidence = build_evidence(_load_json(args.manifest), _load_json(args.queue))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(args.output, flags, 0o644)
    except FileExistsError as exc:
        raise V20EvidenceError(f"refusing to overwrite evidence: {args.output}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.unlink(args.output)
        except FileNotFoundError:
            pass
        raise
    valid = sum(row["strict_status"] == "STRICT_VALID" for row in evidence["rows"])
    print(f"v20 M22 evidence strict-valid={valid}/{len(evidence['rows'])}: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V20EvidenceError as exc:
        print(f"v20 M22 EVIDENCE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
