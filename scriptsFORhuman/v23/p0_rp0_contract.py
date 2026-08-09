"""Emit the static v23 RP0 contract after the exact RP0 test passes.

This producer intentionally has no runtime attestation or training closure.
The common v23 configuration remains a non-launchable FULL-shaped skeleton;
the emitted record describes the future RP0 overlay without writing YAML.
Only a trainer-side producer can establish resume evidence after W3.
"""

from __future__ import annotations

import argparse
import ast
from collections import deque
import json
import math
import pickle
import subprocess
import sys
from pathlib import Path
from numbers import Real
from typing import Any, Mapping, Sequence

import torch

try:
    from ._v23_common import V23Error, artifact_payload, emit_payload, read_yaml, require_file
except ImportError:  # direct ``python scriptsFORhuman/v23/...py`` invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        V23Error,
        artifact_payload,
        emit_payload,
        read_yaml,
        require_file,
    )


SCHEMA = "a2_piper_v23_rp0_contract_v1"
STATIC_STATUS = "STATIC_CONTRACT_VERIFIED"
RUNTIME_STATUS = "PENDING"
RUNTIME_VERIFIED_STATUS = "RUNTIME_VERIFIED"
RUNTIME_RECEIPT_SCHEMA = "a2_piper_v23_p07_rp0_runtime_receipt_v1"
EFFECTIVE_CONFIG_SCHEMA = "a2_piper_v23_p07_effective_config_v1"
RUNTIME_RECEIPT_FILENAME = "a2_v23_p07_runtime_receipt.json"
EFFECTIVE_CONFIG_FILENAME = "a2_v23_p07_effective_config.json"
RP0_INDICES = [3, 4]
RP0_NEUTRAL = 0.0
RUNTIME_ENV_COUNT = 64
FULL_REQUIRED_TRAINER_STATE_FIELDS = [
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
]

ACTOR_SOURCE = "gr00t/rl/trl/modules/actor_critic_modules.py"
RECURRENT_ACTOR_SOURCE = "gr00t/rl/trl/modules/actor_critic_modules_recurrent.py"
TRAINER_SOURCE = "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"
A2_LAYOUT_SOURCE = "gr00t/rl/envs/base_task/a2_base.py"
COMMON_CONFIG = "gr00t/rl/config/ablation/wbmanip/base_v23_common.yaml"
RUNTIME_CONFIG = "gr00t/rl/config/ablation/wbmanip/base_v23_p07_rp0_runtime.yaml"
TEST_SOURCE = "gr00t/rl/tests/test_a2_v23_rp0_contract.py"


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V23Error(f"{name} must be an object")
    return value


def _indices(value: Any, *, name: str) -> list[int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise V23Error(f"{name} must be a sequence of integer action indices")
    values = list(value)
    if any(isinstance(item, bool) or not isinstance(item, int) for item in values):
        raise V23Error(f"{name} must contain only integer action indices")
    return values


def _absolute_output(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise V23Error(f"--output must be an absolute path: {path}")
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise V23Error(f"--output must name a writable file or a new path: {path}")
    return path


def _class_constants(tree: ast.AST) -> dict[str, int]:
    """Read the declared A2 action dimensions from the parsed class AST."""

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "A2Base":
            continue
        constants: dict[str, int] = {}
        for child in node.body:
            if not isinstance(child, ast.Assign) or len(child.targets) != 1:
                continue
            target = child.targets[0]
            if not isinstance(target, ast.Name) or not target.id.startswith("A2_"):
                continue
            try:
                value = ast.literal_eval(child.value)
            except (ValueError, TypeError):
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            constants[target.id] = value
        return constants
    raise V23Error("A2Base class is missing from the live A2 layout source")


def _posture_slice_line(tree: ast.AST) -> int:
    """Locate the exact raw action slice ``[:, 3:5]`` in the parsed source."""

    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        if not isinstance(node.value, ast.Name) or node.value.id != "raw_base_action":
            continue
        if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2:
            continue
        posture = node.slice.elts[1]
        if not isinstance(posture, ast.Slice):
            continue
        try:
            lower = ast.literal_eval(posture.lower)
            upper = ast.literal_eval(posture.upper)
        except (ValueError, TypeError):
            continue
        if lower == 3 and upper == 5:
            return node.lineno
    raise V23Error("live A2 layout source does not expose the raw posture slice [3:5]")


def _command_order_line(tree: ast.AST) -> int:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "[x,y,yaw,pitch,roll]" in node.value
        ):
            return node.lineno
    raise V23Error("live A2 layout source does not document the raw command order")


def _parse_layout_source(source: str) -> ast.AST:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise V23Error(f"A2 layout source is not valid Python: {A2_LAYOUT_SOURCE}") from exc
    return tree


def _layout_facts() -> dict[str, Any]:
    path = require_file(A2_LAYOUT_SOURCE, label="RP0 A2 layout source")
    source = path.read_text(encoding="utf-8")
    tree = _parse_layout_source(source)
    constants = _class_constants(tree)
    expected = {
        "A2_BASE_COMMAND_ACTION_DIM": 5,
        "A2_ARM_ACTION_DIM": 6,
        "A2_GRIPPER_PRIMITIVE_ACTION_DIM": 1,
    }
    if any(constants.get(name) != value for name, value in expected.items()):
        raise V23Error(
            "live A2 action constants do not contain the expected base/arm/gripper dimensions"
        )
    return {
        "source": A2_LAYOUT_SOURCE,
        "class": "A2Base",
        "action_dimensions": {
            "base_command": constants["A2_BASE_COMMAND_ACTION_DIM"],
            "arm": constants["A2_ARM_ACTION_DIM"],
            "gripper_primitive": constants["A2_GRIPPER_PRIMITIVE_ACTION_DIM"],
            "total": sum(expected.values()),
        },
        "raw_base_command_order": ["x", "y", "yaw", "pitch", "roll"],
        "raw_posture_indices": {"3": "pitch", "4": "roll"},
        "raw_posture_slice": [3, 5],
        "command_order_source_line": _command_order_line(tree),
        "posture_slice_source_line": _posture_slice_line(tree),
        "neutral_raw_value": RP0_NEUTRAL,
    }


def _config_facts() -> dict[str, Any]:
    config = read_yaml(require_file(COMMON_CONFIG, label="RP0 v23 common config"))
    algo = _mapping(config.get("algo"), name="base_v23_common.algo")
    algo_config = _mapping(algo.get("config"), name="base_v23_common.algo.config")
    enabled = algo_config.get("rp0_enabled")
    if enabled is not False:
        raise V23Error(
            "base_v23_common.algo.config.rp0_enabled must remain false in the FULL-shaped skeleton"
        )
    indices = _indices(algo_config.get("rp0_mask_indices"), name="base_v23_common.algo.config.rp0_mask_indices")
    if indices != RP0_INDICES:
        raise V23Error("base_v23_common.algo.config.rp0_mask_indices must equal [3,4]")
    neutral = algo_config.get("rp0_neutral_value")
    if isinstance(neutral, bool) or not isinstance(neutral, (int, float)) or float(neutral) != RP0_NEUTRAL:
        raise V23Error("base_v23_common.algo.config.rp0_neutral_value must equal 0.0")
    env = _mapping(config.get("env"), name="base_v23_common.env")
    env_config = _mapping(env.get("config"), name="base_v23_common.env.config")
    if env_config.get("a2_v23_rp0_enabled") is not False:
        raise V23Error("base_v23_common.env.config.a2_v23_rp0_enabled must remain false")
    if _indices(env_config.get("a2_v23_rp0_mask_indices"), name="base_v23_common.env.config.a2_v23_rp0_mask_indices") != RP0_INDICES:
        raise V23Error("base_v23_common.env.config.a2_v23_rp0_mask_indices must equal [3,4]")
    env_neutral = env_config.get("a2_v23_rp0_neutral_value")
    if isinstance(env_neutral, bool) or not isinstance(env_neutral, (int, float)) or float(env_neutral) != RP0_NEUTRAL:
        raise V23Error("base_v23_common.env.config.a2_v23_rp0_neutral_value must equal 0.0")
    return {
        "source": COMMON_CONFIG,
        "skeleton": {
            "algo_config": {
                "rp0_enabled": False,
                "rp0_mask_indices": RP0_INDICES,
                "rp0_neutral_value": RP0_NEUTRAL,
            },
            "env_config": {
                "a2_v23_rp0_enabled": False,
                "a2_v23_rp0_mask_indices": RP0_INDICES,
                "a2_v23_rp0_neutral_value": RP0_NEUTRAL,
            },
        },
        "future_rp0_overlay": {
            "rp0_enabled": True,
            "rp0_mask_indices": RP0_INDICES,
            "rp0_neutral_value": RP0_NEUTRAL,
            "written": False,
        },
    }


def _pytest_summary(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "no pytest output"
    return lines[-1][:240]


def _run_exact_rp0_test() -> dict[str, Any]:
    test_path = require_file(TEST_SOURCE, label="RP0 contract test")
    command = [sys.executable, "-m", "pytest", "-q", TEST_SOURCE]
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    result = {
        "command": command,
        "exit_code": completed.returncode,
        "summary": _pytest_summary(completed.stdout),
    }
    if completed.returncode != 0:
        raise V23Error(
            "exact RP0 test failed with exit code "
            f"{completed.returncode}: {result['summary']}"
        )
    return result


def build_static_record() -> dict[str, Any]:
    test_result = _run_exact_rp0_test()
    layout = _layout_facts()
    config = _config_facts()
    require_file(RUNTIME_CONFIG, label="P0.7 contract-only runtime config")
    return artifact_payload(
        "rp0_contract",
        mode="STATIC",
        status=STATIC_STATUS,
        contract={
            "raw_action_layout": layout,
            "distribution_semantics": {
                "authority": TEST_SOURCE,
                "tested": True,
                "mean_sample_logprob_entropy_kl_mask": True,
                "post_sample_only_clamp": False,
                "mask_attributes_persistent": False,
                "mask_reconstructed_from_config": True,
            },
            "configuration": config,
            "contract_only_runtime_config": RUNTIME_CONFIG,
            "runtime_resume_status": RUNTIME_STATUS,
            "required_future_trainer_evidence": [
                "trainer-side initial run with 64 environments and 10 completed batches",
                "checkpoint and resolved config captured by the trainer-side producer",
                "full resume from step 10 through step 11 after the RP0 to FULL transition",
                "trainer-observed masked statistics and strict restore evidence",
            ],
        },
        source_paths=[
            ACTOR_SOURCE,
            RECURRENT_ACTOR_SOURCE,
            TRAINER_SOURCE,
            A2_LAYOUT_SOURCE,
            COMMON_CONFIG,
            RUNTIME_CONFIG,
            TEST_SOURCE,
        ],
        pytest=test_result,
    )


def _runtime_receipt_path(raw: str, *, label: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise V23Error(f"{label} must be an absolute path: {path}")
    if path.is_symlink() or not path.is_file():
        raise V23Error(f"{label} is not a regular file: {path}")
    return path


def _runtime_receipt_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V23Error(f"{label} must be an object")
    return value


def _runtime_receipt_bool(value: Any, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise V23Error(f"{label} must be bool; got {value!r}")
    return value


def _runtime_receipt_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise V23Error(f"{label} must be an integer; got {value!r}")
    return value


def _runtime_receipt_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V23Error(f"{label} must be numeric; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise V23Error(f"{label} must be finite; got {value!r}")
    return result


def _runtime_receipt_regular_file(raw: Any, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise V23Error(f"{label} must be a non-empty absolute path")
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise V23Error(f"{label} must name an existing regular absolute file: {path}")
    return path.resolve()


def _validate_restore_facts(
    receipt: Mapping[str, Any], *, mode: str, restored_start: int
) -> Mapping[str, Any]:
    facts = _runtime_receipt_mapping(receipt.get("restore_facts"), label="restore_facts")
    if facts.get("load_mode") != ("policy_only" if mode == "RP0" else "full"):
        raise V23Error("restore_facts.load_mode disagrees with the receipt mode")
    required = ("actor", "value", "optimizer", "scheduler", "trainer")
    for key in required:
        child = _runtime_receipt_mapping(facts.get(key), label=f"restore_facts.{key}")
        _runtime_receipt_bool(child.get("loaded"), label=f"restore_facts.{key}.loaded")
    actor = facts["actor"]
    if not actor.get("loaded") or actor.get("strict") is not True:
        raise V23Error("runtime receipt actor restore is not a strict successful load")
    if mode == "RP0":
        for key in ("value", "optimizer", "scheduler", "trainer"):
            if facts[key].get("loaded"):
                raise V23Error(
                    f"policy-only runtime receipt incorrectly claims {key} restoration"
                )
    else:
        for key in ("value", "optimizer", "scheduler", "trainer"):
            if not facts[key].get("loaded"):
                raise V23Error(f"full runtime receipt is missing strict {key} restoration")
        value = facts["value"]
        if value.get("strict") is not True:
            raise V23Error("full runtime receipt value restoration is not strict")
        trainer_step = facts["trainer"].get("global_step")
        if trainer_step != restored_start:
            raise V23Error(
                "full runtime receipt trainer restore step disagrees with restored_start: "
                f"{trainer_step!r} != {restored_start!r}"
            )
    return facts


def _validate_runtime_receipt(
    raw: str,
    *,
    expected_mode: str,
    expected_start: int,
    expected_end: int,
    expected_batches: int,
    expected_input_name: str,
    expected_output_name: str,
) -> tuple[dict[str, Any], Path]:
    path = _runtime_receipt_path(raw, label=f"{expected_mode} runtime receipt")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V23Error(f"invalid {expected_mode} runtime receipt JSON: {path}") from exc
    receipt = dict(_runtime_receipt_mapping(payload, label=f"{expected_mode} runtime receipt"))
    if receipt.get("schema") != RUNTIME_RECEIPT_SCHEMA:
        raise V23Error(f"{expected_mode} runtime receipt schema is not {RUNTIME_RECEIPT_SCHEMA}")
    if receipt.get("status") != "RUNTIME_RECEIPT_VERIFIED":
        raise V23Error(f"{expected_mode} runtime receipt is not trainer-verified")
    if receipt.get("mode") != expected_mode:
        raise V23Error(
            f"runtime receipt mode mismatch: got {receipt.get('mode')!r}, expected {expected_mode!r}"
        )

    contract = _runtime_receipt_mapping(receipt.get("contract"), label="contract")
    if contract.get("env_count") != RUNTIME_ENV_COUNT:
        raise V23Error("runtime receipt environment count must be exactly 64")
    if _runtime_receipt_bool(contract.get("rp0_enabled"), label="contract.rp0_enabled") != (
        expected_mode == "RP0"
    ):
        raise V23Error("runtime receipt RP0 enable flag disagrees with its mode")
    indices = contract.get("mask_indices")
    if indices != RP0_INDICES:
        raise V23Error(f"runtime receipt mask indices must equal {RP0_INDICES}; got {indices!r}")
    if _runtime_receipt_number(contract.get("neutral_value"), label="contract.neutral_value") != RP0_NEUTRAL:
        raise V23Error("runtime receipt neutral value must equal 0.0")
    mask_vector = contract.get("mask_vector")
    if not isinstance(mask_vector, list) or len(mask_vector) != 12 or any(
        not isinstance(item, bool) for item in mask_vector
    ):
        raise V23Error("runtime receipt mask_vector must contain exactly twelve bool values")
    expected_masked = expected_mode == "RP0"
    if mask_vector[3] != (not expected_masked) or mask_vector[4] != (not expected_masked):
        raise V23Error("runtime receipt mask_vector does not encode raw posture indices [3,4]")

    checkpoint = _runtime_receipt_mapping(receipt.get("checkpoint"), label="checkpoint")
    load_mode = "policy_only" if expected_mode == "RP0" else "full"
    if checkpoint.get("load_mode") != load_mode:
        raise V23Error("runtime receipt checkpoint load mode disagrees with its mode")
    if _runtime_receipt_bool(checkpoint.get("input_exists"), label="checkpoint.input_exists") is not True:
        raise V23Error("runtime receipt input checkpoint was not verified as present")
    if _runtime_receipt_bool(checkpoint.get("output_exists"), label="checkpoint.output_exists") is not True:
        raise V23Error("runtime receipt output checkpoint was not verified as present")
    input_path = _runtime_receipt_regular_file(checkpoint.get("input_path"), label="checkpoint.input_path")
    output_path = _runtime_receipt_regular_file(checkpoint.get("output_path"), label="checkpoint.output_path")
    if input_path.name != expected_input_name:
        raise V23Error(
            f"runtime receipt input checkpoint must be {expected_input_name}; got {input_path.name}"
        )
    if output_path.name != expected_output_name:
        raise V23Error(
            f"runtime receipt output checkpoint must be {expected_output_name}; got {output_path.name}"
        )

    steps = _runtime_receipt_mapping(receipt.get("global_step"), label="global_step")
    restored_start = _runtime_receipt_int(steps.get("restored_start"), label="global_step.restored_start")
    invocation_start = _runtime_receipt_int(steps.get("invocation_start"), label="global_step.invocation_start")
    post_batch_end = _runtime_receipt_int(steps.get("post_batch_end"), label="global_step.post_batch_end")
    if (restored_start, invocation_start, post_batch_end) != (expected_start, expected_start, expected_end):
        raise V23Error(
            "runtime receipt global-step chain must be "
            f"{expected_start}->{expected_end}; got {restored_start}->{invocation_start}->{post_batch_end}"
        )

    invocation = _runtime_receipt_mapping(receipt.get("invocation"), label="invocation")
    if _runtime_receipt_int(invocation.get("num_total_batches"), label="invocation.num_total_batches") != expected_batches:
        raise V23Error("runtime receipt num_total_batches is not invocation-local and exact")
    expected_save_frequency = expected_batches
    if _runtime_receipt_int(invocation.get("save_frequency"), label="invocation.save_frequency") != expected_save_frequency:
        raise V23Error("runtime receipt save_frequency does not match the contract invocation")
    if _runtime_receipt_bool(invocation.get("terminal_batch_completed"), label="invocation.terminal_batch_completed") is not True:
        raise V23Error("runtime receipt terminal batch was not completed")
    if _runtime_receipt_bool(invocation.get("terminal_save_verified"), label="invocation.terminal_save_verified") is not True:
        raise V23Error("runtime receipt terminal checkpoint save was not verified")

    stats = _runtime_receipt_mapping(receipt.get("masked_stats"), label="masked_stats")
    for field in ("actions", "action_mean"):
        row = _runtime_receipt_mapping(stats.get(field), label=f"masked_stats.{field}")
        values = row.get("max_abs")
        if not isinstance(values, list) or len(values) != 2:
            raise V23Error(f"masked_stats.{field}.max_abs must contain exactly two values")
        values = [_runtime_receipt_number(value, label=f"masked_stats.{field}.max_abs[{i}]") for i, value in enumerate(values)]
        if _runtime_receipt_int(row.get("sample_count"), label=f"masked_stats.{field}.sample_count") <= 0:
            raise V23Error(f"masked_stats.{field} has no trainer-observed samples")
        if expected_masked and any(value != 0.0 for value in values):
            raise V23Error(f"RP0 masked {field} statistics must be exactly zero; got {values!r}")

    if _runtime_receipt_bool(receipt.get("environment_continuity"), label="environment_continuity") is not False:
        raise V23Error("runtime receipt must state environment_continuity=false after reset")
    resolved_config = _runtime_receipt_regular_file(
        receipt.get("resolved_config_path"), label="resolved_config_path"
    )
    _validate_restore_facts(receipt, mode=expected_mode, restored_start=expected_start)
    return receipt, output_path


def _pending_runtime_record(*, missing_receipts: Sequence[str]) -> dict[str, Any]:
    record = build_static_record()
    record["contract"]["runtime_resume_status"] = RUNTIME_STATUS
    record["runtime_receipts"] = {
        "schema": RUNTIME_RECEIPT_SCHEMA,
        "status": RUNTIME_STATUS,
        "missing_receipts": list(missing_receipts),
    }
    return record


def _runtime_run_dir(raw: str, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise V23Error(f"{label} must be a non-empty absolute run directory")
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise V23Error(f"{label} must be an existing regular absolute directory: {path}")
    return path.resolve()


def _canonical_runtime_paths(run_dir: Path) -> dict[str, Path]:
    return {
        "run_dir": run_dir,
        "receipt": run_dir / RUNTIME_RECEIPT_FILENAME,
        "effective_config": run_dir / EFFECTIVE_CONFIG_FILENAME,
        "step10": run_dir / "model_step_000010.pt",
        "step11": run_dir / "model_step_000011.pt",
    }


def _read_runtime_object(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise V23Error(f"{label} is not a regular canonical file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V23Error(f"{label} is not valid JSON: {path}") from exc
    return dict(_runtime_receipt_mapping(value, label=label))


def _validate_effective_config(
    run_dir: Path, *, expected_mode: str, expected_start: int, expected_end: int, expected_batches: int
) -> tuple[dict[str, Any], Path]:
    paths = _canonical_runtime_paths(run_dir)
    config = _read_runtime_object(paths["effective_config"], label="effective config")
    if config.get("schema") != EFFECTIVE_CONFIG_SCHEMA:
        raise V23Error(f"effective config schema is not {EFFECTIVE_CONFIG_SCHEMA}")
    if config.get("status") != "EFFECTIVE_CONFIG_VERIFIED":
        raise V23Error("effective config is not trainer-verified")
    if config.get("canonical_run_dir") != str(run_dir):
        raise V23Error("effective config canonical_run_dir does not match its run directory")
    if config.get("physical_gpu_count") != 1 or config.get("world_size") != 1:
        raise V23Error("effective config is not the canonical one-GPU/one-rank topology")
    if config.get("mode") != expected_mode:
        raise V23Error("effective config mode disagrees with the expected invocation")
    if _runtime_receipt_bool(config.get("rp0_enabled"), label="effective_config.rp0_enabled") != (
        expected_mode == "RP0"
    ):
        raise V23Error("effective config RP0 flag disagrees with its mode")
    if config.get("mask_indices") != RP0_INDICES:
        raise V23Error("effective config mask indices must equal [3,4]")
    if _runtime_receipt_number(config.get("neutral_value"), label="effective_config.neutral_value") != RP0_NEUTRAL:
        raise V23Error("effective config neutral value must equal 0.0")
    if config.get("env_count") != RUNTIME_ENV_COUNT:
        raise V23Error("effective config environment count must equal 64")
    if config.get("invocation_batches") != expected_batches or config.get("save_frequency") != expected_batches:
        raise V23Error("effective config invocation batches/save frequency are not exact")
    expected_load_mode = "policy_only" if expected_mode == "RP0" else "full"
    if config.get("checkpoint_load_mode") != expected_load_mode:
        raise V23Error("effective config checkpoint load mode disagrees with its mode")
    if config.get("auto_load_latest") is not False:
        raise V23Error("effective config auto_load_latest must be false")
    if _runtime_receipt_number(config.get("effort_profile_nm"), label="effective_config.effort_profile_nm") != 100.0:
        raise V23Error("effective config contract-only effort must equal 100.0 Nm")
    if config.get("effort_profile_source") != "P0_CONTRACT_ONLY_NOT_V23_FREEZE":
        raise V23Error("effective config effort provenance is not contract-only")
    if config.get("expected_start_global_step") != expected_start or config.get("expected_end_global_step") != expected_end:
        raise V23Error("effective config expected global-step bounds are not exact")
    expected_output = paths["step10"] if expected_end == 10 else paths["step11"]
    if config.get("expected_output_checkpoint_path") != str(expected_output):
        raise V23Error("effective config expected output checkpoint is not its canonical sibling")
    expected_initial_step10 = config.get("expected_initial_step10_checkpoint_path")
    if expected_mode == "FULL":
        expected_initial_step10 = _runtime_receipt_regular_file(
            expected_initial_step10,
            label="effective_config.expected_initial_step10_checkpoint_path",
        )
        if expected_initial_step10.name != "model_step_000010.pt":
            raise V23Error(
                "FULL effective config expected_initial_step10_checkpoint_path must name model_step_000010.pt"
            )
    elif expected_initial_step10 is not None:
        raise V23Error(
            "RP0 effective config must leave FULL-only expected_initial_step10_checkpoint_path unset"
        )
    input_path = _runtime_receipt_regular_file(
        config.get("input_checkpoint_path"), label="effective_config.input_checkpoint_path"
    )
    return config, input_path


def _inspect_runtime_checkpoint(path: Path, *, expected_step: int, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise V23Error(f"{label} checkpoint is not a regular file: {path}")
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    except (OSError, RuntimeError, ValueError, EOFError, pickle.UnpicklingError) as exc:
        raise V23Error(f"{label} checkpoint cannot be loaded with torch.load: {path}") from exc
    if not isinstance(checkpoint, Mapping):
        raise V23Error(f"{label} checkpoint is not a mapping")
    actor_keys = [key for key in ("actor_model_state_dict", "policy_state_dict") if key in checkpoint]
    required = ("value_state_dict", "optimizer_state_dict", "lr_scheduler_state_dict", "state")
    if len(actor_keys) != 1 or any(key not in checkpoint for key in required):
        raise V23Error(f"{label} checkpoint is missing required actor/value/optimizer/scheduler/state keys")
    if checkpoint[actor_keys[0]] is None:
        raise V23Error(f"{label} checkpoint contains a null actor state component")
    if any(checkpoint[key] is None for key in required if key != "state"):
        raise V23Error(f"{label} checkpoint contains a null required restore component")
    state = checkpoint["state"]
    if not hasattr(state, "__dict__"):
        raise V23Error(f"{label} checkpoint state is not a trainer state object")
    state_fields = vars(state)
    missing_state_fields = [
        key for key in FULL_REQUIRED_TRAINER_STATE_FIELDS if key not in state_fields
    ]
    if missing_state_fields:
        raise V23Error(
            f"{label} checkpoint trainer state is missing required fields: {missing_state_fields}"
        )
    for field in ("rewbuffer", "lenbuffer"):
        buffer = state_fields[field]
        if not isinstance(buffer, deque):
            raise V23Error(f"{label} checkpoint trainer state field {field} is not a deque")
        for index, member in enumerate(buffer):
            if isinstance(member, bool) or not isinstance(member, Real):
                raise V23Error(
                    f"{label} checkpoint trainer state field {field}[{index}] is not a real numeric value"
                )
            if not math.isfinite(float(member)):
                raise V23Error(
                    f"{label} checkpoint trainer state field {field}[{index}] is not finite"
                )
    global_step = getattr(state, "global_step", None)
    if isinstance(global_step, bool) or not isinstance(global_step, int) or global_step != expected_step:
        raise V23Error(
            f"{label} checkpoint trainer state global_step must equal {expected_step}; got {global_step!r}"
        )
    return {
        "path": path,
        "global_step": global_step,
        "actor_key": actor_keys[0],
        "required_keys": list(required) + actor_keys,
        "trainer_state_fields": list(FULL_REQUIRED_TRAINER_STATE_FIELDS),
    }


def _validate_runtime_receipt_from_run_dir(
    run_dir: Path,
    *,
    config: Mapping[str, Any],
    expected_mode: str,
    expected_start: int,
    expected_end: int,
    checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    paths = _canonical_runtime_paths(run_dir)
    receipt = _read_runtime_object(paths["receipt"], label=f"{expected_mode} runtime receipt")
    if receipt.get("schema") != RUNTIME_RECEIPT_SCHEMA:
        raise V23Error(f"{expected_mode} runtime receipt schema is not {RUNTIME_RECEIPT_SCHEMA}")
    if receipt.get("status") != "RUNTIME_RECEIPT_VERIFIED" or receipt.get("mode") != expected_mode:
        raise V23Error(f"{expected_mode} runtime receipt is not a matching trainer verification")
    if receipt.get("canonical_run_dir") != str(run_dir):
        raise V23Error("runtime receipt canonical_run_dir does not match its run directory")
    if receipt.get("receipt_path") != str(paths["receipt"]):
        raise V23Error("runtime receipt receipt_path is not its canonical sibling")
    if receipt.get("effective_config_path") != str(paths["effective_config"]):
        raise V23Error("runtime receipt effective_config_path is not its canonical sibling")
    if receipt.get("expected_initial_step10_checkpoint_path") != config.get(
        "expected_initial_step10_checkpoint_path"
    ):
        raise V23Error(
            "runtime receipt expected_initial_step10_checkpoint_path disagrees with effective config"
        )

    contract = _runtime_receipt_mapping(receipt.get("contract"), label="contract")
    for key in ("env_count", "mask_indices", "neutral_value", "rp0_enabled"):
        if contract.get(key) != config.get({"env_count": "env_count", "mask_indices": "mask_indices", "neutral_value": "neutral_value", "rp0_enabled": "rp0_enabled"}[key]):
            raise V23Error(f"runtime receipt contract field {key!r} disagrees with effective config")
    mask_vector = contract.get("mask_vector")
    if not isinstance(mask_vector, list) or len(mask_vector) != 12 or any(not isinstance(item, bool) for item in mask_vector):
        raise V23Error("runtime receipt mask_vector must contain exactly twelve bool values")
    expected_masked = expected_mode == "RP0"
    if mask_vector[3] != (not expected_masked) or mask_vector[4] != (not expected_masked):
        raise V23Error("runtime receipt mask_vector does not encode raw posture indices [3,4]")

    checkpoint_row = _runtime_receipt_mapping(receipt.get("checkpoint"), label="checkpoint")
    if checkpoint_row.get("load_mode") != config.get("checkpoint_load_mode"):
        raise V23Error("runtime receipt checkpoint load mode disagrees with effective config")
    input_path = _runtime_receipt_regular_file(checkpoint_row.get("input_path"), label="checkpoint.input_path")
    output_path = _runtime_receipt_regular_file(checkpoint_row.get("output_path"), label="checkpoint.output_path")
    expected_input = Path(config["input_checkpoint_path"]).resolve()
    expected_output = paths["step10"] if expected_end == 10 else paths["step11"]
    if input_path != expected_input or output_path != expected_output:
        raise V23Error("runtime receipt checkpoint paths disagree with derived canonical paths")
    _runtime_receipt_bool(checkpoint_row.get("input_exists"), label="checkpoint.input_exists")
    _runtime_receipt_bool(checkpoint_row.get("output_exists"), label="checkpoint.output_exists")
    if checkpoint_row.get("input_exists") is not True or checkpoint_row.get("output_exists") is not True:
        raise V23Error("runtime receipt checkpoint existence facts are not true")
    if Path(checkpoint["path"]).resolve() != expected_output or checkpoint.get("global_step") != expected_end:
        raise V23Error("runtime receipt checkpoint row does not match inspected checkpoint contents")
    if checkpoint.get("trainer_state_fields") != FULL_REQUIRED_TRAINER_STATE_FIELDS:
        raise V23Error(
            "runtime receipt checkpoint trainer state fields do not match the complete persisted state contract"
        )

    steps = _runtime_receipt_mapping(receipt.get("global_step"), label="global_step")
    if (steps.get("restored_start"), steps.get("invocation_start"), steps.get("post_batch_end")) != (
        expected_start,
        expected_start,
        expected_end,
    ):
        raise V23Error("runtime receipt global-step chain disagrees with the derived contract")
    invocation = _runtime_receipt_mapping(receipt.get("invocation"), label="invocation")
    if invocation.get("num_total_batches") != config.get("invocation_batches") or invocation.get("save_frequency") != config.get("save_frequency"):
        raise V23Error("runtime receipt invocation fields disagree with effective config")
    if invocation.get("terminal_batch_completed") is not True or invocation.get("terminal_save_verified") is not True:
        raise V23Error("runtime receipt lacks terminal after-save execution evidence")

    stats = _runtime_receipt_mapping(receipt.get("masked_stats"), label="masked_stats")
    for field in ("actions", "action_mean"):
        row = _runtime_receipt_mapping(stats.get(field), label=f"masked_stats.{field}")
        values = row.get("max_abs")
        if not isinstance(values, list) or len(values) != 2:
            raise V23Error(f"masked_stats.{field}.max_abs must contain two values")
        values = [_runtime_receipt_number(value, label=f"masked_stats.{field}.max_abs[{i}]") for i, value in enumerate(values)]
        if _runtime_receipt_int(row.get("sample_count"), label=f"masked_stats.{field}.sample_count") <= 0:
            raise V23Error(f"masked_stats.{field} has no trainer-observed samples")
        if expected_masked and any(value != 0.0 for value in values):
            raise V23Error(f"RP0 masked {field} statistics must be exactly zero")
    if receipt.get("environment_continuity") is not False:
        raise V23Error("runtime receipt must state environment_continuity=false")
    restore_facts = _validate_restore_facts(
        receipt, mode=expected_mode, restored_start=expected_start
    )
    if expected_mode == "FULL":
        trainer_facts = _runtime_receipt_mapping(
            restore_facts.get("trainer"), label="restore_facts.trainer"
        )
        if trainer_facts.get("required_fields") != FULL_REQUIRED_TRAINER_STATE_FIELDS:
            raise V23Error(
                "full runtime receipt trainer required_fields do not match the complete persisted state contract"
            )
    return receipt


def finalize_runtime_receipts(
    initial_run_dir: str | None = None, resume_run_dir: str | None = None
) -> dict[str, Any]:
    """Finalize one real RP0 receipt plus one real FULL receipt.

    Omitted receipts intentionally leave the contract PENDING.  A supplied path
    is always parsed and validated; it can never be replaced by a synthetic row.
    """

    supplied = {"initial_run_dir": initial_run_dir, "resume_run_dir": resume_run_dir}
    if initial_run_dir is None or resume_run_dir is None:
        for label, raw in supplied.items():
            if raw is not None:
                _runtime_run_dir(raw, label=label)
        missing = [label for label, raw in supplied.items() if raw is None]
        return _pending_runtime_record(missing_receipts=missing)

    initial_dir = _runtime_run_dir(initial_run_dir, label="initial_run_dir")
    resume_dir = _runtime_run_dir(resume_run_dir, label="resume_run_dir")
    if initial_dir == resume_dir:
        raise V23Error("initial and resume run directories must be distinct canonical runs")
    initial_paths = _canonical_runtime_paths(initial_dir)
    resume_paths = _canonical_runtime_paths(resume_dir)
    initial_config, initial_input = _validate_effective_config(
        initial_dir, expected_mode="RP0", expected_start=0, expected_end=10, expected_batches=10
    )
    resume_config, resume_input = _validate_effective_config(
        resume_dir, expected_mode="FULL", expected_start=10, expected_end=11, expected_batches=1
    )
    initial_checkpoint = _inspect_runtime_checkpoint(
        initial_paths["step10"], expected_step=10, label="initial"
    )
    resume_checkpoint = _inspect_runtime_checkpoint(
        resume_paths["step11"], expected_step=11, label="resume"
    )
    if resume_input != initial_paths["step10"]:
        raise V23Error(
            "FULL resume input checkpoint must be the exact RP0 step10 output: "
            f"{resume_input} != {initial_paths['step10']}"
        )
    resume_expected_initial = Path(
        resume_config["expected_initial_step10_checkpoint_path"]
    ).resolve()
    if resume_expected_initial != initial_paths["step10"]:
        raise V23Error(
            "FULL effective config expected_initial_step10_checkpoint_path must be the exact RP0 step10 output: "
            f"{resume_expected_initial} != {initial_paths['step10']}"
        )
    if initial_input.name != "model_step_001250.pt":
        raise V23Error("initial effective config input must be the G1 step1250 warm checkpoint")
    if initial_config["mask_indices"] != resume_config["mask_indices"]:
        raise V23Error("RP0/FULL receipts disagree on mask indices")
    if initial_config["neutral_value"] != resume_config["neutral_value"]:
        raise V23Error("RP0/FULL receipts disagree on neutral value")
    if initial_config["env_count"] != resume_config["env_count"]:
        raise V23Error("RP0/FULL receipts disagree on environment count")
    initial = _validate_runtime_receipt_from_run_dir(
        initial_dir,
        config=initial_config,
        expected_mode="RP0",
        expected_start=0,
        expected_end=10,
        checkpoint=initial_checkpoint,
    )
    resume = _validate_runtime_receipt_from_run_dir(
        resume_dir,
        config=resume_config,
        expected_mode="FULL",
        expected_start=10,
        expected_end=11,
        checkpoint=resume_checkpoint,
    )

    record = build_static_record()
    record["status"] = RUNTIME_VERIFIED_STATUS
    record["mode"] = "RUNTIME_FINALIZED"
    record["contract"]["runtime_resume_status"] = RUNTIME_VERIFIED_STATUS
    record["runtime_receipts"] = {
        "schema": RUNTIME_RECEIPT_SCHEMA,
        "status": RUNTIME_VERIFIED_STATUS,
        "initial_run_dir": str(initial_dir),
        "resume_run_dir": str(resume_dir),
        "initial_receipt_path": str(initial_paths["receipt"]),
        "resume_receipt_path": str(resume_paths["receipt"]),
        "global_step_chain": [0, 10, 11],
        "mode_chain": ["RP0", "FULL"],
        "checkpoint_chain": [
            str(initial_input),
            str(initial_paths["step10"]),
            str(resume_paths["step11"]),
        ],
        "effective_config_paths": [str(initial_paths["effective_config"]), str(resume_paths["effective_config"])],
        "masked_stats": {
            "initial": initial["masked_stats"],
            "resume": resume["masked_stats"],
        },
        "strict_restore_facts": {
            "initial": initial["restore_facts"],
            "resume": resume["restore_facts"],
        },
        "environment_continuity": False,
    }
    return record


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="absolute output JSON path")
    parser.add_argument(
        "--finalize-receipts",
        action="store_true",
        help="consume trainer-owned initial RP0 and FULL receipts; omitted receipts remain PENDING",
    )
    parser.add_argument("--initial-run-dir", help="absolute initial RP0 trainer run directory")
    parser.add_argument("--resume-run-dir", help="absolute FULL resume trainer run directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.finalize_receipts and (args.initial_run_dir is not None or args.resume_run_dir is not None):
        raise V23Error("--initial-run-dir/--resume-run-dir require --finalize-receipts")
    payload = (
        finalize_runtime_receipts(args.initial_run_dir, args.resume_run_dir)
        if args.finalize_receipts
        else build_static_record()
    )
    emit_payload(payload, _absolute_output(args.output))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 RP0 CONTRACT FAIL: {exc}")
