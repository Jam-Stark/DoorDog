"""Versioned source/config lock for v21-B pre-formal admission."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Iterable

from ._v21b_common import V21B_CELL_ORDER, V21B_CONFIG_PATHS, V21B_EVAL_CONTRACT_PATH, V21BError, V21B_WARM_START_PATH, V21B_WARM_START_SHA256, canonical_json_bytes, require_digest, sha256_file
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact


def build_source_lock(repo_root: Path, *, plan_path: Path, manifest_path: Path, extra_paths: Iterable[Path] = ()) -> dict[str, object]:
    root = repo_root.resolve()
    extras = [
        (root / path if not Path(path).is_absolute() else Path(path)).resolve()
        for path in extra_paths
    ]
    plan = (root / plan_path if not plan_path.is_absolute() else plan_path).resolve()
    manifest = (root / manifest_path if not manifest_path.is_absolute() else manifest_path).resolve()
    # Keep the explicitly named scientific/runtime inputs first for review
    # readability, then include every regular v21-B Python runtime module.
    # The latter is intentionally derived from the tree rather than a hand
    # maintained allow-list: a new launcher/monitor/collector must be locked
    # before it can participate in a run.
    runtime_root = root / "scriptsFORhuman/v21B"
    runtime_paths = [
        path for path in sorted(runtime_root.glob("*.py"))
        if path.is_file() and not path.is_symlink()
    ]
    paths = [
        root / "gr00t/rl/envs/door/door_open_a2_base.py",
        root / "gr00t/rl/envs/door/a2_v21b_evidence.py",
        root / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py",
        root / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py",
        root / "gr00t/rl/simulator/isaacsim/isaacsim.py",
        root / "scriptsFORhuman/v21B/a2_piper_v21B_schemas.py",
        root / "scriptsFORhuman/v21B/a2_piper_v21B_probe_runner.py",
        root / "scriptsFORhuman/v21B/a2_piper_v21B_heavy16_census.py",
        root / "scriptsFORhuman/v21B/a2_piper_v21B_zero_shot.py",
        root / "scriptsFORhuman/v21B/a2_piper_v21B_pilot.py",
        root / V21B_EVAL_CONTRACT_PATH,
        plan,
        manifest,
        root / V21B_WARM_START_PATH,
        *(root / path for path in V21B_CONFIG_PATHS.values()),
        *extras,
        *runtime_paths,
    ]
    # Core entries overlap the runtime glob (schemas/probe runner and the
    # probe modules), so deduplicate by repository-relative path before
    # hashing.  Duplicate rows would make the lock ambiguous and are rejected
    # by the validator as well.
    unique_paths: dict[str, Path] = {}
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise V21BError(f"source lock path must be a regular file: {path}")
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise V21BError(f"source lock path escapes repository: {path}") from exc
        unique_paths[relative] = path
    expected_runtime_paths = {
        path.relative_to(root).as_posix() for path in runtime_paths
    }
    missing_runtime = expected_runtime_paths - set(unique_paths)
    if missing_runtime:
        raise V21BError(
            "source lock omitted regular v21-B runtime modules: "
            + ", ".join(sorted(missing_runtime))
        )
    rows = [
        {"path": relative, "sha256": sha256_file(path)}
        for relative, path in sorted(unique_paths.items())
    ]
    payload = artifact_payload("source_lock", status="STATIC_PASS", source_paths=rows, immutable_after_freeze=True, cells=list(V21B_CELL_ORDER), schema_namespace="a2_piper_base_v21B_", v20_artifacts_rejected=True, source_checkpoint_sha256=V21B_WARM_START_SHA256)
    payload["source_lock_sha256"] = __import__("hashlib").sha256(canonical_json_bytes(rows)).hexdigest()
    return validate_artifact(payload, expected_schema=schema("source_lock"))


def validate_source_lock(lock: dict[str, object], repo_root: Path, *, require_current: bool = True) -> None:
    validate_artifact(lock, expected_schema=schema("source_lock"))
    root = repo_root.resolve()
    rows = lock.get("source_paths")
    if not isinstance(rows, list):
        raise V21BError("source lock source_paths must be a list")
    if any(not isinstance(row, Mapping) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str) for row in rows):
        raise V21BError("source lock rows must contain path and sha256")
    paths = [row["path"] for row in rows]
    if len(paths) != len(set(paths)):
        raise V21BError("source lock contains duplicate paths")
    runtime_root = root / "scriptsFORhuman/v21B"
    expected_runtime = {
        path.relative_to(root).as_posix()
        for path in runtime_root.glob("*.py")
        if path.is_file() and not path.is_symlink()
    }
    missing_runtime = expected_runtime - set(paths)
    if missing_runtime:
        raise V21BError(
            "source lock is missing current v21-B runtime modules: "
            + ", ".join(sorted(missing_runtime))
        )
    eval_rows = [row for row in rows if row["path"] == V21B_EVAL_CONTRACT_PATH]
    if len(eval_rows) != 1:
        raise V21BError(f"source lock must contain exactly one {V21B_EVAL_CONTRACT_PATH} row")
    declared_lock_hash = require_digest(lock.get("source_lock_sha256"), name="source lock")
    expected_lock_hash = __import__("hashlib").sha256(canonical_json_bytes(rows)).hexdigest()
    if declared_lock_hash != expected_lock_hash:
        raise V21BError("source lock digest does not bind its source rows")
    if not require_current:
        return
    for row in rows:
        path = root / row["path"]
        if not path.is_file() or path.is_symlink():
            raise V21BError(f"source lock path is missing or not a regular file: {row['path']}")
        if sha256_file(path) != row["sha256"]:
            raise V21BError(f"source lock mismatch: {row['path']}")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_source_lock", "validate_source_lock", "main"]
