"""CPU contract tests for strict M22, paired, render, and final gates."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _m22_metrics():
    return {
        "goal_count": 16,
        "crossing_while_holding_count": 16,
        "upper_dof_overspeed_count": 0,
        "pre_crossing_bilateral_rate": 1.0,
        "pre_crossing_coasting_rate": 0.0,
        "pre_crossing_over_force_rate": 0.0,
        "goal_with_pre_send_crossing_count": 0,
        "send_ready_count": 16,
        "hinge_at_first_crossing_p50": 0.90,
        "hinge_at_first_crossing_p10": 0.85,
        "pre_send_forward_displacement_p95": 0.20,
        "pre_send_lateral_displacement_p95": 0.15,
        "pre_send_planar_displacement_p95": 0.25,
        "pre_send_yaw_change_p95": 0.30,
        "arm_tangent_share_p50": 0.60,
        "arm_tangent_share_p10": 0.45,
        "arc_position_error_p95_m": 0.03,
        "arc_orientation_error_p95_rad": 0.25,
        "along_handle_slip_p95_m": 0.03,
        "a_positive_income_ratio_p95": 0.10,
        "positive_hinge_velocity_p95": 0.40,
        "hinge_acceleration_p95": 1.00,
        "hinge_jerk_p95": 28.0,
        "arm_action_rate_p95": 2.20,
        "arm_action_jerk_p95": 3.60,
        "median_task_time_s": 15.0,
    }


def _m22_manifest_and_evidence(module, group: str):
    config_sha = format(int(group[1:]), "x") * 64
    candidates = []
    rows = []
    for step in module.STEPS:
        checkpoint_sha = hashlib.sha256(f"{group}:{step}".encode()).hexdigest()
        candidate = {
            "candidate_id": f"{group}:step{step}",
            "step": step,
            "path": f"logs_rl/a2_piper_full_stage_a2_base/base_v20_R1/{group}/model_step_{step:06d}.pt",
            "sha256": checkpoint_sha,
            "group": group,
            "run_id": f"run-{group}",
            "config_sha256": config_sha,
        }
        candidates.append(candidate)
        rows.append(
            {
                "strict_status": "STRICT_VALID",
                "candidate": candidate,
                "metrics": _m22_metrics(),
                "binding": {
                    "checkpoint_sha256": checkpoint_sha,
                    "config_sha256": config_sha,
                    "group": group,
                    "run_id": candidate["run_id"],
                },
                "output": {
                    "group": group,
                    "step": step,
                    "path": f"logs_eval/base_v20_R1/m22/{group}/step{step}",
                },
                "eval_command": {"command": ["eval", group, str(step)], "exit_code": 0},
            }
        )
    return (
        {"plan_id": module.PLAN_ID, "group": group, "candidates": candidates},
        {"rows": rows},
    )


def test_m22_adjudicate_all_is_exact_seven_by_ten():
    module = _module("r1_m22_gates", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_m22_adjudicator.py")
    manifests, evidence = {}, {}
    for group in [f"G{i}" for i in range(1, 8)]:
        manifests[group], evidence[group] = _m22_manifest_and_evidence(module, group)
    result = module.adjudicate_all(manifests=manifests, evidence=evidence)
    assert result["status"] == "RUNTIME PASS"
    assert result["seven_by_ten"] is True
    assert result["total_rows"] == 70
    assert all(row["selection_status"] == "POLICY PASS" for row in result["groups"].values())


def _paired_report(group: str, checkpoint: str = "a", config: str = "b"):
    return {
        "plan_id": "base_v20_R1_policy_behavior_v1",
        "status": "STRICT_VALID",
        "binding": {"group": group, "config": group + ".yaml", "checkpoint_sha256": checkpoint * 64, "config_sha256": config * 64},
        "metrics": {"arm_tangent_share_p50": 0.6, "hinge_at_first_crossing_p50": 0.9},
    }


def test_paired_analysis_has_no_zero_imputation():
    module = _module("r1_paired_gates", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_paired_analysis.py")
    hex_digits = ("a", "b", "c", "d", "e", "f", "0")
    reports = {group: _paired_report(group, checkpoint=hex_digits[i - 1], config=hex_digits[(i + 1) % len(hex_digits)]) for i, group in enumerate([f"G{i}" for i in range(1, 8)], 1)}
    result = module.paired_analysis(reports)
    assert result["status"] == "RUNTIME SEMANTIC PASS"
    assert result["zero_imputation"] is False
    reports["G1"].pop("metrics")
    with pytest.raises(module.R1Error):
        module.paired_analysis(reports)


def test_render_queue_and_adjudicator_bind_checkpoint_config_and_logical_cuda0(tmp_path):
    queue = _module("r1_render_queue_gates", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_render_queue.py")
    adjudicator = _module("r1_render_adjudicator_gates", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_render_adjudicator.py")
    selected_checkpoints, selected_configs = {}, {}
    groups = ("G1", "G4", "G6", "G7")
    for group in groups:
        checkpoint = tmp_path / (group + ".pt")
        config = tmp_path / (group + ".yaml")
        checkpoint.write_bytes((group + " checkpoint").encode())
        config.write_text(group + " config" + chr(10), encoding="utf-8")
        selected_checkpoints[group] = checkpoint
        selected_configs[group] = {"path": str(config), "sha256": hashlib.sha256(config.read_bytes()).hexdigest()}
    output = tmp_path / "logs_eval/base_v20_R1/render/matched"
    result = queue.build_render_queue(
        output_dir=output,
        gpu=3,
        groups=groups,
        selected_checkpoints=selected_checkpoints,
        selected_configs=selected_configs,
        admission_manifest_sha256="e" * 64,
    )
    assert result["status"] == "RUNTIME PASS"
    assert all(row["env"]["CUDA_VISIBLE_DEVICES"] == "3" for row in result["rows"])
    assert all(row["env"]["ACCELERATE_TORCH_DEVICE"] == "cuda:0" for row in result["rows"])
    with pytest.raises(queue.R1Error):
        queue.build_render_queue(
            checkpoint=selected_checkpoints["G1"],
            output_dir=tmp_path / "logs_eval/base_v20_R1/render/fallback",
            gpu=3,
            groups=("G1",),
            selected_checkpoints=selected_checkpoints,
            selected_configs=selected_configs,
            admission_manifest_sha256="e" * 64,
        )
    group = "G1"
    row = result["rows"][0]
    evidence_dir = output / group
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "render_result.json").write_text(
        json.dumps({
            "plan_id": adjudicator.PLAN_ID,
            "status": "RUNTIME PASS",
            "checkpoint_sha256": row["checkpoint_sha256"],
            "config_sha256": row["config_sha256"],
            "doors": list(queue.DOORS),
            "cameras": list(queue.CAMERAS),
        }) + chr(10),
        encoding="utf-8",
    )
    adjudicated = adjudicator.adjudicate_render(
        checkpoint=selected_checkpoints[group],
        checkpoint_sha256=row["checkpoint_sha256"],
        config=Path(row["config"]),
        config_sha256=row["config_sha256"],
        output_dir=evidence_dir,
        doors=tuple(queue.DOORS),
        cameras=tuple(queue.CAMERAS),
    )
    assert adjudicated["status"] == "RUNTIME PASS"
    assert adjudicated["binding"]["checkpoint_sha256"] == row["checkpoint_sha256"]


def test_final_analysis_requires_one_matching_holdout_and_render_winner():
    module = _module("r1_final_gates", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_final_analysis.py")
    winner = {"checkpoint_sha256": "a" * 64, "config_sha256": "b" * 64}
    adjudications = {
        group: {
            "selection_status": "POLICY PASS",
            "selected_checkpoint": {"candidate": {"step": 250}, "binding": winner},
        }
        for group in [f"G{i}" for i in range(1, 8)]
    }
    holdout = {"plan_id": module.PLAN_ID, "status": "RUNTIME PASS", "binding": winner}
    render = {"plan_id": module.PLAN_ID, "status": "RUNTIME PASS", "binding": winner}
    result = module.finalize(adjudications=adjudications, holdout_pass=holdout, render_pass=render, release_candidate="G4")
    assert result["status"] == "POLICY PASS"
    assert result["formal_training_ready"] is True
    bad_render = {**render, "binding": {"checkpoint_sha256": "c" * 64, "config_sha256": "b" * 64}}
    with pytest.raises(module.R1Error):
        module.finalize(adjudications=adjudications, holdout_pass=holdout, render_pass=bad_render, release_candidate="G4")


def test_semantic_admission_requires_all_runtime_evidence_and_rejects_all_true(tmp_path):
    module = _module("r1_semantic_gates", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_semantic_admission.py")
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    checks = {
        "taskspace_mask_contract": True,
        "release_order_contract": True,
        "snapshot_stage4_contract": True,
        "snapshot_stage5_contract": True,
    }
    for name in module.REQUIRED_EVIDENCE:
        (evidence_dir / name).write_text(
            json.dumps({"plan_id": module.PLAN_ID, "status": "RUNTIME SEMANTIC PASS", "checks": checks, "command": ["check"], "exit_code": 0}) + chr(10),
            encoding="utf-8",
        )
    common = {"plan_id": module.PLAN_ID, "status": "RUNTIME SEMANTIC PASS", "provenance": {"plan_id": module.PLAN_ID}, "command": ["eval"], "exit_code": 0}
    for name, artifact_name, count, group in [("b0_admission.json", "b0_pooled48", 48, None), ("forced_one_env.json", "forced_one_env", 1, None)]:
        payload = {**common, "artifact_name": artifact_name, "record_count": count}
        (evidence_dir / name).write_text(json.dumps(payload) + chr(10), encoding="utf-8")
    for group in module.CANONICAL_GROUPS:
        payload = {**common, "artifact_name": "canonical16_" + group, "record_count": 16, "config_group": group}
        (evidence_dir / ("canonical16_" + group + ".json")).write_text(json.dumps(payload) + chr(10), encoding="utf-8")
    result = module.run_semantic_assertions(evidence_dir=evidence_dir, repo_root=ROOT)
    assert result["status"] == "RUNTIME SEMANTIC PASS"
    bad = json.loads((evidence_dir / module.REQUIRED_EVIDENCE[0]).read_text())
    bad["all_true"] = True
    (evidence_dir / module.REQUIRED_EVIDENCE[0]).write_text(json.dumps(bad) + chr(10), encoding="utf-8")
    with pytest.raises(module.R1Error):
        module.run_semantic_assertions(evidence_dir=evidence_dir, repo_root=ROOT)


def test_promotion_chain_requires_typed_status_and_whitelisted_frozen_bytes(tmp_path, monkeypatch):
    module = _module("r1_promotion_gates", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_promote_configs.py")
    repo = tmp_path / "repo"
    config_dir = repo / "gr00t/rl/config/ablation/wbmanip"
    config_dir.mkdir(parents=True)
    preflight_rows = []
    for spec in module.GROUPS:
        source = config_dir / spec["config"]
        source.write_text(
            "# @package _global_" + chr(10)
            + "env:" + chr(10)
            + "  config:" + chr(10)
            + "    a2_v20_formal_values_frozen: true" + chr(10)
            + "    a2_v20_formal_launch: false" + chr(10),
            encoding="utf-8",
        )
        preflight_rows.append({"group": spec["group"], "sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest()})
    admission = repo / "admission.json"
    admission.write_text(json.dumps({"plan_id": module.PLAN_ID, "status": "POLICY PASS"}) + chr(10), encoding="utf-8")
    admission_sha = __import__("hashlib").sha256(admission.read_bytes()).hexdigest()
    chain = {}
    statuses = {"preflight": "STATIC PASS", "semantic": "RUNTIME SEMANTIC PASS", "pilot": "POLICY LEARNABILITY PASS", "smoke": "RUNTIME PASS"}
    for name, status in statuses.items():
        path = repo / (name + ".json")
        path.write_text(json.dumps({"plan_id": module.PLAN_ID, "status": status, "candidate_configs": preflight_rows} if name == "preflight" else {"plan_id": module.PLAN_ID, "status": status}) + chr(10), encoding="utf-8")
        chain[name] = path
    monkeypatch.setattr(module, "verify_hydra_promoted_group", lambda **kwargs: {"status": "HYDRA_RESOLVED", "group": module.FROZEN_GROUP})
    result = module.promote_configs(
        repo_root=repo,
        output_dir=repo / module.FROZEN_NAMESPACE,
        admission_manifest_sha256=admission_sha,
        admission_manifest=admission,
        chain_artifacts=chain,
    )
    assert result["status"] == "POLICY PASS"
    for row in result["configs"]:
        assert Path(row["destination"]).is_file()
        assert "/ablation/" + module.FROZEN_GROUP + "/" in row["destination"].replace("\\", "/")
    bad_chain = dict(chain)
    bad_chain["smoke"] = repo / "bad_smoke.json"
    bad_chain["smoke"].write_text(json.dumps({"plan_id": module.PLAN_ID, "status": "POLICY PASS"}) + chr(10), encoding="utf-8")
    with pytest.raises(module.R1Error):
        module._validate_chain(bad_chain)


def test_preflight_distinguishes_generic_shared_yaml_from_strict_ablation_validation():
    module = _module("r1_preflight_yaml_gate", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_preflight.py")
    shared = (
        "gr00t/rl/config/env/door_open_a2_base.yaml",
        "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml",
    )
    parsed = module._static_parse(ROOT, shared)
    assert {row["path"] for row in parsed} == set(shared)
    with pytest.raises(module.R1Error):
        module._load_config(ROOT, shared[0])
    candidate = module.CONFIG_DIR + "/base_v20_R1_G1_g2_continuation.yaml"
    loaded = module._load_config(ROOT, candidate, group="G1")
    assert loaded["env"]["config"]["a2_v20_R1_plan_id"] == module.PLAN_ID


def test_preflight_manifest_coverage_and_real_exp_ablation_resolve_markers():
    module = _module("r1_preflight_coverage_gate", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_preflight.py")
    assert "gr00t/rl/envs/base_task/staged_task_base.py" in module.PREFLIGHT_SOURCE_PATHS
    assert "scriptsFORhuman/v20_R1/__init__.py" in module.R1_SCRIPT_PATHS
    assert "scriptsFORhuman/v20_R1/a2_piper_v20_R1_render_adjudicator.py" in module.R1_SCRIPT_PATHS
    assert "gr00t/rl/tests/test_a2_v20_R1_gates.py" in module.STATIC_TEST_PATHS
    assert "gr00t/rl/tests/test_a2_v20_staged_reset_state.py" in module.STATIC_TEST_PATHS
    relative = module.CONFIG_DIR + "/base_v20_R1_G1_g2_continuation.yaml"
    command = module._hydra_resolve_command(ROOT, relative)
    assert ["--cfg", "job", "--resolve"] == command[3:6]
    assert "+exp=wbmanip/door_open_a2_base_lstm" in command
    assert "+ablation=wbmanip/base_v20_R1_G1_g2_continuation" in command
    resolved = module._compose_config(ROOT, relative, group="G1")
    assert resolved["env"]["config"]["a2_v20_R1_plan_id"] == module.PLAN_ID
    assert resolved["checkpoint_load_mode"] == "policy_only"
