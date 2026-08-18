"""Policy-camera visibility and illumination overlay for r4."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco


def policy_scene_option_r4() -> mujoco.MjvOption:
    option = mujoco.MjvOption()
    option.sitegroup[5] = 0
    option.geomgroup[5] = 0
    return option


class PolicyVisualSceneR4:
    def __init__(self, native_position_scene: Path):
        self.native_position_scene = native_position_scene.resolve(strict=True)

    def write(self, output_scene: Path, output_report: Path) -> None:
        output_scene = output_scene.resolve()
        root = ET.parse(self.native_position_scene).getroot()
        cameras_before = {
            camera.attrib["name"]: dict(camera.attrib)
            for camera in root.findall(".//camera")
            if camera.attrib.get("name") in {"left_policy", "right_policy", "head_policy"}
        }
        for site in root.findall(".//site"):
            site.set("group", "5")
        debug_geoms = []
        for geom in root.findall(".//geom"):
            name = geom.attrib.get("name", "")
            if "debug" in name or "marker" in name or "axis_" in name:
                geom.set("group", "5")
                debug_geoms.append(name)

        skybox = root.find(".//texture[@name='sim2sim_skybox']")
        floor_texture = root.find(".//texture[@name='sim2sim_floor_checker']")
        floor = root.find(".//geom[@name='floor']")
        light = root.find(".//light[@name='key_light']")
        if skybox is None or floor_texture is None or floor is None or light is None:
            raise ValueError("r4 policy visual overlay lacks skybox, floor, or key light")
        skybox.set("rgb1", "0.96 0.97 0.98")
        skybox.set("rgb2", "0.70 0.73 0.78")
        floor_texture.set("rgb1", "0.82 0.80 0.74")
        floor_texture.set("rgb2", "0.94 0.92 0.86")
        floor.set("rgba", "0.90 0.89 0.84 1")
        light.set("ambient", "0.90 0.90 0.90")
        light.set("diffuse", "1.0 1.0 1.0")
        light.set("specular", "0.15 0.15 0.15")

        cameras_after = {
            camera.attrib["name"]: dict(camera.attrib)
            for camera in root.findall(".//camera")
            if camera.attrib.get("name") in {"left_policy", "right_policy", "head_policy"}
        }
        if cameras_after != cameras_before:
            raise RuntimeError("r4 policy visual overlay changed frozen camera extrinsic/FOV metadata")
        ET.indent(root, space="  ")
        output_scene.parent.mkdir(parents=True, exist_ok=True)
        output_scene.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
        model = mujoco.MjModel.from_xml_path(str(output_scene))
        report = {
            "schema": "doordog.sim2sim.policy_visual_scene.r4.v1",
            "result": "PASS",
            "source_scene": str(self.native_position_scene),
            "output_scene": str(output_scene),
            "compiled": {"ngeom": model.ngeom, "nsite": model.nsite, "ncam": model.ncam},
            "policy_visibility": {
                "site_group": 5,
                "policy_option": "sitegroup[5]=0; geomgroup[5]=0",
                "debug_geom_names": debug_geoms,
                "hard_bug_status": "FIXED",
            },
            "illumination_material_overlay": {
                "skybox_rgb1": [0.96, 0.97, 0.98],
                "skybox_rgb2": [0.70, 0.73, 0.78],
                "floor_checker_rgb1": [0.82, 0.80, 0.74],
                "floor_checker_rgb2": [0.94, 0.92, 0.86],
                "key_light_ambient": [0.90, 0.90, 0.90],
                "key_light_diffuse": [1.0, 1.0, 1.0],
            },
            "camera_extrinsic_fov": {
                "status": "FROZEN_UNCHANGED_PENDING_PAIRED_T0_ISAAC_FRAMES",
                "before": cameras_before,
                "after": cameras_after,
            },
        }
        output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
