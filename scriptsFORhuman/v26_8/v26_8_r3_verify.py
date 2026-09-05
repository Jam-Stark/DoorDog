#!/usr/bin/env python3
"""Lock the narrowly amended v26-8 r3 aggregation/consumption contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED_CHANGED = {
    "gr00t/rl/envs/door/door_open_a2_base.py": "cross_side_pending_episode_aggregation_and_atomic_consumption",
    "gr00t/rl/tests/test_a2_v26_8_penalty_curriculum.py": "r3_aggregation_consumption_unit_proof",
    "scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md": "authority_appendix_14_r3_protocol",
    "scriptsFORhuman/v26_8/v26_8_orchestrate.sh": "r3_runtime_roots_and_gates",
}
R3_SUPPORT = {
    "scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904.md": "r2_runtime_evidence",
    "scriptsFORhuman/v26_8/v26_8_r3_verify.py": "r3_contract_verifier",
}


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    require(baseline.get("status") == "STATIC_PASS", "r2 source lock is not STATIC_PASS")
    locked = baseline.get("source_lock")
    require(isinstance(locked, dict) and locked, "r2 source lock is missing")

    unchanged: list[dict[str, str]] = []
    changed: list[dict[str, str]] = []
    for relative, baseline_sha256 in sorted(locked.items()):
        path = ROOT / relative
        require(path.is_file(), f"r2-locked path is missing: {relative}")
        current_sha256 = digest(path)
        row = {
            "path": relative,
            "baseline_sha256": baseline_sha256,
            "current_sha256": current_sha256,
        }
        if relative in ALLOWED_CHANGED:
            require(current_sha256 != baseline_sha256, f"expected r3 change is absent: {relative}")
            row["classification"] = ALLOWED_CHANGED[relative]
            changed.append(row)
        else:
            require(current_sha256 == baseline_sha256, f"out-of-scope r3 change: {relative}")
            unchanged.append(row)

    require(
        {row["path"] for row in changed} == set(ALLOWED_CHANGED),
        "r3 changed-file set does not match its allowlist",
    )
    support: list[dict[str, str]] = []
    for relative, classification in sorted(R3_SUPPORT.items()):
        path = ROOT / relative
        require(path.is_file(), f"r3 support path is missing: {relative}")
        support.append(
            {
                "path": relative,
                "current_sha256": digest(path),
                "classification": classification,
            }
        )

    payload = {
        "schema": "a2_piper_base_v26_8_r3_contract_lock_v1",
        "status": "R3_CONTRACT_PASS",
        "baseline_source_lock": str(args.baseline.resolve()),
        "baseline_git_head": baseline.get("git_head"),
        "scope": "cross_side_episode_aggregation_and_consumption_only",
        "experiment_configs_unchanged": True,
        "thresholds_reward_scales_stages_sources_unchanged": True,
        "unchanged_locked_files": unchanged,
        "allowed_changed_files": changed,
        "new_r3_support_files": support,
        "aggregation_contract": {
            "record": "accumulate natural completed episodes by side from same-episode start/max pairs",
            "skip": "retain both pending numerator/denominator counters while either side is empty",
            "consume": "when both sides are non-empty, compute side rates and atomically clear both sides once",
        },
    }
    require(not args.output.exists(), f"refusing to overwrite r3 contract lock: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
