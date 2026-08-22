#!/usr/bin/env bash
set -euo pipefail

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
run_root="$repo/logs_rl/by_batch/base_v26_r0_20260821"
runtime_log_root="$repo/scriptsFORhuman/v26/runtime_logs"

mkdir -p "$run_root" "$runtime_log_root"

launch_cell() {
    local gpu="$1"
    local cell="$2"
    local ablation="$3"
    local session="$4"
    local run_dir="$run_root/$cell"
    local runtime_log="$runtime_log_root/$cell.log"

    mkdir -p "$run_dir"
    tmux new-session -d -s "$session" \
        "bash -lc 'cd $repo && env CUDA_VISIBLE_DEVICES=0,1,2,3 CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:$gpu WANDB_MODE=disabled PYTHONPATH=$repo $python_bin -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/$ablation experiment_name=$cell experiment_dir=$run_dir output_dir=$run_dir/output project_name=a2_piper_base_v26_r0 +topology_id=V26-R0-1GPU-$gpu +gpu_binding_mode=accelerate-torch-device-cuda-$gpu >$runtime_log 2>&1; status=\$?; echo V26_EXIT_CODE=\$status >>$runtime_log; exit \$status'"
}

launch_cell 0 V26_LR_S0 base_v26_lr_scratch_seed0 v26_r0_lr_s0
launch_cell 1 V26_LR_S1 base_v26_lr_scratch_seed1 v26_r0_lr_s1
launch_cell 2 V26_L_S0 base_v26_left_scratch_seed0 v26_r0_l_s0
launch_cell 3 V26_R_S0 base_v26_right_scratch_seed0 v26_r0_r_s0
