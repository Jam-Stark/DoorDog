"""Build the frozen v28 camera simulation envelopes and numerical checks."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
PACKAGE = Path("/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103/camera_setup/Vpiper-Plate-Dual-D435i")
sys.path.insert(0, str(PACKAGE / "code"))
from geometry import Robot, serial, tf, quat, R_M_O, R_O_USD
from build_u3_forward import make_variant
from mount_shapes import design_box, beam

RUNTIME = HERE / "runtime_logs/v28_camera_aware_rebaseline_20260909/g0"
WRIST_CENTER_HEIGHT_M = 0.140
WRIST_THETA_DEG = 38.76
BASE_TILT_DEG = 15.0
D20_REFERENCE_COLLISION_ANCHOR_OFFSET_M = 0.027158370732
SUPPORT_CLEARANCE_TARGET_M = 0.001
SUPPORT_CLEARANCE_SOLVER = HERE / "planner_evidence_20260909/asset/mount_clearance_check.py"
GRIPPER_COLLISION_MESH = HERE.parents[1] / "gr00t/rl/data/robots/a2_piper_vpiper_final_20260906/meshes/piper/gripper_base.STL"


def set_wrist_height(plan, height_m: float):
    """Set the reference-pose F-to-M vertical raise and rebuild optical frames."""
    camera = next(c for c in plan["cameras"] if c["name"] == "wrist")
    transform = np.asarray(camera["T_parent_M"])
    transform[:3, 3] *= height_m / 0.180
    camera.update(
        xyz_m=transform[:3, 3].tolist(),
        xyz_mm=(transform[:3, 3] * 1000.0).tolist(),
        T_parent_M=transform.tolist(),
    )
    for stream in camera["streams"].values():
        mechanical_optical = np.eye(4)
        mechanical_optical[:3, :3] = R_M_O
        mechanical_optical[:3, 3] = stream["offset_M_m"]
        optical = transform @ mechanical_optical
        usd = optical.copy()
        usd[:3, :3] = optical[:3, :3] @ R_O_USD
        stream.update(
            T_parent_optical=optical.tolist(),
            position_parent_m=optical[:3, 3].tolist(),
            quat_parent_ros_wxyz=quat(optical[:3, :3]).tolist(),
            T_parent_usd=usd.tolist(),
            quat_parent_usd_wxyz=quat(usd[:3, :3]).tolist(),
        )
    return plan


def support_box_corners(foot: np.ndarray, housing_bottom: np.ndarray, rotation: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(housing_bottom - foot)
    local = np.array(np.meshgrid(*([[-.5, .5]] * 3))).reshape(3, -1).T
    local *= np.array([.090, .025, length])
    return (rotation @ local.T).T + (foot + housing_bottom) / 2.0


def solve_support_mounting_end(visual_anchor: np.ndarray, housing_bottom: np.ndarray, rotation: np.ndarray):
    """Solve D-20's 1-mm convex clearance against the gripper collision hull."""
    asset = load_module("v28_support_clearance", SUPPORT_CLEARANCE_SOLVER)
    gripper_mesh = trimesh.load_mesh(GRIPPER_COLLISION_MESH, process=False)
    gripper_hull = asset.Hull("arm_body6_to_gripper#0", gripper_mesh.vertices)
    axis = housing_bottom - visual_anchor
    axis /= np.linalg.norm(axis)

    def signed_clearance(offset_m: float) -> float:
        foot = visual_anchor + offset_m * axis
        support_hull = asset.Hull(
            "wrist_camera_support#0",
            support_box_corners(foot, housing_bottom, rotation),
        )
        overlap = asset.intersect_depth(gripper_hull, support_hull)
        if overlap is not None and overlap > 1e-9:
            return -overlap
        return asset.distance(gripper_hull, support_hull)

    lower_offset_m = 0.0
    upper_offset_m = np.linalg.norm(housing_bottom - visual_anchor) - 1e-6
    if signed_clearance(lower_offset_m) >= SUPPORT_CLEARANCE_TARGET_M:
        raise ValueError("support visual anchor unexpectedly already exceeds the D-20 clearance target")
    if signed_clearance(upper_offset_m) <= SUPPORT_CLEARANCE_TARGET_M:
        raise ValueError("support cannot reach the D-20 clearance target before its length vanishes")
    for _ in range(48):
        midpoint_m = (lower_offset_m + upper_offset_m) / 2.0
        if signed_clearance(midpoint_m) < SUPPORT_CLEARANCE_TARGET_M:
            lower_offset_m = midpoint_m
        else:
            upper_offset_m = midpoint_m
    foot = visual_anchor + upper_offset_m * axis
    return foot, upper_offset_m, signed_clearance(upper_offset_m)


def simplify_wrist_support(plan):
    """Build D-19's 90x25-mm support from an actual D-20 collision solve."""
    camera = next(c for c in plan["cameras"] if c["name"] == "wrist")
    transform = np.asarray(camera["T_parent_M"])
    visual_anchor = np.asarray(plan["wrist_support_anchor"]["foot_center_F_m"])
    housing_bottom = transform[:3,3] + transform[:3,:3] @ np.array(
        [0.,0.,-plan["housing_size_M_m"][2]/2]
    )
    axis = housing_bottom - visual_anchor
    axis /= np.linalg.norm(axis)
    width_axis = transform[:3,1] - axis * np.dot(transform[:3,1], axis)
    width_axis /= np.linalg.norm(width_axis)
    thickness_axis = np.cross(axis, width_axis)
    support_rotation = np.column_stack([width_axis, thickness_axis, axis])
    foot, mounting_end_offset_m, clearance_m = solve_support_mounting_end(
        visual_anchor, housing_bottom, support_rotation,
    )
    support_size = [.090,.025,float(np.linalg.norm(housing_bottom-foot))]
    plan["brackets"] = [b for b in plan["brackets"] if b["parent"] == "trunk"] + [
        design_box("wrist_camera_support", "arm_body6_to_gripper", (foot+housing_bottom)/2,
                   support_size, support_rotation, contact="arm_body6_to_gripper")
    ]
    plan["wrist_support_model"] = {
        "status":"ESTIMATED_SIMULATION_GEOMETRY_NOT_HARDWARE_CAD",
        "cross_section_m":[.090,.025], "start_F_m":foot.tolist(),
        "end_F_m":housing_bottom.tolist(),
        "d20_reference_f45_offset_m":D20_REFERENCE_COLLISION_ANCHOR_OFFSET_M,
        "mounting_end_offset_m":mounting_end_offset_m,
        "target_static_clearance_m":SUPPORT_CLEARANCE_TARGET_M,
        "actual_static_clearance_m":clearance_m,
        "collision_element":"arm_body6_to_gripper#0 (meshes/piper/gripper_base.STL convex hull)",
        "clearance_solver":"mount_clearance_check.Hull + intersect_depth LP / distance SLSQP QP",
        "clearance_status":"D20_1MM_STATIC_CONVEX_CLEARANCE_SOLVED_FOR_F39_H140",
        "decision":"D-35: 140 mm / 38.76 deg tower with D-19 rectangular support",
    }
    return plan


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build_layouts():
    source = json.loads((PACKAGE / "source/U3_V_previous.json").read_text())
    pose = json.loads((PACKAGE / "config/reference_joint_pose.json").read_text())
    flange = Robot(PACKAGE / "robot").fk(pose)["arm_body6_to_gripper"]
    output = HERE / "camera"
    output.mkdir(exist_ok=True)
    plan = set_wrist_height(
        make_variant(source, flange, "U3_F39_H140", WRIST_THETA_DEG),
        WRIST_CENTER_HEIGHT_M,
    )
    plan = simplify_wrist_support(plan)
    brackets = [b for b in plan["brackets"]
                if b["parent"] != "trunk" or b["name"] in ("base_foot", "base_crossbar")]
    centre_transform = None
    for camera in plan["cameras"]:
        if camera["parent"] != "trunk":
            continue
        angles = [0., -BASE_TILT_DEG, 0.]
        transform = tf(camera["xyz_m"], np.radians(angles))
        rotation = transform[:3, :3]
        camera.update(
            rpy_deg=angles,
            rpy_rad=np.radians(angles).tolist(),
            T_parent_M=transform.tolist(),
            quat_parent_M_wxyz=quat(rotation).tolist(),
        )
        for stream in camera["streams"].values():
            mechanical_optical = np.eye(4)
            mechanical_optical[:3, :3] = R_M_O
            mechanical_optical[:3, 3] = stream["offset_M_m"]
            optical = transform @ mechanical_optical
            usd = optical.copy()
            usd[:3, :3] = optical[:3, :3] @ R_O_USD
            stream.update(
                T_parent_optical=optical.tolist(),
                position_parent_m=optical[:3, 3].tolist(),
                quat_parent_ros_wxyz=quat(optical[:3, :3]).tolist(),
                T_parent_usd=usd.tolist(),
                quat_parent_usd_wxyz=quat(usd[:3, :3]).tolist(),
            )
        centre = transform[:3, 3]
        mount = centre + rotation @ np.array([0., 0., -.0165])
        rail_start = [.045, centre[1], .155431554755]
        rail_end = [mount[0], centre[1], .155431554755]
        name = camera["name"]
        brackets.extend([
            beam(f"{name}_crossbar_rail", "trunk", rail_start, rail_end, .010),
            beam(f"{name}_post", "trunk", rail_end, mount, .010),
            design_box(f"{name}_saddle", "trunk", centre + rotation @ np.array([0., 0., -.0145]),
                       [.022, .080, .004], rotation, contact=name),
        ])
        if camera["name"] == "base_left":
            centre_transform = transform.copy()
            centre_transform[1, 3] = 0.0
    if centre_transform is None:
        raise ValueError("canonical rig lacks base_left for the D-06 central housing envelope")
    plan.update(
        plan_id="U3_F39_H140",
        name_cn="U3腕机140mm/38.76度训练包络",
        brackets=brackets,
        trunk_envelope_housings=[{
            "name": "base_center_housing",
            "parent": "trunk",
            "T_parent_item": centre_transform.tolist(),
            "size_m": plan["housing_size_M_m"],
            "status": "D06_D033_TEACHER_UNION_ENVELOPE_NOT_A_THIRD_CAMERA",
        }],
        hardware_status="SIMULATION_ENVELOPE; wrist bracket CAD not designed",
        mass_and_collision=(
            "Teacher asset uses the two-base-camera mass estimate and the D-06/D-33 "
            "trunk collision union; the central housing is collision-only. "
            "Tower mass is recomputed by v28_build_asset.py."
        ),
        wrist_tower_contract={
            "centre_height_from_flange_m": WRIST_CENTER_HEIGHT_M,
            "theta_deg": WRIST_THETA_DEG,
            "support_cross_section_m": [.090, .025],
            "collision_attachment": "D20 collision-surface attachment convention",
        },
    )
    (output / "U3_F39_H140.json").write_text(json.dumps(serial(plan), indent=2) + "\n")
    print("Built U3_F39_H140: 8 base support boxes, 2 base housings, 1 central union housing, and 1 wrist support.")


def occlusion():
    module = load_module("v28_c1", HERE / "planner_evidence_20260909/camera/t1_occlusion.py")
    module.OUT = RUNTIME / "c1"
    module.OUT.mkdir(parents=True, exist_ok=True)
    # F0 is the existing tool's mandatory coordinate-convention reference.
    module.THETAS = [0,40,45]
    module.OPENINGS = [0.,.013,.020,.035]
    module.make_variant = lambda *args: simplify_wrist_support(make_variant(*args))
    module.main()


def coverage():
    module = load_module("v28_coverage", HERE / "v28_u3f0_geometry_precheck.py")
    module.CAM_JSON = HERE / "camera/U3_F39_H140.json"
    module.DEFAULT_ARM_Q = np.array([0., .10, -.10, 0., -.415, 1.57])
    urdf = HERE.parents[1] / "gr00t/rl/data/robots/a2_piper_vpiper_final_20260906/a2_piper.urdf"
    mount_xyz = np.fromstring(ET.parse(urdf).getroot().find("joint[@name='arm_j0']/origin").attrib["xyz"],sep=" ")
    mount_shift = mount_xyz - np.array([.145,0.,.154])
    historical_fk = module.piper_fk
    def routed_fk(q):
        result = historical_fk(q)
        if q is module.DEFAULT_ARM_Q:
            for name in ("shoulder","elbow","wrist"):
                result[name] += mount_shift
            result["F"][:3,3] += mount_shift
        return result
    module.piper_fk = routed_fk
    output = RUNTIME / "c2/U3_F39_H140"
    report = module.run(["C_S2", "C_S21"], output)
    report.update(variant_json=str(module.CAM_JSON), synthetic_arm_q=module.DEFAULT_ARM_Q.tolist(),
                  evidence_level="COMPUTED", real_cad_validation="NOT_RUN: wrist bracket not designed",
                  synthetic_mount_xyz_m=mount_xyz.tolist(),
                  replay_geometry="Stage2-5 retain historical v27 FK; synthetic default uses current v28 arm_j0 mount")
    pose = report["static_poses"].pop("training_default_[0,0,0,0.25,0.5,1.57]")
    report["static_poses"][f"v28_default_{module.DEFAULT_ARM_Q.tolist()}"] = pose
    (output / "u3f0_geometry_precheck.json").write_text(json.dumps(report, indent=2)+"\n")
    module.write_markdown(report,output / "u3f0_geometry_precheck.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "occlusion", "coverage"])
    args = parser.parse_args()
    if args.command == "build":
        build_layouts()
    elif args.command == "occlusion":
        occlusion()
    else:
        coverage()
