#!/usr/bin/env python3
"""Reduce Wave2 R1 K1 identity and fixed-step natural evaluations."""
from __future__ import annotations
import argparse, json, math
from collections import defaultdict
from pathlib import Path
from typing import Any
from omegaconf import OmegaConf

EPISODES=64; SIDES=("left","right"); TOL=1e-6
SOURCE="/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
RECEIPT_SCHEMA="a2_piper_base_v26_5_runtime_load_receipt_v1"
TRACE_REWARD_TERMS=["push_door_handle","a2_stage3_unlatch_hold","push_door_hinge","a2_stage3_stage4_hold_and_drive"]
K1_LOAD_CONTRACT={
    "control":{"a2_v26_5_policy_only_identity_control":True,"a2_v26_5_policy_only_residual":False,"keyset_contract":"legacy_identity_control_exact","strict":True,"missing_keys":[]},
    "dual":{"a2_v26_5_policy_only_identity_control":False,"a2_v26_5_policy_only_residual":True,"keyset_contract":"legacy_exact_without_residual","strict":False,"missing_keys":["residual_module.0.weight","residual_module.0.bias","residual_module.2.weight","residual_module.2.bias"]},
}
def require(v:bool,m:str)->None:
    if not v: raise RuntimeError(m)
def load(path:Path)->Any:
    require(path.is_file(),f"missing artifact: {path}"); return json.loads(path.read_text(encoding="utf-8"))
def finite(v:Any,m:str)->float:
    require(isinstance(v,(int,float)) and not isinstance(v,bool),m); v=float(v); require(math.isfinite(v),m); return v
def canonical_trace_rows(rows:list[dict[str,Any]],path:Path,env:int)->list[dict[str,Any]]:
    """Order one env's observed trace window without inventing a global origin."""
    ordered=sorted(rows,key=lambda row: row.get("step_index",-1)); previous=None
    for row in ordered:
        step=row.get("step_index")
        require(isinstance(step,int) and not isinstance(step,bool) and step>=0 and (previous is None or step==previous+1),f"noncontiguous trace topology env{env}: {path}")
        previous=step
    return ordered
def paired_trace_topology(control:dict[int,list[dict[str,Any]]],dual:dict[int,list[dict[str,Any]]],env_ids:range)->tuple[bool,list[dict[str,Any]]]:
    mismatches=[]
    for env in env_ids:
        control_steps=[row["step_index"] for row in control[env]]; dual_steps=[row["step_index"] for row in dual[env]]
        if control_steps==dual_steps: continue
        first=next((index for index,(left,right) in enumerate(zip(control_steps,dual_steps)) if left!=right),min(len(control_steps),len(dual_steps)))
        mismatches.append({"env_id":env,"control":{"count":len(control_steps),"first_step":control_steps[0],"last_step":control_steps[-1]},"dual":{"count":len(dual_steps),"first_step":dual_steps[0],"last_step":dual_steps[-1]},"first_step_mismatch":{"index":first,"control_step":control_steps[first] if first<len(control_steps) else None,"dual_step":dual_steps[first] if first<len(dual_steps) else None}})
    return not mismatches,mismatches
def k1_pair_passes(topology:bool,discrete:bool,raw_o1:bool,max_action:float|None,integrity:int)->bool:
    return topology and discrete and raw_o1 and max_action is not None and max_action<=TOL and integrity==0
def runtime(path:Path)->dict[str,Any]:
    cfg=OmegaConf.to_container(OmegaConf.load(path/".hydra/runtime_config.yaml"),resolve=False)
    metrics=load(path/"metrics_eval.json"); records=load(path/"a2_v14_per_env_records.json"); trace=load(path/"stage2_5_step_trace.json"); metadata=load(path/"a2_eval_diagnostic_metadata.json"); receipt=load(path/"a2_v26_5_runtime_load_receipt.json")
    require(isinstance(cfg,dict) and isinstance(metrics,dict) and isinstance(records,list) and isinstance(trace,list) and isinstance(metadata,dict) and isinstance(receipt,dict),f"invalid evidence payload: {path}")
    terminal=metrics.get("episode_terminal_diagnostics"); stages=metrics.get("episode_max_stage_reached")
    require(isinstance(terminal,list) and isinstance(stages,list) and len(terminal)==len(stages)==len(records)==EPISODES,f"exact64 terminal evidence absent: {path}")
    terminal_by={}; stage_by={}; record_by={}
    for term,stage in zip(terminal,stages,strict=True):
        require(isinstance(term,dict) and isinstance(stage,int) and not isinstance(stage,bool),f"invalid terminal stage: {path}"); env=term.get("env_id"); require(isinstance(env,int) and 0<=env<EPISODES and env not in terminal_by,f"invalid terminal env: {path}"); terminal_by[env]=term; stage_by[env]=stage
    for row in records:
        require(isinstance(row,dict),f"invalid records row: {path}"); env=row.get("env_id"); require(isinstance(env,int) and 0<=env<EPISODES and env not in record_by and row.get("max_stage")==stage_by[env],f"invalid record env: {path}"); record_by[env]=row
    traces:dict[int,list[dict[str,Any]]]=defaultdict(list)
    for i,row in enumerate(trace):
        require(isinstance(row,dict) and row.get("first_episode_active") is True and row.get("episode_index")==0,f"non-natural trace row {i}: {path}"); env=row.get("env_id"); require(isinstance(env,int) and 0<=env<EPISODES,f"invalid trace env: {path}"); traces[env].append(row)
    require(set(terminal_by)==set(record_by)==set(traces)==set(range(EPISODES)),f"non-exact env coverage: {path}")
    for env,rows in traces.items(): traces[env]=canonical_trace_rows(rows,path,env)
    return {"path":str(path),"config":cfg,"metadata":metadata,"receipt":receipt,"terminal":terminal_by,"stage":stage_by,"records":record_by,"trace":traces}
def diff(a:Any,b:Any,label:str)->float:
    if isinstance(a,list): require(isinstance(b,list) and len(a)==len(b),f"shape mismatch {label}"); return max((diff(x,y,label) for x,y in zip(a,b,strict=True)),default=0.0)
    return abs(finite(a,label)-finite(b,label))
def validate_common(x:dict[str,Any],seed:int,side:str,*,mode:str)->None:
    cfg=x["config"]; env=cfg.get("env",{}).get("config",{}); ev=cfg.get("algo",{}).get("config",{}).get("eval",{})
    require(cfg.get("checkpoint")==SOURCE and cfg.get("checkpoint_load_mode")==mode and cfg.get("auto_load_latest") is False,f"checkpoint contract: {x['path']}"); require(cfg.get("seed")==seed and cfg.get("num_envs")==EPISODES and ev.get("num_eval_episodes")==EPISODES and ev.get("eval_num_envs_episodes") is True,f"population contract: {x['path']}"); require(env.get("a2_v26_door_open_lr")==side and env.get("a2_v26_side_permutation_seed")==seed and env.get("enable_staged_reset") is False,f"natural side contract: {x['path']}"); require(x["metadata"].get("diagnostic_trace_enabled") is True and x["metadata"].get("reward_terms")==TRACE_REWARD_TERMS and x["metadata"].get("forced_gripper_close_enabled") is False and x["metadata"].get("stage2_close_gate_forced_gripper_close_enabled") is False,f"diagnostic metadata contract: {x['path']}")
def validate_k1_runtime_load(x:dict[str,Any],view:str)->None:
    contract=K1_LOAD_CONTRACT[view]; cfg=x["config"]; ev=cfg.get("algo",{}).get("config",{}).get("eval",{}); receipt=x["receipt"]; path=Path(x["path"]).resolve()
    require(ev.get("a2_v23_p06_policy_only") is False and ev.get("a2_v26_5_runtime_load_receipt") is True and ev.get("a2_v26_5_policy_only_identity_control") is contract["a2_v26_5_policy_only_identity_control"] and ev.get("a2_v26_5_policy_only_residual") is contract["a2_v26_5_policy_only_residual"],f"{view} policy-only runtime flags: {path}")
    require(receipt.get("schema")==RECEIPT_SCHEMA and receipt.get("status")=="CHECKPOINT_LOAD_COMPLETED" and receipt.get("invocation_kind")=="eval" and receipt.get("output_root")==str(path) and receipt.get("checkpoint_path")==SOURCE and receipt.get("checkpoint_load_mode")=="policy_only",f"{view} runtime receipt provenance: {path}")
    actor=receipt.get("actor"); require(isinstance(actor,dict) and actor.get("loaded") is True and actor.get("state_key")=="policy_state_dict" and actor.get("exact_keyset") is True and actor.get("keyset_contract")==contract["keyset_contract"] and actor.get("actor_rms_loaded") is True and actor.get("strict") is contract["strict"],f"{view} runtime actor receipt: {path}")
    require(actor.get("missing_keys")==contract["missing_keys"] and actor.get("unexpected_keys")==[],f"{view} runtime actor key mismatch: {path}")
def k1_pair(control:dict[str,Any],dual:dict[str,Any],seed:int,side:str)->dict[str,Any]:
    validate_common(control,seed,side,mode="policy_only"); validate_common(dual,seed,side,mode="policy_only")
    validate_k1_runtime_load(control,"control"); validate_k1_runtime_load(dual,"dual")
    cenv=control["config"]["env"]["config"]; denv=dual["config"]["env"]["config"]
    require(cenv.get("a2_v26_5_geometry_target_enabled") is False and cenv.get("a2_v26_4_side_canonicalization_enabled") is False and cenv.get("a2_v26_5_stage3_delta_rebase_enabled") is False,f"K1 control factor mismatch: {control['path']}")
    require(denv.get("a2_v26_5_geometry_target_enabled") is True and denv.get("a2_v26_5_actor_gauge_enabled") is True and denv.get("a2_v26_4_side_canonicalization_enabled") is False and denv.get("a2_v26_5_stage3_delta_rebase_enabled") is False,f"K1 dual factor mismatch: {dual['path']}")
    topology,topology_mismatches=paired_trace_topology(control["trace"],dual["trace"],range(EPISODES)); max_action=0.0 if topology else None; discrete=True; raw_o1=True
    for env in range(EPISODES):
        discrete &= control["stage"][env]==dual["stage"][env] and control["records"][env].get("goal_reached")==dual["records"][env].get("goal_reached")
        cv2=control["terminal"][env].get("v26_2",{}); dv2=dual["terminal"][env].get("v26_2",{})
        discrete &= cv2.get("k5_steps")==dv2.get("k5_steps")
        cr,dr=control["trace"][env],dual["trace"][env]
        for left,right in zip(cr,dr):
            if topology: max_action=max(max_action,diff(left.get("policy_high_level_action_raw"),right.get("policy_high_level_action_raw"),"policy action"))
        for right in dr:
            raw_o1 &= isinstance(right.get("target_quat_source_handle"),list) and len(right["target_quat_source_handle"])==4 and isinstance(right.get("target_quat_source_pregrasp"),list) and len(right["target_quat_source_pregrasp"])==4
    integrity=sum(int(finite(v.get("v26_2",{}).get("integrity_violations"),"v26_2 integrity"))+int(finite(v.get("v26_3",{}).get("integrity_violations"),"v26_3 integrity")) for v in dual["terminal"].values())
    passed=k1_pair_passes(topology,discrete,raw_o1,max_action,integrity)
    return {"control":control["path"],"dual":dual["path"],"trace_topology_identical":topology,"trace_topology_mismatches":topology_mismatches,"continuous_trace_fields_verified":topology,"discrete_identity":discrete,"raw_O1_target_source_retained":raw_o1,"policy_mean_raw_action_max_abs":max_action,"std_evidence":"not emitted by diagnostic trace; see static actor/selector/loader contract and actual-load receipt","integrity_violations":integrity,"pass":passed}
def metrics(x:dict[str,Any],seed:int,side:str,checkpoint:Path)->dict[str,Any]:
    cfg=x["config"]; env=cfg.get("env",{}).get("config",{}); ev=cfg.get("algo",{}).get("config",{}).get("eval",{}); require(cfg.get("checkpoint")==str(checkpoint) and cfg.get("checkpoint_load_mode")=="full" and cfg.get("auto_load_latest") is False,f"R1 checkpoint contract: {x['path']}"); require(cfg.get("seed")==seed and cfg.get("num_envs")==EPISODES and ev.get("num_eval_episodes")==EPISODES and ev.get("eval_num_envs_episodes") is True,f"R1 population: {x['path']}"); require(env.get("a2_v26_door_open_lr")==side and env.get("a2_v26_5_geometry_target_enabled") is True and env.get("a2_v26_5_actor_gauge_enabled") is True and env.get("a2_v26_4_side_canonicalization_enabled") is False and env.get("a2_v26_5_stage3_delta_rebase_enabled") is False,f"R1 semantics: {x['path']}")
    stage3=k5=stable=contact=integrity=stage4=stage5=goal=sustained=0
    for env_id in range(EPISODES):
        term=x["terminal"][env_id]; v2=term.get("v26_2"); v3=term.get("v26_3"); require(isinstance(v2,dict) and isinstance(v3,dict),f"missing telemetry: {x['path']}"); stage=x["stage"][env_id]; stage3+=int(stage>=3); k5+=int(int(v2.get("k5_steps",-1))>=5); integrity+=int(finite(v2.get("integrity_violations"),"v2 integrity"))+int(finite(v3.get("integrity_violations"),"v3 integrity")); stage4+=int(stage>=4);stage5+=int(stage>=5);goal+=int(x["records"][env_id].get("goal_reached") is True);run=0;hit=False
        for row in x["trace"][env_id]:
            if row.get("stage_buf")==3: contact+=1; stable+=int(row.get("contact_stability") is True)
            qualifying=row.get("stage_buf")==3 and finite(row.get("door_handle_joint_pos"),"handle")>=.1 and row.get("v26_2",{}).get("strict_k5") is True; run=run+1 if qualifying else 0; hit|=run>=5
        sustained+=int(hit)
    return {"checkpoint":str(checkpoint),"K5_episode_count":k5,"Stage3_admission_count":stage3,"contact_stability_steps":{"numerator":stable,"denominator":contact,"rate":None if not contact else stable/contact},"sustained_handle_ge_0_1_current_K5_ge_5":{"predicate":"stage_buf==3 and handle>=0.1 and strict_k5 for five controls","episode_count":sustained},"stage_episode_count":{"stage4":stage4,"stage5":stage5,"goal":goal},"integrity_violations":integrity}
def main()->None:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="mode",required=True); k=sub.add_parser("k1"); k.add_argument("--eval-root",type=Path,required=True); k.add_argument("--output",type=Path,required=True); r=sub.add_parser("r1"); r.add_argument("--eval-root",type=Path,required=True);r.add_argument("--train-root",type=Path,required=True);r.add_argument("--output",type=Path,required=True);sub.add_parser("topology-proof");a=p.parse_args()
    if a.mode=="topology-proof":
        rows=[{"step_index":97},{"step_index":99},{"step_index":98}]
        require([row["step_index"] for row in canonical_trace_rows(rows,Path("synthetic"),0)]==[97,98,99],"synthetic nonzero-origin topology proof failed")
        base_cfg={"algo":{"config":{"eval":{"a2_v23_p06_policy_only":False,"a2_v26_5_runtime_load_receipt":True,"a2_v26_5_policy_only_identity_control":True,"a2_v26_5_policy_only_residual":False}}}}
        base_receipt={"schema":RECEIPT_SCHEMA,"status":"CHECKPOINT_LOAD_COMPLETED","invocation_kind":"eval","output_root":str(Path("synthetic/control").resolve()),"checkpoint_path":SOURCE,"checkpoint_load_mode":"policy_only","actor":{"loaded":True,"state_key":"policy_state_dict","exact_keyset":True,"keyset_contract":"legacy_identity_control_exact","actor_rms_loaded":True,"strict":True,"missing_keys":[],"unexpected_keys":[]}}
        validate_k1_runtime_load({"path":"synthetic/control","config":base_cfg,"receipt":base_receipt},"control")
        dual_cfg={"algo":{"config":{"eval":{"a2_v23_p06_policy_only":False,"a2_v26_5_runtime_load_receipt":True,"a2_v26_5_policy_only_identity_control":False,"a2_v26_5_policy_only_residual":True}}}}
        dual_receipt={**base_receipt,"output_root":str(Path("synthetic/dual").resolve()),"actor":{**base_receipt["actor"],"keyset_contract":"legacy_exact_without_residual","strict":False,"missing_keys":["residual_module.0.weight","residual_module.0.bias","residual_module.2.weight","residual_module.2.bias"]}}
        validate_k1_runtime_load({"path":"synthetic/dual","config":dual_cfg,"receipt":dual_receipt},"dual")
        for field,bad_value in (("a2_v26_5_policy_only_identity_control",False),("receipt.loaded",False)):
            cfg={"algo":{"config":{"eval":dict(base_cfg["algo"]["config"]["eval"])}}}; receipt={**base_receipt,"actor":dict(base_receipt["actor"])}
            if field.startswith("receipt"): receipt["actor"]["loaded"]=bad_value
            else: cfg["algo"]["config"]["eval"][field]=bad_value
            try: validate_k1_runtime_load({"path":"synthetic/control","config":cfg,"receipt":receipt},"control")
            except RuntimeError: continue
            raise RuntimeError(f"synthetic bad {field} receipt/flag was admitted")
        bad_dual_receipt={**dual_receipt,"actor":{**dual_receipt["actor"],"missing_keys":[]}}
        try: validate_k1_runtime_load({"path":"synthetic/dual","config":dual_cfg,"receipt":bad_dual_receipt},"dual")
        except RuntimeError: pass
        else: raise RuntimeError("synthetic dual bad missing_keys receipt was admitted")
        equal,unequal=paired_trace_topology({0:[{"step_index":97},{"step_index":98}]},{0:[{"step_index":97},{"step_index":99}]},range(1))
        require(equal is False and unequal==[{"env_id":0,"control":{"count":2,"first_step":97,"last_step":98},"dual":{"count":2,"first_step":97,"last_step":99},"first_step_mismatch":{"index":1,"control_step":98,"dual_step":99}}],"synthetic unequal window must produce typed topology mismatch")
        require(k1_pair_passes(False,True,True,None,0) is False,"synthetic unequal window must fail the K1 pair gate")
        print("R1_SYNTHETIC_PER_ENV_NONZERO_ORIGIN_TOPOLOGY_PASS")
        print("R1_SYNTHETIC_BAD_RECEIPT_FLAGS_AND_MISSING_REJECTED")
        print("R1_SYNTHETIC_UNEQUAL_WINDOW_TYPED_FAILURE_PASS")
        return
    require(not a.output.exists(),f"refusing to overwrite reducer: {a.output}")
    if a.mode=="k1":
        rows={f"seed{s}_{side}":k1_pair(runtime(a.eval_root/"K1"/"control"/f"K1_S{s}"/side),runtime(a.eval_root/"K1"/"dual"/f"K1_S{s}"/side),s,side) for s in (0,1) for side in SIDES}; payload={"schema":"a2_piper_base_v26_5_wave2_r1_k1_reducer_v2_per_env_window_topology","status":"EXPERIMENT_COMPLETE","raw_input_root":str(a.eval_root/"K1"),"pairs":rows,"typed_outcome":"K1_IDENTITY_ADMITTED" if all(x["pass"] for x in rows.values()) else "KILL_IDENTITY_NOT_ADMITTED"}
    else:
        formal={};
        for seed in (0,1):
            for step in (125,250):
                label=f"R1_S{seed}_STEP{step:04d}"; checkpoint=a.train_root/f"R1_S{seed}"/f"model_step_{step:06d}.pt"; formal[label]={side:metrics(runtime(a.eval_root/label/side),seed,side,checkpoint) for side in SIDES}
        endpoint=[formal[f"R1_S{s}_STEP0250"][side] for s in (0,1) for side in SIDES]; admitted=all(x["Stage3_admission_count"]>=16 and x["K5_episode_count"]>=16 and x["contact_stability_steps"]["rate"] is not None and x["contact_stability_steps"]["rate"]>=.9 and x["integrity_violations"]==0 for x in endpoint); payload={"schema":"a2_piper_base_v26_5_wave2_r1_reducer_v1","status":"EXPERIMENT_COMPLETE","fixed_steps":formal,"step250_route":"KILL_RESIDUAL_ACQUISITION_REGRESSION" if not admitted else "PROMOTE_STAGE5_RELAY" if all(x["stage_episode_count"]["stage4"]>0 for x in endpoint) else "PROMOTE_SUSTAINED_RELAY" if all(x["sustained_handle_ge_0_1_current_K5_ge_5"]["episode_count"]>=2 for x in endpoint) else "GRAY_EXTEND_ONCE"}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8");print(a.output)
if __name__=="__main__":main()
