#!/usr/bin/env python3
"""Build the immutable R13 receipt for the Attempt14 resource-stop repair."""

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


R12_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R12_RECEIPT.json"
R12_RECEIPT_SHA256 = "676e0df6a8b3a9dca35ce53c41726df6ec64db57e6652f4b25e1b01131c833bb"
R12_SCHEMA = "pull_v0_repair_r12_receipt_v1"
R12_REVISION = "R12"
R11_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R11_RECEIPT.json"
R11_RECEIPT_SHA256 = "4c50d52e25658e296b3101b283bb2eb57e7d9f5747dedb8a8b76a22783e563a4"
R13_SCHEMA = "pull_v0_repair_r13_receipt_v1"
R13_REVISION = "R13"
R13_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R13_RECEIPT.json"
R13_ROOT_CAUSE = "ATTEMPT14_RENDERER_MULTIGPU_RESOURCE_LEASE_VIOLATION"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"

ATTEMPT14_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT14_RECEIPT.json"
ATTEMPT14_RECEIPT_SHA256 = "60c007cf6267e42b66605217880adc24e638da744142e85e362a313ba4778638"
ATTEMPT14_SCHEMA = "pull_v0_p1_push_anchor_attempt_receipt_v14"
ATTEMPT14_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT14_PLAN.json"
ATTEMPT14_PLAN_SHA256 = "fce7011380089e4f8647dfccf5ed4a4c75b149001c0acc6b7dfbf8de02f4f3c4"
ATTEMPT14_PLAN_IDENTITY_SHA256 = "0e24e0c0d74b40791cb4b0d510426078202a62989d518a100ec9889c89d3f75d"
ATTEMPT14_STDOUT_PATH = LOG_ROOT / "attempt14/stdout_stderr.log"
ATTEMPT14_STDOUT_SHA256 = "ccc370f82c7dc2043b97d063788a2a5cf43e2c8755a3cc7388911ccd6172bbab"
ATTEMPT14_KIT_LOG_PATH = Path(
    "/home/baoquanc/anaconda3/envs/isaaclab/lib/python3.11/site-packages/"
    "isaacsim/kit/logs/Kit/Isaac-Sim/5.1/kit_20260804_041952.log"
)
ATTEMPT14_KIT_LOG_SHA256 = "0085e219a74f2c9f36fe32e65a38cc64fab039b656535af7f80209e44554511b"
ATTEMPT14_TRACE_TMP_PATH = LOG_ROOT / "attempt14/eval/stage2_5_step_trace.json.tmp"
ATTEMPT14_TRACE_TMP_BYTES = 1784450644
ATTEMPT14_SUMMARY_PATH = LOG_ROOT / "attempt14/eval/a2_hold_oracle_summary.json"
ATTEMPT14_METRICS_PATH = LOG_ROOT / "attempt14/eval/eval_to_log_metrics.json"
SINGLE_GPU_KIT_ARGS = (
    "--/renderer/multiGpu/enabled=False "
    "--/renderer/multiGpu/autoEnable=False "
    "--/renderer/multiGpu/maxGpuCount=1"
)


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing R13 receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _exact_artifact(path: Path, expected_sha256: str, label: str) -> dict[str, str]:
    artifact = _artifact(path)
    if artifact["sha256"] != expected_sha256:
        raise RuntimeError(
            f"{label} hash changed: expected={expected_sha256}, actual={artifact['sha256']}"
        )
    return artifact


def _validate_r12_parent() -> dict[str, Any]:
    artifact = _exact_artifact(R12_RECEIPT_PATH, R12_RECEIPT_SHA256, "R12 parent receipt")
    receipt = _read_json(R12_RECEIPT_PATH)
    parent = receipt.get("parent_receipt")
    scope = receipt.get("scope")
    if (
        receipt.get("schema_version") != R12_SCHEMA
        or receipt.get("repair_revision") != R12_REVISION
        or receipt.get("status") != "APPROVED_FOR_ATTEMPT14_PREPARATION_ONLY"
        or receipt.get("runtime_validation") != "NOT_RUN"
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
        or not isinstance(parent, Mapping)
        or parent.get("path") != str(R11_RECEIPT_PATH.relative_to(ROOT))
        or parent.get("sha256") != R11_RECEIPT_SHA256
        or parent.get("repair_revision") != "R11"
        or not isinstance(scope, Mapping)
        or scope.get("attempt14_prepared") is not False
        or scope.get("attempt14_runtime_executed") is not False
        or scope.get("pull_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("R12 parent identity or Attempt14 preparation-only scope is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt14_invalidation() -> dict[str, Any]:
    receipt_artifact = _exact_artifact(
        ATTEMPT14_RECEIPT_PATH, ATTEMPT14_RECEIPT_SHA256, "Attempt14 invalidation receipt"
    )
    plan_artifact = _exact_artifact(ATTEMPT14_PLAN_PATH, ATTEMPT14_PLAN_SHA256, "Attempt14 plan")
    stdout_artifact = _exact_artifact(
        ATTEMPT14_STDOUT_PATH, ATTEMPT14_STDOUT_SHA256, "Attempt14 stdout/stderr"
    )
    kit_log_artifact = _exact_artifact(
        ATTEMPT14_KIT_LOG_PATH, ATTEMPT14_KIT_LOG_SHA256, "Attempt14 Kit log"
    )
    receipt = _read_json(ATTEMPT14_RECEIPT_PATH)
    plan = _read_json(ATTEMPT14_PLAN_PATH)
    resource_stop = receipt.get("resource_stop")
    observed_launcher = receipt.get("observed_launcher")
    canonical_outputs = receipt.get("canonical_outputs")
    ignored_partial_outputs = receipt.get("ignored_partial_outputs")
    evidence = receipt.get("evidence")
    trace = evidence.get("interrupted_trace_tmp") if isinstance(evidence, Mapping) else None
    plan_repair = plan.get("repair_receipt")
    gpu_lease = plan.get("gpu_resource_lease")
    if (
        receipt.get("schema_version") != ATTEMPT14_SCHEMA
        or receipt.get("attempt") != 14
        or receipt.get("status") != "PROBE_INVALID"
        or receipt.get("probe_validity") != "PROBE_INVALID"
        or receipt.get("runtime_validation") != "INVALIDATED_BY_RESOURCE_STOP"
        or receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or receipt.get("scientific_verdict_consumed") is not False
        or not isinstance(evidence, Mapping)
        or not isinstance(trace, Mapping)
        or trace.get("bytes") != ATTEMPT14_TRACE_TMP_BYTES
        or trace.get("sha256") is not None
        or not isinstance(resource_stop, Mapping)
        or resource_stop.get("triggered") is not True
        or resource_stop.get("selected_physical_gpu") != 4
        or resource_stop.get("authorized_physical_gpus") != [4, 5, 6]
        or resource_stop.get("observed_gpu_indices") != list(range(8))
        or resource_stop.get("unauthorized_gpu_indices") != [0, 1, 2, 3, 7]
        or resource_stop.get("gpu7_compute_authorized") is not False
        or resource_stop.get("main_action") != "SIGINT_SENT_BY_MAIN"
        or resource_stop.get("child_state") != "DEFUNCT_AFTER_SIGINT"
        or not isinstance(observed_launcher, Mapping)
        or observed_launcher.get("app_launcher_device") != "cuda:4"
        or observed_launcher.get("physics_cuda_device") != 4
        or observed_launcher.get("renderer_active_gpu") != 4
        or observed_launcher.get("renderer_multi_gpu_enabled") is not True
        or observed_launcher.get("renderer_multi_gpu_auto_enable") is not True
        or observed_launcher.get("renderer_multi_gpu_max_gpu_count") is not None
        or observed_launcher.get("kit_command_flags")
        != [
            "--/renderer/multiGpu/enabled=True",
            "--/renderer/activeGpu=4",
            "--/physics/cudaDevice=4",
        ]
        or observed_launcher.get("plan_renderer_single_gpu_contract_present") is not False
        or observed_launcher.get("plan_cuda_visible_devices") != "UNSET"
        or not isinstance(canonical_outputs, Mapping)
        or canonical_outputs.get("process_receipt_present") is not False
        or canonical_outputs.get("summary_verdict_consumed") is not False
        or canonical_outputs.get("metrics_verdict_consumed") is not False
        or canonical_outputs.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or ignored_partial_outputs != [
            {
                "path": "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt14/eval/a2_hold_oracle_summary.json",
                "sha256": "015bf37371fc40e3cd341e4ed3b75560203f264985e903a58a7f3fd373ad6924",
                "reason": "Partial output after resource stop; not a canonical process-backed scientific verdict.",
            },
            {
                "path": "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt14/eval/eval_to_log_metrics.json",
                "sha256": "2d32c411ccd130ce74c8e33a1c30c5ed657ebf63e6459b08cd93e826694dc2aa",
                "reason": "Partial output after resource stop; not consumed as scientific evidence.",
            },
        ]
        or not isinstance(evidence.get("plan"), Mapping)
        or evidence["plan"].get("path") != str(ATTEMPT14_PLAN_PATH.relative_to(ROOT))
        or evidence["plan"].get("sha256") != ATTEMPT14_PLAN_SHA256
        or evidence["plan"].get("plan_sha256") != ATTEMPT14_PLAN_IDENTITY_SHA256
        or not isinstance(evidence.get("stdout"), Mapping)
        or evidence["stdout"].get("path") != str(ATTEMPT14_STDOUT_PATH.relative_to(ROOT))
        or evidence["stdout"].get("sha256") != ATTEMPT14_STDOUT_SHA256
        or not isinstance(evidence.get("kit_log"), Mapping)
        or evidence["kit_log"].get("path") != str(ATTEMPT14_KIT_LOG_PATH)
        or evidence["kit_log"].get("sha256") != ATTEMPT14_KIT_LOG_SHA256
        or plan.get("schema_version") != "pull_v0_p1_push_anchor_plan_v1"
        or plan.get("attempt") != 14
        or plan.get("status") != "READY"
        or plan.get("plan_sha256") != ATTEMPT14_PLAN_IDENTITY_SHA256
        or not isinstance(plan_repair, Mapping)
        or plan_repair.get("path") != str(R12_RECEIPT_PATH.relative_to(ROOT))
        or plan_repair.get("sha256") != R12_RECEIPT_SHA256
        or plan_repair.get("revision") != R12_REVISION
        or plan.get("env", {}).get("CUDA_VISIBLE_DEVICES") != "UNSET"
        or not isinstance(gpu_lease, Mapping)
        or gpu_lease.get("authorized_physical_devices") != [4, 5, 6]
        or gpu_lease.get("selected_physical_device") != 4
        or gpu_lease.get("gpu7_compute_authorized") is not False
        or "+device=cuda:4" not in plan.get("argv", [])
        or "+env.config.max_stage_time=[400,100,100,100,100,200]" not in plan.get("argv", [])
    ):
        raise RuntimeError("Attempt14 resource-stop invalidation or immutable plan evidence is invalid.")
    if not ATTEMPT14_TRACE_TMP_PATH.is_file() or ATTEMPT14_TRACE_TMP_PATH.stat().st_size != ATTEMPT14_TRACE_TMP_BYTES:
        raise RuntimeError("Attempt14 interrupted trace temporary size changed.")
    return {
        "receipt_artifact": receipt_artifact,
        "plan_artifact": plan_artifact,
        "stdout_artifact": stdout_artifact,
        "kit_log_artifact": kit_log_artifact,
        "receipt": receipt,
        "plan": plan,
    }


def _changed_files() -> dict[str, dict[str, Any]]:
    paths = {
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT14_RECEIPT.json": (
            "Record the immutable Attempt14 renderer multi-GPU resource-stop invalidation."
        ),
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r13_receipt.py": (
            "Build and validate the immutable R13 repair receipt."
        ),
        "gr00t/rl/tests/test_a2_pull_namespace.py": (
            "Guard exact Attempt14 invalidation evidence, R13 ancestry, and single-GPU Kit argv."
        ),
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": (
            "Serialize the R13 single-GPU Kit arguments and bind Attempt15; excluded to avoid receipt hash self-cycle."
        ),
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": (
            "Validate R13 ancestry and Attempt14 resource-stop evidence; excluded to avoid receipt hash self-cycle."
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
                "hash_binding": "EXCLUDED_TO_AVOID_R13_RECEIPT_SHA_SELF_CYCLE",
            }
        else:
            path = ROOT / relative
            result[relative] = {
                "pre_sha256": None,
                "post_sha256": _sha256(path) if path.is_file() else None,
                "reason": reason,
            }
    return result


def build_r13_receipt() -> dict[str, Any]:
    parent = _validate_r12_parent()
    attempt14 = _validate_attempt14_invalidation()
    return {
        "schema_version": R13_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R13_REVISION,
        "status": "APPROVED_FOR_ATTEMPT15_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": R13_ROOT_CAUSE,
            "conclusion": (
                "Immutable Attempt14 was invalidated after Isaac Sim's renderer opened compute contexts "
                "on GPUs outside the authorized physical lease [4, 5, 6], including unauthorized GPU7. "
                "AppLauncher selected cuda:4 for physics and active GPU4, but its default renderer multi-GPU "
                "settings remained enabled/auto-enabled with no max GPU count. The bounded repair is to "
                "serialize explicit single-GPU Kit arguments while preserving device cuda:4, the physical GPU "
                "lease, and all pull-v0 product thresholds and timeouts."
            ),
            "resource_stop_condition": "Physical GPU lease violation: renderer opened compute contexts on unauthorized GPUs.",
            "unauthorized_gpu_indices": [0, 1, 2, 3, 7],
            "gpu7_compute_authorized": False,
            "observed_launcher_multi_gpu": {
                "enabled": True,
                "auto_enable": True,
                "max_gpu_count": None,
            },
        },
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R12_REVISION,
        },
        "trigger": {
            "attempt": 14,
            "root_cause": R13_ROOT_CAUSE,
            "attempt_receipt": attempt14["receipt_artifact"],
            "immutable_runtime_artifacts": {
                "plan": attempt14["plan_artifact"],
                "stdout": attempt14["stdout_artifact"],
                "kit_log": attempt14["kit_log_artifact"],
            },
        },
        "scope": {
            "authorized": (
                "Correct only AppLauncher Kit argument serialization so renderer multi-GPU is disabled, "
                "auto-enable is disabled, and maxGpuCount is one; preserve cuda:4, the authorized physical "
                "GPU lease, pull-v0 product mechanics, thresholds, and timeout budgets; authorize Attempt15 "
                "preparation only."
            ),
            "r12_parent_immutable": True,
            "attempt14_plan_immutable": True,
            "attempt14_resource_stop_preserved": True,
            "attempt14_prepared": True,
            "attempt14_runtime_executed": True,
            "attempt14_probe_validity": "PROBE_INVALID",
            "attempt15_prepared": False,
            "attempt15_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
            "product_mechanics_changed": False,
            "thresholds_or_timeouts_changed": False,
        },
        "attempt14_evidence": {
            "status": "PROBE_INVALID",
            "probe_validity": "PROBE_INVALID",
            "runtime_validation": "INVALIDATED_BY_RESOURCE_STOP",
            "pull_mechanism_verdict": "NOT_ASSESSED",
            "scientific_verdict_consumed": False,
            "resource_stop": attempt14["receipt"].get("resource_stop"),
            "plan": attempt14["plan_artifact"],
            "stdout": attempt14["stdout_artifact"],
            "kit_log": attempt14["kit_log_artifact"],
            "interrupted_trace_tmp": {
                "path": str(ATTEMPT14_TRACE_TMP_PATH.relative_to(ROOT)),
                "bytes": ATTEMPT14_TRACE_TMP_BYTES,
                "sha256": None,
                "interpretation": "Ignored as incomplete temporary data; not hashed or consumed as scientific evidence.",
            },
            "canonical_process_receipt_present": False,
            "partial_outputs_consumed": False,
        },
        "renderer_single_gpu_contract": {
            "kit_args": SINGLE_GPU_KIT_ARGS,
            "renderer_multi_gpu_enabled": False,
            "renderer_multi_gpu_auto_enable": False,
            "renderer_multi_gpu_max_gpu_count": 1,
            "active_gpu_index": 4,
            "physics_cuda_device": 4,
            "tensor_device": "cuda:4",
            "cuda_visible_devices": "UNSET",
            "physical_gpu_lease": [4, 5, 6],
            "gpu7_compute_authorized": False,
        },
        "changed_files": _changed_files(),
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "Attempt14 exact invalidation evidence and R13 ancestry checks",
                "single-GPU Kit argv serialization check",
                "git diff --check",
            ],
            "runtime_not_run_reason": (
                "R13 authorizes Attempt15 preparation only; no Attempt15 preparation, IsaacSim, GPU, or "
                "pull-mechanism runtime was executed."
            ),
        },
        "acceptance": {
            "r12_parent_exact": True,
            "attempt14_receipt_exact": True,
            "attempt14_plan_stdout_kit_log_exact": True,
            "attempt14_resource_stop_exact": True,
            "attempt14_gpu7_unauthorized": True,
            "attempt14_probe_invalid": True,
            "attempt14_pull_verdict_not_assessed": True,
            "interrupted_trace_size_only": True,
            "single_gpu_kit_args_exact": True,
            "cuda4_device_preserved": True,
            "product_mechanics_unchanged": True,
            "thresholds_and_timeouts_unchanged": True,
            "attempt15_runner_exact_r13_binding": True,
            "attempt15_not_prepared_or_run": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim or GPU runtime PASS is asserted for R13.",
            "No Attempt15 preparation or runtime was executed.",
            "No pull-mechanism verdict is asserted because Attempt14 was invalidated by the resource stop.",
            "The interrupted temporary trace is size-only evidence and is not interpreted scientifically.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R13 pull-v0 repair receipt.")
    parser.add_argument("--output", type=Path, default=R13_RECEIPT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_r13_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
