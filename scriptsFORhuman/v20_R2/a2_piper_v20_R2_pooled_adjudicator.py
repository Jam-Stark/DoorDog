"""Strict seven-group pooled48 consumer."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication

def adjudicate_pooled(m22:Path, root:Path)->dict[str,object]:
    read_artifact(m22,adjudicator_state="M22_70ROW_PASS")
    reports={}
    for group in GROUPS:
        path=root/group/"record_set.json"; payload=read_artifact(path,schema="a2_piper_base_v20_R2_record_set_v1",producer_state="RECORD_SET_COMPLETE"); reports[group]={"sha256":artifact_hash(path),"record_count":payload.get("record_count")}
        if payload.get("record_count")!=48: raise R2Error(f"pooled {group} must contain 48 records")
    return {"schema":"a2_piper_base_v20_R2_endpoint_report_v1","adjudicator_state":"POOLED7_PASS","source_lock_sha256":"0"*64,"record_set_sha256":artifact_hash(m22),"group":"G1","record_count":7,"metrics":{"groups":7,"reports":reports},"invalid_reasons":[]}
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--m22",type=Path,required=True); p.add_argument("--root",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv); result=adjudicate_pooled(a.m22,a.root); write_adjudication(a.output,result,"POOLED7_PASS"); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
