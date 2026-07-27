"""CPU/no-simulation tests for base_v18 P2 and M41 eval selectors."""

from __future__ import annotations

import ast
import math
from copy import deepcopy
from pathlib import Path

import pytest
import torch
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[3]
TRAINER_SOURCE = ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"
DOOR_ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
BASE_EVAL = ROOT / "gr00t/rl/config/base_eval.yaml"


def _load_helpers():
    tree = ast.parse(TRAINER_SOURCE.read_text(encoding="utf-8"))
    names = {
        "_A2_EVAL_P2_POSTURE_AXES",
        "_A2_EVAL_P2_POSTURE_AXIS_KEY",
        "_A2_M41_RESULT_REQUIRED_FLOAT_FIELDS",
        "_A2_M41_RESULT_REQUIRED_BOOL_FIELDS",
        "_A2_M41_TRACE_REQUIRED_FIELDS",
        "_read_a2_eval_p2_posture_axis",
        "_apply_a2_eval_p2_posture_axis",
        "_a2_m41_finite_scalar",
        "_a2_m41_finite_vector",
        "_a2_m41_reward_sums",
        "_validate_a2_m41_result_records",
        "_validate_a2_m41_stage2_trace",
        "_validate_a2_m41_eval_telemetry",
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names for target in node.targets
        ):
            nodes.append(node)
    namespace = {"math": math, "torch": torch}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(TRAINER_SOURCE), "exec"), namespace)
    return namespace


def _terminal(env_id: int, length: int = 2):
    return {
        "env_id": env_id,
        "stage_buf": 5,
        "time_in_stage_buf": 1,
        "episode_length_buf": length,
        "control_dt": 0.02,
        "terminal_reasons": "complete",
        "door_hinge_drive_max_force": 4.0,
        "door_handle_drive_max_force": 2.0,
        "door_handle_height": 0.9,
        "door_weight": 120.0,
        "crossing_while_holding": True,
        "hinge_at_crossing": 1.1,
        "hinge_at_release": 1.4,
        "root_x_at_release": 0.4,
        "post_release_body_contact": False,
        "post_release_body_force_max": 0.0,
        "stage0_to1_staging_standoff": 0.6,
        "stage0_actual_root_height": 0.57,
        "stage1_actual_root_height": 0.61,
        "root_pos_rel": [0.1, 0.0, 0.6],
        "reward_episode_sums": {"a2_hinge": 2.0, "a2_hold": 1.0},
    }


def _trace(env_id: int, step: int, length: int, stage: int, terminal: str):
    return {
        "env_id": env_id,
        "episode_index": 0,
        "first_episode_active": True,
        "stage_buf": stage,
        "step_index": step,
        "episode_length_buf": length,
        "control_dt": 0.02,
        "target_pos_source_handle": [0.1, 0.2, 0.3],
        "both_contact": True,
        "terminal_reasons": terminal,
        "door_hinge_drive_max_force": 4.0,
        "door_handle_height": 0.9,
        "door_weight": 120.0,
        "door_body_panel_normal_force_per_filter": [0.0] * 13,
        "door_body_panel_normal_force_total": 0.0,
        "door_arm_panel_normal_force_per_filter": [0.0] * 10,
        "door_arm_panel_normal_force_total": 0.0,
        "physical_base_command": [0.0, 0.0, 0.0, 0.4, -0.2],
        "arm_j7_j8_pos": [0.0, 0.0],
        "arm_j7_j8_open_target": [0.0, 0.0],
        "over_force": False,
        "door_hinge_joint_vel": 0.1,
        "root_x_ever_crossed": False,
        "root_pos_rel": [0.1, 0.0, 0.6],
        "reward_episode_sums": {"a2_hinge": 2.0, "a2_hold": 1.0},
    }


def _valid_summary(num_envs=2):
    terminals = [_terminal(env_id) for env_id in range(num_envs)]
    return {
        "episode_terminal_diagnostics": terminals,
        "episode_goal_reached": [True] * num_envs,
        "episode_max_stage_reached": [5] * num_envs,
    }


def _set_event_groups_null(summary, index=0):
    terminal = summary["episode_terminal_diagnostics"][index]
    for field_name in (
        "crossing_while_holding",
        "hinge_at_crossing",
        "hinge_at_release",
        "root_x_at_release",
        "post_release_body_contact",
        "post_release_body_force_max",
    ):
        terminal[field_name] = None


def _valid_trace(num_envs=2):
    rows = []
    for env_id in range(num_envs):
        rows.extend(
            [
                _trace(env_id, 0, 1, 2, "unknown_reset"),
                _trace(env_id, 1, 2, 3, "complete"),
            ]
        )
    return rows


def test_base_eval_defaults_and_canonical_selector_keys():
    config = OmegaConf.load(BASE_EVAL)
    eval_config = config.algo.config.eval
    assert eval_config.a2_eval_p2_posture_axis == "none"
    assert eval_config.a2_eval_m41_strict_telemetry is False

    helpers = _load_helpers()
    parse = helpers["_read_a2_eval_p2_posture_axis"]
    assert parse({}) == "none"
    assert parse({"a2_eval_p2_posture_axis": None}) == "none"
    for value in ("none", "pitch_zero", "roll_zero"):
        assert parse({"a2_eval_p2_posture_axis": value}) == value
    for value in (True, False, 0, 1, "pitch", "none "):
        with pytest.raises(RuntimeError):
            parse({"a2_eval_p2_posture_axis": value})


def test_p2_clamp_changes_only_selected_base_channel_and_keeps_raw():
    helpers = _load_helpers()
    apply = helpers["_apply_a2_eval_p2_posture_axis"]
    layout = {"dim": 8, "base_start": 0, "base_end": 5}
    raw = torch.tensor([[1.0, 2.0, 3.0, 0.4, -0.2, 5.0, 6.0, 7.0]])
    raw_copy = raw.clone()
    pitch = apply(raw, layout, "pitch_zero")
    roll = apply(raw, layout, "roll_zero")
    historical = apply(raw, layout, "none")
    torch.testing.assert_close(raw, raw_copy)
    torch.testing.assert_close(historical, raw)
    assert pitch[0, 3].item() == 0.0
    assert pitch[0, 4].item() == raw[0, 4].item()
    assert roll[0, 4].item() == 0.0
    assert roll[0, 3].item() == raw[0, 3].item()
    for index in (0, 1, 2, 5, 6, 7):
        assert pitch[0, index].item() == raw[0, index].item()
        assert roll[0, index].item() == raw[0, index].item()


def test_m41_complete_rows_and_contiguous_trace_pass():
    helpers = _load_helpers()
    validate = helpers["_validate_a2_m41_eval_telemetry"]
    validate(_valid_summary(), _valid_trace(), 2)


@pytest.mark.parametrize(
    "mutation",
    ("missing", "partial_null", "nonfinite", "ambiguous", "negative_time"),
)
def test_m41_terminal_failures_are_fail_fast(mutation):
    helpers = _load_helpers()
    validate = helpers["_validate_a2_m41_eval_telemetry"]
    summary = _valid_summary()
    if mutation == "missing":
        del summary["episode_terminal_diagnostics"][0]["hinge_at_release"]
    elif mutation == "partial_null":
        summary["episode_terminal_diagnostics"][0]["hinge_at_release"] = None
    elif mutation == "nonfinite":
        summary["episode_terminal_diagnostics"][0]["hinge_at_release"] = float("nan")
    elif mutation == "ambiguous":
        summary["episode_terminal_diagnostics"][1]["env_id"] = 0
    else:
        summary["episode_terminal_diagnostics"][0]["time_in_stage_buf"] = -1
    with pytest.raises(RuntimeError):
        validate(summary, _valid_trace(), 2)


def test_m41_goal_all_null_event_groups_fail(tmp_path):
    helpers = _load_helpers()
    validate = helpers["_validate_a2_m41_eval_telemetry"]
    summary = _valid_summary()
    _set_event_groups_null(summary)
    with pytest.raises(RuntimeError, match="goal_reached"):
        validate(summary, _valid_trace(), 2)


def test_m41_goal_with_crossing_and_no_release_event_passes():
    helpers = _load_helpers()
    validate = helpers["_validate_a2_m41_eval_telemetry"]
    summary = _valid_summary()
    terminal = summary["episode_terminal_diagnostics"][0]
    for field_name in (
        "hinge_at_release",
        "root_x_at_release",
        "post_release_body_contact",
        "post_release_body_force_max",
    ):
        terminal[field_name] = None
    validate(summary, _valid_trace(), 2)


def test_m41_non_goal_all_null_event_groups_pass(tmp_path):
    helpers = _load_helpers()
    validate = helpers["_validate_a2_m41_eval_telemetry"]
    summary = _valid_summary()
    summary["episode_goal_reached"][0] = False
    _set_event_groups_null(summary)
    validate(summary, _valid_trace(), 2)


def test_m41_terminal_time_routes_from_elapsed_stage_buffer():
    tree = ast.parse(DOOR_ENV_SOURCE.read_text(encoding="utf-8"))
    terminal_diagnostics = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_get_a2_terminal_diagnostics"
    )
    source = ast.unparse(terminal_diagnostics)
    assert "actual_time_in_stage_buf = self.actual_time_in_stage_buf" in source
    assert (
        "selected_time_in_stage_buf = "
        "actual_time_in_stage_buf[env_ids].detach().cpu().tolist()"
    ) in source
    assert "self.time_in_stage_buf[env_ids]" not in source
    assert "'time_in_stage_buf': int(selected_time_in_stage_buf[idx])" in source
    assert "torch.any(actual_time_in_stage_buf < 0)" in source


@pytest.mark.parametrize("mutation", ("missing_stage2", "gap", "null", "missing_row"))
def test_m41_trace_coverage_failures_are_fail_fast(mutation):
    helpers = _load_helpers()
    validate = helpers["_validate_a2_m41_eval_telemetry"]
    summary = _valid_summary()
    trace = _valid_trace()
    if mutation == "missing_stage2":
        trace[0]["stage_buf"] = 3
    elif mutation == "gap":
        trace[1]["step_index"] = 3
    elif mutation == "null":
        trace[1]["target_pos_source_handle"] = None
    else:
        trace = trace[:-2]
    with pytest.raises(RuntimeError):
        validate(summary, trace, 2)


def test_m41_off_selector_is_explicit_bool_and_does_not_validate_legacy_null_rows():
    tree = ast.parse(TRAINER_SOURCE.read_text(encoding="utf-8"))
    parser = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_read_a2_eval_diagnostic_config")
    # Static contract check: strict mode is a bool selector and legacy path has no validator call.
    source = ast.unparse(parser)
    assert "strict_m41_telemetry" in source
    assert "must be bool" in source
    assert "_validate_a2_m41_eval_telemetry" not in source


def test_hydra_base_eval_composes_with_canonical_selector_overrides():
    config_dir = ROOT / "gr00t/rl/config"
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        composed = compose(
            config_name="base_eval",
            overrides=[
                "algo.config.eval.a2_eval_p2_posture_axis=pitch_zero",
                "algo.config.eval.a2_eval_m41_strict_telemetry=true",
            ],
        )
    assert composed.algo.config.eval.a2_eval_p2_posture_axis == "pitch_zero"
    assert composed.algo.config.eval.a2_eval_m41_strict_telemetry is True
