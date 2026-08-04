"""Behavioral boundaries for pull-v0 telemetry strata and P0-D bindings."""

from __future__ import annotations

import copy

import pytest

from gr00t.rl.envs.door import a2_pull_v0_guard as pull_guard
from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2_PULL_EVENT_NAMES,
    A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS,
    A2_PULL_HINGE_DRIVE_FORCE_BUCKET_THRESHOLD_NM,
    A2_PULL_NA,
    a2_pull_event_funnel,
    a2_pull_hinge_drive_force_bucket,
    validate_a2_pull_episode,
)
from gr00t.rl.envs.door.a2_pull_v0_guard import (
    A2_PULL_V0_RESOLVED_G4_CONFIG_PATH,
    validate_a2_pull_v0_resolved_g4_config,
)


def _episode(
    max_event: int,
    *,
    door_metadata: dict[str, bool | float],
) -> dict[str, object]:
    """Build a schema-v2 episode from synthetic door custom-data metadata."""

    event_reached = {
        event_name: event_index <= max_event
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    first_event_step = {
        event_name: event_index * 10 if event_index <= max_event else A2_PULL_NA
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    first_event_time_s = {
        event_name: event_index * 0.2 if event_index <= max_event else A2_PULL_NA
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    return {
        "event_reached": event_reached,
        "first_event_step": first_event_step,
        "first_event_time_s": first_event_time_s,
        "proof_hold_duration_s": 0.2 if max_event >= 2 else A2_PULL_NA,
        "proof_retreat_displacement_m": 0.01 if max_event >= 2 else A2_PULL_NA,
        "max_tensile_retreat_before_loss_m": 0.02 if max_event >= 2 else A2_PULL_NA,
        "hinge_at_first_positive_progress_rad": 0.01 if max_event >= 4 else A2_PULL_NA,
        "hinge_at_first_grip_loss_rad": A2_PULL_NA,
        "held_hinge_max_rad": 0.1 if max_event >= 4 else A2_PULL_NA,
        "hinge_at_release_or_hold_decision_rad": 0.1 if max_event >= 5 else A2_PULL_NA,
        "root_outward_excursion_before_clear_m": 0.1 if max_event >= 5 else A2_PULL_NA,
        "first_path_reversal_step": 60 if max_event >= 6 else A2_PULL_NA,
        "release_to_whole_body_clear_s": 0.4 if max_event >= 7 else A2_PULL_NA,
        "hinge_reclosure_after_release_rad": A2_PULL_NA,
        "body_panel_contact_steps_per_20s": 0,
        "body_panel_contact_impulse_Ns": 0.0,
        "crossing_while_valid_capture": max_event >= 6,
        "whole_body_clear": max_event >= 7,
        "terminal_reason": "episode_timeout",
        "spawn_hook": door_metadata["spawnHook"],
        "hinge_drive_max_force_nm": door_metadata["hingeDriveMaxForce"],
    }


@pytest.mark.parametrize(
    ("rng_sample", "expected_spawn_hook"),
    [(0.0, True), (0.5, False)],
)
def test_stochastic_hook_metadata_reaches_both_schema_v2_strata(
    rng_sample: float,
    expected_spawn_hook: bool,
) -> None:
    """Given deterministic p=0.5 samples, metadata exposes both hook outcomes."""

    door_metadata = {
        "spawnHook": rng_sample < 0.5,
        "hingeDriveMaxForce": A2_PULL_HINGE_DRIVE_FORCE_BUCKET_THRESHOLD_NM,
    }

    episode = _episode(4, door_metadata=door_metadata)

    validate_a2_pull_episode(episode)
    funnel = a2_pull_event_funnel([episode])

    assert episode["spawn_hook"] is expected_spawn_hook
    assert funnel[f"spawnHook={expected_spawn_hook}.count"] == 1.0


def test_event_funnel_stratifies_fake_door_metadata_by_hook_and_hinge_force_boundary() -> None:
    """Given fake metadata, the funnel keeps hook and exact-force strata independent."""

    at_threshold = _episode(
        4,
        door_metadata={"spawnHook": True, "hingeDriveMaxForce": 7.25},
    )
    above_threshold = _episode(
        1,
        door_metadata={"spawnHook": False, "hingeDriveMaxForce": 7.250001},
    )

    funnel = a2_pull_event_funnel([at_threshold, above_threshold])

    assert funnel["P(E2 | E1)"] == 0.5
    assert funnel["spawnHook=True.P(E4 | E3)"] == 1.0
    assert funnel["spawnHook=False.P(E3 | E2)"] == A2_PULL_NA
    assert funnel[f"{A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS[0]}.count"] == 1.0
    assert funnel[f"{A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS[1]}.count"] == 1.0


@pytest.mark.parametrize(
    ("force_nm", "expected_bucket"),
    [
        (7.25, A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS[0]),
        (7.250001, A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS[1]),
    ],
)
def test_hinge_drive_force_bucket_uses_the_production_threshold(
    force_nm: float,
    expected_bucket: str,
) -> None:
    """The 7.25 Nm boundary remains inclusive in its low-force bucket."""

    assert a2_pull_hinge_drive_force_bucket(force_nm) == expected_bucket


@pytest.mark.parametrize("missing_field", ["spawn_hook", "hinge_drive_max_force_nm"])
def test_schema_v2_rejects_episodes_missing_required_metadata_strata(missing_field: str) -> None:
    """Missing door-derived strata fail before the event funnel can consume them."""

    episode = _episode(
        1,
        door_metadata={"spawnHook": False, "hingeDriveMaxForce": 7.25},
    )
    del episode[missing_field]

    with pytest.raises(ValueError, match="fields must match the schema exactly"):
        validate_a2_pull_episode(episode)


def test_p0d_resolved_v20_g4_config_is_the_source_of_truth() -> None:
    """The public guard returns the exact source-frozen P0-D finger profile."""

    receipt = validate_a2_pull_v0_resolved_g4_config(A2_PULL_V0_RESOLVED_G4_CONFIG_PATH)

    assert receipt["source_config_path"] == str(A2_PULL_V0_RESOLVED_G4_CONFIG_PATH)
    assert receipt["finger_effort_n"] == (45.0, 45.0)
    assert receipt["finger_stiffness"] == (1300.0, 1300.0)
    assert receipt["finger_damping"] == (32.0, 32.0)
    assert receipt["a2_door_weight_range"] == (80.0, 160.0)


@pytest.mark.parametrize(
    ("path", "replacement", "error"),
    [
        (("env", "config", "a2_door_weight_range"), None, "requires a2_door_weight_range"),
        (("env", "config", "a2_door_weight_range"), [80.0, 120.0], "must carry a2_door_weight_range"),
        (("robot", "dof_effort_limit_list"), None, "requires dof_effort_limit_list"),
        (("robot", "control", "stiffness", "arm_j7"), 1200.0, "must bind finger effort"),
    ],
)
def test_p0d_rejects_malformed_or_mismatched_resolved_config(
    path: tuple[str, ...],
    replacement: float | list[float] | None,
    error: str,
) -> None:
    """Synthetic malformed P0-D payloads fail in the production parser."""

    source_path, source_sha256, payload = pull_guard._load_sha_verified_resolved_g4_config(None)
    mutable_payload = copy.deepcopy(payload)
    parent = mutable_payload
    for key in path[:-1]:
        parent = parent[key]
    if replacement is None:
        del parent[path[-1]]
    else:
        parent[path[-1]] = replacement

    with pytest.raises(RuntimeError, match=error):
        pull_guard._parse_resolved_g4_config(source_path, source_sha256, mutable_payload)
