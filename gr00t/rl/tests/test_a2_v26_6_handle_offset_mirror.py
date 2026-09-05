"""Bilateral handle/pregrasp target-offset mirror contract."""

import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from gr00t.rl.envs.door.a2_v26_6_handle_offset_mirror import (
    a2_v26_6_mirror_quat_wxyz,
)


ROOT = Path(__file__).resolve().parents[3]
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
AUTHORED_OFFSET_WXYZ = (0.5, 0.5, 0.5, 0.5)
PULL_OFFSET_WXYZ = (-0.5, -0.5, 0.5, 0.5)
MIRROR = np.diag([1.0, -1.0, 1.0])
HALF_TURN_TOL_DEG = 1e-3


def rot_from_wxyz(q):
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def angle_between(a, b):
    return np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))


def random_unit_quats(n, seed):
    rng = np.random.default_rng(seed)
    q = rng.normal(size=(n, 4))
    return q / np.linalg.norm(q, axis=1, keepdims=True)


def _side_mirrored_offset_method(door_metadata):
    tree = ast.parse(ENV_SOURCE.read_text(encoding="utf-8"))
    transformer = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "OrderedTargetFrameTransformer"
    )
    method = next(
        node
        for node in transformer.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_a2_v26_6_side_mirrored_offset_quaternions"
    )
    namespace = {
        "torch": torch,
        "omni": SimpleNamespace(
            usd=SimpleNamespace(
                get_context=lambda: SimpleNamespace(
                    get_stage=lambda: _FakeStage(door_metadata)
                )
            )
        ),
        "a2_v26_6_mirror_quat_wxyz": a2_v26_6_mirror_quat_wxyz,
    }
    module = ast.Module(body=[method], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(ENV_SOURCE), "exec"), namespace)
    return namespace[method.name]


class _FakeDoorPrim:
    def __init__(self, metadata):
        self._metadata = metadata

    def IsValid(self):
        return True

    def GetPrim(self):
        return self

    def GetMetadata(self, name):
        assert name == "customData"
        return self._metadata


class _FakeStage:
    def __init__(self, door_metadata):
        self._doors = [_FakeDoorPrim(metadata) for metadata in door_metadata]

    def GetPrimAtPath(self, path):
        env_id = int(path.split("env_", 1)[1].split("/", 1)[0])
        return self._doors[env_id]


def _transformer(offsets):
    return SimpleNamespace(
        _target_frame_names=["handle", "pregrasp"],
        _target_frame_offset_quat=torch.tensor(offsets, dtype=torch.float32),
        _num_envs=len(offsets) // 2,
    )


def test_mirror_helper_matches_the_conjugated_rotation():
    for q in random_unit_quats(512, seed=0):
        got = rot_from_wxyz(a2_v26_6_mirror_quat_wxyz(q))
        want = MIRROR @ rot_from_wxyz(q) @ MIRROR
        assert np.allclose(got, want, atol=1e-9)


def test_mirror_is_an_involution():
    for q in random_unit_quats(256, seed=1):
        twice = a2_v26_6_mirror_quat_wxyz(a2_v26_6_mirror_quat_wxyz(q))
        assert np.allclose(rot_from_wxyz(twice), rot_from_wxyz(q), atol=1e-9)


@pytest.mark.parametrize("offset", [AUTHORED_OFFSET_WXYZ, PULL_OFFSET_WXYZ])
def test_authored_offset_is_180_degrees_from_its_mirror(offset):
    authored = rot_from_wxyz(offset)
    mirrored = rot_from_wxyz(a2_v26_6_mirror_quat_wxyz(offset))
    assert angle_between(authored, mirrored) == pytest.approx(180.0, abs=HALF_TURN_TOL_DEG)


def test_all_right_offsets_are_bit_identical_noop():
    method = _side_mirrored_offset_method([{"doorOpenLR": -1.0}, {"doorOpenLR": -1.0}])
    transformer = _transformer([PULL_OFFSET_WXYZ] * 4)
    result = method(transformer)
    assert torch.equal(result, transformer._target_frame_offset_quat)


def test_invalid_per_env_door_open_lr_fails_fast():
    method = _side_mirrored_offset_method([{"doorOpenLR": 0.0}])
    transformer = _transformer([AUTHORED_OFFSET_WXYZ] * 2)
    with pytest.raises(RuntimeError, match="doorOpenLR in \\{-1, \\+1\\}"):
        method(transformer)


def test_source_wires_enabled_config_into_transformer_initialization():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    assert "a2_v26_6_side_mirrored_handle_offset_enabled=(" in source
    assert "self._a2_v26_6_side_mirrored_handle_offset_enabled()" in source
