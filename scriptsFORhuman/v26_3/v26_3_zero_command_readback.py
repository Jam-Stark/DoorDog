#!/usr/bin/env python3
"""Measure passive handle excursion under zero door/handle commands on the current fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT = (
    ROOT
    / "logs_eval/base_v26/v26_3_event_time_creation_20260827/diagnostics/zero_command_readback.json"
)
FIXTURE = {
    "door_width_m": 0.95,
    "door_height_m": 2.05,
    "door_handle_height_m": 0.90,
    "door_weight_kg": 100.0,
    "door_open_io": "out",
    "handle_drive_max_force_nm": 2.0,
    "hinge_drive_max_force_nm": 7.25,
    "hinge_drive_stiffness": 5.5,
    "steps": 400,
    "physics_dt_s": 0.005,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--side", choices=("left", "right"), required=True)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--steps", type=int, default=FIXTURE["steps"])
    from isaaclab.app import AppLauncher

    AppLauncher.add_app_launcher_args(parser)
    return parser.parse_args()


def exact_joint_index(names: list[str], name: str) -> int:
    matches = [index for index, candidate in enumerate(names) if candidate == name]
    if len(matches) != 1:
        raise RuntimeError(f"v26-3 zero-command readback requires one {name}; got {names!r}")
    return matches[0]


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

    door_cfg = build_doorman_door_cfg(1)
    asset = door_cfg.spawn.assets_cfg[0].replace(
        door_width=(FIXTURE["door_width_m"], FIXTURE["door_width_m"]),
        door_height=(FIXTURE["door_height_m"], FIXTURE["door_height_m"]),
        door_handle_tblr=(1.1, 0.8, 0.08, 0.15),
        door_handle_type=["lever"],
        door_open_lr=[args.side],
        door_open_io=[FIXTURE["door_open_io"]],
        door_weight=(FIXTURE["door_weight_kg"], FIXTURE["door_weight_kg"]),
        hinge_drive_max_force_range=(
            FIXTURE["hinge_drive_max_force_nm"],
            FIXTURE["hinge_drive_max_force_nm"],
        ),
        handle_drive_max_force_range=(
            FIXTURE["handle_drive_max_force_nm"],
            FIXTURE["handle_drive_max_force_nm"],
        ),
        rand_door_width=FIXTURE["door_width_m"],
        rand_door_height=FIXTURE["door_height_m"],
        rand_door_handle_height=FIXTURE["door_handle_height_m"],
        rand_door_weight=FIXTURE["door_weight_kg"],
        rand_door_handle_type="lever",
        rand_door_open_lr=args.side,
        rand_door_open_io=FIXTURE["door_open_io"],
        rand_hinge_drive_max_force=FIXTURE["hinge_drive_max_force_nm"],
        rand_hinge_drive_stiffness=FIXTURE["hinge_drive_stiffness"],
        rand_handle_drive_max_force=FIXTURE["handle_drive_max_force_nm"],
        randomize_material=False,
        use_preloaded_materials=False,
        dynamic_material_randomization=False,
        build_latch=True,
        add_walls=False,
        add_floors=False,
        add_lights=False,
        add_ceiling=False,
    )
    door_cfg = door_cfg.replace(
        spawn=door_cfg.spawn.replace(assets_cfg=[asset], random_choice=False)
    )
    door_cfg.actuators["hinge"] = ImplicitActuatorCfg(
        joint_names_expr=[".*hinge.*"],
        effort_limit_sim=20.0,
        velocity_limit_sim=100.0,
        stiffness=FIXTURE["hinge_drive_stiffness"],
        damping=50.0,
    )

    @configclass
    class SceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane", spawn=sim_utils.GroundPlaneCfg()
        )
        door: ArticulationCfg = door_cfg.replace(prim_path="{ENV_REGEX_NS}/door")

    sim = sim_utils.SimulationContext(
        sim_utils.SimulationCfg(dt=FIXTURE["physics_dt_s"], device=args.device)
    )
    scene = InteractiveScene(SceneCfg(num_envs=1, env_spacing=2.0, replicate_physics=False))
    sim.reset()
    door = scene["door"]
    names = list(door.joint_names)
    hinge, handle, latch = (
        exact_joint_index(names, name)
        for name in ("hinge_joint", "handle_joint", "latch_joint")
    )
    root = door.data.default_root_state.clone()
    root[:, :3] += scene.env_origins
    door.write_root_pose_to_sim(root[:, :7])
    door.write_root_velocity_to_sim(root[:, 7:])
    initial = door.data.default_joint_pos.clone()
    initial[:, hinge] = 0.0
    initial[:, handle] = 0.0
    initial[:, latch] = 0.0
    door.write_joint_state_to_sim(initial, torch.zeros_like(initial))
    zero_target = initial.clone()
    door.set_joint_position_target(zero_target)
    scene.reset()

    handle_min = 0.0
    handle_max = 0.0
    for _ in range(args.steps):
        door.set_joint_position_target(zero_target)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.get_physics_dt())
        observed = door.data.joint_pos
        if not torch.all(torch.isfinite(observed)):
            raise RuntimeError("v26-3 zero-command readback observed non-finite joints")
        value = float(observed[0, handle])
        handle_min = min(handle_min, value)
        handle_max = max(handle_max, value)

    receipt = {
        "schema": "a2_piper_base_v26_3_zero_command_readback_v1",
        "status": "RUNTIME_COMPLETE",
        "side": args.side.upper(),
        "fixture": FIXTURE,
        "joint_names": names,
        "joint_indices": {"hinge": hinge, "handle": handle, "latch": latch},
        "zero_target_rad": 0.0,
        "handle_min_rad": handle_min,
        "handle_max_rad": handle_max,
        "handle_zero_state_excursion_rad": max(abs(handle_min), abs(handle_max)),
        "handle_zero_state_excursion_norm": max(abs(handle_min), abs(handle_max)) / 0.785398,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    app.close(skip_cleanup=True)
    return receipt


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, allow_nan=False))
