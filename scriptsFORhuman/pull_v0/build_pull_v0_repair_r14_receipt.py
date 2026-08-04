#!/usr/bin/env python3
"""Build the immutable R14 receipt for the Attempt15 Hydra transport failure."""

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


R13_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R13_RECEIPT.json"
R13_RECEIPT_SHA256 = "afc3466fc270f9f5166a29a06c34fc6e39c853d0441a52d4539cd0cff0304c32"
R13_SCHEMA = "pull_v0_repair_r13_receipt_v1"
R13_REVISION = "R13"
R14_SCHEMA = "pull_v0_repair_r14_receipt_v1"
R14_REVISION = "R14"
R14_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R14_RECEIPT.json"
R14_ROOT_CAUSE = "ATTEMPT15_HYDRA_KIT_ARGS_TRANSPORT_FAILURE"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"

ATTEMPT15_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT15_RECEIPT.json"
ATTEMPT15_RECEIPT_SHA256 = "01c952a4402a887275ff53f02f26ea4a88f3f6c79ed0fc4388f4d32cbde763b0"
ATTEMPT15_SCHEMA = "pull_v0_p1_push_anchor_attempt_receipt_v15"
ATTEMPT15_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT15_PLAN.json"
ATTEMPT15_PLAN_SHA256 = "254a6937153960ceff5f5c71299ec7106349e544a7b252e31b107123da091bbc"
ATTEMPT15_PLAN_IDENTITY_SHA256 = "30568bef98d7dc1a54691c39640231e84a2e862fdefe6e382ca899275a53cceb"
ATTEMPT15_PROCESS_PATH = LOG_ROOT / "attempt15/process_receipt.json"
ATTEMPT15_PROCESS_SHA256 = "130460dddc02fc0f2f199b4a573ecafad49554513dce5fe4ee69e68fa152133b"
ATTEMPT15_STDOUT_PATH = LOG_ROOT / "attempt15/stdout_stderr.log"
ATTEMPT15_STDOUT_SHA256 = "91579492644ccba3239d89d43a0524bb1846edd152ace05d57bd9612f5e862bc"
SINGLE_GPU_KIT_ARGS = (
    "--/renderer/multiGpu/enabled=False "
    "--/renderer/multiGpu/autoEnable=False "
    "--/renderer/multiGpu/maxGpuCount=1"
)
PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE = "+a2_pull_v0_renderer_single_gpu=true"


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing R14 receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _exact_artifact(path: Path, expected_sha256: str, label: str) -> dict[str, str]:
    artifact = _artifact(path)
    if artifact["sha256"] != expected_sha256:
        raise RuntimeError(
            f"{label} hash changed: expected={expected_sha256}, actual={artifact['sha256']}"
        )
    return artifact


def _validate_r13_parent() -> dict[str, Any]:
    artifact = _exact_artifact(R13_RECEIPT_PATH, R13_RECEIPT_SHA256, "R13 parent receipt")
    receipt = _read_json(R13_RECEIPT_PATH)
    parent = receipt.get("parent_receipt")
    scope = receipt.get("scope")
    if (
        receipt.get("schema_version") != R13_SCHEMA
        or receipt.get("repair_revision") != R13_REVISION
        or receipt.get("status") != "APPROVED_FOR_ATTEMPT15_PREPARATION_ONLY"
        or receipt.get("runtime_validation") != "NOT_RUN"
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
        or not isinstance(parent, Mapping)
        or parent.get("path") != str(EVIDENCE_ROOT.joinpath("PULL_V0_REPAIR_R12_RECEIPT.json").relative_to(ROOT))
        or parent.get("sha256") != "676e0df6a8b3a9dca35ce53c41726df6ec64db57e6652f4b25e1b01131c833bb"
        or parent.get("repair_revision") != "R12"
        or not isinstance(scope, Mapping)
        or scope.get("attempt15_prepared") is not False
        or scope.get("attempt15_runtime_executed") is not False
        or scope.get("pull_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("R13 parent identity or Attempt15 preparation-only scope is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt15_failure() -> dict[str, Any]:
    receipt_artifact = _exact_artifact(
        ATTEMPT15_RECEIPT_PATH, ATTEMPT15_RECEIPT_SHA256, "Attempt15 invalidation receipt"
    )
    plan_artifact = _exact_artifact(ATTEMPT15_PLAN_PATH, ATTEMPT15_PLAN_SHA256, "Attempt15 plan")
    process_artifact = _exact_artifact(
        ATTEMPT15_PROCESS_PATH, ATTEMPT15_PROCESS_SHA256, "Attempt15 process receipt"
    )
    stdout_artifact = _exact_artifact(
        ATTEMPT15_STDOUT_PATH, ATTEMPT15_STDOUT_SHA256, "Attempt15 stdout/stderr"
    )
    receipt = _read_json(ATTEMPT15_RECEIPT_PATH)
    plan = _read_json(ATTEMPT15_PLAN_PATH)
    process = _read_json(ATTEMPT15_PROCESS_PATH)
    error = receipt.get("application_contract_error")
    evidence = receipt.get("evidence")
    gpu_observation = receipt.get("gpu_resource_observation")
    argv = plan.get("argv")
    if (
        receipt.get("schema_version") != ATTEMPT15_SCHEMA
        or receipt.get("attempt") != 15
        or receipt.get("status") != "PROBE_INVALID"
        or receipt.get("probe_validity") != "PROBE_INVALID"
        or receipt.get("runtime_validation") != "INVALIDATED_BEFORE_APPLAUNCHER"
        or receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or receipt.get("scientific_verdict_consumed") is not False
        or receipt.get("application_success") is not False
        or receipt.get("natural_exit") is not False
        or receipt.get("returncode") != 2
        or not isinstance(error, Mapping)
        or error.get("stage") != "BEFORE_APPLAUNCHER"
        or error.get("root_cause") != R14_ROOT_CAUSE
        or error.get("unrecognized_arguments") != ["--kit_args", SINGLE_GPU_KIT_ARGS]
        or error.get("summary_present") is not False
        or error.get("metrics_present") is not False
        or not isinstance(evidence, Mapping)
        or evidence.get("plan", {}).get("path") != str(ATTEMPT15_PLAN_PATH.relative_to(ROOT))
        or evidence.get("plan", {}).get("sha256") != ATTEMPT15_PLAN_SHA256
        or evidence.get("plan", {}).get("plan_sha256") != ATTEMPT15_PLAN_IDENTITY_SHA256
        or evidence.get("process_receipt", {}).get("path") != str(ATTEMPT15_PROCESS_PATH.relative_to(ROOT))
        or evidence.get("process_receipt", {}).get("sha256") != ATTEMPT15_PROCESS_SHA256
        or evidence.get("stdout", {}).get("path") != str(ATTEMPT15_STDOUT_PATH.relative_to(ROOT))
        or evidence.get("stdout", {}).get("sha256") != ATTEMPT15_STDOUT_SHA256
        or evidence.get("summary") is not None
        or evidence.get("metrics") is not None
        or not isinstance(gpu_observation, Mapping)
        or gpu_observation.get("applauncher_started") is not False
        or gpu_observation.get("isaacsim_started") is not False
        or gpu_observation.get("gpu_process_opened") is not False
        or gpu_observation.get("gpu_context_opened") is not False
        or gpu_observation.get("cuda_visible_devices") != "UNSET"
        or gpu_observation.get("selected_physical_gpu") != 4
        or gpu_observation.get("authorized_physical_gpus") != [4, 5, 6]
        or gpu_observation.get("gpu_memory_mib_by_index") != {str(index): 1 for index in range(8)}
        or gpu_observation.get("gpu7_compute_authorized") is not False
        or plan.get("schema_version") != "pull_v0_p1_push_anchor_plan_v1"
        or plan.get("status") != "READY"
        or plan.get("attempt") != 15
        or plan.get("plan_sha256") != ATTEMPT15_PLAN_IDENTITY_SHA256
        or plan.get("repair_receipt", {}).get("path")
        != str(R13_RECEIPT_PATH.relative_to(ROOT))
        or plan.get("repair_receipt", {}).get("sha256") != R13_RECEIPT_SHA256
        or plan.get("repair_receipt", {}).get("revision") != R13_REVISION
        or plan.get("env", {}).get("CUDA_VISIBLE_DEVICES") != "UNSET"
        or not isinstance(argv, list)
        or "--kit_args" not in argv
        or SINGLE_GPU_KIT_ARGS not in argv
        or PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE in argv
        or process.get("schema_version") != "pull_v0_p1_push_anchor_process_v1"
        or process.get("attempt") != 15
        or process.get("returncode") != 2
        or process.get("natural_exit") is not False
        or process.get("application_success") is not False
        or process.get("plan_sha256") != ATTEMPT15_PLAN_IDENTITY_SHA256
        or process.get("repair_receipt_sha256") != R13_RECEIPT_SHA256
        or process.get("stdout_stderr_sha256") != ATTEMPT15_STDOUT_SHA256
        or process.get("summary_path") is not None
        or process.get("summary_sha256") is not None
        or process.get("metrics_path") is not None
        or process.get("metrics_sha256") is not None
    ):
        raise RuntimeError("Attempt15 immutable Hydra argument-transport failure evidence is invalid.")
    log_text = ATTEMPT15_STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    if "error: unrecognized arguments: --kit_args" not in log_text or SINGLE_GPU_KIT_ARGS not in log_text:
        raise RuntimeError("Attempt15 stdout does not preserve the exact Hydra unrecognized-arguments failure.")
    return {
        "receipt_artifact": receipt_artifact,
        "plan_artifact": plan_artifact,
        "process_artifact": process_artifact,
        "stdout_artifact": stdout_artifact,
        "receipt": receipt,
        "plan": plan,
        "process": process,
    }


def _changed_files() -> dict[str, dict[str, Any]]:
    paths = {
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT15_RECEIPT.json": (
            "Record the immutable Attempt15 Hydra argument-transport failure before AppLauncher startup."
        ),
        "gr00t/rl/eval_agent_trl.py": (
            "Consume the pull-v0 Hydra boolean and configure AppLauncher Namespace multi_gpu/kit_args fail-fast."
        ),
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r14_receipt.py": (
            "Build and validate the immutable R14 repair receipt."
        ),
        "gr00t/rl/tests/test_a2_pull_namespace.py": (
            "Guard the pull-v0 boolean transport, Attempt15 invalidation, and R14 ancestry."
        ),
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": (
            "Use the Hydra boolean transport for Attempt16 and bind R14; excluded to avoid receipt hash self-cycle."
        ),
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": (
            "Validate R14 ancestry and Attempt15 transport evidence; excluded to avoid receipt hash self-cycle."
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
                "hash_binding": "EXCLUDED_TO_AVOID_R14_RECEIPT_SHA_SELF_CYCLE",
            }
        else:
            path = ROOT / relative
            result[relative] = {
                "pre_sha256": None,
                "post_sha256": _sha256(path) if path.is_file() else None,
                "reason": reason,
            }
    return result


def build_r14_receipt() -> dict[str, Any]:
    parent = _validate_r13_parent()
    attempt15 = _validate_attempt15_failure()
    return {
        "schema_version": R14_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R14_REVISION,
        "status": "APPROVED_FOR_ATTEMPT16_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": R14_ROOT_CAUSE,
            "conclusion": (
                "Immutable Attempt15 failed before AppLauncher construction because raw AppLauncher "
                "--kit_args tokens were placed in Hydra-owned argv. Hydra rejected those tokens with an "
                "unrecognized-arguments error, so no IsaacSim, GPU, physics, or probe runtime started. "
                "The bounded repair carries a pull-v0-only boolean Hydra override and consumes it after "
                "AppLauncher argument parsing by setting args_cli.multi_gpu=False and the exact kit_args string."
            ),
            "failed_transport": "raw --kit_args in Hydra-owned argv",
            "replacement_transport": "Hydra boolean -> args_cli.multi_gpu/kit_args",
            "unrecognized_arguments": ["--kit_args", SINGLE_GPU_KIT_ARGS],
        },
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R13_REVISION,
        },
        "trigger": {
            "attempt": 15,
            "root_cause": R14_ROOT_CAUSE,
            "attempt_receipt": attempt15["receipt_artifact"],
            "immutable_runtime_artifacts": {
                "plan": attempt15["plan_artifact"],
                "process_receipt": attempt15["process_artifact"],
                "stdout": attempt15["stdout_artifact"],
            },
        },
        "scope": {
            "authorized": (
                "Replace only the raw Kit-argument transport with a pull-v0 Hydra boolean consumed through "
                "the official AppLauncher Namespace contract; preserve cuda:4, CUDA_VISIBLE_DEVICES UNSET, "
                "the physical GPU4-6 lease, all pull mechanics, fixture values, thresholds, host/local timeout "
                "budgets, and P1/P2 gates; authorize Attempt16 preparation only."
            ),
            "r13_parent_immutable": True,
            "attempt15_plan_immutable": True,
            "attempt15_hydra_failure_preserved": True,
            "attempt15_prepared": True,
            "attempt15_runtime_executed": False,
            "attempt15_probe_started": False,
            "attempt16_prepared": False,
            "attempt16_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
            "product_mechanics_changed": False,
            "fixture_changed": False,
            "thresholds_or_timeouts_changed": False,
            "p1_p2_gates_changed": False,
        },
        "attempt15_evidence": {
            "status": "PROBE_INVALID",
            "probe_validity": "PROBE_INVALID",
            "runtime_validation": "INVALIDATED_BEFORE_APPLAUNCHER",
            "pull_mechanism_verdict": "NOT_ASSESSED",
            "scientific_verdict_consumed": False,
            "application_success": False,
            "natural_exit": False,
            "returncode": 2,
            "application_contract_error": attempt15["receipt"]["application_contract_error"],
            "plan": attempt15["plan_artifact"],
            "process_receipt": attempt15["process_artifact"],
            "stdout": attempt15["stdout_artifact"],
            "summary": None,
            "metrics": None,
            "gpu_resource_observation": attempt15["receipt"]["gpu_resource_observation"],
        },
        "renderer_single_gpu_transport": {
            "mode": "Hydra boolean -> args_cli.multi_gpu/kit_args",
            "hydra_config_key": "a2_pull_v0_renderer_single_gpu",
            "hydra_override": PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE,
            "args_cli_multi_gpu": False,
            "args_cli_kit_args": SINGLE_GPU_KIT_ARGS,
            "raw_kit_args_in_argv": False,
            "absent_or_false_semantics": "Leave AppLauncher Namespace defaults unchanged.",
            "invalid_type_behavior": "Raise TypeError.",
            "conflicting_kit_args_behavior": "Raise ValueError without overwrite.",
        },
        "changed_files": _changed_files(),
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "pure helper absent/false/true/invalid/conflict tests",
                "Attempt15 exact plan/process/stdout and no-AppLauncher/GPU checks",
                "Attempt16 exact Hydra boolean argv and R14 ancestry checks",
                "git diff --check",
            ],
            "runtime_not_run_reason": (
                "R14 authorizes Attempt16 preparation only; no Attempt16 preparation, IsaacSim, GPU, or "
                "pull-mechanism runtime was executed."
            ),
        },
        "acceptance": {
            "r13_parent_exact": True,
            "attempt15_receipt_exact": True,
            "attempt15_plan_process_stdout_exact": True,
            "attempt15_hydra_argument_transport_failure": True,
            "attempt15_applauncher_not_started": True,
            "attempt15_gpu_process_context_not_opened": True,
            "attempt15_summary_metrics_absent": True,
            "hydra_boolean_transport_exact": True,
            "raw_kit_args_removed_from_attempt16_argv": True,
            "absent_false_defaults_unchanged": True,
            "invalid_type_and_conflict_fail_fast": True,
            "cuda4_and_host_stage_contract_preserved": True,
            "product_mechanics_unchanged": True,
            "fixture_thresholds_timeouts_gates_unchanged": True,
            "attempt16_runner_exact_r14_binding": True,
            "attempt16_not_prepared_or_run": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim, GPU, physics, or pull-mechanism runtime PASS is asserted for R14.",
            "No Attempt16 preparation or runtime was executed.",
            "No scientific verdict is consumed from Attempt15 because Hydra rejected argv before AppLauncher construction.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R14 pull-v0 repair receipt.")
    parser.add_argument("--output", type=Path, default=R14_RECEIPT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_r14_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
