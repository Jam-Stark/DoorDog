"""DepthADD v3 door factory and R4-based MuJoCo realization."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from .mjcf_builder import _add_geom, _s
from .mjcf_builder_r4 import MjcfDoorBuilderR4
from .spec import DoorInstanceSpec


def _panel_inertia(mass: float, width: float, height: float, thickness: float) -> list[float]:
    """Box inertia about the panel center in the MJCF body frame (x,y,z)."""
    return [mass * (width * width + height * height) / 12.0, mass * (thickness * thickness + height * height) / 12.0, mass * (thickness * thickness + width * width) / 12.0]


class DepthADDV3DoorFactory:
    """Materialize one new right-hinge/out-opening spec from an experiment case row.

    Required row shape: ``{case_id, door_geometry, door_dynamics_cell}``.  Geometry
    contains the named fields from ``narrowed_door_geometry`` and optional boolean
    ``spawn_hook`` / ``spawn_keyhole``.  The dynamics cell contains the handoff's
    ``damping_native``, ``stiffness_native``, ``max_force_nm`` and optionally
    ``panel_mass_kg``.  No legacy p00 manifest is an input to this factory.
    """

    @classmethod
    def from_case_row(
        cls,
        row: Mapping[str, Any],
        *,
        latch_mode: str = "constraint_gate",
        constraint_gate_release_handle_rad: float | None = None,
    ) -> DoorInstanceSpec:
        geometry = row["door_geometry"]
        cell = row["door_dynamics_cell"]
        case_id = str(row["case_id"])
        width = float(geometry["width_m"])
        height = float(geometry["height_m"])
        mass = float(geometry.get("panel_mass_kg", cell["panel_mass_kg"]))
        thickness = float(geometry.get("panel_thickness_m", 0.04))
        if geometry.get("hinge_side", "right") != "right" or geometry.get("opening_direction", "out") != "out":
            raise ValueError("DepthADD v3 only admits right-hinge/out-opening cases")
        if geometry.get("handle_type", "lever") != "lever":
            raise ValueError("DepthADD v3 only admits lever handles")
        damping = float(cell["damping_native"])
        stiffness = float(cell["stiffness_native"])
        effort = float(cell["max_force_nm"])
        if latch_mode not in {"constraint_gate", "physical_collision", "no_latch"}:
            raise ValueError(f"unsupported DepthADD latch mode {latch_mode!r}")
        release_handle_rad = (
            float(geometry.get("constraint_gate_release_handle_rad", math.pi / 6.0))
            if constraint_gate_release_handle_rad is None
            else float(constraint_gate_release_handle_rad)
        )
        if latch_mode == "constraint_gate" and (
            not math.isfinite(release_handle_rad)
            or not 0.0 < release_handle_rad <= math.pi / 4.0
        ):
            raise ValueError(
                "constraint_gate_release_handle_rad must be finite and in (0, pi/4]"
            )
        requested = {"door_weight_kg": mass, "hinge_damping_native": damping, "hinge_stiffness_native": stiffness, "hinge_effort_limit_nm": effort}
        payload: dict[str, Any] = {"schema_version": "doordog.door_instance.v1", "identity": {"family_id": "a2_depthadd_v3_handoff", "instance_id": case_id, "materialization": "DEPTHADD_V3_EXPERIMENT_CASE_ROW", "source_path": "sim2sim_policy_manifest.yaml + mujoco_randomized_experiment.yaml"}, "frames": {"angular_unit": "rad", "convention": "right_handed_z_up", "quaternion_order": "wxyz"}, "geometry": {"panel_width_m": width, "panel_height_m": height, "panel_thickness_m": thickness, "frame_width_m": float(geometry.get("frame_width_m", 0.05)), "wall_height_m": float(geometry["wall_height_m"]), "wall_total_width_m": 20.0, "handle_axle_length_m": float(geometry["axle_length_m"]), "handle_edge_offset_m": float(geometry["handle_edge_offset_m"]), "handle_height_m": float(geometry["handle_height_m"]), "handle_lever_length_m": float(geometry["handle_length_m"]), "handle_radius_m": float(geometry["handle_radius_m"]), "handle_hook_length_m": float(geometry["hook_length_m"]), "cover_width_m": float(geometry["cover_width_m"]), "keyhole_height_offset_m": float(geometry.get("keyhole_height_offset_m", 0.075))}, "kinematics": {"hinge_axis": [0.0, 0.0, 1.0], "hinge_limits_rad": [0.0, 2.6179938779914944], "handle_axis": [-1.0, 0.0, 0.0], "handle_limits_rad": [0.0, 0.7853981633974483], "hinge_side": "right", "open_direction": "out", "latch_mode": latch_mode, "constraint_gate_release_handle_rad": release_handle_rad if latch_mode == "constraint_gate" else None, "latch_travel_per_handle_rad_m": -0.03819718634205488}, "dynamics": {"panel_mass_kg": mass, "panel_diagonal_inertia_kgm2": _panel_inertia(mass, width, height, thickness), "handle_mass_kg": float(geometry.get("handle_mass_kg", 0.2)), "hinge": {"equilibrium_rad": 0.0, "stiffness_nm_per_rad": stiffness, "damping_nms_per_rad": damping, "effort_cap_nm": effort, "static_friction_effort": 0.0, "dynamic_friction_effort": 0.0, "viscous_friction_coefficient": 0.0}, "handle": {"equilibrium_rad": -math.radians(15.0), "stiffness_nm_per_rad": 50.0, "damping_nms_per_rad": 0.5, "effort_cap_nm": 2.0, "static_friction_effort": 0.0, "dynamic_friction_effort": 0.0, "viscous_friction_coefficient": 0.0}}, "contact": {"geom_friction": list(geometry.get("geom_friction", (1.0, 0.005, 0.0001))), "condim": int(geometry.get("condim", 4)), "restitution": 0.0}, "named_sites": {"door_passage_center": {"position_m": [0.0, 0.0, height / 2.0]}, "door_goal": {"position_m": [1.0, 0.0, height / 2.0]}}, "spawn_hook": bool(geometry.get("hook_enabled", False)), "spawn_keyhole": bool(geometry.get("keyhole_enabled", False)), "visual": {"material_slots": ["frame", "panel", "handle", "frame_surround_wall", "handle_cover"], "renderer_parity": "MUJOCO_HANDOFF_GEOMETRY"}, "backend_overrides": {"isaac_physx": {"mechanics_faces": {"requested_trace_config_rad": requested, "usd_degree_readback": {"door_weight_kg": mass, "hinge_damping_native": damping * 180.0 / math.pi, "hinge_stiffness_native": stiffness * 180.0 / math.pi, "hinge_effort_limit_nm": effort}}}, "mujoco": {"door_resistance_mode": "capped_position_actuator", "handoff_native_mapping": {"damping_native_to_kv": damping, "stiffness_native_to_kp": stiffness, "effort_cap_nm": effort}}}}
        spec = DoorInstanceSpec(payload)
        spec.validate()
        return spec


class DepthADDV3DoorBuilder:
    """Realize the source ``door.py`` visible door topology in MuJoCo."""

    def __init__(self, spec: DoorInstanceSpec):
        spec.validate()
        self.spec = spec

    def build(self) -> tuple[str, dict[str, Any]]:
        xml, report = MjcfDoorBuilderR4(self.spec).build()
        root = ET.fromstring(xml)
        door_root = root.find(".//body[@name='door_root']")
        panel = root.find(".//body[@name='door_panel']")
        if door_root is None or panel is None:
            raise ValueError("R4 door realization lacks required bodies")
        handle = panel.find("body[@name='door_handle']")
        if handle is None:
            raise ValueError("R4 door realization lacks handle body")
        grasp = handle.find("site[@name='door_grasp_target']")
        old_pregrasp = panel.find("site[@name='door_pregrasp_target']")
        if grasp is None or old_pregrasp is None:
            raise ValueError("R4 door realization lacks grasp/pregrasp sites")
        grasp.set("quat", "0.5 0.5 0.5 0.5")
        grasp.set("group", "5")
        panel.remove(old_pregrasp)
        grasp_pos = [float(value) for value in grasp.get("pos", "").split()]
        pregrasp = ET.SubElement(handle, "site", {"name": "door_pregrasp_target", "pos": _s([grasp_pos[0] - 0.10, grasp_pos[1], grasp_pos[2]]), "quat": "0.5 0.5 0.5 0.5", "size": "0.012", "group": "5"})
        marker_groups = {
            "door_grasp_target": int(grasp.get("group", "0")),
            "door_pregrasp_target": int(pregrasp.get("group", "0")),
        }
        if marker_groups != {"door_grasp_target": 5, "door_pregrasp_target": 5}:
            raise ValueError(f"DepthADD target marker group contract violated: {marker_groups}")
        g = self.spec.payload["geometry"]
        width, height, thickness = float(g["panel_width_m"]), float(g["panel_height_m"]), float(g["panel_thickness_m"])
        wall_height = float(g.get("wall_height_m", height + 0.5))
        panel_gap = 0.002
        side = 1.0 if self.spec.payload["kinematics"]["hinge_side"] == "left" else -1.0
        panel_collision = panel.find("geom[@name='door_panel_collision']")
        if panel_collision is None:
            raise ValueError("R4 door realization lacks panel collision geometry")
        panel_collision.set("pos", _s([0.0, side * width / 2.0, height / 2.0]))
        panel_collision.set(
            "size",
            _s([thickness / 2.0, (width - 2.0 * panel_gap) / 2.0, (height - 2.0 * panel_gap) / 2.0]),
        )

        legacy_root_geom_names = {"door_frame_left", "door_frame_right", "door_frame_top"}
        for geom in list(door_root.findall("geom")):
            if geom.get("name") in legacy_root_geom_names:
                door_root.remove(geom)
        legacy_panel_geom_prefixes = ("door_inset_", "door_panel_band_")
        for geom in list(panel.findall("geom")):
            if geom.get("name", "").startswith(legacy_panel_geom_prefixes):
                panel.remove(geom)

        cover_width = float(g["cover_width_m"])
        half_width = width / 2.0
        half_wall_length = (20.0 - width) / 4.0
        source_geometries = (
            (
                "door_cover_top",
                [-0.02, 0.0, height + cover_width / 2.0],
                [0.12, width + 2.0 * cover_width - 2.0 * panel_gap, cover_width],
                "visual",
            ),
            (
                "door_cover_left",
                [-0.02, half_width + cover_width / 2.0 - panel_gap, height / 2.0],
                [0.12, cover_width, height],
                "visual",
            ),
            (
                "door_cover_right",
                [-0.02, -half_width - cover_width / 2.0 + panel_gap, height / 2.0],
                [0.12, cover_width, height],
                "visual",
            ),
            (
                "door_source_frame_left",
                [-0.02, half_wall_length + half_width, wall_height / 2.0],
                [0.10, (20.0 - width) / 2.0, wall_height],
                "collision",
            ),
            (
                "door_source_frame_right",
                [-0.02, -half_wall_length - half_width, wall_height / 2.0],
                [0.10, (20.0 - width) / 2.0, wall_height],
                "collision",
            ),
            (
                "door_source_frame_top",
                [-0.02, 0.0, height + (wall_height - height) / 2.0],
                [0.10, width, wall_height - height],
                "collision",
            ),
        )
        names: list[str] = []
        geometry_receipt: dict[str, dict[str, Any]] = {
            "door_panel_collision": {
                "parent": "door_panel",
                "local_center_m": [0.0, side * width / 2.0, height / 2.0],
                "full_dimensions_m": [thickness, width - 2.0 * panel_gap, height - 2.0 * panel_gap],
                "source": "door.py:382-393 panel_shape_prim",
            }
        }
        for name, pos, full_dimensions, role in source_geometries:
            attrs: dict[str, str] = {
                "name": name,
                "type": "box",
                "pos": _s(pos),
                "size": _s([dimension / 2.0 for dimension in full_dimensions]),
                "mass": "0",
                "rgba": "0.62 0.62 0.60 1",
            }
            if role == "visual":
                attrs.update(contype="0", conaffinity="0")
            _add_geom(door_root, **attrs)
            names.append(name)
            geometry_receipt[name] = {
                "parent": "door_root",
                "local_center_m": pos,
                "full_dimensions_m": full_dimensions,
                "source": (
                    "door.py:335-359 covers"
                    if role == "visual"
                    else "door.py:361-380 broad frame"
                ),
                "role": role,
            }

        if self.spec.payload["spawn_keyhole"]:
            handle_y = side * (width / 2.0 - float(g["handle_edge_offset_m"])) - (-side * width / 2.0)
            offset = float(g.get("keyhole_height_offset_m", 0.075))
            _add_geom(panel, name="keyhole", type="cylinder", pos=_s([thickness / 2.0 + 0.003, handle_y, float(g["handle_height_m"]) - offset]), quat="0.707106781187 0 0.707106781187 0", size="0.008 0.0015", mass="0", contype="0", conaffinity="0", rgba="0.08 0.08 0.08 1")
            names.append("keyhole")
        for geom in door_root.findall(".//geom"):
            if int(geom.get("contype", "1")) != 0:
                if geom.get("name") == "latch_collision":
                    geom.set("contype", "4")
                    geom.set("conaffinity", "2")
                else:
                    geom.set("contype", "2")
                    geom.set("conaffinity", "1")
        report["schema_version"] = "doordog.mjcf_door_build_report.depthadd_v3.v2"
        if report["latch_mode"] != self.spec.payload["kinematics"]["latch_mode"]:
            raise RuntimeError("MJCF latch realization disagrees with the requested latch mode")
        report["visual_structure_parity"] = {
            "result": "SOURCE_TOPOLOGY_REALIZED_PIXEL_PAIR_NOT_RUN",
            "authority": "gr00t/rl/isaac_utils/playground/env_rand/door.py:335-403; 1189-1222",
            "panel": {
                "gap_m": panel_gap,
                "full_dimensions_m": [thickness, width - 2.0 * panel_gap, height - 2.0 * panel_gap],
            },
            "covers": ["door_cover_top", "door_cover_left", "door_cover_right"],
            "broad_frames": [
                "door_source_frame_left",
                "door_source_frame_right",
                "door_source_frame_top",
            ],
            "fixed_panel_subpanels": 0,
            "panel_slats": False,
            "insets": 0,
            "bands": 0,
            "room_walls": False,
        }
        report["handoff_realization"] = {"task_semantics": "right_hinge_out_opening", "latch_mode": self.spec.payload["kinematics"]["latch_mode"], "constraint_gate_release_handle_rad": self.spec.payload["kinematics"]["constraint_gate_release_handle_rad"], "geometry": {"source_authority": "gr00t/rl/isaac_utils/playground/env_rand/door.py:335-403; 593-640; 1189-1222", "panel_gap_m": panel_gap, "room_walls": False, "fixed_panel_subpanels": 0, "panel_slats": False, "legacy_geometries_removed": {"root_frames": sorted(legacy_root_geom_names), "panel_decorations": ["door_inset_* (4)", "door_panel_band_* (10)"], "single_handle_cover": "handle_cover"}, "per_geom": geometry_receipt, "cross_engine_visible_geometry_contract": {"result": "SOURCE_FORMULAS_REALIZED_PIXEL_PAIR_NOT_RUN", "source_panel": "width-2*gap, height-2*gap", "source_covers": "top/left/right from door.py", "source_frames": "three broad frames with wall_total_width=20m", "non_source_room_walls": False}, "hook": bool(self.spec.payload["spawn_hook"]), "keyhole": bool(self.spec.payload["spawn_keyhole"])}, "collision_masks": {"environment": {"contype": 2, "conaffinity": 1}, "physical_latch": {"contype": 4, "conaffinity": 2, "frame_contact_enabled": self.spec.payload["kinematics"]["latch_mode"] == "physical_collision"}, "robot_environment_contact": True, "environment_self_collision": False}, "frames": {"door_grasp_target": {"parent": "door_handle", "rotation_offset_wxyz": [0.5, 0.5, 0.5, 0.5], "final_mjcf_group": marker_groups["door_grasp_target"], "policy_camera_visible": False}, "door_pregrasp_target": {"parent": "door_handle", "relative_to_grasp_local_m": [-0.10, 0.0, 0.0], "rotation_offset_wxyz": [0.5, 0.5, 0.5, 0.5], "final_mjcf_group": marker_groups["door_pregrasp_target"], "policy_camera_visible": False}}, "panel_box_inertia_kgm2": self.spec.payload["dynamics"]["panel_diagonal_inertia_kgm2"], "dynamics_mapping": {"mode": "MuJoCo equivalent mapping", "native_damping_to_capped_position_kv": self.spec.payload["dynamics"]["hinge"]["damping_nms_per_rad"], "native_stiffness_to_capped_position_kp": self.spec.payload["dynamics"]["hinge"]["stiffness_nm_per_rad"], "effort_cap_nm": self.spec.payload["dynamics"]["hinge"]["effort_cap_nm"], "cross_engine_exact_physical_equivalence": "NOT_CLAIMED"}}
        report["names"]["geometries"] = [geom.get("name") for geom in root.findall(".//geom") if geom.get("name")]
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode") + "\n", report

    def write(self, output_xml: str | Path, output_report: str | Path) -> None:
        xml, report = self.build()
        Path(output_xml).write_text(xml)
        Path(output_report).write_text(json.dumps(report, indent=2) + "\n")


__all__ = ["DepthADDV3DoorFactory", "DepthADDV3DoorBuilder"]
