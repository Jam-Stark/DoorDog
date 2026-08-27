#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 5 ]]; then
    echo "usage: $0 GPU OUTPUT_ROOT NUM_ENVS SEED LABEL=CHECKPOINT [...]" >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
gpu=$1
output_root=$2
num_envs=$3
seed=$4
shift 4

for spec in "$@"; do
    label=${spec%%=*}
    checkpoint=${spec#*=}
    if [[ "$label" == "$spec" || -z "$label" || -z "$checkpoint" ]]; then
        echo "invalid candidate spec: $spec" >&2
        exit 2
    fi
    bash "$repo/scriptsFORhuman/v26/run_base_v26_side_eval.sh" \
        "$gpu" "$label" "$checkpoint" "$output_root" "$num_envs" "$seed"
done
