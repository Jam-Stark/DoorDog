"""Eval-only matched single-camera pose sweep for A2+Piper."""

from __future__ import annotations

import math
import os
from pathlib import Path

import imageio.v2 as imageio
import torch
from omegaconf import OmegaConf

from gr00t.rl.envs.door.door_open_a2_base import DoorPregrasp
from gr00t.rl.utils.a2_dual_portrait_panorama import (
    depth_aware_cylindrical_panorama,
)
from gr00t.rl.utils.a2_camera_pose_sweep import (
    STAGE_NAMES,
    TARGET_NAMES,
    instance_target_ids_by_env,
    rank_camera_candidates,
    validate_pose_candidates,
)


class DoorPregraspCameraPoseSweep(DoorPregrasp):
    """Keep the Teacher rollout unchanged while sweeping one camera in-place."""

    HANDLE_EDGE_MARGIN_FRACTION = 0.05

    def __init__(self, config, device):
        requested_raw_ids = config.simulator.config.cameras.get(
            "colorize_instance_id_segmentation", None
        )
        if requested_raw_ids is not False:
            raise RuntimeError(
                "camera pose sweep requires explicit "
                "cameras.colorize_instance_id_segmentation=false"
            )

        from isaaclab.sensors.camera import TiledCameraCfg

        original_init = TiledCameraCfg.__init__

        def init_with_raw_instance_ids(camera_cfg, *args, **kwargs):
            supplied = kwargs.get("colorize_instance_id_segmentation", requested_raw_ids)
            if supplied is not False:
                raise RuntimeError("TiledCameraCfg raw instance-ID adapter received true")
            kwargs["colorize_instance_id_segmentation"] = False
            original_init(camera_cfg, *args, **kwargs)

        TiledCameraCfg.__init__ = init_with_raw_instance_ids
        try:
            super().__init__(config, device)
        finally:
            TiledCameraCfg.__init__ = original_init

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
            "ranking_stage_indices",
            "video",
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
        ranking_stage_indices = cfg["ranking_stage_indices"]
        if ranking_stage_indices not in ([1, 2, 3, 4, 5], [0, 1, 2, 3]):
            raise RuntimeError(
                "camera sweep ranking_stage_indices must be exact [1,2,3,4,5] "
                "or stage0-3 hard-gate profile [0,1,2,3]"
            )
        video_cfg = cfg["video"]
        expected_video_keys = {"enabled", "env_id", "fps", "output_dir"}
        if not isinstance(video_cfg, dict) or set(video_cfg) != expected_video_keys:
            keys = None if not isinstance(video_cfg, dict) else sorted(video_cfg)
            raise RuntimeError(
                "camera sweep video config schema mismatch; "
                f"expected={sorted(expected_video_keys)}, got={keys}"
            )
        if video_cfg["enabled"] is not True:
            raise RuntimeError("camera sweep requires one video for every candidate")
        video_env_id = video_cfg["env_id"]
        if (
            isinstance(video_env_id, bool)
            or not isinstance(video_env_id, int)
            or not 0 <= video_env_id < self.num_envs
        ):
            raise RuntimeError(f"camera sweep video env_id is invalid: {video_env_id!r}")
        video_fps = video_cfg["fps"]
        if isinstance(video_fps, bool) or not isinstance(video_fps, int) or video_fps < 1:
            raise RuntimeError(f"camera sweep video fps must be a positive int: {video_fps!r}")
        if not isinstance(video_cfg["output_dir"], str) or not video_cfg["output_dir"]:
            raise RuntimeError("camera sweep video output_dir must be a non-empty string")

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
        rgb = output["rgb"]
        expected_rgb_shape = (self.num_envs, camera.cfg.height, camera.cfg.width, 3)
        if tuple(rgb.shape) != expected_rgb_shape or rgb.dtype != torch.uint8:
            raise RuntimeError(
                "camera RGB shape/dtype mismatch; "
                f"expected={expected_rgb_shape}/torch.uint8, "
                f"got={tuple(rgb.shape)}/{rgb.dtype}"
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
                "runtime camera intrinsics do not match the configured target; "
                f"max_error_px={intrinsic_error_px}"
            )

        self._a2_camera_sweep_cfg = cfg
        self._a2_camera_sweep_candidates = candidates
        self._a2_camera_sweep_camera = camera
        self._a2_camera_sweep_camera_view = camera_view
        self._a2_camera_sweep_sample_interval = sample_interval
        self._a2_camera_sweep_ranking_stage_indices = ranking_stage_indices
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
        self._a2_camera_sweep_video_env_id = video_env_id
        self._a2_camera_sweep_video_fps = video_fps
        self._a2_camera_sweep_video_output_dir = Path(video_cfg["output_dir"]).resolve()
        if self._a2_camera_sweep_video_output_dir.exists():
            raise FileExistsError(
                "refusing to reuse camera candidate video directory: "
                f"{self._a2_camera_sweep_video_output_dir}"
            )
        self._a2_camera_sweep_video_output_dir.mkdir(parents=True, exist_ok=False)
        self._a2_camera_sweep_video_writers = {}
        self._a2_camera_sweep_video_temporary_paths = {}
        self._a2_camera_sweep_video_final_paths = {}
        self._a2_camera_sweep_video_frame_counts = {
            candidate["name"]: 0 for candidate in candidates
        }
        self._a2_camera_sweep_video_stage_frame_counts = {
            STAGE_NAMES[stage_index]: 0 for stage_index in range(6)
        }
        self._a2_camera_sweep_videos_sealed = False
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
            "handle_edge_clear_frames": 0,
            "handle_visible_pixels": [],
        }

    def _a2_camera_for_candidate(self, candidate_name: str):
        candidate_names = {candidate["name"] for candidate in self._a2_camera_sweep_candidates}
        if candidate_name not in candidate_names:
            raise KeyError(f"unknown camera candidate: {candidate_name}")
        return self._a2_camera_sweep_camera

    def _a2_video_frame_for_candidate(self, candidate_name: str) -> torch.Tensor:
        camera = self._a2_camera_for_candidate(candidate_name)
        rgb = camera.data.output["rgb"]
        expected_shape = (self.num_envs, camera.cfg.height, camera.cfg.width, 3)
        if tuple(rgb.shape) != expected_shape or rgb.dtype != torch.uint8:
            raise RuntimeError(
                f"candidate video RGB drift: {tuple(rgb.shape)}/{rgb.dtype}"
            )
        return rgb[self._a2_camera_sweep_video_env_id]

    def _append_a2_camera_candidate_video_frame(self, candidate_name: str):
        frame = (
            self._a2_video_frame_for_candidate(candidate_name)
            .detach()
            .contiguous()
            .cpu()
            .numpy()
        )
        writer = self._a2_camera_sweep_video_writers.get(candidate_name)
        if writer is None:
            temporary_path = (
                self._a2_camera_sweep_video_output_dir
                / f"{candidate_name}_env{self._a2_camera_sweep_video_env_id:04d}.writing.mp4"
            )
            final_path = (
                self._a2_camera_sweep_video_output_dir
                / f"{candidate_name}_env{self._a2_camera_sweep_video_env_id:04d}.mp4"
            )
            if temporary_path.exists() or final_path.exists():
                raise FileExistsError(
                    f"refusing to overwrite candidate video: {candidate_name}"
                )
            writer = imageio.get_writer(
                str(temporary_path),
                fps=self._a2_camera_sweep_video_fps,
                codec="libx264",
                macro_block_size=2,
            )
            self._a2_camera_sweep_video_writers[candidate_name] = writer
            self._a2_camera_sweep_video_temporary_paths[candidate_name] = temporary_path
            self._a2_camera_sweep_video_final_paths[candidate_name] = final_path
        writer.append_data(frame)
        self._a2_camera_sweep_video_frame_counts[candidate_name] += 1

    def _seal_a2_camera_candidate_videos(self) -> dict[str, str]:
        if self._a2_camera_sweep_videos_sealed:
            raise RuntimeError("camera candidate videos were already sealed")
        candidate_names = [
            candidate["name"]
            for candidate in self._a2_camera_sweep_candidates
        ]
        if set(self._a2_camera_sweep_video_writers) != set(candidate_names):
            raise RuntimeError("not every camera candidate opened a video writer")
        frame_counts = [
            self._a2_camera_sweep_video_frame_counts[name] for name in candidate_names
        ]
        if len(set(frame_counts)) != 1 or frame_counts[0] < 1:
            raise RuntimeError(
                f"candidate videos require equal positive frame counts: {frame_counts}"
            )
        missing_video_stages = [
            STAGE_NAMES[stage_index]
            for stage_index in self._a2_camera_sweep_ranking_stage_indices
            if self._a2_camera_sweep_video_stage_frame_counts[STAGE_NAMES[stage_index]] < 1
        ]
        if missing_video_stages:
            raise RuntimeError(
                f"candidate videos have no sampled frames for stages: {missing_video_stages}"
            )
        sealed = {}
        for candidate_name in candidate_names:
            writer = self._a2_camera_sweep_video_writers.pop(candidate_name)
            writer.close()
            temporary_path = self._a2_camera_sweep_video_temporary_paths[candidate_name]
            final_path = self._a2_camera_sweep_video_final_paths[candidate_name]
            if not temporary_path.is_file():
                raise FileNotFoundError(f"candidate video was not written: {temporary_path}")
            os.replace(temporary_path, final_path)
            if not final_path.is_file() or final_path.stat().st_size <= 0:
                raise RuntimeError(f"sealed candidate video is empty: {final_path}")
            sealed[candidate_name] = str(final_path)
        if any(path.exists() for path in self._a2_camera_sweep_video_temporary_paths.values()):
            raise RuntimeError("candidate video .writing files remain after seal")
        self._a2_camera_sweep_videos_sealed = True
        return sealed

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
        video_env_active = bool(
            active[self._a2_camera_sweep_video_env_id].detach().cpu().item()
        )
        video_stage_index = None
        if video_env_active:
            video_stage_index = int(
                self.stage_buf[self._a2_camera_sweep_video_env_id].detach().cpu().item()
            )
            if video_stage_index not in range(6):
                raise RuntimeError(f"video env stage index drift: {video_stage_index}")

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
                if video_env_active:
                    self._append_a2_camera_candidate_video_frame(
                        candidate["name"]
                    )
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
        if video_stage_index is not None:
            video_stage_name = STAGE_NAMES[video_stage_index]
            self._a2_camera_sweep_video_stage_frame_counts[video_stage_name] += 1
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

    def _a2_camera_visibility_metrics(self, camera) -> dict[str, object]:
        segmentation = camera.data.output["instance_id_segmentation_fast"]
        expected_shape = (self.num_envs, camera.cfg.height, camera.cfg.width, 1)
        if tuple(segmentation.shape) != expected_shape or segmentation.dtype != torch.int32:
            raise RuntimeError(
                "instance segmentation shape/dtype drift; "
                f"expected={expected_shape}/torch.int32, "
                f"got={tuple(segmentation.shape)}/{segmentation.dtype}"
            )
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
        margin_x = max(1, math.ceil(self.HANDLE_EDGE_MARGIN_FRACTION * camera.cfg.width))
        margin_y = max(1, math.ceil(self.HANDLE_EDGE_MARGIN_FRACTION * camera.cfg.height))
        handle_in_edge_band = (
            torch.any(handle_mask[:, :, :margin_x], dim=(1, 2))
            | torch.any(handle_mask[:, :, -margin_x:], dim=(1, 2))
            | torch.any(handle_mask[:, :margin_y, :], dim=(1, 2))
            | torch.any(handle_mask[:, -margin_y:, :], dim=(1, 2))
        )
        handle_edge_clear = visible["handle"] & ~handle_in_edge_band
        return {
            "pixel_counts": pixel_counts,
            "visible": visible,
            "handle_centered": handle_centered,
            "handle_edge_clear": handle_edge_clear,
            "trio_visible": visible["handle"] & visible["finger7"] & visible["finger8"],
        }

    def _accumulate_a2_camera_stats(
        self,
        stats_by_stage: dict[str, dict[str, object]],
        metrics: dict[str, object],
        active: torch.Tensor,
    ) -> None:
        visible = metrics["visible"]
        pixel_counts = metrics["pixel_counts"]
        handle_centered = metrics["handle_centered"]
        handle_edge_clear = metrics["handle_edge_clear"]
        trio_visible = metrics["trio_visible"]
        for stage_index in STAGE_NAMES:
            stage_mask = active if stage_index == 6 else active & (self.stage_buf == stage_index)
            count = int(stage_mask.sum().detach().cpu().item())
            if count == 0:
                continue
            stats = stats_by_stage[STAGE_NAMES[stage_index]]
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
            stats["handle_edge_clear_frames"] += self._masked_count(
                handle_edge_clear, stage_mask
            )
            stats["handle_visible_pixels"].extend(
                int(value)
                for value in pixel_counts["handle"][stage_mask].detach().cpu().tolist()
            )

    def _accumulate_a2_camera_candidate(self, candidate_name: str, active: torch.Tensor):
        camera = self._a2_camera_for_candidate(candidate_name)
        metrics = self._a2_camera_visibility_metrics(camera)
        self._accumulate_a2_camera_stats(
            self._a2_camera_sweep_stats[candidate_name], metrics, active
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

        ranking = rank_camera_candidates(
            candidate_summaries,
            ranking_stage_indices=self._a2_camera_sweep_ranking_stage_indices,
        )
        candidate_videos = self._seal_a2_camera_candidate_videos()
        recommended_video = candidate_videos[ranking["recommended_candidate"]]
        summary["a2_camera_pose_sweep"] = {
            "status": "SWEEP_COMPLETE",
            "architecture": (
                "one trunk camera; one sensor prim repositioned between same-step renders"
            ),
            "policy_driver": "sealed Teacher checkpoint; camera is diagnostic-only",
            "ranking_stage_indices": self._a2_camera_sweep_ranking_stage_indices,
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
            "handle_edge_margin_fraction": self.HANDLE_EDGE_MARGIN_FRACTION,
            "candidates": candidate_summaries,
            "recommendation": ranking,
            "candidate_videos": candidate_videos,
            "recommended_candidate_video": recommended_video,
            "candidate_video_metadata": {
                "env_id": self._a2_camera_sweep_video_env_id,
                "fps": self._a2_camera_sweep_video_fps,
                "frame_counts": self._a2_camera_sweep_video_frame_counts,
                "stage_frame_counts": self._a2_camera_sweep_video_stage_frame_counts,
                "sampling": (
                    "stage change or every configured control-step interval; not wall-clock"
                ),
            },
            "boundaries": [
                "nominal FoV-derived intrinsics are not a physical-camera calibration",
                (
                    "current rollout uses the right/out door asset and does not "
                    "validate left/right symmetry"
                ),
                (
                    "handle edge-clear requires the segmentation mask to avoid the outer "
                    "5 percent image band; it detects frame-edge clipping, not occlusion"
                ),
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


class DoorPregraspCameraSchemeC(DoorPregraspCameraPoseSweep):
    """Evaluate one fixed D435i variant and provisional A2 Head camera together."""

    SCHEME_VARIANT = "C"
    D435I_VIEW = "d435i_portrait_up12"
    HEAD_VIEW = "a2_head_context"
    UNION_VIEW = "scheme_c_union"
    D435I_HOUSING_ORIENTATION = "portrait_90_deg"
    D435I_SOFTWARE_UPRIGHTED = True
    D435I_POSITION_M = [0.28, 0.0, 0.25]
    D435I_ROTATION_WXYZ = [
        0.9945218953682733,
        0.0,
        -0.10452846326765347,
        0.0,
    ]
    D435I_RPY_DEG = [0.0, -12.0, 0.0]
    D435I_WIDTH = 216
    D435I_HEIGHT = 384
    D435I_PANEL_DESCRIPTION = "pillarboxed portrait D435i"
    HEAD_CAMERA_REQUIRED_METADATA = {}

    @classmethod
    def _parse_a2_camera_scheme_c_config(cls, config) -> dict[str, object]:
        raw_cfg = config.get("a2_camera_scheme_c", None)
        cfg = OmegaConf.to_container(raw_cfg, resolve=True)
        expected_keys = {
            "enabled",
            "ablation_id",
            "architecture",
            "view_order",
            "combined_video",
            "d435i_mount",
            "head_camera",
        }
        if not isinstance(cfg, dict) or set(cfg) != expected_keys:
            keys = None if not isinstance(cfg, dict) else sorted(cfg)
            raise RuntimeError(
                "a2_camera_scheme_c config schema mismatch; "
                f"expected={sorted(expected_keys)}, got={keys}"
            )
        if cfg["enabled"] is not True:
            raise RuntimeError("DoorPregraspCameraSchemeC requires enabled=true")
        if cfg["ablation_id"] != cls.SCHEME_VARIANT:
            raise RuntimeError(
                "scheme C ablation identity drift; "
                f"expected={cls.SCHEME_VARIANT!r}, got={cfg['ablation_id']!r}"
            )
        if cfg["view_order"] != [cls.D435I_VIEW, cls.HEAD_VIEW]:
            raise RuntimeError(
                "scheme C view_order must be exact D435i then A2 Head order"
            )
        combined = cfg["combined_video"]
        combined_keys = {"enabled", "env_id", "fps", "output_path"}
        if not isinstance(combined, dict) or set(combined) != combined_keys:
            raise RuntimeError("scheme C combined_video schema mismatch")
        if combined["enabled"] is not True:
            raise RuntimeError("scheme C requires the combined render video")
        for key in ("env_id", "fps"):
            value = combined[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeError(f"scheme C combined_video.{key} is invalid: {value!r}")
        if combined["fps"] < 1:
            raise RuntimeError("scheme C combined video fps must be positive")
        if not isinstance(combined["output_path"], str) or not combined["output_path"]:
            raise RuntimeError("scheme C combined video output_path must be non-empty")

        d435i_mount = cfg["d435i_mount"]
        d435i_keys = {
            "parent",
            "physical_housing_orientation",
            "software_uprighted_optical_frame",
            "position_m",
            "effective_optical_rpy_deg",
            "mechanical_clearance_status",
            "lateral_symmetry_contract",
        }
        if not isinstance(d435i_mount, dict) or set(d435i_mount) != d435i_keys:
            raise RuntimeError("scheme C d435i_mount schema mismatch")
        if (
            d435i_mount["parent"] != "trunk"
            or d435i_mount["physical_housing_orientation"]
            != cls.D435I_HOUSING_ORIENTATION
            or d435i_mount["software_uprighted_optical_frame"]
            is not cls.D435I_SOFTWARE_UPRIGHTED
            or d435i_mount["mechanical_clearance_status"] != "unverified"
            or d435i_mount["lateral_symmetry_contract"] != "centerline_y0_yaw0"
            or d435i_mount["position_m"] != cls.D435I_POSITION_M
            or d435i_mount["effective_optical_rpy_deg"] != cls.D435I_RPY_DEG
        ):
            raise RuntimeError("scheme C D435i mount/symmetry boundary drift")

        head = cfg["head_camera"]
        head_keys = {
            "sensor_name",
            "parent",
            "prim_suffix",
            "extrinsic_status",
            "position_m",
            "rotation_wxyz",
            "rpy_deg",
            "width",
            "height",
            "focal_length",
            "focus_distance",
            "horizontal_aperture",
            "vertical_aperture",
            "clipping_range",
            "update_period",
            "nominal_intrinsics",
        } | set(cls.HEAD_CAMERA_REQUIRED_METADATA)
        if not isinstance(head, dict) or set(head) != head_keys:
            raise RuntimeError("scheme C head_camera schema mismatch")
        if (
            head["sensor_name"] != cls.HEAD_VIEW
            or head["parent"] != "trunk"
            or head["prim_suffix"] != "a2_head_context_camera"
            or head["extrinsic_status"] != "provisional_not_cad_or_calibrated"
            or head["position_m"] != [0.32, 0.0, 0.25]
            or head["rotation_wxyz"]
            != [0.9945218953682733, 0.0, -0.10452846326765347, 0.0]
            or head["rpy_deg"] != [0.0, -12.0, 0.0]
        ):
            raise RuntimeError("scheme C A2 Head identity/extrinsic boundary drift")
        for key, expected_value in cls.HEAD_CAMERA_REQUIRED_METADATA.items():
            if head[key] != expected_value:
                raise RuntimeError(
                    "scheme C A2 Head semantic metadata drift; "
                    f"{key} expected={expected_value!r}, got={head[key]!r}"
                )
        for key, length in (
            ("position_m", 3),
            ("rotation_wxyz", 4),
            ("rpy_deg", 3),
            ("clipping_range", 2),
        ):
            value = head[key]
            if (
                not isinstance(value, list)
                or len(value) != length
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, (int, float))
                    or not math.isfinite(float(item))
                    for item in value
                )
            ):
                raise RuntimeError(f"scheme C head_camera.{key} is invalid: {value!r}")
        for key in ("width", "height"):
            value = head[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise RuntimeError(f"scheme C head_camera.{key} must be a positive int")
        for key in (
            "focal_length",
            "focus_distance",
            "horizontal_aperture",
            "vertical_aperture",
        ):
            value = head[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0.0
            ):
                raise RuntimeError(f"scheme C head_camera.{key} must be finite and positive")
        update_period = head["update_period"]
        if (
            isinstance(update_period, bool)
            or not isinstance(update_period, (int, float))
            or not math.isfinite(float(update_period))
            or float(update_period) < 0.0
        ):
            raise RuntimeError("scheme C head_camera.update_period is invalid")
        nominal = head["nominal_intrinsics"]
        nominal_keys = {
            "source",
            "native_resolution",
            "native_fov_deg",
            "diagnostic_resolution",
            "sim_fx_fy_cx_cy",
            "sim_effective_fov_deg",
        }
        if not isinstance(nominal, dict) or set(nominal) != nominal_keys:
            raise RuntimeError("scheme C head nominal_intrinsics schema mismatch")
        return cfg

    def scene_creation_callback(self, simulator):
        super().scene_creation_callback(simulator)
        cfg = self._parse_a2_camera_scheme_c_config(self.config)
        head = cfg["head_camera"]

        from isaaclab import sim as sim_utils
        from isaaclab.sensors.camera import TiledCamera, TiledCameraCfg

        sensor_name = head["sensor_name"]
        if sensor_name in simulator.scene.sensors:
            raise RuntimeError(f"scheme C head sensor already exists: {sensor_name}")
        head_cfg = TiledCameraCfg(
            prim_path=(
                f"/World/envs/env_.*/Robot/{head['parent']}/{head['prim_suffix']}"
            ),
            offset=TiledCameraCfg.OffsetCfg(
                pos=tuple(float(value) for value in head["position_m"]),
                rot=tuple(float(value) for value in head["rotation_wxyz"]),
                convention="world",
            ),
            data_types=["rgb", "instance_id_segmentation_fast"],
            spawn=sim_utils.PinholeCameraCfg(
                focal_length=float(head["focal_length"]),
                focus_distance=float(head["focus_distance"]),
                horizontal_aperture=float(head["horizontal_aperture"]),
                vertical_aperture=float(head["vertical_aperture"]),
                clipping_range=tuple(float(value) for value in head["clipping_range"]),
            ),
            width=int(head["width"]),
            height=int(head["height"]),
            update_period=float(head["update_period"]),
            colorize_instance_id_segmentation=False,
            debug_vis=True,
        )
        head_camera = TiledCamera(head_cfg)
        simulator.scene.sensors[sensor_name] = head_camera
        simulator.a2_head_context_camera = head_camera
        self._a2_scheme_c_cfg = cfg

    def init_a2_eval_stage2_step_trace(
        self,
        diagnostic_enabled: bool = False,
        diagnostic_reward_terms=(),
    ):
        super().init_a2_eval_stage2_step_trace(
            diagnostic_enabled=diagnostic_enabled,
            diagnostic_reward_terms=diagnostic_reward_terms,
        )
        cfg = getattr(self, "_a2_scheme_c_cfg", None)
        if not isinstance(cfg, dict):
            raise RuntimeError("scheme C scene callback did not seal its config")
        candidate_names = [
            candidate["name"] for candidate in self._a2_camera_sweep_candidates
        ]
        if candidate_names != cfg["view_order"]:
            raise RuntimeError(
                f"scheme C candidates/view_order mismatch: {candidate_names}"
            )
        candidate_by_name = {
            candidate["name"]: candidate
            for candidate in self._a2_camera_sweep_candidates
        }
        d435i_candidate = candidate_by_name[self.D435I_VIEW]
        if (
            d435i_candidate["position_m"] != self.D435I_POSITION_M
            or d435i_candidate["rotation_wxyz"] != self.D435I_ROTATION_WXYZ
            or d435i_candidate["rpy_deg"] != self.D435I_RPY_DEG
            or self._a2_camera_sweep_camera.cfg.width != self.D435I_WIDTH
            or self._a2_camera_sweep_camera.cfg.height != self.D435I_HEIGHT
        ):
            raise RuntimeError("scheme C D435i candidate/resolution boundary drift")
        head = cfg["head_camera"]
        head_candidate = candidate_by_name[self.HEAD_VIEW]
        if (
            head_candidate["position_m"] != head["position_m"]
            or head_candidate["rotation_wxyz"] != head["rotation_wxyz"]
            or head_candidate["rpy_deg"] != head["rpy_deg"]
        ):
            raise RuntimeError("scheme C A2 Head candidate/extrinsic boundary drift")
        head_camera = self.simulator.scene.sensors.get(self.HEAD_VIEW)
        if head_camera is None or head_camera is not getattr(
            self.simulator, "a2_head_context_camera", None
        ):
            raise RuntimeError("scheme C A2 Head camera is missing from scene sensors")
        head_rgb = head_camera.data.output.get("rgb")
        head_segmentation = head_camera.data.output.get(
            "instance_id_segmentation_fast"
        )
        if not torch.is_tensor(head_rgb) or not torch.is_tensor(head_segmentation):
            raise RuntimeError(
                "scheme C A2 Head camera did not initialize RGB and raw instance outputs"
            )
        expected_rgb_shape = (
            self.num_envs,
            int(head["height"]),
            int(head["width"]),
            3,
        )
        expected_segmentation_shape = (*expected_rgb_shape[:-1], 1)
        if tuple(head_rgb.shape) != expected_rgb_shape or head_rgb.dtype != torch.uint8:
            raise RuntimeError(
                "scheme C A2 Head RGB shape/dtype mismatch; "
                f"got={tuple(head_rgb.shape)}/{head_rgb.dtype}"
            )
        if (
            tuple(head_segmentation.shape) != expected_segmentation_shape
            or head_segmentation.dtype != torch.int32
        ):
            raise RuntimeError(
                "scheme C A2 Head segmentation shape/dtype mismatch; "
                f"got={tuple(head_segmentation.shape)}/{head_segmentation.dtype}"
            )
        expected_head_intrinsics = head_camera.data.intrinsic_matrices.new_tensor(
            head["nominal_intrinsics"]["sim_fx_fy_cx_cy"]
        )
        observed_head_intrinsics = head_camera.data.intrinsic_matrices[0]
        intrinsic_vector = torch.stack(
            [
                observed_head_intrinsics[0, 0],
                observed_head_intrinsics[1, 1],
                observed_head_intrinsics[0, 2],
                observed_head_intrinsics[1, 2],
            ]
        )
        head_intrinsic_error_px = float(
            torch.max(torch.abs(intrinsic_vector - expected_head_intrinsics))
            .detach()
            .cpu()
            .item()
        )
        if head_intrinsic_error_px > 1.0e-4:
            raise RuntimeError(
                "scheme C A2 Head runtime intrinsics mismatch; "
                f"max_error_px={head_intrinsic_error_px}"
            )
        self._a2_scheme_c_head_intrinsic_error_px = head_intrinsic_error_px
        self._a2_scheme_c_cameras = {
            self.D435I_VIEW: self._a2_camera_sweep_camera,
            self.HEAD_VIEW: head_camera,
        }
        self._a2_scheme_c_union_stats = {
            STAGE_NAMES[index]: self._new_camera_sweep_stage_stats()
            for index in STAGE_NAMES
        }
        combined = cfg["combined_video"]
        if combined["env_id"] != self._a2_camera_sweep_video_env_id:
            raise RuntimeError("scheme C combined and per-view video env ids must match")
        if combined["fps"] != self._a2_camera_sweep_video_fps:
            raise RuntimeError("scheme C combined and per-view video fps must match")
        final_path = Path(combined["output_path"]).resolve()
        temporary_path = final_path.with_name(
            f"{final_path.stem}.writing{final_path.suffix}"
        )
        if final_path.exists() or temporary_path.exists():
            raise FileExistsError(
                f"refusing to overwrite scheme C combined video: {final_path}"
            )
        final_path.parent.mkdir(parents=True, exist_ok=True)
        self._a2_scheme_c_combined_final_path = final_path
        self._a2_scheme_c_combined_temporary_path = temporary_path
        self._a2_scheme_c_combined_writer = None
        self._a2_scheme_c_combined_frame_count = 0
        self._a2_scheme_c_combined_video_sealed = False

    def _a2_camera_for_candidate(self, candidate_name: str):
        cameras = getattr(self, "_a2_scheme_c_cameras", None)
        if not isinstance(cameras, dict) or candidate_name not in cameras:
            raise KeyError(f"scheme C camera mapping is unavailable: {candidate_name}")
        return cameras[candidate_name]

    @staticmethod
    def _fit_a2_scheme_c_panel(frame: torch.Tensor) -> torch.Tensor:
        import torch.nn.functional as functional

        if frame.ndim != 3 or frame.shape[-1] != 3 or frame.dtype != torch.uint8:
            raise RuntimeError(
                f"scheme C panel frame must be uint8 HWC RGB; got {frame.shape}/{frame.dtype}"
            )
        target_height = 216
        target_width = 384
        source_height, source_width = int(frame.shape[0]), int(frame.shape[1])
        scale = min(target_height / source_height, target_width / source_width)
        resized_height = max(1, int(round(source_height * scale)))
        resized_width = max(1, int(round(source_width * scale)))
        resized = functional.interpolate(
            frame.permute(2, 0, 1).unsqueeze(0).float(),
            size=(resized_height, resized_width),
            mode="bilinear",
            align_corners=False,
        )[0].round().clamp(0, 255).to(torch.uint8).permute(1, 2, 0)
        panel = torch.zeros(
            (target_height, target_width, 3),
            dtype=torch.uint8,
            device=frame.device,
        )
        top = (target_height - resized_height) // 2
        left = (target_width - resized_width) // 2
        panel[top : top + resized_height, left : left + resized_width] = resized
        return panel

    def _append_a2_scheme_c_combined_frame(self) -> None:
        d435i_frame = self._a2_video_frame_for_candidate(self.D435I_VIEW)
        head_frame = self._a2_video_frame_for_candidate(self.HEAD_VIEW)
        combined = torch.cat(
            [
                self._fit_a2_scheme_c_panel(d435i_frame),
                self._fit_a2_scheme_c_panel(head_frame),
            ],
            dim=1,
        )
        if tuple(combined.shape) != (216, 768, 3):
            raise RuntimeError(f"scheme C combined frame shape drift: {combined.shape}")
        writer = self._a2_scheme_c_combined_writer
        if writer is None:
            writer = imageio.get_writer(
                str(self._a2_scheme_c_combined_temporary_path),
                fps=self._a2_camera_sweep_video_fps,
                codec="libx264",
                macro_block_size=2,
            )
            self._a2_scheme_c_combined_writer = writer
        writer.append_data(combined.detach().contiguous().cpu().numpy())
        self._a2_scheme_c_combined_frame_count += 1

    def _a2_scheme_c_combined_layout(self) -> str:
        return (
            f"left 384x216 {self.D435I_PANEL_DESCRIPTION}; "
            "right 384x216 letterboxed A2 Head"
        )

    def _capture_a2_camera_pose_sweep_sample(self, active: torch.Tensor):
        from isaaclab.utils.math import convert_camera_frame_orientation_convention

        simulator = self.simulator
        physics_step_before = int(simulator._sim_step_counter)
        video_env_active = bool(
            active[self._a2_camera_sweep_video_env_id].detach().cpu().item()
        )
        video_stage_index = None
        if video_env_active:
            video_stage_index = int(
                self.stage_buf[self._a2_camera_sweep_video_env_id]
                .detach()
                .cpu()
                .item()
            )
            if video_stage_index not in range(6):
                raise RuntimeError(f"scheme C video env stage drift: {video_stage_index}")

        frame_before = {
            name: camera.frame.clone()
            for name, camera in self._a2_scheme_c_cameras.items()
        }
        simulator.sim.render()
        metrics_by_view = {}
        first_rgb = {}
        candidate_by_name = {
            candidate["name"]: candidate
            for candidate in self._a2_camera_sweep_candidates
        }
        for name in self._a2_scheme_c_cfg["view_order"]:
            camera = self._a2_scheme_c_cameras[name]
            camera.update(dt=0.0, force_recompute=True)
            if not torch.equal(camera.frame, frame_before[name] + 1):
                raise RuntimeError(
                    f"scheme C {name} render must advance exactly one sensor frame"
                )
            if int(simulator._sim_step_counter) != physics_step_before:
                raise RuntimeError("scheme C camera update advanced physics")
            candidate = candidate_by_name[name]
            expected_pos = camera.data.intrinsic_matrices.new_tensor(
                candidate["position_m"]
            ).reshape(1, 3).expand(self.num_envs, -1)
            expected_quat = camera.data.intrinsic_matrices.new_tensor(
                candidate["rotation_wxyz"]
            ).reshape(1, 4).expand(self.num_envs, -1)
            expected_quat_opengl = convert_camera_frame_orientation_convention(
                expected_quat, origin="world", target="opengl"
            )
            observed_pos, observed_quat_opengl = camera._view.get_local_poses()
            self._assert_a2_camera_pose(
                observed_pos,
                observed_quat_opengl,
                expected_pos,
                expected_quat_opengl,
                context=f"scheme C {name}",
            )
            metrics = self._a2_camera_visibility_metrics(camera)
            metrics_by_view[name] = metrics
            self._accumulate_a2_camera_stats(
                self._a2_camera_sweep_stats[name], metrics, active
            )
            if video_env_active:
                self._append_a2_camera_candidate_video_frame(name)
            if self._a2_camera_sweep_sample_events == 0:
                first_rgb[name] = camera.data.output["rgb"].clone()

        ordered_metrics = [
            metrics_by_view[name] for name in self._a2_scheme_c_cfg["view_order"]
        ]
        union_visible = {
            target: torch.stack(
                [metrics["visible"][target] for metrics in ordered_metrics], dim=0
            ).any(dim=0)
            for target in TARGET_NAMES
        }
        union_metrics = {
            "visible": union_visible,
            "pixel_counts": {
                target: torch.stack(
                    [metrics["pixel_counts"][target] for metrics in ordered_metrics],
                    dim=0,
                ).amax(dim=0)
                for target in TARGET_NAMES
            },
            "handle_centered": torch.stack(
                [metrics["handle_centered"] for metrics in ordered_metrics], dim=0
            ).any(dim=0),
            "handle_edge_clear": torch.stack(
                [metrics["handle_edge_clear"] for metrics in ordered_metrics], dim=0
            ).any(dim=0),
            "trio_visible": torch.stack(
                [metrics["trio_visible"] for metrics in ordered_metrics], dim=0
            ).any(dim=0),
        }
        self._accumulate_a2_camera_stats(
            self._a2_scheme_c_union_stats, union_metrics, active
        )
        if video_env_active:
            self._append_a2_scheme_c_combined_frame()
        if self._a2_camera_sweep_sample_events == 0:
            same_shape_pairs = [
                (left_name, right_name)
                for index, left_name in enumerate(self._a2_scheme_c_cfg["view_order"])
                for right_name in self._a2_scheme_c_cfg["view_order"][index + 1 :]
                if first_rgb[left_name].shape == first_rgb[right_name].shape
            ]
            if any(
                torch.equal(first_rgb[left_name], first_rgb[right_name])
                for left_name, right_name in same_shape_pairs
            ):
                raise RuntimeError("scheme C distinct cameras rendered identical RGB")
            self._a2_camera_sweep_pose_diversity_validated = True
        if video_stage_index is not None:
            self._a2_camera_sweep_video_stage_frame_counts[
                STAGE_NAMES[video_stage_index]
            ] += 1
        self._a2_camera_sweep_sample_events += 1
        if int(simulator._sim_step_counter) != physics_step_before:
            raise RuntimeError("scheme C same-step capture changed physics counter")

    def _seal_a2_scheme_c_combined_video(self) -> str:
        if self._a2_scheme_c_combined_video_sealed:
            raise RuntimeError("scheme C combined video was already sealed")
        if self._a2_scheme_c_combined_writer is None:
            raise RuntimeError("scheme C combined video writer was never opened")
        individual_counts = set(self._a2_camera_sweep_video_frame_counts.values())
        if individual_counts != {self._a2_scheme_c_combined_frame_count}:
            raise RuntimeError(
                "scheme C combined/per-view frame counts differ; "
                f"combined={self._a2_scheme_c_combined_frame_count}, "
                f"per_view={self._a2_camera_sweep_video_frame_counts}"
            )
        self._a2_scheme_c_combined_writer.close()
        self._a2_scheme_c_combined_writer = None
        if not self._a2_scheme_c_combined_temporary_path.is_file():
            raise FileNotFoundError("scheme C combined temporary video is missing")
        os.replace(
            self._a2_scheme_c_combined_temporary_path,
            self._a2_scheme_c_combined_final_path,
        )
        if (
            not self._a2_scheme_c_combined_final_path.is_file()
            or self._a2_scheme_c_combined_final_path.stat().st_size <= 0
        ):
            raise RuntimeError("scheme C combined video is empty")
        self._a2_scheme_c_combined_video_sealed = True
        return str(self._a2_scheme_c_combined_final_path)

    def _summarize_a2_scheme_c_union(self) -> dict[str, object]:
        stages = {}
        for stage_name, raw_stats in self._a2_scheme_c_union_stats.items():
            stats = dict(raw_stats)
            pixels = stats.pop("handle_visible_pixels")
            sampled = stats["sampled_frames"]
            if len(pixels) != sampled:
                raise RuntimeError(
                    f"scheme C union {stage_name} pixel/sample mismatch"
                )
            for key, value in tuple(stats.items()):
                if key != "sampled_frames":
                    stats[key.replace("_frames", "_rate")] = (
                        None if sampled == 0 else value / sampled
                    )
            stats["handle_visible_pixels_p05"] = self._integer_quantile(
                pixels, 0.05
            )
            stats["handle_visible_pixels_p50"] = self._integer_quantile(
                pixels, 0.50
            )
            stages[stage_name] = stats
        return {"name": self.UNION_VIEW, "stages": stages}

    def get_eval_metrics_summary(self):
        summary = super().get_eval_metrics_summary()
        sweep = summary.get("a2_camera_pose_sweep")
        if not isinstance(sweep, dict) or sweep.get("status") != "SWEEP_COMPLETE":
            raise RuntimeError("scheme C requires a completed per-view sweep summary")
        combined_video = self._seal_a2_scheme_c_combined_video()
        union = self._summarize_a2_scheme_c_union()
        union_ranking = rank_camera_candidates(
            [union],
            ranking_stage_indices=self._a2_camera_sweep_ranking_stage_indices,
        )
        per_view = {candidate["name"]: candidate for candidate in sweep["candidates"]}
        if set(per_view) != set(self._a2_scheme_c_cfg["view_order"]):
            raise RuntimeError(f"scheme C per-view summary mismatch: {sorted(per_view)}")
        sweep["architecture"] = (
            f"{len(self._a2_scheme_c_cfg['view_order'])} fixed trunk-attached "
            "TiledCamera sensors rendered at one physics step"
        )
        sweep["policy_driver"] = (
            "sealed Teacher checkpoint; both cameras are diagnostic-only"
        )
        summary["a2_camera_scheme_c"] = {
            "status": "SCHEME_C_COMPLETE",
            "ablation_id": self.SCHEME_VARIANT,
            "training_performed": False,
            "architecture": self._a2_scheme_c_cfg["architecture"],
            "view_order": self._a2_scheme_c_cfg["view_order"],
            "d435i_mount": self._a2_scheme_c_cfg["d435i_mount"],
            "head_camera": self._a2_scheme_c_cfg["head_camera"],
            "head_extrinsic_status": self._a2_scheme_c_cfg["head_camera"][
                "extrinsic_status"
            ],
            "per_view": per_view,
            "combined_visibility": union,
            "combined_visibility_ranking": union_ranking,
            "combined_video": combined_video,
            "combined_video_metadata": {
                "env_id": self._a2_camera_sweep_video_env_id,
                "fps": self._a2_camera_sweep_video_fps,
                "frame_count": self._a2_scheme_c_combined_frame_count,
                "layout": self._a2_scheme_c_combined_layout(),
                "stage_frame_counts": self._a2_camera_sweep_video_stage_frame_counts,
            },
            "runtime_intrinsic_max_error_px": max(
                self._a2_camera_sweep_intrinsic_error_px,
                self._a2_scheme_c_head_intrinsic_error_px,
            ),
            "physics_advanced_between_views": False,
            "conservative_trio_contract": (
                "handle plus both fingers must be visible in at least one single view"
            ),
            "boundaries": [
                "A2 Head optical extrinsic is provisional, not CAD or calibrated",
                "A2 Head wide optics are represented by a diagnostic pinhole approximation",
                "D435i RGB distortion, rolling shutter, latency, and exposure are not simulated",
                "right/out rollout does not validate mirrored left/out",
                "production Student observation and model are unchanged",
            ],
        }
        return summary


class DoorPregraspCameraSchemeCA(DoorPregraspCameraSchemeC):
    """C-A ablation: landscape D435i at a 45-degree upward pitch."""

    SCHEME_VARIANT = "C-A"
    D435I_VIEW = "d435i_landscape_up45"
    D435I_HOUSING_ORIENTATION = "landscape_0_deg"
    D435I_SOFTWARE_UPRIGHTED = False
    D435I_POSITION_M = [0.28, 0.0, 0.25]
    D435I_ROTATION_WXYZ = [
        0.9238795325112867,
        0.0,
        -0.3826834323650898,
        0.0,
    ]
    D435I_RPY_DEG = [0.0, -45.0, 0.0]
    D435I_WIDTH = 384
    D435I_HEIGHT = 216
    D435I_PANEL_DESCRIPTION = "landscape D435i"


class DoorPregraspCameraSchemeCB(DoorPregraspCameraSchemeC):
    """C-B ablation: landscape D435i at a 60-degree upward pitch."""

    SCHEME_VARIANT = "C-B"
    D435I_VIEW = "d435i_landscape_up60"
    D435I_HOUSING_ORIENTATION = "landscape_0_deg"
    D435I_SOFTWARE_UPRIGHTED = False
    D435I_POSITION_M = [0.26, 0.0, 0.215]
    D435I_ROTATION_WXYZ = [
        0.8660254037844386,
        0.0,
        -0.5,
        0.0,
    ]
    D435I_RPY_DEG = [0.0, -60.0, 0.0]
    D435I_WIDTH = 384
    D435I_HEIGHT = 216
    D435I_PANEL_DESCRIPTION = "landscape D435i"
    HEAD_CAMERA_REQUIRED_METADATA = {
        "role": "fixed_oem_context",
        "optimize_pose": False,
        "oem_extrinsic_status": "measured_required",
        "simulation_extrinsic_role": "historical_provisional_diagnostic_only",
    }


class DoorPregraspCameraSchemeCBDualPortraitOEM(DoorPregraspCameraSchemeC):
    """C-B2: symmetric portrait RGB-D pair plus the official A2 Head pose."""

    SCHEME_VARIANT = "C-B2-DUAL-PORTRAIT-OEM"
    D435I_VIEW = "d435i_left_portrait_up60_toein15"
    RIGHT_D435I_VIEW = "d435i_right_portrait_up60_toein15"
    HEAD_VIEW = "a2_head_oem"
    UNION_VIEW = "scheme_c_b2_union"
    D435I_POSITION_M = [0.215, 0.095, 0.165]
    D435I_ROTATION_WXYZ = [
        0.858616436,
        -0.065263096,
        -0.495722431,
        -0.113038999,
    ]
    D435I_RPY_DEG = [0.0, -60.0, -15.0]
    D435I_WIDTH = 216
    D435I_HEIGHT = 384
    D435I_PANEL_DESCRIPTION = "raw left portrait D435i"
    RIGHT_POSITION_M = [0.215, -0.095, 0.165]
    RIGHT_ROTATION_WXYZ = [
        0.858616436,
        0.065263096,
        -0.495722431,
        0.113038999,
    ]
    RIGHT_RPY_DEG = [0.0, -60.0, 15.0]
    HEAD_POSITION_M = [0.3381, 0.0336, 0.0525]
    HEAD_ROTATION_WXYZ = [1.0, 0.0, 0.0, 0.0]
    HEAD_RPY_DEG = [0.0, 0.0, 0.0]
    D435I_INTRINSICS = [277.72153927108553, 277.72153927108553, 108.0, 192.0]

    @classmethod
    def _parse_a2_camera_scheme_c_config(cls, config) -> dict[str, object]:
        raw_cfg = config.get("a2_camera_scheme_c", None)
        cfg = OmegaConf.to_container(raw_cfg, resolve=True)
        expected_keys = {
            "enabled",
            "ablation_id",
            "architecture",
            "view_order",
            "combined_video",
            "d435i_pair",
            "panorama",
            "head_camera",
        }
        if not isinstance(cfg, dict) or set(cfg) != expected_keys:
            keys = None if not isinstance(cfg, dict) else sorted(cfg)
            raise RuntimeError(
                "C-B2 config schema mismatch; "
                f"expected={sorted(expected_keys)}, got={keys}"
            )
        expected_order = [cls.D435I_VIEW, cls.RIGHT_D435I_VIEW, cls.HEAD_VIEW]
        if (
            cfg["enabled"] is not True
            or cfg["ablation_id"] != cls.SCHEME_VARIANT
            or cfg["view_order"] != expected_order
            or not isinstance(cfg["architecture"], str)
            or not cfg["architecture"]
        ):
            raise RuntimeError("C-B2 identity, architecture, or view_order drift")

        combined = cfg["combined_video"]
        if not isinstance(combined, dict) or set(combined) != {
            "enabled",
            "env_id",
            "fps",
            "output_path",
        }:
            raise RuntimeError("C-B2 combined_video schema mismatch")
        if (
            combined["enabled"] is not True
            or isinstance(combined["env_id"], bool)
            or not isinstance(combined["env_id"], int)
            or combined["env_id"] < 0
            or isinstance(combined["fps"], bool)
            or not isinstance(combined["fps"], int)
            or combined["fps"] < 1
            or not isinstance(combined["output_path"], str)
            or not combined["output_path"]
        ):
            raise RuntimeError("C-B2 combined_video values are invalid")

        pair = cfg["d435i_pair"]
        pair_keys = {
            "parent",
            "physical_housing_orientation",
            "software_uprighted_optical_frame",
            "rgb_native_fov_hv_deg",
            "rgb_portrait_fov_hv_deg",
            "width",
            "height",
            "focal_length",
            "focus_distance",
            "horizontal_aperture",
            "vertical_aperture",
            "clipping_range",
            "update_period",
            "mechanical_clearance_status",
            "lateral_symmetry_contract",
            "nominal_baseline_m",
            "nominal_overlap_deg",
            "left",
            "right",
        }
        if not isinstance(pair, dict) or set(pair) != pair_keys:
            raise RuntimeError("C-B2 d435i_pair schema mismatch")
        if (
            pair["parent"] != "trunk"
            or pair["physical_housing_orientation"]
            != "portrait_plus90_deg_identical_roll"
            or pair["software_uprighted_optical_frame"] is not True
            or pair["rgb_native_fov_hv_deg"] != [69.4, 42.5]
            or pair["rgb_portrait_fov_hv_deg"] != [42.5, 69.4]
            or pair["width"] != cls.D435I_WIDTH
            or pair["height"] != cls.D435I_HEIGHT
            or pair["mechanical_clearance_status"]
            != "step_point_cloud_estimate_only_cad_boolean_required"
            or pair["lateral_symmetry_contract"]
            != "left_y_plus_yaw_minus_right_y_minus_yaw_plus"
            or pair["nominal_baseline_m"] != 0.19
            or pair["nominal_overlap_deg"] != 12.5
        ):
            raise RuntimeError("C-B2 D435i optical/mechanical identity drift")
        for key in (
            "focal_length",
            "focus_distance",
            "horizontal_aperture",
            "vertical_aperture",
        ):
            value = pair[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0.0
            ):
                raise RuntimeError(f"C-B2 d435i_pair.{key} must be finite and positive")
        if pair["clipping_range"] != [0.1, 20.0] or pair["update_period"] != 0.0:
            raise RuntimeError("C-B2 D435i clipping/update contract drift")
        expected_camera_keys = {
            "sensor_name",
            "prim_suffix",
            "position_m",
            "rotation_wxyz",
            "rpy_deg",
        }
        expected_cameras = {
            "left": (
                cls.D435I_VIEW,
                "d435i_left_portrait_camera",
                cls.D435I_POSITION_M,
                cls.D435I_ROTATION_WXYZ,
                cls.D435I_RPY_DEG,
            ),
            "right": (
                cls.RIGHT_D435I_VIEW,
                "d435i_right_portrait_camera",
                cls.RIGHT_POSITION_M,
                cls.RIGHT_ROTATION_WXYZ,
                cls.RIGHT_RPY_DEG,
            ),
        }
        for side, expected in expected_cameras.items():
            camera = pair[side]
            if not isinstance(camera, dict) or set(camera) != expected_camera_keys:
                raise RuntimeError(f"C-B2 {side} D435i schema mismatch")
            observed = (
                camera["sensor_name"],
                camera["prim_suffix"],
                camera["position_m"],
                camera["rotation_wxyz"],
                camera["rpy_deg"],
            )
            if observed != expected:
                raise RuntimeError(f"C-B2 {side} D435i pose identity drift")

        panorama = cfg["panorama"]
        panorama_keys = {
            "projection",
            "stitch_mode",
            "invalid_depth_fallback",
            "depth_source",
            "minimum_depth_m",
            "maximum_depth_m",
            "output_resolution",
            "horizontal_fov_deg",
            "vertical_fov_deg",
            "validity_mask_per_frame",
            "virtual_camera",
            "output_path",
        }
        if not isinstance(panorama, dict) or set(panorama) != panorama_keys:
            raise RuntimeError("C-B2 panorama schema mismatch")
        if (
            panorama["projection"] != "cylindrical_depth_aware"
            or panorama["stitch_mode"] != "z_buffer_no_rgb_averaging"
            or panorama["invalid_depth_fallback"]
            != "best_single_view_fixed_geometry"
            or panorama["depth_source"] != "distance_to_image_plane"
            or panorama["minimum_depth_m"] != 0.28
            or panorama["maximum_depth_m"] != 20.0
            or panorama["output_resolution"] != [384, 416]
            or panorama["horizontal_fov_deg"] != 72.5
            or panorama["vertical_fov_deg"] != 69.4
            or panorama["validity_mask_per_frame"] is not True
            or not isinstance(panorama["output_path"], str)
            or not panorama["output_path"]
        ):
            raise RuntimeError("C-B2 panorama contract drift")
        virtual = panorama["virtual_camera"]
        if not isinstance(virtual, dict) or set(virtual) != {
            "position_m",
            "rotation_wxyz",
            "rpy_deg",
        }:
            raise RuntimeError("C-B2 virtual camera schema mismatch")
        if (
            virtual["position_m"] != [0.215, 0.0, 0.165]
            or virtual["rotation_wxyz"]
            != [0.8660254037844386, 0.0, -0.5, 0.0]
            or virtual["rpy_deg"] != [0.0, -60.0, 0.0]
        ):
            raise RuntimeError("C-B2 virtual camera pose drift")

        head = cfg["head_camera"]
        head_keys = {
            "sensor_name",
            "parent",
            "prim_suffix",
            "role",
            "optimize_pose",
            "extrinsic_status",
            "position_m",
            "rotation_wxyz",
            "rpy_deg",
            "width",
            "height",
            "focal_length",
            "focus_distance",
            "horizontal_aperture",
            "vertical_aperture",
            "clipping_range",
            "update_period",
            "nominal_intrinsics",
        }
        if not isinstance(head, dict) or set(head) != head_keys:
            raise RuntimeError("C-B2 A2 Head schema mismatch")
        if (
            head["sensor_name"] != cls.HEAD_VIEW
            or head["parent"] != "trunk"
            or head["prim_suffix"] != "a2_head_oem_camera"
            or head["role"] != "fixed_oem_context"
            or head["optimize_pose"] is not False
            or head["extrinsic_status"] != "official_unitree_a2_urdf_camera_link"
            or head["position_m"] != cls.HEAD_POSITION_M
            or head["rotation_wxyz"] != cls.HEAD_ROTATION_WXYZ
            or head["rpy_deg"] != cls.HEAD_RPY_DEG
            or head["width"] != 384
            or head["height"] != 136
            or head["clipping_range"] != [0.1, 20.0]
            or head["update_period"] != 0.0
        ):
            raise RuntimeError("C-B2 official A2 Head pose or sensor identity drift")
        nominal = head["nominal_intrinsics"]
        if not isinstance(nominal, dict) or set(nominal) != {
            "source",
            "native_resolution",
            "native_fov_deg",
            "diagnostic_resolution",
            "sim_fx_fy_cx_cy",
            "sim_effective_fov_deg",
        }:
            raise RuntimeError("C-B2 A2 Head nominal_intrinsics schema mismatch")
        cfg["d435i_mount"] = pair
        return cfg

    def scene_creation_callback(self, simulator):
        super().scene_creation_callback(simulator)
        cfg = self._a2_scheme_c_cfg
        pair = cfg["d435i_pair"]
        right = pair["right"]

        from isaaclab import sim as sim_utils
        from isaaclab.sensors.camera import TiledCamera, TiledCameraCfg

        sensor_name = right["sensor_name"]
        if sensor_name in simulator.scene.sensors:
            raise RuntimeError(f"C-B2 right D435i sensor already exists: {sensor_name}")
        right_cfg = TiledCameraCfg(
            prim_path=(
                f"/World/envs/env_.*/Robot/{pair['parent']}/{right['prim_suffix']}"
            ),
            offset=TiledCameraCfg.OffsetCfg(
                pos=tuple(float(value) for value in right["position_m"]),
                rot=tuple(float(value) for value in right["rotation_wxyz"]),
                convention="world",
            ),
            data_types=[
                "rgb",
                "distance_to_image_plane",
                "instance_id_segmentation_fast",
            ],
            spawn=sim_utils.PinholeCameraCfg(
                focal_length=float(pair["focal_length"]),
                focus_distance=float(pair["focus_distance"]),
                horizontal_aperture=float(pair["horizontal_aperture"]),
                vertical_aperture=float(pair["vertical_aperture"]),
                clipping_range=tuple(float(value) for value in pair["clipping_range"]),
            ),
            width=int(pair["width"]),
            height=int(pair["height"]),
            update_period=float(pair["update_period"]),
            colorize_instance_id_segmentation=False,
            debug_vis=True,
        )
        right_camera = TiledCamera(right_cfg)
        simulator.scene.sensors[sensor_name] = right_camera
        simulator.a2_d435i_right_portrait_camera = right_camera

    def init_a2_eval_stage2_step_trace(
        self,
        diagnostic_enabled: bool = False,
        diagnostic_reward_terms=(),
    ):
        super().init_a2_eval_stage2_step_trace(
            diagnostic_enabled=diagnostic_enabled,
            diagnostic_reward_terms=diagnostic_reward_terms,
        )
        right_camera = self.simulator.scene.sensors.get(self.RIGHT_D435I_VIEW)
        if right_camera is None or right_camera is not getattr(
            self.simulator, "a2_d435i_right_portrait_camera", None
        ):
            raise RuntimeError("C-B2 right D435i is missing from scene sensors")
        left_camera = self._a2_camera_sweep_camera
        for name, camera in (
            (self.D435I_VIEW, left_camera),
            (self.RIGHT_D435I_VIEW, right_camera),
        ):
            rgb = camera.data.output.get("rgb")
            depth = camera.data.output.get("distance_to_image_plane")
            segmentation = camera.data.output.get("instance_id_segmentation_fast")
            if (
                not torch.is_tensor(rgb)
                or tuple(rgb.shape) != (self.num_envs, 384, 216, 3)
                or rgb.dtype != torch.uint8
                or not torch.is_tensor(depth)
                or tuple(depth.shape) != (self.num_envs, 384, 216, 1)
                or depth.dtype != torch.float32
                or not torch.is_tensor(segmentation)
                or tuple(segmentation.shape) != (self.num_envs, 384, 216, 1)
                or segmentation.dtype != torch.int32
            ):
                raise RuntimeError(
                    f"C-B2 {name} RGB-D/segmentation output contract mismatch"
                )
        observed = right_camera.data.intrinsic_matrices[0]
        expected = observed.new_tensor(self.D435I_INTRINSICS)
        observed_vector = torch.stack(
            [observed[0, 0], observed[1, 1], observed[0, 2], observed[1, 2]]
        )
        right_intrinsic_error = float(
            torch.max(torch.abs(observed_vector - expected)).detach().cpu().item()
        )
        if right_intrinsic_error > 1.0e-4:
            raise RuntimeError(
                "C-B2 right D435i runtime intrinsics mismatch; "
                f"max_error_px={right_intrinsic_error}"
            )
        self._a2_scheme_c_b2_right_intrinsic_error_px = right_intrinsic_error
        self._a2_scheme_c_cameras[self.RIGHT_D435I_VIEW] = right_camera

        from isaaclab.utils import math as math_utils

        pair = self._a2_scheme_c_cfg["d435i_pair"]
        panorama = self._a2_scheme_c_cfg["panorama"]
        virtual = panorama["virtual_camera"]
        matrix_template = observed
        virtual_quat_world = matrix_template.new_tensor(virtual["rotation_wxyz"]).reshape(1, 4)
        virtual_quat_ros = math_utils.convert_camera_frame_orientation_convention(
            virtual_quat_world,
            origin="world",
            target="ros",
        )[0]
        rotation_trunk_from_virtual = math_utils.matrix_from_quat(virtual_quat_ros)
        virtual_position = matrix_template.new_tensor(virtual["position_m"])
        self._a2_scheme_c_b2_source_transforms = {}
        for side in ("left", "right"):
            camera_cfg = pair[side]
            source_quat_world = matrix_template.new_tensor(
                camera_cfg["rotation_wxyz"]
            ).reshape(1, 4)
            source_quat_ros = math_utils.convert_camera_frame_orientation_convention(
                source_quat_world,
                origin="world",
                target="ros",
            )[0]
            rotation_trunk_from_source = math_utils.matrix_from_quat(source_quat_ros)
            rotation_virtual_from_source = (
                rotation_trunk_from_virtual.transpose(0, 1)
                @ rotation_trunk_from_source
            )
            translation_virtual_from_source = (
                rotation_trunk_from_virtual.transpose(0, 1)
                @ (
                    matrix_template.new_tensor(camera_cfg["position_m"])
                    - virtual_position
                )
            )
            self._a2_scheme_c_b2_source_transforms[side] = (
                rotation_virtual_from_source,
                translation_virtual_from_source,
            )

        panorama_path = Path(panorama["output_path"]).resolve()
        panorama_temporary_path = panorama_path.with_name(
            f"{panorama_path.stem}.writing{panorama_path.suffix}"
        )
        if panorama_path.exists() or panorama_temporary_path.exists():
            raise FileExistsError(
                f"refusing to overwrite C-B2 panorama video: {panorama_path}"
            )
        panorama_path.parent.mkdir(parents=True, exist_ok=True)
        self._a2_scheme_c_b2_panorama_final_path = panorama_path
        self._a2_scheme_c_b2_panorama_temporary_path = panorama_temporary_path
        self._a2_scheme_c_b2_panorama_writer = None
        self._a2_scheme_c_b2_panorama_frame_count = 0
        self._a2_scheme_c_b2_panorama_video_sealed = False
        self._a2_scheme_c_b2_panorama_totals = {
            "valid_input_depth_pixels": 0,
            "projected_depth_samples": 0,
            "depth_fused_output_pixels": 0,
            "fallback_output_pixels": 0,
            "empty_output_pixels": 0,
        }
        self._a2_scheme_c_b2_pair_frame_delta_max = 0

    @staticmethod
    def _fit_a2_scheme_c_b2_panel(
        frame: torch.Tensor,
        *,
        target_height: int,
        target_width: int,
    ) -> torch.Tensor:
        import torch.nn.functional as functional

        if frame.ndim != 3 or frame.shape[-1] != 3 or frame.dtype != torch.uint8:
            raise RuntimeError(
                f"C-B2 panel frame must be uint8 HWC RGB; got {frame.shape}/{frame.dtype}"
            )
        source_height, source_width = int(frame.shape[0]), int(frame.shape[1])
        scale = min(target_height / source_height, target_width / source_width)
        resized_height = max(1, int(round(source_height * scale)))
        resized_width = max(1, int(round(source_width * scale)))
        resized = functional.interpolate(
            frame.permute(2, 0, 1).unsqueeze(0).float(),
            size=(resized_height, resized_width),
            mode="bilinear",
            align_corners=False,
        )[0].round().clamp(0, 255).to(torch.uint8).permute(1, 2, 0)
        panel = torch.zeros(
            (target_height, target_width, 3),
            dtype=torch.uint8,
            device=frame.device,
        )
        top = (target_height - resized_height) // 2
        left = (target_width - resized_width) // 2
        panel[top : top + resized_height, left : left + resized_width] = resized
        return panel

    def _append_a2_scheme_c_combined_frame(self) -> None:
        video_env_id = self._a2_camera_sweep_video_env_id
        left_camera = self._a2_scheme_c_cameras[self.D435I_VIEW]
        right_camera = self._a2_scheme_c_cameras[self.RIGHT_D435I_VIEW]
        head_camera = self._a2_scheme_c_cameras[self.HEAD_VIEW]
        sensor_frames = [
            int(camera.frame[video_env_id].detach().cpu().item())
            for camera in (left_camera, right_camera, head_camera)
        ]
        frame_delta = max(sensor_frames) - min(sensor_frames)
        self._a2_scheme_c_b2_pair_frame_delta_max = max(
            self._a2_scheme_c_b2_pair_frame_delta_max,
            frame_delta,
        )
        if frame_delta != 0:
            raise RuntimeError(
                f"C-B2 same-render sensor frame mismatch: {sensor_frames}"
            )
        left_rotation, left_translation = self._a2_scheme_c_b2_source_transforms[
            "left"
        ]
        right_rotation, right_translation = self._a2_scheme_c_b2_source_transforms[
            "right"
        ]
        panorama_cfg = self._a2_scheme_c_cfg["panorama"]
        result = depth_aware_cylindrical_panorama(
            left_rgb=left_camera.data.output["rgb"][video_env_id],
            left_depth=left_camera.data.output["distance_to_image_plane"][video_env_id],
            left_intrinsics=left_camera.data.intrinsic_matrices[video_env_id],
            left_rotation_virtual_from_source=left_rotation,
            left_translation_virtual_from_source=left_translation,
            right_rgb=right_camera.data.output["rgb"][video_env_id],
            right_depth=right_camera.data.output["distance_to_image_plane"][video_env_id],
            right_intrinsics=right_camera.data.intrinsic_matrices[video_env_id],
            right_rotation_virtual_from_source=right_rotation,
            right_translation_virtual_from_source=right_translation,
            output_height=int(panorama_cfg["output_resolution"][0]),
            output_width=int(panorama_cfg["output_resolution"][1]),
            horizontal_fov_deg=float(panorama_cfg["horizontal_fov_deg"]),
            vertical_fov_deg=float(panorama_cfg["vertical_fov_deg"]),
            minimum_depth_m=float(panorama_cfg["minimum_depth_m"]),
            maximum_depth_m=float(panorama_cfg["maximum_depth_m"]),
        )
        panorama_frame = result["rgb"]
        if tuple(panorama_frame.shape) != (384, 416, 3):
            raise RuntimeError(
                f"C-B2 panorama frame shape drift: {panorama_frame.shape}"
            )
        for key in self._a2_scheme_c_b2_panorama_totals:
            self._a2_scheme_c_b2_panorama_totals[key] += int(result[key])
        panorama_writer = self._a2_scheme_c_b2_panorama_writer
        if panorama_writer is None:
            panorama_writer = imageio.get_writer(
                str(self._a2_scheme_c_b2_panorama_temporary_path),
                fps=self._a2_camera_sweep_video_fps,
                codec="libx264",
                macro_block_size=2,
            )
            self._a2_scheme_c_b2_panorama_writer = panorama_writer
        panorama_writer.append_data(
            panorama_frame.detach().contiguous().cpu().numpy()
        )
        self._a2_scheme_c_b2_panorama_frame_count += 1

        left_frame = self._a2_video_frame_for_candidate(self.D435I_VIEW)
        right_frame = self._a2_video_frame_for_candidate(self.RIGHT_D435I_VIEW)
        head_frame = self._a2_video_frame_for_candidate(self.HEAD_VIEW)
        combined = torch.cat(
            [
                left_frame,
                right_frame,
                panorama_frame,
                self._fit_a2_scheme_c_b2_panel(
                    head_frame,
                    target_height=384,
                    target_width=384,
                ),
            ],
            dim=1,
        )
        if tuple(combined.shape) != (384, 1232, 3):
            raise RuntimeError(f"C-B2 process frame shape drift: {combined.shape}")
        writer = self._a2_scheme_c_combined_writer
        if writer is None:
            writer = imageio.get_writer(
                str(self._a2_scheme_c_combined_temporary_path),
                fps=self._a2_camera_sweep_video_fps,
                codec="libx264",
                macro_block_size=2,
            )
            self._a2_scheme_c_combined_writer = writer
        writer.append_data(combined.detach().contiguous().cpu().numpy())
        self._a2_scheme_c_combined_frame_count += 1

    def _a2_scheme_c_combined_layout(self) -> str:
        return (
            "left-to-right: raw left D435i 216x384; raw right D435i 216x384; "
            "depth-aware cylindrical panorama 416x384; letterboxed OEM A2 Head 384x384"
        )

    def _seal_a2_scheme_c_b2_panorama_video(self) -> str:
        if self._a2_scheme_c_b2_panorama_video_sealed:
            raise RuntimeError("C-B2 panorama video was already sealed")
        if self._a2_scheme_c_b2_panorama_writer is None:
            raise RuntimeError("C-B2 panorama video writer was never opened")
        if (
            self._a2_scheme_c_b2_panorama_frame_count
            != self._a2_scheme_c_combined_frame_count
        ):
            raise RuntimeError(
                "C-B2 panorama/process frame count mismatch; "
                f"panorama={self._a2_scheme_c_b2_panorama_frame_count}, "
                f"process={self._a2_scheme_c_combined_frame_count}"
            )
        self._a2_scheme_c_b2_panorama_writer.close()
        self._a2_scheme_c_b2_panorama_writer = None
        if not self._a2_scheme_c_b2_panorama_temporary_path.is_file():
            raise FileNotFoundError("C-B2 panorama temporary video is missing")
        os.replace(
            self._a2_scheme_c_b2_panorama_temporary_path,
            self._a2_scheme_c_b2_panorama_final_path,
        )
        if (
            not self._a2_scheme_c_b2_panorama_final_path.is_file()
            or self._a2_scheme_c_b2_panorama_final_path.stat().st_size <= 0
        ):
            raise RuntimeError("C-B2 panorama video is empty")
        self._a2_scheme_c_b2_panorama_video_sealed = True
        return str(self._a2_scheme_c_b2_panorama_final_path)

    def get_eval_metrics_summary(self):
        summary = super().get_eval_metrics_summary()
        panorama_video = self._seal_a2_scheme_c_b2_panorama_video()
        scheme = summary.get("a2_camera_scheme_c")
        if not isinstance(scheme, dict):
            raise RuntimeError("C-B2 requires the completed Scheme C base summary")
        pair = scheme.pop("d435i_mount")
        scheme["d435i_pair"] = pair
        scheme["head_extrinsic_status"] = "official_unitree_a2_urdf_camera_link"
        scheme["panorama"] = self._a2_scheme_c_cfg["panorama"]
        scheme["panorama_video"] = panorama_video
        scheme["panorama_video_metadata"] = {
            "env_id": self._a2_camera_sweep_video_env_id,
            "fps": self._a2_camera_sweep_video_fps,
            "frame_count": self._a2_scheme_c_b2_panorama_frame_count,
            "pair_frame_delta_max": self._a2_scheme_c_b2_pair_frame_delta_max,
            "mask_contract": "depth_valid_mask plus fixed-geometry single-view fallback_mask per frame",
            "pixel_totals": self._a2_scheme_c_b2_panorama_totals,
        }
        scheme["runtime_intrinsic_max_error_px"] = max(
            float(scheme["runtime_intrinsic_max_error_px"]),
            self._a2_scheme_c_b2_right_intrinsic_error_px,
        )
        scheme["boundaries"] = [
            "A2 Head pose is the official Unitree URDF camera_link extrinsic; real lens calibration remains required",
            "A2 Head wide optics are represented by a pinhole simulation approximation",
            "D435i distortion, rolling shutter, latency, exposure, and real pair timestamp skew are not simulated",
            "depth holes use one fixed-geometry source view and never RGB averaging",
            "right/out rollout does not validate mirrored left/out",
            "STEP point-cloud clearance is not a CAD solid interference pass",
            "production Student observation and model are unchanged",
        ]
        return summary
