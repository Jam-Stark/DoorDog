"""Forward-only, CRN-paired v23 posture intervention plan.

The current repository supports episode/prefix replay, not exact PhysX state
cloning.  Each intervention therefore shares a scenario seed and replay prefix
with FULL, then switches the forward action rule at a declared event.  A
missing prefix is an explicit error; it is never replaced with an empty or
zero-valued state.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._v23_common import (
    V23Error,
    V23_INTERVENTION_MODES,
    artifact_payload,
    emit_payload,
    read_json,
)


SWITCH_RULES = {
    "FULL": {"switch_event": "none", "posture_policy": "trained_policy"},
    "ACUTE_RP0": {"switch_event": "episode_start", "posture_policy": "rp0_distribution_mask"},
    "BASE0_AT_GRASP": {"switch_event": "stable_grasp_latch", "posture_policy": "base0_neutral"},
    "HIGHER_EFFORT_RESCUE": {"switch_event": "typed_failure_latch", "posture_policy": "higher_effort_forward_only"},
    "ORACLE_TANGENTIAL_ASSIST": {"switch_event": "typed_failure_latch", "posture_policy": "oracle_eval_only"},
}

INTERVENTION_MODES = V23_INTERVENTION_MODES

A2_V23_EFFORT_PROFILE_APPLIED_FIELD = "a2_v23_effort_profile_applied"
A2_V23_ORACLE_OVERRIDE_FIELDS = (
    "a2_v23_oracle_tangential_delta_raw",
    "a2_v23_oracle_active_mask",
)


def _scenario_ids(value: Sequence[str] | str) -> list[str]:
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",") if item.strip()]
    else:
        values = list(value)
    if not values or any(not isinstance(item, str) or not item for item in values):
        raise V23Error("at least one non-empty scenario id is required")
    if len(set(values)) != len(values):
        raise V23Error("scenario ids must be unique for CRN pairing")
    return values


def build_intervention_plan(
    scenarios: Sequence[str] | str = ("A0_stage2", "A0_stage3", "A0_stage4"),
    *,
    seed: int = 0,
) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise V23Error("CRN seed must be an integer")
    scenario_ids = _scenario_ids(scenarios)
    rows = []
    for scenario_index, scenario_id in enumerate(scenario_ids):
        prefix_id = f"seed{seed}_scenario{scenario_index:03d}"
        for mode in V23_INTERVENTION_MODES:
            rows.append(
                {
                    "pair_id": f"{prefix_id}_{mode.lower()}",
                    "scenario_id": scenario_id,
                    "seed": seed,
                    "replay_prefix_id": prefix_id,
                    "mode": mode,
                    "switch_rule": SWITCH_RULES[mode],
                    "required_actor_state_fields": (
                        list(A2_V23_ORACLE_OVERRIDE_FIELDS)
                        if mode == "ORACLE_TANGENTIAL_ASSIST"
                        else [A2_V23_EFFORT_PROFILE_APPLIED_FIELD]
                        if mode == "HIGHER_EFFORT_RESCUE"
                        else []
                    ),
                    "state_clone": "STATE_CLONE_NOT_SUPPORTED",
                    "missing_input_policy": "TYPED_STATUS_REQUIRED",
                    "outcome_fields": {
                        "episode_return": "PENDING",
                        "hinge_progress_window_rad": "PENDING",
                        "delta_j_phi_vs_full": "PENDING",
                        "failure_probability_vs_full": "PENDING",
                    },
                }
            )
    return artifact_payload(
        "posture_intervention",
        status="PLAN_ONLY_FORWARD_SWITCHING",
        seed=seed,
        scenarios=scenario_ids,
        modes=list(V23_INTERVENTION_MODES),
        rows=rows,
        crn_contract={
            "pairing_key": ["seed", "scenario_id", "replay_prefix_id"],
            "prefix_reuse": "same_prefix_across_all_modes",
            "episode_or_prefix_switching": True,
            "exact_state_clone": False,
        },
        route_scope="Route B selected checkpoints only",
        p0_numeric_state="PENDING_UNTIL_MEASURED",
    )


def build_forward_intervention_actor_state(
    mode: str,
    *,
    oracle_tangential_delta_raw: Sequence[Any] | None = None,
    oracle_active_mask: Sequence[Any] | None = None,
    effort_profile_applied: bool | None = None,
) -> dict[str, Any]:
    """Build the explicit state fields consumed by the standard evaluator."""

    if mode not in V23_INTERVENTION_MODES:
        raise V23Error(f"unsupported v23 intervention mode: {mode!r}")
    if mode == "ORACLE_TANGENTIAL_ASSIST":
        if oracle_tangential_delta_raw is None or oracle_active_mask is None:
            raise V23Error(
                "ORACLE_TANGENTIAL_ASSIST requires both explicit oracle override fields: "
                f"{A2_V23_ORACLE_OVERRIDE_FIELDS!r}"
            )
        return {
            A2_V23_ORACLE_OVERRIDE_FIELDS[0]: oracle_tangential_delta_raw,
            A2_V23_ORACLE_OVERRIDE_FIELDS[1]: oracle_active_mask,
        }
    if mode == "HIGHER_EFFORT_RESCUE":
        if effort_profile_applied is not True:
            raise V23Error(
                f"HIGHER_EFFORT_RESCUE requires {A2_V23_EFFORT_PROFILE_APPLIED_FIELD}=true"
            )
        return {A2_V23_EFFORT_PROFILE_APPLIED_FIELD: True}
    if oracle_tangential_delta_raw is not None or oracle_active_mask is not None:
        raise V23Error(f"{mode} does not accept oracle override fields")
    if effort_profile_applied is not None:
        raise V23Error(f"{mode} does not accept an effort-profile proof field")
    return {}


def apply_forward_switch(episode: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Create an intervention record from an existing replay prefix.

    This function does not mutate the episode or perform a simulator call.  It
    requires a concrete prefix and leaves outcome quantities pending for the
    runtime consumer.
    """

    if mode not in V23_INTERVENTION_MODES:
        raise V23Error(f"unsupported v23 intervention mode: {mode!r}")
    if not isinstance(episode, Mapping):
        raise V23Error("episode must be a mapping")
    for key in ("scenario_id", "seed", "replay_prefix_id"):
        if key not in episode:
            raise V23Error(f"forward intervention requires episode.{key}")
    if "replay_prefix" not in episode:
        raise V23Error("forward intervention requires replay_prefix; state cloning is unavailable")
    prefix = episode["replay_prefix"]
    if not isinstance(prefix, list) or not prefix:
        raise V23Error("replay_prefix must be a non-empty list")
    if isinstance(episode["seed"], bool) or not isinstance(episode["seed"], int):
        raise V23Error("episode.seed must be an integer")
    return {
        "schema": "a2_piper_v23_intervention_record_v1",
        "scenario_id": episode["scenario_id"],
        "seed": episode["seed"],
        "replay_prefix_id": episode["replay_prefix_id"],
        "mode": mode,
        "switch_rule": SWITCH_RULES[mode],
        "required_actor_state_fields": (
            list(A2_V23_ORACLE_OVERRIDE_FIELDS)
            if mode == "ORACLE_TANGENTIAL_ASSIST"
            else [A2_V23_EFFORT_PROFILE_APPLIED_FIELD]
            if mode == "HIGHER_EFFORT_RESCUE"
            else []
        ),
        "state_clone": "STATE_CLONE_NOT_SUPPORTED",
        "replay_prefix_rows": len(prefix),
        "outcome": "PENDING_RUNTIME_FORWARD_EXECUTION",
        "missing_input_policy": "TYPED_STATUS_REQUIRED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", default="A0_stage2,A0_stage3,A0_stage4")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--episode",
        type=Path,
        default=None,
        help="optional replay-prefix JSON; emits one forward-switch record",
    )
    parser.add_argument("--mode", choices=V23_INTERVENTION_MODES, default=None)
    args = parser.parse_args(argv)
    if args.episode is not None:
        if args.mode is None:
            raise V23Error("--mode is required with --episode")
        payload = apply_forward_switch(read_json(args.episode), args.mode)
    else:
        payload = build_intervention_plan(args.scenarios, seed=args.seed)
    emit_payload(payload, args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 POSTURE INTERVENTION FAIL: {exc}")
