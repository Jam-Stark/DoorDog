#!/usr/bin/env bash
set -euo pipefail
[[ ${1:-} == 0 && $# -eq 1 ]] || { echo "usage: $0 0" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
out=$repo/logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/K
if [[ -e "$out" ]] && [[ -n $(find "$out" -mindepth 1 -maxdepth 1 ! -name supervisor.log ! -name r2_k.log ! -name '*_failed_*' -print -quit) ]]; then
  echo "refusing existing R2 K output: $out" >&2; exit 2
fi
mkdir -p "$out"
env CUDA_VISIBLE_DEVICES=0 CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 PYTHONPATH="$repo" PYTHONUNBUFFERED=1 \
  /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B "$repo/scriptsFORhuman/v26_4/v26_4_r2_k_kinematics_probe.py" --device cuda:0 --output-root "$out" 2>&1 | tee "$out/r2_k.log"
