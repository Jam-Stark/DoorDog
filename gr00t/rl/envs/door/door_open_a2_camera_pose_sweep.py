"""Eval-only matched single-camera pose sweep for A2+Piper."""

from __future__ import annotations

import math

import torch
from omegaconf import OmegaConf

from gr00t.rl.envs.door.door_open_a2_base import DoorPregrasp
from gr00t.rl.utils.a2_camera_pose_sweep import (
    STAGE_NAMES,
    TARGET_NAMES,
    instance_target_ids_by_env,
    rank_camera_candidates,
    validate_pose_candidates,
)


class DoorPregraspCameraPoseSweep(DoorPregrasp):
    """Keep the v13 teacher rollout unchanged while sweeping one camera in-place."""

    def init_a2_eval_stage2_step_trace(
        self,
        diagnostic_enabled: bool = False,
        diagnostic_reward_terms=(),
    ):
        super().init_a2_eval_stage2_step_trace(
            diagnostic_enabled=diagnostic_enabled,
            diagnostic_reward_terms=diagnostic_reward_terms,
        )
        raw_cfg = self.config.get("a2_camera_pose_sweep", None)
        cfg = OmegaConf.to_container(raw_cfg, resolve=True)
        if not isinstance(cfg, dict) or cfg.get("enabled") is not True:
            raise RuntimeError(
                "DoorPregraspCameraPoseSweep requires env.config.a2_camera_pose_sweep.enabled=true"
            )
        expected_keys = {
            "enabled",
            "sample_interval_control_steps",
            "minimum_visible_pixels",
            "target_path_tokens",
            "nominal_intrinsics",
            "candidates",
        }
        if set(cfg) != expected_keys:
            raise RuntimeError(
                "a2_camera_pose_sweep config schema mismatch; "
                f"missing={sorted(expected_keys - set(cfg))}, "
                f"unexpected={sorted(set(cfg) - expected_keys)}"
            )
        sample_interval = cfg["sample_interval_control_steps"]
        if (
            isinstance(sample_interval, bool)
            or not isinstance(sample_interval, int)
            or sample_interval < 1
        ):
            raise RuntimeError(
                "a2_camera_pose_sweep.sample_interval_control_steps must be a positive int"
            )
        minimum_visible_pixels = cfg["minimum_visible_pixels"]
        if not isinstance(minimum_visible_pixels, dict) or set(minimum_visible_pixels) != set(
            TARGET_NAMES
        ):
            raise RuntimeError(
                f"minimum_visible_pixels must have exact keys {list(TARGET_NAMES)}"
            )
        for target, value in minimum_visible_pixels.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise RuntimeError(
                    f"minimum_visible_pixels.{target} must be a positive int; got {value!r}"
                )
        target_path_tokens = cfg["target_path_tokens"]
        if not isinstance(target_path_tokens, dict) or set(target_path_tokens) != set(TARGET_NAMES):
            raise RuntimeError(f"target_path_tokens must have exact keys {list(TARGET_NAMES)}")
        if any(not isinstance(value, str) or not value for value in target_path_tokens.values()):
            raise RuntimeError("target_path_tokens values must be non-empty strings")

        candidates = validate_pose_candidates(cfg["candidates"])
        camera = self.simulator.ego_camera
        if camera is None:
            raise RuntimeError("camera pose sweep requires simulator.ego_camera")
        from isaaclab.sim.views import XformPrimView

        camera_view = camera._view
        if not isinstance(camera_view, XformPrimView) or camera_view.count != self.num_envs:
            count = None if not isinstance(camera_view, XformPrimView) else camera_view.count
            raise RuntimeError(
                "camera pose sweep must reuse TiledCamera._view for every env; "
                f"type={type(camera_view).__name__}, count={count}, num_envs={self.num_envs}"
            )
        if camera.cfg.colorize_instance_id_segmentation is not False:
            raise RuntimeError("camera pose sweep requires raw, non-colorized instance IDs")
        required_outputs = {"rgb", "instance_id_segmentation_fast"}
        output = camera.data.output
        if set(output).intersection(required_outputs) != required_outputs:
            raise RuntimeError(
                "camera pose sweep requires outputs "
                f"{sorted(required_outputs)}; got {sorted(output)}"
            )
        expected_shape = (self.num_envs, camera.cfg.height, camera.cfg.width, 1)
        segmentation = output["instance_id_segmentation_fast"]
        if tuple(segmentation.shape) != expected_shape or segmentation.dtype != torch.int32:
            raise RuntimeError(
                "raw instance segmentation shape/dtype mismatch; "
                f"expected={expected_shape}/torch.int32, "
                f"got={tuple(segmentation.shape)}/{segmentation.dtype}"
            )

        expected_intrinsics = cfg["nominal_intrinsics"]["sim_policy_fx_fy_cx_cy"]
        if not isinstance(expected_intrinsics, list) or len(expected_intrinsics) != 4:
            raise RuntimeError("nominal_intrinsics.sim_policy_fx_fy_cx_cy must contain four values")
        expected_matrix = torch.tensor(
            [
                [expected_intrinsics[0], 0.0, expected_intrinsics[2]],
                [0.0, expected_intrinsics[1], expected_intrinsics[3]],
                [0.0, 0.0, 1.0],
            ],
            device=camera.data.intrinsic_matrices.device,
            dtype=camera.data.intrinsic_matrices.dtype,
        )
        intrinsic_matrices = camera.data.intrinsic_matrices
        if tuple(intrinsic_matrices.shape) != (self.num_envs, 3, 3):
            raise RuntimeError(
                "camera intrinsic matrix shape mismatch; "
                f"got {tuple(intrinsic_matrices.shape)}"
            )
        intrinsic_error_px = float(
            torch.max(torch.abs(intrinsic_matrices - expected_matrix)).detach().cpu().item()
        )
        if not math.isfinite(intrinsic_error_px) or intrinsic_error_px > 0.05:
            raise RuntimeError(
                "runtime camera intrinsics do not match the 335L crop target; "
                f"max_error_px={intrinsic_error_px}"
            )

        self._a2_camera_sweep_cfg = cfg
        self._a2_camera_sweep_candidates = candidates
        self._a2_camera_sweep_camera = camera
        self._a2_camera_sweep_camera_view = camera_view
        self._a2_camera_sweep_sample_interval = sample_interval
        self._a2_camera_sweep_minimum_visible_pixels = minimum_visible_pixels
        self._a2_camera_sweep_target_path_tokens = target_path_tokens
        self._a2_camera_sweep_intrinsic_error_px = intrinsic_error_px
        self._a2_camera_sweep_first_episode_active = torch.ones(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_camera_sweep_last_stage = self.stage_buf.detach().clone()
        self._a2_camera_sweep_discovered_envs = {
            target: set() for target in TARGET_NAMES
        }
        self._a2_camera_sweep_stats = {
            candidate["name"]: {
                STAGE_NAMES[stage_index]: self._new_camera_sweep_stage_stats()
                for stage_index in STAGE_NAMES
            }
            for candidate in candidates
        }
        self._a2_camera_sweep_sample_events = 0
        self._a2_camera_sweep_pose_diversity_validated = False

    @staticmethod
    def _new_camera_sweep_stage_stats():
        return {
            "sampled_frames": 0,
            "handle_visible_frames": 0,
            "finger7_visible_frames": 0,
            "finger8_visible_frames": 0,
            "handle_and_both_fingers_visible_frames": 0,
            "door_panel_visible_frames": 0,
            "handle_centered_frames": 0,
            "handle_visible_pixels": [],
        }

    def _capture_a2_eval_stage2_step_trace(self):
        super()._capture_a2_eval_stage2_step_trace()
        if "_a2_camera_sweep_cfg" not in self.__dict__:
            raise RuntimeError("camera sweep capture requested before initialization")
        active = self._a2_camera_sweep_first_episode_active
        if not torch.any(active):
            return
        stage_changed = bool(torch.any(self.stage_buf != self._a2_camera_sweep_last_stage))
        self._a2_camera_sweep_last_stage = self.stage_buf.detach().clone()
        step_index = int(self.common_step_counter)
        should_sample = stage_changed or step_index % self._a2_camera_sweep_sample_interval == 0
        if should_sample:
            self._capture_a2_camera_pose_sweep_sample(active)
        self._a2_camera_sweep_first_episode_active &= ~self.reset_buf.bool()

    def _capture_a2_camera_pose_sweep_sample(self, active: torch.Tensor):
        from isaaclab.utils.math import convert_camera_frame_orientation_convention

        simulator = self.simulator
        camera = self._a2_camera_sweep_camera
        camera_view = self._a2_camera_sweep_camera_view
        parent_pos = simulator._robot.data.body_pos_w[:, simulator.camera_body_id, :].clone()
        parent_quat = simulator._robot.data.body_quat_w[:, simulator.camera_body_id, :].clone()
        physics_step_before = int(simulator._sim_step_counter)

        configured_pos = torch.tensor(
            simulator.simulator_config.cameras.camera_pos,
            device=parent_pos.device,
            dtype=parent_pos.dtype,
        ).reshape(1, 3).expand(self.num_envs, -1)
        configured_quat = torch.tensor(
            simulator.simulator_config.cameras.camera_rot_wxyz,
            device=parent_quat.device,
            dtype=parent_quat.dtype,
        ).reshape(1, 4).expand(self.num_envs, -1)
        configured_quat_opengl = convert_camera_frame_orientation_convention(
            configured_quat, origin="world", target="opengl"
        )
        first_render_by_candidate = {}

        try:
            for candidate in self._a2_camera_sweep_candidates:
                local_pos = parent_pos.new_tensor(candidate["position_m"]).reshape(1, 3)
                local_pos = local_pos.expand(self.num_envs, -1)
                local_quat = parent_quat.new_tensor(candidate["rotation_wxyz"]).reshape(1, 4)
                local_quat = local_quat.expand(self.num_envs, -1)
                local_quat_opengl = convert_camera_frame_orientation_convention(
                    local_quat, origin="world", target="opengl"
                )
                camera_view.set_local_poses(local_pos, local_quat_opengl)
                frame_before = camera.frame.clone()
                simulator.sim.render()
                camera.update(dt=0.0, force_recompute=True)
                if not torch.equal(camera.frame, frame_before + 1):
                    raise RuntimeError(
                        "each same-step candidate render must advance exactly one sensor frame"
                    )
                if int(simulator._sim_step_counter) != physics_step_before:
                    raise RuntimeError("camera pose sweep render advanced the physics step counter")
                observed_local_pos, observed_local_quat_opengl = camera_view.get_local_poses()
                self._assert_a2_camera_pose(
                    observed_local_pos,
                    observed_local_quat_opengl,
                    local_pos,
                    local_quat_opengl,
                    context=f"candidate {candidate['name']}",
                )
                self._accumulate_a2_camera_candidate(candidate["name"], active)
                if self._a2_camera_sweep_sample_events == 0:
                    first_render_by_candidate[candidate["name"]] = (
                        camera.data.output["rgb"].clone(),
                        camera.data.output["instance_id_segmentation_fast"].clone(),
                    )
        finally:
            camera_view.set_local_poses(configured_pos, configured_quat_opengl)
            simulator.sim.render()

        restore_pos_observed, restore_quat_opengl_observed = camera_view.get_local_poses()
        self._assert_a2_camera_pose(
            restore_pos_observed,
            restore_quat_opengl_observed,
            configured_pos,
            configured_quat_opengl,
            context="configured-pose restore",
        )

        if int(simulator._sim_step_counter) != physics_step_before:
            raise RuntimeError("camera pose sweep changed the physics step counter")
        if self._a2_camera_sweep_sample_events == 0:
            control_name = next(
                candidate["name"]
                for candidate in self._a2_camera_sweep_candidates
                if candidate["role"] == "control"
            )
            control_rgb, control_segmentation = first_render_by_candidate[control_name]
            search_names = [
                candidate["name"]
                for candidate in self._a2_camera_sweep_candidates
                if candidate["role"] == "search"
            ]
            if all(
                torch.equal(control_rgb, first_render_by_candidate[name][0])
                and torch.equal(control_segmentation, first_render_by_candidate[name][1])
                for name in search_names
            ):
                raise RuntimeError(
                    "camera pose sweep rendered identical RGB and instance segmentation for "
                    "the control and every search pose"
                )
            self._a2_camera_sweep_pose_diversity_validated = True
        self._a2_camera_sweep_sample_events += 1

    @staticmethod
    def _assert_a2_camera_pose(
        observed_pos: torch.Tensor,
        observed_quat: torch.Tensor,
        expected_pos: torch.Tensor,
        expected_quat: torch.Tensor,
        *,
        context: str,
    ):
        position_error_m = float(
            torch.max(torch.abs(observed_pos - expected_pos)).detach().cpu().item()
        )
        quaternion_alignment = torch.abs(torch.sum(observed_quat * expected_quat, dim=-1))
        orientation_error = float(
            torch.max(torch.abs(1.0 - quaternion_alignment)).detach().cpu().item()
        )
        if position_error_m > 1.0e-4 or orientation_error > 1.0e-4:
            raise RuntimeError(
                f"camera {context} pose readback mismatch; "
                f"position_error_m={position_error_m}, "
                f"quaternion_alignment_error={orientation_error}"
            )

    def _accumulate_a2_camera_candidate(self, candidate_name: str, active: torch.Tensor):
        camera = self._a2_camera_sweep_camera
        segmentation = camera.data.output["instance_id_segmentation_fast"]
        if tuple(segmentation.shape) != (self.num_envs, camera.cfg.height, camera.cfg.width, 1):
            raise RuntimeError(f"instance segmentation shape drift: {tuple(segmentation.shape)}")
        segmentation = segmentation[..., 0]
        info = camera.data.info.get("instance_id_segmentation_fast")
        if not isinstance(info, dict):
            raise RuntimeError("instance segmentation output requires an info mapping")
        target_ids = instance_target_ids_by_env(
            info,
            num_envs=self.num_envs,
            target_path_tokens=self._a2_camera_sweep_target_path_tokens,
        )
        masks = {}
        for target in TARGET_NAMES:
            target_mask = torch.zeros_like(segmentation, dtype=torch.bool)
            for env_id, instance_ids in enumerate(target_ids[target]):
                if instance_ids:
                    self._a2_camera_sweep_discovered_envs[target].add(env_id)
                for instance_id in instance_ids:
                    target_mask[env_id] |= segmentation[env_id] == instance_id
            masks[target] = target_mask

        pixel_counts = {target: mask.sum(dim=(1, 2)) for target, mask in masks.items()}
        visible = {
            target: pixel_counts[target] >= self._a2_camera_sweep_minimum_visible_pixels[target]
            for target in TARGET_NAMES
        }
        handle_mask = masks["handle"]
        column_counts = handle_mask.sum(dim=1)
        row_counts = handle_mask.sum(dim=2)
        x_coordinates = torch.arange(camera.cfg.width, device=self.device, dtype=torch.float32)
        y_coordinates = torch.arange(camera.cfg.height, device=self.device, dtype=torch.float32)
        handle_pixels_float = pixel_counts["handle"].clamp(min=1).float()
        centroid_x = (column_counts.float() * x_coordinates).sum(dim=1) / handle_pixels_float
        centroid_y = (row_counts.float() * y_coordinates).sum(dim=1) / handle_pixels_float
        handle_centered = (
            visible["handle"]
            & (centroid_x >= 0.1 * camera.cfg.width)
            & (centroid_x < 0.9 * camera.cfg.width)
            & (centroid_y >= 0.1 * camera.cfg.height)
            & (centroid_y < 0.9 * camera.cfg.height)
        )
        trio_visible = visible["handle"] & visible["finger7"] & visible["finger8"]

        for stage_index in STAGE_NAMES:
            stage_mask = active if stage_index == 6 else active & (self.stage_buf == stage_index)
            count = int(stage_mask.sum().detach().cpu().item())
            if count == 0:
                continue
            stats = self._a2_camera_sweep_stats[candidate_name][STAGE_NAMES[stage_index]]
            stats["sampled_frames"] += count
            stats["handle_visible_frames"] += self._masked_count(visible["handle"], stage_mask)
            stats["finger7_visible_frames"] += self._masked_count(visible["finger7"], stage_mask)
            stats["finger8_visible_frames"] += self._masked_count(visible["finger8"], stage_mask)
            stats["handle_and_both_fingers_visible_frames"] += self._masked_count(
                trio_visible, stage_mask
            )
            stats["door_panel_visible_frames"] += self._masked_count(
                visible["door_panel"], stage_mask
            )
            stats["handle_centered_frames"] += self._masked_count(handle_centered, stage_mask)
            stats["handle_visible_pixels"].extend(
                int(value)
                for value in pixel_counts["handle"][stage_mask].detach().cpu().tolist()
            )

    @staticmethod
    def _masked_count(value: torch.Tensor, mask: torch.Tensor) -> int:
        return int((value & mask).sum().detach().cpu().item())

    def get_eval_metrics_summary(self):
        summary = super().get_eval_metrics_summary()
        if "_a2_camera_sweep_cfg" not in self.__dict__:
            raise RuntimeError("camera sweep summary requested before initialization")
        if torch.any(self._a2_camera_sweep_first_episode_active):
            active_envs = (
                self._a2_camera_sweep_first_episode_active.nonzero(as_tuple=False)
                .flatten()
                .detach()
                .cpu()
                .tolist()
            )
            raise RuntimeError(f"camera sweep ended before first episodes completed: {active_envs}")
        expected_envs = set(range(self.num_envs))
        missing_targets = {
            target: sorted(expected_envs - discovered)
            for target, discovered in self._a2_camera_sweep_discovered_envs.items()
            if discovered != expected_envs
        }
        if missing_targets:
            raise RuntimeError(
                "camera sweep never resolved target instance paths for all envs; "
                f"missing={missing_targets}"
            )
        if self._a2_camera_sweep_sample_events < 1:
            raise RuntimeError("camera sweep produced no sample events")
        if not self._a2_camera_sweep_pose_diversity_validated:
            raise RuntimeError("camera sweep never validated rendered pose diversity")

        candidate_summaries = []
        all_sample_counts = set()
        for candidate in self._a2_camera_sweep_candidates:
            stages = {}
            for stage_name, raw_stats in self._a2_camera_sweep_stats[candidate["name"]].items():
                stats = dict(raw_stats)
                pixels = stats.pop("handle_visible_pixels")
                sampled = stats["sampled_frames"]
                if len(pixels) != sampled:
                    raise RuntimeError(
                        f"candidate {candidate['name']} {stage_name} pixel/sample count mismatch"
                    )
                for key, value in tuple(stats.items()):
                    if key == "sampled_frames":
                        continue
                    stats[key.replace("_frames", "_rate")] = (
                        None if sampled == 0 else value / sampled
                    )
                stats["handle_visible_pixels_p05"] = self._integer_quantile(pixels, 0.05)
                stats["handle_visible_pixels_p50"] = self._integer_quantile(pixels, 0.50)
                stages[stage_name] = stats
            all_sample_counts.add(stages[STAGE_NAMES[6]]["sampled_frames"])
            candidate_summaries.append({**candidate, "stages": stages})
        if len(all_sample_counts) != 1:
            raise RuntimeError(
                f"matched sweep candidates have unequal sample counts: {sorted(all_sample_counts)}"
            )

        ranking = rank_camera_candidates(candidate_summaries)
        summary["a2_camera_pose_sweep"] = {
            "status": "SWEEP_COMPLETE",
            "architecture": (
                "one trunk camera; one sensor prim repositioned between same-step renders"
            ),
            "policy_driver": "base_v13_A teacher checkpoint; camera is diagnostic-only",
            "training_performed": False,
            "num_envs": self.num_envs,
            "sample_events": self._a2_camera_sweep_sample_events,
            "sample_interval_control_steps": self._a2_camera_sweep_sample_interval,
            "physics_advanced_between_candidates": False,
            "candidate_pose_readback_validated": True,
            "rendered_pose_diversity_validated": True,
            "runtime_intrinsic_max_error_px": self._a2_camera_sweep_intrinsic_error_px,
            "nominal_intrinsics": self._a2_camera_sweep_cfg["nominal_intrinsics"],
            "minimum_visible_pixels": self._a2_camera_sweep_minimum_visible_pixels,
            "candidates": candidate_summaries,
            "recommendation": ranking,
            "boundaries": [
                "nominal FoV-derived intrinsics are not a physical-camera calibration",
                (
                    "current rollout uses the right/out door asset and does not "
                    "validate left/right symmetry"
                ),
                "instance visibility is a diagnostic ranking, not the full camera hard gate",
                (
                    "mechanical clearance, vibration, latency, blur, and real-world "
                    "exposure remain untested"
                ),
                "no Student training or Student policy-quality evaluation was performed",
            ],
        }
        return summary

    @staticmethod
    def _integer_quantile(values: list[int], probability: float):
        if not values:
            return None
        ordered = sorted(values)
        index = int(round((len(ordered) - 1) * probability))
        return ordered[index]
