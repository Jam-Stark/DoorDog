#!/usr/bin/env python3
"""Warn when v13 gate metrics stay exactly zero across eval checkpoints."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


DEFAULT_GATE_METRICS = (
    "a2_stage2_contact_stability_frac",
    "a2_stage2_streak_ge_K_frac",
    "a2_stage3_stage4_contact_stability_frac",
    "a2_stage3_stage4_streak_ge_K_frac",
)


def resolve_metrics_path(path: Path) -> Path:
    """Resolve an eval directory or explicit JSON path."""
    metrics_path = path / "eval_to_log_metrics.json" if path.is_dir() else path
    if not metrics_path.is_file():
        raise FileNotFoundError(
            f"Expected eval_to_log_metrics.json file; got {metrics_path}."
        )
    return metrics_path


def load_metric_maxima(path: Path, metrics: tuple[str, ...]) -> dict[str, float]:
    """Load one checkpoint and return each gate metric's maximum step value."""
    metrics_path = resolve_metrics_path(path)
    records = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError(f"{metrics_path} must contain a non-empty JSON list.")

    maxima = {metric: -math.inf for metric in metrics}
    for record_index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(
                f"{metrics_path} record {record_index} must be an object."
            )
        for metric in metrics:
            if metric not in record:
                raise KeyError(
                    f"{metrics_path} record {record_index} is missing metric {metric!r}."
                )
            value = record[metric]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"{metrics_path} metric {metric!r} must be numeric; got {value!r}."
                )
            value = float(value)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{metrics_path} metric {metric!r} must be finite in [0, 1]; "
                    f"got {value}."
                )
            maxima[metric] = max(maxima[metric], value)
    return maxima


def find_exact_zero_runs(
    checkpoint_metrics: list[tuple[Path, dict[str, float]]],
    metric: str,
    consecutive: int,
) -> list[list[Path]]:
    """Return maximal runs where a checkpoint's metric maximum is exactly zero."""
    if consecutive <= 0:
        raise ValueError(f"consecutive must be positive; got {consecutive}.")
    runs: list[list[Path]] = []
    current: list[Path] = []
    for path, metrics in checkpoint_metrics:
        if metric not in metrics:
            raise KeyError(f"Missing metric {metric!r} for checkpoint {path}.")
        if metrics[metric] == 0.0:
            current.append(path)
            continue
        if len(current) >= consecutive:
            runs.append(current)
        current = []
    if len(current) >= consecutive:
        runs.append(current)
    return runs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report v13 gate maxima and warn when a metric is exactly zero for "
            "N consecutive checkpoint evals. Input order is checkpoint order."
        )
    )
    parser.add_argument(
        "checkpoints",
        nargs="+",
        type=Path,
        help="Eval directories or eval_to_log_metrics.json files, in checkpoint order.",
    )
    parser.add_argument(
        "--consecutive",
        type=int,
        default=3,
        help="Minimum exact-zero run length (default: 3).",
    )
    parser.add_argument(
        "--metric",
        action="append",
        dest="metrics",
        help="Metric to inspect; repeat to override the default v13 gate metric set.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return exit code 2 when an exact-zero run is found.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.consecutive <= 0:
        raise ValueError(f"--consecutive must be positive; got {args.consecutive}.")
    metrics = tuple(args.metrics) if args.metrics else DEFAULT_GATE_METRICS
    if not metrics or len(set(metrics)) != len(metrics):
        raise ValueError("Metric names must be non-empty and unique.")

    checkpoint_metrics = [
        (path, load_metric_maxima(path, metrics)) for path in args.checkpoints
    ]
    for path, maxima in checkpoint_metrics:
        values = " ".join(f"{metric}={maxima[metric]:.8f}" for metric in metrics)
        print(f"CHECKPOINT {path}: {values}")

    warning_found = False
    for metric in metrics:
        for run in find_exact_zero_runs(
            checkpoint_metrics,
            metric,
            args.consecutive,
        ):
            warning_found = True
            print(
                "WARNING: "
                f"{metric} stayed exactly zero for {len(run)} consecutive checkpoints: "
                + " -> ".join(str(path) for path in run)
            )
    if not warning_found:
        print("V13_GATE_ZERO_WARNING: PASS (no qualifying exact-zero run)")
    return 2 if warning_found and args.fail_on_warning else 0


if __name__ == "__main__":
    raise SystemExit(main())
