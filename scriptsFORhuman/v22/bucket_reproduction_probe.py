"""Measure whether the frozen H0/H1/H2 marginal ranges reproduce their response classes.

The probe uses the production v22 bucket-mixture selector, spawns a balanced
16-row sample from each realized bucket, and classifies every sampled door from
free-return and fixed external-torque response.  The intended bucket name is
kept separate from both runtime-value registration and measured response.

Output:
    logs_eval/base_v22/locks/V22_BUCKET_REPRODUCTION.json
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


SAMPLES_PER_BUCKET = 16
PROBE_SEED = 20260808
SIM_DT = 0.005
FREE_RETURN_START_RAD = 1.20
FREE_RETURN_HALF_RAD = 0.60
FREE_RETURN_MAX_SECONDS = 12.0
FIXED_TORQUE_NM = 20.0
FIXED_TORQUE_SECONDS = 3.0
EXPECTED_CLASS = {"H0": "CORE", "H1": "HIGH_DAMPING", "H2": "FAST_REBOUND"}


def _bucket_rows(freeze: dict) -> list[dict]:
    rows = []
    for entry in freeze["buckets"]:
        name = entry["bucket"]
        if name not in EXPECTED_CLASS:
            continue
        rows.append(
            {
                "bucket": name,
                "weight": 1.0,
                "damping": list(entry["damping"]),
                "stiffness": list(entry["stiffness"]),
                "max_force_nm": list(entry["max_force_nm"]),
                "mass_kg": list(entry["mass_kg"]),
                "handle_height_m": list(entry["handle_height_m"]),
            }
        )
    if [row["bucket"] for row in rows] != ["H0", "H1", "H2"]:
        raise RuntimeError("P0 bucket reproduction requires the frozen H0/H1/H2 table")
    return rows


def _run_probe(*, device: str, freeze: dict, dynamics: dict) -> dict:
    import torch

    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.utils import configclass

    from gr00t.rl.data.tasks.door.scenario_cfg.isaacsim import (
        get_TaskObjCfgDict_for_v22_hinge_bucket_mixture,
    )
    from gr00t.rl.envs.door.a2_v22_evidence import (
        V22_HINGE_BUCKETS,
        v22_bucket_index_from_runtime,
        v22_classify_free_return,
    )

    mixture = _bucket_rows(freeze)
    num_envs = len(mixture) * SAMPLES_PER_BUCKET
    env_config = {
        "a2_v22_hinge_bucket_mixture": mixture,
        "a2_v22_hinge_bucket_seed": PROBE_SEED,
    }
    task_cfg = get_TaskObjCfgDict_for_v22_hinge_bucket_mixture(num_envs, env_config)
    spawn_cfg = task_cfg["door"].spawn
    variants = []
    intended_bucket = []
    for asset in spawn_cfg.assets_cfg:
        matches = [
            row["bucket"]
            for row in mixture
            if tuple(float(x) for x in asset.hinge_drive_damping_range)
            == tuple(float(x) for x in row["damping"])
            and tuple(float(x) for x in asset.hinge_drive_stiffness_range)
            == tuple(float(x) for x in row["stiffness"])
            and tuple(float(x) for x in asset.hinge_drive_max_force_range)
            == tuple(float(x) for x in row["max_force_nm"])
        ]
        if len(matches) != 1:
            raise RuntimeError(f"cannot recover one intended bucket from production variant: {matches!r}")
        intended_bucket.append(matches[0])
        variants.append(
            asset.replace(
                randomize_material=False,
                use_preloaded_materials=False,
                activate_contact_sensors=False,
            )
        )
    if Counter(intended_bucket) != Counter({name: SAMPLES_PER_BUCKET for name in EXPECTED_CLASS}):
        raise RuntimeError(f"production selector did not make the balanced probe allocation: {Counter(intended_bucket)!r}")
    task_cfg = dict(task_cfg)
    task_cfg["door"] = task_cfg["door"].replace(
        spawn=spawn_cfg.replace(
            assets_cfg=variants,
            random_choice=False,
            activate_contact_sensors=False,
        )
    )

    @configclass
    class BucketProbeSceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane", spawn=sim_utils.GroundPlaneCfg()
        )
        dome_light = AssetBaseCfg(
            prim_path="/World/DomeLight", spawn=sim_utils.DomeLightCfg(intensity=1500.0)
        )
        door: ArticulationCfg = task_cfg["door"].replace(prim_path="{ENV_REGEX_NS}/door")

    np.random.seed(PROBE_SEED)
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=SIM_DT, device=device))
    scene = InteractiveScene(
        BucketProbeSceneCfg(num_envs=num_envs, env_spacing=6.0, replicate_physics=False)
    )
    sim.reset()

    door: Articulation = scene["door"]
    hinge_ids, hinge_names = door.find_joints([".*hinge.*"], preserve_order=True)
    if len(hinge_ids) != 1:
        raise RuntimeError(f"bucket reproduction requires exactly one hinge; got {hinge_names!r}")
    hinge_id = hinge_ids[0]
    panel_ids, panel_names = door.find_bodies(["door_panel"], preserve_order=True)
    if len(panel_ids) != 1:
        raise RuntimeError(f"bucket reproduction requires exactly one door_panel; got {panel_names!r}")

    # PhysX exposes angular drive gains per radian while the door metadata and
    # frozen v22 table use the native per-degree USD values.  P0-D measured the
    # exact 180/pi conversion; convert the high-level articulation tensors back
    # to the registered native convention before runtime bucket labelling.
    damping = door.data.joint_damping[:, hinge_id].clone() * (math.pi / 180.0)
    stiffness = door.data.joint_stiffness[:, hinge_id].clone() * (math.pi / 180.0)
    max_force = door.data.joint_effort_limits[:, hinge_id].clone()
    if not torch.all(torch.isfinite(torch.stack((damping, stiffness, max_force)))):
        raise RuntimeError("bucket reproduction spawned non-finite hinge parameters")

    bucket_table = [
        {
            "bucket": row["bucket"],
            "damping": row["damping"],
            "stiffness": row["stiffness"],
            "max_force_nm": row["max_force_nm"],
        }
        for row in mixture
    ]
    runtime_bucket_index = v22_bucket_index_from_runtime(
        damping, stiffness, max_force, bucket_table
    )

    def reset_hinge(position_rad: float) -> None:
        joint_pos = door.data.default_joint_pos.clone()
        joint_vel = torch.zeros_like(door.data.default_joint_vel)
        joint_pos[:, hinge_id] = position_rad
        door.write_joint_state_to_sim(joint_pos, joint_vel)
        door.set_joint_effort_target(torch.zeros_like(joint_pos))
        scene.write_data_to_sim()
        sim.step()
        scene.update(SIM_DT)

    reset_hinge(FREE_RETURN_START_RAD)
    free_steps = int(FREE_RETURN_MAX_SECONDS / SIM_DT)
    half_step = torch.full((num_envs,), -1, dtype=torch.long, device=door.device)
    peak_closing = torch.zeros(num_envs, device=door.device)
    capped_steps = torch.zeros(num_envs, device=door.device)
    zero_effort = torch.zeros_like(door.data.joint_pos)
    for step in range(free_steps):
        door.set_joint_effort_target(zero_effort)
        scene.write_data_to_sim()
        sim.step()
        scene.update(SIM_DT)
        position = door.data.joint_pos[:, hinge_id]
        velocity = door.data.joint_vel[:, hinge_id]
        applied = door.data.applied_torque[:, hinge_id]
        reached = position <= FREE_RETURN_HALF_RAD
        half_step = torch.where(
            (half_step < 0) & reached,
            torch.full_like(half_step, step + 1),
            half_step,
        )
        peak_closing = torch.maximum(peak_closing, torch.clamp(-velocity, min=0.0))
        capped_steps += (applied.abs() >= 0.995 * max_force).float()

    torque_steps = int(FIXED_TORQUE_SECONDS / SIM_DT)
    sign_progress = []
    for sign in (1.0, -1.0):
        reset_hinge(0.0)
        forces = torch.zeros(num_envs, 1, 3, device=door.device)
        torques = torch.zeros(num_envs, 1, 3, device=door.device)
        torques[:, 0, 2] = sign * FIXED_TORQUE_NM
        door.set_external_force_and_torque(
            forces, torques, body_ids=panel_ids, is_global=True
        )
        max_progress = torch.zeros(num_envs, device=door.device)
        for _ in range(torque_steps):
            door.set_joint_effort_target(zero_effort)
            scene.write_data_to_sim()
            sim.step()
            scene.update(SIM_DT)
            max_progress = torch.maximum(max_progress, door.data.joint_pos[:, hinge_id])
        sign_progress.append(max_progress)
    door.set_external_force_and_torque(
        torch.zeros(num_envs, 1, 3, device=door.device),
        torch.zeros(num_envs, 1, 3, device=door.device),
        body_ids=panel_ids,
        is_global=True,
    )

    half_step_cpu = half_step.cpu().tolist()
    peak_cpu = peak_closing.cpu().tolist()
    capped_cpu = capped_steps.cpu().tolist()
    damping_cpu = damping.cpu().tolist()
    stiffness_cpu = stiffness.cpu().tolist()
    max_force_cpu = max_force.cpu().tolist()
    runtime_bucket_cpu = runtime_bucket_index.cpu().tolist()
    plus_cpu = sign_progress[0].cpu().tolist()
    minus_cpu = sign_progress[1].cpu().tolist()
    samples = []
    for env_id in range(num_envs):
        half_time = (
            None if half_step_cpu[env_id] < 0 else half_step_cpu[env_id] * SIM_DT
        )
        effective_half_time = half_time if half_time is not None else SIM_DT * 1.0e6
        progress = max(plus_cpu[env_id], minus_cpu[env_id])
        response = v22_classify_free_return(
            half_time_s=effective_half_time,
            peak_closing_velocity_radps=peak_cpu[env_id],
            stayed_force_capped=capped_cpu[env_id] / free_steps > 0.5,
            fixed_torque_progress_rad={str(FIXED_TORQUE_NM): progress},
            core_half_time_s=float(dynamics["core_half_time_s"]),
            core_peak_closing_velocity_radps=float(
                dynamics["core_peak_closing_velocity_radps"]
            ),
            core_progress_rad=float(dynamics["core_progress_rad"]),
        )
        registered_index = runtime_bucket_cpu[env_id]
        samples.append(
            {
                "env_id": env_id,
                "intended_bucket": intended_bucket[env_id],
                "runtime_registered_bucket": (
                    None if registered_index < 0 else V22_HINGE_BUCKETS[registered_index]
                ),
                "runtime_damping": damping_cpu[env_id],
                "runtime_stiffness": stiffness_cpu[env_id],
                "runtime_max_force_nm": max_force_cpu[env_id],
                "time_to_0p60_s": half_time,
                "peak_closing_velocity_radps": peak_cpu[env_id],
                "force_capped_step_fraction": capped_cpu[env_id] / free_steps,
                "fixed_torque_progress_rad": progress,
                "measured_response_class": response,
                "expected_response_class": EXPECTED_CLASS[intended_bucket[env_id]],
                "response_reproduced": response == EXPECTED_CLASS[intended_bucket[env_id]],
            }
        )

    by_bucket = {}
    for name in EXPECTED_CLASS:
        bucket_samples = [row for row in samples if row["intended_bucket"] == name]
        response_counts = Counter(row["measured_response_class"] for row in bucket_samples)
        registered_counts = Counter(
            str(row["runtime_registered_bucket"]) for row in bucket_samples
        )
        by_bucket[name] = {
            "expected_response_class": EXPECTED_CLASS[name],
            "sample_count": len(bucket_samples),
            "response_counts": dict(sorted(response_counts.items())),
            "runtime_registration_counts": dict(sorted(registered_counts.items())),
            "all_runtime_registered_as_intended": all(
                row["runtime_registered_bucket"] == name for row in bucket_samples
            ),
            "all_responses_reproduced": all(row["response_reproduced"] for row in bucket_samples),
        }
    status = (
        "BUCKET_REPRODUCTION_PASS"
        if all(
            row["all_runtime_registered_as_intended"] and row["all_responses_reproduced"]
            for row in by_bucket.values()
        )
        else "BUCKET_REPRODUCTION_MISMATCH"
    )
    sim.clear_all_callbacks()
    return {
        "schema": "a2_piper_base_v22_bucket_reproduction_v1",
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "probe_design": {
            "selector": "production_v22_hinge_bucket_mixture",
            "samples_per_realized_bucket": SAMPLES_PER_BUCKET,
            "balanced_probe_not_training_weighted": True,
            "seed": PROBE_SEED,
            "free_return_start_rad": FREE_RETURN_START_RAD,
            "fixed_external_torque_nm": FIXED_TORQUE_NM,
        },
        "classification_reference": {
            "core_half_time_s": dynamics["core_half_time_s"],
            "core_peak_closing_velocity_radps": dynamics[
                "core_peak_closing_velocity_radps"
            ],
            "core_progress_rad": dynamics["core_progress_rad"],
        },
        "by_bucket": by_bucket,
        "samples": samples,
        "interpretation": (
            "PASS requires every runtime tuple to retain its intended bucket registration and "
            "every independently sampled tuple to reproduce the frozen bucket's measured response class."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, default=0)
    args = parser.parse_args(argv)

    from scriptsFORhuman.v22._v22_common import (
        REPO_ROOT,
        V22_LOCK_ROOT,
        read_json,
        require_gpu,
        write_json,
    )

    lock_root = REPO_ROOT / V22_LOCK_ROOT
    freeze = read_json(lock_root / "V22_HINGE_RANGE_FREEZE.json")
    dynamics = read_json(lock_root / "V22_HINGE_DYNAMICS_PROBE.json")
    gpu = require_gpu(args.gpu)

    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(
        {"headless": True, "device": f"cuda:{gpu}", "enable_cameras": False}
    )
    simulation_app = app_launcher.app
    try:
        payload = _run_probe(device=f"cuda:{gpu}", freeze=freeze, dynamics=dynamics)
        target = lock_root / "V22_BUCKET_REPRODUCTION.json"
        write_json(target, payload)
        print(f"WROTE {target} status={payload['status']}", flush=True)
        return 0 if payload["status"] == "BUCKET_REPRODUCTION_PASS" else 2
    finally:
        simulation_app.close()


if __name__ == "__main__":
    raise SystemExit(main())
