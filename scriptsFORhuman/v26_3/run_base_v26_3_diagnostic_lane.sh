#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 GPU LANE CHECKPOINT OUTPUT_ROOT [SEED]"
    exit 0
fi
if [[ $# -lt 4 || $# -gt 5 ]]; then exit 2; fi
gpu=$1
lane=$2
checkpoint=$3
output_root=$4
seed=${5:-1}
case "$lane" in
    D0|E1|E2) num_envs=64 ;;
    D3) num_envs=16 ;;
    *) echo "diagnostic lane must be D0/E1/E2/D3" >&2; exit 2 ;;
esac
exec bash /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_3/run_base_v26_3_eval_lane.sh \
    "$gpu" "$lane" "$checkpoint" "$output_root" "$lane" "$seed" "$num_envs" false
