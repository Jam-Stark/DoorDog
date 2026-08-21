"""Matched-prefix base-command intervention for the v25 causal evaluation."""

from __future__ import annotations

from collections.abc import Mapping
import math

import torch


V25_INTERVENTION_MASKS = {
    "P1_M1": (),
    "P0_M1": (3, 4),
    "P1_M0": (0, 1, 2),
    "P0_M0": (0, 1, 2, 3, 4),
}


def read_v25_intervention_config(eval_config, *, env, process_count: int) -> dict:
    branch = eval_config.get("a2_v25_intervention_branch")
    if branch is None:
        return {"enabled": False}
    if branch not in V25_INTERVENTION_MASKS:
        raise RuntimeError(
            "eval.a2_v25_intervention_branch must be one of "
            f"{tuple(V25_INTERVENTION_MASKS)}; got {branch!r}."
        )
    if process_count != 1:
        raise RuntimeError("v25 matched-prefix intervention requires one eval process.")
    if eval_config.get("eval_num_envs_episodes") is not True:
        raise RuntimeError(
            "v25 matched-prefix intervention requires eval.eval_num_envs_episodes=true."
        )
    if not bool(getattr(env, "_use_a2_base", False)):
        raise RuntimeError("v25 matched-prefix intervention requires an A2_Base environment.")
    horizon_steps = eval_config.get("a2_v25_intervention_horizon_steps", 50)
    if isinstance(horizon_steps, bool) or not isinstance(horizon_steps, int) or horizon_steps <= 0:
        raise RuntimeError("eval.a2_v25_intervention_horizon_steps must be a positive integer.")
    near_closed_max_rad = eval_config.get(
        "a2_v25_intervention_near_closed_max_rad", 0.25
    )
    if (
        isinstance(near_closed_max_rad, bool)
        or not isinstance(near_closed_max_rad, (int, float))
        or not math.isfinite(float(near_closed_max_rad))
        or float(near_closed_max_rad) <= 0.0
    ):
        raise RuntimeError(
            "eval.a2_v25_intervention_near_closed_max_rad must be finite and positive."
        )
    return {
        "enabled": True,
        "branch": branch,
        "mask_indices": V25_INTERVENTION_MASKS[branch],
        "horizon_steps": horizon_steps,
        "near_closed_max_rad": float(near_closed_max_rad),
        "raw_filename": "a2_v25_intervention_records.json",
    }


class V25MatchedPrefixIntervention:
    """Latch at the existing stable-grasp high-water mark and mask base commands."""

    def __init__(self, env, config: Mapping[str, object]):
        self.env = env
        self.branch = str(config["branch"])
        self.mask_indices = tuple(config["mask_indices"])
        self.horizon_steps = int(config["horizon_steps"])
        self.near_closed_max_rad = float(config["near_closed_max_rad"])
        self.num_envs = int(env.num_envs)
        self.device = torch.device(env.device)
        dtype = env.door_open_lr.dtype

        self.latched = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.completed = torch.zeros_like(self.latched)
        self.switch_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self.elapsed = torch.zeros(self.num_envs, dtype=torch.long, device=self.device)
        self.start_hinge = torch.full(
            (self.num_envs,), float("nan"), dtype=dtype, device=self.device
        )
        self.end_hinge = torch.full_like(self.start_hinge, float("nan"))
        self.max_hinge = torch.full_like(self.start_hinge, float("nan"))
        self.start_root_xy = torch.full(
            (self.num_envs, 2), float("nan"), dtype=dtype, device=self.device
        )
        self.end_root_xy = torch.full_like(self.start_root_xy, float("nan"))
        self.start_roll_pitch = torch.full_like(self.start_root_xy, float("nan"))
        self.end_roll_pitch = torch.full_like(self.start_root_xy, float("nan"))
        self.planar_command_l1 = torch.zeros_like(self.start_hinge)
        self.posture_command_l1 = torch.zeros_like(self.start_hinge)
        self.removed_planar_l1 = torch.zeros_like(self.start_hinge)
        self.removed_posture_l1 = torch.zeros_like(self.start_hinge)
        self.roll_pitch_abs_sum = torch.zeros_like(self.start_hinge)
        self.contact_retained_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self.pending_active = torch.zeros_like(self.latched)
        self.records: list[dict] = []

    def _hinge(self) -> torch.Tensor:
        return self.env._get_door_joint_pos("v25 matched-prefix intervention", 1)[:, 0]

    def _robot_root_xy(self) -> torch.Tensor:
        data = self.env.simulator.scene.articulations["robot"].data
        return data.root_pos_w[:, :2]

    def apply(
        self,
        high_level_actions: torch.Tensor,
        *,
        first_episode_active_mask: torch.Tensor,
        control_steps: torch.Tensor,
    ) -> torch.Tensor:
        if (
            not torch.is_tensor(high_level_actions)
            or tuple(high_level_actions.shape) != (self.num_envs, 12)
            or not high_level_actions.is_floating_point()
            or not torch.all(torch.isfinite(high_level_actions))
        ):
            raise RuntimeError(
                "v25 matched-prefix intervention requires finite high-level actions "
                f"shape ({self.num_envs},12)."
            )
        if (
            not torch.is_tensor(first_episode_active_mask)
            or tuple(first_episode_active_mask.shape) != (self.num_envs,)
            or first_episode_active_mask.dtype != torch.bool
            or first_episode_active_mask.device != high_level_actions.device
        ):
            raise RuntimeError("v25 intervention first-episode mask contract mismatch.")
        if (
            not torch.is_tensor(control_steps)
            or tuple(control_steps.shape) != (self.num_envs,)
            or control_steps.dtype != torch.long
            or control_steps.device != high_level_actions.device
        ):
            raise RuntimeError("v25 intervention control-step contract mismatch.")

        hinge = self._hinge()
        stable = self.env._get_a2_v23_stable_grasp_mask(
            self.num_envs, high_level_actions.device
        )
        latch_now = (
            first_episode_active_mask
            & ~self.latched
            & ~self.completed
            & stable
            & (torch.abs(hinge) <= self.near_closed_max_rad)
        )
        if torch.any(latch_now):
            root_xy = self._robot_root_xy()
            roll_pitch = self.env._get_a2_base_roll_pitch()
            self.latched[latch_now] = True
            self.switch_step[latch_now] = control_steps[latch_now]
            self.start_hinge[latch_now] = hinge[latch_now]
            self.end_hinge[latch_now] = hinge[latch_now]
            self.max_hinge[latch_now] = hinge[latch_now]
            self.start_root_xy[latch_now] = root_xy[latch_now]
            self.end_root_xy[latch_now] = root_xy[latch_now]
            self.start_roll_pitch[latch_now] = roll_pitch[latch_now]
            self.end_roll_pitch[latch_now] = roll_pitch[latch_now]

        active = self.latched & ~self.completed & first_episode_active_mask
        base = high_level_actions[:, :5]
        self.planar_command_l1[active] += torch.abs(base[active, :3]).sum(dim=-1)
        self.posture_command_l1[active] += torch.abs(base[active, 3:5]).sum(dim=-1)
        result = high_level_actions.clone()
        if self.mask_indices:
            if any(index < 3 for index in self.mask_indices):
                self.removed_planar_l1[active] += torch.abs(base[active, :3]).sum(dim=-1)
            if any(index >= 3 for index in self.mask_indices):
                self.removed_posture_l1[active] += torch.abs(base[active, 3:5]).sum(dim=-1)
            active_rows = torch.nonzero(active, as_tuple=False).flatten()
            if active_rows.numel() > 0:
                mask_columns = torch.tensor(
                    self.mask_indices, dtype=torch.long, device=high_level_actions.device
                )
                result[active_rows[:, None], mask_columns[None, :]] = 0.0
        self.pending_active = active.clone()
        return result

    def after_step(self, dones: torch.Tensor) -> None:
        dones_flat = dones.reshape(-1).to(device=self.device, dtype=torch.bool)
        active = self.pending_active
        if not torch.any(active):
            return
        self.elapsed[active] += 1
        safe = active & ~dones_flat
        if torch.any(safe):
            hinge = self._hinge()
            root_xy = self._robot_root_xy()
            roll_pitch = self.env._get_a2_base_roll_pitch()
            contacts = self.env._get_a2_stage3_stage4_contact_squeeze_masks(
                "v25 matched-prefix contact retention"
            )
            retained = (
                contacts["both_contact"]
                & contacts["sufficient_squeeze"]
                & contacts["opposite_squeeze"]
            )
            self.end_hinge[safe] = hinge[safe]
            self.max_hinge[safe] = torch.maximum(self.max_hinge[safe], hinge[safe])
            self.end_root_xy[safe] = root_xy[safe]
            self.end_roll_pitch[safe] = roll_pitch[safe]
            self.roll_pitch_abs_sum[safe] += torch.abs(roll_pitch[safe]).sum(dim=-1)
            self.contact_retained_steps[safe] += retained[safe].long()

        finish = active & ((self.elapsed >= self.horizon_steps) | dones_flat)
        for env_id in torch.nonzero(finish, as_tuple=False).flatten().detach().cpu().tolist():
            self.records.append(self._record(env_id, done_early=bool(dones_flat[env_id].item())))
        self.completed[finish] = True
        self.pending_active[:] = False

    def _record(self, env_id: int, *, done_early: bool) -> dict:
        steps = int(self.elapsed[env_id].item())
        side_sign = int(self.env.door_open_lr[env_id].item())
        start_hinge = float(self.start_hinge[env_id].item())
        end_hinge = float(self.end_hinge[env_id].item())
        start_root = self.start_root_xy[env_id]
        end_root = self.end_root_xy[env_id]
        return {
            "schema": "a2_piper_v25_matched_prefix_intervention_record_v1",
            "branch": self.branch,
            "mask_indices": list(self.mask_indices),
            "env_id": env_id,
            "door_open_lr": side_sign,
            "door_handle_side": "left" if side_sign > 0 else "right",
            "switch_step": int(self.switch_step[env_id].item()),
            "state_id": (
                f"{'left' if side_sign > 0 else 'right'}-env{env_id}-"
                f"step{int(self.switch_step[env_id].item())}"
            ),
            "restore_mode": "matched-prefix",
            "near_closed_max_rad": self.near_closed_max_rad,
            "horizon_steps_target": self.horizon_steps,
            "horizon_steps_observed": steps,
            "done_before_horizon": done_early and steps < self.horizon_steps,
            "eligible_complete_horizon": not done_early and steps == self.horizon_steps,
            "hinge_start_rad": start_hinge,
            "hinge_end_rad": end_hinge,
            "hinge_delta_rad": end_hinge - start_hinge,
            "hinge_max_progress_rad": float(self.max_hinge[env_id].item()) - start_hinge,
            "contact_retention_fraction": (
                float(self.contact_retained_steps[env_id].item()) / steps
            ),
            "raw_planar_command_l1_mean": float(self.planar_command_l1[env_id].item()) / steps,
            "raw_posture_command_l1_mean": float(self.posture_command_l1[env_id].item()) / steps,
            "removed_planar_command_l1_mean": float(self.removed_planar_l1[env_id].item()) / steps,
            "removed_posture_command_l1_mean": float(self.removed_posture_l1[env_id].item()) / steps,
            "root_planar_displacement_m": float(torch.linalg.norm(end_root - start_root).item()),
            "roll_pitch_abs_mean_rad": float(self.roll_pitch_abs_sum[env_id].item()) / (2 * steps),
            "start_roll_pitch_rad": self.start_roll_pitch[env_id].detach().cpu().tolist(),
            "end_roll_pitch_rad": self.end_roll_pitch[env_id].detach().cpu().tolist(),
        }

    def payload(self, *, checkpoint: str, seed: int) -> dict:
        latched_ids = torch.nonzero(self.latched, as_tuple=False).flatten().detach().cpu().tolist()
        completed_ids = torch.nonzero(self.completed, as_tuple=False).flatten().detach().cpu().tolist()
        return {
            "schema": "a2_piper_v25_matched_prefix_intervention_v1",
            "status": "COMPLETE",
            "checkpoint": checkpoint,
            "seed": seed,
            "branch": self.branch,
            "mask_indices": list(self.mask_indices),
            "horizon_steps": self.horizon_steps,
            "near_closed_max_rad": self.near_closed_max_rad,
            "friction": {
                "backend": self.env.config.get("a2_v24_friction_backend"),
                "static_effort": self.env.config.get("a2_v24_friction_static_effort"),
                "dynamic_effort": self.env.config.get("a2_v24_friction_dynamic_effort"),
                "viscous_coefficient": self.env.config.get(
                    "a2_v24_friction_viscous_coefficient"
                ),
            },
            "num_envs": self.num_envs,
            "latched_env_ids": latched_ids,
            "completed_env_ids": completed_ids,
            "unlatched_env_ids": sorted(set(range(self.num_envs)) - set(latched_ids)),
            "records": self.records,
            "restore_mode": "matched-prefix",
            "arm_gripper_intervention": False,
        }
