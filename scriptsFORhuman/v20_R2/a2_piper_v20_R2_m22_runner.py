"""M22 runner command planner with exact seven-group ownership."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error
from ._r2_workflow import GROUPS, artifact_hash, parse_gpus, read_artifact, runtime_command, write_raw


def build_m22_commands(*, manifest: Path, repo_root: Path, physical_gpus: tuple[int,...], output_root: Path) -> list[dict[str,object]]:
    payload=read_artifact(manifest,schema="a2_piper_base_v20_R2_m22_manifest_v1",producer_state="RECORD_SET_COMPLETE")
    if len(payload.get("rows",[]))!=70 or len(physical_gpus)!=7: raise R2Error("M22 requires exact 70 rows and seven GPUs")
    rows=[]
    for group,gpu in zip(GROUPS,physical_gpus):
        argv,env,_=runtime_command(module="gr00t.rl.eval_agent_trl",repo_root=repo_root,gpu=gpu,render=False,extra=("--r2-m22-group",group))
        rows.append({"group":group,"physical_gpu":gpu,"argv":argv,"env":env,"manifest_sha256":artifact_hash(manifest)})
    return rows

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--manifest",type=Path,required=True); p.add_argument("--physical-gpus",required=True); p.add_argument("--output-root",type=Path,required=True); p.add_argument("--repo-root",type=Path,required=True); a=p.parse_args(argv); rows=build_m22_commands(manifest=a.manifest,repo_root=a.repo_root,physical_gpus=tuple(parse_gpus(a.physical_gpus)),output_root=a.output_root); write_raw(a.output_root/"m22_commands.json",{"schema":"a2_piper_base_v20_R2_training_attempt_v1","producer_state":"COMMAND_PLANNED","attempt_id":"m22-wave","group":"G1","command":rows[0]["argv"],"env":rows[0]["env"],"source_lock_sha256":"0"*64,"config_sha256":"0"*64,"checkpoint_sha256":None,"groups":rows},producer_state="COMMAND_PLANNED"); return 0
if __name__=="__main__": raise SystemExit(main())
