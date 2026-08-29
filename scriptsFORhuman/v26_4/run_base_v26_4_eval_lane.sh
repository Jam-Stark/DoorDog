#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 GPU LABEL CHECKPOINT OUTPUT_ROOT SEED CANONICAL_OVERRIDE"
    echo "Runs natural, first-episode-only exact64 evaluation for LEFT then RIGHT."
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
[[ $# -eq 6 ]] || { usage >&2; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
label=$2
checkpoint=$3
output_root=$4
seed=$5
canonical_override=$6

[[ "$gpu" =~ ^[0-3]$ ]] || { echo "v26-4 eval requires physical GPU0..3" >&2; exit 2; }
[[ "$seed" =~ ^[01]$ ]] || { echo "v26-4 eval seed must be 0 or 1" >&2; exit 2; }
[[ -f "$checkpoint" ]] || { echo "eval checkpoint missing: $checkpoint" >&2; exit 2; }
[[ "$canonical_override" == ++env.config.*=true || "$canonical_override" == ++env.config.*=false ]] || {
    echo "canonical override must be one frozen env.config boolean override" >&2
    exit 2
}

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
        ++seed="$seed" ++num_envs=64 \
        ++algo.config.num_mini_batches=1 \
        ++algo.config.eval.num_eval_episodes=64 \
        ++algo.config.eval.eval_num_envs_episodes=true \
        ++algo.config.eval.dump_to_log_metrics=true \
        ++algo.config.eval.a2_diagnostic_trace_enabled=true \
        ++algo.config.eval.a2_diagnostic_reward_terms='[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' \
        ++algo.config.eval.a2_forced_gripper_close_enabled=false \
        ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false \
        ++env.config.a2_v26_3_telemetry_enabled=true \
        ++env.config.a2_v26_door_open_lr="$side" \
        ++env.config.a2_v26_side_permutation_seed="$seed" \
        ++env.config.enable_staged_reset=false \
        ++simulator.config.render_results=false \
        ++env.config.save_rendering_dir="$output_dir/renderings" \
        ++eval_name="V26_4_${label}_${side}" ++eval_output_dir="$output_dir" \
        "$canonical_override"
    for required in metrics_eval.json a2_v14_per_env_records.json stage2_5_step_trace.json a2_eval_diagnostic_metadata.json; do
        [[ -f "$output_dir/$required" ]] || { echo "missing eval artifact: $output_dir/$required" >&2; exit 1; }
    done
done
