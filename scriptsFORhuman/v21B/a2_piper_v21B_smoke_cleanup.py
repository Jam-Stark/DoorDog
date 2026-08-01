"""Enumerate only exact v21-B B4 smoke targets; reject broad deletion."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import hashlib
import json
import shutil

from ._v21b_common import V21BError, canonical_json_bytes
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact
from .a2_piper_v21B_smoke_launcher import SMOKE_LAUNCHER_REL, SMOKE_TRAINING_REL

SMOKE_EVAL_REL = "logs_eval/base_v21B/smoke/B4"


def build_smoke_cleanup_manifest(repo_root: Path, *, plan: Mapping[str, Any], smoke_pass: Mapping[str, Any], targets: Sequence[Path]) -> dict[str, Any]:
    validate_artifact(plan, expected_schema=schema("smoke_plan"), expected_cell="B4")
    validate_artifact(smoke_pass, expected_schema=schema("smoke_adjudication"), expected_cell="B4")
    if smoke_pass.get("status") != "SMOKE_PASS":
        raise V21BError("cleanup requires a completed SMOKE_PASS artifact")
    root = repo_root.resolve()
    allowed = {root / SMOKE_TRAINING_REL, root / SMOKE_EVAL_REL, root / SMOKE_LAUNCHER_REL}
    resolved: list[str] = []
    for target in targets:
        path = target.resolve()
        if path not in allowed:
            raise V21BError(f"refusing cleanup target outside exact B4 smoke roots: {target}")
        resolved.append(str(path))
    if set(Path(path) for path in resolved) != allowed:
        raise V21BError("cleanup manifest must name exactly the dedicated train/eval/launcher roots")
    return artifact_payload("smoke_cleanup", status="STATIC_PASS", cell="B4", targets=sorted(set(resolved)), smoke_pass_sha256=hashlib.sha256(canonical_json_bytes(dict(smoke_pass))).hexdigest(), refuses_broad_delete=True, exact_roots=[str(path) for path in sorted(allowed)], receipt_required=True)


def cleanup_targets(manifest: Mapping[str, Any], *, confirm_exact: bool = False, receipt_path: Path | None = None) -> dict[str, Any]:
    validate_artifact(manifest, expected_schema=schema("smoke_cleanup"), expected_cell="B4")
    if confirm_exact is not True:
        raise V21BError("cleanup requires explicit confirm_exact=True")
    targets = manifest.get("targets")
    if not isinstance(targets, list) or not targets:
        raise V21BError("cleanup manifest has no exact targets")
    if receipt_path is None:
        raise V21BError("cleanup requires a receipt path outside the deleted roots")
    receipt = Path(receipt_path).resolve()
    exact_roots = {Path(path).resolve() for path in manifest["exact_roots"]}
    if any(root == receipt or root in receipt.parents for root in exact_roots):
        raise V21BError("cleanup receipt must be outside every deleted root")
    for target in targets:
        path = Path(target).resolve()
        if path not in exact_roots:
            raise V21BError(f"cleanup target is outside the signed exact roots: {path}")
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_dir():
                raise V21BError(f"cleanup target is not an exact directory: {path}")
            shutil.rmtree(path)
        if path.exists() or path.is_symlink():
            raise V21BError(f"cleanup target remains after deletion: {path}")
    if receipt.exists() or receipt.is_symlink():
        raise V21BError(f"refusing to overwrite cleanup receipt: {receipt}")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    result = artifact_payload("smoke_cleanup", status="CLEANUP_PASS", cell="B4", smoke_pass_sha256=manifest["smoke_pass_sha256"], deleted_paths=sorted(str(path) for path in exact_roots), receipt_path=str(receipt), all_targets_absent=True)
    receipt.write_bytes(canonical_json_bytes(result) + b"\n")
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["SMOKE_EVAL_REL", "build_smoke_cleanup_manifest", "cleanup_targets", "main"]
