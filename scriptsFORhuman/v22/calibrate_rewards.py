"""Window-A reward calibration record for the v22 posture and clearance terms.

§7.5 target income ranges are guidance, not blockers.  This module records what
was measured on the 64-env / 10-iteration smoke, which scale was moved, and — more
importantly — which targets were NOT reached and why, so no later reader mistakes
an unreached guidance band for an unnoticed one.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from ._v22_common import (
    REPO_ROOT,
    V22_LOCK_ROOT,
    artifact_payload,
    digest,
    read_json,
    write_json,
)

# Measured on the base_v22 G1 64-env / 10-iteration smoke, mean episode sums.
SMOKE_ABSOLUTE_EPISODE_REWARD = 8.6

MEASURED = {
    "penalty_a2_v22_excess_posture": {
        "scale": -2.0,
        "mean_episode_sum_before": -0.0037,
        "mean_episode_sum_after": -0.0040,
        "share_of_absolute_episode_reward": 0.0005,
        "target_band": [0.01, 0.05],
        "within_target": False,
    },
    "penalty_a2_v22_posture_saturation": {
        "scale_before": -4.0,
        "scale": -16.0,
        "registered_multiplier_applied": 4,
        "mean_episode_sum_before": -0.0807,
        "mean_episode_sum_after": -0.3565,
        "share_of_absolute_episode_reward": 0.0415,
        "target_band": [0.02, 0.08],
        "within_target": True,
    },
    "a2_v22_posture_feasibility": {
        "scale": 0.5,
        "mean_episode_sum_after": 0.0008,
        "share_of_positive_income": 0.0001,
        "target_band": [0.01, 0.06],
        "within_target": False,
    },
    "a2_v22_clearance_success": {"scale": 4.0, "mean_episode_sum_after": 0.0009},
    "a2_v22_controlled_fling": {"scale": 2.0, "mean_episode_sum_after": 0.0},
    "penalty_a2_v22_unsafe_release": {"scale": -8.0, "mean_episode_sum_after": -0.0024},
}

UNREACHED_TARGET_REASONS = {
    "penalty_a2_v22_excess_posture": (
        "The term is gated by (1 - posture_need) and posture_need is active on ~96% of "
        "frames on this warm start, so the term can only act on the residual ~4%.  "
        "Reaching the 1-5% income band would require roughly a 45x scale increase, which "
        "would make those few need-negative frames pathological.  The scale is therefore "
        "held at -2.0 and the shortfall is reported.  This is the same measured cause as "
        "the POSTURE_NEED_OVERACTIVE_OR_VACUOUS adjudication."
    ),
    "a2_v22_posture_feasibility": (
        "The reward multiplies arm_margin_quality, which is structurally near zero on this "
        "warm start: the arm's hard-limit joint margin has p10 ~ 0 and effort utilization "
        "averages ~0.79 during the hold.  Scaling up would be fitting a scale to a "
        "degenerate factor rather than calibrating an active mechanism."
    ),
}


def build_calibration(repo_root: Path = REPO_ROOT) -> dict:
    lock_root = Path(repo_root) / V22_LOCK_ROOT
    source_lock = read_json(lock_root / "V22_SOURCE_LOCK.json")
    atlas = read_json(lock_root / "V22_POSTURE_ATLAS.json")
    body = {
        "window": "A",
        "basis": "base_v22 G1 smoke, 64 env, 10 iterations, warm start policy_only",
        "absolute_episode_reward_reference": SMOKE_ABSOLUTE_EPISODE_REWARD,
        "terms": MEASURED,
        "changes_applied": [
            {
                "term": "penalty_a2_v22_posture_saturation",
                "from": -4.0,
                "to": -16.0,
                "reason": "measured 0.9% of absolute episode reward against the §7.5 2-8% band",
            }
        ],
        "targets_not_reached": UNREACHED_TARGET_REASONS,
        "guidance_status": "§7.5 income ranges are guidance, not hard blockers",
        "posture_atlas_sha256": atlas["posture_atlas_sha256"],
    }
    return artifact_payload(
        "reward_calibration",
        status="REWARD_CALIBRATION_COMPLETE",
        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        source_lock_sha256=source_lock["source_lock_sha256"],
        **body,
        reward_calibration_sha256=digest(body),
    )


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    payload = build_calibration()
    target = REPO_ROOT / V22_LOCK_ROOT / "V22_REWARD_CALIBRATION.json"
    write_json(target, payload)
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
