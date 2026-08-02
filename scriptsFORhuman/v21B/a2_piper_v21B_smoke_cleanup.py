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


def _canonical_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, (str, Path)) or not value:
        raise V21BError(f"cleanup {label} path is missing")
    path = Path(value)
    if not path.is_absolute():
        raise V21BError(f"cleanup {label} path must be absolute")
    return path.resolve()


def _signed_smoke_roots(plan: Mapping[str, Any]) -> tuple[Path, dict[str, Path]]:
    unsigned_plan = dict(plan)
    plan_sha256 = unsigned_plan.pop("plan_sha256", None)
    expected_plan_sha256 = hashlib.sha256(canonical_json_bytes(unsigned_plan)).hexdigest()
    if plan_sha256 != expected_plan_sha256:
        raise V21BError("cleanup smoke plan digest is invalid")
    artifact_root = _canonical_path(plan.get("artifact_root"), label="artifact root")
    roots = {
        "training_root": artifact_root / SMOKE_TRAINING_REL,
        "eval_root": artifact_root / SMOKE_EVAL_REL,
        "launcher_root": artifact_root / SMOKE_LAUNCHER_REL,
    }
    for key, expected in roots.items():
        if _canonical_path(plan.get(key), label=key) != expected:
            raise V21BError(f"cleanup smoke plan {key} is not canonical")
    contract = plan.get("result_contract")
    if not isinstance(contract, Mapping) or _canonical_path(contract.get("artifact_root"), label="contract artifact root") != artifact_root:
        raise V21BError("cleanup smoke result contract is not bound to the plan artifact root")
    expected_contract_paths = {
        "aggregate_path": roots["eval_root"] / "smoke_result.json",
        "raw_metrics_path": roots["eval_root"] / "r2_training_metrics.jsonl",
        "checkpoint_path": roots["training_root"] / "model_step_000010.pt",
    }
    for key, expected in expected_contract_paths.items():
        if _canonical_path(contract.get(key), label=key) != expected:
            raise V21BError(f"cleanup smoke result contract {key} is not canonical")
    return artifact_root, roots


def build_smoke_cleanup_manifest(repo_root: Path, *, plan: Mapping[str, Any], smoke_pass: Mapping[str, Any], targets: Sequence[Path]) -> dict[str, Any]:
    validate_artifact(plan, expected_schema=schema("smoke_plan"), expected_cell="B4")
    validate_artifact(smoke_pass, expected_schema=schema("smoke_adjudication"), expected_cell="B4")
    if smoke_pass.get("status") != "SMOKE_PASS":
        raise V21BError("cleanup requires a completed SMOKE_PASS artifact")
    artifact_root, roots = _signed_smoke_roots(plan)
    if Path(repo_root).resolve() != artifact_root:
        raise V21BError("cleanup repo_root must equal the signed smoke plan artifact_root")
    expected_plan_sha256 = plan["plan_sha256"]
    if smoke_pass.get("plan_sha256") != expected_plan_sha256 or smoke_pass.get("artifact_root") != str(artifact_root):
        raise V21BError("cleanup smoke adjudication is not bound to the signed smoke plan")
    for key, expected in roots.items():
        if _canonical_path(smoke_pass.get(key), label=f"smoke pass {key}") != expected:
            raise V21BError("cleanup smoke adjudication roots are not the signed canonical roots")
    smoke_result = smoke_pass.get("result")
    if not isinstance(smoke_result, Mapping) or smoke_result.get("plan_sha256") != expected_plan_sha256:
        raise V21BError("cleanup smoke aggregate is not bound to the signed smoke plan")
    if _canonical_path(smoke_result.get("result_path"), label="smoke aggregate") != roots["eval_root"] / "smoke_result.json" or _canonical_path(smoke_result.get("training_metrics_path"), label="smoke metrics") != roots["eval_root"] / "r2_training_metrics.jsonl":
        raise V21BError("cleanup smoke aggregate paths are not canonical")
    checkpoint = smoke_result.get("checkpoint")
    if not isinstance(checkpoint, Mapping) or _canonical_path(checkpoint.get("path"), label="smoke checkpoint") != roots["training_root"] / "model_step_000010.pt":
        raise V21BError("cleanup smoke checkpoint path is not canonical")
    allowed = set(roots.values())
    resolved = [_canonical_path(target, label="cleanup target") for target in targets]
    if len(resolved) != 3 or set(resolved) != allowed:
        raise V21BError("cleanup manifest must name exactly the dedicated train/eval/launcher roots")
    return artifact_payload("smoke_cleanup", status="STATIC_PASS", cell="B4", targets=sorted(str(path) for path in resolved), smoke_pass_sha256=hashlib.sha256(canonical_json_bytes(dict(smoke_pass))).hexdigest(), refuses_broad_delete=True, exact_roots=sorted(str(path) for path in allowed), receipt_required=True)


def cleanup_targets(
    manifest: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    smoke_pass: Mapping[str, Any],
    confirm_exact: bool = False,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Delete only the exact roots reconstructed from signed smoke inputs."""

    validate_artifact(plan, expected_schema=schema("smoke_plan"), expected_cell="B4")
    validate_artifact(smoke_pass, expected_schema=schema("smoke_adjudication"), expected_cell="B4")
    artifact_root, roots = _signed_smoke_roots(plan)
    expected_manifest = build_smoke_cleanup_manifest(
        artifact_root,
        plan=plan,
        smoke_pass=smoke_pass,
        targets=tuple(roots.values()),
    )
    if canonical_json_bytes(dict(manifest)) != canonical_json_bytes(expected_manifest):
        raise V21BError("cleanup manifest is not the canonical signed plan/smoke lineage")
    validate_artifact(manifest, expected_schema=schema("smoke_cleanup"), expected_cell="B4")
    if confirm_exact is not True:
        raise V21BError("cleanup requires explicit confirm_exact=True")
    targets = manifest.get("targets")
    exact_roots_value = manifest.get("exact_roots")
    if not isinstance(targets, list) or not targets or not isinstance(exact_roots_value, list):
        raise V21BError("cleanup manifest has no exact targets")
    if receipt_path is None:
        raise V21BError("cleanup requires a receipt path outside the deleted roots")
    receipt = Path(receipt_path).resolve()
    exact_roots = {_canonical_path(path, label="exact root") for path in exact_roots_value}
    target_paths = [_canonical_path(path, label="cleanup target") for path in targets]
    if len(exact_roots) != 3 or len(target_paths) != 3 or set(target_paths) != exact_roots:
        raise V21BError("cleanup manifest targets must equal the exact three roots before deletion")
    if any(root == receipt or root in receipt.parents for root in exact_roots):
        raise V21BError("cleanup receipt must be outside every deleted root")
    if receipt.exists() or receipt.is_symlink():
        raise V21BError(f"refusing to overwrite cleanup receipt: {receipt}")
    for path in target_paths:
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_dir():
                raise V21BError(f"cleanup target is not an exact directory: {path}")
    for path in target_paths:
        if path.exists() or path.is_symlink():
            shutil.rmtree(path)
        if path.exists() or path.is_symlink():
            raise V21BError(f"cleanup target remains after deletion: {path}")
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
