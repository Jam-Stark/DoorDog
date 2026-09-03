#!/usr/bin/env python3
"""Reduce one frozen v26-7 bilateral-natural milestone without rerouting it."""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

import yaml

CELLS = ("Q05_S0", "Q05_S1", "Q05_S2", "Q20_S0", "Q20_S1", "Q20_S2")
SIDES = ("left", "right")
STEPS = (1000, 2000, 3000, 4000, 5000, 6000)
EPISODES = 64
DURABLE_RAD = 0.6
DURABLE_STEPS = 25
LEFT_MIN = 8
RIGHT_MIN = 32
ARM_J4_SOFT_LIMIT_P95 = 1.50


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def p50(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return values[len(values) // 2]


def p95(values: list[float]) -> float:
    require(bool(values), "cannot calculate p95 from an empty arm_j4 distribution")
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def load_json(path: Path):
    require(path.is_file(), f"missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validated_contract(train_root: Path, cell: str) -> dict:
    cfg_path = train_root / cell / "resolved_config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    require(isinstance(cfg, dict), f"{cfg_path}: resolved config must be mapping")
    env, robot = cfg["env"]["config"], cfg["robot"]
    expected_seed = int(cell[-1])
    expected_squeeze = 0.5 if cell.startswith("Q05") else 2.0
    expected = {
        "checkpoint": None, "checkpoint_load_mode": "full", "auto_load_latest": False,
        "seed": expected_seed, "num_envs": 4096, "v26_cell": f"V26_7_{cell}",
    }
    for key, want in expected.items():
        require(cfg.get(key) == want, f"{cell}: resolved {key}={cfg.get(key)!r}, expected {want!r}")
    require(cfg["algo"]["trl"]["num_total_batches"] == 6000, f"{cell}: batch budget changed")
    require(cfg["callbacks"]["model_save"]["save_frequency"] == 250, f"{cell}: save frequency changed")
    env_expected = {
        "a2_v26_door_open_lr": "bilateral",
        "a2_v26_6_side_mirrored_handle_offset_enabled": True,
        "a2_stage2_squeeze_force_min": expected_squeeze,
        "a2_m39_gripper_material_enabled": True,
        "a2_stage2_squeeze_force_max": 30.0,
        "a2_stage2_over_force_threshold": 55.0,
    }
    for key, want in env_expected.items():
        require(env.get(key) == want, f"{cell}: resolved env.config.{key}={env.get(key)!r}, expected {want!r}")
    require([float(v) for v in robot["dof_effort_limit_list"][-2:]] == [45.0, 45.0], f"{cell}: gripper effort contract")
    for group, want in (("stiffness", 1300.0), ("damping", 32.0)):
        require(all(float(robot["control"][group][joint]) == want for joint in ("arm_j7", "arm_j8")), f"{cell}: gripper {group} contract")
    require(cfg["simulator"]["config"]["sim"]["physx"]["num_velocity_iterations"] == 2, f"{cell}: velocity iterations changed")
    return {"seed": expected_seed, "squeeze_force_min": expected_squeeze}


def durable_run(rows: list[dict]) -> int:
    run = best = 0
    for row in sorted(rows, key=lambda value: value["step_index"]):
        if float(row["door_handle_joint_pos"]) >= DURABLE_RAD:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def side_summary(path: Path, side: str, seed: int) -> dict:
    metrics = load_json(path / "metrics_eval.json")
    trace = load_json(path / "stage2_5_step_trace.json")
    runtime = yaml.load((path / ".hydra/runtime_config.yaml").read_text(encoding="utf-8"), Loader=yaml.UnsafeLoader)
    terminal = metrics.get("episode_terminal_diagnostics")
    max_stage = metrics.get("episode_max_stage_reached")
    require(isinstance(terminal, list) and isinstance(max_stage, list) and len(terminal) == len(max_stage) == EPISODES, f"{path}: terminal/max-stage exact64 contract")
    require(metrics.get("completed_episodes") == EPISODES, f"{path}: completed episode count is not exact64")
    env_cfg = runtime["env"]["config"]
    eval_cfg = runtime["algo"]["config"]["eval"]
    require(runtime.get("checkpoint_load_mode") == "full" and runtime.get("auto_load_latest") is False, f"{path}: checkpoint evaluation contract")
    require(runtime.get("num_envs") == EPISODES and runtime.get("seed") == seed, f"{path}: seed/exact64 contract")
    require(eval_cfg.get("num_eval_episodes") == EPISODES and eval_cfg.get("eval_num_envs_episodes") is True, f"{path}: first-episode contract")
    require(env_cfg.get("a2_v26_door_open_lr") == side and env_cfg.get("enable_staged_reset") is False and env_cfg.get("a2_v26_6_side_mirrored_handle_offset_enabled") is True, f"{path}: natural-side/fix contract")
    terminals: dict[int, dict] = {}
    for row, stage in zip(terminal, max_stage, strict=True):
        require(isinstance(row, dict) and isinstance(stage, int), f"{path}: invalid terminal/max-stage row")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and env_id not in terminals and 0 <= env_id < EPISODES, f"{path}: invalid terminal env id")
        require(row.get("door_handle_side") == side, f"{path}: side contamination env{env_id}")
        row = dict(row); row["max_stage"] = stage; terminals[env_id] = row
    require(set(terminals) == set(range(EPISODES)), f"{path}: terminal env coverage")
    by_env: dict[int, list[dict]] = collections.defaultdict(list)
    require(isinstance(trace, list), f"{path}: trace must be list")
    for index, row in enumerate(trace):
        require(isinstance(row, dict) and row.get("first_episode_active") is True and row.get("episode_index") == 0, f"{path}: trace row {index} is not first episode")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES, f"{path}: trace env id")
        by_env[env_id].append(row)
    runs = {env_id: durable_run(by_env.get(env_id, [])) for env_id in range(EPISODES)}
    arm_j4: list[float] = []
    press_forces: list[float] = []
    k5 = 0
    over_force = 0
    arm_j4_limit_residence_steps = 0
    trace_steps = 0
    integrity = 0
    for env_id, row in terminals.items():
        v2, v3 = row.get("v26_2"), row.get("v26_3")
        require(isinstance(v2, dict) and isinstance(v3, dict), f"{path}: missing v26 telemetry env{env_id}")
        integrity += int(v2["integrity_violations"]) + int(v3["integrity_violations"])
        k5 += int(int(v2["k5_steps"]) >= 5)
    for env_id, rows in by_env.items():
        previous = None
        for row in sorted(rows, key=lambda value: value["step_index"]):
            step = row.get("step_index")
            require(isinstance(step, int) and (previous is None or step == previous + 1), f"{path}: non-contiguous trace env{env_id}")
            previous = step
            names, pos = row.get("arm_joint_names"), row.get("arm_joint_pos")
            require(names == ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"] and isinstance(pos, list) and len(pos) == 6, f"{path}: arm_j4 diagnostic contract env{env_id}")
            arm_j4_value = float(pos[3])
            arm_j4.append(arm_j4_value)
            arm_j4_limit_residence_steps += int(abs(1.745 - arm_j4_value) < 1e-3)
            trace_steps += 1
            over_force += int(row.get("over_force") is True)
            if float(row["door_handle_joint_pos"]) >= DURABLE_RAD:
                force = row.get("handle_contact_force_norm")
                require(isinstance(force, list) and len(force) == 2, f"{path}: handle contact force diagnostic")
                press_forces.append(sum(float(value) for value in force))
    return {
        "episodes": EPISODES,
        "durable_depression": sum(run >= DURABLE_STEPS for run in runs.values()),
        "durable_run_steps_p50": p50(list(runs.values())),
        "durable_run_steps_max": max(runs.values()),
        "stage3_admission": sum(row["max_stage"] >= 3 for row in terminals.values()),
        "stage4_episodes": sum(row["max_stage"] >= 4 for row in terminals.values()),
        "stage5_episodes": sum(row["max_stage"] >= 5 for row in terminals.values()),
        "goal_episodes": sum(row.get("terminal_reasons") == "complete" for row in terminals.values()),
        "k5_pass_rate": k5 / EPISODES,
        "press_handle_contact_force_p50": p50(press_forces),
        "over_force_step_share": None if trace_steps == 0 else over_force / trace_steps,
        "arm_j4_p95": p95(arm_j4),
        "arm_j4_trace_samples": len(arm_j4),
        "arm_j4_limit_residence_step_share": None if trace_steps == 0 else arm_j4_limit_residence_steps / trace_steps,
        "integrity_violations": integrity,
        "terminal_reasons": dict(collections.Counter(row["terminal_reasons"] for row in terminals.values())),
    }


def seed_outcome(left: dict, right: dict) -> str:
    if left["durable_depression"] >= LEFT_MIN and right["durable_depression"] >= RIGHT_MIN:
        return "BILATERAL_UNLATCH_SUPPORTED"
    if left["durable_depression"] >= LEFT_MIN and right["durable_depression"] < RIGHT_MIN:
        return "LEFT_RECOVERED_RIGHT_REGRESSED"
    if left["durable_depression"] == 0 and right["durable_depression"] >= RIGHT_MIN:
        return "LEFT_STILL_STRUCTURALLY_ZERO"
    return "BILATERAL_UNLATCH_NOT_LEARNED"


def mean(values: list[float | None]) -> float | None:
    selected = [value for value in values if value is not None]
    return None if not selected else sum(selected) / len(selected)


def frozen_config_endpoints(milestones_root: Path, current_step: int) -> dict[str, dict | None]:
    endpoints: dict[str, dict | None] = {"Q05": None, "Q20": None}
    for step in STEPS:
        if step >= current_step:
            break
        path = milestones_root / f"step{step}" / "reducer.json"
        require(path.is_file(), f"missing required preceding milestone reducer: {path}")
        prior = load_json(path)
        require(prior.get("schema") == "a2_piper_base_v26_7_milestone_reducer_v1" and prior.get("status") == "EXPERIMENT_COMPLETE" and prior.get("step") == step, f"invalid preceding milestone reducer: {path}")
        require(prior.get("stop_all_training") is False, f"preceding milestone stopped all training: {path}")
        stored = prior.get("config_endpoints")
        require(isinstance(stored, dict) and set(stored) == set(endpoints), f"preceding endpoint state missing: {path}")
        for config, endpoint in stored.items():
            if endpoint is None:
                continue
            require(isinstance(endpoint, dict) and endpoint.get("config") == config and endpoint.get("outcome") == "BILATERAL_UNLATCH_SUPPORTED" and endpoint.get("step") in STEPS and endpoint["step"] <= step and isinstance(endpoint.get("per_seed_outcomes"), dict), f"invalid frozen endpoint: {path} {config}")
            if endpoints[config] is None:
                endpoints[config] = endpoint
            else:
                require(endpoints[config] == endpoint, f"endpoint changed after freeze: {config}")
    return endpoints


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--step", type=int, choices=STEPS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite milestone reducer: {args.output}")
    contracts = {cell: validated_contract(args.train_root, cell) for cell in CELLS}
    endpoints = frozen_config_endpoints(args.eval_root.parent, args.step)
    active_configs = tuple(config for config in ("Q05", "Q20") if endpoints[config] is None)
    active_cells = tuple(f"{config}_S{seed}" for config in active_configs for seed in range(3))
    require(active_cells, "no active v26-7 config remains; no further milestone reducer is permitted")
    results: dict[str, dict[str, dict]] = {}
    for cell in active_cells:
        label = f"{cell}_STEP{args.step}"
        results[cell] = {side: side_summary(args.eval_root / label / side, side, contracts[cell]["seed"]) for side in SIDES}
    failures = [f"INTEGRITY_VIOLATIONS:{cell}/{side}" for cell in active_cells for side in SIDES if results[cell][side]["integrity_violations"] != 0]
    per_seed = {cell: seed_outcome(results[cell]["left"], results[cell]["right"]) for cell in active_cells}
    config_outcomes = {}
    stop_eligible = []
    config_endpoints = dict(endpoints)
    for config in ("Q05", "Q20"):
        if endpoints[config] is not None:
            config_outcomes[config] = "BILATERAL_UNLATCH_SUPPORTED"
            per_seed.update(endpoints[config]["per_seed_outcomes"])
            continue
        cells = tuple(f"{config}_S{seed}" for seed in range(3))
        supported = sum(per_seed[cell] == "BILATERAL_UNLATCH_SUPPORTED" for cell in cells)
        if supported >= 2:
            config_outcomes[config] = "BILATERAL_UNLATCH_SUPPORTED"
            if not failures:
                config_endpoints[config] = {"config": config, "step": args.step, "outcome": "BILATERAL_UNLATCH_SUPPORTED", "per_seed_outcomes": {cell: per_seed[cell] for cell in cells}}
                stop_eligible.extend(cells)
        elif args.step == 6000:
            categories = [per_seed[cell] for cell in cells]
            config_outcomes[config] = next((name for name in ("LEFT_RECOVERED_RIGHT_REGRESSED", "LEFT_STILL_STRUCTURALLY_ZERO") if categories.count(name) >= 2), "BILATERAL_UNLATCH_NOT_LEARNED")
        else:
            config_outcomes[config] = "MILESTONE_CONTINUE"
    all_six_active = set(active_cells) == set(CELLS)
    all_left_limit = args.step == 2000 and all_six_active and all(results[cell]["left"]["arm_j4_p95"] >= ARM_J4_SOFT_LIMIT_P95 for cell in CELLS)
    all_left_stage3_zero = args.step == 4000 and all_six_active and all(results[cell]["left"]["stage3_admission"] == 0 for cell in CELLS)
    if failures:
        route = "V26_7_INVALID"; stop_all = True
    elif all_left_limit:
        route = "V26_7_FIX_NOT_EFFECTIVE_IN_TRAINING"; stop_all = True
    elif all_left_stage3_zero:
        route = "V26_7_LEFT_STAGE3_NOT_REACHED"; stop_all = True
    elif args.step == 6000:
        route = "V26_7_ENDPOINT_REPORTED"; stop_all = False
    else:
        route = "V26_7_MILESTONE_REPORTED"; stop_all = False
    factor_summary = {}
    for config in ("Q05", "Q20"):
        if endpoints[config] is not None:
            factor_summary[config] = {"frozen_endpoint": endpoints[config], "current_milestone_readout": None}
            continue
        rows = [results[f"{config}_S{seed}"] for seed in range(3)]
        factor_summary[config] = {
            "left_durable_depression_mean": mean([float(row["left"]["durable_depression"]) for row in rows]),
            "right_durable_depression_mean": mean([float(row["right"]["durable_depression"]) for row in rows]),
            "left_stage3_admission_mean": mean([float(row["left"]["stage3_admission"]) for row in rows]),
            "right_stage3_admission_mean": mean([float(row["right"]["stage3_admission"]) for row in rows]),
            "left_press_handle_contact_force_p50_seed_mean": mean([row["left"]["press_handle_contact_force_p50"] for row in rows]),
            "right_press_handle_contact_force_p50_seed_mean": mean([row["right"]["press_handle_contact_force_p50"] for row in rows]),
            "left_k5_pass_rate_mean": mean([row["left"]["k5_pass_rate"] for row in rows]),
            "right_k5_pass_rate_mean": mean([row["right"]["k5_pass_rate"] for row in rows]),
            "left_over_force_step_share_mean": mean([row["left"]["over_force_step_share"] for row in rows]),
            "right_over_force_step_share_mean": mean([row["right"]["over_force_step_share"] for row in rows]),
        }
    payload = {
        "schema": "a2_piper_base_v26_7_milestone_reducer_v1", "status": "EXPERIMENT_COMPLETE" if not failures else "EXPERIMENT_INVALID",
        "step": args.step, "train_root": str(args.train_root), "eval_root": str(args.eval_root),
        "preregistered_thresholds": {"episodes_per_side": EPISODES, "durable_rad": DURABLE_RAD, "durable_steps": DURABLE_STEPS, "left_min": LEFT_MIN, "right_min": RIGHT_MIN, "arm_j4_soft_limit_p95": ARM_J4_SOFT_LIMIT_P95},
        "resolved_contracts": contracts, "active_cells": active_cells, "cells": results, "per_seed_outcomes": per_seed, "config_outcomes": config_outcomes, "config_endpoints": config_endpoints,
        "squeeze_min_readout": factor_summary, "route": route, "stop_all_training": stop_all, "stop_eligible_cells": stop_eligible, "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"step": args.step, "route": route, "stop_all_training": stop_all, "stop_eligible_cells": stop_eligible, "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
