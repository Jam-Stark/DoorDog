"""Name-resolved actuator and joint addresses for composed A2+Piper scenes."""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np


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
        actuator_names = tuple(f"{name}_motor" for name in robot_joint_names)
        actuator_ids = np.array(
            [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name) for name in actuator_names],
            dtype=np.int32,
        )
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

    def robot_actuator_force(self, data: mujoco.MjData) -> np.ndarray:
        return data.actuator_force[self.robot_actuator_ids].copy()

    def robot_generalized_force(self, data: mujoco.MjData) -> np.ndarray:
        return data.qfrc_actuator[self.robot_qvel_addresses].copy()

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
