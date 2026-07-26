"""CPU-only v19 M42/M43 contract tests."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
ENV_CONFIG = ROOT / "gr00t/rl/config/env/door_open_a2_base.yaml"


def _raw_penalty():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "A2_ARM_DOF_OVERSPEED_HARD_FLOOR" for target in node.targets):
                nodes.append(node)
        if isinstance(node, ast.FunctionDef) and node.name == "a2_arm_dof_overspeed_raw_penalty":
            nodes.append(node)
    namespace = {"math": math, "torch": torch}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["a2_arm_dof_overspeed_raw_penalty"]


def test_m42_default_and_source_getter_are_required():
    config = yaml.safe_load(ENV_CONFIG.read_text(encoding="utf-8"))
    assert config["env"]["config"]["a2_corridor_door_wide_hinge_norm"] == 1.5
    source = SOURCE.read_text(encoding="utf-8")
    assert "A2_CORRIDOR_DOOR_WIDE_HINGE_NORM_CONFIG_KEY" in source
    assert "_get_a2_corridor_door_wide_hinge_norm()" in source
    assert "door_joint_pos[:, 0] / self._get_a2_corridor_door_wide_hinge_norm()" in source
    assert '"reward_episode_sums_unit": "episode-sum"' in source
    assert "if width >= A2_ARM_DOF_OVERSPEED_HARD_FLOOR" in source
    assert "self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx]" in source


@pytest.mark.parametrize(
    ("velocity", "expected"),
    ((2.5, 0.0), (2.75, 0.25), (2.9718, pytest.approx(0.89038, abs=1e-5)), (3.0, 1.0)),
)
def test_f2_normalized_soft_margin_formula(velocity, expected):
    raw = _raw_penalty()
    values = torch.tensor([[velocity, 0.0, 0.0, 0.0, 0.0, 0.0]], dtype=torch.float32)
    actual = raw(values, soft_margin_enabled=True, soft_margin_width=0.5)
    assert actual.item() == expected


def test_f2_sign_symmetry_multi_joint_and_gripper_exclusion_by_input_contract():
    raw = _raw_penalty()
    values = torch.tensor([[2.75, -2.75, 3.0, -3.0, 0.0, 2.5]], dtype=torch.float32)
    assert raw(values, soft_margin_enabled=True, soft_margin_width=0.5).item() == pytest.approx(2.5)
    # The helper receives only arm_j1..j6; arbitrary j7/j8 values are outside this tensor.
    assert raw(values[:, :6], soft_margin_enabled=True, soft_margin_width=0.5).shape == (1,)


@pytest.mark.parametrize("width", (0.0, -0.1, 3.0, float("nan"), float("inf")))
@pytest.mark.parametrize("soft_margin_enabled", (True, False))
def test_f2_invalid_width_fails_fast_regardless_of_selector(width, soft_margin_enabled):
    raw = _raw_penalty()
    with pytest.raises(ValueError):
        raw(torch.ones((1, 6)), soft_margin_enabled=soft_margin_enabled, soft_margin_width=width)


def test_f2_helper_uses_metadata_only_and_requires_six_arm_columns(monkeypatch):
    raw = _raw_penalty()
    monkeypatch.setattr(torch, "all", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("torch.all must not run")))
    raw(torch.ones((1, 6)), soft_margin_enabled=False, soft_margin_width=0.5)
    with pytest.raises(ValueError, match="shape .* 6"):
        raw(torch.ones((1, 5)), soft_margin_enabled=False, soft_margin_width=0.5)
    source = SOURCE.read_text(encoding="utf-8")
    assert "def _get_a2_arm_dof_velocities" not in source
    assert "torch.all(torch.isfinite(arm_dof_vel))" not in source


def test_disabled_branch_is_legacy_and_hard_floor_is_shared():
    raw = _raw_penalty()
    values = torch.tensor([[2.5, 3.0, 3.25, -3.5, 0.0, 4.0]], dtype=torch.float32)
    expected = torch.square(torch.relu(torch.abs(values) - 3.0)).sum(dim=-1)
    torch.testing.assert_close(raw(values, soft_margin_enabled=False, soft_margin_width=0.5), expected)
    source = SOURCE.read_text(encoding="utf-8")
    assert source.count("A2_ARM_DOF_OVERSPEED_HARD_FLOOR") >= 4
    assert "self.termination_level * 20.0" in source
    assert "not_just_resetted = self.episode_length_buf > 20" in source


def _production_overspeed_reward():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_reward_penalty_dof_overspeed"
    )
    namespace = {"torch": torch, "A2_ARM_DOF_OVERSPEED_HARD_FLOOR": 3.0}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["_reward_penalty_dof_overspeed"]


def test_non_a2_legacy_formula_executes_production_method_for_arbitrary_width():
    values = torch.tensor(
        [
            [2.5, 3.0, 3.25, -3.5, 0.0, 4.0, 3.1, -4.2, 0.5, 5.0, 1.0, 2.0, 3.75, -3.25],
            [-4.5, 2.0, 3.0, 3.5, -3.2, 0.1, 3.3, -3.8, 0.0, 3.05, 4.25, -2.0, 3.9, -5.0],
        ],
        dtype=torch.float32,
    )
    fake_self = SimpleNamespace(
        _use_a2_base=False,
        _upper_non_gripper_dof_idx=list(range(values.shape[1])),
        simulator=SimpleNamespace(dof_vel=values),
    )
    actual = _production_overspeed_reward()(fake_self)
    expected = torch.square(torch.clamp(torch.abs(values) - 3.0, min=0.0)).sum(dim=-1)
    torch.testing.assert_close(actual, expected)
