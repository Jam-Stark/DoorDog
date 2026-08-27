#!/usr/bin/env python3
"""Run the one-door deterministic v26-2 handle/latch calibration on the current asset."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT = ROOT / "logs_eval/base_v26/v26_2_pull_derived_20260825/u_probe_receipt.json"
HANDLE_SWEEP_RAD = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.785398)
FIXTURE = {
    "door_width_m": 0.95,
    "door_height_m": 2.05,
    "door_handle_height_m": 0.90,
    "door_weight_kg": 100.0,
    "door_open_lr": "right",
    "door_open_io": "out",
    "handle_drive_max_force_nm": 2.0,
    "hinge_drive_max_force_nm": 7.25,
    "hinge_drive_stiffness": 5.5,
    "steps_per_theta": 200,
    "handle_norm_rad": 0.6,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--steps", type=int, default=FIXTURE["steps_per_theta"])
    from isaaclab.app import AppLauncher

    AppLauncher.add_app_launcher_args(parser)
    return parser.parse_args()


def exact_joint_index(names: list[str], name: str) -> int:
    matches = [index for index, candidate in enumerate(names) if candidate == name]
    if len(matches) != 1:
        raise RuntimeError(f"v26-2 U-probe requires one {name}; got {names!r}")
    return matches[0]


def door_cfg(build_doorman_door_cfg):
    cfg = build_doorman_door_cfg(1)
    asset = cfg.spawn.assets_cfg[0].replace(
        door_width=(FIXTURE["door_width_m"], FIXTURE["door_width_m"]),
        door_height=(FIXTURE["door_height_m"], FIXTURE["door_height_m"]),
        door_handle_tblr=(1.1, 0.8, 0.08, 0.15),
        door_handle_type=["lever"],
        door_open_lr=[FIXTURE["door_open_lr"]],
        door_open_io=[FIXTURE["door_open_io"]],
        door_weight=(FIXTURE["door_weight_kg"], FIXTURE["door_weight_kg"]),
        hinge_drive_max_force_range=(FIXTURE["hinge_drive_max_force_nm"], FIXTURE["hinge_drive_max_force_nm"]),
        handle_drive_max_force_range=(FIXTURE["handle_drive_max_force_nm"], FIXTURE["handle_drive_max_force_nm"]),
        rand_door_width=FIXTURE["door_width_m"], rand_door_height=FIXTURE["door_height_m"],
        rand_door_handle_height=FIXTURE["door_handle_height_m"], rand_door_weight=FIXTURE["door_weight_kg"],
        rand_door_handle_type="lever", rand_door_open_lr=FIXTURE["door_open_lr"], rand_door_open_io=FIXTURE["door_open_io"],
        rand_hinge_drive_max_force=FIXTURE["hinge_drive_max_force_nm"], rand_hinge_drive_stiffness=FIXTURE["hinge_drive_stiffness"],
        rand_handle_drive_max_force=FIXTURE["handle_drive_max_force_nm"],
        randomize_material=False, use_preloaded_materials=False, dynamic_material_randomization=False,
        build_latch=True, add_walls=False, add_floors=False, add_lights=False, add_ceiling=False,
    )
    return cfg.replace(spawn=cfg.spawn.replace(assets_cfg=[asset], random_choice=False))


def run(args: argparse.Namespace) -> dict[str, object]:
    if args.steps <= 0:
        raise ValueError("--steps must be positive")
    from isaaclab.app import AppLauncher

    app = AppLauncher(args).app
    import isaaclab.sim as sim_utils
    from isaaclab.actuators import ImplicitActuatorCfg
    from isaaclab.assets import ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.utils import configclass
    from gr00t.rl.envs.door.a2_piper_door_scene_preview import build_doorman_door_cfg

    cfg = door_cfg(build_doorman_door_cfg)
    cfg.actuators["hinge"] = ImplicitActuatorCfg(joint_names_expr=[".*hinge.*"], effort_limit_sim=20.0, velocity_limit_sim=100.0, stiffness=FIXTURE["hinge_drive_stiffness"], damping=50.0)

    @configclass
    class SceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(prim_path="/World/defaultGroundPlane", spawn=sim_utils.GroundPlaneCfg())
        door: ArticulationCfg = cfg.replace(prim_path="{ENV_REGEX_NS}/door")

    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=args.device))
    scene = InteractiveScene(SceneCfg(num_envs=1, env_spacing=2.0, replicate_physics=False))
    sim.reset()
    door = scene["door"]
    names = list(door.joint_names)
    hinge, handle, latch = (exact_joint_index(names, name) for name in ("hinge_joint", "handle_joint", "latch_joint"))
    table = []
    for theta in HANDLE_SWEEP_RAD:
        root = door.data.default_root_state.clone(); root[:, :3] += scene.env_origins
        door.write_root_pose_to_sim(root[:, :7]); door.write_root_velocity_to_sim(root[:, 7:])
        pos = door.data.default_joint_pos.clone(); pos[:, hinge] = 0.0; pos[:, handle] = theta; pos[:, latch] = 0.0
        door.write_joint_state_to_sim(pos, torch.zeros_like(pos)); door.set_joint_position_target(pos); scene.reset()
        hinge_max = 0.0; latch_max = 0.0
        for _ in range(args.steps):
            current = door.data.joint_pos.clone(); velocity = door.data.joint_vel.clone(); current[:, handle] = theta
            door.write_joint_state_to_sim(current, velocity)
            target = current.clone(); target[:, hinge] = math.radians(150.0); target[:, handle] = theta
            door.set_joint_position_target(target); scene.write_data_to_sim(); sim.step(); scene.update(sim.get_physics_dt())
            observed = door.data.joint_pos
            if not torch.all(torch.isfinite(observed)):
                raise RuntimeError("v26-2 U-probe observed non-finite joint positions")
            hinge_max = max(hinge_max, float(observed[0, hinge]))
            latch_max = max(latch_max, float(observed[0, latch]))
        table.append({"handle_theta_rad": theta, "handle_norm": theta / 0.785398, "hinge_max_rad": hinge_max, "latch_max_m": latch_max})
    receipt = {"schema": "a2_piper_base_v26_2_u_probe_current_fixture_v1", "fixture": FIXTURE, "joint_names": names, "joint_indices": {"hinge": hinge, "handle": handle, "latch": latch}, "table": table, "status": "RUNTIME_COMPLETE"}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    app.close(skip_cleanup=True)
    return receipt


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
