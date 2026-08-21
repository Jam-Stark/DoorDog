#!/usr/bin/env bash
set -euo pipefail

repo_root=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
smoke_root="$repo_root/logs_rl/a2_piper_full_stage_a2_base_smoke/base_v25/m2/prelaunch_p10"

run_smoke() {
    local cell=$1
    local ablation=$2
    local posture=$3
    local experiment_dir="$smoke_root/$cell"

    env -u CUDA_VISIBLE_DEVICES \
        CUDA_DEVICE_ORDER=PCI_BUS_ID \
        ACCELERATE_TORCH_DEVICE=cuda:0 \
        WANDB_MODE=disabled \
        PYTHONPATH="$repo_root" \
        "$python_bin" -m gr00t.rl.train_agent_trl \
        +exp=wbmanip/door_open_a2_base_lstm \
        +ablation="$ablation" \
        ++v25_cell="$cell" \
        ++v25_posture_mode="$posture" \
        ++num_envs=64 \
        ++algo.config.num_mini_batches=1 \
        ++algo.trl.num_total_batches=8 \
        ++callbacks.model_save.save_frequency=8 \
        ++experiment_dir="$experiment_dir" \
        ++output_dir="$experiment_dir/output" \
        ++project_name=a2_piper_full_stage_a2_base_smoke \
        ++experiment_name="$cell"
}

run_smoke V25_FULL_P10_64X8 wbmanip/base_v25_formal_full_p10 FULL
run_smoke V25_RP0_P10_64X8 wbmanip/base_v25_formal_rp0_p10 RP0
