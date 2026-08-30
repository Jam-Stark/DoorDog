#!/usr/bin/env bash
set -euo pipefail
# max_episode_length_s=.02 times out after exactly two control ticks; this is
# the pre-K1 dual-input construction and first-forward runtime gate.
[[ $# -eq 4 ]] || { echo "usage: $0 GPU OUTPUT_ROOT SUPERVISOR_RECEIPT VALIDATOR_ARTIFACT" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper; py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; output=$2; supervisor_receipt=$3; validator_artifact=$4; checkpoint="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
[[ "$gpu" == 4 && ! -e "$output" && ! -e "$validator_artifact" && -f "$checkpoint" ]] || exit 2
env CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 PYTHONPATH="$repo" \
  "$py" -B -m gr00t.rl.eval_agent_trl +ablation=wbmanip/base_v26_5_wave2_R1_eval_policy_residual \
  ++checkpoint="$checkpoint" ++checkpoint_load_mode=policy_only ++policy_only_load_actor_rms=true ++auto_load_latest=false ++seed=0 ++num_envs=64 \
  ++algo.config.eval.a2_v23_p06_policy_only=false ++algo.config.eval.a2_v26_5_policy_only_identity_control=false ++algo.config.eval.a2_v26_5_policy_only_residual=true ++algo.config.eval.a2_v26_5_runtime_load_receipt=true ++algo.config.eval.num_eval_episodes=64 ++algo.config.eval.eval_num_envs_episodes=true ++env.config.a2_v26_door_open_lr=right ++env.config.a2_v26_side_permutation_seed=0 ++env.config.enable_staged_reset=false ++env.config.max_episode_length_s=0.02 ++eval_output_dir="$output"
"$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r12_wiring_validate.py" --raw-output "$output" --supervisor-receipt "$supervisor_receipt" --output "$validator_artifact"
