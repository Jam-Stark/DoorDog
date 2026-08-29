#!/usr/bin/env python3
"""Wave K bilateral A2+PiPER scripted grasp/down-press kinematics probe."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DEFAULT = ROOT / "logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/K/k_kinematics.json"
ARM_NAMES = tuple(f"arm_j{index}" for index in range(1, 7))
SIDE_NAMES = ("LEFT", "RIGHT")
FIXTURE = {
    "door_width_m": 0.95,
    "door_height_m": 2.05,
    "door_handle_height_m": 0.90,
    "door_handle_width_m": 0.115,
    "door_weight_kg": 100.0,
    "door_open_io": "out",
    "handle_drive_max_force_nm": 2.0,
    "hinge_drive_max_force_nm": 7.25,
    "hinge_drive_stiffness": 5.5,
    "handle_length_m": 0.125,
    "axle_length_m": 0.195,
    "hook_length_m": 0.05,
    "handle_radius_m": 0.013,
    "build_latch": True,
}
ACTION_DEFAULT_ARM_Q = (0.0, 0.0, 0.0, 0.25, 0.5, 1.57)
SCAN_SEED_ANCHOR_ARM_Q = (0.0, 1.48, -0.63, -0.84, 0.0, 1.57)
SAGITTAL_MIRROR_SIGNS_ARM_J1_TO_J6 = (-1, 1, 1, -1, 1, -1)
ACTION_SCALE = 0.25
TCP_OFFSET_Z_M = 0.085
IK_STEPS = 360
MAX_POSITION_STEP_M = 0.005
MAX_ORIENTATION_STEP_RAD = 0.03
POSITION_TOLERANCE_M = 0.03
ORIENTATION_TOLERANCE_RAD = 0.10
MIN_HARD_LIMIT_MARGIN_RAD = 0.10
JOINT_MARGIN_ASYMMETRY_RAD = 0.15
J6_TRAVEL_ASYMMETRY_RAD = 0.25
ROOT_OFFSET_READBACK_TOLERANCE_M = 1.0e-4
JOINT_STATE_READBACK_TOLERANCE_RAD = 1.0e-5
STAGE3_GRID_X_M = (-0.72, -0.76, -0.80)
STAGE3_GRID_LATERAL_MAGNITUDE_M = (0.18, 0.22, 0.26)
STAGE3_GRID_Z_M = 0.415
STAGE3_GRID_YAW_RAD = 0.0
STAGE3_ANCHOR_PROVENANCE = {
    "source": "v26_3 M1_S1 step750 Stage3 terminal runtime readback",
    "left_n32_p50_root_pos_rel_xyzm": [-0.75436, 0.22466, 0.41584],
    "left_yaw_rad": 0.01995,
    "right_n13_p50_root_pos_rel_xyzm": [-0.76093, -0.22191, 0.41347],
    "right_yaw_rad": -0.10104,
    "matched_symmetric_anchor_xyzm_yaw": [-0.75765, 0.22329, 0.41466, 0.0],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    return parser.parse_args()


def _finite(name: str, tensor, expected_shape: tuple[int, ...], torch) -> None:
    if not torch.is_tensor(tensor) or tuple(tensor.shape) != expected_shape or not tensor.is_floating_point():
        shape = None if not torch.is_tensor(tensor) else tuple(tensor.shape)
        raise RuntimeError(f"Wave K {name} must be floating shape {expected_shape}; got {shape}.")
    if not bool(torch.all(torch.isfinite(tensor)).item()):
        raise RuntimeError(f"Wave K {name} contains non-finite values.")


def _json_float(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise RuntimeError(f"Wave K attempted to serialize non-finite value: {value!r}.")
    return value


def _door_cfg(build_doorman_door_cfg):
    from isaaclab.actuators import ImplicitActuatorCfg
    from isaaclab.sim import CollisionPropertiesCfg, MultiAssetSpawnerCfg

    door_cfg = build_doorman_door_cfg(2)
    if not isinstance(door_cfg.spawn, MultiAssetSpawnerCfg):
        raise RuntimeError("Wave K requires the repository MultiAssetSpawnerCfg door path.")
    if not door_cfg.spawn.assets_cfg:
        raise RuntimeError("Wave K door route has no asset template.")
    template = copy.deepcopy(door_cfg.spawn.assets_cfg[0])
    assets = []
    for side_name, open_lr in zip(SIDE_NAMES, ("left", "right"), strict=True):
        asset = copy.deepcopy(template)
        asset.rand_door_width = FIXTURE["door_width_m"]
        asset.rand_door_height = FIXTURE["door_height_m"]
        asset.rand_door_handle_height = FIXTURE["door_handle_height_m"]
        asset.rand_door_handle_width = FIXTURE["door_handle_width_m"]
        asset.rand_door_weight = FIXTURE["door_weight_kg"]
        asset.rand_door_handle_type = "lever"
        asset.rand_door_open_lr = open_lr
        asset.rand_door_open_io = FIXTURE["door_open_io"]
        asset.rand_axle_length = FIXTURE["axle_length_m"]
        asset.rand_handle_length = FIXTURE["handle_length_m"]
        asset.rand_hook_length = FIXTURE["hook_length_m"]
        asset.rand_handle_radius = FIXTURE["handle_radius_m"]
        asset.rand_spawn_hook = False
        asset.rand_hinge_drive_max_force = FIXTURE["hinge_drive_max_force_nm"]
        asset.rand_hinge_drive_stiffness = FIXTURE["hinge_drive_stiffness"]
        asset.rand_handle_drive_max_force = FIXTURE["handle_drive_max_force_nm"]
        asset.randomize_material = False
        asset.use_preloaded_materials = False
        asset.dynamic_material_randomization = False
        asset.collision_props = CollisionPropertiesCfg(collision_enabled=False)
        asset.activate_contact_sensors = False
        assets.append(asset)
    door_cfg.spawn.assets_cfg = assets
    door_cfg.spawn.random_choice = False
    door_cfg.spawn.activate_contact_sensors = False
    door_cfg.actuators["hinge"] = ImplicitActuatorCfg(
        joint_names_expr=[".*hinge.*"],
        effort_limit_sim=20.0,
        velocity_limit_sim=100.0,
        stiffness=FIXTURE["hinge_drive_stiffness"],
        damping=50.0,
    )
    return door_cfg


def _make_scene(args: argparse.Namespace):
    import isaaclab.sim as sim_utils
    import torch
    from isaaclab.assets import ArticulationCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.sensors import FrameTransformerCfg
    from isaaclab.sensors.frame_transformer import OffsetCfg
    from isaaclab.sim import SimulationContext
    from isaaclab.utils import configclass
    from gr00t.rl.envs.door.a2_piper_door_scene_preview import (
        build_a2_piper_robot_cfg,
        build_doorman_door_cfg,
    )
    from gr00t.rl.envs.door.door_open_a2_base import OrderedTargetFrameTransformer

    robot_cfg = build_a2_piper_robot_cfg(
        usd_path=ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd",
        root_x=0.0,
        root_y=0.0,
        root_z=0.0,
        root_yaw=0.0,
    )
    robot_cfg.spawn.rigid_props.disable_gravity = True
    robot_cfg.spawn.articulation_props.fix_root_link = True
    door_cfg = _door_cfg(build_doorman_door_cfg)
    frames = FrameTransformerCfg(
        prim_path="/World/envs/env_.*/Robot/arm_body6_to_gripper",
        source_frame_offset=OffsetCfg(pos=(0.0, 0.0, TCP_OFFSET_Z_M)),
        target_frames=[
            FrameTransformerCfg.FrameCfg(
                prim_path="/World/envs/env_.*/door/grasp_target",
                name="downpress_grasp_target",
                offset=OffsetCfg(rot=(0.5, 0.5, 0.5, 0.5)),
            )
        ],
    )
    frames.class_type = OrderedTargetFrameTransformer

    @configclass
    class KinematicsSceneCfg(InteractiveSceneCfg):
        robot: ArticulationCfg = robot_cfg.replace(prim_path="{ENV_REGEX_NS}/Robot")
        door: ArticulationCfg = door_cfg.replace(prim_path="{ENV_REGEX_NS}/door")
        piper_downpress_frames = frames

    sim = SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=args.device))
    scene = InteractiveScene(KinematicsSceneCfg(num_envs=2, env_spacing=3.0, replicate_physics=False))
    return sim, scene, torch


def _mirror_matched_scan_seed_pair(torch, device, dtype):
    anchor_seed = torch.tensor(SCAN_SEED_ANCHOR_ARM_Q, device=device, dtype=dtype)
    mirror_signs = torch.tensor(SAGITTAL_MIRROR_SIGNS_ARM_J1_TO_J6, device=device, dtype=dtype)
    seed_pair = torch.stack((anchor_seed, mirror_signs * anchor_seed), dim=0)
    if not bool(torch.equal(seed_pair[1], mirror_signs * seed_pair[0])):
        raise RuntimeError("Wave K mirror-matched scan seed identity failed.")
    return seed_pair


def _reset_scene(sim, scene, arm_ids, door_local_root_offsets, scan_seed_pair, torch) -> None:
    from isaaclab.utils.math import quat_apply

    robot = scene["robot"]
    door = scene["door"]
    door_root = door.data.default_root_state.clone()
    door_root[:, :3] += scene.env_origins
    door.write_root_pose_to_sim(door_root[:, :7])
    door.write_root_velocity_to_sim(door_root[:, 7:])
    door_q = door.data.default_joint_pos.clone()
    door.write_joint_state_to_sim(door_q, torch.zeros_like(door.data.default_joint_vel))
    door.set_joint_position_target(door_q)
    root = robot.data.default_root_state.clone()
    _finite("door_local_root_offsets", door_local_root_offsets, (2, 3), torch)
    root[:, :3] = door_root[:, :3] + quat_apply(door_root[:, 3:7], door_local_root_offsets)
    root[:, 3:7] = door_root[:, 3:7]
    root[:, 7:] = 0.0
    robot.write_root_pose_to_sim(root[:, :7])
    robot.write_root_velocity_to_sim(root[:, 7:])
    q = robot.data.default_joint_pos.clone()
    _finite("mirror_matched_scan_seed_pair", scan_seed_pair, (2, 6), torch)
    q[:, arm_ids] = scan_seed_pair
    robot.write_joint_state_to_sim(q, torch.zeros_like(robot.data.default_joint_vel))
    robot.set_joint_position_target(q)
    scene.reset()
    scene.write_data_to_sim()
    sim.forward()
    scene.update(sim.get_physics_dt())


def _read_handle_joint_frames(torch):
    from omni.usd import get_context
    from pxr import Gf, UsdGeom

    stage = get_context().get_stage()
    result = []
    for env_id, side_name in enumerate(SIDE_NAMES):
        joint_path = f"/World/envs/env_{env_id}/door/door_panel/handle_joint"
        panel_path = f"/World/envs/env_{env_id}/door/door_panel"
        joint = stage.GetPrimAtPath(joint_path)
        panel = stage.GetPrimAtPath(panel_path)
        if not joint.IsValid() or not panel.IsValid():
            raise RuntimeError(f"Wave K missing handle joint or panel for {side_name}: {joint_path}.")
        local_pos = joint.GetAttribute("physics:localPos0").Get()
        local_rot = joint.GetAttribute("physics:localRot0").Get()
        if local_pos is None or local_rot is None:
            raise RuntimeError(f"Wave K {side_name} handle joint lacks LocalPos0/LocalRot0.")
        local_rot_values = [float(local_rot.GetReal()), *[float(item) for item in local_rot.GetImaginary()]]
        if side_name == "RIGHT":
            if not (
                abs(local_rot_values[0]) < 1.0e-6
                and abs(local_rot_values[1]) < 1.0e-6
                and abs(local_rot_values[2]) < 1.0e-6
                and abs(abs(local_rot_values[3]) - 1.0) < 1.0e-6
            ):
                raise RuntimeError(
                    "Wave K right-side handle LocalRot0 must be a 180-degree Z rotation; "
                    f"got {local_rot_values}."
                )
        xform = UsdGeom.XformCache().GetLocalToWorldTransform(panel)
        axis_local = Gf.Rotation(Gf.Quatd(local_rot)).TransformDir(Gf.Vec3d(1.0, 0.0, 0.0))
        axis_world_gf = xform.TransformDir(axis_local)
        axis_origin_gf = xform.Transform(Gf.Vec3d(local_pos))
        axis_world = torch.tensor(
            [float(axis_world_gf[0]), float(axis_world_gf[1]), float(axis_world_gf[2])], device="cuda:0", dtype=torch.float32
        )
        axis_origin = torch.tensor(
            [float(axis_origin_gf[0]), float(axis_origin_gf[1]), float(axis_origin_gf[2])], device="cuda:0", dtype=torch.float32
        )
        axis_norm = torch.linalg.norm(axis_world)
        if not bool(torch.isfinite(axis_norm).item()) or not bool((axis_norm > 0.0).item()):
            raise RuntimeError(f"Wave K {side_name} handle axis is invalid.")
        result.append(
            {
                "joint_path": joint_path,
                "local_pos0_m": [float(item) for item in local_pos],
                "local_rot0_wxyz": local_rot_values,
                "axis_origin_world_m": axis_origin,
                "axis_world_unit": axis_world / axis_norm,
            }
        )
    return result


def _run_pose_scan(sim, scene, door_local_root_offsets, scan_seed_pair, torch):
    from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
    from isaaclab.utils.math import axis_angle_from_quat, quat_inv, quat_mul, subtract_frame_transforms
    from gr00t.rl.envs.door.door_open_a2_base import (
        a2_hold_apply_source_offset_to_jacobian,
        a2_hold_bound_pose_command_step,
        a2_hold_rotate_jacobian_to_root,
    )

    robot = scene["robot"]
    arm_ids, arm_names = robot.find_joints(list(ARM_NAMES), preserve_order=True)
    if tuple(arm_names) != ARM_NAMES or len(arm_ids) != 6:
        raise RuntimeError(f"Wave K arm joint mapping mismatch: {arm_names}.")
    body_ids, body_names = robot.find_bodies("arm_body6_to_gripper", preserve_order=True)
    if body_names != ["arm_body6_to_gripper"] or len(body_ids) != 1:
        raise RuntimeError(f"Wave K end-effector mapping mismatch: {body_ids}, {body_names}.")
    if not robot.is_fixed_base:
        raise RuntimeError("Wave K requires a fixed-root A2+PiPER static kinematics articulation.")
    _reset_scene(sim, scene, arm_ids, door_local_root_offsets, scan_seed_pair, torch)
    controller = DifferentialIKController(
        DifferentialIKControllerCfg(
            command_type="pose", use_relative_mode=False, ik_method="dls", ik_params={"lambda_val": 0.01}
        ),
        num_envs=2,
        device=str(robot.device),
    )
    jacobian_body_id = body_ids[0] - 1
    if jacobian_body_id < 0:
        raise RuntimeError(f"Wave K fixed-base Jacobian body index is invalid: {jacobian_body_id}.")
    jacobian_columns = arm_ids
    active = torch.ones(2, dtype=torch.bool, device=robot.device)
    invalid_limit = torch.zeros(2, dtype=torch.bool, device=robot.device)
    first_rejections: list[dict[str, object] | None] = [None, None]
    condition_max = torch.zeros(2, dtype=robot.data.joint_pos.dtype, device=robot.device)
    last_q_des = robot.data.joint_pos[:, arm_ids].clone()
    for step in range(IK_STEPS):
        frames = scene.sensors["piper_downpress_frames"].data
        source_pos_w = frames.source_pos_w
        source_quat_w = frames.source_quat_w
        target_pos_w = frames.target_pos_w[:, 0, :]
        target_quat_w = frames.target_quat_w[:, 0, :]
        root_pos_w = robot.data.root_pos_w
        root_quat_w = robot.data.root_quat_w
        body_pos_w = robot.data.body_pos_w[:, body_ids[0]]
        body_quat_w = robot.data.body_quat_w[:, body_ids[0]]
        for name, tensor, shape in (
            ("source_pos_w", source_pos_w, (2, 3)),
            ("source_quat_w", source_quat_w, (2, 4)),
            ("target_pos_w", target_pos_w, (2, 3)),
            ("target_quat_w", target_quat_w, (2, 4)),
            ("root_pos_w", root_pos_w, (2, 3)),
            ("root_quat_w", root_quat_w, (2, 4)),
            ("body_pos_w", body_pos_w, (2, 3)),
            ("body_quat_w", body_quat_w, (2, 4)),
        ):
            _finite(name, tensor, shape, torch)
        source_pos_root, source_quat_root = subtract_frame_transforms(root_pos_w, root_quat_w, source_pos_w, source_quat_w)
        target_pos_root, target_quat_root = subtract_frame_transforms(root_pos_w, root_quat_w, target_pos_w, target_quat_w)
        body_pos_root, _ = subtract_frame_transforms(root_pos_w, root_quat_w, body_pos_w, body_quat_w)
        jacobian_w = robot.root_physx_view.get_jacobians()[:, jacobian_body_id, :, jacobian_columns]
        _finite("arm_jacobian_w", jacobian_w, (2, 6, 6), torch)
        jacobian_root = a2_hold_rotate_jacobian_to_root(jacobian_w, root_quat_w)
        jacobian_root = a2_hold_apply_source_offset_to_jacobian(jacobian_root, source_pos_root - body_pos_root)
        _finite("arm_jacobian_root", jacobian_root, (2, 6, 6), torch)
        singular_values = torch.linalg.svdvals(jacobian_root)
        _finite("arm_jacobian_singular_values", singular_values, (2, 6), torch)
        condition = singular_values[:, 0] / singular_values[:, -1]
        if not bool(torch.all(torch.isfinite(condition)).item()):
            raise RuntimeError("Wave K DLS Jacobian condition is non-finite.")
        condition_max = torch.maximum(condition_max, condition)
        command_pos, command_quat, _, _, _ = a2_hold_bound_pose_command_step(
            source_pos_root,
            source_quat_root,
            target_pos_root,
            target_quat_root,
            MAX_POSITION_STEP_M,
            MAX_ORIENTATION_STEP_RAD,
        )
        controller.set_command(torch.cat((command_pos, command_quat), dim=-1))
        q_current = robot.data.joint_pos[:, arm_ids]
        q_des = controller.compute(source_pos_root, source_quat_root, jacobian_root, q_current)
        _finite("q_des", q_des, (2, 6), torch)
        hard_limits = robot.data.joint_pos_limits[:, arm_ids]
        _finite("hard_joint_limits", hard_limits, (2, 6, 2), torch)
        candidate_invalid = torch.any((q_des < hard_limits[..., 0]) | (q_des > hard_limits[..., 1]), dim=-1)
        lower_violation = q_des < hard_limits[..., 0]
        upper_violation = q_des > hard_limits[..., 1]
        violation_overshoot = torch.where(
            lower_violation,
            hard_limits[..., 0] - q_des,
            torch.where(upper_violation, q_des - hard_limits[..., 1], torch.zeros_like(q_des)),
        )
        first_rejected = active & candidate_invalid
        for env_id in range(2):
            if bool(first_rejected[env_id].item()):
                first_rejections[env_id] = {
                    "iteration": step,
                    "q_des_arm_j1_to_j6_rad": [_json_float(item) for item in q_des[env_id].tolist()],
                    "hard_limit_lower_violation_mask_arm_j1_to_j6": [
                        bool(item) for item in lower_violation[env_id].tolist()
                    ],
                    "hard_limit_upper_violation_mask_arm_j1_to_j6": [
                        bool(item) for item in upper_violation[env_id].tolist()
                    ],
                    "hard_limit_overshoot_rad_arm_j1_to_j6": [
                        _json_float(item) for item in violation_overshoot[env_id].tolist()
                    ],
                }
        invalid_limit |= active & candidate_invalid
        accepted = active & ~candidate_invalid
        last_q_des = torch.where(accepted[:, None], q_des, last_q_des)
        joint_target = robot.data.joint_pos.clone()
        joint_target[:, arm_ids] = torch.where(accepted[:, None], q_des, q_current)
        robot.set_joint_position_target(joint_target)
        robot.write_joint_state_to_sim(joint_target, torch.zeros_like(robot.data.joint_vel))
        scene.write_data_to_sim()
        sim.forward()
        scene.update(sim.get_physics_dt())
        active &= ~candidate_invalid
        if not bool(torch.any(active).item()):
            break

    frames = scene.sensors["piper_downpress_frames"].data
    source_pos_w = frames.source_pos_w
    source_quat_w = frames.source_quat_w
    target_pos_w = frames.target_pos_w[:, 0, :]
    target_quat_w = frames.target_quat_w[:, 0, :]
    _finite("final_source_pos_w", source_pos_w, (2, 3), torch)
    _finite("final_source_quat_w", source_quat_w, (2, 4), torch)
    _finite("final_target_pos_w", target_pos_w, (2, 3), torch)
    _finite("final_target_quat_w", target_quat_w, (2, 4), torch)
    q_final = robot.data.joint_pos[:, arm_ids]
    hard_limits = robot.data.joint_pos_limits[:, arm_ids]
    _finite("final_q", q_final, (2, 6), torch)
    q_readback_max_abs_error = torch.max(torch.abs(q_final - last_q_des), dim=-1).values
    _finite("q_readback_max_abs_error", q_readback_max_abs_error, (2,), torch)
    if not bool(torch.all(q_readback_max_abs_error <= JOINT_STATE_READBACK_TOLERANCE_RAD).item()):
        raise RuntimeError(
            "Wave K direct joint-state readback differs from requested in-limit DLS q_des: "
            f"requested={last_q_des.tolist()}, actual={q_final.tolist()}, "
            f"max_abs={q_readback_max_abs_error.tolist()}."
        )
    _finite("final_hard_limits", hard_limits, (2, 6, 2), torch)
    margins = torch.minimum(q_final - hard_limits[..., 0], hard_limits[..., 1] - q_final)
    _finite("final_joint_margins", margins, (2, 6), torch)
    position_error = torch.linalg.norm(source_pos_w - target_pos_w, dim=-1)
    orientation_error = torch.linalg.norm(axis_angle_from_quat(quat_mul(quat_inv(source_quat_w), target_quat_w)), dim=-1)
    _finite("final_position_error", position_error, (2,), torch)
    _finite("final_orientation_error", orientation_error, (2,), torch)
    reachable = (
        ~invalid_limit
        & (position_error <= POSITION_TOLERANCE_M)
        & (orientation_error <= ORIENTATION_TOLERANCE_RAD)
        & (torch.min(margins, dim=-1).values >= MIN_HARD_LIMIT_MARGIN_RAD)
    )
    return {
        "robot": robot,
        "arm_ids": arm_ids,
        "arm_names": arm_names,
        "jacobian_body_id": jacobian_body_id,
        "jacobian_joint_columns": jacobian_columns,
        "q_des": last_q_des.clone(),
        "q_final": q_final.clone(),
        "q_readback_max_abs_error": q_readback_max_abs_error.clone(),
        "hard_limits": hard_limits.clone(),
        "margins": margins.clone(),
        "source_pos_w": source_pos_w.clone(),
        "source_quat_w": source_quat_w.clone(),
        "target_pos_w": target_pos_w.clone(),
        "target_quat_w": target_quat_w.clone(),
        "position_error": position_error.clone(),
        "orientation_error": orientation_error.clone(),
        "reachable": reachable.clone(),
        "invalid_limit": invalid_limit.clone(),
        "first_rejections": first_rejections,
        "condition_max": condition_max.clone(),
    }


def _typed_outcome(result, torch) -> str:
    reachable = result["reachable"]
    margins = result["margins"]
    q_final = result["q_final"]
    if not bool(torch.all(reachable).item()):
        raise RuntimeError("Wave K typed outcome requires a bilaterally reachable selected Stage3 anchor pair.")
    margin_gap = torch.abs(margins[0] - margins[1])
    max_gap, joint_index = torch.max(margin_gap, dim=0)
    if float(max_gap.item()) > JOINT_MARGIN_ASYMMETRY_RAD:
        return f"BILATERAL_ASYMMETRIC_AT_{ARM_NAMES[int(joint_index.item())]}"
    j6_travel = torch.abs(q_final[:, 5] - ACTION_DEFAULT_ARM_Q[5])
    if float(torch.abs(j6_travel[0] - j6_travel[1]).item()) > J6_TRAVEL_ASYMMETRY_RAD:
        return "BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET"
    return "BILATERAL_KINEMATICALLY_SYMMETRIC"


def _read_root_offsets(scene, expected_offsets, torch):
    from isaaclab.utils.math import subtract_frame_transforms

    robot = scene["robot"]
    door = scene["door"]
    root_offset_local, _ = subtract_frame_transforms(
        door.data.root_pos_w,
        door.data.root_quat_w,
        robot.data.root_pos_w,
        robot.data.root_quat_w,
    )
    _finite("door_to_robot_root_local_offset", root_offset_local, (2, 3), torch)
    if not bool(torch.allclose(root_offset_local, expected_offsets, rtol=0.0, atol=ROOT_OFFSET_READBACK_TOLERANCE_M)):
        raise RuntimeError(
            "Wave K robot root is not at the requested Stage3 door-local offset: "
            f"got {root_offset_local.tolist()}, expected {expected_offsets.tolist()}."
        )
    return root_offset_local.clone()


def _candidate_summary(candidate_id: str, expected_offsets, root_offsets, result, torch) -> dict[str, object]:
    default_q = torch.tensor(ACTION_DEFAULT_ARM_Q, device=result["q_final"].device, dtype=result["q_final"].dtype)
    action_vector = (result["q_final"] - default_q) / ACTION_SCALE
    return {
        "candidate_id": candidate_id,
        "expected_door_local_root_offsets_xyz_m": [
            [_json_float(item) for item in expected_offsets[env_id].tolist()] for env_id in range(2)
        ],
        "readback_door_local_root_offsets_xyz_m": [
            [_json_float(item) for item in root_offsets[env_id].tolist()] for env_id in range(2)
        ],
        "sides": {
            side_name: {
                "reachable": bool(result["reachable"][env_id].item()),
                "ik_invalid_due_to_hard_limit": bool(result["invalid_limit"][env_id].item()),
                "first_hard_limit_rejection": result["first_rejections"][env_id],
                "tcp_position_error_m": _json_float(result["position_error"][env_id].item()),
                "downpress_orientation_error_rad": _json_float(result["orientation_error"][env_id].item()),
                "minimum_hard_limit_margin_rad": _json_float(torch.min(result["margins"][env_id]).item()),
                "arm_j4_relative_default_travel_rad": _json_float(
                    (result["q_final"][env_id, 3] - ACTION_DEFAULT_ARM_Q[3]).item()
                ),
                "arm_j6_relative_default_travel_rad": _json_float(
                    (result["q_final"][env_id, 5] - ACTION_DEFAULT_ARM_Q[5]).item()
                ),
                "holding_action_vector_norm": _json_float(torch.linalg.norm(action_vector[env_id]).item()),
                "ik_requested_q_arm_j1_to_j6_rad": [_json_float(item) for item in result["q_des"][env_id].tolist()],
                "joint_state_readback_arm_j1_to_j6_rad": [
                    _json_float(item) for item in result["q_final"][env_id].tolist()
                ],
                "joint_state_readback_max_abs_error_rad": _json_float(
                    result["q_readback_max_abs_error"][env_id].item()
                ),
                "tcp_source_position_world_m": [
                    _json_float(item) for item in result["source_pos_w"][env_id].tolist()
                ],
                "tcp_source_orientation_world_wxyz": [
                    _json_float(item) for item in result["source_quat_w"][env_id].tolist()
                ],
                "tcp_target_position_world_m": [
                    _json_float(item) for item in result["target_pos_w"][env_id].tolist()
                ],
                "tcp_target_orientation_world_wxyz": [
                    _json_float(item) for item in result["target_quat_w"][env_id].tolist()
                ],
            }
            for env_id, side_name in enumerate(SIDE_NAMES)
        },
    }


def _candidate_score(result) -> tuple[float, float, float, float]:
    normalized_position_error = float(result["position_error"].max().item()) / POSITION_TOLERANCE_M
    normalized_orientation_error = float(result["orientation_error"].max().item()) / ORIENTATION_TOLERANCE_RAD
    return (
        max(normalized_position_error, normalized_orientation_error),
        normalized_position_error,
        normalized_orientation_error,
        -float(result["margins"].min().item()),
    )


def _attach_candidate_handle_axis_measurements(candidates, axis_frames, torch) -> None:
    if len(axis_frames) != 2:
        raise RuntimeError("Wave K handle-axis frame count must equal two sides.")
    for candidate in candidates:
        for env_id, side_name in enumerate(SIDE_NAMES):
            axis = axis_frames[env_id]["axis_world_unit"].to(dtype=candidate["result"]["source_pos_w"].dtype)
            origin = axis_frames[env_id]["axis_origin_world_m"].to(dtype=candidate["result"]["source_pos_w"].dtype)
            contact = candidate["result"]["source_pos_w"][env_id]
            radius = contact - origin
            lever_arm = torch.linalg.norm(radius - torch.dot(radius, axis) * axis)
            if not bool(torch.isfinite(lever_arm).item()):
                raise RuntimeError(f"Wave K {side_name} candidate handle-axis lever arm is non-finite.")
            candidate["record"]["sides"][side_name]["handle_axis_to_gripper_contact_lever_arm_m"] = _json_float(
                lever_arm.item()
            )


def _directional_first_rejection_outcome(candidates) -> str | None:
    common_rejected_joints = set(range(len(ARM_NAMES)))
    for candidate in candidates:
        left = candidate["result"]
        if not bool(left["reachable"][0].item()) or bool(left["invalid_limit"][0].item()):
            return None
        rejection = left["first_rejections"][1]
        if rejection is None:
            return None
        rejected_joints = {
            joint_index
            for joint_index, (lower, upper) in enumerate(
                zip(
                    rejection["hard_limit_lower_violation_mask_arm_j1_to_j6"],
                    rejection["hard_limit_upper_violation_mask_arm_j1_to_j6"],
                    strict=True,
                )
            )
            if lower or upper
        }
        if not rejected_joints:
            raise RuntimeError("Wave K first-rejection record has no violating joint.")
        common_rejected_joints &= rejected_joints
    if len(common_rejected_joints) != 1:
        return None
    joint_index = common_rejected_joints.pop()
    return f"BILATERAL_ASYMMETRIC_AT_{ARM_NAMES[joint_index]}"


def run(args: argparse.Namespace) -> dict[str, object]:
    if args.device != "cuda:0":
        raise ValueError("Wave K requires process-local --device cuda:0 under GPU0 sole visibility.")
    if args.output.exists():
        raise FileExistsError(f"Wave K refuses to overwrite existing evidence: {args.output}")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "0":
        raise RuntimeError("Wave K requires CUDA_VISIBLE_DEVICES=0 for physical GPU0 sole visibility.")
    if not (ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd").is_file():
        raise FileNotFoundError("Wave K A2+PiPER USD is missing.")
    trace_path = args.output.with_name("kinematics_attempt16_phase_trace.jsonl")
    exception_path = args.output.with_name("kinematics_attempt16_exception.txt")
    if trace_path.exists():
        raise FileExistsError(f"Wave K refuses to overwrite phase trace: {trace_path}")
    if exception_path.exists():
        raise FileExistsError(f"Wave K refuses to overwrite exception record: {exception_path}")

    def trace(event: str) -> None:
        with trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": event}) + "\n")

    trace("before_simulation_app")
    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True, "fast_shutdown": True})
    trace("simulation_app_ready")
    sim = None
    scene = None
    succeeded = False
    try:
        sim, scene, torch = _make_scene(args)
        trace("scene_ready")
        sim.reset()
        trace("simulation_reset")
        scan_seed_pair = _mirror_matched_scan_seed_pair(
            torch,
            scene["robot"].device,
            scene["robot"].data.joint_pos.dtype,
        )
        candidates = []
        for root_x in STAGE3_GRID_X_M:
            for lateral_magnitude in STAGE3_GRID_LATERAL_MAGNITUDE_M:
                candidate_id = f"stage3_x_{root_x:+.3f}_abs_y_{lateral_magnitude:.3f}"
                expected_root_offsets = torch.tensor(
                    ((root_x, lateral_magnitude, STAGE3_GRID_Z_M), (root_x, -lateral_magnitude, STAGE3_GRID_Z_M)),
                    device=scene["robot"].device,
                    dtype=scene["robot"].data.joint_pos.dtype,
                )
                candidate_result = _run_pose_scan(sim, scene, expected_root_offsets, scan_seed_pair, torch)
                candidate_root_offsets = _read_root_offsets(scene, expected_root_offsets, torch)
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "expected_root_offsets": expected_root_offsets,
                        "root_offsets": candidate_root_offsets,
                        "result": candidate_result,
                        "record": _candidate_summary(
                            candidate_id,
                            expected_root_offsets,
                            candidate_root_offsets,
                            candidate_result,
                            torch,
                        ),
                    }
                )
        trace("pose_scan_complete")
        axis_frames = _read_handle_joint_frames(torch)
        _attach_candidate_handle_axis_measurements(candidates, axis_frames, torch)
        reachable_candidates = [
            candidate for candidate in candidates if bool(torch.all(candidate["result"]["reachable"]).item())
        ]
        candidate_records = [candidate["record"] for candidate in candidates]
        if not reachable_candidates:
            directional_outcome = _directional_first_rejection_outcome(candidates)
            failure_path = args.output.with_name("k_kinematics_no_bilateral_candidate_evidence.json")
            if failure_path.exists():
                raise FileExistsError(f"Wave K refuses to overwrite Stage3-grid failure evidence: {failure_path}")
            failure_path.write_text(
                json.dumps(
                    {
                        "schema": "a2_piper_base_v26_4_wave_k_no_bilateral_candidate_failure_v1",
                        "status": "NO_BILATERAL_CANDIDATE",
                        "typed_outcome": directional_outcome or "NOT_ADMITTED",
                        "anchor_provenance": STAGE3_ANCHOR_PROVENANCE,
                        "candidates": candidate_records,
                    },
                    indent=2,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
            if directional_outcome is not None:
                receipt = {
                    "schema": "a2_piper_base_v26_4_wave_k_directional_hard_limit_v1",
                    "status": "RUNTIME_COMPLETE_DIRECTIONAL_HARD_LIMIT_ASYMMETRY",
                    "typed_outcome": directional_outcome,
                    "anchor_provenance": STAGE3_ANCHOR_PROVENANCE,
                    "protocol": {
                        "directional_rule": (
                            "all frozen candidates require LEFT reachable without hard-limit rejection and RIGHT first "
                            "rejection to share exactly one violating arm joint"
                        ),
                        "scripted_scan_anchor_side": "LEFT",
                        "scripted_scan_anchor_seed_arm_j1_to_j6_rad": list(SCAN_SEED_ANCHOR_ARM_Q),
                        "scripted_scan_mirror_mask_arm_j1_to_j6": list(SAGITTAL_MIRROR_SIGNS_ARM_J1_TO_J6),
                        "right_seed_equals_mask_times_left_seed": True,
                    },
                    "candidates": candidate_records,
                    "failure_evidence_path": str(failure_path),
                }
                args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                trace("directional_receipt_written")
                succeeded = True
                return receipt
            raise RuntimeError(
                "Wave K Stage3 matched-pair grid has no bilaterally reachable candidate (NOT_ADMITTED); "
                f"preserved evidence at {failure_path}."
            )
        selected = min(reachable_candidates, key=lambda candidate: _candidate_score(candidate["result"]))
        selected_candidate_id = selected["candidate_id"]
        selected_candidate_score = _candidate_score(selected["result"])
        result = selected["result"]
        root_offset_local = selected["root_offsets"]
        trace("root_offset_verified")
        door_joint_ids, door_joint_names = scene["door"].find_joints(
            [".*hinge.*", ".*handle.*"], preserve_order=True
        )
        if len(door_joint_ids) != 2:
            raise RuntimeError(f"Wave K requires exactly hinge and handle joints; got {door_joint_names}.")
        door_joint_pos = scene["door"].data.joint_pos[:, door_joint_ids]
        door_joint_vel = scene["door"].data.joint_vel[:, door_joint_ids]
        _finite("door_joint_position", door_joint_pos, (2, 2), torch)
        _finite("door_joint_velocity", door_joint_vel, (2, 2), torch)
        default_q = torch.tensor(ACTION_DEFAULT_ARM_Q, device=result["q_final"].device, dtype=result["q_final"].dtype)
        action_vector = (result["q_final"] - default_q) / ACTION_SCALE
        _finite("holding_action_vector", action_vector, (2, 6), torch)
        outcome = _typed_outcome(result, torch)
        sides = {}
        for env_id, side_name in enumerate(SIDE_NAMES):
            axis = axis_frames[env_id]["axis_world_unit"].to(dtype=result["source_pos_w"].dtype)
            origin = axis_frames[env_id]["axis_origin_world_m"].to(dtype=result["source_pos_w"].dtype)
            contact = result["source_pos_w"][env_id]
            radius = contact - origin
            lever_vector = radius - torch.dot(radius, axis) * axis
            lever_arm = torch.linalg.norm(lever_vector)
            if not bool(torch.isfinite(lever_arm).item()):
                raise RuntimeError(f"Wave K {side_name} handle-axis lever arm is non-finite.")
            joint_values = {}
            for index, joint_name in enumerate(ARM_NAMES):
                joint_values[joint_name] = {
                    "q_rad": _json_float(result["q_final"][env_id, index].item()),
                    "hard_limit_rad": [
                        _json_float(result["hard_limits"][env_id, index, 0].item()),
                        _json_float(result["hard_limits"][env_id, index, 1].item()),
                    ],
                    "hard_limit_margin_rad": _json_float(result["margins"][env_id, index].item()),
                }
            sides[side_name] = {
                "env_id": env_id,
                "door_open_lr": 1 if side_name == "LEFT" else -1,
                "door_to_robot_root_local_offset_xyz_m": [
                    _json_float(item) for item in root_offset_local[env_id].tolist()
                ],
                "door_joint_zero_state_readback": {
                    joint_name: {
                        "q_rad": _json_float(door_joint_pos[env_id, joint_index].item()),
                        "qdot_rad_s": _json_float(door_joint_vel[env_id, joint_index].item()),
                    }
                    for joint_index, joint_name in enumerate(door_joint_names)
                },
                "reachable": bool(result["reachable"][env_id].item()),
                "ik_invalid_due_to_hard_limit": bool(result["invalid_limit"][env_id].item()),
                "tcp_target_position_world_m": [_json_float(item) for item in result["target_pos_w"][env_id].tolist()],
                "tcp_final_position_world_m": [_json_float(item) for item in result["source_pos_w"][env_id].tolist()],
                "tcp_target_orientation_world_wxyz": [
                    _json_float(item) for item in result["target_quat_w"][env_id].tolist()
                ],
                "tcp_final_orientation_world_wxyz": [
                    _json_float(item) for item in result["source_quat_w"][env_id].tolist()
                ],
                "tcp_position_error_m": _json_float(result["position_error"][env_id].item()),
                "downpress_orientation_error_rad": _json_float(result["orientation_error"][env_id].item()),
                "max_jacobian_condition_number": _json_float(result["condition_max"][env_id].item()),
                "joint_limits": joint_values,
                "minimum_hard_limit_margin_rad": _json_float(torch.min(result["margins"][env_id]).item()),
                "arm_j6_relative_default_travel_rad": _json_float(
                    (result["q_final"][env_id, 5] - ACTION_DEFAULT_ARM_Q[5]).item()
                ),
                "arm_j6_absolute_relative_default_travel_rad": _json_float(
                    torch.abs(result["q_final"][env_id, 5] - ACTION_DEFAULT_ARM_Q[5]).item()
                ),
                "arm_j4_relative_default_travel_rad": _json_float(
                    (result["q_final"][env_id, 3] - ACTION_DEFAULT_ARM_Q[3]).item()
                ),
                "ik_requested_q_arm_j1_to_j6_rad": [_json_float(item) for item in result["q_des"][env_id].tolist()],
                "joint_state_readback_arm_j1_to_j6_rad": [
                    _json_float(item) for item in result["q_final"][env_id].tolist()
                ],
                "joint_state_readback_max_abs_error_rad": _json_float(
                    result["q_readback_max_abs_error"][env_id].item()
                ),
                "holding_action_vector_arm_j1_to_j6": [_json_float(item) for item in action_vector[env_id].tolist()],
                "holding_action_vector_norm": _json_float(torch.linalg.norm(action_vector[env_id]).item()),
                "handle_joint": {
                    "path": axis_frames[env_id]["joint_path"],
                    "local_pos0_m": axis_frames[env_id]["local_pos0_m"],
                    "local_rot0_wxyz": axis_frames[env_id]["local_rot0_wxyz"],
                    "axis_origin_world_m": [_json_float(item) for item in origin.tolist()],
                    "axis_world_unit": [_json_float(item) for item in axis.tolist()],
                    "gripper_contact_world_m": [_json_float(item) for item in contact.tolist()],
                    "axis_to_gripper_contact_lever_arm_m": _json_float(lever_arm.item()),
                },
            }
        receipt = {
            "schema": "a2_piper_base_v26_4_wave_k_kinematics_v1",
            "status": "RUNTIME_COMPLETE",
            "typed_outcome": outcome,
            "source": {
                "repo_head": os.popen("git -C /home/baoquanc/workspace/DoorDog-A2_Piper rev-parse HEAD").read().strip(),
                "robot_usd": str(ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd"),
                "fixture_constructor": "scriptsFORhuman/v26_2/v26_2_u_probe_current_fixture.py::door_cfg",
                "ik_path": "IsaacLab DifferentialIKController DLS + FrameTransformer + A2 TCP Jacobian offset",
            },
            "runtime": {
                "command": " ".join(sys.argv),
                "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
                "process_device": args.device,
                "num_envs": 2,
                "ik_steps": IK_STEPS,
            },
            "fixture": FIXTURE,
            "protocol": {
                "stage3_anchor_provenance": STAGE3_ANCHOR_PROVENANCE,
                "stage3_matched_pair_grid": {
                    "x_m": list(STAGE3_GRID_X_M),
                    "abs_y_m": list(STAGE3_GRID_LATERAL_MAGNITUDE_M),
                    "z_m": STAGE3_GRID_Z_M,
                    "yaw_rad": STAGE3_GRID_YAW_RAD,
                    "left_y_sign": "+",
                    "right_y_sign": "-",
                },
                "selected_candidate_id": selected_candidate_id,
                "selected_candidate_score": list(selected_candidate_score),
                "selected_candidate_rule": (
                    "bilaterally reachable only; then minimize max of normalized position/orientation error; "
                    "then normalized position, normalized orientation, and maximize minimum hard-limit margin"
                ),
                "door_to_robot_root_readback_tolerance_m": ROOT_OFFSET_READBACK_TOLERANCE_M,
                "action_default_arm_j1_to_j6_rad": list(ACTION_DEFAULT_ARM_Q),
                "scripted_scan_anchor_side": "LEFT",
                "scripted_scan_anchor_seed_arm_j1_to_j6_rad": list(SCAN_SEED_ANCHOR_ARM_Q),
                "scripted_scan_mirror_mask_arm_j1_to_j6": list(SAGITTAL_MIRROR_SIGNS_ARM_J1_TO_J6),
                "scripted_scan_seed_by_side_arm_j1_to_j6_rad": {
                    side_name: [_json_float(item) for item in scan_seed_pair[env_id].tolist()]
                    for env_id, side_name in enumerate(SIDE_NAMES)
                },
                "scripted_scan_other_seed_equals_mask_times_anchor_seed": True,
                "action_scale": ACTION_SCALE,
                "tcp_offset_z_m": TCP_OFFSET_Z_M,
                "robot_gravity": "disabled for fixed-root static kinematics scan",
                "joint_state_application": (
                    "accepted in-limit DLS q_des is set as matching position target, then written as static joint "
                    "state with zero velocity; scene.write_data_to_sim -> sim.forward -> scene.update refreshes frames; "
                    "no simulation step or dynamic settle is used"
                ),
                "joint_state_readback_tolerance_rad": JOINT_STATE_READBACK_TOLERANCE_RAD,
                "fixed_base_jacobian": {
                    "body_index": result["jacobian_body_id"],
                    "joint_columns": result["jacobian_joint_columns"],
                },
                "downpress_target_frame_offset_quat_wxyz": [0.5, 0.5, 0.5, 0.5],
                "reachability_thresholds": {
                    "position_error_m_lte": POSITION_TOLERANCE_M,
                    "orientation_error_rad_lte": ORIENTATION_TOLERANCE_RAD,
                    "hard_limit_margin_rad_gte": MIN_HARD_LIMIT_MARGIN_RAD,
                },
                "outcome_thresholds": {
                    "joint_margin_asymmetry_rad_gt": JOINT_MARGIN_ASYMMETRY_RAD,
                    "arm_j6_absolute_travel_asymmetry_rad_gt": J6_TRAVEL_ASYMMETRY_RAD,
                },
                "right_handle_localrot0_rule": "door_open_lr == -1 requires handle_joint LocalRot0 Z-axis 180-degree rotation",
                "anchor_side": "LEFT (door_open_lr=+1); RIGHT (door_open_lr=-1) is compared without canonicalization.",
                "static_fk_sagittal_mirror_signs_arm_j1_to_j6": list(SAGITTAL_MIRROR_SIGNS_ARM_J1_TO_J6),
                "action_default_handed_components": ["arm_j4", "arm_j6"],
                "door_generalized_joint_convention": "hinge/handle q and qdot are read in each side's authored LocalRot0 frame; the zero-state readback is retained per side.",
            },
            "candidates": candidate_records,
            "sides": sides,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        trace("before_receipt_write")
        args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        trace("receipt_written")
        succeeded = True
        return receipt
    except BaseException:
        exception_path.write_text(traceback.format_exc(), encoding="utf-8")
        trace("exception_recorded")
        raise
    finally:
        trace("cleanup")
        if succeeded:
            app.close()
        elif sim is not None:
            sim.clear_all_callbacks()
            sim.clear_instance()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, allow_nan=False))
