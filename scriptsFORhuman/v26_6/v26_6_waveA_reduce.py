#!/usr/bin/env python3
"""Reduce v26-6 Wave A gripper-capability eval-only A/B into a typed route.

Thresholds and strata are fixed by
``scriptsFORhuman/v26_6/a2_piper_base_v26_6_waveA_gripper_capacity_plan_20260831.md``
and are not derived from the observed results.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

SCHEMA = "a2_piper_base_v26_6_waveA_gripper_capacity_reducer_v1"
STRATA = (("1.0-1.6", 1.0, 1.6), ("1.6-2.2", 1.6, 2.2), ("2.2-3.0", 2.2, 3.0001))
DOOR_KEYS = ("door_handle_drive_max_force", "door_hinge_drive_max_force",
             "door_handle_height", "door_weight", "door_open_lr")
PRESS_RAD = 0.3
HOLD_RAD = 0.6
PRIMARY_STRATUM = "1.6-2.2+"          # the two strata above the observed control boundary
CONFIRM_MIN = 22                      # of 43 primary-stratum episodes
PARTIAL_MIN = 5
STAGE3_MIN = 48                       # of 64


def load_side(path: Path) -> dict[int, list[dict]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"empty or malformed trace: {path}")
    by: dict[int, list[dict]] = collections.defaultdict(list)
    for row in rows:
        by[int(row["env_id"])].append(row)
    return dict(by)


def door_signature(by: dict[int, list[dict]]) -> list[list]:
    return [[env] + [float(by[env][0][k]) for k in DOOR_KEYS] for env in sorted(by)]


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1)))]


def summarize(by: dict[int, list[dict]]) -> dict:
    n = len(by)
    strata = {}
    for name, lo, hi in STRATA:
        sel = [rows for rows in by.values()
               if lo <= float(rows[0]["door_handle_drive_max_force"]) < hi]
        strata[name] = {
            "n": len(sel),
            "handle_ge_0_3": sum(1 for r in sel if float(r[-1]["v26_2"]["max_handle_rad"]) >= PRESS_RAD),
            "handle_ge_0_6": sum(1 for r in sel if float(r[-1]["v26_2"]["max_handle_rad"]) >= HOLD_RAD),
        }
    primary_n = strata["1.6-2.2"]["n"] + strata["2.2-3.0"]["n"]
    primary_press = strata["1.6-2.2"]["handle_ge_0_3"] + strata["2.2-3.0"]["handle_ge_0_3"]

    press_forces, over_force_steps, stable_steps, total_steps, longest_hold = [], 0, 0, 0, []
    for rows in by.values():
        run = best = 0
        for row in rows:
            total_steps += 1
            if bool(row["over_force"]):
                over_force_steps += 1
            if bool(row["contact_stability"]):
                stable_steps += 1
            if float(row["door_handle_joint_pos"]) > PRESS_RAD:
                run += 1
                best = max(best, run)
                press_forces.append(sum(float(v) for v in row["handle_contact_force_norm"]))
            else:
                run = 0
        longest_hold.append(best)

    terminal = [rows[-1] for rows in by.values()]
    return {
        "episodes": n,
        "strata": strata,
        "primary_stratum": {"name": PRIMARY_STRATUM, "n": primary_n, "handle_ge_0_3": primary_press},
        "handle_ge_0_3_total": sum(1 for t in terminal if float(t["v26_2"]["max_handle_rad"]) >= PRESS_RAD),
        "handle_ge_0_6_total": sum(1 for t in terminal if float(t["v26_2"]["max_handle_rad"]) >= HOLD_RAD),
        "stage3_admission": sum(1 for t in terminal if int(t["v26_2"]["stage3_or_later"])),
        "k5_episodes": sum(1 for t in terminal if int(t["v26_2"]["k5_steps"]) > 0),
        "hinge_ge_0_1": sum(1 for t in terminal if float(t["v26_2"]["max_hinge_rad"]) >= 0.1),
        "hinge_ge_0_25": sum(1 for t in terminal if float(t["v26_2"]["max_hinge_rad"]) >= 0.25),
        "stage4_episodes": sum(1 for t in terminal if int(t["v26_2"]["stage4_or_later"])),
        "max_hinge_rad_max": max(float(t["v26_2"]["max_hinge_rad"]) for t in terminal),
        "longest_press_run_steps_max": max(longest_hold),
        "longest_press_run_steps_p50": quantile(longest_hold, 0.5),
        "press_handle_force_p50": quantile(press_forces, 0.5),
        "press_handle_force_p90": quantile(press_forces, 0.9),
        "press_steps": len(press_forces),
        "over_force_step_share": over_force_steps / total_steps if total_steps else None,
        "contact_stability_rate": stable_steps / total_steps if total_steps else None,
        "integrity_violations": sum(int(t["v26_2"]["integrity_violations"]) + int(t["v26_3"]["integrity_violations"])
                                    for t in terminal),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--control-reference", type=Path, required=True,
                    help="existing R15_S1_STEP0250 directory used as the frozen control")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")

    cells, failures = {}, []
    for arm in ("control", "restored"):
        for side in ("left", "right"):
            trace = args.root / arm / side / "stage2_5_step_trace.json"
            if trace.exists():
                cells[f"{arm}/{side}"] = (load_side(trace), summarize(load_side(trace)))
    for side in ("left", "right"):
        trace = args.control_reference / side / "stage2_5_step_trace.json"
        if trace.exists():
            cells[f"reference/{side}"] = (load_side(trace), summarize(load_side(trace)))

    for key in ("restored/right", "reference/right"):
        if key not in cells:
            raise RuntimeError(f"missing required cell {key}")

    # Gate 1/2: matched door sampling against the frozen control.
    matched = {}
    ref_sig = door_signature(cells["reference/right"][0])
    for key in ("restored/right", "control/right"):
        if key in cells:
            same = door_signature(cells[key][0]) == ref_sig
            matched[key] = same
            if not same:
                failures.append(f"DOOR_SAMPLING_NOT_MATCHED:{key}")
    if "restored/left" in cells and "reference/left" in cells:
        same = door_signature(cells["restored/left"][0]) == door_signature(cells["reference/left"][0])
        matched["restored/left"] = same
        if not same:
            failures.append("DOOR_SAMPLING_NOT_MATCHED:restored/left")

    # Determinism observation (reported, not a hard gate).
    reproduction = None
    if "control/right" in cells:
        a = {e: float(r[-1]["v26_2"]["max_handle_rad"]) for e, r in cells["control/right"][0].items()}
        b = {e: float(r[-1]["v26_2"]["max_handle_rad"]) for e, r in cells["reference/right"][0].items()}
        reproduction = {
            "exact_match": a == b,
            "max_abs_delta": max(abs(a[e] - b[e]) for e in a) if a.keys() == b.keys() else None,
            "press_count_control_rerun": sum(1 for v in a.values() if v >= PRESS_RAD),
            "press_count_reference": sum(1 for v in b.values() if v >= PRESS_RAD),
        }

    summaries = {k: v[1] for k, v in cells.items()}
    for key, summary in summaries.items():
        if summary["integrity_violations"]:
            failures.append(f"INTEGRITY_VIOLATIONS:{key}")

    treated = summaries["restored/right"]
    h = treated["primary_stratum"]["handle_ge_0_3"]
    s = treated["stage3_admission"]
    if failures:
        route = "WAVE_A_INVALID"
    elif s < STAGE3_MIN:
        route = "TREATMENT_GRASP_GATE_REGRESSION"
    elif h >= CONFIRM_MIN:
        route = "GRIPPER_CAPACITY_CONFIRMED"
    elif h >= PARTIAL_MIN:
        route = "GRIPPER_CAPACITY_PARTIAL"
    else:
        route = "GRIPPER_CAPACITY_NOT_CONFIRMED"

    payload = {
        "schema": SCHEMA,
        "root": str(args.root),
        "control_reference": str(args.control_reference),
        "checkpoint": "logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260831_r15/train/R15_S1/model_step_000250.pt",
        "preregistered_thresholds": {
            "primary_cell": "restored/right",
            "primary_stratum": PRIMARY_STRATUM,
            "press_rad": PRESS_RAD,
            "confirm_min": CONFIRM_MIN,
            "partial_min": PARTIAL_MIN,
            "stage3_admission_min": STAGE3_MIN,
        },
        "door_sampling_matched": matched,
        "control_reproduction": reproduction,
        "cells": summaries,
        "failures": failures,
        "route": route,
        "status": "EXPERIMENT_COMPLETE" if not failures else "EXPERIMENT_INVALID",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"route": route, "primary_handle_ge_0_3": h, "stage3_admission": s,
                      "failures": failures, "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
