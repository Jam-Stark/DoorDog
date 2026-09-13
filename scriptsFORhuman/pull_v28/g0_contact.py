#!/usr/bin/env python3
"""Pull G0 named mapping, target/control and zero-command contact probe.

Load a materialized pull_v28 YAML. This is a bounded runtime harness, not PPO
or natural-policy evaluation. E6/release events are never manufactured.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def finish_probe(code: int):
    # This disposable headless process owns no background writer. IsaacSim's
    # shutdown_and_release_framework can terminate Python with exit0 before a
    # pending traceback/SystemExit is delivered (observed in contact_a1).
    # Reports are closed before this call; process exit releases the GPU context.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    from omegaconf import OmegaConf
    from gr00t.rl.utils.config_utils import register_rl_resolvers
    register_rl_resolvers()
    cfg = OmegaConf.load(args.config)
    # A single 64-environment bilateral construction, with natural reset.
    for key, value in {
        "num_envs": 64, "headless": True, "use_wandb": False,
        "experiment_dir": str(args.output.resolve()),
        "output_dir": str(args.output.resolve() / "output"),
        "env.config.num_envs": 64, "env.config.headless": True,
        "env.config.simulator.config.scene.num_envs": 64,
        "simulator.config.scene.num_envs": 64,
        # Pull-v6 registers specialist buffers at construction. The established
        # natural evaluator keeps that mechanism enabled and samples only Stage0.
        "env.config.enable_staged_reset": True,
        "env.config.staged_reset_ratios": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "env.config.a2_pull_v6_stage4_bank_enabled": False,
        "env.config.a2_pull_v61_late_state_bank_enabled": False,
        "env.config.a2_door_open_lr_distribution": "bilateral",
        "env.config.experiment_dir": str(args.output.resolve()),
        "env.config.save_rendering_dir": str(args.output.resolve() / "renderings"),
    }.items():
        OmegaConf.update(cfg, key, value, force_add=True)
    OmegaConf.save(cfg, args.output / "resolved_config.yaml", resolve=True)

    from isaaclab.app import AppLauncher
    from gr00t.rl.train_agent_trl import patch_app_launcher_toolbar_hiding
    patch_app_launcher_toolbar_hiding(AppLauncher)
    app = AppLauncher(headless=True, device="cuda:0", enable_cameras=False).app
    try:
        import torch
        from isaaclab.utils.math import quat_inv, quat_mul
        from gr00t.rl.trl.utils.common import custom_instantiate
        from gr00t.rl.utils.helpers import pre_process_config
        from gr00t.rl.envs.door.door_open_a2_base import a2_wrist_motion_raw_penalty
        from gr00t.rl.envs.door.a2_pull_telemetry import A2PullEvent
        torch.manual_seed(int(cfg.seed))
        pre_process_config(cfg)
        env = custom_instantiate(cfg.env, device="cuda:0", _resolve=False)
        obs = env.reset_all()
        sim = env.simulator
        arm = env._upper_non_gripper_dof_idx
        names = list(sim.body_names)
        monitored = ["trunk", *[f"arm_body{i}" for i in range(7)], "wrist_camera_tower"]
        report = {"schema": "a2_piper_pull_v28_g0_contact_v1", "gates": {},
                  "evidence_level": "RUNTIME_AND_COMPUTED", "source_config": str(args.config.resolve()),
                  "scope": "PG1/2/3/5 and PG6 zero-command subset; no PPO/opening/Teacher claim"}
        gates = report["gates"]

        def save():
            report["status"] = "PASS" if all(gates.values()) else "FAIL"
            (args.output / "contact_probe.json").write_text(
                json.dumps(report, indent=2, allow_nan=False) + "\n")
            print(json.dumps({"status": report["status"], "gates": gates}), flush=True)

        gates["PG1_named_body_joint_contact_mapping"] = bool(
            sim.num_bodies == 28 and sim._robot.num_bodies == 28
            and sim.contact_sensor.num_bodies == 28 and len(sim.dof_names) == 20
            and names == list(cfg.env.config.robot.body_names)
            and list(sim.dof_names) == list(cfg.env.config.robot.dof_names)
            and [sim.contact_sensor.body_names[i] for i in sim.contact_to_body_idx] == names
            and all(name in names for name in monitored))
        report["mapping"] = {"body_names": names, "native_body_names": list(sim._robot.body_names),
            "contact_body_names": list(sim.contact_sensor.body_names),
            "contact_to_body_idx": list(sim.contact_to_body_idx), "dof_names": list(sim.dof_names)}
        if not gates["PG1_named_body_joint_contact_mapping"]:
            save()
            finish_probe(2)
        ids = [names.index(name) for name in monitored]
        default = env._get_a2_arm_default_dof_pos().expand(env.num_envs, -1)
        expected_default = default.new_tensor([0., .10, -.10, 0., -.415, 1.57])
        relative_obs = env._get_obs_dof_pos()[:, arm]
        report["anchors"] = {"default_rad": default[0].tolist(),
            "reset_arm_rad": sim.dof_pos[:, arm].tolist(),
            "reset_arm_observation_relative_rad": relative_obs.tolist(),
            "observation_anchor_error_max": float((relative_obs - (sim.dof_pos[:, arm] - default)).abs().max()),
            "cumulative_action_reset_abs_max": float(env._delta_actions.abs().max())}
        gates["PG2_default_action_observation_anchor"] = bool(
            torch.allclose(default, expected_default.expand_as(default), atol=1e-6, rtol=0)
            and torch.allclose(relative_obs, sim.dof_pos[:, arm] - default, atol=1e-6, rtol=0)
            and torch.all(env._delta_actions == 0))
        layout = env.get_a2_high_level_action_layout()
        report["action_layout"] = {"high_level": layout, "leg_action_dim": env._a2_leg_action_dim,
                                  "environment_action_dim": layout["dim"] + env._a2_leg_action_dim,
                                  "action_observation_dim": env._get_obs_actions().shape[-1]}
        policy_path = Path(cfg.algo.config.a2_base.policy_path)
        if not policy_path.is_absolute():
            policy_path = ROOT / policy_path
        policy = torch.jit.load(str(policy_path), map_location=env.device).eval()

        def actions():
            value = torch.zeros(env.num_envs, layout["dim"] + env._a2_leg_action_dim, device=env.device)
            value[:, layout["dim"]:] = policy(obs["a2_base_obs"])
            return value

        # Same handle-source quaternion observable as original pull G1. Reconstruct
        # the unmirrored target at this exact physical pose, without changing sensor.
        frame = env._get_a2_gripper_handle_frame_transformer()
        data = frame.data
        actual = data.target_quat_source[:, 0]
        offsets = frame._target_frame_offset_quat.reshape(env.num_envs, 2, 4)[:, 0]
        authored = actual.new_tensor(env._get_a2_grasp_target_orientation_wxyz()).expand_as(actual)
        unmirrored = quat_mul(quat_mul(actual, quat_inv(offsets)), authored)
        dots = ((actual * unmirrored).sum(-1).abs()
                / (actual.norm(dim=-1) * unmirrored.norm(dim=-1)))
        # Unit quaternion roundoff only, not a policy target clamp.
        angles = torch.rad2deg(2 * torch.acos(dots.clamp(0., 1.)))
        import omni.usd
        stage = omni.usd.get_context().get_stage()
        sides = [float(stage.GetPrimAtPath(f"/World/envs/env_{i}/door").GetMetadata("customData")["doorOpenLR"])
                 for i in range(env.num_envs)]
        left = torch.tensor([s == 1. for s in sides], device=env.device)
        right = ~left
        gates["PG5_same_pose_target_frame_mirror"] = bool(
            int(left.sum()) == 32 and int(right.sum()) == 32
            and torch.all((angles[left] - 180.).abs() <= .05)
            and torch.equal(offsets[right], authored[right]))
        report["target_frame"] = {"evidence": "actual runtime frame plus same-pose unmirrored calculation; not old/new policy equivalence",
            "door_open_lr": sides, "target_quat_source_handle": actual.tolist(),
            "unmirrored_target_quat_source_handle_computed": unmirrored.tolist(),
            "relative_angle_degrees": angles.tolist(), "left_tolerance_deg": .05,
            "right_authored_offset_unchanged": bool(torch.equal(offsets[right], authored[right]))}
        wv = torch.as_tensor(env.config.a2_wrist_motion_vel_weights, device=env.device)
        wr = torch.as_tensor(env.config.a2_wrist_motion_reversal_weights, device=env.device)
        expected_wv = wv.new_tensor([[.35]*3, [.5]*3, [.75]*3, [.5,.5,0], [.5,.5,.25], [1.25]*3])
        expected_wr = wr.new_tensor([[.5]*3, [.5]*3, [.5]*3, [.5,.5,.25], [.5]*3, [.5]*3])
        synthetic_dq = torch.ones(6, 3, device=env.device)
        raw = a2_wrist_motion_raw_penalty(synthetic_dq, -synthetic_dq,
                                         torch.arange(6, device=env.device), wv, wr)
        gates["PG3_fixed_wrist_table_computed"] = bool(
            torch.equal(wv, expected_wv) and torch.equal(wr, expected_wr)
            and torch.allclose(raw, (expected_wv + expected_wr).sum(-1)))
        report["wrist_computed"] = {"vel_weights": wv.tolist(), "reversal_weights": wr.tolist(),
                                   "synthetic_dq_1_prev_minus1_raw": raw.tolist(), "evidence": "COMPUTED"}
        records, camera_trace = [], []
        first = torch.ones(env.num_envs, dtype=torch.bool, device=env.device)
        # Record all first 50 control steps, including initialization contact.
        # There is no new height or wrist-speed gate.
        with torch.no_grad():
            for step in range(50):
                obs, reward, done, extras = env.step({"actions": actions()})
                first &= ~done.bool()
                forces = sim.contact_forces[:, ids].norm(dim=-1)
                gate = env._get_a2_pull_v28_post_release_mask()
                masks = env._get_a2_stage3_stage4_contact_squeeze_masks("pull G0 gate observation")
                expected_gate = (env._a2_pull_v6_release_event & ~masks["both_contact"] & (env.stage_buf == 4)
                    & ((env._a2_pull_v6_subphase == env._A2_PULL_V6_PHASE_C) | (env._a2_pull_v6_subphase == env._A2_PULL_V6_PHASE_D)))
                records.append({"step": step, "force_max_by_body_N": dict(zip(monitored, forces.amax(0).tolist())),
                    "tower_raw_mean": float(env._reward_penalty_a2_wrist_tower_contact().mean()),
                    "tower_raw_matches_force": bool(torch.equal(env._reward_penalty_a2_wrist_tower_contact(),
                        (sim.contact_forces[:, names.index("wrist_camera_tower")].norm(dim=-1) > 1).float())),
                    "base_command_abs_max": float(env.get_physical_base_command().abs().max()),
                    "stage_counts": torch.bincount(env.stage_buf, minlength=6).tolist(),
                    "done_count": int(done.sum()), "first_episode_active": int(first.sum()),
                    "release_event_count": int(env._a2_pull_v6_release_event.sum()),
                    "post_release_gate_count": int(gate.sum()), "gate_matches_persistent_event": bool(torch.equal(gate, expected_gate)),
                    "arm_speed_abs_max_rad_s": float(sim.dof_vel[:, arm].abs().max()),
                    "root_z_min_m": float(sim.robot_root_states[:, 2].min()),
                    "root_z_max_m": float(sim.robot_root_states[:, 2].max())})
                active_ids = first.nonzero().flatten()
                for index, camera in zip(active_ids.tolist(), env._get_a2_v28_camera_trace_fields(active_ids), strict=True):
                    camera.update(env_id=index, step_index=step, control_dt=float(env.dt),
                        stage_buf=int(env.stage_buf[index]), first_episode_active=True, episode_index=0,
                        arm_joint_pos=sim.dof_pos[index, arm].tolist(), arm_joint_vel=sim.dof_vel[index, arm].tolist())
                    camera_trace.append(camera)
            # A declared target-buffer stimulus after the contact window exercises
            # production DeltaActionBase.step, with no event or physical-state edit.
            # These two steps are excluded from zero-command contact acceptance.
            limits = sim.hard_dof_pos_limits[arm]
            clamp_rows = []
            for side, bound in (("upper", limits[:, 1]), ("lower", limits[:, 0])):
                obs = env.reset_all()
                delta_bound = (bound - default) / float(env.config.robot.control.action_scale)
                stimulus = delta_bound + (1. if side == "upper" else -1.)
                env._delta_actions[:] = stimulus
                # Observe the existing hook boundary: D17 has run, while the
                # production Stage0 override has not. Delegate without changes.
                sampled = {}
                original_override = env._apply_delta_action_overrides

                def observe_override():
                    sampled["pre_override"] = env._delta_actions.clone()
                    sampled["stage"] = env.stage_buf.clone()
                    original_override()
                    sampled["post_override"] = env._delta_actions.clone()

                env._apply_delta_action_overrides = observe_override
                try:
                    obs, _, done, _ = env.step({"actions": actions()})
                finally:
                    del env._apply_delta_action_overrides
                expected = stimulus.clamp(-float(env.config.delta_action_clip), float(env.config.delta_action_clip))
                expected = torch.maximum(torch.minimum(expected, (limits[:, 1] - default) / float(env.config.robot.control.action_scale)),
                                         (limits[:, 0] - default) / float(env.config.robot.control.action_scale))
                expected_executed = expected.clone()
                expected_executed[sampled["stage"] == env.STAGE_WALK_TO_DOOR] = 0.0
                target = default + float(env.config.robot.control.action_scale) * sampled["post_override"]
                # A2Base._get_obs_actions is leg12, arm6, gripper1, i.e.19.
                action_obs = env._get_obs_actions()[:, env._a2_leg_action_dim:env._a2_leg_action_dim + 6]
                passed = bool(not done.any()
                    and torch.allclose(sampled["pre_override"], expected, atol=1e-6, rtol=0)
                    and torch.allclose(sampled["post_override"], expected_executed, atol=1e-6, rtol=0)
                    and torch.allclose(env._delta_actions, expected_executed, atol=1e-6, rtol=0)
                    and torch.allclose(action_obs, expected_executed, atol=1e-6, rtol=0)
                    and torch.all(target >= limits[:, 0] - 1e-6) and torch.all(target <= limits[:, 1] + 1e-6))
                clamp_rows.append({"bound": side, "pass": passed, "done_count": int(done.sum()),
                    "stimulus_delta": stimulus[0].tolist(), "observed_delta": env._delta_actions[0].tolist(),
                    "d17_pre_override_delta": sampled["pre_override"][0].tolist(),
                    "expected_d17_delta": expected[0].tolist(),
                    "stage_at_override": sampled["stage"].tolist(),
                    "post_stage_override_delta": sampled["post_override"][0].tolist(),
                    "expected_executed_delta": expected_executed[0].tolist(),
                    "executed_action_observation": action_obs[0].tolist(), "target_rad": target[0].tolist()})
        gates["PG2_actual_delta_step_clamp"] = all(row["pass"] for row in clamp_rows)
        gates["PG3_tower_and_observed_release_gate"] = all(row["tower_raw_matches_force"] and row["gate_matches_persistent_event"] for row in records)
        gates["PG6_zero_command_contact_lt_1N"] = all(
            max(row["force_max_by_body_N"].values()) < 1. and row["base_command_abs_max"] == 0. for row in records)
        report.update(records=records, control_dt_s=float(env.dt), contact_window="first 50 control steps, no settle exclusion",
            clamp_probe={"stimulus": "cumulative buffer beyond physical limits, production env.step with zero high-level increment", "records": clamp_rows},
            late_event_evidence={"release_observed": any(row["release_event_count"] for row in records),
                "late_return_runtime_claim": None, "note": "No forced release/E6; zero-event truth-table agreement is not late-stage behavior proof"})
        (args.output / "camera_trace.json").write_text(json.dumps(camera_trace, indent=2, allow_nan=False) + "\n")
        save()
        finish_probe(0 if report["status"] == "PASS" else 2)
    except Exception as error:
        # Capture the real exception before any SimulationApp teardown can mask it.
        detail = traceback.format_exc()
        failure = {"schema": "a2_piper_pull_v28_g0_contact_v1", "status": "HARNESS_ERROR",
                   "source_config": str(args.config.resolve()),
                   "exception_type": type(error).__name__, "error": str(error),
                   "traceback": detail, "acceptance": "NOT_EVALUATED"}
        (args.output / "harness_error.json").write_text(json.dumps(failure, indent=2) + "\n")
        print(detail, file=sys.stderr, flush=True)
        finish_probe(1)


if __name__ == "__main__":
    raise SystemExit(main())
