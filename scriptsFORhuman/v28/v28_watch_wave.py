#!/usr/bin/env python3
"""OS-side v28 scheduler. It observes receipts and GPU capacity; it never guesses policy results."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v28_contract import EVAL_SEEDS, HERE, PYTHON, ROOT, SIDES, cells, require
from v28_orchestrate import (BUDGET_CAP, GPU_FREE_MIB, SCHEMA, add_task, read_json, state_path,
                             supervisor_prepare, task_command, utc_now, write_canonical_json, write_new_json, write_state)


POLL_SECONDS = 60
SUPERVISOR = ROOT / ".ai/scripts/run_supervisor.py"


def reducer_module():
    spec = importlib.util.spec_from_file_location("v28_reduce_scheduler", HERE / "v28_reduce.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v28 reducer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gpu_snapshot() -> dict[str, Any]:
    query = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.free", "--format=csv,noheader,nounits"],
                           check=True, text=True, capture_output=True)
    apps = subprocess.run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name",
                           "--format=csv,noheader,nounits"], check=True, text=True, capture_output=True)
    by_uuid: dict[str, list[dict[str, str]]] = {}
    for line in apps.stdout.splitlines():
        if not line.strip() or line.strip() == "No running processes found":
            continue
        uuid, pid, process = [part.strip() for part in line.split(",", 2)]
        by_uuid.setdefault(uuid, []).append({"pid": pid, "process": process})
    uuid_query = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"],
                                check=True, text=True, capture_output=True)
    uuids = {line.split(",", 1)[0].strip(): line.split(",", 1)[1].strip() for line in uuid_query.stdout.splitlines()}
    rows = []
    for line in query.stdout.splitlines():
        index, free = [part.strip() for part in line.split(",", 1)]
        processes = by_uuid.get(uuids[index], [])
        rows.append({"gpu": int(index), "free_mib": int(free), "compute_processes": processes,
                     "eligible": int(free) >= GPU_FREE_MIB and not processes})
    return {"observed_at": utc_now(), "minimum_free_mib": GPU_FREE_MIB, "gpus": rows}


def append_gpu_observation(state: dict[str, Any], root: Path) -> list[int]:
    snapshot = gpu_snapshot()
    sequence = len(state["gpu_observations"])
    path = root / "gpu_occupancy" / f"{sequence:04d}.json"
    write_new_json(path, snapshot)
    state["gpu_observations"].append(str(path))
    launched = {task["gpu"] for task in state["tasks"].values()
                if task["status"] == "LAUNCHED" and task.get("gpu") is not None}
    return [row["gpu"] for row in snapshot["gpus"] if row["eligible"] and row["gpu"] not in launched]


def supervisor_status(receipt: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(SUPERVISOR), "status", "--receipt", receipt], cwd=ROOT,
                            check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def process_receipt(task: dict[str, Any]) -> dict[str, Any] | None:
    path = Path(task["output"]) / "process_receipt.json"
    return read_json(path) if path.is_file() else None


def consumed_batches(task: dict[str, Any], process: dict[str, Any] | None, completed: bool) -> int:
    if completed:
        return task["batches"]
    if process is None:
        return 0
    start = process.get("start_global_step")
    last = process.get("last_iteration")
    if isinstance(start, int) and isinstance(last, int):
        count = last - start
        require(0 <= count <= task["batches"], "observed batch counter outside registered invocation")
        return count
    return 0


def release_active_budget(state: dict[str, Any], task: dict[str, Any], process: dict[str, Any] | None, completed: bool) -> None:
    if task["batches"] == 0:
        return
    budget = state["budget"]
    budget["active_reserved_batches"] -= task["batches"]
    require(budget["active_reserved_batches"] >= 0, "negative active reservation")
    actual = consumed_batches(task, process, completed)
    budget["actual_consumed_batches"] += actual
    task["actual_batches"] = actual


def synchronize_tasks(state: dict[str, Any], root: Path) -> None:
    for task in state["tasks"].values():
        if task["status"] != "LAUNCHED":
            continue
        status = supervisor_status(task["receipt"])
        if status["process_state"] not in {"PROCESS_COMPLETED", "PROCESS_FAILED", "CANCELLED", "LAUNCH_FAILED"}:
            continue
        process = process_receipt(task)
        if status["process_state"] == "PROCESS_COMPLETED":
            release_active_budget(state, task, process, completed=True)
            task.update(status="COMPLETE", completed_at=utc_now(), supervisor_status=status)
            continue
        release_active_budget(state, task, process, completed=False)
        policy_observed = bool(process and process.get("policy_readout_observed"))
        if task.get("render_budget_cancelled"):
            task.update(status="NOT_COMPLETED_RENDER_BUDGET", completed_at=utc_now(), supervisor_status=status)
        elif not policy_observed and task["attempt"] == 3:
            task.update(status="STOPPED_INFRA_ATTEMPTS_EXHAUSTED", completed_at=utc_now(), supervisor_status=status)
            if task["cell"] == "G1_WARM":
                state["stop"] = {"reason": "G1_INFRA_ATTEMPTS_EXHAUSTED", "task": task["id"], "at": utc_now()}
        elif not policy_observed:
            task.update(status="NEEDS_INFRA_REPAIR", completed_at=utc_now(), supervisor_status=status,
                        repair_receipt=task["receipt"], repair_reason=status["process_state"])
            state["notifications"].append({"kind": "INFRA_REPAIR_REQUIRED", "task": task["id"],
                                           "receipt": task["receipt"], "attempt": task["attempt"]})
        elif task["kind"] == "eval":
            task.update(status="INVALID", completed_at=utc_now(), supervisor_status=status,
                        invalid_reason="evaluation process failure after policy readout")
        else:
            task.update(status="STOPPED_POLICY_READOUT", completed_at=utc_now(), supervisor_status=status)
            if task["cell"] == "G1_WARM":
                state["stop"] = {"reason": "G1_POLICY_READOUT_FAILURE", "task": task["id"], "at": utc_now()}


def enforce_render_budget(state: dict[str, Any]) -> None:
    for task in state["tasks"].values():
        if task["kind"] != "render" or task["status"] != "LAUNCHED" or task.get("render_budget_cancelled"):
            continue
        if time.time() >= task["render_deadline_epoch"]:
            subprocess.run([sys.executable, str(SUPERVISOR), "cancel", "--receipt", task["receipt"],
                            "--reason", "Registered v28 render allowance: at most 900 seconds per fixed lane"],
                           cwd=ROOT, check=True)
            task["render_budget_cancelled"] = True


def checkpoint_for(task: dict[str, Any]) -> Path:
    _, _, _, checkpoint = task_command(task)
    require(checkpoint is not None, f"task {task['id']} has no training checkpoint")
    return checkpoint


def checkpoint_ready(task: dict[str, Any], step: int) -> bool:
    output = Path(task["output"])
    checkpoint = output / f"model_step_{step:06d}.pt"
    if not checkpoint.is_file() or not (output / "config.yaml").is_file():
        return False
    if task["status"] == "COMPLETE":
        receipt = process_receipt(task)
        return receipt is not None and receipt.get("state") == "PASS"
    log = output / "runtime.log"
    if not log.is_file():
        return False
    iterations = [int(value) for value in re.findall(r"Learning iteration\s+(\d+)", log.read_text(errors="replace"))]
    return bool(iterations) and max(iterations) > step


def add_eval_group(state: dict[str, Any], root: Path, *, group: str, cell: str, step: int,
                   checkpoint: Path, episodes: int, eval_kind: str, seed: int) -> None:
    require(episodes in (64, 128), "exact eval population")
    for side in SIDES:
        task_id = f"eval_{group}_{cell.lower()}_{side}"
        if task_id in state["tasks"]:
            continue
        add_task(state, root, task_id=task_id, kind="eval", cell=cell, step=step,
                 checkpoint=str(checkpoint), side=side, eval_kind=eval_kind, seed=seed)
        state["tasks"][task_id]["episodes"] = episodes
        state["tasks"][task_id]["group"] = group


def milestone_evaluations(state: dict[str, Any], root: Path) -> None:
    if state["stop"] is not None:
        return
    for task in list(state["tasks"].values()):
        if task["kind"] != "train" or task["status"] not in {"LAUNCHED", "COMPLETE"}:
            continue
        if task["cell"] == "G1_WARM":
            steps = (task["step"],)
        elif task["cell"] == "A_W281":
            steps = (1000, 2000, 3000, 4000, 5000, 6000)
        else:
            steps = cells()[task["cell"]]["milestones"]
        for step in steps:
            if not checkpoint_ready(task, step):
                continue
            checkpoint = Path(task["output"]) / f"model_step_{step:06d}.pt"
            group = f"milestone_{task['id']}_{step}"
            add_eval_group(state, root, group=group, cell=task["cell"], step=step, checkpoint=checkpoint,
                           episodes=64, eval_kind="milestone", seed=EVAL_SEEDS["milestone"])


def evaluation_manifest(root: Path, tasks: list[dict[str, Any]], reducer_path: Path) -> Path:
    first = tasks[0]
    name = first["group"]
    path = root / "manifests" / f"{name}.json"
    if path.exists():
        return path
    require(len(tasks) == 2 and {task["side"] for task in tasks} == set(SIDES), f"incomplete exact bilateral group {name}")
    lanes = [{"cell": task["cell"], "stratum": "nominal", "side": task["side"], "seed": task["seed"],
              "episodes": task["episodes"], "checkpoint": task["checkpoint"], "artifact_path": task["output"],
              "camera_rig": str(ROOT / "scriptsFORhuman/v28/camera/U3_F39_H140.json"),
              "checkpoint_identity": {"cell": task["cell"], "step": task["step"], "checkpoint": task["checkpoint"],
                                      "run_id": "v28_camera_aware_rebaseline_20260909"}}
             for task in sorted(tasks, key=lambda value: value["side"])]
    write_new_json(path, {"schema": "a2_piper_base_v28_eval_manifest_v1", "name": name, "step": first["step"],
                          "endpoint": False, "lanes": lanes, "wave_a_history": [],
                          "scheduler_reducer_output": str(reducer_path)})
    return path


def reduce_completed_groups(state: dict[str, Any], root: Path) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for task in state["tasks"].values():
        if task["kind"] == "eval" and task["status"] in {"COMPLETE", "INVALID"}:
            grouped.setdefault(task["group"], []).append(task)
    for group, tasks in grouped.items():
        if group in state["reducers"] or len(tasks) != 2:
            continue
        reducer_path = root / "reducers" / f"{group}.json"
        manifest = evaluation_manifest(root, tasks, reducer_path)
        expected_n = tasks[0]["episodes"]
        result = subprocess.run([PYTHON, "-B", str(HERE / "v28_reduce.py"), "--manifest", str(manifest),
                                 "--expected-n", str(expected_n), "--output", str(reducer_path)], cwd=ROOT)
        require(result.returncode in (0, 2) and reducer_path.is_file(), f"reducer failed before typed result: {group}")
        payload = read_json(reducer_path)
        state["reducers"][group] = {"manifest": str(manifest), "path": str(reducer_path), "status": payload["status"],
                                    "task_ids": [task["id"] for task in tasks]}


def write_readout(reducer: Path, manifest: Path, output: Path) -> None:
    subprocess.run([PYTHON, "-B", str(HERE / "v28_readout.py"), "--reducer", str(reducer),
                    "--manifest", str(manifest), "--output", str(output)], cwd=ROOT, check=True)


def aggregate_wave_a_readouts(state: dict[str, Any], root: Path) -> None:
    by_step: dict[int, list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]] = {}
    for record in state["reducers"].values():
        payload = read_json(Path(record["path"]))
        tasks = [state["tasks"][task_id] for task_id in record["task_ids"]]
        if payload["status"] != "V28_COMPLETE" or payload["expected_n"] != 64 or len(tasks) != 2:
            continue
        if tasks[0]["cell"] not in {"A_S281", "A_S282", "A_S283"}:
            continue
        by_step.setdefault(payload["step"], []).append((record, payload, read_json(Path(record["manifest"]))))
    for step, rows in by_step.items():
        if {next(iter(payload["cells"])) for _, payload, _ in rows} != {"A_S281", "A_S282", "A_S283"}:
            continue
        reducer_path = root / "aggregates" / f"wave_a_step{step}_reducer.json"
        manifest_path = root / "aggregates" / f"wave_a_step{step}_manifest.json"
        if not reducer_path.exists():
            merged = {**rows[0][1], "cells": {}, "lanes": [], "invalid_cells": {}, "typed_outcomes": None}
            manifest = {**rows[0][2], "name": f"wave_a_step{step}_aggregate", "lanes": []}
            for _, payload, source_manifest in sorted(rows, key=lambda item: next(iter(item[1]["cells"]))):
                merged["cells"].update(payload["cells"])
                merged["lanes"].extend(payload["lanes"])
                manifest["lanes"].extend(source_manifest["lanes"])
            write_new_json(reducer_path, merged)
            write_new_json(manifest_path, manifest)
        readout_path = root / "readouts" / f"wave_a_step{step}_aggregate.md"
        if not readout_path.exists():
            write_readout(reducer_path, manifest_path, readout_path)


def write_completed_readouts(state: dict[str, Any], root: Path) -> None:
    for group, record in state["reducers"].items():
        if record.get("readout"):
            continue
        if group.startswith("milestone_g1") and record["status"] == "V28_COMPLETE" and not any(item["step"] == read_json(Path(record["path"]))["step"]
                                                           for item in state["g1"].get("history", [])):
            continue
        output = root / "readouts" / f"{group}.md"
        write_readout(Path(record["path"]), Path(record["manifest"]), output)
        record["readout"] = str(output)
    aggregate_wave_a_readouts(state, root)


def reduced_sides(state: dict[str, Any], group: str) -> dict[str, Any] | None:
    record = state["reducers"].get(group)
    if record is None or record["status"] != "V28_COMPLETE":
        return None
    payload = read_json(Path(record["path"]))
    tasks = [state["tasks"][task_id] for task_id in record["task_ids"]]
    return payload["cells"][tasks[0]["cell"]]["nominal"]


def record_g1_decision(state: dict[str, Any], root: Path, group: str, step: int, decision: dict[str, Any]) -> None:
    entry = {"step": step, "source_reducer": state["reducers"][group]["path"], "decision": decision,
             "recorded_at": utc_now()}
    write_new_json(root / "g1_decisions" / f"step{step}.json",
                   {"schema": "a2_piper_base_v28_g1_step_decision_v1", "run_id": "v28_camera_aware_rebaseline_20260909",
                    "source_lock": state["source_lock"], "route_authority": "plan §8.1 / V28-D038",
                    "decision_log_id": "V28-D038", **entry})
    state["g1"].setdefault("history", []).append(entry)
    write_canonical_json(ROOT / "scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/g1_probe_decision.json",
                         {"schema": "a2_piper_base_v28_g1_decision_v2", "run_id": "v28_camera_aware_rebaseline_20260909",
                          "status": decision["decision"], "outcome": decision["outcome"], "step": step,
                          "route_authority": "plan §8.1 / V28-D038", "decision_log_id": "V28-D038",
                          "source_lock": state["source_lock"], "source_reducer": entry["source_reducer"],
                          "endpoint_lock": None, "selection_rule": "plan §8.1 PASS/PARTIAL/FAIL",
                          "history": state["g1"]["history"]})


def g1_route(state: dict[str, Any], root: Path, reduce) -> None:
    if state["g1"]["status"] in {"PASS", "FAIL"}:
        return
    relevant = [task for task in state["tasks"].values() if task["kind"] == "train" and task["cell"] == "G1_WARM"]
    if not relevant:
        return
    current = max(relevant, key=lambda value: value["step"])
    group = f"milestone_{current['id']}_{current['step']}"
    record = state["reducers"].get(group)
    if record is not None and record["status"] == "V28_INVALID":
        state["g1"].update(status="EVALUATION_INVALID", decision=None)
        state["stop"] = {"reason": "G1_EVALUATION_INVALID", "group": group, "at": utc_now()}
        return
    sides = reduced_sides(state, group)
    if sides is None:
        return
    prior = None
    if current["step"] == 1000:
        prior = reduced_sides(state, "milestone_g1_train_500_500")
        require(prior is not None, "G1 1000 decision needs G1 step500 sides")
    wave_c_path = ROOT / "logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step1000/reducer.json"
    wave_c_step1000 = read_json(wave_c_path)["cells"] if wave_c_path.is_file() else None
    decision = reduce.g1_decision(sides, step=current["step"], initial_sides=prior, wave_c_step1000=wave_c_step1000)
    state["g1"].update(status=decision["decision"], decision=decision, decided_at=utc_now())
    record_g1_decision(state, root, group, current["step"], decision)
    if decision["action"] == "STOP":
        state["stop"] = {"reason": "G1_WARM_FAIL", "decision": decision, "at": utc_now()}
        return
    if decision["action"] == "EXTEND_TO_1000":
        require(current["step"] == 500, "G1 may extend only once from step500")
        checkpoint = checkpoint_for(current)
        add_task(state, root, task_id="g1_train_1000", kind="train", cell="G1_WARM", batches=500, step=1000,
                 resume=str(checkpoint), total_batches=1000)
        state["g1"]["status"] = "PARTIAL_EXTENSION_PENDING"
        return
    require(decision["action"] == "START_WAVE_A", f"unexpected G1 action {decision['action']}")
    for seed in (281, 282, 283):
        add_task(state, root, task_id=f"wave_a_s{seed}", kind="train", cell=f"A_S{seed}", batches=6000, step=6000)
    if decision.get("warm_arm_eligible") and not decision.get("warm_arm_cancelled"):
        add_task(state, root, task_id="wave_a_w281", kind="train", cell="A_W281", batches=6000, step=6000)
    state["wave_a"].update(status="ACTIVE", warm_arm_cancelled=decision.get("warm_arm_cancelled", False))


def wave_a_history(state: dict[str, Any]) -> list[dict[str, Any]]:
    by_step: dict[int, dict[str, Any]] = {}
    for record in state["reducers"].values():
        payload = read_json(Path(record["path"]))
        if payload.get("status") != "V28_COMPLETE" or payload.get("expected_n") != 64:
            continue
        if any(cell.startswith("A_S") for cell in payload.get("cells", {})):
            cells_at_step = by_step.setdefault(payload["step"], {})
            for cell, sides in payload["cells"].items():
                require(cell not in cells_at_step, f"duplicate reduced Wave A cell/step: {cell}@{payload['step']}")
                cells_at_step[cell] = sides
    return [{"step": step, "cells": cells_at_step} for step, cells_at_step in sorted(by_step.items())]


def a284_and_freeze(state: dict[str, Any], root: Path, reduce) -> None:
    if state["wave_a"]["status"] not in {"ACTIVE", "A284_PENDING_GPU"}:
        return
    history = wave_a_history(state)
    state["wave_a"]["history"] = history
    if state["commit_milestones"]["wave_a_step1000_aggregate"] == "PENDING":
        step1000 = next((row for row in history if row["step"] == 1000), None)
        if step1000 is not None and all(f"A_S{seed}" in step1000["cells"] for seed in (281, 282, 283)):
            state["commit_milestones"]["wave_a_step1000_aggregate"] = "REACHED"
    driver = reduce.k_reach_without_complete(history)
    if driver["outcome"] == "K_REACH_WITHOUT_COMPLETE" and "wave_a_s284" not in state["tasks"]:
        add_task(state, root, task_id="wave_a_s284", kind="train", cell="A_S284", batches=6000, step=6000)
        state["wave_a"]["a284_trigger"] = driver
    a284 = state["tasks"].get("wave_a_s284")
    if a284 is not None and "launched_at" not in a284:
        state["wave_a"]["status"] = "A284_PENDING_GPU"
        return
    if a284 is not None:
        state["wave_a"]["status"] = "ACTIVE"
    started = [task["cell"] for task in state["tasks"].values()
               if task["kind"] == "train" and task["cell"].startswith("A_S") and "launched_at" in task]
    selection = reduce.select_wave_a(history, started_cells=started)
    if not selection["freeze_ready"] or state["wave_a"]["endpoint_lock"] is not None:
        return
    lock = ROOT / "scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/wave_a_endpoint_lock.json"
    write_new_json(lock, {"schema": "a2_piper_base_v28_wave_a_endpoint_lock_v1", "run_id": "v28_camera_aware_rebaseline_20260909",
                          "frozen_at": utc_now(), "selection_rule": "D039 weak_clean, clean_sum, milestone, seed",
                          "endpoint_reliability": selection["endpoint_reliability"], "history_reach": selection["history_reach"],
                          "ranked_candidates": selection["ranked_candidates"], "candidates": selection["candidates"],
                          "a284_trigger": state["wave_a"].get("a284_trigger")})
    state["wave_a"].update(status="ENDPOINT_LOCKED", endpoint_lock=str(lock), selection=selection)
    state["commit_milestones"]["wave_a_endpoint_lock"] = "REACHED"
    write_wave_a_decision(state)
    start_wave_b(state, root, selection["candidates"])


def start_wave_b(state: dict[str, Any], root: Path, candidates: list[dict[str, Any]]) -> None:
    require(len(candidates) <= 2, "D039 permits at most two candidates")
    if not candidates:
        state["wave_b"].update(status="NOT_RUN_NO_CANDIDATE")
        write_wave_b_decision(state)
        return
    state["wave_b"].update(status="PRIMARY_DEV", candidates=candidates, current_index=0)
    schedule_qualification(state, root, candidates[0], "DEV", 0)


def schedule_qualification(state: dict[str, Any], root: Path, candidate: dict[str, Any], kind: str, index: int) -> None:
    before = state["wave_b"]["exact128_lanes"]
    require(before + 2 <= 8, "exact128 lane cap")
    group = f"qualification_{index}_{kind.lower()}"
    add_eval_group(state, root, group=group, cell=candidate["cell"], step=candidate["step"],
                   checkpoint=Path(candidate["checkpoint"]), episodes=128, eval_kind=kind, seed=EVAL_SEEDS[kind])
    state["wave_b"]["exact128_lanes"] = before + 2


def qualification_route(state: dict[str, Any], root: Path, reduce) -> None:
    wave_b = state["wave_b"]
    if wave_b["status"] in {"NOT_STARTED", "NOT_RUN_NO_CANDIDATE", "QUALIFIED", "QUALIFICATION_NOT_CONFIRMED"}:
        return
    index = wave_b["current_index"]
    kind = "DEV" if wave_b["status"].endswith("DEV") else "CONF"
    group = f"qualification_{index}_{kind.lower()}"
    record = state["reducers"].get(group)
    if record is None:
        return
    sides = reduced_sides(state, group)
    passes = sides is not None and all(reduce.passes_gate(sides[side]) for side in SIDES)
    if kind == "DEV" and passes:
        wave_b["status"] = "PRIMARY_CONF" if index == 0 else "RESERVE_CONF"
        schedule_qualification(state, root, wave_b["candidates"][index], "CONF", index)
        return
    if kind == "CONF" and passes:
        wave_b.update(status="QUALIFIED", qualified_candidate=wave_b["candidates"][index], qualified_at=utc_now())
        write_wave_b_decision(state)
        schedule_renders(state, root)
        return
    if index + 1 < len(wave_b["candidates"]):
        wave_b.update(current_index=index + 1, status="RESERVE_DEV")
        schedule_qualification(state, root, wave_b["candidates"][index + 1], "DEV", index + 1)
    else:
        wave_b.update(status="QUALIFICATION_NOT_CONFIRMED", completed_at=utc_now())
        write_wave_b_decision(state)
        schedule_renders(state, root)


def write_wave_a_decision(state: dict[str, Any]) -> None:
    write_canonical_json(ROOT / "scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/wave_a_decision.json",
                         {"schema": "a2_piper_base_v28_wave_a_decision_v1", "run_id": "v28_camera_aware_rebaseline_20260909",
                          "status": state["wave_a"]["status"],
                          "outcome": state["wave_a"]["selection"]["outcome"],
                          "source_lock": state["source_lock"], "route_authority": "plan §8.2 / V28-D039,V28-D040",
                          "decision_log_id": "V28-D039", "endpoint_lock": state["wave_a"].get("endpoint_lock"),
                          "selection": state["wave_a"].get("selection"), "history": state["wave_a"]["history"]})


def write_wave_b_decision(state: dict[str, Any]) -> None:
    write_canonical_json(ROOT / "scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/wave_b_decision.json",
                   {"schema": "a2_piper_base_v28_wave_b_decision_v2", "run_id": "v28_camera_aware_rebaseline_20260909",
                    "source_lock": state["source_lock"], "endpoint_lock": state["wave_a"]["endpoint_lock"],
                    "status": state["wave_b"]["status"],
                    "outcome": "BILATERAL_TEACHER_QUALIFIED_SIM_V28" if state["wave_b"]["status"] == "QUALIFIED"
                               else state["wave_b"]["status"],
                    "candidates": state["wave_b"].get("candidates", []),
                    "qualified_candidate": state["wave_b"].get("qualified_candidate"),
                    "source_reducers": [record["path"] for group, record in state["reducers"].items()
                                        if group.startswith("qualification_")],
                    "selection_rule": "Frozen primary then backup; bilateral DEV required for CONF",
                    "exact128_lanes": state["wave_b"]["exact128_lanes"], "route_authority": "plan §8.4 / V28-D039",
                    "decision_log_id": "V28-D039", "updated_at": utc_now()})


def terminal_incomplete_wave_a(state: dict[str, Any], reduce) -> None:
    wave_a = state["wave_a"]
    if wave_a["status"] not in {"ACTIVE", "A284_PENDING_GPU"}:
        return
    history = wave_a["history"]
    started = [task["cell"] for task in state["tasks"].values()
               if task["kind"] == "train" and task["cell"].startswith("A_S") and "launched_at" in task]
    selection = reduce.select_wave_a(history, started_cells=started)
    if selection["freeze_ready"]:
        return
    wave_tasks = [task for task in state["tasks"].values() if task["kind"] == "train" and task["cell"].startswith("A_S")]
    eval_tasks = [task for task in state["tasks"].values() if task["kind"] == "eval" and task["cell"].startswith("A_S")]
    terminal = {"COMPLETE", "STOPPED_POLICY_READOUT", "STOPPED_INFRA_ATTEMPTS_EXHAUSTED", "INVALID"}
    if wave_tasks and all(task["status"] in terminal for task in wave_tasks) and all(task["status"] in terminal for task in eval_tasks):
        wave_a.update(status="INCOMPLETE_EVIDENCE", incomplete_reason=selection["missing_evaluations"], selection=selection)
        state["wave_b"].update(status="NOT_RUN_INCOMPLETE_EVIDENCE", reason=selection["missing_evaluations"])
        write_wave_a_decision(state)
        write_wave_b_decision(state)


def schedule_renders(state: dict[str, Any], root: Path) -> None:
    seconds = state["wave_b"].get("render_reserved_seconds", 0)
    for candidate_index, candidate in enumerate(state["wave_b"]["candidates"]):
        for side in SIDES:
            task_id = f"render_{candidate_index}_{candidate['cell'].lower()}_step{candidate['step']}_{side}"
            if task_id in state["tasks"]:
                continue
            require(seconds + 900 <= 3600, "render budget exceeds one hour")
            add_task(state, root, task_id=task_id, kind="render", cell=candidate["cell"], step=candidate["step"],
                     checkpoint=candidate["checkpoint"], side=side, seed=EVAL_SEEDS["render"], eval_kind="render")
            state["tasks"][task_id].update(episode_ids=[0, 1, 2], endpoint_lock=state["wave_a"]["endpoint_lock"],
                                            candidate_index=candidate_index)
            seconds += 900
    state["wave_b"]["render_reserved_seconds"] = seconds


def launch_pending(state: dict[str, Any], root: Path, eligible: list[int]) -> None:
    if state["stop"] is not None:
        return
    available = list(eligible)
    render_running = any(task["kind"] == "render" and task["status"] == "LAUNCHED" for task in state["tasks"].values())
    for task in state["tasks"].values():
        if task["status"] != "PENDING_GPU" or not available:
            continue
        if task["kind"] == "render" and render_running:
            continue
        gpu = available.pop(0)
        task["receipt"] = supervisor_prepare(task, gpu)
        task.update(status="LAUNCHED", gpu=gpu, launched_at=utc_now())
        budget = state["budget"]
        budget["scheduled_batches"] -= task["batches"]
        budget["active_reserved_batches"] += task["batches"]
        require(budget["scheduled_batches"] >= 0 and budget["active_reserved_batches"] <= BUDGET_CAP,
                "invalid active training reservation")
        if task["kind"] == "render":
            render_running = True
            task["render_deadline_epoch"] = time.time() + 900
        write_state(state_path(root), state)


def notify_deadline(state: dict[str, Any], root: Path) -> None:
    pending = [task["id"] for task in state["tasks"].values()
               if task["status"] == "PENDING_GPU" and task["pending_deadline_epoch"] <= time.time()
               and not task.get("pending_gpu_notified_at")]
    if pending:
        notice = root / "notifications" / f"pending_gpu_12h_{len(state['notifications'])}.json"
        write_new_json(notice, {"schema": "a2_piper_base_v28_pending_gpu_notice_v1", "at": utc_now(),
                               "pending_tasks": pending, "next_decision_epoch": state["next_decision_epoch"],
                               "reason": "Pending beyond 12h; keep active cells progressing and launch queued cells when capacity permits"})
        state["notifications"].append({"kind": "GPU_PENDING_12H", "path": str(notice), "tasks": pending})
        for task_id in pending:
            state["tasks"][task_id]["pending_gpu_notified_at"] = utc_now()


def execution_terminal(state: dict[str, Any]) -> bool:
    if state["stop"] is not None:
        return True
    active = [task for task in state["tasks"].values()
              if task["status"] in {"PENDING_GPU", "LAUNCHED"}]
    if active:
        return False
    if state["wave_a"]["status"] == "INCOMPLETE_EVIDENCE":
        return True
    if state["wave_b"]["status"] not in {"QUALIFIED", "QUALIFICATION_NOT_CONFIRMED", "NOT_RUN_NO_CANDIDATE"}:
        return False
    renders = [task for task in state["tasks"].values() if task["kind"] == "render"]
    return all(task["status"] in {"COMPLETE", "INVALID", "STOPPED_POLICY_READOUT",
                                  "STOPPED_INFRA_ATTEMPTS_EXHAUSTED", "NOT_COMPLETED_RENDER_BUDGET"} for task in renders)


def tick(path: Path) -> tuple[dict[str, Any], bool]:
    state = read_json(path)
    require(state.get("schema") == SCHEMA, "scheduler state schema")
    root = path.parent
    enforce_render_budget(state)
    synchronize_tasks(state, root)
    milestone_evaluations(state, root)
    reduce_completed_groups(state, root)
    reduce = reducer_module()
    g1_route(state, root, reduce)
    a284_and_freeze(state, root, reduce)
    terminal_incomplete_wave_a(state, reduce)
    qualification_route(state, root, reduce)
    write_completed_readouts(state, root)
    pending = any(task["status"] == "PENDING_GPU" for task in state["tasks"].values())
    eligible = append_gpu_observation(state, root) if pending else []
    launch_pending(state, root, eligible)
    notify_deadline(state, root)
    write_state(path, state)
    return state, execution_terminal(state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    path = args.state.resolve()
    while True:
        state, done = tick(path)
        if args.once or done:
            return 0
        deadlines = [task["render_deadline_epoch"] for task in state["tasks"].values()
                     if task["kind"] == "render" and task["status"] == "LAUNCHED"
                     and not task.get("render_budget_cancelled")]
        delay = min(POLL_SECONDS, min(deadlines) - time.time()) if deadlines else POLL_SECONDS
        if delay > 0:
            time.sleep(delay)


if __name__ == "__main__":
    raise SystemExit(main())
