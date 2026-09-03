#!/usr/bin/env bash
# v26-6 Wave A: eval-only gripper capability A/B on the frozen R15_S1 step250 checkpoint.
# Single independent variable is the GRIPPER_CAPABILITY_BUNDLE applied by the "restored" arm.
set -euo pipefail
[[ $# -eq 5 ]] || exit 2
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; arm=$2; side=$3; root=$4; seed=$5
[[ "$gpu" =~ ^[24567]$ ]] || exit 2
[[ "$arm" =~ ^(control|restored)$ ]] || exit 2
[[ "$side" =~ ^(left|right)$ ]] || exit 2
[[ "$seed" == "1" ]] || exit 2
checkpoint="$repo/logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260831_r15/train/R15_S1/model_step_000250.pt"
[[ -f "$checkpoint" ]] || exit 2
output="$root/$arm/$side"
[[ ! -e "$output" ]] || exit 1

grip=()
if [[ "$arm" == restored ]]; then
  grip=(
    '++robot.dof_effort_limit_list=[120.0,120.0,180.0,120.0,120.0,180.0,120.0,120.0,180.0,120.0,120.0,180.0,100.0,100.0,100.0,100.0,100.0,100.0,45.0,45.0]'
    '++robot.control.stiffness.arm_j7=1300.0'
    '++robot.control.stiffness.arm_j8=1300.0'
    '++robot.control.damping.arm_j7=32.0'
    '++robot.control.damping.arm_j8=32.0'
    '++env.config.a2_m39_gripper_material_enabled=true'
    '++env.config.a2_stage2_squeeze_force_max=30.0'
    '++env.config.a2_stage2_over_force_threshold=55.0'
  )
fi

env CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 \
    WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo" \
  "$py" -B -m gr00t.rl.eval_agent_trl \
    +ablation=wbmanip/base_v26_5_wave2_R15_eval_policy_residual \
    ++checkpoint="$checkpoint" \
    ++checkpoint_load_mode=full \
    ++auto_load_latest=false \
    ++seed="$seed" \
    ++num_envs=64 \
    ++algo.config.eval.a2_v26_5_policy_only_residual=false \
    ++algo.config.eval.a2_v26_5_runtime_load_receipt=true \
    ++algo.config.eval.a2_v26_5_post_construction_reseed=false \
    ++algo.config.eval.a2_v26_5_post_construction_reseed_pilot_trace=false \
    ++algo.config.eval.num_eval_episodes=64 \
    ++algo.config.eval.eval_num_envs_episodes=true \
    ++algo.config.eval.dump_to_log_metrics=true \
    ++algo.config.eval.a2_diagnostic_trace_enabled=true \
    ++algo.config.eval.a2_diagnostic_reward_terms='[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' \
    ++algo.config.eval.a2_forced_gripper_close_enabled=false \
    ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false \
    ++env.config.a2_v26_5_shared_residual_observation_enabled=true \
    ++env.config.a2_v26_2_telemetry_enabled=true \
    ++env.config.a2_v26_3_telemetry_enabled=true \
    ++env.config.a2_v26_door_open_lr="$side" \
    ++env.config.a2_v26_side_permutation_seed="$seed" \
    ++env.config.enable_staged_reset=false \
    ++simulator.config.render_results=false \
    ++env.config.save_rendering_dir="$output/renderings" \
    "${grip[@]+"${grip[@]}"}" \
    ++eval_output_dir="$output"

for x in metrics_eval.json a2_v14_per_env_records.json stage2_5_step_trace.json \
         a2_eval_diagnostic_metadata.json a2_v26_5_runtime_load_receipt.json; do
  [[ -f "$output/$x" ]] || exit 1
done
