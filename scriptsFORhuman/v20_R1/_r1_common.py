"""Shared fail-fast utilities for the independent v20_R1 human scripts."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping


PLAN_ID = "base_v20_R1_policy_behavior_v1"
PLAN_SHA256 = "6827290631feea15497fe76cd64116c30a1343d5bd6c1cb83ba09c35bc247e3c"
CHECKPOINT_SHA256 = "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d"
URDF_BLOB_SHA1 = "95c7698866962fa6e1b971b9ee534452775d8698"
URDF_SHA256 = "d02cdacdcd4aaf1480b52ba9a6a62f5e9bbd040036a796154dbff70d1391a1d5"
LEGAL_GPUS = tuple(range(7))
RESERVED_GPU = 7

# Typed gate labels are intentionally distinct; callers must not collapse these
# into a generic PASS string.
STATIC_PASS = "STATIC PASS"
RUNTIME_SEMANTIC_PASS = "RUNTIME SEMANTIC PASS"
RUNTIME_PASS = "RUNTIME PASS"
POLICY_LEARNABILITY_PASS = "POLICY LEARNABILITY PASS"
POLICY_PASS = "POLICY PASS"
STRICT_VALID = "STRICT_VALID"
STRICT_INVALID = "STRICT_INVALID"
NO_RELEASE = "NO RELEASE"

R1_ARTIFACT_ROOT = "logs_eval/base_v20_R1"
R1_FORMAL_ROOT = "logs_rl/a2_piper_full_stage_a2_base/base_v20_R1"
R1_SMOKE_ROOT = "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R1"
R1_LAUNCHER_ROOT = "logs_rl/launchers/base_v20_R1"
R1_PILOT_MARKER = "logs_eval/base_v20_R1/pilot/PILOT_ATTEMPT_CONSUMED.json"
CALIBRATION_LABEL = "base_v20_R1_theta090_S500_A350_0850"
CHECKPOINT_PATH = "logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
CHECKPOINT_CONFIG_PATH = "gr00t/rl/config/ablation/wbmanip/base_v19_G2_norm_control.yaml"
B0_JSON_NAME = "a2_piper_base_v20_R1_B0_reference_20260729.json"
B0_CSV_NAME = "a2_piper_base_v20_R1_B0_reference_20260729.csv"
B0_JSON_SHA256 = "98654a976be8b6593e796d89291b4dc6ebdf530d078c625db7130d7a1622c826"
B0_CSV_SHA256 = "209b33a1fa9d79d60f715518cc2798f96b13d71aea8fb2aac0f520a516f4585a"
B0_COMPANION_SCHEMA = "a2_piper_base_v20_R1_B0_reference_v1"
B0_FROZEN_JSON_SHA256 = B0_JSON_SHA256
B0_FROZEN_CSV_SHA256 = B0_CSV_SHA256
B0_POOLED48_EXPECTED = {
    "episodes": 48,
    "seeds": [0, 1, 2],
    "goal_count": 48,
    "crossing_while_holding_count": 48,
    "overspeed_termination_count": 0,
    "post_release_body_contact_count": 0,
    "post_release_body_force_p95_n": 0.0,
    "hinge_at_first_root_crossing_rad": {
        "min": 0.5750486, "p10": 0.6346504, "p50": 0.7189995,
        "p95": 0.8444906, "max": 0.8773267,
    },
    "held_hinge_rad": {"p50": 1.4336079, "p95": 1.5430807},
    "opening_slip_cm": {"p50_cm": 2.1934633, "p95_cm": 2.9084466},
    "release_hinge_rad": {"p50": 1.6054894, "p95": 1.6115434},
    "pre_crossing_bilateral_rate": 0.9966701,
    "pre_crossing_coasting_rate": 0.0028706,
    "pre_crossing_over_force_rate": 0.0004593,
    "pre_crossing_hinge_velocity_radps": {"p50": 0.1987069, "p95": 0.3246622, "max": 0.4179487},
    "root_x_at_release_m": {"p50": 0.5709243, "p95": 0.7298257},
    "task_time_s": {"p50": 12.51, "p95": 13.944},
}
B0_TASKSPACE_DIAGNOSTIC_EXPECTED = {
    "classification": "DIAGNOSTIC_ONLY_TWO_RENDER_EPISODES",
    "combined_step_distribution": {
        "arm_tangent_share": {"p10": 0.0, "p50": 0.0893308, "p95": 1.0},
        "arc_position_error_m": {"p50": 0.0342777, "p95": 0.0393809},
        "arc_orientation_error_rad": {"p50": 0.5363777, "p95": 0.7940030},
    },
    "median_of_episode_arm_share_p50": 0.0677066,
    "worst_episode_p95": {
        "hinge_acceleration_radps2": 0.7797296,
        "hinge_jerk_radps3": 21.7545256,
        "arm_raw_action_rate_per_step": 1.6984240,
        "arm_raw_action_jerk_per_step2": 2.8311783,
    },
}
B0_SOURCE_BINDINGS = (
    ("seed0_per_env_records", "logs_eval/base_v19/G2_m22/base_v19_G2_m22_all_checkpoints_r3_20260727/model_step_002000/seed0/a2_v14_per_env_records.json", "56c152828cd2e57f43e8493097fb062ab1d8a8aef96dd37c0abd8ddf61159f70"),
    ("seed1_per_env_records", "logs_eval/base_v19/m22_shared/_v19_m22_pooled_recovery_r7_20260728/G2/model_step_002000/seed1/a2_v14_per_env_records.json", "388d5e4e4d019427e6b432b3f61c8a2772072f6b65569a89ee4c64373e12423b"),
    ("seed2_per_env_records", "logs_eval/base_v19/m22_shared/_v19_m22_pooled_recovery_r7_20260728/G2/model_step_002000/seed2/a2_v14_per_env_records.json", "10dd616a8b7a3fe723897f92033ca724ff98c24cde8d24387294f06bd805c6c9"),
    ("bucket_report", "logs_eval/base_v19/m22_shared/_v19_m22_pooled_recovery_r7_20260728/G2/selected_endpoint_48door/a2_piper_v17_bucket_report.json", "4c84ca1a6e283d91831baa4380b3e3b580f9707222a83db51ce89da722009d7c"),
    ("endpoint_report", "logs_eval/base_v19/m22_shared/_v19_m22_pooled_recovery_r7_20260728/G2/selected_endpoint_48door/a2_piper_v19_endpoint_report.json", "9c32a9d208f91982cc1d18d4de15fc326f7d26d18ffe98768188974263ebd60b"),
    ("two_env_trace", "logs_eval/base_v19/render/_v19_render_G2_step2000_20260728/winner_G2_2env_3cam_seed0/stage2_5_step_trace.json", "99fba6d134e9f7cb6d7f70d629107e17b67acb47804bb31913abec06563f29fc"),
)
GROUPS = (
    {"group": "G1", "gpu": 0, "seed": 0, "config": "base_v20_R1_G1_g2_continuation.yaml", "s": False, "e": False, "a": False},
    {"group": "G2", "gpu": 1, "seed": 0, "config": "base_v20_R1_G2_economics_only.yaml", "s": False, "e": True, "a": False},
    {"group": "G3", "gpu": 2, "seed": 0, "config": "base_v20_R1_G3_send_curriculum_only.yaml", "s": True, "e": False, "a": False},
    {"group": "G4", "gpu": 3, "seed": 0, "config": "base_v20_R1_G4_send_curriculum_economics.yaml", "s": True, "e": True, "a": False},
    {"group": "G5", "gpu": 4, "seed": 0, "config": "base_v20_R1_G5_send_curriculum_arm_tie.yaml", "s": True, "e": False, "a": True},
    {"group": "G6", "gpu": 5, "seed": 0, "config": "base_v20_R1_G6_full.yaml", "s": True, "e": True, "a": True},
    {"group": "G7", "gpu": 6, "seed": 1, "config": "base_v20_R1_G7_full_seed1.yaml", "s": True, "e": True, "a": True},
)


class R1Error(ValueError):
    """Fail-fast R1 artifact/config error."""


def sha256_file(path: Path | str) -> str:
    target = Path(path)
    if not target.is_file():
        raise R1Error(f"required file is missing: {target}")
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_digest(value: Any, *, name: str, length: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise R1Error(f"{name} must be an exact lowercase hexadecimal digest of length {length}")
    return value


def typed_na(reason: str, denominator: int) -> dict[str, Any]:
    if not isinstance(reason, str) or not reason:
        raise R1Error("typed N/A requires a non-empty reason")
    if isinstance(denominator, bool) or not isinstance(denominator, int) or denominator < 0:
        raise R1Error("typed N/A denominator must be a non-negative integer")
    return {"status": "N/A", "reason": reason, "denominator": denominator}


def validate_typed_metric(value: Any, *, name: str) -> float | dict[str, Any]:
    if isinstance(value, Mapping):
        if value.get("status") != "N/A":
            raise R1Error(f"{name} mapping must use status N/A")
        reason = value.get("reason")
        denominator = value.get("denominator")
        if not isinstance(reason, str) or not reason:
            raise R1Error(f"{name} N/A requires a reason")
        if isinstance(denominator, bool) or not isinstance(denominator, int) or denominator < 0:
            raise R1Error(f"{name} N/A requires a non-negative denominator")
        return dict(value)
    if value is None:
        raise R1Error(f"{name} missing metric; use typed N/A")
    return finite(value, name)


def require_status(payload: Mapping[str, Any], expected: str, *, name: str = "artifact") -> None:
    if not isinstance(payload, Mapping) or payload.get("status") != expected:
        raise R1Error(f"{name} requires typed status {expected!r}")


def canonical_r1_path(repo_root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.startswith(R1_ARTIFACT_ROOT + "/"):
        raise R1Error(f"R1 artifact must stay under {R1_ARTIFACT_ROOT}/: {relative!r}")
    return resolve_repo_path(repo_root, relative)


def hash_paths(repo_root: Path, relative_paths: list[str] | tuple[str, ...]) -> dict[str, str]:
    if len(set(relative_paths)) != len(relative_paths):
        raise R1Error("hash path list contains duplicates")
    return {relative: sha256_file(resolve_repo_path(repo_root, relative)) for relative in relative_paths}


def validate_clean_expected_git(
    repo_root: Path,
    *,
    expected_branch: str = "A2_Piper",
    expected_commit: str | None = None,
) -> dict[str, Any]:
    identity = git_identity(repo_root)
    if identity["dirty"]:
        raise R1Error("formal launch requires a clean working tree")
    if identity["branch"] != expected_branch:
        raise R1Error(
            f"formal launch requires branch {expected_branch!r}, got {identity['branch']!r}"
        )
    if not identity["branch"]:
        raise R1Error("detached HEAD is forbidden for formal launch")
    if expected_commit is not None and identity["commit"] != expected_commit:
        raise R1Error(
            f"formal launch commit mismatch: expected {expected_commit}, got {identity['commit']}"
        )
    return identity


def device_env(gpu: int, *, render: bool = False) -> dict[str, str]:
    gpu = validate_gpu(gpu)
    if render:
        return {
            "CUDA_VISIBLE_DEVICES": str(gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
        }
    return {"ACCELERATE_TORCH_DEVICE": f"cuda:{gpu}"}


def git_identity(repo_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=repo_root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--short"], cwd=repo_root, text=True).strip())
    except (OSError, subprocess.CalledProcessError) as exc:
        raise R1Error("cannot resolve git identity") from exc
    return {"commit": commit, "branch": branch, "dirty": dirty}


def finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise R1Error(f"{name} must be a finite number")
    return float(value)


def resolve_repo_path(repo_root: Path, relative: str) -> Path:
    target = (repo_root / relative).resolve()
    root = repo_root.resolve()
    if target != root and root not in target.parents:
        raise R1Error(f"path escapes repository root: {relative}")
    if target.is_symlink():
        raise R1Error(f"mutable symlink path is forbidden: {relative}")
    return target


def atomic_create_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Create a marker exactly once; never use an exists-then-write TOCTOU check."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise R1Error(f"artifact already exists: {path}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def validate_exact_hash(path: Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise R1Error(f"{label} SHA256 mismatch: expected {expected}, got {actual}")
    return actual


def write_json_no_overwrite(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise R1Error(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise R1Error(f"missing JSON artifact: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R1Error(f"invalid JSON artifact: {path}") from exc


def validate_gpu(gpu: int | str) -> int:
    if isinstance(gpu, str) and gpu.isdigit():
        gpu = int(gpu)
    if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu not in LEGAL_GPUS:
        raise R1Error(f"GPU must be one of 0-6; GPU7 is reserved/unavailable, got {gpu!r}")
    return gpu


def validate_config_mapping(config: Mapping[str, Any], *, group: str | None = None) -> None:
    required = ("checkpoint", "checkpoint_load_mode", "auto_load_latest", "seed", "num_envs", "headless", "algo", "callbacks", "env")
    missing = [key for key in required if key not in config]
    if missing:
        raise R1Error(f"R1 config missing required keys: {missing}")
    if config["checkpoint"] != CHECKPOINT_PATH or config["checkpoint_load_mode"] != "policy_only" or config["auto_load_latest"] is not False:
        raise R1Error("R1 config checkpoint binding must be exact policy-only G2 step2000")
    if config["num_envs"] not in (256, 4096) or config["headless"] is not True:
        raise R1Error("R1 config topology must be headless with 256 pilot or 4096 formal envs")
    env = config["env"].get("config", {})
    if env.get("a2_v20_R1_plan_id") != PLAN_ID or env.get("a2_v20_R1_plan_sha256") != PLAN_SHA256:
        raise R1Error("R1 plan identity is not frozen")
    if env.get("a2_v20_send_hinge_threshold") != 0.90 or env.get("a2_v20_send_hinge_tolerance") != 0.05:
        raise R1Error("R1 send threshold/tolerance drifted")
    if env.get("a2_v20_R1_soft_phase_end_batch") != 500:
        raise R1Error("R1 soft phase boundary must be exactly batch 500")
    if group == "G7" and config.get("seed") != 1:
        raise R1Error("G7 must use training seed 1")


def canonical_topology(name: str) -> dict[str, int]:
    values = {"canonical16": (16, 15), "pooled48": (48, 46), "holdout64": (64, 60)}
    if name not in values:
        raise R1Error(f"unsupported topology {name!r}")
    episodes, minimum = values[name]
    return {"episodes": episodes, "minimum": minimum}
