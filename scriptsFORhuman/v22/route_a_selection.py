"""Record the lead's §14 Wave-2/Wave-3 Route-A checkpoint adjudication.

The script does not assign a weighted score.  It validates the initial §14
eligibility guide, preserves every candidate's dependent variables, and records
the lead's ordered-selection rationale for the chosen row.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scriptsFORhuman.v22._v22_common import REPO_ROOT, V22Error, read_json, write_json


ROUTE_A_ROOT = REPO_ROOT / "logs_eval/base_v22/postformal_20260808_route_a_wave23"
EVIDENCE_INDEX_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_EVIDENCE_INDEX.json"
WAVE_CELLS = {2: ("G3", "G4"), 3: ("G5", "G6")}


def _screen(row: dict) -> dict:
    body_contact = int(row["record_post_release_body_contact_of_16"])
    unauthorized_body_contact = int(row["unauthorized_body_contact_of_16"])
    real_safety = int(row["real_safety_violations_of_16"])
    goal = int(row["goal_of_16"])
    supported = int(row["supported_crossing_of_16"])
    return {
        "goal": goal,
        "supported_crossing": supported,
        "real_safety_violations": real_safety,
        "post_release_body_contact": body_contact,
        "clearance_success": int(row["clearance_success_of_16"]),
        "cmd_pitch_p50": row["cmd_abs_pitch_p50_of_env_p50"],
        "cmd_roll_p50": row["cmd_abs_roll_p50_of_env_p50"],
        "release_velocity_p95": row["release_velocity_p95"],
        "hinge_at_crossing_p50": row["hinge_at_crossing_p50"],
        "strategy_counts": row["strategy_counts"],
        "unsafe_cause_counts": row["unsafe_cause_counts"],
        "arm_failure_latched": row["arm_failure_latched_of_16"],
        "body_assist_eligible": row["body_assist_eligible_of_16"],
        "force_need": row["force_need_of_16"],
        "body_panel_contact": row["body_panel_contact_of_16"],
        "unauthorized_body_contact": unauthorized_body_contact,
        "body_panel_force_max_n": row["body_panel_force_max_n"],
        "eligible": (
            goal >= 14
            and supported >= 13
            and real_safety <= 2
            and unauthorized_body_contact == 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", type=int, choices=tuple(WAVE_CELLS), required=True)
    parser.add_argument("--selected-row", required=True)
    parser.add_argument("--rationale", required=True)
    args = parser.parse_args()

    index = read_json(EVIDENCE_INDEX_PATH)
    rows = [row for row in index["rows"] if row["cell"] in WAVE_CELLS[args.wave]]
    selected = next((row for row in rows if row["row_id"] == args.selected_row), None)
    if selected is None:
        raise V22Error(f"selected row {args.selected_row!r} is not in Wave {args.wave}")
    eligibility = {row["row_id"]: _screen(row) for row in rows}
    if not eligibility[args.selected_row]["eligible"]:
        raise V22Error(f"selected row {args.selected_row!r} does not meet the §14 initial eligibility guide")

    payload = {
        "schema": "a2_piper_base_v22_route_a_wave_selection_v1",
        "plan_id": "base_v22_posture_clearance_force_routing_v3",
        "execution_id": "base_v22_execution_v3",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "wave": args.wave,
        "cells": list(WAVE_CELLS[args.wave]),
        "inputs": {
            "evidence_index_path": str(EVIDENCE_INDEX_PATH),
            "row_count": len(rows),
            "topology": "canonical16 first-episode",
        },
        "posture_gate_state": "REPORT_ONLY_INSUFFICIENT_DENOMINATOR",
        "selection_method": (
            "lead adjudication in plan §14 order: integrity/contact safety; goal/supported crossing; "
            "ordinary posture pathology; clearance/rebound; hinge robustness; task time/crossing; "
            "body-assist increment where applicable. No weighted score."
        ),
        "lead_rationale": args.rationale,
        "unsafe_release_interpretation": (
            "eligibility uses causal real-safety classes; post_clear_natural_release is preserved "
            "but excluded as the known release-detection-order artifact"
        ),
        "eligibility_screen": eligibility,
        "selected": {
            "row_id": selected["row_id"],
            "cell": selected["cell"],
            "step": selected["step"],
            "seed": selected["seed"],
            "checkpoint_path": selected["checkpoint_path"],
            "dv_summary": eligibility[selected["row_id"]],
        },
    }
    target = ROUTE_A_ROOT / f"V22_ROUTE_A_SELECTION_WAVE{args.wave}.json"
    write_json(target, payload)
    print(f"WROTE {target} selected={args.selected_row}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V22Error as exc:
        raise SystemExit(f"V22 ROUTE_A SELECTION FAIL: {exc}")
