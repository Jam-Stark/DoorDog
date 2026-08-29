#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 GPU LABEL CHECKPOINT OUTPUT_ROOT MODE [SEED] [NUM_ENVS] [RENDER]"
    echo "MODE: NATURAL | D0 | E1 | E2 | D3"
}
if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
if [[ $# -lt 5 || $# -gt 8 ]]; then usage >&2; exit 2; fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
label=$2
checkpoint=$3
output_root=$4
mode=$5
seed=${6:-0}
num_envs=${7:-64}
render=${8:-false}

[[ "$gpu" =~ ^[0-3]$ ]] || { echo "v26-3 eval requires physical GPU0..3" >&2; exit 2; }
[[ -f "$checkpoint" ]] || { echo "eval checkpoint missing: $checkpoint" >&2; exit 2; }
[[ "$num_envs" -gt 0 ]] || { echo "num_envs must be positive" >&2; exit 2; }
case "$mode" in NATURAL|D0|E1|E2|D3) ;; *) usage >&2; exit 2 ;; esac

case "$label" in
    *M1*|*CREATE*) diagnostic_terms='[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' ;;
    *) diagnostic_terms='[a2_stage3_handle_depression,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' ;;
esac
extra=()
case "$mode" in
    NATURAL)
        extra+=(
            ++algo.config.eval.a2_forced_gripper_close_enabled=false
            ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false
        )
        ;;
    D0)
        extra+=(
            ++algo.config.eval.a2_forced_gripper_close_enabled=false
            ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false
            ++env.config.a2_v26_3_telemetry_enabled=true
            ++env.config.a2_v26_3_handle_creation_scale=0.0
            ++rewards.reward_scales.a2_stage3_handle_creation=0.0
        )
        ;;
    E1)
        extra+=(
            ++algo.config.eval.a2_forced_gripper_close_enabled=false
            ++env.config.a2_v26_3_telemetry_enabled=true
            ++env.config.a2_v26_3_handle_creation_scale=0.0
            ++rewards.reward_scales.a2_stage3_handle_creation=0.0
            ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=true
        )
        ;;
    E2)
        extra+=(
            ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false
            ++env.config.a2_v26_3_telemetry_enabled=true
            ++env.config.a2_v26_3_handle_creation_scale=0.0
            ++rewards.reward_scales.a2_stage3_handle_creation=0.0
            ++algo.config.eval.a2_forced_gripper_close_enabled=true
            ++algo.config.eval.a2_forced_gripper_close_stages='[3,4]'
        )
        ;;
    D3)
        extra+=(
            ++algo.config.eval.a2_forced_gripper_close_enabled=false
            ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false
            ++env.config.a2_v26_3_telemetry_enabled=true
            ++env.config.a2_v26_3_handle_creation_scale=0.0
            ++rewards.reward_scales.a2_stage3_handle_creation=0.0
            ++env.config.a2_hold_diagnostic_contact_detail_enabled=true
        )
        ;;
esac

for side in left right; do
    output_dir="$output_root/$label/$side"
    [[ ! -e "$output_dir" ]] || { echo "refusing to overwrite eval output: $output_dir" >&2; exit 2; }
    env CUDA_VISIBLE_DEVICES=0,1,2,3 \
        CUDA_DEVICE_ORDER=PCI_BUS_ID \
        ACCELERATE_TORCH_DEVICE="cuda:$gpu" \
        WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 PYTHONPATH="$repo" \
        "$python_bin" -B -m gr00t.rl.eval_agent_trl \
        +ablation=wbmanip/base_v26_eval_natural_start \
        ++checkpoint="$checkpoint" ++checkpoint_load_mode=full ++auto_load_latest=false \
        ++seed="$seed" ++num_envs="$num_envs" \
        ++algo.config.num_mini_batches=1 \
        ++algo.config.eval.num_eval_episodes="$num_envs" \
        ++algo.config.eval.eval_num_envs_episodes=true \
        ++algo.config.eval.dump_to_log_metrics=true \
        ++algo.config.eval.a2_diagnostic_trace_enabled=true \
        ++algo.config.eval.a2_diagnostic_reward_terms="$diagnostic_terms" \
        ++env.config.a2_v26_door_open_lr="$side" \
        ++env.config.a2_v26_side_permutation_seed="$seed" \
        ++env.config.enable_staged_reset=false \
        ++simulator.config.render_results="$render" \
        ++env.config.save_rendering_dir="$output_dir/renderings" \
        ++eval_name="V26_3_${label}_${side}" ++eval_output_dir="$output_dir" \
        "${extra[@]}"
    for required in metrics_eval.json a2_v14_per_env_records.json stage2_5_step_trace.json a2_eval_diagnostic_metadata.json; do
        [[ -f "$output_dir/$required" ]] || { echo "missing eval artifact: $output_dir/$required" >&2; exit 1; }
    done
done
