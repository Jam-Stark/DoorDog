#!/usr/bin/env python3
"""Run an A2 camera-pose overlay against a pinned read-only runtime repository."""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.abc
import importlib.util
import os
import re
import runpy
import sys
from pathlib import Path


EAGER_OVERLAY_MODULES = (
    (
        "gr00t.rl.utils.a2_camera_pose_sweep",
        "gr00t/rl/utils/a2_camera_pose_sweep.py",
    ),
    (
        "gr00t.rl.utils.a2_dual_portrait_panorama",
        "gr00t/rl/utils/a2_dual_portrait_panorama.py",
    ),
)
LAZY_OVERLAY_MODULES = (
    (
        "gr00t.rl.envs.door.door_open_a2_camera_pose_sweep",
        "gr00t/rl/envs/door/door_open_a2_camera_pose_sweep.py",
    ),
)
OVERLAY_MODULES = EAGER_OVERLAY_MODULES + LAZY_OVERLAY_MODULES
BOOTSTRAP_PROFILE_LEGACY = "legacy"
BOOTSTRAP_PROFILE_TOEOUT_NO_PANORAMA = "toeout-no-panorama"
BOOTSTRAP_PROFILES = {
    BOOTSTRAP_PROFILE_LEGACY: {
        "eager": EAGER_OVERLAY_MODULES,
        "lazy": LAZY_OVERLAY_MODULES,
    },
    BOOTSTRAP_PROFILE_TOEOUT_NO_PANORAMA: {
        "eager": (EAGER_OVERLAY_MODULES[0],),
        "lazy": LAZY_OVERLAY_MODULES,
    },
}
CAMERA_CONFIGS = (
    "gemini_335l_centerline",
    "d435i_portrait_a2_head",
    "d435i_landscape_up45_a2_head",
    "d435i_landscape_up60_a2_head",
    "d435i_landscape_stage0_3_pitch_sweep",
    "d435i_dual_portrait_up60_a2_head_oem",
    "d435i_dual_portrait_up60_a2_head_oem_toein20",
    "d435i_dual_portrait_up50_a2_head_oem_toeout6",
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Overlay camera diagnostics onto a pinned A2 runtime repository."
    )
    parser.add_argument("--runtime-repository", type=Path, required=True)
    parser.add_argument("--overlay-repository", type=Path, required=True)
    parser.add_argument(
        "--bootstrap-profile",
        choices=tuple(BOOTSTRAP_PROFILES),
        default=BOOTSTRAP_PROFILE_LEGACY,
    )
    args, hydra_args = parser.parse_known_args()
    if hydra_args[:1] == ["--"]:
        hydra_args = hydra_args[1:]
    if not hydra_args:
        raise ValueError("camera pose eval bootstrap requires Hydra overrides")
    return args, hydra_args


def _module_dotted_name(node: ast.AST) -> str:
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _validate_no_panorama_source(module_name: str, source_path: Path) -> None:
    source = source_path.read_text(encoding="utf-8")
    if "a2_dual_portrait_panorama" in source:
        raise RuntimeError(
            f"{BOOTSTRAP_PROFILE_TOEOUT_NO_PANORAMA} overlay retains forbidden panorama import: "
            f"{module_name}={source_path}"
        )
    if re.search(r"\b(?:panorama_writer|build_panorama|construct_panorama)\b", source):
        raise RuntimeError(
            f"{BOOTSTRAP_PROFILE_TOEOUT_NO_PANORAMA} overlay retains forbidden panorama writer: "
            f"{module_name}={source_path}"
        )
    try:
        tree = ast.parse(source, filename=str(source_path))
    except SyntaxError as exc:
        raise RuntimeError(f"toe-out overlay source is not valid Python: {source_path}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported_names = [node.module or ""] + [alias.name for alias in node.names]
        else:
            imported_names = []
        if any("panorama" in name.lower() for name in imported_names):
            raise RuntimeError(
                f"{BOOTSTRAP_PROFILE_TOEOUT_NO_PANORAMA} overlay imports forbidden panorama code: "
                f"{module_name}={source_path}"
            )
        if isinstance(node, ast.Call):
            dotted_name = _module_dotted_name(node.func)
            if "panorama" in dotted_name.lower():
                raise RuntimeError(
                    f"{BOOTSTRAP_PROFILE_TOEOUT_NO_PANORAMA} overlay invokes forbidden panorama code: "
                    f"{module_name}={source_path}"
                )


def resolve_overlay_sources(overlay_repository: Path, profile: str) -> dict[str, Path]:
    """Resolve exactly the overlay modules required by an explicit bootstrap profile."""
    try:
        profile_spec = BOOTSTRAP_PROFILES[profile]
    except KeyError as exc:
        raise ValueError(f"unsupported camera pose bootstrap profile: {profile!r}") from exc
    source_paths: dict[str, Path] = {}
    module_groups = (profile_spec["eager"], profile_spec["lazy"])
    for module_group in module_groups:
        for module_name, relative_path in module_group:
            source_path = (overlay_repository / relative_path).resolve()
            if not source_path.is_file():
                raise FileNotFoundError(f"camera pose overlay source not found: {source_path}")
            if profile == BOOTSTRAP_PROFILE_TOEOUT_NO_PANORAMA:
                _validate_no_panorama_source(module_name, source_path)
            source_paths[module_name] = source_path
    return source_paths


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
    camera_config_overrides = [
        token.removeprefix("+camera_pose_sweep=")
        for token in hydra_args
        if token.startswith("+camera_pose_sweep=")
    ]
    if len(camera_config_overrides) != 1:
        raise ValueError(
            "camera pose bootstrap requires exactly one +camera_pose_sweep override"
        )
    camera_config = camera_config_overrides[0]
    if camera_config not in CAMERA_CONFIGS:
        raise ValueError(
            f"unsupported camera pose config {camera_config!r}; "
            f"expected one of {CAMERA_CONFIGS}"
        )
    overlay_config = (
        overlay_repository
        / "gr00t/rl/config/camera_pose_sweep"
        / f"{camera_config}.yaml"
    )
    for required_path in (eval_entrypoint, overlay_config):
        if not required_path.is_file():
            raise FileNotFoundError(f"camera pose runtime input not found: {required_path}")

    sys.path.insert(0, str(runtime_repository))
    source_paths = resolve_overlay_sources(overlay_repository, args.bootstrap_profile)
    profile_spec = BOOTSTRAP_PROFILES[args.bootstrap_profile]
    for module_name, _ in profile_spec["eager"]:
        load_overlay_module(module_name, source_paths[module_name])
    lazy_sources = {module_name: source_paths[module_name] for module_name, _ in profile_spec["lazy"]}
    if set(lazy_sources) & set(sys.modules):
        raise RuntimeError("IsaacLab-dependent overlay module was imported before AppLauncher")
    sys.meta_path.insert(0, LazyOverlayFinder(lazy_sources))

    os.chdir(runtime_repository)
    sys.argv = [str(eval_entrypoint), *hydra_args]
    runpy.run_path(str(eval_entrypoint), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
