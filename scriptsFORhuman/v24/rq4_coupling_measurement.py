"""Measurement-only RQ4 closure from the valid r12 post-F3 population."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROWS = Path(
    "logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/"
    "P2_MARGINAL_E1_PILOT_POPULATION.jsonl"
)
DEFAULT_OUTPUT_ROOT = Path("logs_eval/base_v24/rq4/measurement_only/r2")
EXPECTED_AUTHORITY = {
    "capacity_lambda": "ESTIMATE_ONLY_DIRECTIONAL_MARGIN",
    "pd_command": "ESTIMATE_ONLY_IMPLICIT_PD_COMMAND",
    "gravity": "ISAACLAB_GRAVITY_COMPENSATION_ESTIMATE",
    "state": "HIGH_LEVEL_ARTICULATION_DATA",
    "actual_generalized_torque": "UNAVAILABLE_NOT_USED",
    "door_friction": "MODELED_FROM_PARAMS",
    "solver_applied": False,
}
CELLS = {
    "DF1_FULL_SEED0": ("FULL", 0),
    "DF1_FULL_SEED1": ("FULL", 1),
    "DF1_RP0_SEED0": ("RP0", 0),
    "DF1_RP0_SEED1": ("RP0", 1),
}
METRICS = (
    "tau_req_median_nm",
    "directional_utilization_median",
    "directional_clip_fraction_median",
    "progress_recovery_delta_rad",
    "max_loaded_foot_slip_m_s",
)


def _lambda_zone(value: float) -> str:
    if value < 0.5:
        return "E0_PROXY"
    if value < 1.0:
        return "E1_BAND"
    return "ABOVE_BOUNDARY_RIGHT_CENSORED"


def _repo_path(path: str | Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else REPO_ROOT / target


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _load_population(path: str | Path) -> list[dict[str, Any]]:
    source = _repo_path(path)
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 64:
        raise ValueError("RQ4 measurement-only input must be the exact 64-row r12 population")
    return rows


def _validate_row(row: Mapping[str, Any]) -> None:
    cell = row.get("cell")
    posture_seed = CELLS.get(cell)
    if posture_seed is None or (row.get("posture"), row.get("training_seed")) != posture_seed:
        raise ValueError("RQ4 row has invalid r12 cell identity")
    env_id = row.get("env_id")
    scenario = row.get("scenario_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < 16 or scenario != f"S{env_id:02d}":
        raise ValueError("RQ4 row has invalid paired scenario identity")
    if row.get("authority") != EXPECTED_AUTHORITY:
        raise ValueError("RQ4 row authority is not the r12 modeled/estimate contract")
    if row.get("source_unavailable") is not None or row.get("model_valid") is not True or row.get("foot_slip_valid") is not True:
        raise ValueError("RQ4 measurement-only input contains invalid source vitals")
    for metric in METRICS:
        _finite(row.get(metric), label=f"{cell}:{scenario}:{metric}")
    _finite(row.get("lambda"), label=f"{cell}:{scenario}:lambda")


def _delta_summary(values: Sequence[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean_full_minus_rp0": fmean(values),
        "median_full_minus_rp0": median(values),
        "positive": sum(value > 0.0 for value in values),
        "negative": sum(value < 0.0 for value in values),
        "zero": sum(value == 0.0 for value in values),
    }


def build_measurement(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indexed: dict[tuple[int, str, str], Mapping[str, Any]] = {}
    for row in rows:
        _validate_row(row)
        key = (int(row["training_seed"]), str(row["scenario_id"]), str(row["posture"]))
        if key in indexed:
            raise ValueError(f"RQ4 population duplicates pair member {key!r}")
        indexed[key] = row
    if len(indexed) != 64:
        raise ValueError("RQ4 population does not contain 64 unique pair members")

    pair_rows: list[dict[str, Any]] = []
    deltas_by_seed: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    pooled: dict[str, list[float]] = defaultdict(list)
    lambda_zone_pairs: dict[str, int] = defaultdict(int)
    lambda_right_censored_by_cell: dict[str, int] = defaultdict(int)
    for seed in (0, 1):
        for env_id in range(16):
            scenario = f"S{env_id:02d}"
            full = indexed[(seed, scenario, "FULL")]
            rp0 = indexed[(seed, scenario, "RP0")]
            deltas = {metric: _finite(full[metric], label=metric) - _finite(rp0[metric], label=metric) for metric in METRICS}
            full_lambda = _finite(full["lambda"], label="lambda")
            rp0_lambda = _finite(rp0["lambda"], label="lambda")
            full_zone = _lambda_zone(full_lambda)
            rp0_zone = _lambda_zone(rp0_lambda)
            lambda_zone_pairs[f"{full_zone}__TO__{rp0_zone}"] += 1
            if full_lambda >= 1.0e6:
                lambda_right_censored_by_cell[str(full["cell"])] += 1
            if rp0_lambda >= 1.0e6:
                lambda_right_censored_by_cell[str(rp0["cell"])] += 1
            for metric, value in deltas.items():
                deltas_by_seed[seed][metric].append(value)
                pooled[metric].append(value)
            pair_rows.append(
                {
                    "schema": "a2_piper_v24_rq4_measurement_pair_v1",
                    "seed": seed,
                    "scenario_id": scenario,
                    "full_cell": full["cell"],
                    "rp0_cell": rp0["cell"],
                    "full_window_id": full["window_id"],
                    "rp0_window_id": rp0["window_id"],
                    "full_minus_rp0": deltas,
                    "lambda_zone": {"full": full_zone, "rp0": rp0_zone},
                    "lambda_raw_audit": {"full": full_lambda, "rp0": rp0_lambda},
                    "stable_grasp_delta": int(full["stable_grasp"] is True) - int(rp0["stable_grasp"] is True),
                    "admitted_sustained_e1_delta": int(full["admitted_sustained_e1"] is True) - int(rp0["admitted_sustained_e1"] is True),
                    "authority": EXPECTED_AUTHORITY,
                    "claim_scope": "PAIRED_CHRONIC_DESCRIPTIVE_ONLY",
                }
            )

    summary = {
        "schema": "a2_piper_v24_rq4_measurement_only_v1",
        "status": "EXECUTED_DESCRIPTIVE_ONLY",
        "typed_results": [
            "V24_COUPLING_FORWARD_PROXY_ONLY",
            "V24_COUPLING_CRITIC_UNCALIBRATED",
        ],
        "scientific_terminal_input": "V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3",
        "population_rows": len(rows),
        "paired_rows": len(pair_rows),
        "pairing": "FULL_MINUS_RP0_WITHIN_TRAINING_SEED_AND_SCENARIO",
        "admitted_sustained_e1_by_cell": {
            cell: sum(row.get("admitted_sustained_e1") is True for row in rows if row.get("cell") == cell)
            for cell in CELLS
        },
        "delta_summary_by_seed": {
            str(seed): {metric: _delta_summary(values) for metric, values in deltas_by_seed[seed].items()}
            for seed in (0, 1)
        },
        "delta_summary_pooled": {metric: _delta_summary(values) for metric, values in pooled.items()},
        "lambda_interpretation": {
            "comparison": "FROZEN_ZONE_ONLY_NOT_CONTINUOUS_DELTA",
            "zone_pair_counts": dict(sorted(lambda_zone_pairs.items())),
            "epsilon_right_censored_count_by_cell": {
                cell: lambda_right_censored_by_cell.get(cell, 0) for cell in CELLS
            },
            "reason": "Zero additional directional capacity produces epsilon-denominator lambda values whose magnitude is not a continuous effect size.",
        },
        "telemetry_authority": {
            "arm": {
                "available": ["directional_utilization", "directional_clip_fraction", "estimated_lambda"],
                "authority": "ESTIMATE_ONLY_DIRECTIONAL_MARGIN",
                "unavailable": ["actual_generalized_torque", "joint_power", "handle_wrench"],
            },
            "base_leg": {
                "available": [],
                "unavailable": ["base_acceleration", "base_rates", "leg_action", "leg_torque", "leg_power", "support_polygon"],
            },
            "feet": {
                "available": ["max_loaded_foot_slip_m_s"],
                "unavailable": ["3d_grf", "normal_force", "tangential_force", "friction_utilization", "contact_duration", "cop"],
            },
            "door": {
                "available": ["modeled_required_torque", "hinge_progress", "modeled_friction_parameters"],
                "authority": "MODELED_FROM_PARAMS",
                "unavailable": ["solver_applied_friction_torque", "door_work", "door_power"],
            },
        },
        "intervention_status": "NOT_PERFORMED_P2_POST_F3_TERMINAL",
        "missing_registered_design": "BASE_NEUTRAL_X_ARM_SAFE_HOLD_FORWARD_INTERVENTION",
        "shadow_critic": {
            "status": "NOT_TRAINED_UNCALIBRATED",
            "reason": "No registered intervention target and no sufficient per-cell E1 denominator",
        },
        "claim_boundary": "Chronic FULL-RP0 proxy deltas are descriptive and cannot identify arm-base-foot causal coupling.",
        "source_population": str(DEFAULT_ROWS),
        "authority": EXPECTED_AUTHORITY,
    }
    return pair_rows, summary


def _write_outputs(output_root: str | Path, pair_rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> None:
    root = _repo_path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    pairs_path = root / "V24_RQ4_COUPLING_PAIR_ROWS.jsonl"
    summary_path = root / "V24_RQ4_COUPLING_MEASUREMENT.json"
    for path in (pairs_path, summary_path):
        if path.exists() or path.is_symlink():
            raise RuntimeError(f"RQ4 measurement refuses to overwrite existing artifact: {path}")
    with pairs_path.open("x", encoding="utf-8") as stream:
        for row in pair_rows:
            stream.write(json.dumps(dict(row), sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    with summary_path.open("x", encoding="utf-8") as stream:
        json.dump(dict(summary), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="base_v24 RQ4 measurement-only coupling closure")
    parser.add_argument("--rows", default=str(DEFAULT_ROWS))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args(argv)
    pair_rows, summary = build_measurement(_load_population(args.rows))
    _write_outputs(args.output_root, pair_rows, summary)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
