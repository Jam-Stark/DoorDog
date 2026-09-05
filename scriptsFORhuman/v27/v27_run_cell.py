"""Run a single immutable v27 attempt and record observed process evidence."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from v27_contract import (ROOT, PYTHON, PLAN, RUNTIME, PROXY_KEYS, cell_contract,
                         digest, flatten, read_json, require, write_json)

LOAD_LINE = "Loaded policy-only checkpoint actor from key 'policy_state_dict'; actor_rms_loaded=True"
ITERATION = re.compile(r"Learning iteration\s+(\d+)")
WORKFLOW_KEYS = {"timestamp", "experiment_dir", "save_dir", "output_dir",
                 "callbacks.model_save.save_dir", "callbacks.autoresume.save_dir", "wandb.wandb_dir"}


def runtime_env(gpu):
    return {**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu), "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "ACCELERATE_TORCH_DEVICE": "cuda:0", "WANDB_MODE": "disabled",
            "HYDRA_FULL_ERROR": "1", "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "8",
            "PYTHONPATH": str(ROOT)}


def override(key, value):
    import json
    return f"++{key}=" + json.dumps(value, separators=(",", ":"))


def capture(command, output, gpu, *, mode, expected_files, source=None):
    process = subprocess.Popen(command, cwd=ROOT, env=runtime_env(gpu), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    loaded = False
    policy_execution_started = False
    policy_readout = False
    iteration = 0
    evidence = output / "v27_process_evidence.json"
    base = {"command": command, "pid": process.pid, "gpu": gpu,
            "proxy_environment": {key: os.environ.get(key, "") for key in PROXY_KEYS},
            "plan_sha256": digest(PLAN), "source_lock": read_json(RUNTIME / "active_source_lock.json")["path"],
            "mode": mode, "source": source}
    write_json(evidence, {**base, "state": "RUNNING", "policy_readout_observed": False})
    with (output / "runtime.log").open("x") as log:
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
            changed = False
            if LOAD_LINE in line or (mode == "eval" and "Loaded checkpoint from step" in line):
                loaded = True
                changed = True
            matched = ITERATION.search(line)
            if matched:
                policy_readout = True
                iteration = int(matched.group(1))
                changed = True
            if mode == "eval" and "Starting evaluation with" in line:
                policy_execution_started = True
                changed = True
            if changed:
                write_json(evidence, {**base, "state": "RUNNING", "policy_load_observed": loaded,
                           "policy_readout_observed": policy_readout, "policy_execution_started": policy_execution_started,
                           "last_iteration": iteration}, replace=True)
    rc = process.wait()
    missing = [str(path) for path in expected_files if not path.is_file()]
    if mode == "eval" and (output / "metrics_eval.json").exists():
        policy_readout = True
    if source and mode == "train" and not loaded:
        missing.append("observed strict policy-only + actor RMS load")
    wrapper_rc = rc % 256 if rc else (1 if missing else 0)
    write_json(evidence, {**base, "state": "PASS" if wrapper_rc == 0 else "FAIL",
               "policy_load_observed": loaded, "policy_readout_observed": policy_readout,
               "policy_execution_started": policy_execution_started,
               "last_iteration": iteration, "isaac_process_returncode": rc,
               "wrapper_returncode": wrapper_rc, "missing": missing}, replace=True)
    return wrapper_rc


def train_command(cell, output, smoke=False):
    common = ["+exp=wbmanip/door_open_a2_base_lstm", f"+ablation=wbmanip/base_v27_{cell}",
              "headless=true", "use_wandb=false", "simulator.config.render_results=false",
              "simulator.config.cameras.enable_cameras=false", f"experiment_dir={output}",
              f"output_dir={output}/output", "project_name=base_v27_bilateral_hardening",
              f"experiment_name=V27_{cell}"]
    if smoke:
        common += ["num_envs=64", "algo.trl.num_total_batches=5", "callbacks.model_save.save_frequency=5"]
    return [PYTHON, "-B", "-m", "gr00t.rl.train_agent_trl", *common]


def train(args):
    contract = cell_contract(args.cell)
    require(args.gpu == contract["gpu"] or args.smoke, "frozen training GPU mapping")
    require(0 <= args.gpu <= 7, "GPU outside authorization")
    require(not args.output.exists(), "fresh train output required")
    args.output.mkdir(parents=True)
    command = train_command(args.cell, args.output, args.smoke)
    with (args.output / "resolved_config.yaml").open("x") as stream:
        subprocess.run([*command, "--cfg", "job", "--resolve"], cwd=ROOT, env=runtime_env(args.gpu),
                       stdout=stream, check=True)
    cfg = yaml.safe_load((args.output / "resolved_config.yaml").read_text())
    flat = flatten(cfg)
    expected = read_json(RUNTIME / f"wave_{contract['wave'].lower()}_contract.json")["cells"][args.cell]
    compared = {key: value for key, value in expected["resolved_contract"].items()
                if key not in WORKFLOW_KEYS}
    if args.smoke:
        compared.update({"num_envs": 64, "algo.trl.num_total_batches": 5,
                         "env.config.num_envs": 64,
                         "env.config.simulator.config.scene.num_envs": 64,
                         "simulator.config.scene.num_envs": 64,
                         "callbacks.model_save.save_frequency": 5})
    differences = {key: {"expected": value, "actual": flat.get(key)} for key, value in compared.items()
                   if flat.get(key) != value}
    write_json(args.output / "resolved_contract_check.json", {"status": "PASS" if not differences else "V27_INVALID",
               "differences": differences, "registered_contract": expected})
    require(not differences, f"V27_INVALID: resolved contract differs: {differences}")
    source = cfg["checkpoint"]
    if source:
        source = str((ROOT / source).resolve())
        require(digest(source) == expected["checkpoint_sha256"], "source checkpoint lock mismatch")
    budget = 5 if args.smoke else contract["batches"]
    steps = [5] if args.smoke else range(250, budget + 1, 250)
    expected_files = [args.output / f"model_step_{step:06d}.pt" for step in steps]
    expected_files.append(args.output / "config.yaml")
    return capture(command, args.output, args.gpu, mode="train", expected_files=expected_files, source=source)


def evaluate(args):
    require(args.gpu in (0, 1), "eval GPU must be 0 or 1")
    lane = read_json(args.manifest)["lanes"][args.lane]
    output = Path(lane["artifact_path"])
    require(not output.exists(), "fresh eval output required")
    checkpoint = Path(lane["checkpoint"])
    require(checkpoint.is_file() and (checkpoint.parent / "config.yaml").is_file(), "checkpoint-adjacent config missing")
    # Evaluation uses a private copy of historical checkpoints to avoid any writes to v26 artifacts.
    require("/base_v26/" not in str(checkpoint), "historical checkpoint must be mirrored into v27 inputs")
    output.mkdir(parents=True)
    n, seed, side = lane["episodes"], lane["seed"], lane["side"]
    values = {
        "checkpoint": str(checkpoint), "checkpoint_load_mode": "full", "auto_load_latest": False,
        "seed": seed, "num_envs": n, "algo.config.num_mini_batches": 1,
        "algo.config.eval.num_eval_episodes": n, "algo.config.eval.eval_num_envs_episodes": True,
        "algo.config.eval.dump_to_log_metrics": True, "algo.config.eval.a2_diagnostic_trace_enabled": True,
        "algo.config.eval.a2_diagnostic_reward_terms": ["stage", "success_save_time", "a2_stage3_handle_creation",
             "a2_stage3_unlatch_hold", "push_door_hinge", "a2_stage3_stage4_hold_and_drive"],
        "algo.config.eval.a2_forced_gripper_close_enabled": False,
        "algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled": False,
        "env.config.a2_v26_2_telemetry_enabled": True, "env.config.a2_v26_3_telemetry_enabled": True,
        "env.config.a2_v26_door_open_lr": side, "env.config.a2_v26_side_permutation_seed": seed,
        "env.config.enable_staged_reset": False, "rewards.reward_penalty_curriculum": False,
        "env.config.a2_v26_8_penalty_driver": None, "simulator.config.render_results": False,
        "env.config.save_rendering_dir": str(output / "renderings"),
        "output_dir": str(output / "output"),
        "eval_name": f"V27_{lane['cell']}_{lane['stratum']}_{side}", "eval_output_dir": str(output),
    }
    values.update(lane.get("overrides", {}))
    command = [PYTHON, "-B", "-m", "gr00t.rl.eval_agent_trl", "+ablation=wbmanip/base_v26_eval_natural_start",
               *[override(key, value) for key, value in values.items()]]
    write_json(output / "v27_eval_contract.json", {"lane": lane, "overrides": values})
    expected = [output / name for name in ("metrics_eval.json", "a2_v14_per_env_records.json",
                "stage2_5_step_trace.json", "a2_eval_diagnostic_metadata.json", ".hydra/runtime_config.yaml")]
    return capture(command, output, args.gpu, mode="eval", expected_files=expected, source=str(checkpoint))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    train_p = sub.add_parser("train")
    train_p.add_argument("--gpu", type=int, required=True)
    train_p.add_argument("--cell", required=True)
    train_p.add_argument("--output", type=Path, required=True)
    train_p.add_argument("--smoke", action="store_true")
    eval_p = sub.add_parser("eval")
    eval_p.add_argument("--gpu", type=int, required=True)
    eval_p.add_argument("--manifest", type=Path, required=True)
    eval_p.add_argument("--lane", type=int, required=True)
    args = parser.parse_args()
    return train(args) if args.mode == "train" else evaluate(args)


if __name__ == "__main__":
    sys.exit(main())
