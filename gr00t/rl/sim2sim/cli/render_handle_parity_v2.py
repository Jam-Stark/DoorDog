#!/usr/bin/env python3
"""Build and render the Isaac-truth two-sided handle closeups."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import mujoco
from PIL import Image

from gr00t.rl.sim2sim.doors.mjcf_builder_v2 import MjcfDoorBuilderV2
from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--door-instance", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    instance_path = args.door_instance.resolve(strict=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    door_xml = output / "door_handle_parity_v2.xml"
    build_report = output / "door_build_report_v2.json"
    MjcfDoorBuilderV2(DoorInstanceSpec.from_path(instance_path)).write(door_xml, build_report)

    model = mujoco.MjModel.from_xml_path(str(door_xml))
    data = mujoco.MjData(model)
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "door_closed")
    mujoco.mj_resetDataKeyframe(model, data, home_id)
    mujoco.mj_forward(model, data)
    renderer = mujoco.Renderer(model, width=640, height=480)
    images = {}
    for side in ("outside", "inside"):
        camera = f"handle_{side}_closeup"
        renderer.update_scene(data, camera=camera)
        image = renderer.render().copy()
        path = output / f"handle_{side}_closeup.png"
        Image.fromarray(image).save(path)
        images[side] = {
            "path": str(path),
            "camera": camera,
            "shape_hwc": list(image.shape),
            "min_uint8": int(image.min()),
            "max_uint8": int(image.max()),
        }
    renderer.close()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    report = json.loads(build_report.read_text(encoding="utf-8"))
    receipt = {
        "schema": "doordog.sim2sim.handle_parity_render_receipt.v2",
        "result": "PASS",
        "door_instance": str(instance_path),
        "door_build_report": str(build_report),
        "handle_geometry_parity": report["handle_geometry_parity"],
        "images": images,
        "renderer": "mujoco.Renderer",
        "producer_identity": {
            "git_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/render_handle_parity_v2.py",
        },
    }
    (output / "handle_render_receipt_v2.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": "PASS", "images": images}, sort_keys=True))


if __name__ == "__main__":
    main()
