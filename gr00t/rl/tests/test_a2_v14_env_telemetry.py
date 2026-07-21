"""No-simulation tests for v14 staging and telemetry contracts."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[3]
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
TRAINER_SOURCE = ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"
V14_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v14_main.yaml"


def _env_ast() -> ast.Module:
    return ast.parse(ENV_SOURCE.read_text(encoding="utf-8"))


def _load_staging_helpers():
    names = {
        "a2_validate_stage0_staging_band",
        "_validate_a2_stage0_staging_tensors",
        "a2_stage0_staging_band_mask",
        "a2_stage0_nearest_staging_target",
    }
    nodes = [
        node
        for node in _env_ast().body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {"math": math, "torch": torch}
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(ENV_SOURCE), "exec"),
        namespace,
    )
    return namespace


def _class_method_source(name: str) -> str:
    class_node = next(
        node
        for node in _env_ast().body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    method = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return ast.unparse(method)


def _load_v14_record_builder():
    tree = ast.parse(TRAINER_SOURCE.read_text(encoding="utf-8"))
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_build_a2_v14_eval_records"
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(TRAINER_SOURCE), "exec"),
        namespace,
    )
    return namespace["_build_a2_v14_eval_records"]


def test_stage0_band_validation_mask_and_nearest_target_are_exact():
    helpers = _load_staging_helpers()
    validate = helpers["a2_validate_stage0_staging_band"]
    mask = helpers["a2_stage0_staging_band_mask"]
    nearest = helpers["a2_stage0_nearest_staging_target"]

    assert validate(0.45, 0.85, 0.15) == (0.45, 0.85, 0.15)
    for invalid in (
        (0.0, 0.85, 0.15),
        (0.9, 0.85, 0.15),
        (0.45, 0.85, 0.0),
        (0.45, float("inf"), 0.15),
        (True, 0.85, 0.15),
    ):
        with pytest.raises(ValueError):
            validate(*invalid)

    grasp = torch.tensor(
        [[1.0, 0.0, 0.9], [1.0, 0.0, 1.0], [1.0, 0.0, 1.1]]
    )
    roots = torch.tensor(
        [[0.40, 0.00, 0.55], [0.00, 0.30, 0.65], [0.55, 0.15, 0.75]]
    )
    assert mask(roots, grasp, 0.45, 0.85, 0.15).tolist() == [
        True,
        False,
        False,
    ]
    targets = nearest(roots, grasp, 0.45, 0.85, 0.15)
    torch.testing.assert_close(targets[0], roots[0])
    interior_y = torch.nextafter(torch.tensor(0.15), torch.tensor(0.0))
    torch.testing.assert_close(targets[1], torch.tensor([0.15, interior_y, 0.65]))
    torch.testing.assert_close(targets[2], torch.tensor([0.55, interior_y, 0.75]))
    assert targets[1, 1] < 0.15
    assert targets[2, 1] < 0.15


def test_stage0_transition_reward_and_creep_use_band_not_removed_offset():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    assert "a2_stage0_staging_x_offset" not in source

    transition = _class_method_source("_stage_0_to_1_advance_condition")
    assert "a2_stage0_staging_band_mask" in transition
    assert "_record_a2_stage0_to1_staging_standoff" in transition
    assert "max_deviation < arm_max_deviation" in transition

    walk = _class_method_source("_reward_walk_to_door")
    assert "a2_stage0_nearest_staging_target" in walk
    assert "torch.zeros_like(target_direction)" in walk
    assert "F.normalize" not in walk

    creep = _class_method_source(
        "_reward_penalty_a2_stage1_stage2_base_forward_creep"
    )
    assert "stage0_near_boundary_x = grasp_target[:, 0] - x_min" in creep


def test_v14_metadata_and_event_lifecycle_are_strict_and_reset():
    metadata = _class_method_source("_init_door_metadata")
    assert "hingeDriveMaxForce" in metadata
    assert "handleDriveMaxForce" in metadata
    assert "door_hinge_drive_max_force" in metadata
    assert "door_handle_drive_max_force" in metadata
    assert "torch.isfinite" in metadata
    assert "self.door_open_io[env_id] =" not in metadata

    init_buffers = _class_method_source("_init_buffers")
    reset = _class_method_source("_reset_buffers_callback")
    latch = _class_method_source("_update_a2_stage4_release_and_root_latches")
    transition = _class_method_source("_stage_0_to_1_advance_condition")
    for field_name in (
        "_a2_crossing_event_valid",
        "_a2_crossing_while_holding",
        "_a2_hinge_at_crossing",
        "_a2_stage0_to1_staging_valid",
        "_a2_stage0_to1_staging_standoff",
        "_a2_stage0_root_height_sum",
        "_a2_stage1_root_height_sum",
    ):
        assert field_name in init_buffers
        assert field_name in reset
    assert "first_crossing" in latch
    assert "~root_x_ever_crossed" in latch
    assert "both_contact" in latch
    assert "door_joint_pos[first_crossing, 0]" in latch
    assert "_record_a2_stage0_to1_staging_standoff" in transition


def test_v14_uses_actual_root_height_not_a_nonexistent_command():
    combined = (
        ENV_SOURCE.read_text(encoding="utf-8")
        + TRAINER_SOURCE.read_text(encoding="utf-8")
        + V14_CONFIG.read_text(encoding="utf-8")
    )
    assert "body_height_command" not in combined
    assert "stage0_actual_root_height" in combined
    assert "stage1_actual_root_height" in combined
    precompute = _class_method_source("_pre_compute_observations_callback")
    assert "_update_a2_v14_root_height_telemetry" in precompute


def test_v14_per_env_record_builder_requires_complete_unique_first_episodes():
    build = _load_v14_record_builder()

    def diagnostic(env_id, stage=5):
        return {
            "env_id": env_id,
            "stage_buf": stage,
            "door_hinge_drive_max_force": 4.0,
            "door_handle_drive_max_force": 2.0,
            "door_handle_height": 0.95,
            "door_weight": 120.0,
            "crossing_while_holding": True,
            "hinge_at_crossing": 1.1,
            "hinge_at_release": 1.2,
            "root_x_at_release": 0.4,
            "post_release_body_contact": False,
            "post_release_body_force_max": 0.0,
            "stage0_to1_staging_standoff": 0.6,
            "stage0_actual_root_height": 0.57,
            "stage1_actual_root_height": 0.61,
        }

    summary = {
        "episode_terminal_diagnostics": [diagnostic(0, 5), diagnostic(1, 4)],
        "episode_goal_reached": [True, False],
        "episode_max_stage_reached": [5, 4],
    }
    records = build(summary, seed=2, expected_num_envs=2)
    assert [record["env_id"] for record in records] == [0, 1]
    assert records[0]["seed"] == 2
    assert records[0]["goal_reached"] is True
    assert records[0]["stage0_actual_root_height"] == 0.57
    assert records[0]["door_weight"] == 120.0
    assert records[0]["hinge_at_release"] == 1.2
    assert records[0]["root_x_at_release"] == 0.4
    assert records[0]["post_release_body_contact"] is False
    assert records[0]["post_release_body_force_max"] == 0.0

    invalid_goal = dict(summary)
    invalid_goal["episode_goal_reached"] = ["false", False]
    with pytest.raises(ValueError, match="must be bool"):
        build(invalid_goal, seed=2, expected_num_envs=2)

    invalid_max_stage = dict(summary)
    invalid_max_stage["episode_max_stage_reached"] = [4.9, 4]
    with pytest.raises(ValueError, match="integer in"):
        build(invalid_max_stage, seed=2, expected_num_envs=2)

    invalid_final_stage = dict(summary)
    invalid_final_stage["episode_terminal_diagnostics"] = [
        {**diagnostic(0), "stage_buf": True},
        diagnostic(1, 4),
    ]
    with pytest.raises(ValueError, match="integer in"):
        build(invalid_final_stage, seed=2, expected_num_envs=2)

    final_exceeds_max = dict(summary)
    final_exceeds_max["episode_terminal_diagnostics"] = [
        {**diagnostic(0), "stage_buf": 5},
        diagnostic(1, 4),
    ]
    final_exceeds_max["episode_max_stage_reached"] = [4, 4]
    with pytest.raises(ValueError, match="cannot exceed"):
        build(final_exceeds_max, seed=2, expected_num_envs=2)

    duplicated = dict(summary)
    duplicated["episode_terminal_diagnostics"] = [diagnostic(0), diagnostic(0)]
    with pytest.raises(ValueError, match="duplicate"):
        build(duplicated, seed=2, expected_num_envs=2)
