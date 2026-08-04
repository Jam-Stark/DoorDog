"""CPU/no-sim tests for the pull-v0 paired geometry proof."""

from __future__ import annotations

import json
from pathlib import Path

from scriptsFORhuman.pull_v0.build_geometry_proof import (
    RUNTIME_RECEIPT,
    build_receipt,
    require_source_contracts,
)


ROOT = Path(__file__).resolve().parents[3]


def test_geometry_proof_source_contracts_preserve_mechanics_and_use_high_level_apis():
    contracts = require_source_contracts()
    assert contracts["hinge_handle_latch_mechanics_sha256"] == (
        "3e170bbe9477aa9c84e9627e8d8c9f9525c4e8644deca046fb045b14284fded0"
    )


def test_geometry_runtime_receipt_is_paired_finite_and_nonpenetrating():
    runtime = json.loads(RUNTIME_RECEIPT.read_text(encoding="utf-8"))
    assert runtime["door_open_ios"] == ["out", "in"]
    assert runtime["initial_panel_robot_contact"] is False
    assert runtime["max_panel_robot_contact_force_N"] == 0.0
    assert runtime["positive_hinge_probe"]["both_move_positive_world_x"] is True


def test_overlay_selects_the_mirrored_pull_target_orientation():
    runtime = json.loads(RUNTIME_RECEIPT.read_text(encoding="utf-8"))
    orientation = runtime["orientation_overlay"]
    assert orientation["selected_pull_orientation"] == "io_z_pre"
    assert orientation["selected_pull_target_quaternion_wxyz"] == [-0.5, -0.5, 0.5, 0.5]
    assert orientation["mirrored_error_delta_rad"]["handle_io_z_pre"] < 1.0e-3


def test_final_geometry_proof_keeps_runtime_and_training_claims_separate():
    receipt = build_receipt()
    assert receipt["status"] == "PASS"
    assert receipt["evidence_boundary"] == {
        "static": "PASS",
        "isaacsim_runtime": "PASS",
        "policy_or_training": "NOT_RUN",
    }
    assert receipt["threshold_mode"] == "report_only"
    assert receipt["paired_fixture"]["directions"]["in"]["final_target_x_m"] == -2.0
    assert receipt["paired_fixture"]["directions"]["out"]["active_handle_face_x_m"] < 0.0
    assert receipt["paired_fixture"]["directions"]["in"]["active_handle_face_x_m"] > 0.0
