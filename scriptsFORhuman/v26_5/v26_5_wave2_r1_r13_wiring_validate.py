#!/usr/bin/env python3
"""Validate a clean r13 two-control-tick primary-cache wiring run."""
from __future__ import annotations
import argparse,json,shlex
from pathlib import Path
from omegaconf import OmegaConf

ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/"logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt";SCRIPT=ROOT/"scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_wiring_gate.sh"
RAW=["dof_pos","relative_to_door","dof_vel","actions","projected_gravity","door_dof_pos","base_lin_vel","base_ang_vel","hand_force","stage","privileged_door_info","delta_actions","gripper_handle_transform","a2_base_command_raw","a2_base_command"];GAUGE=[*RAW[:12],"gripper_handle_transform_gauge",*RAW[13:]]
DUAL={"base_input_key":"actor_obs","residual_input_key":"residual_actor_obs","base_observation_width":133,"residual_observation_width":133,"base_memory_mlp_frozen":True,"base_std_rms_frozen":True,"residual_action_slice":[5,12],"residual_final_layer_zero":True}
RESIDUAL_MISSING=["residual_module.0.weight","residual_module.0.bias","residual_module.2.weight","residual_module.2.bias"]
ACTOR_LOAD={"loaded":True,"state_key":"policy_state_dict","exact_keyset":True,"keyset_contract":"legacy_exact_without_residual","actor_rms_loaded":True,"strict":False,"missing_keys":RESIDUAL_MISSING,"unexpected_keys":[]}
def require(v,m):
    if not v:raise RuntimeError(m)
def load(p):require(p.is_file(),f"missing artifact: {p}");return json.loads(p.read_text())
def facts(raw:Path):
    cfg=OmegaConf.to_container(OmegaConf.load(raw/".hydra/runtime_config.yaml"),resolve=False);receipt=load(raw/"a2_v26_5_runtime_load_receipt.json");metrics=load(raw/"metrics_eval.json");records=load(raw/"a2_v14_per_env_records.json")
    env=cfg["env"]["config"];obs=cfg["obs"]["obs_dict"];actor=receipt.get("actor");term=metrics.get("episode_terminal_diagnostics");lengths=metrics.get("episode_lengths")
    require(env.get("max_episode_length_s")==.02 and env.get("a2_v26_5_geometry_target_enabled") is False and env.get("a2_v26_5_actor_gauge_enabled") is True and obs.get("actor_obs")==RAW and obs.get("residual_actor_obs")==GAUGE,"r13 resolved raw/residual config")
    require(receipt.get("schema")=="a2_piper_base_v26_5_runtime_load_receipt_v1" and receipt.get("status")=="CHECKPOINT_LOAD_COMPLETED" and receipt.get("output_root")==str(raw) and receipt.get("checkpoint_path")==str(SOURCE) and receipt.get("checkpoint_load_mode")=="policy_only" and isinstance(actor,dict) and {key:actor.get(key) for key in ACTOR_LOAD}==ACTOR_LOAD and actor.get("dual_input_contract")==DUAL,"r13 exact dual actor/RMS receipt")
    require(metrics.get("completed_episodes")==64 and isinstance(term,list) and isinstance(lengths,list) and len(term)==len(lengths)==len(records)==64 and set(x.get("env_id") for x in term)==set(range(64)) and all(x==2 for x in lengths) and all(x.get("episode_length_buf")==2 for x in term),"r13 exact64 two-tick evidence")
    return {"runtime_config":{"main_geometry_target_enabled":env["a2_v26_5_geometry_target_enabled"],"actor_gauge_enabled":env["a2_v26_5_actor_gauge_enabled"],"actor_obs":obs["actor_obs"],"residual_actor_obs":obs["residual_actor_obs"]},"runtime_load":{**ACTOR_LOAD,"dual_input_contract":actor["dual_input_contract"]},"episodes":{"completed":metrics["completed_episodes"],"records":len(records),"terminal":len(term),"lengths":lengths,"terminal_lengths":[x["episode_length_buf"] for x in term]}}
def main():
    p=argparse.ArgumentParser();p.add_argument("--raw-output",type=Path,required=True);p.add_argument("--supervisor-receipt",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--assert-admitted",action="store_true");a=p.parse_args();raw=a.raw_output.resolve();receipt_path=a.supervisor_receipt.resolve();out=a.output.resolve();require(raw.is_dir() and receipt_path.is_file(),"r13 raw/receipt missing")
    receipt=load(receipt_path);log=Path(receipt["output"]).resolve();require(log.is_file(),"r13 supervisor log missing");argv=shlex.split(receipt["command"]);require(len(argv)>=6 and argv[:2]==["bash",str(SCRIPT)] and argv[2]=="4" and argv[3]==str(raw),"r13 receipt command/raw binding");require(receipt.get("checkpoint")==str(raw/"metrics_eval.json"),"r13 receipt checkpoint/raw binding")
    text=log.read_text();clean={"evaluation_completed_exact64":"Evaluation completed - 64 episodes finished" in text,"post_validator_constructor_error": "ConstructorError" in text}
    if a.assert_admitted:
        require(receipt.get("state")=="PASS" and receipt.get("process_returncode")==0 and clean["evaluation_completed_exact64"] and not clean["post_validator_constructor_error"],"r13 clean supervisor provenance")
        value=load(out);require(value.get("schema")=="a2_piper_base_v26_5_r13_wiring_validator_v1" and value.get("status")=="PASS" and value.get("outcome")=="R13_WIRING_ADMITTED" and value.get("raw_output")==str(raw) and value.get("supervisor_receipt")==str(receipt_path) and value.get("receipt_state_at_validation")=="RUNNING" and value.get("measured_facts")==facts(raw),"r13 typed wiring admission mismatch");print(out);return
    require(not out.exists() and receipt.get("state")=="RUNNING" and clean["evaluation_completed_exact64"] and not clean["post_validator_constructor_error"],"r13 live validator provenance")
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({"schema":"a2_piper_base_v26_5_r13_wiring_validator_v1","status":"PASS","outcome":"R13_WIRING_ADMITTED","raw_output":str(raw),"supervisor_receipt":str(receipt_path),"receipt_state_at_validation":"RUNNING","measured_facts":facts(raw)},indent=2)+"\n");print(out)
if __name__=="__main__":main()
