#!/usr/bin/env python3
"""Mandatory true-100/45 native-position standing-vitals gate for r4."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import mujoco
import numpy as np
import torch

from gr00t.rl.sim2sim.cli.run_standing_vitals_gate import _a2_body_observation, _foot_forces
from gr00t.rl.sim2sim.doors.mjcf_builder_v2 import MjcfDoorBuilderV2
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_transform import A2ActionTransform
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.native_position_r4 import (
    NameResolvedPositionActuatorMapR4,
    NativePositionSceneR4,
    ResolvedNativePositionContractR4,
)
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import FOOT_GEOM_NAMES, PairedSceneBuilderV2
from gr00t.rl.sim2sim.mujoco.sensor_clock import SensorClock
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


def _roll_pitch(data: mujoco.MjData, trunk_id: int) -> tuple[float, float]:
    rotation = data.xmat[trunk_id].reshape(3, 3)
    return (
        math.atan2(rotation[2, 1], rotation[2, 2]),
        math.atan2(-rotation[2, 0], math.hypot(rotation[2, 1], rotation[2, 2])),
    )


class _NativeEvidence:
    def __init__(
        self,
        model: mujoco.MjModel,
        mapping: NameResolvedPositionActuatorMapR4,
        effort_limit: np.ndarray,
    ):
        self.model = model
        self.mapping = mapping
        self.effort_limit = effort_limit
        self.writes = 0
        self.max_target_write_error = 0.0
        self.max_effort_over_limit = 0.0
        self.max_generalized_force_error = 0.0
        self.max_abs_qacc = 0.0

    def apply(self, data: mujoco.MjData, target: np.ndarray) -> None:
        self.mapping.write_robot_position_target(data, target)
        self.writes += 1
        self.max_target_write_error = max(
            self.max_target_write_error,
            float(np.max(np.abs(data.ctrl[self.mapping.robot_actuator_ids] - target))),
        )
        mujoco.mj_forward(self.model, data)
        effort = self.mapping.robot_actuator_force(data)
        self.max_effort_over_limit = max(
            self.max_effort_over_limit,
            float(np.max(np.maximum(np.abs(effort) - self.effort_limit, 0.0))),
        )
        self.max_generalized_force_error = max(
            self.max_generalized_force_error,
            float(np.max(np.abs(self.mapping.robot_generalized_force(data) - effort))),
        )
        self.max_abs_qacc = max(self.max_abs_qacc, float(np.max(np.abs(data.qacc))))

    def receipt(self) -> dict[str, Any]:
        return {
            "position_target_writes": self.writes,
            "max_target_write_error": self.max_target_write_error,
            "max_effort_over_limit": self.max_effort_over_limit,
            "max_generalized_force_error": self.max_generalized_force_error,
            "max_abs_qacc": self.max_abs_qacc,
        }


def _summary(
    heights: list[float],
    vertical_velocities: list[float],
    tilts: list[tuple[float, float]],
    forces: list[dict[str, float]],
    tail: int,
) -> dict[str, Any]:
    tail_heights = heights[-tail:]
    return {
        "final_base_height_m": heights[-1],
        "tail_base_height_span_m": max(tail_heights) - min(tail_heights),
        "final_vertical_velocity_mps": vertical_velocities[-1],
        "tail_max_abs_roll_or_pitch_rad": max(
            max(abs(roll), abs(pitch)) for roll, pitch in tilts[-tail:]
        ),
        "tail_steps_with_nonzero_foot_force": sum(
            sum(row.values()) > 0.0 for row in forces[-tail:]
        ),
        "final_foot_normal_force_n": forces[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", type=Path, required=True)
    parser.add_argument("--door-instance", type=Path, required=True)
    parser.add_argument("--resolved-config", type=Path, required=True)
    parser.add_argument("--a2-base-policy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    contract = ResolvedNativePositionContractR4.from_config(args.resolved_config)
    door_xml = output / "door.xml"
    MjcfDoorBuilderV2(
        DoorInstanceSpec.from_path(args.door_instance.resolve(strict=True))
    ).write(door_xml, output / "door_build_report_v2.json")
    source_scene = output / "external_pd_source_scene.xml"
    PairedSceneBuilderV2(
        args.robot.resolve(strict=True),
        door_xml,
        armature_by_joint=contract.values_by_joint(contract.armature),
    ).write(source_scene, output / "external_pd_source_scene_build_report_v2.json")
    scene = output / "standing_vitals_scene_r4.xml"
    NativePositionSceneR4(source_scene, contract).write(
        scene, output / "native_position_scene_build_report_r4.json"
    )
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    mapping = NameResolvedPositionActuatorMapR4.from_model(model, contract.joint_names)
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    trunk = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    foot_ids = {
        name: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        for name in FOOT_GEOM_NAMES
    }
    effort_limit = np.asarray(contract.effort_limit)
    default = np.asarray(contract.default_position)

    mujoco.mj_resetDataKeyframe(model, data, home)
    mujoco.mj_forward(model, data)
    passive_evidence = _NativeEvidence(model, mapping, effort_limit)
    passive_heights, passive_vz, passive_tilts, passive_forces = [], [], [], []
    for _ in range(400):
        passive_evidence.apply(data, default)
        mujoco.mj_step(model, data)
        passive_heights.append(float(data.qpos[2]))
        passive_vz.append(float(data.qvel[2]))
        passive_tilts.append(_roll_pitch(data, trunk))
        passive_forces.append(_foot_forces(model, data, floor, foot_ids))
    passive = _summary(passive_heights, passive_vz, passive_tilts, passive_forces, 100)
    passive["mode"] = "POLICY_FREE_NATIVE_POSITION_DEFAULT_TARGET_LANDING"
    passive["duration_s"] = 2.0
    passive["result"] = "PASS" if (
        0.45 <= passive["final_base_height_m"] <= 0.65
        and passive["tail_base_height_span_m"] <= 0.02
        and abs(passive["final_vertical_velocity_mps"]) <= 0.05
        and passive["tail_steps_with_nonzero_foot_force"] > 0
    ) else "FAIL"

    mujoco.mj_resetDataKeyframe(model, data, home)
    mujoco.mj_forward(model, data)
    base_policy = torch.jit.load(str(args.a2_base_policy.resolve(strict=True)), map_location="cpu").eval()
    robot_contract = resolved_a2_piper_contract()
    joint_map = A2PiperJointMap.from_sim_joint_names(contract.joint_names, device="cpu")
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    transform = A2ActionTransform(joint_map, action_scale=robot_contract.action_scale)
    gait = SensorClock(batch_size=1, physics_dt=0.005, device="cpu", dtype=torch.float32)
    default32 = torch.from_numpy(default.copy()).float().unsqueeze(0)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    zero_command = torch.zeros((1, 5), dtype=torch.float32)
    position_target = default.copy()
    frozen_evidence = _NativeEvidence(model, mapping, effort_limit)
    frozen_heights, frozen_vz, frozen_tilts, frozen_forces = [], [], [], []
    for physics_step in range(1000):
        if physics_step % 4 == 0:
            _, gravity = _a2_body_observation(model, data, trunk)
            roll_pitch = _roll_pitch(data, trunk)
            qpos = data.qpos[mapping.robot_qpos_addresses].copy()
            qvel = data.qvel[mapping.robot_qvel_addresses].copy()
            frame = frame_builder.build(
                projected_gravity=torch.from_numpy(gravity).float().unsqueeze(0),
                dof_pos=torch.from_numpy(qpos).float().unsqueeze(0),
                default_dof_pos=default32,
                dof_vel=torch.from_numpy(qvel).float().unsqueeze(0),
                previous_leg_action=previous_leg,
                physical_base_command=zero_command,
                base_roll_pitch=torch.tensor([roll_pitch], dtype=torch.float32),
                gait_clock=gait.signal(),
            )
            with torch.inference_mode():
                previous_leg = base_policy(history.append(frame))
            position_target = transform.compose(
                high_level_action=torch.zeros((1, 12), dtype=torch.float32),
                policy_leg_action=previous_leg,
                default_dof_pos=default32,
            ).position_target.squeeze(0).numpy()
        frozen_evidence.apply(data, position_target)
        mujoco.mj_step(model, data)
        gait.advance(zero_command[:, :3])
        frozen_heights.append(float(data.qpos[2]))
        frozen_vz.append(float(data.qvel[2]))
        frozen_tilts.append(_roll_pitch(data, trunk))
        frozen_forces.append(_foot_forces(model, data, floor, foot_ids))
    frozen = _summary(frozen_heights, frozen_vz, frozen_tilts, frozen_forces, 200)
    frozen["mode"] = "FROZEN_A2_BASE_ZERO_COMMAND_NATIVE_POSITION"
    frozen["duration_s"] = 5.0
    frozen["result"] = "PASS" if (
        0.44 <= frozen["final_base_height_m"] <= 0.66
        and frozen["tail_base_height_span_m"] <= 0.03
        and frozen["tail_max_abs_roll_or_pitch_rad"] <= 0.35
        and frozen["tail_steps_with_nonzero_foot_force"] > 0
    ) else "FAIL"

    passive_audit = passive_evidence.receipt()
    frozen_audit = frozen_evidence.receipt()
    mapping_result = "PASS" if all(
        audit[key] <= 1.0e-9
        for audit in (passive_audit, frozen_audit)
        for key in ("max_target_write_error", "max_effort_over_limit", "max_generalized_force_error")
    ) else "FAIL"
    result = "PASS" if passive["result"] == frozen["result"] == mapping_result == "PASS" else "FAIL"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "schema": "doordog.sim2sim.standing_vitals_gate.r4.v1",
        "rule": "INSTRUMENT_VITALS_BEFORE_MEASUREMENT_INTERPRETATION",
        "result": result,
        "campaign_authorization": "AUTHORIZED" if result == "PASS" else "DENIED",
        "backend": "mujoco_cpu",
        "physics_dt_s": float(model.opt.timestep),
        "integrator": "implicitfast",
        "control_mode": "MUJOCO_NATIVE_POSITION_TRUE_100_45",
        "passive_landing": passive,
        "frozen_a2_standing": frozen,
        "actuator_mapping_audit": {
            "result": mapping_result,
            "mapping": mapping.receipt(model),
            "passive_trace": passive_audit,
            "frozen_a2_trace": frozen_audit,
            "effort_limit_by_joint": contract.values_by_joint(contract.effort_limit),
        },
        "foot_floor_contact_pair": {
            "floor_geom_id": floor,
            "foot_geom_ids": foot_ids,
            "all_feet_nonzero_in_passive_tail": all(
                any(row[name] > 0.0 for row in passive_forces[-100:]) for name in FOOT_GEOM_NAMES
            ),
        },
        "d5_authorized_deviation": {
            "external_pd_per_step_clip": "REMOVED",
            "replacement": "native position actuator forcerange inside implicitfast solve",
            "robot_scope": "all 20 joints",
            "true_arm_gripper_effort_surface": "100/45",
        },
        "producer_identity": {
            "git_commit_before_phase_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/run_standing_vitals_gate_r4.py",
        },
    }
    (output / "standing_vitals_gate_r4_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": result, "passive": passive, "frozen": frozen}, sort_keys=True))
    if result != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
