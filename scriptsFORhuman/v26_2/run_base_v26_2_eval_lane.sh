#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 GPU CELL TRAIN_DIR EVAL_ROOT [SEED]"
    exit 0
fi
if [[ $# -lt 4 || $# -gt 5 ]]; then
    echo "usage: $0 GPU CELL TRAIN_DIR EVAL_ROOT [SEED]" >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
gpu=$1
cell=$2
train_dir=$3
eval_root=$4
seed=${5:-1}
runner="$repo/scriptsFORhuman/v26_2/run_base_v26_2_route_a.sh"

for step in 250 500 750; do
    checkpoint="$train_dir/model_step_$(printf '%06d' "$step").pt"
    label="${cell}_STEP$(printf '%04d' "$step")"
    bash "$runner" "$gpu" "$label" "$checkpoint" "$eval_root" "$seed" 64 false
done
