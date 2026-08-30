#!/usr/bin/env python3
"""Fail-fast static verifier for the fresh r13 primary-cache admission."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2];RUN_ID="v26_5_wave2_r1_policy_residual_20260830_r13";SOURCE=ROOT/"logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt";DOOR=ROOT/"gr00t/rl/envs/door/door_open_a2_base.py"
RAW=["dof_pos","relative_to_door","dof_vel","actions","projected_gravity","door_dof_pos","base_lin_vel","base_ang_vel","hand_force","stage","privileged_door_info","delta_actions","gripper_handle_transform","a2_base_command_raw","a2_base_command"];GAUGE=[*RAW[:12],"gripper_handle_transform_gauge",*RAW[13:]]
def require(v,m):
 if not v:raise RuntimeError(m)
def flat(x,p=""):
 if isinstance(x,dict):
  out={}
  for k,v in x.items():out.update(flat(v,f"{p}.{k}" if p else k))
  return out
 return {p:x}
def main():
 p=argparse.ArgumentParser();p.add_argument("--registry",type=Path,required=True);p.add_argument("--selector-root",type=Path,required=True);a=p.parse_args();r=json.loads(a.registry.read_text())
 require(r.get("schema")=="a2_piper_base_v26_5_wave2_r13_registry_v1" and r.get("status")=="PREREGISTERED_NOT_RUN" and r.get("run_id")==RUN_ID and r.get("source_checkpoint")==str(SOURCE),"r13 registry")
 require(r.get("primary_cache_contract")=={"main_geometry_target_enabled":False,"actor_gauge_enabled":True,"scene_readers":1,"o1_sensor_or_physx_view":False,"raw_pose_term":"gripper_handle_transform","residual_pose_term":"gripper_handle_transform_gauge","residual_action_slice":[5,12]},"r13 primary cache registry contract")
 formal=r.get("formal",{});require(formal.get("admission_artifact")=="K1/identity_reducer.json" and formal.get("required_typed_outcome")=="R13_CAUSAL_IDENTITY_ADMITTED" and formal.get("smoke")=={"label":"R13_SMOKE64_B1","physical_gpu":4,"num_envs":64,"batches":1} and formal.get("train",{}).get("cells")==[{"label":"R13_S0","seed":0,"physical_gpu":4},{"label":"R13_S1","seed":1,"physical_gpu":5}] and formal.get("train",{}).get("num_envs")==4096 and formal.get("train",{}).get("batches")==250 and formal.get("train",{}).get("save_steps")==[125,250] and formal.get("train",{}).get("s1_main_started_after_s0_first_iteration") is True and formal.get("eval")=={"steps":[125,250],"episodes_per_side":64,"sides":["left","right"]},"r13 formal smoke/train/eval registry")
 cpu=json.loads((a.registry.parent/"r13_cpu_primary_cache_gate.json").read_text());actor=cpu.get("actor_shadow",{});se3=cpu.get("se3_primary_cache",{})
 binding=se3.get("implementation_binding",{});o0=se3.get("o0_representation_static",{});boundary=se3.get("geometry_evidence_boundary",{});offsets=se3.get("actual_o0_authored_offsets",{})
 require(cpu.get("schema")=="a2_piper_base_v26_5_r13_cpu_primary_cache_gate_v3" and cpu.get("status")=="PASS" and actor.get("checkpoint_path")==str(SOURCE) and actor.get("actor_state_key")=="policy_state_dict" and actor.get("rms_source_fields")==["running_mean_std.running_mean","running_mean_std.running_var","running_mean_std.count"] and actor.get("identity_within_tolerance") is True and actor.get("base_frozen_grad_free") is True and actor.get("residual_grad_present") is True and max(actor[k] for k in ("two_d_mean_max_abs","rollout_mean_max_abs","rollout_std_max_abs"))<=1e-6 and all(binding.get(k) is True for k in ("geometry_helper_uses_live_usd","right_handle_joint_localrot0_ast","left_handle_joint_has_no_extra_localrot0_ast","geometry_helper_joint_axis_ast","cache_delta_assignment_ast","cache_delta_env_major_reshape_ast","geometry_disabled_keeps_o0_ast","getter_live_position_reuse_ast","getter_live_quaternion_delta_ast","ordered_handle_pregrasp_ast")) and offsets=={"handle":{"pos":[0.0,0.0,0.0],"rot":[0.5,0.5,0.5,0.5]},"pregrasp":{"pos":[-0.1,0.0,0.0],"rot":[0.5,0.5,0.5,0.5]}} and o0=={"representation_shape":[64,18],"position_reused_max_abs":0.0} and boundary=={"static_source_chain":"DoorSpawner right LocalRot0 + Door helper joint-axis/opening/columns/quat_from_matrix is AST-bound","no_static_o1_quaternion_or_delta_claim":True,"required_runtime_evidence":"R13 two-control-tick wiring followed by exact64 K1"} and se3.get("exactly_one_primary_scene_reader") is True and se3.get("no_historical_o1_sensor_symbols") is True and se3.get("historical_o1_symbols_checked")==["A2_V26_5_GAUGE_GRIPPER_HANDLE_FRAME_TRANSFORMER","piper_gripper_handle_frame_transformer_gauge"],"r13 CPU/SE3 proof")
 text=DOOR.read_text();require(text.count("simulator.scene.sensors[self.A2_GRIPPER_HANDLE_FRAME_TRANSFORMER] = (")==1 and text.count("= (\n                OrderedTargetFrameTransformer(")==1 and "A2_V26_5_GAUGE_GRIPPER_HANDLE_FRAME_TRANSFORMER" not in text and "piper_gripper_handle_frame_transformer_gauge" not in text and "get_a2_v26_5_gauge_target_pose_source" in text and "_a2_v26_5_gauge_offset_delta_quat" in text,"r13 sole primary scene reader source")
 for name,schema in (("train","a2_piper_base_v26_5_wave2_r13_policy_residual_v1"),("eval","a2_piper_base_v26_5_wave2_r13_eval_policy_residual_v1")):
  cfg=flat(yaml.safe_load((a.selector_root/f"R13_{name}_selector.yaml").read_text()));require(cfg.get("v26_schema")==schema and cfg.get("env.config.a2_v26_5_geometry_target_enabled") is False and cfg.get("env.config.a2_v26_5_actor_gauge_enabled") is True and cfg.get("obs.obs_dict.actor_obs")==RAW and cfg.get("obs.obs_dict.residual_actor_obs")==GAUGE and cfg.get("algo.config.actor.input_key")=="actor_obs" and cfg.get("algo.config.actor.residual_input_key")=="residual_actor_obs",f"r13 {name} selector")
 orch=(ROOT/"scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_orchestrate.sh").read_text();reduce=(ROOT/"scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_reduce.py").read_text();require("require_admitted" in orch and "R13_CAUSAL_IDENTITY_ADMITTED" in orch and "smoke)" in orch and "train-cell)" in orch and "eval-cell)" in orch and "r13_smoke.sh" in orch and "r13_train_cell.sh" in orch and "r13_eval_cell.sh" in orch and "--self-check" in reduce,"r13 formal entrypoints")
 print(a.registry)
if __name__=="__main__":main()
