#!/usr/bin/env python3
"""Run the READY r2 Student over every fixed paired case on MuJoCo CPU."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import gr00t.rl
import hydra
import mujoco
import numpy as np
import torch
from omegaconf import OmegaConf
from PIL import Image

from gr00t.rl.sim2sim.doors.mjcf_builder import MjcfDoorBuilder
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_transform import A2ActionTransform, ArmDeltaAccumulator
from gr00t.rl.sim2sim.mujoco.external_pd import ExternalPdController
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.paired_scene_builder import PairedSceneBuilder
from gr00t.rl.sim2sim.mujoco.sensor_clock import SensorClock
from gr00t.rl.sim2sim.policy.observations import build_actor_obs, compose_dual_rgb, normalize_rgb_nhwc
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


TRACE_SCHEMA = "doordog.sim2sim.paired_trace_row.v1"
CAMERA_NAMES = ("left", "right", "head")
CAMERA_PERIODS = {"left": 1.0 / 30.0, "right": 1.0 / 30.0, "head": 1.0 / 15.0}


def _render(renderer: mujoco.Renderer, data: mujoco.MjData, camera: str) -> np.ndarray:
    renderer.update_scene(data, camera=camera)
    return renderer.render().copy()


def _body_state(
    model: mujoco.MjModel, data: mujoco.MjData, trunk_id: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    local_velocity = np.zeros(6, dtype=np.float64)
    world_velocity = np.zeros(6, dtype=np.float64)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, trunk_id, local_velocity, 1)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, trunk_id, world_velocity, 0)
    rotation = data.xmat[trunk_id].reshape(3, 3)
    projected_gravity = rotation.T @ np.array([0.0, 0.0, -1.0])
    roll = math.atan2(rotation[2, 1], rotation[2, 2])
    pitch = math.atan2(-rotation[2, 0], math.sqrt(rotation[2, 1] ** 2 + rotation[2, 2] ** 2))
    return local_velocity[:3], projected_gravity, np.array([roll, pitch]), world_velocity


def _pixel_stats(image: np.ndarray) -> dict[str, Any]:
    return {
        "min_uint8": int(image.min()),
        "max_uint8": int(image.max()),
        "mean_rgb": image.mean(axis=(0, 1)).tolist(),
        "unique_rgb_count": int(np.unique(image.reshape(-1, 3), axis=0).shape[0]),
    }


def _joint_addresses(model: mujoco.MjModel, names: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    joint_ids = np.array(
        [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in names],
        dtype=np.int32,
    )
    return model.jnt_qposadr[joint_ids].copy(), model.jnt_dofadr[joint_ids].copy()


def _load_actor(bundle_dir: Path, student_source_root: Path):
    source_rl = student_source_root.resolve(strict=True) / "gr00t" / "rl"
    gr00t.rl.__path__ = [str(source_rl), *list(gr00t.rl.__path__)]
    config = OmegaConf.load(bundle_dir / "config_snapshot.yaml")
    actor = hydra.utils.instantiate(
        config.algo.config.actor,
        env_config=config.env.config,
        algo_config=config.algo.config,
        module_dim_dict=config.algo.config.module_dim,
        _recursive_=False,
    ).cpu()
    state = torch.load(bundle_dir / "actor_state_dict.pt", map_location="cpu", weights_only=False)
    incompat = actor.load_state_dict(state, strict=True)
    if incompat.missing_keys or incompat.unexpected_keys:
        raise RuntimeError(f"strict Student load mismatch: {incompat}")
    actor.eval()
    return actor


def _run_case(
    *,
    manifest: dict[str, Any],
    case: dict[str, Any],
    manifest_dir: Path,
    robot_xml: Path,
    bundle_manifest: dict[str, Any],
    actor,
    a2_policy,
    output_root: Path,
) -> dict[str, Any]:
    case_id = case["case_id"]
    episode_index = int(case["episode_index"])
    seed = int(case["seed"])
    np.random.seed(seed)
    torch.manual_seed(seed)
    case_output = output_root / "cases" / case_id
    model_output = case_output / "model"
    image_output = case_output / "images"
    model_output.mkdir(parents=True, exist_ok=True)
    image_output.mkdir(parents=True, exist_ok=True)
    instance_path = (manifest_dir / case["door_instance_path"]).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(instance_path)
    if spec.friction_classification != "FRICTION_SEMANTICS_ALIGNED":
        raise ValueError(f"case {case_id} is outside the aligned-friction paired subdomain")
    door_xml = model_output / "door.xml"
    door_report = model_output / "door_build_report.json"
    scene_xml = model_output / "scene.xml"
    scene_report = model_output / "scene_build_report.json"
    MjcfDoorBuilder(spec).write(door_xml, door_report)
    PairedSceneBuilder(robot_xml, door_xml).write(scene_xml, scene_report)

    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    policy_renderers = {
        "left": mujoco.Renderer(model, height=384, width=216),
        "right": mujoco.Renderer(model, height=384, width=216),
        "head": mujoco.Renderer(model, height=136, width=384),
    }
    overview_renderer = mujoco.Renderer(model, height=720, width=1280)
    cached_rgb = {
        name: _render(policy_renderers[name], data, f"{name}_policy") for name in CAMERA_NAMES
    }
    frame_ids = {name: 0 for name in CAMERA_NAMES}
    last_capture = {name: float(data.time) for name in CAMERA_NAMES}
    next_capture = {name: period for name, period in CAMERA_PERIODS.items()}
    if episode_index == 0:
        Image.fromarray(_render(overview_renderer, data, "axis_overview")).save(
            output_root / "mujoco_asset_initial.png"
        )

    actor.init_rollout()
    actor.reset()
    contract = resolved_a2_piper_contract()
    dtype = torch.float64
    joint_map = A2PiperJointMap.from_sim_joint_names(contract.sim_joint_names, device="cpu")
    default64 = torch.tensor(contract.default_dof_pos, dtype=dtype).unsqueeze(0)
    default32 = default64.float()
    pd = ExternalPdController(
        stiffness=torch.tensor(contract.stiffness, dtype=dtype),
        damping=torch.tensor(contract.damping, dtype=dtype),
        torque_limit=torch.tensor(contract.torque_limit, dtype=dtype),
    )
    arm_delta = ArmDeltaAccumulator(batch_size=1, device="cpu", dtype=torch.float32)
    action_transform = A2ActionTransform(joint_map, action_scale=contract.action_scale)
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    gait = SensorClock(batch_size=1, physics_dt=0.005, device="cpu", dtype=torch.float32)
    previous_logical = torch.zeros((1, 19), dtype=torch.float32)
    previous_raw_delta = torch.zeros((1, 6), dtype=torch.float32)
    previous_base_raw = torch.zeros((1, 5), dtype=torch.float32)
    previous_base_physical = torch.zeros((1, 5), dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    position_target = default64.clone()

    robot_qpos_addr, robot_qvel_addr = _joint_addresses(model, contract.sim_joint_names)
    door_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    door_qpos_addr = int(model.jnt_qposadr[door_joint])
    handle_qpos_addr = int(model.jnt_qposadr[handle_joint])
    door_qvel_addr = int(model.jnt_dofadr[door_joint])
    handle_qvel_addr = int(model.jnt_dofadr[handle_joint])
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    open_threshold = float(manifest["episode_contract"]["open_crossing_threshold_hinge_rad"])
    unlatch_threshold = float(manifest["episode_contract"]["unlatch_threshold_handle_rad"])
    horizon_policy_steps = int(manifest["episode_contract"]["horizon_policy_steps"])
    base_height_termination = float(manifest["episode_contract"]["base_height_termination_m"])
    image_mean = bundle_manifest["camera_rig"]["image_mean"]
    image_std = bundle_manifest["camera_rig"]["image_std"]
    trace_path = case_output / "trace.jsonl"
    max_hinge = float(data.qpos[door_qpos_addr])
    max_handle = float(data.qpos[handle_qpos_addr])
    first_unlatch_time = None
    first_open_time = None
    physics_steps = 0
    policy_steps = 0
    termination_reason = "NONE"
    done = False

    with trace_path.open("w", encoding="utf-8") as trace_stream:
        for policy_step in range(horizon_policy_steps):
            local_angular_velocity, projected_gravity, roll_pitch, _ = _body_state(
                model, data, trunk_id
            )
            robot_qpos = data.qpos[robot_qpos_addr].copy()
            robot_qvel = data.qvel[robot_qvel_addr].copy()
            actor_values = {
                "base_ang_vel": torch.from_numpy(local_angular_velocity).float().unsqueeze(0),
                "projected_gravity": torch.from_numpy(projected_gravity).float().unsqueeze(0),
                "a2_student_dof_pos": torch.from_numpy(robot_qpos).float().unsqueeze(0) - default32,
                "a2_student_dof_vel": torch.from_numpy(robot_qvel).float().unsqueeze(0),
                "actions": previous_logical,
                "delta_actions": previous_raw_delta,
                "a2_base_command": previous_base_physical
                * torch.tensor([2.0, 2.0, 0.25, 1.0, 1.0]),
                "a2_base_command_raw": previous_base_raw,
            }
            if float(torch.linalg.vector_norm(previous_base_physical[:, :3])) < 0.1:
                actor_values["a2_base_command"][:, :3] = 0.0
            actor_obs = build_actor_obs(bundle_manifest["observation"]["components"], actor_values)
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
            if tuple(high_raw.shape) != (1, 12) or not bool(torch.isfinite(high_raw).all()):
                raise FloatingPointError(f"Student action invalid in {case_id} at policy step {policy_step}")
            high_effective = arm_delta.apply(high_raw, torch.ones((1,), dtype=torch.long))
            physical_base = torch.cat(
                (
                    high_effective[:, :3] * 0.25,
                    high_effective[:, 3:5].clamp(-1.0, 1.0) * 0.4,
                ),
                dim=1,
            )
            frame = frame_builder.build(
                projected_gravity=torch.from_numpy(projected_gravity).float().unsqueeze(0),
                dof_pos=torch.from_numpy(robot_qpos).float().unsqueeze(0),
                default_dof_pos=default32,
                dof_vel=torch.from_numpy(robot_qvel).float().unsqueeze(0),
                previous_leg_action=previous_leg,
                physical_base_command=physical_base,
                base_roll_pitch=torch.from_numpy(roll_pitch).float().unsqueeze(0),
                gait_clock=gait.signal(),
            )
            with torch.inference_mode():
                leg_action = a2_policy(history.append(frame))
            transformed = action_transform.compose(
                high_level_action=high_effective,
                policy_leg_action=leg_action,
                default_dof_pos=default32,
            )
            position_target = transformed.position_target.double()
            input_frame_ids = [frame_ids[name] for name in CAMERA_NAMES]
            input_ages = list(ages)
            previous_logical = transformed.logical_action
            previous_raw_delta = high_raw[:, 5:11]
            previous_base_raw = high_raw[:, :5]
            previous_base_physical = physical_base
            previous_leg = leg_action
            policy_steps += 1

            for substep in range(4):
                robot_position = torch.from_numpy(data.qpos[robot_qpos_addr].copy()).to(dtype).unsqueeze(0)
                robot_velocity = torch.from_numpy(data.qvel[robot_qvel_addr].copy()).to(dtype).unsqueeze(0)
                robot_ctrl = pd.compute(
                    position_target=position_target,
                    position=robot_position,
                    velocity=robot_velocity,
                ).squeeze(0).numpy()
                data.ctrl[:20] = robot_ctrl
                mujoco.mj_step(model, data)
                physics_steps += 1
                gait.advance(physical_base[:, :3])
                for name in CAMERA_NAMES:
                    if float(data.time) + 1.0e-12 >= next_capture[name]:
                        cached_rgb[name] = _render(policy_renderers[name], data, f"{name}_policy")
                        frame_ids[name] += 1
                        last_capture[name] = float(data.time)
                        next_capture[name] += CAMERA_PERIODS[name]

                if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                    raise FloatingPointError(f"MuJoCo state invalid in {case_id} at physics step {physics_steps}")
                hinge = float(data.qpos[door_qpos_addr])
                handle = float(data.qpos[handle_qpos_addr])
                max_hinge = max(max_hinge, hinge)
                max_handle = max(max_handle, handle)
                unlatched = handle >= unlatch_threshold
                opened = hinge >= open_threshold
                if unlatched and first_unlatch_time is None:
                    first_unlatch_time = float(data.time)
                if opened and first_open_time is None:
                    first_open_time = float(data.time)
                if float(data.qpos[2]) < base_height_termination:
                    done = True
                    termination_reason = "BASE_HEIGHT"
                elif physics_steps == horizon_policy_steps * 4:
                    done = True
                    termination_reason = "HORIZON"
                _, _, _, world_velocity = _body_state(model, data, trunk_id)
                row = {
                    "schema_version": TRACE_SCHEMA,
                    "manifest_id": manifest["manifest_id"],
                    "case_id": case_id,
                    "door_instance_id": case["door_instance_id"],
                    "initial_state_id": manifest["fixed_initial_state"]["initial_state_id"],
                    "policy_bundle_id": bundle_manifest["bundle_id"],
                    "backend": "mujoco_cpu",
                    "episode_index": episode_index,
                    "seed": seed,
                    "physics_step": physics_steps - 1,
                    "policy_step": policy_step,
                    "substep": substep,
                    "time_s": float(data.time),
                    "policy_update": substep == 0,
                    "student_action_mean": high_raw.squeeze(0).tolist(),
                    "applied_action": transformed.logical_action.squeeze(0).tolist(),
                    "position_target_sim_units": position_target.squeeze(0).tolist(),
                    "robot_qpos": data.qpos[robot_qpos_addr].tolist(),
                    "robot_qvel": data.qvel[robot_qvel_addr].tolist(),
                    "robot_ctrl_effort": robot_ctrl.tolist(),
                    "base": {
                        "position_m": data.qpos[:3].tolist(),
                        "quaternion_wxyz": data.qpos[3:7].tolist(),
                        "linear_velocity_mps": world_velocity[3:].tolist(),
                        "angular_velocity_radps": world_velocity[:3].tolist(),
                    },
                    "door": {
                        "hinge_rad": hinge,
                        "hinge_velocity_radps": float(data.qvel[door_qvel_addr]),
                        "handle_rad": handle,
                        "handle_velocity_radps": float(data.qvel[handle_qvel_addr]),
                        "hinge_drive_force_nm": float(data.actuator_force[20]),
                        "handle_drive_force_nm": float(data.actuator_force[21]),
                        "latch_state": "NO_LATCH",
                        "unlatched": unlatched,
                        "open_threshold_crossed": opened,
                    },
                    "camera_input": {
                        "frame_ids": input_frame_ids,
                        "age_normalized": input_ages,
                        "valid": [True, True, True],
                    },
                    "done": done,
                    "termination_reason": termination_reason if done else "NONE",
                }
                trace_stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
                if done:
                    break
            if done:
                break

    for name, image in cached_rgb.items():
        Image.fromarray(image).save(image_output / f"final_{name}.png")
    if episode_index == 0:
        Image.fromarray(_render(overview_renderer, data, "axis_overview")).save(
            output_root / "mujoco_asset_terminal.png"
        )
    for renderer in policy_renderers.values():
        renderer.close()
    overview_renderer.close()

    receipt = {
        "schema": "doordog.sim2sim.paired_mujoco_episode_receipt.v1",
        "result_classification": "VALID_WITH_WARNINGS",
        "manifest_id": manifest["manifest_id"],
        "case_id": case_id,
        "episode_index": episode_index,
        "seed": seed,
        "episode_complete": True,
        "termination_reason": termination_reason,
        "policy_steps": policy_steps,
        "physics_steps": physics_steps,
        "external_pd_clip_applications": physics_steps,
        "trace": str(trace_path),
        "task_metrics": {
            "source": "DIRECT_MUJOCO_DOOR_STATE",
            "max_hinge_rad": max_hinge,
            "max_handle_rad": max_handle,
            "unlatched": first_unlatch_time is not None,
            "first_unlatch_time_s": first_unlatch_time,
            "open_threshold_crossed": first_open_time is not None,
            "first_open_time_s": first_open_time,
            "unlatch_threshold_handle_rad": unlatch_threshold,
            "open_threshold_hinge_rad": open_threshold,
        },
        "pixel_domain_gap_data": {name: _pixel_stats(image) for name, image in cached_rgb.items()},
        "door_realization": {
            "door_instance": str(instance_path),
            "door_build_report": str(door_report),
            "scene_build_report": str(scene_report),
            "friction_classification": spec.friction_classification,
            "mechanics_three_face_receipt": spec.mechanics_receipt(),
        },
        "expectation": manifest["expectation"],
        "warnings": [
            "GRPO step10 is a pilot Student; episode outcome is not Student quality evidence.",
            "MuJoCo RGB statistics are domain-gap data and do not decide policy regression."
        ],
    }
    (case_output / "episode_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--student-source-root", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve(strict=True)
    manifest_dir = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_dir = args.bundle_dir.resolve(strict=True)
    bundle_manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    if bundle_manifest["artifact_status"] != "READY":
        raise ValueError("paired campaign requires a READY policy bundle")
    if manifest["case_count"] != len(manifest["cases"]):
        raise ValueError("paired manifest case_count mismatch")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    actor = _load_actor(bundle_dir, args.student_source_root)
    a2_policy = torch.jit.load(
        str(args.a2_base_policy.resolve(strict=True)), map_location="cpu"
    ).eval()
    receipts = []
    for case in manifest["cases"]:
        receipt = _run_case(
            manifest=manifest,
            case=case,
            manifest_dir=manifest_dir,
            robot_xml=args.robot,
            bundle_manifest=bundle_manifest,
            actor=actor,
            a2_policy=a2_policy,
            output_root=output,
        )
        receipts.append(receipt)
        print(
            json.dumps(
                {
                    "case_id": receipt["case_id"],
                    "termination_reason": receipt["termination_reason"],
                    "physics_steps": receipt["physics_steps"],
                    "open_threshold_crossed": receipt["task_metrics"]["open_threshold_crossed"]
                },
                sort_keys=True,
            ),
            flush=True,
        )

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    campaign = {
        "schema": "doordog.sim2sim.paired_mujoco_campaign_receipt.v1",
        "evidence_level": "E4_FULL_CAMPAIGN_E5_MUJOCO_INPUT",
        "result_classification": "VALID_WITH_WARNINGS",
        "input_status": "MUJOCO_CAMPAIGN_COMPLETE_ISAAC_PAIRED_TRACE_PENDING",
        "manifest_id": manifest["manifest_id"],
        "manifest": str(manifest_path),
        "policy_bundle": str(bundle_dir),
        "backend": "mujoco_cpu",
        "device": "cpu",
        "case_count": len(receipts),
        "episode_receipts": receipts,
        "total_policy_steps": sum(item["policy_steps"] for item in receipts),
        "total_physics_steps": sum(item["physics_steps"] for item in receipts),
        "external_pd_clip_applications": sum(
            item["external_pd_clip_applications"] for item in receipts
        ),
        "asset_render": {
            "initial_screenshot": str(output / "mujoco_asset_initial.png"),
            "terminal_screenshot": str(output / "mujoco_asset_terminal.png"),
            "camera": "axis_overview",
            "render_contract": "MuJoCo Renderer under CPU GLX/Xvfb llvmpipe; zero GPU"
        },
        "expectation": manifest["expectation"],
        "producer_identity": {
            "git_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/run_paired_mujoco_campaign.py"
        },
        "warnings": [
            "This formal campaign proves the pipeline and physics evidence path, not pilot Student quality.",
            "Failed episodes remain in their complete terminal traces.",
            "Success rate is not used as the paired trajectory/mechanics verdict.",
            "Isaac paired input remains typed pending until transferred by the user."
        ]
    }
    (output / "campaign_receipt.json").write_text(
        json.dumps(campaign, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"case_count": len(receipts), "total_physics_steps": campaign["total_physics_steps"]}, sort_keys=True))


if __name__ == "__main__":
    main()
