"""Real matched render producer with logical cuda:0 visibility binding."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error
from ._r2_workflow import artifact_hash, r2_config_path, read_artifact, runtime_command, write_raw

def build_render_command(*, repo_root:Path, physical_gpu:int, config:Path, checkpoint:Path)->tuple[list[str],dict[str,str]]:
    argv,env,binding=runtime_command(module="gr00t.rl.eval_agent_trl",repo_root=repo_root,gpu=physical_gpu,render=True,extra=("--render","true","--config",str(config),"--checkpoint",str(checkpoint)))
    if binding["logical_device"]!="cuda:0": raise R2Error("render must use logical cuda:0")
    return argv,env

def plan_render(*, release_freeze:Path, m22:Path, pooled:Path, repo_root:Path, physical_gpu:int, output_root:Path)->dict[str,object]:
    freeze=read_artifact(release_freeze,schema="a2_piper_base_v20_R2_release_freeze_v1"); read_artifact(m22,adjudicator_state="M22_70ROW_PASS"); read_artifact(pooled,adjudicator_state="POOLED7_PASS")
    if freeze.get("selected_group") is None: raise R2Error("render release queue is unavailable for NO_RELEASE")
    config=r2_config_path(repo_root/"gr00t/rl/config/ablation/wbmanip", freeze["selected_group"])
    checkpoint=repo_root/"logs_rl"/"selected_checkpoint.pt"
    if not config.is_file() or not checkpoint.is_file(): raise R2Error("render requires frozen config and checkpoint")
    argv,env=build_render_command(repo_root=repo_root,physical_gpu=physical_gpu,config=config,checkpoint=checkpoint)
    payload={"schema":"a2_piper_base_v20_R2_render_execution_v1","producer_state":"COMMAND_PLANNED","run_uuid":"render-plan","group":freeze["selected_group"],"physical_gpu":physical_gpu,"logical_device":"cuda:0","config_sha256":artifact_hash(config),"checkpoint_sha256":artifact_hash(checkpoint),"videos":[],"process_receipt":{"argv":argv,"env":env,"release_freeze_sha256":artifact_hash(release_freeze)}}
    write_raw(output_root/"render_command.json",payload,producer_state="COMMAND_PLANNED"); return payload

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--release-freeze",type=Path,required=True); p.add_argument("--m22",type=Path,required=True); p.add_argument("--pooled",type=Path,required=True); p.add_argument("--physical-gpu",type=int,required=True); p.add_argument("--repo-root",type=Path,required=True); p.add_argument("--output-root",type=Path,required=True); a=p.parse_args(argv); plan_render(release_freeze=a.release_freeze,m22=a.m22,pooled=a.pooled,repo_root=a.repo_root,physical_gpu=a.physical_gpu,output_root=a.output_root); return 0
if __name__=="__main__": raise SystemExit(main())
