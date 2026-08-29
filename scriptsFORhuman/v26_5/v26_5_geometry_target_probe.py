#!/usr/bin/env python3
"""Static composition and production-wire proof for the v26-5 geometry target cell."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "gr00t/rl/config"
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
CONFIG = CONFIG_ROOT / "ablation/wbmanip/base_v26_5_geometry_target.yaml"
R2_C0 = CONFIG_ROOT / "ablation/wbmanip/base_v26_4_C0_CANONICAL_OFF.yaml"


def merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def compose(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"config must be a mapping: {path}")
    result: dict[str, Any] = {}
    for entry in payload.get("defaults", []):
        if not isinstance(entry, str) or entry == "_self_":
            continue
        reference = entry.removeprefix("override ").strip()
        if not reference.startswith("/ablation/"):
            raise RuntimeError(f"unsupported config default in v26-5 proof: {entry!r}")
        result = merge(result, compose(CONFIG_ROOT / f"{reference.removeprefix('/')}.yaml"))
    payload.pop("defaults", None)
    return merge(result, payload)


def class_methods(tree: ast.Module, class_name: str) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise RuntimeError(f"production class {class_name} was not found")


def main() -> None:
    r2_c0 = compose(R2_C0)
    resolved = compose(CONFIG)
    config = resolved["env"]["config"]
    if config["a2_v26_4_side_canonicalization_enabled"] is not False:
        raise RuntimeError("v26-5 geometry target requires canonicalization OFF")
    if config["a2_v26_5_geometry_target_enabled"] is not True:
        raise RuntimeError("v26-5 geometry target factor must be bool true")

    expected_config = dict(r2_c0["env"]["config"])
    expected_config["a2_v26_5_geometry_target_enabled"] = True
    if config != expected_config:
        raise RuntimeError("v26-5 geometry target changed an R2 C0 env.config field")
    for key in ("rewards", "robot", "simulator"):
        if resolved[key] != r2_c0[key]:
            raise RuntimeError(f"v26-5 geometry target changed R2 C0 {key}")

    source_text = SOURCE.read_text(encoding="utf-8")
    methods = class_methods(ast.parse(source_text), "OrderedTargetFrameTransformer")
    required_methods = {
        "__init__",
        "_initialize_impl",
        "_a2_v26_5_geometry_target_offset_quaternions",
    }
    if not required_methods <= methods:
        raise RuntimeError(
            "OrderedTargetFrameTransformer is missing v26-5 production methods: "
            f"{sorted(required_methods - methods)}"
        )
    required_source_tokens = (
        "physics:localRot0",
        "physics:localPos0",
        "door_panel/handle_joint",
        "grasp_target",
        "quat_mul(quat_inv(target_world_quat), desired_world_quat)",
        "a2_v26_5_geometry_target_enabled=self._a2_v26_5_geometry_target_enabled()",
    )
    missing = [token for token in required_source_tokens if token not in source_text]
    if missing:
        raise RuntimeError(f"v26-5 geometry target production wire is incomplete: {missing}")

    print(
        json.dumps(
            {
                "status": "STATIC_PASS",
                "config": str(CONFIG.relative_to(ROOT)),
                "canonicalization_enabled": config["a2_v26_4_side_canonicalization_enabled"],
                "geometry_target_enabled": config["a2_v26_5_geometry_target_enabled"],
                "r2_c0_rewards_robot_simulator_preserved": True,
                "ordered_target_frame_transformer_wire": "PASS",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
