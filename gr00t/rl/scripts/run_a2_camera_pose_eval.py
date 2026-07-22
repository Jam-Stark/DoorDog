#!/usr/bin/env python3
"""Run an A2 camera-pose overlay against a pinned read-only runtime repository."""

from __future__ import annotations

import argparse
import importlib
import importlib.abc
import importlib.util
import os
import runpy
import sys
from pathlib import Path


EAGER_OVERLAY_MODULES = (
    (
        "gr00t.rl.utils.a2_camera_pose_sweep",
        "gr00t/rl/utils/a2_camera_pose_sweep.py",
    ),
)
LAZY_OVERLAY_MODULES = (
    (
        "gr00t.rl.envs.door.door_open_a2_camera_pose_sweep",
        "gr00t/rl/envs/door/door_open_a2_camera_pose_sweep.py",
    ),
)
OVERLAY_MODULES = EAGER_OVERLAY_MODULES + LAZY_OVERLAY_MODULES


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Overlay camera diagnostics onto a pinned A2 runtime repository."
    )
    parser.add_argument("--runtime-repository", type=Path, required=True)
    parser.add_argument("--overlay-repository", type=Path, required=True)
    args, hydra_args = parser.parse_known_args()
    if hydra_args[:1] == ["--"]:
        hydra_args = hydra_args[1:]
    if not hydra_args:
        raise ValueError("camera pose eval bootstrap requires Hydra overrides")
    return args, hydra_args


def load_overlay_module(module_name: str, source_path: Path):
    parent_name = module_name.rsplit(".", 1)[0]
    importlib.import_module(parent_name)
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load overlay module spec: {source_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if Path(module.__file__).resolve() != source_path.resolve():
        raise RuntimeError(f"overlay module identity mismatch: {module_name}")
    return module


class LazyOverlayFinder(importlib.abc.MetaPathFinder):
    """Resolve IsaacLab-dependent overlay modules only after AppLauncher starts."""

    def __init__(self, module_sources: dict[str, Path]):
        self._module_sources = module_sources

    def find_spec(self, fullname, path, target=None):
        del path, target
        source_path = self._module_sources.get(fullname)
        if source_path is None:
            return None
        if fullname in sys.modules:
            raise RuntimeError(f"lazy overlay module was imported before its hook: {fullname}")
        spec = importlib.util.spec_from_file_location(fullname, source_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"unable to load lazy overlay module spec: {source_path}")
        return spec


def main() -> int:
    args, hydra_args = parse_args()
    runtime_repository = args.runtime_repository.resolve()
    overlay_repository = args.overlay_repository.resolve()
    eval_entrypoint = runtime_repository / "gr00t/rl/eval_agent_trl.py"
    overlay_config = (
        overlay_repository
        / "gr00t/rl/config/camera_pose_sweep/gemini_335l_centerline.yaml"
    )
    for required_path in (eval_entrypoint, overlay_config):
        if not required_path.is_file():
            raise FileNotFoundError(f"camera pose runtime input not found: {required_path}")

    sys.path.insert(0, str(runtime_repository))
    source_paths = {}
    for module_name, relative_path in OVERLAY_MODULES:
        source_path = (overlay_repository / relative_path).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"camera pose overlay source not found: {source_path}")
        source_paths[module_name] = source_path
    for module_name, _ in EAGER_OVERLAY_MODULES:
        load_overlay_module(module_name, source_paths[module_name])
    lazy_sources = {
        module_name: source_paths[module_name] for module_name, _ in LAZY_OVERLAY_MODULES
    }
    if set(lazy_sources) & set(sys.modules):
        raise RuntimeError("IsaacLab-dependent overlay module was imported before AppLauncher")
    sys.meta_path.insert(0, LazyOverlayFinder(lazy_sources))

    os.chdir(runtime_repository)
    sys.argv = [str(eval_entrypoint), *hydra_args]
    runpy.run_path(str(eval_entrypoint), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
