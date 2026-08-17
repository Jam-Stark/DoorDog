#!/usr/bin/env python3
"""Standalone C-B2H toe-out20 four-rank training lifecycle.

``--mode dry-run`` is read-only: it validates the geometry/topology/batch and
Teacher provenance contracts, then prints the exact sealed plan without
creating an output directory or launching Kit.  The other modes expose the
same sealed commands for an explicitly provisioned GPU4-7 runtime.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_NAME = "wbmanip/door_open_a2_base_v19_p2_b2h_toeout6_mgpu"
ARCHITECTURE_ID = "C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2"
TOPOLOGY_ID = "A2-ACCELERATE-DDP-4RANK-64E-V1"
GPU_BINDING_MODE = "accelerate-ddp-4rank-64e-v1"
CUDA_VISIBLE_DEVICES = "4,5,6,7"
MASTER_PORT = 29640
POST_SEAL_TEARDOWN_BOUNDARY_S = 600
# The 2026-08-04 formal attempt was aborted by a six-hour wall-time limit at
# global_step 2195 with zero training exceptions.  The measured rank iteration
# time was 8.43-8.58s, so the sealed 8000-iteration contract needs about
# 67,600s of training on top of process start-up and teardown.  Twenty-four
# hours covers the sealed contract end to end; it is not a retry budget.
FORMAL_PROCESS_TIMEOUT_S = 86400
ADMISSION_PROCESS_TIMEOUT_S = 3600
TOEOUT_BOOTSTRAP_PROFILE = "toeout-no-panorama"
CHILD_LOG_FILENAME = "owned_child.stdout-stderr.log"
EXPECTED_RUNTIME_COMMIT = "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"
RUNTIME_MODULES = {
    "gr00t.rl.envs.door.door_open_a2_base": "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t.rl.data.tasks.door.scenario_cfg.isaacsim": (
        "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"
    ),
    "gr00t.rl.isaac_utils.playground.env_rand.door": (
        "gr00t/rl/isaac_utils/playground/env_rand/door.py"
    ),
}
PHYSICAL_GPU_UUIDS = {
    4: "GPU-20093912-98d6-3c89-9517-3ac344e38fc3",
    5: "GPU-b126539d-3319-a583-f61d-55879b327ddb",
    6: "GPU-4ac67b5e-dc39-3565-d84b-1e7ce20127fa",
    7: "GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d",
}
LOGICAL_TO_PHYSICAL = {rank: rank + 4 for rank in range(4)}
LOGICAL_TO_UUID = {rank: PHYSICAL_GPU_UUIDS[rank + 4] for rank in range(4)}

TEACHER_CHECKPOINT = Path(
    "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/"
    "base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
)
TEACHER_CONFIG = TEACHER_CHECKPOINT.with_name("config.yaml")
TEACHER_MANIFEST = (
    REPO_ROOT
    / "logs_rl/cb2h_v19_runtime/g2_step2000_c18_reconstruction_candidate6168e6a2/teacher_manifest.json"
)
TEACHER_RUNTIME_REPOSITORY = Path("/tmp/cb2h_v19_runtime.waPJHftX/c18")
ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TEACHER_PROVENANCE = {
    "checkpoint": {
        "path": str(TEACHER_CHECKPOINT),
        "sha256": "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d",
    },
    "config": {
        "path": str(TEACHER_CONFIG),
        "sha256": "65c1537b38d670097bc8498428e0aad1705c3fd66eeef41a93d63e3b6da4cf96",
    },
    "manifest": {
        "path": str(TEACHER_MANIFEST),
        "sha256": "479f4460d4dc05feea9d87d3189fa0617b21078f91b6f5176f4a9c41b141d1b7",
    },
    "runtime_repository": "/tmp/cb2h_v19_runtime.waPJHftX/c18",
    "runtime_commit": "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a",
    "checkpoint_load": {"checkpoint": None, "auto_load_latest": False, "source": "immutable_teacher_only"},
}

OUTPUT_ROOT = REPO_ROOT / "logs_rl/by_batch/cb2h_v19_toeout6_pitch50_20260805"
MODE_OUTPUTS = {
    "geometry": OUTPUT_ROOT / "geometry_gpu4",
    "admission": OUTPUT_ROOT / "admission_4x64_gpu4-7",
    "formal": OUTPUT_ROOT / "formal_4x64_8k_gpu4-7_timeoutfix_retry",
}
TEACHER_RENDER_ROOT = REPO_ROOT / "logs_eval/by_batch/cb2h_v19_toeout6_pitch50_20260804/teacher_manual_render_gpu4"
TEACHER_RENDER_MANIFEST = TEACHER_RENDER_ROOT / "teacher_render_manifest.json"
TEACHER_RENDER_MANIFEST_SHA256 = "df39fbb4f5d93dc0cf68785f717b9dc7d6f133f3d7cb2a2d4cfa22b6a2d04d8d"

HEAD_POS = (0.3381, 0.0336, 0.0525)
HEAD_ROT = (1.0, 0.0, 0.0, 0.0)

MIXED_ROLLOUT_SCHEDULE = (
    {"phase": "L0", "start_step": 0, "end_step": 1000, "ratio": 1.0, "teacher_count": 256},
    {"phase": "L1", "start_step": 1000, "end_step": 2000, "ratio": 0.75, "teacher_count": 192},
    {"phase": "L2", "start_step": 2000, "end_step": 4000, "ratio": 0.5, "teacher_count": 128},
    {"phase": "L3", "start_step": 4000, "end_step": 8000, "ratio": 0.25, "teacher_count": 64},
)
ADMISSION_ROLLOUT_SCHEDULE = (
    {"phase": "L0", "start_step": 0, "end_step": 1, "ratio": 1.0, "teacher_count": 256},
)

GEOMETRY_CAMERA_CONFIG = "d435i_dual_portrait_up50_a2_head_oem_toeout6"
GEOMETRY_SOURCE_CAMERA_CONFIG = "d435i_dual_portrait_up60_a2_head_oem_toein20"
GEOMETRY_LEFT_VIEW = "d435i_left_portrait_up50_toeout6"
GEOMETRY_RIGHT_VIEW = "d435i_right_portrait_up50_toeout6"
GEOMETRY_HEAD_VIEW = "a2_head_oem"
TOEOUT6_LEFT_POS = (0.215, 0.065, 0.165)
TOEOUT6_LEFT_ROT = (0.905065723713, 0.022118130854, -0.422039078101, 0.047432484685)
TOEOUT6_LEFT_RPY = (0.0, -50.0, 6.0)
TOEOUT6_RIGHT_POS = (0.215, -0.065, 0.165)
TOEOUT6_RIGHT_ROT = (0.905065723713, -0.022118130854, -0.422039078101, -0.047432484685)
TOEOUT6_RIGHT_RPY = (0.0, -50.0, -6.0)
TOEOUT6_GEOMETRY = {
    "left": {"position_m": TOEOUT6_LEFT_POS, "rotation_wxyz": TOEOUT6_LEFT_ROT, "rpy_deg": TOEOUT6_LEFT_RPY},
    "right": {"position_m": TOEOUT6_RIGHT_POS, "rotation_wxyz": TOEOUT6_RIGHT_ROT, "rpy_deg": TOEOUT6_RIGHT_RPY},
    "head": {"position_m": HEAD_POS, "rotation_wxyz": HEAD_ROT, "rpy_deg": (0.0, 0.0, 0.0)},
}
TEACHER_RENDER_VIEWS = (GEOMETRY_LEFT_VIEW, GEOMETRY_RIGHT_VIEW, GEOMETRY_HEAD_VIEW)
TEACHER_RENDER_SIDE_BY_SIDE_VIEW = "d435i_left_right_side_by_side"
GEOMETRY_ENV_CONFIG_ALLOWLIST = frozenset(
    {"a2_camera_pose_sweep", "a2_camera_scheme_c"}
)
GEOMETRY_LEGACY_TASK_KEYS = frozenset(
    {"a2_stage4_release_hinge_threshold", "a2_stage45_door_frame_contact_scale"}
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_exclusive_child_log(root: Path, rank: int | None = None):
    path = (
        root / CHILD_LOG_FILENAME
        if rank is None
        else root / "ranks" / f"rank{rank}" / CHILD_LOG_FILENAME
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    return os.fdopen(descriptor, "wb", buffering=0), path


def _finalize_child_log(stream, path: Path | None) -> dict[str, Any] | None:
    if stream is None or path is None:
        return None
    stream.flush()
    stream.close()
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }


def _finite_tuple(value: Any, length: int, name: str) -> tuple[float, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not hasattr(value, "__iter__"):
        raise ValueError(f"{name} must be a numeric sequence")
    values = tuple(value)
    if len(values) != length or any(isinstance(item, bool) for item in values):
        raise ValueError(f"{name} must contain exactly {length} numeric values")
    try:
        result = tuple(float(item) for item in values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain numeric values") from exc
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} must contain finite values")
    return result


def quaternion_forward_y(rotation_wxyz: Any) -> float:
    w, x, y, z = _finite_tuple(rotation_wxyz, 4, "rotation_wxyz")
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1.0e-6):
        raise ValueError(f"rotation_wxyz must be normalized; norm={norm!r}")
    return 2.0 * (x * y + w * z)


def validate_toeout6_geometry(
    left_pos: Any = TOEOUT6_LEFT_POS,
    left_rot: Any = TOEOUT6_LEFT_ROT,
    right_pos: Any = TOEOUT6_RIGHT_POS,
    right_rot: Any = TOEOUT6_RIGHT_ROT,
) -> dict[str, Any]:
    """Validate mirrored world quaternions and outward principal rays."""
    left_position = _finite_tuple(left_pos, 3, "left_pos")
    right_position = _finite_tuple(right_pos, 3, "right_pos")
    left_rotation = _finite_tuple(left_rot, 4, "left_rot")
    right_rotation = _finite_tuple(right_rot, 4, "right_rot")
    quaternion_forward_y(left_rotation)
    quaternion_forward_y(right_rotation)
    if not math.isclose(left_position[0], right_position[0], abs_tol=1.0e-9):
        raise ValueError("left/right X positions must match")
    if not math.isclose(left_position[2], right_position[2], abs_tol=1.0e-9):
        raise ValueError("left/right Z positions must match")
    if not math.isclose(left_position[1], -right_position[1], abs_tol=1.0e-9):
        raise ValueError("left/right Y positions must be mirrored")
    expected_right = (left_rotation[0], -left_rotation[1], left_rotation[2], -left_rotation[3])
    if any(
        not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1.0e-7)
        for actual, expected in zip(right_rotation, expected_right, strict=True)
    ):
        raise ValueError("left/right WXYZ quaternions must be mirrored")
    left_forward_y = quaternion_forward_y(left_rotation)
    right_forward_y = quaternion_forward_y(right_rotation)
    if left_position[1] * left_forward_y <= 0.0:
        raise ValueError(
            "left D435 must point outward: "
            f"left_y={left_position[1]!r} left_forward_y={left_forward_y!r}"
        )
    if right_position[1] * right_forward_y <= 0.0:
        raise ValueError(
            "right D435 must point outward: "
            f"right_y={right_position[1]!r} right_forward_y={right_forward_y!r}"
        )
    head_position = _finite_tuple(HEAD_POS, 3, "head_pos")
    head_rotation = _finite_tuple(HEAD_ROT, 4, "head_rot")
    quaternion_forward_y(head_rotation)
    if tuple(left_position) != tuple(TOEOUT6_LEFT_POS) or tuple(right_position) != tuple(TOEOUT6_RIGHT_POS):
        raise ValueError("TOEOUT6 geometry must use the canonical nominal positions")
    return {
        "architecture_id": ARCHITECTURE_ID,
        "convention": "world",
        "left": {"position_m": list(left_position), "rotation_wxyz": list(left_rotation), "forward_y": left_forward_y},
        "right": {"position_m": list(right_position), "rotation_wxyz": list(right_rotation), "forward_y": right_forward_y},
        "head": {"position_m": list(head_position), "rotation_wxyz": list(head_rotation), "resolution": [384, 136], "hz": 15},
        "outward_products": {
            "left_y_times_forward_y": left_position[1] * left_forward_y,
            "right_y_times_forward_y": right_position[1] * right_forward_y,
        },
        "raw_policy_contract": {
            "d435_views": ["left", "right"],
            "shared_encoder_invocations": "one packed invocation per view pair",
            "head_encoder": "independent_context",
            "panorama": False,
            "head_branch": "required",
            "camera_meta_dim": 6,
        },
    }


def validate_topology_environment(environ: Mapping[str, str], *, rank: int | None = None) -> dict[str, Any]:
    """Validate CVD, world/rank, and exact physical UUID mapping."""
    required = ("CUDA_VISIBLE_DEVICES", "WORLD_SIZE", "LOCAL_WORLD_SIZE", "RANK", "LOCAL_RANK", "MASTER_PORT")
    missing = [name for name in required if name not in environ]
    if missing:
        raise RuntimeError(f"four-rank topology environment is missing {missing}")
    if environ["CUDA_VISIBLE_DEVICES"] != CUDA_VISIBLE_DEVICES:
        raise RuntimeError("CUDA_VISIBLE_DEVICES must be exactly '4,5,6,7'")
    if environ["WORLD_SIZE"] != "4" or environ["LOCAL_WORLD_SIZE"] != "4":
        raise RuntimeError("WORLD_SIZE and LOCAL_WORLD_SIZE must both be 4")
    try:
        process_rank = int(environ["RANK"])
        local_rank = int(environ["LOCAL_RANK"])
    except ValueError as exc:
        raise RuntimeError("RANK and LOCAL_RANK must be decimal integers") from exc
    if process_rank not in range(4) or local_rank != process_rank:
        raise RuntimeError("RANK/LOCAL_RANK must be equal values in 0..3")
    if environ["MASTER_PORT"] != str(MASTER_PORT):
        raise RuntimeError(f"MASTER_PORT must be exactly {MASTER_PORT}")
    if rank is not None and rank != process_rank:
        raise RuntimeError(f"requested rank={rank} does not match RANK={process_rank}")
    physical_index = LOGICAL_TO_PHYSICAL[process_rank]
    return {
        "topology_id": TOPOLOGY_ID,
        "binding_mode": GPU_BINDING_MODE,
        "world_size": 4,
        "rank": process_rank,
        "local_rank": local_rank,
        "logical_cuda": f"cuda:{local_rank}",
        "physical_gpu_index": physical_index,
        "physical_gpu_uuid": LOGICAL_TO_UUID[process_rank],
        "cuda_visible_devices": CUDA_VISIBLE_DEVICES,
        "master_port": MASTER_PORT,
        "renderer": {"multiGpu": False, "maxGpuCount": 1, "activeGpu": physical_index},
        "physx": {"logicalGpu": local_rank},
    }


def validate_batch_contract(*, num_envs: int = 64, steps: int = 8, mini_batches: int = 4, epochs: int = 1, world_size: int = 4, mode: str = "formal") -> dict[str, int]:
    if (num_envs, steps, mini_batches, epochs, world_size) != (64, 8, 4, 1, 4):
        raise ValueError("toe-out20 DDP batch contract must be 64 envs, 8 steps, 4 minibatches, 1 epoch, world_size 4")
    if mode not in {"formal", "admission"}:
        raise ValueError(f"unsupported batch lifecycle mode: {mode!r}")
    local_transitions = num_envs * steps
    global_envs = num_envs * world_size
    global_transitions = local_transitions * world_size
    if local_transitions != 512 or global_transitions != 2048:
        raise RuntimeError("batch transition arithmetic drifted")
    if local_transitions // mini_batches != 128 or global_transitions // mini_batches != 512:
        raise RuntimeError("minibatch transition arithmetic drifted")
    return {
        "envs_per_rank": num_envs,
        "global_envs": global_envs,
        "steps_per_env": steps,
        "local_transitions_per_iteration": local_transitions,
        "global_transitions_per_iteration": global_transitions,
        "minibatches": mini_batches,
        "local_env_sequences_per_minibatch": num_envs // mini_batches,
        "local_transitions_per_minibatch": local_transitions // mini_batches,
        "global_transitions_per_minibatch": global_transitions // mini_batches,
        "per_device_train_batch_size": 16,
        "epochs": epochs,
        "gradient_accumulation_steps": 1,
        "iterations": 1 if mode == "admission" else 8000,
        "save_frequency": 1 if mode == "admission" else 500,
    }


def validate_geometry_batch_contract() -> dict[str, Any]:
    """Describe the diagnostic geometry route without entering a training batch contract."""
    return {
        "mode": "geometry",
        "training_performed": False,
        "envs": 16,
        "iterations": 0,
        "save_frequency": None,
    }


def validate_rollout_schedule(
    schedule: Any = MIXED_ROLLOUT_SCHEDULE,
    *,
    target_global_step: int = 8000,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(schedule, (list, tuple)) or len(schedule) != 4:
        raise ValueError("toe-out20 formal schedule must contain exactly four contiguous phases")
    expected_start = 0
    result = []
    for phase in schedule:
        if set(phase) != {"phase", "start_step", "end_step", "ratio", "teacher_count"}:
            raise ValueError("schedule phase fields drifted")
        if phase["start_step"] != expected_start or phase["end_step"] <= phase["start_step"]:
            raise ValueError("schedule phases must be contiguous and increasing")
        expected_teacher_count = int(256 * float(phase["ratio"]))
        if expected_teacher_count != phase["teacher_count"]:
            raise ValueError("schedule Teacher count drifted")
        if not math.isclose(256 * float(phase["ratio"]), phase["teacher_count"], abs_tol=1.0e-9):
            raise ValueError("schedule ratio does not yield an exact global Teacher count")
        result.append(dict(phase))
        expected_start = phase["end_step"]
    if expected_start != target_global_step:
        raise ValueError(f"schedule must terminate at global step {target_global_step}")
    return tuple(result)


def validate_admission_rollout_schedule(
    schedule: Any = ADMISSION_ROLLOUT_SCHEDULE,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(schedule, (list, tuple)) or len(schedule) != 1:
        raise ValueError("admission schedule must contain exactly one prefix phase")
    phase = schedule[0]
    if set(phase) != {"phase", "start_step", "end_step", "ratio", "teacher_count"}:
        raise ValueError("admission schedule fields drifted")
    if phase["phase"] != "L0" or phase["start_step"] != 0 or phase["end_step"] != 1:
        raise ValueError("admission schedule must be the exact [0,1) L0 prefix")
    if float(phase["ratio"]) != 1.0 or phase["teacher_count"] != 256:
        raise ValueError("admission schedule must select all 256 global Teacher environments")
    return tuple(dict(phase) for phase in schedule)


def validate_provenance() -> dict[str, Any]:
    """Validate and return the immutable Teacher/runtime provenance contract."""
    if TEACHER_PROVENANCE["checkpoint_load"] != {"checkpoint": None, "auto_load_latest": False, "source": "immutable_teacher_only"}:
        raise RuntimeError("Teacher checkpoint selection contract drifted")
    if TEACHER_PROVENANCE["runtime_commit"] != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError("Teacher runtime commit pin drifted from the audited c18 commit")
    validate_runtime_repository(Path(TEACHER_PROVENANCE["runtime_repository"]))
    return json.loads(canonical_json(TEACHER_PROVENANCE))


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_runtime_repository(repository: Path) -> dict[str, Any]:
    """Require the exact clean c18 runtime and audited source module paths."""
    repository = repository.expanduser().resolve()
    if not repository.is_dir():
        raise FileNotFoundError(f"c18 runtime repository is unavailable: {repository}")
    try:
        commit = _git(repository, "rev-parse", "HEAD")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"unable to resolve c18 runtime Git HEAD: {repository}") from exc
    if commit != EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError(
            f"c18 runtime commit mismatch: expected={EXPECTED_RUNTIME_COMMIT} actual={commit}"
        )
    try:
        dirty = _git(repository, "status", "--short", "--", "gr00t")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"unable to inspect c18 runtime Git state: {repository}") from exc
    if dirty:
        raise RuntimeError(f"c18 runtime gr00t source must be clean:\n{dirty}")
    module_sources: dict[str, str] = {}
    for module_name, relative_path in RUNTIME_MODULES.items():
        source_path = (repository / relative_path).resolve()
        if not source_path.is_file() or not source_path.is_relative_to(repository):
            raise FileNotFoundError(
                f"c18 runtime module is unavailable or escaped the repository: {module_name} -> {source_path}"
            )
        module_sources[module_name] = str(source_path)
    eval_entrypoint = (repository / "gr00t/rl/eval_agent_trl.py").resolve()
    if not eval_entrypoint.is_file() or not eval_entrypoint.is_relative_to(repository):
        raise FileNotFoundError(f"c18 runtime eval entrypoint is unavailable: {eval_entrypoint}")
    return {
        "repository": str(repository),
        "commit": commit,
        "clean_gr00t": True,
        "eval_entrypoint": str(eval_entrypoint),
        "module_sources": module_sources,
    }


def _forward_vector(rotation_wxyz: Any) -> list[float]:
    w, x, y, z = _finite_tuple(rotation_wxyz, 4, "rotation_wxyz")
    return [
        1.0 - 2.0 * (y * y + z * z),
        2.0 * (x * y + w * z),
        2.0 * (x * z - w * y),
    ]


def build_top_view_geometry() -> dict[str, Any]:
    """Build the deterministic, diagnostic-only top-view geometry artifact."""
    geometry = validate_toeout6_geometry()
    return {
        "schema": "a2_cb2h_toeout6_top_view_geometry_v1",
        "architecture_id": ARCHITECTURE_ID,
        "convention": "world",
        "origins_m": {
            "left": list(TOEOUT6_LEFT_POS),
            "right": list(TOEOUT6_RIGHT_POS),
            "head": list(HEAD_POS),
        },
        "optical_axes_world": {
            "left": _forward_vector(TOEOUT6_LEFT_ROT),
            "right": _forward_vector(TOEOUT6_RIGHT_ROT),
            "head": _forward_vector(HEAD_ROT),
        },
        "horizontal_fov_boundaries_deg": {
            "left": [-21.25, 21.25],
            "right": [-21.25, 21.25],
            "head": [-38.5, 38.5],
        },
        "nominal_handle_workspace_m": {
            "center": [0.93, 0.0, 0.72],
            "half_extents": [0.20, 0.18, 0.16],
            "source": "diagnostic_nominal_workspace_not_cad_calibration",
        },
        "piper_keep_out_volume_m": {
            "center": [0.28, 0.0, 0.22],
            "half_extents": [0.20, 0.20, 0.20],
            "source": "diagnostic_nominal_keep_out_not_cad_clearance",
        },
        "outward_products": geometry["outward_products"],
        "policy_rgb_contract_unchanged": True,
        "panorama": False,
    }


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite geometry artifact: {path}")
    temporary = path.with_name(f".{path.name}.writing")
    if temporary.exists():
        raise FileExistsError(f"geometry artifact temporary path already exists: {temporary}")
    temporary.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sanitize_geometry_overlay_config(
    config_text: str,
    source_config: Path,
    expected_target_class: str = "DoorPregraspCameraSchemeToeOut6Geometry",
) -> str:
    """Keep the geometry overlay camera-only before the Teacher merge.

    The legacy sweep YAML is intentionally used as the camera source, but its
    task-threshold entries must never become overrides of the immutable
    Teacher.  Validate source keys before stripping them so a newly introduced
    task-semantic key fails fast instead of being silently ignored.
    """
    source_document = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    if not isinstance(source_document, dict):
        raise RuntimeError(f"geometry camera source must be a YAML mapping: {source_config}")
    source_env = source_document.get("env")
    if not isinstance(source_env, dict) or not isinstance(source_env.get("config"), dict):
        raise RuntimeError(f"geometry camera source env.config is missing: {source_config}")
    source_config_keys = set(source_env["config"])
    allowed_source_keys = GEOMETRY_ENV_CONFIG_ALLOWLIST | GEOMETRY_LEGACY_TASK_KEYS
    unexpected_source_keys = source_config_keys - allowed_source_keys
    if unexpected_source_keys:
        raise RuntimeError(
            "geometry camera source contains unexpected env.config keys: "
            f"{sorted(unexpected_source_keys)}"
        )

    generated_document = yaml.safe_load(config_text)
    if not isinstance(generated_document, dict):
        raise RuntimeError("generated geometry overlay must be a YAML mapping")
    generated_env = generated_document.get("env")
    if not isinstance(generated_env, dict) or not isinstance(generated_env.get("config"), dict):
        raise RuntimeError("generated geometry overlay env.config is missing")
    generated_config = generated_env["config"]
    unexpected_generated_keys = set(generated_config) - allowed_source_keys
    if unexpected_generated_keys:
        raise RuntimeError(
            "generated geometry overlay contains unexpected env.config keys: "
            f"{sorted(unexpected_generated_keys)}"
        )
    missing_camera_keys = GEOMETRY_ENV_CONFIG_ALLOWLIST - set(generated_config)
    if missing_camera_keys:
        raise RuntimeError(
            "generated geometry overlay is missing camera env.config keys: "
            f"{sorted(missing_camera_keys)}"
        )
    generated_env["config"] = {
        key: generated_config[key]
        for key in ("a2_camera_pose_sweep", "a2_camera_scheme_c")
    }
    expected_target = (
        "gr00t.rl.envs.door.door_open_a2_camera_pose_sweep."
        f"{expected_target_class}"
    )
    if generated_env.get("_target_") != expected_target:
        raise RuntimeError(
            "generated geometry overlay target drifted: "
            f"{generated_env.get('_target_')!r} != {expected_target!r}"
        )
    if any(
        forbidden_key in generated_env["config"]
        for forbidden_key in GEOMETRY_LEGACY_TASK_KEYS
    ):
        raise RuntimeError("generated geometry overlay retained a legacy task-semantic key")
    return "# @package _global_\n\n" + yaml.safe_dump(
        generated_document, sort_keys=False
    )


def _prepare_geometry_overlay(
    output_root: Path, *, teacher_render: bool = False
) -> tuple[Path, Path, Path]:
    """Create a disposable overlay that runs the existing Teacher camera evaluator."""
    overlay_root = output_root / "_geometry_overlay"
    env_dir = overlay_root / "gr00t/rl/envs/door"
    utils_dir = overlay_root / "gr00t/rl/utils"
    config_dir = overlay_root / "gr00t/rl/config/camera_pose_sweep"
    for directory in (env_dir, utils_dir, config_dir):
        directory.mkdir(parents=True, exist_ok=False)
    for relative_path in (
        "gr00t/rl/utils/a2_camera_pose_sweep.py",
        "gr00t/rl/envs/door/door_open_a2_camera_pose_sweep.py",
    ):
        source = REPO_ROOT / relative_path
        destination = overlay_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    env_module = env_dir / "door_open_a2_camera_pose_sweep.py"
    source_text = env_module.read_text(encoding="utf-8")
    source_text = source_text.split(
        "class DoorPregraspCameraSchemeCBDualPortraitOEM(", 1
    )[0]
    source_text = re.sub(
        r"from gr00t\.rl\.utils\.a2_dual_portrait_panorama import \(.*?\n\)\n",
        "",
        source_text,
        flags=re.DOTALL,
    )
    if "a2_dual_portrait_panorama" in source_text or "depth_aware_cylindrical_panorama" in source_text:
        raise RuntimeError("geometry overlay retained a panorama import")
    env_module.write_text(source_text, encoding="utf-8")
    with env_module.open("a", encoding="utf-8") as stream:
        stream.write(
            """


class DoorPregraspCameraSchemeToeOut6Geometry(DoorPregraspCameraSchemeC):
    \"\"\"Three-view diagnostic evaluator with no stitched/panorama writer.\"\"\"

    SCHEME_VARIANT = \"C-B2H-TOEOUT6-GEOMETRY\"
    D435I_VIEW = \"d435i_left_portrait_up50_toeout6\"
    RIGHT_D435I_VIEW = \"d435i_right_portrait_up50_toeout6\"
    HEAD_VIEW = \"a2_head_oem\"
    UNION_VIEW = \"toeout6_head_left_right_union\"
    D435I_HOUSING_ORIENTATION = \"portrait_plus90_deg_identical_roll\"
    D435I_SOFTWARE_UPRIGHTED = True
    D435I_POSITION_M = [0.215, 0.065, 0.165]
    D435I_ROTATION_WXYZ = [0.905065723713, 0.022118130854, -0.422039078101, 0.047432484685]
    D435I_RPY_DEG = [0.0, -50.0, 6.0]
    D435I_WIDTH = 216
    D435I_HEIGHT = 384
    D435I_PANEL_DESCRIPTION = \"outward left portrait D435i\"
    HEAD_CAMERA_REQUIRED_METADATA = {}

    @classmethod
    def _parse_a2_camera_scheme_c_config(cls, config):
        raw = OmegaConf.to_container(config.get(\"a2_camera_scheme_c\"), resolve=True)
        if not isinstance(raw, dict):
            raise RuntimeError(\"toe-out geometry requires a Scheme C mapping\")
        pair = raw.get(\"d435i_pair\")
        head = raw.get(\"head_camera\")
        combined = raw.get(\"combined_video\")
        if not isinstance(pair, dict) or not isinstance(head, dict) or not isinstance(combined, dict):
            raise RuntimeError(\"toe-out geometry Scheme C config is incomplete\")
        return {
            \"enabled\": True,
            \"ablation_id\": cls.SCHEME_VARIANT,
            \"architecture\": \"three diagnostic views: outward left D435, outward right D435, official OEM Head\",
            \"view_order\": [cls.D435I_VIEW, cls.RIGHT_D435I_VIEW, cls.HEAD_VIEW],
            \"combined_video\": dict(combined),
            \"d435i_mount\": {
                \"parent\": \"trunk\",
                \"physical_housing_orientation\": cls.D435I_HOUSING_ORIENTATION,
                \"software_uprighted_optical_frame\": True,
                \"position_m\": list(cls.D435I_POSITION_M),
                \"effective_optical_rpy_deg\": list(cls.D435I_RPY_DEG),
                \"mechanical_clearance_status\": \"unverified\",
                \"lateral_symmetry_contract\": \"world_mirrored_outward\",
            },
            \"head_camera\": dict(head),
        }

    def scene_creation_callback(self, simulator):
        super().scene_creation_callback(simulator)
        from isaaclab import sim as sim_utils
        from isaaclab.sensors.camera import TiledCamera, TiledCameraCfg

        cfg = self._a2_scheme_c_cfg
        raw = OmegaConf.to_container(self.config.get(\"a2_camera_scheme_c\"), resolve=True)
        pair = raw[\"d435i_pair\"]
        right = pair[\"right\"]
        sensor_name = right[\"sensor_name\"]
        if sensor_name in simulator.scene.sensors:
            raise RuntimeError(\"toe-out right D435 sensor already exists\")
        right_cfg = TiledCameraCfg(
            prim_path=f\"/World/envs/env_.*/Robot/{right['parent']}/{right['prim_suffix']}\",
            offset=TiledCameraCfg.OffsetCfg(
                pos=tuple(right[\"position_m\"]), rot=tuple(right[\"rotation_wxyz\"]), convention=\"world\"
            ),
            data_types=[\"rgb\", \"distance_to_image_plane\", \"instance_id_segmentation_fast\"],
            spawn=sim_utils.PinholeCameraCfg(
                focal_length=float(pair[\"focal_length\"]),
                focus_distance=float(pair[\"focus_distance\"]),
                horizontal_aperture=float(pair[\"horizontal_aperture\"]),
                vertical_aperture=float(pair[\"vertical_aperture\"]),
                clipping_range=tuple(pair[\"clipping_range\"]),
            ),
            width=int(pair[\"width\"]), height=int(pair[\"height\"]),
            update_period=float(pair[\"update_period\"]),
            colorize_instance_id_segmentation=False, debug_vis=True,
        )
        right_camera = TiledCamera(right_cfg)
        simulator.scene.sensors[sensor_name] = right_camera
        simulator.a2_d435i_right_portrait_camera = right_camera

    def init_a2_eval_stage2_step_trace(self, diagnostic_enabled=False, diagnostic_reward_terms=()):
        super().init_a2_eval_stage2_step_trace(
            diagnostic_enabled=diagnostic_enabled, diagnostic_reward_terms=diagnostic_reward_terms
        )
        right_name = self.RIGHT_D435I_VIEW
        right_camera = self.simulator.scene.sensors.get(right_name)
        if right_camera is None:
            raise RuntimeError(\"toe-out right D435 camera is missing\")
        self._a2_scheme_c_cameras[right_name] = right_camera
        self._toeout_sample_stage_trace = []
        self._toeout_sample_frame_evidence = []

    def _capture_a2_camera_pose_sweep_sample(self, active):
        video_active = bool(active[self._a2_camera_sweep_video_env_id].detach().cpu().item())
        stage = int(self.stage_buf[self._a2_camera_sweep_video_env_id].detach().cpu().item()) if video_active else None
        super()._capture_a2_camera_pose_sweep_sample(active)
        if video_active:
            control_step = int(self.common_step_counter)
            per_view = {}
            for view_name in (self.D435I_VIEW, self.RIGHT_D435I_VIEW, self.HEAD_VIEW):
                metrics = self._a2_camera_visibility_metrics(self._a2_scheme_c_cameras[view_name])
                handle_pixels = int(
                    metrics[\"pixel_counts\"][\"handle\"][self._a2_camera_sweep_video_env_id]
                    .detach()
                    .cpu()
                    .item()
                )
                per_view[view_name] = {
                    \"handle_pixels\": handle_pixels,
                    \"semantic_targets\": [\"handle\", \"finger7\", \"finger8\", \"door_panel\"],
                }
            coverage = {
                \"control_step\": control_step,
                \"stage\": stage,
                \"union_handle_pixels\": max(view[\"handle_pixels\"] for view in per_view.values()),
                \"per_view\": per_view,
            }
            frame = {
                \"control_step\": control_step,
                \"stage\": stage,
                \"coverage_control_step\": control_step,
                \"coverage\": coverage,
            }
            self._toeout_sample_stage_trace.append(frame)
            self._toeout_sample_frame_evidence.append(frame)

    def _append_a2_scheme_c_combined_frame(self):
        panels = [
            self._fit_a2_scheme_c_panel(self._a2_video_frame_for_candidate(name))
            for name in (self.D435I_VIEW, self.RIGHT_D435I_VIEW, self.HEAD_VIEW)
        ]
        combined = torch.cat(panels, dim=1)
        if tuple(combined.shape) != (216, 1152, 3):
            raise RuntimeError(f\"toe-out combined frame shape drift: {combined.shape}\")
        writer = self._a2_scheme_c_combined_writer
        if writer is None:
            writer = imageio.get_writer(
                str(self._a2_scheme_c_combined_temporary_path),
                fps=self._a2_camera_sweep_video_fps,
                codec=\"libx264\",
                macro_block_size=2,
            )
            self._a2_scheme_c_combined_writer = writer
        writer.append_data(combined.detach().contiguous().cpu().numpy())
        self._a2_scheme_c_combined_frame_count += 1

    def _a2_scheme_c_combined_layout(self):
        return \"left outward D435 384x216; right outward D435 384x216; official OEM Head 384x216\"

    def get_eval_metrics_summary(self):
        summary = DoorPregraspCameraSchemeC.get_eval_metrics_summary(self)
        scheme = summary.get(\"a2_camera_scheme_c\")
        trace = list(getattr(self, \"_toeout_sample_stage_trace\", []))
        frame_evidence = list(getattr(self, \"_toeout_sample_frame_evidence\", []))
        if not isinstance(scheme, dict) or not trace:
            raise RuntimeError(\"toe-out geometry lacks sampled stage evidence\")
        if not frame_evidence or frame_evidence != trace:
            raise RuntimeError(\"toe-out geometry trace and per-frame coverage evidence diverged\")
        windows = {}
        for previous, current in zip(trace, trace[1:]):
            if previous[\"stage\"] == current[\"stage\"]:
                continue
            transition = f\"stage{previous['stage']}_to_stage{current['stage']}\"
            center = int(current[\"control_step\"])
            members = [item for item in trace if abs(int(item[\"control_step\"]) - center) <= 10]
            if not members:
                raise RuntimeError(f\"toe-out transition window is empty: {transition}\")
            windows.setdefault(transition, {\"center_control_step\": center, \"sampled_frames\": members})
        required = {\"stage1_to_stage2\", \"stage2_to_stage3\", \"stage3_to_stage4\"}
        if not required.issubset(windows):
            raise RuntimeError(f\"toe-out transition evidence is incomplete: {sorted(windows)}\")
        scheme[\"architecture\"] = \"three diagnostic views: outward left D435, outward right D435, official OEM Head\"
        scheme[\"geometry_contract\"] = {
            \"architecture_id\": \"C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2\",
            \"view_order\": [self.D435I_VIEW, self.RIGHT_D435I_VIEW, self.HEAD_VIEW],
            \"panorama\": False,
            \"diagnostic_only\": True,
            \"transition_window_radius_control_steps\": 10,
            \"transition_windows_source\": \"sampled stage trace from video env\",
        }
        scheme[\"transition_windows\"] = windows
        scheme[\"sampled_frame_evidence\"] = frame_evidence
        return summary


class DoorPregraspCameraSchemeToeOut6TeacherRender(DoorPregraspCameraSchemeToeOut6Geometry):
    \"\"\"Teacher-only three-view render with video finalization as the sole gate.\"\"\"

    SCHEME_VARIANT = \"C-B2H-TOEOUT6-GEOMETRY\"

    def init_a2_eval_stage2_step_trace(self, diagnostic_enabled=False, diagnostic_reward_terms=()):
        DoorPregrasp.init_a2_eval_stage2_step_trace(
            self,
            diagnostic_enabled=diagnostic_enabled,
            diagnostic_reward_terms=diagnostic_reward_terms,
        )
        cfg = OmegaConf.to_container(self.config.get(\"a2_camera_pose_sweep\"), resolve=True)
        if not isinstance(cfg, dict) or cfg.get(\"enabled\") is not True:
            raise RuntimeError(\"Teacher render requires enabled camera sweep config\")
        video = cfg[\"video\"]
        self._a2_camera_sweep_cfg = cfg
        self._a2_camera_sweep_candidates = list(cfg[\"candidates\"])
        self._a2_camera_sweep_camera = self.simulator.ego_camera
        self._a2_camera_sweep_camera_view = self.simulator.ego_camera._view
        self._a2_camera_sweep_sample_interval = 1
        self._a2_camera_sweep_ranking_stage_indices = []
        self._a2_camera_sweep_minimum_visible_pixels = {}
        self._a2_camera_sweep_target_path_tokens = {}
        self._a2_camera_sweep_intrinsic_error_px = None
        self._a2_camera_sweep_first_episode_active = torch.ones(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_camera_sweep_last_stage = self.stage_buf.detach().clone()
        self._a2_camera_sweep_sample_events = 0
        self._a2_camera_sweep_video_env_id = int(video[\"env_id\"])
        self._a2_camera_sweep_video_fps = int(video[\"fps\"])
        self._a2_camera_sweep_video_output_dir = Path(video[\"output_dir\"]).resolve()
        if self._a2_camera_sweep_video_output_dir.exists():
            raise FileExistsError(\"refusing to reuse Teacher render video directory\")
        self._a2_camera_sweep_video_output_dir.mkdir(parents=True, exist_ok=False)
        self._a2_camera_sweep_video_writers = {}
        self._a2_camera_sweep_video_temporary_paths = {}
        self._a2_camera_sweep_video_final_paths = {}
        self._a2_camera_sweep_video_frame_counts = {
            candidate[\"name\"]: 0 for candidate in self._a2_camera_sweep_candidates
        }
        self._a2_camera_sweep_video_stage_frame_counts = {
            name: 0 for name in STAGE_NAMES.values()
        }
        self._teacher_side_by_side_writer = None
        self._teacher_side_by_side_temporary_path = (
            self._a2_camera_sweep_video_output_dir
            / "d435i_left_right_side_by_side_env0001.writing.mp4"
        )
        self._teacher_side_by_side_final_path = (
            self._a2_camera_sweep_video_output_dir
            / "d435i_left_right_side_by_side_env0001.mp4"
        )
        self._teacher_side_by_side_frame_count = 0
        self._a2_camera_sweep_videos_sealed = False
        self._a2_camera_sweep_pose_diversity_validated = False
        self._a2_scheme_c_cameras = {
            self.D435I_VIEW: self.simulator.ego_camera,
            self.RIGHT_D435I_VIEW: self.simulator.scene.sensors[self.RIGHT_D435I_VIEW],
            self.HEAD_VIEW: self.simulator.scene.sensors[self.HEAD_VIEW],
        }

    def _capture_a2_camera_pose_sweep_sample(self, active):
        del active
        simulator = self.simulator
        simulator.sim.render()
        for name in self._a2_scheme_c_cfg[\"view_order\"]:
            camera = self._a2_scheme_c_cameras[name]
            camera.update(dt=0.0, force_recompute=True)
            self._append_a2_camera_candidate_video_frame(name)
        self._append_teacher_side_by_side_frame()
        self._a2_camera_sweep_sample_events += 1

    def _append_teacher_side_by_side_frame(self):
        panels = [
            self._fit_a2_scheme_c_panel(self._a2_video_frame_for_candidate(name))
            for name in (self.D435I_VIEW, self.RIGHT_D435I_VIEW)
        ]
        combined = torch.cat(panels, dim=1)
        if tuple(combined.shape) != (216, 768, 3):
            raise RuntimeError(f"Teacher side-by-side frame shape drift: {combined.shape}")
        writer = self._teacher_side_by_side_writer
        if writer is None:
            writer = imageio.get_writer(
                str(self._teacher_side_by_side_temporary_path),
                fps=self._a2_camera_sweep_video_fps,
                codec="libx264",
                macro_block_size=2,
            )
            self._teacher_side_by_side_writer = writer
        writer.append_data(combined.detach().contiguous().cpu().numpy())
        self._teacher_side_by_side_frame_count += 1

    def _seal_teacher_render_videos(self):
        if self._a2_camera_sweep_videos_sealed:
            raise RuntimeError(\"Teacher render videos were already sealed\")
        names = [candidate[\"name\"] for candidate in self._a2_camera_sweep_candidates]
        if set(self._a2_camera_sweep_video_writers) != set(names):
            raise RuntimeError(\"Teacher render did not open all three view writers\")
        frame_counts = [self._a2_camera_sweep_video_frame_counts[name] for name in names]
        if len(set(frame_counts)) != 1:
            raise RuntimeError(f\"Teacher render view frame counts are not synchronized: {frame_counts}\")
        if self._teacher_side_by_side_writer is None:
            raise RuntimeError(\"Teacher render did not open the side-by-side writer\")
        if self._teacher_side_by_side_frame_count != frame_counts[0]:
            raise RuntimeError(\"Teacher side-by-side frame count is not synchronized with D435 views\")
        sealed = {}
        for name in names:
            if self._a2_camera_sweep_video_frame_counts[name] < 1:
                raise RuntimeError(f\"Teacher render video has no frames: {name}\")
            writer = self._a2_camera_sweep_video_writers.pop(name)
            writer.close()
            temporary = self._a2_camera_sweep_video_temporary_paths[name]
            final = self._a2_camera_sweep_video_final_paths[name]
            if not temporary.is_file():
                raise FileNotFoundError(f\"Teacher render video was not written: {temporary}\")
            os.replace(temporary, final)
            if not final.is_file() or final.stat().st_size <= 0:
                raise RuntimeError(f\"Teacher render video is empty: {final}\")
            sealed[name] = str(final)
        self._teacher_side_by_side_writer.close()
        if not self._teacher_side_by_side_temporary_path.is_file():
            raise FileNotFoundError(
                f\"Teacher side-by-side video was not written: {self._teacher_side_by_side_temporary_path}\"
            )
        os.replace(self._teacher_side_by_side_temporary_path, self._teacher_side_by_side_final_path)
        if (
            not self._teacher_side_by_side_final_path.is_file()
            or self._teacher_side_by_side_final_path.stat().st_size <= 0
        ):
            raise RuntimeError(f\"Teacher side-by-side video is empty: {self._teacher_side_by_side_final_path}\")
        sealed[\"d435i_left_right_side_by_side\"] = str(self._teacher_side_by_side_final_path)
        self._a2_camera_sweep_videos_sealed = True
        return sealed

    def get_eval_metrics_summary(self):
        summary = DoorPregrasp.get_eval_metrics_summary(self)
        if self._a2_camera_sweep_sample_events < 1:
            raise RuntimeError(\"Teacher render produced no RGB samples\")
        summary[\"teacher_render\"] = {
            \"status\": \"TEACHER_RENDER_COMPLETE\",
            \"view_order\": list(self._a2_scheme_c_cfg[\"view_order\"]),
            \"training_performed\": False,
            \"video_paths\": self._seal_teacher_render_videos(),
        }
        return summary
"""
        )
    source_config = REPO_ROOT / "gr00t/rl/config/camera_pose_sweep" / f"{GEOMETRY_SOURCE_CAMERA_CONFIG}.yaml"
    if not source_config.is_file():
        raise FileNotFoundError(f"geometry camera source config is missing: {source_config}")
    config_text = source_config.read_text(encoding="utf-8")
    config_text = re.sub(
        r"(?ms)^    a2_camera_scheme_c:\n.*?(?=^algo:)",
        """    a2_camera_scheme_c:
      enabled: true
      ablation_id: C-B2H-TOEOUT6-GEOMETRY
      architecture: "three diagnostic views: outward left D435, outward right D435, official OEM Head"
      view_order: [d435i_left_portrait_up50_toeout6, d435i_right_portrait_up50_toeout6, a2_head_oem]
      combined_video:
        enabled: true
        env_id: 1
        fps: 10
        output_path: ${eval_output_dir}/scheme_c_toeout6_left_right_head_env0001.mp4
      d435i_pair:
        parent: trunk
        physical_housing_orientation: portrait_plus90_deg_identical_roll
        software_uprighted_optical_frame: true
        rgb_native_fov_hv_deg: [69.4, 42.5]
        rgb_portrait_fov_hv_deg: [42.5, 69.4]
        width: 216
        height: 384
        focal_length: 1.0
        focus_distance: 0.5
        horizontal_aperture: 0.7777574637059793
        vertical_aperture: 1.3826799354772965
        clipping_range: [0.1, 20.0]
        update_period: 0.0
        left:
          sensor_name: d435i_left_portrait_up50_toeout6
          parent: trunk
          prim_suffix: d435i_left_portrait_camera
          position_m: [0.215, 0.065, 0.165]
          rotation_wxyz: [0.905065723713, 0.022118130854, -0.422039078101, 0.047432484685]
          rpy_deg: [0.0, -50.0, 6.0]
        right:
          sensor_name: d435i_right_portrait_up50_toeout6
          parent: trunk
          prim_suffix: d435i_right_portrait_camera
          position_m: [0.215, -0.065, 0.165]
          rotation_wxyz: [0.905065723713, -0.022118130854, -0.422039078101, -0.047432484685]
          rpy_deg: [0.0, -50.0, -6.0]
      head_camera:
        sensor_name: a2_head_oem
        parent: trunk
        prim_suffix: a2_head_oem_camera
        extrinsic_status: official_unitree_a2_urdf_camera_link
        position_m: [0.3381, 0.0336, 0.0525]
        rotation_wxyz: [1.0, 0.0, 0.0, 0.0]
        rpy_deg: [0.0, 0.0, 0.0]
        width: 384
        height: 136
        focal_length: 1.0
        focus_distance: 0.5
        horizontal_aperture: 4.492073547808433
        vertical_aperture: 1.59094271484882
        clipping_range: [0.1, 20.0]
        update_period: 0.0
        nominal_intrinsics:
          source: Unitree A2 published Head FoV and official URDF camera_link extrinsic
          native_resolution: [1448, 2568]
          native_fov_deg: [77.0, 132.0]
          diagnostic_resolution: [136, 384]
          sim_fx_fy_cx_cy: [85.48390757923893, 85.48390757923893, 192.0, 68.0]
          sim_effective_fov_deg: [77.0024873497374, 132.0]

""",
        config_text,
    )
    replacements = {
        "DoorPregraspCameraSchemeCBDualPortraitOEMToein20": "DoorPregraspCameraSchemeToeOut6Geometry",
        "C-B2-DUAL-PORTRAIT-OEM-TOEIN20": "C-B2H-TOEOUT6-GEOMETRY",
        "d435i_left_portrait_up60_toein20": GEOMETRY_LEFT_VIEW,
        "d435i_right_portrait_up60_toein20": GEOMETRY_RIGHT_VIEW,
        "[0.852868532, -0.086824089, -0.492403877, -0.150383733]": "__TOEOUT_LEFT_QUAT__",
        "[0.852868532, 0.086824089, -0.492403877, 0.150383733]": "__TOEOUT_RIGHT_QUAT__",
        "rpy_deg: [0.0, -60.0, -20.0]": "__TOEOUT_LEFT_RPY__",
        "rpy_deg: [0.0, -60.0, 20.0]": "__TOEOUT_RIGHT_RPY__",
        "left_y_plus_yaw_minus_right_y_minus_yaw_plus": "left_y_plus_yaw_plus_right_y_minus_yaw_minus",
        "toein20": "toeout6",
        "ranking_stage_indices: [1, 2, 3, 4, 5]": "ranking_stage_indices: [1, 2, 3, 4, 5]",
        "sample_interval_control_steps: 5": "sample_interval_control_steps: 1",
        "handle: 8": "handle: 16",
    }
    for source, replacement in replacements.items():
        config_text = config_text.replace(source, replacement)
    config_text = config_text.replace(
        "__TOEOUT_LEFT_QUAT__",
        "[0.905065723713, 0.022118130854, -0.422039078101, 0.047432484685]",
    )
    config_text = config_text.replace(
        "__TOEOUT_RIGHT_QUAT__",
        "[0.905065723713, -0.022118130854, -0.422039078101, -0.047432484685]",
    )
    config_text = config_text.replace("__TOEOUT_LEFT_RPY__", "rpy_deg: [0.0, -50.0, 6.0]")
    config_text = config_text.replace("__TOEOUT_RIGHT_RPY__", "rpy_deg: [0.0, -50.0, -6.0]")
    if teacher_render:
        config_text = config_text.replace(
            "DoorPregraspCameraSchemeToeOut6Geometry",
            "DoorPregraspCameraSchemeToeOut6TeacherRender",
        )
        config_text = config_text.replace(
            "camera_scheme_c_b2_toeout6_views", "teacher_videos"
        )
    config_text = "\n".join(
        line for line in config_text.splitlines() if "panorama" not in line.lower()
    ) + "\n"
    target_class = (
        "DoorPregraspCameraSchemeToeOut6TeacherRender"
        if teacher_render
        else "DoorPregraspCameraSchemeToeOut6Geometry"
    )
    config_text = _sanitize_geometry_overlay_config(
        config_text, source_config, expected_target_class=target_class
    )
    config_path = config_dir / f"{GEOMETRY_CAMERA_CONFIG}.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    checkpoint_dir = output_root / "_eval_input"
    checkpoint_dir.mkdir(exist_ok=False)
    runtime_checkpoint = checkpoint_dir / TEACHER_CHECKPOINT.name
    shutil.copyfile(TEACHER_CHECKPOINT, runtime_checkpoint)
    runtime_config = checkpoint_dir / "config.yaml"
    shutil.copyfile(TEACHER_CONFIG, runtime_config)
    expected_checkpoint_sha = TEACHER_PROVENANCE["checkpoint"]["sha256"]
    expected_config_sha = TEACHER_PROVENANCE["config"]["sha256"]
    if sha256_bytes(runtime_checkpoint.read_bytes()) != expected_checkpoint_sha:
        raise RuntimeError("geometry Teacher checkpoint copy failed SHA-256 validation")
    if sha256_bytes(runtime_config.read_bytes()) != expected_config_sha:
        raise RuntimeError("geometry Teacher config copy failed SHA-256 validation")
    return overlay_root, config_path, runtime_checkpoint


def _geometry_command(output_root: Path, overlay_root: Path, runtime_checkpoint: Path) -> tuple[str, ...]:
    bootstrap = REPO_ROOT / "gr00t/rl/scripts/run_a2_camera_pose_eval.py"
    overlay_config_root = overlay_root / "gr00t/rl/config"
    return (
        str(ISAACLAB_PYTHON),
        str(bootstrap),
        "--runtime-repository",
        str(TEACHER_RUNTIME_REPOSITORY),
        "--overlay-repository",
        str(overlay_root),
        "--bootstrap-profile",
        TOEOUT_BOOTSTRAP_PROFILE,
        "--",
        f"checkpoint={runtime_checkpoint}",
        f"+camera_pose_sweep={GEOMETRY_CAMERA_CONFIG}",
        "+num_envs=16",
        "+headless=true",
        "+use_wandb=false",
        "+multi_gpu=false",
        "++seed=0",
        "++algo.config.num_mini_batches=1",
        "++algo.config.eval.save_videos=false",
        "simulator.config.render_results=false",
        "env.config.save_rendering_dir=null",
        f"eval_output_dir={output_root}",
        f"eval_log_dir={output_root}",
        f"hydra.run.dir={output_root / '.hydra'}",
        f"hydra.searchpath=[file://{overlay_config_root}]",
    )


def _teacher_render_command(output_root: Path, overlay_root: Path, runtime_checkpoint: Path) -> tuple[str, ...]:
    command = list(_geometry_command(output_root, overlay_root, runtime_checkpoint))
    command.remove("++algo.config.eval.save_videos=false")
    return tuple(command)


def _validate_teacher_render_runtime(output_root: Path) -> Path:
    metrics_path = output_root / "metrics_eval.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Teacher render metrics are missing: {metrics_path}")
    videos = {}
    video_dir = output_root / "_geometry_overlay" / "gr00t/rl/config/camera_pose_sweep"
    del video_dir
    expected_dir = output_root / "teacher_videos"
    expected_views = (*TEACHER_RENDER_VIEWS, TEACHER_RENDER_SIDE_BY_SIDE_VIEW)
    for view in expected_views:
        path = expected_dir / f"{view}_env0001.mp4"
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"Teacher render video is missing or empty: {path}")
        videos[view] = {"path": str(path), "size": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {"schema": "a2_cb2h_toeout6_teacher_render_manifest_v1", "architecture_id": ARCHITECTURE_ID, "views": videos}
    manifest_path = output_root / "teacher_render_manifest.json"
    _atomic_json_write(manifest_path, manifest)
    return manifest_path


def rank_hydra_output_dirs(experiment_root: Path) -> tuple[Path, ...]:
    root = Path(experiment_root).expanduser().resolve()
    return tuple(root / "ranks" / f"rank{rank}" / ".hydra" for rank in range(4))


def validate_rank_hydra_output_dirs(
    experiment_root: Path,
    resolved_paths: Any,
) -> tuple[Path, ...]:
    """Validate four unique Hydra paths before any rank-local write is accepted."""
    expected = rank_hydra_output_dirs(experiment_root)
    if isinstance(resolved_paths, Mapping):
        values = [resolved_paths.get(rank) for rank in range(4)]
    elif isinstance(resolved_paths, (list, tuple)):
        values = list(resolved_paths)
    else:
        raise TypeError("resolved Hydra paths must be a four-entry sequence or rank mapping")
    if len(values) != 4 or any(value is None for value in values):
        raise ValueError("resolved Hydra paths must contain exactly four rank entries")
    normalized = tuple(Path(value).expanduser().resolve() for value in values)
    if len(set(normalized)) != 4:
        raise RuntimeError(f"rank Hydra output paths must be pairwise unique: {normalized}")
    for rank, (actual, expected_root) in enumerate(zip(normalized, expected, strict=True)):
        if not actual.is_relative_to(expected_root.parent):
            raise RuntimeError(
                f"rank{rank} Hydra output escaped its rank root: actual={actual} expected_under={expected_root.parent}"
            )
    return normalized


def _validate_geometry_transition_windows(scheme: Mapping[str, Any], *, radius: int = 10) -> dict[str, Any]:
    windows = scheme.get("transition_windows")
    if not isinstance(windows, Mapping) or not windows:
        raise RuntimeError("geometry runtime did not emit sampled transition windows")
    if isinstance(radius, bool) or not isinstance(radius, int) or radius != 10:
        raise RuntimeError("geometry transition window radius must be exactly +/-10 control steps")
    required = {"stage1_to_stage2", "stage2_to_stage3", "stage3_to_stage4"}
    if not required.issubset(windows):
        raise RuntimeError(f"geometry transition windows are incomplete: {sorted(windows)}")
    validated: dict[str, Any] = {}
    expected_views = {GEOMETRY_LEFT_VIEW, GEOMETRY_RIGHT_VIEW, GEOMETRY_HEAD_VIEW}
    for name, raw in windows.items():
        if not isinstance(raw, Mapping):
            raise RuntimeError(f"geometry transition window {name!r} is not a mapping")
        center = raw.get("center_control_step")
        frames = raw.get("sampled_frames")
        if isinstance(center, bool) or not isinstance(center, int) or not isinstance(frames, list) or not frames:
            raise RuntimeError(f"geometry transition window {name!r} lacks sampled frame evidence")
        expected_steps = set(range(center - radius, center + radius + 1))
        normalized = []
        observed_steps = set()
        for frame in frames:
            if not isinstance(frame, Mapping) or isinstance(frame.get("control_step"), bool) or not isinstance(frame.get("control_step"), int):
                raise RuntimeError(f"geometry transition window {name!r} contains invalid frame evidence")
            if abs(int(frame["control_step"]) - center) > radius:
                raise RuntimeError(f"geometry transition window {name!r} exceeds +/-{radius} control steps")
            if isinstance(frame.get("stage"), bool) or not isinstance(frame.get("stage"), int) or frame["stage"] not in range(5):
                raise RuntimeError(f"geometry transition window {name!r} contains invalid stage evidence")
            control_step = int(frame["control_step"])
            if control_step in observed_steps:
                raise RuntimeError(f"geometry transition window {name!r} contains duplicate frame {control_step}")
            observed_steps.add(control_step)
            if int(frame.get("coverage_control_step", -1)) != control_step:
                raise RuntimeError(f"geometry transition window {name!r} coverage step is not bound to the trace step")
            coverage = frame.get("coverage")
            if not isinstance(coverage, Mapping):
                raise RuntimeError(f"geometry transition window {name!r} lacks per-frame coverage evidence")
            if int(coverage.get("control_step", -1)) != control_step or int(coverage.get("stage", -1)) != int(frame["stage"]):
                raise RuntimeError(f"geometry transition window {name!r} coverage trace binding drifted")
            union_handle_pixels = coverage.get("union_handle_pixels")
            if isinstance(union_handle_pixels, bool) or not isinstance(union_handle_pixels, int) or union_handle_pixels < 16:
                raise RuntimeError(f"geometry transition window {name!r} has a frame below 16 union handle pixels")
            per_view = coverage.get("per_view")
            if not isinstance(per_view, Mapping) or set(per_view) != expected_views:
                raise RuntimeError(f"geometry transition window {name!r} has incomplete per-view semantics")
            for view_name in expected_views:
                view = per_view[view_name]
                if not isinstance(view, Mapping) or view.get("semantic_targets") != ["handle", "finger7", "finger8", "door_panel"]:
                    raise RuntimeError(f"geometry transition window {name!r} has empty semantic evidence for {view_name}")
                pixels = view.get("handle_pixels")
                if isinstance(pixels, bool) or not isinstance(pixels, int) or pixels < 0:
                    raise RuntimeError(f"geometry transition window {name!r} has invalid {view_name} handle pixels")
            normalized.append(
                {
                    "control_step": control_step,
                    "stage": int(frame["stage"]),
                    "coverage_control_step": control_step,
                    "coverage": {
                        "control_step": control_step,
                        "stage": int(frame["stage"]),
                        "union_handle_pixels": union_handle_pixels,
                        "per_view": {
                            str(view_name): {
                                "handle_pixels": int(per_view[view_name]["handle_pixels"]),
                                "semantic_targets": list(per_view[view_name]["semantic_targets"]),
                            }
                            for view_name in expected_views
                        },
                    },
                }
            )
        if observed_steps != expected_steps:
            missing = sorted(expected_steps - observed_steps)
            extra = sorted(observed_steps - expected_steps)
            raise RuntimeError(
                f"geometry transition window {name!r} must contain every contiguous frame in +/-{radius}: missing={missing} extra={extra}"
            )
        validated[str(name)] = {
            "center_control_step": center,
            "radius_control_steps": radius,
            "sampled_frames": normalized,
            "sampled_frame_count": len(normalized),
        }
    return validated


def _validate_geometry_runtime(output_root: Path, top_view_path: Path, command: tuple[str, ...]) -> Path:
    metrics_path = output_root / "metrics_eval.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"geometry runtime did not produce {metrics_path}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    teardown = _read_json_file(output_root / "teardown_record.json")
    if teardown.get("status") != "NATURAL" or teardown.get("unresolved") is not False:
        raise RuntimeError("geometry runtime teardown was not naturally sealed")
    sweep = metrics.get("a2_camera_pose_sweep")
    if not isinstance(sweep, dict) or sweep.get("status") != "SWEEP_COMPLETE":
        raise RuntimeError("geometry runtime did not seal a completed camera sweep")
    if sweep.get("training_performed") is not False or int(sweep.get("num_envs", 0)) != 16:
        raise RuntimeError("geometry runtime violated diagnostic-only 16-env contract")
    if int(sweep.get("sample_interval_control_steps", 0)) != 1:
        raise RuntimeError("geometry runtime did not sample every control step")
    scheme = metrics.get("a2_camera_scheme_c")
    if not isinstance(scheme, dict) or scheme.get("status") != "SCHEME_C_COMPLETE":
        raise RuntimeError("geometry runtime did not seal three-view union evidence")
    expected_views = [GEOMETRY_LEFT_VIEW, GEOMETRY_RIGHT_VIEW, GEOMETRY_HEAD_VIEW]
    if scheme.get("view_order") != expected_views:
        raise RuntimeError(f"geometry view order drifted: {scheme.get('view_order')!r}")
    contract = scheme.get("geometry_contract")
    if not isinstance(contract, dict) or contract.get("panorama") is not False:
        raise RuntimeError("geometry runtime emitted a panorama policy artifact")
    transition_windows = _validate_geometry_transition_windows(scheme)
    union = scheme.get("combined_visibility")
    stages = union.get("stages") if isinstance(union, dict) else None
    required_stage_names = ["stage1_pregrasp", "stage2_grasp", "stage3_open", "stage4_swing"]
    if not isinstance(stages, dict):
        raise RuntimeError("geometry runtime union stages are missing")
    per_view = scheme.get("per_view")
    if not isinstance(per_view, Mapping):
        raise RuntimeError("geometry runtime is missing per-view Head/D435 evidence")
    sampled_frame_evidence = scheme.get("sampled_frame_evidence")
    if not isinstance(sampled_frame_evidence, list) or not sampled_frame_evidence:
        raise RuntimeError("geometry runtime is missing per-sampled-frame union evidence")
    expected_views = {GEOMETRY_LEFT_VIEW, GEOMETRY_RIGHT_VIEW, GEOMETRY_HEAD_VIEW}
    critical_frame_evidence: dict[str, list[dict[str, Any]]] = {
        stage_name: [] for stage_name in required_stage_names
    }
    for frame in sampled_frame_evidence:
        if not isinstance(frame, Mapping):
            raise RuntimeError("geometry per-sampled-frame evidence is malformed")
        stage_id = frame.get("stage")
        if isinstance(stage_id, bool) or not isinstance(stage_id, int):
            raise RuntimeError("geometry per-sampled-frame stage evidence is invalid")
        if stage_id not in (1, 2, 3, 4):
            continue
        stage_name = {
            1: "stage1_pregrasp",
            2: "stage2_grasp",
            3: "stage3_open",
            4: "stage4_swing",
        }[stage_id]
        coverage = frame.get("coverage")
        if not isinstance(coverage, Mapping):
            raise RuntimeError("geometry per-sampled-frame coverage is missing")
        if int(coverage.get("control_step", -1)) != int(frame.get("control_step", -2)) or int(coverage.get("stage", -1)) != stage_id:
            raise RuntimeError("geometry per-sampled-frame trace/coverage binding drifted")
        union_pixels = coverage.get("union_handle_pixels")
        if isinstance(union_pixels, bool) or not isinstance(union_pixels, int) or union_pixels < 16:
            raise RuntimeError(f"geometry frame at step {frame.get('control_step')} has union handle pixels below 16")
        per_frame_views = coverage.get("per_view")
        if not isinstance(per_frame_views, Mapping) or set(per_frame_views) != expected_views:
            raise RuntimeError("geometry per-sampled-frame view semantics are incomplete")
        for view_name in expected_views:
            view = per_frame_views[view_name]
            if not isinstance(view, Mapping) or view.get("semantic_targets") != ["handle", "finger7", "finger8", "door_panel"]:
                raise RuntimeError(f"geometry per-sampled-frame semantics are missing for {view_name}")
        critical_frame_evidence[stage_name].append(dict(frame))
    critical = {}
    for stage_name in required_stage_names:
        stage = stages.get(stage_name)
        if not isinstance(stage, dict) or int(stage.get("sampled_frames", 0)) <= 0:
            raise RuntimeError(f"geometry critical stage has no samples: {stage_name}")
        sampled = int(stage["sampled_frames"])
        visible = int(stage.get("handle_visible_frames", 0))
        frames = critical_frame_evidence[stage_name]
        if visible != sampled or not frames:
            raise RuntimeError(
                f"geometry handle union gate failed for {stage_name}: "
                f"sampled={sampled} visible={visible} per_frame={len(frames)}"
            )
        if any(int(frame["coverage"]["union_handle_pixels"]) < 16 for frame in frames):
            raise RuntimeError(f"geometry handle union gate failed for {stage_name}: a sampled frame is below 16 pixels")
        d435_visible = 0
        for view_name in (GEOMETRY_LEFT_VIEW, GEOMETRY_RIGHT_VIEW):
            view = per_view.get(view_name)
            view_stage = view.get("stages", {}).get(stage_name) if isinstance(view, Mapping) else None
            if isinstance(view_stage, Mapping):
                d435_visible += int(view_stage.get("handle_visible_frames", 0))
        if d435_visible <= 0:
            raise RuntimeError(f"geometry D435 union has no visible handle frames: {stage_name}")
        critical[stage_name] = {
            "sampled_frames": sampled,
            "handle_visible_frames": visible,
            "per_frame_evidence_count": len(frames),
            "minimum_union_handle_pixels": min(int(frame["coverage"]["union_handle_pixels"]) for frame in frames),
            "transition_windows": transition_windows,
        }
    if not top_view_path.is_file():
        raise FileNotFoundError(f"geometry top-view artifact is missing: {top_view_path}")
    top_view = json.loads(top_view_path.read_text(encoding="utf-8"))
    if top_view.get("schema") != "a2_cb2h_toeout6_top_view_geometry_v1":
        raise RuntimeError("geometry top-view artifact schema drifted")
    evidence = {
        "schema": "a2_cb2h_toeout6_geometry_admission_v1",
        "status": "GEOMETRY_COMPLETE",
        "diagnostic_only": True,
        "seed": 0,
        "num_envs": 16,
        "gpu": 4,
        "critical_stage_indices": [1, 2, 3, 4],
        "transition_window_control_steps": 10,
        "transition_windows": transition_windows,
        "minimum_handle_pixels": 16,
        "minimum_d435_views": 1,
        "views": expected_views,
        "union_source": "Head/left_D435/right_D435",
        "critical": critical,
        "top_view_artifact": str(top_view_path),
        "metrics_path": str(metrics_path),
        "command": list(command),
    }
    evidence_path = output_root / "geometry_admission.json"
    _atomic_json_write(evidence_path, evidence)
    return evidence_path


def _output_root_for_mode(mode: str) -> Path:
    if mode == "teacher-render":
        return TEACHER_RENDER_ROOT
    if mode not in MODE_OUTPUTS:
        raise ValueError(f"unsupported runtime mode: {mode!r}")
    return MODE_OUTPUTS[mode]


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required lifecycle artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"lifecycle artifact must be a JSON object: {path}")
    return payload


def _validate_admission_prerequisite() -> dict[str, Any]:
    geometry_path = MODE_OUTPUTS["geometry"] / "geometry_admission.json"
    geometry = _read_json_file(geometry_path)
    if geometry.get("status") != "GEOMETRY_COMPLETE" or geometry.get("diagnostic_only") is not True:
        raise RuntimeError("formal admission requires a sealed GEOMETRY_COMPLETE prerequisite")
    return geometry


def _validate_formal_prerequisite() -> dict[str, Any]:
    _validate_admission_prerequisite()
    return _validate_training_artifacts("admission", MODE_OUTPUTS["admission"])


def _manual_camera_geometry_record() -> dict[str, Any]:
    return json.loads(canonical_json({"architecture_id": ARCHITECTURE_ID, **TOEOUT6_GEOMETRY}))


def _manual_camera_approval_record() -> dict[str, Any]:
    manifest_path = TEACHER_RENDER_MANIFEST
    if not manifest_path.is_file():
        raise FileNotFoundError(f"successful Teacher render manifest is missing: {manifest_path}")
    manifest_sha256 = sha256_file(manifest_path)
    if manifest_sha256 != TEACHER_RENDER_MANIFEST_SHA256:
        raise RuntimeError(
            f"successful Teacher render manifest SHA-256 drifted: {manifest_path}: "
            f"{manifest_sha256} != {TEACHER_RENDER_MANIFEST_SHA256}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("architecture_id") != ARCHITECTURE_ID:
        raise RuntimeError("successful Teacher render manifest architecture identity drifted")
    return {
        "manual_camera_approved": True,
        "geometry": _manual_camera_geometry_record(),
        "teacher_render_manifest_path": str(manifest_path),
        "teacher_render_manifest_sha256": manifest_sha256,
    }


def _validate_training_artifacts(mode: str, root: Path) -> dict[str, Any]:
    aggregate = _read_json_file(root / "aggregate_proof.json")
    expected_status = "ADMISSION_COMPLETE" if mode == "admission" else "FORMAL_COMPLETE"
    expected_step = 1 if mode == "admission" else 8000
    if aggregate.get("status") != expected_status:
        raise RuntimeError(f"{mode} training did not seal {expected_status}")
    final_checkpoint = aggregate.get("final_checkpoint")
    if not isinstance(final_checkpoint, Mapping) or int(final_checkpoint.get("global_step", -1)) != expected_step:
        raise RuntimeError(f"{mode} training final checkpoint step drifted")
    checkpoint_path = Path(str(final_checkpoint.get("path", ""))).expanduser().resolve()
    expected_checkpoint = root.resolve() / f"model_step_{expected_step:06d}.pt"
    if checkpoint_path != expected_checkpoint or not checkpoint_path.is_file():
        raise RuntimeError(f"{mode} training final checkpoint is not canonical: {checkpoint_path}")
    expected_sha = final_checkpoint.get("sha256")
    if not isinstance(expected_sha, str) or sha256_bytes(checkpoint_path.read_bytes()) != expected_sha:
        raise RuntimeError(f"{mode} training final checkpoint SHA256 proof mismatch")
    if (root / "last.pt").exists():
        raise RuntimeError(f"{mode} strict lifecycle emitted forbidden mutable last.pt")
    teardown = _read_json_file(root / "teardown_record.json")
    if teardown.get("status") != "NATURAL" or teardown.get("unresolved") is not False:
        raise RuntimeError(f"{mode} process teardown was not naturally sealed: {teardown}")
    rank_entries = aggregate.get("ranks")
    if not isinstance(rank_entries, list) or len(rank_entries) != 4:
        raise RuntimeError(f"{mode} training aggregate must list exactly four rank proofs")
    for entry in rank_entries:
        if not isinstance(entry, Mapping):
            raise RuntimeError("rank proof entry is malformed")
        proof_path = Path(str(entry.get("path", ""))).expanduser().resolve()
        if proof_path.parent.parent != root.resolve() / "ranks" or not proof_path.is_file():
            raise RuntimeError(f"rank proof escaped canonical root or is missing: {proof_path}")
        proof = _read_json_file(proof_path)
        if proof.get("loss_finite") is not True or proof.get("gradient_finite") is not True:
            raise RuntimeError(f"rank proof is missing finite loss/gradient evidence: {proof_path}")
    return aggregate


def _owned_process_group_alive(pgid: int) -> bool:
    try:
        os.killpg(int(pgid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write_teardown_record(
    root: Path,
    *,
    status: str,
    pgid: int | None,
    returncode: int | None,
    unresolved: bool,
    term_sent: bool = False,
    kill_sent: bool = False,
    group_alive_after_term: bool = False,
    group_alive_after_kill: bool = False,
    child_log: Mapping[str, Any] | None = None,
) -> None:
    record = {
        "schema": "a2_cb2h_toeout20_owned_process_teardown_v1",
        "status": status,
        "pgid": int(pgid) if pgid is not None else None,
        "returncode": returncode,
        "unresolved": bool(unresolved),
        "term_sent": bool(term_sent),
        "kill_sent": bool(kill_sent),
        "group_alive_after_term": bool(group_alive_after_term),
        "group_alive_after_kill": bool(group_alive_after_kill),
        "child_log": dict(child_log) if child_log is not None else None,
        "post_seal_boundary_s": POST_SEAL_TEARDOWN_BOUNDARY_S,
    }
    _atomic_json_write(root / "teardown_record.json", record)


def _terminate_owned_process(
    process,
    *,
    root: Path,
    reason: str,
    child_log_stream=None,
    child_log_path: Path | None = None,
) -> None:
    pgid = int(process.pid)
    import signal

    term_sent = False
    kill_sent = False
    try:
        os.killpg(pgid, signal.SIGTERM)
        term_sent = True
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass
    group_alive_after_term = _owned_process_group_alive(pgid)
    if group_alive_after_term:
        try:
            os.killpg(pgid, signal.SIGKILL)
            kill_sent = True
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
    group_alive_after_kill = _owned_process_group_alive(pgid)
    child_log = _finalize_child_log(child_log_stream, child_log_path)
    _write_teardown_record(
        root,
        status=reason,
        pgid=pgid,
        returncode=process.returncode,
        unresolved=group_alive_after_kill,
        term_sent=term_sent,
        kill_sent=kill_sent,
        group_alive_after_term=group_alive_after_term,
        group_alive_after_kill=group_alive_after_kill,
        child_log=child_log,
    )


def _run_owned_process(command: tuple[str, ...], *, root: Path, environment: Mapping[str, str], seal_path: Path | None, timeout_s: int) -> int:
    """Run one leased process group; failures terminate the exact PGID once with no retry."""
    import time

    child_log_stream, child_log_path = _open_exclusive_child_log(root)
    process = None
    record_written = False
    termination_started = False
    try:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(REPO_ROOT),
                env=dict(environment),
                start_new_session=True,
                stdout=child_log_stream,
                stderr=child_log_stream,
            )
        except BaseException:
            child_log = _finalize_child_log(child_log_stream, child_log_path)
            child_log_stream = None
            _write_teardown_record(
                root,
                status="SPAWN_FAILURE",
                pgid=None,
                returncode=None,
                unresolved=False,
                child_log=child_log,
            )
            record_written = True
            raise

        start = time.monotonic()
        seal_seen_at = None
        while True:
            returncode = process.poll()
            now = time.monotonic()
            if seal_path is not None and seal_path.is_file() and seal_seen_at is None:
                seal_seen_at = now
            if returncode is not None:
                if returncode != 0:
                    termination_started = True
                    _terminate_owned_process(
                        process,
                        root=root,
                        reason="CHILD_FAILURE",
                        child_log_stream=child_log_stream,
                        child_log_path=child_log_path,
                    )
                    child_log_stream = None
                    record_written = True
                    raise RuntimeError(f"owned child returned rc={returncode}")
                if _owned_process_group_alive(process.pid):
                    termination_started = True
                    _terminate_owned_process(
                        process,
                        root=root,
                        reason="SURVIVING_PEER",
                        child_log_stream=child_log_stream,
                        child_log_path=child_log_path,
                    )
                    child_log_stream = None
                    record_written = True
                    raise RuntimeError("owned child returned while its process group still has survivors")
                child_log = _finalize_child_log(child_log_stream, child_log_path)
                child_log_stream = None
                if seal_seen_at is None:
                    _write_teardown_record(
                        root,
                        status="NATURAL_UNSEALED",
                        pgid=process.pid,
                        returncode=returncode,
                        unresolved=True,
                        child_log=child_log,
                    )
                    record_written = True
                    raise RuntimeError("owned child exited successfully without its sealed artifact")
                _write_teardown_record(
                    root,
                    status="NATURAL",
                    pgid=process.pid,
                    returncode=returncode,
                    unresolved=False,
                    child_log=child_log,
                )
                record_written = True
                return 0
            if seal_seen_at is not None and now - seal_seen_at >= POST_SEAL_TEARDOWN_BOUNDARY_S:
                termination_started = True
                _terminate_owned_process(
                    process,
                    root=root,
                    reason="POST_SEAL_TIMEOUT",
                    child_log_stream=child_log_stream,
                    child_log_path=child_log_path,
                )
                child_log_stream = None
                record_written = True
                raise RuntimeError("owned child exceeded the post-seal natural teardown boundary")
            if now - start >= timeout_s:
                termination_started = True
                _terminate_owned_process(
                    process,
                    root=root,
                    reason="PROCESS_TIMEOUT",
                    child_log_stream=child_log_stream,
                    child_log_path=child_log_path,
                )
                child_log_stream = None
                record_written = True
                raise RuntimeError("owned child exceeded its process timeout")
            time.sleep(0.25)
    except BaseException:
        if not record_written:
            if process is not None and not termination_started and _owned_process_group_alive(process.pid):
                termination_started = True
                _terminate_owned_process(
                    process,
                    root=root,
                    reason="INTERRUPTED",
                    child_log_stream=child_log_stream,
                    child_log_path=child_log_path,
                )
                child_log_stream = None
            elif process is not None and child_log_stream is not None:
                child_log = _finalize_child_log(child_log_stream, child_log_path)
                child_log_stream = None
                _write_teardown_record(
                    root,
                    status="INTERRUPTED",
                    pgid=process.pid,
                    returncode=process.returncode,
                    unresolved=False,
                    child_log=child_log,
                )
            elif process is None and child_log_stream is not None:
                child_log = _finalize_child_log(child_log_stream, child_log_path)
                child_log_stream = None
                _write_teardown_record(
                    root,
                    status="SPAWN_FAILURE",
                    pgid=None,
                    returncode=None,
                    unresolved=False,
                    child_log=child_log,
                )
        raise


def _terminate_rank_children(
    children: Mapping[int, Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    import signal
    import time

    for child in children.values():
        process = child["process"]
        if process.poll() is None:
            try:
                os.killpg(int(process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if all(child["process"].poll() is not None for child in children.values()):
            break
        time.sleep(0.25)
    for child in children.values():
        process = child["process"]
        if process.poll() is None:
            try:
                os.killpg(int(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
    for child in children.values():
        process = child["process"]
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
    child_logs = {
        f"rank{rank}": _finalize_child_log(child["stream"], child["path"])
        for rank, child in children.items()
    }
    unresolved = any(_owned_process_group_alive(int(child["process"].pid)) for child in children.values())
    return child_logs, unresolved


def _run_owned_rank_processes(
    command: tuple[str, ...],
    *,
    root: Path,
    environment: Mapping[str, str],
    seal_path: Path | None,
    timeout_s: int,
) -> int:
    import time

    children: dict[int, dict[str, Any]] = {}
    teardown_written = False
    try:
        (root / "ranks").mkdir(parents=True, exist_ok=True)
        for rank in range(4):
            (root / "ranks" / f"rank{rank}").mkdir(parents=True, exist_ok=True)
            stream, path = _open_exclusive_child_log(root, rank)
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(REPO_ROOT),
                    env=_rank_child_environment(environment, rank),
                    start_new_session=True,
                    stdout=stream,
                    stderr=stream,
                )
            except BaseException:
                _finalize_child_log(stream, path)
                raise
            children[rank] = {"process": process, "stream": stream, "path": path}

        start = time.monotonic()
        while True:
            completed = {
                rank: child["process"].poll()
                for rank, child in children.items()
            }
            failed = [(rank, code) for rank, code in completed.items() if code not in (None, 0)]
            if failed:
                child_logs, unresolved = _terminate_rank_children(children)
                _write_teardown_record(
                    root,
                    status="CHILD_FAILURE",
                    pgid=None,
                    returncode=int(failed[0][1]),
                    unresolved=unresolved,
                    child_log=child_logs,
                )
                teardown_written = True
                raise RuntimeError(f"rank child failed: rank={failed[0][0]} rc={failed[0][1]}")
            if all(code is not None for code in completed.values()):
                child_logs = {
                    f"rank{rank}": _finalize_child_log(child["stream"], child["path"])
                    for rank, child in children.items()
                }
                if seal_path is None or not seal_path.is_file():
                    _write_teardown_record(
                        root,
                        status="NATURAL_UNSEALED",
                        pgid=None,
                        returncode=0,
                        unresolved=True,
                        child_log=child_logs,
                    )
                    teardown_written = True
                    raise RuntimeError("rank children exited successfully without their sealed artifact")
                _write_teardown_record(
                    root,
                    status="NATURAL",
                    pgid=None,
                    returncode=0,
                    unresolved=False,
                    child_log=child_logs,
                )
                teardown_written = True
                return 0
            if time.monotonic() - start >= timeout_s:
                child_logs, unresolved = _terminate_rank_children(children)
                _write_teardown_record(
                    root,
                    status="PROCESS_TIMEOUT",
                    pgid=None,
                    returncode=None,
                    unresolved=unresolved,
                    child_log=child_logs,
                )
                teardown_written = True
                raise RuntimeError("rank children exceeded their process timeout")
            time.sleep(0.25)
    except BaseException:
        if not teardown_written:
            child_logs, unresolved = _terminate_rank_children(children)
            _write_teardown_record(
                root,
                status="INTERRUPTED",
                pgid=None,
                returncode=None,
                unresolved=unresolved,
                child_log=child_logs,
            )
        raise


def _rank_command(mode: str, output_root: Path) -> tuple[str, ...]:
    batches = 1 if mode == "admission" else 8000
    save_frequency = 1 if mode == "admission" else 500
    envs = 16 if mode == "geometry" else 64
    rank_hydra_dir = f"{Path(output_root).expanduser().resolve()}/ranks/rank${{oc.env:RANK}}/.hydra"
    return (
        str(ISAACLAB_PYTHON),
        "gr00t/rl/train_agent_trl.py",
        f"+exp={CONFIG_NAME}",
        f"experiment_dir={output_root}",
        f"num_envs={envs}",
        f"algo.trl.num_total_batches={batches}",
        "checkpoint=null",
        "auto_load_latest=false",
        "use_wandb=false",
        "+algo.config.mgpu_runner_mode=" + mode,
        f"++algo.config.p2_lifecycle.target_global_step={batches}",
        f"++callbacks.model_save.save_frequency={save_frequency}",
        "++algo.config.distill_only=true",
        "++algo.config.freeze_noise_std=true",
        "hydra.run.dir=" + rank_hydra_dir,
        "hydra.sweep.dir=" + rank_hydra_dir,
        *(
            (
                "++algo.config.mixed_rollout_schedule=[{phase:L0,start_step:0,end_step:1,ratio:1.0}]",
            )
            if mode == "admission"
            else ()
        ),
    )


def _rank_child_environment(base_environment: Mapping[str, str], rank: int) -> dict[str, str]:
    if rank not in LOGICAL_TO_PHYSICAL:
        raise ValueError(f"rank must be one of 0..3; got {rank!r}")
    environment = dict(base_environment)
    for name in (
        "ACCELERATE_TORCH_DEVICE",
        "ACCELERATE_BYPASS_DEVICE_MAP",
        "ACCELERATE_USE_CPU",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": str(LOGICAL_TO_PHYSICAL[rank]),
            "RANK": str(rank),
            "WORLD_SIZE": "4",
            "LOCAL_RANK": "0",
            "LOCAL_WORLD_SIZE": "1",
            "MASTER_ADDR": "127.0.0.1",
            "MASTER_PORT": str(MASTER_PORT),
            "A2_GPU_BINDING_MODE": GPU_BINDING_MODE,
            "A2_EXPECTED_WORLD_SIZE": "4",
            "A2_EXPECTED_RANK": str(rank),
            "A2_EXPECTED_HOST_GPU_INDEX": str(LOGICAL_TO_PHYSICAL[rank]),
            "A2_EXPECTED_LOGICAL_GPU_INDEX": "0",
            "A2_EXPECTED_GPU_UUID": LOGICAL_TO_UUID[rank],
            "A2_EXPECTED_PHYSICAL_GPU_SET": CUDA_VISIBLE_DEVICES,
            "A2_EXPECTED_MASTER_ADDR": "127.0.0.1",
            "A2_EXPECTED_MASTER_PORT": str(MASTER_PORT),
        }
    )
    return environment


def _rank_launch_contract(mode: str, output_root: Path) -> dict[str, Any]:
    command = list(_rank_command(mode, output_root))
    return {
        "launcher": "independent_single_gpu_children",
        "world_size": 4,
        "master_addr": "127.0.0.1",
        "master_port": MASTER_PORT,
        "local_rank": 0,
        "local_world_size": 1,
        "fail_fast": "any_nonzero_child_terminates_all_exact_owned_children",
        "ranks": [
            {
                "rank": rank,
                "physical_gpu": LOGICAL_TO_PHYSICAL[rank],
                "cuda_visible_devices": str(LOGICAL_TO_PHYSICAL[rank]),
                "local_rank": 0,
                "local_world_size": 1,
                "world_size": 4,
                "master_addr": "127.0.0.1",
                "master_port": MASTER_PORT,
                "a2_gpu_binding_mode": GPU_BINDING_MODE,
                "a2_expected_host_gpu_index": LOGICAL_TO_PHYSICAL[rank],
                "a2_expected_logical_gpu_index": 0,
                "a2_expected_gpu_uuid": LOGICAL_TO_UUID[rank],
                "a2_expected_physical_gpu_set": CUDA_VISIBLE_DEVICES,
                "command": command,
            }
            for rank in range(4)
        ],
    }


def _geometry_plan_command(output_root: Path) -> tuple[str, ...]:
    """Return the deterministic single-GPU c18 evaluator command for one output root."""
    return _geometry_command(
        output_root,
        output_root / "_geometry_overlay",
        output_root / "_eval_input" / TEACHER_CHECKPOINT.name,
    )


def build_plan(mode: str = "dry-run", *, manual_camera_approved: bool = False) -> dict[str, Any]:
    if mode not in {"dry-run", "geometry", "teacher-render", "admission", "formal"}:
        raise ValueError(f"unsupported runner mode: {mode!r}")
    if mode == "formal" and not manual_camera_approved:
        raise ValueError("formal mode requires --manual-camera-approved")
    if mode != "formal" and manual_camera_approved:
        raise ValueError("--manual-camera-approved is valid only with formal mode")
    geometry = validate_toeout6_geometry()
    if mode in {"geometry", "teacher-render"}:
        batch = validate_geometry_batch_contract()
        schedule = ()
    elif mode == "admission":
        batch = validate_batch_contract(mode="admission")
        schedule = validate_admission_rollout_schedule()
    else:
        batch = validate_batch_contract(mode="formal")
        schedule = validate_rollout_schedule()
    provenance = validate_provenance()
    if mode == "dry-run":
        output_roots = {name: str(path) for name, path in MODE_OUTPUTS.items()}
        output_roots["teacher-render"] = str(TEACHER_RENDER_ROOT)
        command = None
    else:
        root = _output_root_for_mode(mode)
        output_roots = {mode: str(root)}
        command = list(
            _geometry_plan_command(root)
            if mode == "geometry"
            else _teacher_render_command(root, root / "_geometry_overlay", root / "_eval_input" / TEACHER_CHECKPOINT.name)
            if mode == "teacher-render"
            else _rank_command(mode, root)
        )
    manual_camera = _manual_camera_approval_record() if manual_camera_approved else None
    rank_launch = (
        _rank_launch_contract(mode, _output_root_for_mode(mode))
        if mode in {"admission", "formal"}
        else None
    )
    return {
        "schema": "a2_cb2h_toeout6_mgpu_plan_v1",
        "mode": mode,
        "dry_run": mode == "dry-run",
        "architecture_id": ARCHITECTURE_ID,
        "topology_id": TOPOLOGY_ID,
        "geometry": geometry,
        "manual_camera_approved": manual_camera_approved,
        "manual_camera_geometry": manual_camera["geometry"] if manual_camera is not None else None,
        "teacher_render_manifest_path": (
            manual_camera["teacher_render_manifest_path"] if manual_camera is not None else None
        ),
        "teacher_render_manifest_sha256": (
            manual_camera["teacher_render_manifest_sha256"] if manual_camera is not None else None
        ),
        "batch": batch,
        "rollout_schedule": list(schedule),
        "provenance": provenance,
        "output_roots": output_roots,
        "port": {"distributed": MASTER_PORT, "geometry": None},
        "command": command,
        "rank_launch": rank_launch,
        "output_ownership": {
            "rank0": ["canonical_config", "step0_manifest", "model_step_*.pt", "aggregate_proof"],
            "rank0_proof": ["ranks/rank0/rank_proof.json"],
            "rank1": ["ranks/rank1/"],
            "rank2": ["ranks/rank2/"],
            "rank3": ["ranks/rank3/"],
            "fresh_init": "rank0-only; formal mode never reuses admission output",
        },
        "geometry_diagnostic": {
            "device": "physical_gpu4",
            "seed": 0,
            "envs": 16,
            "semantic_segmentation": "diagnostic_only",
            "critical_frames": "every stage1-4 frame plus +/-10 control steps around transitions",
            "minimum_handle_pixels": 16,
            "minimum_d435_views": 1,
            "zero_samples": "fail",
            "top_view_artifact": "top_view_geometry.json",
            "policy_rgb_contract_unchanged": True,
        },
        "admission": {
            "iterations": 1,
            "episodes": 256,
            "global_transitions": 2048,
            "finite_loss_gradient_checkpoint_optimizer": True,
            "synchronized_hashes": True,
            "per_rank_proofs": True,
        },
        "formal": {
            "iterations": 8000,
            "save_frequency": 500,
            "final_checkpoint": "model_step_008000.pt",
            "fresh_init": True,
            "no_resume": True,
            "failure_policy": "terminate_leased_peers_without_retry_or_downgrade",
            "post_seal_teardown_boundary_s": POST_SEAL_TEARDOWN_BOUNDARY_S,
            "natural_teardown_claim": False,
        },
        "teacher_render": {
            "device": "physical_gpu4",
            "seed": 0,
            "envs": 16,
            "view_paths": [
                str(TEACHER_RENDER_ROOT / "teacher_videos" / f"{view}_env0001.mp4")
                for view in (*TEACHER_RENDER_VIEWS, TEACHER_RENDER_SIDE_BY_SIDE_VIEW)
            ],
            "success_gate": "Teacher process + four finalized nonempty MP4s + SHA/size manifest; manual decode/visual review",
            "pose_readback_gate": False,
            "semantic_pixel_gate": False,
            "stage_coverage_gate": False,
            "panorama": False,
        },
    }


def _fresh_output_guard(mode: str) -> Path:
    root = _output_root_for_mode(mode)
    if root.exists():
        raise FileExistsError(f"approved output root must be fresh and absent: {root}")
    if mode == "teacher-render":
        return root
    if root.parent != OUTPUT_ROOT:
        raise RuntimeError("approved output root escaped the sealed parent")
    return root


def _build_runtime_environment(mode: str) -> dict[str, str]:
    env = dict(os.environ)
    for key in (
        "WORLD_SIZE",
        "LOCAL_WORLD_SIZE",
        "RANK",
        "LOCAL_RANK",
        "MASTER_ADDR",
        "MASTER_PORT",
        "A2_GPU_BINDING_MODE",
        "A2_EXPECTED_WORLD_SIZE",
        "A2_EXPECTED_HOST_GPU_INDEX",
        "A2_EXPECTED_LOGICAL_GPU_INDEX",
        "A2_EXPECTED_GPU_UUID",
        "A2_EXPECTED_LOCAL_RANK",
        "ACCELERATE_TORCH_DEVICE",
        "ACCELERATE_BYPASS_DEVICE_MAP",
        "ACCELERATE_USE_CPU",
    ):
        env.pop(key, None)
    if mode in {"geometry", "teacher-render"}:
        env.update(
            {
                "CUDA_VISIBLE_DEVICES": "4",
                "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                "HYDRA_FULL_ERROR": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )
        return env
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": CUDA_VISIBLE_DEVICES,
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "MASTER_ADDR": "127.0.0.1",
            "MASTER_PORT": str(MASTER_PORT),
        }
    )
    return env


def run_mode(mode: str, *, manual_camera_approved: bool = False) -> int:
    if mode not in {*MODE_OUTPUTS, "teacher-render"}:
        raise ValueError(f"runtime mode must be geometry, teacher-render, admission, or formal; got {mode!r}")
    if mode == "formal" and not manual_camera_approved:
        raise ValueError("formal mode requires --manual-camera-approved")
    if mode != "formal" and manual_camera_approved:
        raise ValueError("--manual-camera-approved is valid only with formal mode")
    if mode == "admission":
        _validate_admission_prerequisite()
    root = _fresh_output_guard(mode)
    plan = build_plan(mode, manual_camera_approved=manual_camera_approved)
    root.mkdir(parents=True, exist_ok=False)
    _atomic_json_write(root / "sealed_plan.json", plan)
    if mode == "geometry":
        top_view_path = root / "top_view_geometry.json"
        _atomic_json_write(top_view_path, build_top_view_geometry())
        overlay_root, _, runtime_checkpoint = _prepare_geometry_overlay(root)
        command = tuple(plan["command"])
        expected_overlay_root = root / "_geometry_overlay"
        expected_checkpoint = root / "_eval_input" / TEACHER_CHECKPOINT.name
        if overlay_root != expected_overlay_root or runtime_checkpoint != expected_checkpoint:
            raise RuntimeError("sealed geometry command identity drifted before dispatch")
        environment = _build_runtime_environment(mode)
        _run_owned_process(
            command,
            root=root,
            environment=environment,
            seal_path=root / "metrics_eval.json",
            timeout_s=ADMISSION_PROCESS_TIMEOUT_S,
        )
        evidence_path = _validate_geometry_runtime(root, top_view_path, command)
        print(f"[A2_TOEOUT20_GEOMETRY_SEALED] {evidence_path}", flush=True)
        return 0
    if mode == "teacher-render":
        overlay_root, _, runtime_checkpoint = _prepare_geometry_overlay(root, teacher_render=True)
        command = tuple(plan["command"])
        environment = _build_runtime_environment(mode)
        _run_owned_process(
            command,
            root=root,
            environment=environment,
            seal_path=root / "metrics_eval.json",
            timeout_s=ADMISSION_PROCESS_TIMEOUT_S,
        )
        expected = root / "_geometry_overlay"
        if overlay_root != expected or runtime_checkpoint != root / "_eval_input" / TEACHER_CHECKPOINT.name:
            raise RuntimeError("sealed Teacher-render overlay identity drifted before dispatch")
        manifest_path = _validate_teacher_render_runtime(root)
        print(f"[A2_TOEOUT6_TEACHER_RENDER_SEALED] {manifest_path}", flush=True)
        return 0
    command = tuple(plan["command"])
    environment = _build_runtime_environment(mode)
    # Each owned child receives its global rank and one physical GPU as a
    # process-local cuda:0; any missing distributed identity fails fast.
    _run_owned_rank_processes(
        command,
        root=root,
        environment=environment,
        seal_path=root / "aggregate_proof.json",
        timeout_s=ADMISSION_PROCESS_TIMEOUT_S if mode == "admission" else FORMAL_PROCESS_TIMEOUT_S,
    )
    _validate_training_artifacts(mode, root)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "geometry", "teacher-render", "admission", "formal"), required=True)
    parser.add_argument(
        "--manual-camera-approved",
        action="store_true",
        help="acknowledge the manually reviewed pitch50 Teacher camera render for formal mode",
    )
    args = parser.parse_args(argv)
    if args.mode == "formal" and not args.manual_camera_approved:
        parser.error("--mode formal requires --manual-camera-approved")
    if args.mode != "formal" and args.manual_camera_approved:
        parser.error("--manual-camera-approved is valid only with --mode formal")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "dry-run":
        # Deliberately do not call mkdir, touch, Hydra, Accelerate, or Kit.
        print(canonical_json(build_plan("dry-run")), flush=True)
        return 0
    return run_mode(args.mode, manual_camera_approved=args.manual_camera_approved)


if __name__ == "__main__":
    raise SystemExit(main())
