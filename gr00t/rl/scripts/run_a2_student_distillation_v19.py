#!/usr/bin/env python3
"""Run the user-approved c18 A2 Student v19 reconstruction.

The bootstrap validates the immutable runtime, Teacher triplet, single-GPU
binding, and exact Hydra launch dimensions before importing IsaacLab modules.
There is intentionally no checkpoint discovery or mutable last.pt fallback.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import importlib
import importlib.abc
import importlib.util
import os
import runpy
import subprocess
import sys
from pathlib import Path


EXPECTED_RUNTIME_COMMIT = "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"
WANDB_ORIGINAL_COMMIT = "b37a684"
RUNTIME_RECONSTRUCTION_LABEL = "USER_APPROVED_C18_RECONSTRUCTION"
EXPECTED_GPU_INDEX = "7"
EXPECTED_LOGICAL_GPU_INDEX = "0"
EXPECTED_GPU_UUID = "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d"
EXPECTED_GPU_BINDING_MODE = "single-visible-logical-cuda0-v3"
EXPECTED_CUDA_DEVICE_ORDER = "PCI_BUS_ID"
EXPECTED_NUM_ENVS = 64
EXPECTED_TOTAL_BATCHES = 10000
EXPECTED_TEACHER_CHECKPOINT = Path(
    "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/"
    "a2_piper_full_stage_a2_base/base_v19/"
    "base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
)
EXPECTED_TEACHER_CONFIG = EXPECTED_TEACHER_CHECKPOINT.with_name("config.yaml")

V19_RUNTIME_MODULES = {
    "gr00t.rl.envs.door.door_open_a2_base": "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t.rl.data.tasks.door.scenario_cfg.isaacsim": (
        "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"
    ),
    "gr00t.rl.isaac_utils.playground.env_rand.door": (
        "gr00t/rl/isaac_utils/playground/env_rand/door.py"
    ),
}
V19_RUNTIME_SCENARIO_MODULE = "gr00t.rl.data.tasks.door.scenario_cfg.isaacsim"
V19_RUNTIME_SCENARIO_RELATIVE_PATH = Path(V19_RUNTIME_MODULES[V19_RUNTIME_SCENARIO_MODULE])

TEACHER_VALIDATOR_MODULE = "gr00t.rl.scripts.validate_a2_teacher_checkpoint"


def validate_overlay_repository(repository: Path) -> Path:
    """Validate the branch-local package and entrypoint before package imports."""
    repository = repository.expanduser().resolve()
    if not repository.is_dir():
        raise FileNotFoundError(f"v19 overlay repository is unavailable: {repository}")
    package_root = repository / "gr00t"
    package_init = package_root / "__init__.py"
    train_entrypoint = package_root / "rl/train_agent_trl.py"
    teacher_validator = package_root / "rl/scripts/validate_a2_teacher_checkpoint.py"
    missing = [
        path
        for path in (package_init, train_entrypoint, teacher_validator)
        if not path.is_file() or not path.resolve().is_relative_to(repository)
    ]
    if missing:
        raise FileNotFoundError(
            "v19 overlay repository is missing required branch-local files: "
            f"{missing}"
        )
    return repository


def _module_locations(module, module_name: str) -> tuple[Path, ...]:
    locations = []
    module_file = getattr(module, "__file__", None)
    if module_file is not None:
        if not isinstance(module_file, str) or not module_file:
            raise RuntimeError(
                f"A2 overlay source identity cannot be verified for {module_name}: "
                f"invalid __file__={module_file!r}"
            )
        locations.append(Path(module_file).expanduser().resolve(strict=True))
    module_path = getattr(module, "__path__", None)
    if module_path is not None:
        for entry in module_path:
            locations.append(Path(entry).expanduser().resolve(strict=True))
    if not locations:
        raise RuntimeError(
            f"A2 overlay source identity cannot be verified for {module_name}: "
            "module has no concrete __file__ or __path__."
        )
    return tuple(locations)


def _require_module_under_overlay(module_name: str, module, overlay_repository: Path) -> None:
    expected_root = (overlay_repository / "gr00t").resolve(strict=True)
    locations = _module_locations(module, module_name)
    if any(not location.is_relative_to(expected_root) for location in locations):
        raise RuntimeError(
            "A2 overlay source identity mismatch: "
            f"{module_name} locations={list(locations)} expected under={expected_root}"
        )


def _remove_overlay_path_duplicates(overlay_repository: Path) -> None:
    def resolves_to_overlay(entry) -> bool:
        if not isinstance(entry, str):
            return False
        candidate = Path.cwd() if entry == "" else Path(entry).expanduser()
        try:
            return candidate.resolve() == overlay_repository
        except OSError:
            return False

    sys.path[:] = [entry for entry in sys.path if not resolves_to_overlay(entry)]
    sys.path.insert(0, str(overlay_repository))


def prepare_overlay_import(overlay_repository: Path) -> Path:
    """Make the requested overlay the sole highest-precedence gr00t source."""
    overlay_repository = validate_overlay_repository(overlay_repository)
    preloaded = [
        (name, module)
        for name, module in sys.modules.items()
        if name == "gr00t" or name.startswith("gr00t.")
    ]
    for name, module in preloaded:
        if module is None:
            raise RuntimeError(
                "A2 overlay source identity cannot be verified before mutation: "
                f"{name} is already reserved in sys.modules."
            )
        _require_module_under_overlay(name, module, overlay_repository)

    _remove_overlay_path_duplicates(overlay_repository)
    importlib.invalidate_caches()
    package = importlib.import_module("gr00t")
    _require_module_under_overlay("gr00t", package, overlay_repository)
    validator_spec = importlib.util.find_spec(TEACHER_VALIDATOR_MODULE)
    if validator_spec is None or validator_spec.origin in (None, "built-in"):
        raise ImportError(
            "v19 overlay Teacher validator cannot be resolved from the requested overlay: "
            f"{TEACHER_VALIDATOR_MODULE}"
        )
    validator_origin = Path(validator_spec.origin).resolve(strict=True)
    expected_validator_root = overlay_repository / "gr00t/rl/scripts"
    if not validator_origin.is_relative_to(expected_validator_root):
        raise RuntimeError(
            "A2 overlay source identity mismatch for Teacher validator: "
            f"origin={validator_origin} expected under={expected_validator_root}"
        )
    return overlay_repository


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def validate_runtime_repository(repository: Path) -> dict[str, Path]:
    repository = repository.expanduser().resolve()
    if not repository.is_dir():
        raise FileNotFoundError(f"v19 runtime repository is unavailable: {repository}")
    commit = _git(repository, "rev-parse", "HEAD")
    if commit != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError(
            f"v19 runtime commit mismatch: expected={EXPECTED_RUNTIME_COMMIT} actual={commit}"
        )
    dirty = _git(repository, "status", "--short", "--", "gr00t")
    if dirty:
        raise RuntimeError(f"v19 runtime gr00t source must be clean:\n{dirty}")
    module_sources = {}
    for module_name, relative_path in V19_RUNTIME_MODULES.items():
        source_path = (repository / relative_path).resolve()
        if not source_path.is_file() or not source_path.is_relative_to(repository):
            raise FileNotFoundError(f"v19 runtime module is unavailable: {source_path}")
        module_sources[module_name] = source_path
    return module_sources


def validate_gpu7_environment(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    """Require the complete binding-v3 schema before downstream imports run."""
    values = os.environ if environ is None else environ
    required = {
        "A2_GPU_BINDING_MODE": EXPECTED_GPU_BINDING_MODE,
        "CUDA_VISIBLE_DEVICES": EXPECTED_GPU_INDEX,
        "CUDA_DEVICE_ORDER": EXPECTED_CUDA_DEVICE_ORDER,
        "A2_EXPECTED_WORLD_SIZE": "1",
        "A2_EXPECTED_HOST_GPU_INDEX": EXPECTED_GPU_INDEX,
        "A2_EXPECTED_LOGICAL_GPU_INDEX": EXPECTED_LOGICAL_GPU_INDEX,
        "A2_EXPECTED_GPU_UUID": EXPECTED_GPU_UUID,
    }
    missing = [name for name in required if name not in values]
    if missing:
        raise RuntimeError(
            "v19 reconstruction requires the complete A2 binding-v3 schema; "
            f"missing={missing}"
        )
    mismatched = {
        name: (expected, values.get(name))
        for name, expected in required.items()
        if values.get(name) != expected
    }
    if mismatched:
        raise RuntimeError(
            "v19 reconstruction requires physical GPU7/logical CUDA0 binding-v3 values; "
            f"mismatched={mismatched}"
        )
    known_schema = set(required) | {"A2_GPU_BINDING_MODE"}
    unexpected = sorted(
        name
        for name in values
        if isinstance(name, str)
        and (name.startswith("A2_GPU_") or name.startswith("A2_EXPECTED_"))
        and name not in known_schema
    )
    if unexpected:
        raise RuntimeError(
            "v19 reconstruction rejects unknown A2 binding-v3 fields; "
            f"unexpected={unexpected}"
        )
    distributed_names = (
        "WORLD_SIZE",
        "RANK",
        "LOCAL_RANK",
        "LOCAL_WORLD_SIZE",
        "MASTER_ADDR",
        "MASTER_PORT",
    )
    present = [name for name in distributed_names if name in values]
    if present:
        raise RuntimeError(f"v19 reconstruction rejects distributed launch variables: {present}")
    externally_bound = ("ACCELERATE_TORCH_DEVICE", "ACCELERATE_BYPASS_DEVICE_MAP")
    present = [name for name in externally_bound if name in values]
    if present:
        raise RuntimeError(
            "v19 reconstruction rejects externally pre-bound Accelerate device variables: "
            f"{present}"
        )
    return {
        "mode": EXPECTED_GPU_BINDING_MODE,
        "world_size": 1,
        "host_gpu_index": int(EXPECTED_GPU_INDEX),
        "logical_gpu_index": int(EXPECTED_LOGICAL_GPU_INDEX),
        "pinned_uuid": EXPECTED_GPU_UUID,
    }


def _exact_hydra_override(hydra_args: list[str], key: str, expected: int) -> None:
    matches = []
    for argument in hydra_args:
        normalized = argument[1:] if argument.startswith("+") else argument
        if normalized.startswith(f"{key}="):
            matches.append(normalized.split("=", 1)[1])
    if len(matches) != 1 or matches[0] != str(expected):
        raise ValueError(
            f"v19 launch requires exactly one Hydra override {key}={expected}; got {matches!r}"
        )


def _reject_mismatched_teacher_overrides(
    hydra_args: list[str], teacher_paths: dict[str, Path]
) -> None:
    for key, expected_path in teacher_paths.items():
        for argument in hydra_args:
            normalized = argument[1:] if argument.startswith("+") else argument
            if normalized.startswith(f"{key}="):
                supplied = Path(normalized.split("=", 1)[1]).expanduser().resolve()
                if supplied != expected_path:
                    raise ValueError(
                        f"v19 Teacher override {key} must select {expected_path}; got {supplied}"
                    )


def validate_teacher_triplet(
    checkpoint_path: Path, config_path: Path, manifest_path: Path
) -> dict:
    checkpoint_path = checkpoint_path.expanduser().resolve()
    config_path = config_path.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()
    if checkpoint_path != EXPECTED_TEACHER_CHECKPOINT.resolve():
        raise ValueError(
            "v19 Teacher checkpoint must be the user-selected model_step_002000.pt; "
            f"got {checkpoint_path}"
        )
    if config_path != EXPECTED_TEACHER_CONFIG.resolve():
        raise ValueError(
            "v19 Teacher config must be adjacent config.yaml for the selected checkpoint; "
            f"got {config_path}"
        )
    validator_module = importlib.import_module(TEACHER_VALIDATOR_MODULE)
    package = sys.modules.get("gr00t")
    if package is None:
        raise RuntimeError("A2 overlay package must be prepared before Teacher validation")
    _require_module_under_overlay("gr00t", package, Path(package.__path__[0]).resolve().parent)
    _require_module_under_overlay(
        TEACHER_VALIDATOR_MODULE,
        validator_module,
        Path(package.__path__[0]).resolve().parent,
    )
    return validator_module.validate_teacher_artifact(checkpoint_path, config_path, manifest_path)


class V19RuntimeFinder(importlib.abc.MetaPathFinder):
    """Load only the audited c18 task modules after AppLauncher starts."""

    def __init__(self, module_sources: dict[str, Path]):
        self._module_sources = module_sources

    def find_spec(self, fullname, path, target=None):
        del path, target
        source_path = self._module_sources.get(fullname)
        if source_path is None:
            return None
        if fullname in sys.modules:
            raise RuntimeError(f"v19 runtime module was imported before its overlay: {fullname}")
        spec = importlib.util.spec_from_file_location(fullname, source_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"unable to load v19 runtime module: {source_path}")
        return spec


def install_v19_runtime_scenario_file_pin(module_sources: dict[str, Path]) -> Path:
    """Pin c18's legacy cwd-relative door scenario loader to the sealed source."""
    current_loader = importlib.util.spec_from_file_location
    if getattr(current_loader, "_a2_v19_scenario_pin", False):
        raise RuntimeError("v19 runtime scenario file pin is already installed")
    pinned_source = module_sources[V19_RUNTIME_SCENARIO_MODULE].resolve(strict=True)

    def pinned_spec_from_file_location(
        name,
        location,
        *,
        loader=None,
        submodule_search_locations=None,
    ):
        if (
            name == "door"
            and isinstance(location, (str, os.PathLike))
            and os.fspath(location) == os.fspath(V19_RUNTIME_SCENARIO_RELATIVE_PATH)
        ):
            location = pinned_source
        return current_loader(
            name,
            location,
            loader=loader,
            submodule_search_locations=submodule_search_locations,
        )

    pinned_spec_from_file_location._a2_v19_scenario_pin = True
    importlib.util.spec_from_file_location = pinned_spec_from_file_location
    return pinned_source


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-repository", type=Path, required=True)
    parser.add_argument("--overlay-repository", type=Path, required=True)
    parser.add_argument("--teacher-actor-path", type=Path, required=True)
    parser.add_argument("--teacher-config-path", type=Path, required=True)
    parser.add_argument("--teacher-manifest-path", type=Path, required=True)
    args, hydra_args = parser.parse_known_args()
    if hydra_args[:1] == ["--"]:
        hydra_args = hydra_args[1:]
    if not hydra_args:
        raise ValueError("v19 Student distillation bootstrap requires Hydra overrides")
    return args, hydra_args


def main() -> int:
    args, hydra_args = parse_args()
    overlay_repository = prepare_overlay_import(args.overlay_repository)
    train_entrypoint = overlay_repository / "gr00t/rl/train_agent_trl.py"
    if not train_entrypoint.is_file():
        raise FileNotFoundError(f"branch-local training entrypoint is missing: {train_entrypoint}")
    gpu_binding = validate_gpu7_environment()
    _exact_hydra_override(hydra_args, "num_envs", EXPECTED_NUM_ENVS)
    _exact_hydra_override(hydra_args, "algo.trl.num_total_batches", EXPECTED_TOTAL_BATCHES)
    teacher_paths = {
        "teacher_actor_path": args.teacher_actor_path.expanduser().resolve(),
        "teacher_config_path": args.teacher_config_path.expanduser().resolve(),
        "teacher_manifest_path": args.teacher_manifest_path.expanduser().resolve(),
    }
    _reject_mismatched_teacher_overrides(hydra_args, teacher_paths)
    validate_teacher_triplet(
        teacher_paths["teacher_actor_path"],
        teacher_paths["teacher_config_path"],
        teacher_paths["teacher_manifest_path"],
    )
    module_sources = validate_runtime_repository(args.runtime_repository)
    already_loaded = sorted(set(module_sources).intersection(sys.modules))
    if already_loaded:
        raise RuntimeError(f"v19 runtime modules were imported before AppLauncher: {already_loaded}")

    # Bind the validated immutable artifact paths into the Hydra config. The
    # explicit CLI values above remain the only accepted Teacher selection.
    teacher_keys = tuple(teacher_paths)
    hydra_args = [
        argument
        for argument in hydra_args
        if (argument[1:] if argument.startswith("+") else argument).split("=", 1)[0]
        not in teacher_keys
    ]
    hydra_args.extend(f"{key}={value}" for key, value in teacher_paths.items())
    scenario_file_pin = install_v19_runtime_scenario_file_pin(module_sources)
    sys.meta_path.insert(0, V19RuntimeFinder(module_sources))
    os.chdir(overlay_repository)
    print(
        "[A2_V19_RUNTIME] "
        f"reconstruction={RUNTIME_RECONSTRUCTION_LABEL} "
        f"runtime_commit={EXPECTED_RUNTIME_COMMIT} "
        f"wandb_original_commit={WANDB_ORIGINAL_COMMIT} "
        f"gpu={EXPECTED_GPU_INDEX} num_envs={EXPECTED_NUM_ENVS} "
        f"total_batches={EXPECTED_TOTAL_BATCHES} "
        f"binding_mode={gpu_binding['mode']} logical_cuda={gpu_binding['logical_gpu_index']} "
        f"uuid={gpu_binding['pinned_uuid']} overlay_repository={overlay_repository} "
        f"scenario_file_pin={scenario_file_pin}",
        flush=True,
    )
    sys.argv = [str(train_entrypoint), *hydra_args]
    runpy.run_path(str(train_entrypoint), run_name="__main__")
    validate_runtime_repository(args.runtime_repository)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
