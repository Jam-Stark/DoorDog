#!/usr/bin/env python3
"""v28 registered scheduler entrypoints; execution is delegated to run_supervisor."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v28_contract import EVAL_SEEDS, PYTHON, ROOT, RUNTIME, RUN_ID, SIDES, cells, require


SUPERVISOR = ROOT / ".ai/scripts/run_supervisor.py"
HERE = Path(__file__).resolve().parent
EXECUTION_NAME = "execution_20260913"
SCHEMA = "a2_piper_base_v28_scheduler_v1"
BUDGET_CAP = 36500
GPU_FREE_MIB = 20 * 1024
GPU_WAIT_SECONDS = 12 * 60 * 60
PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new_json(path: Path, value: Any) -> None:
    require(not path.exists(), f"refusing to overwrite immutable artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_state(path: Path, value: dict[str, Any]) -> None:
    value["updated_at"] = utc_now()
    write_canonical_json(path, value)


def write_canonical_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def execution_root(raw: Path | None = None) -> Path:
    return (raw or (RUNTIME / EXECUTION_NAME)).resolve()


def state_path(root: Path) -> Path:
    return root / "state.json"


def g0_passed() -> None:
    gate = read_json(RUNTIME / "g0_decision.json")
    require(gate.get("active_gate") is None and gate.get("stopped_at") is None, "G0 is not an active passed gate")
    require(gate.get("git_commit_performed") is True, "G0 completion receipt missing")


def cell_output(root: Path, task_id: str, attempt: int) -> Path:
    return root / "attempts" / task_id / f"attempt{attempt}"


def add_task(state: dict[str, Any], root: Path, *, task_id: str, kind: str, cell: str,
             batches: int = 0, step: int | None = None, checkpoint: str | None = None,
             side: str | None = None, eval_kind: str | None = None, seed: int | None = None,
             resume: str | None = None, total_batches: int | None = None) -> dict[str, Any]:
    require(task_id not in state["tasks"], f"duplicate task {task_id}")
    budget = state["budget"]
    projected = budget["actual_consumed_batches"] + budget["active_reserved_batches"] + budget["scheduled_batches"] + batches
    require(projected <= BUDGET_CAP, f"v28 budget {projected}>{BUDGET_CAP}")
    task = {
        "id": task_id, "kind": kind, "cell": cell, "batches": batches, "step": step,
        "checkpoint": checkpoint, "side": side, "eval_kind": eval_kind, "seed": seed,
        "resume": resume, "total_batches": total_batches, "attempt": 1,
        "output": str(cell_output(root, task_id, 1)), "status": "PENDING_GPU",
        "created_at": utc_now(), "receipt": None, "source_lock": state["source_lock"],
        "proxy_environment": state["proxy_environment"],
        "pending_deadline_epoch": time.time() + GPU_WAIT_SECONDS,
    }
    state["tasks"][task_id] = task
    budget["scheduled_batches"] += batches
    deadlines = [row["pending_deadline_epoch"] for row in state["tasks"].values() if row["status"] == "PENDING_GPU"]
    if deadlines:
        state["next_decision_epoch"] = min(deadlines)
        state["next_decision_reason"] = "12h pending-GPU decision"
    return task


def validate_gpu_assignment(allowed_gpus: list[int], training_gpus: list[int]) -> tuple[list[int], list[int]]:
    require(allowed_gpus, "at least one allowed GPU is required")
    require(len(set(allowed_gpus)) == len(allowed_gpus), "allowed GPUs must be unique")
    require(training_gpus, "at least one training GPU is required")
    require(len(set(training_gpus)) == len(training_gpus), "training GPUs must be unique")
    require(set(training_gpus).issubset(allowed_gpus), "training GPUs must be allowed GPUs")
    return allowed_gpus, training_gpus


def initial_manifest(root: Path, source_lock: Path, allowed_gpus: list[int], training_gpus: list[int]) -> dict[str, Any]:
    declared_cells = cells()
    return {
        "schema": "a2_piper_base_v28_initial_manifest_v1", "run_id": RUN_ID,
        "execution_root": str(root), "source_lock": str(source_lock.resolve()), "evaluation_contract": {
            "milestone": {"episodes_per_side": 64, "seed": EVAL_SEEDS["milestone"], "order": ["left", "right"]},
            "DEV": {"episodes_per_side": 128, "seed": EVAL_SEEDS["DEV"], "order": ["left", "right"]},
            "CONF": {"episodes_per_side": 128, "seed": EVAL_SEEDS["CONF"], "order": ["left", "right"]},
            "render": {"episodes_per_side": 3, "seed": EVAL_SEEDS["render"], "episode_ids": [0, 1, 2]},
        },
        "cells": {name: {key: value for key, value in spec.items() if key != "checkpoint"} |
                  {"source_checkpoint": spec["checkpoint"]} for name, spec in declared_cells.items()},
        "selection": {"max_candidates": 2, "max_exact128_lanes": 8,
                      "order": ["primary_DEV", "primary_CONF", "reserve_DEV", "reserve_CONF"]},
        "budget_cap_batches": BUDGET_CAP,
        "allowed_gpus": allowed_gpus,
        "training_gpus": training_gpus,
    }


def initialize(root: Path, *, source_lock: Path, allowed_gpus: list[int], training_gpus: list[int],
               deadline_epoch: float | None = None) -> Path:
    g0_passed()
    require(not state_path(root).exists() and not (root / "initial_manifest.json").exists(),
            f"scheduler state already initialized: {root}")
    require(source_lock.is_file(), f"source lock missing: {source_lock}")
    allowed_gpus, training_gpus = validate_gpu_assignment(allowed_gpus, training_gpus)
    now = time.time()
    deadline = deadline_epoch if deadline_epoch is not None else now + GPU_WAIT_SECONDS
    require(deadline > now, "next decision deadline must be in the future")
    root.mkdir(parents=True, exist_ok=True)
    write_new_json(root / "initial_manifest.json", initial_manifest(root, source_lock, allowed_gpus, training_gpus))
    state: dict[str, Any] = {
        "schema": SCHEMA, "run_id": RUN_ID, "created_at": utc_now(), "source_lock": str(source_lock.resolve()),
        "next_decision_epoch": deadline, "next_decision_reason": "GPU capacity or 12h pending-GPU decision",
        "budget": {"cap_batches": BUDGET_CAP, "scheduled_batches": 0, "active_reserved_batches": 0,
                   "actual_consumed_batches": 0},
        "proxy_environment": {key: os.environ.get(key, "") for key in PROXY_KEYS},
        "allowed_gpus": allowed_gpus, "training_gpus": training_gpus,
        "tasks": {}, "reducers": {}, "wave_a": {"status": "NOT_STARTED", "history": [], "endpoint_lock": None},
        "g1": {"status": "NOT_STARTED", "decision": None}, "wave_b": {"status": "NOT_STARTED", "exact128_lanes": 0},
        "gpu_observations": [], "notifications": [], "stop": None,
        "commit_milestones": {"wave_a_step1000_aggregate": "PENDING", "wave_a_endpoint_lock": "PENDING",
                              "final_closure": "PENDING"},
    }
    add_task(state, root, task_id="g1_train_500", kind="train", cell="G1_WARM", batches=500, step=500)
    write_state(state_path(root), state)
    return state_path(root)


def archive_resume_stop(root: Path, state: dict[str, Any], owner_decision: dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = root / "archives" / f"resume_wave_a_{stamp}"
    write_new_json(archive / "state_before_resume.json", state)
    for wave in ("wave_a", "wave_b"):
        source = root.parent / f"{wave}_decision.json"
        require(source.is_file(), f"canonical {wave} decision missing: {source}")
        write_new_json(archive / f"{wave}_decision_before_resume.json", read_json(source))
    write_new_json(archive / "owner_decision.json", owner_decision)
    return archive


def resume_wave_a(root: Path, *, source_lock: Path, owner_decision_path: Path,
                  allowed_gpus: list[int], training_gpus: list[int]) -> None:
    path = state_path(root)
    require(path.is_file(), f"scheduler state missing: {path}")
    require(source_lock.is_file(), f"resume source lock missing: {source_lock}")
    require(owner_decision_path.is_file(), f"owner decision missing: {owner_decision_path}")
    allowed_gpus, training_gpus = validate_gpu_assignment(allowed_gpus, training_gpus)
    state = read_json(path)
    require(state.get("schema") == SCHEMA, "scheduler state schema")
    require(state["stop"] is not None and state["stop"].get("reason") == "G1_WARM_FAIL",
            "resume-wave-a requires the recorded G1_WARM_FAIL stop")
    require(not any(task["status"] in {"PENDING_GPU", "LAUNCHED"} for task in state["tasks"].values()),
            "resume-wave-a requires a terminal scheduler state")
    require(state["g1"]["status"] == "FAIL", "resume-wave-a preserves the recorded G1 FAIL")
    require(state["budget"]["actual_consumed_batches"] == 500, "resume-wave-a requires the recorded 500-batch cost")
    require(Path(state["source_lock"]).resolve() != source_lock.resolve(),
            "resume-wave-a requires a new source-lock snapshot")
    owner = read_json(owner_decision_path)
    require(owner.get("status") == "ACCEPTED" and owner.get("action") == "RESUME_SCRATCH_WAVE_A",
            "owner decision does not authorize Wave A scratch resume")
    require(owner.get("authorized_cells") == ["A_S281", "A_S282", "A_S283"],
            "owner decision must authorize only the original three Wave A seeds")
    require(owner.get("batches_per_cell") == 6000 and owner.get("prior_consumed_batches") == 500,
            "owner decision does not preserve the registered Wave A budget")
    require(owner.get("allowed_gpus") == allowed_gpus and owner.get("training_gpus") == training_gpus,
            "CLI GPU allocation must match the owner decision")
    require(owner.get("preserved_g1_status") == "FAIL" and owner.get("warm_arm_cancelled") is True,
            "owner decision must preserve G1 FAIL and the warm-arm cancellation")
    archive = archive_resume_stop(root, state, owner)
    prior_closure = root / "closure_receipt.json"
    require(prior_closure.is_file(), f"prior closure receipt missing: {prior_closure}")
    archived_closure = archive / "closure_receipt_before_resume.json"
    write_new_json(archived_closure, read_json(prior_closure))
    state["historical_stop"] = state["stop"]
    state["stop"] = None
    state["source_lock"] = str(source_lock.resolve())
    state["allowed_gpus"] = allowed_gpus
    state["training_gpus"] = training_gpus
    state["resume_wave_a"] = {
        "at": utc_now(), "owner_decision": str(owner_decision_path.resolve()),
        "decision_log_id": owner.get("decision_log_id"), "archive": str(archive),
        "prior_closure_reference": str(archived_closure),
    }
    state["wave_a"] = {"status": "ACTIVE", "history": [], "endpoint_lock": None,
                       "warm_arm_cancelled": True, "resume_authority": str(owner_decision_path.resolve())}
    state["wave_b"] = {"status": "NOT_STARTED", "exact128_lanes": 0}
    state["commit_milestones"] = {
        "wave_a_step1000_aggregate": "PENDING", "wave_a_endpoint_lock": "PENDING",
        "final_closure": "PENDING", "prior_final_closure_reference": str(archived_closure),
    }
    for seed in (281, 282, 283):
        add_task(state, root, task_id=f"wave_a_s{seed}", kind="train", cell=f"A_S{seed}",
                 batches=6000, step=6000)
    write_state(path, state)
    for wave in ("wave_a", "wave_b"):
        write_canonical_json(root.parent / f"{wave}_decision.json", {
            "schema": f"a2_piper_base_v28_{wave}_decision_v1", "run_id": RUN_ID,
            "status": state[wave]["status"], "outcome": "IN_PROGRESS" if wave == "wave_a" else "PREREQUISITE_PENDING",
            "source_state": str(path), "source_lock": state["source_lock"], "endpoint_lock": None,
            "route_authority": str(owner_decision_path.resolve()), "decision_log_id": owner["decision_log_id"],
            "prior_stop_decision": str(archive / f"{wave}_decision_before_resume.json"),
        })


def task_command(task: dict[str, Any]) -> tuple[list[str], Path, int, Path | None]:
    output = Path(task["output"])
    if task["kind"] == "train":
        command = [PYTHON, "-B", str(HERE / "v28_run_cell.py"), "train", "--gpu", "{gpu}",
                   "--output", str(output), "--cell", task["cell"]]
        if task["resume"]:
            command += ["--resume", task["resume"], "--total-batches", str(task["total_batches"])]
        expected = 12600 if task["cell"] == "G1_WARM" else 165600
        checkpoint = output / f"model_step_{task['step']:06d}.pt"
        return command, output, expected, checkpoint
    if task["kind"] == "eval":
        command = [PYTHON, "-B", str(HERE / "v28_run_cell.py"), "eval", "--gpu", "{gpu}",
                   "--output", str(output), "--cell", task["cell"], "--checkpoint", task["checkpoint"],
                   "--side", task["side"], "--episodes", str(task["episodes"]), "--seed", str(task["seed"]),
                   "--stratum", task["eval_kind"]]
        return command, output, 900, None
    if task["kind"] == "render":
        command = [PYTHON, "-B", str(HERE / "v28_render.py"), "--gpu", "{gpu}", "--output", str(output),
                   "--endpoint-lock", task["endpoint_lock"], "--candidate-index", str(task["candidate_index"]),
                   "--side", task["side"]]
        return command, output, 900, None
    raise ValueError(f"unknown task kind {task['kind']}")


def supervisor_prepare(task: dict[str, Any], gpu: int) -> str:
    command, output, expected, checkpoint = task_command(task)
    command = [str(gpu) if item == "{gpu}" else item for item in command]
    command = ["env", *[f"{key}={value}" for key, value in task["proxy_environment"].items()], *command]
    name = f"v28_{task['id']}_a{task['attempt']}"
    receipt = ROOT / ".ai/runtime/runs" / name / "RUN_RECEIPT.json"
    scheduler_log = Path(task["output"]).parent / "supervisor_logs" / f"attempt{task['attempt']}.log"
    args = [sys.executable, str(SUPERVISOR), "prepare", "--name", name, "--session", name,
            "--cwd", str(ROOT), "--command", shlex.join(command), "--output", str(scheduler_log),
            "--resource", f"GPU{gpu}", "--resource", f"IsaacSim_GPU{gpu}",
            "--expected-seconds", str(expected), "--eta-source", "v28 plan section 10",
            "--stop-condition", "registered v28 task completion or explicit supervisor cancellation",
            "--config-ref", f"v28:{task['cell']}:{task['source_lock']}", "--checkpoint-lineage",
            str(task["resume"] or task["checkpoint"] or cells()[task["cell"]]["checkpoint"] or "scratch"),
            "--source-revision", f"source-lock:{task['source_lock']}"]
    if checkpoint is not None:
        args += ["--checkpoint", str(checkpoint)]
    subprocess.run(args, cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(SUPERVISOR), "launch", "--receipt", str(receipt), "--backend", "tmux"], cwd=ROOT, check=True)
    return str(receipt)


def launch_watcher(root: Path) -> str:
    state = read_json(state_path(root))
    prior = state.get("watcher_receipt")
    if prior:
        prior_status = subprocess.run([sys.executable, str(SUPERVISOR), "status", "--receipt", prior], cwd=ROOT,
                                      check=True, text=True, capture_output=True)
        if json.loads(prior_status.stdout)["process_state"] in {"DECLARED", "LAUNCHING", "RUNNING"}:
            return prior
    attempt = state.get("watcher_attempt", 0) + 1
    name = "v28_execution_20260913_watcher" if attempt == 1 else f"v28_execution_20260913_watcher_a{attempt}"
    receipt = ROOT / ".ai/runtime/runs" / name / "RUN_RECEIPT.json"
    command = [PYTHON, "-B", str(HERE / "v28_watch_wave.py"), "--state", str(state_path(root))]
    command = ["env", *[f"{key}={value}" for key, value in state["proxy_environment"].items()], *command]
    subprocess.run([sys.executable, str(SUPERVISOR), "prepare", "--name", name, "--session", name,
                    "--cwd", str(ROOT), "--command", shlex.join(command),
                    "--output", str(root / f"watcher_a{attempt}.log"),
                    "--expected-seconds", str(max(1, int(state["next_decision_epoch"] - time.time()))),
                    "--eta-source", "fixed 12h GPU-pending decision point", "--stop-condition", "next_decision_epoch",
                    "--config-ref", f"v28 scheduler:{state['source_lock']}", "--checkpoint-lineage", "none",
                    "--source-revision", f"source-lock:{state['source_lock']}"], cwd=ROOT, check=True)
    state["watcher_receipt"] = str(receipt)
    state["watcher_attempt"] = attempt
    write_state(state_path(root), state)
    subprocess.run([sys.executable, str(SUPERVISOR), "launch", "--receipt", str(receipt), "--backend", "tmux"], cwd=ROOT, check=True)
    return str(receipt)


def resume_infra(root: Path, task_id: str, reason: str, source_lock: Path | None = None) -> None:
    path = state_path(root)
    state = read_json(path)
    if state.get("watcher_receipt"):
        status = read_json(Path(state["watcher_receipt"]).with_name("STATUS.json"))
        require(status["process_state"] not in {"DECLARED", "LAUNCHING", "RUNNING"},
                "quiesce the watcher before changing its state; detached training jobs remain separate")
    task = state["tasks"].get(task_id)
    require(task is not None and task["status"] == "NEEDS_INFRA_REPAIR", f"task is not awaiting infra repair: {task_id}")
    require(task["attempt"] < 3, f"pre-policy retry limit reached for {task_id}")
    budget = state["budget"]
    projected = budget["actual_consumed_batches"] + budget["active_reserved_batches"] + budget["scheduled_batches"] + task["batches"]
    require(projected <= BUDGET_CAP, f"repair retry exceeds v28 budget {projected}>{BUDGET_CAP}")
    task.setdefault("prior_attempts", []).append({key: task.get(key) for key in
                                                ("attempt", "output", "receipt", "status", "source_lock", "actual_batches")})
    if source_lock is not None:
        require(source_lock.is_file(), f"repair source lock missing: {source_lock}")
        state["source_lock"] = str(source_lock.resolve())
        for pending in state["tasks"].values():
            if pending["status"] in {"PENDING_GPU", "NEEDS_INFRA_REPAIR"}:
                pending["source_lock"] = state["source_lock"]
    budget["scheduled_batches"] += task["batches"]
    task["attempt"] += 1
    task["output"] = str(cell_output(root, task_id, task["attempt"]))
    for key in ("completed_at", "supervisor_status", "actual_batches", "launched_at", "pending_gpu_notified_at"):
        task.pop(key, None)
    task.update(status="PENDING_GPU", receipt=None, gpu=None, repaired_reason=reason, repaired_at=utc_now(),
                pending_deadline_epoch=time.time() + GPU_WAIT_SECONDS)
    state["next_decision_epoch"] = task["pending_deadline_epoch"]
    state["next_decision_reason"] = "12h pending-GPU decision after recorded infrastructure repair"
    write_state(path, state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--execution-root", type=Path)
    init.add_argument("--source-lock", type=Path, required=True)
    init.add_argument("--gpus", type=int, nargs="+", required=True)
    init.add_argument("--train-gpus", type=int, nargs="+", required=True)
    init.add_argument("--deadline-epoch", type=float)
    start = sub.add_parser("start-watcher")
    start.add_argument("--execution-root", type=Path)
    retry = sub.add_parser("resume-infra")
    retry.add_argument("--execution-root", type=Path)
    retry.add_argument("--task", required=True)
    retry.add_argument("--reason", required=True)
    retry.add_argument("--source-lock", type=Path)
    resume = sub.add_parser("resume-wave-a")
    resume.add_argument("--root", type=Path, required=True)
    resume.add_argument("--source-lock", type=Path, required=True)
    resume.add_argument("--owner-decision", type=Path, required=True)
    resume.add_argument("--gpus", type=int, nargs="+", required=True)
    resume.add_argument("--train-gpus", type=int, nargs="+", required=True)
    args = parser.parse_args()
    if args.command == "init":
        root = execution_root(args.execution_root)
        print(initialize(root, source_lock=args.source_lock, allowed_gpus=args.gpus,
                         training_gpus=args.train_gpus, deadline_epoch=args.deadline_epoch))
    elif args.command == "start-watcher":
        root = execution_root(args.execution_root)
        print(launch_watcher(root))
    elif args.command == "resume-infra":
        root = execution_root(args.execution_root)
        resume_infra(root, args.task, args.reason, args.source_lock)
    else:
        resume_wave_a(args.root.resolve(), source_lock=args.source_lock, owner_decision_path=args.owner_decision,
                      allowed_gpus=args.gpus, training_gpus=args.train_gpus)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
