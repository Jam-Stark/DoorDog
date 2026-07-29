"""CPU-only v20 seven-cell matrix and frozen-value admission checks."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "gr00t/rl/config/ablation/wbmanip"

FILES = {
    "G1": "base_v20_G1_g2_continuation.yaml",
    "G2": "base_v20_G2_economics_only.yaml",
    "G3": "base_v20_G3_send_institution_only.yaml",
    "G4": "base_v20_G4_send_economics.yaml",
    "G5": "base_v20_G5_send_arm_tie.yaml",
    "G6": "base_v20_G6_full.yaml",
    "G7": "base_v20_G7_full_seed1.yaml",
}
FACTORS = {
    "G1": {"send_latch_plumbing": False, "economics": False, "institution": False, "arm_tie": False, "crossing_mode": "disabled", "seed": 0},
    "G2": {"send_latch_plumbing": True, "economics": True, "institution": False, "arm_tie": False, "crossing_mode": "disabled", "seed": 0},
    "G3": {"send_latch_plumbing": True, "economics": False, "institution": True, "arm_tie": False, "crossing_mode": "terminal", "seed": 0},
    "G4": {"send_latch_plumbing": True, "economics": True, "institution": True, "arm_tie": False, "crossing_mode": "terminal", "seed": 0},
    "G5": {"send_latch_plumbing": True, "economics": False, "institution": True, "arm_tie": True, "crossing_mode": "terminal", "seed": 0},
    "G6": {"send_latch_plumbing": True, "economics": True, "institution": True, "arm_tie": True, "crossing_mode": "terminal", "seed": 0},
    "G7": {"send_latch_plumbing": True, "economics": True, "institution": True, "arm_tie": True, "crossing_mode": "terminal", "seed": 1},
}
CKPT = "logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
V19_G2 = CONFIG_DIR / "base_v19_G2_norm_control.yaml"


def _load(group):
    return yaml.safe_load((CONFIG_DIR / FILES[group]).read_text(encoding="utf-8"))


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _flatten(nested, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix, value


def test_v20_matrix_topology_factors_and_checkpoint_are_exact():
    for group, factors in FACTORS.items():
        config = _load(group)
        assert config["checkpoint"] == CKPT
        assert config["checkpoint_load_mode"] == "policy_only"
        assert config["auto_load_latest"] is False
        assert config["seed"] == factors["seed"]
        assert config["num_envs"] == 4096
        assert config["headless"] is True
        assert config["algo"]["trl"]["num_total_batches"] == 2500
        assert config["callbacks"]["model_save"]["save_frequency"] == 250
        env = config["env"]["config"]
        assert env["a2_v20_send_latch_enabled"] is factors["send_latch_plumbing"]
        assert env["a2_v20_traversal_economics_enabled"] is factors["economics"]
        assert env["a2_v20_arm_tie_enabled"] is factors["arm_tie"]
        assert env["a2_v20_pre_send_crossing_mode"] == factors["crossing_mode"]
        assert env["a2_v20_formal_values_frozen"] is False
        assert env["a2_v20_formal_launch"] is False
        assert env["a2_v20_calibration_label"] == "non_formal_calibration_only"


def test_g6_g7_differ_only_seed_and_header():
    g6 = _load("G6")
    g7 = _load("G7")
    g6["seed"] = g7["seed"]
    assert g6 == g7


def test_a_cells_bind_p04_frozen_reward_scales_in_env_and_reward_manager():
    for group in ("G5", "G6", "G7"):
        config = _load(group)
        env = config["env"]["config"]
        rewards = config["rewards"]["reward_scales"]
        assert env["a2_v20_arm_tangent_carry_scale"] == 3.5
        assert env["a2_v20_handle_arc_tracking_scale"] == 0.85
        assert rewards["a2_v20_arm_tangent_carry"] == 3.5
        assert rewards["a2_v20_handle_arc_tracking"] == 0.85


def test_all_cells_explicitly_bind_v19_g2_common_regime_and_e_cells():
    v19 = dict(_flatten(yaml.safe_load(V19_G2.read_text(encoding="utf-8"))))
    intentional_deltas = {
        "checkpoint",
        "seed",
        "env.config.a2_corridor_door_wide_hinge_norm",
        "rewards.reward_scales.a2_corridor_door_wide",
    }
    for group in FILES:
        config = _load(group)
        flattened = dict(_flatten(config))
        for key, value in v19.items():
            if key in intentional_deltas:
                continue
            assert flattened[key] == value, f"{group} drifted v19 G2 common key {key}"
        assert flattened["env.config.a2_stage45_door_frame_contact_scale"] == 0.2
        assert flattened["env.config.a2_stage35_door_panel_contact_scale"] == 0.0
        assert flattened["env.config.a2_stage0_staging_x_min"] == 0.50
        assert flattened["env.config.a2_stage0_staging_x_max"] == 0.80
        assert flattened["env.config.a2_stage0_staging_y_tol"] == 0.15
        if group == "G7":
            assert flattened["seed"] == 1
        else:
            assert flattened["seed"] == 0
    for group in ("G2", "G4", "G6", "G7"):
        env = _load(group)["env"]["config"]
        rewards = _load(group)["rewards"]["reward_scales"]
        assert env["a2_v20_send_latch_enabled"] is True
        assert env["a2_v20_target_root_pre_send_scale"] == 0.0
        assert env["a2_v20_target_root_post_send_stage4_scale"] == 0.5
        assert env["a2_v20_target_root_ramp_width_rad"] == 0.20
        assert env["a2_corridor_door_wide_hinge_norm"] == 1.60
        assert rewards["a2_corridor_door_wide"] == 4.2666667


def test_a_reward_defaults_are_zero_in_shared_yaml():
    reward = yaml.safe_load((ROOT / "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml").read_text(encoding="utf-8"))
    scales = reward["rewards"]["reward_scales"]
    assert scales["a2_v20_arm_tangent_carry"] == 0.0
    assert scales["a2_v20_handle_arc_tracking"] == 0.0
