"""Materialize authorized cells and freeze their actual CPU-resolved contracts."""
from __future__ import annotations

import argparse
import concurrent.futures
import shutil
import subprocess
from pathlib import Path

import yaml

from v27_contract import (ROOT, CONFIG, HERE, PLAN, RUNTIME, TRAIN, EVAL, OLD_TRAIN, PYTHON,
                         cells, digest, flatten, input_checkpoint, merge, read_json,
                         require, write_json, yaml_write)
from v27_run_cell import WORKFLOW_KEYS, runtime_env, train_command


def prepare_inputs():
    entries = {}
    for cell in ("C_S2", "W_S2", "K_S2"):
        original = OLD_TRAIN / cell / "model_step_003000.pt"
        copied = input_checkpoint(cell)
        require(original.is_file() and (original.parent / "config.yaml").is_file(), f"missing {cell} source")
        copied.parent.mkdir(parents=True, exist_ok=False)
        files = {}
        for name in ("model_step_003000.pt", "config.yaml", "resolved_config.yaml"):
            source, target = original.parent / name, copied.parent / name
            shutil.copy2(source, target)
            expected, actual = digest(source), digest(target)
            require(expected == actual, f"input copy differs: {name}")
            files[name] = {"original": str(source), "copy": str(target), "sha256": actual}
        entries[cell] = files
    write_json(RUNTIME / "input_lock.json", {"status": "INPUTS_FROZEN", "inputs": entries})


def q_overlays():
    # This file is authored from the G5 consumer trace before any policy readout.
    contract = read_json(RUNTIME / "g5_overlay_contract.json")
    g5 = yaml.safe_load((CONFIG / "base_v17_G5_full_m34_m35_hinge125.yaml").read_text())
    actual = flatten(g5)
    for arm in ("Q1", "Q2"):
        for key, value in flatten(contract[arm]).items():
            require(actual[key] == value, f"{arm}: G5 value mismatch {key}")
    return {"C": {}, "Q1": contract["Q1"], "Q2": contract["Q2"]}


def k_overlay():
    source = yaml.safe_load((CONFIG / "base_v26_8_K_S2.yaml").read_text())
    env = {key: value for key, value in source["env"]["config"].items() if key.startswith("a2_v26_8_")}
    return {"rewards": source["rewards"], "env": {"config": env}}


def domain_overlay(recipe):
    if recipe == "current":
        return {}
    require(recipe in ("L1", "L1prime"), "unknown domain recipe")
    env = {"a2_v26_door_weight_range": [80.0,160.0], "a2_v24_friction_enabled": True,
           "a2_v24_friction_backend": "native_joint_friction_v1",
           "a2_v24_friction_static_effort": 2.0 if recipe == "L1prime" else 0.0,
           "a2_v24_friction_dynamic_effort": 1.5 if recipe == "L1prime" else 0.0,
           "a2_v24_friction_viscous_coefficient": 0.0}
    if recipe == "L1":
        env.update({"a2_v27_friction_bucket_enabled": True,
                    "a2_v27_friction_bucket_static_efforts": [0.0,2.0,5.0]})
    return {"env": {"config": env}}


def recovery_overlay(arm):
    return {"env": {"config": {
        "a2_v27_recovery_enabled": arm != "R0", "a2_v27_recovery_loss_steps": 10,
        "a2_v27_recovery_window_steps": 300, "a2_v27_recovery_bank_reset_share": 0.2 if arm == "R2" else 0.0,
        "a2_v27_perturb_prob": 0.2, "a2_v27_perturb_steps": 4}}}


def materialize(wave, recipe_a, recipe_b):
    overlays = q_overlays()
    require(recipe_a in overlays, "unknown RECIPE_A")
    common = CONFIG / "base_v27_common.yaml"
    if not common.exists():
        yaml_write(common, {"defaults": ["/ablation/wbmanip/base_v26_7_common", "_self_"],
            "v26_schema": "a2_piper_base_v27_bilateral_hardening_v1", "v26_plan_id": "base_v27_bilateral_hardening_20260905",
            "v26_phase": "V27_BILATERAL_HARDENING", "v26_cell": "V27_UNASSIGNED",
            "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True,
            "auto_load_latest": False, "num_envs": 4096,
            "algo": {"trl": {"num_total_batches": 3000}},
            "callbacks": {"model_save": {"save_frequency": 250}}})
    configurations = {}
    for cell, spec in cells(wave).items():
        arm = spec["arm"]
        source = input_checkpoint("C_S2")
        overlay = {}
        if wave == "A":
            overlay = overlays[arm]
        elif wave == "B" and arm.startswith("L"):
            decision = read_json(RUNTIME / "wave_a_decision.json")
            require(decision["RECIPE_A"] == recipe_a, "Wave B must use frozen RECIPE_A")
            source = Path(decision["CARRIER_A"])
            overlay = merge(overlays[recipe_a], domain_overlay(recipe_b) if arm == "L1" else {})
        elif wave == "B":
            overlay = recovery_overlay(arm)
        else:
            decision = read_json(RUNTIME / "wave_b_decision.json")
            require(decision["RECIPE_B"] == recipe_b, "Wave C must use frozen RECIPE_B")
            overlay = merge(overlays[recipe_a], domain_overlay(recipe_b))
            if arm == "SK":
                overlay = merge(overlay, k_overlay())
        value = {"defaults": ["/ablation/wbmanip/base_v27_common", "_self_"],
                 "v26_cell": f"V27_{cell}", "seed": spec["seed"], "checkpoint": str(source),
                 "algo": {"trl": {"num_total_batches": spec["batches"]}},
                 "env": {"config": {"a2_v26_side_permutation_seed": spec["seed"]}}}
        if wave == "C":
            value.update({"checkpoint": None, "checkpoint_load_mode": "full", "policy_only_load_actor_rms": False})
        value = merge(value, overlay)
        yaml_write(CONFIG / f"base_v27_{cell}.yaml", value)
        configurations[cell] = value
    write_json(RUNTIME / f"wave_{wave.lower()}_declaration.json", {
        "wave": wave, "RECIPE_A": recipe_a, "RECIPE_B": recipe_b,
        "cells": configurations, "plan": str(PLAN), "status": "DECLARED"})


def resolve_cell(cell, spec):
    path = RUNTIME / "compose" / cell / "resolved_config.yaml"
    path.parent.mkdir(parents=True, exist_ok=False)
    command = train_command(cell, TRAIN / cell)
    with path.open("x") as stream:
        result = subprocess.run([*command, "--cfg", "job", "--resolve"], cwd=ROOT,
            env=runtime_env(spec["gpu"]), stdout=stream, stderr=subprocess.PIPE, text=True)
    (path.parent / "stderr.log").write_text(result.stderr)
    require(result.returncode == 0, f"CPU compose failed {cell}: {result.stderr[-2000:]}")
    cfg = yaml.safe_load(path.read_text())
    values = flatten(cfg)
    expected = {"num_envs": 4096, "seed": spec["seed"], "v26_cell": f"V27_{cell}",
                "auto_load_latest": False, "algo.trl.num_total_batches": spec["batches"],
                "callbacks.model_save.save_frequency": 250, "env.config.a2_v26_door_open_lr": "bilateral",
                "env.config.a2_v26_side_permutation_seed": spec["seed"]}
    require(all(values[key] == value for key,value in expected.items()), f"{cell}: base contract")
    scratch = spec["arm"] in ("SC", "SK")
    require(cfg["checkpoint"] is None if scratch else cfg["checkpoint_load_mode"] == "policy_only"
            and cfg["policy_only_load_actor_rms"] is True, f"{cell}: source load")
    return {**spec, "checkpoint_sha256": None if scratch else digest(cfg["checkpoint"]),
            "resolved_path": str(path), "resolved_contract": {key: value for key,value in values.items() if key not in WORKFLOW_KEYS}}


def freeze_wave(wave):
    specifications = cells(wave)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {cell: pool.submit(resolve_cell, cell, spec) for cell,spec in specifications.items()}
        resolved = {cell: future.result() for cell,future in futures.items()}
    write_json(RUNTIME / f"wave_{wave.lower()}_contract.json", {"status": "STATIC_PASS", "wave": wave, "cells": resolved})


def freeze_source():
    paths = [PLAN, ROOT / "gr00t/rl/envs/door/door_open_a2_base.py",
             ROOT / "gr00t/rl/envs/base_task/staged_task_base.py",
             ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py",
             ROOT / "gr00t/rl/train_agent_trl.py", ROOT / "gr00t/rl/eval_agent_trl.py"]
    paths += sorted(HERE.glob("v27_*.py")) + sorted(HERE.glob("v27_*.sh"))
    paths += sorted(CONFIG.glob("base_v27_*.yaml"))
    paths += sorted((ROOT / "gr00t/rl/tests").glob("test_a2_v27_*.py"))
    locked = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    write_json(RUNTIME / "source_lock.json", {"status": "SOURCE_FROZEN", "source_lock": locked,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).splitlines(),
        "input_lock": str(RUNTIME / "input_lock.json")})
    write_json(RUNTIME / "active_source_lock.json", {"path": str(RUNTIME / "source_lock.json")})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inputs", "materialize", "resolve", "freeze"))
    parser.add_argument("--wave", choices=("A","B","C"))
    parser.add_argument("--recipe-a", default="C")
    parser.add_argument("--recipe-b", default="current")
    args = parser.parse_args()
    if args.command == "inputs": prepare_inputs()
    elif args.command == "materialize": materialize(args.wave, args.recipe_a, args.recipe_b)
    elif args.command == "resolve": freeze_wave(args.wave)
    else: freeze_source()


if __name__ == "__main__":
    main()
