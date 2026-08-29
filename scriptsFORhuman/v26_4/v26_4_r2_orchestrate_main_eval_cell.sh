#!/usr/bin/env bash
set -euo pipefail
usage() { echo "usage: $0 GPU C[01]_CANONICAL_(OFF|ON)_S[01] R2_TRAIN_DIR R2_EVAL_ROOT SEED SEAM"; }
[[ ${1:-} == --help || ${1:-} == -h ]] && { usage; exit 0; }
[[ $# -eq 6 ]] || { usage >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
gpu=$1; cell=$2; train=$3; eval_root=$4; seed=$5; seam=$6
[[ "$cell" =~ ^(C0_CANONICAL_OFF|C1_CANONICAL_ON)_S([01])$ && "${BASH_REMATCH[2]}" == "$seed" ]] || { usage >&2; exit 2; }
for step in 125 250 500 750; do
  printf -v padded '%04d' "$step"
  bash "$repo/scriptsFORhuman/v26_4/v26_4_r2_orchestrate_eval_lane.sh" "$gpu" "${cell}_STEP${padded}" "$train/model_step_$(printf '%06d' "$step").pt" "$eval_root" "$seed" "$seam"
done
