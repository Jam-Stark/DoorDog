#!/usr/bin/env python3
"""Offline C-B2H v19 N4 view-utilization and Head-mask diagnostics.

The command consumes the sealed step10000 Student checkpoint and the three
sealed N3 Teacher trajectories.  It never steps IsaacSim, performs backward,
updates an optimizer, or changes model weights.  Each variant starts from a
fresh recurrent state and differs only in camera validity metadata or left/right
input ordering.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT = (
    REPO_ROOT
    / "logs_rl/cb2h_v19_distill/"
    "cb2h_v19_g2s2000_gpu7_64e_10k_fix0f9c11e_retry1/model_step_010000.pt"
).resolve()
CHECKPOINT_CONFIG = CHECKPOINT.with_name("config.yaml")
CHECKPOINT_SHA256 = "005705dc033605a24bc231b18fbfaabe3288a699130a7ce2e423eac736963a45"
CHECKPOINT_CONFIG_SHA256 = "24f94faeca0270928c9c3ff33568e50371dc4f2f3feb767f6fe0607bb084351f"
N3_INPUT_ROOT = (
    REPO_ROOT / "logs_eval/cb2h_pro_phase_a_n3_teacher_trajectories_gpu7-retry1-20260802"
).resolve()
EXPECTED_N3_ROOT_NAME = "cb2h_pro_phase_a_n3_teacher_trajectories_gpu7-retry1-20260802"
EXPECTED_N3_REPLICATES = ("replicate_01", "replicate_02", "replicate_03")
EXPECTED_N3_MANIFEST_IDS = ("n3_rep01", "n3_rep02", "n3_rep03")
TRIVIEW_ACTOR_SOURCE = (
    REPO_ROOT / "gr00t/rl/trl/modules/vision_actor_critic_modules_triview_recurrent.py"
).resolve()
EXPECTED_ENV_COUNT = 16
EXPECTED_ACTION_DIM = 12
EXPECTED_N3_SCHEMA = "a2_cb2h_n3_teacher_trajectory_hdf5_v1"
EXPECTED_N3_PHASE_SCHEMA = "a2_cb2h_pro_phase_a_v1"
EXPECTED_GPU_INDEX = "7"
EXPECTED_GPU_UUID = "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d"
EXPECTED_LOGICAL_DEVICE = "cuda:0"
IMAGE_MEAN = (0.485, 0.456, 0.406)
IMAGE_STD = (0.229, 0.224, 0.225)
VARIANTS = ("FULL", "HEAD_INVALID", "LEFT_INVALID", "RIGHT_INVALID", "LEFT_RIGHT_SWAP")
OBSERVABILITY_KEYS = (
    "feature/d435_left_norm",
    "feature/d435_right_norm",
    "feature/head_norm",
    "feature/manipulation_residual_norm",
    "feature/manipulation_norm",
    "feature/context_gate",
    "feature/head_fixed_contribution_norm",
    "feature/context_residual_gated_norm",
)
HDF5_DATASETS = (
    "actor_obs",
    "left_rgb",
    "right_rgb",
    "head_rgb",
    "camera_meta",
    "teacher_action",
    "pre_action_stage",
    "done",
    "active_mask",
    "env_id",
    "frame_id",
    "episode_index",
    "case_id",
)
HDF5_SHAPES = {
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
HDF5_DTYPES = {
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


@dataclass(frozen=True)
class N3Replicate:
    replicate_id: str
    h5_path: Path
    trajectory_manifest_path: Path
    h5_sha256: str
    trajectory_manifest_sha256: str
    row_count: int
    active_frame_count: int
    case_ids: tuple[str, ...]


@dataclass(frozen=True)
class N3Inputs:
    root: Path
    phase_manifest_path: Path
    phase_manifest_sha256: str
    replicates: tuple[N3Replicate, ...]


@dataclass
class VariantResult:
    actions: Any
    observability: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.expanduser().resolve(strict=True).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_json(path: Path) -> dict[str, Any]:
    with path.expanduser().resolve(strict=True).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"JSON artifact must be an object: {path}")
    return value


def _require_hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA256 string; got {value!r}")
    int(value, 16)
    return value


def _canonicalize_a2_cuda_uuid(value: object) -> str:
    """Convert Torch's exact 16-byte CUDA UUID payload to nvidia-smi form."""
    try:
        raw_value = getattr(value, "bytes")
    except AttributeError as exc:
        raise RuntimeError("A2 CUDA UUID binding must expose a .bytes payload") from exc
    except Exception as exc:
        raise RuntimeError("A2 CUDA UUID .bytes payload could not be read") from exc
    if isinstance(raw_value, (str, int, float, complex, bool)):
        raise RuntimeError("A2 CUDA UUID .bytes payload must be a byte sequence")
    try:
        raw_bytes = bytes(raw_value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("A2 CUDA UUID .bytes payload is not bytes-convertible") from exc
    if len(raw_bytes) != 16:
        raise RuntimeError(
            "A2 CUDA UUID .bytes payload must contain exactly 16 bytes; "
            f"got {len(raw_bytes)}"
        )
    try:
        canonical_uuid = str(uuid.UUID(bytes=raw_bytes))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("A2 CUDA UUID .bytes payload is not a valid UUID") from exc
    return f"GPU-{canonical_uuid}"


def _validate_h5_dataset_contract(handle, expected_rows: int) -> None:
    import numpy as np

    if set(handle.keys()) != set(HDF5_DATASETS):
        raise RuntimeError(
            "N3 HDF5 dataset keys drifted: "
            f"expected={sorted(HDF5_DATASETS)!r} got={sorted(handle.keys())!r}"
        )
    if handle.attrs.get("schema") != EXPECTED_N3_SCHEMA:
        raise RuntimeError(f"N3 HDF5 schema drifted: {handle.attrs.get('schema')!r}")
    if int(handle.attrs.get("expected_envs", -1)) != EXPECTED_ENV_COUNT:
        raise RuntimeError("N3 HDF5 expected_envs must be exactly 16")
    if int(handle.attrs.get("episode_count", -1)) != EXPECTED_ENV_COUNT:
        raise RuntimeError("N3 HDF5 episode_count must be exactly 16")
    for name in HDF5_DATASETS:
        dataset = handle[name]
        if dataset.shape[0] != expected_rows:
            raise RuntimeError(
                f"N3 dataset row count mismatch for {name}: {dataset.shape[0]} vs {expected_rows}"
            )
        expected_shape = (expected_rows, *HDF5_SHAPES[name])
        if tuple(dataset.shape) != expected_shape:
            raise RuntimeError(
                f"N3 dataset shape mismatch for {name}: {tuple(dataset.shape)} vs {expected_shape}"
            )
        if np.dtype(dataset.dtype).str != np.dtype(HDF5_DTYPES[name]).str:
            raise RuntimeError(
                f"N3 dataset dtype mismatch for {name}: {dataset.dtype} vs {HDF5_DTYPES[name]}"
            )


def _validate_step_major_rows(handle, row_count: int) -> tuple[str, ...]:
    import numpy as np

    env_id = handle["env_id"][:]
    frame_id = handle["frame_id"][:]
    active_mask = handle["active_mask"][:]
    done = handle["done"][:]
    case_id = handle["case_id"][:]
    stage = handle["pre_action_stage"][:]
    episode_index = handle["episode_index"][:]
    if row_count % EXPECTED_ENV_COUNT != 0:
        raise RuntimeError("N3 HDF5 row count must be divisible by 16 step-major rows")
    expected_env_row = np.arange(EXPECTED_ENV_COUNT, dtype=np.int16)
    for offset in range(0, row_count, EXPECTED_ENV_COUNT):
        if not np.array_equal(env_id[offset : offset + EXPECTED_ENV_COUNT], expected_env_row):
            raise RuntimeError(f"N3 HDF5 env_id order drifted at row {offset}")
    if not np.isfinite(stage.astype(np.float64)).all():
        raise RuntimeError("N3 pre_action_stage contains non-finite values")
    if not np.array_equal(stage.astype(np.int64), stage):
        raise RuntimeError("N3 pre_action_stage contains non-integral values")
    if np.any(episode_index != 0):
        raise RuntimeError("N3 trajectory dataset must contain episode_index=0 only")
    case_ids: list[str] = []
    for env in range(EXPECTED_ENV_COUNT):
        rows = np.flatnonzero(env_id == env)
        if rows.size != row_count // EXPECTED_ENV_COUNT:
            raise RuntimeError(f"N3 env {env} does not have complete step-major rows")
        env_cases = {bytes(value).decode("ascii") for value in case_id[rows]}
        if len(env_cases) != 1 or len(next(iter(env_cases))) != 64:
            raise RuntimeError(f"N3 env {env} case_id is not stable 64-hex identity")
        case_value = next(iter(env_cases))
        int(case_value, 16)
        case_ids.append(case_value)
        env_active = active_mask[rows]
        env_done = done[rows]
        active_rows = np.flatnonzero(env_active)
        if active_rows.size == 0:
            raise RuntimeError(f"N3 env {env} contains no active frames")
        expected_active_prefix = np.arange(env_active.size) < active_rows.size
        if not np.array_equal(env_active, expected_active_prefix):
            raise RuntimeError(
                f"N3 env {env} active_mask must be exactly one nonempty True prefix followed by False"
            )
        if not np.array_equal(frame_id[rows][active_rows], np.arange(active_rows.size)):
            raise RuntimeError(f"N3 env {env} active frame_id is not contiguous from zero")
        done_rows = np.flatnonzero(env_done)
        if done_rows.size != 1 or int(done_rows[0]) != int(active_rows[-1]):
            raise RuntimeError(f"N3 env {env} must have exactly one terminal done on its last active row")
        if bool(np.any(env_done & ~env_active)):
            raise RuntimeError(f"N3 env {env} has done=true on an inactive row")
    if int(handle.attrs.get("active_frame_count", -1)) != int(active_mask.sum()):
        raise RuntimeError("N3 HDF5 active_frame_count attribute drifted")
    return tuple(case_ids)


def validate_n3_inputs(root: Path = N3_INPUT_ROOT) -> N3Inputs:
    """Validate all three sealed N3 captures and their cross-replicate identity."""
    root = root.expanduser().resolve(strict=True)
    if root.name != EXPECTED_N3_ROOT_NAME:
        raise RuntimeError(f"N4 requires the exact sealed N3 root name; got {root.name!r}")
    phase_path = root / "phase_a_manifest.json"
    phase = _load_json(phase_path)
    if phase.get("schema") != EXPECTED_N3_PHASE_SCHEMA or phase.get("operation") != "n3":
        raise RuntimeError("N3 phase manifest schema/operation drifted")
    if phase.get("replicate_count") != 3 or phase.get("episode_count") != 48:
        raise RuntimeError("N3 phase manifest must contain exactly 3 replicates and 48 episodes")
    if phase.get("case_identity_mapping_equal") is not True:
        raise RuntimeError("N3 phase manifest does not prove equal case identity mapping")
    if phase.get("control_identity", {}).get("controller") != "teacher":
        raise RuntimeError("N3 phase manifest must identify Teacher control")
    phase_artifacts = phase.get("artifacts")
    if not isinstance(phase_artifacts, list):
        raise RuntimeError("N3 phase manifest artifacts must be a list")
    phase_replicates = phase.get("replicates")
    if not isinstance(phase_replicates, list) or len(phase_replicates) != len(EXPECTED_N3_REPLICATES):
        raise RuntimeError("N3 phase manifest must enumerate all three replicate artifacts")
    phase_by_id = {
        item.get("replicate_id"): item
        for item in phase_replicates
        if isinstance(item, Mapping)
    }
    if set(phase_by_id) != set(EXPECTED_N3_MANIFEST_IDS):
        raise RuntimeError("N3 phase replicate identities drifted")

    phase_sha = sha256_file(phase_path)
    declared_phase_artifact = None
    for artifact in phase_artifacts:
        if isinstance(artifact, Mapping) and artifact.get("path") == "phase_a_manifest.json":
            declared_phase_artifact = artifact
            break
    if declared_phase_artifact is not None and _require_hash(
        declared_phase_artifact.get("sha256"), "phase manifest artifact hash"
    ) != phase_sha:
        raise RuntimeError("N3 phase manifest self-artifact hash drifted")

    replicates: list[N3Replicate] = []
    expected_case_ids: tuple[str, ...] | None = None
    for replicate_id, manifest_id in zip(EXPECTED_N3_REPLICATES, EXPECTED_N3_MANIFEST_IDS):
        replicate_root = root / "n3_teacher_trajectories" / replicate_id
        trajectory_path = replicate_root / "n3_teacher_trajectory_manifest.json"
        h5_path = replicate_root / "teacher_trajectory.h5"
        trajectory = _load_json(trajectory_path)
        if trajectory.get("schema") != "a2_cb2h_n3_teacher_trajectory_manifest_v1":
            raise RuntimeError(f"{replicate_id} trajectory manifest schema drifted")
        if trajectory.get("replicate_id") != manifest_id:
            raise RuntimeError(f"{replicate_id} trajectory manifest identity drifted")
        if trajectory.get("backward_call_count") != 0:
            raise RuntimeError(f"{replicate_id} N3 capture reports backward calls")
        if trajectory.get("controller") != "teacher":
            raise RuntimeError(f"{replicate_id} trajectory control identity drifted")
        passive_student = trajectory.get("passive_student")
        if not isinstance(passive_student, Mapping):
            raise RuntimeError(f"{replicate_id} trajectory lacks passive Student identity")
        if (
            passive_student.get("controller") != "student"
            or passive_student.get("global_step") != 10000
            or passive_student.get("path") != str(CHECKPOINT)
            or passive_student.get("config_path") != str(CHECKPOINT_CONFIG)
            or passive_student.get("sha256") != CHECKPOINT_SHA256
            or passive_student.get("config_sha256") != CHECKPOINT_CONFIG_SHA256
        ):
            raise RuntimeError(f"{replicate_id} passive Student identity drifted")
        dataset = trajectory.get("dataset")
        if not isinstance(dataset, Mapping):
            raise RuntimeError(f"{replicate_id} trajectory manifest lacks dataset mapping")
        row_count = int(dataset.get("row_count", -1))
        active_frame_count = int(dataset.get("active_frame_count", -1))
        if row_count <= 0 or active_frame_count <= 0 or not h5_path.is_file():
            raise RuntimeError(f"{replicate_id} trajectory dataset is unavailable")
        declared_h5_hash = _require_hash(dataset.get("sha256"), f"{replicate_id} HDF5 hash")
        declared_h5_path = Path(str(dataset.get("path", ""))).expanduser().resolve()
        if declared_h5_path != h5_path.resolve():
            raise RuntimeError(f"{replicate_id} trajectory manifest HDF5 path drifted")
        phase_entry = phase_by_id[manifest_id]
        phase_dataset = phase_entry.get("dataset")
        if not isinstance(phase_dataset, Mapping):
            raise RuntimeError(f"{replicate_id} phase manifest lacks dataset mapping")
        if (
            phase_dataset.get("path") != str(h5_path.resolve())
            or phase_dataset.get("sha256") != declared_h5_hash
            or phase_dataset.get("row_count") != row_count
            or phase_dataset.get("active_frame_count") != active_frame_count
        ):
            raise RuntimeError(f"{replicate_id} phase dataset identity drifted")
        h5_sha = sha256_file(h5_path)
        if h5_sha != declared_h5_hash:
            raise RuntimeError(f"{replicate_id} HDF5 SHA256 drifted")
        trajectory_sha = sha256_file(trajectory_path)
        _require_phase_trajectory_artifact(
            phase_artifacts,
            expected_relative_path=(
                Path("n3_teacher_trajectories") / replicate_id / trajectory_path.name
            ).as_posix(),
            actual_sha256=trajectory_sha,
            actual_size_bytes=trajectory_path.stat().st_size,
            replicate_id=replicate_id,
        )
        with _open_h5(h5_path) as handle:
            _validate_h5_dataset_contract(handle, row_count)
            if int(handle.attrs.get("active_frame_count", -1)) != active_frame_count:
                raise RuntimeError(f"{replicate_id} HDF5 active_frame_count differs from manifest")
            case_ids = _validate_step_major_rows(handle, row_count)
        if expected_case_ids is None:
            expected_case_ids = case_ids
        elif case_ids != expected_case_ids:
            raise RuntimeError("N3 replicate case identity mapping drifted")
        replicates.append(
            N3Replicate(
                replicate_id=replicate_id,
                h5_path=h5_path,
                trajectory_manifest_path=trajectory_path,
                h5_sha256=h5_sha,
                trajectory_manifest_sha256=trajectory_sha,
                row_count=row_count,
                active_frame_count=active_frame_count,
                case_ids=case_ids,
            )
        )
    return N3Inputs(root, phase_path, phase_sha, tuple(replicates))


def _open_h5(path: Path):
    import h5py

    return h5py.File(path.expanduser().resolve(strict=True), "r")


def _require_phase_trajectory_artifact(
    phase_artifacts: Any,
    *,
    expected_relative_path: str,
    actual_sha256: str,
    actual_size_bytes: int,
    replicate_id: str,
) -> None:
    """Bind one trajectory manifest to exactly one phase artifact record."""
    if not isinstance(phase_artifacts, list):
        raise RuntimeError("N3 phase manifest artifacts must be a list")
    matches = [
        artifact
        for artifact in phase_artifacts
        if isinstance(artifact, Mapping) and artifact.get("path") == expected_relative_path
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{replicate_id} requires exactly one phase artifact for {expected_relative_path}; "
            f"found {len(matches)}"
        )
    artifact = matches[0]
    declared_sha256 = _require_hash(
        artifact.get("sha256"), f"{replicate_id} phase trajectory manifest hash"
    )
    declared_size = artifact.get("size_bytes")
    if isinstance(declared_size, bool) or not isinstance(declared_size, int) or declared_size < 0:
        raise RuntimeError(f"{replicate_id} phase trajectory manifest size is invalid")
    if declared_sha256 != actual_sha256 or declared_size != actual_size_bytes:
        raise RuntimeError(f"{replicate_id} phase trajectory manifest artifact identity drifted")


def variant_contract(variant: str) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown N4 variant {variant!r}; expected {VARIANTS}")
    return {
        "variant": variant,
        "image_content_changed": False,
        "input_order_swapped": variant == "LEFT_RIGHT_SWAP",
        "validity_only": variant in {"HEAD_INVALID", "LEFT_INVALID", "RIGHT_INVALID"},
        "metadata_swapped_with_images": variant == "LEFT_RIGHT_SWAP",
    }


def transform_variant(left, right, head, camera_meta, variant: str):
    """Apply the exact N4 variant contract to one 16-env step slice."""
    import torch

    variant_contract(variant)
    if not all(torch.is_tensor(value) for value in (left, right, head, camera_meta)):
        raise TypeError("N4 variant inputs must be tensors")
    if left.shape != (EXPECTED_ENV_COUNT, 384, 216, 3) or right.shape != left.shape:
        raise ValueError("N4 D435 raw slices must both be [16,384,216,3]")
    if head.shape != (EXPECTED_ENV_COUNT, 136, 384, 3):
        raise ValueError("N4 Head raw slices must be [16,136,384,3]")
    if camera_meta.shape != (EXPECTED_ENV_COUNT, 6):
        raise ValueError("N4 camera_meta slices must be [16,6]")
    left_out, right_out, head_out = left, right, head
    meta_out = camera_meta.clone()
    if variant == "HEAD_INVALID":
        meta_out[:, 5] = 0.0
    elif variant == "LEFT_INVALID":
        meta_out[:, 3] = 0.0
    elif variant == "RIGHT_INVALID":
        meta_out[:, 4] = 0.0
    elif variant == "LEFT_RIGHT_SWAP":
        left_out, right_out = right, left
        meta_out = camera_meta.clone()
        meta_out[:, [0, 1]] = camera_meta[:, [1, 0]]
        meta_out[:, [3, 4]] = camera_meta[:, [4, 3]]
    return left_out, right_out, head_out, meta_out


def build_transition_window_mask(active, env_id, stage, radius: int = 5):
    """Mark active frames within ±``radius`` active frames of stage changes."""
    import numpy as np

    active = np.asarray(active, dtype=bool)
    env_id = np.asarray(env_id)
    stage = np.asarray(stage)
    if active.ndim != 1 or env_id.shape != active.shape or stage.shape != active.shape:
        raise ValueError("transition-window inputs must be equal-length rank-1 arrays")
    if isinstance(radius, bool) or not isinstance(radius, int) or radius < 0:
        raise ValueError("transition window radius must be a non-negative integer")
    result = np.zeros_like(active)
    for env in np.unique(env_id):
        rows = np.flatnonzero((env_id == env) & active)
        for position in np.flatnonzero(np.diff(stage[rows]) != 0):
            start = max(0, int(position + 1 - radius))
            stop = min(rows.size, int(position + 2 + radius))
            result[rows[start:stop]] = True
    return result


def _metric_stats(pred, target, mask):
    import numpy as np

    pred = np.asarray(pred, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    if pred.ndim != 2 or target.shape != pred.shape or pred.shape[1] <= 0:
        raise ValueError("N4 metric actions must be [N,D] with matching target shape")
    if mask.shape != (pred.shape[0],):
        raise ValueError("N4 metric mask length mismatch")
    if not np.isfinite(pred[mask]).all() or not np.isfinite(target[mask]).all():
        raise ValueError("N4 metric actions must be finite")
    count = int(mask.sum())
    if count == 0:
        return {"count": 0}
    error = pred[mask] - target[mask]
    rmse = np.sqrt(np.mean(error * error, axis=0))
    denom = np.std(target[mask], axis=0) + 1.0e-6
    nrmse = rmse / denom
    return {
        "count": count,
        "mse_mean": float(np.mean(error * error)),
        "rmse_mean": float(np.mean(rmse)),
        "nrmse_median_12d": float(np.median(nrmse)),
        "nrmse_max_12d": float(np.max(nrmse)),
        "per_action": {
            "mse": [float(value) for value in np.mean(error * error, axis=0)],
            "rmse": [float(value) for value in rmse],
            "nrmse": [float(value) for value in nrmse],
        },
    }


def _grouped_metric_stats(pred, target, active, stage, transition_window):
    import numpy as np

    groups: dict[str, Any] = {
        "all_active": _metric_stats(pred, target, active),
        "base5": _metric_stats(pred[:, :5], target[:, :5], active),
        "arm7": _metric_stats(pred[:, 5:], target[:, 5:], active),
        "transition_window_pm5_active": _metric_stats(pred, target, transition_window),
    }
    for stage_id in sorted(int(value) for value in np.unique(stage[active])):
        stage_mask = active & (stage == stage_id)
        groups[f"stage_{stage_id}"] = _metric_stats(pred, target, stage_mask)
        groups[f"stage_{stage_id}_base5"] = _metric_stats(pred[:, :5], target[:, :5], stage_mask)
        groups[f"stage_{stage_id}_arm7"] = _metric_stats(pred[:, 5:], target[:, 5:], stage_mask)
    return groups


def classify_h3(metrics: Mapping[str, Any]) -> str:
    full = metrics.get("full_open_loop", {})
    all_active = full.get("all_active", {})
    stage0_base = full.get("stage_0_base5", {})
    median = all_active.get("nrmse_median_12d")
    base_nrmse = stage0_base.get("per_action", {}).get("nrmse")
    if median is None or not isinstance(base_nrmse, list) or not base_nrmse:
        return "INCONCLUSIVE_INSUFFICIENT_ACTIVE_DATA"
    max_stage0_base = max(float(value) for value in base_nrmse)
    if float(median) > 0.40 or max_stage0_base > 0.50:
        return "INSUFFICIENT_OPEN_LOOP_FIT"
    if float(median) <= 0.25 and max_stage0_base <= 0.20:
        return "PASS_REFERENCE_FIT"
    return "INCONCLUSIVE_REFERENCE_BAND"


def _summarize_delta_subset(delta, mask):
    import numpy as np

    active = np.asarray(mask, dtype=bool)
    if int(active.sum()) == 0:
        return {"count": 0}
    selected = delta[active]
    return {
        "count": int(active.sum()),
        "delta_rmse_mean": float(np.sqrt(np.mean(selected * selected))),
        "delta_norm_mean": float(np.linalg.norm(selected, axis=1).mean()),
        "delta_norm_p95": float(np.quantile(np.linalg.norm(selected, axis=1), 0.95)),
        "disagreement_fraction_abs_gt_1e-4": float(np.mean(np.abs(selected) > 1.0e-4)),
        "per_action_delta_rmse": [
            float(value) for value in np.sqrt(np.mean(selected * selected, axis=0))
        ],
    }


def summarize_variant_deltas(
    full_actions,
    variant_actions,
    active,
    *,
    stage=None,
    transition_window=None,
):
    import numpy as np

    full_actions = np.asarray(full_actions, dtype=np.float64)
    variant_actions = np.asarray(variant_actions, dtype=np.float64)
    active = np.asarray(active, dtype=bool)
    if full_actions.shape != variant_actions.shape or full_actions.ndim != 2:
        raise ValueError("N4 variant action arrays must have equal [N,12] shape")
    if active.shape != (full_actions.shape[0],):
        raise ValueError("N4 variant delta active mask length mismatch")
    delta = variant_actions - full_actions
    summary = _summarize_delta_subset(delta, active)
    summary["all_active"] = dict(summary)
    if stage is not None:
        stage = np.asarray(stage)
        if stage.shape != active.shape:
            raise ValueError("N4 variant delta stage length mismatch")
        summary["by_stage"] = {
            str(stage_id): _summarize_delta_subset(
                delta, active & (stage == stage_id)
            )
            for stage_id in sorted(int(value) for value in np.unique(stage[active]))
        }
    if transition_window is not None:
        transition_window = np.asarray(transition_window, dtype=bool)
        if transition_window.shape != active.shape:
            raise ValueError("N4 variant delta transition-window length mismatch")
        summary["transition_window_pm5_active"] = _summarize_delta_subset(
            delta, active & transition_window
        )
    return summary


def validate_gpu_binding(
    device: str = EXPECTED_LOGICAL_DEVICE,
    expected_physical_gpu: str = EXPECTED_GPU_INDEX,
    expected_uuid: str = EXPECTED_GPU_UUID,
) -> dict[str, Any]:
    """Require physical GPU7 exposed as logical cuda:0; never fall back to CPU."""
    if device != EXPECTED_LOGICAL_DEVICE:
        raise RuntimeError(f"N4 requires logical device cuda:0; got {device!r}")
    if str(expected_physical_gpu) != EXPECTED_GPU_INDEX:
        raise RuntimeError("N4 is physically pinned to GPU7")
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if visible != EXPECTED_GPU_INDEX:
        raise RuntimeError(
            "N4 requires CUDA_VISIBLE_DEVICES=7; "
            f"got {visible!r}"
        )
    import torch

    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("N4 requires exactly one visible CUDA device; CPU fallback is forbidden")
    properties = torch.cuda.get_device_properties(0)
    actual_uuid = _canonicalize_a2_cuda_uuid(getattr(properties, "uuid", None))
    if actual_uuid != expected_uuid:
        raise RuntimeError(f"N4 GPU UUID mismatch: expected {expected_uuid}, got {actual_uuid}")
    declared_uuid = os.environ.get("A2_EXPECTED_GPU_UUID")
    if declared_uuid is not None and declared_uuid != expected_uuid:
        raise RuntimeError("A2_EXPECTED_GPU_UUID does not match the pinned GPU7 UUID")
    return {
        "physical_gpu_index": EXPECTED_GPU_INDEX,
        "logical_device": EXPECTED_LOGICAL_DEVICE,
        "uuid": actual_uuid,
        "name": str(properties.name),
        "cuda_visible_devices": visible,
        "training_performed": False,
        "backward_call_count": 0,
        "optimizer_step_count": 0,
    }


def _model_from_exact_checkpoint(checkpoint: Path, config_path: Path, device: str):
    import copy
    import torch
    from hydra.utils import instantiate
    from omegaconf import OmegaConf

    cfg = OmegaConf.load(config_path.expanduser().resolve(strict=True))
    actor_cfg = OmegaConf.to_container(cfg.algo.config.actor, resolve=True)
    actor_cfg = copy.deepcopy(actor_cfg)
    # The sealed step10000 config predates the explicit forward-mode contract;
    # N4 pins the same sequential mode used by the formal Student evaluator.
    actor_cfg["view_contract"]["d435i_forward_mode"] = "sequential"
    for name in ("d435i_vision_module", "head_vision_module"):
        layer = actor_cfg["backbone"][name]["module_config_dict"]["layer_config"]
        layer["pretrained"] = False
    env_config = SimpleNamespace(
        robot=SimpleNamespace(
            algo_obs_dim_dict={
                "actor_obs": 81,
                "vision_obs": 384 * 216 * 6,
                "context_vision_obs": 136 * 384 * 3,
                "camera_meta": 6,
            },
            actions_dim=12,
        )
    )
    # Passing the whole saved config would ask Hydra to resolve unrelated
    # training-only interpolations (teacher paths, simulator resolvers, ...).
    # The actor contract needs only these scalar noise settings; keeping this
    # minimal also prevents accidental training configuration use.
    algo_config = OmegaConf.create(
        {
            "init_noise_std": cfg.algo.config.init_noise_std,
            "freeze_noise_std": cfg.algo.config.freeze_noise_std,
            "clamp_noise_std": cfg.algo.config.clamp_noise_std,
            "max_noise_std": cfg.algo.config.max_noise_std,
            "module_dim": OmegaConf.to_container(cfg.algo.config.module_dim, resolve=True),
        }
    )
    module_dim_dict = OmegaConf.to_container(algo_config.module_dim, resolve=True)
    model = instantiate(
        actor_cfg,
        env_config=env_config,
        algo_config=algo_config,
        module_dim_dict=module_dim_dict,
        _recursive_=False,
    )
    payload = torch.load(checkpoint.expanduser().resolve(strict=True), map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping) or not isinstance(payload.get("policy_state_dict"), Mapping):
        raise RuntimeError("N4 checkpoint must contain a policy_state_dict mapping")
    model.load_state_dict(payload["policy_state_dict"], strict=True)
    model.to(device)
    model.eval()
    return model


def _read_step(handle, offset: int):
    import torch

    end = offset + EXPECTED_ENV_COUNT
    return {
        "actor_obs": torch.from_numpy(handle["actor_obs"][offset:end]),
        "left_rgb": torch.from_numpy(handle["left_rgb"][offset:end]),
        "right_rgb": torch.from_numpy(handle["right_rgb"][offset:end]),
        "head_rgb": torch.from_numpy(handle["head_rgb"][offset:end]),
        "camera_meta": torch.from_numpy(handle["camera_meta"][offset:end]),
        "teacher_action": torch.from_numpy(handle["teacher_action"][offset:end]),
        "pre_action_stage": handle["pre_action_stage"][offset:end],
        "done": handle["done"][offset:end],
        "active_mask": handle["active_mask"][offset:end],
        "env_id": handle["env_id"][offset:end],
        "frame_id": handle["frame_id"][offset:end],
        "case_id": handle["case_id"][offset:end],
    }


def _normalise_step(raw, device):
    import torch
    from gr00t.rl.utils.a2_policy_camera import (
        compose_channel_stacked_dual_rgb,
        normalize_head_context_rgb,
    )

    left, right, head, meta = transform_variant(
        raw["left_rgb"], raw["right_rgb"], raw["head_rgb"], raw["camera_meta"], raw["variant"]
    )
    vision = compose_channel_stacked_dual_rgb(
        left.to(device), right.to(device), resolution=(384, 216), image_mean=IMAGE_MEAN, image_std=IMAGE_STD
    )
    context = normalize_head_context_rgb(
        head.to(device), resolution=(136, 384), image_mean=IMAGE_MEAN, image_std=IMAGE_STD
    )
    actor_obs = raw["actor_obs"].to(device=device, dtype=torch.float32)
    camera_meta = meta.to(device=device, dtype=torch.float32)
    return {
        "actor_obs": actor_obs,
        "vision_obs": vision,
        "context_vision_obs": context,
        "camera_meta": camera_meta,
    }


def evaluate_variant(model, replicate: N3Replicate, variant: str, device: str) -> VariantResult:
    """Run one variant over one row-major N3 replicate from fresh LSTM state."""
    import numpy as np
    import torch

    if variant not in VARIANTS:
        raise ValueError(f"unknown N4 variant {variant!r}")
    model.init_rollout()
    model.reset(torch.ones(EXPECTED_ENV_COUNT, dtype=torch.bool, device=device))
    actions: list[np.ndarray] = []
    feature_rows: dict[str, list[np.ndarray]] = {key: [] for key in OBSERVABILITY_KEYS}
    with _open_h5(replicate.h5_path) as handle:
        for offset in range(0, replicate.row_count, EXPECTED_ENV_COUNT):
            raw = _read_step(handle, offset)
            raw["variant"] = variant
            obs = _normalise_step(raw, device)
            # Memory.forward stores recurrent hidden state.  inference_mode()
            # would create inference tensors that Memory.reset() cannot mutate
            # on the following done update under PyTorch 2.7; no_grad keeps the
            # lifecycle mutation-compatible while still disabling autograd.
            with torch.no_grad():
                action = model.act_inference(obs)
            if not torch.is_tensor(action) or tuple(action.shape) != (EXPECTED_ENV_COUNT, EXPECTED_ACTION_DIM):
                raise RuntimeError(f"N4 model action shape drifted for {variant}: {getattr(action, 'shape', None)}")
            if not bool(torch.all(torch.isfinite(action)).item()):
                raise RuntimeError(f"N4 model produced non-finite actions for {variant}")
            snapshot_fn = getattr(model, "get_observability_snapshot", None)
            if not callable(snapshot_fn):
                raise RuntimeError("N4 model must expose per-sample observability")
            snapshot = snapshot_fn(per_sample=True)
            if set(snapshot) != set(OBSERVABILITY_KEYS):
                raise RuntimeError(
                    "N4 observability key set drifted: "
                    f"expected={OBSERVABILITY_KEYS!r} got={tuple(sorted(snapshot))!r}"
                )
            for key in OBSERVABILITY_KEYS:
                value = snapshot[key]
                if not torch.is_tensor(value) or tuple(value.shape) != (EXPECTED_ENV_COUNT,):
                    raise RuntimeError(f"N4 observability {key} must be per-sample [16]")
                if not bool(torch.all(torch.isfinite(value)).item()):
                    raise RuntimeError(f"N4 observability {key} contains non-finite values")
                feature_rows[key].append(value.detach().cpu().numpy().astype(np.float32, copy=True))
            actions.append(action.detach().cpu().numpy().astype(np.float32, copy=True))
            done = torch.from_numpy(raw["done"]).to(device=device, dtype=torch.bool)
            model.reset(done)
    model.clear_rollout()
    return VariantResult(
        actions=np.concatenate(actions, axis=0),
        observability={key: np.concatenate(rows, axis=0) for key, rows in feature_rows.items()},
    )


def _aggregate_replicate_metrics(raw, results: Mapping[str, VariantResult]):
    import numpy as np

    active = raw["active_mask"].astype(bool)
    stage = raw["pre_action_stage"].astype(np.int64)
    transition = build_transition_window_mask(active, raw["env_id"], stage, radius=5)
    full = results["FULL"].actions
    teacher = raw["teacher_action"].astype(np.float32)
    metrics: dict[str, Any] = {
        "full_open_loop": _grouped_metric_stats(full, teacher, active, stage, transition),
        "variant_deltas": {
            variant: summarize_variant_deltas(
                full,
                results[variant].actions,
                active,
                stage=stage,
                transition_window=transition,
            )
            for variant in VARIANTS
            if variant != "FULL"
        },
        "transition_window_definition": "For each env, detect adjacent active pre_action_stage changes and include the current transition frame plus ±5 active frames in that env.",
        "active_frame_count": int(active.sum()),
        "stage_counts": {
            str(stage_id): int(np.sum(active & (stage == stage_id)))
            for stage_id in sorted(int(value) for value in np.unique(stage[active]))
        },
    }
    metrics["h4_h6_diagnostic_evidence"] = {
        "diagnostic_only": True,
        "head_gate_p95": float(np.quantile(results["FULL"].observability["feature/context_gate"][active], 0.95)),
        "head_invalid_action_delta_norm_mean": metrics["variant_deltas"]["HEAD_INVALID"]["delta_norm_mean"],
        "left_invalid_action_delta_norm_mean": metrics["variant_deltas"]["LEFT_INVALID"]["delta_norm_mean"],
        "right_invalid_action_delta_norm_mean": metrics["variant_deltas"]["RIGHT_INVALID"]["delta_norm_mean"],
        "left_right_swap_action_delta_norm_mean": metrics["variant_deltas"]["LEFT_RIGHT_SWAP"]["delta_norm_mean"],
    }
    return metrics, transition


def run_n4_diagnostic(
    model,
    inputs: N3Inputs,
    output_root: Path,
    *,
    device: str = EXPECTED_LOGICAL_DEVICE,
    gpu_identity: Mapping[str, Any] | None = None,
    checkpoint_info: Mapping[str, Any] | None = None,
    config_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all five variants and atomically seal compact outputs."""
    import numpy as np

    output_root = output_root.expanduser().resolve()
    staging = output_root.with_name(f".{output_root.name}.writing")
    if output_root.exists() or staging.exists():
        raise FileExistsError(f"N4 refuses existing output/staging roots: {output_root} {staging}")
    staging.mkdir(parents=True)
    try:
        all_metric_inputs: list[dict[str, Any]] = []
        artifact_replicate: list[np.ndarray] = []
        artifact_env: list[np.ndarray] = []
        artifact_frame: list[np.ndarray] = []
        artifact_stage: list[np.ndarray] = []
        artifact_case: list[np.ndarray] = []
        artifact_active: list[np.ndarray] = []
        artifact_teacher: list[np.ndarray] = []
        artifact_actions: list[np.ndarray] = []
        artifact_observability: list[np.ndarray] = []
        artifact_transition: list[np.ndarray] = []
        for replicate_index, replicate in enumerate(inputs.replicates):
            raw_parts: dict[str, list[Any]] = {key: [] for key in ("teacher_action", "active_mask", "env_id", "frame_id", "case_id", "pre_action_stage")}
            with _open_h5(replicate.h5_path) as handle:
                for offset in range(0, replicate.row_count, EXPECTED_ENV_COUNT):
                    for key in raw_parts:
                        raw_parts[key].append(handle[key][offset : offset + EXPECTED_ENV_COUNT])
            raw = {key: np.concatenate(value, axis=0) for key, value in raw_parts.items()}
            results = {
                variant: evaluate_variant(model, replicate, variant, device)
                for variant in VARIANTS
            }
            metrics, transition = _aggregate_replicate_metrics(raw, results)
            metrics["replicate_id"] = replicate.replicate_id
            all_metric_inputs.append(metrics)
            active = raw["active_mask"].astype(bool)
            active_rows = np.flatnonzero(active)
            artifact_replicate.append(np.full(active_rows.size, replicate_index, dtype=np.int16))
            artifact_env.append(raw["env_id"][active_rows].astype(np.int16))
            artifact_frame.append(raw["frame_id"][active_rows].astype(np.int64))
            artifact_stage.append(raw["pre_action_stage"][active_rows].astype(np.int16))
            artifact_case.append(raw["case_id"][active_rows].astype("S64"))
            artifact_active.append(active[active_rows])
            artifact_teacher.append(raw["teacher_action"][active_rows].astype(np.float32))
            artifact_actions.append(
                np.stack([results[variant].actions[active_rows] for variant in VARIANTS], axis=1)
            )
            artifact_observability.append(
                np.stack(
                    [
                        np.stack([results[variant].observability[key][active_rows] for key in OBSERVABILITY_KEYS], axis=1)
                        for variant in VARIANTS
                    ],
                    axis=1,
                )
            )
            artifact_transition.append(transition[active_rows])

        metrics_payload: dict[str, Any] = {
            "schema": "a2_cb2h_n4_metrics_v1",
            "operation": "n4",
            "variants": list(VARIANTS),
            "replicate_metrics": all_metric_inputs,
            "diagnostic_only": True,
            "training_performed": False,
            "backward_call_count": 0,
            "optimizer_step_count": 0,
            "observability_keys": list(OBSERVABILITY_KEYS),
        }
        aggregate_actions = np.concatenate(artifact_actions, axis=0)
        aggregate_teacher = np.concatenate(artifact_teacher, axis=0)
        aggregate_active = np.concatenate(artifact_active, axis=0).astype(bool)
        aggregate_stage = np.concatenate(artifact_stage, axis=0).astype(np.int64)
        aggregate_transition = np.concatenate(artifact_transition, axis=0).astype(bool)
        aggregate_full = _grouped_metric_stats(
            aggregate_actions[:, 0, :],
            aggregate_teacher,
            aggregate_active,
            aggregate_stage,
            aggregate_transition,
        )
        metrics_payload["aggregate_metrics"] = {
            "full_open_loop": aggregate_full,
            "variant_deltas": {
                variant: summarize_variant_deltas(
                    aggregate_actions[:, 0, :],
                    aggregate_actions[:, variant_index, :],
                    aggregate_active,
                    stage=aggregate_stage,
                    transition_window=aggregate_transition,
                )
                for variant_index, variant in enumerate(VARIANTS)
                if variant != "FULL"
            },
            "active_frame_count": int(aggregate_active.sum()),
        }
        aggregate_observability = np.concatenate(artifact_observability, axis=0)
        metrics_payload["aggregate_metrics"]["h4_h6_diagnostic_evidence"] = {
            "diagnostic_only": True,
            "head_gate_p95": float(np.quantile(aggregate_observability[:, 0, 5], 0.95)),
            "head_invalid_action_delta_norm_mean": metrics_payload["aggregate_metrics"]["variant_deltas"]["HEAD_INVALID"]["delta_norm_mean"],
            "left_invalid_action_delta_norm_mean": metrics_payload["aggregate_metrics"]["variant_deltas"]["LEFT_INVALID"]["delta_norm_mean"],
            "right_invalid_action_delta_norm_mean": metrics_payload["aggregate_metrics"]["variant_deltas"]["RIGHT_INVALID"]["delta_norm_mean"],
            "left_right_swap_action_delta_norm_mean": metrics_payload["aggregate_metrics"]["variant_deltas"]["LEFT_RIGHT_SWAP"]["delta_norm_mean"],
        }
        metrics_payload["h3_classification"] = classify_h3(metrics_payload["aggregate_metrics"])
        metrics_path = staging / "n4_metrics.json"
        metrics_path.write_text(json.dumps(metrics_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        artifact_path = staging / "n4_active_frames.npz"
        np.savez_compressed(
            artifact_path,
            replicate_index=np.concatenate(artifact_replicate),
            env_id=np.concatenate(artifact_env),
            frame_id=np.concatenate(artifact_frame),
            pre_action_stage=np.concatenate(artifact_stage),
            case_id=np.concatenate(artifact_case),
            active_mask=np.concatenate(artifact_active),
            teacher_action=np.concatenate(artifact_teacher),
            actions=np.concatenate(artifact_actions),
            observability=np.concatenate(artifact_observability),
            transition_window_pm5_active=np.concatenate(artifact_transition),
            variant_names=np.asarray(VARIANTS, dtype="S16"),
            observability_names=np.asarray(OBSERVABILITY_KEYS, dtype="S64"),
        )
        manifest: dict[str, Any] = {
            "schema": "a2_cb2h_n4_view_diagnostic_manifest_v1",
            "operation": "n4",
            "variants": [variant_contract(variant) for variant in VARIANTS],
            "source": {
                "n4_runner": {
                    "path": str(Path(__file__).resolve()),
                    "sha256": sha256_file(Path(__file__).resolve()),
                },
                "triview_actor": {
                    "path": str(TRIVIEW_ACTOR_SOURCE),
                    "sha256": sha256_file(TRIVIEW_ACTOR_SOURCE),
                },
            },
            "checkpoint": dict(checkpoint_info or {}),
            "config": dict(config_info or {}),
            "n3_input": {
                "root": str(inputs.root),
                "phase_manifest_path": str(inputs.phase_manifest_path),
                "phase_manifest_sha256": inputs.phase_manifest_sha256,
                "replicates": [
                    {
                        "replicate_id": rep.replicate_id,
                        "h5_path": str(rep.h5_path),
                        "h5_sha256": rep.h5_sha256,
                        "trajectory_manifest_path": str(rep.trajectory_manifest_path),
                        "trajectory_manifest_sha256": rep.trajectory_manifest_sha256,
                        "row_count": rep.row_count,
                        "active_frame_count": rep.active_frame_count,
                        "case_ids": list(rep.case_ids),
                    }
                    for rep in inputs.replicates
                ],
            },
            "gpu_identity": dict(gpu_identity or {}),
            "outputs": {
                "metrics": {"path": str(output_root / metrics_path.name), "sha256": sha256_file(metrics_path)},
                "active_frames": {"path": str(output_root / artifact_path.name), "sha256": sha256_file(artifact_path)},
            },
            "training_performed": False,
            "backward_call_count": 0,
            "optimizer_step_count": 0,
            "sealed": True,
        }
        content_hash = hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()
        manifest["manifest_content_sha256"] = content_hash
        manifest_path = staging / "n4_provenance_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(staging, output_root)
        # The manifest is intentionally excluded from its own on-disk content
        # hash.  Hash the actual post-rename path only for the returned result.
        manifest_path = output_root / manifest_path.name
        manifest["manifest_file_sha256"] = sha256_file(manifest_path)
        return manifest
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--config", dest="config_path", type=Path, default=CHECKPOINT_CONFIG)
    parser.add_argument("--n3-root", type=Path, default=N3_INPUT_ROOT)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "logs_eval/cb2h_pro_n4_view_diagnostic_step10000_gpu7-20260802",
    )
    parser.add_argument("--device", default=EXPECTED_LOGICAL_DEVICE)
    parser.add_argument("--expected-physical-gpu", default=EXPECTED_GPU_INDEX)
    parser.add_argument("--expected-gpu-uuid", default=EXPECTED_GPU_UUID)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.checkpoint.expanduser().resolve() != CHECKPOINT:
        raise RuntimeError("N4 checkpoint is pinned to the exact step10000 Student checkpoint")
    if args.config_path.expanduser().resolve() != CHECKPOINT_CONFIG:
        raise RuntimeError("N4 config is pinned to the adjacent step10000 Student config")
    gpu_identity = validate_gpu_binding(args.device, args.expected_physical_gpu, args.expected_gpu_uuid)
    from gr00t.rl.scripts.run_a2_student_eval_v19 import validate_checkpoint_artifacts

    checkpoint_info = validate_checkpoint_artifacts(
        args.checkpoint,
        args.config_path,
        controller="student",
        expected_global_step=10000,
        expected_sha256=CHECKPOINT_SHA256,
        expected_config_sha256=CHECKPOINT_CONFIG_SHA256,
    )
    inputs = validate_n3_inputs(args.n3_root)
    model = _model_from_exact_checkpoint(args.checkpoint, args.config_path, args.device)
    manifest = run_n4_diagnostic(
        model,
        inputs,
        args.output_root,
        device=args.device,
        gpu_identity=gpu_identity,
        checkpoint_info=checkpoint_info,
        config_info={
            "path": str(args.config_path.resolve()),
            "sha256": CHECKPOINT_CONFIG_SHA256,
            "d435i_forward_mode": "sequential",
        },
    )
    print(
        f"[A2_N4_PASS] variants={len(VARIANTS)} active_frames={sum(rep.active_frame_count for rep in inputs.replicates)} "
        f"output={args.output_root.resolve()} manifest_content_sha256={manifest['manifest_content_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
