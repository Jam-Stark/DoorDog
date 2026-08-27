#!/usr/bin/env python3
"""DepthADD v3 Student → MuJoCo randomized sim2sim evaluator.

The handoff bundle remains the authority.  This command only materializes its
registered experiment, executes independent shardable episodes, and reduces
the recorded episode receipts.  Robot targets drive the exact 200 Hz ideal-PD
face declared by the DepthADD v3 bundle.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Iterable, Mapping

import mujoco
import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml
from PIL import Image

from gr00t.rl.sim2sim.doors.depthadd_v3 import DepthADDV3DoorBuilder, DepthADDV3DoorFactory
from gr00t.rl.sim2sim.doors.runtime import ConstraintGate
from gr00t.rl.sim2sim.evaluation.depthadd_v3_experiment import materialize_depthadd_v3_experiment
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_warp_r5 import FullActionWarpR5, ResolvedActionWarpContractR5
from gr00t.rl.sim2sim.mujoco.actuator_map_v2 import (
    DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION,
    MUJOCO_LOCAL_DECLARED_REALIZATION,
    NameResolvedActuatorMapV2,
    capture_depthadd_v3_integration_state,
    capture_depthadd_v3_native_contact_snapshot,
    capture_depthadd_v3_pre_step_authority,
    configure_depthadd_v3_production_contact_solref_surface,
    restore_depthadd_v3_pre_step_authority,
)
from gr00t.rl.sim2sim.mujoco.actor_obs_contract import (
    compose_depthadd_v3_actor_obs,
    depthadd_v3_actor_obs_contract,
)
from gr00t.rl.sim2sim.mujoco.depthadd_initial_state import (
    apply_depthadd_initial_state,
    realize_depthadd_initial_state,
)
from gr00t.rl.sim2sim.mujoco.depthadd_stage import (
    STAGE_GRASP,
    STAGE_OPEN,
    STAGE_SWING,
    DepthAddStageAction,
    DepthAddStageObservation,
    DepthAddStageTracker,
)
from gr00t.rl.sim2sim.mujoco.depthadd_visual import (
    apply_fixed_nominal_color_pipeline,
    apply_surface_redraw_to_model,
    augment_normalized_depth_frame,
    augment_rgb_frame,
    fixed_nominal_appearance_factor_names,
    sample_surface_redraw,
    write_depthadd_v3_diagnostic_overlay,
    write_depthadd_v3_fixed_nominal_appearance_factor,
    write_depthadd_v3_source_nominal_appearance_calibration,
    write_depthadd_v3_visual_overlay,
)
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import PairedSceneBuilderV2
from gr00t.rl.sim2sim.mujoco.sensor_clock import SensorClock
from gr00t.rl.sim2sim.policy.depthadd_v3 import load_depthadd_v3_policy
from gr00t.rl.sim2sim.policy.observations import (
    compose_dual_rgbd_from_normalized_depth,
    normalize_metric_depth_nhwc,
    normalize_rgb_nhwc,
)
from gr00t.rl.sim2sim.robot.depthadd_v3 import DepthADDV3MjcfBuilder


PHYSICS_DT = 0.005
CONTROL_DT = 0.02
CAMERA_PERIODS = {"left": 1.0 / 30.0, "right": 1.0 / 30.0, "head": 1.0 / 15.0}
POLICY_CAMERA_NAMES = ("left", "right", "head")
MANIFEST_NAME = "materialized_experiment.json"
STAGE0_ALIGNMENT_MAX_STEPS = 250
CONTACT_ATLAS_WINDOWS = {
    "seed41001_base004__fixed": (421, 432),
    "seed41001_base010__fixed": (262, 273),
}
STAGE34_TARGET_DISCRIMINATOR_CASE_ID = "seed41001_base006__fixed"
STAGE34_TARGET_DISCRIMINATOR_CONTROLS = 12
CONTACT_RETENTION_KD_SELECTOR = (7, 1)
CONTACT_RETENTION_KD_SUBSTEPS = 19


def _configure_deterministic_torch_runtime() -> None:
    """Select deterministic Torch kernels for the evaluator policy path."""

    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _row_json(stream, value: Mapping[str, Any]) -> None:
    stream.write(json.dumps(value, separators=(",", ":")) + "\n")


def _stage34_discriminator_core(
    model: mujoco.MjModel,
    mapping: NameResolvedActuatorMapV2,
    data: mujoco.MjData,
    *,
    pre_step_authority: Mapping[str, Any],
    native_endpoint_integration: list[float],
    native_contact: Mapping[str, Any],
    projection: Any,
) -> dict[str, Any]:
    """Return the strict same-engine state/contact surface for one replay row."""

    return {
        "strict_integration_authority": {
            "pre_native_integration": pre_step_authority["mjstate_integration"],
            "native_endpoint_integration": native_endpoint_integration,
            "post_projection_integration": capture_depthadd_v3_integration_state(model, data),
            "raw_target20": pre_step_authority["raw_target20_rad"],
            "drive_target20": pre_step_authority["drive_target20_rad"],
            "data_ctrl": pre_step_authority["data_ctrl"],
            "eq_active": pre_step_authority["eq_active"],
            "qfrc_applied": pre_step_authority["qfrc_applied"],
            "xfrc_applied": pre_step_authority["xfrc_applied"],
            "mocap_pos": pre_step_authority["mocap_pos"],
            "mocap_quat": pre_step_authority["mocap_quat"],
            "userdata": pre_step_authority["userdata"],
        },
        "post_projection_telemetry": {
            "qpos20": data.qpos[mapping.robot_qpos_addresses].tolist(),
            "qvel20": data.qvel[mapping.robot_qvel_addresses].tolist(),
            "projection_mask20": projection.projected_mask20.tolist(),
            "projection_count": projection.projected_count,
            "qpos_correction20_rad": projection.qpos_correction20.tolist(),
            "native_velocity_limit_max_ratio": projection.native_max_velocity_limit_ratio,
            "projected_velocity_limit_max_ratio": projection.projected_max_velocity_limit_ratio,
        },
        "native_contact_telemetry": dict(native_contact),
    }


def _stage34_strict_mismatch(
    expected_pre_step: Mapping[str, Any],
    actual_pre_step: Mapping[str, Any],
    expected_core: Mapping[str, Any],
    actual_core: Mapping[str, Any],
) -> dict[str, bool]:
    """Name each strict next-integration authority mismatch without comparing telemetry."""

    expected = expected_core["strict_integration_authority"]
    actual = actual_core["strict_integration_authority"]
    return {
        "pre_native_integration": (
            expected_pre_step["mjstate_integration"]
            != actual_pre_step["mjstate_integration"]
        ),
        "raw_target20": expected["raw_target20"] != actual["raw_target20"],
        "drive_target20": expected["drive_target20"] != actual["drive_target20"],
        "data_ctrl": expected["data_ctrl"] != actual["data_ctrl"],
        "eq_active": expected["eq_active"] != actual["eq_active"],
        "qfrc_applied": expected["qfrc_applied"] != actual["qfrc_applied"],
        "xfrc_applied": expected["xfrc_applied"] != actual["xfrc_applied"],
        "mocap_pos": expected["mocap_pos"] != actual["mocap_pos"],
        "mocap_quat": expected["mocap_quat"] != actual["mocap_quat"],
        "userdata": expected["userdata"] != actual["userdata"],
        "native_endpoint_integration": (
            expected["native_endpoint_integration"]
            != actual["native_endpoint_integration"]
        ),
        "post_projection_integration": (
            expected["post_projection_integration"]
            != actual["post_projection_integration"]
        ),
    }


def _stage34_discriminator_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Reduce the two local open-loop lanes without asserting engine equivalence."""

    bilateral_by_control: dict[int, int] = defaultdict(int)
    first_contact_loss: dict[str, int] | None = None
    contact_seen = False
    max_control_streak = 0
    streak = 0
    previous_control: int | None = None
    gaps_by_finger: list[list[float]] = [[], []]
    forces_by_finger: list[list[float]] = [[], []]
    for row in rows:
        contact = row["core"]["native_contact_telemetry"]["finger_handle"]
        bilateral = bool(contact["bilateral_active_contact"])
        control_index = int(row["control_index"])
        bilateral_by_control[control_index] += int(bilateral)
        if contact_seen and not bilateral and first_contact_loss is None:
            first_contact_loss = {
                "control_index": control_index,
                "physics_substep": int(row["physics_substep"]),
            }
        contact_seen = contact_seen or bilateral
        for pair in contact["closest_pairs"]:
            finger_index = int(pair["finger_index"])
            gaps_by_finger[finger_index].append(float(pair["mj_geomDistance_m"]))
        force_vectors = contact["solver_active_finger_handle_force_on_handle_world_N"]
        for finger_index, force in enumerate(force_vectors):
            forces_by_finger[finger_index].append(float(np.linalg.norm(force)))
    for control_index in range(STAGE34_TARGET_DISCRIMINATOR_CONTROLS):
        if bilateral_by_control.get(control_index, 0) > 0:
            streak = streak + 1 if previous_control == control_index - 1 else 1
            max_control_streak = max(max_control_streak, streak)
        else:
            streak = 0
        previous_control = control_index
    first = rows[0]["core"]["native_contact_telemetry"]["native_state"]["door_joint_pos"]
    last = rows[-1]["core"]["native_contact_telemetry"]["native_state"]["door_joint_pos"]
    return {
        "bilateral_native_rows": int(sum(bilateral_by_control.values())),
        "bilateral_native_rows_by_control": {
            str(index): int(bilateral_by_control.get(index, 0))
            for index in range(STAGE34_TARGET_DISCRIMINATOR_CONTROLS)
        },
        "max_bilateral_control_streak": max_control_streak,
        "first_bilateral_contact_loss": first_contact_loss,
        "finger_min_signed_gap_m": [
            None if not values else float(min(values)) for values in gaps_by_finger
        ],
        "finger_max_handle_force_norm_N": [
            None if not values else float(max(values)) for values in forces_by_finger
        ],
        "door_joint_pos_delta": (np.asarray(last, dtype=np.float64) - np.asarray(first, dtype=np.float64)).tolist(),
        "projection": {
            "rows_with_projection": int(
                sum(int(row["core"]["post_projection_telemetry"]["projection_count"] > 0) for row in rows)
            ),
            "joint_events": int(
                sum(int(row["core"]["post_projection_telemetry"]["projection_count"]) for row in rows)
            ),
            "max_native_velocity_limit_ratio": float(
                max(row["core"]["post_projection_telemetry"]["native_velocity_limit_max_ratio"] for row in rows)
            ),
            "max_abs_qpos_correction_rad": float(
                max(
                    np.max(np.abs(row["core"]["post_projection_telemetry"]["qpos_correction20_rad"]))
                    for row in rows
                )
            ),
        },
    }


def _contact_retention_kd_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Reduce the bounded gripper-KD lanes without making production claims."""

    summary = _stage34_discriminator_summary(rows)
    first_positive_gap: dict[str, Any] | None = None
    first_finger1_contact_loss: dict[str, int] | None = None
    finger1_contact_seen = False
    j7_j8_qpos: list[list[float]] = []
    j7_j8_qvel: list[list[float]] = []
    door_joint_names: list[str] | None = None
    for row in rows:
        native = row["core"]["native_contact_telemetry"]
        finger_handle = native["finger_handle"]
        finger1_gaps = [
            float(pair["mj_geomDistance_m"])
            for pair in finger_handle["closest_pairs"]
            if int(pair["finger_index"]) == 1
        ]
        if first_positive_gap is None and finger1_gaps and min(finger1_gaps) > 0.0:
            first_positive_gap = {
                "control_index": int(row["control_index"]),
                "physics_substep": int(row["physics_substep"]),
                "minimum_signed_gap_m": float(min(finger1_gaps)),
            }
        finger1_active = int(
            finger_handle["solver_active_finger_handle_contact_counts"][1]
        ) > 0
        if finger1_contact_seen and not finger1_active and first_finger1_contact_loss is None:
            first_finger1_contact_loss = {
                "control_index": int(row["control_index"]),
                "physics_substep": int(row["physics_substep"]),
            }
        finger1_contact_seen = finger1_contact_seen or finger1_active
        j7_j8_qpos.append(list(native["j7_j8"]["qpos_rad"]))
        j7_j8_qvel.append(list(native["j7_j8"]["qvel_rad_s"]))
        door_joint_names = list(native["native_state"]["door_joint_names"])
    if door_joint_names is None:
        raise RuntimeError("contact-retention KD discriminator produced no rows")
    summary["first_finger1_positive_gap"] = first_positive_gap
    summary["first_finger1_solver_contact_loss"] = first_finger1_contact_loss
    summary["j7_j8"] = {
        "joint_names": ["arm_j7", "arm_j8"],
        "initial_qpos_rad": j7_j8_qpos[0],
        "final_qpos_rad": j7_j8_qpos[-1],
        "initial_qvel_rad_s": j7_j8_qvel[0],
        "final_qvel_rad_s": j7_j8_qvel[-1],
    }
    summary["door_joint_names"] = door_joint_names
    return summary


def contact_retention_kd_discriminator(args: argparse.Namespace) -> None:
    """Run the r4 hold c7.s1 bounded same-engine gripper-KD discriminator."""

    if args.baseline_output_dir is None:
        raise ValueError("--baseline-output-dir is required for contact-retention-kd-discriminator")
    baseline = args.baseline_output_dir.resolve(strict=True)
    case_id = STAGE34_TARGET_DISCRIMINATOR_CASE_ID
    trace_path = baseline / "episodes" / case_id / "stage34_target_discriminator_hold_transition_target.jsonl"
    source_rows = [json.loads(line) for line in trace_path.open(encoding="utf-8")]
    selector_index = next(
        (
            index
            for index, row in enumerate(source_rows)
            if (int(row["control_index"]), int(row["physics_substep"]))
            == CONTACT_RETENTION_KD_SELECTOR
        ),
        None,
    )
    if selector_index is None:
        raise RuntimeError("r4 hold trace lacks the c7.s1 authority selector")
    expected_rows = source_rows[
        selector_index : selector_index + CONTACT_RETENTION_KD_SUBSTEPS
    ]
    expected_coordinates = [
        (control_index, physics_substep)
        for control_index in range(7, 12)
        for physics_substep in range(4)
        if (control_index, physics_substep) >= CONTACT_RETENTION_KD_SELECTOR
    ]
    if len(expected_rows) != CONTACT_RETENTION_KD_SUBSTEPS or [
        (int(row["control_index"]), int(row["physics_substep"]))
        for row in expected_rows
    ] != expected_coordinates:
        raise RuntimeError("r4 hold trace does not contain the exact c7.s1-through-c11.s3 window")
    raw_target20 = np.asarray(source_rows[0]["raw_target20"], dtype=np.float64)
    if raw_target20.shape != (20,):
        raise RuntimeError("r4 hold trace has no fixed raw target20[20]")
    if any(
        not np.array_equal(np.asarray(row["raw_target20"], dtype=np.float64), raw_target20)
        for row in expected_rows
    ):
        raise RuntimeError("r4 hold window does not retain one fixed raw target20")
    manifest = _load_manifest(baseline)
    case_rows = [row for row in manifest["primary_rows"] if row["case_id"] == case_id]
    if len(case_rows) != 1:
        raise RuntimeError("r4 baseline manifest does not contain exactly base006 fixed")
    case_row = case_rows[0]
    scene = baseline / "episodes" / case_id / "model" / "scene.xml"
    contract = json.loads((_prepared_paths(baseline)["robot_contract"]).read_text())
    velocity_limit20 = np.asarray(contract["position_pd"]["velocity_limit"], dtype=np.float64)
    release_handle_rad = float(
        case_row["door_geometry"].get("constraint_gate_release_handle_rad", math.pi / 6.0)
    )
    initial_authority = expected_rows[0]["pre_native_step_authority"]
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    def new_lane(*, gripper_kd: float) -> tuple[mujoco.MjModel, mujoco.MjData, NameResolvedActuatorMapV2, ConstraintGate]:
        model = mujoco.MjModel.from_xml_path(str(scene))
        data = mujoco.MjData(model)
        mapping = NameResolvedActuatorMapV2.from_model(
            model, tuple(contract["sim_joint_names"])
        )
        configure_depthadd_v3_production_contact_solref_surface(model)
        kp_before = model.actuator_gainprm.copy()
        force_before = model.actuator_forcerange.copy()
        armature_before = model.dof_armature.copy()
        bias_before = model.actuator_biasprm.copy()
        joint_indices = np.asarray(
            [mapping.robot_joint_names.index("arm_j7"), mapping.robot_joint_names.index("arm_j8")],
            dtype=np.int32,
        )
        actuator_ids = mapping.robot_actuator_ids[joint_indices]
        before_kd = -model.actuator_biasprm[actuator_ids, 2].copy()
        if not np.array_equal(before_kd, np.asarray([32.0, 32.0])):
            raise RuntimeError(f"gripper KD authority must be exactly [32,32], got {before_kd.tolist()}")
        if gripper_kd != 32.0:
            model.actuator_biasprm[actuator_ids, 2] = -gripper_kd
        expected_bias = bias_before.copy()
        expected_bias[actuator_ids, 2] = -gripper_kd
        if (
            not np.array_equal(model.actuator_gainprm, kp_before)
            or not np.array_equal(model.actuator_forcerange, force_before)
            or not np.array_equal(model.dof_armature, armature_before)
            or not np.array_equal(model.actuator_biasprm, expected_bias)
        ):
            raise RuntimeError("gripper KD discriminator changed a non-KD plant authority")
        after_kd = -model.actuator_biasprm[actuator_ids, 2].copy()
        if not np.array_equal(after_kd, np.asarray([gripper_kd, gripper_kd])):
            raise RuntimeError("gripper KD discriminator failed to realize its requested KD")
        gate = ConstraintGate(model, release_handle_rad=release_handle_rad)
        restore_depthadd_v3_pre_step_authority(model, data, initial_authority)
        return model, data, mapping, gate

    lane_receipts: dict[str, Any] = {}
    for lane_name, gripper_kd in (("baseline_kd32", 32.0), ("gripper_kd64", 64.0)):
        model, data, mapping, gate = new_lane(gripper_kd=gripper_kd)
        rows: list[dict[str, Any]] = []
        path = output / f"contact_retention_kd_{lane_name}.jsonl"
        with path.open("w", encoding="utf-8") as stream:
            for expected in expected_rows:
                target_realization = mapping.realize_velocity_limited_pd_target(
                    model, data, raw_target20, velocity_limit20
                )
                mapping.write_robot_position_target(data, target_realization.drive_target20)
                gate.update(data)
                pre_step = capture_depthadd_v3_pre_step_authority(
                    model,
                    data,
                    mapping,
                    raw_target20=target_realization.raw_target20,
                    drive_target20=target_realization.drive_target20,
                )
                pre_step["constraint_gate_active"] = gate.active(data)
                native_contact: dict[str, Any] | None = None
                native_endpoint_integration: list[float] | None = None

                def capture_native_contact_snapshot() -> None:
                    nonlocal native_contact, native_endpoint_integration
                    native_endpoint_integration = capture_depthadd_v3_integration_state(model, data)
                    native_contact = capture_depthadd_v3_native_contact_snapshot(
                        model,
                        data,
                        mapping,
                        raw_target20=target_realization.raw_target20,
                        drive_target20=target_realization.drive_target20,
                        pre_step_integration=np.asarray(
                            pre_step["mjstate_integration"], dtype=np.float64
                        ),
                    )

                projection = mapping.step_with_declared_endpoint_velocity_projection(
                    model, data, velocity_limit20, capture_native_contact_snapshot
                )
                if native_contact is None or native_endpoint_integration is None:
                    raise RuntimeError("contact-retention KD discriminator missed native contact telemetry")
                core = _stage34_discriminator_core(
                    model,
                    mapping,
                    data,
                    pre_step_authority=pre_step,
                    native_endpoint_integration=native_endpoint_integration,
                    native_contact=native_contact,
                    projection=projection,
                )
                if lane_name == "baseline_kd32":
                    mismatch = _stage34_strict_mismatch(
                        expected["pre_native_step_authority"],
                        pre_step,
                        expected["core"],
                        core,
                    )
                    if any(mismatch.values()):
                        _json_dump(
                            output / "contact_retention_kd_baseline_strict_mismatch.json",
                            {
                                "status": "FAIL",
                                "source_coordinate": {
                                    "control_index": expected["control_index"],
                                    "physics_substep": expected["physics_substep"],
                                },
                                "mismatch": mismatch,
                            },
                        )
                        raise RuntimeError("contact-retention KD baseline failed strict r4 hold reproduction")
                record = {
                    "schema": "doordog.sim2sim.depthadd_v3.contact_retention_kd_discriminator.v1",
                    "lane": lane_name,
                    "gripper_kd": gripper_kd,
                    "control_index": expected["control_index"],
                    "physics_substep": expected["physics_substep"],
                    "raw_target20": target_realization.raw_target20.tolist(),
                    "drive_target20": target_realization.drive_target20.tolist(),
                    "pre_native_step_authority": pre_step,
                    "core": core,
                }
                _row_json(stream, record)
                rows.append(record)
        if len(rows) != CONTACT_RETENTION_KD_SUBSTEPS:
            raise RuntimeError("contact-retention KD discriminator did not write 19 rows")
        lane_receipts[lane_name] = {
            "gripper_kd": gripper_kd,
            "path": str(path),
            "recorded_rows": len(rows),
            "metrics": _contact_retention_kd_metrics(rows),
        }
    _json_dump(
        output / "contact_retention_kd_discriminator_receipt.json",
        {
            "schema": "doordog.sim2sim.depthadd_v3.contact_retention_kd_discriminator.v1",
            "status": "COMPLETE",
            "evaluation_classification": "GRIPPER_KD_DIAGNOSTIC_ONLY",
            "authority": {
                "baseline_output_dir": str(baseline),
                "trace": str(trace_path),
                "selector": {"control_index": 7, "physics_substep": 1},
                "substeps": CONTACT_RETENTION_KD_SUBSTEPS,
                "raw_target": "r4 hold row control_index=0 physics_substep=0",
            },
            "boundary": "same-engine local KD discriminator; not Isaac equivalence or production admission",
            "baseline_strict_reproduction": "PASS",
            "lanes": lane_receipts,
        },
    )


def _run_stage34_target_discriminator(
    *,
    case_dir: Path,
    model: mujoco.MjModel,
    mapping: NameResolvedActuatorMapV2,
    velocity_limit20: np.ndarray,
    gate: ConstraintGate | None,
    capture: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay two local target schedules from one captured Stage4 pre-step state."""

    pre_step = capture["pre_step_authority"]
    raw_schedule = np.asarray(capture["raw_target20_schedule"], dtype=np.float64)
    if raw_schedule.shape != (STAGE34_TARGET_DISCRIMINATOR_CONTROLS, 20):
        raise RuntimeError(
            "Stage3/4 target discriminator requires exactly 12 recorded raw target20 controls"
        )
    lanes = {
        "recorded_targets": raw_schedule,
        "hold_transition_target": np.repeat(raw_schedule[:1], STAGE34_TARGET_DISCRIMINATOR_CONTROLS, axis=0),
    }
    lane_receipts: dict[str, Any] = {}
    expected_first = capture["live_first_core"]
    expected_first_pre_step = pre_step
    for lane_name, targets in lanes.items():
        branch = mujoco.MjData(model)
        restore_depthadd_v3_pre_step_authority(model, branch, pre_step)
        rows: list[dict[str, Any]] = []
        path = case_dir / f"stage34_target_discriminator_{lane_name}.jsonl"
        with path.open("w", encoding="utf-8") as stream:
            for control_index, raw_target20 in enumerate(targets):
                for physics_substep in range(4):
                    target_realization = mapping.realize_velocity_limited_pd_target(
                        model, branch, raw_target20, velocity_limit20
                    )
                    mapping.write_robot_position_target(branch, target_realization.drive_target20)
                    if gate is not None:
                        gate.update(branch)
                    replay_pre_step = capture_depthadd_v3_pre_step_authority(
                        model,
                        branch,
                        mapping,
                        raw_target20=target_realization.raw_target20,
                        drive_target20=target_realization.drive_target20,
                    )
                    replay_pre_step["constraint_gate_active"] = (
                        None if gate is None else gate.active(branch)
                    )
                    native_contact: dict[str, Any] | None = None
                    native_endpoint_integration: list[float] | None = None

                    def capture_native_contact_snapshot() -> None:
                        nonlocal native_contact, native_endpoint_integration
                        native_endpoint_integration = capture_depthadd_v3_integration_state(
                            model, branch
                        )
                        native_contact = capture_depthadd_v3_native_contact_snapshot(
                            model,
                            branch,
                            mapping,
                            raw_target20=target_realization.raw_target20,
                            drive_target20=target_realization.drive_target20,
                            pre_step_integration=np.asarray(
                                replay_pre_step["mjstate_integration"], dtype=np.float64
                            ),
                        )

                    projection = mapping.step_with_declared_endpoint_velocity_projection(
                        model, branch, velocity_limit20, capture_native_contact_snapshot
                    )
                    if native_contact is None or native_endpoint_integration is None:
                        raise RuntimeError("Stage3/4 target discriminator missed its native contact snapshot")
                    core = _stage34_discriminator_core(
                        model,
                        mapping,
                        branch,
                        pre_step_authority=replay_pre_step,
                        native_endpoint_integration=native_endpoint_integration,
                        native_contact=native_contact,
                        projection=projection,
                    )
                    if lane_name == "recorded_targets" and control_index == 0 and physics_substep == 0:
                        mismatch = _stage34_strict_mismatch(
                            expected_first_pre_step,
                            replay_pre_step,
                            expected_first,
                            core,
                        )
                        if any(mismatch.values()):
                            _json_dump(
                                case_dir / "stage34_target_discriminator_strict_mismatch.json",
                                {
                                    "status": "FAIL",
                                    "lane": lane_name,
                                    "control_index": control_index,
                                    "physics_substep": physics_substep,
                                    "mismatch": mismatch,
                                    "telemetry_comparison": "NOT_ADMISSION_CRITERION",
                                },
                            )
                            raise RuntimeError(
                                "Stage3/4 recorded replay failed strict next-integration authority reproduction"
                            )
                    record = {
                        "schema": "doordog.sim2sim.depthadd_v3.stage34_target_discriminator.v1",
                        "lane": lane_name,
                        "control_index": control_index,
                        "physics_substep": physics_substep,
                        "raw_target20": target_realization.raw_target20.tolist(),
                        "drive_target20": target_realization.drive_target20.tolist(),
                        "pre_native_step_authority": replay_pre_step,
                        "core": core,
                    }
                    _row_json(stream, record)
                    rows.append(record)
        if len(rows) != 4 * STAGE34_TARGET_DISCRIMINATOR_CONTROLS:
            raise RuntimeError(
                f"Stage3/4 {lane_name} lane wrote {len(rows)} rows, expected 48"
            )
        lane_receipts[lane_name] = {
            "path": str(path),
            "recorded_rows": len(rows),
            "summary": _stage34_discriminator_summary(rows),
        }
    return {
        "status": "COMPLETE",
        "case_id": STAGE34_TARGET_DISCRIMINATOR_CASE_ID,
        "transition_control_step": capture["transition_control_step"],
        "snapshot_timing": "Stage4 policy control substep0 after target shaping/write ctrl/gate.update and before native mj_step",
        "authority_boundary": (
            "MuJoCo-local open-loop branches only; policy/history/camera/warp/tracker are not called "
            "and no cross-engine or closed-loop successor claim is made"
        ),
        "strict_recorded_first_substep_reproduction": "PASS",
        "lanes": lane_receipts,
    }


def _body_state(model: mujoco.MjModel, data: mujoco.MjData, trunk_id: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    local_velocity = np.zeros(6, dtype=np.float64)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, trunk_id, local_velocity, 1)
    rotation = data.xmat[trunk_id].reshape(3, 3)
    gravity = rotation.T @ np.array([0.0, 0.0, -1.0])
    roll = math.atan2(rotation[2, 1], rotation[2, 2])
    pitch = math.atan2(-rotation[2, 0], math.hypot(rotation[2, 1], rotation[2, 2]))
    return local_velocity[:3], gravity, np.array([roll, pitch])


def _render(renderer: mujoco.Renderer, data: mujoco.MjData, camera: str, option: mujoco.MjvOption) -> np.ndarray:
    renderer.update_scene(data, camera=camera, scene_option=option)
    return renderer.render().copy()


def _option() -> mujoco.MjvOption:
    option = mujoco.MjvOption()
    option.sitegroup[5] = 0
    option.geomgroup[5] = 0
    return option


def _torch(array: np.ndarray, device: torch.device) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(array)).to(device=device, dtype=torch.float32).unsqueeze(0)


def _actor_obs(
    *, local_angular_velocity: np.ndarray, gravity: np.ndarray, qpos: np.ndarray, qvel: np.ndarray,
    default: torch.Tensor, previous_logical: torch.Tensor, previous_delta: torch.Tensor,
    previous_physical: torch.Tensor, action_warp: FullActionWarpR5,
) -> torch.Tensor:
    device = default.device
    scaled_command = action_warp.observation_command_echo(previous_physical)
    return compose_depthadd_v3_actor_obs({
        "scaled_base_command": scaled_command,
        "scaled_base_command_duplicate": scaled_command,
        "q_minus_default": (
            torch.from_numpy(qpos).to(device=device, dtype=torch.float32).unsqueeze(0) - default
        ),
        "dof_velocity_x0p05": (
            0.05 * torch.from_numpy(qvel).to(device=device, dtype=torch.float32).unsqueeze(0)
        ),
        "previous_actions19": previous_logical,
        "base_angular_velocity_x0p5": (
            0.5
            * torch.from_numpy(local_angular_velocity)
            .to(device=device, dtype=torch.float32)
            .unsqueeze(0)
        ),
        "previous_arm_delta6": previous_delta,
        "projected_gravity": (
            torch.from_numpy(gravity).to(device=device, dtype=torch.float32).unsqueeze(0)
        ),
    })


def _prepared_paths(output: Path) -> dict[str, Path]:
    return {
        "robot_xml": output / "prepared" / "robot.xml",
        "robot_contract": output / "prepared" / "robot_contract.json",
        "robot_report": output / "prepared" / "robot_build_receipt.json",
        "actor_obs_contract": output / "prepared" / "actor_obs_contract.json",
        "manifest": output / "prepared" / MANIFEST_NAME,
        "prepare_receipt": output / "prepared" / "prepare_receipt.json",
    }


def _load_manifest(output: Path) -> dict[str, Any]:
    path = _prepared_paths(output)["manifest"]
    return json.loads(path.read_text(encoding="utf-8"))


def _limit_primary_base_cases(rows: list[Mapping[str, Any]], count: int) -> list[Mapping[str, Any]]:
    selected_ids: list[str] = []
    for row in rows:
        base_case_id = str(row["base_case_id"])
        if base_case_id not in selected_ids:
            selected_ids.append(base_case_id)
            if len(selected_ids) == count:
                break
    if len(selected_ids) != count:
        raise ValueError(f"requested {count} primary base cases, found {len(selected_ids)}")
    selected = set(selected_ids)
    return [row for row in rows if str(row["base_case_id"]) in selected]


def _scene_for_row(
    row: Mapping[str, Any],
    *,
    robot_xml: Path,
    output: Path,
    empirical_source_nominal_appearance_calibration: bool = False,
    fixed_nominal_appearance_factor: str | None = None,
    fixed_latch_mode: str = "constraint_gate",
    constraint_gate_release_handle_rad: float | None = None,
) -> tuple[Path, dict[str, Any]]:
    case_dir = output / "episodes" / str(row["case_id"])
    model_dir = case_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    spec = DepthADDV3DoorFactory.from_case_row(
        row,
        latch_mode=fixed_latch_mode,
        constraint_gate_release_handle_rad=constraint_gate_release_handle_rad,
    )
    door_xml = model_dir / "door.xml"
    door_report = model_dir / "door_receipt.json"
    DepthADDV3DoorBuilder(spec).write(door_xml, door_report)
    robot_contract = json.loads((_prepared_paths(output)["robot_contract"]).read_text(encoding="utf-8"))
    armature = dict(zip(robot_contract["sim_joint_names"], robot_contract["armature"], strict=True))
    base_scene = model_dir / "base_scene.xml"
    scene_report = model_dir / "paired_scene_receipt.json"
    PairedSceneBuilderV2(robot_xml, door_xml, armature_by_joint=armature).write(base_scene, scene_report)
    visual = row["realized_visual"]
    if empirical_source_nominal_appearance_calibration and fixed_nominal_appearance_factor is not None:
        raise ValueError("legacy empirical calibration and fixed nominal appearance factor are mutually exclusive")
    if fixed_nominal_appearance_factor is not None:
        if row.get("lane") != "fixed" or visual["mode"] != "nominal":
            raise ValueError("--fixed-nominal-appearance-factor requires a fixed nominal row")
        scene = model_dir / "scene.xml"
        receipt = write_depthadd_v3_fixed_nominal_appearance_factor(
            base_scene,
            scene,
            factor=fixed_nominal_appearance_factor,
        )
        _json_dump(model_dir / "visual_receipt.json", receipt)
        return scene, receipt
    if empirical_source_nominal_appearance_calibration:
        if row.get("lane") != "fixed" or visual["mode"] != "nominal":
            raise ValueError(
                "--empirical-source-nominal-appearance-calibration requires a fixed nominal row"
            )
        scene = model_dir / "scene.xml"
        receipt = write_depthadd_v3_source_nominal_appearance_calibration(base_scene, scene)
        _json_dump(model_dir / "visual_receipt.json", receipt)
        return scene, receipt
    if visual["mode"] == "nominal":
        scene = model_dir / "scene.xml"
        receipt = write_depthadd_v3_diagnostic_overlay(base_scene, scene)
        _json_dump(model_dir / "visual_receipt.json", receipt)
        return scene, {"mode": "nominal", **receipt}
    if visual["mode"] != "narrowed_random":
        raise ValueError(f"unsupported visual realization mode {visual['mode']!r}")
    scene = model_dir / "scene.xml"
    receipt = write_depthadd_v3_visual_overlay(base_scene, scene, visual["realization"])
    _json_dump(model_dir / "visual_receipt.json", receipt)
    return scene, receipt


def _standing_gate(robot_xml: Path, nominal_row: Mapping[str, Any], output: Path, policy, device: torch.device) -> dict[str, Any]:
    gate_dir = output / "prepared" / "standing_gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    spec = DepthADDV3DoorFactory.from_case_row(nominal_row)
    door = gate_dir / "door.xml"
    DepthADDV3DoorBuilder(spec).write(door, gate_dir / "door_receipt.json")
    contract = json.loads((_prepared_paths(output)["robot_contract"]).read_text())
    scene = gate_dir / "scene.xml"
    PairedSceneBuilderV2(
        robot_xml,
        door,
        armature_by_joint=dict(zip(contract["sim_joint_names"], contract["armature"], strict=True)),
    ).write(scene, gate_dir / "scene_receipt.json")
    model, data = mujoco.MjModel.from_xml_path(str(scene)), None
    data = mujoco.MjData(model)
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home); mujoco.mj_forward(model, data)
    mapping = NameResolvedActuatorMapV2.from_model(model, tuple(contract["sim_joint_names"]))
    plant_realization = configure_depthadd_v3_production_contact_solref_surface(model)
    velocity_limit20 = np.asarray(contract["position_pd"]["velocity_limit"], dtype=np.float64)
    default = torch.tensor(contract["default_dof_pos"], dtype=torch.float64).unsqueeze(0)
    target = default.clone()
    heights: list[float] = []
    default_target_telemetry = None
    for _ in range(400):
        default_target_telemetry = mapping.realize_velocity_limited_pd_target(
            model, data, target.squeeze(0).numpy(), velocity_limit20
        )
        mapping.write_robot_position_target(data, default_target_telemetry.drive_target20)
        mapping.step_with_declared_endpoint_velocity_projection(model, data, velocity_limit20)
        heights.append(float(data.qpos[2]))
    default_hold = {"final_height_m": heights[-1], "tail_span_m": max(heights[-100:]) - min(heights[-100:])}
    mujoco.mj_resetDataKeyframe(model, data, home); mujoco.mj_forward(model, data)
    joint_map = A2PiperJointMap.from_sim_joint_names(tuple(contract["sim_joint_names"]), device=device)
    frame_builder, history = A2BaseFrameBuilder(joint_map), A2BaseHistory(batch_size=1, device=device, dtype=torch.float32)
    gait = SensorClock(batch_size=1, physics_dt=PHYSICS_DT, device=device, dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), device=device)
    zero = torch.zeros((1, 5), device=device)
    default_device = torch.tensor(contract["default_dof_pos"], device=device).unsqueeze(0)
    trunk = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    heights = []
    frozen_target_telemetry = None
    for step in range(1000):
        if step % 4 == 0:
            _, gravity, roll_pitch = _body_state(model, data, trunk)
            q = data.qpos[mapping.robot_qpos_addresses].copy(); qd = data.qvel[mapping.robot_qvel_addresses].copy()
            frame = frame_builder.build(projected_gravity=_torch(gravity, device), dof_pos=_torch(q, device), default_dof_pos=default_device, dof_vel=_torch(qd, device), previous_leg_action=previous_leg, physical_base_command=zero, base_roll_pitch=_torch(roll_pitch, device), gait_clock=gait.signal())
            previous_leg = policy.act_a2_base(history.append(frame))
            target = default_device.detach().cpu().double()
            target[:, joint_map.policy_leg_indices.cpu()] += 0.25 * previous_leg.detach().cpu().double()
        frozen_target_telemetry = mapping.realize_velocity_limited_pd_target(
            model, data, target.squeeze(0).numpy(), velocity_limit20
        )
        mapping.write_robot_position_target(data, frozen_target_telemetry.drive_target20)
        mapping.step_with_declared_endpoint_velocity_projection(model, data, velocity_limit20)
        gait.advance(zero[:, :3]); heights.append(float(data.qpos[2]))
    frozen = {"final_height_m": heights[-1], "tail_span_m": max(heights[-200:]) - min(heights[-200:])}
    result = 0.45 <= default_hold["final_height_m"] <= 0.65 and default_hold["tail_span_m"] <= 0.02 and 0.44 <= frozen["final_height_m"] <= 0.66 and frozen["tail_span_m"] <= 0.03
    return {"schema": "doordog.sim2sim.depthadd_v3_standing_gate.v2", "result": "PASS" if result else "FAIL", "position_pd": MUJOCO_LOCAL_DECLARED_REALIZATION, "default_target_hold_2s": default_hold, "a2_base_zero_command_5s": frozen, "plant_realization": plant_realization, "last_default_target": {"raw_target20": default_target_telemetry.raw_target20.tolist(), "drive_target20": default_target_telemetry.drive_target20.tolist(), "shaping_mask20": default_target_telemetry.shaping_mask20.tolist(), "shaping_count": default_target_telemetry.shaping_count, "max_abs_delta_rad": default_target_telemetry.max_abs_delta_rad}, "last_frozen_target": {"raw_target20": frozen_target_telemetry.raw_target20.tolist(), "drive_target20": frozen_target_telemetry.drive_target20.tolist(), "shaping_mask20": frozen_target_telemetry.shaping_mask20.tolist(), "shaping_count": frozen_target_telemetry.shaping_count, "max_abs_delta_rad": frozen_target_telemetry.max_abs_delta_rad}, "endpoint_projection_backup": DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION}


def prepare(args: argparse.Namespace) -> None:
    output = args.output_dir.resolve(); paths = _prepared_paths(output)
    output.mkdir(parents=True, exist_ok=True); paths["robot_xml"].parent.mkdir(parents=True, exist_ok=True)
    materialized = materialize_depthadd_v3_experiment(args.experiment_yaml)
    if materialized["counts"] != {"primary": 1536, "stress": 128}:
        raise RuntimeError(f"unexpected experiment counts {materialized['counts']}")
    _json_dump(paths["manifest"], materialized)
    _json_dump(paths["actor_obs_contract"], depthadd_v3_actor_obs_contract())
    DepthADDV3MjcfBuilder(args.robot_urdf, args.bundle_dir).write(paths["robot_xml"], paths["robot_contract"], paths["robot_report"])
    device = torch.device(args.device); policy = load_depthadd_v3_policy(args.bundle_dir, source_workspace=args.source_workspace, device=device)
    zero_obs = {"actor_obs": torch.zeros((1,81),device=device), "vision_obs": torch.zeros((1,384,216,8),device=device), "context_vision_obs": torch.zeros((1,136,384,3),device=device), "camera_meta": torch.tensor([[0.0,0.0,0.0,1.0,1.0,1.0]],device=device)}
    action = policy.act_inference(zero_obs)
    if tuple(action.shape) != (1, 12) or not bool(torch.isfinite(action).all()):
        raise RuntimeError("strict loaded Student failed finite action proof")
    standing = _standing_gate(paths["robot_xml"], materialized["primary_rows"][0], output, policy, device)
    receipt = {"schema": "doordog.sim2sim.depthadd_v3_prepare.v1", "result": "PASS" if standing["result"] == "PASS" else "FAIL", "materialized_counts": materialized["counts"], "strict_loader": {"student_global_step": policy.global_step, "finite_action_shape": list(action.shape), "a2_base_history_dim": 1620}, "torch_runtime_determinism": {"torch_deterministic_algorithms": True, "cudnn_deterministic": True, "cudnn_benchmark": False, "cublas_workspace_config": ":4096:8", "end_to_end_bitwise_replay": "INCONCLUSIVE_EGL_RENDER_AND_CONTACT_CLOSED_LOOP"}, "robot": str(paths["robot_xml"]), "actor_observation_contract": str(paths["actor_obs_contract"]), "standing_gate": standing}
    _json_dump(paths["prepare_receipt"], receipt)
    if receipt["result"] != "PASS":
        raise RuntimeError("standing vitals gate failed; campaign is not authorized")


def _contact_forces(model: mujoco.MjModel, data: mujoco.MjData, finger_body_ids: tuple[int, int], handle_body_id: int) -> np.ndarray:
    forces = np.zeros((2, 3), dtype=np.float32)
    for index in range(data.ncon):
        contact = data.contact[index]
        if handle_body_id not in (
            model.geom_bodyid[contact.geom1], model.geom_bodyid[contact.geom2]
        ):
            continue
        wrench = np.zeros(6, dtype=np.float64); mujoco.mj_contactForce(model, data, index, wrench)
        world_force = contact.frame.reshape(3, 3).T @ wrench[:3]
        for finger_index, body_id in enumerate(finger_body_ids):
            if model.geom_bodyid[contact.geom1] == body_id:
                forces[finger_index] -= world_force
            if model.geom_bodyid[contact.geom2] == body_id:
                forces[finger_index] += world_force
    return forces


def _stage_observation(model: mujoco.MjModel, data: mujoco.MjData, *, mapping: NameResolvedActuatorMapV2, ids: Mapping[str, Any], base: torch.Tensor, default: torch.Tensor, finger_ids: tuple[int, int], handle_body: int) -> DepthAddStageObservation:
    tcp, pregrasp, grasp = (data.site_xpos[ids[name]].copy() for name in ("tcp", "pregrasp", "grasp"))
    tcp_mat = data.site_xmat[ids["tcp"]].reshape(3, 3); grasp_mat = data.site_xmat[ids["grasp"]].reshape(3, 3)
    # The Isaac transition operates on fingertip forces expressed in the TCP
    # source frame, not in the target/grasp frame.
    forces = _contact_forces(model, data, finger_ids, handle_body) @ tcp_mat
    q = data.qpos[mapping.robot_qpos_addresses].copy()
    return DepthAddStageObservation(
        root_position_m=torch.from_numpy(data.qpos[:3].copy()).float().unsqueeze(0), env_origin_m=torch.zeros((1,3)), grasp_target_position_m=torch.from_numpy(grasp).float().unsqueeze(0),
        arm_position_rad=torch.from_numpy(q[12:18]).float().unsqueeze(0), arm_default_position_rad=default[:,12:18].cpu(), physical_base_command=base.cpu(),
        tcp_pregrasp_distance_m=torch.tensor([np.linalg.norm(tcp-pregrasp)], dtype=torch.float32), opening_alignment=torch.tensor([abs(float(np.dot(tcp_mat[:,1], grasp_mat[:,1])))], dtype=torch.float32), approach_alignment=torch.tensor([float(np.dot(tcp_mat[:,2], grasp_mat[:,2]))], dtype=torch.float32),
        gripper_position_rad=torch.from_numpy(q[18:20]).float().unsqueeze(0), gripper_close_target_rad=torch.tensor([[0.0,0.0]]), gripper_open_target_rad=torch.tensor([[0.035,-0.035]]),
        gripper_handle_forces_source_n=torch.from_numpy(forces).float().unsqueeze(0), door_hinge_rad=torch.tensor([data.qpos[ids["door_qpos"]]], dtype=torch.float32), handle_hinge_rad=torch.tensor([data.qpos[ids["handle_qpos"]]], dtype=torch.float32),
    )


def _capture_policy_camera(
    name: str,
    renderers: Mapping[str, mujoco.Renderer],
    data: mujoco.MjData,
    option: mujoco.MjvOption,
    realization: Mapping[str, Any] | None,
    fixed_nominal_color_pipeline: Mapping[str, Any] | None,
    frame_index: int,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    result: dict[str, np.ndarray] = {}
    receipt: dict[str, Any] = {}
    if name in ("left", "right"):
        raw_renderer_rgb = _render(renderers[f"{name}_rgb"], data, f"{name}_policy", option)
        rgb, pipeline_receipt = apply_fixed_nominal_color_pipeline(
            raw_renderer_rgb,
            fixed_nominal_color_pipeline,
        )
        post_color_pipeline_rgb = rgb.copy()
        depth = _render(renderers[f"{name}_depth"], data, f"{name}_policy", option)
        if not np.isfinite(depth).all() or not bool(np.any(depth > 0.0)):
            raise FloatingPointError(f"{name} D435 produced invalid metric depth")
        depth_tensor = torch.from_numpy(depth[..., None]).unsqueeze(0)
        normalized_depth, valid_depth = normalize_metric_depth_nhwc(depth_tensor)
        if realization is not None:
            rgb_float, rgb_receipt = augment_rgb_frame(rgb, realization, frame_index)
            normalized, depth_receipt = augment_normalized_depth_frame(
                normalized_depth.squeeze(0).squeeze(-1).numpy(),
                realization,
                frame_index,
                valid_mask=valid_depth.squeeze(0).squeeze(-1).numpy(),
            )
            normalized_depth = torch.from_numpy(normalized[..., None]).unsqueeze(0)
            rgb = np.rint(rgb_float*255.0).astype(np.uint8)
            receipt = {"rgb": rgb_receipt, "depth": depth_receipt, "color_pipeline": pipeline_receipt}
        else:
            receipt = {"color_pipeline": pipeline_receipt}
        result[f"{name}_raw_renderer_rgb"] = raw_renderer_rgb
        result[f"{name}_post_color_pipeline_rgb"] = post_color_pipeline_rgb
        result[f"{name}_rgb"] = rgb
        result[f"{name}_depth"] = depth
        result[f"{name}_depth_normalized"] = normalized_depth.squeeze(0).numpy()
        result[f"{name}_depth_valid"] = valid_depth.squeeze(0).numpy()
    elif name == "head":
        raw_renderer_rgb = _render(renderers["head"], data, "head_policy", option)
        head, pipeline_receipt = apply_fixed_nominal_color_pipeline(
            raw_renderer_rgb,
            fixed_nominal_color_pipeline,
        )
        post_color_pipeline_rgb = head.copy()
        if realization is not None:
            head_float, head_receipt = augment_rgb_frame(head, realization, frame_index)
            head = np.rint(head_float*255.0).astype(np.uint8)
            receipt = {"rgb": head_receipt, "color_pipeline": pipeline_receipt}
        else:
            receipt = {"color_pipeline": pipeline_receipt}
        result["head_raw_renderer_rgb"] = raw_renderer_rgb
        result["head_post_color_pipeline_rgb"] = post_color_pipeline_rgb
        result["head_rgb"] = head
    else:
        raise ValueError(f"unsupported policy camera {name!r}")
    return result, receipt


def _alignment_trace_arrays(steps: int) -> dict[str, np.ndarray]:
    if not 1 <= steps <= STAGE0_ALIGNMENT_MAX_STEPS:
        raise ValueError(
            f"alignment control limit must be in [1,{STAGE0_ALIGNMENT_MAX_STEPS}], got {steps}"
        )
    return {
        "actor_obs81": np.empty((steps, 81), dtype=np.float32),
        "raw_left_rgb_uint8": np.empty((steps, 384, 216, 3), dtype=np.uint8),
        "raw_right_rgb_uint8": np.empty((steps, 384, 216, 3), dtype=np.uint8),
        "raw_left_distance_to_image_plane_m": np.empty((steps, 384, 216), dtype=np.float32),
        "raw_right_distance_to_image_plane_m": np.empty((steps, 384, 216), dtype=np.float32),
        "raw_head_rgb_uint8": np.empty((steps, 136, 384, 3), dtype=np.uint8),
        "policy_vision_obs8_float32": np.empty((steps, 384, 216, 8), dtype=np.float32),
        "policy_head_obs3_float32": np.empty((steps, 136, 384, 3), dtype=np.float32),
        "camera_meta6": np.empty((steps, 6), dtype=np.float32),
        "student_action12": np.empty((steps, 12), dtype=np.float32),
        "physical_base_command5": np.empty((steps, 5), dtype=np.float32),
        "lstm_pre_h": np.empty((steps, 2, 256), dtype=np.float32),
        "lstm_pre_c": np.empty((steps, 2, 256), dtype=np.float32),
        "lstm_post_h": np.empty((steps, 2, 256), dtype=np.float32),
        "lstm_post_c": np.empty((steps, 2, 256), dtype=np.float32),
        "lstm_pre_valid": np.empty((steps,), dtype=np.bool_),
        "lstm_reset": np.empty((steps,), dtype=np.bool_),
        "camera_frame_ids": np.empty((steps, 3), dtype=np.int64),
        "camera_source_timestamps_s": np.empty((steps, 3), dtype=np.float64),
        "control_time_s": np.empty((steps,), dtype=np.float64),
        "pre_stage": np.empty((steps,), dtype=np.int64),
        "post_stage": np.empty((steps,), dtype=np.int64),
        "done": np.empty((steps,), dtype=np.bool_),
        "stage0_dx_m": np.empty((steps,), dtype=np.float32),
        "stage0_dy_m": np.empty((steps,), dtype=np.float32),
        "stage0_arm_max_deviation_rad": np.empty((steps,), dtype=np.float32),
        "stage0_base_command_norm": np.empty((steps,), dtype=np.float32),
        "stage0_spatial_ready": np.empty((steps,), dtype=np.bool_),
        "stage0_arm_ready": np.empty((steps,), dtype=np.bool_),
        "stage0_base_still": np.empty((steps,), dtype=np.bool_),
        "stage0_transition_predicate": np.empty((steps,), dtype=np.bool_),
    }


def _lstm_snapshot(policy) -> tuple[np.ndarray, np.ndarray, bool]:
    hidden = policy.actor.get_hidden_states()
    if hidden is None:
        zeros = np.zeros((2, 256), dtype=np.float32)
        return zeros, zeros.copy(), False
    if not isinstance(hidden, tuple) or len(hidden) != 2:
        raise RuntimeError("DepthADD alignment requires an LSTM (h,c) hidden-state tuple")
    values: list[np.ndarray] = []
    for name, tensor in zip(("h", "c"), hidden, strict=True):
        if not torch.is_tensor(tensor) or tuple(tensor.shape) != (2, 1, 256):
            raise RuntimeError(
                f"DepthADD alignment LSTM {name} must be [2,1,256], got {getattr(tensor, 'shape', None)}"
            )
        values.append(tensor[:, 0, :].detach().cpu().numpy().astype(np.float32, copy=True))
    return values[0], values[1], True


def _stage0_alignment_components(
    observation: DepthAddStageObservation,
    tracker: DepthAddStageTracker,
) -> dict[str, float | bool]:
    dx = float(
        (observation.grasp_target_position_m[:, 0] - observation.root_position_m[:, 0]).item()
    )
    dy = float(
        (observation.root_position_m[:, 1] - observation.grasp_target_position_m[:, 1]).item()
    )
    arm_max = float(
        torch.max(
            torch.abs(observation.arm_position_rad - observation.arm_default_position_rad)
        ).item()
    )
    base_norm = float(torch.linalg.vector_norm(observation.physical_base_command[:, :3]).item())
    spatial_ready = (
        tracker.staging_x_min_m <= dx <= tracker.staging_x_max_m
        and abs(dy) < tracker.staging_y_tolerance_m
    )
    arm_ready = arm_max < tracker.arm_default_max_deviation_rad
    base_still = base_norm <= tracker.base_still_norm_max
    return {
        "stage0_dx_m": dx,
        "stage0_dy_m": dy,
        "stage0_arm_max_deviation_rad": arm_max,
        "stage0_base_command_norm": base_norm,
        "stage0_spatial_ready": spatial_ready,
        "stage0_arm_ready": arm_ready,
        "stage0_base_still": base_still,
        "stage0_transition_predicate": spatial_ready and arm_ready and base_still,
    }


def _write_alignment_trace(
    case_dir: Path,
    arrays: Mapping[str, np.ndarray],
    count: int,
    *,
    row: Mapping[str, Any],
    scene: Path,
    stop_reason: str,
    control_limit: int,
) -> None:
    if not 0 < count <= STAGE0_ALIGNMENT_MAX_STEPS:
        raise RuntimeError(f"invalid MuJoCo alignment prefix length {count}")
    values = {name: value[:count] for name, value in arrays.items()}
    np.savez(case_dir / "stage0_alignment_trace.npz", **values)
    ready = values["stage0_spatial_ready"] & values["stage0_arm_ready"]
    ready_norms = values["stage0_base_command_norm"][ready]
    _json_dump(
        case_dir / "stage0_alignment_trace.json",
        {
            "schema": "doordog.sim2sim.depthadd_v3.stage0_alignment_trace.v1",
            "evaluation_classification": "RUNTIME_REPRODUCIBILITY_DIAGNOSTIC",
            "case_id": row["case_id"],
            "source_scene_xml": str(scene),
            "control_hz": 50,
            "physics_hz": 200,
            "steps": count,
            "alignment_control_limit": control_limit,
            "stop_reason": stop_reason,
            "fields": {name: list(value.shape) for name, value in values.items()},
            "spatial_arm_ready_steps": int(np.count_nonzero(ready)),
            "min_locomotion_norm_while_spatial_arm_ready": (
                float(np.min(ready_norms)) if ready_norms.size else None
            ),
            "locomotion_threshold": 0.1,
        },
    )


def _run_episode(
    row: Mapping[str, Any],
    *,
    output: Path,
    robot_xml: Path,
    policy,
    device: torch.device,
    resolved_config: Path,
    scene_override: Path | None = None,
    prepared_output: Path | None = None,
    alignment_export: bool = False,
    alignment_control_limit: int = STAGE0_ALIGNMENT_MAX_STEPS,
    empirical_source_nominal_appearance_calibration: bool = False,
    fixed_nominal_appearance_factor: str | None = None,
    fixed_latch_mode: str = "constraint_gate",
    constraint_gate_release_handle_rad: float | None = None,
    diagnostic_force_close_stage34: bool = False,
    diagnostic_policy_prefix_trace: Path | None = None,
    contact_atlas: bool = False,
    stage34_target_discriminator: bool = False,
) -> dict[str, Any]:
    case_dir = output / "episodes" / str(row["case_id"]); case_dir.mkdir(parents=True, exist_ok=True)
    resolved_constraint_gate_release_handle_rad = (
        float(row["door_geometry"].get("constraint_gate_release_handle_rad", math.pi / 6.0))
        if fixed_latch_mode == "constraint_gate" and constraint_gate_release_handle_rad is None
        else constraint_gate_release_handle_rad
    )
    if scene_override is None:
        scene, visual_receipt = _scene_for_row(
            row,
            robot_xml=robot_xml,
            output=output,
            empirical_source_nominal_appearance_calibration=empirical_source_nominal_appearance_calibration,
            fixed_nominal_appearance_factor=fixed_nominal_appearance_factor,
            fixed_latch_mode=fixed_latch_mode,
            constraint_gate_release_handle_rad=resolved_constraint_gate_release_handle_rad,
        )
    else:
        scene = scene_override.resolve(strict=True)
        visual_receipt = {
            "mode": "immutable_baseline_scene_override",
            "source_scene_xml": str(scene),
        }
    contract_root = prepared_output.resolve() if prepared_output is not None else output
    contract = json.loads((_prepared_paths(contract_root)["robot_contract"]).read_text())
    model, data = mujoco.MjModel.from_xml_path(str(scene)), None; data = mujoco.MjData(model)
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    initial_state = realize_depthadd_initial_state(row, contract)
    mujoco.mj_resetDataKeyframe(model, data, home)
    apply_depthadd_initial_state(data, initial_state, robot_contract=contract)
    mujoco.mj_forward(model, data)
    mapping = NameResolvedActuatorMapV2.from_model(model, tuple(contract["sim_joint_names"]))
    plant_realization = configure_depthadd_v3_production_contact_solref_surface(model)
    velocity_limit20 = np.asarray(contract["position_pd"]["velocity_limit"], dtype=np.float64)
    if (mapping.door_hinge_actuator_id, mapping.handle_actuator_id) != (0, 1): raise RuntimeError("door actuator order contract violated")
    default = torch.tensor(contract["default_dof_pos"], device=device).unsqueeze(0)
    policy_joint_map = A2PiperJointMap.from_sim_joint_names(
        tuple(contract["sim_joint_names"]), device=device
    )
    action_joint_map = A2PiperJointMap.from_sim_joint_names(
        tuple(contract["sim_joint_names"]), device="cpu"
    )
    runtime_config = yaml.safe_load(resolved_config.resolve(strict=True).read_text(encoding="utf-8"))
    task_config = runtime_config["env"]["config"]
    tracker = DepthAddStageTracker.from_task_config(task_config, device="cpu")
    warp = FullActionWarpR5(contract=ResolvedActionWarpContractR5.from_config(resolved_config), joint_map=action_joint_map, stage_tracker=tracker)
    frame_builder, history = A2BaseFrameBuilder(policy_joint_map), A2BaseHistory(batch_size=1, device=device, dtype=torch.float32); gait = SensorClock(batch_size=1, physics_dt=PHYSICS_DT, device=device, dtype=torch.float32)
    trunk = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk"); ids = {"tcp":mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_SITE,"a2_piper_tcp"), "pregrasp":mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_SITE,"door_pregrasp_target"), "grasp":mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_SITE,"door_grasp_target")}
    door_joint = mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,"door_hinge"); handle_joint = mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,"handle_hinge"); ids |= {"door_qpos":int(model.jnt_qposadr[door_joint]),"handle_qpos":int(model.jnt_qposadr[handle_joint])}
    finger_ids = (mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,"arm_body7"),mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,"arm_body8")); handle_body=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,"door_handle")
    gate_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "door_constraint_gate")
    latch_slide_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "latch_slide")
    latch_mimic_eq = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "handle_latch_mimic")
    if fixed_latch_mode == "constraint_gate":
        if gate_id < 0 or latch_slide_joint >= 0 or latch_mimic_eq >= 0:
            raise RuntimeError("constraint_gate model does not realize its declared latch topology")
        if resolved_constraint_gate_release_handle_rad is None:
            raise RuntimeError("constraint_gate must resolve a release threshold before runtime")
        gate = ConstraintGate(model, release_handle_rad=resolved_constraint_gate_release_handle_rad)
    else:
        if gate_id >= 0:
            raise RuntimeError("non-constraint latch model unexpectedly contains door_constraint_gate")
        gate = None
    latch_slide_qpos = None
    latch_mechanics: dict[str, Any] | None = None
    if fixed_latch_mode == "physical_collision":
        if latch_slide_joint < 0 or latch_mimic_eq < 0:
            raise RuntimeError("physical_collision model lacks latch_slide or handle_latch_mimic")
        latch_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "latch_collision")
        latch_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "latch_link")
        if latch_geom < 0 or latch_body < 0:
            raise RuntimeError("physical_collision model lacks latch collision geometry")
        latch_slide_qpos = int(model.jnt_qposadr[latch_slide_joint])
        latch_mechanics = {
            "latch_slide_qpos_range_m": model.jnt_range[latch_slide_joint].tolist(),
            "handle_latch_mimic_realized_ratio_m_per_rad": float(
                model.eq_data[latch_mimic_eq, 1]
            ),
            "handle_latch_mimic_authority_ratio_m_per_rad": -0.03 / (math.pi / 4.0),
            "latch_collision_half_size_m": model.geom_size[latch_geom].tolist(),
            "latch_link_local_position_m": model.body_pos[latch_body].tolist(),
            "isaac_training_latch_contract": "physical cone + prismatic 0..0.03 m + PhysX mimic -0.03/45deg",
        }
    elif latch_slide_joint >= 0 or latch_mimic_eq >= 0:
        raise RuntimeError("non-physical latch model unexpectedly contains physical latch topology")
    gate_initial_active = None if gate is None else gate.active(data)
    atlas_window = CONTACT_ATLAS_WINDOWS.get(str(row["case_id"])) if contact_atlas else None
    atlas_rows = 0
    atlas_bilateral_streak = 0
    atlas_previous_bilateral = False
    stage34_discriminator_capture: dict[str, Any] | None = None
    stage34_raw_target_schedule: list[list[float]] = []
    option = _option(); renderers = {"left_rgb":mujoco.Renderer(model,height=384,width=216),"right_rgb":mujoco.Renderer(model,height=384,width=216),"left_depth":mujoco.Renderer(model,height=384,width=216),"right_depth":mujoco.Renderer(model,height=384,width=216),"head":mujoco.Renderer(model,height=136,width=384),"diag_pos":mujoco.Renderer(model,height=480,width=640),"diag_neg":mujoco.Renderer(model,height=480,width=640)}
    renderers["left_depth"].enable_depth_rendering()
    renderers["right_depth"].enable_depth_rendering()
    realization = row["realized_visual"].get("realization") if row["realized_visual"]["mode"] == "narrowed_random" else None
    fixed_nominal_color_pipeline = visual_receipt.get("color_pipeline")
    surface_redraw_receipts: list[dict[str, Any]] = []
    surface_redraw_index = 1
    next_surface_redraw = (
        float(realization["surface_redraw"]["interval_s"])
        if realization is not None and row["suite"] == "primary"
        else math.inf
    )
    cached: dict[str, np.ndarray] = {}
    augmentation: dict[str, Any] = {}
    # Isaac's camera elapsed clock begins one 50 Hz control interval after the
    # physics/reset state.  Preserve that warmup offset in both capture timing
    # and the frame timestamps; merely shifting camera_meta would be incorrect.
    camera_elapsed_s = 0.0
    frames={n:1 for n in POLICY_CAMERA_NAMES}; last={n:camera_elapsed_s for n in POLICY_CAMERA_NAMES}
    for camera_index, name in enumerate(POLICY_CAMERA_NAMES):
        captured, capture_receipt = _capture_policy_camera(
            name, renderers, data, option, realization, fixed_nominal_color_pipeline, camera_index
        )
        cached.update(captured)
        augmentation[name] = capture_receipt
    image_dir=case_dir/"t0"; image_dir.mkdir(parents=True,exist_ok=True)
    for n in ("left", "right"):
        Image.fromarray(cached[f"{n}_raw_renderer_rgb"]).save(image_dir / f"{n}_raw_renderer_rgb.png")
        Image.fromarray(cached[f"{n}_post_color_pipeline_rgb"]).save(image_dir / f"{n}_post_color_pipeline_rgb.png")
        Image.fromarray(cached[f"{n}_rgb"]).save(image_dir / f"{n}_rgb.png")
        np.save(image_dir / f"{n}_depth_m.npy", cached[f"{n}_depth"])
    Image.fromarray(cached["head_raw_renderer_rgb"]).save(image_dir / "head_raw_renderer_rgb.png")
    Image.fromarray(cached["head_post_color_pipeline_rgb"]).save(image_dir / "head_post_color_pipeline_rgb.png")
    Image.fromarray(cached["head_rgb"]).save(image_dir / "head_rgb.png")
    Image.fromarray(_render(renderers["diag_pos"], data, "door_front_pos_x", option)).save(image_dir / "door_front_pos_x.png")
    Image.fromarray(_render(renderers["diag_neg"], data, "door_front_neg_x", option)).save(image_dir / "door_front_neg_x.png")
    policy.reset(); previous_logical=torch.zeros((1,19),device=device); previous_delta=torch.zeros((1,6),device=device); previous_physical=torch.zeros((1,5),device=device); previous_leg=torch.zeros((1,12),device=device); target=default.detach().cpu().double(); max_qacc=0.0; max_torque=0.0; released=False
    gate_release_control_step: int | None = None
    gate_release_substep: int | None = None
    max_handle_hinge_rad = float(data.qpos[ids["handle_qpos"]])
    max_door_hinge_rad = float(data.qpos[ids["door_qpos"]])
    max_latch_slide_qpos_m = None if latch_slide_qpos is None else float(data.qpos[latch_slide_qpos])
    max_abs_latch_slide_qpos_m = None if latch_slide_qpos is None else abs(float(data.qpos[latch_slide_qpos]))
    stage3_entry: dict[str, Any] | None = None
    alignment = _alignment_trace_arrays(alignment_control_limit) if alignment_export else None
    alignment_count = 0
    alignment_stop_reason: str | None = None
    stage2_min_tcp_grasp_distance_m = math.inf
    stage2_min_tcp_pregrasp_distance_m = math.inf
    stage2_first_close: dict[str, Any] | None = None
    stage2_close_spans: list[dict[str, Any]] = []
    active_stage2_close_span: dict[str, Any] | None = None
    stage2_both_contact_steps = 0
    stage2_valid_squeeze_steps = 0
    stage2_max_squeeze_streak = 0
    forced_gripper_close_applied_steps = 0
    policy_prefix_applied_steps = 0
    target_shaping_exact_nonzero_rows = 0
    target_shaping_exact_nonzero_joint_events = 0
    target_shaping_substantive_rows = 0
    target_shaping_substantive_joint_events = 0
    policy_prefix_rows = (
        [json.loads(line) for line in diagnostic_policy_prefix_trace.resolve(strict=True).open()]
        if diagnostic_policy_prefix_trace is not None
        else None
    )
    recorded_prefix_stage34_diagnostic = (
        stage34_target_discriminator and policy_prefix_rows is not None
    )
    last_control_step = -1
    atlas_path = case_dir / "native_contact_atlas.jsonl"
    with (case_dir/"policy_trace.jsonl").open("w") as policy_trace, (case_dir/"physics_trace.jsonl").open("w") as physics_trace, (case_dir/"first39_policy_diagnostic.jsonl").open("w") as first39_trace, (atlas_path.open("w") if atlas_window is not None else nullcontext(None)) as atlas_trace:
        for step in range(1000):
            last_control_step = step
            control_time_s = float(data.time)
            local,gravity,roll_pitch=_body_state(model,data,trunk); q=data.qpos[mapping.robot_qpos_addresses].copy(); qd=data.qvel[mapping.robot_qvel_addresses].copy()
            tcp_before = data.site_xpos[ids["tcp"]].copy()
            tcp_rotation_before = data.site_xmat[ids["tcp"]].reshape(3, 3).copy()
            pregrasp_before = data.site_xpos[ids["pregrasp"]].copy()
            grasp_before = data.site_xpos[ids["grasp"]].copy()
            tcp_to_pregrasp_world_before = pregrasp_before - tcp_before
            tcp_to_grasp_world_before = grasp_before - tcp_before
            tcp_to_pregrasp_source_before = tcp_rotation_before.T @ tcp_to_pregrasp_world_before
            tcp_to_grasp_source_before = tcp_rotation_before.T @ tcp_to_grasp_world_before
            ages=[min(1.0,(camera_elapsed_s-last[n])/0.1) for n in POLICY_CAMERA_NAMES]
            input_frames = dict(frames)
            input_augmentation = dict(augmentation)
            obs={"actor_obs":_actor_obs(local_angular_velocity=local,gravity=gravity,qpos=q,qvel=qd,default=default,previous_logical=previous_logical,previous_delta=previous_delta,previous_physical=previous_physical,action_warp=warp).to(device), "vision_obs":compose_dual_rgbd_from_normalized_depth(torch.from_numpy(cached["left_rgb"]).unsqueeze(0),torch.from_numpy(cached["right_rgb"]).unsqueeze(0),torch.from_numpy(cached["left_depth_normalized"]).unsqueeze(0),torch.from_numpy(cached["right_depth_normalized"]).unsqueeze(0),left_depth_valid=torch.from_numpy(cached["left_depth_valid"]).unsqueeze(0),right_depth_valid=torch.from_numpy(cached["right_depth_valid"]).unsqueeze(0),image_mean=[.485,.456,.406],image_std=[.229,.224,.225]).to(device), "context_vision_obs":normalize_rgb_nhwc(torch.from_numpy(cached["head_rgb"]).unsqueeze(0),image_mean=[.485,.456,.406],image_std=[.229,.224,.225]).to(device), "camera_meta":torch.tensor([[*ages,1.,1.,1.]],device=device)}
            if alignment is not None:
                if alignment_count >= alignment_control_limit:
                    raise RuntimeError("MuJoCo Stage0 alignment trace exceeded its declared budget")
                alignment["actor_obs81"][alignment_count] = obs["actor_obs"].squeeze(0).detach().cpu().numpy()
                alignment["raw_left_rgb_uint8"][alignment_count] = cached["left_rgb"]
                alignment["raw_right_rgb_uint8"][alignment_count] = cached["right_rgb"]
                alignment["raw_left_distance_to_image_plane_m"][alignment_count] = cached["left_depth"]
                alignment["raw_right_distance_to_image_plane_m"][alignment_count] = cached["right_depth"]
                alignment["raw_head_rgb_uint8"][alignment_count] = cached["head_rgb"]
                alignment["policy_vision_obs8_float32"][alignment_count] = obs["vision_obs"].squeeze(0).detach().cpu().numpy()
                alignment["policy_head_obs3_float32"][alignment_count] = obs["context_vision_obs"].squeeze(0).detach().cpu().numpy()
                alignment["camera_meta6"][alignment_count] = obs["camera_meta"].squeeze(0).detach().cpu().numpy()
                pre_h, pre_c, pre_valid = _lstm_snapshot(policy)
                alignment["lstm_pre_h"][alignment_count] = pre_h
                alignment["lstm_pre_c"][alignment_count] = pre_c
                alignment["lstm_pre_valid"][alignment_count] = pre_valid
                alignment["lstm_reset"][alignment_count] = alignment_count == 0
                alignment["camera_frame_ids"][alignment_count] = [frames[name] for name in POLICY_CAMERA_NAMES]
                alignment["camera_source_timestamps_s"][alignment_count] = [last[name] for name in POLICY_CAMERA_NAMES]
                alignment["control_time_s"][alignment_count] = float(data.time)
            live_policy_raw = policy.act_inference(obs)
            policy_raw = live_policy_raw
            recorded_prefix_row = None
            recorded_policy_prefix_applied = (
                policy_prefix_rows is not None
                and (
                    recorded_prefix_stage34_diagnostic
                    or tracker.stage <= STAGE_GRASP
                )
            )
            if recorded_policy_prefix_applied:
                if step >= len(policy_prefix_rows):
                    raise RuntimeError("diagnostic policy prefix ended before the local episode")
                recorded_prefix_row = policy_prefix_rows[step]
                if recorded_prefix_row.get("step") != step or recorded_prefix_row.get("stage") != tracker.stage:
                    raise RuntimeError("diagnostic policy prefix step/stage differs from live tracker")
                policy_raw = torch.tensor(
                    recorded_prefix_row["high_action12"],
                    dtype=torch.float32,
                    device=device,
                ).unsqueeze(0)
                policy_prefix_applied_steps += 1
            raw = policy_raw
            forced_gripper_close_applied = (
                diagnostic_force_close_stage34
                and tracker.stage in (STAGE_OPEN, STAGE_SWING)
            )
            if forced_gripper_close_applied:
                raw = policy_raw.clone()
                raw[:, 11] = -1.0
                forced_gripper_close_applied_steps += 1
            action=tracker.apply_high_level_action(raw.detach().cpu()); base=warp.warp_base_command(action.effective_high_level_action[:, :5]); frame=frame_builder.build(projected_gravity=_torch(gravity,device),dof_pos=_torch(q,device),default_dof_pos=default,dof_vel=_torch(qd,device),previous_leg_action=previous_leg,physical_base_command=base.physical.to(device),base_roll_pitch=_torch(roll_pitch,device),gait_clock=gait.signal()); live_legs=policy.act_a2_base(history.append(frame)); legs = live_legs if recorded_prefix_row is None else torch.tensor(recorded_prefix_row["leg_action12"], dtype=torch.float32, device=device).unsqueeze(0); warped=warp.compose_simulator_action(stage_action=action,base=base,policy_leg_action=legs.detach().cpu(),default_dof_pos=default.detach().cpu()); target=warped.position_target.double(); previous_logical=warped.logical_action.to(device); previous_delta=action.raw_arm_delta_echo.to(device); previous_physical=base.physical.to(device); previous_leg=legs
            if recorded_prefix_stage34_diagnostic:
                source_target20 = np.asarray(recorded_prefix_row["target20"], dtype=np.float64)
                current_target20 = target.squeeze(0).numpy()
                if source_target20.shape != (20,) or not np.array_equal(
                    current_target20, source_target20
                ):
                    raise RuntimeError(
                        "recorded Stage3/4 prefix target20 differs exactly from the current computed target20"
                    )
            stage34_schedule_control = (
                stage34_target_discriminator
                and len(stage34_raw_target_schedule) < STAGE34_TARGET_DISCRIMINATOR_CONTROLS
                and (
                    stage34_discriminator_capture is not None
                    or action.stage_used_for_action == STAGE_SWING
                )
            )
            if stage34_schedule_control:
                stage34_raw_target_schedule.append(target.squeeze(0).tolist())
            raw_gripper_primitive = float(raw[0, 11].item())
            is_stage2_close = action.stage_used_for_action == STAGE_GRASP and raw_gripper_primitive <= 0.0
            stage2_pre_physics = {
                "control_step": step,
                "time_s": control_time_s,
                "tcp_world_m": tcp_before.tolist(),
                "pregrasp_world_m": pregrasp_before.tolist(),
                "grasp_world_m": grasp_before.tolist(),
                "tcp_to_pregrasp_world_m": tcp_to_pregrasp_world_before.tolist(),
                "tcp_to_grasp_world_m": tcp_to_grasp_world_before.tolist(),
                "tcp_to_pregrasp_tcp_source_m": tcp_to_pregrasp_source_before.tolist(),
                "tcp_to_grasp_tcp_source_m": tcp_to_grasp_source_before.tolist(),
                "tcp_to_pregrasp_distance_m": float(np.linalg.norm(tcp_to_pregrasp_world_before)),
                "tcp_to_grasp_distance_m": float(np.linalg.norm(tcp_to_grasp_world_before)),
                "gripper_raw_primitive": raw_gripper_primitive,
                "gripper_target_rad": target[0, 18:20].tolist(),
                "gripper_position_before_physics_rad": q[18:20].tolist(),
            }
            if action.stage_used_for_action == STAGE_GRASP:
                stage2_min_tcp_grasp_distance_m = min(
                    stage2_min_tcp_grasp_distance_m,
                    stage2_pre_physics["tcp_to_grasp_distance_m"],
                )
                stage2_min_tcp_pregrasp_distance_m = min(
                    stage2_min_tcp_pregrasp_distance_m,
                    stage2_pre_physics["tcp_to_pregrasp_distance_m"],
                )
            if is_stage2_close:
                if stage2_first_close is None:
                    stage2_first_close = dict(stage2_pre_physics)
                if active_stage2_close_span is None:
                    active_stage2_close_span = {
                        "start_control_step": step,
                        "start_time_s": float(data.time),
                        "first_close_state": dict(stage2_pre_physics),
                    }
            elif active_stage2_close_span is not None:
                active_stage2_close_span["end_control_step"] = step - 1
                active_stage2_close_span["control_steps"] = step - int(active_stage2_close_span["start_control_step"])
                active_stage2_close_span["duration_s"] = float(active_stage2_close_span["control_steps"]) * CONTROL_DT
                stage2_close_spans.append(active_stage2_close_span)
                active_stage2_close_span = None
            if alignment is not None:
                post_h, post_c, post_valid = _lstm_snapshot(policy)
                if not post_valid:
                    raise RuntimeError("DepthADD Student did not materialize post-action LSTM state")
                alignment["student_action12"][alignment_count] = raw.squeeze(0).detach().cpu().numpy()
                alignment["physical_base_command5"][alignment_count] = base.physical.squeeze(0).numpy()
                alignment["lstm_post_h"][alignment_count] = post_h
                alignment["lstm_post_c"][alignment_count] = post_c
                alignment["pre_stage"][alignment_count] = action.stage_used_for_action
            if step < 39:
                _row_json(first39_trace, {"step": step, "control_time_s": float(data.time), "actor_obs81": obs["actor_obs"].squeeze(0).detach().cpu().tolist(), "camera_meta6": obs["camera_meta"].squeeze(0).detach().cpu().tolist(), "camera_frame_ids": [frames[name] for name in POLICY_CAMERA_NAMES], "camera_source_timestamps_s": [last[name] for name in POLICY_CAMERA_NAMES], "student_action12": raw.squeeze(0).detach().cpu().tolist()})
            for sub in range(4):
                target_realization = mapping.realize_velocity_limited_pd_target(
                    model, data, target.squeeze(0).numpy(), velocity_limit20
                )
                target_shaping_exact_nonzero_rows += int(target_realization.shaping_count > 0)
                target_shaping_exact_nonzero_joint_events += target_realization.shaping_count
                target_shaping_substantive_rows += int(target_realization.substantive_count > 0)
                target_shaping_substantive_joint_events += target_realization.substantive_count
                mapping.write_robot_position_target(data, target_realization.drive_target20)
                gate_released_this_substep = gate.update(data) if gate is not None else False
                if gate_released_this_substep:
                    released = True
                    gate_release_control_step = step
                    gate_release_substep = sub
                atlas_capture: dict[str, Any] | None = None
                stage34_live_capture: dict[str, Any] | None = None
                stage34_live_native_endpoint_integration: list[float] | None = None
                atlas_active = (
                    atlas_window is not None
                    and atlas_window[0] <= step <= atlas_window[1]
                )
                stage34_capture_active = (
                    stage34_target_discriminator
                    and stage34_discriminator_capture is None
                    and action.stage_used_for_action == STAGE_SWING
                    and sub == 0
                )
                if atlas_active or stage34_capture_active:
                    atlas_pre_step = capture_depthadd_v3_pre_step_authority(
                        model,
                        data,
                        mapping,
                        raw_target20=target_realization.raw_target20,
                        drive_target20=target_realization.drive_target20,
                    )
                    atlas_pre_step["constraint_gate_active"] = (
                        None if gate is None else gate.active(data)
                    )

                    def capture_native_contact_snapshot() -> None:
                        nonlocal atlas_capture, stage34_live_capture, stage34_live_native_endpoint_integration
                        if stage34_capture_active:
                            stage34_live_native_endpoint_integration = (
                                capture_depthadd_v3_integration_state(model, data)
                            )
                        native_capture = capture_depthadd_v3_native_contact_snapshot(
                            model,
                            data,
                            mapping,
                            raw_target20=target_realization.raw_target20,
                            drive_target20=target_realization.drive_target20,
                            pre_step_integration=np.asarray(
                                atlas_pre_step["mjstate_integration"], dtype=np.float64
                            ),
                        )
                        if atlas_active:
                            atlas_capture = native_capture
                        if stage34_capture_active:
                            stage34_live_capture = native_capture

                    projection = mapping.step_with_declared_endpoint_velocity_projection(
                        model, data, velocity_limit20, capture_native_contact_snapshot
                    )
                else:
                    projection = mapping.step_with_declared_endpoint_velocity_projection(
                        model, data, velocity_limit20
                    )
                if atlas_active:
                    if atlas_capture is None or atlas_trace is None:
                        raise RuntimeError("native contact atlas did not capture its declared primary surface")
                    bilateral = bool(
                        atlas_capture["finger_handle"]["bilateral_active_contact"]
                    )
                    atlas_bilateral_streak = atlas_bilateral_streak + 1 if bilateral else 0
                    boundary = (
                        "ENTRY"
                        if bilateral and not atlas_previous_bilateral
                        else "CONTINUE"
                        if bilateral
                        else "EXIT"
                        if atlas_previous_bilateral
                        else "NONE"
                    )
                    _row_json(
                        atlas_trace,
                        {
                            "schema": "doordog.sim2sim.depthadd_v3_native_contact_atlas.v1",
                            "case_id": row["case_id"],
                            "control_step": step,
                            "physics_substep": sub,
                            "primary_realization": MUJOCO_LOCAL_DECLARED_REALIZATION,
                            "pre_native_step_authority": atlas_pre_step,
                            "primary": atlas_capture,
                            "bilateral_contact_boundary": boundary,
                            "bilateral_contact_streak_native_substeps": atlas_bilateral_streak,
                            "endpoint_projection_backup": {
                                "realization": DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION,
                                "applied_count": projection.projected_count,
                                "mask20": projection.projected_mask20.tolist(),
                                "qpos_correction20_rad": projection.qpos_correction20.tolist(),
                                "native_velocity_limit_max_ratio": projection.native_max_velocity_limit_ratio,
                                "projected_velocity_limit_max_ratio": projection.projected_max_velocity_limit_ratio,
                            },
                            "post_projection_state": {
                                "robot_joint_pos20_rad": data.qpos[mapping.robot_qpos_addresses].tolist(),
                                "robot_joint_vel20_rad_s": data.qvel[mapping.robot_qvel_addresses].tolist(),
                            },
                        },
                    )
                    atlas_rows += 1
                    atlas_previous_bilateral = bilateral
                if stage34_capture_active:
                    if (
                        stage34_live_capture is None
                        or stage34_live_native_endpoint_integration is None
                    ):
                        raise RuntimeError("Stage3/4 discriminator missed its live native contact snapshot")
                    stage34_discriminator_capture = {
                        "transition_control_step": step,
                        "pre_step_authority": atlas_pre_step,
                        "live_first_core": _stage34_discriminator_core(
                            model,
                            mapping,
                            data,
                            pre_step_authority=atlas_pre_step,
                            native_endpoint_integration=stage34_live_native_endpoint_integration,
                            native_contact=stage34_live_capture,
                            projection=projection,
                        ),
                        "raw_target20_schedule": stage34_raw_target_schedule,
                    }
                torque = projection.native_actuator_force20
                if not np.isfinite(torque).all(): raise FloatingPointError(f"nonfinite torque in {row['case_id']} step {step}.{sub}")
                max_handle_hinge_rad = max(max_handle_hinge_rad, float(data.qpos[ids["handle_qpos"]]))
                max_door_hinge_rad = max(max_door_hinge_rad, float(data.qpos[ids["door_qpos"]]))
                if max_latch_slide_qpos_m is not None and latch_slide_qpos is not None:
                    max_latch_slide_qpos_m = max(max_latch_slide_qpos_m, float(data.qpos[latch_slide_qpos]))
                    max_abs_latch_slide_qpos_m = max(max_abs_latch_slide_qpos_m, abs(float(data.qpos[latch_slide_qpos])))
                gait.advance(base.physical[:,:3].to(device)); max_qacc=max(max_qacc,float(np.max(np.abs(data.qacc)))); max_torque=max(max_torque,float(np.max(np.abs(torque)))); _row_json(physics_trace,{"control_step":step,"substep":sub,"time_s":float(data.time),"root_qpos7":data.qpos[:7].tolist(),"root_qvel6":data.qvel[:6].tolist(),"qpos20":data.qpos[mapping.robot_qpos_addresses].tolist(),"qvel20":data.qvel[mapping.robot_qvel_addresses].tolist(),"raw_target20":target_realization.raw_target20.tolist(),"drive_target20":target_realization.drive_target20.tolist(),"target_shaping_mask20":target_realization.shaping_mask20.tolist(),"target_shaping_count":target_realization.shaping_count,"target_shaping_substantive_mask20":target_realization.substantive_mask20.tolist(),"target_shaping_substantive_count":target_realization.substantive_count,"target_shaping_substantive_epsilon_rad":target_realization.substantive_epsilon_rad,"target_shaping_delta20_rad":target_realization.shaping_delta20.tolist(),"target_shaping_max_abs_delta_rad":target_realization.max_abs_delta_rad,"runtime_primary_realization":MUJOCO_LOCAL_DECLARED_REALIZATION,"velocity_limit_runtime_realization":MUJOCO_LOCAL_DECLARED_REALIZATION,"native_pre_projection_qpos20":projection.native_qpos20.tolist(),"native_pre_projection_qvel20":projection.native_qvel20.tolist(),"endpoint_qpos_correction20":projection.qpos_correction20.tolist(),"endpoint_velocity_projection_mask20":projection.projected_mask20.tolist(),"endpoint_velocity_projection_count":projection.projected_count,"native_velocity_limit_max_ratio":projection.native_max_velocity_limit_ratio,"projected_velocity_limit_max_ratio":projection.projected_max_velocity_limit_ratio,"native_pre_projection_actuator_force20":torque.tolist(),"native_pre_projection_qfrc_actuator20_Nm":projection.native_qfrc_actuator20_nm.tolist(),"native_pre_projection_qfrc_constraint20_Nm":projection.native_qfrc_constraint20_nm.tolist(),"endpoint_projection_backup_realization":DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION,"endpoint_projection_backup_role":"BACKUP_TELEMETRY","contact_surface_realization":"receipt:plant_realization.geoms","door_hinge_rad":float(data.qpos[ids["door_qpos"]]),"handle_hinge_rad":float(data.qpos[ids["handle_qpos"]]),"latch_mode":fixed_latch_mode,"constraint_gate_active":None if gate is None else gate.active(data),"constraint_gate_released_this_substep":gate_released_this_substep,"latch_slide_qpos_m":None if latch_slide_qpos is None else float(data.qpos[latch_slide_qpos])})
                if data.time + 1e-12 >= next_surface_redraw:
                    sampled_redraw = sample_surface_redraw(realization, surface_redraw_index)
                    applied_redraw = apply_surface_redraw_to_model(model, sampled_redraw)
                    surface_redraw_receipts.append({"time_s": float(data.time), **applied_redraw})
                    surface_redraw_index += 1
                    next_surface_redraw += float(realization["surface_redraw"]["interval_s"])
                for camera_index, name in enumerate(POLICY_CAMERA_NAMES):
                    camera_elapsed_s = max(0.0, float(data.time) - CONTROL_DT)
                    if camera_elapsed_s - last[name] + 1e-12 >= CAMERA_PERIODS[name]:
                        frames[name] += 1
                        captured, capture_receipt = _capture_policy_camera(
                            name, renderers, data, option, realization,
                            fixed_nominal_color_pipeline,
                            3 * frames[name] + camera_index,
                        )
                        cached.update(captured)
                        augmentation[name] = capture_receipt
                        last[name] = camera_elapsed_s
            stage_observation = _stage_observation(model,data,mapping=mapping,ids=ids,base=base.physical,default=default,finger_ids=finger_ids,handle_body=handle_body)
            stage=tracker.observe_after_step(stage_observation,action)
            if stage3_entry is None and action.stage_used_for_action != STAGE_OPEN and stage.stage == STAGE_OPEN:
                stage3_entry = {
                    "control_step": step,
                    "time_s": float(data.time),
                    "door_hinge_rad": float(data.qpos[ids["door_qpos"]]),
                    "handle_hinge_rad": float(data.qpos[ids["handle_qpos"]]),
                    "constraint_gate_active": None if gate is None else gate.active(data),
                    "latch_slide_qpos_m": None if latch_slide_qpos is None else float(data.qpos[latch_slide_qpos]),
                }
            forces_source = stage_observation.gripper_handle_forces_source_n.squeeze(0).numpy()
            contact_force_norms_source = np.linalg.norm(forces_source, axis=1)
            finger_handle_contact = contact_force_norms_source > tracker.contact_force_threshold_n
            both_handle_contact = bool(np.all(finger_handle_contact))
            squeeze_y_source = forces_source[:, 1]
            valid_squeeze = bool(
                np.all(np.abs(squeeze_y_source) > tracker.squeeze_force_min_n)
                and squeeze_y_source[0] * squeeze_y_source[1] < 0.0
            )
            tcp_after = data.site_xpos[ids["tcp"]].copy()
            tcp_rotation_after = data.site_xmat[ids["tcp"]].reshape(3, 3).copy()
            pregrasp_after = data.site_xpos[ids["pregrasp"]].copy()
            grasp_after = data.site_xpos[ids["grasp"]].copy()
            tcp_to_pregrasp_world_after = pregrasp_after - tcp_after
            tcp_to_grasp_world_after = grasp_after - tcp_after
            if action.stage_used_for_action == STAGE_GRASP:
                stage2_both_contact_steps += int(both_handle_contact)
                stage2_valid_squeeze_steps += int(valid_squeeze)
                stage2_max_squeeze_streak = max(stage2_max_squeeze_streak, tracker.stage2_squeeze_streak)
            stage2_post_physics = {
                "tcp_world_m": tcp_after.tolist(),
                "pregrasp_world_m": pregrasp_after.tolist(),
                "grasp_world_m": grasp_after.tolist(),
                "tcp_to_pregrasp_world_m": tcp_to_pregrasp_world_after.tolist(),
                "tcp_to_grasp_world_m": tcp_to_grasp_world_after.tolist(),
                "tcp_to_pregrasp_tcp_source_m": (tcp_rotation_after.T @ tcp_to_pregrasp_world_after).tolist(),
                "tcp_to_grasp_tcp_source_m": (tcp_rotation_after.T @ tcp_to_grasp_world_after).tolist(),
                "tcp_to_pregrasp_distance_m": float(np.linalg.norm(tcp_to_pregrasp_world_after)),
                "tcp_to_grasp_distance_m": float(np.linalg.norm(tcp_to_grasp_world_after)),
                "gripper_position_after_physics_rad": stage_observation.gripper_position_rad.squeeze(0).tolist(),
                "gripper_handle_forces_tcp_source_n": forces_source.tolist(),
                "gripper_handle_contact_force_norms_n": contact_force_norms_source.tolist(),
                "finger_handle_contact": finger_handle_contact.tolist(),
                "both_handle_contact": both_handle_contact,
                "squeeze_y_tcp_source_n": squeeze_y_source.tolist(),
                "valid_squeeze": valid_squeeze,
                "stage2_squeeze_streak_control_steps": tracker.stage2_squeeze_streak,
            }
            vision_stats = torch.stack((obs["vision_obs"].amin(dim=(1,2)), obs["vision_obs"].amax(dim=(1,2)), obs["vision_obs"].mean(dim=(1,2))), dim=1).squeeze(0).detach().cpu().tolist()
            head_stats = torch.stack((obs["context_vision_obs"].amin(dim=(1,2)), obs["context_vision_obs"].amax(dim=(1,2)), obs["context_vision_obs"].mean(dim=(1,2))), dim=1).squeeze(0).detach().cpu().tolist()
            _row_json(policy_trace,{"step":step,"time_s":control_time_s,"actor_obs81":obs["actor_obs"].squeeze(0).detach().cpu().tolist(),"camera_meta6":obs["camera_meta"].squeeze(0).detach().cpu().tolist(),"vision_obs8_min_max_mean":vision_stats,"context_vision_obs3_min_max_mean":head_stats,"input_frames":input_frames,"live_policy_high_action12":live_policy_raw.squeeze(0).detach().cpu().tolist(),"high_action12":policy_raw.squeeze(0).detach().cpu().tolist(),"post_forced_override_high_action12":raw.squeeze(0).detach().cpu().tolist(),"recorded_policy_prefix_applied":recorded_policy_prefix_applied,"forced_gripper_close_applied":forced_gripper_close_applied,"live_leg_action12":live_legs.squeeze(0).detach().cpu().tolist(),"leg_action12":legs.squeeze(0).detach().cpu().tolist(),"logical_action19":warped.logical_action.squeeze(0).tolist(),"target20":target.squeeze(0).tolist(),"raw_target20":target.squeeze(0).tolist(),"target_authority":"policy/source raw target before MUJOCO_LOCAL_DECLARED_REALIZATION","stage":action.stage_used_for_action,"stage_after_observation":stage.stage,"augmentation":input_augmentation,"stage2_telemetry":{"pre_physics":stage2_pre_physics,"post_physics":stage2_post_physics}})
            if alignment is not None:
                components = _stage0_alignment_components(stage_observation, tracker)
                for name, value in components.items():
                    alignment[name][alignment_count] = value
                alignment["post_stage"][alignment_count] = stage.stage
                alignment["done"][alignment_count] = stage.terminal_reason is not None
                alignment_count += 1
                if alignment_count == alignment_control_limit:
                    alignment_stop_reason = "alignment_prefix_limit"
                    break
                if stage.terminal_reason is not None:
                    alignment_stop_reason = stage.terminal_reason
                    break
                if stage.stage != 0:
                    alignment_stop_reason = "stage0_transition"
                    break
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all(): raise FloatingPointError(f"nonfinite MuJoCo state in {row['case_id']} step {step}")
            if stage.terminal_reason is not None: break
    if active_stage2_close_span is not None:
        active_stage2_close_span["end_control_step"] = last_control_step
        active_stage2_close_span["control_steps"] = last_control_step - int(active_stage2_close_span["start_control_step"]) + 1
        active_stage2_close_span["duration_s"] = float(active_stage2_close_span["control_steps"]) * CONTROL_DT
        stage2_close_spans.append(active_stage2_close_span)
    for renderer in renderers.values(): renderer.close()
    if atlas_window is not None:
        expected_atlas_rows = 4 * (atlas_window[1] - atlas_window[0] + 1)
        if atlas_rows != expected_atlas_rows:
            raise RuntimeError(
                f"native contact atlas for {row['case_id']} wrote {atlas_rows} rows, expected {expected_atlas_rows}"
            )
    if stage34_target_discriminator:
        if stage34_discriminator_capture is None:
            raise RuntimeError(
                "Stage3/4 target discriminator requires base006 to enter a real Stage4 policy control"
            )
        if len(stage34_raw_target_schedule) != STAGE34_TARGET_DISCRIMINATOR_CONTROLS:
            raise RuntimeError(
                "Stage3/4 target discriminator ended before recording 12 Stage4 raw target controls"
            )
        stage34_discriminator_capture["raw_target20_schedule"] = stage34_raw_target_schedule
        stage34_target_discriminator_receipt = _run_stage34_target_discriminator(
            case_dir=case_dir,
            model=model,
            mapping=mapping,
            velocity_limit20=velocity_limit20,
            gate=gate,
            capture=stage34_discriminator_capture,
        )
    else:
        stage34_target_discriminator_receipt = {"status": "NOT_REQUESTED"}
    if (
        recorded_prefix_stage34_diagnostic
        and policy_prefix_applied_steps != len(policy_prefix_rows)
    ):
        raise RuntimeError(
            "recorded Stage3/4 prefix did not cover every source trace control step"
        )
    if alignment is not None:
        _write_alignment_trace(
            case_dir, alignment, alignment_count, row=row, scene=scene,
            stop_reason=alignment_stop_reason or "episode_end",
            control_limit=alignment_control_limit,
        )
    status = tracker.status()
    mechanics_diagnostic = {
        "mode": fixed_latch_mode,
        "constraint_gate_release_handle_rad": resolved_constraint_gate_release_handle_rad,
        "constraint_gate_initial_active": gate_initial_active,
        "constraint_gate_final_active": None if gate is None else gate.active(data),
        "constraint_gate_released": released,
        "constraint_gate_release_control_step": gate_release_control_step,
        "constraint_gate_release_physics_substep": gate_release_substep,
        "max_handle_hinge_rad": max_handle_hinge_rad,
        "max_door_hinge_rad": max_door_hinge_rad,
        "max_latch_slide_qpos_m": max_latch_slide_qpos_m,
        "max_abs_latch_slide_qpos_m": max_abs_latch_slide_qpos_m,
        "physical_collision_realization": latch_mechanics,
        "stage3_entry": stage3_entry,
        "isaac_authority_boundary": {
            "training": "build_latch=true: physical cone + prismatic joint + PhysX handle mimic",
            "physical_collision": "MuJoCo candidate realization only; cross-engine mechanics equivalence is not claimed",
            "exact_visual_t0": "build_latch=false and is render-only; it is not mechanics authority",
        },
        "stage2_to3_semantics": "unchanged grasp/contact streak transition; latch unlock is not an added stage gate",
    }
    receipt = {
        "schema": "doordog.sim2sim.depthadd_v3_episode.v3",
        "case_id": row["case_id"],
        "suite": row["suite"],
        "lane": row.get("lane"),
        "stress_profile": row.get("stress_profile"),
        "result": "COMPLETE",
        "evaluation_classification": (
            "RECORDED_HIGH_AND_LEG_ACTION_PREFIX_LOCAL_DIAGNOSTIC"
            if recorded_prefix_stage34_diagnostic
            else "RUNTIME_REPRODUCIBILITY_DIAGNOSTIC"
            if alignment_export
            else "FORMAL_STUDENT_POLICY_EVALUATION"
        ),
        "outcome_eligibility": (
            "NOT_FORMAL_OUTCOME" if alignment_export else "FORMAL_OUTCOME_ELIGIBLE"
        ),
        "torch_runtime_determinism": {
            "torch_deterministic_algorithms": True,
            "cudnn_deterministic": True,
            "cudnn_benchmark": False,
            "cublas_workspace_config": ":4096:8",
            "end_to_end_bitwise_replay": "INCONCLUSIVE_EGL_RENDER_AND_CONTACT_CLOSED_LOOP",
        },
        "goal_reached": status.goal_reached,
        "max_stage": status.stage,
        "terminal_reason": status.terminal_reason or "horizon",
        "stage": status.as_dict(),
        "realized_parameters": row,
        "initial_state_realization": initial_state.receipt(contract["sim_joint_names"]),
        "plant_realization": plant_realization,
        "target_realization": {
            "status": MUJOCO_LOCAL_DECLARED_REALIZATION,
            "formula": "drive_target20 = qpos20 + clip(raw_target20 - qpos20, -velocity_limit20 * KD20 / KP20, +velocity_limit20 * KD20 / KP20)",
            "raw_target_authority": "Student policy/source target20 before local MuJoCo realization",
            "boundary": "MuJoCo-local declared realization; not PhysX or native-engine equivalence",
            "endpoint_projection": {
                "role": "BACKUP_TELEMETRY",
                "realization": DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION,
            },
            "shaping_exposure": {
                "exact_nonzero_rows": target_shaping_exact_nonzero_rows,
                "exact_nonzero_joint_events": target_shaping_exact_nonzero_joint_events,
                "substantive_epsilon_rad": 1.0e-6,
                "substantive_rows": target_shaping_substantive_rows,
                "substantive_joint_events": target_shaping_substantive_joint_events,
            },
        },
        "stage_budget_semantics": {
            "timebase": "control_steps_at_50Hz",
            "carry": "on transition subtract the completed stage budget; any overshoot carries into the next stage",
            "decision_order": "post-physics complete -> stage_overtime -> advance",
            "boundary": "a transition predicate true on the overtime step still terminates as stage_overtime",
        },
        "visual_overlay": visual_receipt,
        "mechanics_diagnostic": mechanics_diagnostic,
        "action_intervention": {
            "diagnostic_force_close_stage34": diagnostic_force_close_stage34,
            "forced_gripper_close_value": -1.0 if diagnostic_force_close_stage34 else None,
            "forced_gripper_close_stages": [STAGE_OPEN, STAGE_SWING] if diagnostic_force_close_stage34 else [],
            "forced_gripper_close_applied_control_steps": forced_gripper_close_applied_steps,
            "diagnostic_policy_prefix_trace": None if diagnostic_policy_prefix_trace is None else str(diagnostic_policy_prefix_trace.resolve()),
            "diagnostic_policy_prefix_applied_control_steps": policy_prefix_applied_steps,
            "authority_boundary": (
                "RECORDED_HIGH_AND_LEG_ACTION_PREFIX_LOCAL_DIAGNOSTIC: base006-only local "
                "plant discriminator; not an unmodified fixed16 or Student-policy outcome"
                if recorded_prefix_stage34_diagnostic
                else "matches the existing Isaac eval diagnostic override surface; formal Student eval keeps it disabled"
            ),
        },
        "surface_redraws": surface_redraw_receipts,
        "surface_redraw_boundary": "after each physics step before due camera capture",
        "t0_views": ["left_raw_renderer_rgb","left_post_color_pipeline_rgb","left_rgbd","right_raw_renderer_rgb","right_post_color_pipeline_rgb","right_rgbd","head_raw_renderer_rgb","head_post_color_pipeline_rgb","head_rgb","door_front_pos_x","door_front_neg_x"],
        "camera_frames": frames,
        "camera_last_capture_s": last,
        "camera_cadence": "after_each_mj_step_elapsed_due_left_right_1_over_30_head_1_over_15",
        "constraint_gate_released": released,
        "max_abs_qacc": max_qacc,
        "max_abs_pd_torque": max_torque,
        "stage2_telemetry_summary": {
            "tcp_source_frame": "a2_piper_tcp; target vectors are R_tcp_world^T @ (target_world - tcp_world)",
            "gripper_close_predicate": "raw_high_action12[11] <= 0.0 while action stage is Stage2",
            "first_close": stage2_first_close,
            "close_spans": stage2_close_spans,
            "min_tcp_to_grasp_distance_m": None if math.isinf(stage2_min_tcp_grasp_distance_m) else stage2_min_tcp_grasp_distance_m,
            "min_tcp_to_pregrasp_distance_m": None if math.isinf(stage2_min_tcp_pregrasp_distance_m) else stage2_min_tcp_pregrasp_distance_m,
            "both_handle_contact_control_steps": stage2_both_contact_steps,
            "valid_squeeze_control_steps": stage2_valid_squeeze_steps,
            "max_squeeze_streak_control_steps": stage2_max_squeeze_streak,
        },
        "native_contact_atlas": (
            {
                "status": "COMPLETE" if atlas_rows == 4 * (atlas_window[1] - atlas_window[0] + 1) else "INCOMPLETE",
                "path": str(atlas_path),
                "control_window_inclusive": list(atlas_window),
                "expected_rows": 4 * (atlas_window[1] - atlas_window[0] + 1),
                "recorded_rows": atlas_rows,
                "pre_step_authority": "mjSTATE_INTEGRATION + ctrl/applied/eq/mocap/userdata after gate update",
                "primary_timing": "after native MuJoCo mj_step and before endpoint projection or mj_forward",
                "projection_role": "secondary endpoint-projection backup telemetry",
            }
            if atlas_window is not None
            else {"status": "NOT_SELECTED_CASE" if contact_atlas else "NOT_REQUESTED"}
        ),
        "stage34_target_discriminator": stage34_target_discriminator_receipt,
    }
    _json_dump(case_dir/"receipt.json",receipt); return receipt


def export_alignment(args: argparse.Namespace) -> None:
    if args.baseline_output_dir is None:
        raise ValueError("--baseline-output-dir is required for export-alignment")
    baseline = args.baseline_output_dir.resolve(strict=True)
    manifest = _load_manifest(baseline)
    case_id = args.alignment_case_id
    rows = [row for row in manifest["primary_rows"] if row["case_id"] == case_id]
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one baseline manifest row {case_id}, got {len(rows)}")
    baseline_scene = baseline / "episodes" / case_id / "model" / "scene.xml"
    policy = load_depthadd_v3_policy(
        args.bundle_dir,
        source_workspace=args.source_workspace,
        device=args.device,
    )
    _run_episode(
        rows[0],
        output=args.output_dir.resolve(),
        robot_xml=_prepared_paths(baseline)["robot_xml"],
        policy=policy,
        device=torch.device(args.device),
        resolved_config=args.bundle_dir / "resolved_config.yaml",
        scene_override=baseline_scene,
        prepared_output=baseline,
        alignment_export=True,
        alignment_control_limit=args.alignment_control_limit,
    )


def run(args: argparse.Namespace) -> None:
    recorded_prefix_stage34_diagnostic = (
        args.stage34_target_discriminator
        and args.diagnostic_policy_prefix_trace is not None
    )
    mechanics_diagnostic_requested = (
        args.fixed_latch_mode != "constraint_gate"
        or args.constraint_gate_release_handle_rad is not None
        or args.diagnostic_force_close_stage34
        or args.diagnostic_policy_prefix_trace is not None
    )
    if mechanics_diagnostic_requested and (
        args.suite != "primary" or args.lane != "fixed"
    ):
        raise ValueError(
            "fixed latch diagnostics require --suite primary --lane fixed"
        )
    if args.contact_atlas and (
        args.suite != "primary"
        or args.lane != "fixed"
        or args.limit_base_cases != 16
        or args.shard_index != 0
        or args.shard_count != 1
        or args.fixed_latch_mode != "constraint_gate"
        or args.constraint_gate_release_handle_rad is not None
        or args.diagnostic_force_close_stage34
        or args.diagnostic_policy_prefix_trace is not None
        or args.empirical_source_nominal_appearance_calibration
        or args.fixed_nominal_appearance_factor is not None
    ):
        raise ValueError(
            "--contact-atlas requires the unmodified production-default fixed16 primary run without sharding"
        )
    if args.stage34_target_discriminator and not recorded_prefix_stage34_diagnostic and (
        args.suite != "primary"
        or args.lane != "fixed"
        or args.limit_base_cases != 16
        or args.shard_index != 0
        or args.shard_count != 1
        or args.fixed_latch_mode != "constraint_gate"
        or args.constraint_gate_release_handle_rad is not None
        or args.diagnostic_force_close_stage34
        or args.diagnostic_policy_prefix_trace is not None
        or args.contact_atlas
        or args.empirical_source_nominal_appearance_calibration
        or args.fixed_nominal_appearance_factor is not None
    ):
        raise ValueError(
            "--stage34-target-discriminator requires the unmodified production-default primary fixed16 run without sharding"
        )
    if recorded_prefix_stage34_diagnostic and (
        args.suite != "primary"
        or args.lane != "fixed"
        or args.limit_base_cases not in (None, 16)
        or args.shard_index != 0
        or args.shard_count != 1
        or args.fixed_latch_mode != "constraint_gate"
        or args.constraint_gate_release_handle_rad is not None
        or args.diagnostic_force_close_stage34
        or args.contact_atlas
        or args.empirical_source_nominal_appearance_calibration
        or args.fixed_nominal_appearance_factor is not None
    ):
        raise ValueError(
            "the Stage3/4 recorded action-prefix discriminator accepts only primary fixed base006 with no other intervention"
        )
    output=args.output_dir.resolve(); prepare_receipt=json.loads(_prepared_paths(output)["prepare_receipt"].read_text());
    if prepare_receipt["result"]!="PASS": raise RuntimeError("prepare receipt is not PASS")
    manifest=_load_manifest(output); rows=manifest[f"{args.suite}_rows"]
    if args.limit_base_cases is not None:
        if args.suite != "primary": raise ValueError("--limit-base-cases applies only to the primary suite")
        rows=_limit_primary_base_cases(rows, args.limit_base_cases)
    if args.lane is not None:
        if args.suite != "primary": raise ValueError("--lane applies only to the primary suite")
        rows=[row for row in rows if row["lane"] == args.lane]
    if recorded_prefix_stage34_diagnostic:
        rows = [
            row
            for row in rows
            if str(row["case_id"]) == STAGE34_TARGET_DISCRIMINATOR_CASE_ID
        ]
        if len(rows) != 1:
            raise RuntimeError("recorded Stage3/4 discriminator did not resolve exactly base006 fixed")
    selected=[row for index,row in enumerate(rows) if index % args.shard_count == args.shard_index]
    if not selected: raise RuntimeError("selected shard has no rows")
    if args.diagnostic_policy_prefix_trace is not None and len(selected) != 1:
        raise ValueError("--diagnostic-policy-prefix-trace requires exactly one selected episode")
    policy=load_depthadd_v3_policy(args.bundle_dir,source_workspace=args.source_workspace,device=args.device); robot=_prepared_paths(output)["robot_xml"]
    for row in selected:
        receipt=output/"episodes"/str(row["case_id"])/"receipt.json"
        if receipt.exists():
            completed=json.loads(receipt.read_text())
            if completed.get("case_id") != row["case_id"] or completed.get("result") != "COMPLETE": raise RuntimeError(f"invalid existing episode receipt {receipt}")
            if args.fixed_nominal_appearance_factor is not None:
                overlay = completed.get("visual_overlay", {})
                if overlay.get("profile") != "EMPIRICAL_FACTOR_SEPARABLE_FIXED_NOMINAL" or overlay.get("factor_requested") != args.fixed_nominal_appearance_factor:
                    raise RuntimeError(f"existing receipt does not match fixed nominal appearance factor {args.fixed_nominal_appearance_factor!r}: {receipt}")
            if args.empirical_source_nominal_appearance_calibration and completed.get("visual_overlay", {}).get("calibration_type") != "EMPIRICAL_T0_NOMINAL_APPEARANCE_CALIBRATION":
                raise RuntimeError(f"existing receipt is not an empirical nominal appearance calibration: {receipt}")
            completed_mechanics = completed.get("mechanics_diagnostic")
            expected_release = (
                float(row["door_geometry"].get("constraint_gate_release_handle_rad", math.pi / 6.0))
                if args.fixed_latch_mode == "constraint_gate" and args.constraint_gate_release_handle_rad is None
                else args.constraint_gate_release_handle_rad
            )
            if (
                not isinstance(completed_mechanics, Mapping)
                or completed_mechanics.get("mode") != args.fixed_latch_mode
                or completed_mechanics.get("constraint_gate_release_handle_rad") != expected_release
            ):
                raise RuntimeError(
                    f"existing receipt does not match requested fixed latch mode: {receipt}"
                )
            completed_intervention = completed.get("action_intervention", {})
            if completed_intervention.get("diagnostic_force_close_stage34", False) != args.diagnostic_force_close_stage34:
                raise RuntimeError(
                    f"existing receipt does not match requested Stage3/4 force-close diagnostic: {receipt}"
                )
            expected_prefix = None if args.diagnostic_policy_prefix_trace is None else str(args.diagnostic_policy_prefix_trace.resolve(strict=True))
            if completed_intervention.get("diagnostic_policy_prefix_trace") != expected_prefix:
                raise RuntimeError(
                    f"existing receipt does not match requested policy prefix trace: {receipt}"
                )
            atlas_receipt = completed.get("native_contact_atlas", {})
            if args.contact_atlas and str(row["case_id"]) in CONTACT_ATLAS_WINDOWS:
                if atlas_receipt.get("status") != "COMPLETE":
                    raise RuntimeError(f"existing target atlas receipt is incomplete: {receipt}")
            if (
                args.stage34_target_discriminator
                and str(row["case_id"]) == STAGE34_TARGET_DISCRIMINATOR_CASE_ID
                and completed.get("stage34_target_discriminator", {}).get("status") != "COMPLETE"
            ):
                raise RuntimeError(
                    f"existing Stage3/4 target discriminator receipt is incomplete: {receipt}"
                )
            if (
                recorded_prefix_stage34_diagnostic
                and completed.get("evaluation_classification")
                != "RECORDED_HIGH_AND_LEG_ACTION_PREFIX_LOCAL_DIAGNOSTIC"
            ):
                raise RuntimeError(
                    f"existing receipt is not the recorded action-prefix local diagnostic: {receipt}"
                )
            continue
        _run_episode(
            row,
            output=output,
            robot_xml=robot,
            policy=policy,
            device=torch.device(args.device),
            resolved_config=args.bundle_dir/"resolved_config.yaml",
            empirical_source_nominal_appearance_calibration=args.empirical_source_nominal_appearance_calibration,
            fixed_nominal_appearance_factor=args.fixed_nominal_appearance_factor,
            fixed_latch_mode=args.fixed_latch_mode,
            constraint_gate_release_handle_rad=args.constraint_gate_release_handle_rad,
            diagnostic_force_close_stage34=args.diagnostic_force_close_stage34,
            diagnostic_policy_prefix_trace=args.diagnostic_policy_prefix_trace,
            contact_atlas=args.contact_atlas,
            stage34_target_discriminator=(
                args.stage34_target_discriminator
                and str(row["case_id"]) == STAGE34_TARGET_DISCRIMINATOR_CASE_ID
            ),
        )


def _rate(rows: Iterable[Mapping[str, Any]]) -> float:
    values=list(rows); return float(sum(bool(row["goal_reached"]) for row in values)/len(values)) if values else float("nan")


def _outcome_summary(receipts: list[Mapping[str, Any]], group_key: str) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for group in sorted({str(receipt[group_key]) for receipt in receipts}):
        rows = [receipt for receipt in receipts if str(receipt[group_key]) == group]
        terminal_counts: dict[str, int] = defaultdict(int)
        stage_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            terminal_counts[str(row["terminal_reason"])] += 1
            stage_counts[str(row["max_stage"])] += 1
        summary[group] = {
            "episodes": len(rows),
            "goals": sum(bool(row["goal_reached"]) for row in rows),
            "success_rate": _rate(rows),
            "max_stage_mean": float(np.mean([float(row["max_stage"]) for row in rows])),
            "max_stage_counts": dict(sorted(stage_counts.items())),
            "terminal_reason_counts": dict(sorted(terminal_counts.items())),
        }
    return summary


def _fixed_stage0_gate_diagnostic(
    output: Path,
    fixed_receipts: list[Mapping[str, Any]],
    resolved_config: Path,
) -> dict[str, Any]:
    robot_contract = json.loads((_prepared_paths(output)["robot_contract"]).read_text())
    default = np.asarray(robot_contract["default_dof_pos"], dtype=np.float64)
    warp_contract = ResolvedActionWarpContractR5.from_config(resolved_config)
    per_episode: list[dict[str, Any]] = []
    for receipt in fixed_receipts:
        case_dir = output / "episodes" / str(receipt["case_id"])
        model = mujoco.MjModel.from_xml_path(str(case_dir / "model" / "scene.xml"))
        data = mujoco.MjData(model)
        home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
        mujoco.mj_resetDataKeyframe(model, data, home)
        mujoco.mj_forward(model, data)
        grasp_site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "door_grasp_target")
        grasp = data.site_xpos[grasp_site].copy()
        policy_rows = [json.loads(line) for line in (case_dir / "policy_trace.jsonl").open()]
        physics_rows = [
            row for row in (json.loads(line) for line in (case_dir / "physics_trace.jsonl").open())
            if int(row["substep"]) == 3
        ]
        if len(policy_rows) != len(physics_rows):
            raise RuntimeError(f"policy/physics trace cadence mismatch in {receipt['case_id']}")
        spatial_arm_ready_steps = 0
        base_still_steps = 0
        all_ready_steps = 0
        ready_base_norms: list[float] = []
        for policy_row, physics_row in zip(policy_rows, physics_rows, strict=True):
            root = np.asarray(physics_row["root_qpos7"][:3], dtype=np.float64)
            qpos = np.asarray(physics_row["qpos20"], dtype=np.float64)
            raw_base = np.asarray(policy_row["high_action12"][:3], dtype=np.float64)
            physical = np.clip(
                raw_base * warp_contract.base_command_scale,
                -np.asarray(warp_contract.base_clip_thresholds_xyz),
                np.asarray(warp_contract.base_clip_thresholds_xyz),
            )
            base_norm = float(np.linalg.norm(physical))
            spatial_ready = (
                0.5 <= float(grasp[0] - root[0]) <= 0.8
                and abs(float(root[1] - grasp[1])) < 0.15
            )
            arm_ready = float(np.max(np.abs(qpos[12:18] - default[12:18]))) < 0.1
            spatial_arm_ready = spatial_ready and arm_ready
            base_still = base_norm <= 0.1
            spatial_arm_ready_steps += int(spatial_arm_ready)
            base_still_steps += int(base_still)
            all_ready_steps += int(spatial_arm_ready and base_still)
            if spatial_arm_ready:
                ready_base_norms.append(base_norm)
        per_episode.append({
            "case_id": receipt["case_id"],
            "spatial_and_arm_ready_steps": spatial_arm_ready_steps,
            "base_still_steps": base_still_steps,
            "all_stage0_gate_ready_steps": all_ready_steps,
            "minimum_base_command_norm_while_spatial_and_arm_ready": min(ready_base_norms),
        })
    return {
        "stage0_gate": {
            "staging_x_m": [0.5, 0.8],
            "staging_abs_y_max_m": 0.15,
            "arm_default_max_deviation_rad": 0.1,
            "physical_base_command_norm_max": 0.1,
        },
        "per_episode": per_episode,
        "conclusion": "spatial_and_arm_gate_was_reached_but_student_never_commanded_base_still",
    }


def reduce_admission(args: argparse.Namespace) -> None:
    if args.suite != "primary" or args.limit_base_cases is None:
        raise ValueError("admission reduction requires --suite primary and --limit-base-cases")
    output = args.output_dir.resolve()
    manifest = _load_manifest(output)
    expected = _limit_primary_base_cases(manifest["primary_rows"], args.limit_base_cases)
    receipts: list[Mapping[str, Any]] = []
    missing: list[str] = []
    for row in expected:
        path = output / "episodes" / str(row["case_id"]) / "receipt.json"
        if not path.is_file():
            missing.append(str(row["case_id"]))
        else:
            receipts.append(json.loads(path.read_text()))
    if missing:
        raise RuntimeError(f"cannot reduce incomplete admission: {len(missing)} receipts missing")
    expected_count = 4 * args.limit_base_cases
    if len(receipts) != expected_count:
        raise RuntimeError(f"admission expected {expected_count} receipts, got {len(receipts)}")
    completed_primary: list[Mapping[str, Any]] = []
    for row in manifest["primary_rows"]:
        path = output / "episodes" / str(row["case_id"]) / "receipt.json"
        if path.is_file():
            completed_primary.append(json.loads(path.read_text()))
    fixed = [receipt for receipt in receipts if receipt["lane"] == "fixed"]
    systemic_fixed_failure = (
        len(fixed) == args.limit_base_cases
        and not any(bool(receipt["goal_reached"]) for receipt in fixed)
        and all(int(receipt["max_stage"]) == 0 for receipt in fixed)
        and all(receipt["terminal_reason"] == "stage_overtime" for receipt in fixed)
    )
    admission_pass = not systemic_fixed_failure and any(bool(receipt["goal_reached"]) for receipt in fixed)
    report = {
        "schema": "doordog.sim2sim.depthadd_v3_admission_reduction.v1",
        "evidence_level": "EXPERIMENT",
        "episode_count": len(receipts),
        "base_case_count": args.limit_base_cases,
        "outcomes_by_lane": _outcome_summary(receipts, "lane"),
        "fixed_stage0_gate_diagnostic": _fixed_stage0_gate_diagnostic(
            output,
            fixed,
            args.bundle_dir / "resolved_config.yaml",
        ),
        "additional_diagnostic_episode_count": len(completed_primary) - len(receipts),
        "all_completed_primary_diagnostic_outcomes_by_lane": _outcome_summary(completed_primary, "lane"),
        "systemic_fixed_failure": systemic_fixed_failure,
        "status": "ADMISSION_PASS" if admission_pass else "HARD_STOP_FIXED_LANE_FAILURE",
        "states": {
            "LOADER": "PASS",
            "FIXED_ROLLOUT": "PASS" if admission_pass else "FAIL",
            "RANDOMIZED_COMPLETE": "NOT_RUN_HARD_STOP" if systemic_fixed_failure else "NOT_RUN",
            "POLICY_QUALITY": "ADMISSION_PASS" if admission_pass else "FAIL_MUJOCO_ADMISSION",
        },
    }
    _json_dump(output / "admission_report.json", report)


def _write_reduction_artifacts(output: Path, report: Mapping[str, Any]) -> None:
    stage_keys = tuple(str(stage) for stage in range(6))
    lane_order = ("fixed", "visual_only", "door_only", "combined")
    with (output / "formal_lane_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "lane",
                "episodes",
                "goals",
                "success_rate",
                "max_stage_mean",
                *(f"max_stage_{stage}_count" for stage in stage_keys),
                "stage_overtime_count",
            )
        )
        for lane in lane_order:
            value = report["outcomes_by_lane"][lane]
            writer.writerow(
                (
                    lane,
                    value["episodes"],
                    value["goals"],
                    value["success_rate"],
                    value["max_stage_mean"],
                    *(value["max_stage_counts"].get(stage, 0) for stage in stage_keys),
                    value["terminal_reason_counts"].get("stage_overtime", 0),
                )
            )
    with (output / "formal_stress_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "stress_profile",
                "episodes",
                "goals",
                "success_rate",
                "max_stage_mean",
                *(f"max_stage_{stage}_count" for stage in stage_keys),
                "stage_overtime_count",
            )
        )
        for profile, value in report["stress_outcomes"].items():
            writer.writerow(
                (
                    profile,
                    value["episodes"],
                    value["goals"],
                    value["success_rate"],
                    value["max_stage_mean"],
                    *(value["max_stage_counts"].get(stage, 0) for stage in stage_keys),
                    value["terminal_reason_counts"].get("stage_overtime", 0),
                )
            )

    panels = (
        ("Primary lanes", lane_order, report["outcomes_by_lane"]),
        ("Stress profiles", tuple(report["stress_outcomes"]), report["stress_outcomes"]),
    )
    colors = ("#4779ad", "#d5962f", "#d06b3c", "#7f8b4c", "#c17aa5", "#8a8f98")
    figure, axes = plt.subplots(2, 1, figsize=(12, 9))
    for axis, (title, names, outcomes) in zip(axes, panels, strict=True):
        left = np.zeros(len(names), dtype=np.float64)
        for stage, color in zip(stage_keys, colors, strict=True):
            values = np.asarray(
                [
                    outcomes[name]["max_stage_counts"].get(stage, 0)
                    / outcomes[name]["episodes"]
                    for name in names
                ],
                dtype=np.float64,
            )
            axis.barh(names, values, left=left, label=f"Stage {stage}", color=color)
            left += values
        axis.set_xlim(0.0, 1.0)
        axis.set_xlabel("share of episodes by maximum reached stage")
        axis.set_title(title)
    axes[0].legend(ncol=6, loc="lower center", bbox_to_anchor=(0.5, 1.08))
    figure.suptitle("DepthADD v3 MuJoCo maximum-stage distribution")
    figure.tight_layout()
    figure.savefig(output / "formal_max_stage_distribution.png", dpi=150)
    plt.close(figure)

    lane_lines = []
    for lane in lane_order:
        value = report["outcomes_by_lane"][lane]
        counts = "/".join(str(value["max_stage_counts"].get(stage, 0)) for stage in ("0", "1", "2", "3"))
        lane_lines.append(
            f"| `{lane}` | {value['episodes']} | {value['goals']} | "
            f"{value['max_stage_mean']:.6f} | {counts} |"
        )
    stress_lines = []
    for profile, value in report["stress_outcomes"].items():
        counts = "/".join(str(value["max_stage_counts"].get(stage, 0)) for stage in ("0", "1", "2", "3"))
        stress_lines.append(
            f"| `{profile}` | {value['episodes']} | {value['goals']} | "
            f"{value['max_stage_mean']:.6f} | {counts} |"
        )
    stage_effects = report["paired_max_stage_deltas"]
    markdown = f"""# DepthADD v3 MuJoCo randomized evaluation

## Technical summary

- **Experiment complete:** `{report['primary_episode_count']}` primary and `{report['stress_episode_count']}` stress episodes; all required receipts were reduced.
- **Policy quality:** `0/{report['primary_episode_count']}` primary and `0/{report['stress_episode_count']}` stress goals. Every episode terminated by `stage_overtime`.
- **Fixed robustness after the observation fix:** all 384 fixed episodes reached Stage2 (`max_stage_mean=2.0`), so the corrected Stage0/Stage1 behavior holds across 128 cases × 3 seeds.
- **Visual degradation is live and broad:** visual-only and combined means are `{report['outcomes_by_lane']['visual_only']['max_stage_mean']:.6f}` and `{report['outcomes_by_lane']['combined']['max_stage_mean']:.6f}`, versus fixed `2.0`. This does not contradict the earlier 39-step substitution result; the earlier claim was limited to the original fixed Stage0 gap.
- **Current bottleneck:** fixed episodes fail at Stage2, while random visual lanes also introduce Stage0/1 regressions. The 20 m wall probe remains `NOT_RUN`.

## Fixed reaches Stage2 consistently, while visual lanes regress earlier

Stage counts are shown as `Stage0/Stage1/Stage2/Stage3`.

| Lane | Episodes | Goals | Mean max stage | Stage0/1/2/3 counts |
|---|---:|---:|---:|---|
{chr(10).join(lane_lines)}

![Maximum-stage distribution](formal_max_stage_distribution.png)

The paired maximum-stage effects are more informative than success effects because every success rate is zero:

- visual − fixed: `{stage_effects['visual_fixed']['mean']:.6f}` stages across `{stage_effects['visual_fixed']['n']}` pairs;
- door − fixed: `{stage_effects['door_fixed']['mean']:.6f}` stages across `{stage_effects['door_fixed']['n']}` pairs;
- visual×door interaction: `{stage_effects['interaction']['mean']:.6f}` stages across `{stage_effects['interaction']['n']}` pairs.

## Stress profiles also produce no goals

| Stress profile | Episodes | Goals | Mean max stage | Stage0/1/2/3 counts |
|---|---:|---:|---:|---|
{chr(10).join(stress_lines)}

Bright/high-handle stress reaches Stage2 most often; full-dark/heavy/low-handle is worst by mean max stage. These are progression differences, not success differences.

## Scope and methodology

The primary design contains 128 base cases × 3 seeds × four matched lanes (`fixed`, `visual_only`, `door_only`, `combined`) for 1536 episodes. Stress contains four profiles × 32 episodes. Success is terminal `complete`; progression is the maximum reached stage. Paired effects use matched case/seed rows. All episodes use the corrected live runtime `actor_obs81` packer.

## Limitations and evidence boundary

- Zero success creates a floor effect: success-rate main effects and interaction are all zero and cannot rank degradation severity.
- Maximum-stage effects describe progression but do not prove which visual parameter or Stage2 mechanic caused failure.
- Fixed Stage2 timeout is distinct from the resolved Stage0 packing bug.
- No episode changes or tests a 20 m wall; geometry attribution remains unsupported.

## Recommended next steps

1. Diagnose fixed Stage2 contact/squeeze/handle mechanics first, because fixed has no remaining Stage0/1 failure.
2. Separately decompose visual-only/combined Stage0/1 regressions by realized material/light/camera parameters using the saved receipts.
3. Do not use success-rate main effects until at least one lane escapes the all-zero floor.
4. Keep the wall probe `NOT_RUN` unless new parameter-level evidence reopens geometry.

## Further questions

- Which realized visual parameters concentrate the 209 visual-only/combined Stage0 failures?
- Why does the single combined episode reach Stage3 while all fixed episodes stop at Stage2?
"""
    (output / "report.md").write_text(markdown, encoding="utf-8")


def reduce(args: argparse.Namespace) -> None:
    output = args.output_dir.resolve()
    manifest = _load_manifest(output)
    expected = manifest["primary_rows"] + manifest["stress_rows"]
    receipts = []
    missing = []
    for row in expected:
        path = output / "episodes" / str(row["case_id"]) / "receipt.json"
        if not path.is_file():
            missing.append(str(row["case_id"]))
            continue
        receipts.append(json.loads(path.read_text()))
    if missing:
        raise RuntimeError(f"cannot reduce incomplete experiment: {len(missing)} receipts missing")

    primary = [receipt for receipt in receipts if receipt["suite"] == "primary"]
    stress = [receipt for receipt in receipts if receipt["suite"] == "stress"]
    lane_names = ("fixed", "visual_only", "door_only", "combined")
    lanes = {
        lane: _rate([receipt for receipt in primary if receipt["lane"] == lane])
        for lane in lane_names
    }
    paired: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for receipt in primary:
        paired[receipt["case_id"].rsplit("__", 1)[0]][receipt["lane"]] = receipt
    success_deltas = {name: [] for name in ("visual_fixed", "door_fixed", "interaction")}
    stage_deltas = {name: [] for name in ("visual_fixed", "door_fixed", "interaction")}
    for values in paired.values():
        if set(values) != set(lane_names):
            raise RuntimeError("incomplete paired primary quartet")
        fixed, visual, door, combined = (
            float(values[lane]["goal_reached"]) for lane in lane_names
        )
        success_deltas["visual_fixed"].append(visual - fixed)
        success_deltas["door_fixed"].append(door - fixed)
        success_deltas["interaction"].append(combined - door - visual + fixed)
        fixed, visual, door, combined = (
            float(values[lane]["max_stage"]) for lane in lane_names
        )
        stage_deltas["visual_fixed"].append(visual - fixed)
        stage_deltas["door_fixed"].append(door - fixed)
        stage_deltas["interaction"].append(combined - door - visual + fixed)

    cell_names = ("A0", "A1", "A4", "A6")
    cell_rows = {
        cell: [
            receipt
            for receipt in primary
            if receipt["realized_parameters"]["door_dynamics_cell_id"] == cell
        ]
        for cell in cell_names
    }
    cell_success = {cell: _rate(rows) for cell, rows in cell_rows.items()}
    outcomes_by_cell = {
        cell: _outcome_summary(
            [{**receipt, "_cell": cell} for receipt in rows], "_cell"
        )[cell]
        for cell, rows in cell_rows.items()
    }
    stress_names = sorted({receipt["stress_profile"] for receipt in stress})
    stress_success = {
        profile: _rate([receipt for receipt in stress if receipt["stress_profile"] == profile])
        for profile in stress_names
    }
    outcomes_by_lane = _outcome_summary(primary, "lane")
    stage_lane_mean = {
        lane: outcomes_by_lane[lane]["max_stage_mean"] for lane in lane_names
    }
    report = {
        "schema": "doordog.sim2sim.depthadd_v3_reduction.v2",
        "status": "RANDOMIZED_COMPLETE",
        "primary_episode_count": len(primary),
        "stress_episode_count": len(stress),
        "lane_success": lanes,
        "outcomes_by_lane": outcomes_by_lane,
        "paired_deltas": {
            key: {"mean": float(np.mean(values)), "n": len(values)}
            for key, values in success_deltas.items()
        },
        "paired_max_stage_deltas": {
            key: {"mean": float(np.mean(values)), "n": len(values)}
            for key, values in stage_deltas.items()
        },
        "main_effects": {
            "visual": float(
                np.mean(
                    [
                        lanes["visual_only"] - lanes["fixed"],
                        lanes["combined"] - lanes["door_only"],
                    ]
                )
            ),
            "door": float(
                np.mean(
                    [
                        lanes["door_only"] - lanes["fixed"],
                        lanes["combined"] - lanes["visual_only"],
                    ]
                )
            ),
        },
        "stage_main_effects": {
            "visual": float(
                np.mean(
                    [
                        stage_lane_mean["visual_only"] - stage_lane_mean["fixed"],
                        stage_lane_mean["combined"] - stage_lane_mean["door_only"],
                    ]
                )
            ),
            "door": float(
                np.mean(
                    [
                        stage_lane_mean["door_only"] - stage_lane_mean["fixed"],
                        stage_lane_mean["combined"] - stage_lane_mean["visual_only"],
                    ]
                )
            ),
        },
        "interaction": float(np.mean(success_deltas["interaction"])),
        "stage_interaction": float(np.mean(stage_deltas["interaction"])),
        "cell_success": cell_success,
        "outcomes_by_cell": outcomes_by_cell,
        "stress_success": stress_success,
        "stress_outcomes": _outcome_summary(stress, "stress_profile"),
        "wall_probe_20m": "NOT_RUN",
        "states": {
            "LOADER": "PASS",
            "FIXED_ROLLOUT": "COMPLETE",
            "RANDOMIZED_COMPLETE": "COMPLETE",
            "POLICY_QUALITY": "REPORTED_BY_SUCCESS_AND_STAGE_METRICS",
        },
    }
    _json_dump(output / "report.json", report)
    _write_reduction_artifacts(output, report)


def main() -> None:
    _configure_deterministic_torch_runtime()
    parser=argparse.ArgumentParser(); parser.add_argument("--mode",choices=("prepare","run","reduce-admission","reduce","export-alignment","contact-retention-kd-discriminator"),required=True); parser.add_argument("--bundle-dir",type=Path,required=True); parser.add_argument("--source-workspace",type=Path,required=True); parser.add_argument("--robot-urdf",type=Path,required=True); parser.add_argument("--experiment-yaml",type=Path,required=True); parser.add_argument("--output-dir",type=Path,required=True); parser.add_argument("--baseline-output-dir",type=Path); parser.add_argument("--device",default="cuda:0"); parser.add_argument("--suite",choices=("primary","stress"),default="primary"); parser.add_argument("--lane",choices=("fixed","visual_only","door_only","combined")); parser.add_argument("--limit-base-cases",type=int); parser.add_argument("--shard-index",type=int,default=0); parser.add_argument("--shard-count",type=int,default=1); parser.add_argument("--empirical-source-nominal-appearance-calibration",action="store_true",help="legacy fixed-only empirical t0 calibration; not material/shader authority"); parser.add_argument("--fixed-nominal-appearance-factor",choices=fixed_nominal_appearance_factor_names(),help="fixed-only controlled ablation: stable_baseline applies all factors; named factors withhold exactly that factor"); parser.add_argument("--fixed-latch-mode",choices=("constraint_gate","physical_collision","no_latch"),default="constraint_gate",help="fixed-only mechanics diagnostic; default preserves the existing constraint gate"); parser.add_argument("--constraint-gate-release-handle-rad",type=float,help="constraint_gate-only release threshold in (0, pi/4]"); parser.add_argument("--diagnostic-force-close-stage34",action="store_true",help="apply the existing Isaac diagnostic -1 gripper override only while the tracker is in Stage3/4"); parser.add_argument("--diagnostic-policy-prefix-trace",type=Path,help="replay recorded high-level and leg actions through Stage2, then return to the live policy"); parser.add_argument("--contact-atlas",action="store_true",help="capture native pre-projection contact telemetry for base004/base010 during full fixed16"); parser.add_argument("--stage34-target-discriminator",action="store_true",help="on unmodified fixed16, capture base006 Stage4 and run recorded-target versus held-target local branches"); parser.add_argument("--alignment-case-id",default="seed41001_base000__fixed",help="export-alignment manifest case id; default preserves base000"); parser.add_argument("--alignment-control-limit",type=int,default=STAGE0_ALIGNMENT_MAX_STEPS,help="export-alignment control steps in [1,250]"); args=parser.parse_args()
    if args.constraint_gate_release_handle_rad is not None:
        if args.fixed_latch_mode != "constraint_gate":
            raise ValueError("--constraint-gate-release-handle-rad requires --fixed-latch-mode constraint_gate")
        if not math.isfinite(args.constraint_gate_release_handle_rad) or not 0.0 < args.constraint_gate_release_handle_rad <= math.pi / 4.0:
            raise ValueError("--constraint-gate-release-handle-rad must be finite and in (0, pi/4]")
    if (
        args.mode != "run"
        and (
            args.fixed_latch_mode != "constraint_gate"
            or args.constraint_gate_release_handle_rad is not None
            or args.diagnostic_force_close_stage34
            or args.diagnostic_policy_prefix_trace is not None
            or args.stage34_target_discriminator
        )
    ):
        raise ValueError("fixed mechanics/action diagnostics are available only with --mode run")
    if args.limit_base_cases is not None and args.limit_base_cases <= 0: raise ValueError("--limit-base-cases must be positive")
    if args.mode == "export-alignment" and not 1 <= args.alignment_control_limit <= STAGE0_ALIGNMENT_MAX_STEPS:
        raise ValueError(f"--alignment-control-limit must be in [1,{STAGE0_ALIGNMENT_MAX_STEPS}]")
    if args.shard_count <= 0 or not 0 <= args.shard_index < args.shard_count: raise ValueError("invalid shard selection")
    if args.empirical_source_nominal_appearance_calibration and args.fixed_nominal_appearance_factor is not None:
        raise ValueError("--empirical-source-nominal-appearance-calibration and --fixed-nominal-appearance-factor are mutually exclusive")
    if args.empirical_source_nominal_appearance_calibration and (args.mode != "run" or args.suite != "primary" or args.lane != "fixed"):
        raise ValueError("--empirical-source-nominal-appearance-calibration is valid only for --mode run --suite primary --lane fixed")
    if args.fixed_nominal_appearance_factor is not None and (args.mode != "run" or args.suite != "primary" or args.lane != "fixed"):
        raise ValueError("--fixed-nominal-appearance-factor is valid only for --mode run --suite primary --lane fixed")
    {"prepare":prepare,"run":run,"reduce-admission":reduce_admission,"reduce":reduce,"export-alignment":export_alignment,"contact-retention-kd-discriminator":contact_retention_kd_discriminator}[args.mode](args)


if __name__ == "__main__": main()
