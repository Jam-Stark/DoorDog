"""Generate and run isolated seven-cell 64x50 R1 smoke commands."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    CHECKPOINT_PATH,
    GROUPS,
    PLAN_ID,
    R1Error,
    R1_LAUNCHER_ROOT,
    R1_SMOKE_ROOT,
    POLICY_LEARNABILITY_PASS,
    STATIC_PASS,
    RUNTIME_PASS,
    RUNTIME_SEMANTIC_PASS,
    atomic_create_json,
    device_env,
    load_json,
    validate_gpu,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_smoke_launcher_v3"


def _validate_wandb_mode(value: str) -> str:
    if value not in ("online", "offline"):
        raise R1Error("WANDB_MODE must be explicitly online or offline")
    return value


def _validate_chain(
    *,
    repo_root: Path,
    chain_artifacts: Mapping[str, Path],
) -> dict[str, Any]:
    required = ("preflight", "semantic", "pilot")
    missing = [name for name in required if name not in chain_artifacts]
    if missing:
        raise R1Error(f"smoke requires chain artifacts: missing {missing}")
    expected_paths = {
        "preflight": repo_root / "logs_eval/base_v20_R1/preflight/R1_SCIENTIFIC_MANIFEST.json",
        "semantic": repo_root / "logs_eval/base_v20_R1/semantic/semantic_admission.json",
        "pilot": repo_root / "logs_eval/base_v20_R1/pilot/pilot_adjudication.json",
    }
    payloads: dict[str, Any] = {}
    for name in required:
        path = Path(chain_artifacts[name]).resolve()
        if path != expected_paths[name].resolve() or not path.is_file() or path.is_symlink():
            raise R1Error(f"smoke chain artifact path is not canonical for {name}: {path}")
        payload = load_json(path)
        if not isinstance(payload, Mapping) or payload.get("plan_id") != PLAN_ID:
            raise R1Error(f"smoke chain artifact provenance mismatch: {path}")
        payloads[name] = payload
    if payloads["preflight"].get("status") != STATIC_PASS:
        raise R1Error("smoke requires P0 STATIC PASS")
    if payloads["semantic"].get("status") != RUNTIME_SEMANTIC_PASS:
        raise R1Error("smoke requires P1 RUNTIME SEMANTIC PASS")
    if payloads["pilot"].get("status") != POLICY_LEARNABILITY_PASS:
        raise R1Error("smoke requires POLICY LEARNABILITY PASS pilot")
    if payloads["pilot"].get("formal_training_ready") is not False:
        raise R1Error("pilot must not grant formal training readiness")
    return payloads


def _canonical_group_root(repo_root: Path, group: str, timestamp: str) -> Path:
    if not isinstance(timestamp, str) or not timestamp:
        raise R1Error("smoke timestamp is required")
    return (repo_root / R1_SMOKE_ROOT / timestamp / group).resolve()


def build_training_command(
    *,
    repo_root: Path,
    spec: Mapping[str, Any],
    accelerate_path: str = "accelerate",
    artifact_root: Path,
    timestamp: str,
    wandb_mode: str = "offline",
) -> dict[str, Any]:
    _validate_wandb_mode(wandb_mode)
    gpu = validate_gpu(spec["gpu"])
    group = str(spec["group"])
    expected = next((row for row in GROUPS if row["group"] == group), None)
    if expected is None or str(spec.get("config")) != expected["config"]:
        raise R1Error(f"unknown or mismatched R1 smoke group/config: {group}")
    canonical_root = _canonical_group_root(repo_root.resolve(), group, timestamp)
    if artifact_root.resolve() != canonical_root:
        raise R1Error("R1 smoke artifact root is not canonical")
    config = repo_root / "gr00t/rl/config/ablation/wbmanip" / expected["config"]
    if not config.is_file() or config.is_symlink():
        raise R1Error(f"missing or symlinked R1 smoke source config: {config}")
    port = 29720 + int(group[1:]) - 1
    command = [
        accelerate_path,
        "launch",
        "--num_processes",
        "1",
        "--main_process_port",
        str(port),
        "gr00t/rl/train_agent_trl.py",
        "+exp=wbmanip/door_open_a2_base_lstm",
        "+ablation=wbmanip/" + expected["config"][:-5],
        "num_envs=64",
        "algo.trl.num_total_batches=50",
        "callbacks.model_save.save_frequency=50",
        "headless=true",
        "simulator.config.cameras.enable_cameras=false",
        "checkpoint=" + CHECKPOINT_PATH,
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        "base_dir=" + R1_SMOKE_ROOT,
        "project_name=base_v20_R1",
        "experiment_name=" + group,
        "timestamp=" + timestamp,
        "experiment_dir=" + str(canonical_root),
        "device=cuda:" + str(gpu),
    ]
    env = device_env(gpu)
    env["WANDB_MODE"] = wandb_mode
    if "CUDA_VISIBLE_DEVICES" in env:
        raise R1Error("non-render smoke must not set CUDA_VISIBLE_DEVICES")
    return {
        "group": group,
        "gpu": gpu,
        "port": port,
        "env": env,
        "command": command,
        "num_envs": 64,
        "num_processes": 1,
        "batches": 50,
        "checkpoint": CHECKPOINT_PATH,
        "artifact_root": str(canonical_root),
        "timestamp": timestamp,
        "status": "COMMAND_BOUND",
    }


def generate_launcher(
    *,
    repo_root: Path,
    launcher_root: Path,
    artifact_root: Path,
    timestamp: str,
    wandb_mode: str = "offline",
    accelerate_path: str = "accelerate",
    chain_artifacts: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    root = repo_root.resolve()
    _validate_wandb_mode(wandb_mode)
    if chain_artifacts is None:
        raise R1Error("smoke launcher requires explicit P0/P1/pilot chain artifacts")
    chain = _validate_chain(repo_root=root, chain_artifacts=chain_artifacts)
    expected_launcher = (root / R1_LAUNCHER_ROOT / timestamp).resolve()
    expected_artifact = (root / R1_SMOKE_ROOT / timestamp).resolve()
    if launcher_root.resolve() != expected_launcher or artifact_root.resolve() != expected_artifact:
        raise R1Error("smoke launcher/output roots must be canonical")
    if launcher_root.exists() or artifact_root.exists():
        raise R1Error("R1 smoke launcher/output roots must not already exist")
    launcher_root.mkdir(parents=True)
    rows = []
    for spec in GROUPS:
        group_root = artifact_root / spec["group"]
        row = build_training_command(
            repo_root=root,
            spec=spec,
            accelerate_path=accelerate_path,
            artifact_root=group_root,
            timestamp=timestamp,
            wandb_mode=wandb_mode,
        )
        group_root.mkdir(parents=True)
        command_text = " ".join(row["command"])
        (launcher_root / (spec["group"] + ".command")).write_text(
            command_text + chr(10), encoding="utf-8"
        )
        wrapper = launcher_root / (spec["group"] + ".sh")
        wrapper.write_text(
            "#!/usr/bin/env bash" + chr(10)
            + "set -euo pipefail" + chr(10)
            + "marker=" + str(group_root / "ATTEMPT_CONSUMED.json") + chr(10)
            + 'test -f "$marker"' + chr(10)
            + "exec " + command_text + chr(10),
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        rows.append(row)
    launch = launcher_root / "launch_smoke.sh"
    launch.write_text(
        "#!/usr/bin/env bash" + chr(10)
        + "set -euo pipefail" + chr(10)
        + chr(10).join(
            "bash " + str(launcher_root / (row["group"] + ".sh")) for row in rows
        )
        + chr(10),
        encoding="utf-8",
    )
    launch.chmod(0o755)
    manifest = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": RUNTIME_PASS,
        "wandb_mode": wandb_mode,
        "chain_artifacts": {
            name: {
                "path": str(path),
                "status": chain[name].get("status"),
            }
            for name, path in chain_artifacts.items()
        },
        "topology": {
            "envs_per_group": 64,
            "batches": 50,
            "training_gpus": list(range(7)),
            "reserved_gpu": 7,
            "one_process_per_group": True,
        },
        "launcher_root": str(launcher_root),
        "artifact_root": str(artifact_root),
        "timestamp": timestamp,
        "groups": rows,
        "atomic_runner_required": True,
        "visibility_mask_forbidden": True,
    }
    write_json_no_overwrite(launcher_root / "manifest.json", manifest)
    return manifest


def run_smoke_group(
    *,
    command: Mapping[str, Any],
    group_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    expected_marker = group_root / "ATTEMPT_CONSUMED.json"
    marker = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "group": command["group"],
        "command": command["command"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pid_intent": "pending",
        "artifact_root": str(group_root.resolve()),
    }
    atomic_create_json(expected_marker, marker)
    process = subprocess.Popen(
        command["command"],
        cwd=repo_root,
        env={**os.environ, **command["env"]},
    )
    atomic_create_json(
        group_root / "child_pid.json",
        {
            "pid": process.pid,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "command": command["command"],
        },
    )
    return {"pid": process.pid, "marker": marker}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--launcher-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--wandb-mode", default="offline")
    args = parser.parse_args()
    generate_launcher(
        repo_root=args.repo_root,
        launcher_root=args.launcher_root,
        artifact_root=args.artifact_root,
        timestamp=args.timestamp,
        wandb_mode=args.wandb_mode,
    )
