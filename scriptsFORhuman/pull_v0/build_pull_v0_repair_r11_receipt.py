#!/usr/bin/env python3
"""Build the immutable R11 receipt that invalidates the flawed Attempt12 plan."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

try:
    from .build_p1_anchor_stop_receipts import (
        EVIDENCE_ROOT,
        LOG_ROOT,
        ROOT,
        _artifact,
        _read_json,
        _sha256,
    )
except ImportError:
    from build_p1_anchor_stop_receipts import (
        EVIDENCE_ROOT,
        LOG_ROOT,
        ROOT,
        _artifact,
        _read_json,
        _sha256,
    )


R9_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R9_RECEIPT.json"
R9_RECEIPT_SHA256 = "3bed2ab4b7e4e21e3d0c05d07b36afa49d7e5a597c8c4efb41178e35f4d6cd69"
R10_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R10_RECEIPT.json"
R10_RECEIPT_SHA256 = "745f0106ba3503f8f2c729ef21576c19dae5e4a477c39c0b547ae6c5f8926301"
R10_SCHEMA = "pull_v0_repair_r10_receipt_v1"
R10_REVISION = "R10"
R11_SCHEMA = "pull_v0_repair_r11_receipt_v1"
R11_REVISION = "R11"
R11_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R11_RECEIPT.json"
R11_ROOT_CAUSE = "ATTEMPT12_PREPARATION_REPAIR_RECEIPT_PATH_MISMATCH"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"

ATTEMPT12_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT12_PLAN.json"
ATTEMPT12_PLAN_SHA256 = "2e4231c6f6a7862d094d5182857c37b9381b557b6760636c508e3fd87c648dbc"
ATTEMPT12_PLAN_IDENTITY_SHA256 = "435bc01e7ad08001390463911d0e450d43ced7110c855f3e3ea69b20006ebe93"
ATTEMPT12_INVALIDATION_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT12_PREPARATION_INVALIDATION.json"
)
ATTEMPT12_INVALIDATION_SHA256 = "0d82c848cab382f873a01f67eb88669efae4d4669fb67bbac42161532d280d78"
ATTEMPT12_CONFIG_PATH = LOG_ROOT / "attempt12/input/config.yaml"
ATTEMPT12_CONFIG_SHA256 = "c9e2bd493a2d20a89fc8f7414b18225f14aeb902d37b6c638a1a72fc77d1ee89"
ATTEMPT12_CHECKPOINT_PATH = LOG_ROOT / "attempt12/input/model_step_002500.pt"
ATTEMPT12_CHECKPOINT_SHA256 = "f000f13e817309f7b73e33c5c4d95076397debb992713e5613dce567bfda806d"

ATTEMPT12_ABSENT_RUNTIME_PATHS = {
    "process_receipt": LOG_ROOT / "attempt12/process_receipt.json",
    "log": LOG_ROOT / "attempt12/stdout_stderr.log",
    "summary": LOG_ROOT / "attempt12/eval/a2_hold_oracle_summary.json",
    "metrics": LOG_ROOT / "attempt12/eval/metrics_eval.json",
}


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing R11 receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _exact_artifact(path: Path, expected_sha256: str, label: str) -> dict[str, str]:
    artifact = _artifact(path)
    if artifact["sha256"] != expected_sha256:
        raise RuntimeError(
            f"{label} hash changed: expected={expected_sha256}, actual={artifact['sha256']}"
        )
    return artifact


def _validate_r10_parent() -> dict[str, Any]:
    artifact = _exact_artifact(R10_RECEIPT_PATH, R10_RECEIPT_SHA256, "R10 parent receipt")
    receipt = _read_json(R10_RECEIPT_PATH)
    parent = receipt.get("parent_receipt")
    trigger = receipt.get("trigger")
    if (
        receipt.get("schema_version") != R10_SCHEMA
        or receipt.get("repair_revision") != R10_REVISION
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
        or receipt.get("status") != "APPROVED_FOR_ATTEMPT12_PREPARATION_ONLY"
        or not isinstance(parent, Mapping)
        or parent.get("path") != str(R9_RECEIPT_PATH.relative_to(ROOT))
        or parent.get("sha256") != R9_RECEIPT_SHA256
        or parent.get("repair_revision") != "R9"
        or not isinstance(trigger, Mapping)
        or trigger.get("attempt") != 11
        or receipt.get("scope", {}).get("attempt12_prepared") is not False
        or receipt.get("scope", {}).get("attempt12_runtime_executed") is not False
        or receipt.get("scope", {}).get("pull_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("R10 parent receipt identity or preparation-only scope is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt12_invalidation() -> dict[str, Any]:
    artifact = _exact_artifact(
        ATTEMPT12_INVALIDATION_PATH,
        ATTEMPT12_INVALIDATION_SHA256,
        "Attempt12 preparation invalidation",
    )
    invalidation = _read_json(ATTEMPT12_INVALIDATION_PATH)
    plan = invalidation.get("plan")
    absence = invalidation.get("absence_of_runtime_artifacts")
    preserved = invalidation.get("preserved_inputs")
    if (
        invalidation.get("schema_version")
        != "pull_v0_p1_push_anchor_attempt12_preparation_invalidation_v1"
        or invalidation.get("status") != "SUPERSEDED_INVALID"
        or invalidation.get("attempt") != 12
        or invalidation.get("preparation_validity") != "PREPARATION_INVALID"
        or invalidation.get("probe_validity") != "NOT_RUN"
        or invalidation.get("runtime_validation") != "NOT_RUN"
        or invalidation.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or not isinstance(plan, Mapping)
        or plan.get("path") != str(ATTEMPT12_PLAN_PATH.relative_to(ROOT))
        or plan.get("sha256") != ATTEMPT12_PLAN_SHA256
        or plan.get("plan_sha256") != ATTEMPT12_PLAN_IDENTITY_SHA256
        or plan.get("attempt") != 12
        or plan.get("path_revision_mismatch") is not True
        or not isinstance(absence, Mapping)
        or any(absence.get(name) is not False for name in ATTEMPT12_ABSENT_RUNTIME_PATHS)
        or any(path.exists() for path in ATTEMPT12_ABSENT_RUNTIME_PATHS.values())
        or not isinstance(preserved, Mapping)
    ):
        raise RuntimeError("Attempt12 invalidation does not preserve the required invalid/no-runtime evidence.")
    config = preserved.get("config")
    checkpoint = preserved.get("checkpoint")
    if (
        not isinstance(config, Mapping)
        or config.get("path") != str(ATTEMPT12_CONFIG_PATH.relative_to(ROOT))
        or config.get("sha256") != ATTEMPT12_CONFIG_SHA256
        or not ATTEMPT12_CONFIG_PATH.is_file()
        or _sha256(ATTEMPT12_CONFIG_PATH) != ATTEMPT12_CONFIG_SHA256
        or not isinstance(checkpoint, Mapping)
        or checkpoint.get("path") != str(ATTEMPT12_CHECKPOINT_PATH.relative_to(ROOT))
        or checkpoint.get("sha256") != ATTEMPT12_CHECKPOINT_SHA256
        or not ATTEMPT12_CHECKPOINT_PATH.is_file()
        or _sha256(ATTEMPT12_CHECKPOINT_PATH) != ATTEMPT12_CHECKPOINT_SHA256
        or not ATTEMPT12_PLAN_PATH.is_file()
        or _sha256(ATTEMPT12_PLAN_PATH) != ATTEMPT12_PLAN_SHA256
    ):
        raise RuntimeError("Attempt12 plan or preserved inputs changed.")
    return {
        "artifact": artifact,
        "invalidation": invalidation,
        "plan_artifact": _artifact(ATTEMPT12_PLAN_PATH),
        "config_artifact": _artifact(ATTEMPT12_CONFIG_PATH),
        "checkpoint_artifact": _artifact(ATTEMPT12_CHECKPOINT_PATH),
    }


def _changed_files() -> dict[str, dict[str, Any]]:
    paths = {
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT12_PREPARATION_INVALIDATION.json": (
            "Record immutable Attempt12 preparation invalidation and absence of runtime artifacts."
        ),
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r11_receipt.py": (
            "Build and validate the immutable R11 preparation-only repair receipt."
        ),
        "gr00t/rl/tests/test_a2_pull_namespace.py": (
            "Guard exact Attempt12 invalidation, R11 ancestry, and plan serialization identity."
        ),
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": (
            "Serialize the exact validated repair receipt path and bind Attempt13 to R11; excluded to avoid receipt hash self-cycle."
        ),
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": (
            "Validate Attempt13 R11 ancestry and invalidation; excluded to avoid receipt hash self-cycle."
        ),
    }
    result: dict[str, dict[str, Any]] = {}
    for relative, reason in paths.items():
        if relative in {
            "scriptsFORhuman/pull_v0/run_p1_push_anchor.py",
            "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py",
        }:
            result[relative] = {
                "pre_sha256": None,
                "post_sha256": None,
                "reason": reason,
                "hash_binding": "EXCLUDED_TO_AVOID_R11_RECEIPT_SHA_SELF_CYCLE",
            }
            continue
        path = ROOT / relative
        result[relative] = {
            "pre_sha256": None,
            "post_sha256": _sha256(path) if path.is_file() else None,
            "reason": reason,
        }
    return result


def build_r11_receipt() -> dict[str, Any]:
    parent = _validate_r10_parent()
    invalidation = _validate_attempt12_invalidation()
    return {
        "schema_version": R11_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R11_REVISION,
        "status": "APPROVED_FOR_ATTEMPT13_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": R11_ROOT_CAUSE,
            "conclusion": (
                "The immutable Attempt12 preparation plan serialized the Repair R9 path while binding "
                "the Repair R10 receipt hash and revision. Attempt12 preparation is invalid; its inputs "
                "are preserved and no Attempt12 process or runtime artifacts exist."
            ),
            "flawed_plan_path": str(ATTEMPT12_PLAN_PATH.relative_to(ROOT)),
            "flawed_plan_sha256": ATTEMPT12_PLAN_SHA256,
            "flawed_serialized_repair_receipt_path": "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R9_RECEIPT.json",
            "flawed_serialized_repair_receipt_revision": "R10",
            "canonical_repair_receipt_path": "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R10_RECEIPT.json",
            "canonical_repair_receipt_revision": "R10",
        },
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R10_REVISION,
        },
        "trigger": {
            "attempt": 12,
            "root_cause": R11_ROOT_CAUSE,
            "invalidation_manifest": invalidation["artifact"],
        },
        "scope": {
            "authorized": (
                "Invalidate the flawed Attempt12 preparation plan, preserve its inputs and audit evidence, "
                "repair receipt-path serialization, and authorize Attempt13 preparation only from R11."
            ),
            "r10_parent_immutable": True,
            "attempt12_plan_immutable": True,
            "attempt12_preparation_invalid": True,
            "attempt12_prepared": False,
            "attempt12_runtime_executed": False,
            "attempt13_prepared": False,
            "attempt13_runtime_executed": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "attempt12_preparation_evidence": {
            "plan": invalidation["plan_artifact"],
            "plan_identity_sha256": ATTEMPT12_PLAN_IDENTITY_SHA256,
            "serialized_repair_receipt": {
                "path": "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R9_RECEIPT.json",
                "sha256": R10_RECEIPT_SHA256,
                "revision": R10_REVISION,
                "path_revision_mismatch": True,
            },
            "preserved_inputs": {
                "config": invalidation["config_artifact"],
                "checkpoint": invalidation["checkpoint_artifact"],
            },
            "runtime_artifacts_absent": {
                name: {
                    "path": str(path.relative_to(ROOT)),
                    "present": False,
                }
                for name, path in ATTEMPT12_ABSENT_RUNTIME_PATHS.items()
            },
            "scientific_verdict": "NOT_ASSESSED",
        },
        "changed_files": _changed_files(),
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "Attempt12 flawed plan and preserved input hash checks",
                "Attempt12 invalidation absence-of-runtime-artifacts checks",
                "Attempt13 runner and builder exact R11 ancestry checks",
                "git diff --check",
            ],
            "runtime_not_run_reason": (
                "R11 authorizes Attempt13 preparation only; no Attempt12 preparation, Attempt13 preparation, "
                "IsaacSim, GPU, or pull-mechanism runtime was executed."
            ),
        },
        "acceptance": {
            "r10_parent_exact": True,
            "attempt12_plan_exact_and_immutable": True,
            "attempt12_path_revision_mismatch_recorded": True,
            "attempt12_inputs_byte_identical_preserved": True,
            "attempt12_runtime_artifacts_absent": True,
            "attempt12_preparation_invalid": True,
            "attempt13_runner_exact_r11_binding": True,
            "attempt13_builder_exact_r11_binding": True,
            "attempt13_not_prepared_or_run": True,
            "pull_mechanism_verdict_not_assessed": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim or GPU runtime PASS is asserted for R11.",
            "No Attempt12 preparation or runtime was executed.",
            "No Attempt13 preparation or runtime was executed.",
            "No pull-mechanism verdict is asserted; this receipt records preparation invalidation only.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R11 pull-v0 repair receipt.")
    parser.add_argument("--output", type=Path, default=R11_RECEIPT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_r11_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
