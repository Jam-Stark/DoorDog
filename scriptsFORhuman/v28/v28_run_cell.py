"""Execute an authorized v28 contact, walk, PPO, or evaluation attempt."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from v28_contract import ROOT, RUNTIME, PYTHON, cell_contract

PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY")
RIG = ROOT / "scriptsFORhuman/v28/camera/U3_F39_H140.json"
RESUME = RUNTIME / "resume_20260911"


def runtime_env(gpu):
    return {**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu), "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "ACCELERATE_TORCH_DEVICE": "cuda:0", "WANDB_MODE": "disabled", "HYDRA_FULL_ERROR": "1",
            "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "8", "PYTHONPATH": str(ROOT)}


def run(command, output, gpu, expected, metadata):
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "a2_piper_v28_process_v2", "state": "RUNNING", "command": command,
               "worktree": str(ROOT), "resources": {"physical_gpu": gpu, "logical_device": "cuda:0"},
               "proxy_environment": {key: os.environ.get(key, "") for key in PROXY_KEYS},
               "started_at": datetime.now(timezone.utc).isoformat(), "expected_outputs": [str(p) for p in expected],
               **metadata}
    path = output / "process_receipt.json"
    with (output / "runtime.log").open("x") as stream:
        process = subprocess.Popen(command, cwd=ROOT, env=runtime_env(gpu), stdout=stream, stderr=subprocess.STDOUT)
        receipt["pid"] = process.pid
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        returncode = process.wait()
    log = (output / "runtime.log").read_text(errors="replace")
    iterations = re.findall(r"Learning iteration\s+(\d+)", log)
    receipt.update(returncode=returncode, finished_at=datetime.now(timezone.utc).isoformat(),
                   policy_readout_observed=bool(iterations) or "Starting evaluation with" in log,
                   last_iteration=None if not iterations else int(iterations[-1]))
    receipt["missing_outputs"] = [str(p) for p in expected if not p.is_file()]
    receipt["state"] = "PASS" if returncode == 0 and not receipt["missing_outputs"] else "FAIL"
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"{output.name}: {receipt['state']}", flush=True)
    return 0 if receipt["state"] == "PASS" else 1


def contact(args):
    data = args.output / "data"
    command = [PYTHON, "-B", str(ROOT / "scriptsFORhuman/v28/v28_g0_contact_probe.py"), "--output", str(data)]
    return run(command, args.output, args.gpu, [data / "contact_probe.json", data / "camera_trace.json"],
               {"mode": "contact", "decision_log_ids": ["V28-D034", "V28-D035"]})


def walk(args):
    poses_path = RESUME / "walk_inputs/postures.json"
    poses = json.loads(poses_path.read_text())["postures"]
    usd = ROOT / "gr00t/rl/data/robots" / (
        "A2_Piper/a2_piper.usd" if args.asset == "baseline" else "a2_piper_v28_merged_20260909/a2_piper.usd"
    )
    commands = RUNTIME / "g0/walk/commands.json"
    metrics = args.output / "metrics.json"
    command = [PYTHON, "-B", str(ROOT / "gr00t/rl/scripts/smoke_a2_base_flat_walk.py"),
               "--headless", "--device", "cuda:0", "--num-envs", "64", "--usd-file", str(usd),
               "--arm-posture", *[str(x) for x in poses[args.posture]], "--command-script", str(commands),
               "--metrics-json", str(metrics), "--seed", "281", "--log-interval", "0"]
    return run(command, args.output, args.gpu, [metrics], {"mode": "walk", "asset": args.asset, "posture": args.posture,
               "posture_input": str(poses_path), "command_input": str(commands)})


def train(args):
    spec = cell_contract(args.cell)
    is_smoke = args.mode == "smoke"
    budget = 5 if is_smoke else spec["batches"]
    if spec["checkpoint"] is not None and not Path(spec["checkpoint"]).is_file():
        raise FileNotFoundError(spec["checkpoint"])
    command = [PYTHON, "-B", "-m", "gr00t.rl.train_agent_trl",
               "+exp=wbmanip/door_open_a2_base_lstm", f"+ablation=wbmanip/base_v28_{args.cell}",
               "headless=true", "use_wandb=false", f"++experiment_dir={args.output}", f"output_dir={args.output}/output",
               "project_name=base_v28_camera_aware_rebaseline", f"experiment_name=V28_{args.cell}"]
    if is_smoke:
        command += ["num_envs=64", "algo.trl.num_total_batches=5", "callbacks.model_save.save_frequency=5"]
    return run(command, args.output, args.gpu, [args.output / f"model_step_{budget:06d}.pt", args.output / "config.yaml"],
               {"mode": args.mode, "cell": args.cell, "batches": budget, "source_checkpoint": spec["checkpoint"]})


def evaluate(args):
    if not args.checkpoint.is_file() or not (args.checkpoint.parent / "config.yaml").is_file():
        raise FileNotFoundError(f"checkpoint and adjacent config required: {args.checkpoint}")
    values = {
        "checkpoint": str(args.checkpoint), "checkpoint_load_mode": "full", "auto_load_latest": False,
        "seed": args.seed, "num_envs": args.episodes, "algo.config.num_mini_batches": 1,
        "algo.config.eval.num_eval_episodes": args.episodes, "algo.config.eval.eval_num_envs_episodes": True,
        "algo.config.eval.dump_to_log_metrics": True, "algo.config.eval.a2_diagnostic_trace_enabled": True,
        "algo.config.eval.a2_diagnostic_reward_terms": ["stage", "success_save_time", "a2_stage3_handle_creation",
             "a2_stage3_unlatch_hold", "push_door_hinge", "a2_stage3_stage4_hold_and_drive",
             "penalty_a2_wrist_motion_l2", "penalty_a2_wrist_tower_contact", "penalty_a2_stage4_arm_default_pose_l1"],
        "algo.config.eval.a2_forced_gripper_close_enabled": False,
        "algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled": False,
        "env.config.a2_v26_2_telemetry_enabled": True, "env.config.a2_v26_3_telemetry_enabled": True,
        "env.config.a2_v28_camera_telemetry_enabled": True,
        "env.config.a2_v26_door_open_lr": args.side, "env.config.a2_v26_side_permutation_seed": args.seed,
        "env.config.enable_staged_reset": False, "rewards.reward_penalty_curriculum": False,
        "env.config.a2_v26_8_penalty_driver": None, "simulator.config.render_results": False,
        "simulator.config.cameras.enable_cameras": False,
        "experiment_dir": str(args.output), "env.config.experiment_dir": str(args.output),
        "env.config.save_rendering_dir": str(args.output / "renderings"), "output_dir": str(args.output / "output"),
        "eval_name": f"V28_{args.cell}_{args.side}", "eval_output_dir": str(args.output),
    }
    command = [PYTHON, "-B", "-m", "gr00t.rl.eval_agent_trl", "+ablation=wbmanip/base_v28_eval_natural_start",
               *[f"++{key}=" + json.dumps(value, separators=(",", ":")) for key, value in values.items()]]
    expected = [args.output / name for name in ("metrics_eval.json", "a2_v14_per_env_records.json",
                "stage2_5_step_trace.json", "a2_eval_diagnostic_metadata.json", ".hydra/runtime_config.yaml")]
    lane = {"cell": args.cell, "stratum": args.stratum, "side": args.side, "seed": args.seed,
            "episodes": args.episodes, "checkpoint": str(args.checkpoint), "artifact_path": str(args.output), "camera_rig": str(RIG)}
    return run(command, args.output, args.gpu, expected, {"mode": "eval", "lane": lane, "overrides": values})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["contact", "walk", "smoke", "train", "eval"])
    parser.add_argument("--gpu", type=int, choices=range(8), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cell", default="A_S281")
    parser.add_argument("--asset", choices=["baseline", "v28"])
    parser.add_argument("--posture", choices=["default", "hold", "stage2"])
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--side", choices=["left", "right"])
    parser.add_argument("--episodes", type=int, choices=[64, 128], default=64)
    parser.add_argument("--seed", type=int, default=280001)
    parser.add_argument("--stratum", default="nominal")
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.mode == "contact":
        return contact(args)
    if args.mode == "walk":
        if args.asset is None or args.posture is None:
            parser.error("walk requires --asset and --posture")
        return walk(args)
    if args.mode == "eval":
        if args.checkpoint is None or args.side is None:
            parser.error("eval requires --checkpoint and --side")
        args.checkpoint = args.checkpoint.resolve()
        return evaluate(args)
    return train(args)


if __name__ == "__main__":
    raise SystemExit(main())
