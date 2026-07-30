"""Small, dependency-free contracts shared by the R2 static tools.

This module is deliberately strict.  It owns the byte representation used for
hashes and markers, path/symlink checks, process-command identity, producer
vocabulary, and physical-device binding.  Higher-level tools should call these
helpers instead of implementing a weaker local variant.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SCIENTIFIC_PLAN_ID = "base_v20_R1_policy_behavior_v1"
ADMISSION_PLAN_ID = "base_v20_R2_admission_execution_v1"
R2_PLAN_PATH = "scriptsFORhuman/a2_piper_base_v20_R2_admission_and_execution_plan_20260730.md"
R2_PLAN_SHA256 = "e82ab57b2f40ba8f8e8c84e518dda0b4b5974a42b06e942e55a7a9e72a7e5371"
R2_PLAN_LOCK_PATH = "scriptsFORhuman/v20_R2/a2_piper_base_v20_R2_plan_lock_20260730.json"
R2_PLAN_LOCK_SHA256 = "01e43100c03f4049c4016b3909bfad6121bab52d2ca1e107ba9bccc91f5fa0ca"
R1_PLAN_PATH = "scriptsFORhuman/a2_piper_base_v20_R1_optimization_plan_20260729.md"
R1_PLAN_SHA256 = "6827290631feea15497fe76cd64116c30a1343d5bd6c1cb83ba09c35bc247e3c"
B0_JSON_PATH = "scriptsFORhuman/v20_R1/a2_piper_base_v20_R1_B0_reference_20260729.json"
B0_JSON_SHA256 = "98654a976be8b6593e796d89291b4dc6ebdf530d078c625db7130d7a1622c826"
B0_CSV_PATH = "scriptsFORhuman/v20_R1/a2_piper_base_v20_R1_B0_reference_20260729.csv"
B0_CSV_SHA256 = "209b33a1fa9d79d60f715518cc2798f96b13d71aea8fb2aac0f520a516f4585a"
R1_BLOCKER_COMMIT = "83cec1036a73c08565601df93aae40ee86856109"
R1_CHECKPOINT_PATH = "logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
R1_CHECKPOINT_SHA256 = "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d"
R1_URDF_PATH = "gr00t/rl/data/robots/A2_Piper/a2_piper.urdf"
R1_URDF_SHA256 = "d02cdacdcd4aaf1480b52ba9a6a62f5e9bbd040036a796154dbff70d1391a1d5"
R1_URDF_GIT_BLOB_SHA1 = "95c7698866962fa6e1b971b9ee534452775d8698"

LEGAL_GPUS = tuple(range(7))
FORBIDDEN_GPU = 7
RESERVED_GPU = FORBIDDEN_GPU

PRODUCER_STATES = frozenset(
    {
        "SOURCE_FROZEN",
        "COMMAND_PLANNED",
        "PROCESS_STARTED",
        "PROCESS_COMPLETED",
        "RECORD_SET_COMPLETE",
        "LAUNCH_PLAN_COMPLETE",
        "ATTEMPT_CONSUMED",
    }
)
ADJUDICATOR_STATES = frozenset(
    {
        "STATIC_PASS",
        "RUNTIME_PASS",
        "RUNTIME_SEMANTIC_PASS",
        "POLICY_LEARNABILITY_PASS",
        "SMOKE_PASS",
        "FORMAL_COMPLETION_PASS",
        "STRICT_VALID",
        "STRICT_INVALID",
        "INCONCLUSIVE",
        "POLICY_PASS",
        "POLICY_FAIL",
        "NO_PROMOTABLE_CHECKPOINT",
        "NO_RELEASE",
        "P0_STATIC_PASS",
        "B0_RUNTIME_PASS",
        "FORCED_RUNTIME_SEMANTIC_PASS",
        "ZERO_SHOT7_RUNTIME_SEMANTIC_PASS",
        "R2_P1_RUNTIME_SEMANTIC_PASS",
        "PILOT_POLICY_LEARNABILITY_PASS",
        "M22_70ROW_PASS",
        "POOLED7_PASS",
        "PROMOTION_PASS",
        "HOLDOUT64_PASS",
        "RENDER_QA_PASS",
    }
)
RAW_FORBIDDEN_FIELDS = frozenset(
    {"status", "pass", "passed", "checks_passed", "verdict", "adjudication"}
)
_GPU7_TOKEN = re.compile(r"(?<![0-9A-Za-z])(?:cuda:7|gpu7|gpu[_ -]?7|CUDA_VISIBLE_DEVICES=7)(?![0-9A-Za-z])", re.IGNORECASE)


class R2Error(ValueError):
    """A fail-fast R2 contract violation."""


def _finite(value: Any, *, path: str = "$", allow_bool: bool = True) -> None:
    if isinstance(value, bool):
        if not allow_bool:
            raise R2Error(f"{path} must be a finite number, not bool")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise R2Error(f"{path} contains NaN or Infinity")
    if isinstance(value, (str, int)) or value is None:
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise R2Error(f"{path} has a non-string JSON key")
            _finite(item, path=f"{path}.{key}", allow_bool=allow_bool)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _finite(item, path=f"{path}[{index}]", allow_bool=allow_bool)
        return
    raise R2Error(f"{path} contains unsupported JSON type {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return compact, sorted UTF-8 JSON and reject non-finite values."""

    _finite(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise R2Error("value cannot be represented as canonical JSON") from exc


def canonical_json(value: Any) -> str:
    """String form of :func:`canonical_json_bytes` for callers/tests."""

    return canonical_json_bytes(value).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise R2Error("sha256_bytes requires bytes")
    return hashlib.sha256(value).hexdigest()


def _absolute_no_symlink(path: Path) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = Path.cwd() / target
    target = Path(os.path.abspath(target))
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise R2Error(f"symlink path component is forbidden: {target}")
    return target


def validate_regular_file(path: Path | str, *, label: str = "file") -> Path:
    """Require a regular, non-symlink file and reject symlink ancestors."""

    target = _absolute_no_symlink(Path(path))
    try:
        mode = os.lstat(target).st_mode
    except FileNotFoundError as exc:
        raise R2Error(f"{label} is missing: {path}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise R2Error(f"{label} must be a regular non-symlink file: {path}")
    return target


def _validate_directory_chain(path: Path) -> Path:
    target = _absolute_no_symlink(path)
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current /= part
        if current.exists():
            mode = os.lstat(current).st_mode
            if stat.S_ISLNK(mode):
                raise R2Error(f"symlink directory component is forbidden: {target}")
            if not stat.S_ISDIR(mode):
                raise R2Error(f"path component is not a directory: {current}")
    return target


def resolve_repo_path(repo_root: Path | str, value: Path | str, *, require_file: bool = False) -> Path:
    """Resolve a repo-relative path without allowing traversal or symlinks."""

    root = _absolute_no_symlink(Path(repo_root))
    if not root.exists() or not root.is_dir():
        raise R2Error(f"repository root is not a directory: {repo_root}")
    candidate = Path(value)
    if candidate.is_absolute():
        target = _absolute_no_symlink(candidate)
    else:
        if any(part == ".." for part in candidate.parts):
            raise R2Error(f"repo-relative path contains traversal: {value}")
        target = _absolute_no_symlink(root / candidate)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise R2Error(f"path escapes repository root: {value}") from exc
    if require_file:
        validate_regular_file(target, label="repo source")
    else:
        _validate_directory_chain(target.parent if target.name else target)
        if target.exists() and target.is_symlink():
            raise R2Error(f"symlink path is forbidden: {value}")
    return target


def repo_relative_path(repo_root: Path | str, value: Path | str, *, require_file: bool = False) -> str:
    root = _absolute_no_symlink(Path(repo_root))
    target = resolve_repo_path(root, value, require_file=require_file)
    relative = target.relative_to(root)
    if not relative.parts:
        raise R2Error("repository root itself is not a source path")
    return relative.as_posix()


def sha256_file(path: Path | str) -> str:
    target = validate_regular_file(path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_sha256(value: Any, *, name: str = "digest") -> str:
    if not isinstance(value, str) or len(value) != 64 or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise R2Error(f"{name} must be exactly 64 lowercase hexadecimal characters")
    return value


def validate_hash(path: Path | str, expected: str, *, label: str = "file") -> str:
    exact_sha256(expected, name=f"{label} expected hash")
    actual = sha256_file(path)
    if actual != expected:
        raise R2Error(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def _prepare_exclusive_parent(path: Path) -> Path:
    target = _absolute_no_symlink(path)
    parent = _absolute_no_symlink(target.parent)
    parent.mkdir(parents=True, exist_ok=True)
    _validate_directory_chain(parent)
    return target


def write_bytes_exclusive(path: Path | str, content: bytes, *, mode: int = 0o444) -> str:
    """Atomically create a regular marker, fsync it and its parent, never overwrite."""

    if not isinstance(content, bytes):
        raise R2Error("write_bytes_exclusive requires bytes")
    target = _prepare_exclusive_parent(Path(path))
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError as exc:
        raise R2Error(f"artifact already exists: {path}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(target, mode)
        parent_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        # A failed marker is not evidence.  Cleanup is limited to this newly
        # opened path; an existing artifact can never be removed here.
        try:
            if target.exists() and not target.is_symlink():
                target.unlink()
        except OSError:
            pass
        raise
    return sha256_bytes(content)


def write_json_exclusive(path: Path | str, payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise R2Error("JSON marker payload must be an object")
    return write_bytes_exclusive(Path(path), canonical_json_bytes(payload))


def utc_now() -> str:
    """Return a strictly ordered, RFC3339 UTC timestamp."""

    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def file_identity(path: Path | str, *, label: str = "artifact") -> dict[str, Any]:
    """Return a regular-file identity suitable for parent binding."""

    target = validate_regular_file(path, label=label)
    return {"path": str(target), "sha256": sha256_file(target), "size": target.stat().st_size}


def process_identity(pid: int) -> dict[str, Any]:
    """Read Linux process identity without treating a missing child as success."""

    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise R2Error(f"process pid must be positive integer, got {pid!r}")
    status_path = Path("/proc") / str(pid) / "status"
    try:
        status = status_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise R2Error(f"process {pid} is not observable") from exc
    values: dict[str, str] = {}
    for line in status.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key] = value.strip()
    try:
        ppid = int(values["PPid"])
    except (KeyError, ValueError) as exc:
        raise R2Error(f"process {pid} has no valid parent identity") from exc
    if ppid <= 0:
        raise R2Error(f"process {pid} has invalid parent pid {ppid}")
    return {"pid": pid, "ppid": ppid, "state": values.get("State", "")}


# Explicit aliases keep all R2 producers on the same fail-fast primitive.
atomic_write_json = write_json_exclusive
write_json_no_overwrite = write_json_exclusive
canonical_json_dumps = canonical_json
validate_repo_relative_path = repo_relative_path


def load_json(path: Path | str) -> Any:
    target = validate_regular_file(path, label="JSON artifact")
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R2Error(f"invalid JSON artifact: {path}") from exc


def hash_command_env(argv: Sequence[str], env: Mapping[str, str]) -> str:
    if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
        raise R2Error("argv must be a sequence of strings")
    if not all(isinstance(item, str) for item in argv):
        raise R2Error("argv entries must be strings")
    if not isinstance(env, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise R2Error("environment must map string keys to string values")
    return sha256_bytes(canonical_json_bytes({"argv": list(argv), "env": dict(sorted(env.items()))}))


command_env_sha256 = hash_command_env


def git_identity(repo_root: Path | str) -> dict[str, Any]:
    root = resolve_repo_path(repo_root, ".")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root, text=True)
        tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise R2Error("cannot resolve git identity") from exc
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise R2Error(f"unexpected git commit: {commit!r}")
    return {"commit": commit, "branch": branch, "dirty": bool(status.strip()), "status": status, "tree": tree}


def validate_clean_git(repo_root: Path | str, *, branch: str, required_ancestor: str) -> dict[str, Any]:
    identity = git_identity(repo_root)
    if not identity["branch"]:
        raise R2Error("detached HEAD is forbidden")
    if identity["branch"] != branch:
        raise R2Error(f"expected branch {branch!r}, got {identity['branch']!r}")
    if identity["dirty"]:
        raise R2Error("source freeze requires a clean worktree")
    exact_commit = required_ancestor
    if re.fullmatch(r"[0-9a-f]{40}", exact_commit) is None:
        raise R2Error("required ancestor must be a 40-character commit")
    try:
        subprocess.check_call(["git", "merge-base", "--is-ancestor", exact_commit, "HEAD"], cwd=Path(repo_root))
    except (OSError, subprocess.CalledProcessError) as exc:
        raise R2Error(f"required ancestor is not an ancestor of HEAD: {required_ancestor}") from exc
    return identity


def validate_gpu(gpu: int | str) -> int:
    if isinstance(gpu, str) and gpu.isdecimal():
        gpu = int(gpu)
    if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu not in LEGAL_GPUS:
        raise R2Error(f"physical GPU must be one of 0-6; GPU7 is forbidden, got {gpu!r}")
    return gpu


def device_env(gpu: int | str, *, render: bool = False) -> dict[str, str]:
    physical = validate_gpu(gpu)
    if render:
        return {"CUDA_VISIBLE_DEVICES": str(physical), "ACCELERATE_TORCH_DEVICE": "cuda:0"}
    return {"ACCELERATE_TORCH_DEVICE": f"cuda:{physical}"}


def _contains_gpu7(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_GPU7_TOKEN.search(value))
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key.upper() == "CUDA_VISIBLE_DEVICES" and isinstance(child, str):
                if any(part.strip() == "7" for part in child.split(",")):
                    return True
            if _contains_gpu7(key) or _contains_gpu7(child):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_gpu7(item) for item in value)
    return False


def validate_device_contract(
    *,
    gpu: int | str,
    render: bool,
    argv: Sequence[str],
    env: Mapping[str, str],
    app_launcher_device: str | None = None,
    accelerator_device: str | None = None,
    observed_physical_gpu: int | str | None = None,
) -> dict[str, Any]:
    """Validate physical/logical CUDA binding before a process can spawn."""

    physical = validate_gpu(gpu)
    if _contains_gpu7(argv) or _contains_gpu7(env):
        raise R2Error("GPU7 is forbidden in command or environment")
    expected = "cuda:0" if render else f"cuda:{physical}"
    if app_launcher_device is not None and app_launcher_device != expected:
        raise R2Error(f"AppLauncher device mismatch: expected {expected}, got {app_launcher_device}")
    if accelerator_device is not None and accelerator_device != expected:
        raise R2Error(f"Accelerator device mismatch: expected {expected}, got {accelerator_device}")
    mask = env.get("CUDA_VISIBLE_DEVICES")
    if render:
        if mask != str(physical):
            raise R2Error("render jobs require a single-physical-GPU visibility mask")
        if env.get("ACCELERATE_TORCH_DEVICE") != "cuda:0":
            raise R2Error("render jobs require logical cuda:0")
    else:
        if mask is not None:
            raise R2Error("non-render jobs must not set CUDA_VISIBLE_DEVICES")
        if env.get("ACCELERATE_TORCH_DEVICE") != f"cuda:{physical}":
            raise R2Error(f"non-render jobs require physical cuda:{physical}")
    if observed_physical_gpu is not None and validate_gpu(observed_physical_gpu) != physical:
        raise R2Error("observed GPU binding differs from requested physical GPU")
    return {
        "physical_gpu": physical,
        "logical_device": expected,
        "render": bool(render),
        "visibility_mask": mask,
    }


validate_device_environment = validate_device_contract


def _walk_forbidden_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key.lower() in RAW_FORBIDDEN_FIELDS:
                raise R2Error(f"raw producer field {path}.{key} is forbidden")
            _walk_forbidden_fields(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _walk_forbidden_fields(child, path=f"{path}[{index}]")


def validate_raw_producer_payload(payload: Mapping[str, Any], *, producer_state: str | None = None) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise R2Error("raw producer payload must be an object")
    _walk_forbidden_fields(payload)
    actual = payload.get("producer_state")
    if actual is not None and actual not in PRODUCER_STATES:
        raise R2Error(f"unknown producer_state: {actual!r}")
    if producer_state is not None and actual != producer_state:
        raise R2Error(f"producer_state must be {producer_state!r}, got {actual!r}")
    return payload


def require_producer_state(payload: Mapping[str, Any], expected: str) -> None:
    validate_raw_producer_payload(payload)
    if payload.get("producer_state") != expected:
        raise R2Error(f"producer_state must be {expected!r}")


def require_adjudicator_state(payload: Mapping[str, Any], expected: str) -> None:
    if not isinstance(payload, Mapping):
        raise R2Error("adjudication payload must be an object")
    state = payload.get("adjudicator_state", payload.get("state"))
    if state not in ADJUDICATOR_STATES:
        raise R2Error(f"unknown adjudicator state: {state!r}")
    if state != expected:
        raise R2Error(f"adjudicator state must be {expected!r}, got {state!r}")


def ensure_no_raw_status_fields(payload: Mapping[str, Any]) -> None:
    validate_raw_producer_payload(payload)
