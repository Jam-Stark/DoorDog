#!/usr/bin/env python3
"""Prepare or run Pull-v5.4 P3 cells and evidence-selected P4 continuations.

The explicit ``version`` parameter is retained for receipt naming; v5.4 is the
only admitted route and owns all new artifacts.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

try:
    from .pull_v5_4_gates import DEFAULT_DECISION, DEFAULT_REHEARSAL, DEFAULT_STAGE_A, require_chain, require_v5_4_downstream_gate
except ImportError:
    from pull_v5_4_gates import DEFAULT_DECISION, DEFAULT_REHEARSAL, DEFAULT_STAGE_A, require_chain, require_v5_4_downstream_gate


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
WARM_CHECKPOINT = TRAIN_ROOT / "pull_v4_B_wave1_seed1/model_step_000750.pt"
LOAD_RECEIPT_PATH = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_4_policy_only.json"
ALLOWED_GPUS = (4, 5, 6, 7)
CELLS = {
    "M_s0": ("pull_v5_M_s0", 0, 0.5),
    "M_s1": ("pull_v5_M_s1", 1, 0.5),
    "C_s0": ("pull_v5_C_s0", 0, 0.9),
    "C_s1": ("pull_v5_C_s1", 1, 0.9),
}
VERSIONS = ("5.4",)


def _version_tag(version: str) -> str:
    if version not in VERSIONS:
        raise ValueError(f"unsupported Pull version: {version!r}")
    return f"v{version.replace('.', '_')}"


def build_command(
    *, cell: str, gpu: int, checkpoint: Path, version: str = "5.4",
    allow_missing_checkpoint: bool = False, allow_g8_pure_a: bool = False,
    decision_path: Path = DEFAULT_DECISION, stage_a_path: Path = DEFAULT_STAGE_A,
    rehearsal_path: Path = DEFAULT_REHEARSAL, anchor_receipt: Path, gate_receipt: Path,
) -> tuple[list[str], dict[str, str], Path]:
    require_chain("anchor", decision_path=decision_path, stage_a_path=stage_a_path, rehearsal_path=rehearsal_path, anchor_path=anchor_receipt)
    require_v5_4_downstream_gate(gate_receipt, anchor_path=anchor_receipt)
    if cell not in CELLS:
        raise ValueError(f"unknown Pull-v5 cell: {cell!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"Pull-v5 training only permits physical GPU4-7; got GPU{gpu}")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    tag = _version_tag(version)
    config_name, seed, ratio = CELLS[cell]
    experiment_dir = TRAIN_ROOT / f"pull_{tag}_{cell}"
    if experiment_dir.exists():
        raise FileExistsError(f"refusing to overwrite Pull-v5 output: {experiment_dir}")
    command = [
        str(PYTHON), "-B", "-m", "accelerate.commands.launch",
        "--num_processes", "1", "--num_machines", "1", "--mixed_precision", "no",
        "--dynamo_backend", "no", "--main_process_port", str(29940 + gpu * 10 + seed),
        "--module", "gr00t.rl.train_agent_trl", "+exp=wbmanip/door_open_a2_pull_lstm",
        f"+ablation=wbmanip/{config_name}", f"seed={seed}", "num_envs=256",
        "algo.trl.num_total_batches=250", "callbacks.model_save.save_frequency=50",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true",
        "use_wandb=false", "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false", "algo.config.load_optimizer=false",
        f"checkpoint={checkpoint}", f"base_dir={TRAIN_ROOT}",
        "project_name=a2_piper_full_stage_a2_pull", f"experiment_name=pull_{tag}_{cell}",
        f"experiment_dir={experiment_dir}",
        "env.config.a2_v20_R1_plan_id=a2_piper_pull_v5_bridge_occupancy_and_release_persistence",
        "env.config.max_episode_length_s=24", "env.config.max_stage_time=[250,100,100,100,250,300]",
        "env.config.enable_staged_reset=true", "env.config.staged_reset_max_samples_per_stage=200",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=true",
        f"env.config.a2_pull_v5_stage4_bank_injection_ratio={ratio}",
        "env.config.a2_pull_v5_start_override_enabled=true",
        "env.config.a2_pull_v5_start_override_steps=50",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        f"env.config.a2_pull_v5_state_bank_allow_g8_pure_a={'true' if allow_g8_pure_a else 'false'}",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_{tag}_{cell}.json",
        "env.config.a2_pull_v5_reset_source=natural",
        "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }, experiment_dir


def build_p4_command(
    *, cell: str, gpu: int, checkpoint: Path, ratio: float,
    additional_batches: int = 250, version: str = "5.4", anneal_index: int = 0,
    allow_missing_checkpoint: bool = False, allow_g8_pure_a: bool = False,
    decision_path: Path = DEFAULT_DECISION, stage_a_path: Path = DEFAULT_STAGE_A,
    rehearsal_path: Path = DEFAULT_REHEARSAL, anchor_receipt: Path, gate_receipt: Path,
) -> tuple[list[str], dict[str, str], Path]:
    """Build one evidence-selected P4 continuation command.

    P4 reloads policy weights only and never an optimizer.  Callers can chain
    commands by feeding each output checkpoint into the next ratio in the
    pre-registered ``0.9 → 0.5 → 0.3`` anneal, or use one fixed ratio.
    """

    require_chain("anchor", decision_path=decision_path, stage_a_path=stage_a_path, rehearsal_path=rehearsal_path, anchor_path=anchor_receipt)
    require_v5_4_downstream_gate(gate_receipt, anchor_path=anchor_receipt)
    if cell not in CELLS:
        raise ValueError(f"unknown Pull-v5 cell: {cell!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"Pull-v5 training only permits physical GPU4-7; got GPU{gpu}")
    if not 0.0 < ratio <= 1.0:
        raise ValueError(f"P4 bank injection ratio must be in (0,1]; got {ratio}")
    if additional_batches <= 0:
        raise ValueError(f"P4 additional_batches must be positive; got {additional_batches}")
    if anneal_index < 0:
        raise ValueError(f"P4 anneal_index must be non-negative; got {anneal_index}")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    tag = _version_tag(version)
    config_name, seed, _base_ratio = CELLS[cell]
    experiment_name = f"pull_{tag}_p4_{cell}_r{str(ratio).replace('.', 'p')}_a{anneal_index}"
    experiment_dir = TRAIN_ROOT / experiment_name
    if experiment_dir.exists():
        raise FileExistsError(f"refusing to overwrite Pull-v5 P4 output: {experiment_dir}")
    command = [
        str(PYTHON), "-B", "-m", "accelerate.commands.launch",
        "--num_processes", "1", "--num_machines", "1", "--mixed_precision", "no",
        "--dynamo_backend", "no",
        "--main_process_port", str(29940 + gpu * 10 + seed + anneal_index + 20),
        "--module", "gr00t.rl.train_agent_trl", "+exp=wbmanip/door_open_a2_pull_lstm",
        f"+ablation=wbmanip/{config_name}", f"seed={seed}", "num_envs=256",
        f"algo.trl.num_total_batches={additional_batches}", "callbacks.model_save.save_frequency=50",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true",
        "use_wandb=false", "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false", "algo.config.load_optimizer=false",
        f"checkpoint={checkpoint}", f"base_dir={TRAIN_ROOT}",
        "project_name=a2_piper_full_stage_a2_pull", f"experiment_name={experiment_name}",
        f"experiment_dir={experiment_dir}",
        "env.config.a2_v20_R1_plan_id=a2_piper_pull_v5_bridge_occupancy_and_release_persistence",
        "env.config.max_episode_length_s=24", "env.config.max_stage_time=[250,100,100,100,250,300]",
        "env.config.enable_staged_reset=true", "env.config.staged_reset_max_samples_per_stage=200",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=true",
        f"env.config.a2_pull_v5_stage4_bank_injection_ratio={ratio}",
        "env.config.a2_pull_v5_start_override_enabled=true",
        "env.config.a2_pull_v5_start_override_steps=50",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        f"env.config.a2_pull_v5_state_bank_allow_g8_pure_a={'true' if allow_g8_pure_a else 'false'}",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/{experiment_name}.json",
        "env.config.a2_pull_v5_reset_source=natural", "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }, experiment_dir


def build_load_receipt_command(
    *, gpu: int, checkpoint: Path, receipt_path: Path, version: str = "5.4",
    allow_missing_checkpoint: bool = False,
    decision_path: Path = DEFAULT_DECISION, stage_a_path: Path = DEFAULT_STAGE_A,
    rehearsal_path: Path = DEFAULT_REHEARSAL, anchor_receipt: Path, gate_receipt: Path,
) -> tuple[list[str], dict[str, str], Path]:
    """Build the train-module policy-only initialization route without updates."""

    require_chain("anchor", decision_path=decision_path, stage_a_path=stage_a_path, rehearsal_path=rehearsal_path, anchor_path=anchor_receipt)
    require_v5_4_downstream_gate(gate_receipt, anchor_path=anchor_receipt)
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"Pull-v5 training only permits physical GPU4-7; got GPU{gpu}")
    tag = _version_tag(version)
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    receipt_path = receipt_path.resolve()
    if not receipt_path.is_relative_to(ROOT.resolve()):
        raise ValueError(f"Pull-v5 load receipt must remain inside the repository: {receipt_path}")
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite Pull-v5 load receipt: {receipt_path}")
    receipt_experiment_name = f"pull_{tag}_policy_only_load"
    receipt_experiment = TRAIN_ROOT / receipt_experiment_name
    if receipt_experiment.exists():
        raise FileExistsError(
            f"refusing to overwrite Pull-v5 load-receipt output: {receipt_experiment}"
        )
    receipt_relative = receipt_path.relative_to(ROOT.resolve())
    experiment_dir = receipt_experiment
    command = [
        str(PYTHON), "-B", "-m", "accelerate.commands.launch",
        "--num_processes", "1", "--num_machines", "1", "--mixed_precision", "no",
        "--dynamo_backend", "no", "--main_process_port", str(29940 + gpu * 10 + 9),
        "--module", "gr00t.rl.train_agent_trl", "+exp=wbmanip/door_open_a2_pull_lstm",
        "+ablation=wbmanip/pull_v5_M_s0", "seed=0", "num_envs=4",
        "algo.trl.num_total_batches=1", "checkpoint_load_mode=policy_only",
        "auto_load_latest=false", "headless=true", "use_wandb=false",
        "simulator.config.render_results=false", "simulator.config.cameras.enable_cameras=false",
        "algo.config.load_optimizer=false", f"checkpoint={checkpoint}", f"base_dir={TRAIN_ROOT}",
        "project_name=a2_piper_full_stage_a2_pull", f"experiment_name={receipt_experiment_name}",
        f"experiment_dir={experiment_dir}",
        "env.config.a2_v20_R1_plan_id=a2_piper_pull_v5_bridge_occupancy_and_release_persistence",
        "env.config.max_episode_length_s=24", "env.config.enable_staged_reset=true",
        "env.config.staged_reset_max_samples_per_stage=200",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=false",
        "env.config.a2_pull_v5_start_override_enabled=false",
        "env.config.a2_pull_v5_start_override_steps=50",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        "env.config.a2_pull_v5_state_bank_allow_g8_pure_a=false",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path={receipt_relative}",
        "+env.config.a2_pull_v5_load_receipt_only=true", "env.config.a2_pull_v5_reset_source=natural", "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }, experiment_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell", choices=tuple(CELLS))
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    parser.add_argument("--checkpoint", type=Path, default=WARM_CHECKPOINT)
    parser.add_argument("--version", choices=VERSIONS, default="5.4")
    parser.add_argument("--load-receipt-only", action="store_true")
    parser.add_argument("--receipt-path", type=Path, default=LOAD_RECEIPT_PATH)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--stage-a", type=Path, default=DEFAULT_STAGE_A)
    parser.add_argument("--rehearsal", type=Path, default=DEFAULT_REHEARSAL)
    parser.add_argument("--anchor-receipt", type=Path, required=True)
    parser.add_argument("--gate-receipt", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-g8-pure-a", action="store_true")
    parser.add_argument("--p4-ratio", type=float)
    parser.add_argument("--p4-additional-batches", type=int, default=250)
    parser.add_argument("--p4-anneal-index", type=int, default=0)
    args = parser.parse_args()
    checkpoint = args.checkpoint.resolve()
    if args.load_receipt_only:
        command, process_env, experiment_dir = build_load_receipt_command(
            gpu=args.gpu,
            checkpoint=checkpoint,
            receipt_path=args.receipt_path,
            version=args.version,
            allow_missing_checkpoint=args.dry_run,
            decision_path=args.decision, stage_a_path=args.stage_a,
            rehearsal_path=args.rehearsal, anchor_receipt=args.anchor_receipt, gate_receipt=args.gate_receipt,
        )
        expected = args.receipt_path.resolve()
    else:
        if args.cell is None:
            parser.error("--cell is required unless --load-receipt-only is selected")
        if args.p4_ratio is None:
            command, process_env, experiment_dir = build_command(
                cell=args.cell, gpu=args.gpu, checkpoint=checkpoint, version=args.version,
                allow_missing_checkpoint=args.dry_run, allow_g8_pure_a=args.allow_g8_pure_a,
                decision_path=args.decision, stage_a_path=args.stage_a,
                rehearsal_path=args.rehearsal, anchor_receipt=args.anchor_receipt, gate_receipt=args.gate_receipt,
            )
            expected = experiment_dir / "model_step_000250.pt"
        else:
            command, process_env, experiment_dir = build_p4_command(
                cell=args.cell, gpu=args.gpu, checkpoint=checkpoint, ratio=args.p4_ratio,
                additional_batches=args.p4_additional_batches, version=args.version,
                anneal_index=args.p4_anneal_index, allow_missing_checkpoint=args.dry_run,
                allow_g8_pure_a=args.allow_g8_pure_a,
                decision_path=args.decision, stage_a_path=args.stage_a,
                rehearsal_path=args.rehearsal, anchor_receipt=args.anchor_receipt, gate_receipt=args.gate_receipt,
            )
            expected = experiment_dir / f"model_step_{args.p4_additional_batches:06d}.pt"
    print("[pull-v5 training] command:", " ".join(command))
    print("[pull-v5 training] environment:", process_env)
    if args.load_receipt_only:
        print("[pull-v5 training] expected policy-only load receipt:", expected)
    else:
        print("[pull-v5 training] expected final checkpoint:", expected)
    if not args.run:
        return 0
    experiment_dir.mkdir(parents=True, exist_ok=False)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with (experiment_dir / "runner.log").open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        return result.returncode
    if args.load_receipt_only:
        if not expected.is_file():
            raise RuntimeError(f"load-receipt route exited without required receipt: {expected}")
    elif not expected.is_file():
        raise RuntimeError(f"training exited without required checkpoint: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
