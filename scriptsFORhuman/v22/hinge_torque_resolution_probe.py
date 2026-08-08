"""Supplement P0-D with the handoff-authorized 25/30 N*m torque ladder.

The original signed P0-D locks remain untouched.  This probe reruns the same
door-only response measurement with higher external torques, adjudicates
whether the ladder is informative at the registered 0.05-rad resolution, and
records whether HIGH_RESISTIVE/COMPOUND become measured response classes.

Output:
    logs_eval/base_v22/locks/V22_HINGE_TORQUE_RESOLUTION.json
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone


TORQUES_NM = (25.0, 30.0)
INFORMATIVE_RANGE_RAD = 0.05


def _adjudicate(measured: dict, reference: dict) -> dict:
    from gr00t.rl.envs.door.a2_v22_evidence import v22_classify_free_return

    free = {row["tuple_id"]: row for row in measured["free_return_rows"]}
    by_tuple_sign: dict[str, dict[str, dict[str, float]]] = {}
    for row in measured["fixed_torque_rows"]:
        by_tuple_sign.setdefault(row["tuple_id"], {}).setdefault(
            row["world_torque_sign"], {}
        )[str(row["applied_torque_nm"])] = float(row["max_progress_rad"])

    selected_progress = {}
    opening_sign = {}
    for tuple_id, signs in by_tuple_sign.items():
        sign = max(
            signs,
            key=lambda candidate: max(signs[candidate].values()),
        )
        opening_sign[tuple_id] = sign
        selected_progress[tuple_id] = signs[sign]

    per_torque = {}
    for torque in TORQUES_NM:
        key = str(torque)
        values = [row[key] for row in selected_progress.values()]
        per_torque[key] = {
            "min_progress_rad": min(values),
            "max_progress_rad": max(values),
            "mean_progress_rad": sum(values) / len(values),
        }
    means = [row["mean_progress_rad"] for row in per_torque.values()]
    ladder_range = max(means) - min(means)

    core_id = reference["core_reference_tuple_id"]
    core_progress = selected_progress[core_id][str(max(TORQUES_NM))]
    classified = []
    for tuple_id, free_row in free.items():
        half_time = free_row["time_to_0p60_s"]
        effective_half_time = (
            float(half_time)
            if half_time is not None
            else float(measured["sim_dt_s"]) * 1.0e6
        )
        response = v22_classify_free_return(
            half_time_s=effective_half_time,
            peak_closing_velocity_radps=float(
                free_row["peak_closing_velocity_radps"]
            ),
            stayed_force_capped=float(free_row["force_capped_step_fraction"]) > 0.5,
            fixed_torque_progress_rad=selected_progress[tuple_id],
            core_half_time_s=float(reference["core_half_time_s"]),
            core_peak_closing_velocity_radps=float(
                reference["core_peak_closing_velocity_radps"]
            ),
            core_progress_rad=core_progress,
        )
        classified.append(
            {
                "tuple_id": tuple_id,
                "opening_world_torque_sign": opening_sign[tuple_id],
                "fixed_torque_progress_rad": selected_progress[tuple_id],
                "measured_response_class": response,
            }
        )
    classes = Counter(row["measured_response_class"] for row in classified)
    realized = [name for name in ("HIGH_RESISTIVE", "COMPOUND") if classes[name] > 0]
    return {
        "schema": "a2_piper_base_v22_hinge_torque_resolution_v1",
        "status": (
            "HINGE_TORQUE_RESOLUTION_INFORMATIVE"
            if ladder_range >= INFORMATIVE_RANGE_RAD
            else "HINGE_TORQUE_RESOLUTION_INCONCLUSIVE_BELOW_RESOLUTION"
        ),
        "timestamp_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "external_torque_ladder_nm": list(TORQUES_NM),
        "informative_range_threshold_rad": INFORMATIVE_RANGE_RAD,
        "ladder_mean_progress_range_rad": ladder_range,
        "per_torque_spread": per_torque,
        "core_reference_tuple_id": core_id,
        "core_progress_rad_at_30nm": core_progress,
        "classification_counts": dict(sorted(classes.items())),
        "newly_realized_resistive_classes": realized,
        "classification": classified,
        "fixed_torque_rows": measured["fixed_torque_rows"],
        "freeze_effect": (
            "SUPPLEMENT_ONLY_EXISTING_H0_H1_H2_FREEZE_UNCHANGED"
            if not realized
            else "RESPONSE_CLASS_REALIZED_AFTER_TRAINING_FREEZE_REQUIRES_FUTURE_ROUND"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, default=0)
    args = parser.parse_args(argv)

    from scriptsFORhuman.v22._v22_common import (
        REPO_ROOT,
        V22_LOCK_ROOT,
        read_json,
        require_gpu,
        write_json,
    )
    from scriptsFORhuman.v22.characterize_hinge_dynamics import _run_probe

    gpu = require_gpu(args.gpu)
    lock_root = REPO_ROOT / V22_LOCK_ROOT
    reference = read_json(lock_root / "V22_HINGE_DYNAMICS_PROBE.json")

    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(
        {"headless": True, "device": f"cuda:{gpu}", "enable_cameras": False}
    )
    simulation_app = app_launcher.app
    try:
        measured = _run_probe(
            device=f"cuda:{gpu}",
            num_envs_note="16 probe tuples; supplemental 25/30 N*m ladder",
            fixed_torques_nm=TORQUES_NM,
        )
        payload = _adjudicate(measured, reference)
        target = lock_root / "V22_HINGE_TORQUE_RESOLUTION.json"
        write_json(target, payload)
        print(f"WROTE {target} status={payload['status']}", flush=True)
    finally:
        simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
