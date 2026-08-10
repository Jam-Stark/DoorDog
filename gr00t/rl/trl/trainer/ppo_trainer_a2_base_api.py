# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from collections import deque
from collections.abc import Mapping
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
import tempfile
from typing import Dict, Optional
from numbers import Real

import numpy as np
import pandas as pd
import torch
import torchvision
from omegaconf import ListConfig, OmegaConf
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from transformers.trainer import *
from trl.trainer.ppo_trainer import *

from gr00t.rl.agents.modules.data_utils import RolloutStorage
from gr00t.rl.trl.callbacks.hv_callback_handler import HVCallbackHandler
from gr00t.rl.trl.utils.common import wandb_run_exists
from gr00t.rl.trl.utils.rl import compute_episode_attnmask
from gr00t.rl.trl.utils.scheduler import update_scheduled_params
from gr00t.rl.utils.average_meters import TensorAverageMeterDict

console = Console()
import time

import onnxruntime as ort

from gr00t.rl.trl.modules.homie_modules import (
    HIMActorCritic,
    HomieActorModule,
    init_actor_critic_dict,
)


_CHECKPOINT_LOAD_MODES = frozenset(("full", "policy_only"))
_V21B_PLAN_ID = "base_v21B_theta_arm_ablation_v1"
_V21B_METRIC_SOURCES = {
    "send_latch_fire_rate": "a2_v21B_send_latch_fire_rate",
    "hinge_at_send_latch_rad": "a2_v21B_hinge_at_send_latch_rad",
    "hinge_at_crossing_rad": "a2_v21B_hinge_at_crossing_rad",
    "send_to_cross_steps": "a2_v21B_send_to_cross_steps",
    "stage_overtime_rate": "a2_v21B_stage_overtime_rate",
    "upper_dof_overspeed_rate": "a2_v21B_upper_dof_overspeed_rate",
    "arm_clipped_utilization": "a2_v21B_arm_clipped_utilization",
    "arm_clipped_utilization_valid_rate": "a2_v21B_arm_clipped_utilization_valid_rate",
    "finite_data": "a2_v21B_finite_data",
    "decomposition_sanity": "a2_v21B_decomposition_sanity",
    "decomposition_sanity_valid_rate": "a2_v21B_decomposition_sanity_valid_rate",
}
_V21B_COVERAGE_METRICS = frozenset((
    "arm_clipped_utilization_valid_rate",
    "decomposition_sanity_valid_rate",
))
_V21B_MATERIALIZATION_PHASES = frozenset(("POST_CENSUS", "FORMAL_PROMOTED"))
_V21B_MISSING_CONFIG = object()

_A2_V23_RP0_RUNTIME_RECEIPT_SCHEMA = "a2_piper_v23_p07_rp0_runtime_receipt_v1"
_A2_V23_RP0_RUNTIME_RECEIPT_FILENAME = "a2_v23_p07_runtime_receipt.json"
_A2_V23_RP0_EFFECTIVE_CONFIG_SCHEMA = "a2_piper_v23_p07_effective_config_v1"
_A2_V23_RP0_EFFECTIVE_CONFIG_FILENAME = "a2_v23_p07_effective_config.json"
_A2_V23_RP0_RUNTIME_MASK_INDICES = (3, 4)
_A2_V23_RP0_RUNTIME_NEUTRAL = 0.0
_A2_V23_RP0_RUNTIME_ENVS = 64
_A2_V23_STATIONARY_RENT_PASS_SCHEMA = "a2_piper_v23_stationary_rent_pass_v1"
_A2_V23_STATIONARY_RENT_PASS_FILENAME = "a2_v23_stationary_rent_pass.json"
_A2_V23_P08_STATE_BANK_RAW_SCHEMA = "a2_piper_v23_p08_state_bank_raw_v1"
_A2_V23_P08_STATE_BANK_ENTRY_SCHEMA = "a2_piper_v23_state_bank_entry_v1"
_A2_V23_P08_STATE_BANK_RAW_FILENAME = "a2_v23_p08_state_bank_raw.json"
_A2_V23_P08_TARGET_STAGES = (2, 3, 4)
_A2_V23_P08_FORWARD_MODE = "FULL"
_A2_V23_P08_SOURCE_FREEZE_PATH = (
    "logs_eval/base_v23/p0/r50_p05_d1_source_20260809/a0_capability_source_freeze.json"
)
_A2_V23_P08_SOURCE_SCHEMA = "a2_piper_v23_capability_source_freeze_v1"
_A2_V23_P08_SOURCE_STATUS = "CAPABILITY_SOURCE_FROZEN"
_A2_V23_P08_SOURCE_CELL = "A0"
_A2_V23_P08_SELECTION_BASIS = "CURRENT_EASY_A0_STABLE_REFERENCE"
_A2_V23_P08_EFFORT_NM = 40.0
_A2_V23_P08_CHECKPOINT_STEP = 1250
_A2_V23_P08_SEED = 0
_A2_V23_P08_NUM_ENVS = 16
_A2_V23_P08_P05_PURPOSE = "D1_CAPABILITY_SOURCE"
_A2_V23_P08_P05_MODE = "FULL"
_A2_V23_P08_P05_TOPOLOGY = "canonical16"
_A2_V23_P08_P05_BOUND_MANIFEST_SCHEMA = (
    "a2_piper_base_v23_d1_capability_bound_plain16_manifest_v1"
)
_A2_V23_P08_P05_BOUND_MANIFEST_STATUS = "BOUND_D1_CAPABILITY_SOURCE"
_A2_V23_P08_P05_BOUND_SELECTOR_MODE = "v23_d1_capability_source_plain16"
_A2_V23_P08_P05_EFFORT_FREEZE_PATH = (
    "logs_eval/base_v23/p0/r33_p02_effort_freeze_20260809/effort_freeze.json"
)
_A2_V23_P08_P05_ATLAS_PATH = (
    "logs_eval/base_v23/p0/r26_p02_p04_p05_runtime_20260809/p04/door_atlas_raw.json"
)
_A2_V23_P08_P05_EXTERNAL_THRESHOLD_PATH = (
    "logs_eval/base_v23/p0/r26_p02_p04_p05_runtime_20260809/p04/door_external_torque_threshold.json"
)
_A2_V23_P08_P05_PLAIN_MANIFEST_PATH = (
    "logs_eval/base_v23/p0/r31_p02_temporal_runtime_20260809/torque/effort_40/canonical16/"
    "v23_p0_plain_scenario_manifest.json"
)
_A2_V23_P08_P05_CONFIG_ID = (
    "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/config.yaml"
)
_A2_V23_P08_P05_REQUESTED_PARAMS = {
    "hinge_damping_native": 50.0,
    "hinge_stiffness_native": 2.0,
    "hinge_max_force_nm": 4.5,
    "door_weight_kg": 120.0,
}
_A2_V23_P08_P05_NATIVE_PARAMS = {
    "hinge_damping_native": 2864.7890625,
    "hinge_stiffness_native": 114.59156036376953,
    "hinge_effort_limit_nm": 4.5,
    "door_weight_kg": 119.99999237060547,
}
_A2_V23_P08_P05_READBACK_SCHEMA = "a2_piper_v23_p05_runtime_physical_readback_v1"
_A2_V23_FULL_REQUIRED_TRAINER_STATE_FIELDS = (
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
_A2_V23_FULL_ENV_RESET_STATE_FIELDS = frozenset(("cur_reward_sum", "cur_episode_length"))


def _v21b_scalar(value, *, key: str):
    """Extract one scalar trainer value without accepting synthetic fallbacks."""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
    elif isinstance(value, torch.Tensor) and value.numel() == 1:
        number = float(value.detach().cpu().item())
    else:
        raise ValueError(f"v21-B metric {key!r} must be a scalar")
    if not math.isfinite(number):
        raise ValueError(f"v21-B metric {key!r} is non-finite")
    return number


def normalize_v21b_training_metrics(metrics) -> dict[str, float | bool]:
    """Map exact trainer ``Env/a2_v21B_*`` keys to the v21-B row schema."""

    if not isinstance(metrics, dict):
        raise ValueError("v21-B training metrics must be a mapping")
    normalized: dict[str, float | bool] = {}
    for name, source in _V21B_METRIC_SOURCES.items():
        source_key = f"Env/{source}"
        if source_key not in metrics:
            raise ValueError(f"v21-B training metric source key is missing: {source_key}")
        normalized[name] = _v21b_scalar(metrics[source_key], key=source_key)
    for name in _V21B_COVERAGE_METRICS:
        coverage = normalized[name]
        if isinstance(coverage, bool) or coverage != 1.0:
            raise ValueError(f"v21-B training metric {name} must equal 1.0 for complete coverage")
    return normalized


def build_v21b_training_metric_row(
    metrics,
    *,
    batch_index: int,
    cell: str,
    seed: int,
    source_config_sha256: str,
    materialization_sha256: str,
    materialized_config_sha256: str,
    materialization_phase: str,
    adaptation_bundle_sha256: str | None,
    source_lock_sha256: str,
    source_lock_file_sha256: str,
    git_commit: str,
    git_tree: str,
    source_checkpoint_sha256: str | None = None,
    checkpoint_path: str | None = None,
    checkpoint_sha256: str | None = None,
) -> dict[str, object]:
    """Build one source/Git-bound v21-B raw training metric row."""

    if isinstance(batch_index, bool) or not isinstance(batch_index, int) or batch_index <= 0:
        raise ValueError("v21-B training metric batch_index must be a positive integer")
    if not isinstance(cell, str) or cell not in {"B1", "B2", "B3", "B4", "B5", "B6", "B7"}:
        raise ValueError("v21-B training metric cell must be one of B1-B7")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed not in (0, 1):
        raise ValueError("v21-B training metric seed must be 0 or 1")
    if materialization_phase not in _V21B_MATERIALIZATION_PHASES:
        raise ValueError("v21-B training metric materialization_phase is invalid")
    if materialization_phase == "POST_CENSUS":
        if adaptation_bundle_sha256 is not None:
            raise ValueError("POST_CENSUS v21-B training metric adaptation identity must be null")
    elif not isinstance(adaptation_bundle_sha256, str) or len(adaptation_bundle_sha256) != 64 or any(char not in "0123456789abcdef" for char in adaptation_bundle_sha256):
        raise ValueError("FORMAL_PROMOTED v21-B training metric adaptation identity must be a lowercase sha256 digest")
    for name, value in (
        ("source_config_sha256", source_config_sha256),
        ("materialization_sha256", materialization_sha256),
        ("materialized_config_sha256", materialized_config_sha256),
    ):
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"v21-B training metric {name} has an invalid identity")
    for name, value in (("source_lock_sha256", source_lock_sha256), ("source_lock_file_sha256", source_lock_file_sha256), ("git_commit", git_commit), ("git_tree", git_tree)):
        expected_length = 40 if name in ("git_commit", "git_tree") else 64
        if not isinstance(value, str) or len(value) != expected_length or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"v21-B training metric {name} has an invalid identity")
    normalized = normalize_v21b_training_metrics(metrics)
    row = {
        "schema": "a2_piper_base_v21B_training_metric_v1",
        "producer_state": "PROCESS_COMPLETED",
        "scientific_plan_id": _V21B_PLAN_ID,
        "cell": cell,
        "seed": seed,
        "source_config_sha256": source_config_sha256,
        "materialization_sha256": materialization_sha256,
        "materialized_config_sha256": materialized_config_sha256,
        "materialization_phase": materialization_phase,
        "adaptation_bundle_sha256": adaptation_bundle_sha256,
        "source_lock_sha256": source_lock_sha256,
        "source_lock_file_sha256": source_lock_file_sha256,
        "git_commit": git_commit,
        "git_tree": git_tree,
        "batch_index": batch_index,
        "metrics": normalized,
        "metric_sources": dict(_V21B_METRIC_SOURCES),
    }
    if source_checkpoint_sha256 is not None:
        if not isinstance(source_checkpoint_sha256, str) or len(source_checkpoint_sha256) != 64 or any(char not in "0123456789abcdef" for char in source_checkpoint_sha256):
            raise ValueError("v21-B training metric source checkpoint identity is invalid")
        row["source_checkpoint_sha256"] = source_checkpoint_sha256
    if checkpoint_path is not None:
        if not isinstance(checkpoint_path, str) or not checkpoint_path:
            raise ValueError("v21-B training metric checkpoint path is invalid")
        row["checkpoint_path"] = checkpoint_path
    if checkpoint_sha256 is not None:
        if not isinstance(checkpoint_sha256, str) or len(checkpoint_sha256) != 64 or any(char not in "0123456789abcdef" for char in checkpoint_sha256):
            raise ValueError("v21-B training metric checkpoint identity is invalid")
        row["checkpoint_sha256"] = checkpoint_sha256
    if checkpoint_path is not None and checkpoint_sha256 is None:
        raise ValueError("v21-B training metric checkpoint hash is required with checkpoint path")
    if checkpoint_sha256 is not None and checkpoint_path is None:
        raise ValueError("v21-B training metric checkpoint path is required with checkpoint hash")
    return row


def validate_r2_batch_ownership(*, local_batch_size: int, world_size: int, num_total_batches: int) -> dict[str, int]:
    """Validate R2 global batch ownership without coercing invalid values."""
    values = (local_batch_size, world_size, num_total_batches)
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
        raise ValueError("R2 batch ownership requires positive integer dimensions")
    return {"local_batch_size": local_batch_size, "world_size": world_size, "global_batch_size": local_batch_size * world_size, "num_total_batches": num_total_batches}


def validate_r2_reward_component_coverage(raw_components, scaled_components) -> tuple[str, ...]:
    if not isinstance(raw_components, dict) or not isinstance(scaled_components, dict):
        raise ValueError("R2 reward hook requires raw and scaled component mappings")
    if set(raw_components) != set(scaled_components):
        raise ValueError("R2 reward hook requires exact raw/scaled reward-name coverage")
    return tuple(sorted(raw_components))


@contextmanager
def _a2_hold_oracle_finalize_guard(env, enabled):
    if not isinstance(enabled, bool):
        raise RuntimeError(f"A2 hold oracle finalize guard requires bool; got {enabled!r}.")
    try:
        yield
    finally:
        if enabled:
            finalize = getattr(env, "finalize_a2_eval_hold_oracle", None)
            if finalize is None:
                raise RuntimeError("A2 hold oracle requires a finalizer for exact gain restore.")
            finalize()


def validate_checkpoint_load_mode(checkpoint_load_mode):
    if not isinstance(checkpoint_load_mode, str) or checkpoint_load_mode not in (
        _CHECKPOINT_LOAD_MODES
    ):
        raise ValueError(
            "checkpoint_load_mode must be exactly one of "
            f"{sorted(_CHECKPOINT_LOAD_MODES)}; got {checkpoint_load_mode!r}."
        )
    return checkpoint_load_mode


def _load_a2_base_metadata(metadata_path):
    path = Path(metadata_path).expanduser()
    with path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)
    obs_contract = metadata["contracts"]["obs"]
    action_contract = metadata["contracts"]["action"]
    contract = {
        "obs_dim": int(obs_contract["flattened_dim"]),
        "history_length": int(obs_contract["history_length"]),
        "frame_dim": int(obs_contract["dog_frame_dim"]),
        "action_dim": int(action_contract["dim"]),
        "leg_joint_names": list(action_contract["leg_joint_names"]),
        "leg_action_scale": float(action_contract["leg_action_scale"]),
        "use_default_offset": bool(action_contract["use_default_offset"]),
    }
    if contract["obs_dim"] != contract["history_length"] * contract["frame_dim"]:
        raise ValueError(f"A2_Base metadata obs contract is inconsistent: {contract}")
    return contract


_A2_EVAL_OPTIONAL_RATIO_SPECS = {
    "a2_stage3_contact_stability_conditional_frac": (
        "a2_stage3_contact_stability_numerator_frac",
        "a2_stage3_contact_stability_denominator_frac"
    ),
    "a2_stage4_contact_stability_conditional_frac": (
        "a2_stage4_contact_stability_numerator_frac",
        "a2_stage4_contact_stability_denominator_frac"
    ),
    "a2_stage3_hold_and_drive_frac": (
        "a2_stage3_hold_and_drive_numerator_frac",
        "a2_stage3_hold_and_drive_denominator_frac",
    ),
    "a2_stage3_stage4_hold_and_drive_frac": (
        "a2_stage3_stage4_hold_and_drive_numerator_frac",
        "a2_stage3_stage4_hold_and_drive_denominator_frac",
    ),
    "a2_stage3_unlatch_hold_issued_frac": (
        "a2_stage3_unlatch_hold_issued_numerator_frac",
        "a2_stage3_unlatch_hold_issued_denominator_frac"
    ),
    "a2_stage3_stage4_coasting_frac": (
        "a2_stage3_stage4_coasting_numerator_frac",
        "a2_stage3_stage4_coasting_denominator_frac"
    ),
    "a2_stage3_stage4_over_force_frac": (
        "a2_stage3_stage4_over_force_numerator_frac",
        "a2_stage3_stage4_over_force_denominator_frac",
    ),
    "a2_stage3_handle_hard_limit_frac": (
        "a2_stage3_handle_hard_limit_numerator_frac",
        "a2_stage3_handle_hard_limit_denominator_frac"
    ),
    "a2_stage4_release_gate_frac": (
        "a2_stage4_release_gate_numerator_frac",
        "a2_stage4_release_gate_denominator_frac",
    ),
}


_A2_GLOBAL_ENV_QUANTILE_SPECS = {
    "a2_stage5_forward_velocity": (
        "_a2_stage5_forward_velocity_samples",
        "_a2_stage5_forward_velocity_sample_mask",
        "a2_stage5_forward_velocity_p50",
        "a2_stage5_forward_velocity_p95",
    ),
    "a2_stage45_doorframe_contact_force": (
        "_a2_stage45_doorframe_contact_force_samples",
        "_a2_stage45_doorframe_contact_force_sample_mask",
        "a2_stage45_doorframe_contact_force_p50",
        "a2_stage45_doorframe_contact_force_p95",
    ),
    "a2_hinge_at_crossing": (
        "_a2_hinge_at_crossing_samples",
        "_a2_hinge_at_crossing_sample_mask",
        "a2_hinge_at_crossing_p50",
        "a2_hinge_at_crossing_p95",
    ),
    "a2_stage3_stage4_hinge_velocity": (
        "_a2_stage3_stage4_hinge_velocity_samples",
        "_a2_stage3_stage4_hinge_velocity_sample_mask",
        "a2_stage3_stage4_hinge_velocity_p50",
        "a2_stage3_stage4_hinge_velocity_p95",
    ),
    "a2_hinge_at_release": (
        "_a2_hinge_at_release_samples",
        "_a2_hinge_at_release_sample_mask",
        "a2_hinge_at_release_p50",
        "a2_hinge_at_release_p95",
    ),
    "a2_root_x_at_release": (
        "_a2_root_x_at_release_samples",
        "_a2_root_x_at_release_sample_mask",
        "a2_root_x_at_release_p50",
        "a2_root_x_at_release_p95",
    ),
    "a2_post_release_body_force_max": (
        "_a2_post_release_body_force_max_samples",
        "_a2_post_release_body_force_max_sample_mask",
        "a2_post_release_body_force_max_p50",
        "a2_post_release_body_force_max_p95",
    ),
    "a2_stage0_to1_staging_standoff": (
        "_a2_stage0_to1_staging_standoff_samples",
        "_a2_stage0_to1_staging_standoff_sample_mask",
        "a2_stage0_to1_staging_standoff_p50",
        "a2_stage0_to1_staging_standoff_p95",
    ),
    "a2_stage0_actual_root_height": (
        "_a2_stage0_actual_root_height_samples",
        "_a2_stage0_actual_root_height_sample_mask",
        "a2_stage0_actual_root_height_p50",
        "a2_stage0_actual_root_height_p95",
    ),
    "a2_stage1_actual_root_height": (
        "_a2_stage1_actual_root_height_samples",
        "_a2_stage1_actual_root_height_sample_mask",
        "a2_stage1_actual_root_height_p50",
        "a2_stage1_actual_root_height_p95",
    ),
}
_A2_ROOT_X_FIRST_CROSSING_ENV_COUNT_KEY = "a2_root_x_first_crossing_env_count"
_A2_EVAL_P2_POSTURE_AXIS_KEY = "a2_eval_p2_posture_axis"
_A2_EVAL_M41_STRICT_TELEMETRY_KEY = "a2_eval_m41_strict_telemetry"
_A2_EVAL_V20_STRICT_TELEMETRY_KEY = "a2_eval_v20_strict_telemetry"
_A2_EVAL_P2_POSTURE_AXES = frozenset(("none", "pitch_zero", "roll_zero"))


_A2_V20_TYPED_TELEMETRY_GROUPS = {
    "send": (
        "send_ready",
        "first_send_ready_step",
        "pre_send_root_crossing",
        "first_pre_send_crossing_step",
        "hinge_at_first_root_crossing",
        "root_x_at_first_crossing",
        "root_displacement_se2",
    ),
    "crossing": (
        "valid",
        "crossing_while_holding",
        "hinge_at_crossing",
        "root_x_at_crossing",
    ),
    "release": (
        "valid",
        "hinge_at_release",
        "root_x_at_release",
        "post_release_body_contact",
        "post_release_body_force_max",
    ),
    "carry": (
        "valid_hold",
        "arm_tangent_share",
        "handle_arc_position_error_m",
        "handle_arc_orientation_error_rad",
        "arc_tracking_quality",
        "along_handle_slip_m",
        "orthogonal_arc_residual_m",
    ),
    "smoothness": (
        "hinge_acceleration_p95",
        "hinge_jerk_p95",
        "arm_action_rate_p95",
        "arm_action_jerk_p95",
    ),
}

# Stage-window captures may begin after simulator step zero.  The absolute
# episode-length counter is still required to equal ``step_index + 1``.
_A2_V20_TRACE_TOPOLOGY_SCHEMA = "a2_piper_v20_trace_topology_v2"


def _a2_v20_validate_typed_value(value, field_name, *, allow_na=True):
    """Validate one strict v20 scalar or explicit typed N/A value."""
    if allow_na and isinstance(value, dict) and value.get("status") == "N/A":
        reason = value.get("reason")
        denominator = value.get("denominator")
        if not isinstance(reason, str) or not reason:
            raise RuntimeError(f"A2 v20 {field_name} N/A requires a non-empty reason.")
        if isinstance(denominator, bool) or not isinstance(denominator, (int, float)) or not math.isfinite(float(denominator)) or float(denominator) < 0.0:
            raise RuntimeError(f"A2 v20 {field_name} N/A requires a finite non-negative denominator.")
        if "value" in value and value["value"] is not None:
            raise RuntimeError(f"A2 v20 {field_name} N/A value must be null.")
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise RuntimeError(f"A2 v20 {field_name} must be finite; got {value!r}.")
        return value
    if isinstance(value, (list, tuple)):
        if not value:
            raise RuntimeError(f"A2 v20 {field_name} must not be an empty vector.")
        for index, component in enumerate(value):
            _a2_v20_validate_typed_value(component, f"{field_name}[{index}]", allow_na=False)
        return value
    if value is None and allow_na:
        raise RuntimeError(
            f"A2 v20 {field_name} undefined values require explicit N/A reason and denominator; bare null is invalid."
        )
    raise RuntimeError(f"A2 v20 {field_name} has malformed value {value!r}.")


def _a2_v20_validate_telemetry_group(group_name, group):
    if not isinstance(group, dict):
        raise RuntimeError(f"A2 v20 telemetry group {group_name!r} must be a mapping.")
    expected = _A2_V20_TYPED_TELEMETRY_GROUPS[group_name]
    missing = [field for field in expected if field not in group]
    if missing:
        raise RuntimeError(f"A2 v20 telemetry group {group_name!r} is missing {missing}.")
    for field in expected:
        _a2_v20_validate_typed_value(group[field], f"{group_name}.{field}")
    return True


def validate_a2_v20_telemetry_records(
    records,
    expected_num_envs: int,
    *,
    checkpoint_path: str,
    checkpoint_sha256: str,
    config_hash: str,
    seed: int,
    topology: dict,
):
    """Strictly validate typed v20 rows and provenance before export/selection."""
    if isinstance(expected_num_envs, bool) or not isinstance(expected_num_envs, int) or expected_num_envs <= 0:
        raise RuntimeError("A2 v20 expected_num_envs must be a positive int.")
    if not isinstance(records, list) or len(records) != expected_num_envs:
        raise RuntimeError(
            f"A2 v20 strict telemetry requires exactly {expected_num_envs} rows; got {None if not isinstance(records, list) else len(records)}."
        )
    if not isinstance(checkpoint_path, str) or not checkpoint_path or not isinstance(checkpoint_sha256, str) or len(checkpoint_sha256) != 64 or not isinstance(config_hash, str) or not config_hash or isinstance(seed, bool) or not isinstance(seed, int) or not isinstance(topology, dict):
        raise RuntimeError("A2 v20 strict telemetry provenance fields are malformed.")
    seen = set()
    for row_index, row in enumerate(records):
        if not isinstance(row, dict):
            raise RuntimeError(f"A2 v20 telemetry row {row_index} must be a mapping.")
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < expected_num_envs or env_id in seen:
            raise RuntimeError(f"A2 v20 telemetry row {row_index} has invalid/duplicate env_id={env_id!r}.")
        seen.add(env_id)
        if row.get("checkpoint_path") != checkpoint_path or row.get("checkpoint_sha256") != checkpoint_sha256 or row.get("config_hash") != config_hash or row.get("seed") != seed or row.get("topology") != topology:
            raise RuntimeError(f"A2 v20 telemetry row {row_index} provenance does not bind to the requested checkpoint/config/seed/topology.")
        groups = row.get("groups")
        if not isinstance(groups, dict):
            raise RuntimeError(f"A2 v20 telemetry row {row_index} requires a typed groups mapping.")
        for group_name in _A2_V20_TYPED_TELEMETRY_GROUPS:
            _a2_v20_validate_telemetry_group(group_name, groups.get(group_name))
        for group_name, validity_field in (
            ("crossing", "valid"),
            ("release", "valid"),
            ("carry", "valid_hold"),
        ):
            group = groups[group_name]
            valid = group[validity_field]
            if not isinstance(valid, bool):
                raise RuntimeError(
                    f"A2 v20 telemetry group {group_name!r} validity must be bool."
                )
            fields = [name for name in _A2_V20_TYPED_TELEMETRY_GROUPS[group_name] if name != validity_field]
            na_fields = [
                name
                for name in fields
                if isinstance(group[name], dict) and group[name].get("status") == "N/A"
            ]
            if valid and na_fields:
                raise RuntimeError(
                    f"A2 v20 valid {group_name} group contains typed N/A fields: {na_fields}."
                )
            if not valid and len(na_fields) != len(fields):
                raise RuntimeError(
                    f"A2 v20 invalid {group_name} group must mark every value N/A."
                )
        reward_units = row.get("reward_units")
        if not isinstance(reward_units, dict) or not reward_units:
            raise RuntimeError(f"A2 v20 telemetry row {row_index} requires non-empty reward_units.")
        for reward_name, unit in reward_units.items():
            if not isinstance(reward_name, str) or not reward_name or not isinstance(unit, str) or not unit:
                raise RuntimeError(f"A2 v20 telemetry row {row_index} reward units are malformed.")
        trace = row.get("trace_topology")
        if (
            not isinstance(trace, dict)
            or trace.get("schema") != _A2_V20_TRACE_TOPOLOGY_SCHEMA
            or trace.get("mode") not in {"full_episode", "stage_window"}
            or trace.get("ordered_unique_contiguous") is not True
            or trace.get("terminal_consistent") is not True
            or trace.get("first_episode_identity") is not True
            or trace.get("episode_length_buf_equals_step_index_plus_one") is not True
            or trace.get("captured_span_matches_trace_count") is not True
        ):
            raise RuntimeError(f"A2 v20 telemetry row {row_index} trace topology is not strict-valid.")
    if seen != set(range(expected_num_envs)):
        raise RuntimeError("A2 v20 telemetry rows must cover every env exactly once.")
    return True


def _a2_v20_typed_na(reason, denominator):
    if not isinstance(reason, str) or not reason or isinstance(denominator, bool) or not isinstance(denominator, (int, float)) or not math.isfinite(float(denominator)) or denominator < 0:
        raise RuntimeError("A2 v20 typed N/A requires reason and finite non-negative denominator.")
    return {"status": "N/A", "reason": reason, "denominator": denominator, "value": None}


def _a2_v20_publish_json_exclusive(path, payload):
    """Publish one strict artifact without replacing an existing artifact."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise RuntimeError(f"A2 v20 artifact already exists; refusing overwrite: {destination}")
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=4, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise RuntimeError(
                f"A2 v20 artifact appeared during exclusive publication: {destination}"
            ) from exc
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _a2_v20_percentile(values, probability, reason):
    finite = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise RuntimeError(f"A2 v20 percentile contains malformed value {value!r}.")
        finite.append(float(value))
    if not finite:
        return _a2_v20_typed_na(reason, 0)
    ordered = sorted(finite)
    return ordered[max(0, math.ceil(float(probability) * len(ordered)) - 1)]


def _build_a2_v20_strict_telemetry_records(
    eval_dict,
    trace_records,
    expected_num_envs,
    *,
    checkpoint_path,
    checkpoint_sha256,
    config_hash,
    seed,
    topology,
):
    """Build one typed v20 evidence row per first-episode environment."""
    diagnostics = eval_dict.get("episode_terminal_diagnostics") if isinstance(eval_dict, dict) else None
    goals = eval_dict.get("episode_goal_reached") if isinstance(eval_dict, dict) else None
    if not isinstance(diagnostics, list) or len(diagnostics) != expected_num_envs or not isinstance(goals, list) or len(goals) != expected_num_envs:
        raise RuntimeError("A2 v20 strict exporter requires complete terminal diagnostics and goal flags.")
    if not isinstance(trace_records, list) or not trace_records:
        raise RuntimeError("A2 v20 strict exporter requires non-empty first-episode trace records.")
    by_env = {env_id: [] for env_id in range(expected_num_envs)}
    for row_index, row in enumerate(trace_records):
        if not isinstance(row, dict):
            raise RuntimeError(f"A2 v20 trace row {row_index} must be a mapping.")
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in by_env:
            raise RuntimeError(f"A2 v20 trace row {row_index} has invalid env_id={env_id!r}.")
        episode_index = row.get("episode_index")
        if (
            isinstance(episode_index, bool)
            or not isinstance(episode_index, int)
            or episode_index != 0
            or row.get("first_episode_active") is not True
        ):
            raise RuntimeError("A2 v20 strict trace rejects non-first-episode rows.")
        by_env[env_id].append(row)
    diagnostic_by_env = {}
    goal_by_env = {}
    for diagnostic_index, diagnostic in enumerate(diagnostics):
        if not isinstance(diagnostic, dict):
            raise RuntimeError("A2 v20 terminal diagnostics must be mappings.")
        env_id = diagnostic.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in by_env or env_id in diagnostic_by_env:
            raise RuntimeError(f"A2 v20 terminal diagnostics has invalid/duplicate env_id={env_id!r}.")
        diagnostic_by_env[env_id] = diagnostic
        goal_value = goals[diagnostic_index]
        if not isinstance(goal_value, bool):
            raise RuntimeError(f"A2 v20 goal flag for env{env_id} must be bool.")
        goal_by_env[env_id] = goal_value
    records = []
    for env_id in range(expected_num_envs):
        trace = by_env[env_id]
        if not trace:
            raise RuntimeError(f"A2 v20 strict exporter has no trace rows for env{env_id}.")
        steps = [row.get("step_index") for row in trace]
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in steps):
            raise RuntimeError(f"A2 v20 env{env_id} step indices are malformed.")
        ordered_unique = steps == sorted(set(steps)) and all(right == left + 1 for left, right in zip(steps, steps[1:]))
        if not ordered_unique:
            raise RuntimeError(f"A2 v20 env{env_id} trace is not ordered, unique, and contiguous.")
        diagnostic = diagnostic_by_env[env_id]
        terminal_reason = diagnostic.get("terminal_reasons")
        episode_lengths = [row.get("episode_length_buf") for row in trace]
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in episode_lengths
        ):
            raise RuntimeError(f"A2 v20 env{env_id} episode_length_buf values must be positive ints.")
        lengths_contiguous = all(
            right == left + 1 for left, right in zip(episode_lengths, episode_lengths[1:])
        )
        if not lengths_contiguous:
            raise RuntimeError(
                f"A2 v20 env{env_id} episode_length_buf must be ordered and contiguous."
            )
        if any(length != step + 1 for step, length in zip(steps, episode_lengths)):
            raise RuntimeError(
                f"A2 v20 env{env_id} episode_length_buf must equal step_index + 1 for every captured row."
            )
        if (
            not isinstance(terminal_reason, str)
            or not terminal_reason
            or trace[-1].get("terminal_reasons") != terminal_reason
            or any(row.get("terminal_reasons") != "unknown_reset" for row in trace[:-1])
        ):
            raise RuntimeError(f"A2 v20 env{env_id} terminal trace is inconsistent.")
        terminal_length = diagnostic.get("episode_length_buf")
        if (
            isinstance(terminal_length, bool)
            or not isinstance(terminal_length, int)
            or terminal_length <= 0
            or episode_lengths[-1] != terminal_length
            or len(steps) != steps[-1] - steps[0] + 1
        ):
            raise RuntimeError(
                f"A2 v20 env{env_id} terminal episode_length_buf/span consistency is invalid."
            )
        dt = diagnostic.get("control_dt")
        if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(float(dt)) or float(dt) <= 0:
            raise RuntimeError(f"A2 v20 env{env_id} control_dt must be finite and positive.")
        dt = float(dt)
        carry_rows = [row for row in trace if row.get("v20_carry_valid") is True]
        carry_denominator = len(carry_rows)
        def carry_value(field, probability, reason):
            return _a2_v20_percentile([row[field] for row in carry_rows], probability, reason)
        hinge_vel = [float(row["door_hinge_joint_vel"]) for row in trace]
        hinge_accel = [abs(right - left) / dt for left, right in zip(hinge_vel, hinge_vel[1:])]
        hinge_jerk = [abs(right - left) / dt for left, right in zip(hinge_accel, hinge_accel[1:])]
        arm_actions = []
        for row in trace:
            action = row.get("post_delta_post_warp_env_action")
            if not isinstance(action, list) or len(action) != 12:
                raise RuntimeError(f"A2 v20 env{env_id} requires 12-D post-delta/post-warp actions.")
            arm_actions.append(torch.tensor(action[5:11], dtype=torch.float64))
        arm_rate = [float(torch.linalg.norm(right - left).item()) / dt for left, right in zip(arm_actions, arm_actions[1:])]
        arm_jerk = [abs(right - left) / dt for left, right in zip(arm_rate, arm_rate[1:])]
        crossing_rows = [row for row in trace if row.get("root_x_ever_crossed") is True]
        crossing_index = trace.index(crossing_rows[0]) if crossing_rows else None
        pre_crossing = trace[: crossing_index + 1] if crossing_index is not None else []
        def fraction(rows, predicate, reason):
            if not rows:
                return _a2_v20_typed_na(reason, 0)
            return sum(bool(predicate(row)) for row in rows) / len(rows)
        held_hinge = [float(row["door_hinge_joint_pos"]) for row in trace if row.get("both_contact") is True]
        positive_hinge_vel = [value for value in hinge_vel if value > 0.0]
        reward_sums = diagnostic.get("reward_episode_sums")
        if not isinstance(reward_sums, dict) or not reward_sums:
            raise RuntimeError(f"A2 v20 env{env_id} requires non-empty episode reward sums.")
        first_send = diagnostic.get("v20_first_send_ready_step")
        first_pre = diagnostic.get("v20_first_pre_send_crossing_step")
        first_crossing = diagnostic.get("v20_first_root_crossing_step")
        if first_crossing is None:
            crossing_valid = False
        elif isinstance(first_crossing, bool) or not isinstance(first_crossing, int):
            raise RuntimeError(f"A2 v20 env{env_id} first root crossing step is malformed.")
        else:
            crossing_valid = first_crossing >= 0
        release_fields = tuple(
            diagnostic.get(name)
            for name in (
                "hinge_at_release",
                "root_x_at_release",
                "post_release_body_contact",
                "post_release_body_force_max",
            )
        )
        release_present = [value is not None for value in release_fields]
        if any(release_present) and not all(release_present):
            raise RuntimeError(f"A2 v20 env{env_id} release fields must be all-present or all-absent.")
        release_valid = all(release_present)
        bilateral_stage3 = [
            row
            for row in trace
            if row.get("stage_buf") == 3 and row.get("both_contact") is True
        ]
        opening_slip_deltas = []
        for left, right in zip(bilateral_stage3, bilateral_stage3[1:]):
            left_position = left.get("target_pos_source_handle")
            right_position = right.get("target_pos_source_handle")
            if (
                not isinstance(left_position, list)
                or len(left_position) < 2
                or not isinstance(right_position, list)
                or len(right_position) < 2
            ):
                raise RuntimeError(
                    f"A2 v20 env{env_id} bilateral stage3 trace lacks target_pos_source_handle[1]."
                )
            delta = abs(float(right_position[1]) - float(left_position[1]))
            if not math.isfinite(delta):
                raise RuntimeError(f"A2 v20 env{env_id} opening slip contains a non-finite delta.")
            opening_slip_deltas.append(delta)
        opening_slip = (
            sum(opening_slip_deltas)
            if opening_slip_deltas
            else _a2_v20_typed_na("fewer_than_two_bilateral_stage3_samples", 0)
        )
        groups = {
            "send": {
                "send_ready": diagnostic["v20_send_ready"],
                "first_send_ready_step": first_send if first_send is not None else _a2_v20_typed_na("send_ready_not_reached", 0),
                "pre_send_root_crossing": diagnostic["v20_pre_send_root_crossing"],
                "first_pre_send_crossing_step": first_pre if first_pre is not None else _a2_v20_typed_na("no_pre_send_root_crossing", 0),
                "hinge_at_first_root_crossing": diagnostic["v20_hinge_at_first_root_crossing"] if diagnostic["v20_hinge_at_first_root_crossing"] is not None else _a2_v20_typed_na("no_root_crossing", 0),
                "root_x_at_first_crossing": diagnostic["v20_root_x_at_first_crossing"] if diagnostic["v20_root_x_at_first_crossing"] is not None else _a2_v20_typed_na("no_root_crossing", 0),
                "root_displacement_se2": diagnostic["v20_root_displacement_se2"],
            },
            "crossing": {
                "valid": crossing_valid,
                "crossing_while_holding": (
                    bool(crossing_rows[0].get("both_contact"))
                    if crossing_valid and crossing_rows
                    else _a2_v20_typed_na("no_root_crossing", 0)
                ),
                "hinge_at_crossing": (
                    diagnostic["v20_hinge_at_first_root_crossing"]
                    if crossing_valid
                    else _a2_v20_typed_na("no_root_crossing", 0)
                ),
                "root_x_at_crossing": (
                    diagnostic["v20_root_x_at_first_crossing"]
                    if crossing_valid
                    else _a2_v20_typed_na("no_root_crossing", 0)
                ),
            },
            "release": {
                "valid": release_valid,
                "hinge_at_release": diagnostic["hinge_at_release"] if release_valid else _a2_v20_typed_na("no_release", 0),
                "root_x_at_release": diagnostic["root_x_at_release"] if release_valid else _a2_v20_typed_na("no_release", 0),
                "post_release_body_contact": diagnostic["post_release_body_contact"] if release_valid else _a2_v20_typed_na("no_release", 0),
                "post_release_body_force_max": diagnostic["post_release_body_force_max"] if release_valid else _a2_v20_typed_na("no_release", 0),
            },
            "carry": {
                "valid_hold": carry_denominator > 0,
                "arm_tangent_share": carry_value("v20_arm_tangent_share", 0.50, "no_valid_hold_samples"),
                "handle_arc_position_error_m": carry_value("v20_handle_arc_position_error_m", 0.95, "no_valid_hold_samples"),
                "handle_arc_orientation_error_rad": carry_value("v20_handle_arc_orientation_error_rad", 0.95, "no_valid_hold_samples"),
                "arc_tracking_quality": carry_value("v20_arc_tracking_quality", 0.50, "no_valid_hold_samples"),
                "along_handle_slip_m": carry_value("v20_along_handle_slip_m", 0.95, "no_valid_hold_samples"),
                "orthogonal_arc_residual_m": carry_value("v20_orthogonal_arc_residual_m", 0.95, "no_valid_hold_samples"),
            },
            "smoothness": {
                "hinge_acceleration_p95": _a2_v20_percentile(hinge_accel, 0.95, "fewer_than_two_hinge_samples"),
                "hinge_jerk_p95": _a2_v20_percentile(hinge_jerk, 0.95, "fewer_than_three_hinge_samples"),
                "arm_action_rate_p95": _a2_v20_percentile(arm_rate, 0.95, "fewer_than_two_arm_action_samples"),
                "arm_action_jerk_p95": _a2_v20_percentile(arm_jerk, 0.95, "fewer_than_three_arm_action_samples"),
            },
        }
        records.append(
            {
                "env_id": env_id,
                "checkpoint_path": checkpoint_path,
                "checkpoint_sha256": checkpoint_sha256,
                "config_hash": config_hash,
                "seed": seed,
                "topology": topology,
                "goal_reached": goal_by_env[env_id],
                "terminal_reason": terminal_reason,
                "groups": groups,
                "episode_metrics": {
                    "pre_crossing_bilateral": fraction(pre_crossing, lambda row: row.get("both_contact") is True, "no_root_crossing"),
                    "pre_crossing_coasting": fraction(pre_crossing, lambda row: abs(float(row["physical_base_command"][0])) <= 0.10, "no_root_crossing"),
                    "pre_crossing_over_force": fraction(pre_crossing, lambda row: row.get("over_force") is True, "no_root_crossing"),
                    "held_hinge": max(held_hinge) if held_hinge else _a2_v20_typed_na("no_bilateral_hold_samples", 0),
                    "opening_slip_m": opening_slip,
                    "positive_hinge_velocity_p95": _a2_v20_percentile(positive_hinge_vel, 0.95, "no_positive_hinge_velocity",  ),
                    "task_time_s": float(diagnostic["episode_length_buf"]) * dt,
                },
                "reward_units": {name: "episode-sum" for name in sorted(reward_sums)},
                "trace_topology": {
                    "schema": _A2_V20_TRACE_TOPOLOGY_SCHEMA,
                    "mode": "full_episode" if steps[0] == 0 else "stage_window",
                    "first_episode_identity": True,
                    "ordered_unique_contiguous": True,
                    "terminal_consistent": True,
                    "episode_length_buf_equals_step_index_plus_one": True,
                    "captured_span_matches_trace_count": len(steps) == steps[-1] - steps[0] + 1,
                    "first_step_index": steps[0],
                    "last_step_index": steps[-1],
                    "episode_length_first": episode_lengths[0],
                    "episode_length_last": episode_lengths[-1],
                    "sample_count": len(steps),
                },
            }
        )
    validate_a2_v20_telemetry_records(
        records,
        expected_num_envs,
        checkpoint_path=checkpoint_path,
        checkpoint_sha256=checkpoint_sha256,
        config_hash=config_hash,
        seed=seed,
        topology=topology,
    )
    return records


def _a2_v20_config_hash(config):
    if OmegaConf.is_config(config):
        value = OmegaConf.to_container(config, resolve=True)
    elif isinstance(config, dict):
        value = config
    elif hasattr(config, "to_dict") and callable(config.to_dict):
        value = config.to_dict()
    else:
        raise RuntimeError(
            f"A2 v20 config hash requires OmegaConf/dict/to_dict config; got {type(config).__name__}."
        )
    try:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("A2 v20 config hash requires a finite JSON configuration.") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_a2_eval_p2_posture_axis(eval_config):
    """Parse the eval-only P2 posture discriminator selector."""
    value = eval_config.get(_A2_EVAL_P2_POSTURE_AXIS_KEY, "none")
    if value is None:
        return "none"
    if isinstance(value, bool) or not isinstance(value, str):
        raise RuntimeError(
            f"eval.{_A2_EVAL_P2_POSTURE_AXIS_KEY} must be absent/None or one of "
            f"{sorted(_A2_EVAL_P2_POSTURE_AXES)}; got {value!r}."
        )
    if value not in _A2_EVAL_P2_POSTURE_AXES:
        raise RuntimeError(
            f"eval.{_A2_EVAL_P2_POSTURE_AXIS_KEY} must be one of "
            f"{sorted(_A2_EVAL_P2_POSTURE_AXES)}; got {value!r}."
        )
    return value


def _apply_a2_eval_p2_posture_axis(action_mean, action_layout, posture_axis):
    """Apply the eval-only P2 pitch/roll zero clamp to high-level base actions."""
    if posture_axis not in _A2_EVAL_P2_POSTURE_AXES:
        raise RuntimeError(
            "A2 P2 posture selector must be one of "
            f"{sorted(_A2_EVAL_P2_POSTURE_AXES)}; got {posture_axis!r}."
        )
    if (
        not isinstance(action_layout, dict)
        or not isinstance(action_layout.get("dim"), int)
        or isinstance(action_layout.get("dim"), bool)
        or action_layout["dim"] <= 0
    ):
        raise RuntimeError(
            "A2 P2 posture selector requires a canonical action layout with a positive dim."
        )
    expected_dim = action_layout["dim"]
    if (
        not torch.is_tensor(action_mean)
        or action_mean.ndim != 2
        or action_mean.shape[1] != expected_dim
        or not torch.is_floating_point(action_mean)
        or not torch.all(torch.isfinite(action_mean))
    ):
        shape = None if not torch.is_tensor(action_mean) else tuple(action_mean.shape)
        dtype = None if not torch.is_tensor(action_mean) else action_mean.dtype
        raise RuntimeError(
            "A2 P2 posture selector requires finite floating action_mean shape "
            f"(num_envs, {expected_dim}); got shape={shape}, dtype={dtype}."
        )
    if posture_axis == "none":
        return action_mean

    base_start = action_layout.get("base_start")
    base_end = action_layout.get("base_end")
    if (
        isinstance(base_start, bool)
        or not isinstance(base_start, int)
        or isinstance(base_end, bool)
        or not isinstance(base_end, int)
        or base_start < 0
        or base_end - base_start != 5
        or base_end > expected_dim
    ):
        raise RuntimeError(
            "A2 P2 posture selector requires a canonical five-dimensional base action "
            f"slice; got base_start={base_start!r}, base_end={base_end!r}, dim={expected_dim}."
        )
    selected_index = base_start + (3 if posture_axis == "pitch_zero" else 4)
    applied = action_mean.clone()
    applied[:, selected_index] = 0.0
    return applied


def _canonicalize_a2_metric_device(device):
    """Resolve an indexless CUDA device before strict telemetry validation."""
    if not isinstance(device, torch.device):
        raise TypeError(f"A2 metric aggregation device must be torch.device; got {device!r}.")
    if device.type == "cuda" and device.index is None:
        return torch.device("cuda", torch.cuda.current_device())
    return device


def _prepare_a2_env_metrics_for_aggregation(step_env_metrics, accelerator, device):
    """Prepare A2 telemetry for rank-global metering and eval logging."""
    if not isinstance(step_env_metrics, dict):
        raise TypeError(
            "A2 step environment metrics must be a shallow dict; "
            f"got {type(step_env_metrics).__name__}."
        )
    device = _canonicalize_a2_metric_device(device)
    gather = getattr(accelerator, "gather", None)
    if not callable(gather):
        raise TypeError("A2 metric aggregation requires accelerator.gather().")

    prepared = dict(step_env_metrics)
    count_key = _A2_ROOT_X_FIRST_CROSSING_ENV_COUNT_KEY
    if count_key in prepared:
        count = prepared[count_key]
        if (
            not torch.is_tensor(count)
            or count.ndim != 0
            or not count.is_floating_point()
            or not bool(torch.all(torch.isfinite(count)))
            or bool(torch.any(count < 0.0))
            or count.device != device
        ):
            raise ValueError(
                "A2 root-X crossing count requires a finite non-negative floating "
                f"scalar on {device}; got {count!r}."
            )
        gathered_count = gather(count)
        if (
            not torch.is_tensor(gathered_count)
            or gathered_count.dtype != count.dtype
            or gathered_count.device != device
        ):
            raise RuntimeError(
                "A2 root-X crossing count gather must preserve floating dtype and device; "
                f"got {gathered_count!r}."
            )
        global_count = gathered_count.sum()
        if (
            global_count.ndim != 0
            or not global_count.is_floating_point()
            or not bool(torch.all(torch.isfinite(global_count)))
            or bool(global_count < 0.0)
        ):
            raise RuntimeError("A2 gathered root-X crossing count is invalid.")
        prepared[count_key] = global_count

    active_ratio_specs = []
    for ratio_key, (numerator_key, denominator_key) in {
        **_A2_EVAL_OPTIONAL_RATIO_SPECS,
        "a2_crossing_while_holding_frac": (
            "a2_crossing_while_holding_numerator_frac",
            "a2_crossing_while_holding_denominator_frac",
        ),
    }.items():
        ratio_keys = (ratio_key, numerator_key, denominator_key)
        present = tuple(key in prepared for key in ratio_keys)
        if not any(present):
            continue
        if not all(present):
            raise ValueError(
                "A2 conditional ratio telemetry requires complete public, numerator, "
                f"and denominator fields for {ratio_key!r}."
            )

        ratio = prepared[ratio_key]
        numerator = prepared[numerator_key]
        denominator = prepared[denominator_key]
        values = (ratio, numerator, denominator)
        if (
            not all(torch.is_tensor(value) for value in values)
            or not all(value.ndim == 0 for value in values)
            or not all(value.is_floating_point() for value in values)
            or not all(value.device == device for value in values)
            or len({value.dtype for value in values}) != 1
            or not all(bool(torch.all(torch.isfinite(value))) for value in values)
            or bool(numerator < 0.0)
            or bool(numerator > denominator)
            or bool(denominator < 0.0)
        ):
            raise ValueError(
                "A2 conditional ratio telemetry requires finite floating scalar "
                f"tensors on {device} with 0 <= numerator <= denominator; got "
                f"ratio={ratio!r}, numerator={numerator!r}, denominator={denominator!r}."
            )
        active_ratio_specs.append((ratio_key, numerator_key, denominator_key))

    if active_ratio_specs:
        packed_values = []
        for _ratio_key, numerator_key, denominator_key in active_ratio_specs:
            packed_values.extend((prepared[numerator_key], prepared[denominator_key]))
        packed = torch.stack(packed_values)
        packed_width = packed.numel()
        gathered_ratios = gather(packed)
        if (
            not torch.is_tensor(gathered_ratios)
            or gathered_ratios.dtype != packed.dtype
            or gathered_ratios.device != device
            or gathered_ratios.ndim == 0
            or gathered_ratios.numel() == 0
            or gathered_ratios.numel() % packed_width != 0
            or (
                gathered_ratios.ndim > 1
                and gathered_ratios.shape[-1] != packed_width
            )
        ):
            raise RuntimeError(
                "A2 conditional ratio gather must preserve dtype/device and expose "
                f"a packed width of {packed_width}; got {gathered_ratios!r}."
            )
        gathered_ratios = gathered_ratios.reshape(-1, packed_width)
        if not bool(torch.all(torch.isfinite(gathered_ratios))):
            raise RuntimeError("A2 gathered conditional ratio telemetry must be finite.")
        global_ratios = gathered_ratios.sum(dim=0)
        for index, (_ratio_key, numerator_key, denominator_key) in enumerate(
            active_ratio_specs
        ):
            numerator = global_ratios[2 * index]
            denominator = global_ratios[2 * index + 1]
            if (
                not bool(torch.all(torch.isfinite(numerator)))
                or not bool(torch.all(torch.isfinite(denominator)))
                or bool(numerator < 0.0)
                or bool(numerator > denominator)
                or bool(denominator < 0.0)
            ):
                raise RuntimeError(
                    "A2 gathered conditional ratio telemetry must satisfy "
                    f"0 <= numerator <= denominator; got numerator={numerator!r}, "
                    f"denominator={denominator!r}."
                )
            prepared[numerator_key] = numerator
            prepared[denominator_key] = denominator
            del prepared[_ratio_key]
    for (
        _metric_name,
        (samples_key, mask_key, p50_key, p95_key),
    ) in _A2_GLOBAL_ENV_QUANTILE_SPECS.items():
        quantile_keys = (samples_key, mask_key, p50_key, p95_key)
        if not any(key in prepared for key in quantile_keys):
            continue
        if samples_key not in prepared or mask_key not in prepared:
            raise ValueError(
                f"A2 quantile telemetry requires both {samples_key!r} and {mask_key!r}."
            )
        samples = prepared[samples_key]
        sample_mask = prepared[mask_key]
        if (
            not torch.is_tensor(samples)
            or samples.ndim != 1
            or samples.numel() == 0
            or not samples.is_floating_point()
            or not bool(torch.all(torch.isfinite(samples)))
            or samples.device != device
            or not torch.is_tensor(sample_mask)
            or sample_mask.ndim != 1
            or sample_mask.shape != samples.shape
            or sample_mask.dtype != torch.bool
            or sample_mask.device != device
        ):
            raise ValueError(
                "A2 quantile telemetry requires non-empty finite floating samples and "
                f"a same-shape bool mask on {device}; got samples={samples!r}, "
                f"mask={sample_mask!r}."
            )

        gathered_samples = gather(samples)
        gathered_mask = gather(sample_mask)
        if (
            not torch.is_tensor(gathered_samples)
            or gathered_samples.dtype != samples.dtype
            or gathered_samples.device != device
            or not torch.is_tensor(gathered_mask)
            or gathered_mask.dtype != torch.bool
            or gathered_mask.device != device
        ):
            raise RuntimeError(
                "A2 quantile gather must preserve sample/mask dtype and device."
            )
        global_samples = gathered_samples.reshape(-1)
        global_mask = gathered_mask.reshape(-1)
        if global_samples.shape != global_mask.shape or global_samples.numel() == 0:
            raise RuntimeError(
                "A2 gathered quantile samples and mask must be non-empty and same-shape."
            )
        if not bool(torch.all(torch.isfinite(global_samples))):
            raise RuntimeError("A2 gathered quantile samples must be finite.")
        active_samples = global_samples[global_mask]
        if active_samples.numel() == 0:
            p50 = torch.zeros((), dtype=samples.dtype, device=device)
            p95 = torch.zeros((), dtype=samples.dtype, device=device)
        else:
            p50 = torch.quantile(active_samples, 0.50)
            p95 = torch.quantile(active_samples, 0.95)
        prepared[p50_key] = p50
        prepared[p95_key] = p95
        del prepared[samples_key]
        del prepared[mask_key]

    return prepared


def _finalize_a2_conditional_ratios(metrics):
    """Reconstruct finalized conditional ratios after temporal metering."""
    if not isinstance(metrics, dict):
        raise TypeError(
            "A2 conditional ratio finalization requires a dict; "
            f"got {type(metrics).__name__}."
        )

    finalized = dict(metrics)
    for ratio_key, (numerator_key, denominator_key) in {
        **_A2_EVAL_OPTIONAL_RATIO_SPECS,
        "a2_crossing_while_holding_frac": (
            "a2_crossing_while_holding_numerator_frac",
            "a2_crossing_while_holding_denominator_frac",
        ),
    }.items():
        ratio_keys = (ratio_key, numerator_key, denominator_key)
        present = tuple(key in finalized for key in ratio_keys)
        if not any(present):
            continue
        if ratio_key in finalized:
            raise ValueError(
                f"A2 conditional ratio {ratio_key!r} must be absent before finalization."
            )
        if numerator_key not in finalized or denominator_key not in finalized:
            raise ValueError(
                "A2 conditional ratio finalization requires complete numerator and "
                f"denominator fields for {ratio_key!r}."
            )

        numerator = finalized[numerator_key]
        denominator = finalized[denominator_key]
        if (
            not torch.is_tensor(numerator)
            or not torch.is_tensor(denominator)
            or numerator.ndim != 0
            or denominator.ndim != 0
            or not numerator.is_floating_point()
            or not denominator.is_floating_point()
            or numerator.dtype != denominator.dtype
            or numerator.device != denominator.device
            or not bool(torch.all(torch.isfinite(numerator)))
            or not bool(torch.all(torch.isfinite(denominator)))
            or bool(numerator < 0.0)
            or bool(numerator > denominator)
            or bool(denominator < 0.0)
        ):
            raise ValueError(
                "A2 conditional ratio finalization requires finite floating scalar "
                "numerator/denominator tensors with 0 <= numerator <= denominator; "
                f"got numerator={numerator!r}, denominator={denominator!r}."
            )

        ratio = torch.where(
            denominator > 0.0,
            numerator / denominator,
            torch.zeros_like(denominator),
        )
        if not bool(torch.all(torch.isfinite(ratio))):
            raise RuntimeError(
                f"A2 finalized conditional ratio {ratio_key!r} must be finite."
            )
        finalized[ratio_key] = ratio

    return finalized


def _build_a2_v14_eval_records(eval_dict, seed, expected_num_envs, *, include_m38_fields=False):
    """Build one strict v14 bucket-report record per first-episode environment."""
    if (
        not isinstance(eval_dict, dict)
        or isinstance(seed, bool)
        or not isinstance(seed, int)
        or isinstance(expected_num_envs, bool)
        or not isinstance(expected_num_envs, int)
        or expected_num_envs <= 0
    ):
        raise ValueError(
            "A2 v14 eval records require a summary dict, integer seed, and "
            "positive expected_num_envs."
        )
    diagnostics = eval_dict.get("episode_terminal_diagnostics")
    goal_reached = eval_dict.get("episode_goal_reached")
    max_stage = eval_dict.get("episode_max_stage_reached")
    for field_name, field_value in (
        ("episode_terminal_diagnostics", diagnostics),
        ("episode_goal_reached", goal_reached),
        ("episode_max_stage_reached", max_stage),
    ):
        if not isinstance(field_value, list) or len(field_value) != expected_num_envs:
            raise ValueError(
                f"A2 v14 eval summary requires {field_name} list length "
                f"{expected_num_envs}; got "
                f"{None if not isinstance(field_value, list) else len(field_value)}."
            )

    metadata_fields = (
        "door_hinge_drive_max_force",
        "door_handle_drive_max_force",
        "door_handle_height",
        "door_weight",
    )
    telemetry_fields = (
        "crossing_while_holding",
        "hinge_at_crossing",
        "hinge_at_release",
        "root_x_at_release",
        "post_release_body_contact",
        "post_release_body_force_max",
        "stage0_to1_staging_standoff",
        "stage0_actual_root_height",
        "stage1_actual_root_height",
    )
    records = []
    seen_env_ids = set()
    for index, diagnostic in enumerate(diagnostics):
        if not isinstance(diagnostic, dict):
            raise ValueError(
                f"A2 v14 terminal diagnostic {index} must be a dict."
            )
        m38_fields = (
            "episode_length_buf",
            "control_dt",
            "root_pos_rel",
            "reward_episode_sums",
        )
        required = (
            "env_id",
            "stage_buf",
            *metadata_fields,
            *telemetry_fields,
            *(m38_fields if include_m38_fields else ()),
        )
        missing = [field_name for field_name in required if field_name not in diagnostic]
        if missing:
            raise ValueError(
                f"A2 v14 terminal diagnostic {index} is missing {missing}."
            )
        env_id = diagnostic["env_id"]
        if (
            isinstance(env_id, bool)
            or not isinstance(env_id, int)
            or env_id < 0
            or env_id >= expected_num_envs
            or env_id in seen_env_ids
        ):
            raise ValueError(
                f"A2 v14 terminal diagnostic has invalid/duplicate env_id={env_id!r}."
            )
        seen_env_ids.add(env_id)
        goal_value = goal_reached[index]
        if not isinstance(goal_value, bool):
            raise ValueError(
                f"A2 v14 episode_goal_reached[{index}] must be bool; "
                f"got {goal_value!r}."
            )
        max_stage_value = max_stage[index]
        final_stage_value = diagnostic["stage_buf"]
        for field_name, stage_value in (
            ("episode_max_stage_reached", max_stage_value),
            ("stage_buf", final_stage_value),
        ):
            if (
                isinstance(stage_value, bool)
                or not isinstance(stage_value, int)
                or not 0 <= stage_value <= 5
            ):
                raise ValueError(
                    f"A2 v14 {field_name}[{index}] must be an integer in [0,5]; "
                    f"got {stage_value!r}."
                )
        if final_stage_value > max_stage_value:
            raise ValueError(
                f"A2 v14 stage_buf[{index}]={final_stage_value} cannot exceed "
                f"episode_max_stage_reached[{index}]={max_stage_value}."
            )
        record = {
            "seed": seed,
            "env_id": env_id,
            "goal_reached": goal_value,
            "max_stage": max_stage_value,
            "final_stage": final_stage_value,
        }
        for field_name in (*metadata_fields, *telemetry_fields):
            record[field_name] = diagnostic[field_name]
        if include_m38_fields:
            for field_name in (
                "episode_length_buf",
                "control_dt",
                "root_pos_rel",
                "reward_episode_sums",
            ):
                record[field_name] = diagnostic[field_name]
        records.append(record)

    expected_ids = set(range(expected_num_envs))
    if seen_env_ids != expected_ids:
        raise ValueError(
            "A2 v14 eval records require exactly one record for each env id; "
            f"missing={sorted(expected_ids - seen_env_ids)}, "
            f"extra={sorted(seen_env_ids - expected_ids)}."
        )
    return sorted(records, key=lambda record: record["env_id"])


_A2_M41_RESULT_REQUIRED_FLOAT_FIELDS = (
    "door_hinge_drive_max_force",
    "door_handle_drive_max_force",
    "door_handle_height",
    "door_weight",
    "hinge_at_crossing",
    "hinge_at_release",
    "root_x_at_release",
    "post_release_body_force_max",
    "stage0_to1_staging_standoff",
    "stage0_actual_root_height",
    "stage1_actual_root_height",
)
_A2_M41_RESULT_REQUIRED_BOOL_FIELDS = (
    "crossing_while_holding",
    "post_release_body_contact",
)
_A2_M41_TRACE_REQUIRED_FIELDS = (
    "env_id",
    "episode_index",
    "first_episode_active",
    "stage_buf",
    "step_index",
    "episode_length_buf",
    "control_dt",
    "target_pos_source_handle",
    "both_contact",
    "terminal_reasons",
    "door_hinge_drive_max_force",
    "door_handle_height",
    "door_weight",
    "door_body_panel_normal_force_per_filter",
    "door_body_panel_normal_force_total",
    "door_arm_panel_normal_force_per_filter",
    "door_arm_panel_normal_force_total",
    "physical_base_command",
    "arm_j7_j8_pos",
    "arm_j7_j8_open_target",
    "over_force",
    "door_hinge_joint_vel",
    "root_x_ever_crossed",
    "root_pos_rel",
    "reward_episode_sums",
)


def _a2_m41_finite_scalar(value, field_name, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"A2 M41 {field_name} must be a finite number; got {value!r}.")
    value = float(value)
    if not math.isfinite(value):
        raise RuntimeError(f"A2 M41 {field_name} must be finite; got {value!r}.")
    if positive and value <= 0.0:
        raise RuntimeError(f"A2 M41 {field_name} must be positive; got {value!r}.")
    if nonnegative and value < 0.0:
        raise RuntimeError(f"A2 M41 {field_name} must be non-negative; got {value!r}.")
    return value


def _a2_m41_finite_vector(value, field_name, length):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise RuntimeError(
            f"A2 M41 {field_name} must contain exactly {length} finite values; got {value!r}."
        )
    return tuple(_a2_m41_finite_scalar(component, f"{field_name}[{index}]") for index, component in enumerate(value))


def _a2_m41_reward_sums(value, field_name):
    if not isinstance(value, dict) or not value:
        raise RuntimeError(f"A2 M41 {field_name} must be a non-empty mapping.")
    if any(not isinstance(name, str) or not name for name in value):
        raise RuntimeError(f"A2 M41 {field_name} keys must be non-empty strings.")
    for name, component in value.items():
        _a2_m41_finite_scalar(component, f"{field_name}.{name}")
    return tuple(sorted(value))


def _validate_a2_m41_result_records(eval_dict, expected_num_envs):
    if not isinstance(eval_dict, dict):
        raise RuntimeError("A2 M41 strict telemetry requires an eval summary dict.")
    if (
        isinstance(expected_num_envs, bool)
        or not isinstance(expected_num_envs, int)
        or expected_num_envs <= 0
    ):
        raise RuntimeError(
            f"A2 M41 strict telemetry requires positive expected_num_envs; got {expected_num_envs!r}."
        )
    diagnostics = eval_dict.get("episode_terminal_diagnostics")
    goals = eval_dict.get("episode_goal_reached")
    max_stages = eval_dict.get("episode_max_stage_reached")
    for field_name, values in (
        ("episode_terminal_diagnostics", diagnostics),
        ("episode_goal_reached", goals),
        ("episode_max_stage_reached", max_stages),
    ):
        if not isinstance(values, list) or len(values) != expected_num_envs:
            raise RuntimeError(
                f"A2 M41 strict telemetry requires {field_name} list length "
                f"{expected_num_envs}; got {None if not isinstance(values, list) else len(values)}."
            )

    result_by_env = {}
    for index, diagnostic in enumerate(diagnostics):
        if not isinstance(diagnostic, dict):
            raise RuntimeError(f"A2 M41 terminal row {index} must be a mapping.")
        required = (
            "env_id",
            "stage_buf",
            "time_in_stage_buf",
            "episode_length_buf",
            "control_dt",
            "terminal_reasons",
            *_A2_M41_RESULT_REQUIRED_FLOAT_FIELDS,
            *_A2_M41_RESULT_REQUIRED_BOOL_FIELDS,
            "root_pos_rel",
            "reward_episode_sums",
        )
        missing = [name for name in required if name not in diagnostic]
        if missing:
            raise RuntimeError(f"A2 M41 terminal row {index} is missing {missing}.")
        env_id = diagnostic["env_id"]
        if (
            isinstance(env_id, bool)
            or not isinstance(env_id, int)
            or not 0 <= env_id < expected_num_envs
            or env_id in result_by_env
        ):
            raise RuntimeError(f"A2 M41 terminal row {index} has invalid/ambiguous env_id={env_id!r}.")
        stage = diagnostic["stage_buf"]
        max_stage = max_stages[index]
        if (
            isinstance(stage, bool)
            or not isinstance(stage, int)
            or not 0 <= stage <= 5
            or isinstance(max_stage, bool)
            or not isinstance(max_stage, int)
            or not 0 <= max_stage <= 5
            or stage > max_stage
        ):
            raise RuntimeError(
                f"A2 M41 terminal row {index} requires integer stage_buf/max_stage in [0,5] "
                f"with stage_buf <= max_stage; got {stage!r}/{max_stage!r}."
            )
        if not isinstance(goals[index], bool):
            raise RuntimeError(f"A2 M41 episode_goal_reached[{index}] must be bool; got {goals[index]!r}.")
        time_in_stage = diagnostic["time_in_stage_buf"]
        episode_length = diagnostic["episode_length_buf"]
        for field_name, value in (("time_in_stage_buf", time_in_stage), ("episode_length_buf", episode_length)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeError(f"A2 M41 terminal row {index} {field_name} must be a non-negative int; got {value!r}.")
        if episode_length <= 0:
            raise RuntimeError(f"A2 M41 terminal row {index} episode_length_buf must be positive; got {episode_length!r}.")
        _a2_m41_finite_scalar(diagnostic["control_dt"], f"terminal row {index} control_dt", positive=True)
        terminal_reasons = diagnostic["terminal_reasons"]
        if not isinstance(terminal_reasons, str) or not terminal_reasons:
            raise RuntimeError(f"A2 M41 terminal row {index} terminal_reasons must be a non-empty string; got {terminal_reasons!r}.")
        _a2_m41_finite_vector(diagnostic["root_pos_rel"], f"terminal row {index} root_pos_rel", 3)
        reward_keys = _a2_m41_reward_sums(diagnostic["reward_episode_sums"], f"terminal row {index} reward_episode_sums")
        event_float_fields = frozenset(
            (
                "hinge_at_crossing",
                "hinge_at_release",
                "root_x_at_release",
                "post_release_body_force_max",
            )
        )
        for field_name in _A2_M41_RESULT_REQUIRED_FLOAT_FIELDS:
            if field_name in event_float_fields:
                continue
            _a2_m41_finite_scalar(diagnostic[field_name], f"terminal row {index} {field_name}")

        crossing_group = (
            diagnostic["crossing_while_holding"],
            diagnostic["hinge_at_crossing"],
        )
        release_group = (
            diagnostic["hinge_at_release"],
            diagnostic["root_x_at_release"],
            diagnostic["post_release_body_contact"],
            diagnostic["post_release_body_force_max"],
        )
        if any(value is None for value in crossing_group) != all(value is None for value in crossing_group):
            raise RuntimeError(
                f"A2 M41 terminal row {index} crossing telemetry fields must be all null or all non-null."
            )
        if any(value is None for value in release_group) != all(value is None for value in release_group):
            raise RuntimeError(
                f"A2 M41 terminal row {index} release telemetry fields must be all null or all non-null."
            )
        if crossing_group[0] is not None:
            if not isinstance(crossing_group[0], bool):
                raise RuntimeError(f"A2 M41 terminal row {index} crossing_while_holding must be bool.")
            _a2_m41_finite_scalar(crossing_group[1], f"terminal row {index} hinge_at_crossing")
        if release_group[0] is not None:
            _a2_m41_finite_scalar(release_group[0], f"terminal row {index} hinge_at_release")
            _a2_m41_finite_scalar(release_group[1], f"terminal row {index} root_x_at_release")
            if not isinstance(release_group[2], bool):
                raise RuntimeError(f"A2 M41 terminal row {index} post_release_body_contact must be bool.")
            _a2_m41_finite_scalar(release_group[3], f"terminal row {index} post_release_body_force_max", nonnegative=True)
        # A completed stage-5 route guarantees a root-X crossing, but it does not
        # guarantee a release event: stage4->5 may advance at a lower hinge angle
        # than the configured release-income threshold. Keep release telemetry
        # explicitly nullable while requiring the crossing event for every goal.
        if goals[index] and crossing_group[0] is None:
            raise RuntimeError(
                f"A2 M41 terminal row {index} goal_reached=true requires non-null crossing telemetry."
            )
        result_by_env[env_id] = {
            "episode_length_buf": episode_length,
            "control_dt": float(diagnostic["control_dt"]),
            "door_hinge_drive_max_force": float(diagnostic["door_hinge_drive_max_force"]),
            "door_handle_height": float(diagnostic["door_handle_height"]),
            "door_weight": float(diagnostic["door_weight"]),
            "reward_keys": reward_keys,
        }

    expected_ids = set(range(expected_num_envs))
    if set(result_by_env) != expected_ids:
        raise RuntimeError(
            "A2 M41 strict telemetry requires exactly one terminal row per env; "
            f"missing={sorted(expected_ids - set(result_by_env))}, "
            f"extra={sorted(set(result_by_env) - expected_ids)}."
        )
    return result_by_env


def _validate_a2_m41_stage2_trace(trace_records, result_by_env, expected_num_envs):
    if not isinstance(trace_records, list) or not trace_records:
        raise RuntimeError("A2 M41 strict telemetry requires a non-empty stage2 trace list.")
    rows_by_env = {env_id: [] for env_id in range(expected_num_envs)}
    previous_by_env = {}
    seen_steps_by_env = {env_id: set() for env_id in range(expected_num_envs)}
    for row_index, row in enumerate(trace_records):
        if not isinstance(row, dict):
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} must be a mapping.")
        missing = [name for name in _A2_M41_TRACE_REQUIRED_FIELDS if name not in row]
        if missing:
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} is missing {missing}.")
        env_id = row["env_id"]
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in rows_by_env:
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} has invalid env_id={env_id!r}.")
        if row["episode_index"] != 0 or not isinstance(row["episode_index"], int) or isinstance(row["episode_index"], bool):
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} requires episode_index=0; got {row['episode_index']!r}.")
        if row["first_episode_active"] is not True:
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} requires first_episode_active=true.")
        stage = row["stage_buf"]
        if isinstance(stage, bool) or not isinstance(stage, int) or stage not in (2, 3, 4, 5):
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} has invalid stage_buf={stage!r}.")
        step_index = row["step_index"]
        episode_length = row["episode_length_buf"]
        if isinstance(step_index, bool) or not isinstance(step_index, int) or step_index < 0:
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} step_index must be non-negative int; got {step_index!r}.")
        if isinstance(episode_length, bool) or not isinstance(episode_length, int) or episode_length <= 0:
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} episode_length_buf must be positive int; got {episode_length!r}.")
        if step_index in seen_steps_by_env[env_id]:
            raise RuntimeError(f"A2 M41 stage2 trace env{env_id} has duplicate step_index={step_index}.")
        seen_steps_by_env[env_id].add(step_index)
        previous = previous_by_env.get(env_id)
        if previous is not None:
            if step_index != previous["step_index"] + 1:
                raise RuntimeError(
                    f"A2 M41 stage2 trace env{env_id} step_index must be unique, ordered, and contiguous; "
                    f"got adjacent values ({previous['step_index']}, {step_index})."
                )
            if episode_length != previous["episode_length_buf"] + 1:
                raise RuntimeError(
                    f"A2 M41 stage2 trace env{env_id} episode_length_buf must be unique, ordered, and contiguous; "
                    f"got adjacent values ({previous['episode_length_buf']}, {episode_length})."
                )
        elif stage != 2:
            raise RuntimeError(f"A2 M41 stage2 trace env{env_id} must start at stage_buf=2; got {stage}.")
        if not isinstance(row["terminal_reasons"], str) or not row["terminal_reasons"]:
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} terminal_reasons must be a non-empty string.")
        _a2_m41_finite_scalar(row["control_dt"], f"stage2 trace row {row_index} control_dt", positive=True)
        _a2_m41_finite_vector(row["target_pos_source_handle"], f"stage2 trace row {row_index} target_pos_source_handle", 3)
        if not isinstance(row["both_contact"], bool) or not isinstance(row["over_force"], bool) or not isinstance(row["root_x_ever_crossed"], bool):
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} contact/force/crossing fields must be bool.")
        _a2_m41_finite_vector(row["root_pos_rel"], f"stage2 trace row {row_index} root_pos_rel", 3)
        reward_keys = _a2_m41_reward_sums(row["reward_episode_sums"], f"stage2 trace row {row_index} reward_episode_sums")
        if reward_keys != result_by_env[env_id]["reward_keys"]:
            raise RuntimeError(f"A2 M41 stage2 trace env{env_id} reward keys must exactly match terminal row.")
        for field_name in ("door_hinge_drive_max_force", "door_handle_height", "door_weight"):
            value = _a2_m41_finite_scalar(row[field_name], f"stage2 trace row {row_index} {field_name}")
            if value != result_by_env[env_id][field_name]:
                raise RuntimeError(f"A2 M41 stage2 trace env{env_id} {field_name} must exactly match terminal row.")
        if float(row["control_dt"]) != result_by_env[env_id]["control_dt"]:
            raise RuntimeError(f"A2 M41 stage2 trace env{env_id} control_dt must exactly match terminal row.")
        for field_name, length in (("physical_base_command", 5), ("arm_j7_j8_pos", 2), ("arm_j7_j8_open_target", 2)):
            _a2_m41_finite_vector(row[field_name], f"stage2 trace row {row_index} {field_name}", length)
        for field_name in ("door_body_panel_normal_force_per_filter", "door_arm_panel_normal_force_per_filter"):
            vector = _a2_m41_finite_vector(row[field_name], f"stage2 trace row {row_index} {field_name}", 13 if field_name.startswith("door_body") else 10)
            if any(value < 0.0 for value in vector):
                raise RuntimeError(f"A2 M41 stage2 trace row {row_index} {field_name} must be non-negative.")
        body_total = _a2_m41_finite_scalar(row["door_body_panel_normal_force_total"], f"stage2 trace row {row_index} door_body_panel_normal_force_total", nonnegative=True)
        arm_total = _a2_m41_finite_scalar(row["door_arm_panel_normal_force_total"], f"stage2 trace row {row_index} door_arm_panel_normal_force_total", nonnegative=True)
        if not math.isclose(body_total, sum(_a2_m41_finite_vector(row["door_body_panel_normal_force_per_filter"], "body force", 13)), rel_tol=1e-5, abs_tol=1e-6):
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} body force total disagrees with per-filter sum.")
        if not math.isclose(arm_total, sum(_a2_m41_finite_vector(row["door_arm_panel_normal_force_per_filter"], "arm force", 10)), rel_tol=1e-5, abs_tol=1e-6):
            raise RuntimeError(f"A2 M41 stage2 trace row {row_index} arm force total disagrees with per-filter sum.")
        _a2_m41_finite_scalar(row["door_hinge_joint_vel"], f"stage2 trace row {row_index} door_hinge_joint_vel")
        rows_by_env[env_id].append(row)
        previous_by_env[env_id] = row

    expected_ids = set(range(expected_num_envs))
    missing = [env_id for env_id, rows in rows_by_env.items() if not rows]
    if missing:
        raise RuntimeError(f"A2 M41 strict telemetry requires stage2 trace rows for every env; missing {missing}.")
    for env_id, rows in rows_by_env.items():
        if not any(row["stage_buf"] == 2 for row in rows):
            raise RuntimeError(f"A2 M41 stage2 trace env{env_id} is missing stage2 coverage.")
        final = rows[-1]
        if final["terminal_reasons"] == "unknown_reset":
            raise RuntimeError(f"A2 M41 stage2 trace env{env_id} is missing terminal evidence at its final row.")
        if final["episode_length_buf"] != result_by_env[env_id]["episode_length_buf"]:
            raise RuntimeError(
                f"A2 M41 stage2 trace env{env_id} terminal episode_length_buf must match terminal row "
                f"{result_by_env[env_id]['episode_length_buf']}; got {final['episode_length_buf']}."
            )
    if set(rows_by_env) != expected_ids:
        raise RuntimeError("A2 M41 stage2 trace environment coverage is ambiguous.")
    return rows_by_env


def _validate_a2_m41_eval_telemetry(eval_dict, trace_records, expected_num_envs):
    result_by_env = _validate_a2_m41_result_records(eval_dict, expected_num_envs)
    _validate_a2_m41_stage2_trace(trace_records, result_by_env, expected_num_envs)
    return None

def _normalize_a2_eval_optional_ratios(records):
    """Convert undefined eval-only ratios to JSON null while retaining raw fields."""
    if not isinstance(records, list):
        raise TypeError(
            "A2 eval optional-ratio records must be a list; "
            f"got {type(records).__name__}."
        )

    for record_index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(
                "A2 eval optional-ratio records must contain dictionaries; "
                f"record {record_index} is {type(record).__name__}."
            )
        for ratio_key, (_numerator_key, denominator_key) in {
            **_A2_EVAL_OPTIONAL_RATIO_SPECS,
            "a2_crossing_while_holding_frac": (
                "a2_crossing_while_holding_numerator_frac",
                "a2_crossing_while_holding_denominator_frac",
            ),
        }.items():
            if ratio_key not in record:
                continue
            if denominator_key not in record:
                raise ValueError(
                    f"A2 eval ratio {ratio_key!r} at record {record_index} "
                    f"requires explicit denominator {denominator_key!r}; missing."
                )

            denominator = record[denominator_key]
            if isinstance(denominator, torch.Tensor):
                if (
                    denominator.ndim != 0
                    or denominator.dtype == torch.bool
                    or denominator.is_complex()
                ):
                    raise ValueError(
                        f"A2 eval ratio {ratio_key!r} at record {record_index} "
                        f"requires a finite non-negative scalar denominator "
                        f"{denominator_key!r}; got tensor shape={tuple(denominator.shape)}, "
                        f"dtype={denominator.dtype}."
                    )
                denominator = denominator.detach().cpu().item()
            elif isinstance(denominator, np.ndarray):
                if denominator.ndim != 0:
                    raise ValueError(
                        f"A2 eval ratio {ratio_key!r} at record {record_index} "
                        f"requires a finite non-negative scalar denominator "
                        f"{denominator_key!r}; got array shape={denominator.shape}."
                    )
                denominator = denominator.item()
            elif isinstance(denominator, np.generic):
                denominator = denominator.item()

            if isinstance(denominator, (bool, np.bool_)) or not isinstance(
                denominator, (int, float, np.integer, np.floating)
            ):
                raise ValueError(
                    f"A2 eval ratio {ratio_key!r} at record {record_index} "
                    f"requires a finite non-negative scalar numeric denominator "
                    f"{denominator_key!r}; got {type(denominator).__name__}."
                )
            denominator_value = float(denominator)
            if not math.isfinite(denominator_value) or denominator_value < 0.0:
                raise ValueError(
                    f"A2 eval ratio {ratio_key!r} at record {record_index} "
                    f"requires a finite non-negative scalar denominator "
                    f"{denominator_key!r}; got {denominator!r}."
                )
            if denominator_value == 0.0:
                record[ratio_key] = None

    return records


def _validate_optional_a2_config_value(config, key, metadata_value):
    if key in config and config.get(key) != metadata_value:
        raise ValueError(
            f"A2_Base config {key}={config.get(key)} disagrees with metadata {metadata_value}"
        )


def _make_json_safe(value, path="root"):
    if isinstance(value, torch.Tensor):
        tensor = value.detach().cpu()
        if tensor.ndim == 0:
            return _make_json_safe(tensor.item(), path)
        return _make_json_safe(tensor.tolist(), path)
    if isinstance(value, np.ndarray):
        return _make_json_safe(value.tolist(), path)
    if isinstance(value, np.generic):
        return _make_json_safe(value.item(), path)
    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            if not isinstance(key, (str, int, float, bool, type(None))):
                raise TypeError(
                    f"Unsupported eval metrics key type at {path}: "
                    f"{type(key).__name__}"
                )
            key_path = f"{path}.{key}" if isinstance(key, str) else f"{path}[{repr(key)}]"
            converted[key] = _make_json_safe(item, key_path)
        return converted
    if isinstance(value, (list, tuple)):
        return [_make_json_safe(item, f"{path}[{idx}]") for idx, item in enumerate(value)]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Non-finite eval artifact value at {path}: {value!r}")
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    raise TypeError(f"Unsupported eval metrics value type at {path}: {type(value).__name__}")


def _a2_v23_p0_metric_vector(record: Mapping, field: str) -> list[float] | None:
    """Read one six-joint v23 metric without replacing missing values."""

    value = record.get(field)
    if isinstance(value, Mapping):
        if value.get("status") == "N/A":
            return None
        raise RuntimeError(f"v23 P0 terminal metric {field} has an invalid typed value.")
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        raise RuntimeError(f"v23 P0 terminal metric {field} requires six arm-joint values.")
    result = [float(item) for item in value]
    if any(not math.isfinite(item) for item in result):
        raise RuntimeError(f"v23 P0 terminal metric {field} contains a non-finite value.")
    return result


def _build_a2_v23_p0_export_payload(
    records: list[Mapping], *, effort_nm: float
) -> tuple[dict, dict]:
    """Build terminal records and one effort-ladder-compatible observation.

    The aggregate is explicitly the maximum over terminal environments and six
    arm joints.  Historical records are not synthesized and a missing metric is
    represented by ``PENDING`` in the pure-data observation while each terminal
    record retains its typed N/A value.
    """

    if isinstance(effort_nm, bool) or not isinstance(effort_nm, (int, float)):
        raise RuntimeError("v23 P0 export requires a numeric env.config.a2_v23_effort_profile_nm.")
    effort_value = float(effort_nm)
    if not math.isfinite(effort_value) or effort_value <= 0.0:
        raise RuntimeError("v23 P0 export effort profile must be finite and strictly positive.")
    if not records:
        raise RuntimeError("v23 P0 export requires at least one terminal episode record.")

    valid_rows: list[dict[str, list[float]]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise RuntimeError(f"v23 P0 terminal record {index} is not a mapping.")
        if record.get("evidence_state") != "TERMINAL_SNAPSHOT":
            raise RuntimeError(
                f"v23 P0 terminal record {index} was not captured as TERMINAL_SNAPSHOT."
            )
        valid_frame_count = record.get("valid_frame_count")
        if isinstance(valid_frame_count, bool) or not isinstance(valid_frame_count, int) or valid_frame_count < 0:
            raise RuntimeError(f"v23 P0 terminal record {index} has invalid valid_frame_count.")
        if valid_frame_count == 0:
            continue
        row = {
            "nominal": _a2_v23_p0_metric_vector(record, "nominal_pd_torque_abs_max"),
            "clipped": _a2_v23_p0_metric_vector(record, "clipped_command_torque_abs_max"),
            "tracking": _a2_v23_p0_metric_vector(record, "arm_joint_position_error_abs_max_6d"),
        }
        if any(value is None for value in row.values()):
            raise RuntimeError(
                f"v23 P0 terminal record {index} has valid frames but a typed-missing metric."
            )
        valid_rows.append({
            "nominal": row["nominal"],
            "clipped": row["clipped"],
            "tracking": row["tracking"],
        })

    if valid_rows:
        nominal = max(value for row in valid_rows for value in row["nominal"])
        clipped = max(value for row in valid_rows for value in row["clipped"])
        tracking = max(value for row in valid_rows for value in row["tracking"])
        aggregate_status = "OBSERVED"
    else:
        nominal = clipped = tracking = "PENDING"
        aggregate_status = "N/A_NO_VALID_TORQUE_TELEMETRY"

    observation = {
        "effort_nm": effort_value,
        "status": aggregate_status,
        "decision_flags": {
            "meaningful_clipped_saturation": "PENDING",
            "e0_not_collapsed": "PENDING",
            "heavy_door_deteriorates_first": "PENDING",
            "pd_oscillation_absent": "PENDING",
        },
        "nominal_clipped_tracking": {
            "nominal_pd_torque": nominal,
            "clipped_command_torque": clipped,
            "tracking_error": tracking,
            "authority": "ESTIMATE_ONLY; max_over_terminal_envs_and_arm_joints",
        },
        "aggregation": {
            "operator": "max",
            "scope": "terminal_envs_and_six_arm_joints",
            "tracking_error_formula": "v21B: joint_pos_target - joint_pos",
        },
        "missing_metric_state": (
            {"status": "N/A", "reason": "NO_VALID_TORQUE_TELEMETRY", "denominator": 0}
            if not valid_rows
            else None
        ),
    }
    records_payload = {
        "schema": "a2_piper_base_v23_p0_torque_terminal_records_v1",
        "effort_nm": effort_value,
        "terminal_identity_contract": {
            "fields": ["env_id", "episode_index", "episode_id"],
            "episode_id_authority": "EVALUATOR_ASSIGNED_ENV_EPISODE_ID",
        },
        "tracking_error_contract": {
            "formula": "v21B: joint_pos_target - joint_pos",
            "position_error_field": "arm_joint_position_error_6d",
            "velocity_field": "arm_joint_velocity_6d",
            "aggregation": "per-joint mean/max over valid terminal frames",
        },
        "records": list(records),
    }
    raw_temporal_records = []
    for index, record in enumerate(records):
        temporal = record.get("temporal_episode") if isinstance(record, Mapping) else None
        if temporal is not None:
            if not isinstance(temporal, Mapping):
                raise RuntimeError(f"v23 P0 terminal record {index}.temporal_episode must be a mapping.")
            if temporal.get("schema") != "a2_piper_base_v23_p0_temporal_episode_v1":
                raise RuntimeError(f"v23 P0 terminal record {index}.temporal_episode schema is not registered.")
            provenance = temporal.get("source_provenance")
            required_provenance = (
                "checkpoint", "config", "scenario", "topology", "seed", "plain_prefix_id",
                "env_id", "episode_index", "episode_id", "effort_nm",
            )
            if not isinstance(provenance, Mapping) or any(key not in provenance for key in required_provenance):
                raise RuntimeError(f"v23 P0 terminal record {index}.temporal_episode lacks strict source provenance.")
            raw_temporal_records.append(dict(temporal))
    records_payload["temporal_records"] = {
        "schema": "a2_piper_base_v23_p0_temporal_records_v1",
        "temporary_label": "A0_CANONICAL16_P0_REFERENCE",
        "records": raw_temporal_records,
        "status": "RAW_TEMPORAL_PRESERVED" if raw_temporal_records else "PENDING_NO_RAW_TEMPORAL_RECORDS",
        "aggregate_fallback": False,
    }
    aggregate_payload = {
        "schema": "a2_piper_base_v23_p0_effort_observations_v1",
        "rows": [observation],
        "rungs": [observation],
        "registered_rung_observation": observation,
        "source": "a2_v23_terminal_snapshot",
        "prior_evidence": "historical_v21B_material_is_prior_only",
    }
    return records_payload, aggregate_payload


def _read_a2_eval_diagnostic_config(eval_config):
    p2_posture_axis = _read_a2_eval_p2_posture_axis(eval_config)
    strict_m41_telemetry = eval_config.get(_A2_EVAL_M41_STRICT_TELEMETRY_KEY, False)
    if not isinstance(strict_m41_telemetry, bool):
        raise RuntimeError(
            f"eval.{_A2_EVAL_M41_STRICT_TELEMETRY_KEY} must be bool; "
            f"got {strict_m41_telemetry!r}."
        )
    strict_v20_telemetry = eval_config.get(_A2_EVAL_V20_STRICT_TELEMETRY_KEY, False)
    if not isinstance(strict_v20_telemetry, bool):
        raise RuntimeError(
            f"eval.{_A2_EVAL_V20_STRICT_TELEMETRY_KEY} must be bool; got {strict_v20_telemetry!r}."
        )
    diagnostic_enabled = eval_config.get("a2_diagnostic_trace_enabled", False)
    forced_close_enabled = eval_config.get("a2_forced_gripper_close_enabled", False)
    for key, value in (
        ("a2_diagnostic_trace_enabled", diagnostic_enabled),
        ("a2_forced_gripper_close_enabled", forced_close_enabled),
    ):
        if not isinstance(value, bool):
            raise RuntimeError(f"eval.{key} must be bool; got {value!r}.")
    if forced_close_enabled and not diagnostic_enabled:
        raise RuntimeError(
            "eval.a2_forced_gripper_close_enabled=true requires "
            "eval.a2_diagnostic_trace_enabled=true for action auditability."
        )

    reward_terms = eval_config.get("a2_diagnostic_reward_terms", ())
    if diagnostic_enabled:
        if not isinstance(reward_terms, (list, tuple, ListConfig)):
            raise RuntimeError(
                "eval.a2_diagnostic_reward_terms must be a list of reward names; "
                f"got {type(reward_terms).__name__}."
            )
        reward_terms = tuple(reward_terms)
        if not reward_terms:
            raise RuntimeError(
                "eval.a2_diagnostic_reward_terms must be non-empty when diagnostics are enabled."
            )
        if any(not isinstance(name, str) or not name for name in reward_terms):
            raise RuntimeError(
                "eval.a2_diagnostic_reward_terms must contain non-empty strings; "
                f"got {reward_terms}."
            )
        if len(set(reward_terms)) != len(reward_terms):
            raise RuntimeError(
                "eval.a2_diagnostic_reward_terms must be unique; "
                f"got {reward_terms}."
            )
    else:
        reward_terms = ()

    forced_close_value = eval_config.get("a2_forced_gripper_close_value", -1.0)
    if (
        isinstance(forced_close_value, bool)
        or not isinstance(forced_close_value, (int, float))
        or not math.isfinite(float(forced_close_value))
        or float(forced_close_value) >= 0.0
    ):
        raise RuntimeError(
            "eval.a2_forced_gripper_close_value must be a finite negative number; "
            f"got {forced_close_value!r}."
        )
    forced_close_value = float(forced_close_value)

    forced_close_stages = eval_config.get("a2_forced_gripper_close_stages", (3, 4))
    if not isinstance(forced_close_stages, (list, tuple, ListConfig)):
        raise RuntimeError(
            "eval.a2_forced_gripper_close_stages must be a list of stage ids; "
            f"got {type(forced_close_stages).__name__}."
        )
    forced_close_stages = tuple(forced_close_stages)
    if not forced_close_stages or any(
        isinstance(stage, bool) or not isinstance(stage, int)
        for stage in forced_close_stages
    ):
        raise RuntimeError(
            "eval.a2_forced_gripper_close_stages must contain integer stage ids; "
            f"got {forced_close_stages}."
        )
    if len(set(forced_close_stages)) != len(forced_close_stages):
        raise RuntimeError(
            "eval.a2_forced_gripper_close_stages must be unique; "
            f"got {forced_close_stages}."
        )

    return {
        "diagnostic_enabled": diagnostic_enabled,
        "reward_terms": reward_terms,
        "forced_close_enabled": forced_close_enabled,
        "forced_close_value": forced_close_value,
        "forced_close_stages": forced_close_stages,
        "p2_posture_axis": p2_posture_axis,
        "strict_m41_telemetry": strict_m41_telemetry,
        "strict_v20_telemetry": strict_v20_telemetry,
    }


def _read_a2_v23_stationary_rent_config(eval_config):
    """Resolve the opt-in one-zero-action v23 stationary-rent pass."""

    enabled = eval_config.get("a2_v23_stationary_rent_export", False)
    if not isinstance(enabled, bool):
        raise RuntimeError(
            "eval.a2_v23_stationary_rent_export must be bool; "
            f"got {enabled!r}."
        )
    target_stage = eval_config.get("a2_v23_stationary_rent_target_stage")
    if enabled and (
        isinstance(target_stage, bool)
        or not isinstance(target_stage, int)
        or target_stage not in range(6)
    ):
        raise RuntimeError(
            "eval.a2_v23_stationary_rent_target_stage must be an integer in 0..5 "
            f"when stationary-rent export is enabled; got {target_stage!r}."
        )
    return {"enabled": enabled, "target_stage": target_stage}


def _capture_a2_v23_stationary_rent_records(
    env,
    pending,
    dones,
    *,
    target_stage: int,
):
    """Consume the dedicated post-reward/pre-reset component clones for one pass."""

    raw_components = env._a2_v23_stationary_rent_last_raw_components
    scaled_components = env._a2_v23_stationary_rent_last_scaled_components
    if not isinstance(raw_components, Mapping) or not isinstance(scaled_components, Mapping):
        raise RuntimeError(
            "v23 stationary-rent export requires dedicated raw/scaled component mappings."
        )
    if set(raw_components) != set(scaled_components) or not raw_components:
        raise RuntimeError(
            "v23 stationary-rent export requires exact reward-name coverage; "
            f"raw={tuple(raw_components)}, scaled={tuple(scaled_components)}."
        )
    if any(not isinstance(name, str) or not name for name in raw_components):
        raise RuntimeError("v23 stationary-rent export requires non-empty string reward names.")

    num_envs = int(env.num_envs)
    env_device = torch.device(env.device)
    dones_flat = dones.reshape(-1)
    if tuple(dones_flat.shape) != (num_envs,):
        raise RuntimeError(
            "v23 stationary-rent export requires one done value per environment; "
            f"got shape={tuple(dones_flat.shape)}."
        )
    reward_stage = env._a2_v23_stationary_rent_last_reward_stage
    if (
        not torch.is_tensor(reward_stage)
        or tuple(reward_stage.shape) != (num_envs,)
        or reward_stage.dtype != torch.long
        or reward_stage.device != env_device
    ):
        raise RuntimeError(
            "v23 stationary-rent export requires one dedicated pre-reset reward stage per environment; "
            f"got shape={None if not torch.is_tensor(reward_stage) else tuple(reward_stage.shape)}."
        )

    for name in raw_components:
        for value_name, value in (("raw", raw_components[name]), ("scaled", scaled_components[name])):
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != (num_envs,)
                or value.dtype != torch.float32
                or value.device != env_device
                or not bool(torch.all(torch.isfinite(value)).item())
            ):
                shape = None if not torch.is_tensor(value) else tuple(value.shape)
                dtype = None if not torch.is_tensor(value) else value.dtype
                device = None if not torch.is_tensor(value) else value.device
                raise RuntimeError(
                    f"v23 stationary-rent {value_name} component {name!r} must be "
                    f"finite float32 shape ({num_envs},) on {env_device}; "
                    f"got shape={shape}, dtype={dtype}, device={device}."
                )

    env_ids = pending["env_ids"]
    pre_stage = pending["pre_stage"]
    episode_indices = pending["episode_indices"]
    policy_raw_action = pending["policy_raw_action"]
    applied_high_level_action = pending["applied_high_level_action"]
    if not torch.is_tensor(applied_high_level_action) or applied_high_level_action.ndim != 2:
        raise RuntimeError("v23 stationary-rent pending applied action must be rank-2.")
    if applied_high_level_action.shape[-1] != 12:
        raise RuntimeError(
            "v23 stationary-rent pending applied action must have exactly 12 dimensions; "
            f"got {applied_high_level_action.shape[-1]}."
        )
    if not bool(torch.all(applied_high_level_action == 0.0).item()):
        raise RuntimeError("v23 stationary-rent pending action is not the exact all-zero 12-D vector.")

    records = []
    for row_index, env_id_value in enumerate(env_ids.tolist()):
        env_id = int(env_id_value)
        episode_index = int(episode_indices[row_index].item())
        raw_action = policy_raw_action[row_index]
        applied_action = applied_high_level_action[row_index]
        reward_raw = {}
        reward_scaled = {}
        for name in raw_components:
            reward_raw[name] = float(raw_components[name][env_id].item())
            reward_scaled[name] = float(scaled_components[name][env_id].item())
            if not math.isfinite(reward_raw[name]) or not math.isfinite(reward_scaled[name]):
                raise RuntimeError(
                    f"v23 stationary-rent reward scalar {name!r} is non-finite for env {env_id}."
                )
        records.append(
            {
                "env_id": env_id,
                "episode_index": episode_index,
                "episode_id": f"a2-v23-stationary-rent-env{env_id}-episode{episode_index}",
                "target_stage": int(target_stage),
                "pre_stage": int(pre_stage[row_index].item()),
                "post_stage": int(reward_stage[env_id].item()),
                "policy_raw_action": [float(value) for value in raw_action.tolist()],
                "applied_high_level_action": [float(value) for value in applied_action.tolist()],
                "zero_action_verified": True,
                "done": bool(dones_flat[env_id].item()),
                "reward_raw": reward_raw,
                "reward_scaled": reward_scaled,
            }
        )
    return records


def _read_a2_v23_p08_state_bank_config(
    eval_config,
    *,
    env,
    checkpoint_load_mode,
    checkpoint_path,
    seed,
    process_count,
):
    """Resolve the strict opt-in A0/D0 P0.8 state-bank capture contract."""

    enabled = eval_config.get("a2_v23_p08_state_bank_export", False)
    if not isinstance(enabled, bool):
        raise RuntimeError(
            "eval.a2_v23_p08_state_bank_export must be bool; "
            f"got {enabled!r}."
        )
    if not enabled:
        return {"enabled": False}
    if eval_config.get("a2_v23_p05_runtime_export") is not False:
        raise RuntimeError(
            "P0.8 state-bank capture requires eval.a2_v23_p05_runtime_export=false."
        )

    if not bool(getattr(env, "_use_a2_base", False)):
        raise RuntimeError("P0.8 state-bank capture requires an A2_Base environment.")
    if eval_config.get("eval_num_envs_episodes") is not True:
        raise RuntimeError(
            "P0.8 state-bank capture requires eval.eval_num_envs_episodes=true."
        )
    if process_count != 1:
        raise RuntimeError("P0.8 state-bank capture requires single-process evaluation.")
    target_stages = eval_config.get("a2_v23_p08_target_stages")
    if not isinstance(target_stages, (list, tuple, ListConfig)):
        raise RuntimeError("eval.a2_v23_p08_target_stages must be a list of stage ids.")
    target_stages = tuple(target_stages)
    if target_stages != _A2_V23_P08_TARGET_STAGES:
        raise RuntimeError(
            "P0.8 state-bank capture requires target stages exactly [2, 3, 4]; "
            f"got {target_stages!r}."
        )
    forward_mode = eval_config.get("a2_v23_p08_forward_mode")
    if forward_mode != _A2_V23_P08_FORWARD_MODE:
        raise RuntimeError(
            "P0.8 state-bank capture requires forward mode FULL; "
            f"got {forward_mode!r}."
        )
    if checkpoint_load_mode != "policy_only":
        raise RuntimeError("P0.8 state-bank capture requires checkpoint_load_mode=policy_only.")
    if seed != _A2_V23_P08_SEED:
        raise RuntimeError("P0.8 state-bank capture requires seed=0.")
    if int(env.num_envs) != _A2_V23_P08_NUM_ENVS:
        raise RuntimeError("P0.8 state-bank capture requires exactly 16 environments.")
    configured_step = eval_config.get("a2_v23_p08_checkpoint_step")
    if configured_step != _A2_V23_P08_CHECKPOINT_STEP:
        raise RuntimeError("P0.8 state-bank capture requires the v22 G1 step1250 anchor.")
    if eval_config.get("a2_v23_p08_source_cell") != _A2_V23_P08_SOURCE_CELL:
        raise RuntimeError("P0.8 state-bank capture requires source_cell=A0.")
    if eval_config.get("a2_v23_p08_atlas_cell") != _A2_V23_P08_SOURCE_CELL:
        raise RuntimeError("P0.8 state-bank capture requires atlas_cell=A0.")
    if eval_config.get("a2_v23_p08_selection_basis") != _A2_V23_P08_SELECTION_BASIS:
        raise RuntimeError("P0.8 state-bank capture requires the registered A0 selection basis.")
    if eval_config.get("a2_v23_p08_effort_profile_nm") != _A2_V23_P08_EFFORT_NM:
        raise RuntimeError("P0.8 state-bank capture requires the 40 N*m effort profile.")
    if eval_config.get("a2_v23_p08_seed") != _A2_V23_P08_SEED:
        raise RuntimeError("P0.8 state-bank capture requires the seed0 policy anchor.")
    if eval_config.get("a2_v23_p08_num_envs") != _A2_V23_P08_NUM_ENVS:
        raise RuntimeError("P0.8 state-bank capture requires the 16-env policy anchor.")
    expected_checkpoint_suffix = (
        "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt"
    )
    if not isinstance(checkpoint_path, str) or not checkpoint_path.endswith(expected_checkpoint_suffix):
        raise RuntimeError(
            "P0.8 state-bank capture requires the v22 G1 step1250 checkpoint anchor; "
            f"got {checkpoint_path!r}."
        )

    source_path = eval_config.get("a2_v23_p08_source_freeze_path")
    if source_path != _A2_V23_P08_SOURCE_FREEZE_PATH:
        raise RuntimeError(
            "P0.8 state-bank capture requires the fixed R50 A0 source-freeze path; "
            f"got {source_path!r}."
        )
    if (
        env.config.get("a2_v23_p08_source_freeze_path") != _A2_V23_P08_SOURCE_FREEZE_PATH
        or env.config.get("a2_v23_p08_source_cell") != _A2_V23_P08_SOURCE_CELL
        or env.config.get("a2_v23_p08_atlas_cell") != _A2_V23_P08_SOURCE_CELL
    ):
        raise RuntimeError("P0.8 env source-freeze/source-cell binding disagrees with the fixed A0 contract.")
    source_file = Path(source_path)
    if not source_file.is_absolute():
        source_file = Path.cwd() / source_file
    if not source_file.is_file():
        raise RuntimeError(f"P0.8 source-freeze artifact is missing: {source_file}")
    try:
        source_payload = json.loads(source_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"P0.8 source-freeze artifact is invalid JSON: {source_file}") from exc
    if (
        source_payload.get("schema") != _A2_V23_P08_SOURCE_SCHEMA
        or source_payload.get("status") != _A2_V23_P08_SOURCE_STATUS
        or source_payload.get("source_cell_id") != _A2_V23_P08_SOURCE_CELL
        or source_payload.get("selection_basis") != _A2_V23_P08_SELECTION_BASIS
        or source_payload.get("selected_effort_nm") != _A2_V23_P08_EFFORT_NM
    ):
        raise RuntimeError("P0.8 source-freeze schema/status/cell/basis/effort identity disagrees.")
    configured_effort = env.config.get("a2_v23_effort_profile_nm")
    if configured_effort != _A2_V23_P08_EFFORT_NM:
        raise RuntimeError(
            "P0.8 state-bank capture requires env.config.a2_v23_effort_profile_nm=40.0."
        )
    geometry_id = source_payload.get("source_geometry_id")
    if not isinstance(geometry_id, str) or not geometry_id:
        raise RuntimeError("P0.8 source-freeze artifact has no source_geometry_id.")
    configured_geometry = eval_config.get("a2_v23_p08_source_geometry_id")
    if configured_geometry != geometry_id:
        raise RuntimeError("P0.8 source geometry identity disagrees with the R50 source freeze.")
    if env.config.get("a2_v23_p08_source_geometry_id") != geometry_id:
        raise RuntimeError("P0.8 env source geometry identity disagrees with the R50 source freeze.")

    def resolve_required_path(value, label):
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"P0.8 requires a non-empty {label} path.")
        path = Path(value)
        if not path.is_absolute():
            path = Path.cwd() / path
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"P0.8 {label} is not a regular file: {path}")
        return str(path.resolve())

    p05_config = env.config
    if p05_config.get("a2_v23_p05_runtime_enabled") is not True:
        raise RuntimeError(
            "P0.8 state-bank capture requires the high-level P0.5 runtime initializer."
        )
    if p05_config.get("a2_v23_p05_purpose") != _A2_V23_P08_P05_PURPOSE:
        raise RuntimeError("P0.8 state-bank capture requires purpose=D1_CAPABILITY_SOURCE.")
    if p05_config.get("a2_v23_p05_mode") != _A2_V23_P08_P05_MODE:
        raise RuntimeError("P0.8 state-bank capture requires P0.5 mode FULL.")
    if p05_config.get("a2_v23_p05_topology") != _A2_V23_P08_P05_TOPOLOGY:
        raise RuntimeError("P0.8 state-bank capture requires the canonical16 P0.5 topology.")
    if p05_config.get("a2_v23_p05_cell_id") != _A2_V23_P08_SOURCE_CELL:
        raise RuntimeError("P0.8 state-bank capture requires P0.5 source cell A0.")
    if p05_config.get("a2_v23_p05_geometry_id") != geometry_id:
        raise RuntimeError("P0.8 P0.5 geometry identity disagrees with the R50 source freeze.")
    if p05_config.get("a2_v23_p05_checkpoint_load_mode") != "policy_only":
        raise RuntimeError("P0.8 P0.5 physical binding requires checkpoint_load_mode=policy_only.")
    if p05_config.get("a2_v23_p05_seed") != _A2_V23_P08_SEED:
        raise RuntimeError("P0.8 P0.5 physical binding requires seed=0.")
    if p05_config.get("a2_v23_p05_effort_profile_nm") != _A2_V23_P08_EFFORT_NM:
        raise RuntimeError("P0.8 P0.5 physical binding requires the 40 N*m effort freeze.")
    if p05_config.get("a2_v23_p05_requested_hinge_damping_native") != _A2_V23_P08_P05_REQUESTED_PARAMS["hinge_damping_native"] or p05_config.get("a2_v23_p05_requested_hinge_stiffness_native") != _A2_V23_P08_P05_REQUESTED_PARAMS["hinge_stiffness_native"] or p05_config.get("a2_v23_p05_requested_hinge_max_force_nm") != _A2_V23_P08_P05_REQUESTED_PARAMS["hinge_max_force_nm"] or p05_config.get("a2_v23_p05_requested_door_weight_kg") != _A2_V23_P08_P05_REQUESTED_PARAMS["door_weight_kg"]:
        raise RuntimeError("P0.8 P0.5 requested A0 parameters are not the R50 values.")
    if p05_config.get("a2_v23_p05_hinge_damping_native") != _A2_V23_P08_P05_NATIVE_PARAMS["hinge_damping_native"] or p05_config.get("a2_v23_p05_hinge_stiffness_native") != _A2_V23_P08_P05_NATIVE_PARAMS["hinge_stiffness_native"] or p05_config.get("a2_v23_p05_hinge_effort_limit_nm") != _A2_V23_P08_P05_NATIVE_PARAMS["hinge_effort_limit_nm"] or p05_config.get("a2_v23_p05_door_weight_kg") != _A2_V23_P08_P05_NATIVE_PARAMS["door_weight_kg"]:
        raise RuntimeError("P0.8 P0.5 native A0 parameters are not the R50 values.")
    expected_p05_paths = {
        "a2_v23_p05_effort_freeze_path": _A2_V23_P08_P05_EFFORT_FREEZE_PATH,
        "a2_v23_p05_atlas_manifest_path": _A2_V23_P08_P05_ATLAS_PATH,
        "a2_v23_p05_external_threshold_path": _A2_V23_P08_P05_EXTERNAL_THRESHOLD_PATH,
        "a2_v23_p05_plain_manifest_path": _A2_V23_P08_P05_PLAIN_MANIFEST_PATH,
        "a2_v23_p05_capability_source_freeze_path": _A2_V23_P08_SOURCE_FREEZE_PATH,
        "a2_v23_p05_checkpoint": expected_checkpoint_suffix,
        "a2_v23_p05_config_id": _A2_V23_P08_P05_CONFIG_ID,
    }
    resolved_p05_paths = {}
    for key, expected in expected_p05_paths.items():
        value = p05_config.get(key)
        if key in ("a2_v23_p05_checkpoint", "a2_v23_p05_config_id"):
            resolved_p05_paths[key] = resolve_required_path(value, key)
            expected_path = Path(expected)
            if not str(Path(resolved_p05_paths[key])).endswith(str(expected_path)):
                raise RuntimeError(f"P0.8 {key} is not the fixed v22 G1 identity.")
        else:
            resolved_p05_paths[key] = resolve_required_path(value, key)
            expected_path = Path(expected)
            expected_resolved = expected_path if expected_path.is_absolute() else Path.cwd() / expected_path
            if Path(resolved_p05_paths[key]) != expected_resolved.resolve():
                raise RuntimeError(f"P0.8 {key} is not the fixed R50/R54 input.")
    if p05_config.get("a2_v23_p05_bands") is not None:
        raise RuntimeError("P0.8 D1 capability-source binding forbids rescue bands.")
    if p05_config.get("a2_v23_p0_plain_scenario_enabled") is not True or p05_config.get("a2_v23_p0_bound_plain_scenario_enabled") is not True:
        raise RuntimeError("P0.8 requires the bound-plain A0 scene selector.")
    if p05_config.get("a2_v23_p0_scenario_topology") != _A2_V23_P08_P05_TOPOLOGY:
        raise RuntimeError("P0.8 bound-plain selector requires topology=canonical16.")
    bound_manifest_value = p05_config.get("a2_v23_p0_bound_plain_scenario_manifest_path")
    scenario_manifest_value = p05_config.get("a2_v23_p0_scenario_manifest_path")
    p05_bound_manifest_value = p05_config.get("a2_v23_p05_bound_plain_manifest_path")
    bound_manifest_path = resolve_required_path(
        bound_manifest_value, "fresh bound plain scenario manifest"
    )
    if scenario_manifest_value != bound_manifest_value or p05_bound_manifest_value != bound_manifest_value:
        raise RuntimeError("P0.8 scenario selector and P0.5 must share the fresh bound manifest.")
    if Path(bound_manifest_path).name != "d1_capability_bound_plain_scenario_manifest.json":
        raise RuntimeError("P0.8 bound manifest must use the D1 capability-source filename.")
    manifest_payload = json.loads(Path(bound_manifest_path).read_text(encoding="utf-8"))
    if (
        manifest_payload.get("schema") != _A2_V23_P08_P05_BOUND_MANIFEST_SCHEMA
        or manifest_payload.get("status") != _A2_V23_P08_P05_BOUND_MANIFEST_STATUS
        or manifest_payload.get("purpose") != _A2_V23_P08_P05_PURPOSE
        or manifest_payload.get("selector_mode") != _A2_V23_P08_P05_BOUND_SELECTOR_MODE
        or manifest_payload.get("topology") != _A2_V23_P08_P05_TOPOLOGY
        or not isinstance(manifest_payload.get("rows"), list)
        or len(manifest_payload["rows"]) != _A2_V23_P08_NUM_ENVS
    ):
        raise RuntimeError("P0.8 fresh bound manifest is not the exact R54 D1 capability-source contract.")

    return {
        "enabled": True,
        "target_stages": target_stages,
        "forward_mode": _A2_V23_P08_FORWARD_MODE,
        "source_identity": {
            "source_freeze_path": _A2_V23_P08_SOURCE_FREEZE_PATH,
            "schema": _A2_V23_P08_SOURCE_SCHEMA,
            "status": _A2_V23_P08_SOURCE_STATUS,
            "source_cell": _A2_V23_P08_SOURCE_CELL,
            "atlas_cell": _A2_V23_P08_SOURCE_CELL,
            "selection_basis": _A2_V23_P08_SELECTION_BASIS,
            "effort_nm": _A2_V23_P08_EFFORT_NM,
            "source_geometry_id": geometry_id,
        },
        "checkpoint": expected_checkpoint_suffix,
        "checkpoint_load_mode": "policy_only",
        "checkpoint_step": _A2_V23_P08_CHECKPOINT_STEP,
        "seed": _A2_V23_P08_SEED,
        "num_envs": _A2_V23_P08_NUM_ENVS,
        "physical_binding_required": True,
        "physical_readback_schema": _A2_V23_P08_P05_READBACK_SCHEMA,
        "p05_purpose": _A2_V23_P08_P05_PURPOSE,
        "p05_mode": _A2_V23_P08_P05_MODE,
        "p05_topology": _A2_V23_P08_P05_TOPOLOGY,
        "p05_requested_params": dict(_A2_V23_P08_P05_REQUESTED_PARAMS),
        "p05_native_params": dict(_A2_V23_P08_P05_NATIVE_PARAMS),
        "bound_manifest_path": bound_manifest_path,
        "p05_input_paths": resolved_p05_paths,
        "canonical_geometry": deepcopy(source_payload["canonical_geometry"]),
    }


def _validate_a2_v23_p08_p05_terminal_readback(
    record,
    *,
    config,
    env_id,
    episode_index,
):
    """Validate one public P0.5 terminal getter record before A0 labeling."""

    if not isinstance(record, Mapping):
        raise RuntimeError("P0.8 physical source binding requires a typed P0.5 getter mapping.")
    expected_episode_id = f"a2-v23-p05-env{env_id}-episode{episode_index}"
    if (
        record.get("schema") != "a2_piper_v23_episode_record_v1"
        or record.get("evidence_state") != "TERMINAL_SNAPSHOT"
        or record.get("mode") != _A2_V23_P08_P05_MODE
        or record.get("purpose") != _A2_V23_P08_P05_PURPOSE
        or record.get("checkpoint_load_mode") != "policy_only"
        or record.get("topology") != _A2_V23_P08_P05_TOPOLOGY
        or record.get("seed") != _A2_V23_P08_SEED
        or record.get("episode_id") != expected_episode_id
        or record.get("cell_id") != _A2_V23_P08_SOURCE_CELL
        or record.get("geometry_id") != config["source_identity"]["source_geometry_id"]
        or record.get("canonical_geometry") != config["canonical_geometry"]
    ):
        raise RuntimeError("P0.8 P0.5 terminal record identity is not the fixed A0 FULL source.")
    step_rows = record.get("step_rows")
    if not isinstance(step_rows, list) or not step_rows:
        raise RuntimeError("P0.8 P0.5 terminal record has no authoritative physical step readback.")
    sample = step_rows[0].get("capability_sample") if isinstance(step_rows[0], Mapping) else None
    if not isinstance(sample, Mapping):
        raise RuntimeError("P0.8 P0.5 terminal record lacks the typed capability readback.")
    if (
        sample.get("schema") != "a2_piper_v23_capability_sample_v1"
        or sample.get("cell_id") != _A2_V23_P08_SOURCE_CELL
        or sample.get("geometry_id") != config["source_identity"]["source_geometry_id"]
        or sample.get("canonical_geometry") != config["canonical_geometry"]
        or sample.get("realized_params") != _A2_V23_P08_P05_NATIVE_PARAMS
        or sample.get("checkpoint_load_mode") != "policy_only"
    ):
        raise RuntimeError("P0.8 P0.5 capability readback does not match R50 native A0 parameters.")
    mass_inertia = sample.get("mass_inertia_receipt")
    if (
        not isinstance(mass_inertia, Mapping)
        or mass_inertia.get("schema") != "a2_piper_v23_p05_mass_inertia_receipt_v1"
        or mass_inertia.get("applied_once") is not True
        or mass_inertia.get("env_id") != env_id
    ):
        raise RuntimeError("P0.8 P0.5 physical mass/inertia readback is not authoritative.")
    for field in ("applied_panel_mass_kg", "inertia_scale"):
        value = mass_inertia.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise RuntimeError(f"P0.8 P0.5 physical readback {field} is not finite.")
    if not math.isclose(
        float(mass_inertia["applied_panel_mass_kg"]),
        _A2_V23_P08_P05_NATIVE_PARAMS["door_weight_kg"],
        rel_tol=0.0,
        abs_tol=1.0e-5,
    ):
        raise RuntimeError("P0.8 P0.5 applied panel mass does not match the R50 native weight.")
    for field in ("expected_scaled_panel_inertia", "readback_panel_inertia"):
        values = mass_inertia.get(field)
        if (
            not isinstance(values, list)
            or len(values) != 9
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in values
            )
        ):
            raise RuntimeError(f"P0.8 P0.5 {field} is not a finite native readback vector.")
    if any(
        not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1.0e-5)
        for actual, expected in zip(
            mass_inertia["readback_panel_inertia"], mass_inertia["expected_scaled_panel_inertia"]
        )
    ):
        raise RuntimeError("P0.8 P0.5 readback inertia does not match the applied high-level write.")
    return {
        "schema": _A2_V23_P08_P05_READBACK_SCHEMA,
        "authority": "P0.5_PUBLIC_TYPED_EPISODE_GETTER",
        "env_id": int(env_id),
        "episode_index": int(episode_index),
        "episode_id": expected_episode_id,
        "purpose": _A2_V23_P08_P05_PURPOSE,
        "mode": _A2_V23_P08_P05_MODE,
        "topology": _A2_V23_P08_P05_TOPOLOGY,
        "cell_id": _A2_V23_P08_SOURCE_CELL,
        "geometry_id": config["source_identity"]["source_geometry_id"],
        "canonical_geometry": deepcopy(config["canonical_geometry"]),
        "requested_params": dict(_A2_V23_P08_P05_REQUESTED_PARAMS),
        "native_params": dict(_A2_V23_P08_P05_NATIVE_PARAMS),
        "applied_native_params": dict(sample["realized_params"]),
        "readback_native_params": dict(sample["realized_params"]),
        "mass_inertia_receipt": deepcopy(mass_inertia),
    }


def _capture_a2_v23_p08_step(
    *,
    config,
    obs_dict,
    action_mean,
    applied_high_level_action,
    stage_buf,
    first_episode_active_mask,
    eval_episode_indices,
    cur_episode_length,
    prefix_rows,
    captured_entries,
):
    """Append one pre-step prefix row per active first-episode env and capture first targets."""

    actor_obs = obs_dict.get("actor_obs")
    num_envs = config["num_envs"]
    if (
        not torch.is_tensor(actor_obs)
        or actor_obs.ndim != 2
        or tuple(actor_obs.shape[:1]) != (num_envs,)
        or not torch.is_floating_point(actor_obs)
        or not bool(torch.all(torch.isfinite(actor_obs)).item())
    ):
        raise RuntimeError("P0.8 capture requires finite rank-2 obs_dict['actor_obs'] for all envs.")
    if (
        not torch.is_tensor(action_mean)
        or action_mean.ndim != 2
        or tuple(action_mean.shape[:1]) != (num_envs,)
        or action_mean.shape[1] <= 0
        or not torch.is_floating_point(action_mean)
        or not bool(torch.all(torch.isfinite(action_mean)).item())
    ):
        raise RuntimeError("P0.8 capture requires finite deterministic action_mean for all envs.")
    if (
        not torch.is_tensor(applied_high_level_action)
        or tuple(applied_high_level_action.shape) != (num_envs, 12)
        or not torch.is_floating_point(applied_high_level_action)
        or not bool(torch.all(torch.isfinite(applied_high_level_action)).item())
    ):
        raise RuntimeError("P0.8 capture requires finite applied 12-D high-level actions for all envs.")
    if (
        not torch.is_tensor(stage_buf)
        or tuple(stage_buf.shape) != (num_envs,)
        or stage_buf.dtype != torch.long
    ):
        raise RuntimeError("P0.8 capture requires the pre-step stage_buf tensor for all envs.")
    if (
        not torch.is_tensor(first_episode_active_mask)
        or tuple(first_episode_active_mask.shape) != (num_envs,)
        or first_episode_active_mask.dtype != torch.bool
    ):
        raise RuntimeError("P0.8 capture requires the first-episode active mask for all envs.")
    for env_id in torch.nonzero(first_episode_active_mask, as_tuple=False).flatten().tolist():
        episode_index = int(eval_episode_indices[env_id].item())
        control_step = int(cur_episode_length[env_id].item())
        prefix_rows[env_id].append(
            {
                "schema": "a2_piper_v23_state_bank_prefix_row_v1",
                "env_id": int(env_id),
                "episode_index": episode_index,
                "episode_id": f"a2-v23-state-bank-env{env_id}-episode{episode_index}",
                "control_step": control_step,
                "pre_stage": int(stage_buf[env_id].item()),
                "done_before_step": False,
                "actor_obs": [float(value) for value in actor_obs[env_id].detach().cpu().tolist()],
                "action_mean": [float(value) for value in action_mean[env_id].detach().cpu().tolist()],
                "applied_high_level_action": [
                    float(value) for value in applied_high_level_action[env_id].detach().cpu().tolist()
                ],
            }
        )

    for target_stage in config["target_stages"]:
        if target_stage in captured_entries:
            continue
        candidates = [
            int(env_id)
            for env_id in torch.nonzero(first_episode_active_mask, as_tuple=False).flatten().tolist()
            if int(stage_buf[env_id].item()) == target_stage
        ]
        if not candidates:
            continue
        chosen_env_id = min(candidates)
        selected_rows = prefix_rows[chosen_env_id]
        if not selected_rows:
            raise RuntimeError("P0.8 target capture found no contiguous prefix rows.")
        episode_index = int(eval_episode_indices[chosen_env_id].item())
        captured_entries[target_stage] = {
            "schema": _A2_V23_P08_STATE_BANK_ENTRY_SCHEMA,
            "entry_id": f"a2-v23-state-bank-stage{target_stage}-env{chosen_env_id}-episode{episode_index}",
            "scenario_id": f"D0_current_like_stage{target_stage}",
            "seed": config["seed"],
            # Source/atlas labels are assigned only after the public P0.5
            # terminal getter supplies authoritative applied/readback identity.
            "atlas_cell": None,
            "source_cell": None,
            "stage": int(target_stage),
            "env_id": chosen_env_id,
            "episode_index": episode_index,
            "episode_id": selected_rows[-1]["episode_id"],
            "replay_prefix_id": f"D0_current_like_stage{target_stage}_env{chosen_env_id}_episode{episode_index}",
            "reset_origin": "evaluator.reset_all_first_episode_observation",
            "source_identity": None,
            "forward_mode": config["forward_mode"],
            "state_clone_supported": False,
            "recurrent_state_restore_supported": False,
            "recurrent_prefix_status": "CAPTURED_NOT_REEXECUTED",
            "capture_selection": "FIRST_TARGET_STEP_LOWEST_ENV_ID",
            "replay_prefix": deepcopy(selected_rows),
        }


def _write_a2_v23_p08_raw_capture(
    eval_output_dir,
    config,
    captured_entries,
    *,
    completed_episodes,
    physical_readbacks,
):
    """Write the single raw P0.8 capture payload after normal evaluation finalization."""

    if not isinstance(physical_readbacks, list) or len(physical_readbacks) != config["num_envs"]:
        raise RuntimeError(
            "P0.8 raw capture requires one authoritative P0.5 physical readback per environment."
        )
    by_env = {}
    for readback in physical_readbacks:
        env_id = readback.get("env_id") if isinstance(readback, Mapping) else None
        if env_id in by_env:
            raise RuntimeError("P0.8 raw capture received duplicate P0.5 physical readback env ids.")
        by_env[env_id] = readback
    if set(by_env) != set(range(config["num_envs"])):
        raise RuntimeError("P0.8 raw capture physical readback does not cover canonical16.")
    entries = []
    for stage in config["target_stages"]:
        if stage not in captured_entries:
            continue
        entry = deepcopy(captured_entries[stage])
        if entry.get("source_identity") is not None:
            raise RuntimeError("P0.8 source labels must remain unset until physical readback validation.")
        entry["source_identity"] = deepcopy(config["source_identity"])
        entry["atlas_cell"] = config["source_identity"]["atlas_cell"]
        entry["source_cell"] = config["source_identity"]["source_cell"]
        entry["physical_readback_env_id"] = int(entry["env_id"])
        if entry["physical_readback_env_id"] not in by_env:
            raise RuntimeError("P0.8 state-bank entry env lacks authoritative physical readback.")
        entries.append(entry)
    missing_stages = [stage for stage in config["target_stages"] if stage not in captured_entries]
    payload = {
        "schema": _A2_V23_P08_STATE_BANK_RAW_SCHEMA,
        "status": (
            "RAW_CAPTURE_COMPLETE"
            if not missing_stages
            else "PARTIAL_A0_D0_PREFIX_COVERAGE_INCOMPLETE"
        ),
        "p08_overall_status": "PARTIAL_INCOMPLETE",
        "target_stages": list(config["target_stages"]),
        "captured_stages": [entry["stage"] for entry in entries],
        "missing_stages": missing_stages,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "recurrent_prefix_status": "CAPTURED_NOT_REEXECUTED",
        "normal_eval_finalization": True,
        "completed_episodes": int(completed_episodes),
        "checkpoint": config["checkpoint"],
        "checkpoint_load_mode": config["checkpoint_load_mode"],
        "checkpoint_step": config["checkpoint_step"],
        "seed": config["seed"],
        "num_envs": config["num_envs"],
        "source_identity": config["source_identity"],
        "physical_readback": physical_readbacks,
        "entries": entries,
        "excluded_claims": [
            "NO_EXACT_STATE_CLONE",
            "NO_RECURRENT_STATE_RESTORE",
            "NO_INTERVENTION_EFFECT_OR_DELTA_J_CLAIM",
            "NO_D1_E_ZONE_OR_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
        ],
    }
    eval_output_dir = Path(eval_output_dir)
    eval_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = eval_output_dir / _A2_V23_P08_STATE_BANK_RAW_FILENAME
    temporary_path = Path(f"{output_path}.tmp")
    with temporary_path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=4, allow_nan=False)
    os.replace(temporary_path, output_path)
    logger.info("Saved v23 P0.8 raw state-bank capture to %s", output_path)
    return payload


def _build_a2_eval_first_episode_active_mask(
    eval_num_envs_episodes,
    env_episode_completed,
    num_envs,
    device,
):
    if not isinstance(eval_num_envs_episodes, bool):
        raise RuntimeError(
            "A2 eval first-episode mode flag must be bool; "
            f"got {eval_num_envs_episodes!r}."
        )
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs <= 0:
        raise RuntimeError(f"A2 eval num_envs must be a positive int; got {num_envs!r}.")
    expected_device = torch.device(device)
    if not eval_num_envs_episodes:
        return torch.ones(num_envs, dtype=torch.bool, device=expected_device)
    if (
        not torch.is_tensor(env_episode_completed)
        or tuple(env_episode_completed.shape) != (num_envs,)
        or env_episode_completed.dtype != torch.bool
        or env_episode_completed.device != expected_device
    ):
        shape = (
            None
            if not torch.is_tensor(env_episode_completed)
            else tuple(env_episode_completed.shape)
        )
        dtype = (
            None if not torch.is_tensor(env_episode_completed) else env_episode_completed.dtype
        )
        actual_device = (
            None if not torch.is_tensor(env_episode_completed) else env_episode_completed.device
        )
        raise RuntimeError(
            "A2 eval first-episode completion bookkeeping requires bool tensor shape "
            f"({num_envs},) on {expected_device}; got shape={shape}, dtype={dtype}, "
            f"device={actual_device}."
        )
    return ~env_episode_completed


def _build_a2_eval_forced_close_mask(
    stage_buf,
    first_episode_active_mask,
    forced_close_enabled,
    forced_close_stage_ids,
):
    if not isinstance(forced_close_enabled, bool):
        raise RuntimeError(
            "A2 eval forced-close enabled flag must be bool; "
            f"got {forced_close_enabled!r}."
        )
    if (
        not torch.is_tensor(stage_buf)
        or stage_buf.ndim != 1
        or stage_buf.dtype != torch.long
    ):
        shape = None if not torch.is_tensor(stage_buf) else tuple(stage_buf.shape)
        dtype = None if not torch.is_tensor(stage_buf) else stage_buf.dtype
        raise RuntimeError(
            "A2 eval forced-close stage_buf requires a 1D long tensor; "
            f"got shape={shape}, dtype={dtype}."
        )
    if (
        not torch.is_tensor(first_episode_active_mask)
        or tuple(first_episode_active_mask.shape) != tuple(stage_buf.shape)
        or first_episode_active_mask.dtype != torch.bool
        or first_episode_active_mask.device != stage_buf.device
    ):
        shape = (
            None
            if not torch.is_tensor(first_episode_active_mask)
            else tuple(first_episode_active_mask.shape)
        )
        dtype = (
            None
            if not torch.is_tensor(first_episode_active_mask)
            else first_episode_active_mask.dtype
        )
        device = (
            None
            if not torch.is_tensor(first_episode_active_mask)
            else first_episode_active_mask.device
        )
        raise RuntimeError(
            "A2 eval forced-close first-episode active mask requires bool tensor "
            f"shape {tuple(stage_buf.shape)} on {stage_buf.device}; got "
            f"shape={shape}, dtype={dtype}, device={device}."
        )
    forced_close_mask = torch.zeros_like(first_episode_active_mask)
    if forced_close_enabled:
        for stage_id in forced_close_stage_ids:
            forced_close_mask |= stage_buf == stage_id
    return forced_close_mask & first_episode_active_mask


class PolicyAndValueWrapper(nn.Module):
    def __init__(
        self,
        policy,
        value_model,
        homie_walk_model=None,
        homie_stand_model=None,
        ref_model=None,
        a2_base_model=None,
        a2_base_command_scale=0.25,
        a2_base_body_pitch_roll_scale=0.4,
        a2_base_command_multipliers=None,
        a2_base_obs_dim=1620,
        a2_base_frame_dim=54,
        a2_base_action_dim=12,
        a2_base_action_sigma=0.0,
        a2_base_command_clip_enabled=False,
        a2_base_command_clip_low=None,
        a2_base_command_clip_high=None,
    ) -> None:
        super().__init__()
        self.policy = policy
        self.value_model = value_model
        self.homie_walk_model = homie_walk_model
        self.homie_stand_model = homie_stand_model
        self.ref_model = ref_model
        object.__setattr__(self, "_a2_base_model", a2_base_model)
        self.use_a2_base = a2_base_model is not None
        self.a2_base_command_scale = a2_base_command_scale
        self.a2_base_body_pitch_roll_scale = a2_base_body_pitch_roll_scale
        self.a2_base_obs_dim = a2_base_obs_dim
        self.a2_base_frame_dim = a2_base_frame_dim
        self.a2_base_action_dim = a2_base_action_dim
        self.a2_base_action_sigma = a2_base_action_sigma
        self.a2_base_command_clip_enabled = a2_base_command_clip_enabled
        if a2_base_command_multipliers is None:
            a2_base_command_multipliers = [2.0, 2.0, 0.25, 1.0, 1.0]
        self.register_buffer(
            "a2_base_command_multipliers",
            torch.tensor(a2_base_command_multipliers, dtype=torch.float32),
        )
        if a2_base_command_clip_low is None:
            a2_base_command_clip_low = [
                -float("inf"),
                -float("inf"),
                -float("inf"),
                -float("inf"),
                -float("inf"),
            ]
        if a2_base_command_clip_high is None:
            a2_base_command_clip_high = [
                float("inf"),
                float("inf"),
                float("inf"),
                float("inf"),
                float("inf"),
            ]
        self.register_buffer(
            "a2_base_command_clip_low",
            torch.tensor(a2_base_command_clip_low, dtype=torch.float32),
        )
        self.register_buffer(
            "a2_base_command_clip_high",
            torch.tensor(a2_base_command_clip_high, dtype=torch.float32),
        )
        self.opt_homie = False
        self.homie_switch_threshold = 0.5

    @property
    def a2_base_model(self):
        return self._a2_base_model

    def set_mode(self, mode):
        if hasattr(self.policy, "mode"):
            self.policy.mode = mode
        if self.use_a2_base:
            self.a2_base_model.eval()
            return
        if hasattr(self.homie_walk_model, "train") and hasattr(self.homie_walk_model, "eval"):
            if self.opt_homie and mode == "train":
                self.homie_walk_model.train()
            else:
                self.homie_walk_model.eval()
        if hasattr(self.homie_stand_model, "train") and hasattr(self.homie_stand_model, "eval"):
            if self.opt_homie and mode == "train":
                self.homie_stand_model.train()
            else:
                self.homie_stand_model.eval()

    def transform_train(self):
        if hasattr(self.policy, "transform_train"):
            self.policy.transform_train()

    def transform_eval(self):
        if hasattr(self.policy, "transform_eval"):
            self.policy.transform_eval()

    def forward(self, modes, input_kwargs):
        results = {}
        for mode in modes:
            results[mode] = self.forward_component(mode, **input_kwargs[mode])
        return results

    def _a2_base_actions(self, obs_dict, high_level_actions, masks=None, original_dones=None):
        a2_base_obs = obs_dict["a2_base_obs"].clone()
        obs_shape = a2_base_obs.shape
        if obs_shape[-1] != self.a2_base_obs_dim:
            raise ValueError(
                f"A2_Base obs dim mismatch: got {obs_shape[-1]}, expected {self.a2_base_obs_dim}"
            )
        action_shape = high_level_actions.shape
        if obs_shape[:-1] != action_shape[:-1]:
            if masks is None or original_dones is None:
                raise ValueError(
                    "A2_Base obs/action leading shape mismatch without recurrent masks: "
                    f"obs leading dims {tuple(obs_shape[:-1])}, "
                    f"high_level_actions leading dims {tuple(action_shape[:-1])}"
                )
            if masks.dim() != 2 or original_dones.dim() != 2:
                raise ValueError(
                    "A2_Base recurrent unsplit expects masks [num_trajectories, max_traj_len] "
                    f"and original_dones [num_envs, num_steps], got {masks.shape=} "
                    f"{original_dones.shape=}"
                )
            if obs_shape[:2] != masks.shape or action_shape[:2] != original_dones.shape:
                raise ValueError(
                    "A2_Base recurrent obs/action layout mismatch: expected obs leading dims "
                    f"{tuple(masks.shape)} and action leading dims "
                    f"{tuple(original_dones.shape)}, got obs {tuple(obs_shape[:-1])} "
                    f"and actions {tuple(action_shape[:-1])}"
                )

            from gr00t.rl.trl.utils.rl import unsplit_trajectories

            a2_base_obs = unsplit_trajectories(a2_base_obs, masks, original_dones)
            obs_shape = a2_base_obs.shape
            if obs_shape[:-1] != action_shape[:-1]:
                raise ValueError(
                    "A2_Base unsplit obs/action leading shape mismatch: "
                    f"unsplit obs leading dims {tuple(obs_shape[:-1])}, "
                    f"high_level_actions leading dims {tuple(action_shape[:-1])}"
                )
        flat_obs = a2_base_obs.reshape(-1, obs_shape[-1])
        flat_high_level_actions = high_level_actions.reshape(-1, action_shape[-1])
        final_frame_start = flat_obs.shape[-1] - self.a2_base_frame_dim
        command_scale = self.a2_base_command_multipliers.to(
            device=flat_obs.device, dtype=flat_obs.dtype
        )
        scaled_base_command = torch.cat(
            [
                flat_high_level_actions[:, :3] * self.a2_base_command_scale,
                flat_high_level_actions[:, 3:5].clamp(-1.0, 1.0)
                * self.a2_base_body_pitch_roll_scale,
            ],
            dim=-1,
        )
        if self.a2_base_command_clip_enabled:
            scaled_base_command = torch.clamp(
                scaled_base_command,
                self.a2_base_command_clip_low.to(device=flat_obs.device, dtype=flat_obs.dtype),
                self.a2_base_command_clip_high.to(device=flat_obs.device, dtype=flat_obs.dtype),
            )
        flat_obs[:, final_frame_start + 39 : final_frame_start + 44] = (
            scaled_base_command * command_scale
        )
        with torch.no_grad():
            flat_actions = self.a2_base_model(flat_obs)
        if flat_actions.shape[-1] != self.a2_base_action_dim:
            raise ValueError(
                f"A2_Base action dim mismatch: got {flat_actions.shape[-1]}, expected {self.a2_base_action_dim}"
            )
        return flat_actions.reshape(*action_shape[:-1], flat_actions.shape[-1])

    def forward_component(self, mode, actions=None, **kwargs):
        if mode == "policy":
            self.policy.act(**kwargs)
            if self.use_a2_base:
                high_level_actions = actions[..., : self.policy.num_actions]
                a2_actions = self._a2_base_actions(
                    kwargs["obs_dict"],
                    high_level_actions,
                    masks=kwargs.get("masks"),
                    original_dones=kwargs.get("original_dones"),
                )
                policy_log_probs = self.policy.get_actions_log_prob(actions=high_level_actions)
                a2_sigma = torch.full_like(a2_actions, self.a2_base_action_sigma)
                results = {
                    "logprobs": policy_log_probs,
                    "action_mean": torch.cat([self.policy.action_mean, a2_actions], dim=-1),
                    "action_std": torch.cat([self.policy.action_std, a2_sigma], dim=-1),
                    "entropy": self.policy.entropy,
                }
                action_mask = getattr(self.policy, "rp0_action_mask", None)
                if action_mask is not None:
                    results["action_mask"] = action_mask
                return results
            homie_obs = kwargs["obs_dict"]["homie_obs"]
            stand_homie_obs = homie_obs.clone()
            reshaped_obs = stand_homie_obs.view(
                stand_homie_obs.shape[0],
                stand_homie_obs.shape[1],
                6,
                stand_homie_obs.shape[-1] // 6,
            )
            reshaped_obs[..., :3] = 0.0
            stand_homie_obs = reshaped_obs.view_as(stand_homie_obs)

            # If recurrent policy, unsplit observations for homie models
            if (
                hasattr(self.policy, "is_recurrent")
                and self.policy.is_recurrent
                and "masks" in kwargs
                and "original_dones" in kwargs
            ):
                from gr00t.rl.trl.utils.rl import unsplit_trajectories

                masks = kwargs["masks"]
                original_dones = kwargs["original_dones"]
                # Unsplit homie_obs from [num_trajectories, max_traj_len, ...] to [num_envs, num_steps, ...]
                homie_obs = unsplit_trajectories(homie_obs, masks, original_dones)
                stand_homie_obs = unsplit_trajectories(stand_homie_obs, masks, original_dones)

            walk_out = self.homie_walk_model(homie_obs)
            stand_out = self.homie_stand_model(stand_homie_obs)
            homie_one_step_obs = init_actor_critic_dict["num_one_step_obs"]
            commands = homie_obs[..., -homie_one_step_obs : -(homie_one_step_obs - 3)]
            walk_mask = torch.norm(commands, dim=-1, keepdim=True) > self.homie_switch_threshold

            def _sel(a_walk, a_stand):
                m = walk_mask
                while m.dim() < a_walk.dim():
                    m = m.unsqueeze(-1)
                while m.dim() > a_walk.dim():
                    m = m.squeeze(-1)
                return torch.where(m, a_walk, a_stand)

            homie_actions = _sel(walk_out["actions"], stand_out["actions"])
            homie_mean = _sel(walk_out["action_mean"], stand_out["action_mean"])
            homie_sigma = _sel(walk_out["action_sigma"], stand_out["action_sigma"])
            homie_entropy = _sel(walk_out["entropy"], stand_out["entropy"])

            policy_log_probs = self.policy.get_actions_log_prob(
                actions=actions[..., : self.policy.num_actions]
            )
            walk_lp = self.homie_walk_model.get_actions_log_prob(actions=homie_actions)
            stand_lp = self.homie_stand_model.get_actions_log_prob(actions=homie_actions)
            homie_log_probs = torch.where(walk_mask.squeeze(-1), walk_lp, stand_lp)
            if getattr(self, "opt_homie", True):
                logprobs = policy_log_probs + homie_log_probs
                entropy = self.policy.entropy + homie_entropy
            else:
                logprobs = policy_log_probs
                entropy = self.policy.entropy
            results = {
                "logprobs": logprobs,
                "action_mean": torch.cat([self.policy.action_mean, homie_mean], dim=-1),
                "action_std": torch.cat([self.policy.action_std, homie_sigma], dim=-1),
                "entropy": entropy,
            }
            action_mask = getattr(self.policy, "rp0_action_mask", None)
            if action_mask is not None:
                if self.opt_homie:
                    action_mask = torch.cat(
                        [
                            action_mask,
                            torch.ones(
                                homie_mean.shape[-1],
                                dtype=torch.bool,
                                device=action_mask.device,
                            ),
                        ],
                        dim=0,
                    )
                results["action_mask"] = action_mask
        elif mode == "policy_distill":
            results = self.policy.act(**kwargs)
        elif mode == "policy_distill_ppo":
            policy_state_dict = self.policy.act(**kwargs)
            log_probs = self.policy.get_actions_log_prob(actions=actions)
            results = {
                "actions": policy_state_dict["actions"],
                "logprobs": log_probs,
                "action_mean": policy_state_dict["action_mean"],
                "action_std": policy_state_dict["action_sigma"],
                "entropy": self.policy.entropy,
            }
            action_mask = getattr(self.policy, "rp0_action_mask", None)
            if action_mask is not None:
                results["action_mask"] = action_mask
            if "normalized_actions" in policy_state_dict:
                results["normalized_actions"] = policy_state_dict["normalized_actions"]
        elif mode == "policy_w_and_wo_imgaug":
            # The first forward is without image augmentation
            self.policy.transform_eval()
            policy_state_dict = self.policy.act(**kwargs)
            # Use the distribution without image augmentation to get the log_probs
            log_probs = self.policy.get_actions_log_prob(actions=actions)
            results = {
                "actions": policy_state_dict["actions"],
                "logprobs": log_probs,
                "action_mean": policy_state_dict["action_mean"],
                "action_std": policy_state_dict["action_sigma"],
                "entropy": self.policy.entropy,
            }
            action_mask = getattr(self.policy, "rp0_action_mask", None)
            if action_mask is not None:
                results["action_mask"] = action_mask

            # The second forward is with image augmentation
            self.policy.transform_train()
            # The second time doesn't need deepcopy
            policy_state_dict_w_imgaug = self.policy.act(**kwargs)
            results["action_mean_w_imgaug"] = policy_state_dict_w_imgaug["action_mean"]
            results["actions_w_imgaug"] = policy_state_dict_w_imgaug["actions"]
            if "normalized_actions" in policy_state_dict_w_imgaug:
                results["normalized_actions_w_imgaug"] = policy_state_dict_w_imgaug[
                    "normalized_actions"
                ]
        elif mode == "policy_deterministic":
            self.policy.act(**kwargs)
            results = {
                "action_mean": self.policy.action_mean,
            }
        elif mode == "vae_policy_deterministic":
            self.policy.act(**kwargs)
            prior_mu, prior_log_var = self.policy.eval_prior(**kwargs)
            results = {
                "action_mean": self.policy.action_mean,
                "vae_mu": self.policy.z_mu,
                "vae_log_var": self.policy.z_log_sigma,
                "prior_mu": prior_mu,
                "prior_log_var": prior_log_var,
            }
        elif mode == "value":
            results = self.value_model.evaluate(**kwargs)
        else:
            raise ValueError(f"Invalid mode: {mode}")

        return results


class PrinterHVCallback(TrainerCallback):
    """
    A bare [`TrainerCallback`] that just prints the logs.
    """

    def on_log(self, args, state, control, logs=None, **kwargs):
        _ = logs.pop("total_flos", None)
        if state.is_local_process_zero:
            width = 80
            pad = 35
            print_str = f" \033[1m Learning iteration {state.global_step}  \033[0m "

            log_string = (
                f"""{print_str.center(width, ' ')}\n\n"""
                f"""{'Computation:':>{pad}} {logs['fps']:.0f} steps/s (Collection: {logs['collection_time']:.3f}s, Learning {logs['learn_time']:.3f}s)\n"""
                f"""{'Mean action noise std:':>{pad}} {logs['Policy/mean_noise_std']:.2f}\n"""
            )

            for k, v in logs.items():
                if k.startswith("objective/"):
                    # Keep the original logic
                    if k.startswith("objective/kin_"):
                        log_string += f"""{f'{k}:':>{pad}} {v:.5f}\n"""
                    else:
                        new_key = k.replace("objective/", "")
                        log_string += f"""{f'Mean {new_key}:':>{pad}} {v:.5f}\n"""

            env_log_string = ""
            ep_string = ""
            for k, v in logs.items():
                if k.startswith("Env/"):
                    entry = f"{f'{k}:':>{pad}} {v:.4f}"
                    env_log_string += f"{entry}\n"
                if k.startswith("Episode/"):
                    new_key = k.replace("Episode/", "")
                    ep_string += f"""{f'Mean episode {new_key}:':>{pad}} {v:.4f}\n"""

            log_string += env_log_string
            log_string += ep_string
            log_string += (
                f"""{'-' * width}\n"""
                f"""{'Total episodes:':>{pad}} {logs['episode']}\n"""
                f"""{'Total timesteps:':>{pad}} {logs['tot_timesteps']}\n"""
                f"""{'Iteration time:':>{pad}} {logs['collection_time'] + logs['learn_time']:.2f}s\n"""
                f"""{'Total time:':>{pad}} {logs['tot_time']:.2f}s\n"""
                f"""{'ETA:':>{pad}} {logs['tot_time'] / logs['batch_idx'] * (logs['num_total_batches'] - logs['batch_idx']):.1f}s\n"""
            )

            log_string += f"Logging Directory: {logs['experiment_save_dir']}"
            with Live(
                Panel(log_string, title="Training Log"), refresh_per_second=4, console=console
            ):
                # Your training loop or other operations
                pass


def process_ep_infos(ep_infos, device):
    infos = {}
    for key in ep_infos[0]:
        infotensor = torch.tensor([], device=device)
        for ep_info in ep_infos:
            # handle scalar and zero dimensional tensor infos
            if not isinstance(ep_info[key], torch.Tensor):
                ep_info[key] = torch.Tensor([ep_info[key]])
            if len(ep_info[key].shape) == 0:
                ep_info[key] = ep_info[key].unsqueeze(0)
            infotensor = torch.cat((infotensor, ep_info[key].to(device)))
        value = torch.mean(infotensor)
        infos[key] = value
    return infos


def load_onnx_policy(path, device):
    model = ort.InferenceSession(path)

    def run_inference(input_tensor):
        ort_inputs = {model.get_inputs()[0].name: input_tensor.cpu().numpy()}
        ort_outs = model.run(None, ort_inputs)
        return torch.tensor(ort_outs[0], device=device)

    return run_inference


class TRLPPOTrainer(PPOTrainer):
    """
    Custom PPO Trainer that adapts TRL's PPOTrainer to work with Humanoid environments.
    """

    _tag_names = ["trl", "humanoid_ppo"]

    def __init__(
        self,
        args,
        config,
        env,
        model,
        ref_model=None,
        reward_model=None,
        processing_class=None,
        value_model=None,
        data_collator=None,
        train_dataset=None,
        eval_dataset=None,
        log_dir=None,
        # less commonly used
        optimizers=(None, None),
        callbacks=None,
        peft_config=None,
        use_ref_model=False,
        checkpoint=None,
        checkpoint_load_mode="full",
        local_seed=None,
        schedule_dict=None,
        accelerator=None,
        workflow_config=None,
    ) -> None:
        self.checkpoint_load_mode = validate_checkpoint_load_mode(checkpoint_load_mode)
        self.checkpoint_path = (
            None
            if checkpoint is None
            else str(Path(str(checkpoint)).expanduser().resolve())
        )
        self.workflow_config = workflow_config
        self._v21b_training_identity = None
        if self.checkpoint_load_mode == "policy_only" and not checkpoint:
            raise ValueError(
                "checkpoint_load_mode='policy_only' requires a non-empty checkpoint path."
            )
        self.accelerator = accelerator
        self._init_trl(
            args,
            config,
            env,
            processing_class,
            model,
            ref_model,
            reward_model,
            train_dataset,
            value_model,
            data_collator,
            eval_dataset,
            optimizers,
            callbacks,
            peft_config,
            use_ref_model,
            local_seed,
            log_dir,
            schedule_dict=schedule_dict,
        )
        self._init_config()
        self._setup_storage()

        self._a2_v23_runtime_receipt_enabled = False
        self._a2_v23_runtime_receipt_config = None
        self._a2_v23_runtime_load_facts = {
            "load_mode": self.checkpoint_load_mode,
            "actor": {"loaded": False, "state_key": None, "strict": False},
            "value": {"loaded": False, "state_key": None, "strict": False},
            "optimizer": {"loaded": False, "state_key": None},
            "scheduler": {"loaded": False, "state_key": None},
            "trainer": {"loaded": False, "state_key": None},
            "environment": {"loaded": False, "state_key": None},
        }
        self._a2_v23_runtime_restored_start_global_step = int(self.state.global_step)
        self._a2_v23_runtime_masked_stats = {
            "actions": {"max_abs": [0.0, 0.0], "sample_count": 0},
            "action_mean": {"max_abs": [0.0, 0.0], "sample_count": 0},
        }
        self._a2_v23_runtime_invocation_start_global_step = None
        self._a2_v23_runtime_invocation_end_global_step = None
        self._a2_v23_runtime_terminal_batch_completed = False

        # Initialize trajectory counter for recurrent policy training
        self._current_first_traj = 0

        self._a2_v23_runtime_receipt_config = self._resolve_a2_v23_runtime_receipt_config()
        self._a2_v23_runtime_receipt_enabled = (
            self._a2_v23_runtime_receipt_config is not None
        )

        if checkpoint is not None:
            if self.checkpoint_load_mode == "full":
                self.load_checkpoint(checkpoint)
            else:
                self.load_policy_checkpoint(checkpoint)

        self._write_a2_v23_effective_config()

    def write_r2_training_metric(self, row, output_path):
        """Append one finite, source-bound lightweight training metric row."""
        if not isinstance(row, dict) or row.get("status") is not None or row.get("verdict") is not None:
            raise ValueError("R2 training metrics are raw producer rows without adjudication fields")
        import json, math, os
        def finite(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("R2 training metric contains non-finite value")
            if isinstance(value, dict):
                for child in value.values(): finite(child)
            elif isinstance(value, list):
                for child in value: finite(child)
        finite(row)
        if row.get("schema") != "a2_piper_base_v20_R2_training_metric_v1":
            raise ValueError("R2 training metric schema identifier is required")
        if not isinstance(row.get("source_lock_sha256"), str) or len(row["source_lock_sha256"]) != 64:
            raise ValueError("R2 training metric requires a source-lock SHA-256")
        target = Path(output_path)
        if target.is_symlink():
            raise ValueError(f"R2 training metric output may not be a symlink: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        with target.open("ab") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())

    def write_v21b_training_metric(self, row, output_path):
        """Append one strict v21-B producer row without adjudication fields."""

        if not isinstance(row, dict) or row.get("status") is not None or row.get("verdict") is not None:
            raise ValueError("v21-B training metrics are raw producer rows without adjudication fields")
        if row.get("schema") != "a2_piper_base_v21B_training_metric_v1" or row.get("producer_state") != "PROCESS_COMPLETED":
            raise ValueError("v21-B training metric schema/state is invalid")
        if row.get("cell") not in {"B1", "B2", "B3", "B4", "B5", "B6", "B7"}:
            raise ValueError("v21-B training metric cell identity is invalid")
        if isinstance(row.get("seed"), bool) or row.get("seed") not in (0, 1):
            raise ValueError("v21-B training metric seed identity is invalid")
        phase = row.get("materialization_phase")
        adaptation = row.get("adaptation_bundle_sha256")
        if phase not in _V21B_MATERIALIZATION_PHASES:
            raise ValueError("v21-B training metric materialization phase identity is invalid")
        if phase == "POST_CENSUS" and adaptation is not None:
            raise ValueError("POST_CENSUS v21-B training metric adaptation identity must be null")
        if phase == "FORMAL_PROMOTED" and (not isinstance(adaptation, str) or len(adaptation) != 64 or any(char not in "0123456789abcdef" for char in adaptation)):
            raise ValueError("FORMAL_PROMOTED v21-B training metric adaptation identity is invalid")
        for key in ("source_config_sha256", "materialization_sha256", "materialized_config_sha256"):
            value = row.get(key)
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"v21-B training metric {key} identity is invalid")
        normalized = row.get("metrics")
        if not isinstance(normalized, dict) or set(normalized) != set(_V21B_METRIC_SOURCES):
            raise ValueError("v21-B training metric normalized coverage is incomplete")
        for value in normalized.values():
            if isinstance(value, bool):
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
                raise ValueError("v21-B training metric contains non-finite/non-scalar data")
        target = Path(output_path)
        if target.is_symlink():
            raise ValueError(f"v21-B training metric output may not be a symlink: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        with target.open("ab") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())

    @staticmethod
    def _v21b_file_stat(path: Path, *, label: str) -> tuple[int, int, int, int]:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"v21-B {label} is not a regular file: {path}")
        stat = path.stat()
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)

    @staticmethod
    def _v21b_sha256_file(path: Path, *, label: str) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise RuntimeError(f"v21-B cannot hash {label}: {path}") from exc
        return digest.hexdigest()

    def _v21b_required_config_identity(self, *paths: str, label: str, allow_none: bool = False) -> object:
        """Read one identity from every resolved config location and require agreement."""

        values: list[tuple[str, object]] = []
        for path in paths:
            value = OmegaConf.select(
                self._workflow_config_for_evidence(), path, default=_V21B_MISSING_CONFIG
            )
            if value is _V21B_MISSING_CONFIG or (value is None and not allow_none):
                raise RuntimeError(f"v21-B configured {label} identity is missing at {path}")
            values.append((path, value))
        first = values[0][1]
        if any(value != first for _, value in values[1:]):
            raise RuntimeError(f"v21-B configured {label} identities disagree")
        return first

    def _workflow_config_for_evidence(self):
        workflow_config = getattr(self, "workflow_config", None)
        if workflow_config is None:
            raise RuntimeError(
                "R2 training metric emission requires explicit workflow_config."
            )
        return workflow_config

    def _workflow_training_metrics_path(self) -> str:
        output_path = OmegaConf.select(
            self._workflow_config_for_evidence(), "r2_training_metrics_path", default=None
        )
        if not isinstance(output_path, str) or not output_path:
            raise RuntimeError(
                "R2 training metric emission requires r2_training_metrics_path."
            )
        return output_path

    def _get_v21b_training_identity(self) -> dict[str, object]:
        """Resolve and cache source/checkpoint/Git identity for v21-B emission."""

        workflow_config = self._workflow_config_for_evidence()
        source_lock_value = OmegaConf.select(workflow_config, "r2_source_lock_path", default=None)
        if not isinstance(source_lock_value, str) or not source_lock_value:
            raise RuntimeError("v21-B training metric emission requires r2_source_lock_path.")
        source_path = Path(source_lock_value)
        if not source_path.is_absolute():
            source_path = Path.cwd() / source_path
        source_path = source_path.absolute()

        checkpoint_value = self.checkpoint_path
        if not isinstance(checkpoint_value, str) or not checkpoint_value:
            raise RuntimeError("v21-B training metric emission requires an explicit trainer checkpoint.")
        checkpoint_path = Path(checkpoint_value).expanduser().absolute()

        cached = getattr(self, "_v21b_training_identity", None)
        if cached is not None:
            if cached["source_lock_path"] != str(source_path):
                raise RuntimeError("v21-B source-lock path changed after first metric emission")
            if cached["checkpoint_path"] != str(checkpoint_path):
                raise RuntimeError("v21-B checkpoint path changed after first metric emission")
            if self._v21b_file_stat(source_path, label="source lock") != cached["source_lock_stat"]:
                raise RuntimeError("v21-B source-lock file changed after first metric emission")
            if self._v21b_file_stat(checkpoint_path, label="checkpoint") != cached["checkpoint_stat"]:
                raise RuntimeError("v21-B checkpoint changed after first metric emission")
            self._v21b_validate_config_identity(cached)
            return cached

        source_lock_stat = self._v21b_file_stat(source_path, label="source lock")
        try:
            source_lock = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("v21-B training metric source lock is not valid JSON") from exc
        if not isinstance(source_lock, dict) or source_lock.get("schema") != "a2_piper_base_v21B_source_lock_v1":
            raise RuntimeError("v21-B training metric source lock schema is invalid")
        from scriptsFORhuman.v21B.a2_piper_v21B_source_freeze import validate_source_lock

        validate_source_lock(source_lock, Path.cwd(), require_current=True)
        source_lock_sha256 = source_lock.get("source_lock_sha256")
        source_checkpoint_sha256 = source_lock.get("source_checkpoint_sha256")
        if (
            not isinstance(source_lock_sha256, str)
            or len(source_lock_sha256) != 64
            or any(char not in "0123456789abcdef" for char in source_lock_sha256)
            or not isinstance(source_checkpoint_sha256, str)
            or len(source_checkpoint_sha256) != 64
            or any(char not in "0123456789abcdef" for char in source_checkpoint_sha256)
        ):
            raise RuntimeError("v21-B training metric source-lock identity is invalid")
        source_lock_file_sha256 = self._v21b_sha256_file(source_path, label="source lock")
        checkpoint_stat = self._v21b_file_stat(checkpoint_path, label="checkpoint")
        checkpoint_sha256 = self._v21b_sha256_file(checkpoint_path, label="checkpoint")
        if checkpoint_sha256 != source_checkpoint_sha256:
            raise RuntimeError("v21-B checkpoint does not match source-lock checkpoint identity")
        try:
            git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path.cwd(), text=True, stderr=subprocess.PIPE).strip()
            git_tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=Path.cwd(), text=True, stderr=subprocess.PIPE).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError("v21-B training metric cannot resolve current Git identity") from exc
        for name, value, length in (("git commit", git_commit, 40), ("git tree", git_tree, 40)):
            if len(value) != length or any(char not in "0123456789abcdef" for char in value):
                raise RuntimeError(f"v21-B {name} identity is invalid")
        identity = {
            "source_lock_path": str(source_path),
            "source_lock_stat": source_lock_stat,
            "source_lock_sha256": source_lock_sha256,
            "source_lock_file_sha256": source_lock_file_sha256,
            "source_checkpoint_sha256": source_checkpoint_sha256,
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_stat": checkpoint_stat,
            "checkpoint_sha256": checkpoint_sha256,
            "git_commit": git_commit,
            "git_tree": git_tree,
        }
        self._v21b_validate_config_identity(identity)
        self._v21b_training_identity = identity
        return identity

    def _v21b_validate_config_identity(self, identity: dict[str, object]) -> None:
        expected_checkpoint = self._v21b_required_config_identity(
            "v21b_source_checkpoint_sha256",
            "env.config.a2_v21B_source_checkpoint_sha256",
            label="source checkpoint",
        )
        if expected_checkpoint != identity["source_checkpoint_sha256"]:
            raise RuntimeError("v21-B configured source checkpoint identity mismatches source lock")
        expected_source_lock = self._v21b_required_config_identity(
            "v21b_source_lock_sha256",
            "env.config.a2_v21B_source_lock_sha256",
            label="source lock",
        )
        if expected_source_lock != identity["source_lock_sha256"]:
            raise RuntimeError("v21-B configured source-lock identity mismatches source lock")
        expected_cell = self._v21b_required_config_identity(
            "v21b_cell", "env.config.a2_v21B_cell", label="cell"
        )
        expected_seed = self._v21b_required_config_identity(
            "seed", "env.config.a2_v20_R2_seed", label="seed"
        )
        expected_phase = self._v21b_required_config_identity(
            "v21b_materialization_phase", "env.config.a2_v21B_materialization_phase", label="materialization phase"
        )
        if expected_phase not in _V21B_MATERIALIZATION_PHASES:
            raise RuntimeError("v21-B configured materialization phase identity is invalid")
        if expected_cell not in {"B1", "B2", "B3", "B4", "B5", "B6", "B7"}:
            raise RuntimeError("v21-B configured cell identity is invalid")
        if isinstance(expected_seed, bool) or not isinstance(expected_seed, int) or expected_seed not in (0, 1):
            raise RuntimeError("v21-B configured seed identity is invalid")
        for label, paths, identity_key in (
            (
                "source config",
                ("v21b_materialized_from_config_sha256", "env.config.a2_v21B_source_config_sha256"),
                "source_config_sha256",
            ),
            (
                "materialization",
                ("v21b_materialization_sha256", "env.config.a2_v21B_materialization_sha256"),
                "materialization_sha256",
            ),
            (
                "materialized config",
                ("v21b_materialized_config_sha256", "env.config.a2_v21B_materialized_config_sha256"),
                "materialized_config_sha256",
            ),
        ):
            expected = self._v21b_required_config_identity(*paths, label=label)
            if not isinstance(expected, str) or len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
                raise RuntimeError(f"v21-B configured {label} identity is invalid")
            if identity_key in identity and expected != identity[identity_key]:
                raise RuntimeError(f"v21-B configured {label} identity mismatches signed materialization")
            identity[identity_key] = expected
        expected_adaptation = self._v21b_required_config_identity(
            "v21b_adaptation_bundle_sha256", "env.config.a2_v21B_adaptation_bundle_sha256",
            label="adaptation bundle", allow_none=True,
        )
        if expected_phase == "POST_CENSUS":
            if expected_adaptation is not None:
                raise RuntimeError("POST_CENSUS configured adaptation identity must be null")
        elif not isinstance(expected_adaptation, str) or len(expected_adaptation) != 64 or any(char not in "0123456789abcdef" for char in expected_adaptation):
            raise RuntimeError("FORMAL_PROMOTED configured adaptation identity must be a lowercase sha256 digest")
        if "adaptation_bundle_sha256" in identity and expected_adaptation != identity["adaptation_bundle_sha256"]:
            raise RuntimeError("v21-B configured adaptation bundle identity mismatches signed materialization")
        identity["adaptation_bundle_sha256"] = expected_adaptation
        identity["materialization_phase"] = expected_phase
        identity["cell"] = expected_cell
        identity["seed"] = expected_seed

    def _write_v21b_training_metric_if_enabled(self, metrics, batch_index):
        identity = self._get_v21b_training_identity()
        row = build_v21b_training_metric_row(
            metrics,
            batch_index=batch_index,
            cell=identity["cell"],
            seed=identity["seed"],
            source_config_sha256=identity["source_config_sha256"],
            materialization_sha256=identity["materialization_sha256"],
            materialized_config_sha256=identity["materialized_config_sha256"],
            materialization_phase=identity["materialization_phase"],
            adaptation_bundle_sha256=identity["adaptation_bundle_sha256"],
            source_lock_sha256=identity["source_lock_sha256"],
            source_lock_file_sha256=identity["source_lock_file_sha256"],
            git_commit=identity["git_commit"],
            git_tree=identity["git_tree"],
            source_checkpoint_sha256=identity["source_checkpoint_sha256"],
            checkpoint_path=identity["checkpoint_path"],
            checkpoint_sha256=identity["checkpoint_sha256"],
        )
        self.write_v21b_training_metric(row, self._workflow_training_metrics_path())

    def _write_r2_training_metric_if_enabled(self, metrics, batch_index):
        """Write scalar-only JSONL telemetry; full M48 arrays remain eval-only."""
        config = self._workflow_config_for_evidence()
        if not bool(OmegaConf.select(config, "r2_evidence_enabled", default=False)):
            return
        if OmegaConf.select(config, "scientific_plan_id", default=None) == _V21B_PLAN_ID:
            self._write_v21b_training_metric_if_enabled(metrics, batch_index)
            return
        source_lock_path = OmegaConf.select(config, "r2_source_lock_path", default=None)
        if not isinstance(source_lock_path, str) or not source_lock_path:
            raise RuntimeError("R2 training metric emission requires r2_source_lock_path.")
        source_path = Path(source_lock_path)
        if not source_path.is_absolute():
            source_path = Path.cwd() / source_path
        if source_path.is_symlink() or not source_path.is_file():
            raise RuntimeError(f"R2 training metric source lock is not a regular file: {source_path}")
        source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError("R2 training metric cannot resolve current commit") from exc
        scalar_metrics = {}
        for key, value in dict(metrics).items():
            if isinstance(value, bool):
                scalar_metrics[str(key)] = value
            elif isinstance(value, (int, float)):
                if isinstance(value, float) and not math.isfinite(value):
                    raise RuntimeError(f"R2 training metric {key!r} is non-finite")
                scalar_metrics[str(key)] = value
        output_path = self._workflow_training_metrics_path()
        row = {
            "schema": "a2_piper_base_v20_R2_training_metric_v1",
            "producer_state": "PROCESS_COMPLETED",
            "source_lock_sha256": source_sha,
            "git_commit": commit,
            "batch_index": int(batch_index),
            "metrics": scalar_metrics,
        }
        self.write_r2_training_metric(row, output_path)

    def _init_trl(
        self,
        args,
        config,
        env,
        processing_class,
        model,
        ref_model,
        reward_model,
        train_dataset,
        value_model,
        data_collator,
        eval_dataset,
        optimizers,
        callbacks,
        peft_config,
        use_ref_model,
        local_seed,
        log_dir,
        schedule_dict=None,
    ):
        self.args = args
        self.config = config
        self.env = env
        self.processing_class = processing_class
        self.policy_model = model
        self.learn_normalized_actions = model.has_normalized_actions
        self.episode_env_tensors = TensorAverageMeterDict()
        self.ep_infos = []
        self.eval_callbacks = []
        self.log_dir = log_dir
        self.schedule_dict = schedule_dict
        self.scheduled_params_dict = {}
        # peft support
        if not is_peft_available() and peft_config is not None:
            raise ImportError(
                "PEFT is not installed and you passed a `peft_config` in the trainer's kwargs, please install it to use the PEFT models"
            )
        elif is_peft_available() and peft_config is not None:
            # if model is a peft model and we have a peft_confg, we merge and unload it first
            if isinstance(self.policy_model, PeftModel):
                self.policy_model = self.policy_model.merge_and_unload()

            # get peft model with the given config
            self.policy_model = get_peft_model(self.policy_model, peft_config)
            if args.bf16 and getattr(self.policy_model, "is_loaded_in_4bit", False):
                peft_module_casting_to_bf16(self.policy_model)

        self.is_peft_model = is_peft_available() and isinstance(self.policy_model, PeftModel)
        self.model_adapter_name = args.model_adapter_name
        self.ref_adapter_name = args.ref_adapter_name

        if use_ref_model:
            if ref_model:
                self.ref_model = ref_model
            elif self.is_peft_model:
                self.ref_model = None
            else:
                self.ref_model = create_reference_model(self.policy_model)
        else:
            self.ref_model = None

        self.reward_model = reward_model
        self.train_dataset = train_dataset
        self.train_dataset_len = (
            len(train_dataset) if train_dataset is not None else self.env.config.num_envs
        )
        self.value_model = value_model
        self.data_collator = data_collator
        self.eval_dataset = eval_dataset

        self.optimizer, self.lr_scheduler = optimizers
        self.optimizer_cls_and_kwargs = None  # needed for transformers >= 4.47
        #########
        # calculate various batch sizes
        #########

        accelerator = self.accelerator

        self.device = accelerator.device
        args.global_rank = accelerator.process_index
        args.world_size = accelerator.num_processes
        args.is_main_process = accelerator.is_main_process
        args.local_batch_size = self.env.config.num_envs
        args.batch_size = int(args.local_batch_size * args.world_size)
        args.mini_batch_size = exact_div(
            args.batch_size,
            args.num_mini_batches,
            "`batch_size` must be a multiple of `num_mini_batches`",
        )
        args.local_mini_batch_size = exact_div(
            args.local_batch_size,
            args.num_mini_batches,
            "`local_batch_size` must be a multiple of `num_mini_batches`",
        )

        if args.per_device_train_batch_size is None:
            args.per_device_train_batch_size = (
                args.local_mini_batch_size
            )  # same as mini-batch size, which implies no micro-batching (num_micro_batches = 1)
        args.num_micro_batches = args.local_mini_batch_size // args.per_device_train_batch_size
        args.micro_batch_size = int(args.per_device_train_batch_size * args.world_size)
        # `per_rank_rollout_batch_size` is our `args.local_batch_size`
        # `per_rank_minibatch_size` is our `args.local_mini_batch_size`
        if args.total_episodes is None:
            assert args.num_total_batches is not None
            args.total_episodes = args.num_total_batches * args.batch_size
        args.num_total_batches = math.ceil(
            args.total_episodes / args.batch_size
        )  # we may train for more than `total_episodes`
        time_tensor = torch.tensor(int(time.time()), device=accelerator.device)
        time_int = broadcast(time_tensor, 0).item()  # avoid different timestamps across processes
        args.run_name = f"{args.exp_name}__{args.seed}__{time_int}"
        self.local_seed = local_seed
        if args.num_sample_generations > 0:
            self.sample_generations_freq = max(
                1, args.num_total_batches // args.num_sample_generations
            )
        self.local_dataloader_batch_size = args.local_batch_size

        self.use_a2_base = bool(self.config.get("use_a2_base", False))
        if self.config.get("a2_base", None) is not None:
            self.use_a2_base = self.use_a2_base or bool(
                self.config.a2_base.get("enabled", False)
            )

        self.homie_walk_model = None
        self.homie_stand_model = None
        self.a2_base_model = None
        self.a2_base_action_dim = 0
        self.a2_base_obs_dim = 0
        self.a2_base_frame_dim = 0
        self.a2_base_leg_action_scale = 0.0
        self.a2_base_command_scale = 0.25
        self.a2_base_body_pitch_roll_scale = 0.4
        self.a2_base_command_multipliers = [2.0, 2.0, 0.25, 1.0, 1.0]
        self.a2_base_action_sigma = 0.0
        self.a2_base_command_clip_enabled = False
        self.a2_base_command_clip_low = None
        self.a2_base_command_clip_high = None

        if self.use_a2_base:
            a2_base_config = self.config.get("a2_base", {})
            a2_base_policy_path = a2_base_config.get(
                "policy_path", "./gr00t/rl/data/policies/A2_Base/policy.pt"
            )
            a2_base_metadata_path = a2_base_config.get(
                "metadata_path", "./gr00t/rl/data/policies/A2_Base/policy_metadata.json"
            )
            a2_base_contract = _load_a2_base_metadata(a2_base_metadata_path)
            _validate_optional_a2_config_value(
                a2_base_config, "obs_dim", a2_base_contract["obs_dim"]
            )
            _validate_optional_a2_config_value(
                a2_base_config, "action_dim", a2_base_contract["action_dim"]
            )
            _validate_optional_a2_config_value(
                a2_base_config, "leg_action_scale", a2_base_contract["leg_action_scale"]
            )
            if not a2_base_contract["use_default_offset"]:
                raise ValueError("A2_Base metadata requires use_default_offset=true")
            self.a2_base_obs_dim = a2_base_contract["obs_dim"]
            self.a2_base_frame_dim = a2_base_contract["frame_dim"]
            self.a2_base_leg_action_scale = a2_base_contract["leg_action_scale"]
            self.a2_base_action_dim = a2_base_contract["action_dim"]
            self.a2_base_command_scale = float(a2_base_config.get("command_scale", 0.25))
            self.a2_base_body_pitch_roll_scale = float(
                a2_base_config.get("body_pitch_roll_scale", 0.4)
            )
            if (
                "command_obs_multipliers" in a2_base_config
                and "command_multipliers" in a2_base_config
                and list(a2_base_config.get("command_obs_multipliers"))
                != list(a2_base_config.get("command_multipliers"))
            ):
                raise ValueError(
                    "A2_Base config command_obs_multipliers disagrees with command_multipliers"
                )
            self.a2_base_command_multipliers = list(
                a2_base_config.get(
                    "command_obs_multipliers",
                    a2_base_config.get(
                        "command_multipliers", [2.0, 2.0, 0.25, 1.0, 1.0]
                    ),
                )
            )
            self.a2_base_action_sigma = float(a2_base_config.get("action_sigma", 0.0))
            self.a2_base_command_clip_enabled = bool(
                self.env.config.get("clip_homie_command", False)
            )
            if self.a2_base_command_clip_enabled:
                self.a2_base_command_clip_low = [
                    -float(self.env.config.clip_homie_linvel_x_threshold),
                    -float(self.env.config.clip_homie_linvel_y_threshold),
                    -float(self.env.config.clip_homie_angvel_threshold),
                    float(
                        self.env.config.get(
                            "clip_homie_torso_pitch_lower_threshold",
                            -self.a2_base_body_pitch_roll_scale,
                        )
                    ),
                    float(
                        self.env.config.get(
                            "clip_homie_torso_roll_lower_threshold",
                            -self.a2_base_body_pitch_roll_scale,
                        )
                    ),
                ]
                self.a2_base_command_clip_high = [
                    float(self.env.config.clip_homie_linvel_x_threshold),
                    float(self.env.config.clip_homie_linvel_y_threshold),
                    float(self.env.config.clip_homie_angvel_threshold),
                    float(
                        self.env.config.get(
                            "clip_homie_torso_pitch_upper_threshold",
                            self.a2_base_body_pitch_roll_scale,
                        )
                    ),
                    float(
                        self.env.config.get(
                            "clip_homie_torso_roll_upper_threshold",
                            self.a2_base_body_pitch_roll_scale,
                        )
                    ),
                ]
            self.a2_base_model = torch.jit.load(a2_base_policy_path, map_location=self.device)
            self.a2_base_model.eval()
            self.a2_base_model.to(self.device)
            for p in self.a2_base_model.parameters():
                p.requires_grad = False
        else:
            # homie policy import
            homie_walk_state_dict = torch.load(
                self.config.homie_walk_model_path, map_location=self.device
            )
            homie_walk_model = HIMActorCritic(**init_actor_critic_dict)
            homie_walk_model.load_state_dict(homie_walk_state_dict["model_state_dict"])
            self.homie_walk_model = HomieActorModule(homie_walk_model).to(self.device)

            homie_stand_state_dict = torch.load(
                self.config.homie_stand_model_path, map_location=self.device
            )
            homie_stand_model = HIMActorCritic(**init_actor_critic_dict)
            homie_stand_model.load_state_dict(homie_stand_state_dict["model_state_dict"])
            self.homie_stand_model = HomieActorModule(homie_stand_model).to(self.device)

        #########
        # setup model, optimizer, and others
        #########
        if self.config.get("disable_dropout", True):
            for module in [
                self.policy_model,
                self.ref_model,
                self.value_model,
                self.reward_model,
                self.homie_walk_model,
                self.homie_stand_model,
                self.a2_base_model,
            ]:
                if module is not None:
                    disable_dropout_in_model(module)

        if self.use_a2_base:
            print("Using frozen A2_Base policy for low-level leg actions")
            disable_dropout_in_model(self.a2_base_model)
        elif not self.config.get("opt_homie", False):
            print("Freezing homie model parameters")
            for p in self.homie_walk_model.parameters():
                p.requires_grad = False
            for p in self.homie_stand_model.parameters():
                p.requires_grad = False
            self.homie_walk_model.eval()
            disable_dropout_in_model(self.homie_walk_model)
            self.homie_stand_model.eval()
            disable_dropout_in_model(self.homie_stand_model)
        self.model = PolicyAndValueWrapper(
            self.policy_model,
            self.value_model,
            self.homie_walk_model,
            self.homie_stand_model,
            a2_base_model=self.a2_base_model,
            a2_base_command_scale=self.a2_base_command_scale,
            a2_base_body_pitch_roll_scale=self.a2_base_body_pitch_roll_scale,
            a2_base_command_multipliers=self.a2_base_command_multipliers,
            a2_base_obs_dim=self.a2_base_obs_dim,
            a2_base_frame_dim=self.a2_base_frame_dim,
            a2_base_action_dim=self.a2_base_action_dim,
            a2_base_action_sigma=self.a2_base_action_sigma,
            a2_base_command_clip_enabled=self.a2_base_command_clip_enabled,
            a2_base_command_clip_low=self.a2_base_command_clip_low,
            a2_base_command_clip_high=self.a2_base_command_clip_high,
        )
        if self.use_a2_base:
            self.homie_switch_threshold = 0.0
            self.opt_homie = False
        else:
            if hasattr(self.model, "homie_switch_threshold"):
                self.homie_switch_threshold = self.model.homie_switch_threshold
            else:
                self.homie_switch_threshold = self.model.module.homie_switch_threshold

            if hasattr(self.model, "opt_homie"):
                self.model.opt_homie = self.config.get("opt_homie", False)
                self.opt_homie = self.model.opt_homie
            else:
                self.model.module.opt_homie = self.config.get("opt_homie", False)
                self.opt_homie = self.model.module.opt_homie

            if hasattr(self.model, "homie_switch_threshold"):
                self.model.homie_switch_threshold = self.config.get("homie_switch_threshold", 0.5)
            else:
                self.model.module.homie_switch_threshold = self.config.get(
                    "homie_switch_threshold", 0.5
                )

        # self.homie_policy = load_onnx_policy(path=config.homie_policy_path, device=self.device)

        # self.model.config = self.policy_model.config  # needed for pushing to hub
        self.create_optimizer_and_scheduler(
            num_training_steps=args.num_total_batches
        )  # note that we are calling `self.lr_scheduler.step()` manually only at the batch level

        #########
        ### trainer specifics
        #########

        default_callbacks = DEFAULT_CALLBACKS + get_reporting_integration_callbacks(
            self.args.report_to
        )
        self.callbacks = default_callbacks if callbacks is None else default_callbacks + callbacks

        self.callback_handler = HVCallbackHandler(
            self.callbacks,
            self.model,
            self.processing_class,
            self.optimizer,
            self.lr_scheduler,
            self.env,
            self.accelerator,
        )
        self.add_callback(
            PrinterHVCallback if self.args.disable_tqdm else DEFAULT_PROGRESS_CALLBACK
        )
        self.control = TrainerControl()
        self.state = OnlineTrainerState(
            is_local_process_zero=self.is_local_process_zero(),
            is_world_process_zero=self.is_world_process_zero(),
            stateful_callbacks=[
                cb
                for cb in self.callback_handler.callbacks + [self.control]
                if isinstance(cb, ExportableState)
            ],
        )
        self.current_flos = 0
        self.hp_search_backend = None
        self.is_deepspeed_enabled = (
            getattr(self.accelerator.state, "deepspeed_plugin", None) is not None
        )
        self.is_fsdp_enabled = getattr(self.accelerator.state, "fsdp_plugin", None) is not None
        # Create distant repo and output directory if needed
        self.hub_model_id = None
        if self.args.push_to_hub:
            self.init_hf_repo()
        if self.args.should_save:
            os.makedirs(self.args.output_dir, exist_ok=True)

        # Add tags for models that have been loaded with the correct transformers version
        if hasattr(self.model, "add_model_tags"):
            self.model.add_model_tags(self._tag_names)

        #########
        ### setup dataloader
        #########
        if self.train_dataset is not None:
            self.dataloader = DataLoader(
                self.train_dataset,
                batch_size=self.local_dataloader_batch_size,
                shuffle=True,
                collate_fn=self.data_collator,
                drop_last=False,  # needed; otherwise the last batch will be of ragged shape
            )
        else:
            self.dataloader = None
        # sync random states for DataLoader(shuffle=True) before `accelerator.prepare`
        # see https://gist.github.com/vwxyzjn/2581bff1e48e185e0b85b6dfe1def79c
        torch.manual_seed(args.seed)

        self.model, self.optimizer, self.dataloader = accelerator.prepare(
            self.model, self.optimizer, self.dataloader
        )
        self.unwrapped_model = unwrap_model(self.model)
        torch.manual_seed(self.local_seed)  # reset the local seed again

        if self.eval_dataset is not None:
            self.eval_dataloader = DataLoader(
                self.eval_dataset,
                batch_size=args.per_device_eval_batch_size,
                collate_fn=self.data_collator,
                drop_last=False,
            )  # no need to shuffle eval dataset
            self.eval_dataloader = accelerator.prepare(self.eval_dataloader)
        else:
            self.eval_dataloader = None

        if self.is_deepspeed_enabled:
            if self.reward_model is not None:
                self.reward_model = prepare_deepspeed(
                    self.reward_model, args.per_device_train_batch_size, args.fp16, args.bf16
                )

            if self.ref_model is None:
                if not self.is_peft_model:
                    raise ValueError("No reference model and model is not a Peft model.")
            else:
                self.ref_model = prepare_deepspeed(
                    self.ref_model, args.per_device_train_batch_size, args.fp16, args.bf16
                )
        else:
            if self.ref_model is None:
                # if not self.is_peft_model:
                #     raise ValueError("No reference model and model is not a Peft model.")
                pass
            else:
                self.ref_model = self.ref_model.to(self.accelerator.device)
            if self.reward_model is not None:
                self.reward_model = self.reward_model.to(self.accelerator.device)
        self.use_apex = False

        self.train_with_evaluating_env = self.config.get("train_with_evaluating_env", False)

        # Camera resolution
        if "vision_obs" in self.env.config.obs.obs_dict:
            if self.env.config.obs.obs_dict.vision_obs[0] in ["depth_image", "height_map"]:
                num_channels = 1
            elif self.env.config.obs.obs_dict.vision_obs[0] in ["rgb_image"]:
                num_channels = 3
            else:
                raise ValueError(
                    f"Invalid vision observation type: {self.env.config.obs.obs_dict.vision_obs[0]}"
                )

            if self.env.config.obs.obs_dict.vision_obs[0] == "height_map":
                heightmap_resolution = self.env.config.simulator.config.heightmap.resolution
                self.camera_resolution = [heightmap_resolution, heightmap_resolution] + [
                    num_channels
                ]
            else:
                self.camera_resolution = (
                    self.env.config.simulator.config.cameras.camera_resolutions + [num_channels]
                )
        else:
            self.camera_resolution = None

    def _init_config(self):
        # Env related Config
        self.num_envs: int = self.env.config.num_envs
        self.algo_obs_dim_dict = self.env.config.robot.algo_obs_dim_dict
        if self.use_a2_base:
            self.num_act = self.policy_model.num_actions + self.a2_base_action_dim
        else:
            self.num_act = self.policy_model.num_actions + self.homie_walk_model.num_actions

        self.num_steps_per_env = self.config.num_steps_per_env
        self.use_padding_mask = self.config.get("use_padding_mask", False)
        self.ppo_shuffle_every_epoch = self.config.get("ppo_shuffle_every_epoch", True)
        self.empty_cache_every_n_ppo_epoch = self.config.get("empty_cache_every_n_ppo_epoch", -1)

        self.entropy_coef = self.config.entropy_coef
        self.desired_kl = self.config.desired_kl
        self.gamma = self.args.gamma
        self.lam = self.args.lam
        self.sync_advantage_normalization = self.config.get("sync_advantage_normalization", True)

        self.compute_imgaug_bc_loss = self.config.get("compute_imgaug_bc_loss", False)
        self.imgaug_bc_loss_coef = self.config.get("imgaug_bc_loss_coef", 1.0)
        self.imgaug_bc_loss_fn = torch.nn.MSELoss()

    @staticmethod
    def _a2_v23_runtime_bool(value, *, name: str) -> bool:
        if not isinstance(value, bool):
            raise RuntimeError(f"{name} must be bool; got {value!r}.")
        return value

    @staticmethod
    def _a2_v23_runtime_indices(value, *, name: str) -> list[int]:
        if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple, ListConfig)):
            raise RuntimeError(f"{name} must be a list of integer action indices; got {value!r}.")
        values = list(value)
        if any(isinstance(item, bool) or not isinstance(item, int) for item in values):
            raise RuntimeError(f"{name} must contain only integer action indices; got {value!r}.")
        return values

    def _resolve_a2_v23_runtime_receipt_config(self):
        """Resolve the opt-in P0.7 receipt contract without changing default training."""

        eval_config = self.config.get("eval", {})
        if not isinstance(eval_config, (Mapping, dict, ListConfig)):
            raise RuntimeError("algo.config.eval must be a mapping when present.")
        enabled = eval_config.get("a2_v23_p0_runtime_receipt", False)
        if not isinstance(enabled, bool):
            raise RuntimeError(
                "algo.config.eval.a2_v23_p0_runtime_receipt must be bool; "
                f"got {enabled!r}."
            )
        if not enabled:
            return None

        mode = eval_config.get("a2_v23_p0_runtime_mode")
        if mode not in {"RP0", "FULL"}:
            raise RuntimeError(
                "algo.config.eval.a2_v23_p0_runtime_mode must be exactly 'RP0' or 'FULL' "
                f"when the receipt is enabled; got {mode!r}."
            )
        rp0_enabled = self._a2_v23_runtime_bool(
            self.config.get("rp0_enabled"), name="algo.config.rp0_enabled"
        )
        expected_enabled = mode == "RP0"
        if rp0_enabled != expected_enabled:
            raise RuntimeError(
                "v23 P0.7 runtime mode disagrees with algo.config.rp0_enabled: "
                f"mode={mode!r}, rp0_enabled={rp0_enabled!r}."
            )

        indices = self._a2_v23_runtime_indices(
            self.config.get("rp0_mask_indices"), name="algo.config.rp0_mask_indices"
        )
        if indices != list(_A2_V23_RP0_RUNTIME_MASK_INDICES):
            raise RuntimeError(
                "v23 P0.7 runtime requires algo.config.rp0_mask_indices=[3,4]; "
                f"got {indices!r}."
            )
        neutral = self.config.get("rp0_neutral_value")
        if isinstance(neutral, bool) or not isinstance(neutral, (int, float)):
            raise RuntimeError(
                "algo.config.rp0_neutral_value must be numeric when the receipt is enabled; "
                f"got {neutral!r}."
            )
        neutral = float(neutral)
        if not math.isfinite(neutral) or neutral != _A2_V23_RP0_RUNTIME_NEUTRAL:
            raise RuntimeError(
                "v23 P0.7 runtime requires algo.config.rp0_neutral_value=0.0; "
                f"got {neutral!r}."
            )

        env_config = self.env.config
        env_enabled = self._a2_v23_runtime_bool(
            env_config.get("a2_v23_rp0_enabled"),
            name="env.config.a2_v23_rp0_enabled",
        )
        if env_enabled != rp0_enabled:
            raise RuntimeError(
                "v23 P0.7 runtime env/algo RP0 enable flags disagree: "
                f"env={env_enabled!r}, algo={rp0_enabled!r}."
            )
        env_indices = self._a2_v23_runtime_indices(
            env_config.get("a2_v23_rp0_mask_indices"),
            name="env.config.a2_v23_rp0_mask_indices",
        )
        if env_indices != indices:
            raise RuntimeError(
                "v23 P0.7 runtime env/algo RP0 mask indices disagree: "
                f"env={env_indices!r}, algo={indices!r}."
            )
        env_neutral = env_config.get("a2_v23_rp0_neutral_value")
        if isinstance(env_neutral, bool) or not isinstance(env_neutral, (int, float)):
            raise RuntimeError(
                "env.config.a2_v23_rp0_neutral_value must be numeric when the receipt is enabled; "
                f"got {env_neutral!r}."
            )
        if float(env_neutral) != neutral:
            raise RuntimeError(
                "v23 P0.7 runtime env/algo RP0 neutral values disagree: "
                f"env={env_neutral!r}, algo={neutral!r}."
            )
        if int(self.env.num_envs) != _A2_V23_RP0_RUNTIME_ENVS:
            raise RuntimeError(
                "v23 P0.7 runtime receipt requires exactly 64 environments; "
                f"got {self.env.num_envs!r}."
            )

        if int(self.accelerator.num_processes) != 1:
            raise RuntimeError(
                "v23 P0.7 runtime receipt is a canonical single-rank contract; "
                f"got world_size={self.accelerator.num_processes}."
            )
        physical_gpu_count = int(torch.cuda.device_count())
        if physical_gpu_count != 1:
            raise RuntimeError(
                "v23 P0.7 runtime receipt requires exactly one visible physical GPU; "
                f"got physical_gpu_count={physical_gpu_count}."
            )
        workflow = self.workflow_config
        if workflow is None:
            raise RuntimeError("v23 P0.7 runtime receipt requires the resolved workflow config.")
        workflow_num_gpus = workflow.get("num_gpus")
        if workflow_num_gpus != 1:
            raise RuntimeError(
                "v23 P0.7 runtime workflow config must declare num_gpus=1; "
                f"got {workflow_num_gpus!r}."
            )
        if workflow.get("multi_gpu") is not False:
            raise RuntimeError("v23 P0.7 runtime workflow config must declare multi_gpu=false.")
        workflow_num_envs = workflow.get("num_envs")
        if workflow_num_envs != _A2_V23_RP0_RUNTIME_ENVS:
            raise RuntimeError(
                "v23 P0.7 runtime workflow config must resolve num_envs=64; "
                f"got {workflow_num_envs!r}."
            )
        workflow_load_mode = workflow.get("checkpoint_load_mode")
        expected_load_mode = "policy_only" if mode == "RP0" else "full"
        if workflow_load_mode != expected_load_mode or self.checkpoint_load_mode != expected_load_mode:
            raise RuntimeError(
                "v23 P0.7 runtime checkpoint load mode mismatch: "
                f"workflow={workflow_load_mode!r}, trainer={self.checkpoint_load_mode!r}, "
                f"expected={expected_load_mode!r}."
            )
        if workflow.get("auto_load_latest") is not False:
            raise RuntimeError("v23 P0.7 runtime requires auto_load_latest=false.")
        if self.checkpoint_path is None or not Path(self.checkpoint_path).is_file():
            raise RuntimeError(
                "v23 P0.7 runtime receipt requires an existing explicit input checkpoint."
            )
        expected_initial_step10_path = None
        if mode == "FULL":
            expected_raw = workflow.get("expected_initial_step10_checkpoint_path")
            if not isinstance(expected_raw, str) or not expected_raw:
                raise RuntimeError(
                    "v23 P0.7 FULL runtime requires an explicit expected_initial_step10_checkpoint_path."
                )
            expected_path = Path(expected_raw).expanduser()
            if not expected_path.is_absolute():
                raise RuntimeError(
                    "v23 P0.7 FULL expected_initial_step10_checkpoint_path must be absolute."
                )
            if expected_path.is_symlink() or not expected_path.is_file():
                raise RuntimeError(
                    "v23 P0.7 FULL expected_initial_step10_checkpoint_path must be an existing regular file: "
                    f"{expected_path}"
                )
            expected_path = expected_path.resolve()
            actual_path = Path(self.checkpoint_path).expanduser().resolve()
            if actual_path != expected_path:
                raise RuntimeError(
                    "v23 P0.7 FULL checkpoint path does not exactly match the expected RP0 step10 path: "
                    f"actual={actual_path}, expected={expected_path}."
                )
            if expected_path.name != "model_step_000010.pt":
                raise RuntimeError(
                    "v23 P0.7 FULL expected_initial_step10_checkpoint_path must name model_step_000010.pt; "
                    f"got {expected_path.name!r}."
                )
            expected_initial_step10_path = str(expected_path)
        elif workflow.get("expected_initial_step10_checkpoint_path") is not None:
            raise RuntimeError(
                "v23 P0.7 RP0 runtime must leave FULL-only expected_initial_step10_checkpoint_path unset."
            )

        effort_nm = env_config.get("a2_v23_effort_profile_nm")
        if isinstance(effort_nm, bool) or not isinstance(effort_nm, (int, float)) or float(effort_nm) != 100.0:
            raise RuntimeError(
                "v23 P0.7 runtime receipt requires contract-only arm effort 100.0 Nm; "
                f"got {effort_nm!r}."
            )
        effort_source = env_config.get("a2_v23_effort_profile_source")
        if effort_source != "P0_CONTRACT_ONLY_NOT_V23_FREEZE":
            raise RuntimeError(
                "v23 P0.7 runtime receipt requires the contract-only effort provenance; "
                f"got {effort_source!r}."
            )

        callback_matches = [
            callback
            for callback in self.callbacks
            if hasattr(callback, "save_frequency") and hasattr(callback, "save_dir")
        ]
        if len(callback_matches) != 1:
            raise RuntimeError(
                "v23 P0.7 runtime receipt requires exactly one model-save callback with "
                f"save_frequency/save_dir; found {len(callback_matches)}."
            )
        callback = callback_matches[0]
        save_frequency = callback.save_frequency
        if isinstance(save_frequency, bool) or not isinstance(save_frequency, int):
            raise RuntimeError(
                "v23 P0.7 runtime model-save callback frequency must be an integer; "
                f"got {save_frequency!r}."
            )
        expected_frequency = 10 if mode == "RP0" else 1
        if save_frequency != expected_frequency:
            raise RuntimeError(
                "v23 P0.7 runtime model-save frequency mismatch: "
                f"got {save_frequency}, expected {expected_frequency} for {mode}."
            )
        save_dir = Path(str(callback.save_dir)).expanduser().resolve()
        output_dir = Path(str(self.args.output_dir)).expanduser().resolve()
        if save_dir != output_dir:
            raise RuntimeError(
                "v23 P0.7 runtime checkpoint directory must equal the invocation output directory: "
                f"save_dir={save_dir}, output_dir={output_dir}."
            )
        expected_batches = 10 if mode == "RP0" else 1
        if int(self.args.num_total_batches) != expected_batches:
            raise RuntimeError(
                "v23 P0.7 runtime invocation batch mismatch: "
                f"got {self.args.num_total_batches}, expected {expected_batches} for {mode}."
            )
        input_name = Path(self.checkpoint_path).name
        expected_input_name = "model_step_001250.pt" if mode == "RP0" else "model_step_000010.pt"
        if input_name != expected_input_name:
            raise RuntimeError(
                "v23 P0.7 runtime input checkpoint name mismatch: "
                f"got {input_name!r}, expected {expected_input_name!r}."
            )

        return {
            "schema": _A2_V23_RP0_RUNTIME_RECEIPT_SCHEMA,
            "mode": mode,
            "rp0_enabled": rp0_enabled,
            "mask_indices": indices,
            "neutral_value": neutral,
            "env_count": int(self.env.num_envs),
            "checkpoint_load_mode": expected_load_mode,
            "invocation_batches": expected_batches,
            "save_frequency": expected_frequency,
            "input_checkpoint_path": str(Path(self.checkpoint_path).resolve()),
            "expected_initial_step10_checkpoint_path": expected_initial_step10_path,
            "output_dir": str(output_dir),
            "effort_profile_nm": float(effort_nm),
            "effort_profile_source": effort_source,
        }

    def _write_a2_v23_effective_config(self) -> None:
        if not self._a2_v23_runtime_receipt_enabled:
            return
        if not self.accelerator.is_main_process:
            raise RuntimeError("v23 P0.7 canonical config writing requires the sole rank to be main.")
        config = self._a2_v23_runtime_receipt_config
        if config is None:
            raise RuntimeError("v23 P0.7 effective config requires resolved receipt config.")
        run_dir = Path(config["output_dir"])
        effective_path = run_dir / _A2_V23_RP0_EFFECTIVE_CONFIG_FILENAME
        if effective_path.is_symlink() or effective_path.exists():
            raise RuntimeError(
                "v23 P0.7 effective config path must be a new canonical sibling: "
                f"{effective_path}"
            )
        expected_start = 0 if config["mode"] == "RP0" else 10
        expected_end = 10 if config["mode"] == "RP0" else 11
        payload = {
            "schema": _A2_V23_RP0_EFFECTIVE_CONFIG_SCHEMA,
            "status": "EFFECTIVE_CONFIG_VERIFIED",
            "canonical_run_dir": str(run_dir.resolve()),
            "physical_gpu_count": 1,
            "world_size": 1,
            "mode": config["mode"],
            "rp0_enabled": config["rp0_enabled"],
            "mask_indices": list(config["mask_indices"]),
            "neutral_value": config["neutral_value"],
            "env_count": config["env_count"],
            "invocation_batches": config["invocation_batches"],
            "save_frequency": config["save_frequency"],
            "input_checkpoint_path": config["input_checkpoint_path"],
            "checkpoint_load_mode": config["checkpoint_load_mode"],
            "auto_load_latest": False,
            "expected_initial_step10_checkpoint_path": config[
                "expected_initial_step10_checkpoint_path"
            ],
            "effort_profile_nm": config["effort_profile_nm"],
            "effort_profile_source": config["effort_profile_source"],
            "expected_start_global_step": expected_start,
            "expected_end_global_step": expected_end,
            "expected_output_checkpoint_path": str(
                (run_dir / f"model_step_{expected_end:06d}.pt").resolve()
            ),
            "launcher_config_path": str((run_dir / "config.yaml").resolve()),
        }
        run_dir.mkdir(parents=True, exist_ok=True)
        with effective_path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        config["effective_config_path"] = str(effective_path.resolve())

    def _a2_v23_runtime_mask_vector(self) -> list[bool]:
        policy = self.policy_model
        mask = getattr(policy, "rp0_action_mask", None)
        if not isinstance(mask, torch.Tensor) or mask.ndim != 1:
            raise RuntimeError(
                "v23 P0.7 runtime receipt requires the actor's reconstructed rp0_action_mask."
            )
        if mask.numel() < max(_A2_V23_RP0_RUNTIME_MASK_INDICES) + 1:
            raise RuntimeError("v23 P0.7 runtime actor mask is shorter than raw posture indices [3,4].")
        return [bool(value) for value in mask.detach().cpu().tolist()]

    def _a2_v23_record_masked_rollout_stats(self) -> None:
        if not self._a2_v23_runtime_receipt_enabled:
            return
        indices = list(_A2_V23_RP0_RUNTIME_MASK_INDICES)
        for field in ("actions", "action_mean"):
            values = self.storage.query_key(field)
            if values.ndim != 3 or values.shape[-1] <= max(indices):
                raise RuntimeError(
                    f"v23 P0.7 runtime {field} rollout tensor must be [steps,envs,actions] "
                    f"with raw indices [3,4]; got shape={tuple(values.shape)}."
                )
            selected = values[..., indices].detach().abs().reshape(-1, len(indices))
            local_max = selected.amax(dim=0)
            gathered = self.accelerator.gather_for_metrics(local_max)
            if gathered.numel() % len(indices) != 0:
                raise RuntimeError("v23 P0.7 runtime gathered masked statistics have an invalid shape.")
            global_max = gathered.reshape(-1, len(indices)).amax(dim=0).cpu().tolist()
            previous = self._a2_v23_runtime_masked_stats[field]["max_abs"]
            self._a2_v23_runtime_masked_stats[field]["max_abs"] = [
                max(float(previous[index]), float(global_max[index]))
                for index in range(len(indices))
            ]
            sample_count = int(selected.shape[0]) * int(self.accelerator.num_processes)
            self._a2_v23_runtime_masked_stats[field]["sample_count"] += sample_count

    def _a2_v23_runtime_output_checkpoint(self) -> Path:
        if self._a2_v23_runtime_receipt_config is None:
            raise RuntimeError("v23 P0.7 runtime receipt config was not resolved.")
        end_step = self._a2_v23_runtime_invocation_end_global_step
        if end_step is None:
            raise RuntimeError("v23 P0.7 runtime receipt has no terminal global step.")
        expected_step = 10 if self._a2_v23_runtime_receipt_config["mode"] == "RP0" else 11
        if end_step != expected_step:
            raise RuntimeError(
                "v23 P0.7 runtime post-batch step mismatch: "
                f"got {end_step}, expected {expected_step}."
            )
        output_path = Path(self._a2_v23_runtime_receipt_config["output_dir"]) / (
            f"model_step_{end_step:06d}.pt"
        )
        if output_path.is_symlink() or not output_path.is_file():
            raise RuntimeError(
                "v23 P0.7 runtime receipt requires a real terminal model-save checkpoint: "
                f"{output_path}"
            )
        return output_path

    def _write_a2_v23_runtime_receipt(self) -> None:
        if not self._a2_v23_runtime_receipt_enabled:
            return
        if not self.accelerator.is_main_process:
            return
        config = self._a2_v23_runtime_receipt_config
        if config is None:
            raise RuntimeError("v23 P0.7 runtime receipt was enabled without resolved config.")
        if not self._a2_v23_runtime_terminal_batch_completed:
            raise RuntimeError("v23 P0.7 runtime receipt requires the terminal invocation batch.")
        start_step = self._a2_v23_runtime_invocation_start_global_step
        end_step = self._a2_v23_runtime_invocation_end_global_step
        expected_start = 0 if config["mode"] == "RP0" else 10
        if start_step != expected_start:
            raise RuntimeError(
                "v23 P0.7 runtime start global step mismatch: "
                f"got {start_step}, expected {expected_start}."
            )
        output_path = self._a2_v23_runtime_output_checkpoint()
        input_path = Path(config["input_checkpoint_path"])
        actor_mask = self._a2_v23_runtime_mask_vector()
        expected_masked_zero = config["mode"] == "RP0"
        for field in ("actions", "action_mean"):
            stats = self._a2_v23_runtime_masked_stats[field]
            if stats["sample_count"] <= 0:
                raise RuntimeError(f"v23 P0.7 runtime {field} masked stats have no rollout samples.")
            if expected_masked_zero and any(value != 0.0 for value in stats["max_abs"]):
                raise RuntimeError(
                    f"v23 P0.7 RP0 runtime requires exact zero masked {field}; got {stats['max_abs']}."
                )
        load_facts = self._a2_v23_runtime_load_facts
        if load_facts.get("load_mode") != config["checkpoint_load_mode"]:
            raise RuntimeError("v23 P0.7 runtime load facts disagree with the configured load mode.")
        if config["mode"] == "RP0":
            if not load_facts["actor"].get("loaded") or load_facts["value"].get("loaded"):
                raise RuntimeError("v23 P0.7 RP0 receipt has inconsistent policy-only restore facts.")
        else:
            required = ("actor", "value", "optimizer", "scheduler", "trainer")
            if any(not load_facts[key].get("loaded") for key in required):
                raise RuntimeError("v23 P0.7 FULL receipt requires strict actor/value/optimizer/scheduler/trainer restore facts.")

        payload = {
            "schema": _A2_V23_RP0_RUNTIME_RECEIPT_SCHEMA,
            "status": "RUNTIME_RECEIPT_VERIFIED",
            "mode": config["mode"],
            "contract": {
                "rp0_enabled": config["rp0_enabled"],
                "mask_vector": actor_mask,
                "mask_indices": list(config["mask_indices"]),
                "neutral_value": config["neutral_value"],
                "env_count": config["env_count"],
            },
            "checkpoint": {
                "input_path": str(input_path),
                "input_exists": input_path.is_file() and not input_path.is_symlink(),
                "load_mode": config["checkpoint_load_mode"],
                "output_path": str(output_path.resolve()),
                "output_exists": True,
            },
            "global_step": {
                "restored_start": int(self._a2_v23_runtime_restored_start_global_step),
                "invocation_start": int(start_step),
                "post_batch_end": int(end_step),
            },
            "invocation": {
                "num_total_batches": int(config["invocation_batches"]),
                "save_frequency": int(config["save_frequency"]),
                "terminal_batch_completed": True,
                "terminal_save_verified": True,
            },
            "masked_stats": self._a2_v23_runtime_masked_stats,
            "restore_facts": load_facts,
            "canonical_run_dir": config["output_dir"],
            "effective_config_path": config["effective_config_path"],
            "expected_initial_step10_checkpoint_path": config[
                "expected_initial_step10_checkpoint_path"
            ],
            "receipt_path": str(
                (Path(config["output_dir"]) / _A2_V23_RP0_RUNTIME_RECEIPT_FILENAME).resolve()
            ),
            "environment_continuity": False,
            "environment_continuity_basis": "trainer_reset_all_after_checkpoint_restore",
        }
        output_dir = Path(config["output_dir"])
        receipt_path = output_dir / _A2_V23_RP0_RUNTIME_RECEIPT_FILENAME
        if receipt_path.is_symlink() or receipt_path.exists():
            raise RuntimeError(f"v23 P0.7 runtime receipt path must be a new canonical file: {receipt_path}")
        temporary_path = receipt_path.with_suffix(".json.tmp")
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, receipt_path)
        logger.info("Saved v23 P0.7 runtime receipt to %s", receipt_path)

    def _setup_storage(self):
        self.storage = RolloutStorage(
            self.env.num_envs, self.num_steps_per_env, device=self.accelerator.device
        )
        ## Register obs keys
        for obs_key, obs_dim in self.algo_obs_dim_dict.items():
            if obs_key == "vision_obs":
                assert obs_dim == np.prod(
                    self.camera_resolution
                ), f"{obs_dim=}, {self.camera_resolution=}"
                self.storage.register_key(
                    obs_key, shape=tuple(self.camera_resolution), dtype=torch.float
                )
            else:
                self.storage.register_key(obs_key, shape=(obs_dim,), dtype=torch.float)

        ## Register others
        self.storage.register_key("actions", shape=(self.num_act,), dtype=torch.float)
        self.storage.register_key("rewards", shape=(1,), dtype=torch.float)
        self.storage.register_key("dones", shape=(1,), dtype=torch.bool)
        self.storage.register_key("time_outs", shape=(1,), dtype=torch.bool)
        self.storage.register_key("values", shape=(1,), dtype=torch.float)
        self.storage.register_key("returns", shape=(1,), dtype=torch.float)
        self.storage.register_key("advantages", shape=(1,), dtype=torch.float)
        self.storage.register_key("actions_log_prob", shape=(1,), dtype=torch.float)
        self.storage.register_key("action_mean", shape=(self.num_act,), dtype=torch.float)
        self.storage.register_key("action_sigma", shape=(self.num_act,), dtype=torch.float)

        # Register hidden states for recurrent models (if applicable)
        # Note: hidden states are stored as nested structures (not tensors directly)
        # We'll handle them separately in the rollout loop

        if self.learn_normalized_actions:
            self.storage.register_key(
                "normalized_actions", shape=(self.num_act,), dtype=torch.float
            )

        self.state.rewbuffer = deque(maxlen=100)
        self.state.lenbuffer = deque(maxlen=100)
        self.cur_reward_sum = torch.zeros(
            self.env.num_envs, dtype=torch.float, device=self.accelerator.device
        )
        self.cur_episode_length = torch.zeros(
            self.env.num_envs, dtype=torch.float, device=self.accelerator.device
        )
        self.state.cur_reward_sum = self.cur_reward_sum
        self.state.cur_episode_length = self.cur_episode_length
        self.ep_infos = []
        self.state.tot_timesteps = 0
        self.state.tot_time = 0
        self.state.eval_step = 0
        self.state.eval_render_step = 0

    def policy_step(
        self,
        policy_model,
        homie_walk_model,
        homie_stand_model,
        obs_dict,
        cur_dones=None,
        store_hidden_states=True,
    ):
        actor_obs_dict = deepcopy(obs_dict)

        if cur_dones is None:
            dones = (
                self.storage.query_key("dones")
                .to(self.accelerator.device)[: self.storage.step + 1]
                .squeeze(-1)
                .transpose(0, 1)
            )
            episode_attnmask = compute_episode_attnmask(dones)
        else:
            episode_attnmask = None

        # Store hidden states BEFORE rollout for recurrent policies
        actor_hidden_states = None
        if (
            store_hidden_states
            and hasattr(policy_model, "is_recurrent")
            and policy_model.is_recurrent
        ):
            actor_hidden_states = policy_model.get_hidden_states()

        policy_out = policy_model.rollout(
            obs_dict=actor_obs_dict, episode_attnmask=episode_attnmask, cur_dones=cur_dones
        )

        if self.use_a2_base:
            a2_actions = self.unwrapped_model._a2_base_actions(
                obs_dict, policy_out["actions"]
            )
            actions_log_prob = policy_model.get_actions_log_prob(
                actions=policy_out["actions"]
            ).unsqueeze(1)
            a2_sigma = torch.full_like(a2_actions, self.a2_base_action_sigma)
            policy_state_dict = {
                "actions": torch.cat([policy_out["actions"], a2_actions], dim=-1),
                "action_mean": torch.cat([policy_out["action_mean"], a2_actions], dim=-1),
                "action_sigma": torch.cat([policy_out["action_sigma"], a2_sigma], dim=-1),
                "actions_log_prob": actions_log_prob,
            }

            if store_hidden_states and actor_hidden_states is not None:
                policy_state_dict["hidden_states"] = (
                    actor_hidden_states,
                    None,
                )

            return policy_state_dict

        homie_obs = obs_dict["homie_obs"]
        stand_homie_obs = homie_obs.clone()
        reshaped_obs = stand_homie_obs.view(
            stand_homie_obs.shape[0], 6, stand_homie_obs.shape[-1] // 6
        )
        reshaped_obs[..., :3] = 0.0
        stand_homie_obs = reshaped_obs.view_as(stand_homie_obs)
        walk_out = self.homie_walk_model(homie_obs)
        stand_out = self.homie_stand_model(stand_homie_obs)
        homie_one_step_obs = init_actor_critic_dict["num_one_step_obs"]
        commands = obs_dict["homie_obs"][..., -homie_one_step_obs : -(homie_one_step_obs - 3)]

        walk_mask = (
            torch.norm(commands, dim=-1, keepdim=True) > self.homie_switch_threshold
        )  # [B,1]

        def _sel(a_walk, a_stand):
            m = walk_mask
            while m.dim() < a_walk.dim():
                m = m.unsqueeze(-1)
            return torch.where(m, a_walk, a_stand)

        homie_actions = _sel(walk_out["actions"], stand_out["actions"])
        homie_mean = _sel(walk_out["action_mean"], stand_out["action_mean"])
        homie_sigma = _sel(walk_out["action_sigma"], stand_out["action_sigma"])
        homie_entropy = _sel(walk_out["entropy"], stand_out["entropy"])

        policy_actions_log_prob = policy_model.get_actions_log_prob(actions=policy_out["actions"])
        walk_lp = homie_walk_model.get_actions_log_prob(actions=homie_actions)
        stand_lp = homie_stand_model.get_actions_log_prob(actions=homie_actions)
        homie_actions_log_prob = torch.where(walk_mask.squeeze(-1), walk_lp, stand_lp)

        if self.opt_homie:
            actions_log_prob = (policy_actions_log_prob + homie_actions_log_prob).unsqueeze(1)
        else:
            actions_log_prob = policy_actions_log_prob.unsqueeze(1)

        actions = torch.cat([policy_out["actions"], homie_actions], dim=-1)
        action_mean = torch.cat([policy_out["action_mean"], homie_mean], dim=-1)
        action_sigma = torch.cat([policy_out["action_sigma"], homie_sigma], dim=-1)

        policy_state_dict = {
            "actions": actions,
            "action_mean": action_mean,
            "action_sigma": action_sigma,
            "actions_log_prob": actions_log_prob,
        }

        # Add hidden states to return dict if they were captured
        if store_hidden_states and actor_hidden_states is not None:
            policy_state_dict["hidden_states"] = (
                actor_hidden_states,
                None,
            )  # (actor, critic) - critic is computed separately

        return policy_state_dict

    def _chunked_value_evaluate(self, value_model, obs_dict, episode_attnmask, chunk_size=1024):
        batch_size = list(obs_dict.values())[0].shape[0]
        if batch_size <= chunk_size:
            return value_model.evaluate(obs_dict=obs_dict, episode_attnmask=episode_attnmask)

        obs_chunks = {}
        for key, value in obs_dict.items():
            obs_chunks[key] = torch.split(value, chunk_size, dim=0)
        if episode_attnmask is not None:
            attnmask_chunks = torch.split(episode_attnmask, chunk_size, dim=0)
        else:
            attnmask_chunks = [None] * len(obs_chunks[list(obs_chunks.keys())[0]])

        value_chunks = []
        for i in range(len(attnmask_chunks)):
            chunk_obs_dict = {key: obs_chunks[key][i] for key in obs_chunks}
            chunk_values = value_model.evaluate(
                obs_dict=chunk_obs_dict, episode_attnmask=attnmask_chunks[i]
            )
            value_chunks.append(chunk_values)
        return torch.cat(value_chunks, dim=0)

    def _rollout_step(self, model, obs_dict):
        self._train_rollout_mode()
        device = self.accelerator.device
        policy_model = model.policy
        value_model = model.value_model
        homie_walk_model = model.homie_walk_model
        homie_stand_model = model.homie_stand_model
        policy_model.init_rollout()
        self.storage.clear()

        dones = torch.zeros(self.env.num_envs, device=device)
        # Check if we need to compute values step-by-step for recurrent models
        is_recurrent = hasattr(policy_model, "is_recurrent") and policy_model.is_recurrent

        with torch.no_grad():
            for i in range(self.num_steps_per_env):
                # Compute the actions and values
                # TODO: 1: unsqueeze to [B, 1, ...]
                policy_state_dict = self.policy_step(
                    policy_model, homie_walk_model, homie_stand_model, obs_dict, cur_dones=dones
                )
                # homie_actions = homie_model(obs_dict['homie_obs'])
                # step_actions = torch.cat([policy_state_dict["actions"], homie_actions["actions"]], dim=-1) # commands + arm_hand_actions + leg_waist_actions

                # For recurrent models, compute values step-by-step to maintain critic hidden states
                if self.value_model is not None:
                    # Check if value model is also recurrent
                    value_is_recurrent = (
                        hasattr(self.value_model, "is_recurrent") and self.value_model.is_recurrent
                    )
                    if value_is_recurrent:
                        # Get critic hidden states BEFORE evaluation
                        critic_hidden_states = (
                            self.value_model.get_hidden_states()
                            if hasattr(self.value_model, "get_hidden_states")
                            else None
                        )
                        # Evaluate the critic to update its hidden states and get values
                        # For recurrent critics, we MUST compute values step-by-step during rollout
                        critic_obs_dict = {k: v for k, v in obs_dict.items() if k != "actor_obs"}
                        step_values = self.value_model.evaluate(obs_dict=critic_obs_dict)
                        # Save values to storage for GAE computation
                        policy_state_dict["values"] = step_values
                        # Store both actor and critic hidden states
                        combined_hidden_states = (
                            policy_state_dict.get("hidden_states", (None, None))[0],
                            critic_hidden_states,
                        )
                        policy_state_dict["hidden_states"] = combined_hidden_states

                # Append states to storage
                for key, value in obs_dict.items():
                    self.storage.update_key(key, value)
                for key, value in policy_state_dict.items():
                    # Skip hidden_states as they're stored separately
                    if key != "hidden_states":
                        self.storage.update_key(key, value)

                # Store hidden states separately for recurrent policies
                if "hidden_states" in policy_state_dict:
                    self.storage._save_hidden_states(policy_state_dict["hidden_states"])
                # Step the environment
                actor_state = {"actions": policy_state_dict["actions"]}
                # Pass gt_actions to environment if available (for distillation mode)
                if "gt_actions" in policy_state_dict:
                    actor_state["gt_actions"] = policy_state_dict["gt_actions"]
                obs_dict, rewards, dones, infos = self.env.step(actor_state)
                for obs_key in obs_dict.keys():
                    obs_dict[obs_key] = obs_dict[obs_key].to(device)
                rewards, dones = rewards.to(device), dones.to(device)
                rewards_stored = rewards.clone().unsqueeze(1)
                assert len(rewards_stored.shape) == 2

                self.ep_infos.append(infos["episode"])
                self.storage.update_key("rewards", rewards_stored)
                self.storage.update_key("dones", dones.unsqueeze(1))
                self.storage.update_key("time_outs", infos["time_outs"].unsqueeze(1))
                self.storage.increment_step()

                self._process_env_step(rewards, dones, infos)

                self.cur_reward_sum += rewards
                self.cur_episode_length += 1
                new_ids = (dones > 0).nonzero(as_tuple=False)
                self.state.rewbuffer.extend(
                    self.cur_reward_sum[new_ids][:, 0].cpu().numpy().tolist()
                )
                self.state.lenbuffer.extend(
                    self.cur_episode_length[new_ids][:, 0].cpu().numpy().tolist()
                )
                self.cur_reward_sum[new_ids] = 0
                self.cur_episode_length[new_ids] = 0

            if self.value_model is not None:
                # Check if critic is recurrent
                value_is_recurrent = (
                    hasattr(self.value_model, "is_recurrent") and self.value_model.is_recurrent
                )

                if value_is_recurrent:
                    # For recurrent critics: values were already computed step-by-step during rollout
                    # We only need to compute the final bootstrapping value
                    critic_obs_dict = {k: v for k, v in obs_dict.items() if k != "actor_obs"}
                    last_values = self.value_model.evaluate(
                        obs_dict=critic_obs_dict
                    )  # Shape: [num_envs, 1]
                    # Values are already in storage from step-by-step computation
                    values = self.storage.query_key("values").to(
                        device
                    )  # Shape: [num_steps, num_envs, 1]
                else:
                    # For non-recurrent critics: compute all values at once
                    dones = self.storage.query_key("dones").to(device).squeeze(-1).transpose(0, 1)
                    dones = torch.cat([dones, torch.zeros_like(dones[:, :1])], dim=1)
                    episode_attnmask = compute_episode_attnmask(dones)
                    all_obs_dict = {}
                    for key in obs_dict.keys():
                        if key not in ["actor_obs"]:  # actor_obs not required by value model
                            obs_value = self.storage.query_key(key).to(device)
                            obs_value = torch.cat([obs_value, obs_dict[key].unsqueeze(0)], dim=0)
                            all_obs_dict[key] = obs_value.transpose(0, 1)
                    all_values = self._chunked_value_evaluate(
                        value_model, all_obs_dict, episode_attnmask
                    ).transpose(0, 1)
                    values, last_values = all_values[:-1], all_values[-1]

                rewards = self.storage.query_key("rewards")
                new_rewards = (
                    rewards.to(device)
                    + self.gamma * self.storage.query_key("time_outs").to(device) * values
                )
                self.storage.batch_update_data("rewards", new_rewards)

                returns, advantages = self._compute_returns(
                    values=values,
                    last_values=last_values,
                    policy_state_dict={
                        "dones": self.storage.query_key("dones"),
                        "rewards": self.storage.query_key("rewards"),
                    },
                )
                self.storage.batch_update_data("values", values)
                self.storage.batch_update_data("returns", returns)
                self.storage.batch_update_data("advantages", advantages)

        self._a2_v23_record_masked_rollout_stats()
        policy_model.clear_rollout()
        return obs_dict

    def _process_env_step(self, rewards, dones, infos):
        self.policy_model.reset(dones)
        if self.value_model is not None:
            self.value_model.reset(dones)
        prepared_env_metrics = _prepare_a2_env_metrics_for_aggregation(
            infos["to_log"], self.accelerator, self.accelerator.device
        )
        self.episode_env_tensors.add(prepared_env_metrics)

    def _register_stats_buffer(self):
        args = self.args
        device = self.accelerator.device

        stats_shape = (args.num_ppo_epochs, args.num_mini_batches, args.num_micro_batches)
        approxkl_stats = torch.zeros(stats_shape, device=device)
        pg_clipfrac_stats = torch.zeros(stats_shape, device=device)
        pg_loss_stats = torch.zeros(stats_shape, device=device)
        vf_loss_stats = torch.zeros(stats_shape, device=device)
        entropy_stats = torch.zeros(stats_shape, device=device)
        weighted_ppo_loss_stats = torch.zeros(stats_shape, device=device)
        vf_clipfrac_stats = torch.zeros(stats_shape, device=device)
        ratio_stats = torch.zeros(stats_shape, device=device)
        if self.compute_imgaug_bc_loss:
            imgaug_bc_loss_stats = torch.zeros(stats_shape, device=device)
            weighted_imgaug_bc_loss_stats = torch.zeros(stats_shape, device=device)

        self.approxkl_stats = approxkl_stats
        self.pg_clipfrac_stats = pg_clipfrac_stats
        self.pg_loss_stats = pg_loss_stats
        self.vf_loss_stats = vf_loss_stats
        self.entropy_stats = entropy_stats
        self.weighted_ppo_loss_stats = weighted_ppo_loss_stats
        self.vf_clipfrac_stats = vf_clipfrac_stats
        self.ratio_stats = ratio_stats
        if self.compute_imgaug_bc_loss:
            self.imgaug_bc_loss_stats = imgaug_bc_loss_stats
            self.weighted_imgaug_bc_loss_stats = weighted_imgaug_bc_loss_stats

    def _get_rollout_data(self, obs_keys):
        device = self.accelerator.device

        all_obs_dict = {
            key: self.storage.query_key(key).transpose(0, 1).to(device) for key in obs_keys
        }
        actions = self.storage.actions.transpose(0, 1).to(device)
        logprobs = self.storage.actions_log_prob.transpose(0, 1).squeeze(-1).to(device)
        values = self.storage.values.transpose(0, 1).squeeze(-1).to(device)
        rewards = self.storage.rewards.transpose(0, 1).squeeze(-1).to(device)
        dones = self.storage.dones.transpose(0, 1).squeeze(-1).to(device)
        old_mu_batch = self.storage.action_mean.transpose(0, 1).to(device)
        old_sigma_batch = self.storage.action_sigma.transpose(0, 1).to(device)
        returns = self.storage.returns.transpose(0, 1).squeeze(-1).to(device)
        advantages = self.storage.advantages.transpose(0, 1).squeeze(-1).to(device)

        if self.use_padding_mask:
            padding_mask = dones.clone()
            padding_mask_p1 = padding_mask.clone()
            for i in range(padding_mask.shape[0]):
                true_indices = torch.where(padding_mask[i])[0]
                if len(true_indices) > 0:
                    padding_mask[i, true_indices[0]] = False
                    padding_mask_p1[
                        i, true_indices[0] : min(true_indices[0] + 2, padding_mask_p1.shape[1])
                    ] = False
            logprobs = torch.masked_fill(logprobs, padding_mask, INVALID_LOGPROB)
            values = torch.masked_fill(values, padding_mask_p1, 0)
        else:
            padding_mask = torch.zeros_like(dones)
            padding_mask_p1 = torch.zeros_like(dones)

        # CRITICAL FIX: For recurrent policies, split trajectories ONCE globally
        # This ensures CONSISTENT max_traj_len across all mini-batches and epochs
        # Without this, LSTM sees same data with different padding -> can't learn temporal patterns
        padded_obs_dict = None
        trajectory_masks = None
        if (hasattr(self.policy_model, "is_recurrent") and self.policy_model.is_recurrent) or (
            hasattr(self.value_model, "is_recurrent") and self.value_model.is_recurrent
        ):
            from gr00t.rl.trl.utils.rl import split_and_pad_trajectories

            padded_obs_dict = {}
            for key in obs_keys:
                # all_obs_dict[key]: [num_envs, num_steps, ...]
                # Transpose to [num_steps, num_envs, ...] for split_and_pad_trajectories
                obs_transposed = all_obs_dict[key].transpose(0, 1)
                dones_transposed = dones.transpose(0, 1)
                padded_obs, traj_masks = split_and_pad_trajectories(
                    obs_transposed, dones_transposed
                )
                # padded_obs: [max_traj_len, num_trajectories, ...]
                # Transpose to [num_trajectories, max_traj_len, ...]
                padded_obs_dict[key] = padded_obs.transpose(0, 1)
                if trajectory_masks is None:
                    # traj_masks: [max_traj_len, num_trajectories]
                    # Transpose to [num_trajectories, max_traj_len]
                    trajectory_masks = traj_masks.transpose(0, 1)

        return dict(
            all_obs_dict=all_obs_dict,
            actions=actions,
            logprobs=logprobs,
            values=values,
            rewards=rewards,
            dones=dones,
            old_mu_batch=old_mu_batch,
            old_sigma_batch=old_sigma_batch,
            returns=returns,
            advantages=advantages,
            padding_mask=padding_mask,
            padding_mask_p1=padding_mask_p1,
            padded_obs_dict=padded_obs_dict,  # Globally pre-split observations
            trajectory_masks=trajectory_masks,  # Globally pre-split masks
        )

    def _get_mb_rollout_data(self, rollout_data, micro_batch_inds):
        mb_advantage = rollout_data["advantages"][micro_batch_inds]
        mb_logprobs = rollout_data["logprobs"][micro_batch_inds]
        mb_return = rollout_data["returns"][micro_batch_inds]
        mb_values = rollout_data["values"][micro_batch_inds]
        mb_dones = rollout_data["dones"][micro_batch_inds]
        mb_actions = rollout_data["actions"][micro_batch_inds]
        mb_old_mu = rollout_data["old_mu_batch"][micro_batch_inds]
        mb_old_sigma = rollout_data["old_sigma_batch"][micro_batch_inds]
        mb_padding_mask = rollout_data["padding_mask"][micro_batch_inds]
        mb_padding_mask_p1 = rollout_data["padding_mask_p1"][micro_batch_inds]

        episode_attnmask = compute_episode_attnmask(mb_dones)

        # CRITICAL FIX: For recurrent policies, SLICE pre-split trajectories instead of re-splitting
        # This ensures consistent max_traj_len across all mini-batches and epochs
        mb_hidden_states = None
        if hasattr(self.policy_model, "is_recurrent") and self.policy_model.is_recurrent:
            if (
                rollout_data.get("padded_obs_dict") is None
                or rollout_data.get("trajectory_masks") is None
            ):
                raise RuntimeError(
                    "Recurrent policy requires padded_obs_dict and trajectory_masks in rollout_data! "
                    "This should have been created in _get_rollout_data."
                )

            # Calculate how many trajectories are in this mini-batch
            # A trajectory starts after each done (including implicit done at t=0)
            last_was_done = torch.zeros_like(mb_dones, dtype=torch.bool)
            last_was_done[:, 1:] = mb_dones[:, :-1].bool()
            last_was_done[:, 0] = True  # First timestep is always after an implicit done
            num_trajectories = torch.sum(last_was_done).item()

            # Slice from globally pre-split trajectories using trajectory counter
            first_traj = self._current_first_traj
            last_traj = first_traj + num_trajectories

            mb_obs_dict = {
                key: rollout_data["padded_obs_dict"][key][first_traj:last_traj]
                for key in rollout_data["padded_obs_dict"].keys()
            }
            mb_masks = rollout_data["trajectory_masks"][first_traj:last_traj]

            # Update trajectory counter for next mini-batch
            self._current_first_traj = last_traj

            # Extract hidden states for this mini-batch at trajectory boundaries
            # Following rsl_rl's approach: extract hidden states right after dones (start of trajectories)
            if (
                self.storage.saved_hidden_states_a is not None
                or self.storage.saved_hidden_states_c is not None
            ):
                # Determine which timesteps are right after dones (first step of each trajectory)
                # mb_dones: [batch_size, num_steps]
                dones_for_extraction = mb_dones.clone()  # [batch_size, num_steps]
                last_was_done = torch.zeros_like(dones_for_extraction, dtype=torch.bool)
                last_was_done[:, 1:] = dones_for_extraction[:, :-1].bool()
                last_was_done[:, 0] = True  # First timestep is always after an implicit "done"

                # Count trajectories in this mini-batch
                trajectories_in_batch = torch.sum(last_was_done)

                # Extract hidden states at trajectory boundaries
                # Storage shape: [num_steps, num_layers, num_envs, hidden_dim]
                # We need: [num_layers, num_trajectories, hidden_dim]

                # Get the environment indices for this mini-batch
                # micro_batch_inds are the environment indices: [batch_size]

                # Permute last_was_done to [num_steps, batch_size] for extraction
                last_was_done_transposed = last_was_done.transpose(0, 1)  # [num_steps, batch_size]

                # Extract actor hidden states
                if self.storage.saved_hidden_states_a is not None:
                    hid_a_batch = []
                    for saved_hidden_states in self.storage.saved_hidden_states_a:
                        # saved_hidden_states: [num_steps, num_layers, num_envs, hidden_dim]
                        # Select the environments in this mini-batch
                        saved_hid_mb = saved_hidden_states[
                            :, :, micro_batch_inds, :
                        ]  # [num_steps, num_layers, batch_size, hidden_dim]
                        # Permute to [batch_size, num_steps, num_layers, hidden_dim]
                        saved_hid_mb = saved_hid_mb.permute(
                            2, 0, 1, 3
                        )  # [batch_size, num_steps, num_layers, hidden_dim]
                        # Flatten to [batch_size * num_steps, num_layers, hidden_dim]
                        saved_hid_mb_flat = saved_hid_mb.reshape(
                            -1, saved_hid_mb.shape[2], saved_hid_mb.shape[3]
                        )
                        # Select only trajectory starts using last_was_done mask
                        last_was_done_flat = last_was_done.reshape(-1)
                        hid_at_traj_starts = saved_hid_mb_flat[
                            last_was_done_flat
                        ]  # [num_trajectories, num_layers, hidden_dim]
                        # Transpose to [num_layers, num_trajectories, hidden_dim]
                        hid_at_traj_starts = hid_at_traj_starts.transpose(1, 0).contiguous()
                        hid_a_batch.append(hid_at_traj_starts)

                    # Remove the tuple for GRU (single element list)
                    hid_a_batch = hid_a_batch[0] if len(hid_a_batch) == 1 else tuple(hid_a_batch)
                else:
                    hid_a_batch = None

                # Extract critic hidden states
                if self.storage.saved_hidden_states_c is not None:
                    hid_c_batch = []
                    for saved_hidden_states in self.storage.saved_hidden_states_c:
                        # saved_hidden_states: [num_steps, num_layers, num_envs, hidden_dim]
                        # Select the environments in this mini-batch
                        saved_hid_mb = saved_hidden_states[
                            :, :, micro_batch_inds, :
                        ]  # [num_steps, num_layers, batch_size, hidden_dim]
                        # Permute to [batch_size, num_steps, num_layers, hidden_dim]
                        saved_hid_mb = saved_hid_mb.permute(
                            2, 0, 1, 3
                        )  # [batch_size, num_steps, num_layers, hidden_dim]
                        # Flatten to [batch_size * num_steps, num_layers, hidden_dim]
                        saved_hid_mb_flat = saved_hid_mb.reshape(
                            -1, saved_hid_mb.shape[2], saved_hid_mb.shape[3]
                        )
                        # Select only trajectory starts using last_was_done mask
                        last_was_done_flat = last_was_done.reshape(-1)
                        hid_at_traj_starts = saved_hid_mb_flat[
                            last_was_done_flat
                        ]  # [num_trajectories, num_layers, hidden_dim]
                        # Transpose to [num_layers, num_trajectories, hidden_dim]
                        hid_at_traj_starts = hid_at_traj_starts.transpose(1, 0).contiguous()
                        hid_c_batch.append(hid_at_traj_starts)

                    # Remove the tuple for GRU (single element list)
                    hid_c_batch = hid_c_batch[0] if len(hid_c_batch) == 1 else tuple(hid_c_batch)
                else:
                    hid_c_batch = None

                mb_hidden_states = (hid_a_batch, hid_c_batch)
            else:
                mb_hidden_states = None
        else:
            # Non-recurrent: standard [batch_size, num_steps, ...] format
            mb_obs_dict = {
                key: rollout_data["all_obs_dict"][key][micro_batch_inds]
                for key in rollout_data["all_obs_dict"].keys()
            }
            mb_masks = None

        mb_rollout_data = dict(
            micro_batch_inds=micro_batch_inds,
            mb_obs_dict=mb_obs_dict,
            mb_advantage=mb_advantage,
            mb_logprobs=mb_logprobs,
            mb_return=mb_return,
            mb_values=mb_values,
            mb_dones=mb_dones,
            mb_actions=mb_actions,
            mb_old_mu=mb_old_mu,
            mb_old_sigma=mb_old_sigma,
            mb_padding_mask=mb_padding_mask,
            mb_padding_mask_p1=mb_padding_mask_p1,
            episode_attnmask=episode_attnmask,
            mb_masks=mb_masks,  # [num_trajectories, max_traj_len] for recurrent, None otherwise
            mb_hidden_states=mb_hidden_states,  # Hidden states for recurrent policies
        )
        return mb_rollout_data

    def _forward_model(self, model, mb_rollout_data):
        mb_obs_dict = mb_rollout_data["mb_obs_dict"]
        mb_actions = mb_rollout_data["mb_actions"]
        episode_attnmask = mb_rollout_data["episode_attnmask"]
        mb_masks = mb_rollout_data.get("mb_masks", None)  # Get masks for recurrent policies
        mb_dones = mb_rollout_data["mb_dones"]  # Original dones for unsplitting
        mb_hidden_states = mb_rollout_data.get(
            "mb_hidden_states", None
        )  # Hidden states for recurrent policies

        # Extract separate hidden states for actor and critic (like rsl_rl)
        actor_hidden_states = mb_hidden_states[0] if mb_hidden_states is not None else None
        critic_hidden_states = mb_hidden_states[1] if mb_hidden_states is not None else None

        # We should only do one forward pass for especially DDP model
        if self.compute_imgaug_bc_loss:
            results = model.forward(
                modes=["policy_w_and_wo_imgaug", "value"],
                input_kwargs=dict(
                    policy_w_and_wo_imgaug=dict(
                        obs_dict=mb_obs_dict,
                        actions=mb_actions,
                        episode_attnmask=episode_attnmask,
                        masks=mb_masks,
                        hidden_states=actor_hidden_states,
                        original_dones=mb_dones,
                    ),
                    value=dict(
                        obs_dict=mb_obs_dict,
                        episode_attnmask=episode_attnmask,
                        masks=mb_masks,
                        hidden_states=critic_hidden_states,
                        original_dones=mb_dones,
                    ),
                ),
            )
            policy_results = results["policy_w_and_wo_imgaug"]
        else:
            results = model.forward(
                modes=["policy", "value"],
                input_kwargs=dict(
                    policy=dict(
                        obs_dict=mb_obs_dict,
                        actions=mb_actions,
                        episode_attnmask=episode_attnmask,
                        masks=mb_masks,
                        hidden_states=actor_hidden_states,
                        original_dones=mb_dones,
                    ),
                    value=dict(
                        obs_dict=mb_obs_dict,
                        episode_attnmask=episode_attnmask,
                        masks=mb_masks,
                        hidden_states=critic_hidden_states,
                        original_dones=mb_dones,
                    ),
                ),
            )
            policy_results = results["policy"]

        return dict(
            policy_results=policy_results,
            value_results=results["value"],
        )

    def _compute_loss(self, forward_results, mb_rollout_data):
        ppo_loss_dict = self._compute_ppo_loss(forward_results, mb_rollout_data)

        loss = ppo_loss_dict["ppo_loss"] * self.config.get("ppo_loss_coef", 1.0)

        ret_dict = dict(
            ppo_loss_dict=ppo_loss_dict,
        )

        if self.compute_imgaug_bc_loss:
            imgaug_bc_loss_dict = self._compute_imgaug_bc_loss(forward_results, mb_rollout_data)
            loss += imgaug_bc_loss_dict["imgaug_bc_loss"] * self.config.imgaug_bc_loss_coef
            ret_dict["imgaug_bc_loss_dict"] = imgaug_bc_loss_dict

        ret_dict["loss"] = loss

        return ret_dict

    def _compute_ppo_loss(self, forward_results, mb_rollout_data):
        args = self.args
        optimizer = self.optimizer

        policy_results = forward_results["policy_results"]
        value_results = forward_results["value_results"]

        mb_old_mu = mb_rollout_data["mb_old_mu"]
        mb_old_sigma = mb_rollout_data["mb_old_sigma"]
        mb_values = mb_rollout_data["mb_values"]
        mb_return = mb_rollout_data["mb_return"]
        mb_logprobs = mb_rollout_data["mb_logprobs"]
        mb_advantage = mb_rollout_data["mb_advantage"]
        padding_mask = mb_rollout_data["mb_padding_mask"]
        padding_mask_p1 = mb_rollout_data["mb_padding_mask_p1"]
        micro_batch_inds = mb_rollout_data["micro_batch_inds"]

        new_logprobs = policy_results["logprobs"]
        sigma_batch = policy_results["action_std"]
        mu_batch = policy_results["action_mean"]
        entropy_batch = policy_results["entropy"]

        if not self.config.get("opt_homie", False):
            if mu_batch.shape[-1] > self.policy_model.num_actions:
                mu_batch = mu_batch[..., : self.policy_model.num_actions]
                sigma_batch = sigma_batch[..., : self.policy_model.num_actions]
            mb_old_mu = mb_old_mu[..., : self.policy_model.num_actions]
            mb_old_sigma = mb_old_sigma[..., : self.policy_model.num_actions]

        action_mask = policy_results.get(
            "action_mask",
            torch.ones(sigma_batch.shape[-1], dtype=torch.bool, device=sigma_batch.device),
        )
        if tuple(action_mask.shape) != (sigma_batch.shape[-1],):
            raise ValueError(
                "A2 PPO action mask must be one-dimensional and match the KL action width; "
                f"got {tuple(action_mask.shape)} for width {sigma_batch.shape[-1]}."
            )
        action_mask = action_mask.to(device=sigma_batch.device, dtype=torch.bool)

        with torch.no_grad():
            kl_per_dim = (
                torch.log(sigma_batch / mb_old_sigma + 1.0e-5)
                + (torch.square(mb_old_sigma) + torch.square(mb_old_mu - mu_batch))
                / (2.0 * torch.square(sigma_batch))
                - 0.5
            )
            kl = torch.sum(kl_per_dim * action_mask, dim=-1)
            local_kl_mean = torch.mean(kl)
            kl_mean = self.accelerator.gather(local_kl_mean).mean()
            self._adjust_learning_rate_based_on_kl(kl_mean, optimizer)

        # Forward a DDP model twice will cause the error: "one of the variables needed for gradient computation has been modified by an inplace operation"
        vpred = value_results.squeeze(-1)
        vpredclipped = torch.clamp(
            vpred,
            mb_values - args.cliprange_value,
            mb_values + args.cliprange_value,
        )
        vf_losses1 = torch.square(vpred - mb_return)
        vf_losses2 = torch.square(vpredclipped - mb_return)
        vf_loss_max = torch.max(vf_losses1, vf_losses2)
        vf_loss = masked_mean(vf_loss_max, ~padding_mask_p1)
        vf_clipfrac = masked_mean((vf_losses2 > vf_losses1).float(), ~padding_mask_p1)
        logprobs_diff = new_logprobs - mb_logprobs
        ratio = torch.exp(logprobs_diff)
        pg_losses = -mb_advantage * ratio
        pg_losses2 = -mb_advantage * torch.clamp(ratio, 1.0 - args.cliprange, 1.0 + args.cliprange)
        pg_loss_max = torch.max(pg_losses, pg_losses2)
        pg_loss = masked_mean(pg_loss_max, ~padding_mask)

        entropy_loss = -masked_mean(entropy_batch, ~padding_mask)

        loss = pg_loss + args.vf_coef * vf_loss + self.entropy_coef * entropy_loss

        return dict(
            ppo_loss=loss,
            # logging metrics
            local_kl_mean=local_kl_mean,
            pg_losses=pg_losses,
            pg_losses2=pg_losses2,
            pg_loss=pg_loss,
            vf_loss=vf_loss,
            entropy_loss=entropy_loss,
            ratio=ratio,
            vf_clipfrac=vf_clipfrac,
        )

    def _compute_imgaug_bc_loss(self, forward_results, mb_rollout_data):
        policy_results = forward_results["policy_results"]
        mu_batch = policy_results["action_mean"]

        action_mean_w_imgaug = policy_results["action_mean_w_imgaug"]
        imgaug_bc_loss = self.imgaug_bc_loss_fn(action_mean_w_imgaug, mu_batch.detach())

        return dict(
            imgaug_bc_loss=imgaug_bc_loss,
        )

    def _update_stats_buffer(
        self,
        ppo_epoch_idx,
        minibatch_idx,
        microbatch_idx,
        loss_dict,
        forward_results,
        mb_rollout_data,
    ):
        local_kl_mean = loss_dict["ppo_loss_dict"]["local_kl_mean"]
        pg_losses = loss_dict["ppo_loss_dict"]["pg_losses"]
        pg_losses2 = loss_dict["ppo_loss_dict"]["pg_losses2"]
        pg_loss = loss_dict["ppo_loss_dict"]["pg_loss"]
        vf_loss = loss_dict["ppo_loss_dict"]["vf_loss"]
        entropy_loss = loss_dict["ppo_loss_dict"]["entropy_loss"]
        weighted_ppo_loss = loss_dict["ppo_loss_dict"]["ppo_loss"] * self.config.get(
            "ppo_loss_coef", 1.0
        )
        ratio = loss_dict["ppo_loss_dict"]["ratio"]
        vf_clipfrac = loss_dict["ppo_loss_dict"]["vf_clipfrac"]

        padding_mask = mb_rollout_data["mb_padding_mask"]
        micro_batch_inds = mb_rollout_data["micro_batch_inds"]

        self.approxkl_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = local_kl_mean
        pg_clipfrac = masked_mean((pg_losses2 > pg_losses).float(), ~padding_mask)
        self.pg_clipfrac_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = pg_clipfrac
        self.pg_loss_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = pg_loss
        self.vf_loss_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = vf_loss
        if self.compute_imgaug_bc_loss:
            imgaug_bc_loss = loss_dict["imgaug_bc_loss_dict"]["imgaug_bc_loss"]
            self.imgaug_bc_loss_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = imgaug_bc_loss
            self.weighted_imgaug_bc_loss_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = (
                self.config.imgaug_bc_loss_coef * imgaug_bc_loss
            )
        self.entropy_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = -entropy_loss
        self.weighted_ppo_loss_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = (
            weighted_ppo_loss
        )
        self.vf_clipfrac_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = vf_clipfrac
        self.ratio_stats[ppo_epoch_idx, minibatch_idx, microbatch_idx] = ratio.mean()

    def _get_train_metrics(self):
        metrics = {}

        approxkl_avg = self.accelerator.gather_for_metrics(self.approxkl_stats).mean().item()

        metrics["policy/approxkl_avg"] = approxkl_avg
        metrics["policy/clipfrac_avg"] = (
            self.accelerator.gather_for_metrics(self.pg_clipfrac_stats).mean().item()
        )
        metrics["loss/policy_avg"] = (
            self.accelerator.gather_for_metrics(self.pg_loss_stats).mean().item()
        )
        if self.compute_imgaug_bc_loss:
            metrics["loss/imgaug_bc_avg"] = (
                self.accelerator.gather_for_metrics(self.imgaug_bc_loss_stats).mean().item()
            )
            metrics["loss/weighted_imgaug_bc_avg"] = (
                self.accelerator.gather_for_metrics(self.weighted_imgaug_bc_loss_stats)
                .mean()
                .item()
            )
        metrics["loss/value_avg"] = (
            self.accelerator.gather_for_metrics(self.vf_loss_stats).mean().item()
        )
        metrics["loss/entropy_avg"] = (
            self.accelerator.gather_for_metrics(self.entropy_stats).mean().item()
        )
        metrics["loss/weighted_ppo_loss_avg"] = (
            self.accelerator.gather_for_metrics(self.weighted_ppo_loss_stats).mean().item()
        )
        metrics["val/clipfrac_avg"] = (
            self.accelerator.gather_for_metrics(self.vf_clipfrac_stats).mean().item()
        )
        metrics["val/ratio"] = self.accelerator.gather_for_metrics(self.ratio_stats).mean().item()
        metrics["val/ratio_var"] = (
            self.accelerator.gather_for_metrics(self.ratio_stats).var().item()
        )
        metrics["objective/entropy"] = metrics["loss/entropy_avg"]

        return metrics

    def train(self):
        args = self.args
        accelerator = self.accelerator
        optimizer = self.optimizer
        model = self.model
        dataloader = self.dataloader
        device = accelerator.device

        def repeat_generator():
            while True:
                if dataloader is not None:
                    yield from dataloader
                else:
                    yield None

        iter_dataloader = iter(repeat_generator())

        accelerator.print("===training policy===")
        start_time = time.time()
        self._register_stats_buffer()
        model.train()

        # trainer state initialization
        self.state.max_steps = args.num_total_batches
        self.state.num_train_epochs = args.total_episodes / self.train_dataset_len
        if self._a2_v23_runtime_receipt_enabled:
            self._a2_v23_runtime_invocation_start_global_step = int(self.state.global_step)
            expected_start = (
                0 if self._a2_v23_runtime_receipt_config["mode"] == "RP0" else 10
            )
            if self._a2_v23_runtime_invocation_start_global_step != expected_start:
                raise RuntimeError(
                    "v23 P0.7 runtime invocation start global step mismatch: "
                    f"got {self._a2_v23_runtime_invocation_start_global_step}, "
                    f"expected {expected_start}."
                )
            if self._a2_v23_runtime_restored_start_global_step != expected_start:
                raise RuntimeError(
                    "v23 P0.7 runtime restored state global step mismatch: "
                    f"got {self._a2_v23_runtime_restored_start_global_step}, "
                    f"expected {expected_start}."
                )
        # Compute absolute values for logging, eval, and save if given as ratio
        if args.logging_steps is not None:
            if args.logging_steps < 1:
                self.state.logging_steps = math.ceil(self.state.max_steps * args.logging_steps)
            else:
                self.state.logging_steps = args.logging_steps
        if args.eval_steps is not None:
            if args.eval_steps < 1:
                self.state.eval_steps = math.ceil(self.state.max_steps * args.eval_steps)
            else:
                self.state.eval_steps = args.eval_steps
        if args.save_steps is not None:
            if args.save_steps < 1:
                self.state.save_steps = math.ceil(self.state.max_steps * args.save_steps)
            else:
                self.state.save_steps = args.save_steps
        self.control = self.callback_handler.on_train_begin(args, self.state, self.control)

        # backward compatibility
        if self.is_deepspeed_enabled:
            self.deepspeed = self.model
            self.model_wrapped = self.model

        # env
        obs_dict = self.env.reset_all()
        if self.config.get("init_at_random_ep_len", False):
            self.env.episode_length_buf = torch.randint_like(
                self.env.episode_length_buf, high=int(self.env.max_episode_length)
            )
            from gr00t.rl.envs.base_task.staged_task_base import StagedTaskBase

            if isinstance(self.env, StagedTaskBase):
                self.env.time_in_stage_buf[:] = torch.randint_like(
                    self.env.time_in_stage_buf, high=int(self.env.max_stage_time[0])
                )
                self.env.actual_time_in_stage_buf[:] = self.env.time_in_stage_buf
        for obs_key in obs_dict.keys():
            obs_dict[obs_key] = obs_dict[obs_key].to(device)

        for batch_idx in range(1, args.num_total_batches + 1):
            batch_start_time = time.time()
            self.state.episode += 1 * args.batch_size
            data = next(iter_dataloader)
            # update scheduled params
            if self.schedule_dict is not None:
                self.scheduled_params_dict = update_scheduled_params(
                    self, self.schedule_dict, self.state.global_step
                )

            reinit_sim_freq = self.env.config.get("reinit_sim_freq", 0)
            if reinit_sim_freq > 0 and (self.state.global_step + 1) % reinit_sim_freq == 0:
                self.env.reinit_sim()
                obs_dict = self.env.reset_all()
                for obs_key in obs_dict.keys():
                    obs_dict[obs_key] = obs_dict[obs_key].to(device)

            # DEBUG: Print model type and distributed configuration (every 5 batches to reduce clutter)
            if batch_idx == 0:
                # Check if model is wrapped in DDP
                model_type = type(self.model).__name__
                if self.accelerator.process_index == 0:
                    print(f"\n{'='*80}")
                    print(f"[CRITICAL] Model type: {model_type}")
                    print(f"[CRITICAL] Num processes: {self.accelerator.num_processes}")
                    print(f"[CRITICAL] Distributed type: {self.accelerator.distributed_type}")
                    print(f"[CRITICAL] Use distributed: {self.accelerator.use_distributed}")
                    print("  >> Model should be DistributedDataParallel if multi-GPU!")
                    print(f"{'='*80}\n")

            with torch.no_grad():
                with unwrap_model_for_generation(
                    self.model,
                    self.accelerator,
                    gather_deepspeed3_params=self.args.ds3_gather_for_generation,
                ) as model:
                    obs_dict = self._rollout_step(model, obs_dict)
                end_collection_time = time.time()
                collection_time = end_collection_time - batch_start_time

                rollout_data = self._get_rollout_data(obs_keys=obs_dict.keys())
                torch.cuda.empty_cache()
                gc.collect()

            model = self.model
            self._train_mode()
            for ppo_epoch_idx in range(args.num_ppo_epochs):
                # CRITICAL FIX: Reset trajectory counter at start of each epoch
                # Without this, trajectory indexing breaks in epoch 2+
                self._current_first_traj = 0

                minibatch_idx = 0
                if self.ppo_shuffle_every_epoch or ppo_epoch_idx == 0:
                    # CRITICAL FIX: Disable shuffling for recurrent policies
                    # Trajectory slicing requires contiguous environment indices
                    # Shuffling breaks the env->trajectory mapping
                    policy_model = self.accelerator.unwrap_model(model).policy
                    if hasattr(policy_model, "is_recurrent") and policy_model.is_recurrent:
                        b_inds = torch.arange(args.local_batch_size, device=device)
                    else:
                        b_inds = torch.randperm(args.local_batch_size, device=device)
                for mini_batch_start in range(0, args.local_batch_size, args.local_mini_batch_size):
                    mini_batch_end = mini_batch_start + args.local_mini_batch_size
                    mini_batch_inds = b_inds[mini_batch_start:mini_batch_end]
                    microbatch_idx = 0
                    for micro_batch_start in range(
                        0, args.local_mini_batch_size, args.per_device_train_batch_size
                    ):
                        with accelerator.accumulate(model):
                            micro_batch_end = micro_batch_start + args.per_device_train_batch_size
                            micro_batch_inds = mini_batch_inds[micro_batch_start:micro_batch_end]

                            mb_rollout_data = self._get_mb_rollout_data(
                                rollout_data, micro_batch_inds
                            )

                            forward_results = self._forward_model(model, mb_rollout_data)

                            loss_dict = self._compute_loss(forward_results, mb_rollout_data)

                            accelerator.backward(loss_dict["loss"])
                            self._gradient_clipping()
                            optimizer.step()
                            optimizer.zero_grad()
                            with torch.no_grad():
                                self._update_stats_buffer(
                                    ppo_epoch_idx,
                                    minibatch_idx,
                                    microbatch_idx,
                                    loss_dict,
                                    forward_results,
                                    mb_rollout_data,
                                )
                            del loss_dict, forward_results, mb_rollout_data
                            microbatch_idx += 1
                    minibatch_idx += 1
                    # del everything and empty cache
                    # fmt: off
                if (
                    self.empty_cache_every_n_ppo_epoch > 0
                    and ppo_epoch_idx % self.empty_cache_every_n_ppo_epoch == 0
                ):
                    print(f"Empty cache at ppo_epoch_idx {ppo_epoch_idx}")
                    torch.cuda.empty_cache()
                    gc.collect()

            with torch.no_grad():
                learn_time = time.time() - end_collection_time
                eps = int(self.state.episode / (time.time() - start_time))

                metrics = {}
                train_metrics = self._get_train_metrics()
                metrics.update(train_metrics)
                metrics["eps"] = eps
                metrics["objective/rewards"] = (
                    self.accelerator.gather_for_metrics(
                        torch.tensor(np.mean(self.state.rewbuffer)).to(device)
                    )
                    .mean()
                    .item()
                )
                metrics["objective/length"] = (
                    self.accelerator.gather_for_metrics(
                        torch.tensor(np.mean(self.state.lenbuffer)).to(device)
                    )
                    .mean()
                    .item()
                )
                metrics["lr"] = self.lr_scheduler.get_last_lr()[0]
                metrics["episode"] = self.state.episode
                env_log_dict_local = self.episode_env_tensors.mean_and_clear()
                env_log_dict_local = _finalize_a2_conditional_ratios(env_log_dict_local)
                # Synchronize every environment metric across ranks before logging.
                env_log_dict = {
                    k: (
                        self.accelerator.gather_for_metrics(
                            torch.tensor(v, dtype=torch.float32).to(device)
                        )
                        .mean()
                        .item()
                        if not isinstance(v, (int, float))
                        else self.accelerator.gather_for_metrics(
                            torch.tensor(v, dtype=torch.float32).to(device)
                        )
                        .mean()
                        .item()
                    )
                    for k, v in env_log_dict_local.items()
                }

                ep_infos = process_ep_infos(self.ep_infos, device)
                self.state.tot_timesteps += (
                    self.num_steps_per_env * self.env.num_envs * accelerator.num_processes
                )
                self.state.tot_time += collection_time + learn_time
                log_dict = {
                    "collection_time": collection_time,
                    "learn_time": learn_time,
                    "tot_timesteps": self.state.tot_timesteps,
                    "tot_time": self.state.tot_time,
                    "it": self.state.global_step,
                    "fps": int(
                        self.num_steps_per_env
                        * self.env.num_envs
                        * accelerator.num_processes
                        / (collection_time + learn_time)
                    ),
                    "experiment_save_dir": self.args.output_dir,
                    "batch_idx": batch_idx,
                    "num_total_batches": args.num_total_batches,
                }

                for key, value in ep_infos.items():
                    log_dict[f"Episode/{key}"] = value

                # Add scheduled parameters to metrics
                for param_name, param_value in self.scheduled_params_dict.items():
                    log_dict[f"scheduled_params/{param_name}"] = param_value

                if hasattr(self.policy_model, "std"):
                    metrics["Policy/mean_noise_std"] = self.policy_model.std.mean().item()
                else:
                    metrics["Policy/mean_noise_std"] = 0.0

                metrics.update({f"Env/{k}": v for k, v in env_log_dict.items()})
                metrics.update(log_dict)

                self.state.epoch = self.state.episode / self.train_dataset_len  # used by self.log
                self.state.global_step += 1

                self.log(metrics)
                self._write_r2_training_metric_if_enabled(metrics, batch_idx)
                self.ep_infos.clear()

            self.lr_scheduler.step()

            self.control = self.callback_handler.on_step_end(args, self.state, self.control)

            if self._a2_v23_runtime_receipt_enabled and batch_idx == args.num_total_batches:
                self._a2_v23_runtime_terminal_batch_completed = True
                self._a2_v23_runtime_invocation_end_global_step = int(self.state.global_step)

            del (
                metrics,
                rollout_data,
            )
            torch.cuda.empty_cache()
            gc.collect()

            if self.control.should_training_stop:
                break

        if self._a2_v23_runtime_receipt_enabled and self._a2_v23_runtime_terminal_batch_completed:
            self._write_a2_v23_runtime_receipt()

        if self.control.should_training_stop:
            return

        # HF trainer specifics
        self.control = self.callback_handler.on_train_end(args, self.state, self.control)
        if self.control.should_save:
            self._save_checkpoint(model, trial=None, metrics=None)
            self.control = self.callback_handler.on_save(self.args, self.state, self.control)

        if wandb_run_exists():
            wandb.finish()

    def _eval_mode(self):
        self.model.eval()
        model = self.accelerator.unwrap_model(self.model)
        model.set_mode("eval")
        model.transform_eval()
        self.env.set_is_evaluating(is_evaluating=True, log_info=False)

    def _train_rollout_mode(self):
        self.model.eval()
        model = self.accelerator.unwrap_model(self.model)
        model.set_mode("train_rollout")
        model.transform_eval()
        if self.train_with_evaluating_env:
            self.env.set_is_evaluating(True, log_info=False)
        else:
            self.env.set_is_evaluating(False, log_info=False)

    def _train_mode(self):
        self.model.train()
        model = self.accelerator.unwrap_model(self.model)
        model.set_mode("train")
        model.transform_train()
        if self.train_with_evaluating_env:
            self.env.set_is_evaluating(True, log_info=False)
        else:
            self.env.set_is_evaluating(False, log_info=False)

    def log(self, logs: Dict[str, float], start_time: Optional[float] = None) -> None:
        """
        Log `logs` on the various objects watching training.

        Subclass and override this method to inject custom behavior.

        Args:
            logs (`Dict[str, float]`):
                The values to log.
            start_time (`Optional[float]`):
                The start of training.
        """
        if self.state.epoch is not None:
            logs["epoch"] = self.state.epoch
        if self.args.include_num_input_tokens_seen:
            logs["num_input_tokens_seen"] = self.state.num_input_tokens_seen
            if start_time is not None:
                speed_metrics("train", start_time, num_tokens=self.state.num_input_tokens_seen)

        output = {**logs, **{"step": self.state.global_step}}
        self.state.log_history.append(output)

        self.control = self.callback_handler.on_log(self.args, self.state, self.control, logs)

    def _gradient_clipping(self):
        # Gradient clipping
        args = self.args
        model = self.model
        if args.max_grad_norm is not None and args.max_grad_norm > 0:
            # deepspeed does its own clipping

            if is_sagemaker_mp_enabled() and args.fp16:
                _grad_norm = self.optimizer.clip_master_grads(args.max_grad_norm)
            elif self.use_apex:
                # Revert to normal clipping otherwise, handling Apex or full precision
                _grad_norm = nn.utils.clip_grad_norm_(
                    amp.master_params(self.optimizer),
                    args.max_grad_norm,
                )
            else:
                _grad_norm = self.accelerator.clip_grad_norm_(
                    model.parameters(),
                    args.max_grad_norm,
                )

            if (
                is_accelerate_available()
                and self.accelerator.distributed_type == DistributedType.DEEPSPEED
            ):
                grad_norm = model.get_global_grad_norm()
                # In some cases the grad norm may not return a float
                if hasattr(grad_norm, "item"):
                    grad_norm = grad_norm.item()
            else:
                grad_norm = _grad_norm

        return grad_norm

    def _compute_returns(self, values, last_values, policy_state_dict):
        """Compute the returns and advantages for the given policy state.
        This function calculates the returns and advantages for each step in the
        environment based on the provided observations and policy state. It uses
        Generalized Advantage Estimation (GAE) to compute the advantages, which
        helps in reducing the variance of the policy gradient estimates.
        Args:
            values (torch.Tensor): The values for each step.
            last_values (torch.Tensor): The last values for the last step.
            policy_state_dict (dict): A dictionary containing the policy state
                          information, including 'values', 'dones',
                          and 'rewards'.
        Returns:
            tuple: A tuple containing:
            - returns (torch.Tensor): The computed returns for each step.
            - advantages (torch.Tensor): The normalized advantages for each step.
        """
        device = self.accelerator.device
        advantage = 0

        dones = policy_state_dict["dones"]
        rewards = policy_state_dict["rewards"]

        dones = dones.to(device)
        rewards = rewards.to(device)

        returns = torch.zeros_like(values)

        num_steps = returns.shape[0]

        for step in reversed(range(num_steps)):
            if step == num_steps - 1:
                next_values = last_values
            else:
                next_values = values[step + 1]
            next_is_not_terminal = 1.0 - dones[step].float()
            delta = rewards[step] + next_is_not_terminal * self.gamma * next_values - values[step]
            advantage = delta + next_is_not_terminal * self.gamma * self.lam * advantage
            returns[step] = advantage + values[step]

        # Compute and normalize the advantages
        advantages = returns - values
        if self.sync_advantage_normalization:
            # gather advantages from all processes before normalization
            advantages = self.accelerator.gather(advantages)
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
            # ungather advantages
            advantages = advantages.reshape(
                self.accelerator.num_processes, -1, *advantages.shape[1:]
            )[self.accelerator.process_index].to(device)
        else:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        return returns, advantages

    def _adjust_learning_rate_based_on_kl(self, kl_mean, optimizer):
        """Adjust the learning rate based on the KL divergence.

        This function implements a learning rate schedule that adjusts the learning rate
        based on the KL divergence between the current policy and the old policy.
        If the KL divergence is too high, the learning rate is decreased.
        If the KL divergence is too low, the learning rate is increased.

        Args:
            kl_mean (float): The mean KL divergence across all processes.
            optimizer (torch.optim.Optimizer): The optimizer to update.
        """
        if self.desired_kl is None:
            return

        if kl_mean > self.desired_kl * 2.0:
            new_lr = max(1e-5, self.args.learning_rate / 1.5)
        elif kl_mean < self.desired_kl / 2.0 and kl_mean > 0.0:
            new_lr = min(1e-2, self.args.learning_rate * 1.5)
        else:
            new_lr = self.args.learning_rate
        self.args.learning_rate = new_lr

        for param_group in optimizer.param_groups:
            param_group["lr"] = self.args.learning_rate

    def _require_a2_v23_full_checkpoint_path(self, checkpoint_path) -> None:
        config = self._a2_v23_runtime_receipt_config
        if config is None or config["mode"] != "FULL":
            return
        expected_raw = config.get("expected_initial_step10_checkpoint_path")
        if not isinstance(expected_raw, str) or not expected_raw:
            raise RuntimeError(
                "v23 P0.7 FULL restore has no canonical expected RP0 step10 checkpoint path."
            )
        expected_path = Path(expected_raw).expanduser().resolve()
        actual_path = Path(str(checkpoint_path)).expanduser()
        if actual_path.is_symlink() or not actual_path.is_file():
            raise RuntimeError(
                "v23 P0.7 FULL restore input checkpoint must be an existing regular file: "
                f"{actual_path}"
            )
        actual_path = actual_path.resolve()
        if actual_path != expected_path:
            raise RuntimeError(
                "v23 P0.7 FULL restore input checkpoint does not exactly match the expected RP0 step10 path: "
                f"actual={actual_path}, expected={expected_path}."
            )
        if actual_path.name != "model_step_000010.pt":
            raise RuntimeError(
                "v23 P0.7 FULL restore input checkpoint must name model_step_000010.pt; "
                f"got {actual_path.name!r}."
            )

    def _require_a2_v23_full_trainer_state(self, state) -> dict[str, object]:
        """Validate the complete persisted state schema before applying a FULL restore."""

        if not hasattr(state, "__dict__"):
            raise RuntimeError("v23 P0.7 FULL checkpoint state is not a trainer state object.")
        state_dict = vars(state)
        missing = [
            key for key in _A2_V23_FULL_REQUIRED_TRAINER_STATE_FIELDS if key not in state_dict
        ]
        if missing:
            raise RuntimeError(
                "v23 P0.7 FULL checkpoint trainer state is missing required fields: "
                f"{missing}."
            )

        def require_int(key: str) -> None:
            value = state_dict[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must be an integer; "
                    f"got {value!r}."
                )

        def require_number(key: str) -> None:
            value = state_dict[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must be numeric; "
                    f"got {value!r}."
                )
            if not math.isfinite(float(value)):
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must be finite."
                )

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
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must be an integer or null."
                )
        if state_dict["best_metric"] is not None:
            require_number("best_metric")
        for key in ("best_model_checkpoint", "trial_name"):
            value = state_dict[key]
            if value is not None and not isinstance(value, str):
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must be a string or null."
                )
        if state_dict["trial_params"] is not None and not isinstance(state_dict["trial_params"], Mapping):
            raise RuntimeError(
                "v23 P0.7 FULL checkpoint trainer state field 'trial_params' must be a mapping or null."
            )
        for key in ("is_local_process_zero", "is_world_process_zero", "is_hyper_param_search"):
            if not isinstance(state_dict[key], bool):
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must be bool."
                )
        if not isinstance(state_dict["stateful_callbacks"], Mapping):
            raise RuntimeError(
                "v23 P0.7 FULL checkpoint trainer state field 'stateful_callbacks' must be a mapping."
            )
        for key in ("rewbuffer", "lenbuffer"):
            if not isinstance(state_dict[key], deque):
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must be a deque."
                )
            for index, member in enumerate(state_dict[key]):
                if isinstance(member, bool) or not isinstance(member, Real):
                    raise RuntimeError(
                        f"v23 P0.7 FULL checkpoint trainer state field {key!r}[{index}] "
                        f"must be a real numeric value; got {member!r}."
                    )
                if not math.isfinite(float(member)):
                    raise RuntimeError(
                        f"v23 P0.7 FULL checkpoint trainer state field {key!r}[{index}] "
                        "must be finite."
                    )
        for key in _A2_V23_FULL_ENV_RESET_STATE_FIELDS:
            value = state_dict[key]
            if not isinstance(value, torch.Tensor) or value.ndim != 1:
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must be a one-dimensional tensor."
                )
            if value.shape[0] != int(self.env.num_envs):
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} must have one value per environment; "
                    f"got shape={tuple(value.shape)}, envs={self.env.num_envs}."
                )
            if not torch.isfinite(value).all().item():
                raise RuntimeError(
                    f"v23 P0.7 FULL checkpoint trainer state field {key!r} contains non-finite values."
                )
        return state_dict

    def _require_a2_v23_full_checkpoint_components(self, checkpoint, checkpoint_path=None):
        """Preflight every component needed by the opt-in FULL restore contract."""

        if self._a2_v23_runtime_receipt_config is None or self._a2_v23_runtime_receipt_config["mode"] != "FULL":
            return None
        if checkpoint_path is not None:
            self._require_a2_v23_full_checkpoint_path(checkpoint_path)
        if self.checkpoint_load_mode != "full":
            raise RuntimeError("v23 P0.7 FULL receipt requires checkpoint_load_mode='full'.")
        input_path = Path(checkpoint_path or self.checkpoint_path)
        if input_path.name != "model_step_000010.pt":
            raise RuntimeError(
                "v23 P0.7 FULL receipt requires the explicit step10 input checkpoint; "
                f"got {str(input_path)!r}."
            )
        if not isinstance(checkpoint, Mapping):
            raise RuntimeError("v23 P0.7 FULL checkpoint must be a mapping.")
        actor_keys = [key for key in ("actor_model_state_dict", "policy_state_dict") if key in checkpoint]
        required = ("value_state_dict", "optimizer_state_dict", "lr_scheduler_state_dict", "state")
        if len(actor_keys) != 1 or any(key not in checkpoint for key in required):
            missing = [key for key in required if key not in checkpoint]
            if not actor_keys:
                missing.append("policy_state_dict|actor_model_state_dict")
            raise RuntimeError(
                "v23 P0.7 FULL checkpoint is missing required restore components: "
                f"{missing}."
            )
        if checkpoint[actor_keys[0]] is None:
            raise RuntimeError("v23 P0.7 FULL checkpoint actor state is null.")
        if checkpoint["value_state_dict"] is None:
            raise RuntimeError("v23 P0.7 FULL checkpoint value_state_dict is null.")
        if checkpoint["optimizer_state_dict"] is None:
            raise RuntimeError("v23 P0.7 FULL checkpoint optimizer_state_dict is null.")
        if checkpoint["lr_scheduler_state_dict"] is None:
            raise RuntimeError("v23 P0.7 FULL checkpoint lr_scheduler_state_dict is null.")
        state = checkpoint["state"]
        state_dict = self._require_a2_v23_full_trainer_state(state)
        restored_step = state_dict.get("global_step")
        if isinstance(restored_step, bool) or not isinstance(restored_step, int) or restored_step != 10:
            raise RuntimeError(
                "v23 P0.7 FULL checkpoint trainer state must restore global_step=10; "
                f"got {restored_step!r}."
            )
        if self.value_model is None or self.optimizer is None or self.lr_scheduler is None:
            raise RuntimeError(
                "v23 P0.7 FULL receipt requires instantiated value, optimizer, and scheduler components."
            )
        return state_dict

    def _require_a2_v23_full_restore_facts(self) -> None:
        config = self._a2_v23_runtime_receipt_config
        if config is None or config["mode"] != "FULL":
            return
        facts = self._a2_v23_runtime_load_facts
        required = ("actor", "value", "optimizer", "scheduler", "trainer")
        if facts.get("load_mode") != "full" or any(not facts[key].get("loaded") for key in required):
            raise RuntimeError(
                "v23 P0.7 FULL restore did not load actor/value/optimizer/scheduler/trainer state completely."
            )
        if not facts["actor"].get("strict") or not facts["value"].get("strict"):
            raise RuntimeError("v23 P0.7 FULL restore actor/value loads were not strict.")
        if facts["trainer"].get("required_fields") != list(
            _A2_V23_FULL_REQUIRED_TRAINER_STATE_FIELDS
        ):
            raise RuntimeError(
                "v23 P0.7 FULL restore trainer state did not restore the complete required field set."
            )
        if facts["trainer"].get("global_step") != 10 or self.state.global_step != 10:
            raise RuntimeError("v23 P0.7 FULL restore did not leave trainer global_step=10.")

    def _apply_v23_warm_head_reset(self, policy):
        """Reset only the raw pitch/roll rows of the warm policy output head."""

        if self.workflow_config is None:
            return None
        initialization = self.workflow_config.get("v23_initialization")
        if initialization != "warm_head_reset":
            return None
        if self.checkpoint_load_mode != "policy_only":
            raise RuntimeError(
                "v23 warm_head_reset requires checkpoint_load_mode='policy_only'."
            )
        if isinstance(self.local_seed, bool) or not isinstance(self.local_seed, int):
            raise RuntimeError(
                "v23 warm_head_reset requires an integer local_seed for its local generator."
            )

        required_keys = (
            "actor_module.module.6.weight",
            "actor_module.module.6.bias",
            "std",
        )
        parameters = dict(policy.named_parameters())
        missing = [key for key in required_keys if key not in parameters]
        if missing:
            raise RuntimeError(
                "v23 warm_head_reset policy is missing exact required parameters: "
                f"{missing}."
            )
        expected_shapes = {
            "actor_module.module.6.weight": (12, 128),
            "actor_module.module.6.bias": (12,),
            "std": (12,),
        }
        for key, expected_shape in expected_shapes.items():
            parameter = parameters[key]
            if tuple(parameter.shape) != expected_shape:
                raise RuntimeError(
                    "v23 warm_head_reset parameter shape mismatch for "
                    f"{key!r}: got {tuple(parameter.shape)}, expected {expected_shape}."
                )

        weight = parameters["actor_module.module.6.weight"]
        bias = parameters["actor_module.module.6.bias"]
        std = parameters["std"]
        generator = torch.Generator(device=weight.device)
        generator.manual_seed(self.local_seed)
        with torch.no_grad():
            torch.nn.init.kaiming_uniform_(
                weight[3:5], a=math.sqrt(5), generator=generator
            )
            bound = 1.0 / math.sqrt(128)
            torch.nn.init.uniform_(bias[3:5], -bound, bound, generator=generator)
            std[3:5].fill_(0.8)
        return {
            "applied": True,
            "initialization": initialization,
            "weight_key": "actor_module.module.6.weight",
            "bias_key": "actor_module.module.6.bias",
            "std_key": "std",
            "row_slice": [3, 5],
            "std_value": 0.8,
            "local_seed": self.local_seed,
        }

    def load_policy_checkpoint(self, checkpoint_path):
        """Strictly load only the actor policy weights from a checkpoint."""
        print(f"Loading policy-only checkpoint from {checkpoint_path}")
        checkpoint = torch.load(
            checkpoint_path, map_location="cpu", weights_only=False
        )
        actor_keys = (
            "policy_state_dict",
            "actor_model_state_dict",
        )
        present_actor_keys = [key for key in actor_keys if key in checkpoint]
        if len(present_actor_keys) != 1:
            raise RuntimeError(
                "Policy-only checkpoint must contain exactly one actor state key from "
                f"{actor_keys}; found {present_actor_keys}."
            )

        model = self.accelerator.unwrap_model(self.model)
        actor_key = present_actor_keys[0]
        load_result = model.policy.load_state_dict(checkpoint[actor_key], strict=True)
        warm_head_reset = self._apply_v23_warm_head_reset(model.policy)
        self._a2_v23_runtime_load_facts["actor"] = {
            "loaded": True,
            "state_key": actor_key,
            "strict": True,
            "missing_keys": list(load_result.missing_keys),
            "unexpected_keys": list(load_result.unexpected_keys),
        }
        if warm_head_reset is not None:
            self._a2_v23_runtime_load_facts["actor"]["warm_head_reset"] = warm_head_reset
        self._a2_v23_runtime_load_facts["load_mode"] = "policy_only"
        self._a2_v23_runtime_restored_start_global_step = int(self.state.global_step)
        print(f"Loaded policy-only checkpoint actor from key {actor_key!r}")

    def load_checkpoint(self, checkpoint_path):
        """Load a checkpoint to restore the state of model, optimizer, trainer etc.

        Args:
            checkpoint_path (str): Path to the checkpoint file
        """
        print(f"Loading checkpoint from {checkpoint_path}")
        self._require_a2_v23_full_checkpoint_path(checkpoint_path)
        checkpoint = torch.load(
            checkpoint_path, map_location=self.accelerator.device, weights_only=False
        )
        required_state = self._require_a2_v23_full_checkpoint_components(
            checkpoint, checkpoint_path
        )

        # Load model state
        model = self.accelerator.unwrap_model(self.model)
        if "actor_model_state_dict" in checkpoint:
            actor_key = "actor_model_state_dict"
            actor_result = model.policy.load_state_dict(checkpoint[actor_key], strict=True)
            self._a2_v23_runtime_load_facts["actor"] = {
                "loaded": True,
                "state_key": actor_key,
                "strict": True,
                "missing_keys": list(actor_result.missing_keys),
                "unexpected_keys": list(actor_result.unexpected_keys),
            }
        elif "policy_state_dict" in checkpoint:
            actor_key = "policy_state_dict"
            actor_result = model.policy.load_state_dict(checkpoint[actor_key], strict=True)
            self._a2_v23_runtime_load_facts["actor"] = {
                "loaded": True,
                "state_key": actor_key,
                "strict": True,
                "missing_keys": list(actor_result.missing_keys),
                "unexpected_keys": list(actor_result.unexpected_keys),
            }
        if "value_state_dict" in checkpoint and model.value_model is not None:
            if checkpoint["value_state_dict"] is None:
                raise RuntimeError("Full checkpoint contains a null value_state_dict.")
            value_result = model.value_model.load_state_dict(
                checkpoint["value_state_dict"], strict=True
            )
            self._a2_v23_runtime_load_facts["value"] = {
                "loaded": True,
                "state_key": "value_state_dict",
                "strict": True,
                "missing_keys": list(value_result.missing_keys),
                "unexpected_keys": list(value_result.unexpected_keys),
            }
        if "homie_state_dict" in checkpoint and model.homie_model is not None:
            model.homie_model.load_state_dict(checkpoint["homie_state_dict"])
        # Load optimizer state
        if "optimizer_state_dict" in checkpoint and checkpoint["optimizer_state_dict"] is not None:
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            self._a2_v23_runtime_load_facts["optimizer"] = {
                "loaded": True,
                "state_key": "optimizer_state_dict",
            }

            # Update learning rate if available
            if "args" in checkpoint and hasattr(checkpoint["args"], "learning_rate"):
                self.args.learning_rate = checkpoint["args"].learning_rate
                for param_group in self.optimizer.param_groups:
                    param_group["lr"] = self.args.learning_rate

        # Load learning rate scheduler state
        if (
            "lr_scheduler_state_dict" in checkpoint
            and checkpoint["lr_scheduler_state_dict"] is not None
        ):
            self.lr_scheduler.load_state_dict(checkpoint["lr_scheduler_state_dict"])
            self._a2_v23_runtime_load_facts["scheduler"] = {
                "loaded": True,
                "state_key": "lr_scheduler_state_dict",
            }

        if "env_state_dict" in checkpoint:
            self.env.load_env_state_dict(checkpoint["env_state_dict"])
            self._a2_v23_runtime_load_facts["environment"] = {
                "loaded": True,
                "state_key": "env_state_dict",
            }

        if "state" in checkpoint:
            if required_state is not None:
                for key in _A2_V23_FULL_REQUIRED_TRAINER_STATE_FIELDS:
                    if key not in _A2_V23_FULL_ENV_RESET_STATE_FIELDS:
                        setattr(self.state, key, required_state[key])
                self._a2_v23_runtime_load_facts["trainer"] = {
                    "loaded": True,
                    "state_key": "state",
                    "global_step": int(self.state.global_step),
                    "required_fields": list(_A2_V23_FULL_REQUIRED_TRAINER_STATE_FIELDS),
                }
            else:
                # Preserve the repository's generic full-resume semantics for
                # every non-v23 runtime: copy its persisted state exactly as
                # the pre-v23 loader did, including unknown future fields.
                for key, value in checkpoint["state"].__dict__.items():
                    if key in ["cur_reward_sum", "cur_episode_length"]:
                        continue
                    if key not in [
                        "stateful_callbacks",
                        "is_local_process_zero",
                        "is_world_process_zero",
                        "log_history",
                    ]:
                        setattr(self.state, key, value)

        self._a2_v23_runtime_load_facts["load_mode"] = "full"
        self._a2_v23_runtime_restored_start_global_step = int(self.state.global_step)
        self._require_a2_v23_full_restore_facts()
        print(f"Loaded checkpoint from step {self.state.global_step}")
        return checkpoint

    def eval(self):
        self._eval_mode()
        self.env.set_is_evaluating()
        self.policy_model.eval_mode()
        self.policy_model.init_rollout()
        obs_dict = self.env.reset_all()
        for obs_key in obs_dict.keys():
            obs_dict[obs_key] = obs_dict[obs_key].to(self.accelerator.device)

        eval_num_envs_episodes = self.config.get("eval", {}).get("eval_num_envs_episodes", False)
        dump_eval_to_log_metrics = self.config.get("eval", {}).get(
            "dump_to_log_metrics", False
        )
        a2_v23_p0_runtime_export = self.config.get("eval", {}).get(
            "a2_v23_p0_runtime_export", False
        )
        if not isinstance(a2_v23_p0_runtime_export, bool):
            raise RuntimeError(
                "eval.a2_v23_p0_runtime_export must be bool; "
                f"got {a2_v23_p0_runtime_export!r}."
            )
        a2_v23_p05_runtime_export = self.config.get("eval", {}).get(
            "a2_v23_p05_runtime_export", False
        )
        if not isinstance(a2_v23_p05_runtime_export, bool):
            raise RuntimeError(
                "eval.a2_v23_p05_runtime_export must be bool; "
                f"got {a2_v23_p05_runtime_export!r}."
            )
        a2_v23_stationary_rent = _read_a2_v23_stationary_rent_config(
            self.config.get("eval", {})
        )
        a2_v23_p08_state_bank = _read_a2_v23_p08_state_bank_config(
            self.config.get("eval", {}),
            env=self.env,
            checkpoint_load_mode=self.checkpoint_load_mode,
            checkpoint_path=self.checkpoint_path,
            seed=int(self.args.seed),
            process_count=self.accelerator.num_processes,
        )
        if a2_v23_p08_state_bank["enabled"] and a2_v23_stationary_rent["enabled"]:
            raise RuntimeError(
                "P0.8 state-bank capture cannot share a rollout with stationary-rent export."
            )
        if a2_v23_p08_state_bank["enabled"]:
            get_p05_evidence = getattr(self.env, "get_a2_v23_p05_episode_evidence", None)
            if not callable(get_p05_evidence):
                raise RuntimeError(
                    "P0.8 state-bank capture requires the existing P0.5 typed episode getter."
                )
            live_p05 = get_p05_evidence(0)
            if (
                not isinstance(live_p05, Mapping)
                or live_p05.get("schema") != "a2_piper_v23_episode_record_live_v1"
                or live_p05.get("mode") != _A2_V23_P08_P05_MODE
                or live_p05.get("purpose") != _A2_V23_P08_P05_PURPOSE
                or live_p05.get("step_rows") != []
            ):
                raise RuntimeError(
                    "P0.8 P0.5 preflight did not expose the initialized FULL/D1 typed state."
                )
        if a2_v23_stationary_rent["enabled"]:
            if not self.use_a2_base or not bool(getattr(self.env, "_use_a2_base", False)):
                raise RuntimeError(
                    "eval.a2_v23_stationary_rent_export requires an A2_Base environment."
                )
            if self.accelerator.num_processes != 1:
                raise RuntimeError(
                    "eval.a2_v23_stationary_rent_export requires single-process evaluation."
                )
            if eval_num_envs_episodes is not True:
                raise RuntimeError(
                    "eval.a2_v23_stationary_rent_export requires "
                    "eval.eval_num_envs_episodes=true."
                )
            stationary_runtime_enabled = self.env.config.get(
                "a2_v23_stationary_rent_runtime_enabled", False
            )
            if not isinstance(stationary_runtime_enabled, bool) or not stationary_runtime_enabled:
                raise RuntimeError(
                    "eval.a2_v23_stationary_rent_export requires "
                    "env.config.a2_v23_stationary_rent_runtime_enabled=true."
                )
            if self.env._a2_v20_r2_evidence_enabled is not False:
                raise RuntimeError(
                    "eval.a2_v23_stationary_rent_export requires "
                    "env.config.a2_v20_R2_evidence_enabled=false."
                )
        if a2_v23_p05_runtime_export:
            if not getattr(self.env, "_a2_v23_p05_enabled", False):
                raise RuntimeError(
                    "eval.a2_v23_p05_runtime_export requires env.config.a2_v23_p05_runtime_enabled=true."
                )
            if getattr(self.env, "_a2_v23_p05_mode", None) not in (
                "FULL", "ACUTE_RP0", "HIGHER_EFFORT_RESCUE"
            ):
                raise RuntimeError("P0.5 runtime export requires a strict three-mode env configuration.")
        a2_eval_diagnostics = _read_a2_eval_diagnostic_config(
            self.config.get("eval", {})
        )
        eval_to_log_records = []
        a2_v23_p0_terminal_records: list[dict] = []
        a2_v23_p05_terminal_records: list[dict] = []

        if eval_num_envs_episodes:
            max_episodes = self.env.num_envs  # One episode per environment
        else:
            max_episodes = self.config.get("eval", {}).get("num_eval_episodes", self.env.num_envs)

        if eval_num_envs_episodes:
            self.env_episode_completed = torch.zeros(
                self.env.num_envs, dtype=torch.bool, device=self.accelerator.device
            )
        eval_episode_indices = torch.zeros(
            self.env.num_envs,
            dtype=torch.long,
            device=self.accelerator.device,
        )

        # Initialize environment-based metrics tracking
        self.env.init_eval_metrics_tracking(self.accelerator.device)
        a2_stage2_trace_enabled = bool(getattr(self.env, "_use_a2_base", False))
        if a2_eval_diagnostics["diagnostic_enabled"] and not a2_stage2_trace_enabled:
            raise RuntimeError("A2 eval diagnostics can only be enabled for an A2_Base env.")
        if a2_stage2_trace_enabled:
            init_stage2_trace = getattr(self.env, "init_a2_eval_stage2_step_trace", None)
            if init_stage2_trace is None:
                raise RuntimeError(
                    "A2 eval stage2 step trace requires "
                    "env.init_a2_eval_stage2_step_trace()."
                )
            init_stage2_trace(
                diagnostic_enabled=a2_eval_diagnostics["diagnostic_enabled"],
                diagnostic_reward_terms=a2_eval_diagnostics["reward_terms"],
            )
            init_hold_oracle = getattr(self.env, "init_a2_eval_hold_oracle", None)
            if init_hold_oracle is None:
                raise RuntimeError("A2 eval requires env.init_a2_eval_hold_oracle().")
            a2_hold_oracle_config = init_hold_oracle(
                self.config.get("eval", {}),
                diagnostic_enabled=a2_eval_diagnostics["diagnostic_enabled"],
            )
            if a2_hold_oracle_config["enabled"] and not eval_num_envs_episodes:
                raise RuntimeError(
                    "A2 hold oracle requires eval.eval_num_envs_episodes=true for strict first-episode isolation."
                )
            if a2_hold_oracle_config["enabled"] and a2_eval_diagnostics["forced_close_enabled"]:
                raise RuntimeError(
                    "A2 hold oracle and generic eval forced-close intervention are mutually exclusive."
                )
            hold_detail_enabled = self.env._get_a2_hold_contact_detail_enabled()
            if hold_detail_enabled and not a2_eval_diagnostics["diagnostic_enabled"]:
                raise RuntimeError(
                    "A2 detailed hold diagnostics require eval.a2_diagnostic_trace_enabled=true."
                )
            a2_hold_runtime_metadata = None
            if hold_detail_enabled:
                get_hold_metadata = getattr(
                    self.env, "get_a2_hold_diagnostic_runtime_metadata", None
                )
                if get_hold_metadata is None:
                    raise RuntimeError(
                        "A2 detailed hold diagnostics require runtime metadata getter."
                    )
                a2_hold_runtime_metadata = get_hold_metadata()
        else:
            a2_hold_oracle_config = {"enabled": False}
            hold_detail_enabled = False
            a2_hold_runtime_metadata = None

        forced_close_stage_ids = a2_eval_diagnostics["forced_close_stages"]
        if a2_eval_diagnostics["forced_close_enabled"]:
            allowed_forced_close_stages = {
                self.env.STAGE_OPEN,
                self.env.STAGE_SWING,
            }
            if not set(forced_close_stage_ids).issubset(allowed_forced_close_stages):
                raise RuntimeError(
                    "A2 eval forced gripper close may only target stage3/open and "
                    f"stage4/swing; got {forced_close_stage_ids}."
                )
        forced_close_applied_counts = torch.zeros(
            self.env.num_envs,
            dtype=torch.long,
            device=self.accelerator.device,
        )

        # Initialize episode tracking
        self.cur_reward_sum = torch.zeros(
            self.env.num_envs, dtype=torch.float32, device=self.accelerator.device
        )
        self.cur_episode_length = torch.zeros(
            self.env.num_envs, dtype=torch.int32, device=self.accelerator.device
        )
        completed_episodes = 0
        stationary_rent_records: list[dict] = []
        stationary_rent_pending = None
        stationary_rent_captured = (
            torch.zeros(
                self.env.num_envs,
                dtype=torch.bool,
                device=self.accelerator.device,
            )
            if a2_v23_stationary_rent["enabled"]
            else None
        )
        p08_prefix_rows = [[] for _ in range(self.env.num_envs)] if a2_v23_p08_state_bank["enabled"] else None
        p08_captured_entries = {} if a2_v23_p08_state_bank["enabled"] else None
        p08_physical_readbacks = [] if a2_v23_p08_state_bank["enabled"] else None
        self.env.render_results(frame_type="initial")

        def terminate_rollout():
            if eval_num_envs_episodes:
                # Stop when all environments have completed their first episode
                return torch.all(self.env_episode_completed).item()
            else:
                # Original behavior: stop when we have collected max_episodes episodes total
                return completed_episodes >= max_episodes

        print(
            f"Starting evaluation with {'one episode per environment' if eval_num_envs_episodes else f'{max_episodes} total episodes'}"
        )

        with _a2_hold_oracle_finalize_guard(
            self.env, bool(a2_hold_oracle_config["enabled"])
        ), torch.no_grad():
            with unwrap_model_for_generation(
                self.model,
                self.accelerator,
                gather_deepspeed3_params=self.args.ds3_gather_for_generation,
            ) as model:
                while not terminate_rollout():
                    device = self.accelerator.device
                    policy_model = model.policy
                    homie_walk_model = model.homie_walk_model
                    homie_stand_model = model.homie_stand_model

                    actor_state = {}

                    actions = policy_model.rollout(obs_dict=obs_dict)
                    action_mean = policy_model.action_mean.detach()

                    if self.use_a2_base:
                        get_action_layout = getattr(
                            self.env, "get_a2_high_level_action_layout", None
                        )
                        if get_action_layout is None:
                            raise RuntimeError(
                                "A2 eval requires env.get_a2_high_level_action_layout()."
                            )
                        action_layout = get_action_layout()
                        if (
                            a2_v23_stationary_rent["enabled"]
                            and action_layout["dim"] != 12
                        ):
                            raise RuntimeError(
                                "eval.a2_v23_stationary_rent_export requires the canonical 12-D "
                                f"A2 high-level action layout; got {action_layout['dim']}."
                            )
                        expected_action_shape = (
                            self.env.num_envs,
                            action_layout["dim"],
                        )
                        if (
                            not torch.is_tensor(action_mean)
                            or tuple(action_mean.shape) != expected_action_shape
                            or not torch.is_floating_point(action_mean)
                            or not torch.all(torch.isfinite(action_mean))
                        ):
                            shape = (
                                None
                                if not torch.is_tensor(action_mean)
                                else tuple(action_mean.shape)
                            )
                            dtype = (
                                None
                                if not torch.is_tensor(action_mean)
                                else action_mean.dtype
                            )
                            raise RuntimeError(
                                "A2 eval policy action_mean requires finite floating tensor "
                                f"shape {expected_action_shape}; got shape={shape}, "
                                f"dtype={dtype}."
                            )

                        env_episode_completed = (
                            self.env_episode_completed
                            if eval_num_envs_episodes
                            else None
                        )
                        first_episode_active_mask = (
                            _build_a2_eval_first_episode_active_mask(
                                eval_num_envs_episodes=eval_num_envs_episodes,
                                env_episode_completed=env_episode_completed,
                                num_envs=self.env.num_envs,
                                device=action_mean.device,
                            )
                        )
                        stage_buf = getattr(self.env, "stage_buf", None)
                        forced_close_mask = _build_a2_eval_forced_close_mask(
                            stage_buf=stage_buf,
                            first_episode_active_mask=first_episode_active_mask,
                            forced_close_enabled=a2_eval_diagnostics[
                                "forced_close_enabled"
                            ],
                            forced_close_stage_ids=forced_close_stage_ids,
                        )
                        p2_posture_axis_action = _apply_a2_eval_p2_posture_axis(
                            action_mean,
                            action_layout,
                            a2_eval_diagnostics["p2_posture_axis"],
                        )
                        post_forced_override_pre_env_action = p2_posture_axis_action
                        if a2_eval_diagnostics["forced_close_enabled"]:
                            post_forced_override_pre_env_action = p2_posture_axis_action.clone()
                            post_forced_override_pre_env_action[
                                forced_close_mask,
                                action_layout["gripper_index"],
                            ] = a2_eval_diagnostics["forced_close_value"]
                            forced_close_applied_counts += forced_close_mask.long()

                        post_oracle_override_pre_env_action = (
                            post_forced_override_pre_env_action
                        )
                        if a2_hold_oracle_config["enabled"]:
                            apply_hold_oracle = getattr(
                                self.env, "apply_a2_eval_hold_oracle_action_override", None
                            )
                            if apply_hold_oracle is None:
                                raise RuntimeError(
                                    "A2 hold oracle requires env action override hook."
                                )
                            post_oracle_override_pre_env_action, _ = apply_hold_oracle(
                                post_forced_override_pre_env_action,
                                first_episode_active_mask,
                            )

                        if a2_v23_p05_runtime_export:
                            p05_actor_state = self.env.build_a2_v23_p05_forward_intervention_actor_state(
                                device=post_oracle_override_pre_env_action.device,
                                dtype=post_oracle_override_pre_env_action.dtype,
                            )
                            post_oracle_override_pre_env_action = self.env.apply_a2_v23_p05_high_level_intervention(
                                post_oracle_override_pre_env_action,
                                actor_state=p05_actor_state,
                            )
                            p05_actor_state["a2_v23_pre_low_level_applied"] = True
                            actor_state.update(p05_actor_state)
                        v23_mode = self.env.config.get("a2_v23_forward_intervention_mode")
                        if not a2_v23_p05_runtime_export and v23_mode is not None:
                            v23_actor_state = (
                                self.env.build_a2_v23_forward_intervention_actor_state(
                                    device=post_oracle_override_pre_env_action.device,
                                    dtype=post_oracle_override_pre_env_action.dtype,
                                )
                            )
                            post_oracle_override_pre_env_action = (
                                self.env.apply_a2_v23_high_level_intervention(
                                    post_oracle_override_pre_env_action,
                                    actor_state=v23_actor_state,
                                )
                            )
                            v23_actor_state["a2_v23_pre_low_level_applied"] = True
                            actor_state.update(v23_actor_state)

                        applied_high_level_action = post_oracle_override_pre_env_action
                        if a2_v23_stationary_rent["enabled"]:
                            stationary_target_stage = a2_v23_stationary_rent["target_stage"]
                            stationary_capture_mask = (
                                first_episode_active_mask
                                & ~stationary_rent_captured
                                & (stage_buf == stationary_target_stage)
                            )
                            stationary_env_ids = stationary_capture_mask.nonzero(
                                as_tuple=False
                            ).flatten()
                            if stationary_env_ids.numel() > 0:
                                applied_high_level_action = (
                                    post_oracle_override_pre_env_action.clone()
                                )
                                applied_high_level_action[stationary_capture_mask] = 0.0
                                stationary_rent_pending = {
                                    "env_ids": stationary_env_ids.detach().clone(),
                                    "pre_stage": stage_buf[stationary_env_ids].detach().clone(),
                                    "episode_indices": eval_episode_indices[
                                        stationary_env_ids
                                    ].detach().clone(),
                                    "policy_raw_action": action_mean[
                                        stationary_env_ids
                                    ].detach().clone(),
                                    "applied_high_level_action": applied_high_level_action[
                                        stationary_env_ids
                                    ].detach().clone(),
                                }
                                stationary_rent_captured[stationary_env_ids] = True

                        if a2_eval_diagnostics["diagnostic_enabled"]:
                            set_diagnostic_actions = getattr(
                                self.env, "set_a2_eval_diagnostic_actions", None
                            )
                            if set_diagnostic_actions is None:
                                raise RuntimeError(
                                    "A2 eval diagnostics require "
                                    "env.set_a2_eval_diagnostic_actions()."
                                )
                            set_diagnostic_actions(
                                policy_high_level_action_raw=action_mean,
                                post_forced_override_pre_env_action=(
                                    post_forced_override_pre_env_action
                                ),
                                forced_gripper_close_mask=forced_close_mask,
                                first_episode_active_mask=first_episode_active_mask,
                                episode_indices=eval_episode_indices,
                            )

                        if a2_v23_p08_state_bank["enabled"]:
                            _capture_a2_v23_p08_step(
                                config=a2_v23_p08_state_bank,
                                obs_dict=obs_dict,
                                action_mean=action_mean,
                                applied_high_level_action=applied_high_level_action,
                                stage_buf=stage_buf,
                                first_episode_active_mask=first_episode_active_mask,
                                eval_episode_indices=eval_episode_indices,
                                cur_episode_length=self.cur_episode_length,
                                prefix_rows=p08_prefix_rows,
                                captured_entries=p08_captured_entries,
                            )

                        a2_actions = model._a2_base_actions(
                            obs_dict, applied_high_level_action
                        )
                        step_actions = torch.cat(
                            [applied_high_level_action, a2_actions], dim=-1
                        )
                    else:
                        homie_obs = obs_dict["homie_obs"]
                        walk_out = homie_walk_model(homie_obs)
                        stand_out = homie_stand_model(homie_obs)
                        homie_one_step_obs = init_actor_critic_dict["num_one_step_obs"]
                        commands = homie_obs[..., -homie_one_step_obs : -(homie_one_step_obs - 3)]
                        walk_mask = (
                            torch.norm(commands, dim=-1, keepdim=True)
                            > self.homie_switch_threshold
                        )
                        m = walk_mask
                        while m.dim() < walk_out["actions"].dim():
                            m = m.unsqueeze(-1)

                        homie_actions = torch.where(
                            m, walk_out["action_mean"], stand_out["action_mean"]
                        )
                        step_actions = torch.cat([action_mean, homie_actions], dim=-1)

                    actor_state["actions"] = step_actions

                    obs_dict, rewards, dones, infos = self.env.step(actor_state)

                    if stationary_rent_pending is not None:
                        stationary_rent_records.extend(
                            _capture_a2_v23_stationary_rent_records(
                                self.env,
                                stationary_rent_pending,
                                dones,
                                target_stage=a2_v23_stationary_rent["target_stage"],
                            )
                        )
                        stationary_rent_pending = None

                    if a2_v23_p05_runtime_export:
                        apply_p05_latch = getattr(
                            self.env, "maybe_apply_a2_v23_p05_rescue_latch", None
                        )
                        if apply_p05_latch is None:
                            raise RuntimeError(
                                "P0.5 runtime export requires a typed rescue-latch hook."
                            )
                        apply_p05_latch()

                    for obs_key in obs_dict.keys():
                        obs_dict[obs_key] = obs_dict[obs_key].to(device)

                    rewards, dones = rewards.to(device), dones.to(device)

                    if a2_hold_oracle_config["enabled"]:
                        update_hold_oracle_after_step = getattr(
                            self.env, "update_a2_eval_hold_oracle_after_step", None
                        )
                        if update_hold_oracle_after_step is None:
                            raise RuntimeError(
                                "A2 hold oracle requires env post-step update hook."
                            )
                        update_hold_oracle_after_step(
                            first_episode_active_mask,
                            (dones.reshape(-1) > 0),
                        )

                    if dump_eval_to_log_metrics:
                        if "to_log" not in infos or not isinstance(infos["to_log"], dict):
                            raise RuntimeError(
                                "eval.dump_to_log_metrics requires env.step() infos['to_log'] "
                                f"to be a dict; got {type(infos.get('to_log', None)).__name__}."
                            )
                        to_log_record = {
                            "step_index": len(eval_to_log_records),
                            "episode_length_buf": self.cur_episode_length.clone(),
                            "dones": dones.clone(),
                        }
                        prepared_env_metrics = _prepare_a2_env_metrics_for_aggregation(
                            infos["to_log"], self.accelerator, device
                        )
                        prepared_env_metrics = _finalize_a2_conditional_ratios(prepared_env_metrics)
                        to_log_record.update(prepared_env_metrics)
                        eval_to_log_records.append(to_log_record)

                    self.cur_reward_sum += rewards
                    self.cur_episode_length += 1

                    self.env.update_eval_metrics_per_step(infos)

                    new_ids = (dones > 0).nonzero(as_tuple=False)

                    if len(new_ids) > 0:
                        if eval_num_envs_episodes:
                            valid_new_ids = new_ids[~self.env_episode_completed[new_ids][:, 0]]
                        else:
                            valid_new_ids = new_ids

                        if len(valid_new_ids) > 0:
                            completed_episodes += len(valid_new_ids)

                            self.env.process_eval_episode_completions(
                                valid_new_ids, self.cur_reward_sum, self.cur_episode_length
                            )

                            if a2_v23_p0_runtime_export:
                                get_v23_torque_evidence = getattr(
                                    self.env, "get_a2_v23_torque_episode_evidence", None
                                )
                                if get_v23_torque_evidence is None:
                                    raise RuntimeError(
                                        "eval.a2_v23_p0_runtime_export requires "
                                        "env.get_a2_v23_torque_episode_evidence()."
                                    )
                                for env_idx in valid_new_ids.flatten().detach().cpu().tolist():
                                    env_id = int(env_idx)
                                    terminal_record = get_v23_torque_evidence(env_id)
                                    if not isinstance(terminal_record, dict):
                                        raise RuntimeError(
                                            "v23 P0 terminal evidence getter must return a mapping."
                                        )
                                    if terminal_record.get("evidence_state") != "TERMINAL_SNAPSHOT":
                                        raise RuntimeError(
                                            "v23 P0 export requires the terminal snapshot before eval reset."
                                        )
                                    episode_index = int(eval_episode_indices[env_id].item())
                                    terminal_record = dict(terminal_record)
                                    terminal_record["terminal_identity"] = {
                                        "env_id": env_id,
                                        "episode_index": episode_index,
                                        "episode_id": f"a2-v23-eval-env{env_id}-episode{episode_index}",
                                        "authority": "EVALUATOR_ASSIGNED_ENV_EPISODE_ID",
                                    }
                                    a2_v23_p0_terminal_records.append(terminal_record)

                            if a2_v23_p05_runtime_export:
                                get_v23_p05_evidence = getattr(
                                    self.env, "get_a2_v23_p05_episode_evidence", None
                                )
                                if get_v23_p05_evidence is None:
                                    raise RuntimeError(
                                        "eval.a2_v23_p05_runtime_export requires "
                                        "env.get_a2_v23_p05_episode_evidence()."
                                    )
                                for env_idx in valid_new_ids.flatten().detach().cpu().tolist():
                                    env_id = int(env_idx)
                                    terminal_record = get_v23_p05_evidence(env_id)
                                    if not isinstance(terminal_record, dict):
                                        raise RuntimeError("P0.5 episode evidence getter must return a mapping.")
                                    if terminal_record.get("evidence_state") != "TERMINAL_SNAPSHOT":
                                        raise RuntimeError(
                                            "P0.5 runtime export requires terminal episode evidence before eval reset."
                                        )
                                    episode_index = int(eval_episode_indices[env_id].item())
                                    terminal_record = dict(terminal_record)
                                    terminal_record["evaluator_terminal_identity"] = {
                                        "env_id": env_id,
                                        "episode_index": episode_index,
                                        "episode_id": f"a2-v23-p05-eval-env{env_id}-episode{episode_index}",
                                        "authority": "EVALUATOR_ASSIGNED_ENV_EPISODE_ID",
                                    }
                                    a2_v23_p05_terminal_records.append(terminal_record)

                            if a2_v23_p08_state_bank["enabled"]:
                                get_p05_evidence = getattr(
                                    self.env, "get_a2_v23_p05_episode_evidence", None
                                )
                                if not callable(get_p05_evidence):
                                    raise RuntimeError(
                                        "P0.8 state-bank capture requires the P0.5 typed episode getter."
                                    )
                                for env_idx in valid_new_ids.flatten().detach().cpu().tolist():
                                    env_id = int(env_idx)
                                    episode_index = int(eval_episode_indices[env_id].item())
                                    terminal_record = get_p05_evidence(env_id)
                                    p08_physical_readbacks.append(
                                        _validate_a2_v23_p08_p05_terminal_readback(
                                            terminal_record,
                                            config=a2_v23_p08_state_bank,
                                            env_id=env_id,
                                            episode_index=episode_index,
                                        )
                                    )

                            for env_idx in valid_new_ids:
                                reward = self.cur_reward_sum[env_idx].item()
                                length = self.cur_episode_length[env_idx].item()

                            if eval_num_envs_episodes:
                                self.env_episode_completed[valid_new_ids] = True

                        self.cur_reward_sum[new_ids] = 0
                        self.cur_episode_length[new_ids] = 0
                        eval_episode_indices[new_ids.flatten()] += 1

                        # Reset environment episode tracking
                        self.env.reset_eval_episode_tracking(new_ids)

                        if not terminate_rollout():
                            if eval_num_envs_episodes:
                                restart_env_ids = new_ids[
                                    ~self.env_episode_completed[new_ids][:, 0]
                                ]
                            else:
                                restart_env_ids = new_ids
                            self.env.render_results(
                                env_ids=restart_env_ids.flatten(), frame_type="initial"
                            )

                    if not terminate_rollout():
                        non_terminal_env_ids = (dones == 0).nonzero(as_tuple=False).flatten()
                        if eval_num_envs_episodes:
                            non_terminal_env_ids = non_terminal_env_ids[
                                ~self.env_episode_completed[non_terminal_env_ids]
                            ]
                        self.env.render_results(env_ids=non_terminal_env_ids, frame_type="step")

        self.env.end_render_results()
        self.policy_model.clear_rollout()
        print(f"Evaluation completed - {completed_episodes} episodes finished")

        # Get evaluation summary from environment (includes class-wise metrics)
        eval_dict = self.env.get_eval_metrics_summary()
        eval_dict["completed_episodes"] = completed_episodes

        # save eval_dict to a file
        import json
        import os

        eval_output_dir = getattr(self.args, "eval_output_dir", self.args.output_dir)
        strict_m41_telemetry = a2_eval_diagnostics["strict_m41_telemetry"]
        strict_v20_telemetry = a2_eval_diagnostics["strict_v20_telemetry"]
        strict_stage2_trace_records = None
        strict_safe_stage2_trace = None
        strict_v14_eval_records = None
        strict_safe_v14_records = None
        strict_safe_to_log_metrics = None
        strict_safe_eval_dict = None
        strict_v20_payload = None
        if strict_m41_telemetry:
            if not eval_num_envs_episodes:
                raise RuntimeError(
                    "eval.a2_eval_m41_strict_telemetry=true requires "
                    "eval_num_envs_episodes=true for unambiguous first-episode rows."
                )
            if not a2_stage2_trace_enabled or not a2_eval_diagnostics["diagnostic_enabled"]:
                raise RuntimeError(
                    "eval.a2_eval_m41_strict_telemetry=true requires an A2 diagnostic "
                    "stage2 trace (a2_diagnostic_trace_enabled=true)."
                )
            if self.accelerator.num_processes != 1:
                raise RuntimeError(
                    "A2 M41 strict telemetry requires single-process matched eval."
                )
            get_stage2_trace = getattr(
                self.env, "get_a2_eval_stage2_step_trace_records", None
            )
            if get_stage2_trace is None:
                raise RuntimeError(
                    "A2 M41 strict telemetry requires "
                    "env.get_a2_eval_stage2_step_trace_records()."
                )
            strict_stage2_trace_records = get_stage2_trace()
            strict_v14_eval_records = _build_a2_v14_eval_records(
                eval_dict,
                int(self.args.seed),
                self.env.num_envs,
                include_m38_fields=True,
            )
            _validate_a2_m41_eval_telemetry(
                eval_dict, strict_stage2_trace_records, self.env.num_envs
            )
            strict_safe_stage2_trace = _make_json_safe(
                strict_stage2_trace_records, path="stage2_step_trace"
            )
            strict_safe_v14_records = _make_json_safe(
                strict_v14_eval_records, path="a2_v14_per_env_records"
            )
            strict_safe_eval_dict = _make_json_safe(eval_dict)
            if dump_eval_to_log_metrics:
                _normalize_a2_eval_optional_ratios(eval_to_log_records)
                strict_safe_to_log_metrics = _make_json_safe(
                    eval_to_log_records, path="eval_to_log_metrics"
                )

        if strict_v20_telemetry:
            if not eval_num_envs_episodes:
                raise RuntimeError(
                    "eval.a2_eval_v20_strict_telemetry=true requires eval_num_envs_episodes=true."
                )
            if not a2_stage2_trace_enabled or not a2_eval_diagnostics["diagnostic_enabled"]:
                raise RuntimeError(
                    "A2 v20 strict telemetry requires an enabled A2 diagnostic stage2 trace."
                )
            if self.accelerator.num_processes != 1:
                raise RuntimeError("A2 v20 strict telemetry requires single-process matched eval.")
            if strict_stage2_trace_records is None:
                get_stage2_trace = getattr(
                    self.env, "get_a2_eval_stage2_step_trace_records", None
                )
                if get_stage2_trace is None:
                    raise RuntimeError(
                        "A2 v20 strict telemetry requires env.get_a2_eval_stage2_step_trace_records()."
                    )
                strict_stage2_trace_records = get_stage2_trace()
            checkpoint_value = self.checkpoint_path
            if checkpoint_value is None:
                raise RuntimeError(
                    "A2 v20 strict telemetry requires an explicit trainer checkpoint."
                )
            checkpoint_path = str(Path(str(checkpoint_value)).expanduser().resolve())
            checkpoint_file = Path(checkpoint_path)
            if not checkpoint_file.is_file():
                raise RuntimeError(f"A2 v20 strict telemetry checkpoint is missing: {checkpoint_path}")
            checkpoint_digest = hashlib.sha256()
            with checkpoint_file.open("rb") as checkpoint_stream:
                for chunk in iter(lambda: checkpoint_stream.read(1024 * 1024), b""):
                    checkpoint_digest.update(chunk)
            checkpoint_sha256 = checkpoint_digest.hexdigest()
            config_hash = _a2_v20_config_hash(self.config)
            topology = {
                "name": "canonical16" if self.env.num_envs == 16 else f"matched{self.env.num_envs}",
                "episode_count": self.env.num_envs,
                "first_episode_only": True,
                "single_process": True,
            }
            strict_v20_records = _build_a2_v20_strict_telemetry_records(
                eval_dict,
                strict_stage2_trace_records,
                self.env.num_envs,
                checkpoint_path=checkpoint_path,
                checkpoint_sha256=checkpoint_sha256,
                config_hash=config_hash,
                seed=int(self.args.seed),
                topology=topology,
            )
            strict_v20_payload = _make_json_safe(
                {
                    "schema": "a2_piper_v20_strict_telemetry_v1",
                    "checkpoint_path": checkpoint_path,
                    "checkpoint_sha256": checkpoint_sha256,
                    "config_hash": config_hash,
                    "seed": int(self.args.seed),
                    "topology": topology,
                    "records": strict_v20_records,
                },
                path="a2_v20_strict_telemetry",
            )

        if not os.path.exists(eval_output_dir):
            os.makedirs(eval_output_dir, exist_ok=True)

        if a2_v23_stationary_rent["enabled"]:
            stationary_payload = {
                "schema": _A2_V23_STATIONARY_RENT_PASS_SCHEMA,
                "status": (
                    "COMPLETE" if stationary_rent_records else "INCOMPLETE_MISSING_STAGE"
                ),
                "target_stage": int(a2_v23_stationary_rent["target_stage"]),
                "forward_only": True,
                "state_clone_supported": False,
                "checkpoint_load_mode": self.checkpoint_load_mode,
                "num_envs": int(self.env.num_envs),
                "reward_semantics": {
                    "raw": "reward-function output",
                    "scaled": (
                        "raw * configured scale in this project custom engine; "
                        "no IsaacLab manager dt factor"
                    ),
                },
                "records": stationary_rent_records,
            }
            stationary_path = os.path.join(
                eval_output_dir, _A2_V23_STATIONARY_RENT_PASS_FILENAME
            )
            stationary_tmp_path = f"{stationary_path}.tmp"
            with open(stationary_tmp_path, "w", encoding="utf-8") as stationary_stream:
                json.dump(
                    _make_json_safe(stationary_payload, path="a2_v23_stationary_rent_pass"),
                    stationary_stream,
                    indent=4,
                    allow_nan=False,
                )
            os.replace(stationary_tmp_path, stationary_path)
            logger.info(f"Saved v23 stationary-rent pass to {stationary_path}")

        if a2_v23_p0_runtime_export:
            env_config = getattr(self.env, "config", None)
            if env_config is None or "a2_v23_effort_profile_nm" not in env_config:
                raise RuntimeError(
                    "eval.a2_v23_p0_runtime_export requires "
                    "env.config.a2_v23_effort_profile_nm."
                )
            effort_nm = env_config.get("a2_v23_effort_profile_nm")
            v23_records_payload, v23_aggregate_payload = _build_a2_v23_p0_export_payload(
                a2_v23_p0_terminal_records,
                effort_nm=effort_nm,
            )
            v23_records_path = os.path.join(
                eval_output_dir, "a2_v23_p0_torque_terminal_records.json"
            )
            v23_records_tmp_path = f"{v23_records_path}.tmp"
            with open(v23_records_tmp_path, "w") as f:
                json.dump(
                    _make_json_safe(v23_records_payload, path="a2_v23_p0_terminal_records"),
                    f,
                    indent=4,
                    allow_nan=False,
                )
            os.replace(v23_records_tmp_path, v23_records_path)
            v23_aggregate_path = os.path.join(
                eval_output_dir, "a2_v23_p0_effort_observations.json"
            )
            v23_aggregate_tmp_path = f"{v23_aggregate_path}.tmp"
            with open(v23_aggregate_tmp_path, "w") as f:
                json.dump(
                    _make_json_safe(v23_aggregate_payload, path="a2_v23_p0_effort_observations"),
                    f,
                    indent=4,
                    allow_nan=False,
                )
            os.replace(v23_aggregate_tmp_path, v23_aggregate_path)
            temporal_payload = v23_records_payload.get(
                "temporal_records",
                {
                    "schema": "a2_piper_base_v23_p0_temporal_records_v1",
                    "temporary_label": "A0_CANONICAL16_P0_REFERENCE",
                    "records": [],
                    "status": "PENDING_NO_RAW_TEMPORAL_RECORDS",
                    "aggregate_fallback": False,
                },
            )
            temporal_path = os.path.join(eval_output_dir, "a2_v23_p0_temporal_records.json")
            temporal_tmp_path = f"{temporal_path}.tmp"
            with open(temporal_tmp_path, "w") as f:
                json.dump(_make_json_safe(temporal_payload, path="a2_v23_p0_temporal_records"), f, indent=4, allow_nan=False)
            os.replace(temporal_tmp_path, temporal_path)
            logger.info(f"Saved v23 P0 terminal records to {v23_records_path}")
            logger.info(f"Saved v23 P0 effort observations to {v23_aggregate_path}")
            logger.info(f"Saved v23 P0 raw temporal records to {temporal_path}")

        if a2_v23_p05_runtime_export:
            if not a2_v23_p05_terminal_records:
                raise RuntimeError("P0.5 runtime export requires at least one terminal episode record.")
            step_records = []
            window_records = []
            for episode in a2_v23_p05_terminal_records:
                rows = episode.get("step_rows")
                windows = episode.get("window_rows")
                if not isinstance(rows, list) or not isinstance(windows, list):
                    raise RuntimeError("P0.5 terminal episode records require step_rows and window_rows lists.")
                step_records.extend(rows)
                window_records.extend(windows)
            p05_exports = {
                "a2_v23_p05_step_records.json": {
                    "schema": "a2_piper_v23_step_records_export_v1",
                    "records": step_records,
                    "source": "a2_v23_p05_terminal_episode_snapshots",
                },
                "a2_v23_p05_window_records.json": {
                    "schema": "a2_piper_v23_window_records_export_v1",
                    "records": window_records,
                    "source": "a2_v23_p05_terminal_episode_snapshots",
                },
                "a2_v23_p05_episode_records.json": {
                    "schema": "a2_piper_v23_episode_records_export_v1",
                    "records": a2_v23_p05_terminal_records,
                    "source": "a2_v23_p05_terminal_episode_snapshots",
                },
                "a2_v23_p05_pairs.json": {
                    "schema": "a2_piper_v23_prefix_pairs_export_v1",
                    "status": "PENDING_SEPARATE_FORWARD_RUNS",
                    "records": [],
                    "comparison": "direct_python_equality_of_registered_pre_switch_rows",
                },
            }
            for filename, payload in p05_exports.items():
                output_path = os.path.join(eval_output_dir, filename)
                tmp_path = f"{output_path}.tmp"
                with open(tmp_path, "w") as f:
                    json.dump(_make_json_safe(payload, path=filename), f, indent=4, allow_nan=False)
                os.replace(tmp_path, output_path)
                logger.info(f"Saved v23 P0.5 evidence to {output_path}")

        if strict_v20_payload is not None:
            v20_path = os.path.join(eval_output_dir, "a2_v20_strict_telemetry.json")
            _a2_v20_publish_json_exclusive(v20_path, strict_v20_payload)
            logger.info(f"Saved A2 v20 strict telemetry to {v20_path}")

        if dump_eval_to_log_metrics:
            to_log_metrics_path = os.path.join(eval_output_dir, "eval_to_log_metrics.json")
            to_log_metrics_tmp_path = f"{to_log_metrics_path}.tmp"
            # Eval-only conversion; training keeps raw finite tensor metrics in its meter.
            if strict_safe_to_log_metrics is None:
                _normalize_a2_eval_optional_ratios(eval_to_log_records)
                safe_to_log_metrics = _make_json_safe(
                    eval_to_log_records, path="eval_to_log_metrics"
                )
            else:
                safe_to_log_metrics = strict_safe_to_log_metrics
            with open(to_log_metrics_tmp_path, "w") as f:
                json.dump(safe_to_log_metrics, f, indent=4, allow_nan=False)
            os.replace(to_log_metrics_tmp_path, to_log_metrics_path)
            logger.info(f"Saved eval to_log metrics to {to_log_metrics_path}")

        if a2_stage2_trace_enabled and eval_num_envs_episodes:
            if self.accelerator.num_processes != 1:
                raise RuntimeError(
                    "A2 v14 per-env eval records require single-process matched eval."
                )
            v14_eval_records = strict_v14_eval_records or _build_a2_v14_eval_records(
                eval_dict,
                int(self.args.seed),
                self.env.num_envs,
                include_m38_fields=strict_m41_telemetry,
            )
            v14_records_path = os.path.join(
                eval_output_dir,
                "a2_v14_per_env_records.json",
            )
            v14_records_tmp_path = f"{v14_records_path}.tmp"
            safe_v14_records = strict_safe_v14_records or _make_json_safe(
                v14_eval_records,
                path="a2_v14_per_env_records",
            )
            with open(v14_records_tmp_path, "w") as f:
                json.dump(safe_v14_records, f, indent=4, allow_nan=False)
            os.replace(v14_records_tmp_path, v14_records_path)
            logger.info(
                f"Saved A2 v14 per-env records to {v14_records_path}"
            )

        if a2_eval_diagnostics["diagnostic_enabled"]:
            get_action_layout = getattr(
                self.env, "get_a2_high_level_action_layout", None
            )
            get_hinge_threshold = getattr(
                self.env, "_get_a2_stage3_to4_door_hinge_threshold", None
            )
            if get_action_layout is None or get_hinge_threshold is None:
                raise RuntimeError(
                    "A2 eval diagnostic metadata requires canonical action layout and "
                    "stage3->4 hinge threshold accessors."
                )
            diagnostic_metadata = {
                "diagnostic_trace_enabled": True,
                "reward_terms": list(a2_eval_diagnostics["reward_terms"]),
                "forced_gripper_close_enabled": a2_eval_diagnostics[
                    "forced_close_enabled"
                ],
                "forced_gripper_close_value": a2_eval_diagnostics[
                    "forced_close_value"
                ],
                "forced_gripper_close_stages": list(forced_close_stage_ids),
                "forced_gripper_close_applied_counts": forced_close_applied_counts,
                "p2_posture_axis": a2_eval_diagnostics["p2_posture_axis"],
                "m41_strict_telemetry": a2_eval_diagnostics["strict_m41_telemetry"],
                "v20_strict_telemetry": a2_eval_diagnostics["strict_v20_telemetry"],
                "canonical_high_level_action_layout": get_action_layout(),
                "stage3_to4_door_hinge_threshold": get_hinge_threshold(),
                "trace_timing": {
                    "policy_and_post_forced_override": (
                        "computed from the pre-step observation and pre-step stage_buf"
                    ),
                    "post_delta_post_warp_env_action": (
                        "captured inside A2Base after DeltaActionBase and "
                        "WarpedActionBase, before action-to-joint-target mapping"
                    ),
                    "articulation_state_contact_reward": (
                        "captured after physics tensor refresh and reward computation, "
                        "before reset and before staged-task stage advancement"
                    ),
                    "joint_pos_target": (
                        "the Articulation position target used for the completed physics "
                        "step, read after physics and before reset"
                    ),
                    "stage_buf": "pre-stage-advance for the completed physics step",
                },
                "first_episode_contract": (
                    "when eval_num_envs_episodes=true, intervention, counts, and expanded "
                    "trace include only envs whose first episode is still active; "
                    "episode_index audits reset boundaries"
                ),
            }
            diagnostic_metadata_path = os.path.join(
                eval_output_dir, "a2_eval_diagnostic_metadata.json"
            )
            diagnostic_metadata_tmp_path = f"{diagnostic_metadata_path}.tmp"
            safe_diagnostic_metadata = _make_json_safe(
                diagnostic_metadata, path="a2_eval_diagnostic_metadata"
            )
            with open(diagnostic_metadata_tmp_path, "w") as f:
                json.dump(safe_diagnostic_metadata, f, indent=4, allow_nan=False)
            os.replace(diagnostic_metadata_tmp_path, diagnostic_metadata_path)
            logger.info(
                "Saved A2 eval diagnostic metadata to "
                f"{diagnostic_metadata_path}"
            )

        if hold_detail_enabled:
            hold_metadata_path = os.path.join(
                eval_output_dir, "a2_hold_diagnostic_runtime_metadata.json"
            )
            hold_metadata_tmp_path = f"{hold_metadata_path}.tmp"
            safe_hold_metadata = _make_json_safe(
                a2_hold_runtime_metadata, path="a2_hold_diagnostic_runtime_metadata"
            )
            with open(hold_metadata_tmp_path, "w") as f:
                json.dump(safe_hold_metadata, f, indent=4, allow_nan=False)
            os.replace(hold_metadata_tmp_path, hold_metadata_path)
            logger.info(f"Saved A2 hold runtime metadata to {hold_metadata_path}")

        if a2_hold_oracle_config["enabled"]:
            get_hold_summary = getattr(self.env, "get_a2_hold_oracle_summary", None)
            if get_hold_summary is None:
                raise RuntimeError("A2 hold oracle requires env summary getter.")
            hold_summary_path = os.path.join(
                eval_output_dir, "a2_hold_oracle_summary.json"
            )
            hold_summary_tmp_path = f"{hold_summary_path}.tmp"
            safe_hold_summary = _make_json_safe(
                get_hold_summary(), path="a2_hold_oracle_summary"
            )
            with open(hold_summary_tmp_path, "w") as f:
                json.dump(safe_hold_summary, f, indent=4, allow_nan=False)
            os.replace(hold_summary_tmp_path, hold_summary_path)
            logger.info(f"Saved A2 hold oracle summary to {hold_summary_path}")

        if a2_stage2_trace_enabled:
            get_stage2_trace = getattr(
                self.env, "get_a2_eval_stage2_step_trace_records", None
            )
            if get_stage2_trace is None:
                raise RuntimeError(
                    "A2 eval stage2 step trace requires "
                    "env.get_a2_eval_stage2_step_trace_records()."
                )
            safe_stage2_trace = strict_safe_stage2_trace or _make_json_safe(
                get_stage2_trace(), path="stage2_step_trace"
            )
            for trace_filename in ("stage2_5_step_trace.json", "stage2_step_trace.json"):
                stage2_trace_path = os.path.join(eval_output_dir, trace_filename)
                stage2_trace_tmp_path = f"{stage2_trace_path}.tmp"
                with open(stage2_trace_tmp_path, "w") as f:
                    json.dump(safe_stage2_trace, f, indent=4, allow_nan=False)
                os.replace(stage2_trace_tmp_path, stage2_trace_path)
                logger.info(f"Saved A2 stage2-5 step trace to {stage2_trace_path}")

        metrics_eval_path = os.path.join(eval_output_dir, "metrics_eval.json")
        metrics_eval_tmp_path = f"{metrics_eval_path}.tmp"
        safe_eval_dict = strict_safe_eval_dict or _make_json_safe(eval_dict)
        with open(metrics_eval_tmp_path, "w") as f:
            json.dump(safe_eval_dict, f, indent=4, allow_nan=False)
        os.replace(metrics_eval_tmp_path, metrics_eval_path)

        logger.info(f"Saved eval_dict to {metrics_eval_path}")  # self.args.eval_output_dir

        if a2_v23_p08_state_bank["enabled"]:
            _write_a2_v23_p08_raw_capture(
                eval_output_dir,
                a2_v23_p08_state_bank,
                p08_captured_entries,
                completed_episodes=completed_episodes,
                physical_readbacks=p08_physical_readbacks,
            )

        return eval_dict

    def batch_write_frame(self, vision_obs):
        """
        vision_obs: [B, H*W*C], [0, 1/255], float32 (The range is a bug)
        This function is for eval time, save all envs' frames,
            as opposed to write_frame, which is for training time, only save the frames for self.visualize_env_idx
        """
        flattened_rgb_images = vision_obs.clone()

        batch_size = flattened_rgb_images.shape[0]

        rgb_images = flattened_rgb_images.reshape(
            batch_size, *self.camera_resolution
        )  # [B, H, W, C]

        # To uint8
        rgb_images = (rgb_images * 255.0).to(torch.uint8)  # [B, H, W, C]

        # Append to frames list
        for i in range(self.env.num_envs):
            self.batch_frames[i].append(rgb_images[i])  # [H, W, C]

    def batch_write_low_dim_obs(
        self,
        actor_obs,
        student_obs,
        actions,
        rewards,
        dones,
    ):
        """
        actor_obs: [B, dim_actor_obs]
        student_obs: [B, dim_student_obs]
        actions: [B, dim_actions]
        rewards: [B]
        dones: [B]
        """
        for i in range(self.env.num_envs):
            self.actor_obs_to_save[i].append(actor_obs[i].cpu().numpy())
            self.student_obs_to_save[i].append(student_obs[i].cpu().numpy())
            self.actions_to_save[i].append(actions[i].cpu().numpy())
            self.reward_to_save[i].append(rewards[i].item())
            # Convert to bool
            self.done_to_save[i].append(bool(dones[i].item()))

    def batch_reset_data_writer(self, env_indices, save_dirpath):
        """
        :param env_indices: list of env indices that have finished the episode
        """
        for env_idx in env_indices:
            do_not_save = False

            cur_reward_sum = self.cur_reward_sum[env_idx].item()
            goal_reached = self.goal_reached_buf[env_idx].item()

            if self.config.eval.save_goal_reached_only:
                if goal_reached == 0:
                    do_not_save = True

            if np.random.rand() > self.config.eval.video_save_prob:
                do_not_save = True

            if do_not_save:
                # Simply empty the buffers
                self.batch_frames[env_idx] = []
                if self.config.eval.save_trajectories:
                    self.actor_obs_to_save[env_idx] = []
                    self.student_obs_to_save[env_idx] = []
                    self.actions_to_save[env_idx] = []
                    self.reward_to_save[env_idx] = []
                    self.done_to_save[env_idx] = []
                continue

            # Video saving
            video_save_dirpath = Path(save_dirpath) / "videos"

            save_filename = f"eps{self.saved_episode_cnt}_env{env_idx.item()}_len{len(self.batch_frames[env_idx])}_reward{cur_reward_sum:.2f}_goal{int(goal_reached)}_rank{self.accelerator.process_index}"
            video_path = video_save_dirpath / f"{save_filename}.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)

            video_tensor = torch.stack(self.batch_frames[env_idx][1:])  # [T, H, W, C]

            fps = 20
            torchvision.io.write_video(str(video_path), video_tensor, fps=fps, video_codec="h264")

            # print(f"Video saved to {video_path}")

            self.batch_frames[env_idx] = []
            self.saved_episode_cnt += 1

            # Low dim data saving
            if self.config.eval.save_trajectories:
                low_dim_data_save_dirpath = Path(save_dirpath) / "data"
                low_dim_data_save_dirpath.mkdir(parents=True, exist_ok=True)

                save_data = {
                    "observation.state": self.student_obs_to_save[env_idx][1:],
                    "actor_obs": self.actor_obs_to_save[env_idx][1:],
                    "action": self.actions_to_save[env_idx][1:],
                    "reward": self.reward_to_save[env_idx][1:],
                    "done": self.done_to_save[env_idx][1:],
                }

                episode_length = len(video_tensor)
                for key, value in save_data.items():
                    assert len(value) == episode_length, f"{key}: {len(value)} != {episode_length}"

                save_data["timestamp"] = np.arange(episode_length) / fps

                data_save_path = low_dim_data_save_dirpath / f"{save_filename}.parquet"

                df = pd.DataFrame(save_data)
                df.to_parquet(data_save_path)

                # Empty the buffers
                self.actor_obs_to_save[env_idx] = []
                self.student_obs_to_save[env_idx] = []
                self.actions_to_save[env_idx] = []
                self.reward_to_save[env_idx] = []
                self.done_to_save[env_idx] = []

            if self.saved_episode_cnt >= self.config.eval.num_save_episodes:
                break

    @torch.no_grad()
    def get_example_obs(self):
        obs_dict = self.env.reset_all()
        for obs_key in obs_dict.keys():
            print(obs_key, sorted(self.env.config.obs.obs_dict[obs_key]))
        # move to cpu
        for k in obs_dict:
            obs_dict[k] = obs_dict[k].cpu()
        return obs_dict

    @property
    def inference_model(self):
        return {"actor": self.model.policy, "critic": self.model.value_model}
