#!/usr/bin/env python3
"""Tmux-resident supervisor for a registered two-cell Wave2 continuation."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
SUPERVISOR = REPO / ".ai/scripts/run_supervisor.py"
CONTINUE_EVAL = REPO / "scriptsFORhuman/pull_v26_8/continue_eval_cell.sh"
CONTINUE_REDUCE = REPO / "scriptsFORhuman/pull_v26_8/continue_reduce.py"
STEPS = (6750, 7500, 8250, 9000)
SIDES = ("left", "right")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load_json(path: Path) -> dict:
    require(path.is_file(), f"missing JSON artifact: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit(path: Path, state: dict, event: dict) -> None:
    state["events"].append(event)
    state["last_event"] = event
    write_state(path, state)
    print(json.dumps(event, ensure_ascii=False), flush=True)


def parse_receipts(values: list[str], cells: tuple[str, str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        cell, separator, raw_path = value.partition("=")
        require(separator == "=" and raw_path, f"--train-receipt must be CELL=PATH: {value!r}")
        require(cell in cells and cell not in parsed, f"invalid or duplicate train receipt cell: {cell!r}")
        parsed[cell] = Path(raw_path).resolve()
    require(set(parsed) == set(cells), "one train receipt is required for each selected cell")
    return parsed


def terminal_returncode(receipt: Path) -> int | None:
    exit_path = receipt.parent / "exit_code.txt"
    if not exit_path.is_file():
        return None
    return int(exit_path.read_text(encoding="utf-8").strip())


def runtime_pass(output: Path) -> bool:
    value = load_json(output / "runtime_result.json")
    return (
        value.get("child_returncode") == 0
        and value.get("wrapper_returncode") == 0
        and value.get("actual_success") is True
    )


def proxy_prefix() -> str:
    values = ["env", "-u", "DISPLAY", "-u", "XAUTHORITY"]
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY"):
        values.append(f"{key}={os.environ.get(key, '')}")
    return shlex.join(values)


def command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=REPO, text=True, capture_output=True, check=False)


def checkpoint_path(train_root: Path, cell: str, step: int) -> Path:
    return train_root / cell / f"model_step_{step:06d}.pt"


def wait_for_checkpoints(
    state_path: Path,
    state: dict,
    *,
    train_root: Path,
    receipts: dict[str, Path],
    step: int,
) -> bool:
    reported = set(state["failed_cells"])
    while True:
        missing = [cell for cell in receipts if not checkpoint_path(train_root, cell, step).is_file()]
        for cell, receipt in receipts.items():
            returncode = terminal_returncode(receipt)
            if returncode is not None and returncode != 0 and cell not in reported:
                reported.add(cell)
                state["failed_cells"] = sorted(reported)
                emit(state_path, state, {"event": "TRAIN_PROCESS_FAILURE", "cell": cell, "receipt": str(receipt), "returncode": returncode})
        terminal_missing = [
            {"cell": cell, "receipt": str(receipts[cell]), "returncode": terminal_returncode(receipts[cell])}
            for cell in missing
            if terminal_returncode(receipts[cell]) is not None
        ]
        if not missing:
            return True
        if terminal_missing or reported:
            emit(
                state_path,
                state,
                {
                    "event": "ATTENTION_REQUIRED",
                    "reason": "WAVE2_MILESTONE_REQUIRES_BOTH_SELECTED_CELLS",
                    "step": step,
                    "missing_checkpoints": missing,
                    "terminal_without_checkpoint": terminal_missing,
                    "failed_cells": sorted(reported),
                },
            )
            return False
        time.sleep(600)


def launch_eval(
    *,
    name: str,
    cells: tuple[str, str],
    step: int,
    train_root: Path,
    milestone_root: Path,
    runtime_log: Path,
) -> Path:
    worker = "set -euo pipefail\n" + "\n".join(
        shlex.join(["bash", str(CONTINUE_EVAL), "0", cell, str(step), str(train_root), str(milestone_root)])
        for cell in cells
    )
    launch_command = f"{proxy_prefix()} bash -lc {shlex.quote(worker)}"
    expected = milestone_root / f"{cells[-1]}_STEP{step}" / "right" / "metrics_eval.json"
    prepared = command([
        str(PYTHON), str(SUPERVISOR), "prepare", "--name", name, "--session", name,
        "--cwd", str(REPO), "--command", launch_command, "--output", str(runtime_log),
        "--checkpoint", str(expected), "--resource", "GPU0", "--resource", "IsaacSim_GPU0",
    ])
    require(prepared.returncode == 0, f"Wave2 eval receipt prepare failed: {prepared.stderr}")
    receipt = Path(prepared.stdout.strip())
    metadata = load_json(receipt)
    metadata["source_lock"] = os.environ["PULL_V26_8_SOURCE_LOCK"]
    metadata["git_revision"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    metadata["stopping_contract"] = "Registered Wave2 full continuation; no seed reruns; exact64 natural protocol required"
    write_state(receipt, metadata)
    launched = command([str(PYTHON), str(SUPERVISOR), "launch", "--receipt", str(receipt)])
    require(launched.returncode == 0, f"Wave2 eval launch failed: {launched.stderr}")
    return receipt


def wait_finalize_eval(receipt: Path) -> bool:
    while True:
        returncode = terminal_returncode(receipt)
        if returncode is None:
            time.sleep(200)
            continue
        if returncode != 0:
            return False
        finalized = command([str(PYTHON), str(SUPERVISOR), "finalize", "--receipt", str(receipt)])
        return finalized.returncode == 0


def finalize_train(receipts: dict[str, Path], train_root: Path) -> bool:
    for cell, receipt in receipts.items():
        finalized = command([str(PYTHON), str(SUPERVISOR), "finalize", "--receipt", str(receipt)])
        if finalized.returncode != 0 or not runtime_pass(train_root / cell):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave1-train-root", type=Path, required=True)
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--cells", nargs=2, required=True)
    parser.add_argument("--train-receipt", action="append", required=True)
    parser.add_argument("--run-prefix", required=True)
    args = parser.parse_args()

    cells = tuple(args.cells)
    require(len(set(cells)) == 2 and all(cell in ("P_S0", "P_S1", "P_S2") for cell in cells), "Wave2 needs two distinct Wave1 cells")
    require(args.train_root.name == "train", "--train-root must end in train")
    require(args.wave1_train_root.name == "train", "--wave1-train-root must end in train")
    require(args.train_root.is_dir() and args.wave1_train_root.is_dir(), "both train roots must exist")
    require(args.run_prefix and "/" not in args.run_prefix, "--run-prefix must be a leaf")
    receipts = parse_receipts(args.train_receipt, cells)
    for receipt in receipts.values():
        require(receipt.is_file(), f"missing train receipt: {receipt}")
    state_path = args.eval_root / "watch_state.json"
    require(not state_path.exists(), f"watch state already exists: {state_path}")
    args.eval_root.mkdir(parents=True, exist_ok=True)
    state = {
        "schema": "a2_piper_pull_v26_8_wave2_watch_v1",
        "wave1_train_root": str(args.wave1_train_root.resolve()),
        "train_root": str(args.train_root.resolve()),
        "eval_root": str(args.eval_root.resolve()),
        "selected_cells": list(cells),
        "steps": list(STEPS),
        "completed_steps": [],
        "failed_cells": [],
        "events": [],
    }
    write_state(state_path, state)

    for step in STEPS:
        if not wait_for_checkpoints(state_path, state, train_root=args.train_root, receipts=receipts, step=step):
            return 2
        milestone_root = args.eval_root / "milestones" / f"step{step}"
        require(not milestone_root.exists(), f"fresh Wave2 milestone root required: {milestone_root}")
        milestone_root.mkdir(parents=True)
        receipt_name = f"{args.run_prefix}_eval_step{step}"
        receipt = launch_eval(
            name=receipt_name,
            cells=cells,
            step=step,
            train_root=args.train_root,
            milestone_root=milestone_root,
            runtime_log=args.eval_root / "runtime_logs" / f"step{step}.log",
        )
        if not wait_finalize_eval(receipt):
            emit(state_path, state, {"event": "EVAL_PROCESS_FAILURE", "step": step, "receipt": str(receipt), "returncode": terminal_returncode(receipt)})
            return 2
        for cell in cells:
            for side in SIDES:
                output = milestone_root / f"{cell}_STEP{step}" / side
                if not runtime_pass(output):
                    emit(state_path, state, {"event": "ATTENTION_REQUIRED", "reason": "EVAL_RUNTIME_RESULT_FAILED", "step": step, "output": str(output)})
                    return 2
        reducer_path = milestone_root / "reducer.json"
        reduced = command([
            str(PYTHON), str(CONTINUE_REDUCE), "--wave1-train-root", str(args.wave1_train_root),
            "--train-root", str(args.train_root), "--eval-root", str(milestone_root), "--step", str(step),
            "--output", str(reducer_path), "--cells", *cells,
        ])
        if reduced.returncode != 0 or not reducer_path.is_file():
            emit(state_path, state, {"event": "ATTENTION_REQUIRED", "reason": "WAVE2_REDUCE_FAILED", "step": step, "returncode": reduced.returncode, "stdout": reduced.stdout, "stderr": reduced.stderr})
            return 2
        reducer = load_json(reducer_path)
        state["completed_steps"].append(step)
        emit(state_path, state, {"event": "MILESTONE_REDUCER_READY", "step": step, "reducer": str(reducer_path), "status": reducer.get("status"), "route": reducer.get("route")})

    if not finalize_train(receipts, args.train_root):
        emit(state_path, state, {"event": "ATTENTION_REQUIRED", "reason": "WAVE2_TRAIN_FINALIZE_FAILED"})
        return 2
    emit(state_path, state, {"event": "WAVE2_COMPLETE", "steps": list(STEPS)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
