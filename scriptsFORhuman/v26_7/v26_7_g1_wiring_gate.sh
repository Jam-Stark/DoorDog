#!/usr/bin/env bash
# G1: a 64-env/two-batch construction run followed by matched old/new target
# dumps.  The two-batch cap is intentionally below the frozen five-batch limit.
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: $0 GPU OUTPUT_ROOT" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; root=$2
[[ "$gpu" =~ ^[01]$ ]] || { echo "G1 is bound to physical GPU0 or GPU1" >&2; exit 2; }
[[ ! -e "$root" ]] || { echo "refusing to reuse G1 root: $root" >&2; exit 1; }
mkdir -p "$root/train_probe"
runtime=(CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo")

env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl \
  +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v26_7_Q05_S0 \
  checkpoint=null checkpoint_load_mode=full auto_load_latest=false seed=0 num_envs=64 \
  algo.trl.num_total_batches=2 callbacks.model_save.save_frequency=2 algo.config.num_mini_batches=1 \
  env.config.a2_v26_side_permutation_seed=0 headless=true use_wandb=false \
  simulator.config.render_results=false simulator.config.cameras.enable_cameras=false \
  experiment_dir="$root/train_probe" output_dir="$root/train_probe/output" \
  project_name=base_v26_7_g1_wiring experiment_name=V26_7_G1 v26_cell=V26_7_G1

checkpoint="$root/train_probe/model_step_000002.pt"
[[ -f "$checkpoint" ]] || { echo "G1 short run did not save its step2 checkpoint" >&2; exit 1; }
for mode in old fixed; do
  output="$root/$mode"
  override=false
  [[ "$mode" == fixed ]] && override=true
  env "${runtime[@]}" "$py" -B -m gr00t.rl.eval_agent_trl \
    +ablation=wbmanip/base_v26_eval_natural_start \
    ++checkpoint="$checkpoint" ++checkpoint_load_mode=full ++auto_load_latest=false \
    ++seed=0 ++num_envs=64 ++algo.config.num_mini_batches=1 \
    ++algo.config.eval.num_eval_episodes=64 ++algo.config.eval.eval_num_envs_episodes=true \
    ++algo.config.eval.dump_to_log_metrics=true ++env.config.a2_v26_door_open_lr=bilateral \
    ++env.config.a2_v26_side_permutation_seed=0 ++env.config.enable_staged_reset=false \
    ++env.config.a2_v26_6_side_mirrored_handle_offset_enabled="$override" \
    ++env.config.max_episode_length_s=0.02 ++simulator.config.render_results=false \
    ++eval_name="V26_7_G1_${mode}" ++eval_output_dir="$output"
  [[ -f "$output/metrics_eval.json" ]] || { echo "G1 target dump missing metrics: $output" >&2; exit 1; }
done
"$py" "$repo/scriptsFORhuman/v26_7/v26_7_g1_reduce.py" \
  --old "$root/old/metrics_eval.json" --fixed "$root/fixed/metrics_eval.json" \
  --output "$root/g1_wiring.json"
