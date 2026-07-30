"""One-shot seven-cell 64x50 smoke-wave producer."""
from __future__ import annotations
import argparse
from pathlib import Path
from ._r2_common import R2Error
from ._r2_workflow import CONFIG_FILENAMES, GROUPS, artifact_hash, config_identity, parse_gpus, read_artifact, r2_config_path, runtime_command, write_raw


def build_smoke_commands(*, repo_root: Path, configs: dict[str, Path], physical_gpus: tuple[int, ...]) -> list[dict[str, object]]:
    if tuple(configs) != GROUPS or len(physical_gpus) != 7:
        raise R2Error("smoke requires exact G1-G7 config map and seven physical GPUs")
    result=[]
    for group,gpu in zip(GROUPS,physical_gpus):
        argv,env,_=runtime_command(module="gr00t.rl.train_agent_trl",repo_root=repo_root,gpu=gpu,render=False,extra=("--config",str(configs[group]),"--seed","0","--num-envs","64","--num-total-batches","50"))
        result.append({"group":group,"physical_gpu":gpu,"argv":argv,"env":env,"config_sha256":config_identity(configs[group])["sha256"]})
    if len({row["config_sha256"] for row in result}) != 7:
        raise R2Error("smoke configs must have distinct hashes")
    return result


def consume_smoke(*, repo_root: Path, source_lock: Path, pilot_pass: Path, configs: dict[str, Path], physical_gpus: tuple[int, ...], output_root: Path) -> dict[str, object]:
    read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN"); read_artifact(pilot_pass, adjudicator_state="POLICY_LEARNABILITY_PASS")
    rows=build_smoke_commands(repo_root=repo_root,configs=configs,physical_gpus=physical_gpus)
    payload={"schema":"a2_piper_base_v20_R2_training_attempt_v1","producer_state":"ATTEMPT_CONSUMED","attempt_id":"smoke-wave-seed0","group":"G1","command":rows[0]["argv"],"env":rows[0]["env"],"source_lock_sha256":artifact_hash(source_lock),"config_sha256":rows[0]["config_sha256"],"checkpoint_sha256":None,"groups":rows}
    write_raw(output_root/"SMOKE_WAVE_ATTEMPT_CONSUMED.json",payload,producer_state="ATTEMPT_CONSUMED"); return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--repo-root",type=Path,required=True); p.add_argument("--source-lock",type=Path,required=True); p.add_argument("--pilot-pass",type=Path,required=True); p.add_argument("--configs",type=Path,required=True); p.add_argument("--physical-gpus",required=True); p.add_argument("--output-root",type=Path,required=True); p.add_argument("--launcher-root",type=Path); p.add_argument("--training-root",type=Path); a=p.parse_args(argv)
    config_map={group:r2_config_path(a.configs, group) for group in GROUPS}; consume_smoke(repo_root=a.repo_root,source_lock=a.source_lock,pilot_pass=a.pilot_pass,configs=config_map,physical_gpus=tuple(parse_gpus(a.physical_gpus)),output_root=a.output_root); return 0
if __name__=="__main__": raise SystemExit(main())
