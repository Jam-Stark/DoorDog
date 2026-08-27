#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 6 || $# -gt 8 ]]; then
    echo "usage: $0 GPU LABEL CHECKPOINT OUTPUT_ROOT NUM_ENVS SEED [RENDER_RESULTS] [VISIBLE_DEVICES]" >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
label=$2
checkpoint=$3
output_root=$4
num_envs=$5
seed=$6
render_results=${7:-false}
visible_devices=${8:-0,1,2,3}

for side in left right; do
    output_dir="$output_root/$label/$side"
    rendering_dir="$output_dir/renderings"
    env CUDA_VISIBLE_DEVICES="$visible_devices" \
        CUDA_DEVICE_ORDER=PCI_BUS_ID \
        ACCELERATE_TORCH_DEVICE="cuda:$gpu" \
        WANDB_MODE=disabled \
        PYTHONPATH="$repo" \
        "$python_bin" -m gr00t.rl.eval_agent_trl \
        +ablation=wbmanip/base_v26_eval_natural_start \
        ++checkpoint="$checkpoint" \
        ++seed="$seed" \
        ++env.config.a2_v26_door_open_lr="$side" \
        ++env.config.a2_v26_side_permutation_seed="$seed" \
        ++num_envs="$num_envs" \
        ++algo.config.eval.num_eval_episodes="$num_envs" \
        ++simulator.config.render_results="$render_results" \
        ++env.config.save_rendering_dir="$rendering_dir" \
        ++eval_name="V26_${label}_${side}" \
        ++eval_output_dir="$output_dir"
done
