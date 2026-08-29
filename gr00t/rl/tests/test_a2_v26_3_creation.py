from pathlib import Path

import pytest
import torch

from gr00t.rl.envs.door.a2_v26_3_creation import (
    A2_V26_3_HANDLE_NORM_RAD,
    a2_v26_3_update_handle_creation,
)


def _step(position, previous, highwater, active=True, dt=0.02):
    active_values = [active] * len(position) if isinstance(active, bool) else active
    return a2_v26_3_update_handle_creation(
        torch.tensor(position, dtype=torch.float32),
        torch.tensor(previous, dtype=torch.float32),
        torch.tensor(highwater, dtype=torch.float32),
        torch.tensor(active_values, dtype=torch.bool),
        control_dt=dt,
    )


def test_creation_pays_only_new_highwater_and_never_stationary_rent():
    created = _step([0.30], [0.20], [0.20])
    assert created["handle_delta_net"].item() == pytest.approx(0.10)
    assert created["handle_delta_highwater"].item() == pytest.approx(0.10)
    assert created["creation_raw"].item() == pytest.approx(
        0.10 / (A2_V26_3_HANDLE_NORM_RAD * 0.02)
    )

    backdrive = _step([0.24], [0.30], [0.30])
    assert backdrive["handle_delta_net"].item() == pytest.approx(-0.06)
    assert backdrive["handle_delta_highwater"].item() == 0.0
    assert backdrive["creation_raw"].item() == 0.0

    revisit = _step([0.30], [0.24], [0.30])
    stationary = _step([0.30], [0.30], [0.30])
    assert revisit["creation_raw"].item() == 0.0
    assert stationary["creation_raw"].item() == 0.0


def test_highwater_evolves_outside_gate_without_retroactive_income():
    outside_gate = _step([0.40], [0.10], [0.10], active=False)
    assert outside_gate["handle_highwater_current"].item() == pytest.approx(0.40)
    assert outside_gate["handle_delta_highwater"].item() == pytest.approx(0.30)
    assert outside_gate["creation_raw"].item() == 0.0

    gate_enters = _step([0.40], [0.40], [0.40], active=True)
    assert gate_enters["handle_delta_highwater"].item() == 0.0
    assert gate_enters["creation_raw"].item() == 0.0


def test_scaled_integral_is_control_dt_invariant():
    coarse = _step([0.50], [0.10], [0.10], dt=0.02)
    fine_first = _step([0.30], [0.10], [0.10], dt=0.01)
    fine_second = _step([0.50], [0.30], [0.30], dt=0.01)
    coarse_integral = coarse["creation_raw"].item() * 0.02
    fine_integral = (
        fine_first["creation_raw"].item() + fine_second["creation_raw"].item()
    ) * 0.01
    assert coarse_integral == pytest.approx(0.40 / A2_V26_3_HANDLE_NORM_RAD)
    assert fine_integral == pytest.approx(coarse_integral)


def test_restored_snapshot_without_new_highwater_has_zero_income():
    restored = _step([0.46], [0.46], [0.46], active=True)
    assert restored["handle_delta_net"].item() == 0.0
    assert restored["handle_delta_highwater"].item() == 0.0
    assert restored["creation_raw"].item() == 0.0


def test_e1_is_a_separate_current_close_gate_selector_in_source():
    root = Path(__file__).parents[3]
    trainer = (
        root / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"
    ).read_text(encoding="utf-8")
    env_source = (
        root / "gr00t/rl/envs/door/door_open_a2_base.py"
    ).read_text(encoding="utf-8")
    assert "_build_a2_eval_stage2_close_gate_forced_close_mask" in trainer
    assert '"_get_a2_stage2_close_reward_gate"' in trainer
    assert "stage2_close_gate_forced_gripper_close_applied" in env_source
    assert "action_mean = policy_model.action_mean.detach()" in trainer
