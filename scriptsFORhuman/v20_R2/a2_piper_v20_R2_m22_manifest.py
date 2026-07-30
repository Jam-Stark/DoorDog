"""Producer for the exact 7x10 M22 checkpoint manifest."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, M22_STEPS, artifact_hash, read_artifact, write_raw


def build_manifest(*, formal_completion: Path, training_root: Path, source_lock_sha256: str) -> dict[str, object]:
    read_artifact(formal_completion,schema="a2_piper_base_v20_R2_formal_completion_v1",adjudicator_state="FORMAL_COMPLETION_PASS")
    rows=[]
    for group in GROUPS:
        for step in M22_STEPS:
            checkpoint=training_root/group/f"model_step_{step:06d}.pt"; record_set=training_root/group/f"step_{step:06d}"/"record_set.json"
            if not checkpoint.is_file() or checkpoint.is_symlink(): raise R2Error(f"missing immutable checkpoint: {checkpoint}")
            if not record_set.is_file() or record_set.is_symlink(): raise R2Error(f"missing M22 record set: {record_set}")
            rows.append({"group":group,"checkpoint_step":step,"checkpoint_path":str(checkpoint),"checkpoint_sha256":artifact_hash(checkpoint),"record_set_path":str(record_set),"record_set_sha256":artifact_hash(record_set)})
    return {"schema":"a2_piper_base_v20_R2_m22_manifest_v1","producer_state":"RECORD_SET_COMPLETE","source_lock_sha256":source_lock_sha256,"group":"G1","rows":rows}


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--formal-completion",type=Path,required=True); p.add_argument("--training-root",type=Path,required=True); p.add_argument("--source-lock-sha256",required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv); result=build_manifest(formal_completion=a.formal_completion,training_root=a.training_root,source_lock_sha256=a.source_lock_sha256); write_raw(a.output,result,producer_state="RECORD_SET_COMPLETE"); print(canonical_json(result)); return 0
if __name__=="__main__": raise SystemExit(main())
