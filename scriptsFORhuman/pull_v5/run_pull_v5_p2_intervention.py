#!/usr/bin/env python3
"""Run and adjudicate the paired frozen-actor release+tuck intervention."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2_PULL_V5_RELEASE_HINGE_THRESHOLD_RAD,
    A2_PULL_V5_RELEASE_TUCK_DURATION_S,
    a2_pull_v5_release_tuck_override,
)


PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
CHECKPOINT = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v4_B_wave1_seed1/model_step_000750.pt"
)
OUTPUT_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/p2_intervention_v5_1"
ALLOWED_GPUS = (4, 5, 6, 7)
V4_PLAN_ID = "a2_piper_pull_v4_annuity_removal_and_frame_approach"
P2_RECEIPT_SCHEMA = "a2_piper_pull_v5_1_p2_receipt_v1"
P2_TRACE_SCHEMA = "a2_piper_pull_p2_intervention_trace_v1"
PERSISTENT_RELEASE_STREAK_STEPS = 25
ALPHA = 0.05
POOL_NUM_ENVS = 16
POOL_EPISODES_PER_ENV = 2
POOL_SIZE = POOL_NUM_ENVS * POOL_EPISODES_PER_ENV
SELECTED_PAIR_COUNT = 16
POOL_ENV_IDS = tuple(range(POOL_NUM_ENVS))
POOL_EPISODE_INDICES = tuple(range(POOL_EPISODES_PER_ENV))


def audit_override_contract() -> None:
    """Check the stateless action contract without constructing an environment."""

    policy = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    hinge = torch.tensor([1.6, 1.2])
    aperture = torch.tensor([True, True])
    elapsed = torch.tensor([0, 0], dtype=torch.long)
    arm_target = torch.tensor(
        [[0.4, -0.2, 0.1, 0.0, -0.1, 0.2], [-0.3, 0.1, 0.2, 0.0, 0.2, -0.2]],
        dtype=torch.float32,
    )
    applied, active = a2_pull_v5_release_tuck_override(
        policy,
        hinge,
        aperture,
        elapsed,
        dt=0.02,
        enabled=True,
        arm_action=arm_target,
    )
    if not torch.equal(applied[:, :5], policy[:, :5]):
        raise RuntimeError("P2 override changed the base command slice")
    if not torch.equal(applied[0, 5:11], arm_target[0]) or applied[0, 11].item() != 1.0:
        raise RuntimeError("P2 override did not set the default-pose arm and gripper-open slices")
    if not torch.equal(applied[1], policy[1]) or bool(active[1]):
        raise RuntimeError("P2 override activated outside the hinge threshold")


def _trace_path(output_dir: Path) -> Path:
    return output_dir / "eval" / "p2_intervention_trace.json"


def _assert_v4_command(command: list[str]) -> None:
    if "+ablation=wbmanip/pull_v4_B_frame_approach" not in command:
        raise AssertionError("P2 command must use the frozen v4-B ablation config")
    if f"env.config.a2_v20_R1_plan_id={V4_PLAN_ID}" not in command:
        raise AssertionError("P2 command must bind the v4 plan id")
    env_config_tokens = [token for token in command if token.startswith("env.config.")]
    forbidden = ("v5", "bank", "injection", "intervention", "guard", "probe")
    leaked = [
        token
        for token in env_config_tokens
        if any(item in token.split("=", 1)[0].lower() for item in forbidden)
    ]
    if leaked:
        raise AssertionError(f"P2 command contains forbidden v5/environment override keys: {leaked}")


def build_command(
    *,
    checkpoint: Path,
    gpu: int,
    intervention: bool,
    output_dir: Path,
    allow_missing_checkpoint: bool = False,
) -> tuple[list[str], dict[str, str]]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"P2 only permits physical GPU4-7; got GPU{gpu}")
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    if not output_dir.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"P2 output must remain inside repository: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite P2 output: {output_dir}")
    trace_path = _trace_path(output_dir).resolve()
    command = [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        "num_envs=16",
        "seed=0",
        "headless=true",
        "use_wandb=false",
        "+ablation=wbmanip/pull_v4_B_frame_approach",
        f"algo.config.eval.num_eval_episodes={POOL_SIZE}",
        "+algo.config.eval.eval_num_envs_episodes=false",
        "+algo.config.eval.dump_to_log_metrics=true",
        "algo.config.eval.save_videos=false",
        f"algo.config.eval.num_save_episodes={POOL_SIZE}",
        "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "algo.config.eval.a2_diagnostic_reward_terms=[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge,a2_corridor_clean_passage,a2_pull_frame_approach]",
        f"env.config.a2_v20_R1_plan_id={V4_PLAN_ID}",
        f"+algo.config.eval.a2_pull_p2_intervention_enabled={'true' if intervention else 'false'}",
        f"+algo.config.eval.a2_pull_p2_intervention_duration_s={A2_PULL_V5_RELEASE_TUCK_DURATION_S}",
        f"+algo.config.eval.a2_pull_p2_intervention_hinge_threshold_rad={A2_PULL_V5_RELEASE_HINGE_THRESHOLD_RAD}",
        f"+algo.config.eval.a2_pull_p2_intervention_trace_path={trace_path}",
        f"eval_output_dir={output_dir / 'eval'}",
        f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}",
        "+device=cuda:0",
    ]
    _assert_v4_command(command)
    return command, {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "WANDB_MODE": "offline",
    }


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite numeric; got {value!r}")
    return float(value)


def _load_terminal_rows(output_dir: Path) -> list[dict]:
    path = output_dir / "eval" / "metrics_eval.json"
    if not path.is_file():
        raise RuntimeError(f"P2 output is missing terminal metrics: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("episode_terminal_diagnostics") if isinstance(document, dict) else None
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("P2 metrics_eval.json requires explicit episode_terminal_diagnostics")
    episode_counts: dict[int, int] = {}
    enriched_rows = []
    for row in rows:
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0:
            raise ValueError(f"P2 terminal diagnostics require non-negative integer env_id; got {env_id!r}")
        episode_index = episode_counts.get(env_id, 0)
        episode_counts[env_id] = episode_index + 1
        enriched = dict(row)
        enriched["_p2_episode_index"] = episode_index
        enriched_rows.append(enriched)
    return enriched_rows


def _load_trace(output_dir: Path) -> tuple[dict, list[dict]]:
    path = _trace_path(output_dir)
    if not path.is_file():
        raise RuntimeError(f"P2 output is missing evaluator-owned trace: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != P2_TRACE_SCHEMA:
        raise ValueError(f"P2 trace schema is invalid: {path}")
    if payload.get("duration_s") != A2_PULL_V5_RELEASE_TUCK_DURATION_S:
        raise ValueError("P2 trace duration does not equal one second")
    if payload.get("hinge_threshold_rad") != A2_PULL_V5_RELEASE_HINGE_THRESHOLD_RAD:
        raise ValueError("P2 trace hinge threshold does not equal 1.6 rad")
    if not isinstance(payload.get("enabled"), bool):
        raise ValueError("P2 trace enabled must be bool")
    if payload.get("plan_id") != V4_PLAN_ID:
        raise ValueError("P2 trace must bind the frozen v4 plan id")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("P2 trace requires a non-empty rows list")
    return payload, rows


def _episode_trace_rows(
    rows: list[dict],
    expected_keys: set[tuple[int, int]],
) -> dict[tuple[int, int], list[dict]]:
    grouped: dict[tuple[int, int], list[dict]] = {
        group_key: [] for group_key in expected_keys
    }
    for row in rows:
        env_id = row.get("env_id")
        episode_index = row.get("episode_index")
        if (
            isinstance(env_id, bool)
            or not isinstance(env_id, int)
            or isinstance(episode_index, bool)
            or not isinstance(episode_index, int)
        ):
            raise ValueError("P2 trace env_id and episode_index must be integers")
        group_key = (episode_index, env_id)
        if group_key not in grouped:
            # Overshoot can leave trace rows for an episode that did not reach a
            # terminal diagnostic before the evaluator stopped.  They are
            # screening-pool evidence only, not paired candidates.
            continue
        required = {
            "fixture_id",
            "episode_id",
            "step_index",
            "trigger_mask",
            "fired_mask",
            "active_mask",
            "elapsed_steps",
            "policy",
            "applied",
            "base_slice_equal",
            "hinge_position_rad",
            "aperture_ready",
            "handle_contact",
            "no_handle_contact",
            "contacting",
        }
        missing = sorted(required.difference(row))
        if missing:
            raise ValueError(f"P2 trace row is missing fields: {missing}")
        if not isinstance(row["fixture_id"], str) or not row["fixture_id"]:
            raise ValueError("P2 trace fixture_id must be a non-empty string")
        if not isinstance(row["episode_id"], str) or not row["episode_id"]:
            raise ValueError("P2 trace episode_id must be a non-empty string")
        for field_name in (
            "trigger_mask",
            "fired_mask",
            "active_mask",
            "aperture_ready",
            "handle_contact",
            "no_handle_contact",
            "base_slice_equal",
        ):
            if not isinstance(row[field_name], bool):
                raise ValueError(f"P2 trace {field_name} must be bool")
        if row["no_handle_contact"] == row["handle_contact"]:
            raise ValueError("P2 trace handle/no-handle contact predicates disagree")
        step = row["step_index"]
        elapsed = row["elapsed_steps"]
        if isinstance(step, bool) or not isinstance(step, int) or step < 0:
            raise ValueError("P2 trace step_index must be a non-negative integer")
        if isinstance(elapsed, bool) or not isinstance(elapsed, int) or elapsed < 0:
            raise ValueError("P2 trace elapsed_steps must be a non-negative integer")
        _finite(row["hinge_position_rad"], name="P2 trace hinge_position_rad")
        policy = row["policy"]
        applied = row["applied"]
        if not isinstance(policy, dict) or not isinstance(applied, dict):
            raise ValueError("P2 trace policy/applied slices must be mappings")
        if tuple(policy) != ("base", "arm", "gripper") or tuple(applied) != ("base", "arm", "gripper"):
            raise ValueError("P2 trace policy/applied slices must contain base, arm, gripper")
        if len(policy["base"]) != 5 or len(applied["base"]) != 5 or len(policy["arm"]) != 6 or len(applied["arm"]) != 6:
            raise ValueError("P2 trace action slice dimensions are invalid")
        grouped[group_key].append(row)
    for group_key, episode_rows in grouped.items():
        if not episode_rows:
            continue
        episode_rows.sort(key=lambda row: row["step_index"])
        steps = [row["step_index"] for row in episode_rows]
        if steps != list(range(steps[-1] + 1)):
            raise ValueError(
                f"P2 trace episode{group_key[0]} env{group_key[1]} steps are not contiguous from zero"
            )
    return grouped


def _scenario(row: dict) -> object:
    value = row.get("door_scenario")
    if not isinstance(value, dict):
        raise ValueError("P2 terminal row is missing door_scenario")
    return value


def _event_e6(row: dict) -> bool:
    episode = row.get("pull_v0_episode")
    if not isinstance(episode, dict):
        raise ValueError("P2 terminal row is missing pull_v0_episode")
    reached = episode.get("event_reached")
    if not isinstance(reached, dict) or "E6_PATH_REVERSAL_ENTRY" not in reached:
        raise ValueError("P2 terminal row is missing E6 event evidence")
    if not isinstance(reached["E6_PATH_REVERSAL_ENTRY"], bool):
        raise ValueError("P2 E6 event evidence must be bool")
    return reached["E6_PATH_REVERSAL_ENTRY"]


def _frame_passage(row: dict) -> bool:
    traversal = row.get("pull_v3_traversal")
    if not isinstance(traversal, dict) or not isinstance(traversal.get("frame_passage"), bool):
        raise ValueError("P2 terminal row is missing boolean pull_v3_traversal.frame_passage")
    return traversal["frame_passage"]


def _summarize_candidate(
    terminal: dict,
    episode_rows: list[dict],
    *,
    episode_index: int,
    env_id: int,
    intervention: bool,
    duration_steps: int,
) -> dict[str, object]:
    rejected_reasons: list[str] = []
    trigger_indices = [index for index, row in enumerate(episode_rows) if row["trigger_mask"]]
    trigger_index = trigger_indices[0] if trigger_indices else None
    if trigger_index is None:
        rejected_reasons.append("missing_trigger")
    else:
        if intervention and not any(row["fired_mask"] for row in episode_rows[trigger_index:]):
            rejected_reasons.append("intervention_not_fired")
        if not intervention and any(row["fired_mask"] for row in episode_rows):
            rejected_reasons.append("control_unexpected_fired")
    if not all(row["base_slice_equal"] for row in episode_rows):
        rejected_reasons.append("base_slice_changed")

    scenario = None
    try:
        scenario = _scenario(terminal)
    except (ValueError, TypeError):
        rejected_reasons.append("missing_door_scenario")

    e6_path_reversal_entry = None
    try:
        e6_path_reversal_entry = _event_e6(terminal)
    except (ValueError, TypeError):
        rejected_reasons.append("missing_e6_evidence")

    frame_passage = None
    try:
        frame_passage = _frame_passage(terminal)
    except (ValueError, TypeError):
        rejected_reasons.append("missing_frame_passage")

    frame_distance = None
    try:
        frame_distance = _finite(
            (terminal.get("pull_v3_traversal") or {}).get("frame_midpoint_distance_min_m"),
            name="frame_midpoint_distance_min_m",
        )
    except (ValueError, TypeError):
        rejected_reasons.append("missing_frame_distance")

    no_handle_streak = 0
    max_no_handle_streak = 0
    no_handle_contact_steps = 0
    post_trigger_steps = 0
    hinge_trigger = None
    hinge_plus_one = None
    hinge_plus_two = None
    if trigger_index is not None:
        for row in episode_rows[trigger_index:]:
            post_trigger_steps += 1
            if row["no_handle_contact"]:
                no_handle_contact_steps += 1
                no_handle_streak += 1
                max_no_handle_streak = max(max_no_handle_streak, no_handle_streak)
            else:
                no_handle_streak = 0
        plus_one_index = trigger_index + duration_steps
        plus_two_index = trigger_index + 2 * duration_steps
        if plus_two_index >= len(episode_rows):
            rejected_reasons.append("missing_plus_2s_evidence")
        else:
            try:
                hinge_trigger = _finite(
                    episode_rows[trigger_index]["hinge_position_rad"], name="hinge_trigger"
                )
                hinge_plus_one = _finite(
                    episode_rows[plus_one_index]["hinge_position_rad"], name="hinge_plus_one"
                )
                hinge_plus_two = _finite(
                    episode_rows[plus_two_index]["hinge_position_rad"], name="hinge_plus_two"
                )
            except (ValueError, TypeError):
                rejected_reasons.append("nonfinite_hinge_evidence")

    episode_id = episode_rows[0]["episode_id"]
    persistent_release = (
        max_no_handle_streak >= PERSISTENT_RELEASE_STREAK_STEPS
        if trigger_index is not None
        else None
    )
    return {
        "fixture_id": f"episode{episode_index}:env{env_id}",
        "episode_index": episode_index,
        "env_id": env_id,
        "episode_id": episode_id,
        "door_scenario": scenario,
        "admissible": not rejected_reasons,
        "rejected_reasons": rejected_reasons,
        "trigger_step": (
            episode_rows[trigger_index]["step_index"] if trigger_index is not None else None
        ),
        "trigger_count": len(trigger_indices),
        "trigger_fired": any(row["fired_mask"] for row in episode_rows),
        "persistent_release": persistent_release,
        "max_no_handle_contact_streak": max_no_handle_streak,
        "no_handle_contact_rate_post_trigger": (
            no_handle_contact_steps / post_trigger_steps if post_trigger_steps else None
        ),
        "hinge_at_trigger_rad": hinge_trigger,
        "hinge_plus_1s_rad": hinge_plus_one,
        "hinge_plus_2s_rad": hinge_plus_two,
        "hinge_retained_plus_1s": (
            hinge_plus_one >= A2_PULL_V5_RELEASE_HINGE_THRESHOLD_RAD
            if hinge_plus_one is not None
            else None
        ),
        "hinge_retained_plus_2s": (
            hinge_plus_two >= A2_PULL_V5_RELEASE_HINGE_THRESHOLD_RAD
            if hinge_plus_two is not None
            else None
        ),
        "frame_midpoint_distance_min_m": frame_distance,
        "e6_path_reversal_entry": e6_path_reversal_entry,
        "frame_passage": frame_passage,
        "base_slice_equal_all_steps": not any(
            not row["base_slice_equal"] for row in episode_rows
        ),
    }


def _screening_rejection(
    terminal: dict,
    *,
    episode_index: int,
    env_id: int,
    reason: str,
) -> dict[str, object]:
    """Represent an overshoot-pool row that cannot enter paired adjudication."""

    return {
        "fixture_id": f"episode{episode_index}:env{env_id}",
        "episode_index": episode_index,
        "env_id": env_id,
        "episode_id": terminal.get("episode_id"),
        "door_scenario": terminal.get("door_scenario"),
        "admissible": False,
        "rejected_reasons": [reason],
        "trigger_step": None,
        "trigger_count": 0,
        "trigger_fired": False,
        "persistent_release": None,
        "max_no_handle_contact_streak": 0,
        "no_handle_contact_rate_post_trigger": None,
        "hinge_at_trigger_rad": None,
        "hinge_plus_1s_rad": None,
        "hinge_plus_2s_rad": None,
        "hinge_retained_plus_1s": None,
        "hinge_retained_plus_2s": None,
        "frame_midpoint_distance_min_m": None,
        "e6_path_reversal_entry": None,
        "frame_passage": None,
        "base_slice_equal_all_steps": False,
    }


def _summarize(output_dir: Path, *, intervention: bool) -> dict[str, object]:
    terminal_rows = _load_terminal_rows(output_dir)
    trace_payload, trace_rows = _load_trace(output_dir)
    if trace_payload.get("fixture_id") not in {"control", "intervention"}:
        raise ValueError("P2 trace fixture_id must be control or intervention")
    if trace_payload["fixture_id"] != ("intervention" if intervention else "control"):
        raise ValueError("P2 trace fixture_id does not match its paired run")
    if trace_payload["enabled"] != intervention:
        raise ValueError("P2 trace enabled does not match its paired run")
    if any(row.get("fixture_id") != trace_payload["fixture_id"] for row in trace_rows):
        raise ValueError("P2 trace row fixture_id does not match its payload")

    duration_steps = trace_payload.get("duration_steps")
    if isinstance(duration_steps, bool) or not isinstance(duration_steps, int) or duration_steps <= 0:
        raise ValueError("P2 trace duration_steps must be a positive integer")
    terminal_by_key: dict[tuple[int, int], dict] = {}
    episode_counts = {env_id: 0 for env_id in POOL_ENV_IDS}
    duplicate_terminal_keys: list[tuple[int, int]] = []
    for terminal in terminal_rows:
        env_id = terminal["env_id"]
        if env_id not in episode_counts:
            raise ValueError(f"P2 screening pool contains unexpected env_id={env_id}")
        episode_index = terminal["_p2_episode_index"]
        key = (episode_index, env_id)
        if key in terminal_by_key:
            duplicate_terminal_keys.append(key)
            continue
        terminal_by_key[key] = terminal
        episode_counts[env_id] += 1

    expected_keys = set(terminal_by_key)
    trace_keys = {
        (row["episode_index"], row["env_id"])
        for row in trace_rows
        if isinstance(row.get("episode_index"), int)
        and not isinstance(row.get("episode_index"), bool)
        and isinstance(row.get("env_id"), int)
        and not isinstance(row.get("env_id"), bool)
    }
    trace_by_key = _episode_trace_rows(trace_rows, expected_keys)
    pool_rows = []
    for episode_index, env_id in sorted(expected_keys):
        terminal = terminal_by_key[(episode_index, env_id)]
        episode_rows = trace_by_key[(episode_index, env_id)]
        if not episode_rows:
            pool_rows.append(
                _screening_rejection(
                    terminal,
                    episode_index=episode_index,
                    env_id=env_id,
                    reason="missing_trace",
                )
            )
            continue
        pool_rows.append(
            _summarize_candidate(
                terminal,
                episode_rows,
                episode_index=episode_index,
                env_id=env_id,
                intervention=intervention,
                duration_steps=duration_steps,
            )
        )
    admissible_rows = [row for row in pool_rows if row["admissible"]]
    rejection_reason_counts: dict[str, int] = {}
    for row in pool_rows:
        for reason in row["rejected_reasons"]:
            rejection_reason_counts[reason] = rejection_reason_counts.get(reason, 0) + 1
    underfilled_env_ids = [
        env_id
        for env_id, count in sorted(episode_counts.items())
        if count < POOL_EPISODES_PER_ENV
    ]
    return {
        "status": "INVALID_G9" if duplicate_terminal_keys else "VALID",
        "reason": (
            "duplicate terminal screening keys"
            if duplicate_terminal_keys
            else None
        ),
        "fixture": trace_payload["fixture_id"],
        "episodes": len(pool_rows),
        "pool_size": len(pool_rows),
        "expected_pool_size": POOL_SIZE,
        "raw_terminal_count": len(terminal_rows),
        "overshoot_count": max(0, len(terminal_rows) - POOL_SIZE),
        "terminal_env_counts": {str(env_id): count for env_id, count in sorted(episode_counts.items())},
        "underfilled_env_ids": underfilled_env_ids,
        "duplicate_terminal_keys": [
            {"episode_index": key[0], "env_id": key[1]}
            for key in duplicate_terminal_keys
        ],
        "trace_key_count": len(trace_keys),
        "trace_unmatched_key_count": len(trace_keys - expected_keys),
        "trace_unmatched_keys": [
            {"episode_index": key[0], "env_id": key[1]}
            for key in sorted(trace_keys - expected_keys)
        ],
        "rejection_reason_counts": rejection_reason_counts,
        "admissible_count": len(admissible_rows),
        "persistent_release_count": sum(
            bool(row["persistent_release"]) for row in admissible_rows
        ),
        "persistent_release_rate": (
            sum(bool(row["persistent_release"]) for row in admissible_rows) / len(admissible_rows)
            if admissible_rows
            else None
        ),
        "persistent_release_required_steps": PERSISTENT_RELEASE_STREAK_STEPS,
        "pool_rows": pool_rows,
        "trace_path": str(_trace_path(output_dir).resolve()),
        "terminal_path": str((output_dir / "eval" / "metrics_eval.json").resolve()),
    }


def _invalid_summary(*, fixture: str, reason: str) -> dict[str, object]:
    return {"status": "INVALID_G9", "fixture": fixture, "reason": reason}


def _index_pool_rows(
    rows: list[dict], *, fixture: str
) -> tuple[dict[tuple[int, int], dict], list[tuple[int, int]]]:
    indexed: dict[tuple[int, int], dict] = {}
    duplicate_keys: list[tuple[int, int]] = []
    for row in rows:
        episode_index = row.get("episode_index")
        env_id = row.get("env_id")
        if (
            isinstance(episode_index, bool)
            or not isinstance(episode_index, int)
            or isinstance(env_id, bool)
            or not isinstance(env_id, int)
        ):
            raise ValueError(f"{fixture} screening row has an invalid episode/env key")
        key = (episode_index, env_id)
        if key in indexed:
            duplicate_keys.append(key)
            continue
        indexed[key] = row
    return indexed, duplicate_keys


def _select_admissible_pairs(
    control: dict[str, object], intervention: dict[str, object]
) -> dict[str, object]:
    raw_terminal_counts = {
        "control": control.get("raw_terminal_count"),
        "intervention": intervention.get("raw_terminal_count"),
    }
    overshoot_counts = {
        "control": control.get("overshoot_count"),
        "intervention": intervention.get("overshoot_count"),
    }
    if control.get("status") != "VALID" or intervention.get("status") != "VALID":
        return {
            "status": "INVALID_G9",
            "reason": "paired fixture pool evidence is invalid",
            "pool_size": 0,
            "screening_pool_size": 0,
            "matched_pool_size": 0,
            "raw_terminal_counts": raw_terminal_counts,
            "overshoot_counts": overshoot_counts,
            "selected_count": 0,
            "selected_fixture_ids": [],
            "selected_fixture_rows": [],
            "rejected_reasons": [],
        }
    control_rows, control_duplicates = _index_pool_rows(
        control["pool_rows"], fixture="control"
    )
    intervention_rows, intervention_duplicates = _index_pool_rows(
        intervention["pool_rows"], fixture="intervention"
    )
    all_keys = sorted(set(control_rows) | set(intervention_rows))
    common_keys = set(control_rows) & set(intervention_rows)
    if control_duplicates or intervention_duplicates:
        return {
            "status": "INVALID_G9",
            "reason": "duplicate screening-pool episode/env keys",
            "pool_size": len(common_keys),
            "screening_pool_size": len(all_keys),
            "matched_pool_size": len(common_keys),
            "raw_terminal_counts": raw_terminal_counts,
            "overshoot_counts": overshoot_counts,
            "selected_count": 0,
            "selected_fixture_ids": [],
            "selected_fixture_rows": [],
            "rejected_reasons": [
                {
                    "fixture": fixture,
                    "episode_index": key[0],
                    "env_id": key[1],
                    "reasons": ["duplicate_screening_key"],
                }
                for fixture, keys in (
                    ("control", control_duplicates),
                    ("intervention", intervention_duplicates),
                )
                for key in keys
            ],
        }
    selected_fixture_rows = []
    rejected_reasons = []
    admissible_pair_count = 0
    for key in all_keys:
        left = control_rows.get(key)
        right = intervention_rows.get(key)
        reasons = []
        if left is None:
            reasons.append("missing_control_fixture")
        elif not left["admissible"]:
            reasons.extend(f"control:{reason}" for reason in left["rejected_reasons"])
        if right is None:
            reasons.append("missing_intervention_fixture")
        elif not right["admissible"]:
            reasons.extend(f"intervention:{reason}" for reason in right["rejected_reasons"])
        if left is not None and right is not None and left["door_scenario"] != right["door_scenario"]:
            reasons.append("door_scenario_mismatch")
        fixture_row = left or right
        if reasons:
            rejected_reasons.append(
                {
                    "fixture_id": fixture_row["fixture_id"],
                    "episode_index": key[0],
                    "env_id": key[1],
                    "reasons": reasons,
                }
            )
            continue
        if left is None or right is None:
            raise RuntimeError("P2 pair screening lost a matched fixture row")
        admissible_pair_count += 1
        if len(selected_fixture_rows) < SELECTED_PAIR_COUNT:
            selected_fixture_rows.append(
                {
                    "fixture_id": left["fixture_id"],
                    "episode_index": left["episode_index"],
                    "env_id": left["env_id"],
                    "door_scenario": left["door_scenario"],
                    "control": left,
                    "intervention": right,
                }
            )
        else:
            rejected_reasons.append(
                {
                    "fixture_id": left["fixture_id"],
                    "episode_index": left["episode_index"],
                    "env_id": left["env_id"],
                    "reasons": ["selection_quota_exhausted"],
                }
            )
    selected_count = len(selected_fixture_rows)
    return {
        "status": "VALID" if selected_count == SELECTED_PAIR_COUNT else "INVALID_G9",
        "reason": (
            None
            if selected_count == SELECTED_PAIR_COUNT
            else f"fewer than {SELECTED_PAIR_COUNT} admissible paired fixtures"
        ),
        "pool_size": len(common_keys),
        "screening_pool_size": len(all_keys),
        "matched_pool_size": len(common_keys),
        "raw_terminal_counts": raw_terminal_counts,
        "overshoot_counts": overshoot_counts,
        "admissible_pair_count": admissible_pair_count,
        "selected_count": selected_count,
        "selected_fixture_ids": [row["fixture_id"] for row in selected_fixture_rows],
        "selected_fixture_rows": selected_fixture_rows,
        "rejected_reasons": rejected_reasons,
    }


def _adjudicate(
    control: dict[str, object],
    intervention: dict[str, object],
    paired_pool: dict[str, object],
) -> dict[str, object]:
    if control.get("status") != "VALID" or intervention.get("status") != "VALID":
        return {"status": "INVALID_G9", "reason": "paired fixture evidence is invalid"}
    if paired_pool.get("status") != "VALID":
        return {
            "status": "INVALID_G9",
            "reason": paired_pool.get("reason") or "paired fixture selection is invalid",
        }
    fixture_results = []
    discordant_control_success = 0
    discordant_intervention_success = 0
    ties = 0
    selected_fixture_rows = paired_pool["selected_fixture_rows"]
    if len(selected_fixture_rows) != SELECTED_PAIR_COUNT:
        return {
            "status": "INVALID_G9",
            "reason": f"expected {SELECTED_PAIR_COUNT} selected fixtures",
        }
    for pair in selected_fixture_rows:
        left = pair["control"]
        right = pair["intervention"]
        if left["fixture_id"] != right["fixture_id"]:
            return {
                "status": "INVALID_G9",
                "reason": f"fixture id mismatch at {pair['fixture_id']}",
            }
        if left["door_scenario"] != right["door_scenario"]:
            return {
                "status": "INVALID_G9",
                "reason": f"door-scenario mismatch at {pair['fixture_id']}",
            }
        control_outcome = bool(left["persistent_release"])
        intervention_outcome = bool(right["persistent_release"])
        if control_outcome and not intervention_outcome:
            discordant_control_success += 1
        elif intervention_outcome and not control_outcome:
            discordant_intervention_success += 1
        else:
            ties += 1
        fixture_results.append(
            {
                "fixture_id": pair["fixture_id"],
                "episode_index": pair["episode_index"],
                "env_id": pair["env_id"],
                "door_scenario": left["door_scenario"],
                "control_k25": control_outcome,
                "intervention_k25": intervention_outcome,
                "control_hinge_plus_1s_rad": left["hinge_plus_1s_rad"],
                "intervention_hinge_plus_1s_rad": right["hinge_plus_1s_rad"],
                "control_hinge_plus_2s_rad": left["hinge_plus_2s_rad"],
                "intervention_hinge_plus_2s_rad": right["hinge_plus_2s_rad"],
                "control_frame_distance_m": left["frame_midpoint_distance_min_m"],
                "intervention_frame_distance_m": right["frame_midpoint_distance_min_m"],
                "control_e6": left["e6_path_reversal_entry"],
                "intervention_e6": right["e6_path_reversal_entry"],
                "control_base_slice_equal": left["base_slice_equal_all_steps"],
                "intervention_base_slice_equal": right["base_slice_equal_all_steps"],
            }
        )
    discordant_total = discordant_control_success + discordant_intervention_success
    if discordant_total:
        from scipy import __version__ as scipy_version
        from scipy.stats import binomtest

        result = binomtest(
            discordant_intervention_success,
            discordant_total,
            p=0.5,
            alternative="greater",
        )
        statistic = float(result.statistic)
        p_value = float(result.pvalue)
    else:
        from scipy import __version__ as scipy_version

        statistic = None
        p_value = 1.0
    significant_positive = (
        discordant_total > 0
        and discordant_intervention_success > discordant_control_success
        and p_value < ALPHA
    )
    return {
        "status": "VALID",
        "test": "one_sided_exact_McNemar_binomial",
        "alpha": ALPHA,
        "discordant_control_success": discordant_control_success,
        "discordant_intervention_success": discordant_intervention_success,
        "ties": ties,
        "discordant_total": discordant_total,
        "statistic": statistic,
        "p_value": p_value,
        "scipy_version": scipy_version,
        "significant_positive_change": significant_positive,
        "binding_route": "release_persistence" if significant_positive else "base_route",
        "selected_fixture_ids": paired_pool["selected_fixture_ids"],
        "fixture_results": fixture_results,
    }


def _write_receipt(
    path: Path,
    control: dict[str, object],
    intervention: dict[str, object],
    output_root: Path,
    checkpoint_path: Path,
) -> dict[str, object]:
    paired_pool = _select_admissible_pairs(control, intervention)
    adjudication = _adjudicate(control, intervention, paired_pool)
    status = "PASS" if adjudication.get("status") == "VALID" else "INVALID_G9"
    receipt = {
        "schema": P2_RECEIPT_SCHEMA,
        "status": status,
        "scientific_plan_id": "a2_piper_pull_v5_1_bridge_occupancy_repair",
        "eval_plan_id": V4_PLAN_ID,
        "checkpoint_path": str(checkpoint_path.resolve()),
        "seed": 0,
        "num_envs": 16,
        "pool_episodes_per_env": POOL_EPISODES_PER_ENV,
        "selected_pair_count": SELECTED_PAIR_COUNT,
        "trigger": "aperture_ready_and_hinge_ge_1.60_rad",
        "duration_s": A2_PULL_V5_RELEASE_TUCK_DURATION_S,
        "one_shot_per_episode": True,
        "base_action_slice_preserved": status == "PASS"
        and paired_pool.get("selected_count") == SELECTED_PAIR_COUNT,
        "arm_target": "actual_default_pose_via_cumulative_delta",
        "gripper_command": 1.0,
        "pool_size": paired_pool.get("pool_size"),
        "screening_pool_size": paired_pool.get("screening_pool_size"),
        "matched_pool_size": paired_pool.get("matched_pool_size"),
        "raw_terminal_counts": paired_pool.get("raw_terminal_counts", {}),
        "overshoot_counts": paired_pool.get("overshoot_counts", {}),
        "selected_fixture_ids": paired_pool.get("selected_fixture_ids", []),
        "selected_fixture_rows": paired_pool.get("selected_fixture_rows", []),
        "rejected_reasons": paired_pool.get("rejected_reasons", []),
        "control": control,
        "intervention": intervention,
        "paired_pool": paired_pool,
        "adjudication": adjudication,
        "paired_output_root": str(output_root),
        "paired_binding": {
            "same_checkpoint": True,
            "checkpoint_path": str(checkpoint_path.resolve()),
            "same_seed": 0,
            "same_num_envs": 16,
            "same_door_scenario_rows": paired_pool.get("status") == "VALID",
            "control_output": str(output_root / "control"),
            "intervention_output": str(output_root / "intervention"),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--summarize-existing",
        action="store_true",
        help="screen existing control/intervention outputs without launching IsaacSim",
    )
    args = parser.parse_args()
    audit_override_contract()
    if args.summarize_existing:
        if args.run:
            parser.error("--summarize-existing cannot be combined with --run")
        existing_root = args.output_root.resolve()
        if not existing_root.is_relative_to(ROOT.resolve()):
            raise ValueError(f"P2 output must remain inside repository: {existing_root}")
        if not existing_root.is_dir():
            raise FileNotFoundError(existing_root)
        summaries: dict[str, dict[str, object]] = {}
        for intervention in (False, True):
            label = "intervention" if intervention else "control"
            output_dir = existing_root / label
            if not output_dir.is_dir():
                raise FileNotFoundError(output_dir)
            summaries[label] = _summarize(output_dir, intervention=intervention)
        receipt_path = (
            args.receipt or existing_root / "P2_INTERVENTION_RECEIPT_SCREENED.json"
        ).resolve()
        if not receipt_path.is_relative_to(ROOT.resolve()):
            raise ValueError(f"P2 receipt must remain inside repository: {receipt_path}")
        if receipt_path.exists():
            raise FileExistsError(f"refusing to overwrite P2 receipt: {receipt_path}")
        receipt = _write_receipt(
            receipt_path,
            summaries["control"],
            summaries["intervention"],
            existing_root,
            args.checkpoint.resolve(),
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt["status"] == "PASS" else 2
    summaries: dict[str, dict[str, object]] = {}
    for intervention in (False, True):
        label = "intervention" if intervention else "control"
        output_dir = (args.output_root / label).resolve()
        command, process_env = build_command(
            checkpoint=args.checkpoint.resolve(),
            gpu=args.gpu,
            intervention=intervention,
            output_dir=output_dir,
            allow_missing_checkpoint=args.dry_run,
        )
        print(f"[pull-v5.1 P2 {label}] command:", " ".join(command))
        print(f"[pull-v5.1 P2 {label}] environment:", process_env)
        if not args.run:
            continue
        output_dir.mkdir(parents=True, exist_ok=False)
        run_env = os.environ.copy()
        run_env.update(process_env)
        with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=run_env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if result.returncode != 0:
            summaries[label] = _invalid_summary(
                fixture=label,
                reason=f"evaluator exited with return code {result.returncode}",
            )
            continue
        try:
            summaries[label] = _summarize(output_dir, intervention=intervention)
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            summaries[label] = _invalid_summary(fixture=label, reason=str(exc))
    if not args.run:
        return 0
    receipt_path = (args.receipt or args.output_root / "P2_INTERVENTION_RECEIPT.json").resolve()
    if not receipt_path.is_relative_to(ROOT.resolve()):
        raise ValueError(f"P2 receipt must remain inside repository: {receipt_path}")
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite P2 receipt: {receipt_path}")
    receipt = _write_receipt(
        receipt_path,
        summaries.get("control", _invalid_summary(fixture="control", reason="control did not run")),
        summaries.get("intervention", _invalid_summary(fixture="intervention", reason="intervention did not run")),
        args.output_root.resolve(),
        args.checkpoint.resolve(),
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
