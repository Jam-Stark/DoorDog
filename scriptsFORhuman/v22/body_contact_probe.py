"""P0-E: high-level IsaacLab trunk/front-thigh panel-contact probe.

The scene uses one door-panel ContactSensor filtered against the A2 body list.
Four environments approach with the trunk and four with the front thighs
(two FL, two FR).  Robot placement uses Articulation.write_root_pose_to_sim;
no low-level USD stage mutation is used.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from ._v22_common import REPO_ROOT, V22_ARTIFACT_ROOT, V22Error, require_gpu, write_json


NUM_ENVS = 8
SIM_DT = 0.005
MAX_STEPS = 7_000
START_DISTANCE_M = 0.45
END_DISTANCE_M = 0.02
CONTACT_EVENT_N = 1.0
PENALTY_N = 150.0
TERMINATION_N = 300.0
BODY_FILTERS = (
    "trunk",
    "FL_hip",
    "FL_thigh",
    "FL_calf",
    "RL_hip",
    "RL_thigh",
    "RL_calf",
    "FR_hip",
    "FR_thigh",
    "FR_calf",
    "RR_hip",
    "RR_thigh",
    "RR_calf",
)
APPROVED = ("trunk", "FL_thigh", "FR_thigh")
TARGETS = (
    ("trunk", 0.00020),
    ("trunk", 0.00015),
    ("trunk", 0.00010),
    ("trunk", 0.000075),
    ("FL_thigh", 0.00015),
    ("FL_thigh", 0.000075),
    ("FR_thigh", 0.00015),
    ("FR_thigh", 0.000075),
)


def _run(device: str) -> dict:
    import torch
    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.sensors import ContactSensorCfg
    from isaaclab.sim import SimulationContext
    from isaaclab.utils import configclass
    from isaaclab.utils.math import quat_apply, quat_from_euler_xyz, quat_mul

    from gr00t.rl.envs.door.a2_piper_door_scene_preview import (
        build_a2_piper_robot_cfg,
        build_doorman_door_cfg,
        reset_preview_scene,
    )

    robot_usd = REPO_ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd"
    robot_base = build_a2_piper_robot_cfg(robot_usd)
    robot_cfg = robot_base.replace(
        spawn=robot_base.spawn.replace(activate_contact_sensors=True)
    )
    door_base = build_doorman_door_cfg(NUM_ENVS)
    for asset_cfg in door_base.spawn.assets_cfg:
        asset_cfg.activate_contact_sensors = True
        asset_cfg.articulation_props = asset_cfg.articulation_props.replace(
            fix_root_link=False
        )
    door_cfg = door_base.replace(spawn=door_base.spawn.replace(activate_contact_sensors=True))

    @configclass
    class BodyContactSceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane",
            spawn=sim_utils.GroundPlaneCfg(
                physics_material=sim_utils.RigidBodyMaterialCfg(
                    static_friction=1.0, dynamic_friction=1.0, restitution=0.0
                )
            ),
        )
        dome_light = AssetBaseCfg(
            prim_path="/World/DomeLight", spawn=sim_utils.DomeLightCfg(intensity=1500.0)
        )
        robot: ArticulationCfg = robot_cfg.replace(prim_path="{ENV_REGEX_NS}/Robot")
        door: ArticulationCfg = door_cfg.replace(prim_path="{ENV_REGEX_NS}/door")
        body_panel = ContactSensorCfg(
            prim_path="{ENV_REGEX_NS}/door/door_panel",
            filter_prim_paths_expr=[f"{{ENV_REGEX_NS}}/Robot/{name}" for name in BODY_FILTERS],
            history_length=0,
            update_period=0.0,
        )

    sim = SimulationContext(sim_utils.SimulationCfg(dt=SIM_DT, device=device))
    scene = InteractiveScene(
        BodyContactSceneCfg(num_envs=NUM_ENVS, env_spacing=5.0, replicate_physics=False)
    )
    sim.reset()
    reset_preview_scene(scene)
    robot: Articulation = scene["robot"]
    door: Articulation = scene["door"]
    for _ in range(10):
        robot.set_joint_position_target(robot.data.default_joint_pos)
        scene.write_data_to_sim()
        sim.step()
        scene.update(SIM_DT)

    panel_ids, panel_names = door.find_bodies(["door_panel"], preserve_order=True)
    if len(panel_ids) != 1:
        raise V22Error(f"P0-E requires one door_panel body; got {panel_names}")
    body_id_by_name = {}
    for name in APPROVED:
        ids, names = robot.find_bodies([name], preserve_order=True)
        if len(ids) != 1:
            raise V22Error(f"P0-E requires one robot body {name}; got {names}")
        body_id_by_name[name] = ids[0]

    robot_root_state = robot.data.default_root_state.clone()
    robot_root_state[:, :3] += scene.env_origins
    door_root_state = door.data.default_root_state.clone()
    door_root_state[:, :3] += scene.env_origins
    panel_pos = door.data.body_pos_w[:, panel_ids[0], :].clone()
    trunk_pos = robot.data.body_pos_w[:, body_id_by_name["trunk"], :].clone()
    target_pos = torch.stack(
        [robot.data.body_pos_w[env_id, body_id_by_name[name], :].clone() for env_id, (name, _) in enumerate(TARGETS)]
    )
    normals = torch.zeros(NUM_ENVS, 3, device=robot.device)
    normals[:4, 0] = 1.0
    for env_id in range(4, NUM_ENVS):
        outward = target_pos[env_id, :2] - trunk_pos[env_id, :2]
        normals[env_id, :2] = outward / torch.linalg.vector_norm(outward)

    yaw = torch.atan2(normals[:, 1], normals[:, 0])
    zeros = torch.zeros_like(yaw)
    yaw_quat = quat_from_euler_xyz(zeros, zeros, yaw)
    door_root_state[:, 3:7] = quat_mul(yaw_quat, door_root_state[:, 3:7])
    panel_offset = panel_pos - door.data.root_pos_w
    rotated_panel_offset = quat_apply(yaw_quat, panel_offset)

    placements = []
    for env_id, (target_name, approach_step) in enumerate(TARGETS):
        placements.append(
            {
                "env_id": env_id,
                "target_body": target_name,
                "approach_step_m": approach_step,
                "panel_approach_normal_xy": normals[env_id, :2].cpu().tolist(),
            }
        )

    sensor = scene["body_panel"]
    distance = torch.full((NUM_ENVS,), START_DISTANCE_M, device=robot.device)
    approach_step = torch.tensor([row[1] for row in TARGETS], device=robot.device)
    latched = torch.zeros(NUM_ENVS, dtype=torch.bool, device=robot.device)
    first_target_force = torch.zeros(NUM_ENVS, device=robot.device)
    first_forbidden_force = torch.zeros(NUM_ENVS, device=robot.device)
    first_overall_force = torch.zeros(NUM_ENVS, device=robot.device)
    first_body_force = torch.zeros(NUM_ENVS, len(BODY_FILTERS), device=robot.device)
    first_distance = torch.full((NUM_ENVS,), float("nan"), device=robot.device)
    first_step = torch.full((NUM_ENVS,), -1, dtype=torch.long, device=robot.device)
    outcome = [None] * NUM_ENVS
    target_indices = torch.tensor(
        [BODY_FILTERS.index(name) for name, _ in TARGETS],
        dtype=torch.long,
        device=robot.device,
    )
    forbidden_indices = torch.tensor(
        [index for index, name in enumerate(BODY_FILTERS) if name not in APPROVED],
        dtype=torch.long,
        device=robot.device,
    )
    for step in range(MAX_STEPS):
        distance = torch.where(
            latched,
            distance,
            torch.clamp(distance - approach_step, min=END_DISTANCE_M),
        )
        desired_panel_pos = target_pos + normals * distance[:, None]
        door_root_state[:, :3] = desired_panel_pos - rotated_panel_offset
        door.write_root_pose_to_sim(door_root_state[:, :7])
        door.write_root_velocity_to_sim(torch.zeros_like(door_root_state[:, 7:]))
        door.write_joint_state_to_sim(
            door.data.default_joint_pos.clone(), torch.zeros_like(door.data.default_joint_vel)
        )
        robot.write_root_pose_to_sim(robot_root_state[:, :7])
        robot.write_root_velocity_to_sim(torch.zeros_like(robot_root_state[:, 7:]))
        robot.write_joint_state_to_sim(
            robot.data.default_joint_pos.clone(), torch.zeros_like(robot.data.default_joint_vel)
        )
        robot.set_joint_position_target(robot.data.default_joint_pos)
        door.set_joint_effort_target(torch.zeros_like(door.data.joint_pos))
        scene.write_data_to_sim()
        sim.step()
        scene.update(SIM_DT)
        force_matrix = sensor.data.force_matrix_w
        if force_matrix is None or tuple(force_matrix.shape) != (NUM_ENVS, 1, len(BODY_FILTERS), 3):
            raise V22Error(
                "P0-E expected force_matrix_w shape "
                f"({NUM_ENVS}, 1, {len(BODY_FILTERS)}, 3); got "
                f"{None if force_matrix is None else tuple(force_matrix.shape)}"
            )
        force = torch.linalg.vector_norm(force_matrix[:, 0, :, :], dim=-1)
        target_force = force.gather(1, target_indices[:, None]).squeeze(1)
        forbidden_force = force[:, forbidden_indices].amax(dim=1)
        overall_force = force.amax(dim=1)
        active = ~latched
        target_contact = active & (target_force >= CONTACT_EVENT_N)
        unsafe_before_target = active & ~target_contact & (
            (forbidden_force >= CONTACT_EVENT_N) | (overall_force >= TERMINATION_N)
        )
        exhausted = active & ~target_contact & ~unsafe_before_target & (distance <= END_DISTANCE_M)
        newly_latched = target_contact | unsafe_before_target | exhausted
        first_target_force = torch.where(newly_latched, target_force, first_target_force)
        first_forbidden_force = torch.where(newly_latched, forbidden_force, first_forbidden_force)
        first_overall_force = torch.where(newly_latched, overall_force, first_overall_force)
        first_body_force = torch.where(newly_latched[:, None], force, first_body_force)
        first_distance = torch.where(newly_latched, distance, first_distance)
        first_step = torch.where(newly_latched, torch.full_like(first_step, step + 1), first_step)
        for env_id in torch.nonzero(newly_latched, as_tuple=False).flatten().cpu().tolist():
            if bool(target_contact[env_id]):
                outcome[env_id] = "TARGET_CONTACT"
            elif bool(unsafe_before_target[env_id]):
                outcome[env_id] = "UNSAFE_NON_TARGET_CONTACT"
            else:
                outcome[env_id] = "NO_TARGET_CONTACT"
        latched |= newly_latched
        if bool(torch.all(latched)):
            break
    if not bool(torch.all(latched)):
        raise V22Error("P0-E quasi-static approach did not reach a terminal outcome in every env")

    first_body_cpu = first_body_force.cpu().tolist()
    first_target_cpu = first_target_force.cpu().tolist()
    first_forbidden_cpu = first_forbidden_force.cpu().tolist()
    first_overall_cpu = first_overall_force.cpu().tolist()
    first_distance_cpu = first_distance.cpu().tolist()
    first_step_cpu = first_step.cpu().tolist()
    rows = []
    for placement in placements:
        env_id = placement["env_id"]
        target_name = placement["target_body"]
        target_index = BODY_FILTERS.index(target_name)
        target_peak = float(first_target_cpu[env_id])
        forbidden_peak = float(first_forbidden_cpu[env_id])
        overall_peak = float(first_overall_cpu[env_id])
        rows.append(
            {
                **placement,
                "outcome": outcome[env_id],
                "first_event_step": int(first_step_cpu[env_id]),
                "first_event_panel_distance_m": float(first_distance_cpu[env_id]),
                "target_peak_force_n": target_peak,
                "forbidden_peak_force_n": forbidden_peak,
                "overall_peak_force_n": overall_peak,
                "per_body_peak_force_n": {
                    name: float(value) for name, value in zip(BODY_FILTERS, first_body_cpu[env_id])
                },
                "safe_target_contact": (
                    outcome[env_id] == "TARGET_CONTACT"
                    and CONTACT_EVENT_N <= target_peak <= PENALTY_N
                    and forbidden_peak < CONTACT_EVENT_N
                    and overall_peak < TERMINATION_N
                ),
            }
        )

    target_pass = {
        name: any(row["safe_target_contact"] for row in rows if row["target_body"] == name)
        for name in APPROVED
    }
    sim.clear_all_callbacks()
    return {
        "rows": rows,
        "target_pass": target_pass,
        "status": "P0_E_PASS" if all(target_pass.values()) else "P0_E_UNSAFE_OR_UNREALIZED",
        "thresholds_n": {
            "contact_event": CONTACT_EVENT_N,
            "penalty": PENALTY_N,
            "termination": TERMINATION_N,
        },
        "api_contract": {
            "contact_sensor": "ContactSensorCfg door_panel one-to-many filter; force_matrix_w",
            "placement": "quasi-static panel approach via Articulation.write_root_pose_to_sim",
            "low_level_usd_used": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, required=True)
    args = parser.parse_args()
    gpu = require_gpu(args.gpu)
    from isaaclab.app import AppLauncher

    launcher = AppLauncher({"headless": True, "device": f"cuda:{gpu}", "enable_cameras": False})
    try:
        measured = _run(f"cuda:{gpu}")
        payload = {
            "schema": "a2_piper_base_v22_body_contact_probe_v1",
            "plan_id": "base_v22_posture_clearance_force_routing_v3",
            "execution_id": "base_v22_execution_v3",
            "node": "P0-E",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            ),
            **measured,
        }
        target = REPO_ROOT / V22_ARTIFACT_ROOT / "locks/V22_BODY_CONTACT_PROBE.json"
        write_json(target, payload)
        print(f"P0-E {payload['status']} target={target}")
        return 0 if payload["status"] == "P0_E_PASS" else 2
    finally:
        launcher.app.close()


if __name__ == "__main__":
    raise SystemExit(main())
