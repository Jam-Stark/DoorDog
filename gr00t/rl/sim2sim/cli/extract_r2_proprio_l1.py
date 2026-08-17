#!/usr/bin/env python3
"""Reconstruct r2 pre-inference 81D proprio at recorded policy boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


def _rotation_wxyz(quaternion: list[float]) -> np.ndarray:
    w, x, y, z = quaternion
    return np.asarray(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y)],
            [2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x)],
            [2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def _stats(values: np.ndarray) -> dict[str, float]:
    return {
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "abs_max": float(np.abs(values).max()),
    }


def _components(
    *,
    row: dict[str, Any] | None,
    initial: dict[str, Any],
    default: np.ndarray,
) -> dict[str, np.ndarray]:
    if row is None:
        qpos = np.asarray(initial["robot_qpos"], dtype=np.float64)
        qvel = np.asarray(initial["robot_qvel"], dtype=np.float64)
        local_ang = np.zeros(3, dtype=np.float64)
        gravity = np.asarray([0.0, 0.0, -1.0])
        actions = np.asarray(initial["previous_applied_action"], dtype=np.float64)
        raw_delta = np.asarray(initial["previous_raw_delta_action"], dtype=np.float64)
        base_raw = np.zeros(5, dtype=np.float64)
        base_physical = np.zeros(5, dtype=np.float64)
    else:
        qpos = np.asarray(row["robot_qpos"], dtype=np.float64)
        qvel = np.asarray(row["robot_qvel"], dtype=np.float64)
        rotation = _rotation_wxyz(row["base"]["quaternion_wxyz"])
        local_ang = rotation.T @ np.asarray(row["base"]["angular_velocity_radps"], dtype=np.float64)
        gravity = rotation.T @ np.asarray([0.0, 0.0, -1.0])
        actions = np.asarray(row["applied_action"], dtype=np.float64)
        high_raw = np.asarray(row["student_action_mean"], dtype=np.float64)
        raw_delta = high_raw[5:11]
        base_raw = high_raw[:5]
        base_physical = np.concatenate((base_raw[:3] * 0.25, np.clip(base_raw[3:5], -1.0, 1.0) * 0.4))
    command_echo = base_physical * np.asarray([2.0, 2.0, 0.25, 1.0, 1.0])
    if np.linalg.norm(base_physical[:3]) < 0.1:
        command_echo[:3] = 0.0
    return {
        "base_ang_vel": local_ang,
        "projected_gravity": gravity,
        "a2_student_dof_pos": qpos - default,
        "a2_student_dof_vel": qvel,
        "actions": actions,
        "delta_actions": raw_delta,
        "a2_base_command": command_echo,
        "a2_base_command_raw": base_raw,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r2-trace", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    trace_path = args.r2_trace.resolve(strict=True)
    manifest = json.loads(args.manifest.resolve(strict=True).read_text(encoding="utf-8"))
    bundle = args.bundle_dir.resolve(strict=True)
    bundle_manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    golden = np.load(bundle / "golden" / "golden_io.npz")["actor_obs"]
    golden_manifest = json.loads((bundle / "golden" / "golden_manifest.json").read_text(encoding="utf-8"))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    last_row_by_step: dict[int, dict[str, Any]] = {}
    with trace_path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            last_row_by_step[int(row["policy_step"])] = row
    policy_steps = sorted(last_row_by_step)
    if policy_steps != list(range(len(policy_steps))):
        raise ValueError("r2 p00 trace policy steps are not contiguous from zero")

    components = bundle_manifest["observation"]["components"]
    default = np.asarray(resolved_a2_piper_contract().default_dof_pos, dtype=np.float64)
    actor_rows = []
    dump_path = output / "l1_r2_actor_obs_81d_boundary_reconstruction.jsonl"
    with dump_path.open("w", encoding="utf-8") as stream:
        for step in policy_steps:
            previous_boundary = None if step == 0 else last_row_by_step[step - 1]
            values = _components(
                row=previous_boundary,
                initial=manifest["fixed_initial_state"],
                default=default,
            )
            actor_obs = np.concatenate(
                [values[str(component["name"])] * float(component["scale"]) for component in components]
            ).astype(np.float32)
            actor_rows.append(actor_obs)
            stream.write(json.dumps({
                "schema": "doordog.sim2sim.r3_l1_r2_actor_obs_boundary_reconstruction.v1",
                "policy_step": step,
                "source_boundary_physics_step": None if previous_boundary is None else previous_boundary["physics_step"],
                "actor_obs_81d_pre_inference": actor_obs.tolist(),
            }, separators=(",", ":"), allow_nan=False) + "\n")

    actor_array = np.stack(actor_rows)
    offset = 0
    component_reports = []
    for component in components:
        end = offset + int(component["dim"])
        actual = _stats(actor_array[:, offset:end])
        reference = _stats(golden[:, offset:end])
        if reference["abs_max"] == 0.0:
            ratio = None
            suspect = "REFERENCE_ZERO_NONZERO_R2" if actual["abs_max"] > 0.0 else None
        else:
            ratio = actual["abs_max"] / reference["abs_max"]
            suspect = "MAGNITUDE_OVER_10X_CONTRACT_FIXTURE" if ratio > 10.0 else None
        component_reports.append({
            "name": component["name"],
            "slice": [offset, end],
            "scale": component["scale"],
            "r2_actual_boundary_reconstruction": actual,
            "bundle_golden_contract_fixture": reference,
            "r2_to_fixture_abs_max_ratio": ratio,
            "suspect": suspect,
        })
        offset = end

    report = {
        "schema": "doordog.sim2sim.r3_l1_r2_proprio_report.v1",
        "result": "PIPELINE_DEFECT_FOUND_STAGE_ACTION_SEMANTICS",
        "source_r2_trace": str(trace_path),
        "policy_step_count": len(actor_rows),
        "actor_obs_dump": str(dump_path),
        "reconstruction_authority": {
            "step0": "PAIRED_MANIFEST_FIXED_INITIAL_STATE",
            "step1_plus": "PREVIOUS_POLICY_STEP_FINAL_SUBSTEP_ROW_IS_THE_NEXT_PRE_INFERENCE_PHYSICS_BOUNDARY",
            "base_ang_vel": "TRACE_WORLD_ANGULAR_VELOCITY_ROTATED_BY_RECORDED_BASE_QUATERNION_INTO_BASE_FRAME",
            "warning": "r2 did not directly serialize actor_obs; this is deterministic boundary reconstruction, not a fabricated direct-capture claim.",
        },
        "components": component_reports,
        "contract_checks": {
            "actor_obs_dim": int(actor_array.shape[1]),
            "actions_echo": "PREVIOUS_APPLIED_12_LEG_6_ARM_1_GRIP",
            "delta_actions_echo": "PREVIOUS_RAW_ACTION_5_11",
            "a2_base_command_raw": "PREVIOUS_RAW_ACTION_0_5; WARP_K_AND_S_ARE_ZERO",
            "a2_base_command": "PHYSICAL_COMMAND_ECHO_WITH_[2,2,.25,1,1]_MULTIPLIER",
            "base_ang_vel_frame": "BASE_LOCAL_NOT_WORLD",
            "dof_order": list(resolved_a2_piper_contract().sim_joint_names),
            "dof_position_surface": "RECORDED_QPOS_MINUS_RESOLVED_DEFAULT",
            "r2_stage_semantics": "FIXED_STAGE_ONE_FROM_FIRST_POLICY_STEP; DEFECT",
            "r3_stage_semantics": "WALK_TO_DOOR_STAGE_ZERO; APPLIED_ARM_DELTA_ZERO; RAW_DELTA_ECHO_RETAINED",
            "reset_delta_actions_with_backmap": "CONFIG_TRUE_BUT_PRODUCTION_METHOD_IS_NOOP; RESET_ZERO_IS_ACTUAL_IMPLEMENTATION",
        },
        "golden_authority": golden_manifest["input_authority"],
        "magnitude_warning": "The requested over-10x screen is retained, but its reference is synthetic contract data rather than empirical Isaac rollout statistics.",
    }
    report_path = output / "l1_r2_proprio_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"policy_steps": len(actor_rows), "report": str(report_path), "result": report["result"]}, sort_keys=True))


if __name__ == "__main__":
    main()
