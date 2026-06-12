# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import gc
import math
from pathlib import Path

import torch

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
from isaaclab.sensors import TiledCameraCfg
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
                disable_gravity=False,
                retain_accelerations=False,
                linear_damping=0.0,
                angular_damping=0.0,
                max_linear_velocity=1000.0,
                max_angular_velocity=1000.0,
                max_depenetration_velocity=1.0,
            ),
            articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                enabled_self_collisions=False,
                solver_position_iteration_count=8,
                solver_velocity_iteration_count=4,
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
            "all": ImplicitActuatorCfg(
                joint_names_expr=A2_PIPER_DOF_NAMES,
                effort_limit_sim=A2_PIPER_EFFORT_LIMITS,
                velocity_limit_sim=A2_PIPER_VELOCITY_LIMITS,
                stiffness={
                    ".*hip.*": 80.0,
                    ".*thigh.*": 80.0,
                    ".*calf.*": 80.0,
                    "arm_j[1-4]": 40.0,
                    "arm_j[5-6]": 20.0,
                    "arm_j[7-8]": 1000.0,
                },
                damping={
                    ".*hip.*": 4.0,
                    ".*thigh.*": 4.0,
                    ".*calf.*": 4.0,
                    "arm_j[1-4]": 2.0,
                    "arm_j[5-6]": 1.0,
                    "arm_j[7-8]": 10.0,
                },
                armature={joint_name: 0.003 for joint_name in A2_PIPER_DOF_NAMES},
                friction={joint_name: 0.0 for joint_name in A2_PIPER_DOF_NAMES},
            )
        },
    )


def build_doorman_door_cfg(num_envs: int) -> ArticulationCfg:
    door_cfg = copy.deepcopy(TaskObjCfgDict["door"])
    if isinstance(door_cfg.spawn, sim_utils.MultiAssetSpawnerCfg):
        door_cfg.spawn.assets_cfg = door_cfg.spawn.assets_cfg[:num_envs]
        door_cfg.spawn.activate_contact_sensors = False
        for asset_cfg in door_cfg.spawn.assets_cfg:
            if hasattr(asset_cfg, "activate_contact_sensors"):
                asset_cfg.activate_contact_sensors = False
    return door_cfg


def build_preview_scene_cfg(
    *,
    num_envs: int,
    env_spacing: float,
    robot_cfg: ArticulationCfg,
    door_cfg: ArticulationCfg,
    enable_camera: bool,
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


def run_zero_action_hold(
    sim: SimulationContext,
    scene: InteractiveScene,
    simulation_app,
    *,
    max_steps: int = -1,
    reset_interval: int = 500,
    robot_root_poses: list[tuple[float, float, float, float]] | None = None,
) -> None:
    robot: Articulation = scene["robot"]
    door: Articulation = scene["door"]
    sim_dt = sim.get_physics_dt()
    count = 0

    reset_preview_scene(scene, robot_root_poses=robot_root_poses)
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
) -> tuple[SimulationContext, InteractiveScene]:
    robot_cfg = build_a2_piper_robot_cfg(
        usd_path=usd_path,
        root_x=root_x,
        root_y=root_y,
        root_z=root_z,
        root_yaw=root_yaw,
    )
    door_cfg = build_doorman_door_cfg(num_envs)
    scene_cfg = build_preview_scene_cfg(
        num_envs=num_envs,
        env_spacing=env_spacing,
        robot_cfg=robot_cfg,
        door_cfg=door_cfg,
        enable_camera=enable_camera,
    )
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=device))
    sim.set_camera_view([1.8, -1.6, 1.25], [-0.35, 0.0, 0.55])
    scene = InteractiveScene(scene_cfg)
    sim.reset()
    return sim, scene
