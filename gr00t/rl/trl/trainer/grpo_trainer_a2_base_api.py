# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import gc
import json
import math
from pathlib import Path
import time

import torch

from gr00t.rl.agents.modules.data_utils import RolloutStorage
from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import TRLPPOTrainer


class GRPOTrainerA2BaseAPI(TRLPPOTrainer):
    """Actor-only recurrent GRPO for the frozen-encoder A2 vision Student."""

    def __init__(self, *args, model=None, config=None, **kwargs):
        if model is None or config is None:
            raise ValueError("GRPO trainer requires explicit model and config")
        if not hasattr(model, "core") or not hasattr(model, "head_vision_module"):
            raise TypeError("GRPO requires the dual-D435 + Head recurrent Student actor")
        if config.get("use_dagger", False):
            raise ValueError("GRPO must not construct the DAgger Teacher pipeline")
        if not config.get("distill_only", False):
            raise ValueError("GRPO actor-only setup requires distill_only=true")
        if config.get("freeze_noise_std") is not True:
            raise ValueError("GRPO v0 requires freeze_noise_std=true")

        for parameter in model.parameters():
            parameter.requires_grad_(False)
        for module in (model.core.memory, model.core.mlp_module):
            for parameter in module.parameters():
                parameter.requires_grad_(True)

        super().__init__(*args, model=model, config=config, **kwargs)

        self.exploration_std = float(config.grpo_exploration_std)
        if not 0.0 < self.exploration_std <= float(config.max_noise_std):
            raise ValueError(
                "grpo_exploration_std must be positive and no larger than max_noise_std"
            )
        with torch.no_grad():
            self.policy_model.core.std.fill_(self.exploration_std)
        self.policy_model.core.std.requires_grad_(False)

        self.action_rate_lambda = float(config.grpo_action_rate_lambda)
        if self.action_rate_lambda < 0.0:
            raise ValueError("grpo_action_rate_lambda must be non-negative")
        self.rollout_chunk_length = int(config.grpo_rollout_chunk_length)
        if self.rollout_chunk_length <= 0:
            raise ValueError("grpo_rollout_chunk_length must be positive")
        self.zero_variance_threshold = float(config.grpo_zero_variance_threshold)
        self.first_update_ratio_tolerance = float(config.grpo_first_update_ratio_tolerance)
        self.max_learning_rate = float(self.args.learning_rate)
        self.min_learning_rate = self.max_learning_rate / 100.0
        self._zero_variance_groups = 0
        self._rollout_started = False
        self._last_rollout_actions = None
        self._metrics_path = Path(self.args.output_dir) / "metrics.jsonl"
        self._enforce_frozen_encoder_eval()

    def _setup_storage(self):
        self.num_steps_per_env = int(self.config.grpo_rollout_horizon)
        if self.num_steps_per_env <= 0:
            raise ValueError("grpo_rollout_horizon must be positive")
        if int(self.config.num_steps_per_env) != self.num_steps_per_env:
            raise ValueError("num_steps_per_env must equal grpo_rollout_horizon")
        actor_obs_dim = int(self.algo_obs_dim_dict["actor_obs"])
        latent_dim = int(self.config.grpo_latent_dim)
        action_dim = int(self.policy_model.num_actions)
        self.storage = RolloutStorage(
            self.env.num_envs,
            self.num_steps_per_env,
            device=self.accelerator.device,
        )
        self.storage.register_key("actor_obs", shape=(actor_obs_dim,), dtype=torch.float)
        self.storage.register_key("latent", shape=(latent_dim,), dtype=torch.float)
        self.storage.register_key("actions", shape=(action_dim,), dtype=torch.float)
        self.storage.register_key("actions_log_prob", shape=(1,), dtype=torch.float)
        self.storage.register_key("action_mean", shape=(action_dim,), dtype=torch.float)
        self.storage.register_key("action_sigma", shape=(action_dim,), dtype=torch.float)
        self.storage.register_key("dones", shape=(1,), dtype=torch.bool)
        self.storage.register_key("valid", shape=(1,), dtype=torch.bool)
        self.storage.register_key("advantages", shape=(1,), dtype=torch.float)

        self.state.rewbuffer = []
        self.state.lenbuffer = []
        self.state.tot_timesteps = 0
        self.state.tot_time = 0.0
        self.state.eval_step = 0
        self.state.eval_render_step = 0

    def _enforce_frozen_encoder_eval(self):
        policy = self.accelerator.unwrap_model(self.model).policy
        policy.core.d435i_vision_module.eval()
        policy.head_vision_module.eval()
        if policy.core.running_mean_std is not None:
            policy.core.running_mean_std.eval()

    def _train_rollout_mode(self):
        super()._train_rollout_mode()
        self._enforce_frozen_encoder_eval()

    def _train_mode(self):
        super()._train_mode()
        self._enforce_frozen_encoder_eval()

    def _eval_mode(self):
        super()._eval_mode()
        self._enforce_frozen_encoder_eval()

    def _reset_iteration(self):
        if not self._rollout_started:
            obs_dict, _ = self.env.reset()
            self._rollout_started = True
        else:
            self.env.episode_length_buf[:] = self.env.max_episode_length + 1
            obs_dict, _, dones, _ = self.env.step(
                {"actions": self._last_rollout_actions}
            )
            if not bool(dones.all().item()):
                raise RuntimeError("GRPO synchronized timeout did not reset every environment")
        obs_dict = {
            key: value.to(self.accelerator.device)
            for key, value in obs_dict.items()
        }
        policy = self.accelerator.unwrap_model(self.model).policy
        policy.core.memory.reset()
        policy.init_rollout()
        self.storage.clear()
        self.storage.valid.zero_()
        self.storage.dones.zero_()
        self.storage.advantages.zero_()
        return obs_dict

    def _collect_rollouts(self):
        self._train_rollout_mode()
        device = self.accelerator.device
        wrapper = self.accelerator.unwrap_model(self.model)
        policy = wrapper.policy
        obs_dict = self._reset_iteration()

        active = torch.ones(self.env.num_envs, dtype=torch.bool, device=device)
        successes = torch.zeros(self.env.num_envs, dtype=torch.bool, device=device)
        lengths = torch.zeros(self.env.num_envs, dtype=torch.long, device=device)
        previous_dones = torch.zeros(self.env.num_envs, dtype=torch.bool, device=device)

        with torch.no_grad():
            for step in range(self.num_steps_per_env):
                hidden_states = policy.get_hidden_states()
                policy_out = policy.rollout_with_latent(
                    obs_dict=obs_dict,
                    cur_dones=previous_dones,
                )
                high_level_actions = policy_out["actions"]
                a2_actions = wrapper._a2_base_actions(obs_dict, high_level_actions)
                rollout_actions = torch.cat((high_level_actions, a2_actions), dim=-1)
                old_log_prob = policy.get_actions_log_prob(high_level_actions).unsqueeze(-1)

                self.storage.update_key("actor_obs", obs_dict[policy.input_key])
                self.storage.update_key("latent", policy_out["latent"])
                self.storage.update_key("actions", high_level_actions)
                self.storage.update_key("actions_log_prob", old_log_prob)
                self.storage.update_key("action_mean", policy_out["action_mean"])
                self.storage.update_key("action_sigma", policy_out["action_sigma"])
                self.storage.update_key("valid", active.unsqueeze(-1))
                if hidden_states is not None:
                    self.storage._save_hidden_states((hidden_states, None))

                obs_dict, _, dones, _ = self.env.step({"actions": rollout_actions})
                self._last_rollout_actions = rollout_actions
                obs_dict = {key: value.to(device) for key, value in obs_dict.items()}
                dones = dones.to(device=device, dtype=torch.bool)
                terminal = active & dones
                if terminal.any():
                    completed = self.env.last_completed_task_buf.to(device=device, dtype=torch.bool)
                    successes[terminal] = completed[terminal]
                    lengths[terminal] = step + 1
                self.storage.update_key("dones", terminal.unsqueeze(-1))
                self.storage.increment_step()

                active &= ~dones
                policy.reset(dones)
                previous_dones = dones
                global_active = self.accelerator.gather(active.sum()).sum()
                if int(global_active.item()) == 0:
                    break

        unfinished = active
        lengths[unfinished] = self.storage.step
        policy.clear_rollout()

        actions = self.storage.query_key("actions")[: self.storage.step]
        valid = self.storage.query_key("valid")[: self.storage.step].squeeze(-1)
        pair_valid = valid[1:] & valid[:-1]
        pair_counts = pair_valid.sum(dim=0)
        if bool((pair_counts == 0).any().item()):
            raise RuntimeError("GRPO action-rate cost requires at least two valid steps per trajectory")
        action_delta_sq = torch.square(actions[1:] - actions[:-1]).sum(dim=-1)
        action_rate_cost = (action_delta_sq * pair_valid).sum(dim=0) / pair_counts
        trajectory_returns = successes.float() - self.action_rate_lambda * action_rate_cost

        global_returns = self.accelerator.gather(trajectory_returns)
        global_successes = self.accelerator.gather(successes)
        global_lengths = self.accelerator.gather(lengths)
        global_action_rate = self.accelerator.gather(action_rate_cost)
        return_mean = global_returns.mean()
        return_std = global_returns.std(unbiased=False)
        skip_update = float(return_std.item()) < self.zero_variance_threshold
        if skip_update:
            self._zero_variance_groups += 1
            local_advantages = torch.zeros_like(trajectory_returns)
        else:
            local_advantages = (trajectory_returns - return_mean) / (return_std + 1.0e-8)
        advantages = torch.zeros_like(self.storage.query_key("advantages"))
        advantages[: self.storage.step, :, 0] = (
            valid * local_advantages.unsqueeze(0)
        )
        self.storage.batch_update_data("advantages", advantages)

        return {
            "skip_update": skip_update,
            "global_returns": global_returns,
            "global_successes": global_successes,
            "global_lengths": global_lengths,
            "global_action_rate": global_action_rate,
            "return_mean": return_mean,
            "return_std": return_std,
            "local_advantages": local_advantages,
            "rollout_steps": self.storage.step,
        }

    def _adjust_learning_rate_based_on_kl(self, kl_mean, optimizer):
        if self.desired_kl is None:
            return

        current_lr = float(self.args.learning_rate)
        if kl_mean > self.desired_kl * 2.0:
            new_lr = max(self.min_learning_rate, current_lr / 1.5)
        elif 0.0 < kl_mean < self.desired_kl / 2.0:
            new_lr = min(self.max_learning_rate, current_lr * 1.5)
        else:
            new_lr = current_lr
        self.args.learning_rate = new_lr
        for param_group in optimizer.param_groups:
            param_group["lr"] = new_lr

    def _chunk_hidden_states(self, start, env_indices):
        saved = self.storage.saved_hidden_states_a
        if saved is None:
            raise RuntimeError("GRPO recurrent rollout did not store actor hidden states")
        states = tuple(item[start, :, env_indices, :].contiguous() for item in saved)
        return states[0] if len(states) == 1 else states

    def _optimize_rollouts(self, perform_update=True):
        args = self.args
        device = self.accelerator.device
        action_dim = self.policy_model.num_actions
        num_envs = self.env.num_envs
        env_indices = torch.arange(num_envs, device=device)
        local_mini_batch_size = int(args.local_mini_batch_size)

        metric_sums = {
            "pg_loss": torch.zeros((), device=device),
            "analytic_kl": torch.zeros((), device=device),
            "clip_count": torch.zeros((), device=device),
            "valid_count": torch.zeros((), device=device),
        }
        ratio_max = torch.ones((), device=device)
        first_ratio_deviation = torch.zeros((), device=device)
        first_mean_deviation = torch.zeros((), device=device)
        first_minibatch = True

        for mini_start in range(0, num_envs, local_mini_batch_size):
            mini_indices = env_indices[mini_start : mini_start + local_mini_batch_size]
            local_valid_total = self.storage.valid[:, mini_indices].sum().float()
            global_valid_total = self.accelerator.gather(local_valid_total).sum()
            if perform_update:
                self.optimizer.zero_grad()
            minibatch_kl_sum = torch.zeros((), device=device)

            for start in range(0, self.storage.step, self.rollout_chunk_length):
                end = min(start + self.rollout_chunk_length, self.storage.step)
                actor_obs = self.storage.actor_obs[start:end].transpose(0, 1)
                latent = self.storage.latent[start:end].transpose(0, 1)
                actions = self.storage.actions[start:end].transpose(0, 1)
                old_logprobs = (
                    self.storage.actions_log_prob[start:end, mini_indices, 0].transpose(0, 1)
                )
                old_mean = self.storage.action_mean[start:end, mini_indices].transpose(0, 1)
                old_sigma = self.storage.action_sigma[start:end, mini_indices].transpose(0, 1)
                advantages = self.storage.advantages[start:end, mini_indices, 0].transpose(0, 1)
                valid = self.storage.valid[start:end, mini_indices, 0].transpose(0, 1)
                forward_masks = self.storage.valid[start:end, :, 0].transpose(0, 1).clone()
                if not bool(forward_masks.any().item()):
                    forward_masks[0, 0] = True

                result = self.model(
                    modes=["policy_from_latent"],
                    input_kwargs={
                        "policy_from_latent": {
                            "actor_obs": actor_obs,
                            "latent": latent,
                            "actions": actions,
                            "masks": forward_masks,
                            "hidden_states": self._chunk_hidden_states(start, env_indices),
                        }
                    },
                )["policy_from_latent"]
                new_logprobs = result["logprobs"][mini_indices]
                new_mean = result["action_mean"][mini_indices]
                new_sigma = result["action_std"][mini_indices]
                log_ratio = new_logprobs - old_logprobs
                ratio = torch.exp(log_ratio)
                pg_loss = torch.maximum(
                    -advantages * ratio,
                    -advantages * torch.clamp(
                        ratio,
                        1.0 - args.cliprange,
                        1.0 + args.cliprange,
                    ),
                )
                local_loss_sum = pg_loss[valid].sum()
                loss = local_loss_sum * self.accelerator.num_processes / global_valid_total
                if perform_update:
                    self.accelerator.backward(loss)

                with torch.no_grad():
                    kl = torch.sum(
                        torch.log(new_sigma / old_sigma + 1.0e-5)
                        + (torch.square(old_sigma) + torch.square(old_mean - new_mean))
                        / (2.0 * torch.square(new_sigma))
                        - 0.5,
                        dim=-1,
                    )
                    local_valid = valid.sum().float()
                    metric_sums["pg_loss"] += local_loss_sum.detach()
                    metric_sums["analytic_kl"] += kl[valid].sum()
                    metric_sums["clip_count"] += (
                        (torch.abs(ratio - 1.0) > args.cliprange) & valid
                    ).sum()
                    metric_sums["valid_count"] += local_valid
                    minibatch_kl_sum += kl[valid].sum()
                    if bool(valid.any().item()):
                        ratio_max = torch.maximum(ratio_max, ratio[valid].max())
                    if first_minibatch:
                        if bool(valid.any().item()):
                            first_ratio_deviation = torch.maximum(
                                first_ratio_deviation,
                                torch.abs(ratio[valid] - 1.0).max(),
                            )
                            mean_deviation = torch.abs(new_mean - old_mean).amax(dim=-1)
                            first_mean_deviation = torch.maximum(
                                first_mean_deviation,
                                mean_deviation[valid].max(),
                            )

            global_kl_sum = self.accelerator.gather(minibatch_kl_sum).sum()
            if perform_update:
                self._adjust_learning_rate_based_on_kl(
                    global_kl_sum / global_valid_total,
                    self.optimizer,
                )
            if first_minibatch:
                global_ratio_deviation = self.accelerator.gather(first_ratio_deviation).max()
                global_mean_deviation = self.accelerator.gather(first_mean_deviation).max()
                if float(global_ratio_deviation.item()) > self.first_update_ratio_tolerance:
                    raise RuntimeError(
                        "GRPO first-update replay ratio drifted from 1: "
                        f"max_abs={float(global_ratio_deviation.item()):.9g} "
                        f"mean_max_abs={float(global_mean_deviation.item()):.9g}"
                    )
                first_minibatch = False
            if perform_update:
                self._gradient_clipping()
                self.optimizer.step()

        gathered = {
            key: self.accelerator.gather(value).sum()
            for key, value in metric_sums.items()
        }
        global_ratio_max = self.accelerator.gather(ratio_max).max()
        global_first_ratio = self.accelerator.gather(first_ratio_deviation).max()
        global_first_mean = self.accelerator.gather(first_mean_deviation).max()
        count = gathered["valid_count"]
        return {
            "pg_loss": float((gathered["pg_loss"] / count).item()),
            "approx_kl": float((gathered["analytic_kl"] / count).item()),
            "clip_fraction": float((gathered["clip_count"] / count).item()),
            "ratio_max": float(global_ratio_max.item()),
            "first_ratio_max_abs": float(global_first_ratio.item()),
            "latent_replay_mean_max_abs": float(global_first_mean.item()),
        }

    def _append_metrics(self, metrics):
        if not self.accelerator.is_main_process:
            return
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metrics, sort_keys=True, allow_nan=False) + "\n")

    def train(self):
        args = self.args
        start_time = time.time()
        self.state.max_steps = args.num_total_batches
        self.state.num_train_epochs = args.total_episodes / self.train_dataset_len
        self.control = self.callback_handler.on_train_begin(args, self.state, self.control)
        for _ in range(self.state.global_step, args.num_total_batches):
            iteration_start = time.time()
            rollout = self._collect_rollouts()
            collection_time = time.time() - iteration_start
            self._train_mode()
            learning_start = time.time()
            update_metrics = self._optimize_rollouts(
                perform_update=not rollout["skip_update"]
            )
            learn_time = time.time() - learning_start

            global_returns = rollout["global_returns"]
            global_successes = rollout["global_successes"]
            global_lengths = rollout["global_lengths"]
            global_action_rate = rollout["global_action_rate"]
            global_advantages = self.accelerator.gather(rollout["local_advantages"])
            iteration_time = time.time() - iteration_start
            self.state.episode += int(global_successes.numel())
            self.state.tot_timesteps += int(global_lengths.sum().item())
            self.state.tot_time += iteration_time
            self.state.global_step += 1
            self.state.epoch = self.state.global_step / args.num_total_batches
            metrics = {
                "step": int(self.state.global_step),
                "group/return_mean": float(global_returns.mean().item()),
                "group/return_std": float(global_returns.std(unbiased=False).item()),
                "group/success_count": int(global_successes.sum().item()),
                "group/size": int(global_successes.numel()),
                "group/success_rate": float(global_successes.float().mean().item()),
                "group/advantage_mean": float(global_advantages.mean().item()),
                "group/advantage_std": float(global_advantages.std(unbiased=False).item()),
                "group/advantage_min": float(global_advantages.min().item()),
                "group/advantage_max": float(global_advantages.max().item()),
                "group/action_rate_mean": float(global_action_rate.mean().item()),
                "group/action_rate_std": float(global_action_rate.std(unbiased=False).item()),
                "group/episode_length_mean": float(global_lengths.float().mean().item()),
                "group/rollout_steps": int(rollout["rollout_steps"]),
                "group/zero_variance_count": int(self._zero_variance_groups),
                "group/update_skipped": bool(rollout["skip_update"]),
                "policy/approx_kl": update_metrics["approx_kl"],
                "policy/clip_fraction": update_metrics["clip_fraction"],
                "policy/ratio_max": update_metrics["ratio_max"],
                "policy/first_ratio_max_abs": update_metrics["first_ratio_max_abs"],
                "policy/latent_replay_mean_max_abs": update_metrics[
                    "latent_replay_mean_max_abs"
                ],
                "loss/policy": update_metrics["pg_loss"],
                "lr": float(self.optimizer.param_groups[0]["lr"]),
                "grpo/exploration_std": self.exploration_std,
                "grpo/action_rate_lambda": self.action_rate_lambda,
                "time/iteration_seconds": iteration_time,
                "time/total_seconds": time.time() - start_time,
                "tot_timesteps": int(self.state.tot_timesteps),
                "fps": float(global_lengths.sum().item() / iteration_time),
                "collection_time": collection_time,
                "learn_time": learn_time,
                "Policy/mean_noise_std": self.exploration_std,
                "episode": int(self.state.episode),
                "tot_time": float(self.state.tot_time),
                "batch_idx": int(self.state.global_step),
                "num_total_batches": int(args.num_total_batches),
                "experiment_save_dir": str(self.args.output_dir),
            }
            self._append_metrics(metrics)
            self.log(metrics)
            self.lr_scheduler.step()
            self.control = self.callback_handler.on_step_end(args, self.state, self.control)
            torch.cuda.empty_cache()
            gc.collect()
            if self.control.should_training_stop:
                break

        self.control = self.callback_handler.on_train_end(args, self.state, self.control)
        return None
