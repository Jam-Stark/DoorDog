#!/usr/bin/env python3
"""Inspect, package, and optionally upload stage artifacts.

The script selects only untracked/ignored files matched by an allowlist. It uploads only under explicit confirmation or the configured Owner standing authorization, and never stores cloud credentials.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from zoneinfo import ZoneInfo

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover - Python <3.11
    raise SystemExit("Python 3.11+ is required (tomllib missing).") from exc

DEFAULT_CONFIG = Path(".ai/artifact-sync.toml")
HARD_EXCLUDE_PARTS = {".git", ".venv", "venv", "node_modules"}
SECRET_NAME_RE = re.compile(
    r"(^|[._-])(secret|secrets|token|tokens|credential|credentials|private[_-]?key)([._-]|$)",
    re.IGNORECASE,
)
SECRET_CONTENT_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
]
TEXT_SCAN_LIMIT = 2 * 1024 * 1024


@dataclass(frozen=True)
class Candidate:
    path: Path
    relative: str
    size: int
    source: str


@dataclass(frozen=True)
class Exclusion:
    relative: str
    reason: str


def run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True)


def git_root(start: Path) -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    return Path(result.stdout.decode().strip()).resolve()


def git_text(root: Path, *args: str) -> str:
    return run(["git", *args], cwd=root).stdout.decode(errors="replace").strip()


def load_config(root: Path, config_path: Path) -> dict[str, Any]:
    path = config_path if config_path.is_absolute() else root / config_path
    if not path.is_file():
        raise SystemExit(f"Config not found: {path}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def nul_paths(data: bytes) -> list[str]:
    return [part.decode(errors="surrogateescape") for part in data.split(b"\0") if part]


def discover_untracked(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    ordinary = run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root
    ).stdout
    ignored = run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
        cwd=root,
    ).stdout
    for relative in nul_paths(ordinary):
        result[PurePosixPath(relative).as_posix()] = "untracked"
    for relative in nul_paths(ignored):
        result[PurePosixPath(relative).as_posix()] = "ignored"
    return result


def glob_match(path: str, patterns: Iterable[str]) -> bool:
    # fnmatch handles ** sufficiently for repository-relative paths.
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def secret_name(path: str) -> bool:
    pp = PurePosixPath(path)
    if any(part in HARD_EXCLUDE_PARTS for part in pp.parts):
        return True
    if any(part.startswith(".env") for part in pp.parts):
        return True
    return any(SECRET_NAME_RE.search(part) for part in pp.parts)


def scan_secret_content(path: Path) -> str | None:
    if path.stat().st_size > TEXT_SCAN_LIMIT:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return "unreadable"
    if b"\x00" in data[:4096]:
        return None
    text = data.decode("utf-8", errors="ignore")
    for label, pattern in SECRET_CONTENT_PATTERNS:
        if pattern.search(text):
            return f"secret-content:{label}"
    return None


def slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    normalized = re.sub(r"-+", "-", normalized).strip("-._")
    return normalized or "unknown"


def select_candidates(
    root: Path,
    config: dict[str, Any],
    *,
    stage: str,
    selectors: list[str],
    include_checkpoints: bool,
    all_matching: bool,
) -> tuple[list[Candidate], list[Exclusion]]:
    selection = config.get("selection", {})
    includes = list(selection.get("include", []))
    excludes = list(selection.get("exclude", []))
    checkpoint_patterns = list(selection.get("checkpoint_patterns", []))
    max_file = int(selection.get("max_file_bytes", 2 * 1024**3))
    max_bundle = int(selection.get("max_bundle_bytes", 10 * 1024**3))

    if not includes:
        raise SystemExit("selection.include must contain at least one allowlist pattern")

    stage_tokens = [slug(stage).lower(), stage.lower()]
    selector_tokens = [token.lower() for token in selectors if token]
    discovered = discover_untracked(root)
    accepted: list[Candidate] = []
    rejected: list[Exclusion] = []
    total = 0

    for relative, source in sorted(discovered.items()):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        if not glob_match(relative, includes):
            continue
        if glob_match(relative, excludes) or secret_name(relative):
            rejected.append(Exclusion(relative, "excluded-or-sensitive-name"))
            continue
        if checkpoint_patterns and glob_match(relative, checkpoint_patterns) and not include_checkpoints:
            rejected.append(Exclusion(relative, "checkpoint-opt-in-required"))
            continue
        lower = relative.lower()
        if not all_matching and not selector_tokens and not any(token in lower for token in stage_tokens):
            rejected.append(Exclusion(relative, "stage-not-in-path"))
            continue
        if selector_tokens and not any(token in lower for token in selector_tokens):
            rejected.append(Exclusion(relative, "selector-mismatch"))
            continue
        size = path.stat().st_size
        if size > max_file:
            rejected.append(Exclusion(relative, f"file-too-large:{size}"))
            continue
        secret_reason = scan_secret_content(path)
        if secret_reason:
            rejected.append(Exclusion(relative, secret_reason))
            continue
        if total + size > max_bundle:
            rejected.append(Exclusion(relative, "bundle-size-limit"))
            continue
        accepted.append(Candidate(path, relative, size, source))
        total += size

    return accepted, rejected


def repository_url(root: Path) -> str | None:
    try:
        return git_text(root, "remote", "get-url", "origin") or None
    except subprocess.CalledProcessError:
        return None


def build_metadata(
    root: Path,
    config: dict[str, Any],
    *,
    project: str,
    worktree: str,
    stage: str,
    candidates: list[Candidate],
    exclusions: list[Exclusion],
    questions: list[str],
) -> dict[str, Any]:
    now = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    sha = git_text(root, "rev-parse", "--short=12", "HEAD")
    branch = git_text(root, "branch", "--show-current") or "detached"
    status = git_text(root, "status", "--short")
    return {
        "schema_version": 1,
        "project": project,
        "repository_url": repository_url(root),
        "repository_root": str(root),
        "branch": branch,
        "worktree": worktree,
        "stage": stage,
        "timestamp_hkt": now.isoformat(timespec="seconds"),
        "timestamp_compact": now.strftime("%Y%m%d-%H%M%S-HKT"),
        "git_revision": git_text(root, "rev-parse", "HEAD"),
        "git_short_sha": sha,
        "dirty_summary": status.splitlines(),
        "selection": config.get("selection", {}),
        "included": [
            {"path": item.relative, "bytes": item.size, "source": item.source}
            for item in candidates
        ],
        "excluded": [
            {"path": item.relative, "reason": item.reason} for item in exclusions
        ],
        "evidence_boundary": (
            "Bundle contents are stage artifacts selected from untracked/ignored files. "
            "Their presence does not by itself prove runtime, experiment, or hardware success."
        ),
        "cloud_planner_questions": questions,
        "upload": config.get("upload", {}),
    }


def handoff_markdown(meta: dict[str, Any]) -> str:
    questions = meta["cloud_planner_questions"] or [
        "请独立分析本阶段结果、失败模式、替代解释和下一阶段候选。",
        "请区分 remote-code/artifact 证据与需要本地 planner 核验的运行条件。",
    ]
    q_lines = "\n".join(f"- {q}" for q in questions)
    return f"""# Cloud Planner Handoff

## Context

- Project: `{meta['project']}`
- Worktree: `{meta['worktree']}`
- Branch: `{meta['branch']}`
- Stage: `{meta['stage']}`
- Git revision: `{meta['git_revision']}`
- Timestamp: `{meta['timestamp_hkt']}`

## Evidence boundary

{meta['evidence_boundary']}

Cloud analysis may inspect the remote repository and this bundle. It must not assume local IsaacLab, GPU, driver, resolved-config, checkpoint, or unbundled log facts. Mark local feasibility claims for the local planner to verify.

## Questions

{q_lines}

## Bundle contents

- Included files: {len(meta['included'])}
- Excluded candidates: {len(meta['excluded'])}
- See `BUNDLE_MANIFEST.json` for exact paths and reasons.
"""


def pack(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    root = git_root(args.repo)
    config = load_config(root, args.config)
    include_checkpoints = args.include_checkpoints or bool(
        config.get("selection", {}).get("include_checkpoints_default", False)
    )
    candidates, exclusions = select_candidates(
        root,
        config,
        stage=args.stage,
        selectors=args.selector,
        include_checkpoints=include_checkpoints,
        all_matching=args.all_matching,
    )
    if not candidates and not args.allow_empty:
        raise SystemExit("No eligible stage artifacts found. Use inspect to review exclusions.")

    project = slug(args.project or root.name)
    branch = git_text(root, "branch", "--show-current") or "detached"
    worktree = slug(args.worktree or branch)
    stage = slug(args.stage)
    meta = build_metadata(
        root,
        config,
        project=project,
        worktree=worktree,
        stage=stage,
        candidates=candidates,
        exclusions=exclusions,
        questions=args.question,
    )
    stamp = meta["timestamp_compact"]
    sha = meta["git_short_sha"]
    bundle_name = f"{project}__{worktree}__{stage}__{stamp}__{sha}__artifacts"
    output_setting = Path(config.get("output_dir", ".ai/outgoing-artifacts"))
    output_root = args.output or (root / output_setting)
    bundle_dir = output_root / bundle_name
    zip_path = output_root / f"{bundle_name}.zip"

    if bundle_dir.exists() or zip_path.exists():
        raise SystemExit(f"Output already exists: {bundle_name}")
    bundle_dir.mkdir(parents=True, exist_ok=False)

    (bundle_dir / "BUNDLE_MANIFEST.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (bundle_dir / "PRO_HANDOFF.md").write_text(handoff_markdown(meta), encoding="utf-8")

    artifact_root = bundle_dir / "artifacts"
    for item in candidates:
        target = artifact_root / item.relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.path, target)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_dir.parent).as_posix())

    print(f"PACKED: {zip_path}")
    print(f"BUNDLE_DIR: {bundle_dir}")
    print(f"INCLUDED: {len(candidates)} files")
    print(f"EXCLUDED: {len(exclusions)} candidates")
    return zip_path, bundle_dir, meta


def inspect(args: argparse.Namespace) -> int:
    root = git_root(args.repo)
    config = load_config(root, args.config)
    candidates, exclusions = select_candidates(
        root,
        config,
        stage=args.stage,
        selectors=args.selector,
        include_checkpoints=args.include_checkpoints,
        all_matching=args.all_matching,
    )
    print("ELIGIBLE")
    for item in candidates:
        print(f"  {item.relative}\t{item.size}\t{item.source}")
    print("EXCLUDED")
    for item in exclusions:
        print(f"  {item.relative}\t{item.reason}")
    print(f"SUMMARY eligible={len(candidates)} excluded={len(exclusions)}")
    return 0


def upload(args: argparse.Namespace) -> int:
    root = git_root(args.repo)
    config = load_config(root, args.config)
    upload_cfg = config.get("upload", {})
    backend = upload_cfg.get("backend", "rclone")
    if backend not in {"rclone", "capability-router"}:
        raise SystemExit(f"Unsupported upload backend: {backend}")
    if backend == "capability-router" and shutil.which("rclone") is None:
        raise SystemExit("No CLI upload capability is available; use a connected Drive/browser runtime or configure rclone.")
    standing = upload_cfg.get("standing_authorization") == "create-only-stage-artifacts"
    if not standing and not args.confirm_external_write:
        raise SystemExit("Upload is an external write; pass --confirm-external-write.")
    source = args.bundle.resolve()
    if not source.exists():
        raise SystemExit(f"Bundle path not found: {source}")
    remote = str(upload_cfg.get("rclone_remote", upload_cfg.get("remote", ""))).strip()
    folder_id = str(upload_cfg.get("root_folder_id", "")).strip()
    if not remote or not folder_id:
        raise SystemExit("upload.remote and upload.root_folder_id are required")
    destination = "/".join(
        [slug(args.project), slug(args.worktree), slug(args.stage), slug(args.release)]
    )
    cmd = [
        "rclone",
        "copy",
        str(source),
        f"{remote}:{destination}",
        "--drive-root-folder-id",
        folder_id,
        "--no-traverse",
        "--progress",
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    print("RUN:", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=root, check=False)
    return completed.returncode


def add_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--selector", action="append", default=[])
    parser.add_argument("--all-matching", action="store_true")
    parser.add_argument("--include-checkpoints", action="store_true")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    p_inspect = commands.add_parser("inspect", help="List eligible and excluded files")
    add_selection_args(p_inspect)

    p_pack = commands.add_parser("pack", help="Create bundle directory and ZIP")
    add_selection_args(p_pack)
    p_pack.add_argument("--project")
    p_pack.add_argument("--worktree")
    p_pack.add_argument("--output", type=Path)
    p_pack.add_argument("--question", action="append", default=[])
    p_pack.add_argument("--allow-empty", action="store_true")

    p_upload = commands.add_parser("upload", help="Upload an existing bundle via rclone")
    p_upload.add_argument("--repo", type=Path, default=Path.cwd())
    p_upload.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p_upload.add_argument("--bundle", type=Path, required=True)
    p_upload.add_argument("--project", required=True)
    p_upload.add_argument("--worktree", required=True)
    p_upload.add_argument("--stage", required=True)
    p_upload.add_argument("--release", required=True, help="timestamp__sha directory name")
    p_upload.add_argument("--confirm-external-write", action="store_true")
    p_upload.add_argument("--dry-run", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "inspect":
        return inspect(args)
    if args.command == "pack":
        pack(args)
        return 0
    return upload(args)


if __name__ == "__main__":
    raise SystemExit(main())
