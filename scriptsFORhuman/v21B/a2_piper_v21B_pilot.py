"""Single B4 pilot planning and adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

from ._v21b_common import V21BError, canonical_json_bytes, sha256_file
from .a2_piper_v21B_adaptation import validate_materialized_config_receipt
from .a2_piper_v21B_probe_runner import hash_command_env, observed_git_identity, read_process_receipt
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact
from .a2_piper_v21B_source_freeze import validate_source_lock


V21B_PILOT_METRIC_KEYS = (
    "send_latch_fire_rate", "hinge_at_send_latch_rad", "hinge_at_crossing_rad",
    "send_to_cross_steps", "stage_overtime_rate", "upper_dof_overspeed_rate",
    "arm_clipped_utilization", "arm_clipped_utilization_valid_rate", "finite_data",
    "decomposition_sanity", "decomposition_sanity_valid_rate",
)
V21B_PILOT_METRIC_SOURCES = {name: f"a2_v21B_{name}" for name in V21B_PILOT_METRIC_KEYS}
V21B_PILOT_COVERAGE_KEYS = (
    "arm_clipped_utilization_valid_rate",
    "decomposition_sanity_valid_rate",
)


def build_b4_pilot_plan(
    repo_root: Path,
    *,
    arm_realistic_limit_nm: float,
    output_root: Path,
    materialization: Mapping[str, Any],
    materialized_config: Path,
    source_lock_path: Path,
    source_checkpoint_sha256: str | None = None,
    source_lock_sha256: str | None = None,
    source_config_sha256: str | None = None,
) -> dict[str, Any]:
    if isinstance(arm_realistic_limit_nm, bool) or not isinstance(arm_realistic_limit_nm, (int, float)) or not math.isfinite(float(arm_realistic_limit_nm)) or float(arm_realistic_limit_nm) <= 0.0:
        raise V21BError("B4 pilot requires a positive signed ARM_REALISTIC limit")
    receipt = validate_materialized_config_receipt(materialization, materialized_config, cell="B4", phase="POST_CENSUS")
    selected_limit = float(receipt["config"]["v21b_arm_realistic_effort_limit_nm"])
    if float(arm_realistic_limit_nm) != selected_limit:
        raise V21BError("B4 pilot limit must exactly match the POST_CENSUS B4 receipt")
    if source_checkpoint_sha256 is not None and source_checkpoint_sha256 != materialization.get("source_checkpoint_sha256"):
        raise V21BError("B4 pilot source checkpoint override disagrees with the receipt")
    if source_lock_sha256 is not None and source_lock_sha256 != materialization.get("source_lock_sha256"):
        raise V21BError("B4 pilot source lock override disagrees with the receipt")
    if source_config_sha256 is not None and source_config_sha256 != receipt["source_config_sha256"]:
        raise V21BError("B4 pilot source config override disagrees with the B4 template binding")
    config = Path(receipt["path"])
    output = Path(output_root).absolute()
    process_root = output / "process"
    training_root = output / "training"
    result_path = output / "pilot_result.json"
    checkpoint_paths = [training_root / f"model_step_{step:06d}.pt" for step in (250, 500, 750)]
    source_lock_file = Path(source_lock_path).absolute()
    if not source_lock_file.is_file() or source_lock_file.is_symlink():
        raise V21BError("B4 pilot requires a regular source-lock artifact bound to the POST_CENSUS receipt")
    try:
        source_lock_payload = json.loads(source_lock_file.read_text(encoding="utf-8"))
        validate_source_lock(source_lock_payload, repo_root, require_current=True)
    except (OSError, ValueError, TypeError, V21BError) as exc:
        raise V21BError("B4 pilot source-lock artifact is invalid or stale") from exc
    if source_lock_payload.get("source_lock_sha256") != materialization["source_lock_sha256"]:
        raise V21BError("B4 pilot source-lock digest does not match the POST_CENSUS receipt")
    raw_metrics_path = training_root / "r2_training_metrics.jsonl"
    git_identity = observed_git_identity(repo_root)
    argv = [
        sys.executable, "-m", "gr00t.rl.train_agent_trl", f"--config-dir={config.parent}", f"--config-name={config.stem}",
        "checkpoint=logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G4-20260731_004712/model_step_002500.pt",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true", "num_envs=256", "seed=0",
        "algo.trl.num_total_batches=750", "callbacks.model_save.save_frequency=250",
        "env.config.a2_v21B_materialization_phase=POST_CENSUS", "env.config.a2_v21B_formal_launch=false", f"experiment_dir={training_root}",
        "+r2_evidence_enabled=true", f"+r2_source_lock_path={source_lock_file}", f"+r2_training_metrics_path={raw_metrics_path}", f"+env.config.a2_v21B_run_uuid=v21B-pilot-B4", f"+env.config.a2_v21B_pilot_checkpoint_root={training_root}",
        f"+env.config.a2_v21B_materialization_sha256={receipt['materialization_sha256']}",
        f"+env.config.a2_v21B_materialized_config_sha256={receipt['materialized_config_sha256']}",
        f"env.config.a2_v21B_source_checkpoint_sha256={materialization['source_checkpoint_sha256']}",
        f"env.config.a2_v21B_source_lock_sha256={materialization['source_lock_sha256']}",
        f"env.config.a2_v21B_source_config_sha256={receipt['source_config_sha256']}",
    ]
    env = {"CUDA_VISIBLE_DEVICES": "3", "WANDB_MODE": "offline"}
    source_bindings = {"source_checkpoint_sha256": materialization["source_checkpoint_sha256"], "source_lock_sha256": materialization["source_lock_sha256"], "source_config_sha256": receipt["source_config_sha256"], "materialization_sha256": receipt["materialization_sha256"], "materialized_config_sha256": receipt["materialized_config_sha256"]}
    # Process parent hashes identify the actual files consumed by the launcher;
    # logical source-lock/materialization digests remain separately bound in
    # ``source_bindings`` and the result contract.
    parent_hashes = {"source_lock": sha256_file(source_lock_file), "materialized_config": sha256_file(config)}
    result_contract = {"kind": "pilot_metrics", "aggregate_path": str(result_path.absolute()), "raw_metrics_path": str(raw_metrics_path.absolute()), "source_lock_path": str(source_lock_file), "source_lock_sha256": materialization["source_lock_sha256"], "source_lock_file_sha256": sha256_file(source_lock_file), "checkpoint_paths": [str(path.absolute()) for path in checkpoint_paths], "arm_realistic_limit_nm": selected_limit, "materialization_phase": receipt["phase"], "materialization_sha256": receipt["materialization_sha256"], "materialized_config_sha256": receipt["materialized_config_sha256"], "source_checkpoint_sha256": materialization["source_checkpoint_sha256"], "source_config_sha256": receipt["source_config_sha256"], "repo_commit": git_identity["commit"], "repo_tree": git_identity["tree"]}
    payload = artifact_payload("pilot", status="STATIC_PASS", cell="B4", num_envs=256, batches=750, save_frequency=250, seed=0, arm_realistic_limit_nm=selected_limit, argv=argv, env=env, command_sha256=hash_command_env(argv, env), gpu=3, process_root=str(process_root), process_receipt_path=str(process_root / "process_receipt.json"), result_paths=[str(result_path)], checkpoint_paths=[str(path) for path in checkpoint_paths], raw_metrics_path=str(raw_metrics_path), source_lock_path=str(source_lock_file), source_lock_file_sha256=sha256_file(source_lock_file), result_contract=result_contract, source_bindings=source_bindings, parent_hashes=parent_hashes, repo_commit=git_identity["commit"], repo_tree=git_identity["tree"], run_uuid="v21B-pilot-B4", required_metrics=list(V21B_PILOT_METRIC_KEYS), metric_sources=dict(V21B_PILOT_METRIC_SOURCES), materialization_phase=receipt["phase"], materialization_sha256=receipt["materialization_sha256"], materialized_config_sha256=receipt["materialized_config_sha256"], effort_limit_vector_6d=receipt["effort_limit_vector_6d"], materialized_config_path=str(config), source_checkpoint_sha256=materialization["source_checkpoint_sha256"], source_lock_sha256=materialization["source_lock_sha256"], source_config_sha256=receipt["source_config_sha256"])
    payload["plan_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return validate_artifact(payload, expected_schema=schema("pilot"), expected_cell="B4")


def _pilot_plan_digest(plan: Mapping[str, Any]) -> None:
    validate_artifact(plan, expected_schema=schema("pilot"), expected_cell="B4")
    unsigned = dict(plan)
    unsigned.pop("plan_sha256", None)
    if plan.get("status") != "STATIC_PASS" or plan.get("plan_sha256") != hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest():
        raise V21BError("B4 pilot plan digest/status is invalid")


def _finite_payload(value: Any, *, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise V21BError(f"B4 pilot raw metric is non-finite at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _finite_payload(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _finite_payload(child, path=f"{path}[{index}]")


def adjudicate_b4_pilot(
    metrics: Mapping[str, Any] | None = None,
    *,
    plan: Mapping[str, Any],
    process_receipt_path: Path | None = None,
    result_path: Path | None = None,
    receipt_path: Path | None = None,
    result_artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Recompute F4 from the receipt-bound 750-batch producer result."""

    if metrics is not None:
        raise V21BError("B4 pilot rejects caller-supplied metrics; provide producer receipt/result paths")
    _pilot_plan_digest(plan)
    receipt_path = Path(process_receipt_path or receipt_path or plan["process_receipt_path"])
    result_file = Path(result_path or result_artifact_path or plan["result_paths"][0])
    receipt = read_process_receipt(receipt_path, repo_root=Path(__file__).resolve().parents[2], expected_command_sha256=plan["command_sha256"], expected_env=plan["env"], expected_result_paths=(result_file,), expected_parent_hashes=plan.get("parent_hashes"), expected_source_bindings=plan.get("source_bindings"), expected_plan_sha256=plan["plan_sha256"], expected_git_commit=plan.get("repo_commit"), expected_git_tree=plan.get("repo_tree"), expected_physical_gpu=plan.get("gpu"), expected_result_contract=plan.get("result_contract"), require_natural_exit=True)
    if receipt.get("plan_sha256") != plan["plan_sha256"]:
        raise V21BError("B4 pilot process receipt is not bound to the signed plan")
    receipt_sha256 = sha256_file(receipt_path)
    if not result_file.is_file() or result_file.is_symlink():
        raise V21BError("B4 pilot result must be a regular non-symlink file")
    try:
        result = json.loads(result_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V21BError("B4 pilot result is not valid JSON") from exc
    if not isinstance(result, Mapping) or result.get("schema") != "a2_piper_base_v21B_pilot_result_v1" or result.get("producer_state") != "AGGREGATED_AFTER_CHILD_EXIT" or result.get("plan_sha256") != plan["plan_sha256"] or result.get("result_path") != str(result_file.absolute()) or result.get("arm_realistic_limit_nm") != plan["arm_realistic_limit_nm"]:
        raise V21BError("B4 pilot result is not bound to the exact plan/receipt/path")
    if result.get("process_receipt_sha256") is not None and result.get("process_receipt_sha256") != receipt_sha256:
        raise V21BError("B4 pilot producer receipt digest disagrees with consumed receipt")
    for key in ("materialization_phase", "materialization_sha256", "materialized_config_sha256", "source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256", "raw_metrics_path", "source_lock_path", "source_lock_file_sha256"):
        if result.get(key) != plan.get(key):
            raise V21BError(f"B4 pilot producer result {key} is not bound to the plan")
    if result.get("repo_commit") != plan.get("repo_commit") or result.get("repo_tree") != plan.get("repo_tree"):
        raise V21BError("B4 pilot producer Git identity is not bound to the plan")
    batches = result.get("batches")
    if not isinstance(batches, list) or len(batches) != 750 or result.get("completed_batches") != 750 or result.get("batch_indices") != list(range(1, 751)):
        raise V21BError("B4 pilot producer result must contain contiguous batches 1..750")
    required_metrics = tuple(plan.get("required_metrics", V21B_PILOT_METRIC_KEYS))
    if required_metrics != V21B_PILOT_METRIC_KEYS or plan.get("metric_sources") != V21B_PILOT_METRIC_SOURCES:
        raise V21BError("B4 pilot plan metric schema is not the v21-B producer mapping")
    metric_sums = {key: 0.0 for key in required_metrics if key not in ("finite_data", "decomposition_sanity")}
    finite_data_pass = True
    decomposition_sanity_pass = True
    raw_metrics: list[dict[str, Any]] = []
    for index, batch in enumerate(batches, start=1):
        if not isinstance(batch, Mapping) or batch.get("batch_index") != index or not isinstance(batch.get("metrics"), Mapping):
            raise V21BError("B4 pilot batch record is malformed or out of order")
        metrics_row = dict(batch["metrics"])
        if batch.get("schema") != "a2_piper_base_v21B_training_metric_v1" or batch.get("producer_state") != "PROCESS_COMPLETED" or batch.get("scientific_plan_id") != "base_v21B_theta_arm_ablation_v1" or batch.get("source_lock_sha256") != plan["source_lock_sha256"] or batch.get("source_lock_file_sha256") != plan["source_lock_file_sha256"] or batch.get("git_commit") != plan["repo_commit"] or batch.get("git_tree") != plan["repo_tree"] or batch.get("metric_sources") != V21B_PILOT_METRIC_SOURCES or set(metrics_row) != set(required_metrics):
            raise V21BError("B4 pilot batch is not bound to the v21-B metric producer schema")
        _finite_payload(metrics_row, path=f"$.batches[{index - 1}].metrics")
        for key in metric_sums:
            value = metrics_row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise V21BError(f"B4 pilot raw metric {key} must be finite numeric data")
            metric_sums[key] += float(value)
        for key in ("send_latch_fire_rate", "stage_overtime_rate", "upper_dof_overspeed_rate", "arm_clipped_utilization"):
            if not 0.0 <= float(metrics_row[key]) <= 1.0:
                raise V21BError(f"B4 pilot raw metric {key} must be in [0,1]")
        if not (metrics_row.get("finite_data") is True or metrics_row.get("finite_data") == 1.0) or not (metrics_row.get("decomposition_sanity") is True or metrics_row.get("decomposition_sanity") == 1.0):
            raise V21BError("B4 pilot producer reported a failed finite/decomposition sanity flag")
        for key in V21B_PILOT_COVERAGE_KEYS:
            value = metrics_row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) != 1.0:
                raise V21BError(f"B4 pilot producer coverage {key} must equal 1.0")
        finite_data_pass &= metrics_row.get("finite_data") is True or metrics_row.get("finite_data") == 1.0
        decomposition_sanity_pass &= metrics_row.get("decomposition_sanity") is True or metrics_row.get("decomposition_sanity") == 1.0
        raw_metrics.append(metrics_row)
    averages = {key: value / 750.0 for key, value in metric_sums.items()}
    rate = averages["send_latch_fire_rate"]
    checkpoints = result.get("checkpoints")
    if not isinstance(checkpoints, list) or {item.get("step") for item in checkpoints if isinstance(item, Mapping)} != {250, 500, 750}:
        raise V21BError("B4 pilot producer must provide checkpoints 250/500/750")
    checkpoint_hashes: dict[str, str] = {}
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, Mapping) or checkpoint.get("step") not in (250, 500, 750) or not isinstance(checkpoint.get("path"), str) or not isinstance(checkpoint.get("sha256"), str):
            raise V21BError("B4 pilot checkpoint identity is malformed")
        path = Path(checkpoint["path"])
        if not path.is_file() or path.is_symlink() or sha256_file(path) != checkpoint["sha256"]:
            raise V21BError("B4 pilot checkpoint hash/path is invalid")
        expected_path = Path(plan["checkpoint_paths"][((checkpoint["step"] // 250) - 1)])
        if path.absolute() != expected_path.absolute():
            raise V21BError("B4 pilot checkpoint path is not bound to the plan")
        checkpoint_hashes[str(checkpoint["step"])] = checkpoint["sha256"]
    summary = {**averages, "send_latch_fire_rate": rate, "finite_data": finite_data_pass, "decomposition_sanity": decomposition_sanity_pass, "batch_count": 750, "checkpoint_sha256": checkpoint_hashes}
    drop_theta = rate < 0.60
    return validate_artifact(artifact_payload("pilot", status="PILOT_COMPLETE", cell="B4", metrics=summary, raw_batch_metrics=raw_metrics, send_latch_fire_rate=rate, fork_f4_theta_downgrade=drop_theta, adaptation_required=True, arm_realistic_limit_nm=float(plan["arm_realistic_limit_nm"]), plan_sha256=plan["plan_sha256"], command_sha256=plan["command_sha256"], receipt_sha256=receipt_sha256, result_sha256=sha256_file(result_file), selected_k_nm=float(plan["arm_realistic_limit_nm"]), materialization_phase=plan["materialization_phase"], materialization_sha256=plan["materialization_sha256"], materialized_config_sha256=plan["materialized_config_sha256"], effort_limit_vector_6d=plan["effort_limit_vector_6d"], source_checkpoint_sha256=plan["source_checkpoint_sha256"], source_lock_sha256=plan["source_lock_sha256"], source_config_sha256=plan["source_config_sha256"]))


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--arm-realistic-limit-nm", type=float, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--materialization", type=Path, required=True)
    parser.add_argument("--materialized-config", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    args = parser.parse_args(argv)
    import json
    materialization = json.loads(args.materialization.read_text(encoding="utf-8"))
    print(json.dumps(build_b4_pilot_plan(args.repo_root, arm_realistic_limit_nm=args.arm_realistic_limit_nm, output_root=args.output_root, materialization=materialization, materialized_config=args.materialized_config, source_lock_path=args.source_lock), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_b4_pilot_plan", "adjudicate_b4_pilot", "main"]
