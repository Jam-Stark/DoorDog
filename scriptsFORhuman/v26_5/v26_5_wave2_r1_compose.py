#!/usr/bin/env python3
"""Resolve R1 train selectors and two-stage eval contracts without Isaac."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "gr00t/rl/config"
ISAAC_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
SOURCE = ROOT / "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"

def merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in update.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result

def compose(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise RuntimeError(f"config is not mapping: {path}")
    result: dict[str, Any] = {}
    for entry in value.get("defaults", []):
        if entry == "_self_": continue
        if isinstance(entry, str) and entry.startswith("/"):
            result = merge(result, compose(CONFIG_ROOT / f"{entry.removeprefix('/')}.yaml"))
        elif isinstance(entry, dict) and len(entry) == 1:
            key, target = next(iter(entry.items()))
            if not isinstance(key, str) or not isinstance(target, str):
                raise RuntimeError(f"unsupported R1 default: {entry!r}")
            if key.startswith("override /"):
                config_path = CONFIG_ROOT / f"{key.removeprefix('override /')}/{target}.yaml"
            elif key.startswith("/"):
                config_path = CONFIG_ROOT / f"{key.removeprefix('/')}/{target}.yaml"
            else:
                raise RuntimeError(f"unsupported R1 default: {entry!r}")
            result = merge(result, compose(config_path))
        else: raise RuntimeError(f"unsupported R1 default: {entry!r}")
    value.pop("defaults", None)
    return merge(result, value)

def resolve_eval(seed: int, side: str) -> dict[str, Any]:
    """Use eval_agent_trl over the actual checkpoint training config.

    ``base_eval`` alone cannot resolve training interpolations.  This records
    the checkpoint-derived host half through the actual eval entrypoint; the
    R1 selector half is emitted separately and merged by that entrypoint at
    runtime.
    """
    command = [
        str(ISAAC_PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        "--config-path", str(SOURCE.parent), "--config-name", "config",
        "--cfg", "job", "--resolve",
        f"++checkpoint={SOURCE}", "++checkpoint_load_mode=policy_only",
        "++policy_only_load_actor_rms=true", "++auto_load_latest=false",
        f"++seed={seed}", "++num_envs=64",
        "++algo.config.num_mini_batches=1",
        "++algo.config.eval.num_eval_episodes=64",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.eval.a2_forced_gripper_close_enabled=false",
        "++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false",
        "++env.config.a2_v26_2_telemetry_enabled=true",
        "++env.config.a2_v26_3_telemetry_enabled=true",
        f"++env.config.a2_v26_door_open_lr={side}",
        f"++env.config.a2_v26_side_permutation_seed={seed}",
        "++env.config.enable_staged_reset=false",
    ]
    result = subprocess.run(
        command, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
        text=True, capture_output=True, check=True,
    )
    value = yaml.safe_load(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("eval_agent_trl --cfg job --resolve did not emit a mapping")
    return value

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--output-dir", type=Path, required=True); a = p.parse_args()
    if a.output_dir.exists(): raise RuntimeError(f"refusing to overwrite R1 static root: {a.output_dir}")
    a.output_dir.mkdir(parents=True)
    if not SOURCE.is_file(): raise RuntimeError(f"CONT_STEP2000 source checkpoint missing: {SOURCE}")
    # Record the selector half independently of the checkpoint-derived host
    # config.  The per-cell files below hold the resolved final contract.
    partial = compose(CONFIG_ROOT / "ablation/wbmanip/base_v26_5_wave2_R1_eval_policy_residual.yaml")
    (a.output_dir / "R1_eval_ablation_partial.yaml").write_text(yaml.safe_dump(partial, sort_keys=True), encoding="utf-8")
    for seed in (0, 1):
        cfg = compose(CONFIG_ROOT / "ablation/wbmanip/base_v26_5_wave2_R1_policy_residual.yaml")
        cfg["seed"] = seed; cfg.setdefault("env", {}).setdefault("config", {})["a2_v26_side_permutation_seed"] = seed
        (a.output_dir / f"R1_S{seed}_train.yaml").write_text(yaml.safe_dump(cfg, sort_keys=True), encoding="utf-8")
        for side in ("left", "right"):
            cfg = resolve_eval(seed, side)
            (a.output_dir / f"R1_S{seed}_eval_{side}.yaml").write_text(yaml.safe_dump(cfg, sort_keys=True), encoding="utf-8")
    print(a.output_dir)

if __name__ == "__main__": main()
