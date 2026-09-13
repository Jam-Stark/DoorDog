#!/usr/bin/env python3
"""Reduce v28 camera telemetry from one all-stage evaluation trace."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


SCHEMA = "a2_piper_base_v28_camera_metrics_v2"
NATIVE_PARAMETERS = Path(__file__).resolve().parent / "camera/d435_native_sim_parameters_20260907.json"
REQUIRED = {
    "v28_flange_pos_w": (3,), "v28_flange_quat_w": (4,), "v28_flange_ang_vel_w": (3,),
    "v28_trunk_ang_vel_w": (3,), "v28_handle_target_pos_w": (3,), "v28_door_panel_pos_w": (3,),
    "v28_door_panel_quat_w": (4,), "arm_joint_pos": (6,), "arm_joint_vel": (6,),
    "v28_arm_default_pose_rad": (6,),
}
SCALARS = (
    "v28_door_width_m", "v28_door_height_m", "v28_tower_contact_force_N", "control_dt",
    "v28_handle_bearing_deg", "v28_doorway_bearing_deg", "v28_root_yaw_relative_door_deg",
    "v28_vy_cmd_m_s",
)


def vector(row: dict, name: str, shape: tuple[int, ...]) -> np.ndarray:
    value = np.asarray(row[name], dtype=np.float64)
    if value.shape != shape or not np.isfinite(value).all():
        raise ValueError(f"{name} must be finite shape {shape}, got {value.shape}")
    return value


def scalar(row: dict, name: str) -> float:
    value = row[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite scalar, got {value!r}")
    return float(value)


def quat_matrix(quat: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(quat)
    if norm <= np.finfo(np.float64).eps:
        raise ValueError("quaternion must be non-degenerate")
    w, x, y, z = quat / norm
    return np.array(((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
                     (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
                     (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))))


def box_surface_points(size: np.ndarray, pitch: float = 0.01) -> np.ndarray:
    half = size / 2
    axes = [np.linspace(-half[i], half[i], max(2, int(math.ceil(size[i] / pitch)) + 1)) for i in range(3)]
    points = []
    for fixed in range(3):
        other = [axis for axis in range(3) if axis != fixed]
        grid = np.array(np.meshgrid(axes[other[0]], axes[other[1]], indexing="ij")).reshape(2, -1).T
        for sign in (-1.0, 1.0):
            face = np.zeros((len(grid), 3)); face[:, other] = grid; face[:, fixed] = sign * half[fixed]
            points.append(face)
    return np.unique(np.concatenate(points), axis=0)


def sdf_box(points: np.ndarray, center: np.ndarray, half: np.ndarray) -> np.ndarray:
    delta = np.abs(points - center) - half
    return np.linalg.norm(np.maximum(delta, 0.0), axis=-1) + np.minimum(np.max(delta, axis=-1), 0.0)


def summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p5": None, "p50": None, "p95": None, "max": None}
    data = np.asarray(values, dtype=np.float64)
    return {"min": float(np.min(data)), "p5": float(np.percentile(data, 5)), "p50": float(np.percentile(data, 50)),
            "p95": float(np.percentile(data, 95)), "max": float(np.max(data))}


def load_rig(path: Path) -> tuple[dict[str, np.ndarray], np.ndarray]:
    rig = json.loads(path.read_text(encoding="utf-8"))
    if rig["plan_id"] != "U3_F39_H140":
        raise ValueError(f"v28 metrics requires U3_F39_H140, got {rig['plan_id']!r}")
    wrist = [camera for camera in rig["cameras"] if camera["name"] == "wrist"]
    if len(wrist) != 1 or wrist[0]["parent"] != "arm_body6_to_gripper":
        raise ValueError("rig must contain exactly one wrist camera on arm_body6_to_gripper")
    transforms = {}
    for name in ("depth", "rgb"):
        stream = wrist[0]["streams"][name]
        transform = np.asarray(stream["T_parent_optical"], dtype=np.float64)
        if transform.shape != (4, 4) or not np.isfinite(transform).all():
            raise ValueError(f"wrist {name} T_parent_optical must be finite 4x4")
        for key in ("K", "width", "height"):
            if key not in stream:
                raise ValueError(f"wrist {name} stream lacks {key}")
        transforms[name] = transform
    boxes = []
    for bracket in rig["brackets"]:
        if bracket["parent"] != "arm_body6_to_gripper":
            continue
        size = np.asarray(bracket["size_m"], dtype=np.float64)
        transform = np.asarray(bracket["T_parent_item"], dtype=np.float64)
        if size.shape != (3,) or transform.shape != (4, 4) or not np.isfinite(size).all() or not np.isfinite(transform).all():
            raise ValueError(f"invalid wrist bracket geometry: {bracket.get('name')!r}")
        boxes.append(box_surface_points(size) @ transform[:3, :3].T + transform[:3, 3])
    housing_size = np.asarray(rig["housing_size_M_m"], dtype=np.float64)
    housing_transform = np.asarray(wrist[0]["T_parent_M"], dtype=np.float64)
    if housing_size.shape != (3,) or housing_transform.shape != (4, 4):
        raise ValueError("invalid wrist housing geometry")
    boxes.append(box_surface_points(housing_size) @ housing_transform[:3, :3].T + housing_transform[:3, 3])
    return transforms, np.concatenate(boxes)


def project(point_w: np.ndarray, flange_pos: np.ndarray, flange_rot: np.ndarray, stream: dict, transform: np.ndarray) -> tuple[bool, np.ndarray]:
    optical_rot = flange_rot @ transform[:3, :3]
    optical_pos = flange_pos + flange_rot @ transform[:3, 3]
    point_o = optical_rot.T @ (point_w - optical_pos)
    if point_o[2] <= 0.0:
        return False, point_o
    K = np.asarray(stream["K"], dtype=np.float64)
    if K.shape != (3, 3) or not np.isfinite(K).all():
        raise ValueError("wrist camera K must be finite 3x3")
    u = K[0][0] * point_o[0] / point_o[2] + K[0][2]
    v = K[1][1] * point_o[1] / point_o[2] + K[1][2]
    return 0.0 <= u < float(stream["width"]) and 0.0 <= v < float(stream["height"]), point_o


def reversal_stats(records: list[dict]) -> dict[str, float | int | None]:
    by_episode: dict[int, list[dict]] = defaultdict(list)
    for row in records: by_episode[row["env_id"]].append(row)
    reversals = 0; duration_s = 0.0; pairs = 0
    for episode_rows in by_episode.values():
        episode_rows.sort(key=lambda row: row["step_index"])
        for previous, current in zip(episode_rows[:-1], episode_rows[1:], strict=True):
            if current["step_index"] != previous["step_index"] + 1:
                continue
            gap = current["step_index"] * scalar(current, "control_dt") - previous["step_index"] * scalar(previous, "control_dt")
            if gap <= 0.0:
                raise ValueError("consecutive trace rows must have increasing timestamps")
            previous_q6 = vector(previous, "arm_joint_vel", (6,))[5]
            current_q6 = vector(current, "arm_joint_vel", (6,))[5]
            duration_s += gap; pairs += 1
            reversals += int(abs(previous_q6) > 0.3 and abs(current_q6) > 0.3 and previous_q6 * current_q6 < 0.0)
    return {"count": reversals, "consecutive_pairs": pairs, "observed_contiguous_duration_s": duration_s,
            "per_s": None if duration_s == 0.0 else reversals / duration_s}


def parse_rows(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("trace must be a non-empty JSON array")
    selected = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"trace row {index} is not an object")
        for name in (*REQUIRED, *SCALARS, "stage_buf", "env_id", "step_index", "first_episode_active", "episode_index", "v28_post_release", "v28_crossing_yaw_deg", "v28_vy_cmd_at_clip"):
            if name not in row:
                raise ValueError(f"trace row {index} lacks required v28 telemetry field {name}")
        if row["first_episode_active"] is not True or row["episode_index"] != 0:
            continue
        for name, shape in REQUIRED.items(): vector(row, name, shape)
        for name in SCALARS: scalar(row, name)
        if row["v28_crossing_yaw_deg"] is not None:
            scalar(row, "v28_crossing_yaw_deg")
        if not isinstance(row["v28_vy_cmd_at_clip"], bool):
            raise ValueError(f"trace row {index} requires bool v28_vy_cmd_at_clip")
        if scalar(row, "control_dt") <= 0.0 or scalar(row, "v28_door_width_m") <= 0.0 or scalar(row, "v28_door_height_m") <= 0.0:
            raise ValueError(f"trace row {index} has non-positive dt or door dimensions")
        if scalar(row, "v28_tower_contact_force_N") < 0.0 or not isinstance(row["v28_post_release"], bool):
            raise ValueError(f"trace row {index} has invalid tower contact or post-release flag")
        if not all(isinstance(row[name], int) for name in ("stage_buf", "env_id", "step_index", "episode_index")):
            raise ValueError(f"trace row {index} requires integer stage/env/step/episode fields")
        selected.append(row)
    if not selected:
        raise ValueError("trace has no first-episode active records")
    return selected


def reduce(trace: Path, rig_path: Path) -> dict:
    rig = json.loads(rig_path.read_text(encoding="utf-8"))
    transforms, tower_points_f = load_rig(rig_path)
    wrist = next(camera for camera in rig["cameras"] if camera["name"] == "wrist")
    native = json.loads(NATIVE_PARAMETERS.read_text(encoding="utf-8"))["cameras"]["wrist"]
    transforms["rgb"] = transforms["depth"] @ np.asarray(
        native["inter_stream_extrinsics"]["rgb__to__depth"]["T_target_source"], dtype=np.float64
    )
    for name in ("depth", "rgb"):
        for key in ("K", "width", "height"):
            wrist["streams"][name][key] = native["streams"][name][key]
    rows = parse_rows(trace)
    by_stage: dict[int, list[dict]] = defaultdict(list)
    for row in rows: by_stage[row["stage_buf"]].append(row)

    def block(records: list[dict]) -> dict:
        metrics = defaultdict(list); contacts = []; high_force_envs = set()
        for row in records:
            flange_pos, flange_rot = vector(row, "v28_flange_pos_w", (3,)), quat_matrix(vector(row, "v28_flange_quat_w", (4,)))
            flange_omega = vector(row, "v28_flange_ang_vel_w", (3,)); trunk_omega = vector(row, "v28_trunk_ang_vel_w", (3,))
            axis_w = flange_rot @ transforms["depth"][:3, 2]
            metrics["wrist_cam_ang_speed_deg_s"].append(float(np.linalg.norm(flange_omega) * 180.0 / math.pi))
            metrics["wrist_cam_axis_sweep_deg_s"].append(float(np.linalg.norm(np.cross(flange_omega, axis_w)) * 180.0 / math.pi))
            metrics["wrist_cam_axis_elev_deg"].append(float(math.asin(np.clip(axis_w[2], -1.0, 1.0)) * 180.0 / math.pi))
            metrics["base_cam_ang_speed_deg_s"].append(float(np.linalg.norm(trunk_omega) * 180.0 / math.pi))
            q = vector(row, "arm_joint_pos", (6,)); q_default = vector(row, "v28_arm_default_pose_rad", (6,))
            metrics["arm_j6_abs_dev_from_1p57_rad"].append(float(abs(q[5] - 1.57)))
            metrics["arm_posture_l1_rad"].append(float(np.abs(q - q_default).sum()))
            handle = vector(row, "v28_handle_target_pos_w", (3,))
            for name in ("depth", "rgb"):
                stream = wrist["streams"][name]
                visible, point_o = project(handle, flange_pos, flange_rot, stream, transforms[name])
                if name == "depth": visible = visible and point_o[2] >= float(stream["min_z_mask_m"])
                metrics[f"handle_in_wrist_{name}"].append(float(visible))
            tower_w = tower_points_f @ flange_rot.T + flange_pos
            panel_local = (tower_w - vector(row, "v28_door_panel_pos_w", (3,))) @ quat_matrix(vector(row, "v28_door_panel_quat_w", (4,)))
            panel_half = np.array((0.02, scalar(row, "v28_door_width_m") / 2, scalar(row, "v28_door_height_m") / 2))
            metrics["wrist_tower_panel_sampled_clearance_m"].append(float(sdf_box(panel_local, np.array((0.0, 0.0, panel_half[2])), panel_half).min()))
            force = scalar(row, "v28_tower_contact_force_N"); contacts.append(force > 1.0)
            if force > 5.0: high_force_envs.add(row["env_id"])
        output = {name: summary(values) for name, values in metrics.items()
                  if name not in ("handle_in_wrist_depth", "handle_in_wrist_rgb")}
        output["wrist_cam_share_axis_sweep_gt_60"] = float(np.mean(np.asarray(metrics["wrist_cam_axis_sweep_deg_s"]) > 60.0))
        output["arm_j6_reversals"] = reversal_stats(records)
        output["handle_in_wrist_depth_share"] = float(np.mean(metrics["handle_in_wrist_depth"]))
        output["handle_in_wrist_rgb_share"] = float(np.mean(metrics["handle_in_wrist_rgb"]))
        output["wrist_tower_contact_step_share_gt_1N"] = float(np.mean(contacts))
        output["wrist_tower_contact_episodes_gt_5N"] = len(high_force_envs)
        output["records"] = len(records)
        return output

    stages = {str(stage): block(records) for stage, records in sorted(by_stage.items())}
    overall = block(rows)
    post_release = defaultdict(list)
    for row in rows: post_release[row["env_id"]].append(row)
    observed, censored = [], []
    for env_id, records in post_release.items():
        records.sort(key=lambda row: row["step_index"])
        released = [row for row in records if row["v28_post_release"]]
        if not released: continue
        start = released[0]["step_index"] * scalar(released[0], "control_dt")
        hit = next((row for row in released if np.abs(vector(row, "arm_joint_pos", (6,)) - vector(row, "v28_arm_default_pose_rad", (6,))).sum() < 0.5), None)
        if hit is None:
            censored.append(records[-1]["step_index"] * scalar(records[-1], "control_dt") - start)
        else:
            observed.append(hit["step_index"] * scalar(hit, "control_dt") - start)
    overall["post_release_return_time_s"] = {"threshold_l1_rad": 0.5, "observed_episodes": len(observed),
        "right_censored_episodes": len(censored), "observed": summary(observed), "censor_duration": summary(censored)}
    stage0_2 = [row for row in rows if row["stage_buf"] in (0, 1, 2)]
    stage5 = [row for row in rows if row["stage_buf"] == 5]
    stage2_4 = [row for row in rows if row["stage_buf"] in (2, 3, 4)]
    stage0_5 = [row for row in rows if row["stage_buf"] in (0, 5)]
    handle_bearing = [abs(scalar(row, "v28_handle_bearing_deg")) for row in stage0_2]
    doorway_bearing = [abs(scalar(row, "v28_doorway_bearing_deg")) for row in stage5]
    crossing_by_env = {}
    for row in sorted(rows, key=lambda row: (row["env_id"], row["step_index"])):
        if row["v28_crossing_yaw_deg"] is not None:
            crossing_by_env.setdefault(row["env_id"], abs(scalar(row, "v28_crossing_yaw_deg")))
    crossing = summary(list(crossing_by_env.values()))
    posture = summary([float(np.abs(vector(row, "arm_joint_pos", (6,)) - vector(row, "v28_arm_default_pose_rad", (6,))).sum()) for row in stage0_5])
    q6 = summary([float(abs(vector(row, "arm_joint_pos", (6,))[5] - 1.57)) for row in stage0_5])
    plan_fields = {}
    for metric, output, quantiles in (
        ("wrist_cam_ang_speed_deg_s", "wrist_cam_ang_speed", ("p50", "p95")),
        ("wrist_cam_axis_sweep_deg_s", "wrist_cam_axis_sweep", ("p95",)),
        ("base_cam_ang_speed_deg_s", "base_cam_ang_speed", ("p95",)),
    ):
        for quantile in quantiles:
            plan_fields[f"{output}_{quantile}_deg_s"] = overall[metric][quantile]
    for quantile in ("p5", "p50", "p95"):
        plan_fields[f"wrist_cam_axis_elev_{quantile}_deg"] = overall["wrist_cam_axis_elev_deg"][quantile]
    for quantile in ("p50", "p95"):
        plan_fields[f"arm_posture_l1_{quantile}_rad"] = posture[quantile]
        plan_fields[f"post_release_return_time_{quantile}_s"] = summary(observed)[quantile]
        plan_fields[f"handle_bearing_deg_{quantile}_stage0_2"] = summary(handle_bearing)[quantile]
        plan_fields[f"crossing_yaw_deg_{quantile}"] = crossing[quantile]
    plan_fields.update({
        "wrist_cam_share_axis_sweep_gt_60": overall["wrist_cam_share_axis_sweep_gt_60"],
        "arm_j6_reversals_per_s": overall["arm_j6_reversals"]["per_s"],
        "arm_j6_abs_dev_from_1p57_p95": q6["p95"],
        "wrist_tower_panel_min_clearance_m": overall["wrist_tower_panel_sampled_clearance_m"]["min"],
        "wrist_tower_contact_step_share": overall["wrist_tower_contact_step_share_gt_1N"],
        "wrist_tower_contact_episodes_gt_5N": overall["wrist_tower_contact_episodes_gt_5N"],
        "handle_bearing_gt_30deg_share_stage0_2": None if not handle_bearing else float(np.mean(np.asarray(handle_bearing) > 30.0)),
        "doorway_bearing_deg_p95_stage5": summary(doorway_bearing)["p95"],
        "stage0_2_vy_cmd_at_clip_share": None if not stage0_2 else float(np.mean([row["v28_vy_cmd_at_clip"] for row in stage0_2])),
    })
    for stream_name in ("depth", "rgb"):
        count = sum(stages[str(stage)]["records"] for stage in (2, 3, 4) if str(stage) in stages)
        visible = sum(stages[str(stage)][f"handle_in_wrist_{stream_name}_share"] * stages[str(stage)]["records"] for stage in (2, 3, 4) if str(stage) in stages)
        plan_fields[f"handle_in_wrist_{stream_name}_share_stage2_4"] = None if count == 0 else visible / count
    return {"schema": SCHEMA, "trace": str(trace), "rig": str(rig_path), "population": "first_episode_active && episode_index == 0",
            "native_calibration": str(NATIVE_PARAMETERS),
            "projection": "measured SDK K and RGB-to-depth extrinsics; depth-module mounting transform from the nominal rig; pinhole visibility without occlusion or stereo reconstruction",
            "geometry": "wrist support + housing box surface samples at 10mm pitch; panel local AABB x=+/-0.02, y=+/-width/2, z=[0,height]; sampled trace result is an upper bound, not exact or hardware clearance",
            "orientation_definition": "bearings are horizontal relative to trunk yaw; reported quantiles use absolute signed angles; crossing yaw is latched at the existing first root-X crossing and counted once per episode; vy clip is physical +/-0.5 m/s",
            "sample_counts": {"all": len(rows), "stage0_2": len(stage0_2), "stage5": len(stage5), "stage2_4": len(stage2_4), "stage0_5": len(stage0_5), "crossing_episodes": len(crossing_by_env)},
            "plan_fields": plan_fields, "overall": overall, "stages": stages}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--rig", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.trace.is_file() or not args.rig.is_file() or not args.output.parent.is_dir():
        raise FileNotFoundError("trace and rig must exist and output parent must exist")
    result = reduce(args.trace, args.rig)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
