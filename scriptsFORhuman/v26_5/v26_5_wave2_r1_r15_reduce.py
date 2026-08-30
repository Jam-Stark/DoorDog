#!/usr/bin/env python3
"""Fail-closed R15 shared-actor-observation reducer."""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
from omegaconf import OmegaConf
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"scriptsFORhuman/v26_5/v26_5_wave2_r1_reduce.py";TOL=1e-6;N=64;STEPS=50
SOURCE=str(ROOT/"logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt")
TERMS=["push_door_handle","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"]
FORMAL_TERMS=["a2_stage3_handle_creation","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"]
DUAL={"base_input_key":"actor_obs","residual_input_key":"residual_actor_obs","base_observation_width":133,"residual_observation_width":133,"base_memory_mlp_frozen":True,"base_std_rms_frozen":True,"residual_action_slice":[5,12],"residual_final_layer_zero":True}
LOAD={"control":{"loaded":True,"state_key":"policy_state_dict","actor_state_kind":"legacy_identity_control","exact_keyset":True,"keyset_contract":"legacy_identity_control_exact","actor_rms_loaded":True,"strict":True,"missing_keys":[],"unexpected_keys":[]},"dual":{"loaded":True,"state_key":"policy_state_dict","actor_state_kind":"legacy","exact_keyset":True,"keyset_contract":"legacy_exact_without_residual","actor_rms_loaded":True,"strict":False,"missing_keys":["residual_module.0.weight","residual_module.0.bias","residual_module.2.weight","residual_module.2.bias"],"unexpected_keys":[]}}
def require(v,m):
 if not v:raise RuntimeError(m)
def load(p):
 require(p.is_file(),f"missing R15 artifact: {p}");return json.loads(p.read_text())
def delta(a,b):
 if isinstance(a,list):
  require(isinstance(b,list) and len(a)==len(b),"R15 trace shape mismatch");return max((delta(x,y) for x,y in zip(a,b,strict=True)),default=0.0)
 require(isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool),"R15 nonnumeric trace value");return abs(float(a)-float(b))
def matrix(v,rows,width,name):
 require(isinstance(v,list) and len(v)==rows and all(isinstance(r,list) and len(r)==width for r in v),f"R15 {name} shape")
def stage2_5_windows(path):
 rows=load(path/"stage2_5_step_trace.json");require(isinstance(rows,list),"R15 stage2_5 trace")
 windows={env:[] for env in range(N)}
 for index,row in enumerate(rows):
  require(isinstance(row,dict) and row.get("first_episode_active") is True and row.get("episode_index")==0,"R15 non-natural stage2_5 trace row")
  env=row.get("env_id");step=row.get("step_index");require(isinstance(env,int) and env in windows and isinstance(step,int) and not isinstance(step,bool) and step>=0,"R15 stage2_5 env/step")
  windows[env].append(step)
 for env,steps in windows.items():
  steps.sort();require(all(right==left+1 for left,right in zip(steps,steps[1:])),f"R15 noncontiguous stage2_5 topology env{env}: {path}")
 return windows
def stage2_5_topology(control,dual):
 control_windows=stage2_5_windows(control);dual_windows=stage2_5_windows(dual);mismatches=[]
 for env in range(N):
  left,right=control_windows[env],dual_windows[env]
  if left==right:continue
  first=next((i for i,(a,b) in enumerate(zip(left,right,strict=False)) if a!=b),min(len(left),len(right)))
  mismatches.append({"env_id":env,"control":{"count":len(left),"first_step":left[0] if left else None,"last_step":left[-1] if left else None},"dual":{"count":len(right),"first_step":right[0] if right else None,"last_step":right[-1] if right else None},"first_step_mismatch":{"index":first,"control_step":left[first] if first<len(left) else None,"dual_step":right[first] if first<len(right) else None}})
 return not mismatches,mismatches
def resolved(path,view,pilot):
 cfg=OmegaConf.to_container(OmegaConf.load(path/".hydra/runtime_config.yaml"),resolve=False);env=cfg["env"]["config"];ev=cfg["algo"]["config"]["eval"]
 require(cfg.get("seed") in (0,1) and env.get("a2_v26_side_permutation_seed")==cfg["seed"] and cfg.get("num_envs")==N and env.get("num_envs")=="${num_envs}" and env.get("a2_v26_5_geometry_target_enabled") is False,"R15 resolved base config")
 require(env.get("a2_v26_5_shared_residual_observation_enabled") is (view=="dual") and ev.get("a2_v26_5_post_construction_reseed") is True and ev.get("a2_v26_5_post_construction_reseed_pilot_trace") is pilot,"R15 resolved shared/reseed config")
 require(ev.get("a2_forced_gripper_close_enabled") is False and ev.get("a2_stage2_close_gate_forced_gripper_close_enabled") is False and ev.get("dump_to_log_metrics") is True and env.get("a2_v26_2_telemetry_enabled") is True and env.get("a2_v26_3_telemetry_enabled") is True,"R15 resolved diagnostic config")
 if pilot:require(cfg["seed"]==0 and env.get("a2_v26_door_open_lr")=="left" and env.get("max_episode_length_s")==.98 and env.get("enable_staged_reset") is False and ev.get("num_eval_episodes")==N and ev.get("eval_num_envs_episodes") is True,"R15 pilot resolved config")
 return cfg
def evidence(path,view,pilot):
 cfg=resolved(path,view,pilot);receipt=load(path/"a2_v26_5_post_construction_reseed_receipt.json")
 require(receipt.get("schema")=="a2_piper_base_v26_5_post_construction_reseed_receipt_v1" and receipt.get("status")=="POST_CONSTRUCTION_RESEED_PRE_ACTION_CAPTURED" and receipt.get("seed")==cfg["seed"] and receipt.get("policy_mode")==("identity_control" if view=="control" else "residual") and receipt.get("actor_load")==LOAD[view],"R15 reseed receipt")
 obs=receipt.get("obs",{}).get("actor_obs",{});require(obs.get("shape")==[N,133] and isinstance(obs.get("values"),list),"R15 reset O0 snapshot");matrix(obs["values"],N,133,"reset O0 snapshot")
 if view=="control":require(receipt.get("residual_actor_obs_absent") is True and "dual_input_contract" not in receipt and "residual_actor_obs" not in receipt.get("obs",{}),"R15 control residual absence")
 else:require(receipt.get("dual_input_contract")==DUAL and receipt.get("obs",{}).get("residual_actor_obs",{}).get("shape")==[N,133],"R15 dual residual receipt")
 runtime=load(path/"a2_v26_5_runtime_load_receipt.json");runtime_actor={k:v for k,v in LOAD[view].items() if k!="actor_state_kind"}
 require(runtime.get("schema")=="a2_piper_base_v26_5_runtime_load_receipt_v1" and runtime.get("status")=="CHECKPOINT_LOAD_COMPLETED" and runtime.get("output_root")==str(path.resolve()) and runtime.get("checkpoint_path")==SOURCE and runtime.get("checkpoint_load_mode")=="policy_only" and all(runtime.get("actor",{}).get(k)==v for k,v in runtime_actor.items()),"R15 runtime load receipt")
 if view=="control":require("dual_input_contract" not in runtime["actor"],"R15 runtime control input")
 else:require(runtime["actor"].get("dual_input_contract")==DUAL,"R15 runtime dual input")
 if not pilot:return receipt,None
 trace=load(path/"a2_v26_5_post_construction_reseed_trace.json")
 require(trace.get("schema")=="a2_piper_base_v26_5_post_construction_reseed_trace_v2" and trace.get("status")=="RUNTIME_VERIFIED" and trace.get("seed")==0 and trace.get("num_envs")==N and trace.get("control_steps")==STEPS and isinstance(trace.get("rows"),list) and len(trace["rows"])==STEPS,"R15 trace-v2 header")
 for step,row in enumerate(trace["rows"]):
  require(row.get("step_index")==step and row.get("active_mask")==[True]*N,"R15 exact first episode active trace")
  matrix(row.get("actor_obs"),N,133,"actor_obs trace");matrix(row.get("action_mean"),N,12,"action_mean trace");matrix(row.get("applied_high_level_action"),N,12,"applied action trace");matrix(row.get("actions_after_delay"),N,20,"physical action trace")
 return receipt,trace
def terminal(path):
 metrics=load(path/"metrics_eval.json");records=load(path/"a2_v14_per_env_records.json");meta=load(path/"a2_eval_diagnostic_metadata.json");terms=metrics.get("episode_terminal_diagnostics");lengths=metrics.get("episode_lengths");stages=metrics.get("episode_max_stage_reached")
 require(meta.get("diagnostic_trace_enabled") is True and meta.get("reward_terms")==TERMS and meta.get("forced_gripper_close_enabled") is False and meta.get("stage2_close_gate_forced_gripper_close_enabled") is False and meta.get("forced_gripper_close_applied_counts")==[0]*N and meta.get("stage2_close_gate_forced_gripper_close_applied_counts")==[0]*N,"R15 diagnostic metadata")
 require(metrics.get("completed_episodes")==N and isinstance(terms,list) and len(terms)==len(lengths)==len(stages)==len(records)==N and all(x==STEPS for x in lengths) and metrics.get("episode_terminal_reasons")==["episode_timeout"]*N and isinstance(metrics.get("episode_goal_reached"),list) and len(metrics["episode_goal_reached"])==N,"R15 exact64 terminal")
 require({x.get("env_id") for x in terms}==set(range(N)) and {x.get("env_id") for x in records}==set(range(N)) and all(x.get("episode_length_buf")==STEPS and x.get("terminal_reasons")=="episode_timeout" for x in terms) and all(x.get("seed")==0 and x.get("door_handle_side")=="left" for x in records),"R15 terminal/record env coverage")
 integrity=sum(int(x["v26_2"]["integrity_violations"])+int(x["v26_3"]["integrity_violations"]) for x in terms);require(integrity==0,"R15 pilot integrity")
 return {"goal":metrics["episode_goal_reached"],"stage":stages,"reason":metrics["episode_terminal_reasons"],"records":[(x["env_id"],x["goal_reached"],x["max_stage"],x["final_stage"]) for x in sorted(records,key=lambda x:x["env_id"])]}
def base_module():
 spec=importlib.util.spec_from_file_location("r15_base",BASE);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);return base
def formal_metrics(path,seed,side,checkpoint):
 base=base_module();x=base.runtime(path);cfg=x["config"];env=cfg["env"]["config"];ev=cfg["algo"]["config"]["eval"];receipt=x["receipt"];meta=x["metadata"]
 require(env.get("a2_v26_5_shared_residual_observation_enabled") is True and env.get("a2_v26_5_geometry_target_enabled") is False and ev.get("a2_v26_5_policy_only_residual") is False and ev.get("a2_v26_5_post_construction_reseed") is False and ev.get("a2_v26_5_post_construction_reseed_pilot_trace") is False,"R15 formal shared/full semantics")
 require(receipt.get("schema")=="a2_piper_base_v26_5_runtime_load_receipt_v1" and receipt.get("status")=="CHECKPOINT_LOAD_COMPLETED" and receipt.get("invocation_kind")=="eval" and receipt.get("output_root")==str(path.resolve()) and receipt.get("checkpoint_path")==str(checkpoint) and receipt.get("checkpoint_load_mode")=="full" and receipt.get("actor",{}).get("loaded") is True,"R15 formal runtime load provenance")
 require(meta.get("diagnostic_trace_enabled") is True and meta.get("reward_terms")==FORMAL_TERMS and meta.get("forced_gripper_close_enabled") is False and meta.get("stage2_close_gate_forced_gripper_close_enabled") is False,"R15 formal diagnostic metadata")
 return base.metrics(x,seed,side,checkpoint)
def formal(eval_root,train_root):
 rows={}
 for seed in (0,1):
  for step in (125,250):
   label=f"R15_S{seed}_STEP{step:04d}";checkpoint=train_root/"train"/f"R15_S{seed}"/f"model_step_{step:06d}.pt";rows[label]={side:formal_metrics(eval_root/label/side,seed,side,checkpoint) for side in ("left","right")}
 endpoint=[rows[f"R15_S{seed}_STEP0250"][side] for seed in (0,1) for side in ("left","right")]
 admitted=all(x["Stage3_admission_count"]>=16 and x["K5_episode_count"]>=16 and x["contact_stability_steps"]["rate"] is not None and x["contact_stability_steps"]["rate"]>=.9 and x["integrity_violations"]==0 for x in endpoint)
 return {"fixed_steps":rows,"step250_route":"KILL_RESIDUAL_ACQUISITION_REGRESSION" if not admitted else "PROMOTE_STAGE5_RELAY" if all(x["stage_episode_count"]["stage4"]>0 for x in endpoint) else "PROMOTE_SUSTAINED_RELAY" if all(x["sustained_handle_ge_0_1_current_K5_ge_5"]["episode_count"]>=2 for x in endpoint) else "GRAY_EXTEND_ONCE"}
def pair(control,dual,pilot):
 cr,ct=evidence(control,"control",pilot);dr,dt=evidence(dual,"dual",pilot);snapshot=delta(cr["obs"]["actor_obs"]["values"],dr["obs"]["actor_obs"]["values"])
 if snapshot>TOL:return {"pass":False,"typed_outcome":"KILL_R15_POST_CONSTRUCTION_RESEED_NOT_ALIGNED","reset_snapshot_max_abs":snapshot}
 if not pilot:
  base=base_module();raw_control=base.runtime(control);base_pair=base.k1_pair(raw_control,base.runtime(dual),int(cr["seed"]),str(raw_control["config"]["env"]["config"]["a2_v26_door_open_lr"]));return {"pass":base_pair["pass"],"typed_outcome":"R15_RESEED_K1_PAIR","reset_snapshot_max_abs":snapshot,"full_topology_raw_action_discrete_integrity":base_pair}
 first=max(delta(ct["rows"][0][k],dt["rows"][0][k]) for k in ("actor_obs","action_mean","applied_high_level_action","actions_after_delay"))
 if first>TOL:return {"pass":False,"typed_outcome":"KILL_R15_BASE_OR_PHYSICAL_PATH_NOT_IDENTICAL","reset_snapshot_max_abs":snapshot,"first_base_or_physical_max_abs":first}
 continuous=max(delta(a[k],b[k]) for a,b in zip(ct["rows"],dt["rows"],strict=True) for k in ("actor_obs","action_mean","applied_high_level_action","actions_after_delay"));left,right=terminal(control),terminal(dual);discrete=left==right;topology,mismatches=stage2_5_topology(control,dual)
 if continuous>TOL or not discrete or not topology:return {"pass":False,"typed_outcome":"KILL_R15_CROSS_PROCESS_TRAJECTORY","reset_snapshot_max_abs":snapshot,"fifty_tick_continuous_max_abs":continuous,"terminal_discrete_identity":discrete,"stage2_5_trace_topology_identical":topology,"stage2_5_trace_topology_mismatches":mismatches,"integrity_violations":0}
 return {"pass":True,"typed_outcome":"R15_SHARED_O0_PILOT_ADMITTED","reset_snapshot_max_abs":snapshot,"first_base_or_physical_max_abs":first,"fifty_tick_continuous_max_abs":continuous,"terminal_discrete_identity":True,"stage2_5_trace_topology_identical":True,"stage2_5_trace_topology_mismatches":[],"integrity_violations":0}
def main():
 p=argparse.ArgumentParser();p.add_argument("--control",type=Path);p.add_argument("--dual",type=Path);p.add_argument("--root",type=Path);p.add_argument("--train-root",type=Path);p.add_argument("--output",type=Path,required=True);p.add_argument("--mode",choices=("pilot","k1","formal"),required=True);a=p.parse_args();require(not a.output.exists(),"R15 reducer overwrite")
 if a.mode=="pilot":require(a.control is not None and a.dual is not None,"R15 pilot paths");out=pair(a.control,a.dual,True)
 elif a.mode=="k1":
  require(a.root is not None,"R15 K1 root");pairs={f"seed{s}_{side}":pair(a.root/"control"/f"K1_S{s}"/side,a.root/"dual"/f"K1_S{s}"/side,False) for s in (0,1) for side in ("left","right")};out={"pairs":pairs,"typed_outcome":"K1_R15_IDENTITY_ADMITTED" if all(x["pass"] for x in pairs.values()) else "KILL_R15_IDENTITY_NOT_ADMITTED"}
 else:
  require(a.root is not None and a.train_root is not None,"R15 formal roots");out=formal(a.root,a.train_root)
 out.update({"schema":"a2_piper_base_v26_5_r15_shared_observation_reducer_v1","status":"EXPERIMENT_COMPLETE"});a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+"\n");print(a.output)
if __name__=="__main__":main()
