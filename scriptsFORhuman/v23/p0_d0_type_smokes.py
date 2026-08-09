"""Run or reduce the admitted P0.9 D0 four-type training smokes.

The tool deliberately has three explicit modes:

* ``PLAN`` validates the R78 admission and prints four one-shot commands.
* ``RUN_TYPE`` launches exactly one selected type on its assigned physical GPU.
* ``REDUCE`` consumes exactly four explicit type records and writes the
  canonical aggregate receipt.

It does not launch training from ``PLAN`` and does not retry a failed process.
P0.9 is a bounded D0 training smoke only; the receipt never admits D1, formal,
or release work.
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
    from ._v23_common import REPO_ROOT, V23Error, V23_WARM_START_PATH, read_json, write_json
except ImportError:  # direct ``python scriptsFORhuman/v23/p0_d0_type_smokes.py``
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


TASK_ID = "v23-p09-vulkan-evidence-fix-r112"
REVISION = "R112"
CONFIG_PATH = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v23_p09_d0_type_smoke.yaml"
CONFIG_OVERRIDE = "wbmanip/base_v23_p09_d0_type_smoke"
PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")

R78_RECEIPT_PATH = REPO_ROOT / "logs_eval/base_v23/p0/state_bank/state_bank_plan.json"
CANONICAL_TRAINING_ROOT = (
    REPO_ROOT / "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v23/r112"
)
CANONICAL_LAUNCHER_ROOT = (
    REPO_ROOT / "logs_rl/launchers/base_v23/r112_p09_d0_type_smokes_20260810"
)
CANONICAL_AGGREGATE_PATH = (
    REPO_ROOT / "logs_eval/base_v23/p0/p09_d0_type_smoke_receipt.json"
)

TYPE_RECORD_SCHEMA = "a2_piper_v23_p09_type_smoke_record_v1"
AGGREGATE_SCHEMA = "a2_piper_v23_p09_d0_four_type_receipt_v1"
R78_SCHEMA = "a2_piper_v23_p08_partial_a0_d0_receipt_v1"
R78_STATUS = "PARTIAL_A0_D0_PLUMBING_RUNTIME_VERIFIED"
PASS_STATUS = "P0_9_D0_FOUR_TYPE_SMOKES_RUNTIME_VERIFIED"
INCOMPLETE_STATUS = "P0_9_D0_TYPE_SMOKE_INCOMPLETE"
RP0_INDICES = [3, 4]
RP0_NEUTRAL = 0.0
EFFORT_NM = 40.0
NUM_ENVS = 64
NUM_BATCHES = 10
SAVE_FREQUENCY = 10
SEED = 0
TYPE_IDS = ("WARM_FULL", "WARM_RP0", "SCRATCH_FULL", "SCRATCH_RP0")
EXPERIMENT_CONFIG_OVERRIDE = "wbmanip/door_open_a2_base_lstm"
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
    "WARM_FULL": {
        "cell": "G1",
        "gpu": 0,
        "initialization": "v22_warm",
        "posture_mode": "FULL",
        "checkpoint": V23_WARM_START_PATH,
        "checkpoint_load_mode": "policy_only",
        "rp0_enabled": False,
    },
    "WARM_RP0": {
        "cell": "G2",
        "gpu": 1,
        "initialization": "v22_warm",
        "posture_mode": "RP0",
        "checkpoint": V23_WARM_START_PATH,
        "checkpoint_load_mode": "policy_only",
        "rp0_enabled": True,
    },
    "SCRATCH_FULL": {
        "cell": "G3",
        "gpu": 2,
        "initialization": "scratch",
        "posture_mode": "FULL",
        "checkpoint": None,
        "checkpoint_load_mode": "full",
        "rp0_enabled": False,
    },
    "SCRATCH_RP0": {
        "cell": "G4",
        "gpu": 3,
        "initialization": "scratch",
        "posture_mode": "RP0",
        "checkpoint": None,
        "checkpoint_load_mode": "full",
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


def validate_r78_admission() -> dict[str, Any]:
    """Validate only the bounded R78 admission boundary consumed by P0.9."""

    receipt = read_json(R78_RECEIPT_PATH)
    expected = {
        "schema": R78_SCHEMA,
        "status": R78_STATUS,
        "p08_overall_status": "PARTIAL_INCOMPLETE",
        "p09_d0_smoke_admission": True,
        "formal_admission": False,
        "release_receipt": False,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "recurrent_prefix_status": "CAPTURED_NOT_REEXECUTED",
        "checkpoint_load_mode": "policy_only",
        "checkpoint_step": 1250,
        "seed": 0,
        "num_envs": 16,
        "binding_count": 15,
        "typed_exit_code": 0,
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise V23Error(
                f"R78 admission field {key!r} disagrees: "
                f"got {receipt.get(key)!r}, expected {value!r}"
            )
    if receipt.get("target_stages") != [2, 3, 4]:
        raise V23Error("R78 admission must contain exactly target stages [2, 3, 4]")
    entries = receipt.get("entries")
    bindings = receipt.get("bindings")
    if not isinstance(entries, list) or len(entries) != 3:
        raise V23Error("R78 admission must contain exactly three state-bank entries")
    if not isinstance(bindings, list) or len(bindings) != 15:
        raise V23Error("R78 admission must contain exactly fifteen bindings")
    return {
        "path": str(R78_RECEIPT_PATH),
        "schema": receipt["schema"],
        "status": receipt["status"],
        "p08_overall_status": receipt["p08_overall_status"],
        "p09_d0_smoke_admission": receipt["p09_d0_smoke_admission"],
        "entry_count": len(entries),
        "binding_count": len(bindings),
        "formal_admission": receipt["formal_admission"],
        "release_receipt": receipt["release_receipt"],
    }


def _type_paths(type_id: str, *, run_root: Path | None = None, launcher_root: Path | None = None) -> dict[str, Path]:
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
    checkpoint = "null" if spec["checkpoint"] is None else str(spec["checkpoint"])
    rp0_enabled = str(bool(spec["rp0_enabled"])).lower()
    command = [
        "env",
        "CUDA_DEVICE_ORDER=PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES=0,1,2,3",
        f"ACCELERATE_TORCH_DEVICE=cuda:{spec['gpu']}",
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
        f"++v23_initialization={spec['initialization']}",
        "++v23_door_regime=D0",
        f"++v23_posture_mode={spec['posture_mode']}",
        "++v23_training_enabled=true",
        "++v23_formal_launchable=false",
        "++v23_contract_only=false",
        f"++checkpoint={checkpoint}",
        f"++checkpoint_load_mode={spec['checkpoint_load_mode']}",
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
        "CUDA_VISIBLE_DEVICES": "0,1,2,3",
        "ACCELERATE_TORCH_DEVICE": f"cuda:{spec['gpu']}",
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }
    return command, environment


def build_plan() -> dict[str, Any]:
    admission = validate_r78_admission()
    rows = []
    for type_id in TYPE_IDS:
        spec = TYPE_MATRIX[type_id]
        paths = _type_paths(type_id)
        argv, environment = _command_for_type(type_id, run_root=paths["run_root"])
        rows.append(
            {
                "type": type_id,
                "cell": spec["cell"],
                "physical_gpu": spec["gpu"],
                "logical_device": f"cuda:{spec['gpu']}",
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
                "rp0_source": "resolved_config",
                "rp0_reconstruction": "resolved_config_not_checkpoint_restored",
                "run_root": str(paths["run_root"]),
                "launcher_type_root": str(paths["launcher_type_root"]),
                "record_path": str(paths["record"]),
                "command": argv,
                "command_shell": shlex.join(argv),
                "environment": environment,
            }
        )
    return {
        "schema": "a2_piper_v23_p09_d0_type_smoke_plan_v1",
        "task_id": TASK_ID,
        "revision": REVISION,
        "status": "P0_9_D0_TYPE_SMOKE_PLAN_READY",
        "admission": admission,
        "config_path": str(CONFIG_PATH),
        "config_override": CONFIG_OVERRIDE,
        "training_root": str(CANONICAL_TRAINING_ROOT),
        "launcher_root": str(CANONICAL_LAUNCHER_ROOT),
        "aggregate_path": str(CANONICAL_AGGREGATE_PATH),
        "rows": rows,
        "one_shot_per_type": True,
        "retry_policy": "none",
        "no_training_in_plan": True,
        "excluded_claims": [
            "NO_D1_TRAINING_OR_MIXTURE_CLAIM",
            "NO_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
            "NO_P010_ADMISSION_UNTIL_THIS_RECEIPT_PASSES",
        ],
    }


def _nested(mapping: Mapping[str, Any], *keys: str, label: str) -> Any:
    current: Any = mapping
    for key in keys:
        current = _mapping(current, label=label).get(key)
        if current is None:
            raise V23Error(f"{label} is missing key {'.'.join(keys)}")
    return current


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _validate_device_stdout(stdout_path: Path, type_id: str) -> dict[str, Any]:
    """Require the four assigned-device facts emitted by the runtime stdout."""

    spec = TYPE_MATRIX[type_id]
    expected_device = f"cuda:{spec['gpu']}"
    try:
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise V23Error(f"{type_id} runtime stdout cannot be read: {stdout_path}") from exc
    stdout = _ANSI_ESCAPE.sub("", stdout)

    app_devices = re.findall(r"Using device:\s*(cuda:\d+)", stdout)
    if not app_devices or set(app_devices) != {expected_device}:
        raise V23Error(
            f"{type_id} AppLauncher device evidence disagrees: "
            f"got {app_devices!r}, expected only {expected_device!r}"
        )

    torch_indices = [int(value) for value in re.findall(r"CUDA device idx=(\d+)", stdout)]
    if not torch_indices or set(torch_indices) != {spec["gpu"]}:
        raise V23Error(
            f"{type_id} Torch CUDA index evidence disagrees: "
            f"got {torch_indices!r}, expected only {spec['gpu']}"
        )

    environment_devices = [
        f"cuda:{value}"
        for value in re.findall(r"Environment device\s*:\s*cuda:(\d+)", stdout)
    ]
    if not environment_devices or set(environment_devices) != {expected_device}:
        raise V23Error(
            f"{type_id} Isaac environment device evidence disagrees: "
            f"got {environment_devices!r}, expected only {expected_device!r}"
        )

    vulkan_rows: list[tuple[int, int]] = []
    for line in stdout.splitlines():
        match = re.search(
            r"^\s*\|\s*(\d+)\s*\|.*?\|\s*Yes:\s*(\d+)\s*\|", line
        )
        if match:
            row, active = match.groups()
            vulkan_rows.append((int(row), int(active)))
    if set(vulkan_rows) != {(spec["gpu"], 0)}:
        raise V23Error(
            f"{type_id} Kit Vulkan active index evidence disagrees: "
            f"got {vulkan_rows!r}, expected {(spec['gpu'], 0)!r}"
        )

    return {
        "app_launcher_device": expected_device,
        "torch_cuda_device_indices": torch_indices,
        "isaac_environment_devices": environment_devices,
        "kit_vulkan_device_rows": [row for row, _ in vulkan_rows],
        "kit_vulkan_active_groups": [active for _, active in vulkan_rows],
        "stdout_path": str(stdout_path),
    }


def _normalise_checkpoint(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise V23Error(f"checkpoint must be a path or null; got {value!r}")
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
    callbacks_root = _mapping(config.get("callbacks"), label="callbacks")
    model_save = _mapping(callbacks_root.get("model_save"), label="callbacks.model_save")
    if model_save.get("_target_") != "gr00t.rl.trl.callbacks.model_save_callback.ModelSaveCallback":
        raise V23Error(f"{type_id} resolved config is not using ModelSaveCallback")
    if config.get("exp_base") != "${hydra:runtime.choices.exp}" or config.get("exp_var") != "lstm":
        raise V23Error(f"{type_id} resolved config is not the canonical LSTM experiment")
    exact = {
        "v23_schema": "a2_piper_base_v23_p09_d0_type_smoke_v1",
        "v23_config_state": "P0_9_D0_TYPE_SMOKE",
        "v23_formal_launchable": False,
        "v23_contract_only": False,
        "v23_training_enabled": True,
        "v23_cell": spec["cell"],
        "v23_seed": SEED,
        "v23_initialization": spec["initialization"],
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
        "checkpoint_load_mode": spec["checkpoint_load_mode"],
        "auto_load_latest": False,
    }
    for key, expected in exact.items():
        if config.get(key) != expected:
            raise V23Error(
                f"{type_id} resolved config field {key!r} disagrees: "
                f"got {config.get(key)!r}, expected {expected!r}"
            )
    actual_checkpoint = _normalise_checkpoint(config.get("checkpoint"))
    expected_checkpoint = (
        None
        if spec["checkpoint"] is None
        else str(_absolute_path(spec["checkpoint"], label="warm checkpoint"))
    )
    if actual_checkpoint != expected_checkpoint:
        raise V23Error(
            f"{type_id} resolved checkpoint disagrees: "
            f"got {actual_checkpoint!r}, expected {expected_checkpoint!r}"
        )

    trl = _mapping(_nested(config, "algo", label="resolved config"), label="algo")
    trl = _mapping(trl.get("trl"), label="algo.trl")
    if trl.get("num_total_batches") != NUM_BATCHES or trl.get("report_to") != "none":
        raise V23Error(f"{type_id} resolved trainer budget/reporting is not the P0.9 contract")
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
    if "a2_v23_p0_runtime_receipt" in eval_config or "a2_v23_p0_runtime_mode" in eval_config:
        raise V23Error(f"{type_id} must not enable the specialized P0.7 runtime receipt")

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

    rewards = _mapping(config.get("rewards"), label="rewards")
    if rewards.get("reward_penalty_curriculum") is not False:
        raise V23Error(f"{type_id} common reward curriculum selector is not false")
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
            raise V23Error(f"{type_id} common reward scale {key} disagrees")
    return {
        "path": str(config_path),
        "schema": config["v23_schema"],
        "cell": config["v23_cell"],
        "initialization": config["v23_initialization"],
        "posture_mode": config["v23_posture_mode"],
        "checkpoint": config.get("checkpoint"),
        "checkpoint_load_mode": config["checkpoint_load_mode"],
        "rp0_enabled": algo_config["rp0_enabled"],
        "rp0_mask_indices": list(algo_config["rp0_mask_indices"]),
        "rp0_neutral_value": float(algo_config["rp0_neutral_value"]),
        "rp0_source": "resolved_config",
        "rp0_reconstruction": "resolved_config_not_checkpoint_restored",
        "effort_profile_nm": float(config["v23_effort_profile_nm"]),
        "staged_reset_ratios": list(env_config["staged_reset_ratios"]),
    }


def _finite_checkpoint_value(value: Any, *, label: str, allow_none: bool) -> None:
    """Validate the finite leaf/container vocabulary emitted by ModelSaveCallback."""

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


def _validate_trainer_state(state: Any, *, num_envs: int) -> dict[str, Any]:
    if type(state).__name__ != "OnlineTrainerState" or not hasattr(state, "__dict__"):
        raise V23Error("terminal checkpoint state must be an OnlineTrainerState object")
    state_dict = vars(state)
    missing = [key for key in TRAINER_STATE_FIELDS if key not in state_dict]
    if missing:
        raise V23Error(f"terminal checkpoint trainer state is missing fields: {missing}")

    def require_int(key: str) -> None:
        value = state_dict[key]
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise V23Error(f"terminal checkpoint state field {key!r} must be an integer")

    def require_number(key: str) -> None:
        value = state_dict[key]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise V23Error(f"terminal checkpoint state field {key!r} must be numeric")
        if not math.isfinite(float(value)):
            raise V23Error(f"terminal checkpoint state field {key!r} must be finite")

    for key in (
        "global_step",
        "max_steps",
        "logging_steps",
        "eval_steps",
        "save_steps",
        "num_input_tokens_seen",
        "episode",
        "tot_timesteps",
        "eval_step",
        "eval_render_step",
    ):
        require_int(key)
    for key in ("epoch", "num_train_epochs", "total_flos", "tot_time"):
        require_number(key)
    for key in ("train_batch_size", "best_global_step"):
        value = state_dict[key]
        if value is not None and (isinstance(value, bool) or not isinstance(value, Integral)):
            raise V23Error(f"terminal checkpoint state field {key!r} must be an integer or null")
    if state_dict["best_metric"] is not None:
        require_number("best_metric")
    for key in ("best_model_checkpoint", "trial_name"):
        value = state_dict[key]
        if value is not None and not isinstance(value, str):
            raise V23Error(f"terminal checkpoint state field {key!r} must be a string or null")
    if state_dict["trial_params"] is not None and not isinstance(state_dict["trial_params"], Mapping):
        raise V23Error("terminal checkpoint state field 'trial_params' must be a mapping or null")
    for key in ("is_local_process_zero", "is_world_process_zero", "is_hyper_param_search"):
        if not isinstance(state_dict[key], bool):
            raise V23Error(f"terminal checkpoint state field {key!r} must be bool")
    if not isinstance(state_dict["stateful_callbacks"], Mapping):
        raise V23Error("terminal checkpoint state field 'stateful_callbacks' must be a mapping")
    for key in ("rewbuffer", "lenbuffer"):
        value = state_dict[key]
        if not isinstance(value, deque):
            raise V23Error(f"terminal checkpoint state field {key!r} must be a deque")
        for index, member in enumerate(value):
            if isinstance(member, bool) or not isinstance(member, Real):
                raise V23Error(f"terminal checkpoint state field {key!r}[{index}] must be real")
            if not math.isfinite(float(member)):
                raise V23Error(f"terminal checkpoint state field {key!r}[{index}] must be finite")
    try:
        import torch
    except ImportError as exc:
        raise V23Error("runtime checkpoint validation requires torch") from exc
    for key in ("cur_reward_sum", "cur_episode_length"):
        value = state_dict[key]
        if not isinstance(value, torch.Tensor) or value.ndim != 1 or value.shape[0] != num_envs:
            raise V23Error(
                f"terminal checkpoint state field {key!r} must be a {num_envs}-value tensor"
            )
        if not bool(torch.isfinite(value).all().item()):
            raise V23Error(f"terminal checkpoint state field {key!r} must be finite")
    if state_dict["global_step"] != NUM_BATCHES:
        raise V23Error(
            f"terminal checkpoint trainer global_step must be {NUM_BATCHES}; "
            f"got {state_dict['global_step']!r}"
        )
    return {
        "type": type(state).__name__,
        "global_step": int(state_dict["global_step"]),
        "required_fields": list(TRAINER_STATE_FIELDS),
    }


def _validate_checkpoint(checkpoint_path: Path) -> dict[str, Any]:
    if checkpoint_path.is_symlink() or not checkpoint_path.is_file():
        raise V23Error(f"missing terminal checkpoint: {checkpoint_path}")
    if checkpoint_path.name != "model_step_000010.pt":
        raise V23Error(
            "terminal checkpoint must be the exact step-10 artifact model_step_000010.pt"
        )
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
    if missing:
        raise V23Error(f"terminal checkpoint is missing ModelSaveCallback keys: {sorted(missing)}")
    if unsupported:
        raise V23Error(f"terminal checkpoint has unsupported top-level keys: {sorted(unsupported)}")
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
    state_facts = _validate_trainer_state(checkpoint["state"], num_envs=NUM_ENVS)
    args = checkpoint["args"]
    if type(args).__name__ != "PPOConfig" or not hasattr(args, "__dict__"):
        raise V23Error("terminal checkpoint args must be the documented PPOConfig metadata object")
    if "homie_state_dict" in checkpoint:
        homie = checkpoint["homie_state_dict"]
        if not isinstance(homie, Mapping) or not homie:
            raise V23Error("terminal checkpoint homie_state_dict must be a non-empty mapping")
        _finite_checkpoint_value(homie, label="checkpoint.homie_state_dict", allow_none=False)
    return {
        "path": str(checkpoint_path),
        "file_name": checkpoint_path.name,
        "global_step": state_facts["global_step"],
        "finite": True,
        "producer": "ModelSaveCallback",
        "mandatory_keys": sorted(CHECKPOINT_REQUIRED_KEYS),
        "optional_keys": sorted(CHECKPOINT_OPTIONAL_KEYS),
        "component_types": {
            "policy_state_dict": type(checkpoint["policy_state_dict"]).__name__,
            "value_state_dict": type(checkpoint["value_state_dict"]).__name__,
            "optimizer_state_dict": type(checkpoint["optimizer_state_dict"]).__name__,
            "lr_scheduler_state_dict": type(checkpoint["lr_scheduler_state_dict"]).__name__,
            "env_state_dict": type(checkpoint["env_state_dict"]).__name__,
        },
        "state": state_facts,
        "args_type": type(args).__name__,
        "homie_state_present": "homie_state_dict" in checkpoint,
    }


def _validate_run_output(type_id: str, paths: Mapping[str, Path]) -> dict[str, Any]:
    config_facts = _validate_resolved_config(paths["resolved_config"], type_id)
    checkpoint_facts = _validate_checkpoint(paths["checkpoint"])
    device_facts = _validate_device_stdout(paths["stdout"], type_id)
    return {
        "resolved_config": config_facts,
        "checkpoint": checkpoint_facts,
        "device": device_facts,
        "global_step": NUM_BATCHES,
    }


def _expected_rp0(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "enabled": spec["rp0_enabled"],
        "mask_indices": list(RP0_INDICES),
        "neutral_value": RP0_NEUTRAL,
        "source": "resolved_config",
        "reconstruction": "resolved_config_not_checkpoint_restored",
        "checkpoint_restored": False,
    }


def _expected_common_reward() -> dict[str, Any]:
    return {
        "state": "P0_6_REWARD_REGISTRY_SELECTED",
        "effort_profile_nm": EFFORT_NM,
        "source": "resolved_config",
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
    """Independently validate a candidate or persisted runtime-pass record."""

    if candidate_record is None:
        record = _load_record(record_path)
    else:
        record = dict(candidate_record)
    spec = TYPE_MATRIX[type_id]
    if record.get("status") != "P0_9_D0_TYPE_SMOKE_RUNTIME_VERIFIED":
        raise V23Error(f"{type_id} record does not claim the runtime-pass status")
    expected = {
        "schema": TYPE_RECORD_SCHEMA,
        "task_id": TASK_ID,
        "revision": REVISION,
        "type": type_id,
        "cell": spec["cell"],
        "physical_gpu": spec["gpu"],
        "logical_device": f"cuda:{spec['gpu']}",
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
        raise V23Error(f"{type_id} PASS record disagrees on exact fields: {mismatch}")
    if record.get("rp0") != _expected_rp0(spec):
        raise V23Error(f"{type_id} PASS record RP0 reconstruction is not exact")
    if record.get("common_reward") != _expected_common_reward():
        raise V23Error(f"{type_id} PASS record common reward evidence is not exact")
    command, environment = _command_for_type(type_id, run_root=expected_run_root)
    if record.get("command") != command or record.get("command_shell") != shlex.join(command):
        raise V23Error(f"{type_id} PASS record launcher command identity is not exact")
    if record.get("environment") != environment:
        raise V23Error(f"{type_id} PASS record launcher environment identity is not exact")
    evidence = record.get("evidence")
    if not isinstance(evidence, Mapping):
        raise V23Error(f"{type_id} PASS record is missing evidence")
    paths = _type_paths(
        type_id,
        run_root=expected_run_root,
        launcher_root=expected_launcher_type_root.parent,
    )
    paths["record"] = expected_record_path.resolve()
    runtime_evidence = _validate_run_output(type_id, paths)
    if dict(evidence) != runtime_evidence:
        raise V23Error(f"{type_id} PASS record evidence does not match revalidated artifacts")
    checkpoint_evidence = _mapping(evidence.get("checkpoint"), label=f"{type_id} checkpoint evidence")
    if (
        checkpoint_evidence.get("path") != expected["terminal_checkpoint_path"]
        or checkpoint_evidence.get("file_name") != "model_step_000010.pt"
        or checkpoint_evidence.get("global_step") != NUM_BATCHES
        or checkpoint_evidence.get("finite") is not True
    ):
        raise V23Error(f"{type_id} PASS record checkpoint evidence is not exact")
    return record


def _write_new_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise V23Error(f"refusing to overwrite existing launcher artifact: {path}")
    path.write_text(text, encoding="utf-8")


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
        "status": "P0_9_D0_TYPE_SMOKE_FAILED",
        "task_id": TASK_ID,
        "revision": REVISION,
        "type": type_id,
        "cell": spec["cell"],
        "physical_gpu": spec["gpu"],
        "logical_device": f"cuda:{spec['gpu']}",
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
        "rp0": {
            "enabled": spec["rp0_enabled"],
            "mask_indices": list(RP0_INDICES),
            "neutral_value": RP0_NEUTRAL,
            "source": "resolved_config",
            "reconstruction": "resolved_config_not_checkpoint_restored",
            "checkpoint_restored": False,
        },
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


def run_type(type_id: str, *, gpu: int, run_root: Path | None, launcher_root: Path | None, record_path: Path | None) -> tuple[dict[str, Any], int]:
    type_id = _type_id(type_id)
    spec = TYPE_MATRIX[type_id]
    validate_r78_admission()
    if isinstance(gpu, bool) or gpu != spec["gpu"]:
        raise V23Error(f"{type_id} must run on its assigned physical GPU{spec['gpu']}")
    paths = _type_paths(type_id, run_root=run_root, launcher_root=launcher_root)
    if record_path is not None:
        paths["record"] = record_path.resolve()
    if paths["record"].parent != paths["run_root"]:
        raise V23Error("per-type record must live directly under its type run root")
    for root, label in ((paths["run_root"], "type run root"), (paths["launcher_type_root"], "launcher type root")):
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
        child_env["CUDA_DEVICE_ORDER"] = environment["CUDA_DEVICE_ORDER"]
        child_env["CUDA_VISIBLE_DEVICES"] = environment["CUDA_VISIBLE_DEVICES"]
        child_env["ACCELERATE_TORCH_DEVICE"] = environment["ACCELERATE_TORCH_DEVICE"]
        child_env["WANDB_MODE"] = environment["WANDB_MODE"]
        child_env["PYTHONPATH"] = environment["PYTHONPATH"]
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
        error = f"subprocess launch failed: {exc}"
        _write_new_text(paths["returncode"], "LAUNCH_ERROR\n")
        record = _write_failure_record(
            type_id=type_id,
            paths=paths,
            command=command,
            environment=environment,
            returncode=returncode,
            error=error,
        )
        return record, 2
    _write_new_text(paths["returncode"], f"{returncode}\n")
    if returncode != 0:
        record = _write_failure_record(
            type_id=type_id,
            paths=paths,
            command=command,
            environment=environment,
            returncode=returncode,
            error=f"training subprocess returned nonzero code {returncode}",
        )
        return record, 2
    try:
        evidence = _validate_run_output(type_id, paths)
    except V23Error as exc:
        record = _write_failure_record(
            type_id=type_id,
            paths=paths,
            command=command,
            environment=environment,
            returncode=returncode,
            error=str(exc),
        )
        return record, 2
    spec = TYPE_MATRIX[type_id]
    record = {
        "schema": TYPE_RECORD_SCHEMA,
        "status": "P0_9_D0_TYPE_SMOKE_RUNTIME_VERIFIED",
        "task_id": TASK_ID,
        "revision": REVISION,
        "type": type_id,
        "cell": spec["cell"],
        "physical_gpu": spec["gpu"],
        "logical_device": f"cuda:{spec['gpu']}",
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
        "rp0": {
            "enabled": spec["rp0_enabled"],
            "mask_indices": list(RP0_INDICES),
            "neutral_value": RP0_NEUTRAL,
            "source": "resolved_config",
            "reconstruction": "resolved_config_not_checkpoint_restored",
            "checkpoint_restored": False,
        },
        "common_reward": {
            "state": "P0_6_REWARD_REGISTRY_SELECTED",
            "effort_profile_nm": EFFORT_NM,
            "source": "resolved_config",
        },
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
        failed_record = _write_failure_record(
            type_id=type_id,
            paths=paths,
            command=command,
            environment=environment,
            returncode=returncode,
            error=f"pre-write PASS validation failed: {exc}",
        )
        return failed_record, 2
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


def _load_record(path: Path) -> dict[str, Any]:
    try:
        return read_json(path)
    except V23Error as exc:
        raise V23Error(f"cannot read explicit type record {path}: {exc}") from exc


def _reduce_records(record_paths: Sequence[Path], *, output: Path) -> tuple[dict[str, Any], int]:
    admission = validate_r78_admission()
    if len(record_paths) != 4:
        raise V23Error("REDUCE requires exactly four explicit per-type record paths")
    if len({path.resolve() for path in record_paths}) != 4:
        raise V23Error("REDUCE requires four unique explicit per-type record paths")
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
            record = _load_record(path)
        except V23Error:
            failed.append(str(path))
            continue
        type_id_raw = record.get("type")
        if not isinstance(type_id_raw, str) or type_id_raw.upper() not in TYPE_MATRIX:
            failed.append(str(path))
            continue
        type_id = _type_id(type_id_raw)
        if type_id in records:
            raise V23Error(f"REDUCE contains duplicate type record {type_id}")
        records[type_id] = record
        record_paths_by_type[type_id] = path
        if record.get("status") == "P0_9_D0_TYPE_SMOKE_RUNTIME_VERIFIED":
            try:
                _validate_claimed_pass_record(
                    path,
                    type_id,
                    expected_run_root=_canonical_run_root(type_id),
                    expected_launcher_type_root=_canonical_launcher_type_root(type_id),
                    expected_record_path=path,
                )
            except V23Error:
                failed.append(type_id)
            else:
                passed.append(type_id)
        else:
            failed.append(type_id)

    for type_id in TYPE_IDS:
        if type_id not in records and type_id not in missing:
            missing.append(type_id)
    output_roots = [record.get("run_root") for record in records.values() if record.get("run_root")]
    output_checkpoints = [
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
        len(output_roots) == len(set(output_roots))
        and len(output_checkpoints) == len(set(output_checkpoints))
        and len(launcher_roots) == len(set(launcher_roots))
    )
    if not disjoint_outputs:
        failed.extend(type_id for type_id in records if type_id not in failed)
        passed = [type_id for type_id in passed if type_id not in failed]
    passed = sorted(set(passed), key=TYPE_IDS.index)
    failed = sorted(set(failed), key=TYPE_IDS.index)
    missing = sorted(set(missing), key=lambda value: TYPE_IDS.index(value) if value in TYPE_IDS else len(TYPE_IDS))
    all_pass = passed == list(TYPE_IDS) and not failed and not missing and disjoint_outputs
    status = PASS_STATUS if all_pass else INCOMPLETE_STATUS
    aggregate = {
        "schema": AGGREGATE_SCHEMA,
        "status": status,
        "task_id": TASK_ID,
        "revision": REVISION,
        "p09_status": "COMPLETE" if all_pass else "INCOMPLETE",
        "p010_d0_full_pilot_admission": all_pass,
        "formal_admission": False,
        "d1_admission": False,
        "release_receipt": False,
        "seed": SEED,
        "num_envs": NUM_ENVS,
        "num_processes": 1,
        "num_total_batches": NUM_BATCHES,
        "save_frequency": SAVE_FREQUENCY,
        "admission": admission,
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
        "excluded_claims": [
            "NO_D1_TRAINING_OR_MIXTURE_CLAIM",
            "NO_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
        ],
    }
    write_json(output, aggregate)
    return aggregate, (0 if all_pass else 2)


def _flatten_records(groups: Sequence[Sequence[str]] | None, direct: Sequence[str] | None) -> list[Path]:
    values: list[str] = []
    for group in groups or ():
        values.extend(group)
    values.extend(direct or ())
    return [_record_path(value) if (Path(value).exists() or "=" in value) else _absolute_path(value, label="type record") for value in values]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "RUN_TYPE", "REDUCE"), required=True)
    parser.add_argument("--type", dest="type_id", default=None)
    parser.add_argument("--gpu", type=int, default=None)
    parser.add_argument("--run-root", type=Path, default=None)
    parser.add_argument("--launcher-root", type=Path, default=None)
    parser.add_argument("--record", dest="record_groups", action="append", nargs="+")
    parser.add_argument("--records", dest="record_list", nargs=4)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.mode == "PLAN":
        if args.type_id is not None or args.gpu is not None:
            raise V23Error("PLAN emits all four types and does not accept --type/--gpu")
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
    if len(record_paths) != 4:
        raise V23Error("REDUCE requires exactly four explicit per-type record paths")
    output = (
        CANONICAL_AGGREGATE_PATH
        if args.output is None
        else _absolute_path(args.output, label="aggregate output")
    )
    aggregate, exit_code = _reduce_records(record_paths, output=output)
    print(json.dumps(aggregate, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        print(f"V23 P0.9 D0 TYPE SMOKE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
