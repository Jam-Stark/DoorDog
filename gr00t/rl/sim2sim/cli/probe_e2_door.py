#!/usr/bin/env python3
"""Compile and run the E2 door mechanics/friction/latch probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from gr00t.rl.sim2sim.doors.runtime import ConstraintGate
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--instance", required=True, type=Path)
    parser.add_argument("--output-receipt", required=True, type=Path)
    args = parser.parse_args()

    model_path = args.model.resolve(strict=True)
    spec = DoorInstanceSpec.from_path(args.instance.resolve(strict=True))
    spec.validate()
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    closed_key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "door_closed")
    hinge_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    hinge_qpos = int(model.jnt_qposadr[hinge_id])
    hinge_dof = int(model.jnt_dofadr[hinge_id])
    handle_qpos = int(model.jnt_qposadr[handle_id])
    gate = ConstraintGate(
        model,
        release_handle_rad=float(spec.payload["kinematics"]["constraint_gate_release_handle_rad"]),
    )

    mujoco.mj_resetDataKeyframe(model, data, closed_key)
    for _ in range(100):
        gate.update(data)
        mujoco.mj_step(model, data)
    closed_angle = float(data.qpos[hinge_qpos])
    if not bool(data.eq_active[gate.eq_id]):
        raise RuntimeError("constraint gate released before handle threshold")

    data.ctrl[1] = float(spec.payload["kinematics"]["handle_limits_rad"][1])
    release_step = None
    for step in range(400):
        if gate.update(data):
            release_step = step
            break
        mujoco.mj_step(model, data)
    if release_step is None:
        raise RuntimeError("constraint gate did not release at the configured handle angle")

    data.ctrl[0] = float(spec.hinge["equilibrium_rad"])
    for _ in range(300):
        data.qfrc_applied[hinge_dof] = 10.0
        mujoco.mj_step(model, data)
    opened_angle = float(data.qpos[hinge_qpos])
    if opened_angle <= closed_angle:
        raise RuntimeError("released door did not open under external hinge torque")
    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
        raise FloatingPointError("E2 door probe produced non-finite state")

    force_probe = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, force_probe, closed_key)
    force_probe.eq_active[gate.eq_id] = 0
    force_probe.qpos[hinge_qpos] = float(spec.payload["kinematics"]["hinge_limits_rad"][1])
    force_probe.qvel[hinge_dof] = 0.0
    mujoco.mj_forward(model, force_probe)
    mechanics = spec.mechanics_receipt()
    receipt = {
        "schema": "doordog.sim2sim.e2_door_probe_receipt.v1",
        "evidence_level": "E2",
        "result_classification": "VALID_WITH_WARNINGS",
        "mujoco_version": mujoco.__version__,
        "model": str(model_path),
        "compiled_dims": {"nq": model.nq, "nv": model.nv, "nu": model.nu, "neq": model.neq},
        "addresses": {
            "door_hinge_qpos": hinge_qpos,
            "door_hinge_dof": hinge_dof,
            "handle_hinge_qpos": handle_qpos,
            "constraint_gate_equality": gate.eq_id,
        },
        "door_resistance_mode": "capped_position_actuator",
        "hinge_actuator_force_probe_nm": float(force_probe.actuator_force[0]),
        "hinge_actuator_force_cap_nm": float(spec.hinge["effort_cap_nm"]),
        "friction_mapping": {
            "static_effort": float(spec.hinge["static_friction_effort"]),
            "dynamic_effort": float(spec.hinge["dynamic_friction_effort"]),
            "viscous_coefficient": float(spec.hinge["viscous_friction_coefficient"]),
            "compiled_mujoco_frictionloss": float(model.dof_frictionloss[hinge_dof]),
            "compiled_mujoco_damping": float(model.dof_damping[hinge_dof]),
            "classification": spec.friction_classification,
        },
        "mechanics_three_face_receipt": mechanics,
        "mechanics_normalized_max_abs_diff": max(
            abs(mechanics["requested_normalized"][field] - mechanics["realized_normalized"][field])
            for field in ("damping_rad", "stiffness_rad", "effort_limit_nm", "door_mass_kg")
        ),
        "latch": {
            "mode": "constraint_gate",
            "closed_hold_angle_rad": closed_angle,
            "release_handle_threshold_rad": gate.release_handle_rad,
            "release_handle_angle_rad": float(data.qpos[handle_qpos]),
            "release_step": release_step,
            "equality_active_after_release": bool(data.eq_active[gate.eq_id]),
            "opened_angle_after_external_torque_rad": opened_angle,
        },
        "final_state_finite": True,
        "warnings": [
            "FRICTION_SEMANTIC_GAP: MuJoCo frictionloss represents dynamic Coulomb effort and cannot express a distinct static effort.",
            "Constraint-gate is the realized latch mode; physical-collision latch was not promoted."
        ],
    }
    args.output_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.output_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
