#!/usr/bin/env python3
"""Cut Vpiper visual and collision geometry below trunk z=0.130 m.

One horizontal plane spans both mount footprints. Fixed poses, joints and
source inertials are retained for this simulation comparison candidate.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import ConvexHull


SOURCE_DEFAULT = Path("gr00t/rl/data/robots/a2_piper_vpiper_final_20260906")
OUTPUT_DEFAULT = Path("gr00t/rl/data/robots/a2_piper_v28_cut_20260909")
CLEARANCE_M = 0.001
EPSILON = 1e-10


def rpy_matrix(rpy: np.ndarray) -> np.ndarray:
    roll, pitch, yaw = rpy
    cr, cp, cy = np.cos([roll, pitch, yaw])
    sr, sp, sy = np.sin([roll, pitch, yaw])
    return np.array([
        [cp * cy, cy * sr * sp - cr * sy, sr * sy + cr * cy * sp],
        [cp * sy, cr * cy + sr * sp * sy, cr * sp * sy - cy * sr],
        [-sp, cp * sr, cr * cp],
    ])


def origin_transform(element: ET.Element | None) -> np.ndarray:
    matrix = np.eye(4)
    if element is None:
        return matrix
    matrix[:3, :3] = rpy_matrix(np.fromstring(element.get("rpy", "0 0 0"), sep=" "))
    matrix[:3, 3] = np.fromstring(element.get("xyz", "0 0 0"), sep=" ")
    return matrix


def world_link_poses(root: ET.Element) -> dict[str, np.ndarray]:
    children: dict[str, list[ET.Element]] = {}
    for joint in root.findall("joint"):
        children.setdefault(joint.find("parent").attrib["link"], []).append(joint)
    poses = {"trunk": np.eye(4)}
    stack = ["trunk"]
    while stack:
        parent = stack.pop()
        for joint in children.get(parent, []):
            if joint.attrib["type"] != "fixed":
                continue
            child = joint.find("child").attrib["link"]
            poses[child] = poses[parent] @ origin_transform(joint.find("origin"))
            stack.append(child)
    return poses


def clipped_convex(vertices: np.ndarray, plane: np.ndarray) -> np.ndarray | None:
    hull = ConvexHull(vertices)
    edges = {tuple(sorted((int(a), int(b)))) for face in hull.simplices for a, b in itertools.combinations(face, 2)}
    values = vertices @ plane[:3] + plane[3]
    points = [vertex for vertex, value in zip(vertices, values) if value <= EPSILON]
    for first, second in edges:
        a, b = values[first], values[second]
        if (a < -EPSILON and b > EPSILON) or (a > EPSILON and b < -EPSILON):
            points.append(vertices[first] + (vertices[second] - vertices[first]) * (a / (a - b)))
    if len(points) < 4:
        return None
    unique = np.unique(np.round(np.asarray(points), 12), axis=0)
    if np.linalg.matrix_rank(unique - unique.mean(axis=0)) < 3:
        return None
    clipped = ConvexHull(unique)
    if clipped.volume <= 1e-14:
        return None
    return unique[clipped.vertices]


def cutter_mesh(corners_world: np.ndarray, link_from_world: np.ndarray) -> trimesh.Trimesh:
    corners_link = (link_from_world @ np.column_stack([corners_world, np.ones(len(corners_world))]).T).T[:, :3]
    hull = ConvexHull(corners_link)
    mesh = trimesh.Trimesh(vertices=corners_link, faces=hull.simplices, process=False)
    mesh.fix_normals()
    return mesh


def mesh_vertices(collision: ET.Element, package: Path) -> np.ndarray:
    mesh = collision.find("geometry/mesh")
    if mesh is None:
        raise ValueError(f"collision {collision.attrib.get('name')} is not a mesh")
    source = trimesh.load(package / mesh.attrib["filename"], force="mesh")
    return (origin_transform(collision.find("origin"))[:3, :3] @ source.vertices.T).T + origin_transform(collision.find("origin"))[:3, 3]


def inertials(root: ET.Element) -> dict[str, bytes]:
    return {link.attrib["name"]: ET.tostring(link.find("inertial")) for link in root.findall("link") if link.find("inertial") is not None}


def joints(root: ET.Element) -> dict[str, bytes]:
    return {joint.attrib["name"]: ET.tostring(joint) for joint in root.findall("joint")}


def write_piece(vertices: np.ndarray, destination: Path) -> float:
    hull = ConvexHull(vertices)
    mesh = trimesh.Trimesh(vertices=vertices, faces=hull.simplices, process=False)
    mesh.fix_normals()
    mesh.export(destination)
    return float(hull.volume)


def meshes_overlap_aabb(first: trimesh.Trimesh, second: trimesh.Trimesh) -> bool:
    return bool(np.all(first.bounds[1] >= second.bounds[0]) and np.all(second.bounds[1] >= first.bounds[0]))


def cut_visual(source_mesh: trimesh.Trimesh, cutters: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    result = source_mesh.copy()
    for cutter in cutters:
        if meshes_overlap_aabb(result, cutter):
            result = trimesh.boolean.difference([result, cutter], engine="manifold")
    if not result.is_watertight:
        raise RuntimeError("visual boolean produced a non-watertight mesh")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    original = ET.parse(source / "a2_piper.urdf").getroot()
    original_inertials = inertials(original)
    original_joints = joints(original)
    poses = world_link_poses(original)
    cut_plane_z = 0.130
    visual_world = {}
    for link_name in ("vpiper_main", "vpiper_support"):
        visual = original.find(f"link[@name='{link_name}']/visual/geometry/mesh")
        if visual is None:
            raise ValueError(f"missing mount visual: {link_name}")
        mesh = trimesh.load(source / visual.attrib["filename"], force="mesh")
        world_vertices = (poses[link_name][:3, :3] @ mesh.vertices.T).T + poses[link_name][:3, 3]
        visual_world[link_name] = world_vertices
    footprint = np.vstack(list(visual_world.values()))
    cutter_bottom = float(footprint[:, 2].min()) - CLEARANCE_M
    low = footprint[:, :2].min(axis=0) - CLEARANCE_M
    high = footprint[:, :2].max(axis=0) + CLEARANCE_M
    cutter_world = np.array([[x, y, z] for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (cutter_bottom, cut_plane_z)])
    output.mkdir(parents=True)
    shutil.copytree(source / "meshes", output / "meshes")
    root = copy.deepcopy(original)
    changed: list[dict[str, object]] = []
    remaining_world_meshes: list[np.ndarray] = []
    collision_counts = {"source": 0, "retained": 0, "plane_cut": 0, "removed": 0}
    visual_receipt: list[dict[str, object]] = []
    for link_name in ("vpiper_main", "vpiper_support"):
        link = root.find(f"link[@name='{link_name}']")
        source_link = original.find(f"link[@name='{link_name}']")
        if link is None or source_link is None or link_name not in poses:
            raise ValueError(f"missing fixed mount link: {link_name}")
        link_from_world = np.linalg.inv(poses[link_name])
        local_cutter = cutter_mesh(cutter_world, link_from_world)
        horizontal_plane = np.r_[-poses[link_name][2, :3], cut_plane_z - poses[link_name][2, 3]]
        source_visual = source_link.find("visual/geometry/mesh")
        target_visual = link.find("visual/geometry/mesh")
        if source_visual is None or target_visual is None:
            raise ValueError(f"missing copied visual: {link_name}")
        source_visual_mesh = trimesh.load(source / source_visual.attrib["filename"], force="mesh")
        cut_visual_mesh = cut_visual(source_visual_mesh, [local_cutter])
        visual_filename = f"v28_cut_{link_name}_visual.stl"
        cut_visual_mesh.export(output / "meshes/mount" / visual_filename)
        target_visual.attrib["filename"] = f"meshes/mount/{visual_filename}"
        visual_receipt.append({
            "link": link_name,
            "source_volume_mm3": abs(float(source_visual_mesh.volume)) * 1e9,
            "cut_volume_mm3": abs(float(cut_visual_mesh.volume)) * 1e9,
            "source_bounds_m": source_visual_mesh.bounds.tolist(),
            "cut_bounds_m": cut_visual_mesh.bounds.tolist(),
            "remaining_components": len(cut_visual_mesh.split(only_watertight=False)),
        })
        for source_collision in source_link.findall("collision"):
            if source_collision.find("geometry/mesh") is None:
                continue
            collision_counts["source"] += 1
            original_vertices = mesh_vertices(source_collision, source)
            original_vertices = original_vertices[ConvexHull(original_vertices).vertices]
            target_collision = link.find(f"collision[@name='{source_collision.attrib['name']}']")
            if target_collision is None:
                raise ValueError(f"missing copied collision {source_collision.attrib['name']}")
            world_vertices = (poses[link_name][:3, :3] @ original_vertices.T).T + poses[link_name][:3, 3]
            world_z = world_vertices[:, 2]
            if world_z.max() <= cut_plane_z + EPSILON:
                link.remove(target_collision)
                collision_counts["removed"] += 1
                changed.append({"link": link_name, "collision": source_collision.attrib["name"], "status": "removed_below_plane", "source_volume_mm3": abs(float(ConvexHull(original_vertices).volume)) * 1e9})
                continue
            if world_z.min() >= cut_plane_z - EPSILON:
                collision_counts["retained"] += 1
                remaining_world_meshes.append(world_vertices)
                continue
            vertices = clipped_convex(original_vertices, horizontal_plane)
            if vertices is None:
                raise RuntimeError(f"plane cut removed an unexpectedly degenerate collider: {source_collision.attrib['name']}")
            source_index = list(link).index(target_collision)
            link.remove(target_collision)
            filename = f"v28_horizontal_cut_{source_collision.attrib['name']}.stl"
            cut_volume = write_piece(vertices, output / "meshes/mount" / filename)
            replacement = copy.deepcopy(target_collision)
            replacement.attrib["name"] = f"{source_collision.attrib['name']}_horizontal_cut"
            replacement.find("geometry/mesh").attrib["filename"] = f"meshes/mount/{filename}"
            link.insert(source_index, replacement)
            collision_counts["plane_cut"] += 1
            remaining_world_meshes.append((poses[link_name][:3, :3] @ vertices.T).T + poses[link_name][:3, 3])
            changed.append({
                "link": link_name,
                "collision": source_collision.attrib["name"],
                "status": "horizontal_plane_cut",
                "source_volume_mm3": abs(float(ConvexHull(original_vertices).volume)) * 1e9,
                "cut_volume_mm3": cut_volume * 1e9,
            })
    if not remaining_world_meshes:
        raise RuntimeError("horizontal cut removed every mount collider")
    output_urdf = output / "a2_piper.urdf"
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output_urdf, encoding="utf-8", xml_declaration=True)
    built = ET.parse(output_urdf).getroot()
    if inertials(built) != original_inertials:
        raise RuntimeError("cut asset changed inertials")
    if joints(built) != original_joints:
        raise RuntimeError("cut asset changed joint poses, axes, or limits")
    minimum_world_z = min(float(vertices[:, 2].min()) for vertices in remaining_world_meshes)
    if minimum_world_z < cut_plane_z - EPSILON:
        raise RuntimeError("horizontal cut left collision below the required plane")
    readme = """# v28 horizontal collision-and-visual cut asset\n\nThis comparison variant retains all source mount poses, joints, inertials, arm geometry, and camera transforms. A single world-horizontal cut at trunk `z=0.130 m` removes all `vpiper_main` and `vpiper_support` visual and collision geometry below that plane. The plane is 1 mm above trunk collision box #1's top (`z=0.129 m`). It spans both mount footprints, so no lower side foot or isolated collision fragment remains.\n\nSource mass and inertia are intentionally retained despite the removed volume, as a simulation approximation. Visual meshes are cut with Manifold; convex collision proxies are retained above the same plane, clipped once at the plane, or removed when fully below it. This is a simulation comparison asset, not hardware CAD.\n\nBuild with `PYTHONPATH=/tmp/v28_mesh_boolean /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v28/v28_build_cut_asset.py --source gr00t/rl/data/robots/a2_piper_vpiper_final_20260906 --output gr00t/rl/data/robots/a2_piper_v28_cut_20260909`.\n"""
    (output / "README.md").write_text(readme)
    result = {
        "evidence": "STATIC_CPU",
        "source": str(source),
        "output": str(output),
        "cut_plane_z_m": cut_plane_z,
        "highest_source_conflict_trunk_box_top_z_m": 0.129,
        "trunk_clearance_above_highest_conflict_m": 0.001,
        "cutter_world_bounds_m": [cutter_world.min(axis=0).tolist(), cutter_world.max(axis=0).tolist()],
        "collision_counts": collision_counts,
        "collision_volume_changes": changed,
        "minimum_remaining_collision_world_z_m": minimum_world_z,
        "mass_and_pose": "unchanged: source URDF inertials and joints byte-identical",
        "visual_cut": visual_receipt,
    }
    validation = output / "validation"
    validation.mkdir()
    (validation / "cut_geometry.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
