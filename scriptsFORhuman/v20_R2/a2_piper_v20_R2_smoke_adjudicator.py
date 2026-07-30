"""Independent consumer for the single seven-cell smoke wave."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication


def _metrics(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise R2Error(f"smoke training metrics are missing: {path}")
    rows = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise R2Error(f"smoke metrics line {index} is invalid") from exc
        if not isinstance(row, dict):
            raise R2Error("smoke metric row must be an object")
        if any(key in row for key in ("status", "pass", "passed", "verdict", "checks_passed", "adjudication")):
            raise R2Error("smoke raw metrics may not self-attest")
        rows.append(row)
    if not rows:
        raise R2Error("smoke training metrics are empty")
    return rows


def adjudicate_smoke(attempt: Path, *, source_lock: Path | None = None,
                     training_root: Path | None = None) -> dict[str, object]:
    payload = read_artifact(attempt, schema="a2_piper_base_v20_R2_training_attempt_v1", producer_state="ATTEMPT_CONSUMED")
    groups = payload.get("groups")
    if not isinstance(groups, list) or len(groups) != 7:
        raise R2Error("smoke wave must contain exactly seven command rows")
    actual = [row.get("group") for row in groups if isinstance(row, dict)]
    if actual != list(GROUPS):
        raise R2Error("smoke wave group order/set must be exact G1-G7")
    if len({row.get("config_sha256") for row in groups}) != 7:
        raise R2Error("smoke wave config hashes must be distinct")
    source_hash = artifact_hash(source_lock) if source_lock else payload.get("source_lock_sha256")
    if not isinstance(source_hash, str):
        raise R2Error("smoke source-lock hash is missing")
    reports: dict[str, Any] = {}
    for row in groups:
        group = str(row["group"])
        root = Path(str(row.get("output_root")))
        if not root.is_absolute() and training_root is not None:
            root = training_root / root
        receipt_path = root / "process_receipt.json"
        receipt = read_artifact(receipt_path, schema="a2_piper_base_v20_R2_process_receipt_v1", producer_state="PROCESS_COMPLETED")
        if receipt.get("exit_code") != 0 or receipt.get("natural_exit") is not True:
            raise R2Error(f"smoke {group} did not naturally exit zero")
        if receipt.get("active_source_lock_sha256") != source_hash:
            raise R2Error(f"smoke {group} receipt source-lock mismatch")
        metrics = _metrics(root / "r2_training_batch_metrics.jsonl")
        batch_values = sorted({item.get("batch_index") for item in metrics if isinstance(item.get("batch_index"), int)})
        if not batch_values or batch_values[-1] != 50 or batch_values != list(range(min(batch_values), 51)):
            raise R2Error(f"smoke {group} did not complete exact 50 batches")
        checkpoint = root / "model_step_000050.pt"
        if not checkpoint.is_file() or checkpoint.is_symlink():
            raise R2Error(f"smoke {group} checkpoint is missing")
        reports[group] = {"config_sha256": row["config_sha256"], "receipt_sha256": artifact_hash(receipt_path),
                          "metrics_sha256": artifact_hash(root / "r2_training_batch_metrics.jsonl"),
                          "checkpoint_sha256": artifact_hash(checkpoint), "batch_count": len(batch_values)}
    return {"schema": "a2_piper_base_v20_R2_endpoint_report_v1", "adjudicator_state": "SMOKE_PASS",
            "source_lock_sha256": source_hash, "record_set_sha256": artifact_hash(attempt),
            "group": "G1", "record_count": 7,
            "metrics": {"groups": reports, "distinct_config_hashes": True, "exact_batch_count": True},
            "invalid_reasons": [], "parents": {"attempt": artifact_hash(attempt)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True); parser.add_argument("--training-root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = adjudicate_smoke(args.attempt, source_lock=args.source_lock, training_root=args.training_root)
    write_adjudication(args.output, result, "SMOKE_PASS")
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
