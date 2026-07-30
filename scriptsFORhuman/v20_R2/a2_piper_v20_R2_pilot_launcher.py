"""One-shot G4 policy learnability pilot producer."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from ._r2_common import R2Error, canonical_json
from ._r2_workflow import artifact_hash, config_identity, read_artifact, runtime_command, write_raw


def build_pilot_command(*, repo_root: Path, config: Path, physical_gpu: int) -> tuple[list[str], dict[str, str]]:
    argv, env, _ = runtime_command(module="gr00t.rl.train_agent_trl", repo_root=repo_root, gpu=physical_gpu, render=False, extra=("--config", str(config), "--seed", "0", "--num-envs", "256", "--num-total-batches", "750"))
    return argv, env


def consume_pilot_parents(source_lock: Path, semantic_pass: Path, config: Path) -> dict[str, str]:
    read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    read_artifact(semantic_pass, adjudicator_state="RUNTIME_SEMANTIC_PASS")
    identity = config_identity(config)
    return {"source_lock_sha256": artifact_hash(source_lock), "semantic_pass_sha256": artifact_hash(semantic_pass), "config_sha256": identity["sha256"]}


def consume_attempt(*, repo_root: Path, source_lock: Path, semantic_pass: Path, config: Path, physical_gpu: int, output_root: Path) -> dict[str, object]:
    parents = consume_pilot_parents(source_lock, semantic_pass, config)
    argv, env = build_pilot_command(repo_root=repo_root, config=config, physical_gpu=physical_gpu)
    payload = {"schema": "a2_piper_base_v20_R2_training_attempt_v1", "producer_state": "ATTEMPT_CONSUMED", "attempt_id": "pilot-G4-seed0", "group": "G4", "command": argv, "env": env, "source_lock_sha256": parents["source_lock_sha256"], "config_sha256": parents["config_sha256"], "checkpoint_sha256": None}
    write_raw(output_root / "PILOT_ATTEMPT_CONSUMED.json", payload, producer_state="ATTEMPT_CONSUMED")
    return payload


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--repo-root",type=Path,required=True); p.add_argument("--source-lock",type=Path,required=True); p.add_argument("--semantic-pass",type=Path,required=True); p.add_argument("--config",type=Path,required=True); p.add_argument("--physical-gpu",type=int,required=True); p.add_argument("--output-root",type=Path,required=True); p.add_argument("--launcher-root",type=Path)
    a=p.parse_args(argv); consume_attempt(repo_root=a.repo_root,source_lock=a.source_lock,semantic_pass=a.semantic_pass,config=a.config,physical_gpu=a.physical_gpu,output_root=a.output_root); return 0
if __name__=="__main__": raise SystemExit(main())
