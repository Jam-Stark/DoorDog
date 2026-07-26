"""Strict v17 M38 report layered on the unchanged v16 schema.

The reporter retains every v16 bucket and M33 validation, then adds continuous
mass-bucket metrics from exact environment telemetry: episode length,
post-release peak body force, stage3+4 opening duration, episode reward
decomposition, and post-release root-X displacement.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final, Mapping, Sequence


SCHEMA: Final = "a2_piper_v17_m38_bucket_report_v1"


def _load_v16_reporter() -> ModuleType:
    source_path = Path(__file__).parents[1] / "v16" / "a2_piper_v16_bucket_report.py"
    spec = importlib.util.spec_from_file_location(
        "a2_piper_v16_bucket_report_for_v17", source_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical v16 reporter from {source_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V16 = _load_v16_reporter()
V17ReportError = V16.V16ReportError
EXPECTED_SEEDS = V16.EXPECTED_SEEDS
EXPECTED_ENVS_PER_SEED = V16.EXPECTED_ENVS_PER_SEED
MASS_BUCKETS = V16.MASS_BUCKETS


@dataclass(frozen=True, slots=True)
class EvalRecord(V16.EvalRecord):
    """v16 result record plus exact M38 terminal fields."""

    episode_length_buf: int
    control_dt: float
    root_pos_rel: tuple[float, float, float]
    reward_episode_sums: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class TraceRecord(V16.TraceRecord):
    """v16 trace record plus exact M38 per-step fields."""

    step_index: int
    episode_length_buf: int
    control_dt: float
    root_pos_rel: tuple[float, float, float]
    reward_episode_sums: Mapping[str, float]


def _positive_int(raw: Mapping[str, Any], name: str) -> int:
    if name not in raw:
        raise V17ReportError(f"record is missing required field {name!r}.")
    value = raw[name]
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise V17ReportError(f"{name} must be a positive int; got {value!r}.")
    return value


def _nonnegative_int(raw: Mapping[str, Any], name: str) -> int:
    if name not in raw:
        raise V17ReportError(f"record is missing required field {name!r}.")
    value = raw[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise V17ReportError(f"{name} must be a non-negative int; got {value!r}.")
    return value


def _positive_finite(raw: Mapping[str, Any], name: str) -> float:
    if name not in raw:
        raise V17ReportError(f"record is missing required field {name!r}.")
    value = raw[name]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise V17ReportError(f"{name} must be finite and positive; got {value!r}.")
    return float(value)


def _finite_vector3(raw: Mapping[str, Any], name: str) -> tuple[float, float, float]:
    if name not in raw:
        raise V17ReportError(f"record is missing required field {name!r}.")
    value = raw[name]
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(not V16.V15._finite(component) for component in value)
    ):
        raise V17ReportError(f"{name} must contain exactly three finite values; got {value!r}.")
    return tuple(float(component) for component in value)


def _reward_sums(raw: Mapping[str, Any]) -> dict[str, float]:
    name = "reward_episode_sums"
    if name not in raw:
        raise V17ReportError(f"record is missing required field {name!r}.")
    if (
        "reward_episode_sums_unit" in raw
        and raw["reward_episode_sums_unit"] != "episode-sum"
    ):
        raise V17ReportError(
            "reward_episode_sums_unit must be exactly 'episode-sum' when present."
        )
    value = raw[name]
    if not isinstance(value, Mapping) or not value:
        raise V17ReportError("reward_episode_sums must be a non-empty mapping.")
    if any(not isinstance(key, str) or not key for key in value):
        raise V17ReportError("reward_episode_sums keys must be non-empty strings.")
    if any(not V16.V15._finite(component) for component in value.values()):
        raise V17ReportError("reward_episode_sums values must all be finite.")
    return {key: float(component) for key, component in value.items()}


def normalize_result(raw: Mapping[str, Any], *, expected_seed: int) -> EvalRecord:
    base = V16.normalize_result(raw, expected_seed=expected_seed)
    return EvalRecord(
        **asdict(base),
        episode_length_buf=_positive_int(raw, "episode_length_buf"),
        control_dt=_positive_finite(raw, "control_dt"),
        root_pos_rel=_finite_vector3(raw, "root_pos_rel"),
        reward_episode_sums=_reward_sums(raw),
    )


def load_result(path: Path, *, expected_seed: int) -> list[EvalRecord]:
    records = [
        normalize_result(raw, expected_seed=expected_seed)
        for raw in V16.V15._load_json_records(path)
    ]
    if len(records) != EXPECTED_ENVS_PER_SEED:
        raise V17ReportError(
            f"seed{expected_seed} result must contain exactly 16 records; got {len(records)}."
        )
    ids = [record.env_id for record in records]
    if set(ids) != set(range(EXPECTED_ENVS_PER_SEED)) or len(set(ids)) != len(ids):
        raise V17ReportError(
            f"seed{expected_seed} result requires exactly env_id 0..15; got {sorted(ids)}."
        )
    return sorted(records, key=lambda record: record.env_id)


def normalize_trace(
    raw: Mapping[str, Any],
    *,
    expected_seed: int,
    result_by_env: Mapping[int, EvalRecord],
) -> TraceRecord | None:
    base = V16.normalize_trace(
        raw, expected_seed=expected_seed, result_by_env=result_by_env
    )
    if base is None:
        return None
    episode_length = _positive_int(raw, "episode_length_buf")
    control_dt = _positive_finite(raw, "control_dt")
    root_pos_rel = _finite_vector3(raw, "root_pos_rel")
    reward_sums = _reward_sums(raw)
    result = result_by_env[base.env_id]
    if control_dt != result.control_dt:
        raise V17ReportError(
            f"seed{expected_seed} env{base.env_id} trace control_dt must exactly "
            f"match result control_dt {result.control_dt}; got {control_dt}."
        )
    if set(reward_sums) != set(result.reward_episode_sums):
        raise V17ReportError(
            f"seed{expected_seed} env{base.env_id} trace reward keys must exactly "
            "match the result reward keys."
        )
    return TraceRecord(
        **asdict(base),
        step_index=_nonnegative_int(raw, "step_index"),
        episode_length_buf=episode_length,
        control_dt=control_dt,
        root_pos_rel=root_pos_rel,
        reward_episode_sums=reward_sums,
    )


def load_trace(
    path: Path,
    *,
    expected_seed: int,
    result_records: Sequence[EvalRecord],
) -> dict[int, list[TraceRecord]]:
    result_by_env = {record.env_id: record for record in result_records}
    selected: dict[int, list[TraceRecord]] = {env_id: [] for env_id in result_by_env}
    for raw in V16.V15._load_json_records(path):
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
        raise V17ReportError(
            f"seed{expected_seed} trace requires at least one stage2 record per env; "
            f"missing {missing}."
        )
    for env_id, rows in selected.items():
        result = result_by_env[env_id]
        if rows[0].stage != 2:
            raise V17ReportError(
                f"seed{expected_seed} env{env_id} trace must start in stage2."
            )
        for name, values in (
            ("step_index", [row.step_index for row in rows]),
            (
                "episode_length_buf",
                [row.episode_length_buf for row in rows],
            ),
        ):
            discontinuity = next(
                (
                    (previous, current)
                    for previous, current in zip(values, values[1:])
                    if current != previous + 1
                ),
                None,
            )
            if discontinuity is not None:
                raise V17ReportError(
                    f"seed{expected_seed} env{env_id} trace {name} must be unique, "
                    "ordered, and contiguous; "
                    f"got adjacent values {discontinuity}."
                )
        if rows[-1].episode_length_buf != result.episode_length_buf:
            raise V17ReportError(
                f"seed{expected_seed} env{env_id} terminal trace episode_length_buf "
                f"must match result value {result.episode_length_buf}; "
                f"got {rows[-1].episode_length_buf}."
            )
    return selected


def _records_for_mass_bucket(
    records: Sequence[EvalRecord], label: str
) -> list[EvalRecord]:
    selected = [record for record in records if V16.mass_bucket(record.door_weight) == label]
    if not selected:
        raise V17ReportError(f"mass bucket {label!r} is empty.")
    return selected


def _trace_rows(
    record: EvalRecord,
    trace_sets: Mapping[int, Mapping[int, Sequence[TraceRecord]]],
) -> Sequence[TraceRecord]:
    try:
        rows = trace_sets[record.seed][record.env_id]
    except KeyError as exc:
        raise V17ReportError(
            f"missing trace rows for seed{record.seed} env{record.env_id}."
        ) from exc
    if any(row.control_dt != record.control_dt for row in rows):
        raise V17ReportError(
            f"seed{record.seed} env{record.env_id} trace control_dt changed within an episode."
        )
    return rows


def _continuous_summary(
    records: Sequence[EvalRecord],
    trace_sets: Mapping[int, Mapping[int, Sequence[TraceRecord]]],
) -> dict[str, Any]:
    reward_names = tuple(sorted(records[0].reward_episode_sums))
    for record in records:
        if tuple(sorted(record.reward_episode_sums)) != reward_names:
            raise V17ReportError(
                "all result records in an M38 report must share exact reward keys."
            )
    opening_durations = []
    for record in records:
        rows = _trace_rows(record, trace_sets)
        opening_steps = sum(row.stage in (3, 4) for row in rows)
        opening_durations.append(opening_steps * record.control_dt)

    released = [record for record in records if record.root_x_at_release is not None]
    return {
        "record_count": len(records),
        "goal": V16._goal_summary(records),
        "episode_length_steps": V16._stats(
            [float(record.episode_length_buf) for record in records]
        ),
        "episode_length_seconds": V16._stats(
            [record.episode_length_buf * record.control_dt for record in records]
        ),
        "opening_phase_duration_seconds": V16._stats(opening_durations),
        "post_release_body_force_max": V16._stats(
            [record.post_release_body_force_max for record in released]
        ),
        "delta_root_x_post_release": V16._stats(
            [record.root_pos_rel[0] - record.root_x_at_release for record in released]
        ),
        "reward_episode_sums_unit": "episode-sum",
        "reward_episode_sums": {
            name: V16._stats([record.reward_episode_sums[name] for record in records])
            for name in reward_names
        },
    }


def build_report(
    result_sets: Mapping[int, Sequence[EvalRecord]],
    trace_sets: Mapping[int, Mapping[int, Sequence[TraceRecord]]],
    *,
    group: str,
) -> dict[str, Any]:
    if not isinstance(group, str) or not group.strip():
        raise V17ReportError("group must be a non-empty string.")
    base = V16.build_report(result_sets, trace_sets)
    all_records = [record for seed in EXPECTED_SEEDS for record in result_sets[seed]]
    by_mass_bucket = {
        label: _continuous_summary(
            _records_for_mass_bucket(all_records, label), trace_sets
        )
        for *_bounds, label in MASS_BUCKETS
    }
    base.update(
        {
            "schema": SCHEMA,
            "schema_version": 1,
            "group": group.strip(),
            "m38": {
                "opening_phase_scope": "first-episode trace steps with stage_buf in {3,4}",
                "opening_phase_duration_source": "trace_step_count * exact control_dt",
                "by_mass_bucket": by_mass_bucket,
                "pooled": _continuous_summary(all_records, trace_sets),
            },
        }
    )
    return base


def write_outputs(
    report: Mapping[str, Any], output_dir: Path, input_paths: Mapping[str, Path]
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = "a2_piper_v17_bucket_report"
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
    rows = V16.V15._rows(report)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# A2_Piper v17 M38 report",
        "",
        f"Group: `{report['group']}`",
        "",
        "The JSON contains the unchanged v16 buckets/M33 metrics plus exact "
        "M38 continuous metrics.",
        "",
        "## M38 continuous metrics",
        "",
        "```json",
        json.dumps(report["m38"], indent=2, sort_keys=True),
        "```",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the strict A2_Piper v17 M38 report.")
    parser.add_argument("--group", required=True)
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
        trace_sets[seed] = load_trace(
            trace_path, expected_seed=seed, result_records=result_sets[seed]
        )
        input_paths[f"seed{seed}_result"] = result_path
        input_paths[f"seed{seed}_trace"] = trace_path
    report = build_report(result_sets, trace_sets, group=args.group)
    paths = write_outputs(report, args.output_dir, input_paths)
    print(f"v17 M38 JSON: {paths[0]}")
    print(f"v17 M38 CSV: {paths[1]}")
    print(f"v17 M38 Markdown: {paths[2]}")
    return 0


load_result_input = load_result
load_trace_input = load_trace
build_bucket_report = build_report
write_report_outputs = write_outputs


if __name__ == "__main__":
    sys.exit(main())
