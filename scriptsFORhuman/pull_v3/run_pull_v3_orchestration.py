#!/usr/bin/env python3
"""Prepare or run bounded pull-v3 D0, smoke, wave, eval, and analysis phases."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V3_DIR = Path(__file__).resolve().parent
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN = V3_DIR / "run_pull_v3_training.py"
EVAL = V3_DIR / "run_pull_v3_eval_all_checkpoints.py"
ANALYSIS = V3_DIR / "analyze_pull_v3.py"
ANALYSIS_OUTPUTS = {
    "wave1": V3_DIR / "PULL_V3_ANALYSIS_WAVE1.json",
    "wave2": V3_DIR / "PULL_V3_ANALYSIS_WAVE2.json",
    "final": V3_DIR / "PULL_V3_ANALYSIS.json",
}
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
WARM_CHECKPOINT = (
    ROOT
    / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v2_W_wave2_relay_seed1/model_step_000750.pt"
)
ALLOWED_PHYSICAL_GPUS = (2, 3)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("d0_lite", "smoke", "wave1", "eval", "wave2", "seed2", "analyze"),
        required=True,
    )
    parser.add_argument("--gpu0", type=int, choices=ALLOWED_PHYSICAL_GPUS, default=2)
    parser.add_argument("--gpu1", type=int, choices=ALLOWED_PHYSICAL_GPUS, default=3)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2))
    parser.add_argument("--train-dir", type=Path)
    parser.add_argument("--checkpoint", type=Path, help="selected checkpoint for relay/seed2")
    parser.add_argument("--include-seed2", action="store_true")
    parser.add_argument("--analysis-wave", choices=tuple(ANALYSIS_OUTPUTS), default="final")
    parser.add_argument("--run", action="store_true", help="execute the prepared phase")
    return parser.parse_args()


def _check_gpu(gpu: int) -> None:
    if gpu not in ALLOWED_PHYSICAL_GPUS:
        raise ValueError(f"pull-v3 orchestration only permits physical GPU2/3; got GPU{gpu}.")


def _check_command_runtime() -> None:
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    for script in (TRAIN, EVAL, ANALYSIS):
        if not script.is_file():
            raise FileNotFoundError(script)


def _training_command(*, mode: str, seed: int, gpu: int, run_name: str, checkpoint: Path | None = None) -> list[str]:
    command = [
        str(PYTHON),
        str(TRAIN),
        "--mode",
        mode,
        "--seed",
        str(seed),
        "--gpu",
        str(gpu),
        "--run-name",
        run_name,
    ]
    if checkpoint is not None:
        command.extend(("--checkpoint", str(checkpoint)))
    return command


def _eval_command(*, seed: int, gpu: int, train_dir: Path, run_name: str) -> list[str]:
    return [
        str(PYTHON),
        str(EVAL),
        "--seed",
        str(seed),
        "--gpu",
        str(gpu),
        "--train-dir",
        str(train_dir),
        "--run-name",
        run_name,
    ]


def _prepared_phase(args: argparse.Namespace) -> list[list[str]]:
    _check_command_runtime()
    _check_gpu(args.gpu0)
    _check_gpu(args.gpu1)
    if args.phase == "d0_lite":
        return [[str(PYTHON), str(EVAL), "--d0-lite", "--gpu", str(args.gpu0)]]
    if args.phase == "smoke":
        return [_training_command(mode="smoke", seed=0, gpu=args.gpu0, run_name="pull_v3_T_smoke_seed0")]
    if args.phase == "wave1":
        if args.gpu0 == args.gpu1:
            raise ValueError("Wave1 requires disjoint physical GPU2 and GPU3 leases.")
        return [
            _training_command(mode="formal", seed=0, gpu=args.gpu0, run_name="pull_v3_T_wave1_seed0"),
            _training_command(mode="formal", seed=1, gpu=args.gpu1, run_name="pull_v3_T_wave1_seed1"),
        ]
    if args.phase == "eval":
        if args.seed is None or args.train_dir is None:
            raise ValueError("eval requires --seed and --train-dir")
        gpu = {0: args.gpu0, 1: args.gpu1, 2: args.gpu0}[args.seed]
        return [_eval_command(seed=args.seed, gpu=gpu, train_dir=args.train_dir, run_name=args.train_dir.name)]
    if args.phase == "wave2":
        if args.checkpoint is None:
            raise ValueError("Wave2 requires --checkpoint from the selected Wave1 checkpoint")
        checkpoint = args.checkpoint.resolve()
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        if args.gpu0 == args.gpu1:
            raise ValueError("Wave2 requires disjoint physical GPU2 and GPU3 leases.")
        return [
            _training_command(
                mode="formal",
                seed=0,
                gpu=args.gpu0,
                checkpoint=checkpoint,
                run_name="pull_v3_T_wave2_relay_seed0",
            ),
            _training_command(
                mode="formal",
                seed=1,
                gpu=args.gpu1,
                checkpoint=checkpoint,
                run_name="pull_v3_T_wave2_relay_seed1",
            ),
        ]
    if args.phase == "seed2":
        if args.checkpoint is None:
            raise ValueError("seed2 requires --checkpoint selected after a G4 decision")
        checkpoint = args.checkpoint.resolve()
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        return [
            _training_command(
                mode="formal",
                seed=2,
                gpu=args.gpu0,
                checkpoint=checkpoint,
                run_name="pull_v3_T_wave1_seed2",
            ),
            _eval_command(
                seed=2,
                gpu=args.gpu0,
                train_dir=TRAIN_ROOT / "pull_v3_T_wave1_seed2",
                run_name="pull_v3_T_wave1_seed2",
            ),
        ]
    output = ANALYSIS_OUTPUTS[args.analysis_wave]
    if output.exists():
        raise FileExistsError(f"refusing to overwrite analysis output: {output}")
    command = [str(PYTHON), str(ANALYSIS), "--output", str(output)]
    if args.include_seed2:
        command.append("--include-seed2")
    return [command]


def _with_run(command: list[str]) -> list[str]:
    return [*command, "--run"]


def _expected_paths(command: list[str]) -> list[Path]:
    if str(TRAIN) in command:
        try:
            run_name = command[command.index("--run-name") + 1]
        except (ValueError, IndexError) as exc:
            raise ValueError(f"training command missing --run-name: {command}") from exc
        return [TRAIN_ROOT / run_name / "model_step_000050.pt" if "--mode" in command and command[command.index("--mode") + 1] == "smoke" else TRAIN_ROOT / run_name / "model_step_000750.pt"]
    if str(EVAL) in command:
        if "--d0-lite" in command:
            return [ROOT / "logs_eval/a2_piper_pull_v3/D0_lite_seed1_step750/eval/metrics_eval.json"]
        try:
            run_name = command[command.index("--run-name") + 1]
        except (ValueError, IndexError) as exc:
            raise ValueError(f"eval command missing --run-name: {command}") from exc
        return [ROOT / "logs_eval/a2_piper_pull_v3" / f"{run_name}_step{step}/eval/metrics_eval.json" for step in (250, 500, 750)]
    if str(ANALYSIS) in command:
        try:
            return [Path(command[command.index("--output") + 1])]
        except (ValueError, IndexError) as exc:
            raise ValueError(f"analysis command missing --output: {command}") from exc
    return []


def _run_one(command: list[str]) -> None:
    prepared = list(command) if str(ANALYSIS) in command else _with_run(command)
    print("[pull-v3] launch:", " ".join(prepared))
    expected = _expected_paths(command)
    print("[pull-v3] expected:", *expected)
    process = subprocess.Popen(prepared, cwd=ROOT, env=os.environ.copy())
    print("[pull-v3] child pid:", process.pid)
    returncode = process.wait()
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, prepared)


def _run_wave(commands: list[list[str]]) -> None:
    processes = []
    for command in commands:
        prepared = _with_run(command)
        print("[pull-v3] concurrent launch:", " ".join(prepared))
        print("[pull-v3] expected:", *_expected_paths(command))
        process = subprocess.Popen(prepared, cwd=ROOT, env=os.environ.copy())
        print("[pull-v3] child pid:", process.pid)
        processes.append((prepared, process))
    results = [(prepared, process.wait()) for prepared, process in processes]
    failures = [(prepared, returncode) for prepared, returncode in results if returncode != 0]
    if failures:
        details = "; ".join(
            f"returncode={returncode} command={' '.join(prepared)}"
            for prepared, returncode in failures
        )
        raise RuntimeError(f"pull-v3 concurrent children failed after all were reaped: {details}")


def main() -> int:
    args = _parse_args()
    commands = _prepared_phase(args)
    for command in commands:
        print("[pull-v3] prepared:", " ".join(command))
        print("[pull-v3] expected:", *_expected_paths(command))
    if not args.run:
        return 0
    if args.phase == "wave1" or args.phase == "wave2":
        _run_wave(commands)
    elif args.phase == "seed2":
        _run_one(commands[0])
        _run_one(commands[1])
    else:
        for command in commands:
            _run_one(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
