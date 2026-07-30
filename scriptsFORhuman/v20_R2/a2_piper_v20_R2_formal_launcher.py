"""Strict formal launch-plan producer; it does not claim runtime success."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, parse_gpus, r2_config_path, read_artifact, runtime_command, write_raw


def build_formal_launch_plan(*, promotion_pass: Path, physical_gpus: tuple[int, ...], repo_root: Path, config_root: Path) -> dict[str, object]:
    if len(physical_gpus)!=7 or set(physical_gpus)!=set(range(7)): raise R2Error("formal launch requires one-to-one physical GPUs 0-6")
    promotion=read_artifact(promotion_pass,adjudicator_state="RUNTIME_PASS")
    rows=[]
    for group,gpu in zip(GROUPS,physical_gpus):
        config=r2_config_path(config_root, group)
        argv,env,binding=runtime_command(module="gr00t.rl.train_agent_trl",repo_root=repo_root,gpu=gpu,render=False,extra=("--config",str(config),"--seed","0"))
        rows.append({"group":group,"physical_gpu":gpu,"argv":argv,"env":env,"config_sha256":artifact_hash(config),"device":binding})
    return {"schema":"a2_piper_base_v20_R2_training_attempt_v1","producer_state":"LAUNCH_PLAN_COMPLETE","attempt_id":"formal-wave-seed0","group":"G1","command":rows[0]["argv"],"env":rows[0]["env"],"source_lock_sha256":promotion["source_lock_sha256"],"config_sha256":rows[0]["config_sha256"],"checkpoint_sha256":None,"groups":rows,"promotion_pass_sha256":artifact_hash(promotion_pass)}


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--repo-root",type=Path,required=True); p.add_argument("--promotion-pass",type=Path,required=True); p.add_argument("--physical-gpus",required=True); p.add_argument("--launcher-root",type=Path,required=False); p.add_argument("--training-root",type=Path,required=False); p.add_argument("--config-root",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(argv)
    payload=build_formal_launch_plan(promotion_pass=a.promotion_pass,physical_gpus=tuple(parse_gpus(a.physical_gpus)),repo_root=a.repo_root,config_root=a.config_root); write_raw(a.output,payload,producer_state="LAUNCH_PLAN_COMPLETE"); print(canonical_json(payload)); return 0
if __name__=="__main__": raise SystemExit(main())
