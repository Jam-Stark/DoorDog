"""Prepare the v23 source record and static P0 contracts.

This command only reads source/config files and emits a small JSON object.  It
does not boot IsaacLab, launch a trainer, or create an evaluation directory.
Use ``--out`` when a caller intentionally wants to save the resulting record.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from ._v23_common import (
    REPO_ROOT,
    V23_D0_SOURCE_CONFIG,
    V23_D0_SOURCE_FACTS,
    V23_D0_SOURCE_RESOLVED_CONFIG,
    V23_WARM_START_PATH,
    V23_WARM_START_CONFIG,
    V23Error,
    artifact_payload,
    emit_payload,
    read_yaml,
    source_identity,
)


SOURCE_PATHS = (
    V23_WARM_START_PATH,
    V23_WARM_START_CONFIG,
    V23_D0_SOURCE_CONFIG,
    "gr00t/rl/isaac_utils/playground/env_rand/door.py",
    "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py",
    "gr00t/rl/envs/base_task/a2_base.py",
)


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def build_source_record() -> dict[str, Any]:
    """Read the warm source and resolve the D0 weight range exactly."""

    identity = source_identity(SOURCE_PATHS)
    resolved = read_yaml(REPO_ROOT / V23_D0_SOURCE_RESOLVED_CONFIG)
    configured_weight = _nested(resolved, "env", "config", "a2_door_weight_range")
    if configured_weight is None:
        configured_weight = resolved.get("a2_door_weight_range")
    if configured_weight != [80.0, 160.0]:
        raise V23Error(
            "D0 source must expose the G1 saved weight range [80.0, 160.0]; "
            f"got {configured_weight!r}"
        )

    facts = {name: dict(value) for name, value in V23_D0_SOURCE_FACTS.items()}
    facts["door_weight_kg"] = {
        "value": list(configured_weight),
        "authority": "G1_SAVED_CONFIG",
        "source_path": V23_D0_SOURCE_RESOLVED_CONFIG,
        "source_field": "env.config.a2_door_weight_range",
    }
    facts["handle_height_m"]["source_path"] = "gr00t/rl/isaac_utils/playground/env_rand/door.py"
    facts["handle_height_m"]["source_field"] = "DoorSpawnerCfg.door_handle_tblr"
    facts["hinge_max_force_nm"]["source_path"] = (
        "gr00t/rl/isaac_utils/playground/env_rand/door.py"
    )
    facts["hinge_max_force_nm"]["source_field"] = "DoorSpawnerCfg.hinge_drive_max_force_range"
    facts["hinge_damping_native"]["source_path"] = (
        "gr00t/rl/isaac_utils/playground/env_rand/door.py"
    )
    facts["hinge_damping_native"]["source_field"] = "DoorSpawnerCfg._resolve_hinge_damping"
    facts["hinge_stiffness_native"]["source_path"] = (
        "gr00t/rl/isaac_utils/playground/env_rand/door.py"
    )
    facts["hinge_stiffness_native"]["source_field"] = "DoorSpawnerCfg._resolve_hinge_stiffness"

    return artifact_payload(
        "source_record",
        status="STATIC_SOURCE_LOCK",
        identity=identity,
        warm_start={
            "checkpoint_path": V23_WARM_START_PATH,
            "saved_config_path": V23_WARM_START_CONFIG,
            "load_mode": "policy_only",
            "alternates": [
                "logs_rl/a2_piper_full_stage_a2_base/base_v22/G4/model_step_001750.pt",
                "logs_rl/a2_piper_full_stage_a2_base/base_v22/G5/model_step_000750.pt",
            ],
        },
        d0={
            "source_config_path": V23_D0_SOURCE_CONFIG,
            "resolved_config_path": V23_D0_SOURCE_RESOLVED_CONFIG,
            "source_facts": facts,
            "regime_definition": "G1_saved_config_only; no v22 Wave-2 mixture",
        },
        action_semantics={
            "high_level_action_dim": 12,
            "base_command_dim": 5,
            "base_command_layout": ["x", "y", "yaw", "pitch", "roll"],
            "raw_posture_indices": {"pitch": 3, "roll": 4},
            "body_pitch_roll_scale_rad": 0.4,
            "rp0_neutral_value": 0.0,
            "verification_state": "SOURCE_READ_STATIC; RUNTIME_NOT_RUN",
        },
        kp_clip_contract={
            "body_pitch_roll_scale_rad": 0.4,
            "high_level_action_clip": 1.0,
            "frozen_a2_command_scale": 0.25,
            "nominal_pd_torque_field": "computed_torque",
            "clipped_command_torque_field": "applied_torque",
            "tracking_error_field": "arm_tracking_error",
            "authority": "ESTIMATE_ONLY",
            "source_paths": [
                "gr00t/rl/envs/base_task/a2_base.py",
                "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py",
                "gr00t/rl/envs/door/door_open_a2_base.py",
            ],
            "status": "P0.3_NOT_RUN_PENDING",
        },
        p0_numeric_state="NOT_RUN_PENDING",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="optional JSON path; omitted means print the static record",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="read and validate source paths without emitting a record",
    )
    args = parser.parse_args(argv)
    payload = build_source_record()
    if args.check_only:
        print("STATIC_SOURCE_LOCK_OK")
    else:
        emit_payload(payload, args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 SOURCE PREPARE FAIL: {exc}")
