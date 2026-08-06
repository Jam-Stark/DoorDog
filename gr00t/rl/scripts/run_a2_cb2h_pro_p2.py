#!/usr/bin/env python3
"""C-B2H-Pro P2 fresh-common-init B1/B2 launcher.

The B1 branch is the sole fresh source.  B2 consumes only the sealed B1
``core.*`` artifact and restores the serialized downstream RNG state before
Teacher/value construction.  ``--dry-run`` composes both real Hydra configs,
prints the serial command plan, and never creates an output root.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any
import runpy

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TEACHER_CHECKPOINT = Path(
    "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/"
    "a2_piper_full_stage_a2_base/base_v19/"
    "base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
).resolve()
TEACHER_CONFIG = TEACHER_CHECKPOINT.with_name("config.yaml")
TEACHER_MANIFEST = (
    REPO_ROOT
    / "logs_rl/cb2h_v19_runtime/g2_step2000_c18_reconstruction_candidate6168e6a2/teacher_manifest.json"
).resolve()
TEACHER_CHECKPOINT_SHA256 = "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d"
TEACHER_CONFIG_SHA256 = "65c1537b38d670097bc8498428e0aad1705c3fd66eeef41a93d63e3b6da4cf96"
TEACHER_MANIFEST_SHA256 = "479f4460d4dc05feea9d87d3189fa0617b21078f91b6f5176f4a9c41b141d1b7"
RUNTIME_REPOSITORY = Path("/tmp/cb2h_v19_runtime.waPJHftX/c18").resolve()
EXPECTED_RUNTIME_COMMIT = "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"
EXPECTED_GPU_INDEX = "7"
EXPECTED_LOGICAL_GPU_INDEX = "0"
EXPECTED_GPU_UUID = "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d"
EXPECTED_GPU_BINDING_MODE = "single-visible-logical-cuda0-v3"
EXPECTED_CUDA_DEVICE_ORDER = "PCI_BUS_ID"
EXPECTED_NUM_ENVS = 64
EXPECTED_BATCHES = 500
EXPECTED_NUM_STEPS_PER_ENV = 8
EXPECTED_NUM_MINI_BATCHES = 4
EXPECTED_NUM_PPO_EPOCHS = 1
EXPECTED_GRADIENT_ACCUMULATION_STEPS = 1
EXPECTED_ACTOR_LEARNING_RATE = 1.0e-4
EXPECTED_GAMMA = 0.9966
EXPECTED_LAM = 0.983
EXPECTED_DESIRED_KL = 0.005
EXPECTED_INIT_AT_RANDOM_EP_LEN = False
EXPECTED_USE_OBJ_PRED = False
EXPECTED_OBJ_PRED_LOSS_COEF = 0.0
VRAM_LIMIT_MIB = 47104
EXPECTED_START_GLOBAL_STEP = 0
EXPECTED_FINAL_GLOBAL_STEP = EXPECTED_BATCHES
EXPECTED_OPTIMIZER_STATE_STEP = (
    EXPECTED_BATCHES * EXPECTED_NUM_MINI_BATCHES * EXPECTED_NUM_PPO_EPOCHS
)
P2_TELEMETRY_SAMPLE_INTERVAL_S = 5.0
P2_TELEMETRY_MAX_ADJACENT_GAP_S = 15.0
P2_TELEMETRY_SCHEMA = "a2_cb2h_pro_p2_gpu_telemetry_v1"
P2_OPTIMIZER_SCHEMA = "a2_cb2h_pro_p2_optimizer_parameter_schema_v1"
P2_SCHEDULER_SCHEMA = "a2_cb2h_pro_p2_constant_scheduler_schema_v1"
P2_MODEL_STATE_SCHEMA = "a2_cb2h_pro_p2_model_state_schema_v1"
BOOTSTRAP_SCRIPT = (REPO_ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v19.py").resolve()
P2_COMMON_INIT_CONTRACT = {
    "schema": "a2_cb2h_pro_p2_common_init_v1",
    "actor_obs_dim": 81,
    "d435_shape": [384, 216, 6],
    "d435_encoder_output_dim": 128,
    "fusion_dim": 128,
    "recurrent": {"input_dim": 209, "hidden_dim": 256, "layers": 2, "type": "lstm"},
    "action_dim": 12,
    "seed": 0,
    "common_components": [
        "left_view_embedding",
        "right_view_embedding",
        "std",
        "d435i_vision_module",
        "left_view_norm",
        "right_view_norm",
        "manipulation_norm",
        "manipulation_residual",
        "memory",
        "mlp_module",
        "running_mean_std",
    ],
    "common_key_schema_sha256": "b608ce21d8477983aa9a78a8db4139140309f39dd8ca3e5fc1aba5327abefd97",
    "effective_training": {
        "num_envs": EXPECTED_NUM_ENVS,
        "num_total_batches": EXPECTED_BATCHES,
        "num_steps_per_env": EXPECTED_NUM_STEPS_PER_ENV,
        "num_mini_batches": EXPECTED_NUM_MINI_BATCHES,
        "num_ppo_epochs": EXPECTED_NUM_PPO_EPOCHS,
        "gradient_accumulation_steps": EXPECTED_GRADIENT_ACCUMULATION_STEPS,
        "actor_learning_rate": EXPECTED_ACTOR_LEARNING_RATE,
        "ratio_teacher_rollout": 1.0,
        "enforce_teacher_rollout": True,
        "gamma": EXPECTED_GAMMA,
        "lam": EXPECTED_LAM,
        "desired_kl": EXPECTED_DESIRED_KL,
        "init_at_random_ep_len": EXPECTED_INIT_AT_RANDOM_EP_LEN,
        "use_obj_pred": EXPECTED_USE_OBJ_PRED,
        "obj_pred_loss_coef": EXPECTED_OBJ_PRED_LOSS_COEF,
        "checkpoint": None,
        "checkpoint_load_mode": "full",
        "auto_load_latest": False,
    },
}
P2_COMMON_CONFIG_SHA256 = hashlib.sha256(
    json.dumps(P2_COMMON_INIT_CONTRACT, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
P2_SCHEMA = "a2_cb2h_pro_p2_plan_v1"
P2_BRANCH_SCHEMA = "a2_cb2h_pro_p2_branch_v1"
P2_RUNTIME_METRICS_SCHEMA = "a2_cb2h_pro_p2_runtime_metrics_v1"
P2_PAIR_SCHEMA = "a2_cb2h_pro_p2_pair_manifest_v1"
P2_FAILURE_SCHEMA = "a2_cb2h_pro_p2_failure_v1"
P2_COMMON_SEAL_SCHEMA = "a2_cb2h_pro_p2_common_init_seal_v1"
_DISTRIBUTED_ENV_NAMES = {
    "WORLD_SIZE",
    "RANK",
    "LOCAL_RANK",
    "LOCAL_WORLD_SIZE",
    "MASTER_ADDR",
    "MASTER_PORT",
}
_ACCELERATE_ENV_NAMES = {
    "ACCELERATE_TORCH_DEVICE",
    "ACCELERATE_BYPASS_DEVICE_MAP",
    "ACCELERATE_USE_CPU",
    "ACCELERATE_MIXED_PRECISION",
    "ACCELERATE_DYNAMO_BACKEND",
}
BRANCHES = ("b1", "b2")
EXPERIMENTS = {
    "b1": "wbmanip/door_open_a2_base_v19_p2_b1",
    "b2": "wbmanip/door_open_a2_base_v19_p2_b2",
}
ARCHITECTURES = {
    "b1": "C-B1-DUALRAW-SHAREDENC-TOEIN20-V19-P2",
    "b2": "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19-P2",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_file(path: Path) -> str:
    path = path.expanduser().resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    """Atomically seal JSON evidence without exposing partial files."""
    import tempfile

    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(value) + "\n").encode("utf-8")
    digest = sha256_bytes(encoded)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"path": str(destination), "sha256": digest, "size": len(encoded)}


def load_json(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=True)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"P2 JSON artifact must be an object: {path}")
    return value


def read_immutable_snapshot(path: Path) -> tuple[bytes, str]:
    """Read and hash one exact byte snapshot; callers decode these bytes."""
    source = path.expanduser().resolve(strict=True)
    with source.open("rb") as handle:
        payload = handle.read()
    return payload, sha256_bytes(payload)


def load_json_snapshot(
    path: Path, *, expected_sha256: str | None = None
) -> tuple[dict[str, Any], str, int]:
    payload, actual_sha256 = read_immutable_snapshot(path)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"P2 JSON artifact digest mismatch: expected={expected_sha256} actual={actual_sha256}"
        )
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"P2 JSON artifact must be an object: {path}")
    return value, actual_sha256, len(payload)


def require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA256 string")
    if any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be lowercase hexadecimal SHA256")
    return value


def require_git_commit(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a 40-character lowercase Git commit SHA")
    return value


def _p2_common_key_schema() -> tuple[str, ...]:
    """Return the production actor's exact ordered 156-key common schema."""
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import P2_COMMON_KEY_SCHEMA

    schema = tuple(P2_COMMON_KEY_SCHEMA)
    if len(schema) != 156:
        raise RuntimeError(f"P2 common key schema must contain 156 keys; got {len(schema)}")
    if sha256_bytes(canonical_json(schema).encode("utf-8")) != P2_COMMON_INIT_CONTRACT["common_key_schema_sha256"]:
        raise RuntimeError("P2 common key schema SHA disagrees with the contract")
    return schema


def _validate_state_schema(value: Any, *, name: str, expected_keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"P2 {name} must be a mapping")
    keys = value.get("keys")
    if not isinstance(keys, list) or tuple(keys) != tuple(expected_keys or keys):
        raise RuntimeError(f"P2 {name}.keys must be an ordered list")
    if not keys or any(not isinstance(key, str) or not key for key in keys):
        raise RuntimeError(f"P2 {name}.keys contains invalid entries")
    if len(set(keys)) != len(keys):
        raise RuntimeError(f"P2 {name}.keys contains duplicates")
    key_count = value.get("key_count")
    if _strict_int(key_count, f"{name}.key_count") != len(keys):
        raise RuntimeError(f"P2 {name}.key_count disagrees with keys")
    identities = value.get("identities")
    if not isinstance(identities, list) or len(identities) != len(keys):
        raise RuntimeError(f"P2 {name}.identities must align with keys")
    for index, (key, identity) in enumerate(zip(keys, identities, strict=True)):
        if not isinstance(identity, Mapping):
            raise RuntimeError(f"P2 {name}.identities[{index}] must be a mapping")
        if set(identity) != {"key", "shape", "dtype", "sha256"}:
            raise RuntimeError(f"P2 {name}.identities[{index}] has unexpected fields")
        if identity["key"] != key:
            raise RuntimeError(f"P2 {name}.identities[{index}] key order drifted")
        shape = identity["shape"]
        if not isinstance(shape, list) or any(isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0 for dim in shape):
            raise RuntimeError(f"P2 {name}.identities[{index}] shape must contain positive integers")
        if not isinstance(identity["dtype"], str) or not identity["dtype"]:
            raise RuntimeError(f"P2 {name}.identities[{index}] dtype is invalid")
        require_sha(identity["sha256"], f"{name}.identities[{index}].sha256")
    schema_sha = require_sha(value.get("schema_sha256"), f"{name}.schema_sha256")
    expected_schema_sha = sha256_bytes(canonical_json(identities).encode("utf-8"))
    if schema_sha != expected_schema_sha:
        raise RuntimeError(f"P2 {name}.schema_sha256 does not match ordered identities")
    aggregate_sha = require_sha(value.get("aggregate_sha256"), f"{name}.aggregate_sha256")
    if aggregate_sha != expected_schema_sha:
        raise RuntimeError(f"P2 {name}.aggregate_sha256 does not match ordered identities")
    return dict(value)


def _validate_production_model_schema(
    value: Mapping[str, Any],
    *,
    name: str,
    branch: str,
    role: str,
) -> dict[str, Any]:
    """Require exact key/shape/dtype schemas from the production implementations."""
    if value.get("schema") != P2_MODEL_STATE_SCHEMA:
        raise RuntimeError(f"P2 {name} model schema identity drifted")
    if value.get("role") != role:
        raise RuntimeError(f"P2 {name} model role drifted")
    if role == "policy":
        expected_architecture = ARCHITECTURES[branch]
        expected_implementation = (
            "gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent."
            + ("DualD435VisionRecurrentActor" if branch == "b1" else "DualD435HeadVisionRecurrentActor")
        )
    elif role == "value":
        expected_architecture = "RecurrentCritic"
        expected_implementation = "gr00t.rl.trl.modules.actor_critic_modules_recurrent.RecurrentCritic"
    else:
        raise RuntimeError(f"P2 {name} model role is unsupported: {role!r}")
    if value.get("architecture") != expected_architecture:
        raise RuntimeError(f"P2 {name} production architecture drifted")
    if value.get("implementation") != expected_implementation:
        raise RuntimeError(f"P2 {name} production implementation drifted")

    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import p2_production_state_contract

    trusted = p2_production_state_contract(branch, role)
    keys = value.get("keys")
    if keys != trusted["keys"]:
        raise RuntimeError(f"P2 {name} ordered production key schema drifted")
    identities = value.get("identities")
    structural = [
        {"key": item.get("key"), "shape": item.get("shape"), "dtype": item.get("dtype")}
        for item in identities
    ] if isinstance(identities, list) else None
    trusted_structural = [
        {"key": item["key"], "shape": item["shape"], "dtype": item["dtype"]}
        for item in trusted["identities"]
    ]
    if structural != trusted_structural:
        raise RuntimeError(f"P2 {name} production shape/dtype schema drifted")
    if value.get("contract_sha256") != trusted["contract_sha256"]:
        raise RuntimeError(f"P2 {name} production contract digest drifted")
    if value.get("parameter_keys") != trusted["parameter_keys"]:
        raise RuntimeError(f"P2 {name} production parameter order drifted")
    parameter_identities = value.get("parameter_identities")
    if parameter_identities != trusted["parameter_identities"]:
        raise RuntimeError(f"P2 {name} production parameter shape/dtype schema drifted")
    if value.get("parameter_count") != trusted["parameter_count"]:
        raise RuntimeError(f"P2 {name} production parameter count drifted")
    if value.get("parameter_schema_sha256") != trusted["parameter_schema_sha256"]:
        raise RuntimeError(f"P2 {name} production parameter contract digest drifted")
    return dict(value)


def _p2_normalize_optimizer_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_p2_normalize_optimizer_value(item) for item in value]
    if isinstance(value, list):
        return [_p2_normalize_optimizer_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _p2_normalize_optimizer_value(item) for key, item in value.items()}
    return value


def _validate_p2_optimizer_schema(
    optimizer_schema: Any,
    scheduler_schema: Any,
    *,
    policy_schema: Mapping[str, Any] | None = None,
    value_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the immutable real-optimizer contract written at step zero."""
    if not isinstance(optimizer_schema, Mapping) or set(optimizer_schema) != {
        "schema",
        "optimizer_wrapper_class",
        "optimizer_class",
        "parameter_count",
        "ordered_parameters",
        "param_groups",
        "state_parameter_ids",
    }:
        raise RuntimeError("P2 step0 optimizer parameter schema is missing or contains decoys")
    if optimizer_schema.get("schema") != P2_OPTIMIZER_SCHEMA:
        raise RuntimeError("P2 step0 optimizer schema identity drifted")
    if optimizer_schema.get("optimizer_wrapper_class") != "accelerate.optimizer.AcceleratedOptimizer":
        raise RuntimeError("P2 optimizer must retain Accelerate's prepared outer wrapper")
    if optimizer_schema.get("optimizer_class") != "torch.optim.adamw.AdamW":
        raise RuntimeError("P2 optimizer must be the real torch AdamW implementation")
    ordered = optimizer_schema.get("ordered_parameters")
    if not isinstance(ordered, list) or len(ordered) < 6:
        raise RuntimeError("P2 optimizer schema must bind the full policy/value parameter order")
    parameter_ids: list[int] = []
    parameter_names: list[str] = []
    parameter_shapes: list[list[int]] = []
    parameter_dtypes: list[str] = []
    for index, item in enumerate(ordered):
        if not isinstance(item, Mapping) or set(item) != {"id", "name", "shape", "dtype"}:
            raise RuntimeError(f"P2 optimizer ordered parameter {index} is malformed")
        parameter_id = item.get("id")
        if isinstance(parameter_id, bool) or not isinstance(parameter_id, int) or parameter_id < 0:
            raise RuntimeError(f"P2 optimizer ordered parameter {index} ID is invalid")
        name = item.get("name")
        if not isinstance(name, str) or not name or (not name.startswith("policy.") and not name.startswith("value_model.")):
            raise RuntimeError(f"P2 optimizer ordered parameter {index} name is invalid")
        shape = item.get("shape")
        if not isinstance(shape, list) or any(isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0 for dim in shape):
            raise RuntimeError(f"P2 optimizer ordered parameter {index} shape is invalid")
        if not isinstance(item.get("dtype"), str) or not item["dtype"]:
            raise RuntimeError(f"P2 optimizer ordered parameter {index} dtype is invalid")
        parameter_ids.append(parameter_id)
        parameter_names.append(name)
        parameter_shapes.append(shape)
        parameter_dtypes.append(item["dtype"])
    if len(set(parameter_ids)) != len(parameter_ids) or len(set(parameter_names)) != len(parameter_names):
        raise RuntimeError("P2 optimizer ordered parameters contain duplicates")
    if parameter_names[0].startswith("value_model.") or not any(name.startswith("value_model.") for name in parameter_names):
        raise RuntimeError("P2 optimizer order must place policy parameters before value parameters")
    if optimizer_schema.get("parameter_count") != len(ordered):
        raise RuntimeError("P2 optimizer parameter_count disagrees with ordered parameters")
    if optimizer_schema.get("state_parameter_ids") != []:
        raise RuntimeError("P2 step0 optimizer state must be empty before training")

    if policy_schema is not None or value_schema is not None:
        if policy_schema is None or value_schema is None:
            raise RuntimeError("P2 optimizer cross-binding requires both policy and value schemas")
        expected_order = [
            (f"policy.{key}", identity)
            for key, identity in zip(
                policy_schema.get("parameter_keys", []),
                policy_schema.get("parameter_identities", []),
                strict=True,
            )
        ] + [
            (f"value_model.{key}", identity)
            for key, identity in zip(
                value_schema.get("parameter_keys", []),
                value_schema.get("parameter_identities", []),
                strict=True,
            )
        ]
        if [item[0] for item in expected_order] != parameter_names:
            raise RuntimeError("P2 optimizer ordered parameters do not exactly bind policy then value")
        if [item[1]["shape"] for item in expected_order] != parameter_shapes or [item[1]["dtype"] for item in expected_order] != parameter_dtypes:
            raise RuntimeError("P2 optimizer ordered parameter shapes/dtypes do not bind model schemas")

    expected_hyperparameters = {
        "lr": EXPECTED_ACTOR_LEARNING_RATE,
        "betas": [0.9, 0.999],
        "eps": 1.0e-8,
        "weight_decay": 0.0,
        "amsgrad": False,
        "maximize": False,
        "foreach": None,
        "capturable": False,
        "differentiable": False,
        "fused": None,
        "decoupled_weight_decay": True,
        "initial_lr": EXPECTED_ACTOR_LEARNING_RATE,
    }
    groups = optimizer_schema.get("param_groups")
    if not isinstance(groups, list) or len(groups) != 2:
        raise RuntimeError("P2 optimizer schema must contain AdamW's two ordered parameter groups")
    grouped_ids: list[int] = []
    grouped_names: list[str] = []
    for group_index, group in enumerate(groups):
        if not isinstance(group, Mapping) or set(group) != {"index", "parameter_ids", "parameter_names", "hyperparameters"}:
            raise RuntimeError(f"P2 optimizer parameter group {group_index} is malformed")
        if group.get("index") != group_index:
            raise RuntimeError(f"P2 optimizer parameter group {group_index} order drifted")
        ids = group.get("parameter_ids")
        names = group.get("parameter_names")
        if not isinstance(ids, list) or not ids or not isinstance(names, list) or len(ids) != len(names):
            raise RuntimeError(f"P2 optimizer parameter group {group_index} members are malformed")
        if any(isinstance(item, bool) or not isinstance(item, int) for item in ids) or any(
            not isinstance(item, str) or not item for item in names
        ):
            raise RuntimeError(f"P2 optimizer parameter group {group_index} members are invalid")
        hyperparameters = group.get("hyperparameters")
        if not isinstance(hyperparameters, Mapping) or set(hyperparameters) != set(expected_hyperparameters):
            raise RuntimeError(f"P2 optimizer parameter group {group_index} hyperparameter schema drifted")
        normalized = _p2_normalize_optimizer_value(hyperparameters)
        for key, expected in expected_hyperparameters.items():
            actual = normalized.get(key)
            if isinstance(expected, float):
                if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(float(actual)):
                    raise RuntimeError(f"P2 optimizer parameter group {group_index}.{key} is invalid")
                if not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1.0e-12):
                    raise RuntimeError(f"P2 optimizer parameter group {group_index}.{key} drifted")
            elif actual != expected:
                raise RuntimeError(f"P2 optimizer parameter group {group_index}.{key} drifted")
        grouped_ids.extend(ids)
        grouped_names.extend(names)
    if set(grouped_ids) != set(parameter_ids) or len(grouped_ids) != len(parameter_ids):
        raise RuntimeError("P2 optimizer parameter groups do not cover the ordered policy/value schema")
    id_to_name = dict(zip(parameter_ids, parameter_names, strict=True))
    if any(id_to_name.get(parameter_id) != name for parameter_id, name in zip(grouped_ids, grouped_names, strict=True)):
        raise RuntimeError("P2 optimizer parameter group IDs/names do not bind the ordered policy/value schema")

    if not isinstance(scheduler_schema, Mapping) or set(scheduler_schema) != {"schema", "scheduler_class", "state_dict"}:
        raise RuntimeError("P2 step0 scheduler schema is missing or contains decoys")
    if scheduler_schema.get("schema") != P2_SCHEDULER_SCHEMA:
        raise RuntimeError("P2 scheduler schema identity drifted")
    scheduler_state = scheduler_schema.get("state_dict")
    if not isinstance(scheduler_state, Mapping) or set(scheduler_state) != {
        "base_lrs", "last_epoch", "_step_count", "_get_lr_called_within_step", "_last_lr", "lr_lambdas"
    }:
        raise RuntimeError("P2 constant scheduler state schema drifted")
    if not isinstance(scheduler_state.get("base_lrs"), list) or scheduler_state["base_lrs"] != [EXPECTED_ACTOR_LEARNING_RATE] * len(groups):
        raise RuntimeError("P2 constant scheduler base_lrs drifted")
    if isinstance(scheduler_state.get("last_epoch"), bool) or not isinstance(scheduler_state.get("last_epoch"), int) or scheduler_state.get("last_epoch") != 0 or isinstance(scheduler_state.get("_step_count"), bool) or not isinstance(scheduler_state.get("_step_count"), int) or scheduler_state.get("_step_count") != 1 or scheduler_state.get("_get_lr_called_within_step") is not False:
        raise RuntimeError("P2 constant scheduler initial step state drifted")
    if scheduler_state.get("_last_lr") != [EXPECTED_ACTOR_LEARNING_RATE] * len(groups):
        raise RuntimeError("P2 constant scheduler initial learning rates drifted")
    if scheduler_state.get("lr_lambdas") != [None] * len(groups):
        raise RuntimeError("P2 constant scheduler lambda state drifted")
    if not isinstance(scheduler_schema.get("scheduler_class"), str) or not scheduler_schema["scheduler_class"].endswith("LambdaLR"):
        raise RuntimeError("P2 scheduler must be the real constant LambdaLR scheduler")
    return dict(optimizer_schema)


def validate_runtime_repository(repository: Path = RUNTIME_REPOSITORY) -> dict[str, Any]:
    """Reuse the v19 bootstrap's exact c18 module-source/runtime validation."""
    from gr00t.rl.scripts import run_a2_student_distillation_v19 as bootstrap

    module_sources = bootstrap.validate_runtime_repository(repository)
    return {
        "repository": str(repository.expanduser().resolve()),
        "commit": EXPECTED_RUNTIME_COMMIT,
        "module_sources": {name: str(path) for name, path in module_sources.items()},
        "scenario_module": "gr00t.rl.data.tasks.door.scenario_cfg.isaacsim",
        "finder": "V19RuntimeFinder",
        "scenario_file_pin": True,
    }


def validate_overlay_repository(repository: Path = REPO_ROOT) -> Path:
    from gr00t.rl.scripts import run_a2_student_distillation_v19 as bootstrap

    return bootstrap.validate_overlay_repository(repository)


def build_child_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Strip inherited distributed/Accelerate/A2 state before exact GPU7 bind."""
    from gr00t.rl.scripts import run_a2_cb2h_pro_p1 as p1

    environment = dict(os.environ if base is None else base)
    for key in list(environment):
        if key in _DISTRIBUTED_ENV_NAMES or key.startswith("MASTER_") or key in _ACCELERATE_ENV_NAMES or key.startswith("ACCELERATE_"):
            environment.pop(key, None)
        elif key.startswith("A2_"):
            environment.pop(key, None)
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": EXPECTED_GPU_INDEX,
            "CUDA_DEVICE_ORDER": EXPECTED_CUDA_DEVICE_ORDER,
            "A2_GPU_BINDING_MODE": EXPECTED_GPU_BINDING_MODE,
            "A2_EXPECTED_WORLD_SIZE": "1",
            "A2_EXPECTED_HOST_GPU_INDEX": EXPECTED_GPU_INDEX,
            "A2_EXPECTED_LOGICAL_GPU_INDEX": EXPECTED_LOGICAL_GPU_INDEX,
            "A2_EXPECTED_GPU_UUID": EXPECTED_GPU_UUID,
        }
    )
    p1.validate_gpu_binding_environment(environment)
    return environment


def sample_gpu_telemetry(environ: Mapping[str, str]) -> dict[str, Any]:
    """Sample physical GPU7 and reject empty/non-finite/over-VRAM evidence."""
    query = "index,uuid,memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu"
    result = subprocess.run(
        [
            "nvidia-smi",
            "-i",
            EXPECTED_GPU_INDEX,
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=dict(environ),
    )
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        raise RuntimeError(f"P2 GPU sampler expected exactly one physical GPU7 row: {rows!r}")
    row_text = rows[0]
    columns = [part.strip() for part in row_text.split(",")]
    if len(columns) != 7:
        raise RuntimeError(f"P2 GPU sampler row shape drifted: {row_text!r}")
    try:
        index = int(columns[0])
        values = [float(part) for part in columns[2:]]
    except ValueError as exc:
        raise RuntimeError(f"P2 GPU sampler row is non-numeric: {row_text!r}") from exc
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"P2 GPU sampler row contains non-finite telemetry: {row_text!r}")
    uuid_value = columns[1]
    if not uuid_value:
        raise RuntimeError("P2 GPU sampler requires a non-empty UUID")
    if index != int(EXPECTED_GPU_INDEX):
        raise RuntimeError(f"P2 GPU sampler sampled unexpected physical GPU index: {index!r}")
    if uuid_value != EXPECTED_GPU_UUID:
        raise RuntimeError(f"P2 GPU UUID drifted: {uuid_value!r}")
    row = {
        "index": index,
        "uuid": uuid_value,
        "memory_used_mib": values[0],
        "memory_total_mib": values[1],
        "utilization_gpu_pct": values[2],
        "power_draw_w": values[3],
        "temperature_c": values[4],
    }
    if not 0.0 <= row["memory_used_mib"] < VRAM_LIMIT_MIB or row["memory_used_mib"] > row["memory_total_mib"]:
        raise RuntimeError(f"P2 GPU VRAM limit violated: {row['memory_used_mib']}")
    if row["memory_total_mib"] <= 0.0:
        raise RuntimeError(f"P2 GPU total memory must be positive: {row['memory_total_mib']}")
    if not 0.0 <= row["utilization_gpu_pct"] <= 100.0:
        raise RuntimeError(f"P2 GPU utilization is outside [0,100]: {row['utilization_gpu_pct']}")
    if row["power_draw_w"] < 0.0 or not 0.0 <= row["temperature_c"] <= 150.0:
        raise RuntimeError("P2 GPU power/temperature telemetry is outside physical bounds")
    return {
        "physical_gpu_index": EXPECTED_GPU_INDEX,
        "logical_gpu_index": int(EXPECTED_LOGICAL_GPU_INDEX),
        "logical_device": "cuda:0",
        "uuid": row["uuid"],
        "cuda_visible_devices": EXPECTED_GPU_INDEX,
        "cuda_device_order": EXPECTED_CUDA_DEVICE_ORDER,
        "binding_mode": EXPECTED_GPU_BINDING_MODE,
        "world_size": 1,
        "memory_used_mib": row["memory_used_mib"],
        "memory_total_mib": row["memory_total_mib"],
        "utilization_gpu_pct": row["utilization_gpu_pct"],
        "power_draw_w": row["power_draw_w"],
        "temperature_c": row["temperature_c"],
        "sample_time_ns": time.time_ns(),
    }


class GpuTelemetrySampler:
    def __init__(self, environ: Mapping[str, str], interval_s: float = P2_TELEMETRY_SAMPLE_INTERVAL_S):
        self.environ = dict(environ)
        self.interval_s = float(interval_s)
        if self.interval_s <= 0.0:
            raise ValueError("P2 GPU sampler interval must be positive")
        if not math.isclose(self.interval_s, P2_TELEMETRY_SAMPLE_INTERVAL_S, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(
                "P2 GPU sampler interval must be the sealed 5-second cadence: "
                f"got {self.interval_s!r}"
            )
        self.records: list[dict[str, Any]] = []
        self.error: BaseException | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self):
        try:
            while not self._stop.is_set():
                self.sample_once()
                self._stop.wait(self.interval_s)
        except BaseException as exc:
            self.error = exc
            self._stop.set()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("P2 GPU sampler already started")
        self._thread = threading.Thread(target=self._run, name="p2-gpu-sampler", daemon=True)
        self._thread.start()

    def sample_once(self) -> dict[str, Any]:
        if self.error is not None:
            raise RuntimeError("P2 GPU sampler failed") from self.error
        record = sample_gpu_telemetry(self.environ)
        self.records.append(record)
        return record

    def stop(self, *, process_started_ns: int | None = None, process_ended_ns: int | None = None) -> dict[str, Any]:
        if self._thread is None:
            raise RuntimeError("P2 GPU sampler was not started")
        self._stop.set()
        self._thread.join(timeout=30.0)
        if self._thread.is_alive():
            raise RuntimeError("P2 GPU sampler did not stop")
        if self.error is not None:
            raise RuntimeError("P2 GPU sampler failed") from self.error
        if process_started_ns is None or process_ended_ns is None:
            raise RuntimeError("P2 GPU sampler requires process interval timestamps")
        if process_ended_ns <= process_started_ns:
            raise RuntimeError("P2 GPU process interval timestamps are not increasing")
        self.sample_once()
        if not self.records:
            raise RuntimeError("P2 GPU sampler produced no records")
        peak = max(record["memory_used_mib"] for record in self.records)
        if not math.isfinite(peak) or peak >= VRAM_LIMIT_MIB:
            raise RuntimeError(f"P2 GPU sampler peak VRAM violates limit: {peak}")
        return {
            "schema": P2_TELEMETRY_SCHEMA,
            "record_count": len(self.records),
            "records": list(self.records),
            "peak_vram_mib": peak,
            "process_started_ns": process_started_ns,
            "process_ended_ns": process_ended_ns,
            "sample_interval_s": self.interval_s,
            "max_adjacent_gap_s": P2_TELEMETRY_MAX_ADJACENT_GAP_S,
            "gpu_identity": {
                "physical_gpu_index": EXPECTED_GPU_INDEX,
                "logical_gpu_index": int(EXPECTED_LOGICAL_GPU_INDEX),
                "logical_device": "cuda:0",
                "uuid": EXPECTED_GPU_UUID,
                "cuda_visible_devices": EXPECTED_GPU_INDEX,
                "cuda_device_order": EXPECTED_CUDA_DEVICE_ORDER,
                "binding_mode": EXPECTED_GPU_BINDING_MODE,
                "world_size": 1,
            },
        }


def validate_artifact(path: Path, expected_sha256: str, name: str) -> dict[str, str]:
    path = path.expanduser().resolve(strict=True)
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise RuntimeError(f"P2 {name} SHA256 mismatch: expected={expected_sha256} actual={actual}")
    return {"path": str(path), "sha256": actual}


def validate_teacher_triplet() -> dict[str, dict[str, str]]:
    return {
        "checkpoint": validate_artifact(TEACHER_CHECKPOINT, TEACHER_CHECKPOINT_SHA256, "Teacher checkpoint"),
        "config": validate_artifact(TEACHER_CONFIG, TEACHER_CONFIG_SHA256, "Teacher config"),
        "manifest": validate_artifact(TEACHER_MANIFEST, TEACHER_MANIFEST_SHA256, "Teacher manifest"),
    }


@dataclass(frozen=True)
class P2Branch:
    branch: str
    root: Path
    overrides: tuple[str, ...]
    command: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": P2_BRANCH_SCHEMA,
            "branch": self.branch,
            "architecture": ARCHITECTURES[self.branch],
            "root": str(self.root),
            "overrides": list(self.overrides),
            "command": list(self.command),
        }


@dataclass(frozen=True)
class P2Plan:
    output_root: Path
    common_root: Path
    serial_root: Path
    branches: tuple[P2Branch, P2Branch]
    teacher: dict[str, dict[str, str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": P2_SCHEMA,
            "output_root": str(self.output_root),
            "layout": {
                "common_init": str(self.common_root),
                "serial": str(self.serial_root),
                "serial_order": list(BRANCHES),
                "branches": {branch.branch: str(branch.root) for branch in self.branches},
            },
            "teacher": self.teacher,
            "runtime": {
                "repository": str(RUNTIME_REPOSITORY),
                "commit": EXPECTED_RUNTIME_COMMIT,
                "bootstrap_library": str(BOOTSTRAP_SCRIPT),
                "branch_entrypoint": str(Path(__file__).resolve()),
                "bootstrap_main_invoked": False,
                "scenario_file_pin": True,
                "runtime_finder": "V19RuntimeFinder",
                "gpu_host_index": EXPECTED_GPU_INDEX,
                "gpu_logical_index": EXPECTED_LOGICAL_GPU_INDEX,
                "gpu_uuid": EXPECTED_GPU_UUID,
                "num_envs": EXPECTED_NUM_ENVS,
            },
            "common_init": {
                "source_branch": "b1",
                "artifact": str(self.common_root / "b1_common_init.pt"),
                "config_sha256": P2_COMMON_CONFIG_SHA256,
                "key_schema_sha256": P2_COMMON_INIT_CONTRACT["common_key_schema_sha256"],
                "fresh_seed": 0,
                "trusted_artifact_sha256": "SEALED_AFTER_B1_STEP0",
            },
            "effective_training_contract": dict(P2_COMMON_INIT_CONTRACT["effective_training"]),
            "branches": [branch.as_dict() for branch in self.branches],
        }


def build_training_overrides(
    branch: str,
    branch_root: Path,
    common_root: Path,
    *,
    trusted_artifact_sha256: str | None = None,
    trusted_source_step0_manifest_sha256: str | None = None,
) -> tuple[str, ...]:
    if branch not in BRANCHES:
        raise ValueError(f"unknown P2 branch: {branch!r}")
    branch_root = branch_root.expanduser().resolve()
    common_root = common_root.expanduser().resolve()
    artifact = common_root / "b1_common_init.pt"
    step0 = common_root / f"{branch}_step0_manifest.json"
    source_step0 = common_root / "b1_step0_manifest.json"
    trusted_artifact_sha256 = trusted_artifact_sha256 or "REQUIRED_AFTER_B1_STEP0_SEAL"
    trusted_source_step0_manifest_sha256 = (
        trusted_source_step0_manifest_sha256 or "REQUIRED_AFTER_B1_STEP0_SEAL"
    )
    return (
        f"+exp={EXPERIMENTS[branch]}",
        f"num_envs={EXPECTED_NUM_ENVS}",
        f"algo.trl.num_total_batches={EXPECTED_BATCHES}",
        "callbacks.model_save.save_frequency=500",
        f"experiment_dir={branch_root}",
        "checkpoint=null",
        "checkpoint_load_mode=full",
        "auto_load_latest=false",
        "use_wandb=false",
        "headless=true",
        "enable_cameras=true",
        "algo.config.num_steps_per_env=8",
        "algo.config.num_mini_batches=4",
        "algo.config.num_learning_epochs=1",
        "algo.trl.num_ppo_epochs=1",
        "algo.trl.gradient_accumulation_steps=1",
        "algo.config.actor_learning_rate=0.0001",
        "algo.config.gamma=0.9966",
        "algo.config.lam=0.983",
        "algo.config.desired_kl=0.005",
        "algo.config.init_at_random_ep_len=false",
        "algo.config.use_obj_pred=false",
        "algo.config.obj_pred_loss_coef=0.0",
        f"teacher_actor_path={TEACHER_CHECKPOINT}",
        f"teacher_config_path={TEACHER_CONFIG}",
        f"teacher_manifest_path={TEACHER_MANIFEST}",
        "algo.config.use_a2_base=true",
        "algo.config.enforce_teacher_rollout=true",
        "algo.config.ratio_teacher_rollout=1.0",
        "algo.config.p2_common_init.enabled=true",
        f"algo.config.p2_common_init.branch={branch}",
        f"algo.config.p2_common_init.mode={'create' if branch == 'b1' else 'load'}",
        f"algo.config.p2_common_init.architecture={ARCHITECTURES[branch]}",
        "algo.config.p2_common_init.seed=0",
        f"algo.config.p2_common_init.config_sha256={P2_COMMON_CONFIG_SHA256}",
        f"algo.config.p2_common_init.artifact_path={artifact}",
        f"algo.config.p2_common_init.step0_manifest_path={step0}",
        f"algo.config.p2_common_init.source_step0_manifest_path={source_step0}",
        f"algo.config.p2_common_init.trusted_artifact_sha256={trusted_artifact_sha256}",
        f"algo.config.p2_common_init.trusted_source_step0_manifest_sha256={trusted_source_step0_manifest_sha256}",
        "algo.config.p2_common_init.runtime_identity.runtime_repository=" + str(RUNTIME_REPOSITORY),
        f"algo.config.p2_common_init.runtime_identity.runtime_commit={EXPECTED_RUNTIME_COMMIT}",
        "algo.config.p2_lifecycle.enabled=true",
        f"algo.config.p2_lifecycle.target_global_step={EXPECTED_FINAL_GLOBAL_STEP}",
        *( ("~obs.obs_dict.context_vision_obs",) if branch == "b1" else () ),
    )


def build_branch_command(branch: str, branch_root: Path, common_root: Path) -> tuple[str, ...]:
    overrides = build_training_overrides(branch, branch_root, common_root)
    return _build_branch_command_with_overrides(
        branch,
        branch_root,
        common_root,
        overrides,
    )


def _build_branch_command_with_overrides(
    branch: str,
    branch_root: Path,
    common_root: Path,
    overrides: tuple[str, ...],
) -> tuple[str, ...]:
    if branch not in BRANCHES:
        raise ValueError(f"unknown P2 branch: {branch!r}")
    if not BOOTSTRAP_SCRIPT.is_file():
        raise FileNotFoundError(f"P2 v19 bootstrap library is unavailable: {BOOTSTRAP_SCRIPT}")
    return (
        sys.executable,
        str(Path(__file__).resolve()),
        "--execute-branch",
        f"--runtime-repository={RUNTIME_REPOSITORY}",
        f"--overlay-repository={REPO_ROOT}",
        f"--teacher-actor-path={TEACHER_CHECKPOINT}",
        f"--teacher-config-path={TEACHER_CONFIG}",
        f"--teacher-manifest-path={TEACHER_MANIFEST}",
        f"--branch={branch}",
        f"--branch-root={Path(branch_root).expanduser().resolve()}",
        f"--common-root={Path(common_root).expanduser().resolve()}",
        "--",
        *overrides,
    )


def compose_training_config(overrides: tuple[str, ...]):
    try:
        from hydra import compose, initialize_config_dir
    except ImportError as exc:
        raise RuntimeError("P2 dry-run requires hydra-core for exact config composition") from exc
    config_dir = (REPO_ROOT / "gr00t/rl/config").resolve(strict=True)
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        return compose(config_name="base", overrides=list(overrides))


def validate_composed_config(config, branch: str) -> None:
    architecture = config.simulator.config.cameras.policy_multiview.architecture_id
    if architecture != ARCHITECTURES[branch]:
        raise RuntimeError(f"P2 {branch} architecture drifted: {architecture!r}")
    actor_target = config.algo.config.actor._target_
    expected_target = (
        "gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent."
        + ("DualD435VisionRecurrentActor" if branch == "b1" else "DualD435HeadVisionRecurrentActor")
    )
    if actor_target != expected_target:
        raise RuntimeError(f"P2 {branch} actor target drifted: {actor_target!r}")
    dims = {}
    for item in config.obs.obs_dims:
        key = str(next(iter(item)))
        if key in {"camera_meta", "rgb_image", "vision_obs", "context_rgb_image", "context_vision_obs"}:
            dims[key] = int(item[key])
    expected_meta = 4 if branch == "b1" else 6
    rgb_dim = dims.get("rgb_image", dims.get("vision_obs"))
    if dims.get("camera_meta") != expected_meta or rgb_dim != 384 * 216 * 6:
        raise RuntimeError(f"P2 {branch} observation dimensions drifted: {dims}")
    effective = config.algo.config
    trl = config.algo.trl
    exact = {
        "num_envs": int(config.num_envs),
        "num_total_batches": int(trl.num_total_batches),
        "num_steps_per_env": int(effective.num_steps_per_env),
        "num_mini_batches": int(effective.num_mini_batches),
        "num_ppo_epochs": int(trl.num_ppo_epochs),
        "gradient_accumulation_steps": int(trl.gradient_accumulation_steps),
        "actor_learning_rate": float(effective.actor_learning_rate),
        "ratio_teacher_rollout": float(effective.ratio_teacher_rollout),
        "enforce_teacher_rollout": bool(effective.enforce_teacher_rollout),
        "gamma": float(effective.gamma),
        "lam": float(effective.lam),
        "desired_kl": float(effective.desired_kl),
        "init_at_random_ep_len": bool(effective.init_at_random_ep_len),
        "use_obj_pred": bool(effective.use_obj_pred),
        "obj_pred_loss_coef": float(effective.obj_pred_loss_coef),
        "checkpoint": config.checkpoint,
        "checkpoint_load_mode": str(config.checkpoint_load_mode),
        "auto_load_latest": bool(config.auto_load_latest),
    }
    for key, expected in P2_COMMON_INIT_CONTRACT["effective_training"].items():
        actual = exact[key]
        if isinstance(expected, float):
            if not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-12):
                raise RuntimeError(f"P2 effective {key} drifted: expected={expected} actual={actual}")
        elif actual != expected:
            raise RuntimeError(f"P2 effective {key} drifted: expected={expected!r} actual={actual!r}")
    if config.callbacks.model_save.save_frequency != EXPECTED_BATCHES:
        raise RuntimeError("P2 effective save_frequency must be exactly 500")
    if config.algo.config.p2_common_init.config_sha256 != P2_COMMON_CONFIG_SHA256:
        raise RuntimeError("P2 common-init config SHA drifted")
    if branch == "b1":
        if "context_vision_obs" in config.obs.obs_dict or "head_vision_module" in config.algo.config.actor.backbone:
            raise RuntimeError("P2 B1 must not contain Head/context inputs")
    elif "context_vision_obs" not in config.obs.obs_dict:
        raise RuntimeError("P2 B2 requires context_vision_obs")


def build_plan(output_root: Path) -> P2Plan:
    output_root = output_root.expanduser().resolve()
    if output_root.exists():
        raise FileExistsError(f"P2 output root must be fresh: {output_root}")
    validate_overlay_repository(REPO_ROOT)
    runtime = validate_runtime_repository(RUNTIME_REPOSITORY)
    if runtime.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError("P2 dry-run runtime commit is not the sealed c18 commit")
    common_root = output_root / "common_init"
    teacher = validate_teacher_triplet()
    branches = []
    for branch in BRANCHES:
        branch_root = output_root / branch
        overrides = build_training_overrides(branch, branch_root, common_root)
        config = compose_training_config(overrides)
        validate_composed_config(config, branch)
        branches.append(P2Branch(branch, branch_root, overrides, build_branch_command(branch, branch_root, common_root)))
    return P2Plan(output_root, common_root, output_root / "serial", tuple(branches), teacher)


def _validate_step0_manifest(
    path: Path,
    *,
    expected_branch: str,
    artifact_sha256: str,
    expected_artifact_path: Path,
    expected_source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    manifest, _, _ = load_json_snapshot(path)
    return _validate_step0_manifest_value(
        manifest,
        expected_branch=expected_branch,
        artifact_sha256=artifact_sha256,
        expected_artifact_path=expected_artifact_path,
        expected_source=expected_source,
    )


def _validate_step0_manifest_value(
    manifest: Mapping[str, Any],
    *,
    expected_branch: str,
    artifact_sha256: str,
    expected_artifact_path: Path,
    expected_source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = dict(manifest)
    if manifest.get("schema") != "a2_cb2h_pro_p2_step0_manifest_v1":
        raise RuntimeError(f"P2 {expected_branch} step0 schema drifted")
    if manifest.get("global_step") != 0 or manifest.get("optimizer") is not None:
        raise RuntimeError("P2 step0 must be global_step=0 with optimizer=null")
    if manifest.get("branch") != expected_branch:
        raise RuntimeError(f"P2 step0 branch drifted: {manifest.get('branch')!r}")
    if manifest.get("architecture") != ARCHITECTURES[expected_branch]:
        raise RuntimeError(f"P2 {expected_branch} step0 architecture drifted")
    if manifest.get("seed") != 0:
        raise RuntimeError(f"P2 {expected_branch} step0 seed drifted")
    if manifest.get("config_sha256") != P2_COMMON_CONFIG_SHA256:
        raise RuntimeError("P2 step0 config SHA drifted")
    runtime_identity = manifest.get("runtime_identity")
    if not isinstance(runtime_identity, Mapping):
        raise RuntimeError("P2 step0 runtime identity is missing")
    if runtime_identity.get("runtime_repository") != str(RUNTIME_REPOSITORY) or runtime_identity.get(
        "runtime_commit"
    ) != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError("P2 step0 runtime identity drifted")
    require_git_commit(runtime_identity.get("runtime_commit"), "P2 step0 runtime commit")
    artifact_digest = require_sha(manifest.get("artifact_sha256"), "P2 step0 artifact SHA")
    if artifact_digest != artifact_sha256:
        raise RuntimeError("P2 step0 external artifact SHA drifted")
    common_schema = _p2_common_key_schema()
    if manifest.get("common_core_key_schema_sha256") != P2_COMMON_INIT_CONTRACT["common_key_schema_sha256"]:
        raise RuntimeError("P2 step0 common key schema SHA drifted")
    keys = manifest.get("common_core_keys")
    if not isinstance(keys, list) or tuple(keys) != common_schema:
        raise RuntimeError("P2 step0 ordered common core keys are not the exact 156-key schema")
    identities = manifest.get("common_core_key_identities")
    if not isinstance(identities, list) or len(identities) != len(common_schema):
        raise RuntimeError("P2 step0 ordered common core identities are missing")
    for index, (key, identity) in enumerate(zip(common_schema, identities, strict=True)):
        if not isinstance(identity, Mapping) or set(identity) != {"key", "shape", "dtype", "sha256"}:
            raise RuntimeError(f"P2 step0 common core identity {index} is malformed")
        if identity["key"] != key:
            raise RuntimeError(f"P2 step0 common core key order drifted at index {index}")
        shape = identity["shape"]
        if not isinstance(shape, list) or any(isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0 for dim in shape):
            raise RuntimeError(f"P2 step0 common core shape is invalid at index {index}")
        if not isinstance(identity["dtype"], str) or not identity["dtype"]:
            raise RuntimeError(f"P2 step0 common core dtype is invalid at index {index}")
        require_sha(identity["sha256"], f"P2 step0 common core tensor SHA {index}")
    expected_core_sha = sha256_bytes(canonical_json(identities).encode("utf-8"))
    if require_sha(manifest.get("common_core_sha256"), "P2 step0 common core SHA") != expected_core_sha:
        raise RuntimeError("P2 step0 common core aggregate SHA drifted")
    require_sha(manifest.get("common_init_manifest_sha256"), "P2 step0 common-init manifest SHA")
    require_sha(manifest.get("rng_before_policy_identity"), "P2 step0 pre-policy RNG identity")
    require_sha(manifest.get("rng_downstream_identity"), "P2 step0 downstream RNG identity")
    if manifest.get("device") != "cuda:0":
        raise RuntimeError("P2 step0 device contract must be cuda:0")
    common_artifact = manifest.get("common_init_artifact")
    if not isinstance(common_artifact, str) or not common_artifact:
        raise RuntimeError("P2 step0 common-init artifact path is missing")
    artifact_path = Path(common_artifact).expanduser().resolve(strict=True)
    expected_artifact_path = Path(expected_artifact_path).expanduser().resolve()
    if artifact_path != expected_artifact_path:
        raise RuntimeError(
            "P2 step0 common-init artifact path is not the caller-trusted exact path: "
            f"expected={expected_artifact_path} actual={artifact_path}"
        )
    artifact_payload, actual_artifact_sha256 = read_immutable_snapshot(artifact_path)
    if actual_artifact_sha256 != artifact_sha256:
        raise RuntimeError("P2 step0 common-init artifact changed or is not externally trusted")
    _validate_common_init_artifact_snapshot(
        artifact_payload,
        artifact_sha256=artifact_sha256,
        step0=manifest,
    )
    policy_schema = _validate_state_schema(manifest.get("policy_state_schema"), name="step0.policy_state_schema")
    value_schema = _validate_state_schema(manifest.get("value_state_schema"), name="step0.value_state_schema")
    _validate_production_model_schema(
        policy_schema,
        name="step0.policy_state_schema",
        branch=expected_branch,
        role="policy",
    )
    _validate_production_model_schema(
        value_schema,
        name="step0.value_state_schema",
        branch=expected_branch,
        role="value",
    )
    artifact_core_identities = {
        identity["key"]: identity
        for identity in manifest["common_core_key_identities"]
    }
    policy_identities = {
        identity["key"]: identity
        for identity in policy_schema["identities"]
    }
    for key in common_schema:
        if policy_identities.get(key) != artifact_core_identities.get(key):
            raise RuntimeError(
                f"P2 {expected_branch} policy common-core identity disagrees with the trusted artifact: {key}"
            )
    if require_sha(manifest.get("policy_state_schema_sha256"), "P2 step0 policy schema SHA") != policy_schema["schema_sha256"]:
        raise RuntimeError("P2 step0 policy schema SHA drifted")
    if require_sha(manifest.get("value_state_schema_sha256"), "P2 step0 value schema SHA") != value_schema["schema_sha256"]:
        raise RuntimeError("P2 step0 value schema SHA drifted")
    _validate_p2_optimizer_schema(
        manifest.get("optimizer_parameter_schema"),
        manifest.get("scheduler_schema"),
        policy_schema=policy_schema,
        value_schema=value_schema,
    )
    if expected_source is not None:
        comparable = (
            "seed",
            "config_sha256",
            "runtime_identity",
            "common_core_sha256",
            "common_core_key_schema_sha256",
            "common_core_keys",
            "common_core_key_identities",
            "artifact_sha256",
            "rng_before_policy_identity",
            "rng_downstream_identity",
        )
        for key in comparable:
            if manifest.get(key) != expected_source.get(key):
                raise RuntimeError(f"P2 B1/B2 step0 mismatch: {key}")
    return manifest


def _validate_common_init_artifact_snapshot(
    artifact_payload: bytes,
    *,
    artifact_sha256: str,
    step0: Mapping[str, Any],
) -> dict[str, Any]:
    """Decode and validate the immutable production B1 common-init payload."""
    import torch

    try:
        payload = torch.load(io.BytesIO(artifact_payload), map_location="cpu", weights_only=False)
    except Exception as exc:
        raise RuntimeError("P2 common-init artifact is not a valid torch payload") from exc
    if not isinstance(payload, Mapping) or set(payload) != {"manifest", "state_dict", "rng_downstream"}:
        raise RuntimeError("P2 common-init artifact payload schema drifted")
    artifact_manifest = payload.get("manifest")
    if not isinstance(artifact_manifest, Mapping):
        raise RuntimeError("P2 common-init artifact manifest is missing")
    expected_manifest_fields = {
        "schema", "branch", "architecture", "seed", "config_sha256", "runtime_identity",
        "common_prefix", "common_components", "common_core_key_schema_sha256", "key_count",
        "keys", "aggregate_sha256", "rng_before_policy_identity", "rng_downstream_identity",
    }
    if set(artifact_manifest) != expected_manifest_fields:
        raise RuntimeError("P2 common-init artifact manifest contains missing/decoy fields")
    if artifact_manifest.get("schema") != "a2_cb2h_pro_p2_common_init_v1" or artifact_manifest.get("branch") != "b1":
        raise RuntimeError("P2 common-init artifact source identity drifted")
    if artifact_manifest.get("architecture") != ARCHITECTURES["b1"] or artifact_manifest.get("seed") != 0:
        raise RuntimeError("P2 common-init artifact architecture/seed drifted")
    if artifact_manifest.get("config_sha256") != P2_COMMON_CONFIG_SHA256:
        raise RuntimeError("P2 common-init artifact config SHA drifted")
    if artifact_manifest.get("runtime_identity") != {
        "runtime_repository": str(RUNTIME_REPOSITORY),
        "runtime_commit": EXPECTED_RUNTIME_COMMIT,
    }:
        raise RuntimeError("P2 common-init artifact runtime identity drifted")
    if artifact_manifest.get("common_prefix") != "core." or artifact_manifest.get("common_components") != list(P2_COMMON_INIT_CONTRACT["common_components"]):
        raise RuntimeError("P2 common-init artifact common component contract drifted")
    if artifact_manifest.get("common_core_key_schema_sha256") != P2_COMMON_INIT_CONTRACT["common_key_schema_sha256"]:
        raise RuntimeError("P2 common-init artifact key schema SHA drifted")
    keys = _p2_common_key_schema()
    manifest_keys = artifact_manifest.get("keys")
    step0_identities = step0.get("common_core_key_identities")
    if artifact_manifest.get("key_count") != len(keys) or not isinstance(manifest_keys, list) or manifest_keys != step0_identities:
        raise RuntimeError("P2 common-init artifact ordered identities do not match trusted step0")
    if step0.get("common_core_keys") != list(keys):
        raise RuntimeError("P2 common-init artifact is not bound to the exact 156-key step0 schema")
    expected_aggregate = sha256_bytes(canonical_json(manifest_keys).encode("utf-8"))
    if artifact_manifest.get("aggregate_sha256") != expected_aggregate or step0.get("common_core_sha256") != expected_aggregate:
        raise RuntimeError("P2 common-init artifact aggregate SHA drifted")
    for key in ("rng_before_policy_identity", "rng_downstream_identity"):
        if artifact_manifest.get(key) != step0.get(key):
            raise RuntimeError(f"P2 common-init artifact {key} disagrees with step0")
        require_sha(artifact_manifest.get(key), f"P2 common-init artifact {key}")
    if step0.get("common_init_manifest_sha256") != sha256_bytes(canonical_json(artifact_manifest).encode("utf-8")):
        raise RuntimeError("P2 step0 common-init manifest SHA does not bind the artifact manifest")
    state_dict = payload.get("state_dict")
    if not isinstance(state_dict, Mapping) or list(state_dict) != list(keys):
        raise RuntimeError("P2 common-init artifact state key order drifted")

    def tensor_identity(key: str, tensor: Any) -> dict[str, Any]:
        if not torch.is_tensor(tensor) or tensor.layout != torch.strided or tensor.numel() <= 0:
            raise RuntimeError(f"P2 common-init artifact state {key!r} must be a non-empty strided tensor")
        contiguous = tensor.detach().to(device="cpu").contiguous()
        if not bool(torch.isfinite(contiguous.float()).all().item()):
            raise RuntimeError(f"P2 common-init artifact state {key!r} is non-finite")
        return {
            "key": key,
            "shape": list(contiguous.shape),
            "dtype": str(contiguous.dtype),
            "sha256": sha256_bytes(contiguous.numpy().tobytes(order="C")),
        }

    actual_identities = [tensor_identity(key, state_dict[key]) for key in keys]
    if actual_identities != manifest_keys:
        raise RuntimeError("P2 common-init artifact state does not match its manifest")
    downstream_rng = payload.get("rng_downstream")
    if not isinstance(downstream_rng, Mapping):
        raise RuntimeError("P2 common-init artifact downstream RNG state is missing")
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import rng_state_identity

    if rng_state_identity(downstream_rng) != artifact_manifest.get("rng_downstream_identity"):
        raise RuntimeError("P2 common-init artifact downstream RNG identity drifted")
    if require_sha(step0.get("artifact_sha256"), "P2 step0 artifact SHA") != artifact_sha256:
        raise RuntimeError("P2 step0 artifact SHA is not the trusted immutable artifact")
    return dict(artifact_manifest)


def seal_b1_common_init(common_root: Path) -> dict[str, Any]:
    """Hash-load B1 artifact/step0 and seal the parent trust anchor."""
    artifact = common_root / "b1_common_init.pt"
    step0_path = common_root / "b1_step0_manifest.json"
    artifact_payload, artifact_sha256 = read_immutable_snapshot(artifact)
    step0, step0_sha256, step0_size = load_json_snapshot(step0_path)
    _validate_common_init_artifact_snapshot(
        artifact_payload,
        artifact_sha256=artifact_sha256,
        step0=step0,
    )
    step0 = _validate_step0_manifest_value(
        step0,
        expected_branch="b1",
        artifact_sha256=artifact_sha256,
        expected_artifact_path=artifact,
    )
    seal = {
        "schema": P2_COMMON_SEAL_SCHEMA,
        "source_branch": "b1",
        "artifact": {"path": str(artifact.resolve()), "sha256": artifact_sha256, "size": len(artifact_payload)},
        "step0_manifest": {"path": str(step0_path.resolve()), "sha256": step0_sha256, "size": step0_size},
        "common_core_sha256": step0["common_core_sha256"],
        "common_core_key_schema_sha256": step0["common_core_key_schema_sha256"],
        "common_core_keys": list(step0["common_core_keys"]),
        "common_core_key_identities": list(step0["common_core_key_identities"]),
        "rng_before_policy_identity": step0["rng_before_policy_identity"],
        "rng_downstream_identity": step0["rng_downstream_identity"],
        "seed": step0["seed"],
        "config_sha256": step0["config_sha256"],
        "runtime_identity": dict(step0["runtime_identity"]),
    }
    seal["content_sha256"] = sha256_bytes(canonical_json(seal).encode("utf-8"))
    seal["seal_artifact"] = _atomic_json(common_root / "b1_common_init_seal.json", seal)
    return seal


def _confined_path(value: Any, *, name: str, root: Path) -> Path:
    """Resolve a manifest path and require it to remain under ``root``."""
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"P2 {name} path is missing")
    resolved = Path(value).expanduser().resolve()
    try:
        resolved.relative_to(root.expanduser().resolve())
    except ValueError as exc:
        raise RuntimeError(f"P2 {name} escapes its output root: {resolved}") from exc
    return resolved


def _validate_branch_manifest_snapshot(
    branch: P2Branch,
    *,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    manifest_size: int,
    plan: P2Plan,
    step0: Mapping[str, Any],
    step0_sha256: str,
    expected_artifact_sha256: str,
    expected_runtime: Mapping[str, Any],
    expected_source_step0_sha256: str | None = None,
    expected_command: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Validate one immutable branch-manifest snapshot before sealing the pair."""
    require_sha(manifest_sha256, f"{branch.branch} branch manifest SHA")
    if _strict_int(manifest_size, f"{branch.branch} branch manifest size") <= 0:
        raise RuntimeError(f"P2 {branch.branch} branch manifest size is invalid")
    root = branch.root.expanduser().resolve(strict=True)
    common_root = plan.common_root.expanduser().resolve(strict=True)
    if set(manifest) < {
        "schema",
        "branch",
        "architecture",
        "root",
        "runtime",
        "teacher",
        "command",
        "command_sha256",
        "effective_training_contract",
        "common_init",
        "lifecycle",
        "telemetry",
        "final_checkpoint",
        "final_config",
        "runtime_metrics",
        "content_sha256",
    }:
        raise RuntimeError(f"P2 {branch.branch} branch manifest is incomplete")
    if manifest.get("schema") != P2_BRANCH_SCHEMA or manifest.get("branch") != branch.branch:
        raise RuntimeError(f"P2 {branch.branch} branch manifest identity drifted")
    if manifest.get("architecture") != ARCHITECTURES[branch.branch] or manifest.get("root") != str(root):
        raise RuntimeError(f"P2 {branch.branch} branch manifest architecture/root drifted")
    if manifest.get("teacher") != dict(plan.teacher):
        raise RuntimeError(f"P2 {branch.branch} branch teacher triplet drifted from preflight")
    command = list(expected_command if expected_command is not None else branch.command)
    if manifest.get("command") != command:
        raise RuntimeError(f"P2 {branch.branch} branch command drifted from preflight")
    expected_command_sha256 = sha256_bytes(canonical_json(command).encode("utf-8"))
    if require_sha(manifest.get("command_sha256"), f"P2 {branch.branch} command SHA") != expected_command_sha256:
        raise RuntimeError(f"P2 {branch.branch} branch command SHA drifted")
    content_sha256 = require_sha(manifest.get("content_sha256"), f"{branch.branch} branch manifest content SHA")
    content_without_hash = dict(manifest)
    content_without_hash.pop("content_sha256", None)
    # ``seal_artifact`` is returned by _atomic_json after the bytes are
    # written, so it is not part of the on-disk content hash.  If a producer
    # embeds it, it is still metadata and must not alter the content digest.
    content_without_hash.pop("seal_artifact", None)
    if content_sha256 != sha256_bytes(canonical_json(content_without_hash).encode("utf-8")):
        raise RuntimeError(f"P2 {branch.branch} branch manifest content hash drifted")

    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        raise RuntimeError(f"P2 {branch.branch} branch runtime identity is missing")
    for key in ("repository", "commit"):
        if runtime.get(key) != expected_runtime.get(key):
            raise RuntimeError(f"P2 {branch.branch} branch runtime identity drifted: {key}")
    if runtime.get("repository") != str(RUNTIME_REPOSITORY) or runtime.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError(f"P2 {branch.branch} branch runtime identity is not c18")

    if manifest.get("effective_training_contract") != dict(P2_COMMON_INIT_CONTRACT["effective_training"]):
        raise RuntimeError(f"P2 {branch.branch} branch effective training contract drifted")
    common_init = manifest.get("common_init")
    if not isinstance(common_init, Mapping) or set(common_init) < {"artifact", "step0_manifest", "common_core_sha256"}:
        raise RuntimeError(f"P2 {branch.branch} branch common-init seal is incomplete")
    artifact_ref = common_init.get("artifact")
    if not isinstance(artifact_ref, Mapping):
        raise RuntimeError(f"P2 {branch.branch} common-init artifact ref is malformed")
    artifact_path = _confined_path(artifact_ref.get("path"), name=f"{branch.branch} common-init artifact", root=common_root)
    expected_artifact_path = (common_root / "b1_common_init.pt").resolve()
    if artifact_path != expected_artifact_path:
        raise RuntimeError(f"P2 {branch.branch} common-init artifact path drifted")
    if require_sha(artifact_ref.get("sha256"), f"{branch.branch} common-init artifact SHA") != expected_artifact_sha256:
        raise RuntimeError(f"P2 {branch.branch} common-init artifact SHA drifted")
    artifact_payload, actual_artifact_sha256 = read_immutable_snapshot(artifact_path)
    if actual_artifact_sha256 != expected_artifact_sha256:
        raise RuntimeError(f"P2 {branch.branch} common-init artifact changed after branch seal")
    if artifact_ref.get("size") is not None and _strict_int(artifact_ref["size"], f"{branch.branch} common-init artifact size") != len(artifact_payload):
        raise RuntimeError(f"P2 {branch.branch} common-init artifact size drifted")
    artifact_size = artifact_ref.get("size")
    if artifact_size is not None and _strict_int(artifact_size, f"{branch.branch} common-init artifact size") != len(artifact_payload):
        raise RuntimeError(f"P2 {branch.branch} common-init artifact size drifted")

    step0_ref = common_init.get("step0_manifest")
    if not isinstance(step0_ref, Mapping):
        raise RuntimeError(f"P2 {branch.branch} common-init step0 ref is malformed")
    step0_path = _confined_path(step0_ref.get("path"), name=f"{branch.branch} step0 manifest", root=common_root)
    expected_step0_path = (common_root / f"{branch.branch}_step0_manifest.json").resolve()
    if step0_path != expected_step0_path:
        raise RuntimeError(f"P2 {branch.branch} step0 path drifted")
    if require_sha(step0_ref.get("sha256"), f"{branch.branch} step0 manifest SHA") != step0_sha256:
        raise RuntimeError(f"P2 {branch.branch} step0 manifest SHA drifted")
    step0_payload, actual_step0_sha256 = read_immutable_snapshot(step0_path)
    if actual_step0_sha256 != step0_sha256:
        raise RuntimeError(f"P2 {branch.branch} step0 manifest changed after branch seal")
    try:
        step0_snapshot = json.loads(step0_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"P2 {branch.branch} step0 manifest is not valid JSON") from exc
    if not isinstance(step0_snapshot, Mapping) or dict(step0_snapshot) != dict(step0):
        raise RuntimeError(f"P2 {branch.branch} step0 manifest snapshot drifted")
    if step0_ref.get("size") is not None and _strict_int(step0_ref["size"], f"{branch.branch} step0 manifest size") <= 0:
        raise RuntimeError(f"P2 {branch.branch} step0 manifest size is invalid")
    if common_init.get("common_core_sha256") != step0.get("common_core_sha256"):
        raise RuntimeError(f"P2 {branch.branch} branch common core SHA drifted")
    _validate_common_init_artifact_snapshot(
        artifact_payload,
        artifact_sha256=expected_artifact_sha256,
        step0=step0,
    )

    lifecycle = manifest.get("lifecycle")
    if lifecycle != {
        "natural": False,
        "status": "UNRESOLVED",
        "controlled": True,
        "proof": lifecycle.get("proof") if isinstance(lifecycle, Mapping) else None,
    }:
        if not isinstance(lifecycle, Mapping) or lifecycle.get("natural") is not False or lifecycle.get("status") != "UNRESOLVED" or lifecycle.get("controlled") is not True:
            raise RuntimeError(f"P2 {branch.branch} lifecycle seal drifted")
    proof_ref = lifecycle.get("proof") if isinstance(lifecycle, Mapping) else None
    if not isinstance(proof_ref, Mapping):
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof ref is missing")
    proof_path = _confined_path(proof_ref.get("path"), name=f"{branch.branch} lifecycle proof", root=root)
    if proof_path != (root / "pre_teardown_completion_proof.json").resolve():
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof path drifted")
    proof_sha256 = require_sha(proof_ref.get("sha256"), f"{branch.branch} lifecycle proof SHA")
    proof_payload, actual_proof_sha256 = read_immutable_snapshot(proof_path)
    if proof_sha256 != actual_proof_sha256:
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof changed after branch seal")
    if proof_ref.get("size") is not None and _strict_int(proof_ref["size"], f"{branch.branch} lifecycle proof size") != len(proof_payload):
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof size drifted")
    try:
        proof = json.loads(proof_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof is not valid JSON") from exc
    if not isinstance(proof, Mapping) or proof.get("branch") != branch.branch or proof.get("root") != str(root) or proof.get("lifecycle_status") != "UNRESOLVED" or proof.get("controlled_post_training_exit") is not True:
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof identity drifted")
    proof_content_sha = require_sha(proof.get("manifest_content_sha256"), f"{branch.branch} lifecycle proof content SHA")
    proof_without_hash = dict(proof)
    proof_without_hash.pop("manifest_content_sha256", None)
    if proof_content_sha != sha256_bytes(canonical_json(proof_without_hash).encode("utf-8")):
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof content hash drifted")
    if proof.get("step0_manifest", {}).get("sha256") != step0_sha256 or proof.get("common_init_artifact", {}).get("sha256") != expected_artifact_sha256:
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof common-init refs drifted")

    final_checkpoint = manifest.get("final_checkpoint")
    if not isinstance(final_checkpoint, Mapping):
        raise RuntimeError(f"P2 {branch.branch} final checkpoint ref is missing")
    checkpoint_path = _confined_path(final_checkpoint.get("path"), name=f"{branch.branch} final checkpoint", root=root)
    if checkpoint_path != (root / "model_step_000500.pt").resolve() or final_checkpoint.get("global_step") != EXPECTED_FINAL_GLOBAL_STEP:
        raise RuntimeError(f"P2 {branch.branch} final checkpoint identity drifted")
    checkpoint_sha256 = require_sha(final_checkpoint.get("sha256"), f"{branch.branch} final checkpoint SHA")
    checkpoint_payload, actual_checkpoint_sha256 = read_immutable_snapshot(checkpoint_path)
    if checkpoint_sha256 != actual_checkpoint_sha256:
        raise RuntimeError(f"P2 {branch.branch} final checkpoint changed after branch seal")
    if final_checkpoint.get("size") is not None and _strict_int(final_checkpoint["size"], f"{branch.branch} final checkpoint size") != len(checkpoint_payload):
        raise RuntimeError(f"P2 {branch.branch} final checkpoint size drifted")
    active_parameter_schema = _validate_active_parameter_schema(
        proof.get("active_parameter_schema"),
        step0_optimizer_schema=step0["optimizer_parameter_schema"],
    )
    validated_checkpoint = validate_checkpoint_artifact(
        checkpoint_path,
        step0_manifest=step0,
        active_parameter_schema=active_parameter_schema,
    )

    final_config = manifest.get("final_config")
    if not isinstance(final_config, Mapping):
        raise RuntimeError(f"P2 {branch.branch} final config ref is missing")
    config_path = _confined_path(final_config.get("path"), name=f"{branch.branch} final config", root=root)
    if config_path != (root / "config.yaml").resolve() or final_config.get("branch") != branch.branch or final_config.get("architecture") != ARCHITECTURES[branch.branch]:
        raise RuntimeError(f"P2 {branch.branch} final config identity drifted")
    config_sha256 = require_sha(final_config.get("sha256"), f"{branch.branch} final config SHA")
    config_payload, actual_config_sha256 = read_immutable_snapshot(config_path)
    if config_sha256 != actual_config_sha256:
        raise RuntimeError(f"P2 {branch.branch} final config changed after branch seal")
    if final_config.get("size") is not None and _strict_int(final_config["size"], f"{branch.branch} final config size") != len(config_payload):
        raise RuntimeError(f"P2 {branch.branch} final config size drifted")
    try:
        saved_config = yaml.safe_load(config_payload.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise RuntimeError(f"P2 {branch.branch} final config is not valid YAML") from exc
    if not isinstance(saved_config, Mapping):
        raise RuntimeError(f"P2 {branch.branch} final config must be a mapping")
    validated_config = validate_final_config(
        config_path,
        branch=branch,
        common_root=common_root,
        expected_artifact_sha256=expected_artifact_sha256,
        expected_source_step0_manifest_sha256=expected_source_step0_sha256,
    )
    for key in ("sha256", "size", "architecture", "branch", "common_init", "effective_training_contract"):
        if final_config.get(key) != validated_config.get(key):
            raise RuntimeError(f"P2 {branch.branch} final config ref disagrees with saved config: {key}")
    if proof.get("final_checkpoint", {}).get("sha256") != checkpoint_sha256 or proof.get("final_config", {}).get("sha256") != config_sha256:
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof final refs drifted")

    telemetry_ref = manifest.get("telemetry")
    if not isinstance(telemetry_ref, Mapping) or not isinstance(telemetry_ref.get("artifact"), Mapping) or not isinstance(telemetry_ref.get("validated"), Mapping):
        raise RuntimeError(f"P2 {branch.branch} telemetry seal is incomplete")
    telemetry_artifact = telemetry_ref["artifact"]
    telemetry_path = _confined_path(telemetry_artifact.get("path"), name=f"{branch.branch} telemetry", root=root)
    if telemetry_path != (root / "gpu_telemetry.json").resolve():
        raise RuntimeError(f"P2 {branch.branch} telemetry path drifted")
    telemetry_sha256 = require_sha(telemetry_artifact.get("sha256"), f"{branch.branch} telemetry SHA")
    telemetry_payload, actual_telemetry_sha256 = read_immutable_snapshot(telemetry_path)
    if telemetry_sha256 != actual_telemetry_sha256:
        raise RuntimeError(f"P2 {branch.branch} telemetry changed after branch seal")
    if telemetry_artifact.get("size") is not None and _strict_int(telemetry_artifact["size"], f"{branch.branch} telemetry size") != len(telemetry_payload):
        raise RuntimeError(f"P2 {branch.branch} telemetry size drifted")
    try:
        saved_telemetry = json.loads(telemetry_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"P2 {branch.branch} telemetry artifact is not valid JSON") from exc
    validated_telemetry = validate_gpu_telemetry(saved_telemetry)
    if dict(telemetry_ref["validated"]) != validated_telemetry:
        raise RuntimeError(f"P2 {branch.branch} telemetry validated snapshot drifted")

    metrics_ref = manifest.get("runtime_metrics")
    if not isinstance(metrics_ref, Mapping):
        raise RuntimeError(f"P2 {branch.branch} runtime metrics ref is missing")
    metrics_path = _confined_path(metrics_ref.get("path"), name=f"{branch.branch} runtime metrics", root=root)
    if metrics_path != (root / "runtime_metrics.json").resolve():
        raise RuntimeError(f"P2 {branch.branch} runtime metrics path drifted")
    metrics_sha256 = require_sha(metrics_ref.get("sha256"), f"{branch.branch} runtime metrics SHA")
    metrics, actual_metrics_sha256, _ = load_json_snapshot(metrics_path)
    if metrics_sha256 != actual_metrics_sha256:
        raise RuntimeError(f"P2 {branch.branch} runtime metrics changed after branch seal")
    validated_metrics = _validate_runtime_metrics(
        metrics,
        branch=branch,
        proof=proof,
        checkpoint=validated_checkpoint,
        config=validated_config,
        artifact_sha256=expected_artifact_sha256,
        step0_sha256=step0_sha256,
        telemetry=validated_telemetry,
    )
    if metrics_ref.get("validated") != validated_metrics:
        raise RuntimeError(f"P2 {branch.branch} runtime metrics validated snapshot drifted")

    seal_artifact = manifest.get("seal_artifact")
    if isinstance(seal_artifact, Mapping):
        if seal_artifact.get("path") != str((root / "p2_branch_manifest.json").resolve()) or seal_artifact.get("sha256") != manifest_sha256:
            raise RuntimeError(f"P2 {branch.branch} branch seal artifact identity drifted")
    return dict(manifest)


def validate_pair_and_seal(plan: P2Plan, b1_seal: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(b1_seal, Mapping) or b1_seal.get("schema") != P2_COMMON_SEAL_SCHEMA or b1_seal.get("source_branch") != "b1":
        raise RuntimeError("P2 B1 common-init seal identity/schema drifted")
    if not isinstance(b1_seal.get("artifact"), Mapping) or not isinstance(b1_seal.get("step0_manifest"), Mapping):
        raise RuntimeError("P2 B1 common-init seal refs are incomplete")
    artifact_ref = b1_seal["artifact"]
    if artifact_ref.get("path") != str((plan.common_root / "b1_common_init.pt").resolve()):
        raise RuntimeError("P2 B1 common-init seal artifact path drifted")
    artifact_sha256 = require_sha(artifact_ref.get("sha256"), "P2 B1 common-init seal artifact SHA")
    step0_seal_ref = b1_seal["step0_manifest"]
    if step0_seal_ref.get("path") != str((plan.common_root / "b1_step0_manifest.json").resolve()):
        raise RuntimeError("P2 B1 common-init seal step0 path drifted")
    require_sha(step0_seal_ref.get("sha256"), "P2 B1 common-init seal step0 SHA")
    b1_step0, b1_step0_sha256, b1_step0_size = load_json_snapshot(plan.common_root / "b1_step0_manifest.json")
    b1_step0 = _validate_step0_manifest_value(
        b1_step0,
        expected_branch="b1",
        artifact_sha256=artifact_sha256,
        expected_artifact_path=plan.common_root / "b1_common_init.pt",
    )
    if step0_seal_ref["sha256"] != b1_step0_sha256 or step0_seal_ref.get("size") != b1_step0_size:
        raise RuntimeError("P2 B1 common-init seal step0 snapshot drifted")
    artifact_payload, actual_artifact_sha256 = read_immutable_snapshot(plan.common_root / "b1_common_init.pt")
    if actual_artifact_sha256 != artifact_sha256:
        raise RuntimeError("P2 B1 common-init artifact changed after parent seal")
    _validate_common_init_artifact_snapshot(
        artifact_payload,
        artifact_sha256=artifact_sha256,
        step0=b1_step0,
    )
    b2_step0, b2_step0_sha256, b2_step0_size = load_json_snapshot(plan.common_root / "b2_step0_manifest.json")
    b2_step0 = _validate_step0_manifest_value(
        b2_step0,
        expected_branch="b2",
        artifact_sha256=artifact_sha256,
        expected_artifact_path=plan.common_root / "b1_common_init.pt",
        expected_source=b1_step0,
    )
    if b2_step0["common_core_sha256"] != b1_step0["common_core_sha256"]:
        raise RuntimeError("P2 B1/B2 common core aggregate hash differs")
    branch_manifests = {}
    for branch in plan.branches:
        manifest_path = branch.root / "p2_branch_manifest.json"
        manifest, manifest_sha256, manifest_size = load_json_snapshot(manifest_path)
        expected_branch = branch
        if branch.branch == "b2":
            b2_overrides = build_training_overrides(
                "b2",
                branch.root,
                plan.common_root,
                trusted_artifact_sha256=artifact_sha256,
                trusted_source_step0_manifest_sha256=b1_step0_sha256,
            )
            expected_branch = P2Branch(
                branch="b2",
                root=branch.root,
                overrides=b2_overrides,
                command=_build_branch_command_with_overrides("b2", branch.root, plan.common_root, b2_overrides),
            )
        _validate_branch_manifest_snapshot(
            expected_branch,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            manifest_size=manifest_size,
            plan=plan,
            step0=b1_step0 if branch.branch == "b1" else b2_step0,
            step0_sha256=b1_step0_sha256 if branch.branch == "b1" else b2_step0_sha256,
            expected_artifact_sha256=artifact_sha256,
            expected_runtime={"repository": str(RUNTIME_REPOSITORY), "commit": EXPECTED_RUNTIME_COMMIT},
            expected_source_step0_sha256=b1_step0_sha256 if branch.branch == "b2" else None,
        )
        branch_manifests[branch.branch] = {
            "path": str(manifest_path.resolve()),
            "sha256": manifest_sha256,
            "size": manifest_size,
        }
    pair = {
        "schema": P2_PAIR_SCHEMA,
        "source_branch": "b1",
        "target_branch": "b2",
        "common_init": dict(b1_seal),
        "b1_step0": {"path": str((plan.common_root / "b1_step0_manifest.json").resolve()), "sha256": b1_step0_sha256, "size": b1_step0_size},
        "b2_step0": {"path": str((plan.common_root / "b2_step0_manifest.json").resolve()), "sha256": b2_step0_sha256, "size": b2_step0_size},
        "core_aggregate_sha256": b1_step0["common_core_sha256"],
        "core_key_schema_sha256": b1_step0["common_core_key_schema_sha256"],
        "ordered_core_keys": list(b1_step0["common_core_keys"]),
        "ordered_core_key_identities": list(b1_step0["common_core_key_identities"]),
        "artifact_sha256": artifact_sha256,
        "downstream_rng_identity": b1_step0["rng_downstream_identity"],
        "runtime_identity": dict(b1_step0["runtime_identity"]),
        "seed": b1_step0["seed"],
        "config_sha256": b1_step0["config_sha256"],
        "branch_manifests": branch_manifests,
    }
    pair["content_sha256"] = sha256_bytes(canonical_json(pair).encode("utf-8"))
    pair["seal_artifact"] = _atomic_json(plan.serial_root / "pair_manifest.json", pair)
    return pair


def _strict_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"P2 {name} must be an integer; got {value!r}")
    return value


def _strict_finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"P2 {name} must be finite numeric; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"P2 {name} must be finite; got {value!r}")
    return result


def _mapping_path(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            raise RuntimeError(f"P2 final config is missing {'/'.join(keys)}")
        current = current[key]
    return current


def _resolve_config_path(value: Any, *, config: Mapping[str, Any], branch_root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise TypeError("P2 final config path must be a non-empty string")
    experiment_dir = config.get("experiment_dir")
    if not isinstance(experiment_dir, str) or not experiment_dir:
        experiment_dir = str(branch_root)
    resolved = value.replace("${experiment_dir}", experiment_dir)
    return Path(resolved).expanduser().resolve()


def validate_final_config(
    path: Path,
    *,
    branch: P2Branch,
    common_root: Path,
    expected_artifact_sha256: str,
    expected_source_step0_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate the actual saved YAML, not the launch-time constants."""
    payload, config_sha256 = read_immutable_snapshot(path)
    config = yaml.safe_load(payload.decode("utf-8"))
    if not isinstance(config, Mapping):
        raise RuntimeError("P2 final config must decode to a mapping")
    algo = _mapping_path(config, "algo")
    trl = _mapping_path(algo, "trl")
    effective = _mapping_path(algo, "config")
    callbacks = _mapping_path(config, "callbacks", "model_save")
    exact = {
        "num_envs": _strict_int(config.get("num_envs"), "config.num_envs"),
        "num_total_batches": _strict_int(trl.get("num_total_batches"), "algo.trl.num_total_batches"),
        "num_steps_per_env": _strict_int(effective.get("num_steps_per_env"), "algo.config.num_steps_per_env"),
        "num_mini_batches": _strict_int(effective.get("num_mini_batches"), "algo.config.num_mini_batches"),
        "num_ppo_epochs": _strict_int(trl.get("num_ppo_epochs"), "algo.trl.num_ppo_epochs"),
        "gradient_accumulation_steps": _strict_int(trl.get("gradient_accumulation_steps"), "algo.trl.gradient_accumulation_steps"),
        "actor_learning_rate": _strict_finite_number(effective.get("actor_learning_rate"), "algo.config.actor_learning_rate"),
        "ratio_teacher_rollout": _strict_finite_number(effective.get("ratio_teacher_rollout"), "algo.config.ratio_teacher_rollout"),
        "enforce_teacher_rollout": effective.get("enforce_teacher_rollout"),
        "gamma": _strict_finite_number(effective.get("gamma"), "algo.config.gamma"),
        "lam": _strict_finite_number(effective.get("lam"), "algo.config.lam"),
        "desired_kl": _strict_finite_number(effective.get("desired_kl"), "algo.config.desired_kl"),
        "init_at_random_ep_len": effective.get("init_at_random_ep_len"),
        "use_obj_pred": effective.get("use_obj_pred"),
        "obj_pred_loss_coef": _strict_finite_number(effective.get("obj_pred_loss_coef"), "algo.config.obj_pred_loss_coef"),
        "checkpoint": config.get("checkpoint"),
        "checkpoint_load_mode": config.get("checkpoint_load_mode"),
        "auto_load_latest": config.get("auto_load_latest"),
    }
    expected_effective = P2_COMMON_INIT_CONTRACT["effective_training"]
    for key, expected in expected_effective.items():
        actual = exact[key]
        if isinstance(expected, float):
            if not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-12):
                raise RuntimeError(f"P2 saved config effective {key} drifted: {actual!r}")
        elif actual != expected:
            raise RuntimeError(f"P2 saved config effective {key} drifted: {actual!r}")
    if callbacks.get("save_frequency") != EXPECTED_BATCHES:
        raise RuntimeError("P2 saved config callbacks.model_save.save_frequency drifted")
    if config.get("headless") is not True or config.get("auto_load_latest") is not False:
        raise RuntimeError("P2 saved config headless/auto-load contract drifted")
    common = _mapping_path(effective, "p2_common_init")
    if common.get("enabled") is not True or common.get("branch") != branch.branch:
        raise RuntimeError("P2 saved config common-init branch/enabled contract drifted")
    if common.get("mode") != ("create" if branch.branch == "b1" else "load"):
        raise RuntimeError("P2 saved config common-init mode drifted")
    if common.get("architecture") != ARCHITECTURES[branch.branch]:
        raise RuntimeError("P2 saved config common-init architecture drifted")
    if common.get("seed") != 0 or common.get("config_sha256") != P2_COMMON_CONFIG_SHA256:
        raise RuntimeError("P2 saved config common-init seed/config drifted")
    expected_common_artifact = (common_root / "b1_common_init.pt").resolve()
    expected_step0 = (common_root / f"{branch.branch}_step0_manifest.json").resolve()
    expected_source_step0 = (common_root / "b1_step0_manifest.json").resolve()
    if _resolve_config_path(common.get("artifact_path"), config=config, branch_root=branch.root) != expected_common_artifact:
        raise RuntimeError("P2 saved config common-init artifact path drifted")
    if _resolve_config_path(common.get("step0_manifest_path"), config=config, branch_root=branch.root) != expected_step0:
        raise RuntimeError("P2 saved config common-init step0 path drifted")
    if _resolve_config_path(common.get("source_step0_manifest_path"), config=config, branch_root=branch.root) != expected_source_step0:
        raise RuntimeError("P2 saved config common-init source step0 path drifted")
    runtime_identity = common.get("runtime_identity")
    if runtime_identity != {"runtime_repository": str(RUNTIME_REPOSITORY), "runtime_commit": EXPECTED_RUNTIME_COMMIT}:
        raise RuntimeError("P2 saved config runtime identity drifted")
    if branch.branch == "b2" and common.get("trusted_artifact_sha256") != expected_artifact_sha256:
        raise RuntimeError("P2 saved config B2 trusted artifact SHA drifted")
    if branch.branch == "b2":
        source_step0_sha256 = common.get("trusted_source_step0_manifest_sha256")
        require_sha(source_step0_sha256, "P2 saved config B2 trusted source step0 SHA")
        if expected_source_step0_manifest_sha256 is not None and source_step0_sha256 != expected_source_step0_manifest_sha256:
            raise RuntimeError("P2 saved config B2 trusted source step0 SHA drifted")
    lifecycle = _mapping_path(effective, "p2_lifecycle")
    if lifecycle.get("enabled") is not True or lifecycle.get("target_global_step") != EXPECTED_BATCHES:
        raise RuntimeError("P2 saved config lifecycle contract drifted")
    cameras = _mapping_path(config, "simulator", "config", "cameras")
    if cameras.get("architecture_id") != ARCHITECTURES[branch.branch]:
        raise RuntimeError("P2 saved config camera architecture drifted")
    if _mapping_path(cameras, "policy_multiview", "architecture_id") != ARCHITECTURES[branch.branch]:
        raise RuntimeError("P2 saved config multiview architecture drifted")
    actor = _mapping_path(effective, "actor")
    actor_target = actor.get("_target_", "")
    expected_actor_name = "DualD435VisionRecurrentActor" if branch.branch == "b1" else "DualD435HeadVisionRecurrentActor"
    if not isinstance(actor_target, str) or not actor_target.endswith(expected_actor_name):
        raise RuntimeError("P2 saved config actor architecture drifted")
    context_obs = _mapping_path(config, "obs", "obs_dict")
    if branch.branch == "b1":
        if "context_vision_obs" in context_obs or "head_vision_module" in _mapping_path(actor, "backbone"):
            raise RuntimeError("P2 saved B1 config contains Head/context inputs")
    elif "context_vision_obs" not in context_obs or "head_vision_module" not in _mapping_path(actor, "backbone"):
        raise RuntimeError("P2 saved B2 config lacks Head/context inputs")
    return {
        "path": str(path.expanduser().resolve()),
        "sha256": config_sha256,
        "size": len(payload),
        "architecture": ARCHITECTURES[branch.branch],
        "branch": branch.branch,
        "common_init": dict(common),
        "effective_training_contract": exact,
    }


def _validate_finite_tensors(value: Any, *, name: str, torch_module: Any) -> int:
    if torch_module.is_tensor(value):
        if (torch_module.is_floating_point(value) or torch_module.is_complex(value)) and not bool(torch_module.isfinite(value).all().item()):
            raise RuntimeError(f"P2 checkpoint contains non-finite tensor: {name}")
        return 1
    if isinstance(value, Mapping):
        return sum(_validate_finite_tensors(child, name=f"{name}.{key}", torch_module=torch_module) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return sum(_validate_finite_tensors(child, name=f"{name}[{index}]", torch_module=torch_module) for index, child in enumerate(value))
    return 0


def _validate_checkpoint_state_mapping(value: Any, *, name: str, schema: Mapping[str, Any], torch_module: Any) -> int:
    if not isinstance(value, Mapping) or not value:
        raise RuntimeError(f"P2 checkpoint {name} must be a non-empty mapping")
    expected_keys = schema.get("keys")
    if not isinstance(expected_keys, list) or list(value) != expected_keys:
        raise RuntimeError(f"P2 checkpoint {name} key schema does not match step0")
    identities = schema.get("identities")
    if not isinstance(identities, list) or len(identities) != len(expected_keys):
        raise RuntimeError(f"P2 checkpoint {name} step0 schema is malformed")
    for index, (key, identity) in enumerate(zip(expected_keys, identities, strict=True)):
        tensor = value.get(key)
        if not torch_module.is_tensor(tensor) or tensor.layout != torch_module.strided or tensor.numel() <= 0:
            raise RuntimeError(f"P2 checkpoint {name}.{key} must be a non-empty tensor")
        if list(tensor.shape) != identity.get("shape") or str(tensor.dtype) != identity.get("dtype"):
            raise RuntimeError(f"P2 checkpoint {name}.{key} shape/dtype disagrees with step0")
        if (torch_module.is_floating_point(tensor) or torch_module.is_complex(tensor)) and not bool(torch_module.isfinite(tensor).all().item()):
            raise RuntimeError(f"P2 checkpoint {name}.{key} is non-finite")
        require_sha(identity.get("sha256"), f"P2 step0 {name} tensor {index} SHA")
    return len(expected_keys)


def _validate_optimizer_state_dict(
    value: Any,
    *,
    step0_optimizer_schema: Mapping[str, Any],
    active_parameter_schema: Mapping[str, Any],
    torch_module: Any,
) -> int:
    if not isinstance(value, Mapping) or set(value) != {"state", "param_groups"}:
        raise RuntimeError("P2 optimizer_state_dict must contain exactly state and param_groups")
    states = value["state"]
    groups = value["param_groups"]
    if not isinstance(states, Mapping) or not states:
        raise RuntimeError("P2 optimizer state must be non-empty")
    if not isinstance(groups, list) or len(groups) != 2:
        raise RuntimeError("P2 optimizer param_groups must contain exactly two AdamW groups")
    _validate_p2_optimizer_schema(step0_optimizer_schema, {
        "schema": P2_SCHEDULER_SCHEMA,
        "scheduler_class": "torch.optim.lr_scheduler.LambdaLR",
        "state_dict": {
            "base_lrs": [EXPECTED_ACTOR_LEARNING_RATE] * len(groups),
            "last_epoch": 0,
            "_step_count": 1,
            "_get_lr_called_within_step": False,
            "_last_lr": [EXPECTED_ACTOR_LEARNING_RATE] * len(groups),
            "lr_lambdas": [None] * len(groups),
        },
    })
    expected_groups = step0_optimizer_schema["param_groups"]
    parameter_ids: list[int] = []
    allowed_group_fields = {
        "params", "lr", "betas", "eps", "weight_decay", "amsgrad", "maximize",
        "foreach", "capturable", "differentiable", "fused", "decoupled_weight_decay", "initial_lr",
    }
    amsgrad_ids: set[int] = set()
    for group_index, group in enumerate(groups):
        if not isinstance(group, Mapping) or set(group) != allowed_group_fields:
            raise RuntimeError(f"P2 optimizer param_group {group_index} is malformed or contains decoys")
        params = group["params"]
        if not isinstance(params, list) or not params or any(
            isinstance(param_id, bool) or not isinstance(param_id, int) for param_id in params
        ):
            raise RuntimeError(f"P2 optimizer param_group {group_index} params are invalid")
        if params != expected_groups[group_index]["parameter_ids"]:
            raise RuntimeError(f"P2 optimizer param_group {group_index} parameter IDs/order drifted")
        parameter_ids.extend(params)
        expected_hyperparameters = expected_groups[group_index]["hyperparameters"]
        actual_hyperparameters = {key: group[key] for key in allowed_group_fields if key != "params"}
        if _p2_normalize_optimizer_value(actual_hyperparameters) != _p2_normalize_optimizer_value(expected_hyperparameters):
            raise RuntimeError(f"P2 optimizer param_group {group_index} hyperparameters drifted")
        if group["lr"] <= 0.0 or group["eps"] <= 0.0 or group["weight_decay"] < 0.0:
            raise RuntimeError(f"P2 optimizer param_group {group_index} has invalid LR/eps/weight decay")
        if group["initial_lr"] <= 0.0 or group["initial_lr"] != group["lr"]:
            raise RuntimeError(f"P2 optimizer param_group {group_index} initial_lr is invalid")
        if not isinstance(group["betas"], (list, tuple)) or len(group["betas"]) != 2 or any(
            not math.isfinite(float(beta)) or not 0.0 <= float(beta) < 1.0 for beta in group["betas"]
        ):
            raise RuntimeError(f"P2 optimizer param_group {group_index}.betas is invalid")
        for field in ("amsgrad", "maximize", "capturable", "differentiable", "decoupled_weight_decay"):
            if not isinstance(group[field], bool):
                raise RuntimeError(f"P2 optimizer param_group {group_index}.{field} must be boolean")
        for field in ("foreach", "fused"):
            if group[field] is not None and not isinstance(group[field], bool):
                raise RuntimeError(f"P2 optimizer param_group {group_index}.{field} must be null or boolean")
        if group["amsgrad"] is True:
            amsgrad_ids.update(params)
    if len(set(parameter_ids)) != len(parameter_ids):
        raise RuntimeError("P2 optimizer parameter IDs must not repeat")
    expected_parameter_ids = {item["id"] for item in step0_optimizer_schema["ordered_parameters"]}
    if set(parameter_ids) != expected_parameter_ids:
        raise RuntimeError("P2 optimizer param_groups do not cover the full step0 parameter schema")
    active = _validate_active_parameter_schema(
        active_parameter_schema,
        step0_optimizer_schema=step0_optimizer_schema,
    )
    active_ids = active["parameter_ids"]
    if set(states) != set(active_ids):
        raise RuntimeError(
            "P2 optimizer state parameter IDs do not exactly match the observed active-gradient set"
        )
    parameter_schema_by_id = {item["id"]: item for item in step0_optimizer_schema["ordered_parameters"]}
    allowed_state_fields = {"step", "exp_avg", "exp_avg_sq", "max_exp_avg_sq"}
    for parameter_id, state in states.items():
        if isinstance(parameter_id, bool) or not isinstance(parameter_id, int) or parameter_id not in parameter_schema_by_id:
            raise RuntimeError(f"P2 optimizer state parameter ID {parameter_id!r} is not trusted")
        if not isinstance(state, Mapping) or not state or not set(state).issubset(allowed_state_fields):
            raise RuntimeError(f"P2 optimizer state entry {parameter_id!r} is not Adam-shaped")
        if not {"step", "exp_avg", "exp_avg_sq"}.issubset(set(state)):
            raise RuntimeError(f"P2 optimizer state entry {parameter_id!r} lacks Adam moments")
        for field, item in state.items():
            if torch_module.is_tensor(item):
                if item.layout != torch_module.strided or item.numel() <= 0:
                    raise RuntimeError(f"P2 optimizer state {parameter_id!r}.{field} is empty/non-strided")
                if (torch_module.is_floating_point(item) or torch_module.is_complex(item)) and not bool(torch_module.isfinite(item).all().item()):
                    raise RuntimeError(f"P2 optimizer state {parameter_id!r}.{field} is non-finite")
            elif isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
                raise RuntimeError(f"P2 optimizer state {parameter_id!r}.{field} is not a finite scalar/tensor")
        if not torch_module.is_tensor(state["step"]) or not torch_module.is_floating_point(state["step"]):
            raise RuntimeError(f"P2 optimizer state {parameter_id!r}.step must be a floating scalar tensor")
        if state["step"].numel() != 1:
            raise RuntimeError(f"P2 optimizer state {parameter_id!r}.step must be scalar")
        step = state["step"].item() if torch_module.is_tensor(state["step"]) else state["step"]
        if isinstance(step, bool) or not isinstance(step, (int, float)) or not math.isfinite(float(step)) or float(step) != EXPECTED_OPTIMIZER_STATE_STEP:
            raise RuntimeError(f"P2 optimizer state entry {parameter_id!r}.step must equal {EXPECTED_OPTIMIZER_STATE_STEP}")
        moments = (state["exp_avg"], state["exp_avg_sq"])
        if not all(torch_module.is_tensor(moment) for moment in moments):
            raise RuntimeError(f"P2 optimizer state {parameter_id!r} Adam moments must be tensors")
        if any(moment.shape != moments[0].shape for moment in moments[1:]):
            raise RuntimeError(f"P2 optimizer state {parameter_id!r} Adam moments disagree in shape")
        expected_parameter = parameter_schema_by_id[parameter_id]
        expected_shape = tuple(expected_parameter["shape"])
        expected_dtype = expected_parameter["dtype"]
        for field, moment in (("exp_avg", state["exp_avg"]), ("exp_avg_sq", state["exp_avg_sq"])):
            if tuple(moment.shape) != expected_shape or str(moment.dtype) != expected_dtype:
                raise RuntimeError(f"P2 optimizer state {parameter_id!r}.{field} shape/dtype does not bind its parameter")
        if parameter_id in amsgrad_ids and "max_exp_avg_sq" not in state:
            raise RuntimeError(f"P2 optimizer state {parameter_id!r} is missing required AMSGrad moment")
        if "max_exp_avg_sq" in state:
            if parameter_id not in amsgrad_ids or not torch_module.is_tensor(state["max_exp_avg_sq"]):
                raise RuntimeError(f"P2 optimizer state {parameter_id!r} contains an unexpected AMSGrad moment")
            if tuple(state["max_exp_avg_sq"].shape) != expected_shape or str(state["max_exp_avg_sq"].dtype) != expected_dtype:
                raise RuntimeError(f"P2 optimizer state {parameter_id!r} max moment disagrees with its parameter")
    return len(states)


def _validate_active_parameter_schema(
    value: Any,
    *,
    step0_optimizer_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the hook-observed lazy Adam state membership."""
    if not isinstance(value, Mapping) or set(value) != {
        "schema", "parameter_count", "ordered_parameters", "parameter_ids", "parameter_names", "schema_sha256"
    }:
        raise RuntimeError("P2 active-parameter schema is missing or contains decoys")
    if value.get("schema") != "a2_cb2h_pro_p2_active_parameter_schema_v1":
        raise RuntimeError("P2 active-parameter schema identity drifted")
    ordered = value.get("ordered_parameters")
    if not isinstance(ordered, list) or not ordered:
        raise RuntimeError("P2 active-parameter schema must contain a non-empty observed subset")
    if value.get("parameter_count") != len(ordered):
        raise RuntimeError("P2 active-parameter count disagrees with ordered entries")
    full = step0_optimizer_schema.get("ordered_parameters")
    if not isinstance(full, list):
        raise RuntimeError("P2 step0 optimizer schema lacks ordered parameters")
    full_by_name = {item["name"]: item for item in full}
    full_names = [item["name"] for item in full]
    active_ids = []
    active_names = []
    last_index = -1
    for index, item in enumerate(ordered):
        if not isinstance(item, Mapping) or set(item) != {"id", "name", "shape", "dtype"}:
            raise RuntimeError(f"P2 active parameter {index} is malformed")
        name = item.get("name")
        if name not in full_by_name:
            raise RuntimeError(f"P2 active parameter {name!r} is not in the trusted optimizer schema")
        if item != {
            "id": full_by_name[name]["id"],
            "name": name,
            "shape": full_by_name[name]["shape"],
            "dtype": full_by_name[name]["dtype"],
        }:
            raise RuntimeError(f"P2 active parameter {name!r} does not bind its trusted shape/dtype/ID")
        current_index = full_names.index(name)
        if current_index <= last_index:
            raise RuntimeError("P2 active parameter order must preserve the trainer's ordered parameter schema")
        last_index = current_index
        if name.startswith("value_model.") or name == "policy.core.std":
            raise RuntimeError(f"P2 BC-only active set contains an unused parameter: {name!r}")
        active_ids.append(item["id"])
        active_names.append(name)
    if len(set(active_ids)) != len(active_ids) or len(set(active_names)) != len(active_names):
        raise RuntimeError("P2 active parameter schema contains duplicates")
    expected = _expected_p2_bc_active_parameters(step0_optimizer_schema)
    if ordered != expected:
        raise RuntimeError(
            "P2 active parameter schema must equal the exact trusted BC-active sequence"
        )
    if value.get("parameter_ids") != active_ids or value.get("parameter_names") != active_names:
        raise RuntimeError("P2 active parameter ID/name projections drifted")
    expected_sha = sha256_bytes(canonical_json(ordered).encode("utf-8"))
    if require_sha(value.get("schema_sha256"), "P2 active parameter schema SHA") != expected_sha:
        raise RuntimeError("P2 active parameter schema digest drifted")
    return dict(value)


def _expected_p2_bc_active_parameters(step0_optimizer_schema: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Derive the exact BC-active sequence from the cross-bound optimizer schema."""
    full = step0_optimizer_schema.get("ordered_parameters")
    if not isinstance(full, list) or not full:
        raise RuntimeError("P2 step0 optimizer schema lacks ordered parameters")
    policy_parameters = [
        item for item in full
        if isinstance(item, Mapping) and isinstance(item.get("name"), str) and item["name"].startswith("policy.")
    ]
    std_parameters = [item for item in policy_parameters if item["name"] == "policy.core.std"]
    if len(std_parameters) != 1:
        raise RuntimeError("P2 trusted policy schema must contain exactly one policy.core.std parameter")
    if not any(
        isinstance(item, Mapping) and isinstance(item.get("name"), str) and item["name"].startswith("value_model.")
        for item in full
    ):
        raise RuntimeError("P2 trusted optimizer schema must contain value_model parameters")
    expected = [item for item in policy_parameters if item["name"] != "policy.core.std"]
    if not expected:
        raise RuntimeError("P2 trusted BC-active sequence must not be empty")
    return [dict(item) for item in expected]


def validate_checkpoint_artifact(
    path: Path,
    *,
    step0_manifest: Mapping[str, Any] | None = None,
    active_parameter_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Single-read CPU checkpoint validation for the final saved artifact."""
    import torch

    payload_bytes, checkpoint_sha256 = read_immutable_snapshot(path)
    try:
        checkpoint = torch.load(io.BytesIO(payload_bytes), map_location="cpu", weights_only=False)
    except Exception as exc:
        raise RuntimeError("P2 final checkpoint is not a valid torch checkpoint") from exc
    if not isinstance(checkpoint, Mapping):
        raise RuntimeError("P2 final checkpoint must decode to a mapping")
    required = ("policy_state_dict", "value_state_dict", "optimizer_state_dict", "lr_scheduler_state_dict", "state")
    missing = [key for key in required if key not in checkpoint]
    if missing:
        raise RuntimeError(f"P2 final checkpoint is missing required fields: {missing}")
    if step0_manifest is None:
        raise RuntimeError("P2 final checkpoint validation requires the finalized step0 model schemas")
    if active_parameter_schema is None:
        raise RuntimeError("P2 final checkpoint validation requires the hook-observed active parameter schema")
    policy_schema = _validate_state_schema(step0_manifest.get("policy_state_schema"), name="step0.policy_state_schema")
    value_schema = _validate_state_schema(step0_manifest.get("value_state_schema"), name="step0.value_state_schema")
    policy_count = _validate_checkpoint_state_mapping(
        checkpoint["policy_state_dict"], name="policy_state_dict", schema=policy_schema, torch_module=torch
    )
    value_count = _validate_checkpoint_state_mapping(
        checkpoint["value_state_dict"], name="value_state_dict", schema=value_schema, torch_module=torch
    )
    optimizer_count = _validate_optimizer_state_dict(
        checkpoint["optimizer_state_dict"],
        step0_optimizer_schema=step0_manifest["optimizer_parameter_schema"],
        active_parameter_schema=active_parameter_schema,
        torch_module=torch,
    )
    scheduler_state = checkpoint["lr_scheduler_state_dict"]
    if not isinstance(scheduler_state, Mapping) or set(scheduler_state) != {
        "base_lrs", "last_epoch", "_step_count", "_get_lr_called_within_step", "_last_lr", "lr_lambdas"
    }:
        raise RuntimeError("P2 final constant scheduler state schema drifted")
    group_count = len(step0_manifest["optimizer_parameter_schema"]["param_groups"])
    expected_lrs = [EXPECTED_ACTOR_LEARNING_RATE] * group_count
    if scheduler_state.get("base_lrs") != expected_lrs or scheduler_state.get("_last_lr") != expected_lrs:
        raise RuntimeError("P2 final constant scheduler learning rates drifted")
    if isinstance(scheduler_state.get("last_epoch"), bool) or not isinstance(scheduler_state.get("last_epoch"), int) or scheduler_state.get("last_epoch") != EXPECTED_FINAL_GLOBAL_STEP or isinstance(scheduler_state.get("_step_count"), bool) or not isinstance(scheduler_state.get("_step_count"), int) or scheduler_state.get("_step_count") != EXPECTED_FINAL_GLOBAL_STEP + 1:
        raise RuntimeError("P2 final constant scheduler step state drifted")
    if scheduler_state.get("_get_lr_called_within_step") is not False or scheduler_state.get("lr_lambdas") != [None] * group_count:
        raise RuntimeError("P2 final constant scheduler state contains decoys")
    state = checkpoint["state"]
    global_step = state.get("global_step") if isinstance(state, Mapping) else getattr(state, "global_step", None)
    if _strict_int(global_step, "checkpoint.state.global_step") != EXPECTED_FINAL_GLOBAL_STEP:
        raise RuntimeError(f"P2 final checkpoint global_step drifted: {global_step!r}")
    tensor_count = _validate_finite_tensors(checkpoint, name="checkpoint", torch_module=torch)
    if tensor_count <= 0:
        raise RuntimeError("P2 final checkpoint contains no tensor payload")
    return {
        "path": str(path.expanduser().resolve()),
        "sha256": checkpoint_sha256,
        "size": len(payload_bytes),
        "global_step": global_step,
        "tensor_count": tensor_count,
        "policy_key_count": policy_count,
        "value_key_count": value_count,
        "optimizer_state_count": optimizer_count,
        "active_parameter_count": active_parameter_schema["parameter_count"],
    }


def validate_gpu_telemetry(telemetry: Mapping[str, Any]) -> dict[str, Any]:
    expected_top_level = {
        "schema",
        "record_count",
        "records",
        "peak_vram_mib",
        "process_started_ns",
        "process_ended_ns",
        "sample_interval_s",
        "max_adjacent_gap_s",
        "gpu_identity",
    }
    if not isinstance(telemetry, Mapping) or set(telemetry) != expected_top_level:
        raise RuntimeError("P2 telemetry top-level schema drifted")
    if telemetry.get("schema") != "a2_cb2h_pro_p2_gpu_telemetry_v1":
        raise RuntimeError("P2 telemetry schema drifted")
    if not isinstance(telemetry.get("sample_interval_s"), float) or not isinstance(telemetry.get("max_adjacent_gap_s"), float):
        raise RuntimeError("P2 telemetry cadence metadata must be floating-point values")
    sample_interval_s = _strict_finite_number(telemetry.get("sample_interval_s"), "telemetry.sample_interval_s")
    max_adjacent_gap_s = _strict_finite_number(telemetry.get("max_adjacent_gap_s"), "telemetry.max_adjacent_gap_s")
    if not math.isclose(sample_interval_s, P2_TELEMETRY_SAMPLE_INTERVAL_S, rel_tol=0.0, abs_tol=1.0e-12):
        raise RuntimeError("P2 telemetry sampler cadence drifted")
    if not math.isclose(max_adjacent_gap_s, P2_TELEMETRY_MAX_ADJACENT_GAP_S, rel_tol=0.0, abs_tol=1.0e-12):
        raise RuntimeError("P2 telemetry maximum adjacent gap drifted")
    records = telemetry.get("records")
    if not isinstance(records, list) or len(records) < 2:
        raise RuntimeError("P2 telemetry requires at least two records")
    if isinstance(telemetry.get("record_count"), bool) or not isinstance(telemetry.get("record_count"), int) or telemetry.get("record_count") != len(records):
        raise RuntimeError("P2 telemetry record_count disagrees with records")
    process_started_ns = _strict_int(telemetry.get("process_started_ns"), "telemetry.process_started_ns")
    process_ended_ns = _strict_int(telemetry.get("process_ended_ns"), "telemetry.process_ended_ns")
    if process_started_ns <= 0 or process_ended_ns <= process_started_ns:
        raise RuntimeError("P2 telemetry process interval is invalid")
    identity = telemetry.get("gpu_identity")
    expected_identity = {
        "physical_gpu_index": EXPECTED_GPU_INDEX,
        "logical_gpu_index": int(EXPECTED_LOGICAL_GPU_INDEX),
        "logical_device": "cuda:0",
        "uuid": EXPECTED_GPU_UUID,
        "cuda_visible_devices": EXPECTED_GPU_INDEX,
        "cuda_device_order": EXPECTED_CUDA_DEVICE_ORDER,
        "binding_mode": EXPECTED_GPU_BINDING_MODE,
        "world_size": 1,
    }
    if not isinstance(identity, Mapping) or dict(identity) != expected_identity:
        raise RuntimeError("P2 telemetry GPU identity drifted")
    peaks = []
    timestamps = []
    expected_record_fields = {
        "physical_gpu_index", "logical_gpu_index", "logical_device", "uuid",
        "cuda_visible_devices", "cuda_device_order", "binding_mode", "world_size",
        "memory_used_mib", "memory_total_mib", "utilization_gpu_pct", "power_draw_w",
        "temperature_c", "sample_time_ns",
    }
    for index, record in enumerate(records):
        if not isinstance(record, Mapping) or set(record) != expected_record_fields or any(record.get(key) != expected_identity[key] for key in expected_identity):
            raise RuntimeError(f"P2 telemetry record {index} GPU identity drifted")
        memory = _strict_finite_number(record.get("memory_used_mib"), f"telemetry.records[{index}].memory_used_mib")
        total_memory = _strict_finite_number(record.get("memory_total_mib"), f"telemetry.records[{index}].memory_total_mib")
        if memory < 0.0 or memory >= VRAM_LIMIT_MIB or total_memory <= 0.0 or memory > total_memory:
            raise RuntimeError(f"P2 telemetry record {index} exceeds VRAM limit")
        utilization = _strict_finite_number(record.get("utilization_gpu_pct"), f"telemetry.records[{index}].utilization_gpu_pct")
        power = _strict_finite_number(record.get("power_draw_w"), f"telemetry.records[{index}].power_draw_w")
        temperature = _strict_finite_number(record.get("temperature_c"), f"telemetry.records[{index}].temperature_c")
        if not 0.0 <= utilization <= 100.0 or power < 0.0 or not 0.0 <= temperature <= 150.0:
            raise RuntimeError(f"P2 telemetry record {index} is outside physical bounds")
        sample_time_ns = _strict_int(record.get("sample_time_ns"), f"telemetry.records[{index}].sample_time_ns")
        if sample_time_ns <= 0:
            raise RuntimeError(f"P2 telemetry record {index} timestamp is invalid")
        peaks.append(memory)
        timestamps.append(sample_time_ns)
    if any(after <= before for before, after in zip(timestamps, timestamps[1:])):
        raise RuntimeError("P2 telemetry sample timestamps must be strictly increasing")
    adjacent_gaps_s = [(after - before) / 1.0e9 for before, after in zip(timestamps, timestamps[1:])]
    effective_max_adjacent_gap_s = min(max_adjacent_gap_s, 2.0 * sample_interval_s)
    if any(gap <= 0.0 or gap >= effective_max_adjacent_gap_s for gap in adjacent_gaps_s):
        raise RuntimeError("P2 telemetry contains an interior cadence gap beyond the sealed cadence/bound")
    if timestamps[0] > process_started_ns or timestamps[-1] < process_ended_ns:
        raise RuntimeError("P2 telemetry records do not bracket the child process interval")
    process_duration_s = (process_ended_ns - process_started_ns) / 1.0e9
    # n records provide n-1 strictly bounded intervals.  Since the first and
    # last records bracket the child interval, duration < (n-1)*effective_max
    # is required; the integer lower bound is therefore floor(duration/max)+2.
    minimum_record_count = max(
        2,
        math.floor(process_duration_s / effective_max_adjacent_gap_s) + 2,
    )
    if len(records) < minimum_record_count:
        raise RuntimeError("P2 telemetry record count is inconsistent with the process duration/cadence")
    peak = _strict_finite_number(telemetry.get("peak_vram_mib"), "telemetry.peak_vram_mib")
    if peak != max(peaks) or peak >= VRAM_LIMIT_MIB:
        raise RuntimeError("P2 telemetry peak does not match finite records")
    return dict(telemetry)


def _validate_runtime_metrics(
    metrics: Mapping[str, Any],
    *,
    branch: P2Branch,
    proof: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    config: Mapping[str, Any],
    artifact_sha256: str,
    step0_sha256: str,
    telemetry: Mapping[str, Any],
) -> dict[str, Any]:
    if metrics.get("schema") != P2_RUNTIME_METRICS_SCHEMA or metrics.get("branch") != branch.branch or metrics.get("training_performed") is not True:
        raise RuntimeError(f"P2 {branch.branch} runtime metrics identity/schema drifted")
    declared = metrics.get("content_sha256")
    if not isinstance(declared, str):
        raise RuntimeError(f"P2 {branch.branch} runtime metrics content hash is missing or malformed")
    require_sha(declared, f"{branch.branch} runtime metrics content_sha256")
    without = dict(metrics)
    without.pop("content_sha256")
    if declared != sha256_bytes(canonical_json(without).encode("utf-8")):
        raise RuntimeError(f"P2 {branch.branch} runtime metrics content hash drifted")
    expected = {
        "global_step_start": 0,
        "global_step_final": EXPECTED_FINAL_GLOBAL_STEP,
        "completed_iterations": EXPECTED_BATCHES,
        "callbacks": EXPECTED_BATCHES,
        "callback_step_end_count": EXPECTED_BATCHES,
        "callback_max_steps": EXPECTED_BATCHES,
        "backward_calls": EXPECTED_BATCHES * EXPECTED_NUM_MINI_BATCHES,
        "optimizer_steps": EXPECTED_BATCHES * EXPECTED_NUM_MINI_BATCHES,
        "backward_call_count": EXPECTED_BATCHES * EXPECTED_NUM_MINI_BATCHES,
        "optimizer_step_count": EXPECTED_BATCHES * EXPECTED_NUM_MINI_BATCHES,
        "scheduler_step_count": EXPECTED_BATCHES,
        "scheduler_step_count_before": 1,
        "scheduler_step_count_after": 501,
        "scheduler_last_epoch_before": 0,
        "scheduler_last_epoch_after": 500,
    }
    for key, value in expected.items():
        if metrics.get(key) != value:
            raise RuntimeError(f"P2 {branch.branch} runtime metric {key} drifted")
    scheduler = metrics.get("scheduler")
    if scheduler != {"step_count": 501, "last_epoch": 500}:
        raise RuntimeError(f"P2 {branch.branch} runtime scheduler evidence drifted")
    if metrics.get("observed_global_steps") != list(range(1, EXPECTED_BATCHES + 1)):
        raise RuntimeError(f"P2 {branch.branch} runtime global-step progression drifted")
    if metrics.get("runtime") != proof.get("runtime") or metrics.get("runtime") != {"runtime_repository": str(RUNTIME_REPOSITORY), "runtime_commit": EXPECTED_RUNTIME_COMMIT}:
        raise RuntimeError(f"P2 {branch.branch} runtime identity drifted")
    if metrics.get("lifecycle") != {"natural": False, "status": "UNRESOLVED", "controlled": True}:
        raise RuntimeError(f"P2 {branch.branch} runtime lifecycle status drifted")
    peak = _strict_finite_number(metrics.get("peak_vram_mib"), f"{branch.branch} runtime peak_vram_mib")
    if peak != telemetry.get("peak_vram_mib"):
        raise RuntimeError(f"P2 {branch.branch} runtime peak does not match validated telemetry")
    if metrics.get("final_checkpoint") != proof.get("final_checkpoint") or metrics.get("final_config") != proof.get("final_config"):
        raise RuntimeError(f"P2 {branch.branch} runtime final artifact refs drifted")
    if metrics.get("common_init") != proof.get("common_init_artifact") or metrics.get("step0_manifest") != proof.get("step0_manifest"):
        raise RuntimeError(f"P2 {branch.branch} runtime common-init paths/refs drifted")
    if metrics.get("common_init", {}).get("sha256") != artifact_sha256 or metrics.get("step0_manifest", {}).get("sha256") != step0_sha256:
        raise RuntimeError(f"P2 {branch.branch} runtime common-init refs drifted")
    if metrics.get("active_parameter_schema") != proof.get("active_parameter_schema"):
        raise RuntimeError(f"P2 {branch.branch} runtime active-parameter schema drifted")
    if checkpoint.get("sha256") != proof.get("final_checkpoint", {}).get("sha256") or config.get("sha256") != proof.get("final_config", {}).get("sha256"):
        raise RuntimeError(f"P2 {branch.branch} runtime artifacts disagree with proof")
    return dict(metrics)


def validate_branch_evidence(
    branch: P2Branch,
    *,
    telemetry: Mapping[str, Any],
    expected_artifact_sha256: str | None = None,
    expected_source_step0_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    root = branch.root.expanduser().resolve(strict=True)
    proof, proof_sha256, proof_size = load_json_snapshot(root / "pre_teardown_completion_proof.json")
    metrics, metrics_sha256, metrics_size = load_json_snapshot(root / "runtime_metrics.json")
    proof_content_sha = require_sha(proof.get("manifest_content_sha256"), f"{branch.branch} lifecycle proof content_sha256")
    proof_without_sha = dict(proof)
    proof_without_sha.pop("manifest_content_sha256", None)
    if proof_content_sha != sha256_bytes(canonical_json(proof_without_sha).encode("utf-8")):
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof content hash drifted")
    if proof.get("schema") != "a2_cb2h_pro_p2_pre_teardown_completion_v1" or proof.get("operation") != "p2_pre_teardown_completion" or proof.get("root") != str(root) or proof.get("branch") != branch.branch or proof.get("proof_stage") != "PRE_TEARDOWN":
        raise RuntimeError(f"P2 {branch.branch} lifecycle proof identity/schema drifted")
    if proof.get("natural_kit_lifecycle_pass") is not False or proof.get("lifecycle_status") != "UNRESOLVED" or proof.get("controlled_post_training_exit") is not True:
        raise RuntimeError(f"P2 {branch.branch} lifecycle status is not controlled/unresolved")
    expected_counts = {
        "start_global_step": 0,
        "target_global_step": EXPECTED_BATCHES,
        "expected_additional_iterations": EXPECTED_BATCHES,
        "completed_iterations": EXPECTED_BATCHES,
        "callback_step_end_count": EXPECTED_BATCHES,
        "backward_call_count": EXPECTED_BATCHES * EXPECTED_NUM_MINI_BATCHES,
        "optimizer_step_count": EXPECTED_BATCHES * EXPECTED_NUM_MINI_BATCHES,
        "scheduler_step_count": EXPECTED_BATCHES,
        "scheduler_step_count_before": 1,
        "scheduler_step_count_after": 501,
        "scheduler_last_epoch_before": 0,
        "scheduler_last_epoch_after": 500,
    }
    for key, expected in expected_counts.items():
        if proof.get(key) != expected:
            raise RuntimeError(f"P2 {branch.branch} lifecycle {key} drifted: {proof.get(key)!r}")
    if proof.get("callback_train_begin_seen") is not True or proof.get("callback_max_steps") != EXPECTED_BATCHES:
        raise RuntimeError(f"P2 {branch.branch} callback lifecycle proof drifted")
    if proof.get("observed_global_steps") != list(range(1, EXPECTED_BATCHES + 1)):
        raise RuntimeError(f"P2 {branch.branch} callback global-step progression drifted")
    runtime = proof.get("runtime")
    if runtime != {"runtime_repository": str(RUNTIME_REPOSITORY), "runtime_commit": EXPECTED_RUNTIME_COMMIT}:
        raise RuntimeError(f"P2 {branch.branch} proof runtime identity drifted")
    final_checkpoint = root / "model_step_000500.pt"
    final_config = root / "config.yaml"
    if proof.get("final_checkpoint", {}).get("path") != str(final_checkpoint) or proof.get("final_config", {}).get("path") != str(final_config):
        raise RuntimeError(f"P2 {branch.branch} final artifact paths drifted")
    common_artifact_ref = proof.get("common_init_artifact")
    step0_ref = proof.get("step0_manifest")
    if not isinstance(common_artifact_ref, Mapping) or not isinstance(step0_ref, Mapping):
        raise RuntimeError(f"P2 {branch.branch} proof common-init refs are missing")
    expected_common_root = (root.parent / "common_init").resolve()
    expected_artifact_path = (expected_common_root / "b1_common_init.pt").resolve()
    expected_step0_path = (expected_common_root / f"{branch.branch}_step0_manifest.json").resolve()
    artifact_path = Path(common_artifact_ref["path"]).expanduser().resolve(strict=True)
    step0_path = Path(step0_ref["path"]).expanduser().resolve(strict=True)
    if artifact_path != expected_artifact_path or step0_path != expected_step0_path:
        raise RuntimeError(f"P2 {branch.branch} common-init proof paths are not the trusted output paths")
    artifact_bytes, artifact_sha256 = read_immutable_snapshot(artifact_path)
    if expected_artifact_sha256 is not None and artifact_sha256 != expected_artifact_sha256:
        raise RuntimeError(f"P2 {branch.branch} common-init artifact is not the trusted parent snapshot")
    step0, step0_sha256, step0_size = load_json_snapshot(step0_path)
    if common_artifact_ref.get("sha256") != artifact_sha256 or step0_ref.get("sha256") != step0_sha256:
        raise RuntimeError(f"P2 {branch.branch} common-init artifact changed after proof")
    _validate_common_init_artifact_snapshot(
        artifact_bytes,
        artifact_sha256=artifact_sha256,
        step0=step0,
    )
    _validate_step0_manifest_value(
        step0,
        expected_branch=branch.branch,
        artifact_sha256=artifact_sha256,
        expected_artifact_path=expected_artifact_path,
    )
    active_parameter_schema = _validate_active_parameter_schema(
        proof.get("active_parameter_schema"),
        step0_optimizer_schema=step0["optimizer_parameter_schema"],
    )
    checkpoint = validate_checkpoint_artifact(
        final_checkpoint,
        step0_manifest=step0,
        active_parameter_schema=active_parameter_schema,
    )
    config = validate_final_config(
        final_config,
        branch=branch,
        common_root=Path(proof.get("common_init_artifact", {}).get("path", "")).expanduser().resolve(strict=True).parent,
        expected_artifact_sha256=artifact_sha256,
        expected_source_step0_manifest_sha256=expected_source_step0_manifest_sha256,
    )
    if proof.get("final_checkpoint", {}).get("sha256") != checkpoint["sha256"] or proof.get("final_config", {}).get("sha256") != config["sha256"]:
        raise RuntimeError(f"P2 {branch.branch} proof final artifact hashes drifted")
    if artifact_sha256 != config["common_init"].get("trusted_artifact_sha256") and branch.branch == "b2":
        raise RuntimeError(f"P2 {branch.branch} config common-init trust SHA disagrees with artifact")
    validated_telemetry = validate_gpu_telemetry(telemetry)
    validated_metrics = _validate_runtime_metrics(
        metrics,
        branch=branch,
        proof=proof,
        checkpoint=checkpoint,
        config=config,
        artifact_sha256=artifact_sha256,
        step0_sha256=step0_sha256,
        telemetry=validated_telemetry,
    )
    return {
        "proof": proof,
        "proof_sha256": proof_sha256,
        "proof_size": proof_size,
        "metrics": validated_metrics,
        "metrics_sha256": metrics_sha256,
        "metrics_size": metrics_size,
        "telemetry": validated_telemetry,
        "checkpoint": checkpoint,
        "config": config,
        "step0": step0,
        "common_artifact_sha256": artifact_sha256,
        "common_artifact_size": len(artifact_bytes),
        "step0_sha256": step0_sha256,
        "step0_size": step0_size,
    }


def seal_branch_manifest(
    branch: P2Branch,
    *,
    runtime: Mapping[str, Any],
    teacher: Mapping[str, Any],
    telemetry: Mapping[str, Any],
    telemetry_artifact: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    root = branch.root.expanduser().resolve(strict=True)
    proof = evidence["proof"]
    validated_checkpoint = evidence["checkpoint"]
    validated_config = evidence["config"]
    manifest = {
        "schema": P2_BRANCH_SCHEMA,
        "branch": branch.branch,
        "architecture": validated_config["architecture"],
        "root": str(root),
        "runtime": dict(runtime),
        "teacher": dict(teacher),
        "command": list(branch.command),
        "command_sha256": sha256_bytes(canonical_json(list(branch.command)).encode("utf-8")),
        "effective_training_contract": dict(validated_config["effective_training_contract"]),
        "common_init": {
            "artifact": {
                **dict(proof["common_init_artifact"]),
                "size": evidence["common_artifact_size"],
            },
            "step0_manifest": {
                **dict(proof["step0_manifest"]),
                "size": evidence["step0_size"],
            },
            "common_core_sha256": _validate_step0_manifest_value(
                evidence["step0"],
                expected_branch=branch.branch,
                artifact_sha256=evidence["common_artifact_sha256"],
                expected_artifact_path=root.parent / "common_init" / "b1_common_init.pt",
            )["common_core_sha256"],
        },
        "lifecycle": {
            "natural": False,
            "status": "UNRESOLVED",
            "controlled": True,
            "proof": {
                "path": str(root / "pre_teardown_completion_proof.json"),
                "sha256": evidence["proof_sha256"],
                "size": evidence["proof_size"],
            },
        },
        "telemetry": {"artifact": dict(telemetry_artifact), "validated": dict(evidence["telemetry"])},
        "final_checkpoint": dict(validated_checkpoint),
        "final_config": dict(validated_config),
        "runtime_metrics": {
            "path": str(root / "runtime_metrics.json"),
            "sha256": evidence["metrics_sha256"],
            "size": evidence["metrics_size"],
            "validated": dict(evidence["metrics"]),
        },
    }
    manifest["content_sha256"] = sha256_bytes(canonical_json(manifest).encode("utf-8"))
    manifest["seal_artifact"] = _atomic_json(root / "p2_branch_manifest.json", manifest)
    return manifest


def _inject_runtime_peak_metric(path: Path, peak_vram_mib: float) -> dict[str, Any]:
    metrics, _, _ = load_json_snapshot(path)
    metrics = dict(metrics)
    metrics["peak_vram_mib"] = peak_vram_mib
    metrics.pop("content_sha256", None)
    metrics["content_sha256"] = sha256_bytes(canonical_json(metrics).encode("utf-8"))
    return _atomic_json(path, metrics)


def _execute_plan(plan: P2Plan) -> int:
    if not BOOTSTRAP_SCRIPT.is_file():
        raise FileNotFoundError(f"P2 v19 bootstrap is unavailable: {BOOTSTRAP_SCRIPT}")
    overlay = validate_overlay_repository(REPO_ROOT)
    runtime = validate_runtime_repository(RUNTIME_REPOSITORY)
    if runtime["commit"] != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError("P2 c18 runtime commit is not the sealed commit")
    validate_teacher_triplet()
    plan.serial_root.mkdir(parents=True, exist_ok=False)
    _atomic_json(plan.serial_root / "plan.json", plan.as_dict())
    b1_seal = None
    for branch in plan.branches:
        if branch.root.exists():
            raise FileExistsError(f"P2 branch root must be fresh: {branch.root}")
        if branch.branch == "b2":
            if b1_seal is None:
                raise RuntimeError("P2 B2 cannot execute before the B1 seal")
            overrides = build_training_overrides(
                "b2",
                branch.root,
                plan.common_root,
                trusted_artifact_sha256=b1_seal["artifact"]["sha256"],
                trusted_source_step0_manifest_sha256=b1_seal["step0_manifest"]["sha256"],
            )
            branch = P2Branch(
                branch="b2",
                root=branch.root,
                overrides=overrides,
                command=_build_branch_command_with_overrides(
                    "b2",
                    branch.root,
                    plan.common_root,
                    overrides,
                ),
            )
        environment = build_child_environment()
        sampler = GpuTelemetrySampler(environment)
        sampler.sample_once()
        process_started_ns = time.time_ns()
        sampler.start()
        try:
            completed = subprocess.run(branch.command, check=False, env=environment, cwd=str(overlay))
            process_ended_ns = time.time_ns()
            telemetry = sampler.stop(
                process_started_ns=process_started_ns,
                process_ended_ns=process_ended_ns,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"P2 {branch.branch} child returned rc={completed.returncode}")
            _inject_runtime_peak_metric(branch.root / "runtime_metrics.json", telemetry["peak_vram_mib"])
            evidence = validate_branch_evidence(
                branch,
                telemetry=telemetry,
                expected_artifact_sha256=(b1_seal["artifact"]["sha256"] if branch.branch == "b2" else None),
                expected_source_step0_manifest_sha256=(
                    b1_seal["step0_manifest"]["sha256"] if branch.branch == "b2" else None
                ),
            )
            telemetry_artifact = _atomic_json(branch.root / "gpu_telemetry.json", telemetry)
            _atomic_json(branch.root / "branch_runtime_evidence.json", evidence)
            seal_branch_manifest(
                branch,
                runtime=runtime,
                teacher=plan.teacher,
                telemetry=telemetry,
                telemetry_artifact=telemetry_artifact,
                evidence=evidence,
            )
        except BaseException as exc:
            if sampler._thread is not None and sampler._thread.is_alive():
                sampler.stop(
                    process_started_ns=process_started_ns,
                    process_ended_ns=time.time_ns(),
                )
            branch.root.mkdir(parents=True, exist_ok=True)
            failure = branch.root / "failure.json"
            if not failure.exists():
                _atomic_json(
                    failure,
                    {
                        "schema": P2_FAILURE_SCHEMA,
                        "branch": branch.branch,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "retry_requires_new_root": True,
                        "fallback": False,
                    },
                )
            raise
        if branch.branch == "b1":
            b1_seal = seal_b1_common_init(plan.common_root)
            _atomic_json(plan.serial_root / "b1_seal.json", b1_seal)
    if b1_seal is None:
        raise RuntimeError("P2 B1 seal was not produced")
    validate_pair_and_seal(plan, b1_seal)
    return 0


def _override_value(overrides: Sequence[str], key: str) -> str:
    matches = []
    for argument in overrides:
        normalized = argument[1:] if argument.startswith("+") else argument
        if normalized.startswith(f"{key}="):
            matches.append(normalized.split("=", 1)[1])
    if len(matches) != 1:
        raise RuntimeError(f"P2 branch requires exactly one override {key}; got {matches!r}")
    return matches[0]


def _execute_branch_impl(args: argparse.Namespace) -> int:
    """Execute one explicit P2 branch; the 10k bootstrap main is never called."""
    if args.branch not in BRANCHES:
        raise ValueError(f"P2 branch must be b1/b2; got {args.branch!r}")
    branch_root = args.branch_root.expanduser().resolve()
    common_root = args.common_root.expanduser().resolve()
    if branch_root.exists():
        raise FileExistsError(f"P2 branch root must be fresh: {branch_root}")
    overrides = tuple(args.hydra_overrides)
    trusted_artifact = _override_value(
        overrides,
        "algo.config.p2_common_init.trusted_artifact_sha256",
    )
    trusted_step0 = _override_value(
        overrides,
        "algo.config.p2_common_init.trusted_source_step0_manifest_sha256",
    )
    expected_overrides = build_training_overrides(
        args.branch,
        branch_root,
        common_root,
        trusted_artifact_sha256=trusted_artifact,
        trusted_source_step0_manifest_sha256=trusted_step0,
    )
    if overrides != expected_overrides:
        raise RuntimeError("P2 branch Hydra overrides differ from the exact generated contract")
    composed = compose_training_config(overrides)
    validate_composed_config(composed, args.branch)
    environment = build_child_environment()
    if not BOOTSTRAP_SCRIPT.is_file():
        raise FileNotFoundError(f"P2 v19 bootstrap library is unavailable: {BOOTSTRAP_SCRIPT}")

    # Import the sealed v19 bootstrap only as a library.  Its 10k-only main
    # remains unreachable; P2 owns this explicit 500-batch branch entrypoint.
    from gr00t.rl.scripts import run_a2_student_distillation_v19 as bootstrap

    preloaded = sorted(set(bootstrap.V19_RUNTIME_MODULES).intersection(sys.modules))
    if preloaded:
        raise RuntimeError(f"P2 runtime task modules were preimported: {preloaded}")
    overlay = bootstrap.prepare_overlay_import(args.overlay_repository)
    module_sources = bootstrap.validate_runtime_repository(args.runtime_repository)
    bootstrap.validate_gpu7_environment(environment)
    bootstrap.validate_teacher_triplet(
        args.teacher_actor_path,
        args.teacher_config_path,
        args.teacher_manifest_path,
    )
    preloaded = sorted(set(module_sources).intersection(sys.modules))
    if preloaded:
        raise RuntimeError(f"P2 runtime task modules were imported before V19 finder install: {preloaded}")
    bootstrap.install_v19_runtime_scenario_file_pin(module_sources)
    sys.meta_path.insert(0, bootstrap.V19RuntimeFinder(module_sources))
    train_entrypoint = overlay / "gr00t/rl/train_agent_trl.py"
    if not train_entrypoint.is_file():
        raise FileNotFoundError(f"P2 branch training entrypoint is unavailable: {train_entrypoint}")
    os.environ.clear()
    os.environ.update(environment)
    os.chdir(overlay)
    sys.argv = [str(train_entrypoint), *overrides]
    runpy.run_path(str(train_entrypoint), run_name="__main__")
    proof_path = branch_root / "pre_teardown_completion_proof.json"
    if not proof_path.is_file():
        raise RuntimeError("P2 branch returned without a pre-teardown completion proof")
    raise RuntimeError("P2 controlled branch returned instead of exiting after proof seal")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--execute-branch", action="store_true")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--runtime-repository", type=Path)
    parser.add_argument("--overlay-repository", type=Path)
    parser.add_argument("--teacher-actor-path", type=Path)
    parser.add_argument("--teacher-config-path", type=Path)
    parser.add_argument("--teacher-manifest-path", type=Path)
    parser.add_argument("--branch", choices=BRANCHES)
    parser.add_argument("--branch-root", type=Path)
    parser.add_argument("--common-root", type=Path)
    args, remaining = parser.parse_known_args(argv)
    if args.execute_branch:
        required = (
            args.runtime_repository,
            args.overlay_repository,
            args.teacher_actor_path,
            args.teacher_config_path,
            args.teacher_manifest_path,
            args.branch,
            args.branch_root,
            args.common_root,
        )
        if any(value is None for value in required) or args.dry_run or args.execute:
            raise ValueError("P2 --execute-branch requires runtime/overlay/Teacher/branch/root arguments only")
        if remaining[:1] == ["--"]:
            remaining = remaining[1:]
        if not remaining:
            raise ValueError("P2 --execute-branch requires exact Hydra overrides after --")
        args.hydra_overrides = tuple(remaining)
        return args
    if remaining:
        raise ValueError(f"unexpected P2 launcher arguments: {remaining!r}")
    if args.output_root is None:
        raise ValueError("P2 --dry-run/--execute requires --output-root")
    if args.dry_run == args.execute:
        raise ValueError("select exactly one of --dry-run or --execute")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.execute_branch:
        return _execute_branch_impl(args)
    plan = build_plan(args.output_root)
    if args.dry_run:
        print(canonical_json(plan.as_dict()), flush=True)
        return 0
    return _execute_plan(plan)


if __name__ == "__main__":
    raise SystemExit(main())
