#!/usr/bin/env python3
"""CPU-only G0-A4 and G0-C3 checks for the selected v28 MERGED asset.

The two checks deliberately preserve their evidence boundaries.  A4 is convex-hull
geometry on the frozen reset pose, using the planner's LP/QP hull implementation;
it is not a PhysX contact probe.  C3 replays sampled archived v27 flange traces
against the new wrist support/housing envelope; it is not evidence about a v28
policy.  Both write their inputs and raw findings to one explicit JSON output.
"""
from __future__ import annotations

import argparse
import collections
import csv
import importlib.util
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import yaml


REPO = Path(__file__).resolve().parents[2]
PLANNER_ASSET = REPO / "scriptsFORhuman/v28/planner_evidence_20260909/asset/mount_clearance_check.py"
PLANNER_T4 = REPO / "scriptsFORhuman/v28/planner_evidence_20260909/camera/t4_clearance.py"
DEFAULT_URDF = REPO / "gr00t/rl/data/robots/a2_piper_v28_merged_20260909/a2_piper.urdf"
DEFAULT_ROBOT_YAML = REPO / "gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml"
DEFAULT_RIG = REPO / "scriptsFORhuman/v28/camera/U3_F39_H140.json"
DEFAULT_TRACE = Path(
    "/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103/"
    "camera_setup/A2-Rail-Dual-D435i/data/camera_trajectories.csv"
)
DEFAULT_PREPARATION = REPO / (
    "scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/"
    "resume_20260911/static_gate_preparation.json"
)
V27_CELLS = {"C_S2", "C_S21"}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _frozen_joint_positions(robot_yaml: Path) -> dict[str, float]:
    resolved = yaml.safe_load(robot_yaml.read_text())
    values = resolved["robot"]["init_state"]["default_joint_angles"]
    if not isinstance(values, dict):
        raise ValueError("robot.init_state.default_joint_angles must be a mapping")
    return {name: float(value) for name, value in values.items()}


def _direct_parent_child_pairs(joints: dict) -> set[frozenset[str]]:
    return {frozenset((joint["parent"], joint["child"])) for joint in joints.values()}


def _pair_minimum(asset, hulls: dict, transforms: dict, left: str, right: str) -> dict:
    """Return the closest convex-collider pair, including a positive overlap depth."""
    best = None
    for left_hull in hulls[left]:
        world_left = left_hull.transformed(transforms[left])
        for right_hull in hulls[right]:
            world_right = right_hull.transformed(transforms[right])
            centre_gap = float(np.linalg.norm(world_left.c - world_right.c) - world_left.r - world_right.r)
            if centre_gap > 0.02:
                candidate = (centre_gap, "bounding_sphere_lower_bound", left_hull.name, right_hull.name)
            else:
                depth = asset.intersect_depth(world_left, world_right)
                if depth is not None and depth > 1e-7:
                    candidate = (-depth, "interior_overlap", left_hull.name, right_hull.name)
                else:
                    candidate = (asset.distance(world_left, world_right), "separated", left_hull.name, right_hull.name)
            if best is None or candidate[0] < best[0]:
                best = candidate
    if best is None:
        raise ValueError(f"no collision hull pairs for {left}, {right}")
    return {
        "links": [left, right],
        "minimum_signed_clearance_m": float(best[0]),
        "solver": best[1],
        "collision_hulls": [best[2], best[3]],
    }


def run_a4(urdf: Path, robot_yaml: Path, output: Path) -> dict:
    asset = _load_module("v28_g0_asset_clearance", PLANNER_ASSET)
    links, joints, base = asset.parse(str(urdf))
    q = _frozen_joint_positions(robot_yaml)
    unknown = sorted(set(q) - set(joints))
    if unknown:
        raise ValueError(f"frozen posture refers to joints absent from {urdf}: {unknown}")
    missing_transforms = set(links) - set(asset.fk(joints, q))
    if missing_transforms:
        raise ValueError(f"URDF links unreachable from trunk: {sorted(missing_transforms)}")
    names = [name for name, collisions in links.items() if collisions]
    transforms = asset.fk(joints, q)
    hulls = asset.build_hulls(links, base, names)
    parent_child = _direct_parent_child_pairs(joints)

    same_body = [
        {"link": name, "collision_hull_count": len(hulls[name])}
        for name in names
        if len(hulls[name]) > 1
    ]
    parent_child_rows = []
    actual = []
    for left, right in combinations(names, 2):
        result = _pair_minimum(asset, hulls, transforms, left, right)
        if frozenset((left, right)) in parent_child:
            result["classification"] = "direct_parent_child_filtered_by_articulation"
            parent_child_rows.append(result)
        else:
            result["classification"] = "actual_contact_pair_requires_investigation"
            actual.append(result)

    actual.sort(key=lambda row: row["minimum_signed_clearance_m"])
    parent_child_rows.sort(key=lambda row: row["minimum_signed_clearance_m"])
    overlaps = [row for row in actual if row["solver"] == "interior_overlap"]
    report = {
        "schema": "v28_g0_a4_convex_clearance_v1",
        "evidence_level": "STATIC_CPU",
        "scope": "all URDF links with collision geometry at robot.init_state.default_joint_angles",
        "source_urdf": str(urdf),
        "source_robot_config": str(robot_yaml),
        "frozen_joint_positions_rad": q,
        "algorithm_source": str(PLANNER_ASSET),
        "algorithm": "planner Hull / LP interior-overlap / SLSQP convex separation",
        "same_rigid_body_compositions_not_contact_pairs": same_body,
        "direct_parent_child_filtered_pairs": parent_child_rows,
        "actual_contact_pairs": actual,
        "actual_penetrations": overlaps,
        "outcome": "A4_PASS" if not overlaps else "A4_FAIL_ACTUAL_INTERIOR_PENETRATION",
        "notes": [
            "Merged mount collision primitives are part of trunk and are represented by trunk-vs-other-link pairs.",
            "Direct parent-child geometry is retained in the report even though the articulation filter classifies it outside this contact gate.",
            "Same-rigid-body collision primitives are enumerated as compositions and are not treated as a self-contact pair.",
        ],
    }
    _write_json(output, report)
    return report


def _stage_stats(values: np.ndarray) -> dict:
    return {
        "min_m": float(values.min()),
        "p1_m": float(np.percentile(values, 1)),
        "p5_m": float(np.percentile(values, 5)),
        "p50_m": float(np.percentile(values, 50)),
        "share_lt_0": float(np.mean(values < 0.0)),
        "share_lt_20mm": float(np.mean(values < 0.02)),
    }


def _c3_lane(legacy, rows: list[dict], side: str, points_f: np.ndarray, tags: np.ndarray) -> dict:
    side_sign = 1.0 if side == "left" else -1.0
    rows.sort(key=lambda row: (int(row["env_id"]), int(row["step_index"])))
    by_env: dict[int, list[dict]] = collections.defaultdict(list)
    for row in rows:
        by_env[int(row["env_id"])].append(row)
    fits = {env_id: legacy.fit_width(env_rows, side_sign) for env_id, env_rows in by_env.items()}
    widths = {env_id: fit["W"] if fit and fit["rms_m"] < 0.02 else None for env_id, fit in fits.items()}
    signs = collections.Counter(
        fit["sgn"] for fit in fits.values() if fit and fit["rms_m"] < 0.02
    )
    rotation_sign = -side_sign
    if signs and signs.most_common(1)[0][0] != rotation_sign:
        rotation_sign = signs.most_common(1)[0][0]

    count = len(rows)
    t_d_f = np.zeros((count, 4, 4))
    hinge_angle = np.zeros(count)
    handle_angle = np.zeros(count)
    handle_position = np.zeros((count, 3))
    width = np.zeros(count)
    stage = np.zeros(count, dtype=int)
    estimated_width: dict[int, float] = {}
    for i, row in enumerate(rows):
        env_id = int(row["env_id"])
        t_d_b = np.eye(4)
        t_d_b[:3, :3] = legacy.quat_R(np.array([float(row[f"base_quat_D_wxyz_{k}"]) for k in range(4)]))
        t_d_b[:3, 3] = [float(row[f"base_pos_D_{k}"]) for k in range(3)]
        t_b_f = np.eye(4)
        t_b_f[:3, :3] = legacy.quat_R(np.array([float(row[f"flange_quat_B_wxyz_{k}"]) for k in range(4)]))
        t_b_f[:3, 3] = [float(row[f"flange_pos_B_{k}"]) for k in range(3)]
        t_d_f[i] = t_d_b @ t_b_f
        hinge_angle[i] = float(row["hinge_rad"])
        handle_angle[i] = float(row["handle_rad"])
        handle_position[i] = [float(row[f"handle_pos_D_{k}"]) for k in range(3)]
        stage[i] = int(row["stage"])
        if widths[env_id] is not None:
            width[i] = widths[env_id]
        else:
            if env_id not in estimated_width:
                estimated_width[env_id] = float(min(max(2.0 * (abs(handle_position[i, 1]) + 0.115), 0.8), 1.1))
            width[i] = estimated_width[env_id]

    point_count = len(points_f)
    panel = np.full(count, np.inf)
    handle = np.full(count, np.inf)
    frame = np.full(count, np.inf)
    panel_arg = np.zeros(count, dtype=int)
    for offset in range(0, count, 1500):
        selection = slice(offset, min(count, offset + 1500))
        n = selection.stop - selection.start
        transform = t_d_f[selection]
        points_d = np.einsum("nij,pj->npi", transform[:, :3, :3], points_f) + transform[:, None, :3, 3]
        local_width = width[selection]
        local_hinge = hinge_angle[selection]
        hinge = np.stack([np.full(n, 0.02), -side_sign * local_width / 2, np.zeros(n)], axis=1)
        panel_rotation = np.stack([legacy.rz(rotation_sign * angle) for angle in local_hinge])
        points_panel = np.einsum("nji,npj->npi", panel_rotation, points_d - hinge[:, None, :])
        centre = np.stack([np.full(n, -0.02), side_sign * local_width / 2, np.full(n, legacy.H_NOM / 2)], axis=1)
        half = np.stack([np.full(n, 0.02), local_width / 2 - legacy.GAP, np.full(n, legacy.H_NOM / 2 - legacy.GAP)], axis=1)
        panel_distance = legacy.sdf_box(points_panel - centre[:, None, :], half[:, None, :])
        panel[selection] = panel_distance.min(axis=1)
        panel_arg[selection] = panel_distance.argmin(axis=1)
        grasp_panel = np.einsum("nji,nj->ni", panel_rotation, handle_position[selection] - hinge)
        lever_direction = np.stack(
            [np.zeros(n), -side_sign * np.cos(handle_angle[selection]), -np.sin(handle_angle[selection])], axis=1
        )
        start = grasp_panel - lever_direction * (legacy.L_NOM / 2)
        tip = grasp_panel + lever_direction * (legacy.L_NOM / 2)
        handle_distance = np.full((n, point_count), np.inf)
        for row_index in range(n):
            handle_distance[row_index] = np.minimum.reduce([
                legacy.sdf_capsule(points_panel[row_index], start[row_index], tip[row_index], legacy.R_NOM),
                legacy.sdf_capsule(points_panel[row_index], start[row_index], start[row_index] + np.array([legacy.AXLE_NOM, 0, 0]), legacy.R_NOM),
                legacy.sdf_capsule(points_panel[row_index], tip[row_index], tip[row_index] + np.array([legacy.HOOK_NOM, 0, 0]), legacy.R_NOM),
            ])
        handle[selection] = handle_distance.min(axis=1)
        hinge_jamb = np.stack([np.full(n, -0.02), side_sign * (local_width / 2 - legacy.GAP + 0.5), np.full(n, 1.5)], axis=1)
        grasp_jamb = np.stack([np.full(n, -0.02), -side_sign * (local_width / 2 - legacy.GAP + 0.5), np.full(n, 1.5)], axis=1)
        jamb_half = np.stack([np.full(n, 0.06), np.full(n, 0.5), np.full(n, 1.5)], axis=1)
        lintel = np.stack([np.full(n, -0.02), np.zeros(n), np.full(n, legacy.H_NOM + 0.5)], axis=1)
        lintel_half = np.stack([np.full(n, 0.06), local_width / 2, np.full(n, 0.5)], axis=1)
        frame_distance = np.minimum.reduce([
            legacy.sdf_box(points_d - hinge_jamb[:, None, :], jamb_half[:, None, :]),
            legacy.sdf_box(points_d - grasp_jamb[:, None, :], jamb_half[:, None, :]),
            legacy.sdf_box(points_d - lintel[:, None, :], lintel_half[:, None, :]),
        ])
        frame[selection] = frame_distance.min(axis=1)

    per_stage = {}
    for current_stage in sorted(set(stage)):
        mask = stage == current_stage
        nearest = collections.Counter(tags[panel_arg[mask][panel[mask] < 0.05]].tolist())
        per_stage[f"stage{current_stage}"] = {
            "sampled_frames": int(mask.sum()),
            "panel": _stage_stats(panel[mask]),
            "handle": _stage_stats(handle[mask]),
            "frame": _stage_stats(frame[mask]),
            "panel_closest_item_when_lt_50mm": dict(nearest),
        }
    return {
        "sampled_frames": count,
        "rotation_sign_used": rotation_sign,
        "width_fit": {
            "envs": len(by_env),
            "fitted": sum(value is not None for value in widths.values()),
            "rotation_sign_votes": dict(signs),
        },
        "per_stage": per_stage,
    }


def run_c3(rig: Path, trace: Path, output: Path) -> dict:
    if not rig.is_file():
        raise FileNotFoundError(f"missing final F39/H140 rig: {rig}")
    if not trace.is_file():
        raise FileNotFoundError(f"missing archived v27 trajectory export: {trace}")
    legacy = _load_module("v28_g0_t4_clearance", PLANNER_T4)
    points_f, tags, item_names = legacy.load_items(str(rig))
    expected = {"wrist_camera_support", "wrist_housing"}
    if not expected.issubset(set(item_names)):
        raise ValueError(f"rig does not expose the required wrist collision items: {item_names}")
    rows_by_lane: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    with trace.open() as handle:
        for row in csv.DictReader(handle):
            if row["cell"] in V27_CELLS and int(row["stage"]) in {2, 3, 4, 5}:
                rows_by_lane[(row["cell"], row["side"])].append(row)
    if not rows_by_lane:
        raise ValueError(f"no C_S2/C_S21 Stage2-5 rows in {trace}")
    lanes = {
        f"{cell}/{side}": _c3_lane(legacy, rows, side, points_f, tags)
        for (cell, side), rows in sorted(rows_by_lane.items())
    }
    violations = []
    for lane, result in lanes.items():
        for stage_name in ("stage2", "stage3", "stage4"):
            entry = result["per_stage"].get(stage_name)
            if entry is None:
                violations.append({"lane": lane, "stage": stage_name, "reason": "missing_sampled_trace_stage"})
                continue
            if entry["panel"]["min_m"] < 0.02 or entry["frame"]["min_m"] < 0.02:
                violations.append({
                    "lane": lane,
                    "stage": stage_name,
                    "panel_min_m": entry["panel"]["min_m"],
                    "frame_min_m": entry["frame"]["min_m"],
                })
    report = {
        "schema": "v28_g0_c3_archived_v27_sweep_v1",
        "evidence_level": "COMPUTED_ARCHIVED_TRAJECTORY",
        "source_rig": str(rig),
        "source_trajectory": str(trace),
        "algorithm_source": str(PLANNER_T4),
        "algorithm": "existing t4 door reconstruction and 5 mm surface sampling",
        "items": item_names,
        "points_per_envelope": int(len(points_f)),
        "trace_scope": "C_S2/C_S21; Stage2-5 only; exported frames are dense at 50 Hz in Stage2/3 and sparse in Stage4/5",
        "lanes": lanes,
        "stage2_4_20mm_violations": violations,
        "outcome": "C3_ARCHIVED_V27_TRACE_PASS" if not violations else "C3_ARCHIVED_V27_TRACE_FAIL",
        "v28_policy_interpretation": "NOT_EVALUATED: this result is a collision-envelope replay on archived v27 traces, not a v28 policy result.",
        "stage5_note": "Reported without a pass/fail judgement because this archived export lacks an arm-retracted/release-state field required by the plan's Stage5 exception.",
    }
    _write_json(output, report)
    return report


def write_preparation(output: Path) -> dict:
    report = {
        "schema": "v28_g0_static_gate_preparation_v1",
        "status": "IMPLEMENTED_AWAITING_MAIN_R2_R3_R5_SUCCESS_NOTIFICATION",
        "owner_sequence": "Do not run G0-A4 or G0-C3 until Main reports MERGED R2/R3/R5 success.",
        "selected_asset": str(DEFAULT_URDF),
        "a4": {
            "command": f"{Path(sys.executable)} {Path(__file__).resolve()} a4 --out <output.json>",
            "evidence": "STATIC_CPU convex-hull clearance on the frozen resolved robot posture",
        },
        "c3": {
            "command": f"{Path(sys.executable)} {Path(__file__).resolve()} c3 --out <output.json>",
            "required_rig": str(DEFAULT_RIG),
            "evidence": "COMPUTED replay of archived v27 traces; does not evaluate a v28 policy",
        },
        "not_run": ["G0-A4", "G0-C3"],
    }
    _write_json(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    a4 = subparsers.add_parser("a4", help="run convex clearance on the frozen MERGED reset pose")
    a4.add_argument("--urdf", type=Path, default=DEFAULT_URDF)
    a4.add_argument("--robot-yaml", type=Path, default=DEFAULT_ROBOT_YAML)
    a4.add_argument("--out", required=True, type=Path)
    c3 = subparsers.add_parser("c3", help="sweep the final wrist envelope on archived v27 traces")
    c3.add_argument("--rig", type=Path, default=DEFAULT_RIG)
    c3.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    c3.add_argument("--out", required=True, type=Path)
    prepare = subparsers.add_parser("prepare", help="write the gated handoff record without running checks")
    prepare.add_argument("--out", type=Path, default=DEFAULT_PREPARATION)
    args = parser.parse_args()
    if args.command == "a4":
        report = run_a4(args.urdf, args.robot_yaml, args.out)
    elif args.command == "c3":
        report = run_c3(args.rig, args.trace, args.out)
    else:
        report = write_preparation(args.out)
    print(json.dumps({"outcome": report.get("outcome", report.get("status")), "output": str(args.out)}))


if __name__ == "__main__":
    main()
