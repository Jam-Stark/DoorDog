#!/usr/bin/env python3
"""Add the frozen v28 simulation camera envelopes to the Vpiper URDF.

The source rig is a design envelope, not wrist-bracket CAD: G0-C1' remains
NOT_RUN until the hardware bracket exists.  The script intentionally accepts
one chosen canonical rig only and fails when its exact asset topology changes.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


TOWER_HOUSING_MASS_KG = 0.075
TOWER_SUPPORT_REFERENCE_MASS_KG = 0.075
TOWER_SUPPORT_REFERENCE_LENGTH_M = 0.11470001524266443
BASE_TOPOLOGIES = {(30, 29), (27, 26)}
HOUSING_SIZE_KEY = "housing_size_M_m"
RIG_DEFAULT = Path("scriptsFORhuman/v28/camera/U3_F39_H140.json")
URDF_DEFAULT = Path("gr00t/rl/data/robots/a2_piper_vpiper_final_20260906/a2_piper.urdf")


def fmt(values: list[float]) -> str:
    return " ".join(f"{value:.15g}" for value in values)


def rpy_from_rotation(rotation: list[list[float]]) -> list[float]:
    pitch = math.asin(-rotation[2][0])
    return [
        math.atan2(rotation[2][1], rotation[2][2]),
        pitch,
        math.atan2(rotation[1][0], rotation[0][0]),
    ]


def add_box(parent: ET.Element, *, name: str, transform: list[list[float]], size: list[float], visual: bool) -> None:
    element = ET.SubElement(parent, "visual" if visual else "collision", {"name": name})
    ET.SubElement(element, "origin", {"xyz": fmt([transform[0][3], transform[1][3], transform[2][3]]), "rpy": fmt(rpy_from_rotation(transform))})
    geometry = ET.SubElement(element, "geometry")
    ET.SubElement(geometry, "box", {"size": fmt(size)})
    if visual:
        material = ET.SubElement(element, "material", {"name": "v28_camera_envelope"})
        ET.SubElement(material, "color", {"rgba": "0.22 0.55 0.78 1"})


def add_geometry(parent: ET.Element, *, name: str, transform: list[list[float]], size: list[float]) -> None:
    add_box(parent, name=f"{name}_visual", transform=transform, size=size, visual=True)
    add_box(parent, name=f"{name}_collision", transform=transform, size=size, visual=False)


def add_tower_inertial(tower: ET.Element, parts: list[tuple[list[list[float]], list[float], float]]) -> None:
    if len(parts) != 2:
        raise ValueError("tower inertia requires exactly support and housing proxy boxes")
    masses = [mass for _, _, mass in parts]
    total_mass = sum(masses)
    centres = [[transform[0][3], transform[1][3], transform[2][3]] for transform, _, _ in parts]
    com = [sum(mass * centre[i] for mass, centre in zip(masses, centres)) / total_mass for i in range(3)]
    inertia = [[0.0] * 3 for _ in range(3)]
    for mass, (transform, size, _), centre in zip(masses, parts, centres):
        local = [
            mass * (size[1] ** 2 + size[2] ** 2) / 12.0,
            mass * (size[0] ** 2 + size[2] ** 2) / 12.0,
            mass * (size[0] ** 2 + size[1] ** 2) / 12.0,
        ]
        rotation = [row[:3] for row in transform[:3]]
        for i in range(3):
            for j in range(3):
                inertia[i][j] += sum(rotation[i][k] * local[k] * rotation[j][k] for k in range(3))
        displacement = [centre[i] - com[i] for i in range(3)]
        squared = sum(value * value for value in displacement)
        for i in range(3):
            for j in range(3):
                inertia[i][j] += mass * ((squared if i == j else 0.0) - displacement[i] * displacement[j])
    inertial = ET.SubElement(tower, "inertial")
    ET.SubElement(inertial, "origin", {"xyz": fmt(com), "rpy": "0 0 0"})
    ET.SubElement(inertial, "mass", {"value": f"{total_mass:.15g}"})
    ET.SubElement(inertial, "inertia", {
        "ixx": f"{inertia[0][0]:.15g}", "ixy": f"{inertia[0][1]:.15g}", "ixz": f"{inertia[0][2]:.15g}",
        "iyy": f"{inertia[1][1]:.15g}", "iyz": f"{inertia[1][2]:.15g}", "izz": f"{inertia[2][2]:.15g}",
    })


def find_link(root: ET.Element, name: str) -> ET.Element:
    link = root.find(f"link[@name='{name}']")
    if link is None:
        raise ValueError(f"missing link: {name}")
    return link


def remove_prior_generated_envelope(root: ET.Element) -> None:
    links = root.findall("link")
    joints = root.findall("joint")
    if (len(links), len(joints)) in BASE_TOPOLOGIES:
        return
    if (len(links) - 1, len(joints) - 1) not in BASE_TOPOLOGIES:
        raise ValueError("URDF link/joint topology is neither source nor this builder's prior output")
    tower = find_link(root, "wrist_camera_tower")
    tower_joint = root.find("joint[@name='arm_body6_to_wrist_camera_tower']")
    if tower_joint is None:
        raise ValueError("prior tower link lacks its fixed joint")
    root.remove(tower)
    root.remove(tower_joint)
    trunk = find_link(root, "trunk")
    generated = [element for element in list(trunk) if element.attrib.get("name", "").startswith("v28_")]
    if len(generated) not in (20, 22):
        raise ValueError("prior trunk camera envelope is incomplete")
    for element in generated:
        trunk.remove(element)


def insert_before_inertial(link: ET.Element, element: ET.Element) -> None:
    inertial = link.find("inertial")
    if inertial is None:
        raise ValueError(f"missing inertial: {link.attrib['name']}")
    link.insert(list(link).index(inertial), element)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rig", type=Path, default=RIG_DEFAULT)
    parser.add_argument("--urdf", type=Path, default=URDF_DEFAULT)
    parser.add_argument("--receipt", type=Path,
                        help="write D-35 tower mass/inertia inputs for the merged-asset receipt")
    parser.add_argument("--independent-urdf-copy", type=Path,
                        help="retain the new-geometry independent input used for D-34 equivalence")
    args = parser.parse_args()
    rig = json.loads(args.rig.read_text())
    brackets = rig["brackets"]
    housing_size = rig[HOUSING_SIZE_KEY]
    base_boxes = [box for box in brackets if box["parent"] == "trunk"]
    wrist_boxes = [box for box in brackets if box["parent"] == "arm_body6_to_gripper"]
    central_housings = rig.get("trunk_envelope_housings")
    if len(base_boxes) != 8 or {box["name"] for box in base_boxes} != {
        "base_foot", "base_crossbar", "base_left_crossbar_rail", "base_left_post", "base_left_saddle",
        "base_right_crossbar_rail", "base_right_post", "base_right_saddle",
    }:
        raise ValueError("canonical rig must supply exactly eight trunk bracket boxes")
    if len(wrist_boxes) != 1 or wrist_boxes[0]["name"] != "wrist_camera_support":
        raise ValueError("canonical rig must supply exactly one wrist_camera_support box")
    if (not isinstance(central_housings, list) or len(central_housings) != 1
            or central_housings[0].get("name") != "base_center_housing"
            or central_housings[0].get("parent") != "trunk"
            or central_housings[0].get("size_m") != housing_size):
        raise ValueError("canonical rig must supply exactly one D-06 central housing envelope")
    cameras = {camera["name"]: camera for camera in rig["cameras"]}
    if set(cameras) != {"base_left", "base_right", "wrist"}:
        raise ValueError("canonical rig camera names changed")
    root = ET.parse(args.urdf).getroot()
    remove_prior_generated_envelope(root)
    trunk = find_link(root, "trunk")
    for box in base_boxes:
        holder = ET.Element("holder")
        add_geometry(holder, name=f"v28_{box['name']}", transform=box["T_parent_item"], size=box["size_m"])
        for element in list(holder):
            insert_before_inertial(trunk, element)
    for camera_name in ("base_left", "base_right"):
        holder = ET.Element("holder")
        add_geometry(holder, name=f"v28_{camera_name}_housing", transform=cameras[camera_name]["T_parent_M"], size=housing_size)
        for element in list(holder):
            insert_before_inertial(trunk, element)
    holder = ET.Element("holder")
    central = central_housings[0]
    add_geometry(holder, name=f"v28_{central['name']}", transform=central["T_parent_item"], size=housing_size)
    for element in list(holder):
        insert_before_inertial(trunk, element)
    support = wrist_boxes[0]
    wrist_housing = cameras["wrist"]
    support_mass = TOWER_SUPPORT_REFERENCE_MASS_KG * support["size_m"][2] / TOWER_SUPPORT_REFERENCE_LENGTH_M
    tower_mass = support_mass + TOWER_HOUSING_MASS_KG
    tower = ET.Element("link", {"name": "wrist_camera_tower"})
    tower.append(ET.Comment("SIMULATION_ENVELOPE: wrist bracket CAD is not designed; G0-C1' is NOT_RUN."))
    tower.append(ET.Comment(
        "MASS_ESTIMATE: support=0.075 kg*(support_length/0.11470001524266443 m); "
        "D435i housing=0.075 kg; no measured CAD mass."
    ))
    add_geometry(tower, name="v28_wrist_camera_support", transform=support["T_parent_item"], size=support["size_m"])
    add_geometry(tower, name="v28_wrist_housing", transform=wrist_housing["T_parent_M"], size=housing_size)
    add_tower_inertial(tower, [
        (support["T_parent_item"], support["size_m"], support_mass),
        (wrist_housing["T_parent_M"], housing_size, TOWER_HOUSING_MASS_KG),
    ])
    root.append(tower)
    joint = ET.Element("joint", {"name": "arm_body6_to_wrist_camera_tower", "type": "fixed"})
    ET.SubElement(joint, "parent", {"link": "arm_body6_to_gripper"})
    ET.SubElement(joint, "child", {"link": "wrist_camera_tower"})
    ET.SubElement(joint, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
    root.append(joint)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(args.urdf, encoding="utf-8", xml_declaration=True)
    if args.independent_urdf_copy is not None:
        args.independent_urdf_copy.parent.mkdir(parents=True, exist_ok=True)
        independent_tree = ET.parse(args.urdf)
        for mesh in independent_tree.findall(".//mesh"):
            mesh.set("filename", (Path("../..") / mesh.attrib["filename"]).as_posix())
        ET.indent(independent_tree.getroot(), space="  ")
        independent_tree.write(args.independent_urdf_copy, encoding="utf-8", xml_declaration=True)
    if args.receipt is not None:
        inertial = tower.find("inertial")
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps({
            "status": "D035_TOWER_ESTIMATED_GEOMETRY_READY",
            "rig": str(args.rig.resolve()),
            "urdf_independent_input": str(args.urdf.resolve()),
            "persistent_independent_input": (
                str(args.independent_urdf_copy.resolve())
                if args.independent_urdf_copy is not None else None
            ),
            "tower_geometry": {
                "support_transform": support["T_parent_item"],
                "support_size_m": support["size_m"],
                "housing_transform": wrist_housing["T_parent_M"],
                "housing_size_m": housing_size,
            },
            "mass_estimate": {
                "support_reference_mass_kg": TOWER_SUPPORT_REFERENCE_MASS_KG,
                "support_reference_length_m": TOWER_SUPPORT_REFERENCE_LENGTH_M,
                "support_formula": "0.075 kg * support_length_m / 0.11470001524266443 m",
                "support_mass_kg": support_mass,
                "housing_mass_kg": TOWER_HOUSING_MASS_KG,
                "tower_mass_kg": tower_mass,
                "status": "ESTIMATED_SIMULATION_GEOMETRY_NOT_HARDWARE_CAD_OR_MEASUREMENT",
            },
            "tower_inertial": {
                "origin_m": [float(value) for value in inertial.find("origin").attrib["xyz"].split()],
                "tensor_kgm2": {key: float(value) for key, value in inertial.find("inertia").attrib.items()},
            },
        }, indent=2) + "\n")
    print(
        f"wrote {args.urdf}: trunk_boxes=8 trunk_housings=3 tower_boxes=2 "
        f"support_mass_kg={support_mass:.15g} tower_mass_kg={tower_mass:.15g}"
    )


if __name__ == "__main__":
    main()
