#!/usr/bin/env python3
"""W2: lateral passability at the doorway crossing step, from archived v27 JSON step traces.

Read-only.  For every first episode in a LEFT and a RIGHT v27 endpoint lane it finds the
first control step with root_pos_rel.x > 0 (the env's own crossing predicate,
door_open_a2_base.py:2295) and computes, for the robot footprint with and without the v28
base-camera boxes, the signed lateral clearance to (a) the two door jambs and (b) the open
panel, using the door model of gr00t/rl/isaac_utils/playground/env_rand/door.py.

Outputs /tmp/v28_team2/camera/out/w2_crossing.json + .md
"""
from __future__ import annotations
import collections, json, math
from pathlib import Path
import numpy as np

REPO = Path("/home/baoquanc/workspace/DoorDog-A2_Piper")
BASE = REPO / "logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step3000/C_S21/nominal"
OUT = Path("/tmp/v28_team2/camera/out")
GAP = 0.002
PANEL_HALF_T = 0.02
HINGE_X = 0.02
# fitted door-width distribution, planner_evidence_20260909/camera/REPORT.md:75 (383/383 envs)
W_QUANTILES = {"p5": 0.82, "p50": 0.957, "p95": 1.08}

# --- robot footprint (trunk frame B, xy projection) -------------------------------------
# COMPUTED by w1_urdf_width.py from a2_piper_vpiper_final_20260906/a2_piper.urdf at the
# configured default leg posture (hip 0, thigh 0.5, calf -1.0) and the v28 arm reset posture.
_RAW = json.loads((OUT / "w1_footprint.json").read_text())


def densify(poly, pitch=0.005):
    """Resample a closed convex polygon boundary at ~pitch so point-wise SDFs are valid."""
    P = np.asarray(poly, float)
    out = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        n = max(2, int(np.linalg.norm(b - a) / pitch) + 1)
        out.append(a + np.linspace(0, 1, n, endpoint=False)[:, None] * (b - a))
    return np.concatenate(out)


FOOTPRINT = {k: densify(v) for k, v in _RAW.items()}


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def load_lane(side):
    rows = json.loads((BASE / side / "stage2_5_step_trace.json").read_text())
    by_env = collections.defaultdict(list)
    for r in rows:
        if r.get("episode_index", 0) != 0:
            continue
        by_env[r["env_id"]].append(r)
    for e in by_env:
        by_env[e].sort(key=lambda r: r["step_index"])
    return by_env


def crossing_rows(by_env):
    out = {}
    for e, rr in by_env.items():
        for r in rr:
            if r["root_pos_rel"][0] > 0.0:
                out[e] = r
                break
    return out


def passage_rows(by_env, xwin=0.6):
    """All steps where the trunk origin is inside the doorway region |x| < xwin."""
    return {e: [r for r in rr if abs(r["root_pos_rel"][0]) < xwin] for e, rr in by_env.items()}


def clearance(poly_B, root_xy, yaw, hinge_rad, W, side_sign):
    """Signed clearance (m) of a 2-D footprint polygon to the doorway obstacles in the door
    frame D.  Positive = free.  Obstacles: the two jamb slabs (x in [-0.07, 0.03], |y| >= W/2)
    and the open panel leaf (hinge at (0.02, -s*W/2), half thickness 0.02)."""
    P = poly_B @ rz(yaw).T + root_xy                       # footprint in D
    res = {}

    # --- jambs: only constrain points that are inside the wall slab in x
    inwall = (P[:, 0] > -0.07) & (P[:, 0] < 0.03)
    half = W / 2 - GAP
    if inwall.any():
        res["jamb"] = float(min(half - P[inwall, 1].max(), half + P[inwall, 1].min()))
    else:
        res["jamb"] = float("inf")

    # --- panel leaf: segment from hinge along the swing direction, half thickness 0.02
    H = np.array([HINGE_X, -side_sign * W / 2])
    d = np.array([math.sin(hinge_rad), side_sign * math.cos(hinge_rad)])
    L = W - GAP
    v = P - H
    t = np.clip(v @ d, 0.0, L)
    perp = np.linalg.norm(v - t[:, None] * d, axis=1) - PANEL_HALF_T
    res["panel"] = float(perp.min())
    res["min"] = float(min(res["jamb"], res["panel"]))
    return res


def main():
    report = {"source": str(BASE), "W_quantiles": W_QUANTILES, "lanes": {}}
    for side in ("left", "right"):
        s = 1.0 if side == "left" else -1.0
        by_env = load_lane(side)
        cross = crossing_rows(by_env)
        lane = {"episodes_traced": len(by_env), "episodes_crossing": len(cross), "per_W": {}}
        hinges = [r["door_hinge_joint_pos"] for r in cross.values()]
        lats = [r["root_pos_rel"][1] for r in cross.values()]
        yaws = [r["root_yaw"] for r in cross.values()]
        lane["hinge_at_crossing_rad"] = {k: float(np.percentile(hinges, q)) for k, q in
                                         (("p5", 5), ("p50", 50), ("p95", 95))} if hinges else None
        lane["hinge_min"] = float(np.min(hinges)) if hinges else None
        lane["root_y_at_crossing_m"] = {k: float(np.percentile(lats, q)) for k, q in
                                        (("p5", 5), ("p50", 50), ("p95", 95))} if lats else None
        lane["root_yaw_at_crossing_rad"] = {k: float(np.percentile(yaws, q)) for k, q in
                                            (("p5", 5), ("p50", 50), ("p95", 95))} if yaws else None
        window = passage_rows(by_env)
        lane["per_W_window"] = {}
        for wname, W in W_QUANTILES.items():
            per = {}
            perw = {}
            for variant, poly in FOOTPRINT.items():
                poly = np.asarray(poly, float)
                vals = []
                for e, r in cross.items():
                    c = clearance(poly, np.array(r["root_pos_rel"][:2]), r["root_yaw"],
                                  r["door_hinge_joint_pos"], W, s)
                    vals.append(c)
                wvals = []
                for e in cross:
                    cs = [clearance(poly, np.array(r["root_pos_rel"][:2]), r["root_yaw"],
                                    r["door_hinge_joint_pos"], W, s) for r in window[e]]
                    if cs:
                        wvals.append({k: min(c[k] for c in cs) for k in ("jamb", "panel", "min")})
                if wvals:
                    wm = np.array([v["min"] for v in wvals])
                    perw[variant] = {
                        "n": int(wm.size),
                        "min_clearance_m": {"min": float(wm.min()), "p5": float(np.percentile(wm, 5)),
                                            "p50": float(np.percentile(wm, 50))},
                        "jamb_p5_m": float(np.percentile([v["jamb"] for v in wvals], 5)),
                        "panel_p5_m": float(np.percentile([v["panel"] for v in wvals], 5)),
                        "share_collide": float(np.mean(wm < 0.0)),
                        "share_lt_30mm": float(np.mean(wm < 0.03)),
                    }
                if not vals:
                    continue
                mn = np.array([v["min"] for v in vals])
                jm = np.array([v["jamb"] for v in vals])
                pn = np.array([v["panel"] for v in vals])
                per[variant] = {
                    "n": int(mn.size),
                    "min_clearance_m": {"min": float(mn.min()), "p5": float(np.percentile(mn, 5)),
                                        "p50": float(np.percentile(mn, 50))},
                    "jamb_m": {"min": float(jm.min()), "p5": float(np.percentile(jm, 5)), "p50": float(np.percentile(jm, 50))},
                    "panel_m": {"min": float(pn.min()), "p5": float(np.percentile(pn, 5)), "p50": float(np.percentile(pn, 50))},
                    "share_collide": float(np.mean(mn < 0.0)),
                    "share_lt_30mm": float(np.mean(mn < 0.03)),
                }
            lane["per_W"][wname] = per
            lane["per_W_window"][wname] = perw
        report["lanes"][side] = lane

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "w2_crossing.json").write_text(json.dumps(report, indent=1))

    lines = ["# W2 crossing-step lateral clearance (COMPUTED)", ""]
    for side, lane in report["lanes"].items():
        lines.append(f"## {side} door — {lane['episodes_crossing']}/{lane['episodes_traced']} episodes cross")
        lines.append(f"hinge at crossing p5/p50/p95 = {lane['hinge_at_crossing_rad']}, min {lane['hinge_min']}")
        lines.append(f"root y at crossing p5/p50/p95 = {lane['root_y_at_crossing_m']}")
        lines.append(f"root yaw at crossing p5/p50/p95 = {lane['root_yaw_at_crossing_rad']}")
        lines.append("")
        lines.append("| W | footprint | min clr min/p5/p50 (mm) | jamb p5 (mm) | panel p5 (mm) | share <0 | share <30 mm |")
        lines.append("|---|---|---|---:|---:|---:|---:|")
        for wname, per in lane["per_W"].items():
            for variant, d in per.items():
                m = d["min_clearance_m"]
                lines.append(f"| {wname} {W_QUANTILES[wname]} | {variant} | "
                             f"{1000*m['min']:.0f} / {1000*m['p5']:.0f} / {1000*m['p50']:.0f} | "
                             f"{1000*d['jamb_m']['p5']:.0f} | {1000*d['panel_m']['p5']:.0f} | "
                             f"{100*d['share_collide']:.1f}% | {100*d['share_lt_30mm']:.1f}% |")
        lines.append("")
        lines.append("### min over the whole passage window |root_x| < 0.6 m")
        lines.append("| W | footprint | min clr min/p5/p50 (mm) | jamb p5 (mm) | panel p5 (mm) | share <0 | share <30 mm |")
        lines.append("|---|---|---|---:|---:|---:|---:|")
        for wname, per in lane["per_W_window"].items():
            for variant, d in per.items():
                m = d["min_clearance_m"]
                lines.append(f"| {wname} {W_QUANTILES[wname]} | {variant} | "
                             f"{1000*m['min']:.0f} / {1000*m['p5']:.0f} / {1000*m['p50']:.0f} | "
                             f"{1000*d['jamb_p5_m']:.0f} | {1000*d['panel_p5_m']:.0f} | "
                             f"{100*d['share_collide']:.1f}% | {100*d['share_lt_30mm']:.1f}% |")
        lines.append("")
    (OUT / "w2_crossing.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
