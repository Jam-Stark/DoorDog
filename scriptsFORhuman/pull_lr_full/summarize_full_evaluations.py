#!/usr/bin/env python3
"""Summarize bilateral full-pull natural evaluation funnels by raw asset side."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


EVENTS = (
    "E0_RESET_VALID",
    "E1_OUTSIDE_FACE_PREGRASP",
    "E2_TENSILE_CAPTURE",
    "E3_LATCH_RELEASE",
    "E4_POSITIVE_HINGE_RETAINED",
    "E5_CLEARANCE_DECISION",
    "E6_PATH_REVERSAL_ENTRY",
    "E7_WHOLE_BODY_CLEAR",
)
SIDE_SIGNS = {"left": 1.0, "right": -1.0}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _cell(root: Path) -> dict:
    records = _load_json(root / "eval/a2_v14_per_env_records.json")
    trace = _load_json(root / "eval/stage2_5_step_trace.json")
    if not isinstance(records, list) or not records:
        raise ValueError(f"{root}: terminal records must be a non-empty list")
    if not isinstance(trace, list) or not trace:
        raise ValueError(f"{root}: stage trace must be a non-empty list")
    by_env: dict[int, list[dict]] = defaultdict(list)
    for row in trace:
        if row.get("first_episode_active") is not True or row.get("episode_index") != 0:
            continue
        by_env[int(row["env_id"])].append(row)
    terminal_by_env = {int(record["env_id"]): record for record in records}
    if set(by_env) != set(terminal_by_env):
        raise ValueError(
            f"{root}: trace/terminal env ids differ: {sorted(by_env)} vs {sorted(terminal_by_env)}"
        )

    episodes = []
    for env_id, record in sorted(terminal_by_env.items()):
        rows = sorted(by_env[env_id], key=lambda row: int(row["step_index"]))
        side = record.get("door_handle_side")
        if side not in SIDE_SIGNS or float(record.get("door_open_lr")) != SIDE_SIGNS[side]:
            raise ValueError(f"{root}: invalid terminal side provenance for env {env_id}")
        if any(
            row.get("door_handle_side") != side
            or float(row.get("door_open_lr")) != SIDE_SIGNS[side]
            for row in rows
        ):
            raise ValueError(f"{root}: trace side provenance changed for env {env_id}")
        last = rows[-1]
        episode = last["pull_v0_episode"]
        reached = episode["event_reached"]
        if tuple(reached) != EVENTS:
            raise ValueError(f"{root}: unexpected event schema for env {env_id}")
        proof_rows = [row["pull_v0"] for row in rows]
        episodes.append(
            {
                "env_id": env_id,
                "side": side,
                "goal_reached": bool(record["goal_reached"]),
                "max_stage": int(record["max_stage"]),
                "terminal_reason": episode["terminal_reason"],
                "strict_k5": max(int(row["a2_stage2_squeeze_streak"]) for row in rows) >= 5,
                "max_handle_rad": max(float(row["handle_position_rad"]) for row in proof_rows),
                "max_latch_m": max(float(row["latch_position_m"]) for row in proof_rows),
                "max_hinge_rad": max(float(row["hinge_position_rad"]) for row in proof_rows),
                "max_proof_duration_s": max(float(row["tensile_proof_duration_s"]) for row in proof_rows),
                "max_proof_displacement_m": max(float(row["tensile_proof_displacement_m"]) for row in proof_rows),
                "max_proof_streak_steps": max(int(row["tensile_proof_streak_steps"]) for row in proof_rows),
                "events": {name: bool(reached[name]) for name in EVENTS},
            }
        )
    return {"root": str(root.resolve()), "episodes": episodes}


def _aggregate(episodes: list[dict]) -> dict:
    result = {"episodes": len(episodes)}
    result["strict_k5"] = sum(row["strict_k5"] for row in episodes)
    for stage in (3, 4, 5):
        result[f"max_stage_ge_{stage}"] = sum(row["max_stage"] >= stage for row in episodes)
    for event in EVENTS:
        result[event] = sum(row["events"][event] for row in episodes)
    result["handle_ge_0p3"] = sum(row["max_handle_rad"] >= 0.3 for row in episodes)
    result["latch_ge_0p0229237154"] = sum(
        row["max_latch_m"] >= 0.02292371541261673 for row in episodes
    )
    result["goal_reached"] = sum(row["goal_reached"] for row in episodes)
    result["terminal_reasons"] = dict(
        sorted(
            (reason, sum(row["terminal_reason"] == reason for row in episodes))
            for reason in {row["terminal_reason"] for row in episodes}
        )
    )
    return result


def main() -> int:
    args = _parse_args()
    cells = [_cell(root.resolve()) for root in args.roots]
    episodes = [episode for cell in cells for episode in cell["episodes"]]
    by_side = {
        side: _aggregate([episode for episode in episodes if episode["side"] == side])
        for side in SIDE_SIGNS
    }
    summary = {
        "schema": "a2_piper_pull_lr_full_evaluation_summary_v1",
        "cells": cells,
        "by_side": by_side,
        "overall": _aggregate(episodes),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
