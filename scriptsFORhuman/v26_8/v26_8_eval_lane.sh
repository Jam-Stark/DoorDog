#!/usr/bin/env bash
# One GPU-owned serial lane; each cell produces exact64 LEFT and RIGHT outputs.
set -euo pipefail
[[ $# -ge 5 ]] || { echo "usage: $0 GPU STEP TRAIN_ROOT EVAL_ROOT CELL [CELL ...]" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
gpu=$1; step=$2; train_root=$3; eval_root=$4; shift 4
[[ "$gpu" =~ ^[01]$ && "$step" =~ ^(500|1000|1500|2000|2500|3000)$ ]] || exit 2
for cell in "$@"; do
  bash "$repo/scriptsFORhuman/v26_8/v26_8_eval_cell.sh" "$gpu" "$cell" "$step" "$train_root" "$eval_root"
done
