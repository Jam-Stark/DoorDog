#!/usr/bin/env bash
# Pull v26-8 backbone operation entrypoint.  Long Isaac workers are tmux-backed
# and each receipt records the proxy-prefixed command it actually launches.
set -euo pipefail

repo=/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
py=/usr/bin/python3
isaac_py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"
attempt=${PULL_V26_8_ATTEMPT:-1}
case "$attempt" in
  1) attempt_suffix= ;;
  2|3) attempt_suffix="_r$attempt" ;;
  *) echo "At most two pre-policy relaunches are authorized" >&2; exit 2 ;;
esac
run_id="pull_v26_8_backbone_20260905$attempt_suffix"
train_root="$repo/logs_rl/a2_piper_pull_v26_8_backbone/$run_id/train"
eval_root="$repo/logs_eval/a2_piper_pull_v26_8_backbone/$run_id"
runtime_logs="$repo/scriptsFORhuman/pull_v26_8/runtime_logs/$run_id"
source_lock=${PULL_V26_8_SOURCE_LOCK:-"$runtime_logs/source_lock.json"}
g0_root="$eval_root/G0_memory_smoke"
g1_root="$eval_root/G1_wiring"
cells=(P_S0 P_S1 P_S2)

usage() {
  cat >&2 <<'EOF'
usage:
  orchestrate.sh static
  orchestrate.sh g0 2048|1024 | g0-finalize 2048|1024
  orchestrate.sh g1-launch 2048|1024 | g1-finalize
  orchestrate.sh train-launch 2048|1024 | train-finalize
  orchestrate.sh milestone-launch STEP | milestone-finalize STEP
  orchestrate.sh closure
EOF
}

receipt() { echo "$repo/.ai/runtime/runs/$1$attempt_suffix/RUN_RECEIPT.json"; }

gpu_idle() {
  local gpu=$1 uuid
  uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F ', ' -v target="$gpu" '$1 == target { print $2 }')
  [[ -n "$uuid" ]] || { echo "GPU$gpu is not visible" >&2; return 1; }
  ! nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep -Fq "$uuid" || {
    echo "GPU$gpu is busy" >&2
    return 1
  }
}

proxy_prefix() {
  local key encoded prefix="env -u DISPLAY -u XAUTHORITY PULL_V26_8_ATTEMPT=$attempt"
  printf -v encoded '%q' "$source_lock"
  prefix+=" PULL_V26_8_SOURCE_LOCK=$encoded"
  for key in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY; do
    printf -v encoded '%q' "${!key-}"
    prefix+=" $key=$encoded"
  done
  printf '%s' "$prefix"
}

p0_preflight() {
  local name=$1 key output
  output="$runtime_logs/p0_assets/$name.json"
  for key in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY; do
    export "$key=${!key-}"
  done
  "$py" "$repo/scriptsFORhuman/pull_v26_8/p0_assets.py" --output "$output"
}

launch() {
  local name="$1$attempt_suffix" gpu=$2 command=$3 log=$4 expected=$5 created
  ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session exists: $name" >&2; exit 1; }
  p0_preflight "$name"
  command="$(proxy_prefix) $command"
  created=$("$py" "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log" --checkpoint "$expected" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu")
  "$py" - "$created" "$source_lock" <<'PY'
import json,subprocess,sys
from pathlib import Path
path=Path(sys.argv[1]); receipt=json.loads(path.read_text())
receipt["source_lock"]=sys.argv[2]
receipt["git_revision"]=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
receipt["stopping_contract"]="Plan sections 4-8: no policy-based early stop; pre-policy infrastructure retries only under Main, maximum 2 and fresh roots"
path.write_text(json.dumps(receipt,indent=2)+"\n")
PY
  "$py" "$supervisor" launch --receipt "$created"
}

require_gate() {
  "$py" - "$1" "$2" <<'PY'
import json,sys
payload=json.load(open(sys.argv[1],encoding="utf-8"))
if payload.get("status") != sys.argv[2]:
    raise SystemExit(f"gate {sys.argv[1]}={payload.get('status')!r}, expected {sys.argv[2]!r}")
PY
}

require_receipt_pass() {
  "$py" - "$(receipt "$1")" <<'PY'
import json,sys
payload=json.load(open(sys.argv[1],encoding="utf-8"))
if payload.get("state") != "PASS" or payload.get("process_returncode") != 0:
    raise SystemExit(f"receipt is not PASS/0: {sys.argv[1]}")
PY
}

require_runtime_pass() {
  "$py" - "$1/runtime_result.json" <<'PY'
import json,sys
payload=json.load(open(sys.argv[1],encoding="utf-8"))
if payload.get("child_returncode") != 0 or payload.get("wrapper_returncode") != 0 or payload.get("actual_success") is not True:
    raise SystemExit(f"runtime result is not child/wrapper PASS: {sys.argv[1]}")
PY
}

require_g0() {
  local envs=$1 root="$g0_root/num_envs$1"
  [[ -f "$root/g0_smoke.json" ]] || { echo "G0 $envs artifact missing" >&2; return 1; }
  require_gate "$root/g0_smoke.json" G0_PASS
  require_receipt_pass "pull_v26_8_g0_${envs}"
  require_runtime_pass "$root"
}

budget_for_envs() {
  case "$1" in
    2048) echo 4000 ;;
    1024) echo 6000 ;;
    *) echo "num_envs must be 2048 or 1024" >&2; return 2 ;;
  esac
}

milestones_for_envs() {
  case "$1" in
    2048) echo "500 1000 1500 2000 2500 3000 3500 4000" ;;
    1024) echo "750 1500 2250 3000 3750 4500 5250 6000" ;;
    *) return 2 ;;
  esac
}

read_num_envs() {
  "$isaac_py" - "$train_root/P_S0/resolved_config.yaml" <<'PY'
import sys,yaml
print(yaml.safe_load(open(sys.argv[1],encoding="utf-8"))["num_envs"])
PY
}

valid_milestone() {
  local step=$1 envs item
  envs=$(read_num_envs)
  for item in $(milestones_for_envs "$envs"); do [[ "$item" == "$step" ]] && return 0; done
  return 1
}

g0_worker() {
  local envs=$1 root=$2 batches=5
  local selector=wbmanip/pull_v26_8_backbone_P_S0
  local output="$root"
  local runtime=(CUDA_VISIBLE_DEVICES=1 CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo")
  local common=(+exp=wbmanip/door_open_a2_pull_v26_backbone_lstm +ablation="$selector" checkpoint=null checkpoint_load_mode=full auto_load_latest=false seed=0 num_envs="$envs" algo.trl.num_total_batches="$batches" callbacks.model_save.save_frequency="$batches" headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir="$output" output_dir="$output/output" project_name=a2_piper_pull_v26_8_backbone experiment_name=P_S0 +device=cuda:0)
  env "${runtime[@]}" "$isaac_py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
  "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/verify.py" --config "$output/resolved_config.yaml" --cell P_S0 --smoke
  "$py" "$repo/scriptsFORhuman/pull_v26_8/p0_assets.py" --output "$output/p0_assets.json"
  "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/runner.py" --output "$output" --gpu 1 --required model_step_000005.pt -- env "${runtime[@]}" "$isaac_py" -B -m gr00t.rl.train_agent_trl "${common[@]}"
  "$py" - "$output/g0_smoke.json" "$envs" <<'PY'
import json,sys
from pathlib import Path
path,envs=sys.argv[1:]
runtime=json.loads((Path(path).parent/"runtime_result.json").read_text())
passed=runtime["minimum_headroom_mib"] >= 2048
with open(path,"x",encoding="utf-8") as stream:
    json.dump({"schema":"a2_piper_pull_v26_8_g0_v1","status":"G0_PASS" if passed else "G0_MEMORY_INSUFFICIENT","num_envs":int(envs),"batches":5,"peak_memory_mib":runtime["peak_memory_mib"],"minimum_headroom_mib":runtime["minimum_headroom_mib"],"decision":"Main freezes this size only after measured minimum headroom is at least 2048 MiB"},stream,indent=2)
    stream.write("\n")
if not passed: raise SystemExit(2)
PY
}

g1_eval() {
  local root=$1 label=$2 side=$3 mirror=$4 checkpoint=$5
  local output="$root/$label"
  local runtime=(CUDA_VISIBLE_DEVICES=0 CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo")
  local common=(checkpoint="$checkpoint" checkpoint_load_mode=full ++auto_load_latest=false ++seed=0 ++num_envs=64 ++headless=true ++use_wandb=false ++algo.config.num_mini_batches=1 ++algo.config.eval.num_eval_episodes=64 ++algo.config.eval.eval_num_envs_episodes=true ++algo.config.eval.dump_to_log_metrics=true ++algo.config.eval.a2_diagnostic_trace_enabled=true ++algo.config.eval.a2_diagnostic_reward_terms='[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge]' ++env.config.a2_door_open_lr_distribution="$side" ++env.config.a2_door_open_lr_permutation_seed=0 ++env.config.enable_staged_reset=false ++env.config.a2_pull_v6_stage4_bank_enabled=false ++env.config.a2_pull_v61_late_state_bank_enabled=false ++env.config.a2_v26_6_side_mirrored_handle_offset_enabled="$mirror" ++simulator.config.render_results=false ++simulator.config.cameras.enable_cameras=false ++eval_name="PULL_V26_8_G1_${label}" ++eval_output_dir="$output" hydra.run.dir="$output" ++env.config.max_episode_length_s=0.02 +device=cuda:0)
  mkdir -p "$output"
  env "${runtime[@]}" "$isaac_py" -B -m gr00t.rl.eval_agent_trl "${common[@]}" --cfg job --resolve > "$output/eval_overrides.yaml"
  "$py" "$repo/scriptsFORhuman/pull_v26_8/p0_assets.py" --output "$output/p0_assets.json"
  "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/runner.py" --output "$output" --gpu 0 --required metrics_eval.json --required a2_v14_per_env_records.json --required stage2_5_step_trace.json --required a2_eval_diagnostic_metadata.json --required .hydra/runtime_config.yaml -- env "${runtime[@]}" "$isaac_py" -B -m gr00t.rl.eval_agent_trl "${common[@]}"
  "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/verify.py" --config "$output/.hydra/runtime_config.yaml" --cell P_S0 --eval-side "$side" --smoke
}

g1_worker() {
  local root=$1
  local train="$root/train" checkpoint selector
  selector=wbmanip/pull_v26_8_backbone_P_S0
  local runtime=(CUDA_VISIBLE_DEVICES=0 CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo")
  local common=(+exp=wbmanip/door_open_a2_pull_v26_backbone_lstm +ablation="$selector" checkpoint=null checkpoint_load_mode=full auto_load_latest=false seed=0 num_envs=64 algo.trl.num_total_batches=5 callbacks.model_save.save_frequency=5 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir="$train" output_dir="$train/output" project_name=a2_piper_pull_v26_8_backbone experiment_name=P_S0 +device=cuda:0)
  mkdir -p "$train"
  env "${runtime[@]}" "$isaac_py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$train/resolved_config.yaml"
  "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/verify.py" --config "$train/resolved_config.yaml" --cell P_S0 --smoke
  "$py" "$repo/scriptsFORhuman/pull_v26_8/p0_assets.py" --output "$train/p0_assets.json"
  "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/runner.py" --output "$train" --gpu 0 --required model_step_000005.pt -- env "${runtime[@]}" "$isaac_py" -B -m gr00t.rl.train_agent_trl "${common[@]}"
  checkpoint="$train/model_step_000005.pt"
  g1_eval "$root" old bilateral false "$checkpoint"
  g1_eval "$root" fixed bilateral true "$checkpoint"
  g1_eval "$root" right_old right false "$checkpoint"
  g1_eval "$root" right_fixed right true "$checkpoint"
  "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/g1_reduce.py" --old "$root/old/metrics_eval.json" --fixed "$root/fixed/metrics_eval.json" --right-old "$root/right_old/metrics_eval.json" --right-fixed "$root/right_fixed/metrics_eval.json" --output "$root/g1_wiring.json"
}

case ${1:-} in
  static)
    [[ $# -eq 1 && ! -e "$source_lock" ]] || { usage; exit 2; }
    mkdir -p "$runtime_logs"
    "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/verify.py" --output "$source_lock"
    exec "$isaac_py" -m pytest -q "$repo/gr00t/rl/tests/test_a2_v26_6_handle_offset_mirror.py"
    ;;
  g0)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    envs=$2; budget_for_envs "$envs" >/dev/null
    require_gate "$source_lock" SOURCE_FROZEN
    root="$g0_root/num_envs$envs"
    [[ ! -e "$root" ]] || { echo "fresh G0 root required: $root" >&2; exit 1; }
    gpu_idle 1; mkdir -p "$root" "$runtime_logs/g0"
    printf -v command '%q ' bash "$repo/scriptsFORhuman/pull_v26_8/orchestrate.sh" _g0-worker "$envs" "$root"
    launch "pull_v26_8_g0_${envs}" 1 "$command" "$runtime_logs/g0/num_envs${envs}.log" "$root/g0_smoke.json"
    ;;
  g0-finalize)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    envs=$2; budget_for_envs "$envs" >/dev/null
    "$py" "$supervisor" finalize --receipt "$(receipt "pull_v26_8_g0_${envs}")"
    require_g0 "$envs"
    ;;
  g1-launch)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    envs=$2; budget_for_envs "$envs" >/dev/null
    require_gate "$source_lock" SOURCE_FROZEN; require_g0 "$envs"
    [[ ! -e "$g1_root" ]] || { echo "fresh G1 root required: $g1_root" >&2; exit 1; }
    gpu_idle 0; mkdir -p "$g1_root" "$runtime_logs/g1"
    printf -v command '%q ' bash "$repo/scriptsFORhuman/pull_v26_8/orchestrate.sh" _g1-worker "$g1_root"
    launch pull_v26_8_g1 0 "$command" "$runtime_logs/g1/g1.log" "$g1_root/g1_wiring.json"
    ;;
  g1-finalize)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    "$py" "$supervisor" finalize --receipt "$(receipt pull_v26_8_g1)"
    require_receipt_pass pull_v26_8_g1; require_gate "$g1_root/g1_wiring.json" G1_PASS
    for output in "$g1_root/train" "$g1_root/old" "$g1_root/fixed" "$g1_root/right_old" "$g1_root/right_fixed"; do require_runtime_pass "$output"; done
    ;;
  train-launch)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    envs=$2; batches=$(budget_for_envs "$envs")
    require_gate "$source_lock" SOURCE_FROZEN; require_g0 "$envs"; require_gate "$g1_root/g1_wiring.json" G1_PASS
    [[ ! -e "$train_root" ]] || { echo "fresh Wave-1 train root required: $train_root" >&2; exit 1; }
    mkdir -p "$train_root" "$runtime_logs/train"
    for cell in "${cells[@]}"; do
      case "$cell" in P_S0) gpu=1;; P_S1) gpu=2;; P_S2) gpu=3;; esac
      gpu_idle "$gpu"
      output="$train_root/$cell"
      printf -v command '%q ' env PULL_V26_8_NUM_ENVS="$envs" PULL_V26_8_TOTAL_BATCHES="$batches" bash "$repo/scriptsFORhuman/pull_v26_8/train_cell.sh" "$gpu" "$cell" "$output"
      launch "pull_v26_8_train_${cell,,}" "$gpu" "$command" "$runtime_logs/train/$cell.log" "$output/model_step_$(printf '%06d' "$batches").pt"
    done
    ;;
  train-finalize)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    for cell in "${cells[@]}"; do
      "$py" "$supervisor" finalize --receipt "$(receipt "pull_v26_8_train_${cell,,}")"
      require_receipt_pass "pull_v26_8_train_${cell,,}"; require_runtime_pass "$train_root/$cell"
    done
    ;;
  milestone-launch)
    [[ $# -eq 2 ]] && valid_milestone "$2" || { usage; exit 2; }
    step=$2; root="$eval_root/milestones/step$step"; budget=$(read_num_envs)
    require_gate "$g1_root/g1_wiring.json" G1_PASS
    [[ ! -e "$root" ]] || { echo "fresh milestone root required: $root" >&2; exit 1; }
    for cell in "${cells[@]}"; do [[ -f "$train_root/$cell/model_step_$(printf '%06d' "$step").pt" ]] || { echo "checkpoint missing: $cell step$step" >&2; exit 1; }; done
    gpu_idle 0; mkdir -p "$root" "$runtime_logs/milestones/step$step"
    printf -v command '%q ' bash "$repo/scriptsFORhuman/pull_v26_8/eval_lane.sh" 0 "$step" "$train_root" "$root" "${cells[@]}"
    launch "pull_v26_8_eval_step$step" 0 "$command" "$runtime_logs/milestones/step$step/gpu0.log" "$root/P_S2_STEP${step}/right/metrics_eval.json"
    ;;
  milestone-finalize)
    [[ $# -eq 2 ]] && valid_milestone "$2" || { usage; exit 2; }
    step=$2; root="$eval_root/milestones/step$step"
    "$py" "$supervisor" finalize --receipt "$(receipt "pull_v26_8_eval_step$step")"
    require_receipt_pass "pull_v26_8_eval_step$step"
    for cell in "${cells[@]}"; do for side in left right; do require_runtime_pass "$root/${cell}_STEP${step}/$side"; done; done
    exec "$isaac_py" "$repo/scriptsFORhuman/pull_v26_8/reduce.py" --train-root "$train_root" --eval-root "$root" --step "$step" --output "$root/reducer.json"
    ;;
  closure)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    if [[ -f "$eval_root/closure.json" ]]; then
      exec "$py" - "$eval_root/closure.json" <<'PY'
import json,sys
payload=json.load(open(sys.argv[1],encoding="utf-8"))
if payload["status"] != "CLOSED_AT_G1_HARD_STOP":
    raise SystemExit("unexpected pre-matrix closure status")
print(json.dumps(payload,ensure_ascii=False,indent=2))
PY
    fi
    envs=$(read_num_envs); endpoint=$(budget_for_envs "$envs")
    [[ -f "$eval_root/milestones/step$endpoint/reducer.json" ]] || { echo "endpoint reducer missing" >&2; exit 1; }
    "$py" - "$eval_root/milestones/step$endpoint/reducer.json" <<'PY'
import json,sys
payload=json.load(open(sys.argv[1],encoding="utf-8"))
if payload.get("status") != "EXPERIMENT_COMPLETE":
    raise SystemExit(f"endpoint status={payload.get('status')!r}")
print(json.dumps({"route":payload.get("route"),"opening_full_labels":payload.get("opening_full_labels"),"wave2_eligible":payload.get("wave2_eligible"),"owner_notification_required_before_wave2":payload.get("wave2_eligible") is True},ensure_ascii=False,indent=2))
PY
    ;;
  _g0-worker)
    [[ $# -eq 3 ]] || exit 2
    g0_worker "$2" "$3"
    ;;
  _g1-worker)
    [[ $# -eq 2 ]] || exit 2
    g1_worker "$2"
    ;;
  *) usage; exit 2 ;;
esac
