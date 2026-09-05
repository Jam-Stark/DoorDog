#!/usr/bin/env bash
# One frozen Wave-1 from-scratch cell.  Retry policy belongs to orchestrate.
set -euo pipefail

usage() {
  echo "usage: $0 GPU P_S0|P_S1|P_S2 OUTPUT_DIR" >&2
}
[[ $# -eq 3 ]] || { usage; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
output=$3
: "${PULL_V26_8_NUM_ENVS:?orchestrate must freeze PULL_V26_8_NUM_ENVS}"
: "${PULL_V26_8_TOTAL_BATCHES:?orchestrate must freeze PULL_V26_8_TOTAL_BATCHES}"

case "$cell" in
  P_S0) expected_gpu=1; seed=0 ;;
  P_S1) expected_gpu=2; seed=1 ;;
  P_S2) expected_gpu=3; seed=2 ;;
  *) usage; exit 2 ;;
esac
[[ "$gpu" == "$expected_gpu" ]] || { echo "$cell is bound to GPU$expected_gpu" >&2; exit 2; }
case "$PULL_V26_8_NUM_ENVS:$PULL_V26_8_TOTAL_BATCHES" in
  2048:4000|1024:6000) ;;
  *) echo "invalid frozen budget: $PULL_V26_8_NUM_ENVS/$PULL_V26_8_TOTAL_BATCHES" >&2; exit 2 ;;
esac
[[ ! -e "$output" ]] || { echo "fresh train output required: $output" >&2; exit 1; }
mkdir -p "$output"

selector="wbmanip/pull_v26_8_backbone_${cell}"
runtime=(
  CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0
  WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo"
)
common=(
  +exp=wbmanip/door_open_a2_pull_v26_backbone_lstm +ablation="$selector"
  checkpoint=null checkpoint_load_mode=full auto_load_latest=false
  seed="$seed" num_envs="$PULL_V26_8_NUM_ENVS"
  algo.trl.num_total_batches="$PULL_V26_8_TOTAL_BATCHES" callbacks.model_save.save_frequency=250
  headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false
  experiment_dir="$output" output_dir="$output/output"
  project_name=a2_piper_pull_v26_8_backbone experiment_name="$cell" +device=cuda:0
)

env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
"$py" "$repo/scriptsFORhuman/pull_v26_8/verify.py" --config "$output/resolved_config.yaml" --cell "$cell"

final_checkpoint="model_step_$(printf '%06d' "$PULL_V26_8_TOTAL_BATCHES").pt"
"$py" "$repo/scriptsFORhuman/pull_v26_8/p0_assets.py" --output "$output/p0_assets.json"
exec "$py" "$repo/scriptsFORhuman/pull_v26_8/runner.py" --output "$output" --gpu "$gpu" --required "$final_checkpoint" -- \
  env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}"
