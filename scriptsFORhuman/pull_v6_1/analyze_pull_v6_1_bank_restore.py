#!/usr/bin/env python3
"""Validate exact V6.1 late-bank provenance and stage-specific restore traces."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch

from trace_utils import first_episode_rows, load_trace, nested, required


EXPECTED_SCHEMA = "a2_piper_pull_v61_late_state_bank_v1"
EXPECTED_LABELS = ("post_release_d25", "frame_passage", "e6_stage5_entry")
EXPECTED_STAGE = {"post_release_d25": 4, "frame_passage": 4, "e6_stage5_entry": 5}
CONTINUATION_TARGET = {
    "post_release_d25": "frame_passage",
    "frame_passage": "E6_PATH_REVERSAL_ENTRY",
    "e6_stage5_entry": "E7_WHOLE_BODY_CLEAR",
}


def _trace_arg(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if not separator or label not in EXPECTED_LABELS:
        raise argparse.ArgumentTypeError("trace must be LABEL=PATH for a canonical late-bank label")
    return label, Path(path)


def _finite(value: Any, where: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{where} must be finite")


def _finite_vector(value: Any, where: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{where} must be a non-empty vector")
    for index, item in enumerate(value):
        _finite(item, f"{where}[{index}]")


def _bank_summary(path: Path) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict) or payload.get("schema") != EXPECTED_SCHEMA:
        raise ValueError("late bank schema mismatch")
    if tuple(payload.get("labels", ())) != EXPECTED_LABELS:
        raise ValueError("late bank labels must be exact ordered D25/frame/E6")
    provenance = payload.get("provenance")
    if not isinstance(provenance, list) or len(provenance) != 3:
        raise ValueError("late bank provenance must contain three rows")
    rows = []
    for label, row in zip(EXPECTED_LABELS, provenance):
        if (
            not isinstance(row, dict)
            or row.get("event_label") != label
            or row.get("source_env_id") != 14
            or not isinstance(row.get("source_control_step"), int)
        ):
            raise ValueError(f"late bank provenance mismatch for {label}")
        rows.append(dict(row))
    buffers = payload.get("buffers")
    if not isinstance(buffers, dict) or not buffers:
        raise ValueError("late bank registered buffers are missing")
    return {
        "schema": payload["schema"],
        "labels": list(payload["labels"]),
        "provenance": rows,
        "registered_buffer_count": len(buffers),
        "robot_root_state_shape": list(payload["robot_root_state"].shape),
        "door_dof_pos_shape": list(payload["door_dof_pos"].shape),
    }


def _restore_summary(label: str, path: Path, expected_num_envs: int) -> dict[str, Any]:
    trace = load_trace(path)
    env_ids = sorted({int(required(row, "env_id", "row")) for row in trace})
    expected_env_ids = list(range(expected_num_envs))
    if env_ids != expected_env_ids:
        raise ValueError(
            f"{label} restore trace must contain env0..{expected_num_envs - 1}; got {env_ids}"
        )
    first_rows = []
    continuation_reached_env_ids = []
    for env_id in env_ids:
        rows = first_episode_rows(trace, env_id)
        first = rows[0]
        reset = nested(first, "pull_v0", "pull_v61_late_state_bank_reset")
        if reset.get("label") != label or reset.get("stage") != EXPECTED_STAGE[label]:
            raise ValueError(f"{label} env{env_id} restored wrong source: {reset}")
        if int(nested(first, "pull_v0", "stage")) != EXPECTED_STAGE[label]:
            raise ValueError(f"{label} env{env_id} first telemetry stage mismatch")
        for field in (
            "policy_high_level_action_raw",
            "post_delta_post_warp_env_action",
            "root_pos_w",
            "root_quat_w",
            "arm_joint_pos",
        ):
            _finite_vector(required(first, field, "first restore row"), f"{label}.env{env_id}.{field}")
        _finite(required(first, "door_hinge_joint_pos", "first restore row"), f"{label}.env{env_id}.hinge")
        first_rows.append({
            "env_id": env_id,
            "step_index": int(required(first, "step_index", "first restore row")),
            "stage": int(nested(first, "pull_v0", "stage")),
            "stage4_subphase": int(nested(first, "pull_v0", "pull_v6", "stage4_subphase")),
            "event_state": nested(first, "pull_v0", "event_state"),
            "reset_source": reset,
            "first_action_finite": True,
            "last_step": int(required(rows[-1], "step_index", "last restore row")),
            "last_stage": int(nested(rows[-1], "pull_v0", "stage")),
            "terminal_reason": required(rows[-1], "terminal_reasons", "last restore row"),
        })
        if label == "post_release_d25":
            reached = any(bool(nested(row, "pull_v3_traversal", "frame_passage")) for row in rows)
        elif label == "frame_passage":
            reached = any(
                nested(row, "pull_v0", "event_state")
                in {"E6_PATH_REVERSAL_ENTRY", "E7_WHOLE_BODY_CLEAR"}
                for row in rows
            )
        else:
            reached = any(
                bool(nested(row, "pull_v0_episode", "whole_body_clear"))
                for row in rows
            )
        if reached:
            continuation_reached_env_ids.append(env_id)
    return {
        "trace": str(path),
        "envs": first_rows,
        "continuation_target": CONTINUATION_TARGET[label],
        "continuation_reached_env_ids": continuation_reached_env_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--trace", action="append", type=_trace_arg, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-continuation", action="store_true")
    parser.add_argument("--expected-num-envs", type=int, default=4)
    args = parser.parse_args()
    if args.expected_num_envs <= 0:
        raise ValueError("expected-num-envs must be positive")
    traces = dict(args.trace)
    report: dict[str, Any] = {
        "schema": "a2_piper_pull_v61_bank_restore_report_v1",
        "admission": "NOT_ADMITTED",
        "cold_recurrent_contract": "actor and critic hidden state are zeroed; no LSTM hidden is banked",
        "evidence_scope": "late-bank capture/restore mechanism only; not strict-natural population evidence",
    }
    try:
        if set(traces) != set(EXPECTED_LABELS):
            raise ValueError("provide exactly D25/frame/E6 restore traces")
        report["bank"] = _bank_summary(args.bank)
        report["restores"] = {
            label: _restore_summary(label, traces[label], args.expected_num_envs)
            for label in EXPECTED_LABELS
        }
        if args.require_continuation:
            for label, restore in report["restores"].items():
                if not restore["continuation_reached_env_ids"]:
                    raise ValueError(
                        f"{label} did not reach {restore['continuation_target']} in any env"
                    )
    except (KeyError, TypeError, ValueError) as error:
        report["admission_reason"] = str(error)
    else:
        report["admission"] = "ADMITTED"
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["admission"] == "ADMITTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
