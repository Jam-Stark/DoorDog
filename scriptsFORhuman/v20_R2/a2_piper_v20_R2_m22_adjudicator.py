"""Independent exact-set M22 consumer."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, M22_STEPS, artifact_hash, canonical_digest, read_artifact, write_adjudication


def _manifest_rows(manifest: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = read_artifact(manifest, schema="a2_piper_base_v20_R2_m22_manifest_v1", producer_state="LAUNCH_PLAN_COMPLETE")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 70:
        raise R2Error("M22 manifest must contain exactly 70 rows")
    identity = {(row.get("group"), row.get("checkpoint_step")) for row in rows}
    expected = {(group, step) for group in GROUPS for step in M22_STEPS}
    if identity != expected:
        raise R2Error("manifest must contain exact G1-G7 x M22-step identity")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry_id = row.get("entry_id")
        if not isinstance(entry_id, str) or entry_id != canonical_digest({key: value for key, value in row.items() if key != "entry_id"}):
            raise R2Error("M22 entry_id does not match canonical row bytes")
        if entry_id in by_id:
            raise R2Error("duplicate M22 entry_id")
        by_id[entry_id] = dict(row)
    if len(by_id) != 70:
        raise R2Error("M22 manifest has duplicate entry identities")
    return payload, by_id


def _find_run(root: Path, entry_id: str) -> Path:
    candidates = [root / entry_id / "record_set.json", root / entry_id[:12] / "record_set.json"]
    candidates.extend(path for path in root.rglob("record_set.json") if entry_id in str(path.parent))
    unique = []
    for path in candidates:
        if path not in unique and path.is_file() and not path.is_symlink():
            unique.append(path)
    if len(unique) != 1:
        raise R2Error(f"M22 run evidence for entry {entry_id} is missing or duplicated")
    return unique[0]


def adjudicate_m22(manifest: Path, runs: Path, *, source_lock: Path | None = None) -> dict[str, object]:
    payload, rows = _manifest_rows(manifest)
    if source_lock is not None and payload.get("source_lock_sha256") != artifact_hash(source_lock):
        raise R2Error("M22 source-lock hash mismatch")
    result_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry_id, row in rows.items():
        path = _find_run(runs, entry_id)
        record_set = read_artifact(path, schema="a2_piper_base_v20_R2_record_set_v1", producer_state="RECORD_SET_COMPLETE")
        records = record_set.get("records")
        if not isinstance(records, list) or len(records) != 16:
            raise R2Error(f"M22 entry {entry_id} must contain canonical16 records")
        for record in records:
            provenance = record.get("provenance", {})
            if provenance.get("checkpoint_sha256") != row["checkpoint_sha256"]:
                raise R2Error(f"M22 checkpoint substitution detected for {entry_id}")
            if provenance.get("resolved_config_sha256") != row["resolved_config_sha256"]:
                raise R2Error(f"M22 config substitution detected for {entry_id}")
            if record.get("topology", {}).get("entry_id") not in (None, entry_id):
                raise R2Error(f"M22 record entry binding mismatch for {entry_id}")
        if entry_id in seen:
            raise R2Error("M22 run entry duplicated")
        seen.add(entry_id)
        result_rows.append({"entry_id": entry_id, "group": row["group"], "checkpoint_step": row["checkpoint_step"],
                            "checkpoint_path": row["checkpoint_path"], "checkpoint_sha256": row["checkpoint_sha256"],
                            "config_path": row["training_run_config_path"],
                            "config_sha256": row["resolved_config_sha256"],
                            "record_set_path": str(path), "record_set_sha256": artifact_hash(path),
                            "record_count": len(records), "state": "STRICT_VALID"})
    if seen != set(rows):
        raise R2Error("M22 runs do not exactly cover the manifest")
    return {"schema": "a2_piper_base_v20_R2_m22_adjudication_v1", "adjudicator_state": "M22_70ROW_PASS",
            "manifest_sha256": artifact_hash(manifest), "source_lock_sha256": payload["source_lock_sha256"],
            "group": "G1", "row_count": 70, "valid_rows": 70, "invalid_reasons": [], "rows": result_rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True); parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = adjudicate_m22(args.manifest, args.runs, source_lock=args.source_lock)
    write_adjudication(args.output, result, "M22_70ROW_PASS")
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
