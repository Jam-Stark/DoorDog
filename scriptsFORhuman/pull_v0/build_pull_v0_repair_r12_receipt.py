#!/usr/bin/env python3
"""Build the immutable R12 receipt for Attempt13 Hydra composition failure."""

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


R10_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R10_RECEIPT.json"
R10_RECEIPT_SHA256 = "745f0106ba3503f8f2c729ef21576c19dae5e4a477c39c0b547ae6c5f8926301"
R11_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R11_RECEIPT.json"
R11_RECEIPT_SHA256 = "4c50d52e25658e296b3101b283bb2eb57e7d9f5747dedb8a8b76a22783e563a4"
R11_SCHEMA = "pull_v0_repair_r11_receipt_v1"
R11_REVISION = "R11"
R12_SCHEMA = "pull_v0_repair_r12_receipt_v1"
R12_REVISION = "R12"
R12_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R12_RECEIPT.json"
R12_ROOT_CAUSE = "ATTEMPT13_HYDRA_STRUCT_CONFIG_MISSING_PLUS_OVERRIDE"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"

ATTEMPT13_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT13_RECEIPT.json"
ATTEMPT13_RECEIPT_SHA256 = "f85e1d177b5e3422ed99f4de250187ad9e7186f7034d9b79e1d1cd339b779cd5"
ATTEMPT13_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT13_PLAN.json"
ATTEMPT13_PLAN_SHA256 = "25c106d21b399add34a182a031804ee6bc4e7aef884af457d10225dedd73e353"
ATTEMPT13_PLAN_IDENTITY_SHA256 = "3aa964ac867e122b787518058da8ff9665315ea31b6fab9156010e5478ae4a5b"
ATTEMPT13_PROCESS_PATH = LOG_ROOT / "attempt13/process_receipt.json"
ATTEMPT13_PROCESS_SHA256 = "fc23b6f83adad04f4ede47397fcff3856abaceccd99b861aaeb6efa49b472b7e"
ATTEMPT13_LOG_PATH = LOG_ROOT / "attempt13/stdout_stderr.log"
ATTEMPT13_LOG_SHA256 = "c7012546d0bd515a60d58ee4d554ef998cc361716408961ad84a3d0c37c782c6"
ATTEMPT13_CONFIG_PATH = LOG_ROOT / "attempt13/input/config.yaml"
ATTEMPT13_CONFIG_SHA256 = "c9e2bd493a2d20a89fc8f7414b18225f14aeb902d37b6c638a1a72fc77d1ee89"
ATTEMPT13_CHECKPOINT_PATH = LOG_ROOT / "attempt13/input/model_step_002500.pt"
ATTEMPT13_CHECKPOINT_SHA256 = "f000f13e817309f7b73e33c5c4d95076397debb992713e5613dce567bfda806d"
ATTEMPT13_ERROR_TYPE = "ConfigCompositionException"
ATTEMPT13_BAD_OVERRIDE = "env.config.max_stage_time=[400,100,100,100,100,200]"
ATTEMPT13_MISSING_PLUS_OVERRIDE = "+env.config.max_stage_time=[400,100,100,100,100,200]"


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing R12 receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _exact_artifact(path: Path, expected_sha256: str, label: str) -> dict[str, str]:
    artifact = _artifact(path)
    if artifact["sha256"] != expected_sha256:
        raise RuntimeError(
            f"{label} hash changed: expected={expected_sha256}, actual={artifact['sha256']}"
        )
    return artifact


def _validate_r11_parent() -> dict[str, Any]:
    artifact = _exact_artifact(R11_RECEIPT_PATH, R11_RECEIPT_SHA256, "R11 parent receipt")
    receipt = _read_json(R11_RECEIPT_PATH)
    parent = receipt.get("parent_receipt")
    trigger = receipt.get("trigger")
    scope = receipt.get("scope")
    if (
        receipt.get("schema_version") != R11_SCHEMA
        or receipt.get("repair_revision") != R11_REVISION
        or receipt.get("status") != "APPROVED_FOR_ATTEMPT13_PREPARATION_ONLY"
        or receipt.get("runtime_validation") != "NOT_RUN"
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
        or not isinstance(parent, Mapping)
        or parent.get("path") != str(R10_RECEIPT_PATH.relative_to(ROOT))
        or parent.get("sha256") != R10_RECEIPT_SHA256
        or parent.get("repair_revision") != "R10"
        or not isinstance(trigger, Mapping)
        or trigger.get("attempt") != 12
        or not isinstance(scope, Mapping)
        or scope.get("attempt13_prepared") is not False
        or scope.get("attempt13_runtime_executed") is not False
        or scope.get("pull_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("R11 parent identity or Attempt13 preparation-only scope is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt13_failure() -> dict[str, Any]:
    receipt_artifact = _exact_artifact(
        ATTEMPT13_RECEIPT_PATH, ATTEMPT13_RECEIPT_SHA256, "Attempt13 receipt"
    )
    plan_artifact = _exact_artifact(ATTEMPT13_PLAN_PATH, ATTEMPT13_PLAN_SHA256, "Attempt13 plan")
    process_artifact = _exact_artifact(
        ATTEMPT13_PROCESS_PATH, ATTEMPT13_PROCESS_SHA256, "Attempt13 process receipt"
    )
    log_artifact = _exact_artifact(ATTEMPT13_LOG_PATH, ATTEMPT13_LOG_SHA256, "Attempt13 log")
    config_artifact = _exact_artifact(
        ATTEMPT13_CONFIG_PATH, ATTEMPT13_CONFIG_SHA256, "Attempt13 materialized config"
    )
    checkpoint_artifact = _exact_artifact(
        ATTEMPT13_CHECKPOINT_PATH, ATTEMPT13_CHECKPOINT_SHA256, "Attempt13 materialized checkpoint"
    )
    receipt = _read_json(ATTEMPT13_RECEIPT_PATH)
    plan = _read_json(ATTEMPT13_PLAN_PATH)
    process = _read_json(ATTEMPT13_PROCESS_PATH)
    application_error = receipt.get("application_contract_error")
    if (
        receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v13"
        or receipt.get("attempt") != 13
        or receipt.get("status") != "APPLICATION_CONFIG_ERROR_BEFORE_PROBE"
        or receipt.get("probe_validity") != "NOT_RUN"
        or receipt.get("runtime_validation") != "NOT_RUN"
        or receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or receipt.get("application_success") is not False
        or receipt.get("natural_exit") is not False
        or not isinstance(application_error, Mapping)
        or application_error.get("exception_type") != ATTEMPT13_ERROR_TYPE
        or application_error.get("root_cause") != R12_ROOT_CAUSE
        or application_error.get("attempted_override") != ATTEMPT13_BAD_OVERRIDE
        or application_error.get("missing_plus_override") != ATTEMPT13_MISSING_PLUS_OVERRIDE
        or plan.get("attempt") != 13
        or plan.get("plan_sha256") != ATTEMPT13_PLAN_IDENTITY_SHA256
        or plan.get("repair_receipt", {}).get("path")
        != str(R11_RECEIPT_PATH.relative_to(ROOT))
        or plan.get("repair_receipt", {}).get("sha256") != R11_RECEIPT_SHA256
        or ATTEMPT13_BAD_OVERRIDE not in plan.get("argv", [])
        or ATTEMPT13_MISSING_PLUS_OVERRIDE in plan.get("argv", [])
        or plan.get("resolved_config", {}).get("sha256") != ATTEMPT13_CONFIG_SHA256
        or plan.get("checkpoint", {}).get("sha256") != ATTEMPT13_CHECKPOINT_SHA256
        or plan.get("host_stage_time_contract", {}).get("max_stage_time_steps")
        != [400, 100, 100, 100, 100, 200]
        or process.get("schema_version") != "pull_v0_p1_push_anchor_process_v1"
        or process.get("attempt") != 13
        or process.get("plan_sha256") != ATTEMPT13_PLAN_IDENTITY_SHA256
        or process.get("repair_receipt_sha256") != R11_RECEIPT_SHA256
        or process.get("stdout_stderr_sha256") != ATTEMPT13_LOG_SHA256
        or process.get("application_success") is not False
        or process.get("natural_exit") is not False
        or process.get("returncode") != 1
        or process.get("required_summary_present") is not False
        or process.get("required_metrics_present") is not False
        or process.get("summary_path") is not None
        or process.get("summary_sha256") is not None
        or process.get("metrics_path") is not None
        or process.get("metrics_sha256") is not None
    ):
        raise RuntimeError("Attempt13 immutable application-config failure evidence is invalid.")
    log_text = ATTEMPT13_LOG_PATH.read_text(encoding="utf-8", errors="replace")
    if (
        f"hydra.errors.{ATTEMPT13_ERROR_TYPE}" not in log_text
        or "Could not override 'env.config.max_stage_time'." not in log_text
        or f"To append to your config use {ATTEMPT13_MISSING_PLUS_OVERRIDE}" not in log_text
    ):
        raise RuntimeError("Attempt13 log does not preserve the exact missing-plus Hydra error.")
    return {
        "receipt_artifact": receipt_artifact,
        "plan_artifact": plan_artifact,
        "process_artifact": process_artifact,
        "log_artifact": log_artifact,
        "config_artifact": config_artifact,
        "checkpoint_artifact": checkpoint_artifact,
        "receipt": receipt,
        "plan": plan,
        "process": process,
    }


def _changed_files() -> dict[str, dict[str, Any]]:
    paths = {
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT13_RECEIPT.json": (
            "Record the immutable Attempt13 application-config failure before probe startup."
        ),
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r12_receipt.py": (
            "Build and validate the immutable R12 repair receipt."
        ),
        "gr00t/rl/tests/test_a2_pull_namespace.py": (
            "Guard exact Attempt13 missing-plus evidence, R12 ancestry, and append-form argv."
        ),
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": (
            "Use the Hydra append-form max_stage_time override and bind Attempt14 to R12; excluded to avoid receipt hash self-cycle."
        ),
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": (
            "Validate Attempt14 R12 ancestry and immutable Attempt13 application evidence; excluded to avoid receipt hash self-cycle."
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
                "hash_binding": "EXCLUDED_TO_AVOID_R12_RECEIPT_SHA_SELF_CYCLE",
            }
            continue
        path = ROOT / relative
        result[relative] = {
            "pre_sha256": None,
            "post_sha256": _sha256(path) if path.is_file() else None,
            "reason": reason,
        }
    return result


def build_r12_receipt() -> dict[str, Any]:
    parent = _validate_r11_parent()
    attempt13 = _validate_attempt13_failure()
    return {
        "schema_version": R12_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R12_REVISION,
        "status": "APPROVED_FOR_ATTEMPT14_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": R12_ROOT_CAUSE,
            "conclusion": (
                "Immutable Attempt13 failed during Hydra composition before probe startup because the "
                "struct config rejected env.config.max_stage_time without the append prefix. The "
                "materialized config and host-stage contract remained unchanged; the runner must use the "
                "exact +env.config.max_stage_time override for Attempt14 preparation."
            ),
            "exception_type": ATTEMPT13_ERROR_TYPE,
            "attempted_override": ATTEMPT13_BAD_OVERRIDE,
            "missing_plus_override": ATTEMPT13_MISSING_PLUS_OVERRIDE,
        },
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R11_REVISION,
        },
        "trigger": {
            "attempt": 13,
            "root_cause": R12_ROOT_CAUSE,
            "attempt_receipt": attempt13["receipt_artifact"],
            "immutable_runtime_artifacts": {
                "plan": attempt13["plan_artifact"],
                "process_receipt": attempt13["process_artifact"],
                "log": attempt13["log_artifact"],
            },
        },
        "scope": {
            "authorized": (
                "Correct only the Hydra argv serialization to append env.config.max_stage_time, preserve "
                "the materialized config and host-stage values, and authorize Attempt14 preparation only."
            ),
            "r11_parent_immutable": True,
            "attempt13_plan_immutable": True,
            "attempt13_application_error_preserved": True,
            "attempt13_prepared": True,
            "attempt13_runtime_executed": False,
            "attempt13_probe_started": False,
            "attempt14_prepared": False,
            "attempt14_runtime_executed": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "attempt13_evidence": {
            "status": "APPLICATION_CONFIG_ERROR_BEFORE_PROBE",
            "probe_validity": "NOT_RUN",
            "runtime_validation": "NOT_RUN",
            "pull_mechanism_verdict": "NOT_ASSESSED",
            "application_success": False,
            "natural_exit": False,
            "returncode": 1,
            "exception_type": ATTEMPT13_ERROR_TYPE,
            "root_cause": R12_ROOT_CAUSE,
            "attempted_override": ATTEMPT13_BAD_OVERRIDE,
            "missing_plus_override": ATTEMPT13_MISSING_PLUS_OVERRIDE,
            "summary_present": False,
            "metrics_present": False,
            "plan": attempt13["plan_artifact"],
            "process_receipt": attempt13["process_artifact"],
            "log": attempt13["log_artifact"],
            "config": attempt13["config_artifact"],
            "checkpoint": attempt13["checkpoint_artifact"],
            "host_stage_time_steps": [400, 100, 100, 100, 100, 200],
        },
        "changed_files": _changed_files(),
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "Attempt13 exact plan/process/log/error and no-summary/no-metrics checks",
                "Attempt14 runner and builder exact R12 ancestry checks",
                "append-form max_stage_time argv check",
                "git diff --check",
            ],
            "runtime_not_run_reason": (
                "R12 authorizes Attempt14 preparation only; no Attempt14 preparation, IsaacSim, GPU, or "
                "pull-mechanism runtime was executed."
            ),
        },
        "acceptance": {
            "r11_parent_exact": True,
            "attempt13_receipt_exact": True,
            "attempt13_plan_process_log_exact": True,
            "attempt13_application_success_false": True,
            "attempt13_natural_exit_false": True,
            "attempt13_config_composition_exception": True,
            "attempt13_missing_plus_root_cause_exact": True,
            "attempt13_probe_not_run": True,
            "attempt13_pull_verdict_not_assessed": True,
            "append_form_override_required": True,
            "attempt14_runner_exact_r12_binding": True,
            "attempt14_not_prepared_or_run": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim or GPU runtime PASS is asserted for R12.",
            "No Attempt14 preparation or runtime was executed.",
            "No pull-mechanism verdict is asserted because Attempt13 failed before probe startup.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R12 pull-v0 repair receipt.")
    parser.add_argument("--output", type=Path, default=R12_RECEIPT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_r12_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
