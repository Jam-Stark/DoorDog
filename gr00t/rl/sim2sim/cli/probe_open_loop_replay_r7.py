#!/usr/bin/env python3
"""r7: open-loop replay of a reference Isaac rollout's command sequence in MuJoCo.

Feeds the recorded Isaac high-level actions (policy_action_mean) per policy
step instead of querying the Student, with live MuJoCo rendering and physics.
Yields (a) dynamics fidelity: does the MuJoCo robot reproduce the Isaac
approach trajectory under identical commands; (b) matched-trajectory frame
pairs (MuJoCo live vs Isaac recorded) for the pure visual gap.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
import torch
from PIL import Image

from gr00t.rl.sim2sim.cli.run_paired_mujoco_campaign import (
    CAMERA_NAMES,
    CAMERA_PERIODS,
    _body_state,
)
from gr00t.rl.sim2sim.doors.mjcf_builder_r4 import MjcfDoorBuilderR4
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_warp_r5 import (
    FullActionWarpR5,
    ResolvedActionWarpContractR5,
)
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.native_position_r4 import (
    NameResolvedPositionActuatorMapR4,
    NativePositionSceneR4,
    ResolvedNativePositionContractR4,
)
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import PairedSceneBuilderV2
from gr00t.rl.sim2sim.mujoco.policy_visual_scene_r4 import (
    PolicyVisualSceneR4,
    policy_scene_option_r4,
)
from gr00t.rl.sim2sim.mujoco.sensor_clock import SensorClock
from gr00t.rl.sim2sim.mujoco.stage_contract_minimal import StageContractMinimal
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract

SIZES = {"left": (384, 216), "right": (384, 216), "head": (136, 384)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--reference-dump", required=True, type=Path)
    parser.add_argument("--reference-env", type=int, default=0)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--case", default="p00_baseline")
    parser.add_argument("--horizon", type=int, default=600)
    parser.add_argument("--appearance", default="production")
    parser.add_argument("--markers", default="off")
    parser.add_argument("--prime-steps", type=int, default=-1,
                        help="if >=0, open-loop only for the first N steps, then closed-loop policy with live MuJoCo vision")
    parser.add_argument("--bundle-dir", type=Path)
    parser.add_argument("--student-source-root", type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in args.reference_dump.read_text(encoding="utf-8").splitlines()]
    ref = [r for r in rows if r["env_id"] == args.reference_env]
    # first episode only: cut at first done
    ep = []
    for r in ref:
        ep.append(r)
        if r["done"]:
            break
    commands = [r["policy_action_mean"] for r in ep]
    isaac_roots = np.asarray([r["root_pos_3d"] for r in ep])
    isaac_stages = [r["stage"] for r in ep]

    native_contract = ResolvedNativePositionContractR4.from_config(args.resolved_config)
    warp_contract = ResolvedActionWarpContractR5.from_config(args.resolved_config)
    manifest_data = json.loads(args.manifest.resolve(strict=True).read_text(encoding="utf-8"))
    case_data = next(item for item in manifest_data["cases"] if item["case_id"] == args.case)
    instance_path = (args.manifest.resolve(strict=True).parent / case_data["door_instance_path"]).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(instance_path)
    door_xml = output / "door_r4.xml"
    external_scene = output / "external_pd_source_scene.xml"
    native_scene = output / "native_position_scene_r4.xml"
    scene_xml = output / "scene.xml"
    MjcfDoorBuilderR4(spec).write(door_xml, output / "door_build_report_r4.json")
    PairedSceneBuilderV2(
        args.robot, door_xml,
        armature_by_joint=native_contract.values_by_joint(native_contract.armature),
    ).write(external_scene, output / "source_scene_build_report_v2.json")
    NativePositionSceneR4(external_scene, native_contract).write(native_scene, output / "native_position_scene_build_report_r4.json")
    PolicyVisualSceneR4(native_scene).write(scene_xml, output / "policy_visual_scene_report_r4.json")

    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    if args.appearance != "production":
        from gr00t.rl.sim2sim.cli.run_fishing_campaign_r7 import _apply_appearance
        _apply_appearance(model, args.appearance)
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    grasp_site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "door_grasp_target")
    mujoco.mj_forward(model, data)

    render_option = policy_scene_option_r4()
    renderers = {n: mujoco.Renderer(model, height=h, width=w) for n, (h, w) in SIZES.items()}
    cached_rgb = {}
    for name in CAMERA_NAMES:
        renderers[name].update_scene(data, camera=f"{name}_policy", scene_option=render_option)
        cached_rgb[name] = renderers[name].render().copy()

    a2_policy = torch.jit.load(str(args.a2_base_policy.resolve(strict=True)), map_location="cpu").eval()
    actor = None
    bundle_manifest = None
    if args.prime_steps >= 0:
        from gr00t.rl.sim2sim.cli.run_paired_mujoco_campaign import _load_actor
        from gr00t.rl.sim2sim.policy.observations import (
            build_actor_obs,
            compose_dual_rgb,
            normalize_rgb_nhwc,
        )
        actor = _load_actor(args.bundle_dir, args.student_source_root)
        actor.init_rollout()
        actor.reset()
        bundle_manifest = json.loads((args.bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    robot_contract = resolved_a2_piper_contract()
    actuator_map = NameResolvedPositionActuatorMapR4.from_model(model, native_contract.joint_names)
    joint_map = A2PiperJointMap.from_sim_joint_names(robot_contract.sim_joint_names, device="cpu")
    default32 = torch.tensor(robot_contract.default_dof_pos, dtype=torch.float32).unsqueeze(0)
    stage_tracker = StageContractMinimal(
        dtype=torch.float32, device="cpu",
        delta_scale=warp_contract.delta_action_scale, delta_clip=warp_contract.delta_action_clip,
    )
    action_warp = FullActionWarpR5(contract=warp_contract, joint_map=joint_map, stage_tracker=stage_tracker)
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    gait = SensorClock(batch_size=1, physics_dt=0.005, device="cpu", dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    previous_logical = torch.zeros((1, 19), dtype=torch.float32)
    previous_raw_delta = torch.zeros((1, 6), dtype=torch.float32)
    previous_base_raw = torch.zeros((1, 5), dtype=torch.float32)
    previous_base_physical = torch.zeros((1, 5), dtype=torch.float32)
    position_target = default32.clone()
    last_capture = {name: float(data.time) for name in CAMERA_NAMES}
    next_capture = dict(CAMERA_PERIODS)

    mujoco_roots = []
    norms = []
    frame_steps = {0, 20, 40, 44, 60, 90, 168, 274}
    trace_path = output / "replay_trace.jsonl"
    horizon = min(args.horizon, len(commands) - 1)
    with trace_path.open("w", encoding="utf-8") as trace:
        for step in range(horizon):
            local_angular_velocity, projected_gravity, roll_pitch, _ = _body_state(model, data, trunk_id)
            robot_qpos = data.qpos[actuator_map.robot_qpos_addresses].copy()
            robot_qvel = data.qvel[actuator_map.robot_qvel_addresses].copy()
            if args.prime_steps >= 0 and step >= args.prime_steps:
                actor_values = {
                    "base_ang_vel": torch.from_numpy(local_angular_velocity).float().unsqueeze(0),
                    "projected_gravity": torch.from_numpy(projected_gravity).float().unsqueeze(0),
                    "a2_student_dof_pos": torch.from_numpy(robot_qpos).float().unsqueeze(0) - default32,
                    "a2_student_dof_vel": torch.from_numpy(robot_qvel).float().unsqueeze(0),
                    "actions": previous_logical,
                    "delta_actions": previous_raw_delta,
                    "a2_base_command": action_warp.observation_command_echo(previous_base_physical),
                    "a2_base_command_raw": previous_base_raw,
                }
                actor_obs = build_actor_obs(bundle_manifest["observation"]["components"], actor_values)
                ages = [min(1.0, (float(data.time) - last_capture[n]) / 0.1) for n in CAMERA_NAMES]
                obs = {
                    "actor_obs": actor_obs,
                    "vision_obs": compose_dual_rgb(
                        torch.from_numpy(cached_rgb["left"].copy()).unsqueeze(0),
                        torch.from_numpy(cached_rgb["right"].copy()).unsqueeze(0),
                        image_mean=bundle_manifest["camera_rig"]["image_mean"],
                        image_std=bundle_manifest["camera_rig"]["image_std"],
                    ),
                    "context_vision_obs": normalize_rgb_nhwc(
                        torch.from_numpy(cached_rgb["head"].copy()).unsqueeze(0),
                        image_mean=bundle_manifest["camera_rig"]["image_mean"],
                        image_std=bundle_manifest["camera_rig"]["image_std"],
                    ),
                    "camera_meta": torch.tensor([[*ages, 1.0, 1.0, 1.0]], dtype=torch.float32),
                }
                with torch.inference_mode():
                    high_raw = actor.act_inference(obs)
            else:
                high_raw = torch.tensor([commands[step]], dtype=torch.float32)
            stage_action = stage_tracker.apply_high_level_action(high_raw)
            base_warp = action_warp.warp_base_command(stage_action.effective_high_level_action[:, :5])
            frame = frame_builder.build(
                projected_gravity=torch.from_numpy(projected_gravity).float().unsqueeze(0),
                dof_pos=torch.from_numpy(robot_qpos).float().unsqueeze(0),
                default_dof_pos=default32,
                dof_vel=torch.from_numpy(robot_qvel).float().unsqueeze(0),
                previous_leg_action=previous_leg,
                physical_base_command=base_warp.physical,
                base_roll_pitch=torch.from_numpy(roll_pitch).float().unsqueeze(0),
                gait_clock=gait.signal(),
            )
            with torch.inference_mode():
                leg_action = a2_policy(history.append(frame))
            warped = action_warp.compose_simulator_action(
                stage_action=stage_action, base=base_warp, policy_leg_action=leg_action, default_dof_pos=default32,
            )
            position_target = warped.position_target
            previous_leg = leg_action
            previous_logical = warped.logical_action
            previous_raw_delta = warped.stage_action.raw_arm_delta_echo
            previous_base_raw = high_raw[:, :5]
            previous_base_physical = warped.base.physical
            norm = float(torch.linalg.vector_norm(warped.base.physical[:, :3]))
            norms.append(norm)
            for _ in range(4):
                actuator_map.write_robot_position_target(data, position_target.squeeze(0).double().numpy())
                mujoco.mj_step(model, data)
                gait.advance(warped.base.physical[:, :3])
                for name in CAMERA_NAMES:
                    if float(data.time) + 1.0e-12 >= next_capture[name]:
                        renderers[name].update_scene(data, camera=f"{name}_policy", scene_option=render_option)
                        cached_rgb[name] = renderers[name].render().copy()
                        last_capture[name] = float(data.time)
                        next_capture[name] += CAMERA_PERIODS[name]
            if step in frame_steps:
                for name in CAMERA_NAMES:
                    Image.fromarray(cached_rgb[name]).save(output / f"mujoco_step{step:03d}_{name}.png")
            mujoco_roots.append(data.qpos[:3].copy())
            trace.write(json.dumps({
                "step": step, "t": float(data.time), "norm": norm,
                "root": data.qpos[:3].tolist(),
                "isaac_root": isaac_roots[step].tolist(),
                "isaac_stage": isaac_stages[step],
            }) + "\n")
    for r in renderers.values():
        r.close()

    mujoco_roots = np.asarray(mujoco_roots)
    isaac_rel = isaac_roots[:horizon] - isaac_roots[0]
    muj_rel = mujoco_roots - mujoco_roots[0]
    drift = np.linalg.norm(isaac_rel[:, :2] - muj_rel[:, :2], axis=1)
    receipt = {
        "schema": "doordog.sim2sim.open_loop_replay.r7.v1",
        "reference": "grpo rollout dump env0 episode0 (policy_action_mean open loop)",
        "horizon": horizon,
        "trajectory_drift_xy_m": {
            "at_step_44": float(drift[44]) if horizon > 44 else None,
            "at_step_168": float(drift[168]) if horizon > 168 else None,
            "at_final": float(drift[-1]),
            "max": float(drift.max()),
        },
        "isaac_final_rel_xy": isaac_rel[-1, :2].tolist(),
        "mujoco_final_rel_xy": muj_rel[-1, :2].tolist(),
        "norm_min": float(np.min(norms)),
        "frame_pairs_saved": sorted(frame_steps),
    }
    (output / "replay_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt["trajectory_drift_xy_m"]))


if __name__ == "__main__":
    main()
