#!/usr/bin/env bash
set -euo pipefail

# This proof sources the cell script while shadowing its `bash` command.  It
# verifies the cell-to-side argv contract without executing the side script or
# allocating Isaac/GPU resources.
root=/home/baoquanc/workspace/DoorDog-A2_Piper
cell="$root/scriptsFORhuman/v26_5/v26_5_wave2_r1_k1_cell.sh"
side_script="$root/scriptsFORhuman/v26_5/v26_5_wave2_r1_k1_eval_side.sh"
calls=0

bash() {
  calls=$((calls + 1))
  [[ $# -eq 7 ]] || { echo "cell must invoke bash with side path plus six argv values" >&2; return 1; }
  [[ ${1##*/} == "${side_script##*/}" && $2 == 4 && $4 == K1_S0 && $5 == /tmp/v26_5_r1_interface && $6 == 0 ]] || {
    echo "cell forwarded an unexpected fixed argv value" >&2; return 1
  }
  case "$calls" in
    1) [[ $3 == control && $7 == left ]] ;;
    2) [[ $3 == dual && $7 == left ]] ;;
    3) [[ $3 == control && $7 == right ]] ;;
    4) [[ $3 == dual && $7 == right ]] ;;
    *) echo "unexpected extra cell->side invocation" >&2; return 1 ;;
  esac
}

set -- 4 K1_S0 /tmp/v26_5_r1_interface 0
source "$cell"
[[ $calls -eq 4 ]] || { echo "expected four cell->side calls, got $calls" >&2; exit 1; }
grep -Fq "trace_reward_terms='[push_door_handle,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]'" "$side_script"
grep -Fq "trace_reward_terms='[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]'" "$side_script"
grep -Fq '++algo.config.eval.a2_diagnostic_reward_terms="$trace_reward_terms"' "$side_script"
grep -Fq 'handle_depression_scale=0.0' "$side_script"
grep -Fq 'handle_creation_scale=0.0' "$side_script"
grep -Fq 'handle_creation_scale=6.0' "$side_script"
grep -Fq '++env.config.a2_v26_2_handle_depression_scale="$handle_depression_scale" ++env.config.a2_v26_3_handle_creation_scale="$handle_creation_scale"' "$side_script"
echo K1_CELL_INTERFACE_PASS
