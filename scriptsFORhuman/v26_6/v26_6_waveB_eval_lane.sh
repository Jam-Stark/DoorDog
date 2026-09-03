#!/usr/bin/env bash
# v26-6 Wave B evaluation lane: one GPU owns one training cell and runs its
# three checkpoints (250/500/750) serially.  Each step evaluates LEFT then
# RIGHT exact64 through v26_6_waveB_eval_cell.sh, so one lane produces 6 of the
# 24 preregistered evaluations.
set -euo pipefail
[[ $# -eq 4 ]] || { echo "usage: $0 GPU CELL TRAIN_ROOT OUTPUT_ROOT   (CELL = B0_S0|B0_S1|B1_S0|B1_S1)" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
gpu=$1; cell=$2; train_root=$3; output_root=$4

[[ "$gpu" =~ ^[4567]$ ]] || { echo "Wave B evaluation is bound to physical GPU4..7" >&2; exit 2; }
[[ "$cell" =~ ^B[01]_S[01]$ ]] || { echo "registered cells are B0_S0 B0_S1 B1_S0 B1_S1" >&2; exit 2; }
[[ -d "$train_root/$cell" ]] || { echo "missing training cell: $train_root/$cell" >&2; exit 2; }

for step in 250 500 750; do
  echo "=== lane gpu$gpu cell=$cell step=$step ==="
  bash "$repo/scriptsFORhuman/v26_6/v26_6_waveB_eval_cell.sh" \
    "$gpu" "$cell" "$step" "$train_root" "$output_root"
done

for step in 250 500 750; do
  for side in left right; do
    trace="$output_root/${cell}_STEP0${step}/${side}/stage2_5_step_trace.json"
    [[ -f "$trace" ]] || { echo "missing lane artifact: $trace" >&2; exit 1; }
  done
done
