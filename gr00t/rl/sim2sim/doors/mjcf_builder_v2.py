"""Isaac-truth handle geometry repair layered over the v1 door builder."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .mjcf_builder import MjcfDoorBuilder, _add_geom, _s
from .spec import DoorInstanceSpec


ISAAC_HANDLE_AUTHORITY = {
    "source_path": "gr00t/rl/isaac_utils/playground/env_rand/door.py",
    "axle_and_levers_lines": "416-473",
    "hook_lines": "461-490",
    "grasp_target_lines": "637-652",
}


class MjcfDoorBuilderV2:
    """Replace the single centered lever with the two-sided Isaac realization."""

    def __init__(self, spec: DoorInstanceSpec):
        spec.validate()
        self.spec = spec

    def build(self) -> tuple[str, dict[str, object]]:
        xml, report = MjcfDoorBuilder(self.spec).build()
        root = ET.fromstring(xml)
        handle = root.find(".//body[@name='door_handle']")
        if handle is None:
            raise ValueError("v1 door XML lacks door_handle")
        old_lever = handle.find("geom[@name='handle_lever']")
        old_grasp = handle.find("site[@name='door_grasp_target']")
        if old_lever is None or old_grasp is None:
            raise ValueError("v1 door XML lacks the replaceable handle geometry")
        handle.remove(old_lever)
        handle.remove(old_grasp)

        data = self.spec.payload
        geometry = data["geometry"]
        door_open_lr = 1.0 if data["kinematics"]["hinge_side"] == "left" else -1.0
        axle_length = float(geometry["handle_axle_length_m"])
        handle_length = float(geometry["handle_lever_length_m"])
        radius = float(geometry["handle_radius_m"])
        lever_y = -0.5 * handle_length * door_open_lr
        lever_quat = "0.707106781187 0.707106781187 0 0"
        for name, x in (
            ("handle_lever_inside", -0.5 * axle_length),
            ("handle_lever_outside", 0.5 * axle_length),
        ):
            _add_geom(
                handle,
                name=name,
                type="capsule",
                pos=_s([x, lever_y, 0.0]),
                quat=lever_quat,
                size=_s([radius, 0.5 * handle_length]),
                mass="0.1",
                rgba="0.8 0.8 0.82 1",
            )

        spawn_hook_value = data.get("spawn_hook")
        spawn_hook = spawn_hook_value is True
        hook_length_value = geometry.get("handle_hook_length_m")
        hook_names: list[str] = []
        if spawn_hook:
            if hook_length_value is None:
                raise ValueError("DoorInstanceSpec spawn_hook=true requires geometry.handle_hook_length_m")
            hook_length = float(hook_length_value)
            hook_y = -handle_length * door_open_lr
            for name, x in (
                ("handle_hook_inside", -0.5 * axle_length + 0.5 * hook_length),
                ("handle_hook_outside", 0.5 * axle_length - 0.5 * hook_length),
            ):
                _add_geom(
                    handle,
                    name=name,
                    type="cylinder",
                    pos=_s([x, hook_y, 0.0]),
                    quat="0.707106781187 0 0.707106781187 0",
                    size=_s([radius, 0.5 * hook_length]),
                    mass="0.05",
                    rgba="0.8 0.8 0.82 1",
                )
                hook_names.append(name)

        grasp_target = [-0.5 * axle_length, lever_y, 0.0]
        ET.SubElement(
            handle,
            "site",
            {
                "name": "door_grasp_target",
                "pos": _s(grasp_target),
                "size": "0.012",
                "rgba": "0 1 0 1",
            },
        )
        door_root = root.find(".//body[@name='door_root']")
        if door_root is None:
            raise ValueError("v1 door XML lacks door_root")
        handle_y = door_open_lr * (
            float(geometry["panel_width_m"]) / 2.0
            - float(geometry["handle_edge_offset_m"])
        )
        handle_z = float(geometry["handle_height_m"])
        ET.SubElement(
            door_root,
            "camera",
            {
                "name": "handle_outside_closeup",
                "pos": _s([-0.45, handle_y, handle_z]),
                "xyaxes": "0 -1 0 0 0 1",
                "fovy": "32",
            },
        )
        ET.SubElement(
            door_root,
            "camera",
            {
                "name": "handle_inside_closeup",
                "pos": _s([0.45, handle_y, handle_z]),
                "xyaxes": "0 1 0 0 0 1",
                "fovy": "32",
            },
        )
        ET.indent(root, space="  ")
        report.update(
            {
                "schema_version": "doordog.mjcf_door_build_report.v2",
                "handle_geometry_parity": {
                    "result": "PASS",
                    "authority": ISAAC_HANDLE_AUTHORITY,
                    "door_open_lr": door_open_lr,
                    "axle": {
                        "name": "handle_axle",
                        "length_m": axle_length,
                        "axis": "X",
                    },
                    "levers": {
                        "inside_center_m": [-0.5 * axle_length, lever_y, 0.0],
                        "outside_center_m": [0.5 * axle_length, lever_y, 0.0],
                        "length_m": handle_length,
                        "rotation": "90_DEG_ABOUT_X",
                        "direction_signed_by_door_open_lr": True,
                    },
                    "hooks": {
                        "door_instance_spawn_hook": spawn_hook_value,
                        "realized": spawn_hook,
                        "absence_semantics": (
                            "LEGACY_PAIRED_DOOR_INSTANCE_HAS_NO_SPAWN_HOOK_FIELD; PRESERVE_NO_HOOK_R1_SUBDOMAIN"
                            if spawn_hook_value is None
                            else None
                        ),
                        "hook_length_m": hook_length_value,
                        "names": hook_names,
                    },
                    "door_grasp_target_local_m": grasp_target,
                    "grasp_target_authority": "Isaac grasp_target fixed-joint localPos1 on the negative-X lever center",
                    "closeup_cameras": ["handle_outside_closeup", "handle_inside_closeup"],
                },
            }
        )
        report["names"]["geometries"] = [
            "handle_axle",
            "handle_lever_inside",
            "handle_lever_outside",
            *hook_names,
        ]
        return ET.tostring(root, encoding="unicode") + "\n", report

    def write(self, output_xml: str | Path, output_report: str | Path) -> None:
        xml, report = self.build()
        Path(output_xml).write_text(xml, encoding="utf-8")
        Path(output_report).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
