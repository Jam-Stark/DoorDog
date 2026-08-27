#!/usr/bin/env python3
"""Run one disjoint worker shard of the calibrated pull-v6 P1 oracle grid."""

from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
CELL_RUNNER = ROOT / "scriptsFORhuman/pull_v6/run_pull_v6_p1_oracle.py"
GRID_ROOT = ROOT / "logs_eval/a2_piper_pull_v6/p1_oracle_v1"
ANGLES = (65, 75, 85)
VELOCITIES = (0.15, 0.20, 0.25)
RELIEFS = (0.05, 0.10, 0.15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-id", type=int, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--gpu", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--attempt", type=int, default=60)
    parser.add_argument("--skip-complete", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.workers <= 0 or not 0 <= args.worker_id < args.workers:
        raise ValueError("worker-id must lie in [0, workers).")
    if args.attempt <= 0:
        raise ValueError("attempt must be positive.")

    cells = list(product(ANGLES, VELOCITIES, RELIEFS))
    assigned = cells[args.worker_id :: args.workers]
    for angle, velocity, relief in assigned:
        label = (
            f"angle_{angle:02d}_vel_{velocity:.2f}_"
            f"relief_{relief:.2f}_axis_x_attempt{args.attempt}"
        )
        output = GRID_ROOT / label
        metrics = output / "eval/metrics_eval.json"
        if output.exists():
            if args.skip_complete and metrics.is_file():
                print(f"[pull-v6 P1 grid] complete, skip: {label}", flush=True)
                continue
            raise FileExistsError(f"incomplete or non-skippable grid output: {output}")
        command = [
            sys.executable,
            str(CELL_RUNNER),
            "--angle-deg",
            str(angle),
            "--velocity",
            f"{velocity:.2f}",
            "--relief",
            f"{relief:.2f}",
            "--orientation-axis",
            "x",
            "--gpu",
            str(args.gpu),
            "--attempt",
            str(args.attempt),
        ]
        if args.run:
            command.append("--run")
        print("[pull-v6 P1 grid]", " ".join(command), flush=True)
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
