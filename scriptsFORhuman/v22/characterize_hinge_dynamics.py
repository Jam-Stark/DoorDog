"""P0-D — mandatory hinge dynamics characterization (plan §6).

Runs a door-only IsaacLab scene: no robot, no policy, no contact.  It first reads
the actual spawned USD drive attributes (§6.0), then measures free return (§6.1),
fixed-torque opening progress (§6.2), and one-parameter attribution (§6.3), and
finally freezes the H0-H4 ranges from measured response (§6.4).

Nothing here is inferred from a scenario name and nothing is assumed about the
historical damping value of 50.0 — that number is treated as unverified until
this probe reads it back from a spawned asset.

Outputs:
    logs_eval/base_v22/locks/V22_HINGE_RUNTIME_BASELINE.json
    logs_eval/base_v22/locks/V22_HINGE_DYNAMICS_PROBE.json
    logs_eval/base_v22/locks/V22_HINGE_RANGE_FREEZE.json
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path


# Registered probe tuples.  The grid deliberately spans the §5.3 worker-adjustable
# bounds so the response classes are measured, not assumed.
PROBE_TUPLES = (
    {"tuple_id": "T00", "damping": 30.0, "stiffness": 2.0, "max_force_nm": 5.0},
    {"tuple_id": "T01", "damping": 30.0, "stiffness": 6.0, "max_force_nm": 10.0},
    {"tuple_id": "T02", "damping": 50.0, "stiffness": 2.0, "max_force_nm": 10.0},
    {"tuple_id": "T03", "damping": 50.0, "stiffness": 6.0, "max_force_nm": 10.0},
    {"tuple_id": "T04", "damping": 50.0, "stiffness": 6.0, "max_force_nm": 20.0},
    {"tuple_id": "T05", "damping": 50.0, "stiffness": 10.0, "max_force_nm": 12.0},
    {"tuple_id": "T06", "damping": 70.0, "stiffness": 6.0, "max_force_nm": 12.0},
    {"tuple_id": "T07", "damping": 100.0, "stiffness": 6.0, "max_force_nm": 12.0},
    {"tuple_id": "T08", "damping": 120.0, "stiffness": 6.0, "max_force_nm": 12.0},
    {"tuple_id": "T09", "damping": 150.0, "stiffness": 20.0, "max_force_nm": 20.0},
    {"tuple_id": "T10", "damping": 15.0, "stiffness": 14.0, "max_force_nm": 14.0},
    {"tuple_id": "T11", "damping": 25.0, "stiffness": 18.0, "max_force_nm": 16.0},
    {"tuple_id": "T12", "damping": 40.0, "stiffness": 20.0, "max_force_nm": 18.0},
    {"tuple_id": "T13", "damping": 50.0, "stiffness": 8.0, "max_force_nm": 16.0},
    {"tuple_id": "T14", "damping": 50.0, "stiffness": 8.0, "max_force_nm": 24.0},
    {"tuple_id": "T15", "damping": 90.0, "stiffness": 14.0, "max_force_nm": 20.0},
)
CORE_TUPLE_ID = "T03"

FREE_RETURN_START_RAD = 1.20
FREE_RETURN_MARKS_RAD = (0.90, 0.60, 0.30)
FREE_RETURN_MAX_SECONDS = 12.0
FIXED_TORQUES_NM = (5.0, 10.0, 15.0, 20.0)
FIXED_TORQUE_SECONDS = 3.0
SIM_DT = 0.005
DOOR_MASS_KG = 120.0
DOOR_HANDLE_HEIGHT_M = 0.975


def _run_probe(*, device: str, num_envs_note: str) -> dict:
    """Boot a door-only scene and return every measured quantity."""
    import torch

    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.utils import configclass
    from pxr import UsdPhysics
    import isaacsim.core.utils.prims as prim_utils

    from gr00t.rl.data.tasks.door.scenario_cfg.isaacsim import TaskObjCfgDict
    from gr00t.rl.isaac_utils.playground.env_rand.door import DoorSpawnerCfg

    base_door_cfg = TaskObjCfgDict["door"]
    base_spawn = base_door_cfg.spawn
    base_asset = base_spawn.assets_cfg[0]
    if not isinstance(base_asset, DoorSpawnerCfg):
        raise TypeError("P0-D requires a DoorSpawnerCfg base asset")

    variants = [
        base_asset.replace(
            rand_door_handle_height=DOOR_HANDLE_HEIGHT_M,
            rand_door_weight=DOOR_MASS_KG,
            rand_hinge_drive_max_force=float(row["max_force_nm"]),
            rand_hinge_drive_damping=float(row["damping"]),
            rand_hinge_drive_stiffness=float(row["stiffness"]),
            randomize_material=False,
            use_preloaded_materials=False,
            activate_contact_sensors=False,
        )
        for row in PROBE_TUPLES
    ]
    door_cfg = base_door_cfg.replace(
        spawn=base_spawn.replace(
            assets_cfg=variants, random_choice=False, activate_contact_sensors=False
        )
    )

    @configclass
    class HingeProbeSceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane", spawn=sim_utils.GroundPlaneCfg()
        )
        dome_light = AssetBaseCfg(
            prim_path="/World/DomeLight", spawn=sim_utils.DomeLightCfg(intensity=1500.0)
        )
        door: ArticulationCfg = door_cfg.replace(prim_path="{ENV_REGEX_NS}/door")

    scene_cfg = HingeProbeSceneCfg(
        num_envs=len(PROBE_TUPLES), env_spacing=6.0, replicate_physics=False
    )
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=SIM_DT, device=device))
    scene = InteractiveScene(scene_cfg)
    sim.reset()

    door: Articulation = scene["door"]
    hinge_ids, hinge_names = door.find_joints([".*hinge.*"], preserve_order=True)
    if len(hinge_ids) != 1:
        raise RuntimeError(f"P0-D requires exactly one hinge joint; got {hinge_names!r}")
    hinge_id = hinge_ids[0]

    # §6.0 — read the actual spawned USD drive attributes before any probe.
    stage = prim_utils.get_current_stage()
    runtime_rows = []
    for env_index, row in enumerate(PROBE_TUPLES):
        matches = [
            prim
            for prim in stage.Traverse()
            if prim.GetPath().pathString.startswith(f"/World/envs/env_{env_index}/door")
            and "hinge" in prim.GetName()
            and UsdPhysics.DriveAPI.CanApply(prim, "angular")
            and prim.HasAPI(UsdPhysics.DriveAPI, "angular")
        ]
        if len(matches) != 1:
            paths = [prim.GetPath().pathString for prim in matches]
            raise RuntimeError(
                f"P0-D expected exactly one angular-driven hinge prim in env {env_index}; got {paths!r}"
            )
        drive = UsdPhysics.DriveAPI(matches[0], "angular")
        runtime_rows.append(
            {
                "tuple_id": row["tuple_id"],
                "env_index": env_index,
                "prim_path": matches[0].GetPath().pathString,
                "requested_damping": float(row["damping"]),
                "requested_stiffness": float(row["stiffness"]),
                "requested_max_force_nm": float(row["max_force_nm"]),
                "runtime_damping": float(drive.GetDampingAttr().Get()),
                "runtime_stiffness": float(drive.GetStiffnessAttr().Get()),
                "runtime_max_force": float(drive.GetMaxForceAttr().Get()),
                "runtime_target_position": float(drive.GetTargetPositionAttr().Get()),
            }
        )

    # §2.3 unit convention: record what IsaacLab actually hands the implicit
    # actuator next to what was written into USD.  The plan requires the exact
    # units and angular convention to be published, not assumed.
    articulation_gains = {
        "tuple_id": PROBE_TUPLES[0]["tuple_id"],
        "usd_stiffness": float(PROBE_TUPLES[0]["stiffness"]),
        "usd_damping": float(PROBE_TUPLES[0]["damping"]),
        "usd_max_force_nm": float(PROBE_TUPLES[0]["max_force_nm"]),
        "sim_stiffness": float(door.data.joint_stiffness[0, hinge_id].item()),
        "sim_damping": float(door.data.joint_damping[0, hinge_id].item()),
        "sim_effort_limit_nm": float(door.data.joint_effort_limits[0, hinge_id].item()),
        "joint_names": list(door.joint_names),
        "body_names": list(door.body_names),
    }

    def _reset_hinge(position_rad: float) -> None:
        joint_pos = door.data.default_joint_pos.clone()
        joint_vel = torch.zeros_like(door.data.default_joint_vel)
        joint_pos[:, hinge_id] = position_rad
        door.write_joint_state_to_sim(joint_pos, joint_vel)
        door.set_joint_effort_target(torch.zeros_like(joint_pos))
        scene.write_data_to_sim()
        sim.step()
        scene.update(SIM_DT)

    # §6.1 — free return from a fixed angle with zero angular velocity.
    # Accumulate on device and transfer once; a per-step .item() loop would make
    # this probe an order of magnitude slower without adding any evidence.
    _reset_hinge(FREE_RETURN_START_RAD)
    steps = int(FREE_RETURN_MAX_SECONDS / SIM_DT)
    n_env = len(PROBE_TUPLES)
    max_force = torch.tensor(
        [float(row["max_force_nm"]) for row in PROBE_TUPLES], device=door.device
    )
    marks = torch.tensor(FREE_RETURN_MARKS_RAD, device=door.device)
    mark_step = torch.full((n_env, len(FREE_RETURN_MARKS_RAD)), -1, dtype=torch.long, device=door.device)
    peak_closing = torch.zeros(n_env, device=door.device)
    closing_impulse = torch.zeros(n_env, device=door.device)
    applied_min = torch.full((n_env,), float("inf"), device=door.device)
    applied_max = torch.full((n_env,), float("-inf"), device=door.device)
    capped_steps = torch.zeros(n_env, device=door.device)
    trajectory = [[] for _ in range(n_env)]
    zero_effort = torch.zeros_like(door.data.joint_pos)
    for step in range(steps):
        door.set_joint_effort_target(zero_effort)
        scene.write_data_to_sim()
        sim.step()
        scene.update(SIM_DT)
        position = door.data.joint_pos[:, hinge_id]
        velocity = door.data.joint_vel[:, hinge_id]
        applied = door.data.applied_torque[:, hinge_id]
        reached = position[:, None] <= marks[None, :]
        mark_step = torch.where((mark_step < 0) & reached, torch.full_like(mark_step, step + 1), mark_step)
        closing = torch.clamp(-velocity, min=0.0)
        peak_closing = torch.maximum(peak_closing, closing)
        closing_impulse = closing_impulse + closing * SIM_DT
        applied_min = torch.minimum(applied_min, applied)
        applied_max = torch.maximum(applied_max, applied)
        capped_steps = capped_steps + (applied.abs() >= 0.995 * max_force).float()
        if step % 40 == 0:
            elapsed = round((step + 1) * SIM_DT, 4)
            pos_list = position.detach().cpu().tolist()
            vel_list = velocity.detach().cpu().tolist()
            for env_index in range(n_env):
                trajectory[env_index].append(
                    [elapsed, round(pos_list[env_index], 6), round(vel_list[env_index], 6)]
                )

    mark_step_list = mark_step.detach().cpu().tolist()
    peak_list = peak_closing.detach().cpu().tolist()
    impulse_list = closing_impulse.detach().cpu().tolist()
    min_list = applied_min.detach().cpu().tolist()
    max_list = applied_max.detach().cpu().tolist()
    capped_list = capped_steps.detach().cpu().tolist()
    final_position = door.data.joint_pos[:, hinge_id].detach().cpu().tolist()
    free_return_rows = []
    for env_index, row in enumerate(PROBE_TUPLES):
        times = [
            None if mark_step_list[env_index][i] < 0 else mark_step_list[env_index][i] * SIM_DT
            for i in range(len(FREE_RETURN_MARKS_RAD))
        ]
        free_return_rows.append(
            {
                "tuple_id": row["tuple_id"],
                "start_rad": FREE_RETURN_START_RAD,
                "time_to_0p90_s": times[0],
                "time_to_0p60_s": times[1],
                "time_to_0p30_s": times[2],
                "peak_closing_velocity_radps": peak_list[env_index],
                "closing_impulse_proxy_rad": impulse_list[env_index],
                "drive_torque_min_nm": min_list[env_index],
                "drive_torque_max_nm": max_list[env_index],
                "force_capped_step_fraction": capped_list[env_index] / steps,
                "final_position_rad": final_position[env_index],
                "trajectory_samples_t_pos_vel": trajectory[env_index],
            }
        )

    # §6.2 — fixed EXTERNAL opening torque probe.
    #
    # The torque must be external to the drive.  A joint effort target is summed
    # with the restoring drive torque and then clipped by the same maxForce cap,
    # so a spring-loaded door never opens and every torque reads identically.
    # The registered doors are right-hinged, which flips the hinge frame relative
    # to world +Z, so the opening sign is measured rather than assumed: both world
    # torque signs are applied and the opening direction is recorded.
    panel_ids, panel_names = door.find_bodies(["door_panel"], preserve_order=True)
    if len(panel_ids) != 1:
        raise RuntimeError(f"P0-D requires exactly one door_panel body; got {panel_names!r}")
    fixed_torque_rows = []
    torque_steps = int(FIXED_TORQUE_SECONDS / SIM_DT)
    for torque in FIXED_TORQUES_NM:
        for sign, sign_label in ((1.0, "world_plus_z"), (-1.0, "world_minus_z")):
            _reset_hinge(0.0)
            forces = torch.zeros(door.num_instances, 1, 3, device=door.device)
            torques = torch.zeros(door.num_instances, 1, 3, device=door.device)
            torques[:, 0, 2] = sign * torque
            door.set_external_force_and_torque(
                forces, torques, body_ids=panel_ids, is_global=True
            )
            capped = torch.zeros(n_env, device=door.device)
            peak_velocity = torch.zeros(n_env, device=door.device)
            max_progress = torch.zeros(n_env, device=door.device)
            for _ in range(torque_steps):
                door.set_joint_effort_target(zero_effort)
                scene.write_data_to_sim()
                sim.step()
                scene.update(SIM_DT)
                applied = door.data.applied_torque[:, hinge_id]
                capped = capped + (applied.abs() >= 0.995 * max_force).float()
                peak_velocity = torch.maximum(peak_velocity, door.data.joint_vel[:, hinge_id])
                max_progress = torch.maximum(max_progress, door.data.joint_pos[:, hinge_id])
            position = door.data.joint_pos[:, hinge_id].detach().cpu().tolist()
            velocity = door.data.joint_vel[:, hinge_id].detach().cpu().tolist()
            peak_list = peak_velocity.detach().cpu().tolist()
            capped_list = capped.detach().cpu().tolist()
            progress_list = max_progress.detach().cpu().tolist()
            for env_index, row in enumerate(PROBE_TUPLES):
                fixed_torque_rows.append(
                    {
                        "tuple_id": row["tuple_id"],
                        "applied_torque_nm": torque,
                        "world_torque_sign": sign_label,
                        "progress_rad": position[env_index],
                        "max_progress_rad": progress_list[env_index],
                        "steady_velocity_radps": velocity[env_index],
                        "peak_velocity_radps": peak_list[env_index],
                        "drive_cap_step_fraction": capped_list[env_index] / torque_steps,
                    }
                )
    door.set_external_force_and_torque(
        torch.zeros(door.num_instances, 1, 3, device=door.device),
        torch.zeros(door.num_instances, 1, 3, device=door.device),
        body_ids=panel_ids,
        is_global=True,
    )

    sim.clear_all_callbacks()
    return {
        "runtime_baseline_rows": runtime_rows,
        "articulation_hinge_gains": articulation_gains,
        "free_return_rows": free_return_rows,
        "fixed_torque_rows": fixed_torque_rows,
        "sim_dt_s": SIM_DT,
        "door_mass_kg": DOOR_MASS_KG,
        "door_handle_height_m": DOOR_HANDLE_HEIGHT_M,
        "num_envs_note": num_envs_note,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, default=0, help="physical GPU, 0 or 1 only")
    parser.add_argument("--out-root", type=Path, default=None)
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="re-adjudicate the saved raw measurements without booting a simulator",
    )
    args = parser.parse_args(argv)

    from scriptsFORhuman.v22._v22_common import (
        REPO_ROOT,
        V22_LOCK_ROOT,
        artifact_payload,
        read_json,
        require_gpu,
        write_json,
    )

    repo_root = Path(args.out_root) if args.out_root is not None else REPO_ROOT
    source_lock = read_json(repo_root / V22_LOCK_ROOT / "V22_SOURCE_LOCK.json")
    raw_path = repo_root / "logs_eval/base_v22/p0d/V22_HINGE_RAW_MEASUREMENTS.json"

    from scriptsFORhuman.v22.hinge_range_freeze import (
        build_dynamics_probe,
        build_range_freeze,
        build_runtime_baseline,
    )

    def _publish(measured):
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        lock_root = repo_root / V22_LOCK_ROOT
        baseline = build_runtime_baseline(measured, source_lock=source_lock, timestamp_utc=stamp)
        probe = build_dynamics_probe(measured, source_lock=source_lock, timestamp_utc=stamp)
        freeze = build_range_freeze(probe, source_lock=source_lock, timestamp_utc=stamp)
        for name, payload in (
            ("V22_HINGE_RUNTIME_BASELINE.json", baseline),
            ("V22_HINGE_DYNAMICS_PROBE.json", probe),
            ("V22_HINGE_RANGE_FREEZE.json", freeze),
        ):
            target = lock_root / name
            write_json(target, payload)
            print(f"P0-D wrote {target}", flush=True)

    if args.reuse:
        _publish(read_json(raw_path))
        return 0

    gpu = require_gpu(args.gpu)
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher({"headless": True, "device": f"cuda:{gpu}", "enable_cameras": False})
    simulation_app = app_launcher.app
    try:
        measured = _run_probe(device=f"cuda:{gpu}", num_envs_note=f"{len(PROBE_TUPLES)} probe tuples")
        write_json(raw_path, measured)
        _publish(measured)
    finally:
        simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
