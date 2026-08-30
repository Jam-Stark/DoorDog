#!/usr/bin/env python3
"""Write the immutable r13 primary-cache admission registry."""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN_ID="v26_5_wave2_r1_policy_residual_20260830_r13"
SOURCE=ROOT/"logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"

def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    if a.output.exists(): raise RuntimeError(f"refusing to overwrite r13 registry: {a.output}")
    if not SOURCE.is_file(): raise RuntimeError(f"missing CONT_STEP2000: {SOURCE}")
    formal_cells=[{"label":"R13_S0","seed":0,"physical_gpu":4},{"label":"R13_S1","seed":1,"physical_gpu":5}]
    payload={"schema":"a2_piper_base_v26_5_wave2_r13_registry_v1","status":"PREREGISTERED_NOT_RUN","run_id":RUN_ID,"source_checkpoint":str(SOURCE),"selectors":{"train":"wbmanip/base_v26_5_wave2_R13_policy_residual","eval":"wbmanip/base_v26_5_wave2_R13_eval_policy_residual"},"primary_cache_contract":{"main_geometry_target_enabled":False,"actor_gauge_enabled":True,"scene_readers":1,"o1_sensor_or_physx_view":False,"raw_pose_term":"gripper_handle_transform","residual_pose_term":"gripper_handle_transform_gauge","residual_action_slice":[5,12]},"wiring":{"seed":0,"side":"right","physical_gpu":4,"num_envs":64,"max_episode_length_s":0.02,"control_ticks":2,"runtime_evidence":"exact_policy_only_actor_rms_load_and_resolved_config","static_evidence":"primary_cache_single_scene_reader"},"K1":{"cells":[{"label":"K1_S0","seed":0,"physical_gpu":4},{"label":"K1_S1","seed":1,"physical_gpu":5}],"sides":["left","right"],"episodes_per_side":64,"identity_tolerance":1e-6,"reducer":"unchanged_per_env_full_topology_no_pooling","all_pass_outcome":"R13_CAUSAL_IDENTITY_ADMITTED","any_fail_outcome":"KILL_R13_IDENTITY_NOT_ADMITTED","s1_stagger_seconds":600},"formal":{"admission_artifact":"K1/identity_reducer.json","required_typed_outcome":"R13_CAUSAL_IDENTITY_ADMITTED","smoke":{"label":"R13_SMOKE64_B1","physical_gpu":4,"num_envs":64,"batches":1},"train":{"cells":formal_cells,"num_envs":4096,"batches":250,"save_steps":[125,250],"s1_main_started_after_s0_first_iteration":True},"eval":{"steps":[125,250],"episodes_per_side":64,"sides":["left","right"]}}}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8");print(a.output)
if __name__=="__main__": main()
