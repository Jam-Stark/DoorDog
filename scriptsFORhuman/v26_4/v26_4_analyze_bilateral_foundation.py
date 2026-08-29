#!/usr/bin/env python3
"""Reduce the preregistered v26-4 bilateral natural-evaluation matrix."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


CELLS = ("C0_CANONICAL_OFF", "C1_CANONICAL_ON")
STEPS = (125, 250, 500, 750)
SIDES = ("left", "right")
SEEDS = (0, 1)
EPISODES = 64
K5_GAP_LIMIT = 0.15
CONTACT_GAP_LIMIT = 0.05
HIGHWATER_RATIO_RANGE = (0.5, 2.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, required=True)
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


def load_config(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"runtime config is missing: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"runtime config must be mapping: {path}")
    return value


def load_side(path: Path, side: str, seed: int) -> dict[str, Any]:
    metrics = load_json(path / "metrics_eval.json")
    records = load_json(path / "a2_v14_per_env_records.json")
    trace = load_json(path / "stage2_5_step_trace.json")
    metadata = load_json(path / "a2_eval_diagnostic_metadata.json")
    config = load_config(path / ".hydra/runtime_config.yaml")
    require(isinstance(metrics, dict), f"metrics must be a mapping: {path}")
    require(isinstance(records, list) and len(records) == EPISODES, f"{path} requires exact64 per-env records")
    require(isinstance(trace, list) and trace, f"{path} requires non-empty trace")
    require(isinstance(metadata, dict), f"metadata must be a mapping: {path}")

    terminal = metrics.get("episode_terminal_diagnostics")
    max_stage = metrics.get("episode_max_stage_reached")
    require(isinstance(terminal, list) and len(terminal) == EPISODES, f"{path} requires exact64 terminal rows")
    require(isinstance(max_stage, list) and len(max_stage) == EPISODES, f"{path} requires exact64 max-stage rows")
    require(config.get("checkpoint_load_mode") == "full", f"{path} must full-load exact checkpoint")
    require(config.get("auto_load_latest") is False, f"{path} must disable auto latest")
    require(config.get("num_envs") == EPISODES, f"{path} num_envs must be exact64")
    eval_cfg = config["algo"]["config"]["eval"]
    env_cfg = config["env"]["config"]
    require(eval_cfg.get("num_eval_episodes") == EPISODES and eval_cfg.get("eval_num_envs_episodes") is True, f"{path} violates natural first-episode exact64 contract")
    require(env_cfg.get("enable_staged_reset") is False, f"{path} is not natural start")
    require(env_cfg.get("a2_v26_door_open_lr") == side, f"{path} side override mismatch")
    require(config.get("seed") == seed and env_cfg.get("a2_v26_side_permutation_seed") == seed, f"{path} seed contract mismatch")
    require(metadata.get("forced_gripper_close_enabled") is False, f"{path} forced gripper intervention is enabled")
    require(metadata.get("stage2_close_gate_forced_gripper_close_enabled") is False, f"{path} close-gate intervention is enabled")

    highwater_by_env: dict[int, float] = {}
    admitted = 0
    integrity = 0
    for index, (row, stage) in enumerate(zip(terminal, max_stage, strict=True)):
        require(isinstance(row, dict), f"{path}: terminal[{index}] must be mapping")
        require(isinstance(stage, int) and not isinstance(stage, bool), f"{path}: max stage invalid")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in highwater_by_env, f"{path}: terminal env id invalid")
        v2 = row.get("v26_2")
        v3 = row.get("v26_3")
        require(isinstance(v2, dict) and isinstance(v3, dict), f"{path}: terminal v26 telemetry missing")
        stage3_or_later = v2.get("stage3_or_later")
        require(stage3_or_later in (0, 1), f"{path}: stage3_or_later must be 0/1")
        require(stage3_or_later == int(stage >= 3), f"{path}: stage3 terminal contract disagrees with max stage")
        admitted += stage3_or_later
        highwater = number(v3.get("handle_highwater"), f"{path}: terminal highwater")
        max_handle = number(v2.get("max_handle_rad"), f"{path}: terminal max handle")
        require(math.isclose(highwater, max_handle, rel_tol=3.0e-6, abs_tol=2.0e-4 + 3.0e-6 * max(abs(highwater), abs(max_handle))), f"{path}: v26-3 highwater and v26-2 max handle disagree")
        highwater_by_env[env_id] = highwater
        integrity += int(number(v2.get("integrity_violations"), f"{path}: v26-2 integrity"))
        integrity += int(number(v3.get("integrity_violations"), f"{path}: v26-3 integrity"))
    require(len(highwater_by_env) == EPISODES, f"{path}: terminal rows do not cover exact64 env ids")

    stage3_steps = 0
    stable_steps = 0
    trace_envs: dict[int, int] = defaultdict(int)
    for index, row in enumerate(trace):
        require(isinstance(row, dict), f"{path}: trace[{index}] must be mapping")
        if row.get("first_episode_active") is not True:
            continue
        require(row.get("episode_index") == 0, f"{path}: later episode contaminates first-episode evidence")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES, f"{path}: trace env id invalid")
        trace_envs[env_id] += 1
        stage = row.get("stage_buf")
        require(isinstance(stage, int) and not isinstance(stage, bool), f"{path}: trace stage invalid")
        if stage != 3:
            continue
        stability = row.get("contact_stability")
        require(isinstance(stability, bool), f"{path}: trace stage3 contact_stability missing or invalid")
        stage3_steps += 1
        stable_steps += int(stability)
    require(set(trace_envs) == set(range(EPISODES)), f"{path}: trace does not cover exact64 first episodes")
    highwater = max(highwater_by_env.values())
    return {
        "episodes": EPISODES,
        "k5_admission_episodes": admitted,
        "k5_admission_rate": admitted / EPISODES,
        "stage3_contact_stability_numerator_steps": stable_steps,
        "stage3_contact_stability_denominator_steps": stage3_steps,
        "stage3_contact_stability": None if stage3_steps == 0 else stable_steps / stage3_steps,
        "handle_highwater_rad": highwater,
        "integrity_violations": integrity,
        "provenance": {
            "checkpoint": str(config.get("checkpoint")),
            "checkpoint_load_mode": config.get("checkpoint_load_mode"),
            "seed": config.get("seed"),
            "first_episode_contract": metadata.get("first_episode_contract"),
        },
    }


def pair_metrics(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if left["integrity_violations"] or right["integrity_violations"]:
        return {"status": "INCONCLUSIVE", "reason": "INTEGRITY_VIOLATION"}
    if left["stage3_contact_stability"] is None or right["stage3_contact_stability"] is None:
        return {"status": "NOT_ADMITTED", "reason": "STAGE3_CONTACT_DENOMINATOR_ZERO"}
    left_hw = left["handle_highwater_rad"]
    right_hw = right["handle_highwater_rad"]
    require(left_hw >= 0.0 and right_hw >= 0.0, "handle highwater must be nonnegative")
    if left_hw == 0.0 and right_hw == 0.0:
        return {"status": "NOT_ADMITTED", "reason": "HANDLE_HIGHWATER_RATIO_UNDEFINED_ZERO_OVER_ZERO"}
    k5_gap = abs(left["k5_admission_rate"] - right["k5_admission_rate"])
    contact_gap = abs(left["stage3_contact_stability"] - right["stage3_contact_stability"])
    if right_hw == 0.0:
        ratio = None
        ratio_class = "POSITIVE_INFINITY"
        highwater_loss = None
    elif left_hw == 0.0:
        ratio = 0.0
        ratio_class = "ZERO"
        highwater_loss = None
    else:
        ratio = left_hw / right_hw
        ratio_class = "FINITE"
        highwater_loss = abs(math.log(ratio))
    bands = {
        "k5_admission_gap_le_0_15": k5_gap <= K5_GAP_LIMIT,
        "contact_stability_gap_le_0_05": contact_gap <= CONTACT_GAP_LIMIT,
        "handle_highwater_ratio_in_0_5_2_0": ratio is not None and HIGHWATER_RATIO_RANGE[0] <= ratio <= HIGHWATER_RATIO_RANGE[1],
    }
    return {
        "status": "ADMITTED",
        "k5_admission_absolute_gap": k5_gap,
        "contact_stability_absolute_gap": contact_gap,
        "handle_highwater_left_right_ratio": ratio,
        "handle_highwater_left_right_ratio_class": ratio_class,
        "asymmetry_loss": {
            "k5_admission": k5_gap,
            "contact_stability": contact_gap,
            "handle_highwater": highwater_loss,
        },
        "bands": bands,
        "all_bands_pass": all(bands.values()),
    }


def cell_seed_label(cell: str, seed: int, step: int) -> str:
    return f"{cell}_S{seed}_STEP{step:04d}"


def final_outcome(c1: dict[int, dict[str, Any]], c0: dict[int, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    c1_pairs = [c1[seed] for seed in SEEDS]
    if any(pair["status"] == "INCONCLUSIVE" for pair in c1_pairs):
        return "INCONCLUSIVE", {"reason": "C1_INTEGRITY_VIOLATION"}
    if any(pair["status"] != "ADMITTED" for pair in c1_pairs):
        return "NOT_ADMITTED", {"reason": "C1_METRIC_DENOMINATOR_OR_HIGHWATER_NOT_ADMITTED"}
    k5_contact_pass = all(pair["bands"]["k5_admission_gap_le_0_15"] and pair["bands"]["contact_stability_gap_le_0_05"] for pair in c1_pairs)
    highwater_fail = any(not pair["bands"]["handle_highwater_ratio_in_0_5_2_0"] for pair in c1_pairs)
    if k5_contact_pass and highwater_fail:
        return "BILATERAL_CONTACT_SYMMETRIC_ROTATION_ASYMMETRIC", {"reason": "C1_ONLY_HIGHWATER_BAND_FAILED"}
    if not all(pair["all_bands_pass"] for pair in c1_pairs):
        return "CANONICALIZATION_NOT_SUPPORTED", {"reason": "C1_PREREGISTERED_BAND_FAILED"}
    if any(c0[seed]["status"] != "ADMITTED" for seed in SEEDS):
        return "INCONCLUSIVE", {"reason": "C0_ASYMMETRY_LOSS_UNAVAILABLE"}
    def strictly_lower_loss(candidate: float | None, baseline: float | None) -> bool:
        candidate_value = math.inf if candidate is None else candidate
        baseline_value = math.inf if baseline is None else baseline
        return candidate_value < baseline_value

    improvements = {
        metric: {
            f"seed{seed}": strictly_lower_loss(c1[seed]["asymmetry_loss"][metric], c0[seed]["asymmetry_loss"][metric])
            for seed in SEEDS
        }
        for metric in ("k5_admission", "contact_stability", "handle_highwater")
    }
    all_improved = all(all(by_seed.values()) for by_seed in improvements.values())
    if not all_improved:
        return "CANONICALIZATION_NOT_SUPPORTED", {
            "reason": "C1_DID_NOT_STRICTLY_IMPROVE_ALL_ASYMMETRY_LOSSES_ON_BOTH_SEEDS",
            "improvements": improvements,
        }
    return "BILATERAL_GRASP_FOUNDATION_SUPPORTED", {"reason": "C1_ALL_BANDS_PASS_AND_ALL_LOSSES_STRICTLY_IMPROVE", "improvements": improvements}


def main() -> None:
    args = parse_args()
    cells: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for cell in CELLS:
        cells[cell] = {}
        for seed in SEEDS:
            seed_key = f"seed{seed}"
            cells[cell][seed_key] = {}
            for step in STEPS:
                label = cell_seed_label(cell, seed, step)
                sides = {side: load_side(args.eval_root / label / side, side, seed) for side in SIDES}
                cells[cell][seed_key][str(step)] = {
                    "left": sides["left"],
                    "right": sides["right"],
                    "pair": pair_metrics(sides["left"], sides["right"]),
                }
    c0 = {seed: cells["C0_CANONICAL_OFF"][f"seed{seed}"]["750"]["pair"] for seed in SEEDS}
    c1 = {seed: cells["C1_CANONICAL_ON"][f"seed{seed}"]["750"]["pair"] for seed in SEEDS}
    outcome, rationale = final_outcome(c1, c0)
    payload = {
        "schema": "a2_piper_base_v26_4_bilateral_foundation_v1",
        "status": "EXPERIMENT_COMPLETE",
        "natural_first_episode_only": True,
        "episodes_per_side": EPISODES,
        "checkpoints": list(STEPS),
        "registered_metrics": {
            "k5_admission": "count(v26_2.stage3_or_later == 1) / 64",
            "contact_stability": "sum(first_episode_active and stage_buf == 3 and contact_stability) / sum(first_episode_active and stage_buf == 3)",
            "handle_highwater": "max(v26_3.handle_highwater) per side; LEFT/RIGHT ratio",
            "two_seed_direction": "C1 asymmetry loss is strictly lower than C0 for each metric on both seeds",
        },
        "thresholds": {
            "k5_admission_absolute_gap_max": K5_GAP_LIMIT,
            "contact_stability_absolute_gap_max": CONTACT_GAP_LIMIT,
            "handle_highwater_left_right_ratio": list(HIGHWATER_RATIO_RANGE),
        },
        "cells": cells,
        "step750_comparison": {"C0_CANONICAL_OFF": {f"seed{seed}": c0[seed] for seed in SEEDS}, "C1_CANONICAL_ON": {f"seed{seed}": c1[seed] for seed in SEEDS}},
        "typed_outcome": outcome,
        "rationale": rationale,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
