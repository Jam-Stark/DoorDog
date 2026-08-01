"""CPU/no-sim v21-B pre-formal workflow contracts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import torch

from gr00t.rl.envs.door.a2_v21b_evidence import (
    V21B_ARM_JOINT_NAMES,
    V21B_AUTHORITY_LABEL,
    V21B_EVIDENCE_SCHEMA,
    a2_v21b_accumulate_arm_step,
    a2_v21b_build_census_frames_from_episode,
    a2_v21b_build_step_evidence,
    a2_v21b_build_terminal_record,
    a2_v21b_init_arm_episode_accumulator,
    a2_v21b_validate_terminal_record,
)
from scriptsFORhuman.v21B._v21b_common import V21BError, canonical_json_bytes, write_json
from scriptsFORhuman.v21B.a2_piper_v21B_adaptation import freeze_adaptation, materialize_v21b_configs
from scriptsFORhuman.v21B.a2_piper_v21B_arm_tie_calibration import calibrate_arm_tie
from scriptsFORhuman.v21B.a2_piper_v21B_formal_launcher import build_formal_launch_plan
from scriptsFORhuman.v21B.a2_piper_v21B_heavy16_census import build_census_plan, build_heavy16_manifest, run_torque_census
from scriptsFORhuman.v21B.a2_piper_v21B_p0_admission import build_p0_admission
from scriptsFORhuman.v21B.a2_piper_v21B_pilot import V21B_PILOT_METRIC_SOURCES, adjudicate_b4_pilot, build_b4_pilot_plan
from scriptsFORhuman.v21B.a2_piper_v21B_smoke_adjudicator import adjudicate_b4_smoke
from scriptsFORhuman.v21B.a2_piper_v21B_smoke_cleanup import build_smoke_cleanup_manifest, cleanup_targets
from scriptsFORhuman.v21B.a2_piper_v21B_smoke_launcher import build_b4_smoke_plan
from scriptsFORhuman.v21B.a2_piper_v21B_source_freeze import build_source_lock
from scriptsFORhuman.v21B.a2_piper_v21B_startup_monitor import build_startup_monitor_plan, monitor_iteration50
from scriptsFORhuman.v21B.a2_piper_v21B_zero_shot import adjudicate_zero_shot, build_zero_shot_plan
from scriptsFORhuman.v21B.a2_piper_v21B_probe_runner import _collect_pilot_result, hash_command_env, observed_git_identity, read_process_receipt, run_process_once


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "scriptsFORhuman/V21/a2_piper_base_v21B_ablation_execution_plan_20260802.md"
MANIFEST = ROOT / "scriptsFORhuman/V21/a2_piper_base_v21B_experiment_manifest_20260802.yaml"


def _assert_eval_overrides_compose(materialized_config: Path, argv: list[str]) -> None:
    """Compose the materialized eval config with the exact signed override forms."""

    from hydra import compose, initialize_config_dir
    from hydra.core.global_hydra import GlobalHydra

    existing_key = next(token for token in argv if token.startswith("algo.config.eval.num_eval_episodes="))
    absent_key = next(token for token in argv if token.startswith("+algo.config.eval.eval_num_envs_episodes="))
    assert existing_key == "algo.config.eval.num_eval_episodes=16"
    assert absent_key == "+algo.config.eval.eval_num_envs_episodes=true"
    path = Path(materialized_config).resolve()
    GlobalHydra.instance().clear()
    try:
        with initialize_config_dir(config_dir=str(path.parent), version_base=None):
            resolved = compose(config_name=path.stem, overrides=[existing_key, absent_key])
    finally:
        GlobalHydra.instance().clear()
    assert int(resolved.algo.config.eval.num_eval_episodes) == 16
    assert bool(resolved.algo.config.eval.eval_num_envs_episodes) is True


def _census_frame(*, scenario_id: str, topology: str, source_checkpoint_sha256: str, source_lock_sha256: str, source_config_sha256: str, materialization_sha256: str, materialized_config_sha256: str, door_weight_kg: float, hinge_force_nm: float, effort: float) -> dict:
    state = a2_v21b_init_arm_episode_accumulator(1, max_episode_length=1)
    value = torch.full((1, 6), effort)
    zeros = torch.zeros((1, 6))
    step = a2_v21b_build_step_evidence(
        pd_estimates={
            "arm_pd_effort_estimate_unclipped_6d": value,
            "arm_pd_effort_estimate_clipped_6d": value,
            "arm_pd_effort_estimated_saturation_6d": torch.zeros((1, 6), dtype=torch.bool),
            "arm_joint_effort_limit_6d": torch.full((1, 6), 100.0),
        },
        tracking={"arm_joint_position_error_6d": zeros, "arm_joint_velocity_6d": zeros},
        valid_mask=torch.ones(1, dtype=torch.bool),
        step_index=torch.zeros(1, dtype=torch.long),
    )
    a2_v21b_accumulate_arm_step(state, step)
    return a2_v21b_build_census_frames_from_episode(
        state, 0, scenario_id=scenario_id, topology=topology, episode_id=f"{scenario_id}:episode0",
        source_checkpoint_sha256=source_checkpoint_sha256, source_lock_sha256=source_lock_sha256,
        source_config_sha256=source_config_sha256, materialization_sha256=materialization_sha256, materialized_config_sha256=materialized_config_sha256,
        door_weight_kg=door_weight_kg, hinge_force_nm=hinge_force_nm, phase="CENSUS_PRE_K",
    )[0]


def _terminal_probe_record(*, row: dict, topology: str, env_id: int, plan: dict, goal: bool = True, max_stage: int = 3) -> dict:
    evidence = {"schema": V21B_EVIDENCE_SCHEMA, "joint_names": list(V21B_ARM_JOINT_NAMES), "authority": V21B_AUTHORITY_LABEL}
    record = a2_v21b_build_terminal_record(
        evidence,
        plan_id="base_v21B_theta_arm_ablation_v1",
        cell="B4",
        group="B4",
        seed=0,
        source_checkpoint_sha256=plan["source_checkpoint_sha256"],
        adaptation_bundle_sha256=None,
        provenance={
            "materialization_phase": "POST_CENSUS",
            "scenario_id": row["scenario_id"],
            "scenario_sha256": row["scenario_sha256"],
            "topology": topology,
            "episode_id": f"{topology}:episode{env_id}",
            "env_id": env_id,
            "manifest_sha256": plan["manifest_sha256"],
            "canonical_manifest_sha256": plan["canonical_manifest_sha256"],
            "manifest_file_sha256": plan["manifest_file_sha256"],
            "manifest_materialization_sha256": plan["manifest_materialization_sha256"],
            "selected_k_nm": plan["arm_realistic_limit_nm"],
            "source_lock_sha256": plan["source_lock_sha256"],
            "source_config_sha256": plan["source_config_sha256"],
            "materialization_sha256": plan["materialization_sha256"],
            "materialized_config_sha256": plan["materialized_config_sha256"],
        },
    )
    record["task"] = {"goal": goal, "max_stage": max_stage, "env_id": env_id}
    unsigned = dict(record)
    unsigned.pop("record_id", None)
    record["record_id"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    a2_v21b_validate_terminal_record(record)
    return record


def _plan_with_harmless_process(plan: dict, *, tmp_path: Path, prefix: str, result_payloads: dict[str, dict], result_names: dict[str, str]) -> tuple[dict, dict[str, Path], dict[str, Path]]:
    """Write realistic raw per-env outputs; production runner aggregates them."""
    commands = []
    result_paths: dict[str, Path] = {}
    for row in plan["commands"]:
        topology = row["topology"]
        result_path = (tmp_path / prefix / topology / result_names[topology]).absolute()
        result_paths[topology] = result_path
        raw_paths = [
            (tmp_path / prefix / topology / "terminal_exports" / (f"B1_{row['run_uuid']}_env{env_id}.json" if prefix == "census" else f"B4_{row['run_uuid']}_env{env_id}.json")).absolute()
            for env_id in range(16)
        ]
        raw_payload_path = (tmp_path / prefix / topology / "raw_payload.json").absolute()
        raw_payload_path.parent.mkdir(parents=True, exist_ok=True)
        if prefix == "census":
            payload = {str(path): [frame] for path, frame in zip(raw_paths, result_payloads[topology]["frames"])}
        else:
            payload = {str(path): record for path, record in zip(raw_paths, result_payloads[topology]["records"])}
        raw_payload_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        script = (
            "from pathlib import Path; import json; "
            f"d=json.loads(Path({str(raw_payload_path)!r}).read_text(encoding='utf-8')); "
            "[(Path(k).parent.mkdir(parents=True, exist_ok=True), Path(k).write_text(json.dumps(v, sort_keys=True), encoding='utf-8')) for k,v in d.items()]"
        )
        command = [sys.executable, "-c", script]
        new_row = dict(row)
        contract = dict(row["result_contract"])
        contract["aggregate_path"] = str(result_path)
        contract["raw_paths"] = [str(path) for path in raw_paths]
        new_row.update({"argv": command, "env": {}, "result_paths": [str(result_path)], "raw_paths": [str(path) for path in raw_paths], "result_contract": contract, "command_sha256": hash_command_env(command, {})})
        commands.append(new_row)
    bound = dict(plan)
    bound["commands"] = commands
    bound.pop("plan_sha256", None)
    bound["plan_sha256"] = hashlib.sha256(canonical_json_bytes(bound)).hexdigest()
    receipts: dict[str, Path] = {}
    for row in commands:
        topology = row["topology"]
        process_root = (tmp_path / prefix / f"{topology}_process").absolute()
        parents = {
            "manifest": Path(bound["manifest_path"]).absolute(),
            "materialized_config": Path(bound["materialized_config_path"]).absolute(),
        }
        run_process_once(
            argv=row["argv"],
            repo_root=ROOT,
            output_root=process_root,
            env=row["env"],
            name=f"{prefix}_{topology}",
            expected_result_paths=[result_paths[topology]],
            parents=parents,
            parent_hashes=row.get("parent_hashes"),
            source_bindings=row.get("source_bindings"),
            plan_sha256=bound["plan_sha256"],
            physical_gpu=row.get("physical_gpu"),
            result_contract=row["result_contract"],
        )
        receipts[topology] = process_root / "process_receipt.json"
    return bound, receipts, result_paths


def _plan_with_harmless_pilot_process(plan: dict, *, tmp_path: Path, coverage: float = 1.0) -> tuple[dict, Path, Path]:
    """Write raw JSONL/checkpoints; production runner performs the aggregate."""
    result_path = Path(plan["result_paths"][0]).absolute()
    checkpoint_contents = {step: f"checkpoint-{step}".encode("utf-8") for step in (250, 500, 750)}
    checkpoint_paths = [Path(path).absolute() for path in plan["checkpoint_paths"]]
    checkpoints = [{"step": step, "path": str(path), "sha256": hashlib.sha256(checkpoint_contents[step]).hexdigest()} for step, path in zip((250, 500, 750), checkpoint_paths)]
    bound = dict(plan)
    bound["env"] = {}
    bound["result_paths"] = [str(result_path)]
    raw_metrics_path = Path(plan["raw_metrics_path"]).absolute()
    source_lock_path = Path(plan["source_lock_path"]).absolute()
    input_path = (tmp_path / "pilot_raw_input.json").absolute()
    metrics_rows = []
    for i in range(1, 751):
        metrics_rows.append({"schema": "a2_piper_base_v21B_training_metric_v1", "producer_state": "PROCESS_COMPLETED", "scientific_plan_id": "base_v21B_theta_arm_ablation_v1", "source_lock_sha256": plan["source_lock_sha256"], "source_lock_file_sha256": plan["source_lock_file_sha256"], "git_commit": plan["repo_commit"], "git_tree": plan["repo_tree"], "batch_index": i, "metrics": {"send_latch_fire_rate": 0.5, "hinge_at_send_latch_rad": 0.1, "hinge_at_crossing_rad": 0.2, "send_to_cross_steps": 1.0, "stage_overtime_rate": 0.0, "upper_dof_overspeed_rate": 0.0, "arm_clipped_utilization": 0.1, "arm_clipped_utilization_valid_rate": coverage, "finite_data": True, "decomposition_sanity": True, "decomposition_sanity_valid_rate": coverage}, "metric_sources": dict(V21B_PILOT_METRIC_SOURCES)})
    input_path.write_text(json.dumps({"metrics": metrics_rows, "checkpoints": {str(step): contents.decode("utf-8") for step, contents in checkpoint_contents.items()}}, sort_keys=True), encoding="utf-8")
    script = (
        "from pathlib import Path; import json; "
        f"d=json.loads(Path({str(input_path)!r}).read_text(encoding='utf-8')); "
        f"p=Path({str(raw_metrics_path)!r}); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(''.join(json.dumps(x, sort_keys=True)+'\\n' for x in d['metrics']), encoding='utf-8'); "
        + "; ".join(f"p=Path({str(path)!r}); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(d['checkpoints'][{str(step)!r}], encoding='utf-8')" for step, path in zip((250, 500, 750), checkpoint_paths))
    )
    bound["argv"] = [sys.executable, "-c", script]
    bound["command_sha256"] = hash_command_env(bound["argv"], {})
    contract = dict(bound["result_contract"])
    bound["result_contract"] = contract
    bound.pop("plan_sha256", None)
    bound["plan_sha256"] = hashlib.sha256(canonical_json_bytes(bound)).hexdigest()
    process_root = tmp_path / "pilot_process"
    run_process_once(argv=bound["argv"], repo_root=ROOT, output_root=process_root, env={}, name="pilot", expected_result_paths=[result_path], parents={"source_lock": source_lock_path, "materialized_config": Path(plan["materialized_config_path"]).absolute()}, parent_hashes=bound["parent_hashes"], source_bindings=bound["source_bindings"], plan_sha256=bound["plan_sha256"], physical_gpu=bound.get("gpu"), result_contract=contract)
    return bound, process_root / "process_receipt.json", result_path

def _signed_artifacts(tmp_path: Path, *, pilot_coverage: float = 1.0):
    source_lock = build_source_lock(ROOT, plan_path=PLAN, manifest_path=MANIFEST)
    source_lock_path = tmp_path / "source_lock.json"
    write_json(source_lock_path, source_lock)
    p0 = build_p0_admission(ROOT, source_lock=source_lock)
    pre = materialize_v21b_configs(ROOT, phase="CENSUS_PRE_K", p0_admission=p0, source_lock=source_lock, census=None, output_root=tmp_path / "pre")
    scenarios = [
        {"scenario_id": f"h{i:02d}", "door_weight_kg": 140.0 + i, "hinge_force_nm": 10.0, "handle_height_m": 0.80 + 0.01 * i}
        for i in range(16)
    ] + [
        {"scenario_id": f"l{i:02d}", "door_weight_kg": 100.0 + i, "hinge_force_nm": 5.0, "handle_height_m": 0.90 + 0.01 * i}
        for i in range(16)
    ]
    manifest = build_heavy16_manifest(
        scenarios,
        materialization=pre,
        materialized_config=Path(pre["configs"][0]["path"]),
        source_checkpoint_sha256=source_lock["source_checkpoint_sha256"],
        source_lock_sha256=source_lock["source_lock_sha256"],
        source_config_sha256=p0["config_sha256_by_cell"]["B1"],
    )
    manifest_path = tmp_path / "V21B_HEAVY16_MANIFEST.json"
    write_json(manifest_path, manifest)
    frames = [_census_frame(scenario_id=row["scenario_id"], topology="heavy16" if row["scenario_id"].startswith("h") else "canonical16", source_checkpoint_sha256=manifest["source_checkpoint_sha256"], source_lock_sha256=manifest["source_lock_sha256"], source_config_sha256=manifest["source_config_sha256"], materialization_sha256=manifest["materialization_sha256"], materialized_config_sha256=manifest["materialized_config_sha256"], door_weight_kg=row["door_weight_kg"], hinge_force_nm=row["hinge_force_nm"], effort=30.0 if row["scenario_id"].startswith("h") else 10.0) for row in manifest["canonical_manifest_rows"]]
    census = run_torque_census(frames, manifest=manifest)
    post = materialize_v21b_configs(ROOT, phase="POST_CENSUS", p0_admission=p0, source_lock=source_lock, census=census, output_root=tmp_path / "post_raw_template_test")
    source_hash = source_lock["source_checkpoint_sha256"]
    lock_hash = source_lock["source_lock_sha256"]
    zero_plan = build_zero_shot_plan(ROOT, arm_realistic_limit_nm=census["selection"], output_root=tmp_path / "zero", manifest_path=manifest_path, materialization=post, materialized_config=Path(post["configs"][0]["path"]))
    manifest_rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    zero_payloads = {}
    for topology in ("canonical16", "heavy16"):
        rows = manifest_rows["manifest_rows"] if topology == "heavy16" else [row for row in manifest_rows["canonical_manifest_rows"] if row["scenario_id"] not in {item["scenario_id"] for item in manifest_rows["manifest_rows"]}]
        zero_payloads[topology] = {"records": [_terminal_probe_record(row=row, topology=topology, env_id=index, plan=zero_plan) for index, row in enumerate(rows)]}
    zero_plan_bound, zero_receipts, zero_results = _plan_with_harmless_process(zero_plan, tmp_path=tmp_path, prefix="zero", result_payloads=zero_payloads, result_names={"canonical16": "terminal_records.json", "heavy16": "terminal_records.json"})
    zero = adjudicate_zero_shot(plan=zero_plan_bound, process_receipt_paths=zero_receipts, result_paths=zero_results, arm_realistic_limit_nm=census["selection"])
    pilot_plan = build_b4_pilot_plan(ROOT, arm_realistic_limit_nm=census["selection"], output_root=tmp_path / "pilot", materialization=post, materialized_config=Path(post["configs"][0]["path"]), source_lock_path=source_lock_path)
    pilot_plan_bound, pilot_receipt, pilot_result = _plan_with_harmless_pilot_process(pilot_plan, tmp_path=tmp_path, coverage=pilot_coverage)
    pilot = adjudicate_b4_pilot(plan=pilot_plan_bound, process_receipt_path=pilot_receipt, result_path=pilot_result)
    tie = calibrate_arm_tie(
        [{"raw_arm_tangent": 0.01, "raw_arc_tracking": 0.01, "positive_income": 1.0}] * 10,
        source_checkpoint_sha256=source_hash,
        source_lock_sha256=lock_hash,
        source_config_sha256=p0["config_sha256_by_cell"]["B7"],
    )
    adaptation = freeze_adaptation(p0_admission=p0, source_lock=source_lock, census=census, zero_shot=zero, pilot=pilot, arm_tie=tie)
    return source_lock, p0, census, zero, pilot, tie, adaptation


@pytest.mark.parametrize("coverage", (0.0, 0.5))
def test_pilot_rejects_no_sample_or_partial_arm_telemetry_coverage(tmp_path, coverage):
    with pytest.raises(V21BError, match="coverage"):
        _signed_artifacts(tmp_path, pilot_coverage=coverage)


def test_probe_aggregation_rejects_invalid_coverage_before_pilot_artifact(tmp_path):
    source_lock_path = tmp_path / "source_lock.json"
    source_lock_path.write_text(
        json.dumps({"schema": "a2_piper_base_v21B_source_lock_v1", "source_lock_sha256": "a" * 64}),
        encoding="utf-8",
    )
    raw_metrics_path = tmp_path / "r2_training_metrics.jsonl"
    required_metrics = {
        "send_latch_fire_rate": 0.5,
        "hinge_at_send_latch_rad": 0.1,
        "hinge_at_crossing_rad": 0.2,
        "send_to_cross_steps": 1.0,
        "stage_overtime_rate": 0.0,
        "upper_dof_overspeed_rate": 0.0,
        "arm_clipped_utilization": 0.1,
        "arm_clipped_utilization_valid_rate": 0.0,
        "finite_data": True,
        "decomposition_sanity": True,
        "decomposition_sanity_valid_rate": 0.0,
    }
    git_identity = observed_git_identity(ROOT)
    row = {
        "schema": "a2_piper_base_v21B_training_metric_v1",
        "producer_state": "PROCESS_COMPLETED",
        "scientific_plan_id": "base_v21B_theta_arm_ablation_v1",
        "source_lock_sha256": "a" * 64,
        "source_lock_file_sha256": hashlib.sha256(source_lock_path.read_bytes()).hexdigest(),
        "git_commit": git_identity["commit"],
        "git_tree": git_identity["tree"],
        "batch_index": 1,
        "metrics": required_metrics,
        "metric_sources": dict(V21B_PILOT_METRIC_SOURCES),
    }
    raw_metrics_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    contract = {
        "raw_metrics_path": str(raw_metrics_path),
        "source_lock_path": str(source_lock_path),
        "source_lock_sha256": "a" * 64,
        "source_lock_file_sha256": hashlib.sha256(source_lock_path.read_bytes()).hexdigest(),
        "repo_commit": row["git_commit"],
        "repo_tree": row["git_tree"],
        "aggregate_path": str(tmp_path / "pilot_result.json"),
        "checkpoint_paths": [str(tmp_path / f"model_step_{step:06d}.pt") for step in (250, 500, 750)],
    }
    with pytest.raises(V21BError, match="coverage"):
        _collect_pilot_result(contract, plan_sha256="b" * 64)


def test_heavy16_is_deterministic_and_exact(tmp_path):
    scenarios = ([{"scenario_id": f"h{i:02d}", "door_weight_kg": 140.0 + i, "hinge_force_nm": 10.0, "handle_height_m": 0.8 + 0.01 * i} for i in range(16)] + [{"scenario_id": f"l{i:02d}", "door_weight_kg": 100.0 + i, "hinge_force_nm": 5.0, "handle_height_m": 0.9 + 0.01 * i} for i in range(16)])
    source_lock = build_source_lock(ROOT, plan_path=PLAN, manifest_path=MANIFEST)
    p0 = build_p0_admission(ROOT, source_lock=source_lock)
    pre = materialize_v21b_configs(ROOT, phase="CENSUS_PRE_K", p0_admission=p0, source_lock=source_lock, census=None, output_root=tmp_path / "pre")
    one = build_heavy16_manifest(scenarios, materialization=pre, materialized_config=Path(pre["configs"][0]["path"]))
    two = build_heavy16_manifest(list(reversed(scenarios)), materialization=pre, materialized_config=Path(pre["configs"][0]["path"]))
    assert one["manifest_sha256"] == two["manifest_sha256"]
    manifest_path = tmp_path / "heavy16_manifest.json"
    write_json(manifest_path, one)
    census_plan = build_census_plan(
        ROOT,
        manifest_path=manifest_path,
        output_root=tmp_path / "census_plan",
        materialization=pre,
        materialized_config=Path(pre["configs"][0]["path"]),
    )
    git_identity = observed_git_identity(ROOT)
    _assert_eval_overrides_compose(Path(pre["configs"][0]["path"]), census_plan["commands"][0]["argv"])
    assert census_plan["repo_commit"] == git_identity["commit"]
    assert census_plan["repo_tree"] == git_identity["tree"]
    unsigned = dict(census_plan)
    unsigned.pop("plan_sha256", None)
    assert census_plan["plan_sha256"] == hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    with pytest.raises(V21BError):
        build_heavy16_manifest(scenarios[:15], materialization=pre, materialized_config=Path(pre["configs"][0]["path"]))


def test_signed_materialization_and_single_b4_smoke_contract(tmp_path):
    source_lock, p0, census, zero, pilot, tie, adaptation = _signed_artifacts(tmp_path)
    materialization = materialize_v21b_configs(
        ROOT,
        phase="FORMAL_PROMOTED",
        p0_admission=p0,
        source_lock=source_lock,
        census=census,
        zero_shot=zero,
        pilot=pilot,
        arm_tie=tie,
        adaptation=adaptation,
        output_root=tmp_path / "materialized",
    )
    materialized_b4 = Path(next(row["path"] for row in materialization["configs"] if row["cell"] == "B4"))
    smoke = build_b4_smoke_plan(tmp_path / "smoke_repo", adaptation=adaptation, p0_admission=p0, materialization=materialization, materialized_config=materialized_b4)
    assert smoke["cell"] == "B4"
    assert smoke["num_envs"] == 64 and smoke["batches"] == 10 and smoke["save_frequency"] == 10
    assert smoke["one_cell_only"] is True and smoke["wandb_mode"] == "online"
    assert "--config-dir=" in " ".join(smoke["command"])
    assert "/home/baoquanc/anaconda3/envs/isaaclab/bin/python" in smoke["command"]
    assert f"PYTHONPATH={tmp_path / 'smoke_repo'}" in smoke["command"]
    with pytest.raises(V21BError):
        build_b4_smoke_plan(ROOT, adaptation=adaptation, p0_admission=p0, materialization=materialization, materialized_config=ROOT / "gr00t/rl/config/ablation/wbmanip/base_v21B_B4_theta120_arm_realistic.yaml")


def test_formal_launch_cleanup_and_monitor_are_fail_fast(tmp_path):
    source_lock, p0, census, zero, pilot, tie, adaptation = _signed_artifacts(tmp_path)
    materialization = materialize_v21b_configs(
        ROOT,
        phase="FORMAL_PROMOTED",
        p0_admission=p0,
        source_lock=source_lock,
        census=census,
        zero_shot=zero,
        pilot=pilot,
        arm_tie=tie,
        adaptation=adaptation,
        output_root=tmp_path / "materialized",
    )
    b4_config = Path(next(row["path"] for row in materialization["configs"] if row["cell"] == "B4"))
    smoke_root = tmp_path / "smoke_repo"
    smoke = build_b4_smoke_plan(smoke_root, adaptation=adaptation, p0_admission=p0, materialization=materialization, materialized_config=b4_config)
    evidence = {"schema": V21B_EVIDENCE_SCHEMA, "joint_names": list(V21B_ARM_JOINT_NAMES), "authority": V21B_AUTHORITY_LABEL}
    telemetry = a2_v21b_build_terminal_record(evidence, plan_id="base_v21B_theta_arm_ablation_v1", cell="B4", group="B4", seed=0, source_checkpoint_sha256=source_lock["source_checkpoint_sha256"], adaptation_bundle_sha256=hashlib.sha256(canonical_json_bytes(adaptation)).hexdigest(), provenance={"materialization_phase": "FORMAL_PROMOTED", "scenario_id": "s", "topology": "canonical16", "episode_id": "e", "source_checkpoint_sha256": source_lock["source_checkpoint_sha256"], "source_lock_sha256": materialization["source_lock_sha256"], "source_config_sha256": next(row for row in materialization["configs"] if row["cell"] == "B4")["template_sha256"], "materialization_sha256": materialization["materialization_sha256"], "materialized_config_sha256": next(row for row in materialization["configs"] if row["cell"] == "B4")["sha256"]})
    smoke_pass = adjudicate_b4_smoke(smoke, {"cell": "B4", "exit_code": 0, "process_natural_exit": True, "completed_batches": 10, "batch_indices": list(range(1, 11)), "finite_data": True, "decomposition_sanity": True, "checkpoint_path": str(tmp_path / "smoke.pt"), "checkpoint_sha256": "a" * 64, "telemetry": telemetry, "plan_sha256": smoke["plan_sha256"], "command_sha256": smoke["command_sha256"], "materialization_sha256": smoke["materialization_sha256"], "materialized_config_sha256": smoke["materialized_config_sha256"], "source_checkpoint_sha256": smoke["source_checkpoint_sha256"], "source_lock_sha256": smoke["source_lock_sha256"], "source_config_sha256": smoke["source_config_sha256"]})
    roots = [smoke_root / "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v21B/B4", smoke_root / "logs_eval/base_v21B/smoke/B4", smoke_root / "logs_rl/launchers/base_v21B_smoke/B4"]
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        (root / "marker").write_text("smoke", encoding="utf-8")
    cleanup_manifest = build_smoke_cleanup_manifest(smoke_root, plan=smoke, smoke_pass=smoke_pass, targets=roots)
    cleanup = cleanup_targets(cleanup_manifest, confirm_exact=True, receipt_path=tmp_path / "cleanup.json")
    assert cleanup["status"] == "CLEANUP_PASS"
    configs = {row["cell"]: Path(row["path"]) for row in materialization["configs"]}
    formal = build_formal_launch_plan(ROOT, adaptation=adaptation, p0_admission=p0, smoke_pass=smoke_pass, cleanup_pass=cleanup, materialization=materialization, materialized_configs=configs)
    assert formal["status"] == "FORMAL_PLAN_COMPLETE"
    assert all("--config-dir=" in " ".join(row["argv"]) for row in formal["rows"])
    monitor_plan = build_startup_monitor_plan(formal)
    metrics = {cell: [{"iteration": i, "metrics": {"loss": 1.0}} for i in range(51)] for cell in ("B1", "B2", "B3", "B4", "B5", "B6", "B7")}
    liveness = {cell: {"session_exists": True, "pane_dead": False, "process_alive": True, "session_attached": 0} for cell in metrics}
    startup = monitor_iteration50(metrics, formal_plan=formal, liveness_by_cell=liveness, session_state={"session_exists": True, "session_attached": 0})
    assert monitor_plan["detach_only"] is True and startup["status"] == "STARTUP_50_PASS" and startup["training_continues"] is True
    with pytest.raises(V21BError):
        monitor_iteration50({**metrics, "B7": metrics["B7"][:-1]}, formal_plan=formal, liveness_by_cell=liveness, session_state={"session_exists": True, "session_attached": 0})


def test_probe_plans_reject_raw_b4_template(tmp_path):
    source_lock, p0, census, zero, pilot, tie, adaptation = _signed_artifacts(tmp_path)
    post = materialize_v21b_configs(ROOT, phase="POST_CENSUS", p0_admission=p0, source_lock=source_lock, census=census, output_root=tmp_path / "post")
    with pytest.raises(V21BError):
        build_zero_shot_plan(ROOT, arm_realistic_limit_nm=census["selection"], output_root=tmp_path / "zero", materialization=post, materialized_config=ROOT / "gr00t/rl/config/ablation/wbmanip/base_v21B_B4_theta120_arm_realistic.yaml")
    with pytest.raises(V21BError):
        build_b4_pilot_plan(ROOT, arm_realistic_limit_nm=census["selection"], output_root=tmp_path / "pilot", materialization=post, materialized_config=ROOT / "gr00t/rl/config/ablation/wbmanip/base_v21B_B4_theta120_arm_realistic.yaml", source_lock_path=tmp_path / "source_lock.json")


def test_zero_shot_topology_key_binds_post_census_terminal_records(tmp_path):
    source_lock, p0, census, _, _, _, _ = _signed_artifacts(tmp_path)
    post = materialize_v21b_configs(
        ROOT,
        phase="POST_CENSUS",
        p0_admission=p0,
        source_lock=source_lock,
        census=census,
        output_root=tmp_path / "post_topology",
    )
    plan = build_zero_shot_plan(
        ROOT,
        arm_realistic_limit_nm=census["selection"],
        output_root=tmp_path / "zero_topology",
        manifest_path=tmp_path / "V21B_HEAVY16_MANIFEST.json",
        materialization=post,
        materialized_config=Path(post["configs"][0]["path"]),
        source_checkpoint_sha256=source_lock["source_checkpoint_sha256"],
        source_lock_sha256=source_lock["source_lock_sha256"],
        source_config_sha256=p0["config_sha256_by_cell"]["B4"],
    )
    evidence = {"schema": V21B_EVIDENCE_SCHEMA, "joint_names": list(V21B_ARM_JOINT_NAMES), "authority": V21B_AUTHORITY_LABEL}
    for row in plan["commands"]:
        topology_token = next(token for token in row["argv"] if token.startswith("+env.config.a2_v21B_census_topology="))
        topology = topology_token.split("=", 1)[1]
        assert topology == row["topology"]
        _assert_eval_overrides_compose(Path(post["configs"][0]["path"]), row["argv"])
        record = a2_v21b_build_terminal_record(
            evidence,
            plan_id="base_v21B_theta_arm_ablation_v1",
            cell="B4",
            group="B4",
            seed=0,
            source_checkpoint_sha256=source_lock["source_checkpoint_sha256"],
            adaptation_bundle_sha256=None,
            provenance={
                "materialization_phase": "POST_CENSUS",
                "scenario_id": f"{topology}-scenario",
                "topology": topology,
                "episode_id": f"{topology}-episode",
                "source_lock_sha256": post["source_lock_sha256"],
                "source_config_sha256": plan["source_config_sha256"],
                "materialization_sha256": plan["materialization_sha256"],
                "materialized_config_sha256": plan["materialized_config_sha256"],
            },
        )
        a2_v21b_validate_terminal_record(record)
        with pytest.raises(ValueError):
            a2_v21b_build_terminal_record(
                evidence,
                plan_id="base_v21B_theta_arm_ablation_v1",
                cell="B4",
                group="B4",
                seed=0,
                source_checkpoint_sha256=source_lock["source_checkpoint_sha256"],
                adaptation_bundle_sha256=None,
                provenance={
                    "materialization_phase": "POST_CENSUS",
                    "scenario_id": f"{topology}-scenario",
                    "topology": "wrong_topology",
                    "episode_id": f"{topology}-episode",
                    "source_lock_sha256": post["source_lock_sha256"],
                    "source_config_sha256": plan["source_config_sha256"],
                    "materialization_sha256": plan["materialization_sha256"],
                    "materialized_config_sha256": plan["materialized_config_sha256"],
                },
            )


def test_f4_theta_downgrade_and_deferred_b7_are_bound_in_formal_materialization(tmp_path):
    source_lock, p0, census, zero, pilot, tie, adaptation_inputs = _signed_artifacts(tmp_path)
    pilot = dict(pilot)
    pilot["fork_f4_theta_downgrade"] = True
    adaptation = freeze_adaptation(p0_admission=p0, source_lock=source_lock, census=census, zero_shot=zero, pilot=pilot, arm_tie=calibrate_arm_tie([{"raw_arm_tangent": 0.01, "raw_arc_tracking": 0.01, "positive_income": 0.0}], source_checkpoint_sha256=source_lock["source_checkpoint_sha256"], source_lock_sha256=source_lock["source_lock_sha256"], source_config_sha256=p0["config_sha256_by_cell"]["B7"]))
    assert adaptation["decision"]["theta_high_rad"] == 1.10
    assert adaptation["decision"]["b7_arm_tie_enabled"] is False
    formal = materialize_v21b_configs(ROOT, phase="FORMAL_PROMOTED", p0_admission=p0, source_lock=source_lock, census=census, zero_shot=zero, pilot=pilot, arm_tie=calibrate_arm_tie([{"raw_arm_tangent": 0.01, "raw_arc_tracking": 0.01, "positive_income": 0.0}], source_checkpoint_sha256=source_lock["source_checkpoint_sha256"], source_lock_sha256=source_lock["source_lock_sha256"], source_config_sha256=p0["config_sha256_by_cell"]["B7"]), adaptation=adaptation, output_root=tmp_path / "formal")
    import yaml
    configs = {row["cell"]: yaml.safe_load(Path(row["path"]).read_text(encoding="utf-8")) for row in formal["configs"]}
    assert configs["B1"]["env"]["config"]["a2_v20_send_hinge_threshold"] == 0.90
    assert configs["B3"]["env"]["config"]["a2_v20_send_hinge_threshold"] == 0.90
    for cell in ("B2", "B4", "B5", "B6", "B7"):
        assert configs[cell]["env"]["config"]["a2_v20_send_hinge_threshold"] == 1.10
    b7 = configs["B7"]
    assert b7["v21b_arm_tie_enabled"] is False and b7["v21b_dv4_tested"] is False
    assert b7["env"]["config"]["a2_v20_arm_tangent_carry_scale"] == 0.0
    assert b7["env"]["config"]["a2_v20_handle_arc_tracking_scale"] == 0.0


def test_receipt_bound_probe_adjudicators_reject_legacy_dicts_and_no_write(tmp_path):
    with pytest.raises(V21BError):
        adjudicate_zero_shot([], plan={})
    with pytest.raises(V21BError):
        adjudicate_b4_pilot({}, plan={})
    result = tmp_path / "result.json"
    result.write_text("pre-existing", encoding="utf-8")
    with pytest.raises(V21BError):
        run_process_once(
            argv=[sys.executable, "-c", "pass"],
            repo_root=ROOT,
            output_root=tmp_path / "process",
            env={},
            name="no_write",
            expected_result_paths=[result],
        )


def test_receipt_rejects_self_consistent_rewritten_marker_pair(tmp_path):
    process_root = tmp_path / "rewritten_pair"
    receipt = run_process_once(
        argv=[sys.executable, "-c", "pass"],
        repo_root=ROOT,
        output_root=process_root,
        env={},
        name="rewritten_pair",
    )
    receipt_path = process_root / "process_receipt.json"
    marker_path = Path(receipt["marker_path"])
    original_command_sha = receipt["command_sha256"]
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["argv"] = [sys.executable, "-c", "raise SystemExit(7)"]
    marker["command_sha256"] = hash_command_env(marker["argv"], {})
    marker_without_self = dict(marker)
    marker_without_self.pop("marker_sha256", None)
    marker["marker_sha256"] = hashlib.sha256(canonical_json_bytes(marker_without_self)).hexdigest()
    marker_path.write_text(json.dumps(marker, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    forged = json.loads(receipt_path.read_text(encoding="utf-8"))
    forged["argv"] = list(marker["argv"])
    forged["command_sha256"] = marker["command_sha256"]
    forged["marker_sha256"] = marker["marker_sha256"]
    forged["marker_size"] = marker_path.stat().st_size
    forged_without_self = dict(forged)
    forged_without_self.pop("receipt_sha256", None)
    forged["receipt_sha256"] = hashlib.sha256(canonical_json_bytes(forged_without_self)).hexdigest()
    receipt_path.write_text(json.dumps(forged, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(V21BError, match="bound|lineage|identity"):
        read_process_receipt(
            receipt_path,
            repo_root=ROOT,
            expected_command_sha256=original_command_sha,
            expected_env={},
            expected_result_paths=(),
            require_natural_exit=True,
        )
