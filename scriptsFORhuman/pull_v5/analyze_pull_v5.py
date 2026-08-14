#!/usr/bin/env python3
"""Strict dual-source Pull-v5.2 terminal-record analyzer.

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
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "PULL_V5_2_ANALYSIS.json"
TERMINAL_FILENAME = "terminal_records.json"
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
    "override_active_outside_canonical_start",
)


def _json_documents(input_roots: Iterable[Path]) -> Iterable[tuple[Path, Any]]:
    """Read only explicitly supplied v5.2 cell roots; never recurse a log tree."""

    for root in input_roots:
        root = root.resolve()
        if root.is_file():
            if root.name != TERMINAL_FILENAME:
                raise ValueError(f"an explicit analyzer file must be named {TERMINAL_FILENAME}: {root}")
            if root.parent.parent.resolve() != DEFAULT_INPUT.resolve() or not root.parent.name.startswith("pull_v5_2_"):
                raise ValueError(f"analyzer terminal file must be under an explicit pull_v5_2_* directory: {root}")
            path = root
        elif root.is_dir():
            if root.parent.resolve() != DEFAULT_INPUT.resolve() or not root.name.startswith("pull_v5_2_"):
                raise ValueError(f"analyzer cell root must be an explicit pull_v5_2_* directory under {DEFAULT_INPUT}: {root}")
            path = root / TERMINAL_FILENAME
            if not path.is_file():
                raise FileNotFoundError(path)
        else:
            raise FileNotFoundError(root)
        yield path, json.loads(path.read_text(encoding="utf-8"))


def _terminal_rows(path: Path, document: Any) -> list[dict[str, Any]]:
    """Extract one explicit terminal collection from a known terminal file."""

    candidates: Any = document if isinstance(document, list) else (
        document.get("records") if isinstance(document, Mapping) else None
    )
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


def _source(row: Mapping[str, Any]) -> str:
    value = row.get("reset_source")
    if value is None and isinstance(row.get("pull_v5"), Mapping):
        value = row["pull_v5"].get("reset_source")
    if value != "natural" and value != "bank_natural_e5_override":
        raise ValueError(f"terminal row reset_source must be natural or bank_natural_e5_override; got {value!r}")
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
    if row.get("schema") != "a2_piper_pull_v5_2_terminal_record_v1":
        raise ValueError("terminal row schema must be a normalized Pull-v5.2 terminal record")
    run_id = _required_string(row, "run_id")
    cell = _required_string(row, "cell")
    checkpoint = _required_string(row, "checkpoint")
    episode_id = row.get("episode_id")
    if isinstance(episode_id, bool) or not isinstance(episode_id, int) or episode_id < 0:
        raise ValueError("terminal row episode_id must be a non-negative integer")
    source_provenance = _source(row)
    source = "canonical_bank" if source_provenance == "bank_natural_e5_override" else "natural"
    declared_source = row.get("source")
    if declared_source not in {"canonical_bank", "natural"} or declared_source != source:
        raise ValueError(
            f"terminal row source must explicitly match reset_source-derived source {source!r}; "
            f"got {declared_source!r}"
        )
    dv_source = row.get("dv_source")
    if dv_source not in {"natural", "canonical_bank"}:
        raise ValueError("terminal row dv_source must be natural or canonical_bank")
    frame_passage = _required_bool(row, "frame_passage")
    persistent_release = _required_bool(row, "persistent_release")
    complete = _required_bool(row, "complete")
    e6 = row.get("E6_PATH_REVERSAL_ENTRY")
    e7 = row.get("E7_WHOLE_BODY_CLEAR")
    if not isinstance(e6, bool) or not isinstance(e7, bool):
        raise ValueError("terminal row requires bool E6_PATH_REVERSAL_ENTRY/E7_WHOLE_BODY_CLEAR")
    settle_valid = _required_bool(row, "settle_valid")
    bank_settle_valid = row.get("bank_settle_valid")
    if source == "canonical_bank":
        if bank_settle_valid is not True:
            raise ValueError("canonical terminal row requires bank_settle_valid=true")
    elif bank_settle_valid is not None:
        raise ValueError("natural terminal row must not carry bank_settle_valid")
    force = _required_finite(row, "hinge_drive_max_force_nm")
    invariants = _invariant_values(row)
    if source == "canonical_bank" and dv_source == "natural":
        raise ValueError("canonical source row cannot use natural dv_source")
    if source == "natural" and dv_source != "natural":
        raise ValueError("natural source row cannot use canonical dv_source")
    start_override_active = _required_bool(row, "start_override_active")
    start_override_steps = row.get("start_override_active_steps")
    if isinstance(start_override_steps, bool) or not isinstance(start_override_steps, int) or start_override_steps < 0:
        raise ValueError("terminal row start_override_active_steps must be a non-negative integer")
    start_override_base_slice_equal = _required_bool(row, "start_override_base_slice_equal")
    if source == "canonical_bank" and not start_override_active:
        raise ValueError("canonical terminal row must activate start override")
    if source == "natural" and start_override_active:
        raise ValueError("natural terminal row must not activate start override")
    passage_hinge = row.get("passage_attempt_hinge_rad")
    if frame_passage:
        passage_hinge = _required_finite(row, "passage_attempt_hinge_rad")
    elif passage_hinge is not None:
        raise ValueError("non-passage terminal row must carry null passage_attempt_hinge_rad")
    panel_contact_steps = row.get("panel_contact_steps_per_20s")
    if isinstance(panel_contact_steps, bool) or not isinstance(panel_contact_steps, int) or panel_contact_steps < 0:
        raise ValueError("terminal row panel_contact_steps_per_20s must be a non-negative integer")
    recontact = row.get("post_release_recontact_count")
    if isinstance(recontact, bool) or not isinstance(recontact, int) or recontact < 0:
        raise ValueError("terminal row post_release_recontact_count must be a non-negative integer")
    midpoint = _required_finite(row, "frame_midpoint_distance_min_m")
    door_hinge = _required_finite(row, "door_hinge_joint_pos")
    return {
        "run_id": run_id,
        "cell": cell,
        "checkpoint": checkpoint,
        "episode_id": episode_id,
        "source": source,
        "source_provenance": source_provenance,
        "dv_source": dv_source,
        "frame_passage": frame_passage,
        "persistent_release": persistent_release,
        "complete": complete,
        "e6": e6,
        "e7": e7,
        "settle_valid": settle_valid,
        "bank_settle_valid": bank_settle_valid,
        "start_override_active": start_override_active,
        "start_override_active_steps": start_override_steps,
        "start_override_base_slice_equal": start_override_base_slice_equal,
        "passage_attempt_hinge_rad": passage_hinge,
        "door_hinge_joint_pos": door_hinge,
        "panel_contact_steps_per_20s": panel_contact_steps,
        "post_release_recontact_count": recontact,
        "frame_midpoint_distance_min_m": midpoint,
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


def analyze(input_roots: Iterable[Path]) -> dict[str, Any]:
    if isinstance(input_roots, (str, Path)):
        input_roots = [Path(input_roots)]
    raw_rows: list[dict[str, Any]] = []
    roots = [Path(root).resolve() for root in input_roots]
    if not roots:
        raise ValueError("analyzer requires at least one explicit v5.2 cell root")
    for path, document in _json_documents(roots):
        raw_rows.extend(_terminal_rows(path, document))
    if not raw_rows:
        raise ValueError("no explicit terminal episode records found")
    rows = [_normalize(row) for row in raw_rows]
    seen: set[tuple[str, str, str, int, str]] = set()
    groups: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    violations = Counter({name: 0 for name in INVARIANTS})
    closer: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "episodes": 0,
            "frame_passage": 0,
            "persistent_release": 0,
            "panel_contact_steps_per_20s": 0,
            "post_release_recontact_count": 0,
            "frame_midpoint_distance_min_m": None,
            "passage_attempt_hinge_rad": [],
            "by_source": defaultdict(
                lambda: {
                    "episodes": 0,
                    "frame_passage": 0,
                    "persistent_release": 0,
                    "panel_contact_steps_per_20s": 0,
                    "post_release_recontact_count": 0,
                    "frame_midpoint_distance_min_m": None,
                    "passage_attempt_hinge_rad": [],
                }
            ),
        }
    )
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
        bucket["panel_contact_steps_per_20s"] += row["panel_contact_steps_per_20s"]
        bucket["post_release_recontact_count"] += row["post_release_recontact_count"]
        midpoint = bucket["frame_midpoint_distance_min_m"]
        bucket["frame_midpoint_distance_min_m"] = row["frame_midpoint_distance_min_m"] if midpoint is None else min(midpoint, row["frame_midpoint_distance_min_m"])
        if row["passage_attempt_hinge_rad"] is not None:
            bucket["passage_attempt_hinge_rad"].append(row["passage_attempt_hinge_rad"])
        source_bucket = bucket["by_source"][row["source"]]
        source_bucket["episodes"] += 1
        source_bucket["frame_passage"] += int(row["frame_passage"])
        source_bucket["persistent_release"] += int(row["persistent_release"])
        source_bucket["panel_contact_steps_per_20s"] += row["panel_contact_steps_per_20s"]
        source_bucket["post_release_recontact_count"] += row["post_release_recontact_count"]
        source_midpoint = source_bucket["frame_midpoint_distance_min_m"]
        source_bucket["frame_midpoint_distance_min_m"] = row["frame_midpoint_distance_min_m"] if source_midpoint is None else min(source_midpoint, row["frame_midpoint_distance_min_m"])
        if row["passage_attempt_hinge_rad"] is not None:
            source_bucket["passage_attempt_hinge_rad"].append(row["passage_attempt_hinge_rad"])
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
    def _finalize_strata(value: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(value)
        by_source = result.get("by_source")
        if isinstance(by_source, Mapping):
            result["by_source"] = {
                source: _finalize_strata(source_value)
                for source, source_value in by_source.items()
            }
        hinges = result.get("passage_attempt_hinge_rad")
        if isinstance(hinges, list):
            result["passage_attempt_hinge_rad"] = {
                "count": len(hinges),
                "values": hinges,
            }
        return result

    return {
        "schema": "a2_piper_pull_v5_2_analysis_v1",
        "status": status,
        "input_roots": [str(root) for root in roots],
        "episode_count": len(rows),
        "cell_checkpoint_counts": {f"{cell}|{checkpoint}": dict(counts) for (cell, checkpoint), counts in groups.items()},
        "sources": {
            "canonical": summarize("canonical_bank"),
            "natural": summarize("natural"),
        },
        "closer_buckets": {bucket: _finalize_strata(summary) for bucket, summary in closer.items()},
        "dual_source": {
            source: {
                "frame_passage": summarize(source)["frame_passage_rate"],
                "K25_persistent_release": summarize(source)["persistent_release_rate"],
                "passage_hinge_count": sum(
                    1 for row in rows if row["source"] == source and row["passage_attempt_hinge_rad"] is not None
                ),
            }
            for source in ("canonical_bank", "natural")
        },
        "invariants": {name: {"status": "FAIL" if count else "PASS", "violations": count} for name, count in violations.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--cell-root", type=Path, action="append", dest="cell_roots")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    roots = args.cell_roots or ([args.input_root] if args.input_root is not None else None)
    if roots is None:
        raise SystemExit("analyzer requires --cell-root at least once")
    report = analyze(roots)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
