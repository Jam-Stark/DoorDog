"""Name-resolved actuator and joint addresses for composed A2+Piper scenes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import mujoco
import numpy as np


DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION = (
    "DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION"
)
MUJOCO_LOCAL_DECLARED_REALIZATION = "MUJOCO_LOCAL_DECLARED_REALIZATION"
DEPTHADD_V3_PRODUCTION_JOINT_ORDER = (
    "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
    "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint",
    "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
    "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
    "arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6", "arm_j7", "arm_j8",
)


@dataclass(frozen=True)
class EndpointVelocityProjectionTelemetry:
    """Native endpoint values and the declared post-step velocity projection."""

    native_qpos20: np.ndarray
    native_qvel20: np.ndarray
    projected_qvel20: np.ndarray
    qpos_correction20: np.ndarray
    projected_mask20: np.ndarray
    projected_count: int
    native_max_velocity_limit_ratio: float
    projected_max_velocity_limit_ratio: float
    native_actuator_force20: np.ndarray
    native_qfrc_actuator20_nm: np.ndarray
    native_qfrc_constraint20_nm: np.ndarray


@dataclass(frozen=True)
class VelocityLimitedPdTargetTelemetry:
    """Per-substep MuJoCo-local position-target realization."""

    raw_target20: np.ndarray
    drive_target20: np.ndarray
    shaping_mask20: np.ndarray
    shaping_count: int
    shaping_delta20: np.ndarray
    max_abs_delta_rad: float
    kp20: np.ndarray
    kd20: np.ndarray
    maximum_delta20_rad: np.ndarray


def configure_depthadd_v3_contact_solref_2dt(model: mujoco.MjModel) -> dict[str, object]:
    """Apply the accepted finger/handle MuJoCo contact realization to a compiled scene."""

    body_ids = set()
    for name in ("arm_body7", "arm_body8", "door_handle"):
        body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if body_id < 0:
            raise RuntimeError(f"MuJoCo local contact realization lacks body {name!r}")
        body_ids.add(body_id)
    solref = np.asarray((2.0 * float(model.opt.timestep), 1.0), dtype=np.float64)
    geoms: list[dict[str, object]] = []
    for geom_id, body_id in enumerate(model.geom_bodyid):
        if int(body_id) not in body_ids:
            continue
        if int(model.geom_contype[geom_id]) == 0 and int(model.geom_conaffinity[geom_id]) == 0:
            continue
        before = model.geom_solref[geom_id].copy()
        model.geom_solref[geom_id] = solref
        geoms.append(
            {
                "geom": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id)
                or f"geom_{geom_id}",
                "body": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(body_id))
                or f"body_{body_id}",
                "solref_before": before.tolist(),
                "solref_after": model.geom_solref[geom_id].tolist(),
            }
        )
    if not geoms:
        raise RuntimeError("MuJoCo local contact realization found no finger/handle collision geoms")
    return {
        "status": MUJOCO_LOCAL_DECLARED_REALIZATION,
        "contact_realization": "geom_solref=[2*model.opt.timestep,1.0] on arm_body7/arm_body8/door_handle collision-enabled geoms",
        "boundary": "MuJoCo-local declared realization; not PhysX or native-engine equivalence",
        "solimp": "UNCHANGED",
        "friction": "UNCHANGED",
        "geometry": "UNCHANGED",
        "geoms": geoms,
    }


def _named_id(model: mujoco.MjModel, object_type: mujoco.mjtObj, object_id: int) -> str:
    """Return a stable MuJoCo name for an already-resolved object ID."""

    return mujoco.mj_id2name(model, object_type, object_id) or f"object_{object_id}"


def _collision_geoms_for_body(model: mujoco.MjModel, body_id: int) -> tuple[int, ...]:
    return tuple(
        geom_id
        for geom_id, geom_body_id in enumerate(model.geom_bodyid)
        if int(geom_body_id) == body_id
        and not (
            int(model.geom_contype[geom_id]) == 0
            and int(model.geom_conaffinity[geom_id]) == 0
        )
    )


def _body_point_velocity_world(
    model: mujoco.MjModel, data: mujoco.MjData, *, body_id: int, point_world: np.ndarray
) -> np.ndarray:
    jacobian_position = np.zeros((3, model.nv), dtype=np.float64)
    jacobian_rotation = np.zeros((3, model.nv), dtype=np.float64)
    mujoco.mj_jac(
        model, data, jacobian_position, jacobian_rotation, point_world, body_id
    )
    return jacobian_position @ data.qvel


def capture_depthadd_v3_pre_step_authority(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    mapping: "NameResolvedActuatorMapV2",
    *,
    raw_target20: np.ndarray,
    drive_target20: np.ndarray,
) -> dict[str, Any]:
    """Capture the exact MuJoCo state authority immediately before one native step."""

    raw_target = np.asarray(raw_target20, dtype=np.float64)
    drive_target = np.asarray(drive_target20, dtype=np.float64)
    if raw_target.shape != (20,) or drive_target.shape != (20,):
        raise ValueError("pre-step authority requires raw_target20[20] and drive_target20[20]")
    state_spec = mujoco.mjtState.mjSTATE_FULLPHYSICS
    state = np.empty(mujoco.mj_stateSize(model, state_spec), dtype=np.float64)
    mujoco.mj_getState(model, data, state, state_spec)
    values = (
        state,
        data.ctrl,
        data.qpos[mapping.robot_qpos_addresses],
        data.qvel[mapping.robot_qvel_addresses],
        raw_target,
        drive_target,
    )
    if not all(np.isfinite(value).all() for value in values):
        raise FloatingPointError("pre-step authority contains a non-finite value")
    return {
        "sample_timing": "immediately before native MuJoCo mj_step",
        "mjstate_spec": "mjSTATE_FULLPHYSICS",
        "mjstate_fullphysics": state.tolist(),
        "qvel_full_pre_integration_rad_s": data.qvel.tolist(),
        "data_ctrl": data.ctrl.tolist(),
        "eq_active": data.eq_active.tolist(),
        "time_s": float(data.time),
        "raw_target20_rad": raw_target.tolist(),
        "drive_target20_rad": drive_target.tolist(),
        "model_runtime": {
            "timestep_s": float(model.opt.timestep),
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
        },
    }


def capture_depthadd_v3_native_contact_snapshot(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    mapping: "NameResolvedActuatorMapV2",
    *,
    raw_target20: np.ndarray,
    drive_target20: np.ndarray,
    pre_step_fullphysics: np.ndarray,
) -> dict[str, Any]:
    """Capture the native contact surface immediately after ``mj_step``.

    This deliberately has no projection or ``mj_forward`` side effect.  Callers
    invoke it while the native endpoint remains resident, then may separately
    apply their declared endpoint-projection backup.
    """

    raw_target = np.asarray(raw_target20, dtype=np.float64)
    drive_target = np.asarray(drive_target20, dtype=np.float64)
    pre_state = np.asarray(pre_step_fullphysics, dtype=np.float64)
    if raw_target.shape != (20,) or drive_target.shape != (20,):
        raise ValueError("native contact snapshot requires raw_target20[20] and drive_target20[20]")
    if pre_state.shape != (mujoco.mj_stateSize(model, mujoco.mjtState.mjSTATE_FULLPHYSICS),):
        raise ValueError("native contact snapshot requires the exact pre-step mjSTATE_FULLPHYSICS")
    pre_integration_data = mujoco.MjData(model)
    mujoco.mj_setState(
        model, pre_integration_data, pre_state, mujoco.mjtState.mjSTATE_FULLPHYSICS
    )
    mujoco.mj_forward(model, pre_integration_data)
    finger_body_ids = tuple(
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        for name in ("arm_body7", "arm_body8")
    )
    handle_body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "door_handle")
    if any(body_id < 0 for body_id in finger_body_ids) or handle_body_id < 0:
        raise RuntimeError("native contact snapshot requires arm_body7/arm_body8/door_handle")
    finger_geoms = tuple(
        _collision_geoms_for_body(model, body_id) for body_id in finger_body_ids
    )
    handle_geoms = _collision_geoms_for_body(model, handle_body_id)
    if not all(finger_geoms) or not handle_geoms:
        raise RuntimeError("native contact snapshot requires collision-enabled finger and handle geoms")

    closest_pairs: list[dict[str, Any]] = []
    for finger_index, geoms in enumerate(finger_geoms):
        for finger_geom_id in geoms:
            for handle_geom_id in handle_geoms:
                fromto = np.empty(6, dtype=np.float64)
                distance = float(
                    mujoco.mj_geomDistance(
                        model, data, finger_geom_id, handle_geom_id, 10.0, fromto
                    )
                )
                fromto_valid = distance < 10.0
                closest_pairs.append(
                    {
                        "finger_index": finger_index,
                        "finger_geom": _named_id(model, mujoco.mjtObj.mjOBJ_GEOM, finger_geom_id),
                        "handle_geom": _named_id(model, mujoco.mjtObj.mjOBJ_GEOM, handle_geom_id),
                        "mj_geomDistance_m": distance,
                        "fromto_valid": fromto_valid,
                        "closest_point_finger_world_m": fromto[:3].tolist() if fromto_valid else None,
                        "closest_point_handle_world_m": fromto[3:].tolist() if fromto_valid else None,
                    }
                )

    detected_contacts: list[dict[str, Any]] = []
    active_contacts: list[dict[str, Any]] = []
    finger_handle_contact_counts = [0, 0]
    finger_handle_force_on_handle_world = np.zeros((2, 3), dtype=np.float64)
    for contact_index in range(data.ncon):
        contact = data.contact[contact_index]
        geom1 = int(contact.geom1)
        geom2 = int(contact.geom2)
        body1 = int(model.geom_bodyid[geom1])
        body2 = int(model.geom_bodyid[geom2])
        efc_address = int(contact.efc_address)
        solver_active = efc_address >= 0
        wrench_contact = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, contact_index, wrench_contact)
        contact_to_world = contact.frame.reshape(3, 3).T
        relative_velocity_world = _body_point_velocity_world(
            model, pre_integration_data, body_id=body2, point_world=contact.pos
        ) - _body_point_velocity_world(
            model, pre_integration_data, body_id=body1, point_world=contact.pos
        )
        finger_index = next(
            (
                index
                for index, finger_body_id in enumerate(finger_body_ids)
                if handle_body_id in (body1, body2) and finger_body_id in (body1, body2)
            ),
            None,
        )
        if solver_active and finger_index is not None:
            finger_handle_contact_counts[finger_index] += 1
            force_world = contact_to_world @ wrench_contact[:3]
            if body1 == finger_body_ids[finger_index] and body2 == handle_body_id:
                finger_handle_force_on_handle_world[finger_index] += force_world
            elif body2 == finger_body_ids[finger_index] and body1 == handle_body_id:
                finger_handle_force_on_handle_world[finger_index] -= force_world
        contact_row = (
            {
                "contact_index": contact_index,
                "geom1": _named_id(model, mujoco.mjtObj.mjOBJ_GEOM, geom1),
                "geom2": _named_id(model, mujoco.mjtObj.mjOBJ_GEOM, geom2),
                "body1": _named_id(model, mujoco.mjtObj.mjOBJ_BODY, body1),
                "body2": _named_id(model, mujoco.mjtObj.mjOBJ_BODY, body2),
                "solver_active": solver_active,
                "exclude": int(contact.exclude),
                "efc_address": efc_address,
                "distance_m": float(contact.dist),
                "pre_integration_position_world_m": contact.pos.tolist(),
                "pre_integration_frame_contact_to_world": contact.frame.tolist(),
                "normal_force_n": float(wrench_contact[0]),
                "tangent_force_n": wrench_contact[1:3].tolist(),
                "force_torque_contact_frame": wrench_contact.tolist(),
                "force_world_n": (contact_to_world @ wrench_contact[:3]).tolist(),
                "pre_integration_relative_velocity_body2_minus_body1_world_m_s": relative_velocity_world.tolist(),
                "pre_integration_relative_velocity_body2_minus_body1_contact_m_s": (
                    contact_to_world.T @ relative_velocity_world
                ).tolist(),
                "finger_handle_pair": finger_index is not None,
                "finger_index": finger_index,
            }
        )
        detected_contacts.append(contact_row)
        if solver_active:
            active_contacts.append(contact_row)

    handle_rotation_world = data.xmat[handle_body_id].reshape(3, 3)
    handle_position_world = data.xpos[handle_body_id]
    finger_poses = []
    for finger_index, body_id in enumerate(finger_body_ids):
        finger_rotation_world = data.xmat[body_id].reshape(3, 3)
        finger_poses.append(
            {
                "finger_index": finger_index,
                "body": _named_id(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "position_handle_frame_m": (
                    handle_rotation_world.T @ (data.xpos[body_id] - handle_position_world)
                ).tolist(),
                "rotation_handle_to_finger": (
                    handle_rotation_world.T @ finger_rotation_world
                ).tolist(),
            }
        )

    door_joints = tuple(
        name
        for name in ("door_hinge", "handle_hinge", "latch_slide")
        if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) >= 0
    )
    door_qpos_addresses = np.asarray(
        [
            model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)]
            for name in door_joints
        ],
        dtype=np.int32,
    )
    door_qvel_addresses = np.asarray(
        [
            model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)]
            for name in door_joints
        ],
        dtype=np.int32,
    )
    j7_j8_indices = np.asarray(
        [mapping.robot_joint_names.index("arm_j7"), mapping.robot_joint_names.index("arm_j8")],
        dtype=np.int32,
    )
    robot_qpos20 = data.qpos[mapping.robot_qpos_addresses].copy()
    robot_qvel20 = data.qvel[mapping.robot_qvel_addresses].copy()
    actuator_force20 = mapping.robot_actuator_force(data)
    qfrc_actuator20 = mapping.robot_generalized_force(data)
    qfrc_constraint20 = data.qfrc_constraint[mapping.robot_qvel_addresses].copy()
    qacc20 = data.qacc[mapping.robot_qvel_addresses].copy()
    qfrc_passive20 = data.qfrc_passive[mapping.robot_qvel_addresses].copy()
    qfrc_smooth20 = data.qfrc_smooth[mapping.robot_qvel_addresses].copy()
    finite_vectors = (
        raw_target,
        drive_target,
        robot_qpos20,
        robot_qvel20,
        actuator_force20,
        qfrc_actuator20,
        qfrc_constraint20,
        qacc20,
        qfrc_passive20,
        qfrc_smooth20,
        data.qpos[door_qpos_addresses],
        data.qvel[door_qvel_addresses],
    )
    if not all(np.isfinite(values).all() for values in finite_vectors):
        raise FloatingPointError("native contact snapshot contains a non-finite primary surface")
    return {
        "sample_timing": "after native MuJoCo mj_step and before endpoint projection or mj_forward",
        "raw_target20_rad": raw_target.tolist(),
        "drive_target20_rad": drive_target.tolist(),
        "native_state": {
            "robot_joint_pos20_rad": robot_qpos20.tolist(),
            "robot_joint_vel20_rad_s": robot_qvel20.tolist(),
            "qacc20_rad_s2": qacc20.tolist(),
            "qfrc_actuator20_Nm": qfrc_actuator20.tolist(),
            "qfrc_constraint20_Nm": qfrc_constraint20.tolist(),
            "qfrc_passive20_Nm": qfrc_passive20.tolist(),
            "qfrc_smooth20_Nm": qfrc_smooth20.tolist(),
            "actuator_force20": actuator_force20.tolist(),
            "door_joint_names": list(door_joints),
            "door_joint_pos": data.qpos[door_qpos_addresses].tolist(),
            "door_joint_vel": data.qvel[door_qvel_addresses].tolist(),
        },
        "j7_j8": {
            "joint_names": [mapping.robot_joint_names[index] for index in j7_j8_indices],
            "qpos_rad": robot_qpos20[j7_j8_indices].tolist(),
            "qvel_rad_s": robot_qvel20[j7_j8_indices].tolist(),
            "raw_target_rad": raw_target[j7_j8_indices].tolist(),
            "drive_target_rad": drive_target[j7_j8_indices].tolist(),
            "actuator_force": actuator_force20[j7_j8_indices].tolist(),
            "qfrc_actuator_Nm": qfrc_actuator20[j7_j8_indices].tolist(),
            "qfrc_constraint_Nm": qfrc_constraint20[j7_j8_indices].tolist(),
        },
        "finger_handle": {
            "finger_collision_geoms": [
                [_named_id(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id) for geom_id in geoms]
                for geoms in finger_geoms
            ],
            "handle_collision_geoms": [
                _named_id(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id) for geom_id in handle_geoms
            ],
            "closest_pairs": closest_pairs,
            "detected_contacts": detected_contacts,
            "active_contacts": active_contacts,
            "solver_active_finger_handle_contact_counts": finger_handle_contact_counts,
            "solver_active_finger_handle_force_on_handle_world_N": (
                finger_handle_force_on_handle_world.tolist()
            ),
            "bilateral_active_contact": bool(all(finger_handle_contact_counts)),
            "finger_pose_in_handle_frame": finger_poses,
        },
    }


@dataclass(frozen=True)
class NameResolvedActuatorMapV2:
    robot_joint_names: tuple[str, ...]
    robot_actuator_names: tuple[str, ...]
    robot_qpos_addresses: np.ndarray
    robot_qvel_addresses: np.ndarray
    robot_actuator_ids: np.ndarray
    door_hinge_actuator_id: int
    handle_actuator_id: int

    @classmethod
    def from_model(
        cls, model: mujoco.MjModel, robot_joint_names: tuple[str, ...]
    ) -> "NameResolvedActuatorMapV2":
        joint_ids = np.array(
            [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in robot_joint_names],
            dtype=np.int32,
        )
        if np.any(joint_ids < 0):
            raise RuntimeError("name-resolved robot map cannot contain a missing joint")
        actuator_names = tuple(f"{name}_motor" for name in robot_joint_names)
        actuator_ids = np.array(
            [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name) for name in actuator_names],
            dtype=np.int32,
        )
        if np.any(actuator_ids < 0):
            raise RuntimeError("name-resolved robot map cannot contain a missing actuator")
        return cls(
            robot_joint_names=robot_joint_names,
            robot_actuator_names=actuator_names,
            robot_qpos_addresses=model.jnt_qposadr[joint_ids].copy(),
            robot_qvel_addresses=model.jnt_dofadr[joint_ids].copy(),
            robot_actuator_ids=actuator_ids,
            door_hinge_actuator_id=mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_ACTUATOR, "door_hinge_capped_position"
            ),
            handle_actuator_id=mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_ACTUATOR, "handle_capped_position"
            ),
        )

    def write_robot_ctrl(self, data: mujoco.MjData, effort: np.ndarray) -> None:
        if effort.shape != (len(self.robot_joint_names),):
            raise ValueError(f"robot effort shape {effort.shape} does not match the joint contract")
        data.ctrl[self.robot_actuator_ids] = effort

    def write_robot_position_target(self, data: mujoco.MjData, target: np.ndarray) -> None:
        if target.shape != (len(self.robot_joint_names),):
            raise ValueError(f"robot target shape {target.shape} does not match the joint contract")
        data.ctrl[self.robot_actuator_ids] = target

    def realize_velocity_limited_pd_target(
        self,
        model: mujoco.MjModel,
        data: mujoco.MjData,
        raw_target20: np.ndarray,
        velocity_limit20: np.ndarray,
    ) -> VelocityLimitedPdTargetTelemetry:
        """Realize the accepted local PD target surface before one physics substep."""

        raw_target = np.asarray(raw_target20, dtype=np.float64)
        limits = np.asarray(velocity_limit20, dtype=np.float64)
        if raw_target.shape != (20,) or limits.shape != (20,):
            raise ValueError("velocity-limited PD target requires raw_target20[20] and velocity_limit20[20]")
        kp20 = model.actuator_gainprm[self.robot_actuator_ids, 0].copy()
        kd20 = -model.actuator_biasprm[self.robot_actuator_ids, 2].copy()
        gear20 = model.actuator_gear[self.robot_actuator_ids].copy()
        if (
            np.any(kp20 <= 0.0)
            or np.any(kd20 <= 0.0)
            or not np.allclose(gear20[:, 0], 1.0, rtol=0.0, atol=0.0)
            or not np.allclose(gear20[:, 1:], 0.0, rtol=0.0, atol=0.0)
        ):
            raise RuntimeError("MuJoCo local PD target realization requires direct unit-gear actuators with positive KP/KD")
        qpos20 = data.qpos[self.robot_qpos_addresses].copy()
        maximum_delta20_rad = limits * kd20 / kp20
        drive_target20 = qpos20 + np.clip(
            raw_target - qpos20, -maximum_delta20_rad, maximum_delta20_rad
        )
        shaping_delta20 = drive_target20 - raw_target
        shaping_mask20 = shaping_delta20 != 0.0
        return VelocityLimitedPdTargetTelemetry(
            raw_target20=raw_target,
            drive_target20=drive_target20,
            shaping_mask20=shaping_mask20,
            shaping_count=int(np.count_nonzero(shaping_mask20)),
            shaping_delta20=shaping_delta20,
            max_abs_delta_rad=float(np.max(np.abs(shaping_delta20))),
            kp20=kp20,
            kd20=kd20,
            maximum_delta20_rad=maximum_delta20_rad,
        )

    def robot_actuator_force(self, data: mujoco.MjData) -> np.ndarray:
        return data.actuator_force[self.robot_actuator_ids].copy()

    def robot_generalized_force(self, data: mujoco.MjData) -> np.ndarray:
        return data.qfrc_actuator[self.robot_qvel_addresses].copy()

    def step_with_declared_endpoint_velocity_projection(
        self,
        model: mujoco.MjModel,
        data: mujoco.MjData,
        velocity_limit20: np.ndarray,
        native_snapshot_callback: Callable[[], None] | None = None,
    ) -> EndpointVelocityProjectionTelemetry:
        """Advance one native substep, then realize the declared 20D velocity surface.

        MuJoCo has no native joint-velocity inequality for this actuator face.
        The projection is deliberately a runtime approximation: it acts after the
        native implicitfast solve, corrects the scalar-joint endpoint displacement,
        and refreshes derived quantities without re-solving the preceding contact.
        """

        width = len(self.robot_joint_names)
        limits = np.asarray(velocity_limit20, dtype=np.float64)
        if width != 20 or self.robot_joint_names != DEPTHADD_V3_PRODUCTION_JOINT_ORDER:
            raise RuntimeError(f"endpoint velocity projection requires 20 robot joints, got {width}")
        if limits.shape != (20,) or not np.isfinite(limits).all() or np.any(limits <= 0.0):
            raise ValueError("endpoint velocity projection requires finite positive velocity_limit20[20]")
        if (
            self.robot_qpos_addresses.shape != (20,)
            or self.robot_qvel_addresses.shape != (20,)
            or self.robot_actuator_ids.shape != (20,)
            or np.any(self.robot_qpos_addresses < 0)
            or np.any(self.robot_qvel_addresses < 0)
            or np.any(self.robot_actuator_ids < 0)
            or len(set(self.robot_joint_names)) != 20
        ):
            raise RuntimeError("endpoint velocity projection requires a unique 20D name-resolved robot map")
        if not math.isfinite(float(model.opt.timestep)) or float(model.opt.timestep) <= 0.0:
            raise ValueError("endpoint velocity projection requires a positive finite MuJoCo timestep")

        mujoco.mj_step(model, data)
        native_qpos20 = data.qpos[self.robot_qpos_addresses].copy()
        native_qvel20 = data.qvel[self.robot_qvel_addresses].copy()
        native_actuator_force20 = self.robot_actuator_force(data)
        native_qfrc_actuator20_nm = self.robot_generalized_force(data)
        native_qfrc_constraint20_nm = data.qfrc_constraint[self.robot_qvel_addresses].copy()
        if not (
            np.isfinite(native_qpos20).all()
            and np.isfinite(native_qvel20).all()
            and np.isfinite(native_actuator_force20).all()
            and np.isfinite(native_qfrc_actuator20_nm).all()
            and np.isfinite(native_qfrc_constraint20_nm).all()
        ):
            raise FloatingPointError("native MuJoCo endpoint telemetry is non-finite")
        if native_snapshot_callback is not None:
            native_snapshot_callback()

        projected_qvel20 = np.clip(native_qvel20, -limits, limits)
        qpos_correction20 = (projected_qvel20 - native_qvel20) * float(model.opt.timestep)
        projected_mask20 = projected_qvel20 != native_qvel20
        if np.any(projected_mask20):
            data.qvel[self.robot_qvel_addresses] = projected_qvel20
            data.qpos[self.robot_qpos_addresses] = native_qpos20 + qpos_correction20
            mujoco.mj_forward(model, data)
        return EndpointVelocityProjectionTelemetry(
            native_qpos20=native_qpos20,
            native_qvel20=native_qvel20,
            projected_qvel20=projected_qvel20,
            qpos_correction20=qpos_correction20,
            projected_mask20=projected_mask20,
            projected_count=int(np.count_nonzero(projected_mask20)),
            native_max_velocity_limit_ratio=float(np.max(np.abs(native_qvel20) / limits)),
            projected_max_velocity_limit_ratio=float(np.max(np.abs(projected_qvel20) / limits)),
            native_actuator_force20=native_actuator_force20,
            native_qfrc_actuator20_nm=native_qfrc_actuator20_nm,
            native_qfrc_constraint20_nm=native_qfrc_constraint20_nm,
        )

    def receipt(self, model: mujoco.MjModel) -> dict[str, object]:
        return {
            "robot_joint_names": list(self.robot_joint_names),
            "robot_actuator_names": list(self.robot_actuator_names),
            "robot_actuator_ids": self.robot_actuator_ids.tolist(),
            "door_actuator_ids": {
                "door_hinge_capped_position": self.door_hinge_actuator_id,
                "handle_capped_position": self.handle_actuator_id,
            },
            "compiled_actuator_order": [
                mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index)
                for index in range(model.nu)
            ],
            "write_contract": "data.ctrl[name_resolved_robot_actuator_ids]",
            "trace_contract": "robot_ctrl_effort follows robot_joint_names and reads actuator_force by the same IDs",
        }
