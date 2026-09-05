#!/usr/bin/env bash
# Frozen v26-8 operation entrypoint: each long worker has one tmux receipt.
set -euo pipefail
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/usr/bin/python3
isaac_py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"
run_id=v26_8_bilateral_opening_scaffold_decay_20260903_r3a
train_root="$repo/logs_rl/by_batch/base_v26/$run_id/train"
eval_root="$repo/logs_eval/base_v26/$run_id"
runtime_logs="$repo/scriptsFORhuman/v26_8/runtime_logs/$run_id"
static_lock="$runtime_logs/source_lock.json"
baseline_static_lock="$repo/scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3/source_lock.json"
r3a_contract_lock="$runtime_logs/r3a_contract_lock.json"
g0_root="$eval_root/G0_static_unit"
g1_root="$repo/logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3/G1_k_wiring"
g1_gate="$g1_root/g1_readjudication.json"
p0_assets="$repo/scriptsFORhuman/v26_8/v26_8_p0_assets.py"
r3a_verify="$repo/scriptsFORhuman/v26_8/v26_8_r3a_verify.py"
cells=(C_S1 W_S1 K_S1 C_S2 W_S2 K_S2)
usage() { echo "usage: $0 static|g0|g1-readjudication-launch|g1-readjudication-finalize|train-launch|train-finalize|milestone-launch STEP|milestone-finalize STEP|closure|wave2-branches" >&2; }
run_name() { echo "${1}_r3a"; }
receipt() { echo "$repo/.ai/runtime/runs/$(run_name "$1")/RUN_RECEIPT.json"; }
valid_step() { [[ "$1" =~ ^(500|1000|1500|2000|2500|3000)$ ]]; }
gpu_visible() {
  local gpu=$1 occupancy
  [[ "$gpu" =~ ^[0-7]$ ]] || { echo "v26-8 GPU must be in 0..7: $gpu" >&2; return 1; }
  occupancy=$(nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader | awk -F ', ' -v i="$gpu" '$1==i {print; found=1} END {exit !found}')
  [[ -n "$occupancy" ]] || { echo "GPU$gpu is not visible" >&2; return 1; }
  echo "GPU$gpu occupancy: $occupancy" >&2
}
proxy_prefix() {
  local key encoded prefix=env
  for key in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY; do
    printf -v encoded '%q' "${!key-}"
    prefix+=" $key=$encoded"
  done
  printf '%s' "$prefix"
}
p0_preflight() {
  local name=$1 key proxy_vars=() artifact
  for key in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY; do proxy_vars+=("$key=${!key-}"); done
  artifact="$runtime_logs/p0_assets/$(run_name "$name").json"
  env "${proxy_vars[@]}" "$py" "$p0_assets" --output "$artifact"
}
launch() {
  local name=$1 gpu=$2 command=$3 log=$4 expected=$5 created session
  session=$(run_name "$name")
  ! tmux has-session -t "$session" 2>/dev/null || { echo "tmux session exists: $session" >&2; exit 1; }
  p0_preflight "$name"
  command="$(proxy_prefix) $command"
  created=$("$py" "$supervisor" prepare --name "$session" --session "$session" --cwd "$repo" --command "$command" --output "$log" --checkpoint "$expected" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu")
  "$py" "$supervisor" launch --receipt "$created"
}
launch_cpu() {
  local name=$1 command=$2 log=$3 expected=$4 created session
  session=$(run_name "$name")
  ! tmux has-session -t "$session" 2>/dev/null || { echo "tmux session exists: $session" >&2; exit 1; }
  created=$("$py" "$supervisor" prepare --name "$session" --session "$session" --cwd "$repo" --command "$command" --output "$log" --checkpoint "$expected" --resource CPU)
  "$py" "$supervisor" launch --receipt "$created"
}
require_gate() { "$py" - "$1" "$2" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
if x.get('status') != sys.argv[2]: raise SystemExit(f"gate {sys.argv[1]}={x.get('status')!r}, expected {sys.argv[2]!r}")
PY
}
require_receipt_pass() { "$py" - "$(receipt "$1")" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
if x.get('state') != 'PASS' or x.get('process_returncode') != 0: raise SystemExit(f"receipt is not PASS/0: {sys.argv[1]}")
PY
}
require_runtime_returncodes_pass() { "$py" - "$1" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
if x.get('status') != 'RUNTIME_PROCESS_PASS' or x.get('isaac_process_returncode') != 0 or x.get('wrapper_returncode') != 0 or x.get('policy_load_observed') is not True:
    raise SystemExit(f"runtime child/wrapper receipt is not PASS/0/0: {sys.argv[1]}")
PY
}
active_cells() { "$py" - "$eval_root" "$1" <<'PY'
import json,sys
root,step=sys.argv[1:]; steps=(500,1000,1500,2000,2500,3000); stopped=set()
for previous in steps[:steps.index(int(step))]:
  payload=json.load(open(f'{root}/milestones/step{previous}/reducer.json',encoding='utf-8'))
  if payload.get('route') == 'V26_8_INVALID': raise SystemExit('preceding milestone is V26_8_INVALID')
  stopped.update(payload.get('stop_cells',()))
for cell in ('C_S1','W_S1','K_S1','C_S2','W_S2','K_S2'):
  if cell not in stopped: print(cell)
PY
}
case ${1:-} in
static)
  [[ $# -eq 1 && -f "$baseline_static_lock" && ! -e "$static_lock" && ! -e "$r3a_contract_lock" ]] || { usage; exit 2; }; mkdir -p "$runtime_logs"
  "$isaac_py" "$r3a_verify" --baseline "$baseline_static_lock" --output "$r3a_contract_lock"
  exec "$isaac_py" "$repo/scriptsFORhuman/v26_8/v26_8_verify.py" --output "$static_lock" ;;
g0)
  [[ $# -eq 1 && -f "$static_lock" && ! -e "$g0_root" ]] || { usage; exit 2; }; require_gate "$static_lock" STATIC_PASS; mkdir -p "$g0_root"
  "$isaac_py" -m pytest -q "$repo"/gr00t/rl/tests/test_a2_v26_8_*.py
  "$py" -c "import json; open('$g0_root/g0_unit.json','x',encoding='utf-8').write(json.dumps({'schema':'a2_piper_base_v26_8_g0_v1','status':'G0_PASS'})+'\\n')" ;;
g1-readjudication-launch)
  [[ $# -eq 1 && -f "$static_lock" && -f "$r3a_contract_lock" && -f "$g0_root/g0_unit.json" && -f "$g1_root/g1_failure.json" && ! -e "$g1_gate" ]] || { usage; exit 2; }
  require_gate "$static_lock" STATIC_PASS; require_gate "$r3a_contract_lock" R3A_CONTRACT_PASS; require_gate "$g0_root/g0_unit.json" G0_PASS
  mkdir -p "$runtime_logs/g1_readjudication"
  printf -v command '%q ' "$isaac_py" "$repo/scriptsFORhuman/v26_8/v26_8_g1_reduce.py" --root "$g1_root" --output "$g1_gate" --readjudication
  launch_cpu v26_8_g1_r3_readjudication "$command" "$runtime_logs/g1_readjudication/g1_readjudication.log" "$g1_gate" ;;
g1-readjudication-finalize)
  [[ $# -eq 1 ]] || { usage; exit 2; }; "$py" "$supervisor" finalize --receipt "$(receipt v26_8_g1_r3_readjudication)"; require_receipt_pass v26_8_g1_r3_readjudication; require_gate "$g1_gate" G1_READJUDICATION_PASS ;;
train-launch)
  [[ $# -eq 1 && ! -e "$train_root" ]] || { usage; exit 2; }; require_gate "$static_lock" STATIC_PASS; require_gate "$r3a_contract_lock" R3A_CONTRACT_PASS; require_gate "$g0_root/g0_unit.json" G0_PASS; require_gate "$g1_gate" G1_READJUDICATION_PASS; require_receipt_pass v26_8_g1_r3_readjudication; mkdir -p "$train_root" "$runtime_logs/train"
  for cell in "${cells[@]}"; do
    case "$cell" in C_S1) gpu=2;; W_S1) gpu=3;; K_S1) gpu=4;; C_S2) gpu=5;; W_S2) gpu=6;; K_S2) gpu=7;; esac
    gpu_visible "$gpu"; output="$train_root/$cell"; printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_8/v26_8_train_cell.sh" "$gpu" "$cell" "$output"
    launch "v26_8_train_${cell,,}" "$gpu" "$command" "$runtime_logs/train/$cell.log" "$output/model_step_003000.pt"
  done ;;
milestone-launch)
  [[ $# -eq 2 ]] && valid_step "$2" || { usage; exit 2; }; step=$2; root="$eval_root/milestones/step$step"; [[ ! -e "$root" ]] || { echo "fresh milestone root required: $root" >&2; exit 1; }; require_gate "$g1_gate" G1_READJUDICATION_PASS
  mapfile -t active < <(active_cells "$step"); [[ ${#active[@]} -gt 0 ]] || { echo V26_8_NO_ACTIVE_CELLS; exit 0; }; for cell in "${active[@]}"; do [[ -f "$train_root/$cell/model_step_$(printf '%06d' "$step").pt" ]] || { echo "checkpoint missing: $cell step$step" >&2; exit 1; }; done
  gpu_visible 0; gpu_visible 1; mkdir -p "$runtime_logs/milestones/step$step"; lane0=(); lane1=(); for i in "${!active[@]}"; do if (( i % 2 == 0 )); then lane0+=("${active[$i]}"); else lane1+=("${active[$i]}"); fi; done
  for gpu in 0 1; do
    if [[ "$gpu" == 0 ]]; then lane=("${lane0[@]}"); else lane=("${lane1[@]}"); fi; [[ ${#lane[@]} -gt 0 ]] || continue
    printf -v command '%q ' bash "$repo/scriptsFORhuman/v26_8/v26_8_eval_lane.sh" "$gpu" "$step" "$train_root" "$root" "${lane[@]}"; last=$(( ${#lane[@]} - 1 ))
    launch "v26_8_eval_step${step}_gpu${gpu}" "$gpu" "$command" "$runtime_logs/milestones/step$step/gpu${gpu}.log" "$root/${lane[$last]}_STEP${step}/right/metrics_eval.json"
  done ;;
milestone-finalize)
  [[ $# -eq 2 ]] && valid_step "$2" || { usage; exit 2; }; step=$2; root="$eval_root/milestones/step$step"
  mapfile -t active < <(active_cells "$step"); [[ ${#active[@]} -gt 0 ]] || { echo V26_8_NO_ACTIVE_CELLS; exit 0; }
  lane0=(); lane1=(); for i in "${!active[@]}"; do if (( i % 2 == 0 )); then lane0+=("${active[$i]}"); else lane1+=("${active[$i]}"); fi; done
  for gpu in 0 1; do
    if [[ "$gpu" == 0 ]]; then lane=("${lane0[@]}"); else lane=("${lane1[@]}"); fi; [[ ${#lane[@]} -gt 0 ]] || continue
    "$py" "$supervisor" finalize --receipt "$(receipt "v26_8_eval_step${step}_gpu${gpu}")"; require_receipt_pass "v26_8_eval_step${step}_gpu${gpu}"
  done
  "$isaac_py" "$repo/scriptsFORhuman/v26_8/v26_8_reduce.py" --train-root "$train_root" --eval-root "$root" --step "$step" --output "$root/reducer.json"
  mapfile -t stopped < <("$py" - "$root/reducer.json" <<'PY'
import json,sys
for cell in json.load(open(sys.argv[1],encoding='utf-8')).get('stop_cells',[]): print(cell)
PY
)
  for cell in "${stopped[@]}"; do tmux has-session -t "$(run_name "v26_8_train_${cell,,}")" 2>/dev/null && tmux send-keys -t "$(run_name "v26_8_train_${cell,,}")" C-c; done ;;
train-finalize)
  [[ $# -eq 1 && -f "$eval_root/milestones/step3000/reducer.json" ]] || { usage; exit 2; }
  for cell in "${cells[@]}"; do
    "$py" "$supervisor" finalize --receipt "$(receipt "v26_8_train_${cell,,}")" || [[ $? -eq 2 ]]
  done
  "$py" - "$eval_root/milestones/step3000/reducer.json" "$repo/.ai/runtime/runs" "${cells[@]}" <<'PY'
import json,sys
from pathlib import Path
reducer= json.load(open(sys.argv[1],encoding='utf-8'))
run_root=Path(sys.argv[2]); cells=sys.argv[3:]; stopped=set(reducer.get('stop_cells',()))
unexpected=[]; states={}
for cell in cells:
    receipt=run_root/f"v26_8_train_{cell.lower()}_r3a"/"RUN_RECEIPT.json"
    value=json.load(open(receipt,encoding='utf-8')); states[cell]={"state":value.get("state"),"process_returncode":value.get("process_returncode")}
    if cell in stopped:
        if value.get("state") not in {"FAIL","PASS"}: unexpected.append(f"{cell}: stopped receipt not terminal")
    elif value.get("state") != "PASS" or value.get("process_returncode") != 0:
        unexpected.append(f"{cell}: expected PASS/0, got {states[cell]}")
print(json.dumps({"train_receipts":states,"stopped_cells":sorted(stopped)},ensure_ascii=False,indent=2))
if unexpected: raise SystemExit("; ".join(unexpected))
PY
  ;;
closure)
  [[ $# -eq 1 ]] || { usage; exit 2; }; require_gate "$eval_root/milestones/step3000/reducer.json" EXPERIMENT_COMPLETE
  "$py" - "$eval_root/milestones/step3000/reducer.json" "$repo/.ai/runtime/runs" "${cells[@]}" <<'PY'
import json,sys
from pathlib import Path
reducer=json.load(open(sys.argv[1],encoding='utf-8')); stopped=set(reducer.get('stop_cells',())); root=Path(sys.argv[2])
for cell in sys.argv[3:]:
    receipt=json.load(open(root/f"v26_8_train_{cell.lower()}_r3a"/"RUN_RECEIPT.json",encoding='utf-8'))
    if cell in stopped:
        if receipt.get('state') not in {'PASS','FAIL'}: raise SystemExit(f"{cell}: stopped receipt is not terminal")
    elif receipt.get('state') != 'PASS' or receipt.get('process_returncode') != 0:
        raise SystemExit(f"{cell}: train receipt is not PASS/0")
print(json.dumps({'typed_outcomes':reducer.get('typed_outcomes'),'evidence':'EXPERIMENT_PASS'},ensure_ascii=False,indent=2))
PY
  ;;
wave2-branches)
  [[ $# -eq 1 ]] || { usage; exit 2; }
  "$py" -c "import json; x=json.load(open('$eval_root/milestones/step3000/reducer.json',encoding='utf-8')); o=x.get('typed_outcomes'); assert isinstance(o,dict); print(json.dumps({'schema':'a2_piper_base_v26_8_wave2_branch_v1','wave2':o['wave2'],'owner_notification_required_before_launch':True},ensure_ascii=False,indent=2))" ;;
*) usage; exit 2 ;;
esac
