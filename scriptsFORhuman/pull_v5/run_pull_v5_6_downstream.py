#!/usr/bin/env python3
"""Generate the conditional Pull-v5.6 P3/P4, dual-DV, and render matrix.

The command builder reuses the established batch/checkpoint mechanics while
using only the v5.6 formal plan id.  Specialist activation is explicit in the
anchor/door runner and explicitly disabled in every downstream command.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ALLOWED_GPUS = (4, 5, 6, 7)
PLAN_ID = "a2_piper_pull_v5_6_formal_bridge"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_pull_v5_6_formal"
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_formal"
P3_CELLS = (("M_s0", 4, 0.5), ("M_s1", 5, 0.5), ("C_s0", 6, 0.9), ("C_s1", 7, 0.9))


def _cuda_env(gpu: int) -> dict[str, str]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"downstream work is restricted to GPU4-7; got GPU{gpu}")
    env = dict(os.environ)
    env.update({"CUDA_VISIBLE_DEVICES": str(gpu), "HYDRA_FULL_ERROR": "1", "WANDB_MODE": "offline"})
    return env


def _command(*parts: object) -> list[str]:
    return [str(part) for part in parts]


def _assert_no_specialist(command: list[str], *, phase: str) -> None:
    text = " ".join(command)
    required = (
        f"+env.config.a2_v20_R1_plan_id={PLAN_ID}",
        "algo.config.load_optimizer=false",
        "env.config.hold_specialist_active=false",
        "env.config.specialist_checkpoint=null",
        "algo.config.scientific_denominator_included=false",
        "+algo.config.invariant12_prime=null",
        f"+env.config.formal_downstream_phase={phase}",
    )
    for item in required:
        if item not in text:
            raise AssertionError(f"downstream command is missing {item!r}")
    if "v5_2" in text or "v5_4" in text or "scheduler" in text.lower():
        raise AssertionError("downstream command contains a legacy v5.2/v5.4 plan or scheduler")


def build_p3_command(*, cell: str, gpu: int, ratio: float, seed: int, output_dir: Path) -> dict[str, Any]:
    if (cell, gpu, ratio) not in P3_CELLS:
        raise ValueError(f"unknown P3 cell tuple: {(cell, gpu, ratio)!r}")
    command = _command(
        PYTHON,
        "-B",
        "-m",
        "gr00t.rl.train_agent_trl",
        "+exp=wbmanip/pull_v5_6_hold_specialist",
        f"seed={seed}",
        "num_envs=256",
        "headless=true",
        "use_wandb=false",
        "checkpoint=null",
        "checkpoint_load_mode=full",
        "algo.trl.num_total_batches=250",
        "algo.config.num_learning_iterations=250",
        "algo.config.load_optimizer=false",
        "algo.config.save_interval=50",
        "callbacks.model_save.save_frequency=50",
        "algo.config.use_a2_base=true",
        "algo.config.specialist_terminal_only=true",
        "algo.config.scientific_denominator_included=false",
        "+algo.config.invariant12_prime=null",
        "+env.config.a2_v20_R1_plan_id=" + PLAN_ID,
        "env.config.hold_specialist_active=false",
        "env.config.specialist_checkpoint=null",
        "+env.config.formal_downstream_phase=P3",
        f"+env.config.formal_occupancy_ratio={ratio}",
        f"experiment_dir={output_dir}",
        "+device=cuda:0",
    )
    _assert_no_specialist(command, phase="P3")
    return {
        "kind": "P3",
        "cell": cell,
        "gpu": gpu,
        "seed": seed,
        "occupancy_ratio": ratio,
        "num_envs": 256,
        "batches": 250,
        "save_frequency": 50,
        "load_optimizer": False,
        "output_dir": str(output_dir),
        "command": command,
        "shell": shlex.join(command),
    }


def build_p4_command(*, cell: str, gpu: int, ratio: float, checkpoint: Path, output_dir: Path, additional_batches: int = 250) -> dict[str, Any]:
    if cell not in {name for name, _gpu, _ratio in P3_CELLS}:
        raise ValueError(f"unknown P4 cell {cell!r}")
    if additional_batches <= 0:
        raise ValueError("P4 additional_batches must be positive")
    command = _command(
        PYTHON,
        "-B",
        "-m",
        "gr00t.rl.train_agent_trl",
        "+exp=wbmanip/pull_v5_6_hold_specialist",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=full",
        "auto_load_latest=false",
        "seed=0",
        "num_envs=256",
        "headless=true",
        "use_wandb=false",
        f"algo.trl.num_total_batches={additional_batches}",
        f"algo.config.num_learning_iterations={additional_batches}",
        "algo.config.load_optimizer=false",
        "algo.config.save_interval=50",
        "callbacks.model_save.save_frequency=50",
        "algo.config.use_a2_base=true",
        "algo.config.specialist_terminal_only=true",
        "algo.config.scientific_denominator_included=false",
        "+algo.config.invariant12_prime=null",
        "+env.config.a2_v20_R1_plan_id=" + PLAN_ID,
        "env.config.hold_specialist_active=false",
        "env.config.specialist_checkpoint=null",
        "+env.config.formal_downstream_phase=P4",
        f"+env.config.formal_occupancy_ratio={ratio}",
        f"experiment_dir={output_dir}",
        "+device=cuda:0",
    )
    _assert_no_specialist(command, phase="P4")
    return {
        "kind": "P4",
        "cell": cell,
        "gpu": gpu,
        "occupancy_ratio": ratio,
        "checkpoint": str(checkpoint),
        "additional_batches": additional_batches,
        "load_optimizer": False,
        "output_dir": str(output_dir),
        "command": command,
        "shell": shlex.join(command),
    }


def build_dual_eval_command(*, source: str, checkpoint: Path, output_dir: Path, gpu: int = 4) -> dict[str, Any]:
    if source not in {"canonical", "natural"}:
        raise ValueError(f"dual eval source must be canonical or natural, got {source!r}")
    command = _command(
        PYTHON,
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        "+exp=wbmanip/pull_v5_6_hold_specialist_eval",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=full",
        "auto_load_latest=false",
        "num_envs=16",
        "seed=0",
        "headless=true",
        "use_wandb=false",
        "algo.config.load_optimizer=false",
        "algo.config.specialist_terminal_only=true",
        "algo.config.scientific_denominator_included=false",
        "+algo.config.invariant12_prime=null",
        "+env.config.a2_v20_R1_plan_id=" + PLAN_ID,
        "env.config.hold_specialist_active=false",
        "env.config.specialist_checkpoint=null",
        "+env.config.formal_downstream_phase=DV",
        f"+env.config.formal_reset_source={source}",
        f"eval_output_dir={output_dir}",
        f"hydra.run.dir={output_dir / 'hydra'}",
        "+device=cuda:0",
    )
    _assert_no_specialist(command, phase="DV")
    return {
        "kind": "dual_eval",
        "source": source,
        "rows": 16,
        "specialist_active": False,
        "checkpoint": str(checkpoint),
        "gpu": gpu,
        "output_dir": str(output_dir),
        "command": command,
        "shell": shlex.join(command),
    }


def build_render_command(*, source: str, checkpoint: Path, output_dir: Path, gpu: int = 4) -> dict[str, Any]:
    if source not in {"canonical", "natural"}:
        raise ValueError(f"render source must be canonical or natural, got {source!r}")
    command = build_dual_eval_command(
        source=source,
        checkpoint=checkpoint,
        output_dir=output_dir,
        gpu=gpu,
    )["command"]
    command = command + ["simulator.config.render_results=true", "simulator.config.cameras.enable_cameras=true"]
    return {
        "kind": "render",
        "source": source,
        "gpu": gpu,
        "output_dir": str(output_dir),
        "command": command,
        "shell": shlex.join(command),
    }


def build_matrix(*, checkpoint: Path = TRAIN_ROOT / "M_s0" / "model_step_000250.pt") -> list[dict[str, Any]]:
    records = [
        build_p3_command(cell=cell, gpu=gpu, ratio=ratio, seed=seed, output_dir=TRAIN_ROOT / cell)
        for cell, gpu, ratio in P3_CELLS
        for seed in (0 if cell.endswith("s0") else 1,)
    ]
    records.append(
        build_p4_command(
            cell="M_s0",
            gpu=4,
            ratio=0.5,
            checkpoint=checkpoint,
            output_dir=TRAIN_ROOT / "P4_M_s0",
        )
    )
    records.extend(
        build_dual_eval_command(
            source=source,
            checkpoint=checkpoint,
            output_dir=EVAL_ROOT / "dual_eval" / source,
        )
        for source in ("canonical", "natural")
    )
    records.extend(
        build_render_command(
            source=source,
            checkpoint=checkpoint,
            output_dir=EVAL_ROOT / "render" / source,
        )
        for source in ("canonical", "natural")
    )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("p3", "p4", "dual_eval", "render", "matrix"), default="matrix")
    parser.add_argument("--cell", choices=tuple(name for name, _gpu, _ratio in P3_CELLS), default="M_s0")
    parser.add_argument("--source", choices=("canonical", "natural"), default="canonical")
    parser.add_argument("--checkpoint", type=Path, default=TRAIN_ROOT / "M_s0" / "model_step_000250.pt")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.phase == "p3":
        cell, gpu, ratio = next(item for item in P3_CELLS if item[0] == args.cell)
        records = [build_p3_command(cell=cell, gpu=gpu, ratio=ratio, seed=0 if cell.endswith("s0") else 1, output_dir=TRAIN_ROOT / cell)]
    elif args.phase == "p4":
        cell, gpu, ratio = next(item for item in P3_CELLS if item[0] == args.cell)
        records = [build_p4_command(cell=cell, gpu=gpu, ratio=ratio, checkpoint=args.checkpoint, output_dir=TRAIN_ROOT / f"P4_{cell}")]
    elif args.phase == "dual_eval":
        records = [build_dual_eval_command(source=args.source, checkpoint=args.checkpoint, output_dir=EVAL_ROOT / "dual_eval" / args.source)]
    elif args.phase == "render":
        records = [build_render_command(source=args.source, checkpoint=args.checkpoint, output_dir=EVAL_ROOT / "render" / args.source)]
    else:
        records = build_matrix(checkpoint=args.checkpoint)
    if args.run:
        if len(records) != 1:
            raise ValueError("--run requires one selected command")
        record = records[0]
        gpu = int(record["gpu"])
        result = subprocess.run(record["command"], env=_cuda_env(gpu), check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    print(json.dumps(records, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
