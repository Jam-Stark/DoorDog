#!/usr/bin/env bash
set -euo pipefail

usage() { echo "usage: $0 GPU LABEL CHECKPOINT OUTPUT_ROOT SEED O0A0|O0A1|O1A0|O1A1 left|right"; }
[[ ${1:-} == --help || ${1:-} == -h ]] && { usage; exit 0; }
[[ $# -eq 7 ]] || { usage >&2; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; label=$2; checkpoint=$3; output_root=$4; seed=$5; factor=$6; side=$7
[[ "$gpu" =~ ^(2|4|5|6|7)$ && "$seed" =~ ^[01]$ && "$side" =~ ^(left|right)$ && -f "$checkpoint" ]] || { usage >&2; exit 2; }
case "$factor" in
  O0A0) selector=wbmanip/base_v26_5_eval_O0A0 ;;
  O0A1) selector=wbmanip/base_v26_5_eval_O0A1 ;;
  O1A0) selector=wbmanip/base_v26_5_eval_O1A0 ;;
  O1A1) selector=wbmanip/base_v26_5_eval_O1A1 ;;
  *) usage >&2; exit 2 ;;
esac
output="$output_root/$label/$side"
[[ ! -e "$output" ]] || { echo "refusing to overwrite Wave1 eval: $output" >&2; exit 1; }
env CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 PYTHONPATH="$repo" \
  "$python_bin" -B -m gr00t.rl.eval_agent_trl +ablation="$selector" \
  ++checkpoint="$checkpoint" ++checkpoint_load_mode=full ++auto_load_latest=false ++seed="$seed" ++num_envs=64 \
  ++algo.config.num_mini_batches=1 ++algo.config.eval.num_eval_episodes=64 ++algo.config.eval.eval_num_envs_episodes=true \
  ++algo.config.eval.dump_to_log_metrics=true ++algo.config.eval.a2_diagnostic_trace_enabled=true \
  ++algo.config.eval.a2_diagnostic_reward_terms='[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' \
  ++algo.config.eval.a2_forced_gripper_close_enabled=false ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false \
  ++env.config.a2_v26_2_telemetry_enabled=true ++env.config.a2_v26_3_telemetry_enabled=true \
  ++env.config.a2_v26_door_open_lr="$side" ++env.config.a2_v26_side_permutation_seed="$seed" ++env.config.enable_staged_reset=false \
  ++simulator.config.render_results=false ++env.config.save_rendering_dir="$output/renderings" \
  ++eval_name="V26_5_${label}_${side}" ++eval_output_dir="$output"
for required in metrics_eval.json a2_v14_per_env_records.json stage2_5_step_trace.json a2_eval_diagnostic_metadata.json; do
  [[ -f "$output/$required" ]] || { echo "missing required eval artifact: $output/$required" >&2; exit 1; }
done
