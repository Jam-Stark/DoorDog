#!/usr/bin/env python3
"""Build the v5 Stage-4 state bank from source-A and source-B snapshots.

The builder accepts two torch payloads with the same per-sample state layout.
Source A is concatenated first and must contain at least one ``bank_natural_e5``
sample.  Every sample carries a settle result; failed settle samples are
rejected before the bank is written.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

import torch


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt"
)
SCHEMA = "a2_piper_pull_v5_state_bank_v1"
MIN_SAMPLES = 64
ALLOWED_SOURCES = {"bank_natural_e5", "bank_constructed"}
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ALLOWED_GPUS = (4, 5, 6, 7)


def _load(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping):
        raise ValueError(f"state-bank source must be a mapping: {path}")
    return payload


def _source_cases(payload: Mapping[str, Any], label: str) -> tuple[int, list[str]]:
    if payload.get("schema") != "a2_piper_pull_v5_state_bank_source_v1":
        raise ValueError(f"{label}.schema must be a2_piper_pull_v5_state_bank_source_v1")
    provenance = payload.get("provenance")
    if not isinstance(provenance, (list, tuple)) or not provenance:
        raise ValueError(f"{label}.provenance must be a non-empty sequence")
    provenance = [str(item) for item in provenance]
    if any(item not in ALLOWED_SOURCES for item in provenance):
        raise ValueError(f"{label}.provenance contains an unsupported source")
    for name in (
        "robot_root_state",
        "robot_dof_pos",
        "robot_dof_vel",
        "door_root_state",
        "door_dof_pos",
        "door_dof_vel",
        "source_env_origin",
        "settle_valid",
        "settle_steps",
        "buffers",
    ):
        if name not in payload:
            raise ValueError(f"{label} is missing {name!r}")
    count = len(provenance)
    for name in (
        "robot_root_state",
        "robot_dof_pos",
        "robot_dof_vel",
        "door_root_state",
        "door_dof_pos",
        "door_dof_vel",
        "source_env_origin",
    ):
        value = payload[name]
        if not torch.is_tensor(value) or value.shape[0] != count:
            raise ValueError(f"{label}.{name} must have leading dimension {count}")
    settle_valid = payload["settle_valid"]
    settle_steps = payload["settle_steps"]
    if not torch.is_tensor(settle_valid) or tuple(settle_valid.shape) != (count,) or settle_valid.dtype != torch.bool:
        raise ValueError(f"{label}.settle_valid must be a bool vector of length {count}")
    if not torch.is_tensor(settle_steps) or tuple(settle_steps.shape) != (count,) or settle_steps.dtype not in (torch.int32, torch.int64):
        raise ValueError(f"{label}.settle_steps must be an integer vector of length {count}")
    if torch.any(settle_steps < 50):
        raise ValueError(f"{label}.settle_steps contains a sample below the 50-step settle minimum")
    if not bool(torch.all(settle_valid).item()):
        raise ValueError(f"{label} contains a failed settle sample; refusing to write the bank")
    buffers = payload["buffers"]
    if not isinstance(buffers, Mapping) or not buffers:
        raise ValueError(f"{label}.buffers must be a non-empty mapping")
    for name, value in buffers.items():
        if not torch.is_tensor(value) or value.shape[0] != count:
            raise ValueError(f"{label}.buffers[{name!r}] must have leading dimension {count}")
    return count, provenance


def build_bank(source_a: Path, source_b: Path, output: Path) -> dict[str, Any]:
    payload_a = _load(source_a)
    payload_b = _load(source_b)
    count_a, provenance_a = _source_cases(payload_a, "source_a")
    count_b, provenance_b = _source_cases(payload_b, "source_b")
    if provenance_a[0] != "bank_natural_e5":
        raise ValueError("source A must begin with bank_natural_e5 provenance")
    if any(item != "bank_natural_e5" for item in provenance_a):
        raise ValueError("source A must contain only bank_natural_e5 provenance")
    if any(item != "bank_constructed" for item in provenance_b):
        raise ValueError("source B must contain only bank_constructed provenance")
    if count_a + count_b < MIN_SAMPLES:
        raise ValueError(f"combined state bank has {count_a + count_b} samples; minimum is {MIN_SAMPLES}")
    if set(payload_a["buffers"]) != set(payload_b["buffers"]):
        raise ValueError("source A and source B registered-buffer keys differ")
    output_payload: dict[str, Any] = {
        "schema": SCHEMA,
        "robot_root_state": torch.cat((payload_a["robot_root_state"], payload_b["robot_root_state"]), dim=0),
        "robot_dof_pos": torch.cat((payload_a["robot_dof_pos"], payload_b["robot_dof_pos"]), dim=0),
        "robot_dof_vel": torch.cat((payload_a["robot_dof_vel"], payload_b["robot_dof_vel"]), dim=0),
        "door_root_state": torch.cat((payload_a["door_root_state"], payload_b["door_root_state"]), dim=0),
        "door_dof_pos": torch.cat((payload_a["door_dof_pos"], payload_b["door_dof_pos"]), dim=0),
        "door_dof_vel": torch.cat((payload_a["door_dof_vel"], payload_b["door_dof_vel"]), dim=0),
        "source_env_origin": torch.cat((payload_a["source_env_origin"], payload_b["source_env_origin"]), dim=0),
        "provenance": provenance_a + provenance_b,
        "buffers": {
            name: torch.cat((payload_a["buffers"][name], payload_b["buffers"][name]), dim=0)
            for name in payload_a["buffers"]
        },
    }
    # Keep the explicit source-A/source-B accounting next to the tensor bank.
    output_payload["provenance_counts"] = {
        "source_a_bank_natural_e5": provenance_a.count("bank_natural_e5"),
        "source_b_bank_constructed": provenance_b.count("bank_constructed"),
    }
    output_payload["closer_buckets"] = {
        "2.5-5": [],
        "5-9": [],
        "9-12": [],
    }
    hinge_forces = list(payload_a.get("hinge_drive_max_force_nm", [])) + list(payload_b.get("hinge_drive_max_force_nm", []))
    if hinge_forces:
        if len(hinge_forces) != len(output_payload["provenance"]):
            raise ValueError("hinge_drive_max_force_nm must have one value per bank sample")
        for index, force in enumerate(hinge_forces):
            value = float(force)
            bucket = "2.5-5" if 2.5 <= value < 5.0 else "5-9" if value < 9.0 else "9-12" if value <= 12.0 else None
            if bucket is not None:
                output_payload["closer_buckets"][bucket].append(index)
    output_payload["provenance_counts"]["total"] = len(output_payload["provenance"])
    if output.exists():
        raise FileExistsError(f"refusing to overwrite state bank: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(output_payload, output)
    result = {
        "schema": SCHEMA,
        "status": "PASS",
        "samples": len(output_payload["provenance"]),
        "source_a_samples": count_a,
        "source_b_samples": count_b,
        "output": str(output),
    }
    receipt_path = output.with_suffix(output.suffix + ".receipt.json")
    with receipt_path.open("x", encoding="utf-8") as stream:
        import json
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    result["receipt"] = str(receipt_path)
    return result


def build_runtime_source_command(
    *, source: str, output: Path, checkpoint: Path, gpu: int, allow_missing_checkpoint: bool = False
) -> tuple[list[str], dict[str, str], Path]:
    """Build an actor-backed source command without starting IsaacSim."""

    if source not in {"bank_natural_e5", "bank_constructed"}:
        raise ValueError(f"unsupported runtime source: {source!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"runtime capture only permits physical GPU4-7; got GPU{gpu}")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite runtime source payload: {output}")
    relative_output = output.resolve().relative_to(ROOT.resolve())
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint.resolve()}", "checkpoint_load_mode=policy_only",
        "auto_load_latest=false", "num_envs=64", "seed=0", "headless=true",
        "use_wandb=false", "+ablation=wbmanip/pull_v5_M_s0",
        "algo.config.eval.num_eval_episodes=1", "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=64", "env.config.enable_staged_reset=true",
        "env.config.staged_reset_max_samples_per_stage=200",
        "+env.config.a2_pull_v5_bank_capture_only=true",
        "+env.config.a2_pull_v5_bank_capture_settle_valid=true",
        "+env.config.a2_pull_v5_bank_capture_settle_steps=50",
        f"+env.config.a2_pull_v5_bank_capture_provenance={source}",
        f"+env.config.a2_pull_v5_bank_capture_path={relative_output}",
        f"eval_output_dir={output.parent / (output.stem + '_eval')}",
        f"hydra.run.dir={output.parent / (output.stem + '_hydra')}",
        "+device=cuda:0",
    ]
    if source == "bank_constructed":
        command.append("env.config.staged_reset_ratios=[0.0,0.0,0.0,0.0,1.0,0.0]")
    run_env = {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "WANDB_MODE": "offline",
    }
    log_path = output.with_suffix(".runner.log")
    return command, run_env, log_path


def _capture_runtime_source(*, source: str, output: Path, checkpoint: Path, gpu: int) -> None:
    """Run the actor-backed source producer and require its exported payload."""

    command, process_env, log_path = build_runtime_source_command(
        source=source, output=output, checkpoint=checkpoint, gpu=gpu
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with log_path.open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"runtime {source} producer failed with exit code {result.returncode}; see {log_path}")
    if not output.is_file():
        raise RuntimeError(f"runtime {source} producer exited without state-bank payload: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-a", type=Path, required=True)
    parser.add_argument("--source-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-source-a", action="store_true")
    parser.add_argument("--run-source-b", action="store_true")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source_a = args.source_a.resolve()
    source_b = args.source_b.resolve()
    output = args.output.resolve()
    if not args.dry_run and (args.run_source_a or args.run_source_b):
        if args.checkpoint is None:
            raise ValueError("runtime source capture requires --checkpoint")
        if args.run_source_a:
            _capture_runtime_source(
                source="bank_natural_e5", output=source_a,
                checkpoint=args.checkpoint.resolve(), gpu=args.gpu,
            )
        if args.run_source_b:
            _capture_runtime_source(
                source="bank_constructed", output=source_b,
                checkpoint=args.checkpoint.resolve(), gpu=args.gpu,
            )
    if args.dry_run:
        if args.run_source_a or args.run_source_b:
            if args.checkpoint is None:
                raise ValueError("dry-run runtime source construction requires --checkpoint")
            for source, output_path, selected in (
                ("bank_natural_e5", source_a, args.run_source_a),
                ("bank_constructed", source_b, args.run_source_b),
            ):
                if selected:
                    command, _process_env, _log_path = build_runtime_source_command(
                        source=source,
                        output=output_path,
                        checkpoint=args.checkpoint.resolve(),
                        gpu=args.gpu,
                        allow_missing_checkpoint=True,
                    )
                    print(f"[pull-v5 state-bank] {source} command:", " ".join(command))
        print({"status": "DRY_RUN", "source_a": str(source_a), "source_b": str(source_b), "output": str(output), "minimum_samples": MIN_SAMPLES})
        return 0
    print(build_bank(source_a, source_b, output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
