#!/usr/bin/env python3
"""Compare the runtime MuJoCo and Isaac exact-visual-state t0 RGB-D exports.

This tool is deliberately limited to the producer's ``EXACT_VISUAL_STATE_T0_ONLY``
scope.  It never loads a policy or makes a mechanics/closed-loop claim.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image


_CAMERAS = ("left", "right", "head")
_RGB_KEYS = {
    "left": "raw_left_rgb_uint8",
    "right": "raw_right_rgb_uint8",
    "head": "raw_head_rgb_uint8",
}
_DEPTH_KEYS = {
    "left": "raw_left_distance_to_image_plane_m",
    "right": "raw_right_distance_to_image_plane_m",
}


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _require(mapping: Mapping[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise KeyError(f"{context} lacks required key {key!r}")
    return mapping[key]


def _array(bundle: Mapping[str, np.ndarray], key: str, dtype: np.dtype, shape: tuple[int, ...]) -> np.ndarray:
    if key not in bundle:
        raise KeyError(f"NPZ lacks {key!r}")
    value = bundle[key]
    if value.dtype != dtype or value.shape != shape:
        raise ValueError(f"{key} must be {dtype} {shape}, got {value.dtype} {value.shape}")
    return value


def _finite(name: str, value: np.ndarray) -> None:
    if not np.isfinite(value).all():
        raise FloatingPointError(f"{name} contains a non-finite value")


def _depth(bundle: Mapping[str, np.ndarray], camera: str, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    depth = _array(bundle, _DEPTH_KEYS[camera], np.dtype(np.float32), shape)
    valid = _array(bundle, f"source_valid_{camera}_bool", np.dtype(bool), shape)
    # Isaac is allowed to preserve +inf raw depth.  NaN or -inf is not part of
    # the producer contract, and the validity predicate must remain exact.
    if np.isnan(depth).any() or np.isneginf(depth).any():
        raise FloatingPointError(f"{camera} raw depth contains NaN or -inf")
    expected = np.isfinite(depth) & (depth >= 0.1) & (depth <= 4.0)
    if not np.array_equal(valid, expected):
        raise RuntimeError(f"{camera} valid mask violates finite & [0.1, 4.0] m")
    return depth, valid


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    return value


def _err(reference: np.ndarray, observed: np.ndarray) -> dict[str, float]:
    diff = observed.astype(np.float64) - reference.astype(np.float64)
    absolute = np.abs(diff)
    return {
        "max_abs": float(absolute.max()),
        "rmse": float(np.sqrt(np.mean(np.square(diff)))),
        "mae": float(np.mean(absolute)),
    }


def _rotation_angle_deg(reference: np.ndarray, observed: np.ndarray) -> float:
    relative = reference.T @ observed
    cosine = float(np.clip((np.trace(relative) - 1.0) * 0.5, -1.0, 1.0))
    return float(math.degrees(math.acos(cosine)))


def _rgb_metrics(reference: np.ndarray, observed: np.ndarray) -> dict[str, Any]:
    diff = observed.astype(np.float64) - reference.astype(np.float64)
    mse = float(np.mean(np.square(diff)))
    per_channel = []
    for channel in range(3):
        channel_diff = diff[..., channel]
        channel_mse = float(np.mean(np.square(channel_diff)))
        per_channel.append({
            "mae": float(np.mean(np.abs(channel_diff))),
            "rmse": float(math.sqrt(channel_mse)),
            "psnr_db": None if channel_mse == 0.0 else float(20.0 * math.log10(255.0 / math.sqrt(channel_mse))),
        })
    return {
        "mae": float(np.mean(np.abs(diff))),
        "rmse": float(math.sqrt(mse)),
        "psnr_db": None if mse == 0.0 else float(20.0 * math.log10(255.0 / math.sqrt(mse))),
        "per_channel_rgb": per_channel,
    }


def _depth_metrics(reference_depth: np.ndarray, observed_depth: np.ndarray, reference_valid: np.ndarray, observed_valid: np.ndarray) -> dict[str, Any]:
    intersection = reference_valid & observed_valid
    union = reference_valid | observed_valid
    if not intersection.any():
        raise RuntimeError("depth valid-mask intersection is empty")
    errors = np.abs(observed_depth[intersection].astype(np.float64) - reference_depth[intersection].astype(np.float64))
    true_positive = int(intersection.sum())
    return {
        "reference_valid_fraction": float(reference_valid.mean()),
        "observed_valid_fraction": float(observed_valid.mean()),
        "intersection_pixels": true_positive,
        "union_pixels": int(union.sum()),
        "iou": float(true_positive / union.sum()),
        "precision": float(true_positive / observed_valid.sum()),
        "recall": float(true_positive / reference_valid.sum()),
        "intersection_abs_error_m": {
            "mae": float(errors.mean()),
            "rmse": float(np.sqrt(np.mean(np.square(errors)))),
            "p50": float(np.quantile(errors, 0.50)),
            "p95": float(np.quantile(errors, 0.95)),
            "max": float(errors.max()),
        },
    }


def _policy_metrics(reference: np.ndarray, observed: np.ndarray) -> dict[str, Any]:
    result = _err(reference, observed)
    per_channel = []
    for channel in range(reference.shape[-1]):
        per_channel.append(_err(reference[..., channel], observed[..., channel]))
    result["per_channel"] = per_channel
    return result


def _save_rgb_comparison(path: Path, reference: np.ndarray, observed: np.ndarray) -> None:
    absolute = np.abs(observed.astype(np.int16) - reference.astype(np.int16)).astype(np.uint8)
    Image.fromarray(np.concatenate((reference, observed, absolute), axis=1), mode="RGB").save(path)


def _save_valid_overlay(path: Path, reference: np.ndarray, observed: np.ndarray) -> None:
    image = np.zeros((*reference.shape, 3), dtype=np.uint8)
    image[reference & observed] = (255, 255, 255)
    image[reference & ~observed] = (255, 48, 48)
    image[~reference & observed] = (48, 96, 255)
    Image.fromarray(image, mode="RGB").save(path)


def _save_depth_heatmap(path: Path, reference_depth: np.ndarray, observed_depth: np.ndarray, intersection: np.ndarray) -> None:
    errors = np.zeros(reference_depth.shape, dtype=np.float64)
    errors[intersection] = np.abs(observed_depth[intersection] - reference_depth[intersection])
    scale = float(np.quantile(errors[intersection], 0.95))
    if scale == 0.0:
        scale = 1.0
    x = np.clip(errors / scale, 0.0, 1.0)
    image = np.zeros((*x.shape, 3), dtype=np.uint8)
    image[..., 0] = np.round(255.0 * x).astype(np.uint8)
    image[..., 1] = np.round(255.0 * np.minimum(1.0, 2.0 * x)).astype(np.uint8)
    image[..., 2] = np.round(255.0 * (1.0 - x)).astype(np.uint8)
    image[~intersection] = (0, 0, 0)
    Image.fromarray(image, mode="RGB").save(path)


def _camera_metrics(mujoco: Mapping[str, Any], isaac: Mapping[str, Any], camera: str) -> dict[str, Any]:
    mj = _require(_require(mujoco, "camera", "MuJoCo JSON"), "readbacks", "MuJoCo camera")[camera]
    post = _require(_require(isaac, "cameras", "Isaac realization"), camera, "Isaac cameras")["post_render"]
    pre = _require(_require(isaac, "cameras", "Isaac realization"), camera, "Isaac cameras")["pre_render"]
    mj_world = np.asarray(mj["world_T_camera_mujoco"], dtype=np.float64)
    isaac_world = np.asarray(post["scene_local_world_T_camera_mujoco_opengl"], dtype=np.float64)
    mj_k = np.asarray(mj["K_pixel_center"], dtype=np.float64)
    common_k = np.asarray(post["intrinsic_projection_equivalence"]["K_common_center_index_coordinates"], dtype=np.float64)
    native_k = np.asarray(post["intrinsic_projection_equivalence"]["K_native_isaac_top_left_edge_coordinates"], dtype=np.float64)
    return {
        "scene_local_world_translation_error_m": _err(mj_world[:3, 3], isaac_world[:3, 3]),
        "scene_local_world_rotation_angle_deg": _rotation_angle_deg(mj_world[:3, :3], isaac_world[:3, :3]),
        "scene_local_world_matrix_max_abs": float(np.max(np.abs(isaac_world - mj_world))),
        "K_common_center_index_error": _err(mj_k, common_k),
        "K_native_top_left_edge_minus_mujoco_center_index": (native_k - mj_k).tolist(),
        "native_coordinate_fact": "native Isaac principal point is +0.5 px on cx/cy; common center-index conversion subtracts 0.5 px",
        "fovy_abs_error_deg": float(abs(float(post["intrinsic_projection_equivalence"]["actual_fovy_deg"]) - float(mj["fovy_deg"]))),
        "clip_max_abs_error_m": float(np.max(np.abs(np.asarray(pre["clip_m"], dtype=np.float64) - np.asarray(mj["effective_clip_m"], dtype=np.float64)))),
        "frame_id": {"mujoco": int(_require(mujoco["camera"], "frame_ids_left_right_head", "MuJoCo camera")[_CAMERAS.index(camera)]), "isaac": int(post["frame_id"])},
        "source_timestamp_s": {"mujoco": float(_require(mujoco["camera"], "source_timestamps_s_left_right_head", "MuJoCo camera")[_CAMERAS.index(camera)]), "isaac": float(post["source_timestamp_s"])},
        "producer_projection_gate": post["intrinsic_projection_equivalence"]["status"],
        "producer_post_render_world_matrix_max_abs": float(post["errors"]["world_matrix_max_abs"]),
    }


def _state_metrics(mujoco_json: Mapping[str, Any], mujoco_npz: Mapping[str, np.ndarray], isaac: Mapping[str, Any]) -> dict[str, Any]:
    mj_qpos = _array(mujoco_npz, "root_and_joint_qpos27_float64", np.dtype(np.float64), (27,))
    mj_qvel = _array(mujoco_npz, "root_and_joint_qvel26_float64", np.dtype(np.float64), (26,))
    _finite("MuJoCo qpos", mj_qpos)
    _finite("MuJoCo qvel", mj_qvel)
    robot = _require(isaac, "robot", "Isaac realization")
    isaac_qpos = np.asarray(robot["readback_root_local_wxyz"][:7] + robot["readback_joint_qpos"], dtype=np.float64)
    isaac_qvel = np.asarray(robot["readback_root_local_wxyz"][7:] + robot["readback_joint_qvel"], dtype=np.float64)
    return {
        "root_and_joint_qpos27": _err(mj_qpos, isaac_qpos),
        "root_and_joint_qvel26": _err(mj_qvel, isaac_qvel),
        "door_root_local": _err(
            np.array([1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float64),
            np.asarray(isaac["door"]["readback_root_local_wxyz"], dtype=np.float64),
        ),
        "door_joint_qpos": _err(
            np.asarray([mujoco_json["initial_state_realization"]["door_hinge_qpos_rad"], mujoco_json["initial_state_realization"]["handle_hinge_qpos_rad"]]),
            np.asarray(isaac["door"]["joint_qpos_readback"]),
        ),
        "door_joint_qvel": _err(np.zeros(2), np.asarray(isaac["door"]["joint_qvel_readback"])),
        "producer_runtime_status": {"robot": robot["status"], "door": isaac["door"]["status"]},
    }


def _geometry_metrics(isaac: Mapping[str, Any]) -> dict[str, Any]:
    authority = _require(isaac, "authority", "Isaac realization")
    expected = _require(authority, "door_per_geom", "Isaac authority")
    observed = _require(_require(isaac, "door", "Isaac realization"), "visible_geometry", "Isaac door")
    per_geom = {}
    for name, source in expected.items():
        readback = _require(observed, name, "Isaac visible geometry")
        per_geom[name] = {
            "full_dimensions_m": _err(np.asarray(source["full_dimensions_m"]), np.asarray(readback["full_dimensions_m"])),
            "local_center_m": _err(np.asarray(source["local_center_m"]), np.asarray(readback["local_center_m"])),
            "status": readback["status"],
        }
    return {
        "authority_source": authority["mujoco_t0_json_path"],
        "per_geom": per_geom,
        "absent_non_source_geometry": isaac["door"]["absent_non_source_geometry"],
        "source_standard_broad_door_frame": isaac["source_standard_broad_door_frame"],
    }


def analyze(args: argparse.Namespace) -> None:
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    mj_dir = args.mujoco_dir.resolve(strict=True)
    isaac_dir = args.isaac_dir.resolve(strict=True)
    mj_json = _read_json(mj_dir / "paired_render_mujoco_t0.json")
    isaac_arrays = _read_json(isaac_dir / "paired_base000_visual_t0.json")
    isaac = _read_json(isaac_dir / "paired_base000_visual_t0_realization.json")
    if mj_json.get("schema") != "doordog.sim2sim.depthadd_v3.paired_render_mujoco_t0.v1":
        raise ValueError("unexpected MuJoCo t0 schema")
    if isaac_arrays.get("schema") != "a2_depthadd_visual_t0_arrays_v1":
        raise ValueError("unexpected Isaac array schema")
    if isaac.get("gate") != "EXACT_VISUAL_STATE_T0_ONLY" or isaac.get("result") != "PASS_WITH_EXPLICIT_PIXEL_COORDINATE_CONVERSION":
        raise RuntimeError("Isaac bundle does not have the required exact-visual-state result")
    with np.load(mj_dir / "paired_render_mujoco_t0.npz") as mj_loaded, np.load(isaac_dir / "paired_base000_visual_t0.npz") as isaac_loaded:
        mj_npz = {key: mj_loaded[key] for key in mj_loaded.files}
        isaac_npz = {key: isaac_loaded[key] for key in isaac_loaded.files}

    rgb_metrics, depth_metrics, policy_metrics = {}, {}, {}
    images: list[str] = []
    output.mkdir(parents=True)
    for camera in _CAMERAS:
        shape = tuple(mj_json["arrays"]["shapes"][_RGB_KEYS[camera]])
        mj_rgb = _array(mj_npz, _RGB_KEYS[camera], np.dtype(np.uint8), shape)
        isaac_rgb = _array(isaac_npz, _RGB_KEYS[camera], np.dtype(np.uint8), shape)
        rgb_metrics[camera] = _rgb_metrics(mj_rgb, isaac_rgb)
        filename = f"{camera}_rgb_side_by_side_absdiff.png"
        images.append(filename)
        _save_rgb_comparison(output / filename, mj_rgb, isaac_rgb)
    for camera in ("left", "right"):
        shape = tuple(mj_json["arrays"]["shapes"][_DEPTH_KEYS[camera]])
        mj_depth, mj_valid = _depth(mj_npz, camera, shape)
        isaac_depth, isaac_valid = _depth(isaac_npz, camera, shape)
        depth_metrics[camera] = _depth_metrics(mj_depth, isaac_depth, mj_valid, isaac_valid)
        overlay = f"{camera}_valid_mask_overlay.png"
        heatmap = f"{camera}_intersection_depth_abs_error_heatmap.png"
        images.extend((overlay, heatmap))
        _save_valid_overlay(output / overlay, mj_valid, isaac_valid)
        _save_depth_heatmap(output / heatmap, mj_depth, isaac_depth, mj_valid & isaac_valid)
    for key, shape in (("policy_vision_obs8_float32", (384, 216, 8)), ("policy_head_obs3_float32", (136, 384, 3))):
        mj_policy = _array(mj_npz, key, np.dtype(np.float32), shape)
        isaac_policy = _array(isaac_npz, key, np.dtype(np.float32), shape)
        _finite(f"MuJoCo {key}", mj_policy)
        _finite(f"Isaac {key}", isaac_policy)
        policy_metrics[key] = _policy_metrics(mj_policy, isaac_policy)

    camera = {name: _camera_metrics(mj_json, isaac, name) for name in _CAMERAS}
    frame_meta = {
        "camera_meta6": _err(_array(mj_npz, "camera_meta6_float32", np.dtype(np.float32), (6,)), _array(isaac_npz, "camera_meta6_float32", np.dtype(np.float32), (6,))),
        "frame_ids_equal": bool(np.array_equal(_array(mj_npz, "camera_frame_ids_int64", np.dtype(np.int64), (3,)), _array(isaac_npz, "camera_frame_ids_int64", np.dtype(np.int64), (3,)))),
        "timestamps_s": _err(_array(mj_npz, "camera_source_timestamps_s_float64", np.dtype(np.float64), (3,)), _array(isaac_npz, "camera_source_timestamps_s_float64", np.dtype(np.float64), (3,))),
    }
    state = _state_metrics(mj_json, mj_npz, isaac)
    geometry = _geometry_metrics(isaac)
    marker = {
        "mujoco": mj_json["policy_marker_visibility"],
        "isaac": isaac["markers"],
        "typed_outcome": "INCONCLUSIVE_MUJOCO_PIXEL_COUNT_NOT_MEASURED__ISAAC_STRUCTURAL_ZERO",
    }
    report = {
        "schema": "doordog.sim2sim.depthadd_v3.paired_render_comparison.v1",
        "result": "RUNTIME_PASS_EXACT_VISUAL_STATE_T0_ONLY",
        "scope": "raw t0 RGB-D and policy-ready visual tensor comparison only; policy/action/LSTM/closed-loop/mechanics are not evaluated",
        "inputs": {"mujoco_dir": str(mj_dir), "isaac_dir": str(isaac_dir)},
        "typed_gates": {
            "state_realization": "PASS_RUNTIME_RECORDED",
            "camera_representation": "PASS_WITH_EXPLICIT_PIXEL_COORDINATE_CONVERSION",
            "visible_geometry": "PASS_APPLIED_AND_READBACK",
            "marker_visibility": marker["typed_outcome"],
            "mechanics": "NOT_EVALUATED_FAIL_UNSUPPORTED_IN_PRODUCER",
            "policy_or_closed_loop": "NOT_RUN_BY_SCOPE",
            "wall_probe_20m": "NOT_RUN",
        },
        "state": state,
        "visible_geometry": geometry,
        "markers": marker,
        "camera": camera,
        "camera_meta_and_cadence": frame_meta,
        "rgb": rgb_metrics,
        "depth": depth_metrics,
        "policy_ready": policy_metrics,
        "artifacts": {"images": images},
        "interpretation": {
            "pixel_threshold": "No arbitrary cross-renderer pixel PASS threshold is applied.",
            "coordinate_rule": "All camera matrix/K conclusions use Isaac scene-local OpenGL and common center-index K. Native Isaac top-left-edge K retains the documented +0.5 px cx/cy difference.",
            "dominant_discrepancy_rule": "RGB/depth/policy discrepancies are renderer and input observations only, not a closed-loop causal conclusion.",
        },
    }
    (output / "paired_render_comparison.json").write_text(json.dumps(_json_ready(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# DepthADD v3 exact visual-state t0 paired render comparison",
        "",
        "Result: `RUNTIME_PASS_EXACT_VISUAL_STATE_T0_ONLY`. This report deliberately does not make a policy, action/LSTM, closed-loop, or mechanics claim.",
        "",
        "## Gates",
        "",
    ]
    for name, value in report["typed_gates"].items():
        lines.append(f"- `{name}`: `{value}`")
    lines += ["", "## Camera / coordinate representation", ""]
    for name in _CAMERAS:
        value = camera[name]
        lines.append(f"- `{name}`: scene-local translation max-abs {value['scene_local_world_translation_error_m']['max_abs']:.3e} m; rotation {value['scene_local_world_rotation_angle_deg']:.6f} deg; common-K max-abs {value['K_common_center_index_error']['max_abs']:.3e}; fovy error {value['fovy_abs_error_deg']:.3e} deg.")
    lines += ["", "Native Isaac K retains +0.5 px on cx/cy; the common center-index K explicitly removes this coordinate-convention offset. No tolerance was relaxed.", "", "## Renderer/input discrepancies (descriptive; no pixel pass threshold)", ""]
    for name in _CAMERAS:
        value = rgb_metrics[name]
        lines.append(f"- `{name}` RGB: MAE {value['mae']:.4f}, RMSE {value['rmse']:.4f}, PSNR {value['psnr_db'] if value['psnr_db'] is not None else 'inf'} dB.")
    for name in ("left", "right"):
        value = depth_metrics[name]
        error = value["intersection_abs_error_m"]
        lines.append(f"- `{name}` depth: valid IoU {value['iou']:.6f}, intersection MAE {error['mae']:.6f} m, p95 {error['p95']:.6f} m, max {error['max']:.6f} m.")
    lines += ["", "## Artifacts", ""]
    for name in images:
        lines.append(f"- `{name}`")
    lines += ["", "Marker conclusion: Isaac reports structural pixel count zero. MuJoCo uses hidden group-5 sites but this non-segmentation capture does not measure per-marker pixels, so a cross-renderer marker-pixel equivalence claim remains inconclusive."]
    (output / "PAIRED_RENDER_COMPARISON.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mujoco-dir", type=Path, required=True)
    parser.add_argument("--isaac-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    analyze(parser.parse_args())


if __name__ == "__main__":
    main()
