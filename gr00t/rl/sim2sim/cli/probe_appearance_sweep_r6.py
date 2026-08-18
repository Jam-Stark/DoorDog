#!/usr/bin/env python3
"""r6 Phase D2: door/floor appearance sweep within the Isaac envelope.

Isaac truth (read from the frozen distillation source): door materials are
wood MDLs (Ash/Bamboo/Birch/Cherry planks family) with per-instance texture
rotate U[0,360] + translate U[0,100]^2 and diffuse_tint per channel
~ Exp(0.02). MuJoCo cannot reproduce the textures; this sweep brackets the
plausible appearance range with flat colors sampled around the production
door palette, including dark-tint and bright extremes. Typed EXPLORATORY.
"""

from __future__ import annotations

import argparse
import colorsys
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

SIZES = {"left": (384, 216), "right": (384, 216), "head": (136, 384)}
DOOR_GEOM_PREFIXES = (
    "door_frame_",
    "door_panel_collision",
    "door_inset_",
    "door_panel_band_",
    "handle_",
)


def _sample_variants(count: int, rng: np.random.Generator) -> list[dict]:
    variants = [
        {
            "name": "control_production",
            "panel_hsl": None,
            "frame_scale": 1.0,
            "floor_scale": 1.0,
            "brightness": 1.0,
        }
    ]
    for index in range(count):
        hue = float(rng.uniform(0.02, 0.13))
        sat = float(rng.uniform(0.15, 0.7))
        light = float(rng.uniform(0.2, 0.8))
        variants.append(
            {
                "name": f"wood_{index:02d}",
                "panel_hsl": (hue, sat, light),
                "frame_scale": float(rng.uniform(0.4, 1.1)),
                "floor_scale": float(rng.uniform(0.6, 1.3)),
                "brightness": float(rng.uniform(0.7, 1.3)),
            }
        )
    variants.append(
        {
            "name": "bracket_dark_tint_exp002",
            "panel_hsl": (0.08, 0.3, 0.03),
            "frame_scale": 0.3,
            "floor_scale": 0.4,
            "brightness": 0.5,
        }
    )
    variants.append(
        {
            "name": "bracket_bright_white",
            "panel_hsl": (0.10, 0.05, 0.92),
            "frame_scale": 1.1,
            "floor_scale": 1.3,
            "brightness": 1.35,
        }
    )
    return variants


def _apply_variant(model: mujoco.MjModel, variant: dict) -> None:
    if variant["panel_hsl"] is None:
        return
    r, g, b = colorsys.hls_to_rgb(
        variant["panel_hsl"][0], variant["panel_hsl"][2], variant["panel_hsl"][1]
    )
    r, g, b = (
        r * variant["brightness"],
        g * variant["brightness"],
        b * variant["brightness"],
    )
    frame_rgb = np.clip(
        (r, g, b), 0.0, 1.0
    ) * variant["frame_scale"]
    for geom_id in range(model.ngeom):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id) or ""
        if name.startswith(DOOR_GEOM_PREFIXES):
            rgba = model.geom_rgba[geom_id].copy()
            if name.startswith("door_frame_"):
                rgba[:3] = np.clip(frame_rgb, 0.0, 1.0)
            else:
                rgba[:3] = np.clip((r, g, b), 0.0, 1.0)
            model.geom_rgba[geom_id] = rgba
    for mat_id in range(model.nmat):
        mat_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_MATERIAL, mat_id) or ""
        if mat_name == "sim2sim_floor_material":
            rgba = model.mat_rgba[mat_id].copy()
            rgba[:3] = np.clip(rgba[:3] * variant["floor_scale"], 0.0, 1.0)
            model.mat_rgba[mat_id] = rgba


def run_variant(
    *,
    variant: dict,
    manifest: Path,
    robot_xml: Path,
    bundle_dir: Path,
    student_source_root: Path,
    a2_base_policy: Path,
    resolved_config: Path,
    output_dir: Path,
    dx: float,
    horizon: int,
    seed: int,
    case: str,
    scene_dir: Path,
    actor,
    a2_policy,
    native_contract,
    warp_contract,
) -> dict:
    manifest_data = json.loads(manifest.resolve(strict=True).read_text(encoding="utf-8"))
    case_data = next(item for item in manifest_data["cases"] if item["case_id"] == case)
    instance_path = (
        manifest.resolve(strict=True).parent / case_data["door_instance_path"]
    ).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(instance_path)
    if not scene_dir.exists():
        scene_dir.mkdir(parents=True)
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
        PolicyVisualSceneR4(native_scene).write(
            scene_dir / "scene.xml", scene_dir / "policy_visual_scene_report_r4.json"
        )
    scene_xml = scene_dir / "scene.xml"

    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    _apply_variant(model, variant)
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
    cached_rgb = {}
    for name in CAMERA_NAMES:
        renderers[name].update_scene(data, camera=f"{name}_policy", scene_option=render_option)
        cached_rgb[name] = renderers[name].render().copy()

    actor.init_rollout()
    actor.reset()
    bundle_manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    image_mean = bundle_manifest["camera_rig"]["image_mean"]
    image_std = bundle_manifest["camera_rig"]["image_std"]
    actuator_map = NameResolvedPositionActuatorMapR4.from_model(
        model, native_contract.joint_names
    )
    robot_contract = resolved_a2_piper_contract()
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
    return {
        "variant": variant["name"],
        "panel_hsl": variant["panel_hsl"],
        "brightness": variant["brightness"],
        "physical_base_command_norm_min": float(material.min()),
        "norm_p10": float(np.percentile(material, 10)),
        "norm_p50": float(np.percentile(material, 50)),
        "base_still_steps": int(np.sum(material <= 0.1)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--student-source-root", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--num-variants", type=int, default=24)
    parser.add_argument("--dx", type=float, default=0.65)
    parser.add_argument("--horizon", type=int, default=200)
    parser.add_argument("--seed", type=int, default=41001)
    parser.add_argument("--case", default="p00_baseline")
    args = parser.parse_args()
    output_dir = args.output.resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_dir = output_dir / "appearance_scene"
    actor = _load_actor(args.bundle_dir, args.student_source_root)
    a2_policy = torch.jit.load(str(args.a2_base_policy), map_location="cpu").eval()
    native_contract = ResolvedNativePositionContractR4.from_config(args.resolved_config)
    warp_contract = ResolvedActionWarpContractR5.from_config(args.resolved_config)
    rng = np.random.default_rng(20260819)
    variants = _sample_variants(args.num_variants, rng)
    results = []
    for variant in variants:
        result = run_variant(
            variant=variant,
            manifest=args.manifest,
            robot_xml=args.robot,
            bundle_dir=args.bundle_dir,
            student_source_root=args.student_source_root,
            a2_base_policy=args.a2_base_policy,
            resolved_config=args.resolved_config,
            output_dir=output_dir,
            dx=args.dx,
            horizon=args.horizon,
            seed=args.seed,
            case=args.case,
            scene_dir=scene_dir,
            actor=actor,
            a2_policy=a2_policy,
            native_contract=native_contract,
            warp_contract=warp_contract,
        )
        results.append(result)
        print(
            json.dumps(
                {
                    "variant": result["variant"],
                    "min_norm": result["physical_base_command_norm_min"],
                    "base_still_steps": result["base_still_steps"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    control = results[0]
    stopped = [item for item in results if item["base_still_steps"] > 0]
    receipt = {
        "schema": "doordog.sim2sim.appearance_sweep.r6.v1",
        "result_classification": "EXPLORATORY_FLAT_COLOR_BRACKET_NOT_TEXTURE_REPRODUCTION",
        "isaac_envelope_truth": (
            "wood MDL family (Ash/Bamboo/Birch/Cherry planks), texture rotate U[0,360], "
            "translate U[0,100]^2, diffuse_tint per-channel Exp(0.02); MuJoCo flat colors "
            "bracket the resulting luminance/hue range but do not reproduce textures"
        ),
        "control_min_norm": control["physical_base_command_norm_min"],
        "min_norm_across_variants": min(
            item["physical_base_command_norm_min"] for item in results
        ),
        "variants_with_base_still": [item["variant"] for item in stopped],
        "variant_count": len(results),
        "horizon": args.horizon,
        "results": results,
    }
    args.output.resolve().write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "variants": len(results),
                "stopped_variants": receipt["variants_with_base_still"],
                "min_norm_across_variants": receipt["min_norm_across_variants"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
