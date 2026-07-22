"""No-simulation tests for the v17 contact-event and stage-income semantics."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
import torch
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[3]
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
ENV_CONFIG = ROOT / "gr00t/rl/config/env/door_open_a2_base.yaml"
REWARD_CONFIG = (
    ROOT / "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml"
)
ABLATION_DIR = ROOT / "gr00t/rl/config/ablation/wbmanip"
CHECKPOINT = (
    "logs_rl/a2_piper_full_stage_a2_base/"
    "base_v16_B_m29_m32_mass80_160-20260721_230405/model_step_002000.pt"
)


def _env_helpers():
    names = {
        "a2_update_stage4_release_and_root_latches",
        "a2_update_stage4_release_and_root_latches_through_stage5",
        "a2_scope_door_body_contact_force",
        "a2_update_door_body_contact_event",
        "a2_finalize_door_body_contact_event",
        "a2_corridor_clean_passage_component",
        "a2_update_stage5_hold_continuation",
    }
    tree = ast.parse(ENV_SOURCE.read_text(encoding="utf-8"))
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {"math": math, "torch": torch}
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(ENV_SOURCE), "exec"),
        namespace,
    )
    return namespace


def _class_method_source(name):
    tree = ast.parse(ENV_SOURCE.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    method = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return ast.unparse(method)


def test_contact_event_force_excludes_preopening_and_postswing_stages():
    helpers = _env_helpers()
    scope_force = helpers["a2_scope_door_body_contact_force"]
    update_event = helpers["a2_update_door_body_contact_event"]
    stage = torch.tensor([2, 3, 4, 5], dtype=torch.long)
    body_total = torch.tensor([400.0, 20.0, 30.0, 500.0])

    scoped = scope_force(stage, body_total, 3, 4)
    torch.testing.assert_close(scoped, torch.tensor([0.0, 20.0, 30.0, 0.0]))
    active, peak, emitted = update_event(
        torch.zeros(4, dtype=torch.bool),
        torch.zeros(4),
        scoped,
        5.0,
        200.0,
        2.0,
    )
    assert active.tolist() == [False, True, True, False]
    torch.testing.assert_close(peak, torch.tensor([0.0, 20.0, 30.0, 0.0]))
    torch.testing.assert_close(emitted, torch.zeros(4))
    assert "a2_scope_door_body_contact_force" in _class_method_source(
        "_update_a2_door_body_contact_event"
    )


def test_contact_event_starts_at_threshold_tracks_peak_and_charges_once():
    helper = _env_helpers()["a2_update_door_body_contact_event"]
    active = torch.zeros(2, dtype=torch.bool)
    peak = torch.zeros(2)

    active, peak, emitted = helper(
        active, peak, torch.tensor([5.0, 500.0]), 5.0, 200.0, 2.0
    )
    assert active.tolist() == [True, True]
    torch.testing.assert_close(peak, torch.tensor([5.0, 500.0]))
    torch.testing.assert_close(emitted, torch.zeros(2))

    active, peak, emitted = helper(
        active, peak, torch.tensor([20.0, 300.0]), 5.0, 200.0, 2.0
    )
    torch.testing.assert_close(peak, torch.tensor([20.0, 500.0]))
    torch.testing.assert_close(emitted, torch.zeros(2))

    active, peak, emitted = helper(
        active, peak, torch.tensor([4.999, 0.0]), 5.0, 200.0, 2.0
    )
    assert active.tolist() == [False, False]
    torch.testing.assert_close(peak, torch.zeros(2))
    torch.testing.assert_close(emitted, torch.tensor([0.1, 2.0]))

    with pytest.raises(ValueError):
        helper(active, peak, torch.tensor([float("nan"), 0.0]), 5.0, 200.0, 2.0)


def test_contact_event_stage_or_terminal_finalization_is_masked_and_capped():
    helper = _env_helpers()["a2_finalize_door_body_contact_event"]
    active = torch.tensor([True, True, False])
    peak = torch.tensor([100.0, 800.0, 0.0])
    next_active, next_peak, emitted = helper(
        active,
        peak,
        torch.tensor([True, False, True]),
        200.0,
        2.0,
    )
    assert next_active.tolist() == [False, True, False]
    torch.testing.assert_close(next_peak, torch.tensor([0.0, 800.0, 0.0]))
    torch.testing.assert_close(emitted, torch.tensor([0.5, 0.0, 0.0]))


def test_clean_passage_requires_corridor_and_strictly_subthreshold_body_force():
    helper = _env_helpers()["a2_corridor_clean_passage_component"]
    result = helper(
        torch.tensor([True, True, True, False]),
        torch.tensor([0.0, 4.999, 5.0, 0.0]),
        5.0,
    )
    torch.testing.assert_close(result, torch.tensor([1.0, 1.0, 0.0, 0.0]))


def test_stage5_hold_continuation_is_irreversible_after_contact_loss():
    helper = _env_helpers()["a2_update_stage5_hold_continuation"]
    continuation = torch.tensor([True, True, False])
    stage = torch.tensor([5, 5, 5], dtype=torch.long)
    continuation = helper(
        continuation, stage, torch.tensor([True, False, True]), 5, True
    )
    assert continuation.tolist() == [True, False, False]
    continuation = helper(
        continuation, stage, torch.tensor([True, True, True]), 5, True
    )
    assert continuation.tolist() == [True, False, False]
    assert not helper(continuation, stage, torch.ones(3, dtype=torch.bool), 5, False).any()


def test_release_latch_extends_to_stage5_only_when_selector_is_enabled():
    helpers = _env_helpers()
    historical = helpers["a2_update_stage4_release_and_root_latches"]
    extended = helpers[
        "a2_update_stage4_release_and_root_latches_through_stage5"
    ]
    gate = torch.zeros(3, dtype=torch.bool)
    crossed = torch.zeros(3, dtype=torch.bool)
    stage = torch.tensor([4, 5, 5], dtype=torch.long)
    hinge = torch.tensor([1.39, 1.40, 1.50])
    root_x = torch.tensor([-0.1, 0.1, -0.1])

    historical_result = historical(gate, crossed, stage, hinge, root_x, 1.40, 4)
    disabled_result = extended(
        gate, crossed, stage, hinge, root_x, 1.40, 4, 5, False
    )
    assert all(torch.equal(left, right) for left, right in zip(historical_result, disabled_result))

    enabled_gate, enabled_crossed = extended(
        gate, crossed, stage, hinge, root_x, 1.40, 4, 5, True
    )
    assert enabled_gate.tolist() == [False, True, True]
    assert enabled_crossed.tolist() == [False, True, False]


def test_v17_lifecycle_and_dt_compensation_are_explicit_in_source():
    precompute = _class_method_source("_pre_compute_observations_callback")
    assert "_update_a2_door_body_contact_event" in precompute
    assert "_update_a2_stage5_hold_continuation" in precompute
    assert "_update_a2_stage4_release_and_root_latches" in precompute

    stage3_callback = _class_method_source("_stage_3_to_4_advance_callback")
    stage4_callback = _class_method_source("_stage_4_to_5_advance_callback")
    assert "_finalize_a2_door_body_contact_event" in stage3_callback
    assert "_finalize_a2_door_body_contact_event" in stage4_callback
    assert "_a2_stage5_hold_continuation" in stage4_callback

    reward = _class_method_source("_reward_penalty_a2_door_body_contact")
    assert "penalty_mode == 'event_v17'" in reward
    assert "/ float(self.dt)" in reward
    assert "terminal_mask" in reward
    assert "terminal_state.dtype != torch.long" in reward
    assert "terminal_state.bool()" in reward

    reset = _class_method_source("_reset_buffers_callback")
    for field in (
        "_a2_stage5_hold_continuation",
        "_a2_door_body_contact_event_active",
        "_a2_door_body_contact_event_peak",
        "_a2_door_body_contact_event_pending",
        "_a2_door_body_contact_event_emitted",
    ):
        assert field in reset

    diagnostics = _class_method_source("_get_a2_terminal_diagnostics")
    assert "'control_dt'" in diagnostics
    assert "'reward_episode_sums'" in diagnostics


def test_shared_v17_defaults_preserve_historical_behavior():
    env = OmegaConf.load(ENV_CONFIG).env.config
    rewards = OmegaConf.load(REWARD_CONFIG).rewards.reward_scales
    assert env.a2_stage5_hold_income_continuity_enabled is False
    assert env.a2_stage4_to5_door_hinge_threshold == pytest.approx(1.0472)
    assert env.a2_door_body_contact_event_force_threshold == 5.0
    assert env.a2_door_body_contact_event_peak_force_norm == 200.0
    assert env.a2_door_body_contact_event_component_cap == 2.0
    assert rewards.a2_corridor_clean_passage == 0.0


@pytest.mark.parametrize(
    ("name", "num_envs", "m34", "m35", "hinge_threshold"),
    (
        ("base_v17_G1_full_m34_m35_hinge135.yaml", 2048, True, True, 1.35),
        ("base_v17_G5_full_m34_m35_hinge125.yaml", 2048, True, True, 1.25),
        ("base_v17_G2_m35_only.yaml", 4096, False, True, 1.35),
        ("base_v17_G3_m34_only.yaml", 4096, True, False, 1.0472),
        ("base_v17_G4_v16_control.yaml", 4096, False, False, 1.0472),
        ("base_v17_G6_full_m34_m35_robustness.yaml", 4096, True, True, 1.35),
    ),
)
def test_six_group_matrix_is_exact(name, num_envs, m34, m35, hinge_threshold):
    config = OmegaConf.load(ABLATION_DIR / name)
    env = config.env.config
    rewards = config.rewards.reward_scales
    assert config.checkpoint == CHECKPOINT
    assert config.checkpoint_load_mode == "policy_only"
    assert config.auto_load_latest is False
    assert config.seed == 0
    assert config.num_envs == num_envs
    assert config.headless is True
    assert config.algo.trl.num_total_batches == 2500
    assert config.callbacks.model_save.save_frequency == 250
    assert list(env.a2_door_weight_range) == [80.0, 160.0]
    assert env.a2_corridor_enabled is True
    assert env.a2_stage5_hold_income_continuity_enabled is m35
    assert env.a2_stage4_to5_door_hinge_threshold == pytest.approx(hinge_threshold)
    assert env.a2_stage4_release_hinge_threshold == pytest.approx(1.40 if m35 else 1.04)
    assert env.a2_door_body_contact_penalty_mode == (
        "event_v17" if m34 else "quadratic_v16"
    )
    assert rewards.penalty_a2_door_body_contact == (-3.0 if m34 else -2.0)
    assert rewards.penalty_a2_posture_command_l1 == (-1.5 if m34 else -0.15)
    assert rewards.a2_corridor_clean_passage == (1.0 if m34 else 0.0)
    assert rewards.a2_corridor_door_wide == (4.0 if m35 else 2.0)


@pytest.mark.parametrize(
    "name",
    (
        "base_v17_G1_full_m34_m35_hinge135",
        "base_v17_G5_full_m34_m35_hinge125",
        "base_v17_G2_m35_only",
        "base_v17_G3_m34_only",
        "base_v17_G4_v16_control",
        "base_v17_G6_full_m34_m35_robustness",
    ),
)
def test_six_group_configs_compose_with_the_production_experiment(name):
    config_dir = ROOT / "gr00t/rl/config"
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        composed = compose(
            config_name="base",
            overrides=["+exp=wbmanip/door_open_a2_base_lstm", f"+ablation=wbmanip/{name}"],
        )
    assert composed.checkpoint == CHECKPOINT
