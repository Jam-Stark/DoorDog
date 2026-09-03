#!/usr/bin/env bash
# Exact64 natural bilateral evaluator for one v26-7 checkpoint.  Unlike the
# v26-6 evaluator this is deliberately bound to physical GPU0 or GPU1.
set -euo pipefail
[[ $# -eq 5 ]] || { echo "usage: $0 GPU CELL STEP TRAIN_ROOT EVAL_ROOT" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; cell=$2; step=$3; train_root=$4; eval_root=$5
[[ "$gpu" =~ ^[01]$ ]] || { echo "v26-7 evaluation is bound to GPU0 or GPU1" >&2; exit 2; }
[[ "$cell" =~ ^Q(05|20)_S[012]$ ]] || exit 2
[[ "$step" =~ ^(1000|2000|3000|4000|5000|6000)$ ]] || exit 2
seed=${cell##*_S}
checkpoint="$train_root/$cell/model_step_$(printf '%06d' "$step").pt"
[[ -f "$checkpoint" ]] || { echo "missing v26-7 checkpoint: $checkpoint" >&2; exit 2; }
label="${cell}_STEP${step}"

for side in left right; do
  output="$eval_root/$label/$side"
  [[ ! -e "$output" ]] || { echo "refusing to overwrite v26-7 eval output: $output" >&2; exit 1; }
  env CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 \
      WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo" \
    "$py" -B -m gr00t.rl.eval_agent_trl \
      +ablation=wbmanip/base_v26_eval_natural_start \
      ++checkpoint="$checkpoint" ++checkpoint_load_mode=full ++auto_load_latest=false \
      ++seed="$seed" ++num_envs=64 ++algo.config.num_mini_batches=1 \
      ++algo.config.eval.num_eval_episodes=64 ++algo.config.eval.eval_num_envs_episodes=true \
      ++algo.config.eval.dump_to_log_metrics=true ++algo.config.eval.a2_diagnostic_trace_enabled=true \
      ++algo.config.eval.a2_diagnostic_reward_terms='[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' \
      ++algo.config.eval.a2_forced_gripper_close_enabled=false \
      ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false \
      ++env.config.a2_v26_2_telemetry_enabled=true ++env.config.a2_v26_3_telemetry_enabled=true \
      ++env.config.a2_v26_door_open_lr="$side" ++env.config.a2_v26_side_permutation_seed="$seed" \
      ++env.config.enable_staged_reset=false ++simulator.config.render_results=false \
      ++env.config.save_rendering_dir="$output/renderings" \
      ++eval_name="V26_7_${label}_${side}" ++eval_output_dir="$output"
  for required in metrics_eval.json a2_v14_per_env_records.json stage2_5_step_trace.json a2_eval_diagnostic_metadata.json .hydra/runtime_config.yaml; do
    [[ -f "$output/$required" ]] || { echo "missing v26-7 eval artifact: $output/$required" >&2; exit 1; }
  done
done
