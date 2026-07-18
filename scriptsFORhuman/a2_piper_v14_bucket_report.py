"""Deterministic v14 M20 bucket report for three explicit eval result files.

The CLI intentionally accepts exactly one seed-0, seed-1, and seed-2 input.  It
does not search an eval directory or merge historical artifacts implicitly.
Only standard-library modules are imported so the validation/report logic is
usable without IsaacLab.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EXPECTED_SEEDS = (0, 1, 2)
EXPECTED_ENVS_PER_SEED = 16
HANDLE_HEIGHT_BUCKET_LABELS = (
    "[0.80,0.90)",
    "[0.90,1.00)",
    "[1.00,1.05]",
)
TELEMETRY_NUMERIC_FIELDS = (
    "hinge_at_crossing",
    "stage0_to1_staging_standoff",
    "stage0_actual_root_height",
    "stage1_actual_root_height",
)


@dataclass(frozen=True)
class EvalRecord:
    seed: int
    env_id: int
    door_hinge_drive_max_force: float
    door_handle_drive_max_force: float
    door_handle_height: float
    goal_reached: bool
    max_stage: int | None
    final_stage: int | None
    crossing_while_holding: bool | None
    hinge_at_crossing: float | None
    stage0_to1_staging_standoff: float | None
    stage0_actual_root_height: float | None
    stage1_actual_root_height: float | None

    @property
    def stage_for_attainment(self) -> int:
        """Use the explicit maximum stage when present, otherwise final stage."""

        stage = self.max_stage if self.max_stage is not None else self.final_stage
        if stage is None:
            raise ValueError(f"Record seed={self.seed} env_id={self.env_id} has no stage representation.")
        return stage


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _field_with_presence(record: Mapping[str, Any], name: str, *sections: str) -> tuple[bool, Any]:
    if name in record:
        return True, record[name]
    for section_name in sections:
        section = record.get(section_name)
        if isinstance(section, Mapping) and name in section:
            return True, section[name]
    return False, None


def _required_field(record: Mapping[str, Any], name: str, *sections: str) -> Any:
    present, value = _field_with_presence(record, name, *sections)
    if not present:
        raise ValueError(f"record is missing required field {name!r}.")
    return value


def _optional_field(record: Mapping[str, Any], names: Sequence[str], *sections: str) -> tuple[bool, Any]:
    for name in names:
        present, value = _field_with_presence(record, name, *sections)
        if present:
            return True, value
    return False, None


def _parse_optional_finite(value: Any, *, field_name: str) -> float | None:
    if value is None:
        return None
    if not _finite(value):
        raise ValueError(f"{field_name} must be finite or null; got {value!r}.")
    return float(value)


def _parse_stage(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if not _finite(value) or float(value) != math.floor(float(value)):
        raise ValueError(f"{field_name} must be an integer stage or null; got {value!r}.")
    stage = int(value)
    if not 0 <= stage <= 5:
        raise ValueError(f"{field_name} must be in the staged-task range [0,5]; got {stage}.")
    return stage


def normalize_record(raw: Mapping[str, Any], *, expected_seed: int | None = None) -> EvalRecord:
    """Validate and normalize one frozen-schema per-environment result record."""

    if not isinstance(raw, Mapping):
        raise ValueError(f"each eval record must be an object; got {type(raw).__name__}.")
    seed = _required_field(raw, "seed", "identity")
    env_id = _required_field(raw, "env_id", "identity")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError(f"seed must be an integer; got {seed!r}.")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0:
        raise ValueError(f"env_id must be a non-negative integer; got {env_id!r}.")
    if expected_seed is not None and seed != expected_seed:
        raise ValueError(f"input assigned to seed{expected_seed} contains seed={seed}.")

    hinge_force = _required_field(raw, "door_hinge_drive_max_force", "metadata")
    handle_force = _required_field(raw, "door_handle_drive_max_force", "metadata")
    handle_height = _required_field(raw, "door_handle_height", "metadata")
    for field_name, value in (
        ("door_hinge_drive_max_force", hinge_force),
        ("door_handle_drive_max_force", handle_force),
        ("door_handle_height", handle_height),
    ):
        if not _finite(value):
            raise ValueError(f"{field_name} must be finite; got {value!r}.")
    if not 2.5 <= float(hinge_force) <= 7.0:
        raise ValueError(
            "door_hinge_drive_max_force must be in the v14 [2.5,7.0] range; "
            f"got {hinge_force!r}."
        )
    if not 1.0 <= float(handle_force) <= 3.0:
        raise ValueError(
            "door_handle_drive_max_force must be in the v14 [1.0,3.0] range; "
            f"got {handle_force!r}."
        )
    if not 0.80 <= float(handle_height) <= 1.05:
        raise ValueError(
            "door_handle_height must be in the M18-backed v14 [0.80,1.05] range; "
            f"got {handle_height!r}."
        )

    goal_reached = _required_field(raw, "goal_reached", "outcome")
    if not isinstance(goal_reached, bool):
        raise ValueError(f"goal_reached must be bool; got {goal_reached!r}.")

    max_present, max_value = _optional_field(
        raw, ("max_stage", "maximum_stage"), "outcome"
    )
    final_present, final_value = _optional_field(raw, ("final_stage", "stage"), "outcome")
    if not max_present and not final_present:
        raise ValueError("record requires max_stage/maximum_stage or final_stage/stage.")

    telemetry_values: dict[str, Any] = {}
    for field_name in ("crossing_while_holding", *TELEMETRY_NUMERIC_FIELDS):
        present, value = _field_with_presence(raw, field_name, "telemetry")
        if not present:
            raise ValueError(f"record is missing required telemetry field {field_name!r}.")
        telemetry_values[field_name] = value
    crossing = telemetry_values["crossing_while_holding"]
    if crossing is not None and not isinstance(crossing, bool):
        raise ValueError(f"crossing_while_holding must be bool or null; got {crossing!r}.")

    parsed_numeric = {
        field_name: _parse_optional_finite(telemetry_values[field_name], field_name=field_name)
        for field_name in TELEMETRY_NUMERIC_FIELDS
    }
    parsed_max_stage = _parse_stage(max_value, field_name="max_stage") if max_present else None
    parsed_final_stage = _parse_stage(final_value, field_name="final_stage") if final_present else None
    if parsed_max_stage is None and parsed_final_stage is None:
        raise ValueError("record requires at least one finite maximum/final stage value.")
    if (
        parsed_max_stage is not None
        and parsed_final_stage is not None
        and parsed_final_stage > parsed_max_stage
    ):
        raise ValueError(
            "final_stage cannot exceed max_stage; "
            f"got final_stage={parsed_final_stage}, max_stage={parsed_max_stage}."
        )
    return EvalRecord(
        seed=seed,
        env_id=env_id,
        door_hinge_drive_max_force=float(hinge_force),
        door_handle_drive_max_force=float(handle_force),
        door_handle_height=float(handle_height),
        goal_reached=goal_reached,
        max_stage=parsed_max_stage,
        final_stage=parsed_final_stage,
        crossing_while_holding=crossing,
        hinge_at_crossing=parsed_numeric["hinge_at_crossing"],
        stage0_to1_staging_standoff=parsed_numeric["stage0_to1_staging_standoff"],
        stage0_actual_root_height=parsed_numeric["stage0_actual_root_height"],
        stage1_actual_root_height=parsed_numeric["stage1_actual_root_height"],
    )


def _extract_json_records(payload: Any, path: Path) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, Mapping):
        for key in ("records", "per_env_records", "results"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                records = candidate
                break
        else:
            raise ValueError(f"{path} must contain a list under records/per_env_records/results.")
    else:
        raise ValueError(f"{path} must contain a JSON list or record container object.")
    return records


def _csv_nullish(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text == "" or text.lower() == "null" else text


def _csv_int(value: Any, *, field_name: str) -> int | None:
    text = _csv_nullish(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer in CSV input; got {value!r}.") from exc


def _csv_float(value: Any, *, field_name: str) -> float | None:
    text = _csv_nullish(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be numeric in CSV input; got {value!r}.") from exc


def _csv_bool(value: Any, *, field_name: str) -> bool | None:
    text = _csv_nullish(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"{field_name} must be true, false, or null in CSV input; got {value!r}.")


def _coerce_csv_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Convert flat CSV text to the strict typed record accepted by normalize_record."""

    converted = dict(raw)
    for field_name in ("seed", "env_id"):
        if field_name in converted:
            converted[field_name] = _csv_int(converted[field_name], field_name=field_name)
    for field_name in (
        "door_hinge_drive_max_force",
        "door_handle_drive_max_force",
        "door_handle_height",
        *TELEMETRY_NUMERIC_FIELDS,
    ):
        if field_name in converted:
            converted[field_name] = _csv_float(converted[field_name], field_name=field_name)
    for field_name in ("max_stage", "maximum_stage", "final_stage", "stage"):
        if field_name in converted:
            converted[field_name] = _csv_int(converted[field_name], field_name=field_name)
    for field_name in ("goal_reached", "crossing_while_holding"):
        if field_name in converted:
            converted[field_name] = _csv_bool(converted[field_name], field_name=field_name)
    return converted


def load_result_input(path: Path, *, expected_seed: int) -> list[EvalRecord]:
    """Load exactly one explicitly supplied seed result input."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Explicit result input does not exist: {path}")
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            raw_records = [_coerce_csv_record(raw) for raw in csv.DictReader(handle)]
    elif path.suffix.lower() == ".jsonl":
        raw_records = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw_records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON input {path}: {exc}") from exc
        raw_records = _extract_json_records(payload, path)

    records = [normalize_record(raw, expected_seed=expected_seed) for raw in raw_records]
    if len(records) != EXPECTED_ENVS_PER_SEED:
        raise ValueError(
            f"seed{expected_seed} input must contain exactly {EXPECTED_ENVS_PER_SEED} records; got {len(records)}."
        )
    env_ids = [record.env_id for record in records]
    expected_env_ids = set(range(EXPECTED_ENVS_PER_SEED))
    if set(env_ids) != expected_env_ids:
        raise ValueError(
            f"seed{expected_seed} input requires exactly env_id=0..15; got {sorted(env_ids)}."
        )
    return sorted(records, key=lambda record: record.env_id)


def validate_seed_inputs(seed_paths: Mapping[int, Path]) -> list[EvalRecord]:
    """Load the three explicitly named seed inputs and reject all other topology."""

    if set(seed_paths) != set(EXPECTED_SEEDS):
        raise ValueError(f"report requires exactly seed inputs {set(EXPECTED_SEEDS)}; got {set(seed_paths)}.")
    records: list[EvalRecord] = []
    for seed in EXPECTED_SEEDS:
        records.extend(load_result_input(seed_paths[seed], expected_seed=seed))
    if len(records) != len(EXPECTED_SEEDS) * EXPECTED_ENVS_PER_SEED:
        raise ValueError(f"report requires 48 total records; got {len(records)}.")
    identities = [(record.seed, record.env_id) for record in records]
    if len(set(identities)) != len(identities):
        raise ValueError("report contains duplicate (seed, env_id) identities.")
    return records


def handle_height_bucket(height: float) -> str:
    if not _finite(height):
        raise ValueError(f"handle height must be finite; got {height!r}.")
    height = float(height)
    if 0.80 <= height < 0.90:
        return HANDLE_HEIGHT_BUCKET_LABELS[0]
    if 0.90 <= height < 1.00:
        return HANDLE_HEIGHT_BUCKET_LABELS[1]
    if 1.00 <= height <= 1.05:
        return HANDLE_HEIGHT_BUCKET_LABELS[2]
    raise ValueError(
        f"handle height {height} is outside the M18-backed v14 [0.80,1.05] range."
    )


def _rank_buckets(records: Sequence[EvalRecord], field_name: str, bucket_count: int) -> dict[tuple[int, int], str]:
    if bucket_count <= 0:
        raise ValueError("bucket_count must be positive.")
    ordered = sorted(
        records,
        key=lambda record: (getattr(record, field_name), record.seed, record.env_id),
    )
    labels = (
        tuple(f"tertile_{index + 1}" for index in range(bucket_count))
        if bucket_count == 3
        else ("low_rank", "high_rank")
    )
    assignments: dict[tuple[int, int], str] = {}
    for index, record in enumerate(ordered):
        bucket_index = min(bucket_count - 1, index * bucket_count // len(ordered))
        assignments[(record.seed, record.env_id)] = labels[bucket_index]
    return assignments


def _numeric_summary(values: Iterable[float | None]) -> dict[str, Any]:
    finite_values = [float(value) for value in values if value is not None and _finite(value)]
    if not finite_values:
        return {"n": 0, "null_count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "n": len(finite_values),
        "null_count": 0,
        "min": min(finite_values),
        "max": max(finite_values),
        "mean": statistics.fmean(finite_values),
        "median": statistics.median(finite_values),
    }


def _telemetry_summary(records: Sequence[EvalRecord]) -> dict[str, Any]:
    crossing_values = [record.crossing_while_holding for record in records]
    known_crossing = [value for value in crossing_values if value is not None]
    numeric = {
        field_name: _numeric_summary(getattr(record, field_name) for record in records)
        for field_name in TELEMETRY_NUMERIC_FIELDS
    }
    for field_name in TELEMETRY_NUMERIC_FIELDS:
        numeric[field_name]["null_count"] = len(records) - numeric[field_name]["n"]
    return {
        "crossing_while_holding": {
            "n": len(known_crossing),
            "null_count": len(records) - len(known_crossing),
            "true_count": sum(value is True for value in known_crossing),
            "false_count": sum(value is False for value in known_crossing),
            "true_rate_known": (
                sum(value is True for value in known_crossing) / len(known_crossing)
                if known_crossing
                else None
            ),
        },
        **numeric,
    }


def summarize_group(records: Sequence[EvalRecord]) -> dict[str, Any]:
    """Summarize goal/stage attainment and telemetry for one deterministic group."""

    if not records:
        return {
            "n": 0,
            "goal_reached_count": 0,
            "goal_reached_rate": None,
            "stage_attainment": {str(stage): {"count": 0, "rate": None} for stage in range(6)},
            "telemetry": _telemetry_summary(records),
        }
    stage_values = [record.stage_for_attainment for record in records]
    stage_attainment = {
        str(stage): {
            "count": sum(value >= stage for value in stage_values),
            "rate": sum(value >= stage for value in stage_values) / len(records),
        }
        for stage in range(6)
    }
    return {
        "n": len(records),
        "goal_reached_count": sum(record.goal_reached for record in records),
        "goal_reached_rate": sum(record.goal_reached for record in records) / len(records),
        "stage_attainment": stage_attainment,
        "max_stage_distribution": {
            str(stage): sum(record.stage_for_attainment == stage for record in records)
            for stage in sorted(set(stage_values))
        },
        "telemetry": _telemetry_summary(records),
    }


def _group_dimension(records: Sequence[EvalRecord], assignments: Mapping[tuple[int, int], str]) -> dict[str, Any]:
    labels = sorted(set(assignments.values()))
    return {
        label: summarize_group(
            [record for record in records if assignments[(record.seed, record.env_id)] == label]
        )
        for label in labels
    }


def build_bucket_report(records: Sequence[EvalRecord]) -> dict[str, Any]:
    """Build the complete M20 report from validated records."""

    if len(records) != len(EXPECTED_SEEDS) * EXPECTED_ENVS_PER_SEED:
        raise ValueError(f"build_bucket_report requires exactly 48 records; got {len(records)}.")
    for record in records:
        handle_height_bucket(record.door_handle_height)
    hinge_assignments = _rank_buckets(records, "door_hinge_drive_max_force", 3)
    handle_force_assignments = _rank_buckets(records, "door_handle_drive_max_force", 2)
    height_assignments = {
        (record.seed, record.env_id): handle_height_bucket(record.door_handle_height)
        for record in records
    }
    seed_groups = {
        f"seed{seed}": {
            "role": "canonical" if seed == 0 else "supplementary",
            "summary": summarize_group([record for record in records if record.seed == seed]),
        }
        for seed in EXPECTED_SEEDS
    }
    return {
        "schema": "a2_piper_v14_bucket_report_v1",
        "record_count": len(records),
        "seed_roles": {
            "seed0": "canonical",
            "seed1": "supplementary",
            "seed2": "supplementary",
        },
        "stage_attainment_basis": "max_stage when present, otherwise the explicit final_stage representation",
        "bucket_rules": {
            "hinge_force": "stable rank tertiles over all 48 records, ties ordered by (force, seed, env_id)",
            "handle_height": list(HANDLE_HEIGHT_BUCKET_LABELS),
            "handle_force": "stable rank split over all 48 records: first 24 low_rank, last 24 high_rank",
        },
        "all_records_summary": summarize_group(records),
        "by_seed": seed_groups,
        "by_hinge_force_tertile": _group_dimension(records, hinge_assignments),
        "by_handle_height_bucket": _group_dimension(records, height_assignments),
        "by_handle_force_bucket": _group_dimension(records, handle_force_assignments),
    }


def _flat_group_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dimension_key in (
        "by_hinge_force_tertile",
        "by_handle_height_bucket",
        "by_handle_force_bucket",
    ):
        for bucket, summary in report[dimension_key].items():
            row = {
                "dimension": dimension_key,
                "bucket": bucket,
                "n": summary["n"],
                "goal_reached_count": summary["goal_reached_count"],
                "goal_reached_rate": summary["goal_reached_rate"],
            }
            for stage in range(6):
                row[f"stage_{stage}_rate"] = summary["stage_attainment"][str(stage)]["rate"]
            rows.append(row)
    return rows


def write_report_outputs(
    output_dir: Path,
    report: Mapping[str, Any],
    *,
    stem: str = "a2_piper_v14_bucket_report",
    input_files: Mapping[int, Path] | None = None,
) -> tuple[Path, Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    payload = dict(report)
    if input_files is not None:
        payload["explicit_input_files"] = {f"seed{seed}": str(path) for seed, path in sorted(input_files.items())}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows = _flat_group_rows(report)
    fieldnames = list(rows[0]) if rows else ["dimension", "bucket", "n"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# A2_Piper v14 M20 bucket report",
        "",
        "Seed 0 is canonical; seeds 1 and 2 are supplementary. The three input paths were explicit CLI arguments.",
        "",
        f"- Records: `{report['record_count']}`",
        f"- Overall goal rate: `{report['all_records_summary']['goal_reached_rate']}`",
        "",
        "| Dimension | Bucket | N | Goal count | Goal rate | Stage 3 rate | Stage 4 rate | Stage 5 rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['dimension']} | {row['bucket']} | {row['n']} | "
            f"{row['goal_reached_count']} | {row['goal_reached_rate']} | "
            f"{row['stage_3_rate']} | {row['stage_4_rate']} | {row['stage_5_rate']} |"
        )
    lines.extend(
        [
            "",
            "Telemetry numeric summaries use `null` in JSON and `N/A` in this report when the event has no finite samples; `crossing_while_holding` retains explicit true/false/null counts.",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, json_path, markdown_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build an explicit-seed A2_Piper v14 bucket report from one seed0, "
            "one seed1, and one seed2 result input."
        )
    )
    parser.add_argument("--seed0-result", "--seed0", dest="seed0_result", type=Path, required=True)
    parser.add_argument("--seed1-result", "--seed1", dest="seed1_result", type=Path, required=True)
    parser.add_argument("--seed2-result", "--seed2", dest="seed2_result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Explicit report output directory.")
    parser.add_argument("--output-stem", default="a2_piper_v14_bucket_report")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    input_files = {0: args.seed0_result, 1: args.seed1_result, 2: args.seed2_result}
    records = validate_seed_inputs(input_files)
    report = build_bucket_report(records)
    paths = write_report_outputs(args.output_dir, report, stem=args.output_stem, input_files=input_files)
    print(f"M20 bucket CSV: {paths[0]}")
    print(f"M20 bucket JSON: {paths[1]}")
    print(f"M20 bucket Markdown: {paths[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
