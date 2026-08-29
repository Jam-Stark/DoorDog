#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage:
  v26_4_r2_orchestrate.sh gate
  v26_4_r2_orchestrate.sh main --gpus 0,1,2,3
  v26_4_r2_orchestrate.sh main-eval --gpus 0,1,2,3
  v26_4_r2_orchestrate.sh analyze
  v26_4_r2_orchestrate.sh closure
EOF
}

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/usr/bin/python3
supervisor="$repo/.ai/scripts/run_supervisor.py"
stage="$repo/logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828"
mroot="$stage/M"
train_root="$repo/logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main"
eval_root="$stage/eval"
gate="$mroot/k_gate_receipt.json"
metadata="$mroot/source_metadata.json"
exposure_metadata="$mroot/source_metadata_reducer_exposure_semantics_repair.json"
trace_metadata="$mroot/source_metadata_reducer_trace_completeness_repair.json"
registry="$mroot/static/command_registry.json"
resolved="$mroot/static/resolved_configs"

parse_gpus() {
  [[ ${1:-} == --gpus && $# -eq 2 && "$2" == 0,1,2,3 ]] || { usage >&2; exit 2; }
}

gpu_idle() {
  local gpu=$1 uuid
  uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F ', ' -v requested="$gpu" '$1 == requested {print $2}')
  [[ -n "$uuid" ]] || { echo "GPU$gpu is not visible" >&2; return 1; }
  ! nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep -Fq "$uuid" || { echo "GPU$gpu already has compute work" >&2; return 1; }
}

require_gate() {
  "$python_bin" - "$gate" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
if p.get('schema') != 'a2_piper_base_v26_4_r2_wave_m_k_gate_v1' or p.get('status') != 'K_C_GATE_ADMITTED_READY_FOR_R2_RUNNER':
    raise SystemExit('exact R2 K/C gate is not admitted')
if p.get('k_typed_outcome') != 'BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET':
    raise SystemExit('R2 K action-offset outcome is required')
PY
}

launch() {
  local name=$1 gpu=$2 command=$3 log=$4 checkpoint=$5 receipt
  ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session exists: $name" >&2; exit 1; }
  receipt=$("$python_bin" "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu" --checkpoint "$checkpoint")
  "$python_bin" "$supervisor" launch --receipt "$receipt"
}

require_pass_receipt() {
  local name=$1
  "$python_bin" - "$repo/.ai/runtime/runs/$name/RUN_RECEIPT.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
if p.get('state') != 'PASS' or p.get('process_returncode') != 0:
    raise SystemExit(f"receipt is not PASS: {sys.argv[1]}")
PY
}

verify_resolved_matrix() {
  "$python_bin" "$repo/scriptsFORhuman/v26_4/v26_4_r2_verify_resolved_matrix.py" \
    --config "C0S0=$resolved/C0S0.yaml" --config "C0S1=$resolved/C0S1.yaml" \
    --config "C1S0=$resolved/C1S0.yaml" --config "C1S1=$resolved/C1S1.yaml" \
    --verify-against "$mroot/static/resolved_matrix.json"
}

case ${1:-} in
  --help|-h|'') usage; exit 0 ;;
  gate)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    require_gate
    "$python_bin" "$repo/scriptsFORhuman/v26_4/v26_4_r2_verify_registry.py" --gate "$gate" --registry "$registry"
    ;;
  main)
    parse_gpus "${@:2}"
    require_gate
    "$python_bin" "$repo/scriptsFORhuman/v26_4/v26_4_r2_verify_registry.py" --gate "$gate" --registry "$registry"
    verify_resolved_matrix
    [[ ! -e "$metadata" ]] || { echo "R2 source metadata already captured; do not relaunch main" >&2; exit 1; }
    "$python_bin" "$repo/scriptsFORhuman/v26_4/v26_4_r2_source_metadata.py" --output "$metadata"
    for gpu in 0 1 2 3; do gpu_idle "$gpu"; done
    names=(C0_CANONICAL_OFF_S0 C0_CANONICAL_OFF_S1 C1_CANONICAL_ON_S0 C1_CANONICAL_ON_S1)
    seeds=(0 1 0 1)
    for index in 0 1 2 3; do
      cell=${names[$index]}; gpu=$index; seed=${seeds[$index]}; stem=${cell%_S*}; seam=false; [[ "$stem" == C1_* ]] && seam=true
      command="bash $repo/scriptsFORhuman/v26_4/v26_4_r2_orchestrate_train_cell.sh $gpu $stem $train_root/$cell $seed ++env.config.a2_v26_4_side_canonicalization_enabled=$seam"
      launch "v26_4_r2_main_${cell,,}" "$gpu" "$command" "$repo/scriptsFORhuman/v26_4/runtime_logs/r2_main/$cell.log" "$train_root/$cell/model_step_000750.pt"
    done
    ;;
  main-eval)
    parse_gpus "${@:2}"
    require_gate
    "$python_bin" "$repo/scriptsFORhuman/v26_4/v26_4_r2_source_metadata.py" --verify-against "$metadata" --output "$mroot/source_metadata_pre_eval.json"
    names=(C0_CANONICAL_OFF_S0 C0_CANONICAL_OFF_S1 C1_CANONICAL_ON_S0 C1_CANONICAL_ON_S1)
    seeds=(0 1 0 1)
    for index in 0 1 2 3; do require_pass_receipt "v26_4_r2_main_${names[$index],,}"; done
    for gpu in 0 1 2 3; do gpu_idle "$gpu"; done
    for index in 0 1 2 3; do
      cell=${names[$index]}; gpu=$index; seed=${seeds[$index]}; seam=false; [[ "$cell" == C1_* ]] && seam=true
      command="bash $repo/scriptsFORhuman/v26_4/v26_4_r2_orchestrate_main_eval_cell.sh $gpu $cell $train_root/$cell $eval_root $seed ++env.config.a2_v26_4_side_canonicalization_enabled=$seam"
      launch "v26_4_r2_eval_${cell,,}" "$gpu" "$command" "$repo/scriptsFORhuman/v26_4/runtime_logs/r2_eval/$cell.log" "$eval_root/${cell}_STEP0750/right/metrics_eval.json"
    done
    ;;
  analyze)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    require_gate
    "$python_bin" "$repo/scriptsFORhuman/v26_4/v26_4_r2_source_metadata.py" --verify-against "$trace_metadata" --output "$mroot/source_metadata_pre_analyze_trace_completeness_repair.json"
    for cell in C0_CANONICAL_OFF_S0 C0_CANONICAL_OFF_S1 C1_CANONICAL_ON_S0 C1_CANONICAL_ON_S1; do require_pass_receipt "v26_4_r2_eval_${cell,,}"; done
    exec "$python_bin" "$repo/scriptsFORhuman/v26_4/v26_4_r2_analyze_bilateral_foundation.py" --gate "$gate" --source-metadata "$trace_metadata" --eval-root "$eval_root" --output "$mroot/bilateral_foundation.json"
    ;;
  closure)
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    require_gate
    [[ -f "$mroot/bilateral_foundation.json" ]] || { echo "R2 bilateral reducer output is missing" >&2; exit 1; }
    exec "$python_bin" "$repo/scriptsFORhuman/v26_4/v26_4_r2_source_metadata.py" --verify-against "$trace_metadata" --output "$mroot/source_metadata_closure_trace_completeness_repair.json"
    ;;
  *) usage >&2; exit 2 ;;
esac
