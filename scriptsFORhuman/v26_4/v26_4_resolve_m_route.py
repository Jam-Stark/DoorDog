#!/usr/bin/env python3
"""Resolve the v26-4 Wave M terminal route from frozen Wave K/C evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CELLS = ("C0_CANONICAL_OFF_S0", "C0_CANONICAL_OFF_S1", "C1_CANONICAL_ON_S0", "C1_CANONICAL_ON_S1")
CHECKPOINTS = (125, 250, 500, 750)
K_OUTCOME = "BILATERAL_ASYMMETRIC_AT_arm_j4"
C_CEILING = "BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"artifact must be a JSON object: {path}")
    return payload


def resolved(path: Path) -> str:
    return str(path.resolve())


def require_absent(path: Path, label: str) -> None:
    require(not path.exists(), f"{label} exists despite terminal NOT_RUN route: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k-artifact", type=Path, required=True)
    parser.add_argument("--c-route", type=Path, required=True)
    parser.add_argument("--c-proof", type=Path, required=True)
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite M outcome: {args.output}")
    require(not args.receipt_output.exists(), f"refusing to overwrite terminal receipt: {args.receipt_output}")
    require_absent(args.train_root, "Wave M train root")
    require_absent(args.eval_root, "Wave M eval root")

    k = load_json(args.k_artifact)
    c_route = load_json(args.c_route)
    c_proof = load_json(args.c_proof)
    k_path = resolved(args.k_artifact)
    require(k.get("schema") == "a2_piper_base_v26_4_wave_k_directional_hard_limit_v1", "unexpected K schema")
    require(k.get("status") == "RUNTIME_COMPLETE_DIRECTIONAL_HARD_LIMIT_ASYMMETRY", "K runtime route is not resolved")
    require(k.get("typed_outcome") == K_OUTCOME, f"K typed outcome is not {K_OUTCOME}")
    require(c_route.get("schema") == "a2_piper_base_v26_4_wave_c_route_v1", "unexpected C route schema")
    require(c_route.get("status") == "C_ROUTE_RESOLVED", "C route is not resolved")
    require(c_route.get("k_artifact") == k_path, "C route K provenance mismatch")
    require(c_route.get("k_typed_outcome") == K_OUTCOME, "C route K outcome mismatch")
    require(c_route.get("canonicalization_permitted") is False, "C route incorrectly permits canonicalization")
    require(c_route.get("typed_ceiling") == C_CEILING, "C route typed ceiling mismatch")
    require(c_route.get("required_joint") == "arm_j4" and c_route.get("required_side") == "RIGHT", "C route asymmetry identity mismatch")
    require(c_route.get("wave_m_status") == "NOT_RUN", "C route does not close Wave M")
    require(c_proof.get("schema") == "a2_piper_base_v26_4_canonical_identity_proof_v1", "unexpected C proof schema")
    require(c_proof.get("status") == "CANONICAL_IDENTITY_PROOF_NOT_RUN", "C proof status must be NOT_RUN")
    require(c_proof.get("proof_result") == "NOT_RUN", "C proof result must be NOT_RUN")
    require(c_proof.get("canonicalization_implemented") is False, "C proof contradicts terminal route")
    require(c_proof.get("k_artifact") == k_path and c_proof.get("k_typed_outcome") == K_OUTCOME, "C proof K provenance mismatch")

    cells = {
        cell: {
            "status": "NOT_RUN",
            "reason": C_CEILING,
            "checkpoints": {
                str(step): {"status": "NOT_RUN", "metrics": None}
                for step in CHECKPOINTS
            },
        }
        for cell in CELLS
    }
    outcome = {
        "schema": "a2_piper_base_v26_4_wave_m_route_v1",
        "status": "NOT_RUN",
        "typed_outcome": "NOT_RUN",
        "reason": "Wave K directional hard-limit asymmetry requires an asymmetric posture; §6.2 forbids the C0/C1 canonical-equivalence experiment.",
        "typed_ceiling": C_CEILING,
        "preregistered_scaffold": {
            "cells": ["C0_CANONICAL_OFF", "C1_CANONICAL_ON"],
            "seeds": [0, 1],
            "checkpoints": list(CHECKPOINTS),
            "metrics": ["K5 admission", "Stage3 contact stability", "handle high-water LEFT/RIGHT ratio"],
            "execution": "NOT_RUN_NO_METRICS_FABRICATED",
        },
        "cells": cells,
        "provenance": {
            "k_artifact": k_path,
            "c_route": resolved(args.c_route),
            "c_proof": resolved(args.c_proof),
            "k_typed_outcome": K_OUTCOME,
            "c_wave_m_status": "NOT_RUN",
        },
    }
    receipt = {
        "schema": "a2_piper_base_v26_4_wave_m_terminal_receipt_v1",
        "status": "TERMINAL_NOT_RUN",
        "typed_outcome": "NOT_RUN",
        "command": args.command,
        "no_gpu_or_source_lock_or_train_or_eval": True,
        "m_outcome": str(args.output),
        "reason": outcome["reason"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
