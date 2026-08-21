#!/usr/bin/env bash
set -euo pipefail

repo_root=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
formal_root="$repo_root/logs_rl/a2_piper_full_stage_a2_base/base_v25/formal"
launch_log_root="$formal_root/launch_logs"

mkdir -p "$launch_log_root"

launch_cell() {
    local session=$1
    local cell=$2
    local posture=$3
    local seed=$4
    local gpu=$5
    local ablation=$6
    local experiment_dir="$formal_root/$cell"
    local launch_log="$launch_log_root/$cell.log"

    tmux new-session -d -s "$session" -c "$repo_root" \
        "env -u CUDA_VISIBLE_DEVICES CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:$gpu WANDB_MODE=disabled PYTHONPATH=$repo_root $python_bin -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=$ablation ++seed=$seed ++v25_cell=$cell ++v25_posture_mode=$posture ++experiment_dir=$experiment_dir ++output_dir=$experiment_dir/output ++project_name=a2_piper_full_stage_a2_base ++experiment_name=$cell > $launch_log 2>&1"
}

launch_cell v25-full-s0 V25_FULL_S0 FULL 0 0 wbmanip/base_v25_formal_full_p10
launch_cell v25-full-s1 V25_FULL_S1 FULL 1 1 wbmanip/base_v25_formal_full_p10
launch_cell v25-rp0-s0 V25_RP0_S0 RP0 0 2 wbmanip/base_v25_formal_rp0_p10
launch_cell v25-rp0-s1 V25_RP0_S1 RP0 1 3 wbmanip/base_v25_formal_rp0_p10
