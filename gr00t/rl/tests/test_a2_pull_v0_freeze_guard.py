"""CPU/no-sim pull-v0 freeze-guard regression tests."""

from __future__ import annotations

import ast
import hashlib
import math
from pathlib import Path

import pytest

from gr00t.rl.envs.door.a2_pull_v0_guard import (
    A2_PULL_V0_DIRECTION_CONTRACT_VERSION,
    A2_PULL_V0_PLAN_ID,
    A2_PULL_V0_TARGET_FRAME_VERSION,
    A2_PULL_V0_TARGET_ORIENTATION_WXYZ,
    validate_a2_pull_v0_guard,
)
from scriptsFORhuman.v21B._v21b_common import read_yaml
from scriptsFORhuman.v21B.a2_piper_v21B_p0_admission import validate_guard_values


ROOT = Path(__file__).resolve().parents[3]
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
V20_G4_CONFIG = ROOT / "scriptsFORhuman/pull_v0/source_freeze/v20_G4_resolved_config.yaml"
V21B_B1_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v21B_B1_theta090_arm_v20.yaml"
V20_V21_GUARD_TAIL_SHA256 = "145b49676457b5fa96b5c38cc35004b0ed15146fc2b1b42fb19fad13b8537be7"


def _valid_pull_config() -> dict:
    return {
        "a2_v20_R1_plan_id": A2_PULL_V0_PLAN_ID,
        "a2_pull_direction_contract_version": A2_PULL_V0_DIRECTION_CONTRACT_VERSION,
        "a2_pull_target_frame_version": A2_PULL_V0_TARGET_FRAME_VERSION,
        "a2_pull_target_orientation_wxyz": list(A2_PULL_V0_TARGET_ORIENTATION_WXYZ),
        "a2_pull_door_open_io": "in",
        "a2_pull_door_open_lr": "right",
        "a2_pull_robot_initial_side_x_sign": 1.0,
        "a2_pull_robot_initial_yaw_rad": math.pi,
        "a2_pull_active_handle_face_x_sign": 1.0,
        "a2_pull_travel_dir_x": -1.0,
        "target_root_pos": [-2.0, 0.0, 0.5],
        "max_stage_time": [250, 100, 100, 100, 100, 200],
        "a2_pull_threshold_mode": "report_only",
        "a2_pull_effort_provenance": "ESTIMATE_ONLY",
        "a2_pull_add_walls": False,
        "a2_pull_hook_profile": "STOCHASTIC_BASELINE",
        "a2_pull_friction_profile": "RESOLVED_V20_G4",
        "a2_pull_finger_profile": "V20_G4_45N_KP1300_KD32",
        "a2_v20_R1_send_curriculum_enabled": False,
        "a2_v20_R1_snapshot_guard_enabled": False,
        "a2_v20_send_latch_enabled": False,
        "a2_v20_pre_send_crossing_mode": "disabled",
        "a2_v20_telemetry_enabled": False,
        "a2_v20_traversal_economics_enabled": False,
        "a2_v20_arm_tie_enabled": False,
        "a2_corridor_enabled": False,
        "a2_corridor_latch_mode": "legacy_root_or_hinge",
        "a2_v20_R2_evidence_enabled": False,
        "a2_v20_formal_launch": False,
        "a2_v20_arm_tangent_carry_scale": 0.0,
        "a2_v20_handle_arc_tracking_scale": 0.0,
    }


def _validate_pull(config: dict) -> dict:
    return validate_a2_pull_v0_guard(
        config,
        actual_finger_effort_n=[[45.0, 45.0], [45.0, 45.0]],
        actual_finger_stiffness=[[1300.0, 1300.0], [1300.0, 1300.0]],
        actual_finger_damping=[[32.0, 32.0], [32.0, 32.0]],
    )


def _validate_existing_guard(config: dict) -> dict:
    env = config["env"]["config"]
    return validate_guard_values(
        plan_id=env["a2_v20_R1_plan_id"],
        theta_send_rad=env["a2_v20_send_hinge_threshold"],
        tolerance_rad=env["a2_v20_send_hinge_tolerance"],
        root_margin_m=env["a2_v20_pre_send_root_x_margin"],
        soft_phase_end_batch=env["a2_v20_R1_soft_phase_end_batch"],
        crossing_base_component=env["a2_v20_R1_crossing_base_component"],
        crossing_shortfall_gain=env["a2_v20_R1_crossing_shortfall_gain"],
        crossing_mode=env["a2_v20_pre_send_crossing_mode"],
        send_latch_enabled=env["a2_v20_send_latch_enabled"],
    )


def test_pull_guard_accepts_the_frozen_pull_contract():
    receipt = _validate_pull(_valid_pull_config())
    assert receipt["plan_id"] == A2_PULL_V0_PLAN_ID
    assert receipt["io"] == "in"
    assert receipt["finger_profile"] == "V20_G4_45N_KP1300_KD32"
    assert receipt["num_profile_rows"] == 2
    assert receipt["threshold_mode"] == "report_only"
    assert receipt["effort_provenance"] == "ESTIMATE_ONLY"


@pytest.mark.parametrize(
    ("key", "bad_value", "message"),
    (
        ("a2_pull_active_handle_face_x_sign", -1.0, "active_handle_face"),
        ("a2_pull_door_open_io", "out", "door_open_io"),
        ("target_root_pos", [2.0, 0.0, 0.5], "target_root_pos"),
        ("a2_v20_R1_send_curriculum_enabled", True, "send_curriculum"),
        ("a2_corridor_enabled", True, "corridor_enabled"),
        ("a2_pull_threshold_mode", "hard_gate", "threshold_mode"),
        ("a2_pull_target_orientation_wxyz", [0.5, 0.5, 0.5, 0.5], "target_orientation"),
    ),
)
def test_pull_guard_rejects_push_or_unfrozen_semantics(key: str, bad_value: object, message: str):
    config = _valid_pull_config()
    config[key] = bad_value
    with pytest.raises(RuntimeError, match=message):
        _validate_pull(config)


def test_pull_guard_rejects_a_different_resolved_finger_profile():
    with pytest.raises(RuntimeError, match="finger effort"):
        validate_a2_pull_v0_guard(
            _valid_pull_config(),
            actual_finger_effort_n=[[10.0, 10.0]],
            actual_finger_stiffness=[[1300.0, 1300.0]],
            actual_finger_damping=[[32.0, 32.0]],
        )


def test_pull_guard_rejects_a_named_profile_without_matching_runtime_values():
    config = _valid_pull_config()
    config["a2_pull_finger_profile"] = "P1_10N_KP1300_KD32"
    with pytest.raises(RuntimeError, match="finger effort"):
        _validate_pull(config)


def test_v20_g4_resolved_config_still_validates_against_the_existing_guard_contract():
    receipt = _validate_existing_guard(read_yaml(V20_G4_CONFIG))
    assert receipt == {
        "plan_id": "base_v20_R1_policy_behavior_v1",
        "theta_send_rad": 0.9,
        "legacy_v20": True,
    }


def test_v21b_b1_config_still_validates_against_the_existing_guard_contract():
    receipt = _validate_existing_guard(read_yaml(V21B_B1_CONFIG))
    assert receipt["plan_id"] == "base_v21B_theta_arm_ablation_v1"
    assert receipt["theta_send_rad"] == 0.9


def test_v20_and_v21b_guard_tail_is_byte_identical_to_the_frozen_base():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(child, ast.FunctionDef) and child.name == "_validate_a2_v20_r1_config"
            for child in node.body
        )
    )
    function = next(
        child
        for child in owner.body
        if isinstance(child, ast.FunctionDef) and child.name == "_validate_a2_v20_r1_config"
    )
    first_existing_branch = next(
        statement
        for statement in function.body
        if isinstance(statement, ast.If)
        and isinstance(statement.test, ast.UnaryOp)
        and isinstance(statement.test.op, ast.Not)
        and isinstance(statement.test.operand, ast.Name)
        and statement.test.operand.id == "enabled"
    )
    lines = source.splitlines(keepends=True)
    tail = "".join(lines[first_existing_branch.lineno - 1 : function.end_lineno])
    assert hashlib.sha256(tail.encode("utf-8")).hexdigest() == V20_V21_GUARD_TAIL_SHA256


def test_pull_guard_runs_before_the_existing_guard_tail():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    pull_branch = source.index("if plan_id == A2_PULL_V0_PLAN_ID:")
    existing_branch = source.index("if not enabled:", pull_branch)
    assert pull_branch < existing_branch
    assert "validate_a2_pull_v0_guard(" in source[pull_branch:existing_branch]
