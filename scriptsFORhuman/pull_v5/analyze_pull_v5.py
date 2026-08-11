#!/usr/bin/env python3
"""Strict dual-source Pull-v5 terminal-record analyzer.

Only explicit terminal episode collections are accepted.  Step traces, control
records, and recursively discovered nested mappings are intentionally rejected
so one episode cannot be counted more than once.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "logs_eval/a2_piper_pull_v5"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "PULL_V5_ANALYSIS.json"
TERMINAL_FILENAMES = frozenset(
    {"terminal_diagnostics.json", "episode_records.json", "metrics_eval.json", "PULL_V5_TERMINAL.json"}
)
INVARIANTS = (
    "fake_e4",
    "stage4_snapshot_below_hinge_gate",
    "dont_push_before_true_stage3_to4",
    "target_root_before_aperture_ready",
    "corridor_active_before_aperture_ready",
    "complete_without_frame_passage",
    "frame_approach_active_before_aperture_ready",
    "frame_approach_active_after_frame_passage",
    "canonical_not_counted_as_natural_start",
    "failed_settle_not_in_bank",
)


def _json_documents(input_root: Path) -> Iterable[tuple[Path, Any]]:
    if not input_root.is_dir():
        raise FileNotFoundError(input_root)
    for path in sorted(input_root.rglob("*.json")):
        if path.name not in TERMINAL_FILENAMES:
            continue
        yield path, json.loads(path.read_text(encoding="utf-8"))


def _terminal_rows(path: Path, document: Any) -> list[dict[str, Any]]:
    """Extract one explicit terminal collection from a known terminal file."""

    candidates: Any = None
    if isinstance(document, list):
        candidates = document
    elif isinstance(document, Mapping):
        for key in ("terminal_episode_records", "episode_terminal_diagnostics", "episode_records", "records"):
            if key in document:
                candidates = document[key]
                break
        if candidates is None and path.name in {"terminal_diagnostics.json", "episode_records.json", "PULL_V5_TERMINAL.json"}:
            candidates = [document]
    if not isinstance(candidates, list) or not candidates:
        raise ValueError(f"{path} must contain a non-empty explicit terminal episode collection")
    rows: list[dict[str, Any]] = []
    for row in candidates:
        if not isinstance(row, Mapping):
            raise ValueError(f"{path} terminal collection contains a non-mapping row")
        value = dict(row)
        value["_terminal_file"] = str(path)
        # Binding metadata is allowed at the document level only when a row has
        # not supplied it; absent metadata remains a hard error below.
        if isinstance(document, Mapping):
            for key in ("run_id", "cell", "checkpoint"):
                if key not in value and key in document:
                    value[key] = document[key]
        rows.append(value)
    return rows


def _required_string(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"terminal row is missing non-empty {key!r}")
    return value


def _required_bool(row: Mapping[str, Any], key: str) -> bool:
    value = row.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"terminal row field {key!r} must be bool")
    return value


def _required_finite(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"terminal row field {key!r} must be finite numeric")
    return float(value)


def _episode_value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    episode = row.get("pull_v0_episode")
    if isinstance(episode, Mapping):
        for key in keys:
            if key in episode:
                return episode[key]
    return None


def _event_bool(row: Mapping[str, Any], name: str, aliases: tuple[str, ...] = ()) -> bool:
    event = row.get("event_reached")
    if isinstance(event, Mapping) and name in event:
        value = event[name]
    else:
        value = _episode_value(row, name, *aliases)
    if not isinstance(value, bool):
        raise ValueError(f"terminal row is missing bool event field {name!r}")
    return value


def _source(row: Mapping[str, Any]) -> str:
    pull_v5 = row.get("pull_v5")
    value = pull_v5.get("reset_source") if isinstance(pull_v5, Mapping) else row.get("reset_source")
    if value not in {"natural", "canonical_bank"}:
        raise ValueError(f"terminal row reset_source must be natural or canonical_bank; got {value!r}")
    return str(value)


def _invariant_values(row: Mapping[str, Any]) -> dict[str, bool]:
    nested = row.get("invariants")
    if not isinstance(nested, Mapping):
        nested = row.get("pull_v5", {}).get("invariants") if isinstance(row.get("pull_v5"), Mapping) else None
    if not isinstance(nested, Mapping):
        raise ValueError("terminal row requires an explicit invariants mapping")
    values: dict[str, bool] = {}
    for name in INVARIANTS:
        value = nested.get(name)
        if not isinstance(value, bool):
            raise ValueError(f"terminal row invariant {name!r} must be bool")
        values[name] = value
    return values


def _normalize(row: Mapping[str, Any]) -> dict[str, Any]:
    run_id = _required_string(row, "run_id")
    cell = _required_string(row, "cell")
    checkpoint = _required_string(row, "checkpoint")
    episode_id = row.get("episode_id")
    if isinstance(episode_id, bool) or not isinstance(episode_id, int) or episode_id < 0:
        raise ValueError("terminal row episode_id must be a non-negative integer")
    source = _source(row)
    dv_source = row.get("dv_source")
    if dv_source not in {"natural", "canonical_bank"}:
        raise ValueError("terminal row dv_source must be natural or canonical_bank")
    frame_passage = _required_bool(row, "frame_passage")
    persistent_release = _required_bool(row, "persistent_release")
    complete = _required_bool(row, "complete")
    e6 = _event_bool(row, "E6_PATH_REVERSAL_ENTRY", ("e6", "path_reversal"))
    e7 = _event_bool(row, "E7_WHOLE_BODY_CLEAR", ("e7", "whole_body_clear"))
    settle_valid = _required_bool(row, "settle_valid")
    force = _required_finite(row, "hinge_drive_max_force_nm")
    invariants = _invariant_values(row)
    invariants["canonical_not_counted_as_natural_start"] = source == "canonical_bank" and dv_source == "natural"
    invariants["failed_settle_not_in_bank"] = source == "canonical_bank" and not settle_valid
    return {
        "run_id": run_id,
        "cell": cell,
        "checkpoint": checkpoint,
        "episode_id": episode_id,
        "source": source,
        "dv_source": dv_source,
        "frame_passage": frame_passage,
        "persistent_release": persistent_release,
        "complete": complete,
        "e6": e6,
        "e7": e7,
        "settle_valid": settle_valid,
        "hinge_drive_max_force_nm": force,
        "invariants": invariants,
    }


def _bucket(force: float) -> str:
    if 2.5 <= force < 5.0:
        return "2.5-5"
    if 5.0 <= force < 9.0:
        return "5-9"
    if 9.0 <= force <= 12.0:
        return "9-12"
    return "outside"


def analyze(input_root: Path) -> dict[str, Any]:
    raw_rows: list[dict[str, Any]] = []
    for path, document in _json_documents(input_root):
        raw_rows.extend(_terminal_rows(path, document))
    if not raw_rows:
        raise ValueError("no explicit terminal episode records found")
    rows = [_normalize(row) for row in raw_rows]
    seen: set[tuple[str, str, str, int, str]] = set()
    groups: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    violations = Counter({name: 0 for name in INVARIANTS})
    closer: dict[str, dict[str, int]] = defaultdict(lambda: {"episodes": 0, "frame_passage": 0, "persistent_release": 0})
    for row in rows:
        identity = (row["run_id"], row["cell"], row["checkpoint"], row["episode_id"], row["source"])
        if identity in seen:
            raise ValueError(f"duplicate terminal episode identity: {identity}")
        seen.add(identity)
        groups[(row["cell"], row["checkpoint"])][row["source"]] += 1
        for name, failed in row["invariants"].items():
            if failed:
                violations[name] += 1
        bucket = closer[_bucket(row["hinge_drive_max_force_nm"])]
        bucket["episodes"] += 1
        bucket["frame_passage"] += int(row["frame_passage"])
        bucket["persistent_release"] += int(row["persistent_release"])
    for key, counts in groups.items():
        if counts["canonical_bank"] != 16 or counts["natural"] != 16:
            raise ValueError(
                f"{key} requires exactly 16 canonical_bank and 16 natural terminal episodes; "
                f"got {dict(counts)}"
            )
    def summarize(source: str) -> dict[str, Any]:
        subset = [row for row in rows if row["source"] == source]
        count = len(subset)
        return {
            "episodes": count,
            "frame_passage_rate": sum(row["frame_passage"] for row in subset) / count,
            "persistent_release_rate": sum(row["persistent_release"] for row in subset) / count,
            "E6_rate": sum(row["e6"] for row in subset) / count,
            "E7_rate": sum(row["e7"] for row in subset) / count,
            "complete_rate": sum(row["complete"] for row in subset) / count,
            "settle_valid_rate": sum(row["settle_valid"] for row in subset) / count,
        }
    status = "PASS" if not any(violations.values()) else "FAIL"
    return {
        "schema": "a2_piper_pull_v5_analysis_v2",
        "status": status,
        "input_root": str(input_root),
        "episode_count": len(rows),
        "cell_checkpoint_counts": {f"{cell}|{checkpoint}": dict(counts) for (cell, checkpoint), counts in groups.items()},
        "sources": {source: summarize(source) for source in ("canonical_bank", "natural")},
        "closer_buckets": dict(closer),
        "invariants": {name: {"status": "FAIL" if count else "PASS", "violations": count} for name, count in violations.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = analyze(args.input_root.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
