"""P0-F: replay frozen B1 clearance telemetry and reward calibration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scriptsFORhuman.v22._v22_common import V22Error, read_json, write_json  # noqa: E402
from scriptsFORhuman.v22.route_a_analysis import CAUSE_CLASSES, analyze_env  # noqa: E402


SOURCE_ROOT = REPO / "logs_eval/base_v22/p0_posture_baseline"
CALIBRATION_PATH = REPO / "logs_eval/base_v22/locks/V22_REWARD_CALIBRATION.json"
OUTPUT_PATH = REPO / "logs_eval/base_v22/locks/V22_CLEARANCE_REPLAY.json"


def main() -> int:
    trace = read_json(SOURCE_ROOT / "stage2_step_trace.json")
    metrics = read_json(SOURCE_ROOT / "metrics_eval.json")
    calibration = read_json(CALIBRATION_PATH)
    by_env: dict[int, list[dict]] = {}
    for step in trace:
        by_env.setdefault(int(step["env_id"]), []).append(step)
    envs = [analyze_env(by_env[env_id]) for env_id in sorted(by_env)]
    terminal_by_env = {int(row["env_id"]): row for row in metrics["episode_terminal_diagnostics"]}
    for env_id in sorted(set(range(16)) - set(by_env)):
        terminal = terminal_by_env[env_id]
        envs.append(
            {
                "env_id": env_id,
                "cause": "none",
                "strategy": terminal["v22_clearance_strategy"],
                "clearance_success": terminal["v22_clearance_success"],
                "release_buf": None,
                "release_velocity_radps": terminal["v22_release_hinge_velocity_radps"],
                "min_hinge_after_release_rad": terminal["v22_min_hinge_after_release_rad"],
                "peak_closing_velocity_radps": terminal["v22_peak_closing_velocity_radps"],
                "episode_evidence": "terminal_only_no_stage_trace",
            }
        )
    envs.sort(key=lambda env: env["env_id"])
    causes = {cause: 0 for cause in CAUSE_CLASSES}
    strategies: dict[str, int] = {}
    for env in envs:
        causes[env["cause"]] += 1
        strategies[str(env["strategy"])] = strategies.get(str(env["strategy"]), 0) + 1

    released = [env for env in envs if env["release_buf"] is not None]
    missing_release_velocity = [env["env_id"] for env in released if env["release_velocity_radps"] is None]
    missing_clearance_window = [
        env["env_id"]
        for env in released
        if env["min_hinge_after_release_rad"] is None or env["peak_closing_velocity_radps"] is None
    ]
    expected_scales = {
        "a2_v22_clearance_success": 4.0,
        "a2_v22_controlled_fling": 2.0,
        "penalty_a2_v22_unsafe_release": -8.0,
    }
    scale_checks = {
        term: calibration["terms"][term]["scale"] == expected
        for term, expected in expected_scales.items()
    }
    telemetry_pass = not missing_release_velocity and not missing_clearance_window
    calibration_pass = calibration["status"] == "REWARD_CALIBRATION_COMPLETE" and all(scale_checks.values())
    payload = {
        "schema": "a2_piper_base_v22_clearance_replay_v1",
        "plan_id": "base_v22_posture_clearance_force_routing_v3",
        "execution_id": "base_v22_execution_v3",
        "node": "P0-F",
        "status": "P0_F_PASS" if telemetry_pass and calibration_pass else "P0_F_FAIL",
        "source": {
            "checkpoint": "frozen B1@500 warm start",
            "trace_path": str(SOURCE_ROOT / "stage2_step_trace.json"),
            "episodes": len(envs),
            "stage_trace_envs": len(by_env),
            "terminal_only_envs": sorted(set(range(16)) - set(by_env)),
        },
        "strategy_counts": strategies,
        "clearance_success_of_16": sum(1 for env in envs if env["clearance_success"]),
        "unsafe_cause_counts": causes,
        "real_safety_violations_of_16": sum(
            causes[cause]
            for cause in (
                "excessive_release_speed",
                "post_release_body_contact",
                "frame_contact_after_release",
                "pre_clear_support_loss",
            )
        ),
        "release_window_telemetry": {
            "released_episodes": len(released),
            "missing_release_velocity_envs": missing_release_velocity,
            "missing_min_hinge_or_peak_closing_envs": missing_clearance_window,
            "pass": telemetry_pass,
        },
        "reward_calibration": {
            "artifact_path": str(CALIBRATION_PATH),
            "artifact_status": calibration["status"],
            "scale_checks": scale_checks,
            "pass": calibration_pass,
        },
        "unsafe_release_adjudication": (
            "post_clear_natural_release is retained as raw telemetry but excluded from real-safety counts "
            "because the current newly_released ordering stamps natural post-clear hand release"
        ),
        "episodes": envs,
    }
    write_json(OUTPUT_PATH, payload)
    print(json.dumps({"status": payload["status"], "strategies": strategies, "causes": causes}, indent=2))
    return 0 if payload["status"] == "P0_F_PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V22Error as exc:
        raise SystemExit(f"V22 P0-F FAIL: {exc}")
