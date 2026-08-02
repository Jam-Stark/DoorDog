"""Seven-cell v21-B formal launch plan in one dedicated tmux session.

This module only builds and validates the command contract.  A caller must
explicitly invoke its launch function under the separately leased GPU/tmux
runtime; importing or planning never starts a process.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

import hashlib

from ._v21b_common import V21B_CELL_ORDER, V21B_CONFIG_PATHS, V21BError, V21B_FORMAL_GPUS, V21B_WARM_START_PATH, canonical_json_bytes, parse_gpus, read_yaml, sha256_file, validate_v21b_config
from .a2_piper_v21B_adaptation import materialized_profile_overrides
from .a2_piper_v21B_adaptation import validate_materialized_config_receipt
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact
from .a2_piper_v21B_source_freeze import validate_source_lock


FORMAL_SESSION = "base_v21B_formal_v1"
FORMAL_TRAINING_REL = "logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal"
FORMAL_LAUNCHER_REL = "logs_rl/launchers/base_v21B/formal"
SMOKE_TRAINING_REL = "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v21B/B4"
SMOKE_EVAL_REL = "logs_eval/base_v21B/smoke/B4"
SMOKE_LAUNCHER_REL = "logs_rl/launchers/base_v21B_smoke/B4"


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
            raise V21BError(f"formal launch cannot resolve current Git {key}") from exc
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
            raise V21BError(f"formal launch Git {key} identity is invalid: {value!r}")
        identity[key] = value
    return identity


def _validate_cleanup_receipt(cleanup_pass: Mapping[str, Any], *, smoke_pass: Mapping[str, Any]) -> str:
    receipt_value = cleanup_pass.get("receipt_path")
    if not isinstance(receipt_value, str) or not receipt_value:
        raise V21BError("formal launch cleanup receipt path is missing")
    receipt_path = Path(receipt_value).absolute()
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise V21BError("formal launch cleanup receipt must be a regular non-symlink file")
    try:
        raw = receipt_path.read_bytes()
        persisted = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V21BError("formal launch cleanup receipt is not valid JSON") from exc
    if not isinstance(persisted, Mapping) or raw != canonical_json_bytes(dict(persisted)) + b"\n":
        raise V21BError("formal launch cleanup receipt bytes are not canonical")
    if dict(persisted) != dict(cleanup_pass):
        raise V21BError("formal launch cleanup receipt differs from supplied CLEANUP_PASS")
    if cleanup_pass.get("status") != "CLEANUP_PASS" or cleanup_pass.get("all_targets_absent") is not True:
        raise V21BError("formal launch cleanup receipt does not prove all targets are absent")
    artifact_root_value = smoke_pass.get("artifact_root")
    if not isinstance(artifact_root_value, str) or not artifact_root_value or not Path(artifact_root_value).is_absolute():
        raise V21BError("formal launch smoke artifact root is missing")
    artifact_root = Path(artifact_root_value).resolve()
    expected_roots = {
        artifact_root / SMOKE_TRAINING_REL,
        artifact_root / SMOKE_EVAL_REL,
        artifact_root / SMOKE_LAUNCHER_REL,
    }
    deleted = cleanup_pass.get("deleted_paths")
    if not isinstance(deleted, list) or {Path(item).absolute() for item in deleted if isinstance(item, str)} != expected_roots or len(deleted) != 3:
        raise V21BError("formal launch cleanup receipt does not name the exact three smoke roots")
    if any(root.exists() or root.is_symlink() for root in expected_roots):
        raise V21BError("formal launch cleanup receipt is stale because a smoke root still exists")
    if cleanup_pass.get("smoke_pass_sha256") != hashlib.sha256(canonical_json_bytes(dict(smoke_pass))).hexdigest():
        raise V21BError("formal launch cleanup receipt is bound to a different smoke adjudication")
    return hashlib.sha256(raw).hexdigest()


def build_formal_launch_plan(repo_root: Path, *, adaptation: Mapping[str, Any], p0_admission: Mapping[str, Any], smoke_pass: Mapping[str, Any], cleanup_pass: Mapping[str, Any], materialization: Mapping[str, Any], source_lock_path: Path, physical_gpus: tuple[int, ...] = V21B_FORMAL_GPUS, materialized_configs: Mapping[str, Path] | None = None) -> dict[str, Any]:
    parse_gpus(physical_gpus, formal=True)
    validate_artifact(adaptation, expected_schema=schema("adaptation"))
    validate_artifact(p0_admission, expected_schema=schema("p0_admission"))
    validate_artifact(smoke_pass, expected_schema=schema("smoke_adjudication"), expected_cell="B4")
    validate_artifact(cleanup_pass, expected_schema=schema("smoke_cleanup"), expected_cell="B4")
    validate_artifact(materialization, expected_schema=schema("materialization"))
    if smoke_pass.get("status") != "SMOKE_PASS" or cleanup_pass.get("status") != "CLEANUP_PASS":
        raise V21BError("formal launch requires SMOKE_PASS followed by CLEANUP_PASS")
    if materialization.get("status") != "MATERIALIZATION_PASS" or materialization.get("phase") != "FORMAL_PROMOTED":
        raise V21BError("formal launch requires FORMAL_PROMOTED materialized configs")
    adaptation_sha256 = hashlib.sha256(canonical_json_bytes(dict(adaptation))).hexdigest()
    declared_adaptation = materialization.get("adaptation_bundle_sha256")
    if not isinstance(declared_adaptation, str) or len(declared_adaptation) != 64 or any(char not in "0123456789abcdef" for char in declared_adaptation) or declared_adaptation != adaptation_sha256:
        raise V21BError("formal launch adaptation artifact is stale, tampered, or not a lowercase sha256 digest")
    root = repo_root.resolve()
    source_lock_file = Path(source_lock_path).absolute()
    if source_lock_file.is_symlink() or not source_lock_file.is_file():
        raise V21BError(f"formal launch source lock must be a regular file: {source_lock_file}")
    source_lock_file_sha256 = sha256_file(source_lock_file)
    smoke_pass_sha256 = hashlib.sha256(canonical_json_bytes(dict(smoke_pass))).hexdigest()
    cleanup_receipt_sha256 = _validate_cleanup_receipt(cleanup_pass, smoke_pass=smoke_pass)
    smoke_result = smoke_pass.get("result")
    if not isinstance(smoke_result, Mapping) or smoke_pass.get("cell") != "B4" or smoke_pass.get("seed") != 0:
        raise V21BError("formal launch smoke adjudication lacks the exact B4 seed0 result")
    artifact_root_value = smoke_pass.get("artifact_root")
    if not isinstance(artifact_root_value, str) or not artifact_root_value:
        raise V21BError("formal launch smoke adjudication artifact root is missing")
    smoke_artifact_root = Path(artifact_root_value).resolve()
    expected_smoke_roots = {
        "training_root": smoke_artifact_root / SMOKE_TRAINING_REL,
        "eval_root": smoke_artifact_root / SMOKE_EVAL_REL,
        "launcher_root": smoke_artifact_root / SMOKE_LAUNCHER_REL,
    }
    if any(Path(smoke_pass.get(key, "")).resolve() != expected for key, expected in expected_smoke_roots.items()):
        raise V21BError("formal launch smoke adjudication roots are not the exact canonical three roots")
    if smoke_result.get("result_path") != str(expected_smoke_roots["eval_root"] / "smoke_result.json") or smoke_result.get("training_metrics_path") != str(expected_smoke_roots["eval_root"] / "r2_training_metrics.jsonl"):
        raise V21BError("formal launch smoke result paths are not bound to the exact smoke roots")
    if materialized_configs is None or "B4" not in materialized_configs:
        raise V21BError("formal launch requires the current B4 materialized config for smoke lineage")
    b4_receipt = validate_materialized_config_receipt(materialization, Path(materialized_configs["B4"]), cell="B4", phase="FORMAL_PROMOTED")
    smoke_identity = {
        "cell": "B4",
        "seed": 0,
        "source_checkpoint_sha256": materialization["source_checkpoint_sha256"],
        "source_lock_sha256": materialization["source_lock_sha256"],
        "source_lock_file_sha256": source_lock_file_sha256,
        "source_config_sha256": b4_receipt["source_config_sha256"],
        "materialization_sha256": b4_receipt["materialization_sha256"],
        "materialized_config_sha256": b4_receipt["materialized_config_sha256"],
        "adaptation_bundle_sha256": materialization["adaptation_bundle_sha256"],
        "materialization_phase": "FORMAL_PROMOTED",
    }
    for owner, value in (("smoke adjudication", smoke_pass), ("smoke result", smoke_result)):
        for key, expected in smoke_identity.items():
            if value.get(key) != expected:
                raise V21BError(f"formal launch {owner} {key} is stale or unrelated to current materialization")
    if smoke_result.get("source_bindings") != {
        "source_checkpoint_sha256": smoke_identity["source_checkpoint_sha256"],
        "source_lock_sha256": smoke_identity["source_lock_sha256"],
        "source_config_sha256": smoke_identity["source_config_sha256"],
        "materialization_sha256": smoke_identity["materialization_sha256"],
        "materialized_config_sha256": smoke_identity["materialized_config_sha256"],
    }:
        raise V21BError("formal launch smoke source bindings are not exact")
    try:
        source_lock = json.loads(source_lock_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V21BError("formal launch source lock is not valid JSON") from exc
    if not isinstance(source_lock, Mapping):
        raise V21BError("formal launch source lock must be a mapping")
    validate_source_lock(dict(source_lock), root, require_current=True)
    source_lock_sha256 = source_lock.get("source_lock_sha256")
    for label, value in (
        ("materialization", materialization.get("source_lock_sha256")),
        ("P0 admission", p0_admission.get("source_lock_sha256")),
        ("adaptation", adaptation.get("source_lock_sha256")),
    ):
        if value != source_lock_sha256:
            raise V21BError(f"formal launch source-lock binding disagrees with {label}")
    if not isinstance(source_lock_sha256, str):
        raise V21BError("formal launch source-lock digest is missing")
    git_identity = _git_identity(root)
    overrides = materialized_profile_overrides(adaptation)
    rows = []
    for cell, gpu in zip(V21B_CELL_ORDER, physical_gpus):
        if materialized_configs is None or cell not in materialized_configs:
            raise V21BError("formal launch requires all seven materialized config paths")
        receipt = validate_materialized_config_receipt(materialization, Path(materialized_configs[cell]), cell=cell, phase="FORMAL_PROMOTED")
        config = Path(receipt["path"])
        loaded = receipt["config"]
        env = loaded.get("env", {}).get("config", {})
        limit = loaded.get("v21b_arm_realistic_effort_limit_nm")
        if loaded.get("v21b_arm_profile") == "ARM_REALISTIC" and limit != overrides["arm_j1..arm_j6_effort_limit_nm"]:
            raise V21BError(f"{cell} materialized ARM_REALISTIC limit does not match adaptation")
        output = root / FORMAL_TRAINING_REL / cell
        training_metrics_path = output / "r2_training_metrics.jsonl"
        argv = [
            "env", "-u", "CUDA_VISIBLE_DEVICES", f"ACCELERATE_TORCH_DEVICE=cuda:{gpu}", "WANDB_MODE=online", f"PYTHONPATH={root}", "/home/baoquanc/anaconda3/envs/isaaclab/bin/python", "-m", "gr00t.rl.train_agent_trl",
            f"--config-dir={config.parent}", f"--config-name={config.stem}", f"checkpoint={V21B_WARM_START_PATH}",
            "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true", "use_wandb=true",
            f"num_envs=4096", f"seed={loaded['seed']}", "algo.trl.num_total_batches=2500", "callbacks.model_save.save_frequency=250",
            "env.config.a2_v21B_formal_launch=true", "+env.config.a2_v21B_census_topology=canonical16", f"+env.config.a2_v21B_materialization_sha256={receipt['materialization_sha256']}", f"+env.config.a2_v21B_materialized_config_sha256={receipt['materialized_config_sha256']}", f"env.config.a2_v21B_source_checkpoint_sha256={materialization['source_checkpoint_sha256']}", f"env.config.a2_v21B_source_lock_sha256={source_lock_sha256}", f"env.config.a2_v21B_source_config_sha256={receipt['source_config_sha256']}", "+r2_evidence_enabled=true", f"+r2_source_lock_path={source_lock_file}", f"+r2_training_metrics_path={training_metrics_path}", f"experiment_dir={output}",
            f"env.config.a2_v21B_adaptation_bundle_sha256={materialization['adaptation_bundle_sha256']}", f"+v21b_adaptation_bundle_sha256={materialization['adaptation_bundle_sha256']}", f"+v21b_materialization_sha256={receipt['materialization_sha256']}", f"+v21b_materialized_config_sha256={receipt['materialized_config_sha256']}",
        ]
        window = ["tmux", "new-window", "-d", "-t", FORMAL_SESSION, "-n", cell, "--", *argv]
        rows.append({"cell": cell, "physical_gpu": gpu, "seed": loaded["seed"], "config": str(config), "materialization_phase": "FORMAL_PROMOTED", "materialized_config_sha256": receipt["materialized_config_sha256"], "materialization_sha256": receipt["materialization_sha256"], "source_checkpoint_sha256": materialization["source_checkpoint_sha256"], "source_lock_sha256": source_lock_sha256, "source_lock_path": str(source_lock_file), "source_lock_file_sha256": source_lock_file_sha256, "source_config_sha256": receipt["source_config_sha256"], "adaptation_bundle_sha256": declared_adaptation, "metric_identity": {"cell": cell, "seed": loaded["seed"], "materialization_phase": "FORMAL_PROMOTED", "source_config_sha256": receipt["source_config_sha256"], "materialization_sha256": receipt["materialization_sha256"], "materialized_config_sha256": receipt["materialized_config_sha256"], "adaptation_bundle_sha256": declared_adaptation, "source_lock_sha256": source_lock_sha256, "source_lock_file_sha256": source_lock_file_sha256, "source_checkpoint_sha256": materialization["source_checkpoint_sha256"], "repo_commit": git_identity["commit"], "repo_tree": git_identity["tree"]}, "repo_commit": git_identity["commit"], "repo_tree": git_identity["tree"], "training_metrics_path": str(training_metrics_path), "command_sha256": hashlib.sha256(canonical_json_bytes(argv)).hexdigest(), "output_root": str(output), "env": {"CUDA_VISIBLE_DEVICES": str(gpu), "WANDB_MODE": "online"}, "argv": argv, "tmux_window_argv": window})
    session = ["tmux", "new-session", "-d", "-s", FORMAL_SESSION, "-n", "B1", "--", *rows[0]["argv"]]
    receipt_hash = materialization.get("materialization_sha256")
    if not isinstance(receipt_hash, str):
        unsigned = dict(materialization)
        unsigned.pop("materialization_sha256", None)
        receipt_hash = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    return artifact_payload("formal_plan", status="FORMAL_PLAN_COMPLETE", session=FORMAL_SESSION, physical_gpus=list(V21B_FORMAL_GPUS), forbidden_gpus=[7], windows=["B1", "B2", "B3", "B4", "B5", "B6", "B7"], initial_session_argv=session, rows=rows, num_envs=4096, batches=2500, save_frequency=250, checkpoint=V21B_WARM_START_PATH, checkpoint_load_mode="policy_only", auto_load_latest=False, wandb_mode="online", p0_admission_sha256=hashlib.sha256(canonical_json_bytes(dict(p0_admission))).hexdigest(), adaptation_sha256=adaptation_sha256, materialization_phase="FORMAL_PROMOTED", materialization_sha256=receipt_hash, smoke_pass_sha256=smoke_pass_sha256, cleanup_pass_sha256=hashlib.sha256(canonical_json_bytes(dict(cleanup_pass))).hexdigest(), cleanup_receipt_sha256=cleanup_receipt_sha256, smoke_lineage_identity=smoke_identity, source_lock_path=str(source_lock_file), source_lock_sha256=source_lock_sha256, source_lock_file_sha256=source_lock_file_sha256, source_checkpoint_sha256=materialization["source_checkpoint_sha256"], repo_commit=git_identity["commit"], repo_tree=git_identity["tree"], training_metric_schema="a2_piper_base_v21B_training_metric_v1", monitor_contract={"iteration": 50, "prefix_batches": 50, "detach_only": True, "kill_processes": False})


def launch_formal_wave(plan: Mapping[str, Any], *, tmux_binary: str = "tmux") -> None:
    """Launch a previously validated plan; never silently downgrade resources."""

    import subprocess
    from .a2_piper_v21B_schemas import validate_artifact, schema
    validate_artifact(plan, expected_schema=schema("formal_plan"))
    if plan.get("physical_gpus") != list(V21B_FORMAL_GPUS) or plan.get("forbidden_gpus") != [7]:
        raise V21BError("formal launch plan GPU contract is invalid")
    initial = list(plan["initial_session_argv"])
    initial[0] = tmux_binary
    subprocess.run(initial, check=True)
    for row in plan["rows"][1:]:
        window = list(row["tmux_window_argv"])
        window[0] = tmux_binary
        subprocess.run(window, check=True)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


build_formal_plan = build_formal_launch_plan

__all__ = ["FORMAL_SESSION", "FORMAL_TRAINING_REL", "FORMAL_LAUNCHER_REL", "build_formal_launch_plan", "build_formal_plan", "launch_formal_wave", "main"]
