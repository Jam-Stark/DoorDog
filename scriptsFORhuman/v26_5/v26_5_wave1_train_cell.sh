#!/usr/bin/env bash
set -euo pipefail

usage() { echo "usage: $0 GPU O1A0_S[01]|O1A1_S[01] OUTPUT_DIR"; }
[[ ${1:-} == --help || ${1:-} == -h ]] && { usage; exit 0; }
[[ $# -eq 3 ]] || { usage >&2; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
python_bin=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
source_checkpoint="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
gpu=$1; label=$2; output=$3
[[ "$gpu" =~ ^[0-3]$ && "$label" =~ ^O1A[01]_S[01]$ ]] || { usage >&2; exit 2; }
[[ -f "$source_checkpoint" && ! -e "$output" ]] || { echo "source checkpoint missing or output exists" >&2; exit 1; }
seed=${label##*_S}
case "$label" in
  O1A0_*) ablation=wbmanip/base_v26_5_O1A0_geometry ;;
  O1A1_*) ablation=wbmanip/base_v26_5_O1A1_geometry_rebase ;;
esac
mkdir -p "$output"
common=(
  +exp=wbmanip/door_open_a2_base_lstm +ablation="$ablation"
  checkpoint="$source_checkpoint" checkpoint_load_mode=policy_only policy_only_load_actor_rms=true auto_load_latest=false
  seed="$seed" num_envs=4096 algo.trl.num_total_batches=750 callbacks.model_save.save_frequency=125
  env.config.a2_v26_side_permutation_seed="$seed" headless=true use_wandb=false simulator.config.render_results=false
  simulator.config.cameras.enable_cameras=false experiment_dir="$output" output_dir="$output/output"
  project_name=base_v26_5_wave1_stage5 experiment_name="V26_5_${label}" v26_cell="V26_5_${label}" v26_phase=V26_5_WAVE1
)
runtime=(CUDA_VISIBLE_DEVICES=0,1,2,3 CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE="cuda:$gpu" WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 PYTHONPATH="$repo")
env "${runtime[@]}" "$python_bin" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
env "${runtime[@]}" "$python_bin" -B -m gr00t.rl.train_agent_trl "${common[@]}"
[[ -f "$output/model_step_000750.pt" ]] || { echo "missing Wave1 step750 checkpoint" >&2; exit 1; }
