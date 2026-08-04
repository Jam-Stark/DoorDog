#!/usr/bin/env python3
"""Prepare and run the pull-v0 P0-G canonical smoke and reload check."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
SOURCE_FREEZE_PATH = EVIDENCE_ROOT / "PULL_V0_SOURCE_FREEZE.json"
PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P0G_CANONICAL_SMOKE_PLAN_R2.json"
CONFIG_PATH = (
    ROOT
    / "gr00t/rl/config/ablation/wbmanip/pull_v0_p0_canonical_smoke.yaml"
)
TRAIN_ROOT = (
    ROOT
    / "logs_rl/a2_piper_full_stage_a2_pull/pull_v0_p0g/canonical_64x50"
)
RELOAD_ROOT = ROOT / "logs_eval/a2_piper_pull_v0/p0g_checkpoint_reload"
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
PHYSICAL_GPU = 2  # physical GPU2; CUDA_VISIBLE_DEVICES unset, +device=cuda:2
CHECKPOINT = TRAIN_ROOT / "model_step_000050.pt"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _command_env() -> dict[str, str]:
    return {
        "ACCELERATE_TORCH_DEVICE": f"cuda:{PHYSICAL_GPU}",
        "WANDB_MODE": "offline",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": "UNSET",
    }


def _train_argv() -> list[str]:
    return [
        str(PYTHON),
        "-B",
        "-m",
        "accelerate.commands.launch",
        "--num_processes",
        "1",
        "--num_machines",
        "1",
        "--mixed_precision",
        "no",
        "--dynamo_backend",
        "no",
        "--main_process_port",
        "29744",
        "gr00t/rl/train_agent_trl.py",
        "+exp=wbmanip/door_open_a2_pull_lstm",
        "+ablation=wbmanip/pull_v0_p0_canonical_smoke",
        "num_envs=64",
        "algo.trl.num_total_batches=50",
        "callbacks.model_save.save_frequency=25",
        "headless=true",
        "use_wandb=false",
        "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        "base_dir=logs_rl/a2_piper_full_stage_a2_pull/pull_v0_p0g",
        "project_name=a2_piper_full_stage_a2_pull",
        "experiment_name=pull_v0_p0g_canonical_64x50",
        f"experiment_dir={TRAIN_ROOT}",
        f"+device=cuda:{PHYSICAL_GPU}",
    ]


def _reload_argv() -> list[str]:
    eval_output = RELOAD_ROOT / "eval"
    hydra_root = RELOAD_ROOT / "hydra"
    return [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"checkpoint={CHECKPOINT}",
        "checkpoint_load_mode=full",
        "+auto_load_latest=false",
        "+num_envs=1",
        "+seed=0",
        "+headless=true",
        "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=false",
        "algo.config.eval.save_goal_reached_only=false",
        "algo.config.eval.save_trajectories=false",
        "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=1",
        "+simulator.config.render_results=false",
        "+simulator.config.cameras.enable_cameras=false",
        f"eval_output_dir={eval_output}",
        f"eval_log_dir={hydra_root}",
        f"env.config.save_rendering_dir={RELOAD_ROOT / 'renderings'}",
        f"+device=cuda:{PHYSICAL_GPU}",
        f"hydra.run.dir={hydra_root}",
    ]


def _load_existing_plan() -> dict | None:
    if not PLAN_PATH.exists():
        return None
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    declared_sha256 = plan.pop("plan_sha256")
    actual_sha256 = _canonical_sha256(plan)
    plan["plan_sha256"] = declared_sha256
    if declared_sha256 != actual_sha256:
        raise RuntimeError("Existing P0-G plan digest is invalid")
    if _sha256(CONFIG_PATH) != plan["config_sha256"]:
        raise RuntimeError("P0-G ablation config changed after plan freeze")
    source = json.loads(SOURCE_FREEZE_PATH.read_text(encoding="utf-8"))
    if source["warm_checkpoint"]["sha256"] != plan["warm_checkpoint_sha256"]:
        raise RuntimeError("P0-G source-freeze binding changed")
    return plan


def prepare() -> dict:
    existing = _load_existing_plan()
    if existing is not None:
        return existing
    if TRAIN_ROOT.exists() or RELOAD_ROOT.exists():
        raise RuntimeError("P0-G output roots must not exist before plan freeze")
    source = json.loads(SOURCE_FREEZE_PATH.read_text(encoding="utf-8"))
    checkpoint = Path(source["warm_checkpoint"]["source_path_read_only"])
    if _sha256(checkpoint) != source["warm_checkpoint"]["sha256"]:
        raise RuntimeError("P0-G frozen warm checkpoint hash mismatch")
    env = _command_env()
    train_argv = _train_argv()
    reload_argv = _reload_argv()
    plan = {
        "schema_version": "pull_v0_p0g_canonical_smoke_plan_v1",
        "generated_at_hkt": _hkt_now(),
        "status": "READY",
        "base_sha": source["base_commit"],
        "warm_checkpoint_sha256": source["warm_checkpoint"]["sha256"],
        "config_path": _relative(CONFIG_PATH),
        "config_sha256": _sha256(CONFIG_PATH),
        "topology": {
            "num_envs": 64,
            "training_iterations": 50,
            "save_frequency": 25,
            "single_process": True,
        },
        "gpu_resource_lease": {
            "authorized_physical_devices": [2, 3],
            "selected_physical_device": PHYSICAL_GPU,
            "gpu7_compute_authorized": False,
        },
        "training": {
            "artifact_root": _relative(TRAIN_ROOT),
            "expected_checkpoint": _relative(CHECKPOINT),
            "argv": train_argv,
            "env": env,
            "command_sha256": _canonical_sha256({"argv": train_argv, "env": env}),
        },
        "reload": {
            "artifact_root": _relative(RELOAD_ROOT),
            "checkpoint": _relative(CHECKPOINT),
            "num_envs": 1,
            "episodes": 1,
            "argv": reload_argv,
            "env": env,
            "command_sha256": _canonical_sha256({"argv": reload_argv, "env": env}),
        },
        "acceptance": {
            "natural_training_exit": True,
            "finite_gradients_and_optimizer_state": True,
            "checkpoint_step_50_saved": True,
            "checkpoint_reload_natural_exit": True,
            "artifact_namespace_is_pull_only": True,
            "performance_threshold": "N/A",
        },
    }
    plan["plan_sha256"] = _canonical_sha256(plan)
    _write_json(PLAN_PATH, plan)
    return plan


def run(phase: str) -> int:
    plan = prepare()
    phase_plan = plan["training" if phase == "train" else "reload"]
    artifact_root = ROOT / phase_plan["artifact_root"]
    receipt_path = artifact_root / "process_receipt.json"
    if phase == "train":
        if artifact_root.exists():
            raise RuntimeError("Refusing to overwrite the P0-G training artifact root")
    else:
        if not CHECKPOINT.is_file():
            raise FileNotFoundError(CHECKPOINT)
        if artifact_root.exists():
            raise RuntimeError("Refusing to overwrite the P0-G reload artifact root")
    artifact_root.mkdir(parents=True)

    started_at = _hkt_now()
    process_env = os.environ.copy()
    process_env.pop("CUDA_VISIBLE_DEVICES", None)
    process_env.update({
        key: value for key, value in phase_plan["env"].items()
        if key != "CUDA_VISIBLE_DEVICES"
    })
    result = subprocess.run(phase_plan["argv"], cwd=ROOT, env=process_env, check=False)
    expected_output = CHECKPOINT if phase == "train" else artifact_root / "eval/metrics_eval.json"
    status = "PASS" if result.returncode == 0 and expected_output.is_file() else "FAIL"
    receipt = {
        "schema_version": "pull_v0_p0g_process_receipt_v1",
        "phase": phase,
        "started_at_hkt": started_at,
        "ended_at_hkt": _hkt_now(),
        "natural_exit": True,
        "exit_code": result.returncode,
        "status": status,
        "plan_sha256": plan["plan_sha256"],
        "command_sha256": phase_plan["command_sha256"],
        "physical_gpu": PHYSICAL_GPU,
        "expected_output": _relative(expected_output),
        "expected_output_sha256": _sha256(expected_output) if expected_output.is_file() else None,
    }
    _write_json(receipt_path, receipt)
    return result.returncode if status == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--phase", choices=("train", "reload"))
    args = parser.parse_args()
    plan = prepare()
    if args.prepare_only:
        print(json.dumps(plan, indent=2))
        return 0
    if args.phase is None:
        parser.error("--phase is required unless --prepare-only is used")
    return run(args.phase)


if __name__ == "__main__":
    raise SystemExit(main())
