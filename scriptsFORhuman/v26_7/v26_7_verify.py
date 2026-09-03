#!/usr/bin/env python3
"""Static source/config lock for the frozen v26-7 operation path."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "gr00t/rl/config"
CELLS = {"Q05_S0": (2, 0, 0.5), "Q05_S1": (3, 1, 0.5), "Q05_S2": (4, 2, 0.5), "Q20_S0": (5, 0, 2.0), "Q20_S1": (6, 1, 2.0), "Q20_S2": (7, 2, 2.0)}

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

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    selectors = {}
    for cell, (gpu, seed, squeeze) in CELLS.items():
        cfg = compose(CONFIG / f"ablation/wbmanip/base_v26_7_{cell}.yaml")
        env, robot = cfg["env"]["config"], cfg["robot"]
        require(cfg.get("v26_schema") == "a2_piper_base_v26_7_bilateral_native_unlatch_v1", f"{cell}: schema")
        require(cfg.get("v26_plan_id") == "base_v26_7_bilateral_native_unlatch_20260902", f"{cell}: plan")
        require(cfg.get("v26_cell") == f"V26_7_{cell}" and cfg.get("seed") == seed, f"{cell}: identity")
        require(cfg.get("checkpoint") is None and cfg.get("checkpoint_load_mode") == "full" and cfg.get("auto_load_latest") is False, f"{cell}: scratch checkpoint contract")
        require(cfg.get("num_envs") == 4096 and cfg["algo"]["trl"]["num_total_batches"] == 6000 and cfg["callbacks"]["model_save"]["save_frequency"] == 250, f"{cell}: budget/save")
        for key, want in {"a2_v26_door_open_lr": "bilateral", "a2_v26_6_side_mirrored_handle_offset_enabled": True, "a2_stage2_squeeze_force_min": squeeze, "a2_m39_gripper_material_enabled": True, "a2_stage2_squeeze_force_max": 30.0, "a2_stage2_over_force_threshold": 55.0}.items():
            require(env.get(key) == want, f"{cell}: env.config.{key}")
        require([float(x) for x in robot["dof_effort_limit_list"][-2:]] == [45.0, 45.0], f"{cell}: effort")
        require(all(float(robot["control"][group][joint]) == want for group, want in (("stiffness", 1300.0), ("damping", 32.0)) for joint in ("arm_j7", "arm_j8")), f"{cell}: gains")
        require(cfg["simulator"]["config"]["sim"]["physx"]["num_velocity_iterations"] == 2, f"{cell}: PhysX")
        selectors[cell] = {"physical_gpu": gpu, "seed": seed, "squeeze_force_min": squeeze}
    source = (ROOT / "gr00t/rl/envs/door/door_open_a2_base.py").read_text(encoding="utf-8")
    require("a2_v26_6_mirror_quat_wxyz," in source and "a2_v26_6_side_mirrored_handle_offset_enabled=(" in source and '"target_quat_source_handle"' in source, "v26-7 source wiring/dump path")
    for script, fragment in {"v26_7_train_cell.sh": "ACCELERATE_TORCH_DEVICE=cuda:0", "v26_7_eval_cell.sh": "[[ \"$gpu\" =~ ^[01]$ ]]", "v26_7_g2_waveB_eval_cell.sh": "[[ \"$gpu\" =~ ^[01]$ ]]"}.items():
        require(fragment in (ROOT / "scriptsFORhuman/v26_7" / script).read_text(encoding="utf-8"), f"{script}: GPU binding")
    reducer = (ROOT / "scriptsFORhuman/v26_7/v26_7_reduce.py").read_text(encoding="utf-8")
    orchestrator = (ROOT / "scriptsFORhuman/v26_7/v26_7_orchestrate.sh").read_text(encoding="utf-8")
    active = (ROOT / "scriptsFORhuman/v26_7/v26_7_active_cells.py").read_text(encoding="utf-8")
    require("frozen_config_endpoints" in reducer and "config_endpoints" in reducer and "all_six_active" in reducer and "stop_eligible_cells" in reducer, "milestone frozen endpoint/early-failure binding")
    require("active_cells_for_step" in orchestrator and "EARLY_SUCCESS_ENDPOINT_STOP_SIGNALLED" in orchestrator and "V26_7_NO_ACTIVE_CONFIGS" in orchestrator, "orchestrator endpoint stop/no-active binding")
    require("endpoint changed after freeze" in active and "NO_ACTIVE" in active, "active-cell endpoint immutability binding")
    payload = {"schema": "a2_piper_base_v26_7_static_lock_v1", "status": "STATIC_PASS", "selectors": selectors, "source_binding": {"side_mirrored_offset": True, "target_quat_source_handle_dump": True}, "early_success_endpoint_binding": True, "eval_gpus": [0, 1]}
    encoded = json.dumps(payload, indent=2) + "\n"
    if args.output:
        require(not args.output.exists(), f"refusing to overwrite static lock: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")

if __name__ == "__main__":
    main()
