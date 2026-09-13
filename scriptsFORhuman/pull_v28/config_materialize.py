#!/usr/bin/env python3
"""Materialize the v28 flat contract from the real P_S2 resolved input."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO / "logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S2/resolved_config.yaml"
DEFAULT_DELTA = REPO / "gr00t/rl/config/ablation/wbmanip/pull_v28_common.yaml"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def set_path(mapping: dict, path: tuple[str, ...], value) -> None:
    current = mapping
    for key in path[:-1]:
        require(key in current and isinstance(current[key], dict), f"P_S2 missing required path: {'.'.join(path)}")
        current = current[key]
    current[path[-1]] = value


def merge(base: dict, delta: dict) -> None:
    for key, value in delta.items():
        if isinstance(value, dict):
            require(key in base and isinstance(base[key], dict), f"delta path absent from P_S2: {key}")
            merge(base[key], value)
        else:
            base[key] = value


def apply_raw_robot_delta(resolved: dict, old: dict, new: dict, path: tuple[str, ...] = ()) -> None:
    """Apply only S2 raw-group changes; retain P_S2 resolved overrides elsewhere."""
    require(set(old) <= set(new), f"S2 raw robot removed keys at {'.'.join(path) or 'robot'}")
    for key, new_value in new.items():
        old_value = old.get(key)
        target_path = path + (key,)
        if isinstance(old_value, dict) and isinstance(new_value, dict):
            require(key in resolved and isinstance(resolved[key], dict), f"P_S2 robot missing mapping: {'.'.join(target_path)}")
            apply_raw_robot_delta(resolved[key], old_value, new_value, target_path)
        elif old_value != new_value:
            require(key in resolved, f"P_S2 robot missing leaf: {'.'.join(target_path)}")
            resolved[key] = new_value


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cell", required=True, choices=("PA_S1", "PA_S2", "PA_S3", "G0"))
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--train-dir", type=Path, required=True)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--robot-config", type=Path, default=REPO / "gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml")
    p.add_argument("--base-robot-config", type=Path, default=REPO / "gr00t/rl/config/robot/A2_Piper/a2_piper.yaml")
    p.add_argument("--delta", type=Path, default=DEFAULT_DELTA)
    a = p.parse_args()
    require(a.source.is_file(), f"missing P_S2 resolved input: {a.source}")
    require(a.robot_config.is_file(), f"S2 robot config not applied: {a.robot_config}")
    require(a.base_robot_config.is_file(), f"missing P_S2 raw robot base: {a.base_robot_config}")
    require(a.delta.is_file(), f"missing v28 delta: {a.delta}")
    require(not a.output.exists(), f"refusing to overwrite: {a.output}")
    cfg = yaml.safe_load(a.source.read_text(encoding="utf-8"))
    require(cfg["num_envs"] == 1024, "P_S2 resolved input is not the 1024-env contract")
    obs_dims = {next(iter(item)): next(iter(item.values())) for item in cfg["obs"]["obs_dims"]}
    actor_dim = sum(obs_dims[name] for name in cfg["obs"]["obs_dict"]["actor_obs"])
    critic_dim = sum(obs_dims[name] for name in cfg["obs"]["obs_dict"]["critic_obs"])
    require((actor_dim, critic_dim, obs_dims["actions"]) == (133, 138, 19), "P_S2 actor/critic/action contract diverged")
    source_env = cfg["env"]["config"]
    require(source_env["completion_stage"] == 5 and source_env["staged_reset_ratios"] == [.5, .1, .1, .1, .1, .1], "P_S2 stage/reset contract diverged")
    merge(cfg, yaml.safe_load(a.delta.read_text(encoding="utf-8")))
    env = cfg["env"]["config"]
    old_raw_robot = yaml.safe_load(a.base_robot_config.read_text(encoding="utf-8"))["robot"]
    new_raw_robot = yaml.safe_load(a.robot_config.read_text(encoding="utf-8"))["robot"]
    require(new_raw_robot["num_bodies"] == 28 and new_raw_robot["actions_dim"] == 20, "S2 vPiper body/action contract diverged")
    robot = cfg["robot"]
    apply_raw_robot_delta(robot, old_raw_robot, new_raw_robot)
    envs = 256 if a.smoke else 1024
    cfg.update(checkpoint=None, checkpoint_load_mode="full", auto_load_latest=False, seed=a.seed,
               num_envs=envs, project_name="a2_piper_pull_v28",
               experiment_name=a.cell, experiment_dir=str(a.train_dir), output_dir=str(a.train_dir / "output"))
    for path in (("env", "config", "num_envs"), ("env", "config", "simulator", "config", "scene", "num_envs"), ("simulator", "config", "scene", "num_envs")):
        set_path(cfg, path, envs)
    cfg["algo"]["trl"]["num_total_batches"] = 5 if a.smoke else 6000
    cfg["callbacks"]["model_save"]["save_frequency"] = 250
    for callback in ("model_save", "autoresume"):
        if callback in cfg["callbacks"] and "save_dir" in cfg["callbacks"][callback]:
            cfg["callbacks"][callback]["save_dir"] = str(a.train_dir)
    cfg["algo"]["trl"]["output_dir"] = str(a.train_dir)
    env["robot"] = robot
    cfg["robot"] = robot
    env["a2_door_open_lr_permutation_seed"] = a.seed
    for key, expected in {"a2_v26_6_side_mirrored_handle_offset_enabled": True,
                          "a2_stage2_squeeze_force_min": .5, "a2_stage2_squeeze_force_max": 30.,
                          "a2_stage2_over_force_threshold": 55., "a2_stage3_unlatch_near_closed_hinge_threshold": .25,
                          "a2_pull_v6_stage4_bank_enabled": False, "a2_pull_v61_late_state_bank_enabled": False}.items():
        require(env.get(key) == expected, f"P_S2 preserved contract diverged: {key}")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
