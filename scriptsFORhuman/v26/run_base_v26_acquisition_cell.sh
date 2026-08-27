#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 GPU CELL ABLATION" >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
run_root="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/formal"
gpu=$1
cell=$2
ablation=$3
run_dir="$run_root/$cell"

mkdir -p "$run_dir"

env CUDA_VISIBLE_DEVICES=0,1,2,3 \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    ACCELERATE_TORCH_DEVICE="cuda:$gpu" \
    WANDB_MODE=disabled \
    PYTHONPATH="$repo" \
    "$python_bin" -m gr00t.rl.train_agent_trl \
    +exp=wbmanip/door_open_a2_base_lstm \
    +ablation="wbmanip/$ablation" \
    experiment_name="$cell" \
    experiment_dir="$run_dir" \
    output_dir="$run_dir/output" \
    project_name=a2_piper_base_v26_acquisition_supplement \
    +topology_id="V26-ACQ-SUPPLEMENT-1GPU-$gpu" \
    +gpu_binding_mode="accelerate-torch-device-cuda-$gpu"
