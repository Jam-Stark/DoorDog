"""No-simulation contract tests for v14 door randomization and config."""

from __future__ import annotations

import ast
import math
from collections.abc import Sequence
from numbers import Real
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[3]
DOOR_SOURCE = ROOT / "gr00t/rl/isaac_utils/playground/env_rand/door.py"
SCENARIO_SOURCE = ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"
SIMULATOR_SOURCE = ROOT / "gr00t/rl/simulator/isaacsim/isaacsim.py"
EVAL_SOURCE = ROOT / "gr00t/rl/eval_agent_trl.py"
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
    assert "door_handle_tblr=(1.10, 0.80, 0.08, 0.15)" in source
    assert "hinge_drive_max_force_range=(2.5, 12.0)" in source
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

class _FakeDoorSpawnerCfg:
    def __init__(self, door_handle_tblr, rand_door_handle_height=None):
        self.door_handle_tblr = door_handle_tblr
        self.rand_door_handle_height = rand_door_handle_height

    def replace(self, **kwargs):
        return _FakeDoorSpawnerCfg(
            kwargs.get("door_handle_tblr", self.door_handle_tblr),
            kwargs.get("rand_door_handle_height", self.rand_door_handle_height),
        )


class _FakeMultiAssetSpawnerCfg:
    def __init__(self, assets_cfg, random_choice):
        self.assets_cfg = assets_cfg
        self.random_choice = random_choice

    def replace(self, **kwargs):
        return _FakeMultiAssetSpawnerCfg(
            kwargs.get("assets_cfg", self.assets_cfg),
            kwargs.get("random_choice", self.random_choice),
        )


class _FakeDoorCfg:
    def __init__(self, spawn):
        self.spawn = spawn

    def replace(self, **kwargs):
        return _FakeDoorCfg(kwargs.get("spawn", self.spawn))


def _load_scenario_eval_helpers():
    names = {
        "_build_eval_door_handle_height_grid",
        "_validate_eval_door_handle_height_task_obj_cfg",
        "get_TaskObjCfgDict_for_eval_door_handle_height_linspace",
    }
    nodes = [
        node
        for node in ast.parse(SCENARIO_SOURCE.read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {
        "DoorSpawnerCfg": _FakeDoorSpawnerCfg,
        "Real": Real,
        "Sequence": Sequence,
        "math": math,
        "np": np,
        "sim_utils": SimpleNamespace(MultiAssetSpawnerCfg=_FakeMultiAssetSpawnerCfg),
    }
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(SCENARIO_SOURCE), "exec"),
        namespace,
    )
    return namespace


def _load_simulator_eval_loader():
    tree = ast.parse(SIMULATOR_SOURCE.read_text(encoding="utf-8"))
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_get_task_obj_cfg_dict_for_door_eval"
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(SIMULATOR_SOURCE), "exec"),
        namespace,
    )
    return namespace[node.name]


def _load_eval_seed_validator():
    tree = ast.parse(EVAL_SOURCE.read_text(encoding="utf-8"))
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_validate_eval_seed"
    )

    namespace = {}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(EVAL_SOURCE), "exec"),
        namespace,
    )
    return namespace[node.name]
def test_eval_handle_height_grid_is_exact_for_16_and_2():
    helpers = _load_scenario_eval_helpers()
    build_grid = helpers["_build_eval_door_handle_height_grid"]
    grid16 = build_grid([0.80, 1.05], 16, (1.05, 0.80, 0.08, 0.15))
    np.testing.assert_array_equal(grid16, np.linspace(0.80, 1.05, 16))
    assert grid16[0] == 0.80
    assert grid16[-1] == 1.05
    grid2 = build_grid([0.80, 1.05], 2, (1.05, 0.80, 0.08, 0.15))
    assert grid2 == (0.80, 1.05)

def test_eval_handle_height_grid_rejects_invalid_inputs():
    helpers = _load_scenario_eval_helpers()
    build_grid = helpers["_build_eval_door_handle_height_grid"]
    invalid_bounds = (
        None,
        "1.05",
        {0.80, 1.05},
        [0.80],
        [0.80, 1.05, 1.10],
        [True, 1.05],
        [float("nan"), 1.05],
        [0.80, float("inf")],
        [0.79, 1.05],
        [0.80, 1.06],
        [1.05, 0.80],
        [0.80, 0.80],
    )
    for bounds in invalid_bounds:
        with pytest.raises((TypeError, ValueError)):
            build_grid(bounds, 16, (1.05, 0.80, 0.08, 0.15))
    for num_envs in (0, 1):
        with pytest.raises(ValueError):
            build_grid([0.80, 1.05], num_envs, (1.05, 0.80, 0.08, 0.15))
    for num_envs in (True, 2.0, "2"):
        with pytest.raises(TypeError):
            build_grid([0.80, 1.05], num_envs, (1.05, 0.80, 0.08, 0.15))

    list_config_bounds = OmegaConf.create([0.80, 1.05])
    grid_from_list_config = build_grid(
        list_config_bounds, 16, (1.05, 0.80, 0.08, 0.15)
    )
    np.testing.assert_array_equal(grid_from_list_config, np.linspace(0.80, 1.05, 16))
def test_eval_hook_builds_ordered_high_level_variants_and_validates_shape():
    helpers = _load_scenario_eval_helpers()
    base = _FakeDoorSpawnerCfg((1.05, 0.80, 0.08, 0.15))
    original_spawn = _FakeMultiAssetSpawnerCfg([base] * 4, random_choice=False)
    task = {"door": _FakeDoorCfg(original_spawn)}
    helpers["TaskObjCfgDict"] = task
    build_config = helpers["get_TaskObjCfgDict_for_eval_door_handle_height_linspace"]
    result = build_config(16, [0.80, 1.05])
    ordered_spawn = result["door"].spawn
    heights = [asset.rand_door_handle_height for asset in ordered_spawn.assets_cfg]
    assert len(ordered_spawn.assets_cfg) == 16
    np.testing.assert_array_equal(heights, np.linspace(0.80, 1.05, 16))
    assert ordered_spawn.random_choice is False
    assert all(isinstance(asset, _FakeDoorSpawnerCfg) for asset in ordered_spawn.assets_cfg)
    assert result is not task
    assert original_spawn.assets_cfg[0].rand_door_handle_height is None

    validate = helpers["_validate_eval_door_handle_height_task_obj_cfg"]
    bad_count = {"door": _FakeDoorCfg(_FakeMultiAssetSpawnerCfg(ordered_spawn.assets_cfg[:-1], False))}
    with pytest.raises(ValueError, match="count"):
        validate(bad_count, heights)
    bad_order = {"door": _FakeDoorCfg(_FakeMultiAssetSpawnerCfg(list(reversed(ordered_spawn.assets_cfg)), False))}
    with pytest.raises(ValueError, match="order/value"):
        validate(bad_order, heights)

    source = SCENARIO_SOURCE.read_text(encoding="utf-8")
    assert "base_door_cfg.replace(rand_door_handle_height=height)" in source
    assert "spawn_cfg.replace(assets_cfg=variants, random_choice=False)" in source
    assert "MultiAssetSpawnerCfg" in source

def test_eval_loader_preserves_absent_path_and_requires_callable_dict_hook():
    loader = _load_simulator_eval_loader()
    sentinel = object()
    module = SimpleNamespace(TaskObjCfgDict=sentinel)
    env_config = OmegaConf.create({})
    assert loader(module, env_config, 16) is sentinel

    calls = []
    expected = {"door": object()}

    def hook(num_envs, bounds):
        calls.append((num_envs, list(bounds)))
        return expected

    module = SimpleNamespace(
        TaskObjCfgDict=sentinel,
        get_TaskObjCfgDict_for_eval_door_handle_height_linspace=hook,
    )
    env_config = OmegaConf.create(
        {"a2_eval_door_handle_height_linspace": [0.80, 1.05]}
    )

    with pytest.raises(TypeError, match="callable"):
        loader(SimpleNamespace(TaskObjCfgDict=sentinel), env_config, 16)

    non_callable_module = SimpleNamespace(
        TaskObjCfgDict=sentinel,
        get_TaskObjCfgDict_for_eval_door_handle_height_linspace=None,
    )
    with pytest.raises(TypeError, match="callable"):
        loader(non_callable_module, env_config, 16)

    def non_dict_hook(num_envs, bounds):
        return [num_envs, bounds]

    non_dict_module = SimpleNamespace(
        TaskObjCfgDict=sentinel,
        get_TaskObjCfgDict_for_eval_door_handle_height_linspace=non_dict_hook,
    )
    with pytest.raises(TypeError, match="dict"):
        loader(non_dict_module, env_config, 16)
    assert loader(module, env_config, 16) is expected
    assert calls == [(16, [0.80, 1.05])]
    assert "env_config.config" not in SIMULATOR_SOURCE.read_text(encoding="utf-8")


def test_eval_seed_validation_and_trl_plumbing():
    validate_seed = _load_eval_seed_validator()
    assert validate_seed(0) == 0
    assert validate_seed(7) == 7
    for invalid in (True, False, 1.0, "1", None):
        with pytest.raises(TypeError):
            validate_seed(invalid)
    source = EVAL_SOURCE.read_text(encoding="utf-8")
    parse_index = source.index("parser.parse_dict(config.algo.trl)")
    seed_index = source.index("training_args.seed = int(config.seed)")
    assert seed_index > parse_index
    assert "config.seed = _validate_eval_seed(config.seed)" in source
