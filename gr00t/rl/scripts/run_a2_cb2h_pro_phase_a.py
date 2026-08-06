#!/usr/bin/env python3
"""Plan and execute the sequential Pro Phase-A N1/N2 formal evaluations.

The default mode is a CPU-only dry-run.  ``--execute`` is the explicit opt-in
for the future physical GPU7 run (normally from an independently created tmux
session); this revision never creates tmux sessions or launches IsaacSim during
tests.  Every subprocess is a fresh formal v19 wrapper invocation with a
unique output root and the sealed c18/G2 provenance on its command line.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gr00t.rl.scripts import run_a2_student_eval_v19 as eval_v19
from gr00t.rl.scripts import run_a2_cb2h_pro_n5 as n5_runner


REPO_ROOT = eval_v19.REPO_ROOT
EVAL_WRAPPER = Path(eval_v19.__file__).resolve(strict=True)
RUNTIME_REPOSITORY = eval_v19.RUNTIME_REPOSITORY
REQUIRED_STUDENT_STEPS = (1000, 2500, 5000, 7500, 10000)
N1_REPLICATE_COUNT = 3
N2_EXTRA_REPLICATE_COUNT = 2
N3_REPLICATE_COUNT = 3
N5_REPLICATE_COUNT = 3
N1_GOAL_PASS = 40
N1_GOAL_INCONCLUSIVE = 32
N1_STAGE0_PASS_MAX = 2
N1_STAGE0_BLOCKER_MIN = 7
PHASE_A_SCHEMA = "a2_cb2h_pro_phase_a_v1"
N5_FORMAL_MODE = "packed"
N5_MANIFEST_SCHEMA = n5_runner.N5_SCHEMA
EXPECTED_N3_PHASE_MANIFEST_SHA256 = "0d5cfec4dc06a47c28b69bbcd14c9ad6216e8bccbbb956848e6dccb1b419077e"
EXPECTED_N2_PHASE_MANIFEST_SHA256 = "a7e17388f2f51ea12d6137bd6d2e6fe48b2078e0907b409a1c02ce1fa1bbe700"
EXPECTED_N3_H5_IDENTITIES = {
    "replicate_01": {
        "sha256": "8c39164f77fe05a58892da98a141c52f3e3acfabf11d3531d5a9b81234f92393",
        "size_bytes": 1491401563,
    },
    "replicate_02": {
        "sha256": "1a41e10f12873af9687e12b4ce995564c1c58bf529ba1a813c7c900d24ddbcdf",
        "size_bytes": 1491930125,
    },
    "replicate_03": {
        "sha256": "1dcccb42cc592eceae5702c12b29a15382d1d3d2685d96d3eaeb10cfd9898175",
        "size_bytes": 1491374976,
    },
}
FORBIDDEN_DISTRIBUTED_ENV = (
    "WORLD_SIZE",
    "RANK",
    "LOCAL_RANK",
    "LOCAL_WORLD_SIZE",
    "MASTER_ADDR",
    "MASTER_PORT",
    "ACCELERATE_TORCH_DEVICE",
    "ACCELERATE_BYPASS_DEVICE_MAP",
)


class MissingEvidenceError(RuntimeError):
    """Required checkpoint/evidence is absent; never silently shrink a sweep."""


@dataclass(frozen=True)
class PlannedRun:
    operation: str
    controller: str
    checkpoint: Path
    expected_global_step: int
    checkpoint_sha256: str
    config_path: Path
    config_sha256: str
    overlay_repository: Path
    experience_path: Path
    experience_sha256: str
    experience_camera_mode: str
    replicate_id: str
    output_root: Path
    command: tuple[str, ...]
    environment: Mapping[str, str]
    student_d435i_forward_mode: str | None = None
    n5_manifest_path: Path | None = None
    n5_manifest_sha256: str | None = None
    capture_controller: str | None = None
    teacher_checkpoint: Path | None = None
    teacher_checkpoint_sha256: str | None = None
    teacher_config_path: Path | None = None
    teacher_config_sha256: str | None = None
    teacher_manifest_path: Path | None = None
    teacher_manifest_sha256: str | None = None


def _safe_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _safe_json(tolist())
    item = getattr(value, "item", None)
    if callable(item):
        return _safe_json(item())
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(_safe_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def build_gpu7_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Construct the exact single-visible-logical-cuda0 binding-v3 environment."""
    environment = dict(os.environ if base is None else base)
    for name in FORBIDDEN_DISTRIBUTED_ENV:
        environment.pop(name, None)
    for name in tuple(environment):
        if name.startswith("A2_GPU_") or name.startswith("A2_EXPECTED_"):
            environment.pop(name, None)
    environment.update(
        {
            "A2_GPU_BINDING_MODE": eval_v19.EXPECTED_GPU_BINDING_MODE,
            "CUDA_VISIBLE_DEVICES": eval_v19.EXPECTED_GPU_INDEX,
            "CUDA_DEVICE_ORDER": eval_v19.EXPECTED_CUDA_DEVICE_ORDER,
            "A2_EXPECTED_WORLD_SIZE": "1",
            "A2_EXPECTED_HOST_GPU_INDEX": eval_v19.EXPECTED_GPU_INDEX,
            "A2_EXPECTED_LOGICAL_GPU_INDEX": eval_v19.EXPECTED_LOGICAL_GPU_INDEX,
            "A2_EXPECTED_GPU_UUID": eval_v19.EXPECTED_GPU_UUID,
        }
    )
    return environment


def validate_runtime_and_overlay_paths(
    overlay_repository: Path = REPO_ROOT,
    runtime_repository: Path = RUNTIME_REPOSITORY,
) -> dict[str, str]:
    """Validate exact c18 source identity without importing IsaacLab."""
    overlay = overlay_repository.expanduser().resolve(strict=True)
    runtime = runtime_repository.expanduser().resolve(strict=True)
    if not (overlay / "gr00t/rl/scripts/run_a2_student_eval_v19.py").is_file():
        raise FileNotFoundError(f"overlay eval wrapper is unavailable: {overlay}")
    if not (runtime / ".git").exists():
        raise FileNotFoundError(f"c18 runtime repository is unavailable: {runtime}")
    result = subprocess.run(
        ["git", "-C", str(runtime), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"unable to inspect c18 runtime repository: {runtime}: {result.stderr.strip()}")
    commit = result.stdout.strip()
    if commit != eval_v19.EXPECTED_RUNTIME_COMMIT:
        raise RuntimeError(
            f"c18 runtime commit mismatch: expected {eval_v19.EXPECTED_RUNTIME_COMMIT}, got {commit}"
        )
    return {"overlay_repository": str(overlay), "runtime_repository": str(runtime), "runtime_commit": commit}


def _output_roots_are_unique_and_absent(output_roots: Sequence[Path]) -> None:
    normalized = [path.expanduser().resolve() for path in output_roots]
    if len(set(normalized)) != len(normalized):
        raise ValueError("planned formal output roots are not unique")
    existing = [str(path) for path in normalized if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite planned formal output roots: {existing}")


def _require_phase_output_root_absent(output_root: Path) -> Path:
    output_root = output_root.expanduser().resolve()
    if output_root.exists():
        raise FileExistsError(
            "dedicated Phase-A output root must be absent before start; "
            f"refusing existing root: {output_root}"
        )
    return output_root


def claim_phase_output_root(output_root: Path) -> Path:
    """Atomically claim the dedicated root before launching any subprocess."""
    output_root = _require_phase_output_root_absent(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir()
    return output_root


def _checkpoint_path(checkpoint_dir: Path, step: int) -> Path:
    if isinstance(step, bool) or step <= 0:
        raise ValueError(f"checkpoint step must be a positive integer: {step!r}")
    return checkpoint_dir.expanduser().resolve() / f"model_step_{step:06d}.pt"


def validate_required_student_checkpoints(
    checkpoint_dir: Path,
) -> dict[int, dict[str, Any]]:
    """Validate every required N2 checkpoint; missing steps are fatal evidence gaps."""
    checkpoint_dir = checkpoint_dir.expanduser().resolve(strict=True)
    missing = [
        str(_checkpoint_path(checkpoint_dir, step))
        for step in REQUIRED_STUDENT_STEPS
        if not _checkpoint_path(checkpoint_dir, step).is_file()
    ]
    if missing:
        raise MissingEvidenceError(
            "MISSING_EVIDENCE: required Student checkpoint set is incomplete; "
            f"missing={missing}"
        )
    validated: dict[int, dict[str, Any]] = {}
    for step in REQUIRED_STUDENT_STEPS:
        checkpoint = _checkpoint_path(checkpoint_dir, step)
        validated[step] = eval_v19.validate_checkpoint_artifacts(
            checkpoint,
            checkpoint.with_name("config.yaml"),
            controller="student",
            expected_global_step=step,
        )
    return validated


def build_eval_command(
    *,
    operation: str,
    controller: str,
    checkpoint: Path,
    expected_global_step: int,
    checkpoint_sha256: str,
    config_path: Path,
    config_sha256: str,
    experience_path: Path,
    experience_sha256: str,
    experience_camera_mode: str,
    replicate_id: str,
    output_root: Path,
    overlay_repository: Path = REPO_ROOT,
    runtime_repository: Path = RUNTIME_REPOSITORY,
    python_executable: str = sys.executable,
    teacher_info: Mapping[str, Any] | None = None,
    student_d435i_forward_mode: str | None = None,
) -> tuple[str, ...]:
    if operation not in {"n1", "n2", "n3", "n5"}:
        raise ValueError(f"unknown Phase-A operation: {operation!r}")
    if controller not in eval_v19.CONTROLLERS:
        raise ValueError(f"unknown controller: {controller!r}")
    if operation == "n1" and controller != "teacher":
        raise ValueError("N1 is Teacher-only")
    if operation == "n2" and controller != "student":
        raise ValueError("N2 is Student-only")
    if operation == "n3" and controller != "student":
        raise ValueError("N3 is passive-Student-only")
    if operation == "n5" and controller != "student":
        raise ValueError("N5 is packed Student-only")
    if operation == "n5" and student_d435i_forward_mode != "packed":
        raise ValueError("N5 formal commands require explicit packed D435 mode")
    if operation != "n5" and student_d435i_forward_mode is not None:
        raise ValueError("explicit Student D435 mode is only valid for N5")
    mode = "n3" if operation == "n3" else "formal"
    command = [
        str(python_executable),
        str(EVAL_WRAPPER),
        "--mode",
        mode,
        "--controller",
        controller,
        "--checkpoint",
        str(checkpoint.expanduser().resolve()),
        "--checkpoint-sha256",
        checkpoint_sha256,
        "--checkpoint-config",
        str(config_path.expanduser().resolve()),
        "--checkpoint-config-sha256",
        config_sha256,
        "--experience-path",
        str(experience_path.expanduser().resolve()),
        "--experience-sha256",
        experience_sha256,
        "--experience-camera-mode",
        experience_camera_mode,
        "--expected-global-step",
        str(expected_global_step),
        "--case-seed",
        "0",
        "--replicate-id",
        replicate_id,
        "--output-root",
        str(output_root.expanduser().resolve()),
        "--overlay-repository",
        str(overlay_repository.expanduser().resolve()),
        "--runtime-repository",
        str(runtime_repository.expanduser().resolve()),
    ]
    if student_d435i_forward_mode is not None:
        command.extend(["--student-d435i-forward-mode", student_d435i_forward_mode])
    if operation == "n3":
        if not isinstance(teacher_info, Mapping):
            raise ValueError("N3 command construction requires the sealed Teacher identity")
        checkpoint = teacher_info.get("checkpoint")
        manifest = teacher_info.get("manifest")
        if not isinstance(checkpoint, Mapping) or not isinstance(manifest, Mapping):
            raise TypeError("N3 Teacher identity must contain checkpoint and manifest mappings")
        required = {
            "path": checkpoint.get("path"),
            "sha256": checkpoint.get("sha256"),
            "config_path": checkpoint.get("config_path"),
            "config_sha256": checkpoint.get("config_sha256"),
            "manifest_path": manifest.get("path"),
            "manifest_sha256": manifest.get("sha256"),
        }
        if any(value is None for value in required.values()):
            raise ValueError("N3 Teacher identity is incomplete")
        command.extend(
            [
                "--n3-control-controller",
                "teacher",
                "--n3-teacher-checkpoint",
                str(Path(required["path"]).expanduser().resolve()),
                "--n3-teacher-sha256",
                str(required["sha256"]),
                "--n3-teacher-config",
                str(Path(required["config_path"]).expanduser().resolve()),
                "--n3-teacher-config-sha256",
                str(required["config_sha256"]),
                "--n3-teacher-manifest",
                str(Path(required["manifest_path"]).expanduser().resolve()),
                "--n3-teacher-manifest-sha256",
                str(required["manifest_sha256"]),
            ]
        )
    return tuple(command)


def _planned_run(
    *,
    operation: str,
    controller: str,
    checkpoint_info: Mapping[str, Any],
    replicate_id: str,
    output_root: Path,
    overlay_repository: Path,
    runtime_repository: Path,
    python_executable: str,
    capture_controller: str | None = None,
    teacher_info: Mapping[str, Any] | None = None,
    student_d435i_forward_mode: str | None = None,
    n5_manifest_path: Path | None = None,
    n5_manifest_sha256: str | None = None,
) -> PlannedRun:
    checkpoint = Path(str(checkpoint_info["path"])).resolve(strict=True)
    config_path = Path(str(checkpoint_info["config_path"])).resolve(strict=True)
    expected_config_path = checkpoint.with_name("config.yaml")
    if config_path != expected_config_path:
        raise RuntimeError(
            "planned checkpoint config must be adjacent config.yaml: "
            f"expected={expected_config_path} got={config_path}"
        )
    config_sha256 = str(checkpoint_info["config_sha256"])
    if eval_v19.sha256_file(config_path) != config_sha256:
        raise RuntimeError(f"planned checkpoint config SHA256 drifted before command construction: {config_path}")
    overlay_repository = overlay_repository.expanduser().resolve(strict=True)
    experience_info = eval_v19.resolve_experience_source(overlay_repository, controller)
    experience_path = Path(str(experience_info["path"])).resolve(strict=True)
    experience_sha256 = str(experience_info["sha256"])
    experience_camera_mode = str(experience_info["camera_mode"])
    command = build_eval_command(
        operation=operation,
        controller=controller,
        checkpoint=checkpoint,
        expected_global_step=int(checkpoint_info["global_step"]),
        checkpoint_sha256=str(checkpoint_info["sha256"]),
        config_path=config_path,
        config_sha256=config_sha256,
        experience_path=experience_path,
        experience_sha256=experience_sha256,
        experience_camera_mode=experience_camera_mode,
        replicate_id=replicate_id,
        output_root=output_root,
        overlay_repository=overlay_repository,
        runtime_repository=runtime_repository,
        python_executable=python_executable,
        teacher_info=teacher_info,
        student_d435i_forward_mode=student_d435i_forward_mode,
    )
    teacher_checkpoint = None
    teacher_checkpoint_sha256 = None
    teacher_config_path = None
    teacher_config_sha256 = None
    teacher_manifest_path = None
    teacher_manifest_sha256 = None
    if operation == "n3":
        if capture_controller != "teacher" or not isinstance(teacher_info, Mapping):
            raise ValueError("N3 planned runs require capture_controller=teacher and Teacher identity")
        teacher_checkpoint_info = teacher_info.get("checkpoint")
        teacher_manifest_info = teacher_info.get("manifest")
        if not isinstance(teacher_checkpoint_info, Mapping) or not isinstance(
            teacher_manifest_info, Mapping
        ):
            raise TypeError("N3 Teacher identity must contain checkpoint and manifest mappings")
        teacher_checkpoint = Path(str(teacher_checkpoint_info["path"])).expanduser().resolve(strict=True)
        teacher_config_path = Path(str(teacher_checkpoint_info["config_path"])).expanduser().resolve(strict=True)
        teacher_manifest_path = Path(str(teacher_manifest_info["path"])).expanduser().resolve(strict=True)
        teacher_checkpoint_sha256 = str(teacher_checkpoint_info["sha256"])
        teacher_config_sha256 = str(teacher_checkpoint_info["config_sha256"])
        teacher_manifest_sha256 = str(teacher_manifest_info["sha256"])
    return PlannedRun(
        operation=operation,
        controller=controller,
        checkpoint=checkpoint,
        expected_global_step=int(checkpoint_info["global_step"]),
        checkpoint_sha256=str(checkpoint_info["sha256"]),
        config_path=config_path,
        config_sha256=config_sha256,
        overlay_repository=overlay_repository,
        experience_path=experience_path,
        experience_sha256=experience_sha256,
        experience_camera_mode=experience_camera_mode,
        replicate_id=replicate_id,
        output_root=output_root.expanduser().resolve(),
        command=command,
        environment=build_gpu7_environment(),
        student_d435i_forward_mode=student_d435i_forward_mode,
        n5_manifest_path=None if n5_manifest_path is None else n5_manifest_path.expanduser().resolve(),
        n5_manifest_sha256=n5_manifest_sha256,
        capture_controller=capture_controller,
        teacher_checkpoint=teacher_checkpoint,
        teacher_checkpoint_sha256=teacher_checkpoint_sha256,
        teacher_config_path=teacher_config_path,
        teacher_config_sha256=teacher_config_sha256,
        teacher_manifest_path=teacher_manifest_path,
        teacher_manifest_sha256=teacher_manifest_sha256,
    )


def build_n1_plan(
    output_root: Path,
    *,
    overlay_repository: Path = REPO_ROOT,
    runtime_repository: Path = RUNTIME_REPOSITORY,
    python_executable: str = sys.executable,
) -> list[PlannedRun]:
    validate_runtime_and_overlay_paths(overlay_repository, runtime_repository)
    output_root = _require_phase_output_root_absent(output_root)
    teacher_info = eval_v19.validate_checkpoint_artifacts(controller="teacher")
    roots = [
        output_root.expanduser().resolve() / "n1_teacher" / f"replicate_{index:02d}"
        for index in range(1, N1_REPLICATE_COUNT + 1)
    ]
    _output_roots_are_unique_and_absent(roots)
    return [
        _planned_run(
            operation="n1",
            controller="teacher",
            checkpoint_info=teacher_info,
            replicate_id=f"n1_rep{index:02d}",
            output_root=root,
            overlay_repository=overlay_repository,
            runtime_repository=runtime_repository,
            python_executable=python_executable,
        )
        for index, root in enumerate(roots, start=1)
    ]


def build_n2_plan(
    output_root: Path,
    checkpoint_dir: Path,
    *,
    overlay_repository: Path = REPO_ROOT,
    runtime_repository: Path = RUNTIME_REPOSITORY,
    python_executable: str = sys.executable,
) -> tuple[list[PlannedRun], dict[int, dict[str, Any]]]:
    validate_runtime_and_overlay_paths(overlay_repository, runtime_repository)
    output_root = _require_phase_output_root_absent(output_root)
    checkpoint_info = validate_required_student_checkpoints(checkpoint_dir)
    roots = [
        output_root.expanduser().resolve() / "n2_student" / f"step_{step:05d}" / "replicate_01"
        for step in REQUIRED_STUDENT_STEPS
    ]
    _output_roots_are_unique_and_absent(roots)
    plans = [
        _planned_run(
            operation="n2",
            controller="student",
            checkpoint_info=checkpoint_info[step],
            replicate_id="n2_rep01",
            output_root=root,
            overlay_repository=overlay_repository,
            runtime_repository=runtime_repository,
            python_executable=python_executable,
        )
        for step, root in zip(REQUIRED_STUDENT_STEPS, roots)
    ]
    return plans, checkpoint_info


def build_n3_plan(
    output_root: Path,
    *,
    overlay_repository: Path = REPO_ROOT,
    runtime_repository: Path = RUNTIME_REPOSITORY,
    python_executable: str = sys.executable,
) -> list[PlannedRun]:
    """Build exactly three sequential N3 Teacher-controlled capture runs."""
    validate_runtime_and_overlay_paths(overlay_repository, runtime_repository)
    output_root = _require_phase_output_root_absent(output_root)
    student_info = eval_v19.validate_checkpoint_artifacts(
        controller="student",
        expected_global_step=eval_v19.STUDENT_GLOBAL_STEP,
        expected_sha256=eval_v19.CHECKPOINT_SHA256,
        expected_config_sha256=eval_v19.CHECKPOINT_CONFIG_SHA256,
    )
    teacher_info = eval_v19.validate_teacher_identity()
    roots = [
        output_root.expanduser().resolve() / "n3_teacher_trajectories" / f"replicate_{index:02d}"
        for index in range(1, N3_REPLICATE_COUNT + 1)
    ]
    _output_roots_are_unique_and_absent(roots)
    plans = [
        _planned_run(
            operation="n3",
            controller="student",
            checkpoint_info=student_info,
            replicate_id=f"n3_rep{index:02d}",
            output_root=root,
            overlay_repository=overlay_repository,
            runtime_repository=runtime_repository,
            python_executable=python_executable,
            capture_controller="teacher",
            teacher_info=teacher_info,
        )
        for index, root in enumerate(roots, start=1)
    ]
    return plans


def build_n5_plan(
    output_root: Path,
    recalibrated_checkpoint_info: Mapping[str, Any],
    *,
    n5_manifest_path: Path | None = None,
    n5_manifest_sha256: str | None = None,
    overlay_repository: Path = REPO_ROOT,
    runtime_repository: Path = RUNTIME_REPOSITORY,
    python_executable: str = sys.executable,
) -> list[PlannedRun]:
    """Build exactly three fresh packed Student formal runs for N5."""
    validate_runtime_and_overlay_paths(overlay_repository, runtime_repository)
    output_root = _require_phase_output_root_absent(output_root)
    if not isinstance(recalibrated_checkpoint_info, Mapping):
        raise TypeError("N5 recalibrated checkpoint identity must be a mapping")
    required = ("path", "sha256", "config_path", "config_sha256", "global_step")
    if any(key not in recalibrated_checkpoint_info for key in required):
        raise ValueError("N5 recalibrated checkpoint identity is incomplete")
    if int(recalibrated_checkpoint_info["global_step"]) != eval_v19.STUDENT_GLOBAL_STEP:
        raise ValueError("N5 packed formal runs require the exact step10000 global_step")
    if n5_manifest_path is None or n5_manifest_sha256 is None:
        raise ValueError("N5 plans require --n5-manifest and --n5-manifest-sha256")
    validate_n5_manifest_identity(
        n5_manifest_path,
        n5_manifest_sha256,
        recalibrated_checkpoint_info,
    )
    roots = [
        output_root.expanduser().resolve() / "n5_student_packed" / f"replicate_{index:02d}"
        for index in range(1, N3_REPLICATE_COUNT + 1)
    ]
    _output_roots_are_unique_and_absent(roots)
    return [
        _planned_run(
            operation="n5",
            controller="student",
            checkpoint_info=recalibrated_checkpoint_info,
            replicate_id=f"n5_rep{index:02d}",
            output_root=root,
            overlay_repository=overlay_repository,
            runtime_repository=runtime_repository,
            python_executable=python_executable,
            student_d435i_forward_mode="packed",
            n5_manifest_path=n5_manifest_path,
            n5_manifest_sha256=n5_manifest_sha256,
        )
        for index, root in enumerate(roots, start=1)
    ]


def _load_json(path: Path) -> dict[str, Any]:
    with path.expanduser().resolve(strict=True).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"artifact must contain a JSON object: {path}")
    return value


def _require_sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA256 string")
    int(value, 16)
    return value


def _exact_identity_fields(
    actual: Mapping[str, Any], expected: Mapping[str, Any], name: str
) -> None:
    if not isinstance(actual, Mapping):
        raise RuntimeError(f"N5 manifest is missing {name} identity")
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            raise RuntimeError(
                f"N5 manifest {name} identity drift for {key}: "
                f"expected={expected_value!r} got={actual.get(key)!r}"
            )


def validate_n5_manifest_identity(
    manifest_path: Path,
    manifest_sha256: str,
    checkpoint_info: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the sealed N5 output before constructing formal plans."""
    manifest_path = manifest_path.expanduser().resolve(strict=True)
    expected_manifest_sha256 = _require_sha256(manifest_sha256, "N5 manifest SHA256")
    actual_manifest_sha256 = eval_v19.sha256_file(manifest_path)
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise RuntimeError(
            "N5 manifest SHA256 mismatch: "
            f"expected={expected_manifest_sha256} got={actual_manifest_sha256}"
        )
    manifest = _load_json(manifest_path)
    if manifest.get("schema") != N5_MANIFEST_SCHEMA or manifest.get("operation") != "n5":
        raise RuntimeError("N5 manifest schema/operation drifted")
    if manifest.get("sealed") is not True:
        raise RuntimeError("N5 manifest must be sealed=true")
    if manifest.get("d435i_forward_mode") != N5_FORMAL_MODE:
        raise RuntimeError("N5 manifest must identify packed D435 mode")
    gpu_identity = n5_runner.validate_gpu_identity(manifest.get("gpu_identity"))
    expected_source = {
        "path": str(n5_runner.CHECKPOINT),
        "sha256": n5_runner.CHECKPOINT_SHA256,
        "config_path": str(n5_runner.CHECKPOINT_CONFIG),
        "config_sha256": n5_runner.CHECKPOINT_CONFIG_SHA256,
        "global_step": eval_v19.STUDENT_GLOBAL_STEP,
        "controller": "student",
    }
    _exact_identity_fields(manifest.get("checkpoint_source"), expected_source, "source checkpoint")
    expected_output = {
        "path": str(Path(str(checkpoint_info["path"])).expanduser().resolve()),
        "sha256": str(checkpoint_info["sha256"]),
    }
    _exact_identity_fields(manifest.get("checkpoint_output"), expected_output, "output checkpoint")
    expected_config = {
        "path": str(Path(str(checkpoint_info["config_path"])).expanduser().resolve()),
        "sha256": str(checkpoint_info["config_sha256"]),
        "d435i_forward_mode": N5_FORMAL_MODE,
    }
    _exact_identity_fields(manifest.get("config"), expected_config, "output config")
    if Path(expected_output["path"]).with_name("config.yaml") != Path(expected_config["path"]):
        raise RuntimeError("N5 checkpoint/config output paths are not adjacent")
    if int(checkpoint_info.get("global_step", -1)) != eval_v19.STUDENT_GLOBAL_STEP:
        raise RuntimeError("N5 output checkpoint global_step must be exactly 10000")
    if checkpoint_info.get("controller") != "student":
        raise RuntimeError("N5 output checkpoint must identify controller=student")

    n3_input = manifest.get("n3_input")
    _exact_identity_fields(
        n3_input,
        {
            "root": str(n5_runner.N3_INPUT_ROOT),
            "phase_manifest_path": str(n5_runner.N3_INPUT_ROOT / "phase_a_manifest.json"),
            "phase_manifest_sha256": EXPECTED_N3_PHASE_MANIFEST_SHA256,
        },
        "N3 input",
    )
    n3_replicates = n3_input.get("replicates")
    if not isinstance(n3_replicates, list) or len(n3_replicates) != N3_REPLICATE_COUNT:
        raise RuntimeError("N5 manifest must enumerate exactly three N3 input replicates")
    by_id = {item.get("replicate_id"): item for item in n3_replicates if isinstance(item, Mapping)}
    if set(by_id) != set(EXPECTED_N3_H5_IDENTITIES):
        raise RuntimeError("N5 manifest N3 replicate identities drifted")
    for replicate_id, expected in EXPECTED_N3_H5_IDENTITIES.items():
        item = by_id[replicate_id]
        expected_path = n5_runner.N3_INPUT_ROOT / "n3_teacher_trajectories" / replicate_id / "teacher_trajectory.h5"
        _exact_identity_fields(
            item,
            {
                "replicate_id": f"replicate_{replicate_id.split('_')[-1]}",
                "h5_path": str(expected_path),
                "h5_sha256": expected["sha256"],
                "active_frame_count": 10206,
            },
            f"N3 {replicate_id}",
        )

    n4_baseline = manifest.get("n4_baseline")
    _exact_identity_fields(
        n4_baseline,
        {
            "root": str(n5_runner.N4_BASELINE_ROOT),
            "manifest_path": str(n5_runner.N4_BASELINE_ROOT / n5_runner.N4_MANIFEST_FILENAME),
            "manifest_sha256": n5_runner.EXPECTED_N4_MANIFEST_SHA256,
            "metrics_path": str(n5_runner.N4_BASELINE_ROOT / n5_runner.N4_METRICS_FILENAME),
            "metrics_sha256": n5_runner.EXPECTED_N4_METRICS_SHA256,
            "active_frames_path": str(n5_runner.N4_BASELINE_ROOT / n5_runner.N4_ACTIVE_FRAMES_FILENAME),
            "active_frames_sha256": n5_runner.EXPECTED_N4_ACTIVE_FRAMES_SHA256,
            "d435i_forward_mode": "sequential",
        },
        "N4 baseline",
    )

    calibration = manifest.get("calibration")
    _exact_identity_fields(
        calibration,
        {
            "encoder": "d435i_vision_module",
            "batch_norm_type": "SyncBatchNorm",
            "forward_mode": N5_FORMAL_MODE,
            "forward_call_count": n5_runner.EXPECTED_PACKED_FORWARD_CALLS,
            "active_frame_count": n5_runner.EXPECTED_ACTIVE_FRAMES,
            "packed_sample_count": n5_runner.EXPECTED_PACKED_SAMPLES,
            "expected_forward_call_count": n5_runner.EXPECTED_PACKED_FORWARD_CALLS,
            "expected_active_frame_count": n5_runner.EXPECTED_ACTIVE_FRAMES,
            "expected_packed_sample_count": n5_runner.EXPECTED_PACKED_SAMPLES,
            "head_fusion_lstm_mlp_calls": 0,
            "backward_call_count": 0,
            "optimizer_step_count": 0,
        },
        "calibration",
    )
    if manifest.get("training_performed") is not False:
        raise RuntimeError("N5 manifest training_performed must be false")
    if manifest.get("calibration_performed") is not True:
        raise RuntimeError("N5 manifest calibration_performed must be true")
    if manifest.get("backward_call_count") != 0 or manifest.get("optimizer_step_count") != 0:
        raise RuntimeError("N5 manifest reports forbidden training calls")
    checkpoint_output = manifest.get("checkpoint_output")
    allowed = checkpoint_output.get("allowed_policy_state_keys") if isinstance(checkpoint_output, Mapping) else None
    changed = checkpoint_output.get("changed_policy_state_keys") if isinstance(checkpoint_output, Mapping) else None
    if not isinstance(allowed, list) or not isinstance(changed, list) or not changed:
        raise RuntimeError("N5 manifest must claim non-empty BN-only changed policy state")
    if not set(changed).issubset(set(allowed)):
        raise RuntimeError("N5 changed policy state keys are not a subset of allowed keys")
    if any(
        not isinstance(key, str)
        or not key.startswith("d435i_vision_module.")
        or key.rsplit(".", 1)[-1] not in n5_runner.ALLOWED_BN_SUFFIXES
        for key in allowed
    ):
        raise RuntimeError("N5 allowed policy state claims are not D435 SyncBatchNorm buffers")
    if checkpoint_output.get("non_bn_policy_state_unchanged") is not True:
        raise RuntimeError("N5 manifest must claim non-BN policy state unchanged")
    if checkpoint_output.get("top_level_fields_unchanged") is not True:
        raise RuntimeError("N5 manifest must claim checkpoint top-level fields unchanged")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping):
        raise RuntimeError("N5 manifest is missing output artifact identities")
    _exact_identity_fields(outputs.get("checkpoint"), expected_output, "N5 output checkpoint artifact")
    _exact_identity_fields(
        outputs.get("config"),
        {"path": expected_config["path"], "sha256": expected_config["sha256"]},
        "N5 output config artifact",
    )
    return {
        "path": str(manifest_path),
        "sha256": actual_manifest_sha256,
        "gpu_identity": gpu_identity,
        "manifest": manifest,
    }


def load_formal_run(output_root: Path, controller: str) -> tuple[dict[str, Any], dict[str, Any]]:
    selection_name = "student_selection.json" if controller == "student" else "teacher_selection.json"
    selection_path = output_root.expanduser().resolve() / selection_name
    selection, metrics = eval_v19.load_sealed_selection(selection_path)
    if selection.get("controller", "student" if selection_name.startswith("student") else None) != controller:
        raise RuntimeError(f"formal artifact controller drift: expected {controller}, got {selection.get('controller')!r}")
    if metrics.get("controller", "student" if controller == "student" else None) != controller:
        raise RuntimeError("formal metrics controller drift")
    return selection, metrics


def case_identity_map(metrics: Mapping[str, Any]) -> dict[int, tuple[Any, ...]]:
    episodes = metrics.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != eval_v19.EXPECTED_EPISODES:
        raise RuntimeError("formal metrics must contain exactly 16 episodes")
    identities: dict[int, tuple[Any, ...]] = {}
    for episode in episodes:
        if not isinstance(episode, Mapping):
            raise TypeError("formal episode record must be a mapping")
        env_id = episode.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int):
            raise TypeError(f"formal case env_id must be an integer: {env_id!r}")
        case = episode.get("randomized_case")
        if not isinstance(case, Mapping) or set(case) != set(eval_v19.RANDOMIZED_CASE_KEYS):
            raise RuntimeError("formal case identity must contain exactly the four c18 fields")
        identity = tuple(_safe_json(case[key]) for key in eval_v19.RANDOMIZED_CASE_KEYS)
        if env_id in identities:
            raise RuntimeError(f"formal case map contains duplicate env_id={env_id}")
        identities[env_id] = identity
    if set(identities) != set(range(eval_v19.EXPECTED_NUM_ENVS)):
        raise RuntimeError("formal case map must cover env_id 0..15 exactly")
    return identities


def case_identity_map_sha256(identity: Mapping[int, Sequence[Any]]) -> str:
    """Return a deterministic hash for the exact four-field env case mapping."""
    normalized = {
        int(env_id): tuple(_safe_json(value) for value in values)
        for env_id, values in identity.items()
    }
    return __import__("hashlib").sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def assert_case_maps_equal(
    reference: Mapping[int, Sequence[Any]], candidate: Mapping[int, Sequence[Any]]
) -> None:
    if dict(reference) != dict(candidate):
        differing = sorted(
            env_id
            for env_id in set(reference) | set(candidate)
            if reference.get(env_id) != candidate.get(env_id)
        )
        raise RuntimeError(
            "strict c18 randomized-case identity mismatch across replicates; "
            f"env_ids={differing}"
        )


def _optional_metric_values(records: Sequence[Mapping[str, Any]], key: str) -> list[float]:
    values = []
    for record in records:
        diagnostic = record.get("terminal_diagnostic")
        if not isinstance(diagnostic, Mapping) or key not in diagnostic:
            continue
        value = _finite_float(diagnostic[key])
        if value is not None:
            values.append(value)
    return values


def aggregate_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("cannot aggregate an empty formal record set")
    rewards = [_finite_float(record.get("reward")) for record in records]
    rewards = [value for value in rewards if value is not None]
    max_stages = [int(record["max_stage"]) for record in records]
    aggregate: dict[str, Any] = {
        "episodes": len(records),
        "goal_count": sum(bool(record.get("goal_reached")) for record in records),
        "stage0_count": sum(stage == 0 for stage in max_stages),
        "mean_max_stage": sum(max_stages) / len(max_stages),
        "mean_reward": sum(rewards) / len(rewards) if rewards else None,
    }
    optional = {
        "doorframe_contact_force": "doorframe_contact_force",
        "root_yaw": "root_yaw",
    }
    for output_name, source_name in optional.items():
        values = _optional_metric_values(records, source_name)
        if values:
            aggregate[f"mean_{output_name}"] = sum(values) / len(values)
            aggregate[f"{output_name}_samples"] = len(values)
    lateral_values: list[float] = []
    for record in records:
        diagnostic = record.get("terminal_diagnostic")
        if not isinstance(diagnostic, Mapping):
            continue
        candidate = diagnostic.get("root_lateral", diagnostic.get("root_y"))
        if candidate is None:
            relative = diagnostic.get("root_pos_rel")
            if isinstance(relative, Sequence) and not isinstance(relative, (str, bytes)) and len(relative) > 1:
                candidate = relative[1]
        value = _finite_float(candidate)
        if value is not None:
            lateral_values.append(value)
    if lateral_values:
        aggregate["mean_root_lateral"] = sum(lateral_values) / len(lateral_values)
        aggregate["root_lateral_samples"] = len(lateral_values)
    return aggregate


def classify_n1(goal_count: int, stage0_count: int) -> str:
    if goal_count >= N1_GOAL_PASS and stage0_count <= N1_STAGE0_PASS_MAX:
        return "PASS"
    if goal_count < N1_GOAL_INCONCLUSIVE or stage0_count >= N1_STAGE0_BLOCKER_MIN:
        return "BLOCKER"
    return "INCONCLUSIVE"


def rank_n2_checkpoints(
    summaries: Mapping[int, Mapping[str, Any]] | Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(summaries, Mapping):
        normalized = [dict(value, step=int(step)) for step, value in summaries.items()]
    else:
        normalized = [dict(value) for value in summaries]
    if {int(item.get("step", -1)) for item in normalized} != set(REQUIRED_STUDENT_STEPS):
        raise MissingEvidenceError("MISSING_EVIDENCE: N2 ranking requires all five checkpoint steps")
    ranked = sorted(
        normalized,
        key=lambda item: (
            -float(item["mean_max_stage"]),
            int(item["stage0_count"]),
            -int(item["goal_count"]),
            -float(item["mean_reward"] if item.get("mean_reward") is not None else float("-inf")),
            int(item["step"]),
        ),
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked


def h2_verdict(summaries: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    ranked = rank_n2_checkpoints(summaries)
    by_step = {int(item["step"]): item for item in ranked}
    best_step = int(ranked[0]["step"])
    delta_5000_to_10000 = float(by_step[10000]["mean_max_stage"]) - float(by_step[5000]["mean_max_stage"])
    stage0_reduction = int(by_step[5000]["stage0_count"]) - int(by_step[10000]["stage0_count"])
    delta_7500_to_10000 = float(by_step[10000]["mean_max_stage"]) - float(by_step[7500]["mean_max_stage"])
    if best_step == 10000 and delta_5000_to_10000 >= 0.20 and stage0_reduction >= 3:
        verdict = "SUPPORT_H2"
    elif best_step in {5000, 7500} or delta_7500_to_10000 <= 0.0:
        verdict = "DENY_H2"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "verdict": verdict,
        "best_step": best_step,
        "delta_5000_to_10000_mean_stage": delta_5000_to_10000,
        "stage0_reduction_5000_to_10000": stage0_reduction,
        "delta_7500_to_10000_mean_stage": delta_7500_to_10000,
    }


def three_checkpoint_early_stop(summaries: Sequence[Mapping[str, Any]]) -> bool:
    """Return the Pro early-stop signal without changing the required set."""
    if len(summaries) < 3:
        return False
    window = list(summaries[-3:])
    for previous, current in zip(window, window[1:]):
        if abs(float(current["mean_max_stage"]) - float(previous["mean_max_stage"])) >= 0.10:
            return False
        if int(current["stage0_count"]) != int(previous["stage0_count"]):
            return False
    return True


def _artifact_hash_manifest(root: Path) -> list[dict[str, Any]]:
    artifacts = []
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest = eval_v19.sha256_file(path)
        artifacts.append(
            {
                "path": str(path.relative_to(root)),
                "size_bytes": path.stat().st_size,
                "sha256": digest,
            }
        )
    return artifacts


def _write_phase_manifest(output_root: Path, manifest: Mapping[str, Any]) -> Path:
    output_root = output_root.expanduser().resolve()
    path = output_root / "phase_a_manifest.json"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite Phase-A manifest: {path}")
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.writing")
    if temporary.exists():
        raise FileExistsError(f"temporary Phase-A manifest already exists: {temporary}")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(_safe_json(manifest), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return path


def _print_plan(plans: Sequence[PlannedRun], execute: bool) -> None:
    print(f"[A2_PRO_PHASE_A_{'EXECUTE' if execute else 'DRY_RUN'}] runs={len(plans)}", flush=True)
    for plan in plans:
        print(
            f"[A2_PRO_COMMAND] {plan.replicate_id} output={plan.output_root} "
            f"env={{CUDA_VISIBLE_DEVICES=7,A2_EXPECTED_GPU_UUID={eval_v19.EXPECTED_GPU_UUID},"
            "A2_EXPECTED_LOGICAL_GPU_INDEX=0,A2_EXPECTED_WORLD_SIZE=1}}",
            flush=True,
        )
        print(shlex.join(plan.command), flush=True)


def validate_planned_run_inputs(plan: PlannedRun) -> None:
    """Revalidate all checkpoint/config/experience identities before launch."""
    if plan.operation == "n5" and plan.student_d435i_forward_mode != N5_FORMAL_MODE:
        raise RuntimeError("N5 planned run must carry the explicit packed Student mode")
    if plan.operation == "n5":
        if plan.n5_manifest_path is None or plan.n5_manifest_sha256 is None:
            raise RuntimeError("N5 planned run is missing the sealed N5 manifest identity")
        validate_n5_manifest_identity(
            plan.n5_manifest_path,
            plan.n5_manifest_sha256,
            {
                "path": str(plan.checkpoint),
                "sha256": plan.checkpoint_sha256,
                "config_path": str(plan.config_path),
                "config_sha256": plan.config_sha256,
                "global_step": plan.expected_global_step,
                "controller": plan.controller,
            },
        )
    if plan.operation != "n5" and plan.student_d435i_forward_mode is not None:
        raise RuntimeError("non-N5 planned run must not carry an explicit packed Student mode")
    current_config = plan.config_path.expanduser().resolve(strict=True)
    if current_config != plan.config_path:
        raise RuntimeError(
            f"planned checkpoint config path drifted: expected={plan.config_path} got={current_config}"
        )
    current_config_sha = eval_v19.sha256_file(current_config)
    if current_config_sha != plan.config_sha256:
        raise RuntimeError(
            "planned checkpoint config SHA256 drifted before subprocess launch: "
            f"expected={plan.config_sha256} got={current_config_sha}"
        )
    checkpoint_info = eval_v19.validate_checkpoint_artifacts(
        plan.checkpoint,
        plan.config_path,
        controller=plan.controller,
        expected_global_step=plan.expected_global_step,
        expected_sha256=plan.checkpoint_sha256,
        expected_config_sha256=plan.config_sha256,
    )
    if checkpoint_info["config_path"] != str(plan.config_path) or checkpoint_info["config_sha256"] != plan.config_sha256:
        raise RuntimeError("planned checkpoint config identity changed before subprocess launch")
    experience_info = eval_v19.validate_experience_identity(
        {
            "controller": plan.controller,
            "camera_mode": plan.experience_camera_mode,
            "path": str(plan.experience_path),
            "sha256": plan.experience_sha256,
        },
        plan.overlay_repository,
        plan.controller,
    )
    if experience_info["path"] != str(plan.experience_path):
        raise RuntimeError("planned experience path identity changed before subprocess launch")
    if plan.operation == "n3":
        if plan.controller != eval_v19.N3_PASSIVE_CONTROLLER or plan.capture_controller != "teacher":
            raise RuntimeError("N3 planned run controller topology drifted")
        teacher_info = eval_v19.validate_teacher_identity()
        expected_teacher = {
            "teacher_checkpoint": str(teacher_info["checkpoint"]["path"]),
            "teacher_checkpoint_sha256": teacher_info["checkpoint"]["sha256"],
            "teacher_config_path": str(teacher_info["checkpoint"]["config_path"]),
            "teacher_config_sha256": teacher_info["checkpoint"]["config_sha256"],
            "teacher_manifest_path": str(teacher_info["manifest"]["path"]),
            "teacher_manifest_sha256": teacher_info["manifest"]["sha256"],
        }
        actual_teacher = {
            "teacher_checkpoint": None if plan.teacher_checkpoint is None else str(plan.teacher_checkpoint),
            "teacher_checkpoint_sha256": plan.teacher_checkpoint_sha256,
            "teacher_config_path": None if plan.teacher_config_path is None else str(plan.teacher_config_path),
            "teacher_config_sha256": plan.teacher_config_sha256,
            "teacher_manifest_path": None if plan.teacher_manifest_path is None else str(plan.teacher_manifest_path),
            "teacher_manifest_sha256": plan.teacher_manifest_sha256,
        }
        if actual_teacher != expected_teacher:
            raise RuntimeError(
                "N3 planned Teacher identity drifted: "
                f"expected={expected_teacher!r} got={actual_teacher!r}"
            )
        eval_v19.validate_n3_teacher_config(plan.config_path, teacher_info)


def validate_plan_artifact_identity(
    plan: PlannedRun, selection: Mapping[str, Any], metrics: Mapping[str, Any]
) -> None:
    """Require formal artifacts to preserve planned checkpoint/config/experience identity."""
    expected = {
        "path": str(plan.checkpoint),
        "sha256": plan.checkpoint_sha256,
        "config_path": str(plan.config_path),
        "config_sha256": plan.config_sha256,
        "global_step": plan.expected_global_step,
        "controller": plan.controller,
    }
    for artifact_name, artifact in (("selection", selection), ("metrics", metrics)):
        identity = artifact.get("checkpoint")
        if not isinstance(identity, Mapping):
            raise RuntimeError(f"formal {artifact_name} is missing checkpoint identity")
        for key, expected_value in expected.items():
            if identity.get(key) != expected_value:
                raise RuntimeError(
                    f"formal {artifact_name} checkpoint identity drift for {key}: "
                    f"expected={expected_value!r} got={identity.get(key)!r}"
                )
        if plan.student_d435i_forward_mode is not None:
            contract = artifact.get("contract")
            if not isinstance(contract, Mapping):
                raise RuntimeError(f"formal {artifact_name} is missing the forward-mode contract")
            if contract.get("student_d435i_forward_mode") != plan.student_d435i_forward_mode:
                raise RuntimeError(
                    f"formal {artifact_name} D435 forward-mode drift: "
                    f"expected={plan.student_d435i_forward_mode!r} "
                    f"got={contract.get('student_d435i_forward_mode')!r}"
                )
        experience = artifact.get("experience")
        if not isinstance(experience, Mapping):
            raise RuntimeError(f"formal {artifact_name} is missing experience identity")
        expected_experience = {
            "controller": plan.controller,
            "camera_mode": plan.experience_camera_mode,
            "path": str(plan.experience_path),
            "sha256": plan.experience_sha256,
        }
        for key, expected_value in expected_experience.items():
            if experience.get(key) != expected_value:
                raise RuntimeError(
                    f"formal {artifact_name} experience identity drift for {key}: "
                    f"expected={expected_value!r} got={experience.get(key)!r}"
                )


def validate_n3_plan_artifact_identity(
    plan: PlannedRun, manifest: Mapping[str, Any], metrics: Mapping[str, Any]
) -> None:
    """Require a sealed N3 bundle to preserve passive/Teacher/source identity."""
    if plan.operation != "n3":
        raise ValueError("N3 artifact validation received a non-N3 plan")
    if manifest.get("schema") != eval_v19.N3_MANIFEST_SCHEMA:
        raise RuntimeError("N3 manifest schema drifted")
    if manifest.get("controller") != "teacher" or manifest.get("replicate_id") != plan.replicate_id:
        raise RuntimeError("N3 manifest controller or replicate identity drifted")
    passive = manifest.get("passive_student")
    if not isinstance(passive, Mapping):
        raise RuntimeError("N3 manifest is missing passive Student identity")
    expected_passive = {
        "path": str(plan.checkpoint),
        "sha256": plan.checkpoint_sha256,
        "config_path": str(plan.config_path),
        "config_sha256": plan.config_sha256,
        "global_step": plan.expected_global_step,
        "controller": "student",
    }
    for key, expected in expected_passive.items():
        if passive.get(key) != expected:
            raise RuntimeError(
                f"N3 passive Student identity drift for {key}: expected={expected!r} "
                f"got={passive.get(key)!r}"
            )
    control = manifest.get("control_identity")
    if not isinstance(control, Mapping):
        raise RuntimeError("N3 manifest is missing Teacher control identity")
    expected_control = {
        "controller": "teacher",
        "high_level_action_dim": 12,
        "high_level_action_source": "Teacher12D",
        "teacher_rollout_enforced": True,
        "teacher_rollout_ratio": 1.0,
        "policy_quality_evidence": False,
    }
    for key, expected in expected_control.items():
        if control.get(key) != expected:
            raise RuntimeError(
                f"N3 control identity drift for {key}: expected={expected!r} got={control.get(key)!r}"
            )
    experience = manifest.get("experience")
    expected_experience = {
        "controller": plan.controller,
        "camera_mode": plan.experience_camera_mode,
        "path": str(plan.experience_path),
        "sha256": plan.experience_sha256,
    }
    if not isinstance(experience, Mapping):
        raise RuntimeError("N3 manifest is missing experience identity")
    for key, expected in expected_experience.items():
        if experience.get(key) != expected:
            raise RuntimeError(
                f"N3 experience identity drift for {key}: expected={expected!r} got={experience.get(key)!r}"
            )
    teacher = manifest.get("teacher")
    if not isinstance(teacher, Mapping) or not isinstance(teacher.get("checkpoint"), Mapping):
        raise RuntimeError("N3 manifest is missing Teacher checkpoint identity")
    teacher_checkpoint = teacher["checkpoint"]
    expected_teacher = {
        "path": str(plan.teacher_checkpoint),
        "sha256": plan.teacher_checkpoint_sha256,
        "config_path": str(plan.teacher_config_path),
        "config_sha256": plan.teacher_config_sha256,
        "global_step": eval_v19.TEACHER_GLOBAL_STEP,
        "controller": "teacher",
    }
    for key, expected in expected_teacher.items():
        if teacher_checkpoint.get(key) != expected:
            raise RuntimeError(
                f"N3 Teacher checkpoint identity drift for {key}: expected={expected!r} "
                f"got={teacher_checkpoint.get(key)!r}"
            )
    if teacher.get("manifest", {}).get("path") != str(plan.teacher_manifest_path):
        raise RuntimeError("N3 Teacher manifest path identity drift")
    if teacher.get("manifest", {}).get("sha256") != plan.teacher_manifest_sha256:
        raise RuntimeError("N3 Teacher manifest SHA256 identity drift")
    dataset = manifest.get("dataset")
    if not isinstance(dataset, Mapping) or int(dataset.get("episode_count", -1)) != eval_v19.EXPECTED_EPISODES:
        raise RuntimeError("N3 dataset must contain exactly 16 completed first episodes")
    if metrics.get("controller") != "teacher" or int(metrics.get("training_performed", 1)) != 0:
        raise RuntimeError("N3 metrics must be Teacher-controlled and training-free")
    if len(metrics.get("episodes", [])) != eval_v19.EXPECTED_EPISODES:
        raise RuntimeError("N3 metrics must contain exactly 16 episode records")


def _execute_plan(plan: PlannedRun) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_planned_run_inputs(plan)
    result = subprocess.run(
        list(plan.command),
        cwd=str(REPO_ROOT),
        env=dict(plan.environment),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{plan.operation} subprocess failed ({plan.replicate_id}) with exit={result.returncode}")
    if plan.operation == "n3":
        manifest, metrics = eval_v19.load_n3_capture_bundle(plan.output_root)
        validate_n3_plan_artifact_identity(plan, manifest, metrics)
        return manifest, metrics
    selection, metrics = load_formal_run(plan.output_root, plan.controller)
    validate_plan_artifact_identity(plan, selection, metrics)
    return selection, metrics


def execute_n1(plans: Sequence[PlannedRun], output_root: Path) -> dict[str, Any]:
    claim_phase_output_root(output_root)
    reference_map = None
    all_records = []
    run_summaries = []
    for plan in plans:
        selection, metrics = _execute_plan(plan)
        current_map = case_identity_map(metrics)
        if reference_map is None:
            reference_map = current_map
        else:
            assert_case_maps_equal(reference_map, current_map)
        all_records.extend(metrics["episodes"])
        run_summaries.append(
            {
                "replicate_id": plan.replicate_id,
                "selection": selection,
                "aggregate": aggregate_records(metrics["episodes"]),
            }
        )
    aggregate = aggregate_records(all_records)
    classification = classify_n1(aggregate["goal_count"], aggregate["stage0_count"])
    manifest = {
        "schema": PHASE_A_SCHEMA,
        "operation": "n1",
        "controller": "teacher",
        "case_seed": 0,
        "replicate_count": len(plans),
        "case_identity_mapping_equal": True,
        "classification": classification,
        "aggregate": aggregate,
        "replicates": run_summaries,
        "artifacts": _artifact_hash_manifest(output_root),
    }
    path = _write_phase_manifest(output_root, manifest)
    manifest["manifest_path"] = str(path)
    return manifest


def execute_n2(
    first_pass_plans: Sequence[PlannedRun],
    checkpoint_info: Mapping[int, Mapping[str, Any]],
    output_root: Path,
    *,
    overlay_repository: Path,
    runtime_repository: Path,
    python_executable: str,
) -> dict[str, Any]:
    claim_phase_output_root(output_root)
    reference_map = None
    first_pass: dict[int, dict[str, Any]] = {}
    first_records: dict[int, list[Mapping[str, Any]]] = {}
    for plan in first_pass_plans:
        selection, metrics = _execute_plan(plan)
        current_map = case_identity_map(metrics)
        if reference_map is None:
            reference_map = current_map
        else:
            assert_case_maps_equal(reference_map, current_map)
        step = plan.expected_global_step
        first_records[step] = list(metrics["episodes"])
        first_pass[step] = {
            "step": step,
            "replicate_id": plan.replicate_id,
            **aggregate_records(metrics["episodes"]),
            "selection": selection,
        }
    ranked = rank_n2_checkpoints(first_pass)
    top2_steps = [int(item["step"]) for item in ranked[:2]]
    extra_records: dict[int, list[Mapping[str, Any]]] = {step: [] for step in top2_steps}
    extra_plans: list[PlannedRun] = []
    for step in top2_steps:
        for replicate_index in range(2, N2_EXTRA_REPLICATE_COUNT + 2):
            root = output_root.expanduser().resolve() / "n2_student" / f"step_{step:05d}" / f"replicate_{replicate_index:02d}"
            extra_plans.append(
                _planned_run(
                    operation="n2",
                    controller="student",
                    checkpoint_info=checkpoint_info[step],
                    replicate_id=f"n2_rep{replicate_index:02d}",
                    output_root=root,
                    overlay_repository=overlay_repository,
                    runtime_repository=runtime_repository,
                    python_executable=python_executable,
                )
            )
    _output_roots_are_unique_and_absent([plan.output_root for plan in extra_plans])
    for plan in extra_plans:
        selection, metrics = _execute_plan(plan)
        current_map = case_identity_map(metrics)
        assert reference_map is not None
        assert_case_maps_equal(reference_map, current_map)
        extra_records[plan.expected_global_step].extend(metrics["episodes"])
    combined = {}
    for step in REQUIRED_STUDENT_STEPS:
        records = first_records[step] + extra_records.get(step, [])
        combined[step] = {"step": step, **aggregate_records(records)}
    combined_ranked = rank_n2_checkpoints(combined)
    h2 = h2_verdict(first_pass)
    ordered_first = [first_pass[step] for step in REQUIRED_STUDENT_STEPS]
    manifest = {
        "schema": PHASE_A_SCHEMA,
        "operation": "n2",
        "controller": "student",
        "case_seed": 0,
        "required_steps": list(REQUIRED_STUDENT_STEPS),
        "missing_required_steps": [],
        "case_identity_mapping_equal": True,
        "first_pass_ranked": ranked,
        "top2_steps": top2_steps,
        "extra_replicates": [plan.replicate_id for plan in extra_plans],
        "combined_ranked": combined_ranked,
        "h2": h2,
        "three_checkpoint_early_stop": three_checkpoint_early_stop(ordered_first),
        "artifacts": _artifact_hash_manifest(output_root),
    }
    path = _write_phase_manifest(output_root, manifest)
    manifest["manifest_path"] = str(path)
    return manifest


def execute_n3(plans: Sequence[PlannedRun], output_root: Path) -> dict[str, Any]:
    """Execute exactly three sequential N3 captures and seal a 48-episode phase."""
    if len(plans) != N3_REPLICATE_COUNT:
        raise ValueError(
            f"N3 requires exactly {N3_REPLICATE_COUNT} plans; got {len(plans)}"
        )
    if any(plan.operation != "n3" for plan in plans):
        raise ValueError("N3 execution received a non-N3 plan")
    claim_phase_output_root(output_root)
    reference_map = None
    reference_manifest = None
    all_records: list[Mapping[str, Any]] = []
    replicate_summaries = []
    for plan in plans:
        manifest, metrics = _execute_plan(plan)
        current_map = case_identity_map(metrics)
        if reference_map is None:
            reference_map = current_map
            reference_manifest = manifest
        else:
            assert_case_maps_equal(reference_map, current_map)
            for key in ("passive_student", "teacher", "experience", "runtime", "case_table"):
                if manifest.get(key) != reference_manifest.get(key):
                    raise RuntimeError(f"N3 replicate provenance drift for {key}")
        records = metrics.get("episodes")
        if not isinstance(records, list) or len(records) != eval_v19.EXPECTED_EPISODES:
            raise RuntimeError("N3 replicate must contain exactly 16 episode records")
        all_records.extend(records)
        replicate_summaries.append(
            {
                "replicate_id": plan.replicate_id,
                "output_root": str(plan.output_root),
                "dataset": manifest.get("dataset"),
                "aggregate": aggregate_records(records),
            }
        )
    if len(all_records) != N3_REPLICATE_COUNT * eval_v19.EXPECTED_EPISODES:
        raise RuntimeError("N3 phase must seal exactly 48 episodes across three replicates")
    if reference_manifest is None:
        raise RuntimeError("N3 phase produced no reference manifest")
    phase_manifest = {
        "schema": PHASE_A_SCHEMA,
        "operation": "n3",
        "controller": "teacher",
        "passive_controller": "student",
        "case_seed": eval_v19.EXPECTED_SEED,
        "replicate_count": N3_REPLICATE_COUNT,
        "episode_count": len(all_records),
        "case_identity_mapping_equal": True,
        "passive_student": reference_manifest.get("passive_student"),
        "teacher": reference_manifest.get("teacher"),
        "experience": reference_manifest.get("experience"),
        "runtime": reference_manifest.get("runtime"),
        "control_identity": reference_manifest.get("control_identity"),
        "replicates": replicate_summaries,
        "artifacts": _artifact_hash_manifest(output_root),
    }
    path = _write_phase_manifest(output_root, phase_manifest)
    phase_manifest["manifest_path"] = str(path)
    return phase_manifest


def load_n2_step10000_baseline(
    phase_manifest: Path | os.PathLike[str],
    manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the sealed N2 combined three-replicate step10000 baseline."""
    if isinstance(phase_manifest, (str, bytes, Mapping)) or not isinstance(
        phase_manifest, os.PathLike
    ):
        raise TypeError("N2 baseline manifest must be a filesystem Path/os.PathLike, not a mapping or string")
    manifest_path = Path(phase_manifest).expanduser().resolve(strict=True)
    expected_manifest_sha256 = _require_sha256(
        manifest_sha256, "N2 baseline manifest SHA256"
    )
    actual_manifest_sha256 = eval_v19.sha256_file(manifest_path)
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise RuntimeError(
            "N2 baseline manifest SHA256 mismatch: "
            f"expected={expected_manifest_sha256} got={actual_manifest_sha256}"
        )
    if actual_manifest_sha256 != EXPECTED_N2_PHASE_MANIFEST_SHA256:
        raise RuntimeError(
            "N2 baseline manifest is not the pinned sealed Phase-A manifest: "
            f"expected={EXPECTED_N2_PHASE_MANIFEST_SHA256} got={actual_manifest_sha256}"
        )
    manifest = _load_json(manifest_path)
    if manifest.get("schema") != PHASE_A_SCHEMA or manifest.get("operation") != "n2":
        raise RuntimeError("N5 baseline must be a sealed N2 Phase-A manifest")
    if manifest.get("controller") != "student":
        raise RuntimeError("N5 baseline N2 manifest must identify the Student controller")
    if manifest.get("case_identity_mapping_equal") is not True:
        raise RuntimeError("N5 baseline N2 manifest does not prove equal case identity mapping")
    if manifest.get("required_steps") != list(REQUIRED_STUDENT_STEPS):
        raise MissingEvidenceError("N5 baseline N2 manifest does not contain all required steps")
    if manifest.get("missing_required_steps"):
        raise MissingEvidenceError("N5 baseline N2 manifest reports missing required steps")
    if eval_v19.STUDENT_GLOBAL_STEP not in [int(step) for step in manifest.get("top2_steps", [])]:
        raise RuntimeError("N5 baseline N2 manifest does not include step10000 in the formal top2")
    combined = manifest.get("combined_ranked")
    if not isinstance(combined, list):
        raise RuntimeError("N5 baseline N2 manifest is missing combined_ranked evidence")
    matches = [
        item for item in combined
        if isinstance(item, Mapping) and int(item.get("step", -1)) == eval_v19.STUDENT_GLOBAL_STEP
    ]
    if len(matches) != 1:
        raise RuntimeError("N5 baseline N2 manifest must contain exactly one combined step10000 summary")
    combined_summary = dict(matches[0])
    expected_episodes = (N2_EXTRA_REPLICATE_COUNT + 1) * eval_v19.EXPECTED_EPISODES
    if int(combined_summary.get("episodes", -1)) != expected_episodes:
        raise RuntimeError(
            "N5 baseline step10000 must contain three 16-env formal replicates: "
            f"got {combined_summary.get('episodes')!r}"
        )
    phase_root = manifest_path.parent.resolve()
    expected_checkpoint_identity = {
        "path": str(n5_runner.CHECKPOINT),
        "sha256": n5_runner.CHECKPOINT_SHA256,
        "config_path": str(n5_runner.CHECKPOINT_CONFIG),
        "config_sha256": n5_runner.CHECKPOINT_CONFIG_SHA256,
        "global_step": eval_v19.STUDENT_GLOBAL_STEP,
        "controller": "student",
    }
    expected_experience_identity = eval_v19.resolve_experience_source(
        eval_v19.REPO_ROOT, "student"
    )
    required_paths = tuple(
        f"n2_student/step_10000/replicate_{index:02d}/formal_student_metrics.json"
        for index in range(1, N3_REPLICATE_COUNT + 1)
    )
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("N2 baseline manifest artifacts must be a list")
    reference_map = None
    all_records: list[Mapping[str, Any]] = []
    artifacts_identity = []
    for relative_name in required_paths:
        matches = [
            artifact
            for artifact in artifacts
            if isinstance(artifact, Mapping) and artifact.get("path") == relative_name
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "N2 baseline requires exactly one declared formal metrics artifact for "
                f"{relative_name}; found {len(matches)}"
            )
        artifact = matches[0]
        relative_path = Path(relative_name)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise RuntimeError(f"N2 baseline artifact path escapes phase root: {relative_name}")
        metrics_path = (phase_root / relative_path).resolve()
        try:
            metrics_path.relative_to(phase_root)
        except ValueError as exc:
            raise RuntimeError(f"N2 baseline artifact path escapes phase root: {relative_name}") from exc
        if not metrics_path.is_file():
            raise FileNotFoundError(f"N2 baseline formal metrics artifact is missing: {metrics_path}")
        declared_size = artifact.get("size_bytes")
        if isinstance(declared_size, bool) or not isinstance(declared_size, int) or declared_size < 0:
            raise RuntimeError(f"N2 baseline artifact size is invalid: {relative_name}")
        actual_size = metrics_path.stat().st_size
        if actual_size != declared_size:
            raise RuntimeError(
                f"N2 baseline artifact size mismatch for {relative_name}: "
                f"expected={declared_size} got={actual_size}"
            )
        declared_sha = _require_sha256(artifact.get("sha256"), f"N2 artifact {relative_name} SHA256")
        actual_sha = eval_v19.sha256_file(metrics_path)
        if actual_sha != declared_sha:
            raise RuntimeError(f"N2 baseline artifact SHA256 mismatch for {relative_name}")
        metrics = _load_json(metrics_path)
        if metrics.get("schema") != eval_v19.STUDENT_METRICS_SCHEMA or metrics.get("controller") != "student":
            raise RuntimeError(f"N2 baseline metrics contract drifted for {relative_name}")
        _exact_identity_fields(
            metrics.get("checkpoint"),
            expected_checkpoint_identity,
            f"N2 checkpoint {relative_name}",
        )
        if metrics.get("experience") != expected_experience_identity:
            raise RuntimeError(f"N2 experience identity drifted for {relative_name}")
        contract = metrics.get("contract")
        if not isinstance(contract, Mapping):
            raise RuntimeError(f"N2 formal contract is missing for {relative_name}")
        _exact_identity_fields(
            contract.get("checkpoint_identity"),
            expected_checkpoint_identity,
            f"N2 contract checkpoint {relative_name}",
        )
        if contract.get("experience_identity") != expected_experience_identity:
            raise RuntimeError(f"N2 contract experience identity drifted for {relative_name}")
        if contract.get("student_d435i_forward_mode", "sequential") != "sequential":
            raise RuntimeError(f"N2 baseline formal metrics are not sequential for {relative_name}")
        records = metrics.get("episodes")
        if not isinstance(records, list) or len(records) != eval_v19.EXPECTED_EPISODES:
            raise RuntimeError(
                f"N2 baseline formal metrics must contain exactly 16 records for {relative_name}"
            )
        current_map = case_identity_map(metrics)
        if reference_map is None:
            reference_map = current_map
        else:
            assert_case_maps_equal(reference_map, current_map)
        all_records.extend(records)
        artifacts_identity.append(
            {"path": relative_name, "size_bytes": actual_size, "sha256": actual_sha}
        )
    if reference_map is None:
        raise RuntimeError("N2 baseline produced no case identity mapping")
    recomputed_baseline = aggregate_records(all_records)
    declared_baseline = {
        key: value
        for key, value in combined_summary.items()
        if key not in {"step", "rank"}
    }
    if canonical_json(recomputed_baseline) != canonical_json(declared_baseline):
        raise RuntimeError(
            "N2 baseline combined step10000 aggregate summary drifted from metrics artifacts"
        )
    baseline = recomputed_baseline
    identity = {
        "path": str(manifest_path),
        "sha256": actual_manifest_sha256,
        "case_identity_map": reference_map,
        "case_identity_map_sha256": case_identity_map_sha256(reference_map),
        "case_artifacts": artifacts_identity,
    }
    return baseline, identity


def classify_n5(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    replicate_count: int = N5_REPLICATE_COUNT,
) -> dict[str, Any]:
    """Classify aggregate stage evidence without claiming policy-quality proof."""
    if replicate_count <= 0:
        raise ValueError("N5 replicate_count must be positive")
    baseline_stage0 = int(baseline.get("stage0_count", -1))
    candidate_stage0 = int(candidate.get("stage0_count", -1))
    baseline_mean_stage = float(baseline.get("mean_max_stage"))
    candidate_mean_stage = float(candidate.get("mean_max_stage"))
    baseline_episodes = int(baseline.get("episodes", -1))
    candidate_episodes = int(candidate.get("episodes", -1))
    if baseline_episodes != candidate_episodes or baseline_episodes <= 0:
        raise RuntimeError(
            "N5 baseline/candidate episode counts must match and be positive: "
            f"baseline={baseline_episodes} candidate={candidate_episodes}"
        )
    stage0_reduction = baseline_stage0 - candidate_stage0
    mean_stage_delta = candidate_mean_stage - baseline_mean_stage
    stage0_reduction_per_replicate = stage0_reduction / float(replicate_count)
    stage0_rate_reduction = (
        baseline_stage0 / float(baseline_episodes)
        - candidate_stage0 / float(candidate_episodes)
    )
    strong_stage0_reduction = stage0_reduction >= 5
    mean_stage_support = mean_stage_delta >= 0.20
    per_replicate_stage0_support = stage0_rate_reduction >= (2.0 / 16.0)
    if strong_stage0_reduction:
        verdict = "SUPPORT_N5_STRONG_STAGE0"
    elif mean_stage_support or per_replicate_stage0_support:
        verdict = "SUPPORT_N5"
    else:
        verdict = "NO_FORMAL_SUPPORT"
    return {
        "verdict": verdict,
        "formal_support": verdict != "NO_FORMAL_SUPPORT",
        "policy_quality_evidence": False,
        "baseline_stage0_count": baseline_stage0,
        "candidate_stage0_count": candidate_stage0,
        "stage0_reduction": stage0_reduction,
        "stage0_reduction_per_replicate": stage0_reduction_per_replicate,
        "stage0_rate_reduction": stage0_rate_reduction,
        "baseline_mean_max_stage": baseline_mean_stage,
        "candidate_mean_max_stage": candidate_mean_stage,
        "mean_max_stage_delta": mean_stage_delta,
        "thresholds": {
            "strong_stage0_reduction_total": 5,
            "mean_max_stage_delta": 0.20,
            "stage0_rate_reduction": 2.0 / 16.0,
        },
    }


def execute_n5(
    plans: Sequence[PlannedRun],
    n2_baseline_manifest: Path | os.PathLike[str],
    output_root: Path,
    n2_baseline_manifest_sha256: str,
) -> dict[str, Any]:
    """Execute three packed formal runs and seal comparison to N2 step10000."""
    if len(plans) != N5_REPLICATE_COUNT:
        raise ValueError(f"N5 requires exactly {N5_REPLICATE_COUNT} plans; got {len(plans)}")
    if any(plan.operation != "n5" or plan.controller != "student" for plan in plans):
        raise ValueError("N5 execution requires packed Student plans")
    if any(plan.student_d435i_forward_mode != N5_FORMAL_MODE for plan in plans):
        raise ValueError("N5 execution requires explicit packed forward-mode plans")
    baseline, baseline_identity = load_n2_step10000_baseline(
        n2_baseline_manifest,
        n2_baseline_manifest_sha256,
    )
    claim_phase_output_root(output_root)
    reference_map = baseline_identity.get("case_identity_map")
    if not isinstance(reference_map, Mapping):
        raise RuntimeError("N2 baseline did not provide a sealed case identity mapping")
    all_records: list[Mapping[str, Any]] = []
    replicate_summaries: list[dict[str, Any]] = []
    for plan in plans:
        selection, metrics = _execute_plan(plan)
        current_map = case_identity_map(metrics)
        assert_case_maps_equal(reference_map, current_map)
        records = metrics.get("episodes")
        if not isinstance(records, list) or len(records) != eval_v19.EXPECTED_EPISODES:
            raise RuntimeError("N5 formal replicate must contain exactly 16 episodes")
        all_records.extend(records)
        replicate_summaries.append(
            {
                "replicate_id": plan.replicate_id,
                "output_root": str(plan.output_root),
                "student_d435i_forward_mode": plan.student_d435i_forward_mode,
                "aggregate": aggregate_records(records),
            }
        )
    if len(all_records) != N5_REPLICATE_COUNT * eval_v19.EXPECTED_EPISODES:
        raise RuntimeError("N5 phase must seal exactly 48 episodes across three replicates")
    candidate = aggregate_records(all_records)
    classification = classify_n5(baseline, candidate)
    manifest_paths = {(str(plan.n5_manifest_path), plan.n5_manifest_sha256) for plan in plans}
    if len(manifest_paths) != 1:
        raise RuntimeError("N5 replicates do not share one sealed N5 manifest identity")
    n5_manifest_path, n5_manifest_sha256 = next(iter(manifest_paths))
    if n5_manifest_path is None or n5_manifest_sha256 is None:
        raise RuntimeError("N5 replicates are missing the sealed recalibration manifest identity")
    n5_identity = validate_n5_manifest_identity(
        Path(n5_manifest_path),
        n5_manifest_sha256,
        {
            "path": str(plans[0].checkpoint),
            "sha256": plans[0].checkpoint_sha256,
            "config_path": str(plans[0].config_path),
            "config_sha256": plans[0].config_sha256,
            "global_step": plans[0].expected_global_step,
            "controller": plans[0].controller,
        },
    )
    manifest: dict[str, Any] = {
        "schema": PHASE_A_SCHEMA,
        "operation": "n5",
        "controller": "student",
        "student_d435i_forward_mode": N5_FORMAL_MODE,
        "case_seed": eval_v19.EXPECTED_SEED,
        "replicate_count": N5_REPLICATE_COUNT,
        "episode_count": len(all_records),
        "case_identity_mapping_equal": True,
        "policy_quality_evidence": False,
        "action_open_loop_evidence_only": True,
        "n5_manifest": {
            "path": n5_manifest_path,
            "sha256": n5_manifest_sha256,
        },
        "gpu_identity": dict(n5_identity["gpu_identity"]),
        "n2_baseline": {
            **baseline_identity,
            "step": eval_v19.STUDENT_GLOBAL_STEP,
            "aggregate": baseline,
        },
        "case_identity_map_sha256": baseline_identity["case_identity_map_sha256"],
        "candidate_aggregate": candidate,
        "classification": classification,
        "replicates": replicate_summaries,
        "artifacts": _artifact_hash_manifest(output_root),
    }
    path = _write_phase_manifest(output_root, manifest)
    manifest["manifest_path"] = str(path)
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=("n1", "n2", "n3", "n5"), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--student-checkpoint-dir",
        type=Path,
        default=eval_v19.CHECKPOINT.parent,
    )
    parser.add_argument("--overlay-repository", type=Path, default=REPO_ROOT)
    parser.add_argument("--runtime-repository", type=Path, default=RUNTIME_REPOSITORY)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument(
        "--n5-checkpoint",
        "--recalibrated-checkpoint",
        dest="n5_checkpoint",
        type=Path,
    )
    parser.add_argument(
        "--n5-config",
        "--recalibrated-config",
        dest="n5_config",
        type=Path,
    )
    parser.add_argument("--n5-checkpoint-sha256", "--recalibrated-checkpoint-sha256", dest="n5_checkpoint_sha256")
    parser.add_argument("--n5-config-sha256", "--recalibrated-config-sha256", dest="n5_config_sha256")
    parser.add_argument("--n5-manifest", type=Path)
    parser.add_argument("--n5-manifest-sha256")
    parser.add_argument("--n2-baseline-manifest", type=Path)
    parser.add_argument("--n2-baseline-manifest-sha256")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.execute and args.dry_run:
        parser.error("--execute and --dry-run are mutually exclusive")
    n5_values = (
        args.n5_checkpoint,
        args.n5_config,
        args.n5_checkpoint_sha256,
        args.n5_config_sha256,
        args.n5_manifest,
        args.n5_manifest_sha256,
        args.n2_baseline_manifest,
        args.n2_baseline_manifest_sha256,
    )
    if args.operation == "n5" and not all(value is not None for value in n5_values):
        parser.error(
            "N5 requires --n5-checkpoint/--n5-config plus both SHA256 values and "
            "--n5-manifest/--n5-manifest-sha256 and "
            "--n2-baseline-manifest/--n2-baseline-manifest-sha256"
        )
    if args.operation != "n5" and any(value is not None for value in n5_values):
        parser.error("N5 artifact flags are only valid with --operation n5")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    execute = bool(args.execute and not args.dry_run)
    try:
        if args.operation == "n1":
            plans = build_n1_plan(
                args.output_root,
                overlay_repository=args.overlay_repository,
                runtime_repository=args.runtime_repository,
                python_executable=args.python_executable,
            )
            _print_plan(plans, execute)
            if not execute:
                return 0
            execute_n1(plans, args.output_root)
            return 0
        if args.operation == "n3":
            plans = build_n3_plan(
                args.output_root,
                overlay_repository=args.overlay_repository,
                runtime_repository=args.runtime_repository,
                python_executable=args.python_executable,
            )
            _print_plan(plans, execute)
            if not execute:
                print(
                    "[A2_PRO_N3_DRY_RUN] three sequential Teacher-controlled captures "
                    "are planned; no subprocess, IsaacSim, or training was started.",
                    flush=True,
                )
                return 0
            execute_n3(plans, args.output_root)
            return 0
        if args.operation == "n5":
            n5_checkpoint = args.n5_checkpoint.expanduser().resolve(strict=True)
            n5_config = args.n5_config.expanduser().resolve(strict=True)
            if n5_config != n5_checkpoint.with_name("config.yaml"):
                raise RuntimeError(
                    "N5 recalibrated checkpoint config must be adjacent config.yaml: "
                    f"expected={n5_checkpoint.with_name('config.yaml')} got={n5_config}"
                )
            n5_info = eval_v19.validate_checkpoint_artifacts(
                n5_checkpoint,
                n5_config,
                controller="student",
                expected_global_step=eval_v19.STUDENT_GLOBAL_STEP,
                expected_sha256=args.n5_checkpoint_sha256,
                expected_config_sha256=args.n5_config_sha256,
            )
            plans = build_n5_plan(
                args.output_root,
                n5_info,
                n5_manifest_path=args.n5_manifest,
                n5_manifest_sha256=args.n5_manifest_sha256,
                overlay_repository=args.overlay_repository,
                runtime_repository=args.runtime_repository,
                python_executable=args.python_executable,
            )
            _print_plan(plans, execute)
            if not execute:
                print(
                    "[A2_PRO_N5_DRY_RUN] three fresh packed Student formal commands "
                    "are constructed; no subprocess, IsaacSim, or training was started.",
                    flush=True,
                )
                return 0
            execute_n5(
                plans,
                args.n2_baseline_manifest,
                args.output_root,
                args.n2_baseline_manifest_sha256,
            )
            return 0
        plans, checkpoint_info = build_n2_plan(
            args.output_root,
            args.student_checkpoint_dir,
            overlay_repository=args.overlay_repository,
            runtime_repository=args.runtime_repository,
            python_executable=args.python_executable,
        )
        _print_plan(plans, execute)
        if not execute:
            print(
                "[A2_PRO_N2_DRY_RUN] extra top2 replicate commands are constructed only "
                "after first-pass paired ranking; required checkpoint set is unchanged.",
                flush=True,
            )
            return 0
        execute_n2(
            plans,
            checkpoint_info,
            args.output_root,
            overlay_repository=args.overlay_repository,
            runtime_repository=args.runtime_repository,
            python_executable=args.python_executable,
        )
        return 0
    except MissingEvidenceError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2
    except (FileExistsError, FileNotFoundError, RuntimeError, TypeError, ValueError) as exc:
        print(f"[A2_PRO_PHASE_A_BLOCKER] {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
