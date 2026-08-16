"""CPU-only descriptive reducer for the frozen v23 Route-B evidence.

The reducer repairs the v23 mechanics surface mismatch without changing any
historical producer.  It streams each pooled/intervention trace independently,
retains typed missingness, and writes one canonical base-v24 P0 evidence unit.
No output is a causal, state-clone, recurrent-restore, or actual-PhysX-torque
claim.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence

try:
    from ._v24_common import (
        EXPECTED_CANDIDATES,
        EXPECTED_INTERVENTION_RECORDS,
        EXPECTED_REALIZED_EPISODES,
        INTERVENTION_MODES,
        REPO_ROOT,
        V23_FINAL_PATH,
        V23_FREEZE_PATH,
        V23_HOLDOUT_PATH,
        V23_INTERVENTION_PATH,
        V23_P05_BANDS_PATH,
        V23_ROUTE_B_PATH,
        V23_STRATIFIED_PATH,
        V24_P0_ROOT,
        V24Error,
        absolute,
        finite_number,
        iter_json_array,
        read_json,
        rel_path,
        require_object,
        write_json,
        write_text,
    )
    from .p0_unit_contract import (
        TRACE_CONFIG_SURFACE,
        USD_DEGREE_SURFACE,
        contract_metadata,
        normalize_realized_dynamics,
        scaled_distance,
    )
except ImportError:  # direct ``python scriptsFORhuman/v24/p0_v23_posthoc.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v24._v24_common import (
        EXPECTED_CANDIDATES,
        EXPECTED_INTERVENTION_RECORDS,
        EXPECTED_REALIZED_EPISODES,
        INTERVENTION_MODES,
        REPO_ROOT,
        V23_FINAL_PATH,
        V23_FREEZE_PATH,
        V23_HOLDOUT_PATH,
        V23_INTERVENTION_PATH,
        V23_P05_BANDS_PATH,
        V23_ROUTE_B_PATH,
        V23_STRATIFIED_PATH,
        V24_P0_ROOT,
        V24Error,
        absolute,
        finite_number,
        iter_json_array,
        read_json,
        rel_path,
        require_object,
        write_json,
        write_text,
    )
    from scriptsFORhuman.v24.p0_unit_contract import (
        TRACE_CONFIG_SURFACE,
        USD_DEGREE_SURFACE,
        contract_metadata,
        normalize_realized_dynamics,
        scaled_distance,
    )


REALIZED_SCHEMA = "a2_piper_v24_v23_realized_mechanics_reanalysis_v1"
INTERVENTION_SCHEMA = "a2_piper_v24_v23_intervention_outcome_adjudication_v1"
POSTURE_SCHEMA = "a2_piper_v24_v23_posture_behavior_analysis_v1"
TOP_LEVEL_SCHEMA = "a2_piper_v24_v23_posthoc_analysis_v1"

POSTURE_SATURATION_THRESHOLD_RAD = 0.35
QUIET_RELEASE_VELOCITY_THRESHOLD_RADPS = 0.25
CONTINUOUS_OOD_DISTANCE_THRESHOLD = 1.0
FORWARD_LABEL = "FORWARD_INTERVENTION_DESCRIPTIVE_ONLY"
EFFORT_AUTHORITY = "CONFIGURED_SOLVER_LIMIT_READBACK_NOT_ACTUAL_PHYSX_TORQUE"
REQUIRED_BEHAVIOR_CATEGORIES = (
    "HOLD_THROUGH_CROSSING/NO_RELEASE_EVENT",
    "QUIET_HOLD_RELEASE",
    "CONTROLLED_FLING",
    "UNSAFE_RELEASE",
    "UNCLASSIFIED_INSUFFICIENT_TELEMETRY",
)


def _candidate_id(candidate: Mapping[str, Any]) -> str:
    required = ("subwave", "cell", "seed", "step")
    if any(key not in candidate for key in required):
        raise V24Error(f"candidate is missing identity fields: {required}")
    return f"{candidate['subwave']}_{candidate['cell']}_seed{int(candidate['seed'])}_step{int(candidate['step'])}"


def _candidate_summary(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": _candidate_id(candidate),
        "subwave": candidate["subwave"],
        "cell": candidate["cell"],
        "seed": candidate["seed"],
        "step": candidate["step"],
        "freeze_id": candidate.get("freeze_id"),
        "posture": "RP0" if int(candidate["cell"][1:]) % 2 == 0 else "FULL",
        "door_regime": "D1" if int(candidate["cell"][1:]) >= 5 else "D0",
    }


def _finite_optional(value: Any, *, label: str) -> float | None:
    if value is None:
        return None
    return finite_number(value, label=label)


def _number_list(value: Any, *, label: str) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise V24Error(f"{label} must be a list or null")
    return [finite_number(item, label=f"{label}[{index}]") for index, item in enumerate(value)]


def _mean(values: Iterable[float]) -> float | None:
    vals = list(values)
    return float(fmean(vals)) if vals else None


def _require_status(payload: Mapping[str, Any], *, schema: str, status: str, label: str) -> None:
    if payload.get("schema") != schema or payload.get("status") != status:
        raise V24Error(f"{label} is not the frozen expected receipt: schema/status disagree")


def _load_sources() -> dict[str, Any]:
    route = require_object(read_json(V23_ROUTE_B_PATH, label="v23 Route-B receipt"), label="Route-B receipt")
    stratified = require_object(read_json(V23_STRATIFIED_PATH, label="v23 stratified receipt"), label="stratified receipt")
    intervention = require_object(read_json(V23_INTERVENTION_PATH, label="v23 intervention receipt"), label="intervention receipt")
    freeze = require_object(read_json(V23_FREEZE_PATH, label="v23 candidate freeze"), label="candidate freeze")
    holdout = require_object(read_json(V23_HOLDOUT_PATH, label="v23 holdout receipt"), label="holdout receipt")
    final = require_object(read_json(V23_FINAL_PATH, label="v23 final analysis"), label="final analysis")
    p05_bands = require_object(read_json(V23_P05_BANDS_PATH, label="v23 P0.5 band receipt"), label="P0.5 band receipt")
    low_progress_min_rad = finite_number(p05_bands.get("low_progress_min_rad"), label="p05_bands.low_progress_min_rad")
    if low_progress_min_rad != 0.02:
        raise V24Error(f"v23 P0.5 low-progress band changed: expected 0.02 rad, got {low_progress_min_rad}")
    _require_status(route, schema="a2_piper_v23_route_b_receipt_v1", status="V23_ROUTE_B_COMPLETE", label="Route-B receipt")
    _require_status(stratified, schema="a2_piper_v23_stratified_eval_receipt_v1", status="V23_STRATIFIED_EVAL_COMPLETE", label="stratified receipt")
    _require_status(intervention, schema="a2_piper_v23_intervention_eval_receipt_v1", status="V23_INTERVENTION_EVAL_COMPLETE", label="intervention receipt")
    _require_status(freeze, schema="a2_piper_v23_candidate_freeze_v1", status="V23_CANDIDATE_FREEZE_COMPLETE", label="candidate freeze")
    _require_status(holdout, schema="a2_piper_v23_holdout64_receipt_v1", status="V23_HOLDOUT64_COMPLETE", label="holdout receipt")
    _require_status(final, schema="a2_piper_v23_final_analysis_v1", status="V23_FINAL_ANALYSIS_COMPLETE", label="final analysis")
    if stratified.get("episode_count") != EXPECTED_REALIZED_EPISODES:
        raise V24Error("v23 stratified receipt must retain exactly 768 episodes")
    if intervention.get("episode_record_count") != EXPECTED_INTERVENTION_RECORDS:
        raise V24Error("v23 intervention receipt must retain exactly 1280 records")
    if freeze.get("candidate_count") != EXPECTED_CANDIDATES or len(freeze.get("selected_candidates", [])) != EXPECTED_CANDIDATES:
        raise V24Error("v23 candidate freeze must contain exactly 16 candidates")
    if intervention.get("modes") != list(INTERVENTION_MODES):
        raise V24Error("v23 intervention mode order disagrees with the preregistered suite")
    if intervention.get("job_count") != EXPECTED_CANDIDATES * len(INTERVENTION_MODES):
        raise V24Error("v23 intervention receipt must contain exactly 80 jobs")
    return {
        "route": route,
        "stratified": stratified,
        "intervention": intervention,
        "freeze": freeze,
        "holdout": holdout,
        "final": final,
        "p05_bands": p05_bands,
    }


def _freeze_maps(sources: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    freeze_rows = sources["freeze"]["selected_candidates"]
    route_rows = sources["route"]["selected_candidates"]
    freeze_by_id: dict[str, dict[str, Any]] = {}
    route_by_id: dict[str, dict[str, Any]] = {}
    if len(route_rows) != EXPECTED_CANDIDATES:
        raise V24Error("Route-B selected candidate list is not exact16")
    for row in freeze_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("freeze_id"), str):
            raise V24Error("candidate freeze row lacks freeze_id")
        summary_id = _candidate_id(row)
        freeze_by_id[summary_id] = dict(row)
    for row in route_rows:
        if not isinstance(row, Mapping):
            raise V24Error("Route-B selected candidate row is invalid")
        route_by_id[_candidate_id(row)] = dict(row)
    if set(freeze_by_id) != set(route_by_id) or len(freeze_by_id) != EXPECTED_CANDIDATES:
        raise V24Error("Route-B and candidate-freeze candidate identities disagree")
    for key in freeze_by_id:
        if freeze_by_id[key]["freeze_id"] != f"{freeze_by_id[key]['subwave']}_{freeze_by_id[key]['cell']}_seed{int(freeze_by_id[key]['seed'])}_step{int(freeze_by_id[key]['step'])}":
            raise V24Error(f"candidate freeze identity disagrees for {key}")
    return freeze_by_id, route_by_id


def _warm_identity_conflict(freeze_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    key = "A1_G7_seed0_step1500"
    row = freeze_by_id.get(key)
    if row is None:
        raise V24Error("the preregistered provisional G7 candidate is absent from the freeze")
    config_path = str(row.get("config_path", ""))
    if "G7" not in config_path:
        raise V24Error("the provisional G7 candidate config identity is not G7")
    return {
        "candidate_id": key,
        "provisional_selection": "A1_G7_seed0_step1500",
        "config_path": rel_path(config_path),
        "config_filename_token": "scratch" if "scratch" in Path(config_path).name else None,
        "formal_plan_initialization": "warm_head_reset",
        "candidate_freeze_initialization_semantics": "warm_head_reset",
        "identity_conflict": True,
        "resolution": "REPORTED_TYPED_CONFLICT;G7_IS_NOT_SILENTLY_RELABELLED_AS_V22_WARM",
        "selection_status": "PROVISIONAL_UNTIL_MECHANICS_POSTHOC_RE_RANKING",
    }


class _TraceAccumulator:
    def __init__(self, env_id: int, *, post_trigger_step: int | None, post_enabled: bool) -> None:
        self.env_id = env_id
        self.post_trigger_step = post_trigger_step
        self.post_enabled = post_enabled and post_trigger_step is not None and post_trigger_step >= 0
        self.row_count = 0
        self.first_step: int | None = None
        self.last_step: int | None = None
        self.max_stage: int | None = None
        self.hinge_min: float | None = None
        self.hinge_max: float | None = None
        self.hinge_first: float | None = None
        self.hinge_last: float | None = None
        self.hinge_velocity_abs_max: float | None = None
        self.root_displacement_max: float | None = None
        self.yaw_abs_max: float | None = None
        self.latest: dict[str, Any] = {}
        self.or_flags: dict[str, bool | None] = {
            "root_x_ever_crossed": None,
            "v22_unsafe_release": None,
            "v22_fling_eligible": None,
            "v22_frame_contact_after_release": None,
        }
        self.doorframe_contact_force_max: float | None = None
        self.command_rows = 0
        self.command_active_rows = 0
        self.achieved_rows = 0
        self.achieved_active_rows = 0
        self.command_pitch_abs_sum = 0.0
        self.command_roll_abs_sum = 0.0
        self.achieved_pitch_abs_sum = 0.0
        self.achieved_roll_abs_sum = 0.0
        self.stage_usage: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "command_active": 0, "achieved_active": 0})
        self.post_rows = 0
        self.post_hinge_first: float | None = None
        self.post_hinge_last: float | None = None
        self.post_hinge_max: float | None = None
        self.post_contact_rows = 0
        self.post_contact_true_rows = 0
        self.post_stage_max: int | None = None
        self.post_effort_values: list[float] = []
        self.post_base_displacements: list[float] = []
        self.post_yaw_values: list[float] = []
        self.post_action_rows = 0
        self.post_action_missing_rows = 0
        self.post_d_phi_sum = 0.0
        self.post_d_base_sum = 0.0
        self.post_action_valid_rows = 0
        self.post_control_dt_sum = 0.0
        self.post_control_dt_rows = 0

    @staticmethod
    def _set_latest(target: dict[str, Any], key: str, value: Any) -> None:
        if value is not None:
            target[key] = value

    def _update_post(self, row: Mapping[str, Any], step: int) -> None:
        if not self.post_enabled or self.post_trigger_step is None or step < self.post_trigger_step:
            return
        self.post_rows += 1
        self.post_action_rows += 1
        control_dt = _finite_optional(row.get("control_dt"), label="post.control_dt")
        if control_dt is not None:
            self.post_control_dt_sum += control_dt
            self.post_control_dt_rows += 1
        pre_base = _number_list(row.get("post_forced_override_pre_env_base_action"), label="post.pre_base_action")
        post_base = _number_list(row.get("post_delta_post_warp_base_action"), label="post.post_base_action")
        if pre_base is None or post_base is None:
            self.post_action_missing_rows += 1
        else:
            if len(pre_base) != 5 or len(post_base) != 5:
                raise V24Error("post action proof arrays must contain exactly 5 base-action values")
            self.post_action_valid_rows += 1
            self.post_d_phi_sum += sum(abs(post_base[index] - pre_base[index]) for index in (3, 4))
            self.post_d_base_sum += sum(abs(post_base[index] - pre_base[index]) for index in range(3))
        hinge = _finite_optional(row.get("door_hinge_joint_pos"), label="post.hinge")
        if hinge is not None:
            if self.post_hinge_first is None:
                self.post_hinge_first = hinge
            self.post_hinge_last = hinge
            self.post_hinge_max = hinge if self.post_hinge_max is None else max(self.post_hinge_max, hinge)
        contact = row.get("both_contact")
        if isinstance(contact, bool):
            self.post_contact_rows += 1
            self.post_contact_true_rows += int(contact)
        stage = row.get("stage_buf")
        if isinstance(stage, int) and not isinstance(stage, bool):
            self.post_stage_max = stage if self.post_stage_max is None else max(self.post_stage_max, stage)
        effort = _finite_optional(row.get("v22_arm_effort_utilization"), label="post.arm_effort")
        if effort is not None:
            self.post_effort_values.append(effort)
        root = row.get("root_pos_rel")
        if isinstance(root, list) and len(root) >= 2:
            x = finite_number(root[0], label="post.root_pos_rel[0]")
            y = finite_number(root[1], label="post.root_pos_rel[1]")
            self.post_base_displacements.append(math.hypot(x, y))
        yaw = _finite_optional(row.get("root_yaw"), label="post.root_yaw")
        if yaw is not None:
            self.post_yaw_values.append(abs(yaw))

    def update(self, row: Mapping[str, Any]) -> None:
        env_id = row.get("env_id")
        if env_id != self.env_id:
            raise V24Error(f"trace env id disagrees: expected {self.env_id}, got {env_id}")
        step_raw = row.get("step_index")
        if isinstance(step_raw, bool) or not isinstance(step_raw, int):
            raise V24Error(f"trace env{self.env_id} has a non-integer step_index")
        step = int(step_raw)
        self.row_count += 1
        self.first_step = step if self.first_step is None else min(self.first_step, step)
        self.last_step = step if self.last_step is None else max(self.last_step, step)
        stage = row.get("stage_buf")
        if isinstance(stage, int) and not isinstance(stage, bool):
            self.max_stage = stage if self.max_stage is None else max(self.max_stage, stage)
        hinge = _finite_optional(row.get("door_hinge_joint_pos"), label="trace.hinge")
        if hinge is not None:
            self.hinge_first = hinge if self.hinge_first is None else self.hinge_first
            self.hinge_last = hinge
            self.hinge_min = hinge if self.hinge_min is None else min(self.hinge_min, hinge)
            self.hinge_max = hinge if self.hinge_max is None else max(self.hinge_max, hinge)
        velocity = _finite_optional(row.get("door_hinge_joint_vel"), label="trace.hinge_velocity")
        if velocity is not None:
            value = abs(velocity)
            self.hinge_velocity_abs_max = value if self.hinge_velocity_abs_max is None else max(self.hinge_velocity_abs_max, value)
        root = row.get("root_pos_rel")
        if isinstance(root, list) and len(root) >= 2:
            x = finite_number(root[0], label="trace.root_pos_rel[0]")
            y = finite_number(root[1], label="trace.root_pos_rel[1]")
            value = math.hypot(x, y)
            self.root_displacement_max = value if self.root_displacement_max is None else max(self.root_displacement_max, value)
        yaw = _finite_optional(row.get("root_yaw"), label="trace.root_yaw")
        if yaw is not None:
            value = abs(yaw)
            self.yaw_abs_max = value if self.yaw_abs_max is None else max(self.yaw_abs_max, value)
        for key in (
            "crossing_while_holding",
            "hinge_at_crossing",
            "hinge_at_release",
            "root_x_at_release",
            "post_release_body_contact",
            "post_release_body_force_max",
            "v22_release_hinge_velocity_radps",
            "v22_min_hinge_after_release_rad",
            "v22_clearance_strategy",
            "v22_clearance_success",
            "v22_root_clear_step",
        ):
            self._set_latest(self.latest, key, row.get(key))
        for key in self.or_flags:
            value = row.get(key)
            if isinstance(value, bool):
                current = self.or_flags[key]
                self.or_flags[key] = value if current is None else current or value
        force = _finite_optional(row.get("doorframe_contact_force"), label="trace.doorframe_contact_force")
        if force is not None:
            self.doorframe_contact_force_max = force if self.doorframe_contact_force_max is None else max(self.doorframe_contact_force_max, force)

        command_pitch = _finite_optional(row.get("v22_posture_command_pitch_rad"), label="trace.command_pitch")
        command_roll = _finite_optional(row.get("v22_posture_command_roll_rad"), label="trace.command_roll")
        achieved_pitch = _finite_optional(row.get("v22_posture_achieved_pitch_rad"), label="trace.achieved_pitch")
        achieved_roll = _finite_optional(row.get("v22_posture_achieved_roll_rad"), label="trace.achieved_roll")
        if command_pitch is not None and command_roll is not None:
            active = abs(command_pitch) >= POSTURE_SATURATION_THRESHOLD_RAD or abs(command_roll) >= POSTURE_SATURATION_THRESHOLD_RAD
            self.command_rows += 1
            self.command_active_rows += int(active)
            self.command_pitch_abs_sum += abs(command_pitch)
            self.command_roll_abs_sum += abs(command_roll)
            stage_key = str(stage) if isinstance(stage, int) and not isinstance(stage, bool) else "UNKNOWN_STAGE"
            self.stage_usage[stage_key]["rows"] += 1
            self.stage_usage[stage_key]["command_active"] += int(active)
        if achieved_pitch is not None and achieved_roll is not None:
            active = abs(achieved_pitch) >= POSTURE_SATURATION_THRESHOLD_RAD or abs(achieved_roll) >= POSTURE_SATURATION_THRESHOLD_RAD
            self.achieved_rows += 1
            self.achieved_active_rows += int(active)
            self.achieved_pitch_abs_sum += abs(achieved_pitch)
            self.achieved_roll_abs_sum += abs(achieved_roll)
            stage_key = str(stage) if isinstance(stage, int) and not isinstance(stage, bool) else "UNKNOWN_STAGE"
            self.stage_usage[stage_key]["achieved_active"] += int(active)
        self._update_post(row, step)

    def output(self) -> dict[str, Any]:
        if self.row_count == 0:
            return {
                "trace_status": "MISSING_TRACE",
                "missingness": "TRACE_ABSENT_PRE_REGISTERED",
                "row_count": 0,
                "trace_derived_metrics": None,
            }
        behavior = _behavior_category(self.latest, self.or_flags, self.max_stage)
        post = None
        post_missingness = None
        if self.post_enabled:
            if self.post_rows == 0:
                post_missingness = "TRACE_ABSENT_AFTER_TRIGGER"
            else:
                post = {
                    "row_count": self.post_rows,
                    "active_step_count": self.post_rows,
                    "active_duration_s": None if self.post_control_dt_rows == 0 else self.post_control_dt_sum,
                    "control_dt_mean_s": None if self.post_control_dt_rows == 0 else self.post_control_dt_sum / self.post_control_dt_rows,
                    "hinge_progress_rad": None if self.post_hinge_first is None or self.post_hinge_max is None else self.post_hinge_max - self.post_hinge_first,
                    "grasp_retention_fraction": None if self.post_contact_rows == 0 else self.post_contact_true_rows / self.post_contact_rows,
                    "max_stage_after_trigger": self.post_stage_max,
                    "arm_effort_utilization_mean": _mean(self.post_effort_values),
                    "base_displacement_m_max": max(self.post_base_displacements) if self.post_base_displacements else None,
                    "yaw_abs_rad_mean": _mean(self.post_yaw_values),
                    "temporal_action_dose": {
                        "D_phi": None if self.post_action_valid_rows == 0 else self.post_d_phi_sum,
                        "D_base": None if self.post_action_valid_rows == 0 else self.post_d_base_sum,
                        "formula": "observed temporal action-amplitude proxy: sum_t>=switch L1(post_delta_post_warp_base_action[t] - post_forced_override_pre_env_base_action[t]) over posture indices [3:5] and base indices [0:3]",
                        "semantics": "TEMPORAL_ACTION_AMPLITUDE_PROXY; descriptive only",
                        "valid_action_rows": self.post_action_valid_rows,
                        "missing_action_rows": self.post_action_missing_rows,
                    },
                }
        elif self.post_trigger_step is not None:
            post_missingness = "NOT_TRIGGERED"
        return {
            "trace_status": "AVAILABLE",
            "missingness": None,
            "row_count": self.row_count,
            "trace_derived_metrics": {
                "first_step": self.first_step,
                "last_step": self.last_step,
                "max_stage": self.max_stage,
                "hinge_position_min_rad": self.hinge_min,
                "hinge_position_max_rad": self.hinge_max,
                "hinge_velocity_abs_max_radps": self.hinge_velocity_abs_max,
                "planar_displacement_m_max": self.root_displacement_max,
                "yaw_abs_rad_max": self.yaw_abs_max,
                "command_dwell_fraction": None if self.command_rows == 0 else self.command_active_rows / self.command_rows,
                "achieved_dwell_fraction": None if self.achieved_rows == 0 else self.achieved_active_rows / self.achieved_rows,
                "command_pitch_abs_mean_rad": None if self.command_rows == 0 else self.command_pitch_abs_sum / self.command_rows,
                "command_roll_abs_mean_rad": None if self.command_rows == 0 else self.command_roll_abs_sum / self.command_rows,
                "achieved_pitch_abs_mean_rad": None if self.achieved_rows == 0 else self.achieved_pitch_abs_sum / self.achieved_rows,
                "achieved_roll_abs_mean_rad": None if self.achieved_rows == 0 else self.achieved_roll_abs_sum / self.achieved_rows,
                "stage_conditioned_usage": {key: dict(value) for key, value in sorted(self.stage_usage.items())},
                "doorframe_contact_force_max": self.doorframe_contact_force_max,
                "behavior_category": behavior,
                "terminal_and_release_fields": dict(self.latest),
                "boolean_telemetry": dict(self.or_flags),
                "clearance_strategy": self.latest.get("v22_clearance_strategy"),
                "clearance_success": self.latest.get("v22_clearance_success"),
                "unsafe_release": self.or_flags.get("v22_unsafe_release"),
                "fling_eligible": self.or_flags.get("v22_fling_eligible"),
            },
            "post_trigger_metrics": post,
            "post_trigger_missingness": post_missingness,
        }


def _behavior_category(latest: Mapping[str, Any], flags: Mapping[str, bool | None], max_stage: int | None) -> str:
    if max_stage is None or max_stage < 3:
        return "UNCLASSIFIED_INSUFFICIENT_TELEMETRY"
    crossing = latest.get("crossing_while_holding")
    hinge_at_crossing = latest.get("hinge_at_crossing")
    hinge_at_release = latest.get("hinge_at_release")
    strategy = latest.get("v22_clearance_strategy")
    body_contact = latest.get("post_release_body_contact")
    frame_contact = flags.get("v22_frame_contact_after_release")

    # v22_unsafe_release is an ever-latched telemetry bit.  It is retained in
    # the trace summary but cannot, by itself, adjudicate an unsafe event.
    unsafe_event = (
        body_contact is True
        or frame_contact is True
        or strategy == "UNSAFE_RELEASE"
    )
    if unsafe_event:
        return "UNSAFE_RELEASE"
    if crossing is True:
        if hinge_at_release is None:
            return "HOLD_THROUGH_CROSSING/NO_RELEASE_EVENT"
        # A release recorded after a true crossing-while-holding event is a
        # hold release, even when the raw latch reports fling eligibility.
        return "QUIET_HOLD_RELEASE"
    if crossing is False and hinge_at_release is not None:
        pre_crossing_release = (
            isinstance(hinge_at_crossing, (int, float))
            and isinstance(hinge_at_release, (int, float))
            and math.isfinite(float(hinge_at_crossing))
            and math.isfinite(float(hinge_at_release))
            and float(hinge_at_release) < float(hinge_at_crossing)
        )
        continued_opening = (
            isinstance(latest.get("v22_min_hinge_after_release_rad"), (int, float))
            and math.isfinite(float(latest["v22_min_hinge_after_release_rad"]))
            and float(latest["v22_min_hinge_after_release_rad"]) >= float(hinge_at_release)
        )
        if (
            pre_crossing_release
            and continued_opening
            and flags.get("v22_fling_eligible") is True
            and body_contact is not True
            and frame_contact is not True
            and strategy != "UNSAFE_RELEASE"
        ):
            return "CONTROLLED_FLING"
    return "UNCLASSIFIED_INSUFFICIENT_TELEMETRY"


def _stream_trace(path: str | Path, *, env_ids: Sequence[int], post_steps: Mapping[int, int | None] | None = None, post_enabled: bool = False) -> dict[int, dict[str, Any]]:
    expected = set(env_ids)
    if len(expected) != len(env_ids):
        raise V24Error("trace env id contract contains duplicates")
    accumulators = {
        env_id: _TraceAccumulator(
            env_id,
            post_trigger_step=None if post_steps is None else post_steps.get(env_id),
            post_enabled=post_enabled,
        )
        for env_id in env_ids
    }
    for row_index, row in enumerate(iter_json_array(path)):
        if not isinstance(row, Mapping):
            raise V24Error(f"trace row {row_index} is not an object: {path}")
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in expected:
            raise V24Error(f"trace row {row_index} has invalid env_id {env_id!r}: {path}")
        accumulators[env_id].update(row)
    return {env_id: accumulator.output() for env_id, accumulator in accumulators.items() if accumulator.row_count > 0}


def _atlas_points(stratified: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    atlas_path = stratified.get("realized_atlas_path")
    r190_path = stratified.get("r190_receipt_path")
    atlas_payload = require_object(read_json(atlas_path, label="v23 realized atlas"), label="v23 realized atlas")
    r190 = require_object(read_json(r190_path, label="v23 physics-first receipt"), label="v23 physics-first receipt")
    rows = atlas_payload.get("rows")
    if not isinstance(rows, list):
        raise V24Error("v23 realized atlas rows are missing")
    points: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(rows):
        if not isinstance(row, Mapping) or not isinstance(row.get("cell_id"), str):
            raise V24Error(f"v23 atlas row {row_index} is invalid")
        cell = str(row["cell_id"])
        normalized = normalize_realized_dynamics(
            require_object(row.get("realized_params"), label=f"atlas.{cell}.realized_params"),
            angular_surface=USD_DEGREE_SURFACE,
            authority_prefix="V23_MEASURED_ATLAS_RUNTIME_READBACK",
        )
        existing = points.get(cell)
        if existing is not None:
            distance = scaled_distance(existing, normalized)
            if distance > 1e-10:
                raise V24Error(f"v23 atlas cell {cell} has changing normalized mechanics")
        else:
            points[cell] = normalized
    if set(points) != {f"A{index}" for index in range(9)}:
        raise V24Error("v23 realized atlas must cover A0..A8")
    zones = r190.get("zones")
    if not isinstance(zones, Mapping) or not isinstance(zones.get("normal"), Mapping):
        raise V24Error("v23 physics-first receipt lacks normal zone map")
    zone_for_cell: dict[str, str] = {}
    for zone, cells in zones["normal"].items():
        if not isinstance(cells, list):
            raise V24Error("v23 physics-first zone cells must be lists")
        for cell in cells:
            if cell in zone_for_cell:
                raise V24Error(f"v23 physics-first zone map duplicates {cell}")
            zone_for_cell[str(cell)] = str(zone)
    if set(zone_for_cell) != set(points):
        raise V24Error("v23 physics-first zone map does not cover atlas cells")
    return points, zone_for_cell


def _nearest_atlas(observed: Mapping[str, Any], points: Mapping[str, Mapping[str, Any]]) -> tuple[str | None, float | None, str]:
    distances = sorted((scaled_distance(observed, reference), cell) for cell, reference in points.items())
    if not distances:
        raise V24Error("continuous atlas has no reference points")
    best_distance, best_cell = distances[0]
    if len(distances) > 1 and abs(distances[1][0] - best_distance) <= 1e-12:
        return None, best_distance, "UNCLASSIFIED_PHYSICS_AMBIGUOUS"
    if best_distance > CONTINUOUS_OOD_DISTANCE_THRESHOLD:
        return best_cell, best_distance, "UNCLASSIFIED_PHYSICS_OOD"
    return best_cell, best_distance, "CLASSIFIED_CONTINUOUS_NEAREST_ATLAS"


def _load_pooled_context(sources: Mapping[str, Any], freeze_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    producer_receipts = sources["route"].get("producer_receipts")
    if not isinstance(producer_receipts, list):
        raise V24Error("Route-B producer receipts are missing")
    pooled_ref = next((row for row in producer_receipts if isinstance(row, Mapping) and row.get("name") == "pooled48"), None)
    if pooled_ref is None:
        raise V24Error("Route-B pooled48 producer receipt is missing")
    pooled = require_object(read_json(pooled_ref["path"], label="v23 pooled48 receipt"), label="v23 pooled48 receipt")
    jobs = pooled.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != EXPECTED_CANDIDATES:
        raise V24Error("v23 pooled48 receipt must contain exactly 16 jobs")
    context: dict[str, dict[str, Any]] = {}
    for job_index, job in enumerate(jobs):
        if not isinstance(job, Mapping):
            raise V24Error(f"v23 pooled48 job {job_index} is invalid")
        candidate = require_object(job.get("selected_candidate"), label=f"pooled48 job {job_index}.candidate")
        key = _candidate_id(candidate)
        freeze = freeze_by_id.get(key)
        if freeze is None:
            raise V24Error(f"pooled48 job candidate is absent from freeze: {key}")
        receipt = require_object(read_json(job["receipt_path"], label=f"pooled48 job {key} receipt"), label=f"pooled48 job {key} receipt")
        records = read_json(receipt["records_path"], label=f"pooled48 job {key} records")
        if not isinstance(records, list) or len(records) != 48:
            raise V24Error(f"pooled48 job {key} must contain 48 episode records")
        by_env: dict[int, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, Mapping) or not isinstance(record.get("env_id"), int):
                raise V24Error(f"pooled48 job {key} has an invalid episode record")
            env_id = int(record["env_id"])
            if env_id in by_env:
                raise V24Error(f"pooled48 job {key} repeats env {env_id}")
            by_env[env_id] = dict(record)
        if set(by_env) != set(range(48)):
            raise V24Error(f"pooled48 job {key} must cover env ids 0..47")
        trace_path = receipt["raw_trace_path"]
        trace_metrics = _stream_trace(trace_path, env_ids=tuple(range(48)))
        context[key] = {
            "candidate": dict(candidate),
            "freeze": dict(freeze),
            "records": by_env,
            "trace_metrics": trace_metrics,
            "trace_path": rel_path(trace_path),
            "receipt_path": rel_path(job["receipt_path"]),
        }
    if len(context) != EXPECTED_CANDIDATES:
        raise V24Error("pooled48 context did not cover all candidates")
    return context


def _realized_posthoc(sources: Mapping[str, Any], freeze_by_id: Mapping[str, Mapping[str, Any]], pooled: Mapping[str, Mapping[str, Any]], points: Mapping[str, Mapping[str, Any]], zones: Mapping[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    jobs = sources["stratified"].get("jobs")
    if not isinstance(jobs, list) or len(jobs) != EXPECTED_CANDIDATES:
        raise V24Error("v23 stratified receipt must contain exactly 16 jobs")
    records: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    zone_counts: Counter[str] = Counter()
    ood_count = 0
    for job in jobs:
        if not isinstance(job, Mapping):
            raise V24Error("v23 stratified job is invalid")
        candidate = require_object(job.get("selected_candidate"), label="stratified.selected_candidate")
        key = _candidate_id(candidate)
        context = pooled.get(key)
        if context is None:
            raise V24Error(f"stratified candidate has no pooled context: {key}")
        stratified_record = require_object(read_json(job["record_path"], label=f"stratified record {key}"), label=f"stratified record {key}")
        episodes = stratified_record.get("episodes")
        if not isinstance(episodes, list) or len(episodes) != 48:
            raise V24Error(f"stratified record {key} must contain 48 episodes")
        for episode in episodes:
            if not isinstance(episode, Mapping) or not isinstance(episode.get("env_id"), int):
                raise V24Error(f"stratified record {key} episode is invalid")
            env_id = int(episode["env_id"])
            base = context["records"].get(env_id)
            if base is None:
                raise V24Error(f"stratified record {key} env {env_id} missing pooled record")
            trace = context["trace_metrics"].get(env_id)
            raw_dynamics = episode.get("realized_dynamics")
            missing_reason = episode.get("classification_status")
            normalized = None
            nearest_cell = None
            distance = None
            classification = "UNCLASSIFIED_NO_TRACE"
            zone = None
            if raw_dynamics is not None:
                normalized = normalize_realized_dynamics(
                    require_object(raw_dynamics, label=f"realized.{key}.env{env_id}"),
                    angular_surface=TRACE_CONFIG_SURFACE,
                    authority_prefix="V23_TRACE_REALIZED_CONFIGURATION",
                )
                nearest_cell, distance, classification = _nearest_atlas(normalized, points)
                if classification == "CLASSIFIED_CONTINUOUS_NEAREST_ATLAS" and nearest_cell is not None:
                    zone = zones[nearest_cell]
                    zone_counts[zone] += 1
                elif classification == "UNCLASSIFIED_PHYSICS_OOD":
                    ood_count += 1
                missing_reason = classification
            else:
                if env_id in context["trace_metrics"]:
                    raise V24Error(f"stratified record marks env{env_id} no-trace but trace contains rows")
                missing_reason = "UNCLASSIFIED_NO_TRACE"
            reason_counts[str(missing_reason)] += 1
            trace_value = trace if trace is not None else {
                "trace_status": "MISSING_TRACE",
                "missingness": "TRACE_ABSENT_PRE_REGISTERED",
                "row_count": 0,
                "trace_derived_metrics": None,
            }
            if normalized is None and trace_value["trace_status"] != "MISSING_TRACE":
                raise V24Error(f"realized no-trace env{env_id} unexpectedly has trace-derived metrics")
            records.append(
                {
                    "candidate": _candidate_summary({**candidate, "freeze_id": context["freeze"]["freeze_id"]}),
                    "env_id": env_id,
                    "goal_reached": base.get("goal_reached"),
                    "max_stage": base.get("max_stage"),
                    "final_stage": base.get("final_stage"),
                    "realized_dynamics_source_status": episode.get("classification_status"),
                    "realized_mechanics": None if normalized is None else {
                        "canonical": {
                            "damping_rad": normalized["damping_rad"],
                            "stiffness_rad": normalized["stiffness_rad"],
                            "effort_limit_nm": normalized["effort_limit_nm"],
                            "door_mass_kg": normalized["door_mass_kg"],
                        },
                        "source_surface": TRACE_CONFIG_SURFACE,
                        "source_fields": normalized["fields"],
                    },
                    "continuous_atlas": {
                        "nearest_cell": nearest_cell,
                        "distance": distance,
                        "coverage_score": None if distance is None else 1.0 / (1.0 + distance),
                        "ood_threshold": CONTINUOUS_OOD_DISTANCE_THRESHOLD,
                        "ood_status": "TYPED_MISSING" if distance is None else ("OOD_REJECTED" if distance > CONTINUOUS_OOD_DISTANCE_THRESHOLD else "IN_DOMAIN_CONTINUOUS"),
                        "normal_zone": zone,
                    },
                    "classification_status": classification,
                    "trace": trace_value,
                    "terminal_fields": {
                        key: base.get(key)
                        for key in (
                            "crossing_while_holding",
                            "hinge_at_crossing",
                            "hinge_at_release",
                            "root_x_at_release",
                            "post_release_body_contact",
                            "post_release_body_force_max",
                        )
                    },
                }
            )
    if len(records) != EXPECTED_REALIZED_EPISODES:
        raise V24Error(f"realized posthoc produced {len(records)} records, expected 768")
    if reason_counts["UNCLASSIFIED_NO_TRACE"] != 13:
        raise V24Error(f"realized no-trace count changed: {reason_counts['UNCLASSIFIED_NO_TRACE']}")
    payload = {
        "schema": REALIZED_SCHEMA,
        "status": "V24_P0_V23_REALIZED_MECHANICS_REANALYSIS_COMPLETE",
        "scope": "V23_POSTHOC_DESCRIPTIVE",
        "episode_count": len(records),
        "no_trace_episode_count": reason_counts["UNCLASSIFIED_NO_TRACE"],
        "classification_counts": dict(sorted(reason_counts.items())),
        "continuous_zone_counts": dict(sorted(zone_counts.items())),
        "ood_rejected_count": ood_count,
        "hard_gate": "NONE;NO_90_PERCENT_CLASSIFICATION_GATE",
        "comparison_rule": "CONTINUOUS_SCALED_DISTANCE_ONLY;NO_EXACT_TUPLE_EQUALITY",
        "unit_contract": contract_metadata(),
        "records": records,
    }
    return payload, records


def _trace_family_pair(raw_trace_path: str | Path) -> dict[str, Any]:
    raw = absolute(raw_trace_path)
    paired = raw.with_name("stage2_5_step_trace.json")
    return {
        "primary_trace_path": rel_path(raw),
        "paired_stage2_5_trace_path": rel_path(paired),
        "paired_stage2_5_status": "EMPTY_ARRAY" if paired.is_file() and paired.read_bytes()[:64].replace(b" ", b"").replace(b"\n", b"") == b"[]" else "NONEMPTY_OR_UNAVAILABLE",
    }


def _dose_from_record(record: Mapping[str, Any], *, mode: str, trace: Mapping[str, Any] | None) -> dict[str, Any]:
    require_object(record.get("action_proof"), label="intervention action_proof")
    switch = record.get("switch_step")
    triggered = record.get("status") == "TRIGGERED" and isinstance(switch, int) and not isinstance(switch, bool) and switch >= 0
    post_metrics = trace.get("post_trigger_metrics") if isinstance(trace, Mapping) else None
    temporal = post_metrics.get("temporal_action_dose") if isinstance(post_metrics, Mapping) else None
    d_phi = None
    d_base = None
    temporal_status = "TYPED_MISSING_ACTIVE_TRACE"
    if not triggered:
        d_phi = 0.0
        d_base = 0.0
        temporal_status = "NO_ACTIVE_INTERVENTION_WINDOW"
    elif isinstance(temporal, Mapping):
        d_phi = _finite_optional(temporal.get("D_phi"), label="temporal_action_dose.D_phi")
        d_base = _finite_optional(temporal.get("D_base"), label="temporal_action_dose.D_base")
        temporal_status = "TEMPORAL_TRACE_SUM" if d_phi is not None and d_base is not None else "TYPED_MISSING_ACTION_FIELDS"
    readback = require_object(record.get("mode_readback"), label="intervention mode_readback")
    applied = readback.get("applied_profile")
    d_effort = None
    d_effort_per_step_sum = None
    effort_active_duration_s = None
    effort_source = "TYPED_MISSING_EFFORT_SOURCE"
    if isinstance(applied, Mapping) and applied.get("status") == "APPLIED":
        requested = require_object(readback.get("requested_profile"), label="intervention requested_profile")
        baseline = _number_list(requested.get("baseline_effort_limit_nm"), label="baseline_effort_limit_nm")
        actual = _number_list(applied.get("readback_effort_limit_nm"), label="readback_effort_limit_nm")
        if baseline is None or actual is None or len(baseline) != len(actual):
            raise V24Error("applied effort profile has incomplete readback vectors")
        per_step_delta = sum(abs(left - right) for left, right in zip(actual, baseline))
        if triggered and isinstance(post_metrics, Mapping):
            active_steps = post_metrics.get("active_step_count")
            effort_active_duration_s = _finite_optional(post_metrics.get("active_duration_s"), label="post_trigger_metrics.active_duration_s")
            if isinstance(active_steps, int) and not isinstance(active_steps, bool) and active_steps >= 0:
                d_effort_per_step_sum = per_step_delta * active_steps
            if effort_active_duration_s is not None:
                d_effort = per_step_delta * effort_active_duration_s
            else:
                d_effort = None
        elif not triggered:
            d_effort = 0.0
        effort_source = EFFORT_AUTHORITY
    elif isinstance(applied, Mapping) and applied.get("status") in {"NOT_EXECUTED", "NOT_REQUESTED"}:
        d_effort = 0.0
        effort_source = "NO_EFFORT_PROFILE_APPLIED_READBACK"
    elif mode != "HIGHER_EFFORT_RESCUE":
        # These modes have no effort intervention by contract.  The structural
        # zero is observed mode semantics, not an imputed telemetry value.
        d_effort = 0.0
        effort_source = "MODE_HAS_NO_EFFORT_INTERVENTION"
    d_oracle = 0.0
    oracle_per_step = None
    oracle_active_duration_s = None
    if mode == "ORACLE_TANGENTIAL_ASSIST":
        if not triggered:
            d_oracle = 0.0
        else:
            d_oracle = None
            raw_delta = readback.get("delta_raw")
            if not isinstance(raw_delta, list) or not raw_delta:
                raise V24Error("oracle mode readback lacks delta_raw matrix")
            delta_row = raw_delta[int(record.get("env_id", 0))] if len(raw_delta) > int(record.get("env_id", 0)) else raw_delta[0]
            delta_values = _number_list(delta_row, label="oracle.delta_raw.env")
            if delta_values is None or len(delta_values) != 5:
                raise V24Error("oracle delta_raw rows must contain exactly 5 values")
            oracle_per_step = abs(delta_values[3]) + abs(delta_values[4])
            if isinstance(post_metrics, Mapping):
                active_steps = post_metrics.get("active_step_count")
                oracle_active_duration_s = _finite_optional(post_metrics.get("active_duration_s"), label="oracle.active_duration_s")
                if isinstance(active_steps, int) and not isinstance(active_steps, bool) and active_steps >= 0:
                    d_oracle = oracle_per_step * active_steps
            if d_phi is not None or d_base is not None:
                # Oracle posture deltas are source-backed tangential assist,
                # not the RP0 posture dose fields.
                d_phi = 0.0
                d_base = 0.0
                temporal_status = "ORACLE_SEPARATE_DOSE"
    return {
        "D_phi": d_phi,
        "D_base": d_base,
        "D_effort": d_effort,
        "D_effort_per_step_sum": d_effort_per_step_sum,
        "D_effort_active_duration_s": effort_active_duration_s,
        "D_oracle": d_oracle,
        "D_oracle_per_step": oracle_per_step,
        "D_oracle_active_duration_s": oracle_active_duration_s,
        "temporal_action_status": temporal_status,
        "semantics": "TEMPORAL_ACTION_AMPLITUDE_PROXY; descriptive only; no causal intervention or actual-torque interpretation",
        "effort_authority": effort_source,
        "dose_available_fields": [name for name, value in (("D_phi", d_phi), ("D_base", d_base), ("D_effort", d_effort), ("D_oracle", d_oracle)) if value is not None],
        "dose_status": "ZERO_DOSE" if all(value is not None and value == 0.0 for value in (d_phi, d_base, d_effort, d_oracle)) else ("POSITIVE_DOSE" if any(value is not None and value > 0.0 for value in (d_phi, d_base, d_effort, d_oracle)) else "TYPED_MISSING"),
    }


def _terminal_by_env(metrics: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    diagnostics = metrics.get("episode_terminal_diagnostics")
    if not isinstance(diagnostics, list):
        raise V24Error("intervention metrics lack episode_terminal_diagnostics")
    goal_values = metrics.get("episode_goal_reached")
    stage_values = metrics.get("episode_max_stage_reached")
    reason_values = metrics.get("episode_terminal_reasons")
    length_values = metrics.get("episode_lengths")
    for name, values in (("episode_goal_reached", goal_values), ("episode_max_stage_reached", stage_values), ("episode_terminal_reasons", reason_values), ("episode_lengths", length_values)):
        if not isinstance(values, list) or len(values) != len(diagnostics):
            raise V24Error(f"intervention metrics {name} does not align with terminal diagnostics")
    result: dict[int, dict[str, Any]] = {}
    for index, item in enumerate(diagnostics):
        if not isinstance(item, Mapping) or not isinstance(item.get("env_id"), int):
            raise V24Error("intervention terminal diagnostic lacks env_id")
        env_id = int(item["env_id"])
        if env_id in result:
            raise V24Error(f"intervention terminal diagnostics repeat env {env_id}")
        normalized = dict(item)
        normalized["goal_reached"] = goal_values[index]
        normalized["max_stage_reached"] = stage_values[index]
        normalized["terminal_reason"] = reason_values[index]
        normalized["episode_length"] = length_values[index]
        result[env_id] = normalized
    return result


def _intervention_posthoc(sources: Mapping[str, Any], freeze_by_id: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    jobs = sources["intervention"].get("jobs")
    if not isinstance(jobs, list) or len(jobs) != EXPECTED_CANDIDATES * len(INTERVENTION_MODES):
        raise V24Error("v23 intervention jobs are not exact 16x5")
    records: list[dict[str, Any]] = []
    mode_counts: dict[str, Counter[str]] = {mode: Counter() for mode in INTERVENTION_MODES}
    mode_outcome: dict[str, dict[str, Any]] = {mode: {"goal_reached": 0, "release_observed": 0, "release_no_event": 0, "positive_dose_goal_reached": 0, "positive_dose_count": 0, "zero_dose_count": 0, "trace_available_count": 0, "trace_missing_count": 0} for mode in INTERVENTION_MODES}
    for job in jobs:
        if not isinstance(job, Mapping):
            raise V24Error("v23 intervention job is invalid")
        mode = job.get("mode")
        if mode not in INTERVENTION_MODES:
            raise V24Error(f"unknown intervention mode: {mode}")
        candidate = require_object(job.get("selected_candidate"), label="intervention.selected_candidate")
        key = _candidate_id(candidate)
        freeze = freeze_by_id.get(key)
        if freeze is None:
            raise V24Error(f"intervention candidate is absent from freeze: {key}")
        receipt = require_object(read_json(job["receipt_path"], label=f"intervention job {key}:{mode} receipt"), label=f"intervention job {key}:{mode} receipt")
        records_payload = require_object(read_json(receipt["intervention_records_path"], label=f"intervention job {key}:{mode} records"), label=f"intervention job {key}:{mode} records")
        raw_records = records_payload.get("records")
        if not isinstance(raw_records, list) or len(raw_records) != 16:
            raise V24Error(f"intervention job {key}:{mode} must contain 16 records")
        metrics = require_object(read_json(receipt["metrics_path"], label=f"intervention job {key}:{mode} metrics"), label=f"intervention job {key}:{mode} metrics")
        terminal = _terminal_by_env(metrics)
        by_env: dict[int, Mapping[str, Any]] = {}
        post_steps: dict[int, int | None] = {}
        for raw in raw_records:
            if not isinstance(raw, Mapping) or not isinstance(raw.get("env_id"), int):
                raise V24Error(f"intervention job {key}:{mode} record lacks env_id")
            env_id = int(raw["env_id"])
            if env_id in by_env:
                raise V24Error(f"intervention job {key}:{mode} repeats env {env_id}")
            by_env[env_id] = raw
            switch = raw.get("switch_step")
            if isinstance(switch, bool) or not isinstance(switch, int):
                raise V24Error(f"intervention job {key}:{mode} switch_step is not an integer")
            # Preserve -1 as an explicit NOT_TRIGGERED sentinel so a
            # trace-available non-triggered row is not confused with absent
            # post-trigger telemetry.
            post_steps[env_id] = switch
        if set(by_env) != set(range(16)):
            raise V24Error(f"intervention job {key}:{mode} must cover env ids 0..15")
        trace_path = receipt["raw_trace_path"]
        trace_metrics = _stream_trace(trace_path, env_ids=tuple(range(16)), post_steps=post_steps, post_enabled=True)
        family = _trace_family_pair(trace_path)
        for env_id in range(16):
            source = by_env[env_id]
            terminal_fields = terminal.get(env_id, {})
            trace = trace_metrics.get(env_id)
            dose = _dose_from_record(source, mode=str(mode), trace=trace)
            status = source.get("status")
            mode_counts[mode][str(status)] += 1
            if dose["dose_status"] == "ZERO_DOSE":
                mode_outcome[mode]["zero_dose_count"] += 1
            elif dose["dose_status"] == "POSITIVE_DOSE":
                mode_outcome[mode]["positive_dose_count"] += 1
            goal = terminal_fields.get("goal_reached")
            if goal is True:
                mode_outcome[mode]["goal_reached"] += 1
            if terminal_fields.get("hinge_at_release") is None:
                mode_outcome[mode]["release_no_event"] += 1
            else:
                mode_outcome[mode]["release_observed"] += 1
            if dose["dose_status"] == "POSITIVE_DOSE" and goal is True:
                mode_outcome[mode]["positive_dose_goal_reached"] += 1
            if trace is None:
                mode_outcome[mode]["trace_missing_count"] += 1
                trace_payload = {
                    "trace_status": "MISSING_TRACE",
                    "missingness": "TRACE_ABSENT_PRE_REGISTERED",
                    "trace_derived_metrics": None,
                    "post_trigger_metrics": None,
                }
            else:
                mode_outcome[mode]["trace_available_count"] += 1
                trace_payload = trace
            records.append(
                {
                    "candidate": _candidate_summary({**candidate, "freeze_id": freeze["freeze_id"]}),
                    "mode": mode,
                    "env_id": env_id,
                    "status": status,
                    "switch_step": source.get("switch_step"),
                    "trigger_observed": status == "TRIGGERED",
                    "dose": dose,
                    "outcome": {
                        "goal_reached": terminal_fields.get("goal_reached"),
                        "max_stage_reached": terminal_fields.get("max_stage_reached"),
                        "terminal_reason": terminal_fields.get("terminal_reason"),
                        "crossing_while_holding": terminal_fields.get("crossing_while_holding"),
                        "hinge_at_crossing": terminal_fields.get("hinge_at_crossing"),
                        "hinge_at_release": terminal_fields.get("hinge_at_release"),
                        "root_x_at_release": terminal_fields.get("root_x_at_release"),
                        "post_release_body_contact": terminal_fields.get("post_release_body_contact"),
                        "post_release_body_force_max": terminal_fields.get("post_release_body_force_max"),
                        "trace_derived": trace_payload,
                    },
                    "trace_family": family,
                    "inference_label": FORWARD_LABEL,
                    "excluded_claims": [
                        "NO_CAUSAL_EFFECT_CLAIM",
                        "NO_EXACT_STATE_CLONE",
                        "NO_RECURRENT_STATE_RESTORE",
                        "NO_ACTUAL_PHYSX_TORQUE_CLAIM",
                    ],
                }
            )
    if len(records) != EXPECTED_INTERVENTION_RECORDS:
        raise V24Error(f"intervention posthoc produced {len(records)} records, expected 1280")
    aggregates: dict[str, Any] = {}
    for mode in INTERVENTION_MODES:
        counts = mode_counts[mode]
        summary = dict(mode_outcome[mode])
        summary.update({"record_count": sum(counts.values()), "status_counts": dict(sorted(counts.items())), "effect_denominator_excludes_zero_dose": True, "inference_label": FORWARD_LABEL})
        if summary["record_count"] != 256:
            raise V24Error(f"intervention mode {mode} count is not 256")
        aggregates[mode] = summary
    payload = {
        "schema": INTERVENTION_SCHEMA,
        "status": "V24_P0_V23_INTERVENTION_OUTCOME_ADJUDICATION_COMPLETE",
        "scope": "V23_POSTHOC_DESCRIPTIVE",
        "record_count": len(records),
        "candidate_count": EXPECTED_CANDIDATES,
        "modes": list(INTERVENTION_MODES),
        "records_per_mode": 256,
        "dose_formulas": {
            "D_phi": "observed temporal action-amplitude proxy: sum_t>=switch L1(post_delta_post_warp_base_action[t][3:5] - post_forced_override_pre_env_base_action[t][3:5])",
            "D_base": "observed temporal action-amplitude proxy: sum_t>=switch L1(post_delta_post_warp_base_action[t][0:3] - post_forced_override_pre_env_base_action[t][0:3])",
            "D_effort": "observed configured-limit proxy: sum_t>=switch control_dt[t] * sum_j(abs(readback_effort_limit_nm[j] - baseline_effort_limit_nm[j])); not actual torque",
            "D_effort_per_step_sum": "sum_t>=switch sum_j(abs(readback_effort_limit_nm[j] - baseline_effort_limit_nm[j]))",
            "D_oracle": "sum_t>=switch L1(delta_raw[env_id][3:5]) from source mode_readback; kept separate from D_phi/D_base",
            "zero_dose_rule": "retain zero-dose episodes in population; exclude them from treatment-effect denominators",
            "semantics": "TEMPORAL_ACTION_AMPLITUDE_PROXY; descriptive only; no causal intervention or actual-torque interpretation",
        },
        "dose_surface_by_mode": {
            "FULL": "no active intervention window; D_phi=D_base=D_effort=D_oracle=0",
            "ACUTE_RP0": "source applies raw base indices [3:5] to zero; D_phi is the observed [3:5] temporal amplitude proxy",
            "BASE0_AT_GRASP": "source applies raw base indices [3:5] to zero after stable-grasp latch; D_phi is the observed [3:5] temporal amplitude proxy; D_base covers [0:3] and remains separate",
            "HIGHER_EFFORT_RESCUE": "source leaves raw base action unchanged; D_effort is the configured solver-limit active-duration proxy",
            "ORACLE_TANGENTIAL_ASSIST": "source applies explicit oracle delta_raw; D_oracle is reported separately and is not folded into D_phi or D_base",
        },
        "D_effort_authority": EFFORT_AUTHORITY,
        "inference_label": FORWARD_LABEL,
        "aggregates": aggregates,
        "records": records,
    }
    return payload, records


def _hinge_progress_for_fp(row: Mapping[str, Any], *, mode: str) -> float | None:
    outcome = require_object(row.get("outcome"), label=f"{mode} intervention outcome")
    trace = outcome.get("trace_derived")
    if not isinstance(trace, Mapping):
        return None
    metrics = trace.get("trace_derived_metrics")
    if not isinstance(metrics, Mapping):
        return None
    if mode == "ACUTE_RP0":
        post = trace.get("post_trigger_metrics")
        value = post.get("hinge_progress_rad") if isinstance(post, Mapping) else None
        return _finite_optional(value, label="FP_phi.acute_hinge_progress_rad")
    minimum = _finite_optional(metrics.get("hinge_position_min_rad"), label="FP_phi.full_hinge_min_rad")
    maximum = _finite_optional(metrics.get("hinge_position_max_rad"), label="FP_phi.full_hinge_max_rad")
    if minimum is None or maximum is None:
        return None
    return maximum - minimum


def _paired_fp_phi(intervention_records: Sequence[Mapping[str, Any]], *, low_progress_min_rad: float) -> tuple[dict[str, Any], dict[tuple[str, int], bool | None]]:
    by_key: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in intervention_records:
        candidate = require_object(row.get("candidate"), label="intervention candidate for FP_phi")
        mode = row.get("mode")
        if mode not in {"FULL", "ACUTE_RP0"}:
            continue
        key = (str(candidate.get("candidate_id")), int(row["env_id"]))
        if mode in by_key[key]:
            raise V24Error(f"FP_phi pair repeats {key} mode {mode}")
        by_key[key][str(mode)] = row
    if len(by_key) != 256:
        raise V24Error(f"FP_phi requires 256 paired FULL/ACUTE rows, got {len(by_key)}")
    missing: Counter[str] = Counter()
    pair_rows: list[dict[str, Any]] = []
    fp_by_key: dict[tuple[str, int], bool | None] = {}
    paired_count = 0
    positive_count = 0
    high_use_count = 0
    false_positive_count = 0
    for key in sorted(by_key):
        pair = by_key[key]
        full = pair.get("FULL")
        acute = pair.get("ACUTE_RP0")
        if full is None:
            missing["FULL_PAIR_MISSING"] += 1
            fp_by_key[key] = None
            continue
        if acute is None:
            missing["ACUTE_PAIR_MISSING"] += 1
            fp_by_key[key] = None
            continue
        full_progress = _hinge_progress_for_fp(full, mode="FULL")
        acute_progress = _hinge_progress_for_fp(acute, mode="ACUTE_RP0")
        if full_progress is None:
            missing["FULL_HINGE_PROGRESS_MISSING"] += 1
        if acute_progress is None:
            missing["ACUTE_HINGE_PROGRESS_MISSING"] += 1
        full_outcome = require_object(full.get("outcome"), label="FULL FP_phi outcome")
        full_trace = full_outcome.get("trace_derived")
        full_metrics = full_trace.get("trace_derived_metrics") if isinstance(full_trace, Mapping) else None
        full_use = full_metrics.get("command_dwell_fraction") if isinstance(full_metrics, Mapping) else None
        if not isinstance(full_use, (int, float)) or not math.isfinite(float(full_use)):
            full_use = None
            missing["FULL_POSTURE_USE_MISSING"] += 1
        margin = None if full_progress is None or acute_progress is None else full_progress - acute_progress
        positive = None if margin is None else margin >= low_progress_min_rad
        if margin is not None:
            paired_count += 1
            positive_count += int(bool(positive))
        high_use = None if full_use is None else float(full_use) >= 0.5
        false_positive = None if high_use is None or positive is None else bool(high_use and not positive)
        if high_use is True:
            high_use_count += 1
        if false_positive is True:
            false_positive_count += 1
        fp_by_key[key] = false_positive
        pair_rows.append({
            "candidate_id": key[0],
            "env_id": key[1],
            "full_hinge_progress_rad": full_progress,
            "acute_hinge_progress_rad": acute_progress,
            "full_minus_acute_hinge_progress_rad": margin,
            "full_posture_use_fraction": full_use,
            "positive_posture_utility": positive,
            "high_posture_use": high_use,
            "FP_phi": false_positive,
        })
    return {
        "value": None if high_use_count == 0 else false_positive_count / high_use_count,
        "paired_denominator": paired_count,
        "positive_utility_count": positive_count,
        "high_posture_use_denominator": high_use_count,
        "false_positive_count": false_positive_count,
        "utility_threshold_rad": low_progress_min_rad,
        "utility_threshold_source": rel_path(V23_P05_BANDS_PATH),
        "pair_window": "same candidate_id/env_id across FULL and ACUTE_RP0 intervention traces",
        "missing_reasons": dict(sorted(missing.items())),
        "pair_count": len(pair_rows),
        "pairs": pair_rows,
    }, fp_by_key


def _posture_posthoc(realized_records: Sequence[Mapping[str, Any]], intervention_records: Sequence[Mapping[str, Any]], *, low_progress_min_rad: float) -> dict[str, Any]:
    usage_by_group: dict[str, list[float]] = defaultdict(list)
    achieved_by_group: dict[str, list[float]] = defaultdict(list)
    stage_usage: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"rows": 0, "command_active": 0, "achieved_active": 0}))
    clearance: Counter[tuple[str, str]] = Counter()
    behavior: Counter[str] = Counter()
    behavior_cross_tab: Counter[tuple[str, str, str, str, str]] = Counter()
    behavior_unclassified_reasons: Counter[str] = Counter()
    zone_values: dict[str, list[float]] = defaultdict(list)
    zone_missing: Counter[str] = Counter()
    posture_records: list[dict[str, Any]] = []
    fp_phi, fp_by_key = _paired_fp_phi(intervention_records, low_progress_min_rad=low_progress_min_rad)
    for row in realized_records:
        candidate = require_object(row.get("candidate"), label="realized candidate")
        group = str(candidate["posture"])
        zone_info = require_object(row.get("continuous_atlas"), label="realized continuous_atlas")
        normal_zone = zone_info.get("normal_zone")
        trace = require_object(row.get("trace"), label="realized trace summary")
        metrics = trace.get("trace_derived_metrics")
        pair_key = (str(candidate["candidate_id"]), int(row["env_id"]))
        fp_value = fp_by_key.get(pair_key)
        if not isinstance(metrics, Mapping):
            category = "UNCLASSIFIED_INSUFFICIENT_TELEMETRY"
            behavior[category] += 1
            behavior_unclassified_reasons["TRACE_ABSENT_PRE_REGISTERED"] += 1
            clearance_key = ("TYPED_MISSING", "TYPED_MISSING")
            clearance[clearance_key] += 1
            behavior_cross_tab[(category, "TYPED_MISSING", "TYPED_MISSING", "TYPED_MISSING", "TYPED_MISSING")] += 1
            posture_records.append({
                "candidate": candidate,
                "env_id": row["env_id"],
                "normal_zone": normal_zone,
                "posture_use_fraction": None,
                "achieved_use_fraction": None,
                "S_phi": None,
                "FP_phi": fp_value,
                "behavior_category": category,
                "clearance": {"strategy": None, "post_release_body_contact": None},
                "missingness": "TRACE_ABSENT_PRE_REGISTERED",
            })
            continue
        usage = metrics.get("command_dwell_fraction")
        achieved = metrics.get("achieved_dwell_fraction")
        if isinstance(usage, (int, float)) and math.isfinite(float(usage)):
            usage = float(usage)
            usage_by_group[group].append(usage)
            if normal_zone in {"E0", "E1"}:
                zone_values[str(normal_zone)].append(usage)
            else:
                zone_missing["NON_E0_E1_ZONE"] += 1
        else:
            usage = None
            zone_missing["POSTURE_USE_MISSING"] += 1
        if isinstance(achieved, (int, float)) and math.isfinite(float(achieved)):
            achieved = float(achieved)
            achieved_by_group[group].append(achieved)
        else:
            achieved = None
        stage_values_by_stage = metrics.get("stage_conditioned_usage")
        if isinstance(stage_values_by_stage, Mapping):
            for stage, stage_values in stage_values_by_stage.items():
                if not isinstance(stage_values, Mapping):
                    continue
                for key in ("rows", "command_active", "achieved_active"):
                    value = stage_values.get(key)
                    if isinstance(value, int) and not isinstance(value, bool):
                        stage_usage[group][str(stage)][key] += value
        category = metrics.get("behavior_category")
        if category not in REQUIRED_BEHAVIOR_CATEGORIES:
            category = "UNCLASSIFIED_INSUFFICIENT_TELEMETRY"
            behavior_unclassified_reasons["BEHAVIOR_CATEGORY_MISSING_OR_UNSUPPORTED"] += 1
        behavior[category] += 1
        terminal = metrics.get("terminal_and_release_fields")
        terminal = terminal if isinstance(terminal, Mapping) else {}
        strategy = metrics.get("clearance_strategy")
        contact = terminal.get("post_release_body_contact")
        frame_contact = (metrics.get("boolean_telemetry") or {}).get("v22_frame_contact_after_release") if isinstance(metrics.get("boolean_telemetry"), Mapping) else None
        success = metrics.get("clearance_success")
        clearance_key = (str(strategy) if strategy is not None else "TYPED_MISSING", str(contact) if contact is not None else "TYPED_MISSING")
        clearance[clearance_key] += 1
        behavior_cross_tab[(category, str(strategy) if strategy is not None else "TYPED_MISSING", str(success) if success is not None else "TYPED_MISSING", str(frame_contact) if frame_contact is not None else "TYPED_MISSING", str(contact) if contact is not None else "TYPED_MISSING")] += 1
        if category == "UNCLASSIFIED_INSUFFICIENT_TELEMETRY":
            behavior_unclassified_reasons["EVENT_FIELDS_INCOMPLETE"] += 1
        posture_records.append({
            "candidate": candidate,
            "env_id": row["env_id"],
            "normal_zone": normal_zone,
            "posture_use_fraction": usage,
            "achieved_use_fraction": achieved,
            "S_phi": None,
            "FP_phi": fp_value,
            "behavior_category": category,
            "clearance": {"strategy": strategy, "post_release_body_contact": contact, "frame_contact_after_release": frame_contact, "success": success},
            "planar_yaw": {"planar_displacement_m_max": metrics.get("planar_displacement_m_max"), "yaw_abs_rad_max": metrics.get("yaw_abs_rad_max")},
            "stage_conditioned_usage": metrics.get("stage_conditioned_usage"),
            "missingness": None,
        })
    full_mean = _mean(usage_by_group.get("FULL", []))
    rp0_mean = _mean(usage_by_group.get("RP0", []))
    e0_values = zone_values.get("E0", [])
    e1_values = zone_values.get("E1", [])
    e0_mean = _mean(e0_values)
    e1_mean = _mean(e1_values)
    s_phi_value = None if e0_mean is None or e1_mean is None else e1_mean - e0_mean
    s_phi = {
        "value": s_phi_value,
        "available": s_phi_value is not None,
        "formula": "mean(command_dwell_fraction | realized continuous_atlas.normal_zone=E1) - mean(command_dwell_fraction | realized continuous_atlas.normal_zone=E0)",
        "denominators": {"E0": len(e0_values), "E1": len(e1_values)},
        "means": {"E0": e0_mean, "E1": e1_mean},
        "missing_reasons": dict(sorted(zone_missing.items())),
        "source": "realized continuous_atlas.normal_zone; no nominal door_regime substitution",
    }
    for row in posture_records:
        row["S_phi"] = s_phi_value if row["posture_use_fraction"] is not None and s_phi_value is not None else None
    payload = {
        "schema": POSTURE_SCHEMA,
        "status": "V24_P0_V23_POSTURE_BEHAVIOR_ANALYSIS_COMPLETE",
        "scope": "V23_POSTHOC_DESCRIPTIVE",
        "episode_count": len(posture_records),
        "formula_metadata": {
            "posture_command_dwell": "count(abs(command_pitch_rad)>=0.35 or abs(command_roll_rad)>=0.35) / rows with both command fields",
            "posture_achieved_dwell": "count(abs(achieved_pitch_rad)>=0.35 or abs(achieved_roll_rad)>=0.35) / rows with both achieved fields",
            "saturation_threshold_rad": POSTURE_SATURATION_THRESHOLD_RAD,
            "S_phi": s_phi["formula"],
            "FP_phi": "mean(1[full posture use >= 0.5 and FULL-minus-ACUTE hinge progress < low_progress_min_rad] | paired FULL/ACUTE common rows with high posture use)",
            "FP_phi_pair_window": fp_phi["pair_window"],
            "FP_phi_utility_threshold_rad": low_progress_min_rad,
            "FP_phi_utility_threshold_source": rel_path(V23_P05_BANDS_PATH),
            "planar_yaw_compensation": "trace planar displacement hypot(root_x_rel,root_y_rel) and abs(root_yaw), descriptive",
            "behavior_release_threshold_radps": QUIET_RELEASE_VELOCITY_THRESHOLD_RADPS,
            "behavior_semantics": {
                "unsafe_release": "post_release_body_contact=true OR v22_frame_contact_after_release=true OR clearance_strategy=UNSAFE_RELEASE; v22_unsafe_release ever-latch alone is not sufficient",
                "hold_through_crossing": "crossing_while_holding=true AND hinge_at_release is null",
                "quiet_hold_release": "crossing_while_holding=true AND hinge_at_release is observed AND unsafe_release=false",
                "controlled_fling": "crossing_while_holding=false AND release precedes crossing AND min hinge after release is non-decreasing AND v22_fling_eligible=true AND unsafe_release=false",
                "unclassified": "required event fields are absent or contradictory",
            },
        },
        "posture_use_by_mode": {
            "FULL": {"count": len(usage_by_group.get("FULL", [])), "mean": full_mean},
            "RP0": {"count": len(usage_by_group.get("RP0", [])), "mean": rp0_mean},
        },
        "S_phi": s_phi_value,
        "S_phi_metadata": s_phi,
        "FP_phi": fp_phi["value"],
        "FP_phi_metadata": fp_phi,
        "stage_conditioned_usage": {group: {stage: values for stage, values in sorted(stage_values.items())} for group, stage_values in sorted(stage_usage.items())},
        "clearance_association": {f"strategy={strategy};contact={contact}": count for (strategy, contact), count in sorted(clearance.items())},
        "behavior_category_counts": {category: behavior.get(category, 0) for category in REQUIRED_BEHAVIOR_CATEGORIES},
        "behavior_categories": list(REQUIRED_BEHAVIOR_CATEGORIES),
        "behavior_cross_tab": {f"category={category};strategy={strategy};clearance_success={success};frame_contact={frame};body_contact={body}": count for (category, strategy, success, frame, body), count in sorted(behavior_cross_tab.items())},
        "behavior_unclassified_reasons": dict(sorted(behavior_unclassified_reasons.items())),
        "records": posture_records,
    }
    return payload


def build_posthoc(*, output_dir: str | Path = V24_P0_ROOT, sources: Mapping[str, Any] | None = None) -> dict[str, Any]:
    loaded = _load_sources() if sources is None else dict(sources)
    freeze_by_id, _route_by_id = _freeze_maps(loaded)
    conflict = _warm_identity_conflict(freeze_by_id)
    points, zones = _atlas_points(loaded["stratified"])
    pooled = _load_pooled_context(loaded, freeze_by_id)
    realized_payload, realized_records = _realized_posthoc(loaded, freeze_by_id, pooled, points, zones)
    intervention_payload, _intervention_records = _intervention_posthoc(loaded, freeze_by_id)
    p05_bands = require_object(loaded.get("p05_bands"), label="P0.5 band receipt")
    low_progress_min_rad = finite_number(p05_bands.get("low_progress_min_rad"), label="p05_bands.low_progress_min_rad")
    posture_payload = _posture_posthoc(realized_records, _intervention_records, low_progress_min_rad=low_progress_min_rad)
    out_dir = absolute(output_dir)
    files = {
        "realized": write_json(out_dir / "V23_REALIZED_MECHANICS_REANALYSIS.json", realized_payload, overwrite=True),
        "intervention": write_json(out_dir / "V23_INTERVENTION_OUTCOME_ADJUDICATION.json", intervention_payload, overwrite=True),
        "posture": write_json(out_dir / "V23_POSTURE_BEHAVIOR_ANALYSIS.json", posture_payload, overwrite=True),
    }
    top = {
        "schema": TOP_LEVEL_SCHEMA,
        "status": "V24_P0_V23_POSTHOC_DESCRIPTIVE_COMPLETE",
        "scope": "V23_POSTHOC_IS_DESCRIPTIVE_ONLY",
        "source_artifacts": {name: rel_path(path) for name, path in (("route_b", V23_ROUTE_B_PATH), ("stratified", V23_STRATIFIED_PATH), ("intervention", V23_INTERVENTION_PATH), ("candidate_freeze", V23_FREEZE_PATH), ("holdout", V23_HOLDOUT_PATH), ("final_analysis", V23_FINAL_PATH), ("p05_bands", V23_P05_BANDS_PATH))},
        "unit_contract": contract_metadata(),
        "realized_episode_count": realized_payload["episode_count"],
        "realized_no_trace_episode_count": realized_payload["no_trace_episode_count"],
        "intervention_record_count": intervention_payload["record_count"],
        "intervention_mode_counts": {mode: intervention_payload["aggregates"][mode]["record_count"] for mode in INTERVENTION_MODES},
        "output_files": {name: rel_path(path) for name, path in files.items()},
        "warm_start_identity_conflict": conflict,
        "scientific_boundaries": [
            "V23 posthoc is DESCRIPTIVE and does not upgrade H3 or H5.",
            "No exact state clone or recurrent restore is claimed.",
            "Configured solver-limit effort readback is not actual PhysX torque.",
            "Missing telemetry remains typed missing and is never replaced by false or zero.",
            "No confirmed E2 or causal intervention claim is produced.",
        ],
        "excluded_claims": [
            "H3_CAUSAL_UPGRADE",
            "H5_CAUSAL_UPGRADE",
            "EXACT_STATE_CLONE",
            "RECURRENT_STATE_RESTORE",
            "ACTUAL_PHYSX_TORQUE",
            "POLICY_QUALITY_OR_RELEASE",
        ],
    }
    top_path = write_json(out_dir / "V23_POSTHOC_ANALYSIS.json", top, overwrite=True)
    markdown = _markdown_summary(top, realized_payload, intervention_payload, posture_payload)
    md_path = write_text(out_dir / "V23_POSTHOC_ANALYSIS.md", markdown, overwrite=True)
    result = dict(top)
    result["output_files"] = {**result["output_files"], "top_level_json": rel_path(top_path), "top_level_markdown": rel_path(md_path)}
    return result


def _markdown_summary(top: Mapping[str, Any], realized: Mapping[str, Any], intervention: Mapping[str, Any], posture: Mapping[str, Any]) -> str:
    lines = [
        "# V23 Posthoc Analysis (base_v24 P0)",
        "",
        "Status: `V24_P0_V23_POSTHOC_DESCRIPTIVE_COMPLETE`",
        "",
        "This report is descriptive only. It does not upgrade H3/H5, claim exact state-clone or recurrent restore, or treat configured solver-limit readback as actual PhysX torque.",
        "",
        "## Cardinality",
        "",
        f"- Realized episodes: **{realized['episode_count']}**; typed no-trace rows: **{realized['no_trace_episode_count']}**.",
        f"- Intervention records: **{intervention['record_count']}**; each of the five modes has **256** records.",
        f"- Continuous OOD rejections: **{realized['ood_rejected_count']}**; no 90% classification gate is applied.",
        "",
        "## Unit contract",
        "",
        "`DoorMechanicsUnitContractV1` is the sole conversion source. Canonical angular values are radians; USD degree-surface damping/stiffness readbacks are multiplied by pi/180. Effort and mass pass through with source authority. Cross-artifact comparisons use continuous scaled distance, never exact tuple equality.",
        "",
        "## Intervention and behavior boundaries",
        "",
        f"Every intervention row is labeled `{FORWARD_LABEL}`. Zero-dose rows remain in the population and are excluded from treatment-effect denominators. D_effort authority is `{EFFORT_AUTHORITY}`.",
        "",
        "Temporal dose uses the active trace window from the observed switch: D_phi and D_base are per-step L1 sums, D_effort is active-duration-weighted configured solver-limit delta, and ORACLE_TANGENTIAL_ASSIST is reported as separate D_oracle.",
        "",
        f"S_phi (realized normal zones) = **{posture['S_phi']}**; E0 denominator **{posture['S_phi_metadata']['denominators']['E0']}**, E1 denominator **{posture['S_phi_metadata']['denominators']['E1']}**.",
        f"FP_phi (paired FULL/ACUTE) = **{posture['FP_phi']}**; paired denominator **{posture['FP_phi_metadata']['paired_denominator']}**, high-use denominator **{posture['FP_phi_metadata']['high_posture_use_denominator']}**, utility band **{posture['FP_phi_metadata']['utility_threshold_rad']} rad**.",
        f"Behavior categories: `{', '.join(posture['behavior_categories'])}`.",
        "",
        "## Warm-start identity note",
        "",
        f"The provisional candidate `{top['warm_start_identity_conflict']['candidate_id']}` retains the formal `warm_head_reset` identity; its filename token is reported without silently relabeling it as v22 warm.",
        "",
        "Missing telemetry is typed missing and never converted to false or zero.",
        "",
    ]
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(V24_P0_ROOT), help="canonical v24 P0 output directory")
    parser.add_argument("--write", action="store_true", help="write canonical artifacts; without this flag only validate source cardinality")
    parser.add_argument("--dry-run", action="store_true", help="validate frozen source receipts without streaming traces")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if args.write and args.dry_run:
        raise V24Error("--write and --dry-run are mutually exclusive")
    sources = _load_sources()
    if args.dry_run or not args.write:
        print(json.dumps({"status": "PLAN_ONLY", "output_dir": rel_path(args.output_dir), "realized_episode_count": EXPECTED_REALIZED_EPISODES, "intervention_record_count": EXPECTED_INTERVENTION_RECORDS}, indent=2))
        return 0
    result = build_posthoc(output_dir=args.output_dir, sources=sources)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V24Error as exc:
        print(f"V24_POSTHOC_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
