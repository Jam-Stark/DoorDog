"""CPU-only R1 send curriculum and wrapped-root contracts."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"


def _helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted = {
        "_a2_v20_validate_vector",
        "a2_v20_r1_pre_send_crossing_penalty",
        "a2_v20_r1_root_reconfiguration",
        "a2_v20_r1_durable_crossing_event",
        "a2_v20_taskspace_valid_mask",
        "a2_v20_arc_tracking_quality",
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {
        "torch": torch,
        "math": math,
        "wrap_to_pi": lambda value: (value + math.pi) % (2 * math.pi) - math.pi,
        "A2_V20_R1_CROSSING_MODES": frozenset(("penalty", "terminal")),
        "quat_mul": lambda q1, q2: torch.stack((
            q1[:, 0] * q2[:, 0] - torch.sum(q1[:, 1:] * q2[:, 1:], dim=-1),
            q1[:, 0, None] * q2[:, 1:] + q2[:, 0, None] * q1[:, 1:] + torch.cross(q1[:, 1:], q2[:, 1:], dim=-1),
        ), dim=-1),
        "quat_inv": lambda q: torch.cat((q[:, :1], -q[:, 1:]), dim=-1),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def test_one_shot_penalty_is_dt_invariant_and_monotonic():
    ns = _helpers()
    opening = torch.tensor([True])
    ready = torch.tensor([False])
    seen = torch.tensor([False])
    root = torch.tensor([0.031])
    hinge = torch.tensor([0.45])
    _, raw_002, seen_after = ns["a2_v20_r1_pre_send_crossing_penalty"](
        opening, ready, root, hinge, seen,
        root_x_margin=0.03, theta_send=0.90, base_component=1.0,
        shortfall_gain=1.0, control_dt=0.02, mode="penalty",
    )
    _, raw_004, _ = ns["a2_v20_r1_pre_send_crossing_penalty"](
        opening, ready, root, hinge, seen,
        root_x_margin=0.03, theta_send=0.90, base_component=1.0,
        shortfall_gain=1.0, control_dt=0.04, mode="penalty",
    )
    assert raw_002.item() * 0.02 == pytest.approx(raw_004.item() * 0.04)
    assert seen_after.tolist() == [True]
    _, duplicate, _ = ns["a2_v20_r1_pre_send_crossing_penalty"](
        opening, ready, root, hinge, seen_after,
        root_x_margin=0.03, theta_send=0.90, base_component=1.0,
        shortfall_gain=1.0, control_dt=0.02, mode="penalty",
    )
    assert duplicate.item() == 0.0


@pytest.mark.parametrize("mode", ["disabled", "invalid"])
def test_r1_penalty_mode_rejects_non_r1_modes(mode):
    ns = _helpers()
    with pytest.raises(ValueError):
        ns["a2_v20_r1_pre_send_crossing_penalty"](
            torch.tensor([True]), torch.tensor([False]), torch.tensor([0.1]), torch.tensor([0.4]), torch.tensor([False]),
            root_x_margin=0.03, theta_send=0.90, base_component=1.0,
            shortfall_gain=1.0, control_dt=0.02, mode=mode,
        )


def test_wrapped_yaw_does_not_report_a_two_pi_jump():
    ns = _helpers()
    current = torch.tensor([[0.0, 0.0, -math.pi + 0.01]])
    reference = torch.tensor([[0.0, 0.0, math.pi - 0.01]])
    result = ns["a2_v20_r1_root_reconfiguration"](current, reference)
    assert result.shape == (1, 4)
    assert result[0, 3].item() == pytest.approx(0.02, abs=1e-5)


def test_batch500_hard_crossing_survives_next_observation_update():
    ns = _helpers()
    normal = torch.tensor([False, False])
    pending = torch.tensor([True, False])
    assert ns["a2_v20_r1_durable_crossing_event"](
        normal, pending, mode="terminal"
    ).tolist() == [True, False]
    assert ns["a2_v20_r1_durable_crossing_event"](
        normal, pending, mode="penalty"
    ).tolist() == [False, False]


def test_taskspace_mask_rejects_pregrasp_postsend_lost_hold_and_postrelease():
    ns = _helpers()
    stage = torch.tensor([3, 3, 3, 3, 5, 1], dtype=torch.long)
    hold = torch.tensor([True, True, False, True, True, True])
    send = torch.tensor([False, True, False, False, False, False])
    reference = torch.ones(6, dtype=torch.bool)
    hinge = torch.ones(6)
    release = torch.tensor([False, False, False, True, False, False])
    kinematic = torch.ones(6, dtype=torch.bool)
    result = ns["a2_v20_taskspace_valid_mask"](
        stage, hold, send, reference, hinge, release, kinematic,
        stage_open=3, stage_through=5,
    )
    assert result.tolist() == [True, False, False, False, False, False]


def test_taskspace_mask_rejects_nonpositive_progress():
    ns = _helpers()
    result = ns["a2_v20_taskspace_valid_mask"](
        torch.tensor([3], dtype=torch.long),
        torch.tensor([True]), torch.tensor([False]), torch.tensor([True]),
        torch.tensor([0.0]), torch.tensor([False]), torch.tensor([True]),
        stage_open=3, stage_through=5,
    )
    assert result.tolist() == [False]


def test_arc_tracking_rejects_degenerate_reference_quaternion():
    ns = _helpers()
    with pytest.raises(ValueError):
        ns["a2_v20_arc_tracking_quality"](
            torch.zeros((1, 3)),
            torch.zeros((1, 4)),
            torch.zeros((1, 3)),
            torch.tensor([[1.0, 0.0, 0.0, 0.0]]),
            torch.tensor([True]),
            position_tolerance_m=0.1,
            orientation_tolerance_rad=0.1,
        )
