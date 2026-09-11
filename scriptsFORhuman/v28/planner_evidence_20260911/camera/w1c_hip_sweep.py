#!/usr/bin/env python3
"""W1c: robot half-width vs. a uniform hip abduction angle, with and without the v28 base cameras."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import w1_urdf_width as W

ASSET = W.ASSETS["final_20260906"]
LEGS = tuple(f"{p}_{s}" for p in ("FL", "RL", "FR", "RR") for s in ("hip", "thigh", "calf", "foot"))
joints, links = W.parse_urdf(ASSET / "a2_piper.urdf")


def halfwidth(hip):
    q = {}
    for leg in ("FL", "RL", "FR", "RR"):
        sgn = 1.0 if leg in ("FL", "RL") else -1.0
        q[f"{leg}_hip_joint"] = sgn * hip     # +hip = abduction (outward) for both sides
        q[f"{leg}_thigh_joint"] = 0.5
        q[f"{leg}_calf_joint"] = -1.0
    q.update(W.ARM_V28)
    Ts = W.fk(joints, q)
    legs_y = 0.0
    cams_y = 0.0
    body_y = 0.0
    for name, geoms in links.items():
        if name not in Ts:
            continue
        for g in geoms["collision"]:
            P = W.geom_points(g, ASSET)
            M = Ts[name] @ W.T(W.rpy_R(*g["rpy"]), g["xyz"])
            y = (P @ M[:3, :3].T + M[:3, 3])[:, 1]
            m = float(max(abs(y.min()), abs(y.max())))
            if name in LEGS:
                legs_y = max(legs_y, m)
            elif name == "trunk" and g["name"].startswith("v28_base_"):
                cams_y = max(cams_y, m)
            else:
                body_y = max(body_y, m)
    return legs_y, cams_y, body_y


if __name__ == "__main__":
    rows = []
    print("| hip abduction (rad) | leg half-width (m) | v28 camera half-width (m) | other body (m) | widest |")
    print("|---:|---:|---:|---:|---|")
    for hip in (-0.30, -0.20, -0.10, -0.072, -0.05, 0.0, 0.10, 0.20, 0.30):
        l, c, b = halfwidth(hip)
        widest = max((l, "legs"), (c, "v28_cameras"), (b, "other"))[1]
        rows.append({"hip": hip, "legs": l, "cams": c, "body": b, "widest": widest})
        print(f"| {hip:+.3f} | {l:.4f} | {c:.4f} | {b:.4f} | {widest} |")
    Path("/tmp/v28_team2/camera/out/w1c_hip_sweep.json").write_text(json.dumps(rows, indent=1))
