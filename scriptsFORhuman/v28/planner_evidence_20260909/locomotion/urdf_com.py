#!/usr/bin/env python3
"""Parse A2_Piper URDF(s): link masses, joint tree, FK for arm postures, whole-robot CoM in trunk frame.

Read-only on repo files. stdlib only (no numpy needed, but use math).
"""
import math
import sys
import xml.etree.ElementTree as ET


def rpy_to_R(r, p, y):
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    # R = Rz(y) * Ry(p) * Rx(r)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def axis_angle_R(axis, th):
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / n, y / n, z / n
    c, s = math.cos(th), math.sin(th)
    C = 1 - c
    return [
        [c + x * x * C, x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, c + z * z * C],
    ]


def matmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def matvec(A, v):
    return [sum(A[i][k] * v[k] for k in range(3)) for i in range(3)]


def vadd(a, b):
    return [a[i] + b[i] for i in range(3)]


def parse(path):
    root = ET.parse(path).getroot()
    links = {}
    for l in root.findall("link"):
        i = l.find("inertial")
        if i is None:
            links[l.get("name")] = (0.0, [0.0, 0.0, 0.0])
            continue
        m = float(i.find("mass").get("value"))
        o = i.find("origin")
        xyz = [float(v) for v in (o.get("xyz") if o is not None else "0 0 0").split()]
        links[l.get("name")] = (m, xyz)
    joints = []
    for j in root.findall("joint"):
        o = j.find("origin")
        xyz = [float(v) for v in (o.get("xyz") if o is not None and o.get("xyz") else "0 0 0").split()]
        rpy = [float(v) for v in (o.get("rpy") if o is not None and o.get("rpy") else "0 0 0").split()]
        ax = j.find("axis")
        axis = [float(v) for v in (ax.get("xyz") if ax is not None else "1 0 0").split()]
        joints.append(
            dict(
                name=j.get("name"),
                type=j.get("type"),
                parent=j.find("parent").get("link"),
                child=j.find("child").get("link"),
                xyz=xyz,
                rpy=rpy,
                axis=axis,
            )
        )
    return links, joints


def fk(links, joints, q, root="trunk"):
    """Return dict link -> (R, p) in root frame given joint angles dict."""
    children = {}
    for j in joints:
        children.setdefault(j["parent"], []).append(j)
    poses = {root: ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0.0, 0.0, 0.0])}
    stack = [root]
    while stack:
        par = stack.pop()
        Rp, pp = poses[par]
        for j in children.get(par, []):
            Rj = rpy_to_R(*j["rpy"])
            pj = vadd(pp, matvec(Rp, j["xyz"]))
            Rc = matmul(Rp, Rj)
            if j["type"] in ("revolute", "continuous", "prismatic"):
                th = q.get(j["name"], 0.0)
                if j["type"] == "prismatic":
                    pj = vadd(pj, matvec(Rc, [a * th for a in j["axis"]]))
                else:
                    Rc = matmul(Rc, axis_angle_R(j["axis"], th))
            poses[j["child"]] = (Rc, pj)
            stack.append(j["child"])
    return poses


def com(links, poses, subset=None):
    M = 0.0
    c = [0.0, 0.0, 0.0]
    for name, (m, lxyz) in links.items():
        if subset is not None and name not in subset:
            continue
        if name not in poses:
            continue
        R, p = poses[name]
        w = vadd(p, matvec(R, lxyz))
        M += m
        c = [c[i] + m * w[i] for i in range(3)]
    return M, [ci / M if M > 0 else 0.0 for ci in c]


LEGQ = {}
for leg in ("FL", "FR", "RL", "RR"):
    LEGQ[f"{leg}_hip_joint"] = 0.0
    LEGQ[f"{leg}_thigh_joint"] = 0.5
    LEGQ[f"{leg}_calf_joint"] = -1.0

POSTURES = {
    "old_default_[0,0,0,0.25,0.5,1.57]": [0.0, 0.0, 0.0, 0.25, 0.5, 1.57],
    "new_v28_[0,0,0,0,-0.44,1.57]": [0.0, 0.0, 0.0, 0.0, -0.44, 1.57],
    "lmp_stage1_hold_[0,1.48,-0.63,-0.84,0,1.57]": [0.0, 1.48, -0.63, -0.84, 0.0, 1.57],
}


def main():
    for path in sys.argv[1:]:
        links, joints = parse(path)
        print("=" * 100)
        print(path)
        tot = sum(m for m, _ in links.values())
        print(f"links={len(links)} total_mass={tot:.4f} kg")
        arm_links = [n for n in links if n.startswith("arm_")]
        arm_mass = sum(links[n][0] for n in arm_links)
        print(f"trunk mass={links['trunk'][0]:.4f} com={links['trunk'][1]}  arm links mass sum={arm_mass:.4f}")
        for n in sorted(links):
            print(f"   {n:26s} m={links[n][0]:8.4f} com_local={links[n][1]}")
        print("-- joints")
        for j in joints:
            print(f"   {j['name']:22s} {j['type']:9s} {j['parent']:22s}->{j['child']:22s} xyz={j['xyz']} rpy={j['rpy']} axis={j['axis']}")
        print("-- FK / CoM (trunk frame), legs at hips 0 / thighs 0.5 / calfs -1.0")
        for label, arm in POSTURES.items():
            q = dict(LEGQ)
            for k, v in zip(["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"], arm):
                q[k] = v
            q["arm_j7"] = 0.0
            q["arm_j8"] = 0.0
            poses = fk(links, joints, q)
            M, c = com(links, poses)
            Ma, ca = com(links, poses, subset=set(arm_links))
            Rg, pg = poses["arm_body6_to_gripper"]
            tcp = vadd(pg, matvec(Rg, [0.0, 0.0, 0.105]))  # LMP TCP offset
            tcp_dd = vadd(pg, matvec(Rg, [0.0, 0.0, 0.085]))  # DoorDog a2_gripper_source_tcp_offset_z
            print(f"  {label}")
            print(f"     whole-robot M={M:.4f} CoM_trunk=({c[0]:+.4f},{c[1]:+.4f},{c[2]:+.4f})")
            print(f"     arm-only   M={Ma:.4f} CoM_trunk=({ca[0]:+.4f},{ca[1]:+.4f},{ca[2]:+.4f})")
            print(f"     gripper_base(arm_body6_to_gripper) p=({pg[0]:+.4f},{pg[1]:+.4f},{pg[2]:+.4f})")
            print(f"     TCP(+0.105 local z) p=({tcp[0]:+.4f},{tcp[1]:+.4f},{tcp[2]:+.4f})   TCP(+0.085) p=({tcp_dd[0]:+.4f},{tcp_dd[1]:+.4f},{tcp_dd[2]:+.4f})")
            # LMP sphere frame: center at base-yaw (0.145, 0, world 0.704); with root at z=0.55 flat -> trunk-frame z = 0.154
            for (cx, cz, tag) in ((0.145, 0.704 - 0.55, "code(0.145,0.704)"), (0.135, 0.687 - 0.55, "doc(0.135,0.687)")):
                rel = [tcp[0] - cx, tcp[1] - 0.0, tcp[2] - cz]
                l = math.sqrt(sum(r * r for r in rel))
                pitch = math.atan2(rel[2], math.hypot(rel[0], rel[1]))
                yaw = math.atan2(rel[1], rel[0])
                print(f"     LPY[{tag}] (flat root z=0.55): l={l:.4f} pitch={pitch:+.4f} yaw={yaw:+.4f}")
            if "arm_body0" in poses:
                print(f"     arm_body0 (arm base) p={[round(v,4) for v in poses['arm_body0'][1]]}")


if __name__ == "__main__":
    main()
