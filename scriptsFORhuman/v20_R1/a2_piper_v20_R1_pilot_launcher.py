"""Build and atomically consume the single R1 learnability pilot attempt."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    CHECKPOINT_PATH,
    PLAN_ID,
    PLAN_SHA256,
    R1_PILOT_MARKER,
    R1Error,
    R1_FORMAL_ROOT,
    RUNTIME_SEMANTIC_PASS,
    STATIC_PASS,
    atomic_create_json,
    device_env,
    exact_digest,
    git_identity,
    load_json,
    sha256_file,
    validate_gpu,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_pilot_attempt_v3"
PILOT_CONFIG = "base_v20_R1_P2_G4_learnability_pilot.yaml"
URDF_PATH = "gr00t/rl/data/robots/A2_Piper/a2_piper.urdf"
PILOT_ROOT = R1_FORMAL_ROOT + "/P2_G4_learnability_pilot"
TIMESTAMP_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _validate_config(repo_root: Path, source_config: Path) -> None:
    expected = (repo_root / "gr00t/rl/config/ablation/wbmanip" / PILOT_CONFIG).resolve()
    if source_config.resolve() != expected:
        raise R1Error(f"pilot source config must be the exact P2 config: {expected}")
    if not source_config.is_file() or source_config.is_symlink():
        raise R1Error("pilot source config is missing or symlinked")


def _validate_gate_artifacts(root: Path) -> dict[str, dict[str, Any]]:
    preflight = root / "logs_eval/base_v20_R1/preflight/R1_SCIENTIFIC_MANIFEST.json"
    semantic = root / "logs_eval/base_v20_R1/semantic/semantic_admission.json"
    for path in (preflight, semantic):
        if not path.is_file() or path.is_symlink():
            raise R1Error(f"pilot gate artifact is missing or symlinked: {path}")
    preflight_payload = load_json(preflight)
    semantic_payload = load_json(semantic)
    if not isinstance(preflight_payload, Mapping) or preflight_payload.get("status") != STATIC_PASS:
        raise R1Error("pilot requires exact P0 STATIC PASS preflight artifact")
    if not isinstance(semantic_payload, Mapping) or semantic_payload.get("status") != RUNTIME_SEMANTIC_PASS:
        raise R1Error("pilot requires exact P1 RUNTIME SEMANTIC PASS artifact")
    exact_digest(preflight_payload.get("plan_sha256"), name="preflight.plan_sha256", length=64)
    if preflight_payload.get("plan_sha256") != PLAN_SHA256:
        raise R1Error("pilot preflight plan hash mismatch")
    if semantic_payload.get("plan_id") != PLAN_ID:
        raise R1Error("pilot semantic plan binding mismatch")
    return {
        "preflight": {"path": str(preflight), "sha256": sha256_file(preflight)},
        "semantic": {"path": str(semantic), "sha256": sha256_file(semantic)},
    }


def _canonical_artifact_root(root: Path, timestamp: str) -> Path:
    if not isinstance(timestamp, str) or TIMESTAMP_PATTERN.fullmatch(timestamp) is None:
        raise R1Error("pilot timestamp must match YYYYMMDDTHHMMSSZ")
    expected = (root / PILOT_ROOT / timestamp).resolve()
    return expected


def consume_attempt(
    *,
    artifact_root: Path,
    gpu: int,
    command: list[str],
    source_config: Path,
    repo_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    validate_gpu(gpu)
    _validate_config(root, source_config)
    if timestamp is None:
        raise R1Error("pilot attempt requires an explicit canonical timestamp")
    canonical_root = _canonical_artifact_root(root, timestamp)
    if artifact_root.resolve() != canonical_root:
        raise R1Error("pilot artifact_root is not the canonical timestamped pilot root")
    if "CUDA_VISIBLE_DEVICES" in (env or {}):
        raise R1Error("non-render pilot must not set CUDA_VISIBLE_DEVICES")
    gates = _validate_gate_artifacts(root)
    checkpoint = root / CHECKPOINT_PATH
    urdf = root / URDF_PATH
    if not checkpoint.is_file() or not urdf.is_file():
        raise R1Error("pilot provenance requires checkpoint and URDF")
    identity = git_identity(root)
    payload = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "plan_sha256": PLAN_SHA256,
        "checkpoint": {"path": CHECKPOINT_PATH, "sha256": sha256_file(checkpoint)},
        "urdf": {"path": URDF_PATH, "sha256": sha256_file(urdf)},
        "source_config": {"path": str(source_config), "sha256": sha256_file(source_config)},
        "git": identity,
        "gate_artifacts": gates,
        "gpu": gpu,
        "command": list(command),
        "env": dict(env or {}),
        "timestamp": timestamp,
        "artifact_root": str(canonical_root),
        "launcher_pid": os.getpid(),
        "pid_intent": "pending_spawn",
        "attempt_consumed": True,
    }
    marker = root / R1_PILOT_MARKER
    atomic_create_json(marker, payload)
    return payload


def build_command(
    *,
    repo_root: Path,
    config: Path,
    gpu: int,
    port: int,
    artifact_root: Path | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    root = repo_root.resolve()
    validate_gpu(gpu)
    if isinstance(port, bool) or not isinstance(port, int) or port <= 0 or port > 65535:
        raise R1Error("pilot port must be a valid positive TCP port")
    _validate_config(root, config)
    if artifact_root is None or timestamp is None:
        raise R1Error("pilot command requires canonical artifact_root and timestamp")
    canonical_root = _canonical_artifact_root(root, timestamp)
    if artifact_root.resolve() != canonical_root:
        raise R1Error("pilot artifact_root is not canonical")
    command = [
        "accelerate",
        "launch",
        "--num_processes",
        "1",
        "--main_process_port",
        str(port),
        "gr00t/rl/train_agent_trl.py",
        "+exp=wbmanip/door_open_a2_base_lstm",
        "+ablation=wbmanip/base_v20_R1_P2_G4_learnability_pilot",
        "num_envs=256",
        "algo.trl.num_total_batches=750",
        "callbacks.model_save.save_frequency=250",
        "headless=true",
        "simulator.config.cameras.enable_cameras=false",
        "checkpoint=" + CHECKPOINT_PATH,
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        "base_dir=" + R1_FORMAL_ROOT,
        "project_name=base_v20_R1",
        "experiment_name=P2_G4_learnability_pilot",
        "timestamp=" + timestamp,
        "experiment_dir=" + str(canonical_root),
        "device=cuda:" + str(gpu),
    ]
    env = device_env(gpu)
    env["WANDB_MODE"] = "offline"
    if "CUDA_VISIBLE_DEVICES" in env:
        raise R1Error("non-render pilot must not set CUDA_VISIBLE_DEVICES")
    return {
        "env": env,
        "command": command,
        "num_envs": 256,
        "batches": 750,
        "artifact_root": str(canonical_root),
        "timestamp": timestamp,
        "gpu": gpu,
        "config": str(config),
        "status": "COMMAND_BOUND",
    }


def run_pilot(
    *,
    repo_root: Path,
    artifact_root: Path,
    config: Path,
    gpu: int,
    port: int,
    timestamp: str,
) -> dict[str, Any]:
    root = repo_root.resolve()
    built = build_command(
        repo_root=root,
        config=config,
        gpu=gpu,
        port=port,
        artifact_root=artifact_root,
        timestamp=timestamp,
    )
    marker = consume_attempt(
        artifact_root=artifact_root,
        gpu=gpu,
        command=built["command"],
        source_config=config,
        repo_root=root,
        env=built["env"],
        timestamp=timestamp,
    )
    try:
        process = subprocess.Popen(
            built["command"],
            cwd=root,
            env={**os.environ, **built["env"]},
        )
    except OSError as exc:
        raise R1Error("pilot process failed to start after atomic consumption") from exc
    child = {"pid": process.pid, "started_utc": _timestamp(), "command": built["command"]}
    atomic_create_json(Path(artifact_root) / "child_pid.json", child)
    return {"marker": marker, "pid": process.pid, "command": built["command"], "env": built["env"]}


def _require_blocked_r1_cli_opt_in() -> None:
    if "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in __import__("os").environ:
        print(
            "R1 execution is blocked by default; set BASE_V20_ALLOW_BLOCKED_R1_EXECUTION explicitly to run historical tooling",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _require_blocked_r1_cli_opt_in()
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--gpu", type=int, required=True)
    parser.add_argument("--port", type=int, default=29730)
    parser.add_argument("--timestamp", required=True)
    args = parser.parse_args()
    run_pilot(
        repo_root=args.repo_root,
        artifact_root=args.artifact_root,
        config=args.config,
        gpu=args.gpu,
        port=args.port,
        timestamp=args.timestamp,
    )
