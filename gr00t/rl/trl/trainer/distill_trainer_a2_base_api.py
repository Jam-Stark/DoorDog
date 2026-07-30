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
_A2_TEACHER_IDENTITY_EMITTED = False
_A2_ACTION_CHAIN_EMITTED = False


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

    def load_teacher_actor(self):
        artifact = self.config.get("teacher_artifact", None)
        if artifact is None:
            raise ValueError("A2 Student requires teacher_artifact checkpoint/config/manifest paths")
        checkpoint_path = artifact.get("checkpoint_path")
        config_path = artifact.get("config_path")
        manifest_path = artifact.get("manifest_path")
        if not all(isinstance(path, str) and path for path in (checkpoint_path, config_path, manifest_path)):
            raise ValueError("A2 Student Teacher artifact paths must be non-empty strings")
        from gr00t.rl.scripts.validate_a2_teacher_checkpoint import validate_teacher_artifact

        manifest = validate_teacher_artifact(checkpoint_path, config_path, manifest_path)
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
        self._a2_cb2h_enabled = architecture_id == "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19"
        if self._a2_cb2h_enabled:
            if self.config.get("compute_dagger_bc_loss_w_imgaug", False):
                raise ValueError("C-B2H Student does not support image-augmented DAgger loss")
            if self.config.get("compute_imgaug_bc_loss", False):
                raise ValueError("C-B2H Student does not support image-augmented BC loss")
            self.camera_resolution = [384, 216, 6]
            self.context_camera_resolution = [136, 384, 3]
            self.camera_meta_resolution = [6]
            expected_obs_dims = {
                "vision_obs": int(np.prod(self.camera_resolution)),
                "context_vision_obs": int(np.prod(self.context_camera_resolution)),
                "camera_meta": 6,
            }
            for key, expected_dim in expected_obs_dims.items():
                if key not in self.algo_obs_dim_dict:
                    raise KeyError(f"C-B2H Student requires algo observation key {key!r}")
                if int(self.algo_obs_dim_dict[key]) != expected_dim:
                    raise ValueError(
                        f"C-B2H {key} dimension mismatch: "
                        f"config={self.algo_obs_dim_dict[key]}, expected={expected_dim}"
                    )
        if self.config.get("student_action_dim", A2_STUDENT_ACTION_DIM) != A2_STUDENT_ACTION_DIM:
            raise ValueError("student_action_dim must be exactly 12")
        if self.config.get("rollout_action_dim", A2_ROLLOUT_ACTION_DIM) != A2_ROLLOUT_ACTION_DIM:
            raise ValueError("rollout_action_dim must be exactly 24")

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
                    raise KeyError("context_vision_obs is only supported by the C-B2H Student")
                expected_dim = int(np.prod(self.context_camera_resolution))
                if int(obs_dim) != expected_dim:
                    raise ValueError(
                        f"context_vision_obs dim mismatch: config={obs_dim}, expected={expected_dim}"
                    )
                self.storage.register_key(
                    obs_key, shape=tuple(self.context_camera_resolution), dtype=torch.float
                )
            elif obs_key == "camera_meta":
                if not self._a2_cb2h_enabled:
                    raise KeyError("camera_meta is only supported by the C-B2H Student")
                if int(obs_dim) != 6:
                    raise ValueError(f"camera_meta dim mismatch: config={obs_dim}, expected=6")
                self.storage.register_key(obs_key, shape=(6,), dtype=torch.float)
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
        if getattr(self, "_a2_cb2h_enabled", False):
            required.update({"context_vision_obs", "camera_meta"})
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
        if not getattr(self, "_a2_cb2h_enabled", False) and vision.shape[-1] != 3:
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
            camera_meta = obs_dict["camera_meta"]
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
            if (
                not torch.is_tensor(camera_meta)
                or camera_meta.ndim != 2
                or tuple(camera_meta.shape[1:]) != (6,)
                or camera_meta.shape[0] != expected_batch
            ):
                raise ValueError(
                    f"camera_meta must match [N,6]; got {getattr(camera_meta, 'shape', None)}"
                )
            if (
                not torch.is_floating_point(camera_meta)
                or not torch.all(torch.isfinite(camera_meta))
                or camera_meta.device != expected_device
            ):
                raise ValueError("camera_meta must be finite floating data on actor_obs device")
            if bool(torch.any(camera_meta[:, :3] < 0.0).item()) or bool(
                torch.any(camera_meta[:, :3] > 1.0).item()
            ):
                raise ValueError("camera_meta ages must be normalized to [0,1]")
            flags = camera_meta[:, 3:]
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
    ):
        if auxiliary_model_a is not None or auxiliary_model_b is not None:
            raise ValueError("A2 Student trainer does not support auxiliary policy models")
        self._validate_rollout_obs(obs_dict, require_teacher=True)
        teacher_actions = self._teacher_actions(obs_dict)
        actor_obs_dict = {"actor_obs": obs_dict["actor_obs"], "vision_obs": obs_dict["vision_obs"]}
        if getattr(self, "_a2_cb2h_enabled", False):
            actor_obs_dict["context_vision_obs"] = obs_dict["context_vision_obs"]
            actor_obs_dict["camera_meta"] = obs_dict["camera_meta"]
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
        selected_high = high_level_actions
        selected_mean = high_level_mean
        ratio = float(self.config.get("ratio_teacher_rollout", 1.0))
        if not 0.0 <= ratio <= 1.0:
            raise ValueError(f"ratio_teacher_rollout must be within [0,1], got {ratio}")
        if self.config.get("enforce_teacher_rollout", False):
            count = int(selected_high.shape[0] * ratio)
            selected_high = selected_high.clone()
            selected_mean = selected_mean.clone()
            selected_high[:count] = teacher_actions[:count]
            selected_mean[:count] = teacher_actions[:count]
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
        if not getattr(self, "_a2_cb2h_enabled", False):
            return rollout_data

        device = self.accelerator.device
        context_vision_obs = (
            self.storage.context_vision_obs.transpose(0, 1).contiguous().to(device)
        )
        camera_meta = self.storage.camera_meta.transpose(0, 1).contiguous().to(device)
        rollout_data["context_vision_obs"] = context_vision_obs
        rollout_data["camera_meta"] = camera_meta

        padded_obs_dict = rollout_data.get("padded_obs_dict")
        if padded_obs_dict is not None:
            from gr00t.rl.trl.utils.rl import split_and_pad_trajectories

            dones = rollout_data["dones"]
            dones_transposed = dones.transpose(0, 1)
            trajectory_masks = rollout_data["trajectory_masks"]
            for key, obs_tensor in (
                ("context_vision_obs", context_vision_obs),
                ("camera_meta", camera_meta),
            ):
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
        if not getattr(self, "_a2_cb2h_enabled", False):
            return mb_rollout_data

        mb_obs_dict = mb_rollout_data["mb_obs_dict"]
        if "context_vision_obs" not in mb_obs_dict:
            mb_obs_dict["context_vision_obs"] = rollout_data["context_vision_obs"][micro_batch_inds]
        if "camera_meta" not in mb_obs_dict:
            mb_obs_dict["camera_meta"] = rollout_data["camera_meta"][micro_batch_inds]
        if set(("context_vision_obs", "camera_meta")).difference(mb_obs_dict):
            raise RuntimeError("C-B2H minibatch dropped context observation keys")
        return mb_rollout_data

    def _forward_model(self, model, mb_rollout_data):
        if getattr(self, "_a2_cb2h_enabled", False):
            obs_dict = mb_rollout_data["mb_obs_dict"]
            missing = {"context_vision_obs", "camera_meta"}.difference(obs_dict)
            if missing:
                raise KeyError(f"C-B2H forward is missing observation keys: {sorted(missing)}")
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
        self.ref_model.init_rollout()
        try:
            return A2TRLPPOTrainer._rollout_step(self, model, obs_dict)
        finally:
            self.ref_model.clear_rollout()

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
            return {"dagger_bc_loss": self.bc_loss_fn(predicted.to(target.dtype), target)}
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
        return {
            "dagger_bc_loss": self.bc_loss_fn(valid_predicted.to(valid_target.dtype), valid_target)
        }
