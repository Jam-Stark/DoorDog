"""Strict v15 three-seed bucket report.

The report consumes exactly six explicit artifact paths (one result and one
trace for each of seed 0/1/2).  It intentionally has no directory discovery or
schema fallback: malformed or incomplete evidence fails before any output is
written.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPECTED_SEEDS = (0, 1, 2)
EXPECTED_ENVS_PER_SEED = 16
HINGE_BUCKETS = ((2.5, 5.5, "[2.5,5.5)"), (5.5, 8.5, "[5.5,8.5)"), (8.5, 12.0, "[8.5,12.0]"))
HEIGHT_BUCKETS = ((0.80, 0.95, "[0.80,0.95)"), (0.95, 1.10, "[0.95,1.10]"))
BODY_FILTER_COUNT = 13
ARM_FILTER_COUNT = 10
# float32(1.10) serializes as 1.100000023841858.  Keep this
# representational allowance explicit and narrow; it is only applied to the
# inclusive final height edge and is not a general range clamp.
HEIGHT_FINAL_UPPER_TOLERANCE = 1.0e-7


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _finite_nonnegative(value: Any, field_name: str) -> float:
    if not _finite(value) or float(value) < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative; got {value!r}.")
    return float(value)


def _vector(value: Any, length: int, field_name: str, *, nonnegative: bool = False) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"{field_name} must have length {length}; got {value!r}.")
    values = tuple(
        _finite_nonnegative(item, f"{field_name}[{index}]") if nonnegative else float(item)
        for index, item in enumerate(value)
    )
    if not nonnegative and any(not _finite(item) for item in value):
        raise ValueError(f"{field_name} must contain only finite values; got {value!r}.")
    return values


def _records(payload: Any, path: Path) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, Mapping):
        records = next((payload[name] for name in ("records", "per_env_records", "results") if isinstance(payload.get(name), list)), None)
        if records is None:
            raise ValueError(f"{path} must contain records/per_env_records/results list.")
    else:
        raise ValueError(f"{path} must contain a JSON list or record container.")
    if any(not isinstance(record, Mapping) for record in records):
        raise ValueError(f"{path} contains a non-object record.")
    return records


def _load_json_records(path: Path) -> list[Mapping[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"explicit input does not exist: {path}")
    try:
        if path.suffix.lower() == ".jsonl":
            payload = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON input {path}: {exc}") from exc
    return _records(payload, path)


def _stage(raw: Any, field_name: str) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 5:
        raise ValueError(f"{field_name} must be an integer stage in [0,5] or null; got {raw!r}.")
    return raw


@dataclass(frozen=True)
class EvalRecord:
    seed: int
    env_id: int
    hinge_force: float
    handle_height: float
    goal_reached: bool
    max_stage: int | None
    final_stage: int | None
    staging_standoff: float

    @property
    def attainment_stage(self) -> int:
        stage = self.max_stage if self.max_stage is not None else self.final_stage
        if stage is None:
            raise ValueError(f"seed{self.seed} env{self.env_id} has no stage outcome.")
        return stage


@dataclass(frozen=True)
class TraceRecord:
    seed: int
    env_id: int
    stage: int
    hinge_force: float
    handle_height: float
    body_per_filter: tuple[float, ...]
    body_total: float
    arm_per_filter: tuple[float, ...]
    arm_total: float
    physical_base_command: tuple[float, ...]
    gripper_pos: tuple[float, ...]
    gripper_open_target: tuple[float, ...]


def normalize_result(raw: Mapping[str, Any], *, expected_seed: int) -> EvalRecord:
    seed = raw.get("seed")
    env_id = raw.get("env_id")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed != expected_seed:
        raise ValueError(f"result seed identity must be {expected_seed}; got {seed!r}.")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < EXPECTED_ENVS_PER_SEED:
        raise ValueError(f"result env_id must be an integer in 0..15; got {env_id!r}.")
    hinge = raw.get("door_hinge_drive_max_force")
    height = raw.get("door_handle_height")
    if not _finite(hinge) or not 2.5 <= float(hinge) <= 12.0:
        raise ValueError(f"door_hinge_drive_max_force must be finite in [2.5,12.0]; got {hinge!r}.")
    if not _finite(height) or not 0.80 <= float(height) <= 1.10 + HEIGHT_FINAL_UPPER_TOLERANCE:
        raise ValueError(f"door_handle_height must be finite in [0.80,1.10]; got {height!r}.")
    goal = raw.get("goal_reached")
    if not isinstance(goal, bool):
        raise ValueError(f"goal_reached must be bool; got {goal!r}.")
    max_stage = _stage(raw.get("max_stage"), "max_stage")
    final_stage = _stage(raw.get("final_stage"), "final_stage")
    if max_stage is None and final_stage is None:
        raise ValueError("result requires max_stage or final_stage.")
    if max_stage is not None and final_stage is not None and final_stage > max_stage:
        raise ValueError("final_stage cannot exceed max_stage.")
    standoff = raw.get("stage0_to1_staging_standoff")
    if not _finite(standoff):
        raise ValueError(f"stage0_to1_staging_standoff must be finite; got {standoff!r}.")
    return EvalRecord(expected_seed, env_id, float(hinge), float(height), goal, max_stage, final_stage, float(standoff))


def load_result(path: Path, *, expected_seed: int) -> list[EvalRecord]:
    records = [normalize_result(raw, expected_seed=expected_seed) for raw in _load_json_records(Path(path))]
    if len(records) != EXPECTED_ENVS_PER_SEED:
        raise ValueError(f"seed{expected_seed} result must contain exactly 16 records; got {len(records)}.")
    ids = [record.env_id for record in records]
    if len(set(ids)) != EXPECTED_ENVS_PER_SEED or set(ids) != set(range(EXPECTED_ENVS_PER_SEED)):
        raise ValueError(f"seed{expected_seed} result requires exactly env_id 0..15; got {sorted(ids)}.")
    return sorted(records, key=lambda record: record.env_id)


def _trace_metadata(raw: Mapping[str, Any], name: str, expected: float) -> float:
    value = raw.get(name)
    if not _finite(value) or float(value) != expected:
        raise ValueError(f"trace {name} must equal result metadata {expected}; got {value!r}.")
    return float(value)


def normalize_trace(raw: Mapping[str, Any], *, expected_seed: int, result_by_env: Mapping[int, EvalRecord]) -> TraceRecord | None:
    active = raw.get("first_episode_active")
    episode_index = raw.get("episode_index")
    if not isinstance(active, bool) or isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
        raise ValueError("trace requires bool first_episode_active and non-negative integer episode_index.")
    if not active or episode_index != 0:
        return None
    env_id = raw.get("env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in result_by_env:
        raise ValueError(f"trace env_id must identify a result env 0..15; got {env_id!r}.")
    trace_seed = raw.get("seed", expected_seed)
    if isinstance(trace_seed, bool) or not isinstance(trace_seed, int) or trace_seed != expected_seed:
        raise ValueError(f"trace seed identity must be {expected_seed}; got {trace_seed!r}.")
    stage = raw.get("stage_buf")
    if isinstance(stage, bool) or not isinstance(stage, int) or stage not in (2, 3, 4, 5):
        raise ValueError(f"trace stage_buf must be integer 2..5; got {stage!r}.")
    result = result_by_env[env_id]
    hinge = _trace_metadata(raw, "door_hinge_drive_max_force", result.hinge_force)
    height = _trace_metadata(raw, "door_handle_height", result.handle_height)
    body_per = _vector(raw.get("door_body_panel_normal_force_per_filter"), BODY_FILTER_COUNT, "door_body_panel_normal_force_per_filter", nonnegative=True)
    arm_per = _vector(raw.get("door_arm_panel_normal_force_per_filter"), ARM_FILTER_COUNT, "door_arm_panel_normal_force_per_filter", nonnegative=True)
    body_total = _finite_nonnegative(raw.get("door_body_panel_normal_force_total"), "door_body_panel_normal_force_total")
    arm_total = _finite_nonnegative(raw.get("door_arm_panel_normal_force_total"), "door_arm_panel_normal_force_total")
    if not math.isclose(body_total, sum(body_per), rel_tol=1e-5, abs_tol=1e-6):
        raise ValueError("door body total must equal the non-cancelling per-filter force sum.")
    if not math.isclose(arm_total, sum(arm_per), rel_tol=1e-5, abs_tol=1e-6):
        raise ValueError("door arm total must equal the non-cancelling per-filter force sum.")
    command = _vector(raw.get("physical_base_command"), 5, "physical_base_command")
    gripper_pos = _vector(raw.get("arm_j7_j8_pos"), 2, "arm_j7_j8_pos")
    open_target = _vector(raw.get("arm_j7_j8_open_target"), 2, "arm_j7_j8_open_target")
    return TraceRecord(expected_seed, env_id, stage, hinge, height, body_per, body_total, arm_per, arm_total, command, gripper_pos, open_target)


def load_trace(path: Path, *, expected_seed: int, result_records: Sequence[EvalRecord]) -> dict[int, list[TraceRecord]]:
    result_by_env = {record.env_id: record for record in result_records}
    selected: dict[int, list[TraceRecord]] = {env_id: [] for env_id in result_by_env}
    for raw in _load_json_records(Path(path)):
        trace = normalize_trace(raw, expected_seed=expected_seed, result_by_env=result_by_env)
        if trace is not None:
            selected[trace.env_id].append(trace)
    missing = [env_id for env_id, rows in selected.items() if not any(row.stage == 2 for row in rows)]
    if missing:
        raise ValueError(f"seed{expected_seed} trace requires at least one stage2 record per env; missing {missing}.")
    return selected


def _bucket(
    value: float,
    rules: Sequence[tuple[float, float, str]],
    *,
    final_upper: bool,
    final_upper_tolerance: float = 0.0,
) -> str:
    for index, (lower, upper, label) in enumerate(rules):
        if lower <= value < upper or (
            final_upper
            and index == len(rules) - 1
            and lower <= value <= upper + final_upper_tolerance
        ):
            return label
    raise ValueError(f"value {value} does not belong to a report bucket.")


def hinge_bucket(value: float) -> str:
    return _bucket(value, HINGE_BUCKETS, final_upper=True)


def height_bucket(value: float) -> str:
    return _bucket(
        value,
        HEIGHT_BUCKETS,
        final_upper=True,
        final_upper_tolerance=HEIGHT_FINAL_UPPER_TOLERANCE,
    )


def _stats(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "min": None, "mean": None, "median": None, "p50": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {
        "n": len(values),
        "min": min(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p50": statistics.quantiles(ordered, n=100, method="inclusive")[49] if len(values) > 1 else ordered[0],
        "p95": statistics.quantiles(ordered, n=100, method="inclusive")[94] if len(values) > 1 else ordered[0],
        "max": max(values),
    }


def _attainment(records: Sequence[EvalRecord]) -> dict[str, Any]:
    n = len(records)
    stages = [record.attainment_stage for record in records]
    return {
        "n": n,
        "goal_count": sum(record.goal_reached for record in records),
        "goal_rate": (sum(item.goal_reached for item in records) / n) if n else None,
        "stage3_count": sum(stage >= 3 for stage in stages),
        "stage4_count": sum(stage >= 4 for stage in stages),
        "stage5_count": sum(stage >= 5 for stage in stages),
        "stage3_rate": (sum(stage >= 3 for stage in stages) / n) if n else None,
        "stage4_rate": (sum(stage >= 4 for stage in stages) / n) if n else None,
        "stage5_rate": (sum(stage >= 5 for stage in stages) / n) if n else None,
    }


def summarize_bucket(
    records: Sequence[EvalRecord],
    traces: Mapping[tuple[int, int], Sequence[TraceRecord]],
    *,
    high_handle: bool,
) -> dict[str, Any]:
    all_steps = [
        trace
        for record in records
        for trace in traces[(record.seed, record.env_id)]
        if trace.stage in (3, 4, 5)
    ]
    body_values = [trace.body_total for trace in all_steps]
    positive_values = [trace.body_total for trace in all_steps if trace.body_total > 1.0]
    body_numerator = sum(trace.body_total for trace in all_steps)
    arm_numerator = sum(trace.arm_total for trace in all_steps)
    share_denominator = body_numerator + arm_numerator
    share_valid = share_denominator > 0.0
    j8_denominator = len(all_steps)
    j8_numerator = sum(abs(trace.gripper_pos[1] - trace.gripper_open_target[1]) <= 1.0e-4 for trace in all_steps)
    result: dict[str, Any] = {
        **_attainment(records),
        "body_contact_usage": {"numerator": sum(value > 1.0 for value in body_values), "denominator": len(body_values), "rate": (sum(value > 1.0 for value in body_values) / len(body_values)) if body_values else None},
        "body_force": {"all_sample": _stats(body_values), "contact_positive": _stats(positive_values)},
        "pooled_panel_force": {"body_numerator": body_numerator, "arm_numerator": arm_numerator, "denominator": share_denominator, "share_valid": share_valid, "body_share": (body_numerator / share_denominator) if share_valid else None, "arm_share": (arm_numerator / share_denominator) if share_valid else None},
        "staging_standoff": _stats([record.staging_standoff for record in records]),
        "j8_open_limit": {"numerator": j8_numerator, "denominator": j8_denominator, "rate": (j8_numerator / j8_denominator) if j8_denominator else None},
    }
    high_steps = [
        trace
        for record in records
        for trace in traces[(record.seed, record.env_id)]
        if trace.stage == 2
    ] if high_handle else []
    pitch = [trace.physical_base_command[3] for trace in high_steps]
    roll = [trace.physical_base_command[4] for trace in high_steps]
    result["high_handle_physical_pitch"] = _stats(pitch)
    result["high_handle_physical_roll"] = _stats(roll)
    result["high_handle_absolute_pitch"] = _stats([abs(value) for value in pitch])
    result["high_handle_absolute_roll"] = _stats([abs(value) for value in roll])
    result["high_handle_pitch_usage"] = {"numerator": sum(abs(value) >= 0.2 for value in pitch), "denominator": len(pitch), "rate": (sum(abs(value) >= 0.2 for value in pitch) / len(pitch)) if pitch else None}
    result["high_handle_roll_usage"] = {"numerator": sum(abs(value) >= 0.2 for value in roll), "denominator": len(roll), "rate": (sum(abs(value) >= 0.2 for value in roll) / len(roll)) if roll else None}
    return result


def build_report(result_sets: Mapping[int, Sequence[EvalRecord]], trace_sets: Mapping[int, Mapping[int, Sequence[TraceRecord]]]) -> dict[str, Any]:
    if set(result_sets) != set(EXPECTED_SEEDS) or set(trace_sets) != set(EXPECTED_SEEDS):
        raise ValueError("report requires exactly seed0, seed1, and seed2 inputs.")
    all_records = [record for seed in EXPECTED_SEEDS for record in result_sets[seed]]
    if len(all_records) != 48 or len({(record.seed, record.env_id) for record in all_records}) != 48:
        raise ValueError("report requires 48 unique (seed, env_id) result records.")
    groups: dict[str, list[EvalRecord]] = {label: [] for *_bounds, label in HINGE_BUCKETS}
    groups.update({label: [] for *_bounds, label in HEIGHT_BUCKETS})
    for record in all_records:
        groups[hinge_bucket(record.hinge_force)].append(record)
        groups[height_bucket(record.handle_height)].append(record)
    summaries: dict[str, Any] = {}
    for label, records in groups.items():
        traces: dict[tuple[int, int], list[TraceRecord]] = {}
        for record in records:
            traces[(record.seed, record.env_id)] = list(
                trace_sets[record.seed][record.env_id]
            )
        summaries[label] = summarize_bucket(records, traces, high_handle=label == HEIGHT_BUCKETS[1][2])
    return {
        "schema": "a2_piper_v15_bucket_report_v1",
        "record_count": 48,
        "seed_roles": {"seed0": "canonical", "seed1": "supplementary", "seed2": "supplementary"},
        "bucket_rules": {"hinge_force": [label for *_bounds, label in HINGE_BUCKETS], "handle_height": [label for *_bounds, label in HEIGHT_BUCKETS]},
        "by_bucket": summaries,
        "by_seed": {f"seed{seed}": _attainment(result_sets[seed]) for seed in EXPECTED_SEEDS},
    }


def _rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for bucket, summary in report["by_bucket"].items():
        rows.append({
            "bucket": bucket,
            "n": summary["n"],
            "goal_count": summary["goal_count"],
            "goal_rate": summary["goal_rate"],
            "stage3_rate": summary["stage3_rate"],
            "stage4_rate": summary["stage4_rate"],
            "stage5_rate": summary["stage5_rate"],
            "body_contact_numerator": summary["body_contact_usage"]["numerator"],
            "body_contact_denominator": summary["body_contact_usage"]["denominator"],
            "body_contact_rate": summary["body_contact_usage"]["rate"],
            "body_share": summary["pooled_panel_force"]["body_share"],
            "arm_share": summary["pooled_panel_force"]["arm_share"],
            "j8_open_limit_rate": summary["j8_open_limit"]["rate"],
        })
    return rows


def write_outputs(report: Mapping[str, Any], output_dir: Path, input_paths: Mapping[str, Path]) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = "a2_piper_v15_bucket_report"
    json_path, csv_path, md_path = (output_dir / f"{stem}.{suffix}" for suffix in ("json", "csv", "md"))
    payload = dict(report)
    payload["explicit_input_files"] = {key: str(path) for key, path in input_paths.items()}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = _rows(report)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# A2_Piper v15 M27 bucket report",
        "",
        "Seed 0 is canonical; seeds 1 and 2 are supplementary. Inputs are explicit CLI paths.",
        "",
        "| Bucket | N | Goal | Stage 3 | Stage 4 | Stage 5 | Body contact | Body share | Arm share | j8 open-limit |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append("| {bucket} | {n} | {goal_count} ({goal_rate}) | {stage3_rate} | {stage4_rate} | {stage5_rate} | {body_contact_rate} | {body_share} | {arm_share} | {j8_open_limit_rate} |".format(**row))
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the strict A2_Piper v15 three-seed bucket report.")
    for seed in EXPECTED_SEEDS:
        parser.add_argument(f"--seed{seed}-result", type=Path, required=True)
        parser.add_argument(f"--seed{seed}-trace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result_sets: dict[int, list[EvalRecord]] = {}
    trace_sets: dict[int, dict[int, list[TraceRecord]]] = {}
    input_paths: dict[str, Path] = {}
    for seed in EXPECTED_SEEDS:
        result_path = getattr(args, f"seed{seed}_result")
        trace_path = getattr(args, f"seed{seed}_trace")
        result_sets[seed] = load_result(result_path, expected_seed=seed)
        trace_sets[seed] = load_trace(trace_path, expected_seed=seed, result_records=result_sets[seed])
        input_paths[f"seed{seed}_result"] = result_path
        input_paths[f"seed{seed}_trace"] = trace_path
    report = build_report(result_sets, trace_sets)
    paths = write_outputs(report, args.output_dir, input_paths)
    print(f"v15 bucket JSON: {paths[0]}")
    print(f"v15 bucket CSV: {paths[1]}")
    print(f"v15 bucket Markdown: {paths[2]}")
    return 0


# Explicit aliases make the standalone implementation easy to exercise from
# no-simulation tests without changing the CLI contract.
load_result_input = load_result
load_trace_input = load_trace
build_bucket_report = build_report
write_report_outputs = write_outputs


if __name__ == "__main__":
    sys.exit(main())
