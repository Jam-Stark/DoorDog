"""A2 PPO bridge for the v5.6 terminal-hold HOMIE specialist."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

import torch

from gr00t.rl.trl.modules.pull_v5_6_hold_specialist_actor import (
    FRESH_DOG_STD,
    SPECIALIST_ACTION_DIM,
    SPECIALIST_OBS_DIM,
    PullV56HoldSpecialistActor,
)
from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import TRLPPOTrainer as A2TRLPPOTrainer


PLAN_ID = "a2_piper_pull_v5_6_terminal_hold_specialist_finetune"
TRACE_SCHEMA = "a2_piper_pull_v5_6_hold_specialist_trace_v1"
HIGH_LEVEL_ACTION_DIM = 12
FROZEN_LEG_ACTION_DIM = 12
NUM_ENVS = 256
CHECKPOINT_INTERVAL = 250
PRELUDE_FAMILIES = ("near_rest", "coarse_neg", "coarse_pos", "straight_minus_x", "side_step")
# Exact executable envelope registered by the v5.5 task.  Keep this local so
# CPU-only actor/gate fixtures do not import IsaacLab/USD through the env.
REGISTERED_ADAPTER_RAW_ACTION_LOW = (-0.30, 0.0, -2.0)
REGISTERED_ADAPTER_RAW_ACTION_HIGH = (0.0, 0.24, 2.0)


def _checkpoint_step(checkpoint: str | None) -> int | None:
    if not checkpoint:
        return None
    match = re.search(r"(?:checkpoint|model_step)[_-](\d+)", str(checkpoint))
    return int(match.group(1)) if match else None


def _validate_carrier(carrier: torch.Tensor) -> None:
    if (
        not torch.is_tensor(carrier)
        or carrier.shape[-1] != HIGH_LEVEL_ACTION_DIM
        or not carrier.is_floating_point()
        or not torch.all(torch.isfinite(carrier))
    ):
        raise ValueError("v5.6 applied carrier must be finite floating 12-D tensor")
    if not torch.all(carrier[..., 3:11] == 0.0) or not torch.all(carrier[..., 11] == 1.0):
        raise ValueError("v5.6 carrier padding must be zeros/open gripper")


class PullV56HoldSpecialistPPOTrainer(A2TRLPPOTrainer):
    """Use the original JIT dog only for transit and the eager specialist in terminal phase."""

    _tag_names = ["trl", "pull_v5_6_hold_specialist"]

    def __init__(self, *args, **kwargs) -> None:
        model = kwargs.get("model")
        if model is None and len(args) >= 4:
            model = args[3]
        if not isinstance(model, PullV56HoldSpecialistActor):
            raise TypeError("v5.6 trainer requires PullV56HoldSpecialistActor")
        config = kwargs.get("config")
        if config is None and len(args) >= 2:
            config = args[1]
        if not bool(config.get("use_a2_base", False)):
            raise ValueError("v5.6 trainer requires the original A2 JIT path")
        super().__init__(*args, **kwargs)
        if self.policy_model.num_actions != SPECIALIST_ACTION_DIM:
            raise ValueError("v5.6 specialist action dimension changed during trainer setup")
        if self.a2_base_obs_dim != SPECIALIST_OBS_DIM or self.a2_base_action_dim != 12:
            raise ValueError("v5.6 trainer did not resolve the 1620-D/12-D original dog contract")

    def _setup_storage(self):
        super()._setup_storage()
        self.storage.register_key("policy_actions", shape=(SPECIALIST_ACTION_DIM,), dtype=torch.float)
        self.storage.register_key("holdtrack_phase_active", shape=(1,), dtype=torch.bool)
        self.storage.register_key("hold_specialist_active", shape=(1,), dtype=torch.bool)

    @staticmethod
    def carrier_from_goal_error(goal_error: torch.Tensor) -> torch.Tensor:
        if (
            not torch.is_tensor(goal_error)
            or goal_error.shape[-1] != 3
            or not goal_error.is_floating_point()
            or not torch.all(torch.isfinite(goal_error))
        ):
            raise ValueError("v5.6 goal error must be finite floating (ex, ey, wrapped eyaw)")
        low = goal_error.new_tensor(REGISTERED_ADAPTER_RAW_ACTION_LOW)
        high = goal_error.new_tensor(REGISTERED_ADAPTER_RAW_ACTION_HIGH)
        command = torch.clamp(goal_error, min=low, max=high)
        carrier = torch.zeros(
            *command.shape[:-1], HIGH_LEVEL_ACTION_DIM,
            dtype=command.dtype,
            device=command.device,
        )
        carrier[..., :3] = command
        carrier[..., 11] = 1.0
        _validate_carrier(carrier)
        return carrier

    @staticmethod
    def inject_carrier_into_a2_obs(
        a2_base_obs: torch.Tensor, applied_carrier: torch.Tensor
    ) -> torch.Tensor:
        if (
            not torch.is_tensor(a2_base_obs)
            or a2_base_obs.shape[-1] != SPECIALIST_OBS_DIM
            or a2_base_obs.shape[:-1] != applied_carrier.shape[:-1]
        ):
            raise ValueError("v5.6 A2 observation/carrier leading shapes must match")
        _validate_carrier(applied_carrier)
        injected = a2_base_obs.clone()
        frame_start = SPECIALIST_OBS_DIM - 54
        multipliers = applied_carrier.new_tensor((2.0, 2.0, 0.25, 1.0, 1.0))
        physical_command = torch.cat(
            (applied_carrier[..., :3] * 0.25, applied_carrier[..., 3:5].clamp(-1.0, 1.0) * 0.4),
            dim=-1,
        ) * multipliers
        injected[..., frame_start + 39 : frame_start + 44] = physical_command
        return injected

    def _original_homie_actions(self, injected_obs: torch.Tensor) -> torch.Tensor:
        if self.a2_base_model is None:
            raise RuntimeError("v5.6 specialist requires the original frozen A2 JIT model")
        with torch.no_grad():
            actions = self.a2_base_model(injected_obs)
        if tuple(actions.shape) != (*injected_obs.shape[:-1], FROZEN_LEG_ACTION_DIM):
            raise ValueError("original A2 JIT returned a non-12-D leg action")
        return actions

    @staticmethod
    def _phase_mask(env, name: str, expected_shape: torch.Size, device: torch.device) -> torch.Tensor:
        mask = getattr(env, name, None)
        if (
            not torch.is_tensor(mask)
            or mask.dtype != torch.bool
            or mask.shape != expected_shape
            or mask.device != device
        ):
            raise RuntimeError(f"v5.6 env {name} must be a device-local bool mask with shape {tuple(expected_shape)}")
        return mask.clone()

    def policy_step(
        self,
        policy_model,
        homie_walk_model,
        homie_stand_model,
        obs_dict,
        cur_dones=None,
        store_hidden_states=True,
    ):
        del homie_walk_model, homie_stand_model, cur_dones, store_hidden_states
        if "actor_obs" not in obs_dict or "a2_base_obs" not in obs_dict:
            raise KeyError("v5.6 policy_step requires actor_obs and a2_base_obs")
        carrier = self.carrier_from_goal_error(obs_dict["actor_obs"][..., :3])
        prepare = getattr(self.env, "prepare_high_level_action", None)
        if not callable(prepare):
            raise RuntimeError("v5.6 environment must expose prepare_high_level_action")
        applied_carrier = prepare(carrier.clone())
        _validate_carrier(applied_carrier)
        injected_obs = self.inject_carrier_into_a2_obs(obs_dict["a2_base_obs"], applied_carrier)
        specialist_out = policy_model.rollout(obs_dict={"actor_obs": injected_obs})
        sampled_legs = specialist_out["actions"]
        if tuple(sampled_legs.shape) != (*carrier.shape[:-1], SPECIALIST_ACTION_DIM):
            raise ValueError("v5.6 specialist rollout must return twelve sampled leg actions")
        original_legs = self._original_homie_actions(injected_obs)
        holdtrack_active = self._phase_mask(
            self.env, "_holdtrack_phase_active", carrier.shape[:-1], carrier.device
        )
        specialist_active = self._phase_mask(
            self.env, "_hold_specialist_active", carrier.shape[:-1], carrier.device
        )
        selected_legs = torch.where(specialist_active.unsqueeze(-1), sampled_legs, original_legs)
        bind = getattr(self.env, "bind_specialist_leg_action", None)
        if not callable(bind):
            raise RuntimeError("v5.6 environment must expose bind_specialist_leg_action")
        bind(selected_legs, specialist_active)
        actions_log_prob = policy_model.get_actions_log_prob(sampled_legs).unsqueeze(1)
        return {
            "actions": torch.cat((applied_carrier, selected_legs), dim=-1),
            "policy_actions": sampled_legs,
            "holdtrack_phase_active": holdtrack_active.unsqueeze(-1),
            "hold_specialist_active": specialist_active.unsqueeze(-1),
            "action_mean": torch.cat((specialist_out["action_mean"], selected_legs), dim=-1),
            "action_sigma": torch.cat(
                (specialist_out["action_sigma"], torch.zeros_like(selected_legs)), dim=-1
            ),
            "actions_log_prob": actions_log_prob,
        }

    def _get_rollout_data(self, obs_keys):
        rollout_data = super()._get_rollout_data(obs_keys)
        device = self.accelerator.device
        executed_actions = rollout_data["actions"]
        policy_actions = self.storage.query_key("policy_actions").transpose(0, 1).to(device)
        holdtrack_active = self.storage.query_key("holdtrack_phase_active").transpose(0, 1).to(device)
        specialist_active = self.storage.query_key("hold_specialist_active").transpose(0, 1).to(device)
        for name, mask in (("holdtrack_phase_active", holdtrack_active), ("hold_specialist_active", specialist_active)):
            if mask.ndim != 3 or mask.shape[-1] != 1 or mask.dtype != torch.bool:
                raise ValueError(f"v5.6 {name} storage must have bool shape [N,T,1]")
        holdtrack_active = holdtrack_active.squeeze(-1)
        specialist_active = specialist_active.squeeze(-1)
        if tuple(policy_actions.shape) != (*executed_actions.shape[:-1], SPECIALIST_ACTION_DIM):
            raise ValueError("v5.6 sampled specialist storage shape does not match rollout actions")
        if (
            holdtrack_active.shape != specialist_active.shape
            or holdtrack_active.shape != rollout_data["padding_mask"].shape
        ):
            raise ValueError("v5.6 phase masks must match PPO rollout mask shape")
        if torch.any(specialist_active & ~holdtrack_active):
            raise RuntimeError("v5.6 specialist cannot be active outside holdtrack phase")
        rollout_data["executed_actions"] = executed_actions
        rollout_data["actions"] = policy_actions
        rollout_data["holdtrack_phase_active"] = holdtrack_active
        rollout_data["hold_specialist_active"] = specialist_active
        rollout_data["padding_mask"] = rollout_data["padding_mask"] | ~specialist_active
        return rollout_data

    def _get_mb_rollout_data(self, rollout_data, micro_batch_inds):
        mb = super()._get_mb_rollout_data(rollout_data, micro_batch_inds)
        mb["mb_executed_actions"] = rollout_data["executed_actions"][micro_batch_inds]
        mb["mb_holdtrack_phase_active"] = rollout_data["holdtrack_phase_active"][micro_batch_inds]
        mb["mb_hold_specialist_active"] = rollout_data["hold_specialist_active"][micro_batch_inds]
        return mb

    def _forward_model(self, model, mb_rollout_data):
        policy_model = getattr(model, "policy", self.policy_model)
        value_model = getattr(model, "value_model", self.value_model)
        mb_obs_dict = mb_rollout_data["mb_obs_dict"]
        executed_actions = mb_rollout_data["mb_executed_actions"]
        applied_carrier = executed_actions[..., :HIGH_LEVEL_ACTION_DIM]
        injected_obs = self.inject_carrier_into_a2_obs(mb_obs_dict["a2_base_obs"], applied_carrier)
        policy_out = policy_model.act(obs_dict={"actor_obs": injected_obs}, deterministic=False)
        new_logprobs = policy_model.get_actions_log_prob(mb_rollout_data["mb_actions"])
        policy_results = {
            "logprobs": new_logprobs,
            "action_mean": policy_out["action_mean"],
            "action_std": policy_out["action_sigma"],
            "entropy": policy_out["entropy"],
        }
        value_results = value_model.evaluate(obs_dict=mb_obs_dict)
        return {"policy_results": policy_results, "value_results": value_results}

    def validate_policy_surface(self) -> dict[str, object]:
        if self.policy_model.num_actions != SPECIALIST_ACTION_DIM:
            raise ValueError("v5.6 specialist policy must expose twelve leg actions")
        return {
            "specialist_action_dim": SPECIALIST_ACTION_DIM,
            "specialist_obs_dim": SPECIALIST_OBS_DIM,
            "fresh_std": float(self.policy_model.fresh_std.mean().item()),
            "original_homie_loaded": self.a2_base_model is not None,
            "critic_initialization": "fresh_incompatible_privileged_25d_semantics",
            "optimizer_initialization": "fresh",
            "scheduler_initialization": "fresh",
        }

    @staticmethod
    def _first_episode_terminal_rows(
        step_rows: list[dict[str, object]],
        dones: torch.Tensor,
        completed: torch.Tensor,
        num_envs: int,
    ) -> list[dict[str, object]]:
        if (
            not isinstance(step_rows, list)
            or not torch.is_tensor(dones)
            or not torch.is_tensor(completed)
            or dones.ndim != 1
            or completed.ndim != 1
            or dones.shape != completed.shape
            or dones.shape[0] != num_envs
        ):
            raise ValueError("v5.6 first-episode filtering requires matching [num_envs] masks")
        accepted: list[dict[str, object]] = []
        accepted_this_step: set[int] = set()
        for row in step_rows:
            if not isinstance(row, dict):
                raise TypeError("v5.6 terminal diagnostic rows must be dictionaries")
            env_id = row.get("env_id")
            if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < num_envs:
                raise ValueError("v5.6 terminal diagnostic row has invalid env_id")
            if bool(completed[env_id].item()):
                continue
            if env_id in accepted_this_step:
                raise RuntimeError(f"duplicate v5.6 terminal row for env {env_id}")
            accepted_this_step.add(env_id)
            if not bool(dones[env_id].item()):
                raise RuntimeError(f"v5.6 terminal row for env {env_id} is not bound to returned done")
            accepted_row = dict(row)
            accepted_row["terminal_after_step"] = True
            accepted.append(accepted_row)
        return accepted

    def _bind_specialist_checkpoint_provenance(self, phase: str) -> tuple[str | None, int | None]:
        if phase == "step0":
            self.env._specialist_checkpoint = None
            self.env._specialist_checkpoint_step = None
            return None, None
        checkpoint = self.checkpoint_path or getattr(self.env, "_specialist_checkpoint", None)
        if not isinstance(checkpoint, str) or not checkpoint:
            raise RuntimeError(f"v5.6 {phase} eval requires a versioned specialist checkpoint")
        step = _checkpoint_step(checkpoint)
        if step is None:
            raise RuntimeError(f"v5.6 specialist checkpoint step is not inferable: {checkpoint}")
        self.env._specialist_checkpoint = checkpoint
        self.env._specialist_checkpoint_step = step
        return checkpoint, step

    @staticmethod
    def _annotate_terminal_row(
        row: dict[str, object],
        *,
        phase: str,
        specialist_active: bool,
        specialist_checkpoint: str | None,
        specialist_checkpoint_step: int | None,
        original_homie_checkpoint: str | None,
    ) -> dict[str, object]:
        row["schema"] = TRACE_SCHEMA
        row["plan_id"] = PLAN_ID
        row["holdtrack_phase_active"] = bool(row.get("adapter_active", False))
        row["hold_specialist_active"] = bool(specialist_active and row.get("adapter_active", False))
        row["specialist_checkpoint"] = specialist_checkpoint if row["hold_specialist_active"] else None
        row["specialist_checkpoint_step"] = specialist_checkpoint_step if row["hold_specialist_active"] else None
        row["original_homie_checkpoint"] = original_homie_checkpoint
        row["adapter_provenance"] = {
            **(row.get("adapter_provenance") if isinstance(row.get("adapter_provenance"), Mapping) else {}),
            "phase": phase,
            "specialist_phase": phase,
            "holdtrack_phase_active": row["holdtrack_phase_active"],
            "hold_specialist_active": row["hold_specialist_active"],
            "specialist_checkpoint": row["specialist_checkpoint"],
            "specialist_checkpoint_step": row["specialist_checkpoint_step"],
            "original_homie_checkpoint": original_homie_checkpoint,
        }
        return row

    def eval(self):
        self._eval_mode()
        self.policy_model.eval_mode()
        self.policy_model.init_rollout()
        obs_dict = self.env.reset_all()
        device = self.accelerator.device
        obs_dict = {key: value.to(device) for key, value in obs_dict.items()}
        dones = torch.zeros(self.env.num_envs, device=device, dtype=torch.bool)
        completed = torch.zeros_like(dones)
        accepted_env_ids: set[int] = set()
        rows: list[dict[str, object]] = []
        adapter_config = getattr(self.env, "_adapter_config", self.env.config)
        if not isinstance(adapter_config, Mapping):
            raise TypeError("v5.6 eval requires a mapping adapter config")
        phase = str(getattr(self.env, "_adapter_probe_phase", "train"))
        specialist_active = bool(getattr(self.env, "_hold_specialist_enabled", True)) and phase != "step0"
        specialist_checkpoint, specialist_checkpoint_step = self._bind_specialist_checkpoint_provenance(phase)
        original_homie_checkpoint = getattr(self.env, "_original_homie_checkpoint", None)
        max_steps = int(adapter_config.get("adapter_eval_max_steps", 600))
        for _ in range(max_steps):
            if bool(torch.all(completed).item()):
                break
            state = self.policy_step(self.policy_model, None, None, obs_dict, cur_dones=dones, store_hidden_states=False)
            obs_dict, _, dones_raw, _ = self.env.step({"actions": state["actions"]})
            dones = dones_raw.reshape(-1).to(device=device, dtype=torch.bool)
            consume = getattr(self.env, "consume_a2_terminal_diagnostics", None)
            if not callable(consume):
                raise RuntimeError("v5.6 eval requires env terminal diagnostics")
            step_rows = self._first_episode_terminal_rows(consume(), dones, completed, self.env.num_envs)
            for row in step_rows:
                env_id = int(row["env_id"])
                if env_id in accepted_env_ids:
                    raise RuntimeError(f"duplicate v5.6 first-episode terminal row for env {env_id}")
                accepted_env_ids.add(env_id)
                rows.append(
                    self._annotate_terminal_row(
                        row,
                        phase=phase,
                        specialist_active=specialist_active,
                        specialist_checkpoint=specialist_checkpoint,
                        specialist_checkpoint_step=specialist_checkpoint_step,
                        original_homie_checkpoint=original_homie_checkpoint,
                    )
                )
            completed |= dones
            obs_dict = {key: value.to(device) for key, value in obs_dict.items()}
        if not bool(torch.all(completed).item()):
            raise RuntimeError("v5.6 eval exceeded horizon before all episodes returned done")
        if len(rows) != self.env.num_envs or accepted_env_ids != set(range(self.env.num_envs)):
            raise RuntimeError(
                f"v5.6 {phase} eval requires exactly one first-episode row per env; "
                f"got {len(rows)} rows for {self.env.num_envs} envs"
            )
        output_dir_raw = getattr(self.args, "eval_output_dir", None) or getattr(self.args, "output_dir", None)
        if not isinstance(output_dir_raw, str) or not output_dir_raw:
            raise ValueError("v5.6 eval requires args.eval_output_dir or args.output_dir")
        output_dir = Path(output_dir_raw)
        output_dir.mkdir(parents=True, exist_ok=True)
        family_row_counts = {family: 0 for family in PRELUDE_FAMILIES}
        family_done_counts = {family: 0 for family in PRELUDE_FAMILIES}
        for row in rows:
            family = row.get("family")
            if family in family_row_counts:
                family_row_counts[family] += 1
                family_done_counts[family] += int(row.get("done") is True)
        if phase == "step0":
            filename = "STEP0_GATE.json"
            schema = "a2_piper_pull_v5_6_specialist_step0_gate_v1"
        elif phase == "training_gate":
            filename = "TRAINING_GATE.json"
            schema = "a2_piper_pull_v5_6_specialist_training_gate_v1"
        elif phase == "rehearsal":
            filename = "REHEARSAL.json"
            schema = "a2_piper_pull_v5_6_specialist_rehearsal_cell_v1"
        elif phase == "anchor":
            filename = "ANCHOR.json"
            schema = "a2_piper_pull_v5_6_specialist_anchor_cell_v1"
        else:
            filename = "SPECIALIST_EVAL.json"
            schema = f"a2_piper_pull_v5_6_{phase}_v1"
        target_yaw = adapter_config.get("adapter_rehearsal_yaw_delta_rad")
        target_xy = adapter_config.get("adapter_rehearsal_xy_delta_m")
        sequence = adapter_config.get("adapter_anchor_sequence")
        status = "PASS" if (phase == "step0" or all(row.get("done") is True for row in rows)) else "FAIL"
        target = output_dir / filename
        if target.exists():
            raise FileExistsError(f"refusing to overwrite v5.6 eval receipt: {target}")
        payload = {
            "schema": schema,
            "plan_id": PLAN_ID,
            "status": status,
            "rows": rows,
            "scientific_denominator_included": False,
            "denominator_scope": "none",
            "phase": phase,
            "mode": "original_jit_gain1_carrier" if phase == "step0" else "specialist_terminal_hold",
            "specialist_active": specialist_active,
            "hold_specialist_active": specialist_active,
            "family_row_counts": family_row_counts,
            "family_done_counts": family_done_counts,
            "training_gate_registered_full": phase in {"step0", "training_gate"},
            "full_source": all(row.get("adapter_target_source") == "training_gate_registered_full" for row in rows) if phase in {"step0", "training_gate"} else None,
            "capability_count": sum(family_done_counts.values()) if phase in {"step0", "training_gate"} else None,
            "invariant12_prime": {
                "status": "PASS",
                "phase": phase,
                "specialist_active": specialist_active,
                "checked_rows": len(rows),
                "downstream_required": phase in {"P3", "P4", "canonical_DV", "natural_DV"},
            },
            "rehearsal_target": {"yaw_delta_rad": target_yaw, "xy_delta_m": target_xy} if phase == "rehearsal" else None,
            "anchor_sequence": sequence if phase == "anchor" else None,
            "original_homie_checkpoint": getattr(self.env, "_original_homie_checkpoint", None),
            "specialist_checkpoint": specialist_checkpoint,
            "specialist_checkpoint_step": specialist_checkpoint_step,
        }
        target.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        self.policy_model.clear_rollout()
        return payload


PullV5_6HoldSpecialistPPOTrainer = PullV56HoldSpecialistPPOTrainer
TRLPPOTrainer = PullV56HoldSpecialistPPOTrainer


__all__ = [
    "PLAN_ID",
    "PullV56HoldSpecialistPPOTrainer",
    "PullV5_6HoldSpecialistPPOTrainer",
    "TRLPPOTrainer",
]
