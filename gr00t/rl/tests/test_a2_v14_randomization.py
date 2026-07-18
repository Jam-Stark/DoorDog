"""No-simulation contract tests for v14 door randomization and config."""

from __future__ import annotations

import ast
from numbers import Real
from pathlib import Path

import numpy as np
import pytest
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[3]
DOOR_SOURCE = ROOT / "gr00t/rl/isaac_utils/playground/env_rand/door.py"
SCENARIO_SOURCE = ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"
ENV_CONFIG = ROOT / "gr00t/rl/config/env/door_open_a2_base.yaml"
V14_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v14_main.yaml"
CHECKPOINT = (
    "logs_rl/a2_piper_full_stage_a2_base/"
    "base_v13_1_main-20260717_202500/model_step_003000.pt"
)


def _door_ast() -> ast.Module:
    return ast.parse(DOOR_SOURCE.read_text(encoding="utf-8"))


def _load_range_helper():
    node = next(
        node
        for node in _door_ast().body
        if isinstance(node, ast.FunctionDef) and node.name == "_sample_uniform_range"
    )
    namespace = {"Real": Real, "np": np}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(DOOR_SOURCE), "exec"),
        namespace,
    )
    return namespace["_sample_uniform_range"]


def _spawn_source() -> str:
    node = next(
        node
        for node in _door_ast().body
        if isinstance(node, ast.FunctionDef) and node.name == "spawn_door"
    )
    return ast.unparse(node)


def test_force_range_sampling_is_strict(monkeypatch):
    sample = _load_range_helper()
    calls = []

    def uniform(low, high):
        calls.append((low, high))
        return 3.25

    monkeypatch.setattr(np.random, "uniform", uniform)
    assert sample((2.5, 7.0), "force") == 3.25
    assert calls == [(2.5, 7.0)]

    for invalid in ((2.0, 2.0), (3.0, 2.0), (float("nan"), 3.0), (1.0, float("inf"))):
        with pytest.raises(ValueError):
            sample(invalid, "force")
    for invalid in ([1.0, 2.0], (True, 2.0), ("1", 2.0)):
        with pytest.raises(TypeError):
            sample(invalid, "force")


def test_spawner_defaults_and_deterministic_override_priority_are_exact():
    tree = _door_ast()
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorSpawnerCfg"
    )
    assignments = {
        node.target.id: ast.literal_eval(node.value)
        for node in class_node.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert assignments["hinge_drive_max_force_range"] == (2.5, 4.5)
    assert assignments["handle_drive_max_force_range"] == (1.0, 2.0)

    source = _spawn_source()
    assert "cfg.rand_hinge_drive_max_force is None" in source
    assert "else cfg.rand_hinge_drive_max_force" in source
    assert "_sample_uniform_range(cfg.hinge_drive_max_force_range" in source
    assert "cfg.rand_handle_drive_max_force is None" in source
    assert "else cfg.rand_handle_drive_max_force" in source
    assert "_sample_uniform_range(cfg.handle_drive_max_force_range" in source
    assert "hingeDriveMaxForce" in source
    assert "hinge_drive.GetMaxForceAttr().Get()" in source
    assert "handleDriveMaxForce" in source
    assert "handle_drive.GetMaxForceAttr().Get()" in source
    assert "schemas.modify_collision_properties(root_prim_path, cfg.collision_props)" in source


def test_v14_scenario_is_fixed_right_out_with_explicit_ranges():
    source = SCENARIO_SOURCE.read_text(encoding="utf-8")
    assert 'door_open_lr=["right"]' in source
    assert 'door_open_io=["out"]' in source
    assert "door_handle_tblr=(1.05, 0.80, 0.08, 0.15)" in source
    assert "hinge_drive_max_force_range=(2.5, 7.0)" in source
    assert "handle_drive_max_force_range=(1.0, 3.0)" in source


def test_v14_config_preserves_warm_start_and_training_contract():
    base_env = OmegaConf.load(ENV_CONFIG)
    env_cfg = base_env.env.config
    assert "a2_stage0_staging_x_offset" not in env_cfg
    assert env_cfg.a2_stage0_staging_x_min == 0.55
    assert env_cfg.a2_stage0_staging_x_max == 0.60
    assert env_cfg.a2_stage0_staging_y_tol == 0.15

    v14 = OmegaConf.load(V14_CONFIG)
    assert v14.checkpoint == CHECKPOINT
    assert v14.checkpoint_load_mode == "policy_only"
    assert v14.auto_load_latest is False
    assert v14.seed == 0
    assert v14.num_envs == 1024
    assert v14.headless is True
    assert v14.algo.trl.num_total_batches == 3000
    assert v14.callbacks.model_save.save_frequency == 250
    assert v14.env.config.a2_stage0_staging_x_min == 0.55
    assert v14.env.config.a2_stage0_staging_x_max == 0.60
    assert v14.env.config.a2_stage0_staging_y_tol == 0.15
    assert v14.env.config.a2_stage4_release_hinge_threshold == 1.04
    assert v14.robot.control.stiffness.arm_j7 == 800.0
    assert v14.robot.control.stiffness.arm_j8 == 800.0
    assert v14.robot.control.damping.arm_j7 == 25.0
    assert v14.robot.control.damping.arm_j8 == 25.0
    assert v14.simulator.config.sim.physx.num_velocity_iterations == 2
