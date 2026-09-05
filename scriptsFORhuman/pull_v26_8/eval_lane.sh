#!/usr/bin/env bash
# GPU0 owns the serial milestone evaluation lane; each cell produces both sides.
set -euo pipefail
[[ $# -ge 5 ]] || { echo "usage: $0 GPU STEP TRAIN_ROOT EVAL_ROOT CELL [CELL ...]" >&2; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
gpu=$1
step=$2
train_root=$3
eval_root=$4
shift 4
[[ "$gpu" == 0 ]] || { echo "pull-v26-8 eval lane is bound to GPU0" >&2; exit 2; }
for cell in "$@"; do
  bash "$repo/scriptsFORhuman/pull_v26_8/eval_cell.sh" "$gpu" "$cell" "$step" "$train_root" "$eval_root"
done
