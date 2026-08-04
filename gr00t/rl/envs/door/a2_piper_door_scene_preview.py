# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import gc
import json
import math
from pathlib import Path

import torch

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
from isaaclab.sensors import ContactSensorCfg, FrameTransformerCfg, TiledCameraCfg, save_images_to_file
from isaaclab.sensors.frame_transformer import OffsetCfg
from isaaclab.sim import SimulationContext
from isaaclab.utils import configclass

from gr00t.rl.data.tasks.door.scenario_cfg.isaacsim import TaskObjCfgDict

# These constants intentionally mirror gr00t/rl/config/robot/A2_Piper/a2_piper.yaml.
# Keeping them local avoids pulling YAML/Hydra parsing into the Isaac Sim preview startup path.
A2_PIPER_DOF_NAMES = [
    "FL_hip_joint",
    "FL_thigh_joint",
    "FL_calf_joint",
    "RL_hip_joint",
    "RL_thigh_joint",
    "RL_calf_joint",
    "FR_hip_joint",
    "FR_thigh_joint",
    "FR_calf_joint",
    "RR_hip_joint",
    "RR_thigh_joint",
    "RR_calf_joint",
    "arm_j1",
    "arm_j2",
    "arm_j3",
    "arm_j4",
    "arm_j5",
    "arm_j6",
    "arm_j7",
    "arm_j8",
]

A2_PIPER_DEFAULT_JOINT_POS = {
    "FL_hip_joint": 0.0,
    "FL_thigh_joint": 0.5,
    "FL_calf_joint": -1.0,
    "RL_hip_joint": 0.0,
    "RL_thigh_joint": 0.5,
    "RL_calf_joint": -1.0,
    "FR_hip_joint": 0.0,
    "FR_thigh_joint": 0.5,
    "FR_calf_joint": -1.0,
    "RR_hip_joint": 0.0,
    "RR_thigh_joint": 0.5,
    "RR_calf_joint": -1.0,
    "arm_j1": 0.0,
    "arm_j2": 1.48,
    "arm_j3": -0.63,
    "arm_j4": -0.84,
    "arm_j5": 0.0,
    "arm_j6": 1.57,
    "arm_j7": 0.0,
    "arm_j8": 0.0,
}

A2_PIPER_EFFORT_LIMITS = {
    "FL_hip_joint": 120.0,
    "FL_thigh_joint": 120.0,
    "FL_calf_joint": 180.0,
    "RL_hip_joint": 120.0,
    "RL_thigh_joint": 120.0,
    "RL_calf_joint": 180.0,
    "FR_hip_joint": 120.0,
    "FR_thigh_joint": 120.0,
    "FR_calf_joint": 180.0,
    "RR_hip_joint": 120.0,
    "RR_thigh_joint": 120.0,
    "RR_calf_joint": 180.0,
    "arm_j1": 100.0,
    "arm_j2": 100.0,
    "arm_j3": 100.0,
    "arm_j4": 100.0,
    "arm_j5": 100.0,
    "arm_j6": 100.0,
    "arm_j7": 10.0,
    "arm_j8": 10.0,
}

A2_PIPER_VELOCITY_LIMITS = {
    "FL_hip_joint": 22.0,
    "FL_thigh_joint": 22.0,
    "FL_calf_joint": 14.6667,
    "RL_hip_joint": 22.0,
    "RL_thigh_joint": 22.0,
    "RL_calf_joint": 14.6667,
    "FR_hip_joint": 22.0,
    "FR_thigh_joint": 22.0,
    "FR_calf_joint": 14.6667,
    "RR_hip_joint": 22.0,
    "RR_thigh_joint": 22.0,
    "RR_calf_joint": 14.6667,
    "arm_j1": 5.0,
    "arm_j2": 5.0,
    "arm_j3": 5.0,
    "arm_j4": 5.0,
    "arm_j5": 5.0,
    "arm_j6": 3.0,
    "arm_j7": 1.0,
    "arm_j8": 1.0,
}

A2_PIPER_HIP_JOINT_NAMES = [
    "FL_hip_joint",
    "FR_hip_joint",
    "RL_hip_joint",
    "RR_hip_joint",
]
A2_PIPER_THIGH_JOINT_NAMES = [
    "FL_thigh_joint",
    "FR_thigh_joint",
    "RL_thigh_joint",
    "RR_thigh_joint",
]
A2_PIPER_CALF_JOINT_NAMES = [
    "FL_calf_joint",
    "FR_calf_joint",
    "RL_calf_joint",
    "RR_calf_joint",
]
A2_PIPER_ARM_JOINT_NAMES = ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"]
A2_PIPER_GRIPPER_JOINT_NAMES = ["arm_j7", "arm_j8"]

PULL_GEOMETRY_PROOF_DIRECTIONS = ("out", "in")
PULL_GEOMETRY_PROOF_ROBOT_BODY_NAMES = (
    "trunk",
    "FL_hip",
    "FL_thigh",
    "FL_calf",
    "RL_hip",
    "RL_thigh",
    "RL_calf",
    "FR_hip",
    "FR_thigh",
    "FR_calf",
    "RR_hip",
    "RR_thigh",
    "RR_calf",
    "arm_body0",
    "arm_body1",
    "arm_body2",
    "arm_body3",
    "arm_body4",
    "arm_body5",
    "arm_body6",
    "arm_body6_to_gripper",
    "arm_body7",
    "arm_body8",
)
PULL_GEOMETRY_PROOF_TARGET_QUATERNIONS = {
    "inherited": (0.5, 0.5, 0.5, 0.5),
    "io_z_pre": (-0.5, -0.5, 0.5, 0.5),
    "io_z_post": (-0.5, 0.5, -0.5, 0.5),
}
PULL_GEOMETRY_PROOF_ASSET_VALUES = {
    "rand_door_width": 0.95,
    "rand_door_height": 2.05,
    "rand_door_handle_height": 0.95,
    "rand_door_handle_width": 0.115,
    "rand_door_weight": 120.0,
    "rand_door_handle_type": "lever",
    "rand_door_open_lr": "right",
    "rand_total_wall_height": 2.7,
    "rand_axle_length": 0.195,
    "rand_handle_length": 0.125,
    "rand_hook_length": 0.05,
    "rand_handle_radius": 0.013,
    "rand_spawn_hook": False,
    "rand_hinge_drive_max_force": 7.25,
    "rand_hinge_drive_stiffness": 5.5,
    "rand_handle_drive_max_force": 2.0,
}


def yaw_to_wxyz(yaw: float) -> tuple[float, float, float, float]:
    half_yaw = 0.5 * yaw
    return (math.cos(half_yaw), 0.0, 0.0, math.sin(half_yaw))


# Mirrors the current Doorman stage-0 robot root reset hardcode in
# gr00t/rl/envs/door/door_open_a2_base.py::_reset_root_states. Keep this local to
# avoid importing HOMIE/G1/hand task code into the A2_Piper preview path.
DOORMAN_STAGE0_ROOT_X_BOUNDS = (-1.5, -0.6)
DOORMAN_STAGE0_ROOT_Y_BOUNDS = (-0.5, 0.5)
DOORMAN_STAGE0_ROOT_YAW_BOUNDS = (-math.pi / 4.0, math.pi / 4.0)


def build_corner_root_poses(
    *,
    bounds_mode: str,
    center_x: float,
    center_y: float,
    center_z: float,
    center_yaw: float,
    x_half_range: float,
    y_half_range: float,
    yaw_half_range: float,
    yaw_mode: str,
) -> list[tuple[float, float, float, float]]:
    if bounds_mode == "doorman-stage0":
        x_min, x_max = DOORMAN_STAGE0_ROOT_X_BOUNDS
        y_min, y_max = DOORMAN_STAGE0_ROOT_Y_BOUNDS
        yaw_min, yaw_max = DOORMAN_STAGE0_ROOT_YAW_BOUNDS
    elif bounds_mode == "root-centered":
        x_min = center_x - x_half_range
        x_max = center_x + x_half_range
        y_min = center_y - y_half_range
        y_max = center_y + y_half_range
        yaw_min = center_yaw - yaw_half_range
        yaw_max = center_yaw + yaw_half_range
    else:
        raise ValueError(f"Unsupported placement bounds mode: {bounds_mode}")

    if yaw_mode == "bounds":
        yaws = (yaw_min, yaw_min, yaw_max, yaw_max)
    elif yaw_mode == "uniform":
        yaws = (center_yaw, center_yaw, center_yaw, center_yaw)
    else:
        raise ValueError(f"Unsupported placement corner yaw mode: {yaw_mode}")

    return [
        (x_min, y_min, center_z, yaws[0]),
        (x_max, y_min, center_z, yaws[1]),
        (x_min, y_max, center_z, yaws[2]),
        (x_max, y_max, center_z, yaws[3]),
    ]


def build_a2_piper_robot_cfg(
    usd_path: str | Path,
    root_x: float = -0.9,
    root_y: float = 0.0,
    root_z: float = 0.55,
    root_yaw: float = 0.0,
) -> ArticulationCfg:
    usd_path = Path(usd_path)
    if not usd_path.is_file():
        raise FileNotFoundError(f"A2_Piper USD not found: {usd_path}")

    return ArticulationCfg(
        spawn=sim_utils.UsdFileCfg(
            usd_path=str(usd_path.resolve()),
            activate_contact_sensors=False,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                rigid_body_enabled=True,
                disable_gravity=False,
                retain_accelerations=False,
                linear_damping=0.0,
                angular_damping=0.0,
                max_linear_velocity=1000.0,
                max_angular_velocity=1000.0,
                max_depenetration_velocity=300.0,
            ),
            articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                enabled_self_collisions=True,
                solver_position_iteration_count=4,
                solver_velocity_iteration_count=0,
                sleep_threshold=0.005,
                stabilization_threshold=0.001,
                articulation_enabled=True,
            ),
        ),
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(root_x, root_y, root_z),
            rot=yaw_to_wxyz(root_yaw),
            joint_pos=A2_PIPER_DEFAULT_JOINT_POS,
            joint_vel={".*": 0.0},
        ),
        soft_joint_pos_limit_factor=0.9,
        actuators={
            "hips": ImplicitActuatorCfg(
                joint_names_expr=A2_PIPER_HIP_JOINT_NAMES,
                effort_limit_sim=120.0,
                velocity_limit_sim=22.0,
                stiffness=140.0,
                damping=4.5,
                armature=0.03,
                friction=0.0,
            ),
            "thighs": ImplicitActuatorCfg(
                joint_names_expr=A2_PIPER_THIGH_JOINT_NAMES,
                effort_limit_sim=120.0,
                velocity_limit_sim=22.0,
                stiffness=140.0,
                damping=4.5,
                armature=0.03,
                friction=0.0,
            ),
            "calfs": ImplicitActuatorCfg(
                joint_names_expr=A2_PIPER_CALF_JOINT_NAMES,
                effort_limit_sim=180.0,
                velocity_limit_sim=14.6667,
                stiffness=220.0,
                damping=9.0,
                armature=0.03,
                friction=0.0,
            ),
            "arm": ImplicitActuatorCfg(
                joint_names_expr=A2_PIPER_ARM_JOINT_NAMES[:5],
                effort_limit_sim=100.0,
                velocity_limit_sim=5.0,
                stiffness=80.0,
                damping=4.0,
                armature=0.0,
                friction=0.0,
            ),
            "arm_wrist": ImplicitActuatorCfg(
                joint_names_expr=[A2_PIPER_ARM_JOINT_NAMES[5]],
                effort_limit_sim=100.0,
                velocity_limit_sim=3.0,
                stiffness=60.0,
                damping=3.0,
                armature=0.0,
                friction=0.0,
            ),
            "gripper_hold": ImplicitActuatorCfg(
                joint_names_expr=A2_PIPER_GRIPPER_JOINT_NAMES,
                effort_limit_sim=10.0,
                velocity_limit_sim=1.0,
                stiffness=40.0,
                damping=1.0,
                armature=0.0,
                friction=0.0,
            ),
        },
    )


def build_doorman_door_cfg(
    num_envs: int,
    *,
    door_open_ios: tuple[str, ...] | None = None,
    activate_contact_sensors: bool = False,
) -> ArticulationCfg:
    door_cfg = copy.deepcopy(TaskObjCfgDict["door"])
    if isinstance(door_cfg.spawn, sim_utils.MultiAssetSpawnerCfg):
        if door_open_ios is None:
            door_cfg.spawn.assets_cfg = door_cfg.spawn.assets_cfg[:num_envs]
        else:
            if tuple(door_open_ios) != PULL_GEOMETRY_PROOF_DIRECTIONS or num_envs != 2:
                raise ValueError(
                    "Paired pull geometry proof requires exactly door_open_ios=('out', 'in') "
                    f"and num_envs=2; got {door_open_ios!r}, num_envs={num_envs}."
                )
            source_asset_cfg = door_cfg.spawn.assets_cfg[0]
            paired_asset_cfgs = []
            for door_open_io in door_open_ios:
                asset_cfg = copy.deepcopy(source_asset_cfg)
                for field_name, value in PULL_GEOMETRY_PROOF_ASSET_VALUES.items():
                    setattr(asset_cfg, field_name, value)
                asset_cfg.rand_door_open_io = door_open_io
                asset_cfg.randomize_material = False
                asset_cfg.use_preloaded_materials = False
                paired_asset_cfgs.append(asset_cfg)
            door_cfg.spawn.assets_cfg = paired_asset_cfgs
            door_cfg.spawn.random_choice = False
        door_cfg.spawn.activate_contact_sensors = activate_contact_sensors
        for asset_cfg in door_cfg.spawn.assets_cfg:
            if hasattr(asset_cfg, "activate_contact_sensors"):
                asset_cfg.activate_contact_sensors = activate_contact_sensors
    return door_cfg


def _pull_geometry_frame_cfg() -> FrameTransformerCfg:
    target_frames = [
        FrameTransformerCfg.FrameCfg(
            prim_path="{ENV_REGEX_NS}/door/grasp_target",
            name="handle_inherited",
            offset=OffsetCfg(rot=PULL_GEOMETRY_PROOF_TARGET_QUATERNIONS["inherited"]),
        ),
        FrameTransformerCfg.FrameCfg(
            prim_path="{ENV_REGEX_NS}/door/grasp_target",
            name="pregrasp_out",
            offset=OffsetCfg(
                pos=(-0.10, 0.0, 0.0),
                rot=PULL_GEOMETRY_PROOF_TARGET_QUATERNIONS["inherited"],
            ),
        ),
        FrameTransformerCfg.FrameCfg(
            prim_path="{ENV_REGEX_NS}/door/grasp_target",
            name="pregrasp_in",
            offset=OffsetCfg(
                pos=(0.10, 0.0, 0.0),
                rot=PULL_GEOMETRY_PROOF_TARGET_QUATERNIONS["io_z_pre"],
            ),
        ),
        FrameTransformerCfg.FrameCfg(
            prim_path="{ENV_REGEX_NS}/door/grasp_target",
            name="handle_io_z_pre",
            offset=OffsetCfg(
                pos=(0.0, -0.08, 0.0),
                rot=PULL_GEOMETRY_PROOF_TARGET_QUATERNIONS["io_z_pre"],
            ),
        ),
        FrameTransformerCfg.FrameCfg(
            prim_path="{ENV_REGEX_NS}/door/grasp_target",
            name="handle_io_z_post",
            offset=OffsetCfg(
                pos=(0.0, 0.08, 0.0),
                rot=PULL_GEOMETRY_PROOF_TARGET_QUATERNIONS["io_z_post"],
            ),
        ),
    ]
    frame_cfg = FrameTransformerCfg(
        prim_path="{ENV_REGEX_NS}/Robot/arm_body6_to_gripper",
        source_frame_offset=OffsetCfg(pos=(0.0, 0.0, 0.085)),
        target_frames=target_frames,
        debug_vis=False,
    )
    frame_cfg.visualizer_cfg = frame_cfg.visualizer_cfg.replace(
        prim_path="/Visuals/PullGeometry/paired_target_tcp_frames"
    )
    frame_cfg.visualizer_cfg.markers["frame"].scale = (0.12, 0.12, 0.12)
    return frame_cfg


def build_preview_scene_cfg(
    *,
    num_envs: int,
    env_spacing: float,
    robot_cfg: ArticulationCfg,
    door_cfg: ArticulationCfg,
    enable_camera: bool,
    enable_pull_geometry_overlay: bool = False,
) -> InteractiveSceneCfg:
    camera_cfg = TiledCameraCfg(
        prim_path="{ENV_REGEX_NS}/preview_camera",
        offset=TiledCameraCfg.OffsetCfg(pos=(1.8, -1.6, 1.25), rot=(1.0, 0.0, 0.0, 0.0), convention="world"),
        data_types=["rgb"],
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=8.0,
            focus_distance=4.0,
            horizontal_aperture=20.0,
            clipping_range=(0.1, 20.0),
        ),
        width=1280,
        height=720,
        debug_vis=True,
    )

    @configclass
    class A2PiperDoorPreviewSceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane",
            spawn=sim_utils.GroundPlaneCfg(
                physics_material=sim_utils.RigidBodyMaterialCfg(
                    static_friction=1.0,
                    dynamic_friction=1.0,
                    restitution=0.0,
                )
            ),
        )
        dome_light = AssetBaseCfg(
            prim_path="/World/DomeLight",
            spawn=sim_utils.DomeLightCfg(intensity=2000.0, color=(0.98, 0.95, 0.88)),
        )
        robot: ArticulationCfg = robot_cfg.replace(prim_path="{ENV_REGEX_NS}/Robot")
        door: ArticulationCfg = door_cfg.replace(prim_path="{ENV_REGEX_NS}/door")

        if enable_camera:
            preview_camera = camera_cfg

        if enable_pull_geometry_overlay:
            pull_target_tcp_frames = _pull_geometry_frame_cfg()
            door_panel_robot_contact = ContactSensorCfg(
                prim_path="/World/envs/env_.*/door/door_panel",
                filter_prim_paths_expr=[
                    f"/World/envs/env_.*/Robot/{body_name}"
                    for body_name in PULL_GEOMETRY_PROOF_ROBOT_BODY_NAMES
                ],
                force_threshold=1.0,
            )

    return A2PiperDoorPreviewSceneCfg(
        num_envs=num_envs,
        env_spacing=env_spacing,
        replicate_physics=False,
    )


def reset_preview_scene(
    scene: InteractiveScene,
    robot_root_poses: list[tuple[float, float, float, float]] | None = None,
) -> None:
    robot: Articulation = scene["robot"]
    door: Articulation = scene["door"]

    robot_root_state = robot.data.default_root_state.clone()
    if robot_root_poses is not None:
        if len(robot_root_poses) != robot_root_state.shape[0]:
            raise ValueError(
                "robot_root_poses length must match scene num_envs: "
                f"{len(robot_root_poses)} != {robot_root_state.shape[0]}"
            )
        for env_id, (root_x, root_y, root_z, root_yaw) in enumerate(robot_root_poses):
            robot_root_state[env_id, 0:3] = torch.tensor(
                (root_x, root_y, root_z),
                dtype=robot_root_state.dtype,
                device=robot_root_state.device,
            )
            robot_root_state[env_id, 3:7] = torch.tensor(
                yaw_to_wxyz(root_yaw),
                dtype=robot_root_state.dtype,
                device=robot_root_state.device,
            )
    robot_root_state[:, :3] += scene.env_origins
    robot.write_root_pose_to_sim(robot_root_state[:, :7])
    robot.write_root_velocity_to_sim(robot_root_state[:, 7:])
    robot_joint_pos = robot.data.default_joint_pos.clone()
    robot_joint_vel = torch.zeros_like(robot.data.default_joint_vel)
    robot.write_joint_state_to_sim(robot_joint_pos, robot_joint_vel)
    robot.set_joint_position_target(robot_joint_pos)

    door_root_state = door.data.default_root_state.clone()
    door_root_state[:, :3] += scene.env_origins
    door.write_root_pose_to_sim(door_root_state[:, :7])
    door.write_root_velocity_to_sim(door_root_state[:, 7:])
    door_joint_pos = door.data.default_joint_pos.clone()
    door_joint_vel = torch.zeros_like(door.data.default_joint_vel)
    door.write_joint_state_to_sim(door_joint_pos, door_joint_vel)

    scene.reset()


def set_pull_geometry_camera_poses(scene: InteractiveScene) -> None:
    if scene.num_envs != 2 or "preview_camera" not in scene.sensors:
        raise RuntimeError("Paired pull geometry camera setup requires two envs and preview_camera.")
    camera = scene["preview_camera"]
    if not hasattr(camera._view, "_sync_usd_on_fabric_write"):
        raise RuntimeError("preview_camera view lacks USD/Fabric synchronization control.")
    camera._view._sync_usd_on_fabric_write = True
    view_offsets = torch.tensor(
        ((-2.0, -2.2, 1.45), (2.0, -2.2, 1.45)),
        dtype=scene.env_origins.dtype,
        device=scene.env_origins.device,
    )
    target_offsets = torch.tensor(
        ((0.0, -0.30, 0.95), (0.0, -0.30, 0.95)),
        dtype=scene.env_origins.dtype,
        device=scene.env_origins.device,
    )
    camera.set_world_poses_from_view(
        scene.env_origins + view_offsets,
        scene.env_origins + target_offsets,
    )


def quaternion_angular_distance(first: torch.Tensor, second: torch.Tensor) -> float:
    if first.shape != (4,) or second.shape != (4,):
        raise ValueError(
            "Quaternion angular distance requires two (4,) tensors; "
            f"got {tuple(first.shape)} and {tuple(second.shape)}."
        )
    dot = torch.abs(torch.dot(first, second))
    return float(2.0 * torch.acos(torch.clamp(dot, max=1.0)))


def run_zero_action_hold(
    sim: SimulationContext,
    scene: InteractiveScene,
    simulation_app,
    *,
    max_steps: int = -1,
    reset_interval: int = 500,
    robot_root_poses: list[tuple[float, float, float, float]] | None = None,
    preview_frame_path: Path | None = None,
    runtime_receipt_path: Path | None = None,
) -> dict[str, object] | None:
    robot: Articulation = scene["robot"]
    door: Articulation = scene["door"]
    sim_dt = sim.get_physics_dt()
    count = 0
    capture_step = 8
    capture_result = None

    reset_preview_scene(scene, robot_root_poses=robot_root_poses)
    if preview_frame_path is not None:
        set_pull_geometry_camera_poses(scene)
    print("[INFO]: A2_Piper door preview reset complete.")
    print(f"[INFO]: Robot joint count={len(robot.joint_names)} names={robot.joint_names}")
    print(f"[INFO]: Robot body count={len(robot.body_names)}")
    print(f"[INFO]: Door joint count={len(door.joint_names)} names={door.joint_names}")
    if robot_root_poses is not None:
        for env_id, (root_x, root_y, root_z, root_yaw) in enumerate(robot_root_poses):
            print(
                "[INFO]: Placement corner "
                f"env={env_id} x={root_x} y={root_y} z={root_z} yaw={root_yaw}"
            )

    while simulation_app.is_running():
        if max_steps >= 0 and count >= max_steps:
            break
        if reset_interval > 0 and count > 0 and count % reset_interval == 0:
            reset_preview_scene(scene, robot_root_poses=robot_root_poses)
            print("[INFO]: Periodic preview reset.")

        robot.set_joint_position_target(robot.data.default_joint_pos)
        if len(door.joint_names) > 0:
            door.set_joint_effort_target(torch.zeros_like(door.data.joint_pos))

        scene.write_data_to_sim()
        sim.step()
        scene.update(sim_dt)
        count += 1

        if preview_frame_path is not None and count == 1:
            frame_sensor = scene["pull_target_tcp_frames"]
            initialized_frame_data = frame_sensor.data
            if initialized_frame_data.target_pos_w is None:
                raise RuntimeError("FrameTransformer data was not initialized before debug visualization.")
            if not frame_sensor.set_debug_vis(True):
                raise RuntimeError("FrameTransformer does not support required debug visualization.")

        if preview_frame_path is not None and count == capture_step:
            if "preview_camera" not in scene.sensors:
                raise RuntimeError("Preview frame output requires the preview_camera sensor.")
            sim.render()
            preview_camera = scene["preview_camera"]
            preview_camera.update(dt=0.0, force_recompute=True)
            rgb = preview_camera.data.output["rgb"].clone()
            if rgb.ndim != 4 or rgb.shape[0] != 2 or rgb.shape[-1] not in (3, 4):
                raise RuntimeError(
                    "Paired pull geometry RGB must be NHWC with two frames and 3/4 channels; "
                    f"got shape={tuple(rgb.shape)}."
                )
            rgb = rgb[..., :3]
            if rgb.dtype != torch.uint8 or torch.any(torch.all(rgb == 0, dim=(-1, -2, -3))):
                raise RuntimeError(
                    "Paired pull geometry RGB must be nonzero torch.uint8 data; "
                    f"got dtype={rgb.dtype}."
                )
            preview_frame_path.parent.mkdir(parents=True, exist_ok=True)
            save_images_to_file(rgb.float() / 255.0, str(preview_frame_path))

            panel_contact = scene["door_panel_robot_contact"].data.force_matrix_w
            if panel_contact is None or not torch.all(torch.isfinite(panel_contact)):
                raise RuntimeError("Door-panel/robot contact proof requires finite force_matrix_w data.")
            max_panel_robot_contact_force = float(torch.linalg.vector_norm(panel_contact, dim=-1).max())

            frame_data = scene["pull_target_tcp_frames"].data
            frame_tensors = (
                frame_data.source_pos_w,
                frame_data.source_quat_w,
                frame_data.target_pos_w,
                frame_data.target_quat_w,
            )
            if any(value is None or not torch.all(torch.isfinite(value)) for value in frame_tensors):
                raise RuntimeError("pull_target_tcp_frames produced missing or non-finite data.")
            frames = {
                "target_frame_names": list(frame_data.target_frame_names),
                "source_pos_w": frame_data.source_pos_w.detach().cpu().tolist(),
                "source_quat_w": frame_data.source_quat_w.detach().cpu().tolist(),
                "target_pos_w": frame_data.target_pos_w.detach().cpu().tolist(),
                "target_quat_w": frame_data.target_quat_w.detach().cpu().tolist(),
            }
            frame_indices = {
                name: index for index, name in enumerate(frame_data.target_frame_names)
            }
            required_names = {"handle_inherited", "handle_io_z_pre", "handle_io_z_post"}
            if not required_names.issubset(frame_indices):
                raise RuntimeError(
                    "Pull geometry FrameTransformer is missing orientation candidates: "
                    f"required={sorted(required_names)}, actual={frame_data.target_frame_names}."
                )
            out_tcp_quat = frame_data.source_quat_w[0]
            in_tcp_quat = frame_data.source_quat_w[1]
            out_inherited_error = quaternion_angular_distance(
                out_tcp_quat,
                frame_data.target_quat_w[0, frame_indices["handle_inherited"]],
            )
            pull_candidate_errors = {
                candidate_name: quaternion_angular_distance(
                    in_tcp_quat,
                    frame_data.target_quat_w[1, frame_indices[candidate_name]],
                )
                for candidate_name in ("handle_inherited", "handle_io_z_pre", "handle_io_z_post")
            }
            symmetry_errors = {
                candidate_name: abs(candidate_error - out_inherited_error)
                for candidate_name, candidate_error in pull_candidate_errors.items()
            }
            ranked_candidates = sorted(symmetry_errors.items(), key=lambda item: item[1])
            if ranked_candidates[1][1] - ranked_candidates[0][1] <= 1.0e-3:
                raise RuntimeError(
                    "Pull target orientation overlay does not distinguish a mirrored candidate: "
                    f"{ranked_candidates}."
                )
            selected_candidate = ranked_candidates[0][0]

            capture_result = {
                "schema": "a2_piper_pull_v0_geometry_runtime_v1",
                "door_open_ios": list(PULL_GEOMETRY_PROOF_DIRECTIONS),
                "capture_step": capture_step,
                "max_panel_robot_contact_force_N": max_panel_robot_contact_force,
                "initial_panel_robot_contact": max_panel_robot_contact_force > 1.0,
                "frame_transformer": frames,
                "orientation_overlay": {
                    "out_inherited_tcp_error_rad": out_inherited_error,
                    "pull_candidate_tcp_error_rad": pull_candidate_errors,
                    "mirrored_error_delta_rad": symmetry_errors,
                    "selected_pull_orientation": selected_candidate.removeprefix("handle_"),
                    "selected_pull_target_quaternion_wxyz": list(
                        PULL_GEOMETRY_PROOF_TARGET_QUATERNIONS[
                            selected_candidate.removeprefix("handle_")
                        ]
                    ),
                },
                "render_path": str(preview_frame_path),
            }
            if capture_result["initial_panel_robot_contact"]:
                raise RuntimeError(
                    "Paired pull geometry proof detected initial robot-panel contact: "
                    f"{max_panel_robot_contact_force} N."
                )
            hinge_joint_index = door.joint_names.index("hinge_joint")
            capture_result["positive_hinge_probe"] = {
                "commanded_position_rad": 0.10,
                "handle_target_x_before_m": frame_data.target_pos_w[
                    :, frame_indices["handle_inherited"], 0
                ].detach().cpu().tolist(),
            }
            door_joint_pos = door.data.joint_pos.clone()
            door_joint_vel = torch.zeros_like(door.data.joint_vel)
            door_joint_pos[:, hinge_joint_index] = 0.10
            door.write_joint_state_to_sim(door_joint_pos, door_joint_vel)

        if preview_frame_path is not None and count == capture_step + 1:
            if capture_result is None:
                raise RuntimeError("Positive hinge probe requires the captured geometry baseline.")
            frame_data = scene["pull_target_tcp_frames"].data
            inherited_index = frame_data.target_frame_names.index("handle_inherited")
            after_x = frame_data.target_pos_w[:, inherited_index, 0]
            before_x = torch.tensor(
                capture_result["positive_hinge_probe"]["handle_target_x_before_m"],
                dtype=after_x.dtype,
                device=after_x.device,
            )
            delta_x = after_x - before_x
            capture_result["positive_hinge_probe"]["handle_target_x_after_m"] = (
                after_x.detach().cpu().tolist()
            )
            capture_result["positive_hinge_probe"]["handle_target_delta_x_m"] = (
                delta_x.detach().cpu().tolist()
            )
            capture_result["positive_hinge_probe"]["both_move_positive_world_x"] = bool(
                torch.all(delta_x > 0.0)
            )
            if not capture_result["positive_hinge_probe"]["both_move_positive_world_x"]:
                raise RuntimeError(
                    "Positive hinge motion did not move both paired handle targets toward +world-X: "
                    f"delta_x={delta_x.detach().cpu().tolist()}."
                )

    if preview_frame_path is not None and capture_result is None:
        raise RuntimeError(
            f"Preview terminated before required capture step {capture_step}; completed {count} steps."
        )
    if preview_frame_path is not None and "both_move_positive_world_x" not in capture_result.get(
        "positive_hinge_probe", {}
    ):
        raise RuntimeError("Preview terminated before the positive hinge geometry probe completed.")
    if runtime_receipt_path is not None:
        runtime_receipt_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_receipt_path.write_text(
            json.dumps(capture_result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return capture_result


def cleanup_preview_scene(sim: SimulationContext | None, scene: InteractiveScene | None) -> None:
    """Release preview scene and simulation resources before closing the SimulationApp."""
    if scene is not None:
        scene = None

    if sim is not None:
        for method_name in ("clear_all_callbacks", "clear_instance"):
            method = getattr(sim, method_name, None)
            if method is None:
                continue
            try:
                print(f"[INFO]: Preview cleanup `{method_name}`.", flush=True)
                method()
            except Exception as exc:
                print(f"[WARN]: Preview cleanup `{method_name}` failed: {exc}")
    else:
        try:
            SimulationContext.clear_instance()
        except Exception as exc:
            print(f"[WARN]: Preview cleanup `clear_instance` failed: {exc}")

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()


def create_preview_scene(
    *,
    usd_path: str | Path,
    num_envs: int,
    env_spacing: float,
    device: str,
    root_x: float,
    root_y: float,
    root_z: float,
    root_yaw: float,
    enable_camera: bool,
    enable_pull_geometry_overlay: bool = False,
) -> tuple[SimulationContext, InteractiveScene]:
    robot_cfg = build_a2_piper_robot_cfg(
        usd_path=usd_path,
        root_x=root_x,
        root_y=root_y,
        root_z=root_z,
        root_yaw=root_yaw,
    )
    door_open_ios = PULL_GEOMETRY_PROOF_DIRECTIONS if enable_pull_geometry_overlay else None
    door_cfg = build_doorman_door_cfg(
        num_envs,
        door_open_ios=door_open_ios,
        activate_contact_sensors=enable_pull_geometry_overlay,
    )
    scene_cfg = build_preview_scene_cfg(
        num_envs=num_envs,
        env_spacing=env_spacing,
        robot_cfg=robot_cfg,
        door_cfg=door_cfg,
        enable_camera=enable_camera,
        enable_pull_geometry_overlay=enable_pull_geometry_overlay,
    )
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=device))
    sim.set_camera_view([1.8, -1.6, 1.25], [-0.35, 0.0, 0.55])
    scene = InteractiveScene(scene_cfg)
    sim.reset()
    return sim, scene
