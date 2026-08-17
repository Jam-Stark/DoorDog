#!/usr/bin/env python3
"""Run the E1 compiled-robot, action, 54D-frame, and torque-clip probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
import torch

from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_transform import A2ActionTransform
from gr00t.rl.sim2sim.mujoco.external_pd import ExternalPdController
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output-receipt", required=True, type=Path)
    parser.add_argument("--steps", type=int, default=200)
    args = parser.parse_args()

    model_path = args.model.resolve(strict=True)
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "home")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)

    contract = resolved_a2_piper_contract()
    dtype = torch.float64
    joint_map = A2PiperJointMap.from_sim_joint_names(contract.sim_joint_names, device="cpu")
    stiffness = torch.tensor(contract.stiffness, dtype=dtype)
    damping = torch.tensor(contract.damping, dtype=dtype)
    limits = torch.tensor(contract.torque_limit, dtype=dtype)
    controller = ExternalPdController(stiffness=stiffness, damping=damping, torque_limit=limits)
    default = torch.tensor(contract.default_dof_pos, dtype=dtype).unsqueeze(0)

    high_action = torch.zeros((1, 12), dtype=dtype)
    high_action[:, 11] = 1.0
    action = A2ActionTransform(joint_map, action_scale=contract.action_scale).compose(
        high_level_action=high_action,
        policy_leg_action=torch.zeros((1, 12), dtype=dtype),
        default_dof_pos=default,
    )
    synthetic_saturation = controller.compute(
        position_target=default + 1.0,
        position=default,
        velocity=torch.zeros_like(default),
    )

    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    rotation = data.xmat[trunk_id].reshape(3, 3)
    projected_gravity = rotation.T @ np.array([0.0, 0.0, -1.0])
    frame = A2BaseFrameBuilder(joint_map).build(
        projected_gravity=torch.from_numpy(projected_gravity).to(dtype=dtype).unsqueeze(0),
        dof_pos=torch.from_numpy(data.qpos[7:].copy()).to(dtype=dtype).unsqueeze(0),
        default_dof_pos=default,
        dof_vel=torch.from_numpy(data.qvel[6:].copy()).to(dtype=dtype).unsqueeze(0),
        previous_leg_action=torch.zeros((1, 12), dtype=dtype),
        physical_base_command=torch.zeros((1, 5), dtype=dtype),
        base_roll_pitch=torch.zeros((1, 2), dtype=dtype),
        gait_clock=torch.tensor([[0.0, 1.0]], dtype=dtype),
    )
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=dtype).append(frame)

    max_abs_ctrl = 0.0
    for _ in range(args.steps):
        position = torch.from_numpy(data.qpos[7:].copy()).to(dtype=dtype).unsqueeze(0)
        velocity = torch.from_numpy(data.qvel[6:].copy()).to(dtype=dtype).unsqueeze(0)
        torque = controller.compute(position_target=default, position=position, velocity=velocity)
        data.ctrl[:] = torque.squeeze(0).numpy()
        max_abs_ctrl = max(max_abs_ctrl, float(torch.max(torch.abs(torque))))
        mujoco.mj_step(model, data)
    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
        raise FloatingPointError("E1 robot probe produced non-finite state")

    receipt = {
        "schema": "doordog.sim2sim.e1_robot_probe_receipt.v1",
        "evidence_level": "E1",
        "result_classification": "VALID_COMPARABLE",
        "mujoco_version": mujoco.__version__,
        "model": str(model_path),
        "compiled_dims": {"nq": model.nq, "nv": model.nv, "nu": model.nu},
        "a2_base_frame_dim": int(frame.shape[1]),
        "a2_base_history_dim": int(history.shape[1]),
        "a2_base_first_history_replicated": bool(torch.equal(history[:, :54], history[:, -54:])),
        "policy_leg_indices_in_sim_order": joint_map.policy_leg_indices.tolist(),
        "action_dims": {
            "student_high_level": int(action.high_level_action.shape[1]),
            "logical_applied": int(action.logical_action.shape[1]),
            "simulator_raw": int(action.simulator_raw_action.shape[1]),
            "position_target": int(action.position_target.shape[1]),
        },
        "open_gripper_target": action.position_target[0, -2:].tolist(),
        "external_pd": {
            "physics_steps": args.steps,
            "torque_clip_applications": args.steps,
            "clip_cadence": "EVERY_PHYSICS_STEP",
            "synthetic_saturated_torque": synthetic_saturation.squeeze(0).tolist(),
            "synthetic_gripper_saturated_torque": synthetic_saturation[0, -2:].tolist(),
            "runtime_max_abs_ctrl": max_abs_ctrl,
        },
        "final_state_finite": True,
        "final_time_s": float(data.time),
        "final_base_height_m": float(data.qpos[2]),
    }
    args.output_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.output_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
