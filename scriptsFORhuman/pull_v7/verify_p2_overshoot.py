#!/usr/bin/env python3
"""Offline reference for the pull-v7 D2 reward term.

Recomputes `a2_pull_v7_arm_target_overshoot_penalty`'s raw value from the
step9000 landmark rows already extracted by analyze_p0.py, using the same hard
joint limits the reward method reads
(`simulator.hard_dof_pos_limits`, a verbatim copy of the robot config
`dof_pos_lower/upper_limit_list`; isaacsim.py:2398-2399).

The CSV stores the executor's actual `arm_joint_pos_target`, i.e. the value
`default_dof_pos + action_scale * delta_actions` that PhysX received, so no
action re-derivation is needed here.  Output is the per-side distribution of
each joint's overshoot and of the summed raw reward, so a runtime smoke value
can be compared against it.

Run: python scriptsFORhuman/pull_v7/verify_p2_overshoot.py
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WAVE = "a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2"
JOINTS = [f"arm_j{j}" for j in range(1, 7)]
# analyze_p0.py landmark labels that carry expanded joint rows.
E5_LANDMARKS = ("E5", "E5+25", "E5+50", "E5+100")


def hard_limits(source: str) -> dict[str, tuple[float, float]]:
    config = ROOT / "logs_rl" / WAVE / "train" / source / "resolved_config.yaml"
    robot = yaml.load(config.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)["robot"]
    names = robot["dof_names"]
    lower = robot["dof_pos_lower_limit_list"]
    upper = robot["dof_pos_upper_limit_list"]
    if not (len(names) == len(lower) == len(upper)):
        raise RuntimeError(f"{config}: dof name/limit list lengths disagree")
    limits = {}
    for joint in JOINTS:
        index = names.index(joint)
        limits[joint] = (float(lower[index]), float(upper[index]))
    return limits


def overshoot(target: float, bounds: tuple[float, float]) -> float:
    low, high = bounds
    return max(0.0, target - high) + max(0.0, low - target)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise RuntimeError("percentile of an empty sample")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(fraction * (len(ordered) - 1) + 0.5))
    return ordered[index]


def distribution(values: list[float]) -> dict:
    return {
        "n": len(values),
        "median": statistics.median(values),
        "p90": percentile(values, 0.9),
        "max": max(values),
        "min": min(values),
        "mean": statistics.fmean(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path(__file__).parent / "P0_ENTRY_TRAJECTORY.csv")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "P2_OVERSHOOT_REFERENCE.json")
    args = parser.parse_args()

    with args.csv.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    limits = {source: hard_limits(source) for source in ("P_S1", "P_S2")}

    groups: dict[tuple[str, str, str], dict[str, list[float]]] = {}
    for row in rows:
        source, side = row["source"], row["side"]
        if source not in limits or row.get("arm_j3_target") in (None, ""):
            continue
        per_joint = {
            joint: overshoot(float(row[f"{joint}_target"]), limits[source][joint])
            for joint in JOINTS
        }
        # `limits_dof_pos` raw is the same six joints' actual-q violation of the
        # 0.95-narrowed interval (door_open_a2_base.py:11982-11998); carrying it
        # here lets a runtime smoke compare the two terms' logged
        # `Episode/rew_*` values as a ratio, which cancels the unknown
        # episode-elapsed normalisation in staged_task_base.py:722-725.
        limits_raw = sum(float(row[f"{joint}_penalty095_violation_rad"]) for joint in JOINTS)
        scopes = [(source, side, "all_landmarks")]
        if row["landmark"] in E5_LANDMARKS:
            scopes.append((source, side, "e5_window"))
        for scope in scopes:
            bucket = groups.setdefault(
                scope, {joint: [] for joint in JOINTS} | {"sum": [], "limits_dof_pos_raw": []}
            )
            for joint, value in per_joint.items():
                bucket[joint].append(value)
            bucket["sum"].append(sum(per_joint.values()))
            bucket["limits_dof_pos_raw"].append(limits_raw)

    payload = {
        "schema": "pull_v7_p2_overshoot_reference_v1",
        "csv": str(args.csv.relative_to(ROOT)),
        "limit_source": {
            source: str((ROOT / "logs_rl" / WAVE / "train" / source / "resolved_config.yaml").relative_to(ROOT))
            for source in limits
        },
        "hard_limits": {source: {j: list(b) for j, b in value.items()} for source, value in limits.items()},
        "definition": "raw = sum_j max(0, target_j - upper_j) + max(0, lower_j - target_j), radians",
        "groups": [
            {
                "source": source,
                "side": side,
                "scope": scope,
                "landmark_rows": len(bucket["sum"]),
                "per_joint": {joint: distribution(bucket[joint]) for joint in JOINTS},
                "raw_sum": distribution(bucket["sum"]),
                "limits_dof_pos_raw": distribution(bucket["limits_dof_pos_raw"]),
                "expected_episode_rew_ratio_d2_over_limits": (
                    1.0 * statistics.median(bucket["sum"])
                ) / (5.0 * statistics.median(bucket["limits_dof_pos_raw"])),
            }
            for (source, side, scope), bucket in sorted(groups.items())
        ],
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    header = (
        f"{'source/side/scope':28s} {'rows':>5s} {'sum med':>9s} {'sum p90':>9s} {'sum max':>9s} "
        f"{'j3 med':>8s} {'j5 med':>8s} {'lim med':>8s} {'ratio':>7s}"
    )
    print(header, flush=True)
    for group in payload["groups"]:
        print(
            f"{group['source'] + '/' + group['side'] + '/' + group['scope']:28s} "
            f"{group['landmark_rows']:5d} "
            f"{group['raw_sum']['median']:9.4f} {group['raw_sum']['p90']:9.4f} {group['raw_sum']['max']:9.4f} "
            f"{group['per_joint']['arm_j3']['median']:8.4f} {group['per_joint']['arm_j5']['median']:8.4f} "
            f"{group['limits_dof_pos_raw']['median']:8.4f} "
            f"{group['expected_episode_rew_ratio_d2_over_limits']:7.3f}",
            flush=True,
        )
    print(f"wrote {args.output.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
