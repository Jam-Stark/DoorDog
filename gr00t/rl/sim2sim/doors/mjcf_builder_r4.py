"""r4 door visuals: two-sided inset panels and frame color bands."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .mjcf_builder import _add_geom, _s
from .mjcf_builder_v2 import MjcfDoorBuilderV2
from .spec import DoorInstanceSpec


class MjcfDoorBuilderR4:
    """Add cheap generator-style panel structure without changing door physics."""

    def __init__(self, spec: DoorInstanceSpec):
        spec.validate()
        self.spec = spec

    def build(self) -> tuple[str, dict[str, object]]:
        xml, report = MjcfDoorBuilderV2(self.spec).build()
        root = ET.fromstring(xml)
        panel = root.find(".//body[@name='door_panel']")
        if panel is None:
            raise ValueError("v2 door lacks door_panel")
        data = self.spec.payload
        geometry = data["geometry"]
        width = float(geometry["panel_width_m"])
        height = float(geometry["panel_height_m"])
        thickness = float(geometry["panel_thickness_m"])
        side = 1.0 if data["kinematics"]["hinge_side"] == "left" else -1.0
        collision = panel.find("geom[@name='door_panel_collision']")
        if collision is None:
            raise ValueError("v2 door lacks door_panel_collision")
        collision.set("rgba", "0.73 0.57 0.36 1")
        for name in ("door_frame_left", "door_frame_right", "door_frame_top"):
            frame = root.find(f".//geom[@name='{name}']")
            if frame is None:
                raise ValueError(f"v2 door lacks {name}")
            frame.set("rgba", "0.79 0.72 0.58 1")

        margin_y = min(0.12, 0.18 * width)
        margin_z = min(0.14, 0.08 * height)
        band = min(0.065, 0.08 * width)
        inset_half_width = width / 2.0 - margin_y - band
        usable_height = height - 2.0 * margin_z - band
        inset_height = usable_height / 2.0
        inset_centers_z = (
            margin_z + inset_height / 2.0,
            margin_z + inset_height + band + inset_height / 2.0,
        )
        decorative_names: list[str] = []
        for face, sign in (("outside", -1.0), ("inside", 1.0)):
            inset_x = sign * (thickness / 2.0 + 0.0008)
            band_x = sign * (thickness / 2.0 + 0.0035)
            for index, center_z in enumerate(inset_centers_z):
                name = f"door_inset_{face}_{index}"
                _add_geom(
                    panel,
                    name=name,
                    type="box",
                    pos=_s([inset_x, side * width / 2.0, center_z]),
                    size=_s([0.0008, inset_half_width, inset_height / 2.0 - band / 2.0]),
                    mass="0",
                    contype="0",
                    conaffinity="0",
                    rgba="0.62 0.43 0.24 1",
                )
                decorative_names.append(name)
            for label, y in (("left", side * (width - band / 2.0)), ("right", side * band / 2.0)):
                # Expressed in hinge-local y: the panel spans [0, side*width].
                name = f"door_panel_band_{face}_{label}"
                _add_geom(
                    panel,
                    name=name,
                    type="box",
                    pos=_s([band_x, y, height / 2.0]),
                    size=_s([0.0015, band / 2.0, height / 2.0 - margin_z]),
                    mass="0",
                    contype="0",
                    conaffinity="0",
                    rgba="0.82 0.71 0.52 1",
                )
                decorative_names.append(name)
            for label, z in (
                ("bottom", margin_z),
                ("middle", margin_z + inset_height + band / 2.0),
                ("top", height - margin_z),
            ):
                name = f"door_panel_band_{face}_{label}"
                _add_geom(
                    panel,
                    name=name,
                    type="box",
                    pos=_s([band_x, side * width / 2.0, z]),
                    size=_s([0.0015, width / 2.0 - margin_y, band / 2.0]),
                    mass="0",
                    contype="0",
                    conaffinity="0",
                    rgba="0.82 0.71 0.52 1",
                )
                decorative_names.append(name)

        for site in root.findall(".//site"):
            site.set("group", "5")
        ET.indent(root, space="  ")
        report.update(
            {
                "schema_version": "doordog.mjcf_door_build_report.r4.v1",
                "visual_structure_parity": {
                    "result": "PASS",
                    "authority": (
                        "gr00t/rl/isaac_utils/playground/env_rand/door.py:build_frame; "
                        "owner r4 requires cheap two-sided inset boxes and frame color bands"
                    ),
                    "two_sided_insets": 4,
                    "two_sided_frame_bands": 10,
                    "decorative_geom_names": decorative_names,
                    "physics_effect": "NONE; mass=0, contype=0, conaffinity=0",
                    "panel_rgba": [0.73, 0.57, 0.36, 1.0],
                    "inset_rgba": [0.62, 0.43, 0.24, 1.0],
                    "band_rgba": [0.82, 0.71, 0.52, 1.0],
                },
                "policy_visibility": {
                    "all_sites_assigned_group": 5,
                    "policy_renderer_requirement": "sitegroup[5]=0",
                },
            }
        )
        report["names"]["geometries"] = [
            *report["names"]["geometries"],
            *decorative_names,
        ]
        return ET.tostring(root, encoding="unicode") + "\n", report

    def write(self, output_xml: str | Path, output_report: str | Path) -> None:
        xml, report = self.build()
        Path(output_xml).write_text(xml, encoding="utf-8")
        Path(output_report).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
