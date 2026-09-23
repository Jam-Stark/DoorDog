#!/usr/bin/env python3
"""Compute the LMP-style TCP LPY observation the NEW A2_Base would see, from DoorDog v27 traces.

LPY definition (LMP-a2-current-gripper-observation, mdp/observations.py ee_lpy_in_base_yaw + utils.resolve_sphere_center_w):
  TCP_w    = pos_w(arm_body6_to_gripper) + R_w(arm_body6_to_gripper) @ (0,0,0.105)
  center_w = [root_xy_w + R_yaw(root) @ (0.145, 0.0), 0.704]   (code values at HEAD; docs say 0.135/0.687)
  rel_b    = R_yaw(root)^T (TCP_w - center_w)
  l = |rel_b| ; pitch = atan2(rel_z, hypot(rel_x, rel_y)) ; yaw = atan2(rel_y, rel_x)
Trace supplies root_pos_w, root_quat_w (wxyz), arm_joint_pos (arm_j1..6). FK from the v27 URDF (old asset).
"""
import json, math, sys
sys.path.insert(0, "/tmp/v28_team/locomotion")
from urdf_com import parse, fk, matvec, vadd, matmul

URDF = "/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/data/robots/A2_Piper/a2_piper.urdf"
links, joints = parse(URDF)
arm_joints = ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"]


def quat_to_R(q):
    w, x, y, z = q
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def yaw_of(q):
    w, x, y, z = q
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def pct(v, p):
    s = sorted(v); k = (len(s) - 1) * p; f = math.floor(k); c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def lpy_for_record(r, center_xy=(0.145, 0.0), center_z=0.704, tcp_off=0.105):
    q = {name: float(v) for name, v in zip(arm_joints, r["arm_joint_pos"])}
    poses = fk(links, joints, q)
    Rg, pg = poses["arm_body6_to_gripper"]
    tcp_trunk = vadd(pg, matvec(Rg, [0.0, 0.0, tcp_off]))
    Rroot = quat_to_R(r["root_quat_w"])
    root = r["root_pos_w"]
    tcp_w = vadd(root, matvec(Rroot, tcp_trunk))
    yaw = yaw_of(r["root_quat_w"])
    cy, sy = math.cos(yaw), math.sin(yaw)
    cx_w = root[0] + cy * center_xy[0] - sy * center_xy[1]
    cy_w = root[1] + sy * center_xy[0] + cy * center_xy[1]
    rel_w = [tcp_w[0] - cx_w, tcp_w[1] - cy_w, tcp_w[2] - center_z]
    rel_b = [cy * rel_w[0] + sy * rel_w[1], -sy * rel_w[0] + cy * rel_w[1], rel_w[2]]
    l = math.sqrt(sum(v * v for v in rel_b))
    pitch = math.atan2(rel_b[2], math.hypot(rel_b[0], rel_b[1]))
    yw = math.atan2(rel_b[1], rel_b[0])
    return l, pitch, yw, root[2]


def run(label, path, stride=4):
    recs = json.load(open(path))
    per = {}
    for i, r in enumerate(recs):
        if i % stride:
            continue
        st = int(r["stage_buf"])
        l, p, y, z = lpy_for_record(r)
        d = per.setdefault(st, {"l": [], "p": [], "y": [], "z": [], "oor": 0, "n": 0})
        d["l"].append(l); d["p"].append(p); d["y"].append(y); d["z"].append(z); d["n"] += 1
        # LMP Stage2 arm-goal sampling ranges: radius (0.4,0.8), pitch (-1,1), yaw (-1.2,1.2)
        if not (0.4 <= l <= 0.8 and -1.0 <= p <= 1.0 and -1.2 <= y <= 1.2):
            d["oor"] += 1
    print(f"\n##### {label} ({path}) stride={stride}")
    print("stage | n | l p5/p50/p95 [m] | pitch p5/p50/p95 [rad] | yaw p5/p50/p95 [rad] | root z p50 | share outside LMP Stage2 goal box l[0.4,0.8] p[-1,1] y[-1.2,1.2]")
    for st in sorted(per):
        d = per[st]
        print(f"{st} | {d['n']} | {pct(d['l'],.05):.3f}/{pct(d['l'],.5):.3f}/{pct(d['l'],.95):.3f} | {pct(d['p'],.05):+.3f}/{pct(d['p'],.5):+.3f}/{pct(d['p'],.95):+.3f} | {pct(d['y'],.05):+.3f}/{pct(d['y'],.5):+.3f}/{pct(d['y'],.95):+.3f} | {pct(d['z'],.5):.3f} | {d['oor']/d['n']:.3f}")


if __name__ == "__main__":
    # self-check: default posture at flat root z=0.55 should reproduce urdf_com.py numbers (l=0.1956 pitch=0.7238 yaw=0.1594)
    r = {"arm_joint_pos": [0, 0, 0, 0.25, 0.5, 1.57], "root_quat_w": [1, 0, 0, 0], "root_pos_w": [0, 0, 0.55]}
    print("SELF-CHECK old default posture flat:", ["%.4f" % v for v in lpy_for_record(r)])
    r = {"arm_joint_pos": [0, 0, 0, 0.0, -0.44, 1.57], "root_quat_w": [1, 0, 0, 0], "root_pos_w": [0, 0, 0.55]}
    print("SELF-CHECK new v28 posture flat (old asset FK):", ["%.4f" % v for v in lpy_for_record(r)])
    r = {"arm_joint_pos": [0, 0, 0, 0.0, -0.44, 1.57], "root_quat_w": [1, 0, 0, 0], "root_pos_w": [0, 0, 0.49]}
    print("SELF-CHECK new v28 posture at walking root z=0.49:", ["%.4f" % v for v in lpy_for_record(r)])
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        run(label, path)
