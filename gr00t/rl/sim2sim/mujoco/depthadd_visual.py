"""DepthADD v3 visual randomization realization for MuJoCo runners.

This module owns procedural visual sampling and scene overlay only.  It does
not replace the frozen r4 visual scene implementation.
"""

from __future__ import annotations

import copy
import math
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np


POLICY_CAMERA_FRAMES = {"left": "left_camera_frame", "right": "right_camera_frame", "head": "head_camera_frame"}
DIAGNOSTIC_CAMERAS = {
    "door_front_pos_x": {"eye_world_m": [4.5, 0.0, 1.025], "lookat_world_m": [0.0, 0.0, 1.025]},
    "door_front_neg_x": {"eye_world_m": [-4.5, 0.0, 1.025], "lookat_world_m": [0.0, 0.0, 1.025]},
}
# MuJoCo cannot consume the 41 Isaac HDRIs or the USD material families.  The
# checker is deliberately kept out of primary rows: it is a MuJoCo-only OOD
# pattern, not a member of the source material family.  It remains available
# only to explicitly labelled OOD stress realizations.
PRIMARY_TEXTURE_POOL = ("procedural_gradient", "procedural_flat")
OOD_TEXTURE_POOL = ("procedural_checker", "procedural_gradient", "procedural_flat")
SURFACE_SELECTORS = {
    "door_frame": ("door_frame", "frame"),
    "door_panel": ("door_panel", "door"),
    "handle": ("handle",),
    "frame_surround_wall": ("wall", "surround"),
    "front_floor": ("floor",),
    "rear_floor": ("rear_floor_visual",),
    "robot": ("trunk", "hip", "thigh", "calf", "arm", "gripper"),
}
_UINT32_PERIOD = 2**32 - 1


# Raw uint8 image-space means from the exact t0 paired render.  They are not
# USD/PBR material parameters: this overlay is a bounded empirical probe for
# the fixed lane only.
_EMPIRICAL_SOURCE_NOMINAL_TARGET_RGB_UINT8 = {
    "background": [236.3, 236.2, 233.9],
    "floor": [143.0, 141.7, 137.3],
    "frame_and_cover": [165.1, 163.5, 159.1],
    "panel": [159.0, 157.4, 153.1],
    "handle": [160.0, 158.5, 154.2],
}
_EMPIRICAL_SOURCE_NOMINAL_GEOMS = {
    "floor": ("floor",),
    "frame_and_cover": (
        "door_cover_top",
        "door_cover_left",
        "door_cover_right",
        "door_source_frame_left",
        "door_source_frame_right",
        "door_source_frame_top",
    ),
    "panel": ("door_panel_collision",),
    "handle": ("handle_axle", "handle_lever_inside", "handle_lever_outside"),
}
_FIXED_NOMINAL_APPEARANCE_FACTORS = (
    "stable_baseline",
    "lighting",
    "background",
    "materials",
    "renderer_color_pipeline",
)
# This is intentionally an empirical pixel-space profile.  The source runtime
# did not expose renderer tone-map/material bindings for authority readback,
# therefore none of these values claims USD, RTX, or PhysX equivalence.
_FIXED_NOMINAL_LIGHTING = {
    "ambient": [1.0, 1.0, 1.0],
    "diffuse": [0.0, 0.0, 0.0],
    "specular": [0.0, 0.0, 0.0],
    "dir": [0.0, 0.0, -1.0],
}
_FIXED_NOMINAL_COLOR_PIPELINE = {
    "formula": "clip(gain * rgb_unit ** gamma + offset, 0, 1)",
    "gain": [1.0, 1.0, 1.0],
    "gamma": [0.95, 0.95, 0.95],
    "offset": [0.015, 0.015, 0.015],
}


# Frozen from the producing DepthADD v3 resolved configuration.  The handoff
# YAML intentionally narrowed several values for the first causal campaign;
# these values define the primary training-equivalent observation contract.
_SOURCE_RGB_AUGMENTATION = {
    "brightness": {"probability": 0.5, "range": [0.5, 2.2]},
    "contrast": {"probability": 0.5, "range": [0.4, 1.8]},
    "hue": {"probability": 0.5, "range": [-0.15, 0.15]},
    "saturation": {"probability": 0.5, "range": [0.3, 2.2]},
    "gaussian_noise": {"probability": 0.5, "std": [0.0, 0.2]},
    "gaussian_blur": {"probability": 0.4, "kernel": [3, 5], "sigma": [0.1, 2.0]},
    "white_balance_temperature_scale": [0.94, 1.06],
    "white_balance_channel_gain": [0.95, 1.05],
}
_SOURCE_DEPTH_AUGMENTATION = {
    "scale": {"probability": 0.4, "range": [0.9, 1.1]},
    "gaussian_noise": {"probability": 0.5, "normalized_std": [0.005, 0.08]},
    "dropout": {"probability": 0.35, "patches": [1, 8], "patch_size_px": [5, 20], "pixel_rate": [0.01, 0.1]},
    "quantization": {"probability": 0.35, "levels": [16, 256]},
    "near_blind_below_m": 0.28,
    "specular_region_dropout": {"probability": 0.25, "regions": [1, 4], "height_fraction": [0.05, 0.25], "width_fraction": [0.05, 0.3]},
    "full_frame_zero_probability": 0.02,
}
_SOURCE_CAMERA = {
    "translation_m": [[-0.005, 0.005]] * 3,
    "rotation_deg": [[-1.5, 1.5]] * 3,
    "focal_scale": [0.98, 1.02],
}


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping, got {type(value).__name__}")
    return value


def _pair(value: object, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a two-element list")
    low, high = float(value[0]), float(value[1])
    if low > high:
        raise ValueError(f"{name} is inverted")
    return low, high


def _uniform(rng: np.random.Generator, value: object, name: str) -> float:
    low, high = _pair(value, name)
    return float(rng.uniform(low, high))


def _event(rng: np.random.Generator, config: Mapping[str, Any], name: str) -> tuple[bool, dict[str, Any]]:
    probability = float(config["probability"])
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"{name}.probability must be in [0, 1]")
    active = bool(rng.random() < probability)
    return active, {"active": active, "probability": probability}


def _frame_seed(seed: int, frame_index: int, domain: int) -> int:
    if frame_index < 0:
        raise ValueError("frame_index must be non-negative")
    return int((int(seed) * 1_000_003 + frame_index * 9_176 + domain * 104_729) % _UINT32_PERIOD)


def _rgba(rng: np.random.Generator) -> list[float]:
    base = rng.uniform(0.18, 0.88, size=3)
    return [float(value) for value in (*base, 1.0)]


def _sample_surface_materials(
    surface_config: Mapping[str, Any],
    rng: np.random.Generator,
    *,
    texture_pool: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    robot_pbr = _mapping(surface_config["robot_pbr"], "surface_material.robot_pbr")
    surfaces = surface_config["surfaces"]
    if not isinstance(surfaces, list):
        raise TypeError("surface_material.surfaces must be a list")
    realized: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        name = str(surface)
        pbr = robot_pbr if name == "robot" else {
            "roughness": [0.10, 0.70],
            "metallic": [0.05, 0.65],
            "specular": [0.10, 0.70],
        }
        roughness = _uniform(rng, pbr["roughness"], f"{name}.roughness")
        metallic = _uniform(rng, pbr["metallic"], f"{name}.metallic")
        specular = _uniform(rng, pbr["specular"], f"{name}.specular")
        realized[name] = {
            "texture": str(texture_pool[int(rng.integers(len(texture_pool)))]),
            "rgba": _rgba(rng),
            "roughness": roughness,
            "metallic": metallic,
            "specular": specular,
            "shininess": float(1.0 - roughness),
            "reflectance": metallic,
            "texrepeat": [float(rng.uniform(0.75, 2.25)), float(rng.uniform(0.75, 2.25))],
        }
    return realized


def _primary_training_equivalent_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return the source-authority subset expressible by this MuJoCo adapter."""
    result = copy.deepcopy(dict(config))
    surface = _mapping(result["surface_material"], "surface_material")
    # In Isaac, door materials redraw at an interval; robot material is reset
    # only.  ``sample_visual_realization`` derives the redraw-only surface set.
    surface["redraw_interval_s"] = [0.9, 1.1]
    surface["robot_pbr"] = {
        "roughness": [0.0, 0.8],
        "metallic": [0.0, 0.8],
        "specular": [0.0, 0.8],
    }
    lighting = _mapping(result["lighting"], "lighting")
    lighting["dome_or_ambient_intensity_equivalent"] = [500.0, 3000.0]
    lighting["environment_yaw_rad"] = [-math.pi, math.pi]
    result["rgb_observation"] = copy.deepcopy(_SOURCE_RGB_AUGMENTATION)
    result["depth_observation"] = copy.deepcopy(_SOURCE_DEPTH_AUGMENTATION)
    camera = _mapping(result["camera"], "camera")
    camera["dual_d435_rigid_translation_jitter_m"] = copy.deepcopy(_SOURCE_CAMERA["translation_m"])
    camera["dual_d435_rigid_rotation_jitter_deg"] = copy.deepcopy(_SOURCE_CAMERA["rotation_deg"])
    camera["head_translation_jitter_m"] = copy.deepcopy(_SOURCE_CAMERA["translation_m"])
    camera["head_rotation_jitter_deg"] = copy.deepcopy(_SOURCE_CAMERA["rotation_deg"])
    camera["focal_scale"] = copy.deepcopy(_SOURCE_CAMERA["focal_scale"])
    return result


def sample_visual_realization(
    visual_config: Mapping[str, Any],
    seed_streams: Mapping[str, int],
    *,
    regime: str,
) -> dict[str, Any]:
    """Sample one episode's visual, lighting, and rigid camera realization.

    ``seed_streams`` must contain the five visual streams generated by
    :mod:`depthadd_v3_experiment`; RGB/depth frame noise remains independent
    through the saved stream seeds.
    """
    required = {"surface_material", "lighting", "camera", "rgb_noise", "depth_noise"}
    missing = required.difference(seed_streams)
    if missing:
        raise KeyError(f"visual seed streams missing {sorted(missing)}")
    if regime not in {"primary_training_equivalent", "ood_stress"}:
        raise ValueError(f"unsupported visual regime {regime!r}")
    configured = _mapping(visual_config, "narrowed_visual_randomization")
    config = (
        _primary_training_equivalent_config(configured)
        if regime == "primary_training_equivalent"
        else copy.deepcopy(dict(configured))
    )
    surface_config = _mapping(config["surface_material"], "surface_material")
    light_config = _mapping(config["lighting"], "lighting")
    camera_config = _mapping(config["camera"], "camera")
    material_rng = np.random.default_rng(int(seed_streams["surface_material"]))
    light_rng = np.random.default_rng(int(seed_streams["lighting"]))
    camera_rng = np.random.default_rng(int(seed_streams["camera"]))

    texture_pool = PRIMARY_TEXTURE_POOL if regime == "primary_training_equivalent" else OOD_TEXTURE_POOL
    redraw_interval_s = _uniform(material_rng, surface_config["redraw_interval_s"], "surface_material.redraw_interval_s")
    realized_surfaces = _sample_surface_materials(
        surface_config,
        material_rng,
        texture_pool=texture_pool,
    )
    redraw_surface_config = copy.deepcopy(dict(surface_config))
    redraw_surface_config["surfaces"] = [
        surface for surface in redraw_surface_config["surfaces"] if str(surface) != "robot"
    ]
    rigid_translation = [_uniform(camera_rng, axis, f"camera.dual_d435_rigid_translation_jitter_m[{index}]") for index, axis in enumerate(camera_config["dual_d435_rigid_translation_jitter_m"])]
    rigid_rotation_deg = [_uniform(camera_rng, axis, f"camera.dual_d435_rigid_rotation_jitter_deg[{index}]") for index, axis in enumerate(camera_config["dual_d435_rigid_rotation_jitter_deg"])]
    head_translation = [_uniform(camera_rng, axis, f"camera.head_translation_jitter_m[{index}]") for index, axis in enumerate(camera_config["head_translation_jitter_m"])]
    head_rotation_deg = [_uniform(camera_rng, axis, f"camera.head_rotation_jitter_deg[{index}]") for index, axis in enumerate(camera_config["head_rotation_jitter_deg"])]
    focal_scale = _uniform(camera_rng, camera_config["focal_scale"], "camera.focal_scale")
    head_focal_scale = _uniform(camera_rng, camera_config["focal_scale"], "camera.focal_scale")
    return {
        "schema": "doordog.sim2sim.depthadd_v3_visual_realization.v1",
        "regime": regime,
        "contract_class": (
            "SOURCE_TRAINING_SUBSET_WITH_EXPLICIT_MUJOCO_RENDER_LIMITS"
            if regime == "primary_training_equivalent"
            else "MUJOCO_OOD_STRESS"
        ),
        "asset_pool": {
            "environment_map_pool": "not_implemented_without_source_hdri_assets",
            "available_procedural_pool": list(texture_pool),
            "hdri_assets": "not_available_in_bundle",
        },
        "surface_materials": realized_surfaces,
        "surface_redraw": {
            "interval_s": redraw_interval_s,
            "seed": int(seed_streams["surface_material"]),
            "config": redraw_surface_config,
            "robot_material_timing": "reset_only",
        },
        "lighting": {
            "dome_or_ambient_intensity_equivalent": _uniform(light_rng, light_config["dome_or_ambient_intensity_equivalent"], "lighting.dome_or_ambient_intensity_equivalent"),
            "environment_yaw_rad": _uniform(light_rng, light_config["environment_yaw_rad"], "lighting.environment_yaw_rad"),
            "motion_blur": (
                {
                    "enabled": False,
                    "authority_status": "DISABLED_PRIMARY_NO_MUJOCO_RTX_EQUIVALENT",
                    "source_config": copy.deepcopy(dict(_mapping(light_config["motion_blur"], "lighting.motion_blur"))),
                }
                if regime == "primary_training_equivalent"
                else {
                    **copy.deepcopy(dict(_mapping(light_config["motion_blur"], "lighting.motion_blur"))),
                    "authority_status": "OOD_MUJOCO_IMAGE_SPACE_APPROXIMATION",
                }
            ),
        },
        "camera": {
            "dual_d435_rigid_translation_jitter_m": rigid_translation,
            "dual_d435_rigid_rotation_jitter_deg": rigid_rotation_deg,
            "head_translation_jitter_m": head_translation,
            "head_rotation_jitter_deg": head_rotation_deg,
            "dual_d435_focal_scale": focal_scale,
            "head_focal_scale": head_focal_scale,
            "preserve_dual_d435_relative_se3": bool(camera_config["preserve_dual_d435_relative_se3"]),
        },
        "augmentation_streams": {"rgb_noise_seed": int(seed_streams["rgb_noise"]), "depth_noise_seed": int(seed_streams["depth_noise"])},
        "config": {
            "rgb_observation": copy.deepcopy(dict(_mapping(config["rgb_observation"], "rgb_observation"))),
            "depth_observation": copy.deepcopy(dict(_mapping(config["depth_observation"], "depth_observation"))),
        },
    }


def apply_stress_visual_overrides(
    realization: Mapping[str, Any], overrides: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply a stress profile directly to a sampled visual realization."""
    result = copy.deepcopy(dict(realization))
    applied = dict(_mapping(overrides, "stress_visual_overrides"))
    if applied.get("mode") == "nominal_visual":
        result["stress_overrides_applied"] = applied
        return result
    if "surface_tint" in applied:
        tint = float(applied["surface_tint"])
        if not 0.0 <= tint <= 1.0:
            raise ValueError("stress surface_tint must be in [0, 1]")
        for values in _mapping(result["surface_materials"], "surface_materials").values():
            surface = _mapping(values, "surface material")
            rgba = list(surface["rgba"])
            surface["rgba"] = [tint, tint, tint, float(rgba[3])]
    lighting = _mapping(result["lighting"], "lighting")
    for field in ("dome_or_ambient_intensity_equivalent", "environment_yaw_rad"):
        if field in applied:
            lighting[field] = float(applied[field])
    endpoint = applied.get("camera_endpoint")
    if endpoint is not None:
        endpoint = _mapping(endpoint, "stress camera_endpoint")
        translation = [float(value) for value in endpoint["translation_m"]]
        rotation = [float(value) for value in endpoint["rotation_deg"]]
        if len(translation) != 3 or len(rotation) != 3:
            raise ValueError("stress camera endpoint must have three translation and rotation values")
        focal_scale = float(endpoint["focal_scale"])
        camera = _mapping(result["camera"], "camera")
        camera["dual_d435_rigid_translation_jitter_m"] = translation
        camera["dual_d435_rigid_rotation_jitter_deg"] = rotation
        camera["head_translation_jitter_m"] = translation.copy()
        camera["head_rotation_jitter_deg"] = rotation.copy()
        camera["dual_d435_focal_scale"] = focal_scale
        camera["head_focal_scale"] = focal_scale
    result["stress_overrides_applied"] = applied
    return result


def sample_surface_redraw(realization: Mapping[str, Any], redraw_index: int) -> dict[str, Any]:
    """Sample one runtime material redraw with an independent deterministic seed."""
    if redraw_index < 0:
        raise ValueError("redraw_index must be non-negative")
    redraw = _mapping(realization["surface_redraw"], "surface_redraw")
    seed = _frame_seed(int(redraw["seed"]), redraw_index, 3)
    materials = _sample_surface_materials(
        _mapping(redraw["config"], "surface_redraw.config"),
        np.random.default_rng(seed),
        texture_pool=tuple(_mapping(realization["asset_pool"], "asset_pool")["available_procedural_pool"]),
    )
    return {
        "schema": "doordog.sim2sim.depthadd_v3_surface_redraw.v1",
        "redraw_index": redraw_index,
        "interval_s": float(redraw["interval_s"]),
        "seed": seed,
        "surface_materials": materials,
    }


def apply_surface_redraw_to_model(model: Any, redraw: Mapping[str, Any]) -> dict[str, Any]:
    """Apply a sampled redraw to MuJoCo material fields and return the actual receipt."""
    import mujoco

    materials = _mapping(redraw["surface_materials"], "surface_redraw.surface_materials")
    rgb_role = mujoco.mjtTextureRole.mjTEXROLE_RGB.value
    receipt: dict[str, Any] = {}
    for surface, values_object in materials.items():
        values = _mapping(values_object, f"surface_redraw.surface_materials.{surface}")
        material_name = f"depthadd_v3_{surface}_material"
        material_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MATERIAL, material_name)
        if material_id < 0:
            raise ValueError(f"model lacks redraw material {material_name}")
        texture_name = f"depthadd_v3_tex_{str(values['texture']).removeprefix('procedural_')}"
        texture_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_TEXTURE, texture_name)
        if texture_id < 0:
            raise ValueError(f"model lacks redraw texture {texture_name}")
        model.mat_rgba[material_id] = np.asarray(values["rgba"], dtype=np.float32)
        model.mat_specular[material_id] = float(values["specular"])
        model.mat_shininess[material_id] = float(values["shininess"])
        model.mat_reflectance[material_id] = float(values["reflectance"])
        model.mat_texrepeat[material_id] = np.asarray(values["texrepeat"], dtype=np.float32)
        model.mat_texid[material_id, rgb_role] = texture_id
        receipt[str(surface)] = {
            "material": material_name,
            "material_id": int(material_id),
            "texture": texture_name,
            "texture_id": int(texture_id),
            "rgba": model.mat_rgba[material_id].tolist(),
            "specular": float(model.mat_specular[material_id]),
            "shininess": float(model.mat_shininess[material_id]),
            "reflectance": float(model.mat_reflectance[material_id]),
            "texrepeat": model.mat_texrepeat[material_id].tolist(),
        }
    return {
        "schema": "doordog.sim2sim.depthadd_v3_surface_redraw_applied.v1",
        "redraw_index": int(redraw["redraw_index"]),
        "interval_s": float(redraw["interval_s"]),
        "surface_materials": receipt,
    }


def _quat_multiply(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array([lw * rw - lx * rx - ly * ry - lz * rz, lw * rx + lx * rw + ly * rz - lz * ry, lw * ry - lx * rz + ly * rw + lz * rx, lw * rz + lx * ry - ly * rx + lz * rw], dtype=np.float64)


def _euler_quat_wxyz(rotation_deg: list[float]) -> np.ndarray:
    roll, pitch, yaw = np.deg2rad(np.asarray(rotation_deg, dtype=np.float64)) / 2.0
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    return np.array([cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy], dtype=np.float64)


def _numbers(text: str | None, count: int, label: str) -> np.ndarray:
    if text is None:
        raise ValueError(f"{label} is absent")
    values = np.fromstring(text, sep=" ", dtype=np.float64)
    if values.size != count:
        raise ValueError(f"{label} has {values.size} values, expected {count}")
    return values


def _fmt(values: np.ndarray | list[float]) -> str:
    return " ".join(f"{float(value):.12g}" for value in values)


def _camera_fovy(fovy_deg: float, focal_scale: float) -> float:
    if focal_scale <= 0.0:
        raise ValueError("focal_scale must be positive")
    return float(math.degrees(2.0 * math.atan(math.tan(math.radians(fovy_deg) / 2.0) / focal_scale)))


def _lookat_xyaxes(eye: list[float], target: list[float]) -> str:
    forward = np.asarray(target, dtype=np.float64) - np.asarray(eye, dtype=np.float64)
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, np.array([0.0, 0.0, 1.0]))
    right /= np.linalg.norm(right)
    up = np.cross(-forward, right)
    return _fmt(np.concatenate((right, up)))


def _ensure_asset(root: ET.Element) -> ET.Element:
    asset = root.find("asset")
    return asset if asset is not None else ET.SubElement(root, "asset")


def _add_procedural_assets(root: ET.Element) -> None:
    asset = _ensure_asset(root)
    existing = {child.get("name") for child in asset}
    definitions = (
        ("depthadd_v3_tex_checker", {"type": "2d", "builtin": "checker", "width": "128", "height": "128", "rgb1": "0.24 0.27 0.31", "rgb2": "0.72 0.68 0.56"}),
        ("depthadd_v3_tex_gradient", {"type": "2d", "builtin": "gradient", "width": "128", "height": "128", "rgb1": "0.20 0.25 0.32", "rgb2": "0.82 0.80 0.71"}),
        ("depthadd_v3_tex_flat", {"type": "2d", "builtin": "flat", "width": "8", "height": "8", "rgb1": "0.55 0.55 0.55", "rgb2": "0.55 0.55 0.55"}),
        ("depthadd_v3_skybox", {"type": "skybox", "builtin": "gradient", "width": "128", "height": "768", "rgb1": "0.15 0.18 0.24", "rgb2": "0.74 0.70 0.60"}),
    )
    for name, attributes in definitions:
        if name not in existing:
            ET.SubElement(asset, "texture", {"name": name, **attributes})


def _surface_geoms(root: ET.Element, surface: str, explicit: Mapping[str, list[str]] | None) -> list[ET.Element]:
    all_geoms = root.findall(".//geom")
    requested = explicit.get(surface) if explicit is not None else None
    if requested is not None:
        names = set(requested)
        selected = [geom for geom in all_geoms if geom.get("name") in names]
        if len(selected) != len(names):
            found = {geom.get("name") for geom in selected}
            raise ValueError(f"surface {surface} geoms missing {sorted(names.difference(found))}")
        return selected
    if surface == "robot":
        trunk = root.find(".//body[@name='trunk']")
        if trunk is None:
            raise ValueError("scene lacks robot trunk body")
        selected = trunk.findall(".//geom")
        for index, geom in enumerate(selected):
            if geom.get("name") is None:
                geom.set("name", f"depthadd_robot_geom_{index:03d}")
    elif surface == "door_frame":
        selected = [geom for geom in all_geoms if geom.get("name", "").startswith("door_frame")]
    elif surface == "door_panel":
        selected = [
            geom
            for geom in all_geoms
            if geom.get("name", "").startswith(("door_panel", "door_inset"))
        ]
    elif surface == "handle":
        selected = [geom for geom in all_geoms if geom.get("name", "").startswith("handle")]
    elif surface == "frame_surround_wall":
        selected = [geom for geom in all_geoms if geom.get("name", "").startswith("wall_surround")]
    elif surface == "front_floor":
        selected = [geom for geom in all_geoms if geom.get("name") == "floor"]
    elif surface == "rear_floor":
        selected = [geom for geom in all_geoms if geom.get("name") == "rear_floor_visual"]
    else:
        raise ValueError(f"unsupported visual surface {surface!r}")
    if not selected:
        raise ValueError(f"surface {surface} has no named geometry; pass surface_geom_names explicitly")
    return selected


def _add_diagnostic_cameras(world: ET.Element) -> dict[str, Any]:
    receipt: dict[str, Any] = {}
    for name, values in DIAGNOSTIC_CAMERAS.items():
        prior = world.find(f"camera[@name='{name}']")
        attributes = {
            "name": name,
            "pos": _fmt(values["eye_world_m"]),
            "xyaxes": _lookat_xyaxes(values["eye_world_m"], values["lookat_world_m"]),
            "fovy": "55",
        }
        if prior is None:
            ET.SubElement(world, "camera", attributes)
        else:
            prior.attrib.update(attributes)
        receipt[name] = {**copy.deepcopy(values), "fovy_deg": 55.0}
    return receipt


def write_depthadd_v3_diagnostic_overlay(source_scene: Path, output_scene: Path) -> dict[str, Any]:
    """Add only world diagnostic cameras to a nominal or randomized scene."""
    source = source_scene.resolve(strict=True)
    root = ET.parse(source).getroot()
    policy_before = {
        camera.attrib["name"]: dict(camera.attrib)
        for camera in root.findall(".//camera")
        if camera.get("name") in {"left_policy", "right_policy", "head_policy"}
    }
    materials_before = {
        material.attrib["name"]: dict(material.attrib) for material in root.findall(".//material")
    }
    world = root.find("worldbody")
    if world is None:
        raise ValueError("scene lacks worldbody")
    diagnostic = _add_diagnostic_cameras(world)
    policy_after = {
        camera.attrib["name"]: dict(camera.attrib)
        for camera in root.findall(".//camera")
        if camera.get("name") in {"left_policy", "right_policy", "head_policy"}
    }
    materials_after = {
        material.attrib["name"]: dict(material.attrib) for material in root.findall(".//material")
    }
    if policy_after != policy_before:
        raise RuntimeError("diagnostic overlay changed policy camera metadata")
    if materials_after != materials_before:
        raise RuntimeError("diagnostic overlay changed material metadata")
    ET.indent(root, space="  ")
    destination = output_scene.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return {
        "schema": "doordog.sim2sim.depthadd_v3_diagnostic_overlay_receipt.v1",
        "source_scene": str(source),
        "output_scene": str(destination),
        "diagnostic_cameras": diagnostic,
        "policy_cameras_unchanged": True,
        "materials_unchanged": True,
    }


def write_depthadd_v3_source_nominal_appearance_calibration(
    source_scene: Path,
    output_scene: Path,
) -> dict[str, Any]:
    """Write the fixed-only empirical t0 appearance calibration scene.

    The source renderer has no runtime material or color-management readback,
    so this stays an image-space diagnostic, not a material/shader equivalence
    claim.  Emissive MuJoCo materials bound the illumination-dependent portion
    of this first causal probe without changing geometry, cameras, physics, or
    policy augmentation.
    """
    source = source_scene.resolve(strict=True)
    root = ET.parse(source).getroot()
    world = root.find("worldbody")
    if world is None:
        raise ValueError("scene lacks worldbody")
    asset = _ensure_asset(root)
    skybox = asset.find("texture[@name='sim2sim_skybox']")
    floor_material = asset.find("material[@name='sim2sim_floor_material']")
    if skybox is None or floor_material is None:
        raise ValueError("source-nominal calibration requires sim2sim skybox and floor material")
    policy_before = {
        camera.attrib["name"]: dict(camera.attrib)
        for camera in root.findall(".//camera")
        if camera.get("name") in {"left_policy", "right_policy", "head_policy"}
    }
    if set(policy_before) != {"left_policy", "right_policy", "head_policy"}:
        raise ValueError("source-nominal calibration requires all three policy cameras")
    target_normalized = {
        name: np.asarray(value, dtype=np.float64) / 255.0
        for name, value in _EMPIRICAL_SOURCE_NOMINAL_TARGET_RGB_UINT8.items()
    }
    skybox.set("rgb1", _fmt(target_normalized["background"]))
    skybox.set("rgb2", _fmt(target_normalized["background"]))
    geoms_by_name = {
        geom.get("name"): geom
        for geom in root.findall(".//geom")
        if geom.get("name") is not None
    }
    material_receipt: dict[str, Any] = {}
    for surface, geom_names in _EMPIRICAL_SOURCE_NOMINAL_GEOMS.items():
        missing = [name for name in geom_names if name not in geoms_by_name]
        if missing:
            raise ValueError(f"source-nominal calibration missing {surface} geoms {missing}")
        material_name = f"depthadd_v3_empirical_nominal_{surface}_material"
        if asset.find(f"material[@name='{material_name}']") is not None:
            raise ValueError(f"source-nominal calibration material already exists: {material_name}")
        rgba = np.concatenate((target_normalized[surface], np.array([1.0])))
        ET.SubElement(
            asset,
            "material",
            {
                "name": material_name,
                "rgba": _fmt(rgba),
                "emission": "1",
                "specular": "0",
                "shininess": "0",
                "reflectance": "0",
            },
        )
        for geom_name in geom_names:
            geoms_by_name[geom_name].set("material", material_name)
        material_receipt[surface] = {
            "material": material_name,
            "rgba": rgba.tolist(),
            "emission": 1.0,
            "specular": 0.0,
            "shininess": 0.0,
            "reflectance": 0.0,
            "geom_names": list(geom_names),
        }
    diagnostic = _add_diagnostic_cameras(world)
    policy_after = {
        camera.attrib["name"]: dict(camera.attrib)
        for camera in root.findall(".//camera")
        if camera.get("name") in {"left_policy", "right_policy", "head_policy"}
    }
    if policy_after != policy_before:
        raise RuntimeError("source-nominal appearance calibration changed policy camera metadata")
    ET.indent(root, space="  ")
    destination = output_scene.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return {
        "schema": "doordog.sim2sim.depthadd_v3.empirical_source_nominal_appearance_calibration.v1",
        "calibration_type": "EMPIRICAL_T0_NOMINAL_APPEARANCE_CALIBRATION",
        "result": "APPLIED",
        "source_scene": str(source),
        "output_scene": str(destination),
        "targets_image_space_raw_rgb_uint8_mean": copy.deepcopy(_EMPIRICAL_SOURCE_NOMINAL_TARGET_RGB_UINT8),
        "actual_mjcf_changes": {
            "skybox": {"texture": "sim2sim_skybox", "rgb1": target_normalized["background"].tolist(), "rgb2": target_normalized["background"].tolist()},
            "replaced_floor_material": "sim2sim_floor_material",
            "emissive_materials": material_receipt,
        },
        "diagnostic_cameras": diagnostic,
        "policy_cameras_unchanged": True,
        "limitations": [
            "UNRESOLVED_RENDERER_APPEARANCE",
            "image-space target means are not source material, shader, light, tone-map, or color-management authority",
            "this overlay is fixed-only and must not characterize visual randomization or OOD stress",
            "robot appearance is intentionally unchanged because its t0 pixel share is negligible in the paired audit",
        ],
    }


def fixed_nominal_appearance_factor_names() -> tuple[str, ...]:
    """Return the fixed-only appearance ablation names accepted by the evaluator."""
    return _FIXED_NOMINAL_APPEARANCE_FACTORS


def _policy_camera_attributes(root: ET.Element) -> dict[str, dict[str, str]]:
    cameras = {
        camera.attrib["name"]: dict(camera.attrib)
        for camera in root.findall(".//camera")
        if camera.get("name") in {"left_policy", "right_policy", "head_policy"}
    }
    if set(cameras) != {"left_policy", "right_policy", "head_policy"}:
        raise ValueError("scene lacks one or more policy cameras")
    return cameras


def _attribute_snapshot(element: ET.Element, *, label: str) -> dict[str, str]:
    if element is None:
        raise ValueError(f"scene lacks {label}")
    return dict(element.attrib)


def write_depthadd_v3_fixed_nominal_appearance_factor(
    source_scene: Path,
    output_scene: Path,
    *,
    factor: str,
) -> dict[str, Any]:
    """Write one controlled fixed-nominal appearance ablation scene.

    ``stable_baseline`` applies all four empirical factors.  Each other value
    withholds exactly that named factor from the same baseline while preserving
    the other three.  Geometry, cameras, marker groups, physics, depth, and
    visual augmentation are deliberately outside this interface.
    """
    if factor not in _FIXED_NOMINAL_APPEARANCE_FACTORS:
        raise ValueError(
            f"unsupported fixed nominal appearance factor {factor!r}; "
            f"expected one of {_FIXED_NOMINAL_APPEARANCE_FACTORS}"
        )
    source = source_scene.resolve(strict=True)
    root = ET.parse(source).getroot()
    asset = _ensure_asset(root)
    world = root.find("worldbody")
    if world is None:
        raise ValueError("scene lacks worldbody")
    policy_before = _policy_camera_attributes(root)
    skybox = asset.find("texture[@name='sim2sim_skybox']")
    floor_material = asset.find("material[@name='sim2sim_floor_material']")
    key_light = world.find("light[@name='key_light']")
    skybox_before = _attribute_snapshot(skybox, label="sim2sim skybox")
    floor_before = _attribute_snapshot(floor_material, label="sim2sim floor material")
    light_before = _attribute_snapshot(key_light, label="key_light")
    geoms_by_name = {
        geom.get("name"): geom
        for geom in root.findall(".//geom")
        if geom.get("name") is not None
    }
    target_normalized = {
        name: np.asarray(value, dtype=np.float64) / 255.0
        for name, value in _EMPIRICAL_SOURCE_NOMINAL_TARGET_RGB_UINT8.items()
    }
    withheld = None if factor == "stable_baseline" else factor
    applied = {
        name: name != withheld
        for name in ("lighting", "background", "materials", "renderer_color_pipeline")
    }
    realized: dict[str, Any] = {}
    if applied["background"]:
        skybox.set("rgb1", _fmt(target_normalized["background"]))
        skybox.set("rgb2", _fmt(target_normalized["background"]))
    realized["background"] = {
        "intended": {
            "texture": "sim2sim_skybox",
            "rgb1": target_normalized["background"].tolist(),
            "rgb2": target_normalized["background"].tolist(),
        },
        "realized": _attribute_snapshot(skybox, label="sim2sim skybox"),
        "source": "EMPIRICAL_TARGET" if applied["background"] else "MUJOCO_BASE_SCENE",
    }
    if applied["lighting"]:
        for name, values in _FIXED_NOMINAL_LIGHTING.items():
            key_light.set(name, _fmt(values))
    realized["lighting"] = {
        "intended": copy.deepcopy(_FIXED_NOMINAL_LIGHTING),
        "realized": _attribute_snapshot(key_light, label="key_light"),
        "source": "EMPIRICAL_TARGET" if applied["lighting"] else "MUJOCO_BASE_SCENE",
        "base_scene": light_before,
    }
    material_receipt: dict[str, Any] = {}
    if applied["materials"]:
        # A factor-separable profile cannot use the legacy emission=1 shortcut:
        # that would make the lighting ablation physically meaningless.
        floor_rgba = np.concatenate((target_normalized["floor"], np.array([1.0])))
        floor_material.attrib.clear()
        floor_material.attrib.update(
            {
                "name": "sim2sim_floor_material",
                "rgba": _fmt(floor_rgba),
                "specular": "0",
                "shininess": "0",
                "reflectance": "0",
                "emission": "0",
            }
        )
        material_receipt["floor"] = {
            "material": "sim2sim_floor_material",
            "rgba": floor_rgba.tolist(),
            "emission": 0.0,
            "geom_names": ["floor"],
        }
        for surface, geom_names in _EMPIRICAL_SOURCE_NOMINAL_GEOMS.items():
            if surface == "floor":
                continue
            missing = [name for name in geom_names if name not in geoms_by_name]
            if missing:
                raise ValueError(f"fixed nominal appearance missing {surface} geoms {missing}")
            material_name = f"depthadd_v3_fixed_nominal_{surface}_material"
            if asset.find(f"material[@name='{material_name}']") is not None:
                raise ValueError(f"fixed nominal appearance material already exists: {material_name}")
            rgba = np.concatenate((target_normalized[surface], np.array([1.0])))
            ET.SubElement(
                asset,
                "material",
                {
                    "name": material_name,
                    "rgba": _fmt(rgba),
                    "emission": "0",
                    "specular": "0",
                    "shininess": "0",
                    "reflectance": "0",
                },
            )
            for geom_name in geom_names:
                geoms_by_name[geom_name].set("material", material_name)
            material_receipt[surface] = {
                "material": material_name,
                "rgba": rgba.tolist(),
                "emission": 0.0,
                "geom_names": list(geom_names),
            }
    realized["materials"] = {
        "intended_targets_raw_rgb_uint8_mean": {
            name: _EMPIRICAL_SOURCE_NOMINAL_TARGET_RGB_UINT8[name]
            for name in ("floor", "frame_and_cover", "panel", "handle")
        },
        "realized": material_receipt if applied["materials"] else {"floor_material": floor_before},
        "source": "EMPIRICAL_TARGET" if applied["materials"] else "MUJOCO_BASE_SCENE",
    }
    color_pipeline = {
        "enabled": bool(applied["renderer_color_pipeline"]),
        "intended": copy.deepcopy(_FIXED_NOMINAL_COLOR_PIPELINE),
        "source": "EMPIRICAL_IMAGE_SPACE" if applied["renderer_color_pipeline"] else "IDENTITY_MUJOCO_RENDERER_RGB",
        "order": "raw_renderer_rgb_uint8 -> fixed_nominal_color_pipeline -> visual_augmentation -> policy_rgb",
        "applies_to": ["left_policy_rgb", "right_policy_rgb", "head_policy_rgb"],
        "depth_unchanged": True,
    }
    diagnostic = _add_diagnostic_cameras(world)
    policy_after = _policy_camera_attributes(root)
    if policy_after != policy_before:
        raise RuntimeError("fixed nominal appearance factor changed policy camera metadata")
    ET.indent(root, space="  ")
    destination = output_scene.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return {
        "schema": "doordog.sim2sim.depthadd_v3.fixed_nominal_appearance_factor.v1",
        "profile": "EMPIRICAL_FACTOR_SEPARABLE_FIXED_NOMINAL",
        "result": "APPLIED",
        "source_scene": str(source),
        "output_scene": str(destination),
        "factor_requested": factor,
        "factor_semantics": "stable_baseline applies all four factors; named factor lanes withhold exactly that factor",
        "withheld_factor": withheld,
        "applied_factors": applied,
        "factor_realization": realized,
        "color_pipeline": color_pipeline,
        "targets_image_space_raw_rgb_uint8_mean": copy.deepcopy(_EMPIRICAL_SOURCE_NOMINAL_TARGET_RGB_UINT8),
        "diagnostic_cameras": diagnostic,
        "policy_cameras_unchanged": True,
        "geometry_unchanged": True,
        "marker_group5_unchanged": True,
        "physics_unchanged": True,
        "depth_unchanged": True,
        "visual_augmentation_unchanged": True,
        "limitations": [
            "UNRESOLVED_RENDERER_APPEARANCE",
            "this is an empirical fixed-nominal calibration, not Isaac USD/PBR/RTX/tone-map/color-management equivalence",
            "the renderer color pipeline is an explicit post-render RGB approximation; it never modifies depth",
            "this interface is fixed-only and must not characterize visual_only, combined, or OOD stress",
        ],
    }


def apply_fixed_nominal_color_pipeline(
    rgb: np.ndarray,
    pipeline: Mapping[str, Any] | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply the explicit fixed-nominal RGB-only post-render approximation."""
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[-1] != 3:
        raise ValueError(f"expected uint8 HWC RGB, got dtype={rgb.dtype} shape={rgb.shape}")
    if pipeline is None or not bool(pipeline.get("enabled", False)):
        return rgb.copy(), {
            "enabled": False,
            "formula": "identity",
            "depth_unchanged": True,
        }
    intended = _mapping(pipeline.get("intended"), "fixed nominal color pipeline intended")
    gain = np.asarray(intended["gain"], dtype=np.float64)
    gamma = np.asarray(intended["gamma"], dtype=np.float64)
    offset = np.asarray(intended["offset"], dtype=np.float64)
    if gain.shape != (3,) or gamma.shape != (3,) or offset.shape != (3,):
        raise ValueError("fixed nominal color pipeline requires three-channel gain/gamma/offset")
    if np.any(gain < 0.0) or np.any(gamma <= 0.0):
        raise ValueError("fixed nominal color pipeline gain must be non-negative and gamma positive")
    transformed = np.clip(gain * (rgb.astype(np.float32) / 255.0) ** gamma + offset, 0.0, 1.0)
    return np.rint(transformed * 255.0).astype(np.uint8), {
        "enabled": True,
        "formula": str(intended["formula"]),
        "gain": gain.tolist(),
        "gamma": gamma.tolist(),
        "offset": offset.tolist(),
        "depth_unchanged": True,
    }


def write_depthadd_v3_visual_overlay(
    source_scene: Path,
    output_scene: Path,
    realization: Mapping[str, Any],
    *,
    surface_geom_names: Mapping[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Write an additive procedural scene overlay and its realized receipt."""
    source = source_scene.resolve(strict=True)
    root = ET.parse(source).getroot()
    _add_procedural_assets(root)
    asset = _ensure_asset(root)
    world = root.find("worldbody")
    if world is None:
        raise ValueError("scene lacks worldbody")
    if world.find("geom[@name='rear_floor_visual']") is None:
        ET.SubElement(
            world,
            "geom",
            {
                "name": "rear_floor_visual",
                "type": "box",
                "pos": "2.5 0 -0.001",
                "size": "1.5 4 0.001",
                "contype": "0",
                "conaffinity": "0",
                "mass": "0",
            },
        )
    material_receipt: dict[str, Any] = {}
    for surface, values_object in _mapping(realization["surface_materials"], "realization.surface_materials").items():
        values = _mapping(values_object, f"surface_materials.{surface}")
        texture_name = f"depthadd_v3_tex_{values['texture'].removeprefix('procedural_')}"
        material_name = f"depthadd_v3_{surface}_material"
        material = asset.find(f"material[@name='{material_name}']")
        attributes = {"name": material_name, "texture": texture_name, "rgba": _fmt(values["rgba"]), "specular": f"{float(values['specular']):.12g}", "shininess": f"{float(values['shininess']):.12g}", "reflectance": f"{float(values['reflectance']):.12g}", "texrepeat": _fmt(values["texrepeat"])}
        if material is None:
            material = ET.SubElement(asset, "material", attributes)
        else:
            material.attrib.update(attributes)
        geoms = _surface_geoms(root, str(surface), surface_geom_names)
        for geom in geoms:
            geom.set("material", material_name)
        material_receipt[str(surface)] = {**dict(values), "material": material_name, "geom_names": [geom.get("name") for geom in geoms]}

    light = root.find(".//light[@name='key_light']")
    if light is None:
        light = ET.SubElement(world, "light", {"name": "key_light", "pos": "0 0 3", "dir": "0 0 -1"})
    light_values = _mapping(realization["lighting"], "realization.lighting")
    intensity = float(light_values["dome_or_ambient_intensity_equivalent"])
    light.set("ambient", _fmt([intensity / 2400.0] * 3))
    light.set("diffuse", _fmt([intensity / 1600.0] * 3))
    light.set("specular", "0.2 0.2 0.2")
    yaw = float(light_values["environment_yaw_rad"])
    light.set("dir", _fmt([-math.cos(yaw), -math.sin(yaw), -1.0]))

    camera_values = _mapping(realization["camera"], "realization.camera")
    camera_receipt: dict[str, Any] = {}
    for name, frame_name in POLICY_CAMERA_FRAMES.items():
        frame = root.find(f".//body[@name='{frame_name}']")
        if frame is None:
            raise ValueError(f"scene lacks policy camera frame {frame_name}")
        translation = camera_values["dual_d435_rigid_translation_jitter_m"] if name in {"left", "right"} else camera_values["head_translation_jitter_m"]
        rotation = camera_values["dual_d435_rigid_rotation_jitter_deg"] if name in {"left", "right"} else camera_values["head_rotation_jitter_deg"]
        position_before = _numbers(frame.get("pos"), 3, f"{frame_name}.pos")
        quat_before = _numbers(frame.get("quat"), 4, f"{frame_name}.quat")
        position_after = position_before + np.asarray(translation, dtype=np.float64)
        quat_after = _quat_multiply(_euler_quat_wxyz(list(rotation)), quat_before)
        quat_after /= np.linalg.norm(quat_after)
        frame.set("pos", _fmt(position_after))
        frame.set("quat", _fmt(quat_after))
        camera = frame.find(f"camera[@name='{name}_policy']")
        if camera is None:
            raise ValueError(f"scene lacks camera {name}_policy under {frame_name}")
        focal_scale = float(camera_values["dual_d435_focal_scale"] if name in {"left", "right"} else camera_values["head_focal_scale"])
        fovy_before = float(camera.get("fovy"))
        fovy_after = _camera_fovy(fovy_before, focal_scale)
        camera.set("fovy", f"{fovy_after:.12g}")
        camera_receipt[name] = {"frame": frame_name, "position_before_m": position_before.tolist(), "position_after_m": position_after.tolist(), "quaternion_before_wxyz": quat_before.tolist(), "quaternion_after_wxyz": quat_after.tolist(), "fovy_before_deg": fovy_before, "fovy_after_deg": fovy_after, "focal_scale": focal_scale}

    diagnostic_cameras = _add_diagnostic_cameras(world)

    ET.indent(root, space="  ")
    destination = output_scene.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return {"schema": "doordog.sim2sim.depthadd_v3_visual_overlay_receipt.v1", "source_scene": str(source), "output_scene": str(destination), "asset_pool": dict(_mapping(realization["asset_pool"], "realization.asset_pool")), "surface_materials": material_receipt, "lighting": dict(light_values), "policy_cameras": camera_receipt, "diagnostic_cameras": diagnostic_cameras}


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    maximum = rgb.max(axis=-1)
    minimum = rgb.min(axis=-1)
    delta = maximum - minimum
    hsv = np.empty_like(rgb)
    hsv[..., 2] = maximum
    hsv[..., 1] = np.divide(delta, maximum, out=np.zeros_like(delta), where=maximum > 0)
    hue = np.zeros_like(maximum)
    nonzero = delta > 0
    red = nonzero & (maximum == rgb[..., 0])
    green = nonzero & (maximum == rgb[..., 1])
    blue = nonzero & (maximum == rgb[..., 2])
    hue[red] = ((rgb[..., 1][red] - rgb[..., 2][red]) / delta[red]) % 6.0
    hue[green] = (rgb[..., 2][green] - rgb[..., 0][green]) / delta[green] + 2.0
    hue[blue] = (rgb[..., 0][blue] - rgb[..., 1][blue]) / delta[blue] + 4.0
    hsv[..., 0] = hue / 6.0
    return hsv


def _hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    h, saturation, value = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    sector = np.floor(h * 6.0).astype(np.int32) % 6
    fraction = h * 6.0 - np.floor(h * 6.0)
    p, q, t = value * (1.0 - saturation), value * (1.0 - fraction * saturation), value * (1.0 - (1.0 - fraction) * saturation)
    candidates = np.stack((np.stack((value, t, p), axis=-1), np.stack((q, value, p), axis=-1), np.stack((p, value, t), axis=-1), np.stack((p, q, value), axis=-1), np.stack((t, p, value), axis=-1), np.stack((value, p, q), axis=-1)), axis=0)
    return np.take_along_axis(candidates, sector[None, ..., None], axis=0)[0]


def _box_blur(rgb: np.ndarray, kernel: int) -> np.ndarray:
    radius = kernel // 2
    padded = np.pad(rgb, ((radius, radius), (radius, radius), (0, 0)), mode="edge")
    result = np.zeros_like(rgb)
    for y in range(kernel):
        for x in range(kernel):
            result += padded[y : y + rgb.shape[0], x : x + rgb.shape[1]]
    return result / float(kernel * kernel)


def _motion_blur(
    rgb: np.ndarray,
    *,
    samples: int,
    diameter_px: float,
    angle_rad: float,
) -> np.ndarray:
    if samples <= 1 or diameter_px <= 0.0:
        return rgb
    radius = max(1, int(math.ceil(diameter_px / 2.0)))
    padded = np.pad(rgb, ((radius, radius), (radius, radius), (0, 0)), mode="edge")
    result = np.zeros_like(rgb)
    for offset in np.linspace(-diameter_px / 2.0, diameter_px / 2.0, samples):
        dx = int(round(math.cos(angle_rad) * offset))
        dy = int(round(math.sin(angle_rad) * offset))
        y0 = radius + dy
        x0 = radius + dx
        result += padded[y0 : y0 + rgb.shape[0], x0 : x0 + rgb.shape[1]]
    return result / float(samples)


def augment_rgb_frame(rgb: np.ndarray, realization: Mapping[str, Any], frame_index: int) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply a recorded per-frame RGB augmentation and return float32 [0,1] RGB."""
    image = np.asarray(rgb)
    if image.ndim != 3 or image.shape[-1] != 3:
        raise ValueError(f"RGB frame must be HxWx3, got {image.shape}")
    if image.dtype == np.uint8:
        result = image.astype(np.float32) / 255.0
    else:
        result = image.astype(np.float32, copy=True)
    if not np.isfinite(result).all() or result.min() < 0.0 or result.max() > 1.0:
        raise ValueError("RGB frame must contain finite values in [0, 1]")
    config = _mapping(_mapping(realization["config"], "realization.config")["rgb_observation"], "rgb_observation")
    seed = _mapping(realization["augmentation_streams"], "augmentation_streams")["rgb_noise_seed"]
    rng = np.random.default_rng(_frame_seed(int(seed), frame_index, 1))
    receipt: dict[str, Any] = {"frame_index": frame_index}
    brightness_active, brightness = _event(rng, _mapping(config["brightness"], "rgb.brightness"), "rgb.brightness")
    if brightness_active:
        brightness["value"] = _uniform(rng, config["brightness"]["range"], "rgb.brightness.range")
        result *= brightness["value"]
    receipt["brightness"] = brightness
    contrast_active, contrast = _event(rng, _mapping(config["contrast"], "rgb.contrast"), "rgb.contrast")
    if contrast_active:
        contrast["value"] = _uniform(rng, config["contrast"]["range"], "rgb.contrast.range")
        result = (result - result.mean(axis=(0, 1), keepdims=True)) * contrast["value"] + result.mean(axis=(0, 1), keepdims=True)
    receipt["contrast"] = contrast
    hue_active, hue = _event(rng, _mapping(config["hue"], "rgb.hue"), "rgb.hue")
    saturation_active, saturation = _event(rng, _mapping(config["saturation"], "rgb.saturation"), "rgb.saturation")
    if hue_active or saturation_active:
        hsv = _rgb_to_hsv(np.clip(result, 0.0, 1.0))
        if hue_active:
            hue["value"] = _uniform(rng, config["hue"]["range"], "rgb.hue.range")
            hsv[..., 0] = (hsv[..., 0] + hue["value"]) % 1.0
        if saturation_active:
            saturation["value"] = _uniform(rng, config["saturation"]["range"], "rgb.saturation.range")
            hsv[..., 1] = np.clip(hsv[..., 1] * saturation["value"], 0.0, 1.0)
        result = _hsv_to_rgb(hsv)
    receipt["hue"], receipt["saturation"] = hue, saturation
    temp = _uniform(rng, config["white_balance_temperature_scale"], "rgb.white_balance_temperature_scale")
    channel_gain = np.array([_uniform(rng, config["white_balance_channel_gain"], "rgb.white_balance_channel_gain") for _ in range(3)], dtype=np.float32)
    gains = np.array([temp, 1.0, 2.0 - temp], dtype=np.float32) * channel_gain
    # Isaac's auto white balance preserves mean channel gain after applying
    # temperature and per-channel factors.  Without this, MuJoCo turns white
    # balance into an unintended brightness augmentation.
    gains /= float(gains.mean())
    result *= gains
    receipt["white_balance_temperature_scale"] = temp
    receipt["white_balance_channel_gain"] = channel_gain.tolist()
    receipt["white_balance_effective_gain"] = gains.tolist()
    receipt["white_balance_mean_normalized"] = True
    noise_active, noise = _event(rng, _mapping(config["gaussian_noise"], "rgb.gaussian_noise"), "rgb.gaussian_noise")
    if noise_active:
        noise["std"] = _uniform(rng, config["gaussian_noise"]["std"], "rgb.gaussian_noise.std")
        result += rng.normal(0.0, noise["std"], size=result.shape).astype(np.float32)
    receipt["gaussian_noise"] = noise
    blur_active, blur = _event(rng, _mapping(config["gaussian_blur"], "rgb.gaussian_blur"), "rgb.gaussian_blur")
    if blur_active:
        kernels = config["gaussian_blur"]["kernel"]
        if not isinstance(kernels, list) or not kernels:
            raise ValueError("rgb.gaussian_blur.kernel must be a non-empty list")
        blur["kernel"] = int(kernels[int(rng.integers(len(kernels)))])
        blur["sigma"] = _uniform(rng, config["gaussian_blur"]["sigma"], "rgb.gaussian_blur.sigma")
        result = _box_blur(result, blur["kernel"])
    receipt["gaussian_blur"] = blur
    motion = _mapping(
        _mapping(realization["lighting"], "realization.lighting")["motion_blur"],
        "lighting.motion_blur",
    )
    if bool(motion["enabled"]):
        samples = int(motion["samples"])
        diameter_px = (
            float(motion["max_blur_diameter_fraction"])
            * min(result.shape[0], result.shape[1])
            * float(motion["exposure_fraction"])
        )
        angle_rad = float(rng.uniform(-math.pi, math.pi))
        result = _motion_blur(
            result,
            samples=samples,
            diameter_px=diameter_px,
            angle_rad=angle_rad,
        )
        receipt["motion_blur"] = {
            "mode": "MUJOCO_OOD_IMAGE_SPACE_APPROXIMATION",
            "authority_status": str(motion["authority_status"]),
            "samples": samples,
            "diameter_px": diameter_px,
            "angle_rad": angle_rad,
        }
    else:
        receipt["motion_blur"] = {
            "mode": "disabled",
            "authority_status": str(motion.get("authority_status", "DISABLED_BY_CONFIG")),
        }
    return np.clip(result, 0.0, 1.0).astype(np.float32), receipt


def augment_normalized_depth_frame(
    depth: np.ndarray,
    realization: Mapping[str, Any],
    frame_index: int,
    *,
    valid_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply DepthADD's per-frame depth augmentation to normalized [0,1] depth."""
    result = np.asarray(depth, dtype=np.float32).copy()
    if result.ndim != 2:
        raise ValueError(f"normalized depth must be HxW, got {result.shape}")
    if not np.isfinite(result).all() or result.min() < 0.0 or result.max() > 1.0:
        raise ValueError("normalized depth must contain finite values in [0, 1]")
    source_valid = result > 0.0 if valid_mask is None else np.asarray(valid_mask, dtype=bool)
    if source_valid.shape != result.shape:
        raise ValueError(
            f"valid_mask shape {source_valid.shape} does not match normalized depth {result.shape}"
        )
    result[~source_valid] = 0.0
    config = _mapping(_mapping(realization["config"], "realization.config")["depth_observation"], "depth_observation")
    seed = _mapping(realization["augmentation_streams"], "augmentation_streams")["depth_noise_seed"]
    rng = np.random.default_rng(_frame_seed(int(seed), frame_index, 2))
    receipt: dict[str, Any] = {"frame_index": frame_index}
    scale_active, scale = _event(rng, _mapping(config["scale"], "depth.scale"), "depth.scale")
    if scale_active:
        scale["value"] = _uniform(rng, config["scale"]["range"], "depth.scale.range")
        result *= scale["value"]
    receipt["scale"] = scale
    noise_active, noise = _event(rng, _mapping(config["gaussian_noise"], "depth.gaussian_noise"), "depth.gaussian_noise")
    if noise_active:
        noise["normalized_std"] = _uniform(rng, config["gaussian_noise"]["normalized_std"], "depth.gaussian_noise.normalized_std")
        result += rng.normal(0.0, noise["normalized_std"], size=result.shape).astype(np.float32)
    result[~source_valid] = 0.0
    receipt["gaussian_noise"] = noise
    metric_depth_m = 0.1 + result * 3.9
    near_blind = metric_depth_m < float(config["near_blind_below_m"])
    result[near_blind] = 0.0
    receipt["near_blind_below_m"] = float(config["near_blind_below_m"])
    receipt["near_blind_pixel_count"] = int(near_blind.sum())
    dropout_active, dropout = _event(rng, _mapping(config["dropout"], "depth.dropout"), "depth.dropout")
    if dropout_active:
        patches = config["dropout"]["patches"]
        count = int(rng.integers(int(patches[0]), int(patches[1]) + 1))
        low_size, high_size = (int(value) for value in config["dropout"]["patch_size_px"])
        rectangles = []
        for _ in range(count):
            height, width = int(rng.integers(low_size, high_size + 1)), int(rng.integers(low_size, high_size + 1))
            top, left = int(rng.integers(max(1, result.shape[0] - height + 1))), int(rng.integers(max(1, result.shape[1] - width + 1)));
            result[top : top + height, left : left + width] = 0.0
            rectangles.append([top, left, height, width])
        pixel_rate = _uniform(rng, config["dropout"]["pixel_rate"], "depth.dropout.pixel_rate")
        result[rng.random(result.shape) < pixel_rate] = 0.0
        dropout.update({"patches": rectangles, "pixel_rate": pixel_rate})
    receipt["dropout"] = dropout
    quant_active, quantization = _event(rng, _mapping(config["quantization"], "depth.quantization"), "depth.quantization")
    if quant_active:
        low, high = (int(value) for value in config["quantization"]["levels"])
        quantization["levels"] = int(rng.integers(low, high + 1))
        valid_for_quantization = source_valid & (result > 0.0)
        if bool(np.any(valid_for_quantization)):
            valid_values = result[valid_for_quantization]
            min_depth = float(valid_values.min())
            max_depth = float(valid_values.max())
            quantization["valid_min"] = min_depth
            quantization["valid_max"] = max_depth
            if max_depth > min_depth:
                levels = quantization["levels"] - 1
                quantized = (
                    np.round((valid_values - min_depth) / (max_depth - min_depth) * levels)
                    / levels
                    * (max_depth - min_depth)
                    + min_depth
                )
                result[valid_for_quantization] = quantized
        else:
            quantization["valid_min"] = None
            quantization["valid_max"] = None
    receipt["quantization"] = quantization
    specular_active, specular = _event(rng, _mapping(config["specular_region_dropout"], "depth.specular_region_dropout"), "depth.specular_region_dropout")
    if specular_active:
        count = int(rng.integers(int(config["specular_region_dropout"]["regions"][0]), int(config["specular_region_dropout"]["regions"][1]) + 1))
        rectangles = []
        for _ in range(count):
            hfrac = _uniform(rng, config["specular_region_dropout"]["height_fraction"], "depth.specular.height_fraction")
            wfrac = _uniform(rng, config["specular_region_dropout"]["width_fraction"], "depth.specular.width_fraction")
            height, width = max(1, round(hfrac * result.shape[0])), max(1, round(wfrac * result.shape[1]))
            top, left = int(rng.integers(max(1, result.shape[0] - height + 1))), int(rng.integers(max(1, result.shape[1] - width + 1)));
            result[top : top + height, left : left + width] = 0.0
            rectangles.append([top, left, height, width])
        specular["regions"] = rectangles
    receipt["specular_region_dropout"] = specular
    full_zero = bool(rng.random() < float(config["full_frame_zero_probability"]))
    if full_zero:
        result.fill(0.0)
    receipt["full_frame_zero"] = full_zero
    result[~source_valid] = 0.0
    receipt["source_valid_pixel_count"] = int(source_valid.sum())
    return np.clip(result, 0.0, 1.0).astype(np.float32), receipt
