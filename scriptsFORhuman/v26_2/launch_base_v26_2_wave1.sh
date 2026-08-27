#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage: launch_base_v26_2_wave1.sh --launch

Launches the registered C/A/R/W Wave1 matrix through one tmux-backed
run_supervisor receipt per physical GPU.  No work is started without --launch.
EOF
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
if [[ ${1:-} != --launch || $# -ne 1 ]]; then usage >&2; exit 2; fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
supervisor="$repo/.ai/scripts/run_supervisor.py"
runner="$repo/scriptsFORhuman/v26_2/run_base_v26_2_cell.sh"
source_checkpoint="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
run_root="$repo/logs_rl/by_batch/base_v26_2_pull_derived_20260825/wave1"
log_root="$repo/scriptsFORhuman/v26_2/runtime_logs/wave1"

if [[ ! -f "$source_checkpoint" ]]; then echo "v26-2 source checkpoint missing: $source_checkpoint" >&2; exit 1; fi
mkdir -p "$run_root" "$log_root"

gpu_idle() {
    local index=$1 uuid
    uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F ', ' -v target="$index" '$1 == target { print $2 }')
    [[ -n "$uuid" ]] || { echo "GPU$index is not visible to nvidia-smi" >&2; return 1; }
    if nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep -Fq "$uuid"; then
        echo "GPU$index already has a compute process; preserve its lease and retry later" >&2
        return 1
    fi
}
for gpu in 0 1 2 3; do gpu_idle "$gpu"; done

launch_cell() {
    local gpu=$1 cell=$2 raw=$3 depression=$4 threshold=$5
    local output name session receipt log command
    output="$run_root/$cell"
    name="v26_2_wave1_${cell,,}"
    session="$name"
    [[ ! -e "$output" ]] || { echo "output already exists: $output" >&2; exit 1; }
    ! tmux has-session -t "$session" 2>/dev/null || { echo "tmux session already exists: $session" >&2; exit 1; }
    printf -v command '%q ' bash "$runner" "$gpu" "$cell" "$raw" "$depression" "$threshold" "$source_checkpoint" "$output" 1 4096 750 250
    receipt=$(python3 "$supervisor" prepare --name "$name" --session "$session" --cwd "$repo" --command "$command" --output "$log_root/$cell.log" --checkpoint "$output/model_step_000750.pt" --resource "GPU$gpu")
    python3 "$supervisor" launch --receipt "$receipt"
}

launch_cell 0 C 6 0 0.1
launch_cell 1 A 0 0 0.1
launch_cell 2 R 0 6 0.1
launch_cell 3 W 0 6 0.25
