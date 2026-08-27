#!/usr/bin/env bash
set -euo pipefail

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
run_root="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/formal"
eval_root="$repo/logs_eval/base_v26/acquisition_supplement_20260823/route_a"
log_root="$repo/scriptsFORhuman/v26/runtime_logs/acquisition_supplement_route_a"
summary="$repo/logs_eval/base_v26/acquisition_supplement_20260823/route_a_summary.json"

scratch_sessions=(v26a_lr_s0 v26a_lr_s1 v26a_l_s0 v26a_r_s0)
scratch_checkpoints=(
    "$run_root/V26A_LR_S0/model_step_004000.pt"
    "$run_root/V26A_LR_S1/model_step_004000.pt"
    "$run_root/V26A_L_S0/model_step_004000.pt"
    "$run_root/V26A_R_S0/model_step_004000.pt"
)
route_sessions=(
    v26a_routea_lr_s0
    v26a_routea_lr_s1
    v26a_routea_l_s0
    v26a_routea_r_s0
)

while true; do
    pending=false
    for index in "${!scratch_sessions[@]}"; do
        session=${scratch_sessions[$index]}
        checkpoint=${scratch_checkpoints[$index]}
        if [[ -f "$checkpoint" ]]; then
            continue
        fi
        if ! tmux has-session -t "$session" 2>/dev/null; then
            echo "scratch session stopped before final checkpoint: $session" >&2
            exit 1
        fi
        pending=true
    done
    if [[ "$pending" == false ]]; then
        break
    fi
    sleep 600
done

for session in "${scratch_sessions[@]}"; do
    while tmux has-session -t "$session" 2>/dev/null; do
        sleep 30
    done
done

bash "$repo/scriptsFORhuman/v26/launch_base_v26_acquisition_route_a.sh"

while true; do
    running=false
    for session in "${route_sessions[@]}"; do
        if tmux has-session -t "$session" 2>/dev/null; then
            running=true
        fi
    done
    if [[ "$running" == false ]]; then
        break
    fi
    sleep 600
done

for session in "${route_sessions[@]}"; do
    log_path="$log_root/$session.log"
    if ! grep -q '^V26_ACQ_ROUTE_A_EXIT_CODE=0$' "$log_path"; then
        echo "Route A lane did not exit cleanly: $session" >&2
        exit 1
    fi
done

python3 "$repo/scriptsFORhuman/v26/summarize_v26_evaluations.py" \
    --suite "acquisition_route_a=$eval_root" \
    --output "$summary"

echo "V26_ACQUISITION_ROUTE_A_COMPLETE=$summary"
