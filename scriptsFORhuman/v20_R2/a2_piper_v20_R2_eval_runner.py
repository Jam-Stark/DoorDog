"""R2 evaluation producer: command identity and production record handoff."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence
from ._r2_common import R2Error, canonical_json, device_env, validate_device_contract, validate_gpu, write_json_exclusive
from ._r2_workflow import GROUPS, read_artifact, artifact_hash, ensure_group, parse_gpus, runtime_command, write_raw


def build_eval_command(mode: str, *, repo_root: Path, checkpoint: Path, config: Path,
                       physical_gpu: int, seed: int = 0, group: str | None = None) -> tuple[list[str], dict[str, str]]:
    if mode not in {"b0", "zero-shot"}:
        raise R2Error("evaluation mode must be b0 or zero-shot")
    if not checkpoint.is_file() or checkpoint.is_symlink():
        raise R2Error("evaluation checkpoint must be a regular file")
    if not config.is_file() or config.is_symlink():
        raise R2Error("evaluation config must be a regular file")
    if mode == "zero-shot":
        if group is None:
            raise R2Error("zero-shot command requires a group")
        ensure_group(group)
    argv = [sys.executable, "-B", "-m", "gr00t.rl.eval_agent_trl", "--config", str(config), "--checkpoint", str(checkpoint), "--seed", str(seed), "--r2-evidence", "true"]
    env = device_env(validate_gpu(physical_gpu), render=False)
    validate_device_contract(gpu=physical_gpu, render=False, argv=argv, env=env, app_launcher_device=env["ACCELERATE_TORCH_DEVICE"], accelerator_device=env["ACCELERATE_TORCH_DEVICE"])
    return argv, env


def validate_record_set(path: Path) -> dict[str, Any]:
    payload = read_artifact(path, schema="a2_piper_base_v20_R2_record_set_v1", producer_state="RECORD_SET_COMPLETE")
    records = payload.get("records")
    if not isinstance(records, list) or payload.get("record_count") != len(records):
        raise R2Error("record set record_count mismatch")
    return payload


def run_eval(*, mode: str, repo_root: Path, checkpoint: Path, config: Path, physical_gpus: Sequence[int], output_root: Path, seed: int = 0, group: str | None = None) -> dict[str, Any]:
    gpus = parse_gpus(physical_gpus)
    if mode == "b0" and len(gpus) != 3:
        raise R2Error("B0 requires physical GPUs 0,1,2")
    if mode == "zero-shot" and len(gpus) != 7:
        raise R2Error("zero-shot requires one physical GPU per canonical group")
    commands = []
    for gpu in gpus:
        argv, env = build_eval_command(mode, repo_root=repo_root, checkpoint=checkpoint, config=config, physical_gpu=gpu, seed=seed, group=group)
        commands.append({"argv": argv, "env": env, "physical_gpu": gpu})
    payload = {"schema": "a2_piper_base_v20_R2_training_attempt_v1", "producer_state": "COMMAND_PLANNED", "attempt_id": f"{mode}-seed{seed}", "group": group or "G1", "command": commands[0]["argv"], "env": commands[0]["env"], "source_lock_sha256": "0" * 64, "config_sha256": artifact_hash(config), "checkpoint_sha256": artifact_hash(checkpoint)}
    write_raw(output_root / "evaluation_command.json", payload, producer_state="COMMAND_PLANNED")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("b0", "zero-shot"))
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--parent-pass", type=Path, required=False)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--physical-gpus", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--group")
    args = parser.parse_args(argv)
    if args.parent_pass is not None:
        read_artifact(args.parent_pass)
    run_eval(mode=args.mode, repo_root=args.repo_root, checkpoint=args.checkpoint, config=args.config, physical_gpus=parse_gpus(args.physical_gpus), output_root=args.output_root, seed=args.seed, group=args.group)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
