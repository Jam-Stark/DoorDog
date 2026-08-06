#!/usr/bin/env python3
"""Run the selected B1 mixed-rollout 8,000-iteration formal path.

This launcher is deliberately separate from the P2 B1/B2 comparison runner.
It consumes the sealed relative winner only as an immutable promotion input,
creates a fresh B1/common-init root, and executes one continuous trainer
process with the explicit L0/L1/L2/L3 schedule.  ``--dry-run`` performs all
read-only preflight and prints the exact child command without creating roots.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gr00t.rl.scripts import run_a2_cb2h_pro_p2 as p2
from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import (
    resolve_mixed_rollout_phase,
    validate_mixed_rollout_schedule,
)


SELECTION_MANIFEST = (
    REPO_ROOT
    / "logs_eval/cb2h_pro_p2_b1_b2_post_gpu7-retry1-20260804/p2_post_adjudication_manifest.json"
).resolve()
SELECTION_MANIFEST_CONTENT_SHA256 = "bf1cd832404967fb3deeeb683a545c15326b96b0e8346b37d72d0e48ae99f9e7"
SELECTION_MANIFEST_FILE_SHA256 = "ec82fbb12077445b7427e38f3608ed94ec06ce98cabd31b3a9380336d50867db"
SELECTION_MANIFEST_FILE_SIZE = 90282
SELECTION_DECISION = "SELECT_B1"
SELECTION_WINNER = "b1"

TEACHER_CHECKPOINT = p2.TEACHER_CHECKPOINT
TEACHER_CONFIG = p2.TEACHER_CONFIG
TEACHER_MANIFEST = p2.TEACHER_MANIFEST
RUNTIME_REPOSITORY = p2.RUNTIME_REPOSITORY
EXPECTED_RUNTIME_COMMIT = p2.EXPECTED_RUNTIME_COMMIT
EXPECTED_GPU_INDEX = p2.EXPECTED_GPU_INDEX
EXPECTED_LOGICAL_GPU_INDEX = p2.EXPECTED_LOGICAL_GPU_INDEX
EXPECTED_GPU_UUID = p2.EXPECTED_GPU_UUID
EXPECTED_GPU_BINDING_MODE = p2.EXPECTED_GPU_BINDING_MODE
EXPECTED_CUDA_DEVICE_ORDER = p2.EXPECTED_CUDA_DEVICE_ORDER
VRAM_LIMIT_MIB = p2.VRAM_LIMIT_MIB

EXPECTED_NUM_ENVS = 64
EXPECTED_TARGET_GLOBAL_STEP = 8000
EXPECTED_NUM_STEPS_PER_ENV = 8
EXPECTED_NUM_MINI_BATCHES = 4
EXPECTED_NUM_PPO_EPOCHS = 1
EXPECTED_GRADIENT_ACCUMULATION_STEPS = 1
EXPECTED_SAVE_FREQUENCY = 500
EXPECTED_EXPECTED_OPTIMIZER_STATE_STEP = (
    EXPECTED_TARGET_GLOBAL_STEP * EXPECTED_NUM_MINI_BATCHES * EXPECTED_NUM_PPO_EPOCHS
)
EXPECTED_ARCHITECTURE = p2.ARCHITECTURES["b1"]
DEFERRED_BOUNDARY_EVAL_SCOPE = (
    "Boundary evaluation is deferred until after continuous training at steps "
    "1000, 2000, 4000, and 8000: fixed16x3/open-loop/view-utilization/safety."
)
LONG_ROLLOUT_SCHEDULE = (
    {"phase": "L0", "start_step": 0, "end_step": 1000, "ratio": 1.0},
    {"phase": "L1", "start_step": 1000, "end_step": 2000, "ratio": 0.75},
    {"phase": "L2", "start_step": 2000, "end_step": 4000, "ratio": 0.50},
    {"phase": "L3", "start_step": 4000, "end_step": 8000, "ratio": 0.25},
)
validate_mixed_rollout_schedule(
    LONG_ROLLOUT_SCHEDULE,
    target_global_step=EXPECTED_TARGET_GLOBAL_STEP,
)

LONG_SCHEMA = "a2_cb2h_pro_b1_long_v1"
FAILURE_SCHEMA = "a2_cb2h_pro_b1_long_failure_v1"
TELEMETRY_FILENAME = "gpu_telemetry.json"
TELEMETRY_STREAM_FILENAME = "gpu_telemetry.jsonl"
PLAN_FILENAME = "long_plan.json"
STDOUT_FILENAME = "post_runner.stdout.log"
STDERR_FILENAME = "post_runner.stderr.log"
FAILURE_FILENAME = "failure.json"
FINAL_MANIFEST_FILENAME = "long_training_manifest.json"
PROOF_FILENAME = "pre_teardown_completion_proof.json"
METRICS_FILENAME = "runtime_metrics.json"
LIVE_STATE_FILENAME = "live_state.json"
LIVE_STATE_SCHEMA = "a2_cb2h_pro_b1_long_live_state_v1"
SOURCE_SNAPSHOT_SCHEMA = "a2_cb2h_pro_b1_long_source_snapshot_v1"
_MARKER_POLL_INTERVAL_S = 0.5
_MARKER_READ_CHUNK_BYTES = 64 * 1024
_MAX_MARKER_PARTIAL_BYTES = 1024 * 1024

SOURCE_CANDIDATE_PATHS = {
    "trainer": REPO_ROOT / "gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py",
    "train_entry": REPO_ROOT / "gr00t/rl/train_agent_trl.py",
    "p2_actor": REPO_ROOT / "gr00t/rl/trl/modules/vision_actor_critic_modules_p2_recurrent.py",
    "b1_config": REPO_ROOT / "gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_p2_b1.yaml",
    "p2_runner": REPO_ROOT / "gr00t/rl/scripts/run_a2_cb2h_pro_p2.py",
    "v19_bootstrap": REPO_ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v19.py",
    "long_runner": Path(__file__).resolve(),
}


class LongTrainingBlocked(RuntimeError):
    """A required long-training preflight or evidence gate failed closed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError(f"long-training JSON must be an object: {path}")
    return dict(payload)


def _confined(path: Path, root: Path, name: str, *, strict: bool = True) -> Path:
    resolved = path.expanduser().resolve(strict=strict)
    root = root.expanduser().resolve()
    if not resolved.is_relative_to(root):
        raise LongTrainingBlocked(f"{name} escapes long output root: {resolved}")
    return resolved


def _artifact_ref(path: Path, root: Path | None = None, name: str = "artifact") -> dict[str, Any]:
    path = path.expanduser().resolve(strict=True)
    if root is not None:
        _confined(path, root, name)
    return {"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size}


def _destination(path: Path) -> Path:
    """Resolve a destination without allowing an existing symlink target."""
    raw = Path(path).expanduser()
    if raw.is_symlink():
        raise FileExistsError(f"long destination refuses symlink: {raw}")
    return raw.resolve(strict=False)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Create one immutable JSON seal with exclusive, race-free installation."""
    destination = _destination(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(payload) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".writing", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link installation is atomic and cannot overwrite an existing
        # destination.  The temporary inode is removed after installation.
        os.link(temporary, destination)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    else:
        temporary.unlink()
    return {"path": str(destination), "sha256": sha256_bytes(encoded), "size": len(encoded)}


def _replace_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Atomically replace mutable operational state; never use for immutable seals."""
    destination = _destination(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(payload) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".writing", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return {"path": str(destination), "sha256": sha256_bytes(encoded), "size": len(encoded)}


def _open_exclusive_binary(path: Path):
    """Open one canonical log/stream path exactly once with no overwrite."""
    destination = _destination(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(str(destination), flags, 0o644)
    return os.fdopen(descriptor, "wb", buffering=0), destination


def _flush_log(stream) -> None:
    stream.flush()
    os.fsync(stream.fileno())


def _write_prelaunch_error(stream, error: BaseException) -> None:
    stream.write(f"{type(error).__name__}: {error}\n".encode("utf-8"))
    _flush_log(stream)


def capture_source_snapshot() -> dict[str, Any]:
    """Capture the exact overlay candidate inputs used by the child."""
    files: dict[str, dict[str, Any]] = {}
    for label, raw_path in SOURCE_CANDIDATE_PATHS.items():
        if raw_path.is_symlink():
            raise LongTrainingBlocked(f"long source candidate {label} must not be a symlink")
        path = raw_path.resolve(strict=True)
        if not path.is_file() or path.is_symlink():
            raise LongTrainingBlocked(f"long source candidate {label} is not a regular file: {path}")
        files[label] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
    return {"schema": SOURCE_SNAPSHOT_SCHEMA, "files": files}


class BoundedGpuTelemetrySampler:
    """Stream exact P2 telemetry rows to JSONL without retaining the run history."""

    def __init__(self, environ: Mapping[str, str], stream, stream_path: Path):
        self.environ = dict(environ)
        self.stream = stream
        self.stream_path = stream_path
        self.interval_s = float(p2.P2_TELEMETRY_SAMPLE_INTERVAL_S)
        if not math.isclose(self.interval_s, 5.0, rel_tol=0.0, abs_tol=1.0e-12):
            raise ValueError("long B1 telemetry cadence must remain the exact 5-second P2 cadence")
        self.sample_count = 0
        self.peak_vram_mib: float | None = None
        self.last_sample_time_ns: int | None = None
        self.error: BaseException | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._closed = False

    def _append(self, record: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(record)
        self.stream.write((canonical_json(row) + "\n").encode("utf-8"))
        self.stream.flush()
        self.sample_count += 1
        memory = float(row["memory_used_mib"])
        self.peak_vram_mib = memory if self.peak_vram_mib is None else max(self.peak_vram_mib, memory)
        self.last_sample_time_ns = int(row["sample_time_ns"])
        return row

    def sample_once(self) -> dict[str, Any]:
        self.raise_if_failed()
        if self._closed:
            raise RuntimeError("long B1 telemetry sampler is already closed")
        return self._append(p2.sample_gpu_telemetry(self.environ))

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self.sample_once()
                self._stop.wait(self.interval_s)
        except BaseException as exc:
            self.error = exc
            self._stop.set()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("long B1 telemetry sampler already started")
        self._thread = threading.Thread(target=self._run, name="a2-cb2h-long-gpu-sampler", daemon=True)
        self._thread.start()

    def raise_if_failed(self) -> None:
        if self.error is not None:
            raise RuntimeError("long B1 telemetry sampler failed") from self.error

    def snapshot(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "peak_vram_mib": self.peak_vram_mib,
            "last_sample_time_ns": self.last_sample_time_ns,
            "stream_path": str(self.stream_path),
            "error": None
            if self.error is None
            else {"type": type(self.error).__name__, "message": str(self.error)},
        }

    def stop(self, *, process_started_ns: int, process_ended_ns: int) -> None:
        if self._thread is None:
            raise RuntimeError("long B1 telemetry sampler was not started")
        self._stop.set()
        self._thread.join(timeout=30.0)
        if self._thread.is_alive():
            raise RuntimeError("long B1 telemetry sampler did not stop")
        self.raise_if_failed()
        if process_ended_ns <= process_started_ns:
            raise ValueError("long B1 telemetry process interval is not increasing")
        # This is the required synchronous terminal post-process sample.
        self.sample_once()
        _flush_log(self.stream)

    def close(self) -> None:
        if self._closed:
            return
        self.stream.close()
        self._closed = True


class CanonicalMarkerReader:
    """Incrementally parse only flushed, canonical A2 rollout markers."""

    def __init__(self, path: Path):
        self.path = path
        self._stream = path.open("rb")
        self._partial = b""
        self._phase: dict[str, Any] | None = None
        self._mask: dict[str, Any] | None = None
        self._marker_count = 0
        self._step_history: list[int] = []

    @staticmethod
    def _fields(line: str, prefix: str, expected: set[str]) -> dict[str, str]:
        if not line.startswith(prefix):
            raise LongTrainingBlocked(f"long B1 canonical marker prefix drifted: {line!r}")
        fields = line[len(prefix) :].strip().split()
        parsed: dict[str, str] = {}
        for field in fields:
            if "=" not in field:
                raise LongTrainingBlocked(f"long B1 canonical marker field is malformed: {line!r}")
            key, value = field.split("=", 1)
            if key in parsed:
                raise LongTrainingBlocked(f"long B1 canonical marker field is duplicated: {line!r}")
            parsed[key] = value
        if set(parsed) != expected:
            raise LongTrainingBlocked(f"long B1 canonical marker fields drifted: {line!r}")
        return parsed

    @staticmethod
    def _int(value: str, label: str) -> int:
        try:
            result = int(value)
        except ValueError as exc:
            raise LongTrainingBlocked(f"long B1 canonical marker {label} is not an integer") from exc
        if result < 0:
            raise LongTrainingBlocked(f"long B1 canonical marker {label} must be non-negative")
        return result

    @staticmethod
    def _ratio(value: str, label: str) -> float:
        try:
            result = float(value)
        except ValueError as exc:
            raise LongTrainingBlocked(f"long B1 canonical marker {label} is not finite") from exc
        if not math.isfinite(result) or not 0.0 <= result <= 1.0:
            raise LongTrainingBlocked(f"long B1 canonical marker {label} is outside [0,1]")
        return result

    def _consume(self, raw_line: bytes) -> None:
        try:
            line = raw_line.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise LongTrainingBlocked("long B1 stdout contains non-UTF8 marker bytes") from exc
        if not line:
            return
        if line.startswith("[A2_ROLLOUT_PHASE]"):
            fields = self._fields(line, "[A2_ROLLOUT_PHASE]", {"transition", "global_step", "ratio"})
            transition = fields["transition"]
            if "->" not in transition:
                raise LongTrainingBlocked(f"long B1 rollout phase transition is malformed: {line!r}")
            phase = transition.rsplit("->", 1)[1]
            if not phase:
                raise LongTrainingBlocked(f"long B1 rollout phase name is empty: {line!r}")
            step = self._int(fields["global_step"], "global_step")
            ratio = self._ratio(fields["ratio"], "ratio")
            expected = resolve_mixed_rollout_phase(LONG_ROLLOUT_SCHEDULE, step)
            if phase != expected["phase"] or not math.isclose(ratio, expected["ratio"], rel_tol=0.0, abs_tol=1.0e-12):
                raise LongTrainingBlocked(f"long B1 rollout phase marker disagrees with schedule: {line!r}")
            self._phase = {"phase": phase, "global_step": step, "ratio": ratio}
            return
        if line.startswith("[A2_ROLLOUT_MASK]"):
            fields = self._fields(
                line,
                "[A2_ROLLOUT_MASK]",
                {"phase", "ratio", "global_step", "teacher_count", "student_count", "mask_hash"},
            )
            step = self._int(fields["global_step"], "global_step")
            ratio = self._ratio(fields["ratio"], "ratio")
            phase = fields["phase"]
            expected = resolve_mixed_rollout_phase(LONG_ROLLOUT_SCHEDULE, step)
            if phase != expected["phase"] or not math.isclose(ratio, expected["ratio"], rel_tol=0.0, abs_tol=1.0e-12):
                raise LongTrainingBlocked(f"long B1 rollout mask marker disagrees with schedule: {line!r}")
            teacher_count = self._int(fields["teacher_count"], "teacher_count")
            student_count = self._int(fields["student_count"], "student_count")
            if teacher_count + student_count != EXPECTED_NUM_ENVS:
                raise LongTrainingBlocked(f"long B1 rollout mask counts do not equal {EXPECTED_NUM_ENVS}: {line!r}")
            expected_teacher = int(round(EXPECTED_NUM_ENVS * ratio))
            if teacher_count != expected_teacher or student_count != EXPECTED_NUM_ENVS - expected_teacher:
                raise LongTrainingBlocked(f"long B1 rollout mask counts disagree with ratio: {line!r}")
            mask_hash = fields["mask_hash"]
            if re.fullmatch(r"[0-9a-f]{64}", mask_hash) is None:
                raise LongTrainingBlocked(f"long B1 rollout mask hash is malformed: {line!r}")
            self._mask = {
                "phase": phase,
                "global_step": step,
                "ratio": ratio,
                "teacher_count": teacher_count,
                "student_count": student_count,
                "mask_hash": mask_hash,
            }
            self._marker_count += 1
            if not self._step_history or self._step_history[-1] != step:
                self._step_history.append(step)
            if len(self._step_history) > 16:
                self._step_history = self._step_history[-16:]

    def poll(self) -> None:
        data = self._stream.read(_MARKER_READ_CHUNK_BYTES)
        if data:
            self._partial += data
            if len(self._partial) > _MAX_MARKER_PARTIAL_BYTES:
                raise LongTrainingBlocked("long B1 stdout contains an unterminated oversized line")
            lines = self._partial.split(b"\n")
            self._partial = lines.pop()
            for line in lines:
                self._consume(line)

    def snapshot(self) -> dict[str, Any]:
        latest = self._mask or self._phase or {}
        return {
            "phase": latest.get("phase"),
            "global_step": latest.get("global_step"),
            "ratio": latest.get("ratio"),
            "teacher_count": None if self._mask is None else self._mask["teacher_count"],
            "student_count": None if self._mask is None else self._mask["student_count"],
            "mask_hash": None if self._mask is None else self._mask["mask_hash"],
            "marker_count": self._marker_count,
            "global_step_tail": list(self._step_history),
        }

    def close(self) -> None:
        self._stream.close()


def _selection_content_sha(payload: Mapping[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("content_sha256", None)
    return sha256_bytes(canonical_json(unsigned).encode("utf-8"))


@dataclass(frozen=True)
class SelectionSnapshot:
    path: Path
    file_sha256: str
    file_size: int
    content_sha256: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "file_sha256": self.file_sha256,
            "file_size": self.file_size,
            "content_sha256": self.content_sha256,
            "decision": self.payload["decision"],
            "selected_branch": self.payload["adjudication"]["selected_branch"],
            "winner": self.payload["adjudication"]["winner"],
            "zero_goals_or_poor_quality_visible": self.payload["adjudication"][
                "zero_goals_or_poor_quality_visible"
            ],
            "effectiveness_pass": self.payload["adjudication"]["effectiveness_pass"],
            "safety_pass": self.payload["adjudication"]["safety_pass"],
        }


def validate_selection_manifest(path: Path = SELECTION_MANIFEST) -> SelectionSnapshot:
    path = path.expanduser().resolve(strict=True)
    payload_bytes = path.read_bytes()
    file_sha = sha256_bytes(payload_bytes)
    if file_sha != SELECTION_MANIFEST_FILE_SHA256:
        raise LongTrainingBlocked(
            f"selected B1 adjudication file SHA drifted: expected={SELECTION_MANIFEST_FILE_SHA256} actual={file_sha}"
        )
    if len(payload_bytes) != SELECTION_MANIFEST_FILE_SIZE:
        raise LongTrainingBlocked(
            f"selected B1 adjudication file size drifted: expected={SELECTION_MANIFEST_FILE_SIZE} actual={len(payload_bytes)}"
        )
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LongTrainingBlocked("selected B1 adjudication manifest is unreadable") from exc
    if not isinstance(payload, Mapping):
        raise LongTrainingBlocked("selected B1 adjudication manifest must be an object")
    payload = dict(payload)
    declared_content = payload.get("content_sha256")
    actual_content = _selection_content_sha(payload)
    if declared_content != SELECTION_MANIFEST_CONTENT_SHA256 or actual_content != declared_content:
        raise LongTrainingBlocked(
            "selected B1 adjudication content SHA drifted: "
            f"declared={declared_content!r} actual={actual_content}"
        )
    adjudication = payload.get("adjudication")
    if not isinstance(adjudication, Mapping):
        raise LongTrainingBlocked("selected B1 adjudication block is missing")
    if payload.get("decision") != SELECTION_DECISION or adjudication.get("decision") != SELECTION_DECISION:
        raise LongTrainingBlocked("selected B1 adjudication decision is not SELECT_B1")
    if adjudication.get("selected_branch") != SELECTION_WINNER or adjudication.get("winner") != SELECTION_WINNER:
        raise LongTrainingBlocked("selected B1 adjudication winner drifted")
    if adjudication.get("zero_goals_or_poor_quality_visible") is not True:
        raise LongTrainingBlocked("selected B1 poor-quality visibility proof is missing")
    if adjudication.get("effectiveness_pass") is not False or adjudication.get("safety_pass") is not True:
        raise LongTrainingBlocked("selected B1 relative architecture gate proof drifted")
    selected = adjudication.get("selected_provenance")
    if not isinstance(selected, Mapping) or selected.get("branch") != "b1":
        raise LongTrainingBlocked("selected B1 provenance is missing")
    if selected.get("architecture") != EXPECTED_ARCHITECTURE:
        raise LongTrainingBlocked("selected B1 architecture drifted")
    # The selected step-500 checkpoint is provenance only.  The long runner
    # must launch checkpoint=null and create a fresh/common initialization.
    checkpoint = selected.get("checkpoint")
    common_init = selected.get("common_init")
    if not isinstance(checkpoint, Mapping) or checkpoint.get("global_step") != 500:
        raise LongTrainingBlocked("selected B1 provenance must identify the sealed step-500 checkpoint")
    if not isinstance(common_init, Mapping) or not isinstance(common_init.get("artifact"), Mapping):
        raise LongTrainingBlocked("selected B1 common-init provenance is missing")
    return SelectionSnapshot(
        path=path,
        file_sha256=file_sha,
        file_size=len(payload_bytes),
        content_sha256=actual_content,
        payload=payload,
    )


def _schedule_override() -> str:
    entries = ",".join(
        "{phase:%s,start_step:%d,end_step:%d,ratio:%s}"
        % (item["phase"], item["start_step"], item["end_step"], repr(item["ratio"]))
        for item in LONG_ROLLOUT_SCHEDULE
    )
    return f"+algo.config.mixed_rollout_schedule=[{entries}]"


def build_long_overrides(branch_root: Path, common_root: Path) -> tuple[str, ...]:
    branch_root = Path(branch_root).expanduser().resolve()
    common_root = Path(common_root).expanduser().resolve()
    artifact = common_root / "b1_common_init.pt"
    step0 = common_root / "b1_step0_manifest.json"
    return (
        "+exp=wbmanip/door_open_a2_base_v19_p2_b1",
        f"num_envs={EXPECTED_NUM_ENVS}",
        f"algo.trl.num_total_batches={EXPECTED_TARGET_GLOBAL_STEP}",
        f"callbacks.model_save.save_frequency={EXPECTED_SAVE_FREQUENCY}",
        f"experiment_dir={branch_root}",
        "checkpoint=null",
        "checkpoint_load_mode=full",
        "auto_load_latest=false",
        "use_wandb=false",
        "headless=true",
        "enable_cameras=true",
        f"algo.config.num_steps_per_env={EXPECTED_NUM_STEPS_PER_ENV}",
        f"algo.config.num_mini_batches={EXPECTED_NUM_MINI_BATCHES}",
        f"algo.config.num_learning_epochs={EXPECTED_NUM_PPO_EPOCHS}",
        f"algo.trl.num_ppo_epochs={EXPECTED_NUM_PPO_EPOCHS}",
        f"algo.trl.gradient_accumulation_steps={EXPECTED_GRADIENT_ACCUMULATION_STEPS}",
        "algo.config.actor_learning_rate=0.0001",
        "algo.config.gamma=0.9966",
        "algo.config.lam=0.983",
        "algo.config.desired_kl=0.005",
        "algo.config.init_at_random_ep_len=false",
        "algo.config.use_obj_pred=false",
        "algo.config.obj_pred_loss_coef=0.0",
        f"teacher_actor_path={TEACHER_CHECKPOINT}",
        f"teacher_config_path={TEACHER_CONFIG}",
        f"teacher_manifest_path={TEACHER_MANIFEST}",
        "algo.config.use_a2_base=true",
        "algo.config.enforce_teacher_rollout=true",
        "algo.config.ratio_teacher_rollout=1.0",
        _schedule_override(),
        "algo.config.p2_common_init.enabled=true",
        "algo.config.p2_common_init.branch=b1",
        "algo.config.p2_common_init.mode=create",
        f"algo.config.p2_common_init.architecture={EXPECTED_ARCHITECTURE}",
        "algo.config.p2_common_init.seed=0",
        f"algo.config.p2_common_init.config_sha256={p2.P2_COMMON_CONFIG_SHA256}",
        f"algo.config.p2_common_init.artifact_path={artifact}",
        f"algo.config.p2_common_init.step0_manifest_path={step0}",
        f"algo.config.p2_common_init.source_step0_manifest_path={step0}",
        "algo.config.p2_common_init.trusted_artifact_sha256=REQUIRED_AFTER_B1_STEP0_SEAL",
        "algo.config.p2_common_init.trusted_source_step0_manifest_sha256=REQUIRED_AFTER_B1_STEP0_SEAL",
        f"algo.config.p2_common_init.runtime_identity.runtime_repository={RUNTIME_REPOSITORY}",
        f"algo.config.p2_common_init.runtime_identity.runtime_commit={EXPECTED_RUNTIME_COMMIT}",
        "algo.config.p2_lifecycle.enabled=true",
        f"algo.config.p2_lifecycle.target_global_step={EXPECTED_TARGET_GLOBAL_STEP}",
        "~obs.obs_dict.context_vision_obs",
    )


def _validate_long_config(config: Any) -> None:
    if config.num_envs != EXPECTED_NUM_ENVS:
        raise LongTrainingBlocked("long B1 num_envs drifted")
    if config.algo.trl.num_total_batches != EXPECTED_TARGET_GLOBAL_STEP:
        raise LongTrainingBlocked("long B1 num_total_batches drifted")
    if config.callbacks.model_save.save_frequency != EXPECTED_SAVE_FREQUENCY:
        raise LongTrainingBlocked("long B1 save_frequency drifted")
    effective = config.algo.config
    if config.simulator.config.cameras.policy_multiview.architecture_id != EXPECTED_ARCHITECTURE:
        raise LongTrainingBlocked("long B1 camera architecture drifted")
    actor_target = str(effective.actor._target_)
    if not actor_target.endswith("vision_actor_critic_modules_p2_recurrent.DualD435VisionRecurrentActor"):
        raise LongTrainingBlocked("long B1 actor target is not the packed no-Head actor")
    if effective.actor.view_contract.d435i_forward_mode != "packed":
        raise LongTrainingBlocked("long B1 D435 forward mode must be packed")
    common_init = effective.get("p2_common_init")
    if (
        common_init is None
        or common_init.get("branch") != "b1"
        or common_init.get("mode") != "create"
        or common_init.get("architecture") != EXPECTED_ARCHITECTURE
        or common_init.get("config_sha256") != p2.P2_COMMON_CONFIG_SHA256
        or common_init.get("runtime_identity", {}).get("runtime_repository") != str(RUNTIME_REPOSITORY)
        or common_init.get("runtime_identity", {}).get("runtime_commit") != EXPECTED_RUNTIME_COMMIT
    ):
        raise LongTrainingBlocked("long B1 common-init provenance drifted")
    if config.teacher_actor_path != str(TEACHER_CHECKPOINT) or config.teacher_config_path != str(TEACHER_CONFIG) or config.teacher_manifest_path != str(TEACHER_MANIFEST):
        raise LongTrainingBlocked("long B1 Teacher triplet path drifted")
    exact = {
        "num_steps_per_env": EXPECTED_NUM_STEPS_PER_ENV,
        "num_mini_batches": EXPECTED_NUM_MINI_BATCHES,
        "num_learning_epochs": EXPECTED_NUM_PPO_EPOCHS,
        "ratio_teacher_rollout": 1.0,
        "enforce_teacher_rollout": True,
    }
    for key, expected in exact.items():
        actual = effective.get(key)
        if actual != expected:
            raise LongTrainingBlocked(f"long B1 config {key} drifted: expected={expected!r} actual={actual!r}")
    lifecycle = effective.get("p2_lifecycle")
    if lifecycle is None or lifecycle.get("enabled") is not True or lifecycle.get("target_global_step") != EXPECTED_TARGET_GLOBAL_STEP:
        raise LongTrainingBlocked("long B1 lifecycle target drifted")
    schedule = effective.get("mixed_rollout_schedule")
    try:
        normalized = validate_mixed_rollout_schedule(
            schedule,
            target_global_step=EXPECTED_TARGET_GLOBAL_STEP,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise LongTrainingBlocked("long B1 mixed-rollout schedule failed strict validation") from exc
    if tuple(normalized) != tuple(LONG_ROLLOUT_SCHEDULE):
        raise LongTrainingBlocked("long B1 mixed-rollout schedule drifted")
    if "context_vision_obs" in config.obs.obs_dict or "head_vision_module" in effective.actor.backbone:
        raise LongTrainingBlocked("long B1 must not contain Head/context inputs")
    if config.checkpoint is not None or config.auto_load_latest or config.checkpoint_load_mode != "full":
        raise LongTrainingBlocked("long B1 must start from fresh checkpoint=null/common-init")


@dataclass(frozen=True)
class LongPlan:
    output_root: Path
    branch_root: Path
    common_root: Path
    selection: SelectionSnapshot
    teacher: dict[str, dict[str, str]]
    runtime: dict[str, Any]
    overrides: tuple[str, ...]
    command: tuple[str, ...]
    source_snapshot: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": LONG_SCHEMA,
            "operation": "cb2h_pro_b1_long_mixed_rollout",
            "output_root": str(self.output_root),
            "branch_root": str(self.branch_root),
            "common_root": str(self.common_root),
            "selection": self.selection.as_dict(),
            "teacher": self.teacher,
            "runtime": {
                "repository": str(RUNTIME_REPOSITORY),
                "commit": EXPECTED_RUNTIME_COMMIT,
                "gpu_host_index": EXPECTED_GPU_INDEX,
                "gpu_logical_index": EXPECTED_LOGICAL_GPU_INDEX,
                "gpu_uuid": EXPECTED_GPU_UUID,
                "binding_mode": EXPECTED_GPU_BINDING_MODE,
                "world_size": 1,
            },
            "source_snapshot": self.source_snapshot,
            "architecture": EXPECTED_ARCHITECTURE,
            "schedule": [dict(item) for item in LONG_ROLLOUT_SCHEDULE],
            "target_global_step": EXPECTED_TARGET_GLOBAL_STEP,
            "save_frequency": EXPECTED_SAVE_FREQUENCY,
            "checkpoint_start": None,
            "common_init_mode": "fresh_create",
            "deferred_boundary_eval_scope": DEFERRED_BOUNDARY_EVAL_SCOPE,
            "overrides": list(self.overrides),
            "command": list(self.command),
        }


def build_long_plan(output_root: Path) -> LongPlan:
    output_root = output_root.expanduser().resolve()
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"long B1 output root must be fresh: {output_root}")
    selection = validate_selection_manifest()
    runtime = p2.validate_runtime_repository(RUNTIME_REPOSITORY)
    if runtime.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise LongTrainingBlocked("long B1 runtime is not the sealed c18 commit")
    teacher = p2.validate_teacher_triplet()
    source_snapshot = capture_source_snapshot()
    branch_root = output_root / "b1"
    common_root = output_root / "common_init"
    overrides = build_long_overrides(branch_root, common_root)
    config = p2.compose_training_config(overrides)
    _validate_long_config(config)
    command = _build_child_command(
        branch_root=branch_root,
        common_root=common_root,
        overrides=overrides,
    )
    return LongPlan(
        output_root,
        branch_root,
        common_root,
        selection,
        teacher,
        runtime,
        overrides,
        command,
        source_snapshot,
    )


def _build_child_command(*, branch_root: Path, common_root: Path, overrides: tuple[str, ...]) -> tuple[str, ...]:
    return (
        sys.executable,
        str(Path(__file__).resolve()),
        "--execute-child",
        "--branch=b1",
        f"--runtime-repository={RUNTIME_REPOSITORY}",
        f"--overlay-repository={REPO_ROOT}",
        f"--selection-manifest={SELECTION_MANIFEST}",
        f"--branch-root={branch_root.expanduser().resolve()}",
        f"--common-root={common_root.expanduser().resolve()}",
        f"--teacher-actor-path={TEACHER_CHECKPOINT}",
        f"--teacher-config-path={TEACHER_CONFIG}",
        f"--teacher-manifest-path={TEACHER_MANIFEST}",
        "--",
        *overrides,
    )


def _validate_gpu_telemetry(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return p2.validate_gpu_telemetry(payload)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise LongTrainingBlocked(f"long B1 GPU telemetry failed the exact P2 contract: {exc}") from exc


def _finite_checkpoint_value(value: Any, name: str) -> None:
    import torch

    if isinstance(value, float) and not math.isfinite(value):
        raise LongTrainingBlocked(f"long B1 checkpoint contains non-finite scalar: {name}")
    if torch.is_tensor(value):
        if torch.is_floating_point(value) and not bool(torch.isfinite(value).all().item()):
            raise LongTrainingBlocked(f"long B1 checkpoint contains non-finite tensor: {name}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _finite_checkpoint_value(child, f"{name}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _finite_checkpoint_value(child, f"{name}[{index}]")


def _confined_checkpoint_path(path: Path, root: Path) -> Path:
    """Resolve one checkpoint path while refusing symlinks and escapes."""
    raw_path = Path(path).expanduser()
    if raw_path.is_symlink():
        raise LongTrainingBlocked(f"long B1 checkpoint symlink is forbidden: {raw_path}")
    try:
        resolved = raw_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise LongTrainingBlocked(f"long B1 checkpoint is missing: {raw_path}") from exc
    root = root.expanduser().resolve(strict=True)
    if not resolved.is_relative_to(root) or resolved.is_symlink() or not resolved.is_file():
        raise LongTrainingBlocked(f"long B1 checkpoint is not a confined regular file: {resolved}")
    return resolved


def _validate_final_optimizer_state(
    value: Any,
    *,
    step0_optimizer_schema: Mapping[str, Any],
    active_parameter_schema: Mapping[str, Any],
    expected_optimizer_state_step: int,
    torch_module: Any,
) -> int:
    """Validate final AdamW state against step-zero schema without P2's 500-step constant."""
    if not isinstance(value, Mapping) or set(value) != {"state", "param_groups"}:
        raise LongTrainingBlocked("long B1 final optimizer state must contain exactly state and param_groups")
    states = value["state"]
    groups = value["param_groups"]
    expected_groups = step0_optimizer_schema.get("param_groups")
    if not isinstance(states, Mapping) or not states:
        raise LongTrainingBlocked("long B1 final optimizer state must be non-empty")
    if not isinstance(expected_groups, list) or not expected_groups or not isinstance(groups, list):
        raise LongTrainingBlocked("long B1 final optimizer parameter groups are malformed")
    if len(groups) != len(expected_groups):
        raise LongTrainingBlocked("long B1 final optimizer parameter-group count drifted")

    parameter_ids: list[int] = []
    active_ids = p2._validate_active_parameter_schema(
        active_parameter_schema,
        step0_optimizer_schema=step0_optimizer_schema,
    )["parameter_ids"]
    amsgrad_ids: set[int] = set()
    for group_index, (group, expected_group) in enumerate(zip(groups, expected_groups, strict=True)):
        if not isinstance(expected_group, Mapping):
            raise LongTrainingBlocked(f"long B1 step0 optimizer group {group_index} is malformed")
        expected_hyperparameters = expected_group.get("hyperparameters")
        if not isinstance(expected_hyperparameters, Mapping) or not isinstance(group, Mapping):
            raise LongTrainingBlocked(f"long B1 final optimizer group {group_index} is malformed")
        expected_fields = {"params", *expected_hyperparameters}
        if set(group) != expected_fields:
            raise LongTrainingBlocked(f"long B1 final optimizer group {group_index} has missing/decoy fields")
        params = group.get("params")
        if not isinstance(params, list) or not params or any(
            isinstance(parameter_id, bool) or not isinstance(parameter_id, int) for parameter_id in params
        ):
            raise LongTrainingBlocked(f"long B1 final optimizer group {group_index} params are malformed")
        if params != expected_group.get("parameter_ids"):
            raise LongTrainingBlocked(f"long B1 final optimizer group {group_index} membership/order drifted")
        actual_hyperparameters = {key: group[key] for key in expected_hyperparameters}
        if p2._p2_normalize_optimizer_value(actual_hyperparameters) != p2._p2_normalize_optimizer_value(expected_hyperparameters):
            raise LongTrainingBlocked(f"long B1 final optimizer group {group_index} hyperparameters drifted")
        parameter_ids.extend(params)
        if group.get("amsgrad") is True:
            amsgrad_ids.update(params)
    if len(set(parameter_ids)) != len(parameter_ids):
        raise LongTrainingBlocked("long B1 final optimizer parameter IDs repeat")
    expected_parameter_ids = [item["id"] for item in step0_optimizer_schema.get("ordered_parameters", [])]
    if parameter_ids != [item for group in expected_groups for item in group.get("parameter_ids", [])]:
        raise LongTrainingBlocked("long B1 final optimizer group order does not bind step0")
    if set(parameter_ids) != set(expected_parameter_ids):
        raise LongTrainingBlocked("long B1 final optimizer groups do not cover step0 parameters")
    state_ids = list(states)
    if any(isinstance(parameter_id, bool) or not isinstance(parameter_id, int) for parameter_id in state_ids):
        raise LongTrainingBlocked("long B1 final optimizer state IDs must be integer/non-bool")
    if set(states) != set(active_ids):
        raise LongTrainingBlocked("long B1 final optimizer state IDs do not match the observed BC-active set")
    parameter_schema_by_id = {item["id"]: item for item in step0_optimizer_schema["ordered_parameters"]}
    for parameter_id in active_ids:
        state = states[parameter_id]
        if parameter_id not in parameter_schema_by_id:
            raise LongTrainingBlocked(f"long B1 final optimizer state ID is untrusted: {parameter_id!r}")
        if not isinstance(state, Mapping):
            raise LongTrainingBlocked(f"long B1 final optimizer state {parameter_id!r} is malformed")
        required_fields = {"step", "exp_avg", "exp_avg_sq"}
        if parameter_id in amsgrad_ids:
            required_fields.add("max_exp_avg_sq")
        if set(state) != required_fields:
            raise LongTrainingBlocked(f"long B1 final optimizer state {parameter_id!r} has missing/decoy fields")
        step = state["step"]
        if not torch_module.is_tensor(step) or not torch_module.is_floating_point(step) or step.numel() != 1:
            raise LongTrainingBlocked(f"long B1 final optimizer step {parameter_id!r} must be a floating scalar tensor")
        if not bool(torch_module.isfinite(step).all().item()) or float(step.item()) != expected_optimizer_state_step:
            raise LongTrainingBlocked(
                f"long B1 final optimizer step {parameter_id!r} must equal {expected_optimizer_state_step}"
            )
        expected_parameter = parameter_schema_by_id[parameter_id]
        expected_shape = tuple(expected_parameter["shape"])
        expected_dtype = expected_parameter["dtype"]
        for field in required_fields - {"step"}:
            moment = state[field]
            if not torch_module.is_tensor(moment) or moment.layout != torch_module.strided or moment.numel() <= 0:
                raise LongTrainingBlocked(f"long B1 final optimizer {parameter_id!r}.{field} is empty/non-strided")
            if (torch_module.is_floating_point(moment) or torch_module.is_complex(moment)) and not bool(
                torch_module.isfinite(moment).all().item()
            ):
                raise LongTrainingBlocked(f"long B1 final optimizer {parameter_id!r}.{field} is non-finite")
            if tuple(moment.shape) != expected_shape or str(moment.dtype) != expected_dtype:
                raise LongTrainingBlocked(f"long B1 final optimizer {parameter_id!r}.{field} shape/dtype drifted")
    return len(states)


def _validate_final_checkpoint_snapshot(
    path: Path,
    expected_step: int,
    *,
    root: Path,
    step0_manifest: Mapping[str, Any],
    active_parameter_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the final checkpoint from one immutable byte snapshot only."""
    import torch

    path = _confined_checkpoint_path(path, root)
    try:
        payload_bytes, checkpoint_sha256 = p2.read_immutable_snapshot(path)
        payload = torch.load(io.BytesIO(payload_bytes), map_location="cpu", weights_only=False)
    except BaseException as exc:
        raise LongTrainingBlocked(f"long B1 final checkpoint could not be loaded: {path}") from exc
    if not isinstance(payload, Mapping):
        raise LongTrainingBlocked(f"long B1 final checkpoint must be a mapping: {path}")
    required = ("policy_state_dict", "value_state_dict", "optimizer_state_dict", "lr_scheduler_state_dict", "state")
    missing = [key for key in required if key not in payload]
    if missing:
        raise LongTrainingBlocked(f"long B1 final checkpoint is missing required fields: {missing}")
    try:
        policy_schema = p2._validate_state_schema(step0_manifest.get("policy_state_schema"), name="step0.policy_state_schema")
        value_schema = p2._validate_state_schema(step0_manifest.get("value_state_schema"), name="step0.value_state_schema")
        optimizer_schema = p2._validate_p2_optimizer_schema(
            step0_manifest.get("optimizer_parameter_schema"),
            step0_manifest.get("scheduler_schema"),
            policy_schema=policy_schema,
            value_schema=value_schema,
        )
        p2._validate_checkpoint_state_mapping(
            payload["policy_state_dict"], name="policy_state_dict", schema=policy_schema, torch_module=torch
        )
        p2._validate_checkpoint_state_mapping(
            payload["value_state_dict"], name="value_state_dict", schema=value_schema, torch_module=torch
        )
        optimizer_count = _validate_final_optimizer_state(
            payload["optimizer_state_dict"],
            step0_optimizer_schema=optimizer_schema,
            active_parameter_schema=active_parameter_schema,
            expected_optimizer_state_step=EXPECTED_EXPECTED_OPTIMIZER_STATE_STEP,
            torch_module=torch,
        )
        scheduler_schema = step0_manifest["scheduler_schema"]["state_dict"]
        scheduler = payload["lr_scheduler_state_dict"]
        if not isinstance(scheduler, Mapping) or set(scheduler) != set(scheduler_schema):
            raise LongTrainingBlocked("long B1 final scheduler state has missing/decoy fields")
        group_count = len(optimizer_schema["param_groups"])
        if scheduler.get("base_lrs") != scheduler_schema.get("base_lrs") or scheduler.get("_last_lr") != scheduler_schema.get("_last_lr"):
            raise LongTrainingBlocked("long B1 final scheduler learning rates drifted from step0")
        if scheduler.get("last_epoch") != expected_step or scheduler.get("_step_count") != expected_step + 1:
            raise LongTrainingBlocked("long B1 final scheduler step state drifted")
        if scheduler.get("_get_lr_called_within_step") is not False or scheduler.get("lr_lambdas") != [None] * group_count:
            raise LongTrainingBlocked("long B1 final scheduler state contains decoys")
        state = payload["state"]
        state_step = state.get("global_step") if isinstance(state, Mapping) else getattr(state, "global_step", None)
        if isinstance(state_step, bool) or not isinstance(state_step, int) or state_step != expected_step:
            raise LongTrainingBlocked(f"long B1 final checkpoint global_step drifted at {expected_step}: {path}")
        tensor_count = p2._validate_finite_tensors(payload, name="checkpoint", torch_module=torch)
        if tensor_count <= 0:
            raise LongTrainingBlocked("long B1 final checkpoint contains no tensor payload")
    except LongTrainingBlocked:
        raise
    except BaseException as exc:
        raise LongTrainingBlocked(f"long B1 final checkpoint schema validation failed: {path}") from exc
    return {
        "path": str(path),
        "sha256": checkpoint_sha256,
        "size": len(payload_bytes),
        "global_step": expected_step,
        "tensor_count": tensor_count,
        "policy_key_count": len(policy_schema["keys"]),
        "value_key_count": len(value_schema["keys"]),
        "optimizer_state_count": optimizer_count,
        "active_parameter_count": active_parameter_schema["parameter_count"],
    }


def _validate_checkpoint(
    path: Path,
    expected_step: int,
    *,
    final: bool,
    root: Path,
    step0_manifest: Mapping[str, Any] | None = None,
    active_parameter_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    import torch

    path = _confined_checkpoint_path(path, root)
    if final:
        if step0_manifest is None or active_parameter_schema is None:
            raise LongTrainingBlocked("long B1 final checkpoint requires finalized step0 and active schemas")
        return _validate_final_checkpoint_snapshot(
            path,
            expected_step,
            root=root,
            step0_manifest=step0_manifest,
            active_parameter_schema=active_parameter_schema,
        )
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except BaseException as exc:
        raise LongTrainingBlocked(f"long B1 checkpoint could not be loaded: {path}") from exc
    if not isinstance(payload, Mapping):
        raise LongTrainingBlocked(f"long B1 checkpoint must be a mapping: {path}")
    state = payload.get("state")
    state_step = state.get("global_step") if isinstance(state, Mapping) else getattr(state, "global_step", None)
    if isinstance(state_step, bool) or not isinstance(state_step, int) or state_step != expected_step:
        raise LongTrainingBlocked(f"long B1 checkpoint global_step drifted at {expected_step}: {path}")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
        "global_step": expected_step,
    }


def _validate_long_evidence(plan: LongPlan, telemetry: Mapping[str, Any]) -> dict[str, Any]:
    root = plan.output_root.resolve(strict=True)
    branch_root = _confined(plan.branch_root, root, "B1 branch root")
    if not branch_root.is_dir() or branch_root.is_symlink():
        raise LongTrainingBlocked("long B1 branch root is not a real directory")
    proof_path = _confined(branch_root / PROOF_FILENAME, root, "completion proof")
    metrics_path = _confined(branch_root / METRICS_FILENAME, root, "runtime metrics")
    proof = _read_json(proof_path)
    metrics = _read_json(metrics_path)
    if proof.get("schema") != "a2_cb2h_pro_p2_pre_teardown_completion_v1" or metrics.get("schema") != p2.P2_RUNTIME_METRICS_SCHEMA:
        raise LongTrainingBlocked("long B1 proof/metrics schema drifted")
    proof_unsigned = dict(proof)
    proof_digest = proof_unsigned.pop("manifest_content_sha256", None)
    if proof_digest != sha256_bytes(canonical_json(proof_unsigned).encode("utf-8")):
        raise LongTrainingBlocked("long B1 completion proof content hash drifted")
    metrics_unsigned = dict(metrics)
    metrics_digest = metrics_unsigned.pop("content_sha256", None)
    if metrics_digest != sha256_bytes(canonical_json(metrics_unsigned).encode("utf-8")):
        raise LongTrainingBlocked("long B1 runtime metrics content hash drifted")
    for payload, label in ((proof, "proof"), (metrics, "metrics")):
        if payload.get("target_global_step") != EXPECTED_TARGET_GLOBAL_STEP or payload.get("completed_iterations") != EXPECTED_TARGET_GLOBAL_STEP:
            raise LongTrainingBlocked(f"long B1 {label} target/completion drifted")
        if payload.get("lifecycle_status") not in (None, "UNRESOLVED"):
            raise LongTrainingBlocked(f"long B1 {label} natural lifecycle status drifted")
    if proof.get("controlled_post_training_exit") is not True or metrics.get("lifecycle") != {"natural": False, "status": "UNRESOLVED", "controlled": True}:
        raise LongTrainingBlocked("long B1 controlled/unresolved lifecycle proof drifted")
    expected_runtime = {"runtime_repository": str(RUNTIME_REPOSITORY), "runtime_commit": EXPECTED_RUNTIME_COMMIT}
    if proof.get("runtime") != expected_runtime or metrics.get("runtime") != expected_runtime:
        raise LongTrainingBlocked("long B1 runtime identity drifted")
    if proof.get("callback_step_end_count") != EXPECTED_TARGET_GLOBAL_STEP or metrics.get("callback_step_end_count") != EXPECTED_TARGET_GLOBAL_STEP:
        raise LongTrainingBlocked("long B1 callback count drifted")
    if proof.get("observed_global_steps") != list(range(1, EXPECTED_TARGET_GLOBAL_STEP + 1)):
        raise LongTrainingBlocked("long B1 observed global-step sequence drifted")
    expected_scheduler = {"step_count": EXPECTED_TARGET_GLOBAL_STEP + 1, "last_epoch": EXPECTED_TARGET_GLOBAL_STEP}
    if proof.get("scheduler") not in (None, expected_scheduler) or metrics.get("scheduler") != expected_scheduler:
        raise LongTrainingBlocked("long B1 scheduler terminal state drifted")
    for payload, label in ((proof, "proof"), (metrics, "metrics")):
        if payload.get("backward_call_count") != EXPECTED_EXPECTED_OPTIMIZER_STATE_STEP or payload.get("optimizer_step_count") != EXPECTED_EXPECTED_OPTIMIZER_STATE_STEP:
            raise LongTrainingBlocked(f"long B1 {label} optimizer/backward count drifted")
    active_parameter_schema = proof.get("active_parameter_schema")
    if not isinstance(active_parameter_schema, Mapping):
        raise LongTrainingBlocked("long B1 proof active-parameter schema is missing")
    if "active_parameter_schema" in metrics and metrics.get("active_parameter_schema") != active_parameter_schema:
        raise LongTrainingBlocked("long B1 metrics active-parameter schema disagrees with proof")
    step0_path = _confined(root / "common_init/b1_step0_manifest.json", root, "step0 manifest")
    try:
        step0_manifest, step0_sha256, step0_size = p2.load_json_snapshot(step0_path)
        policy_schema = p2._validate_state_schema(step0_manifest.get("policy_state_schema"), name="step0.policy_state_schema")
        value_schema = p2._validate_state_schema(step0_manifest.get("value_state_schema"), name="step0.value_state_schema")
        p2._validate_p2_optimizer_schema(
            step0_manifest.get("optimizer_parameter_schema"),
            step0_manifest.get("scheduler_schema"),
            policy_schema=policy_schema,
            value_schema=value_schema,
        )
    except BaseException as exc:
        raise LongTrainingBlocked("long B1 finalized step0 schema is invalid") from exc
    checkpoint_refs = {}
    for step in range(EXPECTED_SAVE_FREQUENCY, EXPECTED_TARGET_GLOBAL_STEP + 1, EXPECTED_SAVE_FREQUENCY):
        checkpoint_refs[str(step)] = _validate_checkpoint(
            branch_root / f"model_step_{step:06d}.pt",
            step,
            final=step == EXPECTED_TARGET_GLOBAL_STEP,
            root=branch_root,
            step0_manifest=step0_manifest if step == EXPECTED_TARGET_GLOBAL_STEP else None,
            active_parameter_schema=active_parameter_schema if step == EXPECTED_TARGET_GLOBAL_STEP else None,
        )
    final_ref = proof.get("final_checkpoint")
    if not isinstance(final_ref, Mapping):
        raise LongTrainingBlocked("long B1 proof final checkpoint reference is missing")
    if (
        final_ref.get("path") != checkpoint_refs["8000"]["path"]
        or final_ref.get("sha256") != checkpoint_refs["8000"]["sha256"]
        or final_ref.get("global_step") != EXPECTED_TARGET_GLOBAL_STEP
        or ("size" in final_ref and final_ref.get("size") != checkpoint_refs["8000"]["size"])
    ):
        raise LongTrainingBlocked("long B1 proof final checkpoint reference drifted")
    final_config = _artifact_ref(branch_root / "config.yaml", root, "final config")
    common_artifact = _artifact_ref(root / "common_init/b1_common_init.pt", root, "common-init artifact")
    step0_manifest_ref = {"path": str(step0_path), "sha256": step0_sha256, "size": step0_size}
    for payload, key, expected in (
        (proof, "final_config", final_config),
        (proof, "common_init_artifact", common_artifact),
        (proof, "step0_manifest", step0_manifest_ref),
    ):
        reference = payload.get(key)
        if not isinstance(reference, Mapping) or reference.get("path") != expected["path"] or reference.get("sha256") != expected["sha256"]:
            raise LongTrainingBlocked(f"long B1 proof {key} reference drifted")
    selection_now = validate_selection_manifest(plan.selection.path)
    if selection_now.file_sha256 != plan.selection.file_sha256 or selection_now.content_sha256 != plan.selection.content_sha256:
        raise LongTrainingBlocked("selected B1 adjudication changed during long run")
    teacher_now = p2.validate_teacher_triplet()
    if teacher_now != plan.teacher:
        raise LongTrainingBlocked("Teacher triplet changed during long run")
    runtime_now = p2.validate_runtime_repository(RUNTIME_REPOSITORY)
    if runtime_now != plan.runtime:
        raise LongTrainingBlocked("c18 runtime repository changed during long run")
    source_now = capture_source_snapshot()
    if source_now != plan.source_snapshot:
        raise LongTrainingBlocked("overlay source candidate changed during long run")
    return {
        "proof": _artifact_ref(proof_path, root, "completion proof"),
        "metrics": _artifact_ref(metrics_path, root, "runtime metrics"),
        "final_config": final_config,
        "common_init": common_artifact,
        "step0_manifest": step0_manifest_ref,
        "checkpoints": checkpoint_refs,
        "selection": selection_now.as_dict(),
        "teacher": teacher_now,
        "runtime": runtime_now,
        "source_snapshot": source_now,
        "active_parameter_schema": dict(active_parameter_schema),
        "expected_optimizer_state_step": EXPECTED_EXPECTED_OPTIMIZER_STATE_STEP,
        "telemetry": dict(telemetry),
    }


def _live_state_payload(
    *,
    status: str,
    child_pid: int,
    child_pgid: int,
    child_sid: int,
    process_started_ns: int,
    stdout_path: Path,
    stderr_path: Path,
    telemetry_stream_path: Path,
    marker_reader: CanonicalMarkerReader,
    sampler: BoundedGpuTelemetrySampler,
    returncode: int | None = None,
    monitor_error: BaseException | None = None,
) -> dict[str, Any]:
    if status not in {"RUNNING", "MONITOR_ERROR_WAITING_CHILD", "EXITED"}:
        raise ValueError(f"long B1 live state status is invalid: {status!r}")
    return {
        "schema": LIVE_STATE_SCHEMA,
        "status": status,
        "child_pid": child_pid,
        "child_pgid": child_pgid,
        "child_session_id": child_sid,
        "process_start_time_ns": process_started_ns,
        "returncode": returncode,
        "last_observed": marker_reader.snapshot(),
        "telemetry": sampler.snapshot(),
        "logs": {
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "telemetry_jsonl": str(telemetry_stream_path),
        },
        "monitor_error": None
        if monitor_error is None
        else {"type": type(monitor_error).__name__, "message": str(monitor_error)},
    }


def _launch_child(
    plan: LongPlan,
    environment: Mapping[str, str],
    stdout_stream,
    stderr_stream,
) -> tuple[subprocess.Popen, int, int, int]:
    """Launch one discrete session and return exact PID/PGID/session provenance."""
    process = subprocess.Popen(
        list(plan.command),
        cwd=str(REPO_ROOT),
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=stdout_stream,
        stderr=stderr_stream,
        start_new_session=True,
        close_fds=True,
    )
    child_pid = int(process.pid)
    if child_pid <= 0:
        raise LongTrainingBlocked(f"long B1 child PID is invalid: {child_pid}")
    try:
        child_pgid = int(os.getpgid(child_pid))
        child_sid = int(os.getsid(child_pid))
    except OSError as exc:
        error = LongTrainingBlocked(
            f"long B1 child process-group provenance is unavailable: pid={child_pid}"
        )
        error.process = process
        raise error from exc
    if child_pgid != child_pid or child_sid != child_pid:
        error = LongTrainingBlocked(
            "long B1 child must own a discrete session/process group: "
            f"pid={child_pid} pgid={child_pgid} sid={child_sid}"
        )
        error.process = process
        raise error
    return process, child_pid, child_pgid, child_sid


def _monitor_child(
    process: subprocess.Popen,
    *,
    live_state_path: Path,
    child_pid: int,
    child_pgid: int,
    child_sid: int,
    process_started_ns: int,
    stdout_path: Path,
    stderr_path: Path,
    telemetry_stream_path: Path,
    marker_reader: CanonicalMarkerReader,
    sampler: BoundedGpuTelemetrySampler,
) -> tuple[int, BaseException | None]:
    """Poll a live child and then wait naturally; never TERM/KILL it."""
    monitor_error: BaseException | None = None
    last_state_signature: str | None = None
    while process.poll() is None:
        try:
            marker_reader.poll()
            sampler.raise_if_failed()
            running_state = _live_state_payload(
                status="RUNNING",
                child_pid=child_pid,
                child_pgid=child_pgid,
                child_sid=child_sid,
                process_started_ns=process_started_ns,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                telemetry_stream_path=telemetry_stream_path,
                marker_reader=marker_reader,
                sampler=sampler,
            )
            state_signature = canonical_json(
                {"last_observed": running_state["last_observed"], "telemetry": running_state["telemetry"]}
            )
            if state_signature != last_state_signature:
                _replace_json(live_state_path, running_state)
                last_state_signature = state_signature
        except BaseException as exc:
            monitor_error = exc
            # Publish the monitor failure before waiting for natural child
            # termination.  This state is intentionally mutable/replaceable
            # and preserves PID/PGID/log/telemetry provenance for observers.
            _replace_json(
                live_state_path,
                _live_state_payload(
                    status="MONITOR_ERROR_WAITING_CHILD",
                    child_pid=child_pid,
                    child_pgid=child_pgid,
                    child_sid=child_sid,
                    process_started_ns=process_started_ns,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    telemetry_stream_path=telemetry_stream_path,
                    marker_reader=marker_reader,
                    sampler=sampler,
                    monitor_error=monitor_error,
                ),
            )
            break
        time.sleep(_MARKER_POLL_INTERVAL_S)
    returncode = int(process.wait())
    try:
        marker_reader.poll()
    except BaseException as exc:
        if monitor_error is None:
            monitor_error = exc
    _replace_json(
        live_state_path,
        _live_state_payload(
            status="EXITED",
            child_pid=child_pid,
            child_pgid=child_pgid,
            child_sid=child_sid,
            process_started_ns=process_started_ns,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            telemetry_stream_path=telemetry_stream_path,
            marker_reader=marker_reader,
            sampler=sampler,
            returncode=returncode,
            monitor_error=monitor_error,
        ),
    )
    return returncode, monitor_error


def _load_telemetry_stream(
    stream_path: Path,
    *,
    process_started_ns: int,
    process_ended_ns: int,
) -> dict[str, Any]:
    """Materialize the finite terminal stream only after the child has exited."""
    terminal_rows: list[dict[str, Any]] = []
    with stream_path.open("rb") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                raise LongTrainingBlocked(f"long B1 telemetry JSONL contains a blank line at {line_number}")
            try:
                row = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LongTrainingBlocked(f"long B1 telemetry JSONL row {line_number} is invalid") from exc
            if not isinstance(row, Mapping):
                raise LongTrainingBlocked(f"long B1 telemetry JSONL row {line_number} is not an object")
            terminal_rows.append(dict(row))
    if not terminal_rows:
        raise LongTrainingBlocked("long B1 telemetry JSONL stream is empty")
    try:
        peak_vram_mib = max(float(row["memory_used_mib"]) for row in terminal_rows)
    except (KeyError, TypeError, ValueError) as exc:
        raise LongTrainingBlocked("long B1 telemetry JSONL rows are missing memory_used_mib") from exc
    payload = {
        "schema": p2.P2_TELEMETRY_SCHEMA,
        "record_count": len(terminal_rows),
        "records": terminal_rows,
        "peak_vram_mib": peak_vram_mib,
        "process_started_ns": process_started_ns,
        "process_ended_ns": process_ended_ns,
        "sample_interval_s": 5.0,
        "max_adjacent_gap_s": p2.P2_TELEMETRY_MAX_ADJACENT_GAP_S,
        "gpu_identity": {
            "physical_gpu_index": p2.EXPECTED_GPU_INDEX,
            "logical_gpu_index": int(p2.EXPECTED_LOGICAL_GPU_INDEX),
            "logical_device": "cuda:0",
            "uuid": p2.EXPECTED_GPU_UUID,
            "cuda_visible_devices": p2.EXPECTED_GPU_INDEX,
            "cuda_device_order": p2.EXPECTED_CUDA_DEVICE_ORDER,
            "binding_mode": p2.EXPECTED_GPU_BINDING_MODE,
            "world_size": 1,
        },
    }
    try:
        return _validate_gpu_telemetry(payload)
    except BaseException as exc:
        raise LongTrainingBlocked("long B1 telemetry stream failed the exact P2 validation") from exc


def _write_failure(root: Path, error: BaseException, *, returncode: int | None = None) -> None:
    path = root / FAILURE_FILENAME
    if path.is_symlink():
        raise FileExistsError(f"long failure seal refuses symlink: {path}")
    if path.exists():
        return
    _atomic_json(
        path,
        {
            "schema": FAILURE_SCHEMA,
            "root": str(root),
            "returncode": returncode,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "final_manifest_sealed": False,
        },
    )


def _seal_telemetry(
    *,
    output_root: Path,
    telemetry_stream_path: Path,
    process_started_ns: int,
    process_ended_ns: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    telemetry = _load_telemetry_stream(
        telemetry_stream_path,
        process_started_ns=process_started_ns,
        process_ended_ns=process_ended_ns,
    )
    telemetry_ref = _atomic_json(output_root / TELEMETRY_FILENAME, telemetry)
    stream_ref = _artifact_ref(telemetry_stream_path, output_root, "telemetry JSONL stream")
    return telemetry, telemetry_ref, stream_ref


def execute_long_plan(plan: LongPlan) -> dict[str, Any]:
    output_root = plan.output_root
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"long B1 output root must remain fresh: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir()
    _atomic_json(output_root / PLAN_FILENAME, plan.as_dict())

    stdout_stream = stderr_stream = telemetry_stream = None
    stdout_path = stderr_path = telemetry_stream_path = None
    process: subprocess.Popen | None = None
    marker_reader: CanonicalMarkerReader | None = None
    sampler: BoundedGpuTelemetrySampler | None = None
    sampler_started = False
    sampler_stopped = False
    process_started_ns: int | None = None
    process_ended_ns: int | None = None
    child_pid = child_pgid = child_sid = None
    returncode: int | None = None
    monitor_error: BaseException | None = None
    telemetry: dict[str, Any] | None = None
    telemetry_ref: dict[str, Any] | None = None
    telemetry_stream_ref: dict[str, Any] | None = None

    try:
        # These canonical destinations are created before launch and passed
        # directly to Popen; the parent never captures an unbounded stream.
        stdout_stream, stdout_path = _open_exclusive_binary(output_root / STDOUT_FILENAME)
        stderr_stream, stderr_path = _open_exclusive_binary(output_root / STDERR_FILENAME)
        telemetry_stream, telemetry_stream_path = _open_exclusive_binary(
            output_root / TELEMETRY_STREAM_FILENAME
        )
        environment = p2.build_child_environment()
        sampler = BoundedGpuTelemetrySampler(environment, telemetry_stream, telemetry_stream_path)
        sampler.sample_once()
        process, child_pid, child_pgid, child_sid = _launch_child(
            plan, environment, stdout_stream, stderr_stream
        )
        process_started_ns = time.time_ns()
        marker_reader = CanonicalMarkerReader(stdout_path)
        sampler.start()
        sampler_started = True
        _replace_json(
            output_root / LIVE_STATE_FILENAME,
            _live_state_payload(
                status="RUNNING",
                child_pid=child_pid,
                child_pgid=child_pgid,
                child_sid=child_sid,
                process_started_ns=process_started_ns,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                telemetry_stream_path=telemetry_stream_path,
                marker_reader=marker_reader,
                sampler=sampler,
            ),
        )
        returncode, monitor_error = _monitor_child(
            process,
            live_state_path=output_root / LIVE_STATE_FILENAME,
            child_pid=child_pid,
            child_pgid=child_pgid,
            child_sid=child_sid,
            process_started_ns=process_started_ns,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            telemetry_stream_path=telemetry_stream_path,
            marker_reader=marker_reader,
            sampler=sampler,
        )
        process_ended_ns = time.time_ns()
        sampler.stop(process_started_ns=process_started_ns, process_ended_ns=process_ended_ns)
        sampler_stopped = True
        sampler.close()
        marker_reader.poll()
        _replace_json(
            output_root / LIVE_STATE_FILENAME,
            _live_state_payload(
                status="EXITED",
                child_pid=child_pid,
                child_pgid=child_pgid,
                child_sid=child_sid,
                process_started_ns=process_started_ns,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                telemetry_stream_path=telemetry_stream_path,
                marker_reader=marker_reader,
                sampler=sampler,
                returncode=returncode,
                monitor_error=monitor_error,
            ),
        )
        telemetry, telemetry_ref, telemetry_stream_ref = _seal_telemetry(
            output_root=output_root,
            telemetry_stream_path=telemetry_stream_path,
            process_started_ns=process_started_ns,
            process_ended_ns=process_ended_ns,
        )
        marker_reader.close()
        marker_reader = None
        _flush_log(stdout_stream)
        _flush_log(stderr_stream)
        stdout_stream.close()
        stderr_stream.close()
        stdout_stream = stderr_stream = None
        if monitor_error is not None:
            raise LongTrainingBlocked("long B1 live monitor failed") from monitor_error
        if returncode != 0:
            raise LongTrainingBlocked(f"long B1 child returned nonzero status: {returncode}")
        terminal_live_state = _read_json(output_root / LIVE_STATE_FILENAME)
        if (
            terminal_live_state.get("status") != "EXITED"
            or terminal_live_state.get("last_observed", {}).get("marker_count", 0) < 1
        ):
            raise LongTrainingBlocked("long B1 terminal live state lacks canonical rollout-marker evidence")
        evidence = _validate_long_evidence(plan, telemetry)
        evidence["telemetry_artifacts"] = {"sealed": telemetry_ref, "stream": telemetry_stream_ref}
        manifest = {
            "schema": LONG_SCHEMA,
            "operation": "cb2h_pro_b1_long_mixed_rollout",
            "decision": "TRAINING_COMPLETION_ONLY_DEFER_BOUNDARY_EVAL",
            "quality_pass": False,
            "output_root": str(output_root),
            "selection": plan.selection.as_dict(),
            "teacher": plan.teacher,
            "runtime": plan.runtime,
            "source_snapshot": plan.source_snapshot,
            "gpu_identity": p2._gpu_identity() if hasattr(p2, "_gpu_identity") else {
                "physical_gpu_index": EXPECTED_GPU_INDEX,
                "logical_gpu_index": int(EXPECTED_LOGICAL_GPU_INDEX),
                "logical_device": "cuda:0",
                "uuid": EXPECTED_GPU_UUID,
                "cuda_visible_devices": EXPECTED_GPU_INDEX,
                "cuda_device_order": EXPECTED_CUDA_DEVICE_ORDER,
                "binding_mode": EXPECTED_GPU_BINDING_MODE,
                "world_size": 1,
            },
            "architecture": EXPECTED_ARCHITECTURE,
            "schedule": [dict(item) for item in LONG_ROLLOUT_SCHEDULE],
            "target_global_step": EXPECTED_TARGET_GLOBAL_STEP,
            "save_frequency": EXPECTED_SAVE_FREQUENCY,
            "checkpoint_start": None,
            "common_init_mode": "fresh_create",
            "deferred_boundary_eval_scope": DEFERRED_BOUNDARY_EVAL_SCOPE,
            "command": list(plan.command),
            "stdout": _artifact_ref(output_root / STDOUT_FILENAME, output_root, "stdout"),
            "stderr": _artifact_ref(output_root / STDERR_FILENAME, output_root, "stderr"),
            # Preserve the R1 validated telemetry shape; artifact refs are
            # additive so downstream consumers keep reading record_count/
            # records while the immutable JSON and append-only stream are
            # explicitly discoverable.
            "telemetry": evidence["telemetry"],
            "telemetry_artifacts": {"artifact": telemetry_ref, "stream": telemetry_stream_ref},
            "live_state_path": str(output_root / LIVE_STATE_FILENAME),
            "evidence": evidence,
        }
        manifest["content_sha256"] = sha256_bytes(canonical_json(dict(manifest)).encode("utf-8"))
        return _atomic_json(output_root / FINAL_MANIFEST_FILENAME, manifest)
    except BaseException as exc:
        cleanup_error: BaseException | None = None
        # Never signal the child.  If an early monitor/launch error occurs,
        # wait for its natural exit and preserve the exact return code.
        if process is None:
            process = getattr(exc, "process", None)
        if process is not None and process.poll() is None:
            returncode = int(process.wait())
            process_ended_ns = time.time_ns()
        if process is not None and returncode is None:
            returncode = int(process.returncode)
            process_ended_ns = process_ended_ns or time.time_ns()
        if (
            process is not None
            and marker_reader is not None
            and child_pid is not None
            and child_pgid is not None
            and child_sid is not None
            and process_started_ns is not None
            and stdout_path is not None
            and stderr_path is not None
            and telemetry_stream_path is not None
            and sampler is not None
        ):
            try:
                marker_reader.poll()
                _replace_json(
                    output_root / LIVE_STATE_FILENAME,
                    _live_state_payload(
                        status="EXITED",
                        child_pid=child_pid,
                        child_pgid=child_pgid,
                        child_sid=child_sid,
                        process_started_ns=process_started_ns,
                        stdout_path=stdout_path,
                        stderr_path=stderr_path,
                        telemetry_stream_path=telemetry_stream_path,
                        marker_reader=marker_reader,
                        sampler=sampler,
                        returncode=returncode,
                        monitor_error=exc,
                    ),
                )
            except BaseException as state_error:
                cleanup_error = state_error
        if sampler is not None and sampler_started and not sampler_stopped:
            try:
                sampler.stop(
                    process_started_ns=process_started_ns or time.time_ns(),
                    process_ended_ns=process_ended_ns or time.time_ns(),
                )
                sampler_stopped = True
            except BaseException as stop_error:
                cleanup_error = stop_error
            finally:
                sampler.close()
            if (
                cleanup_error is None
                and telemetry is None
                and telemetry_stream_path is not None
                and process_started_ns is not None
                and process_ended_ns is not None
            ):
                try:
                    telemetry, telemetry_ref, telemetry_stream_ref = _seal_telemetry(
                        output_root=output_root,
                        telemetry_stream_path=telemetry_stream_path,
                        process_started_ns=process_started_ns,
                        process_ended_ns=process_ended_ns,
                    )
                except BaseException as seal_error:
                    cleanup_error = seal_error
        if marker_reader is not None:
            marker_reader.close()
        if process is None and stderr_stream is not None:
            _write_prelaunch_error(stderr_stream, exc)
        if stdout_stream is not None:
            _flush_log(stdout_stream)
            stdout_stream.close()
            stdout_stream = None
        if stderr_stream is not None:
            _flush_log(stderr_stream)
            stderr_stream.close()
            stderr_stream = None
        failure_error = cleanup_error or exc
        _write_failure(output_root, failure_error, returncode=returncode)
        if cleanup_error is not None:
            raise cleanup_error from exc
        raise
    finally:
        if marker_reader is not None:
            marker_reader.close()
        if sampler is not None and not getattr(sampler, "_closed", False):
            close_sampler = getattr(sampler, "close", None)
            if callable(close_sampler):
                close_sampler()
        if stdout_stream is not None:
            stdout_stream.close()
        if stderr_stream is not None:
            stderr_stream.close()
        if telemetry_stream is not None and not getattr(sampler, "_closed", False):
            telemetry_stream.close()


def _execute_child(args: argparse.Namespace, overrides: tuple[str, ...]) -> int:
    if args.branch != "b1":
        raise LongTrainingBlocked("long runner only supports selected branch b1")
    branch_root = args.branch_root.expanduser().resolve()
    common_root = args.common_root.expanduser().resolve()
    if branch_root.exists() or branch_root.is_symlink():
        raise FileExistsError(f"long B1 branch root must be fresh: {branch_root}")
    expected = build_long_overrides(branch_root, common_root)
    if overrides != expected:
        raise LongTrainingBlocked("long B1 child Hydra overrides differ from the exact generated contract")
    selection = validate_selection_manifest(args.selection_manifest)
    if selection.path != SELECTION_MANIFEST:
        raise LongTrainingBlocked("long B1 child selection path drifted")
    runtime = p2.validate_runtime_repository(args.runtime_repository)
    if runtime.get("commit") != EXPECTED_RUNTIME_COMMIT:
        raise LongTrainingBlocked("long B1 child runtime commit drifted")
    teacher = p2.validate_teacher_triplet()
    if (
        Path(args.teacher_actor_path).resolve() != TEACHER_CHECKPOINT.resolve()
        or Path(args.teacher_config_path).resolve() != TEACHER_CONFIG.resolve()
        or Path(args.teacher_manifest_path).resolve() != TEACHER_MANIFEST.resolve()
    ):
        raise LongTrainingBlocked("long B1 child Teacher path drifted")
    from gr00t.rl.scripts import run_a2_student_distillation_v19 as bootstrap

    environment = p2.build_child_environment()
    bootstrap.validate_gpu7_environment(environment)
    overlay = bootstrap.prepare_overlay_import(args.overlay_repository)
    module_sources = bootstrap.validate_runtime_repository(args.runtime_repository)
    bootstrap.validate_teacher_triplet(args.teacher_actor_path, args.teacher_config_path, args.teacher_manifest_path)
    bootstrap.install_v19_runtime_scenario_file_pin(module_sources)
    sys.meta_path.insert(0, bootstrap.V19RuntimeFinder(module_sources))
    train_entrypoint = overlay / "gr00t/rl/train_agent_trl.py"
    if not train_entrypoint.is_file():
        raise FileNotFoundError(f"long B1 training entrypoint is unavailable: {train_entrypoint}")
    os.environ.clear()
    os.environ.update(environment)
    os.chdir(overlay)
    sys.argv = [str(train_entrypoint), *overrides]
    runpy.run_path(str(train_entrypoint), run_name="__main__")
    proof = branch_root / PROOF_FILENAME
    if not proof.is_file():
        raise LongTrainingBlocked("long B1 child returned without completion proof")
    raise LongTrainingBlocked("long B1 controlled child returned instead of exiting after proof seal")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--execute-child", action="store_true")
    parser.add_argument("--branch", choices=("b1",), default="b1")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--runtime-repository", type=Path, default=RUNTIME_REPOSITORY)
    parser.add_argument("--overlay-repository", type=Path, default=REPO_ROOT)
    parser.add_argument("--selection-manifest", type=Path, default=SELECTION_MANIFEST)
    parser.add_argument("--branch-root", type=Path)
    parser.add_argument("--common-root", type=Path)
    parser.add_argument("--teacher-actor-path", type=Path, default=TEACHER_CHECKPOINT)
    parser.add_argument("--teacher-config-path", type=Path, default=TEACHER_CONFIG)
    parser.add_argument("--teacher-manifest-path", type=Path, default=TEACHER_MANIFEST)
    return parser


def parse_args(argv: Sequence[str] | None = None) -> tuple[argparse.Namespace, tuple[str, ...]]:
    parser = _parser()
    args, remaining = parser.parse_known_args(argv)
    if args.execute_child:
        required = (args.branch_root, args.common_root)
        if args.dry_run or args.execute or any(value is None for value in required):
            raise ValueError("long --execute-child requires branch/common roots and no mode flag")
        if remaining[:1] == ["--"]:
            remaining = remaining[1:]
        if not remaining:
            raise ValueError("long --execute-child requires exact Hydra overrides after --")
        return args, tuple(remaining)
    if remaining:
        raise ValueError(f"unexpected long launcher arguments: {remaining!r}")
    if args.output_root is None or args.dry_run == args.execute:
        raise ValueError("select exactly one of --dry-run or --execute with --output-root")
    return args, ()


def print_plan(plan: LongPlan) -> None:
    print(canonical_json(plan.as_dict()), flush=True)
    print("[A2_CB2H_PRO_B1_LONG_COMMAND]", flush=True)
    print(" ".join(plan.command), flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    args, remaining = parse_args(argv)
    if args.execute_child:
        return _execute_child(args, remaining)
    plan = build_long_plan(args.output_root)
    if args.dry_run:
        print_plan(plan)
        return 0
    result = execute_long_plan(plan)
    print(
        f"[A2_CB2H_PRO_B1_LONG_COMPLETE] manifest={result['path']} sha256={result['sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
