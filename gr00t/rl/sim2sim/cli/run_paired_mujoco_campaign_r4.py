#!/usr/bin/env python3
"""Run the r4 standing-gated paired MuJoCo campaign on the READY Student."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import mujoco
import numpy as np
import torch
from PIL import Image

from gr00t.rl.sim2sim.cli.run_paired_mujoco_campaign import (
    CAMERA_NAMES,
    CAMERA_PERIODS,
    TRACE_SCHEMA,
    _body_state,
    _load_actor,
    _pixel_stats,
)
from gr00t.rl.sim2sim.doors.mjcf_builder_r4 import MjcfDoorBuilderR4
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.a2_base_obs import A2BaseFrameBuilder, A2BaseHistory
from gr00t.rl.sim2sim.mujoco.action_transform import A2ActionTransform
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
    STAGE_ACTION_BRANCH_AUDIT,
    STAGE_CONTRACT_NAME,
    Stage0ObservableState,
    StageContractMinimal,
)
from gr00t.rl.sim2sim.policy.observations import (
    build_actor_obs,
    compose_dual_rgb,
    normalize_rgb_nhwc,
)
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


def _render(
    renderer: mujoco.Renderer,
    data: mujoco.MjData,
    camera: str,
    option: mujoco.MjvOption,
) -> np.ndarray:
    renderer.update_scene(data, camera=camera, scene_option=option)
    return renderer.render().copy()


def _action_stats(values: list[np.ndarray]) -> dict[str, float]:
    material = np.asarray(values, dtype=np.float64)
    return {
        "mean_abs": float(np.mean(np.abs(material))),
        "std": float(np.std(material)),
        "max_abs": float(np.max(np.abs(material))),
    }


def _run_case(
    *,
    manifest: dict[str, Any],
    case: dict[str, Any],
    manifest_dir: Path,
    robot_xml: Path,
    bundle_manifest: dict[str, Any],
    actor: Any,
    a2_policy: Any,
    native_contract: ResolvedNativePositionContractR4,
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
    model_output.mkdir(parents=True)
    image_output.mkdir(parents=True)

    instance_path = (manifest_dir / case["door_instance_path"]).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(instance_path)
    if spec.friction_classification != "FRICTION_SEMANTICS_ALIGNED":
        raise ValueError(f"case {case_id} is outside the aligned-friction paired subdomain")
    door_xml = model_output / "door_r4.xml"
    door_report = model_output / "door_build_report_r4.json"
    external_scene = model_output / "external_pd_source_scene.xml"
    external_scene_report = model_output / "source_scene_build_report_v2.json"
    native_scene = model_output / "native_position_scene_r4.xml"
    native_scene_report = model_output / "native_position_scene_build_report_r4.json"
    scene_xml = model_output / "scene.xml"
    visual_scene_report = model_output / "policy_visual_scene_report_r4.json"
    MjcfDoorBuilderR4(spec).write(door_xml, door_report)
    PairedSceneBuilderV2(
        robot_xml,
        door_xml,
        armature_by_joint=native_contract.values_by_joint(native_contract.armature),
    ).write(external_scene, external_scene_report)
    NativePositionSceneR4(external_scene, native_contract).write(
        native_scene, native_scene_report
    )
    PolicyVisualSceneR4(native_scene).write(scene_xml, visual_scene_report)

    model = mujoco.MjModel.from_xml_path(str(scene_xml))
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    render_option = policy_scene_option_r4()
    policy_renderers = {
        "left": mujoco.Renderer(model, height=384, width=216),
        "right": mujoco.Renderer(model, height=384, width=216),
        "head": mujoco.Renderer(model, height=136, width=384),
    }
    overview_renderer = mujoco.Renderer(model, height=480, width=640)
    cached_rgb = {
        name: _render(policy_renderers[name], data, f"{name}_policy", render_option)
        for name in CAMERA_NAMES
    }
    frame_ids = {name: 0 for name in CAMERA_NAMES}
    last_capture = {name: float(data.time) for name in CAMERA_NAMES}
    next_capture = {name: period for name, period in CAMERA_PERIODS.items()}
    if episode_index == 0:
        Image.fromarray(
            _render(overview_renderer, data, "axis_overview", render_option)
        ).save(output_root / "mujoco_asset_initial.png")

    actor.init_rollout()
    actor.reset()
    robot_contract = resolved_a2_piper_contract()
    actuator_map = NameResolvedPositionActuatorMapR4.from_model(
        model, native_contract.joint_names
    )
    if actuator_map.door_hinge_actuator_id != 0 or actuator_map.handle_actuator_id != 1:
        raise ValueError("r4 campaign requires the two door actuators first")
    joint_map = A2PiperJointMap.from_sim_joint_names(
        robot_contract.sim_joint_names, device="cpu"
    )
    default32 = torch.tensor(robot_contract.default_dof_pos, dtype=torch.float32).unsqueeze(0)
    action_transform = A2ActionTransform(joint_map, action_scale=robot_contract.action_scale)
    frame_builder = A2BaseFrameBuilder(joint_map)
    history = A2BaseHistory(batch_size=1, device="cpu", dtype=torch.float32)
    gait = SensorClock(batch_size=1, physics_dt=0.005, device="cpu", dtype=torch.float32)
    stage_tracker = StageContractMinimal(dtype=torch.float32, device="cpu")
    previous_logical = torch.zeros((1, 19), dtype=torch.float32)
    previous_raw_delta = torch.zeros((1, 6), dtype=torch.float32)
    previous_base_raw = torch.zeros((1, 5), dtype=torch.float32)
    previous_base_physical = torch.zeros((1, 5), dtype=torch.float32)
    previous_leg = torch.zeros((1, 12), dtype=torch.float32)
    position_target = default32.clone()

    door_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    door_qpos_addr = int(model.jnt_qposadr[door_joint])
    handle_qpos_addr = int(model.jnt_qposadr[handle_joint])
    door_qvel_addr = int(model.jnt_dofadr[door_joint])
    handle_qvel_addr = int(model.jnt_dofadr[handle_joint])
    trunk_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    grasp_site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "door_grasp_target"
    )
    open_threshold = float(manifest["episode_contract"]["open_crossing_threshold_hinge_rad"])
    unlatch_threshold = float(manifest["episode_contract"]["unlatch_threshold_handle_rad"])
    horizon_policy_steps = int(manifest["episode_contract"]["horizon_policy_steps"])
    base_height_termination = float(manifest["episode_contract"]["base_height_termination_m"])
    image_mean = bundle_manifest["camera_rig"]["image_mean"]
    image_std = bundle_manifest["camera_rig"]["image_std"]
    trace_path = case_output / "trace.jsonl"
    stage_trace_path = case_output / "stage_trace.jsonl"
    max_hinge = float(data.qpos[door_qpos_addr])
    max_handle = float(data.qpos[handle_qpos_addr])
    first_unlatch_time = None
    first_open_time = None
    first_stage_transition = None
    physics_steps = 0
    policy_steps = 0
    termination_reason = "NONE"
    done = False
    max_target_write_error = 0.0
    max_effort_over_limit = 0.0
    max_generalized_force_error = 0.0
    max_abs_qacc = 0.0
    effort_limit = np.asarray(native_contract.effort_limit)
    raw_base_actions: list[np.ndarray] = []
    raw_arm_actions: list[np.ndarray] = []
    effective_arm_actions: list[np.ndarray] = []
    initial_root = data.qpos[:3].copy()
    initial_grasp = data.site_xpos[grasp_site_id].copy()
    min_root_to_grasp_x = float(initial_grasp[0] - initial_root[0])
    max_root_x = float(initial_root[0])
    max_arm_position_deviation = 0.0

    with (
        trace_path.open("w", encoding="utf-8") as trace_stream,
        stage_trace_path.open("w", encoding="utf-8") as stage_stream,
    ):
        for policy_step in range(horizon_policy_steps):
            local_angular_velocity, projected_gravity, roll_pitch, _ = _body_state(
                model, data, trunk_id
            )
            robot_qpos = data.qpos[actuator_map.robot_qpos_addresses].copy()
            robot_qvel = data.qvel[actuator_map.robot_qvel_addresses].copy()
            actor_values = {
                "base_ang_vel": torch.from_numpy(local_angular_velocity).float().unsqueeze(0),
                "projected_gravity": torch.from_numpy(projected_gravity).float().unsqueeze(0),
                "a2_student_dof_pos": torch.from_numpy(robot_qpos).float().unsqueeze(0)
                - default32,
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
                min(1.0, (float(data.time) - last_capture[name]) / 0.1)
                for name in CAMERA_NAMES
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
                "camera_meta": torch.tensor(
                    [[*ages, 1.0, 1.0, 1.0]], dtype=torch.float32
                ),
            }
            with torch.inference_mode():
                high_raw = actor.act_inference(obs)
            if tuple(high_raw.shape) != (1, 12) or not bool(torch.isfinite(high_raw).all()):
                raise FloatingPointError(
                    f"Student action invalid in {case_id} at policy step {policy_step}"
                )
            stage_action = stage_tracker.apply_high_level_action(high_raw)
            high_effective = stage_action.effective_high_level_action
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
            position_target = transformed.position_target
            input_frame_ids = [frame_ids[name] for name in CAMERA_NAMES]
            input_ages = list(ages)
            previous_logical = transformed.logical_action
            previous_raw_delta = stage_action.raw_arm_delta_echo
            previous_base_raw = high_raw[:, :5]
            previous_base_physical = physical_base
            previous_leg = leg_action
            raw_base_actions.append(high_raw[0, :5].numpy().copy())
            raw_arm_actions.append(high_raw[0, 5:11].numpy().copy())
            effective_arm_actions.append(high_effective[0, 5:11].numpy().copy())
            policy_steps += 1

            for substep in range(4):
                target_np = position_target.squeeze(0).double().numpy()
                actuator_map.write_robot_position_target(data, target_np)
                max_target_write_error = max(
                    max_target_write_error,
                    float(np.max(np.abs(data.ctrl[actuator_map.robot_actuator_ids] - target_np))),
                )
                mujoco.mj_step(model, data)
                applied_robot_effort = actuator_map.robot_actuator_force(data)
                max_effort_over_limit = max(
                    max_effort_over_limit,
                    float(np.max(np.maximum(np.abs(applied_robot_effort) - effort_limit, 0.0))),
                )
                max_generalized_force_error = max(
                    max_generalized_force_error,
                    float(
                        np.max(
                            np.abs(
                                actuator_map.robot_generalized_force(data)
                                - applied_robot_effort
                            )
                        )
                    ),
                )
                max_abs_qacc = max(max_abs_qacc, float(np.max(np.abs(data.qacc))))
                physics_steps += 1
                gait.advance(physical_base[:, :3])
                for name in CAMERA_NAMES:
                    if float(data.time) + 1.0e-12 >= next_capture[name]:
                        cached_rgb[name] = _render(
                            policy_renderers[name], data, f"{name}_policy", render_option
                        )
                        frame_ids[name] += 1
                        last_capture[name] = float(data.time)
                        next_capture[name] += CAMERA_PERIODS[name]

                if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                    raise FloatingPointError(
                        f"MuJoCo state invalid in {case_id} at physics step {physics_steps}"
                    )
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
                    "robot_qpos": data.qpos[actuator_map.robot_qpos_addresses].tolist(),
                    "robot_qvel": data.qvel[actuator_map.robot_qvel_addresses].tolist(),
                    "robot_ctrl_effort": applied_robot_effort.tolist(),
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
                        "hinge_drive_force_nm": float(
                            data.actuator_force[actuator_map.door_hinge_actuator_id]
                        ),
                        "handle_drive_force_nm": float(
                            data.actuator_force[actuator_map.handle_actuator_id]
                        ),
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

            root_position = torch.from_numpy(data.qpos[:3].copy()).float().unsqueeze(0)
            grasp_position = torch.from_numpy(
                data.site_xpos[grasp_site_id].copy()
            ).float().unsqueeze(0)
            arm_position = torch.from_numpy(
                data.qpos[actuator_map.robot_qpos_addresses[12:18]].copy()
            ).float().unsqueeze(0)
            stage_state = Stage0ObservableState(
                root_position_m=root_position,
                grasp_target_position_m=grasp_position,
                arm_position_rad=arm_position,
                arm_default_position_rad=default32[:, 12:18],
                physical_base_command=physical_base,
            )
            advanced = stage_tracker.observe_after_step(stage_state)
            if advanced and first_stage_transition is None:
                first_stage_transition = {
                    "policy_step_after_observation": policy_step,
                    "next_action_policy_step": policy_step + 1,
                    "time_s": float(data.time),
                }
            dx = float(grasp_position[0, 0] - root_position[0, 0])
            dy = float(root_position[0, 1] - grasp_position[0, 1])
            arm_deviation = float(torch.max(torch.abs(arm_position - default32[:, 12:18])))
            base_norm = float(torch.linalg.vector_norm(physical_base[:, :3]))
            min_root_to_grasp_x = min(min_root_to_grasp_x, dx)
            max_root_x = max(max_root_x, float(root_position[0, 0]))
            max_arm_position_deviation = max(max_arm_position_deviation, arm_deviation)
            stage_stream.write(
                json.dumps(
                    {
                        "policy_step": policy_step,
                        "time_s": float(data.time),
                        "stage_used_for_action": stage_action.stage_used_for_action,
                        "stage_after_observation": stage_tracker.stage,
                        "advanced_after_observation": advanced,
                        "root_position_m": root_position.squeeze(0).tolist(),
                        "grasp_target_position_m": grasp_position.squeeze(0).tolist(),
                        "staging_dx_m": dx,
                        "staging_dy_m": dy,
                        "arm_default_max_deviation_rad": arm_deviation,
                        "physical_base_command_norm_first3": base_norm,
                        "raw_arm_delta_echo": stage_action.raw_arm_delta_echo.squeeze(0).tolist(),
                        "effective_arm_delta": high_effective[0, 5:11].tolist(),
                    },
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            )
            if done:
                break

    for name, image in cached_rgb.items():
        Image.fromarray(image).save(image_output / f"final_{name}.png")
    if episode_index == 0:
        Image.fromarray(
            _render(overview_renderer, data, "axis_overview", render_option)
        ).save(output_root / "mujoco_asset_terminal.png")
    for renderer in policy_renderers.values():
        renderer.close()
    overview_renderer.close()

    final_root = data.qpos[:3].copy()
    purposeful_arm = bool(
        stage_tracker.stage >= 1
        and max(float(np.max(np.abs(value))) for value in effective_arm_actions) > 0.05
    )
    walked_toward_door = bool(max_root_x > float(initial_root[0]) + 0.1)
    receipt = {
        "schema": "doordog.sim2sim.paired_mujoco_episode_receipt.r4.v1",
        "result_classification": "VALID_WITH_WARNINGS",
        "manifest_id": manifest["manifest_id"],
        "case_id": case_id,
        "episode_index": episode_index,
        "seed": seed,
        "episode_complete": True,
        "termination_reason": termination_reason,
        "policy_steps": policy_steps,
        "physics_steps": physics_steps,
        "control_surface": {
            "mode": "MUJOCO_NATIVE_POSITION_TRUE_100_45",
            "integrator": "implicitfast",
            "d5_authorized_deviation": (
                "external PD per-step Python clip replaced by native position actuator "
                "forcerange inside implicitfast solve for all 20 robot joints"
            ),
            "max_target_write_error": max_target_write_error,
            "max_effort_over_limit": max_effort_over_limit,
            "max_generalized_force_error": max_generalized_force_error,
            "max_abs_qacc": max_abs_qacc,
        },
        "actuator_mapping": actuator_map.receipt(model),
        "stage_contract": {
            "name": STAGE_CONTRACT_NAME,
            "initial_stage": 0,
            "final_stage": stage_tracker.stage,
            "first_transition": first_stage_transition,
            "trace": str(stage_trace_path),
            "branch_audit": STAGE_ACTION_BRANCH_AUDIT,
        },
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
        "behavior_diagnostics": {
            "initial_root_position_m": initial_root.tolist(),
            "final_root_position_m": final_root.tolist(),
            "net_root_x_m": float(final_root[0] - initial_root[0]),
            "max_root_x_progress_m": float(max_root_x - initial_root[0]),
            "initial_root_to_grasp_x_m": float(initial_grasp[0] - initial_root[0]),
            "minimum_root_to_grasp_x_m": min_root_to_grasp_x,
            "raw_base_action": _action_stats(raw_base_actions),
            "raw_arm_action": _action_stats(raw_arm_actions),
            "effective_arm_action": _action_stats(effective_arm_actions),
            "max_arm_position_deviation_rad": max_arm_position_deviation,
            "walked_toward_door": walked_toward_door,
            "purposeful_arm_after_stage_enable": purposeful_arm,
            "major_progress_signal": walked_toward_door and purposeful_arm,
        },
        "pixel_domain_gap_data": {
            name: _pixel_stats(image) for name, image in cached_rgb.items()
        },
        "door_realization": {
            "door_instance": str(instance_path),
            "door_build_report": str(door_report),
            "source_scene_build_report": str(external_scene_report),
            "native_position_scene_build_report": str(native_scene_report),
            "policy_visual_scene_report": str(visual_scene_report),
            "friction_classification": spec.friction_classification,
            "mechanics_three_face_receipt": spec.mechanics_receipt(),
        },
        "warnings": [
            "READY payload is GRPO-finetuned Student: 91.2% over 512 Isaac instances (baseline 89.6%).",
            "Campaign behavior is pipeline/physics/domain evidence, not a standalone Student quality verdict.",
            "Failed episodes remain complete paired inputs; success rate is not the paired verdict.",
            "MuJoCo RGB statistics are domain-gap data and do not decide policy regression.",
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
    parser.add_argument("--standing-gate-receipt", required=True, type=Path)
    parser.add_argument("--visual-gate-receipt", required=True, type=Path)
    parser.add_argument("--stage-gate-receipt", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    standing_gate_path = args.standing_gate_receipt.resolve(strict=True)
    standing_gate = json.loads(standing_gate_path.read_text(encoding="utf-8"))
    if (
        standing_gate["result"] != "PASS"
        or standing_gate["campaign_authorization"] != "AUTHORIZED"
        or standing_gate["control_mode"] != "MUJOCO_NATIVE_POSITION_TRUE_100_45"
    ):
        raise ValueError("r4 campaign requires the true-100/45 standing-vitals PASS")
    visual_gate_path = args.visual_gate_receipt.resolve(strict=True)
    visual_gate = json.loads(visual_gate_path.read_text(encoding="utf-8"))
    if visual_gate["result"] != "PASS":
        raise ValueError("r4 campaign requires the visual parity prerequisite PASS")
    stage_gate_path = args.stage_gate_receipt.resolve(strict=True)
    stage_gate = json.loads(stage_gate_path.read_text(encoding="utf-8"))
    if stage_gate["result"] != "PASS":
        raise ValueError("r4 campaign requires the scripted stage contract PASS")

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
    output.mkdir(parents=True, exist_ok=False)
    actor = _load_actor(bundle_dir, args.student_source_root)
    a2_policy = torch.jit.load(
        str(args.a2_base_policy.resolve(strict=True)), map_location="cpu"
    ).eval()
    native_contract = ResolvedNativePositionContractR4.from_config(
        bundle_dir / "config_snapshot.yaml"
    )
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
            native_contract=native_contract,
            output_root=output,
        )
        receipts.append(receipt)
        print(
            json.dumps(
                {
                    "case_id": receipt["case_id"],
                    "termination_reason": receipt["termination_reason"],
                    "physics_steps": receipt["physics_steps"],
                    "final_stage": receipt["stage_contract"]["final_stage"],
                    "max_root_x_progress_m": receipt["behavior_diagnostics"][
                        "max_root_x_progress_m"
                    ],
                    "purposeful_arm": receipt["behavior_diagnostics"][
                        "purposeful_arm_after_stage_enable"
                    ],
                    "open_threshold_crossed": receipt["task_metrics"][
                        "open_threshold_crossed"
                    ],
                },
                sort_keys=True,
            ),
            flush=True,
        )

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    campaign = {
        "schema": "doordog.sim2sim.paired_mujoco_campaign_receipt.r4.v1",
        "evidence_level": "E4_FULL_CAMPAIGN_E5_MUJOCO_INPUT",
        "result_classification": "VALID_WITH_WARNINGS",
        "typed_conclusion": "UNRESOLVED_PENDING_E5",
        "input_status": "MUJOCO_CAMPAIGN_COMPLETE_ISAAC_PAIRED_TRACE_PENDING",
        "manifest_id": manifest["manifest_id"],
        "manifest": str(manifest_path),
        "manifest_case_seed_initial_state_unchanged_for_r4": True,
        "manifest_runtime_metadata_supersession": {
            "episode_contract.arm_delta_enable": STAGE_CONTRACT_NAME,
            "expectation.student_level": (
                "GRPO_FINETUNED_91.2_PERCENT_512_ISAAC_INSTANCES_BASELINE_89.6_PERCENT"
            ),
            "reason": "owner r3/r4 adjudication; case material itself remains unchanged",
        },
        "policy_bundle": str(bundle_dir),
        "standing_vitals_gate": str(standing_gate_path),
        "visual_gate": str(visual_gate_path),
        "stage_gate": str(stage_gate_path),
        "all_prerequisite_gates_passed": True,
        "backend": "mujoco_cpu_llvmpipe",
        "device": "cpu",
        "gpu_used": False,
        "case_count": len(receipts),
        "episode_receipts": receipts,
        "total_policy_steps": sum(item["policy_steps"] for item in receipts),
        "total_physics_steps": sum(item["physics_steps"] for item in receipts),
        "native_position_control": {
            "mode": "MUJOCO_NATIVE_POSITION_TRUE_100_45",
            "integrator": "implicitfast",
            "max_target_write_error": max(
                item["control_surface"]["max_target_write_error"] for item in receipts
            ),
            "max_effort_over_limit": max(
                item["control_surface"]["max_effort_over_limit"] for item in receipts
            ),
            "max_generalized_force_error": max(
                item["control_surface"]["max_generalized_force_error"] for item in receipts
            ),
            "max_abs_qacc": max(
                item["control_surface"]["max_abs_qacc"] for item in receipts
            ),
        },
        "stage_summary": {
            "contract": STAGE_CONTRACT_NAME,
            "cases_reaching_stage1": sum(
                item["stage_contract"]["final_stage"] >= 1 for item in receipts
            ),
            "cases_walking_toward_door": sum(
                item["behavior_diagnostics"]["walked_toward_door"] for item in receipts
            ),
            "cases_with_purposeful_arm_after_stage_enable": sum(
                item["behavior_diagnostics"]["purposeful_arm_after_stage_enable"]
                for item in receipts
            ),
            "cases_with_major_progress_signal": sum(
                item["behavior_diagnostics"]["major_progress_signal"] for item in receipts
            ),
        },
        "task_summary": {
            "cases_unlatched": sum(item["task_metrics"]["unlatched"] for item in receipts),
            "cases_open_threshold_crossed": sum(
                item["task_metrics"]["open_threshold_crossed"] for item in receipts
            ),
            "termination_reasons": {
                reason: sum(item["termination_reason"] == reason for item in receipts)
                for reason in ("HORIZON", "BASE_HEIGHT", "INVALID_NUMERICS")
            },
        },
        "asset_render": {
            "initial_screenshot": str(output / "mujoco_asset_initial.png"),
            "terminal_screenshot": str(output / "mujoco_asset_terminal.png"),
            "camera": "axis_overview",
            "policy_visibility_mask_applied": True,
            "render_contract": "MuJoCo Renderer under CPU Xvfb/llvmpipe; zero GPU",
        },
        "prior_campaign_status": {
            "r2": "INVALID_PHYSICS_SUPERSEDED_BY_R4",
            "r3": "INVALID_PHYSICS_SUPERSEDED_BY_R4",
            "meaning": "prior door-learning outcomes remain void; their evidence is retained",
        },
        "producer_identity": {
            "git_commit_before_phase_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/run_paired_mujoco_campaign_r4.py",
        },
        "warnings": [
            "READY payload is the GRPO-finetuned 91.2%/512 Student, not a pilot-level policy.",
            "Behavior is pipeline/physics/domain evidence and not a standalone Student quality verdict.",
            "Uncontrolled flying is not treated as expected behavior for this payload.",
            "Failed episodes remain in complete terminal traces.",
            "Success rate is not used as the paired trajectory/mechanics verdict.",
            "Formal camera and appearance adjudication awaits mandatory paired t=0 Isaac frames.",
            "Formal E5 remains typed pending until the user transfers Isaac paired traces.",
        ],
    }
    (output / "campaign_receipt.json").write_text(
        json.dumps(campaign, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "case_count": len(receipts),
                "total_physics_steps": campaign["total_physics_steps"],
                "stage_summary": campaign["stage_summary"],
                "task_summary": campaign["task_summary"],
                "native_position_control": campaign["native_position_control"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
