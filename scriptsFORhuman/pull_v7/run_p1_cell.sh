#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 3 ]] || { echo 'usage: run_p1_cell.sh GPU P_S1|P_S2 OUTPUT_DIR' >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
output=$3
case "$cell" in
  P_S1) seed=1 ;;
  P_S2) seed=2 ;;
  *) exit 2 ;;
esac
source_checkpoint="$repo/logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/$cell/model_step_009000.pt"
[[ -f "$source_checkpoint" ]]
[[ ! -e "$output" ]]
mkdir -p "$output"
cd "$repo"
runtime=(CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo")
common=(+exp=wbmanip/door_open_a2_pull_v26_backbone_lstm +ablation="wbmanip/pull_v26_8_backbone_$cell"
  checkpoint="$source_checkpoint" checkpoint_load_mode=full auto_load_latest=false
  seed="$seed" num_envs=1024 algo.trl.num_total_batches=9100 callbacks.model_save.save_frequency=50
  env._target_=scriptsFORhuman.pull_v7.p1_env.DoorOpenA2PullP1 ++env.config.a2_pull_p1_output="$output"
  headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false
  experiment_dir="$output" output_dir="$output/output" project_name=a2_piper_pull_v7 experiment_name="$cell" +device=cuda:0)
env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
"$py" "$repo/scriptsFORhuman/pull_v7/verify_p1_config.py" "$output/resolved_config.yaml" "$cell"
exec "$py" "$repo/scriptsFORhuman/pull_v26_8/runner.py" --output "$output" --gpu "$gpu" \
  --required model_step_009050.pt --required model_step_009100.pt --required exposure_complete.json -- \
  env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}"
