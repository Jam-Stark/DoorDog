"""CPU/no-sim v21-B guard and config contracts."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
from hydra.core.override_parser.overrides_parser import OverridesParser

from scriptsFORhuman.v21B._v21b_common import V21B_CELL_ORDER, V21B_EVAL_CONTRACT_PATH, V21B_PLAN_ID, V21BError, canonical_json_bytes, config_for_cell, hydra_string_value, read_yaml, sha256_file, validate_resolved_v21b_parity, validate_v21b_config
from scriptsFORhuman.v21B.a2_piper_v21B_adaptation import materialize_v21b_configs
from scriptsFORhuman.v21B.a2_piper_v21B_p0_admission import validate_guard_values
from scriptsFORhuman.v21B.a2_piper_v21B_p0_admission import build_p0_admission
from scriptsFORhuman.v21B.a2_piper_v21B_source_freeze import build_source_lock, validate_source_lock


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "scriptsFORhuman/V21/a2_piper_base_v21B_ablation_execution_plan_20260802.md"
MANIFEST = ROOT / "scriptsFORhuman/V21/a2_piper_base_v21B_experiment_manifest_20260802.yaml"


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
        assert env["a2_v21B_evidence_enabled"] is True
        assert env["a2_v20_R2_evidence_enabled"] is True
        assert env["a2_v20_R2_formal_launch"] is False
        assert config["num_envs"] == 4096
        assert config["algo"]["trl"]["num_total_batches"] == 2500
        assert config["callbacks"]["model_save"]["save_frequency"] == 250


def test_v21b_evidence_contract_rejects_missing_or_disabled_shared_r2_trace():
    config = read_yaml(config_for_cell(ROOT, "B1"))
    env = config["env"]["config"]
    env.pop("a2_v21B_evidence_enabled")
    with pytest.raises(V21BError, match="v21-B evidence"):
        validate_v21b_config(config, cell="B1")

    config = read_yaml(config_for_cell(ROOT, "B1"))
    config["env"]["config"]["a2_v20_R2_evidence_enabled"] = False
    with pytest.raises(V21BError, match="shared v20 R2 trace evidence"):
        validate_v21b_config(config, cell="B1")

    config = read_yaml(config_for_cell(ROOT, "B1"))
    config["env"]["config"]["a2_v20_R2_formal_launch"] = True
    with pytest.raises(V21BError, match="legacy v20 R2 formal launch"):
        validate_v21b_config(config, cell="B1")


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


def test_source_lock_binds_current_base_eval_contract_and_rejects_missing_row():
    lock = build_source_lock(ROOT, plan_path=PLAN, manifest_path=MANIFEST)
    eval_row = next(row for row in lock["source_paths"] if row["path"] == V21B_EVAL_CONTRACT_PATH)
    assert eval_row["sha256"] == sha256_file(ROOT / V21B_EVAL_CONTRACT_PATH)
    validate_source_lock(lock, ROOT, require_current=True)

    missing = copy.deepcopy(lock)
    missing["source_paths"] = [row for row in missing["source_paths"] if row["path"] != V21B_EVAL_CONTRACT_PATH]
    missing["source_lock_sha256"] = hashlib.sha256(canonical_json_bytes(missing["source_paths"])).hexdigest()
    with pytest.raises(V21BError, match="base_eval.yaml"):
        validate_source_lock(missing, ROOT, require_current=True)


def test_materialized_eval_contract_merges_only_missing_keys(tmp_path):
    source_lock = build_source_lock(ROOT, plan_path=PLAN, manifest_path=MANIFEST)
    p0 = build_p0_admission(ROOT, source_lock=source_lock)
    receipt = materialize_v21b_configs(
        ROOT,
        phase="CENSUS_PRE_K",
        p0_admission=p0,
        source_lock=source_lock,
        output_root=tmp_path / "pre",
    )
    config = read_yaml(Path(receipt["configs"][0]["path"]))
    base_eval = read_yaml(ROOT / V21B_EVAL_CONTRACT_PATH)["algo"]["config"]["eval"]
    eval_values = config["algo"]["config"]["eval"]
    assert eval_values["num_eval_episodes"] == 200
    assert eval_values["save_videos"] is False
    assert eval_values["video_save_prob"] == 0.05
    assert config["v21b_eval_contract_source_sha256"] == sha256_file(ROOT / V21B_EVAL_CONTRACT_PATH)
    assert config["env"]["config"]["a2_v21B_eval_contract_source_sha256"] == config["v21b_eval_contract_source_sha256"]
    assert config["env"]["config"]["a2_v21B_evidence_enabled"] is True
    assert config["env"]["config"]["a2_v20_R2_evidence_enabled"] is True
    assert config["env"]["config"]["a2_v20_R2_formal_launch"] is False
    for key, expected in base_eval.items():
        if key.startswith("a2_hold_oracle_") or key.startswith("a2_v20_arc_probe_") or key in {
            "a2_diagnostic_trace_enabled",
            "a2_diagnostic_reward_terms",
            "a2_forced_gripper_close_enabled",
            "a2_forced_gripper_close_value",
            "a2_forced_gripper_close_stages",
        }:
            assert eval_values[key] == expected
    assert eval_values["a2_hold_oracle_enabled"] is False
    assert receipt["v21b_eval_contract_source_sha256"] == config["v21b_eval_contract_source_sha256"]


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
