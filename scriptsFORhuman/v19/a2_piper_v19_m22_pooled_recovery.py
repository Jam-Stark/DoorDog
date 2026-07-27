#!/usr/bin/env python3
"""Recover ambiguous canonical M22 groups with pooled48 evidence.

The runner waits for an existing post-M22 process by pidfd. Groups whose
canonical adjudication failed because no unique Pareto dominator existed are
escalated without a checkpoint-step tie-break: every canonical candidate that
passed all M22 redlines receives exact seed1/seed2 evals, is re-adjudicated on
pooled48 evidence, and the selected three artifacts become the endpoint.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import select
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
QUEUE_TOOL = ROOT / "scriptsFORhuman/v19/a2_piper_v19_m22_queue.py"
EVIDENCE_TOOL = ROOT / "scriptsFORhuman/v19/a2_piper_v19_m22_evidence.py"
ADJUDICATOR_TOOL = ROOT / "scriptsFORhuman/v19/a2_piper_v19_m22_adjudicator.py"
ENDPOINT_REPORT_TOOL = ROOT / "scriptsFORhuman/v19/a2_piper_v19_endpoint_report.py"
MANIFEST_SCHEMA = "a2_piper_v19_m22_candidate_manifest_v1"
POOLED_SOURCES_SCHEMA = "a2_piper_v19_m22_pooled_sources_v1"
RECOVERY_SCHEMA = "a2_piper_v19_m22_pooled_recovery_v1"


class M22PooledRecoveryError(RuntimeError):
    """Raised when pooled M22 recovery cannot preserve strict provenance."""


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise M22PooledRecoveryError(f"cannot load module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M22PooledRecoveryError(f"cannot load JSON {path}: {exc}") from exc


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _wait_for_pid_exit(pid: int) -> None:
    if pid <= 0:
        raise M22PooledRecoveryError("wait pid must be positive")
    descriptor = os.pidfd_open(pid)
    try:
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        events = poller.poll()
        if not events:
            raise M22PooledRecoveryError(f"pidfd wait returned without an event for pid {pid}")
    finally:
        os.close(descriptor)


def _run_logged(argv: list[str], log_path: Path, *, env: dict[str, str] | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as handle:
        completed = subprocess.run(
            argv,
            cwd=ROOT,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return completed.returncode


def _tool_step(argv: list[str], log_path: Path) -> dict[str, Any]:
    code = _run_logged(argv, log_path)
    return {"argv": argv, "log": str(log_path), "exit_code": code}


def _canonical_frontier_candidates(
    adjudicator: ModuleType,
    manifest: Mapping[str, Any],
    evidence: Any,
) -> list[dict[str, Any]]:
    candidates = adjudicator._validate_manifest(manifest)
    evidence_index = adjudicator._evidence_index(evidence)
    candidate_ids = {str(candidate["candidate_id"]) for candidate in candidates}
    if set(evidence_index) != candidate_ids:
        raise M22PooledRecoveryError("canonical evidence identities differ from manifest")

    passing: list[tuple[dict[str, Any], dict[str, float]]] = []
    for candidate in candidates:
        candidate_id = str(candidate["candidate_id"])
        row = evidence_index[candidate_id]
        topology = adjudicator._validate_evidence_binding(candidate, row)
        if topology != adjudicator.CANONICAL_TOPOLOGY:
            raise M22PooledRecoveryError("recovery input must be canonical16 evidence")
        if adjudicator._strict_status(row) != "STRICT_VALID":
            continue
        metrics = adjudicator.normalize_metrics(row, topology)
        if adjudicator._passes(metrics, topology):
            passing.append((dict(candidate), metrics))
    frontier = [
        candidate
        for candidate, metrics in passing
        if not any(
            other_candidate["candidate_id"] != candidate["candidate_id"]
            and adjudicator._dominates(other_metrics, metrics)
            for other_candidate, other_metrics in passing
        )
    ]
    if len(frontier) < 2:
        raise M22PooledRecoveryError(
            "canonical adjudication failure is not a multi-candidate Pareto ambiguity: "
            f"passing={len(passing)}, frontier={len(frontier)}"
        )
    return frontier


def _canonical_artifact_index(evidence: Any) -> dict[str, Path]:
    rows = evidence.get("rows") if isinstance(evidence, Mapping) else None
    if not isinstance(rows, list):
        raise M22PooledRecoveryError("canonical evidence lacks rows")
    result: dict[str, Path] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise M22PooledRecoveryError("canonical evidence row is not a mapping")
        candidate_id = row.get("candidate_id")
        artifact = row.get("artifact")
        if not isinstance(candidate_id, str) or not isinstance(artifact, str):
            raise M22PooledRecoveryError("canonical evidence provenance is incomplete")
        if candidate_id in result:
            raise M22PooledRecoveryError(f"duplicate canonical evidence identity {candidate_id}")
        result[candidate_id] = Path(artifact).expanduser().resolve()
    return result


def _eval_candidate(
    queue: ModuleType,
    candidate: Mapping[str, Any],
    artifact: Path,
    seed: int,
    gpu: str,
) -> dict[str, Any]:
    if artifact.exists() and any(artifact.iterdir()):
        raise M22PooledRecoveryError(f"pooled artifact is already non-empty: {artifact}")
    artifact.mkdir(parents=True, exist_ok=True)
    command = queue.build_eval_command(candidate, artifact, seed=seed, gpu=gpu)
    argv = command["argv"]
    command_env = command["env"]
    if "--device" in argv or "CUDA_VISIBLE_DEVICES" in command_env:
        raise M22PooledRecoveryError("pooled eval violates physical-device command contract")
    expected_device = f"cuda:{gpu}"
    if command_env.get("ACCELERATE_TORCH_DEVICE") != expected_device:
        raise M22PooledRecoveryError("pooled eval does not bind AppLauncher/Accelerate exactly")
    _write_json_atomic(
        artifact / "pooled_eval_command.json",
        {
            "candidate": dict(candidate),
            "seed": seed,
            "argv": argv,
            "env": command_env,
        },
    )
    env = os.environ.copy()
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env.update(command_env)
    code = _run_logged(argv, artifact / "runner.log", env=env)
    _write_text_atomic(artifact / "eval_exit_code.txt", f"{code}\n")
    if not (artifact / ".hydra/config.yaml").is_file():
        raise M22PooledRecoveryError(f"pooled eval failed before Hydra admission: {artifact}")
    return {"candidate_id": candidate["candidate_id"], "seed": seed, "artifact": str(artifact), "exit_code": code}


def _recover_group(
    group: str,
    row: Mapping[str, Any],
    output_root: Path,
    gpu: str,
    queue: ModuleType,
    adjudicator: ModuleType,
) -> dict[str, Any]:
    group_root = Path(str(row.get("m22_root", ""))).expanduser().resolve()
    manifest_path = group_root / "a2_piper_v19_m22_candidate_manifest.json"
    canonical_evidence_path = group_root / "a2_piper_v19_m22_evidence.json"
    manifest = _load_json(manifest_path)
    canonical_evidence = _load_json(canonical_evidence_path)
    frontier = _canonical_frontier_candidates(adjudicator, manifest, canonical_evidence)
    canonical_artifacts = _canonical_artifact_index(canonical_evidence)

    group_output = output_root / group
    subset_manifest_path = group_output / "a2_piper_v19_m22_pooled_candidate_manifest.json"
    pooled_sources_path = group_output / "a2_piper_v19_m22_pooled_sources.json"
    pooled_evidence_path = group_output / "a2_piper_v19_m22_pooled_evidence.json"
    adjudication_json = group_output / "a2_piper_v19_m22_pooled_adjudication.json"
    adjudication_md = group_output / "a2_piper_v19_m22_pooled_adjudication.md"
    endpoint_root = group_output / "selected_endpoint_48door"
    if group_output.exists() and any(group_output.iterdir()):
        raise M22PooledRecoveryError(f"group recovery output is already non-empty: {group_output}")
    group_output.mkdir(parents=True, exist_ok=True)

    subset_manifest = {"schema": MANIFEST_SCHEMA, "candidates": frontier}
    _write_json_atomic(subset_manifest_path, subset_manifest)
    eval_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for candidate in frontier:
        candidate_id = str(candidate["candidate_id"])
        seed_artifacts = {"seed0": str(canonical_artifacts[candidate_id])}
        for seed in (1, 2):
            artifact = group_output / candidate_id.removesuffix(".pt") / f"seed{seed}"
            eval_rows.append(_eval_candidate(queue, candidate, artifact, seed, gpu))
            seed_artifacts[f"seed{seed}"] = str(artifact)
        source_rows.append(
            {
                "candidate_id": candidate_id,
                "checkpoint_path": candidate["path"],
                "checkpoint_sha256": candidate["sha256"],
                "source_artifacts": seed_artifacts,
            }
        )
    pooled_sources = {"schema": POOLED_SOURCES_SCHEMA, "rows": source_rows}
    _write_json_atomic(pooled_sources_path, pooled_sources)

    evidence_step = _tool_step(
        [
            str(PYTHON),
            str(EVIDENCE_TOOL),
            "--manifest",
            str(subset_manifest_path),
            "--pooled-sources",
            str(pooled_sources_path),
            "--output",
            str(pooled_evidence_path),
        ],
        group_output / "pooled_evidence.log",
    )
    if evidence_step["exit_code"] != 0:
        return {"group": group, "status": "POOLED_EVIDENCE_FAILED", "evidence_step": evidence_step, "evals": eval_rows}

    adjudication_step = _tool_step(
        [
            str(PYTHON),
            str(ADJUDICATOR_TOOL),
            "--manifest",
            str(subset_manifest_path),
            "--evidence",
            str(pooled_evidence_path),
            "--output-json",
            str(adjudication_json),
            "--output-md",
            str(adjudication_md),
        ],
        group_output / "pooled_adjudication.log",
    )
    if adjudication_step["exit_code"] != 0:
        return {"group": group, "status": "POOLED_ADJUDICATION_FAILED", "adjudication_step": adjudication_step, "evals": eval_rows}

    adjudication = _load_json(adjudication_json)
    selected = adjudication["selected_checkpoint"]
    selected_sources = next(
        source for source in source_rows if source["candidate_id"] == selected["candidate_id"]
    )["source_artifacts"]
    report_step = _tool_step(
        [
            str(PYTHON),
            str(ENDPOINT_REPORT_TOOL),
            "--group",
            group,
            "--checkpoint",
            selected["path"],
            "--seed0-artifact",
            selected_sources["seed0"],
            "--seed1-artifact",
            selected_sources["seed1"],
            "--seed2-artifact",
            selected_sources["seed2"],
            "--output-dir",
            str(endpoint_root),
        ],
        group_output / "endpoint_report.log",
    )
    if report_step["exit_code"] != 0:
        return {"group": group, "status": "ENDPOINT_REPORT_FAILED", "report_step": report_step, "evals": eval_rows}

    return {
        "group": group,
        "status": "COMPLETED",
        "m22_root": str(group_root),
        "canonical_adjudication_status": row.get("status"),
        "pooled_recovery_root": str(group_output),
        "pooled_candidate_manifest": str(subset_manifest_path),
        "pooled_sources": str(pooled_sources_path),
        "pooled_evidence": str(pooled_evidence_path),
        "adjudication_json": str(adjudication_json),
        "adjudication_md": str(adjudication_md),
        "selected_checkpoint": selected,
        "seed0_artifact": selected_sources["seed0"],
        "endpoint_root": str(endpoint_root),
        "endpoint_evals": [entry for entry in eval_rows if entry["candidate_id"] == selected["candidate_id"]],
        "endpoint_report_json": str(endpoint_root / "a2_piper_v19_endpoint_report.json"),
        "endpoint_report_md": str(endpoint_root / "a2_piper_v19_endpoint_report.md"),
        "pooled_eval_count": len(eval_rows),
    }


def run_recovery(
    post_state_path: Path,
    output_root: Path,
    output_state: Path,
    gpu: str,
) -> dict[str, Any]:
    post = _load_json(post_state_path)
    if post.get("status") not in {"COMPLETED", "COMPLETED_WITH_FAILURES"}:
        raise M22PooledRecoveryError("post-M22 state is not terminal")
    groups = post.get("groups")
    if not isinstance(groups, list) or len(groups) != 7:
        raise M22PooledRecoveryError("post-M22 state must contain exactly seven groups")

    queue = _load_module("a2_piper_v19_queue_for_pooled_recovery", QUEUE_TOOL)
    adjudicator = _load_module("a2_piper_v19_adjudicator_for_pooled_recovery", ADJUDICATOR_TOOL)
    state: dict[str, Any] = {
        "schema": "a2_piper_v19_post_m22_endpoint_runner_v1",
        "recovery_schema": RECOVERY_SCHEMA,
        "status": "RUNNING",
        "source_post_state": str(post_state_path.resolve()),
        "execution": "strict serial physical GPU; no retry, visibility mask, checkpoint-step tie-break, or artifact reuse",
        "groups": [],
    }
    _write_json_atomic(output_state, state)
    for row in groups:
        if not isinstance(row, Mapping) or row.get("group") is None:
            raise M22PooledRecoveryError("post-M22 group row is invalid")
        group = str(row["group"])
        state["active_group"] = group
        _write_json_atomic(output_state, state)
        if row.get("status") == "COMPLETED":
            result = dict(row)
            result["recovery_action"] = "NOT_REQUIRED"
        elif row.get("status") == "ADJUDICATION_FAILED":
            try:
                result = _recover_group(group, row, output_root, gpu, queue, adjudicator)
            except Exception as exc:
                result = {"group": group, "status": "RECOVERY_EXCEPTION", "error": f"{type(exc).__name__}: {exc}"}
        else:
            result = dict(row)
            result["recovery_action"] = "NOT_APPLICABLE"
        state["groups"].append(result)
        state.pop("active_group", None)
        _write_json_atomic(output_state, state)

    failures = [row for row in state["groups"] if row.get("status") != "COMPLETED"]
    state["status"] = "COMPLETED" if not failures else "COMPLETED_WITH_FAILURES"
    state["completed_group_count"] = len(state["groups"]) - len(failures)
    state["failed_group_count"] = len(failures)
    _write_json_atomic(output_state, state)
    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--post-state", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output-state", type=Path, required=True)
    parser.add_argument("--gpu", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    waiting = {
        "schema": RECOVERY_SCHEMA,
        "status": "WAITING_FOR_POST_M22_PIDFD",
        "wait_pid": args.wait_pid,
    }
    _write_json_atomic(args.output_state, waiting)
    _wait_for_pid_exit(args.wait_pid)
    state = run_recovery(args.post_state, args.output_root, args.output_state, args.gpu)
    return 0 if state["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"M22 POOLED RECOVERY FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
