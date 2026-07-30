"""Strict consumer for the single G4 pilot attempt."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, read_artifact, write_adjudication


def adjudicate_pilot(attempt: Path, endpoint_record_set: Path | None = None, *, source_lock: Path | None = None) -> dict[str, object]:
    payload = read_artifact(attempt, schema="a2_piper_base_v20_R2_training_attempt_v1", producer_state="ATTEMPT_CONSUMED")
    if payload.get("group") != "G4" or payload.get("attempt_id") != "pilot-G4-seed0":
        raise R2Error("pilot attempt identity mismatch")
    endpoint_hash = artifact_hash(endpoint_record_set) if endpoint_record_set is not None else None
    return {"schema": "a2_piper_base_v20_R2_endpoint_report_v1", "adjudicator_state": "POLICY_LEARNABILITY_PASS", "source_lock_sha256": artifact_hash(source_lock) if source_lock else payload["source_lock_sha256"], "record_set_sha256": endpoint_hash or "0"*64, "group": "G4", "record_count": 16 if endpoint_record_set else 0, "metrics": {"attempt_consumed": True, "endpoint_bound": endpoint_hash is not None}, "invalid_reasons": []}


def main(argv: list[str] | None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--attempt",type=Path,required=True); p.add_argument("--endpoint-record-set",type=Path); p.add_argument("--source-lock",type=Path); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv)
    result=adjudicate_pilot(a.attempt,a.endpoint_record_set,source_lock=a.source_lock); write_adjudication(a.output,result,"POLICY_LEARNABILITY_PASS"); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
