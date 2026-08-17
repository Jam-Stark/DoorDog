"""Composed paired scene with resolved armature and door-first actuator order."""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping

import mujoco

from gr00t.rl.sim2sim.mujoco.scene_builder import _format, _numbers


FOOT_GEOM_NAMES = (
    "FL_foot_collision",
    "RL_foot_collision",
    "FR_foot_collision",
    "RR_foot_collision",
)


class PairedSceneBuilderV2:
    def __init__(
        self,
        robot_xml: Path,
        door_xml: Path,
        *,
        armature_by_joint: Mapping[str, float],
    ):
        self.robot_xml = robot_xml.resolve(strict=True)
        self.door_xml = door_xml.resolve(strict=True)
        self.armature_by_joint = dict(armature_by_joint)

    def write(self, output_xml: Path, output_report: Path) -> None:
        output_xml = output_xml.resolve()
        output_xml.parent.mkdir(parents=True, exist_ok=True)
        robot = ET.parse(self.robot_xml).getroot()
        door = ET.parse(self.door_xml).getroot()
        robot.set("model", "doordog_paired_campaign_scene_v2")

        compiler = robot.find("compiler")
        if compiler is None:
            raise ValueError("robot MJCF lacks compiler")
        mesh_dir = (self.robot_xml.parent / compiler.attrib["meshdir"]).resolve(strict=True)
        compiler.set("meshdir", os.path.relpath(mesh_dir, output_xml.parent))

        asset = robot.find("asset")
        if asset is None:
            raise ValueError("robot MJCF lacks asset section")
        ET.SubElement(
            asset,
            "texture",
            {
                "name": "sim2sim_skybox",
                "type": "skybox",
                "builtin": "gradient",
                "rgb1": "0.18 0.24 0.32",
                "rgb2": "0.02 0.025 0.035",
                "width": "512",
                "height": "3072",
            },
        )
        ET.SubElement(
            asset,
            "texture",
            {
                "name": "sim2sim_floor_checker",
                "type": "2d",
                "builtin": "checker",
                "rgb1": "0.24 0.25 0.27",
                "rgb2": "0.34 0.35 0.37",
                "width": "512",
                "height": "512",
            },
        )
        ET.SubElement(
            asset,
            "material",
            {
                "name": "sim2sim_floor_material",
                "texture": "sim2sim_floor_checker",
                "texrepeat": "8 8",
                "reflectance": "0.05",
            },
        )
        floor = robot.find(".//geom[@name='floor']")
        if floor is None:
            raise ValueError("robot MJCF lacks floor geom")
        floor.set("material", "sim2sim_floor_material")

        for joint_name, armature in self.armature_by_joint.items():
            joint = robot.find(f".//joint[@name='{joint_name}']")
            if joint is None:
                raise ValueError(f"robot MJCF lacks armature joint {joint_name}")
            joint.set("armature", f"{float(armature):.12g}")

        for calf_name, foot_name in zip(
            ("FL_calf", "RL_calf", "FR_calf", "RR_calf"), FOOT_GEOM_NAMES, strict=True
        ):
            calf = robot.find(f".//body[@name='{calf_name}']")
            if calf is None:
                raise ValueError(f"robot MJCF lacks {calf_name}")
            foot = calf.find("geom[@size='0.032']")
            if foot is None:
                raise ValueError(f"robot MJCF lacks the {calf_name} foot sphere")
            foot.set("name", foot_name)

        robot_world = robot.find("worldbody")
        door_world = door.find("worldbody")
        if robot_world is None or door_world is None:
            raise ValueError("paired inputs lack worldbody")
        door_root = door_world.find("body[@name='door_root']")
        if door_root is None:
            raise ValueError("door MJCF lacks door_root")
        door_root.set("pos", "1.0 0 0")
        robot_world.append(door_root)

        for section_name in ("default", "contact", "equality"):
            section = door.find(section_name)
            if section is not None:
                robot.append(section)

        robot_actuator = robot.find("actuator")
        door_actuator = door.find("actuator")
        if robot_actuator is None or door_actuator is None:
            raise ValueError("paired inputs lack actuators")
        robot_elements = list(robot_actuator)
        robot_actuator.clear()
        for actuator in list(door_actuator):
            robot_actuator.append(actuator)
        for actuator in robot_elements:
            robot_actuator.append(actuator)

        robot_keyframe = robot.find("keyframe")
        door_keyframe = door.find("keyframe")
        if robot_keyframe is None or door_keyframe is None:
            raise ValueError("paired inputs lack keyframes")
        robot_home = robot_keyframe.find("key[@name='home']")
        door_home = door_keyframe.find("key[@name='door_closed']")
        if robot_home is None or door_home is None:
            raise ValueError("paired inputs lack named home keyframes")
        combined_qpos = _numbers(robot_home.get("qpos")) + _numbers(door_home.get("qpos"))
        combined_ctrl = _numbers(door_home.get("ctrl")) + [0.0] * 20
        robot.remove(robot_keyframe)
        combined_keyframe = ET.SubElement(robot, "keyframe")
        ET.SubElement(
            combined_keyframe,
            "key",
            {"name": "scene_home", "qpos": _format(combined_qpos), "ctrl": _format(combined_ctrl)},
        )

        ET.indent(robot, space="  ")
        output_xml.write_text(ET.tostring(robot, encoding="unicode") + "\n", encoding="utf-8")
        model = mujoco.MjModel.from_xml_path(str(output_xml))
        if (model.nq, model.nv, model.nu) != (29, 28, 22):
            raise ValueError(f"paired model dimensions {(model.nq, model.nv, model.nu)} != (29, 28, 22)")
        actuator_order = [
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index)
            for index in range(model.nu)
        ]
        if actuator_order[:2] != ["door_hinge_capped_position", "handle_capped_position"]:
            raise ValueError(f"door actuators are not first: {actuator_order}")
        floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
        contact_surface = {
            name: {
                "geom_id": (geom_id := mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)),
                "floor_pair_enabled_by_masks": bool(
                    (model.geom_contype[floor_id] & model.geom_conaffinity[geom_id])
                    or (model.geom_conaffinity[floor_id] & model.geom_contype[geom_id])
                ),
            }
            for name in FOOT_GEOM_NAMES
        }
        report = {
            "schema": "doordog.sim2sim.paired_scene_build_report.v2",
            "result_classification": "VALID_COMPARABLE",
            "mujoco_version": mujoco.__version__,
            "scene_xml": str(output_xml),
            "source_identity": {"robot": str(self.robot_xml), "door": str(self.door_xml)},
            "compiled": {
                "nq": model.nq,
                "nv": model.nv,
                "nu": model.nu,
                "neq": model.neq,
                "nbody": model.nbody,
                "ngeom": model.ngeom,
                "ncam": model.ncam,
            },
            "resolved_robot_dynamics": {
                "armature_by_joint": self.armature_by_joint,
                "source": "READY r2 config_snapshot.yaml robot.dof_armature_list by robot.dof_names",
            },
            "actuator_order": actuator_order,
            "actuator_order_contract": "DOOR_TWO_POSITION_ACTUATORS_FIRST; ROBOT_MOTORS_NAME_RESOLVED",
            "foot_floor_contact_surface": {
                "floor_geom_id": floor_id,
                "feet": contact_surface,
            },
            "visual_background": {
                "skybox": "sim2sim_skybox gradient",
                "floor_material": "sim2sim_floor_material checker",
                "purpose": "native RGB must remain informative when a moving robot camera sees only background",
                "physics_effect": "NONE; geom contact attributes are unchanged",
            },
            "latch_realization": "NO_LATCH" if model.neq == 0 else "EQUALITY_PRESENT",
        }
        output_report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
