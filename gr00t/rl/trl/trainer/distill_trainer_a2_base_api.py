# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A2+Piper DAgger trainer with a strict 12D/12D action boundary.

The student and Teacher learn only the 12D A2 high-level command.  A frozen
A2_Base policy consumes the 1620D observation and returns 12D leg actions; the
24D concatenation is created once at the environment boundary.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import math
from pathlib import Path

import numpy as np
import torch

from gr00t.rl.agents.modules.data_utils import RolloutStorage
from gr00t.rl.trl.trainer.distill_trainer import TRLDistillTrainer
from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import (
    TRLPPOTrainer as A2TRLPPOTrainer,
    _load_a2_base_metadata,
    _validate_optional_a2_config_value,
)
from gr00t.rl.trl.utils.rl import compute_episode_attnmask
from gr00t.rl.utils.average_meters import TensorAverageMeterDict


A2_STUDENT_ACTION_DIM = 12
A2_BASE_ACTION_DIM = 12
A2_ROLLOUT_ACTION_DIM = 24
A2_TEACHER_OBS_DIM = 133
A2_CRITIC_OBS_DIM = 138
A2_BASE_OBS_DIM = 1620
_A2_ACTION_BASE_DIM = 5
_A2_ACTION_ARM_DIM = 7
_A2_TEACHER_IDENTITY_EMITTED = False
_A2_ACTION_CHAIN_EMITTED = False

# The long B1 route supplies this exact schedule through Hydra.  Keeping the
# schema/phase arithmetic here means the rollout source cannot silently fall
# back to a fixed ratio or a prefix mask when the schedule is malformed.
MIXED_ROLLOUT_SCHEDULE_SCHEMA = "a2_cb2h_mixed_rollout_schedule_v1"
MIXED_ROLLOUT_PHASE_FIELDS = {"phase", "start_step", "end_step", "ratio"}


def build_cyclic_teacher_mask(
    num_envs,
    ratio_teacher_rollout,
    global_step,
    *,
    enforce_teacher_rollout=True,
    device=None,
):
    """Build the deterministic cyclic Teacher/Student source mask.

    The mask is intended to be created once at rollout start.  A contiguous
    Student block rotates by ``global_step % num_envs``; its complement is the
    Teacher source.  No random sampling or prefix assignment is used.
    """
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs <= 0:
        raise ValueError(f"num_envs must be a positive integer; got {num_envs!r}")
    if isinstance(global_step, bool) or not isinstance(global_step, int) or global_step < 0:
        raise ValueError(f"global_step must be a non-negative integer; got {global_step!r}")
    if isinstance(ratio_teacher_rollout, bool):
        raise ValueError("ratio_teacher_rollout must be a finite real number")
    try:
        ratio = float(ratio_teacher_rollout)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"ratio_teacher_rollout must be a finite real number; got {ratio_teacher_rollout!r}"
        ) from exc
    if not math.isfinite(ratio) or not 0.0 <= ratio <= 1.0:
        raise ValueError(f"ratio_teacher_rollout must be within [0,1], got {ratio}")
    raw_teacher_count = num_envs * ratio
    teacher_count = int(round(raw_teacher_count))
    if not math.isclose(raw_teacher_count, teacher_count, rel_tol=0.0, abs_tol=1.0e-9):
        raise ValueError(
            "ratio_teacher_rollout must yield an exact integer Teacher count; "
            f"num_envs={num_envs} ratio={ratio:.12g} product={raw_teacher_count:.12g}"
        )
    # ``enforce_teacher_rollout`` is the compatibility switch for every
    # ratio, including ratio=1.0.  When disabled the rollout must remain
    # entirely Student-sourced; there is no special-case all-Teacher branch.
    if not enforce_teacher_rollout:
        teacher_count = 0
    student_count = num_envs - teacher_count
    mask = torch.zeros(num_envs, dtype=torch.bool, device=device)
    if teacher_count == num_envs:
        mask.fill_(True)
    elif teacher_count > 0:
        student_count = num_envs - teacher_count
        offset = global_step % num_envs
        student_indices = (torch.arange(student_count, device=device) + offset) % num_envs
        mask[:] = True
        mask[student_indices] = False
    else:
        mask.zero_()
    if int(mask.sum().item()) != teacher_count:
        raise RuntimeError(
            "Cyclic Teacher mask count drifted: "
            f"expected={teacher_count} actual={int(mask.sum().item())}"
        )
    return mask


def cyclic_teacher_mask_hash(mask):
    """Return a stable SHA-256 identity for one boolean rollout mask."""
    if not torch.is_tensor(mask) or mask.ndim != 1 or mask.dtype != torch.bool:
        raise ValueError("rollout mask hash requires a one-dimensional boolean tensor")
    if mask.numel() <= 0:
        raise ValueError("rollout mask hash requires at least one environment")
    payload = mask.to(device="cpu", dtype=torch.uint8).contiguous().numpy().tobytes()
    return hashlib.sha256(payload).hexdigest()


def validate_mixed_rollout_schedule(schedule, *, target_global_step=None):
    """Validate and normalize contiguous mixed-rollout phases.

    ``start_step`` is inclusive and ``end_step`` is exclusive.  The terminal
    target itself is not selectable for a rollout.  An explicit schedule must
    cover exactly the configured target; no gaps, overlaps, or implicit
    fallback ratio are accepted.
    """
    if isinstance(schedule, (str, bytes, bytearray, Mapping)) or not hasattr(schedule, "__iter__"):
        raise ValueError("mixed rollout schedule must be a non-empty list")
    schedule = list(schedule)
    if not schedule:
        raise ValueError("mixed rollout schedule must be a non-empty list")
    normalized = []
    expected_start = 0
    seen_phases = set()
    for index, entry in enumerate(schedule):
        if not isinstance(entry, Mapping) or set(entry) != MIXED_ROLLOUT_PHASE_FIELDS:
            raise ValueError(
                f"mixed rollout phase {index} must contain exactly {sorted(MIXED_ROLLOUT_PHASE_FIELDS)}"
            )
        phase = entry["phase"]
        if not isinstance(phase, str) or not phase:
            raise ValueError(f"mixed rollout phase {index} name must be a non-empty string")
        if phase in seen_phases:
            raise ValueError(f"mixed rollout phase names must be unique: {phase}")
        seen_phases.add(phase)
        starts = entry["start_step"]
        ends = entry["end_step"]
        if isinstance(starts, bool) or not isinstance(starts, int) or starts < 0:
            raise ValueError(f"mixed rollout phase {phase} start_step must be a non-negative integer")
        if isinstance(ends, bool) or not isinstance(ends, int) or ends <= starts:
            raise ValueError(f"mixed rollout phase {phase} end_step must exceed start_step")
        if starts != expected_start:
            raise ValueError(
                f"mixed rollout schedule must be contiguous: expected start {expected_start}, got {starts}"
            )
        ratio_value = entry["ratio"]
        if isinstance(ratio_value, bool):
            raise ValueError(f"mixed rollout phase {phase} ratio must be finite")
        try:
            ratio = float(ratio_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"mixed rollout phase {phase} ratio must be finite") from exc
        if not math.isfinite(ratio) or not 0.0 <= ratio <= 1.0:
            raise ValueError(f"mixed rollout phase {phase} ratio must be within [0,1]")
        normalized.append(
            {"phase": phase, "start_step": starts, "end_step": ends, "ratio": ratio}
        )
        expected_start = ends
    if target_global_step is not None:
        if isinstance(target_global_step, bool) or not isinstance(target_global_step, int) or target_global_step <= 0:
            raise ValueError("mixed rollout target_global_step must be a positive integer")
        if expected_start != target_global_step:
            raise ValueError(
                "mixed rollout schedule must end at target_global_step: "
                f"end={expected_start} target={target_global_step}"
            )
    return tuple(normalized)


def resolve_mixed_rollout_phase(schedule, global_step):
    """Resolve one non-terminal global step to its exact phase/ratio."""
    if isinstance(global_step, bool) or not isinstance(global_step, int) or global_step < 0:
        raise ValueError("mixed rollout global_step must be a non-negative integer")
    phases = validate_mixed_rollout_schedule(schedule)
    if global_step >= phases[-1]["end_step"]:
        raise ValueError(
            f"mixed rollout global_step={global_step} is terminal/not selectable; "
            f"target={phases[-1]['end_step']}"
        )
    for phase in phases:
        if phase["start_step"] <= global_step < phase["end_step"]:
            return dict(phase)
    raise RuntimeError(f"mixed rollout schedule did not resolve global_step={global_step}")


def _emit_teacher_identity(checkpoint_path):
    global _A2_TEACHER_IDENTITY_EMITTED
    if _A2_TEACHER_IDENTITY_EMITTED:
        return
    checkpoint = Path(checkpoint_path).resolve(strict=True)
    print(
        "[A2_TEACHER_IDENTITY] "
        f"checkpoint={checkpoint} obs_dim={A2_TEACHER_OBS_DIM} action_dim={A2_STUDENT_ACTION_DIM}",
        flush=True,
    )
    _A2_TEACHER_IDENTITY_EMITTED = True


def _emit_action_chain_identity(teacher_rollout_ratio):
    global _A2_ACTION_CHAIN_EMITTED
    if _A2_ACTION_CHAIN_EMITTED:
        return
    if not isinstance(teacher_rollout_ratio, (int, float)) or not np.isfinite(teacher_rollout_ratio):
        raise ValueError(f"A2 action-chain teacher rollout ratio must be finite; got {teacher_rollout_ratio!r}")
    print(
        "[A2_ACTION_CHAIN] "
        f"high_level_dim={A2_STUDENT_ACTION_DIM} "
        f"a2_base_dim={A2_BASE_ACTION_DIM} rollout_dim={A2_ROLLOUT_ACTION_DIM} "
        f"teacher_rollout_ratio={teacher_rollout_ratio:.12g}",
        flush=True,
    )
    _A2_ACTION_CHAIN_EMITTED = True


def _validate_floating_tensor(name, value, last_dim):
    if not torch.is_tensor(value) or value.ndim < 2 or value.shape[-1] != last_dim:
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{name} must be a tensor with last dimension {last_dim}; got {shape}")
    if not torch.is_floating_point(value) or not torch.all(torch.isfinite(value)):
        raise ValueError(f"{name} must be a finite floating tensor")


def compose_a2_rollout_action(high_level_actions, a2_base_actions):
    """Compose the only environment-facing A2 action tensor (12 + 12 = 24)."""
    _validate_floating_tensor("high_level_actions", high_level_actions, A2_STUDENT_ACTION_DIM)
    _validate_floating_tensor("a2_base_actions", a2_base_actions, A2_BASE_ACTION_DIM)
    if high_level_actions.shape[:-1] != a2_base_actions.shape[:-1]:
        raise ValueError(
            "A2 high-level/leg action leading shapes must match; "
            f"got {tuple(high_level_actions.shape[:-1])} and {tuple(a2_base_actions.shape[:-1])}"
        )
    action = torch.cat((high_level_actions, a2_base_actions), dim=-1)
    if action.shape[-1] != A2_ROLLOUT_ACTION_DIM:
        raise RuntimeError(f"A2 rollout action composition drifted: got {action.shape[-1]}")
    return action


class TRLDistillTrainerA2BaseAPI(TRLDistillTrainer):
    """DAgger trainer for the A2+Piper Student route."""

    _tag_names = ["trl", "a2_piper_distill"]

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
        optimizers=(None, None),
        callbacks=None,
        peft_config=None,
        use_ref_model=False,
        checkpoint=None,
        local_seed=None,
        schedule_dict=None,
        accelerator=None,
        a2_gpu_identity=None,
    ) -> None:
        self._a2_rgb_frame_validated = False
        self.a2_gpu_identity = a2_gpu_identity
        self._cb2h_rollout_mask = None
        self._cb2h_rollout_mask_config = None
        self._cb2h_rollout_mask_emitted = False
        self._cb2h_rollout_action_sq_sum = None
        self._cb2h_rollout_disagreement_sum = None
        self._cb2h_rollout_sample_count = 0
        self._cb2h_rollout_feature_sum = {}
        self._cb2h_rollout_feature_count = 0
        self._cb2h_rollout_stage_sq_sum = {}
        self._cb2h_rollout_stage_count = {}
        self._cb2h_last_rollout_metrics = {}
        self._cb2h_last_schedule_phase = None
        self._cb2h_stage_tensor_override = None
        self._cb2h_stage_hook_required_emitted = False
        self._cb2h_gradient_sums = {"gradient/d435_norm": 0.0, "gradient/head_norm": 0.0}
        self._cb2h_gradient_count = 0
        self._cb2h_train_feature_sums = {}
        self._cb2h_train_feature_count = 0
        self._a2_teacher_phase_records = []
        self._a2_bc_only_graph_validated = False
        self._a2_last_bc_loss = None
        self._a2_last_gradient_finite = False
        super().__init__(
            args=args,
            config=config,
            env=env,
            model=model,
            ref_model=ref_model,
            reward_model=reward_model,
            processing_class=processing_class,
            value_model=value_model,
            data_collator=data_collator,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            log_dir=log_dir,
            optimizers=optimizers,
            callbacks=callbacks,
            peft_config=peft_config,
            use_ref_model=use_ref_model,
            checkpoint=checkpoint,
            local_seed=local_seed,
            schedule_dict=schedule_dict,
            accelerator=accelerator,
        )

    def _begin_cb2h_rollout_observability(self):
        self._cb2h_rollout_mask = None
        self._cb2h_rollout_mask_config = None
        self._cb2h_rollout_mask_emitted = False
        self._cb2h_rollout_action_sq_sum = None
        self._cb2h_rollout_disagreement_sum = None
        self._cb2h_rollout_sample_count = 0
        self._cb2h_rollout_feature_sum = {}
        self._cb2h_rollout_feature_count = 0
        self._cb2h_rollout_stage_sq_sum = {}
        self._cb2h_rollout_stage_count = {}
        self._cb2h_last_rollout_metrics = {}
        self._cb2h_stage_tensor_override = None
        self._cb2h_gradient_sums = {"gradient/d435_norm": 0.0, "gradient/head_norm": 0.0}
        self._cb2h_gradient_count = 0
        self._cb2h_train_feature_sums = {}
        self._cb2h_train_feature_count = 0

    def _cb2h_schedule_target(self):
        lifecycle = self.config.get("p2_lifecycle", None)
        if lifecycle is None or lifecycle.get("enabled") is not True:
            return None
        target = lifecycle.get("target_global_step")
        if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
            raise ValueError("C-B2H p2_lifecycle.target_global_step must be a positive integer")
        return target

    def _resolve_cb2h_rollout_phase(self, global_step):
        schedule = self.config.get("mixed_rollout_schedule", None)
        if schedule is None:
            ratio = self.config.get("ratio_teacher_rollout", 1.0)
            if isinstance(ratio, bool):
                raise ValueError("ratio_teacher_rollout must be a finite real number")
            try:
                ratio = float(ratio)
            except (TypeError, ValueError) as exc:
                raise ValueError("ratio_teacher_rollout must be a finite real number") from exc
            if not math.isfinite(ratio) or not 0.0 <= ratio <= 1.0:
                raise ValueError(f"ratio_teacher_rollout must be within [0,1], got {ratio}")
            return {"phase": "STATIC", "start_step": 0, "end_step": None, "ratio": ratio}
        phases = validate_mixed_rollout_schedule(
            schedule,
            target_global_step=self._cb2h_schedule_target(),
        )
        return resolve_mixed_rollout_phase(phases, global_step)

    def _register_stats_buffer(self):
        super()._register_stats_buffer()
        self._cb2h_gradient_sums = {"gradient/d435_norm": 0.0, "gradient/head_norm": 0.0}
        self._cb2h_gradient_count = 0
        self._cb2h_train_feature_sums = {}
        self._cb2h_train_feature_count = 0

    def record_stage_tensor(self, stage_tensor):
        """Provide the exact pre-action stage tensor for stage-stratified metrics.

        The Student observation intentionally does not include privileged stage.
        A caller with access to the environment stage buffer may provide it once
        per policy step; no proxy stage is inferred from rewards or termination.
        """
        if not torch.is_tensor(stage_tensor) or stage_tensor.ndim != 1:
            raise ValueError(
                "C-B2H stage diagnostic tensor must be a rank-1 tensor [num_envs]"
            )
        expected_envs = getattr(getattr(self, "env", None), "num_envs", stage_tensor.shape[0])
        if int(stage_tensor.shape[0]) != int(expected_envs):
            raise ValueError(
                "C-B2H stage diagnostic tensor length must match num_envs; "
                f"got {tuple(stage_tensor.shape)} expected={expected_envs}"
            )
        if stage_tensor.dtype.is_floating_point:
            if not bool(torch.all(torch.isfinite(stage_tensor)).item()):
                raise ValueError("C-B2H stage diagnostic tensor must be finite")
            if not bool(torch.all(stage_tensor == stage_tensor.round()).item()):
                raise ValueError("C-B2H stage diagnostic tensor must contain integer stage ids")
        elif stage_tensor.dtype not in (
            torch.int8,
            torch.int16,
            torch.int32,
            torch.int64,
            torch.uint8,
        ):
            raise ValueError("C-B2H stage diagnostic tensor must use an integer dtype")
        self._cb2h_stage_tensor_override = stage_tensor.detach().to(device="cpu", dtype=torch.int64).clone()

    def _stage_tensor_for_policy_step(self, expected_envs):
        stage_tensor = self._cb2h_stage_tensor_override
        self._cb2h_stage_tensor_override = None
        if stage_tensor is None:
            stage_tensor = getattr(getattr(self, "env", None), "stage_buf", None)
        if stage_tensor is None:
            return None
        if not torch.is_tensor(stage_tensor) or stage_tensor.ndim != 1:
            raise ValueError("C-B2H environment stage buffer must be rank-1 [num_envs]")
        if tuple(stage_tensor.shape) != (expected_envs,):
            raise ValueError(
                "C-B2H environment stage buffer shape mismatch: "
                f"got {tuple(stage_tensor.shape)} expected={(expected_envs,)}"
            )
        if stage_tensor.dtype.is_floating_point:
            if not bool(torch.all(torch.isfinite(stage_tensor)).item()):
                raise ValueError("C-B2H environment stage buffer must be finite")
            if not bool(torch.all(stage_tensor == stage_tensor.round()).item()):
                raise ValueError("C-B2H environment stage buffer must contain integer stage ids")
        elif stage_tensor.dtype not in (
            torch.int8,
            torch.int16,
            torch.int32,
            torch.int64,
            torch.uint8,
        ):
            raise ValueError("C-B2H environment stage buffer must use an integer dtype")
        return stage_tensor.detach().to(device="cpu", dtype=torch.int64).clone()

    def _ensure_cb2h_rollout_mask(self, batch_size, device):
        if self._cb2h_rollout_mask is None:
            global_step = int(getattr(self.state, "global_step", 0))
            phase = self._resolve_cb2h_rollout_phase(global_step)
            ratio = phase["ratio"]
            enforce = bool(self.config.get("enforce_teacher_rollout", False))
            mask = build_cyclic_teacher_mask(
                batch_size,
                ratio,
                global_step,
                enforce_teacher_rollout=enforce,
                device=device,
            )
            self._cb2h_rollout_mask = mask
            self._cb2h_rollout_mask_config = (
                batch_size,
                float(ratio),
                enforce,
                global_step,
                phase["phase"],
            )
            self._cb2h_rollout_mask_emitted = True
            teacher_count = int(mask.sum().item())
            student_count = batch_size - teacher_count
            mask_hash = cyclic_teacher_mask_hash(mask)
            previous_phase = getattr(self, "_cb2h_last_schedule_phase", None)
            if previous_phase != phase["phase"]:
                print(
                    "[A2_ROLLOUT_PHASE] "
                    f"transition={previous_phase or 'START'}->{phase['phase']} "
                    f"global_step={global_step} ratio={ratio:.12g}",
                    flush=True,
                )
                self._cb2h_last_schedule_phase = phase["phase"]
            print(
                "[A2_ROLLOUT_MASK] "
                f"phase={phase['phase']} ratio={ratio:.12g} global_step={global_step} "
                f"teacher_count={teacher_count} student_count={student_count} "
                f"mask_hash={mask_hash}",
                flush=True,
            )
        else:
            expected_device = self._cb2h_rollout_mask.device
            if self._cb2h_rollout_mask.shape != (batch_size,) or expected_device != device:
                raise ValueError(
                    "C-B2H rollout mask shape/device changed within one rollout: "
                    f"mask={tuple(self._cb2h_rollout_mask.shape)}@{expected_device} "
                    f"current={(batch_size,)}@{device}"
                )
            current_config = self._cb2h_rollout_mask_config
            if current_config is None:
                raise RuntimeError("C-B2H rollout mask configuration was lost")
            if int(getattr(self.state, "global_step", current_config[3])) != current_config[3]:
                raise ValueError("C-B2H global_step changed within one fixed-mask rollout")
        return self._cb2h_rollout_mask

    @staticmethod
    def _module_gradient_norm(module):
        gradients = [parameter.grad.detach() for parameter in module.parameters() if parameter.grad is not None]
        if not gradients:
            return 0.0
        norm = torch.linalg.vector_norm(torch.cat([gradient.reshape(-1) for gradient in gradients]))
        if not bool(torch.isfinite(norm).item()):
            raise ValueError("C-B2H gradient norm must be finite")
        return float(norm.item())

    def _policy_for_cb2h_observability(self):
        diagnostic_enabled = getattr(self, "_a2_p2_diagnostic_enabled", False) or getattr(
            self, "_a2_cb2h_enabled", False
        )
        if not diagnostic_enabled:
            return None
        candidate = getattr(self, "model", None)
        accelerator = getattr(self, "accelerator", None)
        if candidate is not None and accelerator is not None and hasattr(accelerator, "unwrap_model"):
            candidate = accelerator.unwrap_model(candidate)
        policy = getattr(candidate, "policy", None) or getattr(self, "policy_model", None)
        if policy is None:
            raise RuntimeError("C-B2H observability requires an accessible Student policy")
        d435_module, head_module = self._cb2h_encoder_modules(policy)
        if d435_module is None:
            raise RuntimeError("P2 Student policy is missing the shared D435 encoder")
        if (
            getattr(self, "_a2_p2_b2_enabled", False)
            or getattr(self, "_a2_p2_b2h_toeout6_enabled", False)
            or getattr(self, "_a2_cb2h_enabled", False)
        ) and head_module is None:
            raise RuntimeError("P2 B2 Student policy is missing the Head encoder")
        return policy

    def _validate_a2_cb2h_policy_graph(self):
        if (
            self.a2_gpu_identity is None
            or self.a2_gpu_identity.get("mode") != "accelerate-ddp-4rank-64e-v1"
            or not getattr(self, "_a2_cb2h_enabled", False)
        ):
            return
        policy_for_graph = self._policy_for_cb2h_observability()
        trainable = []
        unfrozen_noise = []
        for name, parameter in policy_for_graph.named_parameters():
            if parameter.requires_grad:
                trainable.append(name)
            if "std" in name.lower() and parameter.requires_grad:
                unfrozen_noise.append(name)
        if not trainable:
            raise RuntimeError("A2 BC-only DDP graph has no trainable policy parameters")
        if unfrozen_noise:
            raise RuntimeError(
                "A2 BC-only DDP graph has trainable noise-standard-deviation parameters: "
                f"{unfrozen_noise}"
            )
        self._a2_bc_only_graph_validated = True

    @staticmethod
    def _cb2h_encoder_modules(policy):
        if hasattr(policy, "d435i_vision_module"):
            return policy.d435i_vision_module, getattr(policy, "head_vision_module", None)
        core = getattr(policy, "core", None)
        if core is not None and hasattr(core, "d435i_vision_module"):
            return core.d435i_vision_module, getattr(policy, "head_vision_module", None)
        return None, None

    def _record_cb2h_rollout_diagnostics(self, policy_model, student_mean, teacher_actions, stage_tensor):
        error_sq = (student_mean - teacher_actions).square()
        disagreement = (student_mean - teacher_actions).abs()
        if error_sq.ndim != 2 or error_sq.shape[-1] != A2_STUDENT_ACTION_DIM:
            raise ValueError("C-B2H action diagnostics require [num_envs,12] tensors")
        if not bool(torch.all(torch.isfinite(error_sq)).item()) or not bool(
            torch.all(torch.isfinite(disagreement)).item()
        ):
            raise ValueError("C-B2H action diagnostics must be finite")
        if self._cb2h_rollout_action_sq_sum is None:
            self._cb2h_rollout_action_sq_sum = torch.zeros(
                A2_STUDENT_ACTION_DIM, dtype=torch.float64, device=error_sq.device
            )
            self._cb2h_rollout_disagreement_sum = torch.zeros((), dtype=torch.float64, device=error_sq.device)
        self._cb2h_rollout_action_sq_sum += error_sq.detach().to(torch.float64).sum(dim=0)
        self._cb2h_rollout_disagreement_sum += disagreement.detach().to(torch.float64).sum()
        self._cb2h_rollout_sample_count += int(error_sq.shape[0])

        snapshot_fn = getattr(policy_model, "get_observability_snapshot", None)
        if snapshot_fn is not None:
            snapshot = snapshot_fn()
            for name, value in snapshot.items():
                if not torch.is_tensor(value) or value.ndim != 0 or not bool(torch.isfinite(value.float()).item()):
                    raise ValueError(f"C-B2H observability metric {name!r} must be a finite scalar")
                self._cb2h_rollout_feature_sum[name] = self._cb2h_rollout_feature_sum.get(name, 0.0) + float(
                    value.item()
                )
            self._cb2h_rollout_feature_count += 1

        if stage_tensor is not None:
            if tuple(stage_tensor.shape) != (error_sq.shape[0],):
                raise ValueError("C-B2H stage diagnostic tensor/action batch shape mismatch")
            stage_cpu = stage_tensor.to(device="cpu", dtype=torch.int64)
            for stage_id in torch.unique(stage_cpu, sorted=True).tolist():
                stage_mask = stage_cpu == int(stage_id)
                stage_error = error_sq.detach().to(device="cpu", dtype=torch.float64)[stage_mask]
                self._cb2h_rollout_stage_sq_sum[int(stage_id)] = self._cb2h_rollout_stage_sq_sum.get(
                    int(stage_id), 0.0
                ) + float(stage_error.mean().item()) * int(stage_error.shape[0])
                self._cb2h_rollout_stage_count[int(stage_id)] = self._cb2h_rollout_stage_count.get(
                    int(stage_id), 0
                ) + int(stage_error.shape[0])

    def _finish_cb2h_rollout_observability(self):
        if self._cb2h_rollout_sample_count <= 0:
            raise RuntimeError("C-B2H rollout produced no action diagnostics")
        count = float(self._cb2h_rollout_sample_count)
        action_mean = self._cb2h_rollout_action_sq_sum / count
        metrics = {
            "distill/action_sq_error_mean": float(action_mean.mean().item()),
            "distill/action_sq_error_base5": float(
                action_mean[:_A2_ACTION_BASE_DIM].mean().item()
            ),
            "distill/action_sq_error_arm7": float(
                action_mean[_A2_ACTION_BASE_DIM:].mean().item()
            ),
            "distill/teacher_student_action_disagreement": float(
                (self._cb2h_rollout_disagreement_sum / count).item()
            ),
            "diagnostics/comparable_action_error": 1.0,
            "diagnostics/comparable_d435_feature": 1.0,
            "diagnostics/head_feature_available": 1.0 if getattr(self, "_a2_p2_b2_enabled", False) or getattr(self, "_a2_cb2h_enabled", False) else 0.0,
            "diagnostics/head_feature_excluded_from_pair": 1.0,
        }
        for index, value in enumerate(action_mean.tolist()):
            metrics[f"distill/action_sq_error_dim_{index}"] = float(value)
        if self._cb2h_rollout_feature_count:
            feature_count = float(self._cb2h_rollout_feature_count)
            for name, value in self._cb2h_rollout_feature_sum.items():
                average = value / feature_count
                metrics.setdefault(name, average)
                metrics[f"rollout/{name}"] = average
        if self._cb2h_rollout_stage_count:
            for stage_id in sorted(self._cb2h_rollout_stage_count):
                stage_count = self._cb2h_rollout_stage_count[stage_id]
                metrics[f"distill/stage_{stage_id}_action_sq_error"] = (
                    self._cb2h_rollout_stage_sq_sum[stage_id] / stage_count
                )
            metrics["diagnostics/stage_stratified_action_error_available"] = 1.0
        else:
            metrics["diagnostics/stage_stratified_action_error_available"] = 0.0
            if not self._cb2h_stage_hook_required_emitted:
                print(
                    "[A2_STAGE_DIAGNOSTIC] stage_tensor=unavailable "
                    "required_r2=true hook=record_stage_tensor",
                    flush=True,
                )
                self._cb2h_stage_hook_required_emitted = True
        mask = self._cb2h_rollout_mask
        if mask is None:
            raise RuntimeError("C-B2H rollout mask was not recorded")
        mask_config = self._cb2h_rollout_mask_config
        if not isinstance(mask_config, tuple) or len(mask_config) < 4:
            raise RuntimeError("C-B2H rollout mask configuration is incomplete")
        metrics.update(
            {
                "rollout/phase": mask_config[4] if len(mask_config) >= 5 else "STATIC",
                "rollout/ratio_teacher_rollout": float(mask_config[1]),
                "rollout/teacher_count": int(mask.sum().item()),
                "rollout/student_count": int(mask.numel() - mask.sum().item()),
                "rollout/mask_hash": cyclic_teacher_mask_hash(mask),
                "rollout/mask_global_step": int(mask_config[3]),
            }
        )
        teacher_phase_records = getattr(self, "_a2_teacher_phase_records", None)
        if teacher_phase_records is None:
            teacher_phase_records = []
            self._a2_teacher_phase_records = teacher_phase_records
        teacher_phase_records.append(
            {
                "global_step": int(mask_config[3]),
                "phase": mask_config[4] if len(mask_config) >= 5 else "STATIC",
                "local_teacher_count": int(mask.sum().item()),
                "local_env_count": int(mask.numel()),
                "mask_hash": cyclic_teacher_mask_hash(mask),
            }
        )
        self._cb2h_last_rollout_metrics = metrics

    def _build_cb2h_train_observability(self):
        metrics = dict(getattr(self, "_cb2h_last_rollout_metrics", {}))
        diagnostic_enabled = getattr(self, "_a2_p2_diagnostic_enabled", False) or getattr(
            self, "_a2_cb2h_enabled", False
        )
        if not diagnostic_enabled:
            return metrics
        policy = self._policy_for_cb2h_observability()
        snapshot_fn = getattr(policy, "get_observability_snapshot", None)
        if snapshot_fn is None:
            raise RuntimeError("C-B2H Student policy must expose observability snapshots")
        snapshot = snapshot_fn()
        for name, value in snapshot.items():
            if not torch.is_tensor(value) or value.ndim != 0 or not bool(torch.isfinite(value.float()).item()):
                raise ValueError(f"C-B2H observability metric {name!r} must be a finite scalar")
        if self._cb2h_train_feature_count:
            feature_count = float(self._cb2h_train_feature_count)
            for name, total in self._cb2h_train_feature_sums.items():
                metrics[f"train/{name}"] = total / feature_count
        else:
            for name, value in snapshot.items():
                metrics[f"train/{name}"] = float(value.item())
                metrics.setdefault(name, float(value.item()))
        if self._cb2h_gradient_count:
            for name, value in self._cb2h_gradient_sums.items():
                if name == "gradient/head_norm" and not getattr(self, "_a2_p2_b2_enabled", False) and not getattr(
                    self, "_a2_cb2h_enabled", False
                ):
                    continue
                metrics[name] = value / self._cb2h_gradient_count
        else:
            d435_module, head_module = self._cb2h_encoder_modules(policy)
            metrics["gradient/d435_norm"] = self._module_gradient_norm(d435_module)
            if head_module is not None:
                metrics["gradient/head_norm"] = self._module_gradient_norm(head_module)
        return metrics

    def _gradient_clipping(self):
        super()._gradient_clipping()
        if getattr(self, "_a2_bc_only_graph_validated", False):
            policy = self._policy_for_cb2h_observability()
            missing = [
                name
                for name, parameter in policy.named_parameters()
                if parameter.requires_grad and parameter.grad is None
            ]
            if missing:
                raise RuntimeError(
                    "A2 BC-only DDP graph has trainable parameters without backward gradients: "
                    f"{missing}"
                )
            gradients = [
                parameter.grad.detach()
                for parameter in policy.parameters()
                if parameter.requires_grad and parameter.grad is not None
            ]
            if not gradients or not all(bool(torch.all(torch.isfinite(gradient)).item()) for gradient in gradients):
                raise RuntimeError("A2 BC-only DDP graph produced non-finite or empty gradients")
            self._a2_last_gradient_finite = True
        diagnostic_enabled = getattr(self, "_a2_p2_diagnostic_enabled", False) or getattr(
            self, "_a2_cb2h_enabled", False
        )
        if not diagnostic_enabled:
            return
        policy = self._policy_for_cb2h_observability()
        d435_module, head_module = self._cb2h_encoder_modules(policy)
        self._cb2h_gradient_sums["gradient/d435_norm"] += self._module_gradient_norm(d435_module)
        if head_module is not None:
            self._cb2h_gradient_sums["gradient/head_norm"] += self._module_gradient_norm(head_module)
        self._cb2h_gradient_count += 1
        snapshot = policy.get_observability_snapshot()
        for name, value in snapshot.items():
            if not torch.is_tensor(value) or value.ndim != 0 or not bool(torch.isfinite(value.float()).item()):
                raise ValueError(f"C-B2H train observability metric {name!r} must be a finite scalar")
            self._cb2h_train_feature_sums[name] = self._cb2h_train_feature_sums.get(name, 0.0) + float(
                value.item()
            )
        self._cb2h_train_feature_count += 1

    def load_teacher_actor(self):
        artifact = self.config.get("teacher_artifact", None)
        if artifact is None:
            raise ValueError("A2 Student requires teacher_artifact checkpoint/config/manifest paths")
        checkpoint_path = artifact.get("checkpoint_path")
        config_path = artifact.get("config_path")
        manifest_path = artifact.get("manifest_path")
        if not all(isinstance(path, str) and path for path in (checkpoint_path, config_path, manifest_path)):
            raise ValueError("A2 Student Teacher artifact paths must be non-empty strings")
        expected_fields = {
            "checkpoint_sha256": artifact.get("checkpoint_sha256"),
            "config_sha256": artifact.get("config_sha256"),
            "manifest_sha256": artifact.get("manifest_sha256"),
        }
        for field_name, expected in expected_fields.items():
            if not isinstance(expected, str) or len(expected) != 64 or any(
                character not in "0123456789abcdef" for character in expected
            ):
                raise ValueError(f"A2 Teacher artifact requires pinned lowercase {field_name}")
        runtime_repository = artifact.get("runtime_repository")
        runtime_commit = artifact.get("runtime_commit")
        if not isinstance(runtime_repository, str) or not runtime_repository.strip():
            raise ValueError("A2 Teacher artifact requires pinned runtime_repository")
        if not isinstance(runtime_commit, str) or not runtime_commit.strip():
            raise ValueError("A2 Teacher artifact requires pinned runtime_commit")
        from gr00t.rl.scripts.run_a2_cb2h_pro_toeout_mgpu import (
            EXPECTED_RUNTIME_COMMIT,
            validate_runtime_repository,
        )
        runtime_identity = validate_runtime_repository(Path(runtime_repository))
        if runtime_commit != EXPECTED_RUNTIME_COMMIT or runtime_identity["commit"] != runtime_commit:
            raise RuntimeError(
                "A2 Teacher runtime repository identity mismatch: "
                f"expected={runtime_commit!r} actual={runtime_identity['commit']!r}"
            )
        from gr00t.rl.scripts.validate_a2_teacher_checkpoint import (
            sha256_file,
            validate_teacher_artifact,
        )

        selected_paths = {
            "checkpoint_sha256": checkpoint_path,
            "config_sha256": config_path,
            "manifest_sha256": manifest_path,
        }
        for field_name, path in selected_paths.items():
            actual = sha256_file(path)
            if actual != expected_fields[field_name]:
                raise RuntimeError(
                    "A2 immutable Teacher provenance mismatch before load: "
                    f"{field_name} expected={expected_fields[field_name]} actual={actual}"
                )

        manifest = validate_teacher_artifact(checkpoint_path, config_path, manifest_path)
        if manifest.get("checkpoint", {}).get("sha256") != expected_fields["checkpoint_sha256"]:
            raise RuntimeError("A2 Teacher manifest checkpoint identity is not config-pinned")
        if manifest.get("source", {}).get("config_sha256") != expected_fields["config_sha256"]:
            raise RuntimeError("A2 Teacher manifest source config identity is not config-pinned")
        if manifest.get("source", {}).get("commit") != runtime_commit:
            raise RuntimeError(
                "A2 Teacher runtime commit mismatch: "
                f"expected={runtime_commit!r} actual={manifest.get('source', {}).get('commit')!r}"
            )
        if sha256_file(manifest_path) != expected_fields["manifest_sha256"]:
            raise RuntimeError("A2 Teacher manifest bytes changed during validation")
        if self.ref_model is None:
            raise ValueError("A2 Student requires a recurrent Teacher reference model")
        if getattr(self.ref_model, "num_actions", None) != A2_STUDENT_ACTION_DIM:
            raise ValueError(
                "A2 Teacher action boundary must be 12D; "
                f"got {getattr(self.ref_model, 'num_actions', None)!r}"
            )
        loaded = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        state_key = manifest["checkpoint"]["state_dict_key"]
        state_dict = loaded[state_key]
        self.ref_model.load_state_dict(state_dict, strict=True)
        self.ref_model.eval()
        _emit_teacher_identity(checkpoint_path)
        self.teacher_manifest = manifest

    def load_checkpoint(self, checkpoint_path):
        """Load one strict A2 Student actor checkpoint and optional full state."""
        print(f"Loading checkpoint from {checkpoint_path}")
        checkpoint = torch.load(
            checkpoint_path, map_location=self.accelerator.device, weights_only=False
        )
        if not isinstance(checkpoint, Mapping):
            raise ValueError(
                "A2 Student checkpoint must be a mapping; "
                f"got {type(checkpoint).__name__}"
            )
        actor_keys = [
            key
            for key in ("policy_state_dict", "actor_model_state_dict")
            if key in checkpoint
        ]
        if len(actor_keys) != 1:
            raise ValueError(
                "A2 Student checkpoint must contain exactly one actor state dict key "
                "(policy_state_dict or actor_model_state_dict); "
                f"found {actor_keys!r}"
            )

        model = self.accelerator.unwrap_model(self.model)
        model.policy.load_state_dict(checkpoint[actor_keys[0]], strict=True)
        if "value_state_dict" in checkpoint and model.value_model is not None:
            model.value_model.load_state_dict(checkpoint["value_state_dict"])

        if "optimizer_state_dict" in checkpoint and checkpoint["optimizer_state_dict"] is not None:
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            if "args" in checkpoint and hasattr(checkpoint["args"], "learning_rate"):
                self.args.learning_rate = checkpoint["args"].learning_rate
                for param_group in self.optimizer.param_groups:
                    param_group["lr"] = self.args.learning_rate

        if (
            "lr_scheduler_state_dict" in checkpoint
            and checkpoint["lr_scheduler_state_dict"] is not None
        ):
            self.lr_scheduler.load_state_dict(checkpoint["lr_scheduler_state_dict"])

        if "env_state_dict" in checkpoint:
            self.env.load_env_state_dict(checkpoint["env_state_dict"])

        if "state" in checkpoint:
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

        print(f"Loaded checkpoint from step {self.state.global_step}")
        return checkpoint

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
        **kwargs,
    ):
        # Reuse the complete A2 PPO preparation path exactly once.  It owns
        # A2_Base loading, PolicyAndValueWrapper construction, optimizer,
        # callbacks and distributed model preparation.  DAgger adds only its
        # loss, scheduler and immutable Teacher load below.
        schedule_dict = kwargs.pop("schedule_dict", None)
        if kwargs:
            raise TypeError(f"Unexpected A2 Student trainer _init_trl kwargs: {sorted(kwargs)}")
        a2_config = config.get("a2_base", None)
        if a2_config is None or a2_config.get("enabled") is not True:
            raise ValueError("A2 Student trainer requires algo.config.a2_base.enabled=true")
        metadata_path = a2_config.get("metadata_path")
        policy_path = a2_config.get("policy_path")
        for field_name, path_value in (("metadata_path", metadata_path), ("policy_path", policy_path)):
            if not isinstance(path_value, str) or not path_value.strip():
                raise ValueError(f"A2_Base {field_name} must be a non-empty string")
            if not Path(path_value).expanduser().is_file():
                raise FileNotFoundError(f"A2_Base {field_name} does not exist: {path_value}")
        A2TRLPPOTrainer._init_trl(
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
            schedule_dict=schedule_dict,
        )

        if self.a2_gpu_identity is not None and self.a2_gpu_identity.get("mode") == "accelerate-ddp-4rank-64e-v1":
            if self.config.get("distill_only", False) is not True:
                raise RuntimeError("C-B2H four-rank training requires distill_only=true")
            if value_model is not None or getattr(self, "value_model", None) is not None:
                raise RuntimeError("C-B2H distillation-only training must not construct a value model")
            if self.config.get("freeze_noise_std", False) is not True:
                raise RuntimeError("C-B2H distillation-only training requires freeze_noise_std=true")
        dagger_bc_loss_type = self.config.get("dagger_bc_loss_type", "l2")
        if dagger_bc_loss_type == "l2":
            self.bc_loss_fn = torch.nn.MSELoss()
        elif dagger_bc_loss_type == "l1":
            self.bc_loss_fn = torch.nn.L1Loss()
        else:
            raise ValueError(f"Invalid dagger_bc_loss_type: {dagger_bc_loss_type}")

        self.train_with_evaluating_env = self.config.get("train_with_evaluating_env", True)
        self.compute_dagger_bc_loss_w_imgaug = self.config.get(
            "compute_dagger_bc_loss_w_imgaug", False
        )
        self._setup_cosine_scheduler(args)
        self.load_teacher_actor()

        if self.policy_model.num_actions != A2_STUDENT_ACTION_DIM:
            raise ValueError(
                f"A2 Student policy must produce 12D high-level actions; got {self.policy_model.num_actions}"
            )
        contract = _load_a2_base_metadata(metadata_path)
        _validate_optional_a2_config_value(a2_config, "obs_dim", contract["obs_dim"])
        _validate_optional_a2_config_value(a2_config, "action_dim", contract["action_dim"])
        if contract["obs_dim"] != A2_BASE_OBS_DIM or contract["action_dim"] != A2_BASE_ACTION_DIM:
            raise ValueError(f"A2_Base contract must be 1620D -> 12D; got {contract}")
        if self.a2_base_model is None or not self.use_a2_base:
            raise RuntimeError("A2 PPO initialization did not construct the frozen A2_Base model")
        if self.a2_base_obs_dim != A2_BASE_OBS_DIM or self.a2_base_action_dim != A2_BASE_ACTION_DIM:
            raise ValueError(
                "A2 PPO metadata contract drifted: "
                f"obs={self.a2_base_obs_dim}, action={self.a2_base_action_dim}"
            )

    def _init_config(self):
        A2TRLPPOTrainer._init_config(self)
        self.num_act = A2_ROLLOUT_ACTION_DIM
        self.teacher_action_dim = A2_STUDENT_ACTION_DIM
        self.a2_base_obs_dim = A2_BASE_OBS_DIM
        self.a2_base_action_dim = A2_BASE_ACTION_DIM
        cameras_config = self.env.config.simulator.config.cameras
        policy_multiview = cameras_config.get("policy_multiview", None)
        architecture_id = (
            policy_multiview.get("architecture_id", None)
            if policy_multiview is not None
            else None
        )
        self._a2_p2_b1_enabled = architecture_id == "C-B1-DUALRAW-SHAREDENC-TOEIN20-V19-P2"
        self._a2_p2_b2_enabled = architecture_id == "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19-P2"
        self._a2_p2_b2h_toeout6_enabled = architecture_id == "C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2"
        self._a2_cb2h_enabled = architecture_id in {
            "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19",
            "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19-P2",
            "C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2",
        }
        self._a2_dual_d435_enabled = self._a2_p2_b1_enabled or self._a2_cb2h_enabled
        self._a2_camera_meta_enabled = self._a2_dual_d435_enabled
        self._a2_p2_diagnostic_enabled = (
            self._a2_p2_b1_enabled
            or self._a2_p2_b2_enabled
            or self._a2_p2_b2h_toeout6_enabled
        )
        if self._a2_dual_d435_enabled:
            if self.config.get("compute_dagger_bc_loss_w_imgaug", False):
                raise ValueError("Dual-D435 Student does not support image-augmented DAgger loss")
            if self.config.get("compute_imgaug_bc_loss", False):
                raise ValueError("Dual-D435 Student does not support image-augmented BC loss")
            self.camera_resolution = [384, 216, 6]
            self.camera_meta_resolution = [4 if self._a2_p2_b1_enabled else 6]
            expected_obs_dims = {
                "vision_obs": int(np.prod(self.camera_resolution)),
                "camera_meta": self.camera_meta_resolution[0],
            }
            if self._a2_cb2h_enabled:
                self.context_camera_resolution = [136, 384, 3]
                expected_obs_dims["context_vision_obs"] = int(np.prod(self.context_camera_resolution))
            for key, expected_dim in expected_obs_dims.items():
                if key not in self.algo_obs_dim_dict:
                    raise KeyError(f"Dual-D435 Student requires algo observation key {key!r}")
                if int(self.algo_obs_dim_dict[key]) != expected_dim:
                    raise ValueError(
                        f"Dual-D435 {key} dimension mismatch: "
                        f"config={self.algo_obs_dim_dict[key]}, expected={expected_dim}"
                    )
        if self.config.get("student_action_dim", A2_STUDENT_ACTION_DIM) != A2_STUDENT_ACTION_DIM:
            raise ValueError("student_action_dim must be exactly 12")
        if self.config.get("rollout_action_dim", A2_ROLLOUT_ACTION_DIM) != A2_ROLLOUT_ACTION_DIM:
            raise ValueError("rollout_action_dim must be exactly 24")
        self._validate_a2_cb2h_policy_graph()

    def _setup_storage(self):
        self.storage = RolloutStorage(
            self.env.num_envs, self.num_steps_per_env, device=self.accelerator.device
        )
        for obs_key, obs_dim in self.algo_obs_dim_dict.items():
            if obs_key == "vision_obs":
                if self.camera_resolution is None:
                    raise ValueError("A2 Student vision_obs requires an enabled camera resolution")
                expected_dim = int(np.prod(self.camera_resolution))
                if int(obs_dim) != expected_dim:
                    raise ValueError(f"vision_obs dim mismatch: config={obs_dim}, expected={expected_dim}")
                self.storage.register_key(obs_key, shape=tuple(self.camera_resolution), dtype=torch.float)
            elif obs_key == "context_vision_obs":
                if not self._a2_cb2h_enabled:
                    raise KeyError("context_vision_obs is only supported by the B2/B2H Student")
                expected_dim = int(np.prod(self.context_camera_resolution))
                if int(obs_dim) != expected_dim:
                    raise ValueError(
                        f"context_vision_obs dim mismatch: config={obs_dim}, expected={expected_dim}"
                    )
                self.storage.register_key(
                    obs_key, shape=tuple(self.context_camera_resolution), dtype=torch.float
                )
            elif obs_key == "camera_meta":
                if not self._a2_camera_meta_enabled:
                    raise KeyError("camera_meta is only supported by the dual-D435 Student")
                expected_meta_dim = 4 if self._a2_p2_b1_enabled else 6
                if int(obs_dim) != expected_meta_dim:
                    raise ValueError(
                        f"camera_meta dim mismatch: config={obs_dim}, expected={expected_meta_dim}"
                    )
                self.storage.register_key(obs_key, shape=(expected_meta_dim,), dtype=torch.float)
            else:
                self.storage.register_key(obs_key, shape=(int(obs_dim),), dtype=torch.float)
        self.storage.register_key("actions", shape=(A2_ROLLOUT_ACTION_DIM,), dtype=torch.float)
        self.storage.register_key("gt_actions", shape=(A2_STUDENT_ACTION_DIM,), dtype=torch.float)
        if self.learn_normalized_actions:
            raise ValueError("A2 Student normalized action storage is unsupported; use raw 12D BC actions")
        self.storage.register_key("rewards", shape=(1,), dtype=torch.float)
        self.storage.register_key("dones", shape=(1,), dtype=torch.bool)
        self.storage.register_key("time_outs", shape=(1,), dtype=torch.bool)
        self.storage.register_key("values", shape=(1,), dtype=torch.float)
        self.storage.register_key("returns", shape=(1,), dtype=torch.float)
        self.storage.register_key("advantages", shape=(1,), dtype=torch.float)
        self.storage.register_key("actions_log_prob", shape=(1,), dtype=torch.float)
        self.storage.register_key("action_mean", shape=(A2_ROLLOUT_ACTION_DIM,), dtype=torch.float)
        self.storage.register_key("action_sigma", shape=(A2_ROLLOUT_ACTION_DIM,), dtype=torch.float)
        self.state.rewbuffer = deque(maxlen=100)
        self.state.lenbuffer = deque(maxlen=100)
        self.cur_reward_sum = torch.zeros(self.env.num_envs, dtype=torch.float, device=self.accelerator.device)
        self.cur_episode_length = torch.zeros(self.env.num_envs, dtype=torch.float, device=self.accelerator.device)
        self.state.cur_reward_sum = self.cur_reward_sum
        self.state.cur_episode_length = self.cur_episode_length
        self.ep_infos = []
        self.episode_env_tensors = TensorAverageMeterDict()
        self.state.tot_timesteps = 0
        self.state.tot_time = 0
        self.state.eval_step = 0
        self.state.eval_render_step = 0

    def _validate_rollout_obs(self, obs_dict, require_teacher=True):
        required = {"actor_obs", "vision_obs", "a2_base_obs"}
        if getattr(self, "_a2_dual_d435_enabled", False):
            required.add("camera_meta")
        if getattr(self, "_a2_cb2h_enabled", False):
            required.add("context_vision_obs")
        if require_teacher:
            required.add("teacher_obs")
        missing = sorted(required.difference(obs_dict))
        if missing:
            raise KeyError(f"A2 Student rollout is missing required observation keys: {missing}")
        _validate_floating_tensor("actor_obs", obs_dict["actor_obs"], 81)
        if require_teacher:
            _validate_floating_tensor("teacher_obs", obs_dict["teacher_obs"], A2_TEACHER_OBS_DIM)
        _validate_floating_tensor("a2_base_obs", obs_dict["a2_base_obs"], A2_BASE_OBS_DIM)
        expected_device = obs_dict["actor_obs"].device
        device_keys = ["a2_base_obs"]
        if require_teacher:
            device_keys.append("teacher_obs")
        for key in device_keys:
            if obs_dict[key].device != expected_device:
                raise ValueError(f"{key} device must match actor_obs: {obs_dict[key].device} vs {expected_device}")
        if getattr(self, "value_model", None) is not None:
            if "critic_obs" not in obs_dict:
                raise KeyError("A2 Student value model requires 138D critic_obs")
            _validate_floating_tensor("critic_obs", obs_dict["critic_obs"], A2_CRITIC_OBS_DIM)
            if obs_dict["critic_obs"].device != expected_device:
                raise ValueError("critic_obs device must match actor_obs")
        vision = obs_dict["vision_obs"]
        expected_batch = obs_dict["actor_obs"].shape[0]
        if (
            not torch.is_tensor(vision)
            or vision.ndim != 4
            or vision.shape[0] != expected_batch
        ):
            raise ValueError(
                "vision_obs must be a batched NHWC tensor; "
                f"got {getattr(vision, 'shape', None)}"
            )
        if not getattr(self, "_a2_dual_d435_enabled", False) and vision.shape[-1] != 3:
            raise ValueError(
                f"vision_obs must be NHWC [N,H,W,3]; got {getattr(vision, 'shape', None)}"
            )
        if vision.device != expected_device:
            raise ValueError(f"vision_obs device must match actor_obs: {vision.device} vs {expected_device}")
        expected_resolution = getattr(self, "camera_resolution", None)
        if expected_resolution is not None and tuple(vision.shape[1:]) != tuple(expected_resolution):
            raise ValueError(
                "vision_obs shape must match the configured NHWC camera resolution: "
                f"expected={(obs_dict['actor_obs'].shape[0], *tuple(expected_resolution))}, "
                f"got={tuple(vision.shape)}"
            )
        if not torch.is_floating_point(vision) or not torch.all(torch.isfinite(vision)):
            raise ValueError("vision_obs must be a finite floating tensor")
        if getattr(self, "_a2_cb2h_enabled", False):
            context = obs_dict["context_vision_obs"]
            if (
                not torch.is_tensor(context)
                or context.ndim != 4
                or tuple(context.shape[1:]) != tuple(self.context_camera_resolution)
                or context.shape[0] != expected_batch
            ):
                raise ValueError(
                    "context_vision_obs must match configured NHWC shape "
                    f"[N,{','.join(str(x) for x in self.context_camera_resolution)}]; "
                    f"got {getattr(context, 'shape', None)}"
                )
            if (
                not torch.is_floating_point(context)
                or not torch.all(torch.isfinite(context))
                or context.device != expected_device
            ):
                raise ValueError(
                    "context_vision_obs must be finite floating data on actor_obs device"
                )
        if getattr(self, "_a2_camera_meta_enabled", False):
            camera_meta = obs_dict["camera_meta"]
            expected_meta_dim = 4 if getattr(self, "_a2_p2_b1_enabled", False) else 6
            age_dim = 2 if getattr(self, "_a2_p2_b1_enabled", False) else 3
            if (
                not torch.is_tensor(camera_meta)
                or camera_meta.ndim != 2
                or tuple(camera_meta.shape[1:]) != (expected_meta_dim,)
                or camera_meta.shape[0] != expected_batch
            ):
                raise ValueError(
                    f"camera_meta must match [N,{expected_meta_dim}]; "
                    f"got {getattr(camera_meta, 'shape', None)}"
                )
            if (
                not torch.is_floating_point(camera_meta)
                or not torch.all(torch.isfinite(camera_meta))
                or camera_meta.device != expected_device
            ):
                raise ValueError("camera_meta must be finite floating data on actor_obs device")
            if bool(torch.any(camera_meta[:, :age_dim] < 0.0).item()) or bool(
                torch.any(camera_meta[:, :age_dim] > 1.0).item()
            ):
                raise ValueError("camera_meta ages must be normalized to [0,1]")
            flags = camera_meta[:, age_dim:]
            if not torch.all((flags == 0.0) | (flags == 1.0)):
                raise ValueError("camera_meta validity flags must be exactly 0 or 1")
        if not self._a2_rgb_frame_validated:
            flattened_pixels = vision.flatten(start_dim=1)
            per_env_min = flattened_pixels.amin(dim=1)
            per_env_max = flattened_pixels.amax(dim=1)
            invalid_environments = per_env_max <= per_env_min
            if bool(invalid_environments.any().item()):
                invalid_count = int(invalid_environments.sum().item())
                first_invalid_index = int(
                    torch.nonzero(invalid_environments, as_tuple=False)[0].item()
                )
                raise ValueError(
                    "A2 Student first RGB frame contains constant/uninitialized RGB; "
                    f"invalid_count={invalid_count} "
                    f"first_invalid_environment_index={first_invalid_index}"
                )
            global_min = per_env_min.amin().item()
            global_max = per_env_max.amax().item()
            print(
                "[A2_RGB_FRAME] "
                f"shape={tuple(vision.shape)} dtype={vision.dtype} device={vision.device} "
                "finite=true per_env_nonconstant=true "
                f"global_min={global_min:.12g} global_max={global_max:.12g}",
                flush=True,
            )
            self._a2_rgb_frame_validated = True

    def _teacher_actions(self, obs_dict):
        actions = self.ref_model.act_inference(obs_dict=deepcopy(obs_dict))
        _validate_floating_tensor("teacher_actions", actions, A2_STUDENT_ACTION_DIM)
        if actions.shape[:-1] != obs_dict["teacher_obs"].shape[:-1]:
            raise ValueError("Teacher action leading shape does not match teacher_obs")
        if actions.device != obs_dict["teacher_obs"].device:
            raise ValueError("Teacher actions device must match teacher_obs")
        return actions

    def policy_step(
        self,
        policy_model,
        auxiliary_model_a,
        auxiliary_model_b,
        obs_dict,
        cur_dones=None,
        store_hidden_states=True,
        stage_tensor=None,
    ):
        if auxiliary_model_a is not None or auxiliary_model_b is not None:
            raise ValueError("A2 Student trainer does not support auxiliary policy models")
        self._validate_rollout_obs(obs_dict, require_teacher=True)
        teacher_actions = self._teacher_actions(obs_dict)
        actor_obs_dict = {"actor_obs": obs_dict["actor_obs"], "vision_obs": obs_dict["vision_obs"]}
        if getattr(self, "_a2_camera_meta_enabled", False):
            actor_obs_dict["camera_meta"] = obs_dict["camera_meta"]
        if getattr(self, "_a2_cb2h_enabled", False):
            actor_obs_dict["context_vision_obs"] = obs_dict["context_vision_obs"]
        if cur_dones is None:
            dones = self.storage.query_key("dones").to(self.accelerator.device)[: self.storage.step + 1]
            episode_attnmask = compute_episode_attnmask(dones.squeeze(-1).transpose(0, 1))
        else:
            episode_attnmask = None
        actor_hidden_states = (
            policy_model.get_hidden_states()
            if store_hidden_states and getattr(policy_model, "is_recurrent", False)
            else None
        )
        student_state = policy_model.rollout(
            obs_dict=actor_obs_dict, episode_attnmask=episode_attnmask, cur_dones=cur_dones
        )
        high_level_actions = student_state["actions"]
        high_level_mean = student_state["action_mean"]
        high_level_sigma = student_state["action_sigma"]
        _validate_floating_tensor("student_actions", high_level_actions, A2_STUDENT_ACTION_DIM)
        _validate_floating_tensor("student_action_mean", high_level_mean, A2_STUDENT_ACTION_DIM)
        _validate_floating_tensor("student_action_sigma", high_level_sigma, A2_STUDENT_ACTION_DIM)
        if any(
            tensor.device != obs_dict["actor_obs"].device
            for tensor in (high_level_actions, high_level_mean, high_level_sigma, teacher_actions)
        ):
            raise ValueError("Teacher/student action tensors must match observation device")
        if high_level_actions.shape != teacher_actions.shape:
            raise ValueError("Student and Teacher high-level action shapes differ")
        if getattr(self, "_a2_cb2h_enabled", False) or getattr(self, "_a2_p2_diagnostic_enabled", False):
            ratio = self._resolve_cb2h_rollout_phase(int(getattr(self.state, "global_step", 0)))["ratio"]
        else:
            ratio = float(self.config.get("ratio_teacher_rollout", 1.0))
        p2_diagnostic_enabled = getattr(self, "_a2_p2_diagnostic_enabled", False)
        if not getattr(self, "_a2_cb2h_enabled", False) and not p2_diagnostic_enabled:
            # Preserve the legacy A2 route exactly: fixed-prefix replacement is
            # intentionally retained outside C-B2H and no C-B2H diagnostics or
            # rollout-mask state is created.
            if not 0.0 <= ratio <= 1.0:
                raise ValueError(f"ratio_teacher_rollout must be within [0,1], got {ratio}")
            selected_high = high_level_actions
            selected_mean = high_level_mean
            if self.config.get("enforce_teacher_rollout", False):
                count = int(selected_high.shape[0] * ratio)
                selected_high = selected_high.clone()
                selected_mean = selected_mean.clone()
                selected_high[:count] = teacher_actions[:count]
                selected_mean[:count] = teacher_actions[:count]
        else:
            if stage_tensor is not None:
                self.record_stage_tensor(stage_tensor)
            stage_for_metrics = self._stage_tensor_for_policy_step(high_level_actions.shape[0])
            teacher_mask = self._ensure_cb2h_rollout_mask(
                high_level_actions.shape[0], high_level_actions.device
            )
            if teacher_mask.shape != (high_level_actions.shape[0],) or teacher_mask.dtype != torch.bool:
                raise RuntimeError("C-B2H rollout Teacher mask shape/dtype drifted")
            selected_high = torch.where(teacher_mask[:, None], teacher_actions, high_level_actions)
            selected_mean = torch.where(teacher_mask[:, None], teacher_actions, high_level_mean)
            self._record_cb2h_rollout_diagnostics(
                policy_model, high_level_mean, teacher_actions, stage_for_metrics
            )
        leg_actions = self.unwrapped_model._a2_base_actions(obs_dict, selected_high)
        if not torch.is_tensor(leg_actions) or leg_actions.device != obs_dict["actor_obs"].device:
            raise ValueError("A2_Base leg actions must be a tensor on the observation device")
        actions = compose_a2_rollout_action(selected_high, leg_actions)
        _emit_action_chain_identity(ratio)
        action_mean = compose_a2_rollout_action(selected_mean, leg_actions)
        action_sigma = compose_a2_rollout_action(high_level_sigma, torch.zeros_like(leg_actions))
        result = {
            "actions": actions,
            "action_mean": action_mean,
            "action_sigma": action_sigma,
            "actions_log_prob": policy_model.get_actions_log_prob(high_level_actions).unsqueeze(1),
            "gt_actions": teacher_actions,
        }
        if actor_hidden_states is not None:
            result["hidden_states"] = (actor_hidden_states, None)
        return result

    def _get_rollout_data(self, obs_keys):
        rollout_data = super()._get_rollout_data(obs_keys)
        if not getattr(self, "_a2_dual_d435_enabled", False):
            return rollout_data

        device = self.accelerator.device
        camera_meta = self.storage.camera_meta.transpose(0, 1).contiguous().to(device)
        rollout_data["camera_meta"] = camera_meta
        extras = [("camera_meta", camera_meta)]
        if getattr(self, "_a2_cb2h_enabled", False):
            context_vision_obs = (
                self.storage.context_vision_obs.transpose(0, 1).contiguous().to(device)
            )
            rollout_data["context_vision_obs"] = context_vision_obs
            extras.append(("context_vision_obs", context_vision_obs))

        padded_obs_dict = rollout_data.get("padded_obs_dict")
        if padded_obs_dict is not None:
            from gr00t.rl.trl.utils.rl import split_and_pad_trajectories

            dones = rollout_data["dones"]
            dones_transposed = dones.transpose(0, 1)
            trajectory_masks = rollout_data["trajectory_masks"]
            for key, obs_tensor in extras:
                padded_obs, traj_masks = split_and_pad_trajectories(
                    obs_tensor.transpose(0, 1), dones_transposed
                )
                candidate_masks = traj_masks.transpose(0, 1)
                if not torch.equal(candidate_masks, trajectory_masks):
                    raise RuntimeError(f"Trajectory mask drift while padding {key}")
                padded_obs_dict[key] = padded_obs.transpose(0, 1)
        return rollout_data

    def _get_mb_rollout_data(self, rollout_data, micro_batch_inds):
        mb_rollout_data = super()._get_mb_rollout_data(rollout_data, micro_batch_inds)
        if not getattr(self, "_a2_dual_d435_enabled", False):
            return mb_rollout_data

        mb_obs_dict = mb_rollout_data["mb_obs_dict"]
        if "camera_meta" not in mb_obs_dict:
            mb_obs_dict["camera_meta"] = rollout_data["camera_meta"][micro_batch_inds]
        if getattr(self, "_a2_cb2h_enabled", False):
            if "context_vision_obs" not in mb_obs_dict:
                mb_obs_dict["context_vision_obs"] = rollout_data["context_vision_obs"][micro_batch_inds]
            if "context_vision_obs" not in mb_obs_dict:
                raise RuntimeError("C-B2H minibatch dropped context observation keys")
        if "camera_meta" not in mb_obs_dict:
            raise RuntimeError("Dual-D435 minibatch dropped camera metadata")
        return mb_rollout_data

    def _forward_model(self, model, mb_rollout_data):
        if getattr(self, "_a2_dual_d435_enabled", False):
            obs_dict = mb_rollout_data["mb_obs_dict"]
            required = {"camera_meta"}
            if getattr(self, "_a2_cb2h_enabled", False):
                required.add("context_vision_obs")
            missing = required.difference(obs_dict)
            if missing:
                raise KeyError(f"Dual-D435 forward is missing observation keys: {sorted(missing)}")
        return super()._forward_model(model, mb_rollout_data)

    def _process_env_step(self, rewards, dones, infos):
        # Invoke only the A2 PPO student/value reset and bookkeeping path.  The
        # generic DAgger helper also resets Teacher state with a swallowed
        # exception, so it must not be called here.
        A2TRLPPOTrainer._process_env_step(self, rewards, dones, infos)
        if self.ref_model is None or not hasattr(self.ref_model, "reset"):
            raise RuntimeError("A2 recurrent Teacher must expose reset(dones)")
        self.ref_model.reset(dones)

    def _rollout_step(self, model, obs_dict):
        if self.ref_model is None or not hasattr(self.ref_model, "init_rollout"):
            raise RuntimeError("A2 recurrent Teacher must expose init_rollout()")
        if not hasattr(self.ref_model, "clear_rollout"):
            raise RuntimeError("A2 recurrent Teacher must expose clear_rollout()")
        observability_enabled = bool(
            getattr(self, "_a2_cb2h_enabled", False)
            or getattr(self, "_a2_p2_diagnostic_enabled", False)
        )
        if observability_enabled:
            self._begin_cb2h_rollout_observability()
        self.ref_model.init_rollout()
        try:
            result = A2TRLPPOTrainer._rollout_step(self, model, obs_dict)
            if observability_enabled:
                self._finish_cb2h_rollout_observability()
            return result
        finally:
            self.ref_model.clear_rollout()

    def _get_train_metrics(self):
        metrics = super()._get_train_metrics()
        metrics.update(self._build_cb2h_train_observability())
        return metrics

    def _compute_dagger_bc_loss(self, forward_results, mb_rollout_data):
        policy_results = forward_results["policy_results"]
        predicted = policy_results.get("action_mean")
        target = mb_rollout_data["mb_gt_actions"]
        _validate_floating_tensor("student BC prediction", predicted, A2_STUDENT_ACTION_DIM)
        _validate_floating_tensor("teacher BC target", target, A2_STUDENT_ACTION_DIM)
        if predicted.shape != target.shape:
            raise ValueError(f"A2 12D BC shape mismatch: {predicted.shape} vs {target.shape}")
        masks = mb_rollout_data.get("mb_masks")
        if masks is None:
            if predicted.ndim != 2:
                raise ValueError("A2 recurrent DAgger BC requires mb_masks for [B,T,12] batches")
            loss = self.bc_loss_fn(predicted.to(target.dtype), target)
            if not bool(torch.isfinite(loss).item()):
                raise RuntimeError("A2 DAgger BC loss is non-finite")
            self._a2_last_bc_loss = float(loss.detach().item())
            return {"dagger_bc_loss": loss}
        if not torch.is_tensor(masks) or masks.dtype != torch.bool:
            raise ValueError("A2 DAgger mb_masks must be a boolean tensor")
        if predicted.ndim != 3 or masks.ndim != 2 or tuple(masks.shape) != tuple(predicted.shape[:2]):
            raise ValueError(
                "A2 DAgger mb_masks must have shape [B,T] for [B,T,12] predictions; "
                f"got masks={getattr(masks, 'shape', None)}, predictions={tuple(predicted.shape)}"
            )
        if masks.device != predicted.device or masks.device != target.device:
            raise ValueError("A2 DAgger mb_masks device must match prediction and target")
        if not bool(masks.any().item()):
            raise ValueError("A2 DAgger mb_masks must contain at least one valid timestep")
        valid_predicted = predicted[masks]
        valid_target = target[masks]
        loss = self.bc_loss_fn(valid_predicted.to(valid_target.dtype), valid_target)
        if not bool(torch.isfinite(loss).item()):
            raise RuntimeError("A2 DAgger BC loss is non-finite")
        self._a2_last_bc_loss = float(loss.detach().item())
        return {"dagger_bc_loss": loss}
