"""Schema and event-funnel contracts for A2+Piper pull-v0 evidence."""

from __future__ import annotations

import math
from enum import IntEnum
from numbers import Integral, Real
from typing import Any, Mapping, Sequence

import torch


A2_PULL_TELEMETRY_SCHEMA_VERSION = "a2_piper_pull_telemetry_v2"
A2_PULL_NA = "N/A"
A2_PULL_ESTIMATE_ONLY = "ESTIMATE_ONLY"
A2_PULL_HINGE_DRIVE_FORCE_BUCKET_THRESHOLD_NM = 7.25
A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS = (
    "hingeDriveMaxForceNm<=7.25Nm",
    "hingeDriveMaxForceNm>7.25Nm",
)
A2_PULL_V5_PERSISTENT_RELEASE_STREAK_STEPS = 25
A2_PULL_V5_RELEASE_HINGE_THRESHOLD_RAD = 1.60
A2_PULL_V5_RELEASE_TUCK_DURATION_S = 1.0


class A2PullEvent(IntEnum):
    """Authoritative physical-event order for pull-v0."""

    E0_RESET_VALID = 0
    E1_OUTSIDE_FACE_PREGRASP = 1
    E2_TENSILE_CAPTURE = 2
    E3_LATCH_RELEASE = 3
    E4_POSITIVE_HINGE_RETAINED = 4
    E5_CLEARANCE_DECISION = 5
    E6_PATH_REVERSAL_ENTRY = 6
    E7_WHOLE_BODY_CLEAR = 7


A2_PULL_EVENT_NAMES = tuple(event.name for event in A2PullEvent)
A2_PULL_PRE_E0 = "PRE_E0"
# E3 is a report-only shaping label in the v1 hard-gate route.  It remains in
# the schema, but it is intentionally not a predecessor of E4.
A2_PULL_HARD_GATE_EVENT_PREDECESSORS: tuple[int | None, ...] = (
    None,
    A2PullEvent.E0_RESET_VALID,
    A2PullEvent.E1_OUTSIDE_FACE_PREGRASP,
    None,
    A2PullEvent.E2_TENSILE_CAPTURE,
    A2PullEvent.E4_POSITIVE_HINGE_RETAINED,
    A2PullEvent.E5_CLEARANCE_DECISION,
    A2PullEvent.E6_PATH_REVERSAL_ENTRY,
)

A2_PULL_CONTROL_STEP_UNITS = {
    "door_open_io_sign": "unitless",
    "door_open_lr_sign": "unitless",
    "active_handle_face_x_sign": "unitless",
    "travel_dir_x": "unitless",
    "stage": "integer",
    "event_state": "enum",
    "root_x_rel_door_m": "m",
    "signed_crossing_progress_m": "m",
    "root_velocity_toward_door_mps": "m/s",
    "root_velocity_yield_outward_mps": "m/s",
    "root_velocity_final_travel_mps": "m/s",
    "root_yaw_error_rad": "rad",
    "handle_position_rad": "rad",
    "handle_velocity_radps": "rad/s",
    "latch_position_m": "m",
    "hinge_position_rad": "rad",
    "hinge_velocity_radps": "rad/s",
    "target_tcp_position_error_m": "m",
    "target_tcp_orientation_error_rad": "rad",
    "bilateral_handle_contact": "bool",
    "hook_contact": "bool_or_N/A",
    "handle_local_slip_xyz_mps": "m/s",
    "gripper_handle_separation_m": "m",
    "finger_pd_effort_estimate_N": "N",
    "finger_effort_utilization_estimate": "ratio",
    "arm_pd_effort_utilization_estimate": "ratio",
    "panel_contact_force_by_body_N": "N",
    "frame_contact_force_by_body_N": "N",
    "minimum_panel_robot_clearance_m": "m_or_N/A",
    "reward_component_raw": "per_control_step",
}

A2_PULL_ESTIMATE_ONLY_FIELDS = (
    "finger_pd_effort_estimate_N",
    "finger_effort_utilization_estimate",
    "arm_pd_effort_utilization_estimate",
)

A2_PULL_EPISODE_UNITS = {
    "first_event_step": "control_step_or_N/A",
    "first_event_time_s": "s_or_N/A",
    "proof_hold_duration_s": "s_or_N/A",
    "proof_retreat_displacement_m": "m_or_N/A",
    "max_tensile_retreat_before_loss_m": "m_or_N/A",
    "hinge_at_first_positive_progress_rad": "rad_or_N/A",
    "hinge_at_first_grip_loss_rad": "rad_or_N/A",
    "held_hinge_max_rad": "rad_or_N/A",
    "hinge_at_release_or_hold_decision_rad": "rad_or_N/A",
    "root_outward_excursion_before_clear_m": "m_or_N/A",
    "first_path_reversal_step": "control_step_or_N/A",
    "release_to_whole_body_clear_s": "s_or_N/A",
    "hinge_reclosure_after_release_rad": "rad_or_N/A",
    "body_panel_contact_steps_per_20s": "count",
    "body_panel_contact_impulse_Ns": "N*s",
    "crossing_while_valid_capture": "bool",
    "whole_body_clear": "bool",
    "terminal_reason": "enum",
}
A2_PULL_EPISODE_STRATIFICATION_UNITS = {
    "spawn_hook": "bool",
    "hinge_drive_max_force_nm": "N*m",
}

A2_PULL_V6_CONTROL_EXTENSION_UNITS = {
    "stage4_subphase": "integer",
    "pivot_valid": "bool",
    "pivot_displacement_m": "m_or_N/A",
    "handle_y_current_m": "m_or_N/A",
    "handle_y_capture_m": "m_or_N/A",
    "handle_crossed": "bool",
    "release_side_qualified": "bool",
    "handoff_active": "bool",
    "handoff_reached": "bool",
    "handoff_active_steps": "count",
    "positive_arm_tangent_mps": "m/s",
    "positive_base_tangent_mps": "m/s",
    "positive_total_tangent_mps": "m/s",
    "arm_tangent_share": "ratio",
    "arc_error_m": "m_or_N/A",
    "arc_quality": "ratio",
    "panel_clearance_m": "m_or_N/A",
    "workspace_margin": "ratio_or_N/A",
    "frame_lateral_delta_y_m": "m_or_N/A",
    "frame_lateral_deficit_m": "m_or_N/A",
    "passage_ready": "bool",
    "release_ready": "bool",
    "release_event": "bool",
    "clean_release": "bool",
    "release_quality": "ratio",
    "release_persistence_steps": "count",
    "hinge_at_release_rad": "rad_or_N/A",
    "hinge_velocity_at_release_radps": "rad/s_or_N/A",
    "root_yaw_delta_rad": "rad_or_N/A",
}


def validate_a2_pull_v6_control_extension(record: Mapping[str, Any]) -> None:
    """Validate the version-scoped v6 telemetry extension without changing legacy rows."""

    _require_exact_fields(record, A2_PULL_V6_CONTROL_EXTENSION_UNITS, "pull_v6 telemetry")
    for name in ("stage4_subphase", "release_persistence_steps", "handoff_active_steps"):
        value = record[name]
        if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < 0:
            raise ValueError(f"pull_v6 telemetry.{name} must be a non-negative integer.")
    if int(record["stage4_subphase"]) > 3:
        raise ValueError("pull_v6 telemetry.stage4_subphase must be one of 0/1/2/3.")
    for name in ("pivot_valid", "handle_crossed", "release_side_qualified", "handoff_active", "handoff_reached", "passage_ready", "release_ready", "release_event", "clean_release"):
        if not isinstance(record[name], bool):
            raise ValueError(f"pull_v6 telemetry.{name} must be bool.")
    for name in set(A2_PULL_V6_CONTROL_EXTENSION_UNITS).difference(
        {"stage4_subphase", "release_persistence_steps", "handoff_active_steps", "pivot_valid", "handle_crossed", "release_side_qualified", "handoff_active", "handoff_reached", "passage_ready", "release_ready", "release_event", "clean_release"}
    ):
        value = record[name]
        if value != A2_PULL_NA and not _is_finite_real(value):
            raise ValueError(f"pull_v6 telemetry.{name} must be finite or N/A; got {value!r}.")
    for name in ("arm_tangent_share", "arc_quality", "release_quality"):
        value = record[name]
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"pull_v6 telemetry.{name} must lie in [0, 1].")


def _is_finite_real(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, Real)
        and math.isfinite(float(value))
    )


def _normalize_event_predecessors(
    event_predecessors: Sequence[int | None] | None,
) -> tuple[int | None, ...] | None:
    if event_predecessors is None:
        return None
    predecessors = tuple(event_predecessors)
    if len(predecessors) != len(A2PullEvent):
        raise ValueError(
            "event_predecessors must provide one predecessor for each pull event."
        )
    normalized: list[int | None] = []
    for event_index, predecessor in enumerate(predecessors):
        if predecessor is None:
            normalized.append(None)
            continue
        if (
            isinstance(predecessor, bool)
            or not isinstance(predecessor, Integral)
            or int(predecessor) < 0
            or int(predecessor) >= event_index
        ):
            raise ValueError(
                "event_predecessors must use None or an earlier event index for each event."
            )
        normalized.append(int(predecessor))
    return tuple(normalized)


def _require_finite_tree(value: Any, field_name: str) -> None:
    if _is_finite_real(value):
        return
    if isinstance(value, Mapping):
        if not value:
            raise ValueError(f"{field_name} must not be an empty mapping.")
        for key, child in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{field_name} mapping keys must be non-empty strings.")
            _require_finite_tree(child, f"{field_name}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if not value:
            raise ValueError(f"{field_name} must not be an empty sequence.")
        for index, child in enumerate(value):
            _require_finite_tree(child, f"{field_name}[{index}]")
        return
    raise ValueError(f"{field_name} must contain only finite numeric values; got {value!r}.")


def _require_exact_fields(record: Mapping[str, Any], expected: Mapping[str, str], context: str) -> None:
    if not isinstance(record, Mapping):
        raise TypeError(f"{context} must be a mapping.")
    missing = set(expected).difference(record)
    extra = set(record).difference(expected)
    if missing or extra:
        raise ValueError(
            f"{context} fields must match the schema exactly; "
            f"missing={sorted(missing)}, extra={sorted(extra)}."
        )


def _require_estimate_envelope(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != {"value", "provenance"}:
        raise ValueError(
            f"{field_name} must contain exactly value and provenance fields."
        )
    if value["provenance"] != A2_PULL_ESTIMATE_ONLY:
        raise ValueError(
            f"{field_name} provenance must be {A2_PULL_ESTIMATE_ONLY!r}."
        )
    _require_finite_tree(value["value"], f"{field_name}.value")


def a2_pull_hinge_drive_force_bucket(hinge_drive_max_force_nm: Any) -> str:
    """Return the canonical pull-v0 hinge-drive-force stratum label."""

    if not _is_finite_real(hinge_drive_max_force_nm) or float(hinge_drive_max_force_nm) <= 0.0:
        raise ValueError("hinge_drive_max_force_nm must be finite and positive.")
    if float(hinge_drive_max_force_nm) <= A2_PULL_HINGE_DRIVE_FORCE_BUCKET_THRESHOLD_NM:
        return A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS[0]
    return A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS[1]


def validate_a2_pull_control_step(record: Mapping[str, Any]) -> None:
    """Fail fast when a pull-v0 per-control-step record violates its contract."""

    _require_exact_fields(record, A2_PULL_CONTROL_STEP_UNITS, "pull control-step record")
    for field_name in (
        "door_open_io_sign",
        "door_open_lr_sign",
        "active_handle_face_x_sign",
        "travel_dir_x",
    ):
        value = record[field_name]
        if isinstance(value, bool) or not isinstance(value, Integral) or int(value) not in (-1, 1):
            raise ValueError(f"{field_name} must be integer -1 or +1; got {value!r}.")
    stage = record["stage"]
    if isinstance(stage, bool) or not isinstance(stage, Integral) or int(stage) < 0:
        raise ValueError(f"stage must be a non-negative integer; got {stage!r}.")
    if record["event_state"] not in (A2_PULL_PRE_E0, *A2_PULL_EVENT_NAMES):
        raise ValueError(f"event_state is not a pull-v0 event enum: {record['event_state']!r}.")
    if not isinstance(record["bilateral_handle_contact"], bool):
        raise ValueError("bilateral_handle_contact must be bool.")
    if record["hook_contact"] != A2_PULL_NA and not isinstance(record["hook_contact"], bool):
        raise ValueError("hook_contact must be bool or 'N/A'.")
    clearance = record["minimum_panel_robot_clearance_m"]
    if clearance != A2_PULL_NA and not _is_finite_real(clearance):
        raise ValueError("minimum_panel_robot_clearance_m must be finite or 'N/A'.")
    slip = record["handle_local_slip_xyz_mps"]
    if slip != A2_PULL_NA:
        if not isinstance(slip, Sequence) or isinstance(slip, (str, bytes)) or len(slip) != 3:
            raise ValueError(
                "handle_local_slip_xyz_mps must be a length-3 numeric sequence or 'N/A'."
            )
        _require_finite_tree(slip, "handle_local_slip_xyz_mps")
    for field_name in A2_PULL_ESTIMATE_ONLY_FIELDS:
        _require_estimate_envelope(record[field_name], field_name)
    for field_name in ("panel_contact_force_by_body_N", "frame_contact_force_by_body_N"):
        forces = record[field_name]
        if not isinstance(forces, Mapping):
            raise ValueError(f"{field_name} must be a body-name mapping.")
        _require_finite_tree(forces, field_name)
        if any(float(value) < 0.0 for value in forces.values()):
            raise ValueError(f"{field_name} values must be non-negative.")
    _require_finite_tree(record["reward_component_raw"], "reward_component_raw")
    excluded = {
        "door_open_io_sign",
        "door_open_lr_sign",
        "active_handle_face_x_sign",
        "travel_dir_x",
        "stage",
        "event_state",
        "bilateral_handle_contact",
        "hook_contact",
        "handle_local_slip_xyz_mps",
        "finger_pd_effort_estimate_N",
        "finger_effort_utilization_estimate",
        "arm_pd_effort_utilization_estimate",
        "panel_contact_force_by_body_N",
        "frame_contact_force_by_body_N",
        "minimum_panel_robot_clearance_m",
        "reward_component_raw",
    }
    for field_name in set(A2_PULL_CONTROL_STEP_UNITS).difference(excluded):
        if not _is_finite_real(record[field_name]):
            raise ValueError(f"{field_name} must be finite; got {record[field_name]!r}.")


def validate_a2_pull_episode(
    record: Mapping[str, Any],
    *,
    event_predecessors: Sequence[int | None] | None = None,
) -> None:
    """Validate an episode summary, including event dependency ordering."""

    expected = {
        **A2_PULL_EPISODE_UNITS,
        **A2_PULL_EPISODE_STRATIFICATION_UNITS,
        "event_reached": "bool_by_event",
    }
    _require_exact_fields(record, expected, "pull episode record")
    if not isinstance(record["spawn_hook"], bool):
        raise ValueError("spawn_hook must be bool.")
    a2_pull_hinge_drive_force_bucket(record["hinge_drive_max_force_nm"])
    reached = record["event_reached"]
    first_steps = record["first_event_step"]
    first_times = record["first_event_time_s"]
    for field_name, value in (
        ("event_reached", reached),
        ("first_event_step", first_steps),
        ("first_event_time_s", first_times),
    ):
        if not isinstance(value, Mapping) or tuple(value) != A2_PULL_EVENT_NAMES:
            raise ValueError(
                f"{field_name} must preserve exact event order {A2_PULL_EVENT_NAMES}."
            )
    normalized_predecessors = _normalize_event_predecessors(event_predecessors)
    if normalized_predecessors is None:
        previous_reached = True
        previous_step = -1
        previous_time = -1.0
        for event_name in A2_PULL_EVENT_NAMES:
            event_reached = reached[event_name]
            if not isinstance(event_reached, bool):
                raise ValueError(f"event_reached.{event_name} must be bool.")
            if event_reached and not previous_reached:
                raise ValueError(f"{event_name} cannot be reached before its predecessor.")
            step = first_steps[event_name]
            time_s = first_times[event_name]
            if event_reached:
                if (
                    isinstance(step, bool)
                    or not isinstance(step, Integral)
                    or int(step) < 0
                    or int(step) < previous_step
                    or not _is_finite_real(time_s)
                    or float(time_s) < 0.0
                    or float(time_s) < previous_time
                ):
                    raise ValueError(
                        f"{event_name} first step/time must be non-negative and ordered."
                    )
                previous_step = int(step)
                previous_time = float(time_s)
            elif step != A2_PULL_NA or time_s != A2_PULL_NA:
                raise ValueError(f"Unreached {event_name} must use 'N/A' step and time.")
            previous_reached = event_reached
    else:
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES):
            event_reached = reached[event_name]
            if not isinstance(event_reached, bool):
                raise ValueError(f"event_reached.{event_name} must be bool.")
            step = first_steps[event_name]
            time_s = first_times[event_name]
            if event_reached:
                if (
                    isinstance(step, bool)
                    or not isinstance(step, Integral)
                    or int(step) < 0
                    or not _is_finite_real(time_s)
                    or float(time_s) < 0.0
                ):
                    raise ValueError(
                        f"{event_name} first step/time must be non-negative and finite."
                    )
                predecessor = normalized_predecessors[event_index]
                if predecessor is not None:
                    predecessor_name = A2_PULL_EVENT_NAMES[predecessor]
                    if not reached[predecessor_name]:
                        raise ValueError(
                            f"{event_name} cannot be reached before {predecessor_name}."
                        )
                    predecessor_step = first_steps[predecessor_name]
                    predecessor_time = first_times[predecessor_name]
                    if (
                        isinstance(predecessor_step, bool)
                        or not isinstance(predecessor_step, Integral)
                        or int(step) < int(predecessor_step)
                        or not _is_finite_real(predecessor_time)
                        or float(time_s) < float(predecessor_time)
                    ):
                        raise ValueError(
                            f"{event_name} first step/time must not precede {predecessor_name}."
                        )
            elif step != A2_PULL_NA or time_s != A2_PULL_NA:
                raise ValueError(f"Unreached {event_name} must use 'N/A' step and time.")
    terminal_reason = record["terminal_reason"]
    if not isinstance(terminal_reason, str) or not terminal_reason:
        raise ValueError("terminal_reason must be a non-empty string.")
    for field_name in ("crossing_while_valid_capture", "whole_body_clear"):
        if not isinstance(record[field_name], bool):
            raise ValueError(f"{field_name} must be bool.")
    contact_steps = record["body_panel_contact_steps_per_20s"]
    if isinstance(contact_steps, bool) or not isinstance(contact_steps, Integral) or contact_steps < 0:
        raise ValueError("body_panel_contact_steps_per_20s must be a non-negative integer.")
    reversal_step = record["first_path_reversal_step"]
    if reversal_step != A2_PULL_NA and (
        isinstance(reversal_step, bool)
        or not isinstance(reversal_step, Integral)
        or reversal_step < 0
    ):
        raise ValueError("first_path_reversal_step must be non-negative or 'N/A'.")
    excluded = {
        "event_reached",
        "first_event_step",
        "first_event_time_s",
        "first_path_reversal_step",
        "body_panel_contact_steps_per_20s",
        "crossing_while_valid_capture",
        "whole_body_clear",
        "terminal_reason",
    }
    for field_name in set(A2_PULL_EPISODE_UNITS).difference(excluded):
        value = record[field_name]
        if value != A2_PULL_NA and not _is_finite_real(value):
            raise ValueError(f"{field_name} must be finite or 'N/A'; got {value!r}.")


def advance_a2_pull_events(
    reached: torch.Tensor,
    evidence: torch.Tensor,
    first_event_step: torch.Tensor,
    control_step: torch.Tensor,
    *,
    event_predecessors: Sequence[int | None] | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Advance pull events on a control step under an explicit dependency graph."""

    if (
        not torch.is_tensor(reached)
        or not torch.is_tensor(evidence)
        or reached.ndim != 2
        or reached.shape != evidence.shape
        or reached.shape[1] != len(A2PullEvent)
        or reached.dtype != torch.bool
        or evidence.dtype != torch.bool
        or reached.device != evidence.device
    ):
        raise ValueError("reached and evidence must be matching device-local bool (N, 8) tensors.")
    if (
        not torch.is_tensor(first_event_step)
        or first_event_step.shape != reached.shape
        or first_event_step.dtype != torch.long
        or first_event_step.device != reached.device
        or torch.any(first_event_step < -1)
    ):
        raise ValueError("first_event_step must be a matching long tensor with values >= -1.")
    if (
        not torch.is_tensor(control_step)
        or control_step.shape != (reached.shape[0],)
        or control_step.dtype != torch.long
        or control_step.device != reached.device
        or torch.any(control_step < 0)
    ):
        raise ValueError("control_step must be a non-negative device-local long vector.")
    normalized_predecessors = _normalize_event_predecessors(event_predecessors)
    updated = reached.clone()
    updated_first = first_event_step.clone()
    for event_index in range(len(A2PullEvent)):
        predecessor_index = (
            None if event_index == 0 else event_index - 1
            if normalized_predecessors is None
            else normalized_predecessors[event_index]
        )
        predecessor = (
            torch.ones(reached.shape[0], dtype=torch.bool, device=reached.device)
            if predecessor_index is None
            else updated[:, predecessor_index]
        )
        newly_reached = ~updated[:, event_index] & evidence[:, event_index] & predecessor
        updated[:, event_index] |= newly_reached
        updated_first[newly_reached, event_index] = control_step[newly_reached]
    if normalized_predecessors is None:
        if torch.any(updated[:, 1:] & ~updated[:, :-1]):
            raise RuntimeError("Pull event state became non-contiguous.")
    else:
        for event_index, predecessor_index in enumerate(normalized_predecessors):
            if predecessor_index is None:
                continue
            reached_without_predecessor = updated[:, event_index] & ~updated[:, predecessor_index]
            if torch.any(reached_without_predecessor):
                raise RuntimeError("Pull hard-gate event state violated its dependency graph.")
            invalid_first_step_order = updated[:, event_index] & (
                (updated_first[:, predecessor_index] < 0)
                | (updated_first[:, event_index] < updated_first[:, predecessor_index])
            )
            if torch.any(invalid_first_step_order):
                raise RuntimeError(
                    "Pull hard-gate first-event steps violated dependency ordering."
                )
    expected_unset = ~updated
    if torch.any(updated_first[expected_unset] != -1) or torch.any(updated_first[updated] < 0):
        raise RuntimeError("Pull first-event steps disagree with reached state.")
    return updated, updated_first


def a2_pull_event_state_names(
    reached: torch.Tensor,
    *,
    event_predecessors: Sequence[int | None] | None = None,
) -> list[str]:
    if (
        not torch.is_tensor(reached)
        or reached.ndim != 2
        or reached.shape[1] != len(A2PullEvent)
        or reached.dtype != torch.bool
    ):
        raise ValueError("reached must be a bool (N, 8) tensor.")
    normalized_predecessors = _normalize_event_predecessors(event_predecessors)
    if normalized_predecessors is None:
        if torch.any(reached[:, 1:] & ~reached[:, :-1]):
            raise ValueError("reached events must be causally contiguous.")
        event_counts = reached.long().sum(dim=-1).tolist()
        return [
            A2_PULL_PRE_E0 if count == 0 else A2_PULL_EVENT_NAMES[count - 1]
            for count in event_counts
        ]
    for event_index, predecessor_index in enumerate(normalized_predecessors):
        if predecessor_index is not None and torch.any(
            reached[:, event_index] & ~reached[:, predecessor_index]
        ):
            raise ValueError("reached events violate the supplied dependency graph.")
    highest_reached = torch.full(
        (reached.shape[0],), -1, dtype=torch.long, device=reached.device
    )
    for event_index in range(len(A2PullEvent)):
        highest_reached = torch.where(
            reached[:, event_index],
            torch.full_like(highest_reached, event_index),
            highest_reached,
        )
    return [
        A2_PULL_PRE_E0 if event_index < 0 else A2_PULL_EVENT_NAMES[event_index]
        for event_index in highest_reached.tolist()
    ]


def _a2_pull_event_funnel_ratios(episodes: Sequence[Mapping[str, Any]]) -> dict[str, float | str]:
    pairs = (
        ("P(E2 | E1)", A2_PULL_EVENT_NAMES[2], A2_PULL_EVENT_NAMES[1]),
        ("P(E3 | E2)", A2_PULL_EVENT_NAMES[3], A2_PULL_EVENT_NAMES[2]),
        ("P(E4 | E3)", A2_PULL_EVENT_NAMES[4], A2_PULL_EVENT_NAMES[3]),
        ("P(E5 | E4)", A2_PULL_EVENT_NAMES[5], A2_PULL_EVENT_NAMES[4]),
        ("P(E7 | E5)", A2_PULL_EVENT_NAMES[7], A2_PULL_EVENT_NAMES[5]),
    )
    if not episodes:
        return {"P(E1)": A2_PULL_NA, **{label: A2_PULL_NA for label, _numerator, _denominator in pairs}}
    counts = {
        name: sum(bool(episode["event_reached"][name]) for episode in episodes)
        for name in A2_PULL_EVENT_NAMES
    }
    funnel: dict[str, float | str] = {
        "P(E1)": counts[A2_PULL_EVENT_NAMES[1]] / len(episodes)
    }
    for label, numerator_name, denominator_name in pairs:
        denominator = counts[denominator_name]
        funnel[label] = A2_PULL_NA if denominator == 0 else counts[numerator_name] / denominator
    return funnel


def a2_pull_event_funnel(
    episodes: Sequence[Mapping[str, Any]],
    *,
    event_predecessors: Sequence[int | None] | None = None,
) -> dict[str, float | str]:
    """Return event-funnel ratios with explicit N/A conditional denominators."""

    if not isinstance(episodes, Sequence) or isinstance(episodes, (str, bytes)) or not episodes:
        raise ValueError("event funnel requires at least one episode record.")
    for episode in episodes:
        validate_a2_pull_episode(episode, event_predecessors=event_predecessors)
    funnel = _a2_pull_event_funnel_ratios(episodes)
    for spawn_hook in (True, False):
        subset = [episode for episode in episodes if episode["spawn_hook"] is spawn_hook]
        prefix = f"spawnHook={spawn_hook}"
        funnel[f"{prefix}.count"] = float(len(subset))
        for label, value in _a2_pull_event_funnel_ratios(subset).items():
            funnel[f"{prefix}.{label}"] = value
    for bucket_label in A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS:
        subset = [
            episode
            for episode in episodes
            if a2_pull_hinge_drive_force_bucket(episode["hinge_drive_max_force_nm"]) == bucket_label
        ]
        funnel[f"{bucket_label}.count"] = float(len(subset))
        for label, value in _a2_pull_event_funnel_ratios(subset).items():
            funnel[f"{bucket_label}.{label}"] = value
    return funnel


def a2_pull_v5_release_tuck_override(
    policy_action: torch.Tensor,
    hinge_position_rad: torch.Tensor,
    aperture_ready: torch.Tensor,
    elapsed_steps: torch.Tensor,
    *,
    dt: float,
    enabled: bool,
    arm_action: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply the bounded P2 arm/gripper override while preserving base policy output.

    The high-level A2 action layout is ``base[0:5]``, ``arm[5:11]``, and
    ``gripper[11]``.  Only the arm/gripper slice is changed during the exact
    one-second window; base commands remain the frozen actor output.
    """

    if (
        not torch.is_tensor(policy_action)
        or policy_action.ndim != 2
        or policy_action.shape[1] != 12
        or not policy_action.is_floating_point()
        or not torch.all(torch.isfinite(policy_action))
    ):
        raise ValueError("Pull-v5 override requires a floating [envs, 12] high-level action tensor.")
    expected = (policy_action.shape[0],)
    for name, value, dtype in (
        ("hinge_position_rad", hinge_position_rad, policy_action.dtype),
        ("aperture_ready", aperture_ready, torch.bool),
        ("elapsed_steps", elapsed_steps, torch.long),
    ):
        if not torch.is_tensor(value) or tuple(value.shape) != expected or value.device != policy_action.device:
            raise ValueError(f"Pull-v5 override {name} must have shape {expected} on the action device.")
        if value.dtype != dtype:
            raise ValueError(f"Pull-v5 override {name} must have dtype {dtype}; got {value.dtype}.")
    if not torch.all(torch.isfinite(hinge_position_rad)):
        raise ValueError("Pull-v5 override hinge_position_rad must be finite.")
    if torch.any(elapsed_steps < 0):
        raise ValueError("Pull-v5 override elapsed_steps must be non-negative.")
    if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(float(dt)) or dt <= 0.0:
        raise ValueError(f"Pull-v5 override dt must be finite and > 0; got {dt!r}.")
    if not isinstance(enabled, bool):
        raise ValueError("Pull-v5 override enabled must be bool.")
    duration_steps = max(1, math.ceil(A2_PULL_V5_RELEASE_TUCK_DURATION_S / float(dt)))
    active = (
        torch.full(expected, enabled, dtype=torch.bool, device=policy_action.device)
        & aperture_ready
        & (hinge_position_rad >= A2_PULL_V5_RELEASE_HINGE_THRESHOLD_RAD)
        & (elapsed_steps < duration_steps)
    )
    if arm_action is not None:
        if (
            not torch.is_tensor(arm_action)
            or tuple(arm_action.shape) != (policy_action.shape[0], 6)
            or arm_action.device != policy_action.device
            or arm_action.dtype != policy_action.dtype
            or not torch.all(torch.isfinite(arm_action))
        ):
            raise ValueError(
                "Pull-v5 override arm_action must be a finite [envs, 6] tensor "
                "matching policy_action dtype/device."
            )
    applied = policy_action.clone()
    applied[active, 5:11] = (
        torch.zeros_like(applied[active, 5:11])
        if arm_action is None
        else arm_action[active]
    )
    applied[active, 11] = 1.0
    return applied, active


__all__ = [
    "A2PullEvent",
    "A2_PULL_CONTROL_STEP_UNITS",
    "A2_PULL_EPISODE_UNITS",
    "A2_PULL_EPISODE_STRATIFICATION_UNITS",
    "A2_PULL_ESTIMATE_ONLY",
    "A2_PULL_ESTIMATE_ONLY_FIELDS",
    "A2_PULL_EVENT_NAMES",
    "A2_PULL_HARD_GATE_EVENT_PREDECESSORS",
    "A2_PULL_HINGE_DRIVE_FORCE_BUCKET_LABELS",
    "A2_PULL_HINGE_DRIVE_FORCE_BUCKET_THRESHOLD_NM",
    "A2_PULL_NA",
    "A2_PULL_PRE_E0",
    "A2_PULL_TELEMETRY_SCHEMA_VERSION",
    "A2_PULL_V5_PERSISTENT_RELEASE_STREAK_STEPS",
    "A2_PULL_V5_RELEASE_HINGE_THRESHOLD_RAD",
    "A2_PULL_V5_RELEASE_TUCK_DURATION_S",
    "A2_PULL_V6_CONTROL_EXTENSION_UNITS",
    "a2_pull_event_funnel",
    "a2_pull_event_state_names",
    "a2_pull_hinge_drive_force_bucket",
    "a2_pull_v5_release_tuck_override",
    "advance_a2_pull_events",
    "validate_a2_pull_control_step",
    "validate_a2_pull_episode",
    "validate_a2_pull_v6_control_extension",
]
