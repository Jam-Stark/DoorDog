"""Strict v16 three-seed M32+M33 report (schema v2).

The report consumes exactly six explicit artifact paths (one result and one
trace for each of seed 0/1/2). It preserves the v15 bucket validation, adds
required ``door_weight`` M32 mass buckets, and emits strict M33 endpoint
metrics. Malformed, incomplete, or partially populated telemetry fails before
any output is written.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final, Mapping, Sequence


MASS_BUCKETS: Final = (
    (80.0, 110.0, "[80,110)"),
    (110.0, 135.0, "[110,135)"),
    (135.0, 160.0, "[135,160]"),
)
PRE_CROSSING_COASTING_VELOCITY_THRESHOLD: Final = 0.1
PITCH_ROLL_USAGE_THRESHOLD: Final = 0.1
BODY_CONTACT_THRESHOLD: Final = 1.0


@dataclass(frozen=True, slots=True)
class V16ReportError(ValueError):
    """Invalid v16 report input or canonical reporter dependency."""

    message: str

    def __str__(self) -> str:
        return self.message


def _load_v15_reporter() -> ModuleType:
    """Load the canonical v15 reporter as the unchanged validation baseline."""
    source_path = Path(__file__).parents[1] / "v15" / "a2_piper_v15_bucket_report.py"
    spec = importlib.util.spec_from_file_location("a2_piper_v15_bucket_report", source_path)
    if spec is None or spec.loader is None:
        raise V16ReportError(f"cannot load canonical v15 reporter from {source_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V15 = _load_v15_reporter()
EXPECTED_SEEDS = V15.EXPECTED_SEEDS
EXPECTED_ENVS_PER_SEED = V15.EXPECTED_ENVS_PER_SEED
HINGE_BUCKETS = V15.HINGE_BUCKETS
HEIGHT_BUCKETS = V15.HEIGHT_BUCKETS
@dataclass(frozen=True, slots=True)
class EvalRecord:
    """Validated result metadata plus strict M33 terminal telemetry."""

    seed: int
    env_id: int
    hinge_force: float
    handle_height: float
    door_weight: float
    goal_reached: bool
    max_stage: int | None
    final_stage: int | None
    staging_standoff: float
    crossing_while_holding: bool | None
    hinge_at_crossing: float | None
    hinge_at_release: float | None
    root_x_at_release: float | None
    post_release_body_contact: bool | None
    post_release_body_force_max: float | None

    @property
    def attainment_stage(self) -> int:
        stage = self.max_stage if self.max_stage is not None else self.final_stage
        if stage is None:
            raise V16ReportError(
                f"seed{self.seed} env{self.env_id} has no stage outcome."
            )
        return stage


@dataclass(frozen=True, slots=True)
class TraceRecord:
    """Validated v15 trace payload plus exact v16 pre-crossing fields."""

    seed: int
    env_id: int
    stage: int
    hinge_force: float
    handle_height: float
    door_weight: float
    body_per_filter: tuple[float, ...]
    body_total: float
    arm_per_filter: tuple[float, ...]
    arm_total: float
    physical_base_command: tuple[float, ...]
    gripper_pos: tuple[float, ...]
    gripper_open_target: tuple[float, ...]
    both_contact: bool
    over_force: bool
    door_hinge_joint_vel: float
    root_x_ever_crossed: bool


def _required_nullable_bool(raw: Mapping[str, Any], name: str) -> bool | None:
    if name not in raw:
        raise V16ReportError(f"result is missing required field {name!r}.")
    value = raw[name]
    if value is not None and not isinstance(value, bool):
        raise V16ReportError(f"{name} must be bool or null; got {value!r}.")
    return value


def _required_nullable_finite(
    raw: Mapping[str, Any], name: str, *, nonnegative: bool = False
) -> float | None:
    if name not in raw:
        raise V16ReportError(f"result is missing required field {name!r}.")
    value = raw[name]
    if value is None:
        return None
    if not V15._finite(value) or (nonnegative and float(value) < 0.0):
        qualifier = "finite and non-negative" if nonnegative else "finite"
        raise V16ReportError(f"{name} must be {qualifier} or null; got {value!r}.")
    return float(value)


def normalize_result(raw: Mapping[str, Any], *, expected_seed: int) -> EvalRecord:
    """Parse one result record and require all v16 M33 terminal telemetry."""
    v15_record = V15.normalize_result(raw, expected_seed=expected_seed)
    door_weight = raw.get("door_weight")
    if not V15._finite(door_weight) or not 80.0 <= float(door_weight) <= 160.0:
        raise V16ReportError(
            f"door_weight must be finite in [80,160]; got {door_weight!r}."
        )
    crossing_while_holding = _required_nullable_bool(
        raw, "crossing_while_holding"
    )
    hinge_at_crossing = _required_nullable_finite(raw, "hinge_at_crossing")
    if (crossing_while_holding is None) != (hinge_at_crossing is None):
        raise V16ReportError(
            "crossing_while_holding and hinge_at_crossing must be both null or both non-null."
        )
    hinge_at_release = _required_nullable_finite(raw, "hinge_at_release")
    root_x_at_release = _required_nullable_finite(raw, "root_x_at_release")
    post_release_body_contact = _required_nullable_bool(
        raw, "post_release_body_contact"
    )
    post_release_body_force_max = _required_nullable_finite(
        raw, "post_release_body_force_max", nonnegative=True
    )
    release_values = (
        hinge_at_release,
        root_x_at_release,
        post_release_body_contact,
        post_release_body_force_max,
    )
    if any(value is None for value in release_values) != all(
        value is None for value in release_values
    ):
        raise V16ReportError(
            "hinge_at_release, root_x_at_release, post_release_body_contact, "
            "and post_release_body_force_max must be all null or all non-null."
        )
    return EvalRecord(
        seed=v15_record.seed,
        env_id=v15_record.env_id,
        hinge_force=v15_record.hinge_force,
        handle_height=v15_record.handle_height,
        door_weight=float(door_weight),
        goal_reached=v15_record.goal_reached,
        max_stage=v15_record.max_stage,
        final_stage=v15_record.final_stage,
        staging_standoff=v15_record.staging_standoff,
        crossing_while_holding=crossing_while_holding,
        hinge_at_crossing=hinge_at_crossing,
        hinge_at_release=hinge_at_release,
        root_x_at_release=root_x_at_release,
        post_release_body_contact=post_release_body_contact,
        post_release_body_force_max=post_release_body_force_max,
    )


def load_result(path: Path, *, expected_seed: int) -> list[EvalRecord]:
    """Load exactly one complete seed's v16 result records."""
    records = [
        normalize_result(raw, expected_seed=expected_seed)
        for raw in V15._load_json_records(path)
    ]
    if len(records) != EXPECTED_ENVS_PER_SEED:
        raise V16ReportError(
            f"seed{expected_seed} result must contain exactly 16 records; got {len(records)}."
        )
    ids = [record.env_id for record in records]
    if len(set(ids)) != EXPECTED_ENVS_PER_SEED or set(ids) != set(
        range(EXPECTED_ENVS_PER_SEED)
    ):
        raise V16ReportError(
            f"seed{expected_seed} result requires exactly env_id 0..15; got {sorted(ids)}."
        )
    return sorted(records, key=lambda record: record.env_id)


def mass_bucket(value: float) -> str:
    """Return the M32 mass bucket used by the full M32+M33 report."""
    return V15._bucket(value, MASS_BUCKETS, final_upper=True)


def normalize_trace(
    raw: Mapping[str, Any],
    *,
    expected_seed: int,
    result_by_env: Mapping[int, EvalRecord],
) -> TraceRecord | None:
    """Retain v15 trace validation and require exact v16 pre-crossing fields."""
    v15_trace = V15.normalize_trace(
        raw, expected_seed=expected_seed, result_by_env=result_by_env
    )
    if v15_trace is None:
        return None
    required_fields = (
        "door_weight",
        "both_contact",
        "over_force",
        "door_hinge_joint_vel",
        "root_x_ever_crossed",
    )
    missing = [field for field in required_fields if field not in raw]
    if missing:
        raise V16ReportError(
            f"seed{expected_seed} env{v15_trace.env_id} trace is missing {missing}."
        )
    trace_door_weight = raw["door_weight"]
    if not V15._finite(trace_door_weight) or not 80.0 <= float(trace_door_weight) <= 160.0:
        raise V16ReportError(
            f"trace door_weight must be finite in [80,160]; got {trace_door_weight!r}."
        )
    result_door_weight = result_by_env[v15_trace.env_id].door_weight
    if float(trace_door_weight) != result_door_weight:
        raise V16ReportError(
            f"trace door_weight must exactly match result door_weight {result_door_weight}; "
            f"got {trace_door_weight!r}."
        )
    both_contact = raw["both_contact"]
    over_force = raw["over_force"]
    if not isinstance(both_contact, bool) or not isinstance(over_force, bool):
        raise V16ReportError("trace both_contact and over_force must be bool.")
    hinge_velocity = raw["door_hinge_joint_vel"]
    if not V15._finite(hinge_velocity):
        raise V16ReportError(
            f"trace door_hinge_joint_vel must be finite; got {hinge_velocity!r}."
        )
    root_x_ever_crossed = raw["root_x_ever_crossed"]
    if not isinstance(root_x_ever_crossed, bool):
        raise V16ReportError("trace root_x_ever_crossed must be bool.")
    return TraceRecord(
        seed=v15_trace.seed,
        env_id=v15_trace.env_id,
        stage=v15_trace.stage,
        hinge_force=v15_trace.hinge_force,
        handle_height=v15_trace.handle_height,
        door_weight=float(trace_door_weight),
        body_per_filter=v15_trace.body_per_filter,
        body_total=v15_trace.body_total,
        arm_per_filter=v15_trace.arm_per_filter,
        arm_total=v15_trace.arm_total,
        physical_base_command=v15_trace.physical_base_command,
        gripper_pos=v15_trace.gripper_pos,
        gripper_open_target=v15_trace.gripper_open_target,
        both_contact=both_contact,
        over_force=over_force,
        door_hinge_joint_vel=float(hinge_velocity),
        root_x_ever_crossed=root_x_ever_crossed,
    )


def load_trace(
    path: Path,
    *,
    expected_seed: int,
    result_records: Sequence[EvalRecord],
) -> dict[int, list[TraceRecord]]:
    """Load strict first-episode stage2-5 traces for every result environment."""
    result_by_env = {record.env_id: record for record in result_records}
    selected: dict[int, list[TraceRecord]] = {env_id: [] for env_id in result_by_env}
    for raw in V15._load_json_records(Path(path)):
        trace = normalize_trace(
            raw, expected_seed=expected_seed, result_by_env=result_by_env
        )
        if trace is not None:
            selected[trace.env_id].append(trace)
    missing = [
        env_id
        for env_id, rows in selected.items()
        if not any(row.stage == 2 for row in rows)
    ]
    if missing:
        raise V16ReportError(
            f"seed{expected_seed} trace requires at least one stage2 record per env; "
            f"missing {missing}."
        )
    return selected


def _stats(values: Sequence[float]) -> dict[str, Any]:
    """Return explicit empty stats and finite deterministic quantiles."""
    if any(not V15._finite(value) for value in values):
        raise V16ReportError("M33 statistics received a non-finite value.")
    if not values:
        return {
            "n": 0,
            "min": None,
            "mean": None,
            "median": None,
            "p50": None,
            "p95": None,
            "max": None,
        }
    ordered = sorted(float(value) for value in values)
    return {
        "n": len(ordered),
        "min": ordered[0],
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "p50": (
            statistics.quantiles(ordered, n=100, method="inclusive")[49]
            if len(ordered) > 1
            else ordered[0]
        ),
        "p95": (
            statistics.quantiles(ordered, n=100, method="inclusive")[94]
            if len(ordered) > 1
            else ordered[0]
        ),
        "max": ordered[-1],
    }


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise V16ReportError(
            f"M33 rate requires 0 <= numerator <= denominator; got {numerator}/{denominator}."
        )
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def _usage_rate(values: Sequence[float]) -> dict[str, Any]:
    """Count signed pitch/roll commands whose absolute magnitude is strictly above 0.1."""
    return _rate(
        sum(abs(value) > PITCH_ROLL_USAGE_THRESHOLD for value in values),
        len(values),
    )


def _goal_summary(records: Sequence[EvalRecord]) -> dict[str, Any]:
    return _rate(
        sum(1 for record in records if record.goal_reached),
        len(records),
    )


def _trace_map_for_records(
    records: Sequence[EvalRecord],
    trace_sets: Mapping[int, Mapping[int, Sequence[TraceRecord]]],
) -> list[TraceRecord]:
    traces: list[TraceRecord] = []
    for record in records:
        try:
            rows = trace_sets[record.seed][record.env_id]
        except KeyError as exc:
            raise V16ReportError(
                f"missing trace rows for seed{record.seed} env{record.env_id}."
            ) from exc
        traces.extend(rows)
    return traces


def _build_m33_metrics(
    all_records: Sequence[EvalRecord],
    trace_sets: Mapping[int, Mapping[int, Sequence[TraceRecord]]],
) -> dict[str, Any]:
    canonical_records = [record for record in all_records if record.seed == 0]
    low_records = [
        record
        for record in all_records
        if V15.height_bucket(record.handle_height) == HEIGHT_BUCKETS[0][2]
    ]
    high_records = [
        record
        for record in all_records
        if V15.height_bucket(record.handle_height) == HEIGHT_BUCKETS[1][2]
    ]

    low_stage2 = [
        trace
        for trace in _trace_map_for_records(low_records, trace_sets)
        if trace.stage == 2
    ]
    high_stage2 = [
        trace
        for trace in _trace_map_for_records(high_records, trace_sets)
        if trace.stage == 2
    ]
    low_pitch = [trace.physical_base_command[3] for trace in low_stage2]
    high_pitch = [trace.physical_base_command[3] for trace in high_stage2]
    high_roll = [trace.physical_base_command[4] for trace in high_stage2]

    release_records = [
        record
        for record in all_records
        if record.hinge_at_release is not None
        and record.root_x_at_release is not None
        and record.post_release_body_contact is not None
        and record.post_release_body_force_max is not None
    ]
    release_forces = [record.post_release_body_force_max for record in release_records]
    contact_positive_forces = [
        record.post_release_body_force_max
        for record in release_records
        if record.post_release_body_contact
    ]

    pre_crossing = [
        trace
        for trace in _trace_map_for_records(all_records, trace_sets)
        if trace.stage in (3, 4) and not trace.root_x_ever_crossed
    ]
    bilateral_count = sum(trace.both_contact for trace in pre_crossing)
    coasting_count = sum(
        trace.door_hinge_joint_vel > PRE_CROSSING_COASTING_VELOCITY_THRESHOLD
        and not trace.both_contact
        for trace in pre_crossing
    )
    over_force_count = sum(trace.over_force for trace in pre_crossing)

    heavy_records = [record for record in all_records if record.door_weight >= 135.0]

    return {
        "goal": {
            "pooled": _goal_summary(all_records),
            "canonical": _goal_summary(canonical_records),
        },
        "low_height_stage2": {
            "pitch_usage": _usage_rate(low_pitch),
            "physical_pitch": _stats(low_pitch),
            "absolute_pitch": _stats([abs(value) for value in low_pitch]),
        },
        "high_height_stage2": {
            "pitch_usage": _usage_rate(high_pitch),
            "roll_usage": _usage_rate(high_roll),
            "physical_pitch": _stats(high_pitch),
            "absolute_pitch": _stats([abs(value) for value in high_pitch]),
            "physical_roll": _stats(high_roll),
            "absolute_roll": _stats([abs(value) for value in high_roll]),
            "goal": _goal_summary(high_records),
        },
        "hinge_at_release": _stats(
            [record.hinge_at_release for record in release_records]
        ),
        "root_x_at_release": _stats(
            [record.root_x_at_release for record in release_records]
        ),
        "post_release_body_contact": {
            "env_count": sum(
                bool(record.post_release_body_contact) for record in release_records
            ),
            "rate": _rate(
                sum(bool(record.post_release_body_contact) for record in release_records),
                len(release_records),
            ),
        },
        "post_release_body_force": {
            "all": _stats(release_forces),
            "contact_positive": _stats(contact_positive_forces),
        },
        "pre_crossing_stage3_stage4": {
            "scope": "stage3_stage4 and not root_x_ever_crossed",
            "coasting_velocity_threshold": PRE_CROSSING_COASTING_VELOCITY_THRESHOLD,
            "bilateral_rate": _rate(bilateral_count, len(pre_crossing)),
            "coasting_rate": _rate(coasting_count, len(pre_crossing)),
            "over_force_rate": _rate(over_force_count, len(pre_crossing)),
            "hinge_velocity": _stats(
                [trace.door_hinge_joint_vel for trace in pre_crossing]
            ),
        },
        "heavy_mass_goal": _goal_summary(heavy_records),
        "crossing_while_holding": {
            "pooled": _rate(
                sum(bool(record.crossing_while_holding) for record in all_records),
                len(all_records),
            ),
            "canonical": _rate(
                sum(bool(record.crossing_while_holding) for record in canonical_records),
                len(canonical_records),
            ),
        },
    }


def build_report(
    result_sets: Mapping[int, Sequence[EvalRecord]],
    trace_sets: Mapping[int, Mapping[int, Sequence[TraceRecord]]],
) -> dict[str, Any]:
    """Build v15 buckets, M32 mass buckets, and M33 metrics for 48 records."""
    if set(result_sets) != set(EXPECTED_SEEDS) or set(trace_sets) != set(
        EXPECTED_SEEDS
    ):
        raise V16ReportError("report requires exactly seed0, seed1, and seed2 inputs.")
    all_records = [record for seed in EXPECTED_SEEDS for record in result_sets[seed]]
    if len(all_records) != 48 or len(
        {(record.seed, record.env_id) for record in all_records}
    ) != 48:
        raise V16ReportError("report requires 48 unique (seed, env_id) result records.")

    groups: dict[str, list[EvalRecord]] = {
        label: [] for *_bounds, label in HINGE_BUCKETS
    }
    groups.update({label: [] for *_bounds, label in HEIGHT_BUCKETS})
    groups.update({label: [] for *_bounds, label in MASS_BUCKETS})
    for record in all_records:
        groups[V15.hinge_bucket(record.hinge_force)].append(record)
        groups[V15.height_bucket(record.handle_height)].append(record)
        groups[mass_bucket(record.door_weight)].append(record)

    summaries: dict[str, Any] = {}
    for label, records in groups.items():
        traces = {
            (record.seed, record.env_id): list(
                trace_sets[record.seed][record.env_id]
            )
            for record in records
        }
        summaries[label] = V15.summarize_bucket(
            records,
            traces,
            high_handle=label == HEIGHT_BUCKETS[1][2],
        )
    m33_metrics = _build_m33_metrics(all_records, trace_sets)
    return {
        "schema": "a2_piper_v16_m33_bucket_report_v2",
        "schema_version": 2,
        "record_count": 48,
        "seed_roles": {
            "seed0": "canonical",
            "seed1": "supplementary",
            "seed2": "supplementary",
        },
        "bucket_rules": {
            "hinge_force": [label for *_bounds, label in HINGE_BUCKETS],
            "handle_height": [label for *_bounds, label in HEIGHT_BUCKETS],
            "door_weight": [label for *_bounds, label in MASS_BUCKETS],
        },
        "by_bucket": summaries,
        "m33": m33_metrics,
        "by_seed": {
            f"seed{seed}": V15._attainment(result_sets[seed])
            for seed in EXPECTED_SEEDS
        },
    }


def write_outputs(
    report: Mapping[str, Any], output_dir: Path, input_paths: Mapping[str, Path]
) -> tuple[Path, Path, Path]:
    """Write the complete v16 M32+M33 schema-v2 JSON/CSV/Markdown trio."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = "a2_piper_v16_bucket_report"
    json_path, csv_path, md_path = (
        output_dir / f"{stem}.{suffix}" for suffix in ("json", "csv", "md")
    )
    payload = dict(report)
    payload["explicit_input_files"] = {
        key: str(path) for key, path in input_paths.items()
    }
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows = V15._rows(report)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# A2_Piper v16 M32+M33 report (schema v2)",
        "",
        "Seed 0 is canonical; seeds 1 and 2 are supplementary. Inputs are explicit CLI paths.",
        "CSV contains legacy and M32 mass buckets; complete M33 endpoint metrics are included below and in JSON.",
        "",
        "| Bucket | N | Goal | Stage 3 | Stage 4 | Stage 5 | Body contact | Body share | Arm share | j8 open-limit |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {bucket} | {n} | {goal_count} ({goal_rate}) | {stage3_rate} | "
            "{stage4_rate} | {stage5_rate} | {body_contact_rate} | {body_share} | "
            "{arm_share} | {j8_open_limit_rate} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## M33 endpoint metrics",
            "",
            "```json",
            json.dumps(report["m33"], indent=2, sort_keys=True),
            "```",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse six explicit inputs for the v16 M32+M33 schema-v2 report."""
    parser = argparse.ArgumentParser(
        description="Build the strict A2_Piper v16 M32+M33 report (schema v2)."
    )
    for seed in EXPECTED_SEEDS:
        parser.add_argument(f"--seed{seed}-result", type=Path, required=True)
        parser.add_argument(f"--seed{seed}-trace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the strict v16 M32+M33 schema-v2 report over six artifacts."""
    args = parse_args(argv)
    result_sets: dict[int, list[EvalRecord]] = {}
    trace_sets: dict[int, dict[int, list[TraceRecord]]] = {}
    input_paths: dict[str, Path] = {}
    for seed in EXPECTED_SEEDS:
        result_path = getattr(args, f"seed{seed}_result")
        trace_path = getattr(args, f"seed{seed}_trace")
        result_sets[seed] = load_result(result_path, expected_seed=seed)
        trace_sets[seed] = load_trace(
            trace_path, expected_seed=seed, result_records=result_sets[seed]
        )
        input_paths[f"seed{seed}_result"] = result_path
        input_paths[f"seed{seed}_trace"] = trace_path
    paths = write_outputs(build_report(result_sets, trace_sets), args.output_dir, input_paths)
    print(f"v16 M32+M33 JSON (schema v2): {paths[0]}")
    print(f"v16 M32+M33 CSV (schema v2): {paths[1]}")
    print(f"v16 M32+M33 Markdown (schema v2): {paths[2]}")
    return 0


load_result_input = load_result
load_trace_input = load_trace
build_bucket_report = build_report
write_report_outputs = write_outputs


if __name__ == "__main__":
    sys.exit(main())
