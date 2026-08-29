#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage:
  orchestrate_base_v26_4.sh main --gpus 0,1,2,3 --canonical-key env.config.<frozen_key>
  orchestrate_base_v26_4.sh main-eval --gpus 0,1,2,3 --canonical-key env.config.<frozen_key>
  orchestrate_base_v26_4.sh analyze
  orchestrate_base_v26_4.sh closure
EOF
}

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/usr/bin/python3
supervisor="$repo/.ai/scripts/run_supervisor.py"
v26="$repo/scriptsFORhuman/v26_4"
train_root="$repo/logs_rl/by_batch/base_v26_4_bilateral_grasp_foundation_20260828/main"
eval_root="$repo/logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/main"
evidence_root="$v26/evidence"
foundation_root="$repo/logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828"
source_cont="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
k_evidence="$foundation_root/K/k_kinematics.json"
c_evidence="$foundation_root/C/canonical_identity_proof.json"
c_route="$foundation_root/C/c_route.json"
m_outcome="$foundation_root/M/m_outcome.json"
m_receipt="$foundation_root/M/orchestrator_terminal_receipt.json"

parse_gpus_and_key() {
    [[ ${1:-} == --gpus && ${3:-} == --canonical-key && $# -eq 4 ]] || { usage >&2; exit 2; }
    IFS=, read -r -a gpus <<<"$2"
    [[ ${#gpus[@]} -eq 4 && "${gpus[*]}" == "0 1 2 3" ]] || { echo "v26-4 requires physical GPU0,1,2,3 exactly" >&2; exit 2; }
    canonical_key=$4
    [[ "$canonical_key" =~ ^env\.config\.[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "canonical key must be one env.config leaf" >&2; exit 2; }
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
    local name=$1 gpu=$2 command=$3 output=$4 checkpoint=$5
    local receipt args
    ! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session exists: $name" >&2; exit 1; }
    args=(prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$output" --resource "GPU$gpu" --resource "IsaacSim_GPU$gpu" --checkpoint "$checkpoint")
    receipt=$($python_bin "$supervisor" "${args[@]}")
    $python_bin "$supervisor" launch --receipt "$receipt"
}

require_k_c_gates() {
    $python_bin - "$k_evidence" "$c_evidence" <<'PY'
import json, sys
k_path, c_path = sys.argv[1:]
k = json.load(open(k_path, encoding="utf-8"))
c = json.load(open(c_path, encoding="utf-8"))
k_outcome = k.get("typed_outcome")
if k_outcome not in {"BILATERAL_KINEMATICALLY_SYMMETRIC", "BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET"}:
    raise SystemExit(f"Wave K does not admit canonical M: {k_outcome!r}")
if c.get("status") != "CANONICAL_IDENTITY_PROOF_PASS":
    raise SystemExit(f"Wave C identity proof is not PASS: {c.get('status')!r}")
PY
}

case ${1:-} in
    --help|-h|'') usage; exit 0 ;;
    main)
        parse_gpus_and_key "${@:2}"
        "$python_bin" "$v26/v26_4_resolve_m_route.py" \
            --k-artifact "$k_evidence" --c-route "$c_route" --c-proof "$c_evidence" \
            --train-root "$train_root" --eval-root "$eval_root" --output "$m_outcome" \
            --receipt-output "$m_receipt" --command "$0 $*"
        exit 0
        ;;
    main-eval)
        parse_gpus_and_key "${@:2}"
        [[ -f "$evidence_root/static/source_lock.json" ]] || { echo "formal source lock is missing" >&2; exit 1; }
        $python_bin "$v26/v26_4_capture_source_lock.py" --verify-against "$evidence_root/static/source_lock.json" --output "$evidence_root/static/source_lock_pre_eval_verification.json"
        mkdir -p "$v26/runtime_logs/main_eval"
        names=(C0_CANONICAL_OFF_S0 C0_CANONICAL_OFF_S1 C1_CANONICAL_ON_S0 C1_CANONICAL_ON_S1)
        seeds=(0 1 0 1)
        for gpu in "${gpus[@]}"; do gpu_idle "$gpu"; done
        for index in 0 1 2 3; do
            gpu=${gpus[$index]}; name=${names[$index]}; seed=${seeds[$index]}
            [[ -f "$train_root/$name/model_step_000750.pt" ]] || { echo "main cell incomplete: $name" >&2; exit 1; }
            [[ ! -e "$eval_root/${name}_STEP0125" ]] || { echo "main eval output exists: $name" >&2; exit 1; }
            canonical_bool=false; [[ "$name" == C1_* ]] && canonical_bool=true
            printf -v command '%q ' bash "$v26/run_base_v26_4_main_eval_cell.sh" "$gpu" "$name" "$train_root/$name" "$eval_root" "$seed" "++$canonical_key=$canonical_bool"
            launch_receipt "v26_4_eval_${name,,}" "$gpu" "$command" "$v26/runtime_logs/main_eval/$name.log" "$eval_root/${name}_STEP0750/right/metrics_eval.json"
        done
        ;;
    analyze)
        [[ $# -eq 1 ]] || { usage >&2; exit 2; }
        [[ -f "$evidence_root/static/source_lock.json" ]] || { echo "formal source lock is missing" >&2; exit 1; }
        $python_bin "$v26/v26_4_capture_source_lock.py" --verify-against "$evidence_root/static/source_lock.json" --output "$evidence_root/static/source_lock_pre_analyze_verification.json"
        exec $python_bin "$v26/v26_4_analyze_bilateral_foundation.py" --eval-root "$eval_root" --output "$foundation_root/main_bilateral_foundation.json"
        ;;
    closure)
        [[ $# -eq 1 ]] || { usage >&2; exit 2; }
        [[ -f "$foundation_root/main_bilateral_foundation.json" ]] || { echo "main bilateral analysis missing" >&2; exit 1; }
        exec $python_bin "$v26/v26_4_capture_source_lock.py" --verify-against "$evidence_root/static/source_lock.json" --output "$evidence_root/static/source_lock_exit_verification.json"
        ;;
    *) usage >&2; exit 2 ;;
esac
