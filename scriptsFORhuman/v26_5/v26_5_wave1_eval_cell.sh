#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 6 ]] || { echo "usage: $0 GPU LABEL CHECKPOINT OUTPUT_ROOT SEED O1A0|O1A1" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
for side in left right; do
  bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_eval_side.sh" "$1" "$2" "$3" "$4" "$5" "$6" "$side"
done
