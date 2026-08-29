#!/usr/bin/env python3
"""Validate R2 Wave K's two hard gates before any C/M routing exists."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


K_ROOT = Path("logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/K")
FK_SCHEMA = "a2_piper_base_v26_4_r2_fk_mirror_identity_v1"
K_SCHEMA = "a2_piper_base_v26_4_r2_wave_k_kinematics_v1"
C_ROUTE_SCHEMA = "a2_piper_base_v26_4_r2_c_route_v1"
C_IDENTITY_SCHEMA = "a2_piper_base_v26_4_r2_canonical_identity_v1"
K_OUTCOMES = {
    "BILATERAL_KINEMATICALLY_SYMMETRIC",
    "BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET",
    "BILATERAL_ASYMMETRIC_AT_arm_j1",
    "BILATERAL_ASYMMETRIC_AT_arm_j2",
    "BILATERAL_ASYMMETRIC_AT_arm_j3",
    "BILATERAL_ASYMMETRIC_AT_arm_j4",
    "BILATERAL_ASYMMETRIC_AT_arm_j5",
    "BILATERAL_ASYMMETRIC_AT_arm_j6",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required R2 K artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"R2 K artifact must be JSON object: {path}")
    return payload


def branch_for(k_outcome: str) -> str:
    if k_outcome in {"BILATERAL_KINEMATICALLY_SYMMETRIC", "BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET"}:
        return "SECTION_6_1_CANONICALIZATION_REQUIRES_FROZEN_C_INTERFACE"
    return "SECTION_6_2_ASYMMETRIC_POSTURE_REQUIRES_FROZEN_C_INTERFACE"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fk-artifact", type=Path, default=K_ROOT / "fk_mirror_identity.json")
    parser.add_argument("--k-artifact", type=Path, default=K_ROOT / "k_kinematics.json")
    parser.add_argument("--c-route", type=Path, required=True)
    parser.add_argument("--c-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite R2 M gate receipt: {args.output}")

    fk = load_json(args.fk_artifact)
    require(fk.get("schema") == FK_SCHEMA, "R2 FK schema mismatch")
    require(fk.get("status") == "RUNTIME_COMPLETE", "R2 FK status is not runtime complete")
    require(fk.get("typed_outcome") == "FK_MIRROR_IDENTITY_PASS", "R2 FK mirror identity did not pass")
    require(fk.get("target_mirror_identity") == "PASS", "R2 handle-derived target mirror identity did not pass")

    k = load_json(args.k_artifact)
    require(k.get("schema") == K_SCHEMA, "R2 K schema mismatch")
    require(k.get("status") == "RUNTIME_COMPLETE", "R2 K status is not runtime complete")
    outcome = k.get("typed_outcome")
    require(isinstance(outcome, str) and outcome in K_OUTCOMES, f"R2 K typed outcome is invalid: {outcome!r}")

    c_route = load_json(args.c_route)
    c_identity = load_json(args.c_identity)
    require(c_route.get("schema") == C_ROUTE_SCHEMA and c_route.get("status") == "SECTION_6_1_ROUTE_COMPLETE", "R2 C route mismatch")
    require(c_route.get("typed_outcome") == "CANONICAL_IDENTITY_PROOF_PASS", "R2 C route is not identity PASS")
    require(c_route.get("k_typed_outcome") == outcome and c_route.get("canonicalization_enabled") is True, "R2 C route K/seam mismatch")
    require(isinstance(c_route.get("seam_key"), str) and c_route.get("seam_key"), "R2 C seam key missing")
    require(c_route.get("identity_artifact") == str(args.c_identity.resolve()), "R2 C identity provenance mismatch")
    require(c_identity.get("schema") == C_IDENTITY_SCHEMA and c_identity.get("status") == "STATIC_IDENTITY_COMPLETE", "R2 identity schema/status mismatch")
    require(c_identity.get("typed_outcome") == "CANONICAL_IDENTITY_PROOF_PASS" and c_identity.get("proof_result") == "PASS" and c_identity.get("implemented") is True, "R2 identity proof is not PASS")
    payload = {
        "schema": "a2_piper_base_v26_4_r2_wave_m_k_gate_v1",
        "status": "K_C_GATE_ADMITTED_READY_FOR_R2_RUNNER",
        "branch": branch_for(outcome),
        "k_typed_outcome": outcome,
        "fk_artifact": str(args.fk_artifact.resolve()),
        "k_artifact": str(args.k_artifact.resolve()),
        "fk_contract": {
            "typed_outcome": "FK_MIRROR_IDENTITY_PASS",
            "target_mirror_identity": "PASS",
        },
        "c_route": str(args.c_route.resolve()), "c_identity": str(args.c_identity.resolve()),
        "seam_key": c_route["seam_key"],
        "next_gate": "Root/reviewer admission required before source lock, GPU allocation, train, eval, or M metrics.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
