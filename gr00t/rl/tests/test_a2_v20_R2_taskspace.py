"""CPU-only R2 staged admission and task-space evidence tests."""

from __future__ import annotations

import pytest
import torch

from gr00t.rl.envs.door.a2_v20_r2_evidence import (
    a2_v20_r2_snapshot_admission_mask,
    a2_v20_r2_taskspace_arm_carry,
)


def test_r2_snapshot_admission_truth_table_and_empty_slots():
    candidate_stage = torch.tensor([2, 3, 3, 3, 3, 4, 4, 4, 4], dtype=torch.long)
    populated = torch.tensor([True, True, True, True, True, True, True, True, False])
    send_ready = torch.tensor([False, False, False, True, True, True, False, True, True])
    crossing_seen = torch.tensor([False, False, False, False, True, False, False, True, True])
    root_x_rel = torch.tensor([0.0, 0.01, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, float("nan")], dtype=torch.float32)

    result = a2_v20_r2_snapshot_admission_mask(
        candidate_stage, populated, send_ready, crossing_seen, root_x_rel, 0.03, 3, 4
    )

    assert result["admit"].tolist() == [True, True, False, True, False, True, False, False, False]
    assert result["reason_code"].tolist() == [1, 2, 11, 3, 10, 4, 12, 10, 0]


def test_r2_snapshot_admission_fails_fast_beyond_through():
    values = torch.zeros(1, dtype=torch.bool)
    with pytest.raises(ValueError, match="unsupported stage"):
        a2_v20_r2_snapshot_admission_mask(
            torch.tensor([5], dtype=torch.long),
            values, values, values, torch.zeros(1, dtype=torch.float32), 0.03, 3, 4
        )


def test_r2_taskspace_requires_all_scope_masks_and_preserves_share_contract():
    zeros = torch.zeros(4, 3)
    root_lin = torch.tensor([[0.5, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    tcp_lin = torch.tensor([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    tangent = torch.tensor([[1.0, 0.0, 0.0]]).repeat(4, 1)
    result = a2_v20_r2_taskspace_arm_carry(
        zeros, root_lin, zeros, zeros, tcp_lin, tangent,
        torch.tensor([True, True, True, True]),
        torch.tensor([True, True, True, False]),
        torch.tensor([True, False, True, True]),
        torch.tensor([True, True, False, True]),
        0.1,
    )
    assert result["active"].tolist() == [True, False, False, False]
    assert result["arm_tangent_share"].tolist() == pytest.approx([0.5, 0.0, 0.0, 0.0])
    assert torch.all(torch.isfinite(result["v_base_at_tcp"]))
    assert torch.all(result["arm_tangent_share"][~result["active"]] == 0.0)


def test_r2_taskspace_rejects_bad_tangent_and_nonfinite_inputs():
    zeros = torch.zeros(1, 3)
    masks = torch.ones(1, dtype=torch.bool)
    with pytest.raises(ValueError, match="unit length"):
        a2_v20_r2_taskspace_arm_carry(
            zeros, zeros, zeros, zeros, zeros, torch.tensor([[2.0, 0.0, 0.0]]),
            masks, masks, masks, masks, 0.1
        )
    bad_root = zeros.clone()
    bad_root[0, 0] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        a2_v20_r2_taskspace_arm_carry(
            bad_root, zeros, zeros, zeros, zeros, torch.tensor([[1.0, 0.0, 0.0]]),
            masks, masks, masks, masks, 0.1
        )
