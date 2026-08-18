#!/usr/bin/env python3
"""Localize the first true-100/45 external-PD acceleration explosion."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
import torch
import yaml

from gr00t.rl.sim2sim.doors.mjcf_builder_v2 import MjcfDoorBuilderV2
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.actuator_map_v2 import NameResolvedActuatorMapV2
from gr00t.rl.sim2sim.mujoco.external_pd import ExternalPdController
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import PairedSceneBuilderV2
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


QACC_EVIDENCE_THRESHOLD = 1.0e6


def _resolved(config_path: Path) -> tuple[dict[str, float], np.ndarray]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    robot = config["robot"]
    names = list(robot["dof_names"])
    armature = dict(zip(names, robot["dof_armature_list"], strict=True))
    effort = np.asarray(robot["dof_effort_limit_list"], dtype=np.float64)
    effort[names.index("arm_j7")] = 45.0
    effort[names.index("arm_j8")] = 45.0
    return armature, effort


def _overlay_effort(scene_path: Path, effort: np.ndarray) -> None:
    contract = resolved_a2_piper_contract()
    root = ET.parse(scene_path).getroot()
    for name, limit in zip(contract.sim_joint_names, effort, strict=True):
        joint = root.find(f".//joint[@name='{name}']")
        actuator = root.find(f".//actuator/motor[@name='{name}_motor']")
        if joint is None or actuator is None:
            raise ValueError(f"external-PD diagnostic lacks {name}")
        limits = f"{-float(limit):.12g} {float(limit):.12g}"
        joint.set("actuatorfrcrange", limits)
        actuator.set("ctrlrange", limits)
    ET.indent(root, space="  ")
    scene_path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")


def _dof_label(model: mujoco.MjModel, dof_id: int) -> str:
    for joint_id in range(model.njnt):
        start = int(model.jnt_dofadr[joint_id])
        width = 6 if model.jnt_type[joint_id] == mujoco.mjtJoint.mjJNT_FREE else (
            3 if model.jnt_type[joint_id] == mujoco.mjtJoint.mjJNT_BALL else 1
        )
        if start <= dof_id < start + width:
            joint = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
            suffix = (
                ("tx", "ty", "tz", "rx", "ry", "rz")[dof_id - start]
                if width == 6
                else str(dof_id - start)
            )
            return f"{joint}:{suffix}"
    raise ValueError(f"unmapped dof {dof_id}")


def _contacts(model: mujoco.MjModel, data: mujoco.MjData) -> list[dict[str, object]]:
    rows = []
    for index in range(data.ncon):
        contact = data.contact[index]
        wrench = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, index, wrench)
        rows.append(
            {
                "geom1": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(contact.geom1)),
                "geom2": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(contact.geom2)),
                "distance_m": float(contact.dist),
                "normal_force_n": float(wrench[0]),
            }
        )
    rows.sort(key=lambda row: abs(float(row["normal_force_n"])), reverse=True)
    return rows[:12]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", type=Path, required=True)
    parser.add_argument("--door-instance", type=Path, required=True)
    parser.add_argument("--resolved-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    config_path = args.resolved_config.resolve(strict=True)
    armature, effort = _resolved(config_path)
    door_path = output / "door.xml"
    MjcfDoorBuilderV2(
        DoorInstanceSpec.from_path(args.door_instance.resolve(strict=True))
    ).write(door_path, output / "door_build_report_v2.json")
    scene_path = output / "external_pd_true_100_45.xml"
    PairedSceneBuilderV2(
        args.robot.resolve(strict=True), door_path, armature_by_joint=armature
    ).write(scene_path, output / "scene_build_report_v2.json")
    _overlay_effort(scene_path, effort)

    model = mujoco.MjModel.from_xml_path(str(scene_path))
    data = mujoco.MjData(model)
    contract = resolved_a2_piper_contract()
    mapping = NameResolvedActuatorMapV2.from_model(model, contract.sim_joint_names)
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home)
    mujoco.mj_forward(model, data)
    default = torch.tensor(contract.default_dof_pos, dtype=torch.float64).unsqueeze(0)
    pd = ExternalPdController(
        stiffness=torch.tensor(contract.stiffness, dtype=torch.float64),
        damping=torch.tensor(contract.damping, dtype=torch.float64),
        torque_limit=torch.from_numpy(effort.copy()),
    )
    timeline = []
    first_huge = None
    peak = None
    for step in range(400):
        position = torch.from_numpy(data.qpos[mapping.robot_qpos_addresses].copy()).double().unsqueeze(0)
        velocity = torch.from_numpy(data.qvel[mapping.robot_qvel_addresses].copy()).double().unsqueeze(0)
        raw = (
            pd.stiffness[None, :] * (default - position)
            - pd.damping[None, :] * velocity
        )
        clipped = pd.compute(position_target=default, position=position, velocity=velocity)
        mapping.write_robot_ctrl(data, clipped.squeeze(0).numpy())
        mujoco.mj_forward(model, data)
        absolute = np.abs(data.qacc.copy())
        dof_id = int(np.argmax(absolute))
        record = {
            "physics_step": step,
            "time_s_before_step": float(data.time),
            "max_abs_qacc": float(absolute[dof_id]),
            "max_qacc_dof_id": dof_id,
            "max_qacc_dof": _dof_label(model, dof_id),
            "max_abs_raw_pd_effort_nm": float(torch.abs(raw).max().item()),
            "saturated_joint_names": [
                name
                for name, saturated in zip(
                    contract.sim_joint_names,
                    (torch.abs(raw).squeeze(0) > torch.from_numpy(effort)).tolist(),
                    strict=True,
                )
                if saturated
            ],
            "contacts": _contacts(model, data),
        }
        timeline.append(record)
        if peak is None or record["max_abs_qacc"] > peak["max_abs_qacc"]:
            peak = record
        if first_huge is None and record["max_abs_qacc"] >= QACC_EVIDENCE_THRESHOLD:
            first_huge = record
        mujoco.mj_step(model, data)
        if first_huge is not None and step >= int(first_huge["physics_step"]) + 4:
            break

    if first_huge is None:
        raise RuntimeError(
            f"external-PD diagnostic did not reproduce qacc >= {QACC_EVIDENCE_THRESHOLD:g}"
        )
    receipt = {
        "schema": "doordog.sim2sim.qacc_localization_r4.v1",
        "result": "REPRODUCED_EXTERNAL_PD_NUMERICAL_INSTABILITY",
        "physics_dt_s": float(model.opt.timestep),
        "integrator": "EULER",
        "control_surface": {
            "mode": "EXTERNAL_PD_PER_PHYSICS_STEP_CLIP",
            "arm_effort_nm": 100.0,
            "gripper_effort_n": 45.0,
            "resolved_armature": armature,
        },
        "qacc_evidence_threshold": QACC_EVIDENCE_THRESHOLD,
        "first_huge_qacc": first_huge,
        "peak_before_mujoco_reset": peak,
        "timeline": timeline,
        "actuator_mapping": mapping.receipt(model),
        "interpretation": (
            "The first unstable generalized coordinate and contemporaneous contact pair are "
            "reported directly; actuator saturation alone is not assigned as the cause."
        ),
    }
    (output / "qacc_localization_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": receipt["result"], "first_huge_qacc": first_huge}, sort_keys=True))


if __name__ == "__main__":
    main()
