"""Focused CPU-only contracts for the v27 recovery path."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"


def _method(name: str) -> str:
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_absent_v27_keys_leave_the_existing_path_untouched():
    parser = _method("_parse_a2_v27_recovery_config")
    step = _method("_a2_v27_prepare_actor_state")
    update = _method("_update_a2_v27_recovery_state")
    assert 'if not keys:\n            return None' in parser
    assert 'if config is None:\n            return actor_state' in step
    assert 'if config is None:\n            return' in update


def test_recovery_uses_existing_stage2_and_masks_only_non_highwater_payments():
    update = _method("_update_a2_v27_recovery_state")
    reward = _method("_after_reward_components")
    assert 'self.stage_buf[trigger] = self.STAGE_GRASP' in update
    assert 'self.time_in_stage_buf[trigger] = 0' in update
    assert 'self.actual_time_in_stage_buf[trigger] = 0' in update
    assert 'self.current_max_stage_buf[trigger]' in update
    assert 'for name in ("stage", "transition", "success_save_time")' in reward
    assert 'self.rew_buf -= removed' in reward
    assert 'self.episode_sums[name] -= removed' in reward


def test_loss_transition_requires_k5_opening_pre_cross_and_unreleased_state():
    update = _method("_update_a2_v27_recovery_state")
    assert 'self._a2_v27_k5_ever |= opening & hold_ok' in update
    assert '~self._a2_root_x_ever_crossed' in update
    assert '~self._a2_stage4_release_gate' in update
    assert 'self._a2_v27_loss_streak >= config["loss_steps"]' in update
    assert 'self._a2_v27_recovery_used' in update


def test_one_bank_bucket_reuses_registered_snapshot_cases_for_capture_and_restore():
    capture = _method("_capture_a2_v27_recovery_bank")
    restore = _method("_restore_a2_v27_recovery_bank")
    assert 'for name, state_case in self.staged_reset_buf.items()' in capture
    assert 'state_case["store_callback"](env_ids)' in capture
    assert 'state_case["obj"].data.root_state_w[env_ids]' in capture
    assert 'entry["dof_state"]' in capture
    assert 'state_case["load_callback"](env_ids' in restore
    assert 'self.simulator.set_task_root_state_tensor' in restore
    assert 'self.simulator.set_task_dof_state_tensor' in restore
    assert 'self.set_to_stage(env_ids, torch.full_like(env_ids, self.STAGE_GRASP))' in restore


def test_training_eval_and_sham_perturbation_contracts_are_explicit():
    step = _method("_a2_v27_prepare_actor_state")
    assert 'torch.rand(first_env_ids.numel(), device=self.device) < config["perturb_prob"]' in step
    assert 'config["eval_mode"] in ("injected", "sham")' in step
    assert 'if config["eval_mode"] == "injected"' in step
    assert 'prepared_actions[force_open, 11] = 1.0' in step
    assert 'self._a2_v27_perturb_remaining[force_open] -= 1' in step


def test_effective_reset_override_restores_bank_after_base_reset_and_before_origin_recording():
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    reset_methods = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "reset_envs_idx"
    ]
    assert len(reset_methods) == 1
    reset = ast.get_source_segment(source, reset_methods[0]) or ""
    assert reset.index("result = super().reset_envs_idx") < reset.index("self._restore_a2_v27_recovery_bank")
    assert reset.index("self._restore_a2_v27_recovery_bank") < reset.index("self._record_a2_v26_reset_origins")
    restore = _method("_restore_a2_v27_recovery_bank")
    assert restore.index("self.set_to_stage") < restore.index('state_case["load_callback"]')
    assert 'self._a2_v27_recovery_used[env_ids] = bank["recovery_used"][slots, env_ids]' in restore


def test_terminal_telemetry_covers_reducer_contract():
    fields = _method("_get_a2_v27_terminal_diagnostic_fields")
    for name in (
        "body_panel_force_max_from_stage3_n",
        "integrity_violations",
        "arm_j4_limit_residence_steps",
        "first_episode_control_steps",
        "first_crossing_hinge_rad",
        "crossing_while_holding",
        "recovery_itt",
        "injection_status",
        "loss_event",
        "regrasp_success",
        "recovered_complete",
        "recovered_clean_complete",
    ):
        assert name in fields
