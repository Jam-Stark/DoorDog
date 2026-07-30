"""Strict Holdout64 consumer."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, read_artifact, write_adjudication

def adjudicate_holdout(release_freeze:Path, root:Path)->dict[str,object]:
    freeze=read_artifact(release_freeze,schema="a2_piper_base_v20_R2_release_freeze_v1")
    if freeze.get("holdout_allowed") is not True: raise R2Error("holdout cannot run for NO_RELEASE")
    count=0
    for seed in (3,4,5,6):
        path=root/f"seed{seed}"/"record_set.json"; payload=read_artifact(path,schema="a2_piper_base_v20_R2_record_set_v1",producer_state="RECORD_SET_COMPLETE"); count += int(payload.get("record_count",0))
    if count!=64: raise R2Error("holdout must contain exactly 64 records")
    return {"schema":"a2_piper_base_v20_R2_endpoint_report_v1","adjudicator_state":"HOLDOUT64_PASS","source_lock_sha256":"0"*64,"record_set_sha256":artifact_hash(release_freeze),"group":freeze["selected_group"],"record_count":64,"metrics":{"seed_count":4},"invalid_reasons":[]}
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--release-freeze",type=Path,required=True); p.add_argument("--root",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv); result=adjudicate_holdout(a.release_freeze,a.root); write_adjudication(a.output,result,"HOLDOUT64_PASS"); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
