"""Frozen-policy zero-shot probe planning/adjudication for v21-B."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

from gr00t.rl.envs.door.a2_v21b_evidence import a2_v21b_validate_terminal_record

from ._v21b_common import V21B_CELL_ORDER, V21BError, canonical_json_bytes, hydra_string_value, sha256_file
from .a2_piper_v21B_adaptation import validate_materialized_config_receipt
from .a2_piper_v21B_heavy16_census import validate_heavy16_manifest
from .a2_piper_v21B_probe_runner import hash_command_env, observed_git_identity, read_process_receipt
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact


def build_zero_shot_plan(
    repo_root: Path,
    *,
    arm_realistic_limit_nm: float | None,
    output_root: Path,
    manifest_path: Path | None = None,
    scenario_manifest_path: Path | None = None,
    materialization: Mapping[str, Any],
    materialized_config: Path,
    source_checkpoint_sha256: str | None = None,
    source_lock_sha256: str | None = None,
    source_config_sha256: str | None = None,
) -> dict[str, Any]:
    if arm_realistic_limit_nm is None:
        raise V21BError("zero-shot ARM_REALISTIC plan requires a signed census-selected limit")
    if manifest_path is None:
        manifest_path = scenario_manifest_path
    if manifest_path is None:
        raise V21BError("zero-shot plan requires the actual signed canonical16/heavy16 manifest path")
    if isinstance(arm_realistic_limit_nm, bool) or not isinstance(arm_realistic_limit_nm, (int, float)) or not math.isfinite(float(arm_realistic_limit_nm)) or float(arm_realistic_limit_nm) <= 0.0:
        raise V21BError("zero-shot ARM_REALISTIC limit must be finite and positive")
    root = repo_root.resolve()
    receipt = validate_materialized_config_receipt(materialization, materialized_config, cell="B4", phase="POST_CENSUS")
    selected_limit = float(receipt["config"]["v21b_arm_realistic_effort_limit_nm"])
    if float(arm_realistic_limit_nm) != selected_limit:
        raise V21BError("zero-shot limit must exactly match the POST_CENSUS B4 receipt")
    if source_checkpoint_sha256 is not None and source_checkpoint_sha256 != materialization.get("source_checkpoint_sha256"):
        raise V21BError("zero-shot source checkpoint override disagrees with the receipt")
    if source_lock_sha256 is not None and source_lock_sha256 != materialization.get("source_lock_sha256"):
        raise V21BError("zero-shot source lock override disagrees with the receipt")
    if source_config_sha256 is not None and source_config_sha256 != receipt["source_config_sha256"]:
        raise V21BError("zero-shot source config override disagrees with the B4 template binding")
    config = Path(receipt["path"])
    manifest = validate_heavy16_manifest(
        manifest_path,
        expected_phase="CENSUS_PRE_K",
        expected_source_checkpoint_sha256=materialization.get("source_checkpoint_sha256"),
        expected_source_lock_sha256=materialization.get("source_lock_sha256"),
    )
    # The heavy manifest is intentionally frozen in CENSUS_PRE_K and reused by
    # POST_CENSUS probes; its B1 source-config/materialization hashes remain
    # distinct signed parents of the probe's B4 materialization.
    output = output_root.resolve()
    manifest_content = canonical_json_bytes({key: value for key, value in manifest.items() if key not in {"path", "file_sha256"}}).decode("utf-8")
    manifest_content_sha256 = hashlib.sha256(manifest_content.encode("utf-8")).hexdigest()
    manifest_bindings = {
        "source_checkpoint_sha256": materialization["source_checkpoint_sha256"],
        "source_lock_sha256": materialization["source_lock_sha256"],
        "source_config_sha256": receipt["source_config_sha256"],
        "materialization_sha256": receipt["materialization_sha256"],
        "materialized_config_sha256": receipt["materialized_config_sha256"],
    }
    git_identity = observed_git_identity(root)
    common = [
        sys.executable, "-m", "gr00t.rl.eval_agent_trl",
        f"--config-dir={config.parent}", f"--config-name={config.stem}",
        "checkpoint=logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G4-20260731_004712/model_step_002500.pt",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true",
        "num_envs=16", "seed=0", "algo.config.eval.num_eval_episodes=16", "+algo.config.eval.eval_num_envs_episodes=true",
        "env.config.a2_v21B_materialization_phase=POST_CENSUS",
        "env.config.a2_v21B_formal_launch=false",
        "+env.config.a2_v21B_signed_probe_scenarios_enabled=true", "env.config.a2_v21B_cell=B4",
        f"+env.config.a2_v21B_materialization_sha256={receipt['materialization_sha256']}",
        f"+env.config.a2_v21B_materialized_config_sha256={receipt['materialized_config_sha256']}",
        f"env.config.a2_v21B_source_checkpoint_sha256={materialization['source_checkpoint_sha256']}",
        f"env.config.a2_v21B_source_lock_sha256={materialization['source_lock_sha256']}",
        f"env.config.a2_v21B_source_config_sha256={receipt['source_config_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_path={Path(manifest_path).absolute()}",
        f"+env.config.a2_v21B_scenario_manifest_sha256={manifest['manifest_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_file_sha256={manifest['file_sha256']}",
        f"+env.config.a2_v21B_canonical_manifest_sha256={manifest['canonical_manifest_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_source_checkpoint_sha256={manifest['source_checkpoint_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_source_lock_sha256={manifest['source_lock_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_source_config_sha256={manifest['source_config_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_materialization_sha256={manifest['materialization_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_json_sha256={manifest_content_sha256}",
        f"+env.config.a2_v21B_scenario_manifest_json={hydra_string_value(manifest_content)}",
    ]
    rows = []
    for topology in ("canonical16", "heavy16"):
        result_path = output / topology / "terminal_records.json"
        run_uuid = f"v21B-zero-shot-{topology}"
        raw_root = output / topology / "terminal_exports"
        raw_paths = [raw_root / f"B4_{run_uuid}_env{env_id}.json" for env_id in range(16)]
        argv = [*common, f"+env.config.a2_v21B_census_topology={topology}", f"+env.config.a2_v21B_run_uuid={run_uuid}", f"env.config.a2_v21B_terminal_export_root={raw_root}", f"+env.config.a2_v21B_output_root={output / topology}"]
        env = {"CUDA_VISIBLE_DEVICES": "0", "WANDB_MODE": "offline"}
        parent_hashes = {"manifest": manifest["file_sha256"], "materialized_config": receipt["materialized_config_sha256"]}
        result_contract = {
            "kind": "zero_shot_terminal_records", "aggregate_path": str(result_path.absolute()), "raw_paths": [str(path.absolute()) for path in raw_paths],
            "topology": topology, "run_uuid": run_uuid, "manifest_content": manifest_content,
            "manifest_content_sha256": manifest_content_sha256,
            "manifest_sha256": manifest["manifest_sha256"], "canonical_manifest_sha256": manifest["canonical_manifest_sha256"],
            "manifest_file_sha256": manifest["file_sha256"], "manifest_materialization_sha256": manifest["materialization_sha256"],
            "source_bindings": manifest_bindings, "selected_k_nm": selected_limit,
        }
        process_root = output / topology / "process"
        rows.append({"topology": topology, "manifest_path": str(Path(manifest_path).absolute()), "manifest_sha256": manifest["manifest_sha256"], "canonical_manifest_sha256": manifest["canonical_manifest_sha256"], "manifest_file_sha256": manifest["file_sha256"], "manifest_materialization_sha256": manifest["materialization_sha256"], "manifest_content": manifest_content, "manifest_content_sha256": manifest_content_sha256, "argv": argv, "env": env, "run_uuid": run_uuid, "num_envs": 16, "result_paths": [str(result_path.absolute())], "raw_paths": [str(path.absolute()) for path in raw_paths], "process_root": str(process_root.absolute()), "process_receipt_path": str((process_root / "process_receipt.json").absolute()), "result_contract": result_contract, "source_bindings": manifest_bindings, "parent_hashes": parent_hashes, "repo_commit": git_identity["commit"], "repo_tree": git_identity["tree"], "physical_gpu": 0, "command_sha256": hash_command_env(argv, env)})
    fields: dict[str, Any] = {}
    for key, value in (("source_checkpoint_sha256", source_checkpoint_sha256), ("source_lock_sha256", source_lock_sha256), ("source_config_sha256", source_config_sha256)):
        if value is not None:
            fields[key] = value
    payload = artifact_payload(
        "zero_shot", status="STATIC_PASS", cell="B4",
        arm_profile="ARM_REALISTIC", arm_realistic_limit_nm=selected_limit, checkpoint_load_mode="policy_only",
        output_root=str(output), commands=rows, selection_is_not_performance_gate=True,
        materialization_phase=receipt["phase"], materialization_sha256=receipt["materialization_sha256"],
        materialized_config_sha256=receipt["materialized_config_sha256"], effort_limit_vector_6d=receipt["effort_limit_vector_6d"], manifest_content_sha256=manifest_content_sha256,
        source_checkpoint_sha256=materialization["source_checkpoint_sha256"], source_lock_sha256=materialization["source_lock_sha256"], source_config_sha256=receipt["source_config_sha256"], materialized_config_path=str(config), manifest_path=str(Path(manifest_path).absolute()), manifest_sha256=manifest["manifest_sha256"], manifest_file_sha256=manifest["file_sha256"], canonical_manifest_sha256=manifest["canonical_manifest_sha256"], manifest_source_config_sha256=manifest["source_config_sha256"], manifest_materialization_sha256=manifest["materialization_sha256"], repo_commit=git_identity["commit"], repo_tree=git_identity["tree"],
    )
    payload["plan_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return validate_artifact(payload, expected_schema=schema("zero_shot"), expected_cell="B4")


def _zero_plan_digest(plan: Mapping[str, Any]) -> None:
    validate_artifact(plan, expected_schema=schema("zero_shot"), expected_cell="B4")
    unsigned = dict(plan)
    unsigned.pop("plan_sha256", None)
    if plan.get("status") != "STATIC_PASS" or plan.get("plan_sha256") != hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest():
        raise V21BError("zero-shot plan digest/status is invalid")


def _zero_result_records(path: Path, *, topology: str, expected_manifest: Mapping[str, Any], receipt_sha256: str, plan: Mapping[str, Any], expected_result_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise V21BError(f"zero-shot result must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V21BError(f"zero-shot result is not valid JSON: {path}") from exc
    if not isinstance(value, Mapping) or value.get("schema") != "a2_piper_base_v21B_zero_shot_result_v1":
        raise V21BError("zero-shot result must be a producer result artifact, not copied metric rows")
    if value.get("producer_state") != "AGGREGATED_AFTER_CHILD_EXIT" or value.get("plan_sha256") != plan["plan_sha256"] or value.get("topology") != topology or value.get("manifest_sha256") != expected_manifest["manifest_sha256"]:
        raise V21BError("zero-shot result is not bound to its plan/receipt/topology/manifest")
    if value.get("process_receipt_sha256") is not None and value.get("process_receipt_sha256") != receipt_sha256:
        raise V21BError("zero-shot producer receipt digest disagrees with the consumed receipt")
    if value.get("result_path") != str(expected_result_path.absolute()):
        raise V21BError("zero-shot result path binding is invalid")
    for key in ("canonical_manifest_sha256", "manifest_file_sha256", "manifest_materialization_sha256", "selected_k_nm"):
        expected = {"canonical_manifest_sha256": plan["canonical_manifest_sha256"], "manifest_file_sha256": plan["manifest_file_sha256"], "manifest_materialization_sha256": plan["manifest_materialization_sha256"], "selected_k_nm": plan["arm_realistic_limit_nm"]}[key]
        if value.get(key) != expected:
            raise V21BError(f"zero-shot result {key} is not bound to the plan")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != 16 or value.get("record_count") != 16:
        raise V21BError("zero-shot producer result requires exactly 16 terminal records")
    manifest_rows = expected_manifest["manifest_rows"] if topology == "heavy16" else [row for row in expected_manifest["canonical_manifest_rows"] if row["scenario_id"] not in {item["scenario_id"] for item in expected_manifest["manifest_rows"]}]
    if len(manifest_rows) != 16:
        raise V21BError("zero-shot result expected manifest topology is not 16 rows")
    expected_by_id = {row["scenario_id"]: row for row in manifest_rows}
    seen_ids: set[str] = set()
    seen_env: set[int] = set()
    goal_count = 0
    stage3_count = 0
    for record in records:
        if not isinstance(record, Mapping):
            raise V21BError("zero-shot result terminal records must be mappings")
        a2_v21b_validate_terminal_record(record)
        provenance = record.get("provenance")
        if not isinstance(provenance, Mapping) or provenance.get("materialization_phase") != "POST_CENSUS" or provenance.get("topology") != topology or provenance.get("manifest_sha256") != expected_manifest["manifest_sha256"] or provenance.get("manifest_materialization_sha256") != expected_manifest["materialization_sha256"]:
            raise V21BError("zero-shot terminal record lacks exact POST_CENSUS manifest binding")
        for key in ("source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256"):
            if provenance.get(key) != plan.get(key):
                raise V21BError(f"zero-shot terminal record {key} is not bound to the POST_CENSUS plan")
        if provenance.get("manifest_file_sha256") != plan["manifest_file_sha256"] or provenance.get("canonical_manifest_sha256") != plan["canonical_manifest_sha256"] or provenance.get("selected_k_nm") != plan["arm_realistic_limit_nm"] or provenance.get("env_id") != len(seen_env):
            raise V21BError("zero-shot terminal record manifest/selected-k/env binding is incomplete")
        scenario_id = provenance.get("scenario_id")
        if scenario_id not in expected_by_id or scenario_id in seen_ids or provenance.get("scenario_sha256") != expected_by_id[scenario_id].get("scenario_sha256"):
            raise V21BError("zero-shot terminal record scenario identity is not bound to manifest")
        seen_ids.add(scenario_id)
        env_id = provenance.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0 or env_id >= 16 or env_id in seen_env:
            raise V21BError("zero-shot terminal record env_id is missing/duplicated/out of range")
        seen_env.add(env_id)
        expected_row = manifest_rows[env_id]
        if expected_row["scenario_id"] != scenario_id:
            raise V21BError("zero-shot terminal record env order disagrees with manifest")
        task = record.get("task")
        if not isinstance(task, Mapping):
            task = record.get("metrics")
        if not isinstance(task, Mapping) or not isinstance(task.get("goal"), bool):
            raise V21BError("zero-shot terminal record must contain producer goal bool")
        max_stage = task.get("max_stage")
        if isinstance(max_stage, bool) or not isinstance(max_stage, int) or max_stage < 0:
            raise V21BError("zero-shot terminal record must contain producer max_stage")
        goal_count += int(task["goal"])
        stage3_count += int(max_stage >= 3)
    if seen_ids != set(expected_by_id) or seen_env != set(range(16)):
        raise V21BError("zero-shot terminal records do not cover the exact manifest topology")
    return [dict(record) for record in records], {"topology": topology, "goal_count": goal_count, "stage3_reached_count": stage3_count, "record_count": 16, "process_receipt_sha256": receipt_sha256, "result_sha256": sha256_file(path)}


def adjudicate_zero_shot(
    rows: list[Mapping[str, Any]] | None = None,
    *,
    plan: Mapping[str, Any],
    process_receipt_paths: Mapping[str, Path] | None = None,
    result_paths: Mapping[str, Path] | None = None,
    receipt_paths: Mapping[str, Path] | None = None,
    process_receipt_path: Mapping[str, Path] | None = None,
    result_artifact_paths: Mapping[str, Path] | None = None,
    arm_realistic_limit_nm: float | None = None,
    canonical_goal_collapse_threshold: int = 3,
    **_rejected_legacy_metrics: Any,
) -> dict[str, Any]:
    """Recompute zero-shot adjudication from two receipt-bound result files."""

    if rows is not None:
        raise V21BError("zero-shot adjudication rejects caller-supplied metric rows; provide producer receipt/result paths")
    _zero_plan_digest(plan)
    if process_receipt_paths is None:
        process_receipt_paths = receipt_paths or process_receipt_path
    if result_paths is None:
        result_paths = result_artifact_paths
    if process_receipt_paths is None or result_paths is None or set(process_receipt_paths) != {"canonical16", "heavy16"} or set(result_paths) != {"canonical16", "heavy16"}:
        raise V21BError("zero-shot adjudication requires exactly canonical16/heavy16 process receipt and result paths")
    manifest = validate_heavy16_manifest(Path(plan["manifest_path"]), expected_manifest_sha256=plan["manifest_sha256"], expected_source_checkpoint_sha256=plan["source_checkpoint_sha256"], expected_source_lock_sha256=plan["source_lock_sha256"])
    computed_rows: list[dict[str, Any]] = []
    all_records: list[dict[str, Any]] = []
    for command in plan["commands"]:
        topology = command["topology"]
        receipt = read_process_receipt(Path(process_receipt_paths[topology]), repo_root=Path(__file__).resolve().parents[2], expected_command_sha256=command["command_sha256"], expected_env=command["env"], expected_result_paths=tuple(Path(item) for item in command["result_paths"]), expected_parent_hashes=command.get("parent_hashes"), expected_source_bindings=command.get("source_bindings"), expected_plan_sha256=plan["plan_sha256"], expected_git_commit=plan.get("repo_commit"), expected_git_tree=plan.get("repo_tree"), expected_physical_gpu=command.get("physical_gpu"), expected_result_contract=command.get("result_contract"), require_natural_exit=True)
        if receipt.get("plan_sha256") != plan["plan_sha256"]:
            raise V21BError("zero-shot process receipt is not bound to this plan")
        receipt_hash = sha256_file(Path(process_receipt_paths[topology]))
        records, summary = _zero_result_records(Path(result_paths[topology]), topology=topology, expected_manifest=manifest, receipt_sha256=receipt_hash, plan=plan, expected_result_path=Path(command["result_paths"][0]))
        computed_rows.append(summary)
        all_records.extend(records)
    canonical = next(row for row in computed_rows if row["topology"] == "canonical16")
    collapse = canonical["goal_count"] < canonical_goal_collapse_threshold and canonical["stage3_reached_count"] < 8
    selected_limit = float(plan["arm_realistic_limit_nm"])
    if arm_realistic_limit_nm is not None and float(arm_realistic_limit_nm) != selected_limit:
        raise V21BError("zero-shot selected k is not bound to the signed plan")
    payload = artifact_payload(
        "zero_shot", status="ZERO_SHOT_COMPLETE", cell="B4", arm_profile="ARM_REALISTIC", arm_realistic_limit_nm=selected_limit,
        records=all_records, rows=computed_rows, fork_f2_arm_axis_collapse=bool(collapse), performance_gate=False,
        plan_sha256=plan["plan_sha256"], command_sha256=[row["command_sha256"] for row in plan["commands"]], receipt_sha256={row["topology"]: row["process_receipt_sha256"] for row in computed_rows}, result_sha256={row["topology"]: row["result_sha256"] for row in computed_rows},
        selected_k_nm=selected_limit, materialization_phase=plan["materialization_phase"], materialization_sha256=plan["materialization_sha256"], materialized_config_sha256=plan["materialized_config_sha256"], effort_limit_vector_6d=plan["effort_limit_vector_6d"], source_checkpoint_sha256=plan["source_checkpoint_sha256"], source_lock_sha256=plan["source_lock_sha256"], source_config_sha256=plan["source_config_sha256"], manifest_path=plan["manifest_path"], manifest_sha256=plan["manifest_sha256"], canonical_manifest_sha256=plan["canonical_manifest_sha256"], manifest_source_config_sha256=plan["manifest_source_config_sha256"], manifest_materialization_sha256=plan["manifest_materialization_sha256"],
    )
    return validate_artifact(payload, expected_schema=schema("zero_shot"), expected_cell="B4")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--arm-realistic-limit-nm", type=float, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--materialization", type=Path, required=True)
    parser.add_argument("--materialized-config", type=Path, required=True)
    args = parser.parse_args(argv)
    import json
    materialization = json.loads(args.materialization.read_text(encoding="utf-8"))
    print(json.dumps(build_zero_shot_plan(args.repo_root, arm_realistic_limit_nm=args.arm_realistic_limit_nm, output_root=args.output_root, manifest_path=args.manifest, materialization=materialization, materialized_config=args.materialized_config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_zero_shot_plan", "adjudicate_zero_shot"]
