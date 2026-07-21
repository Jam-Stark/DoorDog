"""Direct strict v16 M33 bucket reporter tests using synthetic 48-record inputs."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
REPORT_SOURCE = ROOT / "scriptsFORhuman/v16/a2_piper_v16_bucket_report.py"


def _reporter():
    spec = importlib.util.spec_from_file_location("a2_piper_v16_bucket_report_test", REPORT_SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _result(seed: int, env_id: int) -> dict:
    low = env_id < 8
    release_valid = env_id != 14
    crossing_valid = env_id != 15
    return {
        "seed": seed, "env_id": env_id,
        "door_hinge_drive_max_force": 4.0, "door_handle_drive_max_force": 2.0,
        "door_handle_height": 0.80 if low else 1.0,
        "door_weight": 90.0 if env_id < 5 else (120.0 if env_id < 10 else 140.0),
        "goal_reached": True, "max_stage": 5, "final_stage": 5,
        "stage0_to1_staging_standoff": 0.6,
        "crossing_while_holding": True if crossing_valid else None,
        "hinge_at_crossing": 1.1 if crossing_valid else None,
        "hinge_at_release": 1.5 if release_valid else None,
        "root_x_at_release": 0.4 if release_valid else None,
        "post_release_body_contact": bool(env_id % 2) if release_valid else None,
        "post_release_body_force_max": float(20 + env_id) if release_valid else None,
    }


def _trace(seed: int, env_id: int, stage: int, *, crossed: bool) -> dict:
    low = env_id < 8
    body = [0.0] * 13; body[0] = 2.0
    arm = [0.0] * 10; arm[0] = 1.0
    return {
        "seed": seed, "env_id": env_id, "first_episode_active": True, "episode_index": 0,
        "stage_buf": stage, "door_hinge_drive_max_force": 4.0,
        "door_handle_height": 0.80 if low else 1.0,
        "door_weight": 90.0 if env_id < 5 else (120.0 if env_id < 10 else 140.0),
        "door_body_panel_normal_force_per_filter": body, "door_body_panel_normal_force_total": 2.0,
        "door_arm_panel_normal_force_per_filter": arm, "door_arm_panel_normal_force_total": 1.0,
        "physical_base_command": [0.0, 0.0, 0.0, 0.1 if low else 0.3, 0.0 if low else 0.4],
        "arm_j7_j8_pos": [0.0, 0.0], "arm_j7_j8_open_target": [0.035, -0.035],
        "both_contact": stage == 2 or env_id % 2 == 0, "over_force": stage == 3 and env_id % 3 == 0,
        "door_hinge_joint_vel": 0.2 if stage == 3 else 0.8, "root_x_ever_crossed": crossed,
    }


def _inputs(tmp_path: Path):
    paths = {}
    for seed in (0, 1, 2):
        result_path = tmp_path / f"seed{seed}_result.json"
        trace_path = tmp_path / f"seed{seed}_trace.json"
        result_path.write_text(json.dumps([_result(seed, env_id) for env_id in range(16)]), encoding="utf-8")
        trace_path.write_text(json.dumps([row for env_id in range(16) for row in (_trace(seed, env_id, 2, crossed=False), _trace(seed, env_id, 3, crossed=False), _trace(seed, env_id, 4, crossed=True))]), encoding="utf-8")
        paths[seed] = (result_path, trace_path)
    return paths


def test_strict_48_record_report_emits_asserted_m33_values(tmp_path):
    module = _reporter(); paths = _inputs(tmp_path); result_sets = {}; trace_sets = {}
    for seed, (result_path, trace_path) in paths.items():
        result_sets[seed] = module.load_result(result_path, expected_seed=seed)
        trace_sets[seed] = module.load_trace(trace_path, expected_seed=seed, result_records=result_sets[seed])
    report = module.build_report(result_sets, trace_sets); m33 = report["m33"]
    assert report["schema"] == "a2_piper_v16_m33_bucket_report_v2" and report["record_count"] == 48
    assert m33["goal"]["pooled"]["numerator"] == 48 and m33["goal"]["canonical"]["numerator"] == 16
    assert m33["low_height_stage2"]["pitch_usage"]["numerator"] == 0
    assert m33["high_height_stage2"]["pitch_usage"]["numerator"] == 24 and m33["high_height_stage2"]["roll_usage"]["numerator"] == 24
    assert m33["high_height_stage2"]["goal"]["numerator"] == 24 and m33["hinge_at_release"]["n"] == 45
    assert m33["post_release_body_contact"]["rate"]["denominator"] == 45
    assert m33["pre_crossing_stage3_stage4"]["bilateral_rate"]["denominator"] == 48
    assert m33["pre_crossing_stage3_stage4"]["coasting_rate"]["numerator"] == 24
    assert m33["pre_crossing_stage3_stage4"]["coasting_velocity_threshold"] == 0.1
    assert m33["heavy_mass_goal"]["numerator"] == 18
    assert m33["crossing_while_holding"]["pooled"]["numerator"] == 45
    assert m33["crossing_while_holding"]["pooled"]["denominator"] == 48
    assert m33["crossing_while_holding"]["canonical"]["numerator"] == 15
    assert m33["crossing_while_holding"]["canonical"]["denominator"] == 16


def test_pitch_roll_usage_uses_strict_signed_boundary():
    module = _reporter()
    usage = module._usage_rate([0.10, 0.15, -0.15, -0.10])
    assert module.PITCH_ROLL_USAGE_THRESHOLD == 0.1
    assert usage == {"numerator": 2, "denominator": 4, "rate": 0.5}


def test_result_and_trace_missing_camelcase_and_nonfinite_fields_fail_fast(tmp_path):
    module = _reporter(); raw = _result(0, 0)
    missing = dict(raw); missing.pop("crossing_while_holding")
    with pytest.raises(module.V16ReportError, match="missing"):
        module.normalize_result(missing, expected_seed=0)
    camel = dict(raw); camel["crossingWhileHolding"] = camel.pop("crossing_while_holding")
    with pytest.raises(module.V16ReportError, match="missing"):
        module.normalize_result(camel, expected_seed=0)
    nonfinite = dict(raw); nonfinite["hinge_at_release"] = float("nan")
    with pytest.raises(module.V16ReportError, match="finite"):
        module.normalize_result(nonfinite, expected_seed=0)
    partial_crossing = dict(raw); partial_crossing["hinge_at_crossing"] = None
    with pytest.raises(module.V16ReportError, match="crossing_while_holding.*both null"):
        module.normalize_result(partial_crossing, expected_seed=0)
    partial_release = dict(raw); partial_release["post_release_body_force_max"] = None
    with pytest.raises(module.V16ReportError, match="hinge_at_release.*all null"):
        module.normalize_result(partial_release, expected_seed=0)
    result = module.normalize_result(raw, expected_seed=0); trace = _trace(0, 0, 3, crossed=False)
    missing_trace = dict(trace); missing_trace.pop("door_hinge_joint_vel")
    with pytest.raises(module.V16ReportError, match="missing"):
        module.normalize_trace(missing_trace, expected_seed=0, result_by_env={0: result})
    camel_trace = dict(trace); camel_trace["doorHingeJointVel"] = camel_trace.pop("door_hinge_joint_vel")
    with pytest.raises(module.V16ReportError, match="missing"):
        module.normalize_trace(camel_trace, expected_seed=0, result_by_env={0: result})
    bad_trace = dict(trace); bad_trace["door_hinge_joint_vel"] = float("inf")
    with pytest.raises(module.V16ReportError, match="finite"):
        module.normalize_trace(bad_trace, expected_seed=0, result_by_env={0: result})
    assert module.normalize_trace(trace, expected_seed=0, result_by_env={0: result}).door_weight == result.door_weight
    camel_mass = dict(trace); camel_mass["doorWeight"] = camel_mass.pop("door_weight")
    with pytest.raises(module.V16ReportError, match="missing"):
        module.normalize_trace(camel_mass, expected_seed=0, result_by_env={0: result})
    nonfinite_mass = dict(trace); nonfinite_mass["door_weight"] = float("nan")
    with pytest.raises(module.V16ReportError, match="trace door_weight.*finite"):
        module.normalize_trace(nonfinite_mass, expected_seed=0, result_by_env={0: result})
    out_of_range_mass = dict(trace); out_of_range_mass["door_weight"] = 160.1
    with pytest.raises(module.V16ReportError, match=r"trace door_weight.*\[80,160\]"):
        module.normalize_trace(out_of_range_mass, expected_seed=0, result_by_env={0: result})
    mismatched_mass = dict(trace); mismatched_mass["door_weight"] = 100.0
    with pytest.raises(module.V16ReportError, match="exactly match result"):
        module.normalize_trace(mismatched_mass, expected_seed=0, result_by_env={0: result})
