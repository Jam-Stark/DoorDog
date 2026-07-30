"""Queue exact ten hash-bound M22 checkpoints per R1 group."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    GROUPS,
    PLAN_ID,
    R1Error,
    R1_ARTIFACT_ROOT,
    R1_FORMAL_ROOT,
    RUNTIME_PASS,
    device_env,
    exact_digest,
    validate_gpu,
)

SCHEMA = "a2_piper_v20_R1_m22_candidate_manifest_v3"
STEPS = tuple(range(250, 2501, 250))


class M22QueueError(R1Error):
    pass


def sha256_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise M22QueueError(f"missing or symlinked checkpoint: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(
    run_dir: Path,
    *,
    group: str,
    run_id: str | None = None,
    checkpoint_sha256: str | None = None,
    config_sha256: str | None = None,
) -> dict[str, Any]:
    expected_groups = {row["group"] for row in GROUPS}
    if group not in expected_groups:
        raise M22QueueError(f"unknown R1 group: {group}")
    if not run_dir.is_dir() or run_dir.is_symlink():
        raise M22QueueError(f"missing formal run directory: {run_dir}")
    if not isinstance(run_id, str) or not run_id:
        raise M22QueueError("M22 run_id is required")
    if config_sha256 is None:
        raise M22QueueError("M22 manifest requires exact config_sha256 binding")
    exact_digest(config_sha256, name="M22 config_sha256", length=64)
    candidates = []
    seen = set()
    for step in STEPS:
        path = run_dir / ("model_step_" + f"{step:06d}" + ".pt")
        digest = sha256_file(path)
        resolved = path.resolve()
        if resolved in seen:
            raise M22QueueError("M22 checkpoint alias/duplicate detected")
        seen.add(resolved)
        candidates.append(
            {
                "candidate_id": group + ":step" + str(step),
                "step": step,
                "path": str(path),
                "sha256": digest,
                "group": group,
                "run_id": run_id,
                "config_sha256": config_sha256,
            }
        )
    if checkpoint_sha256 is not None:
        exact_digest(checkpoint_sha256, name="M22 checkpoint_sha256", length=64)
        if any(row["sha256"] == checkpoint_sha256 for row in candidates):
            raise M22QueueError("run-level checkpoint binding cannot equal a candidate alias")
    return {
        "schema": SCHEMA,
        "status": RUNTIME_PASS,
        "plan_id": PLAN_ID,
        "group": group,
        "run_id": run_id,
        "run_root": str(run_dir.resolve()),
        "config_sha256": config_sha256,
        "steps": list(STEPS),
        "candidates": candidates,
        "last_pt_present_but_excluded": (run_dir / "last.pt").exists(),
        "exact_candidate_count": 10,
    }


def build_eval_command(
    checkpoint: Path,
    output_dir: Path,
    *,
    gpu: int | str,
    seed: int = 0,
    group: str | None = None,
    config: str | None = None,
    config_sha256: str | None = None,
) -> dict[str, Any]:
    gpu = validate_gpu(gpu)
    if output_dir.exists():
        raise M22QueueError(f"evaluation artifact root already exists: {output_dir}")
    if not checkpoint.is_file() or checkpoint.is_symlink():
        raise M22QueueError(f"evaluation checkpoint missing or symlinked: {checkpoint}")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise M22QueueError("M22 evaluation seed must be a non-negative integer")
    if group not in {row["group"] for row in GROUPS}:
        raise M22QueueError("M22 eval command requires a canonical group")
    if config is None or config_sha256 is None:
        raise M22QueueError("M22 eval command requires config path and hash binding")
    exact_digest(config_sha256, name="M22 config_sha256", length=64)
    expected_output_prefix = "logs_eval/base_v20_R1/m22/" + str(group)
    if expected_output_prefix not in str(output_dir).replace("\\", "/"):
        raise M22QueueError("M22 output directory is not canonical")
    command = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        "--device",
        "cuda:" + str(gpu),
        "+exp=wbmanip/door_open_a2_base_lstm",
        "+ablation=wbmanip/" + config.removesuffix(".yaml"),
        "checkpoint=" + str(checkpoint),
        "checkpoint_sha256=" + sha256_file(checkpoint),
        "config_sha256=" + config_sha256,
        "seed=" + str(seed),
        "num_envs=16",
        "eval_output_dir=" + str(output_dir),
    ]
    env = device_env(gpu)
    if "CUDA_VISIBLE_DEVICES" in env:
        raise M22QueueError("non-render M22 must not set CUDA_VISIBLE_DEVICES")
    return {
        "status": RUNTIME_PASS,
        "plan_id": PLAN_ID,
        "env": env,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "config_sha256": config_sha256,
        "seed": seed,
        "group": group,
        "output_dir": str(output_dir),
        "command": command,
        "device": "cuda:" + str(gpu),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--group", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args()
    print(
        build_manifest(
            args.run_dir,
            group=args.group,
            run_id=args.run_id,
            config_sha256=args.config_sha256,
        )
    )
