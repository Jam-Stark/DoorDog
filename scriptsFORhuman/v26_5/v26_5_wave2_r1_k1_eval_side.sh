#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 6 ]] || { echo "usage: $0 GPU control|dual LABEL OUTPUT_ROOT SEED left|right" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
source_checkpoint="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
gpu=$1; view=$2; label=$3; output_root=$4; seed=$5; side=$6
[[ "$gpu" =~ ^[0-9]+$ && "$view" =~ ^(control|dual)$ && "$label" =~ ^K1_S[01]$ && "$seed" =~ ^[01]$ && "$side" =~ ^(left|right)$ && -f "$source_checkpoint" ]] || exit 2
[[ "${label##*_S}" == "$seed" ]] || { echo "label/seed mismatch" >&2; exit 2; }
case "$view" in control) selector=wbmanip/base_v26_5_eval_O0A0;; dual) selector=wbmanip/base_v26_5_wave2_R1_eval_policy_residual;; esac
output="$output_root/K1/$view/$label/$side"
[[ ! -e "$output" ]] || { echo "refusing to overwrite K1 eval: $output" >&2; exit 1; }
env CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 PYTHONPATH="$repo" \
  "$python_bin" -B -m gr00t.rl.eval_agent_trl +ablation="$selector" \
  ++checkpoint="$source_checkpoint" ++checkpoint_load_mode=policy_only ++policy_only_load_actor_rms=true ++auto_load_latest=false ++seed="$seed" ++num_envs=64 \
  ++algo.config.num_mini_batches=1 ++algo.config.eval.num_eval_episodes=64 ++algo.config.eval.eval_num_envs_episodes=true \
  ++algo.config.eval.dump_to_log_metrics=true ++algo.config.eval.a2_diagnostic_trace_enabled=true \
  ++algo.config.eval.a2_diagnostic_reward_terms='[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' \
  ++algo.config.eval.a2_forced_gripper_close_enabled=false ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false \
  ++env.config.a2_v26_2_telemetry_enabled=true ++env.config.a2_v26_3_telemetry_enabled=true ++env.config.a2_v26_door_open_lr="$side" ++env.config.a2_v26_side_permutation_seed="$seed" ++env.config.enable_staged_reset=false \
  ++simulator.config.render_results=false ++env.config.save_rendering_dir="$output/renderings" ++eval_name="V26_5_R1_K1_${view}_${label}_${side}" ++eval_output_dir="$output"
for artifact in metrics_eval.json a2_v14_per_env_records.json stage2_5_step_trace.json a2_eval_diagnostic_metadata.json; do [[ -f "$output/$artifact" ]] || { echo "missing K1 artifact: $output/$artifact" >&2; exit 1; }; done
