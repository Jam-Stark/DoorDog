"""Forward-only, CRN-paired v23 posture intervention plan.

The current repository supports episode/prefix replay, not exact PhysX state
cloning.  Each intervention therefore shares a scenario seed and replay prefix
with FULL, then switches the forward action rule at a declared event.  A
missing prefix is an explicit error; it is never replaced with an empty or
zero-valued state.
"""

from __future__ import annotations

import argparse
import math
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
STATE_BANK_ENTRY_SCHEMA = "a2_piper_v23_state_bank_entry_v1"
STATE_BANK_BINDING_SCHEMA = "a2_piper_v23_state_bank_binding_v1"
STATE_BANK_TARGET_STAGES = (2, 3, 4)


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


def _validate_state_bank_prefix(entry: Mapping[str, Any]) -> None:
    prefix = entry.get("replay_prefix")
    if not isinstance(prefix, list) or not prefix:
        raise V23Error("state-bank entry requires a non-empty replay_prefix")
    entry_env = entry.get("env_id")
    entry_episode = entry.get("episode_index")
    if isinstance(entry_env, bool) or not isinstance(entry_env, int) or entry_env < 0:
        raise V23Error("state-bank entry env_id must be a non-negative integer")
    if isinstance(entry_episode, bool) or not isinstance(entry_episode, int) or entry_episode < 0:
        raise V23Error("state-bank entry episode_index must be a non-negative integer")
    actor_width = None
    for row_index, row in enumerate(prefix):
        if not isinstance(row, Mapping) or row.get("schema") != "a2_piper_v23_state_bank_prefix_row_v1":
            raise V23Error(f"state-bank replay_prefix[{row_index}] schema is unsupported")
        if (
            row.get("env_id") != entry_env
            or row.get("episode_index") != entry_episode
            or row.get("episode_id") != entry.get("episode_id")
        ):
            raise V23Error("state-bank replay-prefix env/episode identity disagrees with its entry")
        if row.get("control_step") != row_index or row.get("done_before_step") is not False:
            raise V23Error("state-bank replay_prefix must be contiguous pre-step rows from control_step 0")
        actor_obs = row.get("actor_obs")
        action_mean = row.get("action_mean")
        applied = row.get("applied_high_level_action")
        if not isinstance(actor_obs, list) or not actor_obs:
            raise V23Error("state-bank replay-prefix actor_obs must be a non-empty list")
        if actor_width is None:
            actor_width = len(actor_obs)
        if len(actor_obs) != actor_width:
            raise V23Error("state-bank replay-prefix actor_obs width must remain consistent")
        if not isinstance(action_mean, list) or not action_mean:
            raise V23Error("state-bank replay-prefix action_mean must be a non-empty list")
        if not isinstance(applied, list) or len(applied) != 12:
            raise V23Error("state-bank replay-prefix applied_high_level_action must be 12-D")
        values = actor_obs + action_mean + applied
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            raise V23Error("state-bank replay-prefix tensors must contain finite numeric values")
    if prefix[-1].get("pre_stage") != entry.get("stage"):
        raise V23Error("state-bank replay-prefix final pre-stage does not match its entry stage")


def bind_state_bank_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    source_identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Bind each captured real prefix to all five forward-only intervention modes."""

    if not isinstance(source_identity, Mapping) or not source_identity:
        raise V23Error("state-bank bindings require a non-empty source identity")
    required_identity = {
        "schema",
        "status",
        "source_freeze_path",
        "source_cell",
        "atlas_cell",
        "selection_basis",
        "effort_nm",
        "source_geometry_id",
    }
    if set(source_identity) != required_identity:
        raise V23Error("state-bank source identity coverage is not exact")
    if (
        source_identity.get("schema") != "a2_piper_v23_capability_source_freeze_v1"
        or source_identity.get("status") != "CAPABILITY_SOURCE_FROZEN"
        or source_identity.get("source_cell") != "A0"
        or source_identity.get("atlas_cell") != "A0"
        or source_identity.get("selection_basis") != "CURRENT_EASY_A0_STABLE_REFERENCE"
        or source_identity.get("effort_nm") != 40.0
    ):
        raise V23Error("state-bank source identity is not the fixed R50 A0 freeze")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise V23Error("state-bank entries must be a sequence")
    if len(entries) != len(STATE_BANK_TARGET_STAGES):
        raise V23Error("state-bank bindings require exactly one entry for stages 2, 3, and 4")
    by_stage = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("schema") != STATE_BANK_ENTRY_SCHEMA:
            raise V23Error("state-bank entry schema is unsupported")
        for field in ("entry_id", "scenario_id", "episode_id", "replay_prefix_id"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise V23Error(f"state-bank entry {field} must be a non-empty identity string")
        stage = entry.get("stage")
        if isinstance(stage, bool) or not isinstance(stage, int) or stage not in STATE_BANK_TARGET_STAGES:
            raise V23Error("state-bank entry stage must be one of 2, 3, and 4")
        if stage in by_stage:
            raise V23Error(f"duplicate state-bank stage entry: {stage}")
        if entry.get("source_identity") != dict(source_identity):
            raise V23Error("state-bank entry source identity disagrees with the reducer source lock")
        if entry.get("atlas_cell") != "A0" or entry.get("source_cell") != "A0":
            raise V23Error("state-bank entry must record atlas_cell=A0 and source_cell=A0")
        if entry.get("forward_mode") != "FULL":
            raise V23Error("state-bank source capture must use forward mode FULL")
        if entry.get("reset_origin") != "evaluator.reset_all_first_episode_observation":
            raise V23Error("state-bank entry reset origin is not the evaluator reset")
        if (
            entry.get("state_clone_supported") is not False
            or entry.get("recurrent_state_restore_supported") is not False
            or entry.get("recurrent_prefix_status") != "CAPTURED_NOT_REEXECUTED"
            or entry.get("capture_selection") != "FIRST_TARGET_STEP_LOWEST_ENV_ID"
        ):
            raise V23Error("state-bank entry violates the forward-only capture contract")
        _validate_state_bank_prefix(entry)
        by_stage[stage] = entry
    if tuple(sorted(by_stage)) != STATE_BANK_TARGET_STAGES:
        raise V23Error("state-bank entries do not cover stages 2, 3, and 4 exactly")

    bindings = []
    for stage in STATE_BANK_TARGET_STAGES:
        entry = by_stage[stage]
        episode = {
            "scenario_id": entry.get("scenario_id"),
            "seed": entry.get("seed"),
            "replay_prefix_id": entry.get("replay_prefix_id"),
            "replay_prefix": entry.get("replay_prefix"),
        }
        for mode in V23_INTERVENTION_MODES:
            switch_record = apply_forward_switch(episode, mode)
            bindings.append(
                {
                    "schema": STATE_BANK_BINDING_SCHEMA,
                    "entry_id": entry["entry_id"],
                    "stage": stage,
                    "mode": mode,
                    "binding_status": (
                        "RUNTIME_SOURCE_CAPTURED"
                        if mode == "FULL"
                        else "STATIC_BOUND_RUNTIME_PENDING"
                    ),
                    "switch_rule": switch_record["switch_rule"],
                    "required_actor_state_fields": switch_record["required_actor_state_fields"],
                    "replay_prefix_id": entry["replay_prefix_id"],
                    "replay_prefix_length": len(entry["replay_prefix"]),
                    "source_identity": dict(source_identity),
                    "forward_only": True,
                    "state_clone_supported": False,
                    "recurrent_state_restore_supported": False,
                    "recurrent_prefix_status": "CAPTURED_NOT_REEXECUTED",
                    "execution_status": (
                        "SOURCE_ROLLOUT_CAPTURED_NOT_REEXECUTED"
                        if mode == "FULL"
                        else "NOT_EXECUTED_ALTERNATE_MODE"
                    ),
                }
            )
    if len(bindings) != 15:
        raise V23Error(f"state-bank binding cardinality must be exactly 15; got {len(bindings)}")
    return bindings


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
