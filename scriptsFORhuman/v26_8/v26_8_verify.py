#!/usr/bin/env python3
"""Static source/config lock for the frozen v26-8 operation path."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "gr00t/rl/config"
CELLS = {"C_S1": (2, 1, "SRC_S1"), "W_S1": (3, 1, "SRC_S1"), "K_S1": (4, 1, "SRC_S1"), "C_S2": (5, 2, "SRC_S2"), "W_S2": (6, 2, "SRC_S2"), "K_S2": (7, 2, "SRC_S2")}
SOURCES = {"SRC_S1": ("logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S1/model_step_003000.pt", "a683257213aaba82b583924d841235f772182f53113e513e16c8d27bcb394df1"), "SRC_S2": ("logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S2/model_step_003000.pt", "0b2f739f020b056adb2fb47105fdb5bc00d1d1189ef331d42332b3e0740e54ec")}
PENALTY_NAMES = ("walk_to_door", "gripper_handle_orientation", "pregrasp_gripper_dof_pos_l1", "pregrasp_target_distance", "grasp_target_distance", "grasp", "a2_stage2_close_command", "a2_stage2_close_progress", "a2_stage2_handle_center_y", "a2_stage2_handle_approach_xz", "a2_stage2_both_contact", "a2_stage2_opposite_squeeze", "a2_stage2_squeeze_force_window", "a2_stage2_contact_stability", "a2_stage3_handle_creation", "a2_stage3_unlatch_hold")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    out = dict(left)
    for key, value in right.items():
        out[key] = merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def compose(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"config is not mapping: {path}")
    out: dict[str, Any] = {}
    for default in value.get("defaults", []):
        if default == "_self_":
            continue
        if isinstance(default, str) and default.startswith("/"):
            target = CONFIG / f"{default[1:]}.yaml"
        elif isinstance(default, dict) and len(default) == 1:
            key, name = next(iter(default.items()))
            require(isinstance(key, str) and isinstance(name, str), f"unsupported default: {default!r}")
            target = CONFIG / f"{key.removeprefix('override /').removeprefix('/')}/{name}.yaml"
        else:
            raise RuntimeError(f"unsupported default: {default!r}")
        out = merge(out, compose(target))
    value.pop("defaults", None)
    return merge(out, value)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    selectors: dict[str, dict[str, Any]] = {}
    for cell, (gpu, seed, source_name) in CELLS.items():
        cfg = compose(CONFIG / f"ablation/wbmanip/base_v26_8_{cell}.yaml")
        source_path, source_digest = SOURCES[source_name]
        env, rewards = cfg["env"]["config"], cfg["rewards"]
        require(cfg.get("v26_schema") == "a2_piper_base_v26_8_bilateral_opening_scaffold_decay_v1", f"{cell}: schema")
        require(cfg.get("v26_plan_id") == "base_v26_8_bilateral_opening_scaffold_decay_20260903", f"{cell}: plan")
        require(cfg.get("v26_cell") == f"V26_8_{cell}" and cfg.get("seed") == seed, f"{cell}: identity")
        require(cfg.get("checkpoint") == source_path and cfg.get("checkpoint_load_mode") == "policy_only" and cfg.get("policy_only_load_actor_rms") is True and cfg.get("auto_load_latest") is False, f"{cell}: checkpoint contract")
        checkpoint = ROOT / source_path
        require(checkpoint.is_file() and digest(checkpoint) == source_digest, f"{cell}: frozen source SHA-256")
        require(cfg.get("num_envs") == 4096 and cfg["algo"]["trl"]["num_total_batches"] == 3000 and cfg["callbacks"]["model_save"]["save_frequency"] == 250, f"{cell}: budget/save")
        require(env.get("a2_v26_door_open_lr") == "bilateral" and env.get("a2_v26_side_permutation_seed") == seed, f"{cell}: bilateral seed")
        arm = cell[0]
        require(float(env["a2_stage3_unlatch_near_closed_hinge_threshold"]) == (0.25 if arm == "W" else 0.1), f"{cell}: arm threshold")
        if arm == "K":
            require(rewards.get("reward_penalty_curriculum") is True and tuple(rewards.get("reward_penalty_reward_names", ())) == PENALTY_NAMES, f"{cell}: K reward list")
            require(rewards.get("reward_penalty_level_down_ave_goal_reached_rate") is None and rewards.get("reward_penalty_level_up_ave_goal_reached_rate") is None, f"{cell}: legacy goal driver must be disabled")
            expected_k = {"a2_v26_8_penalty_driver": "side_min_natural_stage_reach_rate", "a2_v26_8_penalty_driver_target_stage": 4, "a2_v26_8_penalty_driver_level_down_rate": 0.5, "a2_v26_8_penalty_driver_level_up_rate": 0.7, "a2_v26_8_penalty_curriculum_trace_enabled": True}
            require(all(env.get(key) == want for key, want in expected_k.items()), f"{cell}: K driver")
        else:
            require("a2_v26_8_penalty_driver" not in env and rewards.get("reward_penalty_curriculum") is not True, f"{cell}: non-K leakage")
        selectors[cell] = {"physical_gpu": gpu, "seed": seed, "source": source_name, "checkpoint": source_path, "checkpoint_sha256": source_digest}
    source = (ROOT / "gr00t/rl/envs/door/door_open_a2_base.py").read_text(encoding="utf-8")
    for fragment in ("a2_v26_8_penalty_driver", "_a2_v26_episode_start_stage", "a2_v26_8_penalty_curriculum_trace", "reward_penalty_scale"):
        require(fragment in source, f"v26-8 core source binding missing: {fragment}")
    for source_name, (checkpoint_path, _) in SOURCES.items():
        source_cfg = ROOT / checkpoint_path.replace("model_step_003000.pt", "resolved_config.yaml")
        resolved = yaml.safe_load(source_cfg.read_text(encoding="utf-8"))
        scales = resolved.get("rewards", {}).get("reward_scales")
        require(isinstance(scales, dict) and all(name in scales and float(scales[name]) != 0.0 for name in PENALTY_NAMES), f"{source_name}: v26-8 penalty list must be nonzero in source reward scales")
    eval_script = (ROOT / "scriptsFORhuman/v26_8/v26_8_eval_cell.sh").read_text(encoding="utf-8")
    require("++rewards.reward_penalty_curriculum=false" in eval_script and "++checkpoint_load_mode=full" in eval_script, "v26-8 eval curriculum/load override")
    locked_paths = [ROOT / "gr00t/rl/envs/door/door_open_a2_base.py", *sorted((ROOT / "gr00t/rl/config/ablation/wbmanip").glob("base_v26_8_*.yaml")), *sorted(path for path in (ROOT / "scriptsFORhuman/v26_8").iterdir() if path.is_file()), *sorted((ROOT / "gr00t/rl/tests").glob("test_a2_v26_8_*.py"))]
    locked = {str(path.relative_to(ROOT)): digest(path) for path in locked_paths if path.is_file()}
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).splitlines()
    payload = {"schema": "a2_piper_base_v26_8_static_lock_v1", "status": "STATIC_PASS", "git_head": git_head, "git_status_short": git_status, "selectors": selectors, "source_consumers": {"a2_stage3_unlatch_near_closed_hinge_threshold": source.count("a2_stage3_unlatch_near_closed_hinge_threshold")}, "penalty_reward_names": list(PENALTY_NAMES), "source_lock": locked, "eval_contract": {"exact_episodes": 64, "curriculum_override": "++rewards.reward_penalty_curriculum=false", "natural_start": True}, "runtime_load_contract": {"checkpoint_load_mode": "policy_only", "actor_rms_loaded": True, "strict": True, "state_key": "policy_state_dict", "receipt": "v26_8_policy_load_receipt.json"}, "source_conflict_reconciliation": "The official v26-5 receipt always derives residual-only optimizer facts for train and therefore cannot certify the legacy actor. v26-8 keeps the ordinary strict policy-only+actor-RMS loader, then the v26-8 stream wrapper creates its own receipt only after the loader's observed success line; full exact64 eval uses full checkpoint loading and has no load receipt."}
    encoded = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    if args.output:
        require(not args.output.exists(), f"refusing to overwrite static lock: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
