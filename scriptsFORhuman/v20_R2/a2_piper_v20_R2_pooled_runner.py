"""Pooled48 command planner for each selected M22 checkpoint."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error
from ._r2_workflow import GROUPS, artifact_hash, parse_gpus, read_artifact, runtime_command, write_raw

def build_pooled_commands(*, m22:Path, repo_root:Path, physical_gpus:tuple[int,...])->list[dict[str,object]]:
    payload=read_artifact(m22,adjudicator_state="M22_70ROW_PASS")
    if len(physical_gpus)!=7: raise R2Error("pooled runner requires seven physical GPUs")
    return [{"group":group,"physical_gpu":gpu,"argv":runtime_command(module="gr00t.rl.eval_agent_trl",repo_root=repo_root,gpu=gpu,render=False,extra=("--r2-pooled-group",group))[0],"env":runtime_command(module="gr00t.rl.eval_agent_trl",repo_root=repo_root,gpu=gpu,render=False,extra=("--r2-pooled-group",group))[1],"m22_sha256":artifact_hash(m22)} for group,gpu in zip(GROUPS,physical_gpus)]
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--m22",type=Path,required=True); p.add_argument("--physical-gpus",required=True); p.add_argument("--output-root",type=Path,required=True); p.add_argument("--repo-root",type=Path,required=True); a=p.parse_args(argv); rows=build_pooled_commands(m22=a.m22,repo_root=a.repo_root,physical_gpus=tuple(parse_gpus(a.physical_gpus))); write_raw(a.output_root/"pooled_commands.json",{"schema":"a2_piper_base_v20_R2_training_attempt_v1","producer_state":"COMMAND_PLANNED","attempt_id":"pooled-wave","group":"G1","command":rows[0]["argv"],"env":rows[0]["env"],"source_lock_sha256":"0"*64,"config_sha256":"0"*64,"checkpoint_sha256":None,"groups":rows},producer_state="COMMAND_PLANNED"); return 0
if __name__=="__main__": raise SystemExit(main())
