#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage: run_base_v26_2_cell.sh GPU CELL RAW_HANDLE GATED_DEPRESSION NEAR_CLOSED CHECKPOINT OUTPUT_DIR [SEED] [NUM_ENVS] [BATCHES] [SAVE_FREQUENCY]

CELL must be one of C, A, R, W, W_RELAY_S0, W_RELAY_S1.  The frozen C/A/R/W
matrix is enforced here so launchers cannot accidentally create an unregistered
reward combination.  This command runs one Isaac Sim process when invoked.
EOF
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    usage
    exit 0
fi
if [[ $# -lt 7 || $# -gt 11 ]]; then
    usage >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
raw_handle=$3
gated_depression=$4
near_closed=$5
checkpoint=$6
output_dir=$7
seed=${8:-1}
num_envs=${9:-4096}
batches=${10:-750}
save_frequency=${11:-250}

case "$cell:$raw_handle:$gated_depression:$near_closed" in
    C:6:0:0.1|A:0:0:0.1|R:0:6:0.1|W:0:6:0.25|W_RELAY_S0:0:6:0.25|W_RELAY_S1:0:6:0.25) ;;
    *)
        echo "unregistered v26-2 factor tuple: $cell raw=$raw_handle depression=$gated_depression near_closed=$near_closed" >&2
        exit 2
        ;;
esac
case "$cell" in
    C) ablation=wbmanip/base_v26_2_C_RAW6_T010 ;;
    A) ablation=wbmanip/base_v26_2_A_RAW0_DEP0_T010 ;;
    R) ablation=wbmanip/base_v26_2_R_RAW0_DEP6_T010 ;;
    W|W_RELAY_S0|W_RELAY_S1) ablation=wbmanip/base_v26_2_W_RAW0_DEP6_T025 ;;
esac
if [[ ! "$gpu" =~ ^[0-3]$ ]]; then
    echo "v26-2 requires a physical GPU in 0..3; got $gpu" >&2
    exit 2
fi
if [[ ! -f "$checkpoint" ]]; then
    echo "source checkpoint is missing: $checkpoint" >&2
    exit 2
fi
if [[ -e "$output_dir" ]]; then
    echo "refusing to overwrite v26-2 output: $output_dir" >&2
    exit 2
fi
if [[ "$num_envs" -le 0 || "$batches" -le 0 || "$save_frequency" -le 0 ]]; then
    echo "num_envs, batches, and save_frequency must be positive" >&2
    exit 2
fi
if [[ $((num_envs % 2)) -ne 0 ]]; then
    echo "v26-2 bilateral training requires an even num_envs; got $num_envs" >&2
    exit 2
fi

mkdir -p "$output_dir"
env CUDA_VISIBLE_DEVICES=0,1,2,3 \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    ACCELERATE_TORCH_DEVICE="cuda:$gpu" \
    WANDB_MODE=disabled \
    HYDRA_FULL_ERROR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="$repo" \
    "$python_bin" -B -m gr00t.rl.train_agent_trl \
    +exp=wbmanip/door_open_a2_base_lstm \
    +ablation="$ablation" \
    checkpoint="$checkpoint" \
    checkpoint_load_mode=policy_only \
    policy_only_load_actor_rms=true \
    auto_load_latest=false \
    seed="$seed" \
    num_envs="$num_envs" \
    algo.trl.num_total_batches="$batches" \
    callbacks.model_save.save_frequency="$save_frequency" \
    env.config.a2_v26_side_permutation_seed="$seed" \
    env.config.a2_v26_2_handle_depression_scale="$gated_depression" \
    rewards.reward_scales.push_door_handle="$raw_handle" \
    rewards.reward_scales.a2_stage3_handle_depression="$gated_depression" \
    env.config.a2_stage3_unlatch_near_closed_hinge_threshold="$near_closed" \
    headless=true use_wandb=false \
    simulator.config.render_results=false \
    simulator.config.cameras.enable_cameras=false \
    experiment_dir="$output_dir" \
    output_dir="$output_dir/output" \
    project_name=base_v26_2_pull_derived \
    experiment_name="$cell" \
    v26_cell="$cell" \
    v26_phase="V26_2_WAVE1_OR_RELAY"

expected="$output_dir/model_step_$(printf '%06d' "$batches").pt"
if [[ ! -f "$expected" ]]; then
    echo "training exited without expected checkpoint: $expected" >&2
    exit 1
fi
