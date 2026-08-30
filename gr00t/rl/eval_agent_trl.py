# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


# Copyright 2025 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Evaluation script for trained RL agents (teacher or student).

Loads a checkpoint and its associated training config, sets up the environment
and model, optionally exports the policy as ONNX, then runs evaluation episodes.

Usage:
    python groot/rl/eval_agent_trl.py +checkpoint=<path_to_checkpoint.pt> [+num_envs=1]
"""

import hashlib
import json
import logging
import os
import subprocess
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

import hydra
import yaml
from hydra.core.hydra_config import HydraConfig
from hydra.utils import instantiate
from loguru import logger
from omegaconf import OmegaConf

from gr00t.rl.utils.config_utils import register_rl_resolvers

register_rl_resolvers()


_A2_STAGE2_LEGACY_CONTACT_FORCE_KEY = "a2_stage2_single_finger_contact_force_threshold"
_A2_STAGE2_GRASP_REWARD_CONFIG_DEFAULTS = {
    "a2_stage2_squeeze_force_min": 0.5,
    "a2_stage2_squeeze_force_max": 20.0,
    "a2_stage2_over_force_threshold": 40.0,
}
_A2_STAGE2_GRASP_REWARD_CONFIG_KEYS = (
    "a2_stage2_contact_force_threshold",
    *_A2_STAGE2_GRASP_REWARD_CONFIG_DEFAULTS.keys(),
)
_A2_STAGE3_TO4_DOOR_HINGE_THRESHOLD_KEY = "a2_stage3_to4_door_hinge_threshold"
_A2_STAGE3_TO4_DOOR_HINGE_THRESHOLD_LEGACY_DEFAULT = 0.174533
_A2_STAGE3_BASE_UNLOCKED_KEY = "a2_stage3_base_unlocked"
_A2_STAGE3_BASE_UNLOCKED_LEGACY_DEFAULT = False
_A2_HOLD_DIAGNOSTIC_ENV_CONFIG_DEFAULTS = {
    "a2_gripper_source_tcp_offset_z": 0.085,
    "a2_hold_diagnostic_contact_detail_enabled": False,
    "a2_hold_diagnostic_max_contact_data_count_per_prim": 8,
    "a2_hold_diagnostic_friction_override": None,
}
_A2_BASE_API_TRAINER_TARGET = (
    "gr00t.rl.trl.trainer.ppo_trainer_a2_base_api.TRLPPOTrainer"
)
_CHECKPOINT_LOAD_MODES = frozenset(("full", "policy_only"))
_R2_REQUIRED_PROVENANCE_FIELDS = frozenset(
    {
        "run_uuid",
        "scientific_plan_id",
        "admission_plan_id",
        "source_lock_sha256",
        "plan_sha256",
        "r1_plan_sha256",
        "b0_json_sha256",
        "b0_csv_sha256",
        "urdf_path",
        "urdf_sha256",
        "checkpoint_path",
        "checkpoint_sha256",
        "checkpoint_step",
        "source_config_path",
        "source_config_sha256",
        "resolved_config_sha256",
        "runtime_config_sha256",
        "command_sha256",
        "git_commit",
        "seed",
    }
)
_R2_RUNTIME_CONFIG_SHA_PLACEHOLDER = "0" * 64
_R2_WORKFLOW_TOP_LEVEL_OVERRIDES = (
    "checkpoint",
    "num_envs",
    "seed",
    "headless",
    "r2_evidence_enabled",
    "r2_bound_config_path",
    "r2_bound_config_sha256",
    "r2_resolved_config_sha256",
    "r2_command_sha256",
    "r2_m22_entry_id",
    "r2_selected_checkpoint_step",
    "r2_forced",
)
_R2_WORKFLOW_ENV_OVERRIDES = (
    "env.config.a2_v20_R2_trace_root",
    "env.config.a2_v20_R2_record_set_staging_path",
    "env.config.a2_v20_R2_provenance",
    "env.config.a2_v20_R2_group",
)


def _validate_r2_runtime_bindings(config, *, require_formal_bundle=False):
    """Revalidate workflow-owned source/formal bindings at the eval boundary."""
    source_lock_path = config.get("r2_source_lock_path")
    if not isinstance(source_lock_path, str) or not source_lock_path:
        raise ValueError("R2 evaluation requires r2_source_lock_path from the active workflow.")
    source_lock = Path(source_lock_path)
    if not source_lock.is_absolute():
        source_lock = Path.cwd() / source_lock
    if source_lock.is_symlink() or not source_lock.is_file():
        raise ValueError(f"R2 active source lock is not a regular file: {source_lock}")
    try:
        lock = json.loads(source_lock.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("R2 active source lock is not valid JSON") from exc
    # ACTIVE_SOURCE_LOCK.json wraps the frozen source lock under "source_lock";
    # unwrap so the binding validates the actual SOURCE_FROZEN lock P0 adjudicated.
    if isinstance(lock, dict) and lock.get("schema") == "a2_piper_base_v20_R2_active_source_lock_v1":
        lock = lock.get("source_lock")
    if not isinstance(lock, dict) or lock.get("schema") != "a2_piper_base_v20_R2_source_lock_v1" or lock.get("producer_state") != "SOURCE_FROZEN":
        raise ValueError("R2 evaluation requires a SOURCE_FROZEN active source lock.")
    git = lock.get("git")
    if not isinstance(git, dict) or not isinstance(git.get("commit"), str) or not isinstance(git.get("tree"), str):
        raise ValueError("R2 source lock is missing commit/tree identity.")
    try:
        current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        current_tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("R2 evaluation cannot resolve current git identity") from exc
    if (git["commit"], git["tree"]) != (current_commit, current_tree):
        raise ValueError("R2 active source lock does not match current commit/tree.")
    lock_sha = hashlib.sha256(source_lock.read_bytes()).hexdigest()
    env_config = config.get("env", {}).get("config", {})
    declared_lock_sha = env_config.get("a2_v20_R2_source_lock_sha256")
    if declared_lock_sha not in (None, lock_sha):
        raise ValueError("R2 env source-lock hash does not match active source lock.")
    real_flag = config.get("r2_real_execution", True)
    if not isinstance(real_flag, bool) or not real_flag:
        raise ValueError("R2 evaluation requires r2_real_execution=true.")
    formal_path = config.get("r2_formal_bundle_path") or config.get("r2_admission_bundle_path")
    declared_formal_sha = env_config.get("a2_v20_R2_admission_bundle_sha256")
    if require_formal_bundle or declared_formal_sha not in (None, ""):
        if not isinstance(formal_path, str) or not formal_path:
            raise ValueError("R2 evaluation requires a formal/admission bundle path.")
        bundle = Path(formal_path)
        if not bundle.is_absolute():
            bundle = Path.cwd() / bundle
        if bundle.is_symlink() or not bundle.is_file():
            raise ValueError(f"R2 formal/admission bundle is not a regular file: {bundle}")
        bundle_sha = hashlib.sha256(bundle.read_bytes()).hexdigest()
        if declared_formal_sha not in (None, "", bundle_sha):
            raise ValueError("R2 formal/admission bundle hash mismatch.")
    return {"source_lock_path": str(source_lock), "source_lock_sha256": lock_sha, "git_commit": current_commit, "git_tree": current_tree}


def validate_r2_eval_config(config):
    if config.get("scientific_plan_id") != "base_v20_R1_policy_behavior_v1":
        raise ValueError("R2 evaluation config scientific_plan_id mismatch")
    if config.get("admission_plan_id") != "base_v20_R2_admission_execution_v1":
        raise ValueError("R2 evaluation config admission_plan_id mismatch")
    if not bool(config.get("r2_evidence_enabled", False)):
        raise ValueError("R2 evaluation requires r2_evidence_enabled=true")
    _complete_r2_eval_provenance(config)
    return True


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_regular_file(value, *, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path string")
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is not a regular file: {path}")
    return path


def _load_r2_bound_config(override_config):
    bound_path = override_config.get("r2_bound_config_path", None)
    if bound_path is None:
        return None
    config_path = _resolve_regular_file(bound_path, label="R2 bound config")
    actual_sha = _sha256_file(config_path)
    expected_sha = override_config.get("r2_bound_config_sha256", None)
    if expected_sha not in (None, actual_sha):
        raise ValueError("R2 bound config hash does not match the workflow command binding")
    logger.info(f"Loading workflow-bound R2 config file from {config_path}")
    return OmegaConf.load(config_path)


def _apply_r2_workflow_overrides(config, override_config) -> None:
    for key in _R2_WORKFLOW_TOP_LEVEL_OVERRIDES:
        value = override_config.get(key, None)
        if value is not None:
            OmegaConf.update(config, key, value, force_add=True)
    for key in _R2_WORKFLOW_ENV_OVERRIDES:
        value = OmegaConf.select(override_config, key)
        if value is not None:
            OmegaConf.update(config, key, value, force_add=True)


def _canonical_config_sha256(config) -> str:
    payload = OmegaConf.to_container(config, resolve=True)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _r2_provenance_container(config) -> dict:
    provenance = OmegaConf.select(config, "env.config.a2_v20_R2_provenance")
    payload = OmegaConf.to_container(provenance, resolve=True) if provenance is not None else None
    if not isinstance(payload, Mapping):
        raise ValueError("R2 evaluation requires env.config.a2_v20_R2_provenance from the workflow command")
    return dict(payload)


def _complete_r2_eval_provenance(config) -> None:
    runtime_identity = _validate_r2_runtime_bindings(config)
    provenance = _r2_provenance_container(config)
    command_sha = config.get("r2_command_sha256", None)
    if not isinstance(command_sha, str) or not command_sha:
        raise ValueError("R2 evaluation requires r2_command_sha256 from the workflow command")
    entry_id = config.get("r2_m22_entry_id", None)
    if isinstance(entry_id, str) and entry_id:
        provenance["run_uuid"] = f"m22-{entry_id}"
    resolved_sha = config.get("r2_resolved_config_sha256", None)
    if isinstance(resolved_sha, str) and resolved_sha:
        provenance["resolved_config_sha256"] = resolved_sha
    provenance["source_lock_sha256"] = runtime_identity["source_lock_sha256"]
    provenance["git_commit"] = runtime_identity["git_commit"]
    provenance["command_sha256"] = command_sha
    provenance["runtime_config_sha256"] = _R2_RUNTIME_CONFIG_SHA_PLACEHOLDER
    OmegaConf.update(config, "env.config.a2_v20_R2_source_lock_sha256", runtime_identity["source_lock_sha256"], force_add=True)
    OmegaConf.update(config, "env.config.a2_v20_R2_provenance", provenance, force_add=True)
    provenance["runtime_config_sha256"] = _canonical_config_sha256(config)
    missing = sorted(_R2_REQUIRED_PROVENANCE_FIELDS - set(provenance))
    if missing:
        raise ValueError(f"R2 evaluation provenance is missing required fields: {missing}")
    OmegaConf.update(config, "env.config.a2_v20_R2_provenance", provenance, force_add=True)


def _validate_eval_seed(seed):
    """Require the eval seed to be an actual integer rather than a bool or coercion."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError(f"Evaluation config seed must be an integer, got {seed!r}")
    return int(seed)


def _validate_checkpoint_load_mode(checkpoint_load_mode, context):
    if not isinstance(checkpoint_load_mode, str) or checkpoint_load_mode not in (
        _CHECKPOINT_LOAD_MODES
    ):
        raise ValueError(
            f"{context} checkpoint_load_mode must be exactly one of "
            f"{sorted(_CHECKPOINT_LOAD_MODES)}; got {checkpoint_load_mode!r}."
        )
    return checkpoint_load_mode

def _normalize_eval_checkpoint_load_mode(config):
    requested_mode = _validate_checkpoint_load_mode(
        config.checkpoint_load_mode,
        "Evaluation runtime",
    )
    p06_policy_only = OmegaConf.select(
        config,
        "algo.config.eval.a2_v23_p06_policy_only",
        default=False,
    )
    if not isinstance(p06_policy_only, bool):
        raise ValueError(
            "algo.config.eval.a2_v23_p06_policy_only must be bool; "
            f"got {p06_policy_only!r}."
        )
    v26_5_policy_only_residual = OmegaConf.select(
        config,
        "algo.config.eval.a2_v26_5_policy_only_residual",
        default=False,
    )
    if not isinstance(v26_5_policy_only_residual, bool):
        raise ValueError(
            "algo.config.eval.a2_v26_5_policy_only_residual must be bool; "
            f"got {v26_5_policy_only_residual!r}."
        )
    v26_5_policy_only_identity_control = OmegaConf.select(
        config,
        "algo.config.eval.a2_v26_5_policy_only_identity_control",
        default=False,
    )
    if not isinstance(v26_5_policy_only_identity_control, bool):
        raise ValueError(
            "algo.config.eval.a2_v26_5_policy_only_identity_control must be bool; "
            f"got {v26_5_policy_only_identity_control!r}."
        )
    if sum(
        (
            p06_policy_only,
            v26_5_policy_only_residual,
            v26_5_policy_only_identity_control,
        )
    ) > 1:
        raise ValueError(
            "Evaluation must select at most one policy-only compatibility contract."
        )
    if (
        p06_policy_only
        or v26_5_policy_only_residual
        or v26_5_policy_only_identity_control
    ):
        if requested_mode != "policy_only":
            raise ValueError(
                "Policy-only evaluation contract requires checkpoint_load_mode='policy_only'; "
                f"got {requested_mode!r}."
            )
        return
    if requested_mode != "full":
        logger.warning(
            "Evaluation requested checkpoint_load_mode={!r}; normalizing to 'full' so "
            "trainer state/global_step and checkpoint naming are restored.",
            requested_mode,
        )
    config.checkpoint_load_mode = "full"


def migrate_legacy_a2_stage2_grasp_reward_config(train_config, config_path):
    """Migrate checkpoint-adjacent legacy A2 stage2 grasp reward config."""

    uses_a2_base = bool(
        OmegaConf.select(train_config, "algo.config.use_a2_base", default=False)
    )
    robot_type = OmegaConf.select(train_config, "robot.asset.robot_type", default=None)
    if not uses_a2_base and robot_type != "a2_piper":
        return

    env_config = train_config.env.config
    missing_keys = [
        key for key in _A2_STAGE2_GRASP_REWARD_CONFIG_KEYS if key not in env_config
    ]
    if not missing_keys:
        return

    present_keys = [
        key for key in _A2_STAGE2_GRASP_REWARD_CONFIG_KEYS if key in env_config
    ]
    if present_keys:
        raise RuntimeError(
            "Partial legacy A2 stage2 grasp reward config in "
            f"{config_path}; missing keys: {missing_keys}"
        )

    if _A2_STAGE2_LEGACY_CONTACT_FORCE_KEY not in env_config:
        raise RuntimeError(
            "Missing A2 stage2 grasp reward config in "
            f"{config_path}; missing keys: {missing_keys}"
        )

    env_config.a2_stage2_contact_force_threshold = env_config[
        _A2_STAGE2_LEGACY_CONTACT_FORCE_KEY
    ]
    for key, value in _A2_STAGE2_GRASP_REWARD_CONFIG_DEFAULTS.items():
        env_config[key] = value
    logger.info(
        "Migrated legacy A2 stage2 grasp reward config from "
        f"{config_path} using {_A2_STAGE2_LEGACY_CONTACT_FORCE_KEY}"
    )


def migrate_legacy_a2_stage3_to4_threshold_config(train_config, config_path):
    """Add the historical A2 hinge threshold to pre-parameterization checkpoints."""

    uses_a2_base = bool(
        OmegaConf.select(train_config, "algo.config.use_a2_base", default=False)
    )
    robot_type = OmegaConf.select(train_config, "robot.asset.robot_type", default=None)
    if not uses_a2_base and robot_type != "a2_piper":
        return

    env_config = train_config.env.config
    if _A2_STAGE3_TO4_DOOR_HINGE_THRESHOLD_KEY in env_config:
        return
    env_config[_A2_STAGE3_TO4_DOOR_HINGE_THRESHOLD_KEY] = (
        _A2_STAGE3_TO4_DOOR_HINGE_THRESHOLD_LEGACY_DEFAULT
    )
    logger.info(
        "Migrated legacy A2 stage3->4 hinge threshold config from "
        f"{config_path} using historical default "
        f"{_A2_STAGE3_TO4_DOOR_HINGE_THRESHOLD_LEGACY_DEFAULT}"
    )


def migrate_legacy_a2_stage3_base_unlocked_config(train_config, config_path):
    """Add historical locked stage3 base semantics to legacy A2 checkpoints."""

    uses_a2_base = bool(
        OmegaConf.select(train_config, "algo.config.use_a2_base", default=False)
    )
    robot_type = OmegaConf.select(train_config, "robot.asset.robot_type", default=None)
    if not uses_a2_base and robot_type != "a2_piper":
        return

    env_config = train_config.env.config
    if _A2_STAGE3_BASE_UNLOCKED_KEY in env_config:
        return
    env_config[_A2_STAGE3_BASE_UNLOCKED_KEY] = (
        _A2_STAGE3_BASE_UNLOCKED_LEGACY_DEFAULT
    )
    logger.info(
        "Migrated legacy A2 stage3 base mobility config from "
        f"{config_path} using historical a2_stage3_base_unlocked="
        f"{_A2_STAGE3_BASE_UNLOCKED_LEGACY_DEFAULT}"
    )


def migrate_legacy_a2_hold_diagnostic_env_config(train_config, config_path):
    """Add the complete historical/default-off hold-diagnostic group to legacy A2 checkpoints."""

    uses_a2_base = bool(
        OmegaConf.select(train_config, "algo.config.use_a2_base", default=False)
    )
    robot_type = OmegaConf.select(train_config, "robot.asset.robot_type", default=None)
    if not uses_a2_base and robot_type != "a2_piper":
        return

    env_config = train_config.env.config
    present = [key for key in _A2_HOLD_DIAGNOSTIC_ENV_CONFIG_DEFAULTS if key in env_config]
    if len(present) == len(_A2_HOLD_DIAGNOSTIC_ENV_CONFIG_DEFAULTS):
        return
    if present:
        missing = [
            key for key in _A2_HOLD_DIAGNOSTIC_ENV_CONFIG_DEFAULTS if key not in env_config
        ]
        raise RuntimeError(
            "Partial legacy A2 hold diagnostic env config in "
            f"{config_path}; present={present}, missing={missing}."
        )
    for key, value in _A2_HOLD_DIAGNOSTIC_ENV_CONFIG_DEFAULTS.items():
        env_config[key] = value
    logger.info(
        "Migrated legacy A2 hold diagnostic env config from {} using historical "
        "TCP z=0.085 and default-off detailed/material settings",
        config_path,
    )


def process_output_dim_in_config(config):
    """Process and adapt output dimensions for actor and teacher_actor backbones.

    When output_dim is set to -1 in the config, this function auto-calculates
    the correct dimension based on the homie command keys.
    """

    def calculate_homie_output_dim():
        output_dim = 0
        for key in config.obs["homie_command_keys"].keys():
            output_dim += len(config.obs["homie_command_default"][key])
        return output_dim

    def adapt_backbone_output_dim(backbone_config, config_name=""):
        try:
            if hasattr(backbone_config, "module_config_dict"):
                if backbone_config.module_config_dict.output_dim[0] == -1:
                    output_dim = calculate_homie_output_dim()
                    backbone_config.module_config_dict.output_dim = [output_dim]
                    return True
            elif hasattr(backbone_config, "mlp_module") and hasattr(
                backbone_config.mlp_module, "module_config_dict"
            ):
                if backbone_config.mlp_module.module_config_dict.output_dim[0] == -1:
                    output_dim = calculate_homie_output_dim()
                    backbone_config.mlp_module.module_config_dict.output_dim = [output_dim]
                    return True
        except (AttributeError, IndexError) as e:
            logger.warning(f"Could not adapt {config_name} backbone output_dim: {e}")
        return False

    if (
        config.algo.config.get("use_new_actor_critic", False)
        and hasattr(config.algo.config, "actor")
        and hasattr(config.algo.config.actor, "backbone")
    ):
        adapt_backbone_output_dim(config.algo.config.actor.backbone, "actor")

        if (
            getattr(config.algo.config, "use_dagger", False)
            and hasattr(config.algo.config, "teacher_actor")
            and hasattr(config.algo.config.teacher_actor, "backbone")
        ):
            adapt_backbone_output_dim(config.algo.config.teacher_actor.backbone, "teacher_actor")


def _align_app_launcher_device_with_accelerate(args_cli):
    """Use the exact explicit Accelerate device for IsaacLab AppLauncher."""
    if "ACCELERATE_TORCH_DEVICE" in os.environ:
        args_cli.device = os.environ["ACCELERATE_TORCH_DEVICE"]


def _finalize_p2_eval_if_enabled(config, env) -> None:
    enabled = OmegaConf.select(
        config,
        "env.config.a2_v24_force_boundary_enabled",
        default=False,
    )
    if enabled is not True:
        return
    finalizer = getattr(env, "finalize_a2_v24_force_boundary", None)
    if not callable(finalizer):
        raise RuntimeError(
            "enabled P2 evaluation requires env.finalize_a2_v24_force_boundary()"
        )
    finalizer()


@hydra.main(config_path="config", config_name="base_eval")
def main(override_config: OmegaConf):
    # --- Logging setup ---
    hydra_log_path = os.path.join(HydraConfig.get().runtime.output_dir, "eval.log")
    logger.remove()
    logger.add(hydra_log_path, level="DEBUG")
    console_log_level = os.environ.get("LOGURU_LEVEL", "INFO").upper()
    logger.add(sys.stdout, level=console_log_level, colorize=True)

    from gr00t.rl.utils.logging import HydraLoggerBridge

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger().addHandler(HydraLoggerBridge())
    os.chdir(hydra.utils.get_original_cwd())
    bound_r2_config = _load_r2_bound_config(override_config)

    # --- Load and merge training config from checkpoint directory ---
    if override_config.checkpoint is not None:
        has_config = True
        checkpoint = Path(override_config.checkpoint)
        config_path = checkpoint.parent / "config.yaml"
        if not config_path.exists():
            config_path = checkpoint.parent.parent / "config.yaml"
            if not config_path.exists():
                has_config = False
                logger.error(f"Could not find config path: {config_path}")

        if has_config:
            logger.info(f"Loading training config file from {config_path}")
            with open(config_path) as file:
                train_config = OmegaConf.load(file)

            if "checkpoint_load_mode" in train_config:
                saved_training_mode = _validate_checkpoint_load_mode(
                    train_config.checkpoint_load_mode,
                    f"Saved training config {config_path}",
                )
                if saved_training_mode == "policy_only":
                    logger.info(
                        "Saved training config uses checkpoint_load_mode='policy_only'; "
                        "evaluation normalizes checkpoint loading to 'full'."
                    )

            if train_config.eval_overrides is not None:
                train_config = OmegaConf.merge(train_config, train_config.eval_overrides)

            migrate_legacy_a2_stage2_grasp_reward_config(train_config, config_path)
            migrate_legacy_a2_stage3_to4_threshold_config(train_config, config_path)
            migrate_legacy_a2_stage3_base_unlocked_config(train_config, config_path)
            migrate_legacy_a2_hold_diagnostic_env_config(train_config, config_path)
            if bound_r2_config is not None:
                config = OmegaConf.merge(train_config, override_config, bound_r2_config)
                _apply_r2_workflow_overrides(config, override_config)
            else:
                config = OmegaConf.merge(train_config, override_config)
        else:
            if bound_r2_config is not None:
                config = OmegaConf.merge(override_config, bound_r2_config)
                _apply_r2_workflow_overrides(config, override_config)
            else:
                config = override_config
        config.experiment_dir = checkpoint.parent
    else:
        if override_config.eval_overrides is not None:
            config = override_config.copy()
            eval_overrides = OmegaConf.to_container(config.eval_overrides, resolve=True)
            for arg in sys.argv[1:]:
                if not arg.startswith("+"):
                    key = arg.split("=")[0]
                    if key in eval_overrides:
                        del eval_overrides[key]
            config.eval_overrides = OmegaConf.create(eval_overrides)
            config = OmegaConf.merge(config, eval_overrides)
        else:
            config = override_config
        if bound_r2_config is not None:
            config = OmegaConf.merge(config, bound_r2_config)
            _apply_r2_workflow_overrides(config, override_config)

    _normalize_eval_checkpoint_load_mode(config)
    config.seed = _validate_eval_seed(config.seed)
    if config.get("admission_plan_id", None) == "base_v20_R2_admission_execution_v1":
        validate_r2_eval_config(config)

    # Resume wandb run if meta.yaml exists
    meta_path = Path(config.experiment_dir) / "meta.yaml"
    if meta_path.exists():
        meta = yaml.safe_load(open(meta_path, "r"))
        config.wandb.wandb_id = meta["wandb_run"]
        print(f"resume wandb from run: {config.wandb.wandb_id}")

    # --- Setup Isaac Sim ---
    simulator_type = config.simulator["_target_"].split(".")[-1]
    if simulator_type == "IsaacSim":
        try:
            with open("./rl/simulator/isaacsim/.isaacsim_version", "r", encoding="utf-8") as f:
                DEFAULT_ISAACSIM_VERSION = f.read().strip()
        except FileNotFoundError:
            DEFAULT_ISAACSIM_VERSION = "4.5"

        if DEFAULT_ISAACSIM_VERSION == "4.5":
            from isaaclab.app import AppLauncher
        elif DEFAULT_ISAACSIM_VERSION == "4.2":
            logger.warning("Using IsaacSim 4.2, replacing isaaclab with omni.isaac.lab")
            from omni.isaac.lab.app import AppLauncher

        import argparse

        import isaaclab

        parser = argparse.ArgumentParser(description="Evaluate an RL agent.")
        AppLauncher.add_app_launcher_args(parser)

        args_cli, hydra_args = parser.parse_known_args()
        sys.argv = [sys.argv[0]] + hydra_args
        args_cli.num_envs = config.num_envs
        args_cli.seed = config.seed
        args_cli.env_spacing = config.env.config.env_spacing
        args_cli.output_dir = config.output_dir
        args_cli.enable_cameras = (
            config.simulator.config.cameras.enable_cameras
            or config.simulator.config.get("render_results", False)
        )
        args_cli.headless = config.headless
        _align_app_launcher_device_with_accelerate(args_cli)

        # Copy headless rendering kit file if needed
        dest_path = Path(isaaclab.__file__).resolve().parent.parent.parent.parent / "apps"
        current_file_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
        if args_cli.enable_cameras and args_cli.headless:
            source_file = current_file_dir_path / "apps/phc.isaaclab.python.headless.rendering.kit"
            shutil.copy(source_file, dest_path)
            args_cli.experience = dest_path / "phc.isaaclab.python.headless.rendering.kit"

        app_launcher = AppLauncher(args_cli)
        simulation_app = app_launcher.app

    # --- Imports that must come after Isaac Sim initialization ---
    from accelerate import Accelerator
    from transformers import HfArgumentParser
    from trl import ModelConfig, PPOConfig, ScriptArguments

    from gr00t.rl.agents.modules.ppo_modules import (
        PPOCritic,
        PPOStateActor,
        PPOStateActorFixSigma,
    )
    from gr00t.rl.trl.utils.common import custom_instantiate
    from gr00t.rl.utils.common import seeding
    from gr00t.rl.utils.helpers import pre_process_config

    # --- Config processing ---
    unresolved_conf = OmegaConf.to_container(config, resolve=False)
    os.chdir(hydra.utils.get_original_cwd())
    pre_process_config(config)

    # Set rendering output directory
    ckpt_num = config.checkpoint.split("/")[-1].split("_")[-1].split(".")[0]
    if config.env.config.get("save_rendering_dir", None) is None:
        if config.simulator.config.get("render_results", False):
            from datetime import datetime

            parent_dir = checkpoint.parent.name
            config.env.config.save_rendering_dir = str(
                Path("logs_rl") / "renderings" / datetime.now().strftime("%Y-%m-%d") / parent_dir
            )
        else:
            config.env.config.save_rendering_dir = str(
                checkpoint.parent / "renderings" / f"ckpt_{ckpt_num}"
            )
    config.env.config.ckpt_dir = str(checkpoint.parent)

    # --- Setup TRL training args (reused for eval) ---
    config.algo.trl.output_dir = str(Path(config.experiment_dir))
    parser = HfArgumentParser((ScriptArguments, PPOConfig, ModelConfig))
    script_args, training_args, model_args = parser.parse_dict(config.algo.trl)
    training_args.seed = int(config.seed)
    if "eval_output_dir" in config:
        training_args.eval_output_dir = config.eval_output_dir

    ref_model = None
    value_model = None

    # --- Accelerator and seeding ---
    accelerator = Accelerator()
    device = str(accelerator.device)
    if device == "cuda":
        device = "cuda:0"
    config.multi_gpu = accelerator.num_processes > 1
    if config.multi_gpu:
        config.global_rank = accelerator.process_index
        config.seed += accelerator.process_index
        config.algo.config.global_rank = accelerator.process_index
        config.algo.config.world_size = accelerator.num_processes

    if accelerator.is_main_process:
        eval_runtime_config_path = (
            Path(HydraConfig.get().runtime.output_dir) / ".hydra" / "runtime_config.yaml"
        )
        OmegaConf.save(config, eval_runtime_config_path)
    seeding(config.seed)

    # --- Create environment ---
    env = instantiate(config=config.env, device=device)

    # --- Build policy and value models ---
    process_output_dim_in_config(config)

    if config.algo.config.get("use_new_actor_critic", False):
        module_dim_dict = getattr(config.algo.config, "module_dim", {})
        policy = instantiate(
            config.algo.config.actor,
            env_config=env.config,
            algo_config=config.algo.config,
            module_dim_dict=module_dim_dict,
            _recursive_=False,
        ).to(device)
        if getattr(config.algo.config, "use_dagger", False):
            ref_model = instantiate(
                config.algo.config.teacher_actor,
                env_config=env.config,
                algo_config=config.algo.config,
                module_dim_dict=module_dim_dict,
                _recursive_=False,
                input_key="teacher_obs",
            ).to(device)
        if not getattr(config.algo.config, "distill_only", False) and hasattr(
            config.algo.config, "critic"
        ):
            value_model = instantiate(
                config.algo.config.critic,
                env_config=env.config,
                algo_config=config.algo.config,
                module_dim_dict=module_dim_dict,
                _recursive_=False,
            ).to(device)
    else:
        if getattr(config.algo.config, "use_dagger", False):
            module_dim_dict = getattr(config.algo.config, "module_dim", {})
            policy = PPOStateActorFixSigma(
                obs_dim_dict=env.config.robot.algo_obs_dim_dict,
                module_config_dict=config.algo.config.module_dict.actor,
                num_actions=env.config.robot.actions_dim,
                module_dim_dict=module_dim_dict,
            ).to(device)
            ref_model = PPOStateActorFixSigma(
                obs_dim_dict=env.config.robot.algo_obs_dim_dict,
                module_config_dict=config.algo.config.module_dict.teacher_actor,
                num_actions=env.config.robot.actions_dim,
                module_dim_dict=module_dim_dict,
            ).to(device)
        else:
            policy = PPOStateActor(
                obs_dim_dict=env.config.robot.algo_obs_dim_dict,
                module_config_dict=config.algo.config.module_dict.actor,
                num_actions=env.config.robot.actions_dim,
                input_key="actor_obs",
                init_noise_std=config.algo.config.init_noise_std,
            ).to(device)
            value_model = PPOCritic(
                env.config.robot.algo_obs_dim_dict,
                config.algo.config.module_dict.critic,
            ).to(device)

    accelerator.wait_for_everyone()

    # --- Callbacks ---
    callbacks = []
    for callback in config.callbacks.values():
        callbacks.append(instantiate(callback))

    # --- Build trainer (loads checkpoint weights) ---
    checkpoint_load_kwargs = {}
    if config.trainer["_target_"] == _A2_BASE_API_TRAINER_TARGET:
        checkpoint_load_kwargs["checkpoint_load_mode"] = config.checkpoint_load_mode
        checkpoint_load_kwargs["a2_v26_5_runtime_load_receipt_output_dir"] = str(
            Path(config.eval_output_dir).resolve()
        )
        checkpoint_load_kwargs["a2_v26_5_runtime_load_receipt_kind"] = "eval"

    trainer = custom_instantiate(
        config.trainer,
        args=training_args,
        config=config.algo.config,
        env=env,
        model=policy,
        ref_model=ref_model,
        use_ref_model=getattr(config.algo.config, "use_dagger", False),
        value_model=value_model,
        train_dataset=None,
        eval_dataset=None,
        callbacks=callbacks,
        checkpoint=config.checkpoint,
        local_seed=config.seed,
        accelerator=accelerator,
        **checkpoint_load_kwargs,
    )

    # --- Optional ONNX export (only with single env) ---
    EXPORT_ONNX = config.num_envs == 1
    checkpoint_path = str(checkpoint)

    exported_policy_path = os.path.join(config.experiment_dir, "exported")
    os.makedirs(exported_policy_path, exist_ok=True)
    exported_onnx_name = f"model_step_{trainer.state.global_step:06d}.onnx"
    new_cp_path = (
        f"{os.path.dirname(config.checkpoint)}/model_step_{trainer.state.global_step:06d}.pt"
    )

    if not os.path.exists(new_cp_path):
        shutil.copy(checkpoint_path, new_cp_path)

    if EXPORT_ONNX:
        assert config.num_envs == 1, "num_envs must be 1 for exporting onnx"
        from gr00t.rl.utils.inference_helpers import (
            export_policy_as_onnx,
            export_policy_CNN_as_onnx,
            export_policy_CNN_as_onnx_with_obj_pred,
            export_policy_z_as_onnx,
        )

        algo = trainer
        example_obs_dict = algo.get_example_obs()

        if config.env.config.get("use_z", False):
            export_policy_z_as_onnx(
                algo.inference_model,
                env,
                exported_policy_path,
                exported_onnx_name,
                example_obs_dict,
            )
        elif config.simulator.config.cameras.enable_cameras:
            if hasattr(config.algo.config.actor.backbone, "obj_pred_mlp"):
                export_policy_CNN_as_onnx_with_obj_pred(
                    algo.inference_model,
                    env,
                    exported_policy_path,
                    exported_onnx_name,
                    example_obs_dict,
                )
            else:
                export_policy_CNN_as_onnx(
                    algo.inference_model,
                    env,
                    exported_policy_path,
                    exported_onnx_name,
                    example_obs_dict,
                )
        else:
            export_policy_as_onnx(
                algo.inference_model, exported_policy_path, exported_onnx_name, example_obs_dict
            )
        logger.info(
            f"Exported policy as onnx to: {os.path.join(exported_policy_path, exported_onnx_name)}"
        )

    if config.get("export_onnx_only", False):
        _finalize_p2_eval_if_enabled(config, env)
        exit()

    # --- Run evaluation ---
    trainer.eval()
    _finalize_p2_eval_if_enabled(config, env)
    logger.info("Finished evaluation")
    os._exit(0)


if __name__ == "__main__":
    main()
