#!/usr/bin/env bash
set -euo pipefail

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
run_root="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/formal"
eval_root="$repo/logs_eval/base_v26/acquisition_supplement_20260823/route_a"
log_root="$repo/scriptsFORhuman/v26/runtime_logs/acquisition_supplement_route_a"
lane="$repo/scriptsFORhuman/v26/run_base_v26_route_a_lane.sh"

mkdir -p "$eval_root" "$log_root"

launch_lane() {
    local session=$1
    local gpu=$2
    shift 2
    local log_path="$log_root/$session.log"

    tmux new-session -d -s "$session" \
        "bash -lc 'bash $lane $gpu $eval_root 64 260823 $* >$log_path 2>&1; status=\$?; echo V26_ACQ_ROUTE_A_EXIT_CODE=\$status >>$log_path; exit \$status'"
}

launch_lane v26a_routea_lr_s0 0 \
    "LR_S0_STEP1000=$run_root/V26A_LR_S0/model_step_001000.pt" \
    "LR_S0_STEP2000=$run_root/V26A_LR_S0/model_step_002000.pt" \
    "LR_S0_STEP3000=$run_root/V26A_LR_S0/model_step_003000.pt" \
    "LR_S0_STEP4000=$run_root/V26A_LR_S0/model_step_004000.pt"

launch_lane v26a_routea_lr_s1 1 \
    "LR_S1_STEP0250=$run_root/V26A_LR_S1/model_step_000250.pt" \
    "LR_S1_STEP1000=$run_root/V26A_LR_S1/model_step_001000.pt" \
    "LR_S1_STEP2000=$run_root/V26A_LR_S1/model_step_002000.pt" \
    "LR_S1_STEP3000=$run_root/V26A_LR_S1/model_step_003000.pt" \
    "LR_S1_STEP4000=$run_root/V26A_LR_S1/model_step_004000.pt"

launch_lane v26a_routea_l_s0 2 \
    "L_S0_STEP1000=$run_root/V26A_L_S0/model_step_001000.pt" \
    "L_S0_STEP2000=$run_root/V26A_L_S0/model_step_002000.pt" \
    "L_S0_STEP3000=$run_root/V26A_L_S0/model_step_003000.pt" \
    "L_S0_STEP4000=$run_root/V26A_L_S0/model_step_004000.pt"

launch_lane v26a_routea_r_s0 3 \
    "R_S0_STEP1000=$run_root/V26A_R_S0/model_step_001000.pt" \
    "R_S0_STEP2000=$run_root/V26A_R_S0/model_step_002000.pt" \
    "R_S0_STEP3000=$run_root/V26A_R_S0/model_step_003000.pt" \
    "R_S0_STEP4000=$run_root/V26A_R_S0/model_step_004000.pt"
