#!/usr/bin/env python3
"""Reduce the V6.1Q env14 baseline and admitted A/B/C/D intervention traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trace_utils import first_episode_rows, load_trace, nested, required, summary_from_rows


INTERVENTION_FIELDS = {
    "a2_pull_v61_post_release_intervention_active",
    "pull_v61_post_release_intervention",
    "pull_v61_post_release_terminal_snapshot",
}
BASELINE_PREFIX_FIELDS = (
    "env_id", "episode_index", "step_index", "stage_buf",
    "door_hinge_joint_pos", "door_hinge_joint_vel", "root_pos_w", "root_quat_w",
    "root_lin_vel_w", "policy_high_level_action_raw",
    "post_forced_override_pre_env_action", "post_delta_post_warp_env_action",
    "pull_v0", "pull_v3_traversal", "terminal_reasons",
)
BASELINE_VITAL_FIELDS = (
    "e5_step", "clean_release_step", "release_persistence_k25_step",
    "frame_passage_step", "e6_step", "e7_step", "base_path_length_m",
    "base_reversal_count", "post_release_recontact_count",
    "hinge_reclosure_after_release_rad", "post_release_contact_steps",
    "terminal_reason_post_step", "terminal_complete_post_step",
)


def _trace_arg(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if separator != "=" or label not in {"A", "B", "C", "D"}:
        raise ValueError("--trace must be A|B|C|D=/path/to/stage2_5_step_trace.json")
    return label, Path(path)


def _intervention_start(rows: list[dict[str, Any]]) -> int:
    for index, row in enumerate(rows):
        intervention = nested(row, "pull_v0", "pull_v61_post_release_intervention")
        if not isinstance(intervention, dict):
            raise TypeError("pull_v61_post_release_intervention must be a mapping")
        if bool(required(intervention, "active", "pull_v61_post_release_intervention")):
            return index
    raise ValueError("V6.1 trace has no intervention-active row")


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= 1.0e-6
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right, strict=True))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_equal(left[key], right[key]) for key in left)
    return left == right


def _without_intervention(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in row.items() if key not in INTERVENTION_FIELDS}
    pull_v0 = cleaned.get("pull_v0")
    if isinstance(pull_v0, dict):
        pull_v0 = {key: value for key, value in pull_v0.items() if key not in INTERVENTION_FIELDS}
        cleaned["pull_v0"] = pull_v0
    return cleaned


def _assert_rows_match(
    reference: list[dict[str, Any]], candidate: list[dict[str, Any]], *, label: str
) -> None:
    if len(reference) != len(candidate):
        raise ValueError(f"{label} row count differs: {len(reference)} != {len(candidate)}")
    for row_index, (left, right) in enumerate(zip(reference, candidate, strict=True)):
        left = _without_intervention(left)
        right = _without_intervention(right)
        if not _equal(left, right):
            differing = sorted(
                key for key in left.keys() | right.keys()
                if key not in left or key not in right or not _equal(left[key], right[key])
            )
            raise ValueError(f"{label} mismatch row={row_index} fields={differing}")


def _assert_baseline_prefix(
    baseline: list[dict[str, Any]], cell_a_prefix: list[dict[str, Any]]
) -> None:
    if len(baseline) < len(cell_a_prefix):
        raise ValueError("baseline trace ends before the cell-A intervention boundary")
    for row_index, (left, right) in enumerate(
        zip(baseline[:len(cell_a_prefix)], cell_a_prefix, strict=True)
    ):
        for field in BASELINE_PREFIX_FIELDS:
            left_value = required(left, field, "baseline row")
            right_value = required(right, field, "cell-A row")
            if field == "pull_v0":
                left_value = {
                    key: value for key, value in left_value.items() if key not in INTERVENTION_FIELDS
                }
                right_value = {
                    key: value for key, value in right_value.items() if key not in INTERVENTION_FIELDS
                }
            if not _equal(left_value, right_value):
                raise ValueError(f"cell A does not reproduce baseline prefix row={row_index} field={field}")


def _assert_action_contract(label: str, rows: list[dict[str, Any]], start: int) -> None:
    mode = {"A": "policy", "B": "arm_reset", "C": "base_corridor", "D": "both"}[label]
    for row_index, row in enumerate(rows):
        intervention = nested(row, "pull_v0", "pull_v61_post_release_intervention")
        if required(intervention, "mode", "pull_v61_post_release_intervention") != mode:
            raise ValueError(f"cell {label} mode mismatch")
        policy = required(intervention, "policy_action", "pull_v61_post_release_intervention")
        applied = required(intervention, "applied_action", "pull_v61_post_release_intervention")
        if row_index < start or label == "A":
            if not _equal(policy, applied):
                raise ValueError(f"cell {label} changes action before its registered intervention boundary")
            continue
        preserved = (2, 3, 4, 11)
        if label == "B":
            preserved = (0, 1, 2, 3, 4, 11)
        elif label == "C":
            preserved = tuple(range(2, 12))
        for axis in preserved:
            if not _equal(policy[axis], applied[axis]):
                raise ValueError(f"cell {label} violates action-slice ownership at axis {axis}")


def _write_report(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", action="append", required=True, type=_trace_arg)
    parser.add_argument("--baseline-trace", type=Path)
    parser.add_argument("--target-env-id", type=int, default=14)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    traces = dict(args.trace)
    if set(traces) not in ({"A"}, {"A", "B", "C", "D"}):
        raise ValueError("provide baseline A alone or exactly A/B/C/D")
    loaded = {label: load_trace(path) for label, path in traces.items()}
    target_rows = {
        label: first_episode_rows(rows, args.target_env_id) for label, rows in loaded.items()
    }
    reduced = {label: summary_from_rows(rows) for label, rows in sorted(target_rows.items())}
    report: dict[str, Any] = {
        "schema": "a2_piper_pull_v61_counterfactual_report_v1",
        "target_env_id": args.target_env_id,
        "cells": reduced,
        "admission": "BASELINE_ONLY" if set(traces) == {"A"} else "NOT_ADMITTED",
    }
    if set(traces) == {"A", "B", "C", "D"}:
        if args.baseline_trace is None:
            raise ValueError("full A/B/C/D admission requires --baseline-trace")
        try:
            starts = {label: _intervention_start(rows) for label, rows in target_rows.items()}
            start_steps = {
                label: required(rows[index], "step_index", "intervention start row")
                for label, rows in target_rows.items() for index in (starts[label],)
            }
            if len(set(start_steps.values())) != 1:
                raise ValueError(f"intervention start steps differ: {start_steps}")
            boundary_policy_actions = {
                label: nested(
                    rows[starts[label]], "pull_v0", "pull_v61_post_release_intervention", "policy_action"
                )
                for label, rows in target_rows.items()
            }
            for label in ("B", "C", "D"):
                if not _equal(boundary_policy_actions["A"], boundary_policy_actions[label]):
                    raise ValueError(
                        f"cell {label} policy_action differs from A at intervention boundary"
                    )
            for label, rows in target_rows.items():
                clean_release = reduced[label]["clean_release_step"]
                if clean_release is None or start_steps[label] != clean_release + 1:
                    raise ValueError(
                        f"cell {label} first intervention is not clean-release+1: "
                        f"release={clean_release}, start={start_steps[label]}"
                    )
                _assert_action_contract(label, rows, starts[label])
            for label in ("B", "C", "D"):
                _assert_rows_match(
                    target_rows["A"][:starts["A"]],
                    target_rows[label][:starts[label]],
                    label=f"cell-{label} target prefix",
                )
            baseline_rows = first_episode_rows(load_trace(args.baseline_trace), args.target_env_id)
            _assert_baseline_prefix(baseline_rows, target_rows["A"][:starts["A"]])
            baseline_summary = summary_from_rows(baseline_rows)
            for field in BASELINE_VITAL_FIELDS:
                if not _equal(baseline_summary[field], reduced["A"][field]):
                    raise ValueError(f"cell A baseline vital mismatch field={field}")
            observed_env_ids = {
                label: sorted({
                    int(row["env_id"]) for row in rows
                    if row.get("episode_index") == 0 and row.get("first_episode_active") is True
                })
                for label, rows in loaded.items()
            }
            env_ids = observed_env_ids["A"]
            if args.target_env_id not in env_ids:
                raise ValueError(
                    f"counterfactual trace does not contain target env{args.target_env_id}: {env_ids}"
                )
            for label in ("B", "C", "D"):
                if observed_env_ids[label] != env_ids:
                    raise ValueError(
                        f"cell {label} observed env set differs from A: "
                        f"A={env_ids}, {label}={observed_env_ids[label]}"
                    )
            for env_id in env_ids:
                if env_id == args.target_env_id:
                    continue
                reference = first_episode_rows(loaded["A"], env_id)
                for label in ("B", "C", "D"):
                    _assert_rows_match(
                        reference,
                        first_episode_rows(loaded[label], env_id),
                        label=f"cell-{label} non-target env{env_id}",
                    )
        except ValueError as error:
            report["admission_reason"] = str(error)
            _write_report(args.output, report)
            return 2
        report["admission"] = "ADMITTED"
        report["observed_stage2_5_env_ids"] = env_ids
        report["intervention_start_steps"] = start_steps
        report["intervention_boundary_policy_action"] = boundary_policy_actions["A"]
        report["scope"] = "matched env14 post-release counterfactual only; no population inference"
    _write_report(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
