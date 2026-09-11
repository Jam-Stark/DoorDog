#!/usr/bin/env python3
"""U3_F0 three-camera geometry precheck on existing v27 evaluation trajectories.

Read-only planning evidence for base_v28.  It answers, per stage and side, with the
nominal U3_F0 mounts and the SDK-native K of the three physical D435i units:

* is the handle / TCP / finger region inside each RGB and depth frustum (pinhole +
  Min-Z), and is the line of sight blocked by the Piper upper-arm / forearm / wrist
  links (capsule approximation from URDF FK);
* where does the wrist camera actually look (optical axis vs trunk +X, vs world
  horizontal), and how fast does it rotate (world angular speed, axis sweep rate,
  sweep reversals) on the 50 Hz Stage2/3 frames;
* how much does arm_j6 move per stage.

Inputs are the archived v27 q0_dev / Wave A DEV trajectory export (camera_trajectories.csv
in the A2-Rail camera package, derived from source revision 52933a3), the U3_F0.json
layout, and d435_native_sim_parameters.json.  No Isaac process, no rendering, no mesh
occlusion, no door-panel / wall occlusion: an "in frustum" result is a geometric upper
bound of visibility, never a claim of actual RGB / stereo-depth validity.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
from pathlib import Path

import numpy as np

STUDENT_WT = Path("/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103")
CAM_JSON = STUDENT_WT / "camera_setup/Vpiper-Plate-Dual-D435i/config/U3_F0.json"
SDK_JSON = STUDENT_WT / "camera_setup/d435_native_calibration/20260907/d435_native_sim_parameters.json"
TRAJ_CSV = STUDENT_WT / "camera_setup/A2-Rail-Dual-D435i/data/camera_trajectories.csv"

CONTROL_DT = 0.02
DEFAULT_ARM_Q = np.array([0.0, 0.0, 0.0, 0.25, 0.5, 1.57])
REFERENCE_ARM_Q = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.57])
TCP_Z = 0.085
# capsule radii for self-occlusion screening (URDF meshes are not loaded)
LINK_RADIUS = {"upper_arm": 0.05, "forearm": 0.045, "wrist": 0.04}


# ----------------------------------------------------------------------------- math
def rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rpy(r, p, y):
    return rz(y) @ ry(p) @ rx(r)


def tf(R=None, t=None):
    T = np.eye(4)
    if R is not None:
        T[:3, :3] = R
    if t is not None:
        T[:3, 3] = t
    return T


def quat_wxyz_to_R(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def inv(T):
    R = T[:3, :3]
    t = T[:3, 3]
    Ti = np.eye(4)
    Ti[:3, :3] = R.T
    Ti[:3, 3] = -R.T @ t
    return Ti


def rot_angle(R):
    return math.acos(max(-1.0, min(1.0, (np.trace(R) - 1.0) / 2.0)))


# ----------------------------------------------------------------------------- Piper FK (A2_Piper/a2_piper.urdf)
def piper_fk(q):
    """Return joint-origin positions and the flange (arm_body6_to_gripper) transform in trunk frame B."""
    T = tf(None, [0.145, 0.0, 0.154])  # arm_j0 fixed
    T = T @ tf(None, [0.0, 0.0, 0.123]) @ tf(rz(q[0]))  # arm_j1
    shoulder = T[:3, 3].copy()
    T = T @ tf(rpy(1.5708, -0.1359, -3.1416)) @ tf(rz(q[1]))  # arm_j2
    T = T @ tf(rpy(0.0, 0.0, -1.7939), [0.28503, 0.0, 0.0]) @ tf(rz(q[2]))  # arm_j3
    elbow = T[:3, 3].copy()
    T = T @ tf(rpy(1.5708, 0.0, 0.0), [-0.021984, -0.25075, 0.0]) @ tf(rz(q[3]))  # arm_j4
    wrist = T[:3, 3].copy()
    T = T @ tf(rpy(-1.5708, 0.0, 0.0)) @ tf(rz(q[4]))  # arm_j5
    T = T @ tf(rpy(1.5708, 0.0, 0.0), [8.8259e-05, -0.091, 0.0]) @ tf(rz(q[5]))  # arm_j6 -> F
    return {"shoulder": shoulder, "elbow": elbow, "wrist": wrist, "F": T}


# ----------------------------------------------------------------------------- cameras
class Stream:
    def __init__(self, cam, stream, T_parent_opt, K, width, height, min_z):
        self.cam, self.stream = cam, stream
        self.T_parent_opt = T_parent_opt
        self.T_opt_parent = inv(T_parent_opt)
        self.K, self.width, self.height, self.min_z = K, width, height, min_z

    def project(self, p_parent):
        p = self.T_opt_parent[:3, :3] @ p_parent + self.T_opt_parent[:3, 3]
        z = p[2]
        if z <= 1e-6:
            return False, None, None, z
        u = self.K[0, 0] * p[0] / z + self.K[0, 2]
        v = self.K[1, 1] * p[1] / z + self.K[1, 2]
        ok = (z >= self.min_z) and (0.0 <= u < self.width) and (0.0 <= v < self.height)
        return ok, u, v, z

    def axis_parent(self):
        return self.T_parent_opt[:3, 2]

    def origin_parent(self):
        return self.T_parent_opt[:3, 3]


def load_streams():
    cfg = json.load(open(CAM_JSON))
    sdk = json.load(open(SDK_JSON))
    streams = {}
    for cam in cfg["cameras"]:
        name = cam["name"]
        T_parent_depth = np.array(cam["streams"]["depth"]["T_parent_optical"], dtype=float)
        T_depth_rgb = np.array(
            sdk["cameras"][name]["inter_stream_extrinsics"]["rgb__to__depth"]["T_target_source"], dtype=float
        )
        T_parent_rgb = T_parent_depth @ T_depth_rgb
        for stream_name, T_parent in (("rgb", T_parent_rgb), ("depth", T_parent_depth)):
            st = sdk["cameras"][name]["streams"][stream_name]
            K = np.array(st["K"], dtype=float)
            min_z = float(cam["depth_min_z_m"]) if stream_name == "depth" else 0.0
            streams[(name, stream_name)] = Stream(name, stream_name, T_parent, K, st["width"], st["height"], min_z)
        streams[(name, "parent")] = cam["parent"]
    return streams


# ----------------------------------------------------------------------------- occlusion helper
def seg_seg_dist(p0, p1, q0, q1):
    """Minimum distance between segments p0p1 and q0q1."""
    u = p1 - p0
    v = q1 - q0
    w = p0 - q0
    a, b, c, d, e = u @ u, u @ v, v @ v, u @ w, v @ w
    D = a * c - b * b
    sN, sD, tN, tD = 0.0, D, 0.0, D
    if D < 1e-12:
        sN, sD, tN, tD = 0.0, 1.0, e, c
    else:
        sN, tN = b * e - c * d, a * e - b * d
        if sN < 0:
            sN, tN, tD = 0.0, e, c
        elif sN > sD:
            sN, tN, tD = sD, e + b, c
    if tN < 0:
        tN = 0.0
        if -d < 0:
            sN = 0.0
        elif -d > a:
            sN = sD
        else:
            sN, sD = -d, a
    elif tN > tD:
        tN = tD
        if (-d + b) < 0:
            sN = 0.0
        elif (-d + b) > a:
            sN = sD
        else:
            sN, sD = -d + b, a
    sc = 0.0 if abs(sN) < 1e-12 else sN / sD
    tc = 0.0 if abs(tN) < 1e-12 else tN / tD
    return float(np.linalg.norm(w + sc * u - tc * v))


def arm_blocks(cam_origin_B, target_B, fk):
    """True if the camera->target ray passes through an arm-link capsule (shoulder..wrist link)."""
    links = [
        ("upper_arm", fk["shoulder"], fk["elbow"]),
        ("forearm", fk["elbow"], fk["wrist"]),
        ("wrist", fk["wrist"], fk["F"][:3, 3]),
    ]
    # shrink the ray slightly so the target itself (which sits at the gripper) does not count
    d = target_B - cam_origin_B
    end = cam_origin_B + d * (1.0 - 0.06 / max(np.linalg.norm(d), 1e-6))
    for name, a, b in links:
        if seg_seg_dist(cam_origin_B, end, a, b) < LINK_RADIUS[name]:
            return True
    return False


# ----------------------------------------------------------------------------- per-row evaluation
def door_points_D(handle_D_closed_y, side_sign, hinge_rad, W_est):
    """Synthetic door / frame points in the door frame D (origin: panel centre at floor)."""
    pts = {}
    half = W_est / 2.0
    for z in (0.5, 1.0, 1.5, 1.9):
        pts[f"frame_handle_side_z{z}"] = np.array([0.0, side_sign * (half + 0.04), z])
        pts[f"frame_hinge_side_z{z}"] = np.array([0.0, -side_sign * (half + 0.04), z])
    pts["doorway_floor_centre"] = np.array([0.0, 0.0, 0.0])
    pts["floor_1m_beyond"] = np.array([1.0, 0.0, 0.0])
    pts["floor_2m_beyond"] = np.array([2.0, 0.0, 0.0])
    pts["lintel_centre"] = np.array([0.0, 0.0, 2.05])
    hinge = np.array([0.02, -side_sign * half, 0.0])
    panel_dir = rz(-side_sign * hinge_rad) @ np.array([0.0, side_sign * 1.0, 0.0])
    for z in (1.0, 1.8):
        pts[f"panel_free_edge_z{z}"] = hinge + panel_dir * W_est + np.array([0.0, 0.0, z])
        pts[f"panel_mid_z{z}"] = hinge + panel_dir * (W_est / 2.0) + np.array([0.0, 0.0, z])
    return pts


def evaluate_row(row, streams, prev):
    side = row["side"]
    s = 1.0 if side == "left" else -1.0
    stage = int(row["stage"])
    q = np.array([float(row[f"arm_joint_pos_{i}"]) for i in range(6)])
    g = np.array([float(row["gripper_joint_pos_0"]), float(row["gripper_joint_pos_1"])])
    T_D_B = tf(quat_wxyz_to_R([float(row[f"base_quat_D_wxyz_{i}"]) for i in range(4)]),
               [float(row[f"base_pos_D_{i}"]) for i in range(3)])
    T_B_F = tf(quat_wxyz_to_R([float(row[f"flange_quat_B_wxyz_{i}"]) for i in range(4)]),
               [float(row[f"flange_pos_B_{i}"]) for i in range(3)])
    handle_B = np.array([float(row[f"handle_pos_B_{i}"]) for i in range(3)])
    tcp_B = np.array([float(row[f"tcp_pos_B_{i}"]) for i in range(3)])
    handle_D = np.array([float(row[f"handle_pos_D_{i}"]) for i in range(3)])
    hinge = float(row["hinge_rad"])
    fk = piper_fk(q)
    fk_pos_err = float(np.linalg.norm(fk["F"][:3, 3] - T_B_F[:3, 3]))
    fk_rot_err = rot_angle(fk["F"][:3, :3].T @ T_B_F[:3, :3])

    R_B_F, t_B_F = T_B_F[:3, :3], T_B_F[:3, 3]
    # finger proxies: pads on the finger links, opening axis is F y (arm_j7 -> -y, arm_j8 -> +y)
    pts_B = {
        "handle": handle_B,
        "tcp": tcp_B,
        "finger7_pad": t_B_F + R_B_F @ np.array([0.0, -(0.012 + abs(g[0])), 0.165]),
        "finger8_pad": t_B_F + R_B_F @ np.array([0.0, +(0.012 + abs(g[1])), 0.165]),
        "fingertip_centre": t_B_F + R_B_F @ np.array([0.0, 0.0, 0.19]),
    }
    W_est = prev.get("W_est")
    if W_est is None:
        W_est = 2.0 * (abs(handle_D[1]) + 0.115)
        W_est = float(min(max(W_est, 0.8), 1.1))
    T_B_D = inv(T_D_B)
    for k, pD in door_points_D(handle_D[1], s, hinge, W_est).items():
        pts_B[k] = T_B_D[:3, :3] @ pD + T_B_D[:3, 3]

    out = {"W_est": W_est, "fk_pos_err": fk_pos_err, "fk_rot_err_deg": math.degrees(fk_rot_err), "vis": {}, "occ": {}}
    for (cam, stream), st in streams.items():
        if stream == "parent":
            continue
        parent = streams[(cam, "parent")]
        if parent == "trunk":
            T_B_cam = st.T_parent_opt
        else:
            T_B_cam = T_B_F @ st.T_parent_opt
        T_cam_B = inv(T_B_cam)
        cam_origin_B = T_B_cam[:3, 3]
        for name, pB in pts_B.items():
            p = T_cam_B[:3, :3] @ pB + T_cam_B[:3, 3]
            z = p[2]
            if z <= 1e-6:
                ok = False
            else:
                u = st.K[0, 0] * p[0] / z + st.K[0, 2]
                v = st.K[1, 1] * p[1] / z + st.K[1, 2]
                ok = (z >= st.min_z) and (0.0 <= u < st.width) and (0.0 <= v < st.height)
            out["vis"][(cam, stream, name)] = bool(ok)
            if parent == "trunk" and name in ("handle", "tcp", "finger7_pad", "finger8_pad", "fingertip_centre"):
                out["occ"][(cam, stream, name)] = bool(ok and not arm_blocks(cam_origin_B, pB, fk))
        if stream == "rgb":
            axis_B = T_B_cam[:3, :3] @ np.array([0.0, 0.0, 1.0])
            axis_D = T_D_B[:3, :3] @ axis_B
            out[f"{cam}_axis_vs_B_x_deg"] = math.degrees(math.acos(max(-1.0, min(1.0, axis_B[0]))))
            out[f"{cam}_axis_elev_world_deg"] = math.degrees(math.asin(max(-1.0, min(1.0, axis_D[2]))))
            out[f"{cam}_axis_az_world_deg"] = math.degrees(math.atan2(axis_D[1], axis_D[0]))
            out[f"{cam}_R_D_cam"] = T_D_B[:3, :3] @ T_B_cam[:3, :3]
    out["R_D_B"] = T_D_B[:3, :3]
    out["q6"] = q[5]
    out["q"] = q
    out["stage"] = stage
    return out


# ----------------------------------------------------------------------------- aggregation
def pct(vals):
    vals = np.asarray(vals, dtype=float)
    if vals.size == 0:
        return None
    return {
        "n": int(vals.size),
        "p5": float(np.percentile(vals, 5)),
        "p50": float(np.percentile(vals, 50)),
        "p95": float(np.percentile(vals, 95)),
        "max": float(vals.max()),
    }


def wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


def run(cells, out_dir):
    streams = load_streams()
    rows_by_lane = collections.defaultdict(list)
    with open(TRAJ_CSV) as f:
        for row in csv.DictReader(f):
            if row["cell"] in cells:
                rows_by_lane[(row["cell"], row["side"])].append(row)

    report = {"cells": cells, "source_csv": str(TRAJ_CSV), "lanes": {}}
    fk_pos_errs, fk_rot_errs = [], []
    for (cell, side), rows in sorted(rows_by_lane.items()):
        rows.sort(key=lambda r: (int(r["env_id"]), int(r["step_index"])))
        per_stage = collections.defaultdict(lambda: collections.defaultdict(list))
        motion = collections.defaultdict(lambda: collections.defaultdict(list))
        prev_state = {}
        prev_key = None
        prev_eval = None
        for row in rows:
            env = int(row["env_id"])
            step = int(row["step_index"])
            key = (env,)
            if key != prev_key:
                prev_state = {}
                prev_eval = None
                prev_step = None
            ev = evaluate_row(row, streams, prev_state)
            prev_state["W_est"] = ev["W_est"]
            fk_pos_errs.append(ev["fk_pos_err"])
            fk_rot_errs.append(ev["fk_rot_err_deg"])
            st = ev["stage"]
            for k, ok in ev["vis"].items():
                per_stage[st][("vis",) + k].append(1.0 if ok else 0.0)
            for k, ok in ev["occ"].items():
                per_stage[st][("occ",) + k].append(1.0 if ok else 0.0)
            for cam in ("base_left", "base_right", "wrist"):
                per_stage[st][("axis_vs_B_x", cam)].append(ev[f"{cam}_axis_vs_B_x_deg"])
                per_stage[st][("axis_elev_world", cam)].append(ev[f"{cam}_axis_elev_world_deg"])
            per_stage[st][("q6",)].append(ev["q6"])
            per_stage[st][("q6_dev_from_default",)].append(abs(ev["q6"] - 1.57))
            dense = row["sample_reason"].startswith("dense_50hz")
            if prev_eval is not None and dense and prev_dense and step == prev_step + 1 and prev_eval["stage"] == st:
                for cam in ("wrist", "base_left"):
                    dR = prev_eval[f"{cam}_R_D_cam"].T @ ev[f"{cam}_R_D_cam"]
                    motion[st][f"{cam}_ang_speed_deg_s"].append(math.degrees(rot_angle(dR)) / CONTROL_DT)
                    a0 = prev_eval[f"{cam}_R_D_cam"][:, 2]
                    a1 = ev[f"{cam}_R_D_cam"][:, 2]
                    sweep = math.degrees(math.acos(max(-1.0, min(1.0, float(a0 @ a1))))) / CONTROL_DT
                    motion[st][f"{cam}_axis_sweep_deg_s"].append(sweep)
                    az_rate = wrap_deg(ev[f"{cam}_axis_az_world_deg"] - prev_eval[f"{cam}_axis_az_world_deg"]) / CONTROL_DT
                    el_rate = (ev[f"{cam}_axis_elev_world_deg"] - prev_eval[f"{cam}_axis_elev_world_deg"]) / CONTROL_DT
                    motion[st][f"{cam}_az_rate"].append(az_rate)
                    motion[st][f"{cam}_el_rate"].append(el_rate)
                    motion[st][f"{cam}_env"].append(env)
                dq = (ev["q"] - prev_eval["q"]) / CONTROL_DT
                motion[st]["dq6_abs"].append(abs(dq[5]))
                motion[st]["dq_arm_max_abs"].append(float(np.abs(dq).max()))
            prev_eval = ev
            prev_key = key
            prev_step = step
            prev_dense = dense

        lane = {}
        for st in sorted(per_stage):
            d = per_stage[st]
            entry = {"frames": len(d[("q6",)])}
            vis = {}
            for k, v in d.items():
                if k[0] == "vis":
                    vis[f"{k[1]}/{k[2]}/{k[3]}"] = float(np.mean(v))
                elif k[0] == "occ":
                    vis[f"{k[1]}/{k[2]}/{k[3]}/arm_clear"] = float(np.mean(v))
            entry["in_frustum_share"] = vis
            entry["axis_vs_B_x_deg"] = {cam: pct(d[("axis_vs_B_x", cam)]) for cam in ("base_left", "base_right", "wrist")}
            entry["axis_elev_world_deg"] = {cam: pct(d[("axis_elev_world", cam)]) for cam in ("base_left", "base_right", "wrist")}
            entry["q6_rad"] = pct(d[("q6",)])
            entry["q6_abs_dev_from_1p57"] = pct(d[("q6_dev_from_default",)])
            entry["q6_share_dev_gt_0p3"] = float(np.mean(np.asarray(d[("q6_dev_from_default",)]) > 0.3))
            m = motion.get(st)
            if m and m.get("wrist_ang_speed_deg_s"):
                mm = {}
                for cam in ("wrist", "base_left"):
                    mm[f"{cam}_ang_speed_deg_s"] = pct(m[f"{cam}_ang_speed_deg_s"])
                    mm[f"{cam}_axis_sweep_deg_s"] = pct(m[f"{cam}_axis_sweep_deg_s"])
                    # reversal count: sign flips of azimuth sweep rate above 15 deg/s within an env, per second of dense data
                    az = np.asarray(m[f"{cam}_az_rate"])
                    envs = np.asarray(m[f"{cam}_env"])
                    flips = 0
                    for e in np.unique(envs):
                        r = az[envs == e]
                        r = r[np.abs(r) > 15.0]
                        if r.size > 1:
                            flips += int(np.sum(np.sign(r[1:]) != np.sign(r[:-1])))
                    mm[f"{cam}_az_reversals_per_s"] = flips / (len(az) * CONTROL_DT)
                    mm[f"{cam}_share_axis_sweep_gt_60"] = float(np.mean(np.asarray(m[f"{cam}_axis_sweep_deg_s"]) > 60.0))
                mm["dq6_abs_rad_s"] = pct(m["dq6_abs"])
                mm["dq_arm_max_abs_rad_s"] = pct(m["dq_arm_max_abs"])
                mm["dense_pairs"] = len(m["dq6_abs"])
                entry["motion_dense50hz"] = mm
            lane[f"stage{st}"] = entry
        report["lanes"][f"{cell}/{side}"] = lane

    report["fk_check_vs_csv_flange"] = {"pos_err_m": pct(fk_pos_errs), "rot_err_deg": pct(fk_rot_errs)}
    report["static_poses"] = static_pose_report(streams)
    report["synthetic_approach"] = synthetic_approach(streams)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "u3f0_geometry_precheck.json").write_text(json.dumps(report, indent=1))
    write_markdown(report, out_dir / "u3f0_geometry_precheck.md")
    return report


def static_pose_report(streams):
    out = {}
    for label, q in (("training_default_[0,0,0,0.25,0.5,1.57]", DEFAULT_ARM_Q), ("u3_reference_[0,0,0,0,0,1.57]", REFERENCE_ARM_Q)):
        fk = piper_fk(q)
        T_B_cam = fk["F"] @ streams[("wrist", "rgb")].T_parent_opt
        axis = T_B_cam[:3, :3] @ np.array([0.0, 0.0, 1.0])
        flange_axis = fk["F"][:3, :3] @ np.array([0.0, 0.0, 1.0])
        tcp = fk["F"][:3, 3] + fk["F"][:3, :3] @ np.array([0.0, 0.0, TCP_Z])
        out[label] = {
            "flange_pos_B": fk["F"][:3, 3].round(4).tolist(),
            "flange_z_axis_B": flange_axis.round(4).tolist(),
            "flange_axis_pitch_deg": round(math.degrees(math.asin(flange_axis[2])), 2),
            "wrist_rgb_origin_B": T_B_cam[:3, 3].round(4).tolist(),
            "wrist_rgb_axis_B": axis.round(4).tolist(),
            "wrist_rgb_axis_pitch_deg": round(math.degrees(math.asin(axis[2])), 2),
            "wrist_rgb_axis_yaw_deg": round(math.degrees(math.atan2(axis[1], axis[0])), 2),
            "tcp_B": tcp.round(4).tolist(),
            "tcp_in_wrist_rgb": bool(streams[("wrist", "rgb")].project(np.array([0.0, 0.0, TCP_Z]))[0]),
            "tcp_in_wrist_depth": bool(streams[("wrist", "depth")].project(np.array([0.0, 0.0, TCP_Z]))[0]),
        }
        # distance along the flange axis at which an on-axis point enters the wrist RGB / depth
        for stream in ("rgb", "depth"):
            st = streams[("wrist", stream)]
            d_enter = None
            for d in np.arange(0.05, 1.5, 0.005):
                if st.project(np.array([0.0, 0.0, d]))[0]:
                    d_enter = float(round(d, 3))
                    break
            out[label][f"on_axis_point_enters_wrist_{stream}_at_m"] = d_enter
    return out


def synthetic_approach(streams):
    """Stage0/1 have no exported frames: sweep trunk poses in front of a nominal door (W 0.95, H 2.05,
    handle 0.90 m) with the arm at the training default pose; report base/wrist frustum membership."""
    results = []
    handle_D = np.array([-0.1, 0.35, 0.90])  # LEFT handle grasp target: x=-axle/2, y=W/2-e-L/2
    frame_pts = {
        "handle": handle_D,
        "frame_handle_side_z1.0": np.array([0.0, 0.515, 1.0]),
        "frame_hinge_side_z1.0": np.array([0.0, -0.515, 1.0]),
        "lintel_centre": np.array([0.0, 0.0, 2.05]),
        "doorway_floor_centre": np.array([0.0, 0.0, 0.0]),
        "panel_mid_z1.0": np.array([0.0, 0.0, 1.0]),
    }
    fk = piper_fk(DEFAULT_ARM_Q)
    for dist in (1.5, 1.2, 1.0, 0.8, 0.7):
        for lateral in (-0.15, 0.0, 0.15):
            for yaw_deg in (-17.0, 0.0, 17.0):
                trunk_D = np.array([-dist, handle_D[1] + lateral, 0.48])
                T_D_B = tf(rz(math.radians(yaw_deg)), trunk_D)
                T_B_D = inv(T_D_B)
                rec = {"dist": dist, "lateral_vs_handle": lateral, "yaw_deg": yaw_deg, "vis": {}}
                for (cam, stream), st in streams.items():
                    if stream == "parent":
                        continue
                    T_B_cam = st.T_parent_opt if streams[(cam, "parent")] == "trunk" else fk["F"] @ st.T_parent_opt
                    T_cam_B = inv(T_B_cam)
                    for name, pD in frame_pts.items():
                        pB = T_B_D[:3, :3] @ pD + T_B_D[:3, 3]
                        p = T_cam_B[:3, :3] @ pB + T_cam_B[:3, 3]
                        ok = False
                        if p[2] > 1e-6:
                            u = st.K[0, 0] * p[0] / p[2] + st.K[0, 2]
                            v = st.K[1, 1] * p[1] / p[2] + st.K[1, 2]
                            ok = (p[2] >= st.min_z) and (0 <= u < st.width) and (0 <= v < st.height)
                        rec["vis"][f"{cam}/{stream}/{name}"] = bool(ok)
                results.append(rec)
    # summarise: share over the 45 poses per distance
    summary = collections.defaultdict(lambda: collections.defaultdict(list))
    for rec in results:
        for k, ok in rec["vis"].items():
            summary[rec["dist"]][k].append(1.0 if ok else 0.0)
    return {str(d): {k: float(np.mean(v)) for k, v in sorted(kv.items())} for d, kv in sorted(summary.items())}


def write_markdown(report, path):
    lines = ["# U3_F0 geometry precheck (pinhole + Min-Z + arm-capsule screen; not rendered)", ""]
    fkc = report["fk_check_vs_csv_flange"]
    lines.append(f"FK check vs exported flange pose: pos err p50/p95/max = {fkc['pos_err_m']['p50']:.4f}/{fkc['pos_err_m']['p95']:.4f}/{fkc['pos_err_m']['max']:.4f} m; "
                 f"rot err p50/p95/max = {fkc['rot_err_deg']['p50']:.2f}/{fkc['rot_err_deg']['p95']:.2f}/{fkc['rot_err_deg']['max']:.2f} deg")
    lines.append("")
    lines.append("## Static arm poses (wrist camera pointing)")
    for label, d in report["static_poses"].items():
        lines.append(f"- {label}: flange axis pitch {d['flange_axis_pitch_deg']}°, wrist RGB axis pitch {d['wrist_rgb_axis_pitch_deg']}° yaw {d['wrist_rgb_axis_yaw_deg']}°, "
                     f"TCP in wrist RGB={d['tcp_in_wrist_rgb']} depth={d['tcp_in_wrist_depth']}, on-axis point enters wrist RGB at {d['on_axis_point_enters_wrist_rgb_at_m']} m, depth at {d['on_axis_point_enters_wrist_depth_at_m']} m")
    lines.append("")
    keys = [
        ("base_left/rgb/handle", "L-RGB handle"), ("base_left/rgb/handle/arm_clear", "L-RGB handle clear"),
        ("base_right/rgb/handle", "R-RGB handle"), ("base_right/rgb/handle/arm_clear", "R-RGB handle clear"),
        ("base_left/depth/handle", "L-D handle"), ("base_right/depth/handle", "R-D handle"),
        ("wrist/rgb/handle", "W-RGB handle"), ("wrist/depth/handle", "W-D handle"),
        ("base_left/rgb/tcp/arm_clear", "L-RGB tcp clear"), ("base_right/rgb/tcp/arm_clear", "R-RGB tcp clear"),
        ("base_left/rgb/finger7_pad/arm_clear", "L-RGB f7 clear"), ("base_right/rgb/finger7_pad/arm_clear", "R-RGB f7 clear"),
        ("base_left/rgb/finger8_pad/arm_clear", "L-RGB f8 clear"), ("base_right/rgb/finger8_pad/arm_clear", "R-RGB f8 clear"),
        ("wrist/rgb/fingertip_centre", "W-RGB fingertip"), ("wrist/depth/fingertip_centre", "W-D fingertip"),
        ("wrist/rgb/panel_mid_z1.0", "W-RGB panel"), ("base_left/rgb/panel_free_edge_z1.0", "L-RGB free edge"), ("base_right/rgb/panel_free_edge_z1.0", "R-RGB free edge"),
        ("base_left/rgb/frame_handle_side_z1.0", "L-RGB frame(handle side)"), ("base_right/rgb/frame_handle_side_z1.0", "R-RGB frame(handle side)"),
        ("base_left/rgb/frame_hinge_side_z1.0", "L-RGB frame(hinge side)"), ("base_right/rgb/frame_hinge_side_z1.0", "R-RGB frame(hinge side)"),
        ("base_left/rgb/floor_1m_beyond", "L-RGB floor+1m"), ("base_right/rgb/floor_1m_beyond", "R-RGB floor+1m"), ("base_right/depth/floor_1m_beyond", "R-D floor+1m"),
        ("wrist/rgb/floor_1m_beyond", "W-RGB floor+1m"),
    ]
    for lane, stages in report["lanes"].items():
        lines.append(f"## {lane}")
        lines.append("| stage | frames | " + " | ".join(k[1] for k in keys) + " |")
        lines.append("|---|---:|" + "|".join("---:" for _ in keys) + "|")
        for st, e in stages.items():
            vals = []
            for k, _ in keys:
                v = e["in_frustum_share"].get(k)
                vals.append("-" if v is None else f"{100*v:.0f}%")
            lines.append(f"| {st} | {e['frames']} | " + " | ".join(vals) + " |")
        lines.append("")
        lines.append("| stage | wrist axis vs B+X p50/p95 (deg) | wrist axis world elev p5/p50/p95 | q6 p5/p50/p95 (rad) | q6 dev>0.3 share | wrist ang speed p50/p95 (deg/s) | wrist axis sweep p50/p95 | share sweep>60 | az reversals/s | trunk-cam ang speed p50/p95 | dq6 p50/p95 (rad/s) | dq_arm max p95 |")
        lines.append("|---|---|---|---|---:|---|---|---:|---:|---|---|---|")
        for st, e in stages.items():
            a = e["axis_vs_B_x_deg"]["wrist"]
            el = e["axis_elev_world_deg"]["wrist"]
            q6 = e["q6_rad"]
            m = e.get("motion_dense50hz")
            if m:
                ws, sw, bs, dq = m["wrist_ang_speed_deg_s"], m["wrist_axis_sweep_deg_s"], m["base_left_ang_speed_deg_s"], m["dq6_abs_rad_s"]
                mcol = f"{ws['p50']:.0f}/{ws['p95']:.0f} | {sw['p50']:.0f}/{sw['p95']:.0f} | {100*m['wrist_share_axis_sweep_gt_60']:.0f}% | {m['wrist_az_reversals_per_s']:.2f} | {bs['p50']:.0f}/{bs['p95']:.0f} | {dq['p50']:.2f}/{dq['p95']:.2f} | {m['dq_arm_max_abs_rad_s']['p95']:.2f}"
            else:
                mcol = "n/a (sampled 10 Hz) | | | | | | "
            lines.append(f"| {st} | {a['p50']:.0f}/{a['p95']:.0f} | {el['p5']:.0f}/{el['p50']:.0f}/{el['p95']:.0f} | {q6['p5']:.2f}/{q6['p50']:.2f}/{q6['p95']:.2f} | {100*e['q6_share_dev_gt_0p3']:.0f}% | {mcol} |")
        lines.append("")
    lines.append("## Synthetic Stage0/1 approach (trunk z 0.48, arm default pose, nominal LEFT door W 0.95 / handle 0.90; share over 3 lateral x 3 yaw poses)")
    sa = report["synthetic_approach"]
    skeys = sorted(next(iter(sa.values())).keys())
    lines.append("| dist (m) | " + " | ".join(skeys) + " |")
    lines.append("|---|" + "|".join("---:" for _ in skeys) + "|")
    for d, kv in sa.items():
        lines.append(f"| {d} | " + " | ".join(f"{100*kv[k]:.0f}%" for k in skeys) + " |")
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="+", default=["C_S2", "C_S21"])
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "precheck_outputs"))
    args = ap.parse_args()
    rep = run(args.cells, Path(args.out))
    print(json.dumps(rep["fk_check_vs_csv_flange"], indent=1))
    print(json.dumps(rep["static_poses"], indent=1))
