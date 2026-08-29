#!/usr/bin/env python3
"""Static R2 audit of active A2 training orientation-reference construction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/AUDIT"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def source(path: str) -> str:
    candidate = REPO_ROOT / path
    require(candidate.is_file(), f"missing audited source: {candidate}")
    return candidate.read_text(encoding="utf-8")


def line_of(text: str, needle: str, label: str) -> int:
    offset = text.find(needle)
    require(offset >= 0, f"missing audited construct: {label}")
    return text[:offset].count("\n") + 1


def ref(path: str, line: int, detail: str) -> dict[str, object]:
    return {"path": path, "line": line, "detail": detail}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()

    launcher_path = "scriptsFORhuman/v26_4/run_base_v26_4_train_cell.sh"
    exp_path = "gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml"
    env_path = "gr00t/rl/config/env/door_open_a2_base.yaml"
    ablation_path = "gr00t/rl/config/ablation/wbmanip/base_v26_4_bilateral_grasp_foundation.yaml"
    door_path = "gr00t/rl/isaac_utils/playground/env_rand/door.py"
    env_source_path = "gr00t/rl/envs/door/door_open_a2_base.py"

    launcher = source(launcher_path)
    exp = source(exp_path)
    env_config = source(env_path)
    ablation = source(ablation_path)
    door = source(door_path)
    env_source = source(env_source_path)

    launcher_exp_line = line_of(launcher, "+exp=wbmanip/door_open_a2_base_lstm", "v26-4 train exp selector")
    launcher_ablation_line = line_of(launcher, "+ablation=\"$ablation\"", "v26-4 train ablation selector")
    exp_env_line = line_of(exp, "- /env: door_open_a2_base", "A2 experiment environment selection")
    exp_a2_line = line_of(exp, "use_a2_base: True", "A2 experiment mode")
    env_target_line = line_of(env_config, 'target_obj_transform_sub_prim_path: "grasp_target"', "A2 grasp-target transform selection")
    bilateral_line = line_of(ablation, "a2_v26_door_open_lr: bilateral", "v26-4 bilateral side selection")

    grasp_target_identity = """        grasp_target_prim_path,
        (
            -axle_length / 2,
            (half_door_width - door_handle_width - handle_length / 2) * door_open_lr,
            door_handle_height,
        ),
        (0, 0, 0),
        (1.0, 1.0, 1.0),
"""
    grasp_identity_line = line_of(door, grasp_target_identity, "side-independent grasp_target identity rotation")
    handle_local_rot_line = line_of(
        door,
        "if door_open_lr == -1:\n        handle_joint.CreateLocalRot0Attr().Set(Gf.Quatf(real=0.0, imaginary=(Gf.Vec3f(0, 0, 1))))",
        "RIGHT handle LocalRot0 geometry",
    )

    transformer_target_line = line_of(
        env_source,
        'prim_path="/World/envs/env_.*/door/grasp_target",',
        "Piper FrameTransformer grasp target prim",
    )
    target_offset = "rot=(0.5, 0.5, 0.5, 0.5),"
    first_target_offset = line_of(env_source, target_offset, "Piper handle target quaternion offset")
    require(env_source.count(target_offset) == 2, "Piper handle/pregrasp target offsets must contain exactly two shared quaternion constants")
    source_offset_line = line_of(
        env_source,
        "source_frame_offset=OffsetCfg(\n                        pos=(0.0, 0.0, self._get_a2_gripper_source_tcp_offset_z()),\n                        rot=(1.0, 0.0, 0.0, 0.0),",
        "Piper TCP source offset",
    )

    orientation_metric_line = line_of(
        env_source,
        "q_target_source = target_quat_source[:, 1, :]",
        "orientation reward reference read",
    )
    orientation_reward_line = line_of(
        env_source,
        "def _reward_gripper_handle_orientation(self):",
        "active A2 orientation reward consumer",
    )
    stage1_line = line_of(
        env_source,
        "def _get_a2_stage1_pregrasp_ready_mask(self):",
        "stage1 orientation-gated consumer",
    )
    stage2_line = line_of(
        env_source,
        "def _get_a2_stage2_close_reward_gate(self):",
        "stage2 orientation-gated consumer",
    )
    observation_line = line_of(
        env_source,
        "def _get_obs_gripper_handle_transform(self):",
        "actor observation orientation consumer",
    )

    a2_palm_left_line = line_of(
        env_source,
        "self.left_hand_palm_side_direction = torch.tensor(\n            [1.0, 0.0, 0.0, 0.0], device=self.device\n        )",
        "A2 left palm-side identity quaternion",
    )
    a2_palm_right_line = line_of(
        env_source,
        "self.right_hand_palm_side_direction = torch.tensor(\n            [1.0, 0.0, 0.0, 0.0], device=self.device\n        )",
        "A2 right palm-side identity quaternion",
    )
    a2_grasp_branch_line = line_of(env_source, "if self._use_a2_base:\n            forces_w = self._get_a2_gripper_handle_contact_forces()", "A2 grasp reward branch")
    legacy_palm_consumer_line = line_of(env_source, "left_palm_side_repeat = torch.tile(", "legacy G1 palm-side consumer")
    require(a2_grasp_branch_line < legacy_palm_consumer_line, "A2 grasp branch must precede legacy palm-side consumer")

    artifact = {
        "schema": "a2_piper_base_v26_4_r2_training_orientation_reference_audit_v1",
        "status": "STATIC_AUDIT_COMPLETE",
        "typed_outcome": "SIDE_INDEPENDENT_ORIENTATION_REFERENCE_FOUND_AT_piper_gripper_handle_frame_transformer_target_offsets",
        "evidence_level": "STATIC_PASS",
        "scope": "R2 read-only trace of the v26-4 A2 training source/config path; no IsaacSim or GPU execution.",
        "resolved_training_path": [
            ref(launcher_path, launcher_exp_line, "launches train_agent_trl with the A2 LSTM experiment"),
            ref(launcher_path, launcher_ablation_line, "selects the registered v26-4 ablation"),
            ref(exp_path, exp_env_line, "resolves the DoorPregrasp A2 environment"),
            ref(exp_path, exp_a2_line, "enables the A2 high-level path"),
            ref(env_path, env_target_line, "binds target transform to door/grasp_target"),
            ref(ablation_path, bilateral_line, "requires bilateral LEFT/RIGHT fixture construction"),
        ],
        "sites": [
            {
                "site_id": "piper_gripper_handle_frame_transformer_target_offsets",
                "classification": "ACTIVE_SIDE_INDEPENDENT_ORIENTATION_REFERENCE",
                "reference_value_wxyz": [0.5, 0.5, 0.5, 0.5],
                "references": [
                    ref(env_source_path, transformer_target_line, "both target frames attach to the same door/grasp_target prim"),
                    ref(env_source_path, first_target_offset, "handle and pregrasp each use the same constant quaternion offset; count is exactly two"),
                ],
                "consumers": [
                    ref(env_source_path, orientation_metric_line, "reads target_quat_source for the pregrasp orientation metric"),
                    ref(env_source_path, orientation_reward_line, "active staged gripper_handle_orientation reward"),
                    ref(env_source_path, stage1_line, "stage1 advance requires orientation alignment"),
                    ref(env_source_path, stage2_line, "stage2 close reward gate requires orientation alignment"),
                    ref(env_source_path, observation_line, "actor gripper_handle_transform observation emits both target rotations"),
                ],
                "scientific_impact": "The active A2 reward, stage transitions, and actor observation consume a target orientation whose configured offset is identical for LEFT and RIGHT. This is a concrete side-independent reference in the training path, so bilateral causal conclusions require a corrected geometry-derived R2 reference before interpretation.",
            },
            {
                "site_id": "door_grasp_target_identity_rotation",
                "classification": "UPSTREAM_SIDE_INDEPENDENT_ORIENTATION_CONSTRUCTION",
                "reference_value_euler_deg": [0, 0, 0],
                "references": [
                    ref(door_path, grasp_identity_line, "grasp_target position mirrors in y through door_open_lr but its authored rotation is identity"),
                    ref(door_path, handle_local_rot_line, "RIGHT handle geometry carries a distinct LocalRot0 Rz(pi) convention"),
                ],
                "consumers": [
                    ref(env_source_path, transformer_target_line, "the active Piper transformer targets this grasp_target prim"),
                ],
                "scientific_impact": "The upstream target construction does not itself derive a side-conditioned target rotation from the handle's LocalRot0 convention. Together with the constant active offsets, this is the source-level mismatch that R2 must correct; this audit does not modify it.",
            },
            {
                "site_id": "a2_palm_side_direction_identity",
                "classification": "SIDE_INDEPENDENT_BUT_INACTIVE_IN_A2_GRASP_REWARD",
                "reference_value_wxyz": [1.0, 0.0, 0.0, 0.0],
                "references": [
                    ref(env_source_path, a2_palm_left_line, "A2 left palm-side direction is identity"),
                    ref(env_source_path, a2_palm_right_line, "A2 right palm-side direction is identity"),
                ],
                "consumers": [
                    ref(env_source_path, a2_grasp_branch_line, "A2 reward returns through source_quat_w-based contact force computation before legacy palm use"),
                    ref(env_source_path, legacy_palm_consumer_line, "palm-side quaternion is consumed only by the subsequent non-A2 legacy branch"),
                ],
                "scientific_impact": "The equal A2 palm values are recorded for completeness, but they are not the active A2 grasp-reward orientation reference and are not used to support the typed finding.",
            },
            {
                "site_id": "piper_tcp_source_offset",
                "classification": "SIDE_INVARIANT_LOCAL_TCP_OFFSET_NOT_A_FOUND_DEFECT",
                "reference_value_wxyz": [1.0, 0.0, 0.0, 0.0],
                "references": [
                    ref(env_source_path, source_offset_line, "the local TCP offset is identity in the physical single-arm source frame"),
                ],
                "consumers": [],
                "scientific_impact": "This local source-frame offset follows the single A2 arm and is not treated as a fixed world/door orientation reference.",
            },
        ],
        "r1_runtime_corroboration": {
            "artifact": "logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/K/k_kinematics.json",
            "observation": "R1 recorded the same tcp_target_orientation_world_wxyz [0.5, 0.5, 0.5, 0.5] for LEFT and RIGHT; this corroborates but does not upgrade the present training-path audit beyond STATIC_PASS.",
        },
        "not_a_policy_claim": "The audit finds an active orientation-reference defect candidate. It does not establish training performance, policy causality, or a corrected reference; those require the independently gated R2 K runtime evidence.",
        "r2_action": "Input to v26-5/R2 follow-on correction only. No source, reward, config, threshold, gain, or URDF change is made by this audit.",
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    output_path = args.output_root / "training_orientation_reference_audit.json"
    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(artifact, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"artifact": str(output_path), "typed_outcome": artifact["typed_outcome"]}, sort_keys=True))


if __name__ == "__main__":
    main()
