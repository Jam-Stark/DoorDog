#!/usr/bin/env python3
"""Export a MuJoCo authority state for an exact t0 RGB-D comparison.

This intentionally has no policy rollout: it replays the recorded reset values into
the immutable scene and captures the three policy cameras at t0.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

import mujoco
import numpy as np
import torch

from gr00t.rl.sim2sim.mujoco.depthadd_visual import apply_fixed_nominal_color_pipeline
from gr00t.rl.sim2sim.mujoco.policy_visual_scene_r4 import policy_scene_option_r4
from gr00t.rl.sim2sim.policy.observations import (
    compose_dual_rgbd_from_normalized_depth,
    normalize_metric_depth_nhwc,
    normalize_rgb_nhwc,
)


_CAMERAS = {
    "left": {"mujoco_name": "left_policy", "height": 384, "width": 216},
    "right": {"mujoco_name": "right_policy", "height": 384, "width": 216},
    "head": {"mujoco_name": "head_policy", "height": 136, "width": 384},
}
_REQUIRED_MARKERS = (
    "a2_piper_tcp",
    "door_handle_center",
    "door_grasp_target",
    "door_pregrasp_target",
    "door_hinge_axis",
    "door_passage_center",
    "door_goal",
)
_IMAGE_MEAN = (0.485, 0.456, 0.406)
_IMAGE_STD = (0.229, 0.224, 0.225)


def _json_dump(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _matrix(position: np.ndarray, rotation: np.ndarray) -> np.ndarray:
    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = rotation.reshape(3, 3)
    result[:3, 3] = position
    return result


def _local_camera_matrix(model: mujoco.MjModel, camera_id: int) -> np.ndarray:
    rotation = np.empty(9, dtype=np.float64)
    mujoco.mju_quat2Mat(rotation, model.cam_quat[camera_id])
    return _matrix(model.cam_pos[camera_id], rotation)


def _camera_readback(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    camera_id: int,
    *,
    height: int,
    width: int,
) -> dict[str, Any]:
    fovy_deg = float(model.cam_fovy[camera_id])
    fy = height / (2.0 * math.tan(math.radians(fovy_deg) / 2.0))
    effective_near_m = float(model.vis.map.znear * model.stat.extent)
    effective_far_m = float(model.vis.map.zfar * model.stat.extent)
    return {
        "camera_id": camera_id,
        "parent_body_id": int(model.cam_bodyid[camera_id]),
        "parent_body_name": mujoco.mj_id2name(
            model, mujoco.mjtObj.mjOBJ_BODY, int(model.cam_bodyid[camera_id])
        ),
        "world_T_camera_mujoco": _matrix(data.cam_xpos[camera_id], data.cam_xmat[camera_id]).tolist(),
        "parent_T_camera_mujoco": _local_camera_matrix(model, camera_id).tolist(),
        "K_pixel_center": [
            [fy, 0.0, (width - 1.0) / 2.0],
            [0.0, fy, (height - 1.0) / 2.0],
            [0.0, 0.0, 1.0],
        ],
        "resolution_hw": [height, width],
        "fovy_deg": fovy_deg,
        "effective_clip_m": [effective_near_m, effective_far_m],
        "convention": {
            "transform": "columns are MuJoCo camera +X(screen-right), +Y(screen-up), +Z(camera-back) axes in world coordinates",
            "render_rays": "OpenGL/MuJoCo rendering looks along camera -Z; image rows increase downward",
            "depth": "MuJoCo Renderer depth mode, distance_to_image_plane in metres",
        },
    }


def _site_pose(model: mujoco.MjModel, data: mujoco.MjData, name: str) -> dict[str, Any]:
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
    if site_id < 0:
        raise ValueError(f"immutable scene lacks required site {name!r}")
    return {
        "site_id": site_id,
        "world_position_m": data.site_xpos[site_id].tolist(),
        "world_rotation_mujoco": data.site_xmat[site_id].reshape(3, 3).tolist(),
    }


def _render(renderer: mujoco.Renderer, data: mujoco.MjData, camera: str, option: mujoco.MjvOption) -> np.ndarray:
    renderer.update_scene(data, camera=camera, scene_option=option)
    return renderer.render().copy()


def _source_state(receipt: Mapping[str, Any], robot_contract: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    state = receipt.get("initial_state_realization")
    if not isinstance(state, Mapping):
        raise TypeError("authority receipt lacks initial_state_realization")
    qpos_layout = robot_contract.get("qpos_layout")
    qvel_layout = robot_contract.get("qvel_layout")
    if qpos_layout != {"floating_base": [0, 7], "actuated": [7, 27]}:
        raise ValueError("robot qpos layout does not match the authority A2 state")
    if qvel_layout != {"floating_base": [0, 6], "actuated": [6, 26]}:
        raise ValueError("robot qvel layout does not match the authority A2 state")
    root_qpos = np.asarray(state["root_qpos_mujoco_wxyz"], dtype=np.float64)
    joint_qpos = np.asarray(state["joint_qpos"], dtype=np.float64)
    root_qvel = np.asarray(state["root_qvel"], dtype=np.float64)
    joint_qvel = np.asarray(state["joint_qvel"], dtype=np.float64)
    if root_qpos.shape != (7,) or joint_qpos.shape != (20,):
        raise ValueError("authority initial qpos must be root7 plus joint20")
    if root_qvel.shape != (6,) or joint_qvel.shape != (20,):
        raise ValueError("authority initial qvel must be root6 plus joint20")
    qpos = np.concatenate((root_qpos, joint_qpos))
    qvel = np.concatenate((root_qvel, joint_qvel))
    if not np.isfinite(qpos).all() or not np.isfinite(qvel).all():
        raise FloatingPointError("authority initial state contains a non-finite value")
    return qpos, qvel


def _require_depth(name: str, depth: np.ndarray) -> np.ndarray:
    if depth.dtype != np.float32 or depth.ndim != 2:
        raise ValueError(f"{name} raw depth must be float32 HW, got {depth.dtype} {depth.shape}")
    if not np.isfinite(depth).all() or not bool(np.any(depth > 0.0)):
        raise FloatingPointError(f"{name} raw metric depth is not finite/nonempty")
    valid = np.isfinite(depth) & (depth >= 0.1) & (depth <= 4.0)
    if not bool(np.any(valid)):
        raise FloatingPointError(f"{name} t0 depth has no source-valid [0.1,4.0] pixels")
    if not bool(np.all(np.isfinite(depth[valid]) & (depth[valid] >= 0.1) & (depth[valid] <= 4.0))):
        raise RuntimeError(f"{name} source-valid mask violates the [0.1,4.0] m contract")
    return valid


def _fixed_nominal_color_pipeline(receipt: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Read the exact fixed-nominal pipeline receipt used by the evaluator.

    Legacy and pre-factor nominal episodes did not have an image-space pipeline.
    They are intentionally represented as the evaluator's identity case rather
    than being inferred from scene XML or an experiment directory name.
    """
    visual_overlay = receipt.get("visual_overlay")
    if visual_overlay is None:
        return None
    if not isinstance(visual_overlay, Mapping):
        raise TypeError("episode visual_overlay must be a mapping when present")
    pipeline = visual_overlay.get("color_pipeline")
    if pipeline is None:
        return None
    if not isinstance(pipeline, Mapping):
        raise TypeError("episode visual_overlay.color_pipeline must be a mapping")
    enabled = pipeline.get("enabled")
    if not isinstance(enabled, bool):
        raise TypeError("episode fixed-nominal color_pipeline.enabled must be bool")
    if enabled:
        intended = pipeline.get("intended")
        if not isinstance(intended, Mapping):
            raise TypeError("enabled fixed-nominal color pipeline lacks intended parameters")
    return pipeline


def export(args: argparse.Namespace) -> None:
    episode = args.episode_dir.resolve(strict=True)
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"paired render output already exists: {output}")
    scene = episode / "model" / "scene.xml"
    receipt_path = episode / "receipt.json"
    contract_path = episode.parents[1] / "prepared" / "robot_contract.json"
    if not scene.is_file() or not receipt_path.is_file() or not contract_path.is_file():
        raise FileNotFoundError("authority episode must provide scene.xml, receipt.json, and prepared robot_contract.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    robot_contract = json.loads(contract_path.read_text(encoding="utf-8"))
    source_qpos, source_qvel = _source_state(receipt, robot_contract)
    fixed_nominal_color_pipeline = _fixed_nominal_color_pipeline(receipt)

    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    if home < 0:
        raise ValueError("immutable scene lacks scene_home keyframe")
    mujoco.mj_resetDataKeyframe(model, data, home)
    data.qpos[:27] = source_qpos
    data.qvel[:26] = source_qvel
    mujoco.mj_forward(model, data)
    if not np.array_equal(data.qpos[:27], source_qpos) or not np.array_equal(data.qvel[:26], source_qvel):
        raise RuntimeError("MuJoCo readback differs from the authority initial-state values")

    option = policy_scene_option_r4()
    renderers = {
        name: mujoco.Renderer(model, height=spec["height"], width=spec["width"])
        for name, spec in _CAMERAS.items()
    }
    try:
        left_rgb = _render(renderers["left"], data, "left_policy", option)
        right_rgb = _render(renderers["right"], data, "right_policy", option)
        renderers["left"].enable_depth_rendering()
        renderers["right"].enable_depth_rendering()
        left_depth = _render(renderers["left"], data, "left_policy", option)
        right_depth = _render(renderers["right"], data, "right_policy", option)
        renderers["left"].disable_depth_rendering()
        renderers["right"].disable_depth_rendering()
        head_rgb = _render(renderers["head"], data, "head_policy", option)
    finally:
        for renderer in renderers.values():
            renderer.close()
    for name, image, shape in (
        ("left", left_rgb, (384, 216, 3)),
        ("right", right_rgb, (384, 216, 3)),
        ("head", head_rgb, (136, 384, 3)),
    ):
        if image.dtype != np.uint8 or image.shape != shape:
            raise ValueError(f"{name} raw RGB must be uint8 {shape}, got {image.dtype} {image.shape}")
    left_valid = _require_depth("left", left_depth)
    right_valid = _require_depth("right", right_depth)

    # Keep this exact evaluator order: raw renderer RGB -> fixed-nominal
    # color pipeline -> augmentation (absent for fixed t0) -> policy RGB.
    # Depth is rendered and normalized separately; the RGB-only pipeline must
    # not modify its validity predicate or metric values.
    left_post_color_pipeline_rgb, left_pipeline_receipt = apply_fixed_nominal_color_pipeline(
        left_rgb, fixed_nominal_color_pipeline
    )
    right_post_color_pipeline_rgb, right_pipeline_receipt = apply_fixed_nominal_color_pipeline(
        right_rgb, fixed_nominal_color_pipeline
    )
    head_post_color_pipeline_rgb, head_pipeline_receipt = apply_fixed_nominal_color_pipeline(
        head_rgb, fixed_nominal_color_pipeline
    )
    left_norm, left_normalized_valid = normalize_metric_depth_nhwc(
        torch.from_numpy(left_depth[..., None]).unsqueeze(0)
    )
    right_norm, right_normalized_valid = normalize_metric_depth_nhwc(
        torch.from_numpy(right_depth[..., None]).unsqueeze(0)
    )
    if not np.array_equal(left_valid, left_normalized_valid.squeeze().numpy()):
        raise RuntimeError("left valid mask differs from policy normalization")
    if not np.array_equal(right_valid, right_normalized_valid.squeeze().numpy()):
        raise RuntimeError("right valid mask differs from policy normalization")
    vision8 = compose_dual_rgbd_from_normalized_depth(
        torch.from_numpy(left_post_color_pipeline_rgb).unsqueeze(0),
        torch.from_numpy(right_post_color_pipeline_rgb).unsqueeze(0),
        left_norm,
        right_norm,
        image_mean=_IMAGE_MEAN,
        image_std=_IMAGE_STD,
        left_depth_valid=left_normalized_valid,
        right_depth_valid=right_normalized_valid,
    ).squeeze(0).numpy().astype(np.float32, copy=False)
    head3 = normalize_rgb_nhwc(
        torch.from_numpy(head_post_color_pipeline_rgb).unsqueeze(0), image_mean=_IMAGE_MEAN, image_std=_IMAGE_STD
    ).squeeze(0).numpy().astype(np.float32, copy=False)
    if vision8.shape != (384, 216, 8) or head3.shape != (136, 384, 3):
        raise RuntimeError("policy-ready visual tensor shape contract violated")

    camera_readbacks: dict[str, Any] = {}
    for name, spec in _CAMERAS.items():
        camera_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, spec["mujoco_name"])
        if camera_id < 0:
            raise ValueError(f"immutable scene lacks {spec['mujoco_name']!r}")
        camera_readbacks[name] = _camera_readback(
            model, data, camera_id, height=spec["height"], width=spec["width"]
        )
    marker_sites: dict[str, Any] = {}
    for name in _REQUIRED_MARKERS:
        site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
        if site_id < 0:
            raise ValueError(f"immutable scene lacks marker site {name!r}")
        group = int(model.site_group[site_id])
        if group != 5:
            raise RuntimeError(f"marker site {name!r} compiled into group {group}, expected group 5")
        marker_sites[name] = {
            "site_id": site_id,
            "group": group,
            "policy_visible": bool(option.sitegroup[group]),
            "pixel_count": "NOT_MEASURED",
        }
    for name, value in marker_sites.items():
        if value["policy_visible"]:
            raise RuntimeError(f"policy option exposes marker site {name!r}")

    door_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "door_hinge")
    handle_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "handle_hinge")
    if door_joint < 0 or handle_joint < 0:
        raise ValueError("immutable scene lacks door or handle hinge")
    frame_ids = np.array([1, 1, 1], dtype=np.int64)
    timestamps_s = np.zeros(3, dtype=np.float64)
    camera_meta = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0], dtype=np.float32)
    output.mkdir(parents=True)
    np.savez(
        output / "paired_render_mujoco_t0.npz",
        raw_left_rgb_uint8=left_rgb,
        raw_right_rgb_uint8=right_rgb,
        raw_head_rgb_uint8=head_rgb,
        post_color_pipeline_left_rgb_uint8=left_post_color_pipeline_rgb,
        post_color_pipeline_right_rgb_uint8=right_post_color_pipeline_rgb,
        post_color_pipeline_head_rgb_uint8=head_post_color_pipeline_rgb,
        raw_left_distance_to_image_plane_m=left_depth,
        raw_right_distance_to_image_plane_m=right_depth,
        source_valid_left_bool=left_valid,
        source_valid_right_bool=right_valid,
        policy_vision_obs8_float32=vision8,
        policy_head_obs3_float32=head3,
        camera_meta6_float32=camera_meta,
        camera_frame_ids_int64=frame_ids,
        camera_source_timestamps_s_float64=timestamps_s,
        root_and_joint_qpos27_float64=data.qpos[:27].copy(),
        root_and_joint_qvel26_float64=data.qvel[:26].copy(),
    )
    _json_dump(
        output / "paired_render_mujoco_t0.json",
        {
            "schema": "doordog.sim2sim.depthadd_v3.paired_render_mujoco_t0.v2",
            "result": "PASS",
            "evidence_level": "RUNTIME_PASS",
            "source": {
                "immutable_scene_xml": str(scene),
                "authority_receipt": str(receipt_path),
                "robot_contract": str(contract_path),
                "case_id": receipt["case_id"],
                "lane": receipt["lane"],
                "policy_rollout": "NOT_RUN; t0 observation capture only",
                "wall_probe": "NOT_RUN",
            },
            "model": {
                "mujoco_version": mujoco.__version__,
                "nq": model.nq,
                "nv": model.nv,
                "nu": model.nu,
                "ncam": model.ncam,
                "nsite": model.nsite,
                "time_s_after_mj_forward": float(data.time),
            },
            "initial_state_realization": {
                "authority": receipt["initial_state_realization"],
                "qpos27_readback": data.qpos[:27].tolist(),
                "qvel26_readback": data.qvel[:26].tolist(),
                "door_hinge_qpos_rad": float(data.qpos[model.jnt_qposadr[door_joint]]),
                "handle_hinge_qpos_rad": float(data.qpos[model.jnt_qposadr[handle_joint]]),
                "apply_contract": "mj_resetDataKeyframe(scene_home), assign root7+joint20 and root6+joint20 by authority receipt value, then mj_forward",
            },
            "camera": {
                "frame_ids_left_right_head": frame_ids.tolist(),
                "source_timestamps_s_left_right_head": timestamps_s.tolist(),
                "camera_meta6": camera_meta.tolist(),
                "readbacks": camera_readbacks,
            },
            "landmarks": {
                "tcp": _site_pose(model, data, "a2_piper_tcp"),
                "grasp": _site_pose(model, data, "door_grasp_target"),
                "pregrasp": _site_pose(model, data, "door_pregrasp_target"),
            },
            "policy_marker_visibility": {
                "scene_option": "sitegroup[5]=0; geomgroup[5]=0",
                "marker_sites": marker_sites,
                "pixel_count_contract": "NOT_MEASURED: this export does not infer group-specific pixels from a non-segmentation render",
            },
            "arrays": {
                "npz": "paired_render_mujoco_t0.npz",
                "shapes": {
                    "raw_left_rgb_uint8": list(left_rgb.shape),
                    "raw_right_rgb_uint8": list(right_rgb.shape),
                    "raw_head_rgb_uint8": list(head_rgb.shape),
                    "post_color_pipeline_left_rgb_uint8": list(left_post_color_pipeline_rgb.shape),
                    "post_color_pipeline_right_rgb_uint8": list(right_post_color_pipeline_rgb.shape),
                    "post_color_pipeline_head_rgb_uint8": list(head_post_color_pipeline_rgb.shape),
                    "raw_left_distance_to_image_plane_m": list(left_depth.shape),
                    "raw_right_distance_to_image_plane_m": list(right_depth.shape),
                    "policy_vision_obs8_float32": list(vision8.shape),
                    "policy_head_obs3_float32": list(head3.shape),
                },
                "depth_source_validity": "finite and inclusive [0.1,4.0] m; all other values map to zero policy depth",
            },
            "fixed_nominal_color_pipeline": {
                "receipt_source": "episode.receipt.visual_overlay.color_pipeline",
                "contract": "raw_renderer_rgb_uint8 -> fixed_nominal_color_pipeline -> no_visual_augmentation_at_t0 -> policy_rgb",
                "left": left_pipeline_receipt,
                "right": right_pipeline_receipt,
                "head": head_pipeline_receipt,
                "depth_unchanged": True,
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    export(parser.parse_args())


if __name__ == "__main__":
    main()
