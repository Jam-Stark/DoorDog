#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage:
  orchestrate_base_v26_3.sh diagnostics --gpus 0,1,2,3
  orchestrate_base_v26_3.sh main --gpus 0,1,2,3
  orchestrate_base_v26_3.sh main-eval --gpus 0,1,2,3
  orchestrate_base_v26_3.sh conditional --gpus 0,1,2,3
  orchestrate_base_v26_3.sh final-eval --gpus 0,1,2,3
  orchestrate_base_v26_3.sh render --gpu 0
  orchestrate_base_v26_3.sh closure
EOF
}

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
supervisor="$repo/.ai/scripts/run_supervisor.py"
v26="$repo/scriptsFORhuman/v26_3"
train_root="$repo/logs_rl/by_batch/base_v26_3_event_time_creation_20260827/main"
eval_root="$repo/logs_eval/base_v26/v26_3_event_time_creation_20260827/main"
diagnostic_root="$repo/logs_eval/base_v26/v26_3_event_time_creation_20260827/diagnostics"
source_cont="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
source_w="$repo/logs_rl/by_batch/base_v26_2_pull_derived_20260825/wave1/W/model_step_000750.pt"

parse_gpus() {
    [[ ${1:-} == --gpus && $# -eq 2 ]] || { usage >&2; exit 2; }
    IFS=, read -r -a gpus <<<"$2"
    [[ ${#gpus[@]} -eq 4 ]] || { echo "exactly four GPUs are required" >&2; exit 2; }
    [[ "${gpus[*]}" == "0 1 2 3" ]] || {
        echo "canonical v26-3 allocation is physical GPU0,1,2,3" >&2
        exit 2
    }
}

gpu_idle() {
    local index=$1 uuid
    uuid=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F ', ' -v target="$index" '$1 == target { print $2 }')
    [[ -n "$uuid" ]] || { echo "GPU$index is not visible" >&2; return 1; }
    if nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep -Fq "$uuid"; then
        echo "GPU$index already has a compute process" >&2
        return 1
    fi
}

launch_receipt() {
    local name=$1 gpu=$2 command=$3 output=$4 checkpoint=${5:-}
    local receipt args
    ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session exists: $name" >&2; exit 1; }
    args=(prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$output" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu")
    [[ -z "$checkpoint" ]] || args+=(--checkpoint "$checkpoint")
    receipt=$(python3 "$supervisor" "${args[@]}")
    python3 "$supervisor" launch --receipt "$receipt"
}

case ${1:-} in
    --help|-h|'') usage; exit 0 ;;
    diagnostics)
        parse_gpus "${@:2}"
        [[ -f "$source_w" ]] || { echo "missing W diagnostic source: $source_w" >&2; exit 1; }
        mkdir -p "$v26/runtime_logs/diagnostics"
        lanes=(D0 E1 E2 D3)
        for gpu in "${gpus[@]}"; do gpu_idle "$gpu"; done
        for index in 0 1 2 3; do
            gpu=${gpus[$index]}; lane=${lanes[$index]}
            [[ ! -e "$diagnostic_root/$lane" ]] || { echo "diagnostic output exists: $lane" >&2; exit 1; }
            printf -v command '%q ' bash "$v26/run_base_v26_3_diagnostic_lane.sh" "$gpu" "$lane" "$source_w" "$diagnostic_root" 1
            launch_receipt "v26_3_diag_${lane,,}" "$gpu" "$command" "$v26/runtime_logs/diagnostics/$lane.log" "$diagnostic_root/$lane/right/metrics_eval.json"
        done
        ;;
    main)
        parse_gpus "${@:2}"
        [[ -f "$source_cont" ]] || { echo "missing CONT source: $source_cont" >&2; exit 1; }
        f_decision="$diagnostic_root/F/f_decision.json"
        [[ -f "$diagnostic_root/diagnostic_decision.json" && -f "$f_decision" ]] || { echo "diagnostic/F decision is not frozen" >&2; exit 1; }
        effort_cap=$(python3 - "$f_decision" <<'PY'
import json, sys
d=json.load(open(sys.argv[1], encoding='utf-8'))
v=d.get('selected_effort_limit_nm')
if v not in (10, 20, 40): raise SystemExit('invalid frozen effort cap')
print(int(v))
PY
        )
        mkdir -p "$v26/runtime_logs/main"
        cells=(M0 M0 M1 M1); seeds=(0 1 0 1); names=(M0_S0 M0_S1 M1_S0 M1_S1)
        for gpu in "${gpus[@]}"; do gpu_idle "$gpu"; done
        for index in 0 1 2 3; do
            gpu=${gpus[$index]}; cell=${cells[$index]}; seed=${seeds[$index]}; name=${names[$index]}
            [[ ! -e "$train_root/$name" ]] || { echo "main output exists: $name" >&2; exit 1; }
            printf -v command '%q ' bash "$v26/run_base_v26_3_train_cell.sh" "$gpu" "$cell" "$source_cont" "$train_root/$name" "$seed" 4096 750 125 "$effort_cap"
            launch_receipt "v26_3_main_${name,,}" "$gpu" "$command" "$v26/runtime_logs/main/$name.log" "$train_root/$name/model_step_000750.pt"
        done
        ;;
    main-eval)
        parse_gpus "${@:2}"
        mkdir -p "$v26/runtime_logs/main_eval"
        names=(M0_S0 M0_S1 M1_S0 M1_S1); seeds=(0 1 0 1)
        for gpu in "${gpus[@]}"; do gpu_idle "$gpu"; done
        for index in 0 1 2 3; do
            gpu=${gpus[$index]}; name=${names[$index]}; seed=${seeds[$index]}
            [[ -f "$train_root/$name/model_step_000750.pt" ]] || { echo "main cell incomplete: $name" >&2; exit 1; }
            [[ ! -e "$eval_root/${name}_STEP0125" ]] || { echo "main eval output exists: $name" >&2; exit 1; }
            printf -v command '%q ' bash "$v26/run_base_v26_3_main_eval_cell.sh" "$gpu" "$name" "$train_root/$name" "$eval_root" "$seed"
            launch_receipt "v26_3_eval_${name,,}" "$gpu" "$command" "$v26/runtime_logs/main_eval/$name.log" "$eval_root/${name}_STEP0750/right/metrics_eval.json"
        done
        ;;
    conditional)
        parse_gpus "${@:2}"
        exec python3 "$v26/v26_3_analyze_mechanism.py" --phase conditional --eval-root "$eval_root" --diagnostic-root "$diagnostic_root" --output "$diagnostic_root/conditional_decision.json"
        ;;
    final-eval)
        parse_gpus "${@:2}"
        exec python3 "$v26/v26_3_analyze_mechanism.py" --phase final --eval-root "$eval_root" --diagnostic-root "$diagnostic_root" --output "$repo/logs_eval/base_v26/v26_3_event_time_creation_20260827/final_eval_validation.json"
        ;;
    render)
        [[ ${2:-} == --gpu && $# -eq 3 && ${3:-} =~ ^[0-3]$ ]] || { usage >&2; exit 2; }
        analysis="$repo/logs_eval/base_v26/v26_3_event_time_creation_20260827/main_mechanism.json"
        [[ -f "$analysis" ]] || { echo "main analysis missing" >&2; exit 1; }
        read -r label checkpoint < <(python3 - "$analysis" <<'PY'
import json, sys
d=json.load(open(sys.argv[1], encoding='utf-8'))
s=d.get('selected_render') or {}
if not isinstance(s.get('label'), str) or not isinstance(s.get('checkpoint'), str):
    raise SystemExit('analysis has no selected render')
print(s['label'], s['checkpoint'])
PY
        )
        exec bash "$v26/launch_base_v26_3_selected_render.sh" --launch "$label" "$checkpoint" "$3"
        ;;
    closure)
        [[ $# -eq 1 ]] || { usage >&2; exit 2; }
        exec python3 "$v26/v26_3_analyze_mechanism.py" --phase closure --eval-root "$eval_root" --diagnostic-root "$diagnostic_root" --output "$repo/logs_eval/base_v26/v26_3_event_time_creation_20260827/closure_evidence.json"
        ;;
    *) usage >&2; exit 2 ;;
esac
