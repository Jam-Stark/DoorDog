#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 GPU CELL CHECKPOINT OUTPUT_DIR [SEED] [NUM_ENVS] [BATCHES] [SAVE_FREQUENCY] [GRIPPER_EFFORT_CAP]"
}
if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
if [[ $# -lt 4 || $# -gt 9 ]]; then usage >&2; exit 2; fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
checkpoint=$3
output_dir=$4
seed=${5:-0}
num_envs=${6:-4096}
batches=${7:-750}
save_frequency=${8:-125}
gripper_effort_cap=${9:-10}

[[ "$gpu" =~ ^[0-3]$ ]] || { echo "v26-3 training requires physical GPU0..3" >&2; exit 2; }
[[ "$seed" =~ ^[01]$ ]] || { echo "v26-3 main seed must be 0 or 1" >&2; exit 2; }
[[ -f "$checkpoint" ]] || { echo "source checkpoint missing: $checkpoint" >&2; exit 2; }
[[ ! -e "$output_dir" ]] || { echo "refusing to overwrite v26-3 output: $output_dir" >&2; exit 2; }
[[ $((num_envs % 2)) -eq 0 && "$num_envs" -gt 0 ]] || { echo "num_envs must be positive and even" >&2; exit 2; }
[[ "$batches" -gt 0 && "$save_frequency" -gt 0 ]] || { echo "batches/save frequency must be positive" >&2; exit 2; }
[[ "$gripper_effort_cap" =~ ^(10|20|40)$ ]] || { echo "gripper effort cap must be 10, 20, or 40" >&2; exit 2; }

case "$cell" in
    M0) ablation=wbmanip/base_v26_3_M0_OLD ;;
    M1) ablation=wbmanip/base_v26_3_M1_CREATE ;;
    *) echo "registered v26-3 main cell is M0 or M1; got $cell" >&2; exit 2 ;;
esac
cell_id="V26_3_${cell}_$([[ "$cell" == M0 ]] && echo OLD || echo CREATE)_S${seed}"

mkdir -p "$output_dir"
common=(
    +exp=wbmanip/door_open_a2_base_lstm
    +ablation="$ablation"
    checkpoint="$checkpoint"
    checkpoint_load_mode=policy_only
    policy_only_load_actor_rms=true
    auto_load_latest=false
    seed="$seed"
    num_envs="$num_envs"
    algo.trl.num_total_batches="$batches"
    callbacks.model_save.save_frequency="$save_frequency"
    env.config.a2_v26_side_permutation_seed="$seed"
    headless=true
    use_wandb=false
    simulator.config.render_results=false
    simulator.config.cameras.enable_cameras=false
    experiment_dir="$output_dir"
    output_dir="$output_dir/output"
    project_name=base_v26_3_event_time_creation
    experiment_name="$cell_id"
    v26_cell="$cell_id"
    v26_phase=V26_3_MAIN_EVENT_TIME_CREATION
)
if [[ "$gripper_effort_cap" != 10 ]]; then
    common+=(
        "robot.dof_effort_limit_list=[120.0,120.0,180.0,120.0,120.0,180.0,120.0,120.0,180.0,120.0,120.0,180.0,100.0,100.0,100.0,100.0,100.0,100.0,${gripper_effort_cap}.0,${gripper_effort_cap}.0]"
    )
fi
runtime_env=(
    CUDA_VISIBLE_DEVICES=0,1,2,3
    CUDA_DEVICE_ORDER=PCI_BUS_ID
    ACCELERATE_TORCH_DEVICE="cuda:$gpu"
    WANDB_MODE=disabled
    HYDRA_FULL_ERROR=1
    PYTHONUNBUFFERED=1
    PYTHONPATH="$repo"
)
env "${runtime_env[@]}" "$python_bin" -B -m gr00t.rl.train_agent_trl \
    "${common[@]}" --cfg job --resolve > "$output_dir/resolved_config.yaml"
env "${runtime_env[@]}" "$python_bin" -B -m gr00t.rl.train_agent_trl "${common[@]}"

expected="$output_dir/model_step_$(printf '%06d' "$batches").pt"
[[ -f "$expected" ]] || { echo "training exited without checkpoint $expected" >&2; exit 1; }
