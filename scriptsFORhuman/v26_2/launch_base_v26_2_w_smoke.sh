#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 --launch"
    exit 0
fi
if [[ ${1:-} != --launch || $# -ne 1 ]]; then
    echo "usage: $0 --launch" >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
checkpoint="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
output="$repo/logs_rl/by_batch/base_v26_2_pull_derived_20260825/smoke/V26_2_W_SMOKE"
[[ -f "$checkpoint" ]] || { echo "v26-2 source checkpoint missing: $checkpoint" >&2; exit 1; }
exec bash "$repo/scriptsFORhuman/v26_2/run_base_v26_2_cell.sh" 0 W 0 6 0.25 "$checkpoint" "$output" 1 64 10 10
