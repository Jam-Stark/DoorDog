# Door Asset Generation Scripts

Generate randomized articulated door USD assets offline, matching the same distributions used during training in `spawn_door()`.

<p align="center">
  <img src="../../../media/door_assets.gif" width="90%">
</p>

## A2_Piper Door Scene Preview

Preview the Doorman door scene with the A2_Piper robot, without training, policy loading, DoorPregrasp, HOMIE, or finger primitive logic:

```bash
CUDA_VISIBLE_DEVICES=2 PUBLIC_IP=10.120.16.39 LIVESTREAM=1 ENABLE_CAMERAS=1 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/scripts/preview_a2_piper_door_scene.py \
--num-envs 1 --device cuda:0
```

If this shell has the expected IsaacLab/Python PATH, the wrapper form can also be used with `/home/baoquanc/workspace/IsaacLab/isaaclab.sh -p`.
For IsaacSim/UsdRT livestream or camera preview, `--device cuda:0` must be the logical GPU; use `CUDA_VISIBLE_DEVICES=N` to map physical GPU `N` to logical `cuda:0`.
Use plain `python3 gr00t/rl/scripts/preview_a2_piper_door_scene.py --help` only to inspect CLI options.
Stage-0 robot reset pose can be tuned with `--root-x`, `--root-y`, `--root-z`, and `--root-yaw`.
The default pose is `x=-0.9`, `y=0.0`, `z=0.55`, `yaw=0.0`.
To visualize the preview-only robot placement bounds, launch four envs at the XY range corners:

```bash
CUDA_VISIBLE_DEVICES=2 PUBLIC_IP=10.120.16.39 LIVESTREAM=1 ENABLE_CAMERAS=1 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/scripts/preview_a2_piper_door_scene.py \
--placement-preview corners --device cuda:0
```

`--placement-preview corners` auto-sets `--num-envs 4`; each env keeps the original Doorman door scene and places A2_Piper at one XY vertex of the selected placement bounds.
By default this uses the current Doorman stage-0 reset bounds from `_reset_root_states`: `x=[-1.5, -0.6]`, `y=[-0.5, 0.5]`, and `yaw=[-pi/4, pi/4]`; z still comes from `--root-z` and defaults to `0.55`.
In this default bounds mode, `--root-x`, `--root-y`, and `--root-yaw` still apply to the normal single-robot preview, but not to the Doorman bounds corners.
For a preview-only range around the current `--root-*` pose instead, pass `--placement-bounds root-centered`; then `--placement-x-half-range 0.35`, `--placement-y-half-range 0.35`, and `--placement-yaw-half-range 0.25` are applied around the root center.
Use `--placement-corner-yaws uniform` to keep all four robots at `--root-yaw` instead of showing yaw min/max.
The preview requires `gr00t/rl/data/robots/A2_Piper/a2_piper.usd`; if it is missing, the entrypoint fails fast and prints the conversion command instead of falling back to G1.
The A2_Piper USD asset, door scene preview, flat-walk smoke, and A2 door training config now share the USD-based LMP Stage1-equivalent physics/control plant: self-collision enabled, solver `4/0`, rigid depenetration `300.0`, zero rigid damping, force-style neutral USD drives, and LMP actuator gains/armatures.
In livestream/headless Kit runtimes without `omni.kit.widget.toolbar`, the preview logs a warning and skips IsaacLab toolbar button hiding while continuing scene creation.
For livestream/headless camera preview, the script uses an existing rendering Kit path and does not copy Kit files into the IsaacLab checkout.

## A2_Base Flat Walk Smoke

Open a full Isaac Sim GUI flat-ground monitor for the frozen A2_Base locomotion policy on A2_Piper, without door assets, DoorPregrasp, PPO, DAgger, or high-level door checkpoints:

```bash
CUDA_VISIBLE_DEVICES=2 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/scripts/smoke_a2_base_flat_walk.py \
--device cuda:0 --num-envs 1 --command 0.25 0.0 0.0
```

`--command` is a compatibility alias for physical base command `[vx_mps, vy_mps, yaw_radps]`; new invocations should prefer `--base-command-physical 0.25 0.0 0.0` or `--base-command-raw 1.0 0.0 0.0`.
The script prints both command forms and uses `physical = raw * 0.25`; the default raw command therefore yields physical `vx=0.25 m/s`.
It runs until the GUI closes by default; use `--max-steps N` only for bounded smoke checks.
The same UsdRT logical GPU caveat applies: use `CUDA_VISIBLE_DEVICES=N ... --device cuda:0` instead of passing `--device cuda:N`.

## Generate Door Assets

```bash
python gr00t/rl/scripts/generate_door_assets.py \
    --num_doors 100 \
    --output_dir data/door_assets \
    --build_latch \
    --add_floors \
    --door_open_lr right \
    --door_open_io out \
    --randomize_material \
    --seed 42
```

Each door is saved as a self-contained `.usd` file with randomized geometry (width, height, weight), handle placement, joint dynamics, optional latch, and Omniverse materials. A `metadata.json` with all sampled parameters is saved alongside the USD files.

Multiple values can be passed to `--door_open_lr` and `--door_open_io` to sample from both:

```bash
--door_open_lr left right --door_open_io in out
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--num_doors N` | Number of doors to generate | 100 |
| `--output_dir DIR` | Output directory | `data/door_assets` |
| `--seed S` | Random seed | 0 |
| `--build_latch` | Add latch mechanism | off |
| `--add_floors` | Add floor planes | off |
| `--add_walls` | Add surrounding walls | off |
| `--door_open_lr` | Hinge side(s): `left`, `right`, or both | `right` |
| `--door_open_io` | Open direction(s): `in`, `out`, or both | `out` |
| `--door_handle_tblr T B L R` | Handle position range (fraction of door) | `0.95 0.85 0.08 0.15` |
| `--randomize_material` | Apply random Omniverse materials | off |
| `--preloaded_materials_num_transform` | UV-transform variants per texture | 20 |
| `--preloaded_materials_num_color` | Random-color paint variants | 100 |

## Generate 1000 Doors (Batch)

A convenience script generates 1000 doors across 7 diverse configurations:

```bash
bash gr00t/rl/scripts/generate_1000_doors.sh            # default: data/door_assets/
bash gr00t/rl/scripts/generate_1000_doors.sh /my/path    # custom output dir
```

| Subdirectory | Count | Hinge | Direction | Latch | Walls |
|---|---|---|---|---|---|
| `right_out_latch/` | 200 | right | out | yes | no |
| `left_out_latch/` | 200 | left | out | yes | no |
| `right_in_latch/` | 150 | right | in | yes | no |
| `left_in_latch/` | 150 | left | in | yes | no |
| `mixed_walls/` | 100 | both | both | yes | yes |
| `mixed_no_latch/` | 100 | both | both | no | no |
| `wide_handle_range/` | 100 | both | both | yes | no |
# A2+Piper Student Distillation

* Teacher artifact validator: `validate_a2_teacher_checkpoint.py`
* Import-safe static camera contract validator: `smoke_a2_student_camera.py` (runtime QA uses a separate approved entrypoint)
* Same-step R14 camera transform probe: `probe_a2_student_camera_transform.py`

Run the R14 probe on one visible GPU. It launches exactly one A2 door environment,
advances two physics steps after reset, and compares the same-step trunk body tensor,
trunk prim, configured camera offset, camera prim, cached `CameraData`, and a temporary
`update_latest_camera_pose=True` refresh. The camera setting is restored before evidence
is sealed, and the JSON is written before `SimulationApp.close()`:

```bash
CUDA_VISIBLE_DEVICES=0 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
gr00t/rl/scripts/probe_a2_student_camera_transform.py \
--device cuda:0 \
--output /tmp/a2_student_camera_transform_probe.json
```

The output path must not already exist. `PASS` means the live transform chain closes
within the declared tolerances and the default `CameraData` pose is proven to be the
stale initialization pose; a non-reproduced stale gap is `INCONCLUSIVE`, not PASS.
In the currently pinned Kit, `SimulationApp.close()` may not return after the sealed
marker. R16 remains open; if cleanup is required, terminate only the exact probe PID
after `[R14_EVIDENCE_SEALED]`, never another Isaac Sim process.

Run the diagnostic-only Gemini 335L single-camera pose sweep with a fresh output
directory. The default allowlisted profile is the full-task `base_v16_B` checkpoint.
It copies and SHA-verifies checkpoint/config inputs, runs the pinned clean mainline
runtime through the dedicated worktree overlay, never launches a trainer, and refuses
an existing output directory:

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
gr00t/rl/scripts/sweep_a2_student_camera_pose.py \
--teacher base_v16_B --gpu 0 --num-envs 16 \
--output-dir \
logs_eval/a2_camera_pose_sweep_v16B_ckpt2000_stage1_5_16env_seed0_env1_20260722_2325
```

The sweep uses one existing `TiledCamera` and the centered Gemini 335L nominal
`1280x800 -> 1280x720 -> 384x216` RGB intrinsics. Because the pinned IsaacLab
projection assumes square pixels, simulation preserves the nominal `94 deg`
horizontal FoV with `fx=fy=179.0428965384`; the spec-derived cropped value is
`fy=177.9073162215`, so this is a documented `+1.1355803169 px` approximation,
not physical calibration. Every candidate is set/read back in the camera's local
OpenGL frame, rendered at the same physics step, and checked for image diversity.
Every candidate writes its own MP4 from one selected environment; sealing requires
equal positive frame counts and video coverage of every ranked stage 1--5.

The sealed 16-env seed0 `base_v16_B` run completed 16 episodes (`15/16` reached the
goal) and ranked `x_near_028` first across stages 1--5: local position
`[0.28,0.0,0.25] m`, RPY `[0,-6,0] deg`, quaternion
`[0.9986295348,0,-0.0523359562,0] wxyz`, score `0.5614803625`. Its ranked handle,
handle-plus-both-fingers, door-panel, and centered-handle rates were respectively
`0.6367069486`, `0.4339123867`, `0.7265861027`, and `0.5185045317`. All eight
candidate videos contain 224 frames from env 1 and cover stages 1--5. Manual review
also found that every candidate loses most task geometry in stage 5; even
`x_near_028` has only `0.0953516091` handle visibility and `0.1370679380` door-panel
visibility there. It is therefore only the next pose-search center, not an accepted
simulation default or physical mount. Mirrored left/right validation and calibrated
hardware intrinsics remain required.

For the first approved one-update GPU smoke, launch the A2 route with a fresh
dedicated `experiment_dir`. This uses four environments, one rollout step,
one minibatch, one total batch, and saves `model_step_000001.pt`:

```bash
CUDA_VISIBLE_DEVICES=0 HYDRA_FULL_ERROR=1 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/accelerate launch --num_processes 1 \
gr00t/rl/train_agent_trl.py \
+exp=wbmanip/door_open_a2_base_dagger-lstm \
num_envs=4 \
algo.config.num_steps_per_env=1 \
algo.config.num_mini_batches=1 \
algo.trl.num_total_batches=1 \
algo.trl.per_device_train_batch_size=4 \
callbacks.model_save.save_frequency=1 \
use_wandb=false \
experiment_dir=logs_rl/a2_piper_student_distillation_one_update \
teacher_actor_path=logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/model_step_001000.pt \
teacher_config_path=logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/config.yaml \
teacher_manifest_path=logs_rl/a2_piper_student_distillation_runtime/base_v10_D_teacher-20260714_144359/teacher_manifest.json
```
