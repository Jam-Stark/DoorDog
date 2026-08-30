#!/usr/bin/env bash
set -euo pipefail
usage(){ cat <<'EOF'
usage:
  v26_5_wave2_r1_orchestrate.sh preregister
  v26_5_wave2_r1_orchestrate.sh k1-cell K1_S0|K1_S1 --launch
  v26_5_wave2_r1_orchestrate.sh k1-reduce
  v26_5_wave2_r1_orchestrate.sh smoke --launch
  v26_5_wave2_r1_orchestrate.sh train-cell R1_S0|R1_S1 --launch
  v26_5_wave2_r1_orchestrate.sh eval-cell R1_S0|R1_S1 125|250 --launch
  v26_5_wave2_r1_orchestrate.sh reduce

Cold Isaac starts are deliberately separate commands.  The controller must
launch one cell, observe its first iteration, then start the next cell; this
script never polls, retries, or starts a competing process automatically.
EOF
}
repo=/home/baoquanc/workspace/DoorDog-A2_Piper; py=/usr/bin/python3; isaac_py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python; supervisor="$repo/.ai/scripts/run_supervisor.py"
run_id=v26_5_wave2_r1_policy_residual_20260830_r3; stage="$repo/logs_eval/base_v26/$run_id"; static="$stage/M/static"; registry="$static/command_registry.json"; resolved="$static/resolved_configs"; eval_root="$stage/eval"; train_root="$repo/logs_rl/by_batch/base_v26/$run_id/formal"; runtime_logs="$repo/scriptsFORhuman/v26_5/runtime_logs/$run_id"
gpu_idle(){ local gpu=$1 uuid; uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F ', ' -v requested="$gpu" '$1 == requested {print $2}'); [[ -n "$uuid" ]] || { echo "GPU$gpu is not visible" >&2; return 1; }; ! nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep -Fq "$uuid" || { echo "GPU$gpu already has compute work" >&2; return 1; }; }
launch(){ local name=$1 gpu=$2 command=$3 log=$4 checkpoint=$5 receipt; ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session exists: $name" >&2; exit 1; }; receipt=$("$py" "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log" --checkpoint "$checkpoint" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu"); "$py" "$supervisor" launch --receipt "$receipt"; }
require_pass(){ "$py" - "$repo/.ai/runtime/runs/$1/RUN_RECEIPT.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'))
if v.get('state')!='PASS' or v.get('process_returncode')!=0: raise SystemExit(f"receipt not PASS: {sys.argv[1]}")
PY
}
static_verify(){ "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_verify.py" --registry "$registry" --config "R1_S0_train=$resolved/R1_S0_train.yaml" --config "R1_S0_eval=$resolved/R1_S0_eval.yaml" --config "R1_S1_train=$resolved/R1_S1_train.yaml" --config "R1_S1_eval=$resolved/R1_S1_eval.yaml"; }
case ${1:-} in
  --help|-h|'') usage ;;
  preregister) [[ $# -eq 1 ]] || { usage >&2; exit 2; }; [[ ! -e "$static" ]] || { echo "R1 static root exists" >&2; exit 1; }; "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_registry.py" --output "$registry"; "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_compose.py" --output-dir "$resolved"; static_verify ;;
  k1-cell) [[ $# -eq 3 && $3 == --launch ]] || { usage >&2; exit 2; }; static_verify; label=$2; case "$label" in K1_S0) gpu=2;seed=0;;K1_S1) gpu=3;seed=1;;*) usage >&2;exit 2;;esac; gpu_idle "$gpu"; output="$eval_root/K1/control/$label/right/metrics_eval.json"; [[ ! -e "$eval_root/K1/control/$label" && ! -e "$eval_root/K1/dual/$label" ]] || { echo "K1 output exists: $label" >&2; exit 1; }; printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_k1_cell.sh" "$gpu" "$label" "$eval_root" "$seed"; launch "${run_id}_k1_s${seed}" "$gpu" "$command" "$runtime_logs/k1/$label.log" "$output" ;;
  k1-reduce) [[ $# -eq 1 ]] || { usage >&2; exit 2; }; static_verify; require_pass "${run_id}_k1_s0";require_pass "${run_id}_k1_s1"; exec "$isaac_py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_reduce.py" k1 --eval-root "$eval_root" --output "$stage/K1/identity_reducer.json" ;;
  smoke) [[ $# -eq 2 && $2 == --launch ]] || { usage >&2; exit 2; }; static_verify; [[ -f "$stage/K1/identity_reducer.json" ]] || { echo "K1 reducer required" >&2;exit 1; }; "$py" - "$stage/K1/identity_reducer.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1])).get('typed_outcome')!='K1_IDENTITY_ADMITTED': raise SystemExit('K1 is not admitted')
PY
    gpu_idle 2; output="$repo/logs_rl/by_batch/base_v26/$run_id/smoke/R1_SMOKE64_B1"; [[ ! -e "$output" ]] || { echo "smoke output exists" >&2;exit 1; }; printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_smoke.sh" 2 "$output"; launch "${run_id}_smoke" 2 "$command" "$runtime_logs/smoke/R1_SMOKE64_B1.log" "$output/model_step_000001.pt" ;;
  train-cell) [[ $# -eq 3 && $3 == --launch ]] || { usage >&2;exit 2; }; static_verify; "$py" - "$stage/K1/identity_reducer.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1])).get('typed_outcome')!='K1_IDENTITY_ADMITTED': raise SystemExit('K1 is not admitted')
PY
    require_pass "${run_id}_smoke"; label=$2; case "$label" in R1_S0) gpu=2;seed=0;;R1_S1) gpu=3;seed=1;;*) usage >&2;exit 2;;esac; gpu_idle "$gpu"; output="$train_root/$label"; [[ ! -e "$output" ]] || { echo "R1 output exists: $output" >&2;exit 1; }; printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_train_cell.sh" "$gpu" "$label" "$output"; launch "${run_id}_train_${label,,}" "$gpu" "$command" "$runtime_logs/train/$label.log" "$output/model_step_000250.pt" ;;
  eval-cell) [[ $# -eq 4 && $4 == --launch ]] || { usage >&2;exit 2; }; static_verify; label=$2; step=$3; [[ "$step" =~ ^(125|250)$ ]] || { usage >&2;exit 2; }; case "$label" in R1_S0) gpu=2;seed=0;;R1_S1) gpu=3;seed=1;;*) usage >&2;exit 2;;esac; require_pass "${run_id}_train_${label,,}"; checkpoint="$train_root/$label/$(printf 'model_step_%06d.pt' "$step")"; output="$eval_root/${label}_STEP$(printf '%04d' "$step")"; [[ -f "$checkpoint" && ! -e "$output" ]] || { echo "checkpoint missing or eval output exists" >&2;exit 1; }; gpu_idle "$gpu"; printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_eval_cell.sh" "$gpu" "${label}_STEP$(printf '%04d' "$step")" "$checkpoint" "$eval_root" "$seed"; launch "${run_id}_eval_${label,,}_$step" "$gpu" "$command" "$runtime_logs/eval/${label}_$step.log" "$output/right/metrics_eval.json" ;;
  reduce) [[ $# -eq 1 ]] || { usage >&2;exit 2; }; for label in R1_S0 R1_S1;do for step in 125 250;do require_pass "${run_id}_eval_${label,,}_$step";done;done; exec "$isaac_py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_reduce.py" r1 --eval-root "$eval_root" --train-root "$train_root" --output "$stage/M/r1_reducer.json" ;;
  *) usage >&2;exit 2;;
esac
