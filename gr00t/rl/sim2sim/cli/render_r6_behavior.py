#!/usr/bin/env python3
"""r6 Phase A behavior visualization: replay renders and joint-kinematics receipt.

``case`` replays a stored r5 campaign trace row-by-row (no policy re-run) and
encodes an overview mp4 plus a tiled three-policy-camera mp4. ``probe-rerun``
re-executes the staging-band probe loop with the identical seed/init and a
frame recorder, then checks row-for-row determinism against the stored probe
trace. ``receipt`` computes the joint-kinematics vitals receipt.
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

import imageio.v2 as imageio

CAMERA_SIZES = {"left": (384, 216), "right": (384, 216), "head": (136, 384)}


def _tile_policy_frames(frames: dict[str, np.ndarray]) -> np.ndarray:
    left = Image.fromarray(frames["left"])
    right = Image.fromarray(frames["right"])
    head = Image.fromarray(frames["head"])
    width = left.width + right.width
    canvas = Image.new("RGB", (width, left.height + head.height), (16, 16, 16))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width, 0))
    canvas.paste(head, ((width - head.width) // 2, left.height))
    if canvas.width > 640 or canvas.height > 480:
        scale = min(640 / canvas.width, 480 / canvas.height)
        canvas = canvas.resize(
            (int(canvas.width * scale), int(canvas.height * scale)),
            Image.Resampling.LANCZOS,
        )
    return np.asarray(canvas)


def _encode(frames: list[np.ndarray], path: Path, fps: int = 25) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    imageio.mimwrite(path, frames, fps=fps, quality=8, macro_block_size=1)


def _state_addresses(model: mujoco.MjModel) -> dict[str, object]:
    free = np.nonzero(model.jnt_type == mujoco.mjtJoint.mjJNT_FREE)[0]
    if len(free) != 1:
        raise ValueError("expected exactly one free joint in the paired scene")
    free_qpos_adr = int(model.jnt_qposadr[free[0]])
    door = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    return {
        "free_qpos_adr": free_qpos_adr,
        "door_qpos_adr": int(model.jnt_qposadr[door]),
        "handle_qpos_adr": int(model.jnt_qposadr[handle]),
    }


def render_case(
    *,
    case_dir: Path,
    scene_xml: Path,
    output_dir: Path,
    stride: int = 8,
) -> dict:
    rows = [
        json.loads(line)
        for line in (case_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    addr = _state_addresses(model)
    actuator_map = NameResolvedPositionActuatorMapR4.from_model(
        model,
        ResolvedNativePositionContractR4.from_config(
            Path("scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10_ready_r2/config_snapshot.yaml")
        ).joint_names,
    )
    render_option = policy_scene_option_r4()
    overview = mujoco.Renderer(model, height=480, width=640)
    policy = {
        name: mujoco.Renderer(model, height=h, width=w)
        for name, (h, w) in CAMERA_SIZES.items()
    }
    overview_frames: list[np.ndarray] = []
    tiled_frames: list[np.ndarray] = []
    for index, row in enumerate(rows):
        if index % stride != 0:
            continue
        qpos = data.qpos
        qpos[addr["free_qpos_adr"] : addr["free_qpos_adr"] + 7] = (
            row["base"]["position_m"] + row["base"]["quaternion_wxyz"]
        )
        qpos[actuator_map.robot_qpos_addresses] = row["robot_qpos"]
        qpos[addr["door_qpos_adr"]] = row["door"]["hinge_rad"]
        qpos[addr["handle_qpos_adr"]] = row["door"]["handle_rad"]
        data.qvel[:] = 0.0
        mujoco.mj_forward(model, data)
        overview.update_scene(data, camera="axis_overview", scene_option=render_option)
        overview_frames.append(overview.render().copy())
        frames = {}
        for name in CAMERA_NAMES:
            policy[name].update_scene(
                data, camera=f"{name}_policy", scene_option=render_option
            )
            frames[name] = policy[name].render().copy()
        tiled_frames.append(_tile_policy_frames(frames))
    overview.close()
    for renderer in policy.values():
        renderer.close()
    case_id = case_dir.name
    _encode(overview_frames, output_dir / f"{case_id}_overview.mp4")
    _encode(tiled_frames, output_dir / f"{case_id}_policy_tiled.mp4")
    return {
        "case_id": case_id,
        "frames": len(overview_frames),
        "source": "REPLAY_FROM_STORED_TRACE_ROW_BY_ROW",
        "overview": str(output_dir / f"{case_id}_overview.mp4"),
        "policy_tiled": str(output_dir / f"{case_id}_policy_tiled.mp4"),
    }


def probe_rerun(
    *,
    manifest: Path,
    robot_xml: Path,
    bundle_dir: Path,
    student_source_root: Path,
    a2_base_policy: Path,
    resolved_config: Path,
    stored_trace: Path,
    output_dir: Path,
    dx: float,
    horizon: int,
    seed: int,
    case: str,
    stride: int = 8,
) -> dict:
    """Re-execute the staging-band probe with recording; verify determinism.

    Loop body mirrors gr00t/rl/sim2sim/cli/probe_staging_band_r5.py main()
    verbatim; recording is added around it.
    """
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

    scene_xml = output_dir / "scene.xml"
    door_xml = output_dir / "door_r4.xml"
    external_scene = output_dir / "external_pd_source_scene.xml"
    native_scene = output_dir / "native_position_scene_r4.xml"
    MjcfDoorBuilderR4(spec).write(door_xml, output_dir / "door_build_report_r4.json")
    PairedSceneBuilderV2(
        robot_xml,
        door_xml,
        armature_by_joint=native_contract.values_by_joint(native_contract.armature),
    ).write(external_scene, output_dir / "source_scene_build_report_v2.json")
    NativePositionSceneR4(external_scene, native_contract).write(
        native_scene, output_dir / "native_position_scene_build_report_r4.json"
    )
    PolicyVisualSceneR4(native_scene).write(
        scene_xml, output_dir / "policy_visual_scene_report_r4.json"
    )

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
    overview = mujoco.Renderer(model, height=480, width=640)
    policy = {
        name: mujoco.Renderer(model, height=h, width=w)
        for name, (h, w) in CAMERA_SIZES.items()
    }
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
    cached_rgb: dict[str, np.ndarray] = {}
    overview_frames: list[np.ndarray] = []
    tiled_frames: list[np.ndarray] = []
    norms: list[float] = []

    def capture(step: int) -> None:
        if step % stride != 0:
            return
        overview.update_scene(data, camera="axis_overview", scene_option=render_option)
        overview_frames.append(overview.render().copy())
        frames = {}
        for name in CAMERA_NAMES:
            policy[name].update_scene(
                data, camera=f"{name}_policy", scene_option=render_option
            )
            frames[name] = policy[name].render().copy()
        tiled_frames.append(_tile_policy_frames(frames))

    capture(0)
    physics_step = 0
    for policy_step in range(horizon):
        # --- observation (mirrors probe_staging_band_r5.py; _body_state reused) ---
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
        actor_obs = build_actor_obs(bundle_manifest["observation"]["components"], actor_values)
        ages = [min(1.0, (float(data.time) - last_capture[name]) / 0.1) for name in CAMERA_NAMES]
        if not cached_rgb:
            for name in CAMERA_NAMES:
                policy[name].update_scene(data, camera=f"{name}_policy", scene_option=render_option)
                cached_rgb[name] = policy[name].render().copy()
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
        base_norm = float(torch.linalg.vector_norm(warped.base.physical[:, :3]))
        norms.append(base_norm)
        for _ in range(4):
            actuator_map.write_robot_position_target(
                data, position_target.squeeze(0).double().numpy()
            )
            mujoco.mj_step(model, data)
            physics_step += 1
            gait.advance(warped.base.physical[:, :3])
            for name in CAMERA_NAMES:
                if float(data.time) + 1.0e-12 >= next_capture[name]:
                    policy[name].update_scene(
                        data, camera=f"{name}_policy", scene_option=render_option
                    )
                    cached_rgb[name] = policy[name].render().copy()
                    last_capture[name] = float(data.time)
                    next_capture[name] += CAMERA_PERIODS[name]
        capture(physics_step)

    overview.close()
    for renderer in policy.values():
        renderer.close()
    _encode(overview_frames, output_dir / "staging_band_probe_overview.mp4")
    _encode(tiled_frames, output_dir / "staging_band_probe_policy_tiled.mp4")

    stored_norms = [
        json.loads(line)["physical_base_command_norm_first3"]
        for line in stored_trace.read_text(encoding="utf-8").splitlines()
    ]
    diffs = np.abs(np.asarray(norms) - np.asarray(stored_norms[: len(norms)]))
    return {
        "mode": "SAME_SEED_RERUN_WITH_RECORDING",
        "seed": seed,
        "dx": dx,
        "frames": len(overview_frames),
        "determinism_check_vs_stored_probe_trace": {
            "compared_steps": len(norms),
            "max_abs_norm_diff": float(diffs.max()) if len(diffs) else None,
            "row_identical": bool(len(norms) == len(stored_norms) and diffs.max() == 0.0),
        },
        "overview": str(output_dir / "staging_band_probe_overview.mp4"),
        "policy_tiled": str(output_dir / "staging_band_probe_policy_tiled.mp4"),
    }


def joint_receipt(*, campaign_root: Path, output: Path) -> dict:
    joint_names = resolved_a2_piper_contract().sim_joint_names
    per_case = {}
    arm_dev_curves = {}
    commanded_vs_measured = {}
    for case_dir in sorted((campaign_root / "cases").iterdir()):
        rows = [
            json.loads(line)
            for line in (case_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        qvel = np.asarray([row["robot_qvel"] for row in rows], dtype=np.float64)
        finite = bool(np.isfinite(qvel).all())
        absq = np.abs(qvel)
        stage_rows = [
            json.loads(line)
            for line in (case_dir / "stage_trace.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        arm_dev = np.asarray(
            [row["arm_default_max_deviation_rad"] for row in stage_rows], dtype=np.float64
        )
        arm_dev_curves[case_dir.name] = {
            "max": float(arm_dev.max()),
            "mean": float(arm_dev.mean()),
            "p95": float(np.percentile(arm_dev, 95)),
        }
        warp = ResolvedActionWarpContractR5.from_config(
            Path("scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10_ready_r2/config_snapshot.yaml")
        )
        policy_rows = [row for row in rows if row["substep"] == 0]
        commanded = []
        measured = []
        for row in policy_rows:
            raw = np.asarray(row["student_action_mean"][:5], dtype=np.float64)
            scaled = np.concatenate((raw[:3] * warp.base_command_scale, raw[3:5]))
            low = np.asarray(warp.base_low, dtype=np.float64)
            high = np.asarray(warp.base_high, dtype=np.float64)
            physical = np.clip(scaled, low, high)
            commanded.append(float(np.linalg.norm(physical[:3])))
            measured.append(
                float(np.linalg.norm(np.asarray(row["base"]["linear_velocity_mps"])))
            )
        commanded_vs_measured[case_dir.name] = {
            "commanded_xyz_norm_mean": float(np.mean(commanded)),
            "commanded_xyz_norm_max": float(np.max(commanded)),
            "measured_base_speed_mean": float(np.mean(measured)),
            "measured_base_speed_max": float(np.max(measured)),
            "measured_over_commanded_mean": float(np.mean(measured) / np.mean(commanded)),
        }
        per_case[case_dir.name] = {
            "finite": finite,
            "per_joint_abs_qvel": {
                joint_names[i]: {
                    "max": float(absq[:, i].max()),
                    "rms": float(np.sqrt(np.mean(qvel[:, i] ** 2))),
                    "p95": float(np.percentile(absq[:, i], 95)),
                }
                for i in range(len(joint_names))
            },
        }
    leg_idx = list(range(0, 12))
    arm_idx = list(range(12, 18))
    grip_idx = list(range(18, 20))

    def group_max(case: dict, idx: list[int]) -> float:
        return max(case["per_joint_abs_qvel"][resolved_a2_piper_contract().sim_joint_names[i]]["max"] for i in idx)

    all_finite = all(case["finite"] for case in per_case.values())
    arm_max = max(group_max(case, arm_idx) for case in per_case.values())
    grip_max = max(group_max(case, grip_idx) for case in per_case.values())
    leg_max = max(group_max(case, leg_idx) for case in per_case.values())
    episode_receipts = json.loads(
        (campaign_root / "campaign_receipt.json").read_text(encoding="utf-8")
    )["episode_receipts"]
    qacc_max = max(item["control_surface"]["max_abs_qacc"] for item in episode_receipts)
    checks = {
        "all_states_finite": all_finite,
        "stage0_arm_abs_qvel_lt_2_radps": arm_max < 2.0,
        "leg_abs_qvel_within_gait_envelope_x3_standing_reference": leg_max < 3 * 7.03,
        "qacc_below_1e5_no_nano_scale": qacc_max < 1.0e5,
    }
    verdict = "JOINT_KINEMATICS_SANE" if all(checks.values()) else "JOINT_KINEMATICS_VIOLATIONS_LISTED"
    receipt = {
        "schema": "doordog.sim2sim.joint_kinematics_vitals.r6.v1",
        "source": "paired_mujoco_campaign_r5/cases/*/trace.jsonl + stage_trace.jsonl",
        "typed_verdict": verdict,
        "checks": checks,
        "summary": {
            "max_abs_qvel_radps": {
                "legs_max": leg_max,
                "arms_max_in_stage0_hold": arm_max,
                "grippers_max": grip_max,
                "reference_standing_gate_max": 7.03,
                "arm_reference_bound": 2.0,
            },
            "max_abs_qacc_campaign": qacc_max,
            "arm_default_deviation_rad_by_case": arm_dev_curves,
            "measured_base_speed_vs_commanded_norm_by_case": commanded_vs_measured,
        },
        "per_case": per_case,
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    case_p = sub.add_parser("case")
    case_p.add_argument("--case-id", required=True)
    case_p.add_argument("--campaign-root", type=Path, required=True)
    case_p.add_argument("--output-dir", type=Path, required=True)
    probe_p = sub.add_parser("probe-rerun")
    probe_p.add_argument("--manifest", type=Path, required=True)
    probe_p.add_argument("--robot", type=Path, required=True)
    probe_p.add_argument("--bundle-dir", type=Path, required=True)
    probe_p.add_argument("--student-source-root", type=Path, required=True)
    probe_p.add_argument("--a2-base-policy", type=Path, required=True)
    probe_p.add_argument("--resolved-config", type=Path, required=True)
    probe_p.add_argument("--stored-trace", type=Path, required=True)
    probe_p.add_argument("--output-dir", type=Path, required=True)
    probe_p.add_argument("--dx", type=float, default=0.65)
    probe_p.add_argument("--horizon", type=int, default=1000)
    probe_p.add_argument("--seed", type=int, default=41001)
    probe_p.add_argument("--case", default="p00_baseline")
    receipt_p = sub.add_parser("receipt")
    receipt_p.add_argument("--campaign-root", type=Path, required=True)
    receipt_p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "case":
        case_dir = args.campaign_root / "cases" / args.case_id
        result = render_case(
            case_dir=case_dir,
            scene_xml=case_dir / "model" / "scene.xml",
            output_dir=args.output_dir,
        )
    elif args.command == "probe-rerun":
        args.output_dir.resolve().mkdir(parents=True, exist_ok=True)
        result = probe_rerun(
            manifest=args.manifest,
            robot_xml=args.robot,
            bundle_dir=args.bundle_dir,
            student_source_root=args.student_source_root,
            a2_base_policy=args.a2_base_policy,
            resolved_config=args.resolved_config,
            stored_trace=args.stored_trace,
            output_dir=args.output_dir.resolve(),
            dx=args.dx,
            horizon=args.horizon,
            seed=args.seed,
            case=args.case,
        )
    else:
        result = joint_receipt(campaign_root=args.campaign_root, output=args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "per_case"}, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
