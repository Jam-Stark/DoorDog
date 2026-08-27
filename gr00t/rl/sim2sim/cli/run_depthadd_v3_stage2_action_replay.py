#!/usr/bin/env python3
"""Replay an Isaac Stage2 state/target prefix in a realization-matched MuJoCo scene.

The producer trace is the authority for the recorded Stage2 robot/door state,
the composed A2 leg action, and the final 20-joint position target. The
MuJoCo scene is rebuilt from the same Isaac door customData rather than an
independently sampled fixed row. This establishes a strict recorded
state/kinematic-parameter/target prefix; it does not claim cross-engine
mechanics or collision materials are identical.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import mujoco
import numpy as np
import yaml

from gr00t.rl.sim2sim.doors.depthadd_v3 import DepthADDV3DoorBuilder, DepthADDV3DoorFactory
from gr00t.rl.sim2sim.mujoco.actuator_map_v2 import (
    DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION,
    MUJOCO_LOCAL_DECLARED_REALIZATION,
    NameResolvedActuatorMapV2,
    configure_depthadd_v3_contact_solref_2dt,
)
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import PairedSceneBuilderV2


CONTROL_DT = 0.02
PHYSICS_DT = 0.005
PHYSICS_STEPS_PER_CONTROL = 4
VELOCITY_REALIZATION_ENDPOINT_PROJECTION = "endpoint_projection"
VELOCITY_REALIZATION_NATIVE = "native"
PLANT_VARIANT_BASELINE = "baseline"
PLANT_VARIANT_JOINT_DAMPING_FORCE_PATH = "joint_damping_force_path"
PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET = "velocity_limited_pd_target"
PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT = (
    "velocity_limited_pd_target_contact_solref_2dt"
)
PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09 = (
    "velocity_limited_pd_target_contact_solref_2dt_friction09"
)
SOURCE_HIGH_LEVEL_ACTION_FIELD = "post_delta_post_warp_env_action"
SOURCE_LEG_ACTION_FIELD = "a2_base_leg_action12"
SOURCE_JOINT_NAMES_FIELD = "joint_names"
SOURCE_JOINT_POS_FIELD = "robot_joint_pos20"
SOURCE_JOINT_VEL_FIELD = "robot_joint_vel20"
SOURCE_FINAL_TARGET_FIELD = "final_joint_position_target20"
SOURCE_DOOR_JOINT_NAMES_FIELD = "door_joint_names"
SOURCE_DOOR_JOINT_POS_FIELD = "door_joint_pos"
SOURCE_DOOR_JOINT_VEL_FIELD = "door_joint_vel"


@dataclass(frozen=True)
class SourceStage2Step:
    control_step: int
    high_action12: np.ndarray
    leg_action12: np.ndarray
    joint_names: tuple[str, ...]
    joint_pos20: np.ndarray
    joint_vel20: np.ndarray
    final_target20: np.ndarray
    root_pos_rel3: np.ndarray
    root_quat_wxyz4: np.ndarray
    root_lin_vel_w3: np.ndarray
    root_ang_vel_w3: np.ndarray
    door_joint_names: tuple[str, ...]
    door_joint_pos: np.ndarray
    door_joint_vel: np.ndarray
    source_tcp_to_handle3: np.ndarray
    source_tcp_to_handle_m: float


@dataclass(frozen=True)
class SourcePlantSubstep:
    """One completed Isaac physics substep in the fixed Stage2 attribution window."""

    control_step: int
    physics_substep: int
    joint_pos20: np.ndarray
    joint_vel20: np.ndarray
    final_target20: np.ndarray
    door_joint_pos: np.ndarray
    door_joint_vel: np.ndarray
    applied_effort20_nm: np.ndarray | None
    finger_handle_normal_contact_force_on_handle_w_n: np.ndarray | None


@dataclass(frozen=True)
class VelocityRealizationTelemetry:
    """Native substep telemetry plus the selected velocity-limit realization."""

    native_qpos20: np.ndarray
    native_qvel20: np.ndarray
    realized_qvel20: np.ndarray
    applied_qpos_correction20: np.ndarray
    applied_mask20: np.ndarray
    applied_count: int
    theoretical_projected_qvel20: np.ndarray
    theoretical_qpos_correction20: np.ndarray
    theoretical_mask20: np.ndarray
    theoretical_count: int
    native_max_velocity_limit_ratio: float
    realized_max_velocity_limit_ratio: float
    theoretical_projected_max_velocity_limit_ratio: float
    native_actuator_force20: np.ndarray
    native_qfrc_actuator20_nm: np.ndarray
    native_qfrc_constraint20_nm: np.ndarray
    native_qacc20_rad_s2: np.ndarray
    native_qfrc_passive20_nm: np.ndarray
    native_qfrc_smooth20_nm: np.ndarray


@dataclass(frozen=True)
class ReplayInputs:
    source_steps: tuple[SourceStage2Step, ...]
    robot_joint_names: tuple[str, ...]
    robot_xml: Path
    robot_contract: Path
    armature_by_joint: Mapping[str, float]
    velocity_limit20: np.ndarray
    producer_custom_data: Mapping[str, Any]
    producer_diagnostic_json: Path
    source_latch_mode: str
    source_plant_substeps: Mapping[tuple[int, int], SourcePlantSubstep]
    source_plant_substep_trace: Path | None
    source_plant_substep_schema: str | None
    source_plant_substep_capability: Mapping[str, Any]


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _finite_vector(value: Any, *, width: int, field: str, step: int) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (width,):
        raise ValueError(f"{field} at source step {step} has shape {result.shape}, expected {(width,)}")
    if not np.isfinite(result).all():
        raise FloatingPointError(f"{field} at source step {step} contains a non-finite value")
    return result


def _finite_scalar(value: Any, *, field: str, step: int) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise FloatingPointError(f"{field} at source step {step} is non-finite")
    return result


def _string_tuple(value: Any, *, field: str, step: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise TypeError(f"{field} at source step {step} must be a non-empty list of names")
    result = tuple(value)
    if len(set(result)) != len(result):
        raise ValueError(f"{field} at source step {step} contains duplicate names")
    return result


def _load_source_stage2_steps(
    path: Path, *, env_id: int, episode_index: int
) -> tuple[SourceStage2Step, ...]:
    if path.name != "stage2_step_trace.json":
        raise ValueError("--producer-stage2-trace must be stage2_step_trace.json")
    payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"producer Stage2 trace must be a non-empty JSON list: {path}")
    rows = [
        row
        for row in payload
        if int(row.get("env_id", -1)) == env_id
        and int(row.get("episode_index", -1)) == episode_index
        and int(row.get("stage_buf", -1)) == 2
    ]
    if not rows:
        raise RuntimeError(
            f"producer trace has no Stage2 rows for env_id={env_id}, episode_index={episode_index}"
        )
    rows.sort(key=lambda row: int(row["step_index"]))
    steps = [int(row["step_index"]) for row in rows]
    if steps != list(range(steps[0], steps[0] + len(steps))):
        raise RuntimeError("producer Stage2 steps are not contiguous")
    required = (
        SOURCE_HIGH_LEVEL_ACTION_FIELD,
        SOURCE_LEG_ACTION_FIELD,
        SOURCE_JOINT_NAMES_FIELD,
        SOURCE_JOINT_POS_FIELD,
        SOURCE_JOINT_VEL_FIELD,
        SOURCE_FINAL_TARGET_FIELD,
        SOURCE_DOOR_JOINT_NAMES_FIELD,
        SOURCE_DOOR_JOINT_POS_FIELD,
        SOURCE_DOOR_JOINT_VEL_FIELD,
        "root_pos_rel",
        "root_quat_w",
        "root_lin_vel_w",
        "root_ang_vel_w",
        "tcp_to_handle_pos",
        "target_pos_source_handle_distance",
    )
    result: list[SourceStage2Step] = []
    for row in rows:
        step = int(row["step_index"])
        for field in required:
            if field not in row:
                raise KeyError(f"producer Stage2 row {step} lacks required authority field {field!r}")
        joint_names = _string_tuple(row[SOURCE_JOINT_NAMES_FIELD], field=SOURCE_JOINT_NAMES_FIELD, step=step)
        door_names = _string_tuple(
            row[SOURCE_DOOR_JOINT_NAMES_FIELD], field=SOURCE_DOOR_JOINT_NAMES_FIELD, step=step
        )
        if len(joint_names) != 20:
            raise ValueError(f"producer robot joint order at step {step} has {len(joint_names)} names")
        quat = _finite_vector(row["root_quat_w"], width=4, field="root_quat_w", step=step)
        if not math.isclose(float(np.linalg.norm(quat)), 1.0, rel_tol=0.0, abs_tol=1.0e-5):
            raise ValueError(f"producer root quaternion at step {step} is not unit length")
        result.append(
            SourceStage2Step(
                control_step=step,
                high_action12=_finite_vector(
                    row[SOURCE_HIGH_LEVEL_ACTION_FIELD], width=12, field=SOURCE_HIGH_LEVEL_ACTION_FIELD, step=step
                ),
                leg_action12=_finite_vector(
                    row[SOURCE_LEG_ACTION_FIELD], width=12, field=SOURCE_LEG_ACTION_FIELD, step=step
                ),
                joint_names=joint_names,
                joint_pos20=_finite_vector(
                    row[SOURCE_JOINT_POS_FIELD], width=20, field=SOURCE_JOINT_POS_FIELD, step=step
                ),
                joint_vel20=_finite_vector(
                    row[SOURCE_JOINT_VEL_FIELD], width=20, field=SOURCE_JOINT_VEL_FIELD, step=step
                ),
                final_target20=_finite_vector(
                    row[SOURCE_FINAL_TARGET_FIELD], width=20, field=SOURCE_FINAL_TARGET_FIELD, step=step
                ),
                root_pos_rel3=_finite_vector(row["root_pos_rel"], width=3, field="root_pos_rel", step=step),
                root_quat_wxyz4=quat,
                root_lin_vel_w3=_finite_vector(
                    row["root_lin_vel_w"], width=3, field="root_lin_vel_w", step=step
                ),
                root_ang_vel_w3=_finite_vector(
                    row["root_ang_vel_w"], width=3, field="root_ang_vel_w", step=step
                ),
                door_joint_names=door_names,
                door_joint_pos=_finite_vector(
                    row[SOURCE_DOOR_JOINT_POS_FIELD],
                    width=len(door_names),
                    field=SOURCE_DOOR_JOINT_POS_FIELD,
                    step=step,
                ),
                door_joint_vel=_finite_vector(
                    row[SOURCE_DOOR_JOINT_VEL_FIELD],
                    width=len(door_names),
                    field=SOURCE_DOOR_JOINT_VEL_FIELD,
                    step=step,
                ),
                source_tcp_to_handle3=_finite_vector(
                    row["tcp_to_handle_pos"], width=3, field="tcp_to_handle_pos", step=step
                ),
                source_tcp_to_handle_m=_finite_scalar(
                    row["target_pos_source_handle_distance"],
                    field="target_pos_source_handle_distance",
                    step=step,
                ),
            )
        )
    if len({row.joint_names for row in result}) != 1 or len({row.door_joint_names for row in result}) != 1:
        raise RuntimeError("producer joint-name order changes within the Stage2 trace")
    return tuple(result)


def _optional_finite_vector(
    row: Mapping[str, Any], *, field: str, width: int, control_step: int, physics_substep: int
) -> np.ndarray | None:
    """Parse an exporter field that is explicitly unavailable or numeric.

    Missing, JSON ``null``, and ``NOT_AVAILABLE`` are deliberately retained as absent evidence;
    they are not replaced with a proxy from another Isaac or MuJoCo surface.
    """

    value = row.get(field, "NOT_AVAILABLE")
    if value is None or value == "NOT_AVAILABLE":
        return None
    return _finite_vector(
        value,
        width=width,
        field=f"{field} at control={control_step}, substep={physics_substep}",
        step=control_step,
    )


def _load_source_plant_substeps(
    path: Path | None,
    *,
    env_id: int,
    episode_index: int,
    robot_joint_names: tuple[str, ...],
    door_joint_names: tuple[str, ...],
) -> tuple[Mapping[tuple[int, int], SourcePlantSubstep], str | None, Mapping[str, Any]]:
    if path is None:
        return {}, None, {}
    payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("producer plant substep trace must be a JSON mapping")
    schema = payload.get("schema")
    if not isinstance(schema, str) or not schema:
        raise TypeError("producer plant substep trace lacks a non-empty schema")
    timebase = payload.get("timebase")
    if not isinstance(timebase, Mapping):
        raise TypeError("producer plant substep trace lacks timebase")
    if not math.isclose(
        _finite_scalar(timebase.get("physics_dt_s"), field="physics_dt_s", step=-1),
        PHYSICS_DT,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError("producer plant substep physics_dt_s disagrees with MuJoCo attribution timebase")
    if not math.isclose(
        _finite_scalar(timebase.get("control_dt_s"), field="control_dt_s", step=-1),
        CONTROL_DT,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError("producer plant substep control_dt_s disagrees with MuJoCo attribution timebase")
    source_names = _string_tuple(payload.get("joint_names"), field="joint_names", step=-1)
    if set(source_names) != set(robot_joint_names):
        raise RuntimeError("producer plant substep joint names disagree with the MuJoCo robot contract")
    source_door_names = _string_tuple(payload.get("door_joint_names"), field="door_joint_names", step=-1)
    if source_door_names != door_joint_names:
        raise RuntimeError("producer plant substep door-joint order disagrees with the Stage2 control trace")
    capability = payload.get("capabilities", {})
    if not isinstance(capability, Mapping):
        raise TypeError("producer plant substep capabilities must be a mapping")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("producer plant substep trace has no records")
    result: dict[tuple[int, int], SourcePlantSubstep] = {}
    for row in records:
        if not isinstance(row, Mapping):
            raise TypeError("producer plant substep records must be mappings")
        if int(row.get("env_id", -1)) != env_id or int(row.get("episode_index", -1)) != episode_index:
            continue
        control_step = int(row.get("control_step_index", -1))
        physics_substep = int(row.get("physics_substep_index", -1))
        if control_step < 0 or physics_substep not in range(PHYSICS_STEPS_PER_CONTROL):
            raise ValueError("producer plant substep control/substep index is out of range")
        if (
            row.get("sample_timing")
            != "after simulator.simulate_at_each_physics_step() scene.update before next substep/post physics"
        ):
            raise RuntimeError("producer plant substep sample timing is not the declared post-physics surface")
        if not math.isclose(
            _finite_scalar(row.get("physics_dt_s"), field="physics_dt_s", step=control_step),
            PHYSICS_DT,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("producer substep physics_dt_s disagrees with MuJoCo attribution timebase")
        if not math.isclose(
            _finite_scalar(row.get("control_dt_s"), field="control_dt_s", step=control_step),
            CONTROL_DT,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("producer substep control_dt_s disagrees with MuJoCo attribution timebase")
        key = (control_step, physics_substep)
        if key in result:
            raise RuntimeError(f"producer plant substep trace duplicates control/substep {key}")
        contact_force = row.get("finger_handle_normal_contact_force_on_handle_w_N", "NOT_AVAILABLE")
        if contact_force is None or contact_force == "NOT_AVAILABLE":
            contact_force_array = None
        else:
            contact_force_array = np.asarray(contact_force, dtype=np.float64)
            if contact_force_array.shape != (2, 3) or not np.isfinite(contact_force_array).all():
                raise ValueError(
                    "finger_handle_normal_contact_force_on_handle_w_N at "
                    f"control={control_step}, substep={physics_substep} "
                    "must be finite shape (2, 3)"
                )
        result[key] = SourcePlantSubstep(
            control_step=control_step,
            physics_substep=physics_substep,
            joint_pos20=_finite_vector(
                row.get("robot_joint_pos20_rad"),
                width=20,
                field="robot_joint_pos20_rad",
                step=control_step,
            ),
            joint_vel20=_finite_vector(
                row.get("robot_joint_vel20_rad_s"),
                width=20,
                field="robot_joint_vel20_rad_s",
                step=control_step,
            ),
            final_target20=_finite_vector(
                row.get("final_joint_position_target20_rad"),
                width=20,
                field="final_joint_position_target20_rad",
                step=control_step,
            ),
            door_joint_pos=_finite_vector(
                row.get("door_joint_pos_rad"),
                width=len(source_door_names),
                field="door_joint_pos_rad",
                step=control_step,
            ),
            door_joint_vel=_finite_vector(
                row.get("door_joint_vel_rad_s"),
                width=len(source_door_names),
                field="door_joint_vel_rad_s",
                step=control_step,
            ),
            applied_effort20_nm=_optional_finite_vector(
                row,
                field="applied_effort20_Nm",
                width=20,
                control_step=control_step,
                physics_substep=physics_substep,
            ),
            finger_handle_normal_contact_force_on_handle_w_n=contact_force_array,
        )
    if not result:
        raise RuntimeError(
            f"producer plant substep trace has no rows for env_id={env_id}, episode_index={episode_index}"
        )
    controls = sorted({control_step for control_step, _ in result})
    for control_step in controls:
        present = sorted(
            physics_substep
            for recorded_control_step, physics_substep in result
            if recorded_control_step == control_step
        )
        if present != list(range(PHYSICS_STEPS_PER_CONTROL)):
            raise RuntimeError(
                f"producer plant substep trace is incomplete for control step {control_step}: {present}"
            )
    return result, schema, dict(capability)


def _prepared_root(case_dir: Path, receipt: Mapping[str, Any]) -> Path:
    candidates = [case_dir.parent.parent]
    source_scene = receipt.get("visual_overlay", {}).get("source_scene_xml")
    if source_scene is not None:
        scene = Path(source_scene).resolve(strict=True)
        if scene.name != "scene.xml" or scene.parent.name != "model":
            raise RuntimeError("robot authority receipt has an invalid source_scene_xml layout")
        candidates.append(scene.parents[3])
    roots = list(
        dict.fromkeys(root for root in candidates if (root / "prepared" / "robot_contract.json").is_file())
    )
    if len(roots) != 1:
        raise RuntimeError(f"expected one prepared robot authority root, found {[str(root) for root in roots]}")
    return roots[0]


def _producer_row(path: Path, env_id: int) -> Mapping[str, Any]:
    payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    table = payload.get("case_table")
    if not isinstance(table, Mapping):
        raise RuntimeError("producer diagnostic JSON lacks case_table")
    row = table.get(str(env_id))
    if not isinstance(row, Mapping):
        raise RuntimeError(f"producer diagnostic case_table lacks env {env_id}")
    custom = row.get("door_custom_data")
    if not isinstance(custom, Mapping):
        raise RuntimeError(f"producer diagnostic env {env_id} lacks door_custom_data")
    return row


def _source_latch_mode(door_joint_names: tuple[str, ...]) -> str:
    latch_names = [name for name in door_joint_names if "latch" in name.lower()]
    if latch_names:
        if len(door_joint_names) != 3 or len(latch_names) != 1:
            raise RuntimeError(f"unsupported producer latch topology: {door_joint_names}")
        return "physical_collision"
    if len(door_joint_names) != 2:
        raise RuntimeError(f"unsupported producer door topology: {door_joint_names}")
    return "no_latch"


def _load_inputs(
    *,
    robot_authority_episode_dir: Path,
    producer_stage2_trace: Path,
    producer_diagnostic_json: Path,
    producer_plant_substep_trace: Path | None,
    resolved_config: Path,
    producer_env_id: int,
    producer_episode_index: int,
) -> ReplayInputs:
    receipt = json.loads(
        (robot_authority_episode_dir / "receipt.json").resolve(strict=True).read_text(encoding="utf-8")
    )
    prepared_root = _prepared_root(robot_authority_episode_dir, receipt)
    robot_contract_path = (prepared_root / "prepared" / "robot_contract.json").resolve(strict=True)
    contract = json.loads(robot_contract_path.read_text(encoding="utf-8"))
    names = tuple(contract["sim_joint_names"])
    if len(names) != 20:
        raise RuntimeError(f"robot contract must expose 20 joints, got {len(names)}")
    armature = tuple(float(value) for value in contract["armature"])
    if len(armature) != 20:
        raise RuntimeError(f"robot contract must expose 20 armature values, got {len(armature)}")
    source_steps = _load_source_stage2_steps(
        producer_stage2_trace, env_id=producer_env_id, episode_index=producer_episode_index
    )
    if set(source_steps[0].joint_names) != set(names):
        raise RuntimeError("producer and MuJoCo robot authorities do not contain the same joint names")
    producer_row = _producer_row(producer_diagnostic_json, producer_env_id)
    runtime = yaml.safe_load(resolved_config.resolve(strict=True).read_text(encoding="utf-8"))
    runtime_robot = runtime["env"]["config"]["robot"]
    if tuple(runtime_robot["dof_names"]) != names:
        raise RuntimeError("resolved velocity-limit joint order disagrees with the MuJoCo robot contract")
    velocity_limit20 = _finite_vector(
        runtime_robot["dof_vel_limit_list"], width=20, field="dof_vel_limit_list", step=-1
    )
    if np.any(velocity_limit20 <= 0.0):
        raise ValueError("resolved robot velocity limits must be positive")
    source_plant_substeps, source_plant_schema, source_plant_capability = _load_source_plant_substeps(
        producer_plant_substep_trace,
        env_id=producer_env_id,
        episode_index=producer_episode_index,
        robot_joint_names=names,
        door_joint_names=source_steps[0].door_joint_names,
    )
    return ReplayInputs(
        source_steps=source_steps,
        robot_joint_names=names,
        robot_xml=(prepared_root / "prepared" / "robot.xml").resolve(strict=True),
        robot_contract=robot_contract_path,
        armature_by_joint=dict(zip(names, armature, strict=True)),
        velocity_limit20=velocity_limit20,
        producer_custom_data=dict(producer_row["door_custom_data"]),
        producer_diagnostic_json=producer_diagnostic_json.resolve(strict=True),
        source_latch_mode=_source_latch_mode(source_steps[0].door_joint_names),
        source_plant_substeps=source_plant_substeps,
        source_plant_substep_trace=(
            producer_plant_substep_trace.resolve(strict=True)
            if producer_plant_substep_trace is not None
            else None
        ),
        source_plant_substep_schema=source_plant_schema,
        source_plant_substep_capability=source_plant_capability,
    )


def _source_case_row(custom: Mapping[str, Any]) -> dict[str, Any]:
    if int(custom["panelFrameSubpanels"]) != 0:
        raise RuntimeError("selected producer realization has panel subpanels and is not source-topology pairable")
    if bool(custom["spawnHook"]) or bool(custom["keyholePresent"]):
        raise RuntimeError("selected producer realization must omit optional hook and keyhole geometry")
    degrees_to_radians = math.pi / 180.0
    geometry = {
        "width_m": float(custom["doorWidth"]),
        "height_m": float(custom["doorHeight"]),
        "panel_mass_kg": float(custom["doorWeight"]),
        "panel_thickness_m": 0.04,
        "frame_width_m": float(custom["panelFrameWidth"]),
        "handle_height_m": float(custom["doorHandleHeight"]),
        "handle_edge_offset_m": float(custom["doorHandleWidth"]),
        "wall_height_m": float(custom["totalWallHeight"]),
        "axle_length_m": float(custom["axleLength"]),
        "handle_length_m": float(custom["handleLength"]),
        "hook_length_m": float(custom["hookLength"]),
        "handle_radius_m": float(custom["handleRadius"]),
        "cover_width_m": float(custom["coverWidth"]),
        "keyhole_height_offset_m": float(custom["keyholeHeightOffset"]),
        "hook_enabled": bool(custom["spawnHook"]),
        "keyhole_enabled": bool(custom["keyholePresent"]),
        "handle_type": str(custom["doorHandleType"]),
        "hinge_side": "right" if int(custom["doorOpenLR"]) == -1 else "left",
        "opening_direction": "out" if int(custom["doorOpenIO"]) == -1 else "in",
    }
    dynamics = {
        "damping_native": float(custom["hingeDriveDamping"]) * degrees_to_radians,
        "stiffness_native": float(custom["hingeDriveStiffness"]) * degrees_to_radians,
        "max_force_nm": float(custom["hingeDriveMaxForce"]),
        "panel_mass_kg": float(custom["doorWeight"]),
    }
    return {
        "case_id": "isaac_recorded_stage2_realization",
        "door_geometry": geometry,
        "door_dynamics_cell": dynamics,
    }


def _build_matched_scene(output: Path, inputs: ReplayInputs) -> tuple[Path, dict[str, Any]]:
    model_dir = output / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    row = _source_case_row(inputs.producer_custom_data)
    spec = DepthADDV3DoorFactory.from_case_row(row, latch_mode=inputs.source_latch_mode)
    spec.payload["dynamics"]["handle"]["effort_cap_nm"] = float(
        inputs.producer_custom_data["handleDriveMaxForce"]
    )
    spec.validate()
    door_xml = model_dir / "door.xml"
    door_receipt = model_dir / "door_receipt.json"
    DepthADDV3DoorBuilder(spec).write(door_xml, door_receipt)
    scene = model_dir / "scene.xml"
    scene_receipt = model_dir / "paired_scene_receipt.json"
    PairedSceneBuilderV2(
        inputs.robot_xml,
        door_xml,
        armature_by_joint=inputs.armature_by_joint,
        door_root_position=(0.0, 0.0, 0.0),
    ).write(scene, scene_receipt)
    pairing = {
        "status": "STRICT_RECORDED_JOINT_CONTROL_SURFACE_AND_INITIAL_CARTESIAN_KINEMATIC_PAIR",
        "producer_custom_data": dict(inputs.producer_custom_data),
        "materialized_case_row": row,
        "source_latch_mode": inputs.source_latch_mode,
        "source_door_root_position_m": [0.0, 0.0, 0.0],
        "source_door_root_position_authority": (
            "production TaskObjCfgDict['door'].init_state.pos; resolved eval config does not "
            "set a2_eval_door_asset_root_position"
        ),
        "robot_authority": str(inputs.robot_contract),
        "door_receipt": str(door_receipt),
        "scene_receipt": str(scene_receipt),
        "paired_dimensions": "same numeric robot/door joint state prefix, source door parameters, joint-name order, and final target20",
        "excluded_claim": "cross-engine drive/contact/collision-material/solver equivalence is not claimed",
    }
    _json_dump(model_dir / "stage2_pairing_receipt.json", pairing)
    return scene, pairing


def _reorder(values: np.ndarray, source_names: tuple[str, ...], target_names: tuple[str, ...]) -> np.ndarray:
    index = {name: offset for offset, name in enumerate(source_names)}
    return np.asarray([values[index[name]] for name in target_names], dtype=np.float64)


def _rotation_matrix_wxyz(quat: np.ndarray) -> np.ndarray:
    w, x, y, z = quat
    return np.asarray(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def _source_door_to_mujoco_names(source_names: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for name in source_names:
        lowered = name.lower()
        if "latch" in lowered:
            result.append("latch_slide")
        elif "handle" in lowered:
            result.append("handle_hinge")
        elif "hinge" in lowered:
            result.append("door_hinge")
        else:
            raise RuntimeError(f"cannot map producer door joint {name!r} to the MuJoCo realization")
    if len(set(result)) != len(result):
        raise RuntimeError(f"producer door joint mapping is ambiguous: {source_names}")
    return tuple(result)


def _joint_addresses(model: mujoco.MjModel, names: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    qpos: list[int] = []
    qvel: list[int] = []
    for name in names:
        joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint < 0:
            raise RuntimeError(f"matched scene lacks required joint {name!r}")
        qpos.append(int(model.jnt_qposadr[joint]))
        qvel.append(int(model.jnt_dofadr[joint]))
    return np.asarray(qpos, dtype=np.int32), np.asarray(qvel, dtype=np.int32)


def _run_kinematic_pairing_prefix(
    *, scene: Path, inputs: ReplayInputs, states: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    mapping = NameResolvedActuatorMapV2.from_model(model, inputs.robot_joint_names)
    source_door_names = _source_door_to_mujoco_names(inputs.source_steps[0].door_joint_names)
    door_qpos, _ = _joint_addresses(model, source_door_names)
    tcp_site = _site_id(model, "a2_piper_tcp")
    grasp_site = _site_id(model, "door_grasp_target")
    rows: list[dict[str, Any]] = []
    for source in inputs.source_steps[:states]:
        data.qpos[:3] = source.root_pos_rel3
        data.qpos[3:7] = source.root_quat_wxyz4
        data.qpos[mapping.robot_qpos_addresses] = _reorder(
            source.joint_pos20, source.joint_names, inputs.robot_joint_names
        )
        data.qpos[door_qpos] = source.door_joint_pos
        mujoco.mj_forward(model, data)
        tcp_to_grasp_world = data.site_xpos[grasp_site] - data.site_xpos[tcp_site]
        tcp_to_grasp_source = (
            data.site_xmat[tcp_site].reshape(3, 3).T @ tcp_to_grasp_world
        )
        vector_error = tcp_to_grasp_source - source.source_tcp_to_handle3
        distance = float(np.linalg.norm(tcp_to_grasp_world))
        rows.append(
            {
                "source_control_step": source.control_step,
                "tcp_to_grasp_source_frame_m": tcp_to_grasp_source.tolist(),
                "source_tcp_to_handle_source_frame_m": source.source_tcp_to_handle3.tolist(),
                "cartesian_vector_error_m": vector_error.tolist(),
                "cartesian_vector_error_norm_m": float(np.linalg.norm(vector_error)),
                "tcp_to_grasp_m": distance,
                "source_tcp_to_handle_m": source.source_tcp_to_handle_m,
                "cartesian_distance_gap_m": distance - source.source_tcp_to_handle_m,
            }
        )
    summary = {
        "method": "independently restore every recorded Isaac robot/door state, then MuJoCo mj_forward without dynamics",
        "states": len(rows),
        "first_source_control_step": rows[0]["source_control_step"],
        "last_source_control_step": rows[-1]["source_control_step"],
        "max_cartesian_vector_error_norm_m": float(
            max(row["cartesian_vector_error_norm_m"] for row in rows)
        ),
        "max_cartesian_distance_gap_abs_m": float(
            max(abs(row["cartesian_distance_gap_m"]) for row in rows)
        ),
    }
    return rows, summary


def _body_id(model: mujoco.MjModel, name: str) -> int:
    value = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    if value < 0:
        raise RuntimeError(f"compiled scene lacks required body {name!r}")
    return value


def _site_id(model: mujoco.MjModel, name: str) -> int:
    value = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
    if value < 0:
        raise RuntimeError(f"compiled scene lacks required site {name!r}")
    return value


def _contact_forces_world(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    finger_body_ids: tuple[int, int],
    handle_body_id: int,
) -> np.ndarray:
    forces = np.zeros((2, 3), dtype=np.float64)
    for index in range(data.ncon):
        contact = data.contact[index]
        body1 = int(model.geom_bodyid[contact.geom1])
        body2 = int(model.geom_bodyid[contact.geom2])
        if handle_body_id not in (body1, body2):
            continue
        wrench = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, index, wrench)
        world_force = contact.frame.reshape(3, 3).T @ wrench[:3]
        for finger_index, finger_body_id in enumerate(finger_body_ids):
            if body1 == finger_body_id:
                forces[finger_index] -= world_force
            if body2 == finger_body_id:
                forces[finger_index] += world_force
    return forces


def _finger_handle_normal_force_on_handle_world(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    finger_body_ids: tuple[int, int],
    handle_body_id: int,
) -> np.ndarray:
    """Return native normal-only contact force vectors on the handle body.

    ``mj_contactForce`` reports the wrench associated with its contact-frame
    orientation.  The body-side sign below is resolved from the contact pair,
    so this surface matches the source ContactSensor's declared
    ``force_on_handle_from_finger`` convention without deriving a synthetic
    contact from distances or a force proxy.
    """

    forces = np.zeros((2, 3), dtype=np.float64)
    for index in range(data.ncon):
        contact = data.contact[index]
        body1 = int(model.geom_bodyid[contact.geom1])
        body2 = int(model.geom_bodyid[contact.geom2])
        if handle_body_id not in (body1, body2):
            continue
        wrench = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, index, wrench)
        normal_world = contact.frame.reshape(3, 3).T[:, 0] * wrench[0]
        for finger_index, finger_body_id in enumerate(finger_body_ids):
            if body1 == finger_body_id and body2 == handle_body_id:
                forces[finger_index] += normal_world
            elif body2 == finger_body_id and body1 == handle_body_id:
                forces[finger_index] -= normal_world
    return forces


def _named_contact_wrenches(model: mujoco.MjModel, data: mujoco.MjData) -> list[dict[str, Any]]:
    """Export MuJoCo's native per-contact wrench surface after one physics step."""

    result: list[dict[str, Any]] = []
    for index in range(data.ncon):
        contact = data.contact[index]
        wrench_contact = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, index, wrench_contact)
        contact_to_world = contact.frame.reshape(3, 3).T
        geom1 = int(contact.geom1)
        geom2 = int(contact.geom2)
        body1 = int(model.geom_bodyid[geom1])
        body2 = int(model.geom_bodyid[geom2])
        result.append(
            {
                "contact_index": index,
                "geom1": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom1) or f"geom_{geom1}",
                "geom2": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom2) or f"geom_{geom2}",
                "body1": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body1) or f"body_{body1}",
                "body2": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body2) or f"body_{body2}",
                "distance_m": float(contact.dist),
                "position_world_m": contact.pos.tolist(),
                "frame_contact_to_world": contact.frame.tolist(),
                "force_torque_contact_frame": wrench_contact.tolist(),
                "force_world_n": (contact_to_world @ wrench_contact[:3]).tolist(),
                "torque_world_nm": (contact_to_world @ wrench_contact[3:]).tolist(),
                "wrench_semantics": "native mj_contactForce output; contact-frame axes are contact.frame",
            }
        )
    return result


def _same_name_vector_comparison(
    *, field: str, source: np.ndarray | None, mujoco_values: np.ndarray, unit: str
) -> dict[str, Any]:
    if source is None:
        return {
            "status": "NOT_AVAILABLE_SOURCE_FIELD",
            "field": field,
            "unit": unit,
        }
    delta = mujoco_values - source
    return {
        "status": "RUN_SAME_NAME_NUMERIC_COMPARISON",
        "field": field,
        "unit": unit,
        "error20": delta.tolist(),
        "max_abs_error": float(np.max(np.abs(delta))),
    }


def _source_contact_force_comparison(
    *,
    source: SourcePlantSubstep | None,
    mujoco_normal_force_on_handle_w_n: np.ndarray,
    capability: Mapping[str, Any],
) -> dict[str, Any]:
    if source is None:
        return {"status": "NOT_RUN_NO_SOURCE_SUBSTEP"}
    if source.finger_handle_normal_contact_force_on_handle_w_n is None:
        return {"status": "NOT_AVAILABLE_SOURCE_FIELD"}
    source_capability = capability.get("finger_handle_normal_contact_force_on_handle_w_N")
    if not (
        isinstance(source_capability, Mapping)
        and source_capability.get("status") == "DIRECT_CONTACT_SENSOR_FORCE_MATRIX"
        and source_capability.get("semantics")
        == "normal_force_on_handle_from_finger_world_N; ContactSensor.force_matrix_w filtered in [arm_body7, arm_body8] order."
    ):
        return {
            "status": "NOT_COMPARABLE_CONTACT_FORCE_SEMANTICS_UNDECLARED",
            "source_capability": source_capability,
        }
    delta = mujoco_normal_force_on_handle_w_n - source.finger_handle_normal_contact_force_on_handle_w_n
    return {
        "status": "RUN_SAME_FINGER_HANDLE_NORMAL_WORLD_FORCE_COMPARISON",
        "unit": "N",
        "error2x3": delta.tolist(),
        "max_abs_error": float(np.max(np.abs(delta))),
    }


def _substep_attribution_telemetry(
    *,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    mapping: NameResolvedActuatorMapV2,
    finger_ids: tuple[int, int],
    handle_body: int,
    door_qpos: np.ndarray,
    door_qvel: np.ndarray,
    source: SourcePlantSubstep | None,
    source_joint_names: tuple[str, ...],
    capability: Mapping[str, Any],
    projection: VelocityRealizationTelemetry,
    velocity_realization: str,
    plant_realization: Mapping[str, Any],
    raw_target20: np.ndarray,
    drive_target20: np.ndarray,
) -> dict[str, Any]:
    robot_qpos = data.qpos[mapping.robot_qpos_addresses].copy()
    robot_qvel = data.qvel[mapping.robot_qvel_addresses].copy()
    actuator_force = projection.native_actuator_force20
    qfrc_actuator = projection.native_qfrc_actuator20_nm
    qfrc_constraint = projection.native_qfrc_constraint20_nm
    force_on_finger_w = _contact_forces_world(
        model, data, finger_body_ids=finger_ids, handle_body_id=handle_body
    )
    normal_force_on_handle_w = _finger_handle_normal_force_on_handle_world(
        model, data, finger_body_ids=finger_ids, handle_body_id=handle_body
    )
    if source is None:
        source_comparison: dict[str, Any] = {"status": "NOT_RUN_NO_SOURCE_SUBSTEP"}
    else:
        source_qpos = _reorder(source.joint_pos20, source_joint_names, mapping.robot_joint_names)
        source_qvel = _reorder(source.joint_vel20, source_joint_names, mapping.robot_joint_names)
        source_target = _reorder(source.final_target20, source_joint_names, mapping.robot_joint_names)
        source_effort = (
            None
            if source.applied_effort20_nm is None
            else _reorder(source.applied_effort20_nm, source_joint_names, mapping.robot_joint_names)
        )
        source_comparison = {
            "status": "RUN",
            "robot_joint_pos20_rad": _same_name_vector_comparison(
                field="robot_joint_pos20_rad", source=source_qpos, mujoco_values=robot_qpos, unit="rad"
            ),
            "robot_joint_vel20_rad_s": _same_name_vector_comparison(
                field="robot_joint_vel20_rad_s", source=source_qvel, mujoco_values=robot_qvel, unit="rad/s"
            ),
            "final_joint_position_target20_rad": _same_name_vector_comparison(
                field="final_joint_position_target20_rad",
                source=source_target,
                mujoco_values=raw_target20,
                unit="rad",
            ),
            "applied_effort20_Nm_vs_mujoco_actuator_force20": _same_name_vector_comparison(
                field="applied_effort20_Nm_vs_mujoco_actuator_force20",
                source=source_effort,
                mujoco_values=actuator_force,
                unit="N*m",
            ),
            "finger_handle_normal_contact_force_on_handle_w_N": _source_contact_force_comparison(
                source=source,
                mujoco_normal_force_on_handle_w_n=normal_force_on_handle_w,
                capability=capability,
            ),
            "joint_constraint_impulse20_Ns": {
                "status": "NOT_COMPARABLE_MUJOCO_EXPORT_IS_QFRC_CONSTRAINT_FORCE_NOT_IMPULSE",
                "mujoco_available_field": "qfrc_constraint20_Nm",
            },
            "contact_torque": {"status": "NOT_AVAILABLE_SOURCE_FIELD"},
        }
    return {
        "mujoco_engine_local": {
            "post_projection_state": {
                "robot_joint_pos20_rad": robot_qpos.tolist(),
                "robot_joint_vel20_rad_s": robot_qvel.tolist(),
            },
            "native_pre_projection_endpoint": {
                "robot_joint_pos20_rad": projection.native_qpos20.tolist(),
                "robot_joint_vel20_rad_s": projection.native_qvel20.tolist(),
                "actuator_force20": actuator_force.tolist(),
                "qfrc_actuator20_Nm": qfrc_actuator.tolist(),
                "qfrc_constraint20_Nm": qfrc_constraint.tolist(),
                "qacc20_rad_s2": projection.native_qacc20_rad_s2.tolist(),
                "qfrc_passive20_Nm": projection.native_qfrc_passive20_nm.tolist(),
                "qfrc_smooth20_Nm": projection.native_qfrc_smooth20_nm.tolist(),
                "velocity_limit_max_ratio": projection.native_max_velocity_limit_ratio,
            },
            "endpoint_velocity_projection": {
                "realization": velocity_realization,
                "applied": velocity_realization == VELOCITY_REALIZATION_ENDPOINT_PROJECTION,
                "qpos_correction20_rad": projection.applied_qpos_correction20.tolist(),
                "mask20": projection.applied_mask20.tolist(),
                "count": projection.applied_count,
                "post_realization_velocity_limit_max_ratio": projection.realized_max_velocity_limit_ratio,
                "theoretical_qpos_correction20_rad": projection.theoretical_qpos_correction20.tolist(),
                "theoretical_mask20": projection.theoretical_mask20.tolist(),
                "theoretical_count": projection.theoretical_count,
                "theoretical_projected_velocity_limit_max_ratio": projection.theoretical_projected_max_velocity_limit_ratio,
            },
            "raw_target20_rad": raw_target20.tolist(),
            "drive_target20_rad": drive_target20.tolist(),
            "plant_realization": dict(plant_realization),
            "door_joint_pos": data.qpos[door_qpos].tolist(),
            "door_joint_vel": data.qvel[door_qvel].tolist(),
            "finger_handle_contact_force_on_finger_world_N": force_on_finger_w.tolist(),
            "finger_handle_normal_contact_force_on_handle_world_N": normal_force_on_handle_w.tolist(),
            "contact_wrenches": _named_contact_wrenches(model, data),
            "contact_count": int(data.ncon),
            "constraint_surface": "qfrc_constraint is MuJoCo generalized constraint force, not a solver impulse",
        },
        "source_comparison": source_comparison,
    }


def _telemetry(
    *,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    mapping: NameResolvedActuatorMapV2,
    tcp_site: int,
    grasp_site: int,
    finger_ids: tuple[int, int],
    handle_body: int,
    door_qpos: np.ndarray,
    door_qvel: np.ndarray,
    source_step: SourceStage2Step,
) -> dict[str, Any]:
    tcp = data.site_xpos[tcp_site].copy()
    grasp = data.site_xpos[grasp_site].copy()
    forces_world = _contact_forces_world(
        model, data, finger_body_ids=finger_ids, handle_body_id=handle_body
    )
    forces_source = forces_world @ data.site_xmat[tcp_site].reshape(3, 3)
    force_norm = np.linalg.norm(forces_source, axis=1)
    squeeze_y = forces_source[:, 1]
    robot_q = data.qpos[mapping.robot_qpos_addresses].copy()
    robot_qd = data.qvel[mapping.robot_qvel_addresses].copy()
    expected_q = _reorder(source_step.joint_pos20, source_step.joint_names, mapping.robot_joint_names)
    expected_qd = _reorder(source_step.joint_vel20, source_step.joint_names, mapping.robot_joint_names)
    root_position_error = data.qpos[:3] - source_step.root_pos_rel3
    tcp_to_grasp_world = grasp - tcp
    tcp_to_grasp_source = data.site_xmat[tcp_site].reshape(3, 3).T @ tcp_to_grasp_world
    tcp_to_grasp = float(np.linalg.norm(tcp_to_grasp_world))
    cartesian_vector_error = tcp_to_grasp_source - source_step.source_tcp_to_handle3
    quaternion_dot = abs(float(np.dot(data.qpos[3:7], source_step.root_quat_wxyz4)))
    quaternion_dot = min(1.0, max(-1.0, quaternion_dot))
    return {
        "source_control_step": source_step.control_step,
        "tcp_position_world_m": tcp.tolist(),
        "grasp_target_world_m": grasp.tolist(),
        "tcp_to_grasp_source_frame_m": tcp_to_grasp_source.tolist(),
        "source_tcp_to_handle_source_frame_m": source_step.source_tcp_to_handle3.tolist(),
        "cartesian_vector_error_m": cartesian_vector_error.tolist(),
        "cartesian_vector_error_norm_m": float(np.linalg.norm(cartesian_vector_error)),
        "tcp_to_grasp_m": tcp_to_grasp,
        "source_tcp_to_handle_m": source_step.source_tcp_to_handle_m,
        "cartesian_distance_gap_m": tcp_to_grasp - source_step.source_tcp_to_handle_m,
        "handle_contact_force_world_n": forces_world.tolist(),
        "handle_contact_force_source_n": forces_source.tolist(),
        "handle_contact_force_norm_source_n": force_norm.tolist(),
        "squeeze_y_source_n": squeeze_y.tolist(),
        "both_contact_force_gt_1n": bool(np.all(force_norm > 1.0)),
        "valid_opposed_squeeze_gt_2n": bool(
            np.all(np.abs(squeeze_y) > 2.0) and squeeze_y[0] * squeeze_y[1] < 0.0
        ),
        "robot_joint_pos20": robot_q.tolist(),
        "robot_joint_vel20": robot_qd.tolist(),
        "door_joint_pos": data.qpos[door_qpos].tolist(),
        "door_joint_vel": data.qvel[door_qvel].tolist(),
        "state_error": {
            "root_position_norm_m": float(np.linalg.norm(root_position_error)),
            "root_orientation_angle_rad": float(2.0 * math.acos(quaternion_dot)),
            "robot_joint_pos_max_abs_rad": float(np.max(np.abs(robot_q - expected_q))),
            "robot_joint_vel_max_abs_rad_s": float(np.max(np.abs(robot_qd - expected_qd))),
            "door_joint_pos_max_abs": float(
                np.max(np.abs(data.qpos[door_qpos] - source_step.door_joint_pos))
            ),
            "door_joint_vel_max_abs": float(
                np.max(np.abs(data.qvel[door_qvel] - source_step.door_joint_vel))
            ),
        },
    }


def _restore_source_state(
    *,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    mapping: NameResolvedActuatorMapV2,
    source: SourceStage2Step,
    target_joint_names: tuple[str, ...],
    door_qpos: np.ndarray,
    door_qvel: np.ndarray,
    zero_velocity: bool = False,
) -> None:
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    if home < 0:
        raise RuntimeError("matched scene lacks scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home)
    data.qpos[:3] = source.root_pos_rel3
    data.qpos[3:7] = source.root_quat_wxyz4
    data.qpos[mapping.robot_qpos_addresses] = _reorder(
        source.joint_pos20, source.joint_names, target_joint_names
    )
    data.qpos[door_qpos] = source.door_joint_pos
    if not zero_velocity:
        data.qvel[:3] = source.root_lin_vel_w3
        data.qvel[3:6] = _rotation_matrix_wxyz(source.root_quat_wxyz4).T @ source.root_ang_vel_w3
        data.qvel[mapping.robot_qvel_addresses] = _reorder(
            source.joint_vel20, source.joint_names, target_joint_names
        )
        data.qvel[door_qvel] = source.door_joint_vel
    mujoco.mj_forward(model, data)


def _configure_plant_variant(
    *, model: mujoco.MjModel, mapping: NameResolvedActuatorMapV2, plant_variant: str
) -> dict[str, Any]:
    """Realize one declared actuator/damping force path in the compiled model."""

    if plant_variant not in (
        PLANT_VARIANT_BASELINE,
        PLANT_VARIANT_JOINT_DAMPING_FORCE_PATH,
        PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET,
        PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT,
        PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09,
    ):
        raise ValueError(f"unsupported plant variant: {plant_variant}")
    joints: list[dict[str, Any]] = []
    for name, actuator_id, dof_id in zip(
        mapping.robot_joint_names,
        mapping.robot_actuator_ids,
        mapping.robot_qvel_addresses,
        strict=True,
    ):
        velocity_bias_before = float(model.actuator_biasprm[actuator_id, 2])
        damping_before = float(model.dof_damping[dof_id])
        if plant_variant == PLANT_VARIANT_JOINT_DAMPING_FORCE_PATH:
            if velocity_bias_before >= 0.0:
                raise RuntimeError(
                    f"{name} actuator affine velocity bias must be negative, got {velocity_bias_before}"
                )
            model.actuator_biasprm[actuator_id, 2] = 0.0
            model.dof_damping[dof_id] = damping_before - velocity_bias_before
        joints.append(
            {
                "joint": name,
                "actuator": mapping.robot_actuator_names[len(joints)],
                "affine_bias_velocity_before": velocity_bias_before,
                "affine_bias_velocity_after": float(model.actuator_biasprm[actuator_id, 2]),
                "dof_damping_before": damping_before,
                "dof_damping_after": float(model.dof_damping[dof_id]),
            }
        )
    return {
        "plant_variant": plant_variant,
        "semantics": (
            "baseline retains actuator affine velocity bias"
            if plant_variant == PLANT_VARIANT_BASELINE
            else (
                "moves -affine_bias_velocity KD from each robot actuator into its joint dof_damping"
                if plant_variant == PLANT_VARIANT_JOINT_DAMPING_FORCE_PATH
                else (
                    "shapes position-actuator targets per physics substep without changing model gain, damping, armature, geometry, friction, or solver"
                    if plant_variant == PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET
                    else (
                        "shapes position-actuator targets and realizes the fixed MuJoCo contact solref diagnostic on both fingers and the handle"
                        if plant_variant == PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT
                        else "shapes position-actuator targets, realizes fixed MuJoCo contact solref, and applies source-grounded moving-contact dynamic friction 0.9 on both fingers and the handle"
                    )
                )
            )
        ),
        "position_target_realization": (
            {
                "mode": plant_variant,
                "formula": "drive_target20 = qpos20 + clip(raw_target20 - qpos20, -velocity_limit20 * KD20 / KP20, +velocity_limit20 * KD20 / KP20)",
                "boundary": "MuJoCo diagnostic target realization only; not a PhysX maxJointVelocity or actuator-equivalence claim",
            }
            if plant_variant
            in (
                PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET,
                PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT,
                PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09,
            )
            else {"mode": "raw_position_target"}
        ),
        "contact_impedance_realization": configure_depthadd_v3_contact_solref_2dt(model)
        if plant_variant
        in (
            PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT,
            PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09,
        )
        else {"status": "NOT_APPLIED"},
        "contact_friction_realization": _configure_contact_friction09(model)
        if plant_variant
        == PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09
        else {"status": "NOT_APPLIED"},
        "joints": joints,
    }


def _configure_contact_friction09(model: mujoco.MjModel) -> dict[str, Any]:
    """Apply the source-grounded moving-contact dynamic-friction diagnostic."""

    target_body_ids = {
        _body_id(model, "arm_body7"),
        _body_id(model, "arm_body8"),
        _body_id(model, "door_handle"),
    }
    geoms: list[dict[str, Any]] = []
    for geom_id, body_id in enumerate(model.geom_bodyid):
        if int(body_id) not in target_body_ids:
            continue
        if int(model.geom_contype[geom_id]) == 0 and int(model.geom_conaffinity[geom_id]) == 0:
            continue
        before = model.geom_friction[geom_id].copy()
        model.geom_friction[geom_id, 0] = 0.9
        geoms.append(
            {
                "geom": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id)
                or f"geom_{geom_id}",
                "body": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(body_id))
                or f"body_{body_id}",
                "friction_before": before.tolist(),
                "friction_after": model.geom_friction[geom_id].tolist(),
            }
        )
    if not geoms:
        raise RuntimeError("contact friction diagnostic found no finger/handle collision geoms")
    return {
        "status": "MOVING_CONTACT_DYNAMIC_FRICTION_DIAGNOSTIC",
        "authority": "resolved production a2_m39_gripper_material_enabled=true; M39 dynamic friction=0.9",
        "boundary": "MuJoCo has no static/dynamic friction split; this is not a PhysX material-equivalence claim",
        "sliding_friction": 0.9,
        "torsional_friction": "UNCHANGED",
        "rolling_friction": "UNCHANGED",
        "solimp": "UNCHANGED",
        "geometry": "UNCHANGED",
        "geoms": geoms,
    }


def _realize_position_target(
    *,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    mapping: NameResolvedActuatorMapV2,
    raw_target20: np.ndarray,
    velocity_limit20: np.ndarray,
    plant_variant: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return the direct-actuator target for this physics substep."""

    raw_target = np.asarray(raw_target20, dtype=np.float64)
    if raw_target.shape != (20,):
        raise ValueError(f"raw position target has shape {raw_target.shape}, expected (20,)")
    if plant_variant not in (
        PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET,
        PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT,
        PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09,
    ):
        return raw_target, {
            "mode": "raw_position_target",
            "mask20": [False] * 20,
            "count": 0,
            "max_abs_delta_rad": 0.0,
        }
    target = mapping.realize_velocity_limited_pd_target(
        model, data, raw_target, velocity_limit20
    )
    return target.drive_target20, {
        "mode": plant_variant,
        "formula": "drive_target20 = qpos20 + clip(raw_target20 - qpos20, -velocity_limit20 * KD20 / KP20, +velocity_limit20 * KD20 / KP20)",
        "kp20": target.kp20.tolist(),
        "kd20": target.kd20.tolist(),
        "maximum_delta20_rad": target.maximum_delta20_rad.tolist(),
        "mask20": target.shaping_mask20.tolist(),
        "count": target.shaping_count,
        "max_abs_delta_rad": target.max_abs_delta_rad,
    }


def _step_with_velocity_realization(
    *,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    mapping: NameResolvedActuatorMapV2,
    velocity_limit20: np.ndarray,
    velocity_realization: str,
) -> VelocityRealizationTelemetry:
    """Advance native MuJoCo once and optionally apply the declared endpoint projection.

    The native realization never mutates qpos/qvel after ``mj_step``.  It still
    exports the projection that would have been required under the declared
    endpoint surface, so its numerical exposure is directly comparable.
    """

    if velocity_realization not in (
        VELOCITY_REALIZATION_ENDPOINT_PROJECTION,
        VELOCITY_REALIZATION_NATIVE,
    ):
        raise ValueError(f"unsupported velocity realization: {velocity_realization}")
    limits = np.asarray(velocity_limit20, dtype=np.float64)
    if limits.shape != (20,) or not np.isfinite(limits).all() or np.any(limits <= 0.0):
        raise ValueError("velocity realization requires finite positive velocity_limit20[20]")
    mujoco.mj_step(model, data)
    native_qpos20 = data.qpos[mapping.robot_qpos_addresses].copy()
    native_qvel20 = data.qvel[mapping.robot_qvel_addresses].copy()
    native_actuator_force20 = mapping.robot_actuator_force(data)
    native_qfrc_actuator20_nm = mapping.robot_generalized_force(data)
    native_qfrc_constraint20_nm = data.qfrc_constraint[mapping.robot_qvel_addresses].copy()
    native_qacc20_rad_s2 = data.qacc[mapping.robot_qvel_addresses].copy()
    native_qfrc_passive20_nm = data.qfrc_passive[mapping.robot_qvel_addresses].copy()
    native_qfrc_smooth20_nm = data.qfrc_smooth[mapping.robot_qvel_addresses].copy()
    native_values = (
        native_qpos20,
        native_qvel20,
        native_actuator_force20,
        native_qfrc_actuator20_nm,
        native_qfrc_constraint20_nm,
        native_qacc20_rad_s2,
        native_qfrc_passive20_nm,
        native_qfrc_smooth20_nm,
    )
    if not all(np.isfinite(values).all() for values in native_values):
        raise FloatingPointError("native MuJoCo endpoint telemetry is non-finite")
    theoretical_projected_qvel20 = np.clip(native_qvel20, -limits, limits)
    theoretical_qpos_correction20 = (
        theoretical_projected_qvel20 - native_qvel20
    ) * float(model.opt.timestep)
    theoretical_mask20 = theoretical_projected_qvel20 != native_qvel20
    if velocity_realization == VELOCITY_REALIZATION_ENDPOINT_PROJECTION and np.any(
        theoretical_mask20
    ):
        data.qvel[mapping.robot_qvel_addresses] = theoretical_projected_qvel20
        data.qpos[mapping.robot_qpos_addresses] = native_qpos20 + theoretical_qpos_correction20
        mujoco.mj_forward(model, data)
    applied = velocity_realization == VELOCITY_REALIZATION_ENDPOINT_PROJECTION
    return VelocityRealizationTelemetry(
        native_qpos20=native_qpos20,
        native_qvel20=native_qvel20,
        realized_qvel20=data.qvel[mapping.robot_qvel_addresses].copy(),
        applied_qpos_correction20=(
            theoretical_qpos_correction20 if applied else np.zeros(20, dtype=np.float64)
        ),
        applied_mask20=(theoretical_mask20 if applied else np.zeros(20, dtype=bool)),
        applied_count=int(np.count_nonzero(theoretical_mask20)) if applied else 0,
        theoretical_projected_qvel20=theoretical_projected_qvel20,
        theoretical_qpos_correction20=theoretical_qpos_correction20,
        theoretical_mask20=theoretical_mask20,
        theoretical_count=int(np.count_nonzero(theoretical_mask20)),
        native_max_velocity_limit_ratio=float(np.max(np.abs(native_qvel20) / limits)),
        realized_max_velocity_limit_ratio=float(
            np.max(np.abs(data.qvel[mapping.robot_qvel_addresses]) / limits)
        ),
        theoretical_projected_max_velocity_limit_ratio=float(
            np.max(np.abs(theoretical_projected_qvel20) / limits)
        ),
        native_actuator_force20=native_actuator_force20,
        native_qfrc_actuator20_nm=native_qfrc_actuator20_nm,
        native_qfrc_constraint20_nm=native_qfrc_constraint20_nm,
        native_qacc20_rad_s2=native_qacc20_rad_s2,
        native_qfrc_passive20_nm=native_qfrc_passive20_nm,
        native_qfrc_smooth20_nm=native_qfrc_smooth20_nm,
    )


def _step_position_target(
    *,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    mapping: NameResolvedActuatorMapV2,
    target: np.ndarray,
    velocity_limit20: np.ndarray,
    source_control_step: int,
    source_plant_substeps: Mapping[tuple[int, int], SourcePlantSubstep],
    source_joint_names: tuple[str, ...],
    source_plant_capability: Mapping[str, Any],
    finger_ids: tuple[int, int],
    handle_body: int,
    door_qpos: np.ndarray,
    door_qvel: np.ndarray,
    velocity_realization: str,
    plant_realization: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for physics_substep in range(PHYSICS_STEPS_PER_CONTROL):
        drive_target20, target_realization = _realize_position_target(
            model=model,
            data=data,
            mapping=mapping,
            raw_target20=target,
            velocity_limit20=velocity_limit20,
            plant_variant=str(plant_realization["plant_variant"]),
        )
        mapping.write_robot_position_target(data, drive_target20)
        projection = _step_with_velocity_realization(
            model=model,
            data=data,
            mapping=mapping,
            velocity_limit20=velocity_limit20,
            velocity_realization=velocity_realization,
        )
        velocity = data.qvel[mapping.robot_qvel_addresses].copy()
        ratio = np.abs(velocity) / velocity_limit20
        rows.append(
            {
                "physics_substep": physics_substep,
                "sample_timing": "after native MuJoCo mj_step and the selected velocity realization; mj_forward refresh occurs only after applied endpoint projection",
                "raw_target20_rad": target.tolist(),
                "drive_target20_rad": drive_target20.tolist(),
                "target_shaping": target_realization,
                "robot_joint_vel20": velocity.tolist(),
                "velocity_limit_ratio20": ratio.tolist(),
                "velocity_limit_max_ratio": float(np.max(ratio)),
                "native_pre_projection_robot_joint_vel20": projection.native_qvel20.tolist(),
                "native_pre_projection_velocity_limit_max_ratio": projection.native_max_velocity_limit_ratio,
                "endpoint_velocity_projection_count": projection.applied_count,
                "endpoint_velocity_projection_mask20": projection.applied_mask20.tolist(),
                "endpoint_qpos_correction20_rad": projection.applied_qpos_correction20.tolist(),
                "theoretical_endpoint_velocity_projection_count": projection.theoretical_count,
                "theoretical_endpoint_velocity_projection_mask20": projection.theoretical_mask20.tolist(),
                "theoretical_endpoint_qpos_correction20_rad": projection.theoretical_qpos_correction20.tolist(),
                "native_pre_projection_actuator_force20": projection.native_actuator_force20.tolist(),
                "native_pre_projection_qfrc_actuator20_Nm": projection.native_qfrc_actuator20_nm.tolist(),
                "native_pre_projection_qfrc_constraint20_Nm": projection.native_qfrc_constraint20_nm.tolist(),
                "native_pre_projection_qacc20_rad_s2": projection.native_qacc20_rad_s2.tolist(),
                "native_pre_projection_qfrc_passive20_Nm": projection.native_qfrc_passive20_nm.tolist(),
                "native_pre_projection_qfrc_smooth20_Nm": projection.native_qfrc_smooth20_nm.tolist(),
                "velocity_limit_realization": velocity_realization,
                "plant_realization": dict(plant_realization),
                **_substep_attribution_telemetry(
                    model=model,
                    data=data,
                    mapping=mapping,
                    finger_ids=finger_ids,
                    handle_body=handle_body,
                    door_qpos=door_qpos,
                    door_qvel=door_qvel,
                    source=source_plant_substeps.get((source_control_step, physics_substep)),
                    source_joint_names=source_joint_names,
                    capability=source_plant_capability,
                    projection=projection,
                    velocity_realization=velocity_realization,
                    plant_realization=plant_realization,
                    raw_target20=target,
                    drive_target20=drive_target20,
                ),
            }
        )
    return rows


def _run_state_reset_one_control_residuals(
    *,
    scene: Path,
    inputs: ReplayInputs,
    transitions: int,
    velocity_realization: str,
    plant_variant: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    mapping = NameResolvedActuatorMapV2.from_model(model, inputs.robot_joint_names)
    plant_realization = _configure_plant_variant(
        model=model, mapping=mapping, plant_variant=plant_variant
    )
    source_door_names = _source_door_to_mujoco_names(inputs.source_steps[0].door_joint_names)
    door_qpos, door_qvel = _joint_addresses(model, source_door_names)
    tcp_site = _site_id(model, "a2_piper_tcp")
    grasp_site = _site_id(model, "door_grasp_target")
    finger_ids = (_body_id(model, "arm_body7"), _body_id(model, "arm_body8"))
    handle_body = _body_id(model, "door_handle")
    rows: list[dict[str, Any]] = []
    for index in range(transitions):
        previous = inputs.source_steps[index]
        expected = inputs.source_steps[index + 1]
        _restore_source_state(
            model=model,
            data=data,
            mapping=mapping,
            source=previous,
            target_joint_names=inputs.robot_joint_names,
            door_qpos=door_qpos,
            door_qvel=door_qvel,
        )
        target = _reorder(expected.final_target20, expected.joint_names, inputs.robot_joint_names)
        substeps = _step_position_target(
            model=model,
            data=data,
            mapping=mapping,
            target=target,
            velocity_limit20=inputs.velocity_limit20,
            source_control_step=expected.control_step,
            source_plant_substeps=inputs.source_plant_substeps,
            source_joint_names=inputs.source_steps[0].joint_names,
            source_plant_capability=inputs.source_plant_substep_capability,
            finger_ids=finger_ids,
            handle_body=handle_body,
            door_qpos=door_qpos,
            door_qvel=door_qvel,
            velocity_realization=velocity_realization,
            plant_realization=plant_realization,
        )
        actual_q = data.qpos[mapping.robot_qpos_addresses].copy()
        actual_qd = data.qvel[mapping.robot_qvel_addresses].copy()
        expected_q = _reorder(expected.joint_pos20, expected.joint_names, inputs.robot_joint_names)
        expected_qd = _reorder(expected.joint_vel20, expected.joint_names, inputs.robot_joint_names)
        rows.append(
            {
                "source_from_control_step": previous.control_step,
                "source_to_control_step": expected.control_step,
                "robot_joint_position_error20": (actual_q - expected_q).tolist(),
                "robot_joint_velocity_error20": (actual_qd - expected_qd).tolist(),
                "substeps": substeps,
                **_telemetry(
                    model=model,
                    data=data,
                    mapping=mapping,
                    tcp_site=tcp_site,
                    grasp_site=grasp_site,
                    finger_ids=finger_ids,
                    handle_body=handle_body,
                    door_qpos=door_qpos,
                    door_qvel=door_qvel,
                    source_step=expected,
                ),
            }
        )
    position_errors = np.abs(
        np.asarray([row["robot_joint_position_error20"] for row in rows], dtype=np.float64)
    )
    velocity_errors = np.abs(
        np.asarray([row["robot_joint_velocity_error20"] for row in rows], dtype=np.float64)
    )
    all_substeps = [substep for row in rows for substep in row["substeps"]]
    native_ratio_by_joint = np.asarray(
        [
            np.abs(np.asarray(substep["native_pre_projection_robot_joint_vel20"], dtype=np.float64))
            / inputs.velocity_limit20
            for substep in all_substeps
        ],
        dtype=np.float64,
    )
    theoretical_correction_by_joint = np.asarray(
        [substep["theoretical_endpoint_qpos_correction20_rad"] for substep in all_substeps],
        dtype=np.float64,
    )
    max_position_by_joint = np.max(position_errors, axis=0)
    max_velocity_by_joint = np.max(velocity_errors, axis=0)
    partitions: dict[str, Any] = {}
    for name, selected in (
        ("pre_contact_through_step104", [row for row in rows if row["source_to_control_step"] <= 104]),
        ("first_contact_step105", [row for row in rows if row["source_to_control_step"] == 105]),
        ("recorded_contact_steps106_110", [row for row in rows if row["source_to_control_step"] >= 106]),
    ):
        selected_position = np.abs(
            np.asarray([row["robot_joint_position_error20"] for row in selected], dtype=np.float64)
        )
        selected_substeps = [substep for row in selected for substep in row["substeps"]]
        partitions[name] = {
            "transitions": len(selected),
            "max_robot_joint_position_error_rad": float(np.max(selected_position)),
            "worst_robot_joint": inputs.robot_joint_names[
                int(np.unravel_index(np.argmax(selected_position), selected_position.shape)[1])
            ],
            "max_velocity_limit_ratio": float(
                max(substep["velocity_limit_max_ratio"] for substep in selected_substeps)
            ),
        }
    summary = {
        "method": "independently restore each Isaac state, apply the next recorded final_target20 for four MuJoCo physics steps under the declared velocity/plant realization",
        "transitions": len(rows),
        "max_robot_joint_position_error_by_name": dict(
            zip(inputs.robot_joint_names, max_position_by_joint.tolist(), strict=True)
        ),
        "max_robot_joint_velocity_error_by_name": dict(
            zip(inputs.robot_joint_names, max_velocity_by_joint.tolist(), strict=True)
        ),
        "max_velocity_limit_ratio": float(
            max(substep["velocity_limit_max_ratio"] for substep in all_substeps)
        ),
        "velocity_limit_exceeded_substeps": int(
            sum(substep["velocity_limit_max_ratio"] > 1.0 for substep in all_substeps)
        ),
        "max_native_velocity_limit_ratio_by_name": dict(
            zip(inputs.robot_joint_names, np.max(native_ratio_by_joint, axis=0).tolist(), strict=True)
        ),
        "max_theoretical_endpoint_qpos_correction_abs_rad_by_name": dict(
            zip(
                inputs.robot_joint_names,
                np.max(np.abs(theoretical_correction_by_joint), axis=0).tolist(),
                strict=True,
            )
        ),
        "theoretical_projection_required_substeps": int(
            sum(substep["theoretical_endpoint_velocity_projection_count"] > 0 for substep in all_substeps)
        ),
        "velocity_limit_realization": velocity_realization,
        "plant_realization": plant_realization,
        "partitions": partitions,
    }
    return rows, summary


def _run_fixed_pregrasp_close_hold(
    *,
    scene: Path,
    inputs: ReplayInputs,
    velocity_realization: str,
    plant_variant: str,
    controls: int = 10,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_step = {source.control_step: source for source in inputs.source_steps}
    if 104 not in by_step or 105 not in by_step:
        raise RuntimeError("fixed pregrasp microexperiment requires authority steps 104 and 105")
    source = by_step[104]
    close = by_step[105]
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    mapping = NameResolvedActuatorMapV2.from_model(model, inputs.robot_joint_names)
    plant_realization = _configure_plant_variant(
        model=model, mapping=mapping, plant_variant=plant_variant
    )
    source_door_names = _source_door_to_mujoco_names(source.door_joint_names)
    door_qpos, door_qvel = _joint_addresses(model, source_door_names)
    tcp_site = _site_id(model, "a2_piper_tcp")
    finger_ids = (_body_id(model, "arm_body7"), _body_id(model, "arm_body8"))
    handle_body = _body_id(model, "door_handle")
    _restore_source_state(
        model=model,
        data=data,
        mapping=mapping,
        source=source,
        target_joint_names=inputs.robot_joint_names,
        door_qpos=door_qpos,
        door_qvel=door_qvel,
        zero_velocity=True,
    )
    target = _reorder(source.joint_pos20, source.joint_names, inputs.robot_joint_names)
    close_target = _reorder(close.final_target20, close.joint_names, inputs.robot_joint_names)
    target[18:20] = close_target[18:20]
    rows: list[dict[str, Any]] = []
    streak = 0
    max_streak = 0
    for control_step in range(controls):
        max_force = np.zeros(2, dtype=np.float64)
        min_contact_distance: float | None = None
        substeps = []
        for substep in range(PHYSICS_STEPS_PER_CONTROL):
            drive_target20, target_realization = _realize_position_target(
                model=model,
                data=data,
                mapping=mapping,
                raw_target20=target,
                velocity_limit20=inputs.velocity_limit20,
                plant_variant=str(plant_realization["plant_variant"]),
            )
            mapping.write_robot_position_target(data, drive_target20)
            projection = _step_with_velocity_realization(
                model=model,
                data=data,
                mapping=mapping,
                velocity_limit20=inputs.velocity_limit20,
                velocity_realization=velocity_realization,
            )
            force_world = _contact_forces_world(
                model, data, finger_body_ids=finger_ids, handle_body_id=handle_body
            )
            max_force = np.maximum(max_force, np.linalg.norm(force_world, axis=1))
            distances = []
            for contact_index in range(data.ncon):
                contact = data.contact[contact_index]
                bodies = {
                    int(model.geom_bodyid[contact.geom1]),
                    int(model.geom_bodyid[contact.geom2]),
                }
                if handle_body in bodies and any(finger in bodies for finger in finger_ids):
                    distances.append(float(contact.dist))
            if distances:
                value = min(distances)
                min_contact_distance = value if min_contact_distance is None else min(min_contact_distance, value)
            velocity = data.qvel[mapping.robot_qvel_addresses]
            substeps.append(
                {
                    "physics_substep": substep,
                    "raw_target20_rad": target.tolist(),
                    "drive_target20_rad": drive_target20.tolist(),
                    "target_shaping": target_realization,
                    "velocity_limit_max_ratio": float(
                        np.max(np.abs(velocity) / inputs.velocity_limit20)
                    ),
                    "native_pre_projection_velocity_limit_max_ratio": projection.native_max_velocity_limit_ratio,
                    "endpoint_velocity_projection_count": projection.applied_count,
                    "endpoint_velocity_projection_mask20": projection.applied_mask20.tolist(),
                    "endpoint_qpos_correction20_rad": projection.applied_qpos_correction20.tolist(),
                    "theoretical_endpoint_velocity_projection_count": projection.theoretical_count,
                    "theoretical_endpoint_velocity_projection_mask20": projection.theoretical_mask20.tolist(),
                    "theoretical_endpoint_qpos_correction20_rad": projection.theoretical_qpos_correction20.tolist(),
                    "native_pre_projection_actuator_force20": projection.native_actuator_force20.tolist(),
                    "native_pre_projection_qfrc_actuator20_Nm": projection.native_qfrc_actuator20_nm.tolist(),
                    "native_pre_projection_qfrc_constraint20_Nm": projection.native_qfrc_constraint20_nm.tolist(),
                    "native_pre_projection_qacc20_rad_s2": projection.native_qacc20_rad_s2.tolist(),
                    "native_pre_projection_qfrc_passive20_Nm": projection.native_qfrc_passive20_nm.tolist(),
                    "native_pre_projection_qfrc_smooth20_Nm": projection.native_qfrc_smooth20_nm.tolist(),
                    "velocity_limit_realization": velocity_realization,
                    "plant_realization": dict(plant_realization),
                }
            )
        force_world = _contact_forces_world(
            model, data, finger_body_ids=finger_ids, handle_body_id=handle_body
        )
        force_source = force_world @ data.site_xmat[tcp_site].reshape(3, 3)
        force_norm = np.linalg.norm(force_source, axis=1)
        squeeze_y = force_source[:, 1]
        both_contact = bool(np.all(force_norm > 1.0))
        valid_squeeze = bool(
            both_contact
            and np.all(np.abs(squeeze_y) > 2.0)
            and squeeze_y[0] * squeeze_y[1] < 0.0
            and np.all(np.abs(squeeze_y) <= 30.0)
        )
        streak = streak + 1 if valid_squeeze else 0
        max_streak = max(max_streak, streak)
        rows.append(
            {
                "control_step": control_step,
                "gripper_joint_pos": data.qpos[mapping.robot_qpos_addresses][18:20].tolist(),
                "handle_hinge_rad": float(data.qpos[door_qpos][source_door_names.index("handle_hinge")]),
                "end_contact_force_source_n": force_source.tolist(),
                "max_substep_contact_force_norm_n": max_force.tolist(),
                "both_contact_end": both_contact,
                "valid_squeeze_end": valid_squeeze,
                "over_force_end": bool(np.any(force_norm > 55.0)),
                "streak": streak,
                "min_active_contact_distance_m": min_contact_distance,
                "substeps": substeps,
            }
        )
    summary = {
        "initial_state": "authority step104 pose with root/robot/door velocity zeroed",
        "target": "hold step104 leg+arm positions and step105 close gripper target for ten control steps",
        "controls": controls,
        "required_streak": 5,
        "max_valid_squeeze_streak": max_streak,
        "both_contact_end_controls": int(sum(row["both_contact_end"] for row in rows)),
        "valid_squeeze_end_controls": int(sum(row["valid_squeeze_end"] for row in rows)),
        "result": "PASS" if max_streak >= 5 else "FAIL_NO_FIVE_CONTROL_VALID_SQUEEZE",
        "velocity_limit_realization": velocity_realization,
        "plant_realization": plant_realization,
        "tcp_reference": {
            "adopted_m": 0.085,
            "authority": "source robot task_and_plant.tcp_offset_z_m and recorded-state kinematic pairing",
            "rejected_candidate_m": 0.09755,
            "reason": "not the resolved control TCP; changing it would break the micron-level recorded-state Cartesian pair",
        },
    }
    return rows, summary


def _source_substep_comparison_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    compared = [
        substep["source_comparison"]
        for row in rows
        for substep in row["substeps"]
        if substep["source_comparison"]["status"] == "RUN"
    ]
    if not compared:
        return {"status": "NOT_RUN_NO_SOURCE_SUBSTEP_TRACE"}
    fields = (
        "robot_joint_pos20_rad",
        "robot_joint_vel20_rad_s",
        "final_joint_position_target20_rad",
        "applied_effort20_Nm_vs_mujoco_actuator_force20",
        "finger_handle_normal_contact_force_on_handle_w_N",
    )
    result: dict[str, Any] = {
        "status": "RUN",
        "source_substeps_compared": len(compared),
        "joint_constraint_impulse20_Ns": "NOT_COMPARABLE_MUJOCO_EXPORT_IS_QFRC_CONSTRAINT_FORCE_NOT_IMPULSE",
    }
    for field in fields:
        field_rows = [comparison[field] for comparison in compared]
        numeric = [entry for entry in field_rows if "max_abs_error" in entry]
        result[field] = {
            "statuses": sorted({str(entry["status"]) for entry in field_rows}),
            "max_abs_error": (
                float(max(entry["max_abs_error"] for entry in numeric)) if numeric else None
            ),
        }
    return result


def _run_replay(
    *,
    scene: Path,
    inputs: ReplayInputs,
    stage2_transitions: int,
    velocity_realization: str,
    plant_variant: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model = mujoco.MjModel.from_xml_path(str(scene))
    if not math.isclose(float(model.opt.timestep), PHYSICS_DT, rel_tol=0.0, abs_tol=1.0e-12):
        raise RuntimeError(f"scene physics timestep is {model.opt.timestep}, expected {PHYSICS_DT}")
    data = mujoco.MjData(model)
    mapping = NameResolvedActuatorMapV2.from_model(model, inputs.robot_joint_names)
    if np.any(mapping.robot_actuator_ids < 0):
        raise RuntimeError("matched scene lacks one or more robot position-target actuators")
    plant_realization = _configure_plant_variant(
        model=model, mapping=mapping, plant_variant=plant_variant
    )
    first = inputs.source_steps[0]
    source_door_names = _source_door_to_mujoco_names(first.door_joint_names)
    door_qpos, door_qvel = _joint_addresses(model, source_door_names)
    _restore_source_state(
        model=model,
        data=data,
        mapping=mapping,
        source=first,
        target_joint_names=inputs.robot_joint_names,
        door_qpos=door_qpos,
        door_qvel=door_qvel,
    )
    tcp_site = _site_id(model, "a2_piper_tcp")
    grasp_site = _site_id(model, "door_grasp_target")
    finger_ids = (_body_id(model, "arm_body7"), _body_id(model, "arm_body8"))
    handle_body = _body_id(model, "door_handle")

    initial = _telemetry(
        model=model,
        data=data,
        mapping=mapping,
        tcp_site=tcp_site,
        grasp_site=grasp_site,
        finger_ids=finger_ids,
        handle_body=handle_body,
        door_qpos=door_qpos,
        door_qvel=door_qvel,
        source_step=first,
    )

    rows: list[dict[str, Any]] = []
    for transition_index in range(1, stage2_transitions + 1):
        source = inputs.source_steps[transition_index]
        target = _reorder(source.final_target20, source.joint_names, inputs.robot_joint_names)
        substeps = _step_position_target(
            model=model,
            data=data,
            mapping=mapping,
            target=target,
            velocity_limit20=inputs.velocity_limit20,
            source_control_step=source.control_step,
            source_plant_substeps=inputs.source_plant_substeps,
            source_joint_names=inputs.source_steps[0].joint_names,
            source_plant_capability=inputs.source_plant_substep_capability,
            finger_ids=finger_ids,
            handle_body=handle_body,
            door_qpos=door_qpos,
            door_qvel=door_qvel,
            velocity_realization=velocity_realization,
            plant_realization=plant_realization,
        )
        rows.append(
            {
                "lane": "isaac_stage2_final_target20_replay",
                "transition_index": transition_index - 1,
                "control_time_s": float(data.time),
                "source_post_delta_action12": source.high_action12.tolist(),
                "source_a2_base_leg_action12": source.leg_action12.tolist(),
                "target20": target.tolist(),
                "substeps": substeps,
                **_telemetry(
                    model=model,
                    data=data,
                    mapping=mapping,
                    tcp_site=tcp_site,
                    grasp_site=grasp_site,
                    finger_ids=finger_ids,
                    handle_body=handle_body,
                    door_qpos=door_qpos,
                    door_qvel=door_qvel,
                    source_step=source,
                ),
            }
        )
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
            raise FloatingPointError(f"non-finite MuJoCo state after source step {source.control_step}")
    summary = {
        "initial_source_control_step": first.control_step,
        "transitions": len(rows),
        "final_source_control_step": rows[-1]["source_control_step"],
        "min_tcp_to_grasp_m": float(min(row["tcp_to_grasp_m"] for row in rows)),
        "source_min_tcp_to_handle_m": float(min(row["source_tcp_to_handle_m"] for row in rows)),
        "first_tcp_to_grasp_m": float(rows[0]["tcp_to_grasp_m"]),
        "first_source_tcp_to_handle_m": float(rows[0]["source_tcp_to_handle_m"]),
        "first_cartesian_distance_gap_m": float(rows[0]["cartesian_distance_gap_m"]),
        "max_cartesian_distance_gap_m": float(max(row["cartesian_distance_gap_m"] for row in rows)),
        "max_cartesian_distance_gap_abs_m": float(
            max(abs(row["cartesian_distance_gap_m"]) for row in rows)
        ),
        "max_cartesian_vector_error_norm_m": float(
            max(row["cartesian_vector_error_norm_m"] for row in rows)
        ),
        "both_contact_controls": int(sum(row["both_contact_force_gt_1n"] for row in rows)),
        "valid_squeeze_controls": int(sum(row["valid_opposed_squeeze_gt_2n"] for row in rows)),
        "max_handle_hinge_rad": float(
            max(row["door_joint_pos"][source_door_names.index("handle_hinge")] for row in rows)
        ),
        "max_door_hinge_rad": float(
            max(row["door_joint_pos"][source_door_names.index("door_hinge")] for row in rows)
        ),
        "max_state_errors": {
            key: float(max(row["state_error"][key] for row in rows))
            for key in rows[0]["state_error"]
        },
        "max_velocity_limit_ratio": float(
            max(
                substep["velocity_limit_max_ratio"]
                for row in rows
                for substep in row["substeps"]
            )
        ),
        "velocity_limit_exceeded_substeps": int(
            sum(
                substep["velocity_limit_max_ratio"] > 1.0
                for row in rows
                for substep in row["substeps"]
            )
        ),
        "velocity_limit_realization": velocity_realization,
        "plant_realization": plant_realization,
        "initial_cartesian_kinematic_pair": {
            "tcp_position_world_m": initial["tcp_position_world_m"],
            "grasp_target_world_m": initial["grasp_target_world_m"],
            "tcp_to_grasp_source_frame_m": initial["tcp_to_grasp_source_frame_m"],
            "source_tcp_to_handle_source_frame_m": initial[
                "source_tcp_to_handle_source_frame_m"
            ],
            "cartesian_vector_error_m": initial["cartesian_vector_error_m"],
            "cartesian_vector_error_norm_m": initial["cartesian_vector_error_norm_m"],
            "tcp_to_grasp_m": initial["tcp_to_grasp_m"],
            "source_tcp_to_handle_m": initial["source_tcp_to_handle_m"],
            "cartesian_distance_gap_m": initial["cartesian_distance_gap_m"],
        },
    }
    return rows, summary


def _typed_verdict(
    summary: Mapping[str, Any],
    one_step: Mapping[str, Any],
    pregrasp: Mapping[str, Any],
) -> dict[str, str]:
    contact = int(summary["both_contact_controls"]) > 0
    squeeze = int(summary["valid_squeeze_controls"]) > 0
    if contact and squeeze:
        target_surface = "SUPPORTED_CONTACT_AND_SQUEEZE_REACHED"
    elif contact:
        target_surface = "PARTIAL_BILATERAL_CONTACT_WITHOUT_VALID_SQUEEZE"
    else:
        target_surface = "NOT_SUPPORTED_NO_BILATERAL_CONTACT"
    return {
        "result": "INCONCLUSIVE",
        "post_adapter_target_surface": target_surface,
        "full_isaac_20d_actuator_target_replay": "RUN",
        "gate2_plant_tracking": (
            "INCONCLUSIVE_DECLARED_ENDPOINT_VELOCITY_PROJECTION_VIOLATED_AND_RESIDUAL_PERSISTS"
            if (
                one_step["velocity_limit_realization"]
                == VELOCITY_REALIZATION_ENDPOINT_PROJECTION
                and int(one_step["velocity_limit_exceeded_substeps"]) > 0
            )
            else (
                "INCONCLUSIVE_CROSS_ENGINE_PLANT_RESIDUAL_PERSISTS_AFTER_DECLARED_ENDPOINT_VELOCITY_PROJECTION"
                if one_step["velocity_limit_realization"] == VELOCITY_REALIZATION_ENDPOINT_PROJECTION
                else "INCONCLUSIVE_NATIVE_MUJOCO_PLANT_RESIDUAL_RECORDED_WITHOUT_ENDPOINT_PROJECTION"
            )
        ),
        "gate6_fixed_pregrasp": str(pregrasp["result"]),
        "gate7_latch": (
            "ADMITTED" if pregrasp["result"] == "PASS" else "NOT_ADMITTED_UPSTREAM_CONTACT_GATE_FAILED"
        ),
        "joint_state_target_pairing": "STRICT_RECORDED_STAGE2_JOINT_SURFACE_PREFIX",
        "cartesian_kinematic_pairing": "SUPPORTED_FOR_RECORDED_STAGE2_STATE_PREFIX_MJ_FORWARD",
        "mechanics_vs_input_split": "INCONCLUSIVE_CROSS_ENGINE_PLANT_MAPPING_NOT_EQUIVALENT",
        "visual_causality": "NOT_TESTED_OPEN_LOOP_REPLAY",
    }


def run(args: argparse.Namespace) -> None:
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"replay output directory must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs(
        robot_authority_episode_dir=args.robot_authority_episode_dir.resolve(strict=True),
        producer_stage2_trace=args.producer_stage2_trace,
        producer_diagnostic_json=args.producer_diagnostic_json,
        producer_plant_substep_trace=args.producer_plant_substep_trace,
        resolved_config=args.resolved_config,
        producer_env_id=args.producer_env_id,
        producer_episode_index=args.producer_episode_index,
    )
    transitions = int(args.stage2_control_transitions)
    if transitions <= 0:
        raise ValueError("--stage2-control-transitions must be positive")
    if transitions >= len(inputs.source_steps):
        raise RuntimeError(
            f"producer has {len(inputs.source_steps)} Stage2 states, so at most {len(inputs.source_steps) - 1} transitions are available"
        )
    scene, pairing = _build_matched_scene(output, inputs)
    kinematic_rows, kinematic_summary = _run_kinematic_pairing_prefix(
        scene=scene, inputs=inputs, states=transitions + 1
    )
    rows, summary = _run_replay(
        scene=scene,
        inputs=inputs,
        stage2_transitions=transitions,
        velocity_realization=args.velocity_realization,
        plant_variant=args.plant_variant,
    )
    one_step_rows, one_step_summary = _run_state_reset_one_control_residuals(
        scene=scene,
        inputs=inputs,
        transitions=transitions,
        velocity_realization=args.velocity_realization,
        plant_variant=args.plant_variant,
    )
    source_substep_comparison = _source_substep_comparison_summary(one_step_rows)
    pregrasp_rows, pregrasp_summary = _run_fixed_pregrasp_close_hold(
        scene=scene,
        inputs=inputs,
        velocity_realization=args.velocity_realization,
        plant_variant=args.plant_variant,
    )
    kinematic_telemetry_path = output / "stage2_kinematic_pairing_telemetry.jsonl"
    kinematic_telemetry_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in kinematic_rows),
        encoding="utf-8",
    )
    telemetry_path = output / "stage2_action_replay_telemetry.jsonl"
    telemetry_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8"
    )
    one_step_path = output / "stage2_state_reset_one_control_residuals.jsonl"
    one_step_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in one_step_rows),
        encoding="utf-8",
    )
    pregrasp_path = output / "fixed_pregrasp_close_hold.jsonl"
    pregrasp_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in pregrasp_rows),
        encoding="utf-8",
    )
    receipt = {
        "schema": "doordog.sim2sim.depthadd_v3.stage2_action_replay.v3",
        "evidence_level": "RUNTIME",
        "result": "COMPLETE",
        "scene": str(scene),
        "timebase": {
            "control_dt_s": CONTROL_DT,
            "physics_dt_s": PHYSICS_DT,
            "physics_steps_per_control": PHYSICS_STEPS_PER_CONTROL,
        },
        "authority": {
            "producer_stage2_trace": str(args.producer_stage2_trace.resolve(strict=True)),
            "producer_diagnostic_json": str(inputs.producer_diagnostic_json),
            "producer_env_id": args.producer_env_id,
            "producer_episode_index": args.producer_episode_index,
            "source_stage2_states_available": len(inputs.source_steps),
            "source_stage2_transitions_replayed": transitions,
            "joint_names": SOURCE_JOINT_NAMES_FIELD,
            "a2_base_leg_action12": SOURCE_LEG_ACTION_FIELD,
            "final_joint_position_target20": SOURCE_FINAL_TARGET_FIELD,
            "initial_state": "first recorded post-physics Stage2 row",
            "root_angular_velocity_conversion": "Isaac world frame to MuJoCo local free-joint frame via R_wb.T",
            "velocity_limit20": inputs.velocity_limit20.tolist(),
            "velocity_limit_authority": str(args.resolved_config.resolve(strict=True)),
            "velocity_limit_contract": DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION,
            "velocity_limit_mujoco_realization": args.velocity_realization,
            "velocity_limit_mujoco_realization_semantics": (
                "post-native-step qvel projection plus displacement correction; not a native MuJoCo constraint or PhysX-equivalence claim"
                if args.velocity_realization == VELOCITY_REALIZATION_ENDPOINT_PROJECTION
                else "native MuJoCo endpoint without qpos/qvel projection; theoretical endpoint projection telemetry is exported but never written"
            ),
            "plant_variant": args.plant_variant,
            "plant_target_realization": (
                {
                    "formula": "drive_target20 = qpos20 + clip(raw_target20 - qpos20, -velocity_limit20 * KD20 / KP20, +velocity_limit20 * KD20 / KP20)",
                    "boundary": "MuJoCo diagnostic target realization only; not a PhysX maxJointVelocity or actuator-equivalence claim",
                }
                if args.plant_variant
                in (
                    PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET,
                    PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT,
                    PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09,
                )
                else {"mode": "raw_position_target"}
            ),
            "plant_contact_impedance_realization": (
                {
                    "status": "MUJOCO_CONTACT_IMPEDANCE_DIAGNOSTIC",
                    "formula": "geom_solref = [2 * model.opt.timestep, 1.0]",
                    "boundary": "MuJoCo contact impedance diagnostic only; not a PhysX contact-equivalence claim",
                    "solimp": "UNCHANGED",
                    "friction": "UNCHANGED",
                    "geometry": "UNCHANGED",
                }
                if args.plant_variant
                in (
                    PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT,
                    PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09,
                )
                else {"status": "NOT_APPLIED"}
            ),
            "plant_contact_friction_realization": (
                {
                    "status": "MOVING_CONTACT_DYNAMIC_FRICTION_DIAGNOSTIC",
                    "authority": "resolved production a2_m39_gripper_material_enabled=true; M39 dynamic friction=0.9",
                    "boundary": "MuJoCo has no static/dynamic friction split; this is not a PhysX material-equivalence claim",
                    "sliding_friction": 0.9,
                    "torsional_friction": "UNCHANGED",
                    "rolling_friction": "UNCHANGED",
                    "solimp": "UNCHANGED",
                    "geometry": "UNCHANGED",
                }
                if args.plant_variant
                == PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09
                else {"status": "NOT_APPLIED"}
            ),
            "producer_plant_substep_trace": (
                str(inputs.source_plant_substep_trace)
                if inputs.source_plant_substep_trace is not None
                else "NOT_RUN_NO_PRODUCER_SUBSTEP_TRACE"
            ),
            "producer_plant_substep_schema": inputs.source_plant_substep_schema,
            "producer_plant_substep_capability": dict(inputs.source_plant_substep_capability),
        },
        "pairing": pairing,
        "kinematic_pairing_prefix": kinematic_summary,
        "lane": {"isaac_stage2_final_target20_replay": summary},
        "state_reset_one_control_residual": one_step_summary,
        "source_substep_comparison": source_substep_comparison,
        "fixed_pregrasp_close_hold": pregrasp_summary,
        "typed_verdict": _typed_verdict(summary, one_step_summary, pregrasp_summary),
        "telemetry": str(telemetry_path),
        "kinematic_pairing_telemetry": str(kinematic_telemetry_path),
        "state_reset_one_control_telemetry": str(one_step_path),
        "fixed_pregrasp_close_hold_telemetry": str(pregrasp_path),
    }
    _json_dump(output / "stage2_action_replay_receipt.json", receipt)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-authority-episode-dir", type=Path, required=True)
    parser.add_argument("--producer-stage2-trace", type=Path, required=True)
    parser.add_argument("--producer-diagnostic-json", type=Path, required=True)
    parser.add_argument(
        "--producer-plant-substep-trace",
        type=Path,
        default=None,
        help="Isaac stage2_plant_substep_trace.json; omitted only for legacy state/target replay without attribution.",
    )
    parser.add_argument("--resolved-config", type=Path, required=True)
    parser.add_argument("--producer-env-id", type=int, default=13)
    parser.add_argument("--producer-episode-index", type=int, default=0)
    parser.add_argument("--stage2-control-transitions", type=int, default=25)
    parser.add_argument(
        "--velocity-realization",
        choices=(VELOCITY_REALIZATION_ENDPOINT_PROJECTION, VELOCITY_REALIZATION_NATIVE),
        default=VELOCITY_REALIZATION_ENDPOINT_PROJECTION,
    )
    parser.add_argument(
        "--plant-variant",
        choices=(
            PLANT_VARIANT_BASELINE,
            PLANT_VARIANT_JOINT_DAMPING_FORCE_PATH,
            PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET,
            PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT,
            PLANT_VARIANT_VELOCITY_LIMITED_PD_TARGET_CONTACT_SOLREF_2DT_FRICTION09,
        ),
        default=PLANT_VARIANT_BASELINE,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
