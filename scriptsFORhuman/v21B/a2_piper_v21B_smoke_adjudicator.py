"""Strict adjudication for the one B4 smoke attempt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ._v21b_common import V21BError, canonical_json_bytes, sha256_file
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact
from .a2_piper_v21B_probe_runner import read_process_receipt
from .a2_piper_v21B_smoke_launcher import SMOKE_EVAL_REL, SMOKE_LAUNCHER_REL, SMOKE_TRAINING_REL


def _lower_sha256(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise V21BError(f"{label} must be a lowercase sha256 digest")
    return value


def _canonical_root(path_value: Any, *, label: str) -> Path:
    if not isinstance(path_value, str) or not path_value:
        raise V21BError(f"smoke {label} root is missing")
    path = Path(path_value)
    if not path.is_absolute():
        raise V21BError(f"smoke {label} root must be absolute")
    return path.resolve()


def _validate_exact_roots(plan: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    artifact_root = _canonical_root(plan.get("artifact_root"), label="artifact")
    if contract.get("artifact_root") != str(artifact_root):
        raise V21BError("smoke result contract artifact root is not bound to the plan")
    expected_roots = {
        "training_root": artifact_root / SMOKE_TRAINING_REL,
        "eval_root": artifact_root / SMOKE_EVAL_REL,
        "launcher_root": artifact_root / SMOKE_LAUNCHER_REL,
    }
    for key, expected in expected_roots.items():
        if _canonical_root(plan.get(key), label=key) != expected:
            raise V21BError(f"smoke plan {key} is not the canonical artifact root")
    expected_paths = {
        "aggregate_path": expected_roots["eval_root"] / "smoke_result.json",
        "raw_metrics_path": expected_roots["eval_root"] / "r2_training_metrics.jsonl",
        "checkpoint_path": expected_roots["training_root"] / "model_step_000010.pt",
    }
    for key, expected in expected_paths.items():
        if _canonical_root(contract.get(key), label=key) != expected:
            raise V21BError(f"smoke result contract {key} is not canonical")
    process_root = expected_roots["launcher_root"] / "process"
    if _canonical_root(plan.get("process_root"), label="process") != process_root:
        raise V21BError("smoke process root is not the canonical launcher child")
    if _canonical_root(plan.get("process_receipt_path"), label="process receipt") != process_root / "process_receipt.json":
        raise V21BError("smoke process receipt path is not canonical")


def adjudicate_b4_smoke(plan: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(plan, expected_schema=schema("smoke_plan"), expected_cell="B4")
    if isinstance(plan.get("physical_gpu"), bool) or not isinstance(plan.get("physical_gpu"), int) or plan.get("physical_gpu") != 3:
        raise V21BError("B4 smoke adjudication requires the exact physical GPU3")
    if plan.get("num_envs") != 64 or plan.get("batches") != 10 or plan.get("save_frequency") != 10 or plan.get("one_cell_only") is not True:
        raise V21BError("smoke plan dimensions are not exactly B4/64/10/save10")
    forbidden_fields = ("full_evidence", "run_uuid", "terminal_export_root", "terminal_path", "terminal_record")
    if any(field in plan for field in forbidden_fields) or any(field in plan.get("result_contract", {}) for field in forbidden_fields) or any(any(field in token for field in ("a2_v20_R2_full_evidence", "a2_v21B_run_uuid", "terminal_export")) for token in plan.get("command", [])):
        raise V21BError("smoke plan contains forbidden terminal/full-trace identity")
    if not isinstance(result, Mapping) or result.get("cell") != "B4":
        raise V21BError("smoke result must bind B4")
    if any(field in result for field in forbidden_fields):
        raise V21BError("smoke result contains forbidden terminal/full-trace identity")
    unsigned_plan = dict(plan)
    unsigned_plan.pop("plan_sha256", None)
    expected_plan_sha = hashlib.sha256(canonical_json_bytes(unsigned_plan)).hexdigest()
    if plan.get("plan_sha256") != expected_plan_sha:
        raise V21BError("smoke plan digest is invalid")
    contract = plan.get("result_contract")
    if not isinstance(contract, Mapping):
        raise V21BError("B4 smoke plan result contract is missing")
    _validate_exact_roots(plan, contract)
    aggregate_path = Path(contract["aggregate_path"]).absolute()
    if aggregate_path.is_symlink() or not aggregate_path.is_file():
        raise V21BError("B4 smoke persisted aggregate is missing or non-regular")
    try:
        persisted_bytes = aggregate_path.read_bytes()
        persisted = json.loads(persisted_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V21BError("B4 smoke persisted aggregate is not valid JSON") from exc
    if not isinstance(persisted, Mapping) or persisted_bytes != canonical_json_bytes(dict(persisted)) + b"\n":
        raise V21BError("B4 smoke persisted aggregate is not canonical immutable JSON")
    if canonical_json_bytes(dict(result)) != canonical_json_bytes(dict(persisted)):
        raise V21BError("B4 smoke caller result differs from persisted aggregate")
    result = dict(persisted)
    required = (
        "schema", "producer_state", "plan_sha256", "result_path", "process_receipt_path",
        "process_exit_code", "process_natural_exit", "completed_batches", "batch_indices",
        "training_metrics_path", "training_metrics_file_sha256", "training_metrics",
        "checkpoint", "source_bindings", "repo_commit", "repo_tree", "cell", "seed",
        "source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256",
        "source_lock_file_sha256", "materialization_sha256", "materialized_config_sha256", "adaptation_bundle_sha256",
    )
    if any(key not in result for key in required):
        raise V21BError("smoke result is missing an actual collected evidence field")
    if result.get("schema") != "a2_piper_base_v21B_smoke_result_v1" or result.get("producer_state") != "AGGREGATED_AFTER_CHILD_EXIT":
        raise V21BError("smoke result must be the producer aggregate, not a synthetic status mapping")
    if result.get("plan_sha256") != plan["plan_sha256"] or result.get("process_exit_code") != 0 or result.get("process_natural_exit") is not True or result.get("completed_batches") != 10 or result.get("batch_indices") != list(range(1, 11)):
        raise V21BError("B4 smoke process/result did not complete the exact 10-batch contract")
    if result.get("source_bindings") != plan.get("source_bindings") or result.get("repo_commit") != plan.get("repo_commit") or result.get("repo_tree") != plan.get("repo_tree") or result.get("cell") != plan.get("cell") or result.get("seed") != plan.get("seed"):
        raise V21BError("B4 smoke result provenance is not bound to the signed plan")
    if result.get("materialization_phase") != plan.get("materialization_phase") or result.get("materialization_phase") != "FORMAL_PROMOTED":
        raise V21BError("B4 smoke materialization phase is not FORMAL_PROMOTED")
    _lower_sha256(result.get("adaptation_bundle_sha256"), label="B4 smoke adaptation identity")
    for key in ("source_checkpoint_sha256", "source_lock_sha256", "source_lock_file_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256", "adaptation_bundle_sha256"):
        if result.get(key) != plan.get(key):
            raise V21BError(f"B4 smoke result {key} identity is not bound to the signed plan")
    if result.get("result_path") != contract.get("aggregate_path") or result.get("training_metrics_path") != contract.get("raw_metrics_path"):
        raise V21BError("B4 smoke aggregate paths are not bound to the signed result contract")
    metrics_path = Path(result["training_metrics_path"]).absolute()
    if metrics_path.is_symlink() or not metrics_path.is_file() or sha256_file(metrics_path) != result["training_metrics_file_sha256"]:
        raise V21BError("B4 smoke training metrics artifact is missing or changed")
    metrics = result["training_metrics"]
    if not isinstance(metrics, list) or len(metrics) != 10 or any(not isinstance(row, Mapping) for row in metrics) or [row["batch_index"] for row in metrics] != list(range(1, 11)):
        raise V21BError("B4 smoke aggregate does not contain the exact ten producer metric rows")
    checkpoint = result["checkpoint"]
    checkpoint_value = checkpoint.get("path") if isinstance(checkpoint, Mapping) else None
    if not isinstance(checkpoint_value, str) or checkpoint_value != contract.get("checkpoint_path") or checkpoint_value.rsplit("/", 1)[-1] != "model_step_000010.pt":
        raise V21BError("B4 smoke step10 checkpoint identity is invalid")
    checkpoint_path = Path(checkpoint_value).absolute()
    if checkpoint_path.is_symlink() or not checkpoint_path.is_file() or sha256_file(checkpoint_path) != checkpoint.get("sha256"):
        raise V21BError("B4 smoke step10 checkpoint is missing or changed")
    process_receipt_path = Path(result["process_receipt_path"]).absolute()
    if process_receipt_path != Path(plan.get("process_receipt_path", "")).absolute():
        raise V21BError("B4 smoke process receipt path is not bound to the plan")
    read_process_receipt(
        process_receipt_path,
        repo_root=Path(plan.get("repo_root", Path.cwd())).absolute(),
        expected_command_sha256=plan["command_sha256"],
        expected_result_paths=[Path(contract["aggregate_path"]).absolute()],
        expected_source_bindings=plan.get("source_bindings"),
        expected_plan_sha256=plan["plan_sha256"],
        expected_git_commit=plan.get("repo_commit"),
        expected_git_tree=plan.get("repo_tree"),
        expected_physical_gpu=plan.get("physical_gpu"),
        expected_result_contract=contract,
        require_natural_exit=True,
    )
    return artifact_payload("smoke_adjudication", status="SMOKE_PASS", cell="B4", seed=0, plan_sha256=plan["plan_sha256"], command_sha256=plan["command_sha256"], adaptation_bundle_sha256=plan["adaptation_bundle_sha256"], materialization_phase=plan["materialization_phase"], materialization_sha256=plan["materialization_sha256"], materialized_config_sha256=plan["materialized_config_sha256"], source_checkpoint_sha256=plan["source_checkpoint_sha256"], source_lock_sha256=plan["source_lock_sha256"], source_lock_file_sha256=plan["source_lock_file_sha256"], source_config_sha256=plan["source_config_sha256"], artifact_root=plan["artifact_root"], training_root=plan["training_root"], eval_root=plan["eval_root"], launcher_root=plan["launcher_root"], result=dict(result), runtime_level="RUNTIME_SMOKE_PASS")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["adjudicate_b4_smoke", "main"]
