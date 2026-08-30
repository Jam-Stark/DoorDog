#!/usr/bin/env bash
set -euo pipefail
# max_episode_length_s=.02 times out after exactly two control ticks; this is
# the pre-K1 dual-input construction and first-forward runtime gate.
[[ $# -eq 2 ]] || { echo "usage: $0 GPU OUTPUT_ROOT" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper; py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; output=$2; checkpoint="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
[[ "$gpu" == 4 && ! -e "$output" && -f "$checkpoint" ]] || exit 2
env CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 PYTHONPATH="$repo" \
  "$py" -B -m gr00t.rl.eval_agent_trl +ablation=wbmanip/base_v26_5_wave2_R1_eval_policy_residual \
  ++checkpoint="$checkpoint" ++checkpoint_load_mode=policy_only ++policy_only_load_actor_rms=true ++auto_load_latest=false ++seed=0 ++num_envs=64 \
  ++algo.config.eval.a2_v23_p06_policy_only=false ++algo.config.eval.a2_v26_5_policy_only_identity_control=false ++algo.config.eval.a2_v26_5_policy_only_residual=true ++algo.config.eval.a2_v26_5_runtime_load_receipt=true ++algo.config.eval.num_eval_episodes=64 ++algo.config.eval.eval_num_envs_episodes=true ++env.config.a2_v26_door_open_lr=right ++env.config.a2_v26_side_permutation_seed=0 ++env.config.enable_staged_reset=false ++env.config.max_episode_length_s=0.02 ++eval_output_dir="$output"
"$py" - "$output" <<'PY'
import json,sys,yaml
from pathlib import Path
p=Path(sys.argv[1]); cfg=yaml.safe_load((p/'.hydra/runtime_config.yaml').read_text()); receipt=json.loads((p/'a2_v26_5_runtime_load_receipt.json').read_text()); metrics=json.loads((p/'metrics_eval.json').read_text()); records=json.loads((p/'a2_v14_per_env_records.json').read_text())
raw=['dof_pos','relative_to_door','dof_vel','actions','projected_gravity','door_dof_pos','base_lin_vel','base_ang_vel','hand_force','stage','privileged_door_info','delta_actions','gripper_handle_transform','a2_base_command_raw','a2_base_command']; gauge=[*raw[:12],'gripper_handle_transform_gauge',*raw[13:]]
if cfg['env']['config'].get('max_episode_length_s')!=0.02 or cfg['env']['config'].get('a2_v26_5_geometry_target_enabled') is not False or cfg['obs']['obs_dict'].get('actor_obs')!=raw or cfg['obs']['obs_dict'].get('residual_actor_obs')!=gauge: raise SystemExit('wiring runtime config mismatch')
if receipt['actor']['dual_input_contract']['base_input_key']!='actor_obs' or receipt['actor']['dual_input_contract']['residual_input_key']!='residual_actor_obs': raise SystemExit('wiring dual input receipt mismatch')
term=metrics.get('episode_terminal_diagnostics')
lengths=metrics.get('episode_lengths')
if metrics.get('completed_episodes')!=64 or not isinstance(term,list) or len(term)!=64 or not isinstance(records,list) or len(records)!=64 or not isinstance(lengths,list) or len(lengths)!=64: raise SystemExit('wiring exact64 evidence missing')
if any(value!=2 for value in lengths) or any(row.get('episode_length_buf')!=2 for row in term): raise SystemExit('wiring terminal episode length must be exactly two')
PY
