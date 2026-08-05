"""P0-POSTURE-BASELINE — the same-denominator warm-start posture baseline (plan §7.6).

The raw producer is the exact frozen ``B1@500`` warm start with no optimizer
update and no action intervention; ``posture_need`` runs for telemetry only.  The
baseline and every later gated quantity therefore come from the same evidence
path and the same ``ordinary_need_negative`` denominator by construction.

Outputs:
    logs_eval/base_v22/locks/V22_POSTURE_BASELINE.json
    logs_eval/base_v22/locks/V22_POSTURE_DENOMINATOR_ADJUDICATION.json
    logs_eval/base_v22/locks/V22_POSTURE_GATE_FREEZE.json
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ._v22_common import (
    REPO_ROOT,
    V22_ARTIFACT_ROOT,
    V22_LOCK_ROOT,
    V22_WARM_START_PATH,
    V22_WARM_START_SHA256,
    V22Error,
    artifact_payload,
    digest,
    quantile,
    read_json,
    write_json,
)
from .posture_probe import build_probe_argv, load_trace, run_probe

CONTRIBUTING_EPISODES_MIN = 8
CONTRIBUTING_EPISODES_DENOMINATOR = 16
ORDINARY_NEED_NEGATIVE_FRAMES_MIN = 1000
VACUITY_FRACTION = 0.25
POSTURE_COMMAND_SCALE_RAD = 0.40
SATURATION_FRACTION_OF_SCALE = 0.95

STANDARD_GATES = {
    "pitch_command_p50_max_multiplier_of_B0": 0.85,
    "roll_command_p50_max_multiplier_of_B0": 0.80,
    "roll_saturation_max_multiplier_of_B0": 0.70,
    "pitch_p95_max_offset_rad_over_B0": 0.05,
    "roll_p95_max_offset_rad_over_B0": 0.05,
    "ordinary_goal_regression_max_of_16": 1,
    "ordinary_clearance_success_regression_max_of_16": 1,
}
RELAXED_1_GATES = {
    "pitch_command_p50_max_multiplier_of_B0": 0.95,
    "roll_command_p50_max_multiplier_of_B0": 0.90,
    "roll_saturation_max_multiplier_of_B0": 0.85,
    "pitch_p95_max_offset_rad_over_B0": 0.08,
    "roll_p95_max_offset_rad_over_B0": 0.08,
    "ordinary_goal_regression_max_of_16": 2,
    "ordinary_clearance_success_regression_max_of_16": 2,
}


def _distribution(values: Sequence[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "p50": quantile(values, 0.50),
        "p90": quantile(values, 0.90),
        "p95": quantile(values, 0.95),
        "mean": sum(values) / len(values),
        "max": max(values),
    }


def build_posture_baseline(trace_path: Path, *, source_lock, atlas, timestamp_utc: str) -> dict:
    rows = load_trace(trace_path)
    ordinary_valid = [row for row in rows if bool(row["v22_ordinary_opening_valid"])]
    need_negative = [row for row in ordinary_valid if bool(row["v22_ordinary_need_negative"])]
    if not ordinary_valid:
        raise V22Error("P0-POSTURE-BASELINE produced no valid ordinary opening frames")

    contributing_episodes = sorted({int(row["env_id"]) for row in need_negative})
    saturation_threshold = SATURATION_FRACTION_OF_SCALE * POSTURE_COMMAND_SCALE_RAD

    def _series(source, key):
        return [abs(float(row[key])) for row in source]

    per_episode = {}
    for env_id in sorted({int(row["env_id"]) for row in ordinary_valid}):
        env_rows = [row for row in need_negative if int(row["env_id"]) == env_id]
        if not env_rows:
            per_episode[str(env_id)] = {"need_negative_frames": 0}
            continue
        per_episode[str(env_id)] = {
            "need_negative_frames": len(env_rows),
            "handle_height_m": float(env_rows[0]["door_handle_height"]),
            "command_pitch_abs": _distribution(_series(env_rows, "v22_posture_command_pitch_rad")),
            "command_roll_abs": _distribution(_series(env_rows, "v22_posture_command_roll_rad")),
            "achieved_pitch_abs": _distribution(_series(env_rows, "root_pitch")),
            "achieved_roll_abs": _distribution(_series(env_rows, "root_roll")),
        }

    pooled = {}
    if need_negative:
        pooled = {
            "command_pitch_abs": _distribution(_series(need_negative, "v22_posture_command_pitch_rad")),
            "command_roll_abs": _distribution(_series(need_negative, "v22_posture_command_roll_rad")),
            "achieved_pitch_abs": _distribution(_series(need_negative, "root_pitch")),
            "achieved_roll_abs": _distribution(_series(need_negative, "root_roll")),
            "command_pitch_saturation_rate": sum(
                1 for value in _series(need_negative, "v22_posture_command_pitch_rad")
                if value >= saturation_threshold
            )
            / len(need_negative),
            "command_roll_saturation_rate": sum(
                1 for value in _series(need_negative, "v22_posture_command_roll_rad")
                if value >= saturation_threshold
            )
            / len(need_negative),
        }

    component_prevalence = {
        name: sum(1 for row in ordinary_valid if bool(row[name])) / len(ordinary_valid)
        for name in ("v22_height_need", "v22_workspace_need", "v22_force_need", "v22_tracking_need")
    }
    body = {
        "producer": {
            "checkpoint": V22_WARM_START_PATH,
            "checkpoint_sha256": V22_WARM_START_SHA256,
            "optimizer_update": False,
            "action_intervention": "none",
            "posture_need": "telemetry_only_no_reward_no_action_effect",
            "trace_path": str(trace_path),
        },
        "ordinary_denominator_definition": [
            "scenario belongs to the v22 ordinary16 handle-height grid over [0.85, 1.10] m",
            "stage is OPEN or SWING",
            "valid task-space/reference state",
            "no body-assist eligibility and no body contact",
            "not a terminal-only frame",
            "posture_need_score <= 0.35",
        ],
        "total_ordinary_frames": len(ordinary_valid),
        "ordinary_need_negative_frames": len(need_negative),
        "contributing_episode_count": len(contributing_episodes),
        "contributing_episode_ids": contributing_episodes,
        "fraction_of_ordinary_frames_need_negative": len(need_negative) / len(ordinary_valid),
        "command_saturation_threshold_rad": saturation_threshold,
        "per_episode_command_distributions": per_episode,
        "pooled_command_and_achieved_distributions": pooled,
        "posture_need_component_prevalences": component_prevalence,
        "measured_constants_from_atlas": {
            "directional_wrench_threshold_n": atlas["directional_wrench_threshold_n"],
            "arm_tracking_error_p90_rad": atlas["arm_tracking_error_p90_rad"],
            "workspace_margin_threshold": atlas["workspace_margin_threshold"],
            "posture_atlas_sha256": atlas["posture_atlas_sha256"],
        },
        "commanded_and_achieved_are_separate": True,
    }
    return artifact_payload(
        "posture_baseline",
        status="POSTURE_BASELINE_COMPLETE",
        timestamp_utc=timestamp_utc,
        source_lock_sha256=source_lock["source_lock_sha256"],
        **body,
        posture_baseline_sha256=digest(body),
    )


def build_denominator_adjudication(baseline, *, timestamp_utc: str) -> dict:
    episodes = baseline["contributing_episode_count"]
    frames = baseline["ordinary_need_negative_frames"]
    fraction = baseline["fraction_of_ordinary_frames_need_negative"]
    sufficient = (
        episodes >= CONTRIBUTING_EPISODES_MIN and frames >= ORDINARY_NEED_NEGATIVE_FRAMES_MIN
    )
    gate_state = "BINDING" if sufficient else "REPORT_ONLY_INSUFFICIENT_DENOMINATOR"
    need_state = None if fraction >= VACUITY_FRACTION else "POSTURE_NEED_OVERACTIVE_OR_VACUOUS"
    body = {
        "contributing_episodes": episodes,
        "contributing_episodes_min": CONTRIBUTING_EPISODES_MIN,
        "contributing_episodes_denominator": CONTRIBUTING_EPISODES_DENOMINATOR,
        "ordinary_need_negative_frames": frames,
        "ordinary_need_negative_frames_min": ORDINARY_NEED_NEGATIVE_FRAMES_MIN,
        "fraction_of_ordinary_frames_need_negative": fraction,
        "vacuity_threshold_fraction": VACUITY_FRACTION,
        "posture_gate_state": gate_state,
        "posture_need_state": need_state,
        "blocks_pilot_or_formal": False,
        "effect": (
            "Posture gates bind on the frozen B0 denominator."
            if sufficient
            else "Posture gates are report-only and must not block pilot, formal training, "
            "Route A, Route B, or a research-complete result."
        ),
        "posture_need_precision_binding": False,
        "posture_need_precision_reason": (
            "P0-B independent causal labels are not yet available, so precision is circular "
            "and stays report-only per §7.6.6."
        ),
        "posture_baseline_sha256": baseline["posture_baseline_sha256"],
    }
    return artifact_payload(
        "posture_denominator_adjudication",
        status="POSTURE_DENOMINATOR_ADJUDICATION_COMPLETE",
        timestamp_utc=timestamp_utc,
        **body,
        adjudication_sha256=digest(body),
    )


def build_gate_freeze(baseline, adjudication, *, source_lock, timestamp_utc: str) -> dict:
    pooled = baseline["pooled_command_and_achieved_distributions"]
    if not pooled:
        b0 = {
            "pitch_p50": None,
            "roll_p50": None,
            "pitch_p95": None,
            "roll_p95": None,
            "roll_saturation": None,
        }
        resolved = {}
    else:
        b0 = {
            "pitch_p50": pooled["command_pitch_abs"]["p50"],
            "roll_p50": pooled["command_roll_abs"]["p50"],
            "pitch_p95": pooled["command_pitch_abs"]["p95"],
            "roll_p95": pooled["command_roll_abs"]["p95"],
            "roll_saturation": pooled["command_roll_saturation_rate"],
        }
        resolved = {}
        for profile, gates in (("STANDARD", STANDARD_GATES), ("RELAXED_1", RELAXED_1_GATES)):
            resolved[profile] = {
                "pitch_command_p50_max_rad": gates["pitch_command_p50_max_multiplier_of_B0"] * b0["pitch_p50"],
                "roll_command_p50_max_rad": gates["roll_command_p50_max_multiplier_of_B0"] * b0["roll_p50"],
                "roll_saturation_max": gates["roll_saturation_max_multiplier_of_B0"] * b0["roll_saturation"],
                "pitch_p95_max_rad": b0["pitch_p95"] + gates["pitch_p95_max_offset_rad_over_B0"],
                "roll_p95_max_rad": b0["roll_p95"] + gates["roll_p95_max_offset_rad_over_B0"],
                "ordinary_goal_regression_max_of_16": gates["ordinary_goal_regression_max_of_16"],
                "ordinary_clearance_success_regression_max_of_16": gates[
                    "ordinary_clearance_success_regression_max_of_16"
                ],
            }
    body = {
        "gate_form": "same_denominator_warm_start_relative",
        "gate_side": "command",
        "posture_gate_state": adjudication["posture_gate_state"],
        "posture_need_state": adjudication["posture_need_state"],
        "B0_same_denominator": b0,
        "multipliers": {"STANDARD": STANDARD_GATES, "RELAXED_1": RELAXED_1_GATES},
        "resolved_gates": resolved,
        "withdrawn_absolute_gates_must_not_be_reintroduced": [
            "ordinary pitch p50 <= 0.10 / 0.15",
            "ordinary roll p50 <= 0.06 / 0.10",
            "roll saturation <= 8% / 15%",
        ],
        "release_goal_pooled48": 46,
        "release_goal_pooled48_waivable": False,
        "posture_baseline_sha256": baseline["posture_baseline_sha256"],
        "adjudication_sha256": adjudication["adjudication_sha256"],
    }
    return artifact_payload(
        "posture_gate_freeze",
        status="POSTURE_GATE_FREEZE_COMPLETE",
        timestamp_utc=timestamp_utc,
        source_lock_sha256=source_lock["source_lock_sha256"],
        **body,
        posture_gate_freeze_sha256=digest(body),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / V22_ARTIFACT_ROOT / "p0_posture_baseline")
    parser.add_argument("--reuse", action="store_true")
    args = parser.parse_args(argv)

    lock_root = REPO_ROOT / V22_LOCK_ROOT
    source_lock = read_json(lock_root / "V22_SOURCE_LOCK.json")
    atlas = read_json(lock_root / "V22_POSTURE_ATLAS.json")

    if args.reuse:
        matches = sorted(Path(args.out).rglob("stage2_5_step_trace.json"))
        if not matches:
            raise V22Error(f"no baseline trace under {args.out}")
        trace = matches[-1]
    else:
        argv_cmd = build_probe_argv(
            output_dir=args.out,
            eval_name="v22_P0_posture_baseline",
            seed=0,
            intervention="legacy",
            nominal_heights=atlas["nominal_heights_m"],
            nominal_pitch=atlas["nominal_pitch_rad"],
            nominal_roll=atlas["nominal_roll_rad"],
            wrench_threshold_n=atlas["directional_wrench_threshold_n"],
            tracking_p90_rad=atlas["arm_tracking_error_p90_rad"],
            workspace_margin_threshold=atlas["workspace_margin_threshold"],
            calibration_probe=False,
        )
        trace = run_probe(argv_cmd, gpu=args.gpu, output_dir=args.out)

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    baseline = build_posture_baseline(trace, source_lock=source_lock, atlas=atlas, timestamp_utc=stamp)
    adjudication = build_denominator_adjudication(baseline, timestamp_utc=stamp)
    freeze = build_gate_freeze(baseline, adjudication, source_lock=source_lock, timestamp_utc=stamp)
    for name, payload in (
        ("V22_POSTURE_BASELINE.json", baseline),
        ("V22_POSTURE_DENOMINATOR_ADJUDICATION.json", adjudication),
        ("V22_POSTURE_GATE_FREEZE.json", freeze),
    ):
        target = lock_root / name
        write_json(target, payload)
        print(f"P0-POSTURE-BASELINE wrote {target}", flush=True)
    print(
        f"posture_gate_state={adjudication['posture_gate_state']} "
        f"posture_need_state={adjudication['posture_need_state']} "
        f"episodes={adjudication['contributing_episodes']} "
        f"frames={adjudication['ordinary_need_negative_frames']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
