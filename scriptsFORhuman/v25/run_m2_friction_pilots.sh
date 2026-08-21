#!/usr/bin/env bash
set -euo pipefail

repo_root=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
pilot_root="$repo_root/logs_eval/base_v25/m2/friction_pilot"

run_profile() {
    local profile=$1
    local static_effort=$2
    local dynamic_effort=$3
    local output_dir="$pilot_root/${profile}_mixed16_s0"

    env -u CUDA_VISIBLE_DEVICES \
        CUDA_DEVICE_ORDER=PCI_BUS_ID \
        ACCELERATE_TORCH_DEVICE=cuda:0 \
        WANDB_MODE=disabled \
        PYTHONPATH="$repo_root" \
        "$python_bin" -m gr00t.rl.eval_agent_trl \
        +ablation=wbmanip/base_v25_m1_left_only \
        '++env.config.a2_v25_door_open_lr=[left,right]' \
        ++env.config.a2_v24_friction_enabled=true \
        ++env.config.a2_v24_friction_backend=native_joint_friction_v1 \
        ++env.config.a2_v24_friction_static_effort="$static_effort" \
        ++env.config.a2_v24_friction_dynamic_effort="$dynamic_effort" \
        ++env.config.a2_v24_friction_viscous_coefficient=0.0 \
        ++headless=true \
        ++use_wandb=false \
        ++algo.trl.report_to=none \
        ++num_envs=16 \
        ++algo.config.num_mini_batches=1 \
        ++algo.config.eval.eval_num_envs_episodes=true \
        ++algo.config.eval.num_eval_episodes=16 \
        ++simulator.config.render_results=false \
        ++simulator.config.cameras.enable_cameras=false \
        ++eval_name="V25_M2_FRICTION_${profile}_MIXED16_S0" \
        ++eval_output_dir="$output_dir"
}

run_profile P02 2.0 1.5
run_profile P10 10.0 7.5
run_profile P20 20.0 15.0
