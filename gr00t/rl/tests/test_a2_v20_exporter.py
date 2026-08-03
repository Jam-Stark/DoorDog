"""CPU-only M48 typed v20 exporter tests."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"


def _helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted = {
        "_A2_V20_TRACE_TOPOLOGY_SCHEMA",
        "_A2_V20_TYPED_TELEMETRY_GROUPS",
        "_a2_v20_validate_typed_value",
        "_a2_v20_validate_telemetry_group",
        "validate_a2_v20_telemetry_records",
        "_a2_v20_typed_na",
        "_a2_v20_percentile",
        "_build_a2_v20_strict_telemetry_records",
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in wanted for target in node.targets):
            nodes.append(node)
    namespace = {"math": math, "torch": torch}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def _diagnostic(env_id=0, *, episode_length=13):
    return {
        "env_id": env_id,
        "terminal_reasons": "goal_reached",
        "control_dt": 0.02,
        "episode_length_buf": episode_length,
        "reward_episode_sums": {"stage_reward": 10.0},
        "v20_send_ready": True,
        "v20_first_send_ready_step": 80,
        "v20_pre_send_root_crossing": False,
        "v20_first_pre_send_crossing_step": None,
        "v20_first_root_crossing_step": 1,
        "v20_hinge_at_first_root_crossing": 1.05,
        "v20_root_x_at_first_crossing": 0.01,
        "v20_root_displacement_se2": [0.01, 0.0, 0.0],
        "crossing_while_holding": True,
        "hinge_at_crossing": 1.05,
        "hinge_at_release": None,
        "root_x_at_release": None,
        "post_release_body_contact": None,
        "post_release_body_force_max": None,
    }


def _trace(step, *, terminal="unknown_reset", env_id=0):
    return {
        "env_id": env_id,
        "episode_index": 0,
        "first_episode_active": True,
        "step_index": step,
        "episode_length_buf": step + 1,
        "terminal_reasons": terminal,
        "door_hinge_joint_vel": 0.1 * (step + 1),
        "door_hinge_joint_pos": 1.0 + 0.01 * step,
        "post_delta_post_warp_env_action": [0.0] * 12,
        "root_x_ever_crossed": True,
        "both_contact": True,
        "physical_base_command": [0.0] * 5,
        "over_force": False,
        "v20_carry_valid": True,
        "v20_arm_tangent_share": 0.8,
        "v20_handle_arc_position_error_m": 0.01,
        "v20_handle_arc_orientation_error_rad": 0.1,
        "v20_along_handle_slip_m": 0.004,
        "v20_orthogonal_arc_residual_m": 0.003,
        "v20_arc_tracking_quality": 0.9,
        "stage_buf": 3,
        "target_pos_source_handle": [0.0, 0.01 * step, 0.0],
    }


def test_builder_emits_complete_typed_groups_metrics_and_units():
    fn = _helpers()["_build_a2_v20_strict_telemetry_records"]
    traces = [_trace(10), _trace(11), _trace(12, terminal="goal_reached")]
    topology = {"name": "canonical16", "episode_count": 1, "first_episode_only": True, "single_process": True}
    rows = fn(
        {"episode_terminal_diagnostics": [_diagnostic()], "episode_goal_reached": [True]},
        traces,
        1,
        checkpoint_path="/tmp/model_step_002000.pt",
        checkpoint_sha256="a" * 64,
        config_hash="b" * 64,
        seed=0,
        topology=topology,
    )
    assert len(rows) == 1
    row = rows[0]
    assert set(row["groups"]) == {"send", "crossing", "release", "carry", "smoothness"}
    assert row["groups"]["release"]["valid"] is False
    assert row["groups"]["release"]["hinge_at_release"]["status"] == "N/A"
    assert row["episode_metrics"]["pre_crossing_bilateral"] == 1.0
    assert row["reward_units"] == {"stage_reward": "episode-sum"}
    assert row["trace_topology"]["ordered_unique_contiguous"] is True
    assert row["trace_topology"]["schema"] == "a2_piper_v20_trace_topology_v2"
    assert row["trace_topology"]["mode"] == "stage_window"
    assert row["trace_topology"]["first_episode_identity"] is True
    assert row["trace_topology"]["episode_length_buf_equals_step_index_plus_one"] is True
    assert row["trace_topology"]["captured_span_matches_trace_count"] is True
    assert row["groups"]["carry"]["along_handle_slip_m"] == pytest.approx(0.004)
    assert row["groups"]["carry"]["orthogonal_arc_residual_m"] == pytest.approx(0.003)


def test_builder_rejects_noncontiguous_or_terminal_inconsistent_trace():
    fn = _helpers()["_build_a2_v20_strict_telemetry_records"]
    topology = {"name": "canonical16", "episode_count": 1}
    with pytest.raises(RuntimeError, match="not ordered"):
        fn(
            {"episode_terminal_diagnostics": [_diagnostic()], "episode_goal_reached": [True]},
            [_trace(10), _trace(12, terminal="goal_reached")],
            1,
            checkpoint_path="/tmp/model.pt", checkpoint_sha256="a" * 64,
            config_hash="b", seed=0, topology=topology,
        )
    with pytest.raises(RuntimeError, match="terminal trace is inconsistent"):
        fn(
            {"episode_terminal_diagnostics": [_diagnostic()], "episode_goal_reached": [True]},
            [_trace(10), _trace(11)],
            1,
            checkpoint_path="/tmp/model.pt", checkpoint_sha256="a" * 64,
            config_hash="b", seed=0, topology=topology,
        )


def test_builder_accepts_late_stage_window_and_rejects_contract_mismatches():
    fn = _helpers()["_build_a2_v20_strict_telemetry_records"]
    topology = {"name": "canonical16", "episode_count": 1}
    late = [_trace(97), _trace(98), _trace(99, terminal="goal_reached")]
    rows = fn(
        {"episode_terminal_diagnostics": [_diagnostic(episode_length=100)], "episode_goal_reached": [True]},
        late,
        1,
        checkpoint_path="/tmp/model.pt", checkpoint_sha256="a" * 64,
        config_hash="b", seed=0, topology=topology,
    )
    assert rows[0]["trace_topology"]["first_step_index"] == 97
    assert rows[0]["trace_topology"]["episode_length_first"] == 98

    mismatched_length = [_trace(97), _trace(98), _trace(99, terminal="goal_reached")]
    mismatched_length[1]["episode_length_buf"] += 1
    with pytest.raises(RuntimeError, match=r"must equal step_index \+ 1|ordered and contiguous"):
        fn(
            {"episode_terminal_diagnostics": [_diagnostic(episode_length=100)], "episode_goal_reached": [True]},
            mismatched_length,
            1,
            checkpoint_path="/tmp/model.pt", checkpoint_sha256="a" * 64,
            config_hash="b", seed=0, topology=topology,
        )

    noncontiguous = [_trace(97), _trace(99, terminal="goal_reached")]
    with pytest.raises(RuntimeError, match="not ordered"):
        fn(
            {"episode_terminal_diagnostics": [_diagnostic(episode_length=100)], "episode_goal_reached": [True]},
            noncontiguous,
            1,
            checkpoint_path="/tmp/model.pt", checkpoint_sha256="a" * 64,
            config_hash="b", seed=0, topology=topology,
        )

    terminal_mismatch = [_trace(97), _trace(98), _trace(99, terminal="goal_reached")]
    with pytest.raises(RuntimeError, match="terminal episode_length_buf/span consistency"):
        fn(
            {"episode_terminal_diagnostics": [_diagnostic(episode_length=101)], "episode_goal_reached": [True]},
            terminal_mismatch,
            1,
            checkpoint_path="/tmp/model.pt", checkpoint_sha256="a" * 64,
            config_hash="b", seed=0, topology=topology,
        )

    non_first = [_trace(97), _trace(98), _trace(99, terminal="goal_reached")]
    non_first[0]["episode_index"] = 1
    with pytest.raises(RuntimeError, match="non-first-episode"):
        fn(
            {"episode_terminal_diagnostics": [_diagnostic(episode_length=100)], "episode_goal_reached": [True]},
            non_first,
            1,
            checkpoint_path="/tmp/model.pt", checkpoint_sha256="a" * 64,
            config_hash="b", seed=0, topology=topology,
        )


@pytest.mark.parametrize("bad_episode_index", [False, 0.0])
def test_builder_rejects_non_integer_zero_episode_index(bad_episode_index):
    fn = _helpers()["_build_a2_v20_strict_telemetry_records"]
    topology = {"name": "canonical16", "episode_count": 1}
    trace = [_trace(97), _trace(98), _trace(99, terminal="goal_reached")]
    trace[0]["episode_index"] = bad_episode_index
    with pytest.raises(RuntimeError, match="non-first-episode"):
        fn(
            {"episode_terminal_diagnostics": [_diagnostic(episode_length=100)], "episode_goal_reached": [True]},
            trace,
            1,
            checkpoint_path="/tmp/model.pt", checkpoint_sha256="a" * 64,
            config_hash="b", seed=0, topology=topology,
        )


def test_runtime_exporter_binds_checkpoint_from_composed_config():
    source = SOURCE.read_text(encoding="utf-8")
    assert "self.checkpoint_path = (" in source
    assert "checkpoint_value = self.checkpoint_path" in source
    assert 'getattr(self.args, "checkpoint", None)' not in source
