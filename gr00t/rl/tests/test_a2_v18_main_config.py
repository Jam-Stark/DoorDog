"""CPU-only contract checks for the formal v18 main training ablation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "gr00t/rl/config"
ABLATION_DIR = CONFIG_DIR / "ablation/wbmanip"
G5_CONFIG = ABLATION_DIR / "base_v17_G5_full_m34_m35_hinge125.yaml"
MAIN_CONFIG = ABLATION_DIR / "base_v18_main.yaml"
DOOR_ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
G5_CHECKPOINT = (
    "logs_rl/a2_piper_full_stage_a2_base/"
    "base_v17/base_v17_G5_full_m34_m35_hinge125-20260723_011415/"
    "model_step_002500.pt"
)
M39_EFFORT_LIMITS = [
    120.0,
    120.0,
    180.0,
    120.0,
    120.0,
    180.0,
    120.0,
    120.0,
    180.0,
    120.0,
    120.0,
    180.0,
    100.0,
    100.0,
    100.0,
    100.0,
    100.0,
    100.0,
    45.0,
    45.0,
]


def _container(path: Path) -> dict:
    return OmegaConf.to_container(OmegaConf.load(path), resolve=True)


def _expected_v18_main() -> dict:
    """Build the contract as G5 plus the approved M39/P2 deltas."""

    expected = deepcopy(_container(G5_CONFIG))
    expected.update(
        {
            "checkpoint": G5_CHECKPOINT,
            "num_envs": 1024,
        }
    )
    expected["env"]["config"].update(
        {
            "a2_m39_gripper_material_enabled": True,
            "a2_stage2_squeeze_force_max": 30.0,
            "a2_stage2_over_force_threshold": 55.0,
        }
    )
    expected["rewards"]["reward_scales"]["penalty_a2_posture_command_l1"] = -0.3
    expected["robot"]["dof_effort_limit_list"] = M39_EFFORT_LIMITS
    expected["robot"]["control"]["stiffness"].update(
        {"arm_j7": 1300.0, "arm_j8": 1300.0}
    )
    expected["robot"]["control"]["damping"].update(
        {"arm_j7": 32.0, "arm_j8": 32.0}
    )
    return expected


def test_v18_main_is_exactly_g5_plus_approved_m39_and_p2_deltas():
    actual = _container(MAIN_CONFIG)

    # Deep equality makes omitted G5 thresholds/rewards and accidental new
    # shaping/probe fields fail fast instead of silently drifting.
    assert actual == _expected_v18_main()
    assert actual["checkpoint_load_mode"] == "policy_only"
    assert actual["auto_load_latest"] is False
    assert actual["seed"] == 0
    assert actual["num_envs"] == 1024
    assert actual["algo"]["trl"]["num_total_batches"] == 2500
    assert actual["callbacks"]["model_save"]["save_frequency"] == 250


def test_v18_main_contains_no_probe_only_or_strict_eval_settings():
    actual = _container(MAIN_CONFIG)

    # The training ablation must not inherit the combined-probe diagnostic
    # selectors or strict M41 telemetry admission settings.
    assert "config" not in actual["algo"]
    env_keys = set(actual["env"]["config"])
    assert not any(key.startswith("a2_hold_diagnostic_") for key in env_keys)
    assert "a2_eval_m41_strict_telemetry" not in env_keys
    assert actual["env"]["config"]["a2_m39_gripper_material_enabled"] is True


def test_v18_main_hydra_compose_preserves_training_contract():
    with initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_DIR)):
        composed = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_base_lstm",
                "+ablation=wbmanip/base_v18_main",
            ],
        )

    assert composed.checkpoint == G5_CHECKPOINT
    assert composed.checkpoint_load_mode == "policy_only"
    assert composed.auto_load_latest is False
    assert composed.seed == 0
    assert composed.num_envs == 1024
    assert composed.algo.trl.num_total_batches == 2500
    assert composed.callbacks.model_save.save_frequency == 250
    assert composed.env.config.a2_m39_gripper_material_enabled is True
    assert composed.env.config.a2_hold_diagnostic_contact_detail_enabled is False
    assert composed.env.config.a2_stage2_squeeze_force_max == 30.0
    assert composed.env.config.a2_stage2_over_force_threshold == 55.0
    assert composed.rewards.reward_scales.penalty_a2_posture_command_l1 == -0.3
    assert list(composed.robot.dof_effort_limit_list)[-2:] == [45.0, 45.0]
    assert composed.robot.control.stiffness.arm_j7 == 1300.0
    assert composed.robot.control.stiffness.arm_j8 == 1300.0
    assert composed.robot.control.damping.arm_j7 == 32.0
    assert composed.robot.control.damping.arm_j8 == 32.0


def test_v18_main_m39_runtime_invariant_is_independent_of_probe_contact_detail():
    source = DOOR_ENV_SOURCE.read_text(encoding="utf-8")
    init_start = source.index("    def _init_a2_door_pregrasp_state(self):")
    init_end = source.index("    def ", init_start + 8)
    init_source = source[init_start:init_end]

    assert "_get_a2_m39_gripper_material_enabled" in init_source
    assert "_get_a2_hold_contact_detail_enabled" not in init_source
    assert 'getattr(self.simulator, "_m39_material_runtime_metadata", None)' in init_source
    assert "M39 gripper material runtime evidence is unavailable." in init_source
