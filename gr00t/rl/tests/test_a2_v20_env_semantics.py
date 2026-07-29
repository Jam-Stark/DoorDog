"""CPU-only v20 M45/M46 pure semantic contracts."""

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
    names = {
        "A2_V20_CORRIDOR_LATCH_LEGACY",
        "A2_V20_CORRIDOR_LATCH_SEND_READY",
        "_a2_v20_validate_vector",
        "a2_v20_update_send_ready",
        "a2_v20_pre_send_root_crossing",
        "a2_v20_stage4_target_root_scale",
        "a2_v20_update_corridor_latch",
    }
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.Assign)) and any(
        isinstance(target, ast.Name) and target.id in names for target in getattr(node, "targets", [])
    ) or isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {"torch": torch, "math": math}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def test_send_ready_requires_hold_and_is_monotonic():
    ns = _helpers()
    ready = torch.tensor([False, False, True])
    hold = torch.tensor([True, False, True])
    hinge = torch.tensor([1.0, 2.0, 0.2])
    updated, first = ns["a2_v20_update_send_ready"](ready, hold, hinge, 1.0)
    assert updated.tolist() == [True, False, True]
    assert first.tolist() == [True, False, False]


def test_pre_send_crossing_is_distinct_and_post_send_is_legal():
    ns = _helpers()
    opening = torch.tensor([True, True, False, True])
    ready = torch.tensor([False, True, False, False])
    root_x = torch.tensor([0.031, 0.031, 0.5, 0.0])
    assert ns["a2_v20_pre_send_root_crossing"](opening, ready, root_x, 0.03).tolist() == [True, False, False, False]


def test_stage4_ramp_is_exactly_zero_to_half_and_legacy_is_unchanged():
    ns = _helpers()
    hinge = torch.tensor([0.9, 1.0, 1.1, 1.2, 1.6])
    ramp = ns["a2_v20_stage4_target_root_scale"](
        hinge, 1.0, 0.2, enabled=True, send_ready=torch.ones(5, dtype=torch.bool)
    )
    torch.testing.assert_close(ramp, torch.tensor([0.0, 0.0, 0.25, 0.5, 0.5]))
    torch.testing.assert_close(
        ns["a2_v20_stage4_target_root_scale"](
            hinge, 1.0, 0.2, enabled=False, send_ready=torch.zeros(5, dtype=torch.bool)
        ),
        torch.full_like(hinge, 0.5),
    )
    torch.testing.assert_close(
        ns["a2_v20_stage4_target_root_scale"](
            hinge, 1.0, 0.2, enabled=True, send_ready=torch.zeros(5, dtype=torch.bool)
        ),
        torch.zeros_like(hinge),
    )


def test_v20_corridor_latch_ignores_root_crossing():
    ns = _helpers()
    base = torch.zeros(2, dtype=torch.bool)
    crossed = torch.tensor([True, False])
    send = torch.tensor([False, True])
    stage = torch.tensor([4, 4], dtype=torch.long)
    hinge = torch.tensor([1.2, 0.2])
    updated = ns["a2_v20_update_corridor_latch"](
        base,
        crossed,
        send,
        stage,
        hinge,
        4,
        True,
        "send_ready_v20",
    )
    assert updated.tolist() == [False, True]


@pytest.mark.parametrize("bad", (float("nan"), float("inf"), -1.0))
def test_m45_m46_invalid_scalars_fail_fast(bad):
    ns = _helpers()
    with pytest.raises(ValueError):
        ns["a2_v20_update_send_ready"](
            torch.zeros(1, dtype=torch.bool),
            torch.ones(1, dtype=torch.bool),
            torch.ones(1),
            bad,
        )
