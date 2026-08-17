"""Deterministic XML builder for one DoorInstanceSpec."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .spec import DoorInstanceSpec


def _s(values: list[float] | tuple[float, ...]) -> str:
    return " ".join(f"{float(value):.12g}" for value in values)


def _add_geom(parent: ET.Element, **attrs: Any) -> ET.Element:
    return ET.SubElement(parent, "geom", {key: str(value) for key, value in attrs.items()})


class MjcfDoorBuilder:
    """Build the inspectable XML realization and its semantic receipt."""

    def __init__(self, spec: DoorInstanceSpec):
        spec.validate()
        self.spec = spec

    def build(self) -> tuple[str, dict[str, Any]]:
        data = self.spec.payload
        geometry = data["geometry"]
        kinematics = data["kinematics"]
        dynamics = data["dynamics"]
        hinge = dynamics["hinge"]
        handle = dynamics["handle"]
        contact = data["contact"]
        width = float(geometry["panel_width_m"])
        height = float(geometry["panel_height_m"])
        thickness = float(geometry["panel_thickness_m"])
        frame_width = float(geometry["frame_width_m"])
        side = 1.0 if kinematics["hinge_side"] == "left" else -1.0
        handle_y = side * (width / 2.0 - float(geometry["handle_edge_offset_m"]))
        handle_z = float(geometry["handle_height_m"])
        hinge_ctrl_range = [
            min(float(kinematics["hinge_limits_rad"][0]), float(hinge["equilibrium_rad"])),
            max(float(kinematics["hinge_limits_rad"][1]), float(hinge["equilibrium_rad"])),
        ]
        handle_ctrl_range = [
            min(float(kinematics["handle_limits_rad"][0]), float(handle["equilibrium_rad"])),
            max(float(kinematics["handle_limits_rad"][1]), float(handle["equilibrium_rad"])),
        ]

        root = ET.Element("mujoco", {"model": "doordog_materialized_door"})
        ET.SubElement(root, "compiler", {"angle": "radian", "coordinate": "local"})
        ET.SubElement(root, "option", {"timestep": "0.005", "gravity": "0 0 -9.81"})
        default = ET.SubElement(root, "default")
        ET.SubElement(default, "geom", {
            "friction": _s(contact["geom_friction"]),
            "condim": str(contact["condim"]),
            "density": "0",
        })
        world = ET.SubElement(root, "worldbody")
        door_root = ET.SubElement(world, "body", {"name": "door_root"})
        _add_geom(
            door_root,
            name="door_frame_left",
            type="box",
            pos=_s([0, width / 2.0 + frame_width / 2.0, height / 2.0]),
            size=_s([thickness, frame_width / 2.0, height / 2.0 + frame_width]),
        )
        _add_geom(
            door_root,
            name="door_frame_right",
            type="box",
            pos=_s([0, -width / 2.0 - frame_width / 2.0, height / 2.0]),
            size=_s([thickness, frame_width / 2.0, height / 2.0 + frame_width]),
        )
        _add_geom(
            door_root,
            name="door_frame_top",
            type="box",
            pos=_s([0, 0, height + frame_width / 2.0]),
            size=_s([thickness, width / 2.0, frame_width / 2.0]),
        )
        hinge_y = -side * width / 2.0
        panel = ET.SubElement(door_root, "body", {
            "name": "door_panel",
            "pos": _s([0, hinge_y, 0]),
        })
        ET.SubElement(panel, "joint", {
            "name": "door_hinge",
            "type": "hinge",
            "axis": "0 0 1",
            "range": _s(kinematics["hinge_limits_rad"]),
            "damping": f"{float(hinge['viscous_friction_coefficient']):.12g}",
            "frictionloss": f"{float(hinge['dynamic_friction_effort']):.12g}",
            "limited": "true",
            "solreflimit": "-10000 -100",
        })
        ET.SubElement(panel, "inertial", {
            "pos": _s([0, side * width / 2.0, height / 2.0]),
            "mass": f"{float(dynamics['panel_mass_kg']):.12g}",
            "diaginertia": _s(dynamics["panel_diagonal_inertia_kgm2"]),
        })
        _add_geom(
            panel,
            name="door_panel_collision",
            type="box",
            pos=_s([0, side * width / 2.0, height / 2.0]),
            size=_s([thickness / 2.0, width / 2.0, height / 2.0]),
            mass="0",
            rgba="0.45 0.25 0.12 1",
        )
        handle_body = ET.SubElement(panel, "body", {
            "name": "door_handle",
            "pos": _s([0, handle_y - hinge_y, handle_z]),
        })
        ET.SubElement(handle_body, "joint", {
            "name": "handle_hinge",
            "type": "hinge",
            "axis": "1 0 0",
            "range": _s(kinematics["handle_limits_rad"]),
            "damping": f"{float(handle['viscous_friction_coefficient']):.12g}",
            "frictionloss": f"{float(handle['dynamic_friction_effort']):.12g}",
            "limited": "true",
            "solreflimit": "-10000 -100",
        })
        _add_geom(
            handle_body,
            name="handle_axle",
            type="cylinder",
            pos="0 0 0",
            quat="0.707106781187 0 0.707106781187 0",
            size=_s([geometry["handle_radius_m"], geometry["handle_axle_length_m"] / 2.0]),
            mass=str(dynamics["handle_mass_kg"]),
            rgba="0.75 0.75 0.78 1",
        )
        _add_geom(
            handle_body,
            name="handle_lever",
            type="capsule",
            fromto=_s([0, 0, 0, 0, side * geometry["handle_lever_length_m"], 0]),
            size=f"{float(geometry['handle_radius_m']):.12g}",
            mass="0.05",
            rgba="0.8 0.8 0.82 1",
        )
        ET.SubElement(handle_body, "site", {
            "name": "door_grasp_target",
            "pos": _s([0, side * geometry["handle_lever_length_m"], 0]),
            "size": "0.012",
            "rgba": "1 1 0 1",
        })
        ET.SubElement(handle_body, "site", {
            "name": "door_handle_center",
            "pos": "0 0 0",
            "size": "0.01",
        })
        ET.SubElement(panel, "site", {
            "name": "door_pregrasp_target",
            "pos": _s([-0.16, handle_y - hinge_y, handle_z]),
            "size": "0.012",
        })
        ET.SubElement(door_root, "site", {
            "name": "door_hinge_axis",
            "pos": _s([0, hinge_y, height / 2.0]),
            "size": _s([0.01, height / 2.0]),
            "type": "cylinder",
        })
        for site_name in ("door_passage_center", "door_goal"):
            site = data["named_sites"][site_name]
            ET.SubElement(door_root, "site", {
                "name": site_name,
                "pos": _s(site["position_m"]),
                "size": "0.015",
            })

        contact_pairs = ET.SubElement(root, "contact")
        ET.SubElement(contact_pairs, "exclude", {
            "name": "exclude_panel_handle_self_collision",
            "body1": "door_panel",
            "body2": "door_handle",
        })
        ET.SubElement(contact_pairs, "exclude", {
            "name": "exclude_frame_panel_self_collision",
            "body1": "door_root",
            "body2": "door_panel",
        })
        ET.SubElement(contact_pairs, "exclude", {
            "name": "exclude_frame_handle_self_collision",
            "body1": "door_root",
            "body2": "door_handle",
        })

        equality = ET.SubElement(root, "equality")
        latch_mode = kinematics["latch_mode"]
        if latch_mode == "constraint_gate":
            ET.SubElement(equality, "joint", {
                "name": "door_constraint_gate",
                "joint1": "door_hinge",
                "polycoef": "0 0 0 0 0",
                "active": "true",
            })
        elif latch_mode == "physical_collision":
            latch = ET.SubElement(panel, "body", {
                "name": "latch_link",
                "pos": _s([0, side * (width - 0.01), handle_z]),
            })
            ET.SubElement(latch, "joint", {
                "name": "latch_slide",
                "type": "slide",
                "axis": _s([0, side, 0]),
                "range": "-0.03 0",
                "limited": "true",
            })
            _add_geom(latch, name="latch_collision", type="box", size="0.02 0.025 0.012", mass="0.05")
            ET.SubElement(equality, "joint", {
                "name": "handle_latch_mimic",
                "joint1": "latch_slide",
                "joint2": "handle_hinge",
                "polycoef": f"0 {float(kinematics['latch_travel_per_handle_rad_m']):.15g} 0 0 0",
            })

        actuator = ET.SubElement(root, "actuator")
        ET.SubElement(actuator, "position", {
            "name": "door_hinge_capped_position",
            "joint": "door_hinge",
            "kp": f"{float(hinge['stiffness_nm_per_rad']):.12g}",
            "kv": f"{float(hinge['damping_nms_per_rad']):.12g}",
            "ctrlrange": _s(hinge_ctrl_range),
            "ctrllimited": "true",
            "forcerange": _s([-float(hinge["effort_cap_nm"]), float(hinge["effort_cap_nm"])]),
            "forcelimited": "true",
        })

        keyframe = ET.SubElement(root, "keyframe")
        ET.SubElement(keyframe, "key", {
            "name": "door_closed",
            "qpos": "0 0",
            "ctrl": _s([hinge["equilibrium_rad"], handle["equilibrium_rad"]]),
        })
        ET.SubElement(actuator, "position", {
            "name": "handle_capped_position",
            "joint": "handle_hinge",
            "kp": f"{float(handle['stiffness_nm_per_rad']):.12g}",
            "kv": f"{float(handle['damping_nms_per_rad']):.12g}",
            "ctrlrange": _s(handle_ctrl_range),
            "ctrllimited": "true",
            "forcerange": _s([-float(handle["effort_cap_nm"]), float(handle["effort_cap_nm"])]),
            "forcelimited": "true",
        })

        ET.indent(root, space="  ")
        xml = ET.tostring(root, encoding="unicode") + "\n"
        names = {
            "bodies": ["door_root", "door_panel", "door_handle"] + (["latch_link"] if latch_mode == "physical_collision" else []),
            "joints": ["door_hinge", "handle_hinge"] + (["latch_slide"] if latch_mode == "physical_collision" else []),
            "sites": [
                "door_grasp_target",
                "door_pregrasp_target",
                "door_hinge_axis",
                "door_handle_center",
                "door_passage_center",
                "door_goal",
            ],
            "actuators": ["door_hinge_capped_position", "handle_capped_position"],
        }
        report = {
            "schema_version": "doordog.mjcf_door_build_report.v1",
            "result_classification": "VALID_WITH_WARNINGS" if self.spec.friction_classification == "FRICTION_SEMANTIC_GAP" else "VALID_COMPARABLE",
            "instance_identity": data["identity"],
            "latch_mode": latch_mode,
            "door_resistance_mode": "capped_position_actuator",
            "self_collision_exclusions": [
                "door_panel<->door_handle",
                "door_root<->door_panel",
                "door_root<->door_handle",
            ],
            "names": names,
            "hinge_limits_rad": kinematics["hinge_limits_rad"],
            "handle_limits_rad": kinematics["handle_limits_rad"],
            "equilibrium_ctrl_rad": [hinge["equilibrium_rad"], handle["equilibrium_rad"]],
            "panel_mass_kg": dynamics["panel_mass_kg"],
            "panel_diagonal_inertia_kgm2": dynamics["panel_diagonal_inertia_kgm2"],
            "friction_mapping": {
                "isaac_static_effort": hinge["static_friction_effort"],
                "isaac_dynamic_effort": hinge["dynamic_friction_effort"],
                "isaac_viscous_coefficient": hinge["viscous_friction_coefficient"],
                "mujoco_frictionloss": hinge["dynamic_friction_effort"],
                "mujoco_joint_damping_from_viscous": hinge["viscous_friction_coefficient"],
                "classification": self.spec.friction_classification,
                "authority": "MODELED_FROM_PARAMS;SOLVER_APPLIED_GENERALIZED_TORQUE_NOT_CLAIMED",
            },
            "mechanics_three_face_receipt": self.spec.mechanics_receipt(),
        }
        return xml, report

    def write(self, output_xml: str | Path, output_report: str | Path) -> None:
        xml, report = self.build()
        Path(output_xml).write_text(xml, encoding="utf-8")
        Path(output_report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
