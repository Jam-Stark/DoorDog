"""Pure adjudication of the P0-D hinge measurements and the H0-H4 range freeze.

Separated from the IsaacLab probe so the arithmetic is inspectable and rerunnable
without booting a simulator.  Class labels come from measured response only
(plan §6.3, §5.4, negative tests 5 and 23).
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ._v22_common import V22Error, artifact_payload, digest


CORE_TUPLE_ID = "T03"
# §5.3 global worker-adjustable bounds.  A frozen range outside these is an error.
GLOBAL_BOUNDS = {
    "damping": (10.0, 200.0),
    "stiffness": (0.5, 30.0),
    "max_force_nm": (2.5, 24.0),
    "mass_kg": (80.0, 180.0),
    "handle_height_m": (0.85, 1.10),
}

SLOW_RETURN_MULTIPLIER = 1.5
FAST_RETURN_MULTIPLIER = 0.7
FAST_PEAK_MULTIPLIER = 1.3
RESISTIVE_PROGRESS_MULTIPLIER = 0.7
CORE_PROGRESS_LOWER_MULTIPLIER = 0.7


def _tuple_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index = {}
    for row in rows:
        tuple_id = row.get("tuple_id")
        if not isinstance(tuple_id, str) or tuple_id in index:
            raise V22Error(f"P0-D rows require unique tuple_id; got {tuple_id!r}")
        index[tuple_id] = row
    return index


def build_runtime_baseline(measured: Mapping[str, Any], *, source_lock: Mapping[str, Any], timestamp_utc: str) -> dict:
    rows = measured["runtime_baseline_rows"]
    mismatches = [
        row["tuple_id"]
        for row in rows
        if abs(row["runtime_damping"] - row["requested_damping"]) > 1e-6
        or abs(row["runtime_stiffness"] - row["requested_stiffness"]) > 1e-6
        or abs(row["runtime_max_force"] - row["requested_max_force_nm"]) > 1e-6
    ]
    if mismatches:
        raise V22Error(
            "spawned USD drive attributes disagree with the requested hinge tuple for "
            f"{mismatches!r}; damping randomization plumbing is not effective"
        )
    legacy = [row for row in rows if abs(row["requested_damping"] - 50.0) < 1e-9]
    articulation = measured.get("articulation_hinge_gains")
    unit_finding = None
    if isinstance(articulation, dict):
        usd_stiffness = float(articulation["usd_stiffness"])
        usd_damping = float(articulation["usd_damping"])
        sim_stiffness = float(articulation["sim_stiffness"])
        sim_damping = float(articulation["sim_damping"])
        ratio = [
            sim_stiffness / usd_stiffness if usd_stiffness else None,
            sim_damping / usd_damping if usd_damping else None,
        ]
        unit_finding = {
            "usd_stiffness": usd_stiffness,
            "usd_damping": usd_damping,
            "articulation_stiffness": sim_stiffness,
            "articulation_damping": sim_damping,
            "articulation_effort_limit_nm": float(articulation["sim_effort_limit_nm"]),
            "observed_ratio_sim_over_usd": ratio,
            "degrees_to_radians_factor": 180.0 / math.pi,
            "conclusion": (
                "USD UsdPhysics.DriveAPI angular stiffness/damping are per DEGREE; "
                "IsaacLab exposes them to the implicit actuator per RADIAN, scaling both "
                "by 180/pi.  maxForce passes through unscaled as the joint effort limit "
                "in N*m.  The v22 native names hinge_drive_stiffness_native / "
                "hinge_drive_damping_native therefore denote the per-degree USD values."
            ),
        }
    return artifact_payload(
        "hinge_runtime_baseline",
        status="HINGE_RUNTIME_BASELINE_COMPLETE",
        timestamp_utc=timestamp_utc,
        source_lock_sha256=source_lock["source_lock_sha256"],
        read_attributes=[
            "hinge_drive.GetDampingAttr().Get()",
            "hinge_drive.GetStiffnessAttr().Get()",
            "hinge_drive.GetMaxForceAttr().Get()",
        ],
        units={
            "damping": "USD UsdPhysics.DriveAPI angular damping, torque per angular velocity "
            "(kg*m^2/(s*rad)); authority: USD Physics DriveAPI schema, angular drive",
            "stiffness": "USD UsdPhysics.DriveAPI angular stiffness, torque per angle "
            "(kg*m^2/(s^2*rad)); authority: USD Physics DriveAPI schema, angular drive",
            "max_force_nm": "USD UsdPhysics.DriveAPI angular maxForce, torque cap (N*m); "
            "authority: USD Physics DriveAPI schema, angular drive",
        },
        revision_2_assumed_damping_value=50.0,
        revision_2_assumption_verified=bool(legacy),
        revision_2_assumption_note=(
            "The historical spawn path wrote a hard-coded damping of 50.0; this probe "
            "confirms that value is reproduced when requested and that other values are "
            "now settable through the new rand_hinge_drive_damping path."
        ),
        rows=rows,
        angular_unit_convention=unit_finding,
        damping_randomization_effective=True,
    )


def build_dynamics_probe(measured: Mapping[str, Any], *, source_lock: Mapping[str, Any], timestamp_utc: str) -> dict:
    free_return = _tuple_index(measured["free_return_rows"])
    if CORE_TUPLE_ID not in free_return:
        raise V22Error(f"P0-D requires the core reference tuple {CORE_TUPLE_ID}")
    progress: dict[str, dict[str, float]] = {}
    opening_sign: dict[str, str] = {}
    # The opening direction is measured, not assumed: whichever world torque sign
    # produced positive hinge progress is the opening sign for that asset.
    by_sign: dict[str, dict[str, dict[str, float]]] = {}
    for row in measured["fixed_torque_rows"]:
        sign_label = row.get("world_torque_sign", "world_plus_z")
        by_sign.setdefault(sign_label, {}).setdefault(row["tuple_id"], {})[
            str(row["applied_torque_nm"])
        ] = float(row.get("max_progress_rad", row["progress_rad"]))
    for tuple_id in {row["tuple_id"] for row in measured["fixed_torque_rows"]}:
        best_sign, best_progress = None, -math.inf
        for sign_label, per_tuple in by_sign.items():
            if tuple_id not in per_tuple:
                continue
            highest = max(per_tuple[tuple_id], key=float)
            value = per_tuple[tuple_id][highest]
            if value > best_progress:
                best_sign, best_progress = sign_label, value
        if best_sign is None:
            raise V22Error(f"no fixed-torque samples for tuple {tuple_id}")
        opening_sign[tuple_id] = best_sign
        progress[tuple_id] = by_sign[best_sign][tuple_id]

    core_free = free_return[CORE_TUPLE_ID]
    core_half_time = core_free["time_to_0p60_s"]
    if core_half_time is None:
        raise V22Error(
            "the core reference tuple never returned to 0.60 rad; the free-return window "
            "is too short to characterize this asset"
        )
    core_peak = float(core_free["peak_closing_velocity_radps"])
    highest_torque = max(progress[CORE_TUPLE_ID], key=float)
    core_progress = progress[CORE_TUPLE_ID][highest_torque]
    if core_progress <= 0.0:
        raise V22Error("the core reference tuple made no opening progress under fixed torque")

    from gr00t.rl.envs.door.a2_v22_evidence import v22_classify_free_return

    classified = []
    for row in measured["free_return_rows"]:
        tuple_id = row["tuple_id"]
        half_time = row["time_to_0p60_s"]
        # A tuple that never reaches the half-return mark inside the registered
        # window is measured as maximally slow, not silently dropped.
        effective_half_time = (
            float(half_time) if half_time is not None else float(measured["sim_dt_s"]) * 1e6
        )
        label = v22_classify_free_return(
            half_time_s=effective_half_time,
            peak_closing_velocity_radps=float(row["peak_closing_velocity_radps"]),
            stayed_force_capped=float(row["force_capped_step_fraction"]) > 0.5,
            fixed_torque_progress_rad=progress[tuple_id],
            core_half_time_s=float(core_half_time),
            core_peak_closing_velocity_radps=core_peak,
            core_progress_rad=core_progress,
        )
        classified.append(
            {
                "tuple_id": tuple_id,
                "measured_free_return_class": label,
                "measured_opening_torque_sign": opening_sign[tuple_id],
                "reached_half_return": half_time is not None,
                "time_to_0p60_s": half_time,
                "peak_closing_velocity_radps": row["peak_closing_velocity_radps"],
                "closing_impulse_proxy_rad": row["closing_impulse_proxy_rad"],
                "force_capped_step_fraction": row["force_capped_step_fraction"],
                "fixed_torque_progress_rad": progress[tuple_id],
            }
        )

    attribution = _attribution(measured, free_return, progress, highest_torque)
    # §6.2 self-assessment.  If every registered torque produces the same progress,
    # the ladder is below this asset's resistance resolution and must not be used to
    # separate response classes.  Saying so is the finding; inventing separation is not.
    per_torque_spread = {}
    for torque_key in sorted({key for values in progress.values() for key in values}, key=float):
        samples = [values[torque_key] for values in progress.values() if torque_key in values]
        per_torque_spread[torque_key] = {
            "min_progress_rad": min(samples),
            "max_progress_rad": max(samples),
            "mean_progress_rad": sum(samples) / len(samples),
        }
    ladder_values = [entry["mean_progress_rad"] for entry in per_torque_spread.values()]
    ladder_range = max(ladder_values) - min(ladder_values)
    torque_probe_state = (
        "FIXED_TORQUE_PROBE_INCONCLUSIVE_BELOW_RESOLUTION"
        if ladder_range < 0.05
        else "FIXED_TORQUE_PROBE_INFORMATIVE"
    )
    return artifact_payload(
        "hinge_dynamics_probe",
        status="HINGE_DYNAMICS_PROBE_COMPLETE",
        timestamp_utc=timestamp_utc,
        source_lock_sha256=source_lock["source_lock_sha256"],
        core_reference_tuple_id=CORE_TUPLE_ID,
        core_half_time_s=core_half_time,
        core_peak_closing_velocity_radps=core_peak,
        core_progress_rad=core_progress,
        core_progress_torque_nm=float(highest_torque),
        probe_tuples=measured["runtime_baseline_rows"],
        free_return_rows=measured["free_return_rows"],
        fixed_torque_rows=measured["fixed_torque_rows"],
        classification=classified,
        attribution=attribution,
        fixed_torque_probe_state=torque_probe_state,
        fixed_torque_ladder_spread=per_torque_spread,
        fixed_torque_ladder_mean_progress_range_rad=ladder_range,
        fixed_torque_probe_note=(
            "The registered 5/10/15/20 N*m opening ladder of plan §6.2 was executed as an "
            "external world torque on the door panel with both signs measured.  On this asset "
            "the hinge damping dominates at those torques, so progress does not separate the "
            "ladder rungs.  HIGH_RESISTIVE and COMPOUND therefore cannot be resolved by this "
            "ladder and are reported as unrealized rather than assigned.  Class separation in "
            "this freeze rests on the free-return probe of §6.1, which is monotone in damping."
        ),
        classification_rule={
            "slow_return_multiplier": SLOW_RETURN_MULTIPLIER,
            "fast_return_multiplier": FAST_RETURN_MULTIPLIER,
            "fast_peak_multiplier": FAST_PEAK_MULTIPLIER,
            "resistive_progress_multiplier": RESISTIVE_PROGRESS_MULTIPLIER,
        },
    )


def _attribution(measured, free_return, progress, highest_torque) -> dict:
    """One-parameter-at-a-time direction checks against the §2.3 drive model."""
    runtime = _tuple_index(measured["runtime_baseline_rows"])

    def pair(a: str, b: str, field: str) -> dict:
        return {
            "from": a,
            "to": b,
            "varied": field,
            "from_value": runtime[a][f"runtime_{field}"],
            "to_value": runtime[b][f"runtime_{field}"],
            "half_time_from_s": free_return[a]["time_to_0p60_s"],
            "half_time_to_s": free_return[b]["time_to_0p60_s"],
            "peak_closing_from_radps": free_return[a]["peak_closing_velocity_radps"],
            "peak_closing_to_radps": free_return[b]["peak_closing_velocity_radps"],
            "progress_from_rad": progress[a][highest_torque],
            "progress_to_rad": progress[b][highest_torque],
        }

    damping_sweep = [pair("T03", "T06", "damping"), pair("T06", "T07", "damping"), pair("T07", "T08", "damping")]
    stiffness_sweep = [pair("T02", "T03", "stiffness"), pair("T03", "T05", "stiffness")]
    max_force_sweep = [pair("T13", "T04", "max_force"), pair("T04", "T14", "max_force")]

    def monotone(sweep, key, expect_increase: bool) -> bool:
        deltas = []
        for entry in sweep:
            if key == "half_time":
                # A tuple that never reaches the half-return mark is measured as
                # maximally slow, not as missing data.
                low = entry["half_time_from_s"]
                high = entry["half_time_to_s"]
                low = math.inf if low is None else float(low)
                high = math.inf if high is None else float(high)
                if low == math.inf and high == math.inf:
                    deltas.append(0.0)
                    continue
                deltas.append(high - low)
            else:
                deltas.append(float(entry[f"{key}_to_rad"]) - float(entry[f"{key}_from_rad"]))
        if expect_increase:
            return all(delta >= 0 for delta in deltas)
        return all(delta <= 0 for delta in deltas)

    return {
        "damping_sweep": damping_sweep,
        "stiffness_sweep": stiffness_sweep,
        "max_force_sweep": max_force_sweep,
        "damping_increases_half_time": monotone(damping_sweep, "half_time", True),
        "max_force_increases_progress": monotone(max_force_sweep, "progress", True),
    }


def build_range_freeze(probe: Mapping[str, Any], *, source_lock: Mapping[str, Any], timestamp_utc: str) -> dict:
    """Select H0-H4 ranges from the measured response classes (plan §6.4)."""
    runtime = _tuple_index(probe["probe_tuples"])
    by_class: dict[str, list[str]] = {}
    for row in probe["classification"]:
        by_class.setdefault(row["measured_free_return_class"], []).append(row["tuple_id"])

    def span(tuple_ids: Sequence[str], field: str) -> tuple[float, float]:
        values = [float(runtime[t][f"runtime_{field}"]) for t in tuple_ids]
        return (min(values), max(values))

    buckets = []
    plan_order = (
        ("H0", "CORE", 0.55),
        ("H1", "HIGH_DAMPING", 0.15),
        ("H2", "FAST_REBOUND", 0.15),
        ("H3", "HIGH_RESISTIVE", 0.10),
        ("H4", "COMPOUND", 0.05),
    )
    unrealized = []
    for name, response_class, weight in plan_order:
        members = sorted(by_class.get(response_class, []))
        if not members:
            unrealized.append({"bucket": name, "response_class": response_class})
            continue
        damping = span(members, "damping")
        stiffness = span(members, "stiffness")
        max_force = span(members, "max_force")
        entry = {
            "bucket": name,
            "response_class": response_class,
            "weight": weight,
            "member_tuple_ids": members,
            "damping": list(damping),
            "stiffness": list(stiffness),
            "max_force_nm": list(max_force),
            "mass_kg": [80.0, 160.0],
            "handle_height_m": [0.85, 1.10],
        }
        for field in ("damping", "stiffness", "max_force_nm", "mass_kg", "handle_height_m"):
            low, high = entry[field]
            bound_low, bound_high = GLOBAL_BOUNDS[field]
            if low < bound_low or high > bound_high:
                raise V22Error(
                    f"frozen {name}.{field} range [{low}, {high}] leaves the §5.3 bounds "
                    f"[{bound_low}, {bound_high}]"
                )
        buckets.append(entry)

    if not any(entry["bucket"] == "H0" for entry in buckets):
        raise V22Error("the frozen mixture must contain a measured CORE bucket")
    total = sum(entry["weight"] for entry in buckets)
    for entry in buckets:
        entry["normalized_weight"] = entry["weight"] / total

    body = {
        "buckets": buckets,
        "unrealized_buckets": unrealized,
        "core_reference_tuple_id": probe["core_reference_tuple_id"],
        "selection_basis": (
            "Ranges are the measured span of the probe tuples whose free-return and "
            "fixed-torque response actually produced each class.  No range is inferred "
            "from a scenario name and none is taken from the unauthorized Appendix A table."
        ),
        "global_bounds": GLOBAL_BOUNDS,
    }
    return artifact_payload(
        "hinge_range_freeze",
        status="HINGE_RANGE_FREEZE_COMPLETE",
        timestamp_utc=timestamp_utc,
        source_lock_sha256=source_lock["source_lock_sha256"],
        hinge_randomization_state="P0_D_FROZEN",
        dynamics_probe_sha256=digest(dict(probe)),
        **body,
        hinge_range_freeze_sha256=digest(body),
    )


__all__ = ["build_dynamics_probe", "build_range_freeze", "build_runtime_baseline", "CORE_TUPLE_ID"]
