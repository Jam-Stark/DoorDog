#!/usr/bin/env python3
"""Build the E5 harness receipt without manufacturing a missing Isaac trace."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

from gr00t.rl.sim2sim.evaluation.paired_trace import compare_ordered_rows


FLOAT_FIELDS = (
    "time_s",
    "base_height_m",
    "max_abs_robot_ctrl_nm",
    "door_hinge_rad",
    "handle_hinge_rad",
    "door_external_torque_nm",
)
DISCRETE_FIELDS = ("step", "constraint_gate_active")


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mujoco-trace", required=True, type=Path)
    parser.add_argument("--isaac-trace", type=Path)
    parser.add_argument("--v24-pattern-receipt", required=True, type=Path)
    parser.add_argument("--output-receipt", required=True, type=Path)
    args = parser.parse_args()

    mujoco_trace = args.mujoco_trace.resolve(strict=True)
    rows = _rows(mujoco_trace)
    self_check = compare_ordered_rows(
        rows[:8], rows[:8], float_fields=FLOAT_FIELDS, discrete_fields=DISCRETE_FIELDS, atol=1.0e-6
    )
    v24 = json.loads(args.v24_pattern_receipt.resolve(strict=True).read_text(encoding="utf-8"))
    pattern = {
        "source_schema": v24["schema"],
        "source_status": v24["status"],
        "source_commit": v24["source_identity"]["current_git_commit"],
        "source_path": str(args.v24_pattern_receipt.resolve()),
        "ordered_row_float_atol": v24["comparison"]["atol"],
        "proven_zero_diff_rows": v24["p0_default_off"]["parity"]["compared_rows"],
        "discrete_exact": True,
    }
    if args.isaac_trace is None:
        comparison = None
        input_status = "BLOCKED_INPUT_ISAAC_PAIRED_TRACE"
        classification = "EXPLORATORY_NON_COMPARABLE"
        isaac_identity = None
    else:
        isaac_trace = args.isaac_trace.resolve(strict=True)
        comparison = compare_ordered_rows(
            _rows(isaac_trace),
            rows,
            float_fields=FLOAT_FIELDS,
            discrete_fields=DISCRETE_FIELDS,
            atol=1.0e-6,
        )
        input_status = "PAIRED_TRACE_COMPARED"
        classification = "VALID_COMPARABLE"
        isaac_identity = str(isaac_trace)

    receipt = {
        "schema": "doordog.sim2sim.e5_paired_trace_receipt.v1",
        "evidence_level": "E5",
        "result_classification": classification,
        "input_status": input_status,
        "mujoco_trace": str(mujoco_trace),
        "isaac_trace": isaac_identity,
        "comparison": comparison,
        "harness_self_check": {
            **self_check,
            "authority": "HARNESS_OPERATION_ONLY_NOT_PAIRED_EVIDENCE",
        },
        "v24_p0_pattern": pattern,
        "harness_identity": {
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
            ).stdout.strip(),
            "path": "gr00t/rl/sim2sim/evaluation/paired_trace.py",
        },
        "paired_cases": [
            {"case": name, "status": input_status}
            for name in ("reset", "hold", "handle_release", "door_open", "post_release")
        ],
        "provenance_policy": {
            "identity": "git_commit_plus_path",
            "strict_exact_hash": False,
            "strict_exact_hash_scope": "FORMAL_PAIRED_EVIDENCE_ONLY",
        },
        "reason": (
            "No current Student/scene Isaac trace was produced because the shared production hook is deferred "
            "and the v24 GPU activity window was not disturbed."
            if comparison is None
            else None
        ),
    }
    args.output_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.output_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
