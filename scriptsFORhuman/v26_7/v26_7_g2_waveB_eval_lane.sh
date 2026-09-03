#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 5 ]] || { echo "usage: $0 GPU TRAIN_ROOT OUTPUT_ROOT CELL [CELL ...]" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
gpu=$1; train_root=$2; output_root=$3; shift 3
[[ "$gpu" =~ ^[01]$ ]] || exit 2
for cell in "$@"; do
  [[ "$cell" =~ ^B[01]_S[01]$ ]] || exit 2
  for step in 250 500 750; do
    bash "$repo/scriptsFORhuman/v26_7/v26_7_g2_waveB_eval_cell.sh" "$gpu" "$cell" "$step" "$train_root" "$output_root"
  done
done
