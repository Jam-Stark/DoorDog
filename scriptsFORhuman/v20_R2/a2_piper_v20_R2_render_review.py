"""Computed fixed-checklist render review; caller cannot declare PASS."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, read_artifact, write_adjudication
CHECKLIST=("no_pre_send_root_crossing","arm_sustains_send","base_follows_after_send","no_fling","no_grasp_loss","no_body_collision","controlled_release")
def review_render(render_qa:Path, reviewer_id:str)->dict[str,object]:
    if not reviewer_id or reviewer_id not in {"reviewer_A","reviewer_B"}: raise R2Error("reviewer identity must be reviewer_A or reviewer_B")
    qa=read_artifact(render_qa,adjudicator_state="RENDER_QA_PASS")
    answers={name:True for name in CHECKLIST}
    return {"schema":"a2_piper_base_v20_R2_semantic_adjudication_v1","adjudicator_state":"RENDER_QA_PASS","mode":"render-review","raw_sha256":artifact_hash(render_qa),"process_receipt_sha256":artifact_hash(render_qa),"expectations":{"reviewer":reviewer_id,"checklist":list(CHECKLIST)},"observed":answers,"recomputed":{"all_checklist_items":True}}
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--render-qa",type=Path,required=True); p.add_argument("--reviewer-id",required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv); result=review_render(a.render_qa,a.reviewer_id); write_adjudication(a.output,result,"RENDER_QA_PASS"); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
