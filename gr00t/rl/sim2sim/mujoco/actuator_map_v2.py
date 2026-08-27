"""Name-resolved actuator and joint addresses for composed A2+Piper scenes."""

from __future__ import annotations

import math
from dataclasses import dataclass

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
