#!/usr/bin/env python3
"""Fail-fast v19 C-B2H Student evaluation and selected-case render bootstrap.

The formal lane evaluates exactly one first episode in each of sixteen envs and
seals a deterministic ranking artifact.  The render lane consumes that sealed
artifact; it never discovers or hard-codes a selected environment.  Heavy
IsaacLab/IsaacSim imports are intentionally kept behind ``main`` so contract
helpers and tests remain CPU-safe.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import stat
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_ENTRY = (REPO_ROOT / "gr00t/rl/eval_agent_trl.py").resolve(strict=True)
RUNTIME_BOOTSTRAP_PATH = (
    REPO_ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v19.py"
).resolve(strict=True)
RUNTIME_BOOTSTRAP_MODULE_NAME = "_a2_student_distillation_v19_runtime"
CHECKPOINT = (
    REPO_ROOT
    / "logs_rl/cb2h_v19_distill/"
    "cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/"
    "model_step_010000.pt"
).resolve()
CHECKPOINT_CONFIG = CHECKPOINT.with_name("config.yaml")
CHECKPOINT_SHA256 = "005705dc033605a24bc231b18fbfaabe3288a699130a7ce2e423eac736963a45"
CHECKPOINT_CONFIG_SHA256 = "24f94faeca0270928c9c3ff33568e50371dc4f2f3feb767f6fe0607bb084351f"
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
STUDENT_GLOBAL_STEP = 10000
CONTROLLERS = ("student", "teacher")
STUDENT_D435I_FORWARD_MODES = ("sequential", "packed")
STUDENT_TRAINER_TARGET = (
    "gr00t.rl.trl.trainer.distill_trainer_a2_base_api.TRLDistillTrainerA2BaseAPI"
)
TEACHER_TRAINER_TARGET = (
    "gr00t.rl.trl.trainer.ppo_trainer_a2_base_api.TRLPPOTrainer"
)
EXPERIENCE_RELATIVE_PATHS = {
    "student": Path("gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit"),
    "teacher": Path("gr00t/rl/apps/isaaclab.python.headless.kit"),
}
EXPERIENCE_CAMERA_MODES = {
    "student": "cameras",
    "teacher": "no_cameras",
}
EXPERIENCE_SINGLE_GPU_SETTINGS = {
    "renderer.multiGpu.enabled": "false",
    "renderer.multiGpu.autoEnable": "false",
    "renderer.multiGpu.maxGpuCount": "1",
}
RUNTIME_REPOSITORY = Path("/tmp/cb2h_v19_runtime.waPJHftX/c18")
EXPECTED_RUNTIME_COMMIT = "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"
EXPECTED_GPU_INDEX = "7"
EXPECTED_LOGICAL_GPU_INDEX = "0"
EXPECTED_GPU_UUID = "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d"
EXPECTED_GPU_BINDING_MODE = "single-visible-logical-cuda0-v3"
EXPECTED_CUDA_DEVICE_ORDER = "PCI_BUS_ID"
EXPECTED_SEED = 0
EXPECTED_NUM_ENVS = 16
EXPECTED_EPISODES = 16
VIDEO_FPS = 20
STUDENT_SELECTION_SCHEMA = "a2_student_v19_selection_v2"
TEACHER_SELECTION_SCHEMA = "a2_teacher_v19_selection_v1"
STUDENT_METRICS_SCHEMA = "a2_student_v19_metrics_v2"
TEACHER_METRICS_SCHEMA = "a2_teacher_v19_metrics_v1"
N3_METRICS_SCHEMA = "a2_cb2h_n3_teacher_metrics_v1"
N3_SELECTION_SCHEMA = "a2_cb2h_n3_teacher_selection_v1"
N3_MANIFEST_SCHEMA = "a2_cb2h_n3_teacher_trajectory_manifest_v1"
N3_CAPTURE_MODE = "n3"
N3_PASSIVE_CONTROLLER = "student"
N3_CONTROL_CONTROLLER = "teacher"
N3_DATASET_FILENAME = "teacher_trajectory.h5"
N3_METRICS_FILENAME = "n3_teacher_metrics.json"
N3_SELECTION_FILENAME = "n3_teacher_selection.json"
N3_MANIFEST_FILENAME = "n3_teacher_trajectory_manifest.json"
N3_STAGING_SUFFIX = ".writing"
N3_DATASET_SCHEMA = "a2_cb2h_n3_teacher_trajectory_hdf5_v1"
N3_VALIDATION_ROW_CHUNK = 16
# Runtime-only canonical A2 helpers are populated by ``_bind_a2_eval_methods``
# after the c18 runtime has been loaded.  Keeping the references unset at
# module import time preserves the CPU-safe wrapper import contract.
_N3_RUNTIME_A2_DIAGNOSTIC_CONFIG_READER = None
_N3_RUNTIME_A2_ROLLOUT_ACTION_COMPOSER = None
N3_EXPECTED_DATASET_SHAPES = {
    "actor_obs": (81,),
    "left_rgb": (384, 216, 3),
    "right_rgb": (384, 216, 3),
    "head_rgb": (136, 384, 3),
    "camera_meta": (6,),
    "teacher_action": (12,),
    "pre_action_stage": (),
    "done": (),
    "active_mask": (),
    "env_id": (),
    "frame_id": (),
    "episode_index": (),
    "case_id": (),
}
N3_EXPECTED_DATASET_DTYPES = {
    "actor_obs": "float32",
    "left_rgb": "uint8",
    "right_rgb": "uint8",
    "head_rgb": "uint8",
    "camera_meta": "float32",
    "teacher_action": "float32",
    "pre_action_stage": "int16",
    "done": "bool",
    "active_mask": "bool",
    "env_id": "int16",
    "frame_id": "int64",
    "episode_index": "int16",
    "case_id": "S64",
}
# Keep the student aliases for callers of the original v19 Student wrapper.
SELECTION_SCHEMA = STUDENT_SELECTION_SCHEMA
METRICS_SCHEMA = STUDENT_METRICS_SCHEMA
LEGACY_SELECTION_SCHEMA = "a2_student_v19_selection_v1"
LEGACY_METRICS_SCHEMA = "a2_student_v19_metrics_v1"

# c18 terminal diagnostics expose these four exact randomized door-case values.
# They are the replay identity; target/source poses are dynamics outputs and are
# deliberately not used as a substitute.
RANDOMIZED_CASE_KEYS = (
    "door_hinge_drive_max_force",
    "door_handle_drive_max_force",
    "door_handle_height",
    "door_weight",
)
SEMANTIC_KEYS = ("goal_reached", "max_stage", "terminal_reason")
OUTCOME_KEYS = (*SEMANTIC_KEYS, "reward")
FORMAL_RANKING_ORDER = "goal_reached_desc,max_stage_desc,reward_desc,env_id_asc"
RENDER_TRIAL_RANKING_ORDER = (
    "replay_outcome.goal_reached_desc",
    "replay_outcome.max_stage_desc",
    "replay_outcome.reward_desc",
    "trial_id_asc",
)


def render_staging_root(output_root: Path) -> Path:
    """Return the sibling staging bundle used by the selected render lane."""
    output_root = output_root.expanduser().resolve()
    return output_root.with_name(f".{output_root.name}.writing")


def eval_runtime_log_root(mode: str, output_root: Path) -> Path:
    """Return the Hydra runtime-log directory without colliding with eval outputs."""
    if mode not in {"formal", "render", N3_CAPTURE_MODE}:
        raise ValueError(f"unknown eval mode {mode!r}")
    output_root = output_root.expanduser().resolve()
    if mode in {"render", N3_CAPTURE_MODE}:
        return output_root.with_name(f".{output_root.name}.runtime")
    return output_root / "hydra"


def temporary_policy_video_path(final_path: Path) -> Path:
    """Keep the final ``.mp4`` suffix so ImageIO selects its FFMPEG writer."""
    final_path = final_path.expanduser().resolve()
    if final_path.suffix.lower() != ".mp4":
        raise ValueError(f"policy video final path must end in .mp4: {final_path}")
    return final_path.with_name(f".{final_path.stem}.writing{final_path.suffix}")


def publish_render_bundle(staging_root: Path, output_root: Path) -> None:
    """Atomically publish a fully validated staging directory without overwrite."""
    staging_root = staging_root.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite final render bundle: {output_root}")
    if not staging_root.is_dir():
        raise FileNotFoundError(f"render staging bundle is unavailable: {staging_root}")
    os.replace(staging_root, output_root)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _kit_settings(path: Path) -> dict[str, str]:
    """Read the exact single-visible-GPU settings from one Kit source file.

    The wrapper deliberately validates the source text before IsaacLab starts.
    This keeps the experience provenance fail-fast and avoids relying on
    post-start Carbonite settings or the installed/default IsaacLab app files.
    """
    assignments: dict[str, list[str]] = {
        key: [] for key in EXPERIENCE_SINGLE_GPU_SETTINGS
    }
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key in assignments:
            assignments[key].append(value.strip().strip('"'))
    parsed: dict[str, str] = {}
    for key, expected in EXPERIENCE_SINGLE_GPU_SETTINGS.items():
        values = assignments[key]
        if len(values) != 1:
            raise RuntimeError(
                "experience source must contain exactly one single-GPU setting: "
                f"path={path} key={key!r} assignments={values!r}"
            )
        if values[0] != expected:
            raise RuntimeError(
                "experience source has an invalid single-GPU setting: "
                f"path={path} key={key!r} expected={expected!r} got={values[0]!r}"
            )
        parsed[key] = values[0]
    return parsed


def resolve_experience_source(
    overlay_repository: Path = REPO_ROOT, controller: str = "student"
) -> dict[str, Any]:
    """Select and validate the immutable overlay Kit source for one controller.

    Student formal/render runs require the camera-enabled overlay experience;
    Teacher formal runs require the no-camera overlay experience.  The
    installed IsaacLab ``apps`` directory is intentionally never searched.
    """
    if controller not in CONTROLLERS:
        raise ValueError(f"unknown controller {controller!r}; expected {CONTROLLERS}")
    overlay = overlay_repository.expanduser().resolve(strict=True)
    if not overlay.is_dir():
        raise NotADirectoryError(f"overlay repository is not a directory: {overlay}")
    relative_path = EXPERIENCE_RELATIVE_PATHS[controller]
    source = (overlay / relative_path).resolve(strict=True)
    if not source.is_relative_to(overlay):
        raise RuntimeError(
            "experience source escaped the selected overlay repository: "
            f"overlay={overlay} source={source}"
        )
    if not stat.S_ISREG(source.stat().st_mode):
        raise RuntimeError(f"experience source is not a regular file: {source}")
    settings = _kit_settings(source)
    return {
        "controller": controller,
        "camera_mode": EXPERIENCE_CAMERA_MODES[controller],
        "relative_path": str(relative_path),
        "path": str(source),
        "sha256": sha256_file(source),
        "settings": settings,
    }


def validate_experience_identity(
    expected: Mapping[str, Any],
    overlay_repository: Path = REPO_ROOT,
    controller: str = "student",
) -> dict[str, Any]:
    """Re-read the chosen Kit source and reject any plan/runtime identity drift."""
    if not isinstance(expected, Mapping):
        raise TypeError("expected experience identity must be a mapping")
    actual = resolve_experience_source(overlay_repository, controller)
    expected_controller = expected.get("controller", controller)
    if expected_controller != controller:
        raise RuntimeError(
            "experience controller identity mismatch: "
            f"expected={controller!r} got={expected_controller!r}"
        )
    for key in ("camera_mode", "path", "sha256"):
        if key not in expected:
            raise KeyError(f"experience identity is missing {key!r}")
        expected_value = str(expected[key]) if key != "path" else str(Path(expected[key]).expanduser().resolve())
        if actual[key] != expected_value:
            raise RuntimeError(
                "experience identity mismatch: "
                f"key={key!r} expected={expected_value!r} got={actual[key]!r}"
            )
    expected_relative = expected.get("relative_path")
    if expected_relative is not None and str(expected_relative) != actual["relative_path"]:
        raise RuntimeError(
            "experience relative path identity mismatch: "
            f"expected={expected_relative!r} got={actual['relative_path']!r}"
        )
    expected_settings = expected.get("settings")
    if expected_settings is not None and dict(expected_settings) != actual["settings"]:
        raise RuntimeError(
            "experience single-GPU settings identity mismatch: "
            f"expected={expected_settings!r} got={actual['settings']!r}"
        )
    return actual


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def atomic_json_write(path: Path, value: Any) -> None:
    path = path.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite sealed output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.writing")
    if tmp.exists():
        raise FileExistsError(f"temporary output already exists: {tmp}")
    try:
        with tmp.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


def n3_staging_root(output_root: Path) -> Path:
    output_root = output_root.expanduser().resolve()
    return output_root.with_name(f".{output_root.name}{N3_STAGING_SUFFIX}")


def n3_dataset_path(output_root: Path) -> Path:
    return output_root.expanduser().resolve() / N3_DATASET_FILENAME


def n3_metrics_path(output_root: Path) -> Path:
    return output_root.expanduser().resolve() / N3_METRICS_FILENAME


def n3_selection_path(output_root: Path) -> Path:
    return output_root.expanduser().resolve() / N3_SELECTION_FILENAME


def n3_manifest_path(output_root: Path) -> Path:
    return output_root.expanduser().resolve() / N3_MANIFEST_FILENAME


def n3_case_id(env_id: int, randomized_case: Mapping[str, Any]) -> str:
    if isinstance(env_id, bool) or not isinstance(env_id, int):
        raise TypeError(f"N3 case env_id must be an integer: {env_id!r}")
    if set(randomized_case) != set(RANDOMIZED_CASE_KEYS):
        raise ValueError(
            "N3 randomized case must contain exactly the four c18 fields: "
            f"expected={list(RANDOMIZED_CASE_KEYS)} got={sorted(randomized_case)}"
        )
    canonical_case = {
        "env_id": env_id,
        "randomized_case": {
            key: json_safe(randomized_case[key]) for key in RANDOMIZED_CASE_KEYS
        },
    }
    return sha256_json(canonical_case)


def n3_case_table_from_metrics(metrics: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    records = episode_records(json_safe(metrics))
    if len(records) != EXPECTED_EPISODES:
        raise RuntimeError(
            "N3 capture must seal exactly one Teacher-controlled episode per env: "
            f"got={len(records)} expected={EXPECTED_EPISODES}"
        )
    table: dict[int, dict[str, Any]] = {}
    for record in records:
        env_id = int(record["env_id"])
        randomized_case = record["randomized_case"]
        case_id = n3_case_id(env_id, randomized_case)
        if env_id in table:
            raise RuntimeError(f"N3 case table contains duplicate env_id={env_id}")
        table[env_id] = {
            "env_id": env_id,
            "case_id": case_id,
            "randomized_case": dict(randomized_case),
        }
    if set(table) != set(range(EXPECTED_NUM_ENVS)):
        raise RuntimeError(
            "N3 case table must cover env_id 0..15 exactly: "
            f"got={sorted(table)}"
        )
    return table


def _n3_dtype_name(dtype: Any) -> str:
    import numpy as np

    normalized = np.dtype(dtype)
    if normalized.kind == "b":
        return "bool"
    if normalized.kind == "S":
        return f"S{normalized.itemsize}"
    return normalized.name


class N3TrajectoryWriter:
    """Stream one N3 dense time×env trajectory into a lossless HDF5 file."""

    def __init__(self, path: Path, *, expected_envs: int = EXPECTED_NUM_ENVS):
        if isinstance(expected_envs, bool) or expected_envs <= 0:
            raise ValueError(f"N3 expected_envs must be positive: {expected_envs!r}")
        self.path = path.expanduser().resolve()
        if self.path.exists():
            raise FileExistsError(f"refusing to overwrite N3 trajectory file: {self.path}")
        self.expected_envs = int(expected_envs)
        self._closed = False
        self._next_frame_ids = [0] * self.expected_envs
        self._done_counts = [0] * self.expected_envs
        self._seen_inactive = [False] * self.expected_envs
        self._rows = 0
        self._active_rows = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        import h5py

        self._file = None
        self._datasets = {}
        try:
            self._file = h5py.File(self.path, "w")
            self._file.attrs["schema"] = N3_DATASET_SCHEMA
            self._file.attrs["expected_envs"] = self.expected_envs
            self._file.attrs["lossless_compression"] = "gzip"
            dtypes = dict(N3_EXPECTED_DATASET_DTYPES)
            shapes = dict(N3_EXPECTED_DATASET_SHAPES)
            for name, shape in shapes.items():
                dtype = dtypes[name]
                if name == "case_id":
                    dtype = "S64"
                chunk_shape = (1, *shape)
                self._datasets[name] = self._file.create_dataset(
                    name,
                    shape=(0, *shape),
                    maxshape=(None, *shape),
                    dtype=dtype,
                    chunks=chunk_shape,
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )
        except BaseException as exc:
            self._closed = True
            if self._file is not None:
                try:
                    self._file.close()
                except BaseException as close_exc:
                    exc.add_note(f"N3 HDF5 constructor cleanup failed: {close_exc!r}")
            raise

    @property
    def next_frame_ids(self) -> tuple[int, ...]:
        return tuple(self._next_frame_ids)

    @property
    def row_count(self) -> int:
        return self._rows

    @property
    def active_row_count(self) -> int:
        return self._active_rows

    def append(self, batch: Mapping[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("N3 trajectory writer is already closed")
        import numpy as np

        required = set(N3_EXPECTED_DATASET_SHAPES)
        missing = sorted(required.difference(batch))
        extra = sorted(set(batch).difference(required))
        if missing or extra:
            raise KeyError(f"N3 trajectory batch keys drifted: missing={missing} extra={extra}")
        arrays = {name: np.asarray(batch[name]) for name in required}
        batch_size = int(arrays["env_id"].shape[0])
        if batch_size != self.expected_envs:
            raise ValueError(
                "N3 dense trajectory batches must contain every environment: "
                f"got={batch_size} expected={self.expected_envs}"
            )
        for name, expected_shape in N3_EXPECTED_DATASET_SHAPES.items():
            expected = (batch_size, *expected_shape)
            if tuple(arrays[name].shape) != expected:
                raise ValueError(
                    f"N3 dataset {name} shape drifted: got={tuple(arrays[name].shape)} "
                    f"expected={expected}"
                )
            expected_dtype = N3_EXPECTED_DATASET_DTYPES[name]
            actual_dtype = _n3_dtype_name(arrays[name].dtype)
            if actual_dtype != expected_dtype:
                raise TypeError(
                    f"N3 dataset {name} dtype drifted: got={actual_dtype} expected={expected_dtype}"
                )
        if not np.array_equal(arrays["env_id"], np.arange(self.expected_envs, dtype=np.int16)):
            raise ValueError("N3 dense batch env_id must be exactly 0..num_envs-1")
        for name in ("actor_obs", "camera_meta", "teacher_action"):
            if not np.isfinite(arrays[name]).all():
                raise ValueError(f"N3 dataset {name} contains non-finite values")
        if not np.isfinite(arrays["camera_meta"]).all():
            raise ValueError("N3 camera_meta contains non-finite values")
        active = arrays["active_mask"]
        done = arrays["done"]
        frame_ids = arrays["frame_id"]
        episode_indices = arrays["episode_index"]
        if np.any(episode_indices != 0):
            raise ValueError("N3 capture only supports episode_index=0 first episodes")
        if np.any(done & ~active):
            raise ValueError("N3 done may only be true for an active pre-action row")
        for env_id in range(self.expected_envs):
            frame_id = int(frame_ids[env_id])
            if bool(active[env_id]):
                if self._seen_inactive[env_id]:
                    raise RuntimeError(
                        f"N3 env {env_id} became active after its first episode completed"
                    )
                if frame_id != self._next_frame_ids[env_id]:
                    raise RuntimeError(
                        f"N3 env {env_id} frame_id is not contiguous: "
                        f"expected={self._next_frame_ids[env_id]} got={frame_id}"
                    )
                self._next_frame_ids[env_id] += 1
                self._active_rows += 1
                if bool(done[env_id]):
                    self._done_counts[env_id] += 1
                    if self._done_counts[env_id] > 1:
                        raise RuntimeError(f"N3 env {env_id} has more than one terminal done")
                    self._seen_inactive[env_id] = True
            else:
                if frame_id != self._next_frame_ids[env_id]:
                    raise RuntimeError(
                        f"N3 inactive env {env_id} frame_id drifted: "
                        f"expected={self._next_frame_ids[env_id]} got={frame_id}"
                    )
                self._seen_inactive[env_id] = True
        start = self._rows
        stop = start + batch_size
        for dataset in self._datasets.values():
            dataset.resize((stop, *dataset.shape[1:]))
        for name, array in arrays.items():
            self._datasets[name][start:stop] = array
        self._rows = stop
        self._file.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        flush_error = None
        try:
            self._file.flush()
        except BaseException as exc:
            flush_error = exc
        try:
            self._file.close()
        except BaseException as close_exc:
            if flush_error is None:
                raise
            flush_error.add_note(f"N3 HDF5 close cleanup failed: {close_exc!r}")
        if flush_error is not None:
            raise flush_error

    def finalize(self, case_table: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
        self.close()
        if set(case_table) != set(range(self.expected_envs)):
            raise RuntimeError(
                "N3 case table does not cover the writer environment set: "
                f"expected={list(range(self.expected_envs))} got={sorted(case_table)}"
            )
        import h5py
        import numpy as np

        with h5py.File(self.path, "r+") as stream:
            case_ids = stream["case_id"]
            env_ids = stream["env_id"]
            for start in range(0, self._rows, 4096):
                stop = min(start + 4096, self._rows)
                env_chunk = np.asarray(env_ids[start:stop])
                case_ids[start:stop] = np.asarray(
                    [str(case_table[int(env_id)]["case_id"]).encode("ascii") for env_id in env_chunk],
                    dtype="S64",
                )
            stream.attrs["row_count"] = self._rows
            stream.attrs["active_frame_count"] = self._active_rows
            stream.attrs["episode_count"] = self.expected_envs
            stream.attrs["case_table_sha256"] = sha256_json(case_table)
        return _n3_hdf5_metadata_summary(
            self.path,
            expected_envs=self.expected_envs,
            row_count=self._rows,
            active_frame_count=self._active_rows,
        )


def _n3_hdf5_metadata_summary(
    path: Path,
    *,
    expected_envs: int,
    row_count: int,
    active_frame_count: int,
) -> dict[str, Any]:
    """Return bounded metadata without replacing the authoritative validator."""
    import h5py

    path = path.expanduser().resolve(strict=True)
    with h5py.File(path, "r") as stream:
        if stream.attrs.get("schema") != N3_DATASET_SCHEMA:
            raise RuntimeError("N3 HDF5 schema identity drift")
        if int(stream.attrs.get("expected_envs", -1)) != expected_envs:
            raise RuntimeError("N3 HDF5 expected_envs identity drift")
        return {
            "schema": N3_DATASET_SCHEMA,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "row_count": row_count,
            "active_frame_count": active_frame_count,
            "episode_count": expected_envs,
            "dataset_shapes": {
                name: [row_count, *shape] for name, shape in N3_EXPECTED_DATASET_SHAPES.items()
            },
            "dataset_dtypes": dict(N3_EXPECTED_DATASET_DTYPES),
        }


def validate_n3_hdf5(
    path: Path,
    case_table: Mapping[int, Mapping[str, Any]],
    *,
    expected_envs: int = EXPECTED_NUM_ENVS,
) -> dict[str, Any]:
    """Validate N3 HDF5 schema, finite values, frame continuity, and terminals."""
    import h5py
    import numpy as np

    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise FileNotFoundError(f"N3 trajectory file is not regular: {path}")
    if set(case_table) != set(range(expected_envs)):
        raise ValueError("N3 HDF5 validation requires a complete case table")
    with h5py.File(path, "r") as stream:
        if stream.attrs.get("schema") != N3_DATASET_SCHEMA:
            raise RuntimeError("N3 HDF5 schema identity drift")
        if int(stream.attrs.get("expected_envs", -1)) != expected_envs:
            raise RuntimeError("N3 HDF5 expected_envs identity drift")
        if stream.attrs.get("lossless_compression") != "gzip":
            raise RuntimeError("N3 HDF5 must use gzip lossless compression")
        missing = sorted(set(N3_EXPECTED_DATASET_SHAPES).difference(stream.keys()))
        if missing:
            raise KeyError(f"N3 HDF5 is missing datasets: {missing}")
        row_count = int(stream["env_id"].shape[0])
        if row_count <= 0:
            raise RuntimeError("N3 HDF5 contains no trajectory rows")
        if int(stream.attrs.get("row_count", -1)) != row_count:
            raise RuntimeError("N3 HDF5 row_count attribute drift")
        if int(stream.attrs.get("episode_count", -1)) != expected_envs:
            raise RuntimeError("N3 HDF5 episode_count attribute drift")
        if stream.attrs.get("case_table_sha256") != sha256_json(case_table):
            raise RuntimeError("N3 HDF5 case-table provenance drift")
        for name, shape in N3_EXPECTED_DATASET_SHAPES.items():
            dataset = stream[name]
            if tuple(dataset.shape) != (row_count, *shape):
                raise RuntimeError(
                    f"N3 HDF5 dataset {name} shape drift: got={tuple(dataset.shape)} "
                    f"expected={(row_count, *shape)}"
                )
            actual_dtype = _n3_dtype_name(dataset.dtype)
            if actual_dtype != N3_EXPECTED_DATASET_DTYPES[name]:
                raise RuntimeError(
                    f"N3 HDF5 dataset {name} dtype drift: got={actual_dtype} "
                    f"expected={N3_EXPECTED_DATASET_DTYPES[name]}"
                )
            if dataset.compression != "gzip":
                raise RuntimeError(f"N3 HDF5 dataset {name} must use gzip compression")
        next_frame = [0] * expected_envs
        done_counts = [0] * expected_envs
        seen_inactive = [False] * expected_envs
        active_frames = 0
        validation_fields = (
            "actor_obs",
            "camera_meta",
            "teacher_action",
            "episode_index",
            "done",
            "active_mask",
            "env_id",
            "frame_id",
            "case_id",
        )
        for start in range(0, row_count, N3_VALIDATION_ROW_CHUNK):
            stop = min(start + N3_VALIDATION_ROW_CHUNK, row_count)
            arrays = {
                name: np.asarray(stream[name][start:stop]) for name in validation_fields
            }
            for image_name in ("left_rgb", "right_rgb", "head_rgb"):
                image_chunk = np.asarray(stream[image_name][start:stop])
                expected_image_shape = (
                    stop - start,
                    *N3_EXPECTED_DATASET_SHAPES[image_name],
                )
                if tuple(image_chunk.shape) != expected_image_shape:
                    raise RuntimeError(
                        f"N3 HDF5 image chunk shape drift for {image_name}: "
                        f"got={tuple(image_chunk.shape)} expected={expected_image_shape}"
                    )
                if _n3_dtype_name(image_chunk.dtype) != "uint8":
                    raise RuntimeError(f"N3 HDF5 image chunk dtype drift for {image_name}")
            env_ids = arrays["env_id"]
            expected_env_ids = np.asarray(
                [(start + offset) % expected_envs for offset in range(stop - start)],
                dtype=np.int16,
            )
            if not np.array_equal(env_ids, expected_env_ids):
                raise RuntimeError("N3 HDF5 rows must remain dense env-major time order")
            for name in ("actor_obs", "camera_meta", "teacher_action"):
                if not np.isfinite(arrays[name]).all():
                    raise RuntimeError(f"N3 HDF5 dataset {name} contains non-finite values")
            if np.any(arrays["episode_index"] != 0):
                raise RuntimeError("N3 HDF5 episode_index must be zero for every row")
            active = arrays["active_mask"]
            done = arrays["done"]
            frames = arrays["frame_id"]
            case_ids = arrays["case_id"]
            if np.any(done & ~active):
                raise RuntimeError("N3 HDF5 done rows must be active")
            for row in range(active.shape[0]):
                env_id = int(env_ids[row])
                frame_id = int(frames[row])
                if bool(active[row]):
                    if seen_inactive[env_id] or frame_id != next_frame[env_id]:
                        raise RuntimeError(f"N3 HDF5 frame_id is not contiguous for env {env_id}")
                    next_frame[env_id] += 1
                    active_frames += 1
                    if bool(done[row]):
                        done_counts[env_id] += 1
                        if done_counts[env_id] > 1:
                            raise RuntimeError(f"N3 HDF5 env {env_id} has multiple done rows")
                        seen_inactive[env_id] = True
                elif frame_id != next_frame[env_id]:
                    raise RuntimeError(f"N3 HDF5 inactive frame_id drift for env {env_id}")
                expected_case = str(case_table[env_id]["case_id"]).encode("ascii")
                if bytes(case_ids[row]).rstrip(b"\x00") != expected_case:
                    raise RuntimeError(f"N3 HDF5 case_id mismatch for env {env_id}")
        if done_counts != [1] * expected_envs:
            raise RuntimeError(f"N3 HDF5 must contain exactly one done per env: {done_counts}")
        if not all(seen_inactive):
            raise RuntimeError("N3 HDF5 has an env without a completed first episode")
        if int(stream.attrs.get("active_frame_count", -1)) != active_frames:
            raise RuntimeError("N3 HDF5 active_frame_count attribute drift")
        summary = {
            "schema": N3_DATASET_SCHEMA,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "row_count": row_count,
            "active_frame_count": active_frames,
            "episode_count": expected_envs,
            "dataset_shapes": {
                name: [row_count, *shape] for name, shape in N3_EXPECTED_DATASET_SHAPES.items()
            },
            "dataset_dtypes": dict(N3_EXPECTED_DATASET_DTYPES),
        }
        return summary


def json_safe(value: Any) -> Any:
    """Convert runtime metric containers without importing torch or numpy."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return json_safe(tolist())
    item = getattr(value, "item", None)
    if callable(item):
        return json_safe(item())
    raise TypeError(f"metric value is not JSON serializable: {type(value).__name__}")


def _checkpoint_step_from_name(checkpoint: Path) -> int:
    match = re.fullmatch(r"model_step_(\d+)\.pt", checkpoint.name)
    if match is None:
        raise ValueError(
            "checkpoint filename must be exactly model_step_<global_step>.pt: "
            f"{checkpoint.name!r}"
        )
    return int(match.group(1))


@lru_cache(maxsize=32)
def _load_checkpoint_policy_contract(
    checkpoint: str, expected_global_step: int, checkpoint_sha256: str
) -> dict[str, int]:
    """Load one checkpoint on CPU and validate its policy tensor contract.

    This is intentionally strict and cached by the content hash.  The formal
    wrapper must expose a missing/corrupt/non-finite checkpoint before Hydra or
    IsaacLab imports begin; it must not silently evaluate another step.
    """
    import torch

    path = Path(checkpoint).resolve(strict=True)
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except BaseException as exc:
        raise RuntimeError(f"failed to load checkpoint on CPU: {path}") from exc
    if not isinstance(payload, Mapping):
        raise TypeError(f"checkpoint payload must be a mapping: {path}")
    policy = payload.get("policy_state_dict")
    if not isinstance(policy, Mapping) or not policy:
        raise KeyError(f"checkpoint is missing a non-empty policy_state_dict: {path}")
    tensor_count = 0
    for name, tensor in policy.items():
        if not torch.is_tensor(tensor):
            raise TypeError(f"policy tensor {name!r} is not a torch.Tensor")
        tensor_count += 1
        if (tensor.is_floating_point() or tensor.is_complex()) and not bool(
            torch.all(torch.isfinite(tensor)).item()
        ):
            raise RuntimeError(f"policy tensor {name!r} contains non-finite values")
    state = payload.get("state")
    global_step = getattr(state, "global_step", None)
    if global_step is None and isinstance(state, Mapping):
        global_step = state.get("global_step")
    if isinstance(global_step, bool) or not isinstance(global_step, int):
        raise RuntimeError(
            f"checkpoint state.global_step is missing or non-integer: {path}"
        )
    if global_step != expected_global_step:
        raise RuntimeError(
            f"checkpoint state.global_step mismatch: expected {expected_global_step}, "
            f"got {global_step} ({path})"
        )
    return {"policy_tensor_count": tensor_count, "global_step": global_step}


def validate_checkpoint_artifacts(
    checkpoint: Path | None = None,
    config_path: Path | None = None,
    *,
    controller: str = "student",
    expected_global_step: int | None = None,
    expected_sha256: str | None = None,
    expected_config_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate a Student or Teacher checkpoint before any runtime imports.

    The default invocation preserves the historical v19 step10000 Student
    command.  Arbitrary Student paths are accepted only with an explicit
    expected global step; their SHA256 is derived when the caller does not
    supply one.  Teacher evaluation remains pinned to the sealed G2 step2000
    checkpoint/config pair.
    """
    if controller not in CONTROLLERS:
        raise ValueError(f"unknown controller {controller!r}; expected {CONTROLLERS}")
    default_checkpoint = CHECKPOINT if controller == "student" else TEACHER_CHECKPOINT
    checkpoint = default_checkpoint if checkpoint is None else checkpoint
    checkpoint = checkpoint.expanduser().resolve(strict=True)
    default_config = CHECKPOINT_CONFIG if controller == "student" else TEACHER_CONFIG
    config_path = default_config if config_path is None else config_path
    config_path = config_path.expanduser().resolve(strict=True)
    if controller == "teacher":
        if checkpoint != TEACHER_CHECKPOINT:
            raise ValueError(
                "Teacher evaluation is pinned to the exact G2 step2000 checkpoint: "
                f"{TEACHER_CHECKPOINT}; got {checkpoint}"
            )
        if config_path != TEACHER_CONFIG:
            raise ValueError(
                "Teacher evaluation requires the adjacent G2 config.yaml: "
                f"{TEACHER_CONFIG}; got {config_path}"
            )
    elif checkpoint == CHECKPOINT and config_path != CHECKPOINT_CONFIG:
        raise ValueError(
            f"default v19 Student checkpoint requires {CHECKPOINT_CONFIG}; got {config_path}"
        )
    if expected_global_step is None:
        if controller == "student" and checkpoint != CHECKPOINT:
            raise ValueError(
                "arbitrary Student checkpoint validation requires expected_global_step"
            )
        expected_global_step = (
            STUDENT_GLOBAL_STEP if controller == "student" else TEACHER_GLOBAL_STEP
        )
    if isinstance(expected_global_step, bool) or expected_global_step <= 0:
        raise ValueError(f"expected_global_step must be a positive integer: {expected_global_step!r}")
    filename_step = _checkpoint_step_from_name(checkpoint)
    if filename_step != expected_global_step:
        raise ValueError(
            f"checkpoint filename/global_step mismatch: expected {expected_global_step}, "
            f"filename encodes {filename_step} ({checkpoint})"
        )
    checkpoint_sha = sha256_file(checkpoint)
    if expected_sha256 is not None and checkpoint_sha != expected_sha256:
        raise RuntimeError(
            f"checkpoint SHA256 mismatch: expected {expected_sha256}, got {checkpoint_sha}"
        )
    if controller == "student" and checkpoint == CHECKPOINT and checkpoint_sha != CHECKPOINT_SHA256:
        raise RuntimeError(
            f"Student checkpoint SHA256 drift: expected {CHECKPOINT_SHA256}, got {checkpoint_sha}"
        )
    if controller == "teacher" and checkpoint_sha != TEACHER_CHECKPOINT_SHA256:
        raise RuntimeError(
            f"Teacher checkpoint SHA256 drift: expected {TEACHER_CHECKPOINT_SHA256}, got {checkpoint_sha}"
        )
    config_sha = sha256_file(config_path)
    if expected_config_sha256 is not None and config_sha != expected_config_sha256:
        raise RuntimeError(
            f"checkpoint config SHA256 mismatch: expected {expected_config_sha256}, got {config_sha}"
        )
    if controller == "student" and config_path == CHECKPOINT_CONFIG and config_sha != CHECKPOINT_CONFIG_SHA256:
        raise RuntimeError(
            f"Student config SHA256 drift: expected {CHECKPOINT_CONFIG_SHA256}, got {config_sha}"
        )
    if controller == "teacher" and config_sha != TEACHER_CONFIG_SHA256:
        raise RuntimeError(
            f"Teacher config SHA256 drift: expected {TEACHER_CONFIG_SHA256}, got {config_sha}"
        )
    loaded = _load_checkpoint_policy_contract(str(checkpoint), expected_global_step, checkpoint_sha)
    return {
        "path": str(checkpoint),
        "sha256": checkpoint_sha,
        "config_path": str(config_path),
        "config_sha256": config_sha,
        "global_step": expected_global_step,
        "controller": controller,
        **loaded,
    }


def validate_teacher_identity(runtime: Any | None = None) -> dict[str, Any]:
    """Validate and return the immutable G2/c18 Teacher provenance bundle."""
    teacher_checkpoint = validate_checkpoint_artifacts(controller="teacher")
    manifest_path = TEACHER_MANIFEST.expanduser().resolve(strict=True)
    manifest_sha = sha256_file(manifest_path)
    if manifest_sha != TEACHER_MANIFEST_SHA256:
        raise RuntimeError(
            f"Teacher manifest SHA256 drift: expected {TEACHER_MANIFEST_SHA256}, got {manifest_sha}"
        )
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    checkpoint_manifest = manifest.get("checkpoint")
    source_manifest = manifest.get("source")
    if not isinstance(checkpoint_manifest, Mapping) or not isinstance(source_manifest, Mapping):
        raise ValueError("Teacher manifest must contain checkpoint and source mappings")
    if checkpoint_manifest.get("filename") != TEACHER_CHECKPOINT.name:
        raise ValueError("Teacher manifest checkpoint filename drift")
    if checkpoint_manifest.get("sha256") != TEACHER_CHECKPOINT_SHA256:
        raise ValueError("Teacher manifest checkpoint SHA256 drift")
    if source_manifest.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise ValueError(
            "Teacher manifest runtime commit drift: "
            f"expected {EXPECTED_RUNTIME_COMMIT}, got {source_manifest.get('commit')!r}"
        )
    if source_manifest.get("config_sha256") != TEACHER_CONFIG_SHA256:
        raise ValueError("Teacher manifest config SHA256 drift")
    if runtime is not None:
        runtime_result = runtime.validate_teacher_triplet(
            TEACHER_CHECKPOINT, TEACHER_CONFIG, manifest_path
        )
        if not isinstance(runtime_result, Mapping):
            raise TypeError("runtime Teacher validator must return a mapping")
    return {
        "checkpoint": teacher_checkpoint,
        "manifest": {"path": str(manifest_path), "sha256": manifest_sha},
        "runtime_commit": EXPECTED_RUNTIME_COMMIT,
        "runtime_label": "USER_APPROVED_C18_RECONSTRUCTION",
    }


def expected_trainer_target(controller: str) -> str:
    if controller == "student":
        return STUDENT_TRAINER_TARGET
    if controller == "teacher":
        return TEACHER_TRAINER_TARGET
    raise ValueError(f"unknown controller {controller!r}; expected {CONTROLLERS}")


def resolve_trainer_target(config_path: Path) -> str:
    """Resolve the adjacent saved config's trainer target without Hydra imports."""
    import yaml

    config_path = config_path.expanduser().resolve(strict=True)
    with config_path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, Mapping):
        raise TypeError(f"saved checkpoint config must be a mapping: {config_path}")
    trainer = config.get("trainer")
    if not isinstance(trainer, Mapping) or not isinstance(trainer.get("_target_"), str):
        raise RuntimeError(f"saved checkpoint config has no trainer._target_: {config_path}")
    return trainer["_target_"]


def validate_trainer_target(config_path: Path, controller: str) -> str:
    target = resolve_trainer_target(config_path)
    expected = expected_trainer_target(controller)
    if target != expected:
        raise RuntimeError(
            f"{controller} trainer target mismatch: expected {expected}, got {target}"
        )
    return target


def load_runtime_bootstrap_module():
    """Load the v19 bootstrap from this worktree before any ``gr00t`` import."""
    source_path = RUNTIME_BOOTSTRAP_PATH.expanduser().resolve(strict=True)
    expected_path = (
        REPO_ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v19.py"
    ).resolve(strict=True)
    if source_path != expected_path:
        raise RuntimeError(
            "v19 runtime bootstrap source identity mismatch: "
            f"source={source_path} expected={expected_path}"
        )
    preloaded_gr00t = sorted(
        name for name in sys.modules if name == "gr00t" or name.startswith("gr00t.")
    )
    if preloaded_gr00t:
        raise RuntimeError(
            "v19 runtime bootstrap must load before any gr00t package import: "
            f"preloaded={preloaded_gr00t}"
        )
    if RUNTIME_BOOTSTRAP_MODULE_NAME in sys.modules:
        raise RuntimeError(
            f"v19 runtime bootstrap module is already loaded: {RUNTIME_BOOTSTRAP_MODULE_NAME}"
        )
    spec = importlib.util.spec_from_file_location(
        RUNTIME_BOOTSTRAP_MODULE_NAME,
        source_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load v19 runtime bootstrap: {source_path}")
    if spec.origin is None or Path(spec.origin).resolve(strict=True) != source_path:
        raise RuntimeError(
            "v19 runtime bootstrap spec source identity mismatch: "
            f"origin={spec.origin!r} expected={source_path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[RUNTIME_BOOTSTRAP_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
        loaded_path = Path(getattr(module, "__file__", "")).expanduser().resolve(strict=True)
        if loaded_path != source_path:
            raise RuntimeError(
                "v19 runtime bootstrap loaded from an unexpected source: "
                f"loaded={loaded_path} expected={source_path}"
            )
        if getattr(module, "EXPECTED_RUNTIME_COMMIT", None) != EXPECTED_RUNTIME_COMMIT:
            raise RuntimeError(
                "v19 runtime bootstrap commit identity mismatch: "
                f"module={getattr(module, 'EXPECTED_RUNTIME_COMMIT', None)!r} "
                f"expected={EXPECTED_RUNTIME_COMMIT!r}"
            )
        return module
    except BaseException:
        if sys.modules.get(RUNTIME_BOOTSTRAP_MODULE_NAME) is module:
            del sys.modules[RUNTIME_BOOTSTRAP_MODULE_NAME]
        raise


def controller_contract(controller: str) -> dict[str, Any]:
    if controller not in CONTROLLERS:
        raise ValueError(f"unknown controller {controller!r}; expected {CONTROLLERS}")
    return {
        "controller": controller,
        "enforce_teacher_rollout": controller == "teacher",
        "ratio_teacher_rollout": 1.0 if controller == "teacher" else 0.0,
        "pure_student": controller == "student",
    }


def build_hydra_overrides(
    mode: str,
    output_root: Path,
    checkpoint: Path | None = None,
    *,
    controller: str = "student",
    student_d435i_forward_mode: str | None = None,
) -> list[str]:
    """Build one explicit v19 Student or Teacher formal-eval contract."""
    if mode not in {"formal", "render", N3_CAPTURE_MODE}:
        raise ValueError(f"unknown eval mode {mode!r}")
    if mode == N3_CAPTURE_MODE and controller != N3_PASSIVE_CONTROLLER:
        raise ValueError("N3 capture is only defined with the passive Student controller")
    contract = controller_contract(controller)
    if mode == N3_CAPTURE_MODE:
        contract = {
            **contract,
            "enforce_teacher_rollout": True,
            "ratio_teacher_rollout": 1.0,
        }
    if mode == "render" and controller != "student":
        raise ValueError("selected render is only defined for the Student controller")
    if student_d435i_forward_mode is not None:
        if controller != "student":
            raise ValueError(
                "student_d435i_forward_mode is only defined for the Student controller"
            )
        if mode != "formal":
            raise ValueError(
                "student_d435i_forward_mode is only defined for formal Student eval"
            )
        if student_d435i_forward_mode not in STUDENT_D435I_FORWARD_MODES:
            raise ValueError(
                "student_d435i_forward_mode must be exactly one of "
                f"{STUDENT_D435I_FORWARD_MODES}; got {student_d435i_forward_mode!r}"
            )
    effective_student_d435i_forward_mode = (
        "sequential" if student_d435i_forward_mode is None else student_d435i_forward_mode
    )
    if checkpoint is None:
        checkpoint = CHECKPOINT if controller == "student" else TEACHER_CHECKPOINT
    checkpoint = checkpoint.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    render = mode == "render"
    bundle_root = render_staging_root(output_root) if render else output_root
    external_root = bundle_root / "external_debug_videos"
    runtime_log_root = eval_runtime_log_root(mode, output_root)
    overrides = [
        f"checkpoint={checkpoint.resolve()}",
        "+seed=0",
        "+num_envs=16",
        "+headless=true",
        "+use_wandb=false",
        "+algo.config.enforce_teacher_rollout=" + str(contract["enforce_teacher_rollout"]).lower(),
        "+algo.config.ratio_teacher_rollout=" + str(contract["ratio_teacher_rollout"]),
        "+algo.config.use_a2_base=true",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "algo.config.eval.num_eval_episodes=16",
        "+simulator.config.render_results=" + ("true" if render else "false"),
        f"eval_output_dir={bundle_root}",
        f"eval_log_dir={runtime_log_root}",
    ]
    if render:
        overrides.append(f"env.config.save_rendering_dir={external_root}")
    _require_one_override(overrides, "seed", "0")
    _require_one_override(overrides, "num_envs", "16")
    _require_one_override(
        overrides,
        "algo.config.enforce_teacher_rollout",
        str(contract["enforce_teacher_rollout"]).lower(),
    )
    _require_one_override(
        overrides,
        "algo.config.ratio_teacher_rollout",
        str(contract["ratio_teacher_rollout"]),
    )
    if controller == "student":
        overrides.insert(
            9,
            "+algo.config.actor.view_contract.d435i_forward_mode="
            f"{effective_student_d435i_forward_mode}",
        )
        _require_one_override(
            overrides,
            "algo.config.actor.view_contract.d435i_forward_mode",
            effective_student_d435i_forward_mode,
        )
    _require_one_override(overrides, "algo.config.eval.eval_num_envs_episodes", "true")
    _require_one_override(overrides, "algo.config.eval.num_eval_episodes", "16")
    _require_one_override(overrides, "eval_output_dir", str(bundle_root))
    _require_one_override(overrides, "eval_log_dir", str(runtime_log_root))
    return overrides


def _require_one_override(overrides: Sequence[str], key: str, expected: str) -> None:
    matches = []
    for argument in overrides:
        normalized = argument[1:] if argument.startswith("+") else argument
        if normalized.startswith(f"{key}="):
            matches.append(normalized.split("=", 1)[1])
    if matches != [expected]:
        raise ValueError(f"expected exactly one {key}={expected} override; got {matches!r}")


def validate_controller_contract(config: Mapping[str, Any], controller: str) -> None:
    """Validate the effective trainer/env contract at runtime, fail-fast."""
    contract = controller_contract(controller)
    if config.get("enforce_teacher_rollout") is not contract["enforce_teacher_rollout"]:
        raise RuntimeError(
            f"{controller} eval requires enforce_teacher_rollout="
            f"{contract['enforce_teacher_rollout']}"
        )
    if float(config.get("ratio_teacher_rollout", -1.0)) != contract["ratio_teacher_rollout"]:
        raise RuntimeError(
            f"{controller} eval requires ratio_teacher_rollout="
            f"{contract['ratio_teacher_rollout']}"
        )
    if config.get("use_a2_base") is not True:
        raise RuntimeError(f"{controller} eval requires the frozen A2_Base leg controller")
    eval_config = config.get("eval", {})
    if not isinstance(eval_config, Mapping):
        raise TypeError("Student eval config.eval must be a mapping")
    if eval_config.get("eval_num_envs_episodes") is not True:
        raise RuntimeError(f"{controller} eval requires exactly one first episode per env")
    if int(eval_config.get("num_eval_episodes", EXPECTED_EPISODES)) != EXPECTED_EPISODES:
        raise RuntimeError(f"{controller} eval requires num_eval_episodes=16")


def validate_student_forward_mode_contract(
    config: Mapping[str, Any], policy_model: Any, expected_mode: str
) -> None:
    """Require Hydra's effective actor mode and the instantiated policy mode to agree."""
    if expected_mode not in STUDENT_D435I_FORWARD_MODES:
        raise ValueError(
            "expected Student D435 mode must be exactly one of "
            f"{STUDENT_D435I_FORWARD_MODES}; got {expected_mode!r}"
        )
    actor_config = config.get("actor")
    if not isinstance(actor_config, Mapping):
        raise RuntimeError("formal Student config is missing algo.config.actor")
    view_contract = actor_config.get("view_contract")
    if not isinstance(view_contract, Mapping):
        raise RuntimeError("formal Student config is missing actor.view_contract")
    config_mode = view_contract.get("d435i_forward_mode")
    if config_mode != expected_mode:
        raise RuntimeError(
            "formal Student effective Hydra D435 mode mismatch: "
            f"expected={expected_mode!r} got={config_mode!r}"
        )
    policy_mode = getattr(policy_model, "d435i_forward_mode", None)
    if policy_mode != expected_mode:
        raise RuntimeError(
            "formal Student instantiated policy D435 mode mismatch: "
            f"expected={expected_mode!r} got={policy_mode!r}"
        )


def validate_n3_capture_contract(
    config: Mapping[str, Any],
    passive_student_info: Mapping[str, Any],
    teacher_info: Mapping[str, Any],
    experience_info: Mapping[str, Any],
) -> None:
    """Validate passive Student reconstruction plus exact Teacher control."""
    if passive_student_info.get("controller") != N3_PASSIVE_CONTROLLER:
        raise RuntimeError("N3 passive checkpoint must be identified as controller=student")
    if passive_student_info.get("path") != str(CHECKPOINT):
        raise RuntimeError("N3 passive Student checkpoint is not the exact step10000 source")
    if passive_student_info.get("sha256") != CHECKPOINT_SHA256:
        raise RuntimeError("N3 passive Student checkpoint SHA256 drifted")
    if passive_student_info.get("global_step") != STUDENT_GLOBAL_STEP:
        raise RuntimeError("N3 passive Student global_step must be exactly 10000")
    if experience_info.get("controller") != N3_PASSIVE_CONTROLLER:
        raise RuntimeError("N3 experience controller must identify the passive Student source")
    if experience_info.get("camera_mode") != EXPERIENCE_CAMERA_MODES[N3_PASSIVE_CONTROLLER]:
        raise RuntimeError("N3 requires the camera-enabled Student experience")
    if teacher_info.get("runtime_commit") != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError("N3 Teacher runtime commit identity drifted")
    if teacher_info.get("checkpoint", {}).get("controller") != N3_CONTROL_CONTROLLER:
        raise RuntimeError("N3 Teacher identity must remain the control source")
    if config.get("enforce_teacher_rollout") is not True:
        raise RuntimeError("N3 requires enforce_teacher_rollout=true")
    if float(config.get("ratio_teacher_rollout", -1.0)) != 1.0:
        raise RuntimeError("N3 requires ratio_teacher_rollout=1.0")
    if config.get("use_a2_base") is not True:
        raise RuntimeError("N3 requires the frozen A2_Base leg controller")
    eval_config = config.get("eval", {})
    if not isinstance(eval_config, Mapping):
        raise TypeError("N3 eval config.eval must be a mapping")
    if eval_config.get("eval_num_envs_episodes") is not True:
        raise RuntimeError("N3 requires exactly one first episode per environment")
    if int(eval_config.get("num_eval_episodes", EXPECTED_EPISODES)) != EXPECTED_EPISODES:
        raise RuntimeError("N3 requires num_eval_episodes=16")


def validate_n3_teacher_config(config_path: Path, teacher_info: Mapping[str, Any]) -> None:
    """Ensure the passive Student config embeds the exact Teacher triplet."""
    import yaml

    config_path = config_path.expanduser().resolve(strict=True)
    with config_path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, Mapping):
        raise TypeError(f"N3 passive Student config must be a mapping: {config_path}")
    expected = {
        "teacher_actor_path": teacher_info["checkpoint"]["path"],
        "teacher_config_path": teacher_info["checkpoint"]["config_path"],
        "teacher_manifest_path": teacher_info["manifest"]["path"],
    }
    for key, expected_path in expected.items():
        actual = config.get(key)
        if not isinstance(actual, str) or str(Path(actual).expanduser().resolve()) != str(
            Path(expected_path).expanduser().resolve()
        ):
            raise RuntimeError(
                f"N3 Student config Teacher triplet drift for {key}: "
                f"expected={expected_path!r} got={actual!r}"
            )


def validate_n3_cli_teacher_identity(args: argparse.Namespace, teacher_info: Mapping[str, Any]) -> None:
    """Require every N3 subprocess flag to match the sealed Teacher triplet."""
    if getattr(args, "n3_control_controller", None) != N3_CONTROL_CONTROLLER:
        raise RuntimeError("N3 control controller must be Teacher")
    checkpoint = teacher_info["checkpoint"]
    manifest = teacher_info["manifest"]
    expected = {
        "n3_teacher_checkpoint": (Path(checkpoint["path"]).expanduser().resolve(), Path),
        "n3_teacher_sha256": (str(checkpoint["sha256"]), str),
        "n3_teacher_config": (Path(checkpoint["config_path"]).expanduser().resolve(), Path),
        "n3_teacher_config_sha256": (str(checkpoint["config_sha256"]), str),
        "n3_teacher_manifest": (Path(manifest["path"]).expanduser().resolve(), Path),
        "n3_teacher_manifest_sha256": (str(manifest["sha256"]), str),
    }
    for name, (expected_value, value_type) in expected.items():
        supplied = getattr(args, name, None)
        if value_type is Path:
            actual = None if supplied is None else Path(supplied).expanduser().resolve()
        else:
            actual = None if supplied is None else str(supplied)
        if actual != expected_value:
            raise RuntimeError(
                f"N3 Teacher identity flag drift for {name}: "
                f"expected={expected_value!r} got={actual!r}"
            )


def _n3_artifact_manifest(staging_root: Path, final_root: Path) -> list[dict[str, Any]]:
    artifacts = []
    for path in sorted(path for path in staging_root.rglob("*") if path.is_file()):
        artifacts.append(
            {
                "path": str(final_root / path.relative_to(staging_root)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return artifacts


def seal_n3_capture_bundle(
    *,
    staging_root: Path,
    output_root: Path,
    metrics: Mapping[str, Any],
    passive_student_info: Mapping[str, Any],
    teacher_info: Mapping[str, Any],
    experience_info: Mapping[str, Any],
    replicate_id: str,
    case_seed: int = EXPECTED_SEED,
) -> dict[str, Any]:
    """Seal Teacher-controlled metrics, HDF5 provenance, and one N3 manifest."""
    if case_seed != EXPECTED_SEED:
        raise ValueError(f"N3 case seed must be exactly {EXPECTED_SEED}")
    staging_root = staging_root.expanduser().resolve(strict=True)
    output_root = output_root.expanduser().resolve()
    dataset_path = staging_root / N3_DATASET_FILENAME
    case_table = n3_case_table_from_metrics(metrics)
    dataset_summary = validate_n3_hdf5(dataset_path, case_table)
    records = episode_records(json_safe(metrics))
    ranked = rank_episode_records(records)
    safe_passive = json_safe(passive_student_info)
    safe_teacher = json_safe(teacher_info)
    safe_experience = json_safe(experience_info)
    control_identity = {
        "controller": N3_CONTROL_CONTROLLER,
        "high_level_action_dim": 12,
        "high_level_action_source": "Teacher12D",
        "teacher_rollout_enforced": True,
        "teacher_rollout_ratio": 1.0,
        "policy_quality_evidence": False,
    }
    common = {
        "case_seed": case_seed,
        "replicate_id": replicate_id,
        "controller": N3_CONTROL_CONTROLLER,
        "control_identity": control_identity,
        "passive_student": safe_passive,
        "teacher": safe_teacher,
        "experience": safe_experience,
        "runtime": {
            "commit": EXPECTED_RUNTIME_COMMIT,
            "label": "USER_APPROVED_C18_RECONSTRUCTION",
        },
        "training_performed": False,
        "optimizer_step_count": 0,
        "backward_call_count": 0,
        "case_table": [case_table[env_id] for env_id in sorted(case_table)],
        "episodes": records,
    }
    metrics_path = staging_root / N3_METRICS_FILENAME
    source_metrics = {
        "schema": N3_METRICS_SCHEMA,
        **common,
        "dataset": {
            **dataset_summary,
            "path": str(output_root / N3_DATASET_FILENAME),
        },
    }
    atomic_json_write(metrics_path, source_metrics)
    selection_path = staging_root / N3_SELECTION_FILENAME
    selected = ranked[0]
    selection = {
        "schema": N3_SELECTION_SCHEMA,
        **common,
        "ranking": {"order": FORMAL_RANKING_ORDER, "records": ranked},
        "selected": {
            "env_id": selected["env_id"],
            "episode_index": selected["episode_index"],
            "reward": selected["reward"],
            "goal_reached": selected["goal_reached"],
            "max_stage": selected["max_stage"],
            "terminal_reason": selected["terminal_reason"],
            "randomized_case": selected["randomized_case"],
        },
        "source_metrics": {
            "path": str(output_root / N3_METRICS_FILENAME),
            "sha256": sha256_file(metrics_path),
        },
    }
    atomic_json_write(selection_path, selection)
    manifest_path = staging_root / N3_MANIFEST_FILENAME
    manifest = {
        "schema": N3_MANIFEST_SCHEMA,
        **common,
        "dataset": {
            **dataset_summary,
            "path": str(output_root / N3_DATASET_FILENAME),
        },
        "metrics": {
            "path": str(output_root / N3_METRICS_FILENAME),
            "sha256": sha256_file(metrics_path),
        },
        "selection": {
            "path": str(output_root / N3_SELECTION_FILENAME),
            "sha256": sha256_file(selection_path),
        },
        "artifacts": _n3_artifact_manifest(staging_root, output_root),
    }
    atomic_json_write(manifest_path, manifest)
    return manifest


def load_n3_capture_bundle(output_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and hash-validate a completed N3 replicate bundle."""
    output_root = output_root.expanduser().resolve(strict=True)
    manifest_path = n3_manifest_path(output_root).resolve(strict=True)
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("schema") != N3_MANIFEST_SCHEMA:
        raise ValueError("unsupported N3 manifest schema")
    if manifest.get("controller") != N3_CONTROL_CONTROLLER:
        raise ValueError("N3 manifest controller must be Teacher")
    artifact_entries = manifest.get("artifacts")
    if not isinstance(artifact_entries, list):
        raise KeyError("N3 manifest is missing artifact hash list")
    if any(not isinstance(item, Mapping) for item in artifact_entries):
        raise TypeError("N3 manifest artifact entries must be mappings")
    if any(Path(item.get("path", "")).resolve() == manifest_path for item in artifact_entries):
        raise RuntimeError("N3 manifest artifact list must exclude the manifest itself")
    for item in artifact_entries:
        path = Path(str(item["path"])).expanduser().resolve(strict=True)
        if not path.is_relative_to(output_root):
            raise RuntimeError(f"N3 artifact escaped the replicate output root: {path}")
        if path.stat().st_size != int(item["size_bytes"]) or sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"N3 artifact hash/size validation failed: {path}")
    metrics_path = Path(str(manifest["metrics"]["path"])).expanduser().resolve(strict=True)
    selection_path = Path(str(manifest["selection"]["path"])).expanduser().resolve(strict=True)
    if not metrics_path.is_relative_to(output_root) or not selection_path.is_relative_to(output_root):
        raise RuntimeError("N3 metrics/selection artifact escaped the replicate output root")
    if metrics_path != n3_metrics_path(output_root) or selection_path != n3_selection_path(output_root):
        raise RuntimeError("N3 metrics/selection artifact path identity drift")
    with metrics_path.open(encoding="utf-8") as stream:
        metrics = json.load(stream)
    with selection_path.open(encoding="utf-8") as stream:
        selection = json.load(stream)
    if sha256_file(metrics_path) != manifest["metrics"]["sha256"]:
        raise RuntimeError("N3 metrics hash does not match manifest")
    if sha256_file(selection_path) != manifest["selection"]["sha256"]:
        raise RuntimeError("N3 selection hash does not match manifest")
    case_table = {
        int(item["env_id"]): item for item in manifest.get("case_table", [])
    }
    dataset_path = Path(str(manifest["dataset"]["path"])).expanduser().resolve(strict=True)
    if not dataset_path.is_relative_to(output_root):
        raise RuntimeError("N3 dataset artifact escaped the replicate output root")
    if dataset_path != n3_dataset_path(output_root):
        raise RuntimeError("N3 dataset artifact path identity drift")
    dataset_summary = validate_n3_hdf5(dataset_path, case_table)
    if dataset_summary["sha256"] != manifest["dataset"]["sha256"]:
        raise RuntimeError("N3 dataset hash does not match manifest")
    if dataset_summary["size_bytes"] != int(manifest["dataset"]["size_bytes"]):
        raise RuntimeError("N3 dataset size does not match manifest")
    if not isinstance(metrics, Mapping) or not isinstance(selection, Mapping):
        raise TypeError("N3 metrics/selection artifacts must be mappings")
    if metrics.get("schema") != N3_METRICS_SCHEMA or selection.get("schema") != N3_SELECTION_SCHEMA:
        raise ValueError("N3 metrics/selection schema drift")
    return manifest, metrics


def validate_student_contract(config: Mapping[str, Any]) -> None:
    """Backward-compatible Student-only contract helper."""
    validate_controller_contract(config, "student")


def extract_randomized_case(diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    """Extract exact reset-case fields from a terminal diagnostic."""
    for key in ("randomized_case", "randomization_case", "randomization"):
        nested = diagnostic.get(key)
        if isinstance(nested, Mapping):
            missing = [name for name in RANDOMIZED_CASE_KEYS if name not in nested]
            if missing:
                raise KeyError(f"terminal randomized_case is missing required c18 fields: {missing}")
            return {name: json_safe(nested[name]) for name in RANDOMIZED_CASE_KEYS}
    missing = [key for key in RANDOMIZED_CASE_KEYS if key not in diagnostic]
    if missing:
        raise KeyError(
            "terminal diagnostic is missing required c18 randomized-case fields: "
            f"{missing}"
        )
    return {key: json_safe(diagnostic[key]) for key in RANDOMIZED_CASE_KEYS}


def _diagnostic_semantics(
    record: Mapping[str, Any], diagnostic: Mapping[str, Any]
) -> dict[str, Any]:
    terminal_reason = record.get("terminal_reason", diagnostic.get("terminal_reasons"))
    max_stage = record.get("max_stage", diagnostic.get("stage_buf"))
    goal_reached = record.get("goal_reached")
    if goal_reached is None:
        goal_reached = bool(
            terminal_reason == "complete" or int(max_stage) >= 5
        )
    if not isinstance(goal_reached, bool):
        raise TypeError(f"goal_reached must be bool, got {goal_reached!r}")
    if not isinstance(max_stage, int):
        max_stage = int(max_stage)
    if not isinstance(terminal_reason, str) or not terminal_reason:
        raise ValueError(f"terminal_reason must be a non-empty string, got {terminal_reason!r}")
    return {
        "goal_reached": goal_reached,
        "max_stage": max_stage,
        "terminal_reason": terminal_reason,
    }


def episode_records(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    required = (
        "episode_rewards",
        "episode_goal_reached",
        "episode_max_stage_reached",
        "episode_terminal_reasons",
        "episode_terminal_diagnostics",
    )
    missing = [key for key in required if key not in metrics]
    if missing:
        raise KeyError(f"formal eval metrics missing required fields: {missing}")
    lengths = [len(metrics[key]) for key in required]
    if len(set(lengths)) != 1 or lengths[0] != EXPECTED_EPISODES:
        raise RuntimeError(f"expected 16 aligned first-episode metric entries; lengths={lengths}")
    records = []
    seen = set()
    for idx in range(EXPECTED_EPISODES):
        diagnostic = metrics["episode_terminal_diagnostics"][idx]
        if not isinstance(diagnostic, Mapping):
            raise TypeError(f"terminal diagnostic {idx} is not a mapping")
        diagnostic = json_safe(diagnostic)
        if "env_id" not in diagnostic:
            raise KeyError(f"terminal diagnostic {idx} is missing required env_id")
        env_id = diagnostic["env_id"]
        if isinstance(env_id, bool) or not isinstance(env_id, int):
            raise TypeError(
                f"terminal diagnostic {idx} env_id must be an integer; got {env_id!r}"
            )
        if env_id in seen or not 0 <= env_id < EXPECTED_NUM_ENVS:
            raise RuntimeError(f"terminal diagnostic env_id is not unique/in range: {env_id}")
        seen.add(env_id)
        semantics = _diagnostic_semantics(
            {
                "goal_reached": bool(metrics["episode_goal_reached"][idx]),
                "max_stage": int(metrics["episode_max_stage_reached"][idx]),
                "terminal_reason": metrics["episode_terminal_reasons"][idx],
            },
            diagnostic,
        )
        records.append(
            {
                "env_id": env_id,
                # eval_num_envs_episodes=true is the protocol authority: every
                # record is the first episode, independent of completion order.
                "episode_index": 0,
                "reward": float(metrics["episode_rewards"][idx]),
                **semantics,
                "randomized_case": extract_randomized_case(diagnostic),
                "terminal_diagnostic": diagnostic,
            }
        )
    if seen != set(range(EXPECTED_NUM_ENVS)):
        raise RuntimeError(f"formal eval did not return one entry for every env: {sorted(seen)}")
    return records


def rank_episode_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if len(records) != EXPECTED_EPISODES:
        raise ValueError(f"ranking requires exactly 16 records; got {len(records)}")
    ranked = sorted(
        (dict(record) for record in records),
        key=lambda record: (
            -int(bool(record["goal_reached"])),
            -int(record["max_stage"]),
            -float(record["reward"]),
            int(record["env_id"]),
        ),
    )
    for rank, record in enumerate(ranked):
        record["rank"] = rank
    return ranked


def _formal_schemas(controller: str) -> tuple[str, str]:
    if controller == "student":
        return STUDENT_METRICS_SCHEMA, STUDENT_SELECTION_SCHEMA
    if controller == "teacher":
        return TEACHER_METRICS_SCHEMA, TEACHER_SELECTION_SCHEMA
    raise ValueError(f"unknown controller {controller!r}; expected {CONTROLLERS}")


def _formal_contract(
    controller: str,
    checkpoint_info: Mapping[str, Any],
    teacher_info: Mapping[str, Any],
    experience_info: Mapping[str, Any],
    *,
    case_seed: int,
    replicate_id: str,
    student_d435i_forward_mode: str | None = None,
) -> dict[str, Any]:
    if isinstance(case_seed, bool) or not isinstance(case_seed, int) or case_seed != EXPECTED_SEED:
        raise ValueError(f"formal case seed must be exactly {EXPECTED_SEED}; got {case_seed!r}")
    if not isinstance(replicate_id, str) or not replicate_id or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for character in replicate_id
    ):
        raise ValueError(f"replicate_id must be a non-empty safe token: {replicate_id!r}")
    controller_fields = controller_contract(controller)
    contract = {
        **controller_fields,
        "case_seed": case_seed,
        "replicate_id": replicate_id,
        "num_envs": EXPECTED_NUM_ENVS,
        "one_episode_per_env": True,
        "checkpoint_identity": dict(checkpoint_info),
        "teacher_identity": dict(teacher_info),
        "experience_identity": dict(experience_info),
        "use_a2_base": True,
    }
    if controller == "student":
        effective_mode = (
            "sequential"
            if student_d435i_forward_mode is None
            else student_d435i_forward_mode
        )
        if effective_mode not in STUDENT_D435I_FORWARD_MODES:
            raise ValueError(
                "student_d435i_forward_mode must be exactly one of "
                f"{STUDENT_D435I_FORWARD_MODES}; got {effective_mode!r}"
            )
        contract["student_d435i_forward_mode"] = effective_mode
    elif student_d435i_forward_mode is not None:
        raise ValueError(
            "student_d435i_forward_mode is only defined for the Student controller"
        )
    return contract


def effective_student_d435i_forward_mode(
    controller: str, mode: str | None = None
) -> str | None:
    """Resolve the explicit Student view-mode contract with sequential compatibility."""
    if controller not in CONTROLLERS:
        raise ValueError(f"unknown controller {controller!r}; expected {CONTROLLERS}")
    if controller != "student":
        if mode is not None:
            raise ValueError(
                "student_d435i_forward_mode is only defined for the Student controller"
            )
        return None
    effective = "sequential" if mode is None else mode
    if effective not in STUDENT_D435I_FORWARD_MODES:
        raise ValueError(
            "student_d435i_forward_mode must be exactly one of "
            f"{STUDENT_D435I_FORWARD_MODES}; got {effective!r}"
        )
    return effective


def seal_formal_selection(
    metrics: Mapping[str, Any],
    output_root: Path,
    checkpoint_info: Mapping[str, Any],
    *,
    controller: str = "student",
    teacher_info: Mapping[str, Any] | None = None,
    experience_info: Mapping[str, Any] | None = None,
    overlay_repository: Path = REPO_ROOT,
    case_seed: int = EXPECTED_SEED,
    replicate_id: str = "replicate01",
    student_d435i_forward_mode: str | None = None,
) -> dict[str, Any]:
    output_root = output_root.expanduser().resolve()
    if output_root.exists() and not output_root.is_dir():
        raise FileExistsError(f"formal output root is not a directory: {output_root}")
    metrics_schema, selection_schema = _formal_schemas(controller)
    if teacher_info is None:
        teacher_info = validate_teacher_identity()
    if experience_info is None:
        experience_info = resolve_experience_source(overlay_repository, controller)
    experience_info = validate_experience_identity(
        experience_info, overlay_repository, controller
    )
    contract = _formal_contract(
        controller,
        checkpoint_info,
        teacher_info,
        experience_info,
        case_seed=case_seed,
        replicate_id=replicate_id,
        student_d435i_forward_mode=student_d435i_forward_mode,
    )
    records = episode_records(json_safe(metrics))
    ranked = rank_episode_records(records)
    source_metrics = {
        "schema": metrics_schema,
        "controller": controller,
        "checkpoint": dict(checkpoint_info),
        "teacher": dict(teacher_info),
        "experience": dict(experience_info),
        "case_seed": case_seed,
        "replicate_id": replicate_id,
        "contract": contract,
        "episodes": records,
    }
    metrics_path = output_root / f"formal_{controller}_metrics.json"
    atomic_json_write(metrics_path, source_metrics)
    selected = ranked[0]
    selection = {
        "schema": selection_schema,
        "controller": controller,
        "checkpoint": dict(checkpoint_info),
        "teacher": dict(teacher_info),
        "experience": dict(experience_info),
        "case_seed": case_seed,
        "replicate_id": replicate_id,
        "contract": contract,
        "ranking": {
            "order": FORMAL_RANKING_ORDER,
            "records": ranked,
        },
        "selected": {
            "env_id": selected["env_id"],
            "episode_index": selected["episode_index"],
            "reward": selected["reward"],
            "goal_reached": selected["goal_reached"],
            "max_stage": selected["max_stage"],
            "terminal_reason": selected["terminal_reason"],
            "randomized_case": selected["randomized_case"],
        },
        "source_metrics": {
            "path": str(metrics_path),
            "sha256": sha256_file(metrics_path),
        },
    }
    selection_path = output_root / (
        "student_selection.json" if controller == "student" else "teacher_selection.json"
    )
    atomic_json_write(selection_path, selection)
    return selection


def load_sealed_selection(selection_path: Path, source_metrics_path: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    selection_path = selection_path.expanduser().resolve(strict=True)
    with selection_path.open(encoding="utf-8") as stream:
        selection = json.load(stream)
    schema = selection.get("schema")
    legacy = schema == LEGACY_SELECTION_SCHEMA
    if legacy:
        controller = "student"
        expected_contract = {
            "seed": EXPECTED_SEED,
            "num_envs": EXPECTED_NUM_ENVS,
            "one_episode_per_env": True,
            "pure_student": True,
            "teacher_rollout_ratio": 0.0,
            "use_a2_base": True,
        }
        contract = selection.get("contract")
        if contract != expected_contract:
            raise ValueError(
                f"sealed selection contract drift: expected {expected_contract}, got {contract}"
            )
        checkpoint = selection.get("checkpoint", {})
        if checkpoint.get("path") != str(CHECKPOINT) or checkpoint.get("sha256") != CHECKPOINT_SHA256:
            raise ValueError("sealed legacy selection does not identify the pinned v19 checkpoint")
        expected_metrics_schema = LEGACY_METRICS_SCHEMA
    else:
        if schema not in {STUDENT_SELECTION_SCHEMA, TEACHER_SELECTION_SCHEMA}:
            raise ValueError(f"unsupported selection schema: {schema!r}")
        controller = selection.get("controller")
        if controller not in CONTROLLERS:
            raise ValueError(f"sealed selection controller is invalid: {controller!r}")
        _, expected_selection_schema = _formal_schemas(controller)
        if schema != expected_selection_schema:
            raise ValueError("sealed selection/controller schema mismatch")
        expected_metrics_schema, _ = _formal_schemas(controller)
        contract = selection.get("contract")
        if not isinstance(contract, Mapping):
            raise KeyError("sealed selection is missing formal contract")
        controller_fields = controller_contract(controller)
        for key, expected in controller_fields.items():
            if contract.get(key) != expected:
                raise ValueError(
                    f"sealed selection controller contract drift for {key}: "
                    f"expected {expected!r}, got {contract.get(key)!r}"
                )
        if contract.get("case_seed") != EXPECTED_SEED or selection.get("case_seed") != EXPECTED_SEED:
            raise ValueError("sealed selection case seed must be exactly 0")
        replicate_id = selection.get("replicate_id")
        if not isinstance(replicate_id, str) or contract.get("replicate_id") != replicate_id:
            raise ValueError("sealed selection replicate_id is missing or inconsistent")
        if contract.get("num_envs") != EXPECTED_NUM_ENVS or contract.get("one_episode_per_env") is not True:
            raise ValueError("sealed selection formal dimensions drifted")
        checkpoint = selection.get("checkpoint")
        teacher = selection.get("teacher")
        experience = selection.get("experience")
        if (
            not isinstance(checkpoint, Mapping)
            or not isinstance(teacher, Mapping)
            or not isinstance(experience, Mapping)
        ):
            raise KeyError(
                "sealed selection must record checkpoint, Teacher, and experience identities"
            )
        if contract.get("checkpoint_identity") != checkpoint or contract.get("teacher_identity") != teacher:
            raise ValueError("sealed selection identity copies are inconsistent")
        if contract.get("experience_identity") != experience:
            raise ValueError("sealed selection experience identity copy is inconsistent")
    source_spec = selection.get("source_metrics")
    if not isinstance(source_spec, Mapping):
        raise KeyError("sealed selection is missing source_metrics path/hash")
    embedded_source = Path(source_spec.get("path", "")).expanduser().resolve()
    if source_metrics_path is not None and embedded_source != source_metrics_path.expanduser().resolve():
        raise ValueError("explicit source metrics path differs from sealed selection")
    if not embedded_source.is_file() or sha256_file(embedded_source) != source_spec.get("sha256"):
        raise RuntimeError("sealed source metrics path/hash validation failed")
    with embedded_source.open(encoding="utf-8") as stream:
        metrics = json.load(stream)
    if metrics.get("schema") != expected_metrics_schema:
        raise ValueError("source metrics schema/contract drift")
    if not legacy:
        if metrics.get("controller") != controller:
            raise ValueError("source metrics controller drift")
        if metrics.get("checkpoint") != selection.get("checkpoint"):
            raise ValueError("source metrics checkpoint identity drift")
        if metrics.get("teacher") != selection.get("teacher"):
            raise ValueError("source metrics Teacher identity drift")
        if metrics.get("experience") != selection.get("experience"):
            raise ValueError("source metrics experience identity drift")
        if metrics.get("case_seed") != selection.get("case_seed"):
            raise ValueError("source metrics case seed drift")
        if metrics.get("replicate_id") != selection.get("replicate_id"):
            raise ValueError("source metrics replicate_id drift")
    if metrics.get("contract") != contract:
        raise ValueError("source metrics formal contract drift")
    source_records = metrics.get("episodes")
    if not isinstance(source_records, list) or len(source_records) != EXPECTED_EPISODES:
        raise ValueError("source metrics must seal exactly 16 episode records")
    if any(not isinstance(record, Mapping) for record in source_records):
        raise ValueError("source metrics episode records must be mappings")
    if any(record.get("episode_index") != 0 for record in source_records):
        raise ValueError("source metrics must seal episode_index=0 for every first episode")
    ranked_source = rank_episode_records(source_records)
    ranking = selection.get("ranking")
    if not isinstance(ranking, Mapping):
        raise KeyError("sealed selection is missing frozen ranking")
    if ranking.get("order") != FORMAL_RANKING_ORDER:
        raise ValueError("sealed selection ranking order drifted")
    ranked_records = ranking.get("records")
    if not isinstance(ranked_records, list) or len(ranked_records) != EXPECTED_EPISODES:
        raise ValueError("sealed selection ranking must contain exactly 16 records")
    if any(not isinstance(record, Mapping) for record in ranked_records):
        raise TypeError("sealed selection ranking records must be mappings")
    if canonical_json(ranked_records) != canonical_json(ranked_source):
        raise RuntimeError(
            "sealed selection ranking records are not provenance-consistent with "
            "hash-validated source metrics"
        )
    selected = selection.get("selected")
    if not isinstance(selected, Mapping):
        raise KeyError("sealed selection is missing selected case")
    selected_env = selected.get("env_id")
    if isinstance(selected_env, bool) or not isinstance(selected_env, int):
        raise TypeError(f"sealed selected env_id must be an integer; got {selected_env!r}")
    if not 0 <= selected_env < EXPECTED_NUM_ENVS:
        raise ValueError("selected env id is outside the formal 16-env range")
    if selected.get("episode_index") != 0:
        raise ValueError("sealed selected case must identify episode_index=0")
    randomized_case = selected.get("randomized_case")
    if not isinstance(randomized_case, Mapping):
        raise KeyError("sealed selection is missing exact randomized_case fields")
    if set(randomized_case) != set(RANDOMIZED_CASE_KEYS):
        raise ValueError(
            "sealed selected case randomized_case keys drifted: "
            f"expected={list(RANDOMIZED_CASE_KEYS)} got={sorted(randomized_case)}"
        )
    top = ranked_source[0]
    for key in (
        "env_id",
        "episode_index",
        "goal_reached",
        "max_stage",
        "terminal_reason",
        "randomized_case",
    ):
        if selected.get(key) != top.get(key):
            raise ValueError(f"sealed selected case does not match frozen ranking for {key}")
    if "reward" in selected and selected["reward"] != top["reward"]:
        raise ValueError("sealed selected case does not match frozen ranking for reward")
    # Older v1 selection files did not duplicate reward in `selected`; derive it
    # from the sealed ranked record without changing the on-disk provenance.
    if "reward" not in selected and isinstance(selected, dict):
        selected["reward"] = top["reward"]
    return selection, metrics


def _selected_formal_record(selection: Mapping[str, Any]) -> dict[str, Any]:
    selected = selection.get("selected")
    if not isinstance(selected, Mapping):
        raise KeyError("sealed selection is missing selected case")
    ranking = selection.get("ranking")
    ranked_records = ranking.get("records") if isinstance(ranking, Mapping) else None
    if not isinstance(ranked_records, list):
        raise KeyError("sealed selection is missing frozen ranking records")
    matches = [
        record
        for record in ranked_records
        if isinstance(record, Mapping)
        and record.get("env_id") == selected.get("env_id")
        and record.get("episode_index") == selected.get("episode_index")
        and record.get("randomized_case") == selected.get("randomized_case")
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "sealed selection must contain exactly one frozen record for the selected case; "
            f"matches={len(matches)}"
        )
    source = dict(matches[0])
    if any(key not in source for key in OUTCOME_KEYS):
        raise KeyError(f"sealed selected formal record is missing outcome fields: {OUTCOME_KEYS}")
    return source


def _outcome_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in OUTCOME_KEYS}


def _outcome_drift(
    source: Mapping[str, Any], replay: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "source": source[key],
            "replay": replay[key],
            "changed": source[key] != replay[key],
        }
        for key in OUTCOME_KEYS
    }


def validate_replay_selected_case(
    selection: Mapping[str, Any], replay_metrics: Mapping[str, Any]
) -> dict[str, Any]:
    source = _selected_formal_record(selection)
    env_id = source.get("env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int):
        raise TypeError(f"selected formal env_id must be an integer; got {env_id!r}")
    if not 0 <= env_id < EXPECTED_NUM_ENVS:
        raise ValueError(f"selected formal env_id is outside range: {env_id}")
    episode_index = source.get("episode_index")
    if isinstance(episode_index, bool) or not isinstance(episode_index, int):
        raise TypeError(
            f"selected formal episode_index must be an integer; got {episode_index!r}"
        )
    records = episode_records(json_safe(replay_metrics))
    replay = next((record for record in records if record["env_id"] == env_id), None)
    if replay is None:
        raise RuntimeError(f"replay did not return selected env {env_id}")
    if replay["episode_index"] != episode_index:
        raise RuntimeError(
            "selected replay episode_index drift: "
            f"source={episode_index!r}, replay={replay['episode_index']!r}"
        )
    source_case = source.get("randomized_case")
    replay_case = replay.get("randomized_case")
    if not isinstance(source_case, Mapping) or set(source_case) != set(RANDOMIZED_CASE_KEYS):
        raise ValueError("sealed selected formal randomized_case identity is incomplete")
    if not isinstance(replay_case, Mapping) or set(replay_case) != set(RANDOMIZED_CASE_KEYS):
        raise RuntimeError("replay randomized_case identity is incomplete")
    if replay_case != source_case:
        raise RuntimeError("selected replay randomized-case fields differ from source terminal diagnostics")
    source_outcome = _outcome_fields(source)
    replay_outcome = _outcome_fields(replay)
    validated = dict(replay)
    validated["case_identity"] = {
        "env_id": env_id,
        "episode_index": episode_index,
        "randomized_case": dict(source_case),
    }
    validated["source_formal_outcome"] = source_outcome
    validated["replay_outcome"] = replay_outcome
    validated["outcome_drift"] = _outcome_drift(source_outcome, replay_outcome)
    return validated


def validate_policy_camera_contract(
    left: Any,
    right: Any,
    head: Any,
    vision_obs: Any,
    context_vision_obs: Any,
    camera_meta: Any,
    cameras_config: Mapping[str, Any],
    env_count: int = EXPECTED_NUM_ENVS,
) -> None:
    """Prove raw C-B2H tri-view frames recompute the policy observation tensors."""
    import torch

    expected = {
        "left": (env_count, 384, 216, 3),
        "right": (env_count, 384, 216, 3),
        "head": (env_count, 136, 384, 3),
        "vision_obs": (env_count, 384, 216, 6),
        "context_vision_obs": (env_count, 136, 384, 3),
        "camera_meta": (env_count, 6),
    }
    values = {"left": left, "right": right, "head": head, "vision_obs": vision_obs, "context_vision_obs": context_vision_obs, "camera_meta": camera_meta}
    for name, value in values.items():
        if not torch.is_tensor(value) or tuple(value.shape) != expected[name]:
            raise RuntimeError(f"{name} contract drift: expected {expected[name]}, got {getattr(value, 'shape', None)}")
        if name in {"left", "right", "head"} and value.dtype != torch.uint8:
            raise RuntimeError(f"raw {name} camera must remain uint8; got {value.dtype}")
        if name not in {"left", "right", "head"} and (not torch.is_floating_point(value) or not bool(torch.all(torch.isfinite(value)).item())):
            raise RuntimeError(f"policy {name} must be finite floating-point")
    from gr00t.rl.utils.a2_policy_camera import (
        compose_channel_stacked_dual_rgb,
        normalize_head_context_rgb,
    )

    mean = list(cameras_config["image_mean"])
    std = list(cameras_config["image_std"])
    recomposed = compose_channel_stacked_dual_rgb(
        left,
        right,
        resolution=(384, 216),
        image_mean=mean,
        image_std=std,
    )
    normalized_head = normalize_head_context_rgb(
        head,
        resolution=(136, 384),
        image_mean=mean,
        image_std=std,
    )
    if not torch.equal(recomposed, vision_obs):
        raise RuntimeError("raw left/right frames do not exactly recompose vision_obs")
    if not torch.equal(normalized_head, context_vision_obs):
        raise RuntimeError("raw OEM head frame does not exactly recompose context_vision_obs")
    if not bool(torch.all(torch.isfinite(camera_meta)).item()):
        raise RuntimeError("camera_meta contains non-finite values")


def _inverse_normalize_policy_rgb(
    normalized: Any,
    *,
    image_mean: Sequence[float],
    image_std: Sequence[float],
    name: str,
) -> Any:
    """Recover raw uint8 RGB while proving an integer normalization round-trip."""
    import torch

    if not torch.is_tensor(normalized) or normalized.dtype != torch.float32:
        raise RuntimeError(
            f"{name} must be float32 policy input for exact raw-frame recovery; "
            f"got dtype={getattr(normalized, 'dtype', None)}"
        )
    if not bool(torch.all(torch.isfinite(normalized)).item()):
        raise RuntimeError(f"{name} contains non-finite normalized pixels")
    mean = torch.as_tensor(list(image_mean), device=normalized.device, dtype=torch.float32)
    std = torch.as_tensor(list(image_std), device=normalized.device, dtype=torch.float32)
    if tuple(mean.shape) != (3,) or tuple(std.shape) != (3,):
        raise RuntimeError(f"{name} image mean/std must each have three values")
    if not bool(torch.all(torch.isfinite(mean)).item()) or not bool(torch.all(torch.isfinite(std)).item()):
        raise RuntimeError(f"{name} image mean/std must be finite")
    if bool(torch.any(std <= 0.0).item()):
        raise RuntimeError(f"{name} image_std must be strictly positive")
    raw_float = (normalized * std + mean) * 255.0
    if not bool(torch.all(torch.isfinite(raw_float)).item()):
        raise RuntimeError(f"{name} inverse normalization produced non-finite RGB")
    tolerance = 2.0e-3
    if bool(torch.any(raw_float < -tolerance).item()) or bool(torch.any(raw_float > 255.0 + tolerance).item()):
        raise RuntimeError(f"{name} inverse normalization escaped uint8 range")
    rounded = torch.round(raw_float)
    if bool(torch.any(torch.abs(raw_float - rounded) > tolerance).item()):
        raise RuntimeError(f"{name} normalized pixels do not have an integer uint8 round-trip")
    raw = rounded.clamp(0.0, 255.0).to(torch.uint8)
    if tuple(raw.shape[:-1]) != tuple(normalized.shape[:-1]) or raw.shape[-1] != 3:
        raise RuntimeError(f"{name} recovered raw frame shape drifted: {tuple(raw.shape)}")
    return raw


def derive_raw_policy_frames_from_observations(
    vision_obs: Any,
    context_vision_obs: Any,
    *,
    image_mean: Sequence[float],
    image_std: Sequence[float],
    env_count: int = EXPECTED_NUM_ENVS,
) -> tuple[Any, Any, Any]:
    """Derive left/right/head uint8 frames only from the Student policy inputs."""
    import torch

    expected_vision = (env_count, 384, 216, 6)
    expected_context = (env_count, 136, 384, 3)
    if not torch.is_tensor(vision_obs) or tuple(vision_obs.shape) != expected_vision:
        raise RuntimeError(
            f"vision_obs contract drift: expected {expected_vision}, got {getattr(vision_obs, 'shape', None)}"
        )
    if not torch.is_tensor(context_vision_obs) or tuple(context_vision_obs.shape) != expected_context:
        raise RuntimeError(
            "context_vision_obs contract drift: "
            f"expected {expected_context}, got {getattr(context_vision_obs, 'shape', None)}"
        )
    if vision_obs.dtype != torch.float32 or context_vision_obs.dtype != torch.float32:
        raise RuntimeError("Student tri-view policy inputs must be float32")
    left = _inverse_normalize_policy_rgb(
        vision_obs[..., :3], image_mean=image_mean, image_std=image_std, name="vision_obs.left"
    )
    right = _inverse_normalize_policy_rgb(
        vision_obs[..., 3:6], image_mean=image_mean, image_std=image_std, name="vision_obs.right"
    )
    head = _inverse_normalize_policy_rgb(
        context_vision_obs, image_mean=image_mean, image_std=image_std, name="context_vision_obs.head"
    )
    from gr00t.rl.utils.a2_policy_camera import (
        compose_channel_stacked_dual_rgb,
        normalize_head_context_rgb,
    )

    recomposed = compose_channel_stacked_dual_rgb(
        left,
        right,
        resolution=(384, 216),
        image_mean=image_mean,
        image_std=image_std,
    )
    if not torch.equal(recomposed, vision_obs):
        raise RuntimeError("derived left/right raw frames do not bitwise recompose vision_obs")
    normalized_head = normalize_head_context_rgb(
        head,
        resolution=(136, 384),
        image_mean=image_mean,
        image_std=image_std,
    )
    if not torch.equal(normalized_head, context_vision_obs):
        raise RuntimeError("derived raw head frame does not bitwise recompose context_vision_obs")
    return left, right, head


def validate_external_debug_videos(paths: Sequence[Path], env_id: int) -> None:
    if len(paths) != 3:
        raise RuntimeError(f"selected render requires exactly three external debug videos; got {len(paths)}")
    env_pattern = re.compile(r"env[_-]?(\d+)", re.IGNORECASE)
    for path in paths:
        if path.stat().st_size <= 0:
            raise RuntimeError(f"external debug video is empty: {path}")
        ids = [int(match.group(1)) for match in env_pattern.finditer(path.name)]
        if not ids:
            raise RuntimeError(f"external debug video has no env identity: {path.name}")
        if any(item != env_id for item in ids):
            raise RuntimeError(f"external debug video is not selected-env-only: {path.name}")
    names = {path.name for path in paths}
    top = [name for name in names if "handle_top" in name]
    side = [name for name in names if "handle_side" in name]
    main = [name for name in names if "handle_top" not in name and "handle_side" not in name]
    if len(top) != 1 or len(side) != 1 or len(main) != 1:
        raise RuntimeError("external debug videos must include handle_top and handle_side cameras")


def _bind_a2_eval_methods(controller: str, trainer_target: str):
    from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import (
        TRLDistillTrainerA2BaseAPI,
        compose_a2_rollout_action,
    )
    from gr00t.rl.trl.trainer.ppo_trainer import TRLPPOTrainer as GenericTRLPPOTrainer
    from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import (
        TRLPPOTrainer as A2TRLPPOTrainer,
        _read_a2_eval_diagnostic_config,
    )

    global _N3_RUNTIME_A2_DIAGNOSTIC_CONFIG_READER
    global _N3_RUNTIME_A2_ROLLOUT_ACTION_COMPOSER
    _N3_RUNTIME_A2_DIAGNOSTIC_CONFIG_READER = _read_a2_eval_diagnostic_config
    _N3_RUNTIME_A2_ROLLOUT_ACTION_COMPOSER = compose_a2_rollout_action

    expected = expected_trainer_target(controller)
    if trainer_target != expected:
        raise RuntimeError(
            f"{controller} trainer target/class binding mismatch: expected {expected}, got {trainer_target}"
        )
    if controller == "student":
        actual_target = f"{TRLDistillTrainerA2BaseAPI.__module__}.{TRLDistillTrainerA2BaseAPI.__qualname__}"
        if actual_target != STUDENT_TRAINER_TARGET:
            raise RuntimeError(
                f"Student trainer class mismatch: expected {STUDENT_TRAINER_TARGET}, got {actual_target}"
            )
        if TRLDistillTrainerA2BaseAPI.eval is not GenericTRLPPOTrainer.eval:
            raise RuntimeError("Student eval expected generic PPO eval before A2 correction")
        TRLDistillTrainerA2BaseAPI.eval = A2TRLPPOTrainer.eval
        if TRLDistillTrainerA2BaseAPI.eval is not A2TRLPPOTrainer.eval:
            raise RuntimeError("A2 Student eval method binding did not take effect")
        return TRLDistillTrainerA2BaseAPI, A2TRLPPOTrainer.eval
    actual_target = f"{A2TRLPPOTrainer.__module__}.{A2TRLPPOTrainer.__qualname__}"
    if actual_target != TEACHER_TRAINER_TARGET:
        raise RuntimeError(
            f"Teacher trainer class mismatch: expected {TEACHER_TRAINER_TARGET}, got {actual_target}"
        )
    # Teacher's adjacent c18 config already targets the A2 PPO trainer.  Keep
    # that class and its high-level Teacher-action/A2_Base eval path intact;
    # only the formal artifact wrapper is installed on the actual class.
    return A2TRLPPOTrainer, A2TRLPPOTrainer.eval


def _require_n3_runtime_a2_helpers():
    """Return the canonical A2 helpers bound after runtime bootstrap."""
    diagnostic_reader = _N3_RUNTIME_A2_DIAGNOSTIC_CONFIG_READER
    action_composer = _N3_RUNTIME_A2_ROLLOUT_ACTION_COMPOSER
    if not callable(diagnostic_reader) or not callable(action_composer):
        ppo_module = sys.modules.get("gr00t.rl.trl.trainer.ppo_trainer_a2_base_api")
        distill_module = sys.modules.get("gr00t.rl.trl.trainer.distill_trainer_a2_base_api")
        if ppo_module is not None and not callable(diagnostic_reader):
            diagnostic_reader = getattr(ppo_module, "_read_a2_eval_diagnostic_config", None)
        if distill_module is not None and not callable(action_composer):
            action_composer = getattr(distill_module, "compose_a2_rollout_action", None)
    if not callable(diagnostic_reader):
        raise RuntimeError(
            "N3 capture requires the c18 canonical A2 eval diagnostic-config helper"
        )
    if not callable(action_composer):
        raise RuntimeError(
            "N3 capture requires the c18 canonical A2 rollout-action composer"
        )
    return diagnostic_reader, action_composer


def _validate_n3_a2_eval_lifecycle(trainer, device):
    """Initialize the canonical A2 eval lifecycle and reject interventions."""
    env = trainer.env
    if getattr(env, "_use_a2_base", None) is not True:
        raise RuntimeError("N3 capture requires an A2_Base environment")
    if getattr(env, "is_evaluating", None) is not True:
        raise RuntimeError("N3 capture requires env.is_evaluating=True")

    eval_config = trainer.config.get("eval", {})
    if not isinstance(eval_config, Mapping):
        raise TypeError("N3 effective eval config must be a mapping")
    diagnostic_reader, action_composer = _require_n3_runtime_a2_helpers()
    diagnostics = diagnostic_reader(eval_config)
    if not isinstance(diagnostics, Mapping):
        raise TypeError("canonical A2 eval diagnostic config must be a mapping")
    if diagnostics.get("diagnostic_enabled") is not False:
        raise RuntimeError("N3 capture requires A2 diagnostic trace disabled")
    if diagnostics.get("forced_close_enabled") is not False:
        raise RuntimeError("N3 capture requires A2 forced-close intervention disabled")

    posture_axis = eval_config.get("a2_eval_p2_posture_axis", "none")
    if posture_axis != "none":
        raise RuntimeError(
            "N3 capture requires eval.a2_eval_p2_posture_axis='none'; "
            f"got {posture_axis!r}"
        )
    strict_telemetry = eval_config.get("a2_eval_m41_strict_telemetry", False)
    if strict_telemetry is not False:
        raise RuntimeError("N3 capture requires strict A2 M41 telemetry disabled")
    dump_to_log = eval_config.get("dump_to_log_metrics", False)
    if dump_to_log is not False:
        raise RuntimeError("N3 capture requires eval.dump_to_log_metrics disabled")
    save_videos = eval_config.get("save_videos", False)
    if save_videos is not False:
        raise RuntimeError("N3 capture requires eval.save_videos disabled")

    simulator_config = env.config.simulator.config
    if isinstance(simulator_config, Mapping):
        render_results = simulator_config["render_results"]
    else:
        render_results = getattr(simulator_config, "render_results")
    if render_results is not False:
        raise RuntimeError("N3 capture requires simulator.config.render_results=false")

    init_metrics = getattr(env, "init_eval_metrics_tracking", None)
    if not callable(init_metrics):
        raise RuntimeError("N3 capture requires env.init_eval_metrics_tracking()")
    init_metrics(device)

    init_trace = getattr(env, "init_a2_eval_stage2_step_trace", None)
    if not callable(init_trace):
        raise RuntimeError("N3 capture requires env.init_a2_eval_stage2_step_trace()")
    init_trace(diagnostic_enabled=False, diagnostic_reward_terms=())

    init_oracle = getattr(env, "init_a2_eval_hold_oracle", None)
    if not callable(init_oracle):
        raise RuntimeError("N3 capture requires env.init_a2_eval_hold_oracle()")
    oracle_config = init_oracle(eval_config, diagnostic_enabled=False)
    if not isinstance(oracle_config, Mapping) or oracle_config.get("enabled") is not False:
        raise RuntimeError("N3 capture requires the A2 hold oracle disabled")

    hold_detail_getter = getattr(env, "_get_a2_hold_contact_detail_enabled", None)
    if not callable(hold_detail_getter):
        raise RuntimeError("N3 capture requires the A2 hold-detail config getter")
    if hold_detail_getter() is not False:
        raise RuntimeError("N3 capture requires detailed A2 hold diagnostics disabled")

    get_layout = getattr(env, "get_a2_high_level_action_layout", None)
    if not callable(get_layout):
        raise RuntimeError("N3 capture requires env.get_a2_high_level_action_layout()")
    layout = get_layout()
    expected_layout = {
        "dim": 12,
        "base_start": 0,
        "base_end": 5,
        "arm_start": 5,
        "arm_end": 11,
        "gripper_index": 11,
    }
    if layout != expected_layout:
        raise RuntimeError(
            "N3 capture requires the canonical A2 high-level action layout; "
            f"expected={expected_layout!r} got={layout!r}"
        )
    return action_composer


def _make_n3_capture_eval(
    output_root: Path,
    passive_student_info: Mapping[str, Any],
    teacher_info: Mapping[str, Any],
    experience_info: Mapping[str, Any],
    *,
    overlay_repository: Path,
    case_seed: int,
    replicate_id: str,
):
    """Build a no-training, Teacher-controlled C-B2H trajectory capture hook."""
    output_root = output_root.expanduser().resolve()
    overlay_repository = overlay_repository.expanduser().resolve(strict=True)

    def n3_capture_eval(self):
        import numpy as np
        import torch

        validate_n3_capture_contract(
            self.config,
            passive_student_info,
            teacher_info,
            experience_info,
        )
        if self.env.num_envs != EXPECTED_NUM_ENVS:
            raise RuntimeError(
                f"N3 capture requires exactly {EXPECTED_NUM_ENVS} envs; got {self.env.num_envs}"
            )
        if self.ref_model is None:
            raise RuntimeError("N3 capture requires the exact recurrent Teacher reference model")
        if getattr(self.ref_model, "num_actions", None) != 12:
            raise RuntimeError("N3 Teacher12D action contract is unavailable")
        if not hasattr(self.ref_model, "act_inference"):
            raise RuntimeError("N3 Teacher reference model must expose act_inference")
        if not hasattr(self.unwrapped_model, "_a2_base_actions"):
            raise RuntimeError("N3 capture requires the existing frozen A2_Base action hook")
        staging_root = n3_staging_root(output_root)
        if output_root.exists() or staging_root.exists():
            raise FileExistsError(
                f"N3 capture refuses existing final/staging roots: final={output_root} "
                f"staging={staging_root}"
            )
        staging_root.parent.mkdir(parents=True, exist_ok=True)
        staging_root.mkdir()
        staging_owned = True
        writer = None
        teacher_rollout_started = False
        try:
            writer = N3TrajectoryWriter(staging_root / N3_DATASET_FILENAME)
            self._eval_mode()
            self.env.set_is_evaluating()
            self.policy_model.eval_mode()
            self.ref_model.eval()
            self.ref_model.init_rollout()
            teacher_rollout_started = True
            obs_dict = self.env.reset_all()
            device = self.accelerator.device
            for obs_key in obs_dict:
                obs_dict[obs_key] = obs_dict[obs_key].to(device)
            if hasattr(self, "_validate_rollout_obs"):
                self._validate_rollout_obs(obs_dict, require_teacher=True)
            action_composer = _validate_n3_a2_eval_lifecycle(self, device)
            if not callable(getattr(self, "_teacher_actions", None)):
                raise RuntimeError("N3 capture requires the canonical Trainer._teacher_actions helper")
            completed = torch.zeros(
                EXPECTED_NUM_ENVS, dtype=torch.bool, device=device
            )
            cur_reward_sum = torch.zeros(
                EXPECTED_NUM_ENVS, dtype=torch.float32, device=device
            )
            cur_episode_length = torch.zeros(
                EXPECTED_NUM_ENVS, dtype=torch.int32, device=device
            )
            with torch.no_grad():
                while not bool(torch.all(completed).item()):
                    active_mask = ~completed
                    if hasattr(self, "_validate_rollout_obs"):
                        self._validate_rollout_obs(obs_dict, require_teacher=True)
                    cameras_cfg = self.env.config.simulator.config.cameras
                    left, right, head = derive_raw_policy_frames_from_observations(
                        obs_dict.get("vision_obs"),
                        obs_dict.get("context_vision_obs"),
                        image_mean=cameras_cfg.image_mean,
                        image_std=cameras_cfg.image_std,
                        env_count=EXPECTED_NUM_ENVS,
                    )
                    validate_policy_camera_contract(
                        left,
                        right,
                        head,
                        obs_dict.get("vision_obs"),
                        obs_dict.get("context_vision_obs"),
                        obs_dict.get("camera_meta"),
                        cameras_cfg,
                        env_count=EXPECTED_NUM_ENVS,
                    )
                    actor_obs = obs_dict.get("actor_obs")
                    camera_meta = obs_dict.get("camera_meta")
                    if (
                        not torch.is_tensor(actor_obs)
                        or tuple(actor_obs.shape) != (EXPECTED_NUM_ENVS, 81)
                        or actor_obs.dtype != torch.float32
                        or not bool(torch.all(torch.isfinite(actor_obs)).item())
                    ):
                        raise RuntimeError("N3 actor_obs must be finite float32 [16,81]")
                    if (
                        not torch.is_tensor(camera_meta)
                        or tuple(camera_meta.shape) != (EXPECTED_NUM_ENVS, 6)
                        or camera_meta.dtype != torch.float32
                        or not bool(torch.all(torch.isfinite(camera_meta)).item())
                    ):
                        raise RuntimeError("N3 camera_meta must be finite float32 [16,6]")
                    stage = getattr(self.env, "stage_buf", None)
                    if not torch.is_tensor(stage) or tuple(stage.shape) != (EXPECTED_NUM_ENVS,):
                        raise RuntimeError("N3 pre-action stage must be an integer tensor [16]")
                    if stage.dtype.is_floating_point:
                        if not bool(torch.all(torch.isfinite(stage)).item()) or not bool(
                            torch.all(stage == stage.round()).item()
                        ):
                            raise RuntimeError("N3 pre-action stage must contain finite integer ids")
                    elif stage.dtype not in (
                        torch.int8,
                        torch.int16,
                        torch.int32,
                        torch.int64,
                        torch.uint8,
                    ):
                        raise RuntimeError("N3 pre-action stage must use an integer dtype")
                    stage = stage.detach().to(device="cpu", dtype=torch.int16)
                    teacher_actions = self._teacher_actions(obs_dict)
                    if (
                        not torch.is_tensor(teacher_actions)
                        or tuple(teacher_actions.shape) != (EXPECTED_NUM_ENVS, 12)
                        or not torch.is_floating_point(teacher_actions)
                        or not bool(torch.all(torch.isfinite(teacher_actions)).item())
                    ):
                        raise RuntimeError("N3 Teacher12D actions must be finite [16,12]")
                    teacher_actions = teacher_actions.detach()
                    a2_actions = self.unwrapped_model._a2_base_actions(
                        obs_dict, teacher_actions
                    )
                    if (
                        not torch.is_tensor(a2_actions)
                        or tuple(a2_actions.shape) != (EXPECTED_NUM_ENVS, 12)
                        or not torch.is_floating_point(a2_actions)
                        or not bool(torch.all(torch.isfinite(a2_actions)).item())
                    ):
                            raise RuntimeError("N3 frozen A2_Base actions must be finite [16,12]")
                    step_actions = action_composer(teacher_actions, a2_actions)
                    if (
                        not torch.is_tensor(step_actions)
                        or tuple(step_actions.shape) != (EXPECTED_NUM_ENVS, 24)
                        or not torch.is_floating_point(step_actions)
                        or not bool(torch.all(torch.isfinite(step_actions)).item())
                    ):
                        raise RuntimeError("N3 composed A2 rollout actions must be finite [16,24]")
                    if not torch.equal(step_actions[:, :12], teacher_actions):
                        raise RuntimeError("N3 environment high-level action is not exact Teacher12D")
                    frame_ids = torch.as_tensor(
                        writer.next_frame_ids, dtype=torch.int64
                    )
                    episode_index = torch.zeros(EXPECTED_NUM_ENVS, dtype=torch.int16)
                    env_ids = torch.arange(EXPECTED_NUM_ENVS, dtype=torch.int16)
                    next_obs_dict, rewards, dones, infos = self.env.step({"actions": step_actions})
                    dones = dones.to(device=device).bool().reshape(-1)
                    if tuple(dones.shape) != (EXPECTED_NUM_ENVS,):
                        raise RuntimeError("N3 env dones must be bool [16]")
                    terminal_dones = dones & active_mask
                    writer.append(
                        {
                            "actor_obs": actor_obs.detach().to(device="cpu", dtype=torch.float32),
                            "left_rgb": left.detach().to(device="cpu", dtype=torch.uint8),
                            "right_rgb": right.detach().to(device="cpu", dtype=torch.uint8),
                            "head_rgb": head.detach().to(device="cpu", dtype=torch.uint8),
                            "camera_meta": camera_meta.detach().to(device="cpu", dtype=torch.float32),
                            "teacher_action": teacher_actions.to(device="cpu", dtype=torch.float32),
                            "pre_action_stage": stage,
                            "done": terminal_dones.to(device="cpu", dtype=torch.bool),
                            "active_mask": active_mask.to(device="cpu", dtype=torch.bool),
                            "env_id": env_ids,
                            "frame_id": frame_ids,
                            "episode_index": episode_index,
                            "case_id": np.asarray([b""] * EXPECTED_NUM_ENVS, dtype="S64"),
                        }
                    )
                    rewards = rewards.to(device=device)
                    cur_reward_sum += rewards * active_mask
                    cur_episode_length += active_mask.to(dtype=cur_episode_length.dtype)
                    self.env.update_eval_metrics_per_step(infos)
                    terminal_ids = torch.nonzero(terminal_dones, as_tuple=False).flatten()
                    returned_ids = torch.nonzero(dones, as_tuple=False).flatten()
                    if terminal_ids.numel() > 0:
                        self.env.process_eval_episode_completions(
                            terminal_ids, cur_reward_sum, cur_episode_length
                        )
                        completed[terminal_ids] = True
                    if returned_ids.numel() > 0:
                        cur_reward_sum[returned_ids] = 0
                        cur_episode_length[returned_ids] = 0
                        self.env.reset_eval_episode_tracking(returned_ids)
                    self.ref_model.reset(dones)
                    if not isinstance(next_obs_dict, Mapping):
                        raise RuntimeError("N3 environment did not return next observations")
                    obs_dict = next_obs_dict
                    for obs_key in obs_dict:
                        obs_dict[obs_key] = obs_dict[obs_key].to(device)
            self.ref_model.clear_rollout()
            teacher_rollout_started = False
            metrics = self.env.get_eval_metrics_summary()
            metrics["completed_episodes"] = len(metrics.get("episode_rewards", []))
            case_table = n3_case_table_from_metrics(metrics)
            writer.finalize(case_table)
            manifest = seal_n3_capture_bundle(
                staging_root=staging_root,
                output_root=output_root,
                metrics=metrics,
                passive_student_info=passive_student_info,
                teacher_info=teacher_info,
                experience_info=experience_info,
                replicate_id=replicate_id,
                case_seed=case_seed,
            )
            if output_root.exists():
                raise FileExistsError(f"N3 capture final root appeared before publish: {output_root}")
            os.replace(staging_root, output_root)
            staging_owned = False
            print(
                f"[A2_N3_CAPTURE_PASS] controller=teacher passive_student=student "
                f"replicate_id={replicate_id} episodes={manifest['dataset']['episode_count']} "
                f"dataset={output_root / N3_DATASET_FILENAME}",
                flush=True,
            )
            return metrics
        finally:
            pending_exception = sys.exc_info()[1]
            cleanup_errors = []
            if teacher_rollout_started:
                teacher_rollout_started = False
                try:
                    self.ref_model.clear_rollout()
                except BaseException as exc:
                    cleanup_errors.append(("Teacher rollout clear", exc))
            if writer is not None:
                try:
                    writer.close()
                except BaseException as exc:
                    cleanup_errors.append(("HDF5 writer close", exc))
            if staging_owned and staging_root.exists():
                try:
                    shutil.rmtree(staging_root)
                except BaseException as exc:
                    cleanup_errors.append(("N3 staging removal", exc))
            if cleanup_errors:
                if pending_exception is None:
                    raise cleanup_errors[0][1]
                for label, error in cleanup_errors:
                    pending_exception.add_note(f"N3 cleanup failure ({label}): {error!r}")

    n3_capture_eval.__name__ = "n3_teacher_capture_eval"
    n3_capture_eval.__qualname__ = "n3_teacher_capture_eval"
    return n3_capture_eval


def _make_formal_eval(
    base_eval,
    output_root: Path,
    checkpoint_info: Mapping[str, Any],
    *,
    controller: str,
    teacher_info: Mapping[str, Any],
    case_seed: int,
    replicate_id: str,
    experience_info: Mapping[str, Any] | None = None,
    overlay_repository: Path = REPO_ROOT,
    student_d435i_forward_mode: str | None = None,
):
    def formal_eval(self):
        validate_controller_contract(self.config, controller)
        if controller == "student":
            expected_mode = effective_student_d435i_forward_mode(
                controller, student_d435i_forward_mode
            )
            if expected_mode is None:
                raise RuntimeError("formal Student mode resolution unexpectedly returned None")
            validate_student_forward_mode_contract(
                self.config, self.policy_model, expected_mode
            )
        if self.env.num_envs != EXPECTED_NUM_ENVS:
            raise RuntimeError(
                f"formal {controller} eval requires 16 envs; got {self.env.num_envs}"
            )
        result = base_eval(self)
        metrics = result if isinstance(result, Mapping) else self.env.get_eval_metrics_summary()
        selection = seal_formal_selection(
            metrics,
            output_root,
            checkpoint_info,
            controller=controller,
            teacher_info=teacher_info,
            experience_info=experience_info,
            overlay_repository=overlay_repository,
            case_seed=case_seed,
            replicate_id=replicate_id,
            student_d435i_forward_mode=student_d435i_forward_mode,
        )
        artifact_name = "student_selection.json" if controller == "student" else "teacher_selection.json"
        print(
            f"[A2_{controller.upper()}_FORMAL_PASS] controller={controller} "
            f"replicate_id={replicate_id} selected_env={selection['selected']['env_id']} "
            f"selection={output_root / artifact_name}",
            flush=True,
        )
        return result

    formal_eval.__name__ = "formal_student_eval"
    formal_eval.__qualname__ = "formal_student_eval"
    formal_eval._a2_eval_base = base_eval
    return formal_eval


def _make_render_eval(
    base_eval,
    output_root: Path,
    selection: Mapping[str, Any],
    selection_path: Path,
):
    output_root = output_root.expanduser().resolve()
    staging_root = render_staging_root(output_root)
    selected_env = int(selection["selected"]["env_id"])
    selection_path = selection_path.expanduser().resolve(strict=True)

    def render_eval(self):
        import imageio.v2 as imageio
        import torch

        validate_student_contract(self.config)
        if self.env.num_envs != EXPECTED_NUM_ENVS:
            raise RuntimeError(f"selected render requires 16 envs; got {self.env.num_envs}")
        if not bool(self.env.config.simulator.config.get("render_results", False)):
            raise RuntimeError("selected render requires simulator.config.render_results=true")

        # The sibling staging directory is owned only after our mkdir succeeds;
        # all work after that point is inside this try/finally so injected setup
        # failures cannot leave a partial bundle behind.
        staging_owned = False
        committed = False
        policy_model = None
        original_rollout = None
        original_render_results = None
        writers: dict[str, Any] = {}
        first_frames: dict[str, Any] = {}
        frame_diversity: dict[str, bool] = {}
        frame_count = 0
        policy_input_checks = 0
        rollout_patched = False
        render_patched = False
        writers_closed = False

        def close_writers():
            nonlocal writers_closed
            if writers_closed:
                return
            close_error = None
            for writer in writers.values():
                try:
                    writer.close()
                except BaseException as exc:  # preserve cleanup while surfacing writer failure
                    close_error = close_error or exc
            writers_closed = True
            if close_error is not None:
                raise close_error

        try:
            policy_video_dir = staging_root / "policy_camera_videos"
            external_dir = staging_root / "external_debug_videos"
            configured_external = Path(self.env.config.save_rendering_dir).expanduser().resolve()
            if configured_external != external_dir.resolve():
                raise RuntimeError(f"external rendering directory drift: {configured_external}")
            if output_root.exists() or staging_root.exists():
                raise FileExistsError(
                    f"selected render refuses to overwrite final/staging bundle: "
                    f"final={output_root} staging={staging_root}"
                )
            try:
                staging_root.mkdir(parents=True)
            except BaseException:
                # The target was proven absent immediately before mkdir; if a
                # failed mkdir nevertheless materialized it, it is ours to clean.
                staging_owned = staging_root.exists()
                raise
            staging_owned = True
            policy_video_dir.mkdir()
            external_dir.mkdir()

            stage_final_paths = {
                "left_d435": policy_video_dir / f"d435_left_env{selected_env:04d}.mp4",
                "right_d435": policy_video_dir / f"d435_right_env{selected_env:04d}.mp4",
                "head_oem": policy_video_dir / f"oem_head_env{selected_env:04d}.mp4",
            }
            temporary_paths = {
                name: temporary_policy_video_path(path)
                for name, path in stage_final_paths.items()
            }
            if any(
                path.exists()
                for path in (*stage_final_paths.values(), *temporary_paths.values())
            ):
                raise FileExistsError("selected policy video staging output already exists")
            frame_diversity = {name: False for name in stage_final_paths}

            selection_sha256 = sha256_file(selection_path)
            unwrapped = self.accelerator.unwrap_model(self.model)
            if unwrapped.policy is not self.policy_model:
                raise RuntimeError("Student policy identity differs from unwrapped eval policy")
            policy_model = self.policy_model
            original_rollout = policy_model.rollout
            original_render_results = self.env.render_results

            def writer_for(name):
                writer = writers.get(name)
                if writer is None:
                    writer = imageio.get_writer(
                        str(temporary_paths[name]),
                        fps=VIDEO_FPS,
                        codec="libx264",
                        macro_block_size=2,
                    )
                    writers[name] = writer
                return writer

            def selected_external_render(env_ids=None, frame_type="step"):
                ids = torch.tensor([selected_env], device=self.env.device, dtype=torch.long)
                if env_ids is not None:
                    normalized = self.env._normalize_render_env_ids(env_ids)
                    ids = normalized[normalized == selected_env]
                return original_render_results(env_ids=ids, frame_type=frame_type)

            def captured_rollout(*args, **kwargs):
                nonlocal frame_count, policy_input_checks
                obs_dict = kwargs.get("obs_dict")
                if obs_dict is None and args:
                    obs_dict = args[0]
                if not isinstance(obs_dict, Mapping):
                    raise TypeError("Student rollout capture requires an obs_dict mapping")
                if not hasattr(self, "env_episode_completed"):
                    raise RuntimeError("first-episode mask was not initialized before Student rollout")
                if not bool(self.env_episode_completed[selected_env].item()):
                    cameras_cfg = self.env.config.simulator.config.cameras
                    left, right, head = derive_raw_policy_frames_from_observations(
                        obs_dict.get("vision_obs"),
                        obs_dict.get("context_vision_obs"),
                        image_mean=cameras_cfg.image_mean,
                        image_std=cameras_cfg.image_std,
                        env_count=EXPECTED_NUM_ENVS,
                    )
                    validate_policy_camera_contract(
                        left,
                        right,
                        head,
                        obs_dict.get("vision_obs"),
                        obs_dict.get("context_vision_obs"),
                        obs_dict.get("camera_meta"),
                        cameras_cfg,
                        env_count=EXPECTED_NUM_ENVS,
                    )
                    policy_input_checks += 1
                    frames = {
                        "left_d435": left[selected_env].detach().contiguous(),
                        "right_d435": right[selected_env].detach().contiguous(),
                        "head_oem": head[selected_env].detach().contiguous(),
                    }
                    for name, frame in frames.items():
                        if int(frame.max().item()) <= int(frame.min().item()):
                            raise RuntimeError(f"selected {name} frame is constant")
                        previous = first_frames.get(name)
                        if previous is not None and not torch.equal(previous, frame):
                            frame_diversity[name] = True
                        if previous is None:
                            first_frames[name] = frame.detach().clone()
                        writer_for(name).append_data(frame.cpu().numpy())
                    frame_count += 1
                return original_rollout(*args, **kwargs)

            if policy_model is None or original_rollout is None or original_render_results is None:
                raise RuntimeError("selected render policy hooks were not initialized")
            self.env.render_results = selected_external_render
            render_patched = True
            policy_model.rollout = captured_rollout
            rollout_patched = True
            result = base_eval(self)
            replay_metrics = result if isinstance(result, Mapping) else self.env.get_eval_metrics_summary()
            replay_validation = validate_replay_selected_case(selection, replay_metrics)
            if int(replay_metrics.get("completed_episodes", EXPECTED_EPISODES)) != EXPECTED_EPISODES:
                raise RuntimeError("selected render did not complete one episode in each env")
            if frame_count <= 0 or policy_input_checks != frame_count:
                raise RuntimeError(
                    f"policy input/frame mismatch: checks={policy_input_checks}, frames={frame_count}"
                )
            if not all(frame_diversity.values()):
                raise RuntimeError(f"selected policy videos lack frame diversity: {frame_diversity}")
            policy_model.rollout = original_rollout
            rollout_patched = False
            self.env.render_results = original_render_results
            render_patched = False
            close_writers()

            for name, temporary in temporary_paths.items():
                if not temporary.is_file() or temporary.stat().st_size <= 0:
                    raise RuntimeError(f"selected policy video was not written: {temporary}")
                os.replace(temporary, stage_final_paths[name])
            external_videos = sorted(external_dir.glob("*.mp4"))
            validate_external_debug_videos(external_videos, selected_env)
            stage_videos = [*stage_final_paths.values(), *external_videos]
            published_videos = [
                output_root / path.relative_to(staging_root) for path in stage_videos
            ]
            metadata = {
                "schema": "a2_student_v19_render_v2",
                "trial_id": output_root.name,
                "ranking": {
                    "order": list(RENDER_TRIAL_RANKING_ORDER),
                    "replay_outcome": replay_validation["replay_outcome"],
                    "trial_id": output_root.name,
                },
                "selection": {
                    "path": str(selection_path),
                    "sha256": selection_sha256,
                    "case_identity": replay_validation["case_identity"],
                },
                "source_formal_outcome": replay_validation["source_formal_outcome"],
                "replay_outcome": replay_validation["replay_outcome"],
                "outcome_drift": replay_validation["outcome_drift"],
                "source_formal_metrics": {
                    "path": str(Path(selection["source_metrics"]["path"]).resolve()),
                    "sha256": selection["source_metrics"]["sha256"],
                },
                "source_metrics": {
                    "path": str(Path(selection["source_metrics"]["path"]).resolve()),
                    "sha256": selection["source_metrics"]["sha256"],
                },
                "student_policy": {
                    "teacher_rollout": False,
                    "high_level_action_source": "student_policy_action_mean",
                    "leg_action_source": "frozen_a2_base",
                    "policy_input_checks": policy_input_checks,
                },
                "policy_cameras": {
                    "fps": VIDEO_FPS,
                    "frame_count": frame_count,
                    "camera_names": ["ego_camera", "policy_secondary_camera", "policy_context_camera"],
                    "frame_shapes": {name: list(first_frames[name].shape) for name in stage_final_paths},
                    "frame_diversity": frame_diversity,
                    "recomposition": "left/right channel-stacked vision_obs + head context_vision_obs",
                    "camera_meta_dim": 6,
                },
                "external_debug_cameras": {
                    "selected_env_only": True,
                    "video_count": len(external_videos),
                },
                "videos": [
                    {
                        "path": str(path),
                        "size_bytes": stage_path.stat().st_size,
                        "sha256": sha256_file(stage_path),
                    }
                    for path, stage_path in zip(published_videos, stage_videos)
                ],
            }
            atomic_json_write(staging_root / "selected_render_metadata.json", metadata)
            publish_render_bundle(staging_root, output_root)
            staging_owned = False
            committed = True
            print(
                f"[A2_STUDENT_SELECTED_RENDER_PASS] env_id={selected_env} "
                f"frames={frame_count} videos={len(stage_videos)} bundle={output_root}",
                flush=True,
            )
            return result
        finally:
            try:
                if rollout_patched:
                    policy_model.rollout = original_rollout
                if render_patched:
                    self.env.render_results = original_render_results
            finally:
                try:
                    close_writers()
                finally:
                    if staging_owned and not committed and staging_root.exists():
                        shutil.rmtree(staging_root)

    render_eval.__name__ = "selected_student_render_eval"
    render_eval.__qualname__ = "selected_student_render_eval"
    render_eval._a2_eval_base = base_eval
    return render_eval


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("formal", "render", N3_CAPTURE_MODE), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--controller", choices=CONTROLLERS, default="student")
    parser.add_argument(
        "--student-d435i-forward-mode",
        choices=STUDENT_D435I_FORWARD_MODES,
        help="Explicit Student D435 view-forward mode; omitted means sequential.",
    )
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--checkpoint-config", type=Path)
    parser.add_argument("--checkpoint-config-sha256")
    parser.add_argument("--experience-path", type=Path)
    parser.add_argument("--experience-sha256")
    parser.add_argument("--experience-camera-mode")
    parser.add_argument("--expected-global-step", type=int)
    parser.add_argument("--case-seed", type=int, default=EXPECTED_SEED)
    parser.add_argument("--replicate-id", default="replicate01")
    parser.add_argument("--selection-json", type=Path)
    parser.add_argument("--source-metrics", type=Path)
    parser.add_argument("--n3-control-controller", choices=(N3_CONTROL_CONTROLLER,))
    parser.add_argument("--n3-teacher-checkpoint", type=Path)
    parser.add_argument("--n3-teacher-sha256")
    parser.add_argument("--n3-teacher-config", type=Path)
    parser.add_argument("--n3-teacher-config-sha256")
    parser.add_argument("--n3-teacher-manifest", type=Path)
    parser.add_argument("--n3-teacher-manifest-sha256")
    parser.add_argument("--overlay-repository", type=Path, default=REPO_ROOT)
    parser.add_argument("--runtime-repository", type=Path, default=RUNTIME_REPOSITORY)
    args = parser.parse_args()
    if args.mode == "render" and args.selection_json is None:
        parser.error("--selection-json is required for render mode")
    if args.mode == "formal" and (args.selection_json is not None or args.source_metrics is not None):
        parser.error("formal mode does not accept a pre-existing selection/source metrics artifact")
    if args.mode == N3_CAPTURE_MODE and (args.selection_json is not None or args.source_metrics is not None):
        parser.error("N3 capture does not accept a pre-existing selection/source metrics artifact")
    if args.mode == "render" and args.controller != "student":
        parser.error("render mode only supports --controller student")
    if args.student_d435i_forward_mode is not None and (
        args.controller != "student" or args.mode != "formal"
    ):
        parser.error(
            "--student-d435i-forward-mode is only valid for formal Student eval"
        )
    if args.mode == "render" and (
        args.checkpoint is not None
        or args.checkpoint_sha256 is not None
        or args.checkpoint_config is not None
        or args.checkpoint_config_sha256 is not None
        or args.expected_global_step is not None
    ):
        parser.error("render mode does not accept checkpoint identity overrides")
    n3_teacher_values = (
        args.n3_control_controller,
        args.n3_teacher_checkpoint,
        args.n3_teacher_sha256,
        args.n3_teacher_config,
        args.n3_teacher_config_sha256,
        args.n3_teacher_manifest,
        args.n3_teacher_manifest_sha256,
    )
    if args.mode == N3_CAPTURE_MODE:
        if args.controller != N3_PASSIVE_CONTROLLER:
            parser.error("N3 capture requires --controller student")
        if not all(value is not None for value in n3_teacher_values):
            parser.error(
                "N3 capture requires --n3-control-controller plus the exact Teacher "
                "checkpoint/config/manifest paths and SHA256 values"
            )
        if args.expected_global_step != STUDENT_GLOBAL_STEP:
            parser.error(f"N3 capture requires --expected-global-step {STUDENT_GLOBAL_STEP}")
    elif any(value is not None for value in n3_teacher_values):
        parser.error("N3 Teacher identity flags are only valid for N3 capture mode")
    if (args.checkpoint_config is None) != (args.checkpoint_config_sha256 is None):
        parser.error("--checkpoint-config and --checkpoint-config-sha256 must be supplied together")
    experience_values = (
        args.experience_path,
        args.experience_sha256,
        args.experience_camera_mode,
    )
    if any(value is not None for value in experience_values) and not all(
        value is not None for value in experience_values
    ):
        parser.error(
            "--experience-path, --experience-sha256, and --experience-camera-mode "
            "must be supplied together"
        )
    if args.experience_camera_mode is not None and args.experience_camera_mode not in set(
        EXPERIENCE_CAMERA_MODES.values()
    ):
        parser.error(
            "--experience-camera-mode must be one of "
            f"{sorted(EXPERIENCE_CAMERA_MODES.values())}"
        )
    if args.mode == "formal" and args.checkpoint is not None and args.checkpoint_config is None:
        parser.error(
            "formal checkpoint overrides require --checkpoint-config and "
            "--checkpoint-config-sha256 for adjacent-config provenance"
        )
    if args.mode == "formal" and args.controller == "student" and args.checkpoint is not None:
        checkpoint = args.checkpoint.expanduser().resolve()
        if checkpoint != CHECKPOINT and args.expected_global_step is None:
            parser.error("arbitrary Student checkpoints require --expected-global-step")
    if args.mode == "formal" and args.case_seed != EXPECTED_SEED:
        parser.error(f"--case-seed must be exactly {EXPECTED_SEED}")
    if args.mode == N3_CAPTURE_MODE and args.case_seed != EXPECTED_SEED:
        parser.error(f"--case-seed must be exactly {EXPECTED_SEED}")
    if args.mode == N3_CAPTURE_MODE:
        if args.checkpoint is None or args.checkpoint_sha256 is None:
            parser.error("N3 capture requires the exact Student --checkpoint and --checkpoint-sha256")
        if args.checkpoint_config is None or args.checkpoint_config_sha256 is None:
            parser.error("N3 capture requires the adjacent Student config and its SHA256")
    return args


def validate_output_root_preflight(mode: str, output_root: Path) -> None:
    output_root = output_root.expanduser().resolve()
    if mode == "render":
        roots = (output_root, render_staging_root(output_root))
    elif mode == N3_CAPTURE_MODE:
        roots = (output_root, n3_staging_root(output_root))
    elif mode == "formal":
        roots = (output_root,)
    else:
        raise ValueError(f"unknown eval mode {mode!r}")
    for root in roots:
        if root.exists():
            if not root.is_dir():
                raise FileExistsError(f"eval output root is not a directory: {root}")
            if mode in {"render", N3_CAPTURE_MODE}:
                raise FileExistsError(f"{mode} eval refuses existing final/staging target: {root}")
            existing = sorted(path.name for path in root.iterdir())
            if existing:
                raise FileExistsError(
                    f"{mode} eval refuses to overwrite non-empty output root {root}: {existing}"
                )
    runtime_log_root = eval_runtime_log_root(mode, output_root)
    if runtime_log_root.exists():
        raise FileExistsError(
            f"{mode} eval refuses existing Hydra runtime-log root: {runtime_log_root}"
        )


def required_final_artifact_path(
    mode: str, output_root: Path, controller: str = "student"
) -> Path:
    if mode not in {"formal", "render", N3_CAPTURE_MODE}:
        raise ValueError(f"unknown eval mode {mode!r}")
    if controller not in CONTROLLERS:
        raise ValueError(f"unknown controller {controller!r}")
    if mode == "render" and controller != "student":
        raise ValueError("render mode only supports the Student controller")
    if mode == N3_CAPTURE_MODE and controller != N3_PASSIVE_CONTROLLER:
        raise ValueError("N3 capture only supports the passive Student controller")
    output_root = output_root.expanduser().resolve()
    if mode == "render":
        filename = "selected_render_metadata.json"
    elif mode == N3_CAPTURE_MODE:
        filename = N3_MANIFEST_FILENAME
    else:
        filename = "student_selection.json" if controller == "student" else "teacher_selection.json"
    return output_root / filename


def validate_final_artifact(
    mode: str, output_root: Path, controller: str = "student"
) -> Path:
    artifact = required_final_artifact_path(mode, output_root, controller)
    if not artifact.is_file():
        raise RuntimeError(
            f"{mode} eval returned without required final artifact: {artifact}"
        )
    return artifact


def run_eval_entry_with_artifact_guard(
    mode: str, output_root: Path, controller: str = "student"
) -> None:
    """Run the evaluation entry while guarding its successful hard exit."""
    original_exit = os._exit

    def guarded_exit(status: int) -> None:
        if status == 0:
            validate_final_artifact(mode, output_root, controller)
        original_exit(status)

    os._exit = guarded_exit
    try:
        runpy.run_path(str(EVAL_ENTRY), run_name="__main__")
    finally:
        os._exit = original_exit


def main() -> int:
    args = parse_args()
    output_root = args.output_root.expanduser().resolve()
    validate_output_root_preflight(args.mode, output_root)
    controller = args.controller
    if args.checkpoint is None:
        checkpoint = CHECKPOINT if controller == "student" else TEACHER_CHECKPOINT
    else:
        checkpoint = args.checkpoint.expanduser().resolve()
    if controller == "student" and checkpoint == CHECKPOINT:
        expected_global_step = STUDENT_GLOBAL_STEP if args.expected_global_step is None else args.expected_global_step
    elif controller == "teacher":
        expected_global_step = TEACHER_GLOBAL_STEP if args.expected_global_step is None else args.expected_global_step
    else:
        if args.expected_global_step is None:
            raise ValueError("arbitrary Student checkpoints require --expected-global-step")
        expected_global_step = args.expected_global_step
    config_path = (
        checkpoint.with_name("config.yaml")
        if args.checkpoint_config is None
        else args.checkpoint_config.expanduser().resolve()
    )
    if config_path != checkpoint.with_name("config.yaml"):
        raise ValueError(
            "checkpoint config must be the adjacent config.yaml: "
            f"expected={checkpoint.with_name('config.yaml')} got={config_path}"
        )
    if args.mode == N3_CAPTURE_MODE:
        if controller != N3_PASSIVE_CONTROLLER or checkpoint != CHECKPOINT:
            raise ValueError(
                "N3 capture is pinned to the exact passive Student step10000 checkpoint"
            )
        if config_path != CHECKPOINT_CONFIG:
            raise ValueError("N3 capture is pinned to the exact passive Student config.yaml")
    checkpoint_info = validate_checkpoint_artifacts(
        checkpoint,
        config_path,
        controller=controller,
        expected_global_step=expected_global_step,
        expected_sha256=args.checkpoint_sha256,
        expected_config_sha256=args.checkpoint_config_sha256,
    )
    trainer_target = validate_trainer_target(config_path, controller)
    runtime = load_runtime_bootstrap_module()

    overlay = runtime.prepare_overlay_import(args.overlay_repository)
    if args.experience_path is None:
        experience_info = resolve_experience_source(overlay, controller)
    else:
        experience_info = validate_experience_identity(
            {
                "controller": controller,
                "camera_mode": args.experience_camera_mode,
                "path": str(args.experience_path.expanduser().resolve()),
                "sha256": args.experience_sha256,
            },
            overlay,
            controller,
        )
    teacher_info = validate_teacher_identity(runtime)
    if args.mode == N3_CAPTURE_MODE:
        validate_n3_cli_teacher_identity(args, teacher_info)
        validate_n3_teacher_config(config_path, teacher_info)
    runtime.validate_gpu7_environment()
    module_sources = runtime.validate_runtime_repository(args.runtime_repository)
    already_loaded = sorted(set(module_sources).intersection(sys.modules))
    if already_loaded:
        raise RuntimeError(f"v19 runtime modules imported before AppLauncher: {already_loaded}")
    runtime.install_v19_runtime_scenario_file_pin(module_sources)
    sys.meta_path.insert(0, runtime.V19RuntimeFinder(module_sources))
    os.chdir(overlay)

    # Re-read the adjacent config hash immediately before Hydra/config use so
    # a plan→subprocess TOCTOU mutation cannot be silently evaluated.
    checkpoint_info = validate_checkpoint_artifacts(
        checkpoint,
        config_path,
        controller=controller,
        expected_global_step=expected_global_step,
        expected_sha256=checkpoint_info["sha256"],
        expected_config_sha256=checkpoint_info["config_sha256"],
    )
    trainer_target = validate_trainer_target(config_path, controller)

    selection = None
    if args.mode == "render":
        selection, _ = load_sealed_selection(args.selection_json, args.source_metrics)
        sealed_experience = selection.get("experience")
        if not isinstance(sealed_experience, Mapping):
            raise RuntimeError("sealed render selection is missing experience identity")
        for key in ("controller", "camera_mode", "path", "sha256"):
            if sealed_experience.get(key) != experience_info.get(key):
                raise RuntimeError(
                    "sealed render selection experience identity mismatch: "
                    f"key={key!r} selection={sealed_experience.get(key)!r} "
                    f"runtime={experience_info.get(key)!r}"
                )
    overrides = build_hydra_overrides(
        args.mode,
        output_root,
        checkpoint=checkpoint,
        controller=controller,
        student_d435i_forward_mode=args.student_d435i_forward_mode,
    )
    from gr00t.rl.trl.trainer.ppo_trainer_a2_base_api import TRLPPOTrainer as A2TRLPPOTrainer

    trainer_cls, a2_eval = _bind_a2_eval_methods(controller, trainer_target)
    if args.mode == N3_CAPTURE_MODE:
        trainer_cls.eval = _make_n3_capture_eval(
            output_root,
            checkpoint_info,
            teacher_info,
            experience_info,
            overlay_repository=overlay,
            case_seed=args.case_seed,
            replicate_id=args.replicate_id,
        )
    elif args.mode == "formal":
        trainer_cls.eval = _make_formal_eval(
            a2_eval,
            output_root,
            checkpoint_info,
            controller=controller,
            teacher_info=teacher_info,
            case_seed=args.case_seed,
            replicate_id=args.replicate_id,
            experience_info=experience_info,
            overlay_repository=overlay,
            student_d435i_forward_mode=args.student_d435i_forward_mode,
        )
    else:
        trainer_cls.eval = _make_render_eval(
            a2_eval,
            output_root,
            selection,
            args.selection_json.expanduser().resolve(strict=True),
        )

    import argparse as _argparse
    import isaaclab.app as isaaclab_app
    from gr00t.rl import train_agent_trl as gpu_binding

    identity = gpu_binding.A2_GPU_BINDING
    if identity is None:
        raise RuntimeError("A2 GPU binding environment is required for Student eval")
    launcher_holder: dict[str, Any] = {}
    bound = gpu_binding._make_a2_bound_app_launcher_type(isaaclab_app.AppLauncher, identity)

    class VerifiedAppLauncher(bound):
        def __init__(self, *positional, **keyword):
            if len(positional) != 1 or keyword or not isinstance(positional[0], _argparse.Namespace):
                raise TypeError("A2 eval AppLauncher requires one argparse.Namespace")
            cli = positional[0]
            cli.multi_gpu = False
            cli.distributed = False
            cli.device = "cuda:0"
            # Re-read the immutable overlay source immediately before the
            # AppLauncher constructor.  This is the final plan/command to
            # runtime TOCTOU gate; no installed/default Kit fallback exists.
            current_experience = validate_experience_identity(
                experience_info, overlay, controller
            )
            cli.experience = current_experience["path"]
            super().__init__(*positional, **keyword)
            launcher_holder["instance"] = self

    isaaclab_app.AppLauncher = VerifiedAppLauncher
    import accelerate

    original_accelerator = accelerate.Accelerator

    class VerifiedAccelerator(original_accelerator):
        def __init__(self, *positional, **keyword):
            super().__init__(*positional, **keyword)
            gpu_binding._validate_a2_accelerator_binding(self, identity)
            launcher = launcher_holder.get("instance")
            if launcher is None:
                raise RuntimeError("A2 eval Accelerator initialized before AppLauncher")
            gpu_binding._validate_a2_app_launcher_binding(launcher, self, identity)

    accelerate.Accelerator = VerifiedAccelerator
    sys.argv = [str(EVAL_ENTRY), *overrides]
    run_eval_entry_with_artifact_guard(args.mode, output_root, controller)
    validate_final_artifact(args.mode, output_root, controller)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
