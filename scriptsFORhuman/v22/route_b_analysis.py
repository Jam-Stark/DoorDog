"""Aggregate one selected checkpoint's §15 Route-B evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scriptsFORhuman.v22._v22_common import V22Error, quantile, read_json, write_json  # noqa: E402
from scriptsFORhuman.v22.route_a_analysis import CAUSE_CLASSES, analyze_env  # noqa: E402


DYNAMICS = ("E0_CORE16", "E1_DAMPING16", "E2_REBOUND16")


def analyze_run(name: str, seed: int, root: Path) -> dict:
    metrics = read_json(root / "metrics_eval.json")
    records = read_json(root / "a2_v14_per_env_records.json")
    trace = read_json(root / "stage2_step_trace.json")
    by_env: dict[int, list[dict]] = {}
    for step in trace:
        by_env.setdefault(int(step["env_id"]), []).append(step)
    envs = [analyze_env(by_env[env_id]) for env_id in sorted(by_env)]
    causes = {cause: 0 for cause in CAUSE_CLASSES}
    for env in envs:
        causes[env["cause"]] += 1
    return {
        "run": name,
        "seed": seed,
        "root": str(root),
        "goal_of_16": sum(1 for value in metrics["episode_goal_reached"] if value is True),
        "supported_crossing_of_16": sum(1 for record in records if record.get("crossing_while_holding") is True),
        "clearance_success_of_16": sum(1 for env in envs if env["clearance_success"]),
        "post_release_body_contact_of_16": sum(1 for env in envs if env["post_release_body_contact"]),
        "arm_failure_latched_of_16": sum(1 for env in envs if env["arm_failure_latched"]),
        "body_assist_eligible_of_16": sum(1 for env in envs if env["body_assist_eligible"]),
        "force_need_of_16": sum(1 for env in envs if env["force_need"]),
        "body_panel_contact_of_16": sum(1 for env in envs if env["body_panel_force_max_n"] > 0.0),
        "unauthorized_body_contact_of_16": sum(
            1 for env in envs if env["unauthorized_body_contact"]
        ),
        "body_panel_force_max_n": max(env["body_panel_force_max_n"] for env in envs),
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
        "release_velocities_radps": [
            env["release_velocity_radps"] for env in envs if env["release_velocity_radps"] is not None
        ],
        "envs": envs,
    }


def aggregate(runs: list[dict], denominator: int) -> dict:
    velocities = [value for run in runs for value in run["release_velocities_radps"]]
    return {
        "denominator": denominator,
        "goal": sum(run["goal_of_16"] for run in runs),
        "supported_crossing": sum(run["supported_crossing_of_16"] for run in runs),
        "clearance_success": sum(run["clearance_success_of_16"] for run in runs),
        "post_release_body_contact": sum(run["post_release_body_contact_of_16"] for run in runs),
        "arm_failure_latched": sum(run["arm_failure_latched_of_16"] for run in runs),
        "body_assist_eligible": sum(run["body_assist_eligible_of_16"] for run in runs),
        "force_need": sum(run["force_need_of_16"] for run in runs),
        "body_panel_contact": sum(run["body_panel_contact_of_16"] for run in runs),
        "unauthorized_body_contact": sum(
            run["unauthorized_body_contact_of_16"] for run in runs
        ),
        "body_panel_force_max_n": max(run["body_panel_force_max_n"] for run in runs),
        "real_safety_violations": sum(run["real_safety_violations_of_16"] for run in runs),
        "excessive_release_speed": sum(run["unsafe_cause_counts"]["excessive_release_speed"] for run in runs),
        "release_velocity_p95": quantile(velocities, 0.95) if velocities else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--route-b-root", type=Path, required=True)
    args = parser.parse_args()

    selection = read_json(args.selection)
    terminal = read_json(args.route_b_root / "V22_ROUTE_B_TERMINAL_STATUS.json")
    if terminal["status"] != "PASS":
        raise V22Error("Route-B terminal status is not PASS")
    selected = selection["selected"]
    selected_seed = int(selected["seed"])
    route_a_root = Path(selection["inputs"]["evidence_index_path"]).parent

    pooled = []
    for seed in (0, 1, 2):
        root = (
            route_a_root
            / selected["cell"]
            / f"step{int(selected['step']):04d}"
            / "canonical16"
            / f"seed{seed}"
            if seed == selected_seed
            else args.route_b_root / "pooled48" / f"seed{seed}" / "canonical16"
        )
        pooled.append(analyze_run(f"pooled_seed{seed}", seed, root))

    dynamics = {
        name: analyze_run(name, 0, args.route_b_root / "dynamics80" / name / "canonical16")
        for name in DYNAMICS
    }
    holdout = [
        analyze_run(
            f"holdout_seed{seed}",
            seed,
            args.route_b_root / "holdout64" / f"seed{seed}" / "canonical16",
        )
        for seed in (3, 4, 5, 6)
    ]
    pooled_summary = aggregate(pooled, 48)
    holdout_summary = aggregate(holdout, 64)
    standard = {
        "pooled_goal_ge_46": pooled_summary["goal"] >= 46,
        "pooled_supported_crossing_ge_44": pooled_summary["supported_crossing"] >= 44,
        "pooled_clearance_success_ge_44": pooled_summary["clearance_success"] >= 44,
        "pooled_real_safety_violations_le_2": pooled_summary["real_safety_violations"] <= 2,
        "pooled_release_velocity_p95_le_0p75": (
            pooled_summary["release_velocity_p95"] is not None
            and pooled_summary["release_velocity_p95"] <= 0.75
        ),
        "holdout_goal_ge_59": holdout_summary["goal"] >= 59,
        "holdout_supported_crossing_ge_58": holdout_summary["supported_crossing"] >= 58,
        "pooled_unauthorized_body_contact_eq_0": pooled_summary[
            "unauthorized_body_contact"
        ]
        == 0,
        "holdout_unauthorized_body_contact_eq_0": holdout_summary[
            "unauthorized_body_contact"
        ]
        == 0,
        "dynamics_unauthorized_body_contact_eq_0": all(
            run["unauthorized_body_contact_of_16"] == 0 for run in dynamics.values()
        ),
        "all_body_panel_force_max_le_300": max(
            pooled_summary["body_panel_force_max_n"],
            holdout_summary["body_panel_force_max_n"],
            *(run["body_panel_force_max_n"] for run in dynamics.values()),
        )
        <= 300.0,
        "E0_goal_ge_15": dynamics["E0_CORE16"]["goal_of_16"] >= 15,
        "E1_goal_ge_13": dynamics["E1_DAMPING16"]["goal_of_16"] >= 13,
        "E2_clearance_success_ge_13": dynamics["E2_REBOUND16"]["clearance_success_of_16"] >= 13,
    }
    payload = {
        "schema": "a2_piper_base_v22_route_b_analysis_v1",
        "plan_id": "base_v22_posture_clearance_force_routing_v3",
        "execution_id": "base_v22_execution_v3",
        "selection_path": str(args.selection),
        "candidate": {key: selected[key] for key in ("row_id", "cell", "step", "seed", "checkpoint_path")},
        "posture_gate_state": "REPORT_ONLY_INSUFFICIENT_DENOMINATOR",
        "H3_H4_state": "UNREALIZED_OMITTED",
        "pooled48": {"summary": pooled_summary, "runs": pooled},
        "dynamics80_realized48": dynamics,
        "holdout64": {"summary": holdout_summary, "runs": holdout},
        "standard_profile": standard,
        "standard_profile_pass": all(standard.values()),
        "release_goal_nonwaivable_pass": pooled_summary["goal"] >= 46,
    }
    target = args.route_b_root / "V22_ROUTE_B_ANALYSIS.json"
    write_json(target, payload)
    print(json.dumps({"target": str(target), "standard": standard}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V22Error as exc:
        raise SystemExit(f"V22 ROUTE_B ANALYSIS FAIL: {exc}")
