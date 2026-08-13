"""Deterministic post-formal v23 GPU8 workflow orchestrator.

This launcher owns orchestration only.  The existing stage scripts remain the
source of truth for plan validation, runtime execution, reducers, and final
analysis.  A persisted plan is consumed after its PLAN/BUILD command passes;
RUN never receives a new GPU mapping.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23Error
    from . import final_analysis, holdout64, intervention_eval, pooled48, render, route_b, route_b_analysis, stratified_eval
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23Error
    from scriptsFORhuman.v23 import final_analysis, holdout64, intervention_eval, pooled48, render, route_b, route_b_analysis, stratified_eval


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
LEGAL_PHYSICAL_GPUS = tuple(range(8))
DEFAULT_PHYSICAL_GPUS = LEGAL_PHYSICAL_GPUS
DEFAULT_ORCHESTRATION_ROOT = REPO_ROOT / "logs_eval/base_v23/postformal_gpu8_orchestration"
GPU_MAPPING_POLICY = "CANONICAL_JOB_ORDINAL_MODULO_ORDERED_SELECTED_LIST"


class OrchestratorError(V23Error):
    """A workflow, manifest, child process, or append-only artifact is invalid."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _parse_physical_gpus(value: Sequence[str] | str | None) -> list[int]:
    if value is None:
        return list(DEFAULT_PHYSICAL_GPUS)
    values = [value] if isinstance(value, str) else list(value)
    tokens: list[str] = []
    for item in values:
        tokens.extend(part.strip() for part in str(item).split(","))
    if not tokens or any(not token for token in tokens):
        raise OrchestratorError("physical GPU mapping requires one or more ids in 0..7")
    try:
        parsed = [int(token) for token in tokens]
    except ValueError as exc:
        raise OrchestratorError("physical GPU mapping values must be integer ids in 0..7") from exc
    if any(gpu not in LEGAL_PHYSICAL_GPUS for gpu in parsed):
        raise OrchestratorError("physical GPU mapping ids must be in 0..7")
    if len(set(parsed)) != len(parsed):
        raise OrchestratorError("physical GPU mapping must be ordered and unique")
    return parsed


def _gpu_argument(physical_gpus: Sequence[int]) -> str:
    return ",".join(str(gpu) for gpu in physical_gpus)


def _parse_candidate_ids(values: Sequence[str] | None) -> list[str] | None:
    if values is None:
        return None
    tokens: list[str] = []
    for value in values:
        tokens.extend(part.strip() for part in str(value).split(","))
    if not tokens or any(not token for token in tokens):
        raise OrchestratorError("render requires one to three non-empty candidate IDs")
    if len(tokens) not in (1, 2, 3):
        raise OrchestratorError("render requires exactly one to three candidate IDs")
    if len(set(tokens)) != len(tokens):
        raise OrchestratorError("render candidate IDs must be unique")
    return tokens


def _load_json(path: str | Path) -> dict[str, Any]:
    target = _absolute(path)
    if target.is_symlink() or not target.is_file():
        raise OrchestratorError(f"required persisted plan/receipt is missing: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OrchestratorError(f"persisted plan/receipt is not valid JSON: {target}") from exc
    if not isinstance(payload, dict):
        raise OrchestratorError(f"persisted plan/receipt must be an object: {target}")
    return payload


def _write_append_only(path: Path, payload: Mapping[str, Any]) -> None:
    target = _absolute(path)
    if target.exists() or target.is_symlink():
        raise OrchestratorError(f"refusing to overwrite orchestration receipt: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(dict(payload), stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _new_stage_dir(root: Path, stage: str) -> Path:
    target = _absolute(root) / stage
    if target.exists() or target.is_symlink():
        raise OrchestratorError(f"stage root already exists; retry/resume is forbidden: {target}")
    target.mkdir(parents=True, exist_ok=False)
    return target


def _validate_plan(path: str | Path) -> dict[str, Any]:
    payload = _load_json(path)
    physical_gpus = payload.get("physical_gpus")
    if not isinstance(physical_gpus, list) or not physical_gpus:
        raise OrchestratorError(f"persisted plan has no physical_gpus manifest: {_absolute(path)}")
    manifest = _parse_physical_gpus(physical_gpus)
    if payload.get("physical_gpu_domain") not in (None, list(LEGAL_PHYSICAL_GPUS)):
        raise OrchestratorError(f"persisted plan physical_gpu_domain is not 0..7: {_absolute(path)}")
    if payload.get("physical_gpu_mapping_policy") not in (None, GPU_MAPPING_POLICY):
        raise OrchestratorError(f"persisted plan physical GPU mapping policy is unsupported: {_absolute(path)}")
    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise OrchestratorError(f"persisted plan has no jobs: {_absolute(path)}")
    for ordinal, job in enumerate(jobs):
        if not isinstance(job, Mapping):
            raise OrchestratorError(f"persisted plan job {ordinal} is not an object")
        if job.get("job_ordinal") != ordinal:
            raise OrchestratorError(f"persisted plan job {ordinal} ordinal is not deterministic")
        expected_gpu = manifest[ordinal % len(manifest)]
        if job.get("physical_gpu") != expected_gpu:
            raise OrchestratorError(f"persisted plan job {ordinal} GPU disagrees with its manifest")
    normalized = dict(payload)
    normalized["physical_gpus"] = manifest
    normalized["jobs"] = [dict(job) for job in jobs]
    return normalized


def _script(name: str) -> Path:
    target = SCRIPT_ROOT / name
    if not target.is_file():
        raise OrchestratorError(f"stage script is missing: {target}")
    return target


def _command(script_name: str, args: Sequence[str]) -> list[str]:
    return [sys.executable, str(_script(script_name)), *[str(value) for value in args]]


def _run_process(
    command: Sequence[str],
    *,
    stage_dir: Path,
    label: str,
    physical_gpu: int | None = None,
) -> int:
    suffix = "" if physical_gpu is None else f"_gpu{physical_gpu}"
    stdout_path = stage_dir / f"{label}{suffix}.stdout.log"
    stderr_path = stage_dir / f"{label}{suffix}.stderr.log"
    stdout = stdout_path.open("x", encoding="utf-8")
    stderr = stderr_path.open("x", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [str(value) for value in command],
            cwd=REPO_ROOT,
            env=os.environ.copy(),
            stdout=stdout,
            stderr=stderr,
        )
        return int(process.wait())
    finally:
        stdout.close()
        stderr.close()


def run_command_stage(
    *,
    root: str | Path,
    stage: str,
    command: Sequence[str],
) -> dict[str, Any]:
    """Run one PLAN/BUILD/REDUCE/WRITE child and seal a receipt only on PASS."""

    stage_dir = _new_stage_dir(_absolute(root), stage)
    return_code = _run_process(command, stage_dir=stage_dir, label="command")
    if return_code != 0:
        raise OrchestratorError(f"stage {stage} exited {return_code}; downstream stages are blocked")
    receipt = {
        "schema": "a2_piper_v23_postformal_orchestration_stage_v1",
        "status": "PASS",
        "recorded_at_utc": _utc_now(),
        "stage": stage,
        "command": [str(value) for value in command],
        "return_code": return_code,
        "retry_policy": "none",
    }
    _write_append_only(stage_dir / "orchestration_receipt.json", receipt)
    return receipt


def _job_id(job: Mapping[str, Any], *, ordinal: int, index_mode: bool) -> str:
    if index_mode:
        return str(ordinal)
    value = job.get("job_id")
    if not isinstance(value, str) or not value:
        raise OrchestratorError(f"manifest job {ordinal} has no job_id")
    return value


def _job_command(script_name: str, plan_path: Path, job: Mapping[str, Any], *, ordinal: int, index_mode: bool) -> list[str]:
    args = ["--mode", "RUN", "--plan", str(plan_path)]
    if index_mode:
        args.extend(["--job-index", str(ordinal)])
    else:
        args.extend(["--job", _job_id(job, ordinal=ordinal, index_mode=False)])
    return _command(script_name, args)


def run_job_stage(
    *,
    root: str | Path,
    stage: str,
    script_name: str,
    plan_path: str | Path,
    index_mode: bool,
) -> dict[str, Any]:
    """Run manifest jobs in deterministic waves, one live child per GPU."""

    plan = _validate_plan(plan_path)
    jobs = plan["jobs"]
    manifest = plan["physical_gpus"]
    stage_dir = _new_stage_dir(_absolute(root), stage)
    pending = list(range(len(jobs)))
    waves: list[list[int]] = []
    completed: list[str] = []
    while pending:
        used_gpus: set[int] = set()
        wave: list[int] = []
        remaining: list[int] = []
        for ordinal in pending:
            gpu = int(jobs[ordinal]["physical_gpu"])
            if gpu in used_gpus:
                remaining.append(ordinal)
                continue
            used_gpus.add(gpu)
            wave.append(ordinal)
        if not wave:
            raise OrchestratorError(f"stage {stage} cannot form a GPU-disjoint wave")
        waves.append(wave)
        pending = remaining
        running: list[tuple[int, int, Any, Any, Any]] = []
        try:
            for ordinal in wave:
                job = jobs[ordinal]
                gpu = int(job["physical_gpu"])
                label = f"job_{ordinal:04d}"
                stdout_path = stage_dir / f"{label}_gpu{gpu}.stdout.log"
                stderr_path = stage_dir / f"{label}_gpu{gpu}.stderr.log"
                stdout = stdout_path.open("x", encoding="utf-8")
                stderr = stderr_path.open("x", encoding="utf-8")
                process = subprocess.Popen(
                    _job_command(script_name, Path(plan_path).resolve(), job, ordinal=ordinal, index_mode=index_mode),
                    cwd=REPO_ROOT,
                    env=os.environ.copy(),
                    stdout=stdout,
                    stderr=stderr,
                )
                running.append((ordinal, gpu, process, stdout, stderr))
        except BaseException:
            for _ordinal, _gpu, process, stdout, stderr in running:
                process.wait()
                stdout.close()
                stderr.close()
            raise
        failures: list[tuple[int, int, int]] = []
        for ordinal, gpu, process, stdout, stderr in running:
            return_code = int(process.wait())
            stdout.close()
            stderr.close()
            if return_code != 0:
                failures.append((ordinal, gpu, return_code))
            else:
                completed.append(_job_id(jobs[ordinal], ordinal=ordinal, index_mode=index_mode))
        if failures:
            raise OrchestratorError(f"stage {stage} wave failed: {failures}; no retry and no reducer")
    receipt = {
        "schema": "a2_piper_v23_postformal_orchestration_jobs_v1",
        "status": "PASS",
        "recorded_at_utc": _utc_now(),
        "stage": stage,
        "script": script_name,
        "plan_path": str(Path(plan_path).resolve()),
        "job_count": len(jobs),
        "completed_jobs": completed,
        "physical_gpus": list(manifest),
        "waves": [
            {"ordinals": wave, "physical_gpus": [int(jobs[ordinal]["physical_gpu"]) for ordinal in wave]}
            for wave in waves
        ],
        "retry_policy": "none",
    }
    _write_append_only(stage_dir / "orchestration_receipt.json", receipt)
    return receipt


def _paths(root: str | Path) -> dict[str, Path]:
    base = _absolute(root)
    return {
        "root": base,
        "route_b_plan": base / "V23_ROUTE_B_PLAN.json",
        "pooled_plan": base / "V23_POOLED48_PLAN.json",
        "pooled_receipt": base / "V23_POOLED48.json",
        "stratified_plan": base / "V23_STRATIFIED_EVAL_PLAN.json",
        "stratified_receipt": base / "V23_STRATIFIED_EVAL.json",
        "intervention_plan": base / "V23_INTERVENTION_EVAL_PLAN.json",
        "intervention_receipt": base / "V23_INTERVENTION_EVAL.json",
        "route_b_receipt": base / "V23_ROUTE_B.json",
        "candidate_freeze": base / "candidate_freeze.json",
        "holdout_plan": base / "holdout_plan.json",
        "holdout_receipt": base / "holdout_receipt.json",
        "holdout_output": base / "holdout_outputs",
        "render_plan": base / "render_plan.json",
        "render_receipt": base / "render_receipt.json",
        "render_output": base / "render_outputs",
        "final_json": base / "final_analysis.json",
        "final_markdown": base / "final_analysis.md",
    }


def _load_persisted_route_execution(route_plan_path: str | Path) -> dict[str, Path]:
    """Load child plan/receipt paths from the validated Route-B manifest."""

    try:
        route_plan = route_b._load_route_plan(route_plan_path)
    except (OSError, TypeError, ValueError, V23Error) as exc:
        raise OrchestratorError(f"persisted Route-B plan is invalid: {_absolute(route_plan_path)}") from exc
    execution = route_plan.get("execution_plan")
    if not isinstance(execution, Mapping):
        raise OrchestratorError("persisted Route-B plan has no execution_plan")
    required = (
        "pooled48_plan_path",
        "stratified_plan_path",
        "intervention_plan_path",
        "pooled48_receipt_path",
        "stratified_receipt_path",
        "intervention_receipt_path",
    )
    paths: dict[str, Path] = {}
    for field in required:
        value = execution.get(field)
        if not isinstance(value, str) or not value or not Path(value).is_absolute():
            raise OrchestratorError(f"persisted Route-B execution path {field} is not absolute")
        paths[field] = Path(value)
    physical_gpus = execution.get("physical_gpus")
    if physical_gpus != list(DEFAULT_PHYSICAL_GPUS):
        raise OrchestratorError("persisted Route-B execution plan must use physical GPUs 0..7")
    return paths


def run_route_b(*, root: str | Path, physical_gpus: Sequence[int]) -> dict[str, Path]:
    paths = _paths(root)
    gpu_arg = _gpu_argument(physical_gpus)
    run_command_stage(
        root=root,
        stage="01_route_b_build",
        command=_command("route_b.py", ["--mode", "BUILD", "--physical-gpus", gpu_arg, "--output", str(paths["route_b_plan"])]),
    )
    persisted = _load_persisted_route_execution(paths["route_b_plan"])
    paths.update(
        {
            "pooled_plan": persisted["pooled48_plan_path"],
            "stratified_plan": persisted["stratified_plan_path"],
            "intervention_plan": persisted["intervention_plan_path"],
            "pooled_receipt": persisted["pooled48_receipt_path"],
            "stratified_receipt": persisted["stratified_receipt_path"],
            "intervention_receipt": persisted["intervention_receipt_path"],
        }
    )
    run_job_stage(
        root=root,
        stage="02_pooled48_run",
        script_name="pooled48.py",
        plan_path=paths["pooled_plan"],
        index_mode=False,
    )
    run_command_stage(
        root=root,
        stage="03_pooled48_reduce",
        command=_command("pooled48.py", ["--mode", "REDUCE", "--plan", str(paths["pooled_plan"]), "--output", str(paths["pooled_receipt"])]),
    )
    run_command_stage(
        root=root,
        stage="04_stratified_build",
        command=_command(
            "stratified_eval.py",
            [
                "--mode",
                "BUILD",
                "--pooled48",
                str(paths["pooled_receipt"]),
                "--physical-gpus",
                gpu_arg,
                "--output",
                str(paths["stratified_plan"]),
            ],
        ),
    )
    run_job_stage(
        root=root,
        stage="05_stratified_run",
        script_name="stratified_eval.py",
        plan_path=paths["stratified_plan"],
        index_mode=False,
    )
    run_command_stage(
        root=root,
        stage="06_stratified_reduce",
        command=_command(
            "stratified_eval.py",
            [
                "--mode",
                "REDUCE",
                "--pooled48",
                str(paths["pooled_receipt"]),
                "--plan",
                str(paths["stratified_plan"]),
                "--output",
                str(paths["stratified_receipt"]),
            ],
        ),
    )
    run_command_stage(
        root=root,
        stage="07_intervention_build",
        command=_command(
            "intervention_eval.py",
            [
                "--mode",
                "BUILD",
                "--pooled48",
                str(paths["pooled_receipt"]),
                "--stratified",
                str(paths["stratified_receipt"]),
                "--physical-gpus",
                gpu_arg,
                "--output",
                str(paths["intervention_plan"]),
            ],
        ),
    )
    run_job_stage(
        root=root,
        stage="08_intervention_run",
        script_name="intervention_eval.py",
        plan_path=paths["intervention_plan"],
        index_mode=False,
    )
    run_command_stage(
        root=root,
        stage="09_intervention_reduce",
        command=_command(
            "intervention_eval.py",
            [
                "--mode",
                "REDUCE",
                "--pooled48",
                str(paths["pooled_receipt"]),
                "--stratified",
                str(paths["stratified_receipt"]),
                "--plan",
                str(paths["intervention_plan"]),
                "--output",
                str(paths["intervention_receipt"]),
            ],
        ),
    )
    run_command_stage(
        root=root,
        stage="10_route_b_reduce",
        command=_command("route_b.py", ["--mode", "REDUCE", "--plan", str(paths["route_b_plan"]), "--output", str(paths["route_b_receipt"])]),
    )
    run_command_stage(
        root=root,
        stage="11_route_b_analysis_reduce",
        command=_command(
            "route_b_analysis.py",
            [
                "--mode",
                "REDUCE",
                "--pooled48",
                str(paths["pooled_receipt"]),
                "--stratified",
                str(paths["stratified_receipt"]),
                "--intervention",
                str(paths["intervention_receipt"]),
                "--output",
                str(paths["candidate_freeze"]),
            ],
        ),
    )
    return paths


def run_holdout(*, root: str | Path, physical_gpus: Sequence[int], freeze_path: str | Path | None = None) -> dict[str, Path]:
    paths = _paths(root)
    freeze = _absolute(freeze_path or paths["candidate_freeze"])
    gpu_arg = _gpu_argument(physical_gpus)
    run_command_stage(
        root=root,
        stage="12_holdout_plan",
        command=_command(
            "holdout64.py",
            ["--mode", "PLAN", "--freeze", str(freeze), "--output-root", str(paths["holdout_output"]), "--physical-gpus", gpu_arg, "--output", str(paths["holdout_plan"])],
        ),
    )
    run_job_stage(root=root, stage="13_holdout_run", script_name="holdout64.py", plan_path=paths["holdout_plan"], index_mode=True)
    run_command_stage(
        root=root,
        stage="14_holdout_reduce",
        command=_command("holdout64.py", ["--mode", "REDUCE", "--plan", str(paths["holdout_plan"]), "--output", str(paths["holdout_receipt"])]),
    )
    return paths


def run_render(
    *,
    root: str | Path,
    physical_gpus: Sequence[int],
    candidate_ids: Sequence[str],
    freeze_path: str | Path | None = None,
    holdout_path: str | Path | None = None,
) -> dict[str, Path]:
    ids = _parse_candidate_ids(candidate_ids)
    if ids is None:
        raise OrchestratorError("render requires explicit candidate IDs")
    paths = _paths(root)
    freeze = _absolute(freeze_path or paths["candidate_freeze"])
    holdout = _absolute(holdout_path or paths["holdout_receipt"])
    gpu_arg = _gpu_argument(physical_gpus)
    run_command_stage(
        root=root,
        stage="15_render_plan",
        command=_command(
            "render.py",
            ["--mode", "PLAN", "--freeze", str(freeze), "--holdout", str(holdout), "--output-root", str(paths["render_output"]), "--candidate-ids", *ids, "--physical-gpus", gpu_arg, "--output", str(paths["render_plan"])],
        ),
    )
    run_job_stage(root=root, stage="16_render_run", script_name="render.py", plan_path=paths["render_plan"], index_mode=True)
    run_command_stage(
        root=root,
        stage="17_render_reduce",
        command=_command("render.py", ["--mode", "REDUCE", "--plan", str(paths["render_plan"]), "--output", str(paths["render_receipt"])]),
    )
    return paths


def run_final(*, root: str | Path, paths: Mapping[str, Path]) -> dict[str, Any]:
    command = _command(
        "final_analysis.py",
        [
            "--mode",
            "WRITE",
            "--route-b",
            str(paths["candidate_freeze"]),
            "--intervention",
            str(paths["intervention_receipt"]),
            "--holdout",
            str(paths["holdout_receipt"]),
            "--render",
            str(paths["render_receipt"]),
            "--json-output",
            str(paths["final_json"]),
            "--markdown-output",
            str(paths["final_markdown"]),
        ],
    )
    return run_command_stage(root=root, stage="18_final_analysis_write", command=command)


def run_workflow(
    *,
    workflow: str,
    root: str | Path = DEFAULT_ORCHESTRATION_ROOT,
    physical_gpus: Sequence[int] = DEFAULT_PHYSICAL_GPUS,
    candidate_ids: Sequence[str] | None = None,
    freeze_path: str | Path | None = None,
) -> dict[str, Any]:
    manifest = _parse_physical_gpus(physical_gpus)
    if workflow == "ROUTE_B":
        paths = run_route_b(root=root, physical_gpus=manifest)
        return {"workflow": workflow, "paths": {key: str(value) for key, value in paths.items()}}
    if workflow == "HOLDOUT":
        paths = run_holdout(root=root, physical_gpus=manifest, freeze_path=freeze_path)
        return {"workflow": workflow, "paths": {key: str(value) for key, value in paths.items()}}
    if workflow == "RENDER":
        ids = _parse_candidate_ids(candidate_ids)
        if ids is None:
            raise OrchestratorError("RENDER workflow requires one to three explicit candidate IDs")
        paths = run_render(
            root=root,
            physical_gpus=manifest,
            candidate_ids=ids,
            freeze_path=freeze_path,
            holdout_path=_paths(root)["holdout_receipt"],
        )
        return {"workflow": workflow, "paths": {key: str(value) for key, value in paths.items()}}
    if workflow == "FINAL":
        paths = _paths(root)
        return {"workflow": workflow, "result": run_final(root=root, paths=paths)}
    if workflow != "ALL":
        raise OrchestratorError(f"unsupported workflow {workflow}")
    paths = run_route_b(root=root, physical_gpus=manifest)
    holdout_paths = run_holdout(root=root, physical_gpus=manifest, freeze_path=paths["candidate_freeze"])
    paths.update(holdout_paths)
    render_paths = run_render(
        root=root,
        physical_gpus=manifest,
        candidate_ids=_parse_candidate_ids(candidate_ids) or [],
        freeze_path=paths["candidate_freeze"],
        holdout_path=paths["holdout_receipt"],
    )
    paths.update(render_paths)
    return {"workflow": workflow, "result": run_final(root=root, paths=paths)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", choices=("ROUTE_B", "HOLDOUT", "RENDER", "FINAL", "ALL"), required=True)
    parser.add_argument("--orchestration-root", type=Path, default=DEFAULT_ORCHESTRATION_ROOT)
    parser.add_argument("--physical-gpus", nargs="+", default=None, help="ordered unique physical GPUs, subset of 0..7")
    parser.add_argument("--candidate-id", dest="candidate_ids_single", action="append", default=None)
    parser.add_argument("--candidate-ids", dest="candidate_ids_multi", nargs="+", default=None)
    parser.add_argument("--freeze", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        values: list[str] = []
        if args.candidate_ids_single:
            values.extend(args.candidate_ids_single)
        if args.candidate_ids_multi:
            values.extend(args.candidate_ids_multi)
        candidate_ids = _parse_candidate_ids(values or None)
        physical_gpus = _parse_physical_gpus(args.physical_gpus)
        if args.workflow in {"RENDER", "ALL"} and candidate_ids is None:
            raise OrchestratorError(f"{args.workflow} workflow requires one to three explicit candidate IDs")
        result = run_workflow(
            workflow=args.workflow,
            root=args.orchestration_root,
            physical_gpus=physical_gpus,
            candidate_ids=candidate_ids,
            freeze_path=args.freeze,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 POSTFORMAL ORCHESTRATOR FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
