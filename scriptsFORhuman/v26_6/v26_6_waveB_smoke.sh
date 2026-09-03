#!/usr/bin/env bash
# v26-6 Wave B smoke: real rollout + PPO update + checkpoint under the restored
# gripper contract, before committing four long cells.  Uses the B0 selector.
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: $0 GPU OUTPUT_DIR" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; output=$2
source_cont="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
[[ "$gpu" =~ ^[4567]$ ]] || exit 2
[[ -f "$source_cont" ]] || exit 2
[[ ! -e "$output" ]] || { echo "refusing to overwrite: $output" >&2; exit 1; }
mkdir -p "$output"

env CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 \
    WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo" \
  "$py" -B -m gr00t.rl.train_agent_trl \
    +exp=wbmanip/door_open_a2_base_lstm \
    +ablation=wbmanip/base_v26_6_waveB_B0 \
    checkpoint="$source_cont" checkpoint_load_mode=policy_only policy_only_load_actor_rms=true \
    auto_load_latest=false seed=0 num_envs=64 \
    algo.trl.num_total_batches=2 callbacks.model_save.save_frequency=1 \
    algo.config.num_mini_batches=1 \
    env.config.a2_v26_side_permutation_seed=0 \
    headless=true use_wandb=false \
    simulator.config.render_results=false simulator.config.cameras.enable_cameras=false \
    experiment_dir="$output" output_dir="$output/output" \
    project_name=base_v26_6_waveB_smoke experiment_name=V26_6_WAVEB_SMOKE v26_cell=V26_6_WAVEB_SMOKE

[[ -f "$output/model_step_000002.pt" ]] || { echo "smoke produced no step2 checkpoint" >&2; exit 1; }
