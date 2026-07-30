"""CPU/static checks for the v20 R2 staged-reset lifecycle."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOOR = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
STAGED = ROOT / "gr00t/rl/envs/base_task/staged_task_base.py"
EVIDENCE = ROOT / "gr00t/rl/envs/door/a2_v20_r2_evidence.py"


def test_r2_registry_contains_only_historical_state_and_load_hook_is_after_writers():
    door = DOOR.read_text(encoding="utf-8")
    staged = STAGED.read_text(encoding="utf-8")
    for name in (
        "a2_v20_send_ready",
        "a2_v20_pre_send_crossing_seen",
        "a2_v20_first_pre_send_crossing_step",
        "a2_v20_first_send_ready_step",
        "a2_v20_first_root_crossing_step",
        "a2_v20_hinge_at_first_root_crossing",
        "a2_v20_root_x_at_first_crossing",
        "a2_v20_root_entry_pos_se2",
        "a2_v20_root_entry_valid",
        "a2_v20_max_pre_send_displacement_se2",
        "a2_v20_r2_max_pre_send_reconfiguration",
        "a2_corridor_latched",
        "a2_v20_handle_tcp_capture_pos",
        "a2_v20_handle_tcp_capture_quat",
        "a2_v20_handle_tcp_capture_valid",
        "a2_v20_snapshot_crossing_seen",
        "a2_v20_snapshot_root_x_rel",
    ):
        assert f'("{name}"' in door
    for transient in (
        '"a2_v20_prev_tcp_pos_w"',
        '"a2_v20_prev_tcp_valid"',
        '"a2_v20_pre_send_crossing_event"',
        '"a2_v20_r1_crossing_penalty_raw"',
    ):
        registration = door[door.index("def _register_a2_v20_staged_reset_buffers"):door.index("def _store_a2_v20_named_buffer")]
        assert transient not in registration
    assert "def _validate_loaded_staged_reset_sample" in staged
    writer = staged.index("self.simulator.set_task_dof_state_tensor")
    hook = staged.index("self._validate_loaded_staged_reset_sample", writer)
    extras = staged.index("# fill extras", hook)
    assert writer < hook < extras
    assert "a2_v20_r2_snapshot_admission_mask" in door
    assert "_a2_v20_pre_send_crossing_event[selected_env_ids] = False" in door
    assert "_a2_v20_prev_tcp_valid[selected_env_ids] = False" in door


def test_r2_production_uses_exact_pure_taskspace_helper_and_scope_masks():
    door = DOOR.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    assert "a2_v20_r2_taskspace_arm_carry(" in door
    assert "a2_v20_taskspace_arm_carry(" not in door[door.index("def _update_a2_v20_state"):door.index("def _update_a2_stage5_hold_continuation")]
    for argument in (
        "self._a2_v20_handle_tcp_capture_valid",
        "hold_ok",
        "~updated_send_ready",
        "door_joint_vel[:, 0] > 0.0",
    ):
        assert argument in door[door.index("taskspace = a2_v20_r2_taskspace_arm_carry"):door.index("kinematic_active =", door.index("taskspace = a2_v20_r2_taskspace_arm_carry"))]
    assert "safe_total = torch.where(active" in evidence
    assert "arm_tangent_share[~active] != 0.0" in evidence


def test_r2_source_parses_without_low_level_reset_hook_errors():
    ast.parse(DOOR.read_text(encoding="utf-8"))
    ast.parse(STAGED.read_text(encoding="utf-8"))
    ast.parse(EVIDENCE.read_text(encoding="utf-8"))
