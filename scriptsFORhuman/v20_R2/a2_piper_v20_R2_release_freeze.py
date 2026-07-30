"""Deterministic simplest-passing-group release freeze consumer."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication


def freeze_release(*, pooled: Path, source_lock_sha256: str) -> dict[str, object]:
    payload=read_artifact(pooled,adjudicator_state="POOLED7_PASS")
    reports=payload.get("metrics",{}).get("reports",{})
    selected=next((group for group in GROUPS if reports.get(group,{}).get("eligible") is True),None)
    state="POLICY_PASS" if selected else "NO_RELEASE"
    return {"schema":"a2_piper_base_v20_R2_release_freeze_v1","adjudicator_state":state,"source_lock_sha256":source_lock_sha256,"selected_group":selected,"selection_basis":"simplest_passing_group" if selected else "no_group_passed","pooled_sha256":artifact_hash(pooled),"holdout_allowed":bool(selected)}

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--pooled",type=Path,required=True); p.add_argument("--source-lock-sha256",required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv); result=freeze_release(pooled=a.pooled,source_lock_sha256=a.source_lock_sha256); write_adjudication(a.output,result,result["adjudicator_state"]); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
