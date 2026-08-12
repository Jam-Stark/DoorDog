"""Fail-fast Route-A row orchestration across the physical GPU pool.

``m22.py`` owns Route-A manifests and the implementation of one row.  This
controller only schedules those already-built rows.  A row is launched with
the exact ``m22.py RUN --subwave ... --only-row ...`` command from the
manifest's sub-wave, and the parent gives the child the ordinary inherited
environment.  At most one child is live for a physical GPU in a wave.

The CPU-only ``PLAN`` mode validates manifests and prints deterministic global
waves without creating an artifact or starting a child.  ``RUN`` is the
runtime path: all rows must finish naturally before the per-sub-wave
``INDEX`` -> analysis -> selection pipeline is called.  A nonzero row or
downstream command is a typed failure; there is no retry, fallback, or polling
loop.  The orchestration receipt is written only after the whole pipeline
passes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_GPU_SUBWAVES,
        V23_LAUNCHER_ROOT,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
except ImportError:  # direct ``python scriptsFORhuman/v23/route_a_gpu_orchestrator.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_GPU_SUBWAVES,
        V23_LAUNCHER_ROOT,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
M22_SCRIPT = Path(__file__).with_name("m22.py")
ANALYSIS_SCRIPT = Path(__file__).with_name("route_a_analysis.py")
SELECTION_SCRIPT = Path(__file__).with_name("route_a_selection.py")

ROUTE_A_ROOT = REPO_ROOT / "logs_eval/base_v23/route_a"
ROUTE_A_LEGAL_PHYSICAL_GPUS = tuple(range(8))
ROUTE_A_SUBWAVE_ORDER = tuple(V23_GPU_SUBWAVES)
MANIFEST_SCHEMA = "a2_piper_v23_route_a_manifest_v1"
ORCHESTRATION_PLAN_SCHEMA = "a2_piper_v23_route_a_gpu_orchestration_plan_v1"
ORCHESTRATION_RECEIPT_SCHEMA = "a2_piper_v23_route_a_gpu_orchestration_receipt_v1"


class RouteAGpuOrchestrationError(V23Error):
    """A Route-A manifest, scheduling, or child process contract is invalid."""

    def __init__(self, message: str, *, evidence: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.evidence = dict(evidence or {})


@dataclass(frozen=True)
class RowJob:
    """One manifest row as a scheduler job."""

    subwave: str
    row_id: str
    physical_gpu: int
    manifest_path: Path
    ordinal: int

    @property
    def command(self) -> tuple[str, ...]:
        # Keep this command shape in sync with m22.py's public CLI.  The
        # manifest's evaluation command is intentionally not reused: m22 RUN
        # is the row job unit and m22 itself applies the row environment.
        return (
            str(PROJECT_PYTHON),
            str(M22_SCRIPT),
            "RUN",
            "--subwave",
            self.subwave,
            "--only-row",
            self.row_id,
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _load_object(path: str | Path) -> dict[str, Any]:
    target = _absolute(path)
    if target.is_symlink() or not target.is_file():
        raise RouteAGpuOrchestrationError(f"Route-A manifest is missing: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RouteAGpuOrchestrationError(f"Route-A manifest is not valid JSON: {target}") from exc
    if not isinstance(payload, dict):
        raise RouteAGpuOrchestrationError(f"Route-A manifest must be a JSON object: {target}")
    return payload


def default_manifest_path(subwave: str) -> Path:
    """Return the canonical m22 manifest path for one sub-wave."""

    if subwave not in ROUTE_A_SUBWAVE_ORDER:
        raise RouteAGpuOrchestrationError(f"unknown Route-A sub-wave: {subwave}")
    seed = V23_GPU_SUBWAVES[subwave]["seed"]
    return ROUTE_A_ROOT / f"seed{seed}" / subwave / "V23_ROUTE_A_MANIFEST.json"


def _validate_subwaves(subwaves: Sequence[str]) -> tuple[str, ...]:
    if not subwaves:
        raise RouteAGpuOrchestrationError("at least one Route-A sub-wave is required")
    unknown = [value for value in subwaves if value not in ROUTE_A_SUBWAVE_ORDER]
    if unknown:
        raise RouteAGpuOrchestrationError(f"unknown Route-A sub-wave(s): {unknown}")
    if len(set(subwaves)) != len(subwaves):
        raise RouteAGpuOrchestrationError("Route-A sub-waves must not be repeated")
    # Downstream analysis/selection is always emitted in the canonical v23
    # order, independent of CLI argument order.
    return tuple(subwave for subwave in ROUTE_A_SUBWAVE_ORDER if subwave in subwaves)


def _validate_gpu(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RouteAGpuOrchestrationError(f"{field} must be an integer physical GPU")
    if value not in ROUTE_A_LEGAL_PHYSICAL_GPUS:
        raise RouteAGpuOrchestrationError(
            f"{field} must be one of {ROUTE_A_LEGAL_PHYSICAL_GPUS}; got {value}"
        )
    return value


def _validate_manifest_payload(
    subwave: str,
    payload: Mapping[str, Any],
    *,
    path: Path,
) -> tuple[RowJob, ...]:
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise RouteAGpuOrchestrationError(f"Route-A manifest schema is not {MANIFEST_SCHEMA}: {path}")
    if payload.get("status") != "BUILT":
        raise RouteAGpuOrchestrationError(f"Route-A manifest is not BUILT: {path}")
    if payload.get("route") != "A" or payload.get("subwave") != subwave:
        raise RouteAGpuOrchestrationError(f"Route-A manifest identity disagrees with {subwave}: {path}")
    spec = V23_GPU_SUBWAVES[subwave]
    if payload.get("seed") != spec["seed"]:
        raise RouteAGpuOrchestrationError(f"Route-A manifest seed disagrees with {subwave}: {path}")

    manifest_gpus = payload.get("physical_gpus")
    if not isinstance(manifest_gpus, list) or not manifest_gpus:
        raise RouteAGpuOrchestrationError(f"Route-A manifest physical_gpus is not a nonempty list: {path}")
    validated_manifest_gpus = tuple(
        _validate_gpu(value, field=f"{path}.physical_gpus[{index}]")
        for index, value in enumerate(manifest_gpus)
    )
    if len(set(validated_manifest_gpus)) != len(validated_manifest_gpus):
        raise RouteAGpuOrchestrationError(f"Route-A manifest physical_gpus contains duplicates: {path}")
    if payload.get("max_live_eval_processes") != len(validated_manifest_gpus):
        raise RouteAGpuOrchestrationError(f"Route-A manifest max_live_eval_processes disagrees: {path}")

    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 40:
        raise RouteAGpuOrchestrationError(f"Route-A manifest must contain exactly 40 rows: {path}")
    if payload.get("row_count") != len(rows):
        raise RouteAGpuOrchestrationError(f"Route-A manifest row_count disagrees: {path}")

    jobs: list[RowJob] = []
    seen_row_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise RouteAGpuOrchestrationError(f"Route-A manifest row {index} is not an object: {path}")
        row_subwave = row.get("subwave")
        if row_subwave != subwave:
            raise RouteAGpuOrchestrationError(f"Route-A manifest row {index} subwave disagrees: {path}")
        row_id = row.get("row_id")
        if not isinstance(row_id, str) or not row_id:
            raise RouteAGpuOrchestrationError(f"Route-A manifest row {index} has no row_id: {path}")
        if row_id in seen_row_ids:
            raise RouteAGpuOrchestrationError(f"Route-A manifest has duplicate row_id {row_id!r}: {path}")
        physical_gpu = _validate_gpu(row.get("physical_gpu"), field=f"{path}.rows[{index}].physical_gpu")
        if physical_gpu not in validated_manifest_gpus:
            raise RouteAGpuOrchestrationError(
                f"{path}.rows[{index}].physical_gpu={physical_gpu} is absent from manifest physical_gpus"
            )
        if row.get("status") != "ROW_READY":
            raise RouteAGpuOrchestrationError(f"Route-A manifest row {row_id!r} is not ROW_READY: {path}")
        seen_row_ids.add(row_id)
        jobs.append(
            RowJob(
                subwave=subwave,
                row_id=row_id,
                physical_gpu=physical_gpu,
                manifest_path=path,
                ordinal=index,
            )
        )
    if not jobs:
        raise RouteAGpuOrchestrationError(f"Route-A manifest has no schedulable rows: {path}")
    return tuple(jobs)


def load_manifest(subwave: str, path: str | Path | None = None) -> tuple[RowJob, ...]:
    """Load one already-built m22 manifest and return validated row jobs."""

    if subwave not in ROUTE_A_SUBWAVE_ORDER:
        raise RouteAGpuOrchestrationError(f"unknown Route-A sub-wave: {subwave}")
    target = _absolute(path) if path is not None else default_manifest_path(subwave)
    return _validate_manifest_payload(subwave, _load_object(target), path=target)


def _waves(jobs: Sequence[RowJob]) -> tuple[tuple[RowJob, ...], ...]:
    """Partition the global queue into deterministic one-row-per-GPU waves.

    Rows retain manifest order.  A scan removes at most one queued row for each
    free physical GPU; this lets disjoint sub-waves fill one shared wave while
    preventing a GPU from being double-booked across sub-waves.
    """

    pending = list(jobs)
    result: list[tuple[RowJob, ...]] = []
    while pending:
        selected: dict[int, RowJob] = {}
        remainder: list[RowJob] = []
        for job in pending:
            if job.physical_gpu not in selected:
                selected[job.physical_gpu] = job
            else:
                remainder.append(job)
        if not selected:
            raise RouteAGpuOrchestrationError("global scheduler could not select a row for any physical GPU")
        result.append(tuple(selected[gpu] for gpu in sorted(selected)))
        pending = remainder
    return tuple(result)


def _manifest_path_map(
    subwaves: Sequence[str],
    manifest_paths: Mapping[str, str | Path] | None = None,
    *,
    manifest_dir: str | Path | None = None,
) -> dict[str, Path]:
    overrides = dict(manifest_paths or {})
    unknown = set(overrides) - set(subwaves)
    if unknown:
        raise RouteAGpuOrchestrationError(f"manifest override has unrequested sub-wave(s): {sorted(unknown)}")
    base = _absolute(manifest_dir) if manifest_dir is not None else None
    paths: dict[str, Path] = {}
    for subwave in subwaves:
        if subwave in overrides:
            paths[subwave] = _absolute(overrides[subwave])
            continue
        if base is None:
            paths[subwave] = default_manifest_path(subwave)
            continue
        direct = base / f"{subwave}.json"
        nested = base / f"seed{V23_GPU_SUBWAVES[subwave]['seed']}" / subwave / "V23_ROUTE_A_MANIFEST.json"
        paths[subwave] = direct if direct.is_file() else nested
    return paths


def _jobs_for_subwaves(
    subwaves: Sequence[str],
    manifest_paths: Mapping[str, str | Path] | None = None,
    *,
    manifest_dir: str | Path | None = None,
) -> tuple[dict[str, Path], tuple[RowJob, ...]]:
    ordered = _validate_subwaves(subwaves)
    paths = _manifest_path_map(ordered, manifest_paths, manifest_dir=manifest_dir)
    jobs: list[RowJob] = []
    for subwave in ordered:
        jobs.extend(load_manifest(subwave, paths[subwave]))
    if len(jobs) != 40 * len(ordered):
        raise RouteAGpuOrchestrationError("Route-A global row count disagrees with selected manifests")
    seen = {(job.subwave, job.row_id) for job in jobs}
    if len(seen) != len(jobs):
        raise RouteAGpuOrchestrationError("Route-A global queue contains duplicate sub-wave/row identities")
    return paths, tuple(jobs)


def _job_payload(job: RowJob) -> dict[str, Any]:
    return {
        "subwave": job.subwave,
        "row_id": job.row_id,
        "physical_gpu": job.physical_gpu,
        "manifest_path": str(job.manifest_path),
        "command": list(job.command),
    }


def _downstream_commands(subwaves: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    commands: list[tuple[str, ...]] = []
    for subwave in _validate_subwaves(subwaves):
        commands.append(
            (
                str(PROJECT_PYTHON),
                str(M22_SCRIPT),
                "INDEX",
                "--subwave",
                subwave,
            ),
        )
        commands.append(
            (
                str(PROJECT_PYTHON),
                str(ANALYSIS_SCRIPT),
                "--subwave",
                subwave,
            )
        )
        commands.append(
            (
                str(PROJECT_PYTHON),
                str(SELECTION_SCRIPT),
                "--subwave",
                subwave,
            )
        )
    return tuple(commands)


def build_plan(
    subwaves: Sequence[str],
    manifest_paths: Mapping[str, str | Path] | None = None,
    *,
    manifest_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate manifests and return a CPU-only deterministic launch plan."""

    ordered = _validate_subwaves(subwaves)
    paths, jobs = _jobs_for_subwaves(ordered, manifest_paths, manifest_dir=manifest_dir)
    waves = _waves(jobs)
    physical_gpus = sorted({job.physical_gpu for job in jobs})
    if not physical_gpus:
        raise RouteAGpuOrchestrationError("Route-A queue has no assigned physical GPUs")
    if any(len({job.physical_gpu for job in wave}) != len(wave) for wave in waves):
        raise RouteAGpuOrchestrationError("global scheduler wave double-books a physical GPU")
    if len(waves[0]) != len(physical_gpus):
        raise RouteAGpuOrchestrationError(
            "global scheduler did not fill the union of assigned physical GPUs in its first wave"
        )
    return {
        "schema": ORCHESTRATION_PLAN_SCHEMA,
        "status": "PLAN",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "A",
        "subwaves": list(ordered),
        "manifest_paths": {subwave: str(paths[subwave]) for subwave in ordered},
        "row_count": len(jobs),
        "physical_gpus": physical_gpus,
        "max_live_row_processes": len(physical_gpus),
        "scheduling": "deterministic global waves; one live row per manifest-assigned physical GPU; no retry",
        "waves": [
            {
                "wave_ordinal": index,
                "physical_gpus": [job.physical_gpu for job in wave],
                "rows": [_job_payload(job) for job in wave],
            }
            for index, wave in enumerate(waves)
        ],
        "downstream_commands": [list(command) for command in _downstream_commands(ordered)],
        "no_retry": True,
    }


def plan(
    subwaves: Sequence[str],
    manifest_paths: Mapping[str, str | Path] | None = None,
    *,
    manifest_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Alias for callers that prefer the shorter planning API."""

    return build_plan(subwaves, manifest_paths, manifest_dir=manifest_dir)


def _safe_component(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in value)


def _new_artifact_root() -> tuple[str, Path]:
    run_id = _run_id()
    root = REPO_ROOT / V23_LAUNCHER_ROOT / "route_a_gpu_orchestrator" / run_id
    root.mkdir(parents=True, exist_ok=False)
    (root / "rows").mkdir()
    (root / "downstream").mkdir()
    return run_id, root


def _run_process(
    command: Sequence[str],
    *,
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    """Run one child with inherited environment and natural blocking wait."""

    started = _now()
    environment = os.environ.copy()
    with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
        try:
            process = subprocess.Popen(
                list(command),
                cwd=REPO_ROOT,
                env=environment,
                stdout=stdout,
                stderr=stderr,
            )
        except OSError as exc:
            ended = _now()
            return {
                "command": list(command),
                "started_at_utc": started,
                "ended_at_utc": ended,
                "return_code": None,
                "natural_completion": False,
                "spawn_error": str(exc),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        return_code = process.wait()
    ended = _now()
    return {
        "command": list(command),
        "pid": process.pid,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "return_code": return_code,
        "natural_completion": return_code == 0,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _run_wave(
    wave: Sequence[RowJob],
    *,
    wave_ordinal: int,
    artifact_root: Path,
) -> list[dict[str, Any]]:
    """Launch a bounded wave, then wait for every child to exit naturally."""

    results: list[dict[str, Any]] = []
    # Launch all rows before waiting so a full union-GPU wave is genuinely
    # concurrent.  The deterministic wait order only affects receipt ordering.
    processes: list[tuple[RowJob, subprocess.Popen[Any] | None, Any, Any, str, Path, Path]] = []
    for job in wave:
        prefix = f"{wave_ordinal:04d}_{_safe_component(job.subwave)}_{_safe_component(job.row_id)}"
        stdout_path = artifact_root / "rows" / f"{prefix}.stdout.log"
        stderr_path = artifact_root / "rows" / f"{prefix}.stderr.log"
        started = _now()
        stdout = stdout_path.open("x", encoding="utf-8")
        stderr = stderr_path.open("x", encoding="utf-8")
        try:
            process = subprocess.Popen(
                list(job.command),
                cwd=REPO_ROOT,
                env=os.environ.copy(),
                stdout=stdout,
                stderr=stderr,
            )
        except OSError as exc:
            stdout.close()
            stderr.close()
            processes.append((job, None, None, None, started, stdout_path, stderr_path))
            results.append(
                {
                    **_job_payload(job),
                    "wave_ordinal": wave_ordinal,
                    "started_at_utc": started,
                    "ended_at_utc": _now(),
                    "status": "FAIL",
                    "return_code": None,
                    "natural_completion": False,
                    "spawn_error": str(exc),
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                }
            )
            continue
        processes.append((job, process, stdout, stderr, started, stdout_path, stderr_path))

    for job, process, stdout, stderr, started, stdout_path, stderr_path in processes:
        if process is None:
            continue
        return_code = process.wait()
        stdout.close()
        stderr.close()
        results.append(
            {
                **_job_payload(job),
                "wave_ordinal": wave_ordinal,
                "pid": process.pid,
                "started_at_utc": started,
                "ended_at_utc": _now(),
                "status": "PASS" if return_code == 0 else "FAIL",
                "return_code": return_code,
                "natural_completion": return_code == 0,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )
    # Preserve wave/manifest ordering instead of grouping spawn failures first.
    by_id = {(item["subwave"], item["row_id"]): item for item in results}
    return [by_id[(job.subwave, job.row_id)] for job in wave]


def _run_downstream(
    subwaves: Sequence[str],
    *,
    artifact_root: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    command_index = 0
    for subwave in _validate_subwaves(subwaves):
        stage_commands = (
            (
                "INDEX",
                (
                    str(PROJECT_PYTHON),
                    str(M22_SCRIPT),
                    "INDEX",
                    "--subwave",
                    subwave,
                ),
            ),
            (
                "ANALYSIS",
                (
                    str(PROJECT_PYTHON),
                    str(ANALYSIS_SCRIPT),
                    "--subwave",
                    subwave,
                ),
            ),
            (
                "SELECTION",
                (
                    str(PROJECT_PYTHON),
                    str(SELECTION_SCRIPT),
                    "--subwave",
                    subwave,
                ),
            ),
        )
        for stage, command in stage_commands:
            prefix = f"{command_index:04d}_{_safe_component(subwave)}_{stage.lower()}"
            result = _run_process(
                command,
                stdout_path=artifact_root / "downstream" / f"{prefix}.stdout.log",
                stderr_path=artifact_root / "downstream" / f"{prefix}.stderr.log",
            )
            result.update(
                {
                    "subwave": subwave,
                    "stage": stage,
                    "status": "PASS" if result.get("return_code") == 0 else "FAIL",
                }
            )
            results.append(result)
            command_index += 1
            if result.get("return_code") != 0:
                raise RouteAGpuOrchestrationError(
                    f"Route-A downstream {subwave} {stage} failed; no receipt written",
                    evidence={"downstream": results},
                )
    return results


def run(
    subwaves: Sequence[str],
    manifest_paths: Mapping[str, str | Path] | None = None,
    *,
    manifest_dir: str | Path | None = None,
    receipt: str | Path | None = None,
) -> dict[str, Any]:
    """Run all row waves and deterministic downstream reducers."""

    started = _now()
    ordered = _validate_subwaves(subwaves)
    paths, jobs = _jobs_for_subwaves(ordered, manifest_paths, manifest_dir=manifest_dir)
    waves = _waves(jobs)
    physical_gpus = sorted({job.physical_gpu for job in jobs})
    explicit_receipt = _absolute(receipt) if receipt is not None else None
    if explicit_receipt is not None and (explicit_receipt.exists() or explicit_receipt.is_symlink()):
        raise RouteAGpuOrchestrationError(f"refusing to overwrite existing orchestration receipt: {explicit_receipt}")
    run_id, artifact_root = _new_artifact_root()
    row_results: list[dict[str, Any]] = []
    for wave_ordinal, wave in enumerate(waves):
        wave_results = _run_wave(wave, wave_ordinal=wave_ordinal, artifact_root=artifact_root)
        row_results.extend(wave_results)
        failures = [item for item in wave_results if item.get("return_code") != 0]
        if failures:
            raise RouteAGpuOrchestrationError(
                f"Route-A row wave {wave_ordinal} failed; no INDEX/analysis/selection was run",
                evidence={
                    "run_id": run_id,
                    "artifact_root": str(artifact_root),
                    "failed_rows": failures,
                    "row_results": row_results,
                },
            )

    downstream_results = _run_downstream(ordered, artifact_root=artifact_root)
    ended = _now()
    target = explicit_receipt or artifact_root / "V23_ROUTE_A_GPU_ORCHESTRATION_RECEIPT.json"
    payload = {
        "schema": ORCHESTRATION_RECEIPT_SCHEMA,
        "status": "PASS",
        "recorded_at_utc": ended,
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "A",
        "run_id": run_id,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "artifact_root": str(artifact_root),
        "receipt_path": str(target),
        "subwaves": list(ordered),
        "manifest_paths": {subwave: str(paths[subwave]) for subwave in ordered},
        "row_count": len(row_results),
        "physical_gpus": physical_gpus,
        "max_live_row_processes": len(physical_gpus),
        "waves": [
            {
                "wave_ordinal": index,
                "physical_gpus": [job.physical_gpu for job in wave],
                "rows": [
                    {"subwave": job.subwave, "row_id": job.row_id, "physical_gpu": job.physical_gpu}
                    for job in wave
                ],
            }
            for index, wave in enumerate(waves)
        ],
        "row_results": row_results,
        "downstream_results": downstream_results,
        "commands": [item["command"] for item in row_results]
        + [item["command"] for item in downstream_results],
        "scheduling": "global deterministic waves; one live row per manifest-assigned physical GPU; no retry",
        "no_retry": True,
        "natural_completion": all(item.get("natural_completion") is True for item in row_results + downstream_results),
    }
    write_json(target, payload)
    return payload


def _parse_subwaves(args: argparse.Namespace) -> tuple[str, ...]:
    values: list[str] = []
    values.extend(args.subwave or [])
    if args.subwaves:
        values.extend(args.subwaves)
    return _validate_subwaves(values)


def _parse_manifest_overrides(values: Sequence[str] | None) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for raw in values or []:
        if "=" not in raw:
            raise RouteAGpuOrchestrationError("--manifest values must use SUBWAVE=PATH")
        subwave, path = raw.split("=", 1)
        if not subwave or not path:
            raise RouteAGpuOrchestrationError("--manifest values must use SUBWAVE=PATH")
        if subwave in overrides:
            raise RouteAGpuOrchestrationError(f"duplicate --manifest override for {subwave}")
        overrides[subwave] = _absolute(path)
    return overrides


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode_arg", nargs="?", choices=("PLAN", "RUN"))
    parser.add_argument("--mode", dest="mode_option", choices=("PLAN", "RUN"))
    parser.add_argument("--subwave", action="append", help="Route-A sub-wave; repeat for multiple sub-waves")
    parser.add_argument("--subwaves", nargs="+", help="Route-A sub-waves supplied as one list")
    parser.add_argument("--manifest", action="append", metavar="SUBWAVE=PATH", help="override one m22 manifest")
    parser.add_argument("--manifest-dir", type=Path, help="fixture directory containing SUBWAVE.json manifests")
    parser.add_argument("--receipt", type=Path, help="RUN receipt path; defaults under launcher artifacts")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    mode = args.mode_option or args.mode_arg
    if mode is None:
        parser.error("PLAN or RUN is required")
    try:
        subwaves = _parse_subwaves(args)
        overrides = _parse_manifest_overrides(args.manifest)
        if args.receipt is not None and mode == "PLAN":
            raise RouteAGpuOrchestrationError("--receipt is only valid with RUN")
        if mode == "PLAN":
            payload = build_plan(subwaves, overrides, manifest_dir=args.manifest_dir)
        else:
            payload = run(
                subwaves,
                overrides,
                manifest_dir=args.manifest_dir,
                receipt=args.receipt,
            )
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 ROUTE_A_GPU_ORCHESTRATOR {mode} FAIL: {exc}", file=sys.stderr)
        evidence = getattr(exc, "evidence", None)
        if evidence:
            print(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
