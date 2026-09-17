"""Frozen v28 cell declarations and CPU configuration contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "scriptsFORhuman/v28"
RUN_ID = "v28_camera_aware_rebaseline_20260909"
RUNTIME = HERE / "runtime_logs" / RUN_ID
CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip"
ROBOT_CONFIG = ROOT / "gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml"
PLAN = HERE / "a2_piper_base_v28_plan_20260909.md"
PYTHON = "/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
SIDES = ("left", "right")
MILESTONES = (1000, 2000, 3000, 4000, 5000, 6000)
ORIGINAL_CELLS = ("A_S281", "A_S282", "A_S283")
METRICS = ("D", "S3+", "S4+", "open_hold", "S5+", "complete", "clean_complete")
EVAL_SEEDS = {"milestone": 280001, "DEV": 280101, "CONF": 280201, "render": 280303}
MERGED_ASSET = "a2_piper_v28_merged_20260909"
EXPECTED_POSTURE = {"arm_j1": 0.0, "arm_j2": 0.10, "arm_j3": -0.10, "arm_j4": 0.0, "arm_j5": -0.415, "arm_j6": 1.57}
K_REWARD_NAMES = (
    "walk_to_door", "gripper_handle_orientation", "pregrasp_gripper_dof_pos_l1",
    "pregrasp_target_distance", "grasp_target_distance", "grasp", "a2_stage2_close_command",
    "a2_stage2_close_progress", "a2_stage2_handle_center_y", "a2_stage2_handle_approach_xz",
    "a2_stage2_both_contact", "a2_stage2_opposite_squeeze", "a2_stage2_squeeze_force_window",
    "a2_stage2_contact_stability", "a2_stage3_handle_creation", "a2_stage3_unlatch_hold",
    "penalty_a2_wrist_motion_l2",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    require(not path.exists(), f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def cells() -> dict[str, dict[str, Any]]:
    scratch = {
        f"A_S{seed}": {
            "cell": f"A_S{seed}", "seed": seed, "checkpoint": None,
            "checkpoint_load_mode": "full", "policy_only_load_actor_rms": False,
            "batches": 6000, "milestones": (1000, 2000, 3000, 4000, 5000, 6000),
            "driver_target_stage": 5 if seed == 284 else 4,
        }
        for seed in (281, 282, 283, 284)
    }
    warm_checkpoint = str(ROOT / "logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/C_S2/model_step_003000.pt")
    return {
        "A_W281": {
            "cell": "A_W281", "seed": 281, "checkpoint": warm_checkpoint,
            "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True,
            "batches": 6000, "milestones": MILESTONES, "driver_target_stage": 4,
        },
        "G1_WARM": {
            "cell": "G1_WARM", "seed": 281,
            "checkpoint": str(ROOT / "logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/C_S2/model_step_003000.pt"),
            "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True,
            "batches": 500, "milestones": (250, 500), "driver_target_stage": 4,
        },
        **scratch,
    }


def cell_contract(cell: str) -> dict[str, Any]:
    try:
        return cells()[cell]
    except KeyError as error:
        raise ValueError(f"unknown v28 cell: {cell}") from error


def require_dot(mapping: dict[str, Any], dotted: str, expected: Any) -> None:
    value: Any = mapping
    for part in dotted.split("."):
        require(isinstance(value, dict) and part in value, f"missing config key {dotted}")
        value = value[part]
    require(value == expected, f"config {dotted}: {value!r} != {expected!r}")


def validate_robot_config() -> None:
    payload = yaml.safe_load(ROBOT_CONFIG.read_text(encoding="utf-8"))
    robot = payload["robot"]
    require(robot["num_bodies"] == 28, "robot.num_bodies")
    require(len(robot["body_names"]) == 28, "robot.body_names length")
    require(robot["body_names"][-1] == "wrist_camera_tower", "wrist_camera_tower body")
    require(len(robot["penalize_contacts_on"]) == 20, "penalize_contacts_on length")
    for extension in ("urdf", "usd"):
        require(robot["asset"][f"{extension}_file"] == f"{MERGED_ASSET}/a2_piper.{extension}", f"merged {extension}")
    posture = robot["init_state"]["default_joint_angles"]
    for name, value in EXPECTED_POSTURE.items():
        require(posture[name] == value, f"default posture {name}")
    names = robot["dof_names"]
    for name, value in EXPECTED_POSTURE.items():
        index = names.index(name)
        require(robot["dof_pos_lower_limit_list"][index] <= value <= robot["dof_pos_upper_limit_list"][index], f"default posture limit {name}")


def validate_common_config() -> None:
    payload = yaml.safe_load((CONFIG / "base_v28_common.yaml").read_text(encoding="utf-8"))
    env = payload["env"]["config"]
    rewards = payload["rewards"]
    expected_driver = {
        "a2_v26_8_penalty_driver": "side_min_natural_stage_reach_rate",
        "a2_v26_8_penalty_driver_target_stage": 4,
        "a2_v26_8_penalty_driver_level_down_rate": 0.5,
        "a2_v26_8_penalty_driver_level_up_rate": 0.7,
        "a2_v26_8_penalty_curriculum_trace_enabled": True,
    }
    for name, value in expected_driver.items():
        require(env[name] == value, f"K driver {name}")
    require(rewards["reward_penalty_curriculum"] is True, "K reward curriculum")
    require(tuple(rewards["reward_penalty_reward_names"]) == K_REWARD_NAMES, "K reward names")
    forbidden = {"penalty_a2_wrist_tower_contact", "penalty_a2_stage4_arm_default_pose_l1"}
    require(not forbidden.intersection(rewards["reward_penalty_reward_names"]), "K forbidden reward")


def validate_cpu_contract() -> None:
    validate_robot_config()
    validate_common_config()
    backup = yaml.safe_load((CONFIG / "base_v28_A_S284.yaml").read_text(encoding="utf-8"))
    require(backup["env"]["config"]["a2_v26_8_penalty_driver_target_stage"] == 5, "A_S284 target stage")
    warm = yaml.safe_load((CONFIG / "base_v28_G1_WARM.yaml").read_text(encoding="utf-8"))
    require(warm["checkpoint_load_mode"] == "policy_only", "G1 checkpoint mode")
    require(warm["policy_only_load_actor_rms"] is True, "G1 actor rms")
    require(warm["algo"]["trl"]["num_total_batches"] == 500, "G1 batch budget")
