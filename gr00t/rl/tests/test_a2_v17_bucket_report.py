"""Synthetic strict tests for the v17 M38 reporter."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
REPORT_SOURCE = ROOT / "scriptsFORhuman/v17/a2_piper_v17_bucket_report.py"


def _reporter():
    spec = importlib.util.spec_from_file_location(
        "a2_piper_v17_bucket_report_test", REPORT_SOURCE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _weight(env_id: int) -> float:
    return 90.0 if env_id < 5 else (120.0 if env_id < 10 else 140.0)


def _result(seed: int, env_id: int) -> dict:
    return {
        "seed": seed,
        "env_id": env_id,
        "door_hinge_drive_max_force": 4.0,
        "door_handle_drive_max_force": 2.0,
        "door_handle_height": 0.80 if env_id < 8 else 1.0,
        "door_weight": _weight(env_id),
        "goal_reached": True,
        "max_stage": 5,
        "final_stage": 5,
        "stage0_to1_staging_standoff": 0.6,
        "crossing_while_holding": True,
        "hinge_at_crossing": 1.35,
        "hinge_at_release": 1.40,
        "root_x_at_release": 0.4,
        "post_release_body_contact": bool(env_id % 2),
        "post_release_body_force_max": float(20 + env_id),
        "episode_length_buf": 3,
        "control_dt": 0.02,
        "reward_episode_sums_unit": "episode-sum",
        "root_pos_rel": [2.0 + 0.1 * env_id, 0.0, 0.5],
        "reward_episode_sums": {
            "penalty_a2_posture_command_l1": -0.5,
            "penalty_a2_door_body_contact": -1.0,
            "complete": 4.0,
        },
    }


def _trace(seed: int, env_id: int, stage: int, step: int) -> dict:
    body = [0.0] * 13
    arm = [0.0] * 10
    return {
        "seed": seed,
        "env_id": env_id,
        "first_episode_active": True,
        "episode_index": 0,
        "stage_buf": stage,
        "door_hinge_drive_max_force": 4.0,
        "door_handle_height": 0.80 if env_id < 8 else 1.0,
        "door_weight": _weight(env_id),
        "door_body_panel_normal_force_per_filter": body,
        "door_body_panel_normal_force_total": 0.0,
        "door_arm_panel_normal_force_per_filter": arm,
        "door_arm_panel_normal_force_total": 0.0,
        "physical_base_command": [0.0, 0.0, 0.0, 0.0, 0.0],
        "arm_j7_j8_pos": [0.0, 0.0],
        "arm_j7_j8_open_target": [0.035, -0.035],
        "both_contact": True,
        "over_force": False,
        "door_hinge_joint_vel": 0.2,
        "root_x_ever_crossed": stage == 4,
        "step_index": step,
        "episode_length_buf": step,
        "control_dt": 0.02,
        "root_pos_rel": [0.1 * step, 0.0, 0.5],
        "reward_episode_sums_unit": "episode-sum",
        "reward_episode_sums": {
            "penalty_a2_posture_command_l1": -0.1 * step,
            "penalty_a2_door_body_contact": 0.0,
            "complete": 0.0,
        },
    }


def _inputs(tmp_path: Path):
    paths = {}
    for seed in (0, 1, 2):
        result_path = tmp_path / f"seed{seed}_result.json"
        trace_path = tmp_path / f"seed{seed}_trace.json"
        result_path.write_text(
            json.dumps([_result(seed, env_id) for env_id in range(16)]),
            encoding="utf-8",
        )
        trace_path.write_text(
            json.dumps(
                [
                    row
                    for env_id in range(16)
                    for row in (
                        _trace(seed, env_id, 2, 1),
                        _trace(seed, env_id, 3, 2),
                        _trace(seed, env_id, 4, 3),
                    )
                ]
            ),
            encoding="utf-8",
        )
        paths[seed] = (result_path, trace_path)
    return paths


def test_report_adds_exact_continuous_mass_bucket_metrics(tmp_path):
    module = _reporter()
    result_sets = {}
    trace_sets = {}
    for seed, (result_path, trace_path) in _inputs(tmp_path).items():
        result_sets[seed] = module.load_result(result_path, expected_seed=seed)
        trace_sets[seed] = module.load_trace(
            trace_path,
            expected_seed=seed,
            result_records=result_sets[seed],
        )
    report = module.build_report(result_sets, trace_sets, group="G1")
    assert report["schema"] == "a2_piper_v17_m38_bucket_report_v1"
    assert report["group"] == "G1"
    assert report["record_count"] == 48
    assert report["m33"]["goal"]["pooled"]["numerator"] == 48
    pooled = report["m38"]["pooled"]
    assert pooled["opening_phase_duration_seconds"]["mean"] == pytest.approx(0.04)
    assert pooled["episode_length_steps"]["n"] == 48
    assert pooled["delta_root_x_post_release"]["min"] == pytest.approx(1.6)
    assert pooled["reward_episode_sums_unit"] == "episode-sum"
    assert pooled["reward_episode_sums"]["penalty_a2_posture_command_l1"]["mean"] == -0.5
    assert report["m38"]["by_mass_bucket"]["[80,110)"]["reward_episode_sums_unit"] == "episode-sum"
    assert report["m38"]["by_mass_bucket"]["[80,110)"]["record_count"] == 15
    assert report["m38"]["by_mass_bucket"]["[110,135)"]["record_count"] == 15
    assert report["m38"]["by_mass_bucket"]["[135,160]"]["record_count"] == 18


def test_missing_or_inconsistent_exact_telemetry_fails_fast():
    module = _reporter()
    raw = _result(0, 0)
    missing = dict(raw)
    missing.pop("reward_episode_sums")
    with pytest.raises(module.V17ReportError, match="missing"):
        module.normalize_result(missing, expected_seed=0)

    result = module.normalize_result(raw, expected_seed=0)
    trace = _trace(0, 0, 3, 2)
    bad_dt = dict(trace)
    bad_dt["control_dt"] = 0.01
    with pytest.raises(module.V17ReportError, match="exactly match"):
        module.normalize_trace(bad_dt, expected_seed=0, result_by_env={0: result})

    bad_rewards = dict(trace)
    bad_rewards["reward_episode_sums"] = {"complete": 0.0}
    with pytest.raises(module.V17ReportError, match="reward keys"):
        module.normalize_trace(
            bad_rewards, expected_seed=0, result_by_env={0: result}
        )


@pytest.mark.parametrize("failure_mode", ("missing", "duplicate", "reordered"))
def test_trace_step_sequence_must_be_unique_ordered_and_contiguous(
    tmp_path, failure_mode
):
    module = _reporter()
    result_path, trace_path = _inputs(tmp_path)[0]
    results = module.load_result(result_path, expected_seed=0)
    rows = json.loads(trace_path.read_text(encoding="utf-8"))
    env0_rows = [row for row in rows if row["env_id"] == 0]
    other_rows = [row for row in rows if row["env_id"] != 0]
    if failure_mode == "missing":
        env0_rows.pop(1)
    elif failure_mode == "duplicate":
        env0_rows.insert(2, dict(env0_rows[1]))
    else:
        env0_rows[1], env0_rows[2] = env0_rows[2], env0_rows[1]
    trace_path.write_text(
        json.dumps(env0_rows + other_rows),
        encoding="utf-8",
    )
    with pytest.raises(module.V17ReportError, match="unique, ordered, and contiguous"):
        module.load_trace(
            trace_path,
            expected_seed=0,
            result_records=results,
        )


def test_trace_terminal_episode_length_must_match_result(tmp_path):
    module = _reporter()
    result_path, trace_path = _inputs(tmp_path)[0]
    results_raw = json.loads(result_path.read_text(encoding="utf-8"))
    results_raw[0]["episode_length_buf"] = 4
    result_path.write_text(json.dumps(results_raw), encoding="utf-8")
    results = module.load_result(result_path, expected_seed=0)
    with pytest.raises(module.V17ReportError, match="must match result value"):
        module.load_trace(
            trace_path,
            expected_seed=0,
            result_records=results,
        )


def test_trace_step_index_is_required():
    module = _reporter()
    result = module.normalize_result(_result(0, 0), expected_seed=0)
    raw = _trace(0, 0, 2, 1)
    raw.pop("step_index")
    with pytest.raises(module.V17ReportError, match="missing required field 'step_index'"):
        module.normalize_trace(raw, expected_seed=0, result_by_env={0: result})


def test_group_is_required_and_nonempty():
    module = _reporter()
    with pytest.raises(SystemExit):
        module.parse_args([])

def test_reward_episode_sum_unit_legacy_absent_is_accepted_and_wrong_is_rejected():
    module = _reporter()
    raw = _result(0, 0)
    raw.pop("reward_episode_sums_unit")
    normalized = module.normalize_result(raw, expected_seed=0)
    assert normalized.reward_episode_sums["complete"] == 4.0
    raw = _result(0, 0)
    raw["reward_episode_sums_unit"] = "/20s"
    with pytest.raises(module.V17ReportError, match="episode-sum"):
        module.normalize_result(raw, expected_seed=0)
