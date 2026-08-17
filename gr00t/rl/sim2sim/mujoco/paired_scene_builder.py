"""Compose one paired-campaign scene without the E3 latch assumption."""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco

from gr00t.rl.sim2sim.mujoco.scene_builder import _format, _numbers


class PairedSceneBuilder:
    def __init__(self, robot_xml: Path, door_xml: Path):
        self.robot_xml = robot_xml.resolve(strict=True)
        self.door_xml = door_xml.resolve(strict=True)

    def write(self, output_xml: Path, output_report: Path) -> None:
        output_xml = output_xml.resolve()
        output_xml.parent.mkdir(parents=True, exist_ok=True)
        robot = ET.parse(self.robot_xml).getroot()
        door = ET.parse(self.door_xml).getroot()
        robot.set("model", "doordog_paired_campaign_scene")

        compiler = robot.find("compiler")
        if compiler is None:
            raise ValueError("robot MJCF lacks compiler")
        mesh_dir = (self.robot_xml.parent / compiler.attrib["meshdir"]).resolve(strict=True)
        compiler.set("meshdir", os.path.relpath(mesh_dir, output_xml.parent))

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
        for actuator in list(door_actuator):
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
        combined_ctrl = [0.0] * 20 + _numbers(door_home.get("ctrl"))
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
        actual = (model.nq, model.nv, model.nu)
        if actual != (29, 28, 22):
            raise ValueError(f"paired model dimensions {actual} != (29, 28, 22)")
        report = {
            "schema": "doordog.sim2sim.paired_scene_build_report.v1",
            "result_classification": "VALID_COMPARABLE",
            "mujoco_version": mujoco.__version__,
            "scene_xml": str(output_xml),
            "source_identity": {"robot": str(self.robot_xml), "door": str(self.door_xml)},
            "door_pose": {
                "position_m": [1.0, 0.0, 0.0],
                "orientation_wxyz": [1.0, 0.0, 0.0, 0.0]
            },
            "compiled": {
                "nq": model.nq,
                "nv": model.nv,
                "nu": model.nu,
                "neq": model.neq,
                "nbody": model.nbody,
                "ngeom": model.ngeom,
                "ncam": model.ncam
            },
            "latch_realization": "NO_LATCH" if model.neq == 0 else "EQUALITY_PRESENT"
        }
        output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
