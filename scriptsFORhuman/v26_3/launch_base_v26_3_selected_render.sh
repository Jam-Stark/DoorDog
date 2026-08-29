#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 --launch LABEL CHECKPOINT GPU"
    exit 0
fi
[[ ${1:-} == --launch && $# -eq 4 ]] || exit 2

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"
label=$2
checkpoint=$3
gpu=$4
output_root="$repo/logs_eval/base_v26/v26_3_event_time_creation_20260827/selected_render/$label"
log_root="$repo/scriptsFORhuman/v26_3/runtime_logs/selected_render"
attempt=${V26_3_RENDER_ATTEMPT:-}
[[ -z "$attempt" || "$attempt" =~ ^[a-z0-9_]+$ ]] || { echo "invalid render attempt suffix" >&2; exit 2; }
name="v26_3_render_${label,,}${attempt:+_$attempt}"
log_label="$label${attempt:+_$attempt}"
case "$label" in
    *M1*|*CREATE*) diagnostic_terms='[a2_stage3_handle_creation,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' ;;
    *) diagnostic_terms='[a2_stage3_handle_depression,a2_stage3_unlatch_hold,push_door_hinge,a2_stage3_stage4_hold_and_drive]' ;;
esac
[[ "$gpu" =~ ^[0-3]$ ]] || { echo "selected render requires physical GPU0..3" >&2; exit 2; }
[[ -f "$checkpoint" ]] || { echo "selected render checkpoint missing: $checkpoint" >&2; exit 1; }
[[ ! -e "$output_root" ]] || { echo "refusing to overwrite render output: $output_root" >&2; exit 1; }
! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session already exists: $name" >&2; exit 1; }
mkdir -p "$log_root"
printf -v command '%q ' bash -lc "set -euo pipefail; for side in left right; do out='$output_root'/\$side; env CUDA_VISIBLE_DEVICES='$gpu' CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 PYTHONPATH='$repo' '$python_bin' -B -m gr00t.rl.eval_agent_trl +ablation=wbmanip/base_v26_eval_natural_start ++checkpoint='$checkpoint' ++checkpoint_load_mode=full ++auto_load_latest=false ++seed=1 ++num_envs=1 ++algo.config.num_mini_batches=1 ++algo.config.eval.num_eval_episodes=1 ++algo.config.eval.eval_num_envs_episodes=true ++algo.config.eval.dump_to_log_metrics=true ++algo.config.eval.a2_diagnostic_trace_enabled=true ++algo.config.eval.a2_diagnostic_reward_terms='$diagnostic_terms' ++algo.config.eval.a2_forced_gripper_close_enabled=false ++algo.config.eval.a2_stage2_close_gate_forced_gripper_close_enabled=false ++env.config.a2_v26_door_open_lr=\$side ++env.config.enable_staged_reset=false ++simulator.config.render_results=true ++env.config.save_rendering_dir=\$out/renderings ++eval_name=V26_3_RENDER_${label}_\$side ++eval_output_dir=\$out; test -f \$out/metrics_eval.json; test -f \$out/stage2_5_step_trace.json; test -n \"\$(find \$out/renderings -maxdepth 1 -name '*.mp4' -print -quit)\"; done"
receipt=$(python3 "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$command" --output "$log_root/$log_label.log" --checkpoint "$output_root/right/metrics_eval.json" --resource "GPU$gpu" --resource "CUDA_VISIBLE_DEVICES=$gpu")
python3 "$supervisor" launch --receipt "$receipt"
