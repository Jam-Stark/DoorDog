"""Final strict decision consumer with explicit no-release branch."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, read_artifact, write_adjudication

def final_decision(*, mode:str, source_lock:Path, m22:Path, pooled:Path, release_freeze:Path, holdout:Path|None=None, render:Path|None=None)->dict[str,object]:
    read_artifact(source_lock,schema="a2_piper_base_v20_R2_source_lock_v1",producer_state="SOURCE_FROZEN"); read_artifact(m22,adjudicator_state="M22_70ROW_PASS"); read_artifact(pooled,adjudicator_state="POOLED7_PASS"); freeze=read_artifact(release_freeze,schema="a2_piper_base_v20_R2_release_freeze_v1")
    if mode=="no-release":
        if freeze.get("selected_group") is not None or holdout is not None or render is not None: raise R2Error("no-release branch cannot consume release-only artifacts")
        decision="NO_RELEASE"; state="NO_RELEASE"; reason="no group passed mechanically frozen pooled gates"
    elif mode=="release":
        if freeze.get("selected_group") is None or holdout is None or render is None: raise R2Error("release branch requires selected candidate, holdout, and render")
        read_artifact(holdout,adjudicator_state="HOLDOUT64_PASS"); read_artifact(render,adjudicator_state="RENDER_QA_PASS"); decision="POLICY_PASS"; state="POLICY_PASS"; reason="all strict release parents pass"
    else: raise R2Error("mode must be release or no-release")
    return {"schema":"a2_piper_base_v20_R2_final_decision_v1","adjudicator_state":state,"source_lock_sha256":artifact_hash(source_lock),"release_freeze_sha256":artifact_hash(release_freeze),"decision":decision,"reason":reason,"selected_group":freeze.get("selected_group")}
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="mode",required=True)
    for mode in ("release","no-release"):
        x=sub.add_parser(mode); x.add_argument("--source-lock",type=Path,required=True); x.add_argument("--m22",type=Path,required=True); x.add_argument("--pooled",type=Path,required=True); x.add_argument("--release-freeze",type=Path,required=True); x.add_argument("--holdout",type=Path); x.add_argument("--render",type=Path); x.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv); result=final_decision(mode=a.mode,source_lock=a.source_lock,m22=a.m22,pooled=a.pooled,release_freeze=a.release_freeze,holdout=a.holdout,render=a.render); write_adjudication(a.output,result,result["adjudicator_state"]); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
