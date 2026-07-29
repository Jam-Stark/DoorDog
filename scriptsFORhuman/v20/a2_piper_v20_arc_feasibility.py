"""Run and adjudicate the preregistered base-v20 P1 live-grasp arc probe."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
DEFAULT_CHECKPOINT = REPO_ROOT / (
    "logs_rl/a2_piper_full_stage_a2_base/base_v19/"
    "base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
)
EXPECTED_CHECKPOINT_SHA256 = "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d"
MODES = ("F0", "F1")
ANGLES = (0.9, 1.0, 1.1, 1.2)
SEEDS = (0, 1, 2)
EPISODES_PER_SEED = 16
POOLED_EPISODES = 48
PASS_MINIMUM = 46
ALLOWED_GPUS = tuple(str(index) for index in range(7))
POSITION_P95_MAX_M = 0.03
ORIENTATION_P95_MAX_RAD = 0.20
JACOBIAN_CONDITION_MAX = 1.0e6
F0_TRANSLATION_MAX_M = 0.02
F0_YAW_MAX_RAD = 0.03
F1_TRANSLATION_MAX_M = 0.10
F1_YAW_MAX_RAD = 0.15
BODY_FORCE_MAX_N = 5.0
TERMINAL_WINDOW_STEPS = 10
PROBE_TIMEOUT_STEPS = 1200
PROBE_LEAD_RAD = 0.008
PROBE_MAX_ORIENTATION_STEP_RAD = 0.02
PROBE_JOINT_TARGET_STEP_MAX_RAD = 0.001
PROBE_ROOT_HOLD_TRANSLATION_DAMPING_GAIN = 2.0
PROBE_ROOT_HOLD_YAW_GAIN = 40.0
PROBE_ROOT_HOLD_YAW_DAMPING_GAIN = 2.0
PROBE_F1_ROOT_HOLD_SCALE = 1.00
PROBE_EPISODE_LENGTH_S = 120
SCHEMA = "a2_piper_v20_arc_feasibility_v1"
CSV_FIELDS = (
    "mode", "target_hinge_rad", "seed", "env_id", "outcome", "feasible",
    "failure_reasons", "max_hinge_rad", "position_error_p95_m",
    "orientation_error_p95_rad", "root_translation_max_m", "root_yaw_max_rad",
    "root_crossing", "max_body_force_n", "max_arm_speed_radps", "sample_count",
)


class ArcFeasibilityError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArcFeasibilityError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ArcFeasibilityError(f"{name} must be finite")
    return result


def _p95(values: Sequence[float]) -> float:
    if not values:
        raise ArcFeasibilityError("p95 requires at least one sample")
    ordered = sorted(_finite_number(value, "p95 sample") for value in values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _validate_runtime_config(config: Mapping[str, Any], mode: str, angle: float) -> None:
    expected = {
        "enabled": True,
        "v20_arc_probe_enabled": True,
        "v20_arc_probe_mode": mode,
        "v20_arc_probe_target_hinge_rad": angle,
        "v20_arc_probe_terminal_window_steps": TERMINAL_WINDOW_STEPS,
        "v20_arc_probe_timeout_steps": PROBE_TIMEOUT_STEPS,
        "v20_arc_probe_lead_rad": PROBE_LEAD_RAD,
        "v20_arc_probe_max_orientation_step_rad": PROBE_MAX_ORIENTATION_STEP_RAD,
        "v20_arc_probe_joint_target_step_max_rad": PROBE_JOINT_TARGET_STEP_MAX_RAD,
        "v20_arc_probe_root_hold_translation_damping_gain": PROBE_ROOT_HOLD_TRANSLATION_DAMPING_GAIN,
        "v20_arc_probe_root_hold_yaw_gain": PROBE_ROOT_HOLD_YAW_GAIN,
        "v20_arc_probe_root_hold_yaw_damping_gain": PROBE_ROOT_HOLD_YAW_DAMPING_GAIN,
        "v20_arc_probe_f1_root_hold_scale": PROBE_F1_ROOT_HOLD_SCALE,
        "v20_arc_probe_orientation_tolerance_rad": ORIENTATION_P95_MAX_RAD,
        "v20_arc_probe_relief_translation_max_m": F1_TRANSLATION_MAX_M,
        "v20_arc_probe_relief_yaw_max_rad": F1_YAW_MAX_RAD,
        "jacobian_condition_max": JACOBIAN_CONDITION_MAX,
        "raw_action_abs_max": 10.0,
    }
    mismatched = {key: (config.get(key), value) for key, value in expected.items() if config.get(key) != value}
    if mismatched:
        raise ArcFeasibilityError(f"runtime probe config mismatch: {mismatched}")


def assess_episode(
    *, mode: str, target_hinge_rad: float, seed: int, env_id: int,
    outcome: str, samples: Sequence[Mapping[str, Any]], runtime: Mapping[str, Any],
) -> dict[str, Any]:
    if mode not in MODES or target_hinge_rad not in ANGLES or seed not in SEEDS:
        raise ArcFeasibilityError("episode identity is outside the preregistered grid")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < EPISODES_PER_SEED:
        raise ArcFeasibilityError("env_id must be in 0..15")
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)) or not samples:
        raise ArcFeasibilityError("every activated P1 episode requires non-empty per-step samples")
    required = {
        "hinge_position_rad", "bilateral_contact", "tcp_handle_position_error_m",
        "tcp_handle_orientation_error_rad", "jacobian_condition", "joint_margin_rad",
        "joint_limit_valid", "delta_action_valid", "raw_action_valid", "root_translation_m",
        "root_yaw_rad", "root_x_door", "door_body_force_n", "arm_speed_max_radps",
    }
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping) or not required.issubset(sample):
            raise ArcFeasibilityError(f"sample {index} is missing P1 fields {sorted(required - set(sample)) if isinstance(sample, Mapping) else sorted(required)}")
    position_p95 = _p95([sample["tcp_handle_position_error_m"] for sample in samples])
    orientation_p95 = _p95([sample["tcp_handle_orientation_error_rad"] for sample in samples])
    max_hinge = max(_finite_number(sample["hinge_position_rad"], "hinge_position_rad") for sample in samples)
    root_translation = max(_finite_number(sample["root_translation_m"], "root_translation_m") for sample in samples)
    root_yaw = max(_finite_number(sample["root_yaw_rad"], "root_yaw_rad") for sample in samples)
    root_crossing = any(_finite_number(sample["root_x_door"], "root_x_door") > 0.0 for sample in samples)
    max_body_force = max(_finite_number(sample["door_body_force_n"], "door_body_force_n") for sample in samples)
    max_arm_speed = max(_finite_number(sample["arm_speed_max_radps"], "arm_speed_max_radps") for sample in samples)
    reasons: list[str] = []
    if outcome != "ARC_PROBE_REACHED" or max_hinge < target_hinge_rad:
        reasons.append("target_not_reached")
    window = samples[-TERMINAL_WINDOW_STEPS:]
    if len(window) != TERMINAL_WINDOW_STEPS or not all(sample["bilateral_contact"] is True for sample in window):
        reasons.append("terminal_bilateral_window")
    if position_p95 > POSITION_P95_MAX_M:
        reasons.append("position_error_p95")
    if orientation_p95 > ORIENTATION_P95_MAX_RAD:
        reasons.append("orientation_error_p95")
    if outcome == "JOINT_LIMIT" or any(sample["joint_limit_valid"] is not True or _finite_number(sample["joint_margin_rad"], "joint_margin_rad") < 0.0 for sample in samples):
        reasons.append("joint_limit")
    if any(_finite_number(sample["jacobian_condition"], "jacobian_condition") > JACOBIAN_CONDITION_MAX for sample in samples):
        reasons.append("jacobian_condition")
    if any(sample["delta_action_valid"] is not True for sample in samples):
        reasons.append("delta_action_bound")
    if any(sample["raw_action_valid"] is not True for sample in samples):
        reasons.append("raw_action_bound")
    if outcome == "ARC_PROBE_OVERSPEED":
        reasons.append("upper_dof_overspeed")
    if max_body_force > BODY_FORCE_MAX_N or outcome == "ARC_PROBE_BODY_COLLISION":
        reasons.append("door_body_collision")
    if root_crossing or outcome == "ARC_PROBE_ROOT_CROSSING":
        reasons.append("root_plane_crossing")
    translation_limit = F0_TRANSLATION_MAX_M if mode == "F0" else F1_TRANSLATION_MAX_M
    yaw_limit = F0_YAW_MAX_RAD if mode == "F0" else F1_YAW_MAX_RAD
    if root_translation > translation_limit or root_yaw > yaw_limit:
        reasons.append("root_relief_bound")
    if runtime.get("capture_valid") is not True:
        reasons.append("capture_invalid")
    return {
        "mode": mode,
        "target_hinge_rad": target_hinge_rad,
        "seed": seed,
        "env_id": env_id,
        "outcome": outcome,
        "feasible": not reasons,
        "failure_reasons": reasons,
        "max_hinge_rad": max_hinge,
        "position_error_p95_m": position_p95,
        "orientation_error_p95_rad": orientation_p95,
        "root_translation_max_m": root_translation,
        "root_yaw_max_rad": root_yaw,
        "root_crossing": root_crossing,
        "max_body_force_n": max_body_force,
        "max_arm_speed_radps": max_arm_speed,
        "sample_count": len(samples),
    }


def load_runtime_artifact(path: Path, *, mode: str, angle: float, seed: int) -> list[dict[str, Any]]:
    path = Path(path).expanduser().resolve()
    summary_path = path / "a2_hold_oracle_summary.json" if path.is_dir() else path
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArcFeasibilityError(f"cannot read runtime summary {summary_path}") from exc
    if payload.get("schema") != "a2_piper_v20_arc_probe_runtime_v1":
        raise ArcFeasibilityError(f"wrong runtime summary schema in {summary_path}")
    config = payload.get("config")
    if not isinstance(config, Mapping):
        raise ArcFeasibilityError("runtime summary config must be a mapping")
    _validate_runtime_config(config, mode, angle)
    outcomes = payload.get("per_env_outcome")
    samples = payload.get("per_env_samples")
    captures = payload.get("per_env_capture_valid")
    if not all(isinstance(value, list) and len(value) == EPISODES_PER_SEED for value in (outcomes, samples, captures)):
        raise ArcFeasibilityError("runtime summary must contain exactly 16 outcomes/samples/captures")
    return [
        assess_episode(
            mode=mode, target_hinge_rad=angle, seed=seed, env_id=env_id,
            outcome=outcomes[env_id], samples=samples[env_id],
            runtime={"capture_valid": captures[env_id]},
        )
        for env_id in range(EPISODES_PER_SEED)
    ]


def select_threshold(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    expected = {(mode, angle, seed, env_id) for mode in MODES for angle in ANGLES for seed in SEEDS for env_id in range(EPISODES_PER_SEED)}
    identities = {(row.get("mode"), row.get("target_hinge_rad"), row.get("seed"), row.get("env_id")) for row in rows}
    if identities != expected or len(rows) != len(expected):
        raise ArcFeasibilityError(f"P1 requires exactly {len(expected)} unique episode rows")
    cells = []
    for mode in MODES:
        for angle in ANGLES:
            selected = [row for row in rows if row["mode"] == mode and row["target_hinge_rad"] == angle]
            feasible = sum(bool(row["feasible"]) for row in selected)
            cells.append({"mode": mode, "target_hinge_rad": angle, "episodes": POOLED_EPISODES, "feasible_episodes": feasible, "pass": feasible >= PASS_MINIMUM})
    chosen = None
    for mode in MODES:
        passing = [cell for cell in cells if cell["mode"] == mode and cell["pass"]]
        if passing:
            chosen = max(passing, key=lambda cell: cell["target_hinge_rad"])
            break
    passed = chosen is not None and chosen["target_hinge_rad"] >= 0.9
    frozen = None if not passed else {
        "theta_send_rad": chosen["target_hinge_rad"],
        "selected_mode": chosen["mode"],
        "pre_send_relief_translation_max_m": F0_TRANSLATION_MAX_M if chosen["mode"] == "F0" else F1_TRANSLATION_MAX_M,
        "pre_send_relief_yaw_max_rad": F0_YAW_MAX_RAD if chosen["mode"] == "F0" else F1_YAW_MAX_RAD,
        "pre_send_root_plane_crossing_allowed": False,
        "position_error_p95_max_m": POSITION_P95_MAX_M,
        "orientation_error_p95_max_rad": ORIENTATION_P95_MAX_RAD,
    }
    return {"pass": passed, "cells": cells, "selected": chosen, "frozen_values": frozen}


def build_eval_command(checkpoint: Path, output_dir: Path, *, mode: str, angle: float, seed: int, gpu: str) -> list[str]:
    if mode not in MODES or angle not in ANGLES or seed not in SEEDS or gpu not in ALLOWED_GPUS:
        raise ArcFeasibilityError("invalid P1 eval command identity")
    diagnostic_terms = "[penalty_dof_overspeed,penalty_a2_door_body_contact]"
    return [
        str(ISAACLAB_PYTHON), "-m", "gr00t.rl.eval_agent_trl",
        f"+checkpoint={checkpoint}", "++checkpoint_load_mode=full", "++auto_load_latest=false",
        "++headless=true", "++num_envs=16", f"++seed={seed}", "++use_wandb=false",
        f"++env.config.max_episode_length_s={PROBE_EPISODE_LENGTH_S}",
        "++simulator.config.cameras.enable_cameras=false", "++simulator.config.render_results=false",
        "++env.config.a2_eval_door_handle_height_linspace=[0.80,1.10]",
        "++env.config.a2_hold_diagnostic_contact_detail_enabled=true",
        # Full-load eval restores the v19 checkpoint's env config.  Supply the
        # complete disabled-path v20 contract explicitly; telemetry is the sole
        # enabled selector for this eval-only physical probe.
        "++env.config.a2_v20_send_latch_enabled=false",
        f"++env.config.a2_v20_send_hinge_threshold={angle}",
        "++env.config.a2_v20_send_hinge_tolerance=0.05",
        "++env.config.a2_v20_pre_send_root_x_margin=0.03",
        "++env.config.a2_v20_pre_send_crossing_mode=disabled",
        "++env.config.a2_v20_pre_send_crossing_penalty_component=1.0",
        "++env.config.a2_v20_telemetry_enabled=true",
        "++env.config.a2_v20_traversal_economics_enabled=false",
        "++env.config.a2_v20_target_root_pre_send_scale=0.0",
        "++env.config.a2_v20_target_root_post_send_stage4_scale=0.5",
        "++env.config.a2_v20_target_root_ramp_width_rad=0.20",
        "++env.config.a2_corridor_latch_mode=legacy_root_or_hinge",
        "++env.config.a2_v20_arm_tie_enabled=false",
        "++env.config.a2_v20_arm_tangent_carry_scale=0.0",
        "++env.config.a2_v20_handle_arc_tracking_scale=0.0",
        "++env.config.a2_v20_taskspace_activity_floor_mps=0.005",
        "++env.config.a2_v20_arc_position_tolerance_m=0.03",
        "++env.config.a2_v20_arc_orientation_tolerance_rad=0.20",
        "++env.config.a2_v20_formal_values_frozen=false",
        "++env.config.a2_v20_formal_launch=false",
        "++env.config.a2_v20_calibration_label=non_formal_calibration_only",
        "++algo.config.eval.num_eval_episodes=16", "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.dump_to_log_metrics=true", "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        f"++algo.config.eval.a2_diagnostic_reward_terms={diagnostic_terms}",
        "++algo.config.eval.a2_forced_gripper_close_enabled=false",
        "++algo.config.eval.a2_hold_oracle_enabled=true",
        "++algo.config.eval.a2_v20_arc_probe_enabled=true",
        f"++algo.config.eval.a2_v20_arc_probe_mode={mode}",
        f"++algo.config.eval.a2_v20_arc_probe_target_hinge_rad={angle}",
        f"++algo.config.eval.a2_v20_arc_probe_timeout_steps={PROBE_TIMEOUT_STEPS}",
        f"++algo.config.eval.a2_v20_arc_probe_lead_rad={PROBE_LEAD_RAD}",
        f"++algo.config.eval.a2_v20_arc_probe_max_orientation_step_rad={PROBE_MAX_ORIENTATION_STEP_RAD}",
        f"++algo.config.eval.a2_v20_arc_probe_joint_target_step_max_rad={PROBE_JOINT_TARGET_STEP_MAX_RAD}",
        f"++algo.config.eval.a2_v20_arc_probe_root_hold_translation_damping_gain={PROBE_ROOT_HOLD_TRANSLATION_DAMPING_GAIN}",
        f"++algo.config.eval.a2_v20_arc_probe_root_hold_yaw_gain={PROBE_ROOT_HOLD_YAW_GAIN}",
        f"++algo.config.eval.a2_v20_arc_probe_root_hold_yaw_damping_gain={PROBE_ROOT_HOLD_YAW_DAMPING_GAIN}",
        f"++algo.config.eval.a2_v20_arc_probe_f1_root_hold_scale={PROBE_F1_ROOT_HOLD_SCALE}",
        "++algo.config.eval.save_goal_reached_only=false", "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false", "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        f"++eval_name=v20_p1_{mode}_theta{angle:.1f}_seed{seed}", f"++eval_output_dir={output_dir}",
    ]


def _run_sweep(checkpoint: Path, staging: Path, gpus: Sequence[str]) -> dict[tuple[str, float, int], Path]:
    if not ISAACLAB_PYTHON.is_file() or not checkpoint.is_file():
        raise ArcFeasibilityError("IsaacLab Python or warm-start checkpoint is missing")
    if _sha256(checkpoint) != EXPECTED_CHECKPOINT_SHA256:
        raise ArcFeasibilityError("P1 warm-start checkpoint SHA256 mismatch")
    jobs = [(mode, angle, seed) for mode in MODES for angle in ANGLES for seed in SEEDS]
    artifacts: dict[tuple[str, float, int], Path] = {}
    for offset in range(0, len(jobs), len(gpus)):
        wave = jobs[offset:offset + len(gpus)]
        running = []
        for index, identity in enumerate(wave):
            mode, angle, seed = identity
            output_dir = staging / "runtime" / f"{mode}_theta{angle:.1f}_seed{seed}"
            log_path = staging / "logs" / f"{mode}_theta{angle:.1f}_seed{seed}.log"
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            stream = log_path.open("wb")
            env = os.environ.copy()
            env["CUDA_VISIBLE_DEVICES"] = gpus[index]
            env["ACCELERATE_TORCH_DEVICE"] = "cuda:0"
            env["VK_ICD_FILENAMES"] = "/usr/share/vulkan/icd.d/nvidia_icd.json"
            process = subprocess.Popen(build_eval_command(checkpoint, output_dir, mode=mode, angle=angle, seed=seed, gpu=gpus[index]), cwd=REPO_ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
            running.append((identity, output_dir, log_path, stream, process))
        failures = []
        for identity, output_dir, log_path, stream, process in running:
            returncode = process.wait()
            stream.close()
            if returncode != 0:
                failures.append({"identity": identity, "returncode": returncode, "log": str(log_path)})
            else:
                artifacts[identity] = output_dir
        if failures:
            raise ArcFeasibilityError(f"P1 runtime wave failed without retry: {failures}")
    return artifacts


def _write_outputs(staging: Path, rows: Sequence[Mapping[str, Any]], selection: Mapping[str, Any], provenance: Mapping[str, Any]) -> None:
    payload = {"schema": SCHEMA, "status": "PASS" if selection["pass"] else "FAIL", "provenance": provenance, "selection_rule": "highest F0 >=46/48 else highest F1 >=46/48; theta>=0.90", **selection, "episodes": list(rows)}
    (staging / "per_env").mkdir(parents=True, exist_ok=False)
    for row in rows:
        name = f"{row['mode']}_theta{row['target_hinge_rad']:.1f}_seed{row['seed']}_env{row['env_id']:02d}.json"
        (staging / "per_env" / name).write_text(json.dumps(row, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (staging / "a2_piper_v20_arc_feasibility.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (staging / "a2_piper_v20_arc_feasibility.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            csv_row = {key: row[key] for key in CSV_FIELDS}
            csv_row["failure_reasons"] = ";".join(csv_row["failure_reasons"])
            writer.writerow(csv_row)
    lines = ["# A2 Piper base v20 P1 arc feasibility", "", f"Status: **{payload['status']}**", "", "| Mode | Target rad | Feasible | Result |", "|---|---:|---:|---|"]
    lines.extend(f"| {cell['mode']} | {cell['target_hinge_rad']:.1f} | {cell['feasible_episodes']}/48 | {'PASS' if cell['pass'] else 'FAIL'} |" for cell in selection["cells"])
    lines.extend(["", "Frozen values:", "", f"```json\n{json.dumps(selection['frozen_values'], indent=2)}\n```", ""])
    (staging / "a2_piper_v20_arc_feasibility.md").write_text("\n".join(lines), encoding="utf-8")


def _parse_artifact(value: str) -> tuple[tuple[str, float, int], Path]:
    parts = value.split(":", 3)
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("artifact must be MODE:ANGLE:SEED:PATH")
    mode, angle_text, seed_text, path_text = parts
    try:
        angle, seed = float(angle_text), int(seed_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("artifact angle/seed is invalid") from exc
    if mode not in MODES or angle not in ANGLES or seed not in SEEDS:
        raise argparse.ArgumentTypeError("artifact identity is outside the P1 grid")
    return (mode, angle, seed), Path(path_text)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--gpus", default=",".join(ALLOWED_GPUS))
    parser.add_argument("--run", action="store_true", help="run all 24 live IsaacLab batches before adjudication")
    parser.add_argument("--artifact", action="append", default=[], type=_parse_artifact, help="MODE:ANGLE:SEED:PATH; exactly 24 when --run is absent")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve()
    if output_dir.exists():
        raise ArcFeasibilityError(f"refusing to overwrite P1 output: {output_dir}")
    staging = output_dir.parent / f".{output_dir.name}.tmp-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        if args.run:
            if args.artifact:
                raise ArcFeasibilityError("--run and --artifact are mutually exclusive")
            gpus = tuple(item.strip() for item in args.gpus.split(",") if item.strip())
            if not gpus or len(set(gpus)) != len(gpus) or any(item not in ALLOWED_GPUS for item in gpus):
                raise ArcFeasibilityError("--gpus requires unique physical ids from 0..6; GPU7 is reserved")
            artifacts = _run_sweep(args.checkpoint.expanduser().resolve(), staging, gpus)
        else:
            artifacts = dict(args.artifact)
            if len(args.artifact) != len(MODES) * len(ANGLES) * len(SEEDS) or len(artifacts) != len(args.artifact):
                raise ArcFeasibilityError("offline adjudication requires exactly 24 unique --artifact mappings")
        rows = [row for mode in MODES for angle in ANGLES for seed in SEEDS for row in load_runtime_artifact(artifacts[(mode, angle, seed)], mode=mode, angle=angle, seed=seed)]
        selection = select_threshold(rows)
        provenance = {"checkpoint": str(args.checkpoint.expanduser().resolve()), "checkpoint_sha256": _sha256(args.checkpoint.expanduser().resolve()), "modes": list(MODES), "angles_rad": list(ANGLES), "seeds": list(SEEDS), "episodes_per_seed": EPISODES_PER_SEED}
        _write_outputs(staging, rows, selection, provenance)
        staging.rename(output_dir)
    except Exception:
        failed = output_dir.parent / f".{output_dir.name}.failed-{uuid.uuid4().hex}"
        staging.rename(failed)
        raise
    print(json.dumps({"status": "PASS" if selection["pass"] else "FAIL", "output_dir": str(output_dir), "frozen_values": selection["frozen_values"]}, sort_keys=True))
    return 0 if selection["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
