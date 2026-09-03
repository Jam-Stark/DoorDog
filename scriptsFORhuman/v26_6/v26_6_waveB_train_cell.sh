#!/usr/bin/env bash
# v26-6 Wave B training cell.  Four-cell matched matrix: {B0,B1} x seed{0,1}.
# B0 = v26-4 C0 baseline + GRIPPER_CAPABILITY_BUNDLE.
# B1 = B0 + a2_stage3_unlatch_near_closed_hinge_threshold 0.1 -> 0.25.
set -euo pipefail
[[ $# -eq 3 ]] || { echo "usage: $0 GPU CELL OUTPUT_DIR   (CELL = B0_S0|B0_S1|B1_S0|B1_S1)" >&2; exit 2; }
repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1; cell=$2; output=$3
source_cont="$repo/logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"

[[ "$gpu" =~ ^[4567]$ ]] || { echo "Wave B training is bound to physical GPU4..7" >&2; exit 2; }
[[ "$cell" =~ ^B[01]_S[01]$ ]] || { echo "registered cells are B0_S0 B0_S1 B1_S0 B1_S1" >&2; exit 2; }
[[ -f "$source_cont" ]] || { echo "missing canonical CONT_STEP2000: $source_cont" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "refusing to overwrite: $output" >&2; exit 1; }

arm=${cell%%_*}; seed=${cell##*_S}
case "$arm" in
  B0) ablation=wbmanip/base_v26_6_waveB_B0; expected_near_closed=0.1 ;;
  B1) ablation=wbmanip/base_v26_6_waveB_B1; expected_near_closed=0.25 ;;
esac
cell_id="V26_6_WAVEB_${cell}"
mkdir -p "$output"

common=(
  +exp=wbmanip/door_open_a2_base_lstm
  +ablation="$ablation"
  checkpoint="$source_cont"
  checkpoint_load_mode=policy_only
  policy_only_load_actor_rms=true
  auto_load_latest=false
  seed="$seed"
  num_envs=4096
  algo.trl.num_total_batches=750
  callbacks.model_save.save_frequency=250
  env.config.a2_v26_side_permutation_seed="$seed"
  headless=true
  use_wandb=false
  simulator.config.render_results=false
  simulator.config.cameras.enable_cameras=false
  experiment_dir="$output"
  output_dir="$output/output"
  project_name=base_v26_6_waveB_gripper_capability
  experiment_name="$cell_id"
  v26_cell="$cell_id"
)
runtime=(
  CUDA_VISIBLE_DEVICES="$gpu"
  CUDA_DEVICE_ORDER=PCI_BUS_ID
  ACCELERATE_TORCH_DEVICE=cuda:0
  WANDB_MODE=disabled
  HYDRA_FULL_ERROR=1
  PYTHONUNBUFFERED=1
  OMP_NUM_THREADS=8
  PYTHONPATH="$repo"
)

env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve \
  > "$output/resolved_config.yaml"

# Fail fast if the frozen single-factor seam or the capability bundle did not resolve.
"$py" - "$output/resolved_config.yaml" "$expected_near_closed" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
env_cfg, robot = cfg["env"]["config"], cfg["robot"]
expected = {
    "a2_stage3_unlatch_near_closed_hinge_threshold": float(sys.argv[2]),
    "a2_m39_gripper_material_enabled": True,
    "a2_stage2_squeeze_force_max": 30.0,
    "a2_stage2_over_force_threshold": 55.0,
}
for key, want in expected.items():
    got = env_cfg.get(key)
    if got != want:
        raise SystemExit(f"resolved env.config.{key}={got!r}, expected {want!r}")
if [float(v) for v in robot["dof_effort_limit_list"][-2:]] != [45.0, 45.0]:
    raise SystemExit(f"resolved gripper effort {robot['dof_effort_limit_list'][-2:]}, expected [45.0, 45.0]")
for group, want in (("stiffness", 1300.0), ("damping", 32.0)):
    for joint in ("arm_j7", "arm_j8"):
        got = float(robot["control"][group][joint])
        if got != want:
            raise SystemExit(f"resolved robot.control.{group}.{joint}={got}, expected {want}")
PY

env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}"

for step in 000250 000500 000750; do
  [[ -f "$output/model_step_$step.pt" ]] || { echo "missing checkpoint model_step_$step.pt" >&2; exit 1; }
done
