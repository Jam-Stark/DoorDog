#!/usr/bin/env python3
"""Resolve Wave C §6.2 from the admitted Wave K directional-limit artifact."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_K_ARTIFACT = (
    REPO_ROOT
    / "logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/K/k_kinematics.json"
)
DEFAULT_OUTPUT_ROOT = (
    REPO_ROOT / "logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/C"
)
MIRROR_MASK = [-1, 1, 1, -1, 1, -1]
ROOT_OFFSET_READBACK_TOLERANCE_M = 1.0e-4


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def require_list(value: Any, label: str, length: int) -> list[Any]:
    require(isinstance(value, list), f"{label} must be a list")
    require(len(value) == length, f"{label} must contain exactly {length} values")
    return value


def require_finite_vector(value: Any, label: str, length: int) -> list[float]:
    vector = require_list(value, label, length)
    require(
        all(type(item) in (int, float) and math.isfinite(item) for item in vector),
        f"{label} must contain finite numeric values",
    )
    return vector


def require_exact_readback(side: dict[str, Any], label: str) -> None:
    requested = require_finite_vector(
        side.get("ik_requested_q_arm_j1_to_j6_rad"),
        f"{label}.ik_requested_q_arm_j1_to_j6_rad",
        6,
    )
    readback = require_finite_vector(
        side.get("joint_state_readback_arm_j1_to_j6_rad"),
        f"{label}.joint_state_readback_arm_j1_to_j6_rad",
        6,
    )
    require(
        requested == readback,
        f"{label} joint-state readback must exactly equal the requested arm state",
    )
    require(
        side.get("joint_state_readback_max_abs_error_rad") == 0.0,
        f"{label}.joint_state_readback_max_abs_error_rad must be 0.0",
    )


def validate_k_artifact(k: dict[str, Any]) -> list[str]:
    require(k.get("schema") == "a2_piper_base_v26_4_wave_k_directional_hard_limit_v1", "unexpected K schema")
    require(
        k.get("status") == "RUNTIME_COMPLETE_DIRECTIONAL_HARD_LIMIT_ASYMMETRY",
        "K artifact is not the admitted directional hard-limit runtime result",
    )
    require(
        k.get("typed_outcome") == "BILATERAL_ASYMMETRIC_AT_arm_j4",
        "Wave C §6.2 requires BILATERAL_ASYMMETRIC_AT_arm_j4",
    )

    protocol = require_mapping(k.get("protocol"), "protocol")
    require(protocol.get("right_seed_equals_mask_times_left_seed") is True, "mirror seed identity is not admitted")
    require(
        protocol.get("scripted_scan_mirror_mask_arm_j1_to_j6") == MIRROR_MASK,
        "unexpected admitted arm mirror mask",
    )
    require(
        protocol.get("scripted_scan_anchor_side") == "LEFT",
        "directional scan anchor must be LEFT",
    )
    require_finite_vector(
        protocol.get("scripted_scan_anchor_seed_arm_j1_to_j6_rad"),
        "protocol.scripted_scan_anchor_seed_arm_j1_to_j6_rad",
        6,
    )

    anchor = require_mapping(k.get("anchor_provenance"), "anchor_provenance")
    require(anchor.get("source") == "v26_3 M1_S1 step750 Stage3 terminal runtime readback", "unexpected anchor provenance")
    require_finite_vector(anchor.get("matched_symmetric_anchor_xyzm_yaw"), "anchor_provenance.matched_symmetric_anchor_xyzm_yaw", 4)

    candidates = require_list(k.get("candidates"), "candidates", 9)
    candidate_ids: list[str] = []
    for index, candidate_value in enumerate(candidates):
        label = f"candidates[{index}]"
        candidate = require_mapping(candidate_value, label)
        candidate_id = candidate.get("candidate_id")
        require(isinstance(candidate_id, str) and candidate_id, f"{label}.candidate_id must be non-empty")
        candidate_ids.append(candidate_id)

        expected = require_list(candidate.get("expected_door_local_root_offsets_xyz_m"), f"{label}.expected_door_local_root_offsets_xyz_m", 2)
        readback = require_list(candidate.get("readback_door_local_root_offsets_xyz_m"), f"{label}.readback_door_local_root_offsets_xyz_m", 2)
        expected_left = require_finite_vector(expected[0], f"{label}.expected.LEFT", 3)
        expected_right = require_finite_vector(expected[1], f"{label}.expected.RIGHT", 3)
        readback_left = require_finite_vector(readback[0], f"{label}.readback.LEFT", 3)
        readback_right = require_finite_vector(readback[1], f"{label}.readback.RIGHT", 3)
        root_readback_error = max(
            *(abs(expected_item - readback_item) for expected_item, readback_item in zip(expected_left, readback_left)),
            *(abs(expected_item - readback_item) for expected_item, readback_item in zip(expected_right, readback_right)),
        )
        require(
            root_readback_error <= ROOT_OFFSET_READBACK_TOLERANCE_M,
            f"{label} root readback exceeds the admitted Wave K tolerance of {ROOT_OFFSET_READBACK_TOLERANCE_M} m",
        )
        require(
            expected_left[0] == expected_right[0]
            and expected_left[1] == -expected_right[1]
            and expected_left[2] == expected_right[2],
            f"{label} root offsets are not a left/right mirror pair",
        )

        sides = require_mapping(candidate.get("sides"), f"{label}.sides")
        require(set(sides) == {"LEFT", "RIGHT"}, f"{label}.sides must contain only LEFT and RIGHT")
        left = require_mapping(sides["LEFT"], f"{label}.LEFT")
        require(left.get("reachable") is True, f"{label}.LEFT must be reachable")
        require(left.get("ik_invalid_due_to_hard_limit") is False, f"{label}.LEFT must not be invalidated by a hard limit")
        require(left.get("first_hard_limit_rejection") is None, f"{label}.LEFT must have no first hard-limit rejection")
        require_exact_readback(left, f"{label}.LEFT")

        right = require_mapping(sides["RIGHT"], f"{label}.RIGHT")
        require(right.get("reachable") is False, f"{label}.RIGHT must be unreachable under the mirror seed")
        require(right.get("ik_invalid_due_to_hard_limit") is True, f"{label}.RIGHT must be invalidated by a hard limit")
        rejection = require_mapping(right.get("first_hard_limit_rejection"), f"{label}.RIGHT.first_hard_limit_rejection")
        require(type(rejection.get("iteration")) is int and rejection["iteration"] >= 0, f"{label}.RIGHT rejection iteration must be non-negative int")
        require_finite_vector(rejection.get("q_des_arm_j1_to_j6_rad"), f"{label}.RIGHT rejection q_des", 6)
        lower = require_list(rejection.get("hard_limit_lower_violation_mask_arm_j1_to_j6"), f"{label}.RIGHT lower mask", 6)
        upper = require_list(rejection.get("hard_limit_upper_violation_mask_arm_j1_to_j6"), f"{label}.RIGHT upper mask", 6)
        require(all(type(item) is bool for item in lower + upper), f"{label}.RIGHT hard-limit masks must be bool")
        require(lower == [False] * 6, f"{label}.RIGHT must have no lower-limit violation")
        require(upper == [False, False, False, True, False, False], f"{label}.RIGHT must reject only upper arm_j4")
        overshoot = require_finite_vector(rejection.get("hard_limit_overshoot_rad_arm_j1_to_j6"), f"{label}.RIGHT overshoot", 6)
        require(overshoot[:3] == [0.0, 0.0, 0.0] and overshoot[3] > 0.0 and overshoot[4:] == [0.0, 0.0], f"{label}.RIGHT must overshoot only upper arm_j4")
        require_exact_readback(right, f"{label}.RIGHT")

    require(len(set(candidate_ids)) == 9, "candidate IDs must be unique")
    return candidate_ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k-artifact", type=Path, default=DEFAULT_K_ARTIFACT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    require(args.k_artifact.is_file(), f"missing K artifact: {args.k_artifact}")
    with args.k_artifact.open(encoding="utf-8") as stream:
        k_artifact = json.load(stream)
    require_mapping(k_artifact, "K artifact")
    candidate_ids = validate_k_artifact(k_artifact)

    args.output_root.mkdir(parents=True, exist_ok=True)
    route_artifact = {
        "schema": "a2_piper_base_v26_4_wave_c_route_v1",
        "status": "C_ROUTE_RESOLVED",
        "wave_c_section": "6.2",
        "k_artifact": str(args.k_artifact.resolve()),
        "k_typed_outcome": "BILATERAL_ASYMMETRIC_AT_arm_j4",
        "validated_candidate_count": len(candidate_ids),
        "validated_candidate_ids": candidate_ids,
        "canonicalization_permitted": False,
        "required_joint": "arm_j4",
        "required_side": "RIGHT",
        "posture_value": "NOT_FROZEN_NO_ADMITTED_NON_MIRROR_RIGHT_POSTURE",
        "typed_ceiling": "BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE",
        "wave_m_status": "NOT_RUN",
        "reason": "All admitted mirror-seeded candidates reach LEFT while RIGHT first rejects only at upper arm_j4; §6.2 forbids a false canonical-equivalence claim.",
    }
    identity_artifact = {
        "schema": "a2_piper_base_v26_4_canonical_identity_proof_v1",
        "status": "CANONICAL_IDENTITY_PROOF_NOT_RUN",
        "wave_c_section": "6.1",
        "k_artifact": str(args.k_artifact.resolve()),
        "k_typed_outcome": "BILATERAL_ASYMMETRIC_AT_arm_j4",
        "reason": "§6.1 is closed by the admitted directional hard-limit asymmetry; no admitted non-mirror RIGHT nominal posture exists to define a canonical identity proof.",
        "canonicalization_implemented": False,
        "proof_result": "NOT_RUN",
    }
    with (args.output_root / "c_route.json").open("w", encoding="utf-8") as stream:
        json.dump(route_artifact, stream, indent=2, sort_keys=True)
        stream.write("\n")
    with (args.output_root / "canonical_identity_proof.json").open("w", encoding="utf-8") as stream:
        json.dump(identity_artifact, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"c_route": str(args.output_root / "c_route.json"), "canonical_identity_proof": str(args.output_root / "canonical_identity_proof.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
