#!/usr/bin/env bash
# v26-7 frozen operation entrypoint.  It creates one tmux-backed receipt per
# long worker and refuses to pass either preregistered gate implicitly.
set -euo pipefail

usage() {
  cat <<'EOF'
usage:
  v26_7_orchestrate.sh static
  v26_7_orchestrate.sh g1-launch | g1-finalize
  v26_7_orchestrate.sh g2-launch | g2-finalize
  v26_7_orchestrate.sh train-launch
  v26_7_orchestrate.sh milestone-launch 1000|2000|3000|4000|5000|6000
  v26_7_orchestrate.sh milestone-finalize 1000|2000|3000|4000|5000|6000
EOF
}

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/usr/bin/python3
isaac_py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"
run_id=v26_7_bilateral_native_unlatch_20260902
train_root="$repo/logs_rl/by_batch/base_v26/$run_id/train"
eval_root="$repo/logs_eval/base_v26/$run_id"
runtime_logs="$repo/scriptsFORhuman/v26_7/runtime_logs/$run_id"
g1_root="$eval_root/G1_wiring"
g2_root="$eval_root/G2_waveB_baseline"
g2_train_root="$repo/logs_rl/by_batch/base_v26/v26_6_waveB_gripper_capability_20260831/train"
cells=(Q05_S0 Q05_S1 Q05_S2 Q20_S0 Q20_S1 Q20_S2)

receipt() { echo "$repo/.ai/runtime/runs/$1/RUN_RECEIPT.json"; }
gpu_idle() {
  local gpu=$1 uuid
  uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F ', ' -v gpu_index="$gpu" '$1 == gpu_index { print $2 }')
  [[ -n "$uuid" ]] || { echo "GPU$gpu is not visible" >&2; return 1; }
  ! nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep -Fq "$uuid" || { echo "GPU$gpu is busy" >&2; return 1; }
}
launch() {
  local name=$1 gpu=$2 command=$3 log=$4 expected=$5
  ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session exists: $name" >&2; exit 1; }
  local created
  created=$("$py" "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log" --checkpoint "$expected" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu")
  "$py" "$supervisor" launch --receipt "$created"
}
require_receipt_pass() {
  "$py" - "$(receipt "$1")" <<'PY'
import json,sys
path=sys.argv[1]; value=json.load(open(path, encoding="utf-8"))
if value.get("state") != "PASS" or value.get("process_returncode") != 0:
    raise SystemExit(f"receipt is not PASS/0: {path}")
PY
}
require_gate() {
  "$py" - "$1" "$2" <<'PY'
import json,sys
path,want=sys.argv[1:]; value=json.load(open(path, encoding="utf-8"))
if value.get("status") != want: raise SystemExit(f"gate {path} is {value.get('status')!r}, expected {want!r}")
PY
}
valid_step() { [[ "$1" =~ ^(1000|2000|3000|4000|5000|6000)$ ]]; }
active_cells_for_step() {
  "$isaac_py" "$repo/scriptsFORhuman/v26_7/v26_7_active_cells.py" --milestones-root "$eval_root/milestones" --next-step "$1"
}
read_active_cells() {
  local state=$1
  "$py" - "$state" <<'PY'
import json,sys
for cell in json.loads(sys.argv[1])["active_cells"]:
    print(cell)
PY
}
state_has_no_active() {
  "$py" - "$1" <<'PY'
import json,sys
print("true" if not json.loads(sys.argv[1])["active_cells"] else "false")
PY
}

case ${1:-} in
  static)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    exec "$isaac_py" "$repo/scriptsFORhuman/v26_7/v26_7_verify.py"
    ;;
  g1-launch)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    gpu_idle 0
    [[ ! -e "$g1_root" ]] || { echo "fresh G1 output root required: $g1_root" >&2; exit 1; }
    mkdir -p "$runtime_logs/g1"
    printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_7/v26_7_g1_wiring_gate.sh" 0 "$g1_root"
    launch "v26_7_g1_wiring" 0 "$command" "$runtime_logs/g1/g1.log" "$g1_root/g1_wiring.json"
    ;;
  g1-finalize)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    "$py" "$supervisor" finalize --receipt "$(receipt v26_7_g1_wiring)"
    require_gate "$g1_root/g1_wiring.json" G1_PASS
    ;;
  g2-launch)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    [[ -d "$g2_train_root" && ! -e "$g2_root" ]] || { echo "G2 requires Wave-B train root and fresh output root" >&2; exit 1; }
    gpu_idle 0; gpu_idle 1; mkdir -p "$runtime_logs/g2"
    for gpu in 0 1; do
      if [[ "$gpu" == 0 ]]; then lane_cells=(B0_S0 B1_S0); else lane_cells=(B0_S1 B1_S1); fi
      printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_7/v26_7_g2_waveB_eval_lane.sh" "$gpu" "$g2_train_root" "$g2_root" "${lane_cells[@]}"
      launch "v26_7_g2_gpu${gpu}" "$gpu" "$command" "$runtime_logs/g2/gpu${gpu}.log" "$g2_root/${lane_cells[1]}_STEP0750/right/metrics_eval.json"
    done
    ;;
  g2-finalize)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    "$py" "$supervisor" finalize --receipt "$(receipt v26_7_g2_gpu0)"
    "$py" "$supervisor" finalize --receipt "$(receipt v26_7_g2_gpu1)"
    require_receipt_pass v26_7_g2_gpu0; require_receipt_pass v26_7_g2_gpu1
    "$isaac_py" "$repo/scriptsFORhuman/v26_6/v26_6_waveB_reduce.py" --train-root "$g2_train_root" --eval-root "$g2_root" --output "$g2_root/waveB_reducer.json"
    exec "$isaac_py" "$repo/scriptsFORhuman/v26_7/v26_7_g2_reduce.py" --waveb-reducer "$g2_root/waveB_reducer.json" --output "$g2_root/g2_premise.json"
    ;;
  train-launch)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    require_gate "$g1_root/g1_wiring.json" G1_PASS; require_gate "$g2_root/g2_premise.json" G2_PASS
    [[ ! -e "$train_root" ]] || { echo "fresh v26-7 train root required: $train_root" >&2; exit 1; }
    mkdir -p "$train_root" "$runtime_logs/train"
    for cell in "${cells[@]}"; do
      case "$cell" in Q05_S0) gpu=2;; Q05_S1) gpu=3;; Q05_S2) gpu=4;; Q20_S0) gpu=5;; Q20_S1) gpu=6;; Q20_S2) gpu=7;; esac
      gpu_idle "$gpu"
      output="$train_root/$cell"
      printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_7/v26_7_train_cell.sh" "$gpu" "$cell" "$output"
      launch "v26_7_train_${cell,,}" "$gpu" "$command" "$runtime_logs/train/$cell.log" "$output/model_step_006000.pt"
    done
    ;;
  milestone-launch)
    [[ $# -eq 2 ]] && valid_step "$2" || { usage; exit 2; }
    step=$2; milestone_root="$eval_root/milestones/step$step"
    require_gate "$g1_root/g1_wiring.json" G1_PASS; require_gate "$g2_root/g2_premise.json" G2_PASS
    active_state=$(active_cells_for_step "$step")
    if [[ $(state_has_no_active "$active_state") == true ]]; then
      echo "V26_7_NO_ACTIVE_CONFIGS: all configs reached frozen endpoint or an earlier all-stop rule fired"
      exit 0
    fi
    active_lines=$(read_active_cells "$active_state")
    mapfile -t active_cells <<< "$active_lines"
    [[ ! -e "$milestone_root" ]] || { echo "fresh milestone root required: $milestone_root" >&2; exit 1; }
    for cell in "${active_cells[@]}"; do [[ -f "$train_root/$cell/model_step_$(printf '%06d' "$step").pt" ]] || { echo "checkpoint missing for active $cell step$step" >&2; exit 1; }; done
    gpu_idle 0; gpu_idle 1; mkdir -p "$runtime_logs/milestones/step$step"
    lane0=(); lane1=()
    for index in "${!active_cells[@]}"; do
      if (( index % 2 == 0 )); then lane0+=("${active_cells[$index]}"); else lane1+=("${active_cells[$index]}"); fi
    done
    for gpu in 0 1; do
      if [[ "$gpu" == 0 ]]; then lane_cells=("${lane0[@]}"); else lane_cells=("${lane1[@]}"); fi
      [[ ${#lane_cells[@]} -gt 0 ]] || continue
      printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_7/v26_7_eval_lane.sh" "$gpu" "$step" "$train_root" "$milestone_root" "${lane_cells[@]}"
      last=$(( ${#lane_cells[@]} - 1 ))
      launch "v26_7_eval_step${step}_gpu${gpu}" "$gpu" "$command" "$runtime_logs/milestones/step$step/gpu${gpu}.log" "$milestone_root/${lane_cells[$last]}_STEP${step}/right/metrics_eval.json"
    done
    ;;
  milestone-finalize)
    [[ $# -eq 2 ]] && valid_step "$2" || { usage; exit 2; }
    step=$2; milestone_root="$eval_root/milestones/step$step"
    active_state=$(active_cells_for_step "$step")
    if [[ $(state_has_no_active "$active_state") == true ]]; then
      echo "V26_7_NO_ACTIVE_CONFIGS: no milestone finalize is required"
      exit 0
    fi
    active_lines=$(read_active_cells "$active_state")
    mapfile -t active_cells <<< "$active_lines"
    lane0=(); lane1=()
    for index in "${!active_cells[@]}"; do
      if (( index % 2 == 0 )); then lane0+=("${active_cells[$index]}"); else lane1+=("${active_cells[$index]}"); fi
    done
    for gpu in 0 1; do
      if [[ "$gpu" == 0 ]]; then lane_cells=("${lane0[@]}"); else lane_cells=("${lane1[@]}"); fi
      [[ ${#lane_cells[@]} -gt 0 ]] || continue
      "$py" "$supervisor" finalize --receipt "$(receipt "v26_7_eval_step${step}_gpu${gpu}")"
      require_receipt_pass "v26_7_eval_step${step}_gpu${gpu}"
    done
    "$isaac_py" "$repo/scriptsFORhuman/v26_7/v26_7_reduce.py" --train-root "$train_root" --eval-root "$milestone_root" --step "$step" --output "$milestone_root/reducer.json"
    stop_all=$("$py" - "$milestone_root/reducer.json" <<'PY'
import json,sys
print("true" if json.load(open(sys.argv[1], encoding="utf-8")).get("stop_all_training") else "false")
PY
)
    if [[ "$stop_all" == true ]]; then
      for cell in "${cells[@]}"; do tmux has-session -t "v26_7_train_${cell,,}" 2>/dev/null && tmux send-keys -t "v26_7_train_${cell,,}" C-c; done
      echo "EARLY_FAILURE_STOP_SIGNALLED: see $milestone_root/reducer.json"
    else
      stop_lines=$("$py" - "$milestone_root/reducer.json" <<'PY'
import json,sys
for cell in json.load(open(sys.argv[1], encoding="utf-8"))["stop_eligible_cells"]:
    print(cell)
PY
)
      stop_cells=()
      [[ -z "$stop_lines" ]] || mapfile -t stop_cells <<< "$stop_lines"
      for cell in "${stop_cells[@]}"; do tmux has-session -t "v26_7_train_${cell,,}" 2>/dev/null && tmux send-keys -t "v26_7_train_${cell,,}" C-c; done
      [[ ${#stop_cells[@]} -eq 0 ]] || echo "EARLY_SUCCESS_ENDPOINT_STOP_SIGNALLED: ${stop_cells[*]}"
    fi
    ;;
  *) usage; exit 2 ;;
esac
