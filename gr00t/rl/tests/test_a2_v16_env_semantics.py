"""Direct no-simulation v16 selector, corridor, mass, and penalty tests."""

from __future__ import annotations

import ast
import math
from collections.abc import Sequence
from numbers import Real
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[3]
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
SCENARIO_SOURCE = ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"
SIMULATOR_SOURCE = ROOT / "gr00t/rl/simulator/isaacsim/isaacsim.py"
ENV_CONFIG = ROOT / "gr00t/rl/config/env/door_open_a2_base.yaml"
V14_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v14_main.yaml"
V15_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v15_main.yaml"
V16_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v16_main.yaml"


class _FakeDoorSpawnerCfg:
    def __init__(
        self,
        door_handle_tblr,
        rand_door_handle_height=None,
        door_weight=(80.0, 120.0),
        rand_door_weight=None,
    ):
        self.door_handle_tblr = door_handle_tblr
        self.rand_door_handle_height = rand_door_handle_height
        self.door_weight = door_weight
        self.rand_door_weight = rand_door_weight

    def replace(self, **kwargs):
        return _FakeDoorSpawnerCfg(
            kwargs.get("door_handle_tblr", self.door_handle_tblr),
            kwargs.get("rand_door_handle_height", self.rand_door_handle_height),
            kwargs.get("door_weight", self.door_weight),
            kwargs.get("rand_door_weight", self.rand_door_weight),
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


def _env_helpers():
    tree = ast.parse(ENV_SOURCE.read_text(encoding="utf-8"))
    names = {"a2_corridor_hold_and_drive_component", "a2_update_corridor_latch", "a2_door_body_contact_penalty_component"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {"torch": torch, "math": math}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ENV_SOURCE), "exec"), namespace)
    return namespace


def _scenario_helpers():
    tree = ast.parse(SCENARIO_SOURCE.read_text(encoding="utf-8"))
    names = {
        "_build_eval_door_handle_height_grid",
        "_validate_eval_door_handle_height_task_obj_cfg",
        "_validate_door_weight_range",
        "_validate_eval_door_handle_height_weight_pairs",
        "_apply_door_weight_range",
        "get_TaskObjCfgDict_for_eval_door_handle_height_linspace",
        "get_TaskObjCfgDict_for_eval_door_handle_height_weight_pairs",
        "get_TaskObjCfgDict_for_door_config",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {"DoorSpawnerCfg": _FakeDoorSpawnerCfg, "Real": Real, "Sequence": Sequence, "math": math, "np": np, "sim_utils": SimpleNamespace(MultiAssetSpawnerCfg=_FakeMultiAssetSpawnerCfg)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SCENARIO_SOURCE), "exec"), namespace)
    return namespace


def test_shared_and_v16_selectors_are_explicit():
    base = OmegaConf.load(ENV_CONFIG).env.config
    v14 = OmegaConf.load(V14_CONFIG).env.config
    v15 = OmegaConf.load(V15_CONFIG).env.config
    v16 = OmegaConf.load(V16_CONFIG).env.config
    assert base.a2_corridor_enabled is False
    assert base.a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor == 0.1
    assert base.a2_door_body_contact_penalty_mode == "linear_v15"
    # Historical configs inherit these defaults from the shared env config;
    # they do not duplicate the selectors in their own override files.
    assert "a2_corridor_enabled" not in v14 and "a2_corridor_enabled" not in v15
    assert "a2_door_body_contact_penalty_mode" not in v14
    assert "a2_door_body_contact_penalty_mode" not in v15
    assert v16.a2_corridor_enabled is True
    assert v16.a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor == 0.4
    assert v16.a2_door_body_contact_penalty_mode == "quadratic_v16"
    assert list(v16.a2_door_weight_range) == [80.0, 160.0]


def test_body_penalty_dispatch_is_exact_and_fail_fast():
    helper = _env_helpers()["a2_door_body_contact_penalty_component"]
    body = torch.tensor([0.0, 10.0, 20.0, 40.0, 80.0])
    torch.testing.assert_close(helper(body, "linear_v15"), torch.tensor([0.0, 0.5, 1.0, 1.0, 1.0]))
    torch.testing.assert_close(helper(body, "quadratic_v16"), torch.tensor([0.0, 0.0625, 0.25, 1.0, 1.0]))
    with pytest.raises(ValueError, match="exactly"):
        helper(body, "quadratic")
    with pytest.raises(ValueError):
        helper(torch.tensor([float("nan")]), "linear_v15")


def test_corridor_enabled_and_disabled_components_and_latch_reset():
    helpers = _env_helpers()
    component = helpers["a2_corridor_hold_and_drive_component"]
    latch = helpers["a2_update_corridor_latch"]
    hold = torch.tensor([True, True, False])
    hinge_vel = torch.tensor([0.1, 0.4, 0.4])
    latched = torch.tensor([False, True, True])
    torch.testing.assert_close(component(hold, hinge_vel, latched, 0.1, 0.4, False), torch.tensor([1.0, 1.0, 0.0]))
    torch.testing.assert_close(component(hold, hinge_vel, latched, 0.1, 0.4, True), torch.tensor([1.0, 1.0, 0.0]))
    stage = torch.tensor([3, 4, 4], dtype=torch.long)
    hinge = torch.tensor([0.9, 1.0, 1.1])
    crossed = torch.tensor([False, False, False])
    torch.testing.assert_close(latch(latched, crossed, stage, hinge, 4, True), torch.tensor([False, True, True]))
    torch.testing.assert_close(latch(latched, crossed, stage, hinge, 4, False), torch.zeros(3, dtype=torch.bool))
    with pytest.raises(ValueError, match="bool"):
        latch(latched, crossed, stage, hinge, 4, 1)


def test_mass_override_composes_with_height_grid_and_rejects_invalid_ranges():
    helpers = _scenario_helpers()
    base = _FakeDoorSpawnerCfg((1.10, 0.80, 0.08, 0.15))
    task = {"door": _FakeDoorCfg(_FakeMultiAssetSpawnerCfg([base] * 4, False))}
    helpers["TaskObjCfgDict"] = task
    result = helpers["get_TaskObjCfgDict_for_door_config"](16, {"a2_door_weight_range": [80.0, 160.0], "a2_eval_door_handle_height_linspace": [0.80, 1.05]})
    assets = result["door"].spawn.assets_cfg
    assert len(assets) == 16 and result["door"].spawn.random_choice is False
    assert all(asset.door_weight == (80.0, 160.0) for asset in assets)
    np.testing.assert_array_equal([asset.rand_door_handle_height for asset in assets], np.linspace(0.80, 1.05, 16))
    assert task["door"].spawn.assets_cfg[0].door_weight == (80.0, 120.0)
    for invalid in (None, [80.0], [160.0, 80.0], [0.0, 160.0], [80.0, float("nan")], [True, 160.0], "80,160"):
        with pytest.raises((TypeError, ValueError)):
            helpers["_validate_door_weight_range"](invalid)


def test_explicit_height_weight_pairs_are_ordered_high_level_and_fail_fast():
    helpers = _scenario_helpers()
    base = _FakeDoorSpawnerCfg((1.10, 0.80, 0.08, 0.15))
    task = {"door": _FakeDoorCfg(_FakeMultiAssetSpawnerCfg([base] * 4, False))}
    helpers["TaskObjCfgDict"] = task
    pairs = [[0.80, 80.0], [0.80, 160.0], [1.10, 80.0], [1.10, 160.0]]
    result = helpers["get_TaskObjCfgDict_for_door_config"](
        4,
        {
            "a2_door_weight_range": [80.0, 160.0],
            "a2_eval_door_handle_height_weight_pairs": pairs,
        },
    )
    assets = result["door"].spawn.assets_cfg
    assert result["door"].spawn.random_choice is False
    assert [
        (asset.rand_door_handle_height, asset.rand_door_weight) for asset in assets
    ] == [tuple(pair) for pair in pairs]
    assert all(asset.door_weight == (80.0, 160.0) for asset in assets)
    assert task["door"].spawn.assets_cfg[0].door_weight == (80.0, 120.0)
    assert task["door"].spawn.assets_cfg[0].rand_door_handle_height is None
    assert task["door"].spawn.assets_cfg[0].rand_door_weight is None

    invalid_pairs = (
        None,
        "0.80,80.0",
        pairs[:3],
        [[0.80], *pairs[1:]],
        [[True, 80.0], *pairs[1:]],
        [[0.80, True], *pairs[1:]],
        [[float("nan"), 80.0], *pairs[1:]],
        [[0.80, float("inf")], *pairs[1:]],
        [[0.79, 80.0], *pairs[1:]],
        [[1.11, 80.0], *pairs[1:]],
        [[0.80, 79.0], *pairs[1:]],
        [[0.80, 161.0], *pairs[1:]],
    )
    for invalid in invalid_pairs:
        with pytest.raises((TypeError, ValueError)):
            helpers["get_TaskObjCfgDict_for_door_config"](
                4,
                {
                    "a2_door_weight_range": [80.0, 160.0],
                    "a2_eval_door_handle_height_weight_pairs": invalid,
                },
            )
    with pytest.raises(ValueError, match="mutually exclusive"):
        helpers["get_TaskObjCfgDict_for_door_config"](
            4,
            {
                "a2_door_weight_range": [80.0, 160.0],
                "a2_eval_door_handle_height_linspace": [0.80, 1.10],
                "a2_eval_door_handle_height_weight_pairs": pairs,
            },
        )
    with pytest.raises(ValueError, match="weight must stay within"):
        helpers["get_TaskObjCfgDict_for_door_config"](
            4,
            {"a2_eval_door_handle_height_weight_pairs": pairs},
        )
    for invalid_num_envs in (True, 0, -1, 4.0):
        with pytest.raises((TypeError, ValueError)):
            helpers["get_TaskObjCfgDict_for_eval_door_handle_height_weight_pairs"](
                invalid_num_envs,
                pairs,
                task_obj_cfg_dict=task,
            )


def test_latched_trace_fields_and_reset_source_are_explicit():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    assert '"door_hinge_joint_vel"' in source
    assert '"root_x_ever_crossed"' in source
    assert "_a2_corridor_latched[env_ids] = False" in source


def test_simulator_routes_mass_selector_hook():
    tree = ast.parse(SIMULATOR_SOURCE.read_text(encoding="utf-8"))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_get_task_obj_cfg_dict_for_door_eval")
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SIMULATOR_SOURCE), "exec"), namespace)
    calls = []
    expected = {"door": object()}
    module = SimpleNamespace(TaskObjCfgDict={"baseline": object()}, get_TaskObjCfgDict_for_door_config=lambda num_envs, env_config: calls.append((num_envs, env_config)) or expected)
    cfg = {"a2_door_weight_range": [80.0, 160.0]}
    assert namespace["_get_task_obj_cfg_dict_for_door_eval"](module, cfg, 16) is expected
    assert calls == [(16, cfg)]
    pair_cfg = {
        "a2_eval_door_handle_height_weight_pairs": [
            [0.80, 80.0],
            [0.80, 120.0],
        ]
    }
    assert namespace["_get_task_obj_cfg_dict_for_door_eval"](module, pair_cfg, 2) is expected
    assert calls[-1] == (2, pair_cfg)
