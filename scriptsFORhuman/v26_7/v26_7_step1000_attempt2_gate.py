#!/usr/bin/env python3
"""Gate the sole authorized step1000 attempt2 against the immutable attempt1 LEFT evidence."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REDUCER = ROOT / "scriptsFORhuman/v26_7/v26_7_reduce.py"
CELLS = (("Q05_S0", 0, 0), ("Q05_S1", 1, 64))
EPISODES = 64


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load_json(path: Path) -> Any:
    require(path.is_file(), f"missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_side_summary():
    spec = importlib.util.spec_from_file_location("v26_7_reduce", REDUCER)
    require(spec is not None and spec.loader is not None, f"cannot import v26-7 reducer: {REDUCER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.side_summary


def side_payload(root: Path, cell: str, seed: int, side_summary) -> dict[str, Any]:
    path = root / f"{cell}_STEP1000" / "left"
    summary = side_summary(path, "left", seed)
    records = load_json(path / "a2_v14_per_env_records.json")
    metrics = load_json(path / "metrics_eval.json")
    require(isinstance(records, list) and len(records) == EPISODES, f"{path}: a2_v14 records are not exact64")
    terminal = metrics.get("episode_terminal_diagnostics")
    stages = metrics.get("episode_max_stage_reached")
    require(isinstance(terminal, list) and isinstance(stages, list) and len(terminal) == len(stages) == EPISODES, f"{path}: metrics terminal/max-stage are not exact64")
    return {
        "path": str(path),
        "durable_depression": summary["durable_depression"],
        "records": records,
        "terminal_diagnostics": terminal,
        "episode_max_stage_reached": stages,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt1-root", type=Path, required=True)
    parser.add_argument("--attempt2-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite attempt2 gate: {args.output}")
    side_summary = load_side_summary()
    failures: list[str] = []
    cells: dict[str, dict[str, Any]] = {}
    for cell, seed, expected_durable in CELLS:
        old = side_payload(args.attempt1_root, cell, seed, side_summary)
        new = side_payload(args.attempt2_root, cell, seed, side_summary)
        if old["durable_depression"] != expected_durable:
            failures.append(f"ATTEMPT1_DURABLE_MISMATCH:{cell}:{old['durable_depression']}")
        if new["durable_depression"] != expected_durable:
            failures.append(f"ATTEMPT2_DURABLE_MISMATCH:{cell}:{new['durable_depression']}")
        if old["records"] != new["records"]:
            failures.append(f"A2_V14_RECORDS_NOT_EXACT:{cell}")
        if old["terminal_diagnostics"] != new["terminal_diagnostics"]:
            failures.append(f"TERMINAL_DIAGNOSTICS_NOT_EXACT:{cell}")
        if old["episode_max_stage_reached"] != new["episode_max_stage_reached"]:
            failures.append(f"EPISODE_MAX_STAGE_NOT_EXACT:{cell}")
        cells[cell] = {
            "expected_durable_depression": expected_durable,
            "attempt1_durable_depression": old["durable_depression"],
            "attempt2_durable_depression": new["durable_depression"],
            "a2_v14_records_exact": old["records"] == new["records"],
            "terminal_diagnostics_exact": old["terminal_diagnostics"] == new["terminal_diagnostics"],
            "episode_max_stage_reached_exact": old["episode_max_stage_reached"] == new["episode_max_stage_reached"],
        }
    status = "DETERMINISM_PASS" if not failures else "V26_7_INVALID"
    payload = {
        "schema": "a2_piper_base_v26_7_step1000_attempt2_gate_v1",
        "status": status,
        "attempt1_root": str(args.attempt1_root),
        "attempt2_root": str(args.attempt2_root),
        "contract": {"side": "left", "episodes": EPISODES, "durable_depression": {"Q05_S0": 0, "Q05_S1": 64}, "exact_artifacts": ["a2_v14_per_env_records.json", "metrics_eval.json:episode_terminal_diagnostics", "metrics_eval.json:episode_max_stage_reached"]},
        "cells": cells,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(args.output), "failures": failures}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
