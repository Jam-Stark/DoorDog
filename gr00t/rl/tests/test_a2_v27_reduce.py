from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).parents[3]
REDUCER_PATH = ROOT / "scriptsFORhuman/v27/v27_reduce.py"
SPEC = importlib.util.spec_from_file_location("v27_reduce", REDUCER_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _runtime(side: str, episodes: int) -> dict:
    return {
        "seed": 1,
        "checkpoint": "checkpoint.pt",
        "checkpoint_load_mode": "full",
        "auto_load_latest": False,
        "num_envs": episodes,
        "algo": {"config": {"eval": {"num_eval_episodes": episodes, "eval_num_envs_episodes": True}}},
        "env": {"config": {"a2_v26_door_open_lr": side, "enable_staged_reset": False, "a2_v26_8_penalty_driver": None}},
        "rewards": {"reward_penalty_curriculum": False},
    }


def _write_lane(root: Path, side: str, episodes: int, *, clean: bool = True, recovery: bool = False, integrity: int = 0) -> Path:
    root.mkdir()
    diagnostics = []
    for env_id in range(episodes):
        v27 = {
            "body_panel_force_max_from_stage3_n": 0.0 if clean else 6.0,
            "integrity_violations": integrity,
            "arm_j4_limit_residence_steps": 1,
            "first_episode_control_steps": 10,
            "first_crossing_hinge_rad": 1.2,
            "crossing_while_holding": True,
        }
        if recovery:
            v27.update({
                "recovery_itt": True,
                "injection_status": "TRIGGERED" if env_id == 0 else "NOT_TRIGGERED",
                "loss_event": env_id == 0,
                "regrasp_success": env_id == 0,
                "recovered_complete": env_id == 0,
                "recovered_clean_complete": env_id == 0,
            })
        diagnostics.append({
            "env_id": env_id,
            "door_handle_side": side,
            "episode_length_buf": 20,
            "post_release_body_force_max": 0.0,
            "a2_v27": v27,
            "v26_2": {"integrity_violations": 0, "handle_depression_active_steps": 25, "unlatch_hold_active_steps": 25},
            "v26_3": {"integrity_violations": 0},
        })
    (root / "metrics_eval.json").write_text(json.dumps({
        "completed_episodes": episodes,
        "episode_terminal_diagnostics": diagnostics,
        "episode_terminal_reasons": ["complete"] * episodes,
        "episode_max_stage_reached": [5] * episodes,
    }), encoding="utf-8")
    trace = [
        {
            "env_id": env_id,
            "first_episode_active": True,
            "episode_index": 0,
            "step_index": step,
            "door_handle_joint_pos": 0.7,
            "door_hinge_joint_pos": 0.3,
            "both_contact": True,
            "stage_buf": 3,
            "root_x_ever_crossed": step == 0,
            "crossing_while_holding": True,
            "door_body_panel_normal_force_total": 0.0,
            "arm_joint_names": ["arm_j1", "arm_j2", "arm_j3", "arm_j4", "arm_j5", "arm_j6"],
            "arm_joint_pos": [0.0] * 6,
        }
        for env_id in range(episodes)
        for step in range(25)
    ]
    (root / "stage2_5_step_trace.json").write_text(json.dumps(trace), encoding="utf-8")
    hydra = root / ".hydra"
    hydra.mkdir()
    (hydra / "runtime_config.yaml").write_text(yaml.safe_dump(_runtime(side, episodes)), encoding="utf-8")
    return root


def _lane(cell: str, stratum: str, side: str, artifact: Path, episodes: int, *, recovery: bool = False) -> dict:
    return {
        "cell": cell,
        "stratum": stratum,
        "side": side,
        "seed": 1,
        "episodes": episodes,
        "checkpoint": "checkpoint.pt",
        "artifact_path": str(artifact),
        "recovery_itt": recovery,
    }


def test_clean_complete_is_a_single_episode_boolean_conjunction(tmp_path: Path):
    artifact = _write_lane(tmp_path / "clean", "left", 1)
    summary = MODULE.summary_for_lane(_lane("C_S21", "nominal", "left", artifact, 1), 1)
    assert summary["complete"] == 1
    assert summary["clean_complete"] == 1
    dirty = _write_lane(tmp_path / "dirty", "left", 1, clean=False)
    dirty_summary = MODULE.summary_for_lane(_lane("C_S22", "nominal", "left", dirty, 1), 1)
    assert dirty_summary["complete"] == 1
    assert dirty_summary["clean_complete"] == 0


def test_recovery_itt_keeps_all_episodes_in_the_denominator(tmp_path: Path):
    artifact = _write_lane(tmp_path / "recovery", "left", 2, recovery=True)
    summary = MODULE.summary_for_lane(_lane("R2", "injected", "left", artifact, 2, recovery=True), 2)
    assert summary["recovery_itt"] == {
        "denominator": 2,
        "loss_events": 1,
        "not_triggered": 1,
        "regrasp_success": 1,
        "recovered_complete": 1,
        "recovered_clean_complete": 1,
    }


def test_manifest_keeps_strata_separate(tmp_path: Path):
    lanes = []
    for stratum in ("nominal", "P02"):
        for side in ("left", "right"):
            artifact = _write_lane(tmp_path / f"{stratum}_{side}", side, 1)
            lanes.append(_lane("L1_S31", stratum, side, artifact, 1))
    payload = MODULE.reduce_manifest({"schema": MODULE.MANIFEST_SCHEMA, "step": 1000, "lanes": lanes}, 1)
    assert payload["status"] == "V27_COMPLETE"
    assert set(payload["cells"]["L1_S31"]) == {"nominal", "P02"}
    assert payload["cells"]["L1_S31"]["P02"]["right"]["episodes"] == 1


def test_exact_n_mismatch_marks_the_cell_invalid(tmp_path: Path):
    artifact = _write_lane(tmp_path / "short", "left", 1)
    lane = _lane("C_S21", "nominal", "left", artifact, 1)
    payload = MODULE.reduce_manifest({"schema": MODULE.MANIFEST_SCHEMA, "step": 1000, "lanes": [lane]}, 2)
    assert payload["status"] == "V27_INVALID"
    assert "C_S21" in payload["invalid_cells"]


def test_integrity_violation_marks_its_cell_invalid(tmp_path: Path):
    artifact = _write_lane(tmp_path / "integrity", "left", 1, integrity=1)
    lane = _lane("C_S21", "nominal", "left", artifact, 1)
    payload = MODULE.reduce_manifest({"schema": MODULE.MANIFEST_SCHEMA, "step": 1000, "lanes": [lane]}, 1)
    assert payload["status"] == "V27_INVALID"
    assert "integrity_violations" in payload["invalid_cells"]["C_S21"][0]


def _gate_side(clean_complete: int) -> dict:
    return {
        "episodes": 64,
        "D": 60,
        "S4+": 60,
        "complete": 60,
        "clean_complete": clean_complete,
        "terminal_reasons": {},
    }


def test_wave_a_uses_two_seed_mean_clean_complete_delta():
    cells = {}
    for arm, seed, left_clean in (("C", 1, 50), ("C", 2, 50), ("Q1", 1, 60), ("Q1", 2, 56), ("Q2", 1, 50), ("Q2", 2, 50)):
        cells[f"{arm}_S2{seed}"] = {"nominal": {"left": _gate_side(left_clean), "right": _gate_side(56)}}
    outcome = MODULE.wave_a_outcome(cells)
    assert outcome["outcome"] == "QUALITY_ALIGNED(Q1)"
    assert outcome["recipe_a"] == "Q1"


@pytest.mark.parametrize("early_stage", [0, 1])
def test_pre_stage2_termination_has_valid_empty_trace(tmp_path, early_stage):
    artifact = _write_lane(tmp_path / "early", "left", 1)
    path = artifact / "metrics_eval.json"
    metrics = json.loads(path.read_text())
    metrics["episode_max_stage_reached"] = [early_stage]
    metrics["episode_terminal_reasons"] = ["stage_overtime"]
    path.write_text(json.dumps(metrics))
    (artifact / "stage2_5_step_trace.json").write_text("[]")
    summary = MODULE.summary_for_lane(_lane("SC_S201", "nominal", "left", artifact, 1), 1)
    assert summary["D"] == summary["open_hold"] == summary["complete"] == summary["clean_complete"] == 0
    assert summary["episodes"] == 1


def test_missing_trace_still_invalid_after_stage2_entry(tmp_path):
    artifact = _write_lane(tmp_path / "missing", "left", 1)
    (artifact / "stage2_5_step_trace.json").write_text("[]")
    with pytest.raises(MODULE.ReducerError, match="missing trace"):
        MODULE.summary_for_lane(_lane("SC_S201", "nominal", "left", artifact, 1), 1)
