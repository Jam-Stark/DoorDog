#!/usr/bin/env python3
"""Reduce the G1 matched target-quaternion runtime dumps."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

EPISODES = 64
LEFT_SIGN = 1.0
RIGHT_SIGN = -1.0
ANGLE_DEG = 180.0
ANGLE_TOL_DEG = 0.5


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def rows(path: Path) -> dict[int, dict]:
    require(path.is_file(), f"missing G1 metrics: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    terminal = value.get("episode_terminal_diagnostics")
    require(isinstance(terminal, list) and len(terminal) == EPISODES, f"{path}: requires exact64 terminal diagnostics")
    result: dict[int, dict] = {}
    for row in terminal:
        require(isinstance(row, dict), f"{path}: terminal row must be an object")
        env_id = row.get("env_id")
        quat = row.get("target_quat_source_handle")
        require(isinstance(env_id, int) and env_id not in result and 0 <= env_id < EPISODES, f"{path}: invalid env id")
        require(isinstance(quat, list) and len(quat) == 4 and all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in quat), f"{path}: invalid target_quat_source_handle env{env_id}")
        require(row.get("door_open_lr") in (LEFT_SIGN, RIGHT_SIGN), f"{path}: invalid door side env{env_id}")
        result[env_id] = row
    require(set(result) == set(range(EPISODES)), f"{path}: terminal env coverage is not exact64")
    return result


def relative_angle_degrees(old: list[float], fixed: list[float]) -> float:
    old_norm = math.sqrt(sum(float(x) * float(x) for x in old))
    fixed_norm = math.sqrt(sum(float(x) * float(x) for x in fixed))
    require(old_norm > 0.0 and fixed_norm > 0.0, "G1 target quaternion norm is zero")
    dot = abs(sum(float(a) * float(b) for a, b in zip(old, fixed, strict=True)) / (old_norm * fixed_norm))
    return math.degrees(2.0 * math.acos(min(1.0, dot)))


def integrity(row: dict, label: str) -> int:
    total = 0
    for key in ("v26_2", "v26_3"):
        value = row.get(key)
        require(isinstance(value, dict) and isinstance(value.get("integrity_violations"), (int, float)), f"{label}: missing {key}.integrity_violations")
        total += int(value["integrity_violations"])
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--fixed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite G1 result: {args.output}")
    old, fixed = rows(args.old), rows(args.fixed)
    failures: list[str] = []
    left_angles: list[float] = []
    right_bit_identical = True
    integrity_violations = 0
    for env_id in range(EPISODES):
        before, after = old[env_id], fixed[env_id]
        if before["door_open_lr"] != after["door_open_lr"]:
            failures.append(f"SIDE_ASSIGNMENT_CHANGED:env{env_id}")
            continue
        integrity_violations += integrity(before, f"old env{env_id}") + integrity(after, f"fixed env{env_id}")
        if before["door_open_lr"] == LEFT_SIGN:
            left_angles.append(relative_angle_degrees(before["target_quat_source_handle"], after["target_quat_source_handle"]))
        else:
            right_bit_identical &= before["target_quat_source_handle"] == after["target_quat_source_handle"]
    if len(left_angles) != EPISODES // 2:
        failures.append(f"LEFT_COUNT_NOT_32:{len(left_angles)}")
    if not right_bit_identical:
        failures.append("RIGHT_TARGET_QUAT_NOT_BIT_IDENTICAL")
    if any(abs(angle - ANGLE_DEG) > ANGLE_TOL_DEG for angle in left_angles):
        failures.append("LEFT_TARGET_QUAT_NOT_180_PLUS_MINUS_0_5")
    if integrity_violations != 0:
        failures.append(f"INTEGRITY_VIOLATIONS:{integrity_violations}")
    status = "G1_PASS" if not failures else "V26_7_WIRING_NOT_CONFIRMED"
    payload = {
        "schema": "a2_piper_base_v26_7_g1_wiring_v1",
        "status": status,
        "old_metrics": str(args.old), "fixed_metrics": str(args.fixed),
        "contract": {"num_envs": EPISODES, "max_train_batches": 5, "left_relative_rotation_degrees": ANGLE_DEG, "tolerance_degrees": ANGLE_TOL_DEG, "right": "bit-identical"},
        "left_relative_rotation_degrees": {"count": len(left_angles), "min": min(left_angles) if left_angles else None, "max": max(left_angles) if left_angles else None, "values": left_angles},
        "right_target_quat_bit_identical": right_bit_identical,
        "integrity_violations": integrity_violations,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(args.output), "failures": failures}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
