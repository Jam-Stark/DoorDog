#!/usr/bin/env python3
"""Run the matched Gemini 335L single-camera pose sweep without training."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from gr00t.rl.utils.a2_camera_pose_sweep import derive_center_crop_intrinsics


DEFAULT_CHECKPOINT = Path(
    "logs_rl/a2_piper_student_distillation_v13_A_teacher-20260717_2103/"
    "model_step_003000.pt"
)
DEFAULT_CHECKPOINT_SHA256 = (
    "d576ca4bc6f596e45a8d744ca766164b374f8aba4409b06bcd7c460d6b057a36"
)
DEFAULT_ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Drive a base_v13_A teacher eval while one diagnostic camera is moved "
            "through matched same-step Gemini 335L pose candidates. No training occurs."
        )
    )
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--python", type=Path, default=DEFAULT_ISAACLAB_PYTHON)
    parser.add_argument("--gpu", type=int, choices=(0, 1), default=1)
    parser.add_argument("--num-envs", type=int, default=16)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def nominal_gemini_335l_crop_intrinsics() -> dict[str, object]:
    return derive_center_crop_intrinsics(
        native_width=1280,
        native_height=800,
        horizontal_fov_deg=94.0,
        vertical_fov_deg=68.0,
        crop_width=1280,
        crop_height=720,
        output_width=384,
        output_height=216,
    )


def build_eval_command(
    *,
    python_path: Path,
    checkpoint: Path,
    num_envs: int,
    output_dir: Path,
) -> list[str]:
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs < 2:
        raise ValueError(
            "num_envs must be an int >= 2 so eval does not trigger the unrelated "
            f"single-env ONNX export; got {num_envs!r}"
        )
    return [
        str(python_path),
        "gr00t/rl/eval_agent_trl.py",
        f"checkpoint={checkpoint}",
        "+camera_pose_sweep=gemini_335l_centerline",
        f"+num_envs={num_envs}",
        "+headless=true",
        "+use_wandb=false",
        "+multi_gpu=false",
        "++algo.config.num_mini_batches=1",
        "simulator.config.render_results=false",
        "env.config.save_rendering_dir=null",
        f"eval_output_dir={output_dir}",
        f"eval_log_dir={output_dir}",
        f"hydra.run.dir={output_dir / '.hydra'}",
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_base_v13_a_checkpoint(
    checkpoint: Path,
    expected_sha256: str = DEFAULT_CHECKPOINT_SHA256,
) -> str:
    actual_sha256 = sha256_file(checkpoint)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            "checkpoint is not the sealed base_v13_A Teacher; "
            f"expected_sha256={expected_sha256}, actual_sha256={actual_sha256}"
        )
    return actual_sha256


def prepare_writable_eval_input(
    *,
    output_dir: Path,
    checkpoint: Path,
) -> Path:
    config_path = checkpoint.parent / "config.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"checkpoint-adjacent config not found: {config_path}")

    output_dir.mkdir(parents=True, exist_ok=False)
    input_dir = output_dir / "_eval_input"
    input_dir.mkdir()
    runtime_checkpoint = input_dir / checkpoint.name
    shutil.copyfile(checkpoint, runtime_checkpoint)
    shutil.copyfile(config_path, input_dir / "config.yaml")
    if sha256_file(runtime_checkpoint) != sha256_file(checkpoint):
        raise RuntimeError("writable eval checkpoint copy failed SHA-256 verification")
    return runtime_checkpoint


def seal_summary(
    *,
    output_dir: Path,
    command: list[str],
    checkpoint: Path,
    metrics: dict[str, object],
    runtime_checkpoint: Path,
) -> Path:
    sweep = metrics.get("a2_camera_pose_sweep")
    if not isinstance(sweep, dict) or sweep.get("status") != "SWEEP_COMPLETE":
        raise RuntimeError("metrics_eval.json has no completed camera pose sweep")
    if sweep.get("training_performed") is not False:
        raise RuntimeError("camera pose sweep must explicitly report training_performed=false")
    checkpoint_sha256 = sha256_file(checkpoint)
    runtime_checkpoint_sha256 = sha256_file(runtime_checkpoint)
    if runtime_checkpoint_sha256 != checkpoint_sha256:
        raise RuntimeError("runtime checkpoint SHA-256 differs from sealed source")
    summary = {
        "schema_version": 1,
        "sealed_at_hkt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "SWEEP_COMPLETE",
        "training_performed": False,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "runtime_checkpoint": str(runtime_checkpoint),
        "runtime_checkpoint_sha256": runtime_checkpoint_sha256,
        "command": command,
        "spec_derived_intrinsics": nominal_gemini_335l_crop_intrinsics(),
        "sweep": sweep,
    }
    serialized = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    summary_path = output_dir / "camera_pose_sweep_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"refusing to overwrite sealed summary: {summary_path}")
    temporary_path = output_dir / "camera_pose_sweep_summary.json.tmp"
    with temporary_path.open("x", encoding="utf-8") as stream:
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())
    temporary_path.replace(summary_path)
    return summary_path

    verify_base_v13_a_checkpoint(checkpoint)

def main() -> int:
    args = parse_args()
    repository_root = REPOSITORY_ROOT
    checkpoint = (
        (repository_root / args.checkpoint).resolve()
        if not args.checkpoint.is_absolute()
        else args.checkpoint
    )
    output_dir = args.output_dir.resolve()
    python_path = args.python.resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"base_v13_A checkpoint not found: {checkpoint}")
    if not python_path.is_file():
        raise FileNotFoundError(f"IsaacLab Python not found: {python_path}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse camera sweep output directory: {output_dir}")
    runtime_checkpoint = output_dir / "_eval_input" / checkpoint.name
    command = build_eval_command(
        python_path=python_path,
        checkpoint=runtime_checkpoint,
        num_envs=args.num_envs,
        output_dir=output_dir,
    )
    if args.dry_run:
        print(json.dumps({"cuda_visible_devices": args.gpu, "command": command}, indent=2))
        return 0

    environment = os.environ.copy()
    prepared_checkpoint = prepare_writable_eval_input(
        output_dir=output_dir, checkpoint=checkpoint
    )
    if prepared_checkpoint != runtime_checkpoint:
        raise RuntimeError("prepared eval checkpoint path mismatch")
    environment["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    environment["HYDRA_FULL_ERROR"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(repository_root)
    if existing_pythonpath:
        environment["PYTHONPATH"] += os.pathsep + existing_pythonpath
    completed = subprocess.run(command, cwd=repository_root, env=environment, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"camera pose sweep eval failed with exit code {completed.returncode}; "
            f"partial output remains at {output_dir}"
        )
    metrics_path = output_dir / "metrics_eval.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"camera pose sweep did not produce {metrics_path}")
    with metrics_path.open("r", encoding="utf-8") as stream:
        metrics = json.load(stream)
    summary_path = seal_summary(
        output_dir=output_dir,
        command=command,
        checkpoint=checkpoint,
        metrics=metrics,
        runtime_checkpoint=runtime_checkpoint,
    )
    print(f"[CAMERA_POSE_SWEEP_SEALED] {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
