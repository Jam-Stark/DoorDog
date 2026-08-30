#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage:
  v26_5_wave2_k0_orchestrate.sh preregister
  v26_5_wave2_k0_orchestrate.sh eval-cell K0_CONT_STEP2000_O0A0_S0|K0_CONT_STEP2000_O0A0_S1 --launch
  v26_5_wave2_k0_orchestrate.sh reduce
EOF
}

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/usr/bin/python3
isaac_py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"
run_id=v26_5_wave2_k0_identity_20260830_r2
stage="$repo/logs_eval/base_v26/$run_id"
static="$stage/K0/static"
registry="$static/command_registry.json"
resolved="$static/resolved_configs"
eval_root="$stage/eval"
runtime_logs="$repo/scriptsFORhuman/v26_5/runtime_logs/$run_id"

gpu_idle() {
  local gpu=$1 uuid
  uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F ', ' -v requested="$gpu" '$1 == requested {print $2}')
  [[ -n "$uuid" ]] || { echo "GPU$gpu is not visible" >&2; return 1; }
  ! nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep -Fq "$uuid" || { echo "GPU$gpu already has compute work" >&2; return 1; }
}

launch() {
  local name=$1 gpu=$2 command=$3 log=$4 terminal=$5 receipt
  ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session exists: $name" >&2; exit 1; }
  receipt=$("$py" "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log" --checkpoint "$terminal" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu")
  "$py" "$supervisor" launch --receipt "$receipt"
}

require_pass() {
  "$py" - "$repo/.ai/runtime/runs/$1/RUN_RECEIPT.json" <<'PY'
import json,sys
receipt=json.load(open(sys.argv[1],encoding="utf-8"))
if receipt.get("state") != "PASS" or receipt.get("process_returncode") != 0:
    raise SystemExit(f"receipt is not PASS: {sys.argv[1]}")
PY
}

preregister() {
  [[ ! -e "$static" ]] || { echo "Wave2 K0 static root exists; do not overwrite preregistration" >&2; exit 1; }
  "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_k0_registry.py" --output "$registry"
  "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_k0_compose.py" --output-dir "$resolved"
  "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_k0_verify.py" --registry "$registry" \
    --config "K0_CONT_STEP2000_O0A0_S0=$resolved/K0_CONT_STEP2000_O0A0_S0.yaml" \
    --config "K0_CONT_STEP2000_O0A0_S1=$resolved/K0_CONT_STEP2000_O0A0_S1.yaml"
}

require_static() {
  [[ -f "$registry" && -d "$resolved" ]] || { echo "run preregister first" >&2; exit 1; }
  "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_k0_verify.py" --registry "$registry" \
    --config "K0_CONT_STEP2000_O0A0_S0=$resolved/K0_CONT_STEP2000_O0A0_S0.yaml" \
    --config "K0_CONT_STEP2000_O0A0_S1=$resolved/K0_CONT_STEP2000_O0A0_S1.yaml"
}

case ${1:-} in
  --help|-h|'') usage; exit 0 ;;
  preregister)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    preregister
    ;;
  eval-cell)
    [[ $# -eq 3 && ${3:-} == --launch ]] || { usage >&2; exit 2; }
    require_static
    label=$2
    case "$label" in
      K0_CONT_STEP2000_O0A0_S0) gpu=0; seed=0 ;;
      K0_CONT_STEP2000_O0A0_S1) gpu=1; seed=1 ;;
      *) usage >&2; exit 2 ;;
    esac
    gpu_idle "$gpu"
    output="$eval_root/$label"
    [[ ! -e "$output" ]] || { echo "K0 eval output exists: $output" >&2; exit 1; }
    printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_k0_eval_cell.sh" "$gpu" "$label" "$eval_root" "$seed"
    launch "${run_id}_eval_s${seed}" "$gpu" "$command" "$runtime_logs/eval/$label.log" "$output/right/metrics_eval.json"
    ;;
  reduce)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    require_static
    require_pass "${run_id}_eval_s0"; require_pass "${run_id}_eval_s1"
    exec "$isaac_py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_k0_reduce.py" --eval-root "$eval_root" --output "$stage/K0/source_control_reducer.json"
    ;;
  *) usage >&2; exit 2 ;;
esac
