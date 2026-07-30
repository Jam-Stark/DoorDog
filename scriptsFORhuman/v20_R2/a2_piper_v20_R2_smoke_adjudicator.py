"""Strict consumer for the single seven-cell smoke wave."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication


def adjudicate_smoke(attempt: Path, *, source_lock: Path | None = None) -> dict[str, object]:
    payload=read_artifact(attempt,schema="a2_piper_base_v20_R2_training_attempt_v1",producer_state="ATTEMPT_CONSUMED")
    groups=payload.get("groups")
    if not isinstance(groups,list) or {row.get("group") for row in groups} != set(GROUPS): raise R2Error("smoke wave must contain exactly G1-G7")
    hashes={row.get("config_sha256") for row in groups}
    if len(hashes)!=7: raise R2Error("smoke wave config hashes must be distinct")
    return {"schema":"a2_piper_base_v20_R2_endpoint_report_v1","adjudicator_state":"SMOKE_PASS","source_lock_sha256":artifact_hash(source_lock) if source_lock else payload["source_lock_sha256"],"record_set_sha256":artifact_hash(attempt),"group":"G1","record_count":7,"metrics":{"groups":7,"distinct_config_hashes":True},"invalid_reasons":[]}


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--attempt",type=Path,required=True); p.add_argument("--training-root",type=Path); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv); result=adjudicate_smoke(a.attempt); write_adjudication(a.output,result,"SMOKE_PASS"); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
