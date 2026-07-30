"""Pure, device-local evidence helpers for the v20 R2 transition.

The helpers in this module deliberately have no environment or simulator
dependencies.  They validate their tensor contracts at the call boundary so
invalid staged-reset or task-space state fails fast instead of being silently
coerced into an admissible sample.
"""

from __future__ import annotations

import math
from typing import Mapping

import torch


_SNAPSHOT_REASON_NOT_POPULATED = 0
_SNAPSHOT_REASON_ADMIT_PRE_SWING = 1
_SNAPSHOT_REASON_ADMIT_SWING_PRE_CROSS = 2
_SNAPSHOT_REASON_ADMIT_POST_SEND_SWING = 3
_SNAPSHOT_REASON_ADMIT_POST_SEND_THROUGH = 4
_SNAPSHOT_REASON_REJECT_PRE_SEND_CROSSING_SEEN = 10
_SNAPSHOT_REASON_REJECT_SWING_ROOT_BEYOND_MARGIN_WITHOUT_SEND = 11
_SNAPSHOT_REASON_REJECT_THROUGH_WITHOUT_SEND = 12
_SNAPSHOT_REASON_REJECT_UNSUPPORTED_STAGE = 13


def _require_vector(
    value: torch.Tensor,
    *,
    shape: tuple[int, ...],
    name: str,
    dtype: torch.dtype | None = None,
    floating: bool = False,
) -> None:
    if not torch.is_tensor(value) or tuple(value.shape) != shape:
        actual = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{name} requires shape {shape}; got {actual}.")
    if dtype is not None and value.dtype != dtype:
        raise ValueError(f"{name} requires dtype {dtype}; got {value.dtype}.")
    if floating and not value.is_floating_point():
        raise ValueError(f"{name} requires a floating tensor; got {value.dtype}.")


def _require_finite(value: torch.Tensor, name: str) -> None:
    if not torch.all(torch.isfinite(value)):
        raise ValueError(f"{name} contains non-finite values.")


def a2_v20_r2_snapshot_admission_mask(
    candidate_stage: torch.Tensor,
    populated: torch.Tensor,
    send_ready: torch.Tensor,
    pre_send_crossing_seen: torch.Tensor,
    root_x_rel: torch.Tensor,
    root_x_margin: float,
    stage_swing: int,
    stage_through: int,
) -> Mapping[str, torch.Tensor]:
    """Apply the R2 staged-reset admission truth table.

    ``populated`` identifies real snapshot slots.  Empty slots always return
    ``reason_code == 0`` and are never admitted.  A stage beyond
    ``stage_through`` is a configuration error and raises immediately; reason
    code 13 is retained as a schema value but is never silently returned.
    """

    if not torch.is_tensor(candidate_stage) or candidate_stage.ndim != 1:
        raise ValueError("R2 snapshot candidate_stage requires a one-dimensional tensor.")
    n = candidate_stage.shape[0]
    _require_vector(candidate_stage, shape=(n,), name="R2 candidate_stage", dtype=torch.long)
    for value, name in (
        (populated, "populated"),
        (send_ready, "send_ready"),
        (pre_send_crossing_seen, "pre_send_crossing_seen"),
    ):
        _require_vector(value, shape=(n,), name=f"R2 {name}", dtype=torch.bool)
        if value.device != candidate_stage.device:
            raise ValueError("R2 snapshot tensors must share a device.")
    _require_vector(root_x_rel, shape=(n,), name="R2 root_x_rel", floating=True)
    if root_x_rel.device != candidate_stage.device or root_x_rel.dtype != torch.float32:
        raise ValueError("R2 root_x_rel must be float32 on the candidate-stage device.")
    if torch.any(populated & ~torch.isfinite(root_x_rel)):
        raise ValueError("R2 populated root_x_rel contains non-finite values.")
    if (
        isinstance(root_x_margin, bool)
        or not isinstance(root_x_margin, (int, float))
        or not math.isfinite(float(root_x_margin))
        or float(root_x_margin) < 0.0
    ):
        raise ValueError("R2 root_x_margin must be finite and non-negative.")
    if (
        isinstance(stage_swing, bool)
        or isinstance(stage_through, bool)
        or not isinstance(stage_swing, int)
        or not isinstance(stage_through, int)
        or stage_through <= stage_swing
    ):
        raise ValueError("R2 staged-reset bounds require stage_through > stage_swing.")
    if torch.any(candidate_stage > stage_through):
        bad = torch.where(candidate_stage > stage_through)[0].tolist()
        raise ValueError(
            "R2 staged-reset admission encountered unsupported stage values "
            f"at indices {bad}; stage_through={stage_through}."
        )

    reason_code = torch.zeros(n, dtype=torch.int8, device=candidate_stage.device)
    admit = torch.zeros(n, dtype=torch.bool, device=candidate_stage.device)
    populated_pre_swing = populated & (candidate_stage < stage_swing)
    admit[populated_pre_swing] = True
    reason_code[populated_pre_swing] = _SNAPSHOT_REASON_ADMIT_PRE_SWING

    swing = populated & (candidate_stage == stage_swing)
    swing_crossing = swing & pre_send_crossing_seen
    reason_code[swing_crossing] = _SNAPSHOT_REASON_REJECT_PRE_SEND_CROSSING_SEEN
    swing_unsent = swing & ~pre_send_crossing_seen & ~send_ready
    swing_root_beyond_margin = swing_unsent & (root_x_rel > float(root_x_margin))
    reason_code[swing_root_beyond_margin] = (
        _SNAPSHOT_REASON_REJECT_SWING_ROOT_BEYOND_MARGIN_WITHOUT_SEND
    )
    swing_pre_cross = swing_unsent & ~swing_root_beyond_margin
    admit[swing_pre_cross] = True
    reason_code[swing_pre_cross] = _SNAPSHOT_REASON_ADMIT_SWING_PRE_CROSS
    swing_post_send = swing & ~pre_send_crossing_seen & send_ready
    admit[swing_post_send] = True
    reason_code[swing_post_send] = _SNAPSHOT_REASON_ADMIT_POST_SEND_SWING

    through = populated & (candidate_stage == stage_through)
    through_crossing = through & pre_send_crossing_seen
    reason_code[through_crossing] = _SNAPSHOT_REASON_REJECT_PRE_SEND_CROSSING_SEEN
    through_unsent = through & ~pre_send_crossing_seen & ~send_ready
    reason_code[through_unsent] = _SNAPSHOT_REASON_REJECT_THROUGH_WITHOUT_SEND
    through_sent = through & ~pre_send_crossing_seen & send_ready
    admit[through_sent] = True
    reason_code[through_sent] = _SNAPSHOT_REASON_ADMIT_POST_SEND_THROUGH

    # Empty slots retain the explicit zero reason and false admission even if
    # their backing tensors contain stale values.
    admit &= populated
    reason_code = torch.where(populated, reason_code, torch.zeros_like(reason_code))
    if torch.any(admit & (reason_code == _SNAPSHOT_REASON_NOT_POPULATED)):
        raise RuntimeError("R2 snapshot admission produced an admitted slot without a reason code.")
    return {"admit": admit, "reason_code": reason_code}


def a2_v20_r2_taskspace_arm_carry(
    root_pos_w: torch.Tensor,
    root_lin_vel_w: torch.Tensor,
    root_ang_vel_w: torch.Tensor,
    tcp_pos_w: torch.Tensor,
    tcp_lin_vel_w: torch.Tensor,
    opening_tangent_w: torch.Tensor,
    valid_reference: torch.Tensor,
    valid_hold: torch.Tensor,
    before_send: torch.Tensor,
    positive_hinge_progress: torch.Tensor,
    activity_floor_mps: float,
) -> dict[str, torch.Tensor]:
    """Compute R2 task-space arm carry and its strict validity mask."""

    if not torch.is_tensor(root_pos_w) or root_pos_w.ndim != 2 or root_pos_w.shape[1] != 3:
        raise ValueError("R2 root_pos_w requires shape (N, 3).")
    n = root_pos_w.shape[0]
    if not root_pos_w.is_floating_point():
        raise ValueError("R2 root_pos_w requires a floating tensor.")
    dtype = root_pos_w.dtype
    device = root_pos_w.device
    for value, name in (
        (root_lin_vel_w, "root_lin_vel_w"),
        (root_ang_vel_w, "root_ang_vel_w"),
        (tcp_pos_w, "tcp_pos_w"),
        (tcp_lin_vel_w, "tcp_lin_vel_w"),
        (opening_tangent_w, "opening_tangent_w"),
    ):
        _require_vector(value, shape=(n, 3), name=f"R2 {name}", floating=True)
        if value.device != device or value.dtype != dtype:
            raise ValueError("R2 task-space floating tensors must share dtype and device.")
        _require_finite(value, f"R2 {name}")
    for value, name in (
        (valid_reference, "valid_reference"),
        (valid_hold, "valid_hold"),
        (before_send, "before_send"),
        (positive_hinge_progress, "positive_hinge_progress"),
    ):
        _require_vector(value, shape=(n,), name=f"R2 {name}", dtype=torch.bool)
        if value.device != device:
            raise ValueError("R2 task-space masks must share device.")
    _require_finite(root_pos_w, "R2 root_pos_w")
    if (
        isinstance(activity_floor_mps, bool)
        or not isinstance(activity_floor_mps, (int, float))
        or not math.isfinite(float(activity_floor_mps))
        or float(activity_floor_mps) <= 0.0
    ):
        raise ValueError("R2 activity_floor_mps must be finite and strictly positive.")
    tangent_norm = torch.linalg.norm(opening_tangent_w, dim=-1)
    valid_rows = valid_reference & valid_hold & before_send & positive_hinge_progress
    if torch.any(torch.abs(tangent_norm[valid_rows] - 1.0) > 1.0e-5):
        raise ValueError("R2 opening_tangent_w must be unit length within 1e-5 on valid rows.")

    v_base_at_tcp = root_lin_vel_w + torch.cross(
        root_ang_vel_w, tcp_pos_w - root_pos_w, dim=-1
    )
    v_arm = tcp_lin_vel_w - v_base_at_tcp
    base_tangent = torch.sum(v_base_at_tcp * opening_tangent_w, dim=-1)
    arm_tangent = torch.sum(v_arm * opening_tangent_w, dim=-1)
    positive_base = torch.relu(base_tangent)
    positive_arm = torch.relu(arm_tangent)
    positive_total = positive_base + positive_arm
    active = valid_rows & (positive_total >= float(activity_floor_mps))
    safe_total = torch.where(active, positive_total, torch.ones_like(positive_total))
    arm_tangent_share = torch.where(
        active, positive_arm / safe_total, torch.zeros_like(positive_total)
    )
    computed = {
        "v_base_at_tcp": v_base_at_tcp,
        "v_arm": v_arm,
        "positive_base_tangent": positive_base,
        "positive_arm_tangent": positive_arm,
        "positive_total_tangent": positive_total,
        "active": active,
        "arm_tangent_share": arm_tangent_share,
        "valid": valid_rows,
    }
    for name, value in computed.items():
        if value.is_floating_point() and not torch.all(torch.isfinite(value)):
            raise RuntimeError(f"R2 task-space output {name} is non-finite.")
    if torch.any(active & ((arm_tangent_share < 0.0) | (arm_tangent_share > 1.0))):
        raise RuntimeError("R2 active arm tangent share must lie in [0, 1].")
    if torch.any(arm_tangent_share[~active] != 0.0):
        raise RuntimeError("R2 inactive arm tangent share must be exactly zero.")
    return computed



# M48 record/trace contracts are kept pure and dependency-light so they can be
# exercised without IsaacSim.  Runtime integration supplies only plain Python
# rows and finite scalar metrics.
_R2_RECORD_SCHEMA = "a2_piper_v20_R2_episode_record_v1"
_R2_TRACE_SCHEMA = "a2_piper_v20_R2_step_trace_v1"
_R2_RECORD_SET_SCHEMA = "a2_piper_base_v20_R2_record_set_v1"
_R2_FORBIDDEN_FIELDS = frozenset(
    {"status", "pass", "passed", "checks_passed", "verdict", "adjudication"}
)
_R2_RECORD_TOP_LEVEL = (
    "schema",
    "record_id",
    "provenance",
    "topology",
    "scenario",
    "factor",
    "phase",
    "task",
    "safety",
    "send",
    "task_space",
    "smoothness",
    "income",
    "release",
    "trace",
    "accumulator_audit",
)
_R2_TRACE_FIELDS = (
    "schema",
    "run_uuid",
    "env_id",
    "episode_ordinal",
    "step_index",
    "batch_index",
    "stage",
    "curriculum_phase",
    "root_se2",
    "door_hinge_position_rad",
    "door_hinge_velocity_radps",
    "hold_valid",
    "bilateral",
    "coasting",
    "over_force",
    "send_ready",
    "pre_send_crossing_event",
    "root_crossing_event",
    "release_event",
    "root_x_rel_m",
    "arm_raw_action_6d",
    "taskspace_active",
    "positive_arm_tangent_mps",
    "positive_base_tangent_mps",
    "arm_tangent_share",
    "arc_position_error_m",
    "arc_orientation_error_rad",
    "along_handle_slip_m",
    "orthogonal_arc_residual_m",
    "reward_components_scaled",
    "terminal",
    "terminal_reason",
)


def _r2_json_finite(value: object, *, path: str = "$") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains non-finite numeric data.")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contains a non-string key.")
            _r2_json_finite(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _r2_json_finite(child, path=f"{path}[{index}]")
        return
    raise ValueError(f"{path} contains unsupported JSON type {type(value).__name__}.")


def a2_v20_r2_canonical_json_bytes(value: object) -> bytes:
    _r2_json_finite(value)
    try:
        import json

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError) as exc:
        raise ValueError("R2 canonical JSON encoding failed.") from exc


def a2_v20_r2_sha256_json(value: object) -> str:
    import hashlib

    return hashlib.sha256(a2_v20_r2_canonical_json_bytes(value)).hexdigest()


def a2_v20_r2_event(observed: bool, step: int | None) -> dict[str, object]:
    if not isinstance(observed, bool):
        raise ValueError("R2 event observed flag must be bool.")
    if observed:
        if isinstance(step, bool) or not isinstance(step, int) or step < 0:
            raise ValueError("Observed R2 event requires a non-negative integer step.")
    elif step is not None:
        raise ValueError("Unobserved R2 event must carry step=null.")
    return {"observed": observed, "step": step}


def a2_v20_r2_metric(
    state: str,
    sample_count: int,
    value: float | None = None,
) -> dict[str, object]:
    if not isinstance(state, str) or not state:
        raise ValueError("R2 metric state must be a non-empty string.")
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 0:
        raise ValueError("R2 metric sample_count must be a non-negative integer.")
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise ValueError("R2 metric value must be numeric or null.")
    if value is not None and not math.isfinite(float(value)):
        raise ValueError("R2 metric value must be finite.")
    if state == "DEFINED" and value is None:
        raise ValueError("DEFINED R2 metric requires a finite value.")
    if state != "DEFINED" and value is not None:
        raise ValueError("Non-defined R2 metric must use value=null.")
    return {"state": state, "sample_count": sample_count, "value": None if value is None else float(value)}


def a2_v20_r2_distribution(
    values: torch.Tensor,
    mask: torch.Tensor,
    *,
    empty_state: str,
) -> dict[str, object]:
    if (
        not torch.is_tensor(values)
        or values.ndim != 1
        or not values.is_floating_point()
        or not torch.is_tensor(mask)
        or mask.shape != values.shape
        or mask.dtype != torch.bool
        or mask.device != values.device
    ):
        raise ValueError("R2 distribution requires aligned floating values and bool mask.")
    selected = values[mask]
    if not torch.all(torch.isfinite(selected)):
        raise ValueError("R2 distribution selected values must be finite.")
    if selected.numel() == 0:
        if not isinstance(empty_state, str) or not empty_state:
            raise ValueError("R2 empty distribution requires an explicit reason state.")
        return {
            "state": empty_state,
            "sample_count": 0,
            "p10": None,
            "p50": None,
            "p95": None,
            "max": None,
        }
    quantiles = torch.quantile(selected, selected.new_tensor((0.10, 0.50, 0.95)))
    maximum = torch.max(selected)
    result = {
        "state": "DEFINED",
        "sample_count": int(selected.numel()),
        "p10": float(quantiles[0].item()),
        "p50": float(quantiles[1].item()),
        "p95": float(quantiles[2].item()),
        "max": float(maximum.item()),
    }
    _r2_json_finite(result)
    return result


def a2_v20_r2_validate_trace_rows(
    rows: list[Mapping[str, object]],
    *,
    run_uuid: str,
    env_id: int,
    terminal_reason: str,
) -> dict[str, int]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("R2 trace must contain at least one row.")
    if not isinstance(run_uuid, str) or not run_uuid:
        raise ValueError("R2 trace run_uuid is required.")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0:
        raise ValueError("R2 trace env_id must be a non-negative integer.")
    if not isinstance(terminal_reason, str) or not terminal_reason:
        raise ValueError("R2 trace terminal_reason is required.")
    for expected_step, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"R2 trace row {expected_step} must be an object.")
        keys = set(row)
        if keys != set(_R2_TRACE_FIELDS):
            missing = sorted(set(_R2_TRACE_FIELDS) - keys)
            extra = sorted(keys - set(_R2_TRACE_FIELDS))
            raise ValueError(f"R2 trace row {expected_step} fields mismatch; missing={missing}, extra={extra}.")
        if row["schema"] != _R2_TRACE_SCHEMA:
            raise ValueError("R2 trace schema identifier mismatch.")
        if row["run_uuid"] != run_uuid or row["env_id"] != env_id or row["episode_ordinal"] != 0:
            raise ValueError("R2 trace provenance fields mismatch.")
        if (
            isinstance(row["step_index"], bool)
            or not isinstance(row["step_index"], int)
            or row["step_index"] != expected_step
        ):
            raise ValueError("R2 trace step_index must be an integer starting at zero and remain contiguous.")
        if isinstance(row["terminal"], bool) is False:
            raise ValueError("R2 trace terminal must be bool.")
        if row["terminal"] and expected_step != len(rows) - 1:
            raise ValueError("R2 trace terminal row must be last.")
        if expected_step == len(rows) - 1 and row["terminal"] is not True:
            raise ValueError("R2 trace must end with exactly one terminal row.")
        if row["terminal"]:
            if row["terminal_reason"] != terminal_reason:
                raise ValueError("R2 terminal trace reason does not match the episode record.")
        elif row["terminal_reason"] != "NON_TERMINAL":
            raise ValueError("Non-terminal R2 trace rows must use terminal_reason=NON_TERMINAL.")
        for field in ("root_se2", "arm_raw_action_6d"):
            if not isinstance(row[field], list):
                raise ValueError(f"R2 trace {field} must be an array.")
        if len(row["root_se2"]) != 3 or len(row["arm_raw_action_6d"]) != 6:
            raise ValueError("R2 trace root/action arrays have incorrect dimensions.")
        _r2_json_finite(row)
        for key, child in row.items():
            if isinstance(key, str) and key.lower() in _R2_FORBIDDEN_FIELDS:
                raise ValueError(f"R2 trace forbidden field {key!r}.")
    return {"row_count": len(rows), "first_step": 0, "last_step": len(rows) - 1, "terminal_row_index": len(rows) - 1}


def a2_v20_r2_trace_jsonl_bytes(rows: list[Mapping[str, object]]) -> bytes:
    if not isinstance(rows, list) or not rows:
        raise ValueError("R2 trace rows are required.")
    import json

    lines = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("R2 trace rows must be mappings.")
        lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return ("\n".join(lines) + "\n").encode("utf-8")


def a2_v20_r2_append_record_set_staging(path: str, record: Mapping[str, object]) -> None:
    """Append exactly one canonical record line and fsync before reset."""
    if not isinstance(path, str) or not path:
        raise ValueError("R2 staging path is required.")
    if not isinstance(record, Mapping):
        raise ValueError("R2 staged record must be an object.")
    payload = a2_v20_r2_canonical_json_bytes(record) + b"\n"
    import fcntl
    import os
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, payload)
        os.fsync(fd)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def a2_v20_r2_finalize_record_id(record_without_id: Mapping[str, object]) -> str:
    if not isinstance(record_without_id, Mapping):
        raise ValueError("R2 record identity input must be an object.")
    if "record_id" in record_without_id:
        raise ValueError("R2 record identity input must not contain record_id.")
    return a2_v20_r2_sha256_json(record_without_id)
