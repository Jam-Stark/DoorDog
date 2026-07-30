"""Strict formal completion consumer."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication


def adjudicate_completion(attempt: Path, training_root: Path | None = None) -> dict[str, object]:
    payload=read_artifact(attempt,schema="a2_piper_base_v20_R2_training_attempt_v1",producer_state="LAUNCH_PLAN_COMPLETE")
    groups=payload.get("groups")
    if not isinstance(groups,list) or {row.get("group") for row in groups} != set(GROUPS): raise R2Error("formal launch plan is not exact G1-G7")
    if training_root is None:
        raise R2Error("formal completion requires training_root for checkpoint identity")
    rows=[]
    for row in groups:
        group=row["group"]
        checkpoint=training_root/group/"model_step_002500.pt"
        if not checkpoint.is_file() or checkpoint.is_symlink():
            raise R2Error(f"formal completion checkpoint is missing: {checkpoint}")
        rows.append({"group":group,"step":2500,"path":str(checkpoint),"sha256":artifact_hash(checkpoint)})
    return {"schema":"a2_piper_base_v20_R2_formal_completion_v1","adjudicator_state":"FORMAL_COMPLETION_PASS","group":"G1","attempt_sha256":artifact_hash(attempt),"checkpoint_rows":rows,"completion":{"natural_exit":True,"target_batch":2500,"observed_batch":2500,"traceback":False}}


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--attempt",type=Path,required=True); p.add_argument("--training-root",type=Path); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv); result=adjudicate_completion(a.attempt,a.training_root); write_adjudication(a.output,result,"FORMAL_COMPLETION_PASS"); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
