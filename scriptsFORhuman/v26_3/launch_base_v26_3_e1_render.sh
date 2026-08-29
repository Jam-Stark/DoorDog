#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 --launch CHECKPOINT GPU"
    exit 0
fi
[[ ${1:-} == --launch && $# -eq 3 ]] || exit 2

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"
checkpoint=$2
gpu=$3
output_root="$repo/logs_eval/base_v26/v26_3_event_time_creation_20260827/diagnostics/E1_SELECTED_RENDER"
log_root="$repo/scriptsFORhuman/v26_3/runtime_logs/diagnostic_render"
name=v26_3_diag_e1_render
[[ "$gpu" =~ ^[0-3]$ ]] || { echo "E1 render requires physical GPU0..3" >&2; exit 2; }
[[ -f "$checkpoint" ]] || { echo "E1 render checkpoint missing: $checkpoint" >&2; exit 1; }
[[ ! -e "$output_root" ]] || { echo "refusing to overwrite E1 render output" >&2; exit 1; }
! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session already exists: $name" >&2; exit 1; }
mkdir -p "$log_root"
printf -v command '%q ' bash -lc "set -euo pipefail; for side in left right; do out='$output_root'/\$side; env CUDA_VISIBLE_DEVICES='$gpu' CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 PYTHONPATH='$repo' '$python_bin' -B -m gr00t.rl.eval_agent_trl +ablation=wbmanip/base_v26_eval_natural_start ++checkpoint='$checkpoint' ++checkpoint_load_mode=full ++auto_load_latest=false ++seed=1 ++num_envs=1 ++algo.config.num_mini_batches=1 ++algo.config.eval.num_eval_episodes=1 ++algo.config.eval.eval_num_envs_episodes=true ++algo.config.eval.dump_to_log_metrics=true ++algo.config.eval.a2_diagnostic_trace_enabled=true ++algo.config.eval.a2_diagnostic_reward_terms='[a2_stage3_handle_depression,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' ++algo.config.eval.a2_forced_gripper_close_enabled=false ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=true ++env.config.a2_v26_3_telemetry_enabled=true ++env.config.a2_v26_3_handle_creation_scale=0.0 ++rewards.reward_scales.a2_stage3_handle_creation=0.0 ++env.config.a2_v26_door_open_lr=\$side ++env.config.enable_staged_reset=false ++simulator.config.render_results=true ++env.config.save_rendering_dir=\$out/renderings ++eval_name=V26_3_E1_RENDER_\$side ++eval_output_dir=\$out; test -f \$out/metrics_eval.json; test -f \$out/stage2_5_step_trace.json; test -f \$out/a2_eval_diagnostic_metadata.json; test -n \"\$(find \$out/renderings -maxdepth 1 -name '*.mp4' -print -quit)\"; done"
receipt=$(python3 "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log_root/E1.log" --checkpoint "$output_root/right/metrics_eval.json" --resource "GPU$gpu" --resource "CUDA_VISIBLE_DEVICES=$gpu")
python3 "$supervisor" launch --receipt "$receipt"
