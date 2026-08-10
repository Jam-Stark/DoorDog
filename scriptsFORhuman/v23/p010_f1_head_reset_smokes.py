"""Plan, run, or reduce the bounded F1 warm-head-reset D0 smokes.

The runner has three explicit modes:

* ``PLAN`` prints two independent one-shot commands without launching them.
* ``RUN_TYPE`` launches exactly one assigned physical-GPU type.
* ``REDUCE`` validates exactly two step-10 type receipts and writes a typed F1
  smoke-complete receipt.

F1 is a minimal warm-policy head-reset pilot.  It does not mutate the
historical P0.9 runner or its evidence and never admits D1, formal, or release
work.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import subprocess
import sys
from collections import deque
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23Error, V23_WARM_START_PATH, read_json, write_json
except ImportError:  # direct ``python scriptsFORhuman/v23/p010_f1_head_reset_smokes.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23Error,
        V23_WARM_START_PATH,
        read_json,
        write_json,
    )


TASK_ID = "v23-p010-f1-head-reset-r177"
REVISION = "R177"
CONFIG_PATH = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v23_f1_d0_head_reset_smoke.yaml"
CONFIG_OVERRIDE = "wbmanip/base_v23_f1_d0_head_reset_smoke"
EXPERIMENT_CONFIG_OVERRIDE = "wbmanip/door_open_a2_base_lstm"
PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")

CANONICAL_TRAINING_ROOT = (
    REPO_ROOT / "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v23/f1/r177"
)
CANONICAL_LAUNCHER_ROOT = (
    REPO_ROOT / "logs_rl/launchers/base_v23/r177_p010_f1_d0_head_reset_smokes_20260810"
)
CANONICAL_AGGREGATE_PATH = (
    REPO_ROOT / "logs_eval/base_v23/p0/p010_f1_head_reset_d0_type_smoke_receipt.json"
)

TYPE_RECORD_SCHEMA = "a2_piper_v23_f1_head_reset_d0_type_record_v1"
AGGREGATE_SCHEMA = "a2_piper_v23_f1_head_reset_d0_receipt_v1"
TYPE_PASS_STATUS = "P0_10_F1_D0_TYPE_SMOKE_RUNTIME_VERIFIED"
TYPE_FAIL_STATUS = "P0_10_F1_D0_TYPE_SMOKE_FAILED"
PASS_STATUS = "P0_10_F1_D0_HEAD_RESET_TWO_TYPE_SMOKES_RUNTIME_VERIFIED"
INCOMPLETE_STATUS = "P0_10_F1_D0_HEAD_RESET_TWO_TYPE_SMOKES_INCOMPLETE"
F1_MARKER = "V23_SCRATCH_CURRICULUM_INSUFFICIENT_PILOT"
RP0_INDICES = [3, 4]
RP0_NEUTRAL = 0.0
EFFORT_NM = 40.0
NUM_ENVS = 64
NUM_BATCHES = 10
SAVE_FREQUENCY = 10
SEED = 0
TYPE_IDS = ("HR_FULL_D0", "HR_RP0_D0")

CHECKPOINT_REQUIRED_KEYS = frozenset(
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
CHECKPOINT_OPTIONAL_KEYS = frozenset({"homie_state_dict"})
TRAINER_STATE_FIELDS = (
    "epoch",
    "global_step",
    "max_steps",
    "logging_steps",
    "eval_steps",
    "save_steps",
    "train_batch_size",
    "num_train_epochs",
    "num_input_tokens_seen",
    "total_flos",
    "best_metric",
    "best_global_step",
    "best_model_checkpoint",
    "is_local_process_zero",
    "is_world_process_zero",
    "is_hyper_param_search",
    "trial_name",
    "trial_params",
    "stateful_callbacks",
    "episode",
    "rewbuffer",
    "lenbuffer",
    "cur_reward_sum",
    "cur_episode_length",
    "tot_timesteps",
    "tot_time",
    "eval_step",
    "eval_render_step",
)

TYPE_MATRIX: dict[str, dict[str, Any]] = {
    "HR_FULL_D0": {
        "cell": "G3",
        "gpu": 0,
        "initialization": "warm_head_reset",
        "posture_mode": "FULL",
        "checkpoint": V23_WARM_START_PATH,
        "checkpoint_load_mode": "policy_only",
        "rp0_enabled": False,
    },
    "HR_RP0_D0": {
        "cell": "G4",
        "gpu": 1,
        "initialization": "warm_head_reset",
        "posture_mode": "RP0",
        "checkpoint": V23_WARM_START_PATH,
        "checkpoint_load_mode": "policy_only",
        "rp0_enabled": True,
    },
}


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V23Error(f"{label} must be an object")
    return value


def _type_id(raw: str) -> str:
    value = raw.upper()
    if value not in TYPE_MATRIX:
        raise V23Error(f"type must be one of {TYPE_IDS}; got {raw!r}")
    return value


def _absolute_path(raw: str | Path, *, label: str) -> Path:
    if not isinstance(raw, (str, Path)):
        raise V23Error(f"{label} must be a path; got {raw!r}")
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _canonical_run_root(type_id: str) -> Path:
    return CANONICAL_TRAINING_ROOT / type_id.lower()


def _canonical_launcher_type_root(type_id: str) -> Path:
    return CANONICAL_LAUNCHER_ROOT / type_id.lower()


def _default_record_path(type_id: str, run_root: Path | None = None) -> Path:
    root = run_root if run_root is not None else _canonical_run_root(type_id)
    return root / "type_smoke_record.json"


def _type_paths(
    type_id: str,
    *,
    run_root: Path | None = None,
    launcher_root: Path | None = None,
) -> dict[str, Path]:
    run = (run_root or _canonical_run_root(type_id)).resolve()
    launcher = (launcher_root or CANONICAL_LAUNCHER_ROOT).resolve()
    launcher_type = launcher / type_id.lower()
    return {
        "run_root": run,
        "launcher_root": launcher,
        "launcher_type_root": launcher_type,
        "record": _default_record_path(type_id, run),
        "resolved_config": run / "config.yaml",
        "checkpoint": run / "model_step_000010.pt",
        "command": launcher_type / "command.txt",
        "environment": launcher_type / "environment.json",
        "stdout": launcher_type / "stdout.log",
        "stderr": launcher_type / "stderr.log",
        "returncode": launcher_type / "returncode.txt",
    }


def _command_for_type(type_id: str, *, run_root: Path) -> tuple[list[str], dict[str, str]]:
    spec = TYPE_MATRIX[type_id]
    rp0_enabled = str(bool(spec["rp0_enabled"])).lower()
    checkpoint = str(spec["checkpoint"])
    command = [
        "env",
        "CUDA_DEVICE_ORDER=PCI_BUS_ID",
        f"CUDA_VISIBLE_DEVICES={spec['gpu']}",
        "ACCELERATE_TORCH_DEVICE=cuda:0",
        "WANDB_MODE=disabled",
        f"PYTHONPATH={REPO_ROOT}",
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.train_agent_trl",
        f"+exp={EXPERIMENT_CONFIG_OVERRIDE}",
        f"+ablation={CONFIG_OVERRIDE}",
        f"++experiment_dir={run_root}",
        f"++output_dir={run_root / 'output'}",
        "++project_name=a2_piper_full_stage_a2_base_smoke",
        f"++experiment_name={type_id.lower()}",
        f"++v23_cell={spec['cell']}",
        "++v23_seed=0",
        "++v23_initialization=warm_head_reset",
        "++v23_door_regime=D0",
        f"++v23_posture_mode={spec['posture_mode']}",
        "++v23_training_enabled=true",
        "++v23_formal_launchable=false",
        "++v23_contract_only=false",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++seed=0",
        "++num_envs=64",
        "++num_gpus=1",
        "++multi_gpu=false",
        "++headless=true",
        "++use_wandb=false",
        "++algo.trl.num_total_batches=10",
        "++algo.trl.report_to=none",
        "++callbacks.model_save.save_frequency=10",
        f"++algo.config.rp0_enabled={rp0_enabled}",
        "++algo.config.rp0_mask_indices=[3,4]",
        "++algo.config.rp0_neutral_value=0.0",
        f"++env.config.a2_v23_rp0_enabled={rp0_enabled}",
        "++env.config.a2_v23_rp0_mask_indices=[3,4]",
        "++env.config.a2_v23_rp0_neutral_value=0.0",
        "++env.config.a2_v23_effort_profile_nm=40.0",
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
        "++simulator.config.render_results=false",
        "++simulator.config.cameras.enable_cameras=false",
    ]
    environment = {
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES": str(spec["gpu"]),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }
    return command, environment


def build_plan() -> dict[str, Any]:
    rows = []
    for type_id in TYPE_IDS:
        spec = TYPE_MATRIX[type_id]
        paths = _type_paths(type_id)
        command, environment = _command_for_type(type_id, run_root=paths["run_root"])
        rows.append(
            {
                "type": type_id,
                "cell": spec["cell"],
                "physical_gpu": spec["gpu"],
                "logical_device": "cuda:0",
                "initialization": spec["initialization"],
                "door_regime": "D0",
                "posture_mode": spec["posture_mode"],
                "seed": SEED,
                "num_envs": NUM_ENVS,
                "num_processes": 1,
                "num_total_batches": NUM_BATCHES,
                "save_frequency": SAVE_FREQUENCY,
                "checkpoint": spec["checkpoint"],
                "checkpoint_load_mode": spec["checkpoint_load_mode"],
                "rp0_enabled": spec["rp0_enabled"],
                "rp0_mask_indices": list(RP0_INDICES),
                "rp0_neutral_value": RP0_NEUTRAL,
                "run_root": str(paths["run_root"]),
                "launcher_type_root": str(paths["launcher_type_root"]),
                "record_path": str(paths["record"]),
                "command": command,
                "command_shell": shlex.join(command),
                "environment": environment,
            }
        )
    return {
        "schema": "a2_piper_v23_f1_d0_head_reset_plan_v1",
        "task_id": TASK_ID,
        "revision": REVISION,
        "status": "P0_10_F1_D0_HEAD_RESET_PLAN_READY",
        "f1_marker": F1_MARKER,
        "config_path": str(CONFIG_PATH),
        "config_override": CONFIG_OVERRIDE,
        "training_root": str(CANONICAL_TRAINING_ROOT),
        "launcher_root": str(CANONICAL_LAUNCHER_ROOT),
        "aggregate_path": str(CANONICAL_AGGREGATE_PATH),
        "types": list(TYPE_IDS),
        "rows": rows,
        "one_shot_per_type": True,
        "retry_policy": "none",
        "no_training_in_plan": True,
        "historical_p09_mutation": False,
        "excluded_claims": [
            "NO_D1_TRAINING_OR_MIXTURE_CLAIM",
            "NO_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
            "NO_G7_OR_G8_LAUNCH_WHILE_D1_BLOCKED",
        ],
    }


def _nested(mapping: Mapping[str, Any], *keys: str, label: str) -> Any:
    current: Any = mapping
    for key in keys:
        current = _mapping(current, label=label).get(key)
        if current is None:
            raise V23Error(f"{label} is missing key {'.'.join(keys)}")
    return current


def _normalise_checkpoint(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise V23Error(f"checkpoint must be a non-empty path; got {value!r}")
    return str(_absolute_path(value, label="checkpoint"))


def _validate_resolved_config(config_path: Path, type_id: str) -> dict[str, Any]:
    try:
        import yaml

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise V23Error(f"type resolved config is not valid YAML: {config_path}") from exc
    config = dict(_mapping(config, label="resolved config"))
    spec = TYPE_MATRIX[type_id]
    for section in (
        "trainer",
        "callbacks",
        "algo",
        "env",
        "simulator",
        "robot",
        "obs",
        "wandb",
        "terrain",
        "domain_rand",
    ):
        if section not in config:
            raise V23Error(f"{type_id} resolved config is missing canonical section {section!r}")
    trainer = _mapping(config.get("trainer"), label="trainer")
    if trainer.get("_target_") != "gr00t.rl.trl.trainer.ppo_trainer_a2_base_api.TRLPPOTrainer":
        raise V23Error(f"{type_id} resolved config is not using the canonical TRL trainer")
    callbacks = _mapping(config.get("callbacks"), label="callbacks")
    model_save = _mapping(callbacks.get("model_save"), label="callbacks.model_save")
    if model_save.get("_target_") != "gr00t.rl.trl.callbacks.model_save_callback.ModelSaveCallback":
        raise V23Error(f"{type_id} resolved config is not using ModelSaveCallback")
    if config.get("exp_base") != "${hydra:runtime.choices.exp}" or config.get("exp_var") != "lstm":
        raise V23Error(f"{type_id} resolved config is not the canonical LSTM experiment")
    exact = {
        "v23_schema": "a2_piper_base_v23_f1_d0_head_reset_smoke_v1",
        "v23_config_state": "P0_10_F1_D0_HEAD_RESET_TYPE_SMOKE",
        "v23_formal_launchable": False,
        "v23_contract_only": False,
        "v23_training_enabled": True,
        "v23_cell": spec["cell"],
        "v23_seed": SEED,
        "v23_initialization": "warm_head_reset",
        "v23_door_regime": "D0",
        "v23_posture_mode": spec["posture_mode"],
        "v23_effort_profile_nm": EFFORT_NM,
        "v23_reward_registry_source": "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v23.yaml",
        "v23_common_reward_state": "P0_6_REWARD_REGISTRY_SELECTED",
        "num_envs": NUM_ENVS,
        "num_gpus": 1,
        "multi_gpu": False,
        "seed": SEED,
        "headless": True,
        "use_wandb": False,
        "checkpoint_load_mode": "policy_only",
        "auto_load_latest": False,
    }
    for key, expected in exact.items():
        if config.get(key) != expected:
            raise V23Error(
                f"{type_id} resolved config field {key!r} disagrees: "
                f"got {config.get(key)!r}, expected {expected!r}"
            )
    expected_checkpoint = str(_absolute_path(V23_WARM_START_PATH, label="warm checkpoint"))
    if _normalise_checkpoint(config.get("checkpoint")) != expected_checkpoint:
        raise V23Error(f"{type_id} resolved checkpoint is not the fixed warm source")

    trl = _mapping(_nested(config, "algo", label="resolved config"), label="algo")
    trl = _mapping(trl.get("trl"), label="algo.trl")
    if trl.get("num_total_batches") != NUM_BATCHES or trl.get("report_to") != "none":
        raise V23Error(f"{type_id} resolved trainer budget/reporting is not the F1 contract")
    if model_save.get("save_frequency") != SAVE_FREQUENCY:
        raise V23Error(f"{type_id} resolved save frequency is not {SAVE_FREQUENCY}")

    algo_config = _mapping(_nested(config, "algo", label="resolved config").get("config"), label="algo.config")
    if algo_config.get("rp0_enabled") != spec["rp0_enabled"]:
        raise V23Error(f"{type_id} actor RP0 selector disagrees with its type")
    if algo_config.get("rp0_mask_indices") != RP0_INDICES:
        raise V23Error(f"{type_id} actor RP0 indices are not {RP0_INDICES}")
    if float(algo_config.get("rp0_neutral_value")) != RP0_NEUTRAL:
        raise V23Error(f"{type_id} actor RP0 neutral value is not 0.0")
    eval_config = _mapping(algo_config.get("eval"), label="algo.config.eval")
    for key in (
        "a2_v23_p05_runtime_export",
        "a2_v23_p06_policy_only",
        "a2_v23_p08_state_bank_export",
        "a2_v23_p0_runtime_export",
    ):
        if eval_config.get(key) is not False:
            raise V23Error(f"{type_id} must keep {key}=false")

    env_config = _mapping(_nested(config, "env", label="resolved config").get("config"), label="env.config")
    env_exact = {
        "a2_v23_formal_launch": False,
        "a2_v23_stationary_rent_runtime_enabled": False,
        "a2_v23_effort_profile_nm": EFFORT_NM,
        "a2_v23_effort_profile_source": "P0_2_MEASURED_FREEZE",
        "a2_v23_rp0_enabled": spec["rp0_enabled"],
        "a2_v23_rp0_mask_indices": RP0_INDICES,
        "a2_v23_rp0_neutral_value": RP0_NEUTRAL,
        "enable_staged_reset": True,
        "staged_reset_ratios": [0.5, 0.1, 0.1, 0.1, 0.1, 0.1],
    }
    for key, expected in env_exact.items():
        if env_config.get(key) != expected:
            raise V23Error(
                f"{type_id} resolved env.config.{key} disagrees: "
                f"got {env_config.get(key)!r}, expected {expected!r}"
            )
    simulator_config = _mapping(_nested(config, "simulator", label="resolved config").get("config"), label="simulator.config")
    if simulator_config.get("render_results") is not False:
        raise V23Error(f"{type_id} render_results must be false")
    cameras = _mapping(simulator_config.get("cameras"), label="simulator.config.cameras")
    if cameras.get("enable_cameras") is not False:
        raise V23Error(f"{type_id} cameras must be disabled")
    return {
        "path": str(config_path),
        "schema": config["v23_schema"],
        "cell": config["v23_cell"],
        "initialization": config["v23_initialization"],
        "posture_mode": config["v23_posture_mode"],
        "checkpoint": config["checkpoint"],
        "checkpoint_load_mode": config["checkpoint_load_mode"],
        "rp0_enabled": algo_config["rp0_enabled"],
        "rp0_mask_indices": list(algo_config["rp0_mask_indices"]),
        "rp0_neutral_value": float(algo_config["rp0_neutral_value"]),
        "effort_profile_nm": float(config["v23_effort_profile_nm"]),
        "render_results": simulator_config["render_results"],
        "cameras_enabled": cameras["enable_cameras"],
    }


def _finite_checkpoint_value(value: Any, *, label: str, allow_none: bool) -> None:
    try:
        import torch
    except ImportError as exc:
        raise V23Error("runtime checkpoint validation requires torch") from exc
    if value is None:
        if allow_none:
            return
        raise V23Error(f"checkpoint contains an unsupported null at {label}")
    if isinstance(value, torch.Tensor):
        if not bool(torch.isfinite(value).all().item()):
            raise V23Error(f"checkpoint contains a non-finite tensor at {label}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, (str, Integral)) or isinstance(key, bool):
                raise V23Error(f"checkpoint mapping key at {label} must be a string or integer")
            _finite_checkpoint_value(child, label=f"{label}.{key}", allow_none=allow_none)
        return
    if isinstance(value, (list, tuple, deque)):
        for index, child in enumerate(value):
            _finite_checkpoint_value(child, label=f"{label}[{index}]", allow_none=allow_none)
        return
    if isinstance(value, bool):
        return
    if isinstance(value, (Integral, Real)):
        if not math.isfinite(float(value)):
            raise V23Error(f"checkpoint contains a non-finite number at {label}")
        return
    raise V23Error(f"checkpoint contains an unsupported value at {label}: {type(value).__name__}")


def _validate_checkpoint(checkpoint_path: Path) -> dict[str, Any]:
    if checkpoint_path.is_symlink() or not checkpoint_path.is_file():
        raise V23Error(f"missing terminal checkpoint: {checkpoint_path}")
    if checkpoint_path.name != "model_step_000010.pt":
        raise V23Error("terminal checkpoint must be model_step_000010.pt")
    try:
        import torch

        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except (OSError, RuntimeError, ValueError, EOFError) as exc:
        raise V23Error(f"terminal checkpoint cannot be loaded: {checkpoint_path}") from exc
    if not isinstance(checkpoint, Mapping):
        raise V23Error("terminal checkpoint must be a mapping")
    keys = set(checkpoint)
    missing = CHECKPOINT_REQUIRED_KEYS - keys
    unsupported = keys - CHECKPOINT_REQUIRED_KEYS - CHECKPOINT_OPTIONAL_KEYS
    if missing or unsupported:
        raise V23Error(
            f"terminal checkpoint key contract disagrees: missing={sorted(missing)}, "
            f"unsupported={sorted(unsupported)}"
        )
    for key in (
        "policy_state_dict",
        "value_state_dict",
        "optimizer_state_dict",
        "lr_scheduler_state_dict",
        "env_state_dict",
    ):
        component = checkpoint[key]
        if not isinstance(component, Mapping) or not component:
            raise V23Error(f"terminal checkpoint component {key!r} must be a non-empty mapping")
        _finite_checkpoint_value(component, label=f"checkpoint.{key}", allow_none=key != "policy_state_dict")
    state = checkpoint["state"]
    if type(state).__name__ != "OnlineTrainerState" or not hasattr(state, "__dict__"):
        raise V23Error("terminal checkpoint state must be an OnlineTrainerState object")
    state_dict = vars(state)
    missing_state = [key for key in TRAINER_STATE_FIELDS if key not in state_dict]
    if missing_state:
        raise V23Error(f"terminal checkpoint trainer state is missing fields: {missing_state}")
    if state_dict["global_step"] != NUM_BATCHES:
        raise V23Error(
            f"terminal checkpoint trainer global_step must be {NUM_BATCHES}; "
            f"got {state_dict['global_step']!r}"
        )
    args = checkpoint["args"]
    if type(args).__name__ != "PPOConfig" or not hasattr(args, "__dict__"):
        raise V23Error("terminal checkpoint args must be the PPOConfig metadata object")
    if "homie_state_dict" in checkpoint:
        _finite_checkpoint_value(checkpoint["homie_state_dict"], label="checkpoint.homie_state_dict", allow_none=False)
    return {
        "path": str(checkpoint_path),
        "file_name": checkpoint_path.name,
        "global_step": NUM_BATCHES,
        "finite": True,
        "producer": "ModelSaveCallback",
        "mandatory_keys": sorted(CHECKPOINT_REQUIRED_KEYS),
        "optional_keys": sorted(CHECKPOINT_OPTIONAL_KEYS),
    }


def _validate_run_output(type_id: str, paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "resolved_config": _validate_resolved_config(paths["resolved_config"], type_id),
        "checkpoint": _validate_checkpoint(paths["checkpoint"]),
        "global_step": NUM_BATCHES,
    }


def _expected_head_reset() -> dict[str, Any]:
    return {
        "marker": F1_MARKER,
        "enabled": True,
        "weight_key": "actor_module.module.6.weight",
        "bias_key": "actor_module.module.6.bias",
        "std_key": "std",
        "row_slice": [3, 5],
        "std_value": 0.8,
    }


def _validate_claimed_pass_record(
    record_path: Path,
    type_id: str,
    *,
    expected_run_root: Path,
    expected_launcher_type_root: Path,
    expected_record_path: Path,
    candidate_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = dict(candidate_record) if candidate_record is not None else read_json(record_path)
    spec = TYPE_MATRIX[type_id]
    if record.get("status") != TYPE_PASS_STATUS:
        raise V23Error(f"{type_id} record does not claim the F1 runtime-pass status")
    expected = {
        "schema": TYPE_RECORD_SCHEMA,
        "task_id": TASK_ID,
        "revision": REVISION,
        "type": type_id,
        "cell": spec["cell"],
        "physical_gpu": spec["gpu"],
        "logical_device": "cuda:0",
        "initialization": "warm_head_reset",
        "door_regime": "D0",
        "posture_mode": spec["posture_mode"],
        "seed": SEED,
        "num_envs": NUM_ENVS,
        "num_processes": 1,
        "num_total_batches": NUM_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "checkpoint": spec["checkpoint"],
        "checkpoint_load_mode": "policy_only",
        "run_root": str(expected_run_root.resolve()),
        "launcher_type_root": str(expected_launcher_type_root.resolve()),
        "record_path": str(expected_record_path.resolve()),
        "resolved_config_path": str((expected_run_root / "config.yaml").resolve()),
        "terminal_checkpoint_path": str((expected_run_root / "model_step_000010.pt").resolve()),
        "subprocess_returncode": 0,
        "global_step": NUM_BATCHES,
        "retry_policy": "none",
    }
    mismatch = [key for key, value in expected.items() if record.get(key) != value]
    if mismatch:
        raise V23Error(f"{type_id} F1 PASS record disagrees on exact fields: {mismatch}")
    if record.get("f1_marker") != F1_MARKER or record.get("head_reset") != _expected_head_reset():
        raise V23Error(f"{type_id} F1 head-reset provenance is not exact")
    command, environment = _command_for_type(type_id, run_root=expected_run_root)
    if record.get("command") != command or record.get("command_shell") != shlex.join(command):
        raise V23Error(f"{type_id} F1 launcher command identity is not exact")
    if record.get("environment") != environment:
        raise V23Error(f"{type_id} F1 launcher environment identity is not exact")
    evidence = _mapping(record.get("evidence"), label=f"{type_id} evidence")
    paths = _type_paths(
        type_id,
        run_root=expected_run_root,
        launcher_root=expected_launcher_type_root.parent,
    )
    paths["record"] = expected_record_path.resolve()
    runtime_evidence = _validate_run_output(type_id, paths)
    if dict(evidence) != runtime_evidence:
        raise V23Error(f"{type_id} F1 evidence does not match revalidated artifacts")
    return record


def _write_new_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise V23Error(f"refusing to overwrite existing launcher artifact: {path}")
    path.write_text(value, encoding="utf-8")


def _write_failure_record(
    *,
    type_id: str,
    paths: Mapping[str, Path],
    command: Sequence[str],
    environment: Mapping[str, str],
    returncode: int | None,
    error: str,
) -> dict[str, Any]:
    spec = TYPE_MATRIX[type_id]
    record = {
        "schema": TYPE_RECORD_SCHEMA,
        "status": TYPE_FAIL_STATUS,
        "task_id": TASK_ID,
        "revision": REVISION,
        "type": type_id,
        "cell": spec["cell"],
        "physical_gpu": spec["gpu"],
        "logical_device": "cuda:0",
        "initialization": "warm_head_reset",
        "door_regime": "D0",
        "posture_mode": spec["posture_mode"],
        "seed": SEED,
        "num_envs": NUM_ENVS,
        "num_processes": 1,
        "num_total_batches": NUM_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "checkpoint": spec["checkpoint"],
        "checkpoint_load_mode": "policy_only",
        "f1_marker": F1_MARKER,
        "head_reset": _expected_head_reset(),
        "run_root": str(paths["run_root"]),
        "launcher_type_root": str(paths["launcher_type_root"]),
        "record_path": str(paths["record"]),
        "command": list(command),
        "command_shell": shlex.join(command),
        "environment": dict(environment),
        "subprocess_returncode": returncode,
        "error": error,
        "retry_policy": "none",
    }
    if not paths["record"].exists():
        write_json(paths["record"], record)
    return record


def run_type(
    type_id: str,
    *,
    gpu: int,
    run_root: Path | None,
    launcher_root: Path | None,
    record_path: Path | None,
) -> tuple[dict[str, Any], int]:
    type_id = _type_id(type_id)
    spec = TYPE_MATRIX[type_id]
    if isinstance(gpu, bool) or gpu != spec["gpu"]:
        raise V23Error(f"{type_id} must run on its assigned physical GPU{spec['gpu']}")
    paths = _type_paths(type_id, run_root=run_root, launcher_root=launcher_root)
    if record_path is not None:
        paths["record"] = record_path.resolve()
    if paths["record"].parent != paths["run_root"]:
        raise V23Error("per-type record must live directly under its type run root")
    for root, label in (
        (paths["run_root"], "type run root"),
        (paths["launcher_type_root"], "launcher type root"),
    ):
        if root.exists():
            if root.is_symlink() or not root.is_dir():
                raise V23Error(f"{label} is not a directory: {root}")
            if any(root.iterdir()):
                raise V23Error(f"{label} must be fresh and empty: {root}")
        else:
            root.mkdir(parents=True, exist_ok=True)
    command, environment = _command_for_type(type_id, run_root=paths["run_root"])
    _write_new_text(paths["command"], shlex.join(command) + "\n")
    write_json(paths["environment"], dict(environment))
    try:
        child_env = dict(os.environ)
        child_env.update(environment)
        with paths["stdout"].open("x", encoding="utf-8") as stdout, paths["stderr"].open(
            "x", encoding="utf-8"
        ) as stderr:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                env=child_env,
                stdout=stdout,
                stderr=stderr,
                check=False,
            )
        returncode: int | None = int(completed.returncode)
    except (OSError, subprocess.SubprocessError) as exc:
        returncode = None
        _write_new_text(paths["returncode"], "LAUNCH_ERROR\n")
        return _write_failure_record(
            type_id=type_id,
            paths=paths,
            command=command,
            environment=environment,
            returncode=returncode,
            error=f"subprocess launch failed: {exc}",
        ), 2
    _write_new_text(paths["returncode"], f"{returncode}\n")
    if returncode != 0:
        return _write_failure_record(
            type_id=type_id,
            paths=paths,
            command=command,
            environment=environment,
            returncode=returncode,
            error=f"training subprocess returned nonzero code {returncode}",
        ), 2
    try:
        evidence = _validate_run_output(type_id, paths)
    except V23Error as exc:
        return _write_failure_record(
            type_id=type_id,
            paths=paths,
            command=command,
            environment=environment,
            returncode=returncode,
            error=str(exc),
        ), 2
    record = {
        "schema": TYPE_RECORD_SCHEMA,
        "status": TYPE_PASS_STATUS,
        "task_id": TASK_ID,
        "revision": REVISION,
        "type": type_id,
        "cell": spec["cell"],
        "physical_gpu": spec["gpu"],
        "logical_device": "cuda:0",
        "initialization": "warm_head_reset",
        "door_regime": "D0",
        "posture_mode": spec["posture_mode"],
        "seed": SEED,
        "num_envs": NUM_ENVS,
        "num_processes": 1,
        "num_total_batches": NUM_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "checkpoint": spec["checkpoint"],
        "checkpoint_load_mode": "policy_only",
        "f1_marker": F1_MARKER,
        "head_reset": _expected_head_reset(),
        "run_root": str(paths["run_root"]),
        "launcher_type_root": str(paths["launcher_type_root"]),
        "record_path": str(paths["record"]),
        "resolved_config_path": str(paths["resolved_config"]),
        "terminal_checkpoint_path": str(paths["checkpoint"]),
        "command": command,
        "command_shell": shlex.join(command),
        "environment": environment,
        "subprocess_returncode": returncode,
        "global_step": NUM_BATCHES,
        "evidence": evidence,
        "retry_policy": "none",
    }
    try:
        _validate_claimed_pass_record(
            paths["record"],
            type_id,
            expected_run_root=paths["run_root"],
            expected_launcher_type_root=paths["launcher_type_root"],
            expected_record_path=paths["record"],
            candidate_record=record,
        )
    except V23Error as exc:
        return _write_failure_record(
            type_id=type_id,
            paths=paths,
            command=command,
            environment=environment,
            returncode=returncode,
            error=f"pre-write F1 PASS validation failed: {exc}",
        ), 2
    write_json(paths["record"], record)
    return record, 0


def _record_path(raw: str) -> Path:
    value = raw
    prefix, separator, suffix = raw.partition("=")
    if separator and prefix.upper() in TYPE_MATRIX:
        value = suffix
    path = _absolute_path(value, label="type record")
    if path.is_symlink() or not path.is_file():
        raise V23Error(f"type record is not a regular file: {path}")
    return path


def _record_output_path(raw: str) -> Path:
    value = raw
    prefix, separator, suffix = raw.partition("=")
    if separator and prefix.upper() in TYPE_MATRIX:
        value = suffix
    path = _absolute_path(value, label="type record output")
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise V23Error(f"type record output is not a writable file path: {path}")
    return path


def _reduce_records(record_paths: Sequence[Path], *, output: Path) -> tuple[dict[str, Any], int]:
    if len(record_paths) != 2:
        raise V23Error("REDUCE requires exactly two explicit F1 type record paths")
    if len({path.resolve() for path in record_paths}) != 2:
        raise V23Error("REDUCE requires two unique explicit F1 type record paths")
    passed: list[str] = []
    failed: list[str] = []
    missing: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    record_paths_by_type: dict[str, Path] = {}
    for raw_path in record_paths:
        path = raw_path.resolve()
        if not path.is_file() or path.is_symlink():
            leaf = path.parent.name.upper()
            missing.append(leaf if leaf in TYPE_MATRIX else str(path))
            continue
        try:
            record = read_json(path)
        except V23Error:
            failed.append(str(path))
            continue
        raw_type = record.get("type")
        if not isinstance(raw_type, str) or raw_type.upper() not in TYPE_MATRIX:
            failed.append(str(path))
            continue
        type_id = _type_id(raw_type)
        if type_id in records:
            raise V23Error(f"REDUCE contains duplicate F1 type record {type_id}")
        records[type_id] = record
        record_paths_by_type[type_id] = path
        if record.get("status") != TYPE_PASS_STATUS:
            failed.append(type_id)
            continue
        try:
            expected_run_root = _absolute_path(record.get("run_root"), label=f"{type_id} run root")
            expected_launcher_type_root = _absolute_path(
                record.get("launcher_type_root"), label=f"{type_id} launcher root"
            )
            _validate_claimed_pass_record(
                path,
                type_id,
                expected_run_root=expected_run_root,
                expected_launcher_type_root=expected_launcher_type_root,
                expected_record_path=path,
            )
        except V23Error:
            failed.append(type_id)
        else:
            passed.append(type_id)

    for type_id in TYPE_IDS:
        if type_id not in records and type_id not in missing:
            missing.append(type_id)
    run_roots = [record.get("run_root") for record in records.values() if record.get("run_root")]
    checkpoints = [
        record.get("terminal_checkpoint_path")
        for record in records.values()
        if record.get("terminal_checkpoint_path")
    ]
    launcher_roots = [
        record.get("launcher_type_root")
        for record in records.values()
        if record.get("launcher_type_root")
    ]
    disjoint_outputs = (
        len(run_roots) == len(set(run_roots))
        and len(checkpoints) == len(set(checkpoints))
        and len(launcher_roots) == len(set(launcher_roots))
    )
    passed = sorted(set(passed), key=TYPE_IDS.index)
    failed = sorted(set(failed), key=TYPE_IDS.index if all(item in TYPE_IDS for item in failed) else str)
    missing = sorted(set(missing), key=lambda value: TYPE_IDS.index(value) if value in TYPE_IDS else len(TYPE_IDS))
    all_pass = passed == list(TYPE_IDS) and not failed and not missing and disjoint_outputs
    aggregate = {
        "schema": AGGREGATE_SCHEMA,
        "status": PASS_STATUS if all_pass else INCOMPLETE_STATUS,
        "task_id": TASK_ID,
        "revision": REVISION,
        "f1_marker": F1_MARKER,
        "f1_smoke_complete": all_pass,
        "p010_f1_status": "COMPLETE" if all_pass else "INCOMPLETE",
        "p010_d0_full_pilot_admission": False,
        "formal_admission": False,
        "d1_admission": False,
        "release_receipt": False,
        "seed": SEED,
        "num_envs": NUM_ENVS,
        "num_processes": 1,
        "num_total_batches": NUM_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "passed_types": passed,
        "failed_types": failed,
        "missing_types": missing,
        "explicit_record_paths": [str(path) for path in record_paths],
        "records": {
            type_id: {
                "path": str(record_paths_by_type[type_id]),
                "status": record.get("status"),
                "run_root": record.get("run_root"),
                "physical_gpu": record.get("physical_gpu"),
            }
            for type_id, record in records.items()
        },
        "output_roots_disjoint": disjoint_outputs,
        "launcher_type_roots_disjoint": len(launcher_roots) == len(set(launcher_roots)),
        "retry_policy": "none",
        "typed_exit_code": 0 if all_pass else 2,
        "historical_p09_mutation": False,
        "excluded_claims": [
            "NO_D1_TRAINING_OR_MIXTURE_CLAIM",
            "NO_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
            "NO_G7_OR_G8_LAUNCH_WHILE_D1_BLOCKED",
        ],
    }
    write_json(output, aggregate)
    return aggregate, (0 if all_pass else 2)


def _flatten_records(groups: Sequence[Sequence[str]] | None, direct: Sequence[str] | None) -> list[Path]:
    values: list[str] = []
    for group in groups or ():
        values.extend(group)
    values.extend(direct or ())
    return [_record_path(value) for value in values]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "RUN_TYPE", "REDUCE"), required=True)
    parser.add_argument("--type", dest="type_id", default=None)
    parser.add_argument("--gpu", type=int, default=None)
    parser.add_argument("--run-root", type=Path, default=None)
    parser.add_argument("--launcher-root", type=Path, default=None)
    parser.add_argument("--record", dest="record_groups", action="append", nargs="+")
    parser.add_argument("--records", dest="record_list", nargs=2)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.mode == "PLAN":
        if args.type_id is not None or args.gpu is not None:
            raise V23Error("PLAN emits exactly two F1 types and does not accept --type/--gpu")
        payload = build_plan()
        if args.output is None:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            target = _absolute_path(args.output, label="PLAN output")
            write_json(target, payload)
            print(json.dumps({"status": "WRITTEN", "path": str(target)}, indent=2))
        return 0

    if args.mode == "RUN_TYPE":
        if args.type_id is None or args.gpu is None:
            raise V23Error("RUN_TYPE requires --type and its exact --gpu")
        type_id = _type_id(args.type_id)
        run_root = None if args.run_root is None else _absolute_path(args.run_root, label="run root")
        launcher_root = None if args.launcher_root is None else _absolute_path(args.launcher_root, label="launcher root")
        record_values = [value for group in (args.record_groups or ()) for value in group]
        record_values.extend(args.record_list or ())
        if len(record_values) > 1:
            raise V23Error("RUN_TYPE accepts at most one --record output path")
        record_path = None if not record_values else _record_output_path(record_values[0])
        record, exit_code = run_type(
            type_id,
            gpu=args.gpu,
            run_root=run_root,
            launcher_root=launcher_root,
            record_path=record_path,
        )
        print(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2))
        return exit_code

    if args.type_id is not None or args.gpu is not None:
        raise V23Error("REDUCE does not accept --type/--gpu")
    record_paths = _flatten_records(args.record_groups, args.record_list)
    if len(record_paths) != 2:
        raise V23Error("REDUCE requires exactly two explicit F1 type record paths")
    output = CANONICAL_AGGREGATE_PATH if args.output is None else _absolute_path(args.output, label="aggregate output")
    aggregate, exit_code = _reduce_records(record_paths, output=output)
    print(json.dumps(aggregate, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        print(f"V23 F1 D0 HEAD RESET SMOKE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
