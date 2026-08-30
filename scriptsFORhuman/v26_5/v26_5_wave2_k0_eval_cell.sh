#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 4 ]] || { echo "usage: $0 GPU LABEL OUTPUT_ROOT SEED" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
for side in left right; do
  bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_k0_eval_side.sh" "$1" "$2" "$3" "$4" "$side"
done
