#!/usr/bin/env python3
"""r6 Phase D1: visual-frame-sensitivity probe (typed EXPLORATORY_NON_PAIRED).

Runs the staging-band probe loop for a fixed horizon with one of three vision
modes: ``live`` (production camera capture), ``frozen-mujoco`` (t=0 MuJoCo
frames held constant), ``isaac-frames`` (fixed Isaac RGB frames substituted
into the policy input). Records the physical base-command norm trajectory.
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

SIZES = {"left": (384, 216), "right": (384, 216), "head": (136, 384)}


def _load_isaac_frames(frame_dir: Path) -> dict[str, np.ndarray]:
    frames = {}
    for name in CAMERA_NAMES:
        path = frame_dir / f"{name}.png"
        image = Image.open(path.resolve(strict=True)).convert("RGB")
        height, width = SIZES[name]
        resized = image.size != (width, height)
        if resized:
            image = image.resize((width, height), Image.Resampling.BILINEAR)
        frames[name] = np.asarray(image, dtype=np.uint8)
    return frames


def run_mode(
    *,
    mode: str,
    manifest: Path,
    robot_xml: Path,
    bundle_dir: Path,
    student_source_root: Path,
    a2_base_policy: Path,
    resolved_config: Path,
    isaac_frame_dir: Path | None,
    output_dir: Path,
    dx: float,
    horizon: int,
    seed: int,
    case: str,
) -> dict:
    manifest_data = json.loads(manifest.resolve(strict=True).read_text(encoding="utf-8"))
    manifest_dir = manifest.resolve(strict=True).parent
    case_data = next(item for item in manifest_data["cases"] if item["case_id"] == case)
    instance_path = (manifest_dir / case_data["door_instance_path"]).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(instance_path)
    np.random.seed(seed)
    torch.manual_seed(seed)
    bundle_manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    image_mean = bundle_manifest["camera_rig"]["image_mean"]
    image_std = bundle_manifest["camera_rig"]["image_std"]
    native_contract = ResolvedNativePositionContractR4.from_config(resolved_config)
    warp_contract = ResolvedActionWarpContractR5.from_config(resolved_config)

    scene_dir = output_dir / f"scene_{mode}"
    scene_dir.mkdir(parents=True, exist_ok=True)
    scene_xml = scene_dir / "scene.xml"
    door_xml = scene_dir / "door_r4.xml"
    external_scene = scene_dir / "external_pd_source_scene.xml"
    native_scene = scene_dir / "native_position_scene_r4.xml"
    MjcfDoorBuilderR4(spec).write(door_xml, scene_dir / "door_build_report_r4.json")
    PairedSceneBuilderV2(
        robot_xml,
        door_xml,
        armature_by_joint=native_contract.values_by_joint(native_contract.armature),
    ).write(external_scene, scene_dir / "source_scene_build_report_v2.json")
    NativePositionSceneR4(external_scene, native_contract).write(
        native_scene, scene_dir / "native_position_scene_build_report_r4.json"
    )
    PolicyVisualSceneR4(native_scene).write(scene_xml, scene_dir / "policy_visual_scene_report_r4.json")

    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    grasp_site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "door_grasp_target")
    mujoco.mj_forward(model, data)
    grasp = data.site_xpos[grasp_site_id].copy()
    data.qpos[0] = float(grasp[0]) - dx
    data.qpos[1] = float(grasp[1])
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)

    render_option = policy_scene_option_r4()
    renderers = {
        name: mujoco.Renderer(model, height=h, width=w)
        for name, (h, w) in SIZES.items()
    }
    if mode == "isaac-frames":
        if isaac_frame_dir is None:
            raise ValueError("isaac-frames mode requires --isaac-frame-dir")
        cached_rgb = _load_isaac_frames(isaac_frame_dir)
        frame_source = "FIXED_ISAAC_FRAMES_SUBSTITUTED"
    else:
        cached_rgb = {}
        for name in CAMERA_NAMES:
            renderers[name].update_scene(
                data, camera=f"{name}_policy", scene_option=render_option
            )
            cached_rgb[name] = renderers[name].render().copy()
        frame_source = (
            "FROZEN_MUJOCO_T0_FRAMES" if mode == "frozen-mujoco" else "LIVE_CAPTURE"
        )

    actor = _load_actor(bundle_dir, student_source_root)
    actor.init_rollout()
    actor.reset()
    a2_policy = torch.jit.load(str(a2_base_policy), map_location="cpu").eval()
    robot_contract = resolved_a2_piper_contract()
    actuator_map = NameResolvedPositionActuatorMapR4.from_model(
        model, native_contract.joint_names
    )
    joint_map = A2PiperJointMap.from_sim_joint_names(
        robot_contract.sim_joint_names, device="cpu"
    )
    default32 = torch.tensor(robot_contract.default_dof_pos, dtype=torch.float32).unsqueeze(0)
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
    norms = []
    initial_root = data.qpos[:3].copy()
    frames_pil = {name: Image.fromarray(cached_rgb[name]) for name in CAMERA_NAMES}
    for name in CAMERA_NAMES:
        frames_pil[name].save(output_dir / f"input_frame_{mode}_{name}.png")
    for policy_step in range(horizon):
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
            if mode == "live":
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
    material = np.asarray(norms, dtype=np.float64)
    final_root = data.qpos[:3].copy()
    return {
        "mode": mode,
        "frame_source": frame_source,
        "seed": seed,
        "dx": dx,
        "policy_steps": horizon,
        "physical_base_command_norm_first3": {
            "min": float(material.min()),
            "p10": float(np.percentile(material, 10)),
            "p50": float(np.percentile(material, 50)),
            "max": float(material.max()),
        },
        "base_still_steps": int(np.sum(material <= 0.1)),
        "net_root_x_m": float(final_root[0] - initial_root[0]),
        "norms": [float(v) for v in material],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--student-source-root", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--isaac-frame-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--modes", default="live,frozen-mujoco")
    parser.add_argument("--dx", type=float, default=0.65)
    parser.add_argument("--horizon", type=int, default=200)
    parser.add_argument("--seed", type=int, default=41001)
    parser.add_argument("--case", default="p00_baseline")
    args = parser.parse_args()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        results[mode] = run_mode(
            mode=mode,
            manifest=args.manifest,
            robot_xml=args.robot,
            bundle_dir=args.bundle_dir,
            student_source_root=args.student_source_root,
            a2_base_policy=args.a2_base_policy,
            resolved_config=args.resolved_config,
            isaac_frame_dir=args.isaac_frame_dir,
            output_dir=output_dir,
            dx=args.dx,
            horizon=args.horizon,
            seed=args.seed,
            case=args.case,
        )
        print(
            json.dumps(
                {
                    "mode": mode,
                    "min_norm": results[mode]["physical_base_command_norm_first3"]["min"],
                    "base_still_steps": results[mode]["base_still_steps"],
                    "net_root_x_m": results[mode]["net_root_x_m"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    live = results.get("live")
    frozen = results.get("frozen-mujoco")
    isaac = results.get("isaac-frames")
    summary = {"typed": "EXPLORATORY_NON_PAIRED"}
    if frozen is not None and live is not None:
        summary["frozen_vs_live_min_norm_delta"] = (
            frozen["physical_base_command_norm_first3"]["min"]
            - live["physical_base_command_norm_first3"]["min"]
        )
    if isaac is not None and frozen is not None:
        delta = isaac["physical_base_command_norm_first3"]["min"] - frozen[
            "physical_base_command_norm_first3"
        ]["min"]
        summary["isaac_vs_frozen_mujoco_min_norm_delta"] = delta
        if isaac["base_still_steps"] > 0 and frozen["base_still_steps"] == 0:
            summary["interpretation"] = "ISAAC_FRAME_CONTENT_ALONE_DROVES_BASE_STILL"
        elif isaac["physical_base_command_norm_first3"]["min"] < 0.1:
            summary["interpretation"] = "ISAAC_FRAMES_TRIGGERED_BASE_STILL"
        else:
            summary["interpretation"] = (
                "SINGLE_VISUAL_CHANNEL_NOT_SUFFICIENT_NO_CONVERGENCE_UNDER_ISAAC_FRAMES"
            )
    receipt = {
        "schema": "doordog.sim2sim.visual_sensitivity_probe.r6.v1",
        "result_classification": summary["typed"],
        "probe": "staging_band_stationary_init_same_seed",
        "frame_state_mismatch_disclosure": (
            "Isaac frames, when used, are fixed images whose capture state does not "
            "match the MuJoCo robot state; this probe measures sensitivity to frame "
            "content only and makes no paired claim"
        ),
        "results": {k: {kk: vv for kk, vv in v.items() if kk != "norms"} for k, v in results.items()},
        "summary": summary,
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
