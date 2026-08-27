#!/usr/bin/env python3
"""Reduce v26-2 bilateral natural Route A traces without causal overclaiming."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


CELLS = ("C", "A", "R", "W", "W_RELAY_S0", "W_RELAY_S1")
SIDES = ("left", "right")
EPISODES_PER_SIDE = 64
STEPS = (250, 500, 750)
TERMINAL_REQUIRED = (
    "max_handle_rad",
    "max_hinge_rad",
    "stage3_or_later",
    "stage4_or_later",
    "stage5_or_later",
    "k5_steps",
    "negative_close_steps",
    "bilateral_contact_steps",
    "opposite_squeeze_steps",
    "force_window_steps",
    "stable_contact_steps",
    "handle_depression_raw_income",
    "handle_depression_scaled_income",
    "handle_depression_active_steps",
    "unlatch_band_dwell_steps",
    "unlatch_hold_active_steps",
    "active_outside_stage3",
    "active_without_k5",
    "raw_nonzero_while_inactive",
    "stage4_below_threshold_on_first_admission",
    "integrity_violations",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--phase", choices=("wave1", "relay"), required=True,
        help="Wave1 evaluates C/A/R/W; relay evaluates the two admitted W relays.",
    )
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_number(mapping: dict[str, Any], key: str, label: str) -> float:
    value = mapping.get(key)
    require(not isinstance(value, bool) and isinstance(value, (int, float)), f"{label}.{key} must be numeric")
    return float(value)


def load_side(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("episode_terminal_diagnostics")
    require(isinstance(rows, list) and len(rows) == EPISODES_PER_SIDE, f"{path} must have exactly 64 terminal diagnostics")
    max_stages = payload.get("episode_max_stage_reached")
    goals = payload.get("episode_goal_reached")
    require(isinstance(max_stages, list) and len(max_stages) == EPISODES_PER_SIDE, f"{path} must have exactly 64 top-level max-stage values")
    require(isinstance(goals, list) and len(goals) == EPISODES_PER_SIDE, f"{path} must have exactly 64 top-level goal values")
    ids: set[int] = set()
    result: list[dict[str, Any]] = []
    for index, (row, max_stage, goal) in enumerate(zip(rows, max_stages, goals, strict=True)):
        label = f"{path}:episode[{index}]"
        require(isinstance(row, dict), f"{label} must be an object")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and not isinstance(env_id, bool) and 0 <= env_id < EPISODES_PER_SIDE and env_id not in ids, f"{label}.env_id is invalid or duplicate")
        ids.add(env_id)
        mechanism = row.get("v26_2")
        require(isinstance(mechanism, dict), f"{label}.v26_2 is required")
        for key in TERMINAL_REQUIRED:
            require_number(mechanism, key, f"{label}.v26_2")
        require(isinstance(max_stage, int) and not isinstance(max_stage, bool), f"{label}.max_stage[_reached] must be an int")
        require(isinstance(goal, bool), f"{label}.goal_reached must be bool")
        terminal_reason = row.get("terminal_reasons")
        control_dt = row.get("control_dt")
        require(isinstance(terminal_reason, str) and terminal_reason, f"{label}.terminal_reasons must be non-empty")
        require(not isinstance(control_dt, bool) and isinstance(control_dt, (int, float)) and float(control_dt) > 0.0, f"{label}.control_dt must be positive")
        require(bool(mechanism["stage3_or_later"]) == (max_stage >= 3), f"{label} disagrees about Stage3")
        require(bool(mechanism["stage4_or_later"]) == (max_stage >= 4), f"{label} disagrees about Stage4")
        require(bool(mechanism["stage5_or_later"]) == (max_stage >= 5), f"{label} disagrees about Stage5")
        result.append({"env_id": env_id, "max_stage": max_stage, "goal": goal, "terminal_reason": terminal_reason, "control_dt": float(control_dt), **mechanism})
    return result


def load_trace(path: Path, cell: str) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, list) and payload, f"{path} must be a non-empty expanded trace")
    raw_income = 0.0
    scaled_income = 0.0
    active_steps = 0
    integrity = {"active_outside_stage3": 0, "active_without_k5": 0, "raw_nonzero_while_inactive": 0, "stage4_below_threshold_on_first_admission": 0}
    for index, row in enumerate(payload):
        label = f"{path}:trace[{index}]"
        require(isinstance(row, dict), f"{label} must be an object")
        env_id = row.get("env_id")
        first_episode_active = row.get("first_episode_active")
        episode_index = row.get("episode_index")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES_PER_SIDE, f"{label}.env_id is invalid")
        require(isinstance(first_episode_active, bool), f"{label}.first_episode_active must be bool")
        require(isinstance(episode_index, int) and episode_index >= 0, f"{label}.episode_index must be non-negative int")
        if not first_episode_active:
            continue
        require(episode_index == 0, f"{label} mixes a non-first episode into a natural Route A trace")
        raw = row.get("reward_raw")
        scaled = row.get("reward_scaled")
        require(isinstance(raw, dict) and isinstance(scaled, dict), f"{label} requires reward_raw and reward_scaled mappings")
        mechanism = row.get("v26_2")
        require(isinstance(mechanism, dict), f"{label}.v26_2 is required")
        active = mechanism.get("handle_depression_active")
        strict_k5 = mechanism.get("strict_k5")
        first_stage4 = mechanism.get("first_stage4_admission")
        hinge_rad = mechanism.get("hinge_rad")
        require(isinstance(active, bool) and isinstance(strict_k5, bool) and isinstance(first_stage4, bool), f"{label}.v26_2 requires bool active/strict_k5/first_stage4_admission")
        require_number(mechanism, "hinge_rad", f"{label}.v26_2")
        require(isinstance(row.get("stage_buf"), int) and not isinstance(row.get("stage_buf"), bool), f"{label}.stage_buf must be an int")
        active_steps += int(active)
        integrity["active_outside_stage3"] += int(active and row["stage_buf"] != 3)
        integrity["active_without_k5"] += int(active and not strict_k5)
        integrity["stage4_below_threshold_on_first_admission"] += int(first_stage4 and float(hinge_rad) < 0.25)
        if cell in {"R", "W", "W_RELAY_S0", "W_RELAY_S1"}:
            raw_value = require_number(raw, "a2_stage3_handle_depression", f"{label}.reward_raw")
            raw_income += raw_value
            scaled_income += require_number(scaled, "a2_stage3_handle_depression", f"{label}.reward_scaled")
            integrity["raw_nonzero_while_inactive"] += int(raw_value != 0.0 and not active)
        else:
            require("a2_stage3_handle_depression" not in raw and "a2_stage3_handle_depression" not in scaled, f"{label} exposes an inactive depression term")
    return {"raw_income": raw_income, "scaled_income": scaled_income, "active_steps": active_steps, **integrity}


def summarize(rows: list[dict[str, Any]], trace: dict[str, float]) -> dict[str, Any]:
    count = len(rows)
    require(count == EPISODES_PER_SIDE, "a side summary requires exactly 64 natural episodes")
    sums = {key: sum(float(row[key]) for row in rows) for key in TERMINAL_REQUIRED if key not in {"stage3_or_later", "stage4_or_later", "stage5_or_later"}}
    active = sums["handle_depression_active_steps"]
    require(sums["handle_depression_active_steps"] == trace["active_steps"], "terminal and expanded-trace active-step counts disagree")
    tolerance = lambda left, right: 1.0e-4 + 2.0e-6 * max(abs(left), abs(right))
    require(math.isclose(sums["handle_depression_raw_income"], trace["raw_income"], rel_tol=2.0e-6, abs_tol=tolerance(sums["handle_depression_raw_income"], trace["raw_income"])), "terminal and expanded-trace raw income disagree beyond float32 accumulation tolerance")
    require(math.isclose(sums["handle_depression_scaled_income"], trace["scaled_income"], rel_tol=2.0e-6, abs_tol=tolerance(sums["handle_depression_scaled_income"], trace["scaled_income"])), "terminal and expanded-trace scaled income disagree beyond float32 accumulation tolerance")
    for key in ("active_outside_stage3", "active_without_k5", "raw_nonzero_while_inactive", "stage4_below_threshold_on_first_admission"):
        require(sums[key] == trace[key], f"terminal and expanded-trace {key} disagree")
    require(sums["integrity_violations"] == sum(trace[key] for key in ("active_outside_stage3", "active_without_k5", "raw_nonzero_while_inactive", "stage4_below_threshold_on_first_admission")), "terminal integrity total disagrees with expanded trace")
    return {
        "episodes": count,
        "stage3_or_later": sum(bool(row["stage3_or_later"]) for row in rows),
        "stage4_or_later": sum(bool(row["stage4_or_later"]) for row in rows),
        "stage5_or_later": sum(bool(row["stage5_or_later"]) for row in rows),
        "goals": sum(bool(row["goal"]) for row in rows),
        "stable_handle_ge_0_3": sum(float(row["max_handle_rad"]) >= 0.3 for row in rows),
        "handle_ge_0_6": sum(float(row["max_handle_rad"]) >= 0.6 for row in rows),
        "handle_ge_0_6_and_hinge_ge_0_1": sum(float(row["max_handle_rad"]) >= 0.6 and float(row["max_hinge_rad"]) >= 0.1 for row in rows),
        "hinge_ge_0_1": sum(float(row["max_hinge_rad"]) >= 0.1 for row in rows),
        "hinge_ge_0_25": sum(float(row["max_hinge_rad"]) >= 0.25 for row in rows),
        "max_stage_counts": dict(sorted(Counter(row["max_stage"] for row in rows).items())),
        "terminal_reason_counts": dict(sorted(Counter(row["terminal_reason"] for row in rows).items())),
        "control_dt_s": sorted({row["control_dt"] for row in rows}),
        "mechanism_sums": sums,
        "expanded_trace_mechanism": trace,
        "handle_depression_active_step_mean_income": None if active == 0.0 else sums["handle_depression_scaled_income"] / active,
    }


def load_metadata(path: Path, cell: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path} must be an object")
    require(isinstance(payload.get("first_episode_contract"), str) and payload["first_episode_contract"], f"{path}.first_episode_contract is required")
    require(isinstance(payload.get("trace_timing"), dict) and payload["trace_timing"], f"{path}.trace_timing is required")
    terms = payload.get("reward_terms")
    require(isinstance(terms, list) and all(isinstance(term, str) and term for term in terms), f"{path}.reward_terms must be non-empty strings")
    depression = "a2_stage3_handle_depression"
    if cell in {"R", "W", "W_RELAY_S0", "W_RELAY_S1"}:
        require(depression in terms, f"{path} omits the active depression reward term")
    else:
        require(depression not in terms, f"{path} includes an inactive depression reward term")
    return {"first_episode_contract": payload["first_episode_contract"], "trace_timing": payload["trace_timing"], "reward_terms": terms}


def wave1_outcome(summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    admitted = []
    retained = []
    handle_created = []
    wall_removed = []
    for step in STEPS:
        label = f"W_STEP{step:04d}"
        w = summary[label]
        w_retained = all(side["stage3_or_later"] >= 32 for side in w.values())
        w_admitted = w_retained and all(
            (side["stage4_or_later"] >= 2 or side["handle_ge_0_6_and_hinge_ge_0_1"] >= 2)
            and side["mechanism_sums"]["integrity_violations"] == 0.0
            for side in w.values()
        )
        a, r = (summary[f"{cell}_STEP{step:04d}"] for cell in ("A", "R"))
        a_to_r = all(r[side]["stable_handle_ge_0_3"] > a[side]["stable_handle_ge_0_3"] for side in SIDES)
        r_to_w = all(
            w[side]["stage4_or_later"] > r[side]["stage4_or_later"]
            or w[side]["mechanism_sums"]["unlatch_band_dwell_steps"] > r[side]["mechanism_sums"]["unlatch_band_dwell_steps"]
            for side in SIDES
        )
        score = (min(side["stage4_or_later"] for side in w.values()), min(side["stage3_or_later"] for side in w.values()), min(side["goals"] for side in w.values()), label)
        if w_admitted:
            admitted.append(score)
        if w_retained:
            retained.append(score)
        if a_to_r:
            handle_created.append(score)
        if r_to_w:
            wall_removed.append(score)
    if admitted:
        return {"status": "WAVE1_W_ADMITTED", "relay_allowed": True, "selected_w_label": max(admitted)[-1]}
    if not retained:
        return {"status": "NOT_ADMITTED_ACQUISITION_REGRESSION", "relay_allowed": False}
    if not handle_created:
        return {"status": "HANDLE_CREATION_NOT_SUPPORTED", "relay_allowed": False}
    if not wall_removed:
        return {"status": "WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH", "relay_allowed": False}
    return {"status": "NOT_ADMITTED_INTEGRITY_OR_ADMISSION", "relay_allowed": False}


def causal_claims(summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if "A_STEP0250" not in summary:
        return {}
    claims = {}
    for step in STEPS:
        a, r, w = (summary[f"{cell}_STEP{step:04d}"] for cell in ("A", "R", "W"))
        handle_created = all(r[side]["stable_handle_ge_0_3"] > a[side]["stable_handle_ge_0_3"] for side in SIDES)
        wall_removed = all(w[side]["stage4_or_later"] > r[side]["stage4_or_later"] or w[side]["mechanism_sums"]["unlatch_band_dwell_steps"] > r[side]["mechanism_sums"]["unlatch_band_dwell_steps"] for side in SIDES)
        claims[f"step{step:04d}"] = {"A_to_R_handle_creation": "SUPPORTED" if handle_created else "HANDLE_CREATION_NOT_SUPPORTED", "R_to_W_wall_removal": "SUPPORTED" if wall_removed else "WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH", "A_to_W": "NOT_A_SINGLE_FACTOR_COMPARISON", "C_to_R": "UNGATED_VS_K5_GATED_SCALE6_DESCRIPTIVE_COMPARISON_ONLY"}
    return claims


def relay_outcome(summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for step in STEPS:
        if all(
            summary[f"{cell}_STEP{step:04d}"][side]["stage4_or_later"] >= 48
            and summary[f"{cell}_STEP{step:04d}"][side]["mechanism_sums"]["integrity_violations"] == 0.0
            for cell in ("W_RELAY_S0", "W_RELAY_S1") for side in SIDES
        ):
            return {"status": "V26_2_UNLOCK_CAPABILITY_PASS", "relay_allowed": False, "selected_relay_label": f"STEP{step:04d}"}
    return {"status": "SUPPORTED_BUT_SEED_UNSTABLE", "relay_allowed": False}


def main() -> None:
    args = parse_args()
    root = args.eval_root.resolve()
    allowed = ("C", "A", "R", "W") if args.phase == "wave1" else ("W_RELAY_S0", "W_RELAY_S1")
    summary: dict[str, dict[str, Any]] = {}
    provenance: dict[str, dict[str, Any]] = {}
    for cell in allowed:
        for step in STEPS:
            label = f"{cell}_STEP{step:04d}"
            cell_summary = {}
            for side in SIDES:
                path = root / label / side / "metrics_eval.json"
                trace_path = root / label / side / "stage2_5_step_trace.json"
                metadata_path = root / label / side / "a2_eval_diagnostic_metadata.json"
                require(path.is_file(), f"required Route A metrics are missing: {path}")
                require(trace_path.is_file(), f"required Route A trace is missing: {trace_path}")
                require(metadata_path.is_file(), f"required Route A diagnostic metadata is missing: {metadata_path}")
                cell_summary[side] = summarize(load_side(path), load_trace(trace_path, cell))
                provenance.setdefault(label, {})[side] = load_metadata(metadata_path, cell)
            summary[label] = cell_summary
    outcome = wave1_outcome(summary) if args.phase == "wave1" else relay_outcome(summary)
    payload = {
        "schema": "a2_piper_base_v26_2_mechanism_trace_v1",
        "phase": args.phase,
        "natural_route_a_only": True,
        "episodes_per_side": EPISODES_PER_SIDE,
        "cells": summary,
        "provenance": provenance,
        "outcome": outcome,
        "causal_claims": causal_claims(summary),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
