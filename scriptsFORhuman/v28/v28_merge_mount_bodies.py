"""Prepare a compound-trunk candidate for the three rigid Vpiper mount parts.

No collision shape is removed. Fixed-part poses and the complete mass tensor
are transferred to trunk. Applying this candidate changes the G0 body/inertia
contract and requires Owner approval.
"""
from __future__ import annotations

import argparse
import copy
import json
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

PARTS = ("vpiper_main", "vpiper_support", "metal_plate_5mm")


def precise(value):
    return np.format_float_positional(value, precision=20, unique=False, trim="-")


def transform(origin):
    matrix = np.eye(4)
    if origin is not None:
        matrix[:3,3] = np.fromstring(origin.get("xyz", "0 0 0"),sep=" ")
        matrix[:3,:3] = Rotation.from_euler("xyz",np.fromstring(origin.get("rpy", "0 0 0"),sep=" ")).as_matrix()
    return matrix


def write_origin(element, matrix):
    origin = element.find("origin")
    if origin is None:
        origin = ET.SubElement(element,"origin")
    origin.set("xyz"," ".join(f"{value:.17g}" for value in matrix[:3,3]))
    origin.set("rpy"," ".join(f"{value:.17g}" for value in Rotation.from_matrix(matrix[:3,:3]).as_euler("xyz")))


def aggregate_robot_inertia(root):
    """Express all link inertials in trunk coordinates at zero joint position."""
    links = {link.attrib["name"]: link for link in root.findall("link")}
    joints = root.findall("joint")
    children = {joint.find("child").attrib["link"] for joint in joints}
    roots = set(links) - children
    if roots != {"trunk"}:
        raise ValueError(f"expected trunk as the unique tree root, got {sorted(roots)}")
    outgoing = {}
    for joint in joints:
        parent = joint.find("parent").attrib["link"]
        outgoing.setdefault(parent, []).append(joint)
    poses = {"trunk": np.eye(4)}
    pending = ["trunk"]
    while pending:
        parent = pending.pop()
        for joint in outgoing.get(parent, []):
            child = joint.find("child").attrib["link"]
            if child in poses:
                raise ValueError(f"link has more than one resolved pose: {child}")
            poses[child] = poses[parent] @ transform(joint.find("origin"))
            pending.append(child)
    if set(poses) != set(links):
        raise ValueError("joint graph does not reach every link from trunk")
    dtype = np.longdouble
    masses, centres, tensors = [], [], []
    for name, link in links.items():
        inertial = link.find("inertial")
        if inertial is None:
            raise ValueError(f"missing inertial: {name}")
        mass = dtype(inertial.find("mass").attrib["value"])
        inertial_pose = poses[name] @ transform(inertial.find("origin"))
        fields = inertial.find("inertia").attrib
        local = np.array([
            [float(fields["ixx"]), float(fields["ixy"]), float(fields["ixz"])],
            [float(fields["ixy"]), float(fields["iyy"]), float(fields["iyz"])],
            [float(fields["ixz"]), float(fields["iyz"]), float(fields["izz"])],
        ], dtype=dtype)
        masses.append(mass)
        centres.append(inertial_pose[:3, 3].astype(dtype))
        tensors.append(inertial_pose[:3, :3].astype(dtype) @ local @ inertial_pose[:3, :3].astype(dtype).T)
    total_mass = np.sum(np.asarray(masses, dtype=dtype), dtype=dtype)
    centre = np.sum(np.asarray([mass * point for mass, point in zip(masses, centres, strict=True)]), axis=0, dtype=dtype) / total_mass
    inertia = np.zeros((3, 3), dtype=dtype)
    for mass, point, tensor in zip(masses, centres, tensors, strict=True):
        offset = point - centre
        inertia += tensor + mass * (np.dot(offset, offset) * np.eye(3) - np.outer(offset, offset))
    return {"mass_kg": total_mass, "com_m": centre, "inertia_kgm2": inertia}


def serial_aggregate(aggregate):
    return {
        "mass_kg": float(aggregate["mass_kg"]),
        "com_m": [float(value) for value in aggregate["com_m"]],
        "inertia_kgm2": [[float(value) for value in row] for row in aggregate["inertia_kgm2"]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--persistent-independent-reference", type=Path)
    args = parser.parse_args()
    tree = ET.parse(args.input)
    root = tree.getroot()
    independent_aggregate = aggregate_robot_inertia(root)
    links = {link.attrib["name"]:link for link in root.findall("link")}
    trunk = links["trunk"]
    poses = {"trunk":np.eye(4)}
    joints = {joint.find("child").attrib["link"]:joint for joint in root.findall("joint")}
    for name in PARTS:
        joint = joints[name]
        if joint.attrib["type"] != "fixed":
            raise ValueError(f"{name} is not a fixed mount part")
        poses[name] = poses[joint.find("parent").attrib["link"]] @ transform(joint.find("origin"))
    dtype = np.longdouble
    masses, mass_texts, centres, inertias = [], [], [], []
    for name in ("trunk", *PARTS):
        inertial = links[name].find("inertial")
        mass = dtype(inertial.find("mass").attrib["value"])
        mass_texts.append(Decimal(inertial.find("mass").attrib["value"]))
        pose = poses[name] @ transform(inertial.find("origin"))
        fields = inertial.find("inertia").attrib
        inertia = np.array(
            [[dtype(fields[f"i{a}{b}" if a <= b else f"i{b}{a}"]) for b in "xyz"] for a in "xyz"],
            dtype=dtype,
        )
        masses.append(mass)
        centres.append(pose[:3,3].astype(dtype))
        rotation = pose[:3,:3].astype(dtype)
        inertias.append(rotation @ inertia @ rotation.T)
    mass = np.sum(np.asarray(masses, dtype=dtype), dtype=dtype)
    exact_mass_text = str(sum(mass_texts))
    centre = np.sum(np.asarray([m * p for m, p in zip(masses, centres, strict=True)]), axis=0, dtype=dtype) / mass
    inertia = np.zeros((3,3), dtype=dtype)
    for m,p,tensor in zip(masses,centres,inertias,strict=True):
        offset = p-centre
        inertia += tensor + m*(np.dot(offset,offset)*np.eye(3)-np.outer(offset,offset))
    old_inertia = trunk.find("inertial")
    trunk.remove(old_inertia)
    combined = ET.SubElement(trunk,"inertial")
    ET.SubElement(combined,"origin",{"xyz":" ".join(precise(value) for value in centre),"rpy":"0 0 0"})
    ET.SubElement(combined,"mass",{"value":exact_mass_text})
    ET.SubElement(combined,"inertia",{f"i{a}{b}":precise(inertia[i,j]) for i,a in enumerate("xyz") for j,b in enumerate("xyz") if i <= j})
    moved = []
    for name in PARTS:
        for kind in ("visual","collision"):
            for index,element in enumerate(links[name].findall(kind)):
                item = copy.deepcopy(element)
                item.set("name",f"compound_{name}_{kind}_{index}")
                write_origin(item,poses[name] @ transform(element.find("origin")))
                trunk.append(item)
                moved.append({"part":name,"kind":kind,"new_name":item.attrib["name"]})
        root.remove(links[name])
        root.remove(joints[name])
    # Keep the variant standalone, with relative mesh references and exact copies
    # of the source mesh bytes. This changes no mesh geometry.
    import shutil
    for mesh in root.findall(".//mesh"):
        path = Path(mesh.attrib["filename"])
        source = args.input.resolve().parent / path
        target = args.output.resolve().parent / path
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    total_before = sum(float(link.find("inertial/mass").attrib["value"]) for name,link in links.items() if name != "trunk") + float(masses[0])
    total_after = sum(float(link.find("inertial/mass").attrib["value"]) for link in root.findall("link"))
    merged_aggregate = aggregate_robot_inertia(root)
    aggregate_difference = {
        "mass_abs_kg": float(abs(merged_aggregate["mass_kg"] - independent_aggregate["mass_kg"])),
        "com_max_abs_m": float(np.max(np.abs(merged_aggregate["com_m"] - independent_aggregate["com_m"]))),
        "inertia_max_abs_kgm2": float(np.max(np.abs(merged_aggregate["inertia_kgm2"] - independent_aggregate["inertia_kgm2"]))),
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(root,space="  ")
    tree.write(args.output,encoding="utf-8",xml_declaration=True)
    receipt = {"status":"D034_MERGED_GEOMETRY_READY", "author":"-codex worker",
               "source":str(args.input.resolve()),"candidate":str(args.output.resolve()),
               "persistent_independent_reference": (
                   str(args.persistent_independent_reference.resolve())
                   if args.persistent_independent_reference is not None else None
               ),
               "rigid_links_before":len(links),"rigid_links_after":len(root.findall("link")),
               "total_mass_before_kg":total_before,"total_mass_after_kg":total_after,
               "trunk_mass_kg":float(mass),
               "trunk_com_m":[float(value) for value in centre],
               "trunk_inertia_kgm2":[[float(value) for value in row] for row in inertia],
               "new_geometry_independent_reference":serial_aggregate(independent_aggregate),
               "merged_aggregate":serial_aggregate(merged_aggregate),
               "aggregate_difference":aggregate_difference,
               "equivalence_criterion":"same new-geometry independent input; mass difference 0 and COM/inertia comparison recorded without hashes",
               "moved_geometry":moved,"geometry_removed":[],"hardware_pose_changes":[],
               "wrist_camera_tower":"retained as independent fixed link"}
    args.output.with_suffix(".proposal.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({key:receipt[key] for key in ("status","rigid_links_before","rigid_links_after","total_mass_before_kg","total_mass_after_kg","trunk_mass_kg")}))


if __name__ == "__main__":
    main()
