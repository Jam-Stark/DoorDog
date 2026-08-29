#!/usr/bin/env python3
"""CPU-only proof using the R2 production mapping helper and real actor layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import yaml

from gr00t.rl.envs.door.a2_v26_4_canonicalization import (
    a2_v26_4_accumulate_physical_delta,
    a2_v26_4_canonicalize_dof_values,
    a2_v26_4_canonicalize_hand_force,
    a2_v26_4_canonicalize_vector,
    a2_v26_4_map_action_coordinates,
    a2_v26_4_physical_delta_origin,
)


SCHEMA = "a2_piper_base_v26_4_r2_canonical_identity_v1"
SEAM_KEY = "env.config.a2_v26_4_side_canonicalization_enabled"
OBS_CONFIG = Path("gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml")
EXPECTED_FIELDS = (
    ("dof_pos", 20), ("relative_to_door", 9), ("dof_vel", 20), ("actions", 19),
    ("projected_gravity", 3), ("door_dof_pos", 2), ("base_lin_vel", 3),
    ("base_ang_vel", 3), ("hand_force", 6), ("stage", 6),
    ("privileged_door_info", 8), ("delta_actions", 6),
    ("gripper_handle_transform", 18), ("a2_base_command_raw", 5), ("a2_base_command", 5),
)
DOF_PERM = (6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 19, 18)
DOF_SIGNS = (-1, 1, 1, -1, 1, 1, -1, 1, 1, -1, 1, 1, -1, 1, 1, -1, 1, -1, -1, -1)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_equal(actual: torch.Tensor, expected: torch.Tensor, message: str) -> None:
    require(torch.equal(actual, expected), message)


def require_close(actual: torch.Tensor, expected: torch.Tensor, message: str) -> None:
    require(torch.allclose(actual, expected, rtol=0.0, atol=1.0e-12), message)


def mirror_dof(values: torch.Tensor) -> torch.Tensor:
    return values[:, DOF_PERM] * values.new_tensor(DOF_SIGNS)


def mirror_vector(values: torch.Tensor, signs: tuple[int, ...]) -> torch.Tensor:
    return values * values.new_tensor(signs)


def resolved_actor_fields() -> tuple[tuple[str, int], ...]:
    payload = yaml.safe_load(OBS_CONFIG.read_text(encoding="utf-8"))
    actor_order = tuple(payload["obs"]["obs_dict"]["actor_obs"])
    dims = {
        "dof_pos": 20, "relative_to_door": 9, "dof_vel": 20, "actions": 19,
        "projected_gravity": 3, "door_dof_pos": 2, "base_lin_vel": 3,
        "base_ang_vel": 3, "hand_force": 6, "stage": 6, "privileged_door_info": 8,
        "delta_actions": 6, "gripper_handle_transform": 18, "a2_base_command_raw": 5,
        "a2_base_command": 5,
    }
    require(actor_order == tuple(name for name, _ in EXPECTED_FIELDS), "resolved actor observation order changed")
    fields = tuple((name, dims[name]) for name in actor_order)
    require(fields == EXPECTED_FIELDS, "resolved actor observation dimensions changed")
    return fields


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), f"refusing to overwrite identity artifact: {args.output}")
    source = args.source.read_text(encoding="utf-8")
    require("class DoorPregrasp(\n    StagedTaskBase,\n    DeltaActionBase,\n    WarpedActionBase," in source, "DoorPregrasp MRO no longer places DeltaAction before WarpedAction")
    require("from gr00t.rl.envs.door.a2_v26_4_canonicalization import (" in source, "runtime no longer imports the production pure mapping helpers")

    fields = resolved_actor_fields()
    total = sum(dim for _, dim in fields)
    require(total == 133, f"actor observation total changed: {total}")
    torch.manual_seed(26_4)
    batch = 3
    right_mask = torch.ones(batch, dtype=torch.bool)
    default_full = torch.tensor([[0.0] * 12 + [0.0, 0.0, 0.0, 0.25, 0.5, 1.57, 0.0, 0.0]], dtype=torch.float64)
    default_arm = default_full[:, 12:18]

    left_q = torch.randn(batch, 20, dtype=torch.float64)
    right_q = mirror_dof(left_q)
    left_dof = left_q - default_full
    right_dof = a2_v26_4_canonicalize_dof_values(right_q, right_mask) - default_full
    require_equal(right_dof, left_dof, "actual DOF helper does not canonicalize RIGHT")
    require_equal(mirror_dof(mirror_dof(left_q)), left_q, "DOF mirror is not involutive")

    left_full_action = torch.randn(batch, 24, dtype=torch.float64)
    left_full_action[:, 10] = 15.0
    right_full_action = a2_v26_4_map_action_coordinates(left_full_action, right_mask, default_arm, 0.25, canonical_to_physical=True)
    require_close(a2_v26_4_map_action_coordinates(right_full_action, right_mask, default_arm, 0.25, canonical_to_physical=False), left_full_action, "production action mapping does not round-trip")
    physical_origin = a2_v26_4_physical_delta_origin(left_full_action, right_mask, default_arm, 0.25)
    stage0 = torch.tensor([True, False, False])
    physical_clipped = a2_v26_4_accumulate_physical_delta(
        physical_origin,
        left_full_action[:, 5:11],
        left_full_action,
        right_mask,
        default_arm,
        0.25,
        1.0,
        15.0,
        stage0,
    )
    recovered_full = torch.zeros_like(left_full_action)
    recovered_full[:, 5:11] = physical_clipped
    recovered_after_physical_clip = a2_v26_4_map_action_coordinates(recovered_full, right_mask, default_arm, 0.25, canonical_to_physical=False)[:, 5:11]
    require_equal(physical_clipped[1:, 5], torch.full((batch - 1,), -15.0, dtype=torch.float64), "physical j6 clip did not apply at configured bound")
    require_equal(recovered_after_physical_clip[0, 5:6], torch.zeros(1, dtype=torch.float64), "stage0 canonical delta was not reset")
    require_close(recovered_after_physical_clip[1:, 5], torch.full((batch - 1,), 2.44, dtype=torch.float64), "physical j6 clip did not recover canonical action coordinate")
    require_equal(physical_clipped[0], physical_origin[0], "stage0 delta origin was not restored")
    require(torch.any(physical_clipped[1] != physical_origin[1]), "stage1 physical increment was overwritten by stage0 override")
    physical_reset = a2_v26_4_map_action_coordinates(torch.zeros_like(left_full_action), right_mask, default_arm, 0.25, canonical_to_physical=True)[:, 5:11]
    require_equal(physical_reset[:, 3], torch.full((batch,), -2.0, dtype=torch.float64), "RIGHT arm_j4 physical reset origin changed")
    require_close(physical_reset[:, 5], torch.full((batch,), -12.56, dtype=torch.float64), "RIGHT arm_j6 physical reset origin changed")

    polar = torch.randn(batch, 3, dtype=torch.float64)
    axial = torch.randn(batch, 3, dtype=torch.float64)
    relative = torch.randn(batch, 9, dtype=torch.float64)
    left_vel = torch.randn(batch, 20, dtype=torch.float64)
    transform = torch.randn(batch, 18, dtype=torch.float64)
    force = torch.randn(batch, 6, dtype=torch.float64)
    right_relative = a2_v26_4_canonicalize_vector(mirror_vector(relative, (1, -1, 1, 1, -1, 1, 1, -1, 1)), right_mask, (1, -1, 1, 1, -1, 1, 1, -1, 1))
    right_vel = a2_v26_4_canonicalize_dof_values(mirror_dof(left_vel), right_mask)
    right_transform = a2_v26_4_canonicalize_vector(mirror_vector(transform, (1, -1, 1, -1, 1, -1, 1, -1, 1) * 2), right_mask, (1, -1, 1, -1, 1, -1, 1, -1, 1) * 2)
    right_force_physical = force[:, (3, 4, 5, 0, 1, 2)] * force.new_tensor((1, -1, 1, 1, -1, 1))
    right_force = a2_v26_4_canonicalize_hand_force(right_force_physical, right_mask)
    require_equal(right_relative, relative, "actual relative-door helper does not canonicalize RIGHT")
    require_equal(right_vel, left_vel, "actual DOF velocity helper does not canonicalize RIGHT")
    require_equal(right_transform, transform, "actual gripper-transform helper does not canonicalize RIGHT")
    require_equal(right_force, force, "hand-force body swap/polar map is not involutive")

    left_privileged = torch.cat((torch.randn(batch, 5, dtype=torch.float64), torch.tensor([[1.0, 0.0]] * batch, dtype=torch.float64), torch.randn(batch, 1, dtype=torch.float64)), dim=-1)
    right_privileged = left_privileged.clone()
    right_privileged[:, 5:7] = torch.tensor([0.0, 1.0], dtype=torch.float64)
    left_parts = (left_dof, relative, left_vel, torch.cat((left_full_action[:, 12:], left_full_action[:, 5:11], left_full_action[:, 11:12]), dim=-1), polar, torch.randn(batch, 2, dtype=torch.float64), polar, axial, force, torch.randn(batch, 6, dtype=torch.float64), left_privileged, torch.randn(batch, 6, dtype=torch.float64), transform, left_full_action[:, :5], left_full_action[:, :5])
    right_parts = (right_dof, right_relative, right_vel, torch.cat((left_full_action[:, 12:], left_full_action[:, 5:11], left_full_action[:, 11:12]), dim=-1), a2_v26_4_canonicalize_vector(mirror_vector(polar, (1, -1, 1)), right_mask, (1, -1, 1)), left_parts[5], a2_v26_4_canonicalize_vector(mirror_vector(polar, (1, -1, 1)), right_mask, (1, -1, 1)), a2_v26_4_canonicalize_vector(mirror_vector(axial, (-1, 1, -1)), right_mask, (-1, 1, -1)), right_force, left_parts[9], right_privileged, left_parts[11], right_transform, left_full_action[:, :5], a2_v26_4_canonicalize_vector(mirror_vector(left_full_action[:, :5], (1, -1, -1, 1, -1)), right_mask, (1, -1, -1, 1, -1)))
    left_obs, right_obs = torch.cat(left_parts, dim=-1), torch.cat(right_parts, dim=-1)
    require(tuple(left_obs.shape) == (batch, total) and torch.all(torch.isfinite(left_obs)) and torch.all(torch.isfinite(right_obs)), "real actor fixture shape/finite contract failed")
    continuous = torch.ones(total, dtype=torch.bool)
    continuous[96:98] = False
    require_equal(left_obs[:, continuous], right_obs[:, continuous], "real 133D continuous identity modulo side label failed")
    require_equal(right_obs[:, 96:98], right_privileged[:, 5:7], "side one-hot was not preserved")

    start = 0
    slices = {}
    for name, dim in fields:
        slices[name] = [start, start + dim]
        start += dim
    payload = {
        "schema": SCHEMA, "status": "STATIC_IDENTITY_COMPLETE", "typed_outcome": "CANONICAL_IDENTITY_PROOF_PASS", "proof_result": "PASS", "implemented": True, "evidence_level": "STATIC_PASS", "seam_key": SEAM_KEY,
        "source": str(args.source.resolve()), "actor_obs_dim": total,
        "actor_obs_fields": [{"name": name, "slice": slices[name], "dim": dim} for name, dim in fields],
        "checks": {"resolved_133d_order": "PASS", "actual_mro_and_production_helper": "PASS", "mirror_squared": "PASS", "continuous_identity_modulo_side_label": "PASS", "side_one_hot_preserved": "PASS", "stage0_origin_stage1_to5_increment_survives": "PASS", "physical_delta_clip_reset_and_roundtrip": "PASS", "frame_transformer_target_reference_modified": False},
        "not_a_runtime_or_training_claim": "CPU static fixture only; no IsaacSim, GPU, training, or FrameTransformer target-reference correction was run.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
