"""Publish the final v22 release taxonomy from frozen Route-A/B/render evidence."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scriptsFORhuman.v22._v22_common import V22Error, read_json, write_json  # noqa: E402


CANDIDATES = (
    {
        "wave": "wave1",
        "selection": Path("logs_eval/base_v22/postformal_20260806_route_a/V22_ROUTE_A_SELECTION.json"),
        "route_b": Path("logs_eval/base_v22/route_b_20260806_g1_step1250"),
        "render": Path("logs_eval/base_v22/render_20260806_g1_step1250"),
    },
    {
        "wave": "wave2",
        "selection": Path(
            "logs_eval/base_v22/postformal_20260808_route_a_wave23/"
            "V22_ROUTE_A_SELECTION_WAVE2.json"
        ),
        "route_b": Path("logs_eval/base_v22/route_b_20260808_g4_step1750"),
        "render": Path("logs_eval/base_v22/render_20260808_g4_step1750"),
    },
    {
        "wave": "wave3",
        "selection": Path(
            "logs_eval/base_v22/postformal_20260808_route_a_wave23/"
            "V22_ROUTE_A_SELECTION_WAVE3.json"
        ),
        "route_b": Path("logs_eval/base_v22/route_b_20260808_g5_step0750"),
        "render": Path("logs_eval/base_v22/render_20260808_g5_step0750"),
    },
)


def compact_route_b(analysis: dict) -> dict:
    return {
        "candidate": analysis["candidate"],
        "pooled48": analysis["pooled48"]["summary"],
        "dynamics48_realized": {
            name: {
                key: value
                for key, value in run.items()
                if key
                in {
                    "goal_of_16",
                    "supported_crossing_of_16",
                    "clearance_success_of_16",
                    "real_safety_violations_of_16",
                    "body_assist_eligible_of_16",
                    "body_panel_contact_of_16",
                    "unauthorized_body_contact_of_16",
                    "body_panel_force_max_n",
                }
            }
            for name, run in analysis["dynamics80_realized48"].items()
        },
        "holdout64": analysis["holdout64"]["summary"],
        "standard_profile": analysis["standard_profile"],
        "standard_profile_pass": analysis["standard_profile_pass"],
        "release_goal_nonwaivable_pass": analysis["release_goal_nonwaivable_pass"],
        "H3_H4_state": analysis["H3_H4_state"],
    }


def strategy_counts(analysis: dict) -> Counter:
    counts: Counter = Counter()
    groups = [
        *analysis["pooled48"]["runs"],
        *analysis["dynamics80_realized48"].values(),
        *analysis["holdout64"]["runs"],
    ]
    for run in groups:
        counts.update(env["strategy"] for env in run["envs"])
    return counts


def body_summary(analysis: dict) -> dict:
    groups = [
        *analysis["pooled48"]["runs"],
        *analysis["dynamics80_realized48"].values(),
        *analysis["holdout64"]["runs"],
    ]
    envs = [env for run in groups for env in run["envs"]]
    return {
        "episode_count": len(envs),
        "eligible": sum(bool(env["body_assist_eligible"]) for env in envs),
        "approved_contact": sum(bool(env["approved_body_contact"]) for env in envs),
        "unauthorized_contact": sum(bool(env["unauthorized_body_contact"]) for env in envs),
        "contact_force_max_n": max(env["body_panel_force_max_n"] for env in envs),
    }


def compact_render(summary: dict, adjudication: dict) -> dict:
    return {
        "status": "PASS" if summary["status"] in {"PASS", "RENDER_PASS"} else summary["status"],
        "media_files_primary_total": summary["media_files_primary_total"],
        "scenarios": {
            name: {
                key: value
                for key, value in row.items()
                if key
                in {
                    "exit_code",
                    "primary_mp4",
                    "goal_of_16",
                    "supported_crossing_of_16",
                    "post_release_body_contact_of_16",
                }
            }
            for name, row in summary["scenarios"].items()
        },
        "visual_adjudication": adjudication,
    }


def render_body_summary(adjudication: dict) -> dict:
    rows = adjudication["scenario_metrics"].values()
    approved = sum(row["approved_contact"] for row in rows)
    return {
        "eligible": sum(row["eligible"] for row in rows),
        "approved_contact": approved,
        "unauthorized_contact": sum(row["unauthorized_contact"] for row in rows),
        "contact_force_max_n": max(row["body_force_max_n"] for row in rows),
        "single_approved_contact_p95_le_180": (
            approved != 1
            or max(row["body_force_max_n"] for row in rows) <= 180.0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--render-adjudication",
        type=Path,
        default=Path("logs_eval/base_v22/V22_RENDER_ADJUDICATION.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs_eval/base_v22/V22_FINAL_ANALYSIS.json"),
    )
    args = parser.parse_args()

    visual = read_json(args.render_adjudication)
    if visual["status"] != "COMPLETE_QUESTION_1_TO_7":
        raise V22Error("render adjudication is incomplete")

    candidates = []
    full_analyses = []
    all_strategies: Counter = Counter()
    for spec in CANDIDATES:
        selection = read_json(spec["selection"])
        terminal = read_json(spec["route_b"] / "V22_ROUTE_B_TERMINAL_STATUS.json")
        if terminal["status"] != "PASS":
            raise V22Error(f"{spec['wave']} Route-B is not PASS")
        analysis = read_json(spec["route_b"] / "V22_ROUTE_B_ANALYSIS.json")
        render = read_json(spec["render"] / "V22_RENDER_SUMMARY.json")
        if render["status"] not in {"PASS", "RENDER_PASS"}:
            raise V22Error(f"{spec['wave']} render is not PASS")
        if analysis["candidate"]["row_id"] != selection["selected"]["row_id"]:
            raise V22Error(f"{spec['wave']} selection/analysis mismatch")
        counts = strategy_counts(analysis)
        all_strategies.update(counts)
        body = body_summary(analysis)
        render_adjudication = visual["candidates"][spec["wave"]]
        render_body = render_body_summary(render_adjudication)
        body["render"] = render_body
        compact = compact_route_b(analysis)
        compact.update(
            {
                "wave": spec["wave"],
                "strategy_counts": dict(counts),
                "body_assist": body,
                "render": compact_render(render, render_adjudication),
                "release_blockers": [
                    key
                    for key, passed in analysis["standard_profile"].items()
                    if not passed
                ]
                + (["Dynamics80 incomplete: H3/H4 unrealized"] if analysis["H3_H4_state"] != "REALIZED" else [])
                + (["render unauthorized body contact"] if render_body["unauthorized_contact"] else [])
                + (["render approved-contact force profile exceeds 180 N"] if not render_body["single_approved_contact_p95_le_180"] else []),
            }
        )
        candidates.append(compact)
        full_analyses.append(analysis)

    posture = read_json(Path("logs_eval/base_v22/locks/V22_POSTURE_CAUSAL_INTERVENTION.json"))
    bucket = read_json(Path("logs_eval/base_v22/locks/V22_BUCKET_REPRODUCTION.json"))
    contact = read_json(Path("logs_eval/base_v22/locks/V22_BODY_CONTACT_PROBE.json"))
    clearance = read_json(Path("logs_eval/base_v22/locks/V22_CLEARANCE_REPLAY.json"))
    torque = read_json(Path("logs_eval/base_v22/locks/V22_HINGE_TORQUE_RESOLUTION.json"))

    release_candidates = [
        row
        for row in candidates
        if row["standard_profile_pass"]
        and row["H3_H4_state"] == "REALIZED"
        and row["render"]["status"] == "PASS"
    ]
    body_candidate = next(row for row in candidates if row["candidate"]["cell"] in {"G5", "G6"})
    labels = ["V22_RESEARCH_PASS_NO_RELEASE"]
    if bucket["status"] != "PASS":
        labels.append("V22_RANDOMIZATION_BOUNDARY_IDENTIFIED")
    if posture["posture_need_precision"] >= 0.9 and posture["posture_need_recall"] >= 0.9:
        labels.append("V22_POSTURE_CONDITIONALLY_USEFUL_NO_RELEASE")
    total_approved_body_contact = (
        body_candidate["body_assist"]["approved_contact"]
        + body_candidate["body_assist"]["render"]["approved_contact"]
    )
    if body_candidate["body_assist"]["eligible"] > 0 and total_approved_body_contact == 0:
        labels.append("V22_BODY_ASSIST_NOT_TRIGGERED")
    if (
        body_candidate["body_assist"]["unauthorized_contact"] > 0
        or body_candidate["body_assist"]["contact_force_max_n"] > 300.0
        or body_candidate["body_assist"]["render"]["unauthorized_contact"] > 0
        or not body_candidate["body_assist"]["render"]["single_approved_contact_p95_le_180"]
    ):
        labels.append("V22_BODY_ASSIST_UNSAFE")
    if (
        all_strategies
        and all_strategies["HAND_HOLD_CLEARANCE"] / sum(all_strategies.values()) >= 0.95
    ):
        labels.append("V22_HOLD_OPEN_DOMINANT")

    payload = {
        "schema": "a2_piper_base_v22_final_analysis_v1",
        "plan_id": "base_v22_posture_clearance_force_routing_v3",
        "execution_id": "base_v22_execution_v3",
        "release": {
            "V22_POSTURE_CLEARANCE_RELEASE": bool(release_candidates),
            "V22_FORCE_ROUTING_RELEASE": False,
            "decision": "NO_RELEASE" if not release_candidates else "POSTURE_CLEARANCE_RELEASE",
            "non_release_labels": labels if not release_candidates else [],
            "reason": (
                "No candidate passes the frozen STANDARD profile and complete Dynamics80; "
                "H3/H4 remain unrealized."
                if not release_candidates
                else "At least one candidate satisfies the complete release evidence path."
            ),
        },
        "candidates": candidates,
        "cross_candidate_strategy_counts": dict(all_strategies),
        "admission_and_causal_probes": {
            "P0_B": {
                "status": posture["status"],
                "label_counts": posture["label_counts"],
                "posture_need_precision": posture["posture_need_precision"],
                "posture_need_recall": posture["posture_need_recall"],
                "precision_binding_state": posture["precision_binding_state"],
            },
            "P0_E": {
                "status": contact["status"],
                "target_pass": contact["target_pass"],
            },
            "P0_F": {
                "status": clearance["status"],
                "strategy_counts": clearance["strategy_counts"],
                "real_safety_violations_of_16": clearance[
                    "real_safety_violations_of_16"
                ],
            },
            "bucket_reproduction": {
                "status": bucket["status"],
                "by_bucket": bucket["by_bucket"],
            },
            "higher_torque_probe": {
                "status": torque["status"],
                "freeze_effect": torque["freeze_effect"],
                "newly_realized_resistive_classes": torque[
                    "newly_realized_resistive_classes"
                ],
            },
        },
        "frozen_interpretation": {
            "posture_gate_state": "REPORT_ONLY_INSUFFICIENT_DENOMINATOR",
            "unsafe_release": (
                "Raw v22_unsafe_release is not used for eligibility: natural hand release after "
                "root-clear is separated from excessive speed, panel/frame contact, and pre-clear support loss."
            ),
            "dynamics_scope": "Only H0/H1/H2 were realized; E3/E4 are omitted, not treated as passing.",
            "body_probe_scope": (
                "P0-E proves that safe trunk/front-thigh contact routes are feasible; it does not "
                "substitute for a body-assist increment in policy evaluation."
            ),
        },
    }
    write_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "release": payload["release"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V22Error as exc:
        raise SystemExit(f"V22 FINAL ANALYSIS FAIL: {exc}")
