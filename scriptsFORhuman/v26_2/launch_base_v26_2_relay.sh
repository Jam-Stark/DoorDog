#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 --launch SELECTED_W_WAVE1_CHECKPOINT"
    exit 0
fi
if [[ ${1:-} != --launch || $# -ne 2 ]]; then
    echo "usage: $0 --launch SELECTED_W_WAVE1_CHECKPOINT" >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
supervisor="$repo/.ai/scripts/run_supervisor.py"
runner="$repo/scriptsFORhuman/v26_2/run_base_v26_2_cell.sh"
checkpoint=$2
run_root="$repo/logs_rl/by_batch/base_v26_2_pull_derived_20260825/relay"
log_root="$repo/scriptsFORhuman/v26_2/runtime_logs/relay"
analysis="$repo/logs_eval/base_v26/v26_2_pull_derived_20260825/wave1_mechanism.json"

[[ -f "$checkpoint" && -f "$analysis" ]] || { echo "relay requires a selected W checkpoint and Wave1 analysis" >&2; exit 1; }
python3 - "$analysis" "$checkpoint" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
if payload.get("outcome", {}).get("relay_allowed") is not True:
    raise SystemExit("Wave1 did not admit relay")
if "/wave1/W/" not in sys.argv[2] or not sys.argv[2].endswith(("model_step_000250.pt", "model_step_000500.pt", "model_step_000750.pt")):
    raise SystemExit("relay parent must be a registered Wave1 W checkpoint")
PY
mkdir -p "$run_root" "$log_root"

launch_cell() {
    local gpu=$1 cell=$2 seed=$3
    local output name receipt command
    output="$run_root/$cell"
    name="v26_2_relay_${cell,,}"
    [[ ! -e "$output" ]] || { echo "output already exists: $output" >&2; exit 1; }
    ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session already exists: $name" >&2; exit 1; }
    printf -v command '%q ' bash "$runner" "$gpu" "$cell" 0 6 0.25 "$checkpoint" "$output" "$seed" 4096 750 250
    receipt=$(python3 "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log_root/$cell.log" --checkpoint "$output/model_step_000750.pt" --resource "GPU$gpu" --resource "parent=$checkpoint")
    python3 "$supervisor" launch --receipt "$receipt"
}

launch_cell 0 W_RELAY_S0 0
launch_cell 1 W_RELAY_S1 1
