#!/usr/bin/env bash
set -euo pipefail
usage() { echo "usage: $0 GPU C0_CANONICAL_OFF|C1_CANONICAL_ON R2_OUTPUT_DIR SEED ++env.config.a2_v26_4_side_canonicalization_enabled=true|false"; }
[[ ${1:-} == --help || ${1:-} == -h ]] && { usage; exit 0; }
[[ $# -eq 5 ]] || { usage >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
train_root="$repo/logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main"
source_checkpoint="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
gpu=$1; cell=$2; output=$3; seed=$4; seam=$5
[[ "$gpu" =~ ^[0-3]$ && "$seed" =~ ^[01]$ ]] || { usage >&2; exit 2; }
[[ "$output" == "$train_root/${cell}_S${seed}" ]] || { echo "R2 train output must be the exact registered cell root" >&2; exit 2; }
[[ ! -e "$output" && -f "$source_checkpoint" ]] || { echo "R2 train root already exists or source checkpoint missing" >&2; exit 1; }
case "$cell:$seam" in
  C0_CANONICAL_OFF:++env.config.a2_v26_4_side_canonicalization_enabled=false|C1_CANONICAL_ON:++env.config.a2_v26_4_side_canonicalization_enabled=true) ;;
  *) echo "cell/seam mismatch" >&2; exit 2 ;;
esac
exec bash "$repo/scriptsFORhuman/v26_4/run_base_v26_4_train_cell.sh" "$gpu" "$cell" "$source_checkpoint" "$output" "$seed" "$seam"
