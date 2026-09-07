#!/usr/bin/env python3
"""Reduce one exact64 Wave2 full-continuation milestone."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from natural_protocol import NaturalProtocolViolation
from reduce import SIDES, side_summary
from verify import read_config, validate_config


SCHEMA = "a2_piper_pull_v26_8_wave2_reducer_v1"
STEPS = (6750, 7500, 8250, 9000)
FINAL_WAVE1_STEP = 6000
FINAL_WAVE2_STEP = 9000


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def source_checkpoint(wave1_train_root: Path, cell: str) -> Path:
    path = wave1_train_root / cell / f"model_step_{FINAL_WAVE1_STEP:06d}.pt"
    require(path.is_file(), f"missing final Wave1 checkpoint: {path}")
    return path.resolve()


def continued_contract(train_root: Path, wave1_train_root: Path, cell: str) -> dict:
    cfg_path = train_root / cell / "resolved_config.yaml"
    cfg = read_config(cfg_path)
    source = source_checkpoint(wave1_train_root, cell)
    contract = validate_config(cfg, cell, continuation_from=source)
    require(Path(str(cfg["checkpoint"])).resolve() == source, f"{cell}: continuation checkpoint differs from final Wave1 checkpoint")
    require(cfg["checkpoint_load_mode"] == "full", f"{cell}: full checkpoint load required")
    require(cfg["num_envs"] == 1024, f"{cell}: Wave2 requires 1024 envs")
    require(cfg["algo"]["trl"]["num_total_batches"] == FINAL_WAVE2_STEP, f"{cell}: Wave2 absolute batch ceiling must be 9000")
    require(cfg["callbacks"]["model_save"]["save_frequency"] == 250, f"{cell}: checkpoint cadence")
    return {
        "validation": contract,
        "checkpoint": str(source),
        "checkpoint_load_mode": "full",
        "loaded_global_step": FINAL_WAVE1_STEP,
        "num_total_batches": FINAL_WAVE2_STEP,
        "new_batches": FINAL_WAVE2_STEP - FINAL_WAVE1_STEP,
        "online_staged_reset_buffers": "fresh_process_reaccumulates; not serialized by current env state writer",
    }


def label(results: dict[str, dict[str, dict]], step: int) -> str:
    if step != FINAL_WAVE2_STEP:
        return "PULL_WAVE2_MILESTONE_REPORTED"
    if all(min(results[cell][side]["E7"] for side in SIDES) >= 32 for cell in results):
        return "PULL_FULL_CHAIN_BILATERAL"
    return "PULL_FULL_CHAIN_PARTIAL"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave1-train-root", type=Path, required=True)
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--step", type=int, choices=STEPS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cells", nargs=2, required=True)
    args = parser.parse_args()

    require(not args.output.exists(), f"refusing to overwrite reducer: {args.output}")
    cells = tuple(args.cells)
    require(len(set(cells)) == 2 and all(cell in ("P_S0", "P_S1", "P_S2") for cell in cells), "Wave2 requires two distinct Wave1 cells")
    contracts = {cell: continued_contract(args.train_root, args.wave1_train_root, cell) for cell in cells}
    try:
        results = {
            cell: {
                side: side_summary(args.eval_root / f"{cell}_STEP{args.step}" / side, side, int(cell[-1]))
                for side in SIDES
            }
            for cell in cells
        }
    except NaturalProtocolViolation as exc:
        payload = {
            "schema": SCHEMA,
            "status": "EXPERIMENT_INVALID",
            "step": args.step,
            "route": "PULL_V26_8_INVALID",
            "failures": [f"NATURAL_PROTOCOL:{exc}"],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    integrity_failures = [
        f"INTEGRITY_VIOLATIONS:{cell}/{side}"
        for cell in cells
        for side in SIDES
        if results[cell][side]["integrity_violations"] != 0
    ]
    payload = {
        "schema": SCHEMA,
        "status": "EXPERIMENT_INVALID" if integrity_failures else "EXPERIMENT_COMPLETE",
        "step": args.step,
        "wave1_train_root": str(args.wave1_train_root),
        "train_root": str(args.train_root),
        "eval_root": str(args.eval_root),
        "selected_cells": list(cells),
        "continuation_contracts": contracts,
        "cells": results,
        "route": "PULL_V26_8_INVALID" if integrity_failures else label(results, args.step),
        "failures": integrity_failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "step": args.step, "route": payload["route"], "output": str(args.output)}, ensure_ascii=False))
    return 2 if integrity_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
