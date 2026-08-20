#!/usr/bin/env python3
"""Fail-fast formal bridge and downstream gates for Pull-v5.6.

The gates are intentionally independent of the v5.6 characterization runner.
Formal anchor/door positioning may use the specialist, while P3/P4 and
dual-source DV receipts must explicitly show that specialist provenance is
inactive and that invariant 12-prime is false/null.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PLAN_ID = "a2_piper_pull_v5_6_formal_bridge"
ANCHOR_SCHEMA = "a2_piper_pull_v5_6_formal_anchor_receipt_v1"
DOOR_SCHEMA = "a2_piper_pull_v5_6_formal_door_receipt_v1"
G2_SCHEMA = "a2_piper_pull_v5_6_formal_g2_receipt_v1"
P3_SCHEMA = "a2_piper_pull_v5_6_formal_p3_receipt_v1"
P4_SCHEMA = "a2_piper_pull_v5_6_formal_p4_receipt_v1"
DUAL_EVAL_SCHEMA = "a2_piper_pull_v5_6_formal_dual_eval_receipt_v1"
RENDER_SCHEMA = "a2_piper_pull_v5_6_formal_render_index_v1"
SEQUENCES = ("S1", "S2", "S3", "S4")
BUCKETS = ("2.5-5", "5-9", "9-12")
TERMINAL_HOLD_STEPS = 100
WAYPOINT_TOLERANCE_M = 0.05
YAW_TOLERANCE_RAD = 0.15
MAX_ANCHOR_ATTEMPTS = 3


class GateRejected(RuntimeError):
    """Raised when a formal receipt is missing, stale, or malformed."""


def _read(value: Path | Mapping[str, Any], label: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    path = value.expanduser().resolve()
    if path.is_symlink() or not path.is_file():
        raise GateRejected(f"{label} is missing or not a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateRejected(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, Mapping):
        raise GateRejected(f"{label} must be a JSON object")
    return payload


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise GateRejected(f"{label} must be finite numeric")
    return float(value)


def _require(payload: Mapping[str, Any], key: str, expected: object, label: str) -> None:
    if payload.get(key) != expected:
        raise GateRejected(f"{label}.{key} must equal {expected!r}; got {payload.get(key)!r}")


def _formal_identity(payload: Mapping[str, Any], schema: str, label: str) -> None:
    _require(payload, "schema", schema, label)
    _require(payload, "plan_id", PLAN_ID, label)
    if payload.get("status") not in {"PASS", "FAIL"}:
        raise GateRejected(f"{label}.status must be PASS or FAIL")


def _formal_row(row: object, label: str, *, phase: str, specialist_active: bool) -> Mapping[str, Any]:
    if not isinstance(row, Mapping):
        raise GateRejected(f"{label} must be a mapping")
    if row.get("record_class") != "interface_characterization":
        raise GateRejected(f"{label}.record_class must be interface_characterization")
    if row.get("scientific_denominator_included") is not False or row.get("denominator_scope") not in (None, "none"):
        raise GateRejected(f"{label} must be denominator-excluded")
    if row.get("terminal_after_step") is not True or row.get("returned_dones_binding") != "env.step returned dones":
        raise GateRejected(f"{label} must bind terminal timing to returned env.step dones")
    if row.get("terminal_current_state") is not True or row.get("done") is not True:
        raise GateRejected(f"{label} must be a terminal-current DONE row")
    if row.get("terminal_hold_steps") != TERMINAL_HOLD_STEPS:
        raise GateRejected(f"{label}.terminal_hold_steps must equal {TERMINAL_HOLD_STEPS}")
    if row.get("phase") != phase:
        raise GateRejected(f"{label}.phase must equal {phase!r}")
    if row.get("specialist_active") is not specialist_active:
        raise GateRejected(f"{label}.specialist_active must equal {specialist_active}")
    if phase in {"anchor", "door_positioning"}:
        xy = _finite(row.get("xy_error_m"), f"{label}.xy_error_m")
        yaw = _finite(row.get("yaw_error_rad"), f"{label}.yaw_error_rad")
        if xy > WAYPOINT_TOLERANCE_M or abs(yaw) > YAW_TOLERANCE_RAD:
            raise GateRejected(f"{label} exceeds 0.05 m/0.15 rad terminal tolerance")
    invariant = row.get("invariant12_prime")
    if specialist_active:
        if not isinstance(invariant, Mapping) or invariant.get("status") != "PASS" or invariant.get("specialist_terminal_positioning_only") is not True:
            raise GateRejected(f"{label} must pass invariant12_prime for formal positioning")
        if not isinstance(row.get("specialist_checkpoint"), str) or not row["specialist_checkpoint"]:
            raise GateRejected(f"{label} must record the secondary specialist checkpoint")
    else:
        if invariant not in (None, False, {"status": "NOT_APPLICABLE"}):
            raise GateRejected(f"{label} must not carry specialist invariant12_prime in DV")
        if row.get("specialist_checkpoint") not in (None, ""):
            raise GateRejected(f"{label} must not claim a specialist checkpoint in DV")
    if not isinstance(row.get("original_homie_checkpoint"), str) or not row["original_homie_checkpoint"]:
        raise GateRejected(f"{label} must record the immutable original HOMIE checkpoint")
    return row


def _rows(payload: Mapping[str, Any], label: str) -> list[Mapping[str, Any]]:
    rows = payload.get("terminal_rows", payload.get("rows"))
    if not isinstance(rows, list) or not rows:
        raise GateRejected(f"{label} must contain a non-empty rows list")
    return rows


def validate_formal_anchor(receipt: Path | Mapping[str, Any]) -> dict[str, Any]:
    payload = _read(receipt, "formal anchor receipt")
    _formal_identity(payload, ANCHOR_SCHEMA, "formal anchor")
    attempt = payload.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or not 0 <= attempt < MAX_ANCHOR_ATTEMPTS:
        raise GateRejected("formal anchor attempt must be 0, 1, or 2")
    sequence_rows = payload.get("sequence_rows")
    if not isinstance(sequence_rows, Mapping) or set(sequence_rows) != set(SEQUENCES):
        raise GateRejected("formal anchor must expose exactly S1..S4")
    checked = 0
    for sequence in SEQUENCES:
        rows = sequence_rows[sequence]
        if not isinstance(rows, list) or len(rows) != 16:
            raise GateRejected(f"formal anchor {sequence} must contain exactly 16 rows")
        for index, row in enumerate(rows):
            _formal_row(row, f"formal anchor {sequence}[{index}]", phase="anchor", specialist_active=True)
        checked += len(rows)
    if payload.get("g3_attempt_cap") != MAX_ANCHOR_ATTEMPTS:
        raise GateRejected("formal anchor must declare G3 attempt cap three")
    return {"status": payload["status"], "attempt": attempt, "rows": checked, "sequences": list(SEQUENCES)}


def validate_formal_door(receipt: Path | Mapping[str, Any]) -> dict[str, Any]:
    payload = _read(receipt, "formal door receipt")
    _formal_identity(payload, DOOR_SCHEMA, "formal door")
    bucket_rows = payload.get("bucket_rows")
    if not isinstance(bucket_rows, Mapping) or set(bucket_rows) != set(BUCKETS):
        raise GateRejected("formal door must expose exactly three closer buckets")
    checked = 0
    for bucket in BUCKETS:
        rows = bucket_rows[bucket]
        if not isinstance(rows, list) or len(rows) != 16:
            raise GateRejected(f"formal door bucket {bucket} must contain exactly 16 rows")
        for index, row in enumerate(rows):
            _formal_row(row, f"formal door {bucket}[{index}]", phase="door_positioning", specialist_active=True)
        checked += len(rows)
    return {"status": payload["status"], "rows": checked, "buckets": list(BUCKETS)}


def validate_g2(receipt: Path | Mapping[str, Any]) -> dict[str, Any]:
    payload = _read(receipt, "formal G2 receipt")
    _formal_identity(payload, G2_SCHEMA, "formal G2")
    if payload.get("anchor_pass") is not False or payload.get("lattice_scale") != "full_registered_command_lattice":
        raise GateRejected("formal G2 receipt must be the all-zero-anchor lattice branch")
    rows = _rows(payload, "formal G2")
    if len(rows) != 36:
        raise GateRejected("formal G2 must contain 36 representative states")
    for index, row in enumerate(rows):
        _formal_row(row, f"formal G2[{index}]", phase="anchor", specialist_active=True)
    return {"status": payload["status"], "rows": len(rows)}


def _validate_training_layout(payload: Mapping[str, Any], label: str, schema: str) -> dict[str, Any]:
    _formal_identity(payload, schema, label)
    if payload.get("num_envs") != 256 or payload.get("batches") != 250 or payload.get("save_frequency") != 50:
        raise GateRejected(f"{label} must be 256 envs x 250 batches with save50")
    if payload.get("load_optimizer") is not False:
        raise GateRejected(f"{label} must set load_optimizer=false")
    if payload.get("specialist_active") not in (False, None):
        raise GateRejected(f"{label} must disable specialist provenance")
    if payload.get("invariant12_prime") not in (None, False, {"status": "NOT_APPLICABLE"}):
        raise GateRejected(f"{label} must set invariant12_prime false/null")
    return {"status": payload["status"], "num_envs": 256, "batches": 250, "save_frequency": 50}


def validate_p3(receipt: Path | Mapping[str, Any]) -> dict[str, Any]:
    return _validate_training_layout(_read(receipt, "formal P3 receipt"), "formal P3", P3_SCHEMA)


def validate_p4(receipt: Path | Mapping[str, Any]) -> dict[str, Any]:
    return _validate_training_layout(_read(receipt, "formal P4 receipt"), "formal P4", P4_SCHEMA)


def validate_dual_eval(receipt: Path | Mapping[str, Any]) -> dict[str, Any]:
    payload = _read(receipt, "formal dual-source eval receipt")
    _formal_identity(payload, DUAL_EVAL_SCHEMA, "formal dual-source eval")
    sources = payload.get("sources")
    if not isinstance(sources, Mapping) or set(sources) != {"canonical", "natural"}:
        raise GateRejected("dual-source eval must expose canonical and natural populations")
    checked = 0
    for source in ("canonical", "natural"):
        rows = sources[source]
        if not isinstance(rows, list) or len(rows) != 16:
            raise GateRejected(f"dual-source {source} eval must contain exactly 16 rows")
        for index, row in enumerate(rows):
            _formal_row(row, f"dual-source {source}[{index}]", phase="DV", specialist_active=False)
        checked += len(rows)
    return {"status": payload["status"], "rows": checked, "specialist_active": False}


def validate_render_index(receipt: Path | Mapping[str, Any]) -> dict[str, Any]:
    payload = _read(receipt, "formal render index")
    _formal_identity(payload, RENDER_SCHEMA, "formal render")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise GateRejected("formal render index must contain entries")
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or entry.get("path") in (None, "") or entry.get("fixture") not in {"anchor", "door", "canonical", "natural"}:
            raise GateRejected(f"formal render entry {index} is malformed")
    return {"status": payload["status"], "entries": len(entries)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("anchor", "door", "g2", "p3", "p4", "dual_eval", "render"), required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    validators = {
        "anchor": validate_formal_anchor,
        "door": validate_formal_door,
        "g2": validate_g2,
        "p3": validate_p3,
        "p4": validate_p4,
        "dual_eval": validate_dual_eval,
        "render": validate_render_index,
    }
    result = validators[args.kind](args.receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
