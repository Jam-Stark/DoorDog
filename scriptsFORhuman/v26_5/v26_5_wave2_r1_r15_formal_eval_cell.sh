#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 6 ]] || exit 2
gpu=$1;cell=$2;step=$3;checkpoint=$4;root=$5;seed=$6;[[ "$step" =~ ^(125|250)$ ]]||exit 2
for side in left right;do bash "$(dirname "$0")/v26_5_wave2_r1_r15_formal_eval_side.sh" "$gpu" "${cell}_STEP0${step}" "$checkpoint" "$root" "$seed" "$side";done
