#!/usr/bin/env bash
# One GPU-owned milestone lane.  Cells are serial within the lane; each cell is
# itself an exact64 LEFT+RIGHT evaluation.
set -euo pipefail
[[ $# -ge 5 ]] || { echo "usage: $0 GPU STEP TRAIN_ROOT EVAL_ROOT CELL [CELL ...]" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
gpu=$1; step=$2; train_root=$3; eval_root=$4; shift 4
[[ "$gpu" =~ ^[01]$ && "$step" =~ ^(1000|2000|3000|4000|5000|6000)$ ]] || exit 2
for cell in "$@"; do
  bash "$repo/scriptsFORhuman/v26_7/v26_7_eval_cell.sh" "$gpu" "$cell" "$step" "$train_root" "$eval_root"
done
