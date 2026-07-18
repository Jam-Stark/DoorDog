"""Pure tests for the v14 M20 explicit-seed bucket report."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scriptsFORhuman/a2_piper_v14_bucket_report.py"
SPEC = importlib.util.spec_from_file_location("a2_piper_v14_bucket_report", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _record(seed: int, env_id: int) -> dict:
    height = (0.80, 0.90, 1.00)[env_id % 3]
    return {
        "seed": seed,
        "env_id": env_id,
        "metadata": {
            "door_hinge_drive_max_force": 2.5 + 4.5 * env_id / 15.0,
            "door_handle_drive_max_force": 1.0 + 2.0 * env_id / 15.0,
            "door_handle_height": height,
        },
        "outcome": {
            "goal_reached": env_id % 2 == 0,
            "max_stage": env_id % 6,
            "final_stage": env_id % 6,
        },
        "telemetry": {
            "crossing_while_holding": None if env_id == 0 else env_id % 2 == 0,
            "hinge_at_crossing": None if env_id == 0 else 0.7 + 0.01 * env_id,
            "stage0_to1_staging_standoff": None if env_id == 0 else 0.4 + 0.01 * env_id,
            "stage0_actual_root_height": None if env_id == 0 else 0.55,
            "stage1_actual_root_height": None if env_id == 0 else 0.65,
        },
    }


def _records() -> list[object]:
    return [
        MODULE.normalize_record(_record(seed, env_id), expected_seed=seed)
        for seed in (0, 1, 2)
        for env_id in range(16)
    ]


def test_schema_validation_and_null_telemetry_semantics():
    records = _records()
    assert len(records) == 48
    assert records[0].crossing_while_holding is None
    assert records[0].hinge_at_crossing is None
    assert records[1].stage_for_attainment == 1
    with pytest.raises(ValueError, match="missing required telemetry"):
        bad = _record(0, 0)
        del bad["telemetry"]["hinge_at_crossing"]
        MODULE.normalize_record(bad, expected_seed=0)
    with pytest.raises(ValueError, match="must be finite"):
        bad = _record(0, 0)
        bad["metadata"]["door_handle_height"] = float("nan")
        MODULE.normalize_record(bad, expected_seed=0)
    for field_name, invalid_value in (
        ("door_hinge_drive_max_force", 7.01),
        ("door_handle_drive_max_force", 3.01),
        ("door_handle_height", 1.050001),
    ):
        with pytest.raises(ValueError, match="v14"):
            bad = _record(0, 0)
            bad["metadata"][field_name] = invalid_value
            MODULE.normalize_record(bad, expected_seed=0)
    upper_bound = _record(0, 0)
    upper_bound["metadata"]["door_handle_height"] = 1.05
    normalized_upper = MODULE.normalize_record(upper_bound, expected_seed=0)
    assert normalized_upper.door_handle_height == 1.05
    assert MODULE.handle_height_bucket(1.05) == "[1.00,1.05]"
    with pytest.raises(ValueError, match="M18-backed"):
        MODULE.handle_height_bucket(1.050001)

    with pytest.raises(ValueError, match=r"range \[0,5\]"):
        bad = _record(0, 0)
        bad["outcome"]["max_stage"] = 6
        MODULE.normalize_record(bad, expected_seed=0)
    with pytest.raises(ValueError, match="cannot exceed"):
        bad = _record(0, 0)
        bad["outcome"]["max_stage"] = 3
        bad["outcome"]["final_stage"] = 4
        MODULE.normalize_record(bad, expected_seed=0)


def test_report_has_seed_roles_and_three_deterministic_bucket_dimensions():
    report = MODULE.build_bucket_report(_records())
    assert report["record_count"] == 48
    assert report["seed_roles"] == {
        "seed0": "canonical",
        "seed1": "supplementary",
        "seed2": "supplementary",
    }
    assert [group["n"] for group in report["by_hinge_force_tertile"].values()] == [16, 16, 16]
    assert [group["n"] for group in report["by_handle_force_bucket"].values()] == [24, 24]
    assert set(report["by_handle_height_bucket"]) == set(MODULE.HANDLE_HEIGHT_BUCKET_LABELS)
    assert sum(group["n"] for group in report["by_handle_height_bucket"].values()) == 48
    telemetry = report["all_records_summary"]["telemetry"]
    assert telemetry["hinge_at_crossing"]["null_count"] == 3
    assert telemetry["hinge_at_crossing"]["n"] == 45
    assert telemetry["crossing_while_holding"]["null_count"] == 3


def test_explicit_three_input_validation_requires_exact_16_each(tmp_path):
    paths = {}
    for seed in (0, 1, 2):
        path = tmp_path / f"seed{seed}.json"
        path.write_text(json.dumps([_record(seed, env_id) for env_id in range(16)]), encoding="utf-8")
        paths[seed] = path
    records = MODULE.validate_seed_inputs(paths)
    assert len(records) == 48

    shifted_records = [_record(1, source_id) for source_id in range(16)]
    for shifted_env_id, record in enumerate(shifted_records, 1):
        record["env_id"] = shifted_env_id
    shifted_ids = tmp_path / "shifted_seed1.json"
    shifted_ids.write_text(json.dumps(shifted_records), encoding="utf-8")
    paths[1] = shifted_ids
    with pytest.raises(ValueError, match="exactly env_id=0..15"):
        MODULE.validate_seed_inputs(paths)

    wrong_seed = tmp_path / "wrong_seed.json"
    wrong_seed.write_text(json.dumps([_record(2, env_id) for env_id in range(16)]), encoding="utf-8")
    paths[1] = wrong_seed
    with pytest.raises(ValueError, match="assigned to seed1"):
        MODULE.validate_seed_inputs(paths)

    paths[1] = tmp_path / "missing_seed1.json"
    with pytest.raises(FileNotFoundError, match="Explicit result input"):
        MODULE.validate_seed_inputs(paths)


def test_csv_input_coerces_flat_schema_and_nulls(tmp_path):
    fields = [
        "seed",
        "env_id",
        "door_hinge_drive_max_force",
        "door_handle_drive_max_force",
        "door_handle_height",
        "goal_reached",
        "max_stage",
        "final_stage",
        "crossing_while_holding",
        "hinge_at_crossing",
        "stage0_to1_staging_standoff",
        "stage0_actual_root_height",
        "stage1_actual_root_height",
    ]
    path = tmp_path / "seed0.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for env_id in range(16):
            raw = _record(0, env_id)
            writer.writerow(
                {
                    "seed": raw["seed"],
                    "env_id": raw["env_id"],
                    **raw["metadata"],
                    "goal_reached": str(raw["outcome"]["goal_reached"]).lower(),
                    "max_stage": raw["outcome"]["max_stage"],
                    "final_stage": raw["outcome"]["final_stage"],
                    "crossing_while_holding": (
                        "" if raw["telemetry"]["crossing_while_holding"] is None
                        else str(raw["telemetry"]["crossing_while_holding"]).lower()
                    ),
                    "hinge_at_crossing": raw["telemetry"]["hinge_at_crossing"],
                    "stage0_to1_staging_standoff": raw["telemetry"]["stage0_to1_staging_standoff"],
                    "stage0_actual_root_height": raw["telemetry"]["stage0_actual_root_height"],
                    "stage1_actual_root_height": raw["telemetry"]["stage1_actual_root_height"],
                }
            )
    records = MODULE.load_result_input(path, expected_seed=0)
    assert len(records) == 16
    assert records[0].crossing_while_holding is None
    assert records[1].goal_reached is False
    assert records[1].door_handle_height == 0.90


def test_report_outputs_are_durable_json_markdown_and_csv(tmp_path):
    report = MODULE.build_bucket_report(_records())
    paths = MODULE.write_report_outputs(
        tmp_path,
        report,
        input_files={seed: Path(f"seed{seed}.json") for seed in (0, 1, 2)},
    )
    assert all(path.is_file() for path in paths)
    payload = json.loads(paths[1].read_text(encoding="utf-8"))
    assert payload["explicit_input_files"]["seed0"] == "seed0.json"
    markdown = paths[2].read_text(encoding="utf-8")
    assert "canonical" in markdown
    assert "N/A" in markdown
