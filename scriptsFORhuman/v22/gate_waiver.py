"""Signed v22 gate waivers (plan §3.3).

A waiver is an artifact, not a decision made in prose.  It names the original
gate, the observed value, the replacement, the evidence it rests on, and the node
at which it expires.  Hard safety and integrity gates are refused here.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._v22_common import (
    REPO_ROOT,
    V22_LOCK_ROOT,
    V22Error,
    artifact_payload,
    digest,
    read_json,
    sha256_file,
    write_json,
)

# §3.1 hard non-waivable gates.  Naming one of these is refused outright.
NON_WAIVABLE = frozenset(
    {
        "non_finite_physics_or_metrics",
        "checkpoint_config_source_hash_mismatch",
        "fabricated_or_caller_declared_pass_evidence",
        "missing_metric_silently_filled_with_zero",
        "gpu_other_than_physical_0_or_1",
        "hidden_train_time_action_override",
        "root_teleport_or_scripted_task_completion",
        "unsafe_or_unidentified_body_contact",
        "door_frame_contact_accepted_as_assist",
        "staged_reset_state_corruption",
        "wrong_episode_checkpoint_seed_topology",
        "pooled48_release_goal",
    }
)


def build_posture_gates_report_only_waiver(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    lock_root = Path(repo_root) / V22_LOCK_ROOT
    baseline = read_json(lock_root / "V22_POSTURE_BASELINE.json")
    adjudication = read_json(lock_root / "V22_POSTURE_DENOMINATOR_ADJUDICATION.json")
    freeze = read_json(lock_root / "V22_POSTURE_GATE_FREEZE.json")
    atlas = read_json(lock_root / "V22_POSTURE_ATLAS.json")
    source_lock = read_json(lock_root / "V22_SOURCE_LOCK.json")

    if adjudication["posture_gate_state"] == "BINDING":
        raise V22Error("posture gates are binding; a POSTURE_GATES_REPORT_ONLY waiver is not needed")

    body = {
        "waiver_id": "POSTURE_GATES_REPORT_ONLY",
        "timestamp_hkt": datetime.now(timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds"),
        "worker_identity": "base_v22 execution worker (automated, on the production host)",
        "original_gate": "posture_gates",
        "observed_value": {
            "posture_gate_state": adjudication["posture_gate_state"],
            "posture_need_state": adjudication["posture_need_state"],
            "contributing_episodes": adjudication["contributing_episodes"],
            "contributing_episodes_min": adjudication["contributing_episodes_min"],
            "ordinary_need_negative_frames": adjudication["ordinary_need_negative_frames"],
            "ordinary_need_negative_frames_min": adjudication["ordinary_need_negative_frames_min"],
            "fraction_of_ordinary_frames_need_negative": adjudication[
                "fraction_of_ordinary_frames_need_negative"
            ],
            "measured_arm_joint_margin_p10": atlas["workspace_margin_measured_p10"],
            "measured_arm_joint_margin_p50": atlas["workspace_margin_measured_p50"],
        },
        "decision": "SUSPEND",
        "replacement_gate": (
            "Posture quantities are reported on the frozen B0 denominator and compared against "
            "the resolved §16.2/§16.3 arithmetic, but no posture comparison may block admission, "
            "pilot classification, formal training, Route A, Route B, or a research-complete "
            "result.  No release claim may rest on a posture gate under this waiver."
        ),
        "evidence_paths": [
            str(lock_root / "V22_POSTURE_BASELINE.json"),
            str(lock_root / "V22_POSTURE_DENOMINATOR_ADJUDICATION.json"),
            str(lock_root / "V22_POSTURE_GATE_FREEZE.json"),
            str(lock_root / "V22_POSTURE_ATLAS.json"),
            baseline["producer"]["trace_path"],
        ],
        "scientific_reason": (
            "P0-POSTURE-BASELINE measured the ordinary_need_negative denominator on the exact "
            "frozen B1@500 warm start and found "
            f"{adjudication['ordinary_need_negative_frames']} frames across "
            f"{adjudication['contributing_episodes']} contributing episodes, below the "
            "pre-registered 1000-frame floor.  The cause is measured, not incidental: the arm's "
            "hard-limit joint margin has p10 ~ 0 during a valid hold, so the §7.3 workspace "
            "criterion is satisfied on almost every ordinary opening frame and posture_need is "
            "overactive by construction.  The pre-registered 0.15 margin was retained rather "
            "than re-fitted, because the measured lower tail is degenerate and adapting to it "
            "would make workspace_need unable to fire at all.  §7.6.4 designates exactly this "
            "outcome REPORT_ONLY_INSUFFICIENT_DENOMINATOR and states it must not block the round."
        ),
        "safety_impact": (
            "None.  No hard integrity or contact-safety gate is touched.  Clearance safety, "
            "post-release collision, unsafe release, body-identity and frame-contact gates all "
            "remain in force exactly as pre-registered."
        ),
        "claim_impact": (
            "Ordinary-posture release claims and posture-need precision are report-only for this "
            "round.  V22_POSTURE_CLEARANCE_RELEASE may not be claimed on posture evidence alone. "
            "The pooled48 >= 46/48 release goal is untouched and remains non-waivable."
        ),
        "affected_nodes": ["pilot", "formal Wave 1", "formal Wave 2", "formal Wave 3", "Route A", "Route B"],
        "expiration_node": (
            "A rerun of P0-POSTURE-BASELINE that reaches the 1000-frame denominator, or a "
            "Window-A re-calibration of the §7.3 workspace criterion on a stronger measured basis."
        ),
        "source_lock_sha256": source_lock["source_lock_sha256"],
        "posture_baseline_sha256": baseline["posture_baseline_sha256"],
        "adjudication_sha256": adjudication["adjudication_sha256"],
        "posture_gate_freeze_sha256": freeze["posture_gate_freeze_sha256"],
        "posture_atlas_sha256": atlas["posture_atlas_sha256"],
    }
    if body["original_gate"] in NON_WAIVABLE:
        raise V22Error(f"{body['original_gate']} is a hard non-waivable gate")
    return artifact_payload(
        "gate_waiver",
        status="GATE_WAIVER_SIGNED",
        **body,
        waiver_sha256=digest(body),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--waiver", default="POSTURE_GATES_REPORT_ONLY")
    args = parser.parse_args(argv)
    if args.waiver != "POSTURE_GATES_REPORT_ONLY":
        raise V22Error(f"unknown v22 waiver {args.waiver!r}")
    payload = build_posture_gates_report_only_waiver()
    target = REPO_ROOT / V22_LOCK_ROOT / f"V22_GATE_WAIVER_{args.waiver}.json"
    write_json(target, payload)
    print(f"wrote {target}\nwaiver_sha256={payload['waiver_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
