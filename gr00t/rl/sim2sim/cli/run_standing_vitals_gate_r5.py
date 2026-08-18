#!/usr/bin/env python3
"""Mandatory r5 standing-vitals gate through the resolved full action warp."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import mujoco
import numpy as np
import torch

from gr00t.rl.sim2sim.cli.run_standing_vitals_gate import (
    _a2_body_observation,
    _foot_forces,
)
from gr00t.rl.sim2sim.cli.run_standing_vitals_gate_r4 import (
    _NativeEvidence,
    _roll_pitch,
    _summary,
)
from gr00t.rl.sim2sim.doors.mjcf_builder_v2 import MjcfDoorBuilderV2
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_warp_r5 import (
    FullActionWarpR5,
    ResolvedActionWarpContractR5,
)
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.native_position_r4 import (
    NameResolvedPositionActuatorMapR4,
    NativePositionSceneR4,
    ResolvedNativePositionContractR4,
)
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import (
    FOOT_GEOM_NAMES,
    PairedSceneBuilderV2,
)
from gr00t.rl.sim2sim.mujoco.sensor_clock import SensorClock
from gr00t.rl.sim2sim.mujoco.stage_contract_minimal import StageContractMinimal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", type=Path, required=True)
    parser.add_argument("--door-instance", type=Path, required=True)
    parser.add_argument("--resolved-config", type=Path, required=True)
    parser.add_argument("--action-warp-receipt", type=Path, required=True)
    parser.add_argument("--a2-base-policy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    action_warp_receipt_path = args.action_warp_receipt.resolve(strict=True)
    action_warp_receipt = json.loads(
        action_warp_receipt_path.read_text(encoding="utf-8")
    )
    if (
        action_warp_receipt["result"] != "PASS"
        or action_warp_receipt["coverage"] != "NONE_MISSING"
    ):
        raise ValueError("r5 standing gate requires the complete action-warp PASS")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    native_contract = ResolvedNativePositionContractR4.from_config(args.resolved_config)
    warp_contract = ResolvedActionWarpContractR5.from_config(args.resolved_config)
    door_xml = output / "door.xml"
    MjcfDoorBuilderV2(
        DoorInstanceSpec.from_path(args.door_instance.resolve(strict=True))
    ).write(door_xml, output / "door_build_report_v2.json")
    source_scene = output / "external_pd_source_scene.xml"
    PairedSceneBuilderV2(
        args.robot.resolve(strict=True),
        door_xml,
        armature_by_joint=native_contract.values_by_joint(native_contract.armature),
    ).write(source_scene, output / "external_pd_source_scene_build_report_v2.json")
    scene = output / "standing_vitals_scene_r5.xml"
    NativePositionSceneR4(source_scene, native_contract).write(
        scene, output / "native_position_scene_build_report_r5.json"
    )
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    mapping = NameResolvedPositionActuatorMapR4.from_model(
        model, native_contract.joint_names
    )
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    trunk = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    foot_ids = {
        name: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        for name in FOOT_GEOM_NAMES
    }
    effort_limit = np.asarray(native_contract.effort_limit)
    default = np.asarray(native_contract.default_position)

    mujoco.mj_resetDataKeyframe(model, data, home)
    mujoco.mj_forward(model, data)
    passive_evidence = _NativeEvidence(model, mapping, effort_limit)
    passive_heights: list[float] = []
    passive_vz: list[float] = []
    passive_tilts: list[tuple[float, float]] = []
    passive_forces: list[dict[str, float]] = []
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
    base_policy = torch.jit.load(
        str(args.a2_base_policy.resolve(strict=True)), map_location="cpu"
    ).eval()
    joint_map = A2PiperJointMap.from_sim_joint_names(
        native_contract.joint_names, device="cpu"
    )
    stage_tracker = StageContractMinimal(
        dtype=torch.float32,
        device="cpu",
        delta_scale=warp_contract.delta_action_scale,
        delta_clip=warp_contract.delta_action_clip,
    )
    action_warp = FullActionWarpR5(
        contract=warp_contract,
        joint_map=joint_map,
        stage_tracker=stage_tracker,
    )
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    gait = SensorClock(batch_size=1, physics_dt=0.005, device="cpu", dtype=torch.float32)
    default32 = torch.from_numpy(default.copy()).float().unsqueeze(0)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    zero_command = torch.zeros((1, 5), dtype=torch.float32)
    position_target = default.copy()
    frozen_evidence = _NativeEvidence(model, mapping, effort_limit)
    frozen_heights: list[float] = []
    frozen_vz: list[float] = []
    frozen_tilts: list[tuple[float, float]] = []
    frozen_forces: list[dict[str, float]] = []
    frozen_leg_action_clip_steps = 0
    frozen_max_abs_robot_qvel = 0.0
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
            warped = action_warp.apply(
                raw_high_level_action=torch.zeros((1, 12), dtype=torch.float32),
                policy_leg_action=previous_leg,
                default_dof_pos=default32,
            )
            position_target = warped.position_target.squeeze(0).numpy()
            frozen_leg_action_clip_steps += int(warped.simulator_action_clipped.any())
        frozen_evidence.apply(data, position_target)
        mujoco.mj_step(model, data)
        gait.advance(zero_command[:, :3])
        frozen_max_abs_robot_qvel = max(
            frozen_max_abs_robot_qvel,
            float(np.max(np.abs(data.qvel[mapping.robot_qvel_addresses]))),
        )
        frozen_heights.append(float(data.qpos[2]))
        frozen_vz.append(float(data.qvel[2]))
        frozen_tilts.append(_roll_pitch(data, trunk))
        frozen_forces.append(_foot_forces(model, data, floor, foot_ids))
    frozen = _summary(frozen_heights, frozen_vz, frozen_tilts, frozen_forces, 200)
    frozen["mode"] = "FROZEN_A2_BASE_ZERO_COMMAND_R5_FULL_ACTION_WARP"
    frozen["duration_s"] = 5.0
    frozen["max_abs_robot_joint_velocity_radps"] = frozen_max_abs_robot_qvel
    frozen["policy_steps_with_final_action_clip"] = frozen_leg_action_clip_steps
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
        for key in (
            "max_target_write_error",
            "max_effort_over_limit",
            "max_generalized_force_error",
        )
    ) else "FAIL"
    result = "PASS" if (
        passive["result"] == frozen["result"] == mapping_result == "PASS"
    ) else "FAIL"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "schema": "doordog.sim2sim.standing_vitals_gate.r5.v1",
        "rule": "INSTRUMENT_VITALS_BEFORE_MEASUREMENT_INTERPRETATION",
        "result": result,
        "campaign_authorization": "AUTHORIZED" if result == "PASS" else "DENIED",
        "action_warp_receipt": str(action_warp_receipt_path),
        "action_warp_coverage": action_warp_receipt["coverage"],
        "backend": "mujoco_cpu",
        "physics_dt_s": float(model.opt.timestep),
        "integrator": "implicitfast",
        "control_mode": "MUJOCO_NATIVE_POSITION_TRUE_100_45_R5_FULL_ACTION_WARP",
        "passive_landing": passive,
        "frozen_a2_standing": frozen,
        "actuator_mapping_audit": {
            "result": mapping_result,
            "mapping": mapping.receipt(model),
            "passive_trace": passive_audit,
            "frozen_a2_trace": frozen_audit,
            "effort_limit_by_joint": native_contract.values_by_joint(
                native_contract.effort_limit
            ),
        },
        "foot_floor_contact_pair": {
            "floor_geom_id": floor,
            "foot_geom_ids": foot_ids,
            "all_feet_nonzero_in_passive_tail": all(
                any(row[name] > 0.0 for row in passive_forces[-100:])
                for name in FOOT_GEOM_NAMES
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
            "path": "gr00t/rl/sim2sim/cli/run_standing_vitals_gate_r5.py",
        },
    }
    (output / "standing_vitals_gate_r5_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": result, "passive": passive, "frozen": frozen}, sort_keys=True))
    if result != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
