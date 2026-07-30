"""Static/CPU checks for the R1 staged-reset hard-phase guard."""

from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[3]
DOOR = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
STAGED = ROOT / "gr00t/rl/envs/base_task/staged_task_base.py"


def test_base_hook_is_shape_checked_and_r1_guard_is_present():
    staged = STAGED.read_text(encoding="utf-8")
    door = DOOR.read_text(encoding="utf-8")
    assert "def _filter_staged_reset_snapshot_mask" in staged
    assert "filtered_advance_mask" in staged
    assert "R1 snapshot guard" in door
    assert "on_a2_v20_R1_crossing_mode_transition" in door
    assert "_audit_a2_v20_r1_hard_phase_snapshots" in door


def test_r1_guard_contract_uses_device_local_bool_mask():
    source = DOOR.read_text(encoding="utf-8")
    assert "rejected_count[incompatible] += 1" in source
    assert "return filtered & ~incompatible" in source
    assert "torch.bool" in source
    assert "A2_V20_R1_SOFT_PHASE_END_BATCH" in source



def _snapshot_helper():
    import ast
    source = DOOR.read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_a2_v20_validate_vector", "a2_v20_r1_snapshot_incompatibility_mask"}
    ]
    namespace = {"torch": torch}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(DOOR), "exec"), namespace)
    return namespace["a2_v20_r1_snapshot_incompatibility_mask"]


def test_snapshot_guard_ignores_unpopulated_partial_ring_slots():
    helper = _snapshot_helper()
    data = torch.tensor([[True, True], [True, False], [False, False]], dtype=torch.bool)
    counts = torch.tensor([1, 2], dtype=torch.long)
    assert helper(data, counts).tolist() == [False, True]


def test_snapshot_guard_checks_all_slots_after_ring_wrap():
    helper = _snapshot_helper()
    data = torch.tensor([[True, True], [True, False], [True, True]], dtype=torch.bool)
    counts = torch.tensor([5, 3], dtype=torch.long)
    assert helper(data, counts).tolist() == [False, True]


def test_snapshot_guard_rejects_negative_counts():
    helper = _snapshot_helper()
    with pytest.raises(ValueError):
        helper(torch.ones((2, 1), dtype=torch.bool), torch.tensor([-1], dtype=torch.long))
