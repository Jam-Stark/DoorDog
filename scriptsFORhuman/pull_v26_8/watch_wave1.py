#!/usr/bin/env python3
"""Tmux-resident Wave-1 milestone supervisor for one frozen pull-v26.8 root."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ORCHESTRATE = REPO / "scriptsFORhuman/pull_v26_8/orchestrate.sh"
RUNS = REPO / ".ai/runtime/runs"
CELLS = ("P_S0", "P_S1", "P_S2")
STEPS = (750, 1500, 2250, 3000, 3750, 4500, 5250, 6000)


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def attempt_from_suffix(suffix: str) -> int:
    mapping = {"_natural1": 1, "_natural1_r2": 2, "_natural1_r3": 3}
    try:
        return mapping[suffix]
    except KeyError as exc:
        raise ValueError(f"unsupported attempt suffix: {suffix!r}") from exc


def suffix_from_attempt(attempt: int) -> str:
    mapping = {1: "_natural1", 2: "_natural1_r2", 3: "_natural1_r3"}
    try:
        return mapping[attempt]
    except KeyError as exc:
        raise ValueError(f"unsupported PULL_V26_8_ATTEMPT: {attempt}") from exc


def load_json(path: Path) -> dict:
    require(path.is_file(), f"missing JSON artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"JSON artifact is not an object: {path}")
    return payload


def receipt_path(name: str, suffix: str) -> Path:
    return RUNS / f"{name}{suffix}" / "RUN_RECEIPT.json"


def terminal_returncode(receipt: Path) -> int | None:
    exit_code = receipt.parent / "exit_code.txt"
    if not exit_code.is_file():
        return None
    return int(exit_code.read_text(encoding="utf-8").strip())


def write_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit(path: Path, state: dict, event: dict) -> None:
    state["events"].append(event)
    state["last_event"] = event
    write_state(path, state)
    print(json.dumps(event, ensure_ascii=False), flush=True)


def child_env(attempt: int) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PULL_V26_8_ATTEMPT"] = str(attempt)
    return environment


def command(arguments: list[str], attempt: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ORCHESTRATE), *arguments],
        cwd=REPO,
        env=child_env(attempt),
        text=True,
        capture_output=True,
        check=False,
    )


def checkpoint_path(train_root: Path, cell: str, step: int) -> Path:
    return train_root / cell / f"model_step_{step:06d}.pt"


def record_new_train_failures(
    state_path: Path,
    state: dict,
    *,
    suffix: str,
) -> set[str]:
    failed = set(state["failed_cells"])
    for cell in CELLS:
        if cell in failed:
            continue
        receipt = receipt_path(f"pull_v26_8_train_{cell.lower()}", suffix)
        require(receipt.is_file(), f"missing train receipt for {cell}: {receipt}")
        returncode = terminal_returncode(receipt)
        if returncode is None or returncode == 0:
            continue
        failure = {
            "event": "TRAIN_PROCESS_FAILURE",
            "cell": cell,
            "receipt": str(receipt),
            "returncode": returncode,
        }
        failed.add(cell)
        state["failed_cells"] = sorted(failed)
        emit(state_path, state, failure)
    return failed


def wait_for_checkpoints(
    state_path: Path,
    state: dict,
    *,
    train_root: Path,
    suffix: str,
    step: int,
) -> bool:
    while True:
        failed = record_new_train_failures(state_path, state, suffix=suffix)
        missing = [cell for cell in CELLS if not checkpoint_path(train_root, cell, step).is_file()]
        if not missing:
            return True
        terminal_without_checkpoint: list[dict] = []
        for cell in missing:
            receipt = receipt_path(f"pull_v26_8_train_{cell.lower()}", suffix)
            require(receipt.is_file(), f"missing train receipt for {cell}: {receipt}")
            returncode = terminal_returncode(receipt)
            if returncode is not None:
                terminal_without_checkpoint.append(
                    {"cell": cell, "receipt": str(receipt), "returncode": returncode}
                )
        if terminal_without_checkpoint or failed:
            emit(
                state_path,
                state,
                {
                    "event": "ATTENTION_REQUIRED",
                    "reason": "MILESTONE_REQUIRES_ALL_THREE_CELLS",
                    "step": step,
                    "missing_checkpoints": missing,
                    "terminal_without_checkpoint": terminal_without_checkpoint,
                    "failed_cells": sorted(failed),
                },
            )
            return False
        time.sleep(600)


def wait_for_eval_receipt(
    state_path: Path,
    state: dict,
    *,
    suffix: str,
    step: int,
) -> bool:
    receipt = receipt_path(f"pull_v26_8_eval_step{step}", suffix)
    while not receipt.is_file():
        time.sleep(200)
    while True:
        returncode = terminal_returncode(receipt)
        if returncode is None:
            time.sleep(200)
            continue
        if returncode != 0:
            emit(
                state_path,
                state,
                {
                    "event": "EVAL_PROCESS_FAILURE",
                    "step": step,
                    "receipt": str(receipt),
                    "returncode": returncode,
                },
            )
            return False
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--attempt-suffix")
    args = parser.parse_args()

    train_root = args.run_root.resolve()
    require(train_root.name == "train", f"--run-root must end in train: {train_root}")
    suffix = args.attempt_suffix
    configured_attempt = os.environ.get("PULL_V26_8_ATTEMPT")
    if suffix is None:
        require(configured_attempt is not None, "--attempt-suffix or PULL_V26_8_ATTEMPT is required")
        attempt = int(configured_attempt)
        suffix = suffix_from_attempt(attempt)
    else:
        attempt = attempt_from_suffix(suffix)
        if configured_attempt is not None:
            require(int(configured_attempt) == attempt, "PULL_V26_8_ATTEMPT disagrees with --attempt-suffix")
    expected_run_id = f"pull_v26_8_backbone_20260905{suffix}"
    require(train_root.parent.name == expected_run_id, f"run root does not match attempt suffix: {train_root}")
    eval_root = REPO / "logs_eval/a2_piper_pull_v26_8_backbone" / expected_run_id
    require(train_root.is_dir(), f"missing train root: {train_root}")
    state_path = eval_root / "watch_state.json"
    require(not state_path.exists(), f"watch state already exists: {state_path}")
    state = {
        "schema": "a2_piper_pull_v26_8_wave1_watch_v1",
        "run_root": str(train_root),
        "eval_root": str(eval_root),
        "attempt_suffix": suffix,
        "steps": list(STEPS),
        "completed_steps": [],
        "failed_cells": [],
        "events": [],
    }
    eval_root.mkdir(parents=True, exist_ok=True)
    write_state(state_path, state)

    for step in STEPS:
        if not wait_for_checkpoints(
            state_path,
            state,
            train_root=train_root,
            suffix=suffix,
            step=step,
        ):
            return 2
        launched = command(["milestone-launch", str(step)], attempt)
        if launched.returncode != 0:
            emit(
                state_path,
                state,
                {
                    "event": "ATTENTION_REQUIRED",
                    "reason": "MILESTONE_LAUNCH_FAILED",
                    "step": step,
                    "returncode": launched.returncode,
                    "stdout": launched.stdout,
                    "stderr": launched.stderr,
                },
            )
            return 2
        if not wait_for_eval_receipt(state_path, state, suffix=suffix, step=step):
            return 2
        finalized = command(["milestone-finalize", str(step)], attempt)
        reducer_path = eval_root / "milestones" / f"step{step}" / "reducer.json"
        if finalized.returncode != 0 or not reducer_path.is_file():
            emit(
                state_path,
                state,
                {
                    "event": "ATTENTION_REQUIRED",
                    "reason": "MILESTONE_FINALIZE_FAILED",
                    "step": step,
                    "returncode": finalized.returncode,
                    "reducer": str(reducer_path),
                    "stdout": finalized.stdout,
                    "stderr": finalized.stderr,
                },
            )
            return 2
        reducer = load_json(reducer_path)
        state["completed_steps"].append(step)
        emit(
            state_path,
            state,
            {
                "event": "MILESTONE_REDUCER_READY",
                "step": step,
                "reducer": str(reducer_path),
                "status": reducer.get("status"),
                "route": reducer.get("route"),
                "opening_full_labels": reducer.get("opening_full_labels"),
            },
        )

    finalized_train = command(["train-finalize"], attempt)
    if finalized_train.returncode != 0:
        emit(
            state_path,
            state,
            {
                "event": "ATTENTION_REQUIRED",
                "reason": "TRAIN_FINALIZE_FAILED",
                "returncode": finalized_train.returncode,
                "stdout": finalized_train.stdout,
                "stderr": finalized_train.stderr,
            },
        )
        return 2
    emit(
        state_path,
        state,
        {
            "event": "WAVE1_COMPLETE",
            "steps": list(STEPS),
            "train_finalize_returncode": finalized_train.returncode,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
