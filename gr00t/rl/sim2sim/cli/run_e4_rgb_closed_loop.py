#!/usr/bin/env python3
"""Run policy-image replay and a short native-RGB MuJoCo Student loop on CPU."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import gr00t.rl
import hydra
import mujoco
import numpy as np
import torch
from omegaconf import OmegaConf
from PIL import Image

from gr00t.rl.sim2sim.doors.metrics import DoorStateMetrics
from gr00t.rl.sim2sim.doors.runtime import ConstraintGate
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_transform import A2ActionTransform, ArmDeltaAccumulator
from gr00t.rl.sim2sim.mujoco.external_pd import ExternalPdController
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.sensor_clock import SensorClock
from gr00t.rl.sim2sim.policy.observations import build_actor_obs, compose_dual_rgb, normalize_rgb_nhwc
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


def _render(renderer: mujoco.Renderer, data: mujoco.MjData, camera: str) -> np.ndarray:
    renderer.update_scene(data, camera=camera)
    return renderer.render().copy()


def _base_state(model: mujoco.MjModel, data: mujoco.MjData, trunk_id: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    velocity = np.zeros(6, dtype=np.float64)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, trunk_id, velocity, 1)
    rotation = data.xmat[trunk_id].reshape(3, 3)
    projected_gravity = rotation.T @ np.array([0.0, 0.0, -1.0])
    roll = math.atan2(rotation[2, 1], rotation[2, 2])
    pitch = math.atan2(-rotation[2, 0], math.sqrt(rotation[2, 1] ** 2 + rotation[2, 2] ** 2))
    return velocity[:3], projected_gravity, np.array([roll, pitch])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True, type=Path)
    parser.add_argument("--door-instance", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--student-source-root", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--policy-steps", type=int, default=6)
    args = parser.parse_args()

    source_rl = args.student_source_root.resolve(strict=True) / "gr00t" / "rl"
    gr00t.rl.__path__ = [str(source_rl), *list(gr00t.rl.__path__)]
    scene = args.scene.resolve(strict=True)
    bundle_dir = args.bundle_dir.resolve(strict=True)
    output = args.output_dir.resolve()
    image_dir = output / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    config = OmegaConf.load(bundle_dir / "config_snapshot.yaml")
    instance = json.loads(args.door_instance.resolve(strict=True).read_text(encoding="utf-8"))

    actor_config = config.algo.config.actor
    actor = hydra.utils.instantiate(
        actor_config,
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
    actor.init_rollout()
    actor.reset()
    a2_policy = torch.jit.load(str(args.a2_base_policy.resolve(strict=True)), map_location="cpu").eval()

    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(
        model, data, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    )
    mujoco.mj_forward(model, data)
    renderers = {
        "left": mujoco.Renderer(model, height=384, width=216),
        "right": mujoco.Renderer(model, height=384, width=216),
        "head": mujoco.Renderer(model, height=136, width=384),
    }
    cached_rgb = {
        name: _render(renderers[name], data, f"{name}_policy") for name in renderers
    }
    last_capture = {name: float(data.time) for name in renderers}
    next_capture = {"left": 1.0 / 30.0, "right": 1.0 / 30.0, "head": 1.0 / 15.0}
    for name, image in cached_rgb.items():
        Image.fromarray(image).save(image_dir / f"step000_{name}.png")

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
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    door_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    door_qpos = int(model.jnt_qposadr[door_joint])
    handle_qpos = int(model.jnt_qposadr[handle_joint])
    gate = ConstraintGate(
        model,
        release_handle_rad=float(instance["kinematics"]["constraint_gate_release_handle_rad"]),
    )
    metrics = DoorStateMetrics(open_threshold_rad=0.174533)
    previous_logical = torch.zeros((1, 19), dtype=torch.float32)
    previous_raw_delta = torch.zeros((1, 6), dtype=torch.float32)
    previous_base_raw = torch.zeros((1, 5), dtype=torch.float32)
    previous_base_physical = torch.zeros((1, 5), dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    position_target = default64.clone()
    captured_obs: list[dict[str, torch.Tensor]] = []
    captured_actions: list[torch.Tensor] = []
    policy_rows = []
    mean = manifest["camera_rig"]["image_mean"]
    std = manifest["camera_rig"]["image_std"]

    for policy_step in range(args.policy_steps):
        angular_velocity, projected_gravity, roll_pitch = _base_state(model, data, trunk_id)
        actor_values = {
            "base_ang_vel": torch.from_numpy(angular_velocity).float().unsqueeze(0),
            "projected_gravity": torch.from_numpy(projected_gravity).float().unsqueeze(0),
            "a2_student_dof_pos": torch.from_numpy(data.qpos[7:27].copy()).float().unsqueeze(0) - default32,
            "a2_student_dof_vel": torch.from_numpy(data.qvel[6:26].copy()).float().unsqueeze(0),
            "actions": previous_logical,
            "delta_actions": previous_raw_delta,
            "a2_base_command": previous_base_physical * torch.tensor([2.0, 2.0, 0.25, 1.0, 1.0]),
            "a2_base_command_raw": previous_base_raw,
        }
        if float(torch.linalg.vector_norm(previous_base_physical[:, :3])) < 0.1:
            actor_values["a2_base_command"][:, :3] = 0.0
        actor_obs = build_actor_obs(manifest["observation"]["components"], actor_values)
        left = torch.from_numpy(cached_rgb["left"].copy()).unsqueeze(0)
        right = torch.from_numpy(cached_rgb["right"].copy()).unsqueeze(0)
        head = torch.from_numpy(cached_rgb["head"].copy()).unsqueeze(0)
        ages = [min(1.0, (float(data.time) - last_capture[name]) / 0.1) for name in ("left", "right", "head")]
        obs = {
            "actor_obs": actor_obs,
            "vision_obs": compose_dual_rgb(left, right, image_mean=mean, image_std=std),
            "context_vision_obs": normalize_rgb_nhwc(head, image_mean=mean, image_std=std),
            "camera_meta": torch.tensor([[*ages, 1.0, 1.0, 1.0]], dtype=torch.float32),
        }
        with torch.inference_mode():
            high_raw = actor.act_inference(obs)
        if tuple(high_raw.shape) != (1, 12) or not bool(torch.isfinite(high_raw).all()):
            raise RuntimeError("Student actor returned invalid E4 action")
        high_effective = arm_delta.apply(high_raw, torch.ones((1,), dtype=torch.long))
        physical_base = torch.cat((high_effective[:, :3] * 0.25, high_effective[:, 3:5].clamp(-1.0, 1.0) * 0.4), dim=1)
        frame = frame_builder.build(
            projected_gravity=torch.from_numpy(projected_gravity).float().unsqueeze(0),
            dof_pos=torch.from_numpy(data.qpos[7:27].copy()).float().unsqueeze(0),
            default_dof_pos=default32,
            dof_vel=torch.from_numpy(data.qvel[6:26].copy()).float().unsqueeze(0),
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
        captured_obs.append({name: value.clone() for name, value in obs.items()})
        captured_actions.append(high_raw.clone())
        policy_rows.append(
            {
                "policy_step": policy_step,
                "time_s": float(data.time),
                "student_action_max_abs": float(torch.max(torch.abs(high_raw))),
                "leg_action_max_abs": float(torch.max(torch.abs(leg_action))),
                "door_hinge_rad": float(data.qpos[door_qpos]),
                "camera_meta": obs["camera_meta"].squeeze(0).tolist(),
            }
        )
        previous_logical = transformed.logical_action
        previous_raw_delta = high_raw[:, 5:11]
        previous_base_raw = high_raw[:, :5]
        previous_base_physical = physical_base
        previous_leg = leg_action

        for _ in range(4):
            position = torch.from_numpy(data.qpos[7:27].copy()).to(dtype=dtype).unsqueeze(0)
            velocity = torch.from_numpy(data.qvel[6:26].copy()).to(dtype=dtype).unsqueeze(0)
            data.ctrl[:20] = pd.compute(
                position_target=position_target, position=position, velocity=velocity
            ).squeeze(0).numpy()
            gate.update(data)
            mujoco.mj_step(model, data)
            gait.advance(physical_base[:, :3])
            metrics.update(
                time_s=float(data.time),
                hinge_rad=float(data.qpos[door_qpos]),
                handle_rad=float(data.qpos[handle_qpos]),
            )
            for name, period in (("left", 1.0 / 30.0), ("right", 1.0 / 30.0), ("head", 1.0 / 15.0)):
                if float(data.time) + 1.0e-12 >= next_capture[name]:
                    cached_rgb[name] = _render(renderers[name], data, f"{name}_policy")
                    last_capture[name] = float(data.time)
                    next_capture[name] += period

    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
        raise FloatingPointError("E4 MuJoCo closed loop produced non-finite state")
    for name, image in cached_rgb.items():
        Image.fromarray(image).save(image_dir / f"step{args.policy_steps:03d}_{name}.png")
        renderers[name].close()

    actor.reset()
    replay_diffs = []
    with torch.inference_mode():
        for obs, expected in zip(captured_obs, captured_actions, strict=True):
            replay = actor.act_inference(obs)
            replay_diffs.append(float(torch.max(torch.abs(replay - expected))))
    replay_receipt = {
        "schema": "doordog.sim2sim.e4_image_replay_receipt.v1",
        "evidence_level": "E4_IMAGE_REPLAY",
        "result_classification": "VALID_COMPARABLE",
        "rows": len(captured_obs),
        "atol": 1.0e-6,
        "max_abs_diff": max(replay_diffs),
        "input_domain": "MUJOCO_NATIVE_RGB_AND_MUJOCO_PROPRIO",
        "policy_boundary": "native Hydra Student action_mean plus recurrent sequence",
    }
    if replay_receipt["max_abs_diff"] > replay_receipt["atol"]:
        raise AssertionError(f"E4 image replay drifted: {replay_receipt}")
    (output / "image_replay_receipt.json").write_text(
        json.dumps(replay_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    pixel_gap_data = {
        name: {
            "min_uint8": int(image.min()),
            "max_uint8": int(image.max()),
            "mean_rgb": image.mean(axis=(0, 1)).tolist(),
            "unique_rgb_count": int(np.unique(image.reshape(-1, 3), axis=0).shape[0]),
        }
        for name, image in cached_rgb.items()
    }
    closed_loop = {
        "schema": "doordog.sim2sim.e4_rgb_closed_loop_receipt.v1",
        "evidence_level": "E4_NATIVE_RGB_CLOSED_LOOP",
        "result_classification": "EXPLORATORY_NON_COMPARABLE",
        "scene": str(scene),
        "policy_bundle": str(bundle_dir),
        "device": "cpu",
        "policy_steps": args.policy_steps,
        "physics_steps": args.policy_steps * 4,
        "external_pd_clip_applications": args.policy_steps * 4,
        "policy_rows": policy_rows,
        "image_replay": replay_receipt,
        "pixel_domain_gap_data": pixel_gap_data,
        "task_metrics": metrics.receipt(),
        "final_state_finite": True,
        "stage_semantics": "NOT_MIGRATED; fixed nonzero arm-delta enable for execution probe",
        "warnings": [
            "No Isaac RTX pixels are available for paired comparison; MuJoCo pixel statistics are domain-gap data only.",
            "R6 excludes the production stage machine, so this short native-RGB loop is not a policy success/regression verdict."
        ],
    }
    (output / "closed_loop_receipt.json").write_text(
        json.dumps(closed_loop, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"image_replay": replay_receipt, "closed_loop": closed_loop}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
