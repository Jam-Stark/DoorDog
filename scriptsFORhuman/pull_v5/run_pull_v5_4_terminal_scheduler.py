#!/usr/bin/env python3
"""Run the v5.4 Stage-B terminal-yaw scheduler rehearsal.

The rehearsal is deliberately an interface-characterization producer.  Its
rows are never scientific denominator rows: terminal timing is copied from the
actual evaluator ``env.step`` returned-dones signal and each target cell must
produce eight terminal rows.  A second attempt is allowed only as revision 1;
there is no open-ended retry loop.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
from pathlib import Path
from typing import Any, Mapping

try:
    from .pull_v5_4_gates import (
        DEFAULT_DECISION,
        DEFAULT_STAGE_A,
        GateRejected,
        PLAN_ID,
        require_chain,
    )
except ImportError:
    from pull_v5_4_gates import DEFAULT_DECISION, DEFAULT_STAGE_A, GateRejected, PLAN_ID, require_chain


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v5"
OUTPUT_ROOT = EVAL_ROOT / "v5_4_stage_b_rehearsal"
DEFAULT_REHEARSAL = OUTPUT_ROOT / "REHEARSAL_RECEIPT.json"
ALLOWED_GPUS = (4, 5, 6, 7)
TARGETS = (-2.5, 1.0)
NUM_ENVS = 8
ATTEMPTS = (0, 1)


def build_rehearsal_command(
    *,
    target_delta: float,
    attempt: int,
    output_dir: Path,
    gpu: int = 4,
    checkpoint: Path,
    correction_delta: float = 0.0,
    allow_missing_checkpoint: bool = False,
) -> tuple[list[str], dict[str, str]]:
    """Build one bounded 8-environment rehearsal invocation."""

    if target_delta not in TARGETS:
        raise ValueError(f"rehearsal target must be exactly {TARGETS}; got {target_delta!r}")
    if attempt not in ATTEMPTS:
        raise ValueError(f"rehearsal attempt must be 0 or 1; got {attempt!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"rehearsal only permits physical GPU4-7; got GPU{gpu}")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    output_dir = output_dir.expanduser().resolve()
    if not output_dir.is_relative_to(EVAL_ROOT.resolve()):
        raise ValueError(f"rehearsal output must remain under {EVAL_ROOT}: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite rehearsal output: {output_dir}")
    if not math.isfinite(correction_delta):
        raise ValueError("rehearsal correction_delta must be finite")
    requested_target = target_delta + correction_delta if attempt == 1 else target_delta
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        f"num_envs={NUM_ENVS}", "seed=0", "headless=true", "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0", "algo.config.load_optimizer=false",
        "env.config.a2_v20_R1_plan_id=a2_piper_pull_v5_bridge_occupancy_and_release_persistence",
        "algo.config.eval.num_eval_episodes=1", "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.save_trajectories=true",
        "algo.config.eval.save_videos=false", f"algo.config.eval.num_save_episodes={NUM_ENVS}",
        "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "algo.config.eval.a2_diagnostic_reward_terms=[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge,a2_corridor_clean_passage,a2_pull_frame_approach]",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=false",
        "env.config.a2_pull_v5_stage4_bank_injection_ratio=0.0",
        "env.config.a2_pull_v5_reset_source=natural",
        "env.config.a2_pull_v5_start_override_enabled=false",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "+env.config.a2_pull_v5_probe_enabled=true",
        "+env.config.a2_pull_v5_probe_fixture=rehearsal",
        "+env.config.a2_pull_v5_probe_command=S1",
        "+env.config.a2_pull_v5_probe_sequence=S1",
        "+env.config.a2_pull_v5_probe_open_field=true",
        "+env.config.a2_pull_v5_scheduler_enabled=true",
        f"+env.config.a2_pull_v5_scheduler_rehearsal_target_yaw_delta={requested_target}",
        f"+env.config.a2_pull_v5_scheduler_rehearsal_original_target_yaw_delta={target_delta}",
        f"+env.config.a2_pull_v5_scheduler_rehearsal_attempt={attempt}",
        "+env.config.a2_pull_v5_probe_waypoint_tolerance_m=0.05",
        "+env.config.a2_pull_v5_probe_yaw_tolerance_rad=0.15",
        "env.config.a2_pull_v5_state_bank_allow_g8_pure_a=false",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_4_rehearsal_{target_delta:g}_attempt{attempt}.json",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}", "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }


def _read_mapping(path: Path, label: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"{label} is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _terminal_rows(output_dir: Path, *, target_delta: float, attempt: int) -> list[dict[str, Any]]:
    metrics = _read_mapping(output_dir / "eval" / "metrics_eval.json", "rehearsal metrics")
    raw_rows = metrics.get("episode_terminal_diagnostics")
    if not isinstance(raw_rows, list) or len(raw_rows) != NUM_ENVS or not all(isinstance(row, Mapping) for row in raw_rows):
        raise ValueError("rehearsal metrics must contain exactly eight episode_terminal_diagnostics rows")
    trace_value = None
    trace_path = output_dir / "eval" / "scheduler_trace.json"
    if not trace_path.is_file():
        raise ValueError(f"rehearsal scheduler trace is required for terminal join: {trace_path}")
    trace_value = _read_mapping(trace_path, "scheduler trace")
    trace_rows = trace_value.get("rows")
    if not isinstance(trace_rows, list):
        raise ValueError("scheduler trace must contain a rows list")
    if trace_value.get("terminal_timing_source") != "env.step returned dones":
        raise ValueError("scheduler trace must attest env.step returned-dones terminal timing")
    by_key: dict[tuple[int, int], Mapping[str, Any]] = {}
    for row in trace_rows:
        if not isinstance(row, Mapping):
            raise ValueError("scheduler trace rows must be mappings")
        env_id = row.get("env_id")
        episode_index = row.get("episode_index")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in range(NUM_ENVS):
            raise ValueError(f"scheduler trace has invalid env_id={env_id!r}")
        if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
            raise ValueError(f"scheduler trace env {env_id} has invalid episode_index={episode_index!r}")
        expected_episode_id = f"rehearsal:env{env_id}:episode{episode_index}"
        if row.get("episode_id") != expected_episode_id:
            raise ValueError(f"scheduler trace env {env_id} has mismatched episode_id")
        if row.get("terminal_after_step") is True:
            if episode_index != 0:
                raise ValueError("scheduler trace terminal timing must be joined within episode_index=0")
            key = (env_id, episode_index)
            if key in by_key:
                raise ValueError(f"scheduler trace has duplicate returned-done row for {key}")
            by_key[key] = row
    if set(by_key) != {(env_id, 0) for env_id in range(NUM_ENVS)}:
        raise ValueError("scheduler trace must contain exactly one returned-done terminal row for each first-episode env")
    result: list[dict[str, Any]] = []
    for raw in raw_rows:
        env_id = raw.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in range(NUM_ENVS):
            raise ValueError(f"rehearsal row has invalid env_id: {env_id!r}")
        episode_index = raw.get("episode_index")
        if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index != 0:
            raise ValueError(f"rehearsal metrics env {env_id} must be first-episode episode_index=0")
        episode_id = raw.get("episode_id")
        if episode_id != f"rehearsal:env{env_id}:episode0":
            raise ValueError(f"rehearsal metrics env {env_id} has mismatched episode_id")
        probe = raw.get("pull_v5_probe") if isinstance(raw.get("pull_v5_probe"), Mapping) else raw
        scheduler = probe.get("scheduler") if isinstance(probe, Mapping) else None
        if not isinstance(scheduler, Mapping):
            raise ValueError(f"rehearsal metrics env {env_id} is missing scheduler terminal mapping")
        trace = by_key[(env_id, 0)]
        for field in (
            "state",
            "terminal_current_state",
            "terminal_hold_steps",
            "failure_reason",
            "episode_index",
            "episode_id",
        ):
            if scheduler.get(field) != trace.get(field):
                raise ValueError(f"rehearsal env {env_id} metrics/trace mismatch for {field}")
        metric_error = scheduler.get("terminal_error_original_target_rad")
        trace_error = trace.get("terminal_error_original_target_rad")
        if (
            isinstance(metric_error, bool) or not isinstance(metric_error, (int, float))
            or not math.isfinite(float(metric_error))
            or isinstance(trace_error, bool) or not isinstance(trace_error, (int, float))
            or not math.isfinite(float(trace_error))
            or not math.isclose(float(metric_error), float(trace_error), rel_tol=0.0, abs_tol=1.0e-9)
        ):
            raise ValueError(f"rehearsal env {env_id} metrics/trace original-target error mismatch")
        terminal = trace.get("terminal_after_step")
        if terminal is not True:
            raise ValueError(f"rehearsal env {env_id} has no returned-dones terminal flag")
        scheduler_state = scheduler.get("state")
        terminal_current_state = scheduler.get("terminal_current_state")
        terminal_hold_steps = scheduler.get("terminal_hold_steps")
        failure_reason = scheduler.get("failure_reason")
        if not isinstance(scheduler_state, str) or not scheduler_state:
            raise ValueError(f"rehearsal env {env_id} scheduler state must be a non-empty string")
        if not isinstance(terminal_current_state, bool):
            raise ValueError(f"rehearsal env {env_id} scheduler current-state flag must be boolean")
        if (
            isinstance(terminal_hold_steps, bool)
            or not isinstance(terminal_hold_steps, int)
            or terminal_hold_steps < 0
        ):
            raise ValueError(f"rehearsal env {env_id} scheduler hold count must be a non-negative integer")
        if failure_reason is not None and not isinstance(failure_reason, str):
            raise ValueError(f"rehearsal env {env_id} scheduler failure reason must be string or null")
        if scheduler_state != "DONE" and not failure_reason:
            raise ValueError(
                f"rehearsal env {env_id} non-DONE scheduler row lacks a failure reason"
            )
        signed_error = float(trace_error)
        result.append({
            "record_class": "interface_characterization",
            "env_id": env_id,
            "episode_index": 0,
            "episode_id": f"rehearsal:env{env_id}:episode0",
            "target_yaw_delta_rad": target_delta,
            "attempt": attempt,
            "terminal_after_step": terminal,
            "terminal_error_original_target_rad": signed_error,
            "abs_terminal_error_original_target_rad": abs(signed_error),
            "scheduler_state": scheduler_state,
            "terminal_current_state": terminal_current_state,
            "terminal_hold_steps": terminal_hold_steps,
            "failure_reason": failure_reason,
            "returned_done_source": "env.step returned dones",
            "scientific_denominator_included": False,
            "denominator_scope": "none",
        })
    result.sort(key=lambda row: row["env_id"])
    if [row["env_id"] for row in result] != list(range(NUM_ENVS)):
        raise ValueError("rehearsal terminal rows must cover env ids 0..7 exactly once")
    return result


def _cell_pass(rows: list[Mapping[str, Any]]) -> bool:
    if len(rows) != NUM_ENVS:
        return False
    errors: list[float] = []
    for row in rows:
        if (
            row.get("scheduler_state") != "DONE"
            or row.get("terminal_current_state") is not True
            or row.get("terminal_hold_steps") != 100
            or row.get("terminal_after_step") is not True
            or row.get("episode_index") != 0
        ):
            return False
        error = row.get("terminal_error_original_target_rad")
        if isinstance(error, bool) or not isinstance(error, (int, float)) or not math.isfinite(float(error)):
            return False
        errors.append(abs(float(error)))
    return max(errors) <= 0.15 and statistics.fmean(errors) <= 0.10


def write_rehearsal_receipt(
    path: Path,
    *,
    cells: list[dict[str, Any]],
    correction: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if len(cells) != 2 or {cell.get("original_target_yaw_delta_rad") for cell in cells} != set(TARGETS):
        raise ValueError("rehearsal receipt requires exactly -2.5 and +1.0 cells")
    receipt: dict[str, Any] = {
        "schema": "a2_piper_pull_v5_4_stage_b_rehearsal_v1",
        "plan_id": PLAN_ID,
        "record_class": "interface_characterization",
        "status": "PASS" if all(cell.get("status") == "PASS" for cell in cells) else "FAIL",
        "num_envs": NUM_ENVS,
        "gpu": 4,
        "scientific_denominator_included": False,
        "denominator_scope": "none",
        "cells": cells,
    }
    if correction is not None:
        receipt["correction_revision"] = dict(correction)
    path = path.expanduser().resolve()
    if not path.is_relative_to(EVAL_ROOT.resolve()):
        raise ValueError(f"rehearsal receipt must remain under {EVAL_ROOT}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def _print_commands(args: argparse.Namespace) -> int:
    require_chain("stage_a", decision_path=args.decision, stage_a_path=args.stage_a)
    output_root = args.output_root.expanduser().resolve()
    receipt_path = args.receipt.expanduser().resolve()
    if not output_root.is_relative_to(EVAL_ROOT.resolve()):
        raise GateRejected(f"rehearsal output must remain under {EVAL_ROOT}: {output_root}")
    if not receipt_path.is_relative_to(EVAL_ROOT.resolve()):
        raise GateRejected(f"rehearsal receipt must remain under {EVAL_ROOT}: {receipt_path}")
    for target in TARGETS:
        for attempt in ATTEMPTS:
            output_dir = output_root / f"target_{target:g}_attempt{attempt}"
            command, environment = build_rehearsal_command(
                target_delta=target, attempt=attempt, output_dir=output_dir,
                gpu=args.gpu, checkpoint=args.checkpoint.resolve(), correction_delta=0.0,
                allow_missing_checkpoint=True,
            )
            print(f"[pull-v5.4 rehearsal target={target:g} attempt={attempt}] command:", " ".join(command))
            print(f"[pull-v5.4 rehearsal target={target:g} attempt={attempt}] environment:", environment)
    print(f"[pull-v5.4 rehearsal] receipt: {receipt_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--stage-a", type=Path, default=DEFAULT_STAGE_A)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_REHEARSAL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    output_root = args.output_root.expanduser().resolve()
    receipt_path = args.receipt.expanduser().resolve()
    if not output_root.is_relative_to(EVAL_ROOT.resolve()):
        raise GateRejected(f"rehearsal output must remain under {EVAL_ROOT}: {output_root}")
    if not receipt_path.is_relative_to(EVAL_ROOT.resolve()):
        raise GateRejected(f"rehearsal receipt must remain under {EVAL_ROOT}: {receipt_path}")
    # Keep command generation and runtime admission separate.  Stage-A is the
    # only prerequisite before launching the first rehearsal subprocess.
    require_chain("stage_a", decision_path=args.decision, stage_a_path=args.stage_a)
    if args.dry_run or not args.run:
        return _print_commands(args)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite rehearsal output: {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)
    cells: list[dict[str, Any]] = []

    def run_attempt(target: float, attempt: int, correction_delta: float) -> list[dict[str, Any]]:
        attempt_dir = output_root / f"target_{target:g}_attempt{attempt}"
        command, environment = build_rehearsal_command(
            target_delta=target, attempt=attempt, output_dir=attempt_dir,
            gpu=args.gpu, checkpoint=args.checkpoint.resolve(), correction_delta=correction_delta,
        )
        attempt_dir.mkdir(parents=False, exist_ok=False)
        run_env = os.environ.copy(); run_env.update(environment)
        with (attempt_dir / "runner.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"rehearsal target {target} attempt {attempt} exited {result.returncode}")
        return _terminal_rows(attempt_dir, target_delta=target, attempt=attempt)

    # Collect both original target cells before deciding whether the single
    # bounded revision is needed.  If revision 1 is needed it is rerun for both
    # cells, yielding exactly the required 16-row shared-median source.
    for target in TARGETS:
        rows = run_attempt(target, 0, 0.0)
        cells.append({
            "original_target_yaw_delta_rad": target,
            "attempts": [{
                "attempt": 0,
                "requested_target_yaw_delta_rad": target,
                "terminal_rows": rows,
                "status": "PASS" if _cell_pass(rows) else "FAIL",
            }],
            "status": "PASS" if _cell_pass(rows) else "FAIL",
        })
    if not all(cell["status"] == "PASS" for cell in cells):
        shared_correction = statistics.median(
            [float(row["terminal_error_original_target_rad"])
             for cell in cells for row in cell["attempts"][0]["terminal_rows"]]
        )
        for cell in cells:
            target = float(cell["original_target_yaw_delta_rad"])
            rows = run_attempt(target, 1, shared_correction)
            cell["attempts"].append({
                "attempt": 1,
                "requested_target_yaw_delta_rad": target + shared_correction,
                "terminal_rows": rows,
                "status": "PASS" if _cell_pass(rows) else "FAIL",
            })
            cell["status"] = "PASS" if _cell_pass(rows) else "FAIL"
    attempt1_rows = [row for cell in cells for attempt in cell["attempts"] if attempt["attempt"] == 1 for row in attempt["terminal_rows"]]
    correction = None
    if attempt1_rows:
        correction = {
            "revision": 1,
            "source_revision": 0,
            "source_attempt": 0,
            "shared_median_signed_original_target_error_rad": shared_correction,
            "shared_median_signed_terminal_error_rad": shared_correction,
            "source_row_count": 16,
            "applied_to_planning_target": True,
        }
    receipt = write_rehearsal_receipt(receipt_path, cells=cells, correction=correction)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateRejected as exc:
        raise SystemExit(f"REJECTED: {exc}")
