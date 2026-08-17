#!/usr/bin/env python3
"""Run the mandatory pre-campaign standing-vitals gate on MuJoCo CPU."""

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
import yaml

from gr00t.rl.sim2sim.doors.mjcf_builder_v2 import MjcfDoorBuilderV2
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_transform import A2ActionTransform
from gr00t.rl.sim2sim.mujoco.actuator_map_v2 import NameResolvedActuatorMapV2
from gr00t.rl.sim2sim.mujoco.external_pd import ExternalPdController
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import FOOT_GEOM_NAMES, PairedSceneBuilderV2
from gr00t.rl.sim2sim.mujoco.sensor_clock import SensorClock
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


PHYSICS_DT = 0.005
HEIGHT_REFERENCE_M = 0.55
HEIGHT_TOLERANCE_M = 0.10
CONTACT_SOLVER_MARGIN_M = 0.01


def _resolved_armature(config_path: Path) -> dict[str, float]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    robot = config["robot"]
    return dict(zip(robot["dof_names"], robot["dof_armature_list"], strict=True))


def _roll_pitch(model: mujoco.MjModel, data: mujoco.MjData, trunk_id: int) -> tuple[float, float]:
    rotation = data.xmat[trunk_id].reshape(3, 3)
    return (
        math.atan2(rotation[2, 1], rotation[2, 2]),
        math.atan2(-rotation[2, 0], math.hypot(rotation[2, 1], rotation[2, 2])),
    )


def _a2_body_observation(
    model: mujoco.MjModel, data: mujoco.MjData, trunk_id: int
) -> tuple[np.ndarray, np.ndarray]:
    velocity = np.zeros(6, dtype=np.float64)
    mujoco.mj_objectVelocity(
        model, data, mujoco.mjtObj.mjOBJ_BODY, trunk_id, velocity, 1
    )
    rotation = data.xmat[trunk_id].reshape(3, 3)
    projected_gravity = rotation.T @ np.array([0.0, 0.0, -1.0])
    return velocity[:3], projected_gravity


def _foot_forces(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    floor_id: int,
    foot_ids: dict[str, int],
) -> dict[str, float]:
    forces = {name: 0.0 for name in foot_ids}
    id_to_name = {geom_id: name for name, geom_id in foot_ids.items()}
    for contact_index in range(data.ncon):
        contact = data.contact[contact_index]
        if contact.geom1 == floor_id and contact.geom2 in id_to_name:
            foot_name = id_to_name[contact.geom2]
        elif contact.geom2 == floor_id and contact.geom1 in id_to_name:
            foot_name = id_to_name[contact.geom1]
        else:
            continue
        wrench = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, contact_index, wrench)
        forces[foot_name] += max(0.0, float(wrench[0]))
    return forces


class _Evidence:
    def __init__(
        self,
        model: mujoco.MjModel,
        actuator_map: NameResolvedActuatorMapV2,
        torque_limit: np.ndarray,
    ):
        self.model = model
        self.actuator_map = actuator_map
        self.torque_limit = torque_limit
        self.clip_invocations = 0
        self.saturation_rows = 0
        self.saturated_joint_steps = 0
        self.max_ctrl_write_error = 0.0
        self.max_actuator_force_error = 0.0
        self.max_generalized_force_error = 0.0

    def apply(
        self,
        data: mujoco.MjData,
        clipped_effort: np.ndarray,
        unclipped_effort: np.ndarray,
    ) -> None:
        saturated = np.abs(unclipped_effort) > self.torque_limit
        self.clip_invocations += 1
        self.saturation_rows += int(saturated.any())
        self.saturated_joint_steps += int(saturated.sum())
        self.actuator_map.write_robot_ctrl(data, clipped_effort)
        self.max_ctrl_write_error = max(
            self.max_ctrl_write_error,
            float(np.max(np.abs(data.ctrl[self.actuator_map.robot_actuator_ids] - clipped_effort))),
        )
        mujoco.mj_forward(self.model, data)
        self.max_actuator_force_error = max(
            self.max_actuator_force_error,
            float(np.max(np.abs(self.actuator_map.robot_actuator_force(data) - clipped_effort))),
        )
        self.max_generalized_force_error = max(
            self.max_generalized_force_error,
            float(np.max(np.abs(self.actuator_map.robot_generalized_force(data) - clipped_effort))),
        )

    def receipt(self) -> dict[str, Any]:
        return {
            "clip_invocations": self.clip_invocations,
            "rows_with_any_saturation": self.saturation_rows,
            "saturated_joint_steps": self.saturated_joint_steps,
            "clip_invocation_is_not_saturation": True,
            "max_ctrl_write_error": self.max_ctrl_write_error,
            "max_actuator_force_error": self.max_actuator_force_error,
            "max_generalized_force_error": self.max_generalized_force_error,
        }


def _pd_effort(
    pd: ExternalPdController,
    position_target: torch.Tensor,
    position: np.ndarray,
    velocity: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    position_tensor = torch.from_numpy(position.copy()).to(torch.float64).unsqueeze(0)
    velocity_tensor = torch.from_numpy(velocity.copy()).to(torch.float64).unsqueeze(0)
    unclipped = (
        pd.stiffness[None, :] * (position_target - position_tensor)
        - pd.damping[None, :] * velocity_tensor
    )
    clipped = pd.compute(
        position_target=position_target,
        position=position_tensor,
        velocity=velocity_tensor,
    )
    return clipped.squeeze(0).numpy(), unclipped.squeeze(0).numpy()


def _summarize_vitals(
    *,
    heights: list[float],
    vertical_velocities: list[float],
    tilts: list[tuple[float, float]],
    foot_forces: list[dict[str, float]],
    tail_steps: int,
) -> dict[str, Any]:
    tail_heights = heights[-tail_steps:]
    tail_forces = [sum(row.values()) for row in foot_forces[-tail_steps:]]
    return {
        "final_base_height_m": heights[-1],
        "tail_base_height_min_m": min(tail_heights),
        "tail_base_height_max_m": max(tail_heights),
        "tail_base_height_span_m": max(tail_heights) - min(tail_heights),
        "final_vertical_velocity_mps": vertical_velocities[-1],
        "tail_max_abs_vertical_velocity_mps": max(abs(value) for value in vertical_velocities[-tail_steps:]),
        "final_roll_pitch_rad": list(tilts[-1]),
        "tail_max_abs_roll_or_pitch_rad": max(
            max(abs(roll), abs(pitch)) for roll, pitch in tilts[-tail_steps:]
        ),
        "final_foot_normal_force_n": foot_forces[-1],
        "tail_mean_total_foot_normal_force_n": float(np.mean(tail_forces)),
        "tail_steps_with_nonzero_foot_force": sum(value > 0.0 for value in tail_forces),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--door-instance", required=True, type=Path)
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    door_xml = output / "door.xml"
    door_report = output / "door_build_report_v2.json"
    scene_xml = output / "standing_vitals_scene.xml"
    scene_report = output / "standing_vitals_scene_build_report_v2.json"
    spec = DoorInstanceSpec.from_path(args.door_instance.resolve(strict=True))
    MjcfDoorBuilderV2(spec).write(door_xml, door_report)
    armature_by_joint = _resolved_armature(args.resolved_config.resolve(strict=True))
    PairedSceneBuilderV2(
        args.robot, door_xml, armature_by_joint=armature_by_joint
    ).write(scene_xml, scene_report)

    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    contract = resolved_a2_piper_contract()
    actuator_map = NameResolvedActuatorMapV2.from_model(model, contract.sim_joint_names)
    if actuator_map.door_hinge_actuator_id != 0 or actuator_map.handle_actuator_id != 1:
        raise ValueError("standing gate requires the two door actuators first")
    pd = ExternalPdController(
        stiffness=torch.tensor(contract.stiffness, dtype=torch.float64),
        damping=torch.tensor(contract.damping, dtype=torch.float64),
        torque_limit=torch.tensor(contract.torque_limit, dtype=torch.float64),
    )
    default64 = torch.tensor(contract.default_dof_pos, dtype=torch.float64).unsqueeze(0)
    torque_limit = np.array(contract.torque_limit)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    foot_ids = {
        name: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        for name in FOOT_GEOM_NAMES
    }

    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    passive_evidence = _Evidence(model, actuator_map, torque_limit)
    passive_heights: list[float] = []
    passive_vz: list[float] = []
    passive_tilts: list[tuple[float, float]] = []
    passive_forces: list[dict[str, float]] = []
    for _ in range(400):
        effort, raw_effort = _pd_effort(
            pd,
            default64,
            data.qpos[actuator_map.robot_qpos_addresses],
            data.qvel[actuator_map.robot_qvel_addresses],
        )
        passive_evidence.apply(data, effort, raw_effort)
        mujoco.mj_step(model, data)
        passive_heights.append(float(data.qpos[2]))
        passive_vz.append(float(data.qvel[2]))
        passive_tilts.append(_roll_pitch(model, data, trunk_id))
        passive_forces.append(_foot_forces(model, data, floor_id, foot_ids))
    passive = _summarize_vitals(
        heights=passive_heights,
        vertical_velocities=passive_vz,
        tilts=passive_tilts,
        foot_forces=passive_forces,
        tail_steps=100,
    )
    passive["mode"] = "POLICY_FREE_DEFAULT_POSTURE_PD_LANDING"
    passive["duration_s"] = 2.0
    passive["acceptance"] = {
        "height_band_m": [
            HEIGHT_REFERENCE_M - HEIGHT_TOLERANCE_M,
            HEIGHT_REFERENCE_M + HEIGHT_TOLERANCE_M,
        ],
        "tail_height_span_max_m": 0.02,
        "final_abs_vertical_velocity_max_mps": 0.05,
        "foot_force_required": True,
    }
    passive["result"] = "PASS" if (
        passive["acceptance"]["height_band_m"][0]
        <= passive["final_base_height_m"]
        <= passive["acceptance"]["height_band_m"][1]
        and passive["tail_base_height_span_m"] <= 0.02
        and abs(passive["final_vertical_velocity_mps"]) <= 0.05
        and passive["tail_steps_with_nonzero_foot_force"] > 0
    ) else "FAIL"

    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    a2_policy = torch.jit.load(
        str(args.a2_base_policy.resolve(strict=True)), map_location="cpu"
    ).eval()
    joint_map = A2PiperJointMap.from_sim_joint_names(contract.sim_joint_names, device="cpu")
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    gait = SensorClock(batch_size=1, physics_dt=PHYSICS_DT, device="cpu", dtype=torch.float32)
    action_transform = A2ActionTransform(joint_map, action_scale=contract.action_scale)
    default32 = default64.float()
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    zero_base_command = torch.zeros((1, 5), dtype=torch.float32)
    position_target = default64.clone()
    frozen_evidence = _Evidence(model, actuator_map, torque_limit)
    frozen_heights: list[float] = []
    frozen_vz: list[float] = []
    frozen_tilts: list[tuple[float, float]] = []
    frozen_forces: list[dict[str, float]] = []
    for physics_step in range(1000):
        if physics_step % 4 == 0:
            _, projected_gravity = _a2_body_observation(model, data, trunk_id)
            roll_pitch = _roll_pitch(model, data, trunk_id)
            frame = frame_builder.build(
                projected_gravity=torch.from_numpy(projected_gravity).float().unsqueeze(0),
                dof_pos=torch.from_numpy(
                    data.qpos[actuator_map.robot_qpos_addresses].copy()
                ).float().unsqueeze(0),
                default_dof_pos=default32,
                dof_vel=torch.from_numpy(
                    data.qvel[actuator_map.robot_qvel_addresses].copy()
                ).float().unsqueeze(0),
                previous_leg_action=previous_leg,
                physical_base_command=zero_base_command,
                base_roll_pitch=torch.tensor([roll_pitch], dtype=torch.float32),
                gait_clock=gait.signal(),
            )
            with torch.inference_mode():
                leg_action = a2_policy(history.append(frame))
            position_target = action_transform.compose(
                high_level_action=torch.zeros((1, 12), dtype=torch.float32),
                policy_leg_action=leg_action,
                default_dof_pos=default32,
            ).position_target.double()
            previous_leg = leg_action
        effort, raw_effort = _pd_effort(
            pd,
            position_target,
            data.qpos[actuator_map.robot_qpos_addresses],
            data.qvel[actuator_map.robot_qvel_addresses],
        )
        frozen_evidence.apply(data, effort, raw_effort)
        mujoco.mj_step(model, data)
        gait.advance(zero_base_command[:, :3])
        frozen_heights.append(float(data.qpos[2]))
        frozen_vz.append(float(data.qvel[2]))
        frozen_tilts.append(_roll_pitch(model, data, trunk_id))
        frozen_forces.append(_foot_forces(model, data, floor_id, foot_ids))
    frozen = _summarize_vitals(
        heights=frozen_heights,
        vertical_velocities=frozen_vz,
        tilts=frozen_tilts,
        foot_forces=frozen_forces,
        tail_steps=200,
    )
    frozen["mode"] = "FROZEN_A2_BASE_ZERO_COMMAND"
    frozen["duration_s"] = 5.0
    frozen["acceptance"] = {
        "requested_approximate_height_band_m": [
            HEIGHT_REFERENCE_M - HEIGHT_TOLERANCE_M,
            HEIGHT_REFERENCE_M + HEIGHT_TOLERANCE_M,
        ],
        "explicit_contact_solver_margin_m": CONTACT_SOLVER_MARGIN_M,
        "evaluated_height_band_m": [
            HEIGHT_REFERENCE_M - HEIGHT_TOLERANCE_M - CONTACT_SOLVER_MARGIN_M,
            HEIGHT_REFERENCE_M + HEIGHT_TOLERANCE_M + CONTACT_SOLVER_MARGIN_M,
        ],
        "tail_height_span_max_m": 0.03,
        "tail_max_abs_roll_or_pitch_rad": 0.35,
        "foot_force_required": True,
    }
    frozen["result"] = "PASS" if (
        frozen["acceptance"]["evaluated_height_band_m"][0]
        <= frozen["final_base_height_m"]
        <= frozen["acceptance"]["evaluated_height_band_m"][1]
        and frozen["tail_base_height_span_m"] <= 0.03
        and frozen["tail_max_abs_roll_or_pitch_rad"] <= 0.35
        and frozen["tail_steps_with_nonzero_foot_force"] > 0
    ) else "FAIL"

    combined_audit = {
        "result": "PASS",
        "mapping": actuator_map.receipt(model),
        "passive_trace": passive_evidence.receipt(),
        "frozen_a2_trace": frozen_evidence.receipt(),
        "r1_clip_explanation": (
            "r1 external_pd_clip_applications counted clip-function invocations. It did not count "
            "actual saturation. V2 separates invocations, rows_with_any_saturation, and saturated_joint_steps."
        ),
    }
    for evidence in (passive_evidence, frozen_evidence):
        if (
            evidence.max_ctrl_write_error != 0.0
            or evidence.max_actuator_force_error != 0.0
            or evidence.max_generalized_force_error != 0.0
        ):
            combined_audit["result"] = "FAIL"

    result = "PASS" if (
        passive["result"] == "PASS"
        and frozen["result"] == "PASS"
        and combined_audit["result"] == "PASS"
    ) else "FAIL"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "schema": "doordog.sim2sim.standing_vitals_gate.v1",
        "rule": "INSTRUMENT_VITALS_BEFORE_MEASUREMENT_INTERPRETATION",
        "result": result,
        "campaign_authorization": "AUTHORIZED" if result == "PASS" else "DENIED",
        "backend": "mujoco_cpu",
        "physics_dt_s": PHYSICS_DT,
        "resolved_armature_by_joint": armature_by_joint,
        "armature_source": str(args.resolved_config.resolve(strict=True)),
        "passive_landing": passive,
        "frozen_a2_standing": frozen,
        "actuator_mapping_audit": combined_audit,
        "foot_floor_contact_pair": {
            "floor_geom_id": floor_id,
            "foot_geom_ids": foot_ids,
            "all_feet_produced_nonzero_force_in_passive_tail": all(
                any(row[name] > 0.0 for row in passive_forces[-100:]) for name in FOOT_GEOM_NAMES
            ),
        },
        "producer_identity": {
            "git_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/run_standing_vitals_gate.py",
        },
    }
    receipt_path = output / "standing_vitals_gate_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "result": result,
                "passive": passive,
                "frozen_a2": frozen,
                "actuator_mapping_audit": combined_audit,
                "receipt": str(receipt_path),
            },
            sort_keys=True,
        )
    )
    if result != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
