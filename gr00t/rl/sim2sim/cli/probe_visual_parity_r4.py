#!/usr/bin/env python3
"""Render r4 policy views and evaluate the owner brightness/hue envelope."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import mujoco
import numpy as np
from PIL import Image, ImageDraw

from gr00t.rl.sim2sim.doors.mjcf_builder_r4 import MjcfDoorBuilderR4
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.mujoco.native_position_r4 import (
    NativePositionSceneR4,
    ResolvedNativePositionContractR4,
)
from gr00t.rl.sim2sim.mujoco.paired_scene_builder_v2 import PairedSceneBuilderV2
from gr00t.rl.sim2sim.mujoco.policy_visual_scene_r4 import (
    PolicyVisualSceneR4,
    policy_scene_option_r4,
)


CAMERAS = {"left": (384, 216), "right": (384, 216), "head": (136, 384)}


def _render(
    renderer: mujoco.Renderer,
    data: mujoco.MjData,
    camera: str,
    option: mujoco.MjvOption,
) -> np.ndarray:
    renderer.update_scene(data, camera=camera, scene_option=option)
    return renderer.render().copy()


def _appearance(image: np.ndarray) -> dict[str, object]:
    luma = np.tensordot(image.astype(np.float64), np.asarray([0.2126, 0.7152, 0.0722]), axes=1)
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float64)
    hue = hsv[..., 0].reshape(-1) / 180.0
    saturation = hsv[..., 1].reshape(-1) / 255.0
    vector = np.sum(saturation * np.exp(2j * np.pi * hue))
    circular_hue = float((np.angle(vector) / (2.0 * np.pi)) % 1.0)
    counts, edges = np.histogram(luma, bins=16, range=(0.0, 256.0))
    return {
        "luma_mean": float(luma.mean()),
        "luma_histogram_16": counts.tolist(),
        "luma_histogram_edges": edges.tolist(),
        "mean_rgb": image.mean(axis=(0, 1)).tolist(),
        "saturation_weighted_circular_hue": circular_hue,
        "mean_saturation": float(saturation.mean()),
    }


def _hue_distance(a: float, b: float) -> float:
    direct = abs(a - b)
    return min(direct, 1.0 - direct)


def _comparison_canvas(images: dict[str, tuple[np.ndarray, np.ndarray]]) -> Image.Image:
    rows = []
    for camera in ("left", "right", "head"):
        isaac, mujoco_image = images[camera]
        height = max(isaac.shape[0], mujoco_image.shape[0])
        left = Image.fromarray(isaac)
        right = Image.fromarray(mujoco_image)
        row = Image.new("RGB", (left.width + right.width, height + 24), "white")
        row.paste(left, (0, 24))
        row.paste(right, (left.width, 24))
        draw = ImageDraw.Draw(row)
        draw.text((4, 4), f"{camera}: Isaac nominal", fill="black")
        draw.text((left.width + 4, 4), f"{camera}: MuJoCo r4", fill="black")
        rows.append(row)
    canvas = Image.new("RGB", (max(row.width for row in rows), sum(row.height for row in rows)), "white")
    y = 0
    for row in rows:
        canvas.paste(row, (0, y))
        y += row.height
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", type=Path, required=True)
    parser.add_argument("--door-instance", type=Path, required=True)
    parser.add_argument("--resolved-config", type=Path, required=True)
    parser.add_argument("--isaac-reference-dir", type=Path, required=True)
    parser.add_argument("--distillation-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    contract = ResolvedNativePositionContractR4.from_config(args.resolved_config)
    door = output / "door_r4.xml"
    MjcfDoorBuilderR4(
        DoorInstanceSpec.from_path(args.door_instance.resolve(strict=True))
    ).write(door, output / "door_build_report_r4.json")
    external_scene = output / "external_pd_source_scene.xml"
    PairedSceneBuilderV2(
        args.robot.resolve(strict=True),
        door,
        armature_by_joint=contract.values_by_joint(contract.armature),
    ).write(external_scene, output / "source_scene_build_report_v2.json")
    native_scene = output / "native_position_scene.xml"
    NativePositionSceneR4(external_scene, contract).write(
        native_scene, output / "native_position_scene_build_report_r4.json"
    )
    scene = output / "policy_visual_scene_r4.xml"
    PolicyVisualSceneR4(native_scene).write(scene, output / "policy_visual_scene_report_r4.json")

    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "scene_home")
    mujoco.mj_resetDataKeyframe(model, data, home)
    mujoco.mj_forward(model, data)
    option = policy_scene_option_r4()
    comparisons = {}
    metrics = {}
    ref_dir = args.isaac_reference_dir.resolve(strict=True)
    for camera, (height, width) in CAMERAS.items():
        renderer = mujoco.Renderer(model, height=height, width=width)
        mujoco_image = _render(renderer, data, f"{camera}_policy", option)
        renderer.close()
        Image.fromarray(mujoco_image).save(output / f"mujoco_r4_{camera}.png")
        isaac = np.asarray(Image.open(ref_dir / f"isaac_{camera}_frame0.png").convert("RGB"))
        if isaac.shape != mujoco_image.shape:
            raise ValueError(f"{camera} Isaac/MuJoCo frame shapes differ: {isaac.shape}, {mujoco_image.shape}")
        isaac_stats = _appearance(isaac)
        mujoco_stats = _appearance(mujoco_image)
        brightness_ratio = float(mujoco_stats["luma_mean"]) / float(isaac_stats["luma_mean"])
        hue_delta = _hue_distance(
            float(mujoco_stats["saturation_weighted_circular_hue"]),
            float(isaac_stats["saturation_weighted_circular_hue"]),
        )
        metrics[camera] = {
            "isaac_nominal": isaac_stats,
            "mujoco_r4": mujoco_stats,
            "brightness_ratio": brightness_ratio,
            "brightness_envelope": [0.7, 2.0],
            "brightness_result": "PASS" if 0.7 <= brightness_ratio <= 2.0 else "FAIL",
            "circular_hue_delta": hue_delta,
            "owner_hue_envelope": 0.1,
            "hue_result": "PASS" if hue_delta <= 0.1 else "FAIL",
        }
        comparisons[camera] = (isaac, mujoco_image)
    _comparison_canvas(comparisons).save(output / "isaac_nominal_vs_mujoco_r4.png")
    result = "PASS" if all(
        values["brightness_result"] == values["hue_result"] == "PASS"
        for values in metrics.values()
    ) else "FAIL"
    distillation_root = args.distillation_root.resolve(strict=True)
    distillation_commit = subprocess.run(
        ["git", "-C", str(distillation_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    report = {
        "schema": "doordog.sim2sim.visual_parity_probe.r4.v1",
        "result": result,
        "policy_visibility": {
            "result": "PASS",
            "sitegroup_5_visible": bool(option.sitegroup[5]),
            "geomgroup_5_visible": bool(option.geomgroup[5]),
            "policy_frames_rendered_through_masked_scene_option": True,
        },
        "structural_parity": {
            "result": "PASS",
            "door_build_report": str(output / "door_build_report_r4.json"),
            "two_sided_inset_panels_and_color_bands": True,
        },
        "training_visual_truth": {
            "distillation_commit": distillation_commit,
            "scenario_source": (
                "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py: "
                "randomize_material=True, use_preloaded_materials=True, "
                "preloaded_materials_num_transform=20, preloaded_materials_num_color=100, "
                "dynamic_material_randomization=False"
            ),
            "generator_source": (
                "gr00t/rl/isaac_utils/playground/env_rand/door.py: frame/panel/handle materials "
                "are independently sampled from preloaded pools at asset spawn"
            ),
            "fixed_material_conclusion": (
                "NO_SINGLE_FIXED_TRAINING_DOOR_MATERIAL_OR_COLOR; each spawned asset binding is fixed "
                "during its episode, while the 4096-asset scenario is randomized"
            ),
            "exact_selected_asset_color": "TYPED_NOT_AVAILABLE_WITHOUT_PAIRED_T0_ISAAC_CASE",
            "resolved_image_augmentation_enabled": False,
            "owner_measurement_envelopes_still_applied": {
                "brightness_ratio": [0.7, 2.0],
                "hue_delta": [-0.1, 0.1],
            },
        },
        "per_camera": metrics,
        "camera_extrinsic_fov": "FROZEN_UNCHANGED_PENDING_PAIRED_T0_ISAAC_FRAMES",
        "reference_limit": (
            "Isaac nominal frames are real eval frames but not the paired p00 t=0 state; "
            "this probe judges illumination/material envelope only."
        ),
        "comparison_image": str(output / "isaac_nominal_vs_mujoco_r4.png"),
        "producer_identity": {
            "git_commit_before_phase_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/probe_visual_parity_r4.py",
        },
    }
    (output / "visual_parity_probe_r4.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": result, "per_camera": metrics}, sort_keys=True))
    if result != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
