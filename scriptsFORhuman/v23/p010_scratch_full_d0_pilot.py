"""Bounded P0.10 scratch/FULL/D0 pilot launcher and reducer.

The runner has four explicit modes:

``PLAN``
    Read the canonical R112 P0.9 receipt and print the exact P0.10 train and
    eval contracts.  No process or runtime output is created.
``RUN_TRAIN``
    Launch one foreground ``python -m gr00t.rl.train_agent_trl`` child on
    physical GPU0 (logical ``cuda:0``), then validate the step-500 checkpoint.
``REVALIDATE_TRAIN``
    Perform CPU-only validation of the preserved step-500 training evidence
    after a validator-only failure.  It never launches a training child.
``RUN_EVAL``
    Require the verified train record, launch one foreground module-eval child,
    and validate its canonical16 diagnostic artifacts.
``REDUCE``
    Re-open the train/eval records and raw eval files and adjudicate branch A.
    Birth-stage branch B is deliberately typed as unmeasured; no fallback or
    zero filling is performed.
``ADJUDICATE_TERMINAL``
    Read the immutable measurement receipt, preserved checkpoint, and
    canonical16 evidence on CPU and emit the terminal scratch-pilot
    adjudication.  It never launches a process or instruments branch B.

This is preparation evidence only.  It never admits D1, formal training,
release, or goal claims.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import subprocess
import sys
from collections import deque
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23Error, read_json, read_yaml, write_json
except ImportError:  # direct ``python scriptsFORhuman/v23/p010_scratch_full_d0_pilot.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23Error,
        read_json,
        read_yaml,
        write_json,
    )


TASK_ID = "v23-p010-checkpoint-revalidation-fix-r134"
REVISION = "R134"
ORIGINAL_TRAIN_TASK_ID = "v23-p010-runner-fix-r125"
ORIGINAL_TRAIN_REVISION = "R125"
ORIGINAL_TRAIN_FAILED_STATUS = "P0_10_D0_FULL_PILOT_TRAIN_FAILED"
KNOWN_R125_VALIDATOR_ERROR = (
    "checkpoint.optimizer_state_dict.param_groups[0].foreach contains an unsupported null"
)
TRAIN_REVALIDATION_RECORD_SCHEMA = "a2_piper_v23_p010_train_revalidation_record_v1"
PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
CONFIG_OVERRIDE = "wbmanip/base_v23_p09_d0_type_smoke"
CONFIG_PATH = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v23_p09_d0_type_smoke.yaml"

P09_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/p09_d0_type_smoke_receipt.json"
TRAIN_ROOT = (
    REPO_ROOT
    / "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v23/p010/r121/scratch_full_d0"
)
LAUNCHER_ROOT = (
    REPO_ROOT / "logs_rl/launchers/base_v23/r121_p010_scratch_full_d0_20260810"
)
EVAL_ROOT = (
    REPO_ROOT
    / "logs_eval/base_v23/p0/p010_scratch_full_d0_step500/canonical16"
)
CANONICAL_RECEIPT_PATH = (
    REPO_ROOT / "logs_eval/base_v23/p0/p010_scratch_full_d0_receipt.json"
)
TERMINAL_ADJUDICATION_RECEIPT_PATH = (
    REPO_ROOT
    / "logs_eval/base_v23/p0/p010_scratch_full_d0_terminal_adjudication.json"
)

TRAIN_RECORD_PATH = TRAIN_ROOT / "train_record.json"
TRAIN_REVALIDATION_RECORD_PATH = TRAIN_ROOT / "train_revalidation_record.json"
EVAL_RECORD_PATH = EVAL_ROOT / "eval_record.json"
CHECKPOINT_PATH = TRAIN_ROOT / "model_step_000500.pt"
EVAL_NAME = "p010_scratch_full_d0_step500_canonical16"

NUM_TRAIN_ENVS = 4096
NUM_TRAIN_BATCHES = 500
SAVE_FREQUENCY = 500
NUM_EVAL_ENVS = 16
SEED = 0
EFFORT_NM = 40.0
STAGED_RESET_RATIOS = [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
RP0_MASK_INDICES = [3, 4]
RP0_NEUTRAL_VALUE = 0.0
PHYSICAL_GPU = 0
LOGICAL_DEVICE = "cuda:0"
DOOR_REGIME = "D0"
POSTURE_MODE = "FULL"
CELL = "G3"
DIAGNOSTIC_REWARD_TERMS = ["a2_stage2_both_contact"]

TRAIN_RECORD_SCHEMA = "a2_piper_v23_p010_train_record_v1"
EVAL_RECORD_SCHEMA = "a2_piper_v23_p010_eval_record_v1"
RECEIPT_SCHEMA = "a2_piper_v23_p010_d0_full_pilot_receipt_v1"
PLAN_SCHEMA = "a2_piper_v23_p010_d0_full_pilot_plan_v1"
TERMINAL_ADJUDICATION_SCHEMA = "a2_piper_v23_p010_terminal_adjudication_receipt_v1"
TERMINAL_TASK_ID = "V23-P010-TERMINAL-RECEIPT-R149"
TERMINAL_REVISION = "R149-R1"
TERMINAL_STATUS = (
    "P0_10_SCRATCH_ADMISSION_NO_GO_BRANCH_A_FAILED_BRANCH_B_OBSERVABILITY_BLOCKED"
)
TERMINAL_SCIENTIFIC_OUTCOME = "P0_10_SCIENTIFIC_INCONCLUSIVE_BRANCH_B_UNMEASURED"
TERMINAL_MARKER = "V23_SCRATCH_CURRICULUM_INSUFFICIENT_PILOT"
STAGED_RESET_ENV_STATE_FIELDS = ("staged_reset_buf", "staged_reset_num_samples")
STAGED_RESET_ENV_STATE_SOURCE = "gr00t/rl/envs/base_task/staged_task_base.py"

LAUNCHER_PROCESS_RETRY_POLICY = "none"
LAUNCHER_PROCESS_RETRY_SCOPE = "launcher_and_child_process_only"

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CHECKPOINT_REQUIRED_KEYS = frozenset(
    {
        "policy_state_dict",
        "value_state_dict",
        "optimizer_state_dict",
        "lr_scheduler_state_dict",
        "state",
        "args",
        "env_state_dict",
    }
)
_CHECKPOINT_OPTIONAL_KEYS = frozenset({"homie_state_dict"})


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V23Error(f"{label} must be an object")
    return value


def _absolute_path(value: str | Path, *, label: str) -> Path:
    if not isinstance(value, (str, Path)):
        raise V23Error(f"{label} must be a path string")
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _require_exact(mapping: Mapping[str, Any], expected: Mapping[str, Any], *, label: str) -> None:
    mismatches = [
        f"{key}={mapping.get(key)!r} (expected {value!r})"
        for key, value in expected.items()
        if mapping.get(key) != value
    ]
    if mismatches:
        raise V23Error(f"{label} exact contract mismatch: " + "; ".join(mismatches))


def _nested(mapping: Mapping[str, Any], *keys: str, label: str) -> Any:
    current: Any = mapping
    for key in keys:
        current = _mapping(current, label=label).get(key)
        if current is None:
            raise V23Error(f"{label} is missing key {'.'.join(keys)}")
    return current


def validate_p09_admission() -> dict[str, Any]:
    """Read the canonical R112 receipt used as the sole P0.10 admission."""

    receipt = read_json(P09_RECEIPT_PATH)
    _require_exact(
        receipt,
        {
            "schema": "a2_piper_v23_p09_d0_four_type_receipt_v1",
            "status": "P0_9_D0_FOUR_TYPE_SMOKES_RUNTIME_VERIFIED",
            "p09_status": "COMPLETE",
            "p010_d0_full_pilot_admission": True,
            "d1_admission": False,
            "formal_admission": False,
            "release_receipt": False,
            "typed_exit_code": 0,
            "seed": SEED,
            "num_envs": 64,
            "num_processes": 1,
            "num_total_batches": 10,
            "save_frequency": 10,
        },
        label="R112 P0.9 receipt",
    )
    if receipt.get("passed_types") != [
        "WARM_FULL",
        "WARM_RP0",
        "SCRATCH_FULL",
        "SCRATCH_RP0",
    ]:
        raise V23Error("R112 P0.9 receipt does not list all four passed types in order")
    if receipt.get("failed_types") != [] or receipt.get("missing_types") != []:
        raise V23Error("R112 P0.9 receipt contains failed or missing types")
    return {
        "path": str(P09_RECEIPT_PATH.resolve()),
        "schema": receipt["schema"],
        "status": receipt["status"],
        "p09_status": receipt["p09_status"],
        "p010_d0_full_pilot_admission": receipt["p010_d0_full_pilot_admission"],
        "d1_admission": receipt["d1_admission"],
        "formal_admission": receipt["formal_admission"],
        "release_receipt": receipt["release_receipt"],
        "passed_types": list(receipt["passed_types"]),
    }


def _train_environment() -> dict[str, str]:
    return {
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES": str(PHYSICAL_GPU),
        "ACCELERATE_TORCH_DEVICE": LOGICAL_DEVICE,
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }


def _train_command() -> list[str]:
    train_root = TRAIN_ROOT.resolve()
    return [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.train_agent_trl",
        "+exp=wbmanip/door_open_a2_base_lstm",
        f"+ablation={CONFIG_OVERRIDE}",
        f"++experiment_dir={train_root}",
        f"++output_dir={train_root / 'output'}",
        "++project_name=a2_piper_full_stage_a2_base_smoke",
        "++experiment_name=p010_scratch_full_d0",
        "++v23_schema=a2_piper_base_v23_p010_d0_full_pilot_v1",
        "++v23_config_state=P0_10_D0_FULL_PILOT",
        f"++v23_cell={CELL}",
        f"++v23_seed={SEED}",
        "++v23_initialization=scratch",
        f"++v23_door_regime={DOOR_REGIME}",
        f"++v23_posture_mode={POSTURE_MODE}",
        "++v23_common_reward_state=P0_6_REWARD_REGISTRY_SELECTED",
        "++v23_training_enabled=true",
        "++v23_formal_launchable=false",
        "++v23_contract_only=false",
        "++checkpoint=null",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        f"++seed={SEED}",
        f"++num_envs={NUM_TRAIN_ENVS}",
        "++num_gpus=1",
        "++multi_gpu=false",
        "++headless=true",
        "++use_wandb=false",
        f"++algo.trl.num_total_batches={NUM_TRAIN_BATCHES}",
        "++algo.trl.report_to=none",
        f"++callbacks.model_save.save_frequency={SAVE_FREQUENCY}",
        "++algo.config.rp0_enabled=false",
        "++algo.config.rp0_mask_indices=[3,4]",
        f"++algo.config.rp0_neutral_value={RP0_NEUTRAL_VALUE}",
        "++env.config.a2_v23_rp0_enabled=false",
        "++env.config.a2_v23_rp0_mask_indices=[3,4]",
        f"++env.config.a2_v23_rp0_neutral_value={RP0_NEUTRAL_VALUE}",
        f"++env.config.a2_v23_effort_profile_nm={EFFORT_NM}",
        "++env.config.a2_v23_effort_profile_source=P0_2_MEASURED_FREEZE",
        "++env.config.a2_v23_formal_launch=false",
        "++env.config.a2_v23_stationary_rent_runtime_enabled=false",
        "++env.config.enable_staged_reset=true",
        "++env.config.staged_reset_ratios=[0.5,0.1,0.1,0.1,0.1,0.1]",
        "++algo.config.eval.eval_num_envs_episodes=false",
        "++algo.config.eval.a2_v23_p06_policy_only=false",
        "++algo.config.eval.a2_v23_p05_runtime_export=false",
        "++algo.config.eval.a2_v23_p08_state_bank_export=false",
        "++algo.config.eval.a2_v23_p0_runtime_export=false",
        "++algo.config.eval.a2_diagnostic_trace_enabled=false",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=false",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "++simulator.config.render_results=false",
        "++simulator.config.cameras.enable_cameras=false",
    ]


def _eval_environment() -> dict[str, str]:
    return _train_environment()


def _eval_command() -> list[str]:
    checkpoint = CHECKPOINT_PATH.resolve()
    eval_root = EVAL_ROOT.resolve()
    return [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        f"++num_envs={NUM_EVAL_ENVS}",
        f"++seed={SEED}",
        "++headless=true",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++algo.config.eval.num_eval_episodes={NUM_EVAL_ENVS}",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.eval.a2_diagnostic_reward_terms=[a2_stage2_both_contact]",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=false",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++env.config.enable_staged_reset=true",
        "++env.config.staged_reset_ratios=[0.5,0.1,0.1,0.1,0.1,0.1]",
        f"++eval_name={EVAL_NAME}",
        f"++eval_output_dir={eval_root}",
    ]


def _command_identity(command: Sequence[str], environment: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
        raise V23Error("command identity must be a sequence")
    command_list = list(command)
    if command_list[:3] not in (
        [str(PROJECT_PYTHON), "-m", "gr00t.rl.train_agent_trl"],
        [str(PROJECT_PYTHON), "-m", "gr00t.rl.eval_agent_trl"],
    ):
        raise V23Error("command must be a direct project-python module invocation")
    if any(token in {"setsid", "accelerate", "bash", "sh"} for token in command_list):
        raise V23Error("command contains a detached/wrapper launcher")
    expected_environment = dict(environment)
    if expected_environment != {
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES": "0",
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }:
        raise V23Error("command environment is not the physical-GPU0/logical-cuda0 contract")
    return {"argv": command_list, "shell": shlex.join(command_list), "environment": expected_environment}


def build_plan() -> dict[str, Any]:
    admission = validate_p09_admission()
    train_command = _train_command()
    eval_command = _eval_command()
    train_env = _train_environment()
    eval_env = _eval_environment()
    _command_identity(train_command, train_env)
    _command_identity(eval_command, eval_env)
    return {
        "schema": PLAN_SCHEMA,
        "status": "P0_10_D0_FULL_PILOT_PLAN_READY",
        "task_id": TASK_ID,
        "revision": REVISION,
        "admission": admission,
        "config_path": str(CONFIG_PATH),
        "config_override": CONFIG_OVERRIDE,
        "train": {
            "root": str(TRAIN_ROOT.resolve()),
            "launcher_root": str(LAUNCHER_ROOT.resolve()),
            "record_path": str(TRAIN_RECORD_PATH.resolve()),
            "revalidation_record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
            "revalidation_mode": "CPU_ONLY_NO_TRAIN_LAUNCH",
            "checkpoint_path": str(CHECKPOINT_PATH.resolve()),
            "checkpoint": None,
            "checkpoint_load_mode": "full",
            "auto_load_latest": False,
            "command": train_command,
            "command_shell": shlex.join(train_command),
            "environment": train_env,
        },
        "eval": {
            "root": str(EVAL_ROOT.resolve()),
            "launcher_root": str((LAUNCHER_ROOT / "eval").resolve()),
            "record_path": str(EVAL_RECORD_PATH.resolve()),
            "checkpoint_path": str(CHECKPOINT_PATH.resolve()),
            "checkpoint_load_mode": "full",
            "auto_load_latest": False,
            "command": eval_command,
            "command_shell": shlex.join(eval_command),
            "environment": eval_env,
            "required_artifacts": [
                "metrics_eval.json",
                "stage2_5_step_trace.json",
                "stage2_step_trace.json",
                "a2_v14_per_env_records.json",
                "a2_eval_diagnostic_metadata.json",
            ],
        },
        "revalidation": {
            "mode": "REVALIDATE_TRAIN",
            "record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
            "original_train_record_path": str(TRAIN_RECORD_PATH.resolve()),
            "original_failed_status": ORIGINAL_TRAIN_FAILED_STATUS,
            "known_validator_error": KNOWN_R125_VALIDATOR_ERROR,
            "requires_existing_train_root": True,
            "requires_existing_launcher_root": True,
            "launches_training": False,
            "writes_original_failure_record": False,
            "source_provenance": _source_provenance(),
        },
        "terminal_adjudication": {
            "mode": "ADJUDICATE_TERMINAL",
            "record_path": str(TERMINAL_ADJUDICATION_RECEIPT_PATH.resolve()),
            "measurement_receipt_path": str(CANONICAL_RECEIPT_PATH.resolve()),
            "checkpoint_path": str(CHECKPOINT_PATH.resolve()),
            "eval_root": str(EVAL_ROOT.resolve()),
            "cpu_only": True,
            "launches_training": False,
            "launches_evaluation": False,
            "branch_b_instrumentation": False,
            "required_staged_reset_env_state_fields": list(STAGED_RESET_ENV_STATE_FIELDS),
            "terminal_status": TERMINAL_STATUS,
        },
        "contract": {
            "physical_gpu": PHYSICAL_GPU,
            "logical_device": LOGICAL_DEVICE,
            "initialization": "scratch",
            "door_regime": DOOR_REGIME,
            "posture_mode": POSTURE_MODE,
            "cell": CELL,
            "rp0_enabled": False,
            "effort_profile_nm": EFFORT_NM,
            "common_reward_state": "P0_6_REWARD_REGISTRY_SELECTED",
            "staged_reset": True,
            "staged_reset_ratios": list(STAGED_RESET_RATIOS),
            "train_num_envs": NUM_TRAIN_ENVS,
            "train_num_total_batches": NUM_TRAIN_BATCHES,
            "save_frequency": SAVE_FREQUENCY,
            "eval_num_envs": NUM_EVAL_ENVS,
            "eval_first_episode_count": NUM_EVAL_ENVS,
            "diagnostics": True,
            "video": False,
            "render": False,
            "cameras": False,
            "wandb": False,
            "d1": False,
            "formal": False,
            "release": False,
        },
        "receipt_path": str(CANONICAL_RECEIPT_PATH.resolve()),
        "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
        "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        "common_reward": {
            "state": "P0_6_REWARD_REGISTRY_SELECTED",
            "effort_profile_nm": EFFORT_NM,
            "source": "resolved_config",
        },
        "execution_contract": "one_foreground_direct_module_child_per_run_mode",
        "revalidation_execution_contract": "cpu_only_read_existing_evidence_no_training_launch",
        "no_train_retry": True,
        "no_gpu_in_plan": True,
        "excluded_claims": [
            "NO_D1_TRAINING_OR_MIXTURE_CLAIM",
            "NO_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
            "NO_GOAL_OR_POLICY_QUALITY_CLAIM",
            "NO_BIRTH_STAGE_B_CLAIM",
        ],
    }


def _write_new_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise V23Error(f"refusing to overwrite existing launcher artifact: {path}")
    path.write_text(text, encoding="utf-8")


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_json(path, payload)


def _assert_fresh_root(path: Path, *, label: str) -> None:
    if path.exists():
        raise V23Error(f"{label} must be a fresh absent runtime root: {path}")


def _require_existing_root(path: Path, *, label: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise V23Error(f"{label} must be an existing canonical directory: {path}")


def _read_exact_child_returncode(path: Path) -> int:
    if path.is_symlink() or not path.is_file():
        raise V23Error(f"missing launcher child returncode evidence: {path}")
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise V23Error(f"launcher child returncode evidence cannot be read: {path}") from exc
    if value != "0\n":
        raise V23Error(f"launcher child returncode evidence is not exact rc0: {value!r}")
    return 0


def _load_original_failed_train_record(path: Path = TRAIN_RECORD_PATH) -> dict[str, Any]:
    path = path.resolve()
    if path != TRAIN_RECORD_PATH.resolve():
        raise V23Error("revalidation requires the canonical original train_record.json")
    record = read_json(path)
    _require_exact(
        record,
        {
            "schema": TRAIN_RECORD_SCHEMA,
            "status": ORIGINAL_TRAIN_FAILED_STATUS,
            "task_id": ORIGINAL_TRAIN_TASK_ID,
            "revision": ORIGINAL_TRAIN_REVISION,
            "physical_gpu": PHYSICAL_GPU,
            "logical_device": LOGICAL_DEVICE,
            "initialization": "scratch",
            "door_regime": DOOR_REGIME,
            "posture_mode": POSTURE_MODE,
            "cell": CELL,
            "seed": SEED,
            "num_envs": NUM_TRAIN_ENVS,
            "num_processes": 1,
            "num_total_batches": NUM_TRAIN_BATCHES,
            "save_frequency": SAVE_FREQUENCY,
            "checkpoint_load_mode": "full",
            "subprocess_returncode": 0,
            "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
            "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
            "d1_admission": False,
            "formal_admission": False,
            "release_receipt": False,
        },
        label="preserved R125 train failure record",
    )
    if record.get("error") != KNOWN_R125_VALIDATOR_ERROR:
        raise V23Error("preserved R125 train failure does not contain the known validator error")
    if record.get("run_root") != str(TRAIN_ROOT.resolve()):
        raise V23Error("preserved R125 train failure run root disagrees")
    if record.get("launcher_root") != str(LAUNCHER_ROOT.resolve()):
        raise V23Error("preserved R125 train failure launcher root disagrees")
    if record.get("record_path") != str(TRAIN_RECORD_PATH.resolve()):
        raise V23Error("preserved R125 train failure record path disagrees")
    if record.get("command") != _train_command() or record.get("command_shell") != shlex.join(_train_command()):
        raise V23Error("preserved R125 train failure command identity disagrees")
    if record.get("environment") != _train_environment():
        raise V23Error("preserved R125 train failure environment identity disagrees")
    if record.get("stdout_path") != str((LAUNCHER_ROOT / "stdout.log").resolve()):
        raise V23Error("preserved R125 train failure stdout path disagrees")
    return record


def _validate_device_stdout(stdout_path: Path, *, label: str) -> dict[str, Any]:
    try:
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise V23Error(f"{label} stdout cannot be read: {stdout_path}") from exc
    stdout = _ANSI_ESCAPE.sub("", stdout)
    app_devices = re.findall(r"Using device:\s*(cuda:\d+)", stdout)
    torch_indices = [int(value) for value in re.findall(r"CUDA device idx=(\d+)", stdout)]
    environment_devices = [
        f"cuda:{value}"
        for value in re.findall(r"Environment device\s*:\s*cuda:(\d+)", stdout)
    ]
    vulkan_rows: list[tuple[int, int]] = []
    for line in stdout.splitlines():
        match = re.search(r"^\s*\|\s*(\d+)\s*\|.*?\|\s*Yes:\s*(\d+)\s*\|", line)
        if match:
            row, active = match.groups()
            vulkan_rows.append((int(row), int(active)))
    if not app_devices or set(app_devices) != {LOGICAL_DEVICE}:
        raise V23Error(f"{label} AppLauncher device evidence disagrees: {app_devices!r}")
    if not torch_indices or set(torch_indices) != {PHYSICAL_GPU}:
        raise V23Error(f"{label} Torch CUDA index evidence disagrees: {torch_indices!r}")
    if not environment_devices or set(environment_devices) != {LOGICAL_DEVICE}:
        raise V23Error(f"{label} Isaac environment device evidence disagrees: {environment_devices!r}")
    if set(vulkan_rows) != {(PHYSICAL_GPU, 0)}:
        raise V23Error(f"{label} Kit Vulkan device evidence disagrees: {vulkan_rows!r}")
    return {
        "app_launcher_devices": list(app_devices),
        "torch_cuda_device_indices": torch_indices,
        "isaac_environment_devices": environment_devices,
        "kit_vulkan_device_rows": [row for row, _ in vulkan_rows],
        "kit_vulkan_active_groups": [active for _, active in vulkan_rows],
        "stdout_path": str(stdout_path.resolve()),
    }


def _finite_value(value: Any, *, label: str, allow_none: bool = True) -> None:
    """Reject non-finite checkpoint leaves without coercion or zero filling."""

    try:
        import torch
    except ImportError as exc:
        raise V23Error("checkpoint validation requires torch") from exc
    if value is None:
        if allow_none:
            return
        raise V23Error(f"{label} contains an unsupported null")
    if isinstance(value, torch.Tensor):
        if not bool(torch.isfinite(value).all().item()):
            raise V23Error(f"{label} contains a non-finite tensor")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _finite_value(child, label=f"{label}.{key}", allow_none=allow_none)
        return
    if isinstance(value, (list, tuple, deque)):
        for index, child in enumerate(value):
            _finite_value(child, label=f"{label}[{index}]", allow_none=allow_none)
        return
    if isinstance(value, bool) or isinstance(value, (str, bytes)):
        return
    if isinstance(value, (Integral, Real)) and not math.isfinite(float(value)):
        raise V23Error(f"{label} contains a non-finite number")
    if isinstance(value, (Integral, Real)):
        return
    raise V23Error(f"{label} contains unsupported value type {type(value).__name__}")


def _require_nonempty_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise V23Error(f"{label} must be a non-empty mapping for full restore")
    return value


def _validate_tensor_state_mapping(value: Any, *, label: str) -> None:
    mapping = _require_nonempty_mapping(value, label=label)
    for key, leaf in mapping.items():
        if not isinstance(key, str):
            raise V23Error(f"{label} state-dict key must be a string")
        try:
            import torch
        except ImportError as exc:
            raise V23Error("checkpoint validation requires torch") from exc
        if not isinstance(leaf, torch.Tensor):
            raise V23Error(f"{label}.{key} must be a tensor state-dict leaf")
        _finite_value(leaf, label=f"{label}.{key}", allow_none=False)


def _validate_env_leaf(value: Any, *, label: str) -> None:
    try:
        import torch
    except ImportError as exc:
        raise V23Error("checkpoint validation requires torch") from exc
    if isinstance(value, torch.Tensor):
        _finite_value(value, label=label, allow_none=False)
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _validate_env_leaf(child, label=f"{label}.{key}")
        return
    if isinstance(value, (list, tuple, deque)):
        for index, child in enumerate(value):
            _validate_env_leaf(child, label=f"{label}[{index}]")
        return
    if isinstance(value, bool) or not isinstance(value, (Integral, Real)):
        raise V23Error(f"{label} must be a finite tensor/numeric/container leaf")
    if not math.isfinite(float(value)):
        raise V23Error(f"{label} contains a non-finite number")


def _validate_env_state_mapping(value: Any, *, label: str) -> None:
    mapping = _require_nonempty_mapping(value, label=label)
    for key, leaf in mapping.items():
        if not isinstance(key, str):
            raise V23Error(f"{label} key must be a string")
        _validate_env_leaf(leaf, label=f"{label}.{key}")


def _validate_optimizer_scheduler_leaf(value: Any, *, label: str) -> None:
    try:
        import torch
    except ImportError as exc:
        raise V23Error("checkpoint validation requires torch") from exc
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, torch.Tensor):
        _finite_value(value, label=label, allow_none=False)
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _validate_optimizer_scheduler_leaf(child, label=f"{label}.{key}")
        return
    if isinstance(value, (list, tuple, deque)):
        for index, child in enumerate(value):
            _validate_optimizer_scheduler_leaf(child, label=f"{label}[{index}]")
        return
    if isinstance(value, (Integral, Real)):
        if not math.isfinite(float(value)):
            raise V23Error(f"{label} contains a non-finite number")
        return
    raise V23Error(f"{label} contains an unsupported optimizer/scheduler leaf type")


def _validate_optimizer_scheduler_mapping(value: Any, *, label: str) -> None:
    mapping = _require_nonempty_mapping(value, label=label)
    _validate_optimizer_scheduler_leaf(mapping, label=label)


def _validate_checkpoint(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.name != "model_step_000500.pt":
        raise V23Error(f"missing exact step-500 checkpoint: {path}")
    try:
        import torch

        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    except (OSError, RuntimeError, ValueError, EOFError) as exc:
        raise V23Error(f"step-500 checkpoint cannot be loaded: {path}") from exc
    if not isinstance(checkpoint, Mapping):
        raise V23Error("step-500 checkpoint must be a mapping")
    keys = set(checkpoint)
    missing = _CHECKPOINT_REQUIRED_KEYS - keys
    unsupported = keys - _CHECKPOINT_REQUIRED_KEYS - _CHECKPOINT_OPTIONAL_KEYS
    if missing or unsupported:
        raise V23Error(
            f"step-500 checkpoint schema mismatch: missing={sorted(missing)}, unsupported={sorted(unsupported)}"
        )
    _validate_tensor_state_mapping(
        checkpoint["policy_state_dict"], label="checkpoint.policy_state_dict"
    )
    _validate_tensor_state_mapping(
        checkpoint["value_state_dict"], label="checkpoint.value_state_dict"
    )
    _validate_optimizer_scheduler_mapping(
        checkpoint["optimizer_state_dict"], label="checkpoint.optimizer_state_dict"
    )
    _validate_optimizer_scheduler_mapping(
        checkpoint["lr_scheduler_state_dict"], label="checkpoint.lr_scheduler_state_dict"
    )
    _validate_env_state_mapping(checkpoint["env_state_dict"], label="checkpoint.env_state_dict")
    if checkpoint["state"] is None or not hasattr(checkpoint["state"], "__dict__"):
        raise V23Error("checkpoint.state must be a trainer state object for full restore")
    if "homie_state_dict" in checkpoint:
        _validate_tensor_state_mapping(
            checkpoint["homie_state_dict"], label="checkpoint.homie_state_dict"
        )
    state = checkpoint["state"]
    if not hasattr(state, "global_step"):
        raise V23Error("step-500 checkpoint state has no global_step")
    global_step = getattr(state, "global_step")
    if isinstance(global_step, bool) or not isinstance(global_step, Integral) or global_step != NUM_TRAIN_BATCHES:
        raise V23Error(f"step-500 checkpoint global_step disagrees: {global_step!r}")
    if type(checkpoint["args"]).__name__ != "PPOConfig":
        raise V23Error("step-500 checkpoint args must be the PPOConfig metadata object")
    if hasattr(state, "__dict__"):
        for field_name, field_value in vars(state).items():
            _finite_value(field_value, label=f"checkpoint.state.{field_name}")
    return {
        "path": str(path.resolve()),
        "file_name": path.name,
        "global_step": int(global_step),
        "finite": True,
        "schema_keys": sorted(keys),
        "state_type": type(state).__name__,
        "args_type": type(checkpoint["args"]).__name__,
    }


def _validate_saved_train_config(path: Path) -> dict[str, Any]:
    config = read_yaml(path)
    _require_exact(
        config,
        {
            "v23_schema": "a2_piper_base_v23_p010_d0_full_pilot_v1",
            "v23_config_state": "P0_10_D0_FULL_PILOT",
            "v23_cell": CELL,
            "v23_seed": SEED,
            "v23_initialization": "scratch",
            "v23_door_regime": DOOR_REGIME,
            "v23_posture_mode": POSTURE_MODE,
            "v23_common_reward_state": "P0_6_REWARD_REGISTRY_SELECTED",
            "v23_training_enabled": True,
            "v23_formal_launchable": False,
            "v23_contract_only": False,
            "checkpoint": None,
            "checkpoint_load_mode": "full",
            "auto_load_latest": False,
            "seed": SEED,
            "num_envs": NUM_TRAIN_ENVS,
            "num_gpus": 1,
            "multi_gpu": False,
            "headless": True,
            "use_wandb": False,
        },
        label="saved P0.10 training config",
    )
    if config.get("experiment_dir") != str(TRAIN_ROOT.resolve()):
        raise V23Error("saved training config experiment_dir disagrees with canonical train root")
    trl = _mapping(_nested(config, "algo", label="saved config"), label="algo").get("trl")
    _require_exact(_mapping(trl, label="algo.trl"), {"num_total_batches": NUM_TRAIN_BATCHES, "report_to": "none"}, label="saved algo.trl")
    model_save = _mapping(_nested(config, "callbacks", label="saved config"), label="callbacks").get("model_save")
    _require_exact(
        _mapping(model_save, label="callbacks.model_save"),
        {
            "_target_": "gr00t.rl.trl.callbacks.model_save_callback.ModelSaveCallback",
            "save_frequency": SAVE_FREQUENCY,
        },
        label="saved callbacks.model_save",
    )
    trainer = _mapping(config.get("trainer"), label="trainer")
    if trainer.get("_target_") != "gr00t.rl.trl.trainer.ppo_trainer_a2_base_api.TRLPPOTrainer":
        raise V23Error("saved training config is not using the canonical A2-base TRL trainer")
    algo = _mapping(_nested(config, "algo", label="saved config"), label="algo")
    algo_config = _mapping(algo.get("config"), label="algo.config")
    _require_exact(
        algo_config,
        {"rp0_enabled": False, "rp0_mask_indices": RP0_MASK_INDICES, "rp0_neutral_value": RP0_NEUTRAL_VALUE},
        label="saved algo.config RP0",
    )
    eval_config = _mapping(algo_config.get("eval"), label="algo.config.eval")
    for key in (
        "eval_num_envs_episodes",
        "a2_v23_p06_policy_only",
        "a2_v23_p05_runtime_export",
        "a2_v23_p08_state_bank_export",
        "a2_v23_p0_runtime_export",
        "a2_diagnostic_trace_enabled",
        "a2_eval_m41_strict_telemetry",
        "a2_eval_v20_strict_telemetry",
    ):
        if eval_config.get(key) is not False:
            raise V23Error(f"saved training config must keep algo.config.eval.{key}=false")
    env_config = _mapping(_nested(config, "env", label="saved config"), label="env").get("config")
    _require_exact(
        _mapping(env_config, label="env.config"),
        {
            "a2_v23_formal_launch": False,
            "a2_v23_stationary_rent_runtime_enabled": False,
            "a2_v23_effort_profile_nm": EFFORT_NM,
            "a2_v23_effort_profile_source": "P0_2_MEASURED_FREEZE",
            "a2_v23_rp0_enabled": False,
            "a2_v23_rp0_mask_indices": RP0_MASK_INDICES,
            "a2_v23_rp0_neutral_value": RP0_NEUTRAL_VALUE,
            "enable_staged_reset": True,
            "staged_reset_ratios": STAGED_RESET_RATIOS,
        },
        label="saved env.config",
    )
    simulator_config = _mapping(_nested(config, "simulator", label="saved config"), label="simulator").get("config")
    _require_exact(_mapping(simulator_config, label="simulator.config"), {"render_results": False}, label="saved simulator")
    cameras = _mapping(simulator_config.get("cameras"), label="simulator.config.cameras")
    if cameras.get("enable_cameras") is not False:
        raise V23Error("saved simulator cameras must be disabled")
    rewards = _mapping(config.get("rewards"), label="rewards")
    if rewards.get("reward_penalty_curriculum") is not False:
        raise V23Error("saved common reward curriculum selector must be false")
    reward_scales = _mapping(rewards.get("reward_scales"), label="rewards.reward_scales")
    for key, expected in {
        "penalty_a2_posture_command_l1": 0.0,
        "penalty_a2_v22_excess_posture": 0.0,
        "a2_v22_posture_feasibility": 0.0,
        "penalty_a2_v22_posture_saturation": 0.0,
        "a2_v22_clearance_success": 4.0,
        "a2_v22_controlled_fling": 2.0,
        "penalty_a2_v22_unsafe_release": -8.0,
    }.items():
        if reward_scales.get(key) != expected:
            raise V23Error(f"saved common reward scale {key} disagrees")
    return {
        "path": str(path.resolve()),
        "schema": config["v23_schema"],
        "config_state": config["v23_config_state"],
        "train_root": str(TRAIN_ROOT.resolve()),
        "num_envs": NUM_TRAIN_ENVS,
        "num_total_batches": NUM_TRAIN_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "effort_profile_nm": EFFORT_NM,
        "staged_reset_ratios": list(STAGED_RESET_RATIOS),
        "common_reward_state": "P0_6_REWARD_REGISTRY_SELECTED",
    }


def _validate_train_record(record_path: Path, *, require_artifacts: bool = True) -> dict[str, Any]:
    record = read_json(record_path)
    _require_exact(
        record,
        {
            "schema": TRAIN_RECORD_SCHEMA,
            "task_id": TASK_ID,
            "revision": REVISION,
            "status": "P0_10_D0_FULL_PILOT_TRAIN_RUNTIME_VERIFIED",
            "physical_gpu": PHYSICAL_GPU,
            "logical_device": LOGICAL_DEVICE,
            "initialization": "scratch",
            "door_regime": DOOR_REGIME,
            "posture_mode": POSTURE_MODE,
            "cell": CELL,
            "seed": SEED,
            "num_envs": NUM_TRAIN_ENVS,
            "num_processes": 1,
            "num_total_batches": NUM_TRAIN_BATCHES,
            "save_frequency": SAVE_FREQUENCY,
            "checkpoint_load_mode": "full",
            "subprocess_returncode": 0,
            "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
            "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        },
        label="P0.10 train record",
    )
    expected_root = str(TRAIN_ROOT.resolve())
    expected_launcher = str(LAUNCHER_ROOT.resolve())
    if record.get("run_root") != expected_root or record.get("launcher_root") != expected_launcher:
        raise V23Error("P0.10 train record roots disagree with canonical roots")
    expected_command = _train_command()
    expected_env = _train_environment()
    if record.get("command") != expected_command or record.get("command_shell") != shlex.join(expected_command):
        raise V23Error("P0.10 train record command identity disagrees")
    if record.get("environment") != expected_env:
        raise V23Error("P0.10 train record environment identity disagrees")
    if record.get("common_reward") != {
        "state": "P0_6_REWARD_REGISTRY_SELECTED",
        "effort_profile_nm": EFFORT_NM,
        "source": "resolved_config",
    }:
        raise V23Error("P0.10 train record common reward evidence is not exact")
    config_path = _absolute_path(record.get("resolved_config_path", ""), label="train resolved config")
    checkpoint_path = _absolute_path(record.get("terminal_checkpoint_path", ""), label="train checkpoint")
    if config_path != (TRAIN_ROOT / "config.yaml").resolve() or checkpoint_path != CHECKPOINT_PATH.resolve():
        raise V23Error("P0.10 train record artifact paths disagree")
    evidence = _mapping(record.get("evidence"), label="train evidence")
    if require_artifacts:
        config_facts = _validate_saved_train_config(config_path)
        checkpoint_facts = _validate_checkpoint(checkpoint_path)
        device_facts = _validate_device_stdout(
            _absolute_path(record.get("stdout_path", ""), label="train stdout"),
            label="training",
        )
    else:
        config_facts = dict(evidence.get("resolved_config", {}))
        checkpoint_facts = dict(evidence.get("checkpoint", {}))
        device_facts = dict(evidence.get("device", {}))
    if evidence.get("resolved_config") != config_facts or evidence.get("checkpoint") != checkpoint_facts or evidence.get("device") != device_facts:
        raise V23Error("P0.10 train record evidence does not match artifacts")
    if checkpoint_facts.get("global_step") != NUM_TRAIN_BATCHES or checkpoint_facts.get("finite") is not True:
        raise V23Error("P0.10 train record checkpoint evidence is not exact")
    return record


def _original_failure_summary(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_path": str(TRAIN_RECORD_PATH.resolve()),
        "status": record["status"],
        "task_id": record["task_id"],
        "revision": record["revision"],
        "error": record["error"],
        "subprocess_returncode": record["subprocess_returncode"],
    }


def _source_provenance() -> dict[str, str]:
    return {
        "wrapper_task_id": ORIGINAL_TRAIN_TASK_ID,
        "wrapper_revision": ORIGINAL_TRAIN_REVISION,
        "revalidation_task_id": TASK_ID,
        "revalidation_revision": REVISION,
    }


def _project_allowed_source_provenance(record: Mapping[str, Any]) -> dict[str, str]:
    """Project historical provenance onto the allowed task/revision identity."""

    source_provenance = _mapping(
        record.get("source_provenance"),
        label="P0.10 revalidation source provenance",
    )
    allowed_keys = (
        "wrapper_task_id",
        "wrapper_revision",
        "revalidation_task_id",
        "revalidation_revision",
    )
    projected: dict[str, str] = {}
    for key in allowed_keys:
        value = source_provenance.get(key)
        if not isinstance(value, str) or not value:
            raise V23Error(f"P0.10 revalidation source provenance {key} is missing or invalid")
        projected[key] = value
    return projected


def _validate_allowed_source_provenance(record: Mapping[str, Any]) -> dict[str, str]:
    projected = _project_allowed_source_provenance(record)
    if projected != _source_provenance():
        raise V23Error("P0.10 revalidation source provenance is not exact")
    return projected


def _validate_train_revalidation_record(
    record_path: Path = TRAIN_REVALIDATION_RECORD_PATH,
) -> dict[str, Any]:
    record_path = record_path.resolve()
    if record_path != TRAIN_REVALIDATION_RECORD_PATH.resolve():
        raise V23Error("P0.10 revalidation record must use the canonical path")
    record = read_json(record_path)
    _require_exact(
        record,
        {
            "schema": TRAIN_REVALIDATION_RECORD_SCHEMA,
            "status": "P0_10_D0_FULL_PILOT_TRAIN_REVALIDATION_VERIFIED",
            "task_id": TASK_ID,
            "revision": REVISION,
            "validation_mode": "CPU_ONLY_NO_TRAIN_LAUNCH",
            "physical_gpu": PHYSICAL_GPU,
            "logical_device": LOGICAL_DEVICE,
            "initialization": "scratch",
            "door_regime": DOOR_REGIME,
            "posture_mode": POSTURE_MODE,
            "cell": CELL,
            "seed": SEED,
            "num_envs": NUM_TRAIN_ENVS,
            "num_processes": 1,
            "num_total_batches": NUM_TRAIN_BATCHES,
            "save_frequency": SAVE_FREQUENCY,
            "checkpoint_load_mode": "full",
            "child_subprocess_returncode": 0,
            "subprocess_returncode": 0,
            "run_root": str(TRAIN_ROOT.resolve()),
            "launcher_root": str(LAUNCHER_ROOT.resolve()),
            "record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
            "original_train_record_path": str(TRAIN_RECORD_PATH.resolve()),
            "original_train_record_status": ORIGINAL_TRAIN_FAILED_STATUS,
            "original_train_record_task_id": ORIGINAL_TRAIN_TASK_ID,
            "original_train_record_revision": ORIGINAL_TRAIN_REVISION,
            "original_train_record_error": KNOWN_R125_VALIDATOR_ERROR,
            "wrapper_task_id": ORIGINAL_TRAIN_TASK_ID,
            "wrapper_revision": ORIGINAL_TRAIN_REVISION,
            "validator_revision": REVISION,
            "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
            "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
            "d1_admission": False,
            "formal_admission": False,
            "release_receipt": False,
        },
        label="P0.10 train revalidation record",
    )
    original = _load_original_failed_train_record()
    if record.get("original_failure") != _original_failure_summary(original):
        raise V23Error("P0.10 revalidation record does not preserve original failure provenance")
    _validate_allowed_source_provenance(record)
    expected_command = _train_command()
    if record.get("command") != expected_command or record.get("command_shell") != shlex.join(expected_command):
        raise V23Error("P0.10 revalidation command identity disagrees")
    if record.get("environment") != _train_environment():
        raise V23Error("P0.10 revalidation environment identity disagrees")
    if record.get("resolved_config_path") != str((TRAIN_ROOT / "config.yaml").resolve()):
        raise V23Error("P0.10 revalidation config path disagrees")
    if record.get("terminal_checkpoint_path") != str(CHECKPOINT_PATH.resolve()):
        raise V23Error("P0.10 revalidation checkpoint path disagrees")
    if record.get("stdout_path") != str((LAUNCHER_ROOT / "stdout.log").resolve()):
        raise V23Error("P0.10 revalidation stdout path disagrees")
    config_facts = _validate_saved_train_config(TRAIN_ROOT / "config.yaml")
    checkpoint_facts = _validate_checkpoint(CHECKPOINT_PATH)
    device_facts = _validate_device_stdout(LAUNCHER_ROOT / "stdout.log", label="training")
    expected_evidence = {
        "resolved_config": config_facts,
        "checkpoint": checkpoint_facts,
        "device": device_facts,
    }
    if record.get("evidence") != expected_evidence:
        raise V23Error("P0.10 revalidation evidence does not match preserved artifacts")
    if record.get("global_step") != NUM_TRAIN_BATCHES:
        raise V23Error("P0.10 revalidation global_step is not 500")
    return record


def _resolve_train_provenance(train_record_path: Path = TRAIN_RECORD_PATH) -> dict[str, Any]:
    primary_path = train_record_path.resolve()
    primary = read_json(primary_path)
    if primary.get("status") == ORIGINAL_TRAIN_FAILED_STATUS:
        original = _load_original_failed_train_record(primary_path)
        revalidation = _validate_train_revalidation_record()
        expected_primary = str(primary_path)
        if revalidation.get("original_train_record_path") != expected_primary:
            raise V23Error("revalidation record is not bound to the supplied failed train record")
        return {
            "train_record_path": expected_primary,
            "train_record_status": original["status"],
            "train_verified_record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
            "train_verified_status": revalidation["status"],
            "train_revalidation_record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
            "train_revalidation_status": revalidation["status"],
            "original_failure": _original_failure_summary(original),
        }
    verified = _validate_train_record(primary_path, require_artifacts=True)
    return {
        "train_record_path": str(primary_path),
        "train_record_status": verified["status"],
        "train_verified_record_path": str(primary_path),
        "train_verified_status": verified["status"],
        "train_revalidation_record_path": None,
        "train_revalidation_status": None,
        "original_failure": None,
    }


def _train_failure_record(paths: Mapping[str, Path], command: Sequence[str], environment: Mapping[str, str], returncode: int | None, error: str) -> dict[str, Any]:
    record = {
        "schema": TRAIN_RECORD_SCHEMA,
        "status": "P0_10_D0_FULL_PILOT_TRAIN_FAILED",
        "task_id": TASK_ID,
        "revision": REVISION,
        "physical_gpu": PHYSICAL_GPU,
        "logical_device": LOGICAL_DEVICE,
        "initialization": "scratch",
        "door_regime": DOOR_REGIME,
        "posture_mode": POSTURE_MODE,
        "cell": CELL,
        "seed": SEED,
        "num_envs": NUM_TRAIN_ENVS,
        "num_processes": 1,
        "num_total_batches": NUM_TRAIN_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "checkpoint_load_mode": "full",
        "run_root": str(paths["run_root"]),
        "launcher_root": str(paths["launcher_root"]),
        "record_path": str(paths["record"]),
        "stdout_path": str(paths["stdout"]),
        "command": list(command),
        "command_shell": shlex.join(command),
        "environment": dict(environment),
        "subprocess_returncode": returncode,
        "error": error,
        "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
        "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        "common_reward": {
            "state": "P0_6_REWARD_REGISTRY_SELECTED",
            "effort_profile_nm": EFFORT_NM,
            "source": "resolved_config",
        },
        "d1_admission": False,
        "formal_admission": False,
        "release_receipt": False,
    }
    _write_new_json(paths["record"], record)
    return record


def run_train(
    *,
    record_path: Path | None = None,
) -> tuple[dict[str, Any], int]:
    validate_p09_admission()
    run_root = TRAIN_ROOT.resolve()
    launcher = LAUNCHER_ROOT.resolve()
    record = (record_path or run_root / "train_record.json").resolve()
    if record.parent != run_root:
        raise V23Error("train record must live directly under the train root")
    _assert_fresh_root(run_root, label="train root")
    _assert_fresh_root(launcher, label="launcher root")
    run_root.mkdir(parents=True, exist_ok=True)
    launcher.mkdir(parents=True, exist_ok=True)
    paths = {
        "run_root": run_root,
        "launcher_root": launcher,
        "record": record,
        "command": launcher / "command.txt",
        "environment": launcher / "environment.json",
        "stdout": launcher / "stdout.log",
        "stderr": launcher / "stderr.log",
        "returncode": launcher / "returncode.txt",
        "resolved_config": run_root / "config.yaml",
        "checkpoint": run_root / "model_step_000500.pt",
    }
    command = _train_command()
    environment = _train_environment()
    _command_identity(command, environment)
    _write_new_text(paths["command"], shlex.join(command) + "\n")
    _write_new_json(paths["environment"], environment)
    child_env = dict(os.environ)
    child_env.update(environment)
    try:
        with paths["stdout"].open("x", encoding="utf-8") as stdout, paths["stderr"].open("x", encoding="utf-8") as stderr:
            completed = subprocess.run(command, cwd=REPO_ROOT, env=child_env, stdout=stdout, stderr=stderr, check=False)
        returncode: int | None = int(completed.returncode)
    except (OSError, subprocess.SubprocessError) as exc:
        _write_new_text(paths["returncode"], "LAUNCH_ERROR\n")
        return _train_failure_record(paths, command, environment, None, f"training subprocess launch failed: {exc}"), 2
    _write_new_text(paths["returncode"], f"{returncode}\n")
    if returncode != 0:
        return _train_failure_record(paths, command, environment, returncode, f"training subprocess returned nonzero code {returncode}"), 2
    try:
        config_facts = _validate_saved_train_config(paths["resolved_config"])
        checkpoint_facts = _validate_checkpoint(paths["checkpoint"])
        device_facts = _validate_device_stdout(paths["stdout"], label="training")
    except V23Error as exc:
        return _train_failure_record(paths, command, environment, returncode, str(exc)), 2
    evidence = {"resolved_config": config_facts, "checkpoint": checkpoint_facts, "device": device_facts}
    candidate = {
        "schema": TRAIN_RECORD_SCHEMA,
        "status": "P0_10_D0_FULL_PILOT_TRAIN_RUNTIME_VERIFIED",
        "task_id": TASK_ID,
        "revision": REVISION,
        "physical_gpu": PHYSICAL_GPU,
        "logical_device": LOGICAL_DEVICE,
        "initialization": "scratch",
        "door_regime": DOOR_REGIME,
        "posture_mode": POSTURE_MODE,
        "cell": CELL,
        "seed": SEED,
        "num_envs": NUM_TRAIN_ENVS,
        "num_processes": 1,
        "num_total_batches": NUM_TRAIN_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "checkpoint_load_mode": "full",
        "run_root": str(run_root),
        "launcher_root": str(launcher),
        "record_path": str(record),
        "resolved_config_path": str(paths["resolved_config"]),
        "terminal_checkpoint_path": str(paths["checkpoint"]),
        "stdout_path": str(paths["stdout"]),
        "command": command,
        "command_shell": shlex.join(command),
        "environment": environment,
        "subprocess_returncode": returncode,
        "global_step": NUM_TRAIN_BATCHES,
        "evidence": evidence,
        "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
        "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        "common_reward": {
            "state": "P0_6_REWARD_REGISTRY_SELECTED",
            "effort_profile_nm": EFFORT_NM,
            "source": "resolved_config",
        },
        "d1_admission": False,
        "formal_admission": False,
        "release_receipt": False,
    }
    try:
        _write_new_json(record, candidate)
    except V23Error as exc:
        return _train_failure_record(paths, command, environment, returncode, f"pre-write train PASS validation failed: {exc}"), 2
    return candidate, 0


def run_revalidate_train() -> tuple[dict[str, Any], int]:
    """Validate preserved P0.10 train evidence without launching a process."""

    _require_existing_root(TRAIN_ROOT, label="train root")
    _require_existing_root(LAUNCHER_ROOT, label="launcher root")
    if TRAIN_REVALIDATION_RECORD_PATH.exists():
        raise V23Error(
            f"refusing to overwrite existing train revalidation record: {TRAIN_REVALIDATION_RECORD_PATH}"
        )
    original = _load_original_failed_train_record()
    child_returncode = _read_exact_child_returncode(LAUNCHER_ROOT / "returncode.txt")
    config_facts = _validate_saved_train_config(TRAIN_ROOT / "config.yaml")
    checkpoint_facts = _validate_checkpoint(CHECKPOINT_PATH)
    device_facts = _validate_device_stdout(LAUNCHER_ROOT / "stdout.log", label="training")
    command = _train_command()
    environment = _train_environment()
    _command_identity(command, environment)
    candidate = {
        "schema": TRAIN_REVALIDATION_RECORD_SCHEMA,
        "status": "P0_10_D0_FULL_PILOT_TRAIN_REVALIDATION_VERIFIED",
        "task_id": TASK_ID,
        "revision": REVISION,
        "validation_mode": "CPU_ONLY_NO_TRAIN_LAUNCH",
        "physical_gpu": PHYSICAL_GPU,
        "logical_device": LOGICAL_DEVICE,
        "initialization": "scratch",
        "door_regime": DOOR_REGIME,
        "posture_mode": POSTURE_MODE,
        "cell": CELL,
        "seed": SEED,
        "num_envs": NUM_TRAIN_ENVS,
        "num_processes": 1,
        "num_total_batches": NUM_TRAIN_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "checkpoint_load_mode": "full",
        "run_root": str(TRAIN_ROOT.resolve()),
        "launcher_root": str(LAUNCHER_ROOT.resolve()),
        "record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
        "original_train_record_path": str(TRAIN_RECORD_PATH.resolve()),
        "original_train_record_status": original["status"],
        "original_train_record_task_id": original["task_id"],
        "original_train_record_revision": original["revision"],
        "original_train_record_error": original["error"],
        "original_failure": _original_failure_summary(original),
        "child_subprocess_returncode": child_returncode,
        "subprocess_returncode": child_returncode,
        "resolved_config_path": str((TRAIN_ROOT / "config.yaml").resolve()),
        "terminal_checkpoint_path": str(CHECKPOINT_PATH.resolve()),
        "stdout_path": str((LAUNCHER_ROOT / "stdout.log").resolve()),
        "command": command,
        "command_shell": shlex.join(command),
        "environment": environment,
        "global_step": NUM_TRAIN_BATCHES,
        "evidence": {
            "resolved_config": config_facts,
            "checkpoint": checkpoint_facts,
            "device": device_facts,
        },
        "source_provenance": _source_provenance(),
        "wrapper_task_id": ORIGINAL_TRAIN_TASK_ID,
        "wrapper_revision": ORIGINAL_TRAIN_REVISION,
        "validator_revision": REVISION,
        "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
        "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        "common_reward": {
            "state": "P0_6_REWARD_REGISTRY_SELECTED",
            "effort_profile_nm": EFFORT_NM,
            "source": "resolved_config",
        },
        "d1_admission": False,
        "formal_admission": False,
        "release_receipt": False,
    }
    _write_new_json(TRAIN_REVALIDATION_RECORD_PATH, candidate)
    return candidate, 0


def _required_eval_artifacts(eval_root: Path) -> dict[str, Path]:
    return {
        "metrics": eval_root / "metrics_eval.json",
        "trace": eval_root / "stage2_5_step_trace.json",
        "trace_alias": eval_root / "stage2_step_trace.json",
        "per_env": eval_root / "a2_v14_per_env_records.json",
        "metadata": eval_root / "a2_eval_diagnostic_metadata.json",
    }


def _validate_eval_artifacts(eval_root: Path) -> dict[str, Any]:
    artifacts = _required_eval_artifacts(eval_root)
    loaded: dict[str, Any] = {}
    for name, path in artifacts.items():
        if path.is_symlink() or not path.is_file():
            raise V23Error(f"missing required eval artifact {name}: {path}")
        try:
            loaded[name] = read_json(path) if name not in {"trace", "trace_alias", "per_env"} else json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise V23Error(f"eval artifact {name} is not valid JSON: {path}") from exc
        _validate_json_finite(loaded[name], label=f"eval.{name}")
    if not isinstance(loaded["metrics"], Mapping):
        raise V23Error("metrics_eval.json must be an object")
    if not isinstance(loaded["trace"], list) or not isinstance(loaded["trace_alias"], list):
        raise V23Error("stage2 trace artifacts must be arrays")
    if loaded["trace"] != loaded["trace_alias"]:
        raise V23Error("stage2_5_step_trace.json and stage2_step_trace.json disagree")
    if not isinstance(loaded["per_env"], list):
        raise V23Error("a2_v14_per_env_records.json must be an array")
    if not isinstance(loaded["metadata"], Mapping):
        raise V23Error("a2_eval_diagnostic_metadata.json must be an object")
    _require_exact(
        loaded["metadata"],
        {
            "diagnostic_trace_enabled": True,
            "reward_terms": DIAGNOSTIC_REWARD_TERMS,
            "forced_gripper_close_enabled": False,
            "m41_strict_telemetry": False,
            "v20_strict_telemetry": False,
        },
        label="P0.10 diagnostic metadata",
    )
    completed = loaded["metrics"].get("completed_episodes")
    if isinstance(completed, bool) or not isinstance(completed, Integral) or completed != NUM_EVAL_ENVS:
        raise V23Error(f"P0.10 eval completed_episodes must be {NUM_EVAL_ENVS}")
    if len(loaded["per_env"]) != NUM_EVAL_ENVS:
        raise V23Error("P0.10 eval per-env record count must be exactly 16")
    return {
        "eval_root": str(eval_root.resolve()),
        "artifacts": {name: str(path.resolve()) for name, path in artifacts.items()},
        "completed_episodes": int(completed),
        "trace_row_count": len(loaded["trace"]),
        "per_env_record_count": len(loaded["per_env"]),
        "diagnostic_metadata": dict(loaded["metadata"]),
    }


def _eval_failure_record(
    paths: Mapping[str, Path],
    command: Sequence[str],
    environment: Mapping[str, str],
    returncode: int | None,
    error: str,
    train_record_path: Path,
    train_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    record = {
        "schema": EVAL_RECORD_SCHEMA,
        "status": "P0_10_D0_FULL_PILOT_EVAL_FAILED",
        "task_id": TASK_ID,
        "revision": REVISION,
        "physical_gpu": PHYSICAL_GPU,
        "logical_device": LOGICAL_DEVICE,
        "checkpoint_step": NUM_TRAIN_BATCHES,
        "num_envs": NUM_EVAL_ENVS,
        "first_episode_count": NUM_EVAL_ENVS,
        "seed": SEED,
        "checkpoint_load_mode": "full",
        "train_record_path": str(train_record_path),
        "train_record_status": train_provenance["train_record_status"],
        "train_verified_record_path": train_provenance["train_verified_record_path"],
        "train_verified_status": train_provenance["train_verified_status"],
        "train_revalidation_record_path": train_provenance["train_revalidation_record_path"],
        "train_revalidation_status": train_provenance["train_revalidation_status"],
        "train_provenance": dict(train_provenance),
        "eval_root": str(paths["eval_root"]),
        "launcher_root": str(paths["launcher_root"]),
        "record_path": str(paths["record"]),
        "stdout_path": str(paths["stdout"]),
        "command": list(command),
        "command_shell": shlex.join(command),
        "environment": dict(environment),
        "subprocess_returncode": returncode,
        "error": error,
        "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
        "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        "d1_admission": False,
        "formal_admission": False,
        "release_receipt": False,
    }
    _write_new_json(paths["record"], record)
    return record


def run_eval(
    *,
    train_record_path: Path | None = None,
    record_path: Path | None = None,
) -> tuple[dict[str, Any], int]:
    train_record_target = (train_record_path or TRAIN_RECORD_PATH).resolve()
    train_provenance = _resolve_train_provenance(train_record_target)
    output_root = EVAL_ROOT.resolve()
    launcher = (LAUNCHER_ROOT / "eval").resolve()
    record = (record_path or output_root / "eval_record.json").resolve()
    if record.parent != output_root:
        raise V23Error("eval record must live directly under the eval root")
    _assert_fresh_root(output_root, label="eval root")
    _assert_fresh_root(launcher, label="eval launcher root")
    output_root.mkdir(parents=True, exist_ok=True)
    launcher.mkdir(parents=True, exist_ok=True)
    paths = {
        "eval_root": output_root,
        "launcher_root": launcher,
        "record": record,
        "command": launcher / "command.txt",
        "environment": launcher / "environment.json",
        "stdout": launcher / "stdout.log",
        "stderr": launcher / "stderr.log",
        "returncode": launcher / "returncode.txt",
    }
    command = _eval_command()
    environment = _eval_environment()
    _command_identity(command, environment)
    _write_new_text(paths["command"], shlex.join(command) + "\n")
    _write_new_json(paths["environment"], environment)
    child_env = dict(os.environ)
    child_env.update(environment)
    try:
        with paths["stdout"].open("x", encoding="utf-8") as stdout, paths["stderr"].open("x", encoding="utf-8") as stderr:
            completed = subprocess.run(command, cwd=REPO_ROOT, env=child_env, stdout=stdout, stderr=stderr, check=False)
        returncode: int | None = int(completed.returncode)
    except (OSError, subprocess.SubprocessError) as exc:
        _write_new_text(paths["returncode"], "LAUNCH_ERROR\n")
        return _eval_failure_record(paths, command, environment, None, f"eval subprocess launch failed: {exc}", train_record_target, train_provenance), 2
    _write_new_text(paths["returncode"], f"{returncode}\n")
    if returncode != 0:
        return _eval_failure_record(paths, command, environment, returncode, f"eval subprocess returned nonzero code {returncode}", train_record_target, train_provenance), 2
    try:
        eval_facts = _validate_eval_artifacts(output_root)
        device_facts = _validate_device_stdout(paths["stdout"], label="evaluation")
    except V23Error as exc:
        return _eval_failure_record(paths, command, environment, returncode, str(exc), train_record_target, train_provenance), 2
    eval_facts["device"] = device_facts
    candidate = {
        "schema": EVAL_RECORD_SCHEMA,
        "status": "P0_10_D0_FULL_PILOT_EVAL_RUNTIME_VERIFIED",
        "task_id": TASK_ID,
        "revision": REVISION,
        "physical_gpu": PHYSICAL_GPU,
        "logical_device": LOGICAL_DEVICE,
        "checkpoint_step": NUM_TRAIN_BATCHES,
        "checkpoint_path": str(CHECKPOINT_PATH.resolve()),
        "num_envs": NUM_EVAL_ENVS,
        "first_episode_count": NUM_EVAL_ENVS,
        "seed": SEED,
        "checkpoint_load_mode": "full",
        "diagnostic_trace_enabled": True,
        "video": False,
        "render": False,
        "cameras": False,
        "train_record_path": str(train_record_target),
        "train_record_status": train_provenance["train_record_status"],
        "train_verified_record_path": train_provenance["train_verified_record_path"],
        "train_verified_status": train_provenance["train_verified_status"],
        "train_revalidation_record_path": train_provenance["train_revalidation_record_path"],
        "train_revalidation_status": train_provenance["train_revalidation_status"],
        "train_provenance": train_provenance,
        "eval_root": str(output_root),
        "launcher_root": str(launcher),
        "record_path": str(record),
        "command": command,
        "command_shell": shlex.join(command),
        "environment": environment,
        "subprocess_returncode": returncode,
        "evidence": eval_facts,
        "stdout_path": str(paths["stdout"]),
        "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
        "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        "common_reward": {
            "state": "P0_6_REWARD_REGISTRY_SELECTED",
            "effort_profile_nm": EFFORT_NM,
            "source": "train_resolved_config",
        },
        "d1_admission": False,
        "formal_admission": False,
        "release_receipt": False,
    }
    _write_new_json(record, candidate)
    return candidate, 0


def _validate_json_finite(value: Any, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _validate_json_finite(child, label=f"{label}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_finite(child, label=f"{label}[{index}]")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise V23Error(f"{label} contains a non-finite number")


def _load_json_array(path: Path, *, label: str) -> list[Any]:
    if path.is_symlink() or not path.is_file():
        raise V23Error(f"{label} is not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V23Error(f"{label} is not valid JSON: {path}") from exc
    _validate_json_finite(value, label=label)
    if not isinstance(value, list):
        raise V23Error(f"{label} must be an array")
    return value


def _branch_a_reduce(eval_root: Path) -> dict[str, Any]:
    artifacts = _required_eval_artifacts(eval_root)
    metrics = read_json(artifacts["metrics"])
    _validate_json_finite(metrics, label="metrics_eval")
    trace = _load_json_array(artifacts["trace"], label="stage2_5_step_trace")
    alias = _load_json_array(artifacts["trace_alias"], label="stage2_step_trace")
    if trace != alias:
        raise V23Error("stage2 trace aliases disagree")
    per_env = _load_json_array(artifacts["per_env"], label="a2_v14_per_env_records")
    metadata = read_json(artifacts["metadata"])
    _validate_json_finite(metadata, label="a2_eval_diagnostic_metadata")
    _require_exact(
        metadata,
        {
            "diagnostic_trace_enabled": True,
            "reward_terms": DIAGNOSTIC_REWARD_TERMS,
            "forced_gripper_close_enabled": False,
            "m41_strict_telemetry": False,
            "v20_strict_telemetry": False,
        },
        label="P0.10 diagnostic metadata",
    )
    completed = metrics.get("completed_episodes")
    if isinstance(completed, bool) or not isinstance(completed, Integral):
        raise V23Error("metrics.completed_episodes must be an integer")
    max_stages = metrics.get("episode_max_stage_reached")
    if not isinstance(max_stages, list) or len(max_stages) != NUM_EVAL_ENVS:
        raise V23Error("metrics.episode_max_stage_reached must contain exactly 16 values")
    for stage in max_stages:
        if isinstance(stage, bool) or not isinstance(stage, Integral) or not 0 <= stage <= 5:
            raise V23Error("metrics.episode_max_stage_reached has an invalid type/value")
    goals = metrics.get("episode_goal_reached")
    if not isinstance(goals, list) or len(goals) != NUM_EVAL_ENVS or any(not isinstance(value, bool) for value in goals):
        raise V23Error("metrics.episode_goal_reached must contain exactly 16 bool values")
    diagnostics = metrics.get("episode_terminal_diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != NUM_EVAL_ENVS:
        raise V23Error("metrics.episode_terminal_diagnostics must contain exactly 16 rows")
    diagnostics_by_env: dict[int, Mapping[str, Any]] = {}
    for index, row in enumerate(diagnostics):
        item = _mapping(row, label=f"metrics.episode_terminal_diagnostics[{index}]")
        env_id = item.get("env_id")
        if (
            isinstance(env_id, bool)
            or not isinstance(env_id, Integral)
            or not 0 <= env_id < NUM_EVAL_ENVS
            or int(env_id) in diagnostics_by_env
        ):
            raise V23Error("metrics terminal diagnostics have missing/duplicate/invalid env identity")
        stage = item.get("stage_buf")
        if isinstance(stage, bool) or not isinstance(stage, Integral) or not 0 <= stage <= 5:
            raise V23Error("metrics terminal diagnostics stage_buf has invalid type/value")
        diagnostics_by_env[int(env_id)] = item
    if set(diagnostics_by_env) != set(range(NUM_EVAL_ENVS)):
        raise V23Error("metrics terminal diagnostics do not cover envs 0..15 exactly")
    if len(per_env) != NUM_EVAL_ENVS:
        raise V23Error("a2_v14_per_env_records must contain exactly 16 rows")
    per_env_by_env: dict[int, Mapping[str, Any]] = {}
    for index, row in enumerate(per_env):
        item = _mapping(row, label=f"a2_v14_per_env_records[{index}]")
        env_id = item.get("env_id")
        if (
            isinstance(env_id, bool)
            or not isinstance(env_id, Integral)
            or not 0 <= env_id < NUM_EVAL_ENVS
            or int(env_id) in per_env_by_env
        ):
            raise V23Error("a2_v14 per-env records have missing/duplicate/invalid env identity")
        max_stage = item.get("max_stage")
        if isinstance(max_stage, bool) or not isinstance(max_stage, Integral) or not 0 <= max_stage <= 5:
            raise V23Error("a2_v14 max_stage has invalid type/value")
        final_stage = item.get("final_stage")
        if isinstance(final_stage, bool) or not isinstance(final_stage, Integral) or not 0 <= final_stage <= 5:
            raise V23Error("a2_v14 final_stage has invalid type/value")
        per_env_by_env[int(env_id)] = item
    if set(per_env_by_env) != set(range(NUM_EVAL_ENVS)):
        raise V23Error("a2_v14 per-env records do not cover envs 0..15 exactly")
    if set(diagnostics_by_env) != set(per_env_by_env):
        raise V23Error("a2_v14 per-env and terminal diagnostic env identities disagree")
    max_stage_by_env = {
        env_id: int(item["max_stage"])
        for env_id, item in per_env_by_env.items()
    }
    if sorted(int(stage) for stage in max_stages) != sorted(max_stage_by_env.values()):
        raise V23Error("a2_v14 max_stage values disagree with metrics max-stage multiset")
    for env_id in range(NUM_EVAL_ENVS):
        diagnostic_stage = int(diagnostics_by_env[env_id]["stage_buf"])
        per_env_stage = int(per_env_by_env[env_id]["final_stage"])
        if per_env_stage != diagnostic_stage:
            raise V23Error("a2_v14 final_stage disagrees with the paired terminal diagnostic")
        if diagnostic_stage > max_stage_by_env[env_id]:
            raise V23Error("paired terminal diagnostic stage exceeds its env max stage")

    trace_ids: set[tuple[int, int]] = set()
    trace_env_ids: set[int] = set()
    stage2_trace_envs: set[int] = set()
    stable_envs: set[int] = set()
    for index, row in enumerate(trace):
        item = _mapping(row, label=f"stage2_step_trace[{index}]")
        env_id = item.get("env_id")
        step_index = item.get("step_index")
        episode_index = item.get("episode_index")
        first_active = item.get("first_episode_active")
        stage = item.get("stage_buf")
        hinge = item.get("door_hinge_joint_pos")
        if isinstance(env_id, bool) or not isinstance(env_id, Integral) or not 0 <= env_id < NUM_EVAL_ENVS:
            raise V23Error("trace env_id has invalid type/value")
        if int(env_id) not in max_stage_by_env:
            raise V23Error("trace env_id is absent from the paired per-env mapping")
        trace_env_ids.add(int(env_id))
        if isinstance(step_index, bool) or not isinstance(step_index, Integral) or step_index < 0:
            raise V23Error("trace step_index has invalid type/value")
        identity = (int(env_id), int(step_index))
        if identity in trace_ids:
            raise V23Error("trace contains duplicate env_id/step_index identity")
        trace_ids.add(identity)
        if isinstance(episode_index, bool) or not isinstance(episode_index, Integral) or episode_index != 0:
            raise V23Error("trace episode_index must be exactly zero")
        if first_active is not True:
            raise V23Error("trace first_episode_active must be true")
        if isinstance(stage, bool) or not isinstance(stage, Integral) or stage not in (2, 3, 4, 5):
            raise V23Error("trace stage_buf has invalid type/value")
        if isinstance(hinge, bool) or not isinstance(hinge, Real) or not math.isfinite(float(hinge)):
            raise V23Error("trace door_hinge_joint_pos must be finite")
        gate = item.get("a2_grasp_gate_mode")
        configured_k = item.get("a2_grasp_streak_control_steps")
        squeeze = item.get("a2_stage2_squeeze_streak")
        if not isinstance(gate, str) or not gate:
            raise V23Error("trace a2_grasp_gate_mode must be a string")
        if isinstance(configured_k, bool) or not isinstance(configured_k, Integral) or configured_k <= 0:
            raise V23Error("trace a2_grasp_streak_control_steps must be a positive integer")
        if isinstance(squeeze, bool) or not isinstance(squeeze, Integral) or squeeze < 0:
            raise V23Error("trace a2_stage2_squeeze_streak must be a non-negative integer")
        if int(stage) == 2:
            if int(env_id) not in {
                env for env, max_stage in max_stage_by_env.items() if max_stage >= 2
            }:
                raise V23Error("trace stage2 row belongs to an env whose max stage is below stage2")
            stage2_trace_envs.add(int(env_id))
            if gate == "control_streak" and int(configured_k) == 5 and int(squeeze) >= 5:
                stable_envs.add(int(env_id))
    stage2_count = sum(max_stage >= 2 for max_stage in max_stage_by_env.values())
    expected_stage2_envs = {
        env_id for env_id, max_stage in max_stage_by_env.items() if max_stage >= 2
    }
    if not expected_stage2_envs.issubset(stage2_trace_envs):
        raise V23Error("trace is missing stage2 rows for an episode whose max stage reached stage2")
    branch_a_pass = (
        completed == NUM_EVAL_ENVS
        and stage2_count >= 4
        and len(stable_envs) >= 1
    )
    return {
        "valid": True,
        "pass": branch_a_pass,
        "reason": None if branch_a_pass else (
            "completed_episodes_not_16"
            if completed != NUM_EVAL_ENVS
            else "branch_a_thresholds_not_met"
        ),
        "completed_episodes": int(completed),
        "max_stage_count": len(max_stages),
        "max_stage_by_env": {
            str(env_id): max_stage_by_env[env_id] for env_id in sorted(max_stage_by_env)
        },
        "stage2_count": stage2_count,
        "stable_grasp_env_ids": sorted(stable_envs),
        "stable_grasp_count": len(stable_envs),
        "trace_row_count": len(trace),
        "trace_env_ids": sorted(trace_env_ids),
        "stage2_trace_env_ids": sorted(stage2_trace_envs),
        "branch_a_rule": {
            "stage2_min_count": 4,
            "stable_grasp_min_count": 1,
            "gate_mode": "control_streak",
            "configured_k": 5,
            "squeeze_streak_min": 5,
        },
    }


def _validate_terminal_measurement_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly validate the immutable measurement receipt used by R149."""

    if not isinstance(receipt, Mapping):
        raise V23Error("terminal adjudication measurement receipt must be an object")
    expected_receipt_keys = {
        "branch_a",
        "branch_b",
        "d1_admission",
        "eval_record_path",
        "eval_root",
        "eval_status",
        "excluded_claims",
        "formal_admission",
        "launcher_process_retry_policy",
        "launcher_process_retry_scope",
        "release_receipt",
        "revision",
        "schema",
        "status",
        "task_id",
        "train_provenance",
        "train_record_path",
        "train_status",
        "typed_exit_code",
    }
    if set(receipt) != expected_receipt_keys:
        raise V23Error(
            "immutable measurement receipt schema mismatch: "
            f"keys={sorted(receipt)}"
        )
    _require_exact(
        receipt,
        {
            "schema": RECEIPT_SCHEMA,
            "status": "P0_10_BRANCH_A_FAILED_BRANCH_B_REQUIRED",
            "task_id": "v23-p010-checkpoint-revalidation-fix-r134",
            "revision": "R134",
            "train_record_path": str(TRAIN_RECORD_PATH.resolve()),
            "eval_record_path": str(EVAL_RECORD_PATH.resolve()),
            "eval_root": str(EVAL_ROOT.resolve()),
            "train_status": ORIGINAL_TRAIN_FAILED_STATUS,
            "eval_status": "P0_10_D0_FULL_PILOT_EVAL_RUNTIME_VERIFIED",
            "d1_admission": False,
            "formal_admission": False,
            "release_receipt": False,
            "typed_exit_code": 2,
            "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
            "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        },
        label="immutable P0.10 measurement receipt",
    )
    if receipt.get("excluded_claims") != [
        "NO_D1_TRAINING_OR_MIXTURE_CLAIM",
        "NO_FORMAL_ADMISSION",
        "NO_RELEASE_RECEIPT",
        "NO_GOAL_OR_POLICY_QUALITY_CLAIM",
    ]:
        raise V23Error("immutable measurement receipt excluded claims are not exact")
    for key in ("d1_admission", "formal_admission", "release_receipt"):
        if type(receipt.get(key)) is not bool:
            raise V23Error(f"immutable measurement receipt {key} must be a boolean")
    if type(receipt.get("typed_exit_code")) is not int:
        raise V23Error("immutable measurement receipt typed_exit_code must be an integer")

    branch_a = _mapping(receipt.get("branch_a"), label="measurement receipt branch_a")
    expected_branch_a_keys = {
        "branch_a_rule",
        "completed_episodes",
        "max_stage_by_env",
        "max_stage_count",
        "pass",
        "reason",
        "stable_grasp_count",
        "stable_grasp_env_ids",
        "stage2_count",
        "stage2_trace_env_ids",
        "trace_env_ids",
        "trace_row_count",
        "valid",
    }
    if set(branch_a) != expected_branch_a_keys:
        raise V23Error(
            "immutable measurement receipt branch_a schema mismatch: "
            f"keys={sorted(branch_a)}"
        )
    _require_exact(
        branch_a,
        {
            "valid": True,
            "pass": False,
            "completed_episodes": NUM_EVAL_ENVS,
            "max_stage_count": NUM_EVAL_ENVS,
            "stage2_count": 12,
            "stable_grasp_count": 0,
            "stable_grasp_env_ids": [],
            "reason": "branch_a_thresholds_not_met",
        },
        label="immutable measurement receipt branch_a",
    )
    for key in (
        "valid",
        "pass",
    ):
        if type(branch_a.get(key)) is not bool:
            raise V23Error(f"measurement receipt branch_a.{key} must be a boolean")
    for key in (
        "completed_episodes",
        "max_stage_count",
        "stage2_count",
        "stable_grasp_count",
        "trace_row_count",
    ):
        value = branch_a.get(key)
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise V23Error(f"measurement receipt branch_a.{key} must be an integer")
    max_stage_by_env = _mapping(
        branch_a.get("max_stage_by_env"),
        label="measurement receipt branch_a.max_stage_by_env",
    )
    if set(max_stage_by_env) != {str(index) for index in range(NUM_EVAL_ENVS)}:
        raise V23Error("measurement receipt branch_a.max_stage_by_env must cover envs 0..15")
    for env_id, stage in max_stage_by_env.items():
        if isinstance(stage, bool) or not isinstance(stage, Integral) or not 0 <= stage <= 5:
            raise V23Error(
                f"measurement receipt branch_a.max_stage_by_env[{env_id}] has an invalid stage"
            )
    for key in ("stable_grasp_env_ids", "stage2_trace_env_ids", "trace_env_ids"):
        values = branch_a.get(key)
        if not isinstance(values, list):
            raise V23Error(f"measurement receipt branch_a.{key} must be an array")
        if any(isinstance(value, bool) or not isinstance(value, Integral) for value in values):
            raise V23Error(f"measurement receipt branch_a.{key} contains an invalid env id")
    if branch_a["stage2_trace_env_ids"] != branch_a["trace_env_ids"]:
        raise V23Error("measurement receipt branch_a trace env identities disagree")
    if sorted(int(value) for value in branch_a["stage2_trace_env_ids"]) != sorted(
        int(env_id) for env_id, stage in max_stage_by_env.items() if int(stage) >= 2
    ):
        raise V23Error("measurement receipt branch_a stage2 env identities disagree with max stages")
    branch_a_rule = _mapping(
        branch_a.get("branch_a_rule"),
        label="measurement receipt branch_a.branch_a_rule",
    )
    _require_exact(
        branch_a_rule,
        {
            "stage2_min_count": 4,
            "stable_grasp_min_count": 1,
            "gate_mode": "control_streak",
            "configured_k": 5,
            "squeeze_streak_min": 5,
        },
        label="measurement receipt branch_a.rule",
    )

    branch_b = _mapping(receipt.get("branch_b"), label="measurement receipt branch_b")
    if set(branch_b) != {"measured", "reason", "status"}:
        raise V23Error(
            "immutable measurement receipt branch_b schema mismatch: "
            f"keys={sorted(branch_b)}"
        )
    _require_exact(
        branch_b,
        {
            "measured": False,
            "status": "UNMEASURED_REQUIRED_NEXT_STEP",
            "reason": "existing canonical16 evaluator does not export staged-reset birth-stage episodes",
        },
        label="immutable measurement receipt branch_b",
    )
    if type(branch_b.get("measured")) is not bool:
        raise V23Error("measurement receipt branch_b.measured must be a boolean")

    train_provenance = _mapping(
        receipt.get("train_provenance"),
        label="measurement receipt train_provenance",
    )
    if set(train_provenance) != {
        "original_failure",
        "train_record_path",
        "train_record_status",
        "train_revalidation_record_path",
        "train_revalidation_status",
        "train_verified_record_path",
        "train_verified_status",
    }:
        raise V23Error("measurement receipt train provenance schema is not exact")
    _require_exact(
        train_provenance,
        {
            "train_record_path": str(TRAIN_RECORD_PATH.resolve()),
            "train_record_status": ORIGINAL_TRAIN_FAILED_STATUS,
            "train_verified_record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
            "train_verified_status": "P0_10_D0_FULL_PILOT_TRAIN_REVALIDATION_VERIFIED",
            "train_revalidation_record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
            "train_revalidation_status": "P0_10_D0_FULL_PILOT_TRAIN_REVALIDATION_VERIFIED",
        },
        label="measurement receipt train provenance",
    )
    original_failure = _mapping(
        train_provenance.get("original_failure"),
        label="measurement receipt original_failure",
    )
    if set(original_failure) != {
        "error",
        "record_path",
        "revision",
        "status",
        "subprocess_returncode",
        "task_id",
    }:
        raise V23Error("measurement receipt original failure schema is not exact")
    _require_exact(
        original_failure,
        {
            "record_path": str(TRAIN_RECORD_PATH.resolve()),
            "status": ORIGINAL_TRAIN_FAILED_STATUS,
            "task_id": ORIGINAL_TRAIN_TASK_ID,
            "revision": ORIGINAL_TRAIN_REVISION,
            "error": KNOWN_R125_VALIDATOR_ERROR,
            "subprocess_returncode": 0,
        },
        label="measurement receipt original train failure",
    )
    return {
        "schema": receipt["schema"],
        "status": receipt["status"],
        "task_id": receipt.get("task_id"),
        "revision": receipt.get("revision"),
        "branch_a": dict(branch_a),
        "branch_b": dict(branch_b),
        "train_provenance": dict(train_provenance),
        "train_record_path": receipt["train_record_path"],
        "eval_record_path": receipt["eval_record_path"],
        "eval_root": receipt["eval_root"],
        "train_status": receipt["train_status"],
        "eval_status": receipt["eval_status"],
    }


def _validate_terminal_measurement_receipt(
    path: Path = CANONICAL_RECEIPT_PATH,
) -> dict[str, Any]:
    path = path.resolve()
    if path != CANONICAL_RECEIPT_PATH.resolve():
        raise V23Error("terminal adjudication requires the canonical immutable measurement receipt")
    return _validate_terminal_measurement_payload(read_json(path))


def _validate_terminal_observability_blocker(
    checkpoint_path: Path = CHECKPOINT_PATH,
    eval_root: Path = EVAL_ROOT,
) -> dict[str, Any]:
    """Prove the Branch-B observability blocker from exact preserved fields."""

    checkpoint_path = checkpoint_path.resolve()
    eval_root = eval_root.resolve()
    if checkpoint_path != CHECKPOINT_PATH.resolve() or eval_root != EVAL_ROOT.resolve():
        raise V23Error("terminal adjudication requires canonical checkpoint and eval roots")
    checkpoint_facts = _validate_checkpoint(checkpoint_path)
    try:
        import torch

        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except (OSError, RuntimeError, ValueError, EOFError) as exc:
        raise V23Error(f"terminal checkpoint cannot be loaded for env-state inspection: {checkpoint_path}") from exc
    if not isinstance(checkpoint, Mapping):
        raise V23Error("terminal checkpoint must be a mapping for env-state inspection")
    env_state = _mapping(checkpoint.get("env_state_dict"), label="terminal checkpoint.env_state_dict")
    present_fields = [field for field in STAGED_RESET_ENV_STATE_FIELDS if field in env_state]
    if present_fields:
        raise V23Error(
            "terminal checkpoint unexpectedly persists staged-reset fields: "
            f"{present_fields}"
        )
    missing_fields = list(STAGED_RESET_ENV_STATE_FIELDS)

    branch_a = _branch_a_reduce(eval_root)
    artifacts = _required_eval_artifacts(eval_root)
    metrics = read_json(artifacts["metrics"])
    max_stages = metrics.get("episode_max_stage_reached")
    if not isinstance(max_stages, list) or len(max_stages) != NUM_EVAL_ENVS:
        raise V23Error("terminal metrics episode_max_stage_reached must contain exactly 16 values")
    if any(isinstance(stage, bool) or not isinstance(stage, Integral) for stage in max_stages):
        raise V23Error("terminal metrics episode_max_stage_reached contains an invalid value")
    trace = _load_json_array(artifacts["trace"], label="terminal stage2_5_step_trace")
    trace_alias = _load_json_array(artifacts["trace_alias"], label="terminal stage2_step_trace")
    if trace != trace_alias:
        raise V23Error("terminal canonical16 trace aliases disagree")
    if not trace:
        raise V23Error("terminal canonical16 stage trace is empty")
    trace_stage_values: set[int] = set()
    trace_stage_ge_3_count = 0
    for index, row in enumerate(trace):
        item = _mapping(row, label=f"terminal stage trace[{index}]")
        stage = item.get("stage_buf")
        env_id = item.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, Integral) or not 0 <= env_id < NUM_EVAL_ENVS:
            raise V23Error("terminal stage trace env_id has an invalid value")
        if isinstance(stage, bool) or not isinstance(stage, Integral) or not 0 <= stage <= 5:
            raise V23Error("terminal stage trace stage_buf has an invalid value")
        trace_stage_values.add(int(stage))
        if int(stage) >= 3:
            trace_stage_ge_3_count += 1
    if trace_stage_values != {2}:
        raise V23Error(
            "terminal canonical16 stage trace must expose only stage 2 rows: "
            f"{sorted(trace_stage_values)}"
        )
    metrics_stage_ge_3_count = sum(int(stage) >= 3 for stage in max_stages)
    if metrics_stage_ge_3_count != 0:
        raise V23Error("terminal metrics expose a stage>=3 source")
    per_env = _load_json_array(artifacts["per_env"], label="terminal a2_v14_per_env_records")
    if len(per_env) != NUM_EVAL_ENVS:
        raise V23Error("terminal canonical16 per-env records must contain exactly 16 rows")
    per_env_max_stages: list[int] = []
    per_env_final_stages: list[int] = []
    for index, row in enumerate(per_env):
        item = _mapping(row, label=f"terminal per-env record[{index}]")
        for field_name, values in (
            ("max_stage", per_env_max_stages),
            ("final_stage", per_env_final_stages),
        ):
            stage = item.get(field_name)
            if isinstance(stage, bool) or not isinstance(stage, Integral) or not 0 <= stage <= 5:
                raise V23Error(f"terminal per-env {field_name} has an invalid value")
            values.append(int(stage))
    per_env_stage_ge_3_count = sum(stage >= 3 for stage in per_env_max_stages + per_env_final_stages)
    if per_env_stage_ge_3_count != 0:
        raise V23Error("terminal per-env records expose a stage>=3 source")
    if sorted(int(stage) for stage in max_stages) != sorted(per_env_max_stages):
        raise V23Error("terminal metrics and per-env max-stage values disagree")
    if branch_a["pass"] is not False:
        raise V23Error("terminal canonical16 branch_a unexpectedly passes")
    return {
        "status": "OBSERVABILITY_BLOCKED",
        "reason": (
            "checkpoint env_state_dict omits staged-reset snapshot bank/sample-count fields "
            "and canonical16 exports no stage>=3 birth-stage source"
        ),
        "checkpoint": checkpoint_facts,
        "checkpoint_env_state": {
            "key_count": len(env_state),
            "required_staged_reset_fields": list(STAGED_RESET_ENV_STATE_FIELDS),
            "present_staged_reset_fields": present_fields,
            "missing_staged_reset_fields": missing_fields,
            "source": STAGED_RESET_ENV_STATE_SOURCE,
        },
        "canonical16_stage_source": {
            "eval_root": str(eval_root),
            "trace_path": str(artifacts["trace"].resolve()),
            "trace_alias_path": str(artifacts["trace_alias"].resolve()),
            "trace_alias_equal": True,
            "trace_row_count": len(trace),
            "trace_stage_values": sorted(trace_stage_values),
            "trace_stage_ge_3_count": trace_stage_ge_3_count,
            "metrics_max_stage_values": [int(stage) for stage in max_stages],
            "metrics_stage_ge_3_count": metrics_stage_ge_3_count,
            "per_env_max_stage_values": sorted(per_env_max_stages),
            "per_env_final_stage_values": sorted(per_env_final_stages),
            "per_env_stage_ge_3_count": per_env_stage_ge_3_count,
            "stage_ge_3_source_count": 0,
        },
        "branch_a": branch_a,
    }


def _validate_eval_record(
    record_path: Path,
    *,
    expected_train_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = read_json(record_path)
    _require_exact(
        record,
        {
            "schema": EVAL_RECORD_SCHEMA,
            "task_id": TASK_ID,
            "revision": REVISION,
            "status": "P0_10_D0_FULL_PILOT_EVAL_RUNTIME_VERIFIED",
            "physical_gpu": PHYSICAL_GPU,
            "logical_device": LOGICAL_DEVICE,
            "checkpoint_step": NUM_TRAIN_BATCHES,
            "num_envs": NUM_EVAL_ENVS,
            "first_episode_count": NUM_EVAL_ENVS,
            "seed": SEED,
            "checkpoint_load_mode": "full",
            "diagnostic_trace_enabled": True,
            "video": False,
            "render": False,
            "cameras": False,
            "subprocess_returncode": 0,
            "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
            "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        },
        label="P0.10 eval record",
    )
    if record.get("eval_root") != str(EVAL_ROOT.resolve()) or record.get("checkpoint_path") != str(CHECKPOINT_PATH.resolve()):
        raise V23Error("P0.10 eval record canonical paths disagree")
    expected_command = _eval_command()
    if record.get("command") != expected_command or record.get("command_shell") != shlex.join(expected_command):
        raise V23Error("P0.10 eval record command identity disagrees")
    if record.get("environment") != _eval_environment():
        raise V23Error("P0.10 eval record environment identity disagrees")
    if record.get("common_reward") != {
        "state": "P0_6_REWARD_REGISTRY_SELECTED",
        "effort_profile_nm": EFFORT_NM,
        "source": "train_resolved_config",
    }:
        raise V23Error("P0.10 eval record common reward evidence is not exact")
    evidence = _mapping(record.get("evidence"), label="eval evidence")
    if evidence.get("eval_root") != str(EVAL_ROOT.resolve()) or evidence.get("completed_episodes") != NUM_EVAL_ENVS:
        raise V23Error("P0.10 eval record evidence identity disagrees")
    stdout_path = _absolute_path(record.get("stdout_path", ""), label="eval stdout")
    expected_stdout = (LAUNCHER_ROOT / "eval" / "stdout.log").resolve()
    if stdout_path != expected_stdout:
        raise V23Error("P0.10 eval record stdout path disagrees with canonical launcher root")
    device_facts = _validate_device_stdout(stdout_path, label="evaluation")
    if evidence.get("device") != device_facts:
        raise V23Error("P0.10 eval record device evidence does not match eval stdout")
    train_path = _absolute_path(record.get("train_record_path", ""), label="eval train record")
    train_provenance = expected_train_provenance or _resolve_train_provenance(train_path)
    if record.get("train_provenance") != train_provenance:
        raise V23Error("P0.10 eval record train provenance does not match its bound train records")
    for key in (
        "train_record_status",
        "train_verified_record_path",
        "train_verified_status",
        "train_revalidation_record_path",
        "train_revalidation_status",
    ):
        if record.get(key) != train_provenance[key]:
            raise V23Error(f"P0.10 eval record {key} does not match train provenance")
    return record


def _write_receipt(output: Path, payload: Mapping[str, Any]) -> None:
    _write_new_json(output, payload)


def reduce_p010(
    *,
    train_record_path: Path | None = None,
    eval_record_path: Path | None = None,
    output: Path = CANONICAL_RECEIPT_PATH,
) -> tuple[dict[str, Any], int]:
    train_path = (train_record_path or TRAIN_RECORD_PATH).resolve()
    eval_path = (eval_record_path or EVAL_RECORD_PATH).resolve()
    output = output.resolve()
    train_provenance: dict[str, Any] | None = None
    try:
        train_provenance = _resolve_train_provenance(train_path)
        train_record = read_json(train_path)
        eval_record = _validate_eval_record(
            eval_path,
            expected_train_provenance=train_provenance,
        )
        _validate_eval_artifacts(EVAL_ROOT)
        branch_a = _branch_a_reduce(EVAL_ROOT)
    except V23Error as exc:
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "status": "P0_10_INCONCLUSIVE",
            "task_id": TASK_ID,
            "revision": REVISION,
            "train_record_path": str(train_path),
            "eval_record_path": str(eval_path),
            "eval_root": str(EVAL_ROOT.resolve()),
            "train_provenance": train_provenance,
            "branch_a": {"valid": False, "pass": False, "error": str(exc)},
            "branch_b": {
                "status": "UNMEASURED",
                "required_next_step": "birth-stage B instrumentation is required if branch A is valid and fails",
            },
            "d1_admission": False,
            "formal_admission": False,
            "release_receipt": False,
            "typed_exit_code": 2,
            "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
            "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        }
        _write_receipt(output, receipt)
        return receipt, 2
    if branch_a["pass"]:
        status = "P0_10_D0_FULL_PILOT_GO"
        exit_code = 0
        branch_b = {"status": "NOT_REQUIRED", "measured": False}
    else:
        status = "P0_10_BRANCH_A_FAILED_BRANCH_B_REQUIRED"
        exit_code = 2
        branch_b = {
            "status": "UNMEASURED_REQUIRED_NEXT_STEP",
            "measured": False,
            "reason": "existing canonical16 evaluator does not export staged-reset birth-stage episodes",
        }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "task_id": TASK_ID,
        "revision": REVISION,
        "train_record_path": str(train_path),
        "eval_record_path": str(eval_path),
        "eval_root": str(EVAL_ROOT.resolve()),
        "train_provenance": train_provenance,
        "train_status": train_record.get("status"),
        "eval_status": eval_record.get("status"),
        "branch_a": branch_a,
        "branch_b": branch_b,
        "d1_admission": False,
        "formal_admission": False,
        "release_receipt": False,
        "typed_exit_code": exit_code,
        "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
        "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        "excluded_claims": [
            "NO_D1_TRAINING_OR_MIXTURE_CLAIM",
            "NO_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
            "NO_GOAL_OR_POLICY_QUALITY_CLAIM",
        ],
    }
    _write_receipt(output, receipt)
    return receipt, exit_code


def run_adjudicate_terminal() -> tuple[dict[str, Any], int]:
    """Emit the terminal CPU-only adjudication from preserved evidence."""

    if TERMINAL_ADJUDICATION_RECEIPT_PATH.exists():
        raise V23Error(
            "refusing to overwrite existing terminal adjudication receipt: "
            f"{TERMINAL_ADJUDICATION_RECEIPT_PATH}"
        )
    measurement = _validate_terminal_measurement_receipt()
    original_failure_record = _load_original_failed_train_record()
    revalidation_record = _validate_train_revalidation_record()
    expected_train_provenance = {
        "train_record_path": str(TRAIN_RECORD_PATH.resolve()),
        "train_record_status": original_failure_record["status"],
        "train_verified_record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
        "train_verified_status": revalidation_record["status"],
        "train_revalidation_record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
        "train_revalidation_status": revalidation_record["status"],
        "original_failure": _original_failure_summary(original_failure_record),
    }
    if measurement["train_provenance"] != expected_train_provenance:
        raise V23Error("immutable measurement receipt train provenance is not the preserved revalidation provenance")
    eval_record = _validate_eval_record(
        EVAL_RECORD_PATH,
        expected_train_provenance=expected_train_provenance,
    )
    blocker = _validate_terminal_observability_blocker()
    if blocker["branch_a"] != measurement["branch_a"]:
        raise V23Error(
            "immutable measurement receipt branch_a disagrees with canonical16 evidence"
        )

    receipt = {
        "schema": TERMINAL_ADJUDICATION_SCHEMA,
        "status": TERMINAL_STATUS,
        "task_id": TERMINAL_TASK_ID,
        "revision": TERMINAL_REVISION,
        "scratch_pilot_admission": False,
        "scientific_outcome": TERMINAL_SCIENTIFIC_OUTCOME,
        "branch_a_outcome": "MEASURED_VALID_FAILED",
        "branch_b_outcome": "UNMEASURED_OBSERVABILITY_BLOCKED",
        "branch_a": {
            "status": "MEASURED_VALID_FAILED",
            "measured": True,
            "valid": True,
            "pass": False,
            "measurement_receipt_path": str(CANONICAL_RECEIPT_PATH.resolve()),
            "measurement_receipt_status": measurement["status"],
            "observed": measurement["branch_a"],
        },
        "branch_b": {
            "status": "UNMEASURED_OBSERVABILITY_BLOCKED",
            "measured": False,
            "policy_outcome": "UNADJUDICATED",
            "original_status": measurement["branch_b"]["status"],
            "original_reason": measurement["branch_b"]["reason"],
            "required_next_step": measurement["branch_b"]["reason"],
            "observability_blocker": blocker,
        },
        "branch_b_policy_outcome": "UNADJUDICATED",
        "observability_blocker": blocker,
        "f1_triggered": True,
        "f1": {
            "triggered": True,
            "marker": TERMINAL_MARKER,
        },
        "marker": TERMINAL_MARKER,
        "original_measurement_receipt_path": str(CANONICAL_RECEIPT_PATH.resolve()),
        "original_measurement_receipt_status": measurement["status"],
        "measurement_receipt_path": str(CANONICAL_RECEIPT_PATH.resolve()),
        "measurement_receipt_status": measurement["status"],
        "original_measurement_receipt": {
            "path": str(CANONICAL_RECEIPT_PATH.resolve()),
            "status": measurement["status"],
            "task_id": measurement["task_id"],
            "revision": measurement["revision"],
        },
        "train_failure_record_path": str(TRAIN_RECORD_PATH.resolve()),
        "train_failure_record_status": original_failure_record["status"],
        "train_status": original_failure_record["status"],
        "train_failure": _original_failure_summary(original_failure_record),
        "train_revalidation_record_path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
        "train_revalidation_status": revalidation_record["status"],
        "runtime_eval_record_path": str(EVAL_RECORD_PATH.resolve()),
        "eval_record_path": str(EVAL_RECORD_PATH.resolve()),
        "eval_status": eval_record["status"],
        "eval_root": str(EVAL_ROOT.resolve()),
        "train_provenance": expected_train_provenance,
        "preserved_evidence": {
            "measurement_receipt": {
                "path": str(CANONICAL_RECEIPT_PATH.resolve()),
                "status": measurement["status"],
            },
            "train_failure": _original_failure_summary(original_failure_record),
            "train_revalidation": {
                "path": str(TRAIN_REVALIDATION_RECORD_PATH.resolve()),
                "status": revalidation_record["status"],
                "validation_mode": revalidation_record["validation_mode"],
                "global_step": revalidation_record["global_step"],
            },
            "runtime_eval": {
                "path": str(EVAL_RECORD_PATH.resolve()),
                "status": eval_record["status"],
                "eval_root": str(EVAL_ROOT.resolve()),
                "checkpoint_path": str(CHECKPOINT_PATH.resolve()),
            },
        },
        "d1_admission": False,
        "formal_admission": False,
        "release_receipt": False,
        "typed_exit_code": 2,
        "launcher_process_retry_policy": LAUNCHER_PROCESS_RETRY_POLICY,
        "launcher_process_retry_scope": LAUNCHER_PROCESS_RETRY_SCOPE,
        "excluded_claims": [
            "NO_D1_TRAINING_OR_MIXTURE_CLAIM",
            "NO_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
            "NO_GOAL_OR_POLICY_QUALITY_CLAIM",
            "NO_BRANCH_B_MEASUREMENT_CLAIM",
        ],
    }
    _write_receipt(TERMINAL_ADJUDICATION_RECEIPT_PATH, receipt)
    return receipt, 2


def _record_arg_path(raw: str, *, label: str) -> Path:
    return _absolute_path(raw, label=label)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=(
            "PLAN",
            "RUN_TRAIN",
            "REVALIDATE_TRAIN",
            "RUN_EVAL",
            "REDUCE",
            "ADJUDICATE_TERMINAL",
        ),
        required=True,
    )
    parser.add_argument("--train-record", type=Path, default=None)
    parser.add_argument("--eval-record", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.mode == "PLAN":
        if any(value is not None for value in (args.train_record, args.eval_record)):
            raise V23Error("PLAN does not accept runtime record overrides")
        payload = build_plan()
        if args.output is None:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        else:
            target = _absolute_path(args.output, label="PLAN output")
            _write_new_json(target, payload)
            print(json.dumps({"status": "WRITTEN", "path": str(target)}, indent=2))
        return 0

    if args.mode == "REVALIDATE_TRAIN":
        if any(value is not None for value in (args.train_record, args.eval_record, args.output)):
            raise V23Error("REVALIDATE_TRAIN uses canonical paths and accepts no overrides")
        record, exit_code = run_revalidate_train()
        print(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return exit_code

    if args.mode == "ADJUDICATE_TERMINAL":
        if any(value is not None for value in (args.train_record, args.eval_record, args.output)):
            raise V23Error("ADJUDICATE_TERMINAL uses canonical paths and accepts no overrides")
        receipt, exit_code = run_adjudicate_terminal()
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return exit_code

    if args.mode == "RUN_TRAIN":
        if args.eval_record is not None or args.output is not None:
            raise V23Error("RUN_TRAIN does not accept eval/output overrides")
        record, exit_code = run_train(
            record_path=None if args.train_record is None else _absolute_path(args.train_record, label="train record"),
        )
        print(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return exit_code

    if args.mode == "RUN_EVAL":
        if args.output is not None:
            raise V23Error("RUN_EVAL does not accept output overrides")
        record, exit_code = run_eval(
            train_record_path=None if args.train_record is None else _absolute_path(args.train_record, label="train record"),
            record_path=None if args.eval_record is None else _absolute_path(args.eval_record, label="eval record"),
        )
        print(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return exit_code

    receipt, exit_code = reduce_p010(
        train_record_path=None if args.train_record is None else _record_arg_path(str(args.train_record), label="train record"),
        eval_record_path=None if args.eval_record is None else _record_arg_path(str(args.eval_record), label="eval record"),
        output=CANONICAL_RECEIPT_PATH if args.output is None else _absolute_path(args.output, label="canonical receipt"),
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        print(f"V23 P0.10 SCRATCH FULL D0 PILOT FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
