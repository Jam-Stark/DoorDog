#!/usr/bin/env python3
"""Write the immutable r14 post-construction-reseed preregistry."""
from __future__ import annotations
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUN_ID="v26_5_wave2_r1_policy_residual_20260831_r14";SOURCE=ROOT/"logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
def main():
 p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);a=p.parse_args()
 if a.output.exists() or not SOURCE.is_file():raise RuntimeError("r14 fresh registry/source required")
 payload={"schema":"a2_piper_base_v26_5_wave2_r14_registry_v1","status":"PREREGISTERED_NOT_RUN","run_id":RUN_ID,"source_checkpoint":str(SOURCE),"axis":"R14_POST_CONSTRUCTION_RESEED","selectors":{"train":"wbmanip/base_v26_5_wave2_R14_policy_residual","eval":"wbmanip/base_v26_5_wave2_R14_eval_policy_residual"},"reseed":{"flag":"algo.config.eval.a2_v26_5_post_construction_reseed","pilot_trace_flag":"algo.config.eval.a2_v26_5_post_construction_reseed_pilot_trace"},"pilot":{"seed":0,"side":"left","gpu":4,"num_envs":64,"max_episode_length_s":.98,"episode_length":50,"pilot_trace":True,"outcome":"R14_RESEED_PILOT_ADMITTED"},"K1":{"cells":[{"label":"K1_S0","seed":0,"physical_gpu":4},{"label":"K1_S1","seed":1,"physical_gpu":5}],"sides":["left","right"],"episodes":64,"pilot_trace":False,"outcome":"K1_R14_IDENTITY_ADMITTED","kill":"KILL_R14_IDENTITY_NOT_ADMITTED","s1_stagger_seconds":600},"formal":{"requires":"K1_R14_IDENTITY_ADMITTED","cells":[{"label":"R14_S0","seed":0,"gpu":4},{"label":"R14_S1","seed":1,"gpu":5}],"num_envs":4096,"batches":250,"save_steps":[125,250],"formal_train_reseed":False,"formal_eval_reseed":False,"formal_eval_pilot_trace":False}}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(payload,indent=2)+"\n");print(a.output)
if __name__=="__main__":main()
