"""Executable M48 endpoint-schema negative and denominator tests."""

from __future__ import annotations

import ast
import importlib.util
import math
import re
from copy import deepcopy
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[3]


def _module():
    path = ROOT / "scriptsFORhuman/v20_R1/a2_piper_v20_R1_endpoint_report.py"
    spec = importlib.util.spec_from_file_location("r1_endpoint_schema_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline_module():
    path = ROOT / "scriptsFORhuman/v20_R1/a2_piper_v20_R1_baseline.py"
    spec = importlib.util.spec_from_file_location("r1_b0_schema_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(index: int = 0) -> dict:
    return {
        "schema": "a2_piper_v20_R1_endpoint_record_v1",
        "provenance": {"plan_id": "base_v20_R1_policy_behavior_v1", "checkpoint_sha256": "c" * 64, "config_sha256": "d" * 64, "git_commit": "a" * 40, "seed": 0, "env_id": index},
        "topology": {"name": "canonical16", "episode_count": 16, "first_episode_only": True, "single_process": True},
        "task": {"goal": True, "complete": True, "crossing_while_holding": True, "max_stage": 5},
        "safety": {"upper_dof_overspeed": False, "body_contact_force_max_n": 0.0},
        "send": {"send_ready": True, "hinge_at_first_crossing": 0.9, "pre_send_forward_displacement": 0.1, "pre_send_lateral_displacement": 0.1, "pre_send_planar_displacement": 0.1, "pre_send_yaw_change": 0.1},
        "task_space": {"valid_reference": True, "arm_tangent_share": 0.6, "arc_position_error_m": 0.01, "arc_orientation_error_rad": 0.1, "along_handle_slip_m": 0.01},
        "smoothness": {"positive_hinge_velocity": 0.2, "hinge_acceleration": 0.5, "hinge_jerk": 10.0, "arm_action_rate": 1.0, "arm_action_jerk": 2.0},
        "income": {"positive_income_ratio": 0.05},
        "phase": {"stage": 5, "time_in_stage": 2, "curriculum_phase": "hard"},
        "audit": {"crossing_event_valid": True, "release_event_valid": False, "terminal_reason": "goal"},
        "trace": {"step_index": [0, 1, 2], "terminal": True, "terminal_reason": "goal"},
        "binding": {"group": "G1", "config": "base_v20_R1_G1_g2_continuation.yaml", "config_sha256": "d" * 64, "checkpoint_sha256": "c" * 64},
        "factor": {"group": "G1", "config": "base_v20_R1_G1_g2_continuation.yaml", "config_sha256": "d" * 64, "send_curriculum": False, "economics": False, "arm_tie": False},
        "denominators": {"send": 1, "task_space": 1, "smoothness": 1, "income": 1},
        "release": {"valid": False, "hinge_at_release": None, "root_x_at_release": None, "post_release_body_contact": None, "post_release_body_force_max_n": None},
    }


def test_complete_schema_aggregates_exact_canonical16():
    module = _module()
    result = module.aggregate_records([_record(index) for index in range(16)])
    assert result["record_count"] == 16
    assert result["goal_count"] == 16


@pytest.mark.parametrize("group", ["provenance", "topology", "task", "safety", "send", "task_space", "smoothness", "income", "phase", "audit", "trace", "binding", "factor", "denominators", "release"])
def test_missing_required_group_fails_fast(group):
    module = _module()
    record = _record()
    del record[group]
    with pytest.raises(module.R1Error):
        module._validate_record(record, 0)


def test_malformed_typed_na_fails_fast():
    module = _module()
    record = _record()
    record["task_space"]["arc_position_error_m"] = {"status": "N/A", "reason": "", "denominator": 0}
    with pytest.raises(module.R1Error):
        module._validate_record(record, 0)


def test_noncontiguous_trace_fails_fast():
    module = _module()
    record = _record()
    record["trace"]["step_index"] = [0, 2, 3]
    with pytest.raises(module.R1Error):
        module._validate_record(record, 0)


def test_goal_without_crossing_fails_fast():
    module = _module()
    record = _record()
    record["task"]["crossing_while_holding"] = False
    with pytest.raises(module.R1Error):
        module._validate_record(record, 0)


def test_release_mixed_null_and_value_fails_fast():
    module = _module()
    record = _record()
    record["release"]["hinge_at_release"] = 1.5
    with pytest.raises(module.R1Error):
        module._validate_record(record, 0)


def test_b0_companion_accepts_authoritative_nested_schema_and_bindings():
    module = _baseline_module()
    payload = module.build_b0_companion(repo_root=ROOT)
    assert payload["schema"] == "a2_piper_base_v20_R1_B0_reference_v1"
    assert len(payload["source_files"]) == 6
    assert set(payload["source_files"]) == {relative for _, relative, _ in module.B0_SOURCE_BINDINGS}
    assert "plan_id" not in payload
    assert "frozen_values" not in payload
    assert payload["pooled48_frozen"]["episodes"] == 48
    assert payload["taskspace_trace_diagnostic"]["classification"] == "DIAGNOSTIC_ONLY_TWO_RENDER_EPISODES"


def test_b0_companion_wrong_schema_fails_fast():
    module = _baseline_module()
    payload = deepcopy(module.build_b0_companion(repo_root=ROOT))
    payload["schema"] = "wrong_schema"
    with pytest.raises(module.R1Error):
        module._validate_companion(payload)


def test_b0_companion_missing_nested_metric_group_fails_fast():
    module = _baseline_module()
    payload = deepcopy(module.build_b0_companion(repo_root=ROOT))
    del payload["pooled48_frozen"]["hinge_at_first_root_crossing_rad"]
    with pytest.raises(module.R1Error):
        module._validate_companion(payload)


def test_b0_companion_source_digest_mismatch_fails_fast():
    module = _baseline_module()
    payload = deepcopy(module.build_b0_companion(repo_root=ROOT))
    relative = next(iter(payload["source_files"]))
    payload["source_files"][relative] = "0" * 64
    with pytest.raises(module.R1Error):
        module._validate_companion(payload)


def test_live_terminal_normalization_emits_strict_endpoint_record():
    source = (ROOT / "gr00t/rl/envs/door/door_open_a2_base.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    builder = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "a2_v20_r1_build_endpoint_record"
    )
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "DoorPregrasp"
    )
    method_names = {
        "get_a2_v20_R1_endpoint_records",
        "_a2_v20_r1_normalize_terminal_diagnostic",
    }
    methods = [
        node
        for node in door_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in method_names
    ]
    harness_node = ast.ClassDef(
        name="Harness",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    namespace = {
        "Any": object,
        "Mapping": __import__("collections.abc", fromlist=["Mapping"]).Mapping,
        "math": math,
        "re": re,
        "torch": torch,
        "a2_v20_r1_build_endpoint_record": None,
        "A2_V20_R1_ENDPOINT_SCHEMA": "a2_piper_v20_R1_endpoint_record_v1",
        "A2_V20_R1_PLAN_ID": "base_v20_R1_policy_behavior_v1",
    }
    exec(
        compile(ast.Module(body=[builder], type_ignores=[]), "<door-builder>", "exec"),
        namespace,
    )
    namespace["a2_v20_r1_build_endpoint_record"] = namespace[
        "a2_v20_r1_build_endpoint_record"
    ]
    harness_module = ast.fix_missing_locations(
        ast.Module(body=[harness_node], type_ignores=[])
    )
    exec(compile(harness_module, "<door-exporter>", "exec"), namespace)
    Harness = namespace["Harness"]

    diagnostic = {
        "env_id": 0,
        "stage_buf": 5,
        "time_in_stage_buf": 2,
        "episode_length_buf": 11,
        "terminal_reasons": "complete",
        "crossing_while_holding": True,
        "hinge_at_crossing": 0.9,
        "hinge_at_release": None,
        "root_x_at_release": None,
        "post_release_body_contact": None,
        "post_release_body_force_max": None,
        "v20_send_ready": True,
        "v20_hinge_at_first_root_crossing": 0.9,
        "v20_r1_max_pre_send_reconfiguration": [0.1, 0.02, 0.11, 0.03],
        "v20_carry_valid": True,
        "v20_arm_tangent_share": 0.6,
        "v20_handle_arc_position_error_m": 0.01,
        "v20_handle_arc_orientation_error_rad": 0.1,
        "v20_along_handle_slip_m": 0.01,
        "door_body_panel_normal_force_total": 0.0,
        "door_arm_panel_normal_force_total": 0.0,
        "doorframe_contact_force": 0.0,
    }

    class LiveHarness(Harness):
        def __init__(self, row):
            self._use_a2_base = True
            self.num_envs = 1
            self.device = torch.device("cpu")
            self.current_completed_task_buf = torch.tensor([True])
            self.current_max_stage_buf = torch.tensor([5], dtype=torch.long)
            self._a2_v20_r1_curriculum_phase = "hard"
            self._row = row

        def _normalize_render_env_ids(self, env_ids):
            if env_ids is None:
                return torch.tensor([0], dtype=torch.long)
            return env_ids

        def _get_a2_terminal_diagnostics(self, env_ids):
            return [dict(self._row)]

        def _get_a2_v20_r1_send_curriculum_enabled(self):
            return True

        def _get_a2_v20_traversal_economics_enabled(self):
            return True

        def _get_a2_v20_arm_tie_enabled(self):
            return True

    harness = LiveHarness(diagnostic)
    records = harness.get_a2_v20_R1_endpoint_records(
        provenance={
            "seed": 0,
            "checkpoint_sha256": "c" * 64,
            "config_sha256": "f" * 64,
            "git_commit": "a" * 40,
        },
        factor={
            "group": "G1",
            "config": "base_v20_R1_G1_g2_continuation.yaml",
            "config_sha256": "d" * 64,
        },
        topology={
            "name": "canonical16",
            "episode_count": 16,
            "first_episode_only": True,
            "single_process": True,
        },
    )
    assert len(records) == 1
    assert records[0]["schema"] == "a2_piper_v20_R1_endpoint_record_v1"
    assert records[0]["task"]["goal"] is True
    assert records[0]["task_space"]["valid_reference"] is True

    malformed = dict(diagnostic)
    malformed["v20_carry_valid"] = "true"
    with pytest.raises(RuntimeError):
        LiveHarness(malformed).get_a2_v20_R1_endpoint_records(
            provenance={
                "seed": 0,
                "checkpoint_sha256": "c" * 64,
                "config_sha256": "f" * 64,
                "git_commit": "a" * 40,
            },
            factor={
                "group": "G1",
                "config": "base_v20_R1_G1_g2_continuation.yaml",
                "config_sha256": "d" * 64,
            },
            topology={
                "name": "canonical16",
                "episode_count": 16,
                "first_episode_only": True,
                "single_process": True,
            },
        )
