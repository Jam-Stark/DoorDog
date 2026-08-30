#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage:
  v26_5_wave1_orchestrate.sh preregister
  v26_5_wave1_orchestrate.sh probe --launch
  v26_5_wave1_orchestrate.sh smoke --launch
  v26_5_wave1_orchestrate.sh train-cell O1A0_S0|O1A0_S1|O1A1_S0|O1A1_S1 --launch
  v26_5_wave1_orchestrate.sh diagnostic --launch
  v26_5_wave1_orchestrate.sh eval-cell O1A0_S0|O1A0_S1|O1A1_S0|O1A1_S1 --launch
  v26_5_wave1_orchestrate.sh reduce

All launch modes create one tmux-backed run_supervisor receipt per physical GPU.
They are intentionally separate: formal training must complete before formal eval,
while O0A1 matched-prefix diagnostics are allowed concurrently with training.
EOF
}

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/usr/bin/python3
isaac_py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"
run_id=v26_5_wave1_stage5_20260830_r1
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
    require_static; gpu_idle 2
    command="bash $repo/scriptsFORhuman/v26_5/run_v26_5_wave1_runtime_contract_probe.sh"
    launch v26_5_wave1_r1_runtime_contract_attempt5 2 "$command" "$runtime_logs/runtime_contract_attempt5.log" "$stage/K/runtime_contract.json"
    ;;
  smoke)
    [[ $# -eq 2 && ${2:-} == --launch ]] || { usage >&2; exit 2; }
    require_static; require_pass v26_5_wave1_r1_runtime_contract_attempt5; gpu_idle 2
    smoke_root="$repo/logs_rl/by_batch/base_v26/$run_id/smoke/O1A1_SMOKE64_B1"
    [[ ! -e "$smoke_root" ]] || { echo "smoke output exists: $smoke_root" >&2; exit 1; }
    printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_smoke.sh" 2 "$smoke_root"
    launch v26_5_wave1_r1_smoke 2 "$command" "$runtime_logs/smoke/O1A1_SMOKE64_B1.log" "$smoke_root/model_step_000001.pt"
    ;;
  train-cell)
    [[ $# -eq 3 && ${3:-} == --launch ]] || { usage >&2; exit 2; }
    require_static; require_pass v26_5_wave1_r1_runtime_contract_attempt5; require_pass v26_5_wave1_r1_smoke
    label=$2
    case "$label" in
      O1A0_S0) gpu=2 ;;
      O1A0_S1) gpu=4 ;;
      O1A1_S0) gpu=5 ;;
      O1A1_S1) gpu=6 ;;
      *) usage >&2; exit 2 ;;
    esac
    gpu_idle "$gpu"
    output="$train_root/$label"; [[ ! -e "$output" ]] || { echo "formal output exists: $output" >&2; exit 1; }
    printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_train_cell.sh" "$gpu" "$label" "$output"
    launch "v26_5_wave1_r1_train_${label,,}_attempt2" "$gpu" "$command" "$runtime_logs/train_attempt2/$label.log" "$output/model_step_000750.pt"
    ;;
  diagnostic)
    [[ $# -eq 2 && ${2:-} == --launch ]] || { usage >&2; exit 2; }
    require_static; require_pass v26_5_wave1_r1_runtime_contract_attempt5; require_pass v26_5_wave1_r1_smoke; gpu_idle 7
    diagnostic_root="$eval_root/diagnostic"
    [[ ! -e "$diagnostic_root" ]] || { echo "diagnostic output exists: $diagnostic_root" >&2; exit 1; }
    printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_diagnostic_serial_gpu7.sh" "$diagnostic_root"
    launch v26_5_wave1_r1_diagnostic_gpu7 7 "$command" "$runtime_logs/diagnostic/GPU7_serial.log" "$diagnostic_root/O0A1_DIAG_R2_C0_S1_STEP0750/right/metrics_eval.json"
    ;;
  eval-cell)
    [[ $# -eq 3 && ${3:-} == --launch ]] || { usage >&2; exit 2; }
    require_static; require_pass v26_5_wave1_r1_runtime_contract_attempt5
    label=$2
    case "$label" in
      O1A0_S0) gpu=2; factor=O1A0; seed=0 ;;
      O1A0_S1) gpu=4; factor=O1A0; seed=1 ;;
      O1A1_S0) gpu=5; factor=O1A1; seed=0 ;;
      O1A1_S1) gpu=6; factor=O1A1; seed=1 ;;
      *) usage >&2; exit 2 ;;
    esac
    require_pass "v26_5_wave1_r1_train_${label,,}_attempt2"
    gpu_idle "$gpu"
    checkpoint="$train_root/$label/model_step_000750.pt"
    output="$eval_root/${label}_STEP0750"
    [[ -f "$checkpoint" && ! -e "$output" ]] || { echo "formal checkpoint missing or eval output exists: $label" >&2; exit 1; }
    printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave1_eval_cell.sh" "$gpu" "${label}_STEP0750" "$checkpoint" "$eval_root" "$seed" "$factor"
    launch "v26_5_wave1_r1_eval_${label,,}" "$gpu" "$command" "$runtime_logs/eval/$label.log" "$output/right/metrics_eval.json"
    ;;
  reduce)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    for label in O1A0_S0 O1A0_S1 O1A1_S0 O1A1_S1; do require_pass "v26_5_wave1_r1_eval_${label,,}"; done
    require_pass v26_5_wave1_r1_diagnostic_gpu7
    exec "$isaac_py" "$repo/scriptsFORhuman/v26_5/v26_5_wave1_reduce.py" --formal-eval-root "$eval_root" --diagnostic-eval-root "$eval_root/diagnostic" --output "$stage/M/wave1_reducer.json"
    ;;
  *) usage >&2; exit 2 ;;
esac
