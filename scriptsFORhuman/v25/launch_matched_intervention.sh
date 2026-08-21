#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: $0 CHECKPOINT LABEL" >&2
    exit 2
fi

repo_root=/home/baoquanc/workspace/DoorDog-A2_Piper
checkpoint=$1
label=$2
eval_root="$repo_root/logs_eval/base_v25/causality/$label"

mkdir -p "$eval_root/launch_logs"

launch_branch() {
    local session=$1
    local gpu=$2
    local branch=$3
    local log_path="$eval_root/launch_logs/$branch.log"

    tmux new-session -d -s "$session" -c "$repo_root" \
        "bash scriptsFORhuman/v25/run_matched_intervention_branch.sh $gpu $branch $checkpoint $label > $log_path 2>&1"
}

launch_branch v25-int-p1-m1 0 P1_M1
launch_branch v25-int-p0-m1 1 P0_M1
launch_branch v25-int-p1-m0 2 P1_M0
launch_branch v25-int-p0-m0 3 P0_M0
