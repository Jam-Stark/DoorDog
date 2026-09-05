#!/usr/bin/env python3
"""Lock the v26-8 r3a G1 transition-verifier amendment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED_CHANGED = {
    "scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md": "authority_appendix_15_g1_transition_contract",
    "scriptsFORhuman/v26_8/v26_8_g1_reduce.py": "exact_pending_and_float32_scale_transition_verifier",
    "scriptsFORhuman/v26_8/v26_8_orchestrate.sh": "r3a_wave1_roots_and_external_r3_g1_evidence",
}
R3A_SUPPORT = {
    "gr00t/rl/tests/test_a2_v26_8_g1_reduce.py": "g1_transition_verifier_unit_proof",
    "scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904_r3.md": "r3_runtime_evidence",
    "scriptsFORhuman/v26_8/v26_8_r3a_verify.py": "r3a_contract_verifier",
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
    require(baseline.get("status") == "STATIC_PASS", "r3 source lock is not STATIC_PASS")
    locked = baseline.get("source_lock")
    require(isinstance(locked, dict) and locked, "r3 source lock is missing")

    unchanged: list[dict[str, str]] = []
    changed: list[dict[str, str]] = []
    for relative, baseline_sha256 in sorted(locked.items()):
        path = ROOT / relative
        require(path.is_file(), f"r3-locked path is missing: {relative}")
        current_sha256 = digest(path)
        row = {
            "path": relative,
            "baseline_sha256": baseline_sha256,
            "current_sha256": current_sha256,
        }
        if relative in ALLOWED_CHANGED:
            require(current_sha256 != baseline_sha256, f"expected r3a change is absent: {relative}")
            row["classification"] = ALLOWED_CHANGED[relative]
            changed.append(row)
        else:
            require(current_sha256 == baseline_sha256, f"out-of-scope r3a change: {relative}")
            unchanged.append(row)

    require(
        {row["path"] for row in changed} == set(ALLOWED_CHANGED),
        "r3a changed-file set does not match its allowlist",
    )
    support: list[dict[str, str]] = []
    for relative, classification in sorted(R3A_SUPPORT.items()):
        path = ROOT / relative
        require(path.is_file(), f"r3a support path is missing: {relative}")
        support.append(
            {
                "path": relative,
                "current_sha256": digest(path),
                "classification": classification,
            }
        )

    payload = {
        "schema": "a2_piper_base_v26_8_r3a_contract_lock_v1",
        "status": "R3A_CONTRACT_PASS",
        "baseline_source_lock": str(args.baseline.resolve()),
        "baseline_git_head": baseline.get("git_head"),
        "scope": "g1_exact_scale_transition_verification_and_reducer_only_readjudication",
        "r3_core_and_experiment_configs_unchanged": True,
        "thresholds_reward_scales_stages_sources_unchanged": True,
        "unchanged_locked_files": unchanged,
        "allowed_changed_files": changed,
        "new_r3a_support_files": support,
        "readjudication_contract": {
            "isaac_relaunch": False,
            "immutable_g1_root": "logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3/G1_k_wiring",
            "historical_outer_receipt_preserved": ".ai/runtime/runs/v26_8_g1_wiring_r3/RUN_RECEIPT.json",
            "verifier": "exact per-row pending semantics and torch float32 hysteresis/clip transition",
        },
    }
    require(not args.output.exists(), f"refusing to overwrite r3a contract lock: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
