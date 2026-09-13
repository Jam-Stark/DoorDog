#!/usr/bin/env python3
"""One streaming pass per pull natural trace; per-cell and fixed-three-seed decisions."""
from __future__ import annotations
import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(HERE), str(HERE.parent / "pull_v7"), str(HERE.parent / "pull_v26_8")]
from analyze_p0 import EVENTS, THRESHOLDS, compact, stream, number
from natural_protocol import validate_natural_runtime, _validate_side
from gr00t.rl.envs.door.a2_pull_telemetry import validate_a2_pull_episode, A2_PULL_HARD_GATE_EVENT_PREDECESSORS
from camera_adapter import select_camera, summarize as camera_summary, DEFAULT_RIG, DEFAULT_NATIVE

ORIGINAL = ("PA_S1", "PA_S2", "PA_S3")
SIDES = ("left", "right")
JOINTS = [f"arm_j{i}" for i in range(1,7)]


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text())


def side_summary(directory, side, seed, rig=DEFAULT_RIG, native=DEFAULT_NATIVE):
    runtime = yaml.safe_load((directory / ".hydra/runtime_config.yaml").read_text())
    validate_natural_runtime(runtime, side=side, mirror_enabled=True)
    cfg = runtime["env"]["config"]
    require(runtime["seed"] == seed, "evaluation seed differs from cell")
    require(cfg["a2_pull_threshold_mode"] == "hard_gate", "pull predecessor contract")
    require(cfg["rewards"]["reward_penalty_curriculum"] is False and cfg["a2_v26_8_penalty_driver"] is None, "natural curriculum/driver contract")
    metrics = load(directory / "metrics_eval.json")
    records = load(directory / "a2_v14_per_env_records.json")
    terminals = metrics["episode_terminal_diagnostics"]
    require(metrics["completed_episodes"] == len(terminals) == len(records) == 64, "exact64 artifacts required")
    by_env = {row["env_id"]: row for row in terminals}
    require(set(by_env) == set(range(64)), "terminal exact64 unique env IDs required")
    counts = Counter()
    for terminal in terminals:
        _validate_side(terminal, side, str(directory))
        episode = terminal["pull_v0_episode"]
        validate_a2_pull_episode(episode, event_predecessors=A2_PULL_HARD_GATE_EVENT_PREDECESSORS)
        for event in EVENTS:
            counts[event[:2]] += int(episode["event_reached"][event])
    robot = runtime["robot"]
    limits = {joint: (float(robot["dof_pos_lower_limit_list"][robot["dof_names"].index(joint)]),
                      float(robot["dof_pos_upper_limit_list"][robot["dof_names"].index(joint)])) for joint in JOINTS}
    states = {env: {"rows":0, "last":None, "best":0, "run":0,
        "squeeze":int(terminal["a2_stage2_squeeze_streak"]), "tower":False,
        "ready_steps":0, "clean_steps":0, "handoff":False, "handle_crossed":False, "share":False,
        "phases":Counter(), "post_e5_rows":0, "post_e5_high_margin":0,
        "post_e5_conditions":Counter(), "ready_count_histogram":Counter()} for env, terminal in by_env.items()}
    overshoot = {joint:[] for joint in JOINTS}
    camera_rows = []
    starts = set()
    margin_error = 0.
    require(float(cfg[THRESHOLDS["share"][0]]) == .6, "4B indicator requires frozen share .6")
    for row in stream(directory / "stage2_5_step_trace.json"):
        env = row["env_id"]
        require(isinstance(env,int) and env in states, "trace env ID outside exact64")
        _validate_side(row, side, str(directory))
        require(row["episode_index"] == 0 and row["first_episode_active"] is True
                and row["a2_v26_episode_start_stage"] == 0, "non-natural persisted trace row")
        if row.get("record_type") == "episode_start":
            require(env not in starts and row["stage_buf"] == 0 and row["step_index"] == -1, "invalid/duplicate natural birth")
            starts.add(env)
            continue
        require(env in starts, "trace precedes birth")
        state = states[env]
        step = row["episode_length_buf"]
        require(state["last"] is None or step > state["last"], "nonmonotonic episode counter")
        contiguous = state["last"] is None or step == state["last"] + 1
        state["last"] = step
        state["rows"] += 1
        state["squeeze"] = max(state["squeeze"], int(row["a2_stage2_squeeze_streak"]))
        state["run"] = (state["run"] + 1 if contiguous else 1) if row["door_handle_joint_pos"] >= .6 else 0
        state["best"] = max(state["best"], state["run"])
        c, conditions = compact(row, "pull_v28", side, runtime)
        v6 = row["pull_v0"]["pull_v6"]
        state["phases"][str(c["phase"])] += 1
        state["ready_steps"] += int(c["release_ready"])
        state["clean_steps"] += int(c["clean"])
        state["handoff"] |= v6["handoff_reached"]
        state["handle_crossed"] |= v6["handle_crossed"]
        share = number(v6["arm_tangent_share"])
        state["share"] |= share is not None and share >= .6
        margin_error = max(margin_error, abs(c["margin"] - c["margin_recomputed"]))
        e5 = number(by_env[env]["pull_v0_episode"]["first_event_step"]["E5_CLEARANCE_DECISION"])
        if e5 is not None and step >= e5:
            state["post_e5_rows"] += 1
            state["post_e5_high_margin"] += int(c["margin"] >= .07)
            for condition, passed in conditions.items():
                state["post_e5_conditions"][condition + ("_unknown" if passed is None else "_met" if passed else "_unmet")] += 1
            state["ready_count_histogram"][str(c["ready_condition_count"])] += 1
            require(row["arm_joint_names"] == JOINTS and len(row["arm_joint_pos_target"]) == 6, "six named arm target layout")
            for joint, target in zip(JOINTS,row["arm_joint_pos_target"],strict=True):
                require(math.isfinite(target), "nonfinite commanded target")
                lo,hi = limits[joint]
                overshoot[joint].append(max(0.,target-hi)+max(0.,lo-target))
        camera = select_camera(row)
        # Data come from pull latches, with a separate E6 event denominator.
        expected_post = bool(v6["release_event"] and not row["pull_v0"]["bilateral_handle_contact"]
                             and row["stage_buf"] == 4 and c["phase"] in (2,3))
        require(camera["v28_post_release"] == expected_post, "camera release mask differs from pull latch/C-D contract")
        e6_seen = row["pull_v0_episode"]["event_reached"]["E6_PATH_REVERSAL_ENTRY"]
        require((camera["v28_crossing_yaw_deg"] is not None) == e6_seen, "camera E6 yaw/null mismatch")
        state["tower"] |= camera["v28_tower_contact_force_N"] > 5.
        camera_rows.append(camera)
    require(starts == set(range(64)), "exact64 birth rows required")
    require(all(state["rows"] > 0 for state in states.values()), "v28 all-stage trace requires each natural episode")
    post_count = sum(state["post_e5_rows"] for state in states.values())
    high_count = sum(state["post_e5_high_margin"] for state in states.values())
    require(counts["E5"] == 0 or post_count > 0, "E5 reached without post-E5 samples")
    medians = {joint: statistics.median(values) if values else None for joint,values in overshoot.items()}
    margin_state = "NOT_OBSERVED" if counts["E5"] == 0 else (
        "MARGIN_TRAP_RESOLVED" if high_count > 0 and all(value == 0. for value in medians.values()) else "MARGIN_TRAP_PERSISTS")
    camera = camera_summary(camera_rows, directory / "stage2_5_step_trace.json", rig, native)
    return {"status":"VALID", "denominator":64, "K5":sum(state["squeeze"] >= 5 for state in states.values()),
        "D":sum(state["best"] >= 25 for state in states.values()), **{event[:2]:counts[event[:2]] for event in EVENTS},
        "tower_contact_episode_gt5N":sum(state["tower"] for state in states.values()),
        "margin":{"status":margin_state, "e5_episodes":counts["E5"], "post_e5_samples":post_count,
            "margin_ge_0_07_steps":high_count if post_count else None,
            "margin_ge_0_07_step_fraction":high_count/post_count if post_count else None,
            "joint_target_overshoot_median":medians, "margin_recompute_max_abs_error":margin_error},
        "retained_4a_4b":{"handoff_reached":sum(s["handoff"] for s in states.values()),
            "tangent_share_ge_0_6":sum(s["share"] for s in states.values()), "handle_crossed":sum(s["handle_crossed"] for s in states.values())},
        "release_ready":{"episodes":sum(s["ready_steps"] > 0 for s in states.values()),
            "steps":sum(s["ready_steps"] for s in states.values()), "clean_release_episodes":sum(s["clean_steps"] > 0 for s in states.values()),
            "post_e5_condition_counts":dict(sum((s["post_e5_conditions"] for s in states.values()),Counter())),
            "post_e5_ready_condition_count_histogram":dict(sum((s["ready_count_histogram"] for s in states.values()),Counter()))},
        "terminal_reasons":dict(Counter(row["terminal_reasons"] for row in terminals)),
        "camera":camera, "trace_read_passes":1, "births":len(starts),
        "episodes":[dict(env_id=env, **state) for env,state in states.items()]}


def decision(step, cells, history=None):
    require(set(cells).issubset(ORIGINAL), "only original PA_S1/2/3 cells belong to this decision")
    per_seed = {}
    for cell,sides in cells.items():
        valid = set(sides) == set(SIDES) and all(side["status"] == "VALID" for side in sides.values())
        per_seed[cell] = (all(side[key] >= 60 for side in sides.values() for key in ("K5","D","E4","E5"))
                          and all(side["tower_contact_episode_gt5N"] <= 2 for side in sides.values())) if valid else None
    complete = set(cells) == set(ORIGINAL) and all(value is not None for value in per_seed.values())
    endpoint = step == 6000 and complete
    k = sum(value is True for value in per_seed.values()) if endpoint else None
    route = ("PULL_V28_OPENING_ESTABLISHED" if k >= 2 else "PULL_V28_OPENING_UNSTABLE" if k == 1 else "PULL_V28_OPENING_NOT_ESTABLISHED") if endpoint else (
        "PULL_V28_MILESTONE_INVALID" if any(value is None for value in per_seed.values()) else "PULL_V28_MILESTONE_REPORTED")
    return {"schema":"a2_piper_pull_v28_reducer_v2", "status":"EXPERIMENT_INVALID" if any(value is None for value in per_seed.values()) else "MILESTONE_COMPLETE",
        "step":step, "cells":cells, "per_seed_opening":per_seed, "endpoint":endpoint,
        "endpoint_pending_original_cells":[cell for cell in ORIGINAL if cell not in per_seed or per_seed[cell] is None],
        "k_of_3":{"passing":k,"denominator":3} if endpoint else None, "route":route,
        "history":history or [], "qualification":"opening only; no Teacher/Student eligibility"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--eval-root",type=Path)
    p.add_argument("--step",type=int,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--cells",nargs="+",default=ORIGINAL)
    p.add_argument("--aggregate-decisions",nargs="+",type=Path)
    p.add_argument("--rig",type=Path,default=DEFAULT_RIG)
    p.add_argument("--native-camera",type=Path,default=DEFAULT_NATIVE)
    a=p.parse_args()
    require(not a.output.exists(),f"output already exists: {a.output}")
    require(set(a.cells).issubset(ORIGINAL) and len(set(a.cells)) == len(a.cells), "unique original cells required")
    cells, history = {}, []
    if a.aggregate_decisions:
        for path in a.aggregate_decisions:
            previous=load(path)
            if previous["step"] != a.step:
                history.append({"path":str(path),"step":previous["step"],"per_seed_opening":previous["per_seed_opening"]})
                continue
            require(not set(cells).intersection(previous["cells"]), "duplicate cell decisions for same milestone")
            cells.update(previous["cells"])
    else:
        require(a.eval_root is not None,"--eval-root required for trace reduction")
        for cell in a.cells:
            cells[cell]={}
            for side in SIDES:
                directory=a.eval_root/f"{cell}_STEP{a.step}"/side
                try:
                    cells[cell][side]=side_summary(directory,side,int(cell[-1]),a.rig,a.native_camera)
                except (ValueError,RuntimeError,KeyError,FileNotFoundError,AssertionError) as error:
                    cells[cell][side]={"status":"INVALID", "directory":str(directory),"error":f"{type(error).__name__}: {error}"}
    payload=decision(a.step,cells,history)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    print(json.dumps({"output":str(a.output),"route":payload["route"]}))
    return 2 if payload["status"] == "EXPERIMENT_INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
