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
V21B_TRAINING_METRIC_SCHEMA = "a2_piper_base_v21B_training_metric_v1"
V21B_PLAN_ID = "base_v21B_theta_arm_ablation_v1"
V21B_METRIC_KEYS = (
    "send_latch_fire_rate", "hinge_at_send_latch_rad", "hinge_at_crossing_rad",
    "send_to_cross_steps", "stage_overtime_rate", "upper_dof_overspeed_rate",
    "arm_clipped_utilization", "arm_clipped_utilization_valid_rate", "finite_data",
    "decomposition_sanity", "decomposition_sanity_valid_rate",
)
V21B_METRIC_SOURCES = {name: f"a2_v21B_{name}" for name in V21B_METRIC_KEYS}


def _validate_materialization_identity(phase: Any, adaptation: Any, *, label: str) -> None:
    if phase not in ("POST_CENSUS", "FORMAL_PROMOTED"):
        raise V21BError(f"{label} materialization phase is invalid")
    if phase == "POST_CENSUS":
        if adaptation is not None:
            raise V21BError(f"{label} POST_CENSUS adaptation identity must be null")
    elif not isinstance(adaptation, str) or len(adaptation) != 64 or any(char not in "0123456789abcdef" for char in adaptation):
        raise V21BError(f"{label} FORMAL_PROMOTED adaptation identity must be a lowercase sha256 digest")


def build_startup_monitor_plan(formal_plan: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(formal_plan, expected_schema=schema("formal_plan"))
    session = formal_plan.get("session")
    if session != FORMAL_SESSION:
        raise V21BError(f"formal plan must use the dedicated {FORMAL_SESSION!r} tmux session")
    command = ["tmux", "detach-client", "-a", "-s", session]
    if any(token.lower() in {"kill", "kill-session", "kill-window", "terminate", "pkill"} for token in command):
        raise V21BError("startup monitor must never contain a process-kill command")
    rows = formal_plan.get("rows")
    if not isinstance(rows, list) or len(rows) != len(V21B_CELL_ORDER):
        raise V21BError("formal plan must expose exactly seven metric rows")
    metric_paths: dict[str, str] = {}
    metric_expectations: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("cell") not in V21B_CELL_ORDER:
            raise V21BError("formal metric rows must bind one of B1-B7")
        path = row.get("training_metrics_path")
        required = ("seed", "materialization_phase", "source_config_sha256", "materialization_sha256", "materialized_config_sha256", "adaptation_bundle_sha256", "source_lock_sha256", "source_lock_file_sha256", "source_checkpoint_sha256", "repo_commit", "repo_tree")
        digest_required = tuple(key for key in required if key not in ("seed", "materialization_phase"))
        if not isinstance(path, str) or any(not isinstance(row.get(key), str) for key in digest_required):
            raise V21BError("formal metric rows must bind path/source lock/checkpoint/Git identities")
        if isinstance(row.get("seed"), bool) or row.get("seed") not in (0, 1):
            raise V21BError("formal metric rows must bind seed 0 or 1")
        _validate_materialization_identity(row.get("materialization_phase"), row.get("adaptation_bundle_sha256"), label=f"{row['cell']} formal metric row")
        metric_paths[row["cell"]] = path
        metric_expectations[row["cell"]] = {key: row[key] for key in required}
    if set(metric_paths) != set(V21B_CELL_ORDER):
        raise V21BError("formal metric rows must cover all seven cells exactly once")
    return artifact_payload("startup_monitor", status="STATIC_PASS", session=session, watch_iteration=50, detach_command=command, detach_only=True, kill_processes=False, expected_cells=list(V21B_CELL_ORDER), finite_metrics_required=True, contiguous_iterations_required=True, liveness_required=True, global_batch_cap=2500, training_metric_schema=V21B_TRAINING_METRIC_SCHEMA, metric_paths=metric_paths, metric_expectations=metric_expectations, prefix_batches=50, full_trace_required=False)


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


def load_metrics_file(
    path: Path,
    *,
    expected: Mapping[str, Any] | None = None,
    prefix_batches: int | None = None,
) -> list[Mapping[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise V21BError(f"metrics file is missing/non-regular: {path}")
    if Path(path).suffix == ".jsonl":
        if expected is None:
            try:
                first_line = next(line for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip())
                first = json.loads(first_line)
            except (OSError, StopIteration, json.JSONDecodeError) as exc:
                raise V21BError(f"v21-B training metrics JSONL has no usable first row: {path}") from exc
            if not isinstance(first, Mapping):
                raise V21BError("v21-B training metrics JSONL first row must be a mapping")
            expected = {
                "source_lock_sha256": first.get("source_lock_sha256"),
                "source_lock_file_sha256": first.get("source_lock_file_sha256"),
                "source_checkpoint_sha256": first.get("source_checkpoint_sha256"),
                "cell": first.get("cell"),
                "seed": first.get("seed"),
                "materialization_phase": first.get("materialization_phase"),
                "source_config_sha256": first.get("source_config_sha256"),
                "materialization_sha256": first.get("materialization_sha256"),
                "materialized_config_sha256": first.get("materialized_config_sha256"),
                "adaptation_bundle_sha256": first.get("adaptation_bundle_sha256"),
                "repo_commit": first.get("git_commit"),
                "repo_tree": first.get("git_tree"),
            }
        return load_v21b_training_metrics_jsonl(path, expected=expected, prefix_batches=prefix_batches)
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


def _validate_v21b_training_metric_row(row: Mapping[str, Any], *, expected: Mapping[str, Any], batch_index: int) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise V21BError("v21-B training metric JSONL rows must be mappings")
    required_identity = {
        "schema": V21B_TRAINING_METRIC_SCHEMA,
        "producer_state": "PROCESS_COMPLETED",
        "scientific_plan_id": V21B_PLAN_ID,
        "cell": expected.get("cell"),
        "seed": expected.get("seed"),
        "materialization_phase": expected.get("materialization_phase"),
        "source_config_sha256": expected.get("source_config_sha256"),
        "materialization_sha256": expected.get("materialization_sha256"),
        "materialized_config_sha256": expected.get("materialized_config_sha256"),
        "adaptation_bundle_sha256": expected.get("adaptation_bundle_sha256"),
        "source_lock_sha256": expected.get("source_lock_sha256"),
        "source_lock_file_sha256": expected.get("source_lock_file_sha256"),
        "source_checkpoint_sha256": expected.get("source_checkpoint_sha256"),
        "git_commit": expected.get("repo_commit", expected.get("git_commit")),
        "git_tree": expected.get("repo_tree", expected.get("git_tree")),
    }
    if any(row.get(key) != value for key, value in required_identity.items()):
        raise V21BError("v21-B formal metric source-lock/checkpoint/Git identity is invalid")
    _validate_materialization_identity(row.get("materialization_phase"), row.get("adaptation_bundle_sha256"), label="v21-B formal metric row")
    if row.get("cell") not in {"B1", "B2", "B3", "B4", "B5", "B6", "B7"} or isinstance(row.get("seed"), bool) or row.get("seed") not in (0, 1):
        raise V21BError("v21-B formal metric cell/seed identity is invalid")
    if row.get("batch_index") != batch_index:
        raise V21BError("v21-B formal metric batch indices must be exactly contiguous 1..N")
    metrics = row.get("metrics")
    sources = row.get("metric_sources")
    if not isinstance(metrics, Mapping) or set(metrics) != set(V21B_METRIC_KEYS) or not isinstance(sources, Mapping) or dict(sources) != V21B_METRIC_SOURCES:
        raise V21BError("v21-B formal metric normalized sources/coverage are incomplete")
    _validate_metric_value(metrics, path=f"batch{batch_index}.metrics")
    for key, value in metrics.items():
        if isinstance(value, bool):
            if key not in ("finite_data", "decomposition_sanity") or value is not True:
                raise V21BError("v21-B formal boolean sanity metrics must be true")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if key in ("finite_data", "decomposition_sanity") and float(value) != 1.0:
                raise V21BError("v21-B formal numeric sanity metrics must equal one")
        else:
            raise V21BError("v21-B formal metric values must be finite scalars")
    for key in ("arm_clipped_utilization_valid_rate", "decomposition_sanity_valid_rate"):
        if isinstance(metrics.get(key), bool) or metrics.get(key) != 1.0:
            raise V21BError(f"v21-B formal coverage metric {key} must equal one")
    return dict(row)


def load_v21b_training_metrics_jsonl(
    path: Path,
    *,
    expected: Mapping[str, Any],
    prefix_batches: int | None = None,
) -> list[Mapping[str, Any]]:
    """Load authoritative trainer JSONL and return an optional validated prefix.

    The file may already contain rows beyond iteration 50.  All present rows
    are validated for contiguous identity, while callers requesting a prefix
    receive only rows 1..N without rewriting or truncating the producer file.
    """

    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise V21BError(f"v21-B training metrics JSONL is missing/non-regular: {target}")
    if not isinstance(expected, Mapping):
        raise V21BError("v21-B training metric expectation must be a mapping")
    required_expected = (
        "cell", "seed", "materialization_phase", "source_config_sha256", "materialization_sha256",
        "materialized_config_sha256", "adaptation_bundle_sha256",
        "source_lock_sha256", "source_lock_file_sha256", "source_checkpoint_sha256",
        "repo_commit", "repo_tree",
    )
    if any(key not in expected or (expected.get(key) is None and key != "adaptation_bundle_sha256") for key in required_expected):
        raise V21BError("v21-B training metric expectation is missing exact cell/seed/materialization identity")
    _validate_materialization_identity(expected.get("materialization_phase"), expected.get("adaptation_bundle_sha256"), label="v21-B training metric expectation")
    rows: list[Mapping[str, Any]] = []
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise V21BError(f"v21-B training metrics JSONL cannot be read: {target}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise V21BError("v21-B training metrics JSONL contains an empty line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise V21BError(f"v21-B training metrics JSONL line {line_number} is invalid JSON") from exc
        rows.append(_validate_v21b_training_metric_row(row, expected=expected, batch_index=line_number))
    if not rows:
        raise V21BError("v21-B training metrics JSONL is empty")
    if prefix_batches is not None:
        if isinstance(prefix_batches, bool) or not isinstance(prefix_batches, int) or prefix_batches <= 0 or len(rows) < prefix_batches:
            raise V21BError("v21-B training metrics JSONL does not contain the requested authoritative prefix")
        return rows[:prefix_batches]
    return rows


def load_formal_metrics_prefix(formal_plan: Mapping[str, Any], *, prefix_batches: int = 50) -> dict[str, list[Mapping[str, Any]]]:
    validate_artifact(formal_plan, expected_schema=schema("formal_plan"))
    rows = formal_plan.get("rows")
    if not isinstance(rows, list) or len(rows) != len(V21B_CELL_ORDER):
        raise V21BError("formal plan does not expose exact per-cell metric paths")
    result: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise V21BError("formal plan metric row is malformed")
        cell = row.get("cell")
        path = row.get("training_metrics_path")
        if cell not in V21B_CELL_ORDER or not isinstance(path, str):
            raise V21BError("formal plan metric row path/cell is invalid")
        result[cell] = load_v21b_training_metrics_jsonl(
            Path(path),
            expected={
                "cell": row["cell"],
                "seed": row["seed"],
                "materialization_phase": row["materialization_phase"],
                "source_config_sha256": row["source_config_sha256"],
                "materialization_sha256": row["materialization_sha256"],
                "materialized_config_sha256": row["materialized_config_sha256"],
                "adaptation_bundle_sha256": row["adaptation_bundle_sha256"],
                "source_lock_sha256": row["source_lock_sha256"],
                "source_lock_file_sha256": row["source_lock_file_sha256"],
                "source_checkpoint_sha256": row["source_checkpoint_sha256"],
                "repo_commit": row["repo_commit"],
                "repo_tree": row["repo_tree"],
            },
            prefix_batches=prefix_batches,
        )
    if set(result) != set(V21B_CELL_ORDER):
        raise V21BError("formal metric prefix is missing one or more cells")
    return result


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
        first_row = entries[0]
        if not isinstance(first_row, Mapping) or "batch_index" not in first_row or first_row.get("schema") != V21B_TRAINING_METRIC_SCHEMA:
            raise V21BError(f"{cell} startup metrics must be authoritative v21-B training rows")
        formal_row = next((row for row in formal_plan["rows"] if row.get("cell") == cell), None)
        if not isinstance(formal_row, Mapping):
            raise V21BError(f"{cell} formal metric binding is missing")
        expected_identity = {
            "cell": formal_row["cell"],
            "seed": formal_row["seed"],
            "materialization_phase": formal_row["materialization_phase"],
            "source_config_sha256": formal_row["source_config_sha256"],
            "materialization_sha256": formal_row["materialization_sha256"],
            "materialized_config_sha256": formal_row["materialized_config_sha256"],
            "adaptation_bundle_sha256": formal_row["adaptation_bundle_sha256"],
            "source_lock_sha256": formal_row["source_lock_sha256"],
            "source_lock_file_sha256": formal_row["source_lock_file_sha256"],
            "source_checkpoint_sha256": formal_row["source_checkpoint_sha256"],
            "repo_commit": formal_row["repo_commit"],
            "repo_tree": formal_row["repo_tree"],
        }
        for index, entry in enumerate(entries, start=1):
            _validate_v21b_training_metric_row(entry, expected=expected_identity, batch_index=index)
        iterations = [entry["batch_index"] for entry in entries]
        if len(entries) < 50 or iterations != list(range(1, len(entries) + 1)):
            raise V21BError(f"{cell} startup metrics are not contiguous from batch 1 through iteration50")
        at50 = next(entry for entry in entries if entry["batch_index"] == 50)
        live = liveness_by_cell[cell]
        required_live = ("session_exists", "pane_dead", "process_alive", "session_attached")
        if any(key not in live for key in required_live):
            raise V21BError(f"{cell} liveness record is incomplete")
        if live["session_exists"] is not True or live["pane_dead"] is not False or live["process_alive"] is not True or live["session_attached"] not in (0, False):
            raise V21BError(f"{cell} is not alive and detached at iteration50")
        rows.append({"cell": cell, "iteration50": at50, "contiguous_start": iterations[0], "contiguous_end": iterations[-1], "liveness": dict(live), "metrics_path": formal_row["training_metrics_path"]})
    return artifact_payload("startup_monitor", status="STARTUP_50_PASS", session=formal_plan["session"], watch_iteration=50, prefix_batches=50, rows=rows, detach_only=True, kill_processes=False, training_continues=True, formal_completion=False, session_state=dict(session_state), global_batch_cap=2500, full_trace_required=False)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["FORMAL_SESSION", "V21B_TRAINING_METRIC_SCHEMA", "build_startup_monitor_plan", "load_metrics_file", "load_v21b_training_metrics_jsonl", "load_formal_metrics_prefix", "collect_tmux_liveness", "monitor_iteration50", "main"]
