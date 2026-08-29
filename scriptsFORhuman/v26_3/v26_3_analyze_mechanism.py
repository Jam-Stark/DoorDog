#!/usr/bin/env python3
"""Reduce v26-3 natural traces and emit typed diagnostic/conditional closure evidence."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml


SIDES = ("left", "right")
MAIN_CELLS = ("M0_S0", "M0_S1", "M1_S0", "M1_S1")
STEPS = (125, 250, 500, 750)
ROOT = Path(__file__).resolve().parents[2]
SOURCE_W = str(
    ROOT / "logs_rl/by_batch/base_v26_2_pull_derived_20260825/wave1/W/model_step_000750.pt"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("diagnostics", "main", "conditional", "final", "closure"), required=True
    )
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--diagnostic-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def number(value: Any, label: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{label} must be numeric")
    result = float(value)
    require(math.isfinite(result), f"{label} must be finite")
    return result


def load_json(path: Path) -> Any:
    require(path.is_file(), f"required artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def longest_true_run(values: list[bool]) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=3.0e-6, abs_tol=2.0e-4 + 3.0e-6 * max(abs(left), abs(right)))


def load_runtime_config(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"runtime config is missing: {path}")
    payload = yaml.unsafe_load(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"runtime config must be a mapping: {path}")
    return payload


def validate_action_intervention(rows: list[dict[str, Any]], mode: str, metadata: dict[str, Any]) -> dict[str, int]:
    applied_key = (
        "stage2_close_gate_forced_gripper_close_applied"
        if mode == "E1"
        else "forced_gripper_close_applied"
    )
    applied = 0
    for index, row in enumerate(rows):
        if not row.get("first_episode_active"):
            continue
        flag = row.get(applied_key)
        require(isinstance(flag, bool), f"trace[{index}].{applied_key} must be bool")
        raw = row.get("policy_high_level_action_raw")
        post = row.get("post_forced_override_pre_env_action")
        require(isinstance(raw, list) and isinstance(post, list) and len(raw) == len(post) == 12, f"trace[{index}] action audit must have 12 dimensions")
        if flag:
            applied += 1
            require(all(close(number(raw[i], "raw action"), number(post[i], "post action")) for i in range(11)), f"{mode} changed a non-gripper action dimension")
            require(close(number(post[11], "post gripper"), -1.0), f"{mode} gripper override is not -1")
            stage = row.get("stage_buf")
            if mode == "E1":
                require(stage == 2, "E1 applied outside Stage2")
            else:
                require(stage in (3, 4), "E2 applied outside Stage3/4")
    metadata_key = (
        "stage2_close_gate_forced_gripper_close_applied_counts"
        if mode == "E1"
        else "forced_gripper_close_applied_counts"
    )
    counts = metadata.get(metadata_key)
    require(isinstance(counts, list) and sum(int(value) for value in counts) == applied, f"{mode} metadata/action trace applied counts disagree")
    return {"applied_steps": applied}


def load_side(path: Path, expected: int, reference: float, mode: str) -> dict[str, Any]:
    metrics = load_json(path / "metrics_eval.json")
    records = load_json(path / "a2_v14_per_env_records.json")
    trace = load_json(path / "stage2_5_step_trace.json")
    metadata = load_json(path / "a2_eval_diagnostic_metadata.json")
    config = load_runtime_config(path / ".hydra/runtime_config.yaml")
    require(isinstance(metrics, dict), f"metrics must be a mapping: {path}")
    terminal = metrics.get("episode_terminal_diagnostics")
    stages = metrics.get("episode_max_stage_reached")
    goals = metrics.get("episode_goal_reached")
    require(isinstance(terminal, list) and len(terminal) == expected, f"{path} requires exact{expected} terminal rows")
    require(isinstance(records, list) and len(records) == expected, f"{path} requires exact{expected} per-env rows")
    require(isinstance(stages, list) and len(stages) == expected, f"{path} requires exact{expected} max-stage rows")
    require(isinstance(goals, list) and len(goals) == expected, f"{path} requires exact{expected} goal rows")
    require(isinstance(trace, list) and trace, f"{path} requires a non-empty expanded trace")
    require(isinstance(metadata, dict), f"metadata must be a mapping: {path}")

    eval_cfg = config["algo"]["config"]["eval"]
    env_cfg = config["env"]["config"]
    require(config.get("checkpoint_load_mode") == "full" and config.get("auto_load_latest") is False, f"{path} must full-load an exact checkpoint")
    require(config.get("num_envs") == expected, f"{path} num_envs is not exact{expected}")
    require(eval_cfg.get("num_eval_episodes") == expected and eval_cfg.get("eval_num_envs_episodes") is True, f"{path} first-episode contract is not exact{expected}")
    require(env_cfg.get("enable_staged_reset") is False, f"{path} is not natural start")
    expected_side = path.name
    require(env_cfg.get("a2_v26_door_open_lr") == expected_side, f"{path} side override mismatch")
    natural = mode in {"NATURAL", "D0", "D3"}
    if natural:
        require(metadata.get("forced_gripper_close_enabled") is False, f"{path} generic override is enabled")
        require(metadata.get("stage2_close_gate_forced_gripper_close_enabled") is False, f"{path} E1 override is enabled")
    elif mode == "E1":
        require(metadata.get("stage2_close_gate_forced_gripper_close_enabled") is True and metadata.get("forced_gripper_close_enabled") is False, f"{path} E1 selector metadata mismatch")
    elif mode == "E2":
        require(metadata.get("forced_gripper_close_enabled") is True and metadata.get("stage2_close_gate_forced_gripper_close_enabled") is False, f"{path} E2 selector metadata mismatch")

    by_env: dict[int, list[dict[str, Any]]] = defaultdict(list)
    old_trace_raw = old_trace_scaled = creation_trace_raw = creation_trace_scaled = 0.0
    for index, row in enumerate(trace):
        require(isinstance(row, dict), f"{path}:trace[{index}] must be a mapping")
        first_episode_active = row.get("first_episode_active")
        require(isinstance(first_episode_active, bool), f"{path}:trace[{index}] first_episode_active must be bool")
        if not first_episode_active:
            continue
        require(row.get("episode_index") == 0, f"{path}:trace[{index}] mixes a later episode into first-episode evidence")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < expected, f"{path}:trace[{index}] env_id invalid")
        require(number(row.get("control_dt"), "trace control_dt") > 0.0, "control_dt must be positive")
        by_env[env_id].append(row)
        raw = row.get("reward_raw")
        scaled = row.get("reward_scaled")
        require(isinstance(raw, dict) and isinstance(scaled, dict), f"{path}:trace[{index}] reward maps missing")
        old_trace_raw += number(raw.get("a2_stage3_handle_depression", 0.0), "old raw")
        old_trace_scaled += number(scaled.get("a2_stage3_handle_depression", 0.0), "old scaled")
        creation_trace_raw += number(raw.get("a2_stage3_handle_creation", 0.0), "creation raw")
        creation_trace_scaled += number(scaled.get("a2_stage3_handle_creation", 0.0), "creation scaled")
    episode_rows: list[dict[str, Any]] = []
    old_terminal_raw = old_terminal_scaled = creation_terminal_raw = creation_terminal_scaled = 0.0
    integrity = 0
    for index, (row, stage, goal) in enumerate(zip(terminal, stages, goals, strict=True)):
        require(isinstance(row, dict), f"{path}:terminal[{index}] must be a mapping")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < expected, f"{path}:terminal[{index}] env_id invalid")
        require(isinstance(stage, int) and not isinstance(stage, bool), f"{path}:max stage invalid")
        require(isinstance(goal, bool), f"{path}:goal invalid")
        v2 = row.get("v26_2")
        v3 = row.get("v26_3")
        require(isinstance(v2, dict) and isinstance(v3, dict), f"{path}:terminal[{index}] v26 telemetry missing")
        handle_highwater = number(v3.get("handle_highwater"), "handle highwater")
        max_hinge = number(v2.get("max_hinge_rad"), "max hinge")
        old_raw = number(v2.get("handle_depression_raw_income"), "old terminal raw")
        old_scaled = number(v2.get("handle_depression_scaled_income"), "old terminal scaled")
        creation_raw = number(v3.get("creation_raw_income"), "creation terminal raw")
        creation_scaled = number(v3.get("creation_scaled_income"), "creation terminal scaled")
        v2_integrity = int(number(v2.get("integrity_violations"), "v26-2 integrity"))
        v3_integrity = int(number(v3.get("integrity_violations"), "v26-3 integrity"))
        require(v3.get("state_initialized") is True, f"{path}:terminal[{index}] creation state not initialized")
        values = [number(item.get("door_handle_joint_pos"), "trace handle") for item in by_env[env_id]]
        hinges = [number(item["v26_2"].get("hinge_rad"), "trace hinge") for item in by_env[env_id]]
        above_reference = [value > reference for value in values]
        episode_rows.append(
            {
                "env_id": env_id,
                "max_stage": stage,
                "goal": goal,
                "terminal_reason": row.get("terminal_reasons"),
                "handle_highwater_rad": handle_highwater,
                "max_hinge_rad": max_hinge,
                "k5_steps": int(number(v2.get("k5_steps"), "k5 steps")),
                "durable_creation": longest_true_run(above_reference) >= 5,
                "reference_dwell_steps": sum(above_reference),
                "reference_longest_dwell_steps": longest_true_run(above_reference),
                "handle_band_dwell_steps": {str(band): sum(value >= band for value in values) for band in (0.03, 0.1, 0.3, 0.6)},
                "hinge_band_dwell_steps": {
                    "0.08_0.105": sum(0.08 <= value <= 0.105 for value in hinges),
                    "ge_0.1": sum(value >= 0.1 for value in hinges),
                    "ge_0.25": sum(value >= 0.25 for value in hinges),
                },
                "old_raw_income": old_raw,
                "old_scaled_income": old_scaled,
                "creation_raw_income": creation_raw,
                "creation_scaled_income": creation_scaled,
                "creation_active_steps": int(number(v3.get("creation_active_steps"), "creation active steps")),
                "endpoint_velocity_delta_discrepancy_abs_sum": number(v3.get("endpoint_velocity_delta_discrepancy_abs_sum"), "endpoint discrepancy"),
                "integrity_violations": v2_integrity + v3_integrity,
            }
        )
        old_terminal_raw += old_raw
        old_terminal_scaled += old_scaled
        creation_terminal_raw += creation_raw
        creation_terminal_scaled += creation_scaled
        integrity += v2_integrity + v3_integrity
    require(close(old_terminal_raw, old_trace_raw) and close(old_terminal_scaled, old_trace_scaled), f"{path} old reward terminal/trace sums disagree")
    require(close(creation_terminal_raw, creation_trace_raw) and close(creation_terminal_scaled, creation_trace_scaled), f"{path} creation reward terminal/trace sums disagree")

    intervention = {"applied_steps": 0}
    if mode in {"E1", "E2"}:
        intervention = validate_action_intervention(trace, mode, metadata)
    return {
        "episodes": expected,
        "reference_rad": reference,
        "stage3": sum(row["max_stage"] >= 3 for row in episode_rows),
        "stage4": sum(row["max_stage"] >= 4 for row in episode_rows),
        "stage5": sum(row["max_stage"] >= 5 for row in episode_rows),
        "goals": sum(row["goal"] for row in episode_rows),
        "k5_episodes": sum(row["k5_steps"] > 0 for row in episode_rows),
        "k5_steps": sum(row["k5_steps"] for row in episode_rows),
        "durable_creation_episodes": sum(row["durable_creation"] for row in episode_rows),
        "max_handle_highwater_rad": max(row["handle_highwater_rad"] for row in episode_rows),
        "max_hinge_rad": max(row["max_hinge_rad"] for row in episode_rows),
        "hinge_0.08_0.105_dwell_steps": sum(row["hinge_band_dwell_steps"]["0.08_0.105"] for row in episode_rows),
        "old_raw_income": old_terminal_raw,
        "old_scaled_income": old_terminal_scaled,
        "creation_raw_income": creation_terminal_raw,
        "creation_scaled_income": creation_terminal_scaled,
        "creation_active_steps": sum(row["creation_active_steps"] for row in episode_rows),
        "integrity_violations": integrity,
        "max_stage_counts": dict(sorted(Counter(row["max_stage"] for row in episode_rows).items())),
        "terminal_reason_counts": dict(sorted(Counter(str(row["terminal_reason"]) for row in episode_rows).items())),
        "intervention": intervention,
        "episodes_detail": episode_rows,
        "provenance": {
            "checkpoint": str(config.get("checkpoint")),
            "checkpoint_load_mode": config.get("checkpoint_load_mode"),
            "auto_load_latest": config.get("auto_load_latest"),
            "codebase_version": config.get("codebase_version"),
            "seed": config.get("seed"),
            "control_dt_s": sorted({number(row.get("control_dt"), "terminal control_dt") for row in terminal}),
            "first_episode_contract": metadata.get("first_episode_contract"),
            "reward_terms": metadata.get("reward_terms"),
        },
    }


def old_unlatch_cliff(path: Path) -> dict[str, Any]:
    """Find direct old-0.1 unlatch-income cliffs at natural hinge crossings."""
    trace = load_json(path / "stage2_5_step_trace.json")
    config = load_runtime_config(path / ".hydra/runtime_config.yaml")
    threshold = number(
        config["env"]["config"].get("a2_stage3_unlatch_near_closed_hinge_threshold"),
        f"{path} near-closed threshold",
    )
    require(math.isclose(threshold, 0.1, rel_tol=0.0, abs_tol=1.0e-12), f"{path} is not the old0.1 wall")
    by_env: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in trace:
        if row.get("first_episode_active") is True:
            by_env[int(row["env_id"])].append(row)
    cliff_envs = []
    examples = []
    for env_id, rows in by_env.items():
        ordered = sorted(rows, key=lambda row: int(row["step_index"]))
        for index in range(1, len(ordered)):
            before = ordered[index - 1]
            crossing = ordered[index]
            before_hinge = number(before.get("door_hinge_joint_pos"), "pre-cliff hinge")
            crossing_hinge = number(crossing.get("door_hinge_joint_pos"), "crossing hinge")
            if not (before_hinge < threshold <= crossing_hinge <= 0.105):
                continue
            before_raw = number(
                (before.get("reward_raw") or {}).get("a2_stage3_unlatch_hold", 0.0),
                "pre-cliff unlatch raw",
            )
            after_rows = ordered[index : min(index + 2, len(ordered))]
            after_raw = min(
                number((row.get("reward_raw") or {}).get("a2_stage3_unlatch_hold", 0.0), "post-cliff unlatch raw")
                for row in after_rows
            )
            handle_after = max(number(row.get("door_handle_joint_pos"), "post-cliff handle") for row in after_rows)
            if before_raw > 0.0 and math.isclose(after_raw, 0.0, rel_tol=0.0, abs_tol=1.0e-12) and handle_after > 0.0:
                cliff_envs.append(env_id)
                examples.append(
                    {
                        "env_id": env_id,
                        "pre_hinge_rad": before_hinge,
                        "crossing_hinge_rad": crossing_hinge,
                        "pre_unlatch_raw": before_raw,
                        "post_unlatch_raw": after_raw,
                        "post_handle_rad": handle_after,
                    }
                )
                break
    return {
        "old_near_closed_threshold_rad": threshold,
        "direct_cliff_episode_count": len(cliff_envs),
        "visible_repeated_cliff": len(cliff_envs) >= 2,
        "examples": examples[:8],
    }


def zero_references(root: Path) -> dict[str, float]:
    result = {}
    for side in SIDES:
        payload = load_json(root / f"zero_command_{side}.json")
        result[side] = number(payload.get("handle_zero_state_excursion_rad"), f"zero excursion {side}")
    return result


def d3_capacity_summary(root: Path) -> dict[str, Any]:
    sides = {}
    for side in SIDES:
        trace = load_json(root / "D3" / side / "stage2_5_step_trace.json")
        rows = [
            row
            for row in trace
            if row.get("first_episode_active") is True
            and row.get("stage_buf") == 3
            and row.get("v26_2", {}).get("strict_k5") is True
        ]
        require(rows, f"D3/{side} has no natural Stage3+K5 detailed rows")
        errors = []
        saturation = []
        external_opening = []
        semantic = set()
        for index, row in enumerate(rows):
            err = row.get("gripper_joint_target_error")
            sat = row.get("pd_effort_estimated_saturation")
            force = row.get("finger_total_force_along_opening_axis_body7_body8")
            require(isinstance(err, list) and isinstance(sat, list) and isinstance(force, list) and len(err) == len(sat) == len(force) == 2, f"D3/{side} detailed row {index} shape mismatch")
            errors.extend(abs(number(value, "D3 target error")) for value in err)
            saturation.extend(bool(value) for value in sat)
            external_opening.append(all(number(value, "D3 opening force") > 0.0 for value in force))
            semantic.add(row.get("opening_force_projection_positive_semantic"))
        expected_semantic = "positive_force_on_finger_drives_its_joint_toward_open_target; arm_j7_positive, arm_j8_negative"
        require(semantic == {expected_semantic}, f"D3/{side} opening-axis semantic is not canonical")
        sides[side] = {
            "stage3_k5_detailed_steps": len(rows),
            "mean_abs_gripper_target_error_rad": sum(errors) / len(errors),
            "estimated_saturation_fraction": sum(saturation) / len(saturation),
            "external_opening_force_both_fingers_fraction": sum(external_opening) / len(external_opening),
            "effort_authority": "ISAACLAB_IMPLICIT_ESTIMATE_ONLY_NOT_ACTUAL_DRIVE_FORCE",
            "opening_axis_semantic": expected_semantic,
        }
    tracking_limit = all(
        sides[side]["mean_abs_gripper_target_error_rad"] > 0.005
        and sides[side]["estimated_saturation_fraction"] > 0.10
        for side in SIDES
    )
    external_load_bearing = all(
        sides[side]["external_opening_force_both_fingers_fraction"] > 0.50
        for side in SIDES
    )
    return {
        "sides": sides,
        "tracking_or_estimated_saturation": tracking_limit,
        "contact_opening_axis_interpretable": True,
        "external_finger_spreading_signal_not_mutual_squeeze": external_load_bearing,
        "handle_axis_effect": "INCONCLUSIVE_NO_PER_CONTACT_AXIS_MOMENT",
        "f_initial_eval_admitted": tracking_limit and external_load_bearing,
        "actual_drive_force": "INCONCLUSIVE_UNAVAILABLE",
    }


def diagnostics(root: Path) -> dict[str, Any]:
    zeros = zero_references(root)
    preliminary = {side: load_side(root / "D0" / side, 64, zeros[side], "D0") for side in SIDES}
    references = {}
    for side in SIDES:
        eligible = [row["handle_highwater_rad"] for row in preliminary[side]["episodes_detail"] if row["max_stage"] >= 3 and row["k5_steps"] > 0]
        references[side] = max([zeros[side], *eligible])
    lanes = {}
    for lane, expected in (("D0", 64), ("E1", 64), ("E2", 64), ("D3", 16)):
        lanes[lane] = {side: load_side(root / lane / side, expected, references[side], lane) for side in SIDES}
        for side in SIDES:
            require(lanes[lane][side]["provenance"]["checkpoint"] in {SOURCE_W, str(Path(SOURCE_W).relative_to(ROOT))}, f"{lane}/{side} source checkpoint drift")
    baseline_reproduced = all(lanes["D0"][side]["old_raw_income"] > 0.0 for side in SIDES)
    e1_restored = all(
        lanes["E1"][side]["k5_episodes"] > lanes["D0"][side]["k5_episodes"]
        and lanes["E1"][side]["stage3"] > 0
        and lanes["E1"][side]["intervention"]["applied_steps"] > 0
        for side in SIDES
    )
    e2_creation = all(lanes["E2"][side]["durable_creation_episodes"] > lanes["D0"][side]["durable_creation_episodes"] for side in SIDES)
    d3_capacity = d3_capacity_summary(root)
    return {
        "schema": "a2_piper_base_v26_3_diagnostics_v1",
        "status": "RUNTIME_COMPLETE",
        "handle_creation_reference_side_rad": references,
        "zero_command_excursion_rad": zeros,
        "lanes": lanes,
        "baseline": "D0_OLD_INCOME_HIGHWATER_GAP_REPRODUCED" if baseline_reproduced else "V26_3_BASELINE_DRIFT_INCONCLUSIVE",
        "e1_outcome": "STAGE2_LIMIT_CYCLE_CAUSAL_CONFIRMATION" if e1_restored else "CLOSE_HOLD_NO_K5",
        "e2_outcome": "STAGE3_OPEN_CHATTER_CAUSAL" if e2_creation else "STAGE3_CLOSE_NOT_CAUSAL",
        "d3_capacity": d3_capacity,
        "effort_capacity_branch": (
            {
                "status": "INITIAL_F_EVAL_REQUIRED",
                "typed_reason": "D3_ESTIMATED_SATURATION_WITH_INTERPRETABLE_EXTERNAL_OPENING_LOAD",
                "tested_caps": [10.0, 20.0, 40.0],
                "actual_drive_force": "INCONCLUSIVE_UNAVAILABLE",
            }
            if d3_capacity["f_initial_eval_admitted"]
            else {
                "status": "NOT_RUN",
                "typed_reason": "ACTUATOR_CAPACITY_PRECONDITION_NOT_MET",
                "common_j7_j8_effort_limit": [10.0, 10.0],
                "actual_drive_force": "INCONCLUSIVE_UNAVAILABLE",
            }
        ),
    }


def load_references(diagnostic_root: Path) -> dict[str, float]:
    payload = load_json(diagnostic_root / "diagnostic_decision.json")
    refs = payload.get("handle_creation_reference_side_rad")
    require(isinstance(refs, dict), "diagnostic decision has no frozen references")
    return {side: number(refs.get(side), f"reference {side}") for side in SIDES}


def main_analysis(eval_root: Path, diagnostic_root: Path) -> dict[str, Any]:
    references = load_references(diagnostic_root)
    cells = {}
    for cell in MAIN_CELLS:
        cells[cell] = {}
        for step in STEPS:
            label = f"{cell}_STEP{step:04d}"
            cells[cell][str(step)] = {side: load_side(eval_root / label / side, 64, references[side], "NATURAL") for side in SIDES}
    integrity = sum(cells[cell][str(step)][side]["integrity_violations"] for cell in MAIN_CELLS for step in STEPS for side in SIDES)
    no_delta_income = any(
        row["creation_raw_income"] != 0.0 and row["creation_active_steps"] == 0
        for cell in ("M1_S0", "M1_S1")
        for step in STEPS
        for side in SIDES
        for row in cells[cell][str(step)][side]["episodes_detail"]
    )
    creation_admitted = True
    for seed in (0, 1):
        for side in SIDES:
            m1 = cells[f"M1_S{seed}"]["750"][side]["durable_creation_episodes"]
            m0 = cells[f"M0_S{seed}"]["750"][side]["durable_creation_episodes"]
            creation_admitted &= m1 >= 2 and m1 > m0
    side_seed_support = {
        f"seed{seed}_{side}": cells[f"M1_S{seed}"]["750"][side]["durable_creation_episodes"]
        > cells[f"M0_S{seed}"]["750"][side]["durable_creation_episodes"]
        for seed in (0, 1)
        for side in SIDES
    }
    if no_delta_income or integrity:
        outcome = "CREATION_REWARD_INTEGRITY_BUG"
    elif creation_admitted:
        outcome = "MONOTONE_CREATION_CREDIT_SUPPORTED"
    elif any(side_seed_support.values()):
        outcome = "MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE"
    else:
        outcome = "REWARD_ALIAS_REMOVED_MECHANICS_BLOCKED"
    candidates = []
    for cell in ("M1_S0", "M1_S1"):
        for step in STEPS:
            sides = cells[cell][str(step)]
            score = (
                min(sides[side]["durable_creation_episodes"] for side in SIDES),
                min(sides[side]["goals"] for side in SIDES),
                min(sides[side]["stage4"] for side in SIDES),
                step,
                cell,
            )
            candidates.append(score)
    selected = max(candidates)
    selected_cell = selected[-1]
    selected_step = selected[-2]
    label = f"{selected_cell}_STEP{selected_step:04d}"
    checkpoint = ROOT / f"logs_rl/by_batch/base_v26_3_event_time_creation_20260827/main/{selected_cell}/model_step_{selected_step:06d}.pt"
    return {
        "schema": "a2_piper_base_v26_3_main_mechanism_v1",
        "status": "RUNTIME_COMPLETE",
        "natural_first_episode_only": True,
        "episodes_per_side": 64,
        "handle_creation_reference_side_rad": references,
        "cells": cells,
        "integrity_violations": integrity,
        "creation_reward_nonzero_without_active": no_delta_income,
        "side_seed_support": side_seed_support,
        "outcome": outcome,
        "selected_render": {"label": label, "checkpoint": str(checkpoint)},
        "teacher_boundary": {
            "status": "G7_UNCHANGED_PENDING_EXACT128_HOLDOUT" if creation_admitted and all(cells[f"M1_S{seed}"]["750"][side]["goals"] >= 2 for seed in (0, 1) for side in SIDES) else "G7_UNCHANGED",
            "typed_outcome": "V26_3_MECHANISM_PASS_NO_TEACHER",
        },
    }


def conditional_decision(eval_root: Path, diagnostic_root: Path) -> dict[str, Any]:
    main_path = eval_root.parent / "main_mechanism.json"
    main = load_json(main_path)
    outcome = main.get("outcome")
    selected = main.get("selected_render")
    require(isinstance(selected, dict), "main analysis has no selected checkpoint")
    cells = main.get("cells")
    require(isinstance(cells, dict), "main analysis has no cells")
    selected_label = selected.get("label")
    require(isinstance(selected_label, str) and "_STEP" in selected_label, "selected label is invalid")
    selected_cell, selected_step_label = selected_label.rsplit("_STEP", 1)
    selected_step = str(int(selected_step_label))
    require(selected_cell in ("M1_S0", "M1_S1") and selected_step in cells[selected_cell], "selected M1 checkpoint is invalid")
    selected_sides = cells[selected_cell][selected_step]
    bilateral_creation = all(selected_sides[side]["durable_creation_episodes"] >= 2 for side in SIDES)
    hinge_wall_reached = all(selected_sides[side]["hinge_0.08_0.105_dwell_steps"] > 0 for side in SIDES)
    cliffs = {
        side: old_unlatch_cliff(eval_root / selected_label / side)
        for side in SIDES
    }
    old_income_cliff = all(cliffs[side]["visible_repeated_cliff"] for side in SIDES)
    p = {
        "status": "NOT_RUN",
        "typed_reason": "PUSH_LOAD_BEARING_SIGNAL_INCONCLUSIVE",
        "evidence_boundary": "no proven per-contact side-canonical handle-axis work signal with identified anchor/axis/frame",
    }
    if bilateral_creation and hinge_wall_reached and old_income_cliff:
        w = {
            "status": "READY_TO_RUN",
            "typed_reason": "WAVE_W_PRECONDITIONS_MET",
            "selected_checkpoint": selected,
            "old_unlatch_income_cliff": cliffs,
        }
    else:
        w = {
            "status": "NOT_RUN",
            "typed_reason": "WALL_REMOVAL_NOT_REACHED",
            "preconditions": {
                "selected_bilateral_repeated_creation": bilateral_creation,
                "selected_bilateral_hinge_0.08_0.105_access": hinge_wall_reached,
                "selected_bilateral_old0.1_income_cliff": old_income_cliff,
            },
            "old_unlatch_income_cliff": cliffs,
        }
    effort = load_json(diagnostic_root / "F" / "f_decision.json")
    require(effort.get("status") == "INITIAL_COMPLETE", "bounded F sweep is incomplete")
    f = {
        "status": "RUNTIME_COMPLETE",
        "typed_reason": effort.get("typed_outcome"),
        "selected_effort_limit_nm": effort.get("selected_effort_limit_nm"),
        "common_j7_j8_effort_limit": effort.get("common_j7_j8_effort_limit"),
        "exact64_expansion_required": effort.get("exact64_expansion_required"),
        "actual_drive_force": effort.get("actual_drive_force"),
        "handle_axis_effect": effort.get("handle_axis_effect"),
        "evidence": str(diagnostic_root / "F" / "f_decision.json"),
    }
    return {
        "schema": "a2_piper_base_v26_3_conditional_decision_v1",
        "status": "COMPLETE",
        "main_outcome": outcome,
        "F": f,
        "P": p,
        "W": w,
        "selected_parent": selected,
        "no_unbounded_relay": True,
    }


def final_validation(eval_root: Path, diagnostic_root: Path) -> dict[str, Any]:
    main = load_json(eval_root.parent / "main_mechanism.json")
    conditional = load_json(diagnostic_root / "conditional_decision.json")
    require(main.get("status") == "RUNTIME_COMPLETE", "main analysis is incomplete")
    for branch in ("F", "P", "W"):
        require(isinstance(conditional.get(branch), dict) and conditional[branch].get("status") in {"NOT_RUN", "PRECONDITION_PARTIAL", "RUNTIME_COMPLETE"}, f"conditional branch {branch} has no typed closure")
    return {
        "schema": "a2_piper_base_v26_3_final_validation_v1",
        "status": "COMPLETE",
        "main_outcome": main.get("outcome"),
        "conditional_branches": {key: conditional[key] for key in ("F", "P", "W")},
        "selected_render": main.get("selected_render"),
        "teacher_boundary": main.get("teacher_boundary"),
    }


def main() -> None:
    args = parse_args()
    diagnostic_root = args.diagnostic_root
    if args.phase == "diagnostics":
        payload = diagnostics((diagnostic_root or args.eval_root).resolve())
    else:
        require(diagnostic_root is not None, f"--diagnostic-root is required for {args.phase}")
        diagnostic_root = diagnostic_root.resolve()
        if args.phase == "main":
            payload = main_analysis(args.eval_root.resolve(), diagnostic_root)
        elif args.phase == "conditional":
            payload = conditional_decision(args.eval_root.resolve(), diagnostic_root)
        else:
            payload = final_validation(args.eval_root.resolve(), diagnostic_root)
            if args.phase == "closure":
                payload["schema"] = "a2_piper_base_v26_3_closure_evidence_v1"
                payload["closure_status"] = payload["main_outcome"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
