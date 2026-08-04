#!/usr/bin/env python3
"""Build the bounded R16 contact-capacity receipt and its R16.4 PMON contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
LOG_ROOT = ROOT / "logs_eval" / "a2_piper_pull_v0" / "p1_push_anchor"

BASE_SHA = "4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
R15_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15_RECEIPT.json"
R15_RECEIPT_SHA256 = "3b850232429e4cdaee96281ad16ba2216f34df5baeb5262312f8bba831f841a0"
R16_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R16_RECEIPT.json"
R16_RECEIPT_SHA256 = "cf0d7107062bf8558adf4c64aaee03f91625950bdcaf2e1ee1d767883da1787e"

ATTEMPT18_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RECEIPT.json"
ATTEMPT18_RECEIPT_SHA256 = "329e86b831016ddab68b8a03ac91e65a97ed60700685f9e4b6700b08affb140a"
ATTEMPT18_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json"
ATTEMPT18_PLAN_SHA256 = "58c806cecfef15b876d21358f25742460669cd6e4c14e2c1d6c7ebd43678001f"
ATTEMPT18_PLAN_IDENTITY_SHA256 = "2c9f1efa53423f6abf0a12c41040cfc0c75ed1fb23ce07c05e8c470f093e6d72"
ATTEMPT18_PROCESS_PATH = LOG_ROOT / "attempt18/process_receipt.json"
ATTEMPT18_PROCESS_SHA256 = "641f99ba8ddda16f6114807b72ae9cc87234bae3dc8c0d7f9a6baf911562a94f"
ATTEMPT18_LOG_PATH = LOG_ROOT / "attempt18/stdout_stderr.log"
ATTEMPT18_LOG_SHA256 = "b49d6ed10e8c2665dd4c498692d011e00fb41c64fee72187b24f040679612cb1"
ATTEMPT18_INITIAL_LAUNCH_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_LAUNCH_OCCUPANCY.json"
ATTEMPT18_INITIAL_LAUNCH_SHA256 = "17f91b53a878c25677a96cd5f03a9c3329c5f32424faf6c4f56bab91f141c6ef"
ATTEMPT18_RETRY1_LAUNCH_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY.json"
ATTEMPT18_RETRY1_LAUNCH_SHA256 = "f2b93c71c02600c362a8e8e8eb9a3bcc52fe320f1681726ae933a8b415a0bcb1"
ATTEMPT18_STEADY_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT.json"
ATTEMPT18_STEADY_SHA256 = "a02d5a64683807dcdb1ce33b47f567ac9120a9640235806f7c1273ccaeaf614a"
ATTEMPT19_LAUNCH_OCCUPANCY_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_LAUNCH_OCCUPANCY.json"
ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_STEADY_STATE_FOOTPRINT.json"
R15E_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15E_RECEIPT.json"
R15F_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15F_RECEIPT.json"
R15E_RECEIPT_SHA256 = "bd384df10e61a0bacd79fdbe0bcdab9172f308ba71c3a6e1b5dac1c92b3e0360"
R15F_RECEIPT_SHA256 = "77fda56deb58e5720711fae654da05301cab306162a8fd6b436e23bac00299e3"
PRELAUNCH_INFRA_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PRELAUNCH_INFRA1_RECEIPT.json"
PRELAUNCH_INFRA_SHA256 = "932b6349a339892ea1590d427140820f66884ba357666f35a1bc76f89421e5cf"

ATTEMPT2_ANCHOR_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_RECEIPT.json"
ATTEMPT2_ANCHOR_RECEIPT_SHA256 = "0441648a81c28f180a6ec0a0ed4176b1f4b3f0fc0fd43dea12bc09712429ed63"
ATTEMPT2_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT2_PLAN.json"
ATTEMPT2_PLAN_SHA256 = "a0ad82cd7ce216d75a7ecae2b288d8c97f1dc75f592ef9ad2db4871ee8f43f7c"
ATTEMPT2_PROCESS_PATH = LOG_ROOT / "attempt2/process_receipt.json"
ATTEMPT2_PROCESS_SHA256 = "1bc49d13dc23826dd6fcf25827010f4bf131efbf24ea60c0edc578ab90072c68"
ATTEMPT2_SUMMARY_PATH = LOG_ROOT / "attempt2/eval/a2_hold_oracle_summary.json"
ATTEMPT2_SUMMARY_SHA256 = "edf5819a2189589b4aa5910026eaa40c90845d5afd1feba2aadadc376ea96bf7"
ATTEMPT2_METRICS_PATH = LOG_ROOT / "attempt2/eval/metrics_eval.json"
ATTEMPT2_METRICS_SHA256 = "552b2480360236dc1a4a13d8ac523cf27952951625d8c4353faf957a4d1c6764"

CONTACT_WARNING_SIGNATURE = (
    "Incomplete contact data is reported in GpuRigidContactView::getContactData "
    "because there are more contact data points than specified maxContactDataCount = 8."
)
CUDA_ASSERT_SIGNATURE = "CUDA error: device-side assert triggered"
FRICTION_FAILURE_SIGNATURE = "Exception: Failed to get friction data from backend"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Evidence artifact must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def _artifact(path: Path, expected_sha256: str | None = None) -> dict[str, str]:
    actual = _sha256(path)
    if expected_sha256 is not None and actual != expected_sha256:
        raise RuntimeError(f"{path} hash changed: expected={expected_sha256}, actual={actual}")
    label = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return {"path": label, "sha256": actual}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _validate_r15_parent() -> dict[str, str]:
    r15 = _read_json(R15_RECEIPT_PATH)
    _require(_sha256(R15_RECEIPT_PATH) == R15_RECEIPT_SHA256, "R15 receipt hash changed.")
    _require(r15.get("schema_version") == "pull_v0_repair_r15_receipt_v1", "R15 schema changed.")
    _require(r15.get("repair_revision") == "R15", "R15 revision changed.")
    _require(r15.get("status") == "APPROVED_FOR_ATTEMPT18_PREPARATION_ONLY", "R15 status changed.")
    _require(r15.get("runtime_validation") == "NOT_RUN", "R15 runtime state changed.")
    _require(r15.get("stale_candidate_id") == STALE_CANDIDATE_ID, "R15 stale candidate binding changed.")
    return _artifact(R15_RECEIPT_PATH, R15_RECEIPT_SHA256)


def _validate_attempt18_runtime() -> dict[str, Any]:
    receipt = _read_json(ATTEMPT18_RECEIPT_PATH)
    _require(_sha256(ATTEMPT18_RECEIPT_PATH) == ATTEMPT18_RECEIPT_SHA256, "Attempt18 canonical receipt hash changed.")
    _require(receipt.get("schema_version") == "pull_v0_p1_push_anchor_attempt_receipt_v18", "Attempt18 receipt schema changed.")
    _require(receipt.get("attempt") == 18, "Attempt18 receipt identity changed.")
    _require(receipt.get("status") == "PROBE_INVALID", "Attempt18 status is not PROBE_INVALID.")
    _require(receipt.get("probe_validity") == "PROBE_INVALID", "Attempt18 probe validity changed.")
    _require(receipt.get("runtime_validation") == "INVALIDATED_AFTER_FIRST_SIMULATION_STEP", "Attempt18 runtime boundary changed.")
    _require(receipt.get("scientific_verdict_consumed") is False, "Attempt18 scientific verdict was consumed.")
    _require(receipt.get("pull_mechanism_verdict") == "NOT_ASSESSED", "Attempt18 pull verdict changed.")
    for key, path, expected_sha256, revision in (
        ("repair_r15", R15_RECEIPT_PATH, R15_RECEIPT_SHA256, "R15"),
        ("repair_r15e", R15E_RECEIPT_PATH, R15E_RECEIPT_SHA256, "R15E"),
        ("repair_r15f", R15F_RECEIPT_PATH, R15F_RECEIPT_SHA256, "R15F"),
    ):
        ancestry = receipt.get(key)
        _require(isinstance(ancestry, Mapping), f"Attempt18 {key} ancestry is missing.")
        bound = ancestry.get("artifact")
        _require(isinstance(bound, Mapping), f"Attempt18 {key} artifact binding is missing.")
        expected_artifact = _artifact(path, expected_sha256)
        _require(dict(bound) == expected_artifact, f"Attempt18 {key} artifact binding changed.")
        _require(ancestry.get("revision") == revision, f"Attempt18 {key} revision changed.")
    prelaunch = receipt.get("prelaunch_infra")
    _require(isinstance(prelaunch, Mapping), "Attempt18 prelaunch ancestry is missing.")
    _require(
        dict(prelaunch.get("artifact")) == _artifact(PRELAUNCH_INFRA_PATH, PRELAUNCH_INFRA_SHA256),
        "Attempt18 prelaunch infrastructure binding changed.",
    )
    failure = receipt.get("runtime_failure")
    _require(isinstance(failure, Mapping), "Attempt18 runtime failure evidence is missing.")
    _require(failure.get("root_cause_code") == "CONTACT_SENSOR_CAPACITY_OVERFLOW", "Attempt18 root cause changed.")
    _require(failure.get("configured_max_contact_data_count_per_prim") == 8, "Attempt18 configured contact capacity changed.")
    _require(failure.get("required_anchor_only_detailed_contact_capacity") == 64, "Attempt19 contact capacity contract changed.")
    _require(failure.get("exact_signatures") == [CONTACT_WARNING_SIGNATURE, CUDA_ASSERT_SIGNATURE, FRICTION_FAILURE_SIGNATURE], "Attempt18 failure signatures changed.")
    _require(failure.get("first_simulation_step_boundary_crossed") is True and failure.get("scientific_attempt_started") is True, "Attempt18 first-step boundary evidence changed.")
    _require(failure.get("summary_present") is False and failure.get("metrics_present") is False, "Attempt18 summary/metrics absence changed.")
    termination = receipt.get("termination")
    _require(isinstance(termination, Mapping), "Attempt18 termination evidence is missing.")
    sigterm = termination.get("sigterm")
    _require(isinstance(sigterm, Mapping), "Attempt18 SIGTERM evidence is missing.")
    _require(sigterm.get("sent") is True and sigterm.get("timestamp_hkt") is None and sigterm.get("timestamp_status") == "NOT_RECORDED", "Attempt18 SIGTERM timestamp must remain unrecorded.")
    _require(termination.get("sigterm_timestamp_not_fabricated") is True, "Attempt18 SIGTERM timestamp fabrication guard changed.")
    _require(termination.get("sigkill", {}).get("timestamp_hkt") == "2026-08-04 20:14:10 HKT", "Attempt18 SIGKILL evidence changed.")
    _require(termination.get("runner_reaped_at_hkt") == "2026-08-04 20:14:13 HKT", "Attempt18 reap evidence changed.")
    artifacts = receipt.get("artifacts")
    _require(isinstance(artifacts, Mapping), "Attempt18 artifact map is missing.")
    expected = {
        "plan": (ATTEMPT18_PLAN_PATH, ATTEMPT18_PLAN_SHA256),
        "process_receipt": (ATTEMPT18_PROCESS_PATH, ATTEMPT18_PROCESS_SHA256),
        "log": (ATTEMPT18_LOG_PATH, ATTEMPT18_LOG_SHA256),
        "launch_occupancy": (ATTEMPT18_RETRY1_LAUNCH_PATH, ATTEMPT18_RETRY1_LAUNCH_SHA256),
        "steady_state_footprint": (ATTEMPT18_STEADY_PATH, ATTEMPT18_STEADY_SHA256),
    }
    validated_artifacts: dict[str, dict[str, str]] = {}
    for key, (path, expected_sha256) in expected.items():
        artifact = artifacts.get(key)
        _require(isinstance(artifact, Mapping), f"Attempt18 artifact {key} is missing.")
        validated = _artifact(path, expected_sha256)
        _require(dict(artifact) == validated, f"Attempt18 artifact {key} binding changed.")
        validated_artifacts[key] = validated
    initial_launch = artifacts.get("initial_launch_occupancy")
    _require(isinstance(initial_launch, Mapping), "Attempt18 initial launch occupancy is missing.")
    _require(
        dict(initial_launch) == _artifact(ATTEMPT18_INITIAL_LAUNCH_PATH, ATTEMPT18_INITIAL_LAUNCH_SHA256),
        "Attempt18 initial launch occupancy binding changed.",
    )
    _require(artifacts.get("summary") is None and artifacts.get("metrics") is None, "Attempt18 scientific artifacts were unexpectedly created.")
    return {"receipt": receipt, "artifacts": validated_artifacts}


def _validate_attempt2_no_gate() -> dict[str, Any]:
    anchor = _read_json(ATTEMPT2_ANCHOR_RECEIPT_PATH)
    _require(_sha256(ATTEMPT2_ANCHOR_RECEIPT_PATH) == ATTEMPT2_ANCHOR_RECEIPT_SHA256, "Attempt2 anchor receipt hash changed.")
    attempt2 = next((entry for entry in anchor.get("attempts", []) if isinstance(entry, Mapping) and entry.get("attempt") == 2), None)
    _require(isinstance(attempt2, Mapping), "Historical Attempt2 entry is missing.")
    _require(attempt2.get("result") == "NO_GATE", "Historical Attempt2 result changed.")
    finding = attempt2.get("finding")
    _require(isinstance(finding, Mapping), "Historical Attempt2 finding is missing.")
    _require(finding.get("completed_first_episodes") == 1 and finding.get("max_stage") == 0, "Historical Attempt2 stage evidence changed.")
    _require(finding.get("terminal_reason") == "stage_overtime" and finding.get("proof_samples") == 0, "Historical Attempt2 NO_GATE evidence changed.")
    plan = _read_json(ATTEMPT2_PLAN_PATH)
    summary = _read_json(ATTEMPT2_SUMMARY_PATH)
    metrics = _read_json(ATTEMPT2_METRICS_PATH)
    _require(plan.get("attempt") == 2, "Historical Attempt2 plan identity changed.")
    _require(summary.get("per_env_outcome") == ["NO_GATE"], "Historical Attempt2 summary outcome changed.")
    _require(summary.get("per_env_proof_samples") == [[]], "Historical Attempt2 proof samples changed.")
    _require(metrics.get("episode_max_stage_reached") == [0], "Historical Attempt2 max stage changed.")
    return {
        "anchor_receipt": _artifact(ATTEMPT2_ANCHOR_RECEIPT_PATH, ATTEMPT2_ANCHOR_RECEIPT_SHA256),
        "attempt2_plan": _artifact(ATTEMPT2_PLAN_PATH, ATTEMPT2_PLAN_SHA256),
        "attempt2_process_receipt": _artifact(ATTEMPT2_PROCESS_PATH, ATTEMPT2_PROCESS_SHA256),
        "attempt2_summary": _artifact(ATTEMPT2_SUMMARY_PATH, ATTEMPT2_SUMMARY_SHA256),
        "attempt2_metrics": _artifact(ATTEMPT2_METRICS_PATH, ATTEMPT2_METRICS_SHA256),
        "result": "NO_GATE",
        "proof_samples": 0,
        "max_stage": 0,
        "terminal_reason": "stage_overtime",
        "causal_answer": "Scripted acquisition depended on stage_buf == STAGE_GRASP while the first episode remained at stage0; the proof command never acquired or gated, so no pull-mechanism samples were obtained.",
        "original_finding": "transition inherited push/root-only semantics",
        "physical_plant_cause": "INCONCLUSIVE_NO_PROOF_SAMPLES",
    }


def build_r16_receipt() -> dict[str, Any]:
    r15_artifact = _validate_r15_parent()
    attempt18 = _validate_attempt18_runtime()
    historical_attempt2 = _validate_attempt2_no_gate()
    return {
        "schema_version": "pull_v0_repair_r16_receipt_v1",
        "generated_at_hkt": _hkt_now(),
        "repair_revision": "R16",
        "revision_detail": "R16.4",
        "status": "APPROVED_FOR_ATTEMPT19_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "scientific_verdict_consumed": False,
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": "ATTEMPT18_CONTACT_SENSOR_CAPACITY_OVERFLOW",
            "conclusion": "Attempt18 retry1 crossed the first simulation step with detailed contact telemetry enabled, but the shared max_contact_data_count_per_prim=8 buffer overflowed before summary/metrics finalization. The failure is a contact-buffer capacity defect, not a pull-mechanism verdict.",
            "source_signature": CONTACT_WARNING_SIGNATURE,
            "secondary_signatures": [CUDA_ASSERT_SIGNATURE, FRICTION_FAILURE_SIGNATURE],
            "physical_plant_cause": "INCONCLUSIVE_NO_PROOF_SAMPLES",
        },
        "parent_receipt": {
            "path": str(ATTEMPT18_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": ATTEMPT18_RECEIPT_SHA256,
            "repair_revision": "ATTEMPT18_RUNTIME",
        },
        "trigger": {
            "attempt": 18,
            "root_cause": "ATTEMPT18_CONTACT_SENSOR_CAPACITY_OVERFLOW",
            "attempt18_receipt": _artifact(ATTEMPT18_RECEIPT_PATH, ATTEMPT18_RECEIPT_SHA256),
            "runtime_artifacts": attempt18["artifacts"],
            "exact_failure_signatures": [CONTACT_WARNING_SIGNATURE, CUDA_ASSERT_SIGNATURE, FRICTION_FAILURE_SIGNATURE],
        },
        "scope": {
            "attempt18_parent_immutable": True,
            "attempt18_scientific_verdict_consumed": False,
            "attempt19_prepared": False,
            "attempt19_runtime_executed": False,
            "attempt19_artifacts_created": False,
            "fixture_changed": False,
            "thresholds_or_timeouts_changed": False,
            "p1_p2_gates_changed": False,
            "pull_verdict": "NOT_ASSESSED",
            "gpu_lease_changed": False,
            "shared_default_capacity_changed": False,
        },
        "source_repair": {
            "config_key": "a2_hold_diagnostic_max_contact_data_count_per_prim",
            "anchor_only_detailed_contact_capacity": 64,
            "shared_default_detailed_contact_capacity": 8,
            "num_envs": 1,
            "sensor_body": "door_handle",
            "sensor_body_collision_shape_count": 5,
            "filter_bodies": ["arm_body7", "arm_body8"],
            "filter_collision_shape_counts": {"arm_body7": 1, "arm_body8": 1},
            "observed_total_collision_shape_count": 7,
            "candidate_sensor_filter_shape_pair_count": 10,
            "track_pose": True,
            "track_contact_points": True,
            "track_friction_forces": True,
            "threshold_or_gate": False,
            "low_level_usd_api": False,
        },
        "r16_4_evidence_derivation": {
            "reason": (
                "The installed NVIDIA 580.173.02 driver reports inactive graphics PMON metrics as '-' and active "
                "Vulkan+compute contexts as C+G; R16.4 makes those states explicit and binds compute attribution "
                "to the PMON and compute-app sources together."
            ),
            "diff": [
                "Preserve PMON '-' SM/memory metrics as null with explicit NOT_REPORTED state/source; never rewrite them to zero.",
                "Accept PMON context types C, G, and C+G while rejecting unknown/partial rows and invalid FB memory or command fields.",
                "Require selected GPU2 compute attribution from PMON C/C+G plus positive FB and an exact GPU2 compute-app PID match; do not require instantaneous SM activity.",
                "Require every nonselected same-PID context to be inactive G, absent from compute-apps on that device, and within the 1024 MiB FB limit.",
                "Permit only explicitly recorded inactive G OTHER_TENANT contexts on authorized alternate GPU3; compute/C+G on GPU3 blocks.",
            ],
            "runtime_scope": "PREPARATION_ONLY",
            "runtime_validation": "NOT_RUN",
            "scientific_verdict_consumed": False,
            "installed_driver": "NVIDIA 580.173.02",
            "observed_rows": {
                "gpu3": {"pid": 2198197, "type": "G", "sm": "-", "mem": "-", "fb_mib": 4},
                "gpu4": {"pid": 2198197, "type": "C+G", "sm": 11, "mem": 5, "fb_mib": 5050},
            },
        },
        "attempt19_preparation_contract": {
            "attempt": 19,
            "detailed_contact_capacity": 64,
            "shared_default_detailed_contact_capacity": 8,
            "config_key": "a2_hold_diagnostic_max_contact_data_count_per_prim",
            "launch_occupancy_path": str(ATTEMPT19_LAUNCH_OCCUPANCY_PATH.relative_to(ROOT)),
            "steady_state_footprint_path": str(ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH.relative_to(ROOT)),
            "launch_occupancy_schema": "pull_v0_p1_attempt19_launch_occupancy_v1",
            "steady_state_footprint_schema": "pull_v0_p1_attempt19_steady_state_footprint_v1",
            "capture_tool": "scriptsFORhuman/pull_v0/capture_p1_anchor_gpu_evidence.py",
            "selected_compute_physical_device": 2,
            "authorized_compute_physical_devices": [2, 3],
            "unauthorized_compute_physical_devices": [0, 1, 4, 5, 6, 7],
            "first_simulation_step_boundary_required": True,
            "evidence_derivation_revision": "R16.4",
            "runtime_log_contract": {
                "ansi_stripping_required": True,
                "app_launcher_line": "[INFO][AppLauncher]: Using device: cuda:2",
                "environment_device_suffix": "Environment device    : cuda:2",
                "kit_vulkan_tables_after_app_launcher": "every complete table must contain known rows 0-7 with active physical devices exactly [2]",
                "first_simulation_step_boundary": "Starting evaluation with one episode per environment",
                "source_lines_and_tables_persisted": True,
                "validator_independent_derivation": True,
            },
            "pmon_contract": {
                "query": ["nvidia-smi", "pmon", "-i", "0,1,2,3,4,5,6,7", "-c", "1", "-s", "um"],
                "source": "nvidia-smi pmon -i 0,1,2,3,4,5,6,7 -c 1 -s um",
                "source_authoritative_for_attempt_pid": True,
                "required_fields": ["gpu", "pid", "type", "sm", "mem", "fb", "command"],
                "accepted_types": ["C", "G", "C+G"],
                "not_reported_metric_policy": "Preserve '-' as null with explicit NOT_REPORTED state; never coerce to numeric zero.",
                "compute_cross_source": "Selected GPU2 PID must appear in query-compute-apps on GPU2; nonselected same PID must be absent on that device.",
                "inactive_same_pid_context": {
                    "type": "G",
                    "sm_percent": "0 when reported; NOT_REPORTED otherwise",
                    "memory_percent": "0 when reported; NOT_REPORTED otherwise",
                    "fb_memory_mib_at_most": 1024,
                },
                "non_leased_other_pids": "OTHER_TENANT",
                "authorized_gpu3_alternate": "Only explicit inactive G OTHER_TENANT contexts absent from GPU3 compute-apps are allowed.",
                "device_total_utilization_is_not_attempt_attribution": True,
            },
            "process_identity_contract": {
                "runner_pid_required": True,
                "eval_pid_required_and_live_at_capture": True,
                "direct_child_or_verified_descendant": True,
                "module": "gr00t.rl.eval_agent_trl",
                "output_namespace": "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt19",
                "eval_output_dir": "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt19/eval",
                "closure_uses_static_identity_without_live_probe": True,
            },
            "lifecycle_contract": {
                "launch_capture_strictly_before_process_started_at": True,
                "steady_capture_within_process_started_finished_window": True,
                "finished_at_not_before_started_at": True,
            },
            "runtime_validation": "NOT_RUN",
            "scientific_verdict_consumed": False,
            "preparation_only": True,
        },
        "historical_attempt2_no_gate": historical_attempt2,
        "original_six_repair_policy": {
            "unchanged": True,
            "new_design": False,
            "p1_p2_changes": False,
            "note": "R16 records the historical NO_GATE causal answer separately and adds only the contact-buffer capacity repair; it does not replace the original six repair findings or introduce a new P1/P2 design."
        },
        "changed_files": {
            "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": {"hash_binding": "EXCLUDED_TO_AVOID_R16_RECEIPT_SHA_SELF_CYCLE"},
            "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": {"hash_binding": "EXCLUDED_TO_AVOID_R16_RECEIPT_SHA_SELF_CYCLE"},
            "scriptsFORhuman/pull_v0/build_pull_v0_repair_r16_receipt.py": {"hash_binding": "EXCLUDED_TO_AVOID_R16_RECEIPT_SHA_SELF_CYCLE"},
            "scriptsFORhuman/pull_v0/capture_p1_anchor_gpu_evidence.py": {"resource_evidence": "R16.4 installed-driver PMON states, cross-source PID attribution, GPU3 alternate tenant allowance, process identity, and lifecycle-bound Attempt19 capture"},
            "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml": {"contact_capacity": 64},
            "gr00t/rl/envs/door/door_open_a2_base.py": {"contact_sensor_helper": "existing high-level detail kwargs reused; source not changed by R16"},
        },
        "validation": {
            "static": "PASS",
            "runtime": "NOT_RUN",
            "runtime_not_run_reason": "R16 authorizes Attempt19 preparation only; no Attempt19 plan, output, IsaacSim, GPU, or scientific runtime was created or executed.",
        },
        "acceptance": {
            "attempt18_receipt_exact_and_probe_invalid": True,
            "attempt18_first_step_boundary_recorded": True,
            "attempt18_contact_capacity_overflow_recorded": True,
            "attempt18_scientific_verdict_consumed": False,
            "attempt18_pull_mechanism_not_assessed": True,
            "attempt2_no_gate_causal_answer_separate": True,
            "anchor_only_capacity_64": True,
            "shared_default_capacity_8": True,
            "detailed_contact_telemetry_preserved": True,
            "attempt19_preparation_only": True,
            "attempt19_resource_evidence_contract_bound": True,
            "attempt19_r16_4_log_evidence_derived": True,
            "attempt19_r16_4_pmon_context_evidence_required": True,
            "attempt19_r16_4_cross_source_pid_bound": True,
            "attempt19_r16_4_gpu3_alternate_inactive_tenant_bound": True,
            "attempt19_r16_4_process_identity_bound": True,
            "attempt19_r16_4_lifecycle_order_bound": True,
            "original_six_repair_policy_unchanged": True,
            "runtime_pass_asserted": False,
        },
        "evidence_summary": {
            "attempt18_process_returncode": -9,
            "attempt18_summary_present": False,
            "attempt18_metrics_present": False,
            "attempt18_sigterm_timestamp": None,
            "attempt18_sigterm_timestamp_status": "NOT_RECORDED",
            "attempt18_sigkill_timestamp": "2026-08-04 20:14:10 HKT",
            "attempt18_runner_reaped_at": "2026-08-04 20:14:13 HKT",
            "configured_capacity": 8,
            "required_capacity": 64,
            "historical_attempt2_result": "NO_GATE",
            "historical_attempt2_proof_samples": 0,
        },
        "unverified_claims": [
            "No Attempt19 runtime result or scientific verdict is asserted.",
            "R16.4 changes installed-driver PMON evidence derivation and closure binding only; no product mechanics, fixture, threshold, timeout, or P1/P2 gate is changed.",
            "The physical plant cause remains INCONCLUSIVE because Attempt2 never acquired or gated the proof and Attempt18 produced no summary/metrics samples.",
            "The exact SIGTERM send timestamp was not recorded; no timestamp is fabricated.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R16 contact-capacity receipt.")
    parser.add_argument("--validate-only", action="store_true", help="Validate immutable inputs without writing R16.")
    args = parser.parse_args()
    receipt = build_r16_receipt()
    if args.validate_only:
        print("Validated R16 inputs; no receipt written.")
        return 0
    if R16_RECEIPT_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite immutable receipt: {R16_RECEIPT_PATH}")
    R16_RECEIPT_PATH.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {R16_RECEIPT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
