"""Freeze the exact v22 source and warm-start identity.

Produces ``logs_eval/base_v22/locks/V22_SOURCE_LOCK.json``.  Every later node
binds to this lock; a drifted source is an admission failure, not a warning.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from ._v22_common import (
    REPO_ROOT,
    V22_CHANGE_LOG_DOCUMENT,
    V22_LOCK_ROOT,
    V22_MANIFEST_DOCUMENT,
    V22_PLAN_DOCUMENT,
    V22_SCIENTIFIC_BASE_COMMIT,
    V22_SOURCE_LOCK_FILES,
    V22_URDF_PATH,
    V22_URDF_SHA256,
    V22_WARM_START_CONFIG_SHA256,
    V22_WARM_START_PATH,
    V22_WARM_START_SHA256,
    V22Error,
    artifact_payload,
    digest,
    git_identity,
    sha256_file,
    write_json,
)


def build_source_lock(repo_root: Path = REPO_ROOT) -> dict:
    root = Path(repo_root).resolve()
    sources = {}
    for relative in V22_SOURCE_LOCK_FILES:
        sources[relative] = sha256_file(root / relative)

    warm_start = root / V22_WARM_START_PATH
    warm_start_sha = sha256_file(warm_start)
    if warm_start_sha != V22_WARM_START_SHA256:
        raise V22Error(
            f"v22 warm start hash mismatch: {warm_start_sha} != {V22_WARM_START_SHA256}"
        )
    warm_start_config = warm_start.parent / "config.yaml"
    warm_start_config_sha = sha256_file(warm_start_config) if warm_start_config.is_file() else None
    if warm_start_config_sha is not None and warm_start_config_sha != V22_WARM_START_CONFIG_SHA256:
        raise V22Error(
            "v22 warm-start saved-config hash mismatch: "
            f"{warm_start_config_sha} != {V22_WARM_START_CONFIG_SHA256}"
        )

    urdf_sha = sha256_file(root / V22_URDF_PATH)
    if urdf_sha != V22_URDF_SHA256:
        raise V22Error(f"v22 runtime URDF hash mismatch: {urdf_sha} != {V22_URDF_SHA256}")

    documents = {
        relative: sha256_file(root / relative)
        for relative in (V22_PLAN_DOCUMENT, V22_MANIFEST_DOCUMENT, V22_CHANGE_LOG_DOCUMENT)
    }
    identity = git_identity(root)
    body = {
        "sources": sources,
        "documents": documents,
        "warm_start": {
            "path": V22_WARM_START_PATH,
            "sha256": warm_start_sha,
            "saved_config_sha256": warm_start_config_sha,
            "load_mode": "policy_only",
        },
        "urdf": {"path": V22_URDF_PATH, "sha256": urdf_sha},
        "scientific_base_commit": V22_SCIENTIFIC_BASE_COMMIT,
        "repo_commit": identity["commit"],
        "repo_tree": identity["tree"],
    }
    payload = artifact_payload(
        "source_lock",
        status="SOURCE_LOCK_COMPLETE",
        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **body,
    )
    payload["source_lock_sha256"] = digest(body)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    payload = build_source_lock(args.repo_root)
    target = Path(args.repo_root) / V22_LOCK_ROOT / "V22_SOURCE_LOCK.json"
    file_sha = write_json(target, payload)
    print(f"{target}\nsource_lock_sha256={payload['source_lock_sha256']}\nfile_sha256={file_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
