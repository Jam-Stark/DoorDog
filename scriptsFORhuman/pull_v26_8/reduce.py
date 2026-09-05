#!/usr/bin/env python3
"""Reduce one pull-v26.8 exact64 bilateral-natural milestone."""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

import yaml

from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2_PULL_HARD_GATE_EVENT_PREDECESSORS,
    validate_a2_pull_episode,
)
from verify import read_config, validate_config


SCHEMA = "a2_piper_pull_v26_8_backbone_reducer_v1"
DEFAULT_CELLS = ("P_S0", "P_S1", "P_S2")
SIDES = ("left", "right")
SIDE_SIGNS = {"left": 1.0, "right": -1.0}
EPISODES = 64
DURABLE_RAD = 0.6
OPEN_HOLD_RAD = 0.25
HOLD_STEPS = 25
ARM_J4_LIMIT_RAD = 1.745
LEFT_MIN = 8
RIGHT_MIN = 32
EVENTS = {
    "E2": "E2_TENSILE_CAPTURE",
    "E3": "E3_LATCH_RELEASE",
    "E4": "E4_POSITIVE_HINGE_RETAINED",
    "E5": "E5_CLEARANCE_DECISION",
    "E6": "E6_PATH_REVERSAL_ENTRY",
    "E7": "E7_WHOLE_BODY_CLEAR",
}


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load_json(path: Path):
    require(path.is_file(), f"missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict:
    require(path.is_file(), f"missing artifact: {path}")
    return read_config(path)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def best_run(rows: list[dict], predicate) -> int:
    run = best = 0
    for row in sorted(rows, key=lambda item: item["step_index"]):
        if predicate(row):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def event_predecessors(runtime: dict):
    env = runtime["env"]["config"]
    mode = env.get("a2_pull_threshold_mode")
    require(mode in ("report_only", "hard_gate"), f"unknown pull threshold mode: {mode!r}")
    return A2_PULL_HARD_GATE_EVENT_PREDECESSORS if mode == "hard_gate" else None


def validate_pull_integrity(terminal: dict, predecessors, label: str) -> int:
    episode = terminal.get("pull_v0_episode")
    require(isinstance(episode, dict), f"{label}: missing pull_v0_episode")
    try:
        validate_a2_pull_episode(episode, event_predecessors=predecessors)
    except ValueError as exc:
        raise RuntimeError(f"{label}: pull event integrity violation: {exc}") from exc
    return 0


def terminal_rows(metrics: dict, records: list, side: str, path: Path) -> dict[int, dict]:
    terminal = metrics.get("episode_terminal_diagnostics")
    stages = metrics.get("episode_max_stage_reached")
    require(
        isinstance(terminal, list)
        and isinstance(stages, list)
        and len(terminal) == len(stages) == EPISODES
        and metrics.get("completed_episodes") == EPISODES,
        f"{path}: metrics exact64 terminal contract",
    )
    require(isinstance(records, list) and len(records) == EPISODES, f"{path}: exact64 per-env records")
    by_record: dict[int, dict] = {}
    for record in records:
        require(isinstance(record, dict), f"{path}: per-env record must be object")
        env_id = record.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in by_record, f"{path}: invalid per-env record id")
        by_record[env_id] = record
    result: dict[int, dict] = {}
    for diagnostic, max_stage in zip(terminal, stages, strict=True):
        require(isinstance(diagnostic, dict) and isinstance(max_stage, int), f"{path}: invalid metrics terminal row")
        env_id = diagnostic.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in result, f"{path}: invalid metrics env id")
        record = by_record.get(env_id)
        require(record is not None, f"{path}: terminal env{env_id} missing per-env record")
        for row_name, row in (("terminal", diagnostic), ("record", record)):
            require(row.get("door_handle_side") == side, f"{path}: {row_name} side contamination env{env_id}")
            require(float(row.get("door_open_lr")) == SIDE_SIGNS[side], f"{path}: {row_name} side sign env{env_id}")
        require(record.get("max_stage") == max_stage, f"{path}: max-stage disagreement env{env_id}")
        copied = dict(diagnostic)
        copied["max_stage"] = max_stage
        result[env_id] = copied
    require(set(result) == set(range(EPISODES)) == set(by_record), f"{path}: terminal exact64 coverage")
    return result


def trace_rows(trace: object, side: str, path: Path) -> dict[int, list[dict]]:
    require(isinstance(trace, list), f"{path}: trace must be a list")
    by_env: dict[int, list[dict]] = collections.defaultdict(list)
    for index, row in enumerate(trace):
        require(isinstance(row, dict), f"{path}: trace row {index} must be object")
        require(row.get("first_episode_active") is True and row.get("episode_index") == 0, f"{path}: trace row {index} is not first natural episode")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES, f"{path}: trace env id")
        require(row.get("door_handle_side") == side and float(row.get("door_open_lr")) == SIDE_SIGNS[side], f"{path}: trace side contamination env{env_id}")
        by_env[env_id].append(row)
    require(set(by_env).issubset(set(range(EPISODES))), f"{path}: trace env coverage")
    for env_id, rows in by_env.items():
        previous = None
        for row in sorted(rows, key=lambda item: item["step_index"]):
            step = row.get("step_index")
            require(isinstance(step, int) and (previous is None or step == previous + 1), f"{path}: trace non-contiguous env{env_id}")
            previous = step
    return by_env


def side_summary(path: Path, side: str, seed: int) -> dict:
    metrics = load_json(path / "metrics_eval.json")
    records = load_json(path / "a2_v14_per_env_records.json")
    trace = load_json(path / "stage2_5_step_trace.json")
    runtime = load_yaml(path / ".hydra/runtime_config.yaml")
    env = runtime["env"]["config"]
    evaluation = runtime["algo"]["config"]["eval"]
    require(runtime.get("checkpoint_load_mode") == "full" and runtime.get("auto_load_latest") is False, f"{path}: evaluation checkpoint contract")
    require(runtime.get("num_envs") == EPISODES and runtime.get("seed") == seed, f"{path}: evaluation seed/exact64 contract")
    require(evaluation.get("num_eval_episodes") == EPISODES and evaluation.get("eval_num_envs_episodes") is True, f"{path}: first-episode evaluation contract")
    require(env.get("a2_door_open_lr_distribution") == side and env.get("enable_staged_reset") is False, f"{path}: natural-side/staged-reset contract")
    terminals = terminal_rows(metrics, records, side, path)
    by_env = trace_rows(trace, side, path)
    predecessors = event_predecessors(runtime)
    durable = {
        env_id: best_run(by_env.get(env_id, []), lambda row: float(row["door_handle_joint_pos"]) >= DURABLE_RAD)
        for env_id in range(EPISODES)
    }
    open_hold = {
        env_id: best_run(
            by_env.get(env_id, []),
            lambda row: float(row["door_hinge_joint_pos"]) >= OPEN_HOLD_RAD and row.get("both_contact") is True,
        )
        for env_id in range(EPISODES)
    }
    arm_j4: list[float] = []
    press_forces: list[float] = []
    over_force_steps = 0
    limit_steps = 0
    trace_steps = 0
    k5 = 0
    for env_id in range(EPISODES):
        rows = by_env.get(env_id, [])
        k5 += int(max([int(terminals[env_id]["a2_stage2_squeeze_streak"]), *(int(row["a2_stage2_squeeze_streak"]) for row in rows)]) >= 5)
        for row in rows:
            names, positions = row.get("arm_joint_names"), row.get("arm_joint_pos")
            require(names == ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"], f"{path}: arm joint-name contract env{env_id}")
            require(isinstance(positions, list) and len(positions) == 6, f"{path}: arm position contract env{env_id}")
            j4 = float(positions[3])
            require(math.isfinite(j4), f"{path}: non-finite arm_j4 env{env_id}")
            arm_j4.append(j4)
            limit_steps += int(abs(ARM_J4_LIMIT_RAD - j4) < 1e-3)
            over_force_steps += int(row.get("over_force") is True)
            trace_steps += 1
            if float(row["door_handle_joint_pos"]) >= DURABLE_RAD:
                force = row.get("handle_contact_force_norm")
                require(isinstance(force, list) and len(force) == 2, f"{path}: handle contact force contract env{env_id}")
                press_forces.append(sum(float(value) for value in force))
    integrity = sum(validate_pull_integrity(row, predecessors, f"{path}: env{env_id}") for env_id, row in terminals.items())
    events = {label: 0 for label in EVENTS}
    for row in terminals.values():
        reached = row["pull_v0_episode"]["event_reached"]
        events.update({label: events[label] + int(reached[event]) for label, event in EVENTS.items()})
    return {
        "episodes": EPISODES,
        "D": sum(value >= HOLD_STEPS for value in durable.values()),
        "S3+": sum(row["max_stage"] >= 3 for row in terminals.values()),
        "S4+": sum(row["max_stage"] >= 4 for row in terminals.values()),
        "open_hold": sum(value >= HOLD_STEPS for value in open_hold.values()),
        "S5+": sum(row["max_stage"] >= 5 for row in terminals.values()),
        "complete": sum(row.get("terminal_reasons") == "complete" for row in terminals.values()),
        "K5": k5,
        **events,
        "arm_j4_p95": percentile(arm_j4, 0.95),
        "arm_j4_limit_residence_step_share": None if trace_steps == 0 else limit_steps / trace_steps,
        "press_handle_contact_force_p50": percentile(press_forces, 0.50),
        "over_force_step_share": None if trace_steps == 0 else over_force_steps / trace_steps,
        "integrity_violations": integrity,
        "terminal_reasons": dict(sorted(collections.Counter(row["terminal_reasons"] for row in terminals.values()).items())),
    }


def seed_outcome(left: dict, right: dict) -> str:
    if left["D"] >= LEFT_MIN and right["D"] >= RIGHT_MIN:
        return "BILATERAL_UNLATCH_SUPPORTED"
    if left["D"] >= LEFT_MIN and right["D"] < RIGHT_MIN:
        return "LEFT_RECOVERED_RIGHT_REGRESSED"
    if left["D"] == 0 and right["D"] >= RIGHT_MIN:
        return "LEFT_STILL_STRUCTURALLY_ZERO"
    return "BILATERAL_UNLATCH_NOT_LEARNED"


def opening_labels(cells: dict[str, dict[str, dict]]) -> list[str]:
    labels: list[str] = []
    if any(min(result[side]["E4"] for side in SIDES) >= 16 for result in cells.values()):
        labels.append("PULL_OPENING_EMERGED")
    if sum(min(result[side]["E4"] for side in SIDES) >= 32 for result in cells.values()) >= 2:
        labels.append("PULL_OPENING_BILATERAL")
    if any(min(result[side]["E7"] for side in SIDES) >= 8 for result in cells.values()):
        labels.append("PULL_FULL_CHAIN_OBSERVED")
    return labels


def final_route(per_seed: dict[str, str]) -> str:
    counts = collections.Counter(per_seed.values())
    if counts["LEFT_STILL_STRUCTURALLY_ZERO"] >= 2:
        return "PULL_LEFT_STILL_STRUCTURALLY_ZERO"
    return "PULL_BILATERAL_UNLATCH_NOT_LEARNED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cells", nargs="+", default=DEFAULT_CELLS)
    args = parser.parse_args()
    require(args.step > 0, "step must be positive")
    require(not args.output.exists(), f"refusing to overwrite reducer output: {args.output}")
    cells = tuple(args.cells)
    require(cells and len(set(cells)) == len(cells), "cells must be non-empty and unique")
    contracts = {}
    budgets: set[int] = set()
    for cell in cells:
        cfg = load_yaml(args.train_root / cell / "resolved_config.yaml")
        contracts[cell] = validate_config(cfg, cell)
        budgets.add(int(cfg["algo"]["trl"]["num_total_batches"]))
    require(len(budgets) == 1, f"cell training budgets diverged: {sorted(budgets)}")
    results = {
        cell: {
            side: side_summary(args.eval_root / f"{cell}_STEP{args.step}" / side, side, int(cell[-1]))
            for side in SIDES
        }
        for cell in cells
    }
    integrity_failures = [
        f"INTEGRITY_VIOLATIONS:{cell}/{side}"
        for cell in cells
        for side in SIDES
        if results[cell][side]["integrity_violations"] != 0
    ]
    per_seed = {cell: seed_outcome(results[cell]["left"], results[cell]["right"]) for cell in cells}
    bilateral_supported = [cell for cell, outcome in per_seed.items() if outcome == "BILATERAL_UNLATCH_SUPPORTED"]
    is_endpoint = args.step == next(iter(budgets))
    if integrity_failures:
        route = "PULL_V26_8_INVALID"
    elif len(bilateral_supported) >= 2:
        route = f"PULL_BILATERAL_UNLATCH_SUPPORTED@{args.step}"
    elif is_endpoint:
        route = final_route(per_seed)
    else:
        route = "PULL_V26_8_MILESTONE_REPORTED"
    payload = {
        "schema": SCHEMA,
        "status": "EXPERIMENT_INVALID" if integrity_failures else "EXPERIMENT_COMPLETE",
        "step": args.step,
        "train_root": str(args.train_root),
        "eval_root": str(args.eval_root),
        "resolved_contracts": contracts,
        "cells": results,
        "per_seed_outcomes": per_seed,
        "bilateral_supported_cells": bilateral_supported,
        "opening_full_labels": opening_labels(results),
        "wave2_eligible": len(bilateral_supported) >= 2,
        "route": route,
        "failures": integrity_failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "step": args.step, "route": route, "output": str(args.output)}, ensure_ascii=False))
    return 2 if integrity_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
