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
supervisor="$repo/.ai/scripts/run_supervisor.py"
lane="$repo/scriptsFORhuman/v26_2/run_base_v26_2_eval_lane.sh"
run_root="$repo/logs_rl/by_batch/base_v26_2_pull_derived_20260825/wave1"
eval_root="$repo/logs_eval/base_v26/v26_2_pull_derived_20260825/wave1"
log_root="$repo/scriptsFORhuman/v26_2/runtime_logs/wave1_route_a"
mkdir -p "$eval_root" "$log_root"

launch_lane() {
    local gpu=$1 cell=$2
    local name receipt command train_dir
    name="v26_2_wave1_routea_${cell,,}"
    train_dir="$run_root/$cell"
    [[ -f "$train_dir/model_step_000750.pt" ]] || { echo "Wave1 final checkpoint missing: $train_dir" >&2; exit 1; }
    ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session already exists: $name" >&2; exit 1; }
    printf -v command '%q ' bash "$lane" "$gpu" "$cell" "$train_dir" "$eval_root" 1
    receipt=$(python3 "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log_root/$cell.log" --checkpoint "$eval_root/${cell}_STEP0750/right/metrics_eval.json" --resource "GPU$gpu")
    python3 "$supervisor" launch --receipt "$receipt"
}

launch_lane 0 C
launch_lane 1 A
launch_lane 2 R
launch_lane 3 W
