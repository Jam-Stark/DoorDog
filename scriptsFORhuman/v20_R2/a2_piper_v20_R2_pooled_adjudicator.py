"""Independent seven-group pooled48 consumer."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication


def _records_for_group(root: Path, group: str) -> list[tuple[int, Path, dict[str, Any]]]:
    rows: list[tuple[int, Path, dict[str, Any]]] = []
    aggregate = root / group / "record_set.json"
    if aggregate.is_file() and not aggregate.is_symlink():
        payload = read_artifact(aggregate, schema="a2_piper_base_v20_R2_record_set_v1", producer_state="RECORD_SET_COMPLETE")
        records = payload.get("records")
        if not isinstance(records, list):
            raise R2Error(f"pooled {group} record set records missing")
        # Aggregate record sets must still carry one unique seed per record.
        for seed in (0, 1, 2):
            seed_records = [r for r in records if r.get("provenance", {}).get("seed") == seed]
            if len(seed_records) != 16:
                raise R2Error(f"pooled {group} seed{seed} must contain exactly 16 records")
            rows.append((seed, aggregate, {"records": seed_records, "payload": payload}))
        return rows
    for seed in (0, 1, 2):
        path = root / group / f"seed{seed}" / "record_set.json"
        payload = read_artifact(path, schema="a2_piper_base_v20_R2_record_set_v1", producer_state="RECORD_SET_COMPLETE")
        records = payload.get("records")
        if not isinstance(records, list) or len(records) != 16:
            raise R2Error(f"pooled {group} seed{seed} must contain exactly 16 records")
        if any(record.get("provenance", {}).get("seed") != seed for record in records):
            raise R2Error(f"pooled {group} seed{seed} record provenance mismatch")
        rows.append((seed, path, {"records": records, "payload": payload}))
    return rows


def adjudicate_pooled(m22: Path, root: Path, *, source_lock: Path | None = None) -> dict[str, object]:
    m22_payload = read_artifact(m22, schema="a2_piper_base_v20_R2_m22_adjudication_v1", adjudicator_state="M22_70ROW_PASS")
    if source_lock is not None and m22_payload.get("source_lock_sha256") != artifact_hash(source_lock):
        raise R2Error("pooled M22 source-lock mismatch")
    m22_rows = m22_payload.get("rows")
    if not isinstance(m22_rows, list) or len(m22_rows) != 70:
        raise R2Error("pooled requires exact M22 rows")
    selected: dict[str, dict[str, Any]] = {}
    for group in GROUPS:
        candidates = [row for row in m22_rows if row.get("group") == group and row.get("state") == "STRICT_VALID"]
        if not candidates:
            raise R2Error(f"pooled has no selected strict-valid row for {group}")
        marked = [row for row in candidates if row.get("selected") is True]
        selected[group] = sorted(marked or candidates, key=lambda row: int(row["checkpoint_step"]))[-1]
    reports: dict[str, Any] = {}
    for group in GROUPS:
        seed_rows = _records_for_group(root, group)
        if len(seed_rows) != 3 or sum(len(item[2]["records"]) for item in seed_rows) != 48:
            raise R2Error(f"pooled {group} must contain exactly 48 unique records")
        selected_row = selected[group]
        identities: set[tuple[Any, Any]] = set()
        goals = crossings = overspeed = 0
        hashes: set[str] = set()
        for seed, path, info in seed_rows:
            hashes.add(artifact_hash(path))
            for record in info["records"]:
                prov = record.get("provenance", {})
                identity = (prov.get("seed"), prov.get("env_id"))
                if identity in identities:
                    raise R2Error(f"pooled {group} has duplicate seed/env scenario")
                identities.add(identity)
                if prov.get("checkpoint_sha256") != selected_row.get("checkpoint_sha256"):
                    raise R2Error(f"pooled {group} checkpoint substitution detected")
                if prov.get("resolved_config_sha256") != selected_row.get("config_sha256"):
                    raise R2Error(f"pooled {group} config substitution detected")
                goals += int(record.get("task", {}).get("goal") is True)
                crossings += int(record.get("task", {}).get("crossing_while_holding") is True)
                overspeed += int(record.get("safety", {}).get("upper_dof_overspeed") is True)
        if identities != {(seed, env_id) for seed in (0, 1, 2) for env_id in range(16)}:
            raise R2Error(f"pooled {group} scenario identity set is not exact seed0-2 x env0-15")
        gates = {"goal_min_46": goals >= 46, "crossing_min_46": crossings >= 46, "overspeed_zero": overspeed == 0}
        reports[group] = {"selected_checkpoint_step": selected_row["checkpoint_step"],
                          "selected_checkpoint_path": selected_row.get("checkpoint_path"),
                          "selected_config_path": selected_row.get("config_path"),
                          "selected_checkpoint_sha256": selected_row["checkpoint_sha256"],
                          "config_sha256": selected_row["config_sha256"], "record_count": 48,
                          "record_set_sha256": sorted(hashes), "goal_count": goals,
                          "crossing_while_holding_count": crossings, "overspeed_count": overspeed,
                          "gates": gates, "eligible": all(gates.values())}
    return {"schema": "a2_piper_base_v20_R2_endpoint_report_v1", "adjudicator_state": "POOLED7_PASS",
            "source_lock_sha256": m22_payload["source_lock_sha256"], "record_set_sha256": artifact_hash(m22),
            "group": "G1", "record_count": 7, "metrics": {"groups": reports},
            "invalid_reasons": [], "parents": {"m22": artifact_hash(m22)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m22", type=Path, required=True); parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = adjudicate_pooled(args.m22, args.root, source_lock=args.source_lock)
    write_adjudication(args.output, result, "POOLED7_PASS")
    print(canonical_json(result)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
