"""CPU/no-sim v21-B guard and config contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
from hydra.core.override_parser.overrides_parser import OverridesParser

from scriptsFORhuman.v21B._v21b_common import V21B_CELL_ORDER, V21B_PLAN_ID, V21BError, config_for_cell, hydra_string_value, read_yaml, validate_resolved_v21b_parity, validate_v21b_config
from scriptsFORhuman.v21B.a2_piper_v21B_p0_admission import validate_guard_values


ROOT = Path(__file__).resolve().parents[3]


def test_all_v21b_configs_are_factor_and_latch_bound():
    for cell in V21B_CELL_ORDER:
        config = read_yaml(config_for_cell(ROOT, cell))
        factors = validate_v21b_config(config, cell=cell)
        env = config["env"]["config"]
        assert env["a2_corridor_latch_mode"] == "send_ready_v20"
        assert env["a2_v21B_target_root_ramp_theta_rad"] == env["a2_v20_send_hinge_threshold"] == factors["theta_send_rad"]
        assert env["a2_v20_R1_plan_id"] == V21B_PLAN_ID
        assert env["a2_v21B_cell"] == cell
        assert env["a2_v21B_arm_profile"] == config["v21b_arm_profile"]
        assert config["num_envs"] == 4096
        assert config["algo"]["trl"]["num_total_batches"] == 2500
        assert config["callbacks"]["model_save"]["save_frequency"] == 250


def test_v21b_theta_closed_interval_and_v20_rejection():
    common = dict(plan_id=V21B_PLAN_ID, tolerance_rad=0.05, root_margin_m=0.03, soft_phase_end_batch=500, crossing_base_component=1.0, crossing_shortfall_gain=1.0, crossing_mode="penalty", send_latch_enabled=True)
    assert validate_guard_values(theta_send_rad=1.20, **common)["theta_send_rad"] == 1.20
    with pytest.raises(V21BError, match="v21-B"):
        validate_guard_values(theta_send_rad=1.35, **common)
    with pytest.raises(V21BError):
        validate_guard_values(plan_id="base_v20_R1_policy_behavior_v1", theta_send_rad=1.20, **{key: value for key, value in common.items() if key != "plan_id"})
    assert validate_guard_values(plan_id="base_v20_R1_policy_behavior_v1", theta_send_rad=0.90, **{key: value for key, value in common.items() if key != "plan_id"})["theta_send_rad"] == 0.90


def test_realistic_profiles_are_explicitly_pre_census_non_launchable():
    for cell in ("B3", "B4", "B5", "B7"):
        config = read_yaml(config_for_cell(ROOT, cell))
        assert config["v21b_arm_profile"] == "ARM_REALISTIC"
        assert config["v21b_arm_profile_selection_state"] == "PRE_CENSUS_UNPROMOTED"
        assert config["v21b_arm_realistic_effort_limit_nm"] is None
        assert config["v21b_formal_launchable"] is False


def test_resolved_hydra_parity_is_allowlist_bound():
    resolved = validate_resolved_v21b_parity(ROOT)
    assert set(resolved) == set(V21B_CELL_ORDER)
    assert resolved["B4"]["env"]["config"]["a2_v21B_cell"] == "B4"


def test_signed_probe_selector_is_explicit_and_ordinary_launches_are_unbound():
    task_selector = (ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py").read_text(encoding="utf-8")
    simulator_selector = (ROOT / "gr00t/rl/simulator/isaacsim/isaacsim.py").read_text(encoding="utf-8")
    smoke_launcher = (ROOT / "scriptsFORhuman/v21B/a2_piper_v21B_smoke_launcher.py").read_text(encoding="utf-8")
    formal_launcher = (ROOT / "scriptsFORhuman/v21B/a2_piper_v21B_formal_launcher.py").read_text(encoding="utf-8")
    flag = "a2_v21B_signed_probe_scenarios_enabled"
    assert "env_config.get(_V21B_SIGNED_PROBE_FLAG) is True" in task_selector
    assert "v21b_probe_key = \"a2_v21B_signed_probe_scenarios_enabled\"" in simulator_selector
    assert "if env_config.get(v21b_probe_key) is True" in simulator_selector
    assert f"+env.config.{flag}=true" not in smoke_launcher
    assert f"+env.config.{flag}=true" not in formal_launcher
    for cell in V21B_CELL_ORDER:
        config = read_yaml(config_for_cell(ROOT, cell))
        assert config["num_envs"] == 4096
        assert flag not in config["env"]["config"]


def test_manifest_hydra_override_is_quoted_as_a_string():
    values = (
        '{"scenario_id":"B4", "path":"/tmp/manifest.json"}',
        "it's a signed manifest",
        r"arbitrary \ backslash \\ and quote-adjacent \' content",
    )
    parser = OverridesParser.create()
    for value in values:
        serialized = hydra_string_value(value)
        assert serialized.startswith("'") and serialized.endswith("'")
        parsed = parser.parse_overrides([f"+manifest={serialized}"])
        assert len(parsed) == 1 and parsed[0].value() == value
