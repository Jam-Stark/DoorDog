"""CPU-only geometric clearance check: PiPER arm links vs. Vpiper mount / plate / trunk boxes.

Static evidence (no physics engine). Collision shapes are modelled as PhysX would build them
with collider_type=convex_hull: convex hull of each URDF <collision> mesh; boxes as 8-vertex hulls.
Exact convex-convex separation via LP feasibility (intersection) + SLSQP QP (distance).
Writes JSON/markdown to /tmp/v28_team/asset/.
"""
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import trimesh
from scipy.optimize import linprog, minimize
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation as R

ROOT = "/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/data/robots"
NEW = os.path.join(ROOT, "a2_piper_vpiper_final_20260906")
OLD = os.path.join(ROOT, "A2_Piper")
OUT = "/tmp/v28_team/asset"

ARM_JOINTS = ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"]
ARM_LINKS = ["arm_body0", "arm_body1", "arm_body2", "arm_body3", "arm_body4", "arm_body5",
             "arm_body6", "arm_body6_to_gripper", "arm_body7", "arm_body8"]
MOUNT_LINKS = ["vpiper_main", "vpiper_support", "metal_plate_5mm"]
# parent-child pairs whose contact PhysX filters (joint collisionEnabled=False by importer default)
ADJACENT = {("trunk", "arm_body0"), ("arm_body0", "arm_body1"), ("arm_body1", "arm_body2"),
            ("arm_body2", "arm_body3"), ("arm_body3", "arm_body4"), ("arm_body4", "arm_body5"),
            ("arm_body5", "arm_body6"), ("arm_body6", "arm_body6_to_gripper"),
            ("arm_body6_to_gripper", "arm_body7"), ("arm_body6_to_gripper", "arm_body8"),
            ("trunk", "vpiper_main"), ("vpiper_main", "vpiper_support"), ("vpiper_main", "metal_plate_5mm")}


def T(xyz, rpy):
    m = np.eye(4)
    m[:3, :3] = R.from_euler("xyz", rpy).as_matrix()
    m[:3, 3] = xyz
    return m


def parse(urdf):
    root = ET.parse(urdf).getroot()
    base = os.path.dirname(urdf)
    links, joints = {}, {}
    for l in root.findall("link"):
        cols = []
        for c in l.findall("collision"):
            o = c.find("origin")
            xyz = [float(x) for x in (o.get("xyz") if o is not None else "0 0 0").split()]
            rpy = [float(x) for x in (o.get("rpy", "0 0 0") if o is not None else "0 0 0").split()]
            g = list(c.find("geometry"))[0]
            cols.append((T(xyz, rpy), g.tag, dict(g.attrib)))
        links[l.get("name")] = cols
    for j in root.findall("joint"):
        o = j.find("origin")
        ax = j.find("axis")
        joints[j.get("name")] = dict(
            type=j.get("type"), parent=j.find("parent").get("link"), child=j.find("child").get("link"),
            T=T([float(x) for x in o.get("xyz").split()], [float(x) for x in o.get("rpy", "0 0 0").split()]),
            axis=np.array([float(x) for x in ax.get("xyz").split()]) if ax is not None else None)
    return links, joints, base


def shape_vertices(base, geom, attr):
    if geom == "mesh":
        m = trimesh.load(os.path.join(base, attr["filename"]), force="mesh")
        v = np.asarray(m.vertices, dtype=float)
        s = attr.get("scale")
        if s:
            v = v * np.array([float(x) for x in s.split()])
        return v
    if geom == "box":
        sx, sy, sz = [float(x) / 2 for x in attr["size"].split()]
        return np.array([[i * sx, j * sy, k * sz] for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)])
    if geom == "cylinder":
        r_, h = float(attr["radius"]), float(attr["length"]) / 2
        a = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        return np.array([[r_ * np.cos(t), r_ * np.sin(t), z] for t in a for z in (-h, h)])
    if geom == "sphere":
        r_ = float(attr["radius"])
        m = trimesh.creation.icosphere(subdivisions=2, radius=r_)
        return np.asarray(m.vertices)
    raise ValueError(geom)


def fk(joints, q, root="trunk"):
    """World (=trunk) transforms of every link for joint dict q (missing => 0)."""
    Tw = {root: np.eye(4)}
    children = {}
    for n, j in joints.items():
        children.setdefault(j["parent"], []).append(n)
    stack = [root]
    while stack:
        p = stack.pop()
        for jn in children.get(p, []):
            j = joints[jn]
            Tj = j["T"].copy()
            if j["type"] in ("revolute", "continuous"):
                Tj = Tj @ T([0, 0, 0], [0, 0, 0]) @ np.block([[R.from_rotvec(j["axis"] * q.get(jn, 0.0)).as_matrix(), np.zeros((3, 1))], [np.zeros((1, 3)), 1]])
            elif j["type"] == "prismatic":
                Tj[:3, 3] += Tj[:3, :3] @ (j["axis"] * q.get(jn, 0.0))
            Tw[j["child"]] = Tw[p] @ Tj
            stack.append(j["child"])
    return Tw


class Hull:
    def __init__(self, name, pts):
        self.name = name
        h = ConvexHull(pts)
        self.v = pts[h.vertices]
        eq = h.equations  # n.x + d <= 0 inside
        nrm = np.linalg.norm(eq[:, :3], axis=1, keepdims=True)
        self.A = eq[:, :3] / nrm
        self.b = -eq[:, 3:4] / nrm
        self.c = self.v.mean(0)
        self.r = np.linalg.norm(self.v - self.c, axis=1).max()

    def transformed(self, Tm):
        return Hull(self.name, (Tm[:3, :3] @ self.v.T).T + Tm[:3, 3])


def intersect_depth(h1, h2):
    """LP: max t s.t. A1 x + t <= b1, A2 x + t <= b2. t>0 => interiors overlap, t = inscribed ball radius."""
    A = np.vstack([np.hstack([h1.A, np.ones((len(h1.A), 1))]), np.hstack([h2.A, np.ones((len(h2.A), 1))])])
    b = np.vstack([h1.b, h2.b]).ravel()
    res = linprog(c=[0, 0, 0, -1], A_ub=A, b_ub=b, bounds=[(None, None)] * 3 + [(-1.0, 1.0)], method="highs")
    if res.status != 0:
        return None
    return float(res.x[3])


def distance(h1, h2):
    """Exact min distance between two convex polytopes (SLSQP on 6 vars). Returns >=0."""
    x0 = np.concatenate([h1.c, h2.c])
    cons = [{"type": "ineq", "fun": lambda z, A=h1.A, b=h1.b: (b.ravel() - A @ z[:3])},
            {"type": "ineq", "fun": lambda z, A=h2.A, b=h2.b: (b.ravel() - A @ z[3:])}]
    res = minimize(lambda z: np.sum((z[:3] - z[3:]) ** 2), x0, constraints=cons, method="SLSQP",
                   options={"maxiter": 300, "ftol": 1e-14})
    return math.sqrt(max(res.fun, 0.0))


def build_hulls(links, base, names):
    out = {}
    for n in names:
        out[n] = [Hull(f"{n}#{i}", shape_vertices(base, g, a) @ Tm[:3, :3].T + Tm[:3, 3]) for i, (Tm, g, a) in enumerate(links[n])]
    return out


def check(links, joints, base, q, arm_links, env_links, label):
    Tw = fk(joints, q)
    hulls = build_hulls(links, base, arm_links + env_links)
    rows = []
    for a in arm_links:
        for e in env_links:
            if (a, e) in ADJACENT or (e, a) in ADJACENT or a == e:
                continue
            best = None
            for ha in hulls[a]:
                Ha = ha.transformed(Tw[a])
                for he in hulls[e]:
                    He = he.transformed(Tw[e])
                    if np.linalg.norm(Ha.c - He.c) > Ha.r + He.r + 0.02:
                        d = np.linalg.norm(Ha.c - He.c) - Ha.r - He.r  # lower bound
                        if best is None or d < best[0]:
                            best = (d, "bound", ha.name, he.name)
                        continue
                    t = intersect_depth(Ha, He)
                    if t is not None and t > 1e-7:
                        val = -t
                        kind = "OVERLAP"
                    else:
                        val = distance(Ha, He)
                        kind = "sep"
                    if best is None or val < best[0]:
                        best = (val, kind, ha.name, he.name)
            rows.append(dict(arm=a, env=e, min_dist_m=round(best[0], 5), kind=best[1], pair=(best[2], best[3])))
    return rows, Tw


def main():
    links_n, joints_n, base_n = parse(os.path.join(NEW, "a2_piper.urdf"))
    links_o, joints_o, base_o = parse(os.path.join(OLD, "a2_piper.urdf"))
    q_new = dict(zip(ARM_JOINTS, [0, 0, 0, 0, -0.44, 1.57]))
    q_new52 = dict(zip(ARM_JOINTS, [0, 0, 0, 0, -0.52, 1.57]))
    q_old = dict(zip(ARM_JOINTS, [0, 0, 0, 0.25, 0.5, 1.57]))
    report = {}
    for label, q in [("NEW_asset_q_new", q_new), ("NEW_asset_q_new_j5m052", q_new52), ("NEW_asset_q_old", q_old)]:
        rows, Tw = check(links_n, joints_n, base_n, q, ARM_LINKS, MOUNT_LINKS + ["trunk"], label)
        report[label] = dict(rows=rows, tcp_trunk_frame=Tw["arm_body6_to_gripper"][:3, 3].round(4).tolist(),
                             gripper_tip_trunk_frame=(Tw["arm_body6_to_gripper"] @ np.array([0, 0, 0.1358, 1]))[:3].round(4).tolist())
    rows, Tw = check(links_o, joints_o, base_o, q_old, ARM_LINKS, ["trunk"], "OLD")
    report["OLD_asset_q_old"] = dict(rows=rows, tcp_trunk_frame=Tw["arm_body6_to_gripper"][:3, 3].round(4).tolist())
    rows, Tw = check(links_o, joints_o, base_o, q_new, ARM_LINKS, ["trunk"], "OLD")
    report["OLD_asset_q_new"] = dict(rows=rows, tcp_trunk_frame=Tw["arm_body6_to_gripper"][:3, 3].round(4).tolist())

    # ---- sweep: which (j1,j2,j3) configs make arm links overlap mount/plate/trunk (new) vs trunk only (old)
    sweep = []
    j2s = np.linspace(0.0, 3.14, 17)
    j3s = np.linspace(-2.967, 0.0, 13)
    j1s = [0.0, 1.5708, -1.5708, 2.618]
    hull_cache_n = build_hulls(links_n, base_n, ["arm_body2", "arm_body3", "arm_body4", "arm_body5", "arm_body6", "arm_body6_to_gripper", "arm_body7", "arm_body8"] + MOUNT_LINKS + ["trunk"])
    hull_cache_o = build_hulls(links_o, base_o, ["arm_body2", "arm_body3", "arm_body4", "arm_body5", "arm_body6", "arm_body6_to_gripper", "arm_body7", "arm_body8", "trunk"])

    def any_overlap(links, joints, cache, q, arm_links, env_links):
        Tw = fk(joints, q)
        hits = []
        for a in arm_links:
            for e in env_links:
                for ha in cache[a]:
                    Ha = ha.transformed(Tw[a])
                    for he in cache[e]:
                        He = he.transformed(Tw[e])
                        if np.linalg.norm(Ha.c - He.c) > Ha.r + He.r:
                            continue
                        t = intersect_depth(Ha, He)
                        if t is not None and t > 1e-6:
                            hits.append((a, e, round(t, 4)))
                            break
                    else:
                        continue
                    break
        return hits

    arm_sw = ["arm_body2", "arm_body3", "arm_body4", "arm_body5", "arm_body6", "arm_body6_to_gripper", "arm_body7", "arm_body8"]
    n_new_only = 0
    n_total = 0
    for j1 in j1s:
        for j2 in j2s:
            for j3 in j3s:
                q = dict(zip(ARM_JOINTS, [j1, j2, j3, 0.0, -0.44, 1.57]))
                hn = any_overlap(links_n, joints_n, hull_cache_n, q, arm_sw, MOUNT_LINKS + ["trunk"])
                ho = any_overlap(links_o, joints_o, hull_cache_o, q, arm_sw, ["trunk"])
                n_total += 1
                if hn and not ho:
                    n_new_only += 1
                if hn or ho:
                    sweep.append(dict(j1=round(j1, 4), j2=round(j2, 4), j3=round(j3, 4), new_hits=hn, old_hits=ho))
    report["sweep"] = dict(grid=dict(j1=j1s, j2=j2s.round(4).tolist(), j3=j3s.round(4).tolist(), j4=0.0, j5=-0.44, j6=1.57),
                           n_configs=n_total, n_configs_overlapping_new_only=n_new_only,
                           n_configs_overlapping_any=len(sweep), entries=sweep)
    with open(os.path.join(OUT, "mount_clearance.json"), "w") as f:
        json.dump(report, f, indent=1, default=float)
    # markdown summary
    lines = ["# arm-vs-mount clearance (convex-hull colliders, STATIC CPU)", ""]
    for label in ["NEW_asset_q_new", "NEW_asset_q_new_j5m052", "NEW_asset_q_old", "OLD_asset_q_old", "OLD_asset_q_new"]:
        lines.append(f"## {label}  TCP(arm_body6_to_gripper origin, trunk frame)={report[label]['tcp_trunk_frame']}")
        lines.append("| arm link | env link | min dist [m] | kind |")
        lines.append("|---|---|---:|---|")
        for r in sorted(report[label]["rows"], key=lambda r: r["min_dist_m"]):
            if r["min_dist_m"] < 0.06 or r["kind"] == "OVERLAP":
                lines.append(f"| {r['arm']} | {r['env']} | {r['min_dist_m']:.4f} | {r['kind']} |")
        lines.append("")
    sw = report["sweep"]
    lines.append(f"## sweep j1x j2 x j3 = {len(j1s)}x{len(j2s)}x{len(j3s)} = {sw['n_configs']} configs (j4=0,j5=-0.44,j6=1.57)")
    lines.append(f"configs with any arm-link overlap (new asset incl. mount/plate/trunk OR old asset trunk): {sw['n_configs_overlapping_any']}")
    lines.append(f"configs overlapping in NEW asset but NOT in OLD asset: {sw['n_configs_overlapping_new_only']}")
    lines.append("")
    lines.append("| j1 | j2 | j3 | new hits (arm, env, inscribed r) | old hits |")
    lines.append("|---:|---:|---:|---|---|")
    for e in sw["entries"]:
        lines.append(f"| {e['j1']} | {e['j2']} | {e['j3']} | {e['new_hits']} | {e['old_hits']} |")
    with open(os.path.join(OUT, "mount_clearance.md"), "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:80]))
    print("... full output in", OUT)


if __name__ == "__main__":
    main()
