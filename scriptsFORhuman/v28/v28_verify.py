"""Resolve the G0 scratch recipe and compare with the frozen v27 SC control."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUNTIME = HERE / "runtime_logs/v28_camera_aware_rebaseline_20260909"
PYTHON = "/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
WORKFLOW_KEYS = {
    "timestamp", "experiment_dir", "save_dir", "output_dir",
    "callbacks.model_save.save_dir", "callbacks.autoresume.save_dir", "wandb.wandb_dir",
}


def flatten(value, prefix=""):
    result = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(flatten(item, name))
        else:
            result[name] = item
    return result


K_REWARD_NAMES = [
    "walk_to_door", "gripper_handle_orientation", "pregrasp_gripper_dof_pos_l1",
    "pregrasp_target_distance", "grasp_target_distance", "grasp", "a2_stage2_close_command",
    "a2_stage2_close_progress", "a2_stage2_handle_center_y", "a2_stage2_handle_approach_xz",
    "a2_stage2_both_contact", "a2_stage2_opposite_squeeze", "a2_stage2_squeeze_force_window",
    "a2_stage2_contact_stability", "a2_stage3_handle_creation", "a2_stage3_unlatch_hold",
    "penalty_a2_wrist_motion_l2",
]


def expected_changes(seed):
    changes = {
        "seed": seed, "v26_cell": f"V28_A_S{seed}",
        "v26_schema": "a2_piper_base_v28_camera_aware_rebaseline_v1",
        "v26_plan_id": "base_v28_camera_aware_rebaseline_20260909",
        "v26_phase": "V28_CAMERA_AWARE_REBASELINE",
        "project_name": "base_v28_camera_aware_rebaseline",
        "experiment_name": f"V28_A_S{seed}",
        "env.config.experiment_name": f"V28_A_S{seed}",
        "env.config.a2_v26_side_permutation_seed": seed,
        "env.config.a2_v26_8_penalty_driver": "side_min_natural_stage_reach_rate",
        "env.config.a2_v26_8_penalty_driver_target_stage": 5 if seed == 284 else 4,
        "env.config.a2_v26_8_penalty_driver_level_down_rate": 0.5,
        "env.config.a2_v26_8_penalty_driver_level_up_rate": 0.7,
        "env.config.a2_v26_8_penalty_curriculum_trace_enabled": True,
        "env.config.delta_action_clamp_to_dof_limits": True,
        "env.config.a2_v28_camera_telemetry_enabled": True,
        "env.config.a2_stage4_arm_default_pose_release_gated": True,
        "env.config.a2_wrist_motion_vel_weights": [
            [.35]*3, [.5]*3, [.75]*3, [.5,.5,0.], [1.]*3, [1.25]*3,
        ],
        "env.config.a2_wrist_motion_reversal_weights": [
            [.5]*3, [.5]*3, [.5]*3, [.5,.5,.25], [.5]*3, [.5]*3,
        ],
        "rewards.reward_penalty_curriculum": True,
        "rewards.reward_initial_penalty_scale": 1.0,
        "rewards.reward_min_penalty_scale": 0.2,
        "rewards.reward_max_penalty_scale": 1.0,
        "rewards.reward_penalty_degree": -0.0001,
        "rewards.reward_penalty_level_down_ave_goal_reached_rate": None,
        "rewards.reward_penalty_level_up_ave_goal_reached_rate": None,
        "rewards.reward_penalty_reward_names": K_REWARD_NAMES,
    }
    for prefix in ("robot", "env.config.robot"):
        changes[f"{prefix}.num_bodies"] = 28
        for extension in ("urdf", "usd"):
            changes[f"{prefix}.asset.{extension}_file"] = (
                f"a2_piper_v28_merged_20260909/a2_piper.{extension}"
            )
        for joint, angle in ((2,.10),(3,-.10),(4,0.),(5,-.415)):
            changes[f"{prefix}.init_state.default_joint_angles.arm_j{joint}"] = angle
    for prefix in ("rewards", "env.config.rewards"):
        for name, scale in (("wrist_motion_l2",-.4), ("wrist_tower_contact",-1.),
                            ("stage4_arm_default_pose_l1",-.5)):
            changes[f"{prefix}.reward_scales.penalty_a2_{name}"] = scale
    for key, value in list(changes.items()):
        if key.startswith("rewards."):
            changes[f"env.config.{key}"] = value
    return changes


def resolve(seed, output_root):
    baseline_path = ROOT / (
        "scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/wave_c_contract.json"
    )
    baseline = json.loads(baseline_path.read_text())["cells"]["SC_S201"]["resolved_contract"]
    output = output_root / "compose" / f"A_S{seed}"
    output.mkdir(parents=True, exist_ok=False)
    command = [PYTHON, "-B", "-m", "gr00t.rl.train_agent_trl",
               "+exp=wbmanip/door_open_a2_base_lstm",
               f"+ablation=wbmanip/base_v28_A_S{seed}",
               "project_name=base_v28_camera_aware_rebaseline",
               f"experiment_name=V28_A_S{seed}", "--cfg", "job", "--resolve"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    (output / "resolved_config.yaml").write_text(result.stdout)
    current = {k:v for k,v in flatten(yaml.safe_load(result.stdout)).items() if k not in WORKFLOW_KEYS}
    expected = expected_changes(seed)
    for prefix in ("robot", "env.config.robot"):
        expected[f"{prefix}.body_names"] = baseline[f"{prefix}.body_names"] + ["wrist_camera_tower"]
    expected = {key: value for key, value in expected.items()
                if key not in baseline or baseline[key] != value}
    changed = {k:current[k] for k in current.keys() | baseline.keys()
               if k not in baseline or k not in current or current[k] != baseline[k]}
    if changed != expected:
        raise ValueError(f"Unregistered compose difference: {changed.keys() ^ expected.keys()}; "
                         f"wrong values: {[k for k in changed.keys() & expected.keys() if changed[k] != expected[k]]}")
    receipt = {"status":"STATIC_PASS", "baseline":str(baseline_path), "command":command,
               "cell":f"A_S{seed}", "changes":changed, "resolved_contract":current,
               "evidence_scope":"CPU compose only; asset and runtime gates remain separate"}
    (output / "compose_receipt.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(f"A_S{seed}: STATIC_PASS ({len(changed)} registered differences)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["resolve"])
    parser.add_argument("--seed", type=int, choices=[281,282,283,284], default=281)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    resolve(args.seed, args.output_root)
