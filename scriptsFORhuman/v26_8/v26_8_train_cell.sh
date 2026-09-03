#!/usr/bin/env bash
# Frozen v26-8 policy-only continuation worker.  A non-zero exit is final for
# its cell; no retry or resume path is provided here.
set -euo pipefail
[[ $# -eq 3 ]] || { echo "usage: $0 GPU C_S1|W_S1|K_S1|C_S2|W_S2|K_S2 OUTPUT_DIR" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; cell=$2; output=$3
case "$cell" in
  C_S1) expected_gpu=2; seed=1; source=SRC_S1 ;;
  W_S1) expected_gpu=3; seed=1; source=SRC_S1 ;;
  K_S1) expected_gpu=4; seed=1; source=SRC_S1 ;;
  C_S2) expected_gpu=5; seed=2; source=SRC_S2 ;;
  W_S2) expected_gpu=6; seed=2; source=SRC_S2 ;;
  K_S2) expected_gpu=7; seed=2; source=SRC_S2 ;;
  *) exit 2 ;;
esac
[[ "$gpu" == "$expected_gpu" ]] || { echo "frozen mapping requires $cell on GPU$expected_gpu" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "refusing to overwrite v26-8 cell output: $output" >&2; exit 1; }
selector="wbmanip/base_v26_8_${cell}"
mkdir -p "$output"
runtime=(CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0 WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo")
common=(+exp=wbmanip/door_open_a2_base_lstm +ablation="$selector" headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir="$output" output_dir="$output/output" project_name=base_v26_8_bilateral_opening_scaffold_decay experiment_name="V26_8_${cell}" v26_cell="V26_8_${cell}")
env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
"$py" - "$repo" "$output/resolved_config.yaml" "$cell" "$seed" "$source" <<'PY'
import hashlib, json, sys
from pathlib import Path
import yaml
repo, path, cell, seed, source = sys.argv[1:]
cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
expected_sources = {
    "SRC_S1": ("logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S1/model_step_003000.pt", "a683257213aaba82b583924d841235f772182f53113e513e16c8d27bcb394df1"),
    "SRC_S2": ("logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S2/model_step_003000.pt", "0b2f739f020b056adb2fb47105fdb5bc00d1d1189ef331d42332b3e0740e54ec"),
}
source_path, source_digest = expected_sources[source]
def require(value, message):
    if not value: raise SystemExit(message)
require(cfg.get("v26_cell") == f"V26_8_{cell}" and cfg.get("seed") == int(seed), "v26-8 cell identity did not resolve")
require(cfg.get("checkpoint") == source_path, f"v26-8 checkpoint path did not resolve: {cfg.get('checkpoint')!r}")
require(cfg.get("checkpoint_load_mode") == "policy_only" and cfg.get("policy_only_load_actor_rms") is True and cfg.get("auto_load_latest") is False, "v26-8 policy-only actor-RMS contract did not resolve")
require(cfg.get("num_envs") == 4096 and cfg["algo"]["trl"]["num_total_batches"] == 3000 and cfg["callbacks"]["model_save"]["save_frequency"] == 250, "v26-8 budget/save contract did not resolve")
require(cfg["env"]["config"].get("a2_v26_side_permutation_seed") == int(seed), "v26-8 side permutation seed did not resolve")
actual = hashlib.sha256((Path(repo) / source_path).read_bytes()).hexdigest()
require(actual == source_digest, f"v26-8 source checkpoint SHA-256 mismatch: {actual}")
arm = cell.split("_", 1)[0]
env = cfg["env"]["config"]
rewards = cfg.get("rewards", {})
require(float(env["a2_stage3_unlatch_near_closed_hinge_threshold"]) == (0.25 if arm == "W" else 0.1), "v26-8 arm threshold contract did not resolve")
if arm == "K":
    require(rewards.get("reward_penalty_curriculum") is True and env.get("a2_v26_8_penalty_driver") == "side_min_natural_stage_reach_rate", "v26-8 K contract did not resolve")
else:
    require("a2_v26_8_penalty_driver" not in env and rewards.get("reward_penalty_curriculum") is not True, "v26-8 non-K arm leaked curriculum")
Path(path).with_name("source_checkpoint_lock.json").write_text(json.dumps({"source": source, "checkpoint": source_path, "sha256": actual}, indent=2) + "\n", encoding="utf-8")
PY
"$py" "$repo/scriptsFORhuman/v26_8/v26_8_capture_train.py" --output "$output" --checkpoint "$repo/$("$py" - "$output/resolved_config.yaml" <<'PY'
import sys,yaml
print(yaml.safe_load(open(sys.argv[1],encoding='utf-8'))['checkpoint'])
PY
)" -- env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}"
for step in $(seq 250 250 3000); do
  checkpoint="$output/model_step_$(printf '%06d' "$step").pt"
  [[ -f "$checkpoint" ]] || { echo "missing frozen v26-8 checkpoint: $checkpoint" >&2; exit 1; }
done
[[ -f "$output/v26_8_policy_load_receipt.json" ]] || { echo "missing v26-8 policy-only load receipt" >&2; exit 1; }
if [[ "$cell" == K_* ]]; then
  [[ -f "$output/a2_v26_8_penalty_curriculum_trace.jsonl" ]] || { echo "missing K curriculum trace" >&2; exit 1; }
fi
