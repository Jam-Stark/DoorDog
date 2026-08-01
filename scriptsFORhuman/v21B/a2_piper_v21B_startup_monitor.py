"""Iteration-50 startup monitor that detaches without stopping training."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._v21b_common import V21B_CELL_ORDER, V21BError
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact


FORMAL_SESSION = "base_v21B_formal_v1"


def build_startup_monitor_plan(formal_plan: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(formal_plan, expected_schema=schema("formal_plan"))
    session = formal_plan.get("session")
    if session != FORMAL_SESSION:
        raise V21BError(f"formal plan must use the dedicated {FORMAL_SESSION!r} tmux session")
    command = ["tmux", "detach-client", "-a", "-s", session]
    if any(token.lower() in {"kill", "kill-session", "kill-window", "terminate", "pkill"} for token in command):
        raise V21BError("startup monitor must never contain a process-kill command")
    return artifact_payload("startup_monitor", status="STATIC_PASS", session=session, watch_iteration=50, detach_command=command, detach_only=True, kill_processes=False, expected_cells=list(V21B_CELL_ORDER), finite_metrics_required=True, contiguous_iterations_required=True, liveness_required=True, global_batch_cap=2500)


def _validate_metric_value(value: Any, *, path: str) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise V21BError(f"{path} is non-finite")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _validate_metric_value(item, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _validate_metric_value(item, path=f"{path}[{index}]")
        return
    raise V21BError(f"{path} has an unsupported metric type")


def load_metrics_file(path: Path) -> list[Mapping[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise V21BError(f"metrics file is missing/non-regular: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V21BError(f"metrics file is not valid JSON: {path}") from exc
    if isinstance(value, Mapping):
        value = value.get("metrics")
    if not isinstance(value, list) or not value:
        raise V21BError("metrics file must contain a non-empty list")
    if any(not isinstance(item, Mapping) for item in value):
        raise V21BError("metrics file entries must be mappings")
    return value


def collect_tmux_liveness(session: str, *, tmux_binary: str = "tmux") -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Read detached-session/window/pane liveness from the actual tmux server."""

    if session != FORMAL_SESSION:
        raise V21BError(f"tmux liveness is restricted to the dedicated {FORMAL_SESSION!r} session")
    try:
        has_session = subprocess.run(
            [tmux_binary, "has-session", "-t", session],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise V21BError(f"tmux liveness command failed to start: {tmux_binary!r}") from exc
    if has_session.returncode != 0:
        raise V21BError(f"tmux session does not exist: {session}")
    try:
        attached = subprocess.run(
            [tmux_binary, "display-message", "-p", "-t", session, "#{session_attached}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        panes = subprocess.run(
            [
                tmux_binary,
                "list-panes",
                "-s",
                "-t",
                session,
                "-F",
                "#{window_name}\t#{pane_dead}\t#{pane_pid}",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise V21BError(f"tmux liveness query failed for session {session!r}") from exc
    if attached not in {"0", "1"}:
        raise V21BError(f"tmux session attachment state is invalid: {attached!r}")
    rows: dict[str, dict[str, Any]] = {}
    for line in panes:
        parts = line.split("\t")
        if len(parts) != 3:
            raise V21BError(f"tmux pane liveness row is malformed: {line!r}")
        window, dead_text, pid_text = parts
        if window in rows or window not in V21B_CELL_ORDER:
            raise V21BError(f"tmux pane window is not one-to-one with v21-B cells: {window!r}")
        if dead_text not in {"0", "1"}:
            raise V21BError(f"tmux pane dead flag is invalid for {window}: {dead_text!r}")
        try:
            pid = int(pid_text)
        except ValueError as exc:
            raise V21BError(f"tmux pane pid is invalid for {window}: {pid_text!r}") from exc
        if pid <= 0:
            raise V21BError(f"tmux pane pid must be positive for {window}")
        try:
            os.kill(pid, 0)
            process_alive = True
        except ProcessLookupError:
            process_alive = False
        except PermissionError:
            process_alive = True
        rows[window] = {
            "session_exists": True,
            "pane_dead": dead_text == "1",
            "process_alive": process_alive,
            "session_attached": int(attached),
            "pane_pid": pid,
        }
    if set(rows) != set(V21B_CELL_ORDER):
        raise V21BError(f"tmux liveness is missing cells: {sorted(set(V21B_CELL_ORDER) - set(rows))}")
    session_state = {"session_exists": True, "session_attached": int(attached)}
    return rows, session_state


def monitor_iteration50(metrics_by_cell: Mapping[str, Sequence[Mapping[str, Any]]], *, formal_plan: Mapping[str, Any], liveness_by_cell: Mapping[str, Mapping[str, Any]], session_state: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(formal_plan, expected_schema=schema("formal_plan"))
    if formal_plan.get("session") != FORMAL_SESSION:
        raise V21BError(f"iteration-50 monitor is restricted to {FORMAL_SESSION!r}")
    if set(metrics_by_cell) != set(V21B_CELL_ORDER):
        raise V21BError("iteration-50 monitor requires all seven B1-B7 cells")
    if formal_plan.get("batches") != 2500 or formal_plan.get("num_envs") != 4096:
        raise V21BError("formal plan does not prove the exact 4096/2500 global trainer cap")
    if set(liveness_by_cell) != set(V21B_CELL_ORDER):
        raise V21BError("iteration-50 monitor requires liveness for every formal cell")
    if not isinstance(session_state, Mapping) or session_state.get("session_exists") is not True or session_state.get("session_attached") not in (0, False):
        raise V21BError("formal tmux session must exist and have zero attached clients after detach")
    rows = []
    for cell in V21B_CELL_ORDER:
        entries = metrics_by_cell[cell]
        if not isinstance(entries, Sequence) or not entries:
            raise V21BError(f"{cell} has no startup metrics")
        iterations = [entry.get("iteration") for entry in entries]
        if any(isinstance(value, bool) or not isinstance(value, int) for value in iterations):
            raise V21BError(f"{cell} iteration values must be integers")
        expected = list(range(iterations[0], iterations[0] + len(iterations)))
        if iterations[0] not in (0, 1) or len(iterations) < 51 or iterations != expected or iterations[-1] < 50:
            raise V21BError(f"{cell} startup metrics are not contiguous from batch 0/1 through iteration50")
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping) or "metrics" not in entry:
                raise V21BError(f"{cell} iteration {iterations[index]} has no metrics mapping")
            _validate_metric_value(entry["metrics"], path=f"{cell}[{iterations[index]}]")
        at50 = next(entry for entry in entries if entry["iteration"] == 50)
        live = liveness_by_cell[cell]
        required_live = ("session_exists", "pane_dead", "process_alive", "session_attached")
        if any(key not in live for key in required_live):
            raise V21BError(f"{cell} liveness record is incomplete")
        if live["session_exists"] is not True or live["pane_dead"] is not False or live["process_alive"] is not True or live["session_attached"] not in (0, False):
            raise V21BError(f"{cell} is not alive and detached at iteration50")
        rows.append({"cell": cell, "iteration50": at50, "contiguous_start": iterations[0], "contiguous_end": iterations[-1], "liveness": dict(live)})
    return artifact_payload("startup_monitor", status="STARTUP_50_PASS", session=formal_plan["session"], watch_iteration=50, rows=rows, detach_only=True, kill_processes=False, training_continues=True, formal_completion=False, session_state=dict(session_state), global_batch_cap=2500)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["FORMAL_SESSION", "build_startup_monitor_plan", "load_metrics_file", "collect_tmux_liveness", "monitor_iteration50", "main"]
