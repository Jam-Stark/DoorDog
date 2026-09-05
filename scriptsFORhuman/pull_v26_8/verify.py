#!/usr/bin/env python3
"""Validate the pull backbone against its source-resolved migration contract."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import yaml
from omegaconf import OmegaConf

from gr00t.rl.utils.config_utils import register_rl_resolvers

register_rl_resolvers()

ROOT = Path(__file__).resolve().parents[2]
ACTOR = "gr00t.rl.trl.modules.actor_critic_modules_recurrent.RecurrentActor"
CELLS = ("P_S0", "P_S1", "P_S2")
RATIOS = [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
ACTOR_OBS = [
    "dof_pos", "relative_to_door", "dof_vel", "actions", "projected_gravity",
    "door_dof_pos", "base_lin_vel", "base_ang_vel", "hand_force", "stage",
    "privileged_door_info", "delta_actions", "gripper_handle_transform",
    "a2_base_command_raw", "a2_base_command",
]
CRITIC_OBS = ACTOR_OBS[:-1] + [
    "transition", "complete", "time_in_stage", "actual_time_in_stage",
    "total_time", "a2_base_command",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"PULL_V26_8_INVALID: {message}")


def read_config(path: Path):
    # Current evaluator YAML includes pathlib objects and retains references
    # to the root observation config; resolve fields in their original root.
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.UnsafeLoader)
    return OmegaConf.create(value, flags={"allow_objects": True})


def validate_config(cfg: dict, cell: str, *, eval_side=None, smoke=False) -> dict:
    require(cell in CELLS, f"unknown cell {cell}")
    seed = int(cell[-1])
    env, actor = cfg["env"]["config"], cfg["algo"]["config"]["actor"]
    require(actor["_target_"] == ACTOR, "plain RecurrentActor required")
    require(actor["running_mean_std"] is True, "native updating actor RMS required")
    require("freeze_running_mean_std" not in actor, "unsupported plain-actor constructor argument")
    require(set(actor) == {"_target_", "running_mean_std", "rnn_type", "rnn_hidden_dim", "rnn_num_layers", "backbone"}, "actor constructor differs from plain backbone")
    require((actor["rnn_type"], actor["rnn_hidden_dim"], actor["rnn_num_layers"]) == ("lstm", 256, 2), "LSTM architecture")
    require(actor["backbone"]["module_config_dict"]["layer_config"]["hidden_dims"] == [512, 256, 128], "MLP architecture")
    obs = env["obs"]
    require(obs["obs_dict"]["actor_obs"] == ACTOR_OBS, "actor observation list")
    require(obs["obs_dict"]["critic_obs"] == CRITIC_OBS, "critic observation list")
    # pre_process_config converts the declared list to a mapping at runtime.
    declared_dims = obs["obs_dims"]
    dims = declared_dims if isinstance(declared_dims, Mapping) else {key: value for item in declared_dims for key, value in item.items()}
    dimensions = {group: sum(dims[key.removesuffix("_raw")] for key in obs["obs_dict"][group]) for group in ("actor_obs", "critic_obs")}
    # Both current pull and mainline cb15678 resolve this exact list to 133/138.
    require(dimensions == {"actor_obs": 133, "critic_obs": 138}, f"source-resolved observation dimensions {dimensions}")
    require(cfg.get("schedule_dict") in (None, {}), "scheduled reset curriculum must be absent")
    require(cfg["auto_load_latest"] is False, "auto_load_latest")
    expected_env = {
        "completion_stage": 5,
        "a2_pull_door_open_io": "in",
        "a2_stage2_squeeze_force_min": 0.5,
        "a2_stage2_squeeze_force_max": 30.0,
        "a2_stage2_over_force_threshold": 55.0,
        "a2_m39_gripper_material_enabled": True,
        "a2_pull_stage2_to3_gate_mode": "grasp_completion",
        "a2_pull_stage3_handle_income_mode": "live_proof",
        "a2_pull_stage3_hinge_income_mode": "live_proof",
        "a2_stage3_unlatch_near_closed_hinge_threshold": 0.25,
        "a2_pull_v6_stage4_bank_enabled": False,
        "a2_pull_v61_late_state_bank_enabled": False,
        "a2_pull_stage3_taskspace_action_enabled": False,
        "a2_pull_stage3_absolute_action_enabled": False,
        "a2_pull_h14_teacher_capture_enabled": False,
        "a2_pull_h18d_base_lateral_probe_enabled": False,
        "a2_pull_add_walls": False,
        "a2_pull_hook_profile": "ABSENT",
        "a2_pull_friction_profile": "RESOLVED_V20_G4",
        "a2_pull_finger_profile": "V20_G4_45N_KP1300_KD32",
    }
    for key, value in expected_env.items():
        require(env[key] == value, f"env.config.{key}={env[key]!r}, expected {value!r}")
    require(env["a2_pull_target_orientation_wxyz"] == [-0.5, -0.5, 0.5, 0.5], "authored pull orientation")
    require(env["a2_door_weight_range"] == [90.0, 90.0001], "door weight range")
    robot = cfg["robot"]
    require(robot["dof_effort_limit_list"][-2:] == [45.0, 45.0], "finger effort")
    for group, value in (("stiffness", 1300.0), ("damping", 32.0)):
        require(all(robot["control"][group][joint] == value for joint in ("arm_j7", "arm_j8")), f"finger {group}")
    require(cfg["simulator"]["config"]["sim"]["physx"]["num_velocity_iterations"] == 2, "PhysX velocity iterations")
    if eval_side is None:
        require(cfg["seed"] == seed and cfg["experiment_name"] == cell, "cell/seed identity")
        require(cfg["checkpoint"] is None and cfg["checkpoint_load_mode"] == "full", "scratch/full load")
        require(env["a2_door_open_lr_distribution"] == "bilateral", "bilateral training selector")
        require(env["a2_door_open_lr_permutation_seed"] == seed, "side permutation seed")
        require(env["a2_v26_6_side_mirrored_handle_offset_enabled"] is True, "mirror switch")
        require(env["enable_staged_reset"] is True and env["staged_reset_ratios"] == RATIOS, "fixed staged-reset ratios")
        batches = cfg["algo"]["trl"]["num_total_batches"]
        if smoke:
            require(cfg["num_envs"] in (64, 1024, 2048) and 1 <= batches <= 5, "smoke budget")
        else:
            require((cfg["num_envs"], batches) in ((2048, 4000), (1024, 6000)), "Wave1 budget")
            require(cfg["callbacks"]["model_save"]["save_frequency"] == 250, "checkpoint cadence")
    else:
        require(eval_side in ("left", "right", "bilateral"), "evaluation side")
        require(cfg["checkpoint"] is not None and cfg["checkpoint_load_mode"] in ("full", "policy_only"), "evaluation checkpoint")
        require(env["a2_door_open_lr_distribution"] == eval_side, "evaluation side selector")
        require(env["enable_staged_reset"] is False, "natural evaluation reset")
        require(cfg["num_envs"] == 64, "exact64 evaluation")
        evaluation = cfg["algo"]["config"]["eval"]
        require(evaluation["eval_num_envs_episodes"] is True, "first episode per environment")
        require(evaluation["a2_diagnostic_trace_enabled"] is True, "control-step trace")
        if not smoke:
            require(env["a2_v26_6_side_mirrored_handle_offset_enabled"] is True, "evaluation mirror switch")
    return {"status": "CONFIG_PASS", "cell": cell, "dimensions": dimensions,
            "freeze_running_mean_std": False, "rms_contract": "native RecurrentActor updates RMS",
            "gate": env["a2_pull_stage2_to3_gate_mode"], "near_closed_hinge_threshold": 0.25}


def source_lock(output: Path) -> dict:
    require(not output.exists(), f"source lock already exists: {output}")
    files = [ROOT / path for path in (
        "gr00t/rl/envs/door/door_open_a2_base.py",
        "gr00t/rl/envs/door/door_open_a2_pull.py",
        "gr00t/rl/envs/door/a2_pull_telemetry.py",
        "gr00t/rl/envs/door/a2_pull_v0_guard.py",
        "gr00t/rl/envs/door/a2_v26_6_handle_offset_mirror.py",
        "gr00t/rl/tests/test_a2_v26_6_handle_offset_mirror.py",
        "gr00t/rl/config/exp/wbmanip/door_open_a2_pull_v26_backbone_lstm.yaml",
        "scriptsFORhuman/pull_task/a2_piper_pull_v26_8_backbone_migration_plan_20260905.md",
    )]
    files += sorted((ROOT / "gr00t/rl/config/ablation/wbmanip").glob("pull_v26_8_backbone_*.yaml"))
    files += sorted(path for path in Path(__file__).parent.iterdir() if path.is_file() and path.suffix in (".py", ".sh", ".md"))
    snapshot = output.parent / "source_snapshot"
    snapshot.mkdir(parents=True, exist_ok=False)
    for path in files:
        dest = snapshot / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    payload = {
        "schema": "a2_piper_pull_v26_8_source_lock_v1", "status": "SOURCE_FROZEN",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        "files": [str(path.relative_to(ROOT)) for path in files],
        "snapshot": str(snapshot),
        "identity_method": "Git revision and exact source-file snapshots; no added digests per Owner instruction",
        "mainline_reference": "cb15678ef7f7f041fa8642215dd27bf75b163966",
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--cell", choices=CELLS)
    parser.add_argument("--eval-side", choices=("left", "right", "bilateral"))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.config:
        cfg = read_config(args.config)
        payload = validate_config(cfg, args.cell, eval_side=args.eval_side, smoke=args.smoke)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    else:
        if args.output is None:
            parser.error("--output is required for source lock")
        payload = source_lock(args.output)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
