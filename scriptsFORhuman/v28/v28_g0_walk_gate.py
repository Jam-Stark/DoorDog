"""Compare a v28 flat-walk result with its matched old-asset baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare(baseline_path: Path, candidate_path: Path):
    baseline = json.loads(baseline_path.read_text())
    candidate = json.loads(candidate_path.read_text())
    for key in ("num_envs", "seed", "arm_joint_names", "arm_posture_rad", "policy_dt_s", "sim_dt_s", "policy_path"):
        if baseline[key] != candidate[key]:
            raise ValueError(f"unmatched walk input {key}: {baseline[key]} != {candidate[key]}")
    if candidate["num_envs"] != 64 or set(baseline["blocks"]) != set(candidate["blocks"]):
        raise ValueError("G0-L requires matched 64-env command blocks")
    errors, failures = [], []
    baseline_falls, candidate_falls = {}, {}
    for name, actual in candidate["blocks"].items():
        reference = baseline["blocks"][name]
        baseline_falls[name] = reference["falls"]["unique_envs"]
        candidate_falls[name] = actual["falls"]["unique_envs"]
        if reference["control_samples"] != actual["control_samples"]:
            raise ValueError(f"unmatched control samples: {name}")
        for axis, stats in actual["tracking_error_abs"].items():
            old, new = reference["tracking_error_abs"][axis]["p50"], stats["p50"]
            passed = new <= old * 1.15
            record = {"block": name, "axis": axis, "baseline_p50": old, "candidate_p50": new,
                      "limit": old * 1.15, "ratio": None if old == 0.0 else new / old, "pass": passed}
            errors.append(record)
            if not passed:
                failures.append(record)
    old_slope = baseline["blocks"]["vx050"]["tracking_slope_realized_over_command"]["vx"]
    new_slope = candidate["blocks"]["vx050"]["tracking_slope_realized_over_command"]["vx"]
    slope_pass = new_slope >= old_slope - 0.05
    baseline_ok = all(count == 0 for count in baseline_falls.values())
    passed = baseline_ok and all(count == 0 for count in candidate_falls.values()) and not failures and slope_pass
    return {"schema": "a2_piper_v28_g0_l_comparison_v1", "evidence_level": "RUNTIME",
            "status": "PASS" if passed else "FAIL", "baseline": str(baseline_path), "candidate": str(candidate_path),
            "posture_rad": candidate["arm_posture_rad"], "baseline_admissible_zero_falls": baseline_ok,
            "baseline_falls_by_block": baseline_falls, "candidate_falls_by_block": candidate_falls,
            "tracking_p50_definition": "every recorded command block and all five physical-command axes; candidate <= 1.15 * matched baseline, without a numerical floor",
            "tracking_errors": errors, "tracking_failures": failures,
            "vx050_slope": {"baseline": old_slope, "candidate": new_slope, "limit": old_slope - 0.05, "pass": slope_pass},
            "owner_failure_route": "STOP; preserve data; no threshold or geometry repair"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "tracking_failures": len(result["tracking_failures"]), "vx050_slope": result["vx050_slope"]}))
    raise SystemExit(0 if result["status"] == "PASS" else 2)
