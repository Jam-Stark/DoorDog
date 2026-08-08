"""base_v22 Route A evidence index — per-env causal attribution over delivered traces.

Reads the selected Route A profile's row evidence units (row_receipt.json +
stage2_step_trace.json + a2_v14_per_env_records.json) and produces
V22_ROUTE_A_EVIDENCE_INDEX.json at the Route A root.

The v22 unsafe_release flag fires on ``newly_released & ~hold_at_release``:
at the release-detection step the hold is already off by construction, so a
natural hand-hold release after root clear is stamped unsafe.  This index keeps
the raw counts AND a causal breakdown so adjudication can distinguish real
safety violations (excessive release speed, post-release body contact, frame
contact, pre-clear support loss) from benign post-clear releases.

Fail-fast: any missing artifact, non-finite metric, or topology mismatch raises.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scriptsFORhuman.v22._v22_common import (  # noqa: E402
    V22_ARTIFACT_ROOT,
    V22Error,
    quantile,
    sha256_file,
    write_json,
)

ROUTE_A_ROOT = REPO / V22_ARTIFACT_ROOT / "postformal_20260806_route_a"
CELLS = ("G1", "G2")
STEPS = tuple(range(250, 2501, 250))
SEED_BY_CELL = {"G1": 0, "G2": 1, "G3": 0, "G4": 1, "G5": 0, "G6": 1}
PROFILES = {
    "wave1": ("postformal_20260806_route_a", ("G1", "G2")),
    "wave23": ("postformal_20260808_route_a_wave23", ("G3", "G4", "G5", "G6")),
}
RELEASE_VELOCITY_SOFT_MAX = 0.75
CLEARANCE_MIN_HINGE = 1.10
SATURATION_THRESHOLD = 0.95 * 0.40
BODY_CONTACT_EVENT_N = 1.0
BODY_FILTER_NAMES = (
    "trunk",
    "FL_hip",
    "FL_thigh",
    "FL_calf",
    "RL_hip",
    "RL_thigh",
    "RL_calf",
    "FR_hip",
    "FR_thigh",
    "FR_calf",
    "RR_hip",
    "RR_thigh",
    "RR_calf",
)
APPROVED_BODY_ASSIST_FILTERS = frozenset(("trunk", "FL_thigh", "FR_thigh"))

CAUSE_CLASSES = (
    "none",
    "excessive_release_speed",
    "post_release_body_contact",
    "frame_contact_after_release",
    "pre_clear_support_loss",
    "post_clear_natural_release",
)


def configure(profile: str) -> None:
    global ROUTE_A_ROOT, CELLS
    root_name, cells = PROFILES[profile]
    ROUTE_A_ROOT = REPO / V22_ARTIFACT_ROOT / root_name
    CELLS = cells


def _finite(value: float | int | None, *, name: str) -> float:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V22Error(f"{name} is missing or not numeric: {value!r}")
    out = float(value)
    if not math.isfinite(out):
        raise V22Error(f"{name} is not finite: {value!r}")
    return out


def _last_non_null(steps: list[dict], key: str):
    value = None
    for step in steps:
        if step.get(key) is not None:
            value = step[key]
    return value


def _first_index(steps: list[dict], predicate) -> int | None:
    for index, step in enumerate(steps):
        if predicate(step):
            return index
    return None


def analyze_env(steps: list[dict]) -> dict:
    """Causal attribution for one env's first-episode steps (trace order preserved)."""
    if not steps:
        raise V22Error("env has no trace steps")
    if any(step.get("first_episode_active") is not True for step in steps):
        raise V22Error("env trace mixes non-first-episode steps")

    root_clear_step = _last_non_null(steps, "v22_root_clear_step")
    release_index = _first_index(steps, lambda s: s.get("v22_release_hinge_velocity_radps") is not None)
    unsafe_index = _first_index(steps, lambda s: s.get("v22_unsafe_release") is True)
    release_velocity = (
        steps[release_index]["v22_release_hinge_velocity_radps"] if release_index is not None else None
    )
    release_buf = steps[release_index]["episode_length_buf"] if release_index is not None else None
    unsafe_buf = steps[unsafe_index]["episode_length_buf"] if unsafe_index is not None else None
    frame_flag = any(step.get("v22_frame_contact_after_release") is True for step in steps)
    frame_index = _first_index(steps, lambda s: s.get("v22_frame_contact_after_release") is True)
    frame_buf = steps[frame_index]["episode_length_buf"] if frame_index is not None else None
    body_flag = any(step.get("post_release_body_contact") is True for step in steps)
    body_force_max = _last_non_null(steps, "post_release_body_force_max")

    strategy = _last_non_null(steps, "v22_clearance_strategy")
    success = any(step.get("v22_clearance_success") is True for step in steps)
    min_hinge_after_release = _last_non_null(steps, "v22_min_hinge_after_release_rad")
    hinge_at_crossing = _last_non_null(steps, "hinge_at_crossing")
    if hinge_at_crossing is None:
        hinge_at_crossing = _last_non_null(steps, "v20_hinge_at_first_root_crossing")
    peak_closing = _last_non_null(steps, "v22_peak_closing_velocity_radps")
    episode_len = max(int(step["episode_length_buf"]) for step in steps)
    control_dt = _finite(steps[0].get("control_dt"), name="control_dt")

    cmd_pitch = [abs(_finite(s.get("v22_posture_command_pitch_rad"), name="cmd pitch")) for s in steps]
    cmd_roll = [abs(_finite(s.get("v22_posture_command_roll_rad"), name="cmd roll")) for s in steps]
    ach_pitch = [abs(_finite(s.get("v22_posture_achieved_pitch_rad"), name="ach pitch")) for s in steps]
    ach_roll = [abs(_finite(s.get("v22_posture_achieved_roll_rad"), name="ach roll")) for s in steps]
    ordinary_nn = [s for s in steps if s.get("v22_ordinary_need_negative") is True]
    arm_failure_latched = any(s.get("v22_arm_failure_latched") is True for s in steps)
    body_assist_eligible = any(s.get("v22_body_assist_eligible") is True for s in steps)
    force_need = any(s.get("v22_force_need") is True for s in steps)
    body_panel_forces = [
        _finite(s.get("door_body_panel_normal_force_total"), name="body panel force") for s in steps
    ]
    body_panel_force_vectors = []
    for step in steps:
        values = step.get("door_body_panel_normal_force_per_filter")
        if not isinstance(values, list) or len(values) != len(BODY_FILTER_NAMES):
            raise V22Error("body panel per-filter force vector is missing or has the wrong length")
        body_panel_force_vectors.append(
            [_finite(value, name="body panel per-filter force") for value in values]
        )
    unauthorized_body_contact = False
    approved_body_contact = False
    for step, values in zip(steps, body_panel_force_vectors):
        for name, force in zip(BODY_FILTER_NAMES, values):
            if force < BODY_CONTACT_EVENT_N:
                continue
            if name in APPROVED_BODY_ASSIST_FILTERS:
                approved_body_contact = True
                if step.get("v22_body_assist_eligible") is not True:
                    unauthorized_body_contact = True
            else:
                unauthorized_body_contact = True

    if unsafe_index is None:
        cause = "none"
    elif (
        release_index is not None
        and unsafe_buf == release_buf
        and release_velocity is not None
        and release_velocity > RELEASE_VELOCITY_SOFT_MAX
    ):
        cause = "excessive_release_speed"
    elif body_flag:
        cause = "post_release_body_contact"
    elif frame_flag:
        cause = "frame_contact_after_release"
    elif (
        release_buf is not None
        and root_clear_step is not None
        and release_buf > root_clear_step
    ):
        cause = "post_clear_natural_release"
    else:
        cause = "pre_clear_support_loss"

    return {
        "env_id": int(steps[0]["env_id"]),
        "cause": cause,
        "root_clear_step": root_clear_step,
        "release_buf": release_buf,
        "release_velocity_radps": release_velocity,
        "unsafe_buf": unsafe_buf,
        "frame_contact_after_release": frame_flag,
        "frame_buf": frame_buf,
        "post_release_body_contact": body_flag,
        "post_release_body_force_max": body_force_max,
        "strategy": strategy,
        "clearance_success": success,
        "min_hinge_after_release_rad": min_hinge_after_release,
        "hinge_at_crossing_rad": hinge_at_crossing,
        "peak_closing_velocity_radps": peak_closing,
        "episode_steps": episode_len,
        "episode_seconds": episode_len * control_dt,
        "cmd_abs_pitch_p50": quantile(cmd_pitch, 0.5),
        "cmd_abs_roll_p50": quantile(cmd_roll, 0.5),
        "ach_abs_pitch_p50": quantile(ach_pitch, 0.5),
        "ach_abs_roll_p50": quantile(ach_roll, 0.5),
        "ordinary_need_negative_frames": len(ordinary_nn),
        "arm_failure_latched": arm_failure_latched,
        "body_assist_eligible": body_assist_eligible,
        "force_need": force_need,
        "body_panel_force_max_n": max(body_panel_forces),
        "body_panel_force_max_by_filter_n": {
            name: max(values[index] for values in body_panel_force_vectors)
            for index, name in enumerate(BODY_FILTER_NAMES)
        },
        "approved_body_contact": approved_body_contact,
        "unauthorized_body_contact": unauthorized_body_contact,
        "cmd_pitch_saturation": (
            sum(1 for s in ordinary_nn if abs(s["v22_posture_command_pitch_rad"]) >= SATURATION_THRESHOLD)
            / len(ordinary_nn)
            if ordinary_nn
            else None
        ),
        "cmd_roll_saturation": (
            sum(1 for s in ordinary_nn if abs(s["v22_posture_command_roll_rad"]) >= SATURATION_THRESHOLD)
            / len(ordinary_nn)
            if ordinary_nn
            else None
        ),
    }


def analyze_row(cell: str, step: int) -> dict:
    seed = SEED_BY_CELL[cell]
    root = ROUTE_A_ROOT / cell / f"step{step:04d}" / "canonical16" / f"seed{seed}"
    receipt_path = root / "row_receipt.json"
    trace_path = root / "stage2_step_trace.json"
    records_path = root / "a2_v14_per_env_records.json"
    for path in (receipt_path, trace_path, records_path):
        if path.is_symlink() or not path.is_file():
            raise V22Error(f"missing row artifact: {path}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "ROW_PASS":
        raise V22Error(f"{cell}:{step} receipt is not ROW_PASS")
    if receipt.get("first_episode_count") != 16:
        raise V22Error(f"{cell}:{step} first-episode count != 16")

    records = json.loads(records_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    by_env: dict[int, list[dict]] = {}
    for row in trace:
        by_env.setdefault(int(row["env_id"]), []).append(row)

    goal = sum(1 for r in records if r.get("goal_reached") is True)
    supported = sum(1 for r in records if r.get("crossing_while_holding") is True)
    record_body_contact = sum(1 for r in records if r.get("post_release_body_contact") is True)

    envs = [analyze_env(by_env[env_id]) for env_id in sorted(by_env)]
    causes: dict[str, int] = {name: 0 for name in CAUSE_CLASSES}
    for env in envs:
        causes[env["cause"]] += 1

    strategies: dict[str, int] = {}
    for env in envs:
        strategies[str(env["strategy"])] = strategies.get(str(env["strategy"]), 0) + 1

    release_velocities = [
        env["release_velocity_radps"] for env in envs if env["release_velocity_radps"] is not None
    ]
    crossings = [env["hinge_at_crossing_rad"] for env in envs if env["hinge_at_crossing_rad"] is not None]
    episode_seconds = [env["episode_seconds"] for env in envs]
    cmd_pitch = [env["cmd_abs_pitch_p50"] for env in envs]
    cmd_roll = [env["cmd_abs_roll_p50"] for env in envs]
    ach_pitch = [env["ach_abs_pitch_p50"] for env in envs]
    ach_roll = [env["ach_abs_roll_p50"] for env in envs]
    sat_pitch = [env["cmd_pitch_saturation"] for env in envs if env["cmd_pitch_saturation"] is not None]
    sat_roll = [env["cmd_roll_saturation"] for env in envs if env["cmd_roll_saturation"] is not None]

    real_safety = (
        causes["excessive_release_speed"]
        + causes["post_release_body_contact"]
        + causes["frame_contact_after_release"]
        + causes["pre_clear_support_loss"]
    )

    return {
        "row_id": f"{cell}:step{step:04d}",
        "cell": cell,
        "step": step,
        "seed": seed,
        "receipt_sha256": receipt["receipt_sha256"],
        "checkpoint_path": receipt["checkpoint_path"],
        "checkpoint_sha256": receipt["checkpoint_sha256"],
        "goal_of_16": goal,
        "supported_crossing_of_16": supported,
        "record_post_release_body_contact_of_16": record_body_contact,
        "arm_failure_latched_of_16": sum(1 for env in envs if env["arm_failure_latched"]),
        "body_assist_eligible_of_16": sum(1 for env in envs if env["body_assist_eligible"]),
        "force_need_of_16": sum(1 for env in envs if env["force_need"]),
        "body_panel_contact_of_16": sum(1 for env in envs if env["body_panel_force_max_n"] > 0.0),
        "unauthorized_body_contact_of_16": sum(
            1 for env in envs if env["unauthorized_body_contact"]
        ),
        "body_panel_force_max_n": max(env["body_panel_force_max_n"] for env in envs),
        "clearance_success_of_16": sum(1 for env in envs if env["clearance_success"]),
        "strategy_counts": strategies,
        "unsafe_release_raw_of_16": sum(1 for env in envs if env["cause"] != "none"),
        "unsafe_cause_counts": causes,
        "real_safety_violations_of_16": real_safety,
        "release_velocity_p50": quantile(release_velocities, 0.5) if release_velocities else None,
        "release_velocity_p95": quantile(release_velocities, 0.95) if release_velocities else None,
        "hinge_at_crossing_p50": quantile(crossings, 0.5) if crossings else None,
        "episode_seconds_p50": quantile(episode_seconds, 0.5),
        "cmd_abs_pitch_p50_of_env_p50": quantile(cmd_pitch, 0.5),
        "cmd_abs_roll_p50_of_env_p50": quantile(cmd_roll, 0.5),
        "ach_abs_pitch_p50_of_env_p50": quantile(ach_pitch, 0.5),
        "ach_abs_roll_p50_of_env_p50": quantile(ach_roll, 0.5),
        "ordinary_cmd_pitch_saturation_mean": sum(sat_pitch) / len(sat_pitch) if sat_pitch else None,
        "ordinary_cmd_roll_saturation_mean": sum(sat_roll) / len(sat_roll) if sat_roll else None,
        "envs": envs,
        "headline_from_receipt": receipt["headline"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="base_v22 Route A causal evidence analysis")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="wave1")
    args = parser.parse_args(argv)
    configure(args.profile)
    rows = [analyze_row(cell, step) for cell in CELLS for step in STEPS]
    index = {
        "schema": "a2_piper_base_v22_route_a_evidence_index_v1",
        "plan_id": "base_v22_posture_clearance_force_routing_v3",
        "execution_id": "base_v22_execution_v3",
        "route_a_root": str(ROUTE_A_ROOT),
        "producer": "lead_direct_route_a_causal_analysis",
        "cause_class_semantics": {
            "excessive_release_speed": "release stamped with hinge velocity > 0.75 rad/s (real §8.6 violation)",
            "post_release_body_contact": "post-release panel/body contact before root clear (real violation)",
            "frame_contact_after_release": "door-frame contact flagged after release (real violation; note: no root-crossed qualifier in implementation)",
            "pre_clear_support_loss": "release/support loss stamped before root clear with no contact and sub-limit speed (real premature loss)",
            "post_clear_natural_release": "hand-hold release detected after root clear; flag is a detection-order artifact, not a §8.6 violation",
            "none": "no unsafe_release flag",
        },
        "rows": rows,
    }
    target = ROUTE_A_ROOT / "V22_ROUTE_A_EVIDENCE_INDEX.json"
    digest = write_json(target, index)
    print(f"wrote {target} sha256={digest}")
    for row in rows:
        causes = row["unsafe_cause_counts"]
        print(
            f"{row['row_id']:14} goal={row['goal_of_16']:>2}/16 supX={row['supported_crossing_of_16']:>2}/16 "
            f"clr_ok={row['clearance_success_of_16']:>2} unsafe_raw={row['unsafe_release_raw_of_16']:>2} "
            f"real_safety={row['real_safety_violations_of_16']:>2} "
            f"causes={{spd:{causes['excessive_release_speed']},body:{causes['post_release_body_contact']},"
            f"frame:{causes['frame_contact_after_release']},pre:{causes['pre_clear_support_loss']},"
            f"post:{causes['post_clear_natural_release']},none:{causes['none']}}} "
            f"relv95={row['release_velocity_p95'] if row['release_velocity_p95'] is None else round(row['release_velocity_p95'],3)} "
            f"hingeX={None if row['hinge_at_crossing_p50'] is None else round(row['hinge_at_crossing_p50'],3)} "
            f"cmdP50={row['cmd_abs_pitch_p50_of_env_p50']:.3f}/{row['cmd_abs_roll_p50_of_env_p50']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
