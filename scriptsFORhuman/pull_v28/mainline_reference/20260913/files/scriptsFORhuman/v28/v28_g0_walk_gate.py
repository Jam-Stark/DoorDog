"""Compare a v28 flat-walk result with its matched old-asset baseline."""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

P50_FLOORS = {"vx_mps": 2e-3, "vy_mps": 2e-3, "yaw_radps": 4e-3,
              "pitch_rad": None, "roll_rad": None}
CAPS = {"vx_mps": 0.1, "vy_mps": 0.1, "yaw_radps": 0.1,
        "pitch_rad": 0.05, "roll_rad": 0.04}
AXES = ("vx_mps", "vy_mps", "yaw_radps", "pitch_rad", "roll_rad")
SLOPE_AXES = ("vx", "vy", "yaw", "pitch", "roll")


def command_classes(command_path: Path, harness_path: Path, policy_dt: float):
    spec = importlib.util.spec_from_file_location("v28_frozen_walk_harness", harness_path)
    harness = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = harness
    spec.loader.exec_module(harness)
    program = harness.load_command_program(command_path, policy_dt)
    return {block.name: {axis: any(command[index] != 0.0 for command in block.commands)
                         for index, axis in enumerate(AXES)} for block in program.blocks}


def compare(baseline_path: Path, candidate_path: Path, command_path: Path,
            harness_path: Path, comparison_kind: str = "asset"):
    baseline = json.loads(baseline_path.read_text())
    candidate = json.loads(candidate_path.read_text())
    matched_keys = ["num_envs", "arm_joint_names", "arm_posture_rad", "policy_dt_s", "sim_dt_s", "policy_path"]
    if comparison_kind == "asset":
        matched_keys.append("seed")
    elif comparison_kind == "seed":
        matched_keys.append("usd_file")
        if baseline["seed"] == candidate["seed"]:
            raise ValueError("seed self-comparison requires distinct seeds on the same asset")
    else:
        raise ValueError(f"unsupported comparison kind: {comparison_kind}")
    for key in matched_keys:
        if baseline[key] != candidate[key]:
            raise ValueError(f"unmatched walk input {key}: {baseline[key]} != {candidate[key]}")
    if candidate["num_envs"] != 64 or set(baseline["blocks"]) != set(candidate["blocks"]):
        raise ValueError("G0-L requires matched 64-env command blocks")
    classes = command_classes(command_path, harness_path, candidate["policy_dt_s"])
    if set(classes) != set(candidate["blocks"]):
        raise ValueError("metrics command blocks differ from the authoritative command script")
    errors, failures, d36_failures, legacy_failures = [], [], [], []
    baseline_falls, candidate_falls = {}, {}
    for name, actual in candidate["blocks"].items():
        reference = baseline["blocks"][name]
        baseline_falls[name] = reference["falls"]["unique_envs"]
        candidate_falls[name] = actual["falls"]["unique_envs"]
        if reference["control_samples"] != actual["control_samples"]:
            raise ValueError(f"unmatched control samples: {name}")
        for axis, slope_axis in zip(AXES, SLOPE_AXES, strict=True):
            commanded = classes[name][axis]
            for side, block in (("baseline", reference), ("candidate", actual)):
                slope_present = block["tracking_slope_realized_over_command"][slope_axis] is not None
                if slope_present != commanded:
                    raise ValueError(f"{side} {name}/{axis}: slope null/non-null disagrees with command script")
            stats = actual["tracking_error_abs"][axis]
            old, new = reference["tracking_error_abs"][axis]["p50"], stats["p50"]
            old_p95, new_p95 = reference["tracking_error_abs"][axis]["p95"], stats["p95"]
            limit_ratio = old * 1.15
            floor = P50_FLOORS[axis]
            d36_limit = max(limit_ratio, floor) if floor is not None else limit_ratio
            cap = None if commanded else CAPS[axis]
            limit = limit_ratio if commanded else max(limit_ratio, cap)
            cap_applied = not commanded and new > limit_ratio
            pass_p50, pass_p95 = new <= limit, new_p95 <= old_p95 * 1.15
            passed = pass_p50 and pass_p95
            record = {"block": name, "axis": axis, "baseline_p50": old, "candidate_p50": new,
                      "axis_class": "commanded" if commanded else "coupled",
                      "limit_ratio": limit_ratio, "cap": cap, "cap_applied": cap_applied,
                      "cap_sets_limit": cap is not None and cap > limit_ratio,
                      "candidate_over_cap": None if cap is None else new / cap,
                      "d36_limit": d36_limit, "d36_pass_p50": new <= d36_limit,
                      "limit": limit, "ratio": None if old == 0.0 else new / old,
                      "baseline_p95": old_p95, "candidate_p95": new_p95, "limit_p95": old_p95 * 1.15,
                      "ratio_p95": None if old_p95 == 0.0 else new_p95 / old_p95,
                      "pass_p50": pass_p50, "pass_p95": pass_p95, "pass": passed}
            errors.append(record)
            if not passed:
                failures.append(record)
            if new > d36_limit or not pass_p95:
                d36_failures.append(record)
            if new > limit_ratio:
                legacy_failures.append(record)
    old_slope = baseline["blocks"]["vx050"]["tracking_slope_realized_over_command"]["vx"]
    new_slope = candidate["blocks"]["vx050"]["tracking_slope_realized_over_command"]["vx"]
    slope_pass = new_slope >= old_slope - 0.05
    baseline_ok = all(count == 0 for count in baseline_falls.values())
    candidate_ok = all(count == 0 for count in candidate_falls.values())
    passed = baseline_ok and candidate_ok and not failures and slope_pass
    legacy_passed = baseline_ok and candidate_ok and not legacy_failures and slope_pass
    d36_passed = baseline_ok and candidate_ok and not d36_failures and slope_pass
    class_summary = {}
    for axis_class in ("commanded", "coupled"):
        rows = [row for row in errors if row["axis_class"] == axis_class]
        ratios = [row["ratio"] for row in rows if row["ratio"] is not None]
        class_summary[axis_class] = {"count": len(rows), "defined_ratio_count": len(ratios),
            "ratio_median": statistics.median(ratios), "ratio_max": max(ratios),
            "ratio_gt_1p15_count": sum(row["candidate_p50"] > row["limit_ratio"] for row in rows),
            "p95_ratio_max": max(row["ratio_p95"] for row in rows),
            "cap_applied_count": sum(row["cap_applied"] for row in rows)}
    return {"schema": "a2_piper_v28_g0_l_comparison_v3", "criterion_version": "d37", "evidence_level": "RUNTIME",
            "status": "PASS" if passed else "FAIL", "baseline": str(baseline_path), "candidate": str(candidate_path),
            "d36_status": "PASS" if d36_passed else "FAIL", "d36_tracking_failures": d36_failures,
            "legacy_status": "PASS" if legacy_passed else "FAIL", "legacy_tracking_failures": legacy_failures,
            "comparison_kind": comparison_kind, "baseline_seed": baseline["seed"], "candidate_seed": candidate["seed"],
            "command_script": str(command_path), "command_parser_harness": str(harness_path),
            "axis_class_definition": "commanded iff any executed command-script step is nonzero on that axis; both slope null/non-null values must agree",
            "cap_applied_definition": "coupled axis failed the ratio branch and therefore requires the CAP branch; cap_sets_limit separately identifies max(CAP, ratio_limit)",
            "class_summary": class_summary,
            "posture_rad": candidate["arm_posture_rad"], "baseline_admissible_zero_falls": baseline_ok,
            "baseline_falls_by_block": baseline_falls, "candidate_falls_by_block": candidate_falls,
            "tracking_p50_definition": "commanded axes: candidate_p50 <= 1.15 * baseline_p50; coupled axes: candidate_p50 <= max(1.15 * baseline_p50, CAP_axis); CAP vx/vy 0.1 m/s, yaw 0.1 rad/s, pitch 0.05 rad, roll 0.04 rad",
            "tracking_p95_definition": "every recorded command block and all five physical-command axes; candidate_p95 <= 1.15 * baseline_p95; no floor",
            "tracking_errors": errors, "tracking_failures": failures,
            "vx050_slope": {"baseline": old_slope, "candidate": new_slope, "limit": old_slope - 0.05, "pass": slope_pass},
            "owner_failure_route": "STOP; preserve data; no threshold or geometry repair"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--command-script", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--comparison-kind", choices=("asset", "seed"), default="asset")
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate, args.command_script, args.harness, args.comparison_kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "tracking_failures": len(result["tracking_failures"]), "vx050_slope": result["vx050_slope"]}))
    raise SystemExit(0 if result["status"] == "PASS" else 2)
