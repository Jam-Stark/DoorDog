#!/usr/bin/env python3
"""Render and read back the concrete v29 B05 asset population.

The probe creates 28 production B05 samples (F0--F6 x left/right x no-return/
return), then six boundary samples.  It is deliberately an asset-only run:
there is no robot, contact trial, policy, or training loop.  A single Isaac Sim
application authors every door into one stage and renders the resulting USD
geometry after the whole population has been created.  The bounded run is 34
doors and 68 saved views. Rendering does not advance physics after reset, so
each PNG uses the same handle and target frame state written to readback.

Example (Main must bind the physical GPU before launching):

    CUDA_VISIBLE_DEVICES=0 CUDA_DEVICE_ORDER=PCI_BUS_ID \
      /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B \
      -m scriptsFORhuman.v29.v29_asset_probe --headless --enable_cameras \
      --device cuda:0 --output /ABS/fresh_v29_asset_probe
"""

from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from gr00t.rl.isaac_utils.playground.env_rand.door_v29_parameters import sample_door_parameters
from gr00t.rl.isaac_utils.playground.env_rand.handle_v29 import (
    normalize_handle_metadata,
    sample_handle_parameters,
)


STRUCTURAL_COUNT = 7 * 2 * 2
BOUNDARY_COUNT = 6
RENDER_WIDTH = 640
RENDER_HEIGHT = 480


def _json_value(value: Any) -> Any:
    """Convert USD and NumPy values to a JSON table without changing their values."""
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (Gf.Vec3f, Gf.Vec3d, Gf.Vec3h)):
        return [float(component) for component in value]
    if isinstance(value, (Gf.Quatf, Gf.Quatd, Gf.Quath)):
        imaginary = value.GetImaginary()
        return [float(value.GetReal()), float(imaginary[0]), float(imaginary[1]), float(imaginary[2])]
    return value


def _matrix(matrix: Gf.Matrix4d) -> list[list[float]]:
    return [[float(matrix[row][column]) for column in range(4)] for row in range(4)]


def _force_return(parameters: dict, present: bool, rng: np.random.Generator) -> dict:
    """Choose the B05 conditional return branch after fixing the probe cell."""
    result = deepcopy(parameters)
    result["return_present"] = present
    if not present:
        result["return_radius_m"] = 0.0
        result["return_depth_m"] = 0.0
        return result
    ceiling = min(
        0.060,
        result["face_standoff_m"] - result["tip_cap_extension_m"] - 0.008,
    )
    if ceiling < 0.020:
        raise ValueError(f"B05 return domain is empty for {result['family']}: ceiling={ceiling}")
    radius = float(rng.uniform(0.020, min(0.030, ceiling)))
    result["return_radius_m"] = radius
    result["return_depth_m"] = float(rng.uniform(radius, ceiling))
    return result


def _boundary_parameters(name: str, rng: np.random.Generator) -> tuple[str, str, dict]:
    """Use exact domain edges that matter for the approved B05 construction."""
    if name == "h55":
        parameters = sample_handle_parameters(family="F0", rng=rng)
        parameters["face_standoff_m"] = 0.055
        return "left", name, _force_return(parameters, False, rng)
    if name == "f2_max_roll_return":
        parameters = sample_handle_parameters(family="F2", rng=rng)
        parameters.update(
            section_normal_diameter_m=0.033,
            section_closing_diameter_m=0.0198,
            corner_radius_m=0.0066,
            section_roll_rad=math.atan2(0.015 - 0.006, 0.009 - 0.006),
            face_standoff_m=0.055,
            plane_scale=.90,
        )
        parameters["tip_cap_extension_m"] = 1.1 * (math.hypot(0.015 - 0.006, 0.009 - 0.006) + 0.006)
        ceiling = min(.060, parameters["face_standoff_m"] - parameters["tip_cap_extension_m"] - .008)
        parameters.update(return_present=True, return_radius_m=min(.030, ceiling), return_depth_m=ceiling)
        return "right", name, parameters
    if name in ("f2_max_normal_left", "f2_max_normal_right"):
        _, _, parameters = _boundary_parameters("f2_max_roll_return", rng)
        parameters["section_roll_rad"] = math.atan2(.003, .009)
        return name.rsplit("_", 1)[1], name, parameters
    if name == "f3_lambda_lower":
        parameters = sample_handle_parameters(family="F3", rng=rng)
        parameters["plane_scale"] = .065 / .069
        return "left", name, _force_return(parameters, False, rng)
    if name == "return_h85":
        parameters = sample_handle_parameters(family="F6", rng=rng)
        parameters["face_standoff_m"] = 0.085
        return "right", name, _force_return(parameters, True, rng)
    raise ValueError(f"unknown boundary sample {name}")


def _make_specs(rng: np.random.Generator) -> list[dict]:
    specs: list[dict] = []
    for family_index in range(7):
        family = f"F{family_index}"
        for side in ("left", "right"):
            for return_present in (False, True):
                parameters = _force_return(sample_handle_parameters(family=family, rng=rng), return_present, rng)
                specs.append(
                    {
                        "id": f"{family}_{side}_{'return' if return_present else 'plain'}",
                        "kind": "structural",
                        "side": side,
                        "parameters": parameters,
                    }
                )
    for name in ("h55", "f2_max_roll_return", "f3_lambda_lower", "return_h85",
                 "f2_max_normal_left", "f2_max_normal_right"):
        side, _, parameters = _boundary_parameters(name, rng)
        specs.append({"id": f"boundary_{name}", "kind": "boundary", "side": side, "parameters": parameters})
    if len(specs) != STRUCTURAL_COUNT + BOUNDARY_COUNT:
        raise RuntimeError(f"unexpected v29 asset probe count: {len(specs)}")
    return specs


def build_cases(seed: int = 291) -> list[dict]:
    """Return the exact 28 B05 structural and six boundary probe cases.

    This function is pure: it neither launches Isaac Sim nor authors USD.  A case
    contains the resolved B05 ``handle`` dict, B01/B04 ``dynamics`` dict, door
    ``side``, and stable ``label`` so a separate asset or full-env probe can use
    precisely the same population.
    """
    rng = np.random.default_rng(seed)
    specs = _make_specs(rng)
    dynamics = sample_door_parameters([spec["side"] for spec in specs], rng)
    cases = []
    for spec, dynamic in zip(specs, dynamics, strict=True):
        cases.append(
            {
                "label": spec["id"],
                "kind": spec["kind"],
                "side": spec["side"],
                "handle": spec["parameters"],
                "dynamics": dynamic,
                "handle_height_m": 1.0,
                "door_width_m": 1.0,
                "door_height_m": 2.0,
                "handle_width_m": .10,
            }
        )
    return cases


def _fixed_cfg(parameters: dict, dynamics: dict, side: str) -> DoorSpawnerCfg:
    """Give spawn_door a single fully resolved production v29 door."""
    return DoorSpawnerCfg(
        func=spawn_door,
        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            enabled_self_collisions=True,
            solver_position_iteration_count=4,
            solver_velocity_iteration_count=4,
            fix_root_link=True,
        ),
        activate_contact_sensors=True,
        build_latch=True,
        add_walls=False,
        add_floors=False,
        add_lights=False,
        door_width=(1.0, 1.0),
        door_height=(2.0, 2.0),
        door_handle_tblr=(1.10, 0.80, 0.08, 0.15),
        door_open_lr=[side],
        door_open_io=["out"],
        rand_door_width=1.0,
        rand_door_height=2.0,
        rand_door_handle_height=1.0,
        rand_door_handle_width=0.10,
        rand_door_weight=float(dynamics["mass_kg"]),
        rand_door_handle_type="lever",
        rand_door_open_lr=side,
        rand_door_open_io="out",
        rand_total_wall_height=2.4,
        rand_handle_drive_max_force=2.0,
        v29_handle=parameters,
        v29_dynamics=dynamics,
    )


def _read_frame(stage, path: str, cache: UsdGeom.XformCache) -> dict:
    prim = stage.GetPrimAtPath(path)
    if not prim.IsValid():
        raise RuntimeError(f"missing expected frame prim: {path}")
    transform = cache.GetLocalToWorldTransform(prim)
    return {
        "matrix": _matrix(transform),
        "translation_m": _json_value(transform.ExtractTranslation()),
    }


def _read_back(stage, spec: dict, prim_path: str) -> dict:
    root = stage.GetPrimAtPath(prim_path)
    if not root.IsValid():
        raise RuntimeError(f"spawn_door did not author {prim_path}")
    metadata = root.GetMetadata("customData")
    if "v29Handle" not in metadata or "v29Dynamics" not in metadata:
        raise RuntimeError(f"{prim_path} lacks v29 production metadata")
    handle = stage.GetPrimAtPath(f"{prim_path}/door_handle")
    grasp = stage.GetPrimAtPath(f"{prim_path}/grasp_target")
    fixed_path = f"{prim_path}/door_handle/grasp_target_joint"
    fixed = UsdPhysics.FixedJoint(stage.GetPrimAtPath(fixed_path))
    if not handle.IsValid() or not grasp.IsValid() or not fixed.GetPrim().IsValid():
        raise RuntimeError(f"{prim_path} lacks door_handle, grasp_target, or FixedJoint")
    body0 = [target.pathString for target in fixed.GetBody0Rel().GetTargets()]
    body1 = [target.pathString for target in fixed.GetBody1Rel().GetTargets()]
    if body0 != [f"{prim_path}/grasp_target"] or body1 != [f"{prim_path}/door_handle"]:
        raise RuntimeError(f"{fixed_path} body relationship differs from v29 target contract")
    roses = [f"{prim_path}/door_panel/rose_inside", f"{prim_path}/door_panel/rose_outside"]
    if any(not stage.GetPrimAtPath(path).IsValid() for path in roses):
        raise RuntimeError(f"{prim_path} is missing a B05 panel rose")
    geometry = []
    for prim in Usd.PrimRange(handle):
        if prim.IsA(UsdGeom.Gprim):
            geometry.append(
                {
                    "path": prim.GetPath().pathString,
                    "type": prim.GetTypeName(),
                    "collision": prim.HasAPI(UsdPhysics.CollisionAPI),
                }
            )
    if not geometry:
        raise RuntimeError(f"{prim_path} has no authored handle geometry")
    actual = normalize_handle_metadata(metadata["v29Handle"])
    if actual["family"] != spec["handle"]["family"]:
        raise RuntimeError(f"{prim_path} metadata family differs from requested sample")
    if bool(actual["return_present"]) != bool(spec["handle"]["return_present"]):
        raise RuntimeError(f"{prim_path} metadata return branch differs from requested sample")
    cache = UsdGeom.XformCache()
    return {
        "id": spec["label"],
        "prim_path": prim_path,
        "custom_data": _json_value({**metadata, "v29Handle": actual}),
        "handle_geometry": geometry,
        "roses": roses,
        "fixed_joint": {
            "path": fixed_path,
            "body0": body0,
            "body1": body1,
            "local_pos0": _json_value(fixed.GetLocalPos0Attr().Get()),
            "local_rot0_wxyz": _json_value(fixed.GetLocalRot0Attr().Get()),
            "local_pos1": _json_value(fixed.GetLocalPos1Attr().Get()),
            "local_rot1_wxyz": _json_value(fixed.GetLocalRot1Attr().Get()),
        },
        "frames_world": {
            "door_handle": _read_frame(stage, handle.GetPath().pathString, cache),
            "grasp_target": _read_frame(stage, grasp.GetPath().pathString, cache),
        },
    }


def _camera() -> Camera:
    cfg = CameraCfg(
        prim_path="/World/ProbeCamera",
        update_period=0.0,
        height=RENDER_HEIGHT,
        width=RENDER_WIDTH,
        data_types=["rgb"],
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=24.0,
            focus_distance=5.0,
            horizontal_aperture=20.955,
            clipping_range=(0.01, 100.0),
        ),
    )
    return Camera(cfg=cfg)


def render_view(
    sim: sim_utils.SimulationContext,
    camera: Camera,
    eye: np.ndarray,
    target: np.ndarray,
    output_path: Path,
) -> None:
    """Save one actual Camera RGB view without advancing authored physics."""
    from PIL import Image

    import torch

    camera.set_world_poses_from_view(
        torch.as_tensor(eye[None], dtype=torch.float32, device=sim.device),
        torch.as_tensor(target[None], dtype=torch.float32, device=sim.device),
    )
    # Replicator publishes the moved camera texture asynchronously. Two
    # render-only updates settle that buffer without driving the articulated
    # doors away from the pose recorded in usd_readback.json.
    for _ in range(2):
        sim.render()
        camera.update(0.0, force_recompute=True)
    image = camera.data.output["rgb"][0, ..., :3].detach().cpu().numpy()
    Image.fromarray(image).save(output_path)


def _render_views(sim: sim_utils.SimulationContext, camera: Camera, records: list[dict], output: Path) -> None:
    from PIL import Image

    views = output / "views"
    views.mkdir()
    for record in records:
        target = np.asarray(record["frames_world"]["grasp_target"]["translation_m"], dtype=np.float64)
        for view, x_offset in (("outside", .65), ("inside", -.50)):
            eye = target + np.array([x_offset, -.10, 0.15])
            render_view(sim, camera, eye, target, views / f"{record['id']}_{view}.png")
    structural = [record for record in records if record["id"].startswith("F")]
    thumbnails = [Image.open(views / f"{record['id']}_outside.png").convert("RGB") for record in structural]
    columns = 4
    rows = math.ceil(len(thumbnails) / columns)
    atlas = Image.new("RGB", (columns * RENDER_WIDTH, rows * RENDER_HEIGHT))
    for index, image in enumerate(thumbnails):
        atlas.paste(image, ((index % columns) * RENDER_WIDTH, (index // columns) * RENDER_HEIGHT))
    atlas.save(output / "structural_outside_atlas.png")


def _load_runtime() -> None:
    global Gf, Usd, UsdGeom, UsdPhysics, sim_utils, Camera, CameraCfg, DoorSpawnerCfg, spawn_door

    import isaaclab.sim as sim_utils
    from isaaclab.sensors import Camera, CameraCfg
    from pxr import Gf, Usd, UsdGeom, UsdPhysics

    from gr00t.rl.isaac_utils.playground.env_rand.door import DoorSpawnerCfg, spawn_door


def _run(args_cli: argparse.Namespace) -> None:
    output = args_cli.output.resolve()
    output.mkdir(parents=True)
    cases = build_cases(args_cli.seed)

    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(device=args_cli.device))
    dome = sim_utils.DomeLightCfg(intensity=2500.0, color=(0.75, 0.78, 0.85))
    dome.func("/World/ProbeDome", dome)
    key = sim_utils.DistantLightCfg(intensity=2500.0, angle=20.0)
    key.func("/World/ProbeKey", key)

    stage = sim.stage
    authored: list[tuple[dict, str]] = []
    for index, case in enumerate(cases):
        row, column = divmod(index, 8)
        prim_path = f"/World/V29AssetProbe/{case['label']}"
        spawn_door(
            prim_path,
            _fixed_cfg(case["handle"], case["dynamics"], case["side"]),
            translation=(float(column) * 3.0, float(row) * 3.0, 0.0),
        )
        authored.append((case, prim_path))

    camera = _camera()
    sim.reset()
    records = [_read_back(stage, spec, prim_path) for spec, prim_path in authored]
    stage.Export(str(output / "v29_asset_probe.usda"))
    (output / "parameters.json").write_text(json.dumps(_json_value(cases), indent=2, sort_keys=True) + "\n")
    (output / "usd_readback.json").write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
    _render_views(sim, camera, records, output)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "seed": args_cli.seed,
                "structural_samples": STRUCTURAL_COUNT,
                "boundary_samples": BOUNDARY_COUNT,
                "physics_steps_after_reset": 0,
                "render_refreshes": 2 + 4 * len(records),
                "renders": 2 * len(records),
                "usd": "v29_asset_probe.usda",
                "parameters": "parameters.json",
                "readback": "usd_readback.json",
                "atlas": "structural_outside_atlas.png",
                "cases": _json_value(cases),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    from isaaclab.app import AppLauncher

    parser = argparse.ArgumentParser(description="Author, render, and read back v29 B05 door assets.")
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory for USD, JSON, PNGs, and atlas.")
    parser.add_argument("--seed", type=int, default=291, help="NumPy seed for the fixed probe population.")
    AppLauncher.add_app_launcher_args(parser)
    args_cli = parser.parse_args()
    if args_cli.output.exists():
        raise FileExistsError(f"asset probe output already exists: {args_cli.output}")
    if not args_cli.enable_cameras:
        raise ValueError("v29 asset probe requires --enable_cameras for actual renderer PNG output")
    app_launcher = AppLauncher(args_cli)
    simulation_app = app_launcher.app
    try:
        _load_runtime()
        _run(args_cli)
    except Exception:
        import os
        import sys
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    simulation_app.close(skip_cleanup=True)
