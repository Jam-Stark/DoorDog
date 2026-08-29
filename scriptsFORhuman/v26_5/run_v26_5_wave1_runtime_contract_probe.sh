#!/usr/bin/env bash
set -euo pipefail
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
root="$repo/logs_eval/base_v26/v26_5_wave1_stage5_20260830_r1/K"
cases="$root/runtime_contract_cases_attempt3"
[[ ! -e "$root/runtime_contract.json" && ! -e "$cases" ]] || { echo "runtime contract evidence already exists" >&2; exit 1; }
mkdir -p "$cases"
for factor in O0 O1; do
  for side in left right; do
    output="$cases/${factor}_${side}.json"
    env CUDA_VISIBLE_DEVICES=2 CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONPATH="$repo" "$python_bin" -B "$repo/scriptsFORhuman/v26_5/v26_5_wave1_runtime_contract_case.py" --device cuda:0 --headless --factor "$factor" --side "$side" --output "$output"
    [[ -s "$output" ]] || { echo "runtime contract case returned without receipt: factor=$factor side=$side output=$output" >&2; exit 1; }
  done
done
exec /usr/bin/python3 "$repo/scriptsFORhuman/v26_5/v26_5_wave1_runtime_contract_reduce.py" --case-root "$cases" --output "$root/runtime_contract.json"
