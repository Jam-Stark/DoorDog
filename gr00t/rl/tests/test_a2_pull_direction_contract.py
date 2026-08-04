"""CPU/no-sim tests for the immutable A2 door direction contract."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path

import pytest
import torch

from gr00t.rl.envs.door.a2_pull_direction import (
    A2DoorDirection,
    a2_pull_proof_world_offset_x,
    a2_signed_stage0_nearest_staging_target,
    a2_signed_stage0_staging_band_mask,
)


ROOT = Path(__file__).resolve().parents[3]
BASE_ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
DOOR_SOURCE = ROOT / "gr00t/rl/isaac_utils/playground/env_rand/door.py"
DOOR_MECHANICS_SHA256 = "3e170bbe9477aa9c84e9627e8d8c9f9525c4e8644deca046fb045b14284fded0"


@pytest.mark.parametrize(
    (
        "door_open_io",
        "io_sign",
        "approach_side_x",
        "travel_dir_x",
        "active_handle_face_x",
        "root_before_x",
        "root_after_x",
        "final_target_x",
    ),
    (
        ("out", -1, -1, 1, -1, -1.0, 1.0, 2.0),
        ("in", 1, 1, -1, 1, 1.0, -1.0, -2.0),
    ),
)
def test_paired_in_out_direction_contract(
    door_open_io: str,
    io_sign: int,
    approach_side_x: int,
    travel_dir_x: int,
    active_handle_face_x: int,
    root_before_x: float,
    root_after_x: float,
    final_target_x: float,
):
    direction = A2DoorDirection(door_open_io=door_open_io, door_open_lr="right")
    assert direction.io_sign == io_sign
    assert direction.door_open_lr_sign == -1
    assert direction.approach_side_x == approach_side_x
    assert direction.travel_dir_x == travel_dir_x
    assert direction.active_handle_face_x == active_handle_face_x
    assert direction.signed_distance_to_door(root_before_x) == 1.0
    assert direction.signed_crossing_progress(root_before_x) == -1.0
    assert direction.signed_crossing_progress(root_after_x) == 1.0
    assert direction.signed_velocity_toward_door(float(travel_dir_x)) == 1.0
    assert direction.signed_velocity_yield_outward(float(approach_side_x)) == 1.0
    assert direction.active_face_position_x(0.2) == active_handle_face_x * 0.1
    assert direction.pregrasp_target_x(0.0, 0.1) == approach_side_x * 0.1
    assert direction.final_target_x(0.0, 2.0) == final_target_x


def test_hinge_opening_coordinate_is_not_derived_from_io_sign():
    push = A2DoorDirection(door_open_io="out", door_open_lr="right")
    pull = A2DoorDirection(door_open_io="in", door_open_lr="right")
    assert push.door_open_lr_sign == pull.door_open_lr_sign == -1
    assert push.travel_dir_x == -pull.travel_dir_x


def test_paired_signed_staging_geometry_is_mirrored_without_changing_distances():
    target = torch.tensor([[0.0, 0.0, 0.95]])
    push_root = torch.tensor([[-0.60, 0.0, 0.55]])
    pull_root = torch.tensor([[0.60, 0.0, 0.55]])
    push = A2DoorDirection("out")
    pull = A2DoorDirection("in")

    assert a2_signed_stage0_staging_band_mask(
        push_root, target, 0.5, 0.8, 0.15, push
    ).item()
    assert a2_signed_stage0_staging_band_mask(
        pull_root, target, 0.5, 0.8, 0.15, pull
    ).item()
    torch.testing.assert_close(
        a2_signed_stage0_nearest_staging_target(
            torch.tensor([[-1.0, 0.3, 0.55]]), target, 0.5, 0.8, 0.15, push
        )[:, 0],
        torch.tensor([-0.8]),
    )
    torch.testing.assert_close(
        a2_signed_stage0_nearest_staging_target(
            torch.tensor([[1.0, 0.3, 0.55]]), target, 0.5, 0.8, 0.15, pull
        )[:, 0],
        torch.tensor([0.8]),
    )


def test_spawn_door_uses_the_io_selected_face_for_both_target_poses():
    source = DOOR_SOURCE.read_text(encoding="utf-8")
    assignment = "grasp_target_face_x = door_open_io * axle_length / 2"
    assert source.count(assignment) == 1
    target_block = source[source.index(assignment) : source.index("# set material", source.index(assignment))]
    assert target_block.count("grasp_target_face_x") == 3
    assert "Gf.Vec3f(grasp_target_face_x," in target_block
    assert "-axle_length / 2" not in target_block


def test_spawn_door_hinge_handle_and_latch_mechanics_are_byte_identical():
    source = DOOR_SOURCE.read_text(encoding="utf-8")
    start = source.index("    hinge_joint_prim_path =")
    end = source.index("    # Place the single task target", start)
    mechanics = source[start:end]
    assert hashlib.sha256(mechanics.encode("utf-8")).hexdigest() == DOOR_MECHANICS_SHA256


def test_direction_contract_is_immutable():
    direction = A2DoorDirection(door_open_io="in", door_open_lr="right")
    with pytest.raises(FrozenInstanceError):
        direction.door_open_io = "out"


def test_shared_proof_consumer_uses_world_positive_x():
    offset = a2_pull_proof_world_offset_x(
        0.006,
        batch_size=2,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    torch.testing.assert_close(offset, torch.tensor([[0.006, 0.0, 0.0]]).repeat(2, 1))


def test_production_push_anchor_consumer_passes_tensor_device_to_strict_helper():
    tree = ast.parse(BASE_ENV_SOURCE.read_text(encoding="utf-8"))
    proof_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "a2_pull_proof_world_offset_x"
    ]
    assert len(proof_calls) == 2
    for call in proof_calls:
        device_keyword = next(keyword for keyword in call.keywords if keyword.arg == "device")
        assert ast.unparse(device_keyword.value).replace("'", '"') == (
            'handle_frames["handle_quat_w"].device'
        )


def _quat_apply(quat: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
    quat_vector = quat[..., 1:]
    uv = torch.cross(quat_vector, vector, dim=-1)
    uuv = torch.cross(quat_vector, uv, dim=-1)
    return vector + 2.0 * (quat[..., :1] * uv + uuv)


def _quat_apply_inverse(quat: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
    inverse = quat.clone()
    inverse[..., 1:] *= -1.0
    return _quat_apply(inverse, vector)


def test_production_push_anchor_consumer_maps_world_positive_x_tension_not_compression():
    yaw_quarter_turn = torch.tensor(
        [[2.0**-0.5, 0.0, 0.0, 2.0**-0.5]], dtype=torch.float32
    )
    world_tension = a2_pull_proof_world_offset_x(
        0.006,
        batch_size=1,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    local_tension = _quat_apply_inverse(yaw_quarter_turn, world_tension)
    reconstructed_tension = _quat_apply(yaw_quarter_turn, local_tension)
    torch.testing.assert_close(reconstructed_tension, world_tension)
    assert reconstructed_tension[0, 0] > 0.0

    world_compression = -world_tension
    local_compression = _quat_apply_inverse(yaw_quarter_turn, world_compression)
    reconstructed_compression = _quat_apply(yaw_quarter_turn, local_compression)
    torch.testing.assert_close(reconstructed_compression, world_compression)
    assert reconstructed_compression[0, 0] < 0.0

    source = BASE_ENV_SOURCE.read_text(encoding="utf-8")
    proof_call = source.index("            proof_world_offset = a2_pull_proof_world_offset_x")
    start = source.rindex('        if cfg["pull_p1_probe_enabled"]:', 0, proof_call)
    end = source.index("        (\n            q_des,", start)
    consumer = source[start:end]
    assert consumer.count("a2_pull_proof_world_offset_x") == 2
    assert consumer.count("quat_apply_inverse") == 2
    assert "proof_world_offset = a2_pull_proof_world_offset_x" in consumer
    assert "full_world_offset = a2_pull_proof_world_offset_x" in consumer
    assert "proof_local_offset = quat_apply_inverse" in consumer
    assert "full_local_offset = quat_apply_inverse" in consumer
    assert "local_offset[proof] = proof_local_offset[proof]" in consumer
    assert "local_offset[depress] = full_local_offset[depress]" in consumer
    assert "local_offset[push] = full_local_offset[push]" in consumer


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"door_open_io": "sideways"}, "door_open_io"),
        ({"door_open_io": "in", "door_open_lr": "center"}, "door_open_lr"),
    ),
)
def test_invalid_direction_labels_fail_fast(kwargs: dict, message: str):
    with pytest.raises(ValueError, match=message):
        A2DoorDirection(**kwargs)


@pytest.mark.parametrize("value", (0.0, -0.1, float("nan"), float("inf"), True))
def test_invalid_geometry_distances_fail_fast(value: float):
    direction = A2DoorDirection(door_open_io="in")
    with pytest.raises((TypeError, ValueError)):
        direction.active_face_position_x(value)
    with pytest.raises((TypeError, ValueError)):
        direction.pregrasp_target_x(0.0, value)
    with pytest.raises((TypeError, ValueError)):
        direction.final_target_x(0.0, value)
