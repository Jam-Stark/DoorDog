#!/usr/bin/env python3
"""Run branch-local A2 Student distillation with pinned v16 task source modules."""

from __future__ import annotations

import argparse
import importlib.abc
import importlib.util
import os
import runpy
import subprocess
import sys
from pathlib import Path


EXPECTED_RUNTIME_COMMIT = "815b367f5de2a52b26a4b872d0457af8817d01bd"
V16_RUNTIME_MODULES = {
    "gr00t.rl.envs.door.door_open_a2_base": "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t.rl.data.tasks.door.scenario_cfg.isaacsim": (
        "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"
    ),
    "gr00t.rl.isaac_utils.playground.env_rand.door": (
        "gr00t/rl/isaac_utils/playground/env_rand/door.py"
    ),
}


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def validate_runtime_repository(repository: Path) -> dict[str, Path]:
    repository = repository.resolve()
    commit = _git(repository, "rev-parse", "HEAD")
    if commit != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError(
            f"v16 runtime commit mismatch: expected={EXPECTED_RUNTIME_COMMIT} actual={commit}"
        )
    dirty = _git(repository, "status", "--short", "--", "gr00t")
    if dirty:
        raise RuntimeError(f"v16 runtime gr00t source must be clean:\n{dirty}")
    module_sources = {}
    for module_name, relative_path in V16_RUNTIME_MODULES.items():
        source_path = (repository / relative_path).resolve()
        if not source_path.is_file() or not source_path.is_relative_to(repository):
            raise FileNotFoundError(f"v16 runtime module is unavailable: {source_path}")
        module_sources[module_name] = source_path
    return module_sources


class V16RuntimeFinder(importlib.abc.MetaPathFinder):
    """Load only the audited v16 task modules after Isaac Sim AppLauncher starts."""

    def __init__(self, module_sources: dict[str, Path]):
        self._module_sources = module_sources

    def find_spec(self, fullname, path, target=None):
        del path, target
        source_path = self._module_sources.get(fullname)
        if source_path is None:
            return None
        if fullname in sys.modules:
            raise RuntimeError(f"v16 runtime module was imported before its overlay: {fullname}")
        spec = importlib.util.spec_from_file_location(fullname, source_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"unable to load v16 runtime module: {source_path}")
        return spec


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-repository", type=Path, required=True)
    parser.add_argument("--overlay-repository", type=Path, required=True)
    args, hydra_args = parser.parse_known_args()
    if hydra_args[:1] == ["--"]:
        hydra_args = hydra_args[1:]
    if not hydra_args:
        raise ValueError("v16 Student distillation bootstrap requires Hydra overrides")
    return args, hydra_args


def main() -> int:
    args, hydra_args = parse_args()
    overlay_repository = args.overlay_repository.resolve()
    train_entrypoint = overlay_repository / "gr00t/rl/train_agent_trl.py"
    if not train_entrypoint.is_file():
        raise FileNotFoundError(f"branch-local training entrypoint is missing: {train_entrypoint}")
    module_sources = validate_runtime_repository(args.runtime_repository)
    already_loaded = sorted(set(module_sources).intersection(sys.modules))
    if already_loaded:
        raise RuntimeError(f"v16 runtime modules were imported before AppLauncher: {already_loaded}")

    sys.path.insert(0, str(overlay_repository))
    sys.meta_path.insert(0, V16RuntimeFinder(module_sources))
    os.chdir(overlay_repository)
    print(
        "[A2_V16_RUNTIME] "
        f"commit={EXPECTED_RUNTIME_COMMIT} modules={','.join(sorted(module_sources))} "
        f"overlay_repository={overlay_repository}",
        flush=True,
    )
    sys.argv = [str(train_entrypoint), *hydra_args]
    runpy.run_path(str(train_entrypoint), run_name="__main__")
    validate_runtime_repository(args.runtime_repository)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
