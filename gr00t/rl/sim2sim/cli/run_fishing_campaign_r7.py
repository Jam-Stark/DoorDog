#!/usr/bin/env python3
"""r7 fishing campaign: many short MuJoCo episodes hunting stage1+ events.

Each episode starts near the door with small init jitter (dx, dy, yaw),
runs the full r5 action warp with live policy cameras, and records command
norms plus door/root/arm observables. Episodes that reach stage1 are
extended to the full horizon to observe the manipulation chain.
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
from gr00t.rl.sim2sim.mujoco.stage_contract_minimal import (
    Stage0ObservableState,
    StageContractMinimal,
)
from gr00t.rl.sim2sim.policy.observations import (
    build_actor_obs,
    compose_dual_rgb,
    normalize_rgb_nhwc,
)
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract

SIZES = {"left": (384, 216), "right": (384, 216), "head": (136, 384)}


def build_scene(scene_dir: Path, manifest: Path, robot_xml: Path, native_contract, case: str) -> Path:
    manifest_data = json.loads(manifest.resolve(strict=True).read_text(encoding="utf-8"))
    case_data = next(item for item in manifest_data["cases"] if item["case_id"] == case)
    instance_path = (manifest.resolve(strict=True).parent / case_data["door_instance_path"]).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(instance_path)
    scene_dir.mkdir(parents=True, exist_ok=True)
    door_xml = scene_dir / "door_r4.xml"
    external_scene = scene_dir / "external_pd_source_scene.xml"
    native_scene = scene_dir / "native_position_scene_r4.xml"
    scene_xml = scene_dir / "scene.xml"
    if scene_xml.exists():
        return scene_xml
    MjcfDoorBuilderR4(spec).write(door_xml, scene_dir / "door_build_report_r4.json")
    PairedSceneBuilderV2(
        robot_xml, door_xml,
        armature_by_joint=native_contract.values_by_joint(native_contract.armature),
    ).write(external_scene, scene_dir / "source_scene_build_report_v2.json")
    NativePositionSceneR4(external_scene, native_contract).write(native_scene, scene_dir / "native_position_scene_build_report_r4.json")
    PolicyVisualSceneR4(native_scene).write(scene_xml, scene_dir / "policy_visual_scene_report_r4.json")
    return scene_xml


def _apply_appearance(model: mujoco.MjModel, appearance: str) -> None:
    if appearance == "production":
        return
    if appearance == "isaaclike":
        panel_rgb = (0.90, 0.88, 0.84)
        frame_rgb = (0.28, 0.30, 0.26)
        for geom_id in range(model.ngeom):
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id) or ""
            rgba = model.geom_rgba[geom_id].copy()
            if name.startswith("door_frame_"):
                rgba[:3] = frame_rgb
                model.geom_rgba[geom_id] = rgba
            elif name.startswith(
                ("door_panel_collision", "door_inset_", "door_panel_band_", "handle_")
            ):
                rgba[:3] = panel_rgb
                model.geom_rgba[geom_id] = rgba
        for mat_id in range(model.nmat):
            mat_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_MATERIAL, mat_id) or ""
            if mat_name == "sim2sim_floor_material":
                rgba = model.mat_rgba[mat_id].copy()
                rgba[:3] = np.clip(rgba[:3] * 1.8, 0.0, 1.0)
                model.mat_rgba[mat_id] = rgba
        return
    raise ValueError(f"unknown appearance {appearance!r}")


def run_episode(
    *,
    scene_xml: Path,
    actor,
    a2_policy,
    native_contract,
    warp_contract,
    bundle_manifest,
    dx: float,
    dy: float,
    yaw_deg: float,
    seed: int,
    short_horizon: int,
    full_horizon: int,
    trace_path: Path | None,
    appearance: str = "production",
) -> dict:
    np.random.seed(seed)
    torch.manual_seed(seed)
    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    _apply_appearance(model, appearance)
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    grasp_site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "door_grasp_target")
    door_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    door_qpos = int(model.jnt_qposadr[door_joint])
    handle_qpos = int(model.jnt_qposadr[handle_joint])
    mujoco.mj_forward(model, data)
    grasp = data.site_xpos[grasp_site_id].copy()
    data.qpos[0] = float(grasp[0]) - dx
    data.qpos[1] = float(grasp[1]) + dy
    if abs(yaw_deg) > 1e-9:
        yaw = np.deg2rad(yaw_deg)
        data.qpos[3] = np.cos(yaw / 2.0)
        data.qpos[6] = np.sin(yaw / 2.0)
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    door_plane_x = float(grasp[0])

    render_option = policy_scene_option_r4()
    renderers = {n: mujoco.Renderer(model, height=h, width=w) for n, (h, w) in SIZES.items()}
    cached_rgb = {}
    for name in CAMERA_NAMES:
        renderers[name].update_scene(data, camera=f"{name}_policy", scene_option=render_option)
        cached_rgb[name] = renderers[name].render().copy()

    actor.init_rollout()
    actor.reset()
    image_mean = bundle_manifest["camera_rig"]["image_mean"]
    image_std = bundle_manifest["camera_rig"]["image_std"]
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
    previous_logical = torch.zeros((1, 19), dtype=torch.float32)
    previous_raw_delta = torch.zeros((1, 6), dtype=torch.float32)
    previous_base_raw = torch.zeros((1, 5), dtype=torch.float32)
    previous_base_physical = torch.zeros((1, 5), dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    position_target = default32.clone()
    last_capture = {name: float(data.time) for name in CAMERA_NAMES}
    next_capture = dict(CAMERA_PERIODS)

    norms: list[float] = []
    max_handle = 0.0
    max_hinge = 0.0
    max_root_x = float(data.qpos[0])
    min_base_height = float(data.qpos[2])
    stage1_at = None
    extended = False
    trace_stream = trace_path.open("w", encoding="utf-8") if trace_path else None
    step = 0
    horizon = short_horizon
    while step < horizon:
        local_angular_velocity, projected_gravity, roll_pitch, _ = _body_state(model, data, trunk_id)
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
        actor_obs = build_actor_obs(bundle_manifest["observation"]["components"], actor_values)
        ages = [min(1.0, (float(data.time) - last_capture[n]) / 0.1) for n in CAMERA_NAMES]
        obs = {
            "actor_obs": actor_obs,
            "vision_obs": compose_dual_rgb(
                torch.from_numpy(cached_rgb["left"].copy()).unsqueeze(0),
                torch.from_numpy(cached_rgb["right"].copy()).unsqueeze(0),
                image_mean=image_mean, image_std=image_std,
            ),
            "context_vision_obs": normalize_rgb_nhwc(
                torch.from_numpy(cached_rgb["head"].copy()).unsqueeze(0),
                image_mean=image_mean, image_std=image_std,
            ),
            "camera_meta": torch.tensor([[*ages, 1.0, 1.0, 1.0]], dtype=torch.float32),
        }
        with torch.inference_mode():
            high_raw = actor.act_inference(obs)
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
        previous_logical = warped.logical_action
        previous_raw_delta = warped.stage_action.raw_arm_delta_echo
        previous_base_raw = high_raw[:, :5]
        previous_base_physical = warped.base.physical
        previous_leg = leg_action
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
        max_handle = max(max_handle, float(data.qpos[handle_qpos]))
        max_hinge = max(max_hinge, float(data.qpos[door_qpos]))
        max_root_x = max(max_root_x, float(data.qpos[0]))
        min_base_height = min(min_base_height, float(data.qpos[2]))
        root_position = torch.from_numpy(data.qpos[:3].copy()).float().unsqueeze(0)
        grasp_position = torch.from_numpy(data.site_xpos[grasp_site_id].copy()).float().unsqueeze(0)
        arm_position = torch.from_numpy(data.qpos[actuator_map.robot_qpos_addresses[12:18]].copy()).float().unsqueeze(0)
        advanced = stage_tracker.observe_after_step(
            Stage0ObservableState(
                root_position_m=root_position,
                grasp_target_position_m=grasp_position,
                arm_position_rad=arm_position,
                arm_default_position_rad=default32[:, 12:18],
                physical_base_command=warped.base.physical,
            )
        )
        if trace_stream is not None:
            trace_stream.write(json.dumps({
                "step": step, "t": float(data.time), "norm": norm,
                "root": root_position.squeeze(0).tolist(),
                "hinge": float(data.qpos[door_qpos]), "handle": float(data.qpos[handle_qpos]),
                "stage": stage_tracker.stage,
                "arm": arm_position.squeeze(0).tolist(),
            }) + "\n")
        if advanced and stage1_at is None:
            stage1_at = step
            if not extended:
                extended = True
                horizon = full_horizon
        if min_base_height < 0.30:
            break
        step += 1
    if trace_stream is not None:
        trace_stream.close()
    for r in renderers.values():
        r.close()
    material = np.asarray(norms)
    return {
        "dx": dx, "dy": dy, "yaw_deg": yaw_deg, "seed": seed,
        "steps": len(norms),
        "min_norm": float(material.min()),
        "p10_norm": float(np.percentile(material, 10)),
        "base_still_steps": int(np.sum(material <= 0.1)),
        "stage1_at_step": stage1_at,
        "extended_to_full_horizon": extended,
        "max_handle_rad": max_handle,
        "max_hinge_rad": max_hinge,
        "max_root_x": max_root_x,
        "door_plane_x": door_plane_x,
        "crossed_door_plane": bool(max_root_x > door_plane_x),
        "min_base_height": min_base_height,
        "terminated_early_fall": bool(min_base_height < 0.30),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--student-source-root", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--case", default="p00_baseline")
    parser.add_argument("--appearance", default="production")
    parser.add_argument("--worker-index", type=int, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--episodes", type=int, default=16)
    parser.add_argument("--short-horizon", type=int, default=400)
    parser.add_argument("--full-horizon", type=int, default=1000)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    native_contract = ResolvedNativePositionContractR4.from_config(args.resolved_config)
    warp_contract = ResolvedActionWarpContractR5.from_config(args.resolved_config)
    scene_xml = build_scene(
        output / f"scene_worker{args.worker_index}", args.manifest, args.robot, native_contract, args.case
    )
    actor = _load_actor(args.bundle_dir, args.student_source_root)
    a2_policy = torch.jit.load(str(args.a2_base_policy.resolve(strict=True)), map_location="cpu").eval()
    bundle_manifest = json.loads((args.bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(77000 + args.worker_index)
    results_path = output / f"results_worker{args.worker_index}.jsonl"
    for ep in range(args.episodes):
        dx = float(rng.uniform(0.55, 0.95))
        dy = float(rng.uniform(-0.10, 0.10))
        yaw = float(rng.uniform(-8.0, 8.0))
        seed = 90000 + args.worker_index * 1000 + ep
        result = run_episode(
            scene_xml=scene_xml, actor=actor, a2_policy=a2_policy,
            native_contract=native_contract, warp_contract=warp_contract,
            bundle_manifest=bundle_manifest,
            dx=dx, dy=dy, yaw_deg=yaw, seed=seed,
            short_horizon=args.short_horizon, full_horizon=args.full_horizon,
            trace_path=(output / f"trace_worker{args.worker_index}_ep{ep:03d}.jsonl") if True else None,
            appearance=args.appearance,
        )
        with results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, sort_keys=True) + "\n")
        print(json.dumps({
            "worker": args.worker_index, "ep": ep, "min_norm": result["min_norm"],
            "stage1_at": result["stage1_at_step"], "max_handle": result["max_handle_rad"],
            "max_hinge": result["max_hinge_rad"],
        }), flush=True)


if __name__ == "__main__":
    main()
