#!/usr/bin/env python3
"""Run the Pull-v5.2 narrow sequence anchor and deterministic door probe.

The anchor is bank-independent and uses the high-level HOMIE sequence commands
against the explicit open-field fixture.  Each sequence is an independent
16-row producer.  Door probes only use sequences admitted by the anchor and
retain every producer row (16 per bucket-by-sequence cell).  The G2 lattice
keeps all 36 scaled sequence states and validates each state as a 16-row batch.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
CHECKPOINT = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v4_B_wave1_seed1/model_step_000750.pt"
)
OUTPUT_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/pull_v5_2_p1_anchor_probe"
ALLOWED_GPUS = (4, 5, 6, 7)
CLOSER_BUCKETS = ("2.5-5", "5-9", "9-12")
SEQUENCE_IDS = ("S1", "S2", "S3", "S4")
SEQUENCE_PHASES = {
    "S1": ("straight_minus_x",),
    "S2": ("side_step",),
    "S3": ("side_step", "straight_minus_x"),
    "S4": ("straight_minus_x", "side_step"),
}
# The primitive names remain part of the receipt for auditability, while the
# evaluator-facing command IDs are the exact v5.2 sequence IDs.
PRIMITIVES = tuple(sorted({primitive for phases in SEQUENCE_PHASES.values() for primitive in phases}))
ANCHOR_COMMAND_LIBRARY = {sequence: SEQUENCE_PHASES[sequence] for sequence in SEQUENCE_IDS}
LATTICE_SCALES = (0.4, 0.55, 0.7, 0.85, 1.0, 1.15, 1.3, 1.45, 1.6)
LATTICE_COMMANDS = tuple((sequence, scale) for sequence in SEQUENCE_IDS for scale in LATTICE_SCALES)
ANCHOR_WAYPOINT_TOLERANCE_M = 0.05
ANCHOR_YAW_TOLERANCE_RAD = 0.15


def _reset_source(source: str) -> str:
    if source == "canonical":
        return "bank_natural_e5"
    if source == "natural":
        return "natural"
    raise ValueError(f"unknown P1 source: {source!r}")


def build_command(
    *, checkpoint: Path, gpu: int, source: str, output_dir: Path,
    fixture: str, sequence_id: str | None = None, command_name: str | None = None,
    closer_bucket: str | None = None,
    anchor_attempt: int = 1, allow_missing_checkpoint: bool = False,
    allow_g8_pure_a: bool = False,
) -> tuple[list[str], dict[str, str]]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"P1 only permits physical GPU4-7; got GPU{gpu}")
    if source not in {"canonical", "natural"}:
        raise ValueError(f"unknown P1 source: {source!r}")
    if fixture not in {"anchor", "door"}:
        raise ValueError(f"unknown P1 fixture: {fixture!r}")
    if sequence_id is None:
        sequence_id = command_name
    if sequence_id not in ANCHOR_COMMAND_LIBRARY:
        raise ValueError(f"unknown v5.2 sequence ID: {sequence_id!r}")
    if closer_bucket is not None and closer_bucket not in CLOSER_BUCKETS:
        raise ValueError(f"unknown closer bucket: {closer_bucket!r}")
    if anchor_attempt not in (1, 2, 3):
        raise ValueError("P1 anchor retries are capped at three corrected attempts")
    if fixture == "door" and source != "canonical":
        raise ValueError("P1 door probe requires canonical bank source")
    if fixture == "anchor" and source != "natural":
        raise ValueError("P1 open-field anchor requires natural Stage-0 source")
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    if not output_dir.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"P1 output must remain inside repository: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite P1 output: {output_dir}")
    reset_source = _reset_source(source)
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        "num_envs=16", "seed=0", "headless=true", "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0", "algo.config.load_optimizer=false",
        "algo.config.eval.num_eval_episodes=1", "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=16", "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "algo.config.eval.a2_diagnostic_reward_terms=[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge,a2_corridor_clean_passage,a2_pull_frame_approach]",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=false",
        "env.config.a2_pull_v5_stage4_bank_injection_ratio=0.0",
        f"env.config.a2_pull_v5_reset_source={reset_source}",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        f"env.config.a2_pull_v5_state_bank_allow_g8_pure_a={'true' if allow_g8_pure_a else 'false'}",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_2_p1_{output_dir.name}.json",
        "+env.config.a2_pull_v5_probe_enabled=true",
        f"+env.config.a2_pull_v5_probe_fixture={fixture}",
        f"+env.config.a2_pull_v5_probe_command={sequence_id}",
        f"+env.config.a2_pull_v5_probe_sequence={sequence_id}",
        f"+env.config.a2_pull_v5_probe_correction_retry={anchor_attempt - 1}",
        "+env.config.a2_pull_v5_probe_open_field=true" if fixture == "anchor" else "+env.config.a2_pull_v5_probe_open_field=false",
        f"+env.config.a2_pull_v5_probe_waypoint_tolerance_m={ANCHOR_WAYPOINT_TOLERANCE_M}",
        f"+env.config.a2_pull_v5_probe_yaw_tolerance_rad={ANCHOR_YAW_TOLERANCE_RAD}",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}",
        "+device=cuda:0",
    ]
    # The start override is a door-only assisted start.  The open-field anchor
    # must remain a pure command-library measurement.
    command.extend((
        "env.config.a2_pull_v5_start_override_enabled=false",
        "env.config.a2_pull_v5_start_override_steps=50",
    ))
    if fixture == "door":
        command.extend((
            f"+env.config.a2_pull_v5_eval_closer_bucket={closer_bucket}",
            "+env.config.a2_pull_v5_eval_state_count=16",
            "+env.config.a2_pull_v5_eval_sequence_count=4",
            "+env.config.a2_pull_v5_eval_selection=deterministic_provenance_balanced",
            "+env.config.a2_pull_v5_eval_selection_seed=0",
            "+algo.config.eval.a2_pull_p2_intervention_enabled=true",
            "+algo.config.eval.a2_pull_p2_intervention_duration_s=1.0",
            "+algo.config.eval.a2_pull_p2_intervention_hinge_threshold_rad=1.6",
            f"+algo.config.eval.a2_pull_p2_intervention_trace_path={output_dir / 'traces' / f'{sequence_id}_p2_intervention_trace.json'}",
        ))
    else:
        command.append("+algo.config.eval.a2_pull_p2_intervention_enabled=false")
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }


def _terminal_rows(output_dir: Path) -> list[dict[str, object]]:
    metrics_path = output_dir / "eval" / "metrics_eval.json"
    if not metrics_path.is_file():
        raise RuntimeError(f"P1 runtime output is missing terminal metrics: {metrics_path}")
    document = json.loads(metrics_path.read_text(encoding="utf-8"))
    rows = document.get("episode_terminal_diagnostics") if isinstance(document, dict) else None
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("P1 metrics_eval.json requires explicit episode_terminal_diagnostics")
    return rows


def _bucket(force: float) -> str:
    if 2.5 <= force < 5.0:
        return "2.5-5"
    if 5.0 <= force < 9.0:
        return "5-9"
    if 9.0 <= force <= 12.0:
        return "9-12"
    raise ValueError(f"closer force outside planned buckets: {force}")


def _nested_value(row: dict[str, object], *paths: tuple[str, ...]) -> object:
    """Read an explicit producer field from the documented nested row schema."""

    for path in paths:
        value: object = row
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if value is not None:
            return value
    return None


def _required_bool(value: object, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"P1 producer field {label} must be bool; got {value!r}")
    return value


def _required_float(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"P1 producer field {label} must be finite numeric; got {value!r}")
    return float(value)


def _anchor_measurement(probe: dict[str, object]) -> dict[str, object]:
    waypoint_arrived = _nested_value(
        probe,
        ("waypoint_arrived",),
        ("waypoint_reached",),
        ("probe_waypoint_arrived",),
        ("anchor_waypoint_arrived",),
        ("anchor", "waypoint_arrived"),
        ("anchor", "waypoint_reached"),
        ("measurement", "waypoint_arrived"),
    )
    yaw_arrived = _nested_value(
        probe,
        ("yaw_arrived",),
        ("yaw_reached",),
        ("probe_yaw_arrived",),
        ("anchor_yaw_arrived",),
        ("anchor", "yaw_arrived"),
        ("anchor", "yaw_reached"),
        ("measurement", "yaw_arrived"),
    )
    waypoint_error = _nested_value(
        probe,
        ("waypoint_position_error_m",),
        ("waypoint_error_m",),
        ("probe_waypoint_error_m",),
        ("anchor", "waypoint_position_error_m"),
        ("anchor", "waypoint_error_m"),
        ("measurement", "waypoint_position_error_m"),
    )
    yaw_error = _nested_value(
        probe,
        ("yaw_error_rad",),
        ("probe_yaw_error_rad",),
        ("anchor", "yaw_error_rad"),
        ("measurement", "yaw_error_rad"),
    )
    if waypoint_arrived is None:
        waypoint_error_f = _required_float(waypoint_error, label="waypoint_position_error_m")
        waypoint_arrived = waypoint_error_f <= ANCHOR_WAYPOINT_TOLERANCE_M
    else:
        waypoint_arrived = _required_bool(waypoint_arrived, label="waypoint_arrived")
        waypoint_error_f = None if waypoint_error is None else _required_float(
            waypoint_error, label="waypoint_position_error_m"
        )
    if yaw_arrived is None:
        yaw_error_f = _required_float(yaw_error, label="yaw_error_rad")
        yaw_arrived = yaw_error_f <= ANCHOR_YAW_TOLERANCE_RAD
    else:
        yaw_arrived = _required_bool(yaw_arrived, label="yaw_arrived")
        yaw_error_f = None if yaw_error is None else _required_float(yaw_error, label="yaw_error_rad")
    return {
        "waypoint_arrived": waypoint_arrived,
        "yaw_arrived": yaw_arrived,
        "waypoint_position_error_m": waypoint_error_f,
        "yaw_error_rad": yaw_error_f,
    }


def _hinge_force(row: dict[str, object]) -> float:
    value = _nested_value(
        row,
        ("hinge_drive_max_force_nm",),
        ("pull_v5", "hinge_drive_max_force_nm"),
        ("pull_v5", "hinge", "drive_max_force_nm"),
        ("door_scenario", "hinge_max_force_nm"),
        ("pull_v0_episode", "hinge_drive_max_force_nm"),
    )
    return _required_float(value, label="hinge_drive_max_force_nm")


def _required_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"P1 producer field {label} must be a non-negative int; got {value!r}")
    return value


def _door_metrics(row: dict[str, object], probe: dict[str, object]) -> dict[str, object]:
    """Extract the v5.2 door-side telemetry without converting missing data to zero."""

    traversal = row.get("pull_v3_traversal")
    if not isinstance(traversal, dict):
        raise ValueError("P1 door row requires pull_v3_traversal telemetry")
    frame_passage = _required_bool(traversal.get("frame_passage"), label="frame_passage")
    panel = row.get("pull_v0_episode")
    if not isinstance(panel, dict):
        raise ValueError("P1 door row requires pull_v0_episode telemetry")
    panel_steps = _required_int(panel.get("body_panel_contact_steps_per_20s"), label="body_panel_contact_steps_per_20s")
    pull_v5 = row.get("pull_v5")
    if not isinstance(pull_v5, dict):
        raise ValueError("P1 door row requires pull_v5 telemetry")
    passage_hinge = pull_v5.get("passage_attempt_hinge_rad")
    if frame_passage:
        passage_hinge = _required_float(passage_hinge, label="passage_attempt_hinge_rad")
    elif passage_hinge is not None:
        raise ValueError("P1 non-passage row must have null passage_attempt_hinge_rad")
    top_hinge = _required_float(row.get("door_hinge_joint_pos"), label="door_hinge_joint_pos")
    recontact = _required_int(
        traversal.get("post_release_recontact_count"), label="post_release_recontact_count"
    )
    midpoint = _required_float(
        traversal.get("frame_midpoint_distance_min_m"), label="frame_midpoint_distance_min_m"
    )
    waypoint_error = _required_float(
        probe.get("waypoint_position_error_m"), label="waypoint_position_error_m"
    )
    yaw_error = _required_float(probe.get("yaw_error_rad"), label="yaw_error_rad")
    return {
        "frame_passage": frame_passage,
        "panel_contact_steps_per_20s": panel_steps,
        "post_release_recontact_count": recontact,
        "frame_midpoint_distance_min_m": midpoint,
        "passage_attempt_hinge_rad": passage_hinge,
        "door_hinge_joint_pos": top_hinge,
        "command_error": {
            "waypoint_position_error_m": waypoint_error,
            "yaw_error_rad": yaw_error,
        },
    }


def _read_p2_trace(path: Path) -> dict[int, dict[str, int | bool | str]]:
    if not path.is_file():
        raise ValueError(f"P1 door row requires evaluator-owned P2 trace: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"P2 evaluator trace must be a mapping: {path}")
    if document.get("schema") != "a2_piper_pull_p2_intervention_trace_v1":
        raise ValueError(f"P2 evaluator trace has unexpected schema: {path}")
    if document.get("enabled") is not True:
        raise ValueError(f"P1 door probe requires enabled P2 evaluator trace: {path}")
    duration_s = _required_float(document.get("duration_s"), label="p2_trace.duration_s")
    if duration_s != 1.0:
        raise ValueError(f"P2 evaluator trace duration must be 1.0s; got {duration_s!r}: {path}")
    hinge_threshold = _required_float(
        document.get("hinge_threshold_rad"), label="p2_trace.hinge_threshold_rad"
    )
    if hinge_threshold != 1.6:
        raise ValueError(
            f"P2 evaluator trace hinge threshold must be 1.6rad; got {hinge_threshold!r}: {path}"
        )
    duration_steps = _required_int(document.get("duration_steps"), label="p2_trace.duration_steps")
    if duration_steps <= 0:
        raise ValueError(f"P2 evaluator trace duration_steps must be positive: {path}")
    trace_rows = document.get("rows")
    if not isinstance(trace_rows, list) or not trace_rows:
        raise ValueError(f"P2 evaluator trace requires non-empty rows: {path}")
    by_env: dict[int, list[dict[str, object]]] = {}
    for trace_row in trace_rows:
        if not isinstance(trace_row, dict):
            raise ValueError(f"P2 evaluator trace rows must be mappings: {path}")
        env_id = _required_int(trace_row.get("env_id"), label="p2_trace.env_id")
        for field in ("trigger_mask", "fired_mask", "active_mask", "base_slice_equal"):
            _required_bool(trace_row.get(field), label=f"p2_trace.{field}")
        by_env.setdefault(env_id, []).append(trace_row)
    metrics: dict[int, dict[str, int | bool | str]] = {}
    for env_id, env_rows in by_env.items():
        triggered = any(item["trigger_mask"] is True for item in env_rows)
        fired = any(item["fired_mask"] is True for item in env_rows)
        active_rows = [item for item in env_rows if item["active_mask"] is True]
        if not triggered or not fired or not active_rows:
            raise ValueError(
                f"P2 evaluator trace env {env_id} did not trigger and activate release+tuck: {path}"
            )
        if any(item["base_slice_equal"] is not True for item in active_rows):
            raise ValueError(
                f"P2 evaluator trace env {env_id} violated base-slice equality while active: {path}"
            )
        metrics[env_id] = {
            "trace_path": str(path),
            "triggered": True,
            "fired": True,
            "active": True,
            "base_slice_equal": True,
            "active_steps": len(active_rows),
        }
    return metrics


def _write_receipt(
    path: Path, *, source: str, fixture: str, attempt: int, rows: list[dict[str, object]],
    closer_bucket: str | None = None, lattice: bool = False,
    lattice_state_count: int | None = None, sequences: tuple[str, ...] | None = None,
    trace_paths: list[Path] | None = None,
) -> dict[str, object]:
    if sequences is None:
        sequences = SEQUENCE_IDS
    if not sequences or any(sequence not in SEQUENCE_IDS for sequence in sequences):
        raise ValueError(f"P1 receipt sequences must be drawn from {SEQUENCE_IDS!r}; got {sequences!r}")
    probes = [row.get("pull_v5_probe") for row in rows if isinstance(row.get("pull_v5_probe"), dict)]
    if len(probes) != len(rows) or not probes:
        raise ValueError("P1 terminal rows require one pull_v5_probe mapping per row")
    if fixture == "door" and trace_paths is not None and len(trace_paths) != len(rows):
        raise ValueError(
            f"P1 door trace path count must match terminal rows: {len(trace_paths)} != {len(rows)}"
        )
    trace_path_by_row = (
        {id(row): trace_paths[index] for index, row in enumerate(rows)}
        if trace_paths is not None
        else {}
    )
    trace_cache: dict[Path, dict[int, dict[str, int | bool | str]]] = {}
    sequence_rows: dict[str, list[dict[str, object]]] = {sequence: [] for sequence in sequences}
    reset_sources: set[str] = set()
    for row, probe in zip(rows, probes):
        sequence = probe.get("sequence")
        if sequence not in sequence_rows:
            raise ValueError(f"P1 terminal row has unexpected sequence {sequence!r}")
        sequence_rows[str(sequence)].append(row)
        pull_v5 = row.get("pull_v5")
        reset_source = pull_v5.get("reset_source") if isinstance(pull_v5, dict) else row.get("reset_source")
        if reset_source not in {"natural", "bank_natural_e5", "bank_natural_e5_plus", "bank_natural_e5_override"}:
            raise ValueError(f"P1 terminal row reset_source is invalid: {reset_source!r}")
        reset_sources.add(str(reset_source))
        if fixture == "anchor" and isinstance(pull_v5, dict) and pull_v5.get("start_override_active") is True:
            raise ValueError("v5.2 open-field anchor must not activate the start override")
    if any(len(group) != 16 for group in sequence_rows.values()) and (fixture == "anchor" or not lattice):
        raise ValueError(
            f"v5.2 P1 requires exactly 16 rows per sequence; got "
            f"{ {sequence: len(group) for sequence, group in sequence_rows.items()} }"
        )
    measurements_by_sequence: dict[str, list[dict[str, object]]] = {}
    sequence_results: dict[str, dict[str, object]] = {}
    for sequence, group in sequence_rows.items():
        group_probes = [row["pull_v5_probe"] for row in group]
        measurements = [_anchor_measurement(item) for item in group_probes] if fixture == "anchor" else []
        measurements_by_sequence[sequence] = measurements
        sequence_results[sequence] = {
            "terminal_records": len(group),
            "waypoint_arrived": sum(item["waypoint_arrived"] for item in measurements),
            "yaw_arrived": sum(item["yaw_arrived"] for item in measurements),
            "command_solvable": sum(item.get("command_solvable") is True for item in group_probes),
            "sequence_pass": bool(
                fixture == "anchor"
                and len(group) == 16
                and all(item.get("anchor_pass") is True for item in group_probes)
                and all(item["waypoint_arrived"] and item["yaw_arrived"] for item in measurements)
                and all(item.get("command_solvable") is True for item in group_probes)
            ) if fixture == "anchor" else None,
        }
    anchored_sequences = [sequence for sequence in sequences if sequence_results[sequence]["sequence_pass"] is True]
    implementation_defects = [sequence for sequence in ("S1", "S2") if sequence in sequence_results and not sequence_results[sequence]["sequence_pass"]]
    bucket_sequence_records: dict[str, dict[str, dict[str, object]]] = {
        bucket: {
            sequence: {
                "episodes": 0,
                "passage": 0,
                "panel_contact_steps_per_20s": 0,
                "panel_contact_rows": 0,
                "post_release_recontact_count": 0,
                "frame_midpoint_distance_min_m": None,
                "passage_attempt_hinge_rad": [],
                "door_hinge_joint_pos": [],
                "command_error": [],
                "evaluator_override_triggered_rows": 0,
                "evaluator_override_active_rows": 0,
                "evaluator_override_base_slice_equal_rows": 0,
                "evaluator_override_active_steps": 0,
            }
            for sequence in sequences
        }
        for bucket in CLOSER_BUCKETS
    }
    evaluator_override_rows = 0
    evaluator_override_active_rows = 0
    evaluator_override_base_equal_rows = 0
    evaluator_override_active_steps = 0
    for sequence, group in sequence_rows.items():
        for row in group:
            probe = row["pull_v5_probe"]
            if fixture != "door":
                continue
            force = _hinge_force(row)
            bucket = _bucket(force)
            if closer_bucket is not None and bucket != closer_bucket:
                raise ValueError(f"P1 row force bucket {bucket} disagrees with requested {closer_bucket}")
            metrics = _door_metrics(row, probe)
            env_id = _required_int(row.get("env_id"), label="env_id")
            trace_path = trace_path_by_row.get(id(row))
            if trace_path is None:
                trace_path = path.parent / sequence / "traces" / f"{sequence}_p2_intervention_trace.json"
            if trace_path not in trace_cache:
                trace_cache[trace_path] = _read_p2_trace(trace_path)
            evaluator_metrics = trace_cache[trace_path].get(env_id)
            if evaluator_metrics is None:
                raise ValueError(
                    f"P1 door row env {env_id} is missing from evaluator P2 trace: {trace_path}"
                )
            summary = bucket_sequence_records[bucket][sequence]
            summary["episodes"] += 1
            summary["passage"] += int(metrics["frame_passage"])
            summary["panel_contact_steps_per_20s"] += metrics["panel_contact_steps_per_20s"]
            summary["panel_contact_rows"] += int(metrics["panel_contact_steps_per_20s"] > 0)
            summary["post_release_recontact_count"] += metrics["post_release_recontact_count"]
            current_midpoint = summary["frame_midpoint_distance_min_m"]
            summary["frame_midpoint_distance_min_m"] = metrics["frame_midpoint_distance_min_m"] if current_midpoint is None else min(current_midpoint, metrics["frame_midpoint_distance_min_m"])
            if metrics["passage_attempt_hinge_rad"] is not None:
                summary["passage_attempt_hinge_rad"].append(metrics["passage_attempt_hinge_rad"])
            summary["door_hinge_joint_pos"].append(metrics["door_hinge_joint_pos"])
            summary["command_error"].append(metrics["command_error"])
            summary["evaluator_override_triggered_rows"] += int(evaluator_metrics["triggered"])
            summary["evaluator_override_active_rows"] += int(evaluator_metrics["active"])
            summary["evaluator_override_base_slice_equal_rows"] += int(
                evaluator_metrics["base_slice_equal"]
            )
            summary["evaluator_override_active_steps"] += int(evaluator_metrics["active_steps"])
            evaluator_override_rows += 1
            evaluator_override_active_rows += int(evaluator_metrics["active"])
            evaluator_override_base_equal_rows += int(evaluator_metrics["base_slice_equal"])
            evaluator_override_active_steps += int(evaluator_metrics["active_steps"])
    if fixture == "door" and not lattice:
        for bucket in CLOSER_BUCKETS:
            for sequence in sequences:
                records = bucket_sequence_records[bucket][sequence]["episodes"]
                expected = 16 if closer_bucket is None or bucket == closer_bucket else 0
                if records != expected:
                    raise ValueError(f"P1 door requires 16 actual rows for {bucket}×{sequence}; got {records}")
    if lattice:
        if lattice_state_count != len(LATTICE_COMMANDS):
            raise ValueError(
                f"G2 lattice validator requires {len(LATTICE_COMMANDS)} scaled states; got {lattice_state_count}"
            )
        if len(rows) != lattice_state_count * 16:
            raise ValueError(
                f"G2 lattice requires 16 terminal rows per scaled state; got {len(rows)} for {lattice_state_count} states"
            )
        for state_index in range(lattice_state_count):
            state_rows = rows[state_index * 16 : (state_index + 1) * 16]
            state_probes = [row.get("pull_v5_probe") for row in state_rows]
            if any(not isinstance(item, dict) for item in state_probes):
                raise ValueError(f"G2 lattice state {state_index} is missing probe telemetry")
            state_commands = {str(item.get("command")) for item in state_probes}
            expected_command, expected_scale = LATTICE_COMMANDS[state_index]
            if state_commands != {expected_command}:
                raise ValueError(
                    f"G2 lattice state {state_index} command mismatch: expected {expected_command}, got {state_commands}"
                )
            state_scales = {
                _required_float(item.get("lattice_scale"), label="lattice_scale")
                for item in state_probes
            }
            if state_scales != {expected_scale}:
                raise ValueError(
                    f"G2 lattice state {state_index} scale mismatch: expected {expected_scale}, got {state_scales}"
                )
    anchor_pass = None
    if fixture == "anchor":
        anchor_pass = not implementation_defects and bool(anchored_sequences)
    frame_passage_count = sum(
        int(summary["passage"])
        for bucket_summary in bucket_sequence_records.values()
        for summary in bucket_summary.values()
    )
    if fixture == "door":
        for bucket_summary in bucket_sequence_records.values():
            for summary in bucket_summary.values():
                hinges = summary["passage_attempt_hinge_rad"]
                summary["passage_attempt_hinge_rad"] = {
                    "count": len(hinges),
                    "values": hinges,
                }
                summary["door_hinge_joint_pos"] = {
                    "count": len(summary["door_hinge_joint_pos"]),
                    "values": summary["door_hinge_joint_pos"],
                }
    receipt = {
        "schema": "a2_piper_pull_v5_2_p1_receipt_v1",
        "status": "PASS" if (anchor_pass is not False) else "FAIL",
        "source": source,
        "reset_source_group": "canonical" if any(item.startswith("bank_") for item in reset_sources) else "natural",
        "fixture": fixture,
        "anchor_attempt": attempt,
        "correction_retry": attempt - 1,
        "lattice": lattice,
        "terminal_records": len(rows),
        "probe_records": len(probes),
        "anchor_pass": anchor_pass,
        "interface_feasible": all(item.get("command_solvable") is True for item in probes),
        "frame_passage_count": frame_passage_count,
        "closer_bucket": closer_bucket,
        "closer_buckets": list(CLOSER_BUCKETS),
        "bucket_sequence_records": bucket_sequence_records,
        "sequence_ids": list(sequences),
        "sequence_phases": {sequence: list(SEQUENCE_PHASES[sequence]) for sequence in sequences},
        "sequence_counts": {sequence: len(group) for sequence, group in sequence_rows.items()},
        "sequence_results": sequence_results,
        "anchored_sequences": anchored_sequences,
        "implementation_defects": implementation_defects,
        "reset_sources": sorted(reset_sources),
        "command_library": list(SEQUENCE_IDS),
        "evaluator_override": {
            "enabled_for_fixture": fixture == "door",
            "trace_schema": "a2_piper_pull_p2_intervention_trace_v1" if fixture == "door" else None,
            "triggered_rows": evaluator_override_rows,
            "active_rows": evaluator_override_active_rows,
            "base_slice_equal_rows": evaluator_override_base_equal_rows,
            "active_steps": evaluator_override_active_steps,
        },
    }
    if fixture == "anchor":
        receipt["anchor_measurements"] = measurements_by_sequence
    if lattice_state_count is not None:
        receipt["lattice_state_count"] = lattice_state_count
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--source", choices=("canonical", "natural"), default="natural")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--anchor-attempt", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--mode", choices=("anchor", "probe", "lattice"), default="probe")
    parser.add_argument("--command", choices=SEQUENCE_IDS, default="S1")
    parser.add_argument("--sequences", nargs="+", choices=SEQUENCE_IDS, default=None)
    parser.add_argument("--anchor-receipt", type=Path)
    parser.add_argument("--closer-bucket", choices=CLOSER_BUCKETS)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--allow-g8-pure-a", action="store_true")
    args = parser.parse_args()
    fixture = "anchor" if args.mode == "anchor" else "door"
    if fixture == "door" and args.closer_bucket is None and args.mode != "lattice":
        parser.error("--closer-bucket is required for a door probe")
    bucket_suffix = "" if args.closer_bucket is None else f"_{args.closer_bucket.replace('-', '_')}"
    output_dir = (args.output_dir or OUTPUT_ROOT / f"pull_v5_2_{args.mode}_{args.source}{bucket_suffix}_attempt{args.anchor_attempt}").resolve()
    sequence_ids = tuple(args.sequences or SEQUENCE_IDS)
    if args.mode == "probe" and args.anchor_receipt is not None:
        anchor_document = json.loads(args.anchor_receipt.resolve().read_text(encoding="utf-8"))
        anchored = anchor_document.get("anchored_sequences")
        if not isinstance(anchored, list) or not all(sequence in SEQUENCE_IDS for sequence in anchored):
            raise ValueError("v5.2 door probe anchor receipt requires anchored_sequences=[S1..S4 subset]")
        sequence_ids = tuple(sequence for sequence in sequence_ids if sequence in anchored)
        if not sequence_ids:
            raise RuntimeError("v5.2 door probe has no anchored sequence available")
    if args.mode == "lattice":
        if args.source != "canonical":
            parser.error("G2 lattice requires canonical source")
        command, process_env = build_command(
            checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
            output_dir=output_dir, fixture="door", sequence_id=args.command,
            closer_bucket="2.5-5", anchor_attempt=args.anchor_attempt,
            allow_missing_checkpoint=args.dry_run,
            allow_g8_pure_a=args.allow_g8_pure_a,
        )
        command = [*command, f"+env.config.a2_pull_v5_lattice_state_count={len(LATTICE_COMMANDS)}"]
        print("[pull-v5.2 P1 lattice] commands:", len(LATTICE_COMMANDS), "states")
        print("[pull-v5.2 P1 lattice] representative command:", " ".join(command))
        print("[pull-v5.2 P1 lattice] environment:", process_env)
        if not args.run:
            return 0
        output_dir.mkdir(parents=True, exist_ok=False)
        all_rows: list[dict[str, object]] = []
        all_trace_paths: list[Path] = []
        for index, (name, scale) in enumerate(LATTICE_COMMANDS):
            state_dir = output_dir / f"state_{index:02d}_{name}_{scale:g}"
            state_command, state_env = build_command(
                checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
                output_dir=state_dir, fixture="door", sequence_id=name,
                closer_bucket="2.5-5", anchor_attempt=args.anchor_attempt,
                allow_g8_pure_a=args.allow_g8_pure_a,
            )
            state_command.append(f"+env.config.a2_pull_v5_lattice_scale={scale}")
            state_dir.mkdir(parents=False, exist_ok=False)
            run_env = os.environ.copy(); run_env.update(state_env)
            with (state_dir / "runner.log").open("x", encoding="utf-8") as stream:
                result = subprocess.run(state_command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
            if result.returncode != 0:
                return result.returncode
            state_rows = _terminal_rows(state_dir)
            if len(state_rows) != 16:
                raise ValueError(f"G2 lattice state {index} must produce exactly 16 rows")
            all_rows.extend(state_rows)
            all_trace_paths.extend(
                [state_dir / "traces" / f"{name}_p2_intervention_trace.json"] * len(state_rows)
            )
        receipt_path = (args.receipt or output_dir / f"P1_lattice_{args.source}_attempt{args.anchor_attempt}_RECEIPT.json").resolve()
        print(json.dumps(_write_receipt(receipt_path, source=args.source, fixture="door", attempt=args.anchor_attempt, rows=all_rows, lattice=True, lattice_state_count=len(LATTICE_COMMANDS), sequences=SEQUENCE_IDS, trace_paths=all_trace_paths), indent=2, sort_keys=True))
        return 0
    if args.mode in {"anchor", "probe"}:
        commands = []
        for sequence in sequence_ids:
            primitive_dir = output_dir / sequence
            command, process_env = build_command(
                checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
                output_dir=primitive_dir, fixture=fixture, sequence_id=sequence,
                closer_bucket=args.closer_bucket, anchor_attempt=args.anchor_attempt,
                allow_missing_checkpoint=args.dry_run,
                allow_g8_pure_a=args.allow_g8_pure_a,
            )
            commands.append((sequence, primitive_dir, command, process_env))
            print(f"[pull-v5.2 P1 {sequence}] command:", " ".join(command))
            print(f"[pull-v5.2 P1 {sequence}] environment:", process_env)
        if not args.run:
            return 0
        output_dir.mkdir(parents=True, exist_ok=False)
        rows = []
        trace_paths: list[Path] = []
        for sequence, primitive_dir, command, process_env in commands:
            primitive_dir.mkdir(parents=False, exist_ok=False)
            run_env = os.environ.copy(); run_env.update(process_env)
            with (primitive_dir / "runner.log").open("x", encoding="utf-8") as stream:
                result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
            if result.returncode != 0:
                return result.returncode
            primitive_rows = _terminal_rows(primitive_dir)
            if len(primitive_rows) != 16:
                raise ValueError(f"P1 sequence {sequence} must produce exactly 16 rows")
            primitive_rows.sort(key=lambda row: row.get("env_id", 0))
            rows.extend(primitive_rows)
            if fixture == "door":
                trace_paths.extend(
                    [primitive_dir / "traces" / f"{sequence}_p2_intervention_trace.json"] * len(primitive_rows)
                )
    else:
        command, process_env = build_command(
            checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
            output_dir=output_dir, fixture=fixture, sequence_id=args.command,
            closer_bucket=args.closer_bucket, anchor_attempt=args.anchor_attempt,
            allow_missing_checkpoint=args.dry_run,
            allow_g8_pure_a=args.allow_g8_pure_a,
        )
        print("[pull-v5.2 P1] command:", " ".join(command))
        print("[pull-v5.2 P1] environment:", process_env)
        if not args.run:
            return 0
        output_dir.mkdir(parents=True, exist_ok=False)
        run_env = os.environ.copy(); run_env.update(process_env)
        with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if result.returncode != 0:
            return result.returncode
        rows = _terminal_rows(output_dir)
    receipt_path = (args.receipt or output_dir / f"P1_v5_2_{args.mode}_{args.source}_attempt{args.anchor_attempt}_RECEIPT.json").resolve()
    receipt = _write_receipt(receipt_path, source=args.source, fixture=fixture, attempt=args.anchor_attempt, rows=rows, closer_bucket=args.closer_bucket, sequences=sequence_ids, trace_paths=trace_paths if fixture == "door" else None)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.mode == "anchor" and receipt["anchor_pass"] is not True:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
