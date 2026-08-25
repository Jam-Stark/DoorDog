#!/usr/bin/env python3
"""Fixed-scene Stage2 action-surface replay for DepthADD v3.

This is deliberately an *action-surface* probe.  It replays the recorded
MuJoCo prefix through the Stage2 entry, then compares its recorded 20D target
path with an Isaac-authoritative Stage2 arm/gripper target substitution.  The
producer trace does not expose Isaac's low-level 12D leg action or a final
20D target, so this command refuses to describe the second lane as a full
Isaac actuator replay.  It retains the original MuJoCo legs only to hold the
same body context while testing the Stage2 arm/gripper mechanics.
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

from gr00t.rl.sim2sim.doors.runtime import ConstraintGate
from gr00t.rl.sim2sim.mujoco.actuator_map_v2 import NameResolvedActuatorMapV2


CONTROL_DT = 0.02
PHYSICS_DT = 0.005
PHYSICS_STEPS_PER_CONTROL = 4
SOURCE_HIGH_LEVEL_ACTION_FIELD = "post_delta_post_warp_env_action"
SOURCE_ARM_TARGET_FIELD = "arm_joint_pos_target"
SOURCE_GRIPPER_TARGET_FIELD = "gripper_joint_pos_target"


@dataclass(frozen=True)
class SourceStage2Action:
    control_step: int
    high_action12: np.ndarray
    arm_target6: np.ndarray
    gripper_target2: np.ndarray


@dataclass(frozen=True)
class ReplayInputs:
    source_actions: tuple[SourceStage2Action, ...]
    original_targets: tuple[np.ndarray, ...]
    stage2_start: int
    robot_joint_names: tuple[str, ...]
    release_handle_rad: float
    initial_root_qpos7: np.ndarray
    initial_root_qvel6: np.ndarray
    initial_joint_qpos20: np.ndarray
    initial_joint_qvel20: np.ndarray
    initial_state_receipt: Path


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"required trace is absent: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise RuntimeError(f"trace has no rows: {path}")
    return rows


def _finite_vector(value: Any, *, width: int, field: str, step: int) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (width,):
        raise ValueError(f"{field} at source step {step} has shape {result.shape}, expected {(width,)}")
    if not np.isfinite(result).all():
        raise FloatingPointError(f"{field} at source step {step} contains a non-finite value")
    return result


def _load_source_stage2_actions(
    path: Path, *, env_id: int, episode_index: int
) -> tuple[SourceStage2Action, ...]:
    """Load only true Stage2 producer rows; no Stage0 artifact is accepted."""

    if path.name != "stage2_step_trace.json":
        raise ValueError(
            "--producer-stage2-trace must be the producer's stage2_step_trace.json; "
            "Stage0 traces are not Stage2 action authority."
        )
    payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"producer Stage2 trace must be a non-empty JSON list: {path}")
    rows = [
        row for row in payload
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
        raise RuntimeError("producer Stage2 action steps are not contiguous")
    result: list[SourceStage2Action] = []
    for row in rows:
        step = int(row["step_index"])
        for field in (
            SOURCE_HIGH_LEVEL_ACTION_FIELD,
            SOURCE_ARM_TARGET_FIELD,
            SOURCE_GRIPPER_TARGET_FIELD,
        ):
            if field not in row:
                raise KeyError(f"producer Stage2 row {step} lacks required authority field {field!r}")
        result.append(
            SourceStage2Action(
                control_step=step,
                high_action12=_finite_vector(
                    row[SOURCE_HIGH_LEVEL_ACTION_FIELD], width=12, field=SOURCE_HIGH_LEVEL_ACTION_FIELD, step=step
                ),
                arm_target6=_finite_vector(
                    row[SOURCE_ARM_TARGET_FIELD], width=6, field=SOURCE_ARM_TARGET_FIELD, step=step
                ),
                gripper_target2=_finite_vector(
                    row[SOURCE_GRIPPER_TARGET_FIELD], width=2, field=SOURCE_GRIPPER_TARGET_FIELD, step=step
                ),
            )
        )
    return tuple(result)


def _load_original_targets(case_dir: Path) -> tuple[tuple[np.ndarray, ...], int]:
    rows = _json_lines(case_dir / "policy_trace.jsonl")
    steps = [int(row["step"]) for row in rows]
    if steps != list(range(len(rows))):
        raise RuntimeError("MuJoCo policy trace steps must start at zero and be contiguous")
    targets = tuple(
        _finite_vector(row.get("target20"), width=20, field="target20", step=int(row["step"]))
        for row in rows
    )
    stage2_rows = [int(row["step"]) for row in rows if int(row.get("stage", -1)) == 2]
    if not stage2_rows:
        raise RuntimeError("fixed MuJoCo policy trace never entered Stage2")
    stage2_start = stage2_rows[0]
    if stage2_rows != list(range(stage2_start, len(rows))):
        raise RuntimeError("fixed MuJoCo trace must remain in Stage2 after the first Stage2 control step")
    return targets, stage2_start


def _prepared_root(case_dir: Path, receipt: Mapping[str, Any]) -> Path:
    candidates = [case_dir.parent.parent]
    source_scene = receipt.get("visual_overlay", {}).get("source_scene_xml")
    if source_scene is not None:
        scene = Path(source_scene).resolve(strict=True)
        if scene.name != "scene.xml" or scene.parent.name != "model":
            raise RuntimeError("receipt visual_overlay source_scene_xml has an invalid scene layout")
        candidates.append(scene.parents[3])
    roots = list(dict.fromkeys(root for root in candidates if (root / "prepared" / "robot_contract.json").is_file()))
    if len(roots) != 1:
        raise RuntimeError(
            f"expected exactly one prepared output root for {case_dir}; found {[str(root) for root in roots]}"
        )
    return roots[0]


def _load_release_handle_rad(prepared_root: Path, case_dir: Path) -> float:
    manifest = prepared_root / "prepared" / "materialized_experiment.json"
    payload = json.loads(manifest.resolve(strict=True).read_text(encoding="utf-8"))
    case_id = case_dir.name
    rows = [row for row in payload["primary_rows"] if str(row["case_id"]) == case_id]
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one manifest row for {case_id}, got {len(rows)}")
    geometry = rows[0]["door_geometry"]
    # The original fixed runner resolves this absent optional manifest key to
    # pi/6 at scene construction.  It is a traced runtime contract, not an
    # inferred replay value; make the provenance visible in the receipt.
    return (
        float(geometry["constraint_gate_release_handle_rad"])
        if "constraint_gate_release_handle_rad" in geometry
        else math.pi / 6.0
    )


def _load_exact_initial_state(receipt_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    receipt = json.loads(receipt_path.resolve(strict=True).read_text(encoding="utf-8"))
    state = receipt.get("initial_state_realization")
    if not isinstance(state, Mapping):
        raise RuntimeError(
            "fixed admission receipt lacks initial_state_realization; do not substitute scene_home or a post-step physics trace"
        )
    if state.get("schema") != "a2_depthadd_v3_mujoco_initial_state_v1":
        raise RuntimeError("unsupported initial-state receipt schema")
    return (
        _finite_vector(state.get("root_qpos_mujoco_wxyz"), width=7, field="initial_root_qpos", step=-1),
        _finite_vector(state.get("root_qvel"), width=6, field="initial_root_qvel", step=-1),
        _finite_vector(state.get("joint_qpos"), width=20, field="initial_joint_qpos", step=-1),
        _finite_vector(state.get("joint_qvel"), width=20, field="initial_joint_qvel", step=-1),
    )


def _load_inputs(
    *, case_dir: Path, producer_stage2_trace: Path, producer_env_id: int, producer_episode_index: int
) -> ReplayInputs:
    receipt_path = case_dir / "receipt.json"
    receipt = json.loads(receipt_path.resolve(strict=True).read_text(encoding="utf-8"))
    prepared_root = _prepared_root(case_dir, receipt)
    contract_path = prepared_root / "prepared" / "robot_contract.json"
    contract = json.loads(contract_path.resolve(strict=True).read_text(encoding="utf-8"))
    names = tuple(contract["sim_joint_names"])
    if len(names) != 20:
        raise RuntimeError(f"robot contract must have 20 simulator joints, got {len(names)}")
    targets, stage2_start = _load_original_targets(case_dir)
    source_actions = _load_source_stage2_actions(
        producer_stage2_trace, env_id=producer_env_id, episode_index=producer_episode_index
    )
    root_qpos, root_qvel, joint_qpos, joint_qvel = _load_exact_initial_state(receipt_path)
    return ReplayInputs(
        source_actions=source_actions,
        original_targets=targets,
        stage2_start=stage2_start,
        robot_joint_names=names,
        release_handle_rad=_load_release_handle_rad(prepared_root, case_dir),
        initial_root_qpos7=root_qpos,
        initial_root_qvel6=root_qvel,
        initial_joint_qpos20=joint_qpos,
        initial_joint_qvel20=joint_qvel,
        initial_state_receipt=receipt_path.resolve(strict=True),
    )


def _scene_for_episode(case_dir: Path) -> Path:
    local_scene = case_dir / "model" / "scene.xml"
    if local_scene.is_file():
        return local_scene.resolve(strict=True)
    receipt = json.loads((case_dir / "receipt.json").resolve(strict=True).read_text(encoding="utf-8"))
    source_scene = receipt.get("visual_overlay", {}).get("source_scene_xml")
    if source_scene is None:
        raise FileNotFoundError(f"fixed admission episode has no local scene.xml: {case_dir}")
    return Path(source_scene).resolve(strict=True)


def _scene_pairing(
    *, case_dir: Path, producer_diagnostic_json: Path | None, producer_env_id: int
) -> dict[str, Any]:
    """Record the geometry/drive mismatch instead of treating env9 as paired."""

    receipt = json.loads((case_dir / "receipt.json").resolve(strict=True).read_text(encoding="utf-8"))
    realized = receipt["realized_parameters"]
    mujoco = {
        "geometry": realized["door_geometry"],
        "dynamics": realized["door_dynamics_cell"],
    }
    result: dict[str, Any] = {
        "status": "NOT_PAIRED",
        "reason": "producer env and MuJoCo fixed admission episode are independently realized scenes",
        "mujoco_fixed": mujoco,
    }
    if producer_diagnostic_json is None:
        result["producer_geometry"] = "NOT_RECORDED"
        return result
    diagnostic = json.loads(producer_diagnostic_json.resolve(strict=True).read_text(encoding="utf-8"))
    table = diagnostic.get("case_table")
    if not isinstance(table, Mapping):
        raise RuntimeError("producer diagnostic JSON lacks a case_table mapping")
    producer_row = table.get(str(producer_env_id))
    if not isinstance(producer_row, Mapping):
        raise RuntimeError(f"producer diagnostic case_table lacks env {producer_env_id}")
    custom = producer_row.get("door_custom_data")
    if not isinstance(custom, Mapping):
        raise RuntimeError(f"producer diagnostic env {producer_env_id} lacks door_custom_data")
    result["producer_diagnostic_json"] = str(producer_diagnostic_json.resolve(strict=True))
    result["producer_geometry"] = dict(custom)
    result["producer_drive_summary"] = {
        key: producer_row[key]
        for key in (
            "door_handle_height",
            "door_handle_drive_max_force",
            "door_hinge_drive_max_force",
            "door_weight",
        )
        if key in producer_row
    }
    result["key_mismatch"] = {
        "handle_height_m": {
            "producer": custom["doorHandleHeight"],
            "mujoco": realized["door_geometry"]["handle_height_m"],
        },
        "axle_length_m": {
            "producer": custom["axleLength"],
            "mujoco": realized["door_geometry"]["axle_length_m"],
        },
        "handle_length_m": {
            "producer": custom["handleLength"],
            "mujoco": realized["door_geometry"]["handle_length_m"],
        },
        "handle_radius_m": {
            "producer": custom["handleRadius"],
            "mujoco": realized["door_geometry"]["handle_radius_m"],
        },
        "handle_drive_max_force": {
            "producer": custom["handleDriveMaxForce"],
            "mujoco": realized["door_dynamics_cell"]["max_force_nm"],
        },
        "hinge_drive": {
            "producer": {
                "stiffness": custom["hingeDriveStiffness"],
                "damping": custom["hingeDriveDamping"],
                "max_force": custom["hingeDriveMaxForce"],
            },
            "mujoco": realized["door_dynamics_cell"],
        },
    }
    return result


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


def _site_id(model: mujoco.MjModel, name: str) -> int:
    value = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
    if value < 0:
        raise RuntimeError(f"compiled scene lacks required site {name!r}")
    return value


def _body_id(model: mujoco.MjModel, name: str) -> int:
    value = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    if value < 0:
        raise RuntimeError(f"compiled scene lacks required body {name!r}")
    return value


def _joint_qpos_address(model: mujoco.MjModel, name: str) -> int:
    joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    if joint < 0:
        raise RuntimeError(f"compiled scene lacks required joint {name!r}")
    return int(model.jnt_qposadr[joint])


def _telemetry(
    *,
    model: mujoco.MjModel,
    data: mujoco.MjData,
    tcp_site: int,
    grasp_site: int,
    finger_ids: tuple[int, int],
    handle_body: int,
    handle_qpos_address: int,
    door_qpos_address: int,
    gate: ConstraintGate,
) -> dict[str, Any]:
    tcp = data.site_xpos[tcp_site].copy()
    grasp = data.site_xpos[grasp_site].copy()
    forces_world = _contact_forces_world(
        model, data, finger_body_ids=finger_ids, handle_body_id=handle_body
    )
    tcp_rotation = data.site_xmat[tcp_site].reshape(3, 3)
    forces_source = forces_world @ tcp_rotation
    force_norm = np.linalg.norm(forces_source, axis=1)
    squeeze_y = forces_source[:, 1]
    both_contact = bool(np.all(force_norm > 1.0))
    valid_squeeze = bool(np.all(np.abs(squeeze_y) > 2.0) and squeeze_y[0] * squeeze_y[1] < 0.0)
    return {
        "tcp_position_world_m": tcp.tolist(),
        "grasp_target_world_m": grasp.tolist(),
        "tcp_to_grasp_m": float(np.linalg.norm(tcp - grasp)),
        "handle_contact_force_world_n": forces_world.tolist(),
        "handle_contact_force_source_n": forces_source.tolist(),
        "handle_contact_force_norm_source_n": force_norm.tolist(),
        "squeeze_y_source_n": squeeze_y.tolist(),
        "both_contact_force_gt_1n": both_contact,
        "valid_opposed_squeeze_gt_2n": valid_squeeze,
        "door_hinge_rad": float(data.qpos[door_qpos_address]),
        "handle_hinge_rad": float(data.qpos[handle_qpos_address]),
        "constraint_gate_active": bool(data.eq_active[gate.eq_id]),
    }


def _run_lane(
    *,
    lane: str,
    scene: Path,
    inputs: ReplayInputs,
    stage2_steps: int,
    source_substitution: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model = mujoco.MjModel.from_xml_path(str(scene))
    if not math.isclose(float(model.opt.timestep), PHYSICS_DT, rel_tol=0.0, abs_tol=1.0e-12):
        raise RuntimeError(f"scene physics timestep is {model.opt.timestep}, expected {PHYSICS_DT}")
    data = mujoco.MjData(model)
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    if home < 0:
        raise RuntimeError("compiled scene lacks scene_home keyframe")
    mujoco.mj_resetDataKeyframe(model, data, home)
    data.qpos[:7] = inputs.initial_root_qpos7
    data.qvel[:6] = inputs.initial_root_qvel6
    # The joint address mapping is model-resolved below; only the free-joint
    # prefix can be assigned before compilation/name checks.
    mujoco.mj_forward(model, data)
    mapping = NameResolvedActuatorMapV2.from_model(model, inputs.robot_joint_names)
    if np.any(mapping.robot_actuator_ids < 0):
        raise RuntimeError("scene does not expose the required 20 position-target robot actuators")
    data.qpos[mapping.robot_qpos_addresses] = inputs.initial_joint_qpos20
    data.qvel[mapping.robot_qvel_addresses] = inputs.initial_joint_qvel20
    mujoco.mj_forward(model, data)
    tcp_site = _site_id(model, "a2_piper_tcp")
    grasp_site = _site_id(model, "door_grasp_target")
    finger_ids = (_body_id(model, "arm_body7"), _body_id(model, "arm_body8"))
    handle_body = _body_id(model, "door_handle")
    handle_qpos = _joint_qpos_address(model, "handle_hinge")
    door_qpos = _joint_qpos_address(model, "door_hinge")
    gate = ConstraintGate(model, release_handle_rad=inputs.release_handle_rad)

    total_steps = inputs.stage2_start + stage2_steps
    if total_steps > len(inputs.original_targets):
        raise RuntimeError(
            f"original target trace has {len(inputs.original_targets)} controls, needs {total_steps}"
        )
    rows: list[dict[str, Any]] = []
    released = False
    for control_step in range(total_steps):
        target = inputs.original_targets[control_step].copy()
        source_row: SourceStage2Action | None = None
        if control_step >= inputs.stage2_start and source_substitution:
            source_row = inputs.source_actions[control_step - inputs.stage2_start]
            # The producer has no leg12/final target20 authority.  Keep the
            # original local legs and substitute only explicitly exported
            # Isaac arm/gripper position targets.
            target[12:18] = source_row.arm_target6
            target[18:20] = source_row.gripper_target2
        if not np.isfinite(target).all():
            raise FloatingPointError(f"non-finite target in {lane} at control step {control_step}")
        for _ in range(PHYSICS_STEPS_PER_CONTROL):
            mapping.write_robot_position_target(data, target)
            released = gate.update(data) or released
            mujoco.mj_step(model, data)
        values = _telemetry(
            model=model,
            data=data,
            tcp_site=tcp_site,
            grasp_site=grasp_site,
            finger_ids=finger_ids,
            handle_body=handle_body,
            handle_qpos_address=handle_qpos,
            door_qpos_address=door_qpos,
            gate=gate,
        )
        rows.append(
            {
                "lane": lane,
                "control_step": control_step,
                "control_time_s": float(data.time),
                "phase": "prefix" if control_step < inputs.stage2_start else "stage2",
                "source_stage2_control_step": source_row.control_step if source_row else None,
                "target20": target.tolist(),
                "source_post_delta_action12": source_row.high_action12.tolist() if source_row else None,
                **values,
            }
        )
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
            raise FloatingPointError(f"non-finite MuJoCo state in {lane} at control step {control_step}")
    stage2 = [row for row in rows if row["phase"] == "stage2"]
    summary = {
        "controls": len(rows),
        "stage2_controls": len(stage2),
        "min_tcp_to_grasp_m": float(min(row["tcp_to_grasp_m"] for row in stage2)),
        "both_contact_controls": int(sum(row["both_contact_force_gt_1n"] for row in stage2)),
        "valid_squeeze_controls": int(sum(row["valid_opposed_squeeze_gt_2n"] for row in stage2)),
        "max_handle_hinge_rad": float(max(row["handle_hinge_rad"] for row in stage2)),
        "max_door_hinge_rad": float(max(row["door_hinge_rad"] for row in stage2)),
        "constraint_gate_released": released,
        "final_constraint_gate_active": bool(rows[-1]["constraint_gate_active"]),
    }
    return rows, summary


def _verdict(*, original: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, str]:
    source_contact = int(source["both_contact_controls"]) > 0
    source_squeeze = int(source["valid_squeeze_controls"]) > 0
    if source_contact and source_squeeze:
        upper_target_restore = "SUPPORTED"
        detail = "Isaac Stage2 arm/gripper targets established the Stage2 contact+squeeze predicate under retained MuJoCo legs."
    elif source_contact:
        upper_target_restore = "NOT_SUPPORTED"
        detail = "Isaac Stage2 arm/gripper targets reached both contacts but not the opposed squeeze predicate."
    else:
        upper_target_restore = "NOT_SUPPORTED"
        detail = "Isaac Stage2 arm/gripper targets did not establish bilateral contact under retained MuJoCo legs."
    return {
        "result": "INCONCLUSIVE",
        "upper_target_restore": upper_target_restore,
        "full_mechanics_vs_input_split": "INCONCLUSIVE_NON_PAIRED_SCENE_AND_MISSING_LEG12_TARGET20",
        "scope": "non-paired-scene, exact MuJoCo prefix, Stage2-only Isaac arm6+gripper2 target substitution",
        "detail": detail,
        "full_isaac_20d_actuator_replay": "UNRESOLVED_SOURCE_ARTIFACT_LACKS_ISAAC_LEG12_AND_FINAL_TARGET20",
        "visual_causality": "NOT_TESTED; this open-loop action probe bypasses camera and actor observation inputs.",
        "original_lane_contact_controls": str(original["both_contact_controls"]),
    }


def run(args: argparse.Namespace) -> None:
    case_dir = args.fixed_admission_episode_dir.resolve(strict=True)
    scene = _scene_for_episode(case_dir)
    inputs = _load_inputs(
        case_dir=case_dir,
        producer_stage2_trace=args.producer_stage2_trace,
        producer_env_id=args.producer_env_id,
        producer_episode_index=args.producer_episode_index,
    )
    scene_pairing = _scene_pairing(
        case_dir=case_dir,
        producer_diagnostic_json=args.producer_diagnostic_json,
        producer_env_id=args.producer_env_id,
    )
    stage2_steps = int(args.stage2_control_steps)
    if stage2_steps <= 0:
        raise ValueError("--stage2-control-steps must be positive")
    if stage2_steps > len(inputs.source_actions):
        raise RuntimeError(
            f"producer has only {len(inputs.source_actions)} true Stage2 controls; requested {stage2_steps}"
        )
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"replay output directory must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    original_rows, original_summary = _run_lane(
        lane="original_mujoco_target20_replay",
        scene=scene,
        inputs=inputs,
        stage2_steps=stage2_steps,
        source_substitution=False,
    )
    source_rows, source_summary = _run_lane(
        lane="isaac_stage2_arm_gripper_target_replay",
        scene=scene,
        inputs=inputs,
        stage2_steps=stage2_steps,
        source_substitution=True,
    )
    telemetry_path = output / "stage2_action_replay_telemetry.jsonl"
    telemetry_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in [*original_rows, *source_rows]),
        encoding="utf-8",
    )
    receipt = {
        "schema": "doordog.sim2sim.depthadd_v3.stage2_action_replay.v1",
        "evidence_level": "RUNTIME",
        "result": "COMPLETE",
        "scene": str(scene),
        "fixed_reset": "exact initial_state_realization restored for each lane; identical recorded MuJoCo target20 prefix through Stage2 entry",
        "initial_state_receipt": str(inputs.initial_state_receipt),
        "timebase": {"control_dt_s": CONTROL_DT, "physics_dt_s": PHYSICS_DT, "physics_steps_per_control": PHYSICS_STEPS_PER_CONTROL},
        "authority": {
            "producer_stage2_trace": str(args.producer_stage2_trace.resolve(strict=True)),
            "producer_env_id": args.producer_env_id,
            "producer_episode_index": args.producer_episode_index,
            "source_stage": 2,
            "source_stage2_controls_available": len(inputs.source_actions),
            "source_stage2_controls_replayed": stage2_steps,
            "post_delta_high_level_action12": SOURCE_HIGH_LEVEL_ACTION_FIELD,
            "arm_position_target6": SOURCE_ARM_TARGET_FIELD,
            "gripper_position_target2": SOURCE_GRIPPER_TARGET_FIELD,
            "isaac_leg_action12": "ABSENT",
            "isaac_final_target20": "ABSENT",
            "stage0_authority_used": False,
            "source_limit": "not a full Isaac 20D actuator replay; source lane preserves original MuJoCo leg targets",
        },
        "scene_pairing": scene_pairing,
        "lanes": {"original_mujoco_target20_replay": original_summary, "isaac_stage2_arm_gripper_target_replay": source_summary},
        "typed_verdict": _verdict(original=original_summary, source=source_summary),
        "telemetry": str(telemetry_path),
    }
    _json_dump(output / "stage2_action_replay_receipt.json", receipt)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed-admission-episode-dir", type=Path, required=True)
    parser.add_argument("--producer-stage2-trace", type=Path, required=True)
    parser.add_argument("--producer-env-id", type=int, default=9)
    parser.add_argument("--producer-episode-index", type=int, default=0)
    parser.add_argument("--producer-diagnostic-json", type=Path)
    parser.add_argument("--stage2-control-steps", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
