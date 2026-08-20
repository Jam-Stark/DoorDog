#!/usr/bin/env python3
"""Verify the restored pull-v5.6-r2 migration boundary without launching IsaacSim."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import torch


EXPECTED_ROOT = Path("/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0")
PLAN_ID = "a2_piper_pull_v5_6_terminal_hold_specialist_finetune"
FAMILIES = ("near_rest", "coarse_neg", "coarse_pos", "straight_minus_x", "side_step")
MANIFEST = Path("scriptsFORhuman/pull_v5/PULL_V5_6_R2_RUNTIME_ASSETS.txt")
WARM_RECEIPT = Path("logs_eval/a2_piper_pull_v5/v5_6_specialist_t0/WARM_START.json")
MICRO_RECEIPT = Path("logs_eval/a2_piper_pull_v5/v5_6_specialist_t0_5_micro_r2/MICRO_SMOKE.json")
STEP0_RECEIPT = Path("logs_eval/a2_piper_pull_v5/v5_6_specialist_gate_step0/STEP0_GATE.json")
WARM_CHECKPOINT = Path("logs_rl/a2_piper_pull_v5_6_hold_specialist/warm_start/model_step_000000.pt")
STATE_BANK = Path("logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt")
V4B_CHECKPOINT = Path(
    "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v4_B_wave1_seed1/model_step_000750.pt"
)
ORIGINAL_HOMIE = Path("gr00t/rl/data/policies/A2_Base/policy.pt")


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def _validate_receipt(path: Path, rows: int) -> dict:
    receipt = _read_json(path)
    if receipt.get("plan_id") != PLAN_ID or receipt.get("status") != "PASS":
        raise RuntimeError(f"receipt is not a PASS for the v5.6 plan: {path}")
    if len(receipt.get("rows", [])) != rows:
        raise RuntimeError(f"receipt row count mismatch: {path}")
    if receipt.get("scientific_denominator_included") is not False:
        raise RuntimeError(f"diagnostic receipt entered a scientific denominator: {path}")
    if receipt.get("denominator_scope") != "none":
        raise RuntimeError(f"diagnostic denominator scope mismatch: {path}")
    env_ids = [row.get("env_id") for row in receipt["rows"]]
    if len(set(env_ids)) != rows:
        raise RuntimeError(f"receipt env IDs are not unique: {path}")
    return receipt


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    if root != EXPECTED_ROOT:
        raise RuntimeError(
            f"clone path must be {EXPECTED_ROOT}; current path is {root}. "
            "Use the documented compatibility symlink before validation."
        )

    manifest_path = root / MANIFEST
    assets = [
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    missing = [path for path in assets if not (root / path).is_file()]
    if missing:
        raise RuntimeError("missing migrated runtime assets: " + ", ".join(missing))
    if not (root / ORIGINAL_HOMIE).is_file():
        raise RuntimeError(f"tracked original HOMIE policy is missing: {ORIGINAL_HOMIE}")

    warm = _read_json(root / WARM_RECEIPT)
    expected_warm = str((root / WARM_CHECKPOINT).resolve())
    if warm.get("plan_id") != PLAN_ID or warm.get("status") != "PASS":
        raise RuntimeError("warm-start receipt is not an admitted PASS")
    if warm.get("checkpoint_path") != expected_warm:
        raise RuntimeError("warm-start receipt absolute checkpoint path does not match this clone")

    micro = _validate_receipt(root / MICRO_RECEIPT, 8)
    if micro.get("training_launch_eligible") is not False or micro.get("t1_prerequisite") is not False:
        raise RuntimeError("micro-smoke must remain diagnostic-only")

    step0 = _validate_receipt(root / STEP0_RECEIPT, 80)
    expected_family_counts = {family: 16 for family in FAMILIES}
    if step0.get("family_row_counts") != expected_family_counts:
        raise RuntimeError("step-0 family balance is not 16 rows per family")
    if sum(step0.get("family_done_counts", {}).values()) != 0:
        raise RuntimeError("migrated step-0 receipt differs from the accepted 0/80 diagnostic")

    checkpoint = torch.load(root / WARM_CHECKPOINT, map_location="cpu", weights_only=False)
    required_checkpoint_keys = {"policy_state_dict", "value_state_dict", "optimizer_state_dict", "lr_scheduler_state_dict", "state"}
    if not isinstance(checkpoint, dict) or not required_checkpoint_keys.issubset(checkpoint):
        raise RuntimeError("warm checkpoint structure is incomplete")
    if checkpoint["optimizer_state_dict"] is not None or checkpoint["lr_scheduler_state_dict"] is not None:
        raise RuntimeError("warm checkpoint unexpectedly carries optimizer or scheduler state")

    bank = torch.load(root / STATE_BANK, map_location="cpu", weights_only=False)
    if not isinstance(bank, dict) or bank.get("schema") != "a2_piper_pull_v5_state_bank_v2":
        raise RuntimeError("G8 state-bank schema mismatch")
    if int(bank["robot_root_state"].shape[0]) != 191 or len(bank.get("buffers", {})) != 86:
        raise RuntimeError("G8 state-bank payload does not contain the admitted 191 rows / 86 buffers")
    if not (root / V4B_CHECKPOINT).is_file():
        raise RuntimeError("v4-B primary checkpoint is missing")

    print("MIGRATION_ASSET_VALIDATION_PASS")
    print(f"repo_root={root}")
    print(f"runtime_assets={len(assets)}")
    print("micro_rows=8")
    print("step0_rows=80")
    print("step0_diagnostic_capability=0/80")
    print("state_bank_rows=191")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"MIGRATION_ASSET_VALIDATION_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
