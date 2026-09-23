#!/usr/bin/env python3
"""W1b: 2-D (xy) convex-hull footprints of the robot in trunk frame B, for passability.

Variants:
  with_cams     : every collision element of every link (incl. the v28 base-camera boxes)
  no_cams       : same, minus every `v28_base_*` collision element on the trunk
  cams_only     : only the v28 base-camera crossbar/rail/post/saddle/housing boxes
  body_no_legs  : trunk + arm + mount, no leg links (the "legs tucked" lower bound)
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull

sys.path.insert(0, str(Path(__file__).parent))
import w1_urdf_width as W

ASSET = W.ASSETS["final_20260906"]
OUT = Path("/tmp/v28_team2/camera/out")
LEGS = tuple(f"{p}_{s}" for p in ("FL", "RL", "FR", "RR") for s in ("hip", "thigh", "calf", "foot"))


def collect():
    joints, links = W.parse_urdf(ASSET / "a2_piper.urdf")
    q = {}
    for leg in ("FL", "RL", "FR", "RR"):
        q[f"{leg}_hip_joint"] = W.DEFAULT_LEGS["hip"]
        q[f"{leg}_thigh_joint"] = W.DEFAULT_LEGS["thigh"]
        q[f"{leg}_calf_joint"] = W.DEFAULT_LEGS["calf"]
    q.update(W.ARM_V28)
    Ts = W.fk(joints, q)
    groups = {"with_cams": [], "no_cams": [], "cams_only": [], "body_no_legs": []}
    for name, geoms in links.items():
        if name not in Ts:
            continue
        for g in geoms["collision"]:
            P = W.geom_points(g, ASSET)
            M = Ts[name] @ W.T(W.rpy_R(*g["rpy"]), g["xyz"])
            Pw = P @ M[:3, :3].T + M[:3, 3]
            is_cam = name == "trunk" and g["name"].startswith("v28_base_")
            groups["with_cams"].append(Pw)
            if is_cam:
                groups["cams_only"].append(Pw)
            else:
                groups["no_cams"].append(Pw)
            if name not in LEGS:
                groups["body_no_legs"].append(Pw)
    out = {}
    for k, v in groups.items():
        pts = np.concatenate(v)[:, :2]
        h = ConvexHull(pts)
        out[k] = pts[h.vertices].round(6).tolist()
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fp = collect()
    (OUT / "w1_footprint.json").write_text(json.dumps(fp))
    for k, v in fp.items():
        a = np.asarray(v)
        print(f"{k:14s} n_hull={len(v):3d}  x {a[:,0].min():+.4f}..{a[:,0].max():+.4f}  "
              f"y {a[:,1].min():+.4f}..{a[:,1].max():+.4f}  full width {a[:,1].max()-a[:,1].min():.4f}")
