"""Single B4 64-env/10-batch smoke plan (no implicit multi-cell launch)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

from ._v21b_common import V21BError, V21B_WARM_START_PATH, canonical_json_bytes, read_yaml, sha256_file, validate_v21b_config
from .a2_piper_v21B_adaptation import validate_materialized_config_receipt
from .a2_piper_v21B_probe_runner import hash_command_env
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact
from .a2_piper_v21B_source_freeze import validate_source_lock


SMOKE_TRAINING_REL = "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v21B/B4"
SMOKE_EVAL_REL = "logs_eval/base_v21B/smoke/B4"
SMOKE_LAUNCHER_REL = "logs_rl/launchers/base_v21B_smoke/B4"
V21B_PYTHON = "/home/baoquanc/anaconda3/envs/isaaclab/bin/python"


def _git_identity(repo_root: Path) -> dict[str, str]:
    identity: dict[str, str] = {}
    for key, expression in (("commit", "HEAD"), ("tree", "HEAD^{tree}")):
        try:
            value = subprocess.check_output(
                ["git", "rev-parse", expression],
                cwd=repo_root,
                text=True,
                stderr=subprocess.PIPE,
            ).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise V21BError(f"B4 smoke cannot resolve current Git {key}") from exc
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
            raise V21BError(f"B4 smoke Git {key} identity is invalid: {value!r}")
        identity[key] = value
    return identity


def build_b4_smoke_plan(
    repo_root: Path,
    *,
    adaptation: Mapping[str, Any],
    p0_admission: Mapping[str, Any],
    materialization: Mapping[str, Any],
    materialized_config: Path,
    source_lock_path: Path,
    output_root: Path | None = None,
    artifact_root: Path | None = None,
    gpu: int = 3,
) -> dict[str, Any]:
    if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu != 3:
        raise V21BError("B4 smoke requires the exact physical GPU3")
    validate_artifact(adaptation, expected_schema=schema("adaptation"), expected_cell=None)
    validate_artifact(p0_admission, expected_schema=schema("p0_admission"))
    validate_artifact(materialization, expected_schema=schema("materialization"))
    adaptation_sha256 = hashlib.sha256(canonical_json_bytes(dict(adaptation))).hexdigest()
    declared_adaptation = materialization.get("adaptation_bundle_sha256")
    if materialization.get("phase") != "FORMAL_PROMOTED" or not isinstance(declared_adaptation, str) or len(declared_adaptation) != 64 or any(char not in "0123456789abcdef" for char in declared_adaptation) or declared_adaptation != adaptation_sha256:
        raise V21BError("B4 smoke requires a signed FORMAL_PROMOTED materialization bound to adaptation")
    receipt = validate_materialized_config_receipt(materialization, Path(materialized_config), cell="B4", phase="FORMAL_PROMOTED")
    config_path = Path(receipt["path"])
    loaded = receipt["config"]
    root = repo_root.resolve()
    artifact_base = (Path(artifact_root) if artifact_root is not None else root).resolve()
    source_lock_file = Path(source_lock_path).absolute()
    if source_lock_file.is_symlink() or not source_lock_file.is_file():
        raise V21BError(f"B4 smoke source lock must be a regular file: {source_lock_file}")
    try:
        source_lock = json.loads(source_lock_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V21BError("B4 smoke source lock is not valid JSON") from exc
    if not isinstance(source_lock, Mapping):
        raise V21BError("B4 smoke source lock must be a mapping")
    validate_source_lock(dict(source_lock), root, require_current=True)
    source_lock_sha256 = source_lock.get("source_lock_sha256")
    expected_source_lock = materialization.get("source_lock_sha256")
    for label, value in (
        ("materialization", expected_source_lock),
        ("P0 admission", p0_admission.get("source_lock_sha256")),
        ("adaptation", adaptation.get("source_lock_sha256")),
    ):
        if value != source_lock_sha256:
            raise V21BError(f"B4 smoke source-lock binding disagrees with {label}")
    if not isinstance(source_lock_sha256, str):
        raise V21BError("B4 smoke source-lock digest is missing")
    source_lock_file_sha256 = sha256_file(source_lock_file)
    config = config_path
    training_root = artifact_base / SMOKE_TRAINING_REL
    if output_root is not None and Path(output_root).resolve() != training_root:
        raise V21BError("B4 smoke output_root must equal the canonical artifact training root")
    eval_root = artifact_base / SMOKE_EVAL_REL
    launcher_root = artifact_base / SMOKE_LAUNCHER_REL
    training_metrics_path = eval_root / "r2_training_metrics.jsonl"
    checkpoint_path = training_root / "model_step_000010.pt"
    result_path = eval_root / "smoke_result.json"
    process_root = launcher_root / "process"
    git_identity = _git_identity(root)
    argv = [
        "env", "-u", "CUDA_VISIBLE_DEVICES", f"ACCELERATE_TORCH_DEVICE=cuda:{gpu}", "WANDB_MODE=online", f"PYTHONPATH={root}", V21B_PYTHON, "-m", "gr00t.rl.train_agent_trl", f"--config-dir={config.parent}", f"--config-name={config.stem}",
        f"checkpoint={V21B_WARM_START_PATH}", "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true",
        "use_wandb=true",
        "num_envs=64", "seed=0", "algo.trl.num_total_batches=10", "callbacks.model_save.save_frequency=10",
        f"env.config.a2_v21B_adaptation_bundle_sha256={adaptation_sha256}",
        f"+v21b_adaptation_bundle_sha256={adaptation_sha256}",
        f"+env.config.a2_v21B_materialization_sha256={receipt['materialization_sha256']}",
        f"+env.config.a2_v21B_materialized_config_sha256={receipt['materialized_config_sha256']}",
        f"+v21b_materialization_sha256={receipt['materialization_sha256']}",
        f"+v21b_materialized_config_sha256={receipt['materialized_config_sha256']}",
        f"env.config.a2_v21B_source_checkpoint_sha256={materialization['source_checkpoint_sha256']}",
        f"env.config.a2_v21B_source_lock_sha256={materialization['source_lock_sha256']}",
        f"env.config.a2_v21B_source_config_sha256={receipt['source_config_sha256']}",
        "+env.config.a2_v21B_census_topology=canonical16",
        "+r2_evidence_enabled=true",
        f"+r2_source_lock_path={source_lock_file}",
        f"+r2_training_metrics_path={training_metrics_path}",
        f"experiment_dir={training_root}",
        "env.config.a2_v21B_formal_launch=true",
    ]
    source_bindings = {
        "source_checkpoint_sha256": materialization["source_checkpoint_sha256"],
        "source_lock_sha256": source_lock_sha256,
        "source_config_sha256": receipt["source_config_sha256"],
        "materialization_sha256": receipt["materialization_sha256"],
        "materialized_config_sha256": receipt["materialized_config_sha256"],
    }
    result_contract = {
        "kind": "smoke_evidence",
        "aggregate_path": str(result_path.absolute()),
        "raw_metrics_path": str(training_metrics_path.absolute()),
        "checkpoint_path": str(checkpoint_path.absolute()),
        "source_lock_path": str(source_lock_file),
        "source_lock_sha256": source_lock_sha256,
        "source_lock_file_sha256": source_lock_file_sha256,
        "source_checkpoint_sha256": materialization["source_checkpoint_sha256"],
        "source_bindings": source_bindings,
        "materialization_phase": "FORMAL_PROMOTED",
        "adaptation_bundle_sha256": adaptation_sha256,
        "materialization_sha256": receipt["materialization_sha256"],
        "materialized_config_sha256": receipt["materialized_config_sha256"],
        "source_config_sha256": receipt["source_config_sha256"],
        "repo_commit": git_identity["commit"],
        "repo_tree": git_identity["tree"],
        "repo_root": str(root),
        "artifact_root": str(artifact_base),
        "training_root": str(training_root),
        "eval_root": str(eval_root),
        "launcher_root": str(launcher_root),
        "cell": "B4",
        "seed": 0,
        "batch_count": 10,
        "checkpoint_step": 10,
    }
    payload = artifact_payload(
        "smoke_plan",
        status="SMOKE_PLAN_COMPLETE",
        cell="B4",
        physical_gpu=gpu,
        num_envs=64,
        batches=10,
        save_frequency=10,
        training_root=str(training_root),
        eval_root=str(eval_root),
        launcher_root=str(launcher_root),
        training_metrics_path=str(training_metrics_path),
        checkpoint_path=str(checkpoint_path),
        checkpoint_step=10,
        seed=0,
        checkpoint=V21B_WARM_START_PATH,
        checkpoint_load_mode="policy_only",
        auto_load_latest=False,
        adaptation_bundle_sha256=adaptation_sha256,
        materialization_phase="FORMAL_PROMOTED",
        p0_admission_sha256=hashlib.sha256(canonical_json_bytes(dict(p0_admission))).hexdigest(),
        source_checkpoint_sha256=materialization["source_checkpoint_sha256"],
        source_lock_sha256=source_lock_sha256,
        source_lock_path=str(source_lock_file),
        source_lock_file_sha256=source_lock_file_sha256,
        source_config_sha256=receipt["source_config_sha256"],
        materialization_sha256=receipt["materialization_sha256"],
        materialized_config_sha256=receipt["materialized_config_sha256"],
        materialized_config_path=str(config_path),
        command_sha256=hash_command_env(argv, {}),
        wandb_mode="online",
        command=argv,
        one_cell_only=True,
        canonical_root_contract={"training": SMOKE_TRAINING_REL, "eval": SMOKE_EVAL_REL, "launcher": SMOKE_LAUNCHER_REL},
        result_paths=[str(result_path.absolute())],
        result_contract=result_contract,
        source_bindings=source_bindings,
        parent_hashes={"source_lock": source_lock_file_sha256, "materialized_config": sha256_file(config_path)},
        process_root=str(process_root),
        process_receipt_path=str(process_root / "process_receipt.json"),
        repo_root=str(root),
        artifact_root=str(artifact_base),
        repo_commit=git_identity["commit"],
        repo_tree=git_identity["tree"],
    )
    payload["plan_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return validate_artifact(payload, expected_schema=schema("smoke_plan"), expected_cell="B4")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["SMOKE_TRAINING_REL", "SMOKE_EVAL_REL", "SMOKE_LAUNCHER_REL", "V21B_PYTHON", "build_b4_smoke_plan", "main"]
