"""Summarize v25 Teacher comparison and matched-prefix intervention records."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean, median


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _teacher_summary(root: Path) -> dict:
    candidates = {}
    for path in sorted(root.glob("*/*/a2_v14_per_env_records.json")):
        label = path.parent.parent.name
        side = path.parent.name
        payload = _read(path)
        rows = payload["records"] if isinstance(payload, dict) else payload
        candidates.setdefault(label, {})[side] = {
            "episodes": len(rows),
            "goals": sum(bool(row["goal_reached"]) for row in rows),
            "goal_rate": mean(bool(row["goal_reached"]) for row in rows),
            "max_stage_counts": dict(sorted(Counter(int(row["max_stage"]) for row in rows).items())),
            "crossing_while_holding_rate": mean(
                bool(row["crossing_while_holding"]) for row in rows
            ),
            "post_release_body_contact_rate": mean(
                bool(row["post_release_body_contact"]) for row in rows
            ),
            "hinge_at_release_median_rad": median(
                float(row["hinge_at_release"])
                for row in rows
                if row["hinge_at_release"] is not None
            ) if any(row["hinge_at_release"] is not None for row in rows) else None,
        }
    return candidates


def _causal_summary(root: Path) -> dict:
    branches = {}
    by_state = {}
    for path in sorted(root.glob("*/*/a2_v25_intervention_records.json")):
        payload = _read(path)
        branch = payload["branch"]
        side = path.parent.name
        rows = [row for row in payload["records"] if row["eligible_complete_horizon"]]
        branches.setdefault(branch, {})[side] = {
            "latched": len(payload["latched_env_ids"]),
            "eligible_complete_horizon": len(rows),
            "hinge_delta_median_rad": median(row["hinge_delta_rad"] for row in rows) if rows else None,
            "hinge_delta_mean_rad": mean(row["hinge_delta_rad"] for row in rows) if rows else None,
            "hinge_max_progress_median_rad": median(row["hinge_max_progress_rad"] for row in rows) if rows else None,
            "hinge_max_progress_mean_rad": mean(row["hinge_max_progress_rad"] for row in rows) if rows else None,
            "contact_retention_mean": mean(row["contact_retention_fraction"] for row in rows) if rows else None,
            "root_planar_displacement_mean_m": mean(row["root_planar_displacement_m"] for row in rows) if rows else None,
            "roll_pitch_abs_mean_rad": mean(row["roll_pitch_abs_mean_rad"] for row in rows) if rows else None,
            "raw_planar_dose_mean": mean(row["raw_planar_command_l1_mean"] for row in rows) if rows else None,
            "raw_posture_dose_mean": mean(row["raw_posture_command_l1_mean"] for row in rows) if rows else None,
            "removed_planar_dose_mean": mean(row["removed_planar_command_l1_mean"] for row in rows) if rows else None,
            "removed_posture_dose_mean": mean(row["removed_posture_command_l1_mean"] for row in rows) if rows else None,
        }
        for row in rows:
            by_state.setdefault((side, row["state_id"]), {})[branch] = row

    paired = []
    required = {"P1_M1", "P0_M1", "P1_M0", "P0_M0"}
    for (side, state_id), rows in sorted(by_state.items()):
        if set(rows) != required:
            continue
        paired.append({
            "side": side,
            "state_id": state_id,
            "hinge_delta_rad": {branch: rows[branch]["hinge_delta_rad"] for branch in sorted(required)},
            "posture_effect_with_planar": rows["P1_M1"]["hinge_delta_rad"] - rows["P0_M1"]["hinge_delta_rad"],
            "posture_effect_without_planar": rows["P1_M0"]["hinge_delta_rad"] - rows["P0_M0"]["hinge_delta_rad"],
            "planar_effect_with_posture": rows["P1_M1"]["hinge_delta_rad"] - rows["P1_M0"]["hinge_delta_rad"],
            "planar_effect_without_posture": rows["P0_M1"]["hinge_delta_rad"] - rows["P0_M0"]["hinge_delta_rad"],
        })
    effects = {}
    for side in ("left", "right"):
        side_rows = [row for row in paired if row["side"] == side]
        effects[side] = {
            "paired_states": len(side_rows),
            "posture_effect_with_planar_median": median(
                row["posture_effect_with_planar"] for row in side_rows
            ) if side_rows else None,
            "posture_effect_with_planar_mean": mean(
                row["posture_effect_with_planar"] for row in side_rows
            ) if side_rows else None,
            "posture_effect_without_planar_median": median(
                row["posture_effect_without_planar"] for row in side_rows
            ) if side_rows else None,
            "posture_effect_without_planar_mean": mean(
                row["posture_effect_without_planar"] for row in side_rows
            ) if side_rows else None,
            "planar_effect_with_posture_median": median(
                row["planar_effect_with_posture"] for row in side_rows
            ) if side_rows else None,
            "planar_effect_with_posture_mean": mean(
                row["planar_effect_with_posture"] for row in side_rows
            ) if side_rows else None,
            "planar_effect_without_posture_median": median(
                row["planar_effect_without_posture"] for row in side_rows
            ) if side_rows else None,
            "planar_effect_without_posture_mean": mean(
                row["planar_effect_without_posture"] for row in side_rows
            ) if side_rows else None,
        }
    return {"branches": branches, "paired_effects": effects, "paired_records": paired}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-root", type=Path)
    parser.add_argument("--causal-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = {"schema": "a2_piper_v25_summary_v1"}
    if args.teacher_root is not None:
        payload["teacher"] = _teacher_summary(args.teacher_root)
    if args.causal_root is not None:
        payload["causality"] = _causal_summary(args.causal_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
