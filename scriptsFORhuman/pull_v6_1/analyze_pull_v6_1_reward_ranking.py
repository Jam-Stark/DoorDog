#!/usr/bin/env python3
"""Compare full and event-aligned Pull-v6.1 reward sequences without a PPO-preference claim."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from trace_utils import first_episode_rows, first_step_with, load_trace, nested, required


def _trace_arg(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if separator != "=" or not label or not path:
        raise ValueError("--trace must be label=/path/to/stage2_5_step_trace.json")
    return label, Path(path)


def _category(term: str) -> str:
    if term.startswith(("a2_stage3_stage4_", "a2_stage4_")):
        return "legacy_stage4_hold_income"
    if any(token in term for token in ("contact", "force", "push", "recontact")):
        return "contact_safety"
    if any(token in term for token in (
        "arm_default", "arm_tuck", "upper_body", "dof", "roll_pitch", "orientation",
        "face_door", "standing_still", "gripper", "delta_action_rate", "ref_dof",
    )):
        return "posture_arm_compactness"
    if term in {"termination", "success_save_time"}:
        return "time_termination"
    return "progress_one_shot"


def _partition(per_term: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = defaultdict(float)
    for term, value in per_term.items():
        result[_category(term)] += value
    return dict(sorted(result.items()))


def _window(rows: list[dict[str, Any]], start: int, stop: int, gamma: float) -> dict[str, Any]:
    per_term: dict[str, float] = defaultdict(float)
    expected_terms: set[str] | None = None
    previous_termination_sum = 0.0
    if start > 0:
        previous_episode_sums = required(rows[start - 1], "reward_episode_sums", "pre-window row")
        if not isinstance(previous_episode_sums, dict):
            raise TypeError("pre-window row.reward_episode_sums must be a mapping")
        previous_termination_sum = float(required(
            previous_episode_sums, "termination", "pre-window row.reward_episode_sums"
        ))
    for absolute_index, row in enumerate(rows[start:stop], start):
        reward = required(row, "reward_scaled", "row")
        if not isinstance(reward, dict):
            raise TypeError("row.reward_scaled must be a mapping")
        terms = set(reward)
        if expected_terms is None:
            expected_terms = terms
        elif terms != expected_terms:
            raise ValueError("reward_scaled term set changed inside one episode")
        discount = gamma ** (absolute_index - start)
        for term, value in reward.items():
            per_term[term] += discount * float(value)
        episode_sums = required(row, "reward_episode_sums", "row")
        if not isinstance(episode_sums, dict):
            raise TypeError("row.reward_episode_sums must be a mapping")
        termination_sum = float(required(episode_sums, "termination", "row.reward_episode_sums"))
        per_term["termination"] += discount * (termination_sum - previous_termination_sum)
        previous_termination_sum = termination_sum
    ordered = dict(sorted(per_term.items()))
    return {
        "steps": stop - start,
        "total": sum(ordered.values()),
        "categories": _partition(ordered),
        "per_term": ordered,
    }


def _resolved_gamma(path: Path) -> float:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise TypeError("resolved config must be a mapping")
    algo = required(config, "algo", "resolved config")
    if not isinstance(algo, dict):
        raise TypeError("resolved config.algo must be a mapping")
    algo_config = required(algo, "config", "resolved config.algo")
    if not isinstance(algo_config, dict):
        raise TypeError("resolved config.algo.config must be a mapping")
    gamma = required(algo_config, "gamma", "resolved config.algo.config")
    if isinstance(gamma, bool) or not isinstance(gamma, (int, float)) or not 0.0 < float(gamma) <= 1.0:
        raise ValueError(f"resolved config gamma must lie in (0, 1], got {gamma!r}")
    return float(gamma)


def _cell(path: Path, env_id: int, equal_horizon_steps: int, gamma: float) -> dict[str, Any]:
    rows = first_episode_rows(load_trace(path), env_id)
    release = first_step_with(
        rows, lambda row: bool(nested(row, "pull_v0", "pull_v6", "clean_release"))
    )
    if release is None:
        raise ValueError(f"reward-ranking cell has no clean release: {path}")
    episode_sums = required(rows[-1], "reward_episode_sums", "terminal row")
    if not isinstance(episode_sums, dict):
        raise TypeError("terminal row.reward_episode_sums must be a mapping")
    full_per_term = {term: float(value) for term, value in sorted(episode_sums.items())}
    trace_reward = required(rows[release], "reward_scaled", "clean-release row")
    if not isinstance(trace_reward, dict):
        raise TypeError("clean-release row.reward_scaled must be a mapping")
    trace_terms = set(trace_reward)
    missing_trace_terms = set(full_per_term) - trace_terms
    if missing_trace_terms != {"termination"} or trace_terms - set(full_per_term):
        raise ValueError(
            "reward-ranking trace must capture every active reward term; termination is the sole "
            "allowed episode-sum delta term; "
            f"missing={sorted(missing_trace_terms)}, "
            f"extra={sorted(trace_terms - set(full_per_term))}"
        )
    tail_steps = [required(row, "step_index", "row") for row in rows[release:]]
    if tail_steps != list(range(tail_steps[0], tail_steps[0] + len(tail_steps))):
        raise ValueError("release tail step_index must be contiguous")
    if len(rows) - release < equal_horizon_steps:
        raise ValueError(
            f"release tail is shorter than registered equal horizon: "
            f"{len(rows) - release} < {equal_horizon_steps}"
        )
    equal_stop = release + equal_horizon_steps
    return {
        "trace": str(path),
        "env_id": env_id,
        "clean_release_step": required(rows[release], "step_index", "clean-release row"),
        "terminal_step": required(rows[-1], "step_index", "terminal row"),
        "terminal_reason_post_step": required(rows[-1], "terminal_reasons", "terminal row"),
        "terminal_complete_post_step": bool(nested(rows[-1], "pull_v0_episode", "whole_body_clear")),
        "full_episode": {
            "total": sum(full_per_term.values()),
            "categories": _partition(full_per_term),
            "per_term": full_per_term,
        },
        "clean_release_tail": _window(rows, release, len(rows), 1.0),
        "equal_horizon_tail": _window(rows, release, equal_stop, 1.0),
        "discounted_clean_release_tail": _window(rows, release, len(rows), gamma),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", action="append", type=_trace_arg, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-env-id", type=int, default=14)
    parser.add_argument("--equal-horizon-steps", type=int, default=569)
    parser.add_argument("--training-config", type=Path, required=True)
    args = parser.parse_args()
    if args.equal_horizon_steps <= 0:
        raise ValueError("equal-horizon-steps must be positive.")
    gamma = _resolved_gamma(args.training_config)
    traces = dict(args.trace)
    if len(traces) != len(args.trace):
        raise ValueError("reward-ranking trace labels must be unique")
    try:
        cells = {
            label: _cell(path, args.target_env_id, args.equal_horizon_steps, gamma)
            for label, path in sorted(traces.items())
        }
    except ValueError as error:
        report = {
            "schema": "a2_piper_pull_v61_reward_ranking_report_v1",
            "target_env_id": args.target_env_id,
            "equal_horizon_steps": args.equal_horizon_steps,
            "gamma": gamma,
            "gamma_provenance": f"{args.training_config}:algo.config.gamma",
            "admission": "NOT_ADMITTED",
            "admission_reason": str(error),
            "claim_boundary": "No reward-sequence ranking is admitted from unequal horizons.",
        }
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, allow_nan=False))
        return 2
    metrics = (
        "full_episode", "clean_release_tail", "equal_horizon_tail",
        "discounted_clean_release_tail",
    )
    report = {
        "schema": "a2_piper_pull_v61_reward_ranking_report_v1",
        "target_env_id": args.target_env_id,
        "equal_horizon_steps": args.equal_horizon_steps,
        "gamma": gamma,
        "gamma_provenance": f"{args.training_config}:algo.config.gamma",
        "admission": "ADMITTED",
        "cells": cells,
        "reward_sequence_rankings_high_to_low": {
            metric: sorted(cells, key=lambda label: cells[label][metric]["total"], reverse=True)
            for metric in metrics
        },
        "claim_boundary": (
            "Discounting follows the configured training gamma and terminal reward sequence. "
            "No common-anchor critic evidence is present, so this report does not claim PPO preference."
        ),
    }
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
