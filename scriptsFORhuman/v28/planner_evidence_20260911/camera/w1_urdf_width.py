#!/usr/bin/env python3
"""W1: lateral (y) extent of the A2+PiPER+camera-mount assembly from the v28 candidate URDFs.

Read-only. Parses URDF, does FK at the configured default leg posture and the v28 arm
reset posture, and reports the y extent of every link's collision (and visual) geometry
in the trunk frame B.  Meshes are loaded with trimesh (vertices only, no physics).
Outputs /tmp/v28_team2/camera/out/w1_width.json + .md
"""
from __future__ import annotations
import json, math, re, sys
from pathlib import Path
import numpy as np
import trimesh

REPO = Path("/home/baoquanc/workspace/DoorDog-A2_Piper")
ASSETS = {
    "final_20260906": REPO / "gr00t/rl/data/robots/a2_piper_vpiper_final_20260906",
    "v28_cut_20260909": REPO / "gr00t/rl/data/robots/a2_piper_v28_cut_20260909",
    "v28_merged_20260909": REPO / "gr00t/rl/data/robots/a2_piper_v28_merged_20260909",
}
# gr00t/rl/config/robot/A2_Piper/a2_piper.yaml:122-142 (legs) ; v28 plan D-03/D-03a (arm)
DEFAULT_LEGS = {"hip": 0.0, "thigh": 0.5, "calf": -1.0}
ARM_V28 = {"arm_j1": 0.0, "arm_j2": 0.10, "arm_j3": -0.10, "arm_j4": 0.0, "arm_j5": -0.52, "arm_j6": 1.57,
           "arm_j7": 0.0, "arm_j8": 0.0}
ARM_V27 = {"arm_j1": 0.0, "arm_j2": 0.0, "arm_j3": 0.0, "arm_j4": 0.25, "arm_j5": 0.5, "arm_j6": 1.57,
           "arm_j7": 0.0, "arm_j8": 0.0}


def rpy_R(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def T(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def axis_rot(axis, q):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * (K @ K)


def parse_urdf(path: Path):
    s = path.read_text()
    joints = []
    for m in re.finditer(r'<joint name="([^"]+)" type="([^"]+)">(.*?)</joint>', s, re.S):
        b = m.group(3)
        o = re.search(r'<origin xyz="([^"]*)"\s+rpy="([^"]*)"', b)
        xyz = [float(v) for v in o.group(1).split()] if o else [0, 0, 0]
        rpy = [float(v) for v in o.group(2).split()] if o else [0, 0, 0]
        ax = re.search(r'<axis xyz="([^"]*)"', b)
        joints.append({
            "name": m.group(1), "type": m.group(2),
            "parent": re.search(r'<parent link="([^"]+)"', b).group(1),
            "child": re.search(r'<child link="([^"]+)"', b).group(1),
            "xyz": xyz, "rpy": rpy,
            "axis": [float(v) for v in ax.group(1).split()] if ax else [0, 0, 1],
        })
    links = {}
    for m in re.finditer(r'<link name="([^"]+)">(.*?)</link>', s, re.S):
        name, b = m.group(1), m.group(2)
        geoms = {"collision": [], "visual": []}
        for tag in ("collision", "visual"):
            for gm in re.finditer(r'<%s(?: name="([^"]*)")?>(.*?)</%s>' % (tag, tag), b, re.S):
                gname, gb = gm.group(1) or "", gm.group(2)
                o = re.search(r'<origin xyz="([^"]*)"\s+rpy="([^"]*)"', gb)
                xyz = [float(v) for v in o.group(1).split()] if o else [0, 0, 0]
                rpy = [float(v) for v in o.group(2).split()] if o else [0, 0, 0]
                box = re.search(r'<box size="([^"]*)"', gb)
                cyl = re.search(r'<cylinder radius="([^"]*)" length="([^"]*)"', gb)
                sph = re.search(r'<sphere radius="([^"]*)"', gb)
                mesh = re.search(r'<mesh filename="([^"]*)"', gb)
                g = {"name": gname, "xyz": xyz, "rpy": rpy}
                if box:
                    g["shape"] = "box"; g["size"] = [float(v) for v in box.group(1).split()]
                elif cyl:
                    g["shape"] = "cylinder"; g["r"] = float(cyl.group(1)); g["l"] = float(cyl.group(2))
                elif sph:
                    g["shape"] = "sphere"; g["r"] = float(sph.group(1))
                elif mesh:
                    g["shape"] = "mesh"; g["file"] = mesh.group(1)
                else:
                    continue
                geoms[tag].append(g)
        links[name] = geoms
    return joints, links


_mesh_cache = {}


def geom_points(g, root: Path):
    """Local-frame surface/corner points for a geometry element (before its <origin>)."""
    if g["shape"] == "box":
        sx, sy, sz = [v / 2 for v in g["size"]]
        return np.array([[x, y, z] for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)])
    if g["shape"] == "cylinder":
        r, l = g["r"], g["l"] / 2
        th = np.linspace(0, 2 * math.pi, 64, endpoint=False)
        p = np.stack([r * np.cos(th), r * np.sin(th)], 1)
        return np.concatenate([np.c_[p, np.full(len(p), -l)], np.c_[p, np.full(len(p), l)]])
    if g["shape"] == "sphere":
        r = g["r"]
        u = np.linspace(0, math.pi, 24); v = np.linspace(0, 2 * math.pi, 48)
        U, V = np.meshgrid(u, v)
        return np.stack([r * np.sin(U) * np.cos(V), r * np.sin(U) * np.sin(V), r * np.cos(U)], -1).reshape(-1, 3)
    if g["shape"] == "mesh":
        f = root / g["file"]
        if f not in _mesh_cache:
            m = trimesh.load(f, force="mesh", process=False)
            _mesh_cache[f] = np.asarray(m.vertices, float)
        return _mesh_cache[f]
    raise ValueError(g)


def fk(joints, q):
    """Transforms of every link in trunk frame B (trunk is the root of the fixed/actuated tree here)."""
    Ts = {"trunk": np.eye(4)}
    todo = list(joints)
    for _ in range(len(joints) + 2):
        rest = []
        for j in todo:
            if j["parent"] not in Ts:
                rest.append(j); continue
            M = T(rpy_R(*j["rpy"]), j["xyz"])
            v = q.get(j["name"], 0.0)
            if j["type"] == "revolute" or j["type"] == "continuous":
                M = M @ T(axis_rot(j["axis"], v))
            elif j["type"] == "prismatic":
                M = M @ T(None, np.asarray(j["axis"], float) * v)
            Ts[j["child"]] = Ts[j["parent"]] @ M
        todo = rest
        if not todo:
            break
    return Ts


def y_extents(asset: Path, q):
    joints, links = parse_urdf(asset / "a2_piper.urdf")
    Ts = fk(joints, q)
    out = {}
    for name, geoms in links.items():
        if name not in Ts:
            continue
        rec = {}
        for tag in ("collision", "visual"):
            per = []
            for g in geoms[tag]:
                P = geom_points(g, asset)
                M = Ts[name] @ T(rpy_R(*g["rpy"]), g["xyz"])
                Pw = P @ M[:3, :3].T + M[:3, 3]
                per.append({"name": g["name"] or g["shape"], "shape": g["shape"],
                            "y_min": float(Pw[:, 1].min()), "y_max": float(Pw[:, 1].max()),
                            "z_min": float(Pw[:, 2].min()), "z_max": float(Pw[:, 2].max()),
                            "x_min": float(Pw[:, 0].min()), "x_max": float(Pw[:, 0].max())})
            if per:
                rec[tag] = {"elements": per,
                            "y_min": min(e["y_min"] for e in per), "y_max": max(e["y_max"] for e in per)}
        if rec:
            out[name] = rec
    return out


def main():
    res = {}
    for aname, apath in ASSETS.items():
        for pname, arm in (("v28_reset", ARM_V28), ("v27_default", ARM_V27)):
            q = {}
            for leg in ("FL", "RL", "FR", "RR"):
                q[f"{leg}_hip_joint"] = DEFAULT_LEGS["hip"]
                q[f"{leg}_thigh_joint"] = DEFAULT_LEGS["thigh"]
                q[f"{leg}_calf_joint"] = DEFAULT_LEGS["calf"]
            q.update(arm)
            res[f"{aname}/{pname}"] = y_extents(apath, q)
    outdir = Path("/tmp/v28_team2/camera/out")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "w1_width.json").write_text(json.dumps(res, indent=1))

    # summary
    lines = ["# W1 lateral extents (trunk frame B, metres; COMPUTED from URDF + trimesh vertices)", ""]
    for key, links in res.items():
        lines.append(f"## {key}")
        lines.append("| link | collision y_min/y_max | half-width | visual y_min/y_max |")
        lines.append("|---|---|---:|---|")
        for name in sorted(links):
            c = links[name].get("collision"); v = links[name].get("visual")
            cs = f"{c['y_min']:+.4f} / {c['y_max']:+.4f}" if c else "-"
            hw = f"{max(abs(c['y_min']), abs(c['y_max'])):.4f}" if c else "-"
            vs = f"{v['y_min']:+.4f} / {v['y_max']:+.4f}" if v else "-"
            lines.append(f"| {name} | {cs} | {hw} | {vs} |")
        lines.append("")
    (outdir / "w1_width.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:4]))
    for key in res:
        links = res[key]
        allc = [(n, l["collision"]) for n, l in links.items() if "collision" in l]
        gmax = max(max(abs(c["y_min"]), abs(c["y_max"])) for _, c in allc)
        who = [n for n, c in allc if max(abs(c["y_min"]), abs(c["y_max"])) > gmax - 1e-9]
        print(f"{key}: global collision half-width {gmax:.4f} m  ({who})")


if __name__ == "__main__":
    main()
