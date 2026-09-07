#!/usr/bin/env bash
# One Wave-2 full-checkpoint continuation.  Receipt orchestration is external.
set -euo pipefail

usage() {
  echo "usage: $0 GPU P_S0|P_S1|P_S2 WAVE1_TRAIN_ROOT OUTPUT_DIR" >&2
}
[[ $# -eq 4 ]] || { usage; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
wave1_train_root=$3
output=$4

case "$cell" in
  P_S0) expected_gpu=1; seed=0 ;;
  P_S1) expected_gpu=2; seed=1 ;;
  P_S2) expected_gpu=3; seed=2 ;;
  *) usage; exit 2 ;;
esac
[[ "$gpu" == "$expected_gpu" ]] || { echo "$cell is bound to GPU$expected_gpu" >&2; exit 2; }
source_checkpoint="$wave1_train_root/$cell/model_step_006000.pt"
[[ -f "$source_checkpoint" ]] || { echo "missing final Wave1 checkpoint: $source_checkpoint" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "fresh Wave2 output required: $output" >&2; exit 1; }
mkdir -p "$output"

selector="wbmanip/pull_v26_8_backbone_${cell}"
runtime=(
  CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0
  WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo"
)
common=(
  +exp=wbmanip/door_open_a2_pull_v26_backbone_lstm +ablation="$selector"
  checkpoint="$source_checkpoint" checkpoint_load_mode=full auto_load_latest=false
  seed="$seed" num_envs=1024 algo.trl.num_total_batches=9000 callbacks.model_save.save_frequency=250
  headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false
  experiment_dir="$output" output_dir="$output/output"
  project_name=a2_piper_pull_v26_8_backbone experiment_name="$cell" +device=cuda:0
)

env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
"$py" "$repo/scriptsFORhuman/pull_v26_8/verify.py" --config "$output/resolved_config.yaml" --cell "$cell" --continuation-from "$source_checkpoint"
"$py" "$repo/scriptsFORhuman/pull_v26_8/p0_assets.py" --output "$output/p0_assets.json"
exec "$py" "$repo/scriptsFORhuman/pull_v26_8/runner.py" --output "$output" --gpu "$gpu" --required model_step_009000.pt -- \
  env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}"
