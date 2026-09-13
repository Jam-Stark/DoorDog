#!/usr/bin/env bash
# Exact64 natural, first-episode evaluator for one pull-v7 P2 milestone
# checkpoint.  The evaluator overrides are byte-for-byte the pull-v26.8
# continuation eval contract (scriptsFORhuman/pull_v26_8/continue_eval_cell.sh)
# except for the cell names, milestone steps and the GPU binding: pull-v26.8
# was pinned to GPU0, which now carries another user's LightNav server.
set -euo pipefail

usage() {
  echo "usage: $0 GPU T_S1|T_S2|C_S1|C_S2 9500|10000|10500 P2_TRAIN_ROOT EVAL_ROOT" >&2
}
[[ $# -eq 5 ]] || { usage; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
step=$3
train_root=$4
eval_root=$5
[[ "$gpu" =~ ^[123]$ ]] || { echo 'pull-v7 P2 evaluation runs on GPU1, GPU2 or GPU3 only' >&2; exit 2; }
[[ "$cell" =~ ^[TC]_S[12]$ ]] || { usage; exit 2; }
[[ "$step" =~ ^(9500|10000|10500)$ ]] || { usage; exit 2; }

if [[ "$cell" == T_* ]]; then
  diagnostic_reward_terms='[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge,a2_stage3_unlatch_hold,a2_stage3_stage4_hold_and_drive,a2_pull_v7_arm_target_overshoot_penalty]'
else
  diagnostic_reward_terms='[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge,a2_stage3_unlatch_hold,a2_stage3_stage4_hold_and_drive]'
fi

seed=${cell##*_S}
checkpoint="$train_root/$cell/model_step_$(printf '%06d' "$step").pt"
[[ -f "$checkpoint" ]] || { echo "missing milestone checkpoint: $checkpoint" >&2; exit 2; }
runtime=(
  CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0
  WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo"
)

for side in left right; do
  output="$eval_root/${cell}_STEP${step}/$side"
  [[ ! -e "$output" ]] || { echo "fresh P2 eval output required: $output" >&2; exit 1; }
  mkdir -p "$output"
  common=(
    checkpoint="$checkpoint" checkpoint_load_mode=full ++auto_load_latest=false
    ++seed="$seed" ++num_envs=64 ++headless=true ++use_wandb=false ++algo.config.num_mini_batches=1
    ++algo.config.eval.num_eval_episodes=64 ++algo.config.eval.eval_num_envs_episodes=true
    ++algo.config.eval.dump_to_log_metrics=true ++algo.config.eval.a2_diagnostic_trace_enabled=true
    ++algo.config.eval.a2_diagnostic_reward_terms="$diagnostic_reward_terms"
    ++env.config.a2_door_open_lr_distribution="$side" ++env.config.a2_door_open_lr_permutation_seed="$seed"
    ++env.config.enable_staged_reset=true ++env.config.staged_reset_ratios='[1.0,0.0,0.0,0.0,0.0,0.0]'
    ++env.config.a2_pull_v6_stage4_bank_enabled=false ++env.config.a2_pull_v61_late_state_bank_enabled=false
    ++simulator.config.render_results=false ++simulator.config.cameras.enable_cameras=false
    ++eval_name="PULL_V7_P2_${cell}_STEP${step}_${side}" ++eval_output_dir="$output" hydra.run.dir="$output" +device=cuda:0
  )
  env "${runtime[@]}" "$py" -B -m gr00t.rl.eval_agent_trl "${common[@]}" --cfg job --resolve > "$output/eval_overrides.yaml"
  "$py" "$repo/scriptsFORhuman/pull_v26_8/p0_assets.py" --output "$output/p0_assets.json"
  "$py" "$repo/scriptsFORhuman/pull_v26_8/runner.py" --output "$output" --gpu "$gpu" \
    --required metrics_eval.json --required a2_v14_per_env_records.json --required stage2_5_step_trace.json \
    --required a2_eval_diagnostic_metadata.json --required .hydra/runtime_config.yaml -- \
    env "${runtime[@]}" "$py" -B -m gr00t.rl.eval_agent_trl "${common[@]}"
  # The natural-protocol and plant checks are the unchanged pull-v26.8 evaluator
  # contract; the P2 cell name is not one of its three cells, so the source cell
  # identity is passed instead.
  case "$cell" in *_S1) source_cell=P_S1 ;; *_S2) source_cell=P_S2 ;; esac
  "$py" "$repo/scriptsFORhuman/pull_v26_8/verify.py" --config "$output/.hydra/runtime_config.yaml" --cell "$source_cell" --eval-side "$side"
done
