#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage:
  v26_5_wave1_orchestrate.sh preregister
  v26_5_wave1_orchestrate.sh probe --launch
  v26_5_wave1_orchestrate.sh smoke --launch
  v26_5_wave1_orchestrate.sh train --launch
  v26_5_wave1_orchestrate.sh diagnostic --launch
  v26_5_wave1_orchestrate.sh formal-eval --launch
  v26_5_wave1_orchestrate.sh reduce

All launch modes create one tmux-backed run_supervisor receipt per physical GPU.
They are intentionally separate: formal training must complete before formal eval,
while O0A1 matched-prefix diagnostics are allowed concurrently with training.
EOF
}

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/usr/bin/python3
supervisor="$repo/.ai/scripts/run_supervisor.py"
run_id=v26_5_wave1_stage5_20260830
stage="$repo/logs_eval/base_v26/$run_id"
static="$stage/M/static"
registry="$static/command_registry.json"
resolved="$static/resolved_configs"
train_root="$repo/logs_rl/by_batch/base_v26/$run_id/formal"
eval_root="$stage/eval"
runtime_logs="$repo/scriptsFORhuman/v26_5/runtime_logs/$run_id"

gpu_idle() {
  local gpu=$1 uuid
  uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F ', ' -v requested="$gpu" '$1 == requested {print $2}')
  [[ -n "$uuid" ]] || { echo "GPU$gpu is not visible" >&2; return 1; }
  ! nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep -Fq "$uuid" || { echo "GPU$gpu already has compute work" >&2; return 1; }
}

launch() {
  local name=$1 gpu=$2 command=$3 log=$4 checkpoint=$5 receipt
  ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session exists: $name" >&2; exit 1; }
  receipt=$("$py" "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log" --checkpoint "$checkpoint" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu")
  "$py" "$supervisor" launch --receipt "$receipt"
}

require_pass() {
  "$py" - "$repo/.ai/runtime/runs/$1/RUN_RECEIPT.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
if p.get('state') != 'PASS' or p.get('process_returncode') != 0:
    raise SystemExit(f"receipt is not PASS: {sys.argv[1]}")
PY
}

preregister() {
  [[ ! -e "$static" ]] || { echo "Wave1 static root exists; do not overwrite preregistration" >&2; exit 1; }
  "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave1_registry.py" --output "$registry"
  "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave1_compose.py" --output-dir "$resolved"
  "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave1_verify.py" --registry "$registry" \
    --config "O1A0_S0=$resolved/O1A0_S0.yaml" --config "O1A0_S1=$resolved/O1A0_S1.yaml" \
    --config "O1A1_S0=$resolved/O1A1_S0.yaml" --config "O1A1_S1=$resolved/O1A1_S1.yaml"
}

require_static() {
  [[ -f "$registry" && -d "$resolved" ]] || { echo "run preregister first" >&2; exit 1; }
  "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave1_verify.py" --registry "$registry" \
    --config "O1A0_S0=$resolved/O1A0_S0.yaml" --config "O1A0_S1=$resolved/O1A0_S1.yaml" \
    --config "O1A1_S0=$resolved/O1A1_S0.yaml" --config "O1A1_S1=$resolved/O1A1_S1.yaml"
}

case ${1:-} in
  --help|-h|'') usage; exit 0 ;;
  preregister)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    preregister
    ;;
  probe)
    [[ $# -eq 2 && ${2:-} == --launch ]] || { usage >&2; exit 2; }
    require_static; gpu_idle 0
    command="bash $repo/scriptsFORhuman/v26_5/run_v26_5_wave1_runtime_contract_probe.sh"
    launch v26_5_wave1_runtime_contract 0 "$command" "$runtime_logs/runtime_contract.log" "$stage/K/runtime_contract.json"
    ;;
  smoke)
    [[ $# -eq 2 && ${2:-} == --launch ]] || { usage >&2; exit 2; }
    require_static; require_pass v26_5_wave1_runtime_contract; gpu_idle 0
    smoke_root="$repo/logs_rl/by_batch/base_v26/$run_id/smoke/O1A1_SMOKE64_B1"
    [[ ! -e "$smoke_root" ]] || { echo "smoke output exists: $smoke_root" >&2; exit 1; }
    printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_smoke.sh" 0 "$smoke_root"
    launch v26_5_wave1_smoke 0 "$command" "$runtime_logs/smoke/O1A1_SMOKE64_B1.log" "$smoke_root/model_step_000001.pt"
    ;;
  train)
    [[ $# -eq 2 && ${2:-} == --launch ]] || { usage >&2; exit 2; }
    require_static; require_pass v26_5_wave1_runtime_contract; require_pass v26_5_wave1_smoke
    for gpu in 0 1 2 3; do gpu_idle "$gpu"; done
    for entry in '0 O1A0_S0' '1 O1A0_S1' '2 O1A1_S0' '3 O1A1_S1'; do
      read -r gpu label <<<"$entry"; output="$train_root/$label"; [[ ! -e "$output" ]] || { echo "formal output exists: $output" >&2; exit 1; }
      printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_train_cell.sh" "$gpu" "$label" "$output"
      launch "v26_5_wave1_train_${label,,}" "$gpu" "$command" "$runtime_logs/train/$label.log" "$output/model_step_000750.pt"
    done
    ;;
  diagnostic)
    [[ $# -eq 2 && ${2:-} == --launch ]] || { usage >&2; exit 2; }
    require_static; require_pass v26_5_wave1_runtime_contract; require_pass v26_5_wave1_smoke
    for gpu in 4 5 6 7; do gpu_idle "$gpu"; done
    for entry in '4 0 left' '5 0 right' '6 1 left' '7 1 right'; do
      read -r gpu seed side <<<"$entry"; label="O0A1_DIAG_R2_C0_S${seed}_STEP0750"; checkpoint="$repo/logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main/C0_CANONICAL_OFF_S${seed}/model_step_000750.pt"
      output="$eval_root/diagnostic/$label/$side"; [[ -f "$checkpoint" && ! -e "$output" ]] || { echo "diagnostic checkpoint missing or output exists: $output" >&2; exit 1; }
      printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_eval_side.sh" "$gpu" "$label" "$checkpoint" "$eval_root/diagnostic" "$seed" O0A1 "$side"
      launch "v26_5_wave1_diag_s${seed}_${side}" "$gpu" "$command" "$runtime_logs/diagnostic/${label}_${side}.log" "$output/metrics_eval.json"
    done
    ;;
  formal-eval)
    [[ $# -eq 2 && ${2:-} == --launch ]] || { usage >&2; exit 2; }
    require_static
    for label in O1A0_S0 O1A0_S1 O1A1_S0 O1A1_S1; do require_pass "v26_5_wave1_train_${label,,}"; done
    for gpu in 0 1 2 3; do gpu_idle "$gpu"; done
    for entry in '0 O1A0_S0 O1A0' '1 O1A0_S1 O1A0' '2 O1A1_S0 O1A1' '3 O1A1_S1 O1A1'; do
      read -r gpu label factor <<<"$entry"; seed=${label##*_S}; checkpoint="$train_root/$label/model_step_000750.pt"; [[ ! -e "$eval_root/${label}_STEP0750" ]] || { echo "formal eval output exists: $label" >&2; exit 1; }
      printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_eval_cell.sh" "$gpu" "${label}_STEP0750" "$checkpoint" "$eval_root" "$seed" "$factor"
      launch "v26_5_wave1_eval_${label,,}" "$gpu" "$command" "$runtime_logs/eval/$label.log" "$eval_root/${label}_STEP0750/right/metrics_eval.json"
    done
    ;;
  reduce)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    for label in O1A0_S0 O1A0_S1 O1A1_S0 O1A1_S1; do require_pass "v26_5_wave1_eval_${label,,}"; done
    for name in v26_5_wave1_diag_s0_left v26_5_wave1_diag_s0_right v26_5_wave1_diag_s1_left v26_5_wave1_diag_s1_right; do require_pass "$name"; done
    exec "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave1_reduce.py" --formal-eval-root "$eval_root" --diagnostic-eval-root "$eval_root/diagnostic" --output "$stage/M/wave1_reducer.json"
    ;;
  *) usage >&2; exit 2 ;;
esac
