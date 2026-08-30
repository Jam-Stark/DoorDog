#!/usr/bin/env bash
set -euo pipefail
usage(){ cat <<'EOF'
usage:
  v26_5_wave2_r1_r13_orchestrate.sh preregister
  v26_5_wave2_r1_r13_orchestrate.sh wiring-gate --launch
  v26_5_wave2_r1_r13_orchestrate.sh k1-cell K1_S0|K1_S1 --launch
  v26_5_wave2_r1_r13_orchestrate.sh k1-reduce
  v26_5_wave2_r1_r13_orchestrate.sh self-check
  v26_5_wave2_r1_r13_orchestrate.sh smoke --launch
  v26_5_wave2_r1_r13_orchestrate.sh train-cell R13_S0|R13_S1 --launch
  v26_5_wave2_r1_r13_orchestrate.sh eval-cell R13_S0|R13_S1 125|250 --launch

Each cold Isaac start is a separate supervisor command. K1_S1 includes an
in-tmux sleep 600; this script never polls or retries a simulator process.
EOF
}
repo=/home/baoquanc/workspace/DoorDog-A2_Piper;py=/usr/bin/python3;isaac_py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python;supervisor="$repo/.ai/scripts/run_supervisor.py"
run_id=v26_5_wave2_r1_policy_residual_20260830_r13;stage="$repo/logs_eval/base_v26/$run_id";static="$stage/M/static";registry="$static/command_registry.json";selectors="$static/selectors";eval_root="$stage/eval";train_root="$repo/logs_rl/by_batch/base_v26/$run_id";runtime_logs="$repo/scriptsFORhuman/v26_5/runtime_logs/$run_id";wiring_output="$stage/wiring_gate/R13_DUAL_S0_RIGHT";wiring_receipt="$repo/.ai/runtime/runs/${run_id}_wiring_gate/RUN_RECEIPT.json";wiring_artifact="$stage/wiring_gate/r13_wiring_admission.json"
gpu_idle(){ local gpu=$1 uuid;uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader|awk -F ', ' -v g="$gpu" '$1==g{print $2}');[[ -n "$uuid" ]]||{ echo "GPU$gpu unavailable" >&2;return 1;};! nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader|grep -Fq "$uuid"||{ echo "GPU$gpu busy" >&2;return 1;}; }
launch(){ local name=$1 gpu=$2 command=$3 log=$4 checkpoint=$5 receipt;! tmux has-session -t "$name" 2>/dev/null||{ echo "tmux session exists: $name" >&2;exit 1;};receipt=$("$py" "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log" --checkpoint "$checkpoint" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu");"$py" "$supervisor" launch --receipt "$receipt"; }
require_pass(){ "$py" - "$repo/.ai/runtime/runs/$1/RUN_RECEIPT.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1]));
if v.get('state')!='PASS' or v.get('process_returncode')!=0:raise SystemExit(f"receipt not PASS: {sys.argv[1]}")
PY
}
require_admitted(){ "$py" - "$stage/K1/identity_reducer.json" <<'PY'
import json,sys
p=sys.argv[1]
try:v=json.load(open(p))
except FileNotFoundError:raise SystemExit(f"missing r13 K1 reducer: {p}")
expected={"seed0_left","seed0_right","seed1_left","seed1_right"}
pairs=v.get("pairs",{})
if v.get("typed_outcome")!="R13_CAUSAL_IDENTITY_ADMITTED" or set(pairs)!=expected or not all(x.get("pass") is True for x in pairs.values()):
 raise SystemExit("r13 formal admission refused: reducer is absent, KILL, or lacks four passing pairs")
PY
}
verify(){ "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_verify.py" --registry "$registry" --selector-root "$selectors"; }
require_wiring(){ "$isaac_py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_wiring_validate.py" --assert-admitted --raw-output "$wiring_output" --supervisor-receipt "$wiring_receipt" --output "$wiring_artifact"; }
case ${1:-} in
 preregister) [[ $# -eq 1 && ! -e "$static" ]]||{ echo "fresh r13 static root required" >&2;exit 2;};"$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_registry.py" --output "$registry";"$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_compose.py" --output-dir "$selectors";"$isaac_py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_cpu_shadow_gate.py" --output "$static/r13_cpu_primary_cache_gate.json";verify;;
 wiring-gate) [[ $# -eq 2 && $2 == --launch ]]||{ usage >&2;exit 2;};verify;gpu_idle 4;[[ ! -e "$wiring_output" && ! -e "$wiring_artifact" ]]||{ echo "fresh r13 wiring paths required" >&2;exit 1;};printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_wiring_gate.sh" 4 "$wiring_output" "$wiring_receipt" "$wiring_artifact";launch "${run_id}_wiring_gate" 4 "$command" "$runtime_logs/wiring_gate.log" "$wiring_output/metrics_eval.json";;
 k1-cell) [[ $# -eq 3 && $3 == --launch ]]||{ usage >&2;exit 2;};verify;require_wiring;label=$2;case "$label" in K1_S0)gpu=4;seed=0;stagger=0;;K1_S1)gpu=5;seed=1;stagger=600;;*)usage >&2;exit 2;;esac;gpu_idle "$gpu";[[ ! -e "$eval_root/K1/control/$label" && ! -e "$eval_root/K1/dual/$label" ]]||{ echo "fresh r13 K1 output required" >&2;exit 1;};printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_k1_cell.sh" "$gpu" "$label" "$eval_root" "$seed";[[ $stagger -eq 0 ]]||command="sleep $stagger; $command";launch "${run_id}_k1_s${seed}" "$gpu" "$command" "$runtime_logs/k1/$label.log" "$eval_root/K1/control/$label/right/metrics_eval.json";;
 k1-reduce) [[ $# -eq 1 ]]||{ usage >&2;exit 2;};verify;require_pass "${run_id}_k1_s0";require_pass "${run_id}_k1_s1";exec "$isaac_py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_reduce.py" --eval-root "$eval_root" --output "$stage/K1/identity_reducer.json";;
 self-check) [[ $# -eq 1 ]]||{ usage >&2;exit 2;};verify;exec "$py" "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_reduce.py" --self-check;;
 smoke) [[ $# -eq 2 && $2 == --launch ]]||{ usage >&2;exit 2;};verify;require_admitted;gpu_idle 4;smoke_output="$train_root/smoke/R13_SMOKE64_B1";[[ ! -e "$smoke_output" ]]||{ echo "fresh r13 smoke output required" >&2;exit 1;};printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_smoke.sh" 4 "$smoke_output";launch "${run_id}_smoke" 4 "$command" "$runtime_logs/smoke.log" "$smoke_output/model_step_000001.pt";;
 train-cell) [[ $# -eq 3 && $3 == --launch ]]||{ usage >&2;exit 2;};verify;require_admitted;require_pass "${run_id}_smoke";label=$2;case "$label" in R13_S0)gpu=4;seed=0;;R13_S1)gpu=5;seed=1;;*)usage >&2;exit 2;;esac;gpu_idle "$gpu";train_output="$train_root/train/$label";[[ ! -e "$train_output" ]]||{ echo "fresh r13 train output required" >&2;exit 1;};printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_train_cell.sh" "$gpu" "$label" "$train_output";launch "${run_id}_train_${label,,}" "$gpu" "$command" "$runtime_logs/train/$label.log" "$train_output/model_step_000250.pt";;
 eval-cell) [[ $# -eq 4 && $4 == --launch ]]||{ usage >&2;exit 2;};verify;require_admitted;label=$2;step=$3;case "$label" in R13_S0)gpu=4;seed=0;;R13_S1)gpu=5;seed=1;;*)usage >&2;exit 2;;esac;[[ "$step" =~ ^(125|250)$ ]]||{ usage >&2;exit 2;};require_pass "${run_id}_train_${label,,}";checkpoint="$train_root/train/$label/model_step_000${step}.pt";[[ -f "$checkpoint" ]]||{ echo "missing r13 train checkpoint: $checkpoint" >&2;exit 1;};gpu_idle "$gpu";eval_label="${label}_STEP0${step}";eval_output="$stage/formal_eval/$eval_label";[[ ! -e "$eval_output" ]]||{ echo "fresh r13 eval output required" >&2;exit 1;};printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_5/v26_5_wave2_r1_r13_eval_cell.sh" "$gpu" "$label" "$step" "$checkpoint" "$eval_output" "$seed";launch "${run_id}_eval_${label,,}_${step}" "$gpu" "$command" "$runtime_logs/eval/${eval_label}.log" "$eval_output/$eval_label/right/metrics_eval.json";;
 *)usage >&2;exit 2;;
esac
