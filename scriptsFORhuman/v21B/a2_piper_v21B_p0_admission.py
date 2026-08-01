"""No-simulation P0 admission for v21-B source/config bindings."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from ._v21b_common import (
    V21B_CELL_ORDER,
    V21B_PLAN_ID,
    V21B_WARM_START_PATH,
    V21B_WARM_START_SHA256,
    V21BError,
    config_for_cell,
    read_yaml,
    sha256_file,
    validate_resolved_v21b_parity,
)
from .a2_piper_v21B_schemas import artifact_payload, schema


def validate_guard_values(*, plan_id: str, theta_send_rad: float, tolerance_rad: float, root_margin_m: float, soft_phase_end_batch: int, crossing_base_component: float, crossing_shortfall_gain: float, crossing_mode: str, send_latch_enabled: bool) -> dict[str, Any]:
    """Mirror the fail-fast P0-G contract without constructing IsaacSim."""

    if plan_id != V21B_PLAN_ID:
        if plan_id == "base_v20_R1_policy_behavior_v1":
            if theta_send_rad != 0.90:
                raise V21BError("v20 R1 guard rejects theta values other than 0.90")
            if tolerance_rad != 0.05 or root_margin_m != 0.03 or soft_phase_end_batch != 500 or crossing_base_component != 1.0 or crossing_shortfall_gain != 1.0 or crossing_mode not in ("penalty", "terminal") or send_latch_enabled is not True:
                raise V21BError("v20 R1 guard values are not byte-compatible")
            return {"plan_id": plan_id, "theta_send_rad": theta_send_rad, "legacy_v20": True}
        raise V21BError(f"unsupported v21-B guard plan id: {plan_id!r}")
    if not 0.90 <= theta_send_rad <= 1.30:
        raise V21BError(f"v21-B plan {V21B_PLAN_ID!r} theta must lie in [0.90,1.30]")
    if tolerance_rad != 0.05 or root_margin_m != 0.03 or soft_phase_end_batch != 500:
        raise V21BError("v21-B guard schedule/tolerance/margin is not frozen")
    if crossing_base_component != 1.0 or crossing_shortfall_gain != 1.0:
        raise V21BError("v21-B crossing component constants must be 1.0/1.0")
    if crossing_mode not in ("penalty", "terminal") or send_latch_enabled is not True:
        raise V21BError("v21-B enabled path requires penalty/terminal mode and send latch")
    return {"plan_id": plan_id, "theta_send_rad": theta_send_rad, "schedule": [0, 500], "send_latch": True}


def build_p0_admission(repo_root: Path, *, warm_start_path: Path | None = None, source_lock: Mapping[str, Any] | None = None) -> dict[str, Any]:
    root = repo_root.resolve()
    validate_resolved_v21b_parity(root)
    warm = warm_start_path or root / V21B_WARM_START_PATH
    if not warm.is_file() or warm.is_symlink():
        raise V21BError(f"v21-B warm start is missing or not regular: {warm}")
    if sha256_file(warm) != V21B_WARM_START_SHA256:
        raise V21BError("v21-B warm-start SHA-256 does not match the signed handoff")
    rows: list[dict[str, Any]] = []
    for cell in V21B_CELL_ORDER:
        path = config_for_cell(root, cell)
        config = read_yaml(path)
        env = config["env"]["config"]
        validate_guard_values(
            plan_id=env["a2_v20_R1_plan_id"],
            theta_send_rad=env["a2_v20_send_hinge_threshold"],
            tolerance_rad=env["a2_v20_send_hinge_tolerance"],
            root_margin_m=env["a2_v20_pre_send_root_x_margin"],
            soft_phase_end_batch=env["a2_v20_R1_soft_phase_end_batch"],
            crossing_base_component=env["a2_v20_R1_crossing_base_component"],
            crossing_shortfall_gain=env["a2_v20_R1_crossing_shortfall_gain"],
            crossing_mode=env["a2_v20_pre_send_crossing_mode"],
            send_latch_enabled=env["a2_v20_send_latch_enabled"],
        )
        rows.append({
            "cell": cell,
            "config_path": str(path.relative_to(root)),
            "config_sha256": sha256_file(path),
            "theta_send_rad": env["a2_v20_send_hinge_threshold"],
            "arm_profile": config["v21b_arm_profile"],
            "arm_tie": bool(env["a2_v20_arm_tie_enabled"]),
            "latch_mode": env["a2_corridor_latch_mode"],
            "formal_launchable": bool(config["v21b_formal_launchable"]),
        })
    payload_fields: dict[str, Any] = {
        "source_checkpoint_sha256": V21B_WARM_START_SHA256,
        "warm_start_path": str(warm.relative_to(root)),
        "warm_start_sha256": V21B_WARM_START_SHA256,
        "source_file_sha256": sha256_file(root / "gr00t/rl/envs/door/door_open_a2_base.py"),
        "cells": rows,
        "config_sha256_by_cell": {row["cell"]: row["config_sha256"] for row in rows},
        "legal_gpus": [0, 1, 2, 3, 4, 5, 6],
        "forbidden_gpus": [7],
    }
    if source_lock is not None:
        from .a2_piper_v21B_schemas import validate_artifact
        validate_artifact(source_lock, expected_schema=schema("source_lock"))
        payload_fields["source_lock_sha256"] = source_lock.get("source_lock_sha256")
    return artifact_payload(
        "p0_admission",
        status="STATIC_PASS",
        **payload_fields,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    print(__import__("json").dumps(build_p0_admission(args.repo_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


run_p0_admission = build_p0_admission

__all__ = ["validate_guard_values", "build_p0_admission", "run_p0_admission"]
