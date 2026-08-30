#!/usr/bin/env python3
"""Static r14 preregistration verifier."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];RUN="v26_5_wave2_r1_policy_residual_20260831_r14"
def require(v,m):
 if not v:raise RuntimeError(m)
def main():
 p=argparse.ArgumentParser();p.add_argument("--registry",type=Path,required=True);p.add_argument("--selector-root",type=Path,required=True);a=p.parse_args();r=json.loads(a.registry.read_text())
 require(r.get("run_id")==RUN and r.get("axis")=="R14_POST_CONSTRUCTION_RESEED" and r.get("status")=="PREREGISTERED_NOT_RUN","r14 registry")
 require(r.get("pilot",{}).get("max_episode_length_s")==.98 and r["pilot"].get("episode_length")==50 and r["pilot"].get("gpu")==4,"r14 pilot contract")
 for name,schema in (("train","a2_piper_base_v26_5_wave2_r14_policy_residual_v1"),("eval","a2_piper_base_v26_5_wave2_r14_eval_policy_residual_v1")):
  cfg=yaml.safe_load((a.selector_root/f"R14_{name}_selector.yaml").read_text());require(cfg.get("v26_schema")==schema and cfg["env"]["config"].get("a2_v26_5_geometry_target_enabled") is False,"r14 selector")
 source=(ROOT/"gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py").read_text();require("a2_v26_5_post_construction_reseed" in source and "a2_v26_5_post_construction_reseed_trace" in source and "applied_high_level_action" in source,"r14 reseed source contract")
 print(a.registry)
if __name__=="__main__":main()
