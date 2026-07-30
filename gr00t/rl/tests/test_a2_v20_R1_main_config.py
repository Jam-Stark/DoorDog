"""Appendix-D source config matrix checks for R1."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "gr00t/rl/config/ablation/wbmanip"
FILES = {
    "G1": "base_v20_R1_G1_g2_continuation.yaml",
    "G2": "base_v20_R1_G2_economics_only.yaml",
    "G3": "base_v20_R1_G3_send_curriculum_only.yaml",
    "G4": "base_v20_R1_G4_send_curriculum_economics.yaml",
    "G5": "base_v20_R1_G5_send_curriculum_arm_tie.yaml",
    "G6": "base_v20_R1_G6_full.yaml",
    "G7": "base_v20_R1_G7_full_seed1.yaml",
    "P2": "base_v20_R1_P2_G4_learnability_pilot.yaml",
}


def _load(name):
    return yaml.safe_load((CONFIG_DIR / FILES[name]).read_text(encoding="utf-8"))


def test_all_eight_configs_bind_frozen_r1_headers_and_topology():
    for name in FILES:
        cfg = _load(name)
        assert cfg["checkpoint_load_mode"] == "policy_only"
        assert cfg["auto_load_latest"] is False
        assert cfg["headless"] is True
        assert cfg["env"]["config"]["a2_v20_R1_plan_id"] == "base_v20_R1_policy_behavior_v1"
        assert cfg["env"]["config"]["a2_v20_R1_p1_status"] == "P1_PHYSICAL_BLOCKER"
        assert cfg["env"]["config"]["a2_v20_send_hinge_threshold"] == 0.90
        assert cfg["env"]["config"]["a2_v20_send_hinge_tolerance"] == 0.05
        assert cfg["env"]["config"]["a2_v20_R1_soft_phase_end_batch"] == 500
        assert cfg["env"]["config"]["a2_v20_R1_plan_sha256"] == "6827290631feea15497fe76cd64116c30a1343d5bd6c1cb83ba09c35bc247e3c"
        assert cfg["env"]["config"]["a2_v20_formal_values_frozen"] is True
        assert cfg["env"]["config"]["a2_v20_formal_launch"] is False
        if name == "P2":
            assert cfg["num_envs"] == 256
            assert cfg["algo"]["trl"]["num_total_batches"] == 750
        else:
            assert cfg["num_envs"] == 4096
            assert cfg["algo"]["trl"]["num_total_batches"] == 2500


def test_schedule_is_exactly_0_500_and_only_s_cells_have_it():
    for name in FILES:
        cfg = _load(name)
        has_s = cfg["env"]["config"]["a2_v20_R1_send_curriculum_enabled"]
        if has_s:
            schedule = cfg["schedule_dict"]["env@config@a2_v20_pre_send_crossing_mode"]
            assert schedule["seg_steps"] == [0, 500]
            assert schedule["seg_vals"] == ["penalty", "terminal"]
            assert schedule["trigger_func"] == "env@on_a2_v20_R1_crossing_mode_transition"
        else:
            assert "schedule_dict" not in cfg


def test_shared_reward_registry_keeps_r1_terms_zero():
    cfg = yaml.safe_load((ROOT / "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml").read_text(encoding="utf-8"))
    scales = cfg["rewards"]["reward_scales"]
    assert scales["penalty_a2_v20_pre_send_crossing"] == 0.0
    assert scales["a2_v20_arm_tangent_carry"] == 0.0
    assert scales["a2_v20_handle_arc_tracking"] == 0.0
