"""D1-FULL 64x10 bucket-plumbing PLAN/RUN/REDUCE orchestration.

This runner owns one bounded plumbing smoke.  It validates the R190
physics-first source, launches one exact Conda/IsaacLab command when requested,
and reduces one raw runtime record into the canonical receipt.  The receipt
proves sampler plumbing only; it never claims policy quality, D1 science, or
formal admission.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

try:
    from ._v23_common import REPO_ROOT, V23Error, read_json, write_json
except ImportError:  # direct invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23Error, read_json, write_json

from gr00t.rl.envs.door.a2_v23_d1_sampler import (
    BUCKET_NAMES,
    DEFAULT_RECEIPT_PATH,
    D1Sampler,
    RECEIPT_SCHEMA,
    RECEIPT_STATUS,
    load_d1_catalog,
)


TASK_ID = "V23-R211-D1-FULL-64X10"
REVISION = "C2"
CONFIG_PATH = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v23_d1_full_64x10_smoke.yaml"
CONFIG_OVERRIDE = "wbmanip/base_v23_d1_full_64x10_smoke"
PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
PHYSICAL_GPUS = (0, 1)
LOGICAL_DEVICE = "cuda:0"
NUM_ENVS = 64
NUM_BATCHES = 10
SAVE_FREQUENCY = 10
BUCKET_SEED = 0
VARIANT = "normal"
CANONICAL_ROOT = REPO_ROOT / "logs_eval/base_v23/p0/d1_full_64x10"
CANONICAL_RECEIPT_PATH = CANONICAL_ROOT / "d1_full_64x10_receipt.json"
CANONICAL_RUN_ROOT = REPO_ROOT / "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v23/d1_full_64x10"
CANONICAL_LAUNCHER_ROOT = REPO_ROOT / "logs_rl/launchers/base_v23/d1_full_64x10"
PLAN_SCHEMA = "a2_piper_v23_d1_full_64x10_plan_v1"
RAW_SCHEMA = "a2_piper_v23_d1_full_64x10_raw_v1"
RECEIPT_SCHEMA_D1 = "a2_piper_v23_d1_full_64x10_receipt_v1"
PASS_STATUS = "D1_FULL_64X10_BUCKET_PLUMBING_RUNTIME_VERIFIED"
INCOMPLETE_STATUS = "D1_FULL_64X10_BUCKET_PLUMBING_INCOMPLETE"
EXCLUDED_CLAIMS = (
    "NO_POLICY_QUALITY_CLAIM",
    "NO_D1_PHYSICS_ADJUDICATION_CLAIM",
    "NO_FORMAL_ADMISSION",
    "NO_RELEASE_RECEIPT",
)


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V23Error(f"{label} must be an object")
    return value


def _validate_bucket_counts(value: Any, *, label: str) -> dict[str, int]:
    counts = _mapping(value, label=label)
    if set(counts) != set(BUCKET_NAMES):
        raise V23Error(
            f"{label} must contain exactly the bucket keys {list(BUCKET_NAMES)!r}; "
            f"got {sorted(counts)!r}"
        )
    normalized = {}
    for bucket in BUCKET_NAMES:
        count = counts[bucket]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise V23Error(f"{label}[{bucket!r}] must be a non-negative integer; got {count!r}")
        normalized[bucket] = count
    if sum(normalized.values()) != NUM_ENVS:
        raise V23Error(
            f"{label} must sum to {NUM_ENVS}; got {sum(normalized.values())}"
        )
    return normalized


def _require_path(path: Path, *, label: str) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise V23Error(f"{label} must be a regular file: {path}")
    return path


def build_run_command(*, physical_gpu: int = 0, run_root: Path = CANONICAL_RUN_ROOT) -> tuple[list[str], dict[str, str]]:
    if physical_gpu not in PHYSICAL_GPUS:
        raise V23Error(f"physical GPU must be one of {PHYSICAL_GPUS}; got {physical_gpu}")
    _require_path(PROJECT_PYTHON, label="approved IsaacLab Python")
    _require_path(CONFIG_PATH, label="D1-FULL smoke config")
    _require_path(DEFAULT_RECEIPT_PATH, label="R190 physics-first receipt")
    run_root = Path(run_root).resolve()
    command = [
        "env",
        "CUDA_DEVICE_ORDER=PCI_BUS_ID",
        f"CUDA_VISIBLE_DEVICES={physical_gpu}",
        f"ACCELERATE_TORCH_DEVICE={LOGICAL_DEVICE}",
        "WANDB_MODE=disabled",
        f"PYTHONPATH={REPO_ROOT}",
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.train_agent_trl",
        "+exp=wbmanip/door_open_a2_base_lstm",
        f"+ablation={CONFIG_OVERRIDE}",
        f"++experiment_dir={run_root}",
        f"++output_dir={run_root / 'output'}",
        "++project_name=a2_piper_full_stage_a2_base_smoke",
        "++experiment_name=d1_full_64x10",
        "++v23_cell=G5",
        "++v23_seed=0",
        "++v23_initialization=v22_warm",
        "++v23_door_regime=D1",
        "++v23_posture_mode=FULL",
        "++v23_training_enabled=true",
        "++v23_formal_launchable=false",
        "++v23_contract_only=false",
        "++checkpoint=logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++seed=0",
        f"++num_envs={NUM_ENVS}",
        "++num_gpus=1",
        "++multi_gpu=false",
        "++headless=true",
        "++use_wandb=false",
        f"++algo.trl.num_total_batches={NUM_BATCHES}",
        "++algo.trl.report_to=none",
        "++algo.config.num_mini_batches=1",
        "++algo.config.a2_v23_d1_runtime_export=true",
        f"++algo.config.a2_v23_d1_runtime_raw_path={run_root / 'd1_full_64x10_raw.json'}",
        f"++callbacks.model_save.save_frequency={SAVE_FREQUENCY}",
        "++algo.config.rp0_enabled=false",
        "++algo.config.rp0_mask_indices=[3,4]",
        "++algo.config.rp0_neutral_value=0.0",
        "++env.config.a2_v23_d1_sampler_enabled=true",
        f"++env.config.a2_v23_d1_manifest_path={DEFAULT_RECEIPT_PATH}",
        f"++env.config.a2_v23_d1_receipt_path={DEFAULT_RECEIPT_PATH}",
        f"++env.config.a2_v23_d1_variant={VARIANT}",
        f"++env.config.a2_v23_d1_bucket_seed={BUCKET_SEED}",
        f"++env.config.a2_v23_d1_total_steps={NUM_BATCHES}",
        "++env.config.a2_v23_d1_global_step=0",
        "++env.config.a2_v23_d1_confirmed_e2_enabled=false",
        "++env.config.a2_v23_effort_profile_nm=40.0",
        "++env.config.a2_v23_effort_profile_source=P0_2_MEASURED_FREEZE",
        "++env.config.a2_v23_formal_launch=false",
        "++env.config.enable_staged_reset=true",
        "++env.config.staged_reset_ratios=[0.5,0.1,0.1,0.1,0.1,0.1]",
        "++simulator.config.render_results=false",
        "++simulator.config.cameras.enable_cameras=false",
    ]
    return command, {
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES": str(physical_gpu),
        "ACCELERATE_TORCH_DEVICE": LOGICAL_DEVICE,
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }


def _expected_phase_rows() -> list[dict[str, Any]]:
    sampler = D1Sampler(variant=VARIANT, bucket_seed=BUCKET_SEED, total_steps=NUM_BATCHES)
    rows = []
    for step in range(NUM_BATCHES):
        counts = sampler.bucket_counts(step)
        rows.append(
            {
                "global_step": step,
                "bucket_counts": counts,
                "intended_bucket_counts": dict(counts),
                "full_reset_boundary": step in (0, 2, 5),
            }
        )
    return rows


def build_plan(*, physical_gpu: int = 0, run_root: Path = CANONICAL_RUN_ROOT) -> dict[str, Any]:
    """Build a no-launch plan after validating the R190 source and config."""

    catalog = load_d1_catalog(DEFAULT_RECEIPT_PATH)
    command, environment = build_run_command(physical_gpu=physical_gpu, run_root=run_root)
    return {
        "schema": PLAN_SCHEMA,
        "task_id": TASK_ID,
        "revision": REVISION,
        "status": "PLAN_ONLY",
        "config_path": str(CONFIG_PATH),
        "receipt_path": str(DEFAULT_RECEIPT_PATH),
        "receipt_schema": RECEIPT_SCHEMA,
        "receipt_status": RECEIPT_STATUS,
        "catalog_cells": [row.cell_id for row in catalog.rows],
        "physical_gpu": physical_gpu,
        "logical_device": LOGICAL_DEVICE,
        "num_envs": NUM_ENVS,
        "num_total_batches": NUM_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "num_mini_batches": 1,
        "run_root": str(Path(run_root).resolve()),
        "launcher_root": str(CANONICAL_LAUNCHER_ROOT),
        "aggregate_receipt": str(CANONICAL_RECEIPT_PATH),
        "command": command,
        "command_shell": shlex.join(command),
        "environment": environment,
        "expected_phase_rows": _expected_phase_rows(),
        "one_shot": True,
        "retry_policy": "none",
        "no_training_in_plan": True,
        "excluded_claims": list(EXCLUDED_CLAIMS),
    }


def run_once(*, physical_gpu: int = 0, run_root: Path = CANONICAL_RUN_ROOT) -> dict[str, Any]:
    """Launch exactly one fresh runtime attempt; never retry or reuse output."""

    root = Path(run_root).resolve()
    if root.exists():
        raise V23Error(f"refusing to reuse existing D1 smoke run root: {root}")
    root.mkdir(parents=True, exist_ok=False)
    command, environment = build_run_command(physical_gpu=physical_gpu, run_root=root)
    result = subprocess.run(command, cwd=REPO_ROOT, env={**os.environ, **environment}, check=False)
    if result.returncode != 0:
        raise V23Error(f"D1-FULL 64x10 smoke failed with returncode={result.returncode}")
    raw_path = root / "d1_full_64x10_raw.json"
    if not raw_path.is_file():
        raise V23Error(f"D1-FULL smoke exited without its raw record: {raw_path}")
    return {
        "status": "RUN_COMPLETED",
        "physical_gpu": physical_gpu,
        "logical_device": LOGICAL_DEVICE,
        "returncode": int(result.returncode),
        "raw_path": str(raw_path),
        "command": shlex.join(command),
    }


def _validate_raw(path: Path) -> dict[str, Any]:
    raw = _mapping(read_json(path), label="D1-FULL smoke raw record")
    if raw.get("schema") != RAW_SCHEMA:
        raise V23Error(f"D1-FULL raw schema must be {RAW_SCHEMA}")
    if raw.get("status") != "RUNTIME_VERIFIED":
        raise V23Error("D1-FULL raw status must be RUNTIME_VERIFIED")
    if raw.get("physical_gpu") not in PHYSICAL_GPUS or raw.get("logical_device") != LOGICAL_DEVICE:
        raise V23Error("D1-FULL raw GPU identity is invalid")
    if raw.get("process_count") != 1 or raw.get("num_processes") != 1:
        raise V23Error("D1-FULL raw must prove one process")
    if raw.get("cell") != "G5" or raw.get("training_enabled") is not True:
        raise V23Error("D1-FULL raw workflow identity must be the training-enabled G5 smoke")
    if raw.get("formal_admission") is not False or raw.get("policy_quality_claim") is not False:
        raise V23Error("D1-FULL raw must remain plumbing-only")
    for key, expected in (("num_envs", NUM_ENVS), ("num_total_batches", NUM_BATCHES), ("num_mini_batches", 1), ("save_frequency", SAVE_FREQUENCY), ("returncode", 0)):
        if raw.get(key) != expected:
            raise V23Error(f"D1-FULL raw {key} must be {expected!r}")
    if raw.get("retry_count") != 0:
        raise V23Error("D1-FULL smoke must have retry_count=0")
    if raw.get("full_reset_boundaries") != [0, 2, 5]:
        raise V23Error("D1-FULL raw full-reset boundaries must be exactly [0, 2, 5]")
    if raw.get("checkpoint_global_step") != NUM_BATCHES or raw.get("checkpoint_finite") is not True:
        raise V23Error("D1-FULL raw checkpoint proof is incomplete")
    checkpoint_path = raw.get("checkpoint_path")
    if (
        not isinstance(checkpoint_path, str)
        or Path(checkpoint_path).is_symlink()
        or not Path(checkpoint_path).is_file()
    ):
        raise V23Error("D1-FULL raw checkpoint proof must name the actual saved checkpoint file")
    phases = raw.get("phases")
    if not isinstance(phases, list) or len(phases) != NUM_BATCHES:
        raise V23Error("D1-FULL raw must contain one phase record per absolute global step")
    sampler = D1Sampler(variant=VARIANT, bucket_seed=BUCKET_SEED, total_steps=NUM_BATCHES)
    for expected_step, phase in enumerate(phases):
        item = _mapping(phase, label="D1 phase record")
        step = item.get("global_step")
        if step != expected_step:
            raise V23Error("D1 phase record global_step is not absolute")
        expected = sampler.telemetry(step)
        expected_counts = sampler.bucket_counts(step)
        bucket_counts = _validate_bucket_counts(
            item.get("bucket_counts"), label=f"D1 bucket_counts at global_step={step}"
        )
        intended_bucket_counts = _validate_bucket_counts(
            item.get("intended_bucket_counts"),
            label=f"D1 intended_bucket_counts at global_step={step}",
        )
        if bucket_counts != intended_bucket_counts:
            raise V23Error(f"D1 bucket count representations disagree at global_step={step}")
        if bucket_counts != expected_counts:
            raise V23Error(f"D1 bucket counts disagree at global_step={step}")
        if item.get("full_reset_boundary") is not (step in (0, 2, 5)):
            raise V23Error(f"D1 reset-boundary marker disagrees at global_step={step}")
        assignments = item.get("assignments")
        if not isinstance(assignments, list) or len(assignments) != NUM_ENVS:
            raise V23Error(f"D1 realized assignment identity is incomplete at global_step={step}")
        if assignments != expected:
            raise V23Error(f"D1 realized assignments disagree at global_step={step}")
        identity = item.get("realized_assignment_identity")
        if not isinstance(identity, list) or len(identity) != NUM_ENVS:
            raise V23Error(f"D1 realized parameter identity is incomplete at global_step={step}")
        if item.get("configured_joint_readback_status") != "CONFIGURED_HIGH_LEVEL_JOINT_READBACK_VERIFIED":
            raise V23Error(f"D1 configured joint readback status is incomplete at global_step={step}")
        applied_mass = item.get("door_panel_mass_kg_applied")
        expected_mass = [row["realized_params"]["door_weight_kg"] for row in expected]
        if applied_mass != expected_mass:
            raise V23Error(f"D1 applied mass assignments disagree at global_step={step}")
        if item.get("door_panel_mass_assignment_source") != "D1Sampler.realized_params_via_mdp.randomize_rigid_body_mass":
            raise V23Error(f"D1 applied mass assignment source is invalid at global_step={step}")
    return dict(raw)


def reduce_receipt(*, raw_path: Path, receipt_path: Path = CANONICAL_RECEIPT_PATH) -> dict[str, Any]:
    """Reduce one runtime record into the typed plumbing-only receipt."""

    raw = _validate_raw(Path(raw_path).resolve())
    receipt = {
        "schema": RECEIPT_SCHEMA_D1,
        "task_id": TASK_ID,
        "revision": REVISION,
        "status": PASS_STATUS,
        "runtime_verified": True,
        "physical_gpu": raw["physical_gpu"],
        "logical_device": raw["logical_device"],
        "num_envs": NUM_ENVS,
        "num_total_batches": NUM_BATCHES,
        "num_mini_batches": 1,
        "save_frequency": SAVE_FREQUENCY,
        "bucket_seed": BUCKET_SEED,
        "variant": VARIANT,
        "absolute_global_steps": list(range(NUM_BATCHES)),
        "phase_boundaries": [2, 5],
        "raw_path": str(Path(raw_path).resolve()),
        "physics_receipt_path": str(DEFAULT_RECEIPT_PATH),
        "physics_receipt_schema": RECEIPT_SCHEMA,
        "physics_receipt_status": RECEIPT_STATUS,
        "full_reset_boundaries_only": [0, 2, 5],
        "formal_admission": False,
        "policy_quality_claim": False,
        "excluded_claims": list(EXCLUDED_CLAIMS),
    }
    write_json(Path(receipt_path).resolve(), receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    plan = sub.add_parser("PLAN")
    plan.add_argument("--physical-gpu", type=int, choices=PHYSICAL_GPUS, default=0)
    plan.add_argument("--run-root", type=Path, default=CANONICAL_RUN_ROOT)
    run = sub.add_parser("RUN")
    run.add_argument("--physical-gpu", type=int, choices=PHYSICAL_GPUS, default=0)
    run.add_argument("--run-root", type=Path, default=CANONICAL_RUN_ROOT)
    reduce = sub.add_parser("REDUCE")
    reduce.add_argument("--raw", type=Path, required=True)
    reduce.add_argument("--receipt", type=Path, default=CANONICAL_RECEIPT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "PLAN":
            print(json.dumps(build_plan(physical_gpu=args.physical_gpu, run_root=args.run_root), indent=2))
        elif args.mode == "RUN":
            print(json.dumps(run_once(physical_gpu=args.physical_gpu, run_root=args.run_root), indent=2))
        else:
            print(json.dumps(reduce_receipt(raw_path=args.raw, receipt_path=args.receipt), indent=2))
    except (OSError, ValueError, TypeError, V23Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
