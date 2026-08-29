#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 GPU CELL CHECKPOINT OUTPUT_DIR SEED CANONICAL_OVERRIDE"
    echo "CANONICAL_OVERRIDE is the frozen Hydra override, for example ++env.config.<frozen_key>=true"
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
[[ $# -eq 6 ]] || { usage >&2; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
checkpoint=$3
output_dir=$4
seed=$5
canonical_override=$6
source_cont="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"

[[ "$gpu" =~ ^[0-3]$ ]] || { echo "v26-4 training requires physical GPU0..3" >&2; exit 2; }
[[ "$seed" =~ ^[01]$ ]] || { echo "v26-4 seed must be 0 or 1" >&2; exit 2; }
[[ "$checkpoint" == "$source_cont" && -f "$checkpoint" ]] || { echo "v26-4 source must be canonical CONT_STEP2000: $checkpoint" >&2; exit 2; }
[[ ! -e "$output_dir" ]] || { echo "refusing to overwrite v26-4 output: $output_dir" >&2; exit 2; }
[[ "$canonical_override" == ++env.config.*=true || "$canonical_override" == ++env.config.*=false ]] || {
    echo "canonical override must be one frozen env.config boolean override" >&2
    exit 2
}

case "$cell" in
    C0_CANONICAL_OFF) ablation=wbmanip/base_v26_4_C0_CANONICAL_OFF; expected_bool=false ;;
    C1_CANONICAL_ON) ablation=wbmanip/base_v26_4_C1_CANONICAL_ON; expected_bool=true ;;
    *) echo "registered v26-4 cell is C0_CANONICAL_OFF or C1_CANONICAL_ON; got $cell" >&2; exit 2 ;;
esac
[[ "$canonical_override" == *"=$expected_bool" ]] || { echo "cell/canonical override mismatch" >&2; exit 2; }

cell_id="V26_4_${cell}_S${seed}"
common=(
    +exp=wbmanip/door_open_a2_base_lstm
    +ablation="$ablation"
    checkpoint="$checkpoint"
    checkpoint_load_mode=policy_only
    policy_only_load_actor_rms=true
    auto_load_latest=false
    seed="$seed"
    num_envs=4096
    algo.trl.num_total_batches=750
    callbacks.model_save.save_frequency=125
    env.config.a2_v26_side_permutation_seed="$seed"
    headless=true
    use_wandb=false
    simulator.config.render_results=false
    simulator.config.cameras.enable_cameras=false
    experiment_dir="$output_dir"
    output_dir="$output_dir/output"
    project_name=base_v26_4_bilateral_grasp_foundation
    experiment_name="$cell_id"
    v26_cell="$cell_id"
    v26_phase=V26_4_BILATERAL_GRASP_FOUNDATION
    "$canonical_override"
)
runtime_env=(
    CUDA_VISIBLE_DEVICES=0,1,2,3
    CUDA_DEVICE_ORDER=PCI_BUS_ID
    ACCELERATE_TORCH_DEVICE="cuda:$gpu"
    WANDB_MODE=disabled
    HYDRA_FULL_ERROR=1
    PYTHONUNBUFFERED=1
    PYTHONPATH="$repo"
)

mkdir -p "$output_dir"
env "${runtime_env[@]}" "$python_bin" -B -m gr00t.rl.train_agent_trl \
    "${common[@]}" --cfg job --resolve > "$output_dir/resolved_config.yaml"
env "${runtime_env[@]}" "$python_bin" -B -m gr00t.rl.train_agent_trl "${common[@]}"

expected="$output_dir/model_step_000750.pt"
[[ -f "$expected" ]] || { echo "training exited without checkpoint $expected" >&2; exit 1; }
