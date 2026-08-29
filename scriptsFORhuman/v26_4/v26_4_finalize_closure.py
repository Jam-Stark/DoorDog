#!/usr/bin/env python3
"""Validate the terminal v26-4 K/C/M route and emit one closure receipt."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE_ROOT = ROOT / "logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828"
CELLS = (
    "C0_CANONICAL_OFF_S0",
    "C0_CANONICAL_OFF_S1",
    "C1_CANONICAL_ON_S0",
    "C1_CANONICAL_ON_S1",
)
CHECKPOINTS = ("125", "250", "500", "750")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_object(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"artifact must be a JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", type=Path, default=DEFAULT_STAGE_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stage_root = args.stage_root.resolve()
    output = (args.output or stage_root / "closure_evidence.json").resolve()
    require(not output.exists(), f"refusing to overwrite closure evidence: {output}")

    paths = {
        "k": stage_root / "K/k_kinematics.json",
        "c_route": stage_root / "C/c_route.json",
        "c_proof": stage_root / "C/canonical_identity_proof.json",
        "m": stage_root / "M/m_outcome.json",
        "m_receipt": stage_root / "M/orchestrator_terminal_receipt.json",
    }
    k = load_object(paths["k"])
    c_route = load_object(paths["c_route"])
    c_proof = load_object(paths["c_proof"])
    m = load_object(paths["m"])
    m_receipt = load_object(paths["m_receipt"])

    require(k.get("typed_outcome") == "BILATERAL_ASYMMETRIC_AT_arm_j4", "unexpected K outcome")
    require(
        k.get("status") == "RUNTIME_COMPLETE_DIRECTIONAL_HARD_LIMIT_ASYMMETRY",
        "K is not the admitted directional runtime receipt",
    )
    candidates = k.get("candidates")
    require(isinstance(candidates, list) and len(candidates) == 9, "K candidate count is not nine")

    require(c_route.get("status") == "C_ROUTE_RESOLVED", "C route is unresolved")
    require(c_route.get("canonicalization_permitted") is False, "C route permits canonicalization")
    require(
        c_route.get("typed_ceiling") == "BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE",
        "unexpected C ceiling",
    )
    require(c_route.get("wave_m_status") == "NOT_RUN", "C route does not stop M")
    require(c_proof.get("status") == "CANONICAL_IDENTITY_PROOF_NOT_RUN", "C proof is not NOT_RUN")
    require(c_proof.get("canonicalization_implemented") is False, "C proof claims implementation")
    require(c_proof.get("proof_result") == "NOT_RUN", "C proof claims a result")

    require(m.get("status") == "NOT_RUN" and m.get("typed_outcome") == "NOT_RUN", "M is not NOT_RUN")
    cells = m.get("cells")
    require(isinstance(cells, dict) and tuple(sorted(cells)) == tuple(sorted(CELLS)), "M cells mismatch")
    for cell in CELLS:
        cell_payload = cells[cell]
        require(isinstance(cell_payload, dict) and cell_payload.get("status") == "NOT_RUN", f"{cell} ran")
        checkpoints = cell_payload.get("checkpoints")
        require(
            isinstance(checkpoints, dict) and tuple(sorted(checkpoints)) == tuple(sorted(CHECKPOINTS)),
            f"{cell} checkpoints mismatch",
        )
        for checkpoint in CHECKPOINTS:
            item = checkpoints[checkpoint]
            require(
                isinstance(item, dict) and item.get("status") == "NOT_RUN" and item.get("metrics") is None,
                f"{cell}/{checkpoint} contains a result",
            )
    require(m_receipt.get("status") == "TERMINAL_NOT_RUN", "M terminal receipt mismatch")
    require(m_receipt.get("no_gpu_or_source_lock_or_train_or_eval") is True, "M receipt lacks no-run assertion")

    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    receipt = {
        "schema": "a2_piper_base_v26_4_closure_v1",
        "status": "CLOSED_TYPED_STOP",
        "typed_ceiling": "BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE",
        "source_head": head,
        "outcomes": {
            "K": "BILATERAL_ASYMMETRIC_AT_arm_j4",
            "C": "CANONICAL_IDENTITY_PROOF_NOT_RUN",
            "M": "NOT_RUN",
        },
        "wave_m_entries": {"cells": 4, "checkpoints_per_cell": 4, "metrics": None},
        "claims": {
            "canonical_foundation_supported": False,
            "push_pull_shared_foundation_admitted": False,
            "teacher_or_student_binding_updated": False,
            "experiment_metrics_available": False,
        },
        "evidence": {name: str(path.resolve()) for name, path in paths.items()},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
