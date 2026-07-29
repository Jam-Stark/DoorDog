"""Compute exact matched-door paired v20 factor deltas."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v20_paired_analysis_v1"
PAIRS = (("G1", "G2"), ("G1", "G3"), ("G3", "G4"), ("G3", "G5"), ("G4", "G6"), ("G6", "G7"))
METRICS = (
    "hinge_at_first_crossing",
    "pre_send_root_crossing",
    "held_hinge",
    "opening_slip_m",
    "arm_tangent_share",
    "arc_position_error_m",
    "hinge_jerk",
    "arm_action_jerk",
    "task_time_s",
)


class V20PairedError(ValueError):
    pass


def _load_records(path: Path, group: str) -> dict[tuple[int, str], Mapping[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V20PairedError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, Mapping) or payload.get("schema") != "a2_piper_v20_per_env_endpoint_v1":
        raise V20PairedError(f"{group} per-env schema mismatch")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 48:
        raise V20PairedError(f"{group} requires exactly 48 pooled rows")
    result = {}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("group") != group:
            raise V20PairedError(f"{group} row binding mismatch")
        seed, door_id = row.get("seed"), row.get("door_id")
        if isinstance(seed, bool) or seed not in (0, 1, 2) or not isinstance(door_id, str) or not door_id:
            raise V20PairedError(f"{group} row key is malformed")
        key = (seed, door_id)
        if key in result:
            raise V20PairedError(f"{group} duplicate matched key {key}")
        for metric in METRICS:
            value = row.get(metric)
            if isinstance(value, bool):
                continue
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise V20PairedError(f"{group}.{metric} must be finite/bool")
        result[key] = row
    if len(result) != 48:
        raise V20PairedError(f"{group} matched topology is incomplete")
    return result


def build_paired_analysis(sources: Mapping[str, Path]) -> dict[str, Any]:
    if set(sources) != {f"G{index}" for index in range(1, 8)}:
        raise V20PairedError("sources must contain exactly G1..G7")
    records = {group: _load_records(Path(path), group) for group, path in sources.items()}
    rows = []
    summaries = {}
    for control, treatment in PAIRS:
        if set(records[control]) != set(records[treatment]):
            raise V20PairedError(f"{control}->{treatment} matched door keys differ")
        pair_rows = []
        for seed, door_id in sorted(records[control]):
            row = {"comparison": f"{control}->{treatment}", "seed": seed, "door_id": door_id}
            for metric in METRICS:
                left, right = records[control][(seed, door_id)][metric], records[treatment][(seed, door_id)][metric]
                row[f"{metric}_delta"] = int(right) - int(left) if isinstance(left, bool) else float(right) - float(left)
            pair_rows.append(row)
            rows.append(row)
        summaries[f"{control}->{treatment}"] = {
            metric: {
                "median_delta": sorted(row[f"{metric}_delta"] for row in pair_rows)[23:25],
                "positive_count": sum(row[f"{metric}_delta"] > 0 for row in pair_rows),
                "negative_count": sum(row[f"{metric}_delta"] < 0 for row in pair_rows),
                "total": 48,
            }
            for metric in METRICS
        }
    return {
        "schema": SCHEMA,
        "pairs": [f"{left}->{right}" for left, right in PAIRS],
        "rows": rows,
        "summaries": summaries,
        "claim": "descriptive paired evidence; not statistical proof",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    sources = {}
    for token in args.source:
        if "=" not in token:
            raise V20PairedError("--source must be GROUP=PATH")
        group, path = token.split("=", 1)
        if group in sources:
            raise V20PairedError(f"duplicate source {group}")
        sources[group] = Path(path)
    if args.output_json.exists() or args.output_csv.exists():
        raise V20PairedError("refusing to overwrite paired outputs")
    report = build_paired_analysis(sources)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report["rows"][0]))
        writer.writeheader()
        writer.writerows(report["rows"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V20PairedError as exc:
        print(f"v20 PAIRED FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
