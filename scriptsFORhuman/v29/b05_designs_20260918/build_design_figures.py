"""Generate B05 nominal design data and figures; this does not create simulation assets."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Ellipse, FancyBboxPatch
import numpy as np

OUT = Path(__file__).resolve().parent
PARAMS = [
    dict(id="F0", name="原始圆直杆", kind="straight", X=125, normal=26, closing=26, section="circle", free=[30, 95]),
    dict(id="F1", name="椭圆直杆", kind="straight", X=130, normal=28, closing=20, section="ellipse", free=[28, 102]),
    dict(id="F2", name="圆角扁直杆", kind="straight", X=130, normal=30, closing=18, section="rounded", corner=6, free=[28, 102]),
    dict(id="F3", name="单弧轻弯杆", kind="arc", L=135, R=400, normal=26, closing=26, section="circle", free=[33, 102]),
    dict(id="F4", name="浅 S 杆", kind="sine", X=130, amplitude=3, normal=24, closing=24, section="circle", inset=31),
    dict(id="F5", name="偏置直腹杆", kind="offset", X=140, amplitude=8, ramp=32, normal=26, closing=26, section="circle", free_x=[34, 106]),
    dict(id="F6", name="缓变锥度杆", kind="taper", X=130, normal=28, closing=28, tip=24, section="circle", free=[30, 100]),
]


def make_family(p):
    p = dict(p)
    u = np.linspace(0, 1, 241)
    if p["kind"] == "arc":
        half = p["L"] / p["R"] / 2
        a = (u - .5) * p["L"] / p["R"]
        x = p["R"] * (np.sin(a) + np.sin(half))
        z = p["R"] * (np.cos(a) - np.cos(half))
    else:
        x = u * p["X"]
        if p["kind"] == "sine":
            z = p["amplitude"] * np.sin(2 * np.pi * u)
        elif p["kind"] == "offset":
            a = np.minimum(x / p["ramp"], (p["X"] - x) / p["ramp"]).clip(0, 1)
            z = p["amplitude"] * a * a * (3 - 2 * a)
        else:
            z = np.zeros_like(x)
    ds = np.hypot(np.diff(x), np.diff(z))
    s = np.r_[0., ds.cumsum()]
    tangent = np.stack([np.gradient(x), np.gradient(z)], axis=1)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    normal = np.full_like(x, p["normal"])
    closing = np.full_like(x, p["closing"])
    if p["kind"] == "taper":
        normal = closing = p["normal"] + (p["tip"] - p["normal"]) * u * u * (3 - 2 * u)
    if "free_x" in p:
        lo, hi = np.interp(p["free_x"], x, s)
    elif "inset" in p:
        lo, hi = p["inset"], s[-1] - p["inset"]
    else:
        lo, hi = p["free"]
    # 56 mm is a static whole-finger tangent envelope, not a certified pad width.
    centre_lo, centre_hi = lo + 28 + 3, hi - 28 - 3
    sg = (centre_lo + centre_hi) / 2
    gx, gz = np.interp(sg, s, x), np.interp(sg, s, z)
    tx, tz = np.interp(sg, s, tangent[:, 0]), np.interp(sg, s, tangent[:, 1])
    p.update(
        arc_length=float(s[-1]), free_s=[float(lo), float(hi)],
        centre_s=[float(centre_lo), float(centre_hi)], target_s=float(sg),
        target_xyz=[float(gx), 77.5, float(gz)],
        target_tangent_degrees=float(np.degrees(np.arctan2(tz, tx))),
        points=np.round(np.c_[s, x, z, normal, closing, tangent], 5).tolist(),
    )
    return p


def outline(f, lo=0, hi=None, caps=True):
    a = np.array(f["points"])
    if hi is None:
        hi = a[-1, 0]
    ss = np.linspace(lo, hi, 170)
    q = np.stack([np.interp(ss, a[:, 0], a[:, j]) for j in range(1, 7)], axis=1)
    c, t = q[:, :2], q[:, 4:6]
    n = np.c_[-t[:, 1], t[:, 0]]
    b = q[:, 3] / 2
    top, bottom = c + n * b[:, None], c - n * b[:, None]
    if not caps:
        return np.r_[top, bottom[::-1]]
    phi = np.linspace(0, np.pi, 24)
    cap1 = c[-1] + np.cos(phi)[:, None] * b[-1] * n[-1] + np.sin(phi)[:, None] * b[-1] * t[-1]
    cap0 = c[0] - np.cos(phi)[:, None] * b[0] * n[0] - np.sin(phi)[:, None] * b[0] * t[0]
    return np.r_[top, cap1, bottom[::-1], cap0]


families = [make_family(p) for p in PARAMS]
payload = dict(
    units="mm", status="NOMINAL_DESIGN_NOT_SIMULATION_VALIDATED",
    coordinates="u along main lever from neck to tip; n away from door face; z vertical",
    axle_length=195, door_panel_thickness=40, face_to_centerline=77.5,
    tangent_envelope_reference=56, illustrative_end_margin=3,
    pregrasp_distance=100, hook_length_reference=50, families=families,
)
(OUT / "families.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

plt.rcParams.update({"font.family": "Noto Sans CJK JP", "font.size": 11, "axes.unicode_minus": False})
fig, axes = plt.subplots(4, 2, figsize=(14, 14), constrained_layout=True)
fig.suptitle("B05 · 七族把手设计与抓握参考\n标称尺寸，非仿真资产；绿色＝自由主握段，橙点G＝抓握目标", fontsize=18, fontweight="medium")
for f, ax in zip(families, axes.flat):
    ax.add_patch(Polygon(outline(f), facecolor="#d7dce0", edgecolor="#59666f", linewidth=1))
    ax.add_patch(Polygon(outline(f, *f["free_s"], caps=False), facecolor="#168d83", edgecolor="none", alpha=.86))
    a = np.array(f["points"])
    ax.plot(a[:, 1], a[:, 2], color="#546570", lw=.8, ls="--")
    x, _, z = f["target_xyz"]
    ax.scatter([x], [z], s=65, color="#ed8a27", zorder=8)
    ax.annotate("G", (x, z), (x + 7, z + 20), arrowprops={"arrowstyle": "-", "lw": .7}, color="#674b23")
    ax.scatter([0], [0], s=90, color="#59666f", marker="o", zorder=4)
    ax.text(0, -26, "轴颈", ha="center", color="#59666f", fontsize=10)
    lo, hi = f["free_s"]
    cl, ch = f["centre_s"]
    ax.plot([0, f["arc_length"]], [-44, -44], color="#a3adb3", lw=1)
    ax.plot([lo, hi], [-44, -44], color="#168d83", lw=7, solid_capstyle="butt")
    ax.plot([cl, ch], [-44, -44], color="#ed8a27", lw=4, solid_capstyle="butt")
    ax.text(62, -64, f"自由段 {hi-lo:.1f}  |  中心候选 {ch-cl:.1f}  |  sG {f['target_s']:.1f} mm", ha="center", fontsize=10)
    cx, cz = 185, -4
    idx = len(f["points"]) // 2
    nd, cd = f["points"][idx][3:5]
    if f["section"] == "rounded":
        sec = FancyBboxPatch((cx-nd/2, cz-cd/2), nd, cd, boxstyle=f"round,pad=0,rounding_size={f['corner']}", facecolor="#d7dce0", edgecolor="#59666f")
    else:
        sec = Ellipse((cx, cz), nd, cd, facecolor="#d7dce0", edgecolor="#59666f")
    ax.add_patch(sec)
    ax.text(cx, cz+25, "目标截面 n×c", ha="center", fontsize=10)
    ax.text(cx, cz-28, f"{nd:.0f}×{cd:.0f} mm", ha="center", fontsize=10)
    ax.set_title(f"{f['id']}  {f['name']}     主杆弧长 {f['arc_length']:.1f} mm", loc="left", fontsize=13, fontweight="medium")
    ax.set(xlim=(-20, 210), ylim=(-75, 42), aspect="equal")
    ax.axis("off")
ax = axes.flat[-1]
ax.axis("off")
ax.text(.03, .85, "抓点不是几何包围盒中点", fontsize=16, fontweight="medium", transform=ax.transAxes)
ax.text(.03, .66, "1  标出避开轴颈、过渡、端帽与回钩的主握段\n2  两端各退 31 mm：56 mm指体参照的一半 + 3 mm示意余量\n3  在收缩后的中心候选区取弧长中点 G\n4  G随把手刚体运动；夹爪局部Y闭合、+Z接近", fontsize=11, linespacing=1.55, transform=ax.transAxes, va="top")
ax.text(.03, .03, "F0保留原圆杆量级；其他族是工程候选。\n该包络收缩只是静态选点参照，未验证指垫接触/扫掠净空。\n回钩为独立选项，当前0.5概率是对照，不是新族权重。", fontsize=10, color="#59666f", linespacing=1.6, transform=ax.transAxes)
fig.savefig(OUT / "handle_family_atlas.png", dpi=170, facecolor="white")
fig.savefig(OUT / "handle_family_atlas.svg", facecolor="white")
plt.close(fig)
summary = [{k: f[k] for k in ("id", "name", "arc_length", "free_s", "centre_s", "target_s", "target_xyz", "target_tangent_degrees")} for f in families]
(OUT / "geometry_readout.json").write_text(json.dumps({"evidence": "COMPUTED_NOMINAL_DESIGN", "families": summary}, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
