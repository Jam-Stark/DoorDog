#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 6 ]] || { echo "usage: $0 GPU R13_S0|R13_S1 125|250 CHECKPOINT OUTPUT_ROOT SEED" >&2; exit 2; }
gpu=$1;cell=$2;step=$3;checkpoint=$4;root=$5;seed=$6
[[ "$cell" =~ ^R13_S[01]$ && "$step" =~ ^(125|250)$ ]] || exit 2
label="${cell}_STEP0${step}"
for side in left right;do bash "$(dirname "$0")/v26_5_wave2_r1_r13_eval_side.sh" "$gpu" "$label" "$checkpoint" "$root" "$seed" "$side";done
