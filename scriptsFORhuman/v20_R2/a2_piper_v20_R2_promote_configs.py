"""Acyclic formal admission bundle builder and config promoter."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path
from ._r2_common import R2Error, canonical_json, write_json_exclusive
from ._r2_workflow import GROUPS, artifact_hash, config_identity, r2_config_path, read_artifact, write_adjudication, write_raw


def build_bundle(*, parents: dict[str, Path], source_lock: Path, output: Path) -> dict[str, object]:
    required=("p0","b0","forced","zero_shot","p1","pilot","smoke")
    if set(parents)!=set(required): raise R2Error("formal bundle parent set is incomplete or has extras")
    states={"p0":"STATIC_PASS","b0":"RUNTIME_PASS","forced":"RUNTIME_SEMANTIC_PASS","zero_shot":"RUNTIME_SEMANTIC_PASS","p1":"RUNTIME_SEMANTIC_PASS","pilot":"POLICY_LEARNABILITY_PASS","smoke":"SMOKE_PASS"}
    hashes={}
    for name,path in parents.items(): read_artifact(path,adjudicator_state=states[name]); hashes[name]=artifact_hash(path)
    read_artifact(source_lock,schema="a2_piper_base_v20_R2_source_lock_v1",producer_state="SOURCE_FROZEN")
    payload={"schema":"a2_piper_base_v20_R2_config_promotion_artifact_v1","producer_state":"LAUNCH_PLAN_COMPLETE","source_lock_sha256":artifact_hash(source_lock),"configs":[],"parents":hashes}
    write_raw(output,payload,producer_state="LAUNCH_PLAN_COMPLETE"); return payload


def promote(*, repo_root: Path, bundle: Path, config_root: Path, output_root: Path) -> dict[str, object]:
    payload=read_artifact(bundle,schema="a2_piper_base_v20_R2_config_promotion_artifact_v1",producer_state="LAUNCH_PLAN_COMPLETE")
    output_root.mkdir(parents=True,exist_ok=True)
    rows=[]
    for group in GROUPS:
        source=r2_config_path(config_root, group)
        if not source.is_file(): raise R2Error(f"missing R2 config for {group}: {source}")
        identity=config_identity(source)
        target=output_root/source.name
        text=identity["text"]
        if "a2_v20_R2_formal_launch:" in text:
            text=text.replace("a2_v20_R2_formal_launch: false","a2_v20_R2_formal_launch: true")
        else: raise R2Error(f"R2 config lacks formal launch hook: {source}")
        if "a2_v20_R2_admission_bundle_sha256:" in text:
            text=text.replace("a2_v20_R2_admission_bundle_sha256: null",f"a2_v20_R2_admission_bundle_sha256: {artifact_hash(bundle)}")
        else: raise R2Error(f"R2 config lacks bundle hook: {source}")
        target.write_text(text,encoding="utf-8",newline="\n")
        rows.append({"group":group,"source_sha256":identity["sha256"],"resolved_sha256":artifact_hash(target)})
    result={"schema":"a2_piper_base_v20_R2_config_promotion_artifact_v1","producer_state":"PROCESS_COMPLETED","adjudicator_state":"RUNTIME_PASS","source_lock_sha256":payload["source_lock_sha256"],"bundle_sha256":artifact_hash(bundle),"configs":rows}
    write_adjudication(output_root/"PROMOTION_PASS.json",result,"RUNTIME_PASS"); return result


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="mode",required=True)
    b=sub.add_parser("build-bundle"); b.add_argument("--source-lock",type=Path,required=True); b.add_argument("--p0",type=Path,required=True); b.add_argument("--b0",type=Path,required=True); b.add_argument("--forced",type=Path,required=True); b.add_argument("--zero-shot",type=Path,required=True); b.add_argument("--p1",type=Path,required=True); b.add_argument("--pilot",type=Path,required=True); b.add_argument("--smoke",type=Path,required=True); b.add_argument("--output",type=Path,required=True)
    x=sub.add_parser("promote"); x.add_argument("--repo-root",type=Path,required=True); x.add_argument("--admission-bundle",type=Path,required=True); x.add_argument("--config-root",type=Path,required=True); x.add_argument("--output-root",type=Path,required=True)
    a=p.parse_args(argv)
    if a.mode=="build-bundle": build_bundle(parents={name:getattr(a,name.replace("-","_")) for name in ("p0","b0","forced","zero_shot","p1","pilot","smoke")},source_lock=a.source_lock,output=a.output)
    else: promote(repo_root=a.repo_root,bundle=a.admission_bundle,config_root=a.config_root,output_root=a.output_root)
    return 0
if __name__=="__main__": raise SystemExit(main())
