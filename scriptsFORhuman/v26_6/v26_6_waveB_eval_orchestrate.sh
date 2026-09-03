#!/usr/bin/env bash
# v26-6 Wave B evaluation orchestrator.
#
#   launch    prepare + launch the four tmux-backed lane receipts (GPU4..7)
#   status    report run_supervisor status for the four lanes
#   finalize  finalize the four lane receipts
#   reduce    run the preregistered reducer over the fixed eval root
#
# The eval output root and the receipt namespace are fixed here so that the
# reducer path is not reconstructed by hand.
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: $0 {launch|status|finalize|reduce}" >&2; exit 2; }
action=$1
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"

plan_id=v26_6_waveB_gripper_capability_20260831
train_root="$repo/logs_rl/by_batch/base_v26/$plan_id/train"
eval_root="$repo/logs_eval/base_v26/$plan_id"
log_dir="$repo/scriptsFORhuman/v26_6/runtime_logs/waveB"
reducer_out="$eval_root/reducer.json"

cells=(B0_S0 B0_S1 B1_S0 B1_S1)
gpus=(4 5 6 7)

receipt_for() { echo "$repo/.ai/runtime/runs/v26_6_waveB_eval_${1,,}/RUN_RECEIPT.json"; }

case "$action" in
  launch)
    [[ ! -e "$eval_root" ]] || { echo "refusing to reuse existing eval root: $eval_root" >&2; exit 1; }
    mkdir -p "$log_dir"
    for i in "${!cells[@]}"; do
      cell=${cells[$i]}; gpu=${gpus[$i]}; name="v26_6_waveB_eval_${cell,,}"
      "$py" "$supervisor" prepare \
        --name "$name" \
        --session "$name" \
        --command "bash $repo/scriptsFORhuman/v26_6/v26_6_waveB_eval_lane.sh $gpu $cell $train_root $eval_root" \
        --cwd "$repo" \
        --output "$log_dir/eval_${cell}.log" \
        --resource "gpu$gpu"
      "$py" "$supervisor" launch --receipt "$(receipt_for "$cell")"
    done
    ;;
  status|finalize)
    for cell in "${cells[@]}"; do
      receipt=$(receipt_for "$cell")
      printf '%-8s ' "$cell"
      if [[ ! -f "$receipt" ]]; then
        echo "NOT_LAUNCHED"
        continue
      fi
      "$py" "$supervisor" "$action" --receipt "$receipt" 2>&1 | tr '\n' ' '
      echo
    done
    ;;
  reduce)
    "$py" "$repo/scriptsFORhuman/v26_6/v26_6_waveB_reduce.py" \
      --train-root "$train_root" --eval-root "$eval_root" --output "$reducer_out"
    ;;
  *)
    echo "unknown action: $action" >&2; exit 2
    ;;
esac
