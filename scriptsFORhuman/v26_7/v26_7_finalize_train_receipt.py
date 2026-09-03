#!/usr/bin/env python3
"""Finalize an early-success Q05 v26-7 training receipt without changing generic supervision.

This adapter is deliberately restricted to the three Q05 training cells.  It derives an
already-frozen endpoint from contiguous milestone reducers, preserves the prior receipt
as append-only history, replaces only the receipt's full-run checkpoint expectation with
the endpoint checkpoint, and delegates the standard receipt write to run_supervisor.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


RUN_ID = "v26_7_bilateral_native_unlatch_20260902"
CONFIG = "Q05"
CELLS = ("Q05_S0", "Q05_S1", "Q05_S2")
STEPS = (1000, 2000, 3000, 4000, 5000, 6000)
REDUCER_SCHEMA = "a2_piper_base_v26_7_milestone_reducer_v1"
SUPPORTED = "BILATERAL_UNLATCH_SUPPORTED"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fail(message: str) -> None:
    raise SystemExit(f"V26_7_ENDPOINT_FINALIZE_INVALID: {message}")


def endpoint_from_contiguous_reducers(repo: Path) -> tuple[int, list[str]]:
    """Return Q05's first frozen endpoint and the reducers that establish it."""
    milestones = repo / "logs_eval/base_v26" / RUN_ID / "milestones"
    expected_cells = set(CELLS)
    endpoint: dict | None = None
    reducer_paths: list[str] = []

    for step in STEPS:
        path = milestones / f"step{step}" / "reducer.json"
        if not path.is_file():
            if endpoint is None:
                fail(f"missing contiguous reducer before Q05 endpoint: {path}")
            break
        reducer = load_json(path)
        if not (
            reducer.get("schema") == REDUCER_SCHEMA
            and reducer.get("status") == "EXPERIMENT_COMPLETE"
            and reducer.get("step") == step
            and isinstance(reducer.get("config_endpoints"), dict)
            and set(reducer["config_endpoints"]) == {"Q05", "Q20"}
            and isinstance(reducer.get("config_outcomes"), dict)
        ):
            fail(f"invalid reducer contract: {path}")
        reducer_paths.append(str(path))
        candidate = reducer["config_endpoints"][CONFIG]
        if candidate is None:
            if endpoint is not None:
                fail(f"Q05 endpoint disappeared after freeze: {path}")
            continue
        outcomes = candidate.get("per_seed_outcomes") if isinstance(candidate, dict) else None
        if not (
            isinstance(candidate, dict)
            and candidate.get("config") == CONFIG
            and candidate.get("outcome") == SUPPORTED
            and candidate.get("step") in STEPS
            and candidate["step"] <= step
            and isinstance(outcomes, dict)
            and set(outcomes) == expected_cells
            and sum(value == SUPPORTED for value in outcomes.values()) >= 2
            and reducer["config_outcomes"].get(CONFIG) == SUPPORTED
        ):
            fail(f"invalid frozen Q05 endpoint: {path}")
        if endpoint is None:
            if candidate["step"] != step:
                fail(f"Q05 endpoint was not recorded at its first contiguous milestone: {path}")
            endpoint = candidate
        elif candidate != endpoint:
            fail(f"Q05 endpoint changed after freeze: {path}")

    if endpoint is None:
        fail("no frozen Q05 endpoint; full-run receipt remains outside this adapter")
    return int(endpoint["step"]), reducer_paths


def validate_receipt(
    repo: Path, cell: str, receipt_path: Path, endpoint_step: int, session_live: Callable[[str], bool]
) -> tuple[dict, Path, Path]:
    if cell not in CELLS:
        fail(f"only Q05 early-success cells are accepted, got {cell!r}")
    if not receipt_path.is_file():
        fail(f"receipt does not exist: {receipt_path}")
    receipt = load_json(receipt_path)
    expected_name = f"v26_7_train_{cell.lower()}"
    if receipt.get("name") != expected_name or receipt.get("session") != expected_name:
        fail(f"receipt identity does not match {cell}: {receipt_path}")
    if receipt.get("v26_7_endpoint_finalize") is not None:
        fail(f"receipt already has endpoint-finalize evidence: {receipt_path}")
    run = receipt_path.parent
    exit_file = run / "exit_code.txt"
    if not exit_file.is_file() or exit_file.read_text(encoding="utf-8").strip() != "0":
        fail(f"process did not exit zero: {exit_file}")
    if session_live(expected_name):
        fail(f"tmux session still exists: {expected_name}")

    output = repo / "logs_rl/by_batch/base_v26" / RUN_ID / "train" / cell
    expected_full = output / "model_step_006000.pt"
    if receipt.get("cwd") != str(repo.resolve()):
        fail(f"receipt cwd does not match repository: {receipt_path}")
    if Path(receipt.get("checkpoint", "")) != expected_full:
        fail(f"receipt does not preserve the frozen full-run checkpoint expectation: {receipt_path}")
    endpoint_checkpoint = output / f"model_step_{endpoint_step:06d}.pt"
    for step in range(250, endpoint_step + 1, 250):
        checkpoint = output / f"model_step_{step:06d}.pt"
        if not checkpoint.is_file():
            fail(f"missing checkpoint through frozen endpoint: {checkpoint}")
    return receipt, expected_full, endpoint_checkpoint


def append_history(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def finalize(
    repo: Path,
    cell: str,
    receipt_path: Path,
    supervisor: Path,
    runner: Callable[[list[str], Path], None],
    session_live: Callable[[str], bool],
) -> None:
    endpoint_step, reducer_paths = endpoint_from_contiguous_reducers(repo)
    receipt, full_checkpoint, endpoint_checkpoint = validate_receipt(
        repo, cell, receipt_path, endpoint_step, session_live
    )
    if not supervisor.is_file():
        fail(f"standard supervisor is missing: {supervisor}")

    history_path = receipt_path.parent / "RUN_RECEIPT_HISTORY.jsonl"
    append_history(
        history_path,
        {
            "schema": "v26_7_endpoint_receipt_history_v1",
            "event": "before_endpoint_finalize",
            "recorded_at": now(),
            "cell": cell,
            "endpoint_step": endpoint_step,
            "startup_checkpoint_expectation": str(full_checkpoint),
            "endpoint_checkpoint_expectation": str(endpoint_checkpoint),
            "receipt_preimage": receipt,
        },
    )
    receipt["checkpoint"] = str(endpoint_checkpoint)
    receipt["v26_7_endpoint_finalize"] = {
        "schema": "v26_7_endpoint_finalize_v1",
        "cell": cell,
        "endpoint_step": endpoint_step,
        "startup_checkpoint_expectation": str(full_checkpoint),
        "endpoint_checkpoint_expectation": str(endpoint_checkpoint),
        "reducer_paths": reducer_paths,
        "history": str(history_path),
    }
    save_json(receipt_path, receipt)
    runner(["python3", str(supervisor), "finalize", "--receipt", str(receipt_path)], repo)
    finalized = load_json(receipt_path)
    if finalized.get("state") != "PASS" or finalized.get("process_returncode") != 0:
        fail(f"standard supervisor did not PASS endpoint receipt: {receipt_path}")
    append_history(
        history_path,
        {
            "schema": "v26_7_endpoint_receipt_history_v1",
            "event": "after_endpoint_finalize",
            "recorded_at": now(),
            "cell": cell,
            "endpoint_step": endpoint_step,
            "receipt_after": finalized,
        },
    )


def actual_runner(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def actual_session_live(session: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True, check=False)
    if result.returncode not in (0, 1):
        fail(f"tmux has-session returned {result.returncode} for {session}")
    return result.returncode == 0


def self_test() -> None:
    """Exercise the adapter using a temporary reducer/receipt fixture and fake finalizer."""
    with tempfile.TemporaryDirectory(prefix="v26_7_receipt_finalize_") as temporary:
        repo = Path(temporary)
        supervisor = repo / ".ai/scripts/run_supervisor.py"
        supervisor.parent.mkdir(parents=True)
        supervisor.write_text("# fixture finalizer\n", encoding="utf-8")
        milestones = repo / "logs_eval/base_v26" / RUN_ID / "milestones"

        def reducer(step: int, endpoint: dict | None) -> None:
            path = milestones / f"step{step}" / "reducer.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            save_json(
                path,
                {
                    "schema": REDUCER_SCHEMA,
                    "status": "EXPERIMENT_COMPLETE",
                    "step": step,
                    "config_endpoints": {"Q05": endpoint, "Q20": None},
                    "config_outcomes": {"Q05": SUPPORTED if endpoint else "MILESTONE_CONTINUE", "Q20": "MILESTONE_CONTINUE"},
                },
            )

        endpoint = {
            "config": "Q05",
            "step": 3000,
            "outcome": SUPPORTED,
            "per_seed_outcomes": {"Q05_S0": "LEFT_STILL_STRUCTURALLY_ZERO", "Q05_S1": SUPPORTED, "Q05_S2": SUPPORTED},
        }
        reducer(1000, None); reducer(2000, None); reducer(3000, endpoint)

        def fixture_receipt(cell: str) -> Path:
            run = repo / ".ai/runtime/runs" / f"v26_7_train_{cell.lower()}"
            run.mkdir(parents=True)
            (run / "exit_code.txt").write_text("0\n", encoding="utf-8")
            output = repo / "logs_rl/by_batch/base_v26" / RUN_ID / "train" / cell
            output.mkdir(parents=True)
            for step in range(250, 3001, 250):
                (output / f"model_step_{step:06d}.pt").touch()
            receipt_path = run / "RUN_RECEIPT.json"
            save_json(
                receipt_path,
                {
                    "name": f"v26_7_train_{cell.lower()}", "session": f"v26_7_train_{cell.lower()}",
                    "cwd": str(repo.resolve()), "checkpoint": str(output / "model_step_006000.pt"),
                    "state": "FAIL", "summary": "expected checkpoint missing", "finalized_at": "fixture-time",
                },
            )
            return receipt_path

        def fixture_runner(command: list[str], cwd: Path) -> None:
            receipt_path = Path(command[-1]); value = load_json(receipt_path)
            value.update({"state": "PASS", "process_returncode": 0, "summary": "fixture pass", "finalized_at": "fixture-final"})
            save_json(receipt_path, value)

        receipt_path = fixture_receipt("Q05_S0")
        finalize(repo, "Q05_S0", receipt_path, supervisor, fixture_runner, lambda _: False)
        passed = load_json(receipt_path)
        assert passed["state"] == "PASS"
        assert passed["checkpoint"].endswith("model_step_003000.pt")
        history = (receipt_path.parent / "RUN_RECEIPT_HISTORY.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(history) == 2 and "model_step_006000.pt" in history[0] and "fixture-time" in history[0]

        missing_receipt = fixture_receipt("Q05_S1")
        missing = repo / "logs_rl/by_batch/base_v26" / RUN_ID / "train/Q05_S1/model_step_002750.pt"
        missing.unlink()
        q20_receipt = fixture_receipt("Q05_S2")
        for label, action in (
            ("no_endpoint", lambda: endpoint_from_contiguous_reducers(repo.parent)),
            ("missing_checkpoint", lambda: finalize(repo, "Q05_S1", missing_receipt, supervisor, fixture_runner, lambda _: False)),
            ("q20_rejected", lambda: finalize(repo, "Q20_S0", q20_receipt, supervisor, fixture_runner, lambda _: False)),
        ):
            try:
                action()
            except SystemExit:
                continue
            raise AssertionError(f"fixture should fail fast: {label}")
    print("SELF_TEST_PASS: endpoint PASS; no-endpoint/missing-checkpoint/Q20 reject; history retained")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--cell", choices=CELLS)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--supervisor", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        if args.cell is not None or args.receipt is not None or args.supervisor is not None:
            parser.error("--self-test does not accept receipt arguments")
        self_test()
        return 0
    if args.cell is None:
        parser.error("--cell is required unless --self-test is used")
    repo = args.repo.resolve()
    receipt = args.receipt or repo / ".ai/runtime/runs" / f"v26_7_train_{args.cell.lower()}" / "RUN_RECEIPT.json"
    supervisor = args.supervisor or repo / ".ai/scripts/run_supervisor.py"
    finalize(repo, args.cell, receipt, supervisor, actual_runner, actual_session_live)
    print(f"PASS: endpoint-aware receipt finalized for {args.cell}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
