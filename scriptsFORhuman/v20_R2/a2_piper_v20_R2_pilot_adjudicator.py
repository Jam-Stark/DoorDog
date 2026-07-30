"""Independent consumer for the single G4 pilot attempt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, read_artifact, validate_schema, write_adjudication

ATTEMPT_SCHEMA = "a2_piper_base_v20_R2_training_attempt_v1"
RECORD_SCHEMA = "a2_piper_base_v20_R2_record_set_v1"
RECEIPT_SCHEMA = "a2_piper_base_v20_R2_process_receipt_v1"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise R2Error(f"pilot training evidence missing: {path}")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise R2Error(f"pilot training JSONL line {index} is invalid") from exc
        if not isinstance(row, dict):
            raise R2Error(f"pilot training JSONL line {index} must be an object")
        for key in ("status", "pass", "passed", "verdict", "checks_passed", "adjudication"):
            if key in row:
                raise R2Error("training raw evidence may not self-attest a verdict")
        rows.append(row)
    if not rows:
        raise R2Error(f"pilot training evidence is empty: {path}")
    return rows


def _natural_completion(training_root: Path) -> dict[str, Any]:
    metrics = _jsonl(training_root / "r2_training_batch_metrics.jsonl")
    batches = sorted({row.get("batch_index") for row in metrics if isinstance(row.get("batch_index"), int)})
    if not batches or batches[-1] != 750:
        raise R2Error("pilot did not produce exact batch750 training evidence")
    if batches != list(range(min(batches), 751)):
        raise R2Error("pilot training batch evidence is not contiguous")
    checkpoints = {}
    for step in (250, 500, 750):
        path = training_root / f"model_step_{step:06d}.pt"
        if not path.is_file() or path.is_symlink():
            raise R2Error(f"pilot checkpoint missing: {path}")
        checkpoints[str(step)] = artifact_hash(path)
    receipt_path = training_root / "process_receipt.json"
    receipt = read_artifact(receipt_path, schema=RECEIPT_SCHEMA, producer_state="PROCESS_COMPLETED")
    if receipt.get("exit_code") != 0 or receipt.get("natural_exit") is not True:
        raise R2Error("pilot process receipt is not a natural exit-zero receipt")
    return {"batch_count": len(batches), "last_batch": batches[-1], "checkpoints": checkpoints,
            "process_receipt_sha256": artifact_hash(receipt_path),
            "metrics_sha256": artifact_hash(training_root / "r2_training_batch_metrics.jsonl")}


def _endpoint(endpoint_record_set: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = read_artifact(endpoint_record_set, schema=RECORD_SCHEMA, producer_state="RECORD_SET_COMPLETE")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != 16:
        raise R2Error("pilot endpoint must contain exactly 16 canonical records")
    provenance = [record.get("provenance") for record in records]
    if any(not isinstance(item, dict) or item.get("seed") != 0 for item in provenance):
        raise R2Error("pilot endpoint records must all be seed0")
    goals = sum(1 for record in records if record.get("task", {}).get("goal") is True)
    crossings = sum(1 for record in records if record.get("task", {}).get("crossing_while_holding") is True)
    overspeed = sum(1 for record in records if record.get("safety", {}).get("upper_dof_overspeed") is True)
    return payload, {"record_count": len(records), "goal_count": goals,
                     "crossing_while_holding_count": crossings, "overspeed_count": overspeed}


def adjudicate_pilot(attempt: Path, endpoint_record_set: Path | None = None, *, source_lock: Path | None = None,
                     training_root: Path | None = None) -> dict[str, object]:
    payload = read_artifact(attempt, schema=ATTEMPT_SCHEMA, producer_state="ATTEMPT_CONSUMED")
    if payload.get("group") != "G4" or payload.get("attempt_id") != "pilot-G4-seed0":
        raise R2Error("pilot attempt identity mismatch")
    if source_lock is not None and payload.get("source_lock_sha256") != artifact_hash(source_lock):
        raise R2Error("pilot attempt source-lock hash mismatch")
    if endpoint_record_set is None or training_root is None:
        raise R2Error("pilot adjudication requires both training evidence and endpoint record set")
    training = _natural_completion(training_root)
    endpoint, metrics = _endpoint(endpoint_record_set)
    source_hash = artifact_hash(source_lock) if source_lock else str(payload["source_lock_sha256"])
    if endpoint.get("records", [{}])[0].get("provenance", {}).get("source_lock_sha256") != source_hash:
        raise R2Error("pilot endpoint source-lock binding mismatch")
    # Frozen pilot gates are recomputed from records/logs.  A caller cannot
    # force a PASS by adding booleans to either producer artifact.
    gates = {
        "natural_750": training["last_batch"] == 750,
        "finite_checkpoints": len(training["checkpoints"]) == 3,
        "goal_min_8": metrics["goal_count"] >= 8,
        "crossing_min_8": metrics["crossing_while_holding_count"] >= 8,
        "overspeed_zero": metrics["overspeed_count"] == 0,
    }
    if not all(gates.values()):
        raise R2Error(f"pilot policy gates failed: {[key for key, value in gates.items() if not value]}")
    return {
        "schema": "a2_piper_base_v20_R2_endpoint_report_v1", "adjudicator_state": "POLICY_LEARNABILITY_PASS",
        "source_lock_sha256": source_hash, "record_set_sha256": artifact_hash(endpoint_record_set),
        "group": "G4", "record_count": metrics["record_count"],
        "metrics": {"training": training, "endpoint": metrics, "gates": gates}, "invalid_reasons": [],
        "parents": {"attempt": artifact_hash(attempt), "training_process_receipt": training["process_receipt_sha256"],
                     "endpoint": artifact_hash(endpoint_record_set)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True); parser.add_argument("--training-root", type=Path, required=True)
    parser.add_argument("--endpoint", "--endpoint-record-set", dest="endpoint_record_set", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = adjudicate_pilot(args.attempt, args.endpoint_record_set, source_lock=args.source_lock,
                              training_root=args.training_root)
    write_adjudication(args.output, result, "POLICY_LEARNABILITY_PASS")
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
