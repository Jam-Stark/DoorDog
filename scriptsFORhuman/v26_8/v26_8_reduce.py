#!/usr/bin/env python3
"""Reduce a v26-8 exact64 milestone under its frozen bilateral contract."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CELLS = ("C_S1", "W_S1", "K_S1", "C_S2", "W_S2", "K_S2")
SIDES = ("left", "right")
STEPS = (500, 1000, 1500, 2000, 2500, 3000)
EPISODES, DURABLE_RAD, OPEN_HOLD_RAD, HOLD_STEPS = 64, 0.6, 0.25, 25
ARM_J4_LIMIT_RAD = 1.745
SOURCES = {"S1": ("logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S1/model_step_003000.pt", "a683257213aaba82b583924d841235f772182f53113e513e16c8d27bcb394df1"), "S2": ("logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S2/model_step_003000.pt", "0b2f739f020b056adb2fb47105fdb5bc00d1d1189ef331d42332b3e0740e54ec")}
SOURCE_ENDPOINT = {
    "S1": {"left": {"durable_depression": 62, "stage4_episodes": 62}, "right": {"durable_depression": 64, "stage4_episodes": 64}},
    "S2": {"left": {"durable_depression": 60, "stage4_episodes": 0}, "right": {"durable_depression": 57, "stage4_episodes": 64}},
}
PENALTY_NAMES = ("walk_to_door", "gripper_handle_orientation", "pregrasp_gripper_dof_pos_l1", "pregrasp_target_distance", "grasp_target_distance", "grasp", "a2_stage2_close_command", "a2_stage2_close_progress", "a2_stage2_handle_center_y", "a2_stage2_handle_approach_xz", "a2_stage2_both_contact", "a2_stage2_opposite_squeeze", "a2_stage2_squeeze_force_window", "a2_stage2_contact_stability", "a2_stage3_handle_creation", "a2_stage3_unlatch_hold")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load_json(path: Path):
    require(path.is_file(), f"missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if fraction == 0.5:
        return ordered[len(ordered) // 2]
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def best_run(rows: list[dict], predicate) -> int:
    run = best = 0
    for row in sorted(rows, key=lambda item: item["step_index"]):
        if predicate(row):
            run += 1; best = max(best, run)
        else:
            run = 0
    return best


def validated_contract(train_root: Path, cell: str) -> dict:
    cfg_path = train_root / cell / "resolved_config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    require(isinstance(cfg, dict), f"{cfg_path}: config mapping")
    arm, seed_label = cell.split("_")
    seed = int(seed_label[1:])
    source_path, source_digest = SOURCES[seed_label]
    require(cfg.get("v26_cell") == f"V26_8_{cell}" and cfg.get("seed") == seed, f"{cell}: identity")
    require(cfg.get("checkpoint") == source_path and cfg.get("checkpoint_load_mode") == "policy_only" and cfg.get("policy_only_load_actor_rms") is True and cfg.get("auto_load_latest") is False, f"{cell}: source load")
    require(cfg.get("num_envs") == 4096 and cfg["algo"]["trl"]["num_total_batches"] == 3000 and cfg["callbacks"]["model_save"]["save_frequency"] == 250, f"{cell}: budget")
    source_file = ROOT / source_path
    require(source_file.is_file() and sha256(source_file) == source_digest, f"{cell}: source checkpoint SHA-256")
    lock = load_json(train_root / cell / "source_checkpoint_lock.json")
    require(lock == {"source": f"SRC_{seed_label}", "checkpoint": source_path, "sha256": source_digest}, f"{cell}: source checkpoint lock")
    env, rewards, robot = cfg["env"]["config"], cfg["rewards"], cfg["robot"]
    require(env.get("a2_v26_door_open_lr") == "bilateral" and env.get("a2_v26_side_permutation_seed") == seed, f"{cell}: bilateral")
    for key, want in {
        "a2_v26_6_side_mirrored_handle_offset_enabled": True,
        "a2_stage2_squeeze_force_min": 0.5,
        "a2_m39_gripper_material_enabled": True,
        "a2_stage2_squeeze_force_max": 30.0,
        "a2_stage2_over_force_threshold": 55.0,
    }.items():
        require(env.get(key) == want, f"{cell}: env.config.{key}")
    require([float(value) for value in robot["dof_effort_limit_list"][-2:]] == [45.0, 45.0], f"{cell}: gripper effort")
    for group, want in (("stiffness", 1300.0), ("damping", 32.0)):
        require(all(float(robot["control"][group][joint]) == want for joint in ("arm_j7", "arm_j8")), f"{cell}: gripper {group}")
    require(cfg["simulator"]["config"]["sim"]["physx"]["num_velocity_iterations"] == 2, f"{cell}: PhysX velocity iterations")
    require(float(env["a2_stage3_unlatch_near_closed_hinge_threshold"]) == (0.25 if arm == "W" else 0.1), f"{cell}: wall arm")
    if arm == "K":
        expected_k = {
            "reward_penalty_curriculum": True,
            "reward_initial_penalty_scale": 1.0,
            "reward_min_penalty_scale": 0.2,
            "reward_max_penalty_scale": 1.0,
            "reward_penalty_degree": -0.0001,
            "reward_penalty_level_down_ave_goal_reached_rate": None,
            "reward_penalty_level_up_ave_goal_reached_rate": None,
        }
        require(all(rewards.get(key) == want for key, want in expected_k.items()), f"{cell}: K reward curriculum")
        require(tuple(rewards.get("reward_penalty_reward_names", ())) == PENALTY_NAMES, f"{cell}: K penalty list")
        require(env.get("a2_v26_8_penalty_driver") == "side_min_natural_stage_reach_rate" and env.get("a2_v26_8_penalty_driver_target_stage") == 4 and env.get("a2_v26_8_penalty_driver_level_down_rate") == 0.5 and env.get("a2_v26_8_penalty_driver_level_up_rate") == 0.7 and env.get("a2_v26_8_penalty_curriculum_trace_enabled") is True, f"{cell}: K driver")
    else:
        require("a2_v26_8_penalty_driver" not in env and rewards.get("reward_penalty_curriculum") is not True, f"{cell}: non-K leakage")
    receipt = load_json(train_root / cell / "v26_8_policy_load_receipt.json")
    plan = ROOT / "scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md"
    require(receipt.get("status") == "POLICY_LOAD_CONFIRMED" and receipt.get("checkpoint") == str(source_file) and receipt.get("checkpoint_sha256") == source_digest and receipt.get("plan_sha256") == sha256(plan) and receipt.get("checkpoint_load_mode") == "policy_only" and receipt.get("actor_rms_loaded") is True and receipt.get("strict") is True and receipt.get("state_key") == "policy_state_dict", f"{cell}: runtime policy-only receipt")
    return {"seed": seed, "source": f"SRC_{seed_label}", "checkpoint": source_path, "checkpoint_sha256": source_digest}


def side_summary(path: Path, side: str, seed: int) -> dict:
    metrics = load_json(path / "metrics_eval.json")
    trace = load_json(path / "stage2_5_step_trace.json")
    runtime = yaml.load((path / ".hydra/runtime_config.yaml").read_text(encoding="utf-8"), Loader=yaml.UnsafeLoader)
    terminal, stages = metrics.get("episode_terminal_diagnostics"), metrics.get("episode_max_stage_reached")
    require(isinstance(terminal, list) and isinstance(stages, list) and len(terminal) == len(stages) == EPISODES and metrics.get("completed_episodes") == EPISODES, f"{path}: exact64 terminal contract")
    env, evaluation = runtime["env"]["config"], runtime["algo"]["config"]["eval"]
    require(runtime.get("checkpoint_load_mode") == "full" and runtime.get("auto_load_latest") is False and runtime.get("num_envs") == EPISODES and runtime.get("seed") == seed, f"{path}: eval load/seed")
    require(evaluation.get("num_eval_episodes") == EPISODES and evaluation.get("eval_num_envs_episodes") is True and env.get("a2_v26_door_open_lr") == side and env.get("enable_staged_reset") is False, f"{path}: exact natural eval")
    require(runtime.get("rewards", {}).get("reward_penalty_curriculum") is False, f"{path}: curriculum-off eval")
    terminals: dict[int, dict] = {}
    for row, stage in zip(terminal, stages, strict=True):
        require(isinstance(row, dict) and isinstance(stage, int), f"{path}: terminal row")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in terminals and row.get("door_handle_side") == side, f"{path}: terminal coverage/side")
        copied = dict(row); copied["max_stage"] = stage; terminals[env_id] = copied
    require(set(terminals) == set(range(EPISODES)), f"{path}: terminal exact64 coverage")
    by_env: dict[int, list[dict]] = collections.defaultdict(list)
    require(isinstance(trace, list), f"{path}: trace list")
    for index, row in enumerate(trace):
        require(isinstance(row, dict) and row.get("first_episode_active") is True and row.get("episode_index") == 0, f"{path}: trace first episode {index}")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES, f"{path}: trace env id")
        by_env[env_id].append(row)
    durable = {env_id: best_run(by_env.get(env_id, []), lambda row: float(row["door_handle_joint_pos"]) >= DURABLE_RAD) for env_id in range(EPISODES)}
    open_hold = {env_id: best_run(by_env.get(env_id, []), lambda row: float(row["door_hinge_joint_pos"]) >= OPEN_HOLD_RAD and row.get("both_contact") is True) for env_id in range(EPISODES)}
    dwell = [max(int(row["time_in_stage_buf"]) for row in rows if int(row["stage_buf"]) == 4) for rows in by_env.values() if any(int(row["stage_buf"]) == 4 for row in rows)]
    integrity = 0
    k5 = 0
    highwater: list[float] = []
    for row in terminals.values():
        v2, v3 = row.get("v26_2"), row.get("v26_3")
        require(isinstance(v2, dict) and isinstance(v3, dict), f"{path}: integrity telemetry")
        integrity += int(v2["integrity_violations"]) + int(v3["integrity_violations"])
        k5 += int(int(v2["k5_steps"]) >= 5)
        highwater.append(float(v2["max_hinge_rad"]))
    arm_j4: list[float] = []
    press_forces: list[float] = []
    over_force_steps = 0
    arm_j4_limit_steps = 0
    trace_steps = 0
    for env_id, rows in by_env.items():
        previous = None
        for row in sorted(rows, key=lambda value: value["step_index"]):
            step_index = row.get("step_index")
            require(isinstance(step_index, int) and (previous is None or step_index == previous + 1), f"{path}: non-contiguous trace env{env_id}")
            previous = step_index
            names, positions = row.get("arm_joint_names"), row.get("arm_joint_pos")
            require(names == ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"] and isinstance(positions, list) and len(positions) == 6, f"{path}: arm_j4 trace contract env{env_id}")
            arm_j4_value = float(positions[3])
            arm_j4.append(arm_j4_value)
            arm_j4_limit_steps += int(abs(ARM_J4_LIMIT_RAD - arm_j4_value) < 1e-3)
            over_force_steps += int(row.get("over_force") is True)
            trace_steps += 1
            if float(row["door_handle_joint_pos"]) >= DURABLE_RAD:
                force = row.get("handle_contact_force_norm")
                require(isinstance(force, list) and len(force) == 2, f"{path}: handle contact force trace")
                press_forces.append(sum(float(value) for value in force))
    release = [float(row["hinge_at_release"]) for row in terminals.values() if row.get("max_stage", 0) >= 5 and isinstance(row.get("hinge_at_release"), (int, float)) and math.isfinite(float(row["hinge_at_release"]))]
    return {"episodes": EPISODES, "durable_depression": sum(value >= HOLD_STEPS for value in durable.values()), "stage3_admission": sum(row["max_stage"] >= 3 for row in terminals.values()), "stage4_episodes": sum(row["max_stage"] >= 4 for row in terminals.values()), "open_hold_episodes": sum(value >= HOLD_STEPS for value in open_hold.values()), "stage5_episodes": sum(row["max_stage"] >= 5 for row in terminals.values()), "goal_episodes": sum(row.get("terminal_reasons") == "complete" for row in terminals.values()), "hinge_highwater_p50": percentile(highwater, .5), "hinge_highwater_p95": percentile(highwater, .95), "stage4_dwell_p50": percentile(dwell, .5), "release_hinge_p50": percentile(release, .5), "k5_pass_rate": k5 / EPISODES, "press_handle_contact_force_p50": percentile(press_forces, .5), "over_force_step_share": None if trace_steps == 0 else over_force_steps / trace_steps, "arm_j4_p95": percentile(arm_j4, .95), "arm_j4_limit_residence_step_share": None if trace_steps == 0 else arm_j4_limit_steps / trace_steps, "integrity_violations": integrity, "terminal_reasons": dict(collections.Counter(row["terminal_reasons"] for row in terminals.values()))}


def trace_summary(path: Path, step: int) -> dict:
    require(path.is_file(), f"missing K trace: {path}")
    all_rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    rows = [row for row in all_rows if row.get("common_step", step * 64 + 1) <= step * 64]
    require(rows, f"empty K trace prefix through batch {step}: {path}")
    required = {"update_index", "common_step", "scale_before", "scale_after", "driver_left", "driver_right", "natural_sample_left", "natural_sample_right", "skipped"}
    scales, skipped = [], 0
    previous_common_step = -1
    for index, row in enumerate(rows):
        require(isinstance(row, dict) and required <= set(row), f"{path}: trace schema row {index}")
        require(row["update_index"] == index and isinstance(row["common_step"], int) and previous_common_step <= row["common_step"] <= step * 64, f"{path}: trace ordering row {index}")
        previous_common_step = row["common_step"]
        for key in ("scale_before", "scale_after"):
            require(isinstance(row[key], (int, float)) and math.isfinite(float(row[key])), f"{path}: trace {key} row {index}")
        for key in ("driver_left", "driver_right"):
            require(row[key] is None or (isinstance(row[key], (int, float)) and math.isfinite(float(row[key]))), f"{path}: trace {key} row {index}")
        for key in ("natural_sample_left", "natural_sample_right"):
            require(isinstance(row[key], int) and row[key] >= 0, f"{path}: trace {key} row {index}")
        require(isinstance(row["skipped"], bool), f"{path}: trace skipped row {index}")
        require((row["driver_left"] is None or row["driver_right"] is None) is row["skipped"], f"{path}: trace skip/driver mismatch row {index}")
        scale = float(row["scale_after"])
        require(0.2 <= scale <= 1.0, f"{path}: trace scale outside clip bounds row {index}")
        scales.append(scale); skipped += int(row["skipped"])
    directions: list[int] = []
    for before, after in zip(scales, scales[1:], strict=False):
        if before >= .5 > after: directions.append(-1)
        elif before < .5 <= after: directions.append(1)
    return {"through_batch": step, "max_common_step": step * 64, "scale_min": min(scales), "first_update_below_0.95": next((rows[i]["update_index"] for i, value in enumerate(scales) if value < .95), None), "share_of_updates_below_0.5": sum(value < .5 for value in scales) / len(scales), "reversal_count": sum(left != right for left, right in zip(directions, directions[1:], strict=False)), "skipped_updates": skipped, "trace_rows": len(rows)}


def typed_outcomes(cells: dict[str, dict[str, dict]], traces: dict[str, dict], driver_mismatch_cells: set[str]) -> dict:
    def no_regress(arm: str) -> bool:
        return all(cells[f"{arm}_{source}"][side][metric] >= cells[f"C_{source}"][side][metric] - 8 for source in ("S1", "S2") for side in SIDES for metric in ("durable_depression", "stage4_episodes"))
    w_entry = cells["W_S2"]["left"]["stage4_episodes"] >= 16 and cells["W_S2"]["left"]["open_hold_episodes"] >= 8 and cells["W_S2"]["right"]["stage4_episodes"] >= 48
    w_delta = cells["W_S2"]["left"]["stage4_episodes"] - cells["C_S2"]["left"]["stage4_episodes"]
    w_no_regress = no_regress("W")
    c_entry = cells["C_S2"]["left"]["stage4_episodes"] >= 16 and cells["C_S2"]["left"]["open_hold_episodes"] >= 8 and cells["C_S2"]["right"]["stage4_episodes"] >= 48
    if c_entry and w_no_regress: w = "W_NOT_DIFFERENT"
    elif w_entry and w_delta >= 8 and w_no_regress: w = "W_STAGE34_SUPPORTED"
    elif not w_no_regress: w = "W_REGRESSED"
    elif abs(w_delta) < 8: w = "W_NOT_DIFFERENT"
    else: w = "INCONCLUSIVE"
    labels = []
    if min(cells["W_S1"][side]["stage5_episodes"] for side in SIDES) <= min(cells["C_S1"][side]["stage5_episodes"] for side in SIDES) - 8: labels.append("W_HARMFUL_DOWNSTREAM")
    c_labels = []
    c_consolidated = min(cells["C_S1"][side]["stage5_episodes"] for side in SIDES) >= 32 and min(cells["C_S1"][side]["open_hold_episodes"] for side in SIDES) >= 32 and all(cells["C_S1"][side]["durable_depression"] >= 32 for side in SIDES)
    if c_entry: c_labels.append("C_ENTRY_EMERGED")
    if c_consolidated: c_labels.append("C_CONSOLIDATED")
    k_s1_engaged, k_s2_engaged = traces["K_S1"]["scale_min"] < .95, traces["K_S2"]["scale_min"] < .95
    k_s2_invalid = k_s2_engaged and cells["K_S2"]["left"]["stage4_episodes"] < 32
    k_s2_identity = not k_s2_engaged and all(abs(cells["K_S2"][side][metric] - cells["C_S2"][side][metric]) < 8 for side in SIDES for metric in ("durable_depression", "stage4_episodes"))
    if k_s2_invalid: k = "K_DRIVER_INVALID"
    elif not k_s2_engaged and not k_s2_identity: k = "K_IDENTITY_VIOLATED"
    elif not no_regress("K"): k = "K_REGRESSED"
    elif k_s1_engaged and min(cells["K_S1"][side]["stage5_episodes"] for side in SIDES) >= min(cells["C_S1"][side]["stage5_episodes"] for side in SIDES) + 8: k = "K_SUPPORTED"
    elif k_s1_engaged and abs(min(cells["K_S1"][side]["stage5_episodes"] for side in SIDES) - min(cells["C_S1"][side]["stage5_episodes"] for side in SIDES)) < 8: k = "K_NEUTRAL"
    else: k = "INCONCLUSIVE"
    k_labels = (["K_ENGAGED"] if k_s1_engaged else ["K_INERT"]) + (["K_S2_ENGAGED"] if k_s2_engaged else ["K_S2_INERT"])
    if k_s2_identity: k_labels.append("K_IDENTITY_HOLDS")
    if driver_mismatch_cells: k_labels.append("K_DRIVER_MISMATCH")
    if traces["K_S1"]["reversal_count"] >= 3: k_labels.append("K_OSCILLATING")
    return {"W": {"outcome": w, "labels": labels}, "C": {"labels": c_labels}, "K": {"outcome": k, "labels": k_labels, "driver_mismatch_cells": sorted(driver_mismatch_cells)}, "wave2": {"B1": "RUN" if k not in {"K_REGRESSED", "K_DRIVER_INVALID", "K_IDENTITY_VIOLATED"} else "NOT_RUN", "B2": "RUN" if w == "W_STAGE34_SUPPORTED" and k == "K_SUPPORTED" else "NOT_RUN"}}


def warm_start_sanity(cells: dict[str, dict[str, dict]], step: int, prior: dict | None) -> dict:
    if step not in (500, 1000):
        return {}
    results = {}
    for source in ("S1", "S2"):
        if step == 1000 and prior is not None and prior.get("warm_start_sanity", {}).get(source, {}).get("status") != "WARM_START_TRANSIENT":
            continue
        retained = all(
            cells[f"C_{source}"][side][metric] >= SOURCE_ENDPOINT[source][side][metric] - 16
            for side in SIDES
            for metric in ("durable_depression", "stage4_episodes")
        )
        results[source] = {
            "status": "WARM_START_RETAINED" if retained else "WARM_START_TRANSIENT",
            "source_endpoint": SOURCE_ENDPOINT[source],
            "checked_at_step": step,
        }
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--step", type=int, choices=STEPS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite milestone reducer: {args.output}")
    prior = None
    stopped_before: set[str] = set()
    if args.step != STEPS[0]:
        prior = load_json(args.eval_root.parent / f"step{STEPS[STEPS.index(args.step)-1]}" / "reducer.json")
        require(prior.get("schema") == "a2_piper_base_v26_8_milestone_reducer_v1", "preceding reducer schema")
        stopped_before = set(prior.get("stop_cells", ()))
    active = tuple(cell for cell in CELLS if cell not in stopped_before)
    require(active, "no active v26-8 cells remain; no further reducer is permitted")
    contracts = {cell: validated_contract(args.train_root, cell) for cell in CELLS}
    cells = {} if prior is None else dict(prior["cells"])
    for cell in active:
        cells[cell] = {side: side_summary(args.eval_root / f"{cell}_STEP{args.step}" / side, side, contracts[cell]["seed"]) for side in SIDES}
    failures = [f"INTEGRITY_VIOLATIONS:{cell}/{side}" for cell in active for side in SIDES if cells[cell][side]["integrity_violations"] != 0]
    k_trace = {cell: trace_summary(args.train_root / cell / "a2_v26_8_penalty_curriculum_trace.jsonl", args.step) for cell in ("K_S1", "K_S2")}
    deltas: dict[str, dict[str, dict[str, int]]] = {}
    for source in ("S1", "S2"):
        deltas[source] = {}
        for arm in ("W", "K"):
            deltas[source][arm] = {side: {metric: cells[f"{arm}_{source}"][side][metric] - cells[f"C_{source}"][side][metric] for metric in ("durable_depression", "stage4_episodes", "open_hold_episodes", "stage5_episodes", "goal_episodes")} for side in SIDES}
    collapsed = []
    if prior is not None:
        for cell in active:
            if all(cells[cell][side]["durable_depression"] < 8 and prior["cells"][cell][side]["durable_depression"] < 8 for side in SIDES): collapsed.append(cell)
    endpoint = args.step == 3000
    driver_mismatch_cells = set() if prior is None else set(prior.get("k_driver_mismatch_cells_ever", ()))
    driver_mismatch_cells.update(cell for cell in ("K_S1", "K_S2") if k_trace[cell]["scale_min"] < 0.95 and min(cells[cell][side]["stage4_episodes"] for side in SIDES) < 32)
    outcomes = typed_outcomes(cells, k_trace, driver_mismatch_cells) if endpoint and not failures else None
    payload = {"schema": "a2_piper_base_v26_8_milestone_reducer_v1", "status": "EXPERIMENT_INVALID" if failures else "EXPERIMENT_COMPLETE", "step": args.step, "train_root": str(args.train_root), "eval_root": str(args.eval_root), "resolved_contracts": contracts, "active_cells": list(active), "stopped_before_step": sorted(stopped_before), "cells": cells, "k_trace_metrics": k_trace, "k_driver_mismatch_cells_ever": sorted(driver_mismatch_cells), "paired_deltas_arm_minus_C": deltas, "warm_start_sanity": warm_start_sanity(cells, args.step, prior), "early_collapsed_cells": collapsed, "typed_outcomes": outcomes, "route": "V26_8_INVALID" if failures else ("V26_8_ENDPOINT_READY" if endpoint else "V26_8_MILESTONE_REPORTED"), "stop_cells": sorted(stopped_before | set(collapsed)), "failures": failures}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"step": args.step, "route": payload["route"], "stop_cells": payload["stop_cells"], "output": str(args.output)}))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
