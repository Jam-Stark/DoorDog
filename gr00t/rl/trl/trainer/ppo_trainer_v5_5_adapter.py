"""Executable v5.5 adapter trainer built on the repository A2 PPO lifecycle."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

import torch

from gr00t.rl.trl.modules.pull_v5_5_adapter_actor import (
    ADAPTER_ACTION_DIM,
    ADAPTER_OBS_DIM,
    FROZEN_LEG_ACTION_DIM,
    HIGH_LEVEL_ACTION_DIM,
    PullV55AdapterActor,
)
from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import TRLPPOTrainer as A2TRLPPOTrainer


PLAN_ID = "a2_piper_pull_v5_5_residual_terminal_hold_adapter"
TRAINING_RECORD_CLASS = "interface_characterization"
SCIENTIFIC_DENOMINATOR_INCLUDED = False
MAX_BATCHES = 750
CHECKPOINT_INTERVAL = 250
NUM_ENVS = 256
GATE_FAMILY_COUNT = 5
GATE_EPISODES_PER_FAMILY = 16
GATE_MIN_PER_FAMILY = 15
GATE_MIN_OVERALL = 77


def validate_adapter_action_tensor(actions: torch.Tensor) -> None:
    if not torch.is_tensor(actions) or actions.shape[-1] != HIGH_LEVEL_ACTION_DIM:
        raise ValueError("adapter carrier actions must have exactly twelve values")
    if not actions.is_floating_point() or not torch.all(torch.isfinite(actions)):
        raise ValueError("adapter carrier actions must be finite floating point")
    if not torch.all(actions[..., 3:11] == 0.0) or not torch.all(actions[..., 11] == 1.0):
        raise ValueError("adapter carrier padded axes must be deterministic zeros/open-gripper")


def validate_adapter_observation_tensor(observations: torch.Tensor) -> None:
    if not torch.is_tensor(observations) or observations.shape[-1] != ADAPTER_OBS_DIM:
        raise ValueError("PPO adapter observations must have exactly twelve features")
    if not observations.is_floating_point() or not torch.all(torch.isfinite(observations)):
        raise ValueError("PPO adapter observations must be finite floating point")


def adapter_contract_receipt(
    *,
    checkpoint: str | None,
    reward_scales: Mapping[str, float],
    action_bounds: Mapping[str, tuple[float, float]],
    from_scratch: bool = True,
) -> dict[str, object]:
    required_rewards = {
        "adapter_dense_error",
        "adapter_in_tolerance",
        "adapter_hold_progress",
        "adapter_done",
        "penalty_adapter_action_delta",
    }
    if set(reward_scales) != required_rewards:
        raise ValueError(f"adapter reward scales must be exactly {sorted(required_rewards)}")
    if "adapter_magnitude" in reward_scales or "penalty_adapter_action_magnitude" in reward_scales:
        raise ValueError("adapter reward contract must not penalize action magnitude")
    if float(reward_scales["adapter_dense_error"]) <= 0.0:
        raise ValueError("adapter_dense_error is already negative raw error; its scale must be positive")
    if set(action_bounds) != {"x", "y", "yaw"}:
        raise ValueError("adapter action bounds must identify x, y, and yaw")
    if from_scratch and checkpoint not in (None, ""):
        raise ValueError("from-scratch T1 adapter training must not load an actor checkpoint")
    return {
        "schema": "a2_piper_pull_v5_5_adapter_training_contract_v1",
        "plan_id": PLAN_ID,
        "record_class": TRAINING_RECORD_CLASS,
        "scientific_denominator_included": SCIENTIFIC_DENOMINATOR_INCLUDED,
        "denominator_scope": "none",
        "obs_dim": ADAPTER_OBS_DIM,
        "trainable_action_dim": ADAPTER_ACTION_DIM,
        "high_level_carrier_dim": HIGH_LEVEL_ACTION_DIM,
        "frozen_leg_action_dim": 12,
        "from_scratch": bool(from_scratch),
        "checkpoint": None if checkpoint in (None, "") else str(checkpoint),
        "reward_scales": {key: float(value) for key, value in reward_scales.items()},
        "action_bounds": {
            key: {"low": float(bounds[0]), "high": float(bounds[1])}
            for key, bounds in action_bounds.items()
        },
        "padded_axes_stochastic": False,
        "frozen_a2_base_no_grad": True,
    }


class PullV55AdapterPPOTrainer(A2TRLPPOTrainer):
    """A2 trainer specialization that inserts the adapter FSM before leg inference."""

    _tag_names = ["trl", "pull_v5_5_adapter"]

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
        checkpoint_load_mode="full",
        local_seed=None,
        schedule_dict=None,
        accelerator=None,
        workflow_config=None,
    ) -> None:
        if not isinstance(model, PullV55AdapterActor):
            raise TypeError("v5.5 trainer requires PullV55AdapterActor")
        if model.num_actions != HIGH_LEVEL_ACTION_DIM:
            raise ValueError("v5.5 trainer requires the canonical 12-D policy carrier")
        if not bool(config.get("use_a2_base", False)):
            raise ValueError("v5.5 trainer requires algo.config.use_a2_base=true")
        env_config = getattr(env, "config", None)
        if not isinstance(env_config, Mapping):
            raise TypeError("v5.5 trainer requires a mapping env.config")
        if checkpoint is not None and checkpoint_load_mode not in ("full", None):
            raise ValueError("v5.5 eval checkpoints use the inherited full trainer load path")
        workflow_config_for_base = config if workflow_config is None else workflow_config
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
            checkpoint_load_mode=checkpoint_load_mode,
            local_seed=local_seed,
            schedule_dict=schedule_dict,
            accelerator=accelerator,
            workflow_config=workflow_config_for_base,
        )
        if self.policy_model.num_actions != HIGH_LEVEL_ACTION_DIM:
            raise ValueError("v5.5 policy carrier dim changed during A2 trainer setup")
        if self.a2_base_obs_dim != 1620 or self.a2_base_action_dim != 12:
            raise ValueError("v5.5 A2_Base loader did not resolve the 1620/12 contract")

    def validate_policy_surface(self) -> dict[str, object]:
        if self.policy_model.num_actions != HIGH_LEVEL_ACTION_DIM:
            raise ValueError("adapter policy must expose twelve carrier actions")
        trainable = [name for name, parameter in self.policy_model.named_parameters() if parameter.requires_grad]
        return {
            "trainable_action_dim": ADAPTER_ACTION_DIM,
            "carrier_action_dim": HIGH_LEVEL_ACTION_DIM,
            "trainable_parameter_names": trainable,
            "padded_carrier_axes_stochastic": False,
            "a2_base_no_grad": all(not parameter.requires_grad for parameter in self.a2_base_model.parameters()),
        }

    def _setup_storage(self):
        super()._setup_storage()
        self.storage.register_key(
            "policy_actions", shape=(HIGH_LEVEL_ACTION_DIM,), dtype=torch.float
        )
        self.storage.register_key("adapter_active", shape=(1,), dtype=torch.bool)

    def _capture_adapter_active(self, sampled_carrier: torch.Tensor) -> torch.Tensor:
        active = getattr(self.env, "_adapter_active", None)
        if (
            not torch.is_tensor(active)
            or active.dtype != torch.bool
            or active.shape != sampled_carrier.shape[:-1]
            or active.device != sampled_carrier.device
        ):
            shape = None if not torch.is_tensor(active) else tuple(active.shape)
            dtype = None if not torch.is_tensor(active) else active.dtype
            device = None if not torch.is_tensor(active) else active.device
            raise RuntimeError(
                "v5.5 env adapter-active provenance must be a bool tensor matching the sampled "
                f"carrier leading shape/device; got shape={shape}, dtype={dtype}, device={device}, "
                f"expected shape={tuple(sampled_carrier.shape[:-1])}, device={sampled_carrier.device}"
            )
        return active.unsqueeze(-1)

    def policy_step(
        self,
        policy_model,
        homie_walk_model,
        homie_stand_model,
        obs_dict,
        cur_dones=None,
        store_hidden_states=True,
    ):
        del homie_walk_model, homie_stand_model, store_hidden_states
        policy_out = policy_model.rollout(obs_dict=obs_dict, cur_dones=cur_dones)
        sampled_carrier = policy_out["actions"]
        validate_adapter_action_tensor(sampled_carrier)
        prepare = getattr(self.env, "prepare_high_level_action", None)
        if prepare is None:
            raise RuntimeError("v5.5 training requires the env prelude/handoff carrier hook")
        applied_carrier = prepare(sampled_carrier.clone())
        if not torch.is_tensor(applied_carrier) or applied_carrier.shape != sampled_carrier.shape:
            raise ValueError(
                "v5.5 env applied carrier must preserve the sampled carrier shape; "
                f"got applied={None if not torch.is_tensor(applied_carrier) else tuple(applied_carrier.shape)}, "
                f"sampled={tuple(sampled_carrier.shape)}"
            )
        validate_adapter_action_tensor(applied_carrier)
        adapter_active = self._capture_adapter_active(sampled_carrier)
        a2_actions = self.unwrapped_model._a2_base_actions(obs_dict, applied_carrier)
        actions_log_prob = policy_model.get_actions_log_prob(actions=sampled_carrier).unsqueeze(1)
        return {
            "actions": torch.cat([applied_carrier, a2_actions], dim=-1),
            "policy_actions": sampled_carrier,
            "adapter_active": adapter_active,
            "action_mean": torch.cat([policy_out["action_mean"], a2_actions], dim=-1),
            "action_sigma": torch.cat([policy_out["action_sigma"], torch.full_like(a2_actions, self.a2_base_action_sigma)], dim=-1),
            "actions_log_prob": actions_log_prob,
        }

    @staticmethod
    def _merge_policy_and_executed_actions(
        executed_actions: torch.Tensor, policy_actions: torch.Tensor
    ) -> torch.Tensor:
        if not torch.is_tensor(executed_actions) or not torch.is_tensor(policy_actions):
            raise TypeError("v5.5 rollout action provenance requires tensor actions")
        expected_policy_shape = (*executed_actions.shape[:-1], HIGH_LEVEL_ACTION_DIM)
        if tuple(policy_actions.shape) != expected_policy_shape:
            raise ValueError(
                "v5.5 policy-action provenance shape mismatch: "
                f"got executed={tuple(executed_actions.shape)}, policy={tuple(policy_actions.shape)}; "
                f"expected policy={expected_policy_shape}"
            )
        expected_executed_dim = HIGH_LEVEL_ACTION_DIM + FROZEN_LEG_ACTION_DIM
        if executed_actions.shape[-1] != expected_executed_dim:
            raise ValueError(
                "v5.5 executed action must contain the 12-D applied carrier and 12-D frozen legs; "
                f"got {executed_actions.shape[-1]} values"
            )
        return torch.cat(
            (policy_actions, executed_actions[..., HIGH_LEVEL_ACTION_DIM:]), dim=-1
        )

    def _get_rollout_data(self, obs_keys):
        rollout_data = super()._get_rollout_data(obs_keys)
        device = self.accelerator.device
        executed_actions = rollout_data["actions"]
        policy_actions = self.storage.query_key("policy_actions").transpose(0, 1).to(device)
        adapter_active = self.storage.query_key("adapter_active").transpose(0, 1).to(device)
        if adapter_active.ndim != 3 or adapter_active.shape[-1] != 1:
            raise ValueError(
                "v5.5 adapter-active rollout storage must have shape [num_envs, num_steps, 1]; "
                f"got {tuple(adapter_active.shape)}"
            )
        if adapter_active.dtype != torch.bool:
            raise TypeError("v5.5 adapter-active rollout storage must use bool dtype")
        adapter_active = adapter_active.squeeze(-1)
        if rollout_data["padding_mask"].shape != adapter_active.shape:
            raise ValueError(
                "v5.5 adapter-active mask must match PPO padding-mask shape; "
                f"got active={tuple(adapter_active.shape)}, padding={tuple(rollout_data['padding_mask'].shape)}"
            )
        if rollout_data["padding_mask"].dtype != torch.bool:
            raise TypeError("v5.5 PPO padding mask must use bool dtype")
        rollout_data["actions"] = self._merge_policy_and_executed_actions(
            executed_actions, policy_actions
        )
        rollout_data["adapter_active"] = adapter_active
        rollout_data["padding_mask"] = rollout_data["padding_mask"] | ~adapter_active
        return rollout_data

    @staticmethod
    def _checkpoint_step(checkpoint: str | None) -> int | None:
        if not checkpoint:
            return None
        match = re.search(r"(?:checkpoint|model_step)[_-](\d+)", str(checkpoint))
        return int(match.group(1)) if match else None

    def _bind_checkpoint_provenance(self) -> None:
        checkpoint = self.checkpoint_path
        if checkpoint is None:
            return
        if hasattr(self.env, "_adapter_checkpoint"):
            self.env._adapter_checkpoint = checkpoint
            self.env._adapter_checkpoint_step = self._checkpoint_step(checkpoint)

    def _write_adapter_eval_receipt(self, rows: list[dict[str, object]]) -> dict[str, object]:
        adapter_config = getattr(self.env, "_adapter_config", self.env.config)
        if not isinstance(adapter_config, Mapping):
            raise TypeError("v5.5 eval requires a mapping adapter config")
        phase = str(adapter_config.get("adapter_probe_phase", "train"))
        output_dir_raw = getattr(self.args, "eval_output_dir", None) or getattr(self.args, "output_dir", None)
        if not isinstance(output_dir_raw, str) or not output_dir_raw:
            raise ValueError("adapter eval requires args.eval_output_dir or args.output_dir")
        output_dir = Path(output_dir_raw)
        output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = self.checkpoint_path
        step = self._checkpoint_step(checkpoint)

        def active_row(row: dict[str, object]) -> dict[str, object]:
            if row.get("adapter_active") is True:
                if not isinstance(row.get("adapter_checkpoint"), str) or not row["adapter_checkpoint"]:
                    row["adapter_checkpoint"] = checkpoint
                if row.get("adapter_checkpoint_step") is None:
                    row["adapter_checkpoint_step"] = step
            return row

        rows = [active_row(dict(row)) for row in rows]
        if phase == "training_gate":
            from scriptsFORhuman.pull_v5.pull_v5_5_adapter_gates import PRELUDE_FAMILIES, training_gate_pass

            totals = {family: 0 for family in PRELUDE_FAMILIES}
            done_counts = {family: 0 for family in PRELUDE_FAMILIES}
            for row in rows:
                family = row.get("family")
                if family in totals:
                    totals[family] += 1
                    done_counts[family] += int(row.get("done") is True)
            payload = {
                "schema": "a2_piper_pull_v5_5_adapter_training_gate_v1",
                "plan_id": PLAN_ID,
                "status": "PASS" if totals == {family: 16 for family in PRELUDE_FAMILIES} and training_gate_pass(done_counts) else "FAIL",
                "rows": rows,
                "family_row_counts": totals,
                "family_done_counts": done_counts,
                "checkpoint": checkpoint,
                "checkpoint_step": step,
                "scientific_denominator_included": False,
                "denominator_scope": "none",
            }
            target = output_dir / "TRAINING_GATE.json"
        elif phase == "rehearsal":
            target_yaw = float(adapter_config.get("adapter_rehearsal_yaw_delta_rad"))
            target_xy = float(adapter_config.get("adapter_rehearsal_xy_delta_m"))
            payload = {
                "schema": "a2_piper_pull_v5_5_adapter_rehearsal_v1",
                "plan_id": PLAN_ID,
                "status": "PASS" if len(rows) == 8 and all(row.get("done") is True for row in rows) else "FAIL",
                "cells": [{"yaw_delta_rad": target_yaw, "xy_delta_m": target_xy, "rows": rows}],
                "checkpoint": checkpoint,
                "checkpoint_step": step,
            }
            target = output_dir / "REHEARSAL.json"
        elif phase == "anchor":
            from gr00t.rl.envs.base_task.pull_v5_5_adapter_holdtrack import (
                ADAPTER_ANCHOR_SCOPE,
                FORMAL_T3_ANCHOR_ADMISSION,
            )

            sequence = str(adapter_config.get("adapter_anchor_sequence"))
            pass_sequence = len(rows) == 16 and all(row.get("done") is True for row in rows)
            payload = {
                "schema": "a2_piper_pull_v5_5_adapter_anchor_v1",
                "plan_id": PLAN_ID,
                "status": "CHARACTERIZATION_ONLY" if pass_sequence else "FAIL",
                "anchor_scope": ADAPTER_ANCHOR_SCOPE,
                "formal_t3_anchor_admission": FORMAL_T3_ANCHOR_ADMISSION,
                "anchor_targets_authoritative": False,
                "attempts": [{
                    "attempt": int(adapter_config.get("adapter_anchor_attempt", 0)),
                    "status": "CHARACTERIZATION_ONLY" if pass_sequence else "FAIL",
                    "admitted_sequences": [sequence] if pass_sequence else [],
                    "rows": rows,
                }],
                "checkpoint": checkpoint,
                "checkpoint_step": step,
            }
            target = output_dir / "ANCHOR.json"
        else:
            payload = {"schema": "a2_piper_pull_v5_5_adapter_eval_v1", "plan_id": PLAN_ID, "status": "PASS", "rows": rows}
            target = output_dir / "ADAPTER_EVAL.json"
        if target.exists():
            raise FileExistsError(f"adapter evaluation refuses to overwrite {target}")
        target.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        return payload

    @staticmethod
    def _first_episode_terminal_rows(
        step_rows: list[dict[str, object]],
        dones: torch.Tensor,
        completed: torch.Tensor,
        num_envs: int,
    ) -> list[dict[str, object]]:
        if not isinstance(step_rows, list):
            raise TypeError("adapter terminal diagnostics must be a list")
        if (
            not torch.is_tensor(dones)
            or not torch.is_tensor(completed)
            or dones.ndim != 1
            or completed.ndim != 1
            or dones.shape != completed.shape
            or dones.shape[0] != num_envs
        ):
            raise ValueError("adapter first-episode filtering requires matching [num_envs] masks")
        accepted: list[dict[str, object]] = []
        accepted_this_step: set[int] = set()
        for row in step_rows:
            if not isinstance(row, dict):
                raise TypeError("adapter terminal diagnostic rows must be dictionaries")
            env_id = row.get("env_id")
            if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < num_envs:
                raise ValueError("v5.5 terminal diagnostic row has invalid env_id")
            if bool(completed[env_id].item()):
                continue
            if env_id in accepted_this_step:
                raise RuntimeError(f"duplicate first-episode terminal row for env {env_id}")
            if not bool(dones[env_id].item()):
                raise RuntimeError(
                    f"terminal diagnostic row for env {env_id} is not bound to returned done"
                )
            accepted_this_step.add(env_id)
            accepted_row = dict(row)
            accepted_row["terminal_after_step"] = True
            accepted.append(accepted_row)
        return accepted

    def eval(self):
        self._bind_checkpoint_provenance()
        self._eval_mode()
        self.policy_model.eval_mode()
        self.policy_model.init_rollout()
        obs_dict = self.env.reset_all()
        device = self.accelerator.device
        obs_dict = {key: value.to(device) for key, value in obs_dict.items()}
        dones = torch.zeros(self.env.num_envs, device=device, dtype=torch.bool)
        completed = torch.zeros(self.env.num_envs, device=device, dtype=torch.bool)
        rows: list[dict[str, object]] = []
        adapter_config = getattr(self.env, "_adapter_config", self.env.config)
        if not isinstance(adapter_config, Mapping):
            raise TypeError("v5.5 eval requires a mapping adapter config")
        max_steps = int(adapter_config.get("adapter_eval_max_steps", 600))
        for _ in range(max_steps):
            if bool(torch.all(completed).item()):
                break
            state = self.policy_step(
                self.policy_model,
                self.homie_walk_model,
                self.homie_stand_model,
                obs_dict,
                cur_dones=dones,
                store_hidden_states=False,
            )
            obs_dict, _, dones_raw, _ = self.env.step({"actions": state["actions"]})
            dones = dones_raw.reshape(-1).to(device=device, dtype=torch.bool)
            consume = getattr(self.env, "consume_a2_terminal_diagnostics", None)
            if consume is None:
                raise RuntimeError("v5.5 eval requires env.consume_a2_terminal_diagnostics")
            step_rows = consume()
            rows.extend(
                self._first_episode_terminal_rows(
                    step_rows, dones, completed, self.env.num_envs
                )
            )
            completed |= dones
            obs_dict = {key: value.to(device) for key, value in obs_dict.items()}
        if not bool(torch.all(completed).item()):
            raise RuntimeError("v5.5 eval exceeded adapter horizon before every first episode returned done")
        row_env_ids = [row.get("env_id") for row in rows]
        if len(rows) != self.env.num_envs or set(row_env_ids) != set(range(self.env.num_envs)):
            raise RuntimeError("v5.5 eval must produce exactly one first-episode terminal row per env")
        self.policy_model.clear_rollout()
        return self._write_adapter_eval_receipt(rows)


PullV5_5AdapterPPOTrainer = PullV55AdapterPPOTrainer
TRLPPOTrainer = PullV55AdapterPPOTrainer


__all__ = [
    "PLAN_ID",
    "PullV55AdapterPPOTrainer",
    "PullV5_5AdapterPPOTrainer",
    "TRLPPOTrainer",
    "adapter_contract_receipt",
    "validate_adapter_action_tensor",
    "validate_adapter_observation_tensor",
]
