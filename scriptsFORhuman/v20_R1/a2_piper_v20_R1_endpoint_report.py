"""Strict M48 endpoint telemetry schema and aggregation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    PLAN_ID,
    R1Error,
    canonical_topology,
    exact_digest,
    finite,
    load_json,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_endpoint_record_v1"
REPORT_SCHEMA = "a2_piper_v20_R1_endpoint_report_v1"
REQUIRED_GROUPS = (
    "provenance",
    "topology",
    "task",
    "send",
    "task_space",
    "safety",
    "smoothness",
    "income",
    "phase",
    "audit",
    "trace",
    "binding",
    "factor",
    "denominators",
    "release",
)
METRIC_FIELDS = {
    "send": (
        "hinge_at_first_crossing",
        "pre_send_forward_displacement",
        "pre_send_lateral_displacement",
        "pre_send_planar_displacement",
        "pre_send_yaw_change",
    ),
    "task_space": (
        "arm_tangent_share",
        "arc_position_error_m",
        "arc_orientation_error_rad",
        "along_handle_slip_m",
    ),
    "safety": ("body_contact_force_max_n",),
    "smoothness": (
        "positive_hinge_velocity",
        "hinge_acceleration",
        "hinge_jerk",
        "arm_action_rate",
        "arm_action_jerk",
    ),
    "income": ("positive_income_ratio",),
}
CORE_METRICS = (
    ("send", "hinge_at_first_crossing"),
    ("task_space", "arm_tangent_share"),
    ("smoothness", "positive_hinge_velocity"),
)


def _strict_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise R1Error(f"{name} must be a strict boolean")
    return value


def _strict_int(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise R1Error(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise R1Error(f"{name} must be >= {minimum}")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise R1Error(f"{name} must be a mapping")
    return value


def _required(mapping: Mapping[str, Any], key: str, name: str) -> Any:
    if key not in mapping:
        raise R1Error(f"{name} missing required field {key}")
    return mapping[key]


def _typed_metric(value: Any, name: str) -> float | None:
    if isinstance(value, Mapping):
        if value.get("status") != "N/A":
            raise R1Error(f"{name} mapping must have status N/A")
        reason = value.get("reason")
        denominator = value.get("denominator")
        if (
            not isinstance(reason, str)
            or not reason
            or isinstance(denominator, bool)
            or not isinstance(denominator, int)
            or denominator < 0
        ):
            raise R1Error(
                f"{name} N/A requires a non-empty reason and non-negative denominator"
            )
        return None
    if value is None:
        raise R1Error(f"{name} must be finite or typed N/A")
    return finite(value, name)


def _metric(group: Mapping[str, Any], key: str, name: str) -> float | None:
    return _typed_metric(_required(group, key, name), name)


def _validate_trace(trace: Mapping[str, Any], name: str) -> None:
    steps = _required(trace, "step_index", name)
    if not isinstance(steps, list) or not steps:
        raise R1Error(f"{name}.step_index must be a non-empty list")
    parsed = [_strict_int(value, f"{name}.step_index[{i}]", minimum=0) for i, value in enumerate(steps)]
    if parsed != list(range(parsed[0], parsed[0] + len(parsed))):
        raise R1Error(f"{name}.step_index must be contiguous and ordered")
    if not _strict_bool(_required(trace, "terminal", name), f"{name}.terminal"):
        raise R1Error(f"{name}.terminal must be true for a terminal record")
    reason = _required(trace, "terminal_reason", name)
    if not isinstance(reason, str) or not reason:
        raise R1Error(f"{name}.terminal_reason must be non-empty")
    return


def _validate_release(release: Mapping[str, Any], name: str) -> None:
    valid = _strict_bool(_required(release, "valid", name), f"{name}.valid")
    keys = (
        "hinge_at_release",
        "root_x_at_release",
        "post_release_body_contact",
        "post_release_body_force_max_n",
    )
    values = [_required(release, key, name) for key in keys]
    if valid:
        if any(value is None for value in values):
            raise R1Error(f"{name} valid release must contain all values")
        _typed_metric(values[0], f"{name}.hinge_at_release")
        _typed_metric(values[1], f"{name}.root_x_at_release")
        _strict_bool(values[2], f"{name}.post_release_body_contact")
        _typed_metric(values[3], f"{name}.post_release_body_force_max_n")
    elif any(value is not None for value in values):
        raise R1Error(f"{name} invalid release must be all-null")


def _validate_record(record: Mapping[str, Any], index: int) -> dict[str, Any]:
    name = f"record[{index}]"
    if _required(record, "schema", name) != SCHEMA:
        raise R1Error(f"{name} has unsupported schema")
    groups = {
        group_name: _mapping(_required(record, group_name, name), f"{name}.{group_name}")
        for group_name in REQUIRED_GROUPS
    }
    provenance = groups["provenance"]
    if _required(provenance, "plan_id", f"{name}.provenance") != PLAN_ID:
        raise R1Error(f"{name} is not bound to {PLAN_ID}")
    exact_digest(
        _required(provenance, "checkpoint_sha256", f"{name}.provenance"),
        name=f"{name}.provenance.checkpoint_sha256",
        length=64,
    )
    exact_digest(
        _required(provenance, "config_sha256", f"{name}.provenance"),
        name=f"{name}.provenance.config_sha256",
        length=64,
    )
    exact_digest(
        _required(provenance, "git_commit", f"{name}.provenance"),
        name=f"{name}.provenance.git_commit",
        length=40,
    )
    for optional, length in (
        ("plan_sha256", 64),
        ("urdf_sha256", 64),
        ("resolved_hydra_sha256", 64),
    ):
        if optional in provenance:
            exact_digest(provenance[optional], name=f"{name}.provenance.{optional}", length=length)
    seed = _strict_int(_required(provenance, "seed", f"{name}.provenance.seed"), f"{name}.provenance.seed", minimum=0)
    _strict_int(_required(provenance, "env_id", f"{name}.provenance.env_id"), f"{name}.provenance.env_id", minimum=0)
    if "checkpoint_path" in provenance and (
        not isinstance(provenance["checkpoint_path"], str) or not provenance["checkpoint_path"]
    ):
        raise R1Error(f"{name}.provenance.checkpoint_path must be non-empty")
    if "config_path" in provenance and (
        not isinstance(provenance["config_path"], str) or not provenance["config_path"]
    ):
        raise R1Error(f"{name}.provenance.config_path must be non-empty")

    topology = groups["topology"]
    topology_name = _required(topology, "name", f"{name}.topology")
    if not isinstance(topology_name, str):
        raise R1Error(f"{name}.topology.name must be a string")
    expected = canonical_topology(topology_name)
    episode_count = _strict_int(_required(topology, "episode_count", f"{name}.topology"), f"{name}.topology.episode_count", minimum=1)
    if episode_count != expected["episodes"]:
        raise R1Error(f"{name}.topology episode_count must be {expected['episodes']}")
    _strict_bool(_required(topology, "first_episode_only", f"{name}.topology"), f"{name}.topology.first_episode_only")
    _strict_bool(_required(topology, "single_process", f"{name}.topology"), f"{name}.topology.single_process")
    if topology["first_episode_only"] is not True or topology["single_process"] is not True:
        raise R1Error(f"{name}.topology must be first-episode single-process")

    task = groups["task"]
    goal = _strict_bool(_required(task, "goal", f"{name}.task"), f"{name}.task.goal")
    crossing = _strict_bool(
        _required(task, "crossing_while_holding", f"{name}.task"),
        f"{name}.task.crossing_while_holding",
    )
    _strict_bool(_required(task, "complete", f"{name}.task"), f"{name}.task.complete")
    _strict_int(_required(task, "max_stage", f"{name}.task"), f"{name}.task.max_stage", minimum=0)
    if goal and not crossing:
        raise R1Error(f"{name}.task.goal requires crossing_while_holding=true")

    send = groups["send"]
    _strict_bool(_required(send, "send_ready", f"{name}.send"), f"{name}.send.send_ready")
    for key in METRIC_FIELDS["send"]:
        _metric(send, key, f"{name}.send.{key}")
    task_space = groups["task_space"]
    _strict_bool(
        _required(task_space, "valid_reference", f"{name}.task_space"),
        f"{name}.task_space.valid_reference",
    )
    for key in METRIC_FIELDS["task_space"]:
        _metric(task_space, key, f"{name}.task_space.{key}")
    safety = groups["safety"]
    _strict_bool(
        _required(safety, "upper_dof_overspeed", f"{name}.safety"),
        f"{name}.safety.upper_dof_overspeed",
    )
    for key in METRIC_FIELDS["safety"]:
        _metric(safety, key, f"{name}.safety.{key}")
    for section in ("smoothness", "income"):
        for key in METRIC_FIELDS[section]:
            _metric(groups[section], key, f"{name}.{section}.{key}")

    phase = groups["phase"]
    _strict_int(_required(phase, "stage", f"{name}.phase"), f"{name}.phase.stage", minimum=0)
    _strict_int(
        _required(phase, "time_in_stage", f"{name}.phase"),
        f"{name}.phase.time_in_stage",
        minimum=0,
    )
    if not isinstance(_required(phase, "curriculum_phase", f"{name}.phase"), str):
        raise R1Error(f"{name}.phase.curriculum_phase must be a string")

    audit = groups["audit"]
    _strict_bool(
        _required(audit, "crossing_event_valid", f"{name}.audit"),
        f"{name}.audit.crossing_event_valid",
    )
    _strict_bool(
        _required(audit, "release_event_valid", f"{name}.audit"),
        f"{name}.audit.release_event_valid",
    )
    terminal_reason = _required(audit, "terminal_reason", f"{name}.audit")
    if not isinstance(terminal_reason, str) or not terminal_reason:
        raise R1Error(f"{name}.audit.terminal_reason must be non-empty")

    trace = groups["trace"]
    _validate_trace(trace, f"{name}.trace")
    if trace["terminal_reason"] != terminal_reason:
        raise R1Error(f"{name}.trace terminal reason does not match audit")

    binding = groups["binding"]
    for key in ("group", "config"):
        value = _required(binding, key, f"{name}.binding")
        if not isinstance(value, str) or not value:
            raise R1Error(f"{name}.binding.{key} must be non-empty")
    exact_digest(
        _required(binding, "config_sha256", f"{name}.binding"),
        name=f"{name}.binding.config_sha256",
        length=64,
    )
    exact_digest(
        _required(binding, "checkpoint_sha256", f"{name}.binding"),
        name=f"{name}.binding.checkpoint_sha256",
        length=64,
    )
    if binding["checkpoint_sha256"] != provenance["checkpoint_sha256"]:
        raise R1Error(f"{name}.binding checkpoint hash does not match provenance")
    factor = groups["factor"]
    for key in ("group", "config"):
        value = _required(factor, key, f"{name}.factor")
        if not isinstance(value, str) or not value:
            raise R1Error(f"{name}.factor.{key} must be non-empty")
    exact_digest(_required(factor, "config_sha256", f"{name}.factor"), name=f"{name}.factor.config_sha256", length=64)
    if factor["config_sha256"] != binding["config_sha256"] or factor["group"] != binding["group"] or factor["config"] != binding["config"]:
        raise R1Error(f"{name}.factor binding disagrees with endpoint binding")
    for key in ("send_curriculum", "economics", "arm_tie"):
        _strict_bool(_required(factor, key, f"{name}.factor"), f"{name}.factor.{key}")

    denominators = groups["denominators"]
    for key, value in denominators.items():
        _strict_int(value, f"{name}.denominators.{key}", minimum=0)
    release = groups["release"]
    _validate_release(release, f"{name}.release")
    return dict(record)


def load_typed_records(path: Path | str) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.is_file():
        raise R1Error(f"missing endpoint artifact: {target}")
    payload_text = target.read_text(encoding="utf-8")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        payload = [
            json.loads(line)
            for line in payload_text.splitlines()
            if line.strip()
        ]
    if isinstance(payload, Mapping):
        payload = payload.get("records")
    if not isinstance(payload, list) or not payload:
        raise R1Error("endpoint artifact must contain a non-empty records list")
    rows = [
        _validate_record(_mapping(row, f"record[{i}]"), i)
        for i, row in enumerate(payload)
    ]
    return _validate_cross_record_bindings(rows)


def _validate_cross_record_bindings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        raise R1Error("endpoint artifact cannot be empty")
    pairs: set[tuple[int, int]] = set()
    binding = None
    topology = None
    for index, row in enumerate(rows):
        provenance = row["provenance"]
        pair = (provenance["seed"], provenance["env_id"])
        if pair in pairs:
            raise R1Error(f"duplicate endpoint identity seed/env_id: {pair}")
        pairs.add(pair)
        current_binding = (
            provenance["checkpoint_sha256"],
            provenance["config_sha256"],
            row["binding"]["checkpoint_sha256"],
            row["binding"]["config_sha256"],
            row["binding"]["group"],
            row["binding"]["config"],
        )
        if binding is None:
            binding = current_binding
        elif current_binding != binding:
            raise R1Error(f"cross-record binding mismatch at record {index}")
        current_topology = (
            row["topology"]["name"],
            row["topology"]["episode_count"],
            row["topology"]["first_episode_only"],
            row["topology"]["single_process"],
        )
        if topology is None:
            topology = current_topology
        elif current_topology != topology:
            raise R1Error(f"cross-record topology mismatch at record {index}")
    return rows


def _quantile(values: Sequence[float], q: float, name: str) -> float:
    if not values:
        raise R1Error(f"cannot compute {name}: no valid denominator")
    ordered = sorted(finite(value, name) for value in values)
    position = (len(ordered) - 1) * q
    lower, upper = int(math.floor(position)), int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _nested_metric(record: Mapping[str, Any], section: str, key: str) -> float | None:
    value = record[section][key]
    if isinstance(value, Mapping):
        return None
    return finite(value, f"{section}.{key}")


def aggregate_records(
    records: Iterable[Mapping[str, Any]],
    *,
    topology: str = "canonical16",
) -> dict[str, Any]:
    rows = [
        _validate_record(_mapping(row, f"record[{index}]"), index)
        for index, row in enumerate(records)
    ]
    rows = _validate_cross_record_bindings(rows)
    expected = canonical_topology(topology)["episodes"]
    if len(rows) != expected:
        raise R1Error(f"{topology} endpoint requires exactly {expected} records, got {len(rows)}")
    if any(row["topology"]["name"] != topology for row in rows):
        raise R1Error(f"records are not bound to requested topology {topology}")
    for section, key in CORE_METRICS:
        if not any(_nested_metric(row, section, key) is not None for row in rows):
            raise R1Error(f"all records are N/A for required metric {section}.{key}")

    result: dict[str, Any] = {
        "status": "STRICT_VALID",
        "record_count": len(rows),
        "goal_count": sum(row["task"]["goal"] for row in rows),
        "complete_count": sum(row["task"]["complete"] for row in rows),
        "crossing_while_holding_count": sum(
            row["task"]["crossing_while_holding"] for row in rows
        ),
        "send_ready_count": sum(row["send"]["send_ready"] for row in rows),
        "max_stage": max(row["task"]["max_stage"] for row in rows),
    }
    specs = {
        "hinge_at_first_crossing_p50": ("send", "hinge_at_first_crossing", 0.50),
        "pre_send_forward_displacement_p95": ("send", "pre_send_forward_displacement", 0.95),
        "pre_send_lateral_displacement_p95": ("send", "pre_send_lateral_displacement", 0.95),
        "pre_send_planar_displacement_p95": ("send", "pre_send_planar_displacement", 0.95),
        "pre_send_yaw_change_p95": ("send", "pre_send_yaw_change", 0.95),
        "arm_tangent_share_p50": ("task_space", "arm_tangent_share", 0.50),
        "arc_position_error_p95_m": ("task_space", "arc_position_error_m", 0.95),
        "arc_orientation_error_p95_rad": ("task_space", "arc_orientation_error_rad", 0.95),
        "along_handle_slip_p95_m": ("task_space", "along_handle_slip_m", 0.95),
        "positive_hinge_velocity_p95": ("smoothness", "positive_hinge_velocity", 0.95),
        "hinge_acceleration_p95": ("smoothness", "hinge_acceleration", 0.95),
        "hinge_jerk_p95": ("smoothness", "hinge_jerk", 0.95),
        "arm_action_rate_p95": ("smoothness", "arm_action_rate", 0.95),
        "arm_action_jerk_p95": ("smoothness", "arm_action_jerk", 0.95),
        "positive_income_ratio_p95": ("income", "positive_income_ratio", 0.95),
    }
    for output, (section, key, q) in specs.items():
        values = [
            value
            for row in rows
            if (value := _nested_metric(row, section, key)) is not None
        ]
        result[output] = (
            _quantile(values, q, output)
            if values
            else {"status": "N/A", "reason": f"no valid {section}.{key} denominator", "denominator": 0}
        )
    return result


def build_report(
    records: Sequence[Mapping[str, Any]] | Path | str,
    *,
    topology: str = "canonical16",
    output_path: Path | None = None,
) -> dict[str, Any]:
    rows = load_typed_records(records) if isinstance(records, (Path, str)) else list(records)
    aggregate = aggregate_records(rows, topology=topology)
    report = {
        "schema": REPORT_SCHEMA,
        "plan_id": PLAN_ID,
        "topology": topology,
        "status": "STRICT_VALID",
        "strict_status": "STRICT_VALID",
        "aggregate": aggregate,
        "record_count": len(rows),
    }
    if output_path is not None:
        write_json_no_overwrite(output_path, report)
    return report


def _require_blocked_r1_cli_opt_in() -> None:
    if "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in __import__("os").environ:
        print(
            "R1 execution is blocked by default; set BASE_V20_ALLOW_BLOCKED_R1_EXECUTION explicitly to run historical tooling",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _require_blocked_r1_cli_opt_in()
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path)
    parser.add_argument("--topology", default="canonical16")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_report(args.records, topology=args.topology, output_path=args.output)
