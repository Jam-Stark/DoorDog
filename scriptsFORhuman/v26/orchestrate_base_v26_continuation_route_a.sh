#!/usr/bin/env bash
set -euo pipefail

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
run_root="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800"
final_checkpoint="$run_root/model_step_003000.pt"
eval_root="$repo/logs_eval/base_v26/acquisition_supplement_20260823/continuation_route_a"
log_root="$repo/scriptsFORhuman/v26/runtime_logs/continuation_route_a"
summary="$repo/logs_eval/base_v26/acquisition_supplement_20260823/continuation_route_a_summary.json"
training_session=v26a_policy800
route_sessions=(v26a_cont_routea_0 v26a_cont_routea_1 v26a_cont_routea_2 v26a_cont_routea_3)

while [[ ! -f "$final_checkpoint" ]]; do
    if ! tmux has-session -t "$training_session" 2>/dev/null; then
        echo "continuation stopped before final checkpoint: $training_session" >&2
        exit 1
    fi
    sleep 600
done

while tmux has-session -t "$training_session" 2>/dev/null; do
    sleep 30
done

bash "$repo/scriptsFORhuman/v26/launch_base_v26_continuation_route_a.sh"

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
    if ! grep -q '^V26_CONT_ROUTE_A_EXIT_CODE=0$' "$log_path"; then
        echo "continuation Route A lane did not exit cleanly: $session" >&2
        exit 1
    fi
done

python3 "$repo/scriptsFORhuman/v26/summarize_v26_evaluations.py" \
    --suite "continuation_route_a=$eval_root" \
    --output "$summary"

echo "V26_CONTINUATION_ROUTE_A_COMPLETE=$summary"
