"""CPU execution of the v27 recovery methods."""

import ast
from pathlib import Path
from typing import Any, Mapping

import torch


SOURCE = Path(__file__).resolve().parents[3] / "gr00t/rl/envs/door/door_open_a2_base.py"


def _method(name: str):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {"torch": torch, "Any": Any, "Mapping": Mapping}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace[name]


def test_asynchronous_pending_bank_promotes_later_opposite_side_and_restore_uses_available_slot():
    capture = _method("_capture_a2_v27_recovery_bank")
    restore = _method("_restore_a2_v27_recovery_bank")

    class State:
        num_envs = 2
        device = torch.device("cpu")
        STAGE_GRASP = 2
        enable_staged_reset = True
        staged_reset_max_samples_per_stage = 2
        door_open_lr = torch.tensor([1.0, -1.0])

        def __init__(self):
            self._a2_v27_bank = None
            self._a2_v27_recovery_highwater = torch.tensor([3, 4], dtype=torch.long)
            self._a2_v27_recovery_used = torch.tensor([True, True])
            self.payload = torch.tensor([11.0, 22.0])
            self.loaded = torch.zeros(2)
            self.staged_reset_buf = {
                "payload": {
                    "type": "buffer",
                    "data": torch.zeros(1, 2, 2),
                    "store_callback": lambda ids: self.payload[ids],
                    "load_callback": lambda ids, data: self.loaded.__setitem__(ids, data),
                }
            }
            self.stage = None
            self.current_max_stage_buf = torch.zeros(2, dtype=torch.long)
            self._a2_v27_recovery_active = torch.zeros(2, dtype=torch.bool)
            self._a2_v27_recovery_start_step = torch.zeros(2, dtype=torch.long)
            self.episode_length_buf = torch.zeros(2, dtype=torch.long)
            self._a2_v27_bank_reset_used = torch.zeros(2, dtype=torch.bool)
            self._a2_v27_bank_reset_slot = torch.full((2,), -1, dtype=torch.long)
            self._a2_v27_bank_reset_snapshot_count = torch.zeros(2, dtype=torch.long)
            self.need_to_refresh_envs = torch.zeros(2, dtype=torch.bool)

        def set_to_stage(self, ids, stage):
            self.stage = (ids.clone(), stage.clone())

    state = State()
    capture(state, torch.tensor([0], dtype=torch.long))
    assert state._a2_v27_bank["pending"][:, 0].tolist() == [True, False]
    assert not state._a2_v27_bank["available"].any()
    capture(state, torch.tensor([1], dtype=torch.long))
    bank = state._a2_v27_bank
    assert bank["raw_capture_count_by_side"].tolist() == [1, 1]
    assert bank["promotion_count_by_side"].tolist() == [1, 1]
    assert bank["available"][0].tolist() == [True, True]
    state.payload[:] = -1.0
    slots = restore(state, torch.tensor([0], dtype=torch.long))
    assert slots.tolist() == [0]
    assert state.loaded.tolist() == [11.0, 0.0]
    assert state._a2_v27_bank_reset_snapshot_count[0].item() == 1


def test_exact_regrasp_k5_accepts_stage2_and_stage34_only_after_loss_event():
    update = _method("_update_a2_v27_recovery_state")

    class State:
        num_envs = 3
        device = torch.device("cpu")
        STAGE_GRASP, STAGE_OPEN, STAGE_SWING = 2, 3, 4
        _a2_v27_recovery_config = {"enabled": False, "loss_steps": 10, "window_steps": 300}
        stage_buf = torch.tensor([2, 3, 4], dtype=torch.long)
        _a2_v27_k5_ever = torch.zeros(3, dtype=torch.bool)
        _a2_root_x_ever_crossed = torch.zeros(3, dtype=torch.bool)
        _a2_stage4_release_gate = torch.zeros(3, dtype=torch.bool)
        _a2_v27_loss_streak = torch.zeros(3, dtype=torch.long)
        _a2_v27_loss_event = torch.tensor([True, True, False])
        _a2_v27_recovery_active = torch.ones(3, dtype=torch.bool)
        _a2_v27_recovery_start_step = torch.zeros(3, dtype=torch.long)
        episode_length_buf = torch.ones(3, dtype=torch.long)
        _a2_v27_recovery_highwater = torch.zeros(3, dtype=torch.long)
        current_max_stage_buf = torch.tensor([2, 3, 4], dtype=torch.long)
        _a2_v27_regrasp_success = torch.zeros(3, dtype=torch.bool)
        _a2_v27_recovery_used = torch.zeros(3, dtype=torch.bool)
        _a2_v27_arm_j4_limit_residence_steps = torch.zeros(3, dtype=torch.long)
        _upper_non_gripper_dof_idx = [0, 1, 2, 3]
        simulator = type("Simulator", (), {"dof_pos": torch.zeros(3, 4)})()

        def _get_a2_hold_streak_ok_mask(self):
            return torch.tensor([False, True, True])

        def _get_a2_stage3_stage4_contact_squeeze_masks(self, _context):
            return {"both_contact": torch.ones(3, dtype=torch.bool)}

        def _get_a2_stage2_grasp_completion_masks(self):
            return {"completion": torch.tensor([True, False, False])}

    state = State()
    update(state)
    assert state._a2_v27_regrasp_success.tolist() == [True, True, False]


def test_training_perturbation_attempts_first_eligible_even_when_release_latched():
    prepare = _method("_a2_v27_prepare_actor_state")

    class State:
        num_envs = 1
        device = torch.device("cpu")
        STAGE_OPEN, STAGE_SWING = 3, 4
        _a2_high_level_action_dim = 12
        _a2_leg_action_dim = 8
        _a2_v27_recovery_config = {"perturb_prob": 1.0, "perturb_steps": 4, "eval_mode": "nominal"}
        stage_buf = torch.tensor([3], dtype=torch.long)
        _a2_v27_k5_ever = torch.tensor([True])
        _a2_root_x_ever_crossed = torch.tensor([False])
        _a2_stage4_release_gate = torch.tensor([True])
        _a2_v27_perturb_started = torch.tensor([False])
        _a2_v27_perturb_remaining = torch.zeros(1, dtype=torch.long)
        _a2_v27_perturb_command_applied = torch.zeros(1, dtype=torch.bool)
        _a2_v27_perturb_applied_steps = torch.zeros(1, dtype=torch.long)
        _a2_v27_injection_status = torch.zeros(1, dtype=torch.long)
        is_evaluating = False

    state = State()
    action = torch.zeros(1, 20)
    prepared = prepare(state, {"actions": action})
    assert state._a2_v27_perturb_started.tolist() == [True]
    assert state._a2_v27_perturb_applied_steps.tolist() == [1]
    assert prepared["actions"][0, 11].item() == 1.0
