#!/usr/bin/env python3
"""Dedicated A2 student camera smoke entrypoint for a later runtime lane.

This script deliberately does not launch IsaacSim by default.  It provides
import-safe config/frame checks for static tests.  Runtime QA uses a separate
approved runtime entrypoint and is not hidden behind a switch here.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import math
from pathlib import Path

import torch
import yaml


def _numeric_sequence(value, length, field_name):
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be an explicit numeric sequence; got {value!r}")
    values = tuple(value)
    if len(values) != length:
        raise ValueError(f"{field_name} must contain exactly {length} values; got {value!r}")
    if any(isinstance(item, bool) for item in values):
        raise ValueError(f"{field_name} must contain numeric values; got {value!r}")
    try:
        converted = tuple(float(item) for item in values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain numeric values; got {value!r}") from exc
    if not all(math.isfinite(item) for item in converted):
        raise ValueError(f"{field_name} must contain finite values; got {value!r}")
    return converted


def parse_camera_clipping_range(value):
    near, far = _numeric_sequence(value, 2, "camera_clipping_range")
    if not math.isfinite(near) or not math.isfinite(far) or near <= 0.0 or far <= near:
        raise ValueError(f"camera clipping range requires 0 < near < far, got {(near, far)!r}")
    return near, far


def _parse_camera_pose(cameras):
    position = _numeric_sequence(cameras["camera_pos"], 3, "camera_pos")
    rotation = _numeric_sequence(cameras["camera_rot_wxyz"], 4, "camera_rot_wxyz")
    norm = math.sqrt(sum(component * component for component in rotation))
    if not math.isclose(norm, 1.0, rel_tol=1.0e-4, abs_tol=1.0e-4):
        raise ValueError(f"camera_rot_wxyz must be normalized; got norm={norm!r}")
    return position, rotation


def validate_rgb_frame(frame, expected_shape):
    if not torch.is_tensor(frame):
        raise TypeError(f"RGB frame must be a tensor, got {type(frame).__name__}")
    if tuple(frame.shape) != tuple(expected_shape):
        raise ValueError(f"RGB frame shape mismatch: expected {tuple(expected_shape)}, got {tuple(frame.shape)}")
    if frame.dtype != torch.uint8:
        raise TypeError(f"RGB frame must be raw torch.uint8 NHWC data; got {frame.dtype}")
    if torch.any(torch.all(frame == 0, dim=(-1, -2, -3))):
        raise ValueError("RGB frame contains an all-zero/uninitialized environment")
    return frame


def validate_camera_config(config_path: str | Path):
    with Path(config_path).open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    cameras = config.get("simulator", {}).get("config", {}).get("cameras", {})
    required = (
        "camera_parent",
        "camera_prim_suffix",
        "camera_pos",
        "camera_rot_wxyz",
        "camera_convention",
        "camera_focal_length",
        "camera_focus_distance",
        "camera_horizontal_aperture",
        "camera_vertical_aperture",
        "camera_clipping_range",
        "camera_update_period",
        "camera_resolutions",
    )
    missing = [key for key in required if key not in cameras]
    if missing:
        raise ValueError(f"A2 camera config is missing explicit fields: {missing}")
    for key in ("camera_parent", "camera_prim_suffix"):
        if not isinstance(cameras[key], str) or not cameras[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    if cameras.get("camera_convention") != "world":
        raise ValueError("A2 camera convention must be 'world'")
    if "camera_yaw_only" in cameras:
        raise ValueError("camera_yaw_only is unsupported")
    _parse_camera_pose(cameras)
    clipping = parse_camera_clipping_range(cameras["camera_clipping_range"])
    resolution = _numeric_sequence(cameras["camera_resolutions"], 2, "camera_resolutions")
    if any(value <= 0.0 or not value.is_integer() for value in resolution):
        raise ValueError("camera_resolutions must contain positive integers")
    update_period = cameras["camera_update_period"]
    if isinstance(update_period, bool):
        raise ValueError("camera_update_period must be a finite non-negative number")
    try:
        update_period = float(update_period)
    except (TypeError, ValueError) as exc:
        raise ValueError("camera_update_period must be a finite non-negative number") from exc
    if not math.isfinite(update_period) or update_period < 0.0:
        raise ValueError("camera_update_period must be a finite non-negative number")
    camera_types = cameras.get("camera_types")
    if isinstance(camera_types, (str, bytes)) or not isinstance(camera_types, Sequence):
        raise ValueError("camera_types must be an explicit sequence")
    if not any(isinstance(item, Mapping) and item.get("rgb") is True for item in camera_types):
        raise ValueError("camera_types must explicitly enable RGB")
    return {"parent": cameras["camera_parent"], "suffix": cameras["camera_prim_suffix"], "clipping": clipping}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(validate_camera_config(args.config))
    print("STATIC_ONLY: import-safe camera contract validation complete")


if __name__ == "__main__":
    main()
