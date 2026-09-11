#!/usr/bin/env python3
"""Refine support collision 19 only when its source visual clears trunk collision 1.

This intentionally stops before producing a smaller proxy if the source-derived
support visual mesh crosses the retained trunk collision box.  A collision
refinement is then not a geometry-preserving repair.
"""

from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import trimesh
from scipy.optimize import linprog
from scipy.spatial import ConvexHull


PACKAGE = Path("gr00t/rl/data/robots/a2_piper_vpiper_final_20260906")


def transform(xyz: np.ndarray, rpy: np.ndarray) -> np.ndarray:
    cx, cy, cz = np.cos(rpy)
    sx, sy, sz = np.sin(rpy)
    rotation = np.array([
        [cy * cz, cz * sx * sy - cx * sz, sx * sz + cx * cz * sy],
        [cy * sz, cx * cz + sx * sy * sz, cx * sy * sz - cz * sx],
        [-sy, cy * sx, cx * cy],
    ])
    result = np.eye(4)
    result[:3, :3] = rotation
    result[:3, 3] = xyz
    return result


def origin(element: ET.Element | None) -> np.ndarray:
    if element is None:
        return np.eye(4)
    return transform(np.fromstring(element.get("xyz", "0 0 0"), sep=" "), np.fromstring(element.get("rpy", "0 0 0"), sep=" "))


def support_transform(root: ET.Element) -> np.ndarray:
    joints = {joint.attrib["name"]: joint for joint in root.findall("joint")}
    main = joints["trunk_to_vpiper"]
    support = joints["vpiper_to_support"]
    if main.find("parent").attrib["link"] != "trunk" or main.find("child").attrib["link"] != "vpiper_main":
        raise ValueError("unexpected trunk_to_vpiper topology")
    if support.find("parent").attrib["link"] != "vpiper_main" or support.find("child").attrib["link"] != "vpiper_support":
        raise ValueError("unexpected vpiper_to_support topology")
    return origin(main.find("origin")) @ origin(support.find("origin"))


def triangle_intersects_box(triangle: np.ndarray, center: np.ndarray, half_extent: np.ndarray) -> bool:
    vertices = triangle - center
    edges = np.array([vertices[1] - vertices[0], vertices[2] - vertices[1], vertices[0] - vertices[2]])
    axes = [*np.eye(3), np.cross(edges[0], edges[1])]
    for edge in edges:
        axes.extend(np.cross(edge, np.eye(3)[axis]) for axis in range(3))
    for axis in axes:
        if np.dot(axis, axis) <= 1e-22:
            continue
        projected = vertices @ axis
        radius = np.dot(half_extent, np.abs(axis))
        if projected.min() > radius + 1e-12 or projected.max() < -radius - 1e-12:
            return False
    return True


def hull_overlap_depth(points_a: np.ndarray, points_b: np.ndarray) -> float:
    hull_a = ConvexHull(points_a)
    hull_b = ConvexHull(points_b)
    equations_a = hull_a.equations
    equations_b = hull_b.equations
    normals_a = equations_a[:, :3] / np.linalg.norm(equations_a[:, :3], axis=1, keepdims=True)
    normals_b = equations_b[:, :3] / np.linalg.norm(equations_b[:, :3], axis=1, keepdims=True)
    offsets_a = -equations_a[:, 3] / np.linalg.norm(equations_a[:, :3], axis=1)
    offsets_b = -equations_b[:, 3] / np.linalg.norm(equations_b[:, :3], axis=1)
    constraints = np.vstack([
        np.hstack([normals_a, np.ones((len(normals_a), 1))]),
        np.hstack([normals_b, np.ones((len(normals_b), 1))]),
    ])
    bounds = np.concatenate([offsets_a, offsets_b])
    result = linprog(c=[0, 0, 0, -1], A_ub=constraints, b_ub=bounds, bounds=[(None, None)] * 3 + [(-1.0, 1.0)], method="highs")
    if result.status != 0:
        raise RuntimeError(f"LP failed: {result.message}")
    return float(result.x[3])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PACKAGE)
    args = parser.parse_args()
    package = args.package
    root = ET.parse(package / "a2_piper.urdf").getroot()
    trunk = root.find("link[@name='trunk']")
    if trunk is None:
        raise ValueError("missing trunk link")
    collisions = trunk.findall("collision")
    if len(collisions) < 2:
        raise ValueError("trunk collision #1 is absent")
    trunk_box = collisions[1]
    box = trunk_box.find("geometry/box")
    if box is None:
        raise ValueError("trunk collision #1 is not a box")
    box_size = np.fromstring(box.attrib["size"], sep=" ")
    box_transform = origin(trunk_box.find("origin"))
    box_center = box_transform[:3, 3]
    box_half = box_size / 2.0
    visual = trimesh.load(package / "meshes/mount/vpiper_support_visual.stl", force="mesh")
    support_pose = support_transform(root)
    visual.apply_transform(support_pose)
    candidate_faces = np.flatnonzero(np.all(visual.triangles.max(axis=1) >= box_center - box_half, axis=1) & np.all(visual.triangles.min(axis=1) <= box_center + box_half, axis=1))
    visual_hits = [int(index) for index in candidate_faces if triangle_intersects_box(visual.triangles[index], box_center, box_half)]
    current_hull = trimesh.load(package / "meshes/mount/vpiper_support_collision_19.stl", force="mesh")
    current_hull.apply_transform(support_pose)
    box_points = np.array([[x, y, z] for x in (box_center[0] - box_half[0], box_center[0] + box_half[0]) for y in (box_center[1] - box_half[1], box_center[1] + box_half[1]) for z in (box_center[2] - box_half[2], box_center[2] + box_half[2])])
    decomposition = json.loads((package / "validation/mount_collision_decomposition.json").read_text())
    source_part = decomposition["vpiper_support"]["parts"][19]
    result = {
        "evidence": "STATIC_CPU",
        "support_collision": "vpiper_support_collision_19",
        "source_partition_mm3": source_part["source_partition_mm3"],
        "current_hull_mm3": source_part["convex_hull_mm3"],
        "current_hull_oversize_ratio": source_part["oversize_ratio"],
        "current_hull_trunk_1_overlap_depth_m": hull_overlap_depth(current_hull.vertices, box_points),
        "source_visual_triangle_box_intersections": len(visual_hits),
        "source_visual_triangle_indices": visual_hits,
        "decision": "NO_REFINEMENT_WRITTEN" if visual_hits else "REFINEMENT_REQUIRED",
    }
    print(json.dumps(result, indent=2))
    if visual_hits:
        raise SystemExit("source-derived support visual intersects retained trunk collision #1; refusing geometry-shrinking proxy")


if __name__ == "__main__":
    main()
