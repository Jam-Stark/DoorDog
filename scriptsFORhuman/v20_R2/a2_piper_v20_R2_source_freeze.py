"""Create an immutable, producer-only R2 source lock.

The command performs all repository checks before writing its output.  It never
accepts a caller-authored status and refuses an existing marker, so a lock is
an auditable source snapshot rather than a declaration of admission.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

from ._r2_common import (
    ADMISSION_PLAN_ID,
    B0_CSV_PATH,
    B0_CSV_SHA256,
    B0_JSON_PATH,
    B0_JSON_SHA256,
    PRODUCER_STATES,
    R1_CHECKPOINT_PATH,
    R1_CHECKPOINT_SHA256,
    R1_PLAN_PATH,
    R1_PLAN_SHA256,
    R1_URDF_PATH,
    R1_URDF_SHA256,
    R2_PLAN_LOCK_PATH,
    R2_PLAN_LOCK_SHA256,
    R2_PLAN_PATH,
    R2_PLAN_SHA256,
    R2Error,
    R1_BLOCKER_COMMIT,
    canonical_json,
    exact_sha256,
    git_identity,
    hash_command_env,
    resolve_repo_path,
    sha256_file,
    validate_clean_git,
    validate_regular_file,
    write_json_exclusive,
)


R2_SOURCE_ROOT = "scriptsFORhuman/v20_R2"
R2_SCHEMA_ROOT = "scriptsFORhuman/v20_R2/schemas"
R2_TEST_GLOB = "gr00t/rl/tests/test_a2_v20*"
R2_CONFIG_ROOT = "gr00t/rl/config/ablation/wbmanip"


def _git_tracked(repo_root: Path, relative: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _source_entry(repo_root: Path, relative: str, kind: str) -> dict[str, str]:
    if not _git_tracked(repo_root, relative):
        raise R2Error(f"source must be tracked before freeze: {relative}")
    path = resolve_repo_path(repo_root, relative, require_file=True)
    return {"path": relative, "sha256": sha256_file(path), "kind": kind}


def discover_sources(repo_root: Path) -> list[dict[str, str]]:
    """Deterministically select all Phase-I R2 and immutable contract inputs."""

    selected: list[tuple[str, str]] = [
        (R2_PLAN_PATH, "immutable_input"),
        (R2_PLAN_LOCK_PATH, "immutable_input"),
        (R1_PLAN_PATH, "immutable_input"),
        (B0_JSON_PATH, "immutable_input"),
        (B0_CSV_PATH, "immutable_input"),
        (R1_CHECKPOINT_PATH, "checkpoint"),
        (R1_URDF_PATH, "urdf"),
    ]
    source_root = resolve_repo_path(repo_root, R2_SOURCE_ROOT)
    for path in sorted(source_root.glob("*.py")):
        relative = path.relative_to(repo_root).as_posix()
        selected.append((relative, "source"))
    schema_root = resolve_repo_path(repo_root, R2_SCHEMA_ROOT)
    for path in sorted(schema_root.glob("*.json")):
        relative = path.relative_to(repo_root).as_posix()
        selected.append((relative, "schema"))
    test_root = resolve_repo_path(repo_root, "gr00t/rl/tests")
    for path in sorted(test_root.glob("test_a2_v20*.py")):
        relative = path.relative_to(repo_root).as_posix()
        selected.append((relative, "test"))
    config_root = resolve_repo_path(repo_root, R2_CONFIG_ROOT)
    for path in sorted(config_root.glob("base_v20*.yaml")):
        relative = path.relative_to(repo_root).as_posix()
        selected.append((relative, "config"))
    deduped = sorted(dict.fromkeys(selected), key=lambda row: row[0])
    return [_source_entry(repo_root, relative, kind) for relative, kind in deduped]


def _immutable_expected(repo_root: Path) -> None:
    checks = (
        (R2_PLAN_PATH, R2_PLAN_SHA256, "R2 plan"),
        (R2_PLAN_LOCK_PATH, R2_PLAN_LOCK_SHA256, "R2 plan lock"),
        (R1_PLAN_PATH, R1_PLAN_SHA256, "R1 plan"),
        (B0_JSON_PATH, B0_JSON_SHA256, "B0 JSON"),
        (B0_CSV_PATH, B0_CSV_SHA256, "B0 CSV"),
        (R1_CHECKPOINT_PATH, R1_CHECKPOINT_SHA256, "R1 checkpoint"),
        (R1_URDF_PATH, R1_URDF_SHA256, "R1 URDF"),
    )
    for relative, expected, label in checks:
        path = resolve_repo_path(repo_root, relative, require_file=True)
        actual = sha256_file(path)
        exact_sha256(expected, name=f"{label} expected SHA-256")
        if actual != expected:
            raise R2Error(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")


def build_source_lock(
    *,
    repo_root: Path,
    revision: int,
    required_branch: str,
    required_ancestor: str,
) -> dict[str, Any]:
    if revision not in (0, 1):
        raise R2Error("R2 permits only static revision 0 or 1")
    if required_branch != "A2_Piper":
        raise R2Error("R2 source freeze requires branch A2_Piper")
    if required_ancestor != R1_BLOCKER_COMMIT:
        raise R2Error("R2 source freeze requires the exact R1 blocker ancestor")
    root = resolve_repo_path(repo_root, ".")
    identity = validate_clean_git(root, branch=required_branch, required_ancestor=required_ancestor)
    _immutable_expected(root)
    sources = discover_sources(root)
    command_templates = [
        {"name": "py_compile", "argv": ["python", "-B", "-m", "py_compile"], "env": {}},
        {"name": "diff_check", "argv": ["git", "diff", "--check", required_ancestor, "HEAD", "--"], "env": {}},
        {"name": "focused_tests", "argv": ["python", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"], "env": {}},
    ]
    commands = [
        {
            "name": item["name"],
            "argv": item["argv"],
            "env_sha256": hash_command_env(item["argv"], item["env"]),
        }
        for item in command_templates
    ]
    return {
        "schema": "a2_piper_base_v20_R2_source_lock_v1",
        "producer_state": "SOURCE_FROZEN",
        "revision": revision,
        "admission_plan_id": ADMISSION_PLAN_ID,
        "scientific_plan_id": "base_v20_R1_policy_behavior_v1",
        "git": {
            "commit": identity["commit"],
            "tree": identity["tree"],
            "branch": identity["branch"],
            "required_ancestor": required_ancestor,
        },
        "immutable_inputs": {
            "r2_plan_sha256": R2_PLAN_SHA256,
            "r2_plan_lock_sha256": R2_PLAN_LOCK_SHA256,
            "r1_plan_sha256": R1_PLAN_SHA256,
            "b0_json_sha256": B0_JSON_SHA256,
            "b0_csv_sha256": B0_CSV_SHA256,
            "checkpoint_sha256": R1_CHECKPOINT_SHA256,
            "urdf_sha256": R1_URDF_SHA256,
        },
        "sources": sources,
        "commands": commands,
        "discovery": {
            "r2_tests_glob": R2_TEST_GLOB,
            "r2_config_root": R2_CONFIG_ROOT,
            "test_count": sum(1 for row in sources if row["kind"] == "test"),
            "config_count": sum(1 for row in sources if row["kind"] == "config"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--revision", type=int, required=True, choices=(0, 1))
    parser.add_argument("--required-branch", default="A2_Piper")
    parser.add_argument("--required-ancestor", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else args.repo_root / args.output
    payload = build_source_lock(
        repo_root=args.repo_root,
        revision=args.revision,
        required_branch=args.required_branch,
        required_ancestor=args.required_ancestor,
    )
    write_json_exclusive(output, payload)
    print(canonical_json({"producer_state": payload["producer_state"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
