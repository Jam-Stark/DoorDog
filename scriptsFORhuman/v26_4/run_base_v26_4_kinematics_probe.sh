#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 GPU [OUTPUT_JSON]"
    exit 0
fi
if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "usage: $0 GPU [OUTPUT_JSON]" >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
output=${2:-$repo/logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/K/k_kinematics.json}

[[ "$gpu" == 0 ]] || { echo "Wave K requires its leased physical GPU0" >&2; exit 2; }
[[ -x "$python_bin" ]] || { echo "IsaacLab Python is unavailable: $python_bin" >&2; exit 1; }
[[ ! -e "$output" ]] || { echo "refusing to overwrite K evidence: $output" >&2; exit 2; }

mkdir -p "$(dirname "$output")"
log="$(dirname "$output")/kinematics.log"

set +e
env CUDA_VISIBLE_DEVICES=0 \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    ACCELERATE_TORCH_DEVICE=cuda:0 \
    HYDRA_FULL_ERROR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="$repo" \
    "$python_bin" -B "$repo/scriptsFORhuman/v26_4/v26_4_k_kinematics_probe.py" \
        --device cuda:0 --output "$output" 2>&1 | tee "$log"
probe_status=${PIPESTATUS[0]}
set -e
[[ "$probe_status" -eq 0 ]] || exit "$probe_status"
[[ -f "$output" ]] || { echo "probe exited without K evidence: $output" >&2; exit 1; }
