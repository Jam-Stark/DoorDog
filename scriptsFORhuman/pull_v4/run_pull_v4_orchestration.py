#!/usr/bin/env python3
"""Fail-fast pull-v4 phase orchestrator with explicit stage barriers."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V4_DIR = Path(__file__).resolve().parent
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN = V4_DIR / "run_pull_v4_training.py"
EVAL = V4_DIR / "run_pull_v4_eval_all_checkpoints.py"
ANALYSIS = V4_DIR / "analyze_pull_v4.py"
ALLOWED_PHYSICAL_GPUS = (4, 5, 6, 7)
WAVE1 = (("A", 0, 4), ("A", 1, 5), ("B", 0, 6), ("B", 1, 7))
STEPS = (250, 500, 750)
ANALYSIS_OUTPUT = V4_DIR / "PULL_V4_ANALYSIS.json"
G6_ANALYSIS_OUTPUT = V4_DIR / "PULL_V4_G6_ANALYSIS.json"
D0_RECEIPT = V4_DIR / "D0_LITE_RECEIPT.json"
SMOKE_CHECKPOINT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_smoke_seed0/model_step_000050.pt"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("d0_lite", "smoke", "wave1", "eval", "analyze", "g6_eval", "g6_analyze", "relay", "seed2", "seed2_eval"),
        required=True,
    )
    parser.add_argument("--variant", choices=("A", "B"))
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def _training(variant: str, seed: int, gpu: int, *, mode: str = "formal", relay: bool = False, checkpoint: Path | None = None) -> list[str]:
    command = [str(PYTHON), str(TRAIN), "--variant", variant, "--mode", mode, "--seed", str(seed), "--gpu", str(gpu)]
    if relay:
        command.append("--relay")
    if checkpoint is not None:
        command.extend(("--checkpoint", str(checkpoint)))
    return command


def _eval_cell(
    variant: str,
    seed: int,
    gpu: int,
    step: int,
    *,
    family: str | None = None,
    g6_budget: bool = False,
) -> list[str]:
    train_name = family or f"pull_v4_{variant}_wave1_seed{seed}"
    train_dir = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull" / train_name
    command = [
        str(PYTHON), str(EVAL), "--variant", variant, "--seed", str(seed), "--gpu", str(gpu),
        "--step", str(step), "--train-dir", str(train_dir),
    ]
    if g6_budget:
        command.append("--g6-budget")
    return command


def _require_stage_pass(*, require_rule: str | None = None) -> None:
    if not ANALYSIS_OUTPUT.is_file():
        raise RuntimeError(f"stage barrier requires prior PASS analysis: {ANALYSIS_OUTPUT}")
    report = json.loads(ANALYSIS_OUTPUT.read_text(encoding="utf-8"))
    if report.get("status") != "PASS":
        raise RuntimeError(f"stage barrier requires analysis status PASS; got {report.get('status')!r}")
    if require_rule is not None:
        rule = report.get("g1_g11", {}).get(require_rule, {})
        if rule.get("status") != "TRIGGERED":
            raise RuntimeError(f"stage barrier requires {require_rule}=TRIGGERED; got {rule}")


def _require_d0_pass() -> None:
    if not D0_RECEIPT.is_file():
        raise RuntimeError(f"stage barrier requires D0 PASS receipt: {D0_RECEIPT}")
    receipt = json.loads(D0_RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("status") != "PASS":
        raise RuntimeError(f"stage barrier requires D0 status PASS; got {receipt.get('status')!r}")


def _require_smoke_pass() -> None:
    _require_d0_pass()
    if not SMOKE_CHECKPOINT.is_file():
        raise RuntimeError(f"stage barrier requires completed B smoke checkpoint: {SMOKE_CHECKPOINT}")


def _require_wave1_outputs() -> None:
    _require_smoke_pass()
    missing = [
        ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull" / f"pull_v4_{variant}_wave1_seed{seed}/model_step_{step:06d}.pt"
        for variant, seed, _gpu in WAVE1
        for step in STEPS
        if not (ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull" / f"pull_v4_{variant}_wave1_seed{seed}/model_step_{step:06d}.pt").is_file()
    ]
    if missing:
        raise RuntimeError(f"stage barrier requires all Wave1 step750 checkpoints; missing={missing}")


def _require_eval_outputs() -> None:
    _require_wave1_outputs()
    missing = [
        ROOT / "logs_eval/a2_piper_pull_v4" / f"pull_v4_{variant}_wave1_seed{seed}_step{step}/eval/{name}"
        for variant, seed, _gpu in WAVE1
        for step in STEPS
        for name in ("metrics_eval.json", "stage2_5_step_trace.json")
        if not (ROOT / "logs_eval/a2_piper_pull_v4" / f"pull_v4_{variant}_wave1_seed{seed}_step{step}/eval/{name}").is_file()
    ]
    if missing:
        raise RuntimeError(f"stage barrier requires complete eval evidence; missing={missing}")


def _require_g6_eval_barrier() -> None:
    _require_stage_pass(require_rule="G6")
    missing = [
        ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull" / f"pull_v4_B_wave1_seed{seed}/model_step_{step:06d}.pt"
        for seed in (0, 1)
        for step in STEPS
        if not (ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull" / f"pull_v4_B_wave1_seed{seed}/model_step_{step:06d}.pt").is_file()
    ]
    if missing:
        raise RuntimeError(f"G6 barrier requires exactly the six B Wave1 checkpoints; missing={missing}")


def _commands(phase: str, *, variant: str | None, checkpoint: Path | None, enforce_barrier: bool) -> list[list[str]]:
    for path in (PYTHON, TRAIN, EVAL, ANALYSIS):
        if not path.is_file():
            raise FileNotFoundError(path)
    if phase == "d0_lite":
        return [[str(PYTHON), str(EVAL), "--d0-lite", "--variant", "B", "--gpu", "4"]]
    if phase == "smoke":
        if enforce_barrier:
            _require_d0_pass()
        return [_training("B", 0, 6, mode="smoke")]
    if phase == "wave1":
        if enforce_barrier:
            _require_smoke_pass()
        return [_training(arm, seed, gpu) for arm, seed, gpu in WAVE1]
    if phase == "eval":
        if enforce_barrier:
            _require_wave1_outputs()
        commands = []
        for index, (arm, seed, _wave_gpu) in enumerate((
            (arm, seed, gpu) for arm, seed, gpu in WAVE1 for _step in STEPS
        )):
            step = STEPS[index % len(STEPS)]
            commands.append(_eval_cell(arm, seed, ALLOWED_PHYSICAL_GPUS[index % 4], step))
        return commands
    if phase == "analyze":
        if enforce_barrier:
            _require_eval_outputs()
        return [
            [str(PYTHON), str(ANALYSIS), "--input-root", str(ROOT / "logs_eval/a2_piper_pull_v4"), "--output", str(ANALYSIS_OUTPUT)]
        ]
    if phase == "g6_eval":
        if enforce_barrier:
            _require_g6_eval_barrier()
        return [
            _eval_cell("B", seed, ALLOWED_PHYSICAL_GPUS[index % 4], step, g6_budget=True)
            for index, (seed, step) in enumerate(
                ( (seed, step) for seed in (0, 1) for step in STEPS )
            )
        ]
    if phase == "g6_analyze":
        return [[str(PYTHON), str(ANALYSIS), "--g6-input", str(ROOT / "logs_eval/a2_piper_pull_v4"), "--output", str(G6_ANALYSIS_OUTPUT)]]
    if phase == "relay":
        if variant not in ("A", "B") or checkpoint is None:
            raise ValueError("relay requires --variant and the selected winning --checkpoint")
        if enforce_barrier:
            _require_stage_pass(require_rule="G1")
        return [_training(variant, seed, gpu, relay=True, checkpoint=checkpoint) for seed, gpu in ((0, 4), (1, 5))]
    if phase == "seed2":
        if variant not in ("A", "B") or checkpoint is None:
            raise ValueError("seed2 requires --variant and an explicit selected --checkpoint")
        if enforce_barrier:
            _require_stage_pass(require_rule="G4")
        return [_training(variant, 2, 4, relay=True, checkpoint=checkpoint)]
    if phase == "seed2_eval":
        if variant not in ("A", "B"):
            raise ValueError("seed2_eval requires --variant")
        family = f"pull_v4_{variant}_seed2"
        return [_eval_cell(variant, 2, 4, step, family=family) for step in STEPS]
    raise ValueError(f"unknown phase: {phase}")


def _run_concurrent(commands: list[list[str]]) -> int:
    processes = [subprocess.Popen([*command, "--run"], cwd=ROOT) for command in commands]
    statuses = [process.wait() for process in processes]
    return next((status for status in statuses if status != 0), 0)


def _run_eval_batches(commands: list[list[str]]) -> int:
    for start in range(0, len(commands), 4):
        status = _run_concurrent(commands[start : start + 4])
        if status != 0:
            return status
    return 0


def _run_d0(commands: list[list[str]]) -> int:
    status = _run_concurrent(commands)
    if status != 0:
        return status
    receipt_command = [
        str(PYTHON), str(ANALYSIS), "--d0-lite",
        "--input-root", str(ROOT / "logs_eval/a2_piper_pull_v4"),
        "--output", str(V4_DIR / "D0_LITE_RECEIPT.json"),
    ]
    return subprocess.run(receipt_command, cwd=ROOT, check=False).returncode


def main() -> int:
    args = _parse_args()
    checkpoint = args.checkpoint.resolve() if args.checkpoint is not None else None
    commands = _commands(args.phase, variant=args.variant, checkpoint=checkpoint, enforce_barrier=args.run)
    for command in commands:
        print("[pull-v4] prepared:", " ".join(command))
    if not args.run:
        return 0
    if args.phase in ("analyze", "g6_analyze"):
        return subprocess.run(commands[0], cwd=ROOT, check=False).returncode
    if args.phase == "d0_lite":
        return _run_d0(commands)
    if args.phase in ("eval", "g6_eval", "seed2_eval"):
        return _run_eval_batches(commands)
    return _run_concurrent(commands)


if __name__ == "__main__":
    raise SystemExit(main())
