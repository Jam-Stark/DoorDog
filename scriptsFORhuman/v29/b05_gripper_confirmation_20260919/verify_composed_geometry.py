"""Offline B05 planning calculation; does not create or edit simulation assets.

The finger/opening references come from the read-only URDF/STL section calculation
recorded in README.md. This complementary calculation checks the composed
neck/rose/return separation at the default grasp reference and fixed-pose approach.
"""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
ROBOT = ROOT / "gr00t/rl/data/robots/a2_piper_v29_merged_20260917"
families = json.loads((ROOT / "scriptsFORhuman/v29/b05_designs_20260918/families.json").read_text())["families"]
urdf = ET.parse(ROBOT / "a2_piper.urdf").getroot()


def origin_matrix(element):
    o = element.find("origin")
    if o is None:
        return np.eye(4)
    x, y, z = map(float, o.get("rpy", "0 0 0").split())
    sx, cx = math.sin(x), math.cos(x)
    sy, cy = math.sin(y), math.cos(y)
    sz, cz = math.sin(z), math.cos(z)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    t = np.eye(4)
    t[:3, :3] = rz @ ry @ rx
    t[:3, 3] = list(map(float, o.get("xyz", "0 0 0").split()))
    return t


tcp_z = 85.0
finger_half_x = 28.001
finger_forward = 50.8
rose_radius, rose_thickness = 27.0, 6.0
h_min, h_max = 55.0, 85.0
section_radii = {"F0": 15.0, "F1": 15.4, "F2": 1.1 * (math.hypot(9, 3) + 6),
                 "F3": 15.0, "F4": 15.0, "F5": 15.0, "F6": 15.0}
section_radius_max = max(section_radii.values())
rows = []
for f in families:
    fid = f["id"]
    length_i = f["free_s"][1] - f["free_s"][0]
    lam_min = max(0.90, 65.0 / length_i)
    if fid == "F3":
        half = 135.0 / 400.0 / 2.0
        g = np.array([400 * math.sin(half), 400 * (1 - math.cos(half))])
        tip = np.array([800 * math.sin(half), 0.0])
        tg = np.array([1.0, 0.0])
        tt = np.array([math.cos(half), -math.sin(half)])
    elif fid == "F4":
        slope = 2 * math.pi * 3 / 130
        g, tip = np.array([65.0, 0.0]), np.array([130.0, 0.0])
        tg = np.array([1.0, -slope]) / math.hypot(1, slope)
        tt = np.array([1.0, slope]) / math.hypot(1, slope)
    elif fid == "F5":
        g, tip = np.array([70.0, 8.0]), np.array([140.0, 0.0])
        tg = tt = np.array([1.0, 0.0])
    else:
        g, tip = np.array([f["X"] / 2, 0.0]), np.array([f["X"], 0.0])
        tg = tt = np.array([1.0, 0.0])
    root_projection = lam_min * float(g @ tg)
    tip_projection = lam_min * float((tip - g) @ tg)
    # Return centreline projection cannot move towards G: tip tangent dot tg>0,
    # and all door-normal bend/tail movement has zero projection onto tg.
    rows.append({
        "family": fid, "lambda_min": lam_min, "lambda_max": 1.1,
        "I_length_mm": [length_i * lam_min, length_i * 1.1],
        "J_length_mm": [length_i * lam_min - 62, length_i * 1.1 - 62],
        "G_to_axle_projection_min_mm": root_projection,
        "finger_to_rose_projected_separation_lower_bound_mm": root_projection - finger_half_x - rose_radius,
        "finger_to_neck_r15_projected_separation_lower_bound_mm": root_projection - finger_half_x - 15.0,
        "return_tip_tangent_dot_grasp_tangent": float(tt @ tg),
        "finger_to_return_projected_separation_lower_bound_mm": tip_projection - section_radii[fid] - finger_half_x,
        "maximum_section_enclosing_radius_mm": section_radii[fid],
    })

fixed_parts = []
joint = urdf.find("joint[@name='arm_body6_to_wrist_camera_tower']")
tower_to_base = origin_matrix(joint)
for collision in urdf.find("link[@name='wrist_camera_tower']").findall("collision"):
    t = tower_to_base @ origin_matrix(collision)
    half_size = np.array(list(map(float, collision.find("geometry/box").get("size").split()))) / 2
    bound = np.abs(t[:3, :3]) @ half_size
    lo, hi = (t[:3, 3] - bound) * 1000, (t[:3, 3] + bound) * 1000
    fixed_parts.append({"name": collision.get("name"), "base_bbox_mm": [lo.tolist(), hi.tolist()],
                        "normal_separation_from_handle_envelope_mm": tcp_z - float(hi[2]) - section_radius_max})
link6_to_base = np.linalg.inv(origin_matrix(urdf.find("joint[@name='arm_j6_to_gripper_base']")))
for collision in urdf.find("link[@name='arm_body6']").findall("collision"):
    mesh = trimesh.load_mesh(ROBOT / collision.find("geometry/mesh").get("filename"), process=False)
    t = link6_to_base @ origin_matrix(collision)
    vertices = (mesh.vertices @ t[:3, :3].T + t[:3, 3]) * 1000
    lo, hi = vertices.min(axis=0), vertices.max(axis=0)
    fixed_parts.append({"name": "arm_body6", "base_bbox_mm": [lo.tolist(), hi.tolist()],
                        "normal_separation_from_handle_envelope_mm": tcp_z - float(hi[2]) - section_radius_max})

result = {
    "evidence": "STATIC_GEOMETRIC_CONFIRMATION_ONLY",
    "conditions": ["Current URDF/STL and TCP85mm", "G at the midpoint of J", "Jaw fully open during fixed-pose straight approach",
                   "Door-plane centrelines and target frame remain aligned", "Round rose radius27/thickness6 and neck radius<=15mm",
                   "Return follows positive end tangent then bends toward door; closed tip extends toward door, not back toward G"],
    "not_proved": ["USD/PhysX imported collider/contact offsets", "Robot IK/whole-body reach or actual tracking errors",
                   "Force/friction stability", "Learning or hardware outcome"],
    "gripper_reference": {
        "tcp_z_mm": 85.0, "finger_half_x_bound_mm": 28.001, "finger_front_from_tcp_mm": 50.8,
        "palm_max_base_z_mm": 63.000001,
        "full_open_q_m": [0.035, -0.035],
        "full_open_sections_base_z_and_inner_gap_mm": [[67.964, 73.999424], [85, 73.999475], [100, 73.999614], [102.036, 73.950551], [130, 69.999871]],
        "source": "Single read-only URDF/STL triangle-section calculation for this Owner-requested second confirmation",
    },
    "maximum_F2_width_mm": 2 * section_radius_max,
    "F2_phi_for_max_closing_width_deg": math.degrees(math.atan2(9, 3)),
    "palm_to_handle_normal_separation_lower_bound_mm": tcp_z - 63.000001 - section_radius_max,
    "finger_to_door_plane_at_h55_mm": h_min - finger_forward,
    "main_rod_abs_closing_envelope_mm": {"F0": 15, "F1": 15.4, "F2": section_radius_max,
        "F3": 15 + 440 * (1 - math.cos(135 / 800)), "F4": 15 + 1.1 * (3 + 3 * math.pi), "F5": 23.8, "F6": 15},
    "family_bounds": rows, "additional_fixed_parts": fixed_parts,
    "return_joint_sampling": {
        "tip_cap_extent_rule": "r_tip is exact axial extent returned by the chosen smooth cap; it must fit within the local section enclosing radius for this first construction",
        "C_mm": "min(60,h-r_tip-8)", "R_mm": "Uniform[20,min(30,C)]", "H_mm": "Uniform[R,C]", "b_mm": "H-R",
        "worst_F2_cap_bound_mm": section_radius_max, "C_at_h55_with_this_bound_mm": h_min - section_radius_max - 8,
        "meaning": "Direct conditional sampling of Pro's valid joint domain, preserving h and family marginals; no clipping or retry fallback",
    },
}
(OUT / "readout.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({
    "max_section_width_mm": result["maximum_F2_width_mm"],
    "palm_separation_mm": result["palm_to_handle_normal_separation_lower_bound_mm"],
    "min_finger_rose_separation_mm": min(r["finger_to_rose_projected_separation_lower_bound_mm"] for r in rows),
    "min_finger_return_separation_mm": min(r["finger_to_return_projected_separation_lower_bound_mm"] for r in rows),
    "fixed_parts": fixed_parts, "return_C_min_mm": result["return_joint_sampling"]["C_at_h55_with_this_bound_mm"],
    "family_bounds": rows,
}, ensure_ascii=False))
