"""Strict no-simulation tests for the v15 bucket report."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scriptsFORhuman.v15.a2_piper_v15_bucket_report import (
    build_report,
    height_bucket,
    hinge_bucket,
    load_result,
    load_trace,
    normalize_result,
    normalize_trace,
    write_outputs,
)


def _result(seed: int, env_id: int, hinge: float = 6.0, height: float = 1.0) -> dict:
    return {
        "seed": seed,
        "env_id": env_id,
        "goal_reached": env_id % 2 == 0,
        "max_stage": 5 if env_id % 2 == 0 else 3,
        "final_stage": 5 if env_id % 2 == 0 else 3,
        "door_hinge_drive_max_force": hinge,
        "door_handle_drive_max_force": 2.0,
        "door_handle_height": height,
        "stage0_to1_staging_standoff": 0.5 + env_id / 100.0,
    }


def _trace(
    seed: int,
    env_id: int,
    stage: int,
    hinge: float = 6.0,
    height: float = 1.0,
    body: float = 2.0,
    arm: float = 3.0,
    pitch: float = 0.2,
    roll: float = -0.2,
    j8_pos: float = -0.03495,
) -> dict:
    return {
        "seed": seed,
        "env_id": env_id,
        "first_episode_active": True,
        "episode_index": 0,
        "stage_buf": stage,
        "door_hinge_drive_max_force": hinge,
        "door_handle_height": height,
        "door_body_panel_normal_force_per_filter": [body / 13.0] * 13,
        "door_body_panel_normal_force_total": body,
        "door_arm_panel_normal_force_per_filter": [arm / 10.0] * 10,
        "door_arm_panel_normal_force_total": arm,
        "physical_base_command": [0.0, 0.0, 0.0, pitch, roll],
        "arm_j7_j8_pos": [0.0, j8_pos],
        "arm_j7_j8_open_target": [0.035, -0.035],
    }


def _write_inputs(tmp_path: Path, *, mutate=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    paths = {}
    for seed in range(3):
        results = []
        traces = []
        for env_id in range(16):
            hinge = (2.5, 5.5, 8.5)[(seed + env_id) % 3]
            height = (0.80, 0.95, 1.10)[(seed + env_id) % 3]
            result = _result(seed, env_id, hinge, height)
            results.append(result)
            traces.extend([_trace(seed, env_id, 2, hinge, height, body=0.0, arm=0.0), _trace(seed, env_id, 3, hinge, height)])
        if mutate is not None:
            mutate(seed, results, traces)
        result_path = tmp_path / f"seed{seed}_result.json"
        trace_path = tmp_path / f"seed{seed}_trace.json"
        result_path.write_text(json.dumps(results), encoding="utf-8")
        trace_path.write_text(json.dumps(traces), encoding="utf-8")
        paths[seed] = (result_path, trace_path)
    return paths


def test_bucket_boundaries_are_fixed_and_inclusive_only_at_upper_final_edge():
    assert hinge_bucket(2.5) == "[2.5,5.5)"
    assert hinge_bucket(5.5) == "[5.5,8.5)"
    assert hinge_bucket(8.5) == "[8.5,12.0]"
    assert hinge_bucket(12.0) == "[8.5,12.0]"
    assert height_bucket(0.80) == "[0.80,0.95)"
    assert height_bucket(0.95) == "[0.95,1.10]"
    assert height_bucket(1.10) == "[0.95,1.10]"
    with pytest.raises(ValueError):
        hinge_bucket(12.0001)
    with pytest.raises(ValueError):
        height_bucket(1.1001)


def test_float32_height_endpoint_is_accepted_and_preserved(tmp_path):
    float32_height = 1.100000023841858

    def use_float32_height(_seed, results, traces):
        for row in results:
            row["door_handle_height"] = float32_height
        for row in traces:
            row["door_handle_height"] = float32_height

    paths = _write_inputs(tmp_path, mutate=use_float32_height)
    result_sets = {
        seed: load_result(paths[seed][0], expected_seed=seed) for seed in range(3)
    }
    assert all(
        record.handle_height == float32_height
        for records in result_sets.values()
        for record in records
    )
    assert height_bucket(float32_height) == "[0.95,1.10]"
    with pytest.raises(ValueError):
        normalize_result(_result(0, 0, height=1.1001), expected_seed=0)

    trace_sets = {
        seed: load_trace(
            paths[seed][1], expected_seed=seed, result_records=result_sets[seed]
        )
        for seed in range(3)
    }
    report = build_report(result_sets, trace_sets)
    assert report["by_bucket"]["[0.95,1.10]"]["n"] == 48


def test_explicit_seed_env_topology_and_trace_filtering(tmp_path):
    paths = _write_inputs(tmp_path)
    result_sets = {}
    trace_sets = {}
    for seed in range(3):
        result_sets[seed] = load_result(paths[seed][0], expected_seed=seed)
        trace_sets[seed] = load_trace(paths[seed][1], expected_seed=seed, result_records=result_sets[seed])
    report = build_report(result_sets, trace_sets)
    assert report["record_count"] == 48
    assert report["by_bucket"]["[2.5,5.5)"]["n"] > 0
    assert report["by_bucket"]["[5.5,8.5)"]["n"] > 0
    assert report["by_bucket"]["[8.5,12.0]"]["n"] > 0
    high = report["by_bucket"]["[0.95,1.10]"]
    assert high["high_handle_pitch_usage"]["rate"] == 1.0
    assert high["j8_open_limit"]["numerator"] == high["j8_open_limit"]["denominator"]


def test_cross_seed_trace_identity_and_metric_stage_scopes(tmp_path):
    def place_every_record_in_the_same_buckets(seed, results, traces):
        for result in results:
            result["door_hinge_drive_max_force"] = 6.0
            result["door_handle_height"] = 1.0
        traces.clear()
        body = float(seed + 1)
        arm = body * 10.0
        pitch = 0.1 * (seed + 1)
        for env_id in range(16):
            traces.extend(
                [
                    _trace(
                        seed,
                        env_id,
                        2,
                        body=0.0,
                        arm=0.0,
                        pitch=pitch,
                        roll=-pitch,
                        j8_pos=0.0,
                    ),
                    _trace(seed, env_id, 3, body=body, arm=arm, pitch=0.4, roll=0.4),
                    _trace(
                        seed,
                        env_id,
                        4,
                        body=body,
                        arm=arm,
                        pitch=0.4,
                        roll=0.4,
                        j8_pos=-0.03490000000000001,
                    ),
                    _trace(
                        seed,
                        env_id,
                        5,
                        body=body,
                        arm=arm,
                        pitch=0.4,
                        roll=0.4,
                        j8_pos=-0.0348,
                    ),
                ]
            )

    paths = _write_inputs(tmp_path, mutate=place_every_record_in_the_same_buckets)
    result_sets = {
        seed: load_result(paths[seed][0], expected_seed=seed) for seed in range(3)
    }
    trace_sets = {
        seed: load_trace(
            paths[seed][1], expected_seed=seed, result_records=result_sets[seed]
        )
        for seed in range(3)
    }
    report = build_report(result_sets, trace_sets)

    for bucket in ("[5.5,8.5)", "[0.95,1.10]"):
        summary = report["by_bucket"][bucket]
        assert summary["n"] == 48
        assert summary["body_contact_usage"] == {
            "numerator": 96,
            "denominator": 144,
            "rate": pytest.approx(2.0 / 3.0),
        }
        assert summary["pooled_panel_force"]["body_numerator"] == pytest.approx(288.0)
        assert summary["pooled_panel_force"]["arm_numerator"] == pytest.approx(2880.0)
        assert summary["j8_open_limit"] == {
            "numerator": 96,
            "denominator": 144,
            "rate": pytest.approx(2.0 / 3.0),
        }

    high = report["by_bucket"]["[0.95,1.10]"]
    assert high["high_handle_physical_pitch"]["n"] == 48
    assert high["high_handle_physical_pitch"]["mean"] == pytest.approx(0.2)
    assert high["high_handle_physical_roll"]["mean"] == pytest.approx(-0.2)
    assert high["high_handle_pitch_usage"] == {
        "numerator": 32,
        "denominator": 48,
        "rate": pytest.approx(2.0 / 3.0),
    }


def test_zero_total_share_is_null_and_body_usage_uses_gt_one_threshold(tmp_path):
    paths = _write_inputs(tmp_path)
    for seed in range(3):
        trace_path = paths[seed][1]
        rows = json.loads(trace_path.read_text())
        for row in rows:
            row["door_body_panel_normal_force_per_filter"] = [0.0] * 13
            row["door_body_panel_normal_force_total"] = 0.0
            row["door_arm_panel_normal_force_per_filter"] = [0.0] * 10
            row["door_arm_panel_normal_force_total"] = 0.0
        trace_path.write_text(json.dumps(rows))
    result_sets = {seed: load_result(paths[seed][0], expected_seed=seed) for seed in range(3)}
    trace_sets = {seed: load_trace(paths[seed][1], expected_seed=seed, result_records=result_sets[seed]) for seed in range(3)}
    report = build_report(result_sets, trace_sets)
    for summary in report["by_bucket"].values():
        assert summary["pooled_panel_force"]["body_share"] is None
        assert summary["pooled_panel_force"]["arm_share"] is None
        assert summary["pooled_panel_force"]["share_valid"] is False
        assert summary["body_contact_usage"]["rate"] == 0.0


def test_missing_nan_negative_force_and_wrong_trace_topology_fail_fast(tmp_path):
    paths = _write_inputs(tmp_path)
    bad_trace = json.loads(paths[0][1].read_text())
    bad_trace[1]["physical_base_command"] = [0.0] * 4
    paths[0][1].write_text(json.dumps(bad_trace))
    results = load_result(paths[0][0], expected_seed=0)
    with pytest.raises(ValueError, match="length 5"):
        load_trace(paths[0][1], expected_seed=0, result_records=results)

    paths = _write_inputs(tmp_path / "negative")
    bad_trace = json.loads(paths[1][1].read_text())
    bad_trace[1]["door_body_panel_normal_force_total"] = -1.0
    paths[1][1].write_text(json.dumps(bad_trace))
    results = load_result(paths[1][0], expected_seed=1)
    with pytest.raises(ValueError, match="non-negative"):
        load_trace(paths[1][1], expected_seed=1, result_records=results)

    paths = _write_inputs(tmp_path / "missing_stage2")
    rows = [row for row in json.loads(paths[2][1].read_text()) if not (row["env_id"] == 0 and row["stage_buf"] == 2)]
    paths[2][1].write_text(json.dumps(rows))
    results = load_result(paths[2][0], expected_seed=2)
    with pytest.raises(ValueError, match="stage2"):
        load_trace(paths[2][1], expected_seed=2, result_records=results)


def test_json_csv_markdown_outputs(tmp_path):
    paths = _write_inputs(tmp_path / "inputs")
    result_sets = {seed: load_result(paths[seed][0], expected_seed=seed) for seed in range(3)}
    trace_sets = {seed: load_trace(paths[seed][1], expected_seed=seed, result_records=result_sets[seed]) for seed in range(3)}
    report = build_report(result_sets, trace_sets)
    outputs = write_outputs(report, tmp_path / "out", {f"seed{seed}-result": paths[seed][0] for seed in range(3)})
    assert all(path.is_file() for path in outputs)
    assert json.loads(outputs[0].read_text())["schema"] == "a2_piper_v15_bucket_report_v1"
    assert "Bucket" in outputs[2].read_text()
    assert "goal_rate" in outputs[1].read_text()


def test_trace_requires_first_episode_fields_and_exact_seed():
    result = _result(0, 0)
    with pytest.raises(ValueError):
        normalize_trace({"env_id": 0, "first_episode_active": True, "episode_index": 0}, expected_seed=1, result_by_env={0: type("R", (), {"hinge_force": 6.0, "handle_height": 1.0})()})
