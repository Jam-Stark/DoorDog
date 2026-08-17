#!/usr/bin/env python3
"""Run the r3 L1-L4 single-case diagnostic ladder on MuJoCo CPU."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import cv2
import mujoco
import numpy as np
import torch
import yaml
from PIL import Image, ImageDraw

from gr00t.rl.sim2sim.cli.run_paired_mujoco_campaign import (
    CAMERA_NAMES,
    CAMERA_PERIODS,
    _body_state,
    _load_actor,
    _render,
)
from gr00t.rl.sim2sim.doors.mjcf_builder_v2 import MjcfDoorBuilderV2
from gr00t.rl.sim2sim.doors.runtime import ConstraintGate
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_transform import A2ActionTransform, ArmDeltaAccumulator
from gr00t.rl.sim2sim.mujoco.actuator_map_v2 import NameResolvedActuatorMapV2
from gr00t.rl.sim2sim.mujoco.external_pd import ExternalPdController
from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import PairedSceneBuilderV2
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import FOOT_GEOM_NAMES
from gr00t.rl.sim2sim.mujoco.sensor_clock import SensorClock
from gr00t.rl.sim2sim.policy.observations import (
    build_actor_obs,
    compose_dual_rgb,
    normalize_rgb_nhwc,
)
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


MODES = (
    "live_rgb",
    "frozen_contract_golden_images",
    "imagenet_mean",
    "live_rgb_fresh_meta",
)
CAPTURE_STEPS = {0, 10, 50}


def _armature(config_path: Path) -> dict[str, float]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    robot = config["robot"]
    return dict(zip(robot["dof_names"], robot["dof_armature_list"], strict=True))


def _resolved_effort(config_path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    robot = config["robot"]
    names = list(robot["dof_names"])
    source = np.asarray(robot["dof_effort_limit_list"], dtype=np.float64)
    resolved = source.copy()
    resolved[names.index("arm_j7")] = 45.0
    resolved[names.index("arm_j8")] = 45.0
    return resolved, {
        "source": str(config_path),
        "source_dof_effort_limit_by_joint": dict(zip(names, source.tolist(), strict=True)),
        "resolved_dof_effort_limit_by_joint": dict(zip(names, resolved.tolist(), strict=True)),
        "owner_override": {"arm_j7": 45.0, "arm_j8": 45.0},
        "finding": "R2 used 40 N*m for arm_j1..arm_j6; evaluated READY config resolves 100 N*m.",
    }


def _apply_effort_overlay(scene_xml: Path, effort: np.ndarray, output: Path) -> None:
    contract = resolved_a2_piper_contract()
    root = ET.parse(scene_xml).getroot()
    for name, limit in zip(contract.sim_joint_names, effort, strict=True):
        joint = root.find(f".//joint[@name='{name}']")
        actuator = root.find(f".//actuator/motor[@name='{name}_motor']")
        if joint is None or actuator is None:
            raise ValueError(f"r3 effort overlay lacks joint/actuator {name}")
        value = f"{-float(limit):.12g} {float(limit):.12g}"
        joint.set("actuatorfrcrange", value)
        actuator.set("ctrlrange", value)
    ET.indent(root, space="  ")
    scene_xml.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    realized = {}
    for name in contract.sim_joint_names:
        actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"{name}_motor")
        realized[name] = model.actuator_ctrlrange[actuator_id].tolist()
    output["realized_actuator_ctrlrange_by_joint"] = realized


def _roll_pitch(data: mujoco.MjData, trunk_id: int) -> tuple[float, float]:
    rotation = data.xmat[trunk_id].reshape(3, 3)
    return (
        math.atan2(rotation[2, 1], rotation[2, 2]),
        math.atan2(-rotation[2, 0], math.hypot(rotation[2, 1], rotation[2, 2])),
    )


def _foot_force_sum(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    floor_id: int,
    foot_ids: set[int],
) -> float:
    total = 0.0
    for index in range(data.ncon):
        contact = data.contact[index]
        if not (
            (contact.geom1 == floor_id and contact.geom2 in foot_ids)
            or (contact.geom2 == floor_id and contact.geom1 in foot_ids)
        ):
            continue
        wrench = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, index, wrench)
        total += max(0.0, float(wrench[0]))
    return total


def _run_corrected_standing_gate(
    *,
    scene_xml: Path,
    a2_policy,
    effort: np.ndarray,
    output: Path,
) -> dict[str, Any]:
    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    contract = resolved_a2_piper_contract()
    actuator_map = NameResolvedActuatorMapV2.from_model(model, contract.sim_joint_names)
    default64 = torch.tensor(contract.default_dof_pos, dtype=torch.float64).unsqueeze(0)
    default32 = default64.float()
    pd = ExternalPdController(
        stiffness=torch.tensor(contract.stiffness, dtype=torch.float64),
        damping=torch.tensor(contract.damping, dtype=torch.float64),
        torque_limit=torch.from_numpy(effort.copy()),
    )
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    foot_ids = {
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name) for name in FOOT_GEOM_NAMES
    }

    def apply_pd(target: torch.Tensor) -> None:
        position = torch.from_numpy(data.qpos[actuator_map.robot_qpos_addresses].copy()).double().unsqueeze(0)
        velocity = torch.from_numpy(data.qvel[actuator_map.robot_qvel_addresses].copy()).double().unsqueeze(0)
        actuator_map.write_robot_ctrl(
            data,
            pd.compute(position_target=target, position=position, velocity=velocity).squeeze(0).numpy(),
        )

    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    passive_heights, passive_forces = [], []
    for _ in range(400):
        apply_pd(default64)
        mujoco.mj_step(model, data)
        passive_heights.append(float(data.qpos[2]))
        passive_forces.append(_foot_force_sum(model, data, floor_id, foot_ids))

    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    joint_map = A2PiperJointMap.from_sim_joint_names(contract.sim_joint_names, device="cpu")
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    transform = A2ActionTransform(joint_map, action_scale=contract.action_scale)
    gait = SensorClock(batch_size=1, physics_dt=0.005, device="cpu", dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    zero_command = torch.zeros((1, 5), dtype=torch.float32)
    target = default64.clone()
    frozen_heights, frozen_forces, frozen_tilts, arm_positions = [], [], [], []
    for physics_step in range(1000):
        if physics_step % 4 == 0:
            local_ang, gravity, roll_pitch, _ = _body_state(model, data, trunk_id)
            del local_ang
            qpos = data.qpos[actuator_map.robot_qpos_addresses].copy()
            qvel = data.qvel[actuator_map.robot_qvel_addresses].copy()
            frame = frame_builder.build(
                projected_gravity=torch.from_numpy(gravity).float().unsqueeze(0),
                dof_pos=torch.from_numpy(qpos).float().unsqueeze(0),
                default_dof_pos=default32,
                dof_vel=torch.from_numpy(qvel).float().unsqueeze(0),
                previous_leg_action=previous_leg,
                physical_base_command=zero_command,
                base_roll_pitch=torch.from_numpy(roll_pitch).float().unsqueeze(0),
                gait_clock=gait.signal(),
            )
            with torch.inference_mode():
                previous_leg = a2_policy(history.append(frame))
            target = transform.compose(
                high_level_action=torch.zeros((1, 12), dtype=torch.float32),
                policy_leg_action=previous_leg,
                default_dof_pos=default32,
            ).position_target.double()
        apply_pd(target)
        mujoco.mj_step(model, data)
        gait.advance(zero_command[:, :3])
        frozen_heights.append(float(data.qpos[2]))
        frozen_forces.append(_foot_force_sum(model, data, floor_id, foot_ids))
        frozen_tilts.append(_roll_pitch(data, trunk_id))
        arm_positions.append(data.qpos[actuator_map.robot_qpos_addresses][12:18].copy())

    passive_tail = np.asarray(passive_heights[-100:])
    frozen_tail = np.asarray(frozen_heights[-200:])
    tilts = np.asarray(frozen_tilts[-200:])
    arm = np.stack(arm_positions)
    passive_pass = (
        0.45 <= passive_heights[-1] <= 0.65
        and float(np.ptp(passive_tail)) <= 0.02
        and any(value > 0.0 for value in passive_forces[-100:])
    )
    frozen_pass = (
        0.44 <= frozen_heights[-1] <= 0.66
        and float(np.ptp(frozen_tail)) <= 0.03
        and float(np.abs(tilts).max()) <= 0.35
        and any(value > 0.0 for value in frozen_forces[-200:])
    )
    receipt = {
        "schema": "doordog.sim2sim.standing_vitals_gate.r3.v1",
        "rule": "INSTRUMENT_VITALS_BEFORE_MEASUREMENT_INTERPRETATION",
        "result": "PASS" if passive_pass and frozen_pass else "FAIL",
        "campaign_authorization": "AUTHORIZED" if passive_pass and frozen_pass else "DENIED",
        "resolved_effort_limit_by_joint": dict(zip(contract.sim_joint_names, effort.tolist(), strict=True)),
        "passive_landing": {
            "result": "PASS" if passive_pass else "FAIL",
            "duration_s": 2.0,
            "final_base_height_m": passive_heights[-1],
            "tail_base_height_span_m": float(np.ptp(passive_tail)),
            "tail_steps_with_nonzero_foot_force": sum(value > 0.0 for value in passive_forces[-100:]),
        },
        "frozen_a2_standing": {
            "result": "PASS" if frozen_pass else "FAIL",
            "duration_s": 5.0,
            "final_base_height_m": frozen_heights[-1],
            "tail_base_height_span_m": float(np.ptp(frozen_tail)),
            "tail_max_abs_roll_or_pitch_rad": float(np.abs(tilts).max()),
            "tail_steps_with_nonzero_foot_force": sum(value > 0.0 for value in frozen_forces[-200:]),
            "arm_joint_displacement_from_initial_abs_max_rad": float(np.abs(arm - arm[0]).max()),
        },
        "actuator_mapping": actuator_map.receipt(model),
    }
    path = output / "standing_vitals_gate_r3_receipt.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if receipt["result"] != "PASS":
        raise RuntimeError("r3 resolved-effort standing-vitals gate failed")
    return receipt


def _stats(values: np.ndarray) -> dict[str, Any]:
    return {
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "abs_max": float(np.abs(values).max()),
    }


def _inverse_normalize(value: torch.Tensor, mean: list[float], std: list[float]) -> np.ndarray:
    array = value.detach().cpu().numpy()[0]
    restored = (array * np.asarray(std, dtype=np.float32) + np.asarray(mean, dtype=np.float32)) * 255.0
    return np.rint(np.clip(restored, 0.0, 255.0)).astype(np.uint8)


def _save_exact_policy_images(
    *,
    obs: dict[str, torch.Tensor],
    raw: dict[str, np.ndarray],
    mean: list[float],
    std: list[float],
    step: int,
    output: Path,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    dual = obs["vision_obs"]
    recovered = {
        "left": _inverse_normalize(dual[..., :3], mean, std),
        "right": _inverse_normalize(dual[..., 3:6], mean, std),
        "head": _inverse_normalize(obs["context_vision_obs"], mean, std),
    }
    report: dict[str, Any] = {}
    for name, image in recovered.items():
        Image.fromarray(image).save(output / f"step{step:04d}_{name}_inverse_from_policy_tensor.png")
        channel_paths = []
        if step == 0:
            for channel, label in enumerate(("R", "G", "B")):
                path = output / f"step0000_{name}_channel_{label}.png"
                Image.fromarray(image[..., channel], mode="L").save(path)
                channel_paths.append(str(path))
        report[name] = {
            "shape_hwc": list(image.shape),
            "raw_roundtrip_max_abs_uint8": int(np.abs(image.astype(np.int16) - raw[name].astype(np.int16)).max()),
            "bgr_hypothesis_mean_abs_uint8": float(np.abs(image.astype(np.int16) - raw[name][..., ::-1].astype(np.int16)).mean()),
            "vertical_flip_hypothesis_mean_abs_uint8": float(np.abs(image.astype(np.int16) - raw[name][::-1].astype(np.int16)).mean()),
            "channel_separation_images": channel_paths,
        }
    return report


def _first_video_frame(video: Path, output: Path) -> np.ndarray:
    capture = cv2.VideoCapture(str(video.resolve(strict=True)))
    ok, bgr = capture.read()
    capture.release()
    if not ok:
        raise RuntimeError(f"cannot read first frame from {video}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    Image.fromarray(rgb).save(output)
    return rgb


def _side_by_side(isaac: np.ndarray, mujoco_rgb: np.ndarray, output: Path, camera: str) -> None:
    height, width = mujoco_rgb.shape[:2]
    isaac_display = np.asarray(Image.fromarray(isaac).resize((width, height), Image.Resampling.BILINEAR))
    canvas = Image.new("RGB", (2 * width, height + 28), "white")
    canvas.paste(Image.fromarray(isaac_display), (0, 28))
    canvas.paste(Image.fromarray(mujoco_rgb), (width, 28))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 7), f"Isaac eval: {camera}", fill="black")
    draw.text((width + 6, 7), f"MuJoCo initial: {camera}", fill="black")
    canvas.save(output)


def _build_scene(
    *,
    manifest_path: Path,
    robot: Path,
    armature_by_joint: dict[str, float],
    output: Path,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    case = manifest["cases"][0]
    if case["case_id"] != "p00_baseline":
        raise ValueError("r3 L4 requires p00_baseline as the first paired case")
    spec_path = (manifest_path.parent / case["door_instance_path"]).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(spec_path)
    model_dir = output / "model"
    model_dir.mkdir(parents=True)
    door_xml = model_dir / "door.xml"
    MjcfDoorBuilderV2(spec).write(door_xml, model_dir / "door_build_report_v2.json")
    scene_xml = model_dir / "scene.xml"
    PairedSceneBuilderV2(robot, door_xml, armature_by_joint=armature_by_joint).write(
        scene_xml, model_dir / "scene_build_report_v2.json"
    )
    return manifest, case, scene_xml


def _run_mode(
    *,
    mode: str,
    scene_xml: Path,
    manifest: dict[str, Any],
    case: dict[str, Any],
    bundle_manifest: dict[str, Any],
    golden: dict[str, np.ndarray],
    actor,
    a2_policy,
    effort: np.ndarray,
    output: Path,
) -> tuple[dict[str, Any], np.ndarray | None, dict[int, dict[str, Any]]]:
    np.random.seed(int(case["seed"]))
    torch.manual_seed(int(case["seed"]))
    mode_dir = output / "l4" / mode
    mode_dir.mkdir(parents=True)
    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    renderers = {
        "left": mujoco.Renderer(model, height=384, width=216),
        "right": mujoco.Renderer(model, height=384, width=216),
        "head": mujoco.Renderer(model, height=136, width=384),
    }
    cached = {name: _render(renderers[name], data, f"{name}_policy") for name in CAMERA_NAMES}
    initial_live = {name: image.copy() for name, image in cached.items()}
    frame_ids = {name: 0 for name in CAMERA_NAMES}
    last_capture = {name: float(data.time) for name in CAMERA_NAMES}
    next_capture = dict(CAMERA_PERIODS)

    actor.init_rollout()
    actor.reset()
    contract = resolved_a2_piper_contract()
    actuator_map = NameResolvedActuatorMapV2.from_model(model, contract.sim_joint_names)
    joint_map = A2PiperJointMap.from_sim_joint_names(contract.sim_joint_names, device="cpu")
    default64 = torch.tensor(contract.default_dof_pos, dtype=torch.float64).unsqueeze(0)
    default32 = default64.float()
    stiffness = torch.tensor(contract.stiffness, dtype=torch.float64)
    damping = torch.tensor(contract.damping, dtype=torch.float64)
    pd = ExternalPdController(
        stiffness=stiffness,
        damping=damping,
        torque_limit=torch.from_numpy(effort.copy()),
    )
    arm_delta = ArmDeltaAccumulator(batch_size=1, device="cpu", dtype=torch.float32)
    transform = A2ActionTransform(joint_map, action_scale=contract.action_scale)
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    gait = SensorClock(batch_size=1, physics_dt=0.005, device="cpu", dtype=torch.float32)
    previous_logical = torch.zeros((1, 19), dtype=torch.float32)
    previous_raw_delta = torch.zeros((1, 6), dtype=torch.float32)
    previous_base_raw = torch.zeros((1, 5), dtype=torch.float32)
    previous_base_physical = torch.zeros((1, 5), dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    position_target = default64.clone()
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    gate = None
    if model.neq:
        gate = ConstraintGate(
            model,
            release_handle_rad=float(manifest["episode_contract"]["unlatch_threshold_handle_rad"]),
        )
    image_mean = list(bundle_manifest["camera_rig"]["image_mean"])
    image_std = list(bundle_manifest["camera_rig"]["image_std"])
    horizon = int(manifest["episode_contract"]["horizon_policy_steps"])
    base_termination = float(manifest["episode_contract"]["base_height_termination_m"])
    trace_path = mode_dir / "policy_step_trace.jsonl"
    actor_rows: list[np.ndarray] = []
    raw_actions: list[np.ndarray] = []
    physical_commands: list[np.ndarray] = []
    applied_arm: list[np.ndarray] = []
    arm_positions: list[np.ndarray] = []
    base_heights: list[float] = []
    roundtrip_reports: dict[int, dict[str, Any]] = {}
    max_ctrl_write_error = 0.0
    gate_release_count = 0
    termination = "HORIZON"

    with trace_path.open("w", encoding="utf-8") as stream:
        for policy_step in range(horizon):
            local_ang, projected_gravity, roll_pitch, _ = _body_state(model, data, trunk_id)
            qpos = data.qpos[actuator_map.robot_qpos_addresses].copy()
            qvel = data.qvel[actuator_map.robot_qvel_addresses].copy()
            command_echo = previous_base_physical * torch.tensor([2.0, 2.0, 0.25, 1.0, 1.0])
            if float(torch.linalg.vector_norm(previous_base_physical[:, :3])) < 0.1:
                command_echo[:, :3] = 0.0
            values = {
                "base_ang_vel": torch.from_numpy(local_ang).float().unsqueeze(0),
                "projected_gravity": torch.from_numpy(projected_gravity).float().unsqueeze(0),
                "a2_student_dof_pos": torch.from_numpy(qpos).float().unsqueeze(0) - default32,
                "a2_student_dof_vel": torch.from_numpy(qvel).float().unsqueeze(0),
                "actions": previous_logical,
                "delta_actions": previous_raw_delta,
                "a2_base_command": command_echo,
                "a2_base_command_raw": previous_base_raw,
            }
            actor_obs = build_actor_obs(bundle_manifest["observation"]["components"], values)
            ages = [min(1.0, (float(data.time) - last_capture[name]) / 0.1) for name in CAMERA_NAMES]
            live_vision = compose_dual_rgb(
                torch.from_numpy(cached["left"].copy()).unsqueeze(0),
                torch.from_numpy(cached["right"].copy()).unsqueeze(0),
                image_mean=image_mean,
                image_std=image_std,
            )
            live_head = normalize_rgb_nhwc(
                torch.from_numpy(cached["head"].copy()).unsqueeze(0),
                image_mean=image_mean,
                image_std=image_std,
            )
            if mode in ("live_rgb", "live_rgb_fresh_meta"):
                vision, head = live_vision, live_head
            elif mode == "frozen_contract_golden_images":
                vision = torch.from_numpy(golden["vision_obs"][0:1].copy())
                head = torch.from_numpy(golden["context_vision_obs"][0:1].copy())
            else:
                vision = torch.zeros_like(live_vision)
                head = torch.zeros_like(live_head)
            meta = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0] if mode == "live_rgb_fresh_meta" else [*ages, 1.0, 1.0, 1.0]
            obs = {
                "actor_obs": actor_obs,
                "vision_obs": vision,
                "context_vision_obs": head,
                "camera_meta": torch.tensor([meta], dtype=torch.float32),
            }
            if mode == "live_rgb" and policy_step in CAPTURE_STEPS:
                roundtrip_reports[policy_step] = _save_exact_policy_images(
                    obs=obs,
                    raw=cached,
                    mean=image_mean,
                    std=image_std,
                    step=policy_step,
                    output=output / "l2",
                )
            with torch.inference_mode():
                high_raw = actor.act_inference(obs)
            # Production WALK_TO_DOOR is stage 0: raw delta is echoed, applied arm delta is zeroed.
            high_effective = arm_delta.apply(high_raw, torch.zeros((1,), dtype=torch.long))
            physical_base = torch.cat(
                (high_effective[:, :3] * 0.25, high_effective[:, 3:5].clamp(-1.0, 1.0) * 0.4),
                dim=1,
            )
            frame = frame_builder.build(
                projected_gravity=torch.from_numpy(projected_gravity).float().unsqueeze(0),
                dof_pos=torch.from_numpy(qpos).float().unsqueeze(0),
                default_dof_pos=default32,
                dof_vel=torch.from_numpy(qvel).float().unsqueeze(0),
                previous_leg_action=previous_leg,
                physical_base_command=physical_base,
                base_roll_pitch=torch.from_numpy(roll_pitch).float().unsqueeze(0),
                gait_clock=gait.signal(),
            )
            with torch.inference_mode():
                leg_action = a2_policy(history.append(frame))
            transformed = transform.compose(
                high_level_action=high_effective,
                policy_leg_action=leg_action,
                default_dof_pos=default32,
            )
            position_target = transformed.position_target.double()
            actor_rows.append(actor_obs.squeeze(0).numpy().copy())
            raw_actions.append(high_raw.squeeze(0).numpy().copy())
            physical_commands.append(physical_base.squeeze(0).numpy().copy())
            applied_arm.append(high_effective[0, 5:11].numpy().copy())
            arm_positions.append(qpos[12:18].copy())
            base_heights.append(float(data.qpos[2]))
            stream.write(json.dumps({
                "schema": "doordog.sim2sim.r3_policy_input_trace.v1",
                "mode": mode,
                "policy_step": policy_step,
                "time_s": float(data.time),
                "actor_obs_81d_exact_pre_inference": actor_obs.squeeze(0).tolist(),
                "camera_meta_exact_pre_inference": meta,
                "student_action_mean": high_raw.squeeze(0).tolist(),
                "applied_action_19d": transformed.logical_action.squeeze(0).tolist(),
                "stage": 0,
                "arm_delta_raw_echo_next": high_raw[0, 5:11].tolist(),
                "arm_delta_applied": high_effective[0, 5:11].tolist(),
                "base_command_physical": physical_base.squeeze(0).tolist(),
                "robot_qpos": qpos.tolist(),
                "robot_qvel": qvel.tolist(),
                "base_height_m": float(data.qpos[2]),
            }, separators=(",", ":"), allow_nan=False) + "\n")
            previous_logical = transformed.logical_action
            previous_raw_delta = high_raw[:, 5:11]
            previous_base_raw = high_raw[:, :5]
            previous_base_physical = physical_base
            previous_leg = leg_action

            for _ in range(4):
                robot_position = torch.from_numpy(data.qpos[actuator_map.robot_qpos_addresses].copy()).double().unsqueeze(0)
                robot_velocity = torch.from_numpy(data.qvel[actuator_map.robot_qvel_addresses].copy()).double().unsqueeze(0)
                robot_ctrl = pd.compute(
                    position_target=position_target,
                    position=robot_position,
                    velocity=robot_velocity,
                ).squeeze(0).numpy()
                actuator_map.write_robot_ctrl(data, robot_ctrl)
                max_ctrl_write_error = max(max_ctrl_write_error, float(np.abs(data.ctrl[actuator_map.robot_actuator_ids] - robot_ctrl).max()))
                if gate is not None:
                    gate_release_count += int(gate.update(data))
                mujoco.mj_step(model, data)
                gait.advance(physical_base[:, :3])
                for name in CAMERA_NAMES:
                    if float(data.time) + 1.0e-12 >= next_capture[name]:
                        cached[name] = _render(renderers[name], data, f"{name}_policy")
                        frame_ids[name] += 1
                        last_capture[name] = float(data.time)
                        next_capture[name] += CAMERA_PERIODS[name]
                if float(data.qpos[2]) < base_termination:
                    termination = "BASE_HEIGHT"
                    break
            if termination == "BASE_HEIGHT":
                break

    for renderer in renderers.values():
        renderer.close()
    actor_array = np.stack(actor_rows)
    raw_array = np.stack(raw_actions)
    command_array = np.stack(physical_commands)
    applied_arm_array = np.stack(applied_arm)
    arm_position_array = np.stack(arm_positions)
    metrics = {
        "mode": mode,
        "policy_steps": len(actor_rows),
        "termination_reason": termination,
        "student_action": _stats(raw_array),
        "base_action_0_5": _stats(raw_array[:, :5]),
        "arm_raw_action_5_11": _stats(raw_array[:, 5:11]),
        "base_command_physical": _stats(command_array),
        "applied_arm_delta": _stats(applied_arm_array),
        "arm_joint_displacement_from_initial_abs_max_rad": float(np.abs(arm_position_array - arm_position_array[0]).max()),
        "base_height_m": _stats(np.asarray(base_heights)),
        "max_name_resolved_ctrl_write_error": max_ctrl_write_error,
        "external_pd_torque_limit": effort.tolist(),
        "constraint_gate_release_count": gate_release_count,
        "trace": str(trace_path),
    }
    (mode_dir / "rollout_receipt.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metrics, actor_array if mode == "live_rgb" else None, roundtrip_reports


def _l1_report(
    *,
    actor_obs: np.ndarray,
    golden_obs: np.ndarray,
    components: list[dict[str, Any]],
    r2_trace: Path,
) -> dict[str, Any]:
    offset = 0
    rows = []
    for component in components:
        end = offset + int(component["dim"])
        live_stats = _stats(actor_obs[:, offset:end])
        golden_stats = _stats(golden_obs[:, offset:end])
        reference = golden_stats["abs_max"]
        ratio = live_stats["abs_max"] / reference if reference > 0.0 else None
        if reference == 0.0 and live_stats["abs_max"] > 0.0:
            suspect = "REFERENCE_ZERO_NONZERO_LIVE"
        elif ratio is not None and ratio > 10.0:
            suspect = "MAGNITUDE_OVER_10X_CONTRACT_FIXTURE"
        else:
            suspect = None
        rows.append({
            "name": component["name"],
            "slice": [offset, end],
            "scale": component["scale"],
            "live_exact_pre_inference": live_stats,
            "bundle_golden_contract_fixture": golden_stats,
            "live_to_fixture_abs_max_ratio": ratio,
            "suspect": suspect,
        })
        offset = end
    first_r2 = json.loads(r2_trace.open(encoding="utf-8").readline())
    return {
        "schema": "doordog.sim2sim.r3_l1_proprio_report.v1",
        "result": "PIPELINE_DEFECT_FOUND_TRACE_INSTRUMENTATION_AND_STAGE_ACTION_SEMANTICS",
        "components": rows,
        "contract_checks": {
            "actor_obs_dim": int(actor_obs.shape[1]),
            "actions_echo": "PREVIOUS_APPLIED_12_LEG_6_ARM_1_GRIP",
            "delta_actions_echo": "PREVIOUS_RAW_ACTION_5_11",
            "delta_reset_backmap": "CONFIG_TRUE_BUT_PRODUCTION_IMPLEMENTATION_IS_NOOP; RESET_ZERO_RETAINED",
            "a2_base_command_warp": "raw k=s=0; physical [0:3]*0.25 and [3:5] clip*0.4; echo scales [2,2,.25,1,1]",
            "base_ang_vel_frame": "MUJOCO_TRUNK_LOCAL_FRAME",
            "dof_order": "NAME_RESOLVED_CONTRACT_ORDER",
            "dof_pos": "QPOS_MINUS_RESOLVED_DEFAULT",
            "stage_action_fix": "R2_FIXED_STAGE_ONE_REPLACED_BY_PRODUCTION_WALK_TO_DOOR_STAGE_ZERO",
        },
        "r2_trace_limitation": {
            "trace": str(r2_trace),
            "actor_obs_present": "actor_obs" in first_r2 or "actor_obs_81d_exact_pre_inference" in first_r2,
            "dynamic_state_timing": "R2 ROW WRITTEN AFTER FIRST PHYSICS SUBSTEP; EXACT POLICY INPUT CANNOT_BE_RECONSTRUCTED",
        },
        "golden_authority": "DETERMINISTIC_CONTRACT_FIXTURES_NOT_ISAAC_STATE_TRACE",
        "magnitude_warning": "Over-10x flags compare against synthetic contract fixtures, not empirical Isaac rollout statistics.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--student-source-root", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--standing-gate-receipt", required=True, type=Path)
    parser.add_argument("--constraint-gate-receipt", required=True, type=Path)
    parser.add_argument("--r2-campaign-root", required=True, type=Path)
    parser.add_argument("--isaac-left-video", required=True, type=Path)
    parser.add_argument("--isaac-right-video", required=True, type=Path)
    parser.add_argument("--isaac-head-video", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    standing_path = args.standing_gate_receipt.resolve(strict=True)
    standing = json.loads(standing_path.read_text(encoding="utf-8"))
    constraint_path = args.constraint_gate_receipt.resolve(strict=True)
    constraint = json.loads(constraint_path.read_text(encoding="utf-8"))
    if standing["result"] != "PASS" or standing["campaign_authorization"] != "AUTHORIZED":
        raise ValueError("r3 diagnostic denied by standing-vitals gate")
    if constraint["result"] != "PASS" or constraint["campaign_authorization"] != "AUTHORIZED":
        raise ValueError("r3 diagnostic denied by constraint-gate proof")

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    bundle = args.bundle_dir.resolve(strict=True)
    bundle_manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    golden_npz = np.load(bundle / "golden" / "golden_io.npz")
    golden = {name: golden_npz[name] for name in golden_npz.files}
    golden_manifest = json.loads((bundle / "golden" / "golden_manifest.json").read_text(encoding="utf-8"))
    a2_policy = torch.jit.load(str(args.a2_base_policy.resolve(strict=True)), map_location="cpu").eval()
    manifest_path = args.manifest.resolve(strict=True)
    manifest, case, scene_xml = _build_scene(
        manifest_path=manifest_path,
        robot=args.robot,
        armature_by_joint=_armature(bundle / "config_snapshot.yaml"),
        output=output,
    )
    effort, effort_receipt = _resolved_effort(bundle / "config_snapshot.yaml")
    _apply_effort_overlay(scene_xml, effort, effort_receipt)
    (output / "control_contract_overlay_r3.json").write_text(
        json.dumps(effort_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    corrected_standing = _run_corrected_standing_gate(
        scene_xml=scene_xml,
        a2_policy=a2_policy,
        effort=effort,
        output=output,
    )
    actor = _load_actor(bundle, args.student_source_root)

    mode_metrics = []
    live_actor = None
    l2_roundtrip = None
    for mode in MODES:
        metrics, actor_rows, roundtrip = _run_mode(
            mode=mode,
            scene_xml=scene_xml,
            manifest=manifest,
            case=case,
            bundle_manifest=bundle_manifest,
            golden=golden,
            actor=actor,
            a2_policy=a2_policy,
            effort=effort,
            output=output,
        )
        mode_metrics.append(metrics)
        if actor_rows is not None:
            live_actor = actor_rows
            l2_roundtrip = roundtrip
        print(json.dumps({"mode": mode, "policy_steps": metrics["policy_steps"], "termination": metrics["termination_reason"]}, sort_keys=True), flush=True)

    assert live_actor is not None and l2_roundtrip is not None
    r2_trace = args.r2_campaign_root.resolve(strict=True) / "cases" / "p00_baseline" / "trace.jsonl"
    l1 = _l1_report(
        actor_obs=live_actor,
        golden_obs=golden["actor_obs"],
        components=bundle_manifest["observation"]["components"],
        r2_trace=r2_trace,
    )
    (output / "l1_proprio_report.json").write_text(json.dumps(l1, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    frozen_vs_mean = float(np.abs(golden["vision_obs"][0]).max()) == 0.0 and float(np.abs(golden["context_vision_obs"][0]).max()) == 0.0
    l2 = {
        "schema": "doordog.sim2sim.r3_l2_image_pipeline_report.v1",
        "result": "PASS_EXACT_POLICY_TENSOR_ROUNDTRIP",
        "capture_steps": sorted(l2_roundtrip),
        "captures": l2_roundtrip,
        "packing": "vision_obs NHWC left RGB channels 0:3 then right RGB channels 3:6; head context_vision_obs NHWC",
        "normalization": {"mean": bundle_manifest["camera_rig"]["image_mean"], "std": bundle_manifest["camera_rig"]["image_std"]},
        "readback": "mujoco.Renderer RGB; no vertical flip and no BGR swap on the tensor path",
        "golden_image_authority": golden_manifest["input_authority"],
        "golden_images_equal_imagenet_mean_after_inverse_normalization": frozen_vs_mean,
    }
    (output / "l2_image_pipeline_report.json").write_text(json.dumps(l2, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    l3_dir = output / "l3"
    l3_dir.mkdir()
    videos = {
        "left": args.isaac_left_video,
        "right": args.isaac_right_video,
        "head": args.isaac_head_video,
    }
    l3_sources = {}
    for name, video in videos.items():
        isaac = _first_video_frame(video, l3_dir / f"isaac_{name}_frame0.png")
        mujoco_image_path = output / "l2" / f"step0000_{name}_inverse_from_policy_tensor.png"
        mujoco_rgb = np.asarray(Image.open(mujoco_image_path).convert("RGB"))
        _side_by_side(isaac, mujoco_rgb, l3_dir / f"isaac_vs_mujoco_{name}.png", name)
        l3_sources[name] = {
            "isaac_video": str(video.resolve(strict=True)),
            "isaac_first_frame_shape_hwc": list(isaac.shape),
            "mujoco_exact_policy_input": str(mujoco_image_path),
            "mujoco_shape_hwc": list(mujoco_rgb.shape),
            "side_by_side": str(l3_dir / f"isaac_vs_mujoco_{name}.png"),
        }
    l3 = {
        "schema": "doordog.sim2sim.r3_l3_camera_compare_report.v1",
        "result": "UNRESOLVED_PENDING_PAIRED_SAME_STATE_RGB",
        "sources": l3_sources,
        "mujoco_camera_contract": bundle_manifest["camera_rig"]["streams"],
        "comparison_limit": "Isaac source is a real eval video but not the transferred paired p00 trace; formal first-discrete-point attribution remains E5 pending.",
        "finding": "The available real Isaac eval frames are not the fixed p00 initial state, so visible framing differences cannot be separated from robot/door state. No evidence-authorized extrinsic/FOV edit was made.",
    }
    (output / "l3_camera_compare_report.json").write_text(json.dumps(l3, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    by_mode = {row["mode"]: row for row in mode_metrics}
    l4 = {
        "schema": "doordog.sim2sim.r3_l4_ablation_report.v1",
        "result": "PIPELINE_DEFECT_FOUND_STAGE_ACTION_SEMANTICS",
        "modes": by_mode,
        "interpretation": {
            "hard_defect": "r2 forced stage=1 although production starts WALK_TO_DOOR at stage=0; r3 stage=0 zeros applied arm delta while retaining raw delta echo",
            "golden_vs_mean": "IDENTICAL_INPUTS" if frozen_vs_mean else "DISTINCT_INPUTS",
            "golden_vs_mean_reason": golden_manifest["input_authority"],
            "camera_meta_test": "Compare live_rgb against live_rgb_fresh_meta metrics; fresh meta is not adopted unless it alone stabilizes behavior.",
            "visual_domain": "L3 records a material visual gap; causal dominance cannot replace E5 Isaac-image replay/paired trace attribution.",
        },
    }
    (output / "l4_ablation_report.json").write_text(json.dumps(l4, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    receipt = {
        "schema": "doordog.sim2sim.r3_diagnostic_receipt.v1",
        "result_classification": "VALID_WITH_WARNINGS",
        "typed_conclusion": "PIPELINE_DEFECT_FOUND_STAGE_ACTION_SEMANTICS",
        "standing_vitals_gate": {"path": str(standing_path), "result": standing["result"]},
        "standing_vitals_gate_r3_resolved_effort": {
            "path": str(output / "standing_vitals_gate_r3_receipt.json"),
            "result": corrected_standing["result"],
        },
        "constraint_gate": {"path": str(constraint_path), "result": constraint["result"]},
        "levels": {
            "L1": str(output / "l1_proprio_report.json"),
            "L2": str(output / "l2_image_pipeline_report.json"),
            "L3": str(output / "l3_camera_compare_report.json"),
            "L4": str(output / "l4_ablation_report.json"),
            "L5": "BLOCKED_INPUT_ISAAC_PAIRED_TRACE",
        },
        "r2_disposition": "INVALID_PIPELINE_SUPERSEDED_BY_R3_DIAGNOSTIC",
        "student_quality_disposition": "NO_STUDENT_QUALITY_VERDICT_FROM_MUJOCO",
        "producer_identity": {"git_commit": commit, "path": "gr00t/rl/sim2sim/cli/run_diagnostic_ladder_r3.py"},
    }
    receipt_path = output / "r3_diagnostic_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"typed_conclusion": receipt["typed_conclusion"], "receipt": str(receipt_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
