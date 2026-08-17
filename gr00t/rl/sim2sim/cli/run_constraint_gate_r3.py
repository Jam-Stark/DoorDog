#!/usr/bin/env python3
"""Prove equality lock, threshold release, and post-release door motion."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from pathlib import Path

import mujoco
import yaml

from gr00t.rl.sim2sim.doors.mjcf_builder_v2 import MjcfDoorBuilderV2
from gr00t.rl.sim2sim.doors.runtime import ConstraintGate
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import PairedSceneBuilderV2


def _armature(config_path: Path) -> dict[str, float]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    robot = config["robot"]
    return dict(zip(robot["dof_names"], robot["dof_armature_list"], strict=True))


def _drive(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    hinge_dof: int,
    torque_nm: float,
    steps: int,
) -> list[float]:
    values = []
    for _ in range(steps):
        data.qfrc_applied[hinge_dof] = torque_nm
        mujoco.mj_step(model, data)
        values.append(float(data.qpos[model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")]]))
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--door-instance", required=True, type=Path)
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    payload = copy.deepcopy(json.loads(args.door_instance.resolve(strict=True).read_text(encoding="utf-8")))
    payload["identity"]["instance_id"] = f'{payload["identity"]["instance_id"]}_constraint_gate_r3'
    payload["identity"]["materialization"] = "R3_EQUALITY_GATE_DIAGNOSTIC_COPY"
    payload["kinematics"]["latch_mode"] = "constraint_gate"
    instance_path = output / "door_instance_constraint_gate_r3.json"
    instance_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    door_xml = output / "door_constraint_gate_r3.xml"
    door_report = output / "door_build_report_v2.json"
    scene_xml = output / "scene_constraint_gate_r3.xml"
    scene_report = output / "scene_build_report_v2.json"
    spec = DoorInstanceSpec(payload)
    MjcfDoorBuilderV2(spec).write(door_xml, door_report)
    PairedSceneBuilderV2(
        args.robot, door_xml, armature_by_joint=_armature(args.resolved_config.resolve(strict=True))
    ).write(scene_xml, scene_report)

    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    hinge_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    hinge_qpos = int(model.jnt_qposadr[hinge_id])
    hinge_dof = int(model.jnt_dofadr[hinge_id])
    handle_qpos = int(model.jnt_qposadr[handle_id])
    gate = ConstraintGate(
        model,
        release_handle_rad=float(payload["kinematics"]["constraint_gate_release_handle_rad"]),
    )
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    active_at_reset = int(data.eq_active[gate.eq_id])
    locked = _drive(model, data, hinge_dof=hinge_dof, torque_nm=20.0, steps=200)
    locked_max_abs_hinge = max(abs(value) for value in locked)

    data.qpos[handle_qpos] = gate.release_handle_rad - 0.01
    mujoco.mj_forward(model, data)
    below_threshold_released = gate.update(data)
    active_below_threshold = int(data.eq_active[gate.eq_id])
    data.qpos[handle_qpos] = gate.release_handle_rad + 0.01
    mujoco.mj_forward(model, data)
    threshold_released = gate.update(data)
    active_after_release = int(data.eq_active[gate.eq_id])
    hinge_at_release = float(data.qpos[hinge_qpos])
    released = _drive(model, data, hinge_dof=hinge_dof, torque_nm=20.0, steps=200)
    released_motion = max(released) - hinge_at_release

    equality_pass = active_at_reset == 1 and locked_max_abs_hinge < 1.0e-3
    release_pass = (
        not below_threshold_released
        and active_below_threshold == 1
        and threshold_released
        and active_after_release == 0
    )
    locked_door_pass = equality_pass and released_motion > 0.05
    result = "PASS" if equality_pass and release_pass and locked_door_pass else "FAIL"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "schema": "doordog.sim2sim.constraint_gate_r3.v1",
        "result": result,
        "campaign_authorization": "AUTHORIZED" if result == "PASS" else "DENIED",
        "backend": "mujoco_cpu",
        "derived_door_instance": str(instance_path),
        "source_door_instance": str(args.door_instance.resolve(strict=True)),
        "equality_effectiveness": {
            "result": "PASS" if equality_pass else "FAIL",
            "compiled_equality_count": int(model.neq),
            "gate_equality_id": int(gate.eq_id),
            "active_at_reset": active_at_reset,
            "applied_hinge_torque_nm": 20.0,
            "duration_s": 1.0,
            "locked_max_abs_hinge_rad": locked_max_abs_hinge,
        },
        "release_logic": {
            "result": "PASS" if release_pass else "FAIL",
            "release_handle_rad": gate.release_handle_rad,
            "below_threshold_released": below_threshold_released,
            "active_below_threshold": active_below_threshold,
            "threshold_released": threshold_released,
            "active_after_release": active_after_release,
        },
        "locked_door_validation": {
            "result": "PASS" if locked_door_pass else "FAIL",
            "locked_max_abs_hinge_rad": locked_max_abs_hinge,
            "post_release_hinge_motion_rad": released_motion,
            "matched_applied_hinge_torque_nm": 20.0,
        },
        "build_reports": {
            "door": str(door_report),
            "scene": str(scene_report),
        },
        "producer_identity": {
            "git_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/run_constraint_gate_r3.py",
        },
    }
    receipt_path = output / "constraint_gate_r3_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": result, "receipt": str(receipt_path), "locked_max_abs_hinge_rad": locked_max_abs_hinge, "post_release_hinge_motion_rad": released_motion}, sort_keys=True))
    if result != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
