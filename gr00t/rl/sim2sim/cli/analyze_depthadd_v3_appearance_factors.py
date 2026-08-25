#!/usr/bin/env python3
"""Compare the five fixed-nominal appearance-factor t0 exports with Isaac.

Each ``--factor-dir`` is the paired-export directory for one fixed-nominal
factor lane.  The exporter records the authority episode receipt path, which
lets this analysis also summarize the matching 16-case evaluation receipts
when they have been produced.  This is a descriptive factor ablation: it does
not assert renderer, material, or closed-loop equivalence.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import numpy as np


_FACTORS = (
    "stable_baseline",
    "lighting",
    "background",
    "materials",
    "renderer_color_pipeline",
)
_CAMERAS = ("left", "right", "head")
_RGB_SHAPES = {
    "left": (384, 216, 3),
    "right": (384, 216, 3),
    "head": (136, 384, 3),
}
_DEPTH_SHAPES = {"left": (384, 216), "right": (384, 216)}
_FIXED_EVALUATION_CASE_IDS = tuple(
    f"seed41001_base{index:03d}__fixed" for index in range(16)
)


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _npz_array(bundle: Mapping[str, np.ndarray], key: str, dtype: np.dtype, shape: tuple[int, ...]) -> np.ndarray:
    value = bundle.get(key)
    if value is None:
        raise KeyError(f"NPZ lacks {key!r}")
    if value.dtype != dtype or value.shape != shape:
        raise ValueError(f"{key} must be {dtype} {shape}, got {value.dtype} {value.shape}")
    return value


def _error(reference: np.ndarray, observed: np.ndarray) -> dict[str, float]:
    diff = observed.astype(np.float64) - reference.astype(np.float64)
    absolute = np.abs(diff)
    return {
        "max_abs": float(absolute.max()),
        "mae": float(absolute.mean()),
        "rmse": float(np.sqrt(np.mean(np.square(diff)))),
    }


def _rgb(reference: np.ndarray, observed: np.ndarray) -> dict[str, float | None]:
    error = _error(reference, observed)
    mse = error["rmse"] ** 2
    return {
        "mae": error["mae"],
        "rmse": error["rmse"],
        "psnr_db": None if mse == 0.0 else float(20.0 * math.log10(255.0 / math.sqrt(mse))),
    }


def _depth(bundle: Mapping[str, np.ndarray], camera: str) -> tuple[np.ndarray, np.ndarray]:
    shape = _DEPTH_SHAPES[camera]
    depth = _npz_array(bundle, f"raw_{camera}_distance_to_image_plane_m", np.dtype(np.float32), shape)
    valid = _npz_array(bundle, f"source_valid_{camera}_bool", np.dtype(bool), shape)
    expected = np.isfinite(depth) & (depth >= 0.1) & (depth <= 4.0)
    if np.isnan(depth).any() or np.isneginf(depth).any() or not np.array_equal(valid, expected):
        raise RuntimeError(f"{camera} depth source-valid [0.1,4.0] m contract is violated")
    return depth, valid


def _depth_metrics(reference_depth: np.ndarray, observed_depth: np.ndarray, reference_valid: np.ndarray, observed_valid: np.ndarray) -> dict[str, Any]:
    intersection = reference_valid & observed_valid
    union = reference_valid | observed_valid
    if not intersection.any():
        raise RuntimeError("depth valid-mask intersection is empty")
    errors = np.abs(observed_depth[intersection].astype(np.float64) - reference_depth[intersection].astype(np.float64))
    return {
        "valid_iou": float(intersection.sum() / union.sum()),
        "valid_precision": float(intersection.sum() / observed_valid.sum()),
        "valid_recall": float(intersection.sum() / reference_valid.sum()),
        "intersection_abs_error_m": {
            "mae": float(errors.mean()),
            "rmse": float(np.sqrt(np.mean(np.square(errors)))),
            "p95": float(np.quantile(errors, 0.95)),
            "max": float(errors.max()),
        },
    }


def _rotation_deg(reference: np.ndarray, observed: np.ndarray) -> float:
    relative = reference.T @ observed
    cosine = float(np.clip((np.trace(relative) - 1.0) * 0.5, -1.0, 1.0))
    return float(math.degrees(math.acos(cosine)))


def _camera_invariants(mujoco_json: Mapping[str, Any], isaac: Mapping[str, Any], camera: str) -> dict[str, Any]:
    mj = mujoco_json["camera"]["readbacks"][camera]
    source = isaac["cameras"][camera]
    mj_world = np.asarray(mj["world_T_camera_mujoco"], dtype=np.float64)
    isaac_world = np.asarray(source["post_render"]["scene_local_world_T_camera_mujoco_opengl"], dtype=np.float64)
    mj_k = np.asarray(mj["K_pixel_center"], dtype=np.float64)
    common_k = np.asarray(source["post_render"]["intrinsic_projection_equivalence"]["K_common_center_index_coordinates"], dtype=np.float64)
    return {
        "scene_local_translation_m": _error(mj_world[:3, 3], isaac_world[:3, 3]),
        "scene_local_rotation_deg": _rotation_deg(mj_world[:3, :3], isaac_world[:3, :3]),
        "common_center_index_K": _error(mj_k, common_k),
        "frame_id": {
            "mujoco": int(mujoco_json["camera"]["frame_ids_left_right_head"][_CAMERAS.index(camera)]),
            "isaac": int(source["post_render"]["frame_id"]),
        },
        "source_timestamp_s": {
            "mujoco": float(mujoco_json["camera"]["source_timestamps_s_left_right_head"][_CAMERAS.index(camera)]),
            "isaac": float(source["post_render"]["source_timestamp_s"]),
        },
    }


def _state_invariants(mujoco_npz: Mapping[str, np.ndarray], isaac: Mapping[str, Any]) -> dict[str, Any]:
    qpos = _npz_array(mujoco_npz, "root_and_joint_qpos27_float64", np.dtype(np.float64), (27,))
    qvel = _npz_array(mujoco_npz, "root_and_joint_qvel26_float64", np.dtype(np.float64), (26,))
    robot = isaac["robot"]
    isaac_qpos = np.asarray(robot["readback_root_local_wxyz"][:7] + robot["readback_joint_qpos"], dtype=np.float64)
    isaac_qvel = np.asarray(robot["readback_root_local_wxyz"][7:] + robot["readback_joint_qvel"], dtype=np.float64)
    return {"qpos27": _error(isaac_qpos, qpos), "qvel26": _error(isaac_qvel, qvel)}


def _episode_summary(factor_dir: Path, paired_json: Mapping[str, Any]) -> dict[str, Any]:
    receipt_text = paired_json["source"]["authority_receipt"]
    anchor = Path(receipt_text).resolve(strict=True)
    episode_root = anchor.parents[2]
    all_receipts = sorted((episode_root / "episodes").glob("*/receipt.json"))
    receipt_by_case = {path.parent.name: path for path in all_receipts}
    receipts = [
        receipt_by_case[case_id]
        for case_id in _FIXED_EVALUATION_CASE_IDS
        if case_id in receipt_by_case
    ]
    rows: dict[str, dict[str, Any]] = {}
    for path in receipts:
        receipt = _read_json(path)
        telemetry = receipt.get("stage2_telemetry_summary", {})
        if not isinstance(telemetry, Mapping):
            raise TypeError(f"{path} stage2_telemetry_summary must be a mapping")
        case_id = receipt.get("case_id")
        if not isinstance(case_id, str):
            raise TypeError(f"{path} lacks string case_id")
        rows[case_id] = {
            "max_stage": int(receipt["max_stage"]),
            "goal_reached": bool(receipt["goal_reached"]),
            "terminal_reason": str(receipt["terminal_reason"]),
            "both_handle_contact_control_steps": int(telemetry.get("both_handle_contact_control_steps", 0)),
            "valid_squeeze_control_steps": int(telemetry.get("valid_squeeze_control_steps", 0)),
            "max_squeeze_streak_control_steps": int(telemetry.get("max_squeeze_streak_control_steps", 0)),
        }
    if not rows:
        return {"receipt_root": str(episode_root), "status": "NOT_RUN", "case_rows": {}, "aggregate": None}
    missing = sorted(set(_FIXED_EVALUATION_CASE_IDS) - set(rows))
    if missing:
        raise RuntimeError(f"fixed16 evaluation is incomplete under {episode_root}: {missing}")
    stage_counts = Counter(row["max_stage"] for row in rows.values())
    terminal_counts = Counter(row["terminal_reason"] for row in rows.values())
    return {
        "receipt_root": str(episode_root),
        "status": "AVAILABLE",
        "selected_case_ids": list(_FIXED_EVALUATION_CASE_IDS),
        "ignored_receipt_case_ids": sorted(set(receipt_by_case) - set(_FIXED_EVALUATION_CASE_IDS)),
        "case_rows": rows,
        "aggregate": {
            "n_cases": len(rows),
            "goal_count": sum(row["goal_reached"] for row in rows.values()),
            "stage_counts": {str(key): value for key, value in sorted(stage_counts.items())},
            "terminal_reason_counts": dict(sorted(terminal_counts.items())),
            "both_handle_contact_control_steps_total": sum(row["both_handle_contact_control_steps"] for row in rows.values()),
            "valid_squeeze_control_steps_total": sum(row["valid_squeeze_control_steps"] for row in rows.values()),
            "max_squeeze_streak_control_steps_max": max(row["max_squeeze_streak_control_steps"] for row in rows.values()),
        },
    }


def _receipt_delta(baseline: Mapping[str, Any], factor: Mapping[str, Any]) -> Mapping[str, Any]:
    if baseline["status"] != "AVAILABLE" or factor["status"] != "AVAILABLE":
        return {"status": "NOT_RUN_MISSING_EVALUATION_RECEIPTS"}
    baseline_rows = baseline["case_rows"]
    factor_rows = factor["case_rows"]
    common_ids = sorted(set(baseline_rows) & set(factor_rows))
    if not common_ids:
        return {"status": "NOT_RUN_NO_COMMON_CASE_IDS"}
    fields = (
        "max_stage",
        "goal_reached",
        "both_handle_contact_control_steps",
        "valid_squeeze_control_steps",
        "max_squeeze_streak_control_steps",
    )
    sums = {}
    for field in fields:
        sums[field] = sum(float(factor_rows[case][field]) - float(baseline_rows[case][field]) for case in common_ids)
    return {
        "status": "AVAILABLE",
        "common_case_count": len(common_ids),
        "only_stable_baseline": sorted(set(baseline_rows) - set(factor_rows)),
        "only_factor": sorted(set(factor_rows) - set(baseline_rows)),
        "sum_factor_minus_stable_baseline": sums,
    }


def _parse_factor_dirs(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not name or not raw_path:
            raise ValueError("--factor-dir must have the exact form NAME=PAIRED_EXPORT_DIRECTORY")
        if name not in _FACTORS:
            raise ValueError(f"unknown appearance factor {name!r}; expected {_FACTORS}")
        if name in parsed:
            raise ValueError(f"duplicate factor directory for {name!r}")
        parsed[name] = Path(raw_path).resolve(strict=True)
    if tuple(sorted(parsed)) != tuple(sorted(_FACTORS)):
        missing = sorted(set(_FACTORS) - set(parsed))
        raise ValueError(f"exactly one paired export is required for every factor; missing {missing}")
    return parsed


def analyze(args: argparse.Namespace) -> None:
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    factors = _parse_factor_dirs(args.factor_dir)
    isaac_dir = args.isaac_dir.resolve(strict=True)
    isaac_array_schema = _read_json(isaac_dir / "paired_base000_visual_t0.json")
    isaac = _read_json(isaac_dir / "paired_base000_visual_t0_realization.json")
    if isaac_array_schema.get("schema") != "a2_depthadd_visual_t0_arrays_v1":
        raise ValueError("unexpected Isaac t0 array schema")
    if isaac.get("gate") != "EXACT_VISUAL_STATE_T0_ONLY" or isaac.get("result") != "PASS_WITH_EXPLICIT_PIXEL_COORDINATE_CONVERSION":
        raise RuntimeError("Isaac t0 bundle is not the required exact visual-state authority")
    with np.load(isaac_dir / "paired_base000_visual_t0.npz") as loaded:
        isaac_npz = {key: loaded[key] for key in loaded.files}

    report_lanes: dict[str, Any] = {}
    for name in _FACTORS:
        factor_dir = factors[name]
        mujoco_json = _read_json(factor_dir / "paired_render_mujoco_t0.json")
        if mujoco_json.get("schema") != "doordog.sim2sim.depthadd_v3.paired_render_mujoco_t0.v2":
            raise ValueError(f"{name} must be exported with paired-render schema v2")
        with np.load(factor_dir / "paired_render_mujoco_t0.npz") as loaded:
            mujoco_npz = {key: loaded[key] for key in loaded.files}
        raw_rgb, policy_rgb, depth = {}, {}, {}
        for camera in _CAMERAS:
            shape = _RGB_SHAPES[camera]
            isaac_rgb = _npz_array(isaac_npz, f"raw_{camera}_rgb_uint8", np.dtype(np.uint8), shape)
            raw = _npz_array(mujoco_npz, f"raw_{camera}_rgb_uint8", np.dtype(np.uint8), shape)
            post = _npz_array(mujoco_npz, f"post_color_pipeline_{camera}_rgb_uint8", np.dtype(np.uint8), shape)
            raw_rgb[camera] = _rgb(isaac_rgb, raw)
            policy_rgb[camera] = _rgb(isaac_rgb, post)
        for camera in ("left", "right"):
            reference_depth, reference_valid = _depth(isaac_npz, camera)
            observed_depth, observed_valid = _depth(mujoco_npz, camera)
            depth[camera] = _depth_metrics(reference_depth, observed_depth, reference_valid, observed_valid)
        frame_meta = {
            "camera_meta6": _error(
                _npz_array(isaac_npz, "camera_meta6_float32", np.dtype(np.float32), (6,)),
                _npz_array(mujoco_npz, "camera_meta6_float32", np.dtype(np.float32), (6,)),
            ),
            "frame_ids_equal": bool(np.array_equal(
                _npz_array(isaac_npz, "camera_frame_ids_int64", np.dtype(np.int64), (3,)),
                _npz_array(mujoco_npz, "camera_frame_ids_int64", np.dtype(np.int64), (3,)),
            )),
            "timestamps_s": _error(
                _npz_array(isaac_npz, "camera_source_timestamps_s_float64", np.dtype(np.float64), (3,)),
                _npz_array(mujoco_npz, "camera_source_timestamps_s_float64", np.dtype(np.float64), (3,)),
            ),
        }
        report_lanes[name] = {
            "paired_export_dir": str(factor_dir),
            "factor_receipt": mujoco_json["fixed_nominal_color_pipeline"],
            "raw_renderer_rgb": raw_rgb,
            "policy_rgb_after_color_pipeline": policy_rgb,
            "depth": depth,
            "state_invariants": _state_invariants(mujoco_npz, isaac),
            "camera_invariants": {camera: _camera_invariants(mujoco_json, isaac, camera) for camera in _CAMERAS},
            "camera_meta_invariants": frame_meta,
            "evaluation_receipts": _episode_summary(factor_dir, mujoco_json),
        }

    stable = report_lanes["stable_baseline"]["evaluation_receipts"]
    for name in _FACTORS:
        report_lanes[name]["evaluation_receipt_delta_vs_stable_baseline"] = _receipt_delta(
            stable, report_lanes[name]["evaluation_receipts"]
        )
    report = {
        "schema": "doordog.sim2sim.depthadd_v3.fixed_nominal_appearance_factor_analysis.v1",
        "result": "RUNTIME_T0_FACTOR_ABLATION_COMPLETE",
        "scope": "exact-state t0 raw-renderer and post-color-pipeline policy RGB comparison plus any available fixed evaluation receipt deltas",
        "inputs": {"isaac_exact_visual_t0": str(isaac_dir), "factor_dirs": {name: str(path) for name, path in factors.items()}},
        "lanes": report_lanes,
        "typed_conclusion": {
            "appearance_factor_ablation": "DESCRIPTIVE_ONLY",
            "renderer_equivalence": "NOT_CLAIMED",
            "materials_equivalence": "NOT_CLAIMED",
            "policy_or_mechanics_causality": "NOT_ESTABLISHED_BY_T0_RENDER_COMPARISON",
            "wall_probe_20m": "NOT_RUN",
        },
    }
    output.mkdir(parents=True)
    (output / "appearance_factor_analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# DepthADD v3 fixed-nominal appearance factor analysis",
        "",
        "This is a factor ablation. It does not claim MuJoCo/Isaac renderer or material equivalence.",
        "",
        "| Lane | Camera | Raw RGB MAE | Policy RGB MAE | Depth IoU | Depth MAE (m) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name in _FACTORS:
        lane = report_lanes[name]
        for camera in _CAMERAS:
            depth_value = lane["depth"].get(camera)
            lines.append(
                f"| {name} | {camera} | {lane['raw_renderer_rgb'][camera]['mae']:.4f} | "
                f"{lane['policy_rgb_after_color_pipeline'][camera]['mae']:.4f} | "
                f"{depth_value['valid_iou']:.6f} | {depth_value['intersection_abs_error_m']['mae']:.6f} |"
                if depth_value is not None
                else f"| {name} | {camera} | {lane['raw_renderer_rgb'][camera]['mae']:.4f} | "
                f"{lane['policy_rgb_after_color_pipeline'][camera]['mae']:.4f} | — | — |"
            )
    lines += [
        "",
        "## Fixed16 closed-loop outcomes",
        "",
        "| Lane | Max-stage counts | Goal | Both-contact steps | Valid-squeeze steps | Max streak |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name in _FACTORS:
        aggregate = report_lanes[name]["evaluation_receipts"]["aggregate"]
        if aggregate is None:
            lines.append(f"| {name} | NOT_RUN | — | — | — | — |")
        else:
            lines.append(
                f"| {name} | {json.dumps(aggregate['stage_counts'], sort_keys=True)} | "
                f"{aggregate['goal_count']}/{aggregate['n_cases']} | "
                f"{aggregate['both_handle_contact_control_steps_total']} | "
                f"{aggregate['valid_squeeze_control_steps_total']} | "
                f"{aggregate['max_squeeze_streak_control_steps_max']} |"
            )
    lines += ["", "## Fixed evaluation receipt deltas", ""]
    for name in _FACTORS:
        value = report_lanes[name]["evaluation_receipt_delta_vs_stable_baseline"]
        lines.append(f"- `{name}`: `{value['status']}`; {json.dumps(value, sort_keys=True)}")
    lines += ["", "State, camera pose/K, frame-id, timestamp, and camera-meta invariants are recorded per lane in the JSON report."]
    (output / "APPEARANCE_FACTOR_ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isaac-dir", type=Path, required=True)
    parser.add_argument(
        "--factor-dir",
        action="append",
        required=True,
        help="NAME=PAIRED_EXPORT_DIRECTORY; provide exactly one for each stable_baseline, lighting, background, materials, renderer_color_pipeline",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    analyze(parser.parse_args())


if __name__ == "__main__":
    main()
