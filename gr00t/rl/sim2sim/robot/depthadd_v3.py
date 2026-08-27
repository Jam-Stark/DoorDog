"""DepthADD v3 handoff-backed floating-base A2+Piper MJCF builder."""

from __future__ import annotations

import json
import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

import mujoco
import yaml

from gr00t.rl.sim2sim.mujoco.actuator_map_v2 import (
    DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION,
)
from .contract import A2PiperRobotContract
from .mjcf_builder import WORLD_TO_OPENGL_WXYZ, _id_map, _quat_multiply, _values


def _camera_fovy_deg(camera: Mapping[str, Any]) -> float:
    focal = float(camera["focal_length"])
    vertical = float(camera["aperture_hv"][1])
    return math.degrees(2.0 * math.atan(vertical / (2.0 * focal)))


class DepthADDV3MjcfBuilder:
    """Build the robot solely from the DepthADD v3 handoff authority.

    The generated affine actuators realize the handoff's ideal-PD face inside
    MuJoCo at each 200 Hz physics step.
    """

    _CAMERA_KEYS = (("left_d435", "left"), ("right_d435", "right"), ("head_rgb", "head"))

    def __init__(self, urdf_path: Path, handoff_dir: Path):
        self.urdf_path = Path(urdf_path).resolve(strict=True)
        self.handoff_dir = Path(handoff_dir).resolve(strict=True)
        self.manifest = yaml.safe_load((self.handoff_dir / "sim2sim_policy_manifest.yaml").read_text())
        self.resolved_config = yaml.safe_load((self.handoff_dir / "resolved_config.yaml").read_text())
        self.plant_contract = json.loads((self.handoff_dir / "depthadd_plant_observation_contract.json").read_text())
        self.contract = self._handoff_robot_contract()

    def _handoff_robot_contract(self) -> A2PiperRobotContract:
        control = self.manifest["control"]
        names = tuple(control["joint_order"])
        defaults = tuple(float(value) for value in control["default_joint_pos_in_joint_order"])
        effort = tuple(float(value) for value in control["effort_limit_nm_in_joint_order"])
        resolved_robot = self.resolved_config["env"]["config"]["robot"]
        velocity = tuple(float(value) for value in resolved_robot["dof_vel_limit_list"])
        kp = control["kp_by_group"]
        kd = control["kd_by_group"]
        stiffness = tuple(float(kp["hip" if "hip" in name else "thigh" if "thigh" in name else "calf" if "calf" in name else name]) for name in names)
        damping = tuple(float(kd["hip" if "hip" in name else "thigh" if "thigh" in name else "calf" if "calf" in name else name]) for name in names)
        if len(names) != 20 or not (
            len(defaults) == len(effort) == len(velocity) == len(stiffness) == len(damping) == 20
        ):
            raise ValueError("DepthADD handoff must declare exactly 20 controlled joints")
        if tuple(resolved_robot["dof_names"]) != names:
            raise ValueError("resolved robot velocity-limit order disagrees with the handoff joint order")
        if int(control["physics_hz"]) != 200 or float(control["physics_dt_s"]) != 0.005:
            raise ValueError("DepthADD handoff requires 200 Hz / 0.005 s physics")
        if tuple(float(value) for value in self.plant_contract["plant"]["arm_effort_limit_nm"]) != effort[12:18]:
            raise ValueError("plant contract arm effort face disagrees with policy manifest")
        gripper = self.plant_contract["plant"]["gripper_face"]
        if tuple(float(value) for value in gripper["stiffness"]) != stiffness[18:] or tuple(float(value) for value in gripper["damping"]) != damping[18:] or tuple(float(value) for value in gripper["effort_limit_nm"]) != effort[18:]:
            raise ValueError("plant contract gripper PD face disagrees with policy manifest")
        return A2PiperRobotContract(
            schema="a2_depthadd_v3_mujoco_robot_contract_v1",
            sim_joint_names=names,
            policy_leg_joint_names=(
                "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
                "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
                "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
            ),
            default_dof_pos=defaults,
            stiffness=stiffness,
            damping=damping,
            torque_limit=effort,
            velocity_limit=velocity,
            action_scale=float(self.resolved_config["env"]["config"]["robot"]["control"]["action_scale"]),
        )

    def _initial_root_qpos(self) -> tuple[float, ...]:
        init_state = self.resolved_config["env"]["config"]["robot"]["init_state"]
        position = tuple(float(value) for value in init_state["pos"])
        rotation_xyzw = tuple(float(value) for value in init_state["rot"])
        if len(position) != 3 or len(rotation_xyzw) != 4:
            raise ValueError("resolved robot init_state must contain pos[3] and rot[4]")
        norm = math.sqrt(sum(value * value for value in rotation_xyzw))
        if norm == 0.0:
            raise ValueError("resolved robot initial quaternion must be nonzero")
        x, y, z, w = (value / norm for value in rotation_xyzw)
        return (*position, w, x, y, z)

    def _xml_tree(self, output_xml: Path) -> tuple[ET.Element, list[dict[str, Any]]]:
        source_spec = mujoco.MjSpec.from_file(str(self.urdf_path))
        root = ET.fromstring(source_spec.to_xml())
        root.set("model", "a2_piper_depthadd_v3")
        compiler = root.find("compiler")
        if compiler is None:
            raise ValueError("URDF conversion did not emit a compiler element")
        compiler.set("angle", "radian")
        compiler.set("meshdir", os.path.relpath(self.urdf_path.parent, output_xml.parent))
        ET.SubElement(root, "option", {"timestep": "0.005", "gravity": "0 0 -9.81", "integrator": "implicitfast"})
        world = root.find("worldbody")
        if world is None:
            raise ValueError("URDF conversion did not emit worldbody")
        source_children = list(world)
        for child in source_children:
            world.remove(child)
        ET.SubElement(world, "light", {"name": "key_light", "pos": "0 0 3", "dir": "0 0 -1"})
        ET.SubElement(world, "geom", {"name": "floor", "type": "plane", "size": "4 4 0.1", "rgba": "0.28 0.29 0.31 1", "contype": "2", "conaffinity": "1"})
        trunk = ET.SubElement(world, "body", {"name": "trunk"})
        ET.SubElement(trunk, "freejoint", {"name": "floating_base"})
        ET.SubElement(trunk, "inertial", {"pos": "0.0069826 -0.0007129 0.0128895", "mass": "19.651", "fullinertia": "0.1417753 0.4077246 0.472248 0.0004005 -0.0069965 -0.0003619"})
        arm_base = ET.Element("body", {"name": "arm_body0", "pos": "0.145 0 0.154"})
        ET.SubElement(arm_base, "inertial", {"pos": "-0.004736411642 0.00002568291346 0.04145151804", "mass": "1.02", "fullinertia": "0.00267433 0.00282612 0.00089624 -0.00000073 -0.00017389 0.0000004"})
        for child in source_children:
            if child.tag == "geom" and child.get("mesh") == "base_link":
                child.set("pos", "0 0 0")
                arm_base.append(child)
            elif child.tag == "body" and child.get("name") == "arm_body1":
                child.set("pos", "0 0 0.123")
                arm_base.append(child)
            else:
                trunk.append(child)
        trunk.append(arm_base)
        if int(self.resolved_config["env"]["config"]["robot"]["asset"]["self_collisions"]) != 0:
            raise ValueError("DepthADD v3 robot collision mapping requires self_collisions=0")
        for geom in trunk.findall(".//geom"):
            geom.set("contype", "1")
            geom.set("conaffinity", "2")
        arm_body6 = trunk.find(".//body[@name='arm_body6']")
        if arm_body6 is None:
            raise KeyError("converted URDF lacks arm_body6 for the handoff TCP frame")
        tcp_body = ET.SubElement(arm_body6, "body", {"name": "arm_body6_to_gripper", "pos": "0 0 0.085"})
        ET.SubElement(tcp_body, "site", {"name": "a2_piper_tcp", "pos": "0 0 0", "size": "0.008", "rgba": "0 1 1 1", "group": "5"})
        for gripper_body in ("arm_body7", "arm_body8"):
            if trunk.find(f".//body[@name='{gripper_body}']") is None:
                raise KeyError(f"converted URDF lacks {gripper_body} required for gripper contact aggregation")
        for name, limit in zip(self.contract.sim_joint_names, self.contract.torque_limit, strict=True):
            joint = root.find(f".//joint[@name='{name}']")
            if joint is None:
                raise KeyError(f"converted URDF lacks handoff joint {name}")
            joint.set("actuatorfrcrange", _values((-limit, limit)))
        camera_receipts: list[dict[str, Any]] = []
        cameras = self.manifest["policy_cameras"]
        for manifest_name, mj_name in self._CAMERA_KEYS:
            camera = cameras[manifest_name]
            source_quat = [float(value) for value in camera["rotation_wxyz"]]
            mujoco_quat = _quat_multiply(source_quat, WORLD_TO_OPENGL_WXYZ)
            fovy = _camera_fovy_deg(camera)
            frame = ET.SubElement(trunk, "body", {"name": f"{mj_name}_camera_frame", "pos": _values(camera["position_m"]), "quat": _values(mujoco_quat)})
            ET.SubElement(frame, "camera", {"name": f"{mj_name}_policy", "fovy": f"{fovy:.12g}", "resolution": _values(tuple(camera["resolution_hw"])[::-1])})
            camera_receipts.append({"handoff_name": manifest_name, "mujoco_name": f"{mj_name}_policy", "parent": "trunk", "position_m": camera["position_m"], "source_rotation_wxyz": source_quat, "mujoco_rotation_wxyz": mujoco_quat, "fovy_deg": fovy, "aperture_hv": camera["aperture_hv"], "clipping_m": camera["clipping_m"], "resolution_hw": camera["resolution_hw"], "update_period_s": camera["update_period_s"]})
        actuator = ET.SubElement(root, "actuator")
        for name, stiffness, damping, limit in zip(
            self.contract.sim_joint_names,
            self.contract.stiffness,
            self.contract.damping,
            self.contract.torque_limit,
            strict=True,
        ):
            ET.SubElement(
                actuator,
                "general",
                {
                    "name": f"{name}_motor",
                    "joint": name,
                    "dyntype": "none",
                    "gaintype": "fixed",
                    "gainprm": f"{stiffness:.12g}",
                    "biastype": "affine",
                    "biasprm": f"0 {-stiffness:.12g} {-damping:.12g}",
                    "ctrllimited": "true",
                    "ctrlrange": "-100 100",
                    "forcelimited": "true",
                    "forcerange": _values((-limit, limit)),
                },
            )
        keyframe = ET.SubElement(root, "keyframe")
        initial_root_qpos = self._initial_root_qpos()
        ET.SubElement(keyframe, "key", {"name": "home", "qpos": _values((*initial_root_qpos, *self.contract.default_dof_pos))})
        return root, camera_receipts

    def write(self, output_xml: Path, output_contract: Path, output_report: Path) -> None:
        output_xml, output_contract, output_report = map(Path, (output_xml, output_contract, output_report))
        for path in (output_xml, output_contract, output_report):
            path.parent.mkdir(parents=True, exist_ok=True)
        root, camera_receipts = self._xml_tree(output_xml)
        ET.indent(root, space="  ")
        output_xml.write_text(ET.tostring(root, encoding="unicode") + "\n")
        model = mujoco.MjModel.from_xml_path(str(output_xml))
        joint_ids = _id_map(model, mujoco.mjtObj.mjOBJ_JOINT, model.njnt)
        actuator_ids = _id_map(model, mujoco.mjtObj.mjOBJ_ACTUATOR, model.nu)
        expected_actuators = [f"{name}_motor" for name in self.contract.sim_joint_names]
        if list(joint_ids)[1:] != list(self.contract.sim_joint_names) or list(actuator_ids) != expected_actuators:
            raise ValueError("compiled robot name/order contract disagrees with DepthADD handoff")
        if (model.nq, model.nv, model.nu) != (27, 26, 20):
            raise ValueError(f"DepthADD robot dimensions must be (27,26,20), got {(model.nq, model.nv, model.nu)}")
        tcp_site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "a2_piper_tcp")
        if tcp_site_id < 0 or int(model.site_group[tcp_site_id]) != 5:
            raise ValueError("DepthADD TCP marker must compile into MJCF group 5")
        frame_mapping = {"tcp": {"parent_body": "arm_body6", "tcp_body": "arm_body6_to_gripper", "tcp_site": "a2_piper_tcp", "local_offset_m": [0.0, 0.0, 0.085], "final_mjcf_group": int(model.site_group[tcp_site_id]), "policy_camera_visible": False, "authority": "DepthADD handoff task_and_plant.tcp_offset_z_m"}, "gripper_contact_bodies": ["arm_body7", "arm_body8"]}
        contract = self.contract.as_dict() | {"robot_xml": str(output_xml.resolve()), "source_urdf": str(self.urdf_path), "floating_base_joint": "floating_base", "qpos_layout": {"floating_base": [0, 7], "actuated": [7, 27]}, "qvel_layout": {"floating_base": [0, 6], "actuated": [6, 26]}, "initial_state": {"root_qpos_mujoco_wxyz": list(self._initial_root_qpos()), "resolved_source_pos": self.resolved_config["env"]["config"]["robot"]["init_state"]["pos"], "resolved_source_rotation_xyzw": self.resolved_config["env"]["config"]["robot"]["init_state"]["rot"], "joint_position": list(self.contract.default_dof_pos)}, "actuator_names": expected_actuators, "position_pd": {"formula": "clip(kp*(q_target-q)-kd*qvel,-effort_limit,+effort_limit)", "mujoco_realization": "implicit affine general actuator with one combined force limit", "cadence": "target refreshed every 0.02 s; drive evaluated every 0.005 s physics step", "physics_hz": 200, "stiffness": self.contract.stiffness, "damping": self.contract.damping, "effort_limit_nm": self.contract.torque_limit, "velocity_limit": self.contract.velocity_limit, "velocity_limit_authority": "resolved env.config.robot.dof_vel_limit_list -> IsaacLab ImplicitActuatorCfg.velocity_limit_sim", "velocity_limit_mujoco_realization": DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION, "velocity_limit_mujoco_realization_semantics": "post-native-step endpoint qvel projection plus implicitfast displacement correction; not a native MuJoCo constraint or PhysX-equivalence claim"}, "collision_masks": {"robot": {"contype": 1, "conaffinity": 2}, "environment": {"contype": 2, "conaffinity": 1}, "self_collisions": False}, "camera_receipts": camera_receipts, "frame_mapping": frame_mapping, "authority": {"policy_manifest": str(self.handoff_dir / "sim2sim_policy_manifest.yaml"), "resolved_config": str(self.handoff_dir / "resolved_config.yaml"), "plant_contract": str(self.handoff_dir / "depthadd_plant_observation_contract.json")}}
        resolved_robot = self.resolved_config["env"]["config"]["robot"]
        if tuple(resolved_robot["dof_names"]) != self.contract.sim_joint_names:
            raise ValueError("resolved armature joint order disagrees with the handoff joint order")
        contract["armature"] = tuple(float(value) for value in resolved_robot["dof_armature_list"])
        report = {"schema": "doordog.sim2sim.depthadd_v3_robot_build_receipt.v1", "evidence_level": "STATIC_PASS_WITH_DECLARED_PLANT_GAP", "mujoco_version": mujoco.__version__, "compiled": {"nq": model.nq, "nv": model.nv, "nu": model.nu, "nbody": model.nbody, "njnt": model.njnt, "ngeom": model.ngeom, "ncam": model.ncam}, "joint_ids": joint_ids, "actuator_ids": actuator_ids, "camera_ids": _id_map(model, mujoco.mjtObj.mjOBJ_CAMERA, model.ncam), "handoff_control": {"physics_hz": 200, "policy_hz": 50, "control_decimation": 4, "velocity_limit": list(self.contract.velocity_limit), "velocity_limit_mujoco_realization": DECLARED_ENDPOINT_VELOCITY_DISPLACEMENT_PROJECTION, "velocity_limit_mujoco_realization_semantics": "post-native-step endpoint qvel projection plus implicitfast displacement correction; not a native MuJoCo constraint or PhysX-equivalence claim", "arm_effort_limit_nm": list(self.contract.torque_limit[12:18]), "gripper_pd_effort": {"kp": list(self.contract.stiffness[18:]), "kd": list(self.contract.damping[18:]), "effort_limit_nm": list(self.contract.torque_limit[18:])}}, "camera_receipts": camera_receipts, "frame_mapping": frame_mapping}
        output_contract.write_text(json.dumps(contract, indent=2) + "\n")
        output_report.write_text(json.dumps(report, indent=2) + "\n")


__all__ = ["DepthADDV3MjcfBuilder"]
