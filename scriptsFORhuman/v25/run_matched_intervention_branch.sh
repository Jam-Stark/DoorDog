#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "usage: $0 GPU BRANCH CHECKPOINT LABEL" >&2
    exit 2
fi

repo_root=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
branch=$2
checkpoint=$3
label=$4
eval_root="$repo_root/logs_eval/base_v25/causality/$label/$branch"

for side in left right; do
    output_dir="$eval_root/$side"
    env -u CUDA_VISIBLE_DEVICES \
        CUDA_DEVICE_ORDER=PCI_BUS_ID \
        ACCELERATE_TORCH_DEVICE="cuda:$gpu" \
        WANDB_MODE=disabled \
        PYTHONPATH="$repo_root" \
        "$python_bin" -m gr00t.rl.eval_agent_trl \
        +ablation=wbmanip/base_v25_m1_left_only \
        ++checkpoint="$checkpoint" \
        ++checkpoint_load_mode=policy_only \
        ++env.config.a2_v25_door_open_lr="$side" \
        ++env.config.a2_v24_friction_enabled=true \
        ++env.config.a2_v24_friction_backend=native_joint_friction_v1 \
        ++env.config.a2_v24_friction_static_effort=10.0 \
        ++env.config.a2_v24_friction_dynamic_effort=7.5 \
        ++env.config.a2_v24_friction_viscous_coefficient=0.0 \
        ++headless=true \
        ++use_wandb=false \
        ++algo.trl.report_to=none \
        ++num_envs=32 \
        ++algo.config.num_mini_batches=1 \
        ++algo.config.eval.eval_num_envs_episodes=true \
        ++algo.config.eval.num_eval_episodes=32 \
        ++algo.config.eval.a2_v25_intervention_branch="$branch" \
        ++algo.config.eval.a2_v25_intervention_horizon_steps=50 \
        ++algo.config.eval.a2_v25_intervention_near_closed_max_rad=0.25 \
        ++simulator.config.render_results=false \
        ++simulator.config.cameras.enable_cameras=false \
        ++eval_name="V25_CAUSAL_${label}_${branch}_${side}" \
        ++eval_output_dir="$output_dir"
done
