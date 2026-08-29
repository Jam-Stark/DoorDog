#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 ]] || { echo "usage: $0 DIAGNOSTIC_EVAL_ROOT" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
eval_root=$1
for entry in '0 left' '0 right' '1 left' '1 right'; do
  read -r seed side <<<"$entry"
  label="O0A1_DIAG_R2_C0_S${seed}_STEP0750"
  checkpoint="$repo/logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main/C0_CANONICAL_OFF_S${seed}/model_step_000750.pt"
  output="$eval_root/$label/$side"
  [[ -f "$checkpoint" && ! -e "$output" ]] || { echo "diagnostic checkpoint missing or output exists: $output" >&2; exit 1; }
  bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_eval_side.sh" 7 "$label" "$checkpoint" "$eval_root" "$seed" O0A1 "$side"
done
