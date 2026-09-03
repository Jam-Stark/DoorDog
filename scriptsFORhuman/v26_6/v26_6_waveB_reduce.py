#!/usr/bin/env python3
"""Reduce the v26-6 Wave B four-cell matrix into a typed route.

Thresholds are fixed by
``scriptsFORhuman/v26_6/a2_piper_base_v26_6_waveB_gripper_capability_plan_20260831.md``
(section "Wave B") before any cell was launched.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import yaml

SCHEMA = "a2_piper_base_v26_6_waveB_reducer_v1"
CELLS = ("B0_S0", "B0_S1", "B1_S0", "B1_S1")
STEPS = ("250", "500", "750")
SIDES = ("left", "right")
STRATA = (("1.0-1.6", 1.0, 1.6), ("1.6-2.2", 1.6, 2.2), ("2.2-3.0", 2.2, 3.0001))

DURABLE_RAD = 0.6           # handle angle counted as a real depression
DURABLE_STEPS = 25          # contiguous control steps required to call it durable
DURABLE_MIN = 32            # of 64, per side, for the depression gate
STAGE4_MIN = 2              # of 64, per side, for the unlock gate
EXPECTED_NEAR_CLOSED = {"B0": 0.1, "B1": 0.25}


def load_side(path: Path) -> dict[int, list[dict]]:
    by: dict[int, list[dict]] = collections.defaultdict(list)
    for row in json.loads(path.read_text(encoding="utf-8")):
        by[int(row["env_id"])].append(row)
    if not by:
        raise RuntimeError(f"empty trace: {path}")
    return dict(by)


def durable_run(rows: list[dict]) -> int:
    run = best = 0
    for row in rows:
        if float(row["door_handle_joint_pos"]) >= DURABLE_RAD:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def summarize(by: dict[int, list[dict]]) -> dict:
    terminal = {e: rows[-1] for e, rows in by.items()}
    runs = {e: durable_run(rows) for e, rows in by.items()}
    strata = {}
    for name, lo, hi in STRATA:
        sel = [e for e, rows in by.items() if lo <= float(rows[0]["door_handle_drive_max_force"]) < hi]
        strata[name] = {
            "n": len(sel),
            "durable_depression": sum(1 for e in sel if runs[e] >= DURABLE_STEPS),
            "hinge_ge_0_25": sum(1 for e in sel if float(terminal[e]["v26_2"]["max_hinge_rad"]) >= 0.25),
        }
    return {
        "episodes": len(by),
        "strata": strata,
        "durable_depression": sum(1 for v in runs.values() if v >= DURABLE_STEPS),
        "handle_ge_0_6": sum(1 for t in terminal.values() if float(t["v26_2"]["max_handle_rad"]) >= DURABLE_RAD),
        "durable_run_steps_p50": sorted(runs.values())[len(runs) // 2],
        "durable_run_steps_max": max(runs.values()),
        "stage3_admission": sum(1 for t in terminal.values() if int(t["v26_2"]["stage3_or_later"])),
        "hinge_ge_0_1": sum(1 for t in terminal.values() if float(t["v26_2"]["max_hinge_rad"]) >= 0.1),
        "hinge_ge_0_25": sum(1 for t in terminal.values() if float(t["v26_2"]["max_hinge_rad"]) >= 0.25),
        "max_hinge_rad_max": max(float(t["v26_2"]["max_hinge_rad"]) for t in terminal.values()),
        "stage4_episodes": sum(1 for t in terminal.values() if int(t["v26_2"]["stage4_or_later"])),
        "stage5_episodes": sum(1 for t in terminal.values() if int(t["v26_2"]["stage5_or_later"])),
        "goal_episodes": sum(1 for t in terminal.values() if t["terminal_reasons"] == "complete"),
        "terminal_reasons": dict(collections.Counter(t["terminal_reasons"] for t in terminal.values())),
        "integrity_violations": sum(int(t["v26_2"]["integrity_violations"]) + int(t["v26_3"]["integrity_violations"])
                                    for t in terminal.values()),
    }


def check_contract(train_root: Path, cell: str) -> dict:
    resolved = yaml.safe_load((train_root / cell / "resolved_config.yaml").read_text(encoding="utf-8"))
    env_cfg, robot = resolved["env"]["config"], resolved["robot"]
    return {
        "gripper_effort": [float(v) for v in robot["dof_effort_limit_list"][-2:]],
        "gripper_kp": float(robot["control"]["stiffness"]["arm_j7"]),
        "gripper_kd": float(robot["control"]["damping"]["arm_j7"]),
        "m39": bool(env_cfg["a2_m39_gripper_material_enabled"]),
        "squeeze_force_max": float(env_cfg["a2_stage2_squeeze_force_max"]),
        "over_force_threshold": float(env_cfg["a2_stage2_over_force_threshold"]),
        "near_closed": float(env_cfg["a2_stage3_unlatch_near_closed_hinge_threshold"]),
        "seed": int(resolved["seed"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-root", type=Path, required=True)
    ap.add_argument("--eval-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")

    failures: list[str] = []
    contracts = {}
    for cell in CELLS:
        contract = check_contract(args.train_root, cell)
        contracts[cell] = contract
        arm = cell.split("_")[0]
        if contract["gripper_effort"] != [45.0, 45.0] or contract["gripper_kp"] != 1300.0 \
                or contract["gripper_kd"] != 32.0 or not contract["m39"] \
                or contract["squeeze_force_max"] != 30.0 or contract["over_force_threshold"] != 55.0:
            failures.append(f"CAPABILITY_BUNDLE_NOT_APPLIED:{cell}")
        if contract["near_closed"] != EXPECTED_NEAR_CLOSED[arm]:
            failures.append(f"WALL_SEAM_NOT_APPLIED:{cell}")
        if contract["seed"] != int(cell[-1]):
            failures.append(f"SEED_MISMATCH:{cell}")

    results: dict[str, dict] = {}
    for cell in CELLS:
        for step in STEPS:
            for side in SIDES:
                trace = args.eval_root / f"{cell}_STEP0{step}" / side / "stage2_5_step_trace.json"
                if not trace.exists():
                    failures.append(f"MISSING_EVAL:{cell}_STEP0{step}/{side}")
                    continue
                summary = summarize(load_side(trace))
                results[f"{cell}/step{step}/{side}"] = summary
                if summary["episodes"] != 64:
                    failures.append(f"NOT_EXACT64:{cell}_STEP0{step}/{side}")
                if summary["integrity_violations"]:
                    failures.append(f"INTEGRITY_VIOLATIONS:{cell}_STEP0{step}/{side}")

    def endpoint(cell: str, side: str) -> dict:
        return results.get(f"{cell}/step750/{side}", {})

    gates = {}
    for cell in CELLS:
        left, right = endpoint(cell, "left"), endpoint(cell, "right")
        gates[cell] = {
            "durable_depression": {"left": left.get("durable_depression"), "right": right.get("durable_depression")},
            "stage4": {"left": left.get("stage4_episodes"), "right": right.get("stage4_episodes")},
            "bilateral_depression_pass": bool(left.get("durable_depression", 0) >= DURABLE_MIN
                                              and right.get("durable_depression", 0) >= DURABLE_MIN),
            "bilateral_stage4_pass": bool(left.get("stage4_episodes", 0) >= STAGE4_MIN
                                          and right.get("stage4_episodes", 0) >= STAGE4_MIN),
            "any_side_depression_pass": bool(max(left.get("durable_depression", 0), right.get("durable_depression", 0)) >= DURABLE_MIN),
            "any_side_stage4": bool(max(left.get("stage4_episodes", 0), right.get("stage4_episodes", 0)) > 0),
        }

    b0_dep = any(gates[c]["any_side_depression_pass"] for c in ("B0_S0", "B0_S1"))
    b1_dep = any(gates[c]["any_side_depression_pass"] for c in ("B1_S0", "B1_S1"))
    b1_s4_bilat = any(gates[c]["bilateral_stage4_pass"] for c in ("B1_S0", "B1_S1"))
    b0_s4_bilat = any(gates[c]["bilateral_stage4_pass"] for c in ("B0_S0", "B0_S1"))
    b1_s4_any = any(gates[c]["any_side_stage4"] for c in ("B1_S0", "B1_S1"))
    b0_s4_any = any(gates[c]["any_side_stage4"] for c in ("B0_S0", "B0_S1"))

    if failures:
        route = "WAVE_B_INVALID"
    elif not (b0_dep or b1_dep):
        route = "DURABLE_DEPRESSION_NOT_LEARNED"
    elif b1_s4_bilat and not b0_s4_bilat:
        route = "WALL_REMOVAL_CAUSAL_BILATERAL_STAGE4"
    elif b0_s4_bilat or b1_s4_bilat:
        route = "BILATERAL_STAGE4_SUPPORTED"
    elif b1_s4_any and not b0_s4_any:
        route = "WALL_REMOVAL_DIRECTIONAL_STAGE4_UNSTABLE"
    elif b0_s4_any or b1_s4_any:
        route = "STAGE4_SEED_OR_SIDE_UNSTABLE"
    else:
        route = "DEPRESSION_LEARNED_STAGE4_NOT_REACHED"

    payload = {
        "schema": SCHEMA,
        "train_root": str(args.train_root),
        "eval_root": str(args.eval_root),
        "preregistered_thresholds": {
            "durable_rad": DURABLE_RAD, "durable_steps": DURABLE_STEPS,
            "durable_min_per_side": DURABLE_MIN, "stage4_min_per_side": STAGE4_MIN,
            "endpoint": "step750",
        },
        "resolved_contracts": contracts,
        "cells": results,
        "endpoint_gates": gates,
        "failures": failures,
        "route": route,
        "status": "EXPERIMENT_COMPLETE" if not failures else "EXPERIMENT_INVALID",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"route": route, "failures": failures, "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
