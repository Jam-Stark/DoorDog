#!/usr/bin/env python3
"""W3: coverage of alternative v28 camera layouts.

Re-uses scriptsFORhuman/v28/v28_u3f0_geometry_precheck.py (pinhole + Min-Z frustum test,
Piper FK, arm-capsule self-occlusion screen, door-point construction in the door frame D)
and the mount JSONs in planner_evidence_20260909/camera/variants/.  Nothing in any git
worktree is modified; all outputs go to /tmp/v28_team2/camera/out/.

Two independent evaluations:
  (a) replay of the archived v27 trajectories (cells C_S2, C_S21, both door sides)  -- depends
      on how the OLD Teacher moved;
  (b) a trajectory-independent canonical posture set derived from task geometry only.
"""
from __future__ import annotations
import collections, csv, importlib.util, json, math, sys, time
from pathlib import Path
import numpy as np

REPO = Path("/home/baoquanc/workspace/DoorDog-A2_Piper")
PC_SRC = REPO / "scriptsFORhuman/v28/v28_u3f0_geometry_precheck.py"
VARIANTS = REPO / "scriptsFORhuman/v28/planner_evidence_20260909/camera/variants"
STUDENT = Path("/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103")
SDK_JSON = STUDENT / "camera_setup/d435_native_calibration/20260907/d435_native_sim_parameters.json"
TRAJ_CSV = STUDENT / "camera_setup/A2-Rail-Dual-D435i/data/camera_trajectories.csv"
OUT = Path("/tmp/v28_team2/camera/out")

spec = importlib.util.spec_from_file_location("pc", PC_SRC)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

SDK = json.loads(SDK_JSON.read_text())
B15 = json.loads((VARIANTS / "U3_F45_B15.json").read_text())
CAMS_B15 = {c["name"]: c for c in B15["cameras"]}

# v28 reset posture, plan §3.1 / D-03a
ARM_V28 = np.array([0.0, 0.10, -0.10, 0.0, -0.52, 1.57])


class Stream(pc.Stream):
    pass


def stream_pair(name_for_K, T_parent_rgb, T_parent_depth, min_z):
    """Build (rgb, depth) Stream objects with the measured SDK intrinsics of one D435i."""
    out = {}
    for s, T in (("rgb", T_parent_rgb), ("depth", T_parent_depth)):
        st = SDK["cameras"][name_for_K]["streams"][s]
        out[s] = Stream(name_for_K, s, T, np.array(st["K"], float), st["width"], st["height"],
                        min_z if s == "depth" else 0.0)
    return out


def T_opt_from_json(cam, stream):
    return np.array(cam["streams"][stream]["T_parent_optical"], float)


def _T_M_optical(cam):
    TM = np.array(cam["T_parent_M"], float)
    return {s: pc.inv(TM) @ T_opt_from_json(cam, s) for s in ("rgb", "depth")}


BASE_M_OPT = _T_M_optical(CAMS_B15["base_left"])
WRIST_M_OPT = _T_M_optical(CAMS_B15["wrist"])
WRIST_RPY0 = CAMS_B15["wrist"]["rpy_deg"]          # [-0.0008, -40.0036, -89.9536] at theta=45
WRIST_XYZ0 = CAMS_B15["wrist"]["xyz_m"]            # [-0.000143, 0.179316, 0.015677]


def base_cam(y, pitch_up_deg, x=0.025, z=0.19, kname="base_left"):
    TM = pc.tf(pc.ry(math.radians(-pitch_up_deg)), [x, y, z])
    return stream_pair(kname, TM @ BASE_M_OPT["rgb"], TM @ BASE_M_OPT["depth"],
                       float(CAMS_B15["base_left"]["depth_min_z_m"]))


def wrist_cam(theta_deg, height_m):
    r, p, yw = WRIST_RPY0
    p = -85.0036 + theta_deg
    # the tower axis is B +Z at the reference posture, not F +Y: build_u3_forward.make_variant
    # asserts R_B_F @ xyz_F == [0, 0, 0.180], so a tower of height h has xyz_F = xyz_F0 * h/0.180
    xyz = [c * height_m / 0.180 for c in WRIST_XYZ0]
    TM = pc.tf(pc.rpy(math.radians(r), math.radians(p), math.radians(yw)), xyz)
    return stream_pair("wrist", TM @ WRIST_M_OPT["rgb"], TM @ WRIST_M_OPT["depth"],
                       float(CAMS_B15["wrist"]["depth_min_z_m"]))


def head_cam_d435i(pitch_up_deg=0.0):
    """A D435i placed at the frozen Student's head-RGB mount point
    (DepthADD_v3_Standard_Student_Export_Spec_20260825.yaml:120, trunk-local), looking forward."""
    p = math.radians(pitch_up_deg)
    f = np.array([math.cos(p), 0.0, math.sin(p)])
    r = np.array([0.0, -1.0, 0.0])
    d = np.cross(f, r)
    R = np.stack([r, d, f], axis=1)
    TM = pc.tf(R, [0.3381, 0.0336, 0.0525])
    # the D435i rig offsets are expressed in the mount frame M, not the optical frame; place the
    # optical centres directly (the 8-33 mm intra-rig offsets are immaterial at door distances)
    return stream_pair("base_left", TM, TM, float(CAMS_B15["base_left"]["depth_min_z_m"]))


def head_cam_student_rgb(pitch_up_deg=0.0):
    """The frozen Student's actual head RGB stream: 384x136, aperture_hv [4.4921, 1.5909],
    focal_length 1.0 (same spec line) -> 132.0 deg x 77.6 deg."""
    p = math.radians(pitch_up_deg)
    f = np.array([math.cos(p), 0.0, math.sin(p)])
    r = np.array([0.0, -1.0, 0.0])
    d = np.cross(f, r)
    R = np.stack([r, d, f], axis=1)
    TM = pc.tf(R, [0.3381, 0.0336, 0.0525])
    W, H = 384, 136
    fx = (W / 2) / (4.4920735478 / 2.0)
    fy = (H / 2) / (1.5909427148 / 2.0)
    K = np.array([[fx, 0, W / 2], [0, fy, H / 2], [0, 0, 1]], float)
    return {"rgb": Stream("head", "rgb", TM, K, W, H, 0.0)}


# ---------------------------------------------------------------- camera / layout registry
CAMERAS = {
    "base_left_B15": ("trunk", base_cam(+0.155, 15.0, kname="base_left")),
    "base_right_B15": ("trunk", base_cam(-0.155, 15.0, kname="base_right")),
    "base_centre_B15": ("trunk", base_cam(0.0, 15.0)),
    "base_centre_B0": ("trunk", base_cam(0.0, 0.0)),
    "head_d435i_B0": ("trunk", head_cam_d435i(0.0)),
    "head_d435i_B15": ("trunk", head_cam_d435i(15.0)),
    "head_student_rgb": ("trunk", head_cam_student_rgb(0.0)),
    "wrist_F45_180": ("flange", wrist_cam(45.0, 0.180)),
    "wrist_F39_140": ("flange", wrist_cam(38.76, 0.140)),
    "wrist_F345_120": ("flange", wrist_cam(34.49, 0.120)),
}

LAYOUTS = {
    "V0_dual_B15_W45_180": ["base_left_B15", "base_right_B15", "wrist_F45_180"],
    "V1a_centre_B15_W45_180": ["base_centre_B15", "wrist_F45_180"],
    "V1b_centre_B0_W45_180": ["base_centre_B0", "wrist_F45_180"],
    "V2_head_d435i_B0_W45_180": ["head_d435i_B0", "wrist_F45_180"],
    "V2b_head_d435i_B15_W45_180": ["head_d435i_B15", "wrist_F45_180"],
    "V2c_head_studentRGB_W45_180": ["head_student_rgb", "wrist_F45_180"],
    "V3_wrist_only_W45_180": ["wrist_F45_180"],
    "V4a_centre_B15_W39_140": ["base_centre_B15", "wrist_F39_140"],
    "V4b_centre_B15_W345_120": ["base_centre_B15", "wrist_F345_120"],
}

TARGETS = ["handle", "tcp", "finger7_pad", "finger8_pad", "fingertip_centre",
           "frame_handle_side_z1.0", "frame_hinge_side_z1.0", "doorway_floor_centre",
           "floor_1m_beyond", "lintel_centre", "panel_free_edge_z1.0", "panel_mid_z1.0"]
ARM_SCREEN = {"handle", "tcp", "finger7_pad", "finger8_pad", "fingertip_centre"}


def eval_pose(pts_B, fk, want_arm_screen=True):
    """Return {(cam, stream, target): bool} for every registered camera."""
    out = {}
    for cname, (parent, streams) in CAMERAS.items():
        for sname, st in streams.items():
            T_B_cam = st.T_parent_opt if parent == "trunk" else fk["F"] @ st.T_parent_opt
            T_cam_B = pc.inv(T_B_cam)
            org = T_B_cam[:3, 3]
            for tname, pB in pts_B.items():
                p = T_cam_B[:3, :3] @ pB + T_cam_B[:3, 3]
                z = p[2]
                ok = False
                if z > 1e-6:
                    u = st.K[0, 0] * p[0] / z + st.K[0, 2]
                    v = st.K[1, 1] * p[1] / z + st.K[1, 2]
                    ok = (z >= st.min_z) and (0.0 <= u < st.width) and (0.0 <= v < st.height)
                if ok and want_arm_screen and parent == "trunk" and tname in ARM_SCREEN:
                    ok = not pc.arm_blocks(org, pB, fk)
                out[(cname, sname, tname)] = bool(ok)
    return out


# ---------------------------------------------------------------- (a) v27 trajectory replay
def replay(cells=("C_S2", "C_S21")):
    rows_by_lane = collections.defaultdict(list)
    with open(TRAJ_CSV) as f:
        for row in csv.DictReader(f):
            if row["cell"] in cells:
                rows_by_lane[(row["cell"], row["side"])].append(row)
    res = {}
    for (cell, side), rows in sorted(rows_by_lane.items()):
        rows.sort(key=lambda r: (int(r["env_id"]), int(r["step_index"])))
        acc = collections.defaultdict(lambda: collections.defaultdict(list))
        W_prev = {}
        for row in rows:
            s = 1.0 if side == "left" else -1.0
            stage = int(row["stage"])
            q = np.array([float(row[f"arm_joint_pos_{i}"]) for i in range(6)])
            g = np.array([float(row["gripper_joint_pos_0"]), float(row["gripper_joint_pos_1"])])
            T_D_B = pc.tf(pc.quat_wxyz_to_R([float(row[f"base_quat_D_wxyz_{i}"]) for i in range(4)]),
                          [float(row[f"base_pos_D_{i}"]) for i in range(3)])
            T_B_F = pc.tf(pc.quat_wxyz_to_R([float(row[f"flange_quat_B_wxyz_{i}"]) for i in range(4)]),
                          [float(row[f"flange_pos_B_{i}"]) for i in range(3)])
            handle_B = np.array([float(row[f"handle_pos_B_{i}"]) for i in range(3)])
            tcp_B = np.array([float(row[f"tcp_pos_B_{i}"]) for i in range(3)])
            handle_D = np.array([float(row[f"handle_pos_D_{i}"]) for i in range(3)])
            hinge = float(row["hinge_rad"])
            fk = pc.piper_fk(q)
            fk["F"] = T_B_F      # use the exported flange pose (FK check p50 5e-8 m, REPORT.md:47)
            R_B_F, t_B_F = T_B_F[:3, :3], T_B_F[:3, 3]
            pts = {"handle": handle_B, "tcp": tcp_B,
                   "finger7_pad": t_B_F + R_B_F @ np.array([0.0, -(0.012 + abs(g[0])), 0.165]),
                   "finger8_pad": t_B_F + R_B_F @ np.array([0.0, +(0.012 + abs(g[1])), 0.165]),
                   "fingertip_centre": t_B_F + R_B_F @ np.array([0.0, 0.0, 0.19])}
            env = int(row["env_id"])
            if env not in W_prev:
                W_prev[env] = float(min(max(2.0 * (abs(handle_D[1]) + 0.115), 0.8), 1.1))
            T_B_D = pc.inv(T_D_B)
            for k, pD in pc.door_points_D(handle_D[1], s, hinge, W_prev[env]).items():
                if k in TARGETS:
                    pts[k] = T_B_D[:3, :3] @ pD + T_B_D[:3, 3]
            vis = add_unions(eval_pose(pts, fk))
            for k, ok in vis.items():
                acc[stage][k].append(1.0 if ok else 0.0)
        res[f"{cell}/{side}"] = {f"stage{st}": {"frames": len(next(iter(d.values()))),
                                                "share": {f"{k[0]}/{k[1]}/{k[2]}": float(np.mean(v)) for k, v in d.items()}}
                                 for st, d in sorted(acc.items())}
        print("replay done", cell, side, flush=True)
    return res


# ---------------------------------------------------------------- (b) canonical posture set
W_NOM, H_NOM = 0.957, 1.9           # fitted W p50 (REPORT.md:75); door.py nominal lowest lintel
HANDLE_Z, EDGE_OFF, LEVER_L = 0.90, 0.115, 0.125
AXLE = 0.195


def door_pts(side_sign, hinge_rad, W=W_NOM, handle_z=HANDLE_Z):
    half = W / 2
    hy = side_sign * (half - EDGE_OFF - LEVER_L / 2)
    pts = pc.door_points_D(hy, side_sign, hinge_rad, W)
    keep = {k: v for k, v in pts.items() if k in TARGETS}
    # grasp target (handle centre) on the swung panel
    hinge = np.array([0.02, -side_sign * half, 0.0])
    R = pc.rz(-side_sign * hinge_rad)
    keep["handle"] = hinge + R @ (np.array([-AXLE / 2, hy, handle_z]) - hinge)
    return keep


def canonical_approach(side_sign=1.0):
    """Stage0/1 approach family: distance x lateral x yaw, arm at the v28 reset posture."""
    fk = pc.piper_fk(ARM_V28)
    rows = []
    dpts = door_pts(side_sign, 0.0)
    for dist in (1.5, 1.2, 1.0, 0.8):
        for lateral in (-0.15, 0.0, 0.15):
            for yaw in (-17.0, 0.0, 17.0):
                trunk_D = np.array([-dist, dpts["handle"][1] + lateral, 0.48])
                T_D_B = pc.tf(pc.rz(math.radians(yaw)), trunk_D)
                T_B_D = pc.inv(T_D_B)
                pts = {k: T_B_D[:3, :3] @ v + T_B_D[:3, 3] for k, v in dpts.items()}
                pts["tcp"] = fk["F"][:3, 3] + fk["F"][:3, :3] @ np.array([0, 0, pc.TCP_Z])
                rows.append((dist, eval_pose(pts, fk)))
    return rows


def sample_grasp_postures(side_sign=1.0, n=200000, seed=0):
    """IK-free grasp-posture family: sample arm joints inside the PiPER limits, keep the ones
    whose TCP sits at handle height, just in front of the panel, with the flange approach axis
    roughly horizontal and the tower pointing up."""
    rng = np.random.default_rng(seed)
    lo = np.array([-2.618, 0.0, -2.967, -1.745, -1.22, -2.0944])
    hi = np.array([2.618, 3.14, 0.0, 1.745, 1.22, 2.0944])
    Q = rng.uniform(lo, hi, size=(n, 6))
    keep = []
    for q in Q:
        fk = pc.piper_fk(q)
        F = fk["F"]
        tcp_B = F[:3, 3] + F[:3, :3] @ np.array([0, 0, pc.TCP_Z])
        # trunk z 0.48 in world; handle 0.85-0.95 world -> 0.37..0.47 in B
        if not (0.37 <= tcp_B[2] <= 0.47):
            continue
        if not (0.25 <= tcp_B[0] <= 0.60):
            continue
        if abs(tcp_B[1]) > 0.25:
            continue
        ax = F[:3, :3] @ np.array([0, 0, 1.0])          # flange approach axis
        if abs(math.degrees(math.asin(max(-1, min(1, ax[2]))))) > 20.0:
            continue
        tower = F[:3, :3] @ np.array([0, 1.0, 0])        # tower direction (F+Y)
        if tower[2] < math.cos(math.radians(50)):
            continue
        keep.append((q, fk, tcp_B))
        if len(keep) >= 400:
            break
    return keep


def canonical_grasp(side_sign=1.0):
    """Place each sampled grasp posture so that the TCP coincides with the handle, for
    hinge angles 0 (grasp) and 0.5 rad (pull/push), and score the camera set."""
    postures = sample_grasp_postures(side_sign)
    rows = []
    for hinge_rad in (0.0, 0.5):
        for q, fk, tcp_B in postures:
            # place the door handle exactly at this posture's TCP height (inside the trained
            # a2_v26_door_handle_height_range [0.85, 0.95] by construction of the filter)
            dpts = door_pts(side_sign, hinge_rad, handle_z=0.48 + tcp_B[2])
            for yaw in (-10.0, 0.0, 10.0):
                R_D_B = pc.rz(math.radians(yaw))
                # trunk position so the TCP lands on the handle
                trunk_D = dpts["handle"] - R_D_B @ tcp_B
                trunk_D[2] = 0.48
                T_D_B = pc.tf(R_D_B, trunk_D)
                T_B_D = pc.inv(T_D_B)
                pts = {k: T_B_D[:3, :3] @ v + T_B_D[:3, 3] for k, v in dpts.items()}
                pts["tcp"] = tcp_B
                F = fk["F"]
                pts["finger7_pad"] = F[:3, 3] + F[:3, :3] @ np.array([0.0, -0.025, 0.165])
                pts["finger8_pad"] = F[:3, 3] + F[:3, :3] @ np.array([0.0, +0.025, 0.165])
                pts["fingertip_centre"] = F[:3, 3] + F[:3, :3] @ np.array([0.0, 0.0, 0.19])
                rows.append((hinge_rad, eval_pose(pts, fk)))
    return rows, len(postures)


def canonical_passage(side_sign=1.0):
    """Robot centred in the doorway, arm at the v28 reset posture, door at 60 deg / 90 deg."""
    fk = pc.piper_fk(ARM_V28)
    rows = []
    for hinge_rad in (1.0472, 1.5708):
        dpts = door_pts(side_sign, hinge_rad)
        for x in (-0.4, 0.0, 0.4):
            for yaw in (-20.0, 0.0, 20.0):
                T_D_B = pc.tf(pc.rz(math.radians(yaw)), np.array([x, 0.0, 0.48]))
                T_B_D = pc.inv(T_D_B)
                pts = {k: T_B_D[:3, :3] @ v + T_B_D[:3, 3] for k, v in dpts.items()}
                pts["tcp"] = fk["F"][:3, 3] + fk["F"][:3, :3] @ np.array([0, 0, pc.TCP_Z])
                rows.append((hinge_rad, eval_pose(pts, fk)))
    return rows


def add_unions(vis):
    """Per-pose OR over the cameras of each layout (a true union, not a max of marginals)."""
    for lay, cams in LAYOUTS.items():
        for s in ("rgb", "depth"):
            for t in TARGETS:
                vals = [vis[(c, s, t)] for c in cams if (c, s, t) in vis]
                if vals:
                    vis[(f"UNION:{lay}", s, t)] = bool(any(vals))
    return vis


def summarise(rows):
    """rows = [(key, {(cam,stream,target): bool})] -> {key: {full_name: share}}"""
    acc = collections.defaultdict(lambda: collections.defaultdict(list))
    for key, vis in rows:
        for k, ok in add_unions(vis).items():
            acc[key][k].append(1.0 if ok else 0.0)
    return {str(k): {"n": len(next(iter(d.values()))),
                     "share": {f"{a}/{b}/{c}": float(np.mean(v)) for (a, b, c), v in d.items()}}
            for k, d in sorted(acc.items())}


def layout_union(share, layout, stream, target):
    """Share of poses where at least one camera of the layout sees the target.  NOTE: this is a
    per-camera union of marginals, i.e. an upper bound on the true joint 'any camera' share."""
    vals = [share.get(f"{c}/{stream}/{target}") for c in LAYOUTS[layout]]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"cameras": list(CAMERAS), "layouts": LAYOUTS}
    report["canonical"] = {
        "approach_left": summarise(canonical_approach(1.0)),
        "approach_right": summarise(canonical_approach(-1.0)),
        "passage_left": summarise(canonical_passage(1.0)),
    }
    grasp_l, n_post = canonical_grasp(1.0)
    grasp_r, _ = canonical_grasp(-1.0)
    report["canonical"]["grasp_left"] = summarise(grasp_l)
    report["canonical"]["grasp_right"] = summarise(grasp_r)
    report["canonical"]["grasp_postures_kept"] = n_post
    print("canonical done", round(time.time() - t0), "s", flush=True)
    report["replay_v27"] = replay()
    report["runtime_s"] = time.time() - t0
    (OUT / "w3_layouts.json").write_text(json.dumps(report, indent=1))
    print("total", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
