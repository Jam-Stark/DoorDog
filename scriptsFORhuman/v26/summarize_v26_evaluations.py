"""Summarize side-stratified v26 Route A, holdout, and render records."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean, median


def _read_records(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["records"] if isinstance(payload, dict) else payload


def _optional_stat(rows: list[dict], field: str, reducer) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return reducer(values) if values else None


def _side_summary(rows: list[dict]) -> dict:
    if not rows:
        raise RuntimeError("evaluation record set is empty")
    stages = [int(row["max_stage"]) for row in rows]
    goals = [bool(row["goal_reached"]) for row in rows]
    crossings = [bool(row["crossing_while_holding"]) for row in rows]
    body_contacts = [bool(row["post_release_body_contact"]) for row in rows]
    return {
        "episodes": len(rows),
        "goals": sum(goals),
        "goal_rate": mean(goals),
        "max_stage": max(stages),
        "max_stage_counts": dict(sorted(Counter(stages).items())),
        "stage3_or_later": sum(stage >= 3 for stage in stages),
        "stage3_or_later_rate": mean(stage >= 3 for stage in stages),
        "crossing_while_holding": sum(crossings),
        "crossing_while_holding_rate": mean(crossings),
        "post_release_body_contact": sum(body_contacts),
        "post_release_body_contact_rate": mean(body_contacts),
        "hinge_at_crossing_median_rad": _optional_stat(
            rows, "hinge_at_crossing", median
        ),
        "hinge_at_release_median_rad": _optional_stat(
            rows, "hinge_at_release", median
        ),
        "post_release_body_force_max_n": _optional_stat(
            rows, "post_release_body_force_max", max
        ),
        "stage0_to1_staging_standoff_median_m": _optional_stat(
            rows, "stage0_to1_staging_standoff", median
        ),
        "door_handle_sides": sorted({str(row["door_handle_side"]) for row in rows}),
        "door_handle_height_range_m": [
            min(float(row["door_handle_height"]) for row in rows),
            max(float(row["door_handle_height"]) for row in rows),
        ],
        "door_weight_range_kg": [
            min(float(row["door_weight"]) for row in rows),
            max(float(row["door_weight"]) for row in rows),
        ],
    }


def _summarize_suite(root: Path) -> dict:
    candidates: dict[str, dict[str, dict]] = {}
    for path in sorted(root.glob("*/*/a2_v14_per_env_records.json")):
        candidate = path.parent.parent.name
        side = path.parent.name
        candidates.setdefault(candidate, {})[side] = _side_summary(_read_records(path))

    ranking = []
    for candidate, sides in candidates.items():
        if set(sides) != {"left", "right"}:
            raise RuntimeError(f"{candidate} is missing a side: {sorted(sides)}")
        left = sides["left"]
        right = sides["right"]
        ranking.append(
            {
                "candidate": candidate,
                "min_side_goals": min(left["goals"], right["goals"]),
                "min_side_stage3_or_later": min(
                    left["stage3_or_later"], right["stage3_or_later"]
                ),
                "min_side_max_stage": min(left["max_stage"], right["max_stage"]),
                "total_goals": left["goals"] + right["goals"],
                "total_stage3_or_later": (
                    left["stage3_or_later"] + right["stage3_or_later"]
                ),
                "total_post_release_body_contact": (
                    left["post_release_body_contact"]
                    + right["post_release_body_contact"]
                ),
            }
        )
    ranking.sort(
        key=lambda row: (
            row["min_side_goals"],
            row["min_side_stage3_or_later"],
            row["min_side_max_stage"],
            row["total_goals"],
            row["total_stage3_or_later"],
            -row["total_post_release_body_contact"],
            row["candidate"],
        ),
        reverse=True,
    )
    return {"root": str(root), "candidates": candidates, "diagnostic_ranking": ranking}


def _parse_suite(raw: str) -> tuple[str, Path]:
    label, separator, root = raw.partition("=")
    if not separator or not label or not root:
        raise argparse.ArgumentTypeError("--suite must use LABEL=ROOT")
    return label, Path(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", action="append", type=_parse_suite, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = {
        "schema": "a2_piper_base_v26_side_evaluation_summary_v1",
        "suites": {label: _summarize_suite(root) for label, root in args.suite},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
