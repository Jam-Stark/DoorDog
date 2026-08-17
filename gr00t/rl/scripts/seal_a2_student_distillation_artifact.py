#!/usr/bin/env python3
"""Generate and verify a sealed A2 Student Distillation artifact ledger.

The sealer is deliberately CPU-only and import-safe: it imports no IsaacSim,
IsaacLab, Hydra, or project training modules.  Generation never overwrites an
existing ledger and verification only reads the ledger and referenced files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import torch


SCHEMA_VERSION = "a2_student_distillation_artifact_ledger.v1"
_CHECKPOINT_NAME_RE = re.compile(r"^model_step_(?P<step>[0-9]+)\.pt$")
_MISSING = object()
_IDENTITY_FIELDS = ("path", "sha256", "size", "mtime_ns")
_ARTIFACT_KEYS = (
    "final_checkpoint",
    "resolved_config",
    "teacher_checkpoint",
    "teacher_config",
    "teacher_manifest",
)
_TOP_LEVEL_KEYS = (
    "schema_version",
    "base_sha",
    "candidate_id",
    "source_root",
    "expected_global_step",
    "artifacts",
    "logs",
)


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_step(value: Any, label: str = "expected_global_step") -> int:
    if type(value) is not int or value < 0:  # noqa: E721 - exact bool/int contract
        raise ValueError(f"{label} must be a non-negative integer; got {value!r}")
    return value


def _reject_raw_parent_components(path: str | Path, label: str) -> Path:
    """Reject raw lexical ``..`` components before filesystem inspection."""
    candidate = Path(path)
    if ".." in candidate.parts:
        raise ValueError(f"{label} path contains unsupported parent component '..': {candidate}")
    return candidate


def _reject_symlink_components(path: str | Path, label: str) -> None:
    """Reject lexical symlink components before any path resolution."""
    # abspath applies lexical normpath semantics but does not resolve symlinks.
    candidate = _reject_raw_parent_components(path, label)
    normalized = Path(os.path.abspath(os.fspath(candidate)))
    current = Path(normalized.anchor)
    for part in normalized.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} path contains symlink component: {current}")
        if not current.exists():
            break


def _canonical_file(path: str | Path, label: str) -> Path:
    candidate = Path(path)
    _reject_symlink_components(candidate, label)
    if not candidate.is_file():
        raise FileNotFoundError(f"{label} does not exist or is not a regular file: {candidate}")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_file() or resolved.is_symlink():
        raise FileNotFoundError(f"{label} does not resolve to a regular file: {resolved}")
    return resolved


def _canonical_directory(path: str | Path, label: str) -> Path:
    candidate = Path(path)
    _reject_symlink_components(candidate, label)
    if not candidate.is_dir():
        raise FileNotFoundError(f"{label} does not exist or is not a directory: {candidate}")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_dir():
        raise FileNotFoundError(f"{label} does not resolve to a directory: {resolved}")
    return resolved


def sha256_file(path: str | Path) -> str:
    """Return the SHA256 digest of one file without loading it into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(
    path: str | Path, label: str, *, require_nonempty: bool = False
) -> dict[str, Any]:
    resolved = _canonical_file(path, label)
    stat = resolved.stat()
    if require_nonempty and stat.st_size <= 0:
        raise ValueError(f"{label} must be non-empty; got size={stat.st_size}")
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _reject_mutable_checkpoint(path: Path) -> None:
    if path.name == "last.pt" or path.name.endswith("_last.pt"):
        raise ValueError(f"Mutable checkpoint filename is forbidden: {path}")


def _checkpoint_filename_step(path: Path, expected_global_step: int) -> int:
    _reject_mutable_checkpoint(path)
    match = _CHECKPOINT_NAME_RE.fullmatch(path.name)
    if match is None:
        raise ValueError(
            "Final A2 Student checkpoint must be named model_step_<global_step>.pt; "
            f"got {path.name!r}"
        )
    filename_step = int(match.group("step"))
    if filename_step != expected_global_step:
        raise ValueError(
            "Final A2 Student checkpoint filename step does not match "
            f"--expected-global-step={expected_global_step}: got {filename_step}"
        )
    return filename_step


def _serialized_global_step(checkpoint: Mapping[str, Any], expected_global_step: int) -> int:
    state = checkpoint.get("state", _MISSING)
    if state is _MISSING:
        raise ValueError("Final A2 Student checkpoint is missing serialized state.global_step")
    if isinstance(state, Mapping):
        value = state.get("global_step", _MISSING)
    else:
        value = getattr(state, "global_step", _MISSING)
    if type(value) is not int:  # noqa: E721 - reject strings/tensors/coercive fallbacks
        raise ValueError(
            "Final A2 Student checkpoint state.global_step must be a serialized integer; "
            f"got {value!r}"
        )
    if value != expected_global_step:
        raise ValueError(
            "Final A2 Student checkpoint state.global_step does not match "
            f"--expected-global-step={expected_global_step}: got {value}"
        )
    return value


def _checkpoint_semantics(path: Path, expected_global_step: int) -> dict[str, int]:
    """Load and validate the real callback checkpoint schema on CPU."""
    _checkpoint_filename_step(path, expected_global_step)
    loaded = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(loaded, Mapping):
        raise ValueError(
            "Final A2 Student checkpoint must be a mapping; "
            f"got {type(loaded).__name__}"
        )

    policy = loaded.get("policy_state_dict", _MISSING)
    if not isinstance(policy, Mapping) or not policy:
        raise ValueError("Final A2 Student checkpoint policy_state_dict must be nonempty")
    policy_element_count = 0
    for key, tensor in policy.items():
        if not isinstance(tensor, torch.Tensor):
            raise ValueError(
                "Final A2 Student checkpoint policy_state_dict values must be tensors; "
                f"key={key!r} type={type(tensor).__name__}"
            )
        element_count = int(tensor.numel())
        if element_count <= 0:
            raise ValueError(
                "Final A2 Student checkpoint policy_state_dict tensors must be non-empty; "
                f"key={key!r}"
            )
        policy_element_count += element_count
        try:
            finite = torch.isfinite(tensor)
            all_finite = bool(torch.all(finite).item())
        except Exception as exc:
            raise ValueError(
                "Final A2 Student checkpoint policy_state_dict tensors must support "
                f"finite validation; key={key!r}"
            ) from exc
        if not all_finite:
            raise ValueError(
                "Final A2 Student checkpoint policy_state_dict contains non-finite values; "
                f"key={key!r}"
            )

    optimizer = loaded.get("optimizer_state_dict", _MISSING)
    if not isinstance(optimizer, Mapping):
        raise ValueError("Final A2 Student checkpoint optimizer_state_dict must be a mapping")
    optimizer_state = optimizer.get("state", _MISSING)
    if not isinstance(optimizer_state, Mapping) or not optimizer_state:
        raise ValueError(
            "Final A2 Student checkpoint optimizer_state_dict.state must be nonempty"
        )

    global_step = _serialized_global_step(loaded, expected_global_step)
    return {
        "global_step": global_step,
        "policy_tensor_count": len(policy),
        "policy_element_count": policy_element_count,
        "optimizer_state_entries": len(optimizer_state),
    }


def _normalize_log_paths(paths: Sequence[str | Path], label: str) -> list[Path]:
    if isinstance(paths, (str, bytes, Path)):
        raise TypeError(f"{label} must be a sequence of paths, not a single path")
    normalized = list(paths)
    if not normalized:
        raise ValueError(f"{label} must contain at least one log path")
    result = []
    for index, path in enumerate(normalized):
        canonical = _canonical_file(path, f"{label}[{index}]")
        if canonical.stat().st_size <= 0:
            raise ValueError(f"{label}[{index}] must be non-empty")
        result.append(canonical)
    return result


def _write_deterministic_json(output_path: str | Path, payload: Mapping[str, Any]) -> None:
    output = _reject_raw_parent_components(output_path, "artifact ledger output")
    if output.is_symlink():
        raise FileExistsError(
            f"Refusing to overwrite existing or symlink artifact ledger: {output}"
        )
    _reject_symlink_components(output, "artifact ledger output")
    if output.exists() or output.is_symlink():
        raise FileExistsError(
            f"Refusing to overwrite existing or symlink artifact ledger: {output}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation closes the check/write race and preserves the no-overwrite contract.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            payload,
            stream,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")


def generate_artifact_ledger(
    *,
    checkpoint_path: str | Path,
    expected_global_step: int,
    resolved_config_path: str | Path,
    teacher_checkpoint_path: str | Path,
    teacher_config_path: str | Path,
    teacher_manifest_path: str | Path,
    rank_logs: Sequence[str | Path],
    training_logs: Sequence[str | Path],
    base_sha: str,
    candidate_id: str,
    source_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Generate one immutable deterministic ledger for a final Student artifact."""
    expected_global_step = _require_step(expected_global_step)
    base_sha = _require_text(base_sha, "BASE_SHA")
    candidate_id = _require_text(candidate_id, "CANDIDATE_ID")
    canonical_source_root = _canonical_directory(source_root, "source_root")

    checkpoint = _canonical_file(checkpoint_path, "final checkpoint")
    checkpoint_semantics = _checkpoint_semantics(checkpoint, expected_global_step)
    checkpoint_record = _file_identity(checkpoint, "final checkpoint")
    checkpoint_record.update(checkpoint_semantics)

    artifacts = {
        "final_checkpoint": checkpoint_record,
        "resolved_config": _file_identity(resolved_config_path, "resolved config"),
        "teacher_checkpoint": _file_identity(
            teacher_checkpoint_path, "Teacher checkpoint"
        ),
        "teacher_config": _file_identity(teacher_config_path, "Teacher config"),
        "teacher_manifest": _file_identity(teacher_manifest_path, "Teacher manifest"),
    }
    rank_records = [
        _file_identity(path, f"rank log[{index}]")
        for index, path in enumerate(_normalize_log_paths(rank_logs, "rank_logs"))
    ]
    training_records = [
        _file_identity(path, f"training log[{index}]")
        for index, path in enumerate(_normalize_log_paths(training_logs, "training_logs"))
    ]

    ledger: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "base_sha": base_sha,
        "candidate_id": candidate_id,
        "source_root": str(canonical_source_root),
        "expected_global_step": expected_global_step,
        "artifacts": artifacts,
        "logs": {"rank": rank_records, "training": training_records},
    }
    _write_deterministic_json(output_path, ledger)
    return ledger


def _require_identity_record(
    record: Any, label: str, *, extra_fields: Sequence[str] = ()
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError(f"{label} identity must be a mapping")
    allowed_fields = set(_IDENTITY_FIELDS).union(extra_fields)
    unexpected_fields = sorted(set(record).difference(allowed_fields))
    if unexpected_fields:
        raise ValueError(f"{label} identity has unexpected keys: {unexpected_fields}")
    for field in (*_IDENTITY_FIELDS, *extra_fields):
        if field not in record:
            raise ValueError(f"{label} identity is missing {field!r}")
    path_value = record["path"]
    if not isinstance(path_value, str) or not path_value or not Path(path_value).is_absolute():
        raise ValueError(f"{label} identity path must be an absolute string")
    if type(record["size"]) is not int or record["size"] < 0:  # noqa: E721
        raise ValueError(f"{label} identity size must be a non-negative integer")
    if type(record["mtime_ns"]) is not int or record["mtime_ns"] < 0:  # noqa: E721
        raise ValueError(f"{label} identity mtime_ns must be a non-negative integer")
    digest = record["sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"{label} identity sha256 must be a lowercase SHA256 digest")
    return dict(record)


def _verify_identity(
    record: Mapping[str, Any],
    label: str,
    *,
    extra_fields: Sequence[str] = (),
    require_nonempty: bool = False,
) -> dict[str, Any]:
    expected = _require_identity_record(record, label, extra_fields=extra_fields)
    if require_nonempty and expected["size"] <= 0:
        raise ValueError(f"{label} recorded size must be positive")
    path = _canonical_file(expected["path"], label)
    if str(path) != expected["path"]:
        raise ValueError(
            f"{label} identity path is not canonical: recorded={expected['path']!r}, "
            f"resolved={str(path)!r}"
        )
    actual = _file_identity(path, label, require_nonempty=require_nonempty)
    for field in ("sha256", "size", "mtime_ns"):
        if actual[field] != expected[field]:
            raise ValueError(
                f"{label} identity mismatch for {field}: "
                f"recorded={expected[field]!r}, actual={actual[field]!r}"
            )
    return actual


def verify_artifact_ledger(ledger_path: str | Path) -> dict[str, Any]:
    """Verify ledger schema, every recorded identity, and final checkpoint semantics."""
    ledger_file = _canonical_file(ledger_path, "artifact ledger")
    with ledger_file.open("r", encoding="utf-8") as stream:
        ledger = json.load(stream)
    if not isinstance(ledger, Mapping):
        raise ValueError("Artifact ledger must be a JSON mapping")
    missing_top_level = [key for key in _TOP_LEVEL_KEYS if key not in ledger]
    unexpected_top_level = sorted(set(ledger).difference(_TOP_LEVEL_KEYS))
    if missing_top_level or unexpected_top_level:
        raise ValueError(
            "Artifact ledger top-level schema mismatch: "
            f"missing={missing_top_level}, unexpected={unexpected_top_level}"
        )
    if ledger.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "Artifact ledger schema mismatch: "
            f"expected {SCHEMA_VERSION!r}, got {ledger.get('schema_version')!r}"
        )
    base_sha = _require_text(ledger.get("base_sha"), "BASE_SHA")
    candidate_id = _require_text(ledger.get("candidate_id"), "CANDIDATE_ID")
    expected_global_step = _require_step(ledger.get("expected_global_step"))
    source_root = _canonical_directory(ledger.get("source_root"), "source_root")
    if str(source_root) != ledger.get("source_root"):
        raise ValueError("Artifact ledger source_root is not canonical")

    artifacts = ledger.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("Artifact ledger artifacts must be a mapping")
    missing_artifacts = [key for key in _ARTIFACT_KEYS if key not in artifacts]
    if missing_artifacts:
        raise ValueError(f"Artifact ledger is missing artifacts: {missing_artifacts}")

    unexpected_artifacts = sorted(set(artifacts).difference(_ARTIFACT_KEYS))
    if unexpected_artifacts:
        raise ValueError(f"Artifact ledger has unexpected artifacts: {unexpected_artifacts}")
    checkpoint_record = _require_identity_record(
        artifacts["final_checkpoint"],
        "final checkpoint",
        extra_fields=("global_step", "policy_tensor_count", "policy_element_count", "optimizer_state_entries"),
    )
    checkpoint_path = _canonical_file(checkpoint_record["path"], "final checkpoint")
    _verify_identity(
        checkpoint_record,
        "final checkpoint",
        extra_fields=("global_step", "policy_tensor_count", "policy_element_count", "optimizer_state_entries"),
    )
    semantics = _checkpoint_semantics(checkpoint_path, expected_global_step)
    for field, actual in semantics.items():
        recorded = checkpoint_record.get(field)
        if type(recorded) is not int or recorded != actual:  # noqa: E721
            raise ValueError(
                f"Final checkpoint semantic mismatch for {field}: "
                f"recorded={recorded!r}, actual={actual!r}"
            )

    for key in _ARTIFACT_KEYS[1:]:
        _verify_identity(artifacts[key], key.replace("_", " "))

    logs = ledger.get("logs")
    if not isinstance(logs, Mapping):
        raise ValueError("Artifact ledger logs must be a mapping")
    unexpected_categories = sorted(set(logs).difference(("rank", "training")))
    if unexpected_categories:
        raise ValueError(f"Artifact ledger has unexpected log categories: {unexpected_categories}")
    for category in ("rank", "training"):
        records = logs.get(category)
        if not isinstance(records, list) or not records:
            raise ValueError(f"Artifact ledger logs.{category} must be a nonempty list")
        for index, record in enumerate(records):
            _verify_identity(record, f"{category} log[{index}]", require_nonempty=True)

    # Keep these local assignments explicit: verification validates their presence but
    # cannot recompute provenance values from filesystem bytes.
    _ = (base_sha, candidate_id)
    return dict(ledger)


# Concise aliases make the import-safe API discoverable without duplicating behavior.
generate_ledger = generate_artifact_ledger
verify_ledger = verify_artifact_ledger


def _add_generate_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-global-step", type=int, required=True)
    parser.add_argument("--resolved-config", dest="resolved_config_path", type=Path, required=True)
    parser.add_argument("--teacher-checkpoint", dest="teacher_checkpoint_path", type=Path, required=True)
    parser.add_argument("--teacher-config", dest="teacher_config_path", type=Path, required=True)
    parser.add_argument("--teacher-manifest", dest="teacher_manifest_path", type=Path, required=True)
    parser.add_argument("--rank-log", dest="rank_logs", action="append", required=True)
    parser.add_argument("--training-log", dest="training_logs", action="append", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", dest="output_path", type=Path, required=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="write one new immutable artifact ledger")
    _add_generate_arguments(generate)
    verify = subparsers.add_parser("verify", help="verify a ledger and all referenced files")
    verify.add_argument("--ledger", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if args.command == "generate":
        result = generate_artifact_ledger(
            checkpoint_path=args.checkpoint,
            expected_global_step=args.expected_global_step,
            resolved_config_path=args.resolved_config_path,
            teacher_checkpoint_path=args.teacher_checkpoint_path,
            teacher_config_path=args.teacher_config_path,
            teacher_manifest_path=args.teacher_manifest_path,
            rank_logs=args.rank_logs,
            training_logs=args.training_logs,
            base_sha=args.base_sha,
            candidate_id=args.candidate_id,
            source_root=args.source_root,
            output_path=args.output_path,
        )
    elif args.command == "verify":
        result = verify_artifact_ledger(args.ledger)
    else:  # pragma: no cover - argparse enforces the subcommand
        raise RuntimeError(f"Unsupported sealer command: {args.command!r}")
    print(json.dumps(result, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
