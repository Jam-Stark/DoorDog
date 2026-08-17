# Sim2sim production source map

Last updated: 2026-08-17 17:49 HKT

## Policy and checkpoint

- Student production source: read-only worktree `/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103`.
- Selected current Student candidate: `logs_rl/by_batch/cb2h_v19_toeout6_pitch50_grpo_20260811/pilot_2x32_lr375e8_syncreset/model_step_000010.pt` in the read-only distillation worktree; its adjacent `config.yaml` is the config source. The recorded fixed-G2 formal result is 467/512.
- Production eval entry: `gr00t/rl/scripts/run_a2_toeout6_student_eval.py` -> `gr00t/rl/eval_agent_trl.py`.
- Production actor: `gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent.DualD435HeadVisionRecurrentToeOut6Actor`.
- Production load sequence: checkpoint-adjacent config load/merge -> `instantiate(config.env)` -> `instantiate(config.algo.config.actor)` -> `GRPOTrainerA2BaseAPI` strict `policy_state_dict` load.
- Checkpoint payload is `policy_state_dict` plus optimizer/scheduler/state/args/env state; `state.global_step=10`. The deployable surface excludes Teacher/value state.
- Native eval currently initializes IsaacSim before actor construction. A CPU-only independent native-Hydra reconstruction is not established and remains a typed E0 runtime boundary.

## Robot and low-level control

- URDF: `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf`.
- A2_Base TorchScript: `gr00t/rl/data/policies/A2_Base/policy.pt`.
- A2_Base metadata: `gr00t/rl/data/policies/A2_Base/policy_metadata.json`.
- 54D frame/history producer: `gr00t/rl/envs/base_task/a2_base.py::_get_a2_base_obs_frame` and `_get_obs_a2_base_obs`: gravity3, relative leg q12, `0.05*qd`12, previous leg action12, scaled physical command5, zero arm command6, roll/pitch2, gait sin/cos2. The first frame fills all 30 slots; later calls shift/append.
- Delta action state/update/reset: `gr00t/rl/envs/base_task/delta_action_base.py`.
- High-level/action chain: 12D `[base5, arm6, gripper1]`; frozen A2 leg output adds 12D; logical applied action is 19D `[leg12, arm6, gripper1]`; gripper expands to two joints for the 20D simulator target.
- Delta source semantics: raw arm channels 5:11 accumulate at scale 0.3 and clip ±15; stage0 and reset clear them. The configured reset backmap branch is an unimplemented `pass`, so a sim2sim backmap would change production behavior.
- A2 policy order is remapped by names into simulator order. Production domain-randomization-off behavior has zero control delay despite metadata listing candidates `[0,1]`.
- Base robot config is `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml`; Owner R4 fixes the evaluated gripper control face to `Kp/Kd/effort=1300/32/45`, with supporting v20+ overlays such as `gr00t/rl/config/ablation/wbmanip/base_v20_R2_G6_full.yaml`.

## Door and mechanics

- Legacy generator reference: `gr00t/rl/isaac_utils/playground/env_rand/door.py`.
- v24 rad unit contract reference: read-only original `scriptsFORhuman/v24/_v24_common.py` and its direct receipt producers.
- v24 friction backend reference: read-only original v24 environment/evidence modules using `write_joint_friction_coefficient_to_sim(static, dynamic, viscous)`.
- Canonical golden compatibility evidence: read-only original `logs_eval/base_v24/p0/runtime_compatibility/`.
- Reusable row contract: 16 first episodes, `env_id/episode_index/control_step`, actor obs, raw action mean, post-env action, final action, done, and typed terminal facts; discrete facts exact and float comparison at `1e-6`. The canonical r6 receipt contains 7,326 zero-diff rows.

## Non-production implementation boundary

New backend-neutral contracts, MuJoCo runtime, generated MJCF, bundle artifacts, and reports live only in additive `gr00t/rl/sim2sim/`, `gr00t/rl/data/mujoco/A2_Piper/`, and `scriptsFORhuman/sim2sim/` paths on this branch.
