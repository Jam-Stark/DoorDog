#!/usr/bin/env python3
"""Fail-closed cross-process r14 post-construction-reseed reducer."""
from __future__ import annotations
import argparse,importlib.util,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"scriptsFORhuman/v26_5/v26_5_wave2_r1_reduce.py";TOL=1e-6;N=64;STEPS=50
def require(v,m):
 if not v:raise RuntimeError(m)
def load(p):require(p.is_file(),f"missing r14 artifact: {p}");return json.loads(p.read_text())
def d(a,b):
 if isinstance(a,list):require(isinstance(b,list) and len(a)==len(b),"r14 shape mismatch");return max((d(x,y) for x,y in zip(a,b,strict=True)),default=0.)
 require(isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool),"r14 nonnumeric trace value");return abs(float(a)-float(b))
DUAL={"base_input_key":"actor_obs","residual_input_key":"residual_actor_obs","base_observation_width":133,"residual_observation_width":133,"base_memory_mlp_frozen":True,"base_std_rms_frozen":True,"residual_action_slice":[5,12],"residual_final_layer_zero":True}
LOAD={"control":{"loaded":True,"state_key":"policy_state_dict","actor_state_kind":"legacy_identity_control","exact_keyset":True,"keyset_contract":"legacy_identity_control_exact","actor_rms_loaded":True,"strict":True,"missing_keys":[],"unexpected_keys":[]},"dual":{"loaded":True,"state_key":"policy_state_dict","actor_state_kind":"legacy","exact_keyset":True,"keyset_contract":"legacy_exact_without_residual","actor_rms_loaded":True,"strict":False,"missing_keys":["residual_module.0.weight","residual_module.0.bias","residual_module.2.weight","residual_module.2.bias"],"unexpected_keys":[]}}
def evidence(path,view,pilot):
 receipt=load(path/"a2_v26_5_post_construction_reseed_receipt.json");trace=load(path/"a2_v26_5_post_construction_reseed_trace.json") if pilot else None
 require(receipt.get("schema")=="a2_piper_base_v26_5_post_construction_reseed_receipt_v1" and receipt.get("status")=="POST_CONSTRUCTION_RESEED_PRE_ACTION_CAPTURED" and receipt.get("policy_mode")==("identity_control" if view=="control" else "residual"),"r14 reseed receipt")
 require(receipt.get("actor_load")==LOAD[view],"r14 exact actor_load receipt")
 if view=="control":require(receipt.get("residual_actor_obs_absent") is True and "dual_input_contract" not in receipt and "residual_actor_obs" not in receipt.get("obs",{}),"r14 control residual absence")
 else:require(receipt.get("dual_input_contract")==DUAL and receipt.get("obs",{}).get("residual_actor_obs",{}).get("shape")==[N,133],"r14 dual residual receipt")
 obs=receipt.get("obs",{}).get("actor_obs",{});require(obs.get("shape")==[N,133] and isinstance(obs.get("values"),list) and len(obs["values"])==N,"r14 reset O0 snapshot")
 if not pilot:return receipt,None
 require(trace.get("schema")=="a2_piper_base_v26_5_post_construction_reseed_trace_v1" and trace.get("status")=="RUNTIME_VERIFIED" and trace.get("num_envs")==N and trace.get("control_steps")==STEPS and isinstance(trace.get("rows"),list) and len(trace["rows"])==STEPS,"r14 trace header")
 for step,row in enumerate(trace["rows"]):require(row.get("step_index")==step and row.get("active_mask")==[True]*N and all(isinstance(row.get(k),list) and len(row[k])==N for k in ("actor_obs","action_mean","applied_high_level_action")),"r14 exact first episode trace")
 return receipt,trace
def pair(c,dv,pilot):
 cr,ct=evidence(c,"control",pilot);dr,dt=evidence(dv,"dual",pilot);snap=d(cr["obs"]["actor_obs"]["values"],dr["obs"]["actor_obs"]["values"])
 if snap>TOL:return {"pass":False,"typed_outcome":"KILL_R14_POST_CONSTRUCTION_RESEED_NOT_ALIGNED","reset_snapshot_max_abs":snap}
 if not pilot:
  base_spec=importlib.util.spec_from_file_location("r14_base",BASE);base=importlib.util.module_from_spec(base_spec);base_spec.loader.exec_module(base);base_pair=base.k1_pair(base.runtime(c),base.runtime(dv),int(cr["seed"]),str(base.runtime(c)["config"]["env"]["config"]["a2_v26_door_open_lr"]));return {"pass":base_pair["pass"],"typed_outcome":"R14_RESEED_K1_PAIR","reset_snapshot_max_abs":snap,"full_topology_raw_action_discrete_integrity":base_pair}
 first=max(d(ct["rows"][0]["action_mean"],dt["rows"][0]["action_mean"]),d(ct["rows"][0]["applied_high_level_action"],dt["rows"][0]["applied_high_level_action"]))
 if first>TOL:return {"pass":False,"typed_outcome":"KILL_R14_BASE_PATH_NOT_IDENTICAL","reset_snapshot_max_abs":snap,"first_mean_or_action_max_abs":first}
 later=max(d(a["actor_obs"],b["actor_obs"]) for a,b in zip(ct["rows"],dt["rows"],strict=True));action=max(max(d(a["action_mean"],b["action_mean"]),d(a["applied_high_level_action"],b["applied_high_level_action"])) for a,b in zip(ct["rows"],dt["rows"],strict=True))
 base_spec=importlib.util.spec_from_file_location("r14_base",BASE);base=importlib.util.module_from_spec(base_spec);base_spec.loader.exec_module(base);base_pair=base.k1_pair(base.runtime(c),base.runtime(dv),int(cr["seed"]),str(base.runtime(c)["config"]["env"]["config"]["a2_v26_door_open_lr"]))
 if max(later,action)>TOL or base_pair["pass"] is not True:return {"pass":False,"typed_outcome":"KILL_R14_CROSS_PROCESS_TRAJECTORY","reset_snapshot_max_abs":snap,"fifty_tick_obs_or_action_max_abs":max(later,action),"full_topology_raw_action_discrete_integrity":base_pair}
 return {"pass":True,"typed_outcome":"R14_RESEED_PILOT_ADMITTED","reset_snapshot_max_abs":snap,"first_mean_or_action_max_abs":first,"fifty_tick_obs_or_action_max_abs":max(later,action),"full_topology_raw_action_discrete_integrity":base_pair}
def main():
 p=argparse.ArgumentParser();p.add_argument("--control",type=Path);p.add_argument("--dual",type=Path);p.add_argument("--root",type=Path);p.add_argument("--output",type=Path,required=True);p.add_argument("--mode",choices=("pilot","k1"),required=True);a=p.parse_args();require(not a.output.exists(),"r14 reducer overwrite")
 if a.mode=="pilot":
  require(a.control is not None and a.dual is not None,"r14 pilot paths");out=pair(a.control,a.dual,True);out["typed_outcome"]="R14_RESEED_PILOT_ADMITTED" if out["pass"] else out["typed_outcome"]
 else:
  require(a.root is not None,"r14 K1 root");pairs={f"seed{s}_{side}":pair(a.root/"control"/f"K1_S{s}"/side,a.root/"dual"/f"K1_S{s}"/side,False) for s in (0,1) for side in ("left","right")};out={"pairs":pairs,"typed_outcome":"K1_R14_IDENTITY_ADMITTED" if all(x["pass"] for x in pairs.values()) else "KILL_R14_IDENTITY_NOT_ADMITTED"}
 out.update({"schema":"a2_piper_base_v26_5_r14_reseed_reducer_v1","status":"EXPERIMENT_COMPLETE"});a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+"\n");print(a.output)
if __name__=="__main__":main()
