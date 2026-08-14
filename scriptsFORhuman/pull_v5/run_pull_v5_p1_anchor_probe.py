#!/usr/bin/env python3
"""Run the Pull-v5.1 open-field anchor and deterministic door probe.

The anchor is bank-independent and uses the existing high-level HOMIE command
primitives against the explicit open-field fixture.  Door probes execute each
registered primitive separately, then retain exactly four measured rows per
primitive for each 16-row closer bucket.  The G2 lattice keeps all 36 scaled
states and validates each state as a 16-row producer batch.
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
OUTPUT_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/pull_v5_1_p1_anchor_probe"
ALLOWED_GPUS = (4, 5, 6, 7)
CLOSER_BUCKETS = ("2.5-5", "5-9", "9-12")
PRIMITIVES = ("straight_minus_x", "turn_then_forward", "side_step", "arc")
ANCHOR_COMMAND_LIBRARY = {
    "straight_minus_x": ([-0.30, 0.0, 0.0, 0.0, 0.0], "policy_owned_arm", "policy_owned_gripper"),
    "turn_then_forward": ([0.0, 0.0, -0.55, 0.0, 0.0], "policy_owned_arm", "policy_owned_gripper"),
    "side_step": ([-0.18, 0.24, 0.0, 0.0, 0.0], "policy_owned_arm", "policy_owned_gripper"),
    "arc": ([-0.22, 0.0, 0.35, 0.0, 0.0], "policy_owned_arm", "policy_owned_gripper"),
}
LATTICE_SCALES = (0.4, 0.55, 0.7, 0.85, 1.0, 1.15, 1.3, 1.45, 1.6)
LATTICE_COMMANDS = tuple((name, scale) for name in PRIMITIVES for scale in LATTICE_SCALES)
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
    fixture: str, command_name: str, closer_bucket: str | None = None,
    anchor_attempt: int = 1, allow_missing_checkpoint: bool = False,
    allow_g8_pure_a: bool = False,
) -> tuple[list[str], dict[str, str]]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"P1 only permits physical GPU4-7; got GPU{gpu}")
    if source not in {"canonical", "natural"}:
        raise ValueError(f"unknown P1 source: {source!r}")
    if fixture not in {"anchor", "door"}:
        raise ValueError(f"unknown P1 fixture: {fixture!r}")
    if command_name not in ANCHOR_COMMAND_LIBRARY:
        raise ValueError(f"unknown P1 command: {command_name!r}")
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
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_1_p1_{output_dir.name}.json",
        "+env.config.a2_pull_v5_probe_enabled=true",
        f"+env.config.a2_pull_v5_probe_fixture={fixture}",
        f"+env.config.a2_pull_v5_probe_command={command_name}",
        f"+env.config.a2_pull_v5_probe_correction_retry={anchor_attempt - 1}",
        "+env.config.a2_pull_v5_probe_open_field=true" if fixture == "anchor" else "+env.config.a2_pull_v5_probe_open_field=false",
        f"+env.config.a2_pull_v5_probe_waypoint_tolerance_m={ANCHOR_WAYPOINT_TOLERANCE_M}",
        f"+env.config.a2_pull_v5_probe_yaw_tolerance_rad={ANCHOR_YAW_TOLERANCE_RAD}",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}",
        "+device=cuda:0",
    ]
    if fixture == "door":
        command.extend((
            f"+env.config.a2_pull_v5_eval_closer_bucket={closer_bucket}",
            "+env.config.a2_pull_v5_eval_state_count=16",
            "+env.config.a2_pull_v5_eval_primitive_count=4",
            "+env.config.a2_pull_v5_eval_selection=deterministic_provenance_balanced",
            "+env.config.a2_pull_v5_eval_selection_seed=0",
        ))
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


def _write_receipt(
    path: Path, *, source: str, fixture: str, attempt: int, rows: list[dict[str, object]],
    closer_bucket: str | None = None, lattice: bool = False,
    lattice_state_count: int | None = None,
) -> dict[str, object]:
    probes = [row.get("pull_v5_probe") for row in rows if isinstance(row.get("pull_v5_probe"), dict)]
    if not probes:
        raise ValueError("P1 terminal rows contain no pull_v5_probe diagnostics")
    measurements = [_anchor_measurement(item) for item in probes] if fixture == "anchor" else []
    anchor_pass = (
        all(item.get("anchor_pass") is True for item in probes)
        and all(item["waypoint_arrived"] and item["yaw_arrived"] for item in measurements)
        and all(item.get("command_solvable") is True for item in probes)
        if fixture == "anchor"
        else None
    )
    frame_passage = sum(bool((row.get("pull_v3_traversal") or {}).get("frame_passage")) for row in rows)
    bucket_summary = {bucket: {"episodes": 0, "frame_passage": 0} for bucket in CLOSER_BUCKETS}
    primitive_counts = {primitive: 0 for primitive in PRIMITIVES}
    reset_sources: set[str] = set()
    for row in rows:
        pull_v5 = row.get("pull_v5")
        reset_source = pull_v5.get("reset_source") if isinstance(pull_v5, dict) else row.get("reset_source")
        if reset_source not in {"natural", "bank_natural_e5", "bank_natural_e5_plus", "bank_constructed"}:
            raise ValueError(f"P1 terminal row reset_source is invalid: {reset_source!r}")
        reset_sources.add(str(reset_source))
        if fixture == "door":
            force = _hinge_force(row)
            bucket = _bucket(force)
            if closer_bucket is not None and bucket != closer_bucket:
                raise ValueError(f"P1 row force bucket {bucket} disagrees with requested {closer_bucket}")
            bucket_summary[bucket]["episodes"] += 1
            bucket_summary[bucket]["frame_passage"] += int(bool((row.get("pull_v3_traversal") or {}).get("frame_passage")))
        command = row.get("pull_v5_probe")
        if isinstance(command, dict) and command.get("command") in primitive_counts:
            primitive_counts[str(command["command"])] += 1
    if fixture == "door" and not lattice:
        if len(rows) != 16 or any(count != 4 for count in primitive_counts.values()):
            raise ValueError(f"P1 door probe requires exactly 16 rows and four per primitive; got {len(rows)}, {primitive_counts}")
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
    if fixture == "anchor":
        counts = tuple(primitive_counts.values())
        if not counts or min(counts) <= 0 or len(set(counts)) != 1:
            anchor_pass = False
    receipt = {
        "schema": "a2_piper_pull_v5_1_p1_receipt_v3",
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
        "frame_passage_count": frame_passage,
        "closer_bucket": closer_bucket,
        "closer_buckets": list(CLOSER_BUCKETS),
        "closer_bucket_records": bucket_summary,
        "primitive_counts": primitive_counts,
        "reset_sources": sorted(reset_sources),
        "command_library": list(PRIMITIVES),
    }
    if fixture == "anchor":
        receipt["anchor_measurements"] = measurements
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
    parser.add_argument("--command", choices=tuple(ANCHOR_COMMAND_LIBRARY), default="straight_minus_x")
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
    output_dir = (args.output_dir or OUTPUT_ROOT / f"pull_v5_1_{args.mode}_{args.source}{bucket_suffix}_attempt{args.anchor_attempt}").resolve()
    if args.mode == "lattice":
        if args.source != "canonical":
            parser.error("G2 lattice requires canonical source")
        command, process_env = build_command(
            checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
            output_dir=output_dir, fixture="door", command_name="straight_minus_x",
            closer_bucket="2.5-5", anchor_attempt=args.anchor_attempt,
            allow_missing_checkpoint=args.dry_run,
            allow_g8_pure_a=args.allow_g8_pure_a,
        )
        command = [*command, f"+env.config.a2_pull_v5_lattice_state_count={len(LATTICE_COMMANDS)}"]
        print("[pull-v5.1 P1 lattice] commands:", len(LATTICE_COMMANDS), "states")
        print("[pull-v5.1 P1 lattice] representative command:", " ".join(command))
        print("[pull-v5.1 P1 lattice] environment:", process_env)
        if not args.run:
            return 0
        output_dir.mkdir(parents=True, exist_ok=False)
        all_rows: list[dict[str, object]] = []
        for index, (name, scale) in enumerate(LATTICE_COMMANDS):
            state_dir = output_dir / f"state_{index:02d}_{name}_{scale:g}"
            state_command, state_env = build_command(
                checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
                output_dir=state_dir, fixture="door", command_name=name,
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
            all_rows.extend(_terminal_rows(state_dir))
        receipt_path = (args.receipt or output_dir / f"P1_lattice_{args.source}_attempt{args.anchor_attempt}_RECEIPT.json").resolve()
        print(json.dumps(_write_receipt(receipt_path, source=args.source, fixture="door", attempt=args.anchor_attempt, rows=all_rows, lattice=True, lattice_state_count=len(LATTICE_COMMANDS)), indent=2, sort_keys=True))
        return 0
    if args.mode in {"anchor", "probe"}:
        commands = []
        for primitive in PRIMITIVES:
            primitive_dir = output_dir / primitive
            command, process_env = build_command(
                checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
                output_dir=primitive_dir, fixture=fixture, command_name=primitive,
                closer_bucket=args.closer_bucket, anchor_attempt=args.anchor_attempt,
                allow_missing_checkpoint=args.dry_run,
                allow_g8_pure_a=args.allow_g8_pure_a,
            )
            commands.append((primitive, primitive_dir, command, process_env))
            print(f"[pull-v5.1 P1 {primitive}] command:", " ".join(command))
            print(f"[pull-v5.1 P1 {primitive}] environment:", process_env)
        if not args.run:
            return 0
        output_dir.mkdir(parents=True, exist_ok=False)
        rows = []
        for primitive, primitive_dir, command, process_env in commands:
            primitive_dir.mkdir(parents=False, exist_ok=False)
            run_env = os.environ.copy(); run_env.update(process_env)
            with (primitive_dir / "runner.log").open("x", encoding="utf-8") as stream:
                result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
            if result.returncode != 0:
                return result.returncode
            primitive_rows = _terminal_rows(primitive_dir)
            if len(primitive_rows) != 16:
                raise ValueError(f"P1 primitive {primitive} must produce exactly 16 rows before four-row selection")
            primitive_rows.sort(key=lambda row: row.get("env_id", 0))
            rows.extend(primitive_rows if args.mode == "anchor" else primitive_rows[:4])
    else:
        command, process_env = build_command(
            checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
            output_dir=output_dir, fixture=fixture, command_name=args.command,
            closer_bucket=args.closer_bucket, anchor_attempt=args.anchor_attempt,
            allow_missing_checkpoint=args.dry_run,
            allow_g8_pure_a=args.allow_g8_pure_a,
        )
        print("[pull-v5.1 P1] command:", " ".join(command))
        print("[pull-v5.1 P1] environment:", process_env)
        if not args.run:
            return 0
        output_dir.mkdir(parents=True, exist_ok=False)
        run_env = os.environ.copy(); run_env.update(process_env)
        with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if result.returncode != 0:
            return result.returncode
        rows = _terminal_rows(output_dir)
    receipt_path = (args.receipt or output_dir / f"P1_{args.mode}_{args.source}_attempt{args.anchor_attempt}_RECEIPT.json").resolve()
    receipt = _write_receipt(receipt_path, source=args.source, fixture=fixture, attempt=args.anchor_attempt, rows=rows, closer_bucket=args.closer_bucket)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.mode == "anchor" and receipt["anchor_pass"] is not True:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
