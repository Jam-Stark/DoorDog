#!/usr/bin/env bash
# Frozen v26-7 from-scratch training worker.  A non-zero training exit is final
# for that cell; this worker has no retry path.
set -euo pipefail

usage() {
  echo "usage: $0 GPU Q05_S0|Q05_S1|Q05_S2|Q20_S0|Q20_S1|Q20_S2 OUTPUT_DIR" >&2
}
[[ $# -eq 3 ]] || { usage; exit 2; }

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
py=/home/baoquanc/anaconda3/envs/isaaclab/bin/python
gpu=$1
cell=$2
output=$3

case "$cell" in
  Q05_S0) expected_gpu=2; seed=0; squeeze=0.5 ;;
  Q05_S1) expected_gpu=3; seed=1; squeeze=0.5 ;;
  Q05_S2) expected_gpu=4; seed=2; squeeze=0.5 ;;
  Q20_S0) expected_gpu=5; seed=0; squeeze=2.0 ;;
  Q20_S1) expected_gpu=6; seed=1; squeeze=2.0 ;;
  Q20_S2) expected_gpu=7; seed=2; squeeze=2.0 ;;
  *) usage; exit 2 ;;
esac
[[ "$gpu" == "$expected_gpu" ]] || { echo "frozen mapping requires $cell on GPU$expected_gpu" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "refusing to overwrite v26-7 cell output: $output" >&2; exit 1; }

selector="wbmanip/base_v26_7_${cell}"
mkdir -p "$output"
common=(
  +exp=wbmanip/door_open_a2_base_lstm
  +ablation="$selector"
  checkpoint=null checkpoint_load_mode=full auto_load_latest=false
  seed="$seed" num_envs=4096
  algo.trl.num_total_batches=6000 callbacks.model_save.save_frequency=250
  env.config.a2_v26_side_permutation_seed="$seed"
  headless=true use_wandb=false
  simulator.config.render_results=false simulator.config.cameras.enable_cameras=false
  experiment_dir="$output" output_dir="$output/output"
  project_name=base_v26_7_bilateral_native_unlatch
  experiment_name="V26_7_${cell}" v26_cell="V26_7_${cell}"
  v26_phase=V26_7_BILATERAL_NATIVE_UNLATCH
)
runtime=(
  CUDA_VISIBLE_DEVICES="$gpu" CUDA_DEVICE_ORDER=PCI_BUS_ID ACCELERATE_TORCH_DEVICE=cuda:0
  WANDB_MODE=disabled HYDRA_FULL_ERROR=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8 PYTHONPATH="$repo"
)

env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}" --cfg job --resolve > "$output/resolved_config.yaml"
"$py" - "$output/resolved_config.yaml" "$cell" "$seed" "$squeeze" <<'PY'
import sys, yaml
path, cell, seed, squeeze = sys.argv[1:]
cfg = yaml.safe_load(open(path, encoding="utf-8"))
env, robot = cfg["env"]["config"], cfg["robot"]
expected = {
    "checkpoint": None, "checkpoint_load_mode": "full", "auto_load_latest": False,
    "seed": int(seed), "num_envs": 4096, "v26_cell": f"V26_7_{cell}",
}
for key, want in expected.items():
    if cfg.get(key) != want:
        raise SystemExit(f"resolved {key}={cfg.get(key)!r}, expected {want!r}")
if cfg["algo"]["trl"]["num_total_batches"] != 6000 or cfg["callbacks"]["model_save"]["save_frequency"] != 250:
    raise SystemExit("v26-7 batch/save contract did not resolve")
expected_env = {
    "a2_v26_door_open_lr": "bilateral",
    "a2_v26_6_side_mirrored_handle_offset_enabled": True,
    "a2_stage2_squeeze_force_min": float(squeeze),
    "a2_m39_gripper_material_enabled": True,
    "a2_stage2_squeeze_force_max": 30.0,
    "a2_stage2_over_force_threshold": 55.0,
}
for key, want in expected_env.items():
    if env.get(key) != want:
        raise SystemExit(f"resolved env.config.{key}={env.get(key)!r}, expected {want!r}")
if [float(v) for v in robot["dof_effort_limit_list"][-2:]] != [45.0, 45.0]:
    raise SystemExit("v26-7 gripper effort contract did not resolve")
for group, want in (("stiffness", 1300.0), ("damping", 32.0)):
    if any(float(robot["control"][group][joint]) != want for joint in ("arm_j7", "arm_j8")):
        raise SystemExit(f"v26-7 gripper {group} contract did not resolve")
if cfg["simulator"]["config"]["sim"]["physx"]["num_velocity_iterations"] != 2:
    raise SystemExit("v26-7 PhysX velocity-iteration contract did not resolve")
PY

env "${runtime[@]}" "$py" -B -m gr00t.rl.train_agent_trl "${common[@]}"

checkpoint_endpoint_step() {
  "$py" - "$repo" "$cell" <<'PY'
import json
import sys
from pathlib import Path

repo, cell = map(str, sys.argv[1:])
steps = (1000, 2000, 3000, 4000, 5000, 6000)
configs = ("Q05", "Q20")
config = cell.split("_", 1)[0]
if config not in configs or cell not in {f"{config}_S{seed}" for seed in range(3)}:
    raise SystemExit(f"invalid v26-7 cell for endpoint resolution: {cell}")
milestones = Path(repo) / "logs_eval/base_v26/v26_7_bilateral_native_unlatch_20260902/milestones"
endpoint = None
for step in steps:
    path = milestones / f"step{step}" / "reducer.json"
    if not path.is_file():
        break
    reducer = json.loads(path.read_text(encoding="utf-8"))
    if not (
        reducer.get("schema") == "a2_piper_base_v26_7_milestone_reducer_v1"
        and reducer.get("status") == "EXPERIMENT_COMPLETE"
        and reducer.get("step") == step
        and isinstance(reducer.get("config_endpoints"), dict)
        and set(reducer["config_endpoints"]) == set(configs)
    ):
        raise SystemExit(f"invalid frozen endpoint reducer: {path}")
    candidate = reducer["config_endpoints"][config]
    if candidate is None:
        continue
    expected_cells = {f"{config}_S{seed}" for seed in range(3)}
    outcomes = candidate.get("per_seed_outcomes") if isinstance(candidate, dict) else None
    if not (
        isinstance(candidate, dict)
        and candidate.get("config") == config
        and candidate.get("outcome") == "BILATERAL_UNLATCH_SUPPORTED"
        and candidate.get("step") in steps
        and candidate["step"] <= step
        and isinstance(outcomes, dict)
        and set(outcomes) == expected_cells
        and sum(value == "BILATERAL_UNLATCH_SUPPORTED" for value in outcomes.values()) >= 2
        and isinstance(reducer.get("config_outcomes"), dict)
        and reducer["config_outcomes"].get(config) == "BILATERAL_UNLATCH_SUPPORTED"
    ):
        raise SystemExit(f"invalid frozen endpoint: {path} {config}")
    if endpoint is None:
        endpoint = candidate
    elif endpoint != candidate:
        raise SystemExit(f"frozen endpoint changed after freeze: {config}")
print(6000 if endpoint is None else endpoint["step"])
PY
}

checkpoint_limit=$(checkpoint_endpoint_step)
for step in $(seq 250 250 "$checkpoint_limit"); do
  checkpoint="$output/model_step_$(printf '%06d' "$step").pt"
  [[ -f "$checkpoint" ]] || { echo "missing frozen save checkpoint: $checkpoint" >&2; exit 1; }
done
