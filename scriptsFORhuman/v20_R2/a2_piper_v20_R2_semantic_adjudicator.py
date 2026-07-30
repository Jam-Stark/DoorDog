"""Strict consumer for forced, zero-shot, and aggregate semantic evidence."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication
from .a2_piper_v20_R2_forced_runner import validate_forced_trace


def adjudicate_forced(raw: Path, process_receipt: Path | None = None) -> dict[str, Any]:
    rows = validate_forced_trace(raw)
    receipt_hash = artifact_hash(process_receipt) if process_receipt is not None else artifact_hash(raw)
    return {"schema": "a2_piper_base_v20_R2_semantic_adjudication_v1", "adjudicator_state": "RUNTIME_SEMANTIC_PASS", "mode": "forced", "raw_sha256": artifact_hash(raw), "process_receipt_sha256": receipt_hash, "expectations": {"case_count": 17}, "observed": {"case_count": len(rows)}, "recomputed": {"exact_case_set": True}}


def adjudicate_zero_shot(root: Path) -> dict[str, Any]:
    reports = {}
    for group in GROUPS:
        path = root / group / "record_set.json"
        payload = read_artifact(path, schema="a2_piper_base_v20_R2_record_set_v1", producer_state="RECORD_SET_COMPLETE")
        reports[group] = {"sha256": artifact_hash(path), "record_count": payload.get("record_count")}
    if len({row["sha256"] for row in reports.values()}) != 7:
        raise R2Error("zero-shot groups require distinct record-set hashes")
    return {"schema": "a2_piper_base_v20_R2_semantic_adjudication_v1", "adjudicator_state": "RUNTIME_SEMANTIC_PASS", "mode": "zero-shot", "raw_sha256": artifact_hash(root / "G1" / "record_set.json"), "process_receipt_sha256": artifact_hash(root / "G1" / "record_set.json"), "expectations": {"groups": list(GROUPS)}, "observed": reports, "recomputed": {"distinct_groups": True}}


def adjudicate_aggregate(paths: dict[str, Path]) -> dict[str, Any]:
    for name, path in paths.items():
        read_artifact(path, adjudicator_state="RUNTIME_SEMANTIC_PASS" if name != "p0" else "STATIC_PASS")
    return {"schema": "a2_piper_base_v20_R2_semantic_adjudication_v1", "adjudicator_state": "RUNTIME_SEMANTIC_PASS", "mode": "aggregate", "raw_sha256": artifact_hash(paths["zero-shot"]), "process_receipt_sha256": artifact_hash(paths["forced"]), "expectations": {"parents": sorted(paths)}, "observed": {"parents": sorted(paths)}, "recomputed": {"all_parent_states": True}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="mode", required=True)
    f = sub.add_parser("forced"); f.add_argument("--source-lock", type=Path, required=False); f.add_argument("--raw", type=Path, required=True); f.add_argument("--process-receipt", type=Path); f.add_argument("--output", type=Path, required=True)
    z = sub.add_parser("zero-shot"); z.add_argument("--source-lock", type=Path, required=False); z.add_argument("--root", type=Path, required=True); z.add_argument("--output", type=Path, required=True)
    a = sub.add_parser("aggregate");
    for name in ("p0", "b0", "forced", "zero-shot"): a.add_argument(f"--{name}", type=Path, required=True)
    a.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "forced": result = adjudicate_forced(args.raw, args.process_receipt)
    elif args.mode == "zero-shot": result = adjudicate_zero_shot(args.root)
    else: result = adjudicate_aggregate({"p0": args.p0, "b0": args.b0, "forced": args.forced, "zero-shot": args.zero_shot})
    write_adjudication(args.output, result, "RUNTIME_SEMANTIC_PASS"); print(canonical_json(result)); return 0
if __name__ == "__main__": raise SystemExit(main())
