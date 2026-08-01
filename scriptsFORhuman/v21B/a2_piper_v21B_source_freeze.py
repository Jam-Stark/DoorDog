"""Versioned source/config lock for v21-B pre-formal admission."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ._v21b_common import V21B_CELL_ORDER, V21B_CONFIG_PATHS, V21BError, V21B_WARM_START_PATH, V21B_WARM_START_SHA256, canonical_json_bytes, sha256_file
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact


def build_source_lock(repo_root: Path, *, plan_path: Path, manifest_path: Path, extra_paths: Iterable[Path] = ()) -> dict[str, object]:
    root = repo_root.resolve()
    extras = [
        (root / path if not Path(path).is_absolute() else Path(path)).resolve()
        for path in extra_paths
    ]
    plan = (root / plan_path if not plan_path.is_absolute() else plan_path).resolve()
    manifest = (root / manifest_path if not manifest_path.is_absolute() else manifest_path).resolve()
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
        plan,
        manifest,
        root / V21B_WARM_START_PATH,
        *(root / path for path in V21B_CONFIG_PATHS.values()),
        *extras,
    ]
    rows = []
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise V21BError(f"source lock path must be a regular file: {path}")
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise V21BError(f"source lock path escapes repository: {path}") from exc
        rows.append({"path": relative, "sha256": sha256_file(path)})
    rows.sort(key=lambda row: row["path"])
    payload = artifact_payload("source_lock", status="STATIC_PASS", source_paths=rows, immutable_after_freeze=True, cells=list(V21B_CELL_ORDER), schema_namespace="a2_piper_base_v21B_", v20_artifacts_rejected=True, source_checkpoint_sha256=V21B_WARM_START_SHA256)
    payload["source_lock_sha256"] = __import__("hashlib").sha256(canonical_json_bytes(rows)).hexdigest()
    return validate_artifact(payload, expected_schema=schema("source_lock"))


def validate_source_lock(lock: dict[str, object], repo_root: Path, *, require_current: bool = True) -> None:
    validate_artifact(lock, expected_schema=schema("source_lock"))
    if not require_current:
        return
    root = repo_root.resolve()
    for row in lock["source_paths"]:
        path = root / row["path"]
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
