"""Compose the proven robot and door XMLs into one independent MuJoCo scene."""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco


def _numbers(text: str | None) -> list[float]:
    if text is None:
        return []
    return [float(value) for value in text.split()]


def _format(values: list[float]) -> str:
    return " ".join(f"{value:.12g}" for value in values)


class ShadowSceneBuilder:
    def __init__(self, robot_xml: Path, door_xml: Path):
        self.robot_xml = robot_xml.resolve(strict=True)
        self.door_xml = door_xml.resolve(strict=True)

    def write(self, output_xml: Path, output_report: Path) -> None:
        output_xml = output_xml.resolve()
        output_xml.parent.mkdir(parents=True, exist_ok=True)
        output_report.parent.mkdir(parents=True, exist_ok=True)
        robot = ET.parse(self.robot_xml).getroot()
        door = ET.parse(self.door_xml).getroot()
        robot.set("model", "doordog_shadow_scene")

        compiler = robot.find("compiler")
        assert compiler is not None
        robot_mesh_dir = (self.robot_xml.parent / compiler.attrib["meshdir"]).resolve(strict=True)
        compiler.set("meshdir", os.path.relpath(robot_mesh_dir, output_xml.parent))

        robot_world = robot.find("worldbody")
        door_world = door.find("worldbody")
        assert robot_world is not None and door_world is not None
        door_root = door_world.find("body[@name='door_root']")
        assert door_root is not None
        door_world.remove(door_root)
        door_root.set("pos", "1.0 0 0")
        robot_world.append(door_root)

        for section_name in ("default", "contact", "equality"):
            section = door.find(section_name)
            if section is not None:
                door.remove(section)
                robot.append(section)

        robot_actuator = robot.find("actuator")
        door_actuator = door.find("actuator")
        assert robot_actuator is not None and door_actuator is not None
        for actuator in list(door_actuator):
            door_actuator.remove(actuator)
            robot_actuator.append(actuator)

        robot_keyframe = robot.find("keyframe")
        door_keyframe = door.find("keyframe")
        assert robot_keyframe is not None and door_keyframe is not None
        robot_home = robot_keyframe.find("key[@name='home']")
        door_home = door_keyframe.find("key[@name='door_closed']")
        assert robot_home is not None and door_home is not None
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
        expected = (29, 28, 22, 1)
        actual = (model.nq, model.nv, model.nu, model.neq)
        if actual != expected:
            raise ValueError(f"composed model dimensions {actual} != {expected}")
        report = {
            "schema": "doordog.sim2sim.shadow_scene_build_report.v1",
            "evidence_level": "E3",
            "result_classification": "VALID_COMPARABLE",
            "mujoco_version": mujoco.__version__,
            "scene_xml": str(output_xml),
            "source_identity": {
                "robot": str(self.robot_xml),
                "door": str(self.door_xml),
            },
            "door_pose": {"position_m": [1.0, 0.0, 0.0], "orientation_wxyz": [1.0, 0.0, 0.0, 0.0]},
            "compiled": {
                "nq": model.nq,
                "nv": model.nv,
                "nu": model.nu,
                "neq": model.neq,
                "nbody": model.nbody,
                "ngeom": model.ngeom,
                "ncam": model.ncam,
            },
            "layouts": {
                "robot_qpos": [0, 27],
                "door_qpos": [27, 29],
                "robot_qvel": [0, 26],
                "door_qvel": [26, 28],
                "robot_actuator": [0, 20],
                "door_actuator": [20, 22],
            },
        }
        output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

