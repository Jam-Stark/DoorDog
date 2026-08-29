#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 GPU CELL TRAIN_DIR EVAL_ROOT SEED CANONICAL_OVERRIDE"
    exit 0
fi
[[ $# -eq 6 ]] || exit 2

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
gpu=$1
cell=$2
train_dir=$3
eval_root=$4
seed=$5
canonical_override=$6
[[ "$cell" =~ ^C[01]_CANONICAL_(OFF|ON)_S[01]$ ]] || { echo "invalid v26-4 eval cell: $cell" >&2; exit 2; }
[[ "$seed" =~ ^[01]$ && "$cell" == *_S"$seed" ]] || { echo "cell/seed mismatch: $cell seed=$seed" >&2; exit 2; }

for step in 125 250 500 750; do
    checkpoint="$train_dir/model_step_$(printf '%06d' "$step").pt"
    label="${cell}_STEP$(printf '%04d' "$step")"
    bash "$repo/scriptsFORhuman/v26_4/run_base_v26_4_eval_lane.sh" \
        "$gpu" "$label" "$checkpoint" "$eval_root" "$seed" "$canonical_override"
done
