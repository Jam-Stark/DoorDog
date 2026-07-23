"""Strict v18 P1 fingertip-slip report.

The input is one or more first-episode ``stage2_5_step_trace.json`` files.  For
each ``(seed, env_id)`` this reporter sums the absolute change in the source
frame handle Y coordinate (``target_pos_source_handle[1]``) only across
adjacent bilateral-contact rows.  Sums are reported in centimetres and are
split into opening stage 3 and corridor stages 4/5.

This is intentionally an offline, fail-fast reporter.  It never infers a
terminal or continuity boundary from row count, and it never substitutes a
missing value with zero.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "a2_piper_v18_p1_slip_report_v1"
EXPECTED_ENV_IDS = set(range(16))
TRACE_FILENAME = "stage2_5_step_trace.json"
_SEED_RE = re.compile(r"(?:^|[_-])seed(?P<seed>\d+)(?:$|[_-])")


class SlipReportError(ValueError):
    """Raised when trace schema/topology evidence is not strict-valid."""


def _finite_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SlipReportError(f"{field} must be a finite number; got {value!r}.")
    value = float(value)
    if not math.isfinite(value):
        raise SlipReportError(f"{field} must be finite; got {value!r}.")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SlipReportError(f"{field} must be a non-negative int; got {value!r}.")
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SlipReportError(f"{field} must be a positive int; got {value!r}.")
    return value


def _seed_from_path(path: Path) -> int:
    matches = [int(match.group("seed")) for part in path.parts for match in [_SEED_RE.search(part)] if match]
    if len(matches) != 1:
        raise SlipReportError(
            f"trace input {path} must contain exactly one unambiguous seedN path component; "
            f"found {matches}."
        )
    return matches[0]


def resolve_trace_input(path: Path) -> tuple[int, Path]:
    """Resolve a trace file or eval directory and derive its seed provenance."""
    path = path.expanduser()
    trace_path = path / TRACE_FILENAME if path.is_dir() else path
    if not trace_path.is_file():
        raise SlipReportError(f"trace input does not exist as file or eval directory: {path}")
    return _seed_from_path(trace_path.parent), trace_path


def _required_row(raw: Mapping[str, Any], seed: int, row_index: int) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise SlipReportError(f"seed{seed} row {row_index} must be a mapping; got {type(raw).__name__}.")
    required = (
        "env_id",
        "episode_index",
        "first_episode_active",
        "stage_buf",
        "step_index",
        "episode_length_buf",
        "control_dt",
        "target_pos_source_handle",
        "both_contact",
        "terminal_reasons",
    )
    missing = [name for name in required if name not in raw]
    if missing:
        raise SlipReportError(f"seed{seed} row {row_index} missing required fields {missing}.")
    env_id = raw["env_id"]
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in EXPECTED_ENV_IDS:
        raise SlipReportError(f"seed{seed} row {row_index} has invalid env_id={env_id!r}.")
    episode_index = raw["episode_index"]
    if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index != 0:
        raise SlipReportError(
            f"seed{seed} env{env_id} row {row_index} requires first-episode episode_index=0; "
            f"got {episode_index!r}."
        )
    if raw["first_episode_active"] is not True:
        raise SlipReportError(
            f"seed{seed} env{env_id} row {row_index} requires first_episode_active=true; "
            f"got {raw['first_episode_active']!r}."
        )
    stage = raw["stage_buf"]
    if isinstance(stage, bool) or not isinstance(stage, int) or stage not in {2, 3, 4, 5}:
        raise SlipReportError(f"seed{seed} env{env_id} row {row_index} has invalid stage_buf={stage!r}.")
    step_index = _nonnegative_int(raw["step_index"], "step_index")
    episode_length = _positive_int(raw["episode_length_buf"], "episode_length_buf")
    control_dt = _finite_float(raw["control_dt"], "control_dt")
    if control_dt <= 0.0:
        raise SlipReportError(f"seed{seed} env{env_id} control_dt must be positive; got {control_dt}.")
    target = raw["target_pos_source_handle"]
    if not isinstance(target, (list, tuple)) or len(target) != 3:
        raise SlipReportError(
            f"seed{seed} env{env_id} target_pos_source_handle must contain exactly 3 values; "
            f"got {target!r}."
        )
    target = tuple(_finite_float(value, "target_pos_source_handle component") for value in target)
    if not isinstance(raw["both_contact"], bool):
        raise SlipReportError(
            f"seed{seed} env{env_id} both_contact must be bool; got {raw['both_contact']!r}."
        )
    terminal = raw["terminal_reasons"]
    if not isinstance(terminal, str) or not terminal:
        raise SlipReportError(
            f"seed{seed} env{env_id} terminal_reasons must be a non-empty string; got {terminal!r}."
        )
    if "seed" in raw:
        row_seed = raw["seed"]
        if isinstance(row_seed, bool) or not isinstance(row_seed, int) or row_seed != seed:
            raise SlipReportError(
                f"seed{seed} env{env_id} row {row_index} has conflicting seed provenance {row_seed!r}."
            )
    return {
        "env_id": env_id,
        "episode_index": episode_index,
        "first_episode_active": True,
        "stage_buf": stage,
        "step_index": step_index,
        "episode_length_buf": episode_length,
        "control_dt": control_dt,
        "target_pos_source_handle": target,
        "both_contact": raw["both_contact"],
        "terminal_reasons": terminal,
    }


def _new_accumulator(seed: int, env_id: int) -> dict[str, Any]:
    return {
        "seed": seed,
        "env_id": env_id,
        "rows": 0,
        "bilateral_rows": 0,
        "opening_pairs": 0,
        "corridor_pairs": 0,
        "opening_slip_cm": 0.0,
        "corridor_slip_cm": 0.0,
        "first_step_index": None,
        "last_step_index": None,
        "first_episode_length_buf": None,
        "last_episode_length_buf": None,
        "terminal_reasons": None,
        "_previous": None,
    }


def _consume_rows(rows: Iterable[Mapping[str, Any]], *, seed: int) -> dict[int, dict[str, Any]]:
    accumulators = {env_id: _new_accumulator(seed, env_id) for env_id in sorted(EXPECTED_ENV_IDS)}
    seen_steps: set[tuple[int, int]] = set()
    seen_envs: set[int] = set()
    parsed_rows = 0
    for row_index, raw in enumerate(rows):
        row = _required_row(raw, seed, row_index)
        env_id = row["env_id"]
        key = (env_id, row["step_index"])
        if key in seen_steps:
            raise SlipReportError(f"seed{seed} env{env_id} has duplicate step_index={row['step_index']}.")
        seen_steps.add(key)
        seen_envs.add(env_id)
        acc = accumulators[env_id]
        previous = acc["_previous"]
        if previous is not None:
            if row["step_index"] != previous["step_index"] + 1:
                raise SlipReportError(
                    f"seed{seed} env{env_id} step_index must be unique, ordered, and contiguous; "
                    f"got adjacent values ({previous['step_index']}, {row['step_index']})."
                )
            if row["episode_length_buf"] != previous["episode_length_buf"] + 1:
                raise SlipReportError(
                    f"seed{seed} env{env_id} episode_length_buf must be unique, ordered, and "
                    f"contiguous; got adjacent values ({previous['episode_length_buf']}, "
                    f"{row['episode_length_buf']})."
                )
            if previous["terminal_reasons"] != "unknown_reset":
                raise SlipReportError(
                    f"seed{seed} env{env_id} has terminal_reasons={previous['terminal_reasons']!r} "
                    "before its final trace row."
                )
            same_opening_phase = previous["stage_buf"] == row["stage_buf"] == 3
            same_corridor_phase = previous["stage_buf"] in (4, 5) and row["stage_buf"] in (4, 5)
            if previous["both_contact"] and row["both_contact"] and (
                same_opening_phase or same_corridor_phase
            ):
                delta_cm = abs(row["target_pos_source_handle"][1] - previous["target_pos_source_handle"][1]) * 100.0
                if same_opening_phase:
                    acc["opening_slip_cm"] += delta_cm
                    acc["opening_pairs"] += 1
                else:
                    acc["corridor_slip_cm"] += delta_cm
                    acc["corridor_pairs"] += 1
        else:
            acc["first_step_index"] = row["step_index"]
            acc["first_episode_length_buf"] = row["episode_length_buf"]
            if row["stage_buf"] != 2:
                raise SlipReportError(
                    f"seed{seed} env{env_id} trace must start at stage_buf=2; got {row['stage_buf']}."
                )
        acc["rows"] += 1
        if row["both_contact"]:
            acc["bilateral_rows"] += 1
        acc["last_step_index"] = row["step_index"]
        acc["last_episode_length_buf"] = row["episode_length_buf"]
        acc["terminal_reasons"] = row["terminal_reasons"]
        acc["_previous"] = row
        parsed_rows += 1

    if seen_envs != EXPECTED_ENV_IDS:
        raise SlipReportError(
            f"seed{seed} trace requires exactly env_id 0..15; missing={sorted(EXPECTED_ENV_IDS - seen_envs)}."
        )
    result: dict[int, dict[str, Any]] = {}
    for env_id, acc in accumulators.items():
        if acc["rows"] == 0 or acc["_previous"] is None:
            raise SlipReportError(f"seed{seed} env{env_id} has no trace rows.")
        if acc["terminal_reasons"] == "unknown_reset":
            raise SlipReportError(f"seed{seed} env{env_id} is missing terminal evidence at the final row.")
        if acc["last_step_index"] != acc["first_step_index"] + acc["rows"] - 1:
            raise SlipReportError(f"seed{seed} env{env_id} step_index terminal continuity is invalid.")
        if acc["last_episode_length_buf"] != acc["first_episode_length_buf"] + acc["rows"] - 1:
            raise SlipReportError(f"seed{seed} env{env_id} episode_length_buf terminal continuity is invalid.")
        acc.pop("_previous")
        result[env_id] = acc
    if parsed_rows <= 0:
        raise SlipReportError(f"seed{seed} trace is empty.")
    return result


def load_trace(path: Path, *, expected_seed: int | None = None) -> dict[int, dict[str, Any]]:
    seed, trace_path = resolve_trace_input(path)
    if expected_seed is not None and seed != expected_seed:
        raise SlipReportError(f"trace {trace_path} expected seed{expected_seed}, found seed{seed}.")
    try:
        with trace_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SlipReportError(f"cannot load strict trace {trace_path}: {exc}") from exc
    if not isinstance(payload, list):
        raise SlipReportError(f"trace {trace_path} must be a JSON list of rows.")
    return _consume_rows(payload, seed=seed)


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        raise SlipReportError("cannot compute a quantile for an empty record set.")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        raise SlipReportError("cannot summarize an empty record set.")
    def metric(key: str) -> dict[str, Any]:
        values = [float(record[key]) for record in records]
        return {
            "n": len(values),
            "p50_cm": _quantile(values, 0.50),
            "p95_cm": _quantile(values, 0.95),
            "min_cm": min(values),
            "max_cm": max(values),
        }
    return {
        "record_count": len(records),
        "opening_stage3": metric("opening_slip_cm"),
        "corridor_stages4_5": metric("corridor_slip_cm"),
    }


def build_report(record_sets: Mapping[int, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    if not record_sets:
        raise SlipReportError("at least one seed trace is required.")
    seeds = sorted(record_sets)
    if len(seeds) == 3 and set(seeds) != {0, 1, 2}:
        raise SlipReportError(f"three-input P1 report requires seeds 0,1,2; got {seeds}.")
    all_records = []
    by_seed: dict[str, Any] = {}
    for seed in seeds:
        records = sorted((dict(record) for record in record_sets[seed]), key=lambda row: row["env_id"])
        if {record["env_id"] for record in records} != EXPECTED_ENV_IDS or len(records) != 16:
            raise SlipReportError(f"seed{seed} P1 report requires exactly 16 env records.")
        by_seed[str(seed)] = _summary(records)
        all_records.extend(records)
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "seed_count": len(seeds),
        "seeds": seeds,
        "record_count": len(all_records),
        "per_seed": by_seed,
        "pooled": _summary(all_records),
        "records": all_records,
        "pair_semantics": (
            "absolute target_pos_source_handle[1] delta in consecutive bilateral-contact rows; "
            "both rows must be in stage3 for opening or both in stages4/5 for corridor, "
            "so stage4-to-stage5 pairs count while cross-phase pairs are excluded"
        ),
    }


def write_outputs(report: Mapping[str, Any], output_prefix: Path) -> tuple[Path, Path, Path]:
    output_prefix = output_prefix.expanduser()
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_prefix.with_suffix(".json")
    csv_path = output_prefix.with_suffix(".csv")
    md_path = output_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = list(report["records"])
    fieldnames = [
        "seed", "env_id", "rows", "bilateral_rows", "opening_pairs", "corridor_pairs",
        "opening_slip_cm", "corridor_slip_cm", "first_step_index", "last_step_index",
        "first_episode_length_buf", "last_episode_length_buf", "terminal_reasons",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fieldnames} for row in rows)
    md_path.write_text(
        "# A2+Piper v18 P1 slip report\n\n"
        f"Schema: `{report['schema']}`\n\n"
        f"Seeds: `{report['seeds']}`; records: `{report['record_count']}`\n\n"
        "## Pooled slip (cm)\n\n"
        "```json\n"
        + json.dumps(report["pooled"], indent=2, sort_keys=True)
        + "\n```\n\n"
        "## Pair semantics\n\n"
        + report["pair_semantics"]
        + "\n",
        encoding="utf-8",
    )
    return json_path, csv_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict v18 P1 fingertip slip report.")
    parser.add_argument("--trace-dir", type=Path, nargs="+", required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    record_sets: dict[int, list[dict[str, Any]]] = {}
    for path in args.trace_dir:
        seed, _trace_path = resolve_trace_input(path)
        if seed in record_sets:
            raise SlipReportError(f"duplicate seed input seed{seed}; input provenance is ambiguous.")
        record_sets[seed] = list(load_trace(path, expected_seed=seed).values())
    if set(record_sets) != {0, 1, 2}:
        raise SlipReportError(
            f"formal v18 P1 report requires exactly seeds 0,1,2; got {sorted(record_sets)}."
        )
    report = build_report(record_sets)
    paths = write_outputs(report, args.output_prefix)
    print(f"v18 P1 JSON: {paths[0]}")
    print(f"v18 P1 CSV: {paths[1]}")
    print(f"v18 P1 Markdown: {paths[2]}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SlipReportError as exc:
        print(f"v18 P1 FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
