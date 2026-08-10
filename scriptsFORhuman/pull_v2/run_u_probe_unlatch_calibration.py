#!/usr/bin/env python3
"""Calibrate the door latch release angle with a door-only IsaacLab scene."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT = Path(__file__).resolve().parent / "PULL_V2_U_PROBE_UNLATCH_CALIBRATION.json"
THETA_SWEEP_RAD = tuple(round(0.1 * index, 1) for index in range(8)) + (0.785,)
HINGE_TARGET_RAD = math.radians(150.0)
HINGE_EFFORT_LIMIT_NM = 20.0
PROBE_STEPS = 200
UNLATCH_HINGE_MIN_RAD = 0.05

# Canonical central P1 fixture from the TaskObj/preview configuration.  Every
# stochastic DoorSpawnerCfg input is pinned below before the scene is built.
PULL_V2_U_PROBE_FIXTURE = {
    "door_width_m": 0.95,
    "door_height_m": 2.05,
    "door_handle_height_m": 0.95,
    "door_handle_width_m": 0.115,
    "door_handle_type": "lever",
    "door_weight_kg": 120.0,
    "door_open_lr": "right",
    "door_open_io": "out",
    "total_wall_height_m": 2.7,
    "axle_length_m": 0.195,
    "handle_length_m": 0.125,
    "hook_length_m": 0.05,
    "handle_radius_m": 0.013,
    "spawn_hook": True,
    "hinge_drive_max_force_nm": 7.25,
    "hinge_drive_stiffness": 5.5,
    "handle_drive_max_force_nm": 2.0,
    "door_width_range_m": (0.8, 1.1),
    "door_height_range_m": (1.9, 2.2),
    "door_handle_tblr_m": (1.1, 0.8, 0.08, 0.15),
    "door_weight_range_kg": (80.0, 120.0),
    "hinge_drive_max_force_range_nm": (2.5, 12.0),
    "handle_drive_max_force_range_nm": (1.0, 3.0),
    "wall_minimum_clearance_fblr_m": (3.0, 3.0, 1.0, 1.0),
    "wall_maximum_clearance_fblr_m": (10.0, 10.0, 10.0, 10.0),
    "randomize_material": False,
    "use_preloaded_materials": False,
    "preloaded_materials_num_transform": 1,
    "preloaded_materials_num_color": 1,
    "dynamic_material_randomization": False,
    "dynamic_material_randomization_interval_s": 1.0,
    "random_choice": False,
    "build_latch": True,
    "add_walls": False,
    "add_floors": False,
    "add_lights": False,
    "add_ceiling": False,
    "contact_sensors": True,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--steps", type=int, default=PROBE_STEPS)
    from isaaclab.app import AppLauncher

    AppLauncher.add_app_launcher_args(parser)
    return parser.parse_args()


def _joint_index(joint_names: list[str], expected_name: str) -> int:
    matches = [index for index, name in enumerate(joint_names) if name == expected_name]
    if len(matches) != 1:
        raise RuntimeError(
            f"U-probe requires exactly one {expected_name!r} joint; got names={joint_names!r}."
        )
    return matches[0]


def _build_deterministic_door_cfg(build_doorman_door_cfg):
    door_cfg = build_doorman_door_cfg(1)
    spawn_cfg = door_cfg.spawn
    assets_cfg = getattr(spawn_cfg, "assets_cfg", None)
    if not isinstance(assets_cfg, list) or len(assets_cfg) != 1:
        raise RuntimeError("U-probe requires exactly one high-level DoorSpawnerCfg asset")
    asset_cfg = assets_cfg[0].replace(
        door_width=PULL_V2_U_PROBE_FIXTURE["door_width_range_m"],
        door_height=PULL_V2_U_PROBE_FIXTURE["door_height_range_m"],
        door_handle_tblr=PULL_V2_U_PROBE_FIXTURE["door_handle_tblr_m"],
        door_handle_type=[PULL_V2_U_PROBE_FIXTURE["door_handle_type"]],
        door_open_lr=[PULL_V2_U_PROBE_FIXTURE["door_open_lr"]],
        door_open_io=[PULL_V2_U_PROBE_FIXTURE["door_open_io"]],
        door_weight=PULL_V2_U_PROBE_FIXTURE["door_weight_range_kg"],
        hinge_drive_max_force_range=PULL_V2_U_PROBE_FIXTURE["hinge_drive_max_force_range_nm"],
        handle_drive_max_force_range=PULL_V2_U_PROBE_FIXTURE["handle_drive_max_force_range_nm"],
        wall_minimum_clearance_fblr=PULL_V2_U_PROBE_FIXTURE["wall_minimum_clearance_fblr_m"],
        wall_maximum_clearance_fblr=PULL_V2_U_PROBE_FIXTURE["wall_maximum_clearance_fblr_m"],
        rand_door_width=PULL_V2_U_PROBE_FIXTURE["door_width_m"],
        rand_door_height=PULL_V2_U_PROBE_FIXTURE["door_height_m"],
        rand_door_handle_height=PULL_V2_U_PROBE_FIXTURE["door_handle_height_m"],
        rand_door_handle_width=PULL_V2_U_PROBE_FIXTURE["door_handle_width_m"],
        rand_door_weight=PULL_V2_U_PROBE_FIXTURE["door_weight_kg"],
        rand_door_handle_type=PULL_V2_U_PROBE_FIXTURE["door_handle_type"],
        rand_door_open_lr=PULL_V2_U_PROBE_FIXTURE["door_open_lr"],
        rand_door_open_io=PULL_V2_U_PROBE_FIXTURE["door_open_io"],
        rand_total_wall_height=PULL_V2_U_PROBE_FIXTURE["total_wall_height_m"],
        rand_axle_length=PULL_V2_U_PROBE_FIXTURE["axle_length_m"],
        rand_handle_length=PULL_V2_U_PROBE_FIXTURE["handle_length_m"],
        rand_hook_length=PULL_V2_U_PROBE_FIXTURE["hook_length_m"],
        rand_handle_radius=PULL_V2_U_PROBE_FIXTURE["handle_radius_m"],
        rand_spawn_hook=PULL_V2_U_PROBE_FIXTURE["spawn_hook"],
        rand_hinge_drive_max_force=PULL_V2_U_PROBE_FIXTURE["hinge_drive_max_force_nm"],
        rand_hinge_drive_stiffness=PULL_V2_U_PROBE_FIXTURE["hinge_drive_stiffness"],
        rand_handle_drive_max_force=PULL_V2_U_PROBE_FIXTURE["handle_drive_max_force_nm"],
        rand_front=False,
        rand_rear=False,
        rand_left=False,
        rand_left_front=False,
        rand_right_front=False,
        rand_left_rear=False,
        rand_right_rear=False,
        build_latch=PULL_V2_U_PROBE_FIXTURE["build_latch"],
        add_walls=PULL_V2_U_PROBE_FIXTURE["add_walls"],
        add_floors=PULL_V2_U_PROBE_FIXTURE["add_floors"],
        add_lights=PULL_V2_U_PROBE_FIXTURE["add_lights"],
        add_ceiling=PULL_V2_U_PROBE_FIXTURE["add_ceiling"],
        randomize_material=PULL_V2_U_PROBE_FIXTURE["randomize_material"],
        use_preloaded_materials=PULL_V2_U_PROBE_FIXTURE["use_preloaded_materials"],
        preloaded_materials_num_transform=PULL_V2_U_PROBE_FIXTURE["preloaded_materials_num_transform"],
        preloaded_materials_num_color=PULL_V2_U_PROBE_FIXTURE["preloaded_materials_num_color"],
        dynamic_material_randomization=PULL_V2_U_PROBE_FIXTURE["dynamic_material_randomization"],
        dynamic_material_randomization_interval=PULL_V2_U_PROBE_FIXTURE["dynamic_material_randomization_interval_s"],
        activate_contact_sensors=PULL_V2_U_PROBE_FIXTURE["contact_sensors"],
    )
    spawn_cfg = spawn_cfg.replace(
        assets_cfg=[asset_cfg],
        random_choice=PULL_V2_U_PROBE_FIXTURE["random_choice"],
        activate_contact_sensors=PULL_V2_U_PROBE_FIXTURE["contact_sensors"],
    )
    return door_cfg.replace(spawn=spawn_cfg)


def _build_door_only_scene(num_envs: int, build_doorman_door_cfg):
    import isaaclab.sim as sim_utils
    from isaaclab.actuators import ImplicitActuatorCfg
    from isaaclab.assets import ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.utils import configclass

    if num_envs != 1:
        raise ValueError("U-probe is a single-door calibration and requires num_envs=1.")
    door_cfg = _build_deterministic_door_cfg(build_doorman_door_cfg)
    door_cfg.actuators["hinge"] = ImplicitActuatorCfg(
        joint_names_expr=[".*hinge.*"],
        effort_limit_sim=HINGE_EFFORT_LIMIT_NM,
        velocity_limit_sim=100.0,
        stiffness=5.5,
        damping=50.0,
    )

    @configclass
    class DoorOnlySceneCfg(InteractiveSceneCfg):
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
        door: ArticulationCfg = door_cfg.replace(prim_path="{ENV_REGEX_NS}/door")

    scene_cfg = DoorOnlySceneCfg(num_envs=1, env_spacing=2.0, replicate_physics=False)
    return sim_utils, InteractiveScene, scene_cfg


def run_probe(args: argparse.Namespace) -> dict[str, object]:
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app
    from gr00t.rl.envs.door.a2_piper_door_scene_preview import build_doorman_door_cfg
    import isaaclab.sim as sim_utils

    sim_utils_module, interactive_scene_cls, scene_cfg = _build_door_only_scene(
        1, build_doorman_door_cfg
    )
    del sim_utils_module
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=args.device))
    scene = interactive_scene_cls(scene_cfg)
    sim.reset()
    door = scene["door"]
    joint_names = list(door.joint_names)
    hinge_index = _joint_index(joint_names, "hinge_joint")
    handle_index = _joint_index(joint_names, "handle_joint")
    latch_index = _joint_index(joint_names, "latch_joint")
    if args.steps <= 0:
        raise ValueError("--steps must be positive.")

    rows: list[dict[str, float]] = []
    for theta in THETA_SWEEP_RAD:
        door_root_state = door.data.default_root_state.clone()
        door_root_state[:, :3] += scene.env_origins
        door.write_root_pose_to_sim(door_root_state[:, :7])
        door.write_root_velocity_to_sim(door_root_state[:, 7:])
        joint_pos = door.data.default_joint_pos.clone()
        joint_pos[:, hinge_index] = 0.0
        joint_pos[:, handle_index] = theta
        joint_pos[:, latch_index] = 0.0
        door.write_joint_state_to_sim(joint_pos, torch.zeros_like(joint_pos))
        door.set_joint_position_target(joint_pos)
        scene.reset()

        hinge_max = 0.0
        latch_max = 0.0
        for _step in range(args.steps):
            current_pos = door.data.joint_pos.clone()
            current_vel = door.data.joint_vel.clone()
            current_pos[:, handle_index] = theta
            door.write_joint_state_to_sim(current_pos, current_vel)
            target = current_pos.clone()
            target[:, hinge_index] = HINGE_TARGET_RAD
            target[:, handle_index] = theta
            door.set_joint_position_target(target)
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim.get_physics_dt())
            updated_pos = door.data.joint_pos
            if not torch.all(torch.isfinite(updated_pos)):
                raise RuntimeError("U-probe produced non-finite door joint positions.")
            hinge_max = max(hinge_max, float(updated_pos[0, hinge_index].item()))
            latch_max = max(latch_max, float(updated_pos[0, latch_index].item()))
        rows.append(
            {
                "theta_rad": theta,
                "latch_m": latch_max,
                "hinge_max_rad": hinge_max,
            }
        )

    qualifying = [row for row in rows if row["hinge_max_rad"] > UNLATCH_HINGE_MIN_RAD]
    theta_star = qualifying[0]["theta_rad"] if qualifying else None
    receipt = {
        "schema": "pull_v2_u_probe_unlatch_calibration_v1",
        "plan_id": "a2_piper_pull_v2_wall_removal_and_unlatch_calibration",
        "status": "PASS" if theta_star is not None else "NO_UNLOCK_WITHIN_SWEEP",
        "scene": "door_only",
        "fixture": PULL_V2_U_PROBE_FIXTURE,
        "joint_names": joint_names,
        "resolved_joint_indices": {
            "hinge_joint": hinge_index,
            "handle_joint": handle_index,
            "latch_joint": latch_index,
        },
        "theta_sweep_rad": list(THETA_SWEEP_RAD),
        "steps_per_theta": args.steps,
        "hinge_target_rad": HINGE_TARGET_RAD,
        "hinge_effort_limit_nm": HINGE_EFFORT_LIMIT_NM,
        "unlatch_hinge_min_rad": UNLATCH_HINGE_MIN_RAD,
        "table": rows,
        "theta_star_rad": theta_star,
        "a2_pull_e3_latch_threshold_m": (
            qualifying[0]["latch_m"] if qualifying else None
        ),
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    simulation_app.close(skip_cleanup=True)
    return receipt


def main() -> int:
    args = _parse_args()
    result = run_probe(args)
    print(json.dumps(result, indent=2))
    return 0 if result["theta_star_rad"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
