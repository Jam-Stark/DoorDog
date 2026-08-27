#!/usr/bin/env bash
set -euo pipefail

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
run_root="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800"
eval_root="$repo/logs_eval/base_v26/acquisition_supplement_20260823/continuation_route_a"
log_root="$repo/scriptsFORhuman/v26/runtime_logs/continuation_route_a"
lane="$repo/scriptsFORhuman/v26/run_base_v26_route_a_lane.sh"

mkdir -p "$eval_root" "$log_root"

launch_lane() {
    local session=$1
    local gpu=$2
    shift 2
    local log_path="$log_root/$session.log"

    tmux new-session -d -s "$session" \
        "bash -lc 'bash $lane $gpu $eval_root 64 260824 $* >$log_path 2>&1; status=\$?; echo V26_CONT_ROUTE_A_EXIT_CODE=\$status >>$log_path; exit \$status'"
}

launch_lane v26a_cont_routea_0 0 \
    "CONT_STEP0250=$run_root/model_step_000250.pt" \
    "CONT_STEP2000=$run_root/model_step_002000.pt"

launch_lane v26a_cont_routea_1 1 \
    "CONT_STEP0500=$run_root/model_step_000500.pt" \
    "CONT_STEP2500=$run_root/model_step_002500.pt"

launch_lane v26a_cont_routea_2 2 \
    "CONT_STEP1000=$run_root/model_step_001000.pt" \
    "CONT_STEP3000=$run_root/model_step_003000.pt"

launch_lane v26a_cont_routea_3 3 \
    "CONT_STEP1500=$run_root/model_step_001500.pt"
