#!/usr/bin/env python3
"""Render the R9 axis-marker probe and an explicit Isaac/MuJoCo basis comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
from OpenGL import GL
from PIL import Image, ImageDraw


COLORS = {"X": (230, 40, 40), "Y": (40, 200, 70), "Z": (40, 90, 235)}


def _reference_panel(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), (245, 245, 242))
    draw = ImageDraw.Draw(image)
    origin = (width // 2, int(height * 0.70))
    draw.text((18, 16), "IsaacLab world camera convention (contract reference)", fill=(25, 25, 25))
    draw.text((18, 36), "+X forward, +Y left, +Z up; wxyz", fill=(45, 45, 45))
    for label, end in (
        ("X", (origin[0] + 105, origin[1] - 70)),
        ("Y", (origin[0] - 105, origin[1] - 45)),
        ("Z", (origin[0], origin[1] - 130)),
    ):
        draw.line((origin, end), fill=COLORS[label], width=9)
        draw.ellipse((end[0] - 7, end[1] - 7, end[0] + 7, end[1] + 7), fill=COLORS[label])
        draw.text((end[0] + 8, end[1] - 8), label, fill=COLORS[label])
    draw.text((18, height - 40), "Algebraic reference, not an Isaac runtime RGB frame", fill=(135, 75, 25))
    return image


def _render(model: mujoco.MjModel, data: mujoco.MjData, camera: str, width: int, height: int) -> tuple[Image.Image, str]:
    renderer = mujoco.Renderer(model, height=height, width=width)
    renderer.update_scene(data, camera=camera)
    pixels = renderer.render()
    gl_renderer = GL.glGetString(GL.GL_RENDERER).decode("utf-8")
    image = Image.fromarray(pixels)
    renderer.close()
    return image, gl_renderer


def _labeled(image: Image.Image, label: str, target_size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", target_size, (22, 22, 24))
    preview = image.copy()
    preview.thumbnail((target_size[0], target_size[1] - 30))
    panel.paste(preview, ((target_size[0] - preview.width) // 2, 25))
    ImageDraw.Draw(panel).text((8, 7), label, fill=(235, 235, 235))
    return panel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    model_path = args.model.resolve(strict=True)
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "home"))
    mujoco.mj_forward(model, data)

    rendered: dict[str, Image.Image] = {}
    renderer_names = set()
    for camera, width, height in (
        ("axis_overview", 640, 480),
        ("left_policy", 216, 384),
        ("right_policy", 216, 384),
        ("head_policy", 384, 136),
    ):
        rendered[camera], gl_name = _render(model, data, camera, width, height)
        renderer_names.add(gl_name)
        rendered[camera].save(output / f"{camera}.png")

    panel_size = (430, 300)
    composite = Image.new("RGB", (panel_size[0] * 2, panel_size[1] * 2), (255, 255, 255))
    composite.paste(_reference_panel(*panel_size), (0, 0))
    composite.paste(_labeled(rendered["axis_overview"], "MuJoCo overview: X red / Y green / Z blue", panel_size), (panel_size[0], 0))
    composite.paste(_labeled(rendered["left_policy"], "MuJoCo left policy camera", panel_size), (0, panel_size[1]))
    right_head = Image.new("RGB", panel_size, (22, 22, 24))
    right_head.paste(_labeled(rendered["right_policy"], "right policy", (215, 300)), (0, 0))
    right_head.paste(_labeled(rendered["head_policy"], "head policy", (215, 300)), (215, 0))
    composite.paste(right_head, (panel_size[0], panel_size[1]))
    comparison = output / "axis_marker_comparison.png"
    composite.save(comparison)

    receipt = {
        "schema": "doordog.sim2sim.axis_marker_probe_receipt.v1",
        "evidence_level": "E1_CAMERA_CONTRACT",
        "result_classification": "VALID_WITH_WARNINGS",
        "model": str(model_path),
        "comparison_image": str(comparison),
        "axis_color_contract": {"X": "red", "Y": "green", "Z": "blue"},
        "source_camera_basis": "IsaacLab world: +X forward, +Y left, +Z up",
        "target_camera_basis": "MuJoCo/OpenGL: -Z forward, +Y up, +X right",
        "conversion": "q_mujoco = q_isaac_world * (0.5,0.5,-0.5,-0.5) wxyz",
        "render_backend": "GLX under Xvfb with LIBGL_ALWAYS_SOFTWARE=1",
        "gl_renderer": sorted(renderer_names),
        "gpu_lease": False,
        "warnings": [
            "Isaac reference panel is the local IsaacLab camera-basis contract, not a runtime Isaac RGB capture.",
            "Pixel/domain parity remains non-comparable until paired Isaac frames exist."
        ]
    }
    (output / "axis_marker_probe_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
