#!/usr/bin/env bash
# One pull-v7 P2 cell: full continuation from its own Wave2 step9000 to the
# absolute ceiling 10500 in a single process, so the online staged-reset banks
# stay continuous.  The 9500 admission gate is enforced by Main stopping a cell
# after the 9500 milestone eval, not by relaunching.  Receipt orchestration is
# external.
set -euo pipefail
[[ $# -eq 3 || $# -eq 4 ]] || { echo 'usage: run_p2_cell.sh GPU T_S1|T_S2|C_S1|C_S2 OUTPUT_DIR [smoke]' >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
output=$3
mode=${4:-full}
# GPU0 carries another user's LightNav server; pull-v7 P2 uses GPU1-3 only.
[[ "$gpu" =~ ^[123]$ ]] || { echo 'pull-v7 P2 runs on GPU1, GPU2 or GPU3 only' >&2; exit 2; }
case "$cell" in
  T_S1) source_cell=P_S1; seed=1; selector=wbmanip/pull_v7_p2_T_S1 ;;
  T_S2) source_cell=P_S2; seed=2; selector=wbmanip/pull_v7_p2_T_S2 ;;
  C_S1) source_cell=P_S1; seed=1; selector=wbmanip/pull_v26_8_backbone_P_S1 ;;
  C_S2) source_cell=P_S2; seed=2; selector=wbmanip/pull_v26_8_backbone_P_S2 ;;
  *) exit 2 ;;
esac
case "$mode" in
  full) num_envs=1024; batches=10500; verify_flag=() ;;
  # Full resume requires num_total_batches above the loaded global step
  # (ppo_trainer_a2_base_api: loaded=9000), so the smoke budget is 5 new
  # batches, i.e. the absolute ceiling 9005.
  smoke) num_envs=256; batches=9005; verify_flag=(--smoke) ;;
  *) echo "unknown mode: $mode" >&2; exit 2 ;;
esac
source_checkpoint="$repo/logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/$source_cell/model_step_009000.pt"
[[ -f "$source_checkpoint" ]] || { echo "missing source checkpoint: $source_checkpoint" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "fresh output required: $output" >&2; exit 1; }
mkdir -p "$output"
cd "$repo"
runtime=(CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo")
common=(+exp=wbmanip/door_open_a2_pull_v26_backbone_lstm +ablation="$selector"
  checkpoint="$source_checkpoint" checkpoint_load_mode=full auto_load_latest=false
  seed="$seed" num_envs="$num_envs" algo.trl.num_total_batches="$batches" callbacks.model_save.save_frequency=250
  headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false
  experiment_dir="$output" output_dir="$output/output" project_name=a2_piper_pull_v7 experiment_name="$cell" +device=cuda:0)
env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
"$py" "$repo/scriptsFORhuman/pull_v7/verify_p2_config.py" "$output/resolved_config.yaml" "$cell" "${verify_flag[@]}"
required=()
if [[ "$mode" == full ]]; then required=(--required model_step_010500.pt); fi
exec "$py" "$repo/scriptsFORhuman/pull_v26_8/runner.py" --output "$output" --gpu "$gpu" "${required[@]}" -- \
  env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}"
