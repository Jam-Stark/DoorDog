#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "usage: $0 FULL_S0_CHECKPOINT FULL_S0_LABEL FULL_S1_CHECKPOINT FULL_S1_LABEL" >&2
    exit 2
fi

repo_root=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
g7_checkpoint="$repo_root/logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
eval_root="$repo_root/logs_eval/base_v25/m3/teacher_comparison"
s0_checkpoint=$1
s0_label=$2
s1_checkpoint=$3
s1_label=$4

mkdir -p "$eval_root/launch_logs"

launch_candidate() {
    local session=$1
    local gpu=$2
    local label=$3
    local checkpoint=$4
    local log_path="$eval_root/launch_logs/$label.log"

    tmux new-session -d -s "$session" -c "$repo_root" \
        "bash scriptsFORhuman/v25/run_teacher_candidate_sides.sh $gpu $label $checkpoint > $log_path 2>&1"
}

launch_candidate v25-teacher-g7 0 G7_STEP1500 "$g7_checkpoint"
launch_candidate v25-teacher-full-s0 1 "$s0_label" "$s0_checkpoint"
launch_candidate v25-teacher-full-s1 2 "$s1_label" "$s1_checkpoint"
