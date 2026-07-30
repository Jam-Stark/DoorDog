"""Holdout64 producer for one mechanically frozen release candidate."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error
from ._r2_workflow import artifact_hash, parse_gpus, read_artifact, runtime_command, write_raw

def build_holdout_commands(*, release_freeze:Path, repo_root:Path, physical_gpus:tuple[int,...])->list[dict[str,object]]:
    payload=read_artifact(release_freeze,schema="a2_piper_base_v20_R2_release_freeze_v1")
    if payload.get("holdout_allowed") is not True or payload.get("selected_group") is None: raise R2Error("holdout is forbidden for a NO_RELEASE freeze")
    if len(physical_gpus)!=4: raise R2Error("holdout uses exactly four physical GPUs")
    group=payload["selected_group"]
    return [{"seed":seed,"physical_gpu":gpu,"argv":runtime_command(module="gr00t.rl.eval_agent_trl",repo_root=repo_root,gpu=gpu,render=False,extra=("--r2-holdout-group",group,"--seed",str(seed)))[0],"env":runtime_command(module="gr00t.rl.eval_agent_trl",repo_root=repo_root,gpu=gpu,render=False,extra=("--r2-holdout-group",group,"--seed",str(seed)))[1],"release_freeze_sha256":artifact_hash(release_freeze)} for seed,gpu in zip((3,4,5,6),physical_gpus)]
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--release-freeze",type=Path,required=True); p.add_argument("--physical-gpus",required=True); p.add_argument("--output-root",type=Path,required=True); p.add_argument("--repo-root",type=Path,required=True); a=p.parse_args(argv); rows=build_holdout_commands(release_freeze=a.release_freeze,repo_root=a.repo_root,physical_gpus=tuple(parse_gpus(a.physical_gpus))); write_raw(a.output_root/"holdout_commands.json",{"schema":"a2_piper_base_v20_R2_training_attempt_v1","producer_state":"COMMAND_PLANNED","attempt_id":"holdout","group":"G1","command":rows[0]["argv"],"env":rows[0]["env"],"source_lock_sha256":"0"*64,"config_sha256":"0"*64,"checkpoint_sha256":None,"seeds":rows},producer_state="COMMAND_PLANNED"); return 0
if __name__=="__main__": raise SystemExit(main())
