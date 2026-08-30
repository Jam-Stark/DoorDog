#!/usr/bin/env python3
"""Static R15 shared-observation preregistration verifier."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];RUN="v26_5_wave2_r1_policy_residual_20260831_r15"
def require(v,m):
 if not v:raise RuntimeError(m)
def groups(cfg):
 obs=cfg["obs"]["obs_dict"];return list(obs["actor_obs"]),list(obs["residual_actor_obs"])
def main():
 p=argparse.ArgumentParser();p.add_argument("--registry",type=Path,required=True);p.add_argument("--selector-root",type=Path,required=True);p.add_argument("--retry1",action="store_true");a=p.parse_args();r=json.loads(a.registry.read_text())
 if a.retry1:
  formal=r.get("formal_retry1",{});stage=ROOT/"logs_eval/base_v26"/RUN
  require(r.get("schema")=="a2_piper_base_v26_5_wave2_r15_execution_amendment_registry_v1" and r.get("run_id")==RUN and r.get("axis")=="R15_SHARED_ACTOR_OBSERVATION" and r.get("status")=="PREREGISTERED_RETRY1_NOT_RUN" and r.get("original_registry")==str(stage/"M/static/command_registry.json"),"R15 retry1 registry")
  require(formal.get("reason")=="full_checkpoint_active_diagnostic_term" and formal.get("original_output_root")==str(stage/"formal_eval") and formal.get("output_root")==str(stage/"formal_eval_retry1") and formal.get("runtime_log_root")==str(ROOT/"scriptsFORhuman/v26_5/runtime_logs"/RUN/"eval_retry1") and formal.get("reducer_output")==str(stage/"formal_eval_retry1/reducer.json") and formal.get("supervisor_name_template")==RUN+"_eval_retry1_{label_lower}_{step}" and formal.get("diagnostic_reward_terms")==["a2_stage3_handle_creation","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"] and formal.get("formal_train_reseed") is False and formal.get("formal_eval_reseed") is False and formal.get("formal_eval_pilot_trace") is False and formal.get("step250_route")=="R1 fixed thresholds","R15 retry1 formal contract")
 else:
  require(r.get("run_id")==RUN and r.get("axis")=="R15_SHARED_ACTOR_OBSERVATION" and r.get("status")=="PREREGISTERED_NOT_RUN","R15 registry")
  require(r.get("pilot",{}).get("max_episode_length_s")==.98 and r["pilot"].get("episode_length")==50 and r["pilot"].get("gpu")==4 and r["pilot"].get("stage2_5_topology")=="per-env contiguous step_index; empty/empty is identical" and r.get("reseed",{}).get("trace_schema")=="a2_piper_base_v26_5_post_construction_reseed_trace_v2" and r.get("formal",{}).get("reducer_output")=="formal_eval/reducer.json" and r["formal"].get("step250_route")=="R1 fixed thresholds","R15 pilot/formal contract")
 for name,schema in (("train","a2_piper_base_v26_5_wave2_r15_policy_residual_v1"),("eval","a2_piper_base_v26_5_wave2_r15_eval_policy_residual_v1")):
  cfg=yaml.safe_load((a.selector_root/f"R15_{name}_selector.yaml").read_text());env=cfg["env"]["config"];actor,residual=groups(cfg)
  require(cfg.get("v26_schema")==schema and env.get("a2_v26_5_geometry_target_enabled") is False and env.get("a2_v26_5_shared_residual_observation_enabled") is True,"R15 selector")
  require(set(residual)==(set(actor)-{"gripper_handle_transform"})|{"gripper_handle_transform_gauge"} and len(actor)==len(set(actor)) and len(residual)==len(set(residual)),"R15 shared observation groups")
 source=(ROOT/"gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py").read_text();env_source=(ROOT/"gr00t/rl/envs/door/door_open_a2_base.py").read_text()
 require("a2_piper_base_v26_5_post_construction_reseed_trace_v2" in source and "actions_after_delay" in source and "_A2_V26_5_POST_CONSTRUCTION_RESEED_PHYSICAL_ACTION_DIM = 20" in source,"R15 trace-v2 source contract")
 require("a2_v26_5_shared_residual_observation_enabled" in env_source and "shared residual observation common slice mismatch" in env_source,"R15 shared observation source contract")
 launcher=(ROOT/"scriptsFORhuman/v26_5/v26_5_wave2_r1_r15_eval_side.sh").read_text()
 require("shared=false" in launcher and "shared=true" in launcher and "a2_v26_5_shared_residual_observation_enabled=\"$shared\"" in launcher,"R15 control/dual shared launcher contract")
 if a.retry1:
  formal_launcher=(ROOT/"scriptsFORhuman/v26_5/v26_5_wave2_r1_r15_formal_eval_side.sh").read_text()
  require("[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]" in formal_launcher,"R15 retry1 formal diagnostic launcher contract")
 print(a.registry)
if __name__=="__main__":main()
