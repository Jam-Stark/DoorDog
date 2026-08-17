#!/usr/bin/env python3
"""Run the E6 CPU door mass/damping/friction robustness sweep."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import mujoco
import numpy as np

from gr00t.rl.sim2sim.doors.runtime import ConstraintGate


CASES = (
    {"name": "baseline", "mass": 100.0, "drive_damping": 50.0, "stiffness": 2.0, "cap": 4.5, "static": 1.0, "dynamic": 0.75, "viscous": 0.0},
    {"name": "static_high_gap", "mass": 100.0, "drive_damping": 50.0, "stiffness": 2.0, "cap": 4.5, "static": 1.25, "dynamic": 0.75, "viscous": 0.0},
    {"name": "dynamic_low", "mass": 100.0, "drive_damping": 50.0, "stiffness": 2.0, "cap": 4.5, "static": 1.0, "dynamic": 0.5, "viscous": 0.0},
    {"name": "dynamic_high", "mass": 100.0, "drive_damping": 50.0, "stiffness": 2.0, "cap": 4.5, "static": 1.0, "dynamic": 1.0, "viscous": 0.0},
    {"name": "viscous_0p2", "mass": 100.0, "drive_damping": 50.0, "stiffness": 2.0, "cap": 4.5, "static": 1.0, "dynamic": 0.75, "viscous": 0.2},
    {"name": "soft_drive", "mass": 100.0, "drive_damping": 25.0, "stiffness": 1.0, "cap": 4.5, "static": 1.0, "dynamic": 0.75, "viscous": 0.0},
    {"name": "stiff_drive", "mass": 100.0, "drive_damping": 75.0, "stiffness": 4.0, "cap": 4.5, "static": 1.0, "dynamic": 0.75, "viscous": 0.0},
    {"name": "light_low_cap", "mass": 75.0, "drive_damping": 50.0, "stiffness": 2.0, "cap": 3.0, "static": 1.0, "dynamic": 0.75, "viscous": 0.0},
    {"name": "heavy_high_cap", "mass": 125.0, "drive_damping": 50.0, "stiffness": 2.0, "cap": 6.0, "static": 1.0, "dynamic": 0.75, "viscous": 0.0},
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--door-model", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    model_path = args.door_model.resolve(strict=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for case in CASES:
        model = mujoco.MjModel.from_xml_path(str(model_path))
        data = mujoco.MjData(model)
        closed_key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "door_closed")
        panel_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "door_panel")
        hinge_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
        handle_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
        hinge_act = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "door_hinge_capped_position")
        hinge_qpos = int(model.jnt_qposadr[hinge_id])
        handle_qpos = int(model.jnt_qposadr[handle_id])
        hinge_dof = int(model.jnt_dofadr[hinge_id])
        mass_scale = case["mass"] / float(model.body_mass[panel_id])
        model.body_mass[panel_id] *= mass_scale
        model.body_inertia[panel_id] *= mass_scale
        model.dof_frictionloss[hinge_dof] = case["dynamic"]
        model.dof_damping[hinge_dof] = case["viscous"]
        model.actuator_gainprm[hinge_act, 0] = case["stiffness"]
        model.actuator_biasprm[hinge_act, 1] = -case["stiffness"]
        model.actuator_biasprm[hinge_act, 2] = -case["drive_damping"]
        model.actuator_forcerange[hinge_act] = (-case["cap"], case["cap"])
        mujoco.mj_setConst(model, data)
        mujoco.mj_resetDataKeyframe(model, data, closed_key)
        gate = ConstraintGate(model, release_handle_rad=0.5235987755982988)
        data.qpos[handle_qpos] = gate.release_handle_rad + 0.02
        mujoco.mj_forward(model, data)
        if not gate.update(data):
            raise RuntimeError(f"{case['name']} did not release its constraint gate")

        max_hinge = float(data.qpos[hinge_qpos])
        peak_actuator_force = 0.0
        for _ in range(300):
            data.qfrc_applied[hinge_dof] = 10.0
            mujoco.mj_step(model, data)
            max_hinge = max(max_hinge, float(data.qpos[hinge_qpos]))
            peak_actuator_force = max(peak_actuator_force, abs(float(data.actuator_force[hinge_act])))
        finite = bool(np.isfinite(data.qpos).all() and np.isfinite(data.qvel).all())
        if not finite:
            raise FloatingPointError(f"{case['name']} produced non-finite state")
        results.append(
            {
                **case,
                "compiled_frictionloss": float(model.dof_frictionloss[hinge_dof]),
                "compiled_viscous_damping": float(model.dof_damping[hinge_dof]),
                "friction_classification": (
                    "FRICTION_SEMANTIC_GAP" if case["static"] != case["dynamic"] else "FRICTION_SEMANTICS_ALIGNED"
                ),
                "final_hinge_rad": float(data.qpos[hinge_qpos]),
                "max_hinge_rad": max_hinge,
                "final_hinge_velocity_rad_s": float(data.qvel[hinge_dof]),
                "peak_capped_actuator_force_nm": peak_actuator_force,
                "finite": finite,
            }
        )

    csv_path = output / "robustness_cases.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    receipt = {
        "schema": "doordog.sim2sim.e6_robustness_receipt.v1",
        "evidence_level": "E6",
        "result_classification": "VALID_WITH_WARNINGS",
        "mujoco_version": mujoco.__version__,
        "door_model": str(model_path),
        "device": "cpu",
        "case_count": len(results),
        "all_cases_finite": all(result["finite"] for result in results),
        "swept_axes": [
            "door_mass_kg",
            "hinge_drive_damping_nms_per_rad",
            "hinge_stiffness_nm_per_rad",
            "hinge_effort_cap_nm",
            "static_friction_effort",
            "dynamic_friction_effort",
            "viscous_friction_coefficient",
        ],
        "cases": results,
        "trace": str(csv_path),
        "optional_renderer_variants": "NOT_RUN_OPTIONAL",
        "warnings": [
            "Static friction is retained as an input axis but cannot alter MuJoCo frictionloss independently; affected rows remain FRICTION_SEMANTIC_GAP.",
            "This door-only sweep reports response data and numerical validity, not Isaac physical parity or policy robustness."
        ],
    }
    (output / "robustness_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
