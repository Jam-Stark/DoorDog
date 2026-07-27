"""CPU-only tests for the v19 final gate and ablation analysis."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "scriptsFORhuman/v19/a2_piper_v19_final_analysis.py"


def _load():
    spec = importlib.util.spec_from_file_location("a2_piper_v19_final_analysis_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _stats(value: float, n: int = 48) -> dict:
    return {"n": n, "p50": value, "p95": value + 0.05, "min": value - 0.05, "max": value + 0.10}


def _endpoint(
    tmp_path: Path,
    group: str,
    *,
    held: float = 1.50,
    overspeed: int = 0,
    force: float = 20.0,
    slip: float = 2.0,
    goal_canonical: int = 16,
    goal_pooled: int = 48,
    crossing: int = 48,
    release: float = 1.60,
) -> tuple[dict, Path]:
    checkpoint = tmp_path / f"{group}.pt"
    checkpoint.write_bytes(group.encode())
    artifacts = {}
    for seed in (0, 1, 2):
        artifact = tmp_path / f"{group}_seed{seed}"
        artifact.mkdir()
        artifacts[f"seed{seed}"] = str(artifact)
    report_path = tmp_path / f"{group}_endpoint.json"
    report = {
        "schema": "a2_piper_v19_endpoint_report_v1",
        "group": group,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": group * 64,
        "source_artifacts": artifacts,
        "goal": {
            "canonical": {"count": goal_canonical, "total": 16},
            "pooled": {"count": goal_pooled, "total": 48},
        },
        "crossing_while_holding": {"pooled": {"count": crossing, "total": 48}},
        "held_carry": {
            "denominator": 48,
            "hinge_rad": _stats(held),
            "arm_j1_delta_rad": _stats(0.40),
            "arm_j1_delta_gt_0_3": 40,
        },
        "overspeed_terminations": {"count": overspeed, "total": 48},
        "opening_slip": {"n": 48, "p50_cm": 1.0, "p95_cm": slip, "min_cm": 0.5, "max_cm": 2.5},
        "release": {
            "denominator": 48,
            "hinge_rad": _stats(release),
            "post_release_body_contact_count": 0,
            "post_release_body_force_n": _stats(force),
        },
        "pre_crossing_stage3_stage4": {
            "denominator": 1000,
            "bilateral_rate": 0.995,
            "coasting_rate": 0.01,
            "over_force_rate": 0.01,
        },
    }
    report_path.write_text(__import__("json").dumps(report), encoding="utf-8")
    return report, report_path


def _wandb() -> dict:
    return {
        "schema": "a2_piper_v19_wandb_sync_v1",
        "project": "entity/project",
        "sync_cli_exit_code": 0,
        "verified_via_api": True,
        "runs": [
            {
                "group": group,
                "id": f"id{group}",
                "name": f"run-{group}",
                "state": "finished",
                "url": f"https://wandb.ai/entity/project/runs/id{group}",
            }
            for group in ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
        ],
    }


def _post(tmp_path: Path, overrides: dict[str, dict] | None = None) -> dict:
    overrides = overrides or {}
    rows = []
    for group in ("G1", "G2", "G3", "G4", "G5", "G6", "G7"):
        endpoint_kwargs = dict(overrides.get(group, {}))
        _, report_path = _endpoint(tmp_path, group, **endpoint_kwargs)
        rows.append(
            {
                "group": group,
                "status": "COMPLETED",
                "m22_root": str(tmp_path / f"{group}_m22"),
                "adjudication_json": str(tmp_path / f"{group}_adjudication.json"),
                "adjudication_md": str(tmp_path / f"{group}_adjudication.md"),
                "endpoint_report_json": str(report_path),
            }
        )
    return {
        "schema": "a2_piper_v19_post_m22_endpoint_runner_v1",
        "status": "COMPLETED",
        "groups": rows,
    }


def _render_qa(tmp_path: Path, report: dict, *, passed: bool = True) -> dict:
    winner_output = tmp_path / "winner_render"
    g7_output = tmp_path / "g7_render"
    winner_output.mkdir(exist_ok=True)
    g7_output.mkdir(exist_ok=True)
    gate = {"target": "arm_j1 delta > 0.3 rad", "pass": passed}
    winner = {
        "role": "winner",
        "group": "G1",
        "checkpoint": report["groups"]["G1"]["checkpoint"],
        "output_dir": str(winner_output),
        "arm_j1_sweep": [{"env_id": 0, "arm_j1_delta_rad": 0.4}],
        "winner_render_gate": gate,
    }
    g7 = {
        "role": "g7_probe",
        "group": "G7",
        "checkpoint": report["groups"]["G7"]["checkpoint"],
        "output_dir": str(g7_output),
        "arm_j1_sweep": [{"env_id": 0, "arm_j1_delta_rad": 0.5}],
        "winner_render_gate": None,
    }
    return {
        "schema": "a2_piper_v19_render_qa_v1",
        "status": "PASS",
        "artifacts": [winner, g7],
        "winner_render_gate": gate,
        "g7_render_observability": g7["arm_j1_sweep"],
    }


def test_complete_gate_matrix_and_registered_comparisons(tmp_path):
    module = _load()
    post = _post(
        tmp_path,
        {
            "G2": {"held": 1.40},
            "G5": {"overspeed": 3},
            "G7": {"held": 1.62},
        },
    )
    report = module.build_analysis(post, _wandb(), tmp_path / "post.json", tmp_path / "wandb.json")
    assert report["groups"]["G1"]["numeric_gate_status_excluding_render"] == "PASS"
    assert report["groups"]["G2"]["numeric_gate_status_excluding_render"] == "FAIL"
    assert report["groups"]["G5"]["numeric_gate_status_excluding_render"] == "FAIL"
    assert report["comparisons"]["G1_vs_G2_norm_raise"]["carry_gate_read"] == "NORM_RAISE_REQUIRED_IN_THIS_PAIR"
    assert report["comparisons"]["G1_vs_G5_overspeed_fix"]["overspeed_gate_read"] == "FIX_NECESSITY_SUPPORTED"
    assert report["comparisons"]["G1_vs_G4_warmstart"]["drifted_warmstart_common_numeric_gate_read"] == "DRIFTED_WARMSTART_COMMON_NUMERIC_GATES_PASS"
    assert report["comparisons"]["G7_geometric_plateau"]["held_hinge_p50_rad"] == pytest.approx(1.62)
    assert report["render_gate_status"] == "SEPARATE_PLAN_REQUIRED_EVIDENCE"
    report = module.attach_render_qa(report, _render_qa(tmp_path, report), tmp_path / "render_qa.json")
    assert report["render_gate_status"] == "PASS"
    assert report["winner_full_judgement_status"] == "PASS"

    output_json = tmp_path / "analysis.json"
    output_md = tmp_path / "analysis.md"
    module.write_outputs(report, output_json, output_md)
    assert output_json.is_file()
    assert "G1_vs_G2_norm_raise" in output_md.read_text(encoding="utf-8")



def test_pre_registered_no_carry_fallback_selects_g3(tmp_path):
    module = _load()
    post = _post(
        tmp_path,
        {
            "G1": {"held": 1.30},
            "G2": {"held": 1.40},
            "G6": {"held": 1.35},
            "G7": {"held": 1.42},
        },
    )
    report = module.build_analysis(
        post, _wandb(), tmp_path / "post.json", tmp_path / "wandb.json"
    )
    decision = report["release_decision"]
    assert decision["status"] == "SELECTED"
    assert decision["selected_release_group"] == "G3"
    assert decision["reason"] == "PRE_REGISTERED_NO_CARRY_FALLBACK"
    assert decision["carry_p50_gate_pass"] == {"G1": False, "G2": False, "G6": False}
    assert decision["g7_plateau_ge_1_5"] is False
    assert decision["g7_held_hinge_p50_rad"] == pytest.approx(1.42)
    assert decision["g7_held_hinge_p95_rad"] == pytest.approx(1.47)

def test_render_checkpoint_must_match_endpoint(tmp_path):
    module = _load()
    report = module.build_analysis(_post(tmp_path), _wandb(), tmp_path / "post.json", tmp_path / "wandb.json")
    render = _render_qa(tmp_path, report)
    wrong = tmp_path / "wrong.pt"
    wrong.write_bytes(b"wrong")
    render["artifacts"][0]["checkpoint"] = str(wrong)
    with pytest.raises(module.V19FinalAnalysisError, match="does not match endpoint"):
        module.attach_render_qa(report, render, tmp_path / "render_qa.json")


def test_gate_boundaries_preserve_strict_inequalities():
    module = _load()
    metrics = {
        "goal_canonical_count": 15,
        "goal_pooled_count": 46,
        "overspeed_termination_count": 0,
        "opening_slip_p95_cm": 3.0,
        "post_release_body_contact_count": 2,
        "post_release_body_force_p95_n": 80.0,
        "pre_crossing_bilateral_rate": 0.99,
        "pre_crossing_coasting_rate": 0.02,
        "pre_crossing_over_force_rate": 0.019999,
        "crossing_while_holding_pooled_count": 46,
        "held_hinge_p50_rad": 1.45,
        "hinge_at_release_p50_rad": 1.55,
    }
    result = module._gates("G1", metrics)
    assert result["gates"]["goal_canonical"]["pass"] is True
    assert result["gates"]["opening_slip_p95_cm"]["pass"] is True
    assert result["gates"]["held_hinge_p50_rad"]["pass"] is True
    assert result["gates"]["hinge_at_release_p50_rad"]["pass"] is True
    assert result["gates"]["post_release_body_force_p95_n"]["pass"] is False
    assert result["gates"]["pre_crossing_coasting_rate"]["pass"] is False
    assert result["numeric_gate_status_excluding_render"] == "FAIL"


def test_nonterminal_post_state_fails_fast(tmp_path):
    module = _load()
    post = _post(tmp_path)
    post["status"] = "RUNNING_POST_M22"
    with pytest.raises(module.V19FinalAnalysisError, match="not terminal"):
        module.build_analysis(post, _wandb(), tmp_path / "post.json", tmp_path / "wandb.json")


def test_failed_group_is_explicitly_unevaluable(tmp_path):
    module = _load()
    post = _post(tmp_path)
    post["status"] = "COMPLETED_WITH_FAILURES"
    post["groups"][2] = {
        "group": "G3",
        "status": "ADJUDICATION_FAILED",
        "m22_root": str(tmp_path / "G3_m22"),
        "adjudication_step": {"exit_code": 2},
    }
    report = module.build_analysis(post, _wandb(), tmp_path / "post.json", tmp_path / "wandb.json")
    assert report["groups"]["G3"]["numeric_gate_status_excluding_render"] == "UNEVALUABLE"
    assert report["groups"]["G3"]["failure"]["status"] == "ADJUDICATION_FAILED"
    assert report["comparisons"]["G1_vs_G3_carry_institution"]["status"] == "UNEVALUABLE"


def test_unfinished_wandb_run_fails_fast(tmp_path):
    module = _load()
    wandb = _wandb()
    wandb["runs"][-1]["state"] = "running"
    with pytest.raises(module.V19FinalAnalysisError, match="state must be finished"):
        module.build_analysis(_post(tmp_path), wandb, tmp_path / "post.json", tmp_path / "wandb.json")
