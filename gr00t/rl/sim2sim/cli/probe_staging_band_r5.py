#!/usr/bin/env python3
"""Pre-authorized r5 CPU discriminative probe: clean in-staging-band initialization.

Splits "visually did not recognize the arrival configuration" from "command
dynamics never converge": the robot starts stationary inside the staging band
with zeroed command history and a naturally evolving LSTM state, and the probe
records whether the Student ever issues an in-contract base-still command
(xyz norm <= 0.1) and whether stage1 enables.
"""

from __future__ import annotations

import argparse
import json
import subprocess
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


def _render(
    renderer: mujoco.Renderer,
    data: mujoco.MjData,
    camera: str,
    option: mujoco.MjvOption,
) -> np.ndarray:
    renderer.update_scene(data, camera=camera, scene_option=option)
    return renderer.render().copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--robot", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--student-source-root", required=True, type=Path)
    parser.add_argument("--a2-base-policy", required=True, type=Path)
    parser.add_argument("--resolved-config", required=True, type=Path)
    parser.add_argument("--campaign-receipt", required=True, type=Path)
    parser.add_argument("--case", default="p00_baseline")
    parser.add_argument("--dx", type=float, default=0.65)
    parser.add_argument("--horizon-policy-steps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=41001)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    campaign_receipt = json.loads(
        args.campaign_receipt.resolve(strict=True).read_text(encoding="utf-8")
    )
    if campaign_receipt["typed_conclusion"] != (
        "IN_CONTRACT_0_OF_8_BASE_STILL_STUDENT_UNDER_GAP_EVIDENCE"
    ):
        raise ValueError("the staging-band probe requires the r5 in-contract 0/8 result")

    manifest = json.loads(args.manifest.resolve(strict=True).read_text(encoding="utf-8"))
    manifest_dir = args.manifest.resolve(strict=True).parent
    case = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    instance_path = (manifest_dir / case["door_instance_path"]).resolve(strict=True)
    spec = DoorInstanceSpec.from_path(instance_path)
    if spec.friction_classification != "FRICTION_SEMANTICS_ALIGNED":
        raise ValueError("probe case is outside the aligned-friction paired subdomain")
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)

    bundle_dir = args.bundle_dir.resolve(strict=True)
    bundle_manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    if bundle_manifest["artifact_status"] != "READY":
        raise ValueError("probe requires a READY policy bundle")
    image_mean = bundle_manifest["camera_rig"]["image_mean"]
    image_std = bundle_manifest["camera_rig"]["image_std"]

    door_xml = output / "door_r4.xml"
    external_scene = output / "external_pd_source_scene.xml"
    native_scene = output / "native_position_scene_r4.xml"
    scene_xml = output / "scene.xml"
    native_contract = ResolvedNativePositionContractR4.from_config(args.resolved_config)
    warp_contract = ResolvedActionWarpContractR5.from_config(args.resolved_config)
    MjcfDoorBuilderR4(spec).write(door_xml, output / "door_build_report_r4.json")
    PairedSceneBuilderV2(
        args.robot.resolve(strict=True),
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
    grasp_site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "door_grasp_target"
    )
    mujoco.mj_forward(model, data)
    grasp = data.site_xpos[grasp_site_id].copy()
    data.qpos[0] = float(grasp[0]) - args.dx
    data.qpos[1] = float(grasp[1])
    data.qvel[:] = 0.0
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
    Image.fromarray(
        _render(overview_renderer, data, "axis_overview", render_option)
    ).save(output / "probe_initial.png")

    actor = _load_actor(bundle_dir, args.student_source_root)
    actor.init_rollout()
    actor.reset()
    a2_policy = torch.jit.load(
        str(args.a2_base_policy.resolve(strict=True)), map_location="cpu"
    ).eval()
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
        contract=warp_contract,
        joint_map=joint_map,
        stage_tracker=stage_tracker,
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
    next_capture = {name: period for name, period in CAMERA_PERIODS.items()}

    initial_root = data.qpos[:3].copy()
    initial_dx = float(grasp[0] - initial_root[0])
    initial_dy = float(initial_root[1] - grasp[1])
    if not (0.5 <= initial_dx <= 0.8) or abs(initial_dy) >= 0.15:
        raise FloatingPointError(
            f"probe initial state is not inside the staging band: dx={initial_dx} dy={initial_dy}"
        )
    if float(np.max(np.abs(data.qvel[:]))) != 0.0:
        raise FloatingPointError("probe initial state is not stationary")

    physical_norms: list[float] = []
    base_still_steps = 0
    in_band_steps = 0
    first_stage_transition = None
    trace_path = output / "probe_trace.jsonl"
    max_abs_qacc = 0.0
    physics_steps = 0
    with trace_path.open("w", encoding="utf-8") as stream:
        for policy_step in range(args.horizon_policy_steps):
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
                "a2_base_command": action_warp.observation_command_echo(
                    previous_base_physical
                ),
                "a2_base_command_raw": previous_base_raw,
            }
            actor_obs = build_actor_obs(
                bundle_manifest["observation"]["components"], actor_values
            )
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
                    f"Student action invalid in probe at policy step {policy_step}"
                )
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
            physical_norms.append(base_norm)
            if base_norm <= stage_tracker.base_still_norm_max:
                base_still_steps += 1

            for substep in range(4):
                actuator_map.write_robot_position_target(
                    data, position_target.squeeze(0).double().numpy()
                )
                mujoco.mj_step(model, data)
                physics_steps += 1
                gait.advance(warped.base.physical[:, :3])
                max_abs_qacc = max(max_abs_qacc, float(np.max(np.abs(data.qacc))))
                for name in CAMERA_NAMES:
                    if float(data.time) + 1.0e-12 >= next_capture[name]:
                        cached_rgb[name] = _render(
                            policy_renderers[name], data, f"{name}_policy", render_option
                        )
                        last_capture[name] = float(data.time)
                        next_capture[name] += CAMERA_PERIODS[name]
                if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                    raise FloatingPointError(
                        f"MuJoCo state invalid in probe at physics step {physics_steps}"
                    )

            root_position = torch.from_numpy(data.qpos[:3].copy()).float().unsqueeze(0)
            grasp_position = torch.from_numpy(
                data.site_xpos[grasp_site_id].copy()
            ).float().unsqueeze(0)
            arm_position = torch.from_numpy(
                data.qpos[actuator_map.robot_qpos_addresses[12:18]].copy()
            ).float().unsqueeze(0)
            dx = float(grasp_position[0, 0] - root_position[0, 0])
            dy = float(root_position[0, 1] - grasp_position[0, 1])
            arm_deviation = float(torch.max(torch.abs(arm_position - default32[:, 12:18])))
            if 0.5 <= dx <= 0.8 and abs(dy) < 0.15:
                in_band_steps += 1
            advanced = stage_tracker.observe_after_step(
                Stage0ObservableState(
                    root_position_m=root_position,
                    grasp_target_position_m=grasp_position,
                    arm_position_rad=arm_position,
                    arm_default_position_rad=default32[:, 12:18],
                    physical_base_command=warped.base.physical,
                )
            )
            if advanced and first_stage_transition is None:
                first_stage_transition = {
                    "policy_step_after_observation": policy_step,
                    "time_s": float(data.time),
                    "physical_base_command_norm_first3": base_norm,
                }
            stream.write(
                json.dumps(
                    {
                        "policy_step": policy_step,
                        "time_s": float(data.time),
                        "staging_dx_m": dx,
                        "staging_dy_m": dy,
                        "in_band": 0.5 <= dx <= 0.8 and abs(dy) < 0.15,
                        "arm_default_max_deviation_rad": arm_deviation,
                        "physical_base_command_norm_first3": base_norm,
                        "base_still": base_norm <= stage_tracker.base_still_norm_max,
                        "stage_after_observation": stage_tracker.stage,
                        "advanced_after_observation": advanced,
                    },
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            )

    Image.fromarray(
        _render(overview_renderer, data, "axis_overview", render_option)
    ).save(output / "probe_terminal.png")
    for renderer in policy_renderers.values():
        renderer.close()
    overview_renderer.close()

    norms = np.asarray(physical_norms, dtype=np.float64)
    stage1 = stage_tracker.stage >= 1
    if stage1:
        typed = "POLICY_CAN_HOLD_BASE_STILL_IN_BAND_STAGE1_ADVANCED"
    elif base_still_steps > 0:
        typed = "BASE_STILL_COMMAND_OBSERVED_WITHOUT_STAGE1_TRANSITION"
    else:
        typed = "COMMAND_DYNAMICS_NEVER_CONVERGE_FROM_CLEAN_IN_BAND_START"
    final_root = data.qpos[:3].copy()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "schema": "doordog.sim2sim.staging_band_probe.r5.v1",
        "rule": "P2_PRE_AUTHORIZED_DISCRIMINATIVE_PROBE_AFTER_CAMPAIGN",
        "campaign_receipt": str(args.campaign_receipt.resolve(strict=True)),
        "case_id": args.case,
        "seed": args.seed,
        "initialization": {
            "mode": "STATIONARY_INSIDE_STAGING_BAND",
            "command_history_zeroed": True,
            "lstm_state": "RESET_THEN_NATURAL_EVOLUTION",
            "initial_staging_dx_m": initial_dx,
            "initial_staging_dy_m": initial_dy,
            "initial_root_position_m": initial_root.tolist(),
        },
        "typed_conclusion": typed,
        "final_stage": stage_tracker.stage,
        "first_stage_transition": first_stage_transition,
        "base_still_steps": base_still_steps,
        "in_band_steps": in_band_steps,
        "policy_steps": args.horizon_policy_steps,
        "physics_steps": physics_steps,
        "physical_base_command_norm_first3": {
            "min": float(np.min(norms)),
            "p25": float(np.percentile(norms, 25)),
            "p50": float(np.percentile(norms, 50)),
            "p75": float(np.percentile(norms, 75)),
            "max": float(np.max(norms)),
        },
        "root_motion": {
            "initial_position_m": initial_root.tolist(),
            "final_position_m": final_root.tolist(),
            "net_x_m": float(final_root[0] - initial_root[0]),
        },
        "control_surface": {
            "mode": "MUJOCO_NATIVE_POSITION_TRUE_100_45_R5_FULL_ACTION_WARP",
            "integrator": "implicitfast",
            "max_abs_qacc": max_abs_qacc,
        },
        "trace": str(trace_path),
        "producer_identity": {
            "git_commit_before_phase_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/probe_staging_band_r5.py",
        },
        "warnings": [
            "Probe evidence splits command-dynamics vs in-band visual recognition; it does not replace the campaign or the paired t=0 Isaac adjudication.",
            "Formal visual attribution remains blocked on the mandatory paired t=0 Isaac frames.",
        ],
    }
    (output / "staging_band_probe_r5_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "typed_conclusion": typed,
                "final_stage": stage_tracker.stage,
                "base_still_steps": base_still_steps,
                "in_band_steps": in_band_steps,
                "norm_summary": receipt["physical_base_command_norm_first3"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
