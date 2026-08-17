#!/usr/bin/env python3
"""C-B2H v19 P1 packed-vs-sequential training contract and launcher.

The P1 experiment is deliberately narrow: both branches start from the exact
original Student step-10000 artifact and use the same c18/G2/64-environment
training contract.  The only model behavior variable is the D435 forward
mode.  This module keeps all contract validation and open-loop adjudication
CPU-safe.  IsaacSim is reached only with the explicit ``--execute`` command;
``--dry-run`` never creates an output directory or imports the simulator.

The runner is intentionally fail-fast.  It does not discover checkpoints,
resume from ``last.pt``, lower the environment count, retry in-place, or turn a
resource failure into a sequential success.  A failed execution keeps its
partial evidence; a retry must use a new output root.
"""

from __future__ import annotations

import argparse
import builtins
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import threading
import time
import types
import uuid
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SOURCE_CHECKPOINT = (
    REPO_ROOT
    / "logs_rl/cb2h_v19_distill/"
    "cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/model_step_010000.pt"
).resolve()
SOURCE_CONFIG = SOURCE_CHECKPOINT.with_name("config.yaml")
SOURCE_CHECKPOINT_SHA256 = (
    "005705dc033605a24bc231b18fbfaabe3288a699130a7ce2e423eac736963a45"
)
SOURCE_CONFIG_SHA256 = "24f94faeca0270928c9c3ff33568e50371dc4f2f3feb767f6fe0607bb084351f"

TEACHER_CHECKPOINT = Path(
    "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/"
    "a2_piper_full_stage_a2_base/base_v19/"
    "base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
).resolve()
TEACHER_CONFIG = TEACHER_CHECKPOINT.with_name("config.yaml")
TEACHER_MANIFEST = (
    REPO_ROOT
    / "logs_rl/cb2h_v19_runtime/g2_step2000_c18_reconstruction_candidate6168e6a2/"
    "teacher_manifest.json"
).resolve()
TEACHER_CHECKPOINT_SHA256 = "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d"
TEACHER_CONFIG_SHA256 = "65c1537b38d670097bc8498428e0aad1705c3fd66eeef41a93d63e3b6da4cf96"
TEACHER_MANIFEST_SHA256 = "479f4460d4dc05feea9d87d3189fa0617b21078f91b6f5176f4a9c41b141d1b7"
TEACHER_GLOBAL_STEP = 2000

RUNTIME_REPOSITORY = Path("/tmp/cb2h_v19_runtime.waPJHftX/c18").resolve()
EXPECTED_RUNTIME_COMMIT = "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"
EXPECTED_GPU_INDEX = "7"
EXPECTED_LOGICAL_GPU_INDEX = "0"
EXPECTED_GPU_UUID = "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d"
EXPECTED_GPU_BINDING_MODE = "single-visible-logical-cuda0-v3"
EXPECTED_CUDA_DEVICE_ORDER = "PCI_BUS_ID"
EXPECTED_LOGICAL_DEVICE = "cuda:0"
EXPECTED_NUM_ENVS = 64
EXPECTED_EPISODES = 16
EXPECTED_ACTIVE_FRAME_COUNT = 10206
EXPECTED_ACTION_DIM = 12
EXPECTED_INITIAL_GLOBAL_STEP = 10000
INITIAL_ITERATIONS = 200
EXTENDED_ITERATIONS = 500
INITIAL_TARGET_GLOBAL_STEP = EXPECTED_INITIAL_GLOBAL_STEP + INITIAL_ITERATIONS
EXTENDED_TARGET_GLOBAL_STEP = EXPECTED_INITIAL_GLOBAL_STEP + EXTENDED_ITERATIONS
EXTENSION_ITERATIONS = EXTENDED_ITERATIONS - INITIAL_ITERATIONS
VRAM_LIMIT_MIB = 46 * 1024
P1_SCHEMA = "a2_cb2h_pro_p1_v1"
P1_BRANCH_SCHEMA = "a2_cb2h_pro_p1_branch_manifest_v1"
P1_ADJUDICATION_SCHEMA = "a2_cb2h_pro_p1_adjudication_manifest_v1"
P1_FORWARD_MODES = ("sequential", "packed")
P1_BRANCHES = P1_FORWARD_MODES
TARGET_EXPERIMENT = "wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm"
TARGET_CONFIG = (
    REPO_ROOT
    / "gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm.yaml"
).resolve()
N3_INPUT_ROOT = (
    REPO_ROOT / "logs_eval/cb2h_pro_phase_a_n3_teacher_trajectories_gpu7-retry1-20260802"
).resolve()
N3_PHASE_MANIFEST = N3_INPUT_ROOT / "phase_a_manifest.json"
N3_PHASE_MANIFEST_SHA256 = "0d5cfec4dc06a47c28b69bbcd14c9ad6216e8bccbbb956848e6dccb1b419077e"
N2_INPUT_ROOT = (
    REPO_ROOT / "logs_eval/cb2h_pro_phase_a_n2_student_sweep_gpu7-20260802"
).resolve()
N2_PHASE_MANIFEST = N2_INPUT_ROOT / "phase_a_manifest.json"
N2_PHASE_MANIFEST_SHA256 = "a7e17388f2f51ea12d6137bd6d2e6fe48b2078e0907b409a1c02ce1fa1bbe700"
P1_BRANCH_MANIFEST_FILENAME = "p1_branch_manifest.json"
P1_FORMAL_REPLICATE_MANIFEST_FILENAME = "p1_formal_replicate_manifest.json"
P1_N3_ACTION_MANIFEST_FILENAME = "p1_n3_action_manifest.json"
P1_RUNTIME_METRICS_SCHEMA = "a2_cb2h_pro_p1_runtime_metrics_v2"
P1_GPU_TELEMETRY_SCHEMA = "a2_cb2h_pro_p1_gpu_telemetry_v2"
P1_N3_ACTION_SCHEMA = "a2_cb2h_pro_p1_n3_action_manifest_v2"
# The pre-teardown proof is the lifecycle artifact.  Keep the historical
# constant names as aliases so existing CPU-side consumers cannot silently
# select a post-teardown record.
P1_PRE_TEARDOWN_PROOF_SCHEMA = "a2_cb2h_pro_p1_pre_teardown_completion_v1"
P1_PRE_TEARDOWN_PROOF_FILENAME = "pre_teardown_completion_proof.json"
P1_RUNTIME_LIFECYCLE_SCHEMA = P1_PRE_TEARDOWN_PROOF_SCHEMA
P1_RUNTIME_LIFECYCLE_FILENAME = P1_PRE_TEARDOWN_PROOF_FILENAME
P1_RUNTIME_METRICS_FILENAME = "runtime_metrics.json"
P1_GPU_TELEMETRY_FILENAME = "gpu_telemetry.json"
P1_EFFECTIVE_NUM_MINI_BATCHES = 4
P1_EFFECTIVE_NUM_PPO_EPOCHS = 1
P1_EFFECTIVE_NUM_MICRO_BATCHES = 1
P1_COMMON_INIT_CONTRACT = {
    "num_envs": EXPECTED_NUM_ENVS,
    "num_steps_per_env": 8,
    "num_mini_batches": 4,
    "actor_learning_rate": 1.0e-4,
    "use_a2_base": True,
    "ratio_teacher_rollout": 1.0,
    "enforce_teacher_rollout": True,
    "checkpoint_load_mode": "full",
    "auto_load_latest": False,
}

_STEP_PATTERN = re.compile(r"(?:^|/)model_step_(\d+)\.pt$")
_ALLOWED_DISTRIBUTED_NAMES = {
    "WORLD_SIZE",
    "RANK",
    "LOCAL_RANK",
    "LOCAL_WORLD_SIZE",
    "MASTER_ADDR",
    "MASTER_PORT",
}
_FORBIDDEN_DEVICE_NAMES = {
    "ACCELERATE_TORCH_DEVICE",
    "ACCELERATE_BYPASS_DEVICE_MAP",
    "ACCELERATE_USE_CPU",
    "ACCELERATE_MIXED_PRECISION",
    "ACCELERATE_DYNAMO_BACKEND",
}
_RUNTIME_REQUIRED_RELATIVE_PATHS = (
    Path("gr00t/rl/train_agent_trl.py"),
    Path("gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"),
)


class P1Blocked(RuntimeError):
    """A resource or evidence gate blocks the experiment without fallback."""


@dataclass(frozen=True)
class ArtifactRef:
    path: Path
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {"path": str(self.path), "sha256": self.sha256}


@dataclass(frozen=True)
class P1BranchSpec:
    mode: str
    root: Path
    checkpoint: Path
    checkpoint_sha256: str
    checkpoint_config: Path
    checkpoint_config_sha256: str
    start_global_step: int
    requested_iterations: int
    run_iterations: int
    target_global_step: int
    overrides: tuple[str, ...]
    command: tuple[str, ...]
    source_manifest_root: Path | None = None
    source_manifest_sha256: str | None = None

    @property
    def final_checkpoint(self) -> Path:
        return self.root / f"model_step_{self.target_global_step:06d}.pt"

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "root": str(self.root),
            "checkpoint": ArtifactRef(self.checkpoint, self.checkpoint_sha256).as_dict(),
            "checkpoint_config": ArtifactRef(
                self.checkpoint_config, self.checkpoint_config_sha256
            ).as_dict(),
            "start_global_step": self.start_global_step,
            "requested_iterations": self.requested_iterations,
            "run_iterations": self.run_iterations,
            "target_global_step": self.target_global_step,
            "overrides": list(self.overrides),
            "command": list(self.command),
            "source_manifest_root": None if self.source_manifest_root is None else str(self.source_manifest_root),
            "source_manifest_sha256": self.source_manifest_sha256,
        }


@dataclass(frozen=True)
class P1Plan:
    root: Path
    requested_iterations: int
    branches: tuple[P1BranchSpec, P1BranchSpec]
    paired_extension: bool
    contract: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": P1_SCHEMA,
            "root": str(self.root),
            "requested_iterations": self.requested_iterations,
            "paired_extension": self.paired_extension,
            "contract": dict(self.contract),
            "branches": [branch.as_dict() for branch in self.branches],
        }


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    path = path.expanduser().resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


P1_COMMON_INIT_CONTRACT_SHA256 = sha256_bytes(
    canonical_json(P1_COMMON_INIT_CONTRACT).encode("utf-8")
)


def _load_json(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=True)
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"JSON artifact must be an object: {path}")
    return value


def _require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA256 string")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name} is not hexadecimal SHA256") from exc
    return value


def _expected_path(path: Path, expected: Path, name: str) -> Path:
    actual = path.expanduser().resolve()
    expected = expected.expanduser().resolve()
    if actual != expected:
        raise RuntimeError(f"{name} must be the exact sealed path {expected}; got {actual}")
    return actual


def _assert_hash(path: Path, expected: str, name: str) -> str:
    expected = _require_sha(expected, name)
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"{name} SHA256 drifted: expected={expected} actual={actual}")
    return actual


def _step_from_checkpoint(path: Path) -> int:
    match = _STEP_PATTERN.search(path.as_posix())
    if match is None:
        raise ValueError(f"checkpoint filename must encode model_step_NNNNNN.pt: {path}")
    return int(match.group(1))


def validate_source_checkpoint(
    checkpoint: Path = SOURCE_CHECKPOINT,
    config_path: Path = SOURCE_CONFIG,
    *,
    expected_checkpoint_sha256: str = SOURCE_CHECKPOINT_SHA256,
    expected_config_sha256: str = SOURCE_CONFIG_SHA256,
) -> dict[str, Any]:
    """Validate the immutable original Student step-10000 full checkpoint."""
    checkpoint = _expected_path(checkpoint, SOURCE_CHECKPOINT, "source checkpoint")
    config_path = _expected_path(config_path, SOURCE_CONFIG, "source config")
    if not checkpoint.is_file() or not config_path.is_file():
        raise FileNotFoundError("exact P1 source checkpoint/config is unavailable")
    checkpoint_sha = _assert_hash(checkpoint, expected_checkpoint_sha256, "source checkpoint")
    config_sha = _assert_hash(config_path, expected_config_sha256, "source config")
    global_step = _step_from_checkpoint(checkpoint)
    if global_step != EXPECTED_INITIAL_GLOBAL_STEP:
        raise RuntimeError(f"P1 source must start at global_step 10000; got {global_step}")
    text = config_path.read_text(encoding="utf-8")
    if "checkpoint_load_mode: full" not in text:
        raise RuntimeError("P1 source config must select checkpoint_load_mode: full")
    if "auto_load_latest: false" not in text:
        raise RuntimeError("P1 source config must disable auto_load_latest")
    return {
        "path": str(checkpoint),
        "sha256": checkpoint_sha,
        "config_path": str(config_path),
        "config_sha256": config_sha,
        "global_step": global_step,
        "checkpoint_load_mode": "full",
        "auto_load_latest": False,
    }


def validate_branch_checkpoint(
    checkpoint: Path,
    config_path: Path,
    *,
    expected_checkpoint_sha256: str,
    expected_config_sha256: str,
    expected_global_step: int,
) -> dict[str, Any]:
    """Validate a sealed branch checkpoint used only for the paired extension."""
    checkpoint = checkpoint.expanduser().resolve(strict=True)
    config_path = config_path.expanduser().resolve(strict=True)
    if not checkpoint.is_file() or not config_path.is_file():
        raise FileNotFoundError("P1 branch extension checkpoint/config is unavailable")
    checkpoint_sha = _assert_hash(
        checkpoint, expected_checkpoint_sha256, "P1 branch checkpoint"
    )
    config_sha = _assert_hash(config_path, expected_config_sha256, "P1 branch config")
    global_step = _step_from_checkpoint(checkpoint)
    if global_step != expected_global_step:
        raise RuntimeError(
            f"P1 extension checkpoint must start at global_step {expected_global_step}; got {global_step}"
        )
    config_text = config_path.read_text(encoding="utf-8")
    if "checkpoint_load_mode: full" not in config_text:
        raise RuntimeError("P1 extension config must select checkpoint_load_mode: full")
    if "auto_load_latest: false" not in config_text:
        raise RuntimeError("P1 extension config must disable auto_load_latest")
    return {
        "path": str(checkpoint),
        "sha256": checkpoint_sha,
        "config_path": str(config_path),
        "config_sha256": config_sha,
        "global_step": global_step,
        "checkpoint_load_mode": "full",
        "auto_load_latest": False,
    }


def validate_teacher_triplet(
    checkpoint: Path = TEACHER_CHECKPOINT,
    config_path: Path = TEACHER_CONFIG,
    manifest_path: Path = TEACHER_MANIFEST,
    *,
    expected_checkpoint_sha256: str = TEACHER_CHECKPOINT_SHA256,
    expected_config_sha256: str = TEACHER_CONFIG_SHA256,
    expected_manifest_sha256: str = TEACHER_MANIFEST_SHA256,
) -> dict[str, Any]:
    """Validate the exact G2 step-2000 Teacher triplet and manifest binding."""
    checkpoint = _expected_path(checkpoint, TEACHER_CHECKPOINT, "Teacher checkpoint")
    config_path = _expected_path(config_path, TEACHER_CONFIG, "Teacher config")
    manifest_path = _expected_path(manifest_path, TEACHER_MANIFEST, "Teacher manifest")
    for path in (checkpoint, config_path, manifest_path):
        if not path.is_file():
            raise FileNotFoundError(f"Teacher artifact is unavailable: {path}")
    checkpoint_sha = _assert_hash(checkpoint, expected_checkpoint_sha256, "Teacher checkpoint")
    config_sha = _assert_hash(config_path, expected_config_sha256, "Teacher config")
    manifest_sha = _assert_hash(manifest_path, expected_manifest_sha256, "Teacher manifest")
    if _step_from_checkpoint(checkpoint) != TEACHER_GLOBAL_STEP:
        raise RuntimeError("P1 Teacher checkpoint must be model_step_002000.pt")
    manifest = _load_json(manifest_path)
    checkpoint_info = manifest.get("checkpoint")
    source_info = manifest.get("source")
    teacher_info = manifest.get("teacher")
    if not isinstance(checkpoint_info, Mapping) or not isinstance(source_info, Mapping):
        raise RuntimeError("G2 Teacher manifest is missing checkpoint/source provenance")
    if checkpoint_info.get("filename") != checkpoint.name:
        raise RuntimeError("G2 Teacher manifest checkpoint filename drifted")
    if checkpoint_info.get("sha256") != checkpoint_sha:
        raise RuntimeError("G2 Teacher manifest checkpoint SHA256 drifted")
    if source_info.get("config_sha256") != config_sha:
        raise RuntimeError("G2 Teacher manifest config SHA256 drifted")
    if source_info.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError("G2 Teacher manifest runtime commit drifted")
    if not isinstance(teacher_info, Mapping) or int(teacher_info.get("action_dim", -1)) != 12:
        raise RuntimeError("G2 Teacher manifest must describe action_dim=12")
    return {
        "checkpoint": ArtifactRef(checkpoint, checkpoint_sha).as_dict(),
        "config": ArtifactRef(config_path, config_sha).as_dict(),
        "manifest": ArtifactRef(manifest_path, manifest_sha).as_dict(),
        "global_step": TEACHER_GLOBAL_STEP,
        "runtime_commit": EXPECTED_RUNTIME_COMMIT,
    }


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_runtime_contract(repository: Path = RUNTIME_REPOSITORY) -> dict[str, Any]:
    """Require the immutable c18 runtime and required task sources."""
    repository = repository.expanduser().resolve()
    if not repository.is_dir():
        raise FileNotFoundError(f"c18 runtime repository is unavailable: {repository}")
    commit = _git(repository, "rev-parse", "HEAD")
    if commit != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError(f"c18 runtime commit mismatch: expected={EXPECTED_RUNTIME_COMMIT} actual={commit}")
    dirty = _git(repository, "status", "--short", "--", "gr00t")
    if dirty:
        raise RuntimeError(f"c18 runtime gr00t source must be clean:\n{dirty}")
    missing = []
    for relative in _RUNTIME_REQUIRED_RELATIVE_PATHS:
        path = (repository / relative).resolve()
        if not path.is_file() or not path.is_relative_to(repository):
            missing.append(path)
    if missing:
        raise FileNotFoundError(f"c18 runtime required sources are unavailable: {missing}")
    return {
        "repository": str(repository),
        "commit": commit,
        "clean_gr00t": True,
        "required_sources": [str(repository / path) for path in _RUNTIME_REQUIRED_RELATIVE_PATHS],
    }


def validate_gpu_binding_environment(environ: Mapping[str, str]) -> dict[str, Any]:
    """Require physical GPU7, logical cuda:0, and world size one."""
    required = {
        "CUDA_VISIBLE_DEVICES": EXPECTED_GPU_INDEX,
        "CUDA_DEVICE_ORDER": EXPECTED_CUDA_DEVICE_ORDER,
        "A2_GPU_BINDING_MODE": EXPECTED_GPU_BINDING_MODE,
        "A2_EXPECTED_WORLD_SIZE": "1",
        "A2_EXPECTED_HOST_GPU_INDEX": EXPECTED_GPU_INDEX,
        "A2_EXPECTED_LOGICAL_GPU_INDEX": EXPECTED_LOGICAL_GPU_INDEX,
        "A2_EXPECTED_GPU_UUID": EXPECTED_GPU_UUID,
    }
    mismatched = {
        key: (expected, environ.get(key))
        for key, expected in required.items()
        if environ.get(key) != expected
    }
    if mismatched:
        raise RuntimeError(f"P1 requires physical GPU7/logical cuda:0 binding-v3: {mismatched}")
    distributed = sorted(name for name in _ALLOWED_DISTRIBUTED_NAMES if name in environ)
    if distributed:
        raise RuntimeError(f"P1 rejects distributed launch variables: {distributed}")
    external = sorted(name for name in _FORBIDDEN_DEVICE_NAMES if name in environ)
    if external:
        raise RuntimeError(f"P1 rejects externally bound Accelerate/device variables: {external}")
    unknown = sorted(
        name
        for name in environ
        if isinstance(name, str)
        and (name.startswith("A2_GPU_") or name.startswith("A2_EXPECTED_"))
        and name not in required
    )
    if unknown:
        raise RuntimeError(f"P1 rejects unknown A2 binding fields: {unknown}")
    return {
        "physical_gpu_index": EXPECTED_GPU_INDEX,
        "logical_gpu_index": int(EXPECTED_LOGICAL_GPU_INDEX),
        "logical_device": EXPECTED_LOGICAL_DEVICE,
        "uuid": EXPECTED_GPU_UUID,
        "world_size": 1,
        "binding_mode": EXPECTED_GPU_BINDING_MODE,
    }


def build_gpu_binding_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build the exact child environment; no inherited distributed fallback is allowed."""
    environment = dict(os.environ if base is None else base)
    for key in list(environment):
        if key in _ALLOWED_DISTRIBUTED_NAMES or key in _FORBIDDEN_DEVICE_NAMES:
            environment.pop(key, None)
        elif key.startswith("A2_GPU_") or key.startswith("A2_EXPECTED_"):
            environment.pop(key, None)
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": EXPECTED_GPU_INDEX,
            "CUDA_DEVICE_ORDER": EXPECTED_CUDA_DEVICE_ORDER,
            "A2_GPU_BINDING_MODE": EXPECTED_GPU_BINDING_MODE,
            "A2_EXPECTED_WORLD_SIZE": "1",
            "A2_EXPECTED_HOST_GPU_INDEX": EXPECTED_GPU_INDEX,
            "A2_EXPECTED_LOGICAL_GPU_INDEX": EXPECTED_LOGICAL_GPU_INDEX,
            "A2_EXPECTED_GPU_UUID": EXPECTED_GPU_UUID,
        }
    )
    validate_gpu_binding_environment(environment)
    return environment


def _normalise_override(argument: str) -> tuple[str, str]:
    if not isinstance(argument, str):
        raise TypeError(f"Hydra override must be a string, got {type(argument).__name__}")
    normalized = argument[1:] if argument.startswith("+") else argument
    if "=" not in normalized:
        raise ValueError(f"Hydra override must be key=value: {argument!r}")
    key, value = normalized.split("=", 1)
    if not key or not value:
        raise ValueError(f"Hydra override must have non-empty key/value: {argument!r}")
    return key, value


def override_map(overrides: Sequence[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for argument in overrides:
        key, value = _normalise_override(argument)
        if key in values:
            raise ValueError(f"duplicate Hydra override: {key}")
        values[key] = value
    return values


def _path_value(values: Mapping[str, str], key: str) -> Path:
    return Path(values[key]).expanduser().resolve()


def validate_training_override_contract(
    overrides: Sequence[str],
    *,
    mode: str,
    branch_root: Path,
    checkpoint: Path,
    teacher: Mapping[str, Path],
    iterations: int,
    expected_start_global_step: int = EXPECTED_INITIAL_GLOBAL_STEP,
    run_iterations: int | None = None,
) -> dict[str, str]:
    """Validate the effective P1 training contract represented by Hydra args."""
    if mode not in P1_FORWARD_MODES:
        raise ValueError(f"mode must be one of {P1_FORWARD_MODES}; got {mode!r}")
    if iterations not in (INITIAL_ITERATIONS, EXTENDED_ITERATIONS):
        raise ValueError("P1 requested iterations must be exactly 200 or 500")
    if run_iterations is not None and run_iterations not in (
        INITIAL_ITERATIONS,
        EXTENSION_ITERATIONS,
    ):
        raise ValueError("P1 run_iterations must be exactly 200 or 300")
    batch_count = iterations if run_iterations is None else run_iterations
    if iterations == EXTENDED_ITERATIONS and (
        expected_start_global_step != INITIAL_TARGET_GLOBAL_STEP
        or batch_count != EXTENSION_ITERATIONS
    ):
        raise ValueError(
            "P1 500-step execution requires a sealed 200-step start at global_step 10200 "
            "and exactly 300 additional batches"
        )
    if iterations == INITIAL_ITERATIONS and expected_start_global_step != EXPECTED_INITIAL_GLOBAL_STEP:
        raise ValueError("P1 200-step execution must start from global_step 10000")
    target_global_step = expected_start_global_step + batch_count
    values = override_map(overrides)
    expected = {
        "num_envs": str(EXPECTED_NUM_ENVS),
        "algo.trl.num_total_batches": str(target_global_step),
        "callbacks.model_save.save_frequency": str(target_global_step),
        "experiment_dir": str(branch_root.expanduser().resolve()),
        "checkpoint": str(checkpoint.expanduser().resolve()),
        "checkpoint_load_mode": "full",
        "auto_load_latest": "false",
        "use_wandb": "false",
        "headless": "true",
        "teacher_actor_path": str(teacher["teacher_actor_path"].expanduser().resolve()),
        "teacher_config_path": str(teacher["teacher_config_path"].expanduser().resolve()),
        "teacher_manifest_path": str(teacher["teacher_manifest_path"].expanduser().resolve()),
        "algo.config.use_a2_base": "true",
        "algo.config.enforce_teacher_rollout": "true",
        "algo.config.ratio_teacher_rollout": "1.0",
        "algo.config.actor.view_contract.d435i_forward_mode": mode,
    }
    for key, wanted in expected.items():
        if values.get(key) != wanted:
            raise RuntimeError(f"P1 override contract drift for {key}: expected={wanted!r} got={values.get(key)!r}")
    serialized_values = canonical_json(values).lower()
    if "last.pt" in serialized_values or "resume" in serialized_values or values.get("auto_load_latest") != "false":
        raise RuntimeError("P1 forbids checkpoint discovery/resume/last.pt fallback")
    if _step_from_checkpoint(checkpoint) != expected_start_global_step:
        raise RuntimeError(
            f"branch checkpoint global_step must be {expected_start_global_step}; got {_step_from_checkpoint(checkpoint)}"
        )
    if target_global_step not in (INITIAL_TARGET_GLOBAL_STEP, EXTENDED_TARGET_GLOBAL_STEP):
        raise ValueError(f"P1 target global_step is invalid: {target_global_step}")
    return values


def canonical_branch_contract(
    overrides: Sequence[str], *, allow_distinct_start_checkpoint: bool = False
) -> dict[str, str]:
    """Return branch-effective values with only mode/root differences removed."""
    values = override_map(overrides)
    for key in (
        "algo.config.actor.view_contract.d435i_forward_mode",
        "experiment_dir",
    ):
        values.pop(key, None)
    if allow_distinct_start_checkpoint:
        values.pop("checkpoint", None)
    return values


def validate_branch_pair(
    sequential: P1BranchSpec,
    packed: P1BranchSpec,
    *,
    requested_iterations: int,
    allow_distinct_start_checkpoint: bool = False,
) -> None:
    """Prove paired branches differ only in D435 forward mode and root."""
    if sequential.mode != "sequential" or packed.mode != "packed":
        raise RuntimeError("P1 pair must contain exactly sequential and packed branches")
    if sequential.root == packed.root:
        raise RuntimeError("P1 branches require unique output roots")
    if sequential.checkpoint != packed.checkpoint and not allow_distinct_start_checkpoint:
        raise RuntimeError("P1 branches must use the same source checkpoint")
    if sequential.checkpoint_sha256 != packed.checkpoint_sha256 and not allow_distinct_start_checkpoint:
        raise RuntimeError("P1 branches must use the same source checkpoint SHA256")
    if sequential.start_global_step != packed.start_global_step:
        raise RuntimeError("P1 branches must start at the same global_step")
    if sequential.requested_iterations != requested_iterations or packed.requested_iterations != requested_iterations:
        raise RuntimeError("P1 branches must request the same iteration count")
    if sequential.run_iterations != packed.run_iterations:
        raise RuntimeError("P1 paired branches must run the same number of batches")
    if sequential.target_global_step != packed.target_global_step:
        raise RuntimeError("P1 paired branches must target the same global_step")
    if canonical_branch_contract(
        sequential.overrides,
        allow_distinct_start_checkpoint=allow_distinct_start_checkpoint,
    ) != canonical_branch_contract(
        packed.overrides,
        allow_distinct_start_checkpoint=allow_distinct_start_checkpoint,
    ):
        raise RuntimeError("P1 branches differ in a contract field other than forward mode/root")
    seq_values = override_map(sequential.overrides)
    packed_values = override_map(packed.overrides)
    if seq_values.get("algo.config.actor.view_contract.d435i_forward_mode") != "sequential":
        raise RuntimeError("sequential branch mode override is missing")
    if packed_values.get("algo.config.actor.view_contract.d435i_forward_mode") != "packed":
        raise RuntimeError("packed branch mode override is missing")


def validate_fresh_output_root(root: Path) -> Path:
    root = root.expanduser().resolve()
    if root in {
        Path("/"),
        Path("/tmp"),
        Path("/home"),
        Path.cwd().resolve(),
        REPO_ROOT,
    }:
        raise RuntimeError(f"P1 output root is unsafe: {root}")
    if root.exists():
        raise RuntimeError(f"P1 output root must be fresh and absent: {root}")
    return root


def validate_retry_root(previous_root: Path, retry_root: Path) -> tuple[Path, Path]:
    previous_root = previous_root.expanduser().resolve()
    retry_root = retry_root.expanduser().resolve()
    if previous_root == retry_root:
        raise RuntimeError("P1 retry must use a new output root")
    if retry_root.is_relative_to(previous_root) or previous_root.is_relative_to(retry_root):
        raise RuntimeError("P1 retry root must not overlap the previous evidence root")
    if not previous_root.is_dir():
        raise RuntimeError("P1 retry requires the previous failed evidence root to remain present")
    validate_fresh_output_root(retry_root)
    return previous_root, retry_root


def _sealed_artifact(
    value: Any,
    *,
    name: str,
    root: Path | None = None,
    expected_path: Path | None = None,
) -> dict[str, Any]:
    """Validate one path/hash object without coercing malformed values."""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    raw_path = value.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise TypeError(f"{name}.path must be a non-empty string")
    path = Path(raw_path).expanduser().resolve(strict=True)
    if root is not None and not path.is_relative_to(root):
        raise RuntimeError(f"{name}.path escapes sealed branch root: {path}")
    if expected_path is not None and path != expected_path.expanduser().resolve():
        raise RuntimeError(f"{name}.path is not the expected exact artifact: {path}")
    sha256 = _require_sha(value.get("sha256"), f"{name}.sha256")
    _assert_hash(path, sha256, f"{name}")
    return {"path": str(path), "sha256": sha256}


def load_sealed_branch_manifest(
    root: Path,
    *,
    expected_sha256: str,
    expected_mode: str,
    expected_target_global_step: int = INITIAL_TARGET_GLOBAL_STEP,
) -> dict[str, Any]:
    """Load and validate a success-sealed P1 branch, including exact hashes."""
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise FileNotFoundError(f"P1 sealed branch root is unavailable: {root}")
    if expected_mode not in P1_FORWARD_MODES:
        raise ValueError(f"unknown P1 branch mode: {expected_mode!r}")
    manifest_path = root / P1_BRANCH_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"P1 branch success manifest is unavailable: {manifest_path}")
    _assert_hash(manifest_path, expected_sha256, "P1 branch manifest")
    manifest = _load_json(manifest_path)
    if manifest.get("schema") != P1_BRANCH_SCHEMA or manifest.get("operation") != "p1_training":
        raise RuntimeError("P1 branch manifest schema/operation drifted")
    content_sha = manifest.get("manifest_content_sha256")
    _require_sha(content_sha, "P1 manifest_content_sha256")
    without_content = dict(manifest)
    without_content.pop("manifest_content_sha256", None)
    if sha256_bytes(canonical_json(without_content).encode("utf-8")) != content_sha:
        raise RuntimeError("P1 branch manifest content hash drifted")
    if manifest.get("root") != str(root):
        raise RuntimeError("P1 branch manifest root identity drifted")
    if manifest.get("branch") != expected_mode:
        raise RuntimeError("P1 branch manifest mode does not match the requested branch")
    source = manifest.get("source")
    launch = manifest.get("launch_contract")
    result = manifest.get("result")
    if not isinstance(source, Mapping) or not isinstance(launch, Mapping) or not isinstance(result, Mapping):
        raise TypeError("P1 branch manifest source/launch_contract/result must be mappings")
    lifecycle_meta = manifest.get("lifecycle")
    if not isinstance(lifecycle_meta, Mapping):
        raise TypeError("P1 branch manifest lifecycle must be a mapping")
    if lifecycle_meta.get("natural_kit_lifecycle_pass") is not False:
        raise RuntimeError("P1 branch manifest cannot claim natural Kit lifecycle PASS")
    if lifecycle_meta.get("lifecycle_status") != "UNRESOLVED":
        raise RuntimeError("P1 branch manifest lifecycle_status must remain UNRESOLVED")
    if lifecycle_meta.get("controlled_post_training_exit") is not True:
        raise RuntimeError("P1 branch manifest controlled exit marker drifted")
    if source.get("checkpoint_load_mode") != "full":
        raise RuntimeError("P1 branch source must use checkpoint_load_mode=full")
    source_step = _strict_int(source.get("global_step"), "source.global_step")
    if source_step not in (EXPECTED_INITIAL_GLOBAL_STEP, INITIAL_TARGET_GLOBAL_STEP):
        raise RuntimeError("P1 branch source global_step is outside the allowed continuation grid")
    source_checkpoint = _sealed_artifact(source.get("checkpoint"), name="source.checkpoint")
    source_config = _sealed_artifact(source.get("config"), name="source.config")
    target_config_ref = _sealed_artifact(manifest.get("target_config"), name="target_config")
    if target_config_ref["path"] != str(TARGET_CONFIG) or target_config_ref["sha256"] != sha256_file(TARGET_CONFIG):
        raise RuntimeError("P1 branch target config is not the exact frozen target config")
    if source_step == EXPECTED_INITIAL_GLOBAL_STEP:
        if source_checkpoint["path"] != str(SOURCE_CHECKPOINT) or source_checkpoint["sha256"] != SOURCE_CHECKPOINT_SHA256:
            raise RuntimeError("P1 branch source checkpoint is not the exact original step-10000 artifact")
        if source_config["path"] != str(SOURCE_CONFIG) or source_config["sha256"] != SOURCE_CONFIG_SHA256:
            raise RuntimeError("P1 branch source config is not the exact original config artifact")
    if launch.get("num_envs") != EXPECTED_NUM_ENVS:
        raise RuntimeError("P1 branch launch num_envs drifted")
    if launch.get("num_steps_per_env") != 8 or launch.get("num_mini_batches") != 4:
        raise RuntimeError("P1 branch rollout/minibatch contract drifted")
    if launch.get("actor_learning_rate") != 1.0e-4:
        raise RuntimeError("P1 branch actor learning rate drifted")
    if launch.get("ratio_teacher_rollout") != 1.0 or launch.get("enforce_teacher_rollout") is not True:
        raise RuntimeError("P1 branch teacher-rollout contract drifted")
    if launch.get("checkpoint_load_mode") != "full" or launch.get("auto_load_latest") is not False:
        raise RuntimeError("P1 branch checkpoint discovery contract drifted")
    if launch.get("forward_mode") != expected_mode or launch.get("world_size") != 1:
        raise RuntimeError("P1 branch launch identity drifted")
    if launch.get("common_init_contract_sha256") != P1_COMMON_INIT_CONTRACT_SHA256:
        raise RuntimeError("P1 paired branch common-init contract hash drifted")
    target = _strict_int(result.get("target_global_step"), "result.target_global_step")
    if target != expected_target_global_step:
        raise RuntimeError(f"P1 branch target_global_step drifted: {target} vs {expected_target_global_step}")
    requested = _strict_int(result.get("requested_iterations"), "result.requested_iterations")
    completed = _strict_int(result.get("completed_iterations"), "result.completed_iterations")
    run_iterations = _strict_int(result.get("run_iterations"), "result.run_iterations")
    has_total_completed = "total_completed_iterations" in result
    has_additional_iterations = "additional_iterations" in result
    if has_total_completed != has_additional_iterations:
        raise RuntimeError("P1 branch total/additional iteration fields must be supplied together")
    total_completed = _strict_int(
        result.get("total_completed_iterations", completed),
        "result.total_completed_iterations",
    )
    additional_iterations = _strict_int(
        result.get("additional_iterations", run_iterations),
        "result.additional_iterations",
    )
    expected_total, _expected_additional = _trusted_stage_iteration_counts(
        source_global_step=source_step,
        target_global_step=target,
        name="P1 branch result",
    )
    if expected_total == EXTENDED_ITERATIONS and not (has_total_completed and has_additional_iterations):
        raise RuntimeError("P1 extension branch result must explicitly separate total and additional iterations")
    _validate_trusted_stage_iteration_grid(
        source_global_step=source_step,
        target_global_step=target,
        requested_iterations=requested,
        completed_iterations=completed,
        total_completed_iterations=total_completed,
        run_iterations=run_iterations,
        additional_iterations=additional_iterations,
        name="P1 branch result",
    )
    if result.get("training_performed") is not True:
        raise RuntimeError("P1 branch success manifest must state training_performed=true")
    expected_updates = run_iterations * P1_EFFECTIVE_NUM_MINI_BATCHES
    for field in ("backward_call_count", "optimizer_step_count"):
        if _strict_nonnegative_int(result.get(field), f"result.{field}") != expected_updates:
            raise RuntimeError(f"P1 branch success manifest {field} count drifted")
    if _strict_nonnegative_int(result.get("scheduler_step_count"), "result.scheduler_step_count") != run_iterations:
        raise RuntimeError("P1 branch success manifest scheduler_step_count drifted")
    scheduler_before = _strict_int(result.get("scheduler_step_count_before"), "result.scheduler_step_count_before")
    scheduler_after = _strict_int(result.get("scheduler_step_count_after"), "result.scheduler_step_count_after")
    epoch_before = _strict_int(result.get("scheduler_last_epoch_before"), "result.scheduler_last_epoch_before")
    epoch_after = _strict_int(result.get("scheduler_last_epoch_after"), "result.scheduler_last_epoch_after")
    if scheduler_after - scheduler_before != run_iterations or epoch_after - epoch_before != run_iterations:
        raise RuntimeError("P1 branch success manifest scheduler native counter deltas drifted")
    if scheduler_after - scheduler_before != epoch_after - epoch_before:
        raise RuntimeError("P1 branch success manifest scheduler counter deltas disagree")
    if scheduler_before != source_step + 1 or epoch_before != source_step:
        raise RuntimeError("P1 branch success manifest scheduler before counters are not source-bound")
    if scheduler_after != target + 1 or epoch_after != target:
        raise RuntimeError("P1 branch success manifest scheduler after counters are not target-bound")
    final_checkpoint = _sealed_artifact(
        manifest.get("final_checkpoint"),
        name="final_checkpoint",
        root=root,
    )
    final_config = _sealed_artifact(
        manifest.get("final_config"),
        name="final_config",
        root=root,
    )
    if _step_from_checkpoint(Path(final_checkpoint["path"])) != target:
        raise RuntimeError("P1 final checkpoint filename/global_step mismatch")
    if _strict_int(manifest["final_checkpoint"].get("global_step"), "final_checkpoint.global_step") != target:
        raise RuntimeError("P1 final checkpoint global_step drifted")
    if Path(final_config["path"]).name != "config.yaml":
        raise RuntimeError("P1 final effective config must be the branch config.yaml")
    effective = manifest.get("effective_training_contract")
    if not isinstance(effective, Mapping):
        raise TypeError("P1 branch effective_training_contract must be a mapping")
    if dict(effective) != {
        "num_envs": EXPECTED_NUM_ENVS,
        "num_total_batches": target,
        "save_frequency": target,
        "num_steps_per_env": 8,
        "num_mini_batches": 4,
        "actor_learning_rate": 1.0e-4,
        "use_a2_base": True,
        "enforce_teacher_rollout": True,
        "ratio_teacher_rollout": 1.0,
        "d435i_forward_mode": expected_mode,
    }:
        raise RuntimeError("P1 effective training contract drifted")
    runtime_evidence = validate_runtime_evidence(
        manifest.get("runtime_evidence"),
        start_global_step=source_step,
        target_global_step=target,
        expected_iterations=run_iterations,
    )
    result_metrics = runtime_evidence["metrics"]
    if result_metrics["backward_call_count"] != _strict_nonnegative_int(result.get("backward_call_count"), "result.backward_call_count"):
        raise RuntimeError("P1 branch result backward count drifted from runtime evidence")
    if result_metrics["optimizer_step_count"] != _strict_nonnegative_int(result.get("optimizer_step_count"), "result.optimizer_step_count"):
        raise RuntimeError("P1 branch result optimizer count drifted from runtime evidence")
    if result_metrics["scheduler_step_count"] != _strict_nonnegative_int(result.get("scheduler_step_count"), "result.scheduler_step_count"):
        raise RuntimeError("P1 branch result scheduler count drifted from runtime evidence")
    for field in (
        "scheduler_step_count_before",
        "scheduler_step_count_after",
        "scheduler_last_epoch_before",
        "scheduler_last_epoch_after",
    ):
        if result_metrics[field] != _strict_int(result.get(field), f"result.{field}"):
            raise RuntimeError(f"P1 branch result {field} drifted from runtime evidence")
    if result_metrics["peak_vram_mib"] != result.get("peak_vram_mib"):
        raise RuntimeError("P1 branch result peak VRAM drifted from runtime evidence")
    return {
        "root": str(root),
        "manifest": ArtifactRef(manifest_path, _require_sha(expected_sha256, "P1 branch manifest")).as_dict(),
        "branch": expected_mode,
        "source": dict(source),
        "lifecycle": dict(lifecycle_meta),
        "launch_contract": dict(launch),
        "result": dict(result),
        "final_checkpoint": {**final_checkpoint, "global_step": target},
        "final_config": final_config,
        "effective_training_contract": dict(effective),
        "runtime_evidence": runtime_evidence,
        "raw": manifest,
    }


def validate_paired_extension(
    sequential_root: Path,
    packed_root: Path,
    *,
    source_step: int = EXPECTED_INITIAL_GLOBAL_STEP,
    completed_step: int = EXPECTED_INITIAL_GLOBAL_STEP + INITIAL_ITERATIONS,
    target_step: int = EXPECTED_INITIAL_GLOBAL_STEP + EXTENDED_ITERATIONS,
) -> tuple[Path, Path]:
    """Require both 200-step branches before a 500-step extension."""
    if completed_step != source_step + INITIAL_ITERATIONS or target_step != source_step + EXTENDED_ITERATIONS:
        raise ValueError("P1 paired extension step arithmetic drifted")
    roots = (sequential_root.expanduser().resolve(), packed_root.expanduser().resolve())
    if roots[0] == roots[1]:
        raise RuntimeError("P1 500 extension requires distinct sequential/packed roots")
    checkpoints = tuple(root / f"model_step_{completed_step:06d}.pt" for root in roots)
    missing = [path for path in checkpoints if not path.is_file()]
    if missing:
        raise P1Blocked(f"P1 500 extension is blocked until both 200-step checkpoints exist: {missing}")
    return checkpoints


def validate_global_step_progression(
    start_global_step: int,
    target_global_step: int,
    observed_global_steps: Sequence[int],
) -> dict[str, Any]:
    """Prove an absolute-target progression after a full checkpoint restore."""
    if isinstance(start_global_step, bool) or not isinstance(start_global_step, int):
        raise TypeError("P1 start_global_step must be an integer")
    if isinstance(target_global_step, bool) or not isinstance(target_global_step, int):
        raise TypeError("P1 target_global_step must be an integer")
    if target_global_step <= start_global_step:
        raise ValueError("P1 target_global_step must be greater than start_global_step")
    observed = list(observed_global_steps)
    if not observed:
        raise ValueError("P1 progression evidence cannot be empty")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in observed):
        raise TypeError("P1 observed global steps must be integers")
    expected = list(range(start_global_step + 1, target_global_step + 1))
    if observed != expected:
        raise RuntimeError(
            "P1 absolute-target progression drifted: "
            f"expected first/last={expected[0]}/{expected[-1]} got "
            f"first/last={observed[0]}/{observed[-1]}"
        )
    return {
        "start_global_step": start_global_step,
        "target_global_step": target_global_step,
        "executed_iterations": len(observed),
        "first_observed_global_step": observed[0],
        "last_observed_global_step": observed[-1],
        "stop_at_target": observed[-1] == target_global_step,
    }


def build_training_overrides(
    *,
    mode: str,
    branch_root: Path,
    checkpoint: Path,
    teacher_checkpoint: Path = TEACHER_CHECKPOINT,
    teacher_config: Path = TEACHER_CONFIG,
    teacher_manifest: Path = TEACHER_MANIFEST,
    iterations: int = INITIAL_ITERATIONS,
    run_iterations: int | None = None,
    start_global_step: int = EXPECTED_INITIAL_GLOBAL_STEP,
) -> tuple[str, ...]:
    """Build the exact Hydra contract passed to the c18 training entrypoint."""
    if mode not in P1_FORWARD_MODES:
        raise ValueError(f"mode must be one of {P1_FORWARD_MODES}")
    if iterations not in (INITIAL_ITERATIONS, EXTENDED_ITERATIONS):
        raise ValueError("P1 iterations must be exactly 200 or 500")
    if run_iterations is not None and run_iterations not in (
        INITIAL_ITERATIONS,
        EXTENSION_ITERATIONS,
    ):
        raise ValueError("P1 run_iterations must be exactly 200 or 300")
    batch_count = iterations if run_iterations is None else run_iterations
    if iterations == EXTENDED_ITERATIONS and (
        start_global_step != INITIAL_TARGET_GLOBAL_STEP
        or batch_count != EXTENSION_ITERATIONS
    ):
        raise ValueError(
            "P1 direct 500-step launch is forbidden; use --extend-from-root with "
            "a sealed global_step=10200 pair"
        )
    if iterations == INITIAL_ITERATIONS and start_global_step != EXPECTED_INITIAL_GLOBAL_STEP:
        raise ValueError("P1 200-step launch must start from global_step 10000")
    target_global_step = start_global_step + batch_count
    branch_root = branch_root.expanduser().resolve()
    checkpoint = checkpoint.expanduser().resolve()
    values = (
        f"+exp={TARGET_EXPERIMENT}",
        f"num_envs={EXPECTED_NUM_ENVS}",
        f"algo.trl.num_total_batches={target_global_step}",
        f"callbacks.model_save.save_frequency={target_global_step}",
        f"experiment_dir={branch_root}",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=full",
        "auto_load_latest=false",
        "use_wandb=false",
        "headless=true",
        "enable_cameras=true",
        f"teacher_actor_path={teacher_checkpoint.expanduser().resolve()}",
        f"teacher_config_path={teacher_config.expanduser().resolve()}",
        f"teacher_manifest_path={teacher_manifest.expanduser().resolve()}",
        "algo.config.use_a2_base=true",
        "algo.config.enforce_teacher_rollout=true",
        "algo.config.ratio_teacher_rollout=1.0",
        f"algo.config.actor.view_contract.d435i_forward_mode={mode}",
    )
    return values


def build_branch_command(
    spec: P1BranchSpec,
    *,
    script_path: Path | None = None,
    runtime_repository: Path = RUNTIME_REPOSITORY,
    overlay_repository: Path = REPO_ROOT,
    teacher: Mapping[str, Path] | None = None,
) -> tuple[str, ...]:
    """Build a self-contained launcher command for one branch."""
    script_path = (Path(__file__) if script_path is None else script_path).expanduser().resolve()
    teacher = teacher or {
        "teacher_actor_path": TEACHER_CHECKPOINT,
        "teacher_config_path": TEACHER_CONFIG,
        "teacher_manifest_path": TEACHER_MANIFEST,
    }
    command = [
        sys.executable,
        str(script_path),
        "--execute-branch",
        f"--runtime-repository={runtime_repository.expanduser().resolve()}",
        f"--overlay-repository={overlay_repository.expanduser().resolve()}",
        f"--mode={spec.mode}",
        f"--branch-root={spec.root}",
        f"--checkpoint={spec.checkpoint}",
        f"--config={spec.checkpoint_config}",
        f"--checkpoint-sha256={spec.checkpoint_sha256}",
        f"--config-sha256={spec.checkpoint_config_sha256}",
        f"--start-global-step={spec.start_global_step}",
        f"--target-global-step={spec.target_global_step}",
        f"--iterations={spec.requested_iterations}",
        f"--run-iterations={spec.run_iterations}",
    ]
    if spec.source_manifest_root is not None or spec.source_manifest_sha256 is not None:
        if spec.source_manifest_root is None or spec.source_manifest_sha256 is None:
            raise ValueError("P1 extension source manifest root/SHA must be supplied together")
        command.extend(
            (
                f"--source-manifest-root={spec.source_manifest_root.expanduser().resolve()}",
                f"--source-manifest-sha256={spec.source_manifest_sha256}",
            )
        )
    command.extend(
        (
            f"--teacher-actor-path={teacher['teacher_actor_path'].expanduser().resolve()}",
            f"--teacher-config-path={teacher['teacher_config_path'].expanduser().resolve()}",
            f"--teacher-manifest-path={teacher['teacher_manifest_path'].expanduser().resolve()}",
        )
    )
    command.extend(spec.overrides)
    return tuple(command)


def build_formal_eval_command(
    branch: P1BranchSpec,
    output_root: Path,
    *,
    replicate_id: str,
    eval_script: Path | None = None,
    overlay_repository: Path = REPO_ROOT,
    runtime_repository: Path = RUNTIME_REPOSITORY,
) -> tuple[str, ...]:
    """Build one fixed-seed 16-episode formal Student-eval command.

    The branch checkpoint and adjacent config must already exist so their
    hashes can be sealed into the command; this prevents a dry-run from
    inventing a checkpoint identity.  Callers create three fresh output roots
    and invoke this command serially on GPU7.
    """
    if not replicate_id or "/" in replicate_id or "\\" in replicate_id:
        raise ValueError("formal replicate_id must be a path-safe non-empty label")
    final_checkpoint = branch.final_checkpoint.expanduser().resolve(strict=True)
    final_config = final_checkpoint.with_name("config.yaml").resolve(strict=True)
    if _step_from_checkpoint(final_checkpoint) != branch.target_global_step:
        raise RuntimeError("formal eval checkpoint global_step does not match the branch target")
    output_root = output_root.expanduser().resolve()
    validate_fresh_output_root(output_root)
    eval_script = (
        REPO_ROOT / "gr00t/rl/scripts/run_a2_student_eval_v19.py"
        if eval_script is None
        else eval_script
    ).expanduser().resolve(strict=True)
    return (
        sys.executable,
        str(eval_script),
        "--mode",
        "formal",
        "--controller",
        "student",
        "--output-root",
        str(output_root),
        "--replicate-id",
        replicate_id,
        "--case-seed",
        "0",
        "--student-d435i-forward-mode",
        branch.mode,
        "--checkpoint",
        str(final_checkpoint),
        "--checkpoint-sha256",
        sha256_file(final_checkpoint),
        "--checkpoint-config",
        str(final_config),
        "--checkpoint-config-sha256",
        sha256_file(final_config),
        "--expected-global-step",
        str(branch.target_global_step),
        "--overlay-repository",
        str(overlay_repository.expanduser().resolve()),
        "--runtime-repository",
        str(runtime_repository.expanduser().resolve()),
    )


def compose_training_config(overrides: Sequence[str]):
    """Compose the real base Hydra config without launching IsaacSim."""
    try:
        from hydra import compose, initialize_config_dir
    except ImportError as exc:  # pragma: no cover - project dependency
        raise RuntimeError("P1 dry-run requires hydra-core for real composition") from exc
    config_dir = (REPO_ROOT / "gr00t/rl/config").resolve(strict=True)
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        return compose(config_name="base", overrides=list(overrides))


def _strict_bool(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"P1 effective {name} must be bool; got {value!r}")
    return value


def _strict_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"P1 effective {name} must be int; got {value!r}")
    return value


def _strict_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"P1 effective {name} must be finite float; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"P1 effective {name} must be finite; got {value!r}")
    return result


def validate_effective_training_config(config: Mapping[str, Any], *, mode: str, target_global_step: int) -> dict[str, Any]:
    """Assert every high-impact training field after actual Hydra composition."""
    if mode not in P1_FORWARD_MODES:
        raise ValueError(f"unknown P1 forward mode: {mode!r}")
    if _strict_int(config.get("num_envs"), "num_envs") != EXPECTED_NUM_ENVS:
        raise RuntimeError("P1 effective num_envs drifted from 64")
    if _strict_bool(config.get("headless"), "headless") is not True:
        raise RuntimeError("P1 effective headless must be true")
    if _strict_bool(config.get("enable_cameras"), "enable_cameras") is not True:
        raise RuntimeError("P1 effective enable_cameras must be true")
    if config.get("checkpoint_load_mode") != "full":
        raise RuntimeError("P1 effective checkpoint_load_mode must be full")
    if _strict_bool(config.get("auto_load_latest"), "auto_load_latest") is not False:
        raise RuntimeError("P1 effective auto_load_latest must be false")
    trl = config.get("algo", {}).get("trl", {})
    callbacks = config.get("callbacks", {}).get("model_save", {})
    algo = config.get("algo", {}).get("config", {})
    if _strict_int(trl.get("num_total_batches"), "algo.trl.num_total_batches") != target_global_step:
        raise RuntimeError("P1 effective num_total_batches must be the absolute target global_step")
    if _strict_int(callbacks.get("save_frequency"), "callbacks.model_save.save_frequency") != target_global_step:
        raise RuntimeError("P1 effective model save frequency must equal target global_step")
    if _strict_int(algo.get("num_steps_per_env"), "num_steps_per_env") != 8:
        raise RuntimeError("P1 effective rollout steps must equal 8")
    if _strict_int(algo.get("num_mini_batches"), "num_mini_batches") != 4:
        raise RuntimeError("P1 effective minibatches must equal 4")
    if _strict_float(algo.get("actor_learning_rate"), "actor_learning_rate") != 1.0e-4:
        raise RuntimeError("P1 effective actor learning rate drifted from 1e-4")
    if _strict_bool(algo.get("use_a2_base"), "use_a2_base") is not True:
        raise RuntimeError("P1 effective use_a2_base must be true")
    if _strict_bool(algo.get("enforce_teacher_rollout"), "enforce_teacher_rollout") is not True:
        raise RuntimeError("P1 effective enforce_teacher_rollout must be true")
    if _strict_float(algo.get("ratio_teacher_rollout"), "ratio_teacher_rollout") != 1.0:
        raise RuntimeError("P1 effective ratio_teacher_rollout must be 1.0")
    actor = algo.get("actor", {})
    view_contract = actor.get("view_contract", {})
    if view_contract.get("d435i_forward_mode") != mode:
        raise RuntimeError("P1 effective D435 forward mode drifted")
    return {
        "num_envs": EXPECTED_NUM_ENVS,
        "num_total_batches": target_global_step,
        "save_frequency": target_global_step,
        "num_steps_per_env": 8,
        "num_mini_batches": 4,
        "actor_learning_rate": 1.0e-4,
        "use_a2_base": True,
        "enforce_teacher_rollout": True,
        "ratio_teacher_rollout": 1.0,
        "d435i_forward_mode": mode,
    }


def build_p1_plan(
    output_root: Path,
    *,
    requested_iterations: int = INITIAL_ITERATIONS,
    checkpoint: Path = SOURCE_CHECKPOINT,
    config_path: Path = SOURCE_CONFIG,
    teacher_checkpoint: Path = TEACHER_CHECKPOINT,
    teacher_config: Path = TEACHER_CONFIG,
    teacher_manifest: Path = TEACHER_MANIFEST,
    runtime_repository: Path = RUNTIME_REPOSITORY,
    overlay_repository: Path = REPO_ROOT,
    n3_root: Path = N3_INPUT_ROOT,
    n2_root: Path = N2_INPUT_ROOT,
    script_path: Path | None = None,
) -> P1Plan:
    """Validate inputs and build both launch commands without touching outputs."""
    if requested_iterations != INITIAL_ITERATIONS:
        raise ValueError(
            "P1 initial plan is exactly 200 iterations; 500 requires --extend-from-root"
        )
    root = validate_fresh_output_root(output_root)
    source = validate_source_checkpoint(checkpoint, config_path)
    teacher = validate_teacher_triplet(teacher_checkpoint, teacher_config, teacher_manifest)
    runtime = validate_runtime_contract(runtime_repository)
    gpu_identity = validate_gpu_binding_environment(build_gpu_binding_environment())
    n3_input = validate_n3_contract(n3_root)
    n2_input = validate_n2_contract(n2_root)
    overlay_repository = overlay_repository.expanduser().resolve()
    if overlay_repository != REPO_ROOT:
        raise RuntimeError(
            f"P1 overlay repository must be the frozen candidate repository {REPO_ROOT}; got {overlay_repository}"
        )
    target_config = _expected_path(TARGET_CONFIG, TARGET_CONFIG, "P1 target config")
    if not target_config.is_file():
        raise FileNotFoundError(f"P1 target config is unavailable: {target_config}")
    teacher_paths = {
        "teacher_actor_path": Path(teacher["checkpoint"]["path"]),
        "teacher_config_path": Path(teacher["config"]["path"]),
        "teacher_manifest_path": Path(teacher["manifest"]["path"]),
    }
    branches = []
    for mode in P1_BRANCHES:
        branch_root = root / mode
        overrides = build_training_overrides(
            mode=mode,
            branch_root=branch_root,
            checkpoint=Path(source["path"]),
            teacher_checkpoint=teacher_paths["teacher_actor_path"],
            teacher_config=teacher_paths["teacher_config_path"],
            teacher_manifest=teacher_paths["teacher_manifest_path"],
            iterations=requested_iterations,
            run_iterations=INITIAL_ITERATIONS,
            start_global_step=source["global_step"],
        )
        validate_training_override_contract(
            overrides,
            mode=mode,
            branch_root=branch_root,
            checkpoint=Path(source["path"]),
            teacher=teacher_paths,
            iterations=requested_iterations,
        )
        effective_config = compose_training_config(overrides)
        effective_contract = validate_effective_training_config(
            effective_config,
            mode=mode,
            target_global_step=source["global_step"] + INITIAL_ITERATIONS,
        )
        branches.append(
            P1BranchSpec(
                mode=mode,
                root=branch_root,
                checkpoint=Path(source["path"]),
                checkpoint_sha256=source["sha256"],
                checkpoint_config=Path(source["config_path"]),
                checkpoint_config_sha256=source["config_sha256"],
                start_global_step=source["global_step"],
                requested_iterations=requested_iterations,
                run_iterations=requested_iterations,
                target_global_step=source["global_step"] + requested_iterations,
                overrides=tuple(overrides),
                command=(),
            )
        )
    provisional = P1Plan(
        root=root,
        requested_iterations=requested_iterations,
        branches=(branches[0], branches[1]),
        paired_extension=False,
        contract={
            "source_global_step": source["global_step"],
            "num_envs": EXPECTED_NUM_ENVS,
            "teacher_global_step": TEACHER_GLOBAL_STEP,
            "ratio_teacher_rollout": 1.0,
            "enforce_teacher_rollout": True,
            "checkpoint_load_mode": "full",
            "runtime_commit": EXPECTED_RUNTIME_COMMIT,
            "physical_gpu_index": EXPECTED_GPU_INDEX,
            "logical_device": EXPECTED_LOGICAL_DEVICE,
            "world_size": 1,
            "vram_limit_mib": VRAM_LIMIT_MIB,
            "n3_input": n3_input,
            "n2_input": n2_input,
            "effective_training_contract": effective_contract,
        },
    )
    final_branches = tuple(
        P1BranchSpec(
            **{
                **branch.__dict__,
                "command": build_branch_command(
                    branch,
                    script_path=script_path,
                    runtime_repository=runtime_repository,
                    overlay_repository=overlay_repository,
                    teacher=teacher_paths,
                ),
            }
        )
        for branch in provisional.branches
    )
    final_contract = {
        **provisional.contract,
        "runtime_repository": runtime["repository"],
        "target_config": {
            "path": str(target_config),
            "sha256": sha256_file(target_config),
        },
        "gpu_identity": gpu_identity,
    }
    final_plan = P1Plan(
        root=provisional.root,
        requested_iterations=provisional.requested_iterations,
        branches=(final_branches[0], final_branches[1]),
        paired_extension=provisional.paired_extension,
        contract=final_contract,
    )
    validate_branch_pair(final_plan.branches[0], final_plan.branches[1], requested_iterations=requested_iterations)
    return final_plan


def build_paired_extension_plan(
    output_root: Path,
    sequential_200_root: Path,
    packed_200_root: Path,
    *,
    sequential_manifest_sha256: str | None = None,
    packed_manifest_sha256: str | None = None,
    teacher_checkpoint: Path = TEACHER_CHECKPOINT,
    teacher_config: Path = TEACHER_CONFIG,
    teacher_manifest: Path = TEACHER_MANIFEST,
    runtime_repository: Path = RUNTIME_REPOSITORY,
    overlay_repository: Path = REPO_ROOT,
    n3_root: Path = N3_INPUT_ROOT,
    n2_root: Path = N2_INPUT_ROOT,
    script_path: Path | None = None,
) -> P1Plan:
    """Build a paired 200-to-500 continuation plan.

    Both already-completed step-10200 artifacts are required.  The extension
    uses a fresh root with 300 additional batches per branch, ending at
    step-10500; a single branch can never be extended by this API.
    """
    if sequential_manifest_sha256 is None or packed_manifest_sha256 is None:
        raise ValueError(
            "--extend-from-root requires exact sequential and packed sealed manifest SHA256 values"
        )
    sequential_200_root = sequential_200_root.expanduser().resolve()
    packed_200_root = packed_200_root.expanduser().resolve()
    sequential_manifest = load_sealed_branch_manifest(
        sequential_200_root,
        expected_sha256=sequential_manifest_sha256,
        expected_mode="sequential",
        expected_target_global_step=INITIAL_TARGET_GLOBAL_STEP,
    )
    packed_manifest = load_sealed_branch_manifest(
        packed_200_root,
        expected_sha256=packed_manifest_sha256,
        expected_mode="packed",
        expected_target_global_step=INITIAL_TARGET_GLOBAL_STEP,
    )
    if sequential_manifest["source"] != packed_manifest["source"]:
        raise RuntimeError("paired extension source checkpoint/config provenance differs")
    if sequential_manifest["effective_training_contract"] != {
        **sequential_manifest["effective_training_contract"],
        "num_total_batches": INITIAL_TARGET_GLOBAL_STEP,
        "save_frequency": INITIAL_TARGET_GLOBAL_STEP,
    }:
        raise RuntimeError("sequential 200-step effective contract is not the sealed initial contract")
    if packed_manifest["effective_training_contract"] != {
        **packed_manifest["effective_training_contract"],
        "num_total_batches": INITIAL_TARGET_GLOBAL_STEP,
        "save_frequency": INITIAL_TARGET_GLOBAL_STEP,
    }:
        raise RuntimeError("packed 200-step effective contract is not the sealed initial contract")
    checkpoint_paths = (
        Path(sequential_manifest["final_checkpoint"]["path"]),
        Path(packed_manifest["final_checkpoint"]["path"]),
    )
    validate_paired_extension(sequential_200_root, packed_200_root)
    root = validate_fresh_output_root(output_root)
    teacher = validate_teacher_triplet(teacher_checkpoint, teacher_config, teacher_manifest)
    runtime = validate_runtime_contract(runtime_repository)
    gpu_identity = validate_gpu_binding_environment(build_gpu_binding_environment())
    n3_input = validate_n3_contract(n3_root)
    n2_input = validate_n2_contract(n2_root)
    overlay_repository = overlay_repository.expanduser().resolve()
    if overlay_repository != REPO_ROOT:
        raise RuntimeError(
            f"P1 overlay repository must be the frozen candidate repository {REPO_ROOT}; got {overlay_repository}"
        )
    target_config = _expected_path(TARGET_CONFIG, TARGET_CONFIG, "P1 target config")
    if not target_config.is_file():
        raise FileNotFoundError(f"P1 target config is unavailable: {target_config}")
    teacher_paths = {
        "teacher_actor_path": Path(teacher["checkpoint"]["path"]),
        "teacher_config_path": Path(teacher["config"]["path"]),
        "teacher_manifest_path": Path(teacher["manifest"]["path"]),
    }
    branches = []
    source_manifests = (sequential_manifest, packed_manifest)
    for mode, checkpoint, source_manifest in zip(P1_BRANCHES, checkpoint_paths, source_manifests, strict=True):
        config_path = checkpoint.with_name("config.yaml")
        checkpoint_info = validate_branch_checkpoint(
            checkpoint,
            config_path,
            expected_checkpoint_sha256=sha256_file(checkpoint),
            expected_config_sha256=sha256_file(config_path),
            expected_global_step=EXPECTED_INITIAL_GLOBAL_STEP + INITIAL_ITERATIONS,
        )
        branch_root = root / mode
        overrides = build_training_overrides(
            mode=mode,
            branch_root=branch_root,
            checkpoint=checkpoint,
            teacher_checkpoint=teacher_paths["teacher_actor_path"],
            teacher_config=teacher_paths["teacher_config_path"],
            teacher_manifest=teacher_paths["teacher_manifest_path"],
            iterations=EXTENDED_ITERATIONS,
            run_iterations=EXTENDED_ITERATIONS - INITIAL_ITERATIONS,
            start_global_step=checkpoint_info["global_step"],
        )
        validate_training_override_contract(
            overrides,
            mode=mode,
            branch_root=branch_root,
            checkpoint=checkpoint,
            teacher=teacher_paths,
            iterations=EXTENDED_ITERATIONS,
            expected_start_global_step=checkpoint_info["global_step"],
            run_iterations=EXTENDED_ITERATIONS - INITIAL_ITERATIONS,
        )
        effective_config = compose_training_config(overrides)
        effective_contract = validate_effective_training_config(
            effective_config,
            mode=mode,
            target_global_step=EXTENDED_TARGET_GLOBAL_STEP,
        )
        branches.append(
            P1BranchSpec(
                mode=mode,
                root=branch_root,
                checkpoint=checkpoint,
                checkpoint_sha256=checkpoint_info["sha256"],
                checkpoint_config=config_path,
                checkpoint_config_sha256=checkpoint_info["config_sha256"],
                start_global_step=checkpoint_info["global_step"],
                requested_iterations=EXTENDED_ITERATIONS,
                run_iterations=EXTENDED_ITERATIONS - INITIAL_ITERATIONS,
                target_global_step=EXPECTED_INITIAL_GLOBAL_STEP + EXTENDED_ITERATIONS,
                overrides=tuple(overrides),
                command=(),
                source_manifest_root=Path(source_manifest["root"]),
                source_manifest_sha256=source_manifest["manifest"]["sha256"],
            )
        )
    provisional = P1Plan(
        root=root,
        requested_iterations=EXTENDED_ITERATIONS,
        branches=(branches[0], branches[1]),
        paired_extension=True,
        contract={
            "source_global_step": EXPECTED_INITIAL_GLOBAL_STEP,
            "extension_start_global_step": EXPECTED_INITIAL_GLOBAL_STEP + INITIAL_ITERATIONS,
            "sequential_manifest_sha256": sequential_manifest_sha256,
            "packed_manifest_sha256": packed_manifest_sha256,
            "num_envs": EXPECTED_NUM_ENVS,
            "teacher_global_step": TEACHER_GLOBAL_STEP,
            "ratio_teacher_rollout": 1.0,
            "enforce_teacher_rollout": True,
            "checkpoint_load_mode": "full",
            "runtime_commit": EXPECTED_RUNTIME_COMMIT,
            "physical_gpu_index": EXPECTED_GPU_INDEX,
            "logical_device": EXPECTED_LOGICAL_DEVICE,
            "world_size": 1,
            "vram_limit_mib": VRAM_LIMIT_MIB,
            "n3_input": n3_input,
            "n2_input": n2_input,
            "effective_training_contract": effective_contract,
        },
    )
    final_branches = tuple(
        P1BranchSpec(
            **{
                **branch.__dict__,
                "command": build_branch_command(
                    branch,
                    script_path=script_path,
                    runtime_repository=runtime_repository,
                    overlay_repository=overlay_repository,
                    teacher=teacher_paths,
                ),
            }
        )
        for branch in provisional.branches
    )
    final_plan = P1Plan(
        root=root,
        requested_iterations=EXTENDED_ITERATIONS,
        branches=(final_branches[0], final_branches[1]),
        paired_extension=True,
        contract={
            **provisional.contract,
            "runtime_repository": runtime["repository"],
            "overlay_repository": str(overlay_repository),
            "target_config": {"path": str(target_config), "sha256": sha256_file(target_config)},
            "gpu_identity": gpu_identity,
        },
    )
    validate_branch_pair(
        final_plan.branches[0],
        final_plan.branches[1],
        requested_iterations=EXTENDED_ITERATIONS,
        allow_distinct_start_checkpoint=True,
    )
    return final_plan


def validate_peak_vram_mib(peak_mib: int | float) -> dict[str, Any]:
    if isinstance(peak_mib, bool) or not isinstance(peak_mib, (int, float)):
        raise TypeError("P1 peak VRAM must be a numeric finite MiB value")
    if not math.isfinite(float(peak_mib)):
        raise ValueError("P1 peak VRAM must be a finite number of MiB")
    peak_mib = float(peak_mib)
    if peak_mib >= VRAM_LIMIT_MIB:
        raise P1Blocked(f"P1 peak VRAM {peak_mib:.3f} MiB breaches the strict <46 GiB gate")
    if peak_mib < 0:
        raise ValueError("P1 peak VRAM cannot be negative")
    return {"peak_vram_mib": peak_mib, "limit_mib": VRAM_LIMIT_MIB, "passed": True}


def _strict_nonnegative_int(value: Any, name: str) -> int:
    result = _strict_int(value, name)
    if result < 0:
        raise ValueError(f"P1 {name} cannot be negative")
    return result


def _trusted_stage_iteration_counts(
    *,
    source_global_step: Any,
    target_global_step: Any,
    name: str,
) -> tuple[int, int]:
    source = _strict_int(source_global_step, f"{name}.source_global_step")
    target = _strict_int(target_global_step, f"{name}.target_global_step")
    if (source, target) == (EXPECTED_INITIAL_GLOBAL_STEP, INITIAL_TARGET_GLOBAL_STEP):
        return INITIAL_ITERATIONS, INITIAL_ITERATIONS
    if (source, target) == (INITIAL_TARGET_GLOBAL_STEP, EXTENDED_TARGET_GLOBAL_STEP):
        return EXTENDED_ITERATIONS, EXTENSION_ITERATIONS
    raise RuntimeError(
        f"{name} source/target is outside the exact P1 stage grid: "
        f"source={source} target={target}"
    )


def _validate_trusted_stage_iteration_grid(
    *,
    source_global_step: Any,
    target_global_step: Any,
    requested_iterations: Any,
    completed_iterations: Any,
    total_completed_iterations: Any,
    run_iterations: Any,
    additional_iterations: Any,
    name: str,
) -> tuple[int, int]:
    """Require one of the two exact P1 stage tuples; no relabeling is valid."""
    expected_total, expected_additional = _trusted_stage_iteration_counts(
        source_global_step=source_global_step,
        target_global_step=target_global_step,
        name=name,
    )
    expected_fields = {
        "requested_iterations": expected_total,
        "completed_iterations": expected_total,
        "total_completed_iterations": expected_total,
        "run_iterations": expected_additional,
        "additional_iterations": expected_additional,
    }
    actual_fields = {
        "requested_iterations": requested_iterations,
        "completed_iterations": completed_iterations,
        "total_completed_iterations": total_completed_iterations,
        "run_iterations": run_iterations,
        "additional_iterations": additional_iterations,
    }
    for field, expected in expected_fields.items():
        actual = _strict_int(actual_fields[field], f"{name}.{field}")
        if actual != expected:
            raise RuntimeError(
                f"{name} {field} is not the exact stage-grid value: "
                f"expected={expected} got={actual}"
            )
    return expected_total, expected_additional


def validate_runtime_metrics(
    metrics: Mapping[str, Any],
    *,
    start_global_step: int,
    target_global_step: int,
    expected_iterations: int,
) -> dict[str, Any]:
    """Validate typed runtime evidence needed before success sealing."""
    if not isinstance(metrics, Mapping):
        raise TypeError("P1 runtime metrics must be a mapping")
    if metrics.get("schema") != P1_RUNTIME_METRICS_SCHEMA:
        raise RuntimeError("P1 runtime metrics schema drifted")
    if metrics.get("training_performed") is not True:
        raise RuntimeError("P1 runtime metrics must explicitly report training_performed=true")
    if metrics.get("num_mini_batches") != P1_EFFECTIVE_NUM_MINI_BATCHES:
        raise RuntimeError("P1 runtime metrics num_mini_batches must remain exactly 4")
    if metrics.get("num_ppo_epochs") != P1_EFFECTIVE_NUM_PPO_EPOCHS:
        raise RuntimeError("P1 runtime metrics num_ppo_epochs must remain exactly 1")
    if metrics.get("num_micro_batches") != P1_EFFECTIVE_NUM_MICRO_BATCHES:
        raise RuntimeError("P1 runtime metrics gradient accumulation must remain one micro-batch")
    metric_start_global_step = _strict_int(metrics.get("start_global_step"), "start_global_step")
    metric_target_global_step = _strict_int(metrics.get("target_global_step"), "target_global_step")
    if metric_start_global_step != start_global_step:
        raise RuntimeError("P1 runtime metrics start_global_step drifted")
    if metric_target_global_step != target_global_step:
        raise RuntimeError("P1 runtime metrics target_global_step drifted")
    completed = _strict_nonnegative_int(metrics.get("completed_iterations"), "completed_iterations")
    if completed != expected_iterations:
        raise RuntimeError(f"P1 runtime completed_iterations drifted: {completed} vs {expected_iterations}")
    backward = _strict_nonnegative_int(metrics.get("backward_call_count"), "backward_call_count")
    optimizer = _strict_nonnegative_int(metrics.get("optimizer_step_count"), "optimizer_step_count")
    scheduler = _strict_nonnegative_int(metrics.get("scheduler_step_count"), "scheduler_step_count")
    expected_updates = expected_iterations * P1_EFFECTIVE_NUM_MINI_BATCHES
    if backward != expected_updates or optimizer != expected_updates:
        raise RuntimeError(
            "P1 runtime update counts must equal expected_iterations*num_mini_batches: "
            f"expected={expected_updates} backward={backward} optimizer={optimizer}"
        )
    if scheduler != expected_iterations:
        raise RuntimeError(
            "P1 runtime scheduler count must equal one lr_scheduler.step per outer iteration: "
            f"expected={expected_iterations} got={scheduler}"
        )
    scheduler_before = _strict_int(metrics.get("scheduler_step_count_before"), "scheduler_step_count_before")
    scheduler_after = _strict_int(metrics.get("scheduler_step_count_after"), "scheduler_step_count_after")
    epoch_before = _strict_int(metrics.get("scheduler_last_epoch_before"), "scheduler_last_epoch_before")
    epoch_after = _strict_int(metrics.get("scheduler_last_epoch_after"), "scheduler_last_epoch_after")
    if scheduler_after - scheduler_before != expected_iterations:
        raise RuntimeError("P1 runtime scheduler _step_count delta drifted")
    if epoch_after - epoch_before != expected_iterations:
        raise RuntimeError("P1 runtime scheduler last_epoch delta drifted")
    if scheduler_after - scheduler_before != epoch_after - epoch_before:
        raise RuntimeError("P1 runtime scheduler native counter deltas disagree")
    if scheduler_before != epoch_before + 1 or scheduler_after != epoch_after + 1:
        raise RuntimeError("P1 runtime scheduler _step_count must equal last_epoch + 1")
    if epoch_before != start_global_step or scheduler_before != start_global_step + 1:
        raise RuntimeError("P1 runtime scheduler before counters are not bound to the source step")
    if epoch_after != target_global_step or scheduler_after != target_global_step + 1:
        raise RuntimeError("P1 runtime scheduler after counters are not bound to the target step")
    additional = _strict_nonnegative_int(metrics.get("additional_iterations"), "additional_iterations")
    if additional != expected_iterations:
        raise RuntimeError("P1 runtime additional iteration count drifted")
    observed_steps = metrics.get("observed_global_steps")
    if not isinstance(observed_steps, Sequence) or isinstance(observed_steps, (str, bytes)):
        raise TypeError("P1 runtime metrics observed_global_steps must be an integer sequence")
    progression = validate_global_step_progression(
        start_global_step,
        target_global_step,
        observed_steps,
    )
    peak = metrics.get("peak_vram_mib")
    resource = validate_peak_vram_mib(peak)
    iteration_time = _strict_float(metrics.get("iteration_time_s"), "iteration_time_s")
    if iteration_time <= 0.0:
        raise ValueError("P1 iteration_time_s must be positive")
    final_checkpoint = metrics.get("final_checkpoint")
    if not isinstance(final_checkpoint, Mapping):
        raise TypeError("P1 runtime metrics final_checkpoint must be a mapping")
    final_path = final_checkpoint.get("path")
    final_step = final_checkpoint.get("global_step")
    if not isinstance(final_path, str) or not final_path:
        raise TypeError("P1 runtime metrics final checkpoint path must be a non-empty string")
    if isinstance(final_step, bool) or final_step != target_global_step:
        raise RuntimeError("P1 runtime metrics final checkpoint step drifted")
    _assert_hash(Path(final_path), final_checkpoint.get("sha256"), "P1 runtime final checkpoint")
    gpu_identity = metrics.get("gpu_identity")
    if not isinstance(gpu_identity, Mapping):
        raise TypeError("P1 runtime metrics gpu_identity must be a mapping")
    if gpu_identity.get("physical_gpu_index") not in (EXPECTED_GPU_INDEX, int(EXPECTED_GPU_INDEX)):
        raise RuntimeError("P1 runtime metrics physical GPU identity drifted")
    if gpu_identity.get("logical_device") != EXPECTED_LOGICAL_DEVICE:
        raise RuntimeError("P1 runtime metrics logical device drifted")
    if gpu_identity.get("uuid") != EXPECTED_GPU_UUID:
        raise RuntimeError("P1 runtime metrics GPU UUID drifted")
    if gpu_identity.get("cuda_visible_devices") != EXPECTED_GPU_INDEX:
        raise RuntimeError("P1 runtime metrics CUDA_VISIBLE_DEVICES drifted")
    if gpu_identity.get("world_size") != 1:
        raise RuntimeError("P1 runtime metrics world size drifted")
    if not isinstance(metrics.get("callback_train_begin_seen"), bool) or metrics["callback_train_begin_seen"] is not True:
        raise RuntimeError("P1 runtime metrics lacks callback lifecycle proof")
    callback_steps = _strict_nonnegative_int(metrics.get("callback_step_end_count"), "callback_step_end_count")
    if callback_steps != expected_iterations:
        raise RuntimeError("P1 runtime callback step count drifted")
    if metrics.get("callback_max_steps") != target_global_step:
        raise RuntimeError("P1 runtime callback max_steps drifted")
    return {
        "schema": P1_RUNTIME_METRICS_SCHEMA,
        "completed_iterations": completed,
        "start_global_step": start_global_step,
        "target_global_step": target_global_step,
        "num_mini_batches": P1_EFFECTIVE_NUM_MINI_BATCHES,
        "num_ppo_epochs": P1_EFFECTIVE_NUM_PPO_EPOCHS,
        "num_micro_batches": P1_EFFECTIVE_NUM_MICRO_BATCHES,
        "additional_iterations": additional,
        "observed_global_steps": list(observed_steps),
        "backward_call_count": backward,
        "optimizer_step_count": optimizer,
        "scheduler_step_count": scheduler,
        "scheduler_step_count_before": scheduler_before,
        "scheduler_step_count_after": scheduler_after,
        "scheduler_last_epoch_before": epoch_before,
        "scheduler_last_epoch_after": epoch_after,
        "training_performed": True,
        "progression": progression,
        "peak_vram_mib": resource["peak_vram_mib"],
        "iteration_time_s": iteration_time,
        "final_checkpoint": {
            "path": str(Path(final_path).expanduser().resolve()),
            "global_step": target_global_step,
            "sha256": final_checkpoint["sha256"],
        },
        "gpu_identity": dict(gpu_identity),
        "callback_train_begin_seen": True,
        "callback_step_end_count": callback_steps,
        "callback_max_steps": target_global_step,
        "observability": metrics.get("observability", {}),
    }


def sample_gpu_telemetry(environment: Mapping[str, str]) -> dict[str, Any]:
    """Sample physical GPU7 via nvidia-smi; no CPU/software fallback exists."""
    result = subprocess.run(
        [
            "nvidia-smi",
            "-i",
            EXPECTED_GPU_INDEX,
            "--query-gpu=index,uuid,memory.used",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=dict(environment),
    )
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        raise RuntimeError(f"P1 telemetry expected one GPU7 sample, got {len(rows)}")
    fields = [field.strip() for field in rows[0].split(",")]
    if len(fields) != 3:
        raise RuntimeError(f"P1 telemetry nvidia-smi row schema drifted: {rows[0]!r}")
    physical_index, uuid_value, memory_used = fields
    if physical_index not in (EXPECTED_GPU_INDEX, str(int(EXPECTED_GPU_INDEX))):
        raise RuntimeError("P1 telemetry sampled a GPU other than physical GPU7")
    if uuid_value != EXPECTED_GPU_UUID:
        raise RuntimeError("P1 telemetry sampled an unexpected GPU UUID")
    if not memory_used.isdigit():
        raise TypeError("P1 telemetry memory.used must be an integer MiB string from nvidia-smi")
    return {
        "physical_gpu_index": EXPECTED_GPU_INDEX,
        "logical_device": EXPECTED_LOGICAL_DEVICE,
        "uuid": EXPECTED_GPU_UUID,
        "cuda_visible_devices": EXPECTED_GPU_INDEX,
        "world_size": 1,
        "peak_vram_mib": int(memory_used),
        "sample_epoch_s": time.time(),
    }


class GpuTelemetrySampler:
    """Bounded physical-GPU sampler started before each branch subprocess."""

    def __init__(self, environment: Mapping[str, str], *, interval_s: float = 0.25, sampler=None):
        if isinstance(interval_s, bool) or not isinstance(interval_s, (int, float)) or interval_s <= 0.0:
            raise ValueError("P1 telemetry interval must be a positive finite number")
        if not math.isfinite(float(interval_s)):
            raise ValueError("P1 telemetry interval must be finite")
        self.environment = dict(environment)
        self.interval_s = float(interval_s)
        self.sampler = sample_gpu_telemetry if sampler is None else sampler
        self.samples: list[dict[str, Any]] = []
        self.errors: list[BaseException] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.started_at_epoch_s: float | None = None
        self.ended_at_epoch_s: float | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("P1 GPU telemetry sampler cannot be started twice")
        self.started_at_epoch_s = time.time()
        self._thread = threading.Thread(target=self._run, name="p1-gpu7-telemetry", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                sample = self.sampler(self.environment)
                if not isinstance(sample, Mapping):
                    raise TypeError("P1 telemetry sampler must return a mapping")
                self.samples.append(dict(sample))
            except BaseException as error:  # retain error and fail at stop; never downgrade
                self.errors.append(error)
                self._stop.set()
                return
            self._stop.wait(self.interval_s)

    def stop(self) -> dict[str, Any]:
        if self._thread is None:
            raise RuntimeError("P1 GPU telemetry sampler was not started")
        self._stop.set()
        self._thread.join(timeout=max(5.0, self.interval_s * 8.0))
        if self._thread.is_alive():
            raise RuntimeError("P1 GPU telemetry sampler did not join safely")
        self.ended_at_epoch_s = time.time()
        if self.errors:
            raise RuntimeError("P1 GPU telemetry sampler failed") from self.errors[0]
        if not self.samples:
            raise RuntimeError("P1 GPU telemetry sampler produced no samples")
        for index, sample in enumerate(self.samples):
            if not isinstance(sample, Mapping):
                raise TypeError(f"P1 telemetry sample {index} must be a mapping")
            for field, expected in (
                ("physical_gpu_index", EXPECTED_GPU_INDEX),
                ("logical_device", EXPECTED_LOGICAL_DEVICE),
                ("uuid", EXPECTED_GPU_UUID),
                ("cuda_visible_devices", EXPECTED_GPU_INDEX),
                ("world_size", 1),
            ):
                if sample.get(field) != expected:
                    raise RuntimeError(f"P1 telemetry sample {index} {field} identity drifted")
            value = sample.get("peak_vram_mib")
            validate_peak_vram_mib(value)
            stamp = sample.get("sample_epoch_s")
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(float(stamp)):
                raise TypeError(f"P1 telemetry sample {index} sample_epoch_s must be finite numeric")
        peak = max(sample["peak_vram_mib"] for sample in self.samples)
        peak_gate = validate_peak_vram_mib(peak)
        result = {
            "schema": P1_GPU_TELEMETRY_SCHEMA,
            "physical_gpu_index": EXPECTED_GPU_INDEX,
            "logical_device": EXPECTED_LOGICAL_DEVICE,
            "uuid": EXPECTED_GPU_UUID,
            "cuda_visible_devices": EXPECTED_GPU_INDEX,
            "world_size": 1,
            "started_at_epoch_s": self.started_at_epoch_s,
            "ended_at_epoch_s": self.ended_at_epoch_s,
            "samples": [dict(sample) for sample in self.samples],
            "peak_vram_mib": peak_gate["peak_vram_mib"],
        }
        if result["ended_at_epoch_s"] < result["started_at_epoch_s"]:
            raise RuntimeError("P1 GPU telemetry timestamps are not monotonic")
        return result


def load_gpu_telemetry_peak_vram(path: Path) -> dict[str, Any]:
    """Read sealed sampler output and enforce exact identity/46-GiB gate."""
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise FileNotFoundError(f"P1 GPU telemetry is unavailable: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        loaded = json.loads(text)
        if not isinstance(loaded, Mapping) or "samples" not in loaded:
            raise RuntimeError("P1 GPU telemetry must be the sealed sampler wrapper, not raw samples")
    except json.JSONDecodeError as exc:
        raise RuntimeError("P1 GPU telemetry must be one sealed JSON wrapper") from exc
    if loaded.get("schema") != P1_GPU_TELEMETRY_SCHEMA:
        raise RuntimeError("P1 GPU telemetry schema drifted")
    for field, expected in (
        ("physical_gpu_index", EXPECTED_GPU_INDEX),
        ("logical_device", EXPECTED_LOGICAL_DEVICE),
        ("uuid", EXPECTED_GPU_UUID),
        ("cuda_visible_devices", EXPECTED_GPU_INDEX),
        ("world_size", 1),
    ):
        if loaded.get(field) != expected:
            raise RuntimeError(f"P1 GPU telemetry physical GPU identity field {field} drifted")
    for field in ("started_at_epoch_s", "ended_at_epoch_s"):
        if isinstance(loaded.get(field), bool) or not isinstance(loaded.get(field), (int, float)) or not math.isfinite(float(loaded[field])):
            raise TypeError(f"P1 GPU telemetry {field} must be finite numeric")
    if loaded["ended_at_epoch_s"] < loaded["started_at_epoch_s"]:
        raise RuntimeError("P1 GPU telemetry timestamps are not monotonic")
    records = loaded["samples"]
    if not isinstance(records, list) or not records:
        raise TypeError("P1 GPU telemetry samples must be a non-empty list")
    if not records:
        raise ValueError("P1 telemetry contains no records")
    peaks = []
    for record in records:
        if record.get("physical_gpu_index") not in (EXPECTED_GPU_INDEX, int(EXPECTED_GPU_INDEX)):
            raise RuntimeError("P1 telemetry physical GPU identity drifted")
        if record.get("logical_device") != EXPECTED_LOGICAL_DEVICE:
            raise RuntimeError("P1 telemetry logical device drifted")
        if record.get("uuid") != EXPECTED_GPU_UUID:
            raise RuntimeError("P1 telemetry GPU UUID drifted")
        if record.get("cuda_visible_devices") != EXPECTED_GPU_INDEX or record.get("world_size") != 1:
            raise RuntimeError("P1 telemetry process binding drifted")
        value = record.get("peak_vram_mib")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("P1 telemetry peak_vram_mib must be numeric")
        if not math.isfinite(float(value)):
            raise ValueError("P1 telemetry peak_vram_mib must be finite")
        stamp = record.get("sample_epoch_s")
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(float(stamp)):
            raise TypeError("P1 telemetry sample_epoch_s must be finite numeric")
        peaks.append(float(value))
    peak = max(peaks)
    gate = validate_peak_vram_mib(peak)
    declared = validate_peak_vram_mib(loaded.get("peak_vram_mib"))["peak_vram_mib"]
    if declared != gate["peak_vram_mib"]:
        raise RuntimeError("P1 GPU telemetry declared peak does not match samples")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "record_count": len(records),
        "schema": P1_GPU_TELEMETRY_SCHEMA,
        "physical_gpu_index": EXPECTED_GPU_INDEX,
        "logical_device": EXPECTED_LOGICAL_DEVICE,
        "uuid": EXPECTED_GPU_UUID,
        "cuda_visible_devices": EXPECTED_GPU_INDEX,
        "world_size": 1,
        "started_at_epoch_s": float(loaded["started_at_epoch_s"]),
        "ended_at_epoch_s": float(loaded["ended_at_epoch_s"]),
        **gate,
    }


def load_runtime_evidence(
    metrics_path: Path,
    telemetry_path: Path,
    *,
    start_global_step: int,
    target_global_step: int,
    expected_iterations: int,
) -> dict[str, Any]:
    metrics = _load_json(metrics_path)
    runtime_metrics = validate_runtime_metrics(
        metrics,
        start_global_step=start_global_step,
        target_global_step=target_global_step,
        expected_iterations=expected_iterations,
    )
    telemetry = load_gpu_telemetry_peak_vram(telemetry_path)
    if runtime_metrics["peak_vram_mib"] != telemetry["peak_vram_mib"]:
        raise RuntimeError("P1 runtime metrics and GPU telemetry peak VRAM disagree")
    return {
        "schema": "a2_cb2h_pro_p1_runtime_evidence_v2",
        "metrics": runtime_metrics,
        "metrics_artifact": artifact_ref(metrics_path),
        "telemetry": telemetry,
        "telemetry_artifact": {
            "path": telemetry["path"],
            "sha256": telemetry["sha256"],
        },
    }


def validate_runtime_evidence(
    evidence: Mapping[str, Any],
    *,
    start_global_step: int,
    target_global_step: int,
    expected_iterations: int,
) -> dict[str, Any]:
    """Revalidate the exact runtime evidence object at seal and reload time."""
    if not isinstance(evidence, Mapping) or evidence.get("schema") != "a2_cb2h_pro_p1_runtime_evidence_v2":
        raise RuntimeError("P1 runtime evidence schema drifted")
    metrics = evidence.get("metrics")
    telemetry = evidence.get("telemetry")
    if not isinstance(metrics, Mapping) or not isinstance(telemetry, Mapping):
        raise TypeError("P1 runtime evidence metrics/telemetry must be mappings")
    validated_metrics = validate_runtime_metrics(
        metrics,
        start_global_step=start_global_step,
        target_global_step=target_global_step,
        expected_iterations=expected_iterations,
    )
    metrics_artifact = _sealed_artifact(evidence.get("metrics_artifact"), name="runtime.metrics_artifact")
    telemetry_artifact = _sealed_artifact(evidence.get("telemetry_artifact"), name="runtime.telemetry_artifact")
    metrics_path = Path(metrics_artifact["path"])
    loaded_metrics = _load_json(metrics_path)
    if loaded_metrics.get("schema") != P1_RUNTIME_METRICS_SCHEMA:
        raise RuntimeError("P1 runtime metrics artifact schema drifted")
    validated_file_metrics = validate_runtime_metrics(
        loaded_metrics,
        start_global_step=start_global_step,
        target_global_step=target_global_step,
        expected_iterations=expected_iterations,
    )
    if canonical_json(validated_file_metrics) != canonical_json(validated_metrics):
        raise RuntimeError("P1 runtime inline metrics differ from hash-validated metrics artifact")
    loaded_telemetry = load_gpu_telemetry_peak_vram(Path(telemetry_artifact["path"]))
    if loaded_telemetry["sha256"] != telemetry_artifact["sha256"]:
        raise RuntimeError("P1 runtime telemetry artifact hash drifted")
    peak = validate_peak_vram_mib(telemetry.get("peak_vram_mib"))["peak_vram_mib"]
    if peak != validated_metrics["peak_vram_mib"]:
        raise RuntimeError("P1 runtime evidence metrics/telemetry peak VRAM disagree")
    if peak != loaded_telemetry["peak_vram_mib"]:
        raise RuntimeError("P1 runtime evidence telemetry artifact peak drifted")
    for field in (
        "schema",
        "physical_gpu_index",
        "logical_device",
        "uuid",
        "cuda_visible_devices",
        "world_size",
        "record_count",
        "started_at_epoch_s",
        "ended_at_epoch_s",
        "peak_vram_mib",
    ):
        if telemetry.get(field) != loaded_telemetry.get(field):
            raise RuntimeError(f"P1 runtime evidence telemetry {field} drifted")
    if telemetry.get("schema") != P1_GPU_TELEMETRY_SCHEMA:
        raise RuntimeError("P1 runtime evidence telemetry schema drifted")
    if telemetry.get("uuid") != EXPECTED_GPU_UUID or telemetry.get("physical_gpu_index") not in (EXPECTED_GPU_INDEX, int(EXPECTED_GPU_INDEX)):
        raise RuntimeError("P1 runtime evidence telemetry GPU identity drifted")
    if telemetry.get("logical_device") != EXPECTED_LOGICAL_DEVICE or telemetry.get("cuda_visible_devices") != EXPECTED_GPU_INDEX or telemetry.get("world_size") != 1:
        raise RuntimeError("P1 runtime evidence telemetry process binding drifted")
    return {
        "schema": "a2_cb2h_pro_p1_runtime_evidence_v2",
        "metrics": validated_metrics,
        "metrics_artifact": metrics_artifact,
        "telemetry": dict(telemetry),
        "telemetry_artifact": telemetry_artifact,
    }


def _as_numpy(value: Any, name: str):
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - project dependency
        raise RuntimeError("N3 open-loop adjudication requires numpy") from exc
    array = np.asarray(value)
    if array.dtype == np.dtype(bool) or not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"{name} must be numeric")
    array = np.asarray(array, dtype=np.float64)
    if not bool(np.isfinite(array).all()):
        raise ValueError(f"{name} must contain only finite numeric values")
    return array


def nrmse_stats(prediction: Any, target: Any, mask: Any | None = None) -> dict[str, Any]:
    """Compute the N4/N3 per-action NRMSE: RMSE/(std(target)+1e-6)."""
    import numpy as np

    prediction = _as_numpy(prediction, "prediction")
    target = _as_numpy(target, "target")
    if prediction.shape != target.shape or prediction.ndim != 2 or prediction.shape[1] != EXPECTED_ACTION_DIM:
        raise ValueError("N3 open-loop arrays must have equal shape [N,12]")
    if mask is None:
        selected = np.ones(prediction.shape[0], dtype=bool)
    else:
        selected = np.asarray(mask)
        if selected.dtype != np.dtype(bool):
            raise TypeError("N3 open-loop mask must contain strict boolean values")
        if selected.shape != (prediction.shape[0],):
            raise ValueError("N3 open-loop mask must have shape [N]")
    if not selected.any():
        raise ValueError("N3 open-loop mask selects no rows")
    error = prediction[selected] - target[selected]
    rmse = np.sqrt(np.mean(np.square(error), axis=0))
    denominator = np.std(target[selected], axis=0) + 1e-6
    nrmse = rmse / denominator
    if not bool(np.isfinite(nrmse).all()):
        raise ValueError("N3 open-loop NRMSE output must be finite")
    return {
        "count": int(selected.sum()),
        "mse_mean": float(np.mean(np.square(error))),
        "rmse_mean": float(np.mean(rmse)),
        "nrmse_median_12d": float(np.median(nrmse)),
        "nrmse_max_12d": float(np.max(nrmse)),
        "per_action_rmse": rmse.tolist(),
        "per_action_nrmse": nrmse.tolist(),
    }


def n3_open_loop_nrmse(
    prediction: Any,
    teacher_action: Any,
    *,
    active_mask: Any | None = None,
    stage: Any | None = None,
    branch_identity: Mapping[str, Any] | None = None,
    n3_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Sealable N3 open-loop metrics for one branch checkpoint.

    ``stage`` is optional for callers that also compute per-stage subsets; the
    all-active metric always uses the exact N4 denominator formula.
    """
    result = nrmse_stats(prediction, teacher_action, active_mask)
    result["schema"] = "a2_cb2h_pro_p1_open_loop_nrmse_v1"
    result["n3_phase_manifest_sha256"] = N3_PHASE_MANIFEST_SHA256
    if branch_identity is not None:
        result["branch_identity"] = dict(branch_identity)
    if n3_identity is not None:
        result["n3_identity"] = dict(n3_identity)
    if stage is not None:
        import numpy as np

        stage_array = np.asarray(stage)
        if active_mask is None:
            selected = np.ones(stage_array.shape, dtype=bool)
        else:
            selected = np.asarray(active_mask)
            if selected.dtype != np.dtype(bool):
                raise TypeError("N3 stage active_mask must contain strict boolean values")
        if stage_array.shape != selected.shape:
            raise ValueError("N3 stage and active_mask must have the same shape")
        by_stage = {}
        for value in sorted(set(stage_array[selected].tolist())):
            by_stage[str(int(value))] = nrmse_stats(
                prediction,
                teacher_action,
                selected & (stage_array == value),
            )
        result["by_stage"] = by_stage
    return result


def _formal_records(value: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    records = value.get("episodes") if isinstance(value, Mapping) else value
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise TypeError("formal artifact must contain an episodes sequence")
    result = [record for record in records if isinstance(record, Mapping)]
    if len(result) != len(records):
        raise TypeError("formal episode records must be mappings")
    return result


def _case_value(record: Mapping[str, Any]) -> Any:
    if "case_id" in record:
        return record["case_id"]
    if "randomized_case" in record:
        return record["randomized_case"]
    raise RuntimeError("formal record is missing case_id/randomized_case")


def formal_case_map(metrics: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> tuple[tuple[int, str], ...]:
    records = _formal_records(metrics)
    if len(records) != EXPECTED_EPISODES:
        raise RuntimeError(f"formal evaluation must contain exactly 16 episodes, got {len(records)}")
    pairs = []
    for record in records:
        if "env_id" not in record:
            raise RuntimeError("formal episode is missing env_id")
        pairs.append((int(record["env_id"]), canonical_json(_case_value(record))))
    pairs.sort(key=lambda item: item[0])
    env_ids = [env_id for env_id, _ in pairs]
    if env_ids == list(range(16)):
        normalized_pairs = pairs
    elif env_ids == list(range(1, 17)):
        normalized_pairs = [(env_id - 1, case) for env_id, case in pairs]
    else:
        raise RuntimeError("formal case map must contain env_id 0..15 or 1..16 exactly once")
    if len({case for _, case in pairs}) != EXPECTED_EPISODES:
        raise RuntimeError("formal case map contains duplicate cases")
    return tuple(normalized_pairs)


def validate_case_map_identity(
    case_maps: Sequence[tuple[tuple[int, str], ...] | Mapping[int, Any]],
) -> str:
    if len(case_maps) < 2:
        raise ValueError("fixed16x3 adjudication requires at least two case maps")
    canonical_maps = []
    for case_map in case_maps:
        if isinstance(case_map, Mapping):
            pairs = tuple(sorted((int(key), canonical_json(value)) for key, value in case_map.items()))
        else:
            pairs = tuple((int(key), str(value)) for key, value in case_map)
        keys = [key for key, _ in pairs]
        if keys == list(range(1, 17)):
            pairs = tuple((key - 1, value) for key, value in pairs)
        elif keys != list(range(16)):
            raise RuntimeError("every formal case map must contain exactly env_id 0..15 or 1..16")
        if len(pairs) != EXPECTED_EPISODES:
            raise RuntimeError("every formal case map must contain exactly 16 cases")
        canonical_maps.append(pairs)
    first = canonical_maps[0]
    if any(case_map != first for case_map in canonical_maps[1:]):
        raise P1Blocked("formal fixed16x3 case identity mismatch; paired gates are invalid")
    return sha256_bytes(canonical_json(first).encode("utf-8"))


def validate_n3_contract(root: Path = N3_INPUT_ROOT) -> dict[str, Any]:
    """Validate the sealed three-replicate N3 trajectory input used by P1."""
    from gr00t.rl.scripts import run_a2_cb2h_pro_n4 as n4

    inputs = n4.validate_n3_inputs(root.expanduser().resolve())
    if inputs.phase_manifest_sha256 != N3_PHASE_MANIFEST_SHA256:
        raise RuntimeError("N3 phase manifest SHA256 drifted")
    if len(inputs.replicates) != 3:
        raise RuntimeError("P1 N3 open-loop adjudication requires exactly three replicates")
    active_frames = [replicate.active_frame_count for replicate in inputs.replicates]
    if active_frames != [10206, 10206, 10206]:
        raise RuntimeError(f"P1 N3 active-frame counts drifted: {active_frames}")
    case_hash = validate_case_map_identity(
        [
            tuple((index, case_id) for index, case_id in enumerate(replicate.case_ids))
            for replicate in inputs.replicates
        ]
    )
    replicate_details = []
    experience_identity = None
    for replicate in inputs.replicates:
        if all(
            hasattr(replicate, field)
            for field in (
                "replicate_id",
                "h5_path",
                "h5_sha256",
                "trajectory_manifest_path",
                "trajectory_manifest_sha256",
                "row_count",
            )
        ):
            replicate_details.append(
                {
                    "replicate_id": replicate.replicate_id,
                    "h5": ArtifactRef(replicate.h5_path, replicate.h5_sha256).as_dict(),
                    "trajectory_manifest": ArtifactRef(
                        replicate.trajectory_manifest_path, replicate.trajectory_manifest_sha256
                    ).as_dict(),
                    "row_count": replicate.row_count,
                    "active_frame_count": replicate.active_frame_count,
                    "case_ids": list(replicate.case_ids),
                }
            )
            trajectory = _load_json(replicate.trajectory_manifest_path)
            experience = trajectory.get("experience")
            if not isinstance(experience, Mapping):
                raise RuntimeError("N3 trajectory manifest lacks exact experience identity")
            if experience_identity is None:
                experience_identity = dict(experience)
            elif dict(experience) != experience_identity:
                raise RuntimeError("N3 replicate experience identity drifted")
            import h5py
            with h5py.File(replicate.h5_path.expanduser().resolve(strict=True), "r") as handle:
                active = handle["active_mask"][:]
                active_identity = {
                    "active_mask": active.astype(bool).tolist(),
                    "env_id": handle["env_id"][:].tolist(),
                    "frame_id": handle["frame_id"][:].tolist(),
                    "case_id": [bytes(value).decode("ascii") for value in handle["case_id"][:]],
                    "pre_action_stage": handle["pre_action_stage"][:].tolist(),
                }
            replicate_details[-1]["active_mask_sha256"] = sha256_bytes(
                canonical_json(active_identity).encode("utf-8")
            )
            replicate_details[-1]["active_frame_count"] = int(sum(active_identity["active_mask"]))
    return {
        "root": str(inputs.root),
        "phase_manifest": ArtifactRef(
            inputs.phase_manifest_path, inputs.phase_manifest_sha256
        ).as_dict(),
        "replicate_count": len(inputs.replicates),
        "active_frame_count": active_frames,
        "case_map_sha256": case_hash,
        "replicates": replicate_details,
        "experience_identity": experience_identity,
    }


def _strict_finite_json(value: Any, name: str) -> None:
    """Reject booleans, numeric strings, and non-finite JSON numbers."""
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} contains a non-finite numeric value")
        return
    if isinstance(value, str):
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _strict_finite_json(child, f"{name}.{key}")
        return
    if isinstance(value, Sequence):
        for index, child in enumerate(value):
            _strict_finite_json(child, f"{name}[{index}]")


def _branch_identity(branch: P1BranchSpec | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(branch, P1BranchSpec):
        return {
            "mode": branch.mode,
            "checkpoint": {"path": str(branch.final_checkpoint.resolve()), "sha256": sha256_file(branch.final_checkpoint)},
            "config": {
                "path": str(branch.final_checkpoint.with_name("config.yaml").resolve()),
                "sha256": sha256_file(branch.final_checkpoint.with_name("config.yaml")),
            },
            "global_step": branch.target_global_step,
        }
    if not isinstance(branch, Mapping):
        raise TypeError("branch identity must be a P1BranchSpec or mapping")
    mode = branch.get("branch", branch.get("mode"))
    final = branch.get("final_checkpoint")
    config = branch.get("final_config")
    if not isinstance(mode, str) or not isinstance(final, Mapping) or not isinstance(config, Mapping):
        raise TypeError("branch identity mapping lacks mode/final checkpoint/config")
    return {
        "mode": mode,
        "checkpoint": _sealed_artifact(final, name="branch.final_checkpoint"),
        "config": _sealed_artifact(config, name="branch.final_config"),
        "global_step": _strict_int(final.get("global_step"), "branch.final_checkpoint.global_step"),
    }


def _n3_replicate_identity(n3_contract: Mapping[str, Any], replicate_id: str) -> dict[str, Any]:
    if not isinstance(n3_contract, Mapping):
        raise TypeError("n3_contract must be a mapping")
    phase = n3_contract.get("phase_manifest")
    replicas = n3_contract.get("replicates")
    if not isinstance(phase, Mapping) or not isinstance(replicas, Sequence):
        raise TypeError("n3_contract lacks phase_manifest/replicates")
    matches = [item for item in replicas if isinstance(item, Mapping) and item.get("replicate_id") == replicate_id]
    if len(matches) != 1:
        raise RuntimeError(f"N3 replicate identity is not unique: {replicate_id!r}")
    item = matches[0]
    return {
        "phase_manifest": _sealed_artifact(phase, name="n3.phase_manifest"),
        "replicate_id": replicate_id,
        "h5": _sealed_artifact(item.get("h5"), name="n3.replicate.h5"),
        "trajectory_manifest": _sealed_artifact(
            item.get("trajectory_manifest"), name="n3.replicate.trajectory_manifest"
        ),
        "case_map_sha256": n3_contract.get("case_map_sha256"),
    }


def build_n3_inference_command(
    branch: P1BranchSpec | Mapping[str, Any],
    n3_root: Path,
    output_root: Path,
    *,
    replicate_id: str,
    n3_contract: Mapping[str, Any] | None = None,
    inference_script: Path | None = None,
) -> tuple[str, ...]:
    """Build a checkpoint- and N3-hash-bound recurrent-reset inference command."""
    if not replicate_id or "/" in replicate_id or "\\" in replicate_id:
        raise ValueError("N3 replicate_id must be a path-safe non-empty label")
    identity = _branch_identity(branch)
    if identity["mode"] not in P1_FORWARD_MODES:
        raise ValueError("N3 branch mode is invalid")
    n3_contract = validate_n3_contract(n3_root) if n3_contract is None else n3_contract
    declared_n3_root = n3_contract.get("root")
    if declared_n3_root is not None and Path(str(declared_n3_root)).expanduser().resolve() != n3_root.expanduser().resolve():
        raise RuntimeError("N3 command root does not match the validated N3 contract root")
    replicate = _n3_replicate_identity(n3_contract, replicate_id)
    output_root = validate_fresh_output_root(output_root)
    inference_script = (
        REPO_ROOT / "gr00t/rl/scripts/run_a2_cb2h_pro_p1.py"
        if inference_script is None
        else inference_script.expanduser().resolve(strict=True)
    )
    return (
        sys.executable,
        str(inference_script),
        "--n3-infer",
        "--mode",
        identity["mode"],
        "--checkpoint",
        identity["checkpoint"]["path"],
        "--checkpoint-sha256",
        identity["checkpoint"]["sha256"],
        "--config",
        identity["config"]["path"],
        "--config-sha256",
        identity["config"]["sha256"],
        "--device",
        EXPECTED_LOGICAL_DEVICE,
        "--n3-root",
        str(n3_root.expanduser().resolve(strict=True)),
        "--n3-phase-manifest",
        replicate["phase_manifest"]["path"],
        "--n3-phase-manifest-sha256",
        replicate["phase_manifest"]["sha256"],
        "--n3-h5",
        replicate["h5"]["path"],
        "--n3-h5-sha256",
        replicate["h5"]["sha256"],
        "--n3-trajectory-manifest",
        replicate["trajectory_manifest"]["path"],
        "--n3-trajectory-manifest-sha256",
        replicate["trajectory_manifest"]["sha256"],
        "--replicate-id",
        replicate_id,
        "--recurrent-reset-per-replicate",
        "--output",
        str(output_root),
    )


def load_n3_action_artifact(
    path: Path,
    *,
    expected_sha256: str,
    branch: P1BranchSpec | Mapping[str, Any],
    n3_contract: Mapping[str, Any],
    replicate_id: str,
    expected_experience: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load active-row N3 actions only when every sealed identity is exact."""
    path = path.expanduser().resolve(strict=True)
    _assert_hash(path, expected_sha256, "P1 N3 action artifact")
    manifest = _load_json(path)
    if manifest.get("schema") != P1_N3_ACTION_SCHEMA:
        raise RuntimeError("P1 N3 action artifact schema drifted")
    content_sha = manifest.get("manifest_content_sha256")
    _require_sha(content_sha, "N3 action manifest_content_sha256")
    raw = dict(manifest)
    raw.pop("manifest_content_sha256", None)
    if sha256_bytes(canonical_json(raw).encode("utf-8")) != content_sha:
        raise RuntimeError("P1 N3 action manifest content hash drifted")
    identity = _branch_identity(branch)
    if manifest.get("forward_mode") != identity["mode"] or manifest.get("branch") != identity["mode"]:
        raise RuntimeError("P1 N3 action mode identity drifted")
    if manifest.get("replicate_id") != replicate_id:
        raise RuntimeError("P1 N3 action replicate identity drifted")
    if manifest.get("recurrent_reset_per_replicate") is not True:
        raise RuntimeError("P1 N3 inference must reset recurrent state per replicate")
    checkpoint = _sealed_artifact(manifest.get("checkpoint"), name="N3 action checkpoint")
    config = _sealed_artifact(manifest.get("config"), name="N3 action config")
    if checkpoint != identity["checkpoint"] or config != identity["config"]:
        raise RuntimeError("P1 N3 action artifact is bound to a different branch checkpoint/config")
    n3 = _n3_replicate_identity(n3_contract, replicate_id)
    if (
        manifest.get("n3_phase_manifest") != n3["phase_manifest"]
        or manifest.get("n3_h5") != n3["h5"]
        or manifest.get("n3_trajectory_manifest") != n3["trajectory_manifest"]
    ):
        raise RuntimeError("P1 N3 action artifact is bound to a different N3 phase/HDF5 identity")
    experience = manifest.get("experience")
    expected_experience = n3_contract.get("experience_identity") if expected_experience is None else expected_experience
    if not isinstance(experience, Mapping) or not isinstance(expected_experience, Mapping) or dict(experience) != dict(expected_experience):
        raise RuntimeError("P1 N3 action experience identity drifted")
    replicate_record = next(
        item for item in n3_contract["replicates"] if item.get("replicate_id") == replicate_id
    )
    active_frame_count = replicate_record.get("active_frame_count")
    if isinstance(active_frame_count, bool) or not isinstance(active_frame_count, int) or active_frame_count != EXPECTED_ACTIVE_FRAME_COUNT:
        raise RuntimeError("N3 active-frame count contract drifted")
    if manifest.get("active_frame_count") != active_frame_count:
        raise RuntimeError("N3 action active-frame count drifted")
    if manifest.get("active_mask_sha256") != replicate_record.get("active_mask_sha256"):
        raise RuntimeError("N3 action active-mask identity drifted")
    active_identity = manifest.get("active_identity")
    if not isinstance(active_identity, Mapping):
        raise TypeError("N3 action active_identity must be a mapping")
    for key in ("env_id", "frame_id", "case_id", "pre_action_stage"):
        values = active_identity.get(key)
        if not isinstance(values, list) or len(values) != active_frame_count:
            raise RuntimeError(f"N3 action active_identity {key} length drifted")
        if key != "case_id" and any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise TypeError(f"N3 action active_identity {key} values must be strict ints")
        if key == "case_id" and any(not isinstance(value, str) for value in values):
            raise TypeError("N3 action active_identity case_id values must be strings")
    active_identity_sha = sha256_bytes(canonical_json(dict(active_identity)).encode("utf-8"))
    declared_active_identity_sha = manifest.get("active_identity_sha256")
    if declared_active_identity_sha is None or active_identity_sha != declared_active_identity_sha:
        raise RuntimeError("N3 action active identity content hash drifted")
    _strict_finite_json(manifest.get("actions"), "N3 actions")
    actions = manifest.get("actions")
    if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)) or not actions:
        raise TypeError("N3 actions must be a non-empty nested numeric sequence")
    rows = []
    for index, row in enumerate(actions):
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) != EXPECTED_ACTION_DIM:
            raise ValueError(f"N3 action row {index} must have exactly 12 values")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in row):
            raise TypeError(f"N3 action row {index} contains non-finite/non-numeric values")
        rows.append([float(value) for value in row])
    if len(rows) != active_frame_count:
        raise RuntimeError("N3 actions must contain exactly active frames, never padded rows")
    teacher_action = manifest.get("teacher_action")
    if not isinstance(teacher_action, Sequence) or len(teacher_action) != len(rows):
        raise ValueError("N3 teacher_action must align exactly with active action rows")
    for index, row in enumerate(teacher_action):
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) != EXPECTED_ACTION_DIM:
            raise ValueError(f"N3 teacher_action row {index} must have 12 values")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in row):
            raise TypeError(f"N3 teacher_action row {index} is malformed")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "branch": identity["mode"],
        "replicate_id": replicate_id,
        "checkpoint": checkpoint,
        "config": config,
        "actions": rows,
        "teacher_action": teacher_action,
        "experience": dict(experience),
        "n3_phase_manifest": n3["phase_manifest"],
        "n3_h5": n3["h5"],
        "n3_trajectory_manifest": n3["trajectory_manifest"],
        "active_frame_count": active_frame_count,
        "active_mask_sha256": manifest["active_mask_sha256"],
        "active_identity_sha256": active_identity_sha,
        "active_identity": dict(active_identity),
    }


def load_formal_replicate_artifact(
    metrics_path: Path,
    selection_path: Path,
    *,
    metrics_sha256: str,
    selection_sha256: str,
    branch: P1BranchSpec | Mapping[str, Any],
    replicate_id: str,
    expected_mode: str,
    expected_experience: Mapping[str, Any],
    manifest_path: Path | None = None,
    manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Load current evaluator-v2 metrics/selection bound to exact branch identity.

    The evaluator's metrics and selection files are the formal provenance.  P1
    deliberately does not require a synthetic sidecar manifest: accepting one
    would create a second source of truth and would fail on the current v2
    evaluator artifacts.
    """
    if manifest_path is not None or manifest_sha256 is not None:
        raise ValueError("P1 formal sidecar manifests are unsupported; use evaluator-v2 paths directly")
    metrics_path = metrics_path.expanduser().resolve(strict=True)
    selection_path = selection_path.expanduser().resolve(strict=True)
    _assert_hash(metrics_path, metrics_sha256, "formal metrics artifact")
    _assert_hash(selection_path, selection_sha256, "formal selection artifact")
    metrics = _load_json(metrics_path)
    selection = _load_json(selection_path)
    _strict_finite_json(metrics, "formal metrics")
    _strict_finite_json(selection, "formal selection")
    if metrics.get("schema") != "a2_student_v19_metrics_v2":
        raise RuntimeError("formal metrics schema drifted")
    if selection.get("schema") != "a2_student_v19_selection_v2":
        raise RuntimeError("formal selection schema drifted")
    if metrics.get("controller") != "student" or selection.get("controller") != "student":
        raise RuntimeError("formal artifacts must describe the Student controller")
    if metrics.get("replicate_id") != replicate_id or selection.get("replicate_id") != replicate_id:
        raise RuntimeError("formal replicate_id drifted")
    if metrics.get("case_seed") != 0 or selection.get("case_seed") != 0:
        raise RuntimeError("formal case_seed must be exactly 0")
    contract = metrics.get("contract")
    selection_contract = selection.get("contract")
    if not isinstance(contract, Mapping) or dict(selection_contract or {}) != dict(contract):
        raise RuntimeError("formal metrics/selection contract identity drifted")
    required_contract = {
        "case_seed": 0,
        "controller": "student",
        "enforce_teacher_rollout": False,
        "num_envs": EXPECTED_EPISODES,
        "one_episode_per_env": True,
        "pure_student": True,
        "ratio_teacher_rollout": 0.0,
        "replicate_id": replicate_id,
        "student_d435i_forward_mode": expected_mode,
        "use_a2_base": True,
    }
    for key, value in required_contract.items():
        if contract.get(key) != value:
            raise RuntimeError(f"formal contract drifted for {key}: expected {value!r}")
    if contract.get("experience_identity") != dict(expected_experience):
        raise RuntimeError("formal experience identity drifted")
    if metrics.get("experience") != dict(expected_experience) or selection.get("experience") != dict(expected_experience):
        raise RuntimeError("formal top-level experience identity drifted")
    if not isinstance(contract.get("checkpoint_identity"), Mapping) or contract.get("checkpoint_identity") != metrics.get("checkpoint"):
        raise RuntimeError("formal metrics checkpoint identity copy drifted")
    if selection.get("checkpoint") != metrics.get("checkpoint"):
        raise RuntimeError("formal selection checkpoint identity drifted")
    identity = _branch_identity(branch)
    if expected_mode != identity["mode"]:
        raise RuntimeError("formal expected mode does not match branch identity")
    checkpoint_identity = metrics.get("checkpoint")
    if not isinstance(checkpoint_identity, Mapping):
        raise TypeError("formal checkpoint identity must be a mapping")
    if {
        "path": checkpoint_identity.get("path"),
        "sha256": checkpoint_identity.get("sha256"),
    } != identity["checkpoint"]:
        raise RuntimeError("formal artifact is bound to a different branch checkpoint")
    if {
        "path": checkpoint_identity.get("config_path"),
        "sha256": checkpoint_identity.get("config_sha256"),
    } != identity["config"]:
        raise RuntimeError("formal artifact is bound to a different branch config")
    episodes = metrics.get("episodes")
    if not isinstance(episodes, Sequence) or isinstance(episodes, (str, bytes)) or len(episodes) != EXPECTED_EPISODES:
        raise RuntimeError("formal metrics must contain exactly 16 episodes")
    for index, episode in enumerate(episodes):
        if not isinstance(episode, Mapping):
            raise TypeError(f"formal episode {index} must be a mapping")
        if isinstance(episode.get("env_id"), bool) or not isinstance(episode.get("env_id"), int):
            raise TypeError(f"formal episode {index} env_id must be int")
        if isinstance(episode.get("episode_index"), bool) or not isinstance(episode.get("episode_index"), int):
            raise TypeError(f"formal episode {index} episode_index must be int")
        if type(episode.get("goal_reached")) is not bool:
            raise TypeError(f"formal episode {index} goal_reached must be bool")
        if isinstance(episode.get("max_stage"), bool) or not isinstance(episode.get("max_stage"), int):
            raise TypeError(f"formal episode {index} max_stage must be int")
        if not isinstance(episode.get("randomized_case"), Mapping):
            raise TypeError(f"formal episode {index} randomized_case must be a mapping")
    formal_case_map(metrics)
    source = selection.get("source_metrics")
    if not isinstance(source, Mapping):
        raise TypeError("formal selection source_metrics must be a mapping")
    if source.get("path") != str(metrics_path) or source.get("sha256") != metrics_sha256:
        raise RuntimeError("formal selection is not bound to the exact metrics artifact")
    from gr00t.rl.scripts import run_a2_student_eval_v19 as evaluator

    loaded_selection, loaded_metrics = evaluator.load_sealed_selection(selection_path, metrics_path)
    if loaded_metrics.get("schema") != metrics.get("schema"):
        raise RuntimeError("formal evaluator metrics reload schema drifted")
    if loaded_selection.get("source_metrics") != source:
        raise RuntimeError("formal evaluator selection source binding drifted")
    return {
        "replicate_id": replicate_id,
        "branch": expected_mode,
        "experience": dict(expected_experience),
        "metrics": artifact_ref(metrics_path),
        "selection": artifact_ref(selection_path),
        "episodes": [dict(record, replicate_index=0) for record in episodes],
        "checkpoint": identity["checkpoint"],
        "config": identity["config"],
        "selection_schema": loaded_selection["schema"],
    }


def validate_n2_contract(root: Path = N2_INPUT_ROOT) -> dict[str, Any]:
    """Validate N2's sealed fixed-case sweep and source checkpoint binding."""
    root = root.expanduser().resolve(strict=True)
    if root.name != N2_INPUT_ROOT.name:
        raise RuntimeError(f"N2 input root name drifted: {root.name!r}")
    manifest_path = root / "phase_a_manifest.json"
    if sha256_file(manifest_path) != N2_PHASE_MANIFEST_SHA256:
        raise RuntimeError("N2 phase manifest SHA256 drifted")
    manifest = _load_json(manifest_path)
    if manifest.get("schema") != "a2_cb2h_pro_phase_a_v1" or manifest.get("operation") != "n2":
        raise RuntimeError("N2 phase manifest schema/operation drifted")
    if manifest.get("controller") != "student":
        raise RuntimeError("N2 phase manifest must describe the Student controller")
    if manifest.get("case_identity_mapping_equal") is not True:
        raise RuntimeError("N2 phase manifest does not prove fixed case identity")
    if manifest.get("required_steps") != [1000, 2500, 5000, 7500, 10000]:
        raise RuntimeError("N2 required step grid drifted")
    artifact_records = manifest.get("artifacts")
    if not isinstance(artifact_records, Sequence) or not artifact_records:
        raise RuntimeError("N2 phase manifest has no sealed artifacts")
    for record in artifact_records:
        if not isinstance(record, Mapping):
            raise RuntimeError("N2 artifact record must be a mapping")
        relative = Path(str(record.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("N2 artifact path escapes the sealed root")
        artifact_path = (root / relative).resolve()
        if not artifact_path.is_file() or not artifact_path.is_relative_to(root):
            raise FileNotFoundError(f"N2 artifact is unavailable: {artifact_path}")
        expected_sha = _require_sha(record.get("sha256"), "N2 artifact sha256")
        if sha256_file(artifact_path) != expected_sha:
            raise RuntimeError(f"N2 artifact SHA256 drifted: {artifact_path}")

    checkpoint_refs = []

    def collect_checkpoint_refs(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("global_step") == EXPECTED_INITIAL_GLOBAL_STEP and "sha256" in value:
                checkpoint_refs.append(value)
            for child in value.values():
                collect_checkpoint_refs(child)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for child in value:
                collect_checkpoint_refs(child)

    collect_checkpoint_refs(manifest)
    if not checkpoint_refs:
        raise RuntimeError("N2 manifest has no step10000 checkpoint binding")
    for reference in checkpoint_refs:
        if reference.get("sha256") != SOURCE_CHECKPOINT_SHA256:
            raise RuntimeError("N2 checkpoint binding does not use the exact source SHA256")
        config_sha = reference.get("config_sha256")
        if config_sha is not None and config_sha != SOURCE_CONFIG_SHA256:
            raise RuntimeError("N2 checkpoint config binding does not use the exact source SHA256")
    return {
        "root": str(root),
        "phase_manifest": ArtifactRef(manifest_path, N2_PHASE_MANIFEST_SHA256).as_dict(),
        "artifact_count": len(artifact_records),
        "required_steps": list(manifest["required_steps"]),
        "checkpoint_sha256": SOURCE_CHECKPOINT_SHA256,
        "checkpoint_config_sha256": SOURCE_CONFIG_SHA256,
    }


def compare_formal_outcomes(
    sequential: Sequence[Mapping[str, Any]],
    packed: Sequence[Mapping[str, Any]],
    *,
    replicate_count: int = 3,
) -> dict[str, Any]:
    """Compare paired 16-episode formal outcomes without calling zero goals quality."""
    if replicate_count != 3:
        raise ValueError("P1 formal adjudication requires exactly three replicates")
    sequential = _formal_records(sequential)
    packed = _formal_records(packed)
    expected_count = EXPECTED_EPISODES * replicate_count
    if len(sequential) != expected_count or len(packed) != expected_count:
        raise ValueError(f"formal adjudication requires {expected_count} records per branch")
    def with_replicate_index(records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        indexed = []
        for index, record in enumerate(records):
            if "replicate_index" in record:
                replicate_index = int(record["replicate_index"])
            else:
                replicate_index = index // EXPECTED_EPISODES
            if not 0 <= replicate_index < replicate_count:
                raise RuntimeError("formal replicate_index is outside the fixed 3-replicate contract")
            indexed.append({**record, "replicate_index": replicate_index})
        return indexed

    sequential = with_replicate_index(sequential)
    packed = with_replicate_index(packed)
    keys = lambda record: (
        int(record.get("replicate_index", 0)),
        int(record["env_id"]),
        int(record.get("episode_index", 0)),
    )
    seq_by_key = {keys(record): record for record in sequential}
    packed_by_key = {keys(record): record for record in packed}
    if set(seq_by_key) != set(packed_by_key):
        raise P1Blocked("formal sequential/packed episode identity mismatch")
    seq_cases = []
    packed_cases = []
    for index in range(replicate_count):
        seq_cases.append(formal_case_map([record for record in sequential if int(record.get("replicate_index", 0)) == index]))
        packed_cases.append(formal_case_map([record for record in packed if int(record.get("replicate_index", 0)) == index]))
    case_hash = validate_case_map_identity([*seq_cases, *packed_cases])
    def summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if any(not isinstance(record.get("goal_reached", False), bool) for record in records):
            raise TypeError("formal goal_reached fields must be booleans")
        goals = sum(bool(record.get("goal_reached", False)) for record in records)
        stages = [int(record.get("max_stage", -1)) for record in records]
        if any(stage < 0 for stage in stages):
            raise RuntimeError("formal max_stage must be non-negative")
        return {
            "count": len(records),
            "goals": goals,
            "goal_rate": goals / len(records),
            "mean_max_stage": sum(stages) / len(stages),
            "stage0_count": sum(stage == 0 for stage in stages),
            "max_stage_counts": {str(stage): stages.count(stage) for stage in sorted(set(stages))},
        }
    seq_summary = summary(sequential)
    packed_summary = summary(packed)
    stage0_reduction = seq_summary["stage0_count"] - packed_summary["stage0_count"]
    mean_stage_delta = packed_summary["mean_max_stage"] - seq_summary["mean_max_stage"]
    return {
        "replicate_count": replicate_count,
        "case_map_sha256": case_hash,
        "sequential": seq_summary,
        "packed": packed_summary,
        "mean_stage_delta": mean_stage_delta,
        "stage0_count_reduction": stage0_reduction,
        "stage0_count_reduction_per_16": stage0_reduction / replicate_count,
        "quality_guard": {
            "packed_goal_count": packed_summary["goals"],
            "zero_goals_is_not_quality_pass": packed_summary["goals"] == 0,
        },
    }


def directional_gates(
    *,
    sequential_nrmse_median: float,
    packed_nrmse_median: float,
    mean_stage_delta: float,
    stage0_count_reduction_per_16: float,
) -> dict[str, Any]:
    if sequential_nrmse_median < 0 or packed_nrmse_median < 0:
        raise ValueError("NRMSE values cannot be negative")
    if sequential_nrmse_median == 0:
        nrmse_improvement = 0.0 if packed_nrmse_median == 0 else -math.inf
    else:
        nrmse_improvement = (
            sequential_nrmse_median - packed_nrmse_median
        ) / sequential_nrmse_median
    gates = {
        "nrmse": {
            "improvement": nrmse_improvement,
            "threshold": 0.10,
            "pass": nrmse_improvement >= 0.10,
        },
        "mean_stage": {
            "delta": mean_stage_delta,
            "threshold": 0.20,
            "pass": mean_stage_delta >= 0.20,
        },
        "stage0": {
            "reduction_per_16": stage0_count_reduction_per_16,
            "threshold": 2.0,
            "pass": stage0_count_reduction_per_16 >= 2.0,
        },
    }
    return {"gates": gates, "any_directional_pass": any(item["pass"] for item in gates.values())}


def _adjudicate_p1(
    *,
    sequential_nrmse: Mapping[str, Any],
    packed_nrmse: Mapping[str, Any],
    sequential_formal: Sequence[Mapping[str, Any]],
    packed_formal: Sequence[Mapping[str, Any]],
    replicate_count: int = 3,
) -> dict[str, Any]:
    outcomes = compare_formal_outcomes(
        sequential_formal, packed_formal, replicate_count=replicate_count
    )
    gates = directional_gates(
        sequential_nrmse_median=float(sequential_nrmse["nrmse_median_12d"]),
        packed_nrmse_median=float(packed_nrmse["nrmse_median_12d"]),
        mean_stage_delta=float(outcomes["mean_stage_delta"]),
        stage0_count_reduction_per_16=float(outcomes["stage0_count_reduction_per_16"]),
    )
    if outcomes["quality_guard"]["zero_goals_is_not_quality_pass"]:
        status = "INCONCLUSIVE_NO_GOAL_QUALITY" if gates["any_directional_pass"] else "FAIL_NO_DIRECTIONAL_GATE"
    elif gates["any_directional_pass"]:
        status = "PASS_DIRECTIONAL"
    else:
        status = "FAIL_NO_DIRECTIONAL_GATE"
    return {
        "schema": P1_ADJUDICATION_SCHEMA,
        "status": status,
        "directional_gates": gates,
        "formal_outcomes": outcomes,
        "open_loop_nrmse": {
            "sequential": dict(sequential_nrmse),
            "packed": dict(packed_nrmse),
        },
        "quality_pass": status == "PASS_DIRECTIONAL",
    }


def adjudicate_p1(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Fail-closed compatibility stub; raw adjudication is not a public API."""
    raise P1Blocked(
        "raw P1 adjudication is unavailable; use adjudicate_p1_from_paths with sealed artifacts"
    )


def adjudicate_p1_from_paths(
    *,
    branch_roots: Mapping[str, Path] | None = None,
    branch_manifest_shas: Mapping[str, str] | None = None,
    sequential_root: Path | None = None,
    packed_root: Path | None = None,
    sequential_manifest_sha256: str | None = None,
    packed_manifest_sha256: str | None = None,
    n3_root: Path = N3_INPUT_ROOT,
    n3_phase_manifest_sha256: str = N3_PHASE_MANIFEST_SHA256,
    formal_artifacts: Mapping[str, Sequence[Mapping[str, Any]]],
    action_artifacts: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Adjudicate only artifacts reached through sealed branch/N3 loaders.

    Callers provide roots and expected manifest hashes, never pre-loaded branch
    or N3 identity mappings.  All checkpoint/config/mode/experience identities
    are derived from the sealed manifests before formal/action loaders run.
    """
    if set(formal_artifacts) != set(P1_BRANCHES) or set(action_artifacts) != set(P1_BRANCHES):
        raise ValueError("P1 path adjudication requires both sequential and packed branches/artifacts")
    explicit_roots = (sequential_root, packed_root, sequential_manifest_sha256, packed_manifest_sha256)
    if branch_roots is not None or branch_manifest_shas is not None:
        if any(value is not None for value in explicit_roots):
            raise ValueError("P1 branch roots must use either branch_roots/branch_manifest_shas or explicit roots, not both")
        if not isinstance(branch_roots, Mapping) or not isinstance(branch_manifest_shas, Mapping):
            raise TypeError("P1 branch_roots and branch_manifest_shas must be mappings together")
        if set(branch_roots) != set(P1_BRANCHES) or set(branch_manifest_shas) != set(P1_BRANCHES):
            raise ValueError("P1 branch roots/hashes require sequential and packed entries")
        branch_roots = {mode: Path(branch_roots[mode]) for mode in P1_BRANCHES}
        branch_manifest_shas = {mode: branch_manifest_shas[mode] for mode in P1_BRANCHES}
    else:
        if any(value is None for value in explicit_roots):
            raise ValueError("P1 path adjudication requires both branch roots and expected manifest SHAs")
        branch_roots = {"sequential": Path(sequential_root), "packed": Path(packed_root)}
        branch_manifest_shas = {
            "sequential": sequential_manifest_sha256,
            "packed": packed_manifest_sha256,
        }
    sealed_branches: dict[str, dict[str, Any]] = {}
    branch_identities: dict[str, Mapping[str, Any]] = {}
    for mode in P1_BRANCHES:
        manifest = load_sealed_branch_manifest(
            branch_roots[mode],
            expected_sha256=branch_manifest_shas[mode],
            expected_mode=mode,
            expected_target_global_step=INITIAL_TARGET_GLOBAL_STEP,
        )
        sealed_branches[mode] = manifest
        branch_identities[mode] = {
            "branch": mode,
            "final_checkpoint": manifest["final_checkpoint"],
            "final_config": manifest["final_config"],
        }
    n3_root = n3_root.expanduser().resolve(strict=True)
    n3_contract = validate_n3_contract(n3_root)
    expected_phase_sha = _require_sha(n3_phase_manifest_sha256, "P1 expected N3 phase manifest SHA256")
    phase_ref = n3_contract.get("phase_manifest")
    if not isinstance(phase_ref, Mapping) or phase_ref.get("sha256") != expected_phase_sha:
        raise RuntimeError("P1 N3 phase manifest does not match the caller-provided expected SHA256")
    phase_path = n3_root / "phase_a_manifest.json"
    _assert_hash(phase_path, expected_phase_sha, "P1 N3 phase manifest")
    expected_experience = n3_contract.get("experience_identity")
    if not isinstance(expected_experience, Mapping):
        raise RuntimeError("P1 N3 sealed contract lacks one exact experience identity")
    n3_replicate_ids = {
        item.get("replicate_id")
        for item in n3_contract.get("replicates", [])
        if isinstance(item, Mapping)
    }
    if len(n3_replicate_ids) != 3 or any(not isinstance(value, str) for value in n3_replicate_ids):
        raise RuntimeError("P1 N3 sealed contract must contain three distinct replicate IDs")
    formal_records: dict[str, list[Mapping[str, Any]]] = {}
    nrmse: dict[str, Mapping[str, Any]] = {}
    for mode in P1_BRANCHES:
        records: list[Mapping[str, Any]] = []
        metrics_by_rep = formal_artifacts[mode]
        actions_by_rep = action_artifacts[mode]
        if len(metrics_by_rep) != 3 or len(actions_by_rep) != 3:
            raise ValueError("P1 path adjudication requires exactly three formal/N3 replicates per branch")
        if any(not isinstance(artifact, Mapping) for artifact in (*metrics_by_rep, *actions_by_rep)):
            raise TypeError("P1 formal/N3 adjudication inputs must be path mappings")
        formal_ids = [artifact.get("replicate_id") for artifact in metrics_by_rep]
        action_ids = [artifact.get("replicate_id") for artifact in actions_by_rep]
        if any(not isinstance(value, str) for value in (*formal_ids, *action_ids)):
            raise TypeError("P1 formal/N3 replicate_id values must be strings")
        if len(set(formal_ids)) != 3 or len(set(action_ids)) != 3 or set(formal_ids) != set(action_ids):
            raise P1Blocked("P1 formal/N3 replicate IDs must be three distinct aligned identities")
        if set(formal_ids) != n3_replicate_ids:
            raise P1Blocked("P1 formal/N3 replicate IDs do not match the sealed N3 replicate identities")
        formal_by_id = {artifact["replicate_id"]: artifact for artifact in metrics_by_rep}
        action_by_id = {artifact["replicate_id"]: artifact for artifact in actions_by_rep}
        loaded_formal = []
        for replicate_index, replicate_id in enumerate(sorted(formal_ids)):
            artifact = formal_by_id[replicate_id]
            if not isinstance(artifact, Mapping):
                raise TypeError("formal adjudication inputs must be path mappings")
            if any(key in artifact for key in ("episodes", "metrics", "selection")) and not {
                "metrics_path",
                "selection_path",
                "metrics_sha256",
                "selection_sha256",
            }.issubset(artifact):
                raise P1Blocked("raw formal records are forbidden; provide evaluator-v2 paths and expected SHAs")
            required = ("metrics_path", "selection_path", "metrics_sha256", "selection_sha256", "replicate_id")
            if any(key not in artifact for key in required):
                raise ValueError("formal adjudication path mapping lacks metrics/selection path/hash/replicate_id")
            loaded = load_formal_replicate_artifact(
                Path(artifact["metrics_path"]),
                Path(artifact["selection_path"]),
                metrics_sha256=artifact["metrics_sha256"],
                selection_sha256=artifact["selection_sha256"],
                branch=branch_identities[mode],
                replicate_id=replicate_id,
                expected_mode=mode,
                expected_experience=expected_experience,
            )
            loaded_formal.append(loaded)
            records.extend(dict(record, replicate_index=replicate_index) for record in loaded["episodes"])
        formal_records[mode] = records
        nrmse_values = []
        for replicate_id in sorted(action_ids):
            artifact = action_by_id[replicate_id]
            if not isinstance(artifact, Mapping):
                raise TypeError("N3 adjudication inputs must be path mappings")
            if any(key in artifact for key in ("actions", "teacher_action", "active_identity")) and "path" not in artifact:
                raise P1Blocked("raw N3 action records are forbidden; provide a sealed action path and expected SHA")
            if any(key not in artifact for key in ("path", "sha256", "replicate_id")):
                raise ValueError("N3 adjudication path mapping lacks path/sha256/replicate_id")
            loaded_action = load_n3_action_artifact(
                Path(artifact["path"]),
                expected_sha256=artifact["sha256"],
                branch=branch_identities[mode],
                n3_contract=n3_contract,
                replicate_id=replicate_id,
                expected_experience=expected_experience,
            )
            if loaded_action["branch"] != mode or loaded_action["active_frame_count"] != EXPECTED_ACTIVE_FRAME_COUNT:
                raise RuntimeError("N3 action artifact branch/active-frame identity drifted")
            stats = n3_open_loop_nrmse(
                loaded_action["actions"],
                loaded_action["teacher_action"],
                branch_identity={"mode": mode, "checkpoint": loaded_action["checkpoint"], "config": loaded_action["config"]},
                n3_identity={"phase_manifest": loaded_action["n3_phase_manifest"], "h5": loaded_action["n3_h5"]},
            )
            if stats.get("n3_phase_manifest_sha256") != expected_phase_sha:
                raise RuntimeError("N3 NRMSE is not bound to the exact phase manifest")
            if stats.get("count") != EXPECTED_ACTIVE_FRAME_COUNT:
                raise RuntimeError("N3 NRMSE must use exactly active rows")
            nrmse_values.append(stats["nrmse_median_12d"])
        ordered_nrmse = sorted(nrmse_values)
        middle = len(ordered_nrmse) // 2
        median_nrmse = ordered_nrmse[middle] if len(ordered_nrmse) % 2 else (ordered_nrmse[middle - 1] + ordered_nrmse[middle]) / 2.0
        nrmse[mode] = {
            "schema": "a2_cb2h_pro_p1_open_loop_nrmse_v1",
            "n3_phase_manifest_sha256": expected_phase_sha,
            "nrmse_median_12d": float(median_nrmse),
            "replicate_values": nrmse_values,
        }
    return _adjudicate_p1(
        sequential_nrmse=nrmse["sequential"],
        packed_nrmse=nrmse["packed"],
        sequential_formal=formal_records["sequential"],
        packed_formal=formal_records["packed"],
    )


def artifact_ref(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=True)
    return ArtifactRef(path, sha256_file(path)).as_dict()


def build_branch_manifest(
    spec: P1BranchSpec,
    *,
    runtime: Mapping[str, Any],
    teacher: Mapping[str, Any],
    target_config: Path = TARGET_CONFIG,
    final_checkpoint: Path | None = None,
    final_config: Path | None = None,
    completed_iterations: int | None = None,
    training_performed: bool = True,
    backward_call_count: int | None = None,
    optimizer_step_count: int | None = None,
    scheduler_step_count: int | None = None,
    scheduler_step_count_before: int | None = None,
    scheduler_step_count_after: int | None = None,
    scheduler_last_epoch_before: int | None = None,
    scheduler_last_epoch_after: int | None = None,
    peak_vram_mib: float | None = None,
    metrics: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    runtime_evidence: Mapping[str, Any] | None = None,
    effective_training_contract: Mapping[str, Any] | None = None,
    lifecycle: Mapping[str, Any] | None = None,
    total_completed_iterations: int | None = None,
) -> dict[str, Any]:
    """Build a sealed branch provenance object; caller decides when to write it."""
    target_config = target_config.expanduser().resolve(strict=True)
    if peak_vram_mib is not None:
        validate_peak_vram_mib(peak_vram_mib)
    final_checkpoint = spec.final_checkpoint if final_checkpoint is None else final_checkpoint.expanduser().resolve()
    final_config = (
        final_checkpoint.with_name("config.yaml")
        if final_config is None
        else final_config.expanduser().resolve()
    )
    if completed_iterations is not None and total_completed_iterations is not None:
        if completed_iterations != total_completed_iterations:
            raise ValueError("completed_iterations and total_completed_iterations disagree")
    total_completed_iterations = (
        spec.requested_iterations
        if completed_iterations is None and total_completed_iterations is None
        else completed_iterations
        if total_completed_iterations is None
        else total_completed_iterations
    )
    if total_completed_iterations is None:
        raise AssertionError("total completed iteration count was not resolved")
    total_completed_iterations = _strict_nonnegative_int(
        total_completed_iterations,
        "total_completed_iterations",
    )
    _validate_trusted_stage_iteration_grid(
        source_global_step=spec.start_global_step,
        target_global_step=spec.target_global_step,
        requested_iterations=spec.requested_iterations,
        completed_iterations=total_completed_iterations,
        total_completed_iterations=total_completed_iterations,
        run_iterations=spec.run_iterations,
        additional_iterations=spec.run_iterations,
        name="P1 branch manifest",
    )
    if training_performed and not final_checkpoint.is_file():
        raise FileNotFoundError(
            f"training provenance cannot be sealed without the final checkpoint: {final_checkpoint}"
        )
    if training_performed and not final_config.is_file():
        raise FileNotFoundError(
            f"training provenance cannot be sealed without the effective config: {final_config}"
        )
    validated_runtime_evidence = None
    if training_performed:
        if runtime_evidence is None:
            raise RuntimeError("successful P1 branch sealing requires runtime telemetry evidence")
        validated_runtime_evidence = validate_runtime_evidence(
            runtime_evidence,
            start_global_step=spec.start_global_step,
            target_global_step=spec.target_global_step,
            expected_iterations=spec.run_iterations,
        )
        runtime_completed_iterations = validated_runtime_evidence["metrics"]["completed_iterations"]
        runtime_additional_iterations = validated_runtime_evidence["metrics"]["additional_iterations"]
        if runtime_completed_iterations != spec.run_iterations:
            raise RuntimeError(
                "branch runtime completed_iterations must describe this invocation's additional iterations"
            )
        if runtime_additional_iterations != spec.run_iterations:
            raise RuntimeError(
                "branch runtime additional_iterations must describe this invocation's run_iterations"
            )
        if backward_call_count != validated_runtime_evidence["metrics"]["backward_call_count"]:
            raise RuntimeError("branch manifest backward count disagrees with runtime evidence")
        if optimizer_step_count != validated_runtime_evidence["metrics"]["optimizer_step_count"]:
            raise RuntimeError("branch manifest optimizer count disagrees with runtime evidence")
        if scheduler_step_count != validated_runtime_evidence["metrics"]["scheduler_step_count"]:
            raise RuntimeError("branch manifest scheduler count disagrees with runtime evidence")
        for field, value in (
            ("scheduler_step_count_before", scheduler_step_count_before),
            ("scheduler_step_count_after", scheduler_step_count_after),
            ("scheduler_last_epoch_before", scheduler_last_epoch_before),
            ("scheduler_last_epoch_after", scheduler_last_epoch_after),
        ):
            if value != validated_runtime_evidence["metrics"][field]:
                raise RuntimeError(f"branch manifest {field} disagrees with runtime evidence")
        if peak_vram_mib is not None and float(peak_vram_mib) != validated_runtime_evidence["metrics"]["peak_vram_mib"]:
            raise RuntimeError("branch manifest peak VRAM disagrees with runtime evidence")
        peak_vram_mib = validated_runtime_evidence["metrics"]["peak_vram_mib"]
    result = {
        "requested_iterations": spec.requested_iterations,
        "completed_iterations": total_completed_iterations,
        "total_completed_iterations": total_completed_iterations,
        "additional_iterations": spec.run_iterations,
        "run_iterations": spec.run_iterations,
        "start_global_step": spec.start_global_step,
        "target_global_step": spec.target_global_step,
        "training_performed": bool(training_performed),
        "backward_call_count": backward_call_count,
        "optimizer_step_count": optimizer_step_count,
        "scheduler_step_count": scheduler_step_count,
        "scheduler_step_count_before": scheduler_step_count_before,
        "scheduler_step_count_after": scheduler_step_count_after,
        "scheduler_last_epoch_before": scheduler_last_epoch_before,
        "scheduler_last_epoch_after": scheduler_last_epoch_after,
        "peak_vram_mib": peak_vram_mib,
    }
    if total_completed_iterations != spec.requested_iterations:
        raise RuntimeError("branch manifest total completed iterations do not match the requested stage")
    if training_performed and (
        backward_call_count is None
        or optimizer_step_count is None
        or scheduler_step_count is None
        or scheduler_step_count_before is None
        or scheduler_step_count_after is None
        or scheduler_last_epoch_before is None
        or scheduler_last_epoch_after is None
    ):
        raise RuntimeError("training provenance must report backward, optimizer, and scheduler counts")
    if training_performed:
        scheduler_before = _strict_int(scheduler_step_count_before, "branch scheduler_step_count_before")
        scheduler_after = _strict_int(scheduler_step_count_after, "branch scheduler_step_count_after")
        epoch_before = _strict_int(scheduler_last_epoch_before, "branch scheduler_last_epoch_before")
        epoch_after = _strict_int(scheduler_last_epoch_after, "branch scheduler_last_epoch_after")
        if scheduler_before != spec.start_global_step + 1 or epoch_before != spec.start_global_step:
            raise RuntimeError("branch scheduler before counters are not source-bound")
        if scheduler_after != spec.target_global_step + 1 or epoch_after != spec.target_global_step:
            raise RuntimeError("branch scheduler after counters are not target-bound")
        if scheduler_before != epoch_before + 1 or scheduler_after != epoch_after + 1:
            raise RuntimeError("branch scheduler _step_count must equal last_epoch + 1")
    expected_contract = {
        "num_envs": EXPECTED_NUM_ENVS,
        "num_total_batches": spec.target_global_step,
        "save_frequency": spec.target_global_step,
        "num_steps_per_env": 8,
        "num_mini_batches": 4,
        "actor_learning_rate": 1.0e-4,
        "use_a2_base": True,
        "enforce_teacher_rollout": True,
        "ratio_teacher_rollout": 1.0,
        "d435i_forward_mode": spec.mode,
    }
    if effective_training_contract is None:
        effective_training_contract = expected_contract
    if dict(effective_training_contract) != expected_contract:
        raise RuntimeError("P1 branch effective training contract does not match the sealed stage")
    lifecycle = dict(lifecycle or {
        "natural_kit_lifecycle_pass": False,
        "lifecycle_status": "UNRESOLVED",
        "controlled_post_training_exit": True,
    })
    if lifecycle.get("natural_kit_lifecycle_pass") is not False:
        raise RuntimeError("P1 branch manifest cannot claim natural Kit lifecycle PASS")
    if lifecycle.get("lifecycle_status") != "UNRESOLVED":
        raise RuntimeError("P1 branch manifest lifecycle_status must remain UNRESOLVED")
    if lifecycle.get("controlled_post_training_exit") is not True:
        raise RuntimeError("P1 branch manifest requires controlled_post_training_exit=true")
    manifest = {
        "schema": P1_BRANCH_SCHEMA,
        "operation": "p1_training",
        "branch": spec.mode,
        "root": str(spec.root),
        "source": {
            "checkpoint": ArtifactRef(spec.checkpoint, spec.checkpoint_sha256).as_dict(),
            "config": ArtifactRef(spec.checkpoint_config, spec.checkpoint_config_sha256).as_dict(),
            "global_step": spec.start_global_step,
            "checkpoint_load_mode": "full",
        },
        "target_config": artifact_ref(target_config),
        "runtime": dict(runtime),
        "teacher": dict(teacher),
        "lifecycle": lifecycle,
        "launch_contract": {
            "num_envs": EXPECTED_NUM_ENVS,
            "num_steps_per_env": 8,
            "num_mini_batches": 4,
            "actor_learning_rate": 1.0e-4,
            "ratio_teacher_rollout": 1.0,
            "enforce_teacher_rollout": True,
            "checkpoint_load_mode": "full",
            "auto_load_latest": False,
            "forward_mode": spec.mode,
            "world_size": 1,
            "physical_gpu_index": EXPECTED_GPU_INDEX,
            "logical_device": EXPECTED_LOGICAL_DEVICE,
            "common_init_contract_sha256": P1_COMMON_INIT_CONTRACT_SHA256,
        },
        "result": result,
        "final_checkpoint": {
            "path": str(final_checkpoint),
            "global_step": spec.target_global_step,
            "sha256": sha256_file(final_checkpoint) if final_checkpoint.is_file() else None,
        },
        "final_config": artifact_ref(final_config) if final_config.is_file() else None,
        "effective_training_contract": dict(effective_training_contract),
        "runtime_evidence": dict(validated_runtime_evidence or {}),
        "metrics": dict(metrics or {}),
        "artifacts": {key: dict(value) for key, value in (artifacts or {}).items()},
    }
    return manifest


def execute_n3_inference(args: argparse.Namespace) -> int:
    """Execute one sealed recurrent N3 pass for the requested branch mode.

    N4 owns the checkpoint/model construction and recurrent rollout lifecycle;
    P1 supplies only the exact mode, artifact identities, active-row contract,
    and atomic action-manifest seal.  A non-CUDA device is rejected rather than
    silently downgraded.
    """
    import numpy as np

    if args.mode not in P1_FORWARD_MODES:
        raise ValueError("--n3-infer requires --mode sequential or packed")
    if args.device != EXPECTED_LOGICAL_DEVICE:
        raise P1Blocked("P1 N3 inference requires logical cuda:0; CPU fallback is forbidden")
    if args.recurrent_reset_per_replicate is not True:
        raise ValueError("--n3-infer requires --recurrent-reset-per-replicate")
    required = (
        args.checkpoint_sha256,
        args.config_sha256,
        args.n3_phase_manifest,
        args.n3_phase_manifest_sha256,
        args.n3_h5,
        args.n3_h5_sha256,
        args.n3_trajectory_manifest,
        args.n3_trajectory_manifest_sha256,
        args.replicate_id,
        args.output,
    )
    if any(value is None for value in required):
        raise ValueError("--n3-infer requires checkpoint/config/N3 artifact hashes, replicate, and output")
    checkpoint = args.checkpoint.expanduser().resolve(strict=True)
    config = args.config.expanduser().resolve(strict=True)
    checkpoint_sha = _assert_hash(checkpoint, args.checkpoint_sha256, "N3 inference checkpoint")
    config_sha = _assert_hash(config, args.config_sha256, "N3 inference config")
    if _step_from_checkpoint(checkpoint) not in (INITIAL_TARGET_GLOBAL_STEP, EXTENDED_TARGET_GLOBAL_STEP):
        raise RuntimeError("N3 inference checkpoint must be a sealed P1 final checkpoint")
    if args.output.exists():
        raise RuntimeError(f"P1 N3 inference output root must be fresh and absent: {args.output}")
    if args.n3_phase_manifest.expanduser().resolve() != N3_PHASE_MANIFEST.resolve():
        raise RuntimeError("N3 inference phase manifest path is not the exact pinned artifact")
    _assert_hash(args.n3_phase_manifest, args.n3_phase_manifest_sha256, "N3 inference phase manifest")

    from gr00t.rl.scripts import run_a2_cb2h_pro_n4 as n4

    n4.validate_gpu_binding(device=args.device)
    n3_inputs = n4.validate_n3_inputs(args.n3_root)
    n3_contract = validate_n3_contract(args.n3_root)
    matching = [replicate for replicate in n3_inputs.replicates if replicate.replicate_id == args.replicate_id]
    if len(matching) != 1:
        raise RuntimeError(f"N3 inference replicate identity is not unique: {args.replicate_id!r}")
    replicate = matching[0]
    if replicate.h5_path.resolve() != args.n3_h5.expanduser().resolve():
        raise RuntimeError("N3 inference HDF5 path is not the exact validated replicate artifact")
    if replicate.trajectory_manifest_path.resolve() != args.n3_trajectory_manifest.expanduser().resolve():
        raise RuntimeError("N3 inference trajectory manifest path is not the exact validated replicate artifact")
    _assert_hash(args.n3_h5, args.n3_h5_sha256, "N3 inference HDF5")
    _assert_hash(args.n3_trajectory_manifest, args.n3_trajectory_manifest_sha256, "N3 inference trajectory manifest")
    contract_replicate = next(
        item for item in n3_contract["replicates"] if item.get("replicate_id") == args.replicate_id
    )
    expected_experience = n3_contract.get("experience_identity")
    if not isinstance(expected_experience, Mapping):
        raise RuntimeError("N3 inference lacks one exact experience identity")
    trajectory = _load_json(args.n3_trajectory_manifest)
    if trajectory.get("experience") != dict(expected_experience):
        raise RuntimeError("N3 inference trajectory experience identity drifted")
    if contract_replicate.get("active_frame_count") != EXPECTED_ACTIVE_FRAME_COUNT:
        raise RuntimeError("N3 inference active-frame count drifted")

    model = n4._model_from_exact_checkpoint(checkpoint, config, args.device)
    if not hasattr(model, "d435i_forward_mode"):
        raise RuntimeError("N3 model does not expose d435i_forward_mode")
    model.d435i_forward_mode = args.mode
    if model.d435i_forward_mode != args.mode:
        raise RuntimeError("N3 model forward mode binding drifted")
    result = n4.evaluate_variant(model, replicate, "FULL", args.device)
    actions = np.asarray(result.actions)
    if actions.shape != (replicate.row_count, EXPECTED_ACTION_DIM):
        raise RuntimeError(f"N3 inference action shape drifted: {actions.shape}")
    if not np.isfinite(actions).all():
        raise RuntimeError("N3 inference produced non-finite actions")
    with n4._open_h5(replicate.h5_path) as handle:
        active_mask = np.asarray(handle["active_mask"][:])
        teacher_action = np.asarray(handle["teacher_action"][:])
        identity_arrays = {
            "active_mask": active_mask.astype(bool),
            "env_id": np.asarray(handle["env_id"][:]),
            "frame_id": np.asarray(handle["frame_id"][:]),
            "case_id": [bytes(value).decode("ascii") for value in handle["case_id"][:]],
            "pre_action_stage": np.asarray(handle["pre_action_stage"][:]),
        }
    if active_mask.dtype != np.dtype(bool) or int(active_mask.sum()) != EXPECTED_ACTIVE_FRAME_COUNT:
        raise RuntimeError("N3 inference active mask/count is not exact")
    if teacher_action.shape != actions.shape or not np.isfinite(teacher_action).all():
        raise RuntimeError("N3 teacher action identity/finite contract drifted")
    active_identity = {
        "env_id": identity_arrays["env_id"][active_mask].astype(int).tolist(),
        "frame_id": identity_arrays["frame_id"][active_mask].astype(int).tolist(),
        "case_id": [value for value, active in zip(identity_arrays["case_id"], active_mask.tolist()) if active],
        "pre_action_stage": identity_arrays["pre_action_stage"][active_mask].astype(int).tolist(),
    }
    full_identity = {
        "active_mask": active_mask.tolist(),
        "env_id": identity_arrays["env_id"].astype(int).tolist(),
        "frame_id": identity_arrays["frame_id"].astype(int).tolist(),
        "case_id": list(identity_arrays["case_id"]),
        "pre_action_stage": identity_arrays["pre_action_stage"].astype(int).tolist(),
    }
    active_mask_hash = sha256_bytes(canonical_json(full_identity).encode("utf-8"))
    active_identity_content_hash = sha256_bytes(canonical_json(active_identity).encode("utf-8"))
    if active_mask_hash != contract_replicate.get("active_mask_sha256"):
        raise RuntimeError("N3 inference active identity hash drifted from validated HDF5")
    active_actions = actions[active_mask].astype(np.float32).tolist()
    active_teacher = teacher_action[active_mask].astype(np.float32).tolist()
    manifest = {
        "schema": P1_N3_ACTION_SCHEMA,
        "operation": "p1_n3_inference",
        "branch": args.mode,
        "forward_mode": args.mode,
        "replicate_id": args.replicate_id,
        "recurrent_reset_per_replicate": True,
        "checkpoint": {"path": str(checkpoint), "sha256": checkpoint_sha},
        "config": {"path": str(config), "sha256": config_sha},
        "n3_phase_manifest": artifact_ref(args.n3_phase_manifest),
        "n3_h5": artifact_ref(args.n3_h5),
        "n3_trajectory_manifest": artifact_ref(args.n3_trajectory_manifest),
        "experience": dict(expected_experience),
        "active_frame_count": EXPECTED_ACTIVE_FRAME_COUNT,
        "active_mask_sha256": active_mask_hash,
        "active_identity_sha256": active_identity_content_hash,
        "active_identity": active_identity,
        "actions": active_actions,
        "teacher_action": active_teacher,
        "prediction_contract": {
            "shape": [EXPECTED_ACTIVE_FRAME_COUNT, EXPECTED_ACTION_DIM],
            "dtype": "float32",
            "finite": True,
            "active_rows_only": True,
        },
    }
    output_root = args.output.expanduser().resolve()
    seal_json(output_root / P1_N3_ACTION_MANIFEST_FILENAME, manifest)
    print(
        f"[A2_P1_N3_INFERENCE_PASS] mode={args.mode} replicate={args.replicate_id} "
        f"active_frames={EXPECTED_ACTIVE_FRAME_COUNT}",
        flush=True,
    )
    return 0


def seal_json(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    """Write one new manifest atomically; never overwrite prior evidence."""
    path = path.expanduser().resolve()
    if path.exists():
        raise RuntimeError(f"sealed P1 artifact already exists; refusing overwrite: {path}")
    if path.parent.exists() and not path.parent.is_dir():
        raise RuntimeError(f"P1 manifest parent is not a directory: {path.parent}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(value)
    payload["manifest_content_sha256"] = sha256_bytes(canonical_json(payload).encode("utf-8"))
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.writing")
    temporary.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return payload


def build_adjudication_manifest(
    *,
    plan: P1Plan,
    branch_manifests: Mapping[str, Mapping[str, Any]],
    n3_phase_manifest: Path,
    formal_replicates: Mapping[str, Sequence[Mapping[str, Any]]],
    sequential_nrmse: Mapping[str, Any],
    packed_nrmse: Mapping[str, Any],
    n2_phase_manifest: Path | None = None,
) -> dict[str, Any]:
    raise P1Blocked(
        "raw adjudication records are forbidden; use adjudicate_p1_from_paths with evaluator-v2 paths and expected SHAs"
    )

    # Kept below for API compatibility with older callers; production code
    # cannot reach it because the path-bound loader above is mandatory.
    if set(branch_manifests) != set(P1_BRANCHES):
        raise ValueError("adjudication requires both sequential and packed branch manifests")
    n3_phase_manifest = n3_phase_manifest.expanduser().resolve(strict=True)
    if sha256_file(n3_phase_manifest) != N3_PHASE_MANIFEST_SHA256:
        raise RuntimeError("N3 phase manifest SHA256 drifted")
    formal_seq = formal_replicates.get("sequential")
    formal_packed = formal_replicates.get("packed")
    if formal_seq is None or formal_packed is None:
        raise ValueError("adjudication requires formal records for both branches")
    decision = adjudicate_p1(
        sequential_nrmse=sequential_nrmse,
        packed_nrmse=packed_nrmse,
        sequential_formal=formal_seq,
        packed_formal=formal_packed,
    )
    n2_input = None
    if n2_phase_manifest is not None:
        n2_input = validate_n2_contract(n2_phase_manifest.parent)
    return {
        "schema": P1_ADJUDICATION_SCHEMA,
        "operation": "p1_adjudication",
        "plan": plan.as_dict(),
        "branches": {key: dict(value) for key, value in branch_manifests.items()},
        "n3_input": artifact_ref(n3_phase_manifest),
        "n2_input": n2_input,
        "formal_replicates": {
            key: {"count": len(value)} for key, value in formal_replicates.items()
        },
        "decision": decision,
    }


def _stable_proof_artifact(
    path: Path,
    *,
    name: str,
    root: Path | None = None,
    expected_path: Path | None = None,
) -> dict[str, str]:
    """Return a path/hash only when two immediate reads observe one artifact."""
    resolved = path.expanduser().resolve(strict=True)
    if root is not None and not resolved.is_relative_to(root.expanduser().resolve()):
        raise RuntimeError(f"{name} escapes sealed branch root: {resolved}")
    if expected_path is not None and resolved != expected_path.expanduser().resolve():
        raise RuntimeError(f"{name} is not the exact expected artifact: {resolved}")

    def snapshot() -> tuple[tuple[int, int, int], str]:
        stat = resolved.stat()
        identity = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
        return identity, sha256_file(resolved)

    first_identity, first_sha = snapshot()
    second_identity, second_sha = snapshot()
    if first_identity != second_identity or first_sha != second_sha:
        raise RuntimeError(f"{name} changed while its pre-teardown proof was being sealed")
    return {"path": str(resolved), "sha256": second_sha}


def _scheduler_native_snapshot(
    scheduler: Any,
    *,
    name: str,
    expected_last_epoch: int | None = None,
) -> dict[str, Any]:
    """Read native scheduler counters without replacing its bound ``step`` method."""
    if expected_last_epoch is not None:
        expected_last_epoch = _strict_int(expected_last_epoch, f"{name} expected_last_epoch")
    native_step = getattr(scheduler, "step", None)
    native_step_func = getattr(native_step, "__func__", None)
    native_step_owner = getattr(native_step, "__self__", None)
    if not callable(native_step) or native_step_func is None or native_step_owner is not scheduler:
        raise RuntimeError(f"{name} must expose its native bound lr_scheduler.step method")
    state_dict_fn = getattr(scheduler, "state_dict", None)
    if not callable(state_dict_fn):
        raise RuntimeError(f"{name} must expose a serializable state_dict")
    state_dict = state_dict_fn()
    if not isinstance(state_dict, Mapping):
        raise TypeError(f"{name}.state_dict() must return a mapping")

    def strict_counter(field: str) -> int:
        value = getattr(scheduler, field, None)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name}.{field} must be an integer")
        state_value = state_dict.get(field)
        if isinstance(state_value, bool) or not isinstance(state_value, int) or state_value != value:
            raise RuntimeError(f"{name}.{field} disagrees with its native state_dict")
        return value

    step_count = strict_counter("_step_count")
    last_epoch = strict_counter("last_epoch")
    if step_count != last_epoch + 1:
        raise RuntimeError(f"{name} native _step_count must equal last_epoch + 1")
    if expected_last_epoch is not None and last_epoch != expected_last_epoch:
        raise RuntimeError(
            f"{name} native last_epoch must equal expected absolute step "
            f"{expected_last_epoch}; got {last_epoch}"
        )
    return {
        "step_count": step_count,
        "last_epoch": last_epoch,
        "native_step_func": native_step_func,
        "native_step_owner": native_step_owner,
    }


def _seal_pre_teardown_completion_proof(
    *,
    branch_root: Path,
    branch: str,
    source: Mapping[str, Any],
    runtime: Mapping[str, Any],
    environment: Mapping[str, str],
    lifecycle: Mapping[str, Any],
    start_global_step: int,
    target_global_step: int,
    run_iterations: int,
    final_checkpoint: Path,
    final_config: Path,
    iteration_time_s: float,
    controlled_post_training_exit: bool,
) -> dict[str, Any]:
    """Seal the only success proof before Kit teardown can run.

    This function deliberately has no fallback path.  A missing artifact,
    lifecycle mismatch, unstable hash, or non-production exit mode is an
    error, so a child cannot promote a partial run to exit ``0``.
    """
    if branch not in P1_FORWARD_MODES:
        raise ValueError(f"unknown P1 branch mode: {branch!r}")
    if controlled_post_training_exit is not True:
        raise RuntimeError("P1 completion proof requires controlled_post_training_exit=true")
    branch_root = branch_root.expanduser().resolve(strict=True)
    if not isinstance(source, Mapping) or not isinstance(runtime, Mapping):
        raise TypeError("P1 pre-teardown proof source/runtime must be mappings")
    if runtime.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError("P1 pre-teardown proof runtime commit is not the exact pinned runtime")
    if source.get("checkpoint_load_mode") != "full":
        raise RuntimeError("P1 pre-teardown proof source must use checkpoint_load_mode=full")
    source_checkpoint = _stable_proof_artifact(
        Path(source["path"]),
        name="pre-teardown source checkpoint",
    )
    source_config = _stable_proof_artifact(
        Path(source["config_path"]),
        name="pre-teardown source config",
    )
    if source_checkpoint["sha256"] != source.get("sha256"):
        raise RuntimeError("P1 pre-teardown source checkpoint hash changed")
    if source_config["sha256"] != source.get("config_sha256"):
        raise RuntimeError("P1 pre-teardown source config hash changed")
    start_global_step = _strict_int(start_global_step, "pre-teardown start_global_step")
    target_global_step = _strict_int(target_global_step, "pre-teardown target_global_step")
    run_iterations = _strict_int(run_iterations, "pre-teardown run_iterations")
    source_global_step = _strict_int(source.get("global_step"), "pre-teardown source.global_step")
    if source_global_step != start_global_step:
        raise RuntimeError("P1 pre-teardown source global_step drifted")
    if target_global_step - start_global_step != run_iterations or run_iterations <= 0:
        raise RuntimeError("P1 pre-teardown target arithmetic is not exact")
    if not isinstance(iteration_time_s, (int, float)) or isinstance(iteration_time_s, bool):
        raise TypeError("P1 pre-teardown iteration_time_s must be numeric")
    if not math.isfinite(float(iteration_time_s)) or float(iteration_time_s) <= 0.0:
        raise ValueError("P1 pre-teardown iteration_time_s must be finite and positive")

    expected_steps = list(range(start_global_step + 1, target_global_step + 1))
    expected_updates = run_iterations * P1_EFFECTIVE_NUM_MINI_BATCHES
    if lifecycle.get("num_mini_batches") != P1_EFFECTIVE_NUM_MINI_BATCHES:
        raise RuntimeError("P1 pre-teardown effective num_mini_batches must remain exactly 4")
    if lifecycle.get("num_ppo_epochs") != P1_EFFECTIVE_NUM_PPO_EPOCHS:
        raise RuntimeError("P1 pre-teardown effective num_ppo_epochs must remain exactly 1")
    if lifecycle.get("num_micro_batches") != P1_EFFECTIVE_NUM_MICRO_BATCHES:
        raise RuntimeError("P1 pre-teardown gradient accumulation must remain one micro-batch")
    if lifecycle.get("configured_num_total_batches") != target_global_step:
        raise RuntimeError("P1 pre-teardown configured absolute target drifted")
    if lifecycle.get("expected_additional_iterations") != run_iterations:
        raise RuntimeError("P1 pre-teardown expected iteration count drifted")
    if lifecycle.get("outer_range_call_count") != 1:
        raise RuntimeError("P1 pre-teardown outer absolute-target range proof is missing")
    if lifecycle.get("callback_train_begin_seen") is not True:
        raise RuntimeError("P1 pre-teardown callback train-begin proof is missing")
    if lifecycle.get("callback_step_end_count") != run_iterations:
        raise RuntimeError("P1 pre-teardown callback step count drifted")
    if lifecycle.get("callback_max_steps") != target_global_step:
        raise RuntimeError("P1 pre-teardown callback max_steps drifted")
    if lifecycle.get("observed_global_steps") != expected_steps:
        raise RuntimeError("P1 pre-teardown callback global-step progression drifted")
    for field in ("backward_call_count", "optimizer_step_count"):
        count = lifecycle.get(field)
        if isinstance(count, bool) or not isinstance(count, int) or count != expected_updates:
            raise RuntimeError(
                f"P1 pre-teardown lifecycle {field} must equal expected update count {expected_updates}"
            )
    scheduler_count = lifecycle.get("scheduler_step_count")
    if isinstance(scheduler_count, bool) or not isinstance(scheduler_count, int) or scheduler_count != run_iterations:
        raise RuntimeError(
            f"P1 pre-teardown lifecycle scheduler_step_count must equal {run_iterations}"
        )
    scheduler_before = lifecycle.get("scheduler_step_count_before")
    scheduler_after = lifecycle.get("scheduler_step_count_after")
    epoch_before = lifecycle.get("scheduler_last_epoch_before")
    epoch_after = lifecycle.get("scheduler_last_epoch_after")
    for field, value in (
        ("scheduler_step_count_before", scheduler_before),
        ("scheduler_step_count_after", scheduler_after),
        ("scheduler_last_epoch_before", epoch_before),
        ("scheduler_last_epoch_after", epoch_after),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"P1 pre-teardown {field} must be an integer")
    if scheduler_after - scheduler_before != run_iterations or epoch_after - epoch_before != run_iterations:
        raise RuntimeError("P1 pre-teardown scheduler native counter deltas are inconsistent")
    if scheduler_after - scheduler_before != epoch_after - epoch_before:
        raise RuntimeError("P1 pre-teardown scheduler _step_count/last_epoch deltas disagree")
    if scheduler_before != start_global_step + 1 or epoch_before != start_global_step:
        raise RuntimeError("P1 pre-teardown scheduler before counters are not bound to the source step")
    if scheduler_after != target_global_step + 1 or epoch_after != target_global_step:
        raise RuntimeError("P1 pre-teardown scheduler after counters are not bound to the target step")

    expected_checkpoint = branch_root / f"model_step_{target_global_step:06d}.pt"
    expected_config = branch_root / "config.yaml"
    final_checkpoint_ref = _stable_proof_artifact(
        final_checkpoint,
        name="pre-teardown final checkpoint",
        root=branch_root,
        expected_path=expected_checkpoint,
    )
    final_config_ref = _stable_proof_artifact(
        final_config,
        name="pre-teardown final config",
        root=branch_root,
        expected_path=expected_config,
    )
    if _step_from_checkpoint(Path(final_checkpoint_ref["path"])) != target_global_step:
        raise RuntimeError("P1 pre-teardown final checkpoint filename/global_step mismatch")
    gpu_identity = {
        "physical_gpu_index": EXPECTED_GPU_INDEX,
        "logical_gpu_index": int(EXPECTED_LOGICAL_GPU_INDEX),
        "logical_device": EXPECTED_LOGICAL_DEVICE,
        "uuid": EXPECTED_GPU_UUID,
        "cuda_visible_devices": EXPECTED_GPU_INDEX,
        "world_size": 1,
        "binding_mode": environment.get("A2_GPU_BINDING_MODE"),
        "cuda_device_order": environment.get("CUDA_DEVICE_ORDER"),
    }
    if environment.get("CUDA_VISIBLE_DEVICES") != EXPECTED_GPU_INDEX or environment.get("A2_EXPECTED_WORLD_SIZE") != "1":
        raise RuntimeError("P1 pre-teardown GPU process identity drifted")
    if environment.get("A2_EXPECTED_HOST_GPU_INDEX") != EXPECTED_GPU_INDEX:
        raise RuntimeError("P1 pre-teardown physical GPU binding drifted")
    if environment.get("A2_EXPECTED_GPU_UUID") != EXPECTED_GPU_UUID:
        raise RuntimeError("P1 pre-teardown GPU UUID binding drifted")
    if environment.get("A2_EXPECTED_LOGICAL_GPU_INDEX") != EXPECTED_LOGICAL_GPU_INDEX:
        raise RuntimeError("P1 pre-teardown logical GPU binding drifted")
    if environment.get("A2_GPU_BINDING_MODE") != EXPECTED_GPU_BINDING_MODE:
        raise RuntimeError("P1 pre-teardown GPU binding mode drifted")
    if environment.get("CUDA_DEVICE_ORDER") != EXPECTED_CUDA_DEVICE_ORDER:
        raise RuntimeError("P1 pre-teardown CUDA device order drifted")

    lifecycle_counts = {
        "configured_num_total_batches": target_global_step,
        "expected_additional_iterations": run_iterations,
        "completed_iterations": run_iterations,
        "num_mini_batches": P1_EFFECTIVE_NUM_MINI_BATCHES,
        "num_ppo_epochs": P1_EFFECTIVE_NUM_PPO_EPOCHS,
        "num_micro_batches": P1_EFFECTIVE_NUM_MICRO_BATCHES,
        "outer_range_call_count": 1,
        "backward_call_count": lifecycle["backward_call_count"],
        "optimizer_step_count": lifecycle["optimizer_step_count"],
        "scheduler_step_count": lifecycle["scheduler_step_count"],
        "scheduler_step_count_before": lifecycle["scheduler_step_count_before"],
        "scheduler_step_count_after": lifecycle["scheduler_step_count_after"],
        "scheduler_last_epoch_before": lifecycle["scheduler_last_epoch_before"],
        "scheduler_last_epoch_after": lifecycle["scheduler_last_epoch_after"],
        "callback_train_begin_seen": True,
        "callback_step_end_count": run_iterations,
        "callback_max_steps": target_global_step,
        "observed_global_steps": expected_steps,
    }
    proof = {
        "schema": P1_PRE_TEARDOWN_PROOF_SCHEMA,
        "operation": "p1_pre_teardown_completion",
        "proof_stage": "PRE_TEARDOWN",
        "branch": branch,
        "root": str(branch_root),
        "source": {
            "checkpoint": source_checkpoint,
            "config": source_config,
            "global_step": start_global_step,
            "checkpoint_load_mode": "full",
        },
        "runtime": dict(runtime),
        "start_global_step": start_global_step,
        "target_global_step": target_global_step,
        "run_iterations": run_iterations,
        "expected_additional_iterations": run_iterations,
        "completed_iterations": run_iterations,
        "iteration_time_s": float(iteration_time_s),
        "lifecycle": lifecycle_counts,
        **lifecycle_counts,
        "final_checkpoint": {
            **final_checkpoint_ref,
            "global_step": target_global_step,
        },
        "final_config": final_config_ref,
        "gpu_identity": gpu_identity,
        "natural_kit_lifecycle_pass": False,
        "lifecycle_status": "UNRESOLVED",
        "controlled_post_training_exit": True,
    }
    return seal_json(branch_root / P1_PRE_TEARDOWN_PROOF_FILENAME, proof)


def _controlled_post_training_exit(proof_path: Path) -> None:
    """Exit only after loading and validating the sealed pre-teardown proof."""
    proof_path = proof_path.expanduser().resolve(strict=True)
    proof = _load_json(proof_path)
    if proof.get("schema") != P1_PRE_TEARDOWN_PROOF_SCHEMA:
        raise RuntimeError("P1 controlled exit requires the pre-teardown proof schema")
    if proof.get("natural_kit_lifecycle_pass") is not False:
        raise RuntimeError("P1 controlled exit cannot claim natural Kit lifecycle PASS")
    if proof.get("lifecycle_status") != "UNRESOLVED":
        raise RuntimeError("P1 controlled exit requires lifecycle_status=UNRESOLVED")
    if proof.get("controlled_post_training_exit") is not True:
        raise RuntimeError("P1 controlled exit marker is missing from the sealed proof")
    content_sha = _require_sha(proof.get("manifest_content_sha256"), "pre-teardown proof content hash")
    without_content = dict(proof)
    without_content.pop("manifest_content_sha256", None)
    if sha256_bytes(canonical_json(without_content).encode("utf-8")) != content_sha:
        raise RuntimeError("P1 controlled exit proof content hash drifted")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def install_absolute_target_train_guard(
    trainer_class: type,
    *,
    start_global_step: int,
    target_global_step: int,
    branch_root: Path | None = None,
    branch: str | None = None,
    source: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
    environment: Mapping[str, str] | None = None,
    controlled_post_training_exit: bool = False,
) -> None:
    """Patch the production train lifecycle without changing its absolute target.

    The pinned trainer uses ``args.num_total_batches`` as the loop bound while
    the restored state already carries an absolute ``global_step``.  P1 keeps
    the configured argument and callback-visible ``state.max_steps`` absolute,
    and scopes a proxy only around the trainer's outer batch ``range`` so the
    loop emits exactly ``target_global_step - start_global_step`` additional
    batches.  This preserves scheduler/callback provenance and exposes any
    lifecycle drift as an error; it never mutates ``args.num_total_batches``.
    """
    if getattr(trainer_class, "_a2_p1_absolute_target_guard", False):
        raise RuntimeError("P1 absolute-target train guard is already installed")
    if target_global_step <= start_global_step:
        raise ValueError("P1 target must be greater than the restored start step")
    proof_context = (branch_root, branch, source, runtime, environment)
    if any(value is not None for value in proof_context) and not all(value is not None for value in proof_context):
        raise ValueError("P1 pre-teardown proof context must be supplied as one complete binding")
    if controlled_post_training_exit and not all(value is not None for value in proof_context):
        raise ValueError("P1 controlled post-training exit requires complete proof context")
    original_train = trainer_class.train
    train_globals = getattr(original_train, "__globals__", None)
    if not isinstance(train_globals, dict):
        raise RuntimeError("P1 cannot locate the production trainer train globals")
    import builtins
    import types

    original_range = train_globals.get("range", builtins.range)
    if original_range is not builtins.range:
        raise RuntimeError("P1 trainer train range binding is already patched")
    import ast
    import inspect
    import textwrap

    try:
        source_lines, source_start = inspect.getsourcelines(original_train)
        source_tree = ast.parse(textwrap.dedent("".join(source_lines)))
    except (OSError, TypeError, IndentationError) as exc:
        raise RuntimeError("P1 cannot prove the production outer range call site") from exc

    def _is_target_outer_range_call(node: ast.Call) -> bool:
        if not isinstance(node.func, ast.Name) or node.func.id != "range":
            return False
        if len(node.args) not in (2, 3):
            return False
        first, stop = node.args[0], node.args[1]
        if not isinstance(first, ast.Constant) or first.value != 1:
            return False
        if not isinstance(stop, ast.BinOp) or not isinstance(stop.op, ast.Add):
            return False
        if not isinstance(stop.left, ast.Attribute) or stop.left.attr != "num_total_batches":
            return False
        if not isinstance(stop.left.value, ast.Name) or stop.left.value.id != "args":
            return False
        return isinstance(stop.right, ast.Constant) and stop.right.value == 1 and (
            len(node.args) == 2
            or (isinstance(node.args[2], ast.Constant) and node.args[2].value == 1)
        )

    outer_range_lines = {
        source_start + node.lineno - 1
        for node in ast.walk(source_tree)
        if isinstance(node, ast.Call) and _is_target_outer_range_call(node)
    }
    if len(outer_range_lines) != 1:
        raise RuntimeError(
            "P1 requires exactly one statically proven outer range(1, args.num_total_batches + 1) call site"
        )
    outer_range_line = next(iter(outer_range_lines))

    def guarded_train(self, *args, **kwargs):
        loaded = getattr(getattr(self, "state", None), "global_step", None)
        if isinstance(loaded, bool) or not isinstance(loaded, int):
            raise RuntimeError(f"P1 trainer state.global_step must be int; got {loaded!r}")
        if loaded != start_global_step:
            raise RuntimeError(
                f"P1 trainer restored the wrong global_step: expected {start_global_step}, got {loaded}"
            )
        training_args = getattr(self, "args", None)
        configured_target = getattr(training_args, "num_total_batches", None)
        if configured_target != target_global_step:
            raise RuntimeError(
                "P1 Hydra num_total_batches must be the absolute target: "
                f"expected {target_global_step}, got {configured_target!r}"
            )
        effective_num_mini_batches = getattr(training_args, "num_mini_batches", None)
        effective_num_ppo_epochs = getattr(training_args, "num_ppo_epochs", None)
        effective_num_micro_batches = getattr(training_args, "num_micro_batches", None)
        if effective_num_mini_batches != P1_EFFECTIVE_NUM_MINI_BATCHES:
            raise RuntimeError("P1 production trainer requires effective num_mini_batches=4")
        if effective_num_ppo_epochs != P1_EFFECTIVE_NUM_PPO_EPOCHS:
            raise RuntimeError("P1 production trainer requires effective num_ppo_epochs=1")
        if effective_num_micro_batches != P1_EFFECTIVE_NUM_MICRO_BATCHES:
            raise RuntimeError("P1 production trainer requires exactly one effective micro-batch")
        expected_additional = target_global_step - loaded
        if expected_additional <= 0:
            raise RuntimeError("P1 absolute-target guard computed no remaining iterations")
        lifecycle_started_at = time.time()
        lifecycle = {
            "configured_num_total_batches": configured_target,
            "expected_additional_iterations": expected_additional,
            "num_mini_batches": effective_num_mini_batches,
            "num_ppo_epochs": effective_num_ppo_epochs,
            "num_micro_batches": effective_num_micro_batches,
            "callback_train_begin_seen": False,
            "callback_step_end_count": 0,
            "callback_max_steps": None,
            "outer_range_call_count": 0,
            "backward_call_count": 0,
            "optimizer_step_count": 0,
            "scheduler_step_count": 0,
            "observed_global_steps": [],
        }
        setattr(self, "_a2_p1_lifecycle_probe", lifecycle)

        accelerator = getattr(self, "accelerator", None)
        optimizer = getattr(self, "optimizer", None)
        scheduler = getattr(self, "lr_scheduler", None)
        original_backward = getattr(accelerator, "backward", None)
        original_optimizer_step = getattr(optimizer, "step", None)
        if not callable(original_backward) or not callable(original_optimizer_step):
            raise RuntimeError("P1 production trainer must expose accelerator.backward and optimizer.step")
        scheduler_before = _scheduler_native_snapshot(
            scheduler,
            name="P1 production lr_scheduler",
            expected_last_epoch=start_global_step,
        )

        callback_handler = getattr(self, "callback_handler", None)
        original_on_train_begin = None
        original_on_step_end = None
        if callback_handler is None:
            raise RuntimeError("P1 production trainer callback_handler is required for lifecycle proof")
        if callback_handler is not None:
            original_on_train_begin = callback_handler.on_train_begin
            original_on_step_end = callback_handler.on_step_end

            def probe_on_train_begin(handler_self, callback_args, callback_state, callback_control, **event_kwargs):
                if callback_args is not training_args:
                    raise RuntimeError("P1 callback received a different TrainingArguments object")
                if callback_args.num_total_batches != target_global_step:
                    raise RuntimeError("P1 callback saw a non-absolute num_total_batches")
                if callback_state.max_steps != target_global_step:
                    raise RuntimeError("P1 callback saw a non-absolute state.max_steps")
                lifecycle["callback_train_begin_seen"] = True
                lifecycle["callback_max_steps"] = callback_state.max_steps
                return original_on_train_begin(callback_args, callback_state, callback_control, **event_kwargs)

            def probe_on_step_end(handler_self, callback_args, callback_state, callback_control, **event_kwargs):
                if callback_args.num_total_batches != target_global_step or callback_state.max_steps != target_global_step:
                    raise RuntimeError("P1 callback step lifecycle lost the absolute target")
                lifecycle["callback_step_end_count"] += 1
                global_step = getattr(callback_state, "global_step", None)
                if isinstance(global_step, bool) or not isinstance(global_step, int):
                    raise RuntimeError("P1 callback state.global_step must be an integer")
                lifecycle["observed_global_steps"].append(global_step)
                return original_on_step_end(callback_args, callback_state, callback_control, **event_kwargs)

            callback_handler.on_train_begin = types.MethodType(probe_on_train_begin, callback_handler)
            callback_handler.on_step_end = types.MethodType(probe_on_step_end, callback_handler)

        range_used = False

        def probe_backward(*backward_args, **backward_kwargs):
            lifecycle["backward_call_count"] += 1
            return original_backward(*backward_args, **backward_kwargs)

        def probe_optimizer_step(*step_args, **step_kwargs):
            lifecycle["optimizer_step_count"] += 1
            return original_optimizer_step(*step_args, **step_kwargs)

        def absolute_outer_range(*range_args):
            nonlocal range_used
            caller = inspect.currentframe().f_back
            caller_proven = (
                caller is not None
                and caller.f_code is original_train.__code__
                and caller.f_lineno == outer_range_line
                and caller.f_locals.get("args") is training_args
            )
            exact_outer_args = range_args in (
                (1, target_global_step + 1),
                (1, target_global_step + 1, 1),
            )
            if not range_used and caller_proven and exact_outer_args:
                range_used = True
                lifecycle["outer_range_call_count"] += 1
                return builtins.range(1, 1 + expected_additional)
            return builtins.range(*range_args)

        try:
            train_globals["range"] = absolute_outer_range
            accelerator.backward = probe_backward
            optimizer.step = probe_optimizer_step
            result = original_train(self, *args, **kwargs)
        finally:
            train_globals["range"] = original_range
            accelerator.backward = original_backward
            optimizer.step = original_optimizer_step
            if callback_handler is not None:
                callback_handler.on_train_begin = original_on_train_begin
                callback_handler.on_step_end = original_on_step_end
        scheduler_after = _scheduler_native_snapshot(
            scheduler,
            name="P1 production lr_scheduler",
            expected_last_epoch=target_global_step,
        )
        if (
            scheduler_after["native_step_func"] is not scheduler_before["native_step_func"]
            or scheduler_after["native_step_owner"] is not scheduler_before["native_step_owner"]
        ):
            raise RuntimeError("P1 lr_scheduler.step native method identity changed during training")
        scheduler_step_delta = scheduler_after["step_count"] - scheduler_before["step_count"]
        scheduler_epoch_delta = scheduler_after["last_epoch"] - scheduler_before["last_epoch"]
        if scheduler_step_delta != scheduler_epoch_delta:
            raise RuntimeError("P1 lr_scheduler native _step_count/last_epoch deltas disagree")
        lifecycle["scheduler_step_count"] = scheduler_step_delta
        lifecycle["scheduler_step_count_before"] = scheduler_before["step_count"]
        lifecycle["scheduler_step_count_after"] = scheduler_after["step_count"]
        lifecycle["scheduler_last_epoch_before"] = scheduler_before["last_epoch"]
        lifecycle["scheduler_last_epoch_after"] = scheduler_after["last_epoch"]
        if not range_used or lifecycle["outer_range_call_count"] != 1:
            raise RuntimeError("P1 production trainer outer absolute-target loop was not observed")
        if lifecycle["callback_train_begin_seen"] and lifecycle["callback_max_steps"] != target_global_step:
            raise RuntimeError("P1 callback state.max_steps did not remain absolute")
        if lifecycle["callback_step_end_count"] != expected_additional:
            raise RuntimeError(
                "P1 callback lifecycle count drifted: "
                f"expected {expected_additional}, got {lifecycle['callback_step_end_count']}"
            )
        expected_updates = expected_additional * P1_EFFECTIVE_NUM_MINI_BATCHES
        if lifecycle["backward_call_count"] != expected_updates:
            raise RuntimeError(
                "P1 production trainer backward lifecycle count drifted: "
                f"expected {expected_updates}, got {lifecycle['backward_call_count']}"
            )
        if lifecycle["optimizer_step_count"] != expected_updates:
            raise RuntimeError(
                "P1 production trainer optimizer lifecycle count drifted: "
                f"expected {expected_updates}, got {lifecycle['optimizer_step_count']}"
            )
        if lifecycle["scheduler_step_count"] != expected_additional:
            raise RuntimeError(
                "P1 production trainer scheduler lifecycle count drifted: "
                f"expected {expected_additional}, got {lifecycle['scheduler_step_count']}"
            )
        if lifecycle["observed_global_steps"] != list(range(start_global_step + 1, target_global_step + 1)):
            raise RuntimeError("P1 callback global-step progression drifted")
        final_step = getattr(getattr(self, "state", None), "global_step", None)
        if final_step != target_global_step:
            raise RuntimeError(
                "P1 training stopped before its absolute target: "
                f"expected {target_global_step}, got {final_step}"
            )
        lifecycle["iteration_time_s"] = time.time() - lifecycle_started_at
        setattr(trainer_class, "_a2_p1_last_lifecycle", dict(lifecycle))
        if branch_root is not None:
            _seal_pre_teardown_completion_proof(
                branch_root=branch_root,
                branch=branch,
                source=source,
                runtime=runtime,
                environment=environment,
                lifecycle=lifecycle,
                start_global_step=start_global_step,
                target_global_step=target_global_step,
                run_iterations=expected_additional,
                final_checkpoint=branch_root / f"model_step_{target_global_step:06d}.pt",
                final_config=branch_root / "config.yaml",
                iteration_time_s=lifecycle["iteration_time_s"],
                controlled_post_training_exit=controlled_post_training_exit,
            )
            if controlled_post_training_exit:
                _controlled_post_training_exit(branch_root / P1_PRE_TEARDOWN_PROOF_FILENAME)
        return result

    guarded_train.__name__ = "p1_absolute_target_train"
    guarded_train.__qualname__ = f"{trainer_class.__name__}.p1_absolute_target_train"
    trainer_class.train = guarded_train
    trainer_class._a2_p1_absolute_target_guard = True


def _execute_branch_impl(args: argparse.Namespace) -> int:
    """Execute one branch after all CPU contract checks (never used by dry-run/tests)."""
    if getattr(args, "controlled_post_training_exit", False) is not True:
        raise RuntimeError("P1 production branch execution requires --controlled-post-training-exit")
    branch_root = args.branch_root.expanduser().resolve()
    validate_fresh_output_root(branch_root)
    if args.start_global_step == EXPECTED_INITIAL_GLOBAL_STEP:
        source = validate_source_checkpoint(
            args.checkpoint,
            args.config,
            expected_checkpoint_sha256=args.checkpoint_sha256,
            expected_config_sha256=args.config_sha256,
        )
    else:
        source = validate_branch_checkpoint(
            args.checkpoint,
            args.config,
            expected_checkpoint_sha256=args.checkpoint_sha256,
            expected_config_sha256=args.config_sha256,
            expected_global_step=args.start_global_step,
        )
    teacher = validate_teacher_triplet(
        args.teacher_actor_path, args.teacher_config_path, args.teacher_manifest_path
    )
    runtime = validate_runtime_contract(args.runtime_repository)
    target_config = _expected_path(args.target_config, TARGET_CONFIG, "P1 target config")
    if not target_config.is_file():
        raise FileNotFoundError(f"P1 target config is unavailable: {target_config}")
    environment = build_gpu_binding_environment()
    validate_gpu_binding_environment(environment)
    teacher_paths = {
        "teacher_actor_path": Path(teacher["checkpoint"]["path"]),
        "teacher_config_path": Path(teacher["config"]["path"]),
        "teacher_manifest_path": Path(teacher["manifest"]["path"]),
    }
    overrides = build_training_overrides(
        mode=args.mode,
        branch_root=branch_root,
        checkpoint=Path(source["path"]),
        teacher_checkpoint=teacher_paths["teacher_actor_path"],
        teacher_config=teacher_paths["teacher_config_path"],
        teacher_manifest=teacher_paths["teacher_manifest_path"],
        iterations=args.iterations,
        run_iterations=args.run_iterations,
        start_global_step=args.start_global_step,
    )
    if args.hydra_overrides and tuple(args.hydra_overrides) != tuple(overrides):
        raise RuntimeError(
            "P1 branch Hydra overrides differ from the fail-fast generated contract"
        )
    validate_training_override_contract(
        overrides,
        mode=args.mode,
        branch_root=branch_root,
        checkpoint=Path(source["path"]),
        teacher=teacher_paths,
        iterations=args.iterations,
        expected_start_global_step=args.start_global_step,
        run_iterations=args.run_iterations,
    )
    if args.target_global_step != args.start_global_step + args.run_iterations:
        raise RuntimeError(
            "P1 branch target arithmetic drifted: "
            f"expected {args.start_global_step + args.run_iterations}, got {args.target_global_step}"
        )
    if args.source_manifest_root is not None or args.source_manifest_sha256 is not None:
        if args.source_manifest_root is None or args.source_manifest_sha256 is None:
            raise ValueError("extension execution requires source manifest root and SHA256 together")
        sealed_source = load_sealed_branch_manifest(
            args.source_manifest_root,
            expected_sha256=args.source_manifest_sha256,
            expected_mode=args.mode,
            expected_target_global_step=INITIAL_TARGET_GLOBAL_STEP,
        )
        if Path(sealed_source["final_checkpoint"]["path"]) != Path(source["path"]).resolve():
            raise RuntimeError("extension checkpoint is not the exact checkpoint sealed by its source manifest")
        if sealed_source["final_checkpoint"]["sha256"] != source["sha256"]:
            raise RuntimeError("extension checkpoint SHA256 differs from its source manifest")
    elif args.iterations == EXTENDED_ITERATIONS:
        raise ValueError("P1 direct --iterations 500 execution requires --extend-from-root sealed source manifests")
    # Importing the legacy bootstrap is delayed until explicit execution.  Its
    # ``main`` is not called, so the historical 10k guard remains untouched.
    from gr00t.rl.scripts import run_a2_student_distillation_v19 as bootstrap

    overlay = bootstrap.prepare_overlay_import(args.overlay_repository)
    module_sources = bootstrap.validate_runtime_repository(args.runtime_repository)
    bootstrap.validate_gpu7_environment(environment)
    bootstrap.validate_teacher_triplet(
        teacher_paths["teacher_actor_path"],
        teacher_paths["teacher_config_path"],
        teacher_paths["teacher_manifest_path"],
    )
    if set(module_sources).intersection(sys.modules):
        raise RuntimeError("c18 runtime task modules were imported before P1 bootstrap")
    bootstrap.install_v19_runtime_scenario_file_pin(module_sources)
    sys.meta_path.insert(0, bootstrap.V19RuntimeFinder(module_sources))
    from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import (
        TRLDistillTrainerA2BaseAPI,
    )

    install_absolute_target_train_guard(
        TRLDistillTrainerA2BaseAPI,
        start_global_step=args.start_global_step,
        target_global_step=args.target_global_step,
        branch_root=branch_root,
        branch=args.mode,
        source=source,
        runtime=runtime,
        environment=environment,
        controlled_post_training_exit=bool(getattr(args, "controlled_post_training_exit", False)),
    )
    os.environ.clear()
    os.environ.update(environment)
    os.chdir(overlay)
    train_entrypoint = overlay / "gr00t/rl/train_agent_trl.py"
    sys.argv = [str(train_entrypoint), *overrides]
    runpy.run_path(str(train_entrypoint), run_name="__main__")
    proof_path = branch_root / P1_PRE_TEARDOWN_PROOF_FILENAME
    if not proof_path.is_file():
        raise RuntimeError("P1 train returned without a pre-teardown completion proof")
    if getattr(args, "controlled_post_training_exit", False):
        raise RuntimeError("P1 controlled post-training path returned instead of exiting after proof seal")
    final_checkpoint = branch_root / f"model_step_{args.target_global_step:06d}.pt"
    print(f"[A2_P1_BRANCH_TRAIN_PASS] mode={args.mode} final_checkpoint={final_checkpoint}", flush=True)
    return 0


def _load_runtime_lifecycle(path: Path, *, spec: P1BranchSpec) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=True)
    lifecycle = _load_json(path)
    if lifecycle.get("schema") != P1_RUNTIME_LIFECYCLE_SCHEMA:
        raise RuntimeError("P1 pre-teardown completion proof schema drifted")
    content_sha = _require_sha(lifecycle.get("manifest_content_sha256"), "runtime lifecycle content hash")
    without_content = dict(lifecycle)
    without_content.pop("manifest_content_sha256", None)
    if sha256_bytes(canonical_json(without_content).encode("utf-8")) != content_sha:
        raise RuntimeError("P1 pre-teardown completion proof content hash drifted")
    if lifecycle.get("operation") != "p1_pre_teardown_completion" or lifecycle.get("proof_stage") != "PRE_TEARDOWN":
        raise RuntimeError("P1 pre-teardown completion proof operation/stage drifted")
    if lifecycle.get("root") != str(spec.root.resolve()):
        raise RuntimeError("P1 pre-teardown completion proof root identity drifted")
    if lifecycle.get("branch") != spec.mode:
        raise RuntimeError("P1 pre-teardown completion proof branch identity drifted")
    lifecycle_start_global_step = _strict_int(lifecycle.get("start_global_step"), "lifecycle.start_global_step")
    lifecycle_target_global_step = _strict_int(lifecycle.get("target_global_step"), "lifecycle.target_global_step")
    if lifecycle_start_global_step != spec.start_global_step or lifecycle_target_global_step != spec.target_global_step:
        raise RuntimeError("P1 pre-teardown completion proof absolute target drifted")
    if lifecycle.get("expected_additional_iterations") != spec.run_iterations or lifecycle.get("completed_iterations") != spec.run_iterations:
        raise RuntimeError("P1 pre-teardown completion proof iteration count drifted")
    if lifecycle.get("num_mini_batches") != P1_EFFECTIVE_NUM_MINI_BATCHES:
        raise RuntimeError("P1 pre-teardown completion proof num_mini_batches drifted")
    if lifecycle.get("num_ppo_epochs") != P1_EFFECTIVE_NUM_PPO_EPOCHS:
        raise RuntimeError("P1 pre-teardown completion proof num_ppo_epochs drifted")
    if lifecycle.get("num_micro_batches") != P1_EFFECTIVE_NUM_MICRO_BATCHES:
        raise RuntimeError("P1 pre-teardown completion proof micro-batch count drifted")
    expected_updates = spec.run_iterations * P1_EFFECTIVE_NUM_MINI_BATCHES
    _strict_nonnegative_int(lifecycle.get("backward_call_count"), "lifecycle.backward_call_count")
    _strict_nonnegative_int(lifecycle.get("optimizer_step_count"), "lifecycle.optimizer_step_count")
    if lifecycle["backward_call_count"] != expected_updates or lifecycle["optimizer_step_count"] != expected_updates:
        raise RuntimeError("P1 pre-teardown completion proof backward/optimizer counts drifted")
    if _strict_nonnegative_int(lifecycle.get("scheduler_step_count"), "lifecycle.scheduler_step_count") != spec.run_iterations:
        raise RuntimeError("P1 pre-teardown completion proof scheduler count drifted")
    scheduler_before = _strict_int(lifecycle.get("scheduler_step_count_before"), "lifecycle.scheduler_step_count_before")
    scheduler_after = _strict_int(lifecycle.get("scheduler_step_count_after"), "lifecycle.scheduler_step_count_after")
    epoch_before = _strict_int(lifecycle.get("scheduler_last_epoch_before"), "lifecycle.scheduler_last_epoch_before")
    epoch_after = _strict_int(lifecycle.get("scheduler_last_epoch_after"), "lifecycle.scheduler_last_epoch_after")
    if scheduler_after - scheduler_before != spec.run_iterations or epoch_after - epoch_before != spec.run_iterations:
        raise RuntimeError("P1 pre-teardown scheduler native counter deltas drifted")
    if scheduler_after - scheduler_before != epoch_after - epoch_before:
        raise RuntimeError("P1 pre-teardown scheduler native counter deltas disagree")
    if scheduler_before != spec.start_global_step + 1 or epoch_before != spec.start_global_step:
        raise RuntimeError("P1 pre-teardown scheduler before counters are not source-bound")
    if scheduler_after != spec.target_global_step + 1 or epoch_after != spec.target_global_step:
        raise RuntimeError("P1 pre-teardown scheduler after counters are not target-bound")
    if lifecycle.get("outer_range_call_count") != 1:
        raise RuntimeError("P1 pre-teardown completion proof outer range count drifted")
    if lifecycle.get("callback_train_begin_seen") is not True:
        raise RuntimeError("P1 pre-teardown completion proof lacks callback train-begin proof")
    if lifecycle.get("callback_step_end_count") != spec.run_iterations or lifecycle.get("callback_max_steps") != spec.target_global_step:
        raise RuntimeError("P1 pre-teardown completion proof callback proof drifted")
    observed = lifecycle.get("observed_global_steps")
    validate_global_step_progression(spec.start_global_step, spec.target_global_step, observed)
    iteration_time = _strict_float(lifecycle.get("iteration_time_s"), "lifecycle.iteration_time_s")
    if iteration_time <= 0.0:
        raise RuntimeError("P1 pre-teardown completion proof iteration time must be positive")
    if lifecycle.get("natural_kit_lifecycle_pass") is not False:
        raise RuntimeError("P1 natural Kit lifecycle must remain explicitly unresolved")
    if lifecycle.get("lifecycle_status") != "UNRESOLVED":
        raise RuntimeError("P1 lifecycle_status must remain UNRESOLVED before parent teardown audit")
    if lifecycle.get("controlled_post_training_exit") is not True:
        raise RuntimeError("P1 pre-teardown completion proof lacks controlled exit marker")
    source = lifecycle.get("source")
    if not isinstance(source, Mapping):
        raise TypeError("P1 pre-teardown completion proof source must be a mapping")
    source_global_step = _strict_int(source.get("global_step"), "source.global_step")
    if source_global_step != spec.start_global_step or source.get("checkpoint_load_mode") != "full":
        raise RuntimeError("P1 pre-teardown source binding drifted")
    _sealed_artifact(source.get("checkpoint"), name="pre-teardown source checkpoint", expected_path=spec.checkpoint)
    _sealed_artifact(source.get("config"), name="pre-teardown source config", expected_path=spec.checkpoint_config)
    runtime = lifecycle.get("runtime")
    if not isinstance(runtime, Mapping) or runtime.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError("P1 pre-teardown runtime binding drifted")
    final = lifecycle.get("final_checkpoint")
    if not isinstance(final, Mapping):
        raise TypeError("P1 pre-teardown completion proof final_checkpoint must be a mapping")
    if final.get("path") != str(spec.final_checkpoint.resolve()) or final.get("global_step") != spec.target_global_step:
        raise RuntimeError("P1 pre-teardown final checkpoint identity drifted")
    stable_final = _stable_proof_artifact(
        spec.final_checkpoint,
        name="P1 pre-teardown final checkpoint",
        root=spec.root,
        expected_path=spec.final_checkpoint,
    )
    if stable_final["sha256"] != final.get("sha256"):
        raise RuntimeError("P1 pre-teardown final checkpoint hash drifted after child exit")
    final_config = lifecycle.get("final_config")
    if not isinstance(final_config, Mapping):
        raise TypeError("P1 pre-teardown completion proof final_config must be a mapping")
    expected_config = spec.final_checkpoint.with_name("config.yaml").resolve()
    if final_config.get("path") != str(expected_config):
        raise RuntimeError("P1 pre-teardown final config identity drifted")
    stable_config = _stable_proof_artifact(
        expected_config,
        name="P1 pre-teardown final config",
        root=spec.root,
        expected_path=expected_config,
    )
    if stable_config["sha256"] != final_config.get("sha256"):
        raise RuntimeError("P1 pre-teardown final config hash drifted after child exit")
    identity = lifecycle.get("gpu_identity")
    if not isinstance(identity, Mapping):
        raise TypeError("P1 runtime lifecycle gpu_identity must be a mapping")
    if (
        identity.get("physical_gpu_index") != EXPECTED_GPU_INDEX
        or identity.get("logical_gpu_index") != int(EXPECTED_LOGICAL_GPU_INDEX)
        or identity.get("logical_device") != EXPECTED_LOGICAL_DEVICE
        or identity.get("uuid") != EXPECTED_GPU_UUID
        or identity.get("cuda_visible_devices") != EXPECTED_GPU_INDEX
        or identity.get("world_size") != 1
        or identity.get("binding_mode") != EXPECTED_GPU_BINDING_MODE
        or identity.get("cuda_device_order") != EXPECTED_CUDA_DEVICE_ORDER
    ):
        raise RuntimeError("P1 pre-teardown GPU binding drifted")
    return dict(lifecycle)


def _finalize_branch_evidence(
    spec: P1BranchSpec,
    *,
    runtime: Mapping[str, Any],
    teacher: Mapping[str, Any],
    target_config: Path,
    telemetry: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal telemetry, runtime metrics, and branch provenance after child exit."""
    branch_root = spec.root.expanduser().resolve()
    telemetry_path = branch_root / P1_GPU_TELEMETRY_FILENAME
    seal_json(telemetry_path, telemetry)
    telemetry_summary = load_gpu_telemetry_peak_vram(telemetry_path)
    lifecycle = _load_runtime_lifecycle(branch_root / P1_RUNTIME_LIFECYCLE_FILENAME, spec=spec)
    proof_path = branch_root / P1_PRE_TEARDOWN_PROOF_FILENAME
    lifecycle_manifest = {
        "proof": artifact_ref(proof_path),
        "natural_kit_lifecycle_pass": False,
        "lifecycle_status": "UNRESOLVED",
        "controlled_post_training_exit": True,
    }
    metrics_path = branch_root / P1_RUNTIME_METRICS_FILENAME
    metrics = {
        "schema": P1_RUNTIME_METRICS_SCHEMA,
        "training_performed": True,
        "start_global_step": spec.start_global_step,
        "target_global_step": spec.target_global_step,
        "num_mini_batches": P1_EFFECTIVE_NUM_MINI_BATCHES,
        "num_ppo_epochs": P1_EFFECTIVE_NUM_PPO_EPOCHS,
        "num_micro_batches": P1_EFFECTIVE_NUM_MICRO_BATCHES,
        "completed_iterations": spec.run_iterations,
        "additional_iterations": spec.run_iterations,
        "backward_call_count": lifecycle["backward_call_count"],
        "optimizer_step_count": lifecycle["optimizer_step_count"],
        "scheduler_step_count": lifecycle["scheduler_step_count"],
        "scheduler_step_count_before": lifecycle["scheduler_step_count_before"],
        "scheduler_step_count_after": lifecycle["scheduler_step_count_after"],
        "scheduler_last_epoch_before": lifecycle["scheduler_last_epoch_before"],
        "scheduler_last_epoch_after": lifecycle["scheduler_last_epoch_after"],
        "observed_global_steps": lifecycle["observed_global_steps"],
        "peak_vram_mib": telemetry_summary["peak_vram_mib"],
        "iteration_time_s": lifecycle["iteration_time_s"],
        "final_checkpoint": lifecycle["final_checkpoint"],
        "gpu_identity": lifecycle["gpu_identity"],
        "callback_train_begin_seen": lifecycle["callback_train_begin_seen"],
        "callback_step_end_count": lifecycle["callback_step_end_count"],
        "callback_max_steps": lifecycle["callback_max_steps"],
        "observability": {
            "telemetry_record_count": telemetry_summary["record_count"],
            "pre_teardown_proof": lifecycle_manifest["proof"],
            "natural_kit_lifecycle_pass": False,
            "lifecycle_status": "UNRESOLVED",
            "controlled_post_training_exit": True,
        },
    }
    seal_json(metrics_path, metrics)
    runtime_evidence = load_runtime_evidence(
        metrics_path,
        telemetry_path,
        start_global_step=spec.start_global_step,
        target_global_step=spec.target_global_step,
        expected_iterations=spec.run_iterations,
    )
    manifest = build_branch_manifest(
        spec,
        runtime=runtime,
        teacher=teacher,
        target_config=target_config,
        final_checkpoint=spec.final_checkpoint,
        final_config=spec.final_checkpoint.with_name("config.yaml"),
        total_completed_iterations=spec.requested_iterations,
        backward_call_count=runtime_evidence["metrics"]["backward_call_count"],
        optimizer_step_count=runtime_evidence["metrics"]["optimizer_step_count"],
        scheduler_step_count=runtime_evidence["metrics"]["scheduler_step_count"],
        scheduler_step_count_before=runtime_evidence["metrics"]["scheduler_step_count_before"],
        scheduler_step_count_after=runtime_evidence["metrics"]["scheduler_step_count_after"],
        scheduler_last_epoch_before=runtime_evidence["metrics"]["scheduler_last_epoch_before"],
        scheduler_last_epoch_after=runtime_evidence["metrics"]["scheduler_last_epoch_after"],
        peak_vram_mib=runtime_evidence["metrics"]["peak_vram_mib"],
        runtime_evidence=runtime_evidence,
        lifecycle=lifecycle_manifest,
        effective_training_contract=validate_effective_training_config(
            compose_training_config(spec.overrides), mode=spec.mode, target_global_step=spec.target_global_step
        ),
    )
    sealed_manifest = seal_json(branch_root / P1_BRANCH_MANIFEST_FILENAME, manifest)
    return {
        "manifest": sealed_manifest,
        "runtime_evidence": runtime_evidence,
        "telemetry": telemetry_summary,
    }


def _spec_from_execute_args(args: argparse.Namespace) -> P1BranchSpec:
    if args.start_global_step == EXPECTED_INITIAL_GLOBAL_STEP:
        source = validate_source_checkpoint(
            args.checkpoint,
            args.config,
            expected_checkpoint_sha256=args.checkpoint_sha256,
            expected_config_sha256=args.config_sha256,
        )
    else:
        source = validate_branch_checkpoint(
            args.checkpoint,
            args.config,
            expected_checkpoint_sha256=args.checkpoint_sha256,
            expected_config_sha256=args.config_sha256,
            expected_global_step=args.start_global_step,
        )
    teacher = validate_teacher_triplet(
        args.teacher_actor_path,
        args.teacher_config_path,
        args.teacher_manifest_path,
    )
    teacher_paths = {
        "teacher_actor_path": Path(teacher["checkpoint"]["path"]),
        "teacher_config_path": Path(teacher["config"]["path"]),
        "teacher_manifest_path": Path(teacher["manifest"]["path"]),
    }
    overrides = build_training_overrides(
        mode=args.mode,
        branch_root=args.branch_root,
        checkpoint=Path(source["path"]),
        teacher_checkpoint=teacher_paths["teacher_actor_path"],
        teacher_config=teacher_paths["teacher_config_path"],
        teacher_manifest=teacher_paths["teacher_manifest_path"],
        iterations=args.iterations,
        run_iterations=args.run_iterations,
        start_global_step=args.start_global_step,
    )
    return P1BranchSpec(
        mode=args.mode,
        root=args.branch_root.expanduser().resolve(),
        checkpoint=Path(source["path"]),
        checkpoint_sha256=source["sha256"],
        checkpoint_config=Path(source["config_path"]),
        checkpoint_config_sha256=source["config_sha256"],
        start_global_step=args.start_global_step,
        requested_iterations=args.iterations,
        run_iterations=args.run_iterations,
        target_global_step=args.target_global_step,
        overrides=tuple(overrides),
        command=(),
        source_manifest_root=args.source_manifest_root,
        source_manifest_sha256=args.source_manifest_sha256,
    )


def write_failure_evidence(root: Path, error: BaseException) -> Path:
    """Retain a typed failure artifact; never overwrite a prior branch result."""
    root = root.expanduser().resolve()
    path = root / "p1_failure.json"
    payload = {
        "schema": "a2_cb2h_pro_p1_failure_v1",
        "operation": "p1_training_failure",
        "root": str(root),
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    seal_json(path, payload)
    return path


def _execute_branch(args: argparse.Namespace) -> int:
    sampler = None
    try:
        if not args.defer_seal:
            environment = build_gpu_binding_environment()
            validate_gpu_binding_environment(environment)
            sampler = GpuTelemetrySampler(environment)
            sampler.start()
        result = _execute_branch_impl(args)
        if sampler is not None:
            telemetry = sampler.stop()
            spec = _spec_from_execute_args(args)
            runtime = validate_runtime_contract(args.runtime_repository)
            teacher = validate_teacher_triplet(
                args.teacher_actor_path,
                args.teacher_config_path,
                args.teacher_manifest_path,
            )
            target_config = _expected_path(args.target_config, TARGET_CONFIG, "P1 target config")
            _finalize_branch_evidence(
                spec,
                runtime=runtime,
                teacher=teacher,
                target_config=target_config,
                telemetry=telemetry,
            )
            print(f"[A2_P1_BRANCH_PASS] mode={args.mode} final_checkpoint={spec.final_checkpoint}", flush=True)
        return result
    except BaseException as error:
        if sampler is not None:
            try:
                telemetry = sampler.stop()
                telemetry_path = args.branch_root.expanduser().resolve() / P1_GPU_TELEMETRY_FILENAME
                if not telemetry_path.exists():
                    seal_json(telemetry_path, telemetry)
            except BaseException as telemetry_error:
                error = RuntimeError(f"P1 branch telemetry sealing failed: {telemetry_error}")
        if args.branch_root is not None:
            write_failure_evidence(args.branch_root, error)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="validate and print both commands")
    parser.add_argument("--execute", action="store_true", help="launch both branches; requires GPU7")
    parser.add_argument("--execute-branch", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--defer-seal", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--controlled-post-training-exit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--n3-infer", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument(
        "--extend-from-root",
        type=Path,
        help="existing 200-step root containing sequential/packed checkpoints; requires --iterations 500",
    )
    parser.add_argument("--sequential-manifest-sha256")
    parser.add_argument("--packed-manifest-sha256")
    parser.add_argument("--branch-root", type=Path)
    parser.add_argument("--mode", choices=P1_FORWARD_MODES)
    parser.add_argument("--iterations", type=int, choices=(INITIAL_ITERATIONS, EXTENDED_ITERATIONS), default=INITIAL_ITERATIONS)
    parser.add_argument("--run-iterations", type=int)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--config-sha256")
    parser.add_argument("--start-global-step", type=int, default=EXPECTED_INITIAL_GLOBAL_STEP)
    parser.add_argument("--target-global-step", type=int)
    parser.add_argument("--source-manifest-root", type=Path)
    parser.add_argument("--source-manifest-sha256")
    parser.add_argument("--metrics-path", type=Path)
    parser.add_argument("--gpu-telemetry-path", type=Path)
    parser.add_argument("--target-config", type=Path, default=TARGET_CONFIG)
    parser.add_argument("--n3-phase-manifest", type=Path)
    parser.add_argument("--n3-phase-manifest-sha256")
    parser.add_argument("--n3-h5", type=Path)
    parser.add_argument("--n3-h5-sha256")
    parser.add_argument("--n3-trajectory-manifest", type=Path)
    parser.add_argument("--n3-trajectory-manifest-sha256")
    parser.add_argument("--replicate-id")
    parser.add_argument("--recurrent-reset-per-replicate", action="store_true")
    parser.add_argument("--device", default=EXPECTED_LOGICAL_DEVICE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checkpoint", type=Path, default=SOURCE_CHECKPOINT)
    parser.add_argument("--config", type=Path, default=SOURCE_CONFIG)
    parser.add_argument("--runtime-repository", type=Path, default=RUNTIME_REPOSITORY)
    parser.add_argument("--overlay-repository", type=Path, default=REPO_ROOT)
    parser.add_argument("--n3-root", type=Path, default=N3_INPUT_ROOT)
    parser.add_argument("--n2-root", type=Path, default=N2_INPUT_ROOT)
    parser.add_argument("--teacher-actor-path", type=Path, default=TEACHER_CHECKPOINT)
    parser.add_argument("--teacher-config-path", type=Path, default=TEACHER_CONFIG)
    parser.add_argument("--teacher-manifest-path", type=Path, default=TEACHER_MANIFEST)
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = _parser()
    args, unknown = parser.parse_known_args(argv)
    if unknown and not args.execute_branch:
        raise ValueError(f"unexpected P1 arguments: {unknown}")
    args.hydra_overrides = tuple(unknown)
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.n3_infer:
        return execute_n3_inference(args)
    if args.execute_branch:
        if args.branch_root is None or args.mode is None:
            raise ValueError("--execute-branch requires --branch-root and --mode")
        if args.run_iterations is None:
            raise ValueError("--execute-branch requires --run-iterations")
        if args.target_global_step is None:
            raise ValueError("--execute-branch requires --target-global-step")
        return _execute_branch(args)
    if args.dry_run == args.execute:
        raise ValueError("select exactly one of --dry-run or --execute")
    if args.output_root is None:
        raise ValueError("--output-root is required for a P1 plan")
    if args.extend_from_root is not None:
        if args.iterations != EXTENDED_ITERATIONS:
            raise ValueError("--extend-from-root requires --iterations 500")
        plan = build_paired_extension_plan(
            args.output_root,
            args.extend_from_root / "sequential",
            args.extend_from_root / "packed",
            sequential_manifest_sha256=args.sequential_manifest_sha256,
            packed_manifest_sha256=args.packed_manifest_sha256,
            teacher_checkpoint=args.teacher_actor_path,
            teacher_config=args.teacher_config_path,
            teacher_manifest=args.teacher_manifest_path,
            runtime_repository=args.runtime_repository,
            overlay_repository=args.overlay_repository,
            n3_root=args.n3_root,
            n2_root=args.n2_root,
        )
    else:
        plan = build_p1_plan(
            args.output_root,
            requested_iterations=args.iterations,
            checkpoint=args.checkpoint,
            config_path=args.config,
            teacher_checkpoint=args.teacher_actor_path,
            teacher_config=args.teacher_config_path,
            teacher_manifest=args.teacher_manifest_path,
            runtime_repository=args.runtime_repository,
            overlay_repository=args.overlay_repository,
            n3_root=args.n3_root,
            n2_root=args.n2_root,
        )
    if args.dry_run:
        print(canonical_json(plan.as_dict()), flush=True)
        return 0
    environment = build_gpu_binding_environment()
    validate_gpu_binding_environment(environment)
    for branch in plan.branches:
        sampler = GpuTelemetrySampler(environment)
        sampler.start()
        command = [
            *branch.command,
            "--defer-seal",
            "--controlled-post-training-exit",
        ]
        try:
            subprocess.run(command, check=True, env=environment)
            telemetry = sampler.stop()
            runtime = validate_runtime_contract(args.runtime_repository)
            teacher = validate_teacher_triplet(
                args.teacher_actor_path,
                args.teacher_config_path,
                args.teacher_manifest_path,
            )
            target_config = _expected_path(args.target_config, TARGET_CONFIG, "P1 target config")
            _finalize_branch_evidence(
                branch,
                runtime=runtime,
                teacher=teacher,
                target_config=target_config,
                telemetry=telemetry,
            )
            print(f"[A2_P1_BRANCH_PASS] mode={branch.mode} final_checkpoint={branch.final_checkpoint}", flush=True)
        except BaseException as exc:
            try:
                telemetry = sampler.stop()
                telemetry_path = branch.root / P1_GPU_TELEMETRY_FILENAME
                if not telemetry_path.exists():
                    seal_json(telemetry_path, telemetry)
            except BaseException as telemetry_error:
                exc = RuntimeError(f"P1 branch telemetry collection/sealing failed: {telemetry_error}")
            # Preserve partial branch evidence.  Never remove it or retry in-place.
            failure_path = branch.root / "failure.json"
            if not failure_path.exists():
                branch.root.mkdir(parents=True, exist_ok=True)
                failure_path.write_text(
                    canonical_json(
                        {
                            "schema": f"{P1_SCHEMA}_failure_v1",
                            "branch": branch.mode,
                            "root": str(branch.root),
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "retry_requires_new_root": True,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
