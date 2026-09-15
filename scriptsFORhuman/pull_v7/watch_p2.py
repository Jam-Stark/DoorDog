#!/usr/bin/env python3
"""Tmux-resident milestone watcher for the pull-v7 P2 cells.

For each milestone in {9500, 10000, 10500} it waits until every selected cell
has written that checkpoint, runs the exact64 natural evaluation per side, then
runs the P2 mediator reducer.  It never stops, signals or relaunches training:
Main owns the 9500 gate decision and every stop.

GPU placement, from the stage plan §4.3 and the current machine state:
  * GPU0 carries another user's LightNav server and is never used;
  * training peaks are ~18.6 GB for a P_S1-lineage cell and ~16.5 GB for a
    P_S2-lineage cell, natural evaluation peaks ~3.8 GB;
  * milestone evaluation therefore runs only on the designated eval GPU (3,
    next to C_S2) and only after a preflight shows at least 5 GB free;
    otherwise it queues.  Evaluation is never placed next to a P_S1-lineage
    cell.

Run inside tmux session `pull_v7_p2_watch`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_CELL = REPO / "scriptsFORhuman/pull_v7/eval_p2_cell.sh"
REDUCER = REPO / "scriptsFORhuman/pull_v7/analyze_p2.py"
STEPS = (9500, 10000, 10500)
SIDES = ("left", "right")
# Cells whose training peak (~18.6 GB) leaves no room for a 3.8 GB evaluation.
P_S1_LINEAGE = ("T_S1", "C_S1")
EVAL_HEADROOM_MIB = 5 * 1024
CHECKPOINT_POLL_S = 600
HEADROOM_POLL_S = 300


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"PULL_V7_P2_WATCH_INVALID: {message}")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def emit(state_path: Path, state: dict, event: dict) -> None:
    event = {"at": now(), **event}
    state["events"].append(event)
    state["last_event"] = event
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(event, ensure_ascii=False), flush=True)


def free_mib(gpu: int) -> int:
    output = subprocess.check_output(
        ["nvidia-smi", f"--id={gpu}", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
        text=True,
    ).strip().splitlines()[0]
    used, total = (int(value.strip()) for value in output.split(","))
    return total - used


def exit_code(receipt: Path) -> int | None:
    path = receipt.parent / "exit_code.txt"
    return None if not path.is_file() else int(path.read_text(encoding="utf-8").strip())


def checkpoint(train_root: Path, cell: str, step: int) -> Path:
    return train_root / cell / f"model_step_{step:06d}.pt"


def runtime_pass(output: Path) -> bool:
    result = output / "runtime_result.json"
    if not result.is_file():
        return False
    value = json.loads(result.read_text(encoding="utf-8"))
    return value.get("child_returncode") == 0 and value.get("actual_success") is True


def wait_for_checkpoints(state_path: Path, state: dict, *, train_root: Path, receipts: dict[str, Path], step: int) -> bool:
    while True:
        missing = [cell for cell in receipts if not checkpoint(train_root, cell, step).is_file()]
        if not missing:
            return True
        # A cell whose process has already exited will never produce this
        # checkpoint.  Report and leave the milestone to Main rather than
        # comparing T against a control from a different batch.
        exited = {cell: exit_code(receipts[cell]) for cell in missing if exit_code(receipts[cell]) is not None}
        if exited:
            emit(
                state_path,
                state,
                {
                    "event": "ATTENTION_REQUIRED",
                    "reason": "MILESTONE_REQUIRES_ALL_SELECTED_CELLS",
                    "step": step,
                    "missing_checkpoints": missing,
                    "exited_without_checkpoint": exited,
                },
            )
            return False
        time.sleep(CHECKPOINT_POLL_S)


def wait_for_eval_gpu(state_path: Path, state: dict, *, gpu: int, cells: list[str], step: int) -> None:
    require(gpu != 0, "GPU0 carries another user's process and must not be used")
    require(
        not any(cell in P_S1_LINEAGE and state["cell_gpu"].get(cell) == gpu for cell in cells),
        f"evaluation GPU{gpu} hosts a P_S1-lineage training cell",
    )
    queued = False
    while True:
        headroom = free_mib(gpu)
        if headroom >= EVAL_HEADROOM_MIB:
            if queued:
                emit(state_path, state, {"event": "EVAL_GPU_READY", "step": step, "gpu": gpu, "free_mib": headroom})
            return
        if not queued:
            queued = True
            emit(state_path, state, {"event": "EVAL_QUEUED_FOR_HEADROOM", "step": step, "gpu": gpu, "free_mib": headroom, "required_mib": EVAL_HEADROOM_MIB})
        time.sleep(HEADROOM_POLL_S)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--cell", action="append", required=True, help="CELL=GPU of a running training cell")
    parser.add_argument("--train-receipt", action="append", required=True, help="CELL=RECEIPT_PATH")
    parser.add_argument("--eval-gpu", type=int, default=3)
    args = parser.parse_args()

    cell_gpu: dict[str, int] = {}
    for value in args.cell:
        cell, separator, gpu = value.partition("=")
        require(separator == "=" and gpu.isdigit(), f"--cell must be CELL=GPU: {value!r}")
        require(cell not in cell_gpu, f"duplicate cell {cell}")
        cell_gpu[cell] = int(gpu)
    receipts: dict[str, Path] = {}
    for value in args.train_receipt:
        cell, separator, path = value.partition("=")
        require(separator == "=" and path, f"--train-receipt must be CELL=PATH: {value!r}")
        require(cell in cell_gpu and cell not in receipts, f"invalid or duplicate receipt cell {cell}")
        receipts[cell] = Path(path).resolve()
        require(receipts[cell].is_file(), f"missing train receipt {receipts[cell]}")
    require(set(receipts) == set(cell_gpu), "one receipt per selected cell")
    cells = sorted(cell_gpu)
    require(args.train_root.is_dir(), f"missing train root {args.train_root}")

    args.eval_root.mkdir(parents=True, exist_ok=True)
    state_path = args.eval_root / "watch_state.json"
    require(not state_path.exists(), f"watch state already exists: {state_path}")
    state = {
        "schema": "pull_v7_p2_watch_v1",
        "train_root": str(args.train_root.resolve()),
        "eval_root": str(args.eval_root.resolve()),
        "cells": cells,
        "cell_gpu": cell_gpu,
        "train_receipts": {cell: str(path) for cell, path in receipts.items()},
        "eval_gpu": args.eval_gpu,
        "steps": list(STEPS),
        "completed_steps": [],
        "events": [],
    }
    emit(state_path, state, {"event": "WATCH_STARTED", "cells": cells, "eval_gpu": args.eval_gpu})

    for step in STEPS:
        if not wait_for_checkpoints(state_path, state, train_root=args.train_root, receipts=receipts, step=step):
            return 2
        emit(state_path, state, {"event": "MILESTONE_CHECKPOINTS_READY", "step": step})
        milestone_root = args.eval_root / "milestones" / f"step{step}"
        require(not milestone_root.exists(), f"fresh milestone root required: {milestone_root}")
        milestone_root.mkdir(parents=True)
        failed = False
        for cell in cells:
            wait_for_eval_gpu(state_path, state, gpu=args.eval_gpu, cells=cells, step=step)
            result = subprocess.run(
                ["bash", str(EVAL_CELL), str(args.eval_gpu), cell, str(step), str(args.train_root), str(milestone_root)],
                cwd=REPO,
                text=True,
                capture_output=True,
                check=False,
            )
            outputs = [milestone_root / f"{cell}_STEP{step}" / side for side in SIDES]
            if result.returncode != 0 or not all(runtime_pass(output) for output in outputs):
                emit(
                    state_path,
                    state,
                    {
                        "event": "ATTENTION_REQUIRED",
                        "reason": "EVAL_FAILED",
                        "step": step,
                        "cell": cell,
                        "returncode": result.returncode,
                        "stderr_tail": result.stderr[-2000:],
                    },
                )
                failed = True
                break
            emit(state_path, state, {"event": "EVAL_DONE", "step": step, "cell": cell, "outputs": [str(o) for o in outputs]})
        if failed:
            return 2
        reduced = subprocess.run(
            [str(PYTHON), str(REDUCER), "--eval-root", str(milestone_root), "--step", str(step), "--cells", *cells],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = milestone_root / f"P2_MEDIATOR_step{step}.json"
        if reduced.returncode != 0 or not payload.is_file():
            emit(
                state_path,
                state,
                {
                    "event": "ATTENTION_REQUIRED",
                    "reason": "REDUCE_FAILED",
                    "step": step,
                    "returncode": reduced.returncode,
                    "stderr_tail": reduced.stderr[-2000:],
                },
            )
            return 2
        summary = json.loads(payload.read_text(encoding="utf-8"))
        state["completed_steps"].append(step)
        emit(
            state_path,
            state,
            {
                "event": "MILESTONE_REDUCER_READY",
                "step": step,
                "mediator": str(payload),
                "report": str(payload.with_suffix(".md")),
                "overshoot_post_e5_sum_median": {
                    f"{g['cell']}/{g['side']}": g["overshoot_post_e5"]["sum"]["median"] for g in summary["groups"]
                },
                "release_margin_episode_max_median": {
                    f"{g['cell']}/{g['side']}": g["release_margin_episode_max"]["median"] for g in summary["groups"]
                },
                "ready_episodes": {f"{g['cell']}/{g['side']}": g["ready"]["episodes"] for g in summary["groups"]},
                "retention": {f"{g['cell']}/{g['side']}": g["retention"] for g in summary["groups"]},
            },
        )
    emit(state_path, state, {"event": "WATCH_COMPLETE", "steps": list(STEPS)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
