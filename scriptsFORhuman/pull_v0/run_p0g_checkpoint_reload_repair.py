#!/usr/bin/env python3
"""Run the bounded four-environment P0-G checkpoint reload repair."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
TRAIN_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P0G_CANONICAL_SMOKE_PLAN_R2.json"
PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P0G_RELOAD_PLAN_R2.json"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v0_p0g/canonical_64x50"
CHECKPOINT = TRAIN_ROOT / "model_step_000050.pt"
TRAIN_RECEIPT = TRAIN_ROOT / "process_receipt.json"
OUTPUT_ROOT = ROOT / "logs_eval/a2_piper_pull_v0/p0g_checkpoint_reload"
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
PHYSICAL_GPU = 4


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


def _argv() -> list[str]:
    eval_output = OUTPUT_ROOT / "eval"
    hydra_root = OUTPUT_ROOT / "hydra"
    return [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"checkpoint={CHECKPOINT}",
        "checkpoint_load_mode=full",
        "+auto_load_latest=false",
        "+num_envs=4",
        "+seed=0",
        "+headless=true",
        "algo.config.eval.num_eval_episodes=4",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=false",
        "algo.config.eval.save_goal_reached_only=false",
        "algo.config.eval.save_trajectories=false",
        "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=4",
        "+simulator.config.render_results=false",
        "+simulator.config.cameras.enable_cameras=false",
        f"eval_output_dir={eval_output}",
        f"eval_log_dir={hydra_root}",
        f"env.config.save_rendering_dir={OUTPUT_ROOT / 'renderings'}",
        f"+device=cuda:{PHYSICAL_GPU}",
        f"hydra.run.dir={hydra_root}",
    ]


def _env_contract() -> dict[str, str]:
    return {
        "ACCELERATE_TORCH_DEVICE": f"cuda:{PHYSICAL_GPU}",
        "WANDB_MODE": "offline",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": "UNSET",
    }


def prepare() -> dict:
    train_plan = json.loads(TRAIN_PLAN_PATH.read_text(encoding="utf-8"))
    train_receipt = json.loads(TRAIN_RECEIPT.read_text(encoding="utf-8"))
    if train_receipt["status"] != "PASS" or train_receipt["exit_code"] != 0:
        raise RuntimeError("Reload repair requires a passing P0-G training receipt")
    if train_receipt["plan_sha256"] != train_plan["plan_sha256"]:
        raise RuntimeError("P0-G training receipt is not bound to the R2 plan")
    if _sha256(CHECKPOINT) != train_receipt["expected_output_sha256"]:
        raise RuntimeError("P0-G step-50 checkpoint hash changed before reload")
    argv = _argv()
    env = _env_contract()
    expected = {
        "schema_version": "pull_v0_p0g_checkpoint_reload_plan_v1",
        "generated_at_hkt": None,
        "status": "READY",
        "parent_training_plan_sha256": train_plan["plan_sha256"],
        "parent_training_receipt_sha256": _sha256(TRAIN_RECEIPT),
        "checkpoint": {
            "path": _relative(CHECKPOINT),
            "sha256": _sha256(CHECKPOINT),
        },
        "repair": {
            "failed_attempt": "logs_eval/a2_piper_pull_v0/p0g_checkpoint_reload_one_env_fail",
            "failure": "One eval environment could not be divided by the inherited four minibatches.",
            "bounded_change": "Use four eval environments and four first episodes; retain num_mini_batches=4 and all checkpoint/scientific semantics.",
        },
        "topology": {
            "num_envs": 4,
            "episodes": 4,
            "optimizer_updates": 0,
        },
        "gpu_resource_lease": {
            "authorized_physical_devices": [4, 5, 6],
            "selected_physical_device": 4,
            "gpu7_compute_authorized": False,
        },
        "artifact_root": _relative(OUTPUT_ROOT),
        "argv": argv,
        "env": env,
        "command_sha256": _canonical_sha256({"argv": argv, "env": env}),
    }
    if PLAN_PATH.exists():
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        declared_sha256 = plan.pop("plan_sha256")
        actual_sha256 = _canonical_sha256(plan)
        plan["plan_sha256"] = declared_sha256
        if declared_sha256 != actual_sha256:
            raise RuntimeError("Existing P0-G reload repair plan digest is invalid")
        for key, value in expected.items():
            if key != "generated_at_hkt" and plan[key] != value:
                raise RuntimeError(f"Existing P0-G reload repair plan changed at {key}")
        return plan
    expected["generated_at_hkt"] = _hkt_now()
    expected["plan_sha256"] = _canonical_sha256(expected)
    _write_json(PLAN_PATH, expected)
    return expected


def main() -> int:
    plan = prepare()
    if OUTPUT_ROOT.exists():
        raise RuntimeError("Refusing to overwrite the P0-G checkpoint reload root")
    OUTPUT_ROOT.mkdir(parents=True)
    started_at = _hkt_now()
    process_env = os.environ.copy()
    process_env.pop("CUDA_VISIBLE_DEVICES", None)
    process_env.update({
        key: value for key, value in plan["env"].items()
        if key != "CUDA_VISIBLE_DEVICES"
    })
    result = subprocess.run(plan["argv"], cwd=ROOT, env=process_env, check=False)
    metrics_path = OUTPUT_ROOT / "eval/metrics_eval.json"
    status = "PASS" if result.returncode == 0 and metrics_path.is_file() else "FAIL"
    receipt = {
        "schema_version": "pull_v0_p0g_checkpoint_reload_receipt_v1",
        "started_at_hkt": started_at,
        "ended_at_hkt": _hkt_now(),
        "natural_exit": True,
        "exit_code": result.returncode,
        "status": status,
        "plan_sha256": plan["plan_sha256"],
        "command_sha256": plan["command_sha256"],
        "physical_gpu": PHYSICAL_GPU,
        "checkpoint_sha256": _sha256(CHECKPOINT),
        "metrics_path": _relative(metrics_path),
        "metrics_sha256": _sha256(metrics_path) if metrics_path.is_file() else None,
    }
    _write_json(OUTPUT_ROOT / "process_receipt.json", receipt)
    return result.returncode if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
