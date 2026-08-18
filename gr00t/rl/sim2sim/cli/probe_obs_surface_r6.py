#!/usr/bin/env python3
"""r6 Phase B: per-step dump of the constructed 81D actor obs surface.

Re-executes the staging-band probe loop (identical seed/init/loop) on the
same llvmpipe backend and dumps the pre-normalization construction-layer
actor_obs at every policy step. Verifies t=0 analytic anchors, screens
per-component ranges, and re-checks determinism against the stored probe
trace.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
import torch

from gr00t.rl.sim2sim.cli.run_paired_mujoco_campaign import (
    CAMERA_NAMES,
    CAMERA_PERIODS,
    _body_state,
    _load_actor,
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
from gr00t.rl.sim2sim.policy.observations import (
    build_actor_obs,
    compose_dual_rgb,
    normalize_rgb_nhwc,
)
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract

COMPONENT_LAYOUT = [
    ("base_ang_vel", 0, 3, 0.5),
    ("projected_gravity", 3, 6, 1.0),
    ("a2_student_dof_pos", 6, 26, 1.0),
    ("a2_student_dof_vel", 26, 46, 0.05),
    ("actions", 46, 65, 1.0),
    ("delta_actions", 65, 71, 1.0),
    ("a2_base_command", 71, 76, 1.0),
    ("a2_base_command_raw", 76, 81, 1.0),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--student-source-root", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--stored-trace", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dx", type=float, default=0.65)
    parser.add_argument("--horizon", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=41001)
    parser.add_argument("--case", default="p00_baseline")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    manifest_data = json.loads(args.manifest.resolve(strict=True).read_text(encoding="utf-8"))
    manifest_dir = args.manifest.resolve(strict=True).parent
    case_data = next(item for item in manifest_data["cases"] if item["case_id"] == args.case)
    instance_path = (manifest_dir / case_data["door_instance_path"]).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(instance_path)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    bundle_manifest = json.loads((args.bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    image_mean = bundle_manifest["camera_rig"]["image_mean"]
    image_std = bundle_manifest["camera_rig"]["image_std"]
    native_contract = ResolvedNativePositionContractR4.from_config(args.resolved_config)
    warp_contract = ResolvedActionWarpContractR5.from_config(args.resolved_config)

    scene_xml = output / "scene.xml"
    door_xml = output / "door_r4.xml"
    external_scene = output / "external_pd_source_scene.xml"
    native_scene = output / "native_position_scene_r4.xml"
    MjcfDoorBuilderR4(spec).write(door_xml, output / "door_build_report_r4.json")
    PairedSceneBuilderV2(
        args.robot,
        door_xml,
        armature_by_joint=native_contract.values_by_joint(native_contract.armature),
    ).write(external_scene, output / "source_scene_build_report_v2.json")
    NativePositionSceneR4(external_scene, native_contract).write(
        native_scene, output / "native_position_scene_build_report_r4.json"
    )
    PolicyVisualSceneR4(native_scene).write(scene_xml, output / "policy_visual_scene_report_r4.json")

    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    grasp_site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "door_grasp_target")
    mujoco.mj_forward(model, data)
    home_quat_wxyz = data.qpos[3:7].copy()
    home_rotation = data.xmat[trunk_id].reshape(3, 3).copy()
    expected_gravity_t0 = home_rotation.T @ np.array([0.0, 0.0, -1.0])
    grasp = data.site_xpos[grasp_site_id].copy()
    data.qpos[0] = float(grasp[0]) - args.dx
    data.qpos[1] = float(grasp[1])
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)

    render_option = policy_scene_option_r4()
    sizes = {"left": (384, 216), "right": (384, 216), "head": (136, 384)}
    renderers = {
        name: mujoco.Renderer(model, height=h, width=w)
        for name, (h, w) in sizes.items()
    }
    cached_rgb = {}
    for name in CAMERA_NAMES:
        renderers[name].update_scene(data, camera=f"{name}_policy", scene_option=render_option)
        cached_rgb[name] = renderers[name].render().copy()

    actor = _load_actor(args.bundle_dir, args.student_source_root)
    actor.init_rollout()
    actor.reset()
    a2_policy = torch.jit.load(str(args.a2_base_policy), map_location="cpu").eval()
    robot_contract = resolved_a2_piper_contract()
    actuator_map = NameResolvedPositionActuatorMapR4.from_model(
        model, native_contract.joint_names
    )
    joint_map = A2PiperJointMap.from_sim_joint_names(
        robot_contract.sim_joint_names, device="cpu"
    )
    default32 = torch.tensor(robot_contract.default_dof_pos, dtype=torch.float32).unsqueeze(0)
    home_dof_pos = (
        torch.from_numpy(data.qpos[actuator_map.robot_qpos_addresses].copy())
        .float()
        .unsqueeze(0)
    )
    expected_dof_offset_t0 = (home_dof_pos - default32).squeeze(0).numpy()
    stage_tracker = StageContractMinimal(
        dtype=torch.float32,
        device="cpu",
        delta_scale=warp_contract.delta_action_scale,
        delta_clip=warp_contract.delta_action_clip,
    )
    action_warp = FullActionWarpR5(
        contract=warp_contract, joint_map=joint_map, stage_tracker=stage_tracker
    )
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    gait = SensorClock(batch_size=1, physics_dt=0.005, device="cpu", dtype=torch.float32)
    previous_logical = torch.zeros((1, 19), dtype=torch.float32)
    previous_raw_delta = torch.zeros((1, 6), dtype=torch.float32)
    previous_base_raw = torch.zeros((1, 5), dtype=torch.float32)
    previous_base_physical = torch.zeros((1, 5), dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    position_target = default32.clone()
    last_capture = {name: float(data.time) for name in CAMERA_NAMES}
    next_capture = dict(CAMERA_PERIODS)

    obs_rows = np.zeros((args.horizon, 81), dtype=np.float32)
    norms = []
    for policy_step in range(args.horizon):
        local_angular_velocity, projected_gravity, roll_pitch, _ = _body_state(
            model, data, trunk_id
        )
        robot_qpos = data.qpos[actuator_map.robot_qpos_addresses].copy()
        robot_qvel = data.qvel[actuator_map.robot_qvel_addresses].copy()
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
        actor_obs = build_actor_obs(
            bundle_manifest["observation"]["components"], actor_values
        )
        obs_rows[policy_step] = actor_obs.squeeze(0).numpy()
        ages = [
            min(1.0, (float(data.time) - last_capture[name]) / 0.1) for name in CAMERA_NAMES
        ]
        obs = {
            "actor_obs": actor_obs,
            "vision_obs": compose_dual_rgb(
                torch.from_numpy(cached_rgb["left"].copy()).unsqueeze(0),
                torch.from_numpy(cached_rgb["right"].copy()).unsqueeze(0),
                image_mean=image_mean,
                image_std=image_std,
            ),
            "context_vision_obs": normalize_rgb_nhwc(
                torch.from_numpy(cached_rgb["head"].copy()).unsqueeze(0),
                image_mean=image_mean,
                image_std=image_std,
            ),
            "camera_meta": torch.tensor([[*ages, 1.0, 1.0, 1.0]], dtype=torch.float32),
        }
        with torch.inference_mode():
            high_raw = actor.act_inference(obs)
        stage_action = stage_tracker.apply_high_level_action(high_raw)
        base_warp = action_warp.warp_base_command(
            stage_action.effective_high_level_action[:, :5]
        )
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
            stage_action=stage_action,
            base=base_warp,
            policy_leg_action=leg_action,
            default_dof_pos=default32,
        )
        position_target = warped.position_target
        previous_logical = warped.logical_action
        previous_raw_delta = warped.stage_action.raw_arm_delta_echo
        previous_base_raw = high_raw[:, :5]
        previous_base_physical = warped.base.physical
        previous_leg = leg_action
        norms.append(float(torch.linalg.vector_norm(warped.base.physical[:, :3])))
        for _ in range(4):
            actuator_map.write_robot_position_target(
                data, position_target.squeeze(0).double().numpy()
            )
            mujoco.mj_step(model, data)
            gait.advance(warped.base.physical[:, :3])
            for name in CAMERA_NAMES:
                if float(data.time) + 1.0e-12 >= next_capture[name]:
                    renderers[name].update_scene(
                        data, camera=f"{name}_policy", scene_option=render_option
                    )
                    cached_rgb[name] = renderers[name].render().copy()
                    last_capture[name] = float(data.time)
                    next_capture[name] += CAMERA_PERIODS[name]
    for renderer in renderers.values():
        renderer.close()

    np.savez_compressed(
        output / "actor_obs_surface.npz",
        actor_obs=obs_rows,
        home_quat_wxyz=home_quat_wxyz,
        expected_gravity_t0=expected_gravity_t0,
        expected_dof_offset_t0=expected_dof_offset_t0,
    )

    t0 = obs_rows[0]
    anchors = {
        "projected_gravity_vs_analytic_max_abs_diff": float(
            np.max(np.abs(t0[3:6] - expected_gravity_t0))
        ),
        "base_ang_vel_scaled_is_zero": bool(np.all(t0[0:3] == 0.0)),
        "dof_vel_scaled_is_zero": bool(np.all(t0[26:46] == 0.0)),
        "dof_pos_offset_vs_home_keyframe_max_abs_diff": float(
            np.max(np.abs(t0[6:26] - expected_dof_offset_t0))
        ),
        "actions_echo_zero": bool(np.all(t0[46:65] == 0.0)),
        "delta_actions_echo_zero": bool(np.all(t0[65:71] == 0.0)),
        "a2_base_command_echo_zero": bool(np.all(t0[71:76] == 0.0)),
        "a2_base_command_raw_echo_zero": bool(np.all(t0[76:81] == 0.0)),
    }
    dof_offset_zero_like = bool(
        np.max(np.abs(expected_dof_offset_t0)) < 1.0e-9
    )
    ranges = {}
    for name, lo, hi, scale in COMPONENT_LAYOUT:
        block = obs_rows[:, lo:hi]
        ranges[name] = {
            "scale": scale,
            "min": float(block.min()),
            "max": float(block.max()),
            "abs_max": float(np.abs(block).max()),
            "finite": bool(np.isfinite(block).all()),
        }
    stored_norms = [
        json.loads(line)["physical_base_command_norm_first3"]
        for line in args.stored_trace.read_text(encoding="utf-8").splitlines()
    ]
    diffs = np.abs(np.asarray(norms) - np.asarray(stored_norms[: len(norms)]))
    determinism = {
        "compared_steps": len(norms),
        "max_abs_norm_diff": float(diffs.max()),
        "row_identical": bool(len(norms) == len(stored_norms) and diffs.max() == 0.0),
    }
    anchor_pass = (
        anchors["projected_gravity_vs_analytic_max_abs_diff"] < 1.0e-6
        and anchors["base_ang_vel_scaled_is_zero"]
        and anchors["dof_vel_scaled_is_zero"]
        and anchors["dof_pos_offset_vs_home_keyframe_max_abs_diff"] < 1.0e-6
        and anchors["actions_echo_zero"]
        and anchors["delta_actions_echo_zero"]
        and anchors["a2_base_command_echo_zero"]
        and anchors["a2_base_command_raw_echo_zero"]
    )
    ranges_pass = all(item["finite"] for item in ranges.values())
    verdict = (
        "NONVISUAL_OBS_SURFACE_CLOSED"
        if anchor_pass and ranges_pass and determinism["row_identical"]
        else "NONVISUAL_OBS_SURFACE_ANOMALY_LISTED"
    )
    receipt = {
        "schema": "doordog.sim2sim.obs_surface_forensics.r6.v1",
        "typed_verdict": verdict,
        "loop": "staging_band_probe_r5 identical loop, seed 41001, dx 0.65, llvmpipe",
        "construction_layer": "pre running_mean_std: exactly the tensor fed as actor_obs",
        "coordinate_conventions": {
            "base_ang_vel": {
                "production": "distillation legged_robot_base.py:171 quat_rotate_inverse(base_quat, root_ang_vel) = body frame",
                "mujoco": "mj_objectVelocity(flg_local=1)[:3] = body frame; same convention",
            },
            "projected_gravity": {
                "production": "distillation legged_robot_base.py:199 quat_rotate_inverse(base_quat, [0,0,-1]) = body-frame unit down",
                "mujoco": "xmat.T @ [0,0,-1]; same convention",
            },
            "scales": "obs config door_open_a2_base.yaml:137-141 (base_ang_vel 0.5, dof_vel 0.05, projected_gravity 1.0) applied at construction, matching bundle manifest components",
        },
        "t0_anchors": anchors,
        "t0_anchor_notes": {
            "dof_pos_offset_expected_zero": dof_offset_zero_like,
            "detail": "dof_pos-default at t=0 equals the home keyframe minus default; if the keyframe equals default this is exactly zero",
        },
        "component_ranges_full_run": ranges,
        "determinism_vs_stored_probe_trace": determinism,
        "dump": str(output / "actor_obs_surface.npz"),
    }
    (output / "obs_surface_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "typed_verdict": verdict,
                "t0_anchors": anchors,
                "determinism": determinism,
                "component_abs_max": {
                    name: ranges[name]["abs_max"] for name, _, _, _ in COMPONENT_LAYOUT
                },
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
