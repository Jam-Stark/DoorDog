#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "usage: $0 --launch LABEL CHECKPOINT [GPU]"
    exit 0
fi
if [[ ${1:-} != --launch || $# -lt 3 || $# -gt 4 ]]; then
    echo "usage: $0 --launch LABEL CHECKPOINT [GPU]" >&2
    exit 2
fi

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
supervisor="$repo/.ai/scripts/run_supervisor.py"
label=$2
checkpoint=$3
gpu=${4:-0}
output_root="$repo/logs_eval/base_v26/v26_2_pull_derived_20260825/selected_render/$label"
log_root="$repo/scriptsFORhuman/v26_2/runtime_logs/selected_render"
name="v26_2_render_${label,,}"
[[ "$gpu" =~ ^[0-3]$ ]] || { echo "selected render requires physical GPU0..3" >&2; exit 2; }
[[ -f "$checkpoint" ]] || { echo "selected render checkpoint missing: $checkpoint" >&2; exit 1; }
[[ ! -e "$output_root" ]] || { echo "refusing to overwrite render output: $output_root" >&2; exit 1; }
! tmux has-session -t "$name" 2>/dev/null || { echo "tmux session already exists: $name" >&2; exit 1; }
mkdir -p "$log_root"
printf -v render_command '%q ' bash -lc "set -euo pipefail; for side in left right; do out='$output_root'/\$side; env CUDA_VISIBLE_DEVICES='$gpu' CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled PYTHONPATH='$repo' '$python_bin' -B -m gr00t.rl.eval_agent_trl +ablation=wbmanip/base_v26_eval_natural_start ++checkpoint='$checkpoint' ++checkpoint_load_mode=full ++auto_load_latest=false ++seed=1 ++num_envs=1 ++algo.config.eval.num_eval_episodes=1 ++algo.config.eval.eval_num_envs_episodes=true ++env.config.a2_v26_door_open_lr=\$side ++env.config.enable_staged_reset=false ++simulator.config.render_results=true ++env.config.save_rendering_dir=\$out/renderings ++eval_output_dir=\$out; done"
receipt=$(python3 "$supervisor" prepare --name "$name" --session "$name" --cwd "$repo" --command "$render_command" --output "$log_root/$label.log" --checkpoint "$output_root/right/metrics_eval.json" --resource "GPU$gpu" --resource "CUDA_VISIBLE_DEVICES=$gpu")
python3 "$supervisor" launch --receipt "$receipt"
