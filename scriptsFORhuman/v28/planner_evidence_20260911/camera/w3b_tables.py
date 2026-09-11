#!/usr/bin/env python3
"""W3b: sanity checks + decision tables from w3_layouts.json (true per-pose layout unions)."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import w3_layouts as L

OUT = Path("/tmp/v28_team2/camera/out")
R = json.loads((OUT / "w3_layouts.json").read_text())


def rot_err(A, B):
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(A.T @ B) - 1.0) / 2.0))))


def check():
    lines = ["## reconstruction check vs planner_evidence_20260909/camera/variants/U3_F45_B15.json"]
    for name, key in (("base_left_B15", "base_left"), ("base_right_B15", "base_right"), ("wrist_F45_180", "wrist")):
        ref = L.CAMS_B15[key]
        for s in ("rgb", "depth"):
            mine = L.CAMERAS[name][1][s].T_parent_opt
            theirs = np.array(ref["streams"][s]["T_parent_optical"], float)
            lines.append(f"- {name}/{s}: |dp| = {1000*np.linalg.norm(mine[:3,3]-theirs[:3,3]):.3f} mm, "
                         f"drot = {rot_err(mine[:3,:3], theirs[:3,:3]):.4f} deg")
    return lines


def fmt(v):
    return "-" if v is None else f"{100*v:.0f}"


def emit(title, share, targets, streams=("rgb", "depth"), rows=None):
    rows = rows if rows is not None else [f"UNION:{l}" for l in L.LAYOUTS]
    hdr = "| set | " + " | ".join(f"{t} {s[0].upper()}" for t in targets for s in streams) + " |"
    sep = "|---|" + "|".join("---:" for _ in targets for _ in streams) + "|"
    out = [f"### {title}", hdr, sep]
    for r in rows:
        cells = [fmt(share.get(f"{r}/{s}/{t}")) for t in targets for s in streams]
        out.append(f"| {r.replace('UNION:','')} | " + " | ".join(cells) + " |")
    out.append("")
    return out


T_NAV = ["handle", "frame_handle_side_z1.0", "frame_hinge_side_z1.0", "doorway_floor_centre", "panel_free_edge_z1.0"]
CAMROWS = list(L.CAMERAS)


def main():
    lines = ["# W3 layout coverage (COMPUTED; pinhole + Min-Z + arm-capsule screen; no mesh / door-panel occlusion)", ""]
    lines += check() + [""]
    lines.append("Shares are per-pose UNIONs over the cameras of a layout (a pose counts if at least one "
                 "camera of that layout has the point inside its frustum beyond Min-Z and, for trunk-mounted "
                 "cameras looking at handle/TCP/fingers, not behind an arm capsule).")
    lines.append("")

    lines.append("## (b) trajectory-independent canonical postures (task geometry only)")
    for scen in ("approach_left", "approach_right", "passage_left"):
        for key, d in R["canonical"][scen].items():
            if not isinstance(d, dict):
                continue
            lines += emit(f"{scen} @ {key} (n={d['n']})", d["share"], T_NAV)
    for scen in ("grasp_left", "grasp_right"):
        for key, d in R["canonical"][scen].items():
            if not isinstance(d, dict):
                continue
            lines += emit(f"{scen} @ hinge {key} (n={d['n']}) — per CAMERA",
                          d["share"], ["handle", "frame_handle_side_z1.0", "panel_free_edge_z1.0"],
                          rows=CAMROWS)
    lines.append(f"grasp postures kept from IK-free sampling: {R['canonical']['grasp_postures_kept']}")
    lines.append("")

    lines.append("## (a) replay of archived v27 trajectories (CONDITIONAL on how the OLD Teacher moved)")
    for lane, stages in R["replay_v27"].items():
        for st, d in stages.items():
            if st in ("stage2", "stage3", "stage4"):
                lines += emit(f"{lane} {st} (n={d['frames']})", d["share"], T_NAV)
    lines.append("### per-camera detail, C_S2/left and C_S2/right, stage3")
    for lane in ("C_S2/left", "C_S2/right"):
        d = R["replay_v27"][lane]["stage3"]
        lines += emit(f"{lane} stage3 per CAMERA (n={d['frames']})", d["share"], T_NAV, rows=CAMROWS)

    (OUT / "w3_tables.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    print("written", OUT / "w3_tables.md")


if __name__ == "__main__":
    main()
