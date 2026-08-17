# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Standalone door joint / reward verification script."""

from __future__ import annotations

import argparse
import gc
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def import_app_launcher():
    try:
        from isaaclab.app import AppLauncher
    except ModuleNotFoundError as exc:
        if exc.name != "isaaclab":
            raise
        return None
    return AppLauncher


def parse_args():
    parser = argparse.ArgumentParser(description="Door joint / reward verification")
    AppLauncher = import_app_launcher()
    if AppLauncher is None:
        return parser.parse_args(), None, None
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    args.headless = True  # force headless
    print("[smoke] creating AppLauncher...", flush=True)
    app_launcher = AppLauncher(args)
    print("[smoke] AppLauncher created.", flush=True)
    return args, app_launcher, app_launcher.app


def create_door_scene(*, device: str):
    import torch  # noqa: F401

    import isaaclab.sim as sim_utils
    from isaaclab.actuators import ImplicitActuatorCfg
    from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.sim import SimulationContext
    from isaaclab.utils import configclass

    from gr00t.rl.data.tasks.door.scenario_cfg.isaacsim import door_spawner_cfg

    door_cfg = ArticulationCfg(
        spawn=door_spawner_cfg,
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(0.0, 0.0, 0.0),
            rot=(1.0, 0.0, 0.0, 0.0),
            joint_pos={
                ".*hinge.*": 0.0,
                ".*handle.*": 0.0,
                ".*latch.*": 0.0,
            },
            joint_vel={".*": 0.0},
        ),
        soft_joint_pos_limit_factor=0.9,
        actuators={
            "hinge": ImplicitActuatorCfg(
                joint_names_expr=[".*hinge.*"],
                velocity_limit_sim=100.0,
                stiffness=None,
                damping=None,
            ),
            "handle": ImplicitActuatorCfg(
                joint_names_expr=[".*handle.*"],
                velocity_limit_sim=100.0,
                stiffness=None,
                damping=None,
            ),
            "latch": ImplicitActuatorCfg(
                joint_names_expr=[".*latch.*"],
                velocity_limit_sim=100.0,
                stiffness=None,
                damping=None,
            ),
        },
    )

    @configclass
    class DoorOnlySceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane",
            spawn=sim_utils.GroundPlaneCfg(),
        )
        dome_light = AssetBaseCfg(
            prim_path="/World/DomeLight",
            spawn=sim_utils.DomeLightCfg(intensity=2000.0),
        )
        door: ArticulationCfg = door_cfg.replace(prim_path="{ENV_REGEX_NS}/door")

    scene_cfg = DoorOnlySceneCfg(num_envs=1, env_spacing=4.0, replicate_physics=False)
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=device))
    scene = InteractiveScene(scene_cfg)
    sim.reset()
    return sim, scene


def run_door_joint_test(sim, scene, device: str):
    import torch

    door = scene["door"]
    sim_dt = sim.get_physics_dt()

    def compute_push_door_handle(joint_pos, joint_vel):
        handle_vel_reward = joint_vel[:, 1]
        handle_pos_reward = joint_pos[:, 1].clamp(min=0.0, max=0.785398) / 0.785398
        return (handle_vel_reward + handle_pos_reward).clamp(max=1.0, min=-1.0)

    def compute_push_door_hinge(joint_pos, joint_vel):
        hinge_vel_reward = joint_vel[:, 0] * 10
        hinge_pos_reward = joint_pos[:, 0].clamp(min=0.0, max=1.5708) / 1.5708
        return (hinge_vel_reward + hinge_pos_reward).clamp(max=1.0, min=-1.0)

    # settle
    for _ in range(5):
        door.set_joint_effort_target(torch.zeros_like(door.data.joint_pos))
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim_dt)

    print("=" * 70, flush=True)
    print("DOOR JOINT VERIFICATION", flush=True)
    print("=" * 70, flush=True)

    # 1. Joint names and indices
    print("\n--- 1. Joint names and indices ---", flush=True)
    print(f"  joint_names: {door.joint_names}", flush=True)
    print(f"  num_joints:  {door.num_joints}", flush=True)
    for i, name in enumerate(door.joint_names):
        print(f"    index {i}: {name}", flush=True)

    # 2. Joint limits (safe access)
    print("\n--- 2. Joint limits ---", flush=True)
    try:
        jpl = door.data.joint_pos_limits.cpu()
        print(f"  joint_pos_limits shape: {jpl.shape}", flush=True)
        if jpl.dim() >= 2:
            limits_env0 = jpl[0]
            if limits_env0.dim() == 2:
                for i, name in enumerate(door.joint_names):
                    print(f"    {name}: [{limits_env0[i, 0]:.4f}, {limits_env0[i, 1]:.4f}]", flush=True)
            elif limits_env0.dim() == 1:
                print(f"  values: {limits_env0.tolist()}", flush=True)
    except Exception as e:
        print(f"  (could not read joint_pos_limits: {e})", flush=True)

    # 3. Set joints to known positions
    test_cases = [
        ("all closed (0, 0)",           [0.0, 0.0, 0.0]),
        ("hinge 10deg (0.1745, 0, 0)",   [0.1745, 0.0, 0.0]),
        ("hinge 30deg (0.524, 0, 0)",    [0.524, 0.0, 0.0]),
        ("hinge 60deg (1.047, 0, 0)",    [1.047, 0.0, 0.0]),
        ("hinge 90deg (1.571, 0, 0)",    [1.571, 0.0, 0.0]),
        ("handle 15deg (0, 0.262, 0)",   [0.0, 0.262, 0.0]),
        ("handle 45deg (0, 0.785, 0)",   [0.0, 0.785, 0.0]),
        ("both mid (0.5, 0.4, 0)",       [0.5, 0.4, 0.0]),
        ("negative hinge (-0.5, 0, 0)", [-0.5, 0.0, 0.0]),
    ]

    print("\n--- 3. Joint position set/read + reward computation ---", flush=True)
    print(f"{'test case':<35} {'set_pos':>22} {'read_pos':>22} {'read_vel':>22} {'hinge_rw':>10} {'handle_rw':>10}", flush=True)
    print("-" * 125, flush=True)

    for label, test_pos in test_cases:
        target_pos = torch.tensor([test_pos], device=device, dtype=torch.float32)
        zero_vel = torch.zeros_like(target_pos)

        for _ in range(50):
            door.set_joint_position_target(target_pos)
            door.set_joint_velocity_target(zero_vel)
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim_dt)

        read_pos = door.data.joint_pos[0].cpu().tolist()
        read_vel = door.data.joint_vel[0].cpu().tolist()

        jp = door.data.joint_pos
        jv = door.data.joint_vel
        r_hinge = compute_push_door_hinge(jp, jv)[0].cpu().item()
        r_handle = compute_push_door_handle(jp, jv)[0].cpu().item()

        set_str = f"[{test_pos[0]:.3f}, {test_pos[1]:.3f}, {test_pos[2]:.3f}]"
        read_str = f"[{read_pos[0]:.3f}, {read_pos[1]:.3f}, {read_pos[2]:.3f}]"
        vel_str = f"[{read_vel[0]:.3f}, {read_vel[1]:.3f}, {read_vel[2]:.3f}]"
        print(f"{label:<35} {set_str:>22} {read_str:>22} {vel_str:>22} {r_hinge:>10.4f} {r_handle:>10.4f}", flush=True)

    print("\n--- Done ---", flush=True)


def main() -> int:
    print("[smoke] main() start", flush=True)
    args, app_launcher, simulation_app = parse_args()
    print("[smoke] parse_args done", flush=True)
    if simulation_app is None:
        print("ERROR: IsaacLab is required to run this script.", file=sys.stderr, flush=True)
        return 1

    sim = None
    scene = None
    run_error = None

    try:
        print("[smoke] creating door scene...", flush=True)
        sim, scene = create_door_scene(device=args.device)
        print("[smoke] door scene created, running test...", flush=True)
        run_door_joint_test(sim, scene, args.device)
        print("[smoke] test completed.", flush=True)
    except BaseException as exc:
        run_error = exc
        traceback.print_exception(exc, file=sys.stderr)
    finally:
        scene = None
        gc.collect()
        if sim is not None:
            try:
                sim.clear_all_callbacks()
                sim.clear_instance()
            except Exception:
                pass
        sim = None
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if simulation_app is not None:
            try:
                simulation_app.close()
            except BaseException as exc:
                if run_error is None:
                    run_error = exc
                    traceback.print_exception(exc, file=sys.stderr)
        if run_error is not None:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
