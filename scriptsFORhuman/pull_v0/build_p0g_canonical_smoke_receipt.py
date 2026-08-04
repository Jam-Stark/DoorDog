#!/usr/bin/env python3
"""Build and validate the pull-v0 P0-G canonical smoke receipt."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import torch
import yaml


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
TRAIN_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P0G_CANONICAL_SMOKE_PLAN_R2.json"
RELOAD_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P0G_RELOAD_PLAN_R2.json"
OUTPUT_PATH = EVIDENCE_ROOT / "PULL_V0_P0G_CANONICAL_SMOKE.json"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v0_p0g/canonical_64x50"
TRAIN_RECEIPT_PATH = TRAIN_ROOT / "process_receipt.json"
CHECKPOINT_25 = TRAIN_ROOT / "model_step_000025.pt"
CHECKPOINT_50 = TRAIN_ROOT / "model_step_000050.pt"
TRAIN_CONFIG_PATH = TRAIN_ROOT / "config.yaml"
TRAIN_LOG_PATH = TRAIN_ROOT / ".hydra/train.log"
RELOAD_ROOT = ROOT / "logs_eval/a2_piper_pull_v0/p0g_checkpoint_reload"
RELOAD_RECEIPT_PATH = RELOAD_ROOT / "process_receipt.json"
RELOAD_METRICS_PATH = RELOAD_ROOT / "eval/metrics_eval.json"
RELOAD_LOG_PATH = RELOAD_ROOT / "hydra/eval.log"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_plan(path: Path) -> dict:
    plan = _load_json(path)
    declared_sha256 = plan.pop("plan_sha256")
    actual_sha256 = _canonical_sha256(plan)
    plan["plan_sha256"] = declared_sha256
    if declared_sha256 != actual_sha256:
        raise AssertionError(f"Invalid canonical plan digest: {path}")
    return plan


def _finite_tensor_tree(value: object, path: str, counts: dict[str, int]) -> None:
    if torch.is_tensor(value):
        counts["tensors"] += 1
        counts["elements"] += value.numel()
        if (value.is_floating_point() or value.is_complex()) and not torch.isfinite(value).all():
            raise AssertionError(f"Non-finite checkpoint tensor: {path}")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _finite_tensor_tree(child, f"{path}.{key}", counts)
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _finite_tensor_tree(child, f"{path}[{index}]", counts)
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise AssertionError(f"Non-finite checkpoint scalar: {path}")


def main() -> None:
    train_plan = _validate_plan(TRAIN_PLAN_PATH)
    reload_plan = _validate_plan(RELOAD_PLAN_PATH)
    train_receipt = _load_json(TRAIN_RECEIPT_PATH)
    reload_receipt = _load_json(RELOAD_RECEIPT_PATH)
    if train_plan["topology"] != {
        "num_envs": 64,
        "training_iterations": 50,
        "save_frequency": 25,
        "single_process": True,
    }:
        raise AssertionError("P0-G training plan is not the canonical 64x50 topology")
    if train_receipt["status"] != "PASS" or train_receipt["exit_code"] != 0:
        raise AssertionError("P0-G training process receipt did not pass")
    if train_receipt["plan_sha256"] != train_plan["plan_sha256"]:
        raise AssertionError("P0-G training receipt is not bound to the R2 plan")
    if train_receipt["physical_gpu"] != 4:
        raise AssertionError("P0-G training used an unallocated GPU")
    if _sha256(CHECKPOINT_50) != train_receipt["expected_output_sha256"]:
        raise AssertionError("P0-G step-50 checkpoint changed after process receipt")

    config = yaml.safe_load(TRAIN_CONFIG_PATH.read_text(encoding="utf-8"))
    exact_config = {
        "num_envs": config["num_envs"],
        "training_iterations": config["algo"]["trl"]["num_total_batches"],
        "save_frequency": config["callbacks"]["model_save"]["save_frequency"],
        "num_learning_epochs": config["algo"]["config"]["num_learning_epochs"],
        "num_mini_batches": config["algo"]["config"]["num_mini_batches"],
        "checkpoint_load_mode": config["checkpoint_load_mode"],
        "auto_load_latest": config["auto_load_latest"],
        "finger_effort_n": config["robot"]["dof_effort_limit_list"][-2:],
        "finger_stiffness": [
            config["robot"]["control"]["stiffness"]["arm_j7"],
            config["robot"]["control"]["stiffness"]["arm_j8"],
        ],
        "finger_damping": [
            config["robot"]["control"]["damping"]["arm_j7"],
            config["robot"]["control"]["damping"]["arm_j8"],
        ],
        "threshold_mode": config["env"]["config"]["a2_pull_threshold_mode"],
        "effort_provenance": config["env"]["config"]["a2_pull_effort_provenance"],
    }
    if exact_config != {
        "num_envs": 64,
        "training_iterations": 50,
        "save_frequency": 25,
        "num_learning_epochs": 5,
        "num_mini_batches": 4,
        "checkpoint_load_mode": "policy_only",
        "auto_load_latest": False,
        "finger_effort_n": [45.0, 45.0],
        "finger_stiffness": [1300.0, 1300.0],
        "finger_damping": [32.0, 32.0],
        "threshold_mode": "report_only",
        "effort_provenance": "ESTIMATE_ONLY",
    }:
        raise AssertionError(f"P0-G resolved config drifted: {exact_config}")

    checkpoint = torch.load(CHECKPOINT_50, map_location="cpu", weights_only=False)
    if set(checkpoint) != {
        "policy_state_dict",
        "value_state_dict",
        "optimizer_state_dict",
        "lr_scheduler_state_dict",
        "state",
        "args",
        "env_state_dict",
    }:
        raise AssertionError("P0-G checkpoint schema changed")
    counts = {"tensors": 0, "elements": 0}
    for key in ("policy_state_dict", "value_state_dict", "optimizer_state_dict"):
        _finite_tensor_tree(checkpoint[key], key, counts)
    trainer_state = checkpoint["state"]
    if trainer_state.global_step != 50 or trainer_state.max_steps != 50:
        raise AssertionError("P0-G checkpoint trainer state is not at exact step 50")

    train_log = TRAIN_LOG_PATH.read_text(encoding="utf-8")
    train_markers = (
        "CUDA device idx=4",
        "door metadata validated num_envs=64",
        "device=cuda:4",
        "a2_door_body_panel_contact_sensor force_matrix_w_shape=(64, 1, 13, 3)",
        "a2_door_arm_panel_contact_sensor force_matrix_w_shape=(64, 1, 10, 3)",
        "a2_pull_door_body_frame_contact_sensor force_matrix_w_shape=(64, 1, 13, 3)",
        "a2_pull_door_arm_frame_contact_sensor force_matrix_w_shape=(64, 1, 10, 3)",
    )
    missing_train_markers = [marker for marker in train_markers if marker not in train_log]
    if missing_train_markers:
        raise AssertionError(f"P0-G training log is missing markers: {missing_train_markers}")

    if reload_plan["parent_training_plan_sha256"] != train_plan["plan_sha256"]:
        raise AssertionError("P0-G reload plan does not bind the passing training plan")
    if reload_plan["checkpoint"]["sha256"] != _sha256(CHECKPOINT_50):
        raise AssertionError("P0-G reload plan checkpoint binding changed")
    if reload_receipt["status"] != "PASS" or reload_receipt["exit_code"] != 0:
        raise AssertionError("P0-G checkpoint reload process did not pass")
    if reload_receipt["plan_sha256"] != reload_plan["plan_sha256"]:
        raise AssertionError("P0-G reload receipt is not bound to its plan")
    if reload_receipt["physical_gpu"] != 4:
        raise AssertionError("P0-G reload used an unallocated GPU")
    metrics = _load_json(RELOAD_METRICS_PATH)
    if metrics["completed_episodes"] != 4:
        raise AssertionError("P0-G reload did not finish four first episodes")
    reload_log = RELOAD_LOG_PATH.read_text(encoding="utf-8")
    reload_markers = (
        "Loading training config file from",
        "CUDA device idx=4",
        "door metadata validated num_envs=4",
        "device=cuda:4",
        "a2_pull_door_body_frame_contact_sensor force_matrix_w_shape=(4, 1, 13, 3)",
        "a2_pull_door_arm_frame_contact_sensor force_matrix_w_shape=(4, 1, 10, 3)",
    )
    missing_reload_markers = [marker for marker in reload_markers if marker not in reload_log]
    if missing_reload_markers:
        raise AssertionError(f"P0-G reload log is missing markers: {missing_reload_markers}")

    receipt = {
        "schema_version": "pull_v0_p0g_canonical_smoke_v1",
        "generated_at_hkt": _hkt_now(),
        "status": "PASS",
        "threshold_mode": "report_only",
        "training": {
            "plan_path": _relative(TRAIN_PLAN_PATH),
            "plan_sha256": train_plan["plan_sha256"],
            "process_receipt_path": _relative(TRAIN_RECEIPT_PATH),
            "process_receipt_sha256": _sha256(TRAIN_RECEIPT_PATH),
            "resolved_config_path": _relative(TRAIN_CONFIG_PATH),
            "resolved_config_sha256": _sha256(TRAIN_CONFIG_PATH),
            "topology": exact_config,
            "natural_exit": "PASS",
            "runtime_device": "cuda:4",
        },
        "checkpoints": {
            "step_25": {
                "path": _relative(CHECKPOINT_25),
                "sha256": _sha256(CHECKPOINT_25),
                "size_bytes": CHECKPOINT_25.stat().st_size,
            },
            "step_50": {
                "path": _relative(CHECKPOINT_50),
                "sha256": _sha256(CHECKPOINT_50),
                "size_bytes": CHECKPOINT_50.stat().st_size,
                "trainer_global_step": trainer_state.global_step,
                "finite_policy_value_optimizer": "PASS",
                "finite_tensor_count": counts["tensors"],
                "finite_element_count": counts["elements"],
            },
        },
        "checkpoint_reload": {
            "plan_path": _relative(RELOAD_PLAN_PATH),
            "plan_sha256": reload_plan["plan_sha256"],
            "process_receipt_path": _relative(RELOAD_RECEIPT_PATH),
            "process_receipt_sha256": _sha256(RELOAD_RECEIPT_PATH),
            "metrics_path": _relative(RELOAD_METRICS_PATH),
            "metrics_sha256": _sha256(RELOAD_METRICS_PATH),
            "natural_exit": "PASS",
            "completed_first_episodes": 4,
            "runtime_device": "cuda:4",
            "performance_threshold": "N/A",
        },
        "attempt_history": [
            {
                "artifact": "logs_rl/a2_piper_full_stage_a2_pull/pull_v0_p0g/canonical_64x50_hydra_fail",
                "status": "FAIL_BEFORE_SIMULATION",
                "failure": "Hydra required +device for a key absent from the composed training config.",
                "bounded_repair": "Use +device=cuda:4 and freeze the R2 plan; training semantics are unchanged.",
            },
            {
                "artifact": "logs_eval/a2_piper_pull_v0/p0g_checkpoint_reload_one_env_fail",
                "status": "FAIL_BEFORE_CHECKPOINT_LOAD",
                "failure": "One eval environment could not be divided by the inherited four minibatches.",
                "bounded_repair": "Use four eval environments and four first episodes; retain num_mini_batches=4.",
            },
        ],
        "gpu_resource_evidence": {
            "authorized_physical_devices": [4, 5, 6],
            "compute_device_used": 4,
            "gpu5_used": False,
            "gpu6_used": False,
            "gpu7_compute_used": False,
            "isaacsim_adapter_note": "IsaacSim may enumerate system Vulkan adapters; training and reload logs identify CUDA device index 4 and environment/sensor tensors as cuda:4.",
        },
        "evidence_boundary": {
            "isaacsim_runtime": "PASS",
            "gradient_and_optimizer_finiteness": "PASS",
            "checkpoint_save": "PASS",
            "checkpoint_reload": "PASS",
            "pull_performance": "NOT_EVALUATED_NO_THRESHOLD",
            "p1_mechanism_landscape": "NOT_RUN",
            "p2_initialization_decision": "NOT_RUN",
        },
    }
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
