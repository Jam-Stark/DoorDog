"""Resolved native-position realization for the r4 true-100/45 control surface."""

from __future__ import annotations

from dataclasses import dataclass
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
import yaml

from gr00t.rl.sim2sim.mujoco.names import SIM_JOINT_NAMES
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


@dataclass(frozen=True)
class ResolvedNativePositionContractR4:
    joint_names: tuple[str, ...]
    stiffness: tuple[float, ...]
    damping: tuple[float, ...]
    effort_limit: tuple[float, ...]
    armature: tuple[float, ...]
    default_position: tuple[float, ...]
    config_path: str

    @classmethod
    def from_config(cls, config_path: Path) -> "ResolvedNativePositionContractR4":
        path = config_path.resolve(strict=True)
        robot = yaml.safe_load(path.read_text(encoding="utf-8"))["robot"]
        names = tuple(robot["dof_names"])
        if names != SIM_JOINT_NAMES:
            raise ValueError("READY config robot.dof_names does not match the MuJoCo robot contract.")
        control = robot["control"]
        stiffness_map = control["stiffness"]
        damping_map = control["damping"]
        control_key = lambda name: (
            "hip" if "hip" in name else
            "thigh" if "thigh" in name else
            "calf" if "calf" in name else
            name
        )
        stiffness = [float(stiffness_map[control_key(name)]) for name in names]
        damping = [float(damping_map[control_key(name)]) for name in names]
        effort = list(map(float, robot["dof_effort_limit_list"]))
        armature = list(map(float, robot["dof_armature_list"]))
        if not all(len(values) == len(names) for values in (stiffness, damping, effort, armature)):
            raise ValueError("READY native-position lists must align with robot.dof_names.")
        for gripper in ("arm_j7", "arm_j8"):
            index = names.index(gripper)
            stiffness[index] = 1300.0
            damping[index] = 32.0
            effort[index] = 45.0
        return cls(
            joint_names=names,
            stiffness=tuple(stiffness),
            damping=tuple(damping),
            effort_limit=tuple(effort),
            armature=tuple(armature),
            default_position=resolved_a2_piper_contract().default_dof_pos,
            config_path=str(path),
        )

    def values_by_joint(self, values: tuple[float, ...]) -> dict[str, float]:
        return dict(zip(self.joint_names, values, strict=True))


@dataclass(frozen=True)
class NameResolvedPositionActuatorMapR4:
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
    ) -> "NameResolvedPositionActuatorMapR4":
        joint_ids = np.asarray(
            [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in robot_joint_names],
            dtype=np.int32,
        )
        actuator_names = tuple(f"{name}_position" for name in robot_joint_names)
        actuator_ids = np.asarray(
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

    def write_robot_position_target(self, data: mujoco.MjData, target: np.ndarray) -> None:
        if target.shape != (len(self.robot_joint_names),):
            raise ValueError("native position target shape does not match the robot joint contract.")
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
            "write_contract": "data.ctrl[name_resolved_robot_position_actuator_ids] = position_target",
            "trace_contract": "robot_ctrl_effort reads actuator_force in robot_joint_names order",
        }


class NativePositionSceneR4:
    """Convert the composed external-PD motor scene to native position servos."""

    def __init__(self, source_scene: Path, contract: ResolvedNativePositionContractR4):
        self.source_scene = source_scene.resolve(strict=True)
        self.contract = contract

    def write(self, output_scene: Path, output_report: Path) -> None:
        output_scene = output_scene.resolve()
        output_scene.parent.mkdir(parents=True, exist_ok=True)
        root = ET.parse(self.source_scene).getroot()
        root.set("model", "doordog_paired_campaign_scene_r4_native_position")
        option = root.find("option")
        if option is None:
            raise ValueError("composed scene lacks option")
        option.set("integrator", "implicitfast")
        actuator = root.find("actuator")
        if actuator is None:
            raise ValueError("composed scene lacks actuator section")

        for name, kp, kv, effort, armature in zip(
            self.contract.joint_names,
            self.contract.stiffness,
            self.contract.damping,
            self.contract.effort_limit,
            self.contract.armature,
            strict=True,
        ):
            joint = root.find(f".//joint[@name='{name}']")
            motor = actuator.find(f"motor[@name='{name}_motor']")
            if joint is None or motor is None:
                raise ValueError(f"native-position conversion lacks {name}")
            joint.set("armature", f"{armature:.12g}")
            joint.set("actuatorfrcrange", f"{-effort:.12g} {effort:.12g}")
            index = list(actuator).index(motor)
            actuator.remove(motor)
            servo = ET.Element(
                "position",
                {
                    "name": f"{name}_position",
                    "joint": name,
                    "kp": f"{kp:.12g}",
                    "kv": f"{kv:.12g}",
                    "forcerange": f"{-effort:.12g} {effort:.12g}",
                    "forcelimited": "true",
                },
            )
            actuator.insert(index, servo)

        key = root.find(".//keyframe/key[@name='scene_home']")
        if key is None:
            raise ValueError("composed scene lacks scene_home keyframe")
        old_ctrl = [float(value) for value in key.attrib["ctrl"].split()]
        key.set(
            "ctrl",
            " ".join(
                f"{value:.12g}"
                for value in [*old_ctrl[:2], *self.contract.default_position]
            ),
        )
        ET.indent(root, space="  ")
        output_scene.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
        model = mujoco.MjModel.from_xml_path(str(output_scene))
        mapping = NameResolvedPositionActuatorMapR4.from_model(model, self.contract.joint_names)
        if mapping.door_hinge_actuator_id != 0 or mapping.handle_actuator_id != 1:
            raise ValueError("native-position scene lost the door-first actuator contract")
        report = {
            "schema": "doordog.sim2sim.native_position_scene_build_report.r4.v1",
            "result_classification": "VALID_COMPARABLE_WITH_DECLARED_CONTROL_DEVIATION",
            "mujoco_version": mujoco.__version__,
            "source_scene": str(self.source_scene),
            "output_scene": str(output_scene),
            "compiled": {"nq": model.nq, "nv": model.nv, "nu": model.nu, "nbody": model.nbody},
            "integrator": "implicitfast",
            "resolved_control": {
                "stiffness_by_joint": self.contract.values_by_joint(self.contract.stiffness),
                "damping_by_joint": self.contract.values_by_joint(self.contract.damping),
                "effort_limit_by_joint": self.contract.values_by_joint(self.contract.effort_limit),
                "armature_by_joint": self.contract.values_by_joint(self.contract.armature),
                "source": self.contract.config_path,
                "owner_gripper_surface": {"kp": 1300.0, "kv": 32.0, "effort": 45.0},
            },
            "d5_authorized_deviation": {
                "from": "EXTERNAL_PD_WITH_PER_PHYSICS_STEP_PYTHON_TORQUE_CLIP",
                "to": "MUJOCO_NATIVE_POSITION_ACTUATOR_WITH_FORCERANGE",
                "robot_scope": "ALL_20_JOINTS_INCLUDING_LEGS",
                "reason": "true 100/45 external PD first exceeded 1e6 qacc on arm_j4 before contact",
                "semantic_difference": (
                    "MuJoCo applies servo stiffness/damping and force limiting inside the implicitfast solve; "
                    "there is no Python per-step torque-clip operation."
                ),
            },
            "actuator_mapping": mapping.receipt(model),
        }
        output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
