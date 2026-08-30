#!/usr/bin/env python3
"""Summarize and rank fixed-side pull Stage0-2 evaluation results."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean, median

from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_lr_grasp"
SIDES = ("left", "right")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_EVAL_ROOT)
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--expected-episodes", type=int, default=64)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _rate(count: int, denominator: int) -> float:
    return count / denominator


def _median(diagnostics: list[dict], field: str) -> float | None:
    values = [float(row[field]) for row in diagnostics if row.get(field) is not None]
    return median(values) if values else None


def _load_contract(side_root: Path, expected_side: str) -> dict:
    config_path = side_root / "hydra/.hydra/runtime_config.yaml"
    config = OmegaConf.load(config_path)
    env = config["env"]["config"]
    if env["enable_staged_reset"] is not False:
        raise RuntimeError(f"numeric eval must use natural reset: {config_path}")
    if int(env["completion_stage"]) != 2:
        raise RuntimeError(f"numeric eval must terminate at Stage2: {config_path}")
    if env["a2_door_open_lr_distribution"] != expected_side:
        raise RuntimeError(f"fixed-side config mismatch: {config_path}")
    if env["a2_grasp_gate_mode"] != "control_streak":
        raise RuntimeError(f"unsupported grasp gate: {config_path}")
    streak_steps = int(env["a2_grasp_streak_control_steps"])
    if streak_steps <= 0:
        raise RuntimeError(f"invalid grasp streak length: {config_path}")
    return {
        "checkpoint": str(config["checkpoint"]),
        "seed": int(config["seed"]),
        "completion_stage": 2,
        "grasp_gate_mode": "control_streak",
        "grasp_streak_control_steps": streak_steps,
        "contact_force_threshold_n": float(
            env["a2_stage2_contact_force_threshold"]
        ),
        "squeeze_force_min_n": float(env["a2_stage2_squeeze_force_min"]),
        "squeeze_force_max_n": float(env["a2_stage2_squeeze_force_max"]),
        "over_force_threshold_n": float(env["a2_stage2_over_force_threshold"]),
    }


def _load_trace(side_root: Path) -> dict[int, list[dict]]:
    trace_path = side_root / "eval/stage2_5_step_trace.json"
    rows = json.loads(trace_path.read_text(encoding="utf-8"))
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if int(row["episode_index"]) != 0 or row["first_episode_active"] is not True:
            raise RuntimeError(f"trace violates first-episode contract: {trace_path}")
        if int(row["stage_buf"]) != 2:
            raise RuntimeError(f"Stage0-2 trace contains non-Stage2 row: {trace_path}")
        grouped[int(row["env_id"])].append(row)
    for env_rows in grouped.values():
        env_rows.sort(key=lambda row: int(row["step_index"]))
    return dict(grouped)


def _clean_k_streak(rows: list[dict], streak_steps: int) -> bool:
    for index, row in enumerate(rows):
        if int(row["a2_stage2_squeeze_streak"]) < streak_steps:
            continue
        start = index + 1 - streak_steps
        if start < 0:
            return False
        window = rows[start : index + 1]
        step_indices = [int(item["step_index"]) for item in window]
        if any(
            current != previous + 1
            for previous, current in zip(step_indices, step_indices[1:])
        ):
            return False
        return all(
            item["squeeze_window"] is True and item["over_force"] is False
            for item in window
        )
    return False


def _summarize_side(
    side_root: Path, expected_side: str, expected_episodes: int
) -> dict:
    metrics_path = side_root / "eval/metrics_eval.json"
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    episodes = int(payload["completed_episodes"])
    stages = [int(value) for value in payload["episode_max_stage_reached"]]
    goals = [bool(value) for value in payload["episode_goal_reached"]]
    reasons = [str(value) for value in payload["episode_terminal_reasons"]]
    diagnostics = payload["episode_terminal_diagnostics"]
    if episodes != expected_episodes:
        raise RuntimeError(
            f"expected {expected_episodes} first episodes, got {episodes}: {metrics_path}"
        )
    if not all(
        len(values) == episodes
        for values in (stages, goals, reasons, diagnostics)
    ):
        raise RuntimeError(f"incomplete first-episode result set: {metrics_path}")

    contract = _load_contract(side_root, expected_side)
    streak_steps = contract["grasp_streak_control_steps"]
    traces = _load_trace(side_root)
    expected_sign = 1.0 if expected_side == "left" else -1.0
    observed_sides = {str(row["door_handle_side"]) for row in diagnostics}
    observed_signs = {float(row["door_open_lr"]) for row in diagnostics}
    if observed_sides != {expected_side} or observed_signs != {expected_sign}:
        raise RuntimeError(
            f"fixed-side evidence mismatch for {metrics_path}: "
            f"sides={observed_sides}, signs={observed_signs}"
        )

    episode_rows = {}
    for index, diagnostic in enumerate(diagnostics):
        env_id = int(diagnostic["env_id"])
        if env_id in episode_rows:
            raise RuntimeError(f"duplicate env_id={env_id}: {metrics_path}")
        stage = stages[index]
        goal = goals[index]
        reason = reasons[index]
        if stage > 2:
            raise RuntimeError(f"completion-stage eval reached Stage{stage}: {metrics_path}")
        if goal != ("complete" in reason.split("+")):
            raise RuntimeError(f"goal/terminal reason mismatch for env {env_id}")
        if goal and stage != 2:
            raise RuntimeError(f"Stage2 completion has max_stage={stage} for env {env_id}")
        if stage >= 1 and diagnostic["stage0_to1_staging_standoff"] is None:
            raise RuntimeError(f"Stage0->1 evidence mismatch for env {env_id}")
        env_trace = traces.get(env_id, [])
        if (stage >= 2) != bool(env_trace):
            raise RuntimeError(f"Stage1->2 trace evidence mismatch for env {env_id}")
        max_streak = max(
            (int(row["a2_stage2_squeeze_streak"]) for row in env_trace),
            default=0,
        )
        if goal != (max_streak >= streak_steps):
            raise RuntimeError(f"goal/K-streak evidence mismatch for env {env_id}")
        episode_rows[env_id] = {
            "stage": stage,
            "goal": goal,
            "reason": reason,
            "trace": env_trace,
            "max_streak": max_streak,
            "clean_k": goal and _clean_k_streak(env_trace, streak_steps),
        }
    if set(episode_rows) != set(range(expected_episodes)):
        raise RuntimeError(f"env_id coverage mismatch: {metrics_path}")

    rows = list(episode_rows.values())
    stage0_to1 = sum(row["stage"] >= 1 for row in rows)
    stage1_to2 = sum(row["stage"] >= 2 for row in rows)
    strict_complete = sum(row["goal"] for row in rows)
    clean_k = sum(row["clean_k"] for row in rows)
    bilateral_contact_ever = sum(
        any(trace_row["both_contact"] is True for trace_row in row["trace"])
        for row in rows
    )
    qualifying_squeeze_ever = sum(row["max_streak"] >= 1 for row in rows)
    overforce_episodes = sum(
        any(trace_row["over_force"] is True for trace_row in row["trace"])
        for row in rows
    )
    trace_rows = [trace_row for row in rows for trace_row in row["trace"]]
    overforce_frames = sum(row["over_force"] is True for row in trace_rows)
    max_contact_force = max(
        (
            max(float(value) for value in row["handle_contact_force_norm"])
            for row in trace_rows
        ),
        default=0.0,
    )

    return {
        "episodes": episodes,
        "raw_asset_side": expected_side,
        "door_open_lr_sign": expected_sign,
        "contract": contract,
        "stage0_to1": stage0_to1,
        "stage0_to1_rate": _rate(stage0_to1, episodes),
        "stage1_to2": stage1_to2,
        "stage1_to2_rate": _rate(stage1_to2, episodes),
        "strict_k_complete": strict_complete,
        "strict_k_complete_rate": _rate(strict_complete, episodes),
        "clean_k": clean_k,
        "clean_k_rate": _rate(clean_k, episodes),
        "bilateral_contact_ever": bilateral_contact_ever,
        "bilateral_contact_ever_rate": _rate(bilateral_contact_ever, episodes),
        "qualifying_squeeze_ever": qualifying_squeeze_ever,
        "qualifying_squeeze_ever_rate": _rate(
            qualifying_squeeze_ever, episodes
        ),
        "max_squeeze_streak_counts": dict(
            sorted(Counter(row["max_streak"] for row in rows).items())
        ),
        "overforce_episodes": overforce_episodes,
        "overforce_episode_rate": _rate(overforce_episodes, episodes),
        "overforce_frames": overforce_frames,
        "overforce_frame_fraction": _rate(overforce_frames, len(trace_rows))
        if trace_rows
        else 0.0,
        "max_handle_contact_force_n": max_contact_force,
        "failure_stage_counts": {
            "stage0_to1_failed": sum(row["stage"] == 0 for row in rows),
            "stage1_to2_failed": sum(row["stage"] == 1 for row in rows),
            "stage2_strict_grasp_failed": sum(
                row["stage"] == 2 and not row["goal"] for row in rows
            ),
        },
        "max_stage_counts": dict(
            sorted(Counter(row["stage"] for row in rows).items())
        ),
        "terminal_reason_counts": dict(
            sorted(Counter(row["reason"] for row in rows).items())
        ),
        "terminal_target_distance_median_m": _median(
            diagnostics, "target_pos_source_handle_distance"
        ),
        "episode_length_mean_steps": mean(payload["episode_lengths"]),
    }


def _candidate_summary(
    root: Path, candidate: str, expected_episodes: int
) -> dict:
    sides = {
        side: _summarize_side(root / candidate / side, side, expected_episodes)
        for side in SIDES
    }
    left = sides["left"]
    right = sides["right"]
    if left["contract"] != right["contract"]:
        raise RuntimeError(
            f"LEFT/RIGHT evaluation contract mismatch for candidate {candidate!r}: "
            f"left={left['contract']}, right={right['contract']}"
        )
    strict_counts = [left["strict_k_complete"], right["strict_k_complete"]]
    clean_counts = [left["clean_k"], right["clean_k"]]
    return {
        "sides": sides,
        "min_side_strict_k_complete": min(strict_counts),
        "min_side_clean_k": min(clean_counts),
        "total_strict_k_complete": sum(strict_counts),
        "worst_side_overforce_episode_rate": max(
            left["overforce_episode_rate"], right["overforce_episode_rate"]
        ),
        "strict_k_side_gap": abs(strict_counts[0] - strict_counts[1]),
        "min_side_stage1_to2": min(left["stage1_to2"], right["stage1_to2"]),
        "min_side_stage0_to1": min(left["stage0_to1"], right["stage0_to1"]),
    }


def main() -> int:
    args = _parse_args()
    root = args.root.expanduser().resolve()
    candidates = args.candidate

    summaries = {
        candidate: _candidate_summary(root, candidate, args.expected_episodes)
        for candidate in candidates
    }
    ranking_fields = (
        "min_side_strict_k_complete",
        "min_side_clean_k",
        "total_strict_k_complete",
        "worst_side_overforce_episode_rate",
        "strict_k_side_gap",
        "min_side_stage1_to2",
        "min_side_stage0_to1",
    )
    ranking = [
        {"candidate": candidate, **{key: summary[key] for key in ranking_fields}}
        for candidate, summary in summaries.items()
    ]
    ranking.sort(
        key=lambda row: (
            row["min_side_strict_k_complete"],
            row["min_side_clean_k"],
            row["total_strict_k_complete"],
            -row["worst_side_overforce_episode_rate"],
            -row["strict_k_side_gap"],
            row["min_side_stage1_to2"],
            row["min_side_stage0_to1"],
            row["candidate"],
        ),
        reverse=True,
    )
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema": "a2_piper_pull_lr_grasp_side_evaluation_summary_v1",
                "root": str(root),
                "candidates": summaries,
                "ranking": ranking,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
