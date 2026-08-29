#!/usr/bin/env python3
"""Emit the frozen v26-4 M command/artifact registry before formal launch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
REQUIRED = (
    "scriptsFORhuman/v26_4/orchestrate_base_v26_4.sh",
    "scriptsFORhuman/v26_4/run_base_v26_4_train_cell.sh",
    "scriptsFORhuman/v26_4/run_base_v26_4_eval_lane.sh",
    "scriptsFORhuman/v26_4/run_base_v26_4_main_eval_cell.sh",
    "scriptsFORhuman/v26_4/v26_4_analyze_bilateral_foundation.py",
    "scriptsFORhuman/v26_4/v26_4_resolve_m_route.py",
    "scriptsFORhuman/v26_4/v26_4_verify_resolved_matrix.py",
    "scriptsFORhuman/v26_4/v26_4_capture_source_lock.py",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_bilateral_grasp_foundation.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_C0_CANONICAL_OFF.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v26_4_C1_CANONICAL_ON.yaml",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-key", required=True)
    parser.add_argument("--m-outcome", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.canonical_key.startswith("env.config."):
        raise RuntimeError("canonical key must be one env.config leaf")
    missing = [relative for relative in REQUIRED if not (ROOT / relative).is_file()]
    if missing:
        raise RuntimeError(f"v26-4 registry files missing: {missing}")
    source = ROOT / SOURCE
    if not source.is_file():
        raise RuntimeError(f"canonical CONT_STEP2000 source missing: {source}")
    m_outcome = json.loads(args.m_outcome.read_text(encoding="utf-8"))
    if not isinstance(m_outcome, dict):
        raise RuntimeError("M outcome must be JSON object")
    if m_outcome.get("schema") != "a2_piper_base_v26_4_wave_m_route_v1" or m_outcome.get("status") != "NOT_RUN" or m_outcome.get("typed_outcome") != "NOT_RUN":
        raise RuntimeError("M outcome is not terminal NOT_RUN")
    cells = m_outcome.get("cells")
    expected_cells = {"C0_CANONICAL_OFF_S0", "C0_CANONICAL_OFF_S1", "C1_CANONICAL_ON_S0", "C1_CANONICAL_ON_S1"}
    if not isinstance(cells, dict) or set(cells) != expected_cells:
        raise RuntimeError("M outcome cell registry mismatch")
    for cell, payload in cells.items():
        if not isinstance(payload, dict) or payload.get("status") != "NOT_RUN":
            raise RuntimeError(f"M cell is not NOT_RUN: {cell}")
        checkpoints = payload.get("checkpoints")
        if not isinstance(checkpoints, dict) or set(checkpoints) != {"125", "250", "500", "750"}:
            raise RuntimeError(f"M checkpoint registry mismatch: {cell}")
        for step, checkpoint in checkpoints.items():
            if not isinstance(checkpoint, dict) or checkpoint.get("status") != "NOT_RUN" or checkpoint.get("metrics") is not None:
                raise RuntimeError(f"M checkpoint falsely records evidence: {cell}/{step}")
    payload = {
        "schema": "a2_piper_base_v26_4_command_registry_v1",
        "status": "TERMINAL_NOT_RUN_VERIFIED",
        "canonicalization_key": args.canonical_key,
        "source_checkpoint": str(source),
        "m_outcome": str(args.m_outcome.resolve()),
        "terminal_route": {"status": "NOT_RUN", "typed_ceiling": m_outcome.get("typed_ceiling")},
        "training_contract": {
            "num_envs": 4096, "bilateral_runtime_count": {"left": 2048, "right": 2048},
            "batches": 750, "save_frequency": 125,
            "canonical_checkpoints": [125, 250, 500, 750],
            "checkpoint_load_mode": "policy_only", "policy_only_load_actor_rms": True,
            "visible_devices": [0, 1, 2, 3], "physical_binding": "ACCELERATE_TORCH_DEVICE=cuda:<physical_gpu>",
        },
        "evaluation_contract": {
            "per_checkpoint": True, "sides": ["left", "right"], "episodes_per_side": 64,
            "natural_first_episode_only": True, "checkpoint_load_mode": "full",
        },
        "commands": {"terminal": "orchestrate_base_v26_4.sh main --gpus 0,1,2,3 --canonical-key " + args.canonical_key},
        "gates": {
            "terminal_precondition": ["K BILATERAL_ASYMMETRIC_AT_arm_j4", "C §6.2 terminal route", "C identity proof NOT_RUN"],
            "forbidden": ["source lock", "GPU probe", "train", "eval", "metrics fabrication"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
