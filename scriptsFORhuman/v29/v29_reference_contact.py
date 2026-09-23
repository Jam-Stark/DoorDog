"""Bounded reference approach/closure with the real v29 robot and door.

The robot root is held as an explicit bench fixture; arm/finger motion uses
the production implicit drives. This is geometry/contact evidence, not policy
success, whole-body stability, or a training intervention.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def bounded_dls_targets(jacobians, command_positions, pose_delta, limits):
    """Solve DLS with actual joint bounds as constraints, without clipping.

    Integrate a Cartesian velocity correction into the preceding drive target:
    min ||J(q_next-q_cmd)-dx||² + .01²||q_next-q_cmd||², with native bounds.
    """
    import numpy as np
    from scipy.optimize import lsq_linear

    targets, active_bounds = [], []
    regularizer = .01 * np.eye(6)
    for index, (jacobian, q, delta, bound) in enumerate(zip(jacobians, command_positions, pose_delta, limits)):
        matrix = np.vstack((jacobian, regularizer))
        rhs = np.concatenate((jacobian @ q + delta, regularizer @ q))
        result = lsq_linear(matrix, rhs, bounds=(bound[:, 0], bound[:, 1]),
                            method="bvls", tol=1.e-10)
        if not result.success:
            raise RuntimeError(f"Bounded reference DLS failed for env {index}: {result.message}")
        targets.append(result.x)
        active_bounds.append(result.active_mask.tolist())
    return np.asarray(targets), active_bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ik-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--staged-lifecycle-only", action="store_true")
    parser.add_argument("--standoff", type=float, default=.60)
    parser.add_argument("--pregrasp-steps", type=int, default=300)
    parser.add_argument("--approach-steps", type=int, default=150)
    parser.add_argument("--close-steps", type=int, default=100)
    parser.add_argument("--dynamics-steps", type=int, default=250)
    parser.add_argument("--limit-steps", type=int, default=50)
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text())["cases"]
    n = len(cases)
    if not 1 <= n <= 64:
        raise ValueError("D032 reference contact authorization is limited to 64 environments")
    args.output.mkdir(parents=True, exist_ok=False)

    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from gr00t.rl.utils.config_utils import register_rl_resolvers
    register_rl_resolvers()
    with initialize_config_dir(config_dir=str(ROOT / "gr00t/rl/config"), version_base="1.1"):
        config = compose(config_name="base", overrides=[
            "+exp=wbmanip/door_open_a2_base_lstm", "+ablation=wbmanip/base_v29_baseline",
            f"num_envs={n}", "seed=291", "headless=true", "use_wandb=false",
            "project_name=base_v29_owner_baseline", "experiment_name=C001_REFERENCE_CONTACT",
            "exp_base=wbmanip/door_open_a2_base_lstm", "env.config.enable_staged_reset=false",
            "env.config.a2_hold_diagnostic_contact_detail_enabled=true",
            "env.config.a2_hold_diagnostic_max_contact_data_count_per_prim=128",
            f"experiment_dir={args.output.resolve()}", f"output_dir={args.output.resolve()}/output",
        ])
    if args.staged_lifecycle_only:
        config.env.config.enable_staged_reset = True
        config.env.config.staged_reset_ratios = [1.e-6, 1., 0., 0., 0., 0.]
        config.env.config.staged_reset_max_samples_per_stage = 200
    OmegaConf.save(config, args.output / "resolved_config.yaml", resolve=True)
    from isaaclab.app import AppLauncher
    from gr00t.rl.train_agent_trl import patch_app_launcher_toolbar_hiding
    patch_app_launcher_toolbar_hiding(AppLauncher)
    app = AppLauncher(headless=True, device=args.device, enable_cameras=args.render).app
    try:
        run_reference(config, cases, args)
    except Exception:
        # Kit's immediate shutdown exits with zero, even while unwinding an
        # exception. Preserve the real failure before the framework can do so.
        import os
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    app.close(skip_cleanup=True)


def run_reference(config, cases, args):
    import importlib
    import numpy as np
    import torch
    from isaaclab.sensors import ContactSensor, ContactSensorCfg, Camera, CameraCfg
    import isaaclab.sim as sim_utils
    from isaaclab.utils.math import subtract_frame_transforms, quat_apply_inverse, quat_mul, quat_inv, axis_angle_from_quat, apply_delta_pose
    from gr00t.rl.envs.door.door_open_a2_base import (
        DoorPregrasp, a2_hold_rotate_jacobian_to_root,
        a2_hold_apply_source_offset_to_jacobian, a2_hold_bound_pose_command_step,
    )
    from gr00t.rl.trl.utils.common import custom_instantiate
    from gr00t.rl.utils.helpers import pre_process_config
    from scriptsFORhuman.v29.v29_runtime_evidence import V29RuntimeEvidence

    # Explicit reference inputs replace only this process's selector result.
    # Production generation, robot, sensors, dynamics and target consumers remain
    # the same implementation used by the approved baseline configuration.
    simulator_module = importlib.import_module("gr00t.rl.simulator.isaacsim.isaacsim")
    original_selector = simulator_module._get_task_obj_cfg_dict_for_door_eval

    def reference_selector(task_module, env_config, num_envs):
        result = original_selector(task_module, env_config, num_envs)
        door = result["door"]
        template = door.spawn.assets_cfg[0]
        variants = []
        for case in cases:
            variants.append(template.replace(
                rand_door_open_lr=case["side"], door_open_lr=[case["side"]],
                rand_door_open_io="out", rand_door_handle_height=case["handle_height_m"],
                rand_door_width=case["door_width_m"], rand_door_height=case["door_height_m"],
                rand_door_handle_width=case["handle_width_m"],
                rand_door_weight=case["dynamics"]["mass_kg"],
                rand_total_wall_height=2.4, rand_handle_drive_max_force=2.0,
                v29_handle=case["handle"], v29_dynamics=case["dynamics"],
            ))
        return {**result, "door": door.replace(spawn=door.spawn.replace(assets_cfg=variants, random_choice=False))}

    simulator_module._get_task_obj_cfg_dict_for_door_eval = reference_selector
    original_scene = DoorPregrasp.scene_creation_callback

    def reference_scene(self, simulator):
        original_scene(self, simulator)
        simulator.scene.sensors["v29_panel_finger_contact"] = ContactSensor(ContactSensorCfg(
            prim_path="/World/envs/env_.*/door/door_panel", track_pose=True,
            track_contact_points=True, max_contact_data_count_per_prim=128,
            filter_prim_paths_expr=["/World/envs/env_.*/Robot/arm_body7", "/World/envs/env_.*/Robot/arm_body8"],
        ))
        if args.render:
            simulator.scene.sensors["v29_reference_camera"] = Camera(CameraCfg(
                prim_path="/World/envs/env_.*/V29ReferenceCamera", width=640, height=480,
                data_types=["rgb"], update_period=0.,
                spawn=sim_utils.PinholeCameraCfg(focal_length=24., horizontal_aperture=20.955,
                                                clipping_range=(.01, 20.)),
            ))

    DoorPregrasp.scene_creation_callback = reference_scene
    np.random.seed(291)
    torch.manual_seed(291)
    pre_process_config(config)
    config.env.config.save_rendering_dir = str(args.output / "renderings")
    config.env.config.experiment_dir = str(args.output)
    env = custom_instantiate(config.env, device=args.device, _resolve=False)
    env.reset_all()
    evidence = V29RuntimeEvidence(args.output / "runtime")
    evidence.capture(env, "natural_reset_before_reference_fixture", 0)

    if args.staged_lifecycle_only:
        run_staged_lifecycle(env, evidence, args)
        return

    scene, sim = env.simulator.scene, env.simulator.sim
    robot = scene.articulations["robot"]
    frame_sensor = env._get_a2_gripper_handle_frame_transformer()
    handle_sensor = scene.sensors[env.A2_GRIPPER_HANDLE_CONTACT_SENSOR]
    panel_sensor = scene.sensors["v29_panel_finger_contact"]
    arm_panel_sensor = scene.sensors[env.A2_DOOR_ARM_PANEL_CONTACT_SENSOR]
    handle_body_ids, _ = scene.articulations["door"].find_bodies("door_handle", preserve_order=True)
    arm_ids, arm_names = robot.find_joints([f"arm_j{i}" for i in range(1, 7)], preserve_order=True)
    finger_ids, finger_names = robot.find_joints(["arm_j7", "arm_j8"], preserve_order=True)
    body_ids, _ = robot.find_bodies("arm_body6_to_gripper", preserve_order=True)
    body_id = body_ids[0]
    jacobian_columns = [index + 6 for index in arm_ids]
    root_fixture = robot.data.root_state_w.clone()
    grasp = frame_sensor.data.target_pos_w[:, 0]
    root_fixture[:, 0] = grasp[:, 0] - args.standoff
    root_fixture[:, 1] = grasp[:, 1]
    root_fixture[:, 2] = env.env_origins[:, 2] + .50
    root_fixture[:, 3:7] = root_fixture.new_tensor([1., 0., 0., 0.])
    root_fixture[:, 7:] = 0.
    joint_target = robot.data.default_joint_pos.clone()
    ik_plan = json.loads(args.ik_plan.read_text())
    plans_by_label = {case["label"]: case for case in ik_plan["cases"]}
    fixture_arm_q = joint_target.new_tensor([plans_by_label[case["label"]]["pregrasp_arm_q"] for case in cases])
    joint_target[:, arm_ids] = fixture_arm_q
    open_target = joint_target.new_tensor(list(config.env.config.a2_base.gripper_open_target))
    close_target = joint_target.new_tensor(list(config.env.config.a2_base.gripper_close_target))
    joint_target[:, finger_ids] = open_target
    robot.write_joint_state_to_sim(joint_target, torch.zeros_like(joint_target))
    robot.set_joint_position_target(joint_target)
    robot.write_root_state_to_sim(root_fixture)
    scene.write_data_to_sim()
    sim.step(render=False)
    physics_dt = float(sim.get_physics_dt())
    scene.update(physics_dt)
    phases = [("pregrasp", args.pregrasp_steps, 1), ("approach", args.approach_steps, 0),
              ("close", args.close_steps, 0)]
    summary = {"claim": "Reference geometry/contact only; root held as bench fixture",
               "manifest": str(args.manifest.resolve()), "num_envs": env.num_envs,
               "root_fixture_state_w": root_fixture.cpu().tolist(),
               "arm_joint_names": arm_names, "finger_joint_names": finger_names,
               "arm_panel_filter_paths": list(arm_panel_sensor.cfg.filter_prim_paths_expr),
               "contact_force_semantics": "normal forces; tangential friction is not included",
               "contact_capacity_per_prim": handle_sensor.cfg.max_contact_data_count_per_prim,
               "reference_ik": "integrated drive-target DLS, lambda=.01, Cartesian error gain1/s, scipy BVLS/native bounds; no post-solve clipping",
               "ik_plan": str(args.ik_plan.resolve()), "fixture_preposition_arm_q_rad": fixture_arm_q.cpu().tolist(),
               "control_dt_seconds": float(env.dt), "physics_dt_seconds": physics_dt,
               "phases": [], "cases": cases}
    with (args.output / "reference_trace.jsonl").open("w") as stream, torch.no_grad():
        for phase, count, target_index in phases:
            for step in range(count):
                frame = frame_sensor.data
                root_pos, root_quat = robot.data.root_pos_w, robot.data.root_quat_w
                source_pos, source_quat = subtract_frame_transforms(root_pos, root_quat, frame.source_pos_w, frame.source_quat_w)
                target_pos, target_quat = subtract_frame_transforms(root_pos, root_quat, frame.target_pos_w[:, target_index], frame.target_quat_w[:, target_index])
                body_pos = quat_apply_inverse(root_quat, robot.data.body_pos_w[:, body_id] - root_pos)
                jacobian = robot.root_physx_view.get_jacobians()[:, body_id, :, jacobian_columns]
                jacobian = a2_hold_rotate_jacobian_to_root(jacobian, root_quat)
                jacobian = a2_hold_apply_source_offset_to_jacobian(jacobian, source_pos - body_pos)
                pose_error = torch.cat((target_pos - source_pos,
                                        axis_angle_from_quat(quat_mul(target_quat, quat_inv(source_quat)))), dim=-1)
                command_pos, command_quat = apply_delta_pose(source_pos, source_quat, float(env.dt) * pose_error)
                _, _, _, _, bounded_delta = a2_hold_bound_pose_command_step(
                    source_pos, source_quat, command_pos, command_quat, .002, .02)
                limits = robot.data.joint_pos_limits[:, arm_ids]
                desired_np, active_bounds = bounded_dls_targets(
                    jacobian.cpu().numpy().astype(np.float64),
                    joint_target[:, arm_ids].cpu().numpy().astype(np.float64),
                    bounded_delta.cpu().numpy().astype(np.float64),
                    limits.cpu().numpy().astype(np.float64),
                )
                desired = torch.as_tensor(desired_np, device=args.device, dtype=joint_target.dtype)
                if not torch.isfinite(desired).all() or ((desired < limits[..., 0]) | (desired > limits[..., 1])).any():
                    (args.output / "invalid_dls_target.json").write_text(json.dumps({
                        "phase": phase, "step": step, "joint_names": arm_names,
                        "current_q": robot.data.joint_pos[:, arm_ids].cpu().tolist(),
                        "desired_q": desired.cpu().tolist(), "limits": limits.cpu().tolist(),
                    }, indent=2) + "\n")
                    raise RuntimeError(f"Reference DLS invalid joint target in {phase} step {step}; no clipping applied")
                joint_target[:, arm_ids] = desired
                fraction = (step + 1) / count if phase == "close" else 0.
                joint_target[:, finger_ids] = open_target * (1. - fraction) + close_target * fraction
                robot.set_joint_position_target(joint_target)
                for _ in range(round(float(env.dt) / physics_dt)):
                    robot.write_root_state_to_sim(root_fixture)
                    scene.write_data_to_sim()
                    sim.step(render=False)
                    scene.update(physics_dt)
                frame = frame_sensor.data
                position_error = (frame.source_pos_w - frame.target_pos_w[:, target_index]).norm(dim=-1)
                rotation_error = axis_angle_from_quat(quat_mul(frame.target_quat_w[:, target_index], quat_inv(frame.source_quat_w))).norm(dim=-1)
                row = {"phase": phase, "step": step,
                       "ik_active_bounds": active_bounds,
                       "arm_q_rad": robot.data.joint_pos[:, arm_ids].cpu().tolist(),
                       "arm_q_target_rad": desired.cpu().tolist(),
                       "position_error_m": position_error.cpu().tolist(), "orientation_error_rad": rotation_error.cpu().tolist(),
                       "finger_q_m": robot.data.joint_pos[:, finger_ids].cpu().tolist(),
                       "finger_handle_normal_force_w_n": handle_sensor.data.force_matrix_w.cpu().tolist(),
                       "finger_panel_including_rose_normal_force_w_n": panel_sensor.data.force_matrix_w.cpu().tolist(),
                       "arm_panel_including_rose_normal_force_w_n": arm_panel_sensor.data.force_matrix_w.cpu().tolist(),
                       "door_handle_pos_w": scene.articulations["door"].data.body_pos_w[:, handle_body_ids[0]].cpu().tolist(),
                       "door_handle_quat_wxyz": scene.articulations["door"].data.body_quat_w[:, handle_body_ids[0]].cpu().tolist(),
                       "door_q_rad": scene.articulations["door"].data.joint_pos.cpu().tolist()}
                # Preserve every real contact point, rather than substituting a
                # mean point for curved-main/return contact localization.
                forces, points, normals, distances, counts, starts = handle_sensor.contact_physx_view.get_contact_data(dt=physics_dt)
                pairs = []
                for env_id in range(env.num_envs):
                    for finger in range(2):
                        start, size = int(starts[env_id, finger]), int(counts[env_id, finger])
                        if size:
                            pairs.append({"env_id": env_id, "finger": finger,
                                          "points_w": points[start:start+size].cpu().tolist(),
                                          "normal_forces_n": forces[start:start+size].cpu().tolist(),
                                          "normals_w": normals[start:start+size].cpu().tolist(),
                                          "separation_m": distances[start:start+size].cpu().tolist()})
                row["handle_contact_points"] = pairs
                row["handle_contact_counts"] = counts.cpu().tolist()
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                if step == count - 1:
                    summary["phases"].append(row)
                    if args.render:
                        from PIL import Image
                        camera = scene.sensors["v29_reference_camera"]
                        target = frame.target_pos_w[:, 0]
                        eye = target + target.new_tensor([-.45, -.35, .20])
                        camera.set_world_poses_from_view(eye, target)
                        for _ in range(4):
                            sim.render()
                        camera.update(physics_dt, force_recompute=True)
                        image_dir = args.output / "keyframes"
                        image_dir.mkdir(exist_ok=True)
                        rgb = camera.data.output["rgb"][..., :3].cpu().numpy()
                        for index, case in enumerate(cases):
                            Image.fromarray(rgb[index]).save(image_dir / f"{case['label']}_{phase}.png")
            stream.flush()
    evidence.capture(env, "after_reference_fixture", sum(count for _, count, _ in phases), export_assets=False)
    (args.output / "reference_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    # Separate initial-state interventions for B01/B04 readback. The solver
    # evolves each door freely after one initialization; no door q/qdot writes
    # occur inside either response window.
    door = scene.articulations["door"]
    hinge_id = env._a2_v24_friction_backend.hinge_joint_id
    root_fixture[:, 0] = env.env_origins[:, 0] - 4.
    root_fixture[:, 1] = env.env_origins[:, 1]
    dynamics_records = []
    for label, steps in (("release", args.dynamics_steps), ("native_upper_limit", args.limit_steps)):
        if steps == 0:
            continue
        positions = torch.zeros_like(door.data.joint_pos)
        velocities = torch.zeros_like(positions)
        if label == "release":
            positions[:, hinge_id] = torch.minimum(env.door_max_opening_rad - .10,
                                                   env.door_max_opening_rad.new_full((env.num_envs,), np.pi / 2))
        else:
            positions[:, hinge_id] = env.door_max_opening_rad - .03
            velocities[:, hinge_id] = .40
        door.write_joint_state_to_sim(positions, velocities)
        for step in range(steps):
            for _ in range(round(float(env.dt) / physics_dt)):
                robot.write_root_state_to_sim(root_fixture)
                scene.write_data_to_sim()
                sim.step(render=False)
                scene.update(physics_dt)
            dynamics_records.append({"phase": label, "step": step,
                                     "q_rad": door.data.joint_pos[:, hinge_id].cpu().tolist(),
                                     "qdot_rad_s": door.data.joint_vel[:, hinge_id].cpu().tolist(),
                                     "native_limits_rad": door.root_physx_view.get_dof_limits()[:, hinge_id].cpu().tolist()})
    (args.output / "dynamics_response.json").write_text(json.dumps(dynamics_records, allow_nan=False) + "\n")
    env.reset_all()
    evidence.capture(env, "natural_reset_after_reference", 0, export_assets=False)


def run_staged_lifecycle(env, evidence, args):
    """Exercise production stage advancement, snapshot creation and restore."""
    import torch

    robot = env.simulator.scene.articulations["robot"]
    actions = torch.zeros((env.num_envs, 24), device=env.device, dtype=torch.float32)
    pending_before = env.need_to_refresh_envs.cpu().tolist()
    # reset_all writes the natural state but leaves its queued refresh for the
    # first real step. Consume that lifecycle operation before the fixture.
    env.step({"actions": actions})
    transitions = [{"phase": "natural_reset_flush", "step": 0,
                    "pending_refresh_before": pending_before,
                    "pending_refresh_after": env.need_to_refresh_envs.cpu().tolist(),
                    "stage": env.stage_buf.cpu().tolist(),
                    "sample_counts": env.staged_reset_num_samples.cpu().tolist()}]
    root = robot.data.root_state_w.clone()
    grasp = env._compute_grasp_target()
    root[:, 0] = grasp[:, 0] - .70
    root[:, 1] = grasp[:, 1]
    root[:, 7:] = 0.
    robot.write_root_state_to_sim(root)
    robot.write_joint_state_to_sim(robot.data.default_joint_pos, torch.zeros_like(robot.data.default_joint_pos))
    env.simulator.scene.write_data_to_sim()
    # Exercise the production transition and snapshot callbacks through real
    # control ticks, without editing reset flags, stage state, or the bank.
    for step in range(3):
        env.step({"actions": actions})
        transitions.append({"phase": "fixture", "step": step + 1,
                            "stage": env.stage_buf.cpu().tolist(),
                            "root_state_w": robot.data.root_state_w.cpu().tolist(),
                            "grasp_target_w": env._compute_grasp_target().cpu().tolist(),
                            "physical_base_commands": env.get_physical_homie_commands().cpu().tolist(),
                            "pending_refresh": env.need_to_refresh_envs.cpu().tolist(),
                            "sample_counts": env.staged_reset_num_samples.cpu().tolist()})
    evidence.capture(env, "before_staged_restore", 4, export_assets=False)
    (args.output / "staged_transition.json").write_text(json.dumps(transitions, indent=2) + "\n")
    if not (env.staged_reset_num_samples[1] > 0).all():
        raise RuntimeError("Reference staging fixture did not create stage1 production snapshots for every case")
    snapshots = {
        name: {field: env.staged_reset_buf[name][field][1, 0].cpu().tolist()
               for field in ("root_state", "dof_state")}
        for name in ("robot", "door")
    }
    (args.output / "stage1_first_production_snapshot.json").write_text(json.dumps(snapshots, indent=2) + "\n")
    # Use the public wrapper to apply the robot targets selected by the real
    # staged reset as well as the door states restored inside reset_envs_idx.
    env.reset_all()
    receipt = env.get_a2_v24_last_reset_friction_receipt()
    (args.output / "staged_reset_receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    evidence.capture(env, "after_staged_restore", 4, export_assets=False)


if __name__ == "__main__":
    main()
