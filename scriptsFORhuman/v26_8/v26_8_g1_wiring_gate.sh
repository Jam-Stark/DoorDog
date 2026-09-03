#!/usr/bin/env bash
# G1 proves only the K wiring: a fresh, bounded 64-env K_S1 construction run.
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: $0 GPU OUTPUT_ROOT" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; root=$2
[[ "$gpu" == 0 ]] || { echo "v26-8 G1 is bound to GPU0" >&2; exit 2; }
[[ ! -e "$root" ]] || { echo "refusing to overwrite G1 output root: $root" >&2; exit 1; }
mkdir -p "$root"
output="$root/K_S1_smoke"
runtime=(CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo")
common=(+exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v26_8_K_S1 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir="$output" output_dir="$output/output" project_name=base_v26_8_g1 experiment_name=V26_8_G1_K_S1 v26_cell=V26_8_G1_K_S1 num_envs=64 algo.trl.num_total_batches=5 callbacks.model_save.save_frequency=5)
mkdir -p "$output"
env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
"$py" "$repo/scriptsFORhuman/v26_8/v26_8_capture_train.py" --output "$output" --checkpoint "$repo/logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S1/model_step_003000.pt" -- env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}"
exec "$py" "$repo/scriptsFORhuman/v26_8/v26_8_g1_reduce.py" --root "$root" --output "$root/g1_wiring.json"
