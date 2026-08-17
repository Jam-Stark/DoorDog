#!/usr/bin/env python3
"""Run one independent MuJoCo E3 robot+door open-loop scenario."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import mujoco
import numpy as np
import torch

from gr00t.rl.sim2sim.doors.metrics import DoorStateMetrics
from gr00t.rl.sim2sim.doors.runtime import ConstraintGate
from gr00t.rl.sim2sim.mujoco.external_pd import ExternalPdController
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True, type=Path)
    parser.add_argument("--door-instance", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    scene = args.scene.resolve(strict=True)
    instance = json.loads(args.door_instance.resolve(strict=True).read_text(encoding="utf-8"))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(
        model, data, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    )
    mujoco.mj_forward(model, data)

    contract = resolved_a2_piper_contract()
    dtype = torch.float64
    default = torch.tensor(contract.default_dof_pos, dtype=dtype).unsqueeze(0)
    target = default.clone()
    controller = ExternalPdController(
        stiffness=torch.tensor(contract.stiffness, dtype=dtype),
        damping=torch.tensor(contract.damping, dtype=dtype),
        torque_limit=torch.tensor(contract.torque_limit, dtype=dtype),
    )
    robot_qpos = slice(7, 27)
    robot_qvel = slice(6, 26)
    door_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    door_qpos = int(model.jnt_qposadr[door_joint])
    handle_qpos = int(model.jnt_qposadr[handle_joint])
    door_dof = int(model.jnt_dofadr[door_joint])
    door_actuator = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "door_hinge_capped_position")
    handle_actuator = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "handle_capped_position")
    gate = ConstraintGate(
        model,
        release_handle_rad=float(instance["kinematics"]["constraint_gate_release_handle_rad"]),
    )
    metrics = DoorStateMetrics(open_threshold_rad=0.174533)

    rows = []
    release_time = None
    robot_clip_steps = 0
    total_steps = 600
    for step in range(total_steps):
        if step == 100:
            target[0, 15] += 0.05
            data.ctrl[handle_actuator] = float(instance["kinematics"]["handle_limits_rad"][1])
        if gate.update(data) and release_time is None:
            release_time = float(data.time)
        data.qfrc_applied[door_dof] = 10.0 if release_time is not None else 0.0
        position = torch.from_numpy(data.qpos[robot_qpos].copy()).to(dtype=dtype).unsqueeze(0)
        velocity = torch.from_numpy(data.qvel[robot_qvel].copy()).to(dtype=dtype).unsqueeze(0)
        torque = controller.compute(position_target=target, position=position, velocity=velocity)
        data.ctrl[:20] = torque.squeeze(0).numpy()
        robot_clip_steps += 1
        mujoco.mj_step(model, data)
        hinge = float(data.qpos[door_qpos])
        handle = float(data.qpos[handle_qpos])
        metrics.update(time_s=float(data.time), hinge_rad=hinge, handle_rad=handle)
        rows.append(
            {
                "step": step,
                "time_s": float(data.time),
                "base_height_m": float(data.qpos[2]),
                "max_abs_robot_ctrl_nm": float(torch.max(torch.abs(torque))),
                "door_hinge_rad": hinge,
                "handle_hinge_rad": handle,
                "constraint_gate_active": int(data.eq_active[gate.eq_id]),
                "door_external_torque_nm": float(data.qfrc_applied[door_dof]),
            }
        )
    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
        raise FloatingPointError("E3 open-loop scene produced non-finite state")

    trace_path = output / "open_loop_trace.csv"
    with trace_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    task_metrics = metrics.receipt()
    if not task_metrics["opened"]:
        raise RuntimeError("E3 direct door-state open threshold was not reached")
    receipt = {
        "schema": "doordog.sim2sim.e3_open_loop_receipt.v1",
        "evidence_level": "E3",
        "result_classification": "VALID_WITH_WARNINGS",
        "scene": str(scene),
        "mujoco_version": mujoco.__version__,
        "physics_hz": 200,
        "steps": total_steps,
        "trace": str(trace_path),
        "external_pd": {
            "clip_cadence": "EVERY_PHYSICS_STEP",
            "clip_applications": robot_clip_steps,
            "max_abs_ctrl_nm": max(row["max_abs_robot_ctrl_nm"] for row in rows),
        },
        "latch": {
            "mode": "constraint_gate",
            "release_time_s": release_time,
            "active_final": bool(data.eq_active[gate.eq_id]),
        },
        "task_metrics": task_metrics,
        "final_state_finite": True,
        "final_base_height_m": float(data.qpos[2]),
        "warnings": [
            "This is an independent MuJoCo open-loop excitation, not a paired Isaac trajectory.",
            "Door opening torque is an explicit E3 probe input; it is not a policy success claim."
        ],
    }
    (output / "open_loop_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
