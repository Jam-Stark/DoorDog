#!/usr/bin/env python3
"""Reduce matched G1 target-quaternion dumps for pull-v26.8."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import yaml

from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2_PULL_HARD_GATE_EVENT_PREDECESSORS,
    validate_a2_pull_episode,
)


SCHEMA = "a2_piper_pull_v26_8_g1_wiring_v1"
EPISODES = 64
SIDE_SIGNS = {"left": 1.0, "right": -1.0}
ANGLE_DEG = 180.0
ANGLE_TOL_DEG = 0.05


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path, *, distribution: str, enabled: bool) -> dict[int, dict]:
    require(path.is_file(), f"missing G1 metrics: {path}")
    runtime = yaml.load((path.parent / ".hydra/runtime_config.yaml").read_text(encoding="utf-8"), Loader=yaml.UnsafeLoader)
    env = runtime["env"]["config"]
    require(env["a2_pull_threshold_mode"] == "hard_gate", f"{path}: pull event predecessor contract")
    require(env["a2_door_open_lr_distribution"] == distribution, f"{path}: distribution")
    require(env["a2_v26_6_side_mirrored_handle_offset_enabled"] is enabled, f"{path}: mirror switch")
    require(env["enable_staged_reset"] is False and runtime["num_envs"] == EPISODES, f"{path}: natural exact64")
    metrics = json.loads(path.read_text(encoding="utf-8"))
    terminal = metrics.get("episode_terminal_diagnostics")
    require(isinstance(terminal, list) and len(terminal) == EPISODES, f"{path}: exact64 terminal diagnostics required")
    rows: dict[int, dict] = {}
    for row in terminal:
        require(isinstance(row, dict), f"{path}: terminal row must be object")
        env_id = row.get("env_id")
        quat = row.get("target_quat_source_handle")
        side = row.get("door_handle_side")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES and env_id not in rows, f"{path}: invalid env id")
        require(side in SIDE_SIGNS and float(row.get("door_open_lr")) == SIDE_SIGNS[side], f"{path}: side provenance env{env_id}")
        require(isinstance(quat, list) and len(quat) == 4 and all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in quat), f"{path}: target_quat_source_handle env{env_id}")
        episode = row.get("pull_v0_episode")
        require(isinstance(episode, dict), f"{path}: missing pull_v0_episode env{env_id}")
        validate_a2_pull_episode(episode, event_predecessors=A2_PULL_HARD_GATE_EVENT_PREDECESSORS)
        rows[env_id] = row
    require(set(rows) == set(range(EPISODES)), f"{path}: terminal exact64 coverage")
    return rows


def angle_degrees(before: list[float], after: list[float]) -> float:
    before_norm = math.sqrt(sum(float(value) ** 2 for value in before))
    after_norm = math.sqrt(sum(float(value) ** 2 for value in after))
    require(before_norm > 0.0 and after_norm > 0.0, "zero-norm target quaternion")
    dot = abs(sum(float(a) * float(b) for a, b in zip(before, after, strict=True)) / (before_norm * after_norm))
    require(0.0 <= dot <= 1.0, f"invalid normalized target-quaternion dot product: {dot}")
    return math.degrees(2.0 * math.acos(dot))


def matched(old: dict[int, dict], fixed: dict[int, dict], *, expected_side: str | None, label: str) -> tuple[list[float], bool]:
    angles: list[float] = []
    bit_identical = True
    for env_id in range(EPISODES):
        before, after = old[env_id], fixed[env_id]
        require(before["door_handle_side"] == after["door_handle_side"], f"{label}: side changed env{env_id}")
        side = before["door_handle_side"]
        if expected_side is not None:
            require(side == expected_side, f"{label}: requires all-{expected_side} env{env_id}")
        if side == "left":
            angles.append(angle_degrees(before["target_quat_source_handle"], after["target_quat_source_handle"]))
        else:
            bit_identical &= before["target_quat_source_handle"] == after["target_quat_source_handle"]
    return angles, bit_identical


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--fixed", type=Path, required=True)
    parser.add_argument("--right-old", type=Path, required=True)
    parser.add_argument("--right-fixed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite G1 output: {args.output}")
    old = load(args.old, distribution="bilateral", enabled=False)
    fixed = load(args.fixed, distribution="bilateral", enabled=True)
    right_old = load(args.right_old, distribution="right", enabled=False)
    right_fixed = load(args.right_fixed, distribution="right", enabled=True)
    bilateral_angles, bilateral_right_identical = matched(old, fixed, expected_side=None, label="bilateral")
    right_angles, right_noop = matched(right_old, right_fixed, expected_side="right", label="all-right")
    failures: list[str] = []
    if len(bilateral_angles) != EPISODES // 2:
        failures.append(f"BILATERAL_LEFT_COUNT_NOT_32:{len(bilateral_angles)}")
    if any(abs(value - ANGLE_DEG) > ANGLE_TOL_DEG for value in bilateral_angles):
        failures.append("LEFT_TARGET_QUAT_NOT_180_PLUS_MINUS_0_05")
    if not bilateral_right_identical:
        failures.append("BILATERAL_RIGHT_TARGET_QUAT_NOT_BIT_IDENTICAL")
    if right_angles:
        failures.append("ALL_RIGHT_CONTAINS_LEFT")
    if not right_noop:
        failures.append("ALL_RIGHT_TARGET_QUAT_NOT_BIT_IDENTICAL")
    status = "G1_PASS" if not failures else "PULL_V26_8_WIRING_NOT_CONFIRMED"
    payload = {
        "schema": SCHEMA,
        "status": status,
        "inputs": {"old": str(args.old), "fixed": str(args.fixed), "right_old": str(args.right_old), "right_fixed": str(args.right_fixed)},
        "contract": {"episodes": EPISODES, "left_relative_rotation_degrees": ANGLE_DEG, "left_tolerance_degrees": ANGLE_TOL_DEG, "right": "bit-identical", "integrity": "pull_v0_episode validated"},
        "bilateral_left_relative_rotation_degrees": {"count": len(bilateral_angles), "min": min(bilateral_angles) if bilateral_angles else None, "max": max(bilateral_angles) if bilateral_angles else None, "values": bilateral_angles},
        "bilateral_right_target_quat_bit_identical": bilateral_right_identical,
        "all_right_target_quat_bit_identical": right_noop,
        "integrity_violations": 0,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(args.output), "failures": failures}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
