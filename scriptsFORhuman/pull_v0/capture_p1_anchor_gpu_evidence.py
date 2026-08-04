#!/usr/bin/env python3
"""Capture CPU-side GPU resource evidence for bounded pull-anchor attempts.

This tool only queries ``nvidia-smi`` and reads the selected runtime log.  It
never starts, stops, or signals a runtime process.  Canonical evidence is
written only after the plan, device topology, tenant attribution, and (for
steady mode) first-step boundary checks all pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
ATTEMPT19_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_PLAN.json"
ATTEMPT19_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_LAUNCH_OCCUPANCY.json"
)
ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_STEADY_STATE_FOOTPRINT.json"
)
ATTEMPT20_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_PLAN.json"
ATTEMPT20_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_LAUNCH_OCCUPANCY.json"
)
ATTEMPT20_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_STEADY_STATE_FOOTPRINT.json"
)

ATTEMPT = 19
SELECTED_COMPUTE_PHYSICAL_DEVICE = 2
AUTHORIZED_COMPUTE_PHYSICAL_DEVICES = [2, 3]
UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES = [0, 1, 4, 5, 6, 7]
ALL_PHYSICAL_DEVICES = list(range(8))
NON_LEASED_STOP_THRESHOLD_MIB = 1024
PMON_SOURCE = "nvidia-smi pmon -i 0,1,2,3,4,5,6,7 -c 1 -s um"
PMON_PROCESS_TYPES = {"C", "G", "C+G"}
PMON_NOT_REPORTED = "NOT_REPORTED"
PMON_REPORTED = "REPORTED"
PMON_NOT_APPLICABLE = "NOT_APPLICABLE"

GPU_QUERY = (
    "nvidia-smi",
    "--query-gpu=index,uuid,memory.used,utilization.gpu",
    "--format=csv,noheader,nounits",
)
COMPUTE_QUERY = (
    "nvidia-smi",
    "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
    "--format=csv,noheader,nounits",
)
PMON_QUERY = (
    "nvidia-smi",
    "pmon",
    "-i",
    ",".join(str(index) for index in ALL_PHYSICAL_DEVICES),
    "-c",
    "1",
    "-s",
    "um",
)
EXPECTED_ATTEMPT19_OUTPUT_ROOT = Path(
    "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt19"
)
EXPECTED_ATTEMPT19_EVAL_OUTPUT_DIR = EXPECTED_ATTEMPT19_OUTPUT_ROOT / "eval"
ANSI_ESCAPE_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
KIT_GRAPHICS_RE = re.compile(r"Graphics API:\s*Vulkan\s*$")
KIT_GPU_HEADER_RE = re.compile(r"^\|\s*GPU\s*\|.*\|\s*Active\s*\|")
KIT_GPU_ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*)\|"
)
KIT_SEPARATOR_RE = re.compile(r"^\|[-=]+\|?$|^\|[-=| ]+\|$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be a JSON object.")
    return value


def _finite_nonnegative(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise RuntimeError(f"{label} must be a finite non-negative number.")
    return float(value)


def _parse_nonnegative_number(raw: str, label: str) -> float:
    value = raw.strip()
    if not value or value.upper() in {"N/A", "NA", "UNKNOWN"}:
        raise RuntimeError(f"nvidia-smi returned an unknown {label}: {raw!r}")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(f"nvidia-smi returned an invalid {label}: {raw!r}") from exc
    return _finite_nonnegative(parsed, label)


def _parse_hkt(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} must be a non-empty HKT timestamp.")
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S HKT").replace(
            tzinfo=ZoneInfo("Asia/Hong_Kong")
        )
    except ValueError as exc:
        raise RuntimeError(f"{label} must use YYYY-MM-DD HH:MM:SS HKT.") from exc


def _validate_fresh_capture(
    value: Any,
    *,
    now: datetime | None = None,
    label: str = "launch occupancy",
    attempt: int = ATTEMPT,
) -> None:
    captured = _parse_hkt(value, f"{label} captured_at_hkt")
    reference = datetime.now(ZoneInfo("Asia/Hong_Kong")) if now is None else now
    age = (reference - captured).total_seconds()
    if age < -30.0:
        raise RuntimeError(f"Attempt{attempt} {label} capture timestamp is in the future.")
    if age > 300.0:
        raise RuntimeError(
            f"Attempt{attempt} {label} capture is stale; it must be captured during the bounded evidence window."
        )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Evidence path must be a regular non-symlink file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Evidence path is not readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Evidence path must contain a JSON object: {path}")
    return value


def _artifact(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Artifact must be a regular non-symlink file: {path}")
    label = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return {"path": label, "sha256": _sha256(path)}


def _plan_identity(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in plan.items()
        if key not in {"generated_at_hkt", "plan_sha256"}
    }


def _load_plan(plan_path: Path, *, attempt: int = ATTEMPT) -> tuple[dict[str, Any], dict[str, str]]:
    if not plan_path.is_absolute():
        plan_path = ROOT / plan_path
    if plan_path.is_symlink():
        raise RuntimeError(f"Attempt{attempt} plan must be a regular non-symlink file.")
    plan_path = plan_path.resolve()
    expected_plan_path = ATTEMPT19_PLAN_PATH if attempt == ATTEMPT else ATTEMPT20_PLAN_PATH
    if plan_path != expected_plan_path.resolve():
        raise RuntimeError(f"Attempt{attempt} evidence accepts only the canonical Attempt{attempt} plan path.")
    plan = _read_json(plan_path)
    if plan.get("attempt") != attempt or plan.get("status") != "READY":
        raise RuntimeError(f"Attempt{attempt} plan identity or status is not READY.")
    plan_sha256 = plan.get("plan_sha256")
    if not isinstance(plan_sha256, str) or not plan_sha256:
        raise RuntimeError(f"Attempt{attempt} plan must include a non-empty plan_sha256 identity.")
    canonical_identity = _canonical_sha256(_plan_identity(plan))
    if plan_sha256 != canonical_identity:
        raise RuntimeError(
            f"Attempt{attempt} plan_sha256 does not match the canonical plan identity: "
            f"stored={plan_sha256}, computed={canonical_identity}."
        )
    artifact = _artifact(plan_path)
    return plan, {**artifact, "plan_sha256": plan_sha256}


def _validate_plan_binding(
    evidence: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    label: str,
    attempt: int = ATTEMPT,
) -> None:
    binding = _require_mapping(evidence.get("plan"), f"{label}.plan")
    for field in ("path", "sha256", "plan_sha256"):
        if binding.get(field) != plan_artifact[field]:
            raise RuntimeError(f"Attempt{attempt} {label} plan binding mismatch for {field}.")
    if plan.get("plan_sha256") != binding.get("plan_sha256"):
        raise RuntimeError(f"Attempt{attempt} {label} plan identity does not match the prepared plan.")


def _parse_csv_rows(raw: str, *, label: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in csv.reader(io.StringIO(raw)):
        if not row or not any(cell.strip() for cell in row):
            continue
        rows.append([cell.strip() for cell in row])
    if not rows and label == "compute processes":
        return []
    return rows


def parse_gpu_query_output(raw: str) -> dict[int, dict[str, Any]]:
    """Parse exact ``nvidia-smi --query-gpu`` CSV output."""
    rows = _parse_csv_rows(raw, label="GPU inventory")
    devices: dict[int, dict[str, Any]] = {}
    for row_index, row in enumerate(rows):
        if len(row) != 4:
            raise RuntimeError(f"GPU inventory row {row_index} must contain exactly four columns.")
        try:
            index = int(row[0])
        except ValueError as exc:
            raise RuntimeError(f"GPU inventory row {row_index} has an invalid physical index.") from exc
        if index in devices:
            raise RuntimeError(f"GPU inventory contains duplicate physical GPU{index}.")
        uuid = row[1].strip()
        if not uuid or uuid.upper() in {"N/A", "NA", "UNKNOWN"}:
            raise RuntimeError(f"GPU inventory GPU{index} has an unknown UUID.")
        devices[index] = {
            "index": index,
            "uuid": uuid,
            "memory_used_mib": _parse_nonnegative_number(row[2], f"GPU{index} memory_used_mib"),
            "utilization_gpu_percent": _parse_nonnegative_number(
                row[3], f"GPU{index} utilization_gpu_percent"
            ),
        }
        if devices[index]["utilization_gpu_percent"] > 100.0:
            raise RuntimeError(f"GPU inventory GPU{index} utilization exceeds 100%.")
    if set(devices) != set(ALL_PHYSICAL_DEVICES):
        raise RuntimeError("GPU inventory must cover physical GPU indices 0-7 exactly.")
    return devices


def parse_compute_query_output(raw: str) -> list[dict[str, Any]]:
    """Parse exact ``nvidia-smi --query-compute-apps`` CSV output."""
    if raw.strip().lower() in {"no running processes found", "no running processes found."}:
        return []
    rows = _parse_csv_rows(raw, label="compute processes")
    processes: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for row_index, row in enumerate(rows):
        if len(row) != 4:
            raise RuntimeError(
                f"Compute process row {row_index} must contain exactly four columns; unknown output is not classified."
            )
        uuid = row[0].strip()
        if not uuid or uuid.upper() in {"N/A", "NA", "UNKNOWN"}:
            raise RuntimeError(f"Compute process row {row_index} has an unknown GPU UUID.")
        try:
            pid = int(row[1])
        except ValueError as exc:
            raise RuntimeError(f"Compute process row {row_index} has an invalid PID.") from exc
        if pid <= 0:
            raise RuntimeError(f"Compute process row {row_index} PID must be positive.")
        name = row[2].strip()
        if not name or name.upper() in {"N/A", "NA", "UNKNOWN"}:
            raise RuntimeError(f"Compute process row {row_index} has an unknown process name.")
        memory_used_mib = _parse_nonnegative_number(
            row[3], f"compute process row {row_index} used_memory_mib"
        )
        key = (uuid, pid)
        if key in seen:
            raise RuntimeError(f"Compute process inventory contains duplicate GPU/PID {key!r}.")
        seen.add(key)
        processes.append(
            {
                "gpu_uuid": uuid,
                "pid": pid,
                "name": name,
                "memory_used_mib": memory_used_mib,
            }
        )
    return processes


def _parse_pmon_metric(
    raw: str,
    label: str,
    *,
    allow_not_reported: bool = False,
) -> tuple[float | None, str]:
    value = raw.strip()
    if value == "-":
        if allow_not_reported:
            return None, PMON_NOT_REPORTED
        raise RuntimeError(f"nvidia-smi pmon returned an unknown {label}: {raw!r}")
    if value in {"", "N/A", "NA", "UNKNOWN"}:
        raise RuntimeError(f"nvidia-smi pmon returned an unknown {label}: {raw!r}")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(f"nvidia-smi pmon returned an invalid {label}: {raw!r}") from exc
    return _finite_nonnegative(parsed, label), PMON_REPORTED


def parse_pmon_output(raw: str) -> dict[int, list[dict[str, Any]]]:
    """Parse one complete all-device ``nvidia-smi pmon -s um`` snapshot."""
    lines = [_strip_ansi(line).rstrip() for line in raw.splitlines() if line.strip()]
    if len(lines) < 3:
        raise RuntimeError("nvidia-smi pmon output is missing its complete header or device rows.")
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if " ".join(line.lower().split())
            == "# gpu pid type sm mem enc dec jpg ofa fb ccpm command"
        ),
        None,
    )
    if header_index is None or header_index + 1 >= len(lines):
        raise RuntimeError("nvidia-smi pmon output has an unknown or partial header.")
    units = " ".join(lines[header_index + 1].lower().split())
    if units != "# idx # c/g % % % % % % mb mb name":
        raise RuntimeError("nvidia-smi pmon output has an unknown units header.")
    rows: dict[int, list[dict[str, Any]]] = {}
    for row_index, line in enumerate(lines[header_index + 2 :], start=header_index + 2):
        if line.startswith("#"):
            raise RuntimeError(f"nvidia-smi pmon output contains an unexpected header at line {row_index}.")
        fields = line.split(maxsplit=11)
        if len(fields) != 12:
            raise RuntimeError(
                f"nvidia-smi pmon row {row_index} is partial; expected 12 columns including command."
            )
        try:
            gpu_index = int(fields[0])
        except ValueError as exc:
            raise RuntimeError(f"nvidia-smi pmon row {row_index} has an invalid GPU index.") from exc
        if gpu_index not in ALL_PHYSICAL_DEVICES:
            raise RuntimeError("nvidia-smi pmon contains an invalid physical GPU index.")
        rows.setdefault(gpu_index, [])
        pid_field, type_field = fields[1].strip(), fields[2].strip()
        if pid_field == "-":
            if rows[gpu_index]:
                raise RuntimeError(f"nvidia-smi pmon GPU{gpu_index} mixes empty and process rows.")
            if any(field != "-" for field in fields[2:]):
                raise RuntimeError(
                    f"nvidia-smi pmon GPU{gpu_index} no-process row contains unknown context metrics."
                )
            rows[gpu_index] = [
                {
                    "gpu_index": gpu_index,
                    "pid": None,
                    "type": None,
                    "sm_util_percent": None,
                    "sm_util_percent_state": PMON_NOT_APPLICABLE,
                    "memory_util_percent": None,
                    "memory_util_percent_state": PMON_NOT_APPLICABLE,
                    "fb_memory_mib": None,
                    "fb_memory_mib_state": PMON_NOT_APPLICABLE,
                    "command": None,
                    "source": PMON_SOURCE,
                }
            ]
            continue
        try:
            pid = int(pid_field)
        except ValueError as exc:
            raise RuntimeError(f"nvidia-smi pmon row {row_index} has an invalid PID.") from exc
        if pid <= 0 or type_field not in PMON_PROCESS_TYPES:
            raise RuntimeError(f"nvidia-smi pmon row {row_index} has an unknown PID/type context.")
        command = fields[11].strip()
        if not command or command in {"-", "N/A", "NA", "UNKNOWN"}:
            raise RuntimeError(f"nvidia-smi pmon row {row_index} has an unknown command.")
        if any(item["pid"] == pid for item in rows[gpu_index]):
            raise RuntimeError(f"nvidia-smi pmon GPU{gpu_index} contains duplicate PID{pid} rows.")
        sm_util_percent, sm_state = _parse_pmon_metric(
            fields[3],
            f"GPU{gpu_index} PID{pid} SM utilization",
            allow_not_reported=True,
        )
        memory_util_percent, memory_state = _parse_pmon_metric(
            fields[4],
            f"GPU{gpu_index} PID{pid} memory utilization",
            allow_not_reported=True,
        )
        fb_memory_mib, fb_state = _parse_pmon_metric(
            fields[9], f"GPU{gpu_index} PID{pid} FB memory"
        )
        rows[gpu_index].append(
            {
                "gpu_index": gpu_index,
                "pid": pid,
                "type": type_field,
                "sm_util_percent": sm_util_percent,
                "sm_util_percent_state": sm_state,
                "memory_util_percent": memory_util_percent,
                "memory_util_percent_state": memory_state,
                "fb_memory_mib": fb_memory_mib,
                "fb_memory_mib_state": fb_state,
                "command": command,
                "source": PMON_SOURCE,
            }
        )
    if set(rows) != set(ALL_PHYSICAL_DEVICES):
        raise RuntimeError("nvidia-smi pmon output must cover physical GPU indices 0-7 exactly.")
    return rows


parse_pmon_query_output = parse_pmon_output


def _default_query_runner(
    argv: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def query_gpu_snapshot(
    *,
    query_runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[int, dict[str, Any]]:
    """Query all physical GPUs and compute processes without mutating runtime state."""
    runner = _default_query_runner if query_runner is None else query_runner
    gpu_result = runner(GPU_QUERY)
    if gpu_result.returncode != 0:
        raise RuntimeError(f"nvidia-smi GPU query failed with return code {gpu_result.returncode}.")
    devices = parse_gpu_query_output(gpu_result.stdout)
    process_result = runner(COMPUTE_QUERY)
    if process_result.returncode != 0:
        raise RuntimeError(
            f"nvidia-smi compute-process query failed with return code {process_result.returncode}."
        )
    processes = parse_compute_query_output(process_result.stdout)
    by_uuid = {device["uuid"]: device["index"] for device in devices.values()}
    for process in processes:
        if process["gpu_uuid"] not in by_uuid:
            raise RuntimeError(
                f"Compute process references unknown GPU UUID {process['gpu_uuid']!r}; refusing classification."
            )
        process.setdefault("gpu_index", by_uuid[process["gpu_uuid"]])
    for device in devices.values():
        device["compute_processes"] = [
            {
                "pid": process["pid"],
                "name": process["name"],
                "memory_used_mib": process["memory_used_mib"],
            }
            for process in processes
            if process["gpu_index"] == device["index"]
        ]
    pmon_result = runner(PMON_QUERY)
    if pmon_result.returncode != 0:
        raise RuntimeError(
            f"nvidia-smi pmon query failed with return code {pmon_result.returncode}."
        )
    pmon_processes = parse_pmon_output(pmon_result.stdout)
    for index, device in devices.items():
        device["pmon_processes"] = pmon_processes[index]
    return devices


def _sorted_processes(processes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "pid": int(process["pid"]),
            "name": str(process["name"]),
            "memory_used_mib": float(process["memory_used_mib"]),
        }
        for process in sorted(processes, key=lambda value: int(value["pid"]))
    ]


def _is_kit_separator(line: str) -> bool:
    compact = line.replace("|", "").strip()
    return line.startswith("|") and bool(compact) and set(compact) <= {"-", "="}


def _parse_kit_vulkan_tables(
    lines: Sequence[str], *, app_launcher_index: int, attempt: int = ATTEMPT
) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    cursor = app_launcher_index + 1
    while cursor < len(lines):
        if not KIT_GRAPHICS_RE.search(lines[cursor].strip()):
            cursor += 1
            continue
        graphics_index = cursor
        header_index = next(
            (
                index
                for index in range(graphics_index + 1, min(len(lines), graphics_index + 24))
                if KIT_GPU_HEADER_RE.match(lines[index].strip())
            ),
            None,
        )
        if header_index is None:
            raise RuntimeError(f"Attempt{attempt} runtime log contains a partial Kit Vulkan GPU table header.")
        rows: list[dict[str, Any]] = []
        table_end: int | None = None
        for index in range(header_index + 1, len(lines)):
            match = KIT_GPU_ROW_RE.match(lines[index].strip())
            if match:
                physical_device = int(match.group(1))
                if physical_device not in ALL_PHYSICAL_DEVICES or any(
                    row["physical_device"] == physical_device for row in rows
                ):
                    raise RuntimeError(f"Attempt{attempt} Kit Vulkan GPU table has duplicate or invalid device rows.")
                rows.append(
                    {
                        "physical_device": physical_device,
                        "name": match.group(2).strip(),
                        "active": match.group(3).strip(),
                        "source_line_number": index + 1,
                        "source_line": lines[index],
                    }
                )
                continue
            if len(rows) == len(ALL_PHYSICAL_DEVICES) and _is_kit_separator(lines[index].strip()):
                table_end = index
                break
            if rows and not lines[index].strip().startswith("|"):
                raise RuntimeError(f"Attempt{attempt} Kit Vulkan GPU table contains an unexpected non-table line.")
        if table_end is None or len(rows) != len(ALL_PHYSICAL_DEVICES):
            raise RuntimeError(f"Attempt{attempt} runtime log contains an incomplete Kit Vulkan GPU table.")
        if [row["physical_device"] for row in rows] != ALL_PHYSICAL_DEVICES:
            raise RuntimeError(f"Attempt{attempt} Kit Vulkan GPU table rows must cover physical GPUs 0-7 in order.")
        active_devices = [
            row["physical_device"]
            for row in rows
            if row["active"].startswith("Yes")
        ]
        if active_devices != [SELECTED_COMPUTE_PHYSICAL_DEVICE]:
            raise RuntimeError(
                f"Attempt{attempt} Kit Vulkan GPU table must identify active physical devices exactly [2]."
            )
        tables.append(
            {
                "source_line_number_start": graphics_index + 1,
                "source_line_number_end": table_end + 1,
                "source_lines": list(lines[graphics_index : table_end + 1]),
                "rows": rows,
                "active_physical_devices": active_devices,
            }
        )
        cursor = table_end + 1
    if not tables:
        raise RuntimeError(f"Attempt{attempt} runtime log contains no complete Kit Vulkan GPU table after AppLauncher.")
    return tables


def parse_runtime_log_contract(log_text: str, *, attempt: int = ATTEMPT) -> dict[str, Any]:
    """Derive the exact AppLauncher, environment, Kit, and evaluation boundary evidence."""
    lines = [_strip_ansi(line).rstrip() for line in log_text.splitlines()]
    app_matches = [
        (index, line, int(match.group(1)))
        for index, line in enumerate(lines)
        if (match := re.search(r"^\[INFO\]\[AppLauncher\]: Using device: cuda:(\d+)\s*$", line))
    ]
    if len(app_matches) != 1 or app_matches[0][2] != SELECTED_COMPUTE_PHYSICAL_DEVICE:
        raise RuntimeError(f"Attempt{attempt} runtime log must contain exactly AppLauncher `Using device: cuda:2`.")
    environment_matches = [
        (index, line, int(match.group(1)))
        for index, line in enumerate(lines)
        if (match := re.search(r"Environment device\s+:\s+cuda:(\d+)\s*$", line))
    ]
    if len(environment_matches) != 1 or environment_matches[0][2] != SELECTED_COMPUTE_PHYSICAL_DEVICE:
        raise RuntimeError(f"Attempt{attempt} runtime log must contain exactly Environment device : cuda:2.")
    boundary = "Starting evaluation with one episode per environment"
    boundary_matches = [
        (index, line)
        for index, line in enumerate(lines)
        if line == boundary
    ]
    if len(boundary_matches) != 1:
        raise RuntimeError(
            f"Attempt{attempt} runtime log must contain exactly the first simulation boundary line: "
            f"{boundary!r}."
        )
    app_index, app_line, app_device = app_matches[0]
    tables = _parse_kit_vulkan_tables(lines, app_launcher_index=app_index, attempt=attempt)
    return {
        "app_launcher": {
            "line_number": app_index + 1,
            "source_line": app_line,
            "device": f"cuda:{app_device}",
        },
        "environment": {
            "line_number": environment_matches[0][0] + 1,
            "source_line": environment_matches[0][1],
            "device": f"cuda:{environment_matches[0][2]}",
        },
        "first_simulation_step_boundary": {
            "line_number": boundary_matches[0][0] + 1,
            "source_line": boundary_matches[0][1],
            "exact_text": boundary,
        },
        "kit_vulkan_tables_after_app_launcher": tables,
    }


def _default_proc_reader(pid: int, *, attempt: int = ATTEMPT) -> dict[str, Any]:
    proc_path = Path("/proc") / str(pid)
    if not proc_path.is_dir():
        raise RuntimeError(f"Attempt{attempt} process PID {pid} is not live in /proc.")
    try:
        raw_cmdline = (proc_path / "cmdline").read_bytes()
        status_text = (proc_path / "status").read_text(encoding="utf-8", errors="replace")
        cwd = os.readlink(proc_path / "cwd")
    except OSError as exc:
        raise RuntimeError(f"Attempt{attempt} process PID {pid} identity cannot be read from /proc.") from exc
    command = [part.decode("utf-8", errors="replace") for part in raw_cmdline.split(b"\0") if part]
    if not command:
        raise RuntimeError(f"Attempt{attempt} process PID {pid} has an empty /proc cmdline.")
    ppid_match = re.search(r"^PPid:\s*(\d+)\s*$", status_text, re.MULTILINE)
    state_match = re.search(r"^State:\s*(.+)$", status_text, re.MULTILINE)
    if ppid_match is None:
        raise RuntimeError(f"Attempt{attempt} process PID {pid} status is missing PPid.")
    return {
        "pid": pid,
        "ppid": int(ppid_match.group(1)),
        "cmdline": command,
        "cwd": cwd,
        "state": state_match.group(1).strip() if state_match else None,
    }


def _normalize_proc_snapshot(
    raw: Mapping[str, Any], *, expected_pid: int, attempt: int = ATTEMPT
) -> dict[str, Any]:
    pid = raw.get("pid", expected_pid)
    ppid = raw.get("ppid")
    command = raw.get("cmdline")
    cwd = raw.get("cwd")
    if pid != expected_pid or isinstance(ppid, bool) or not isinstance(ppid, int) or ppid < 0:
        raise RuntimeError(f"Attempt{attempt} /proc identity has an invalid PID/PPid for {expected_pid}.")
    if isinstance(command, str):
        command = [part for part in command.split("\0") if part]
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(part, str) or not part for part in command)
    ):
        raise RuntimeError(f"Attempt{attempt} /proc PID{expected_pid} cmdline is missing or malformed.")
    if not isinstance(cwd, str) or not cwd:
        raise RuntimeError(f"Attempt{attempt} /proc PID{expected_pid} cwd is missing or malformed.")
    state = raw.get("state")
    if state is not None and (
        not isinstance(state, str)
        or not state.strip()
        or state.lstrip()[0].upper() in {"Z", "X"}
    ):
        raise RuntimeError(f"Attempt{attempt} /proc PID{expected_pid} is not a live process state.")
    return {
        "pid": expected_pid,
        "ppid": ppid,
        "cmdline": list(command),
        "cwd": cwd,
        "state": state,
    }


def _cmdline_has_eval_module(command: Sequence[str]) -> bool:
    return any(
        command[index] == "-m" and command[index + 1] == "gr00t.rl.eval_agent_trl"
        for index in range(len(command) - 1)
    )


def _extract_eval_output_dir(command: Sequence[str], *, attempt: int = ATTEMPT) -> str:
    values: list[str] = []
    for index, token in enumerate(command):
        if token.startswith("eval_output_dir="):
            values.append(token.split("=", 1)[1])
        elif token == "--eval_output_dir" and index + 1 < len(command):
            values.append(command[index + 1])
    if len(values) != 1:
        raise RuntimeError(f"Attempt{attempt} eval child cmdline must bind exactly one eval_output_dir.")
    value = Path(values[0])
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve())


def derive_process_identity(
    *,
    runner_pid: int,
    process_pid: int,
    attempt: int = ATTEMPT,
    proc_reader: Callable[[int], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read-only verification that the eval PID is a child of the attempt runner."""
    if (
        isinstance(runner_pid, bool)
        or not isinstance(runner_pid, int)
        or runner_pid <= 0
        or isinstance(process_pid, bool)
        or not isinstance(process_pid, int)
        or process_pid <= 0
        or runner_pid == process_pid
    ):
        raise RuntimeError(f"Attempt{attempt} runner_pid and eval process_pid must be distinct positive PIDs.")
    runner_raw = (
        _default_proc_reader(runner_pid, attempt=attempt)
        if proc_reader is None
        else proc_reader(runner_pid)
    )
    runner = _normalize_proc_snapshot(runner_raw, expected_pid=runner_pid, attempt=attempt)
    chain: list[dict[str, Any]] = []
    current_pid = process_pid
    visited: set[int] = set()
    while True:
        if current_pid in visited:
            raise RuntimeError(f"Attempt{attempt} process ancestry contains a cycle.")
        visited.add(current_pid)
        raw_snapshot = (
            _default_proc_reader(current_pid, attempt=attempt)
            if proc_reader is None
            else proc_reader(current_pid)
        )
        snapshot = _normalize_proc_snapshot(raw_snapshot, expected_pid=current_pid, attempt=attempt)
        chain.append(snapshot)
        if snapshot["ppid"] == runner_pid:
            chain.append(runner)
            break
        if snapshot["ppid"] <= 0 or snapshot["ppid"] in visited:
            raise RuntimeError(f"Attempt{attempt} eval PID is not a direct child or verified descendant of runner_pid.")
        current_pid = snapshot["ppid"]
    eval_snapshot = chain[0]
    command = eval_snapshot["cmdline"]
    if not _cmdline_has_eval_module(command):
        raise RuntimeError(f"Attempt{attempt} eval child cmdline must contain `-m gr00t.rl.eval_agent_trl`.")
    eval_output_dir = _extract_eval_output_dir(command, attempt=attempt)
    expected_output_root = (
        EXPECTED_ATTEMPT19_OUTPUT_ROOT
        if attempt == ATTEMPT
        else Path(f"logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt{attempt}")
    )
    expected_output_dir = str((ROOT / expected_output_root / "eval").resolve())
    if eval_output_dir != expected_output_dir:
        raise RuntimeError(
            f"Attempt{attempt} eval child cmdline must bind the exact Attempt{attempt} eval_output_dir: "
            f"expected={expected_output_dir}, actual={eval_output_dir}."
        )
    return {
        "runner_pid": runner_pid,
        "eval_pid": process_pid,
        "runner": runner,
        "eval": eval_snapshot,
        "ancestry_chain": chain,
        "module": "gr00t.rl.eval_agent_trl",
        "output_namespace": str((ROOT / expected_output_root).resolve()),
        "eval_output_dir": eval_output_dir,
    }


def _validate_process_identity_evidence(
    identity: Mapping[str, Any], *, process_pid: int, attempt: int = ATTEMPT
) -> None:
    if identity.get("eval_pid") != process_pid:
        raise RuntimeError(f"Attempt{attempt} process identity eval_pid does not match the steady process PID.")
    runner_pid = identity.get("runner_pid")
    if isinstance(runner_pid, bool) or not isinstance(runner_pid, int) or runner_pid <= 0:
        raise RuntimeError(f"Attempt{attempt} process identity runner_pid is missing or invalid.")
    if identity.get("module") != "gr00t.rl.eval_agent_trl":
        raise RuntimeError(f"Attempt{attempt} process identity module binding is not exact.")
    expected_output_root = (
        EXPECTED_ATTEMPT19_OUTPUT_ROOT
        if attempt == ATTEMPT
        else Path(f"logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt{attempt}")
    )
    expected_root = str((ROOT / expected_output_root).resolve())
    expected_eval = str((ROOT / expected_output_root / "eval").resolve())
    if identity.get("output_namespace") != expected_root or identity.get("eval_output_dir") != expected_eval:
        raise RuntimeError(f"Attempt{attempt} process identity output namespace binding is not exact.")
    chain = identity.get("ancestry_chain")
    if not isinstance(chain, list) or len(chain) < 2:
        raise RuntimeError(f"Attempt{attempt} process identity ancestry chain is missing.")
    if any(not isinstance(item, Mapping) for item in chain):
        raise RuntimeError(f"Attempt{attempt} process identity ancestry chain contains a malformed snapshot.")
    if chain[0].get("pid") != process_pid or chain[-1].get("pid") != runner_pid:
        raise RuntimeError(f"Attempt{attempt} process identity ancestry endpoints do not match runner/eval PIDs.")
    for child, parent in zip(chain, chain[1:]):
        if child.get("ppid") != parent.get("pid"):
            raise RuntimeError(f"Attempt{attempt} process identity ancestry chain is not contiguous.")
    eval_record = identity.get("eval")
    runner_record = identity.get("runner")
    if not isinstance(eval_record, Mapping) or not isinstance(runner_record, Mapping):
        raise RuntimeError(f"Attempt{attempt} process identity runner/eval snapshots are missing.")
    normalized_eval_record = _normalize_proc_snapshot(eval_record, expected_pid=process_pid, attempt=attempt)
    normalized_runner_record = _normalize_proc_snapshot(runner_record, expected_pid=runner_pid, attempt=attempt)
    if normalized_eval_record != dict(chain[0]) or normalized_runner_record != dict(chain[-1]):
        raise RuntimeError(f"Attempt{attempt} process identity runner/eval snapshots do not match the ancestry chain.")
    eval_identity = _normalize_proc_snapshot(chain[0], expected_pid=process_pid, attempt=attempt)
    if not _cmdline_has_eval_module(eval_identity["cmdline"]):
        raise RuntimeError(f"Attempt{attempt} process identity eval cmdline module binding is not exact.")
    if _extract_eval_output_dir(eval_identity["cmdline"], attempt=attempt) != expected_eval:
        raise RuntimeError(f"Attempt{attempt} process identity eval_output_dir binding is not exact.")


def _validate_device_records(
    evidence: Mapping[str, Any],
    *,
    steady: bool,
    attempt: int = ATTEMPT,
) -> dict[int, Mapping[str, Any]]:
    devices = evidence.get("per_device")
    if not isinstance(devices, list) or len(devices) != len(ALL_PHYSICAL_DEVICES):
        raise RuntimeError(f"Attempt{attempt} evidence must contain exactly one record for each physical GPU0-7.")
    by_index: dict[int, Mapping[str, Any]] = {}
    for raw in devices:
        device = _require_mapping(raw, f"Attempt{attempt} per_device record")
        index = device.get("index")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index in by_index
            or index not in ALL_PHYSICAL_DEVICES
        ):
            raise RuntimeError(f"Attempt{attempt} evidence has duplicate or invalid physical GPU indices.")
        by_index[index] = device
        if device.get("leased") is not (index in AUTHORIZED_COMPUTE_PHYSICAL_DEVICES):
            raise RuntimeError(f"Attempt{attempt} GPU{index} leased flag violates the GPU2/[2, 3] contract.")
        uuid = device.get("uuid")
        if not isinstance(uuid, str) or not uuid.strip():
            raise RuntimeError(f"Attempt{attempt} GPU{index} UUID is missing or unknown.")
        utilization = _finite_nonnegative(
            device.get("utilization_gpu_percent"), f"Attempt{attempt} GPU{index} utilization_gpu_percent"
        )
        if utilization > 100.0:
            raise RuntimeError(f"Attempt{attempt} GPU{index} utilization exceeds 100%.")
        if steady:
            _finite_nonnegative(
                device.get("total_memory_used_mib"), f"Attempt{attempt} GPU{index} total_memory_used_mib"
            )
            _finite_nonnegative(
                device.get("attempt_process_memory_mib"),
                f"Attempt{attempt} GPU{index} attempt_process_memory_mib",
            )
        else:
            _finite_nonnegative(
                device.get("memory_used_mib"), f"Attempt{attempt} GPU{index} memory_used_mib"
            )
        processes = device.get("compute_processes")
        if not isinstance(processes, list):
            raise RuntimeError(f"Attempt{attempt} GPU{index} compute_processes must be a list.")
        seen_pids: set[int] = set()
        for process in processes:
            item = _require_mapping(process, f"Attempt{attempt} GPU{index} compute process")
            pid = item.get("pid")
            if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or pid in seen_pids:
                raise RuntimeError(f"Attempt{attempt} GPU{index} compute process PID is invalid or duplicated.")
            name = item.get("name")
            if (
                not isinstance(name, str)
                or not name.strip()
                or name.strip().upper() in {"N/A", "NA", "UNKNOWN", "[NOT SUPPORTED]"}
            ):
                raise RuntimeError(f"Attempt{attempt} GPU{index} compute process name is unknown.")
            _finite_nonnegative(
                item.get("memory_used_mib"), f"Attempt{attempt} GPU{index} compute process memory_used_mib"
            )
            seen_pids.add(pid)
        pmon_processes = device.get("pmon_processes")
        if not isinstance(pmon_processes, list) or not pmon_processes:
            raise RuntimeError(f"Attempt{attempt} GPU{index} pmon_processes must be a complete non-empty list.")
        seen_pmon_pids: set[int] = set()
        for process in pmon_processes:
            item = _require_mapping(process, f"Attempt{attempt} GPU{index} pmon process")
            if item.get("gpu_index") != index:
                raise RuntimeError(f"Attempt{attempt} GPU{index} pmon process has a mismatched physical index.")
            pid = item.get("pid")
            if pid is None:
                if any(
                    item.get(field) is not None
                    for field in (
                        "type",
                        "sm_util_percent",
                        "memory_util_percent",
                        "fb_memory_mib",
                        "command",
                    )
                ):
                    raise RuntimeError(f"Attempt{attempt} GPU{index} pmon empty row contains unknown context fields.")
                if (
                    item.get("sm_util_percent_state") != PMON_NOT_APPLICABLE
                    or item.get("memory_util_percent_state") != PMON_NOT_APPLICABLE
                    or item.get("fb_memory_mib_state") != PMON_NOT_APPLICABLE
                    or item.get("source") != PMON_SOURCE
                ):
                    raise RuntimeError(f"Attempt{attempt} GPU{index} pmon empty row source/state is not explicit.")
                continue
            if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or pid in seen_pmon_pids:
                raise RuntimeError(f"Attempt{attempt} GPU{index} pmon process PID is invalid or duplicated.")
            if item.get("type") not in PMON_PROCESS_TYPES:
                raise RuntimeError(f"Attempt{attempt} GPU{index} pmon process type is unknown.")
            if item.get("source") != PMON_SOURCE:
                raise RuntimeError(f"Attempt{attempt} GPU{index} pmon process source is unknown.")
            for field, state_field in (
                ("sm_util_percent", "sm_util_percent_state"),
                ("memory_util_percent", "memory_util_percent_state"),
            ):
                state = item.get(state_field)
                value = item.get(field)
                if state == PMON_NOT_REPORTED:
                    if value is not None:
                        raise RuntimeError(
                            f"Attempt{attempt} GPU{index} pmon {field} marked NOT_REPORTED but is not null."
                        )
                elif state == PMON_REPORTED:
                    _finite_nonnegative(value, f"Attempt{attempt} GPU{index} pmon {field}")
                else:
                    raise RuntimeError(f"Attempt{attempt} GPU{index} pmon {field} availability state is unknown.")
            if item.get("fb_memory_mib_state") != PMON_REPORTED:
                raise RuntimeError(f"Attempt{attempt} GPU{index} pmon FB memory availability state is unknown.")
            _finite_nonnegative(item.get("fb_memory_mib"), f"Attempt{attempt} GPU{index} pmon fb_memory_mib")
            command = item.get("command")
            if not isinstance(command, str) or not command.strip():
                raise RuntimeError(f"Attempt{attempt} GPU{index} pmon process command is unknown.")
            seen_pmon_pids.add(pid)
    if set(by_index) != set(ALL_PHYSICAL_DEVICES):
        raise RuntimeError(f"Attempt{attempt} evidence must cover physical GPU indices 0-7 exactly.")
    return by_index


def _sorted_pmon_processes(processes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "gpu_index": int(process["gpu_index"]),
            "pid": None if process.get("pid") is None else int(process["pid"]),
            "type": process.get("type"),
            "sm_util_percent": process.get("sm_util_percent"),
            "sm_util_percent_state": process.get("sm_util_percent_state"),
            "memory_util_percent": process.get("memory_util_percent"),
            "memory_util_percent_state": process.get("memory_util_percent_state"),
            "fb_memory_mib": process.get("fb_memory_mib"),
            "fb_memory_mib_state": process.get("fb_memory_mib_state"),
            "command": process.get("command"),
            "source": process.get("source"),
        }
        for process in sorted(
            processes,
            key=lambda value: -1 if value.get("pid") is None else int(value["pid"]),
        )
    ]


def _validate_tenant_records(
    evidence: Mapping[str, Any],
    *,
    field: str,
    by_index: Mapping[int, Mapping[str, Any]],
    attempt: int = ATTEMPT,
) -> dict[int, dict[str, Any]]:
    records = evidence.get(field)
    if not isinstance(records, list):
        raise RuntimeError(f"Attempt{attempt} evidence must include {field}.")
    tenant_by_device: dict[int, dict[str, Any]] = {}
    excluded_pid = evidence.get("attempt_pid")
    for raw in records:
        record = _require_mapping(raw, f"Attempt{attempt} {field} record")
        index = record.get("device_index")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index in tenant_by_device
            or index not in UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
        ):
            raise RuntimeError(f"Attempt{attempt} {field} must use unique non-leased GPU indices.")
        if record.get("attribution") != "OTHER_TENANT":
            raise RuntimeError(f"Attempt{attempt} {field} must explicitly attribute occupancy to OTHER_TENANT.")
        utilization = _finite_nonnegative(
            record.get("utilization_gpu_percent"),
            f"Attempt{attempt} {field} GPU{index} utilization_gpu_percent",
        )
        if utilization > 100.0:
            raise RuntimeError(f"Attempt{attempt} {field} GPU{index} utilization exceeds 100%.")
        processes = record.get("processes")
        pmon_processes = record.get("pmon_processes")
        if not isinstance(processes, list) or not isinstance(pmon_processes, list):
            raise RuntimeError(f"Attempt{attempt} {field} OTHER_TENANT records require process evidence.")
        normalized = _sorted_processes(processes)
        normalized_pmon = _sorted_pmon_processes(pmon_processes)
        if not normalized_pmon or any(item.get("pid") is None for item in normalized_pmon):
            raise RuntimeError(f"Attempt{attempt} {field} OTHER_TENANT records require observed pmon process evidence.")
        tenant_by_device[index] = {
            "utilization_gpu_percent": utilization,
            "processes": normalized,
            "pmon_processes": normalized_pmon,
        }
        device = by_index[index]
        if float(device["utilization_gpu_percent"]) != utilization:
            raise RuntimeError(f"Attempt{attempt} {field} utilization does not match GPU{index}.")
        device_processes = [
            process
            for process in device["compute_processes"]
            if excluded_pid is None or process.get("pid") != excluded_pid
        ]
        if _sorted_processes(device_processes) != normalized:
            raise RuntimeError(f"Attempt{attempt} {field} processes do not match GPU{index}.")
        device_pmon_processes = [
            process
            for process in device["pmon_processes"]
            if process.get("pid") is not None
            and (excluded_pid is None or process.get("pid") != excluded_pid)
        ]
        if _sorted_pmon_processes(device_pmon_processes) != normalized_pmon:
            raise RuntimeError(f"Attempt{attempt} {field} pmon processes do not match GPU{index}.")
    return tenant_by_device


def _compute_pids(device: Mapping[str, Any]) -> set[int]:
    return {int(process["pid"]) for process in device["compute_processes"]}


def _validate_inactive_vulkan_context(
    context: Mapping[str, Any], *, label: str
) -> None:
    if context.get("type") != "G":
        raise RuntimeError(f"{label} must be an inactive graphics G context.")
    fb_memory = _finite_nonnegative(context.get("fb_memory_mib"), f"{label} FB memory")
    if fb_memory > NON_LEASED_STOP_THRESHOLD_MIB:
        raise RuntimeError(f"{label} exceeds the inactive Vulkan FB memory threshold.")
    for metric, state_field in (
        ("sm_util_percent", "sm_util_percent_state"),
        ("memory_util_percent", "memory_util_percent_state"),
    ):
        state = context.get(state_field)
        value = context.get(metric)
        if state == PMON_NOT_REPORTED:
            if value is not None:
                raise RuntimeError(f"{label} {metric} is NOT_REPORTED but not null.")
        elif state == PMON_REPORTED:
            if _finite_nonnegative(value, f"{label} {metric}") != 0.0:
                raise RuntimeError(f"{label} reported nonzero {metric}.")
        else:
            raise RuntimeError(f"{label} {metric} availability state is unknown.")


def _validate_attempt20_inactive_context(
    context: Mapping[str, Any], *, label: str
) -> None:
    """Validate an Attempt20 same-PID enumeration context without erasing source facts."""
    if context.get("type") not in PMON_PROCESS_TYPES:
        raise RuntimeError(f"{label} has an unknown PMON context type.")
    fb_memory = _finite_nonnegative(context.get("fb_memory_mib"), f"{label} FB memory")
    if fb_memory > NON_LEASED_STOP_THRESHOLD_MIB:
        raise RuntimeError(f"{label} exceeds the inactive enumeration FB memory threshold.")
    for metric, state_field in (
        ("sm_util_percent", "sm_util_percent_state"),
        ("memory_util_percent", "memory_util_percent_state"),
    ):
        state = context.get(state_field)
        value = context.get(metric)
        if state == PMON_NOT_REPORTED:
            if value is not None:
                raise RuntimeError(f"{label} {metric} is NOT_REPORTED but not null.")
        elif state == PMON_REPORTED:
            if _finite_nonnegative(value, f"{label} {metric}") != 0.0:
                raise RuntimeError(f"{label} reported nonzero {metric}.")
        else:
            raise RuntimeError(f"{label} {metric} availability state is unknown.")


def _validate_gpu3_alternate_tenant_records(
    evidence: Mapping[str, Any],
    *,
    by_index: Mapping[int, Mapping[str, Any]],
    field: str,
    excluded_pid: int | None = None,
    attempt: int = ATTEMPT,
) -> dict[int, dict[str, Any]]:
    records = evidence.get(field)
    if not isinstance(records, list):
        raise RuntimeError(f"Attempt{attempt} evidence must include {field}.")
    device = by_index[3]
    compute_pids = _compute_pids(device)
    tenant_by_device: dict[int, dict[str, Any]] = {}
    for raw in records:
        record = _require_mapping(raw, f"Attempt{attempt} {field} record")
        index = record.get("device_index")
        if index != 3 or index in tenant_by_device:
            raise RuntimeError(f"Attempt{attempt} {field} must contain at most one GPU3 record.")
        if record.get("attribution") != "OTHER_TENANT":
            raise RuntimeError(f"Attempt{attempt} {field} GPU3 attribution must be OTHER_TENANT.")
        utilization = _finite_nonnegative(
            record.get("utilization_gpu_percent"),
            f"Attempt{attempt} {field} GPU3 utilization_gpu_percent",
        )
        if utilization > 100.0:
            raise RuntimeError(f"Attempt{attempt} {field} GPU3 utilization exceeds 100%.")
        processes = record.get("processes")
        pmon_processes = record.get("pmon_processes")
        if not isinstance(processes, list) or not isinstance(pmon_processes, list) or not pmon_processes:
            raise RuntimeError(f"Attempt{attempt} {field} GPU3 requires explicit process evidence.")
        normalized_processes = _sorted_processes(processes)
        normalized_pmon = _sorted_pmon_processes(pmon_processes)
        if any(item["pid"] == excluded_pid for item in normalized_processes):
            raise RuntimeError(f"Attempt{attempt} {field} GPU3 must exclude the Attempt{attempt} PID.")
        for item in normalized_pmon:
            item_pid = item.get("pid")
            if item_pid is None or item_pid == excluded_pid:
                raise RuntimeError(f"Attempt{attempt} {field} GPU3 contains an invalid or excluded PID.")
            if item_pid in compute_pids:
                raise RuntimeError(
                    f"Attempt{attempt} {field} GPU3 process PID{item_pid} is present in compute-apps."
                )
            _validate_inactive_vulkan_context(item, label=f"Attempt{attempt} {field} GPU3 PID{item_pid}")
        device_processes = [
            process
            for process in device["compute_processes"]
            if excluded_pid is None or process.get("pid") != excluded_pid
        ]
        if _sorted_processes(device_processes) != normalized_processes:
            raise RuntimeError(f"Attempt{attempt} {field} GPU3 processes do not match GPU3.")
        device_pmon_processes = [
            process
            for process in device["pmon_processes"]
            if process.get("pid") is not None
            and (excluded_pid is None or process.get("pid") != excluded_pid)
        ]
        if _sorted_pmon_processes(device_pmon_processes) != normalized_pmon:
            raise RuntimeError(f"Attempt{attempt} {field} GPU3 pmon processes do not match GPU3.")
        tenant_by_device[3] = {
            "utilization_gpu_percent": utilization,
            "processes": normalized_processes,
            "pmon_processes": normalized_pmon,
        }
    device_processes = [
        process
        for process in device["compute_processes"]
        if excluded_pid is None or process.get("pid") != excluded_pid
    ]
    device_pmon_processes = [
        process
        for process in device["pmon_processes"]
        if process.get("pid") is not None
        and (excluded_pid is None or process.get("pid") != excluded_pid)
    ]
    if not tenant_by_device and (device_processes or device_pmon_processes or float(device["utilization_gpu_percent"]) != 0.0):
        raise RuntimeError(f"Attempt{attempt} GPU3 has unrecorded alternate occupancy.")
    if not tenant_by_device:
        return {}
    if tenant_by_device[3]["utilization_gpu_percent"] != float(device["utilization_gpu_percent"]):
        raise RuntimeError(f"Attempt{attempt} GPU3 alternate occupancy utilization does not match GPU3.")
    return tenant_by_device


def _validate_common(
    evidence: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    schema: str,
    label: str,
    attempt: int = ATTEMPT,
) -> None:
    if evidence.get("schema_version") != schema:
        raise RuntimeError(f"Attempt{attempt} {label} schema is not canonical.")
    if evidence.get("attempt") != attempt:
        raise RuntimeError(f"Attempt{attempt} {label} attempt identity is not {attempt}.")
    if evidence.get("status") != "PASS":
        raise RuntimeError(f"Attempt{attempt} {label} evidence must have status PASS.")
    _validate_plan_binding(evidence, plan=plan, plan_artifact=plan_artifact, label=label, attempt=attempt)
    if evidence.get("selected_compute_physical_device") != SELECTED_COMPUTE_PHYSICAL_DEVICE:
        raise RuntimeError(f"Attempt{attempt} {label} selected GPU must be GPU2.")
    if evidence.get("authorized_compute_physical_devices") != AUTHORIZED_COMPUTE_PHYSICAL_DEVICES:
        raise RuntimeError(f"Attempt{attempt} {label} authorized GPUs must be [2, 3].")
    if evidence.get("unauthorized_compute_physical_devices") != UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES:
        raise RuntimeError(f"Attempt{attempt} {label} non-leased GPUs must be [0, 1, 4, 5, 6, 7].")
    if evidence.get("cuda_visible_devices") != "UNSET":
        raise RuntimeError(f"Attempt{attempt} {label} must preserve CUDA_VISIBLE_DEVICES=UNSET.")
    if evidence.get("container_isolation_used") is not False:
        raise RuntimeError(f"Attempt{attempt} {label} must not claim container isolation.")


def validate_launch_evidence(
    evidence: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    now: datetime | None = None,
    require_fresh: bool = True,
    attempt: int = ATTEMPT,
) -> dict[str, Any]:
    """Validate an attempt launch receipt without writing or querying GPUs."""
    _validate_common(
        evidence,
        plan=plan,
        plan_artifact=plan_artifact,
        schema=f"pull_v0_p1_attempt{attempt}_launch_occupancy_v1",
        label="launch occupancy",
        attempt=attempt,
    )
    if evidence.get("phase") != "IMMEDIATELY_BEFORE_LAUNCH":
        raise RuntimeError(f"Attempt{attempt} launch occupancy phase must be IMMEDIATELY_BEFORE_LAUNCH.")
    if require_fresh:
        _validate_fresh_capture(
            evidence.get("captured_at_hkt"), now=now, label="launch occupancy", attempt=attempt
        )
    else:
        _parse_hkt(evidence.get("captured_at_hkt"), "captured_at_hkt")
    if evidence.get("runtime_started") is not False or evidence.get("scientific_attempt_started") is not False:
        raise RuntimeError(f"Attempt{attempt} launch occupancy must be captured before runtime starts.")
    if evidence.get("incidental_vulkan_enumeration_contexts_authorized") is not True:
        raise RuntimeError(f"Attempt{attempt} launch occupancy must preserve incidental Vulkan authorization.")
    by_index = _validate_device_records(evidence, steady=False, attempt=attempt)
    tenant_by_device = _validate_tenant_records(
        evidence,
        field="non_leased_tenant_occupancy_at_launch",
        by_index=by_index,
        attempt=attempt,
    )
    alternate_tenant_by_device = _validate_gpu3_alternate_tenant_records(
        evidence,
        by_index=by_index,
        field="authorized_alternate_tenant_occupancy_at_launch",
        attempt=attempt,
    )
    for index, device in by_index.items():
        processes = _sorted_processes(device["compute_processes"])
        pmon_processes = [
            process for process in device["pmon_processes"] if process.get("pid") is not None
        ]
        utilization = float(device["utilization_gpu_percent"])
        if index in AUTHORIZED_COMPUTE_PHYSICAL_DEVICES:
            if index == 3:
                if processes:
                    raise RuntimeError(f"Attempt{attempt} launch occupancy blocks compute-app presence on authorized GPU3.")
                if pmon_processes and index not in alternate_tenant_by_device:
                    raise RuntimeError(f"Attempt{attempt} launch occupancy requires explicit GPU3 alternate attribution.")
                if not pmon_processes and index in alternate_tenant_by_device:
                    raise RuntimeError(f"Attempt{attempt} launch occupancy has an empty GPU3 alternate attribution.")
            elif utilization != 0.0 or processes or pmon_processes:
                raise RuntimeError(
                    f"Attempt{attempt} launch occupancy requires leased GPU{index} idle immediately before launch."
                )
            if index in tenant_by_device or (
                index == 3 and not pmon_processes and index in alternate_tenant_by_device
            ):
                raise RuntimeError(f"Attempt{attempt} launch occupancy incorrectly attributes leased GPU{index} to OTHER_TENANT.")
            if index == 3 and pmon_processes and device.get("context_classification") != "OTHER_TENANT_INACTIVE_VULKAN_ENUMERATION":
                raise RuntimeError(f"Attempt{attempt} launch occupancy GPU3 alternate context classification is missing.")
        else:
            tenant = tenant_by_device.get(index)
            if tenant is None and (utilization != 0.0 or processes or pmon_processes):
                raise RuntimeError(
                    f"Attempt{attempt} launch occupancy has unrecorded non-leased GPU{index} compute."
                )
            if tenant is not None and (
                tenant["utilization_gpu_percent"] != utilization
                or tenant["processes"] != processes
                or tenant["pmon_processes"] != _sorted_pmon_processes(pmon_processes)
            ):
                raise RuntimeError(f"Attempt{attempt} launch occupancy OTHER_TENANT attribution does not match GPU{index}.")
    return {
        "launch": dict(evidence),
        "tenant_devices_at_launch": sorted(tenant_by_device),
        "selected_compute_physical_device": SELECTED_COMPUTE_PHYSICAL_DEVICE,
        "authorized_compute_physical_devices": list(AUTHORIZED_COMPUTE_PHYSICAL_DEVICES),
    }


def validate_steady_evidence(
    evidence: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    log_text: str,
    required_pid: int | None = None,
    now: datetime | None = None,
    require_fresh: bool = False,
    attempt: int = ATTEMPT,
) -> dict[str, Any]:
    """Validate an attempt steady-state receipt and first-step log boundary."""
    _validate_common(
        evidence,
        plan=plan,
        plan_artifact=plan_artifact,
        schema=f"pull_v0_p1_attempt{attempt}_steady_state_footprint_v1",
        label="steady-state footprint",
        attempt=attempt,
    )
    if evidence.get("phase") != "EVALUATION_STEPPING":
        raise RuntimeError(f"Attempt{attempt} steady-state footprint phase must be EVALUATION_STEPPING.")
    if require_fresh:
        _validate_fresh_capture(
            evidence.get("captured_at_hkt"), now=now, label="steady-state", attempt=attempt
        )
    else:
        _parse_hkt(evidence.get("captured_at_hkt"), "steady-state captured_at_hkt")
    runtime_log_contract = parse_runtime_log_contract(log_text, attempt=attempt)
    if evidence.get("runtime_log_contract") != runtime_log_contract:
        raise RuntimeError(
            f"Attempt{attempt} steady-state runtime_log_contract does not match independently derived log evidence."
        )
    if evidence.get("kit_active_physical_devices") != [SELECTED_COMPUTE_PHYSICAL_DEVICE]:
        raise RuntimeError(f"Attempt{attempt} steady-state Kit activity must be derived as physical GPU2 only.")
    if evidence.get("app_launcher_device") != runtime_log_contract["app_launcher"]["device"]:
        raise RuntimeError(f"Attempt{attempt} steady-state AppLauncher device does not match the runtime log.")
    if evidence.get("environment_device") != runtime_log_contract["environment"]["device"]:
        raise RuntimeError(f"Attempt{attempt} steady-state environment device does not match the runtime log.")
    if evidence.get("first_simulation_step_boundary_crossed") is not True:
        raise RuntimeError(f"Attempt{attempt} steady-state footprint must prove the exact first-step boundary.")
    if evidence.get("scientific_attempt_started") is not True:
        raise RuntimeError(f"Attempt{attempt} steady-state footprint must prove scientific attempt start.")
    boundary_line = runtime_log_contract["first_simulation_step_boundary"]["source_line"]
    if evidence.get("first_simulation_step_evidence") != boundary_line:
        raise RuntimeError(f"Attempt{attempt} steady-state first-step evidence does not match the exact boundary line.")
    process = _require_mapping(evidence.get("process"), f"Attempt{attempt} steady-state footprint.process")
    pid = process.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise RuntimeError(f"Attempt{attempt} steady-state footprint process PID must be positive.")
    if required_pid is not None and pid != required_pid:
        raise RuntimeError(f"Attempt{attempt} steady-state footprint process PID does not match the requested attempt PID.")
    if evidence.get("attempt_pid") != pid:
        raise RuntimeError(f"Attempt{attempt} steady-state attempt_pid does not match the process PID.")
    _validate_process_identity_evidence(
        _require_mapping(evidence.get("process_identity"), f"Attempt{attempt} steady-state process_identity"),
        process_pid=pid,
        attempt=attempt,
    )
    name = process.get("name")
    if (
        not isinstance(name, str)
        or not name.strip()
        or name.strip().upper() in {"N/A", "NA", "UNKNOWN", "[NOT SUPPORTED]"}
    ):
        raise RuntimeError(f"Attempt{attempt} steady-state footprint process name is unknown.")
    by_index = _validate_device_records(evidence, steady=True, attempt=attempt)
    tenant_by_device = _validate_tenant_records(
        evidence,
        field="non_leased_tenant_occupancy_at_steady_state",
        by_index=by_index,
        attempt=attempt,
    )
    alternate_tenant_by_device = _validate_gpu3_alternate_tenant_records(
        evidence,
        by_index=by_index,
        field="authorized_alternate_tenant_occupancy_at_steady_state",
        excluded_pid=pid,
        attempt=attempt,
    )
    selected = by_index[SELECTED_COMPUTE_PHYSICAL_DEVICE]
    attempt_memory_by_device: dict[int, float] = {}
    for index, device in by_index.items():
        contexts = [
            process
            for process in device["pmon_processes"]
            if process.get("pid") == pid
        ]
        if index == SELECTED_COMPUTE_PHYSICAL_DEVICE:
            if len(contexts) != 1:
                raise RuntimeError(f"Attempt{attempt} steady-state pmon must capture exactly one selected GPU2 PID context.")
            context = contexts[0]
            if context.get("type") not in {"C", "C+G"}:
                raise RuntimeError(f"Attempt{attempt} selected GPU2 attempt context must include compute type C.")
            if float(context["fb_memory_mib"]) <= 0.0:
                raise RuntimeError(f"Attempt{attempt} selected GPU2 attempt context must have positive FB memory.")
            if pid not in _compute_pids(device):
                raise RuntimeError(f"Attempt{attempt} selected GPU2 PID must appear in compute-apps on GPU2.")
            if attempt != ATTEMPT and float(device["utilization_gpu_percent"]) <= 0.0:
                raise RuntimeError(
                    f"Attempt{attempt} selected GPU2 must show selected-device activity/context."
                )
            attempt_memory_by_device[index] = float(context["fb_memory_mib"])
            expected_classification = "AUTHORIZED_COMPUTE"
        else:
            compute_pids = _compute_pids(device)
            if pid in compute_pids and not contexts:
                raise RuntimeError(
                    f"Attempt{attempt} nonselected GPU{index} compute-apps contains the attempt PID without a pmon context."
                )
            if contexts:
                for context in contexts:
                    if attempt == ATTEMPT and pid in compute_pids:
                        raise RuntimeError(
                            f"Attempt{attempt} nonselected GPU{index} compute-apps contains the attempt PID."
                        )
                    if attempt == ATTEMPT:
                        _validate_inactive_vulkan_context(
                            context,
                            label=f"Attempt{attempt} nonselected GPU{index} selected PID context",
                        )
                    else:
                        _validate_attempt20_inactive_context(
                            context,
                            label=f"Attempt{attempt} nonselected GPU{index} selected PID context",
                        )
                if attempt != ATTEMPT and float(device["utilization_gpu_percent"]) != 0.0:
                    tenant = tenant_by_device.get(index)
                    alternate_tenant = alternate_tenant_by_device.get(index)
                    if tenant is None and alternate_tenant is None:
                        raise RuntimeError(
                            f"Attempt{attempt} nonselected GPU{index} utilization requires exact OTHER_TENANT attribution."
                        )
                attempt_memory_by_device[index] = max(
                    float(context["fb_memory_mib"]) for context in contexts
                )
                expected_classification = "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION"
            else:
                attempt_memory_by_device[index] = 0.0
                expected_classification = "NO_ATTEMPT_CONTEXT_OBSERVED"
        if float(device["attempt_process_memory_mib"]) != attempt_memory_by_device[index]:
            raise RuntimeError(
                f"Attempt{attempt} GPU{index} attempt_process_memory_mib is not derived from the pmon PID context."
            )
        if device.get("context_classification") != expected_classification:
            raise RuntimeError(f"Attempt{attempt} GPU{index} context classification is not derived from pmon evidence.")
    if selected.get("selected") is not True:
        raise RuntimeError(f"Attempt{attempt} steady-state footprint must mark GPU2 selected.")
    for index, device in by_index.items():
        processes = _sorted_processes(device["compute_processes"])
        utilization = float(device["utilization_gpu_percent"])
        attempt_memory = float(device["attempt_process_memory_mib"])
        if index == SELECTED_COMPUTE_PHYSICAL_DEVICE:
            continue
        if index in AUTHORIZED_COMPUTE_PHYSICAL_DEVICES:
            if attempt_memory > NON_LEASED_STOP_THRESHOLD_MIB:
                raise RuntimeError(f"Attempt{attempt} authorized alternate GPU{index} exceeds inactive Vulkan FB memory threshold.")
            if index == 3 and device.get("context_classification") not in {
                "NO_ATTEMPT_CONTEXT_OBSERVED",
                "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION",
            }:
                raise RuntimeError(f"Attempt{attempt} GPU3 context classification is not derived from the selected PID.")
            if index == 3 and alternate_tenant_by_device and device.get(
                "other_tenant_context_classification"
            ) != "OTHER_TENANT_INACTIVE_VULKAN_ENUMERATION":
                raise RuntimeError(f"Attempt{attempt} GPU3 alternate tenant classification is missing.")
            continue
        tenant = tenant_by_device.get(index)
        pmon_processes = [
            process
            for process in device["pmon_processes"]
            if process.get("pid") is not None and process.get("pid") != pid
        ]
        if tenant is None and (processes or pmon_processes or utilization != 0.0):
            raise RuntimeError(f"Attempt{attempt} non-leased GPU{index} has unrecorded compute occupancy.")
        if tenant is not None and (
            tenant["utilization_gpu_percent"] != utilization
            or tenant["processes"] != [item for item in processes if item["pid"] != pid]
            or tenant["pmon_processes"] != _sorted_pmon_processes(pmon_processes)
        ):
            raise RuntimeError(f"Attempt{attempt} OTHER_TENANT steady-state attribution does not match GPU{index}.")
    max_non_leased_memory = _finite_nonnegative(
        evidence.get("max_non_leased_attempt_process_memory_mib"),
        f"Attempt{attempt} max_non_leased_attempt_process_memory_mib",
    )
    threshold = _finite_nonnegative(
        evidence.get("non_leased_stop_threshold_mib"),
        f"Attempt{attempt} non_leased_stop_threshold_mib",
    )
    if threshold != NON_LEASED_STOP_THRESHOLD_MIB:
        raise RuntimeError(f"Attempt{attempt} non-leased stop threshold must remain exactly 1024 MiB.")
    if evidence.get("non_leased_threshold_pass") is not True or max_non_leased_memory > threshold:
        raise RuntimeError(f"Attempt{attempt} steady-state footprint fails the non-leased attempt-memory threshold.")
    observed_utilization = _finite_nonnegative(
        evidence.get("non_leased_observed_utilization_gpu_percent"),
        f"Attempt{attempt} non_leased_observed_utilization_gpu_percent",
    )
    expected_utilization = max(
        float(device["utilization_gpu_percent"])
        for index, device in by_index.items()
        if index in UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
    )
    if not math.isclose(observed_utilization, expected_utilization, rel_tol=1.0e-6, abs_tol=1.0e-6):
        raise RuntimeError(f"Attempt{attempt} steady-state non-leased utilization aggregate is inconsistent.")
    max_non_leased_memory_observed = max(
        attempt_memory_by_device[index] for index in UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
    )
    if max_non_leased_memory != max_non_leased_memory_observed:
        raise RuntimeError(f"Attempt{attempt} steady-state maximum non-leased attempt FB memory is not derived from pmon.")
    return {
        "steady_state": dict(evidence),
        "first_simulation_step_boundary_crossed": True,
        "scientific_attempt_started": True,
        "selected_compute_physical_device": SELECTED_COMPUTE_PHYSICAL_DEVICE,
        "authorized_compute_physical_devices": list(AUTHORIZED_COMPUTE_PHYSICAL_DEVICES),
        "non_leased_compute_observed": False,
        "tenant_devices_at_steady_state": sorted(tenant_by_device),
        "first_step_marker": boundary_line,
        "runtime_log_contract": runtime_log_contract,
        "attempt_process_memory_by_device": attempt_memory_by_device,
    }


def _require_output_path(path: Path, expected: Path, label: str, *, attempt: int) -> Path:
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    if resolved != expected.resolve():
        raise RuntimeError(f"Attempt{attempt} {label} output must use the canonical path.")
    if resolved.exists():
        raise RuntimeError(f"Refusing to overwrite existing Attempt{attempt} {label} evidence: {resolved}")
    return resolved


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def capture_launch_evidence(
    plan_path: Path = ATTEMPT19_PLAN_PATH,
    *,
    output_path: Path | None = None,
    query_runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
    captured_at_hkt: str | None = None,
    attempt: int = ATTEMPT,
) -> dict[str, Any]:
    """Capture and atomically write the canonical launch occupancy receipt."""
    expected_output = ATTEMPT19_LAUNCH_OCCUPANCY_PATH if attempt == ATTEMPT else ATTEMPT20_LAUNCH_OCCUPANCY_PATH
    output_path = expected_output if output_path is None else output_path
    output_path = _require_output_path(output_path, expected_output, "launch occupancy", attempt=attempt)
    plan, plan_artifact = _load_plan(plan_path, attempt=attempt)
    devices = query_gpu_snapshot(query_runner=query_runner)
    timestamp = _hkt_now() if captured_at_hkt is None else captured_at_hkt
    evidence = {
        "schema_version": f"pull_v0_p1_attempt{attempt}_launch_occupancy_v1",
        "captured_at_hkt": timestamp,
        "attempt": attempt,
        "phase": "IMMEDIATELY_BEFORE_LAUNCH",
        "status": "PASS",
        "plan": dict(plan_artifact),
        "selected_compute_physical_device": SELECTED_COMPUTE_PHYSICAL_DEVICE,
        "authorized_compute_physical_devices": list(AUTHORIZED_COMPUTE_PHYSICAL_DEVICES),
        "unauthorized_compute_physical_devices": list(UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES),
        "per_device": [
            {
                **device,
                "compute_processes": _sorted_processes(device["compute_processes"]),
                "pmon_processes": _sorted_pmon_processes(device["pmon_processes"]),
                "leased": index in AUTHORIZED_COMPUTE_PHYSICAL_DEVICES,
            }
            for index, device in sorted(devices.items())
        ],
        "non_leased_tenant_occupancy_at_launch": [],
        "authorized_alternate_tenant_occupancy_at_launch": [],
        "cuda_visible_devices": "UNSET",
        "incidental_vulkan_enumeration_contexts_authorized": True,
        "container_isolation_used": False,
        "runtime_started": False,
        "scientific_attempt_started": False,
        "observation": f"CPU-side nvidia-smi inventory captured immediately before the exact Attempt{attempt} launch.",
    }
    for device in evidence["per_device"]:
        pmon_processes = [
            process for process in device["pmon_processes"] if process.get("pid") is not None
        ]
        if device["index"] in AUTHORIZED_COMPUTE_PHYSICAL_DEVICES:
            if device["index"] == 3 and pmon_processes:
                device["context_classification"] = "OTHER_TENANT_INACTIVE_VULKAN_ENUMERATION"
                evidence["authorized_alternate_tenant_occupancy_at_launch"].append(
                    {
                        "device_index": 3,
                        "attribution": "OTHER_TENANT",
                        "utilization_gpu_percent": device["utilization_gpu_percent"],
                        "processes": device["compute_processes"],
                        "pmon_processes": pmon_processes,
                    }
                )
            else:
                device["context_classification"] = "LEASE_IDLE"
            continue
        device["context_classification"] = (
            "OTHER_TENANT"
            if device["utilization_gpu_percent"] != 0.0
            or device["compute_processes"]
            or pmon_processes
            else "IDLE"
        )
        if device["index"] in UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES and (
            device["utilization_gpu_percent"] != 0.0
            or device["compute_processes"]
            or pmon_processes
        ):
            evidence["non_leased_tenant_occupancy_at_launch"].append(
                {
                    "device_index": device["index"],
                    "attribution": "OTHER_TENANT",
                    "utilization_gpu_percent": device["utilization_gpu_percent"],
                    "processes": device["compute_processes"],
                    "pmon_processes": pmon_processes,
                }
            )
    validate_launch_evidence(
        evidence,
        plan=plan,
        plan_artifact=plan_artifact,
        now=_parse_hkt(timestamp, "captured_at_hkt"),
        require_fresh=False,
        attempt=attempt,
    )
    _write_json(output_path, evidence)
    return evidence


def capture_steady_state_evidence(
    plan_path: Path = ATTEMPT19_PLAN_PATH,
    *,
    process_pid: int,
    runner_pid: int,
    log_path: Path,
    output_path: Path | None = None,
    query_runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
    proc_reader: Callable[[int], Mapping[str, Any]] | None = None,
    captured_at_hkt: str | None = None,
    attempt: int = ATTEMPT,
) -> dict[str, Any]:
    """Capture and atomically write the canonical steady-state receipt."""
    if isinstance(process_pid, bool) or not isinstance(process_pid, int) or process_pid <= 0:
        raise ValueError("process_pid must be a positive integer")
    expected_output = ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH if attempt == ATTEMPT else ATTEMPT20_STEADY_STATE_FOOTPRINT_PATH
    output_path = expected_output if output_path is None else output_path
    output_path = _require_output_path(output_path, expected_output, "steady-state footprint", attempt=attempt)
    if not log_path.is_file() or log_path.is_symlink():
        raise RuntimeError(f"Attempt{attempt} runtime log must be a regular non-symlink file: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    runtime_log_contract = parse_runtime_log_contract(log_text, attempt=attempt)
    process_identity = derive_process_identity(
        runner_pid=runner_pid,
        process_pid=process_pid,
        attempt=attempt,
        proc_reader=proc_reader,
    )
    plan, plan_artifact = _load_plan(plan_path, attempt=attempt)
    devices = query_gpu_snapshot(query_runner=query_runner)
    timestamp = _hkt_now() if captured_at_hkt is None else captured_at_hkt
    _validate_fresh_capture(timestamp, label="steady-state", attempt=attempt)
    selected = devices[SELECTED_COMPUTE_PHYSICAL_DEVICE]
    selected_contexts = [
        process for process in selected["pmon_processes"] if process.get("pid") == process_pid
    ]
    if (
        len(selected_contexts) != 1
        or selected_contexts[0].get("type") not in {"C", "C+G"}
        or process_pid not in _compute_pids(selected)
    ):
        raise RuntimeError(
            f"Requested Attempt{attempt} process PID must have one selected GPU2 C/C+G pmon context and a GPU2 compute-app record."
        )
    selected_context = selected_contexts[0]
    footprint_devices: list[dict[str, Any]] = []
    tenant_records: list[dict[str, Any]] = []
    alternate_tenant_records: list[dict[str, Any]] = []
    for index, device in sorted(devices.items()):
        processes = _sorted_processes(device["compute_processes"])
        pmon_processes = _sorted_pmon_processes(device["pmon_processes"])
        same_pid_contexts = [
            process for process in pmon_processes if process.get("pid") == process_pid
        ]
        if index == SELECTED_COMPUTE_PHYSICAL_DEVICE:
            attempt_memory = float(selected_context["fb_memory_mib"])
            context_classification = "AUTHORIZED_COMPUTE"
        elif same_pid_contexts:
            attempt_memory = max(float(process["fb_memory_mib"]) for process in same_pid_contexts)
            context_classification = "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION"
        else:
            attempt_memory = 0.0
            context_classification = "NO_ATTEMPT_CONTEXT_OBSERVED"
        tenant_pmon_processes = [
            process
            for process in pmon_processes
            if process.get("pid") is not None and process.get("pid") != process_pid
        ]
        tenant_processes = [
            process for process in processes if process.get("pid") != process_pid
        ]
        if index == 3 and (tenant_processes or tenant_pmon_processes):
            alternate_tenant_records.append(
                {
                    "device_index": 3,
                    "attribution": "OTHER_TENANT",
                    "utilization_gpu_percent": device["utilization_gpu_percent"],
                    "processes": tenant_processes,
                    "pmon_processes": tenant_pmon_processes,
                }
            )
        elif index in UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES and (
            device["utilization_gpu_percent"] != 0.0
            or tenant_processes
            or tenant_pmon_processes
        ):
            tenant_records.append(
                {
                    "device_index": index,
                    "attribution": "OTHER_TENANT",
                    "utilization_gpu_percent": device["utilization_gpu_percent"],
                    "processes": tenant_processes,
                    "pmon_processes": tenant_pmon_processes,
                }
            )
        footprint_devices.append(
            {
                "index": index,
                "uuid": device["uuid"],
                "leased": index in AUTHORIZED_COMPUTE_PHYSICAL_DEVICES,
                **({"selected": True} if index == SELECTED_COMPUTE_PHYSICAL_DEVICE else {}),
                "total_memory_used_mib": device["memory_used_mib"],
                "attempt_process_memory_mib": attempt_memory,
                "utilization_gpu_percent": device["utilization_gpu_percent"],
                "compute_processes": processes,
                "pmon_processes": pmon_processes,
                "context_classification": context_classification,
                **(
                    {"other_tenant_context_classification": "OTHER_TENANT_INACTIVE_VULKAN_ENUMERATION"}
                    if index == 3 and tenant_pmon_processes
                    else {}
                ),
            }
        )
    non_leased_memory = max(
        float(device["attempt_process_memory_mib"])
        for device in footprint_devices
        if device["index"] in UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
    )
    non_leased_utilization = max(
        float(device["utilization_gpu_percent"])
        for index, device in devices.items()
        if index in UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
    )
    evidence = {
        "schema_version": f"pull_v0_p1_attempt{attempt}_steady_state_footprint_v1",
        "captured_at_hkt": timestamp,
        "attempt": attempt,
        "phase": "EVALUATION_STEPPING",
        "status": "PASS",
        "plan": dict(plan_artifact),
        "attempt_pid": process_pid,
        "process": {
            "pid": process_pid,
            "name": selected_context["command"],
        },
        "process_identity": process_identity,
        "selected_compute_physical_device": SELECTED_COMPUTE_PHYSICAL_DEVICE,
        "authorized_compute_physical_devices": list(AUTHORIZED_COMPUTE_PHYSICAL_DEVICES),
        "unauthorized_compute_physical_devices": list(UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES),
        "per_device": footprint_devices,
        "max_non_leased_attempt_process_memory_mib": non_leased_memory,
        "non_leased_stop_threshold_mib": NON_LEASED_STOP_THRESHOLD_MIB,
        "non_leased_threshold_pass": True,
        "non_leased_observed_utilization_gpu_percent": non_leased_utilization,
        "non_leased_tenant_occupancy_at_steady_state": tenant_records,
        "authorized_alternate_tenant_occupancy_at_steady_state": alternate_tenant_records,
        "runtime_log_contract": runtime_log_contract,
        "kit_active_physical_devices": list(
            runtime_log_contract["kit_vulkan_tables_after_app_launcher"][0]["active_physical_devices"]
        ),
        "app_launcher_device": runtime_log_contract["app_launcher"]["device"],
        "environment_device": runtime_log_contract["environment"]["device"],
        "cuda_visible_devices": "UNSET",
        "container_isolation_used": False,
        "first_simulation_step_boundary_crossed": True,
        "first_simulation_step_evidence": runtime_log_contract["first_simulation_step_boundary"]["source_line"],
        "scientific_attempt_started": True,
        "runtime_log": _artifact(log_path),
    }
    validate_steady_evidence(
        evidence,
        plan=plan,
        plan_artifact=plan_artifact,
        log_text=log_text,
        required_pid=process_pid,
        require_fresh=True,
        attempt=attempt,
    )
    _write_json(output_path, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture CPU-side pull-anchor GPU resource evidence.")
    parser.add_argument("--mode", choices=("launch", "steady"), required=True)
    parser.add_argument("--attempt", type=int, choices=(19, 20), default=ATTEMPT)
    parser.add_argument("--plan", "--plan-path", dest="plan_path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--log-path", "--stdout-log", dest="log_path", type=Path, default=None)
    parser.add_argument("--pid", "--process-pid", dest="process_pid", type=int, default=None)
    parser.add_argument("--runner-pid", dest="runner_pid", type=int, default=None)
    args = parser.parse_args()
    default_plan = ATTEMPT19_PLAN_PATH if args.attempt == ATTEMPT else ATTEMPT20_PLAN_PATH
    plan_path = default_plan if args.plan_path is None else args.plan_path
    if args.mode == "launch":
        output = (
            ATTEMPT19_LAUNCH_OCCUPANCY_PATH
            if args.attempt == ATTEMPT and args.output is None
            else ATTEMPT20_LAUNCH_OCCUPANCY_PATH
            if args.output is None
            else args.output
        )
        capture_launch_evidence(plan_path, output_path=output, attempt=args.attempt)
    else:
        if args.log_path is None or args.process_pid is None or args.runner_pid is None:
            parser.error("--mode steady requires --log-path, --pid, and --runner-pid")
        output = (
            ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH
            if args.attempt == ATTEMPT and args.output is None
            else ATTEMPT20_STEADY_STATE_FOOTPRINT_PATH
            if args.output is None
            else args.output
        )
        capture_steady_state_evidence(
            plan_path,
            process_pid=args.process_pid,
            runner_pid=args.runner_pid,
            log_path=args.log_path,
            output_path=output,
            attempt=args.attempt,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
