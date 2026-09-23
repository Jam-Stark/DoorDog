"""Draw two wrist mounting candidates in the original U3 orthographic views.

CPU-only SVG construction from URDF visual triangles. No policy or asset mutation.
The shortened support is a drawing envelope, not a collision-qualified bracket.
"""
from __future__ import annotations

import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import shapely
from scipy.spatial.transform import Rotation
from shapely.geometry import MultiPoint

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PACKAGE = Path(
    "/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103"
    "/camera_setup/Vpiper-Plate-Dual-D435i"
)
sys.path.insert(0, str(PACKAGE / "code"))
from geometry import Robot, VIEWS, apply, corners, project

OUT = HERE / "camera/wrist_comparison_20260911"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
INK, MUTED = "#203b4d", "#647888"
PURPLE, SUPPORT, RGB, DEPTH = "#7854a4", "#b48447", "#c66a30", "#3286b0"
RECTS = [(35, 160, 1145, 675), (1220, 160, 1145, 675),
         (35, 870, 1145, 675), (1220, 870, 1145, 675)]
LABELS = {
    "front": ("前视图 FRONT", "从 +B.X 看向后方；图右 +B.Y，图上 +B.Z"),
    "right": ("右视图 RIGHT", "从 −B.Y 看向左侧；图右 +B.X，图上 +B.Z"),
    "rear": ("后视图 REAR", "从 −B.X 看向前方；图右 −B.Y，图上 +B.Z"),
    "top": ("俯视图 TOP", "从 +B.Z 向下看；图右 +B.X，图上 +B.Y"),
}


def node(parent, tag, **attrs):
    return ET.SubElement(parent, f"{{{NS}}}{tag}", {
        k.replace("_", "-"): str(v) for k, v in attrs.items() if v is not None
    })


def text(parent, x, y, value, size=22, color=INK, bold=False, anchor="start"):
    n = node(parent, "text", x=x, y=y, font_size=size, fill=color,
             font_weight="700" if bold else "400", text_anchor=anchor,
             font_family="Noto Sans CJK SC,Microsoft YaHei,sans-serif")
    n.text = value


def line(parent, a, b, color=INK, width=1.5, dash=None):
    return node(parent, "line", x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                stroke=color, stroke_width=width, stroke_dasharray=dash)


def polygon(parent, pts, color, opacity, width=1.5, dash=None):
    node(parent, "polygon", points=" ".join(f"{x:.4f},{y:.4f}" for x, y in pts),
         fill=color, fill_opacity=opacity, stroke=color, stroke_width=width,
         stroke_dasharray=dash, stroke_linejoin="round")


def outline(triangles, view):
    xy = project(triangles, view) * 1000
    a, b = xy[:, 1] - xy[:, 0], xy[:, 2] - xy[:, 0]
    keep = np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) > 1e-10
    shape = shapely.union_all(shapely.polygons(xy[keep]), grid_size=1e-5)
    shapes = [shape] if shape.geom_type == "Polygon" else list(shape.geoms)
    segments = []
    for poly in shapes:
        if poly.geom_type != "Polygon":
            continue
        for ring in [poly.exterior, *poly.interiors]:
            segments.append("M" + "L".join(f"{x:.6f},{y:.6f}" for x, y in ring.coords) + "Z")
    return "".join(segments)


def candidates(rig, flange):
    camera = next(c for c in rig["cameras"] if c["name"] == "wrist")
    original = np.array(camera["T_parent_M"])
    support = next(b for b in rig["brackets"] if b["name"] == "wrist_camera_support")
    start = np.array(rig["wrist_support_model"]["start_F_m"])
    result = []
    for height, theta in [(180.0, 45.0), (140.0, 38.76)]:
        tm = original.copy()
        if height == 140:
            tm[:3, 3] *= height / 180
            tm[:3, :3] = flange[:3, :3].T @ Rotation.from_euler("y", theta, degrees=True).as_matrix()
            end = tm[:3, 3] + tm[:3, :3] @ [0, 0, -rig["housing_size_M_m"][2] / 2]
            axis = (end - start) / np.linalg.norm(end - start)
            width_axis = tm[:3, 1] - axis * np.dot(tm[:3, 1], axis)
            width_axis /= np.linalg.norm(width_axis)
            ts = np.eye(4)
            ts[:3, :3] = np.column_stack([width_axis, np.cross(axis, width_axis), axis])
            ts[:3, 3] = (start + end) / 2
            size = np.array([0.09, 0.025, np.linalg.norm(end - start)])
        else:
            ts = np.array(support["T_parent_item"])
            size = np.array(support["size_m"])
        bm, bs = flange @ tm, flange @ ts
        bm[:3, 3] -= flange[:3, 3]
        bs[:3, 3] -= flange[:3, 3]
        streams = {}
        for name in ("rgb", "depth"):
            source = camera["streams"][name]
            local = np.linalg.inv(original) @ np.array(source["T_parent_optical"])
            streams[name] = {"T": bm @ local, "fov": source["nominal_fov_deg"]}
        result.append(dict(height=height, theta=theta, T_F_M=tm, T_F_support=ts,
                           T_Brel_M=bm, T_Brel_support=bs, support_size=size,
                           housing=apply(bm, corners(rig["housing_size_M_m"])),
                           support=apply(bs, corners(size)), streams=streams))
    return result


def draw(candidate, meshes, bounds, scale):
    height, theta = candidate["height"], candidate["theta"]
    ident = f"wrist_H{height:g}_F{str(theta).replace('.', 'p')}"
    root = ET.Element(f"{{{NS}}}svg", width="600mm", height="455mm",
                      viewBox="0 0 2400 1820", version="1.1")
    node(root, "title").text = f"腕机 {height:g} mm / {theta:g}° 局部四视图"
    node(root, "desc").text = "Original U3 front/right/rear/top projections; original URDF visual triangles; common reference pose and scale; drawing envelope only."
    defs = node(root, "defs")
    marker = node(defs, "marker", id="arrow", markerWidth=7, markerHeight=7,
                  refX=6, refY=3.5, orient="auto", markerUnits="strokeWidth")
    node(marker, "path", d="M0,0 L7,3.5 L0,7 Z", fill=PURPLE)
    node(root, "rect", x=0, y=0, width=2400, height=1820, fill="white")
    node(root, "rect", x=0, y=0, width=2400, height=125, fill=INK)
    text(root, 42, 56, f"腕机局部四视图  |  {height:g} mm / {theta:g}°", 40, "white", True)
    text(root, 44, 100, "原 U3 观察方向 · 同一参考臂姿态、同一比例 · 外壳中心 M 相对夹爪原点 F", 25, "#dce7ee")
    for view, rect in zip(VIEWS, RECTS):
        x, y, w, h = rect
        lo, hi = bounds[view]
        origin = np.array([x + w / 2 - scale * (lo[0] + hi[0]) / 2,
                           y + 92 + (h - 142) / 2 + scale * (lo[1] + hi[1]) / 2])

        def xy(points):
            return project(np.asarray(points), view) * 1000 * [scale, -scale] + origin

        node(root, "rect", x=x, y=y, width=w, height=h, rx=8, fill="white", stroke="#d1dce3")
        text(root, x + 20, y + 36, LABELS[view][0], 29, bold=True)
        text(root, x + 20, y + 70, LABELS[view][1], 21, MUTED)
        clipid = f"clip_{view}"
        clip = node(defs, "clipPath", id=clipid)
        node(clip, "rect", x=x + 12, y=y + 92, width=w - 24, height=h - 142)
        g = node(root, "g", clip_path=f"url(#{clipid})")
        for i in np.arange(math.ceil(lo[0] / 50) * 50, hi[0] + 1, 50):
            line(g, origin + [i * scale, -lo[1] * scale], origin + [i * scale, -hi[1] * scale], "#e9eef2", 1, "3 7")
        for i in np.arange(math.ceil(lo[1] / 50) * 50, hi[1] + 1, 50):
            line(g, origin + [lo[0] * scale, -i * scale], origin + [hi[0] * scale, -i * scale], "#e9eef2", 1, "3 7")
        # Frusta show nominal geometric directions only; no visibility claim.
        for name, stream in candidate["streams"].items():
            t = stream["T"]
            length = 0.32
            tx, ty = np.tan(np.radians(stream["fov"]) / 2) * length
            end = apply(t, [[-tx, -ty, length], [tx, -ty, length], [tx, ty, length], [-tx, ty, length]])
            cloud = xy(np.vstack([t[:3, 3], end]))
            shape = MultiPoint(cloud).convex_hull
            color = RGB if name == "rgb" else DEPTH
            polygon(g, np.asarray(shape.exterior.coords), color, 0.025, 0.9, "5 8")
        source_group = node(g, "g", transform=f"translate({origin[0]},{origin[1]}) scale({scale},{-scale})")
        for name, paths in meshes.items():
            node(source_group, "path", d=paths[view], fill="#a7bbc8", fill_opacity=.65,
                 stroke="#566f80", stroke_width=1.3, fill_rule="evenodd", vector_effect="non-scaling-stroke")
        for kind, color, opacity in [("support", SUPPORT, .40), ("housing", PURPLE, .85)]:
            shape = MultiPoint(xy(candidate[kind])).convex_hull
            polygon(g, np.asarray(shape.exterior.coords), color, opacity, 2)
        centre3 = candidate["T_Brel_M"][:3, 3]
        centre, f = xy([centre3, [0, 0, 0]])
        node(g, "circle", cx=f[0], cy=f[1], r=5, fill="white", stroke="#2a736b", stroke_width=2)
        text(g, f[0] - 18, f[1] + 30, "F", 23, "#2a736b", True)
        node(g, "circle", cx=centre[0], cy=centre[1], r=5, fill="white", stroke=PURPLE, stroke_width=2)
        text(g, centre[0] - 18, centre[1] - 12, "M", 22, PURPLE, True)
        for name, stream in candidate["streams"].items():
            uv = xy([stream["T"][:3, 3]])[0]
            node(g, "circle", cx=uv[0], cy=uv[1], r=3.5, fill=RGB if name == "rgb" else DEPTH, stroke="white")
        forward = candidate["T_Brel_M"][:3, 0]
        end = xy([centre3 + .15 * forward])[0]
        arrow = line(g, centre, end, PURPLE, 2.5)
        arrow.set("marker-end", "url(#arrow)")
        if view == "right":
            dimx = min(centre[0], f[0]) - 80 * scale
            line(g, f, [dimx - 8, f[1]], MUTED, 1, "4 4")
            line(g, centre, [dimx - 8, centre[1]], MUTED, 1, "4 4")
            line(g, [dimx, f[1]], [dimx, centre[1]], MUTED, 1.7)
            for yy in [f[1], centre[1]]:
                line(g, [dimx - 6, yy], [dimx + 6, yy], MUTED, 2)
            text(g, dimx - 13, (centre[1] + f[1]) / 2, f"{height:g} mm", 26, MUTED, anchor="end")
            line(g, centre, centre + [150 * scale, 0], MUTED, 1.2, "6 5")
            aa = np.linspace(0, math.radians(theta), 45)
            arc = np.column_stack([centre[0] + 62 * scale * np.cos(aa), centre[1] + 62 * scale * np.sin(aa)])
            node(g, "polyline", points=" ".join(f"{a:.3f},{b:.3f}" for a, b in arc), fill="none", stroke=PURPLE, stroke_width=2)
            text(g, centre[0] + 103 * scale, centre[1] + 44 * scale, f"θ = {theta:g}°", 26, PURPLE, True)
            text(g, centre[0] + 135 * scale, centre[1] - 13, "+B.X", 19, MUTED)
        elif view == "front":
            bar_y = centre[1] - 44 * scale
            line(g, [centre[0] - 45 * scale, bar_y], [centre[0] + 45 * scale, bar_y], MUTED)
            for xx in [centre[0] - 45 * scale, centre[0] + 45 * scale]:
                line(g, [xx, bar_y - 6], [xx, bar_y + 6], MUTED)
            text(g, centre[0], bar_y - 12, "外壳横条 90 mm", 23, MUTED, anchor="middle")
        sx, sy = x + 22, y + h - 24
        line(root, [sx, sy], [sx + 100 * scale, sy], INK, 3)
        text(root, sx + 100 * scale + 12, sy + 7, "100 mm", 20, MUTED)
        text(root, x + w - 18, sy + 7, "50 mm 网格 · 零件轮廓半透明叠绘", 19, MUTED, anchor="end")
    t = candidate["T_F_M"]
    pos = ", ".join(f"{v:.6f}" for v in t[:3, 3] * 1000)
    angles = ", ".join(f"{v:.6f}" for v in Rotation.from_matrix(t[:3, :3]).as_euler("xyz", degrees=True))
    text(root, 44, 1600, f"外壳中心：F系 XYZ = [{pos}] mm    RPY = [{angles}]°", 24, bold=True)
    text(root, 44, 1644, "参考臂姿态：[0, 0, 0, 0, 0, 1.57] rad；夹爪关节 ±20 mm。θ 相对参考姿态的机身水平前向。", 24)
    status = "当前90×25mm宽支架包络，沿用源rig" if height == 180 else "候选90×25mm宽支架示意：保留原起端，连接新外壳底面；未验收间隙"
    text(root, 44, 1688, f"{status}。本图高度是 F→M 的参考竖直距离，不是杆长。", 23, MUTED)
    text(root, 44, 1732, "紫色：外壳与前向轴；棕色：支架包络；灰蓝：URDF原始网格；橙/蓝虚线：名义RGB/depth视锥。", 23, MUTED)
    text(root, 44, 1776, "位置/角度示意，非孔位加工图；视锥未作遮挡求交，不代表有效深度。两方案未改变当前训练配置。", 23, MUTED)
    ET.indent(root, space="  ")
    target = OUT / f"{ident}_wrist_detail_four_views.svg"
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
    print(target, flush=True)
    return target


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rig = json.loads((HERE / "camera/U3_F45_B15.json").read_text())
    q = json.loads((PACKAGE / "config/reference_joint_pose.json").read_text())
    robot = Robot(REPO / "gr00t/rl/data/robots/a2_piper_vpiper_final_20260906")
    poses, parts = robot.scene(q)
    flange = poses["arm_body6_to_gripper"]
    selected = [p for p in parts if p.name in {
        "arm_body5", "arm_body6", "arm_body6_to_gripper", "arm_body7", "arm_body8"
    }]
    for part in selected:
        part.vertices = part.vertices - flange[:3, 3]
    variants = candidates(rig, flange)
    cloud = np.concatenate([p.vertices for p in selected] +
                           [c[k] for c in variants for k in ("housing", "support")])
    bounds = {}
    for view in VIEWS:
        pp = project(cloud, view) * 1000
        bounds[view] = (pp.min(0) - [110, 65], pp.max(0) + [165, 85])
    scale = min(min(1080 / (hi[0] - lo[0]), 515 / (hi[1] - lo[1])) for lo, hi in bounds.values())
    meshes = {}
    for part in selected:
        meshes[part.name] = {}
        for view in VIEWS:
            meshes[part.name][view] = outline(part.triangles, view)
        print("Projected original mesh:", part.name, flush=True)
    for candidate in variants:
        draw(candidate, meshes, bounds, scale)
    payload = {
        "source_rig": str(HERE / "camera/U3_F45_B15.json"),
        "source_urdf": str(robot.root / "a2_piper.urdf"),
        "source_views": str(PACKAGE / "code/geometry.py"),
        "views": VIEWS, "reference_joint_pose": q,
        "scale_svg_units_per_mm": scale,
        "status": "DRAWING_ONLY__140MM_SUPPORT_NOT_COLLISION_QUALIFIED",
        "variants": [{k: (v.tolist() if isinstance(v, np.ndarray) else v)
                      for k, v in c.items() if k not in ("housing", "support", "streams")}
                     for c in variants],
    }
    (OUT / "drawing_geometry.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
