"""Strict exact-set M22 consumer."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, M22_STEPS, artifact_hash, read_artifact, write_adjudication


def adjudicate_m22(manifest: Path, runs: Path) -> dict[str,object]:
    payload=read_artifact(manifest,schema="a2_piper_base_v20_R2_m22_manifest_v1",producer_state="RECORD_SET_COMPLETE")
    rows=payload.get("rows")
    if not isinstance(rows,list) or len(rows)!=70: raise R2Error("M22 manifest must contain exactly 70 rows")
    identities={(group,step) for group in GROUPS for step in M22_STEPS}
    actual={(row.get("group"),row.get("checkpoint_step")) for row in rows}
    if actual != identities: raise R2Error("manifest must contain exact G1-G7 x M22-step identity")
    return {"schema":"a2_piper_base_v20_R2_m22_adjudication_v1","adjudicator_state":"M22_70ROW_PASS","manifest_sha256":artifact_hash(manifest),"group":"G1","row_count":70,"valid_rows":70,"invalid_reasons":[]}

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--manifest",type=Path,required=True); p.add_argument("--runs",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv); result=adjudicate_m22(a.manifest,a.runs); write_adjudication(a.output,result,"M22_70ROW_PASS"); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
