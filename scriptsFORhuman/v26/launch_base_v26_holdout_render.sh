#!/usr/bin/env bash
set -euo pipefail

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
checkpoint="$repo/logs_rl/by_batch/base_v26_r0_20260821/V26_LR_S1/model_step_004000.pt"
runner="$repo/scriptsFORhuman/v26/run_base_v26_side_eval.sh"
log_root="$repo/scriptsFORhuman/v26/runtime_logs/final_eval"
holdout_root="$repo/logs_eval/base_v26/holdout_20260822"
render_root="$repo/logs_eval/base_v26/render_20260822"

mkdir -p "$log_root" "$holdout_root" "$render_root"

tmux new-session -d -s v26_holdout_lr_s1_step4000 \
    "bash -lc 'bash $runner 0 LR_S1_STEP4000_HOLDOUT $checkpoint $holdout_root 128 260823 false >$log_root/holdout.log 2>&1; status=\$?; echo V26_HOLDOUT_EXIT_CODE=\$status >>$log_root/holdout.log; exit \$status'"

tmux new-session -d -s v26_render_lr_s1_step4000 \
    "bash -lc 'bash $runner 0 LR_S1_STEP4000_RENDER $checkpoint $render_root 1 260824 true 1 >$log_root/render.log 2>&1; status=\$?; echo V26_RENDER_EXIT_CODE=\$status >>$log_root/render.log; exit \$status'"
