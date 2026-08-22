"""Extract exact v26 R0 milestone tables from formal runtime logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
ITERATION_RE = re.compile(r"Learning iteration\s+(\d+)")
METRIC_RE = re.compile(
    r"^\s*│\s*(.*?)\s*:\s*"
    r"(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*│\s*$"
)
DEFAULT_MILESTONES = (250, 500, 1000, 1500, 2000, 3000, 4000)


def _keep_metric(name: str) -> bool:
    return (
        name in {
            "Mean rewards",
            "Total episodes",
            "Total timesteps",
            "Iteration time",
            "Total time",
            "ETA",
            "Env/a2_door_hinge_joint_pos_mean",
            "Env/a2_door_handle_joint_pos_mean",
            "Env/a2_root_x_mean",
            "Env/a2_root_y_mean",
            "Env/a2_target_root_distance_mean",
            "Env/a2_doorframe_contact_force_mean",
            "Env/a2_doorframe_contact_frac",
            "Env/a2_stage2_both_contact_frac",
            "Env/a2_stage2_opposite_squeeze_frac",
            "Env/a2_stage2_squeeze_force_window_frac",
            "Env/a2_stage2_contact_stability_frac",
            "Env/a2_stage3_stage4_both_contact_frac",
            "Env/a2_stage3_stage4_opposite_squeeze_frac",
            "Env/a2_stage3_stage4_squeeze_force_window_frac",
            "Env/a2_stage4_release_gate_frac",
            "Env/a2_crossing_while_holding_frac",
            "Env/a2_release_event_env_count",
            "Env/a2_post_release_body_contact_env_count",
            "Mean episode rew_stage",
            "Mean episode rew_complete",
        }
        or name.startswith("Env/a2_v26_")
    )


def _parse_log(path: Path) -> dict[int, dict[str, float | int]]:
    tables: dict[int, dict[str, float | int]] = {}
    current_iteration: int | None = None
    current_metrics: dict[str, float | int] = {}

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = ANSI_RE.sub("", raw_line)
        iteration_match = ITERATION_RE.search(line)
        if iteration_match:
            if current_iteration is not None:
                tables[current_iteration] = current_metrics
            current_iteration = int(iteration_match.group(1))
            current_metrics = {}
            continue
        if current_iteration is None:
            continue
        metric_match = METRIC_RE.match(line)
        if metric_match is None:
            continue
        name, raw_value = metric_match.groups()
        if not _keep_metric(name):
            continue
        value = float(raw_value)
        current_metrics[name] = int(value) if value.is_integer() else value

    if current_iteration is not None:
        tables[current_iteration] = current_metrics
    return tables


def _parse_log_argument(raw: str) -> tuple[str, Path]:
    label, separator, path = raw.partition("=")
    if not separator or not label or not path:
        raise argparse.ArgumentTypeError("--log must use LABEL=/absolute/or/relative/path")
    return label, Path(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", action="append", type=_parse_log_argument, required=True)
    parser.add_argument("--milestones", nargs="+", type=int, default=DEFAULT_MILESTONES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cells = {}
    for label, path in args.log:
        tables = _parse_log(path)
        if not tables:
            raise RuntimeError(f"no completed training table found in {path}")
        latest_iteration = max(tables)
        cells[label] = {
            "log": str(path),
            "latest_iteration": latest_iteration,
            "latest": tables[latest_iteration],
            "milestones": {
                str(iteration): tables[iteration]
                for iteration in args.milestones
                if iteration in tables
            },
        }

    payload = {
        "schema": "a2_piper_base_v26_r0_progress_v1",
        "requested_milestones": args.milestones,
        "cells": cells,
    }
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)


if __name__ == "__main__":
    main()
