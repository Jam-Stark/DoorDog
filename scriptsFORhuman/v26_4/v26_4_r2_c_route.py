#!/usr/bin/env python3
"""Resolve the admitted R2 K result through the implemented C identity seam."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


K_SCHEMA = "a2_piper_base_v26_4_r2_wave_k_kinematics_v1"
IDENTITY_SCHEMA = "a2_piper_base_v26_4_r2_canonical_identity_v1"
ROUTE_SCHEMA = "a2_piper_base_v26_4_r2_c_route_v1"
K_OUTCOME = "BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET"
SEAM_KEY = "env.config.a2_v26_4_side_canonicalization_enabled"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"artifact must be a JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k-artifact", type=Path, required=True)
    parser.add_argument("--identity-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite C route artifact: {args.output}")

    k = load_json(args.k_artifact)
    require(k.get("schema") == K_SCHEMA, "R2 K schema mismatch")
    require(k.get("status") == "RUNTIME_COMPLETE", "R2 K is not runtime complete")
    require(k.get("typed_outcome") == K_OUTCOME, "R2 K does not admit the action-offset C route")
    require(k.get("fk_mirror_identity") == "PASS", "R2 K FK mirror identity is not PASS")
    require(k.get("target_mirror_identity") == "PASS", "R2 K target mirror identity is not PASS")

    identity = load_json(args.identity_artifact)
    require(identity.get("schema") == IDENTITY_SCHEMA, "C identity schema mismatch")
    require(identity.get("status") == "STATIC_IDENTITY_COMPLETE", "C identity is not complete")
    require(identity.get("typed_outcome") == "CANONICAL_IDENTITY_PROOF_PASS", "C identity typed outcome mismatch")
    require(identity.get("proof_result") == "PASS", "C identity proof did not pass")
    require(identity.get("implemented") is True, "C identity implementation is not admitted")
    require(identity.get("seam_key") == SEAM_KEY, "C identity seam key mismatch")

    payload = {
        "schema": ROUTE_SCHEMA,
        "status": "SECTION_6_1_ROUTE_COMPLETE",
        "typed_outcome": "CANONICAL_IDENTITY_PROOF_PASS",
        "k_typed_outcome": k["typed_outcome"],
        "canonicalization_enabled": True,
        "seam_key": SEAM_KEY,
        "identity_artifact": str(args.identity_artifact.resolve()),
        "k_artifact": str(args.k_artifact.resolve()),
        "route_basis": "R2 admitted action-offset asymmetry with FK and handle-target mirror identity PASS; C is a static implementation proof only.",
        "training_orientation_reference_audit": "Not corrected in R2 C; remains an explicit v26-5 input.",
        "evidence_level": "STATIC_PASS",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
