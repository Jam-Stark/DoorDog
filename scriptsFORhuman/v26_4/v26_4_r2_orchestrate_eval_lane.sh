#!/usr/bin/env bash
set -euo pipefail
usage() { echo "usage: $0 GPU C[01]_CANONICAL_(OFF|ON)_S[01]_STEP(0125|0250|0500|0750) R2_CHECKPOINT R2_EVAL_ROOT SEED SEAM"; }
[[ ${1:-} == --help || ${1:-} == -h ]] && { usage; exit 0; }
[[ $# -eq 6 ]] || { usage >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
train_root="$repo/logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main"
eval_root="$repo/logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/eval"
gpu=$1; label=$2; checkpoint=$3; output=$4; seed=$5; seam=$6
[[ "$gpu" =~ ^[0-3]$ && "$seed" =~ ^[01]$ && "$output" == "$eval_root" ]] || { usage >&2; exit 2; }
if [[ ! "$label" =~ ^(C0_CANONICAL_OFF|C1_CANONICAL_ON)_S([01])_STEP(0125|0250|0500|0750)$ ]]; then usage >&2; exit 2; fi
cell=${BASH_REMATCH[1]}; label_seed=${BASH_REMATCH[2]}; step=${BASH_REMATCH[3]}
[[ "$label_seed" == "$seed" && "$checkpoint" == "$train_root/${cell}_S${seed}/model_step_00${step}.pt" ]] || { echo "checkpoint/label is not an exact R2 registered checkpoint" >&2; exit 2; }
[[ ! -e "$output/$label" && -f "$checkpoint" ]] || { echo "R2 eval output exists or checkpoint missing" >&2; exit 1; }
case "$cell:$seam" in
  C0_CANONICAL_OFF:++env.config.a2_v26_4_side_canonicalization_enabled=false|C1_CANONICAL_ON:++env.config.a2_v26_4_side_canonicalization_enabled=true) ;;
  *) echo "cell/seam mismatch" >&2; exit 2 ;;
esac
exec bash "$repo/scriptsFORhuman/v26_4/run_base_v26_4_eval_lane.sh" "$gpu" "$label" "$checkpoint" "$output" "$seed" "$seam"
