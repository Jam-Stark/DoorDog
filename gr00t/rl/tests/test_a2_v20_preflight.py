from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scriptsFORhuman/v20/a2_piper_v20_preflight.py"
SPEC = importlib.util.spec_from_file_location("a2_piper_v20_preflight", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _saved_config(source_checkpoint: Path) -> dict:
    return {
        "num_envs": 4096,
        "checkpoint": str(source_checkpoint),
        "checkpoint_load_mode": "policy_only",
        "auto_load_latest": False,
        "env": {
            "config": {
                "a2_stage4_release_hinge_threshold": 1.6,
                "a2_corridor_door_wide_hinge_norm": 1.5,
                "a2_m39_gripper_material_enabled": True,
                "a2_arm_dof_overspeed_soft_margin_enabled": True,
                "a2_arm_dof_overspeed_soft_margin_width": 0.5,
            }
        },
        "robot": {
            "control": {
                "stiffness": {"arm_j7": 1300.0, "arm_j8": 1300.0},
                "damping": {"arm_j7": 32.0, "arm_j8": 32.0},
            },
            "dof_effort_limit_list": [1.0, 45.0, 45.0],
        },
    }


def test_historical_config_records_its_v18_source(tmp_path: Path) -> None:
    run = tmp_path / "base_v19_G2"
    run.mkdir()
    target = run / "model_step_002000.pt"
    target.write_bytes(b"target")
    historical = tmp_path / "base_v18" / "model_step_001500.pt"
    historical.parent.mkdir()
    historical.write_bytes(b"historical")
    config = run / "config.yaml"
    config.write_text(yaml.safe_dump(_saved_config(historical)), encoding="utf-8")

    result = MODULE.validate_saved_config(
        config,
        {"path": str(target)},
        repo_root=tmp_path,
    )

    values = result["validated_values"]
    assert values["historical_source_checkpoint"] == str(historical.resolve())
    assert values["historical_source_checkpoint_sha256"] == MODULE.sha256_file(historical)


def _write_v20_configs(tmp_path: Path, checkpoint: Path, *, frozen: bool) -> list[Path]:
    paths = []
    for index, name in enumerate(MODULE.EXPECTED_V20_CONFIG_NAMES, 1):
        path = tmp_path / name
        path.write_text(
            yaml.safe_dump(
                {
                    "num_envs": 4096,
                    "seed": 1 if index == 7 else 0,
                    "checkpoint": str(checkpoint),
                    "checkpoint_load_mode": "policy_only",
                    "auto_load_latest": False,
                "env": {
                    "config": {
                        "a2_v20_formal_values_frozen": frozen,
                        "a2_v20_formal_launch": False,
                        "a2_v20_calibration_label": "non_formal_calibration_only",
                    }
                },
                }
            ),
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def test_v20_matrix_binds_target_checkpoint_and_freeze_gate(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model_step_002000.pt"
    checkpoint.write_bytes(b"target")
    configs = _write_v20_configs(tmp_path, checkpoint, frozen=False)

    records = MODULE.validate_v20_configs(
        configs,
        checkpoint={"path": str(checkpoint)},
        repo_root=tmp_path,
    )
    assert [record["seed"] for record in records] == [0, 0, 0, 0, 0, 0, 1]
    assert not any(record["formal_values_frozen"] for record in records)
    with pytest.raises(MODULE.PreflightError, match="formal bundle requires"):
        MODULE.validate_v20_configs(
            configs,
            checkpoint={"path": str(checkpoint)},
            repo_root=tmp_path,
            require_formal_frozen=True,
        )

    wrong = tmp_path / "wrong.pt"
    wrong.write_bytes(b"wrong")
    payload = yaml.safe_load(configs[0].read_text(encoding="utf-8"))
    payload["checkpoint"] = str(wrong)
    configs[0].write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(MODULE.PreflightError, match="exact G2 step2000"):
        MODULE.validate_v20_configs(
            configs,
            checkpoint={"path": str(checkpoint)},
            repo_root=tmp_path,
        )


def test_baseline_requires_exact_70_55_15_and_retains_invalid(tmp_path: Path) -> None:
    sources = []
    for group_index in range(1, 8):
        rows = []
        for checkpoint_index in range(1, 11):
            valid = group_index <= 5 or (group_index == 6 and checkpoint_index <= 5)
            row = {
                "group": f"G{group_index}",
                "candidate_id": f"model_step_{checkpoint_index * 250:06d}.pt",
                "strict_status": "STRICT_VALID" if valid else "STRICT_INVALID",
            }
            if valid:
                row["metrics"] = {"goal": {"count": 16, "total": 16}}
            else:
                row["reason"] = "typed invalid evidence"
            rows.append(row)
        path = tmp_path / f"G{group_index}_m22.json"
        path.write_text(json.dumps({"rows": rows}), encoding="utf-8")
        sources.append(path)

    normalized = MODULE.ingest_baseline_sources(sources, repo_root=tmp_path)
    assert len(normalized) == 70
    assert sum(row["strict_status"] == "STRICT_VALID" for row in normalized) == 55
    invalid = [row for row in normalized if row["strict_status"] == "STRICT_INVALID"]
    assert len(invalid) == 15
    assert all(row["metrics"] is None and row["reason"] == "typed invalid evidence" for row in invalid)

    payload = json.loads(sources[0].read_text(encoding="utf-8"))
    payload["rows"].pop()
    sources[0].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MODULE.PreflightError, match="exactly 70 rows"):
        MODULE.ingest_baseline_sources(sources, repo_root=tmp_path)


def test_output_is_atomic_and_refuses_overwrite(tmp_path: Path) -> None:
    metrics = {
        "goal_pooled_count": 48,
        "crossing_while_holding_pooled_count": 48,
        "held_hinge_p50_rad": 1.45,
        "held_hinge_p95_rad": 1.50,
        "opening_slip_p95_cm": 2.0,
        "hinge_at_release_p50_rad": 1.6,
        "overspeed_termination_count": 0,
        "post_release_body_contact_count": 0,
    }
    payload = {
        "provenance": {
            "git": {"head": "abc"},
            "checkpoint": {"path": "/checkpoint", "sha256": "deadbeef"},
            "saved_config": {"path": "/config"},
        },
        "baseline_coverage": {
            "total_rows": 1,
            "strict_valid": 0,
            "strict_invalid": 1,
            "groups": {group: 0 for group in MODULE.EXPECTED_GROUPS},
        },
        "baseline_rows": [
            {
                "group": "G1",
                "candidate_id": "model_step_000250.pt",
                "strict_status": "STRICT_INVALID",
                "reason": "failed",
                "artifact": None,
            }
        ],
        "f1": {"status": "N/A_SCHEMA_UNSUPPORTED", "reason": "test", "row_metrics": []},
        "f2": {"groups": {"G2": {"metrics": metrics}, "G3": {"metrics": metrics}}},
        "input_hashes": [],
    }
    output = tmp_path / "result"
    MODULE.write_preflight_outputs(payload, output)
    assert sorted(path.name for path in output.iterdir()) == [
        "a2_piper_v20_preflight.csv",
        "a2_piper_v20_preflight.json",
        "a2_piper_v20_preflight.md",
        "file_hashes.sha256",
    ]
    with pytest.raises(MODULE.PreflightError, match="refusing to overwrite"):
        MODULE.write_preflight_outputs(payload, output)
