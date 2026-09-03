#!/usr/bin/env python3
"""Prove that the v26-8 r2 relaunch leaves the experiment contract unchanged."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED_CHANGED = {
    "scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md": "authority_appendix_13_r2_protocol",
    "scriptsFORhuman/v26_8/v26_8_capture_train.py": "supervisor_child_process_receipt",
    "scriptsFORhuman/v26_8/v26_8_orchestrate.sh": "r2_runtime_orchestration",
}
R2_SUPPORT = {
    "scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260903.md": "attempt_1_runtime_evidence",
    "scriptsFORhuman/v26_8/v26_8_p0_assets.py": "r2_asset_preflight",
    "scriptsFORhuman/v26_8/v26_8_r2_verify.py": "r2_contract_verifier",
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
    require(baseline.get("status") == "STATIC_PASS", "baseline source lock is not STATIC_PASS")
    locked = baseline.get("source_lock")
    require(isinstance(locked, dict) and locked, "baseline source lock is missing")

    unchanged: list[dict[str, str]] = []
    changed: list[dict[str, str]] = []
    for relative, baseline_sha256 in sorted(locked.items()):
        path = ROOT / relative
        require(path.is_file(), f"baseline-locked path is missing: {relative}")
        current_sha256 = digest(path)
        row = {
            "path": relative,
            "baseline_sha256": baseline_sha256,
            "current_sha256": current_sha256,
        }
        if relative in ALLOWED_CHANGED:
            require(
                current_sha256 != baseline_sha256,
                f"expected r2 support change is absent: {relative}",
            )
            row["classification"] = ALLOWED_CHANGED[relative]
            changed.append(row)
        else:
            require(
                current_sha256 == baseline_sha256,
                f"experiment contract changed after G0: {relative}",
            )
            unchanged.append(row)

    support: list[dict[str, str]] = []
    for relative, classification in sorted(R2_SUPPORT.items()):
        path = ROOT / relative
        require(path.is_file(), f"r2 support path is missing: {relative}")
        support.append(
            {
                "path": relative,
                "current_sha256": digest(path),
                "classification": classification,
            }
        )

    payload = {
        "schema": "a2_piper_base_v26_8_r2_contract_lock_v1",
        "status": "R2_CONTRACT_PASS",
        "baseline_source_lock": str(args.baseline.resolve()),
        "baseline_git_head": baseline.get("git_head"),
        "experiment_contract_unchanged": True,
        "unchanged_locked_files": unchanged,
        "allowed_changed_files": changed,
        "new_r2_support_files": support,
        "source_lock_delta_contract": (
            "Every baseline-locked experiment source/config/test/train/eval/reducer file "
            "is byte-identical. Only the frozen plan's r2 authority appendix, the "
            "orchestrator, and its child-process capture wrapper changed; attempt-1 "
            "evidence and r2 preflight/verification are listed separately."
        ),
    }
    require(not args.output.exists(), f"refusing to overwrite r2 contract lock: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
