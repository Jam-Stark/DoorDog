#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage: run_base_v26_2_route_a.sh GPU LABEL CHECKPOINT OUTPUT_ROOT [SEED] [NUM_ENVS] [RENDER]

Runs exactly one LEFT and one RIGHT natural-start evaluation.  It enables the
v26-2 mechanism trace and therefore requires the implementation-side telemetry
contract; an eval which cannot publish the trace is intentionally a failure.
EOF
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    usage
    exit 0
fi
if [[ $# -lt 4 || $# -gt 7 ]]; then
    usage >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
label=$2
checkpoint=$3
output_root=$4
seed=${5:-1}
num_envs=${6:-64}
render=${7:-false}

if [[ ! "$gpu" =~ ^[0-3]$ ]]; then
    echo "v26-2 Route A requires a physical GPU in 0..3; got $gpu" >&2
    exit 2
fi
if [[ ! -f "$checkpoint" ]]; then
    echo "Route A checkpoint is missing: $checkpoint" >&2
    exit 2
fi
if [[ "$num_envs" -ne 64 ]]; then
    echo "v26-2 Route A is registered for exactly 64 natural episodes per side; got $num_envs" >&2
    exit 2
fi

for side in left right; do
    output_dir="$output_root/$label/$side"
    if [[ -e "$output_dir" ]]; then
        echo "refusing to overwrite Route A output: $output_dir" >&2
        exit 2
    fi
    case "${label%%_*}" in
        C) diagnostic_terms='[push_door_handle,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' ;;
        A) diagnostic_terms='[a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' ;;
        R|W) diagnostic_terms='[a2_stage3_handle_depression,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' ;;
        *)
            echo "Route A label must begin with registered cell C/A/R/W; got $label" >&2
            exit 2
            ;;
    esac
    env CUDA_VISIBLE_DEVICES=0,1,2,3 \
        CUDA_DEVICE_ORDER=PCI_BUS_ID \
        ACCELERATE_TORCH_DEVICE="cuda:$gpu" \
        WANDB_MODE=disabled \
        HYDRA_FULL_ERROR=1 \
        PYTHONPATH="$repo" \
        "$python_bin" -B -m gr00t.rl.eval_agent_trl \
        +ablation=wbmanip/base_v26_eval_natural_start \
        ++checkpoint="$checkpoint" \
        ++checkpoint_load_mode=full ++auto_load_latest=false \
        ++seed="$seed" ++num_envs=64 \
        ++algo.config.num_mini_batches=1 \
        ++algo.config.eval.num_eval_episodes=64 \
        ++algo.config.eval.eval_num_envs_episodes=true \
        ++algo.config.eval.dump_to_log_metrics=true \
        ++algo.config.eval.a2_diagnostic_trace_enabled=true \
        ++algo.config.eval.a2_diagnostic_reward_terms="$diagnostic_terms" \
        ++env.config.a2_v26_door_open_lr="$side" \
        ++env.config.a2_v26_side_permutation_seed="$seed" \
        ++env.config.enable_staged_reset=false \
        ++simulator.config.render_results="$render" \
        ++env.config.save_rendering_dir="$output_dir/renderings" \
        ++eval_name="V26_2_${label}_${side}" \
        ++eval_output_dir="$output_dir"
    for required in metrics_eval.json a2_v14_per_env_records.json stage2_5_step_trace.json a2_eval_diagnostic_metadata.json; do
        if [[ ! -f "$output_dir/$required" ]]; then
            echo "Route A did not produce required telemetry: $output_dir/$required" >&2
            exit 1
        fi
    done
done
