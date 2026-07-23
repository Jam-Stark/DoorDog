"""Focused synthetic tests for the strict v18 M39 combined reporter."""

from __future__ import annotations

import copy
from hashlib import sha256
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "scriptsFORhuman/v18/a2_piper_v18_combined_probe_report.py"


def _reporter():
    spec = importlib.util.spec_from_file_location("a2_v18_combined_probe_report_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _result(env_id: int) -> dict:
    return {
        "seed": 0,
        "env_id": env_id,
        "goal_reached": True,
        "max_stage": 5,
        "final_stage": 5,
        "door_hinge_drive_max_force": 4.0,
        "door_handle_drive_max_force": 2.0,
        "door_handle_height": 0.8 + 0.02 * (env_id % 8),
        "door_weight": 90.0 + env_id,
        "stage0_to1_staging_standoff": 0.6,
        "crossing_while_holding": True,
        "hinge_at_crossing": 0.8,
        "hinge_at_release": 1.4,
        "root_x_at_release": 0.5,
        "post_release_body_contact": False,
        "post_release_body_force_max": 0.0,
    }


def _trace(env_id: int, step: int, stage: int, *, terminal: str = "unknown_reset") -> dict:
    result = _result(env_id)
    return {
        "env_id": env_id,
        "first_episode_active": True,
        "episode_index": 0,
        "stage_buf": stage,
        "step_index": step,
        "episode_length_buf": step + 1,
        "control_dt": 0.02,
        "door_hinge_drive_max_force": result["door_hinge_drive_max_force"],
        "door_handle_height": result["door_handle_height"],
        "door_weight": result["door_weight"],
        "both_contact": True,
        "over_force": False,
        "root_x_ever_crossed": False,
        "stage3_stage4_gripper_raw_sign_flip": False,
        "terminal_reasons": terminal,
        "root_pos_rel": [0.1 * step, 0.0, 0.5],
        "reward_episode_sums": {"complete": 0.0, "hold": 0.1},
    }


def _summary(values: list[float], digest: str, shape_count: int) -> dict:
    return {
        "shape": [16, shape_count, 3],
        "min": values,
        "max": values,
        "unique": [values],
        "sha256": digest,
    }


def _material() -> dict:
    pre_finger = _summary([0.5, 0.4, 0.0], "1" * 64, 2)
    post_finger = _summary([1.100000023841858, 0.8999999761581421, 0.0], "2" * 64, 2)
    handle = _summary([0.6, 0.5, 0.0], "3" * 64, 2)
    body = lambda name, pre, post, path_root="Robot": {
        "body_path": f"/World/envs/env_0/{path_root}/{name}",
        "shape_count": 2,
        "pre": pre,
        "post": post,
    }
    handle_path = "/World/envs/env_0/Door/door_handle"
    handle_paths = sorted(
        handle_path.replace("/env_0/", f"/env_{env_id}/", 1)
        for env_id in range(16)
    )
    handle_paths_sha256 = sha256("\n".join(handle_paths).encode("utf-8")).hexdigest()
    return {
        "m39_gripper_material": {
            "schema": "a2_m39_gripper_material_v1",
            "selector_enabled": True,
            "event_term": {
                "function": "isaaclab.envs.mdp.events.randomize_rigid_body_material",
                "mode": "startup",
                "asset": "robot",
                "target_bodies": ["arm_body7", "arm_body8"],
                "static_friction_range": [1.1, 1.1],
                "dynamic_friction_range": [0.9, 0.9],
                "restitution_range": [0.0, 0.0],
                "num_buckets": 1,
                "make_consistent": True,
            },
            "finger_bodies": {
                "arm_body7": body("arm_body7", pre_finger, post_finger),
                "arm_body8": body("arm_body8", pre_finger, post_finger),
            },
            "handle": {
                **body("door_handle", handle, handle, "Door"),
                "scope": "exact_target_rigid_body_view_all_envs",
                "target_path": handle_path,
                "target_body": "door_handle",
                "evidence_scope": "exact_target_rigid_body_view_all_envs",
                "view_count": 16,
                "prim_paths_sha256": handle_paths_sha256,
                "unchanged": True,
            },
            "all_envs": True,
        }
    }


def _config() -> dict:
    return {
        "num_envs": 16,
        "algo": {
            "config": {
                "eval": {
                    "a2_eval_m41_strict_telemetry": True,
                }
            }
        },
        "env": {
            "config": {
                "a2_m39_gripper_material_enabled": True,
                "a2_hold_diagnostic_contact_detail_enabled": True,
                "a2_stage2_squeeze_force_max": 30.0,
                "a2_stage2_over_force_threshold": 55.0,
            }
        },
        "robot": {
            "control": {
                "stiffness": {"arm_j7": 1300.0, "arm_j8": 1300.0},
                "damping": {"arm_j7": 32.0, "arm_j8": 32.0},
            },
            "dof_effort_limit_list": [100.0] * 18 + [45.0, 45.0],
        },
    }


def _metadata() -> dict:
    return {
        "diagnostic_trace_enabled": True,
        "m41_strict_telemetry": True,
        "forced_gripper_close_enabled": False,
        "canonical_high_level_action_layout": {"dim": 12, "gripper_index": 11},
        "trace_timing": {"stage_buf": "pre-stage-advance"},
        "first_episode_contract": "first episode only",
    }


def _fixture(tmp_path: Path) -> Path:
    eval_dir = tmp_path / "eval"
    (eval_dir / ".hydra").mkdir(parents=True)
    (eval_dir / "eval_exit_code.txt").write_text("0\n", encoding="utf-8")
    (eval_dir / "a2_v14_per_env_records.json").write_text(
        json.dumps([_result(env_id) for env_id in range(16)]), encoding="utf-8"
    )
    rows = []
    for env_id in range(16):
        rows.extend(
            [
                _trace(env_id, 0, 2),
                _trace(env_id, 1, 3),
                _trace(env_id, 2, 4, terminal="complete"),
            ]
        )
    (eval_dir / "stage2_5_step_trace.json").write_text(json.dumps(rows), encoding="utf-8")
    (eval_dir / "a2_eval_diagnostic_metadata.json").write_text(
        json.dumps(_metadata()), encoding="utf-8"
    )
    (eval_dir / "a2_hold_diagnostic_runtime_metadata.json").write_text(
        json.dumps(_material()), encoding="utf-8"
    )
    (eval_dir / ".hydra/config.yaml").write_text(
        yaml.safe_dump(_config(), sort_keys=False), encoding="utf-8"
    )
    return eval_dir


def test_combined_report_passes_all_four_gates(tmp_path):
    module = _reporter()
    report = module.build_report(_fixture(tmp_path))
    assert report["schema"] == "a2_piper_v18_m39_combined_zero_shot_report_v1"
    assert report["admission"] == {"all_four_gates_pass": True, "status": "PASS"}
    assert report["gates"]["goal"]["numerator"] == 16
    assert report["p1_slip_reduction"]["status"] == "NOT_AN_ADMISSION_GATE"
    assert report["gates"]["pre_crossing_bilateral_contact"]["rate"] == pytest.approx(1.0)
    assert report["gates"]["stage3_stage4_raw_gripper_action_sign_flip"]["count"] == 0


def test_false_effective_strict_telemetry_provenance_fails(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    config = _config()
    config["algo"]["config"]["eval"]["a2_eval_m41_strict_telemetry"] = False
    (eval_dir / ".hydra/config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(module.CombinedProbeReportError, match="strict_telemetry"):
        module.build_report(eval_dir)


def test_false_diagnostic_strict_telemetry_provenance_fails(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    metadata = _metadata()
    metadata["m41_strict_telemetry"] = False
    (eval_dir / "a2_eval_diagnostic_metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    with pytest.raises(module.CombinedProbeReportError, match="strict_telemetry"):
        module.build_report(eval_dir)


@pytest.mark.parametrize(
    "relative_path",
    (
        "a2_v14_per_env_records.json",
        "stage2_5_step_trace.json",
        "a2_eval_diagnostic_metadata.json",
        "a2_hold_diagnostic_runtime_metadata.json",
        ".hydra/config.yaml",
        "eval_exit_code.txt",
    ),
)
def test_missing_required_artifact_fails(tmp_path, relative_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    (eval_dir / relative_path).unlink()
    with pytest.raises(module.CombinedProbeReportError, match="required|does not exist|missing"):
        module.build_report(eval_dir)


@pytest.mark.parametrize("field", ("goal_reached", "both_contact", "over_force", "stage3_stage4_gripper_raw_sign_flip"))
def test_null_gate_evidence_fails(tmp_path, field):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    if field == "goal_reached":
        records = json.loads((eval_dir / "a2_v14_per_env_records.json").read_text())
        records[0][field] = None
        (eval_dir / "a2_v14_per_env_records.json").write_text(json.dumps(records))
    else:
        rows = json.loads((eval_dir / "stage2_5_step_trace.json").read_text())
        rows[0 if field != "stage3_stage4_gripper_raw_sign_flip" else 1][field] = None
        (eval_dir / "stage2_5_step_trace.json").write_text(json.dumps(rows))
    with pytest.raises(module.CombinedProbeReportError, match="bool|missing"):
        module.build_report(eval_dir)


def test_duplicate_env_topology_fails(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    records = json.loads((eval_dir / "a2_v14_per_env_records.json").read_text())
    records[-1]["env_id"] = records[-2]["env_id"]
    (eval_dir / "a2_v14_per_env_records.json").write_text(json.dumps(records))
    with pytest.raises(module.CombinedProbeReportError, match="unique env_id"):
        module.build_report(eval_dir)


def test_trace_continuity_and_terminal_evidence_fail(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    rows = json.loads((eval_dir / "stage2_5_step_trace.json").read_text())
    rows[1]["step_index"] = 4
    (eval_dir / "stage2_5_step_trace.json").write_text(json.dumps(rows))
    with pytest.raises(module.CombinedProbeReportError, match="contiguous"):
        module.build_report(eval_dir)
    eval_dir = _fixture(tmp_path / "terminal")
    rows = json.loads((eval_dir / "stage2_5_step_trace.json").read_text())
    rows[2]["terminal_reasons"] = "unknown_reset"
    (eval_dir / "stage2_5_step_trace.json").write_text(json.dumps(rows))
    with pytest.raises(module.CombinedProbeReportError, match="terminal evidence"):
        module.build_report(eval_dir)


@pytest.mark.parametrize("failure", ("goal", "bilateral", "over_force", "sign_flip"))
def test_each_gate_failure_is_reported(tmp_path, failure):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    if failure == "goal":
        records = json.loads((eval_dir / "a2_v14_per_env_records.json").read_text())
        for record in records[:2]:
            record["goal_reached"] = False
        (eval_dir / "a2_v14_per_env_records.json").write_text(json.dumps(records))
    else:
        rows = json.loads((eval_dir / "stage2_5_step_trace.json").read_text())
        if failure == "bilateral":
            for row in rows:
                if row["stage_buf"] == 3:
                    row["both_contact"] = False
        elif failure == "over_force":
            rows[1]["over_force"] = True
        else:
            rows[1]["stage3_stage4_gripper_raw_sign_flip"] = True
        (eval_dir / "stage2_5_step_trace.json").write_text(json.dumps(rows))
    report = module.build_report(eval_dir)
    assert report["admission"]["all_four_gates_pass"] is False


def test_real_float32_material_readback_passes_and_nearby_value_fails(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    module.load_material_provenance(eval_dir)

    material = json.loads((eval_dir / "a2_hold_diagnostic_runtime_metadata.json").read_text())
    wrong_triplet = [1.1000001430511475, 0.8999999761581421, 0.0]
    for body_name in ("arm_body7", "arm_body8"):
        post = material["m39_gripper_material"]["finger_bodies"][body_name]["post"]
        post["min"] = wrong_triplet
        post["max"] = wrong_triplet
        post["unique"] = [wrong_triplet]
    (eval_dir / "a2_hold_diagnostic_runtime_metadata.json").write_text(json.dumps(material))
    with pytest.raises(module.CombinedProbeReportError, match="exact float32 representation"):
        module.load_material_provenance(eval_dir)


def test_wrong_gain_or_material_provenance_fails(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    config = _config()
    config["robot"]["control"]["stiffness"]["arm_j7"] = 800.0
    (eval_dir / ".hydra/config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(module.CombinedProbeReportError, match="stiffness"):
        module.build_report(eval_dir)
    eval_dir = _fixture(tmp_path / "material")
    material = json.loads((eval_dir / "a2_hold_diagnostic_runtime_metadata.json").read_text())
    material["m39_gripper_material"]["handle"]["unchanged"] = False
    (eval_dir / "a2_hold_diagnostic_runtime_metadata.json").write_text(json.dumps(material))
    with pytest.raises(module.CombinedProbeReportError, match="unchanged"):
        module.build_report(eval_dir)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("scope", "uniform_full_asset_including_target", "scope"),
        ("evidence_scope", "uniform_full_asset_including_target", "evidence_scope"),
        ("target_body", "door_panel", "target_body"),
        ("target_path", "/World/envs/env_0/Door/other", "target_path"),
        ("view_count", 15, "view_count"),
        ("prim_paths_sha256", "A" * 64, "prim_paths_sha256"),
        ("prim_paths_sha256", "4" * 64, "prim_paths_sha256"),
    ),
)
def test_wrong_handle_scope_or_target_provenance_fails(tmp_path, field, value, message):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    material = json.loads((eval_dir / "a2_hold_diagnostic_runtime_metadata.json").read_text())
    material["m39_gripper_material"]["handle"][field] = value
    (eval_dir / "a2_hold_diagnostic_runtime_metadata.json").write_text(json.dumps(material))
    with pytest.raises(module.CombinedProbeReportError, match=message):
        module.build_report(eval_dir)


def test_wrong_handle_summary_shape_fails(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    material = json.loads((eval_dir / "a2_hold_diagnostic_runtime_metadata.json").read_text())
    handle = material["m39_gripper_material"]["handle"]
    handle["pre"]["shape"] = [16, 3, 3]
    handle["post"]["shape"] = [16, 3, 3]
    (eval_dir / "a2_hold_diagnostic_runtime_metadata.json").write_text(json.dumps(material))
    with pytest.raises(module.CombinedProbeReportError, match=r"pre\.shape"):
        module.build_report(eval_dir)


def _set_result_event_groups_null(record):
    for field_name in (
        "crossing_while_holding",
        "hinge_at_crossing",
        "hinge_at_release",
        "root_x_at_release",
        "post_release_body_contact",
        "post_release_body_force_max",
    ):
        record[field_name] = None


def test_partial_null_result_event_group_fails(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    records = json.loads((eval_dir / "a2_v14_per_env_records.json").read_text())
    records[0]["hinge_at_release"] = None
    (eval_dir / "a2_v14_per_env_records.json").write_text(json.dumps(records))
    with pytest.raises(module.CombinedProbeReportError, match="all null or all non-null"):
        module.build_report(eval_dir)


def test_goal_result_all_null_event_groups_fails(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    records = json.loads((eval_dir / "a2_v14_per_env_records.json").read_text())
    _set_result_event_groups_null(records[0])
    (eval_dir / "a2_v14_per_env_records.json").write_text(json.dumps(records))
    with pytest.raises(module.CombinedProbeReportError, match="goal_reached"):
        module.build_report(eval_dir)


def test_non_goal_result_all_null_event_groups_passes(tmp_path):
    module = _reporter()
    eval_dir = _fixture(tmp_path)
    records = json.loads((eval_dir / "a2_v14_per_env_records.json").read_text())
    records[0]["goal_reached"] = False
    _set_result_event_groups_null(records[0])
    (eval_dir / "a2_v14_per_env_records.json").write_text(json.dumps(records))
    report = module.build_report(eval_dir)
    assert report["gates"]["goal"]["numerator"] == 15
    assert report["admission"] == {"all_four_gates_pass": True, "status": "PASS"}
