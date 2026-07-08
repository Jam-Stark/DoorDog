---
name: phase2-student-distillation-a2-piper
scope: Full A2+Piper adaptation plan for Doorman Phase2 Student Distillation / DAgger vision policy
status: planned
last_updated: 2026-07-08 15:11 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/phase2-student-distillation-a2-piper/description.md
  - memory/a2-piper/phase2-student-distillation-a2-piper/TODO.md
  - memory/a2-piper/phase2-student-distillation-a2-piper/DONE.md
read_when:
  - 开始设计、实现、review 或 debug A2+Piper Phase2 Student Distillation / DAgger vision route 前
  - 需要判断 origin G1/HOMIE student route 哪些部分可复用、哪些必须 A2-specific 替换前
  - 需要给 code worker / reviewer 派发 A2 student trainer、vision observation、camera 或 teacher-student action contract 任务前
---

# A2+Piper Phase2 Student Distillation Plan

## Purpose

记录完整的 A2+Piper adaptation 版本，而不是 minimum viable skeleton。目标是把 Doorman paper 中 Phase2 `Student Distillation` / DAgger vision policy 从 G1/HOMIE route 完整替换为 A2+Piper route，使 student policy 能从 A2 Teacher PPO checkpoint 蒸馏，并通过 RGB vision + A2 proprioception 输出 A2 high-level door policy action。

本 entry 只记录未来实现参考、scope boundary、target architecture、施工顺序和验收条件。当前尚未实现 A2 student route。

## Current Source Facts

- Origin G1/HOMIE student route exists, but is not A2-compatible:
  - Experiment config: `gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml`
  - Algorithm config: `gr00t/rl/config/algo/dagger_vision_distributed.yaml`
  - Observation config: `gr00t/rl/config/obs/wbmanip/door_open_homie_dagger.yaml`
  - Trainer config: `gr00t/rl/config/trainer/trl_distill_obj_pred_homie_api.yaml`
  - Trainer/source: `gr00t/rl/trl/trainer/distill_trainer.py`, `distill_trainer_obj_pred.py`, `distill_trainer_obj_pred_homie_api.py`
  - Vision actor: `gr00t/rl/trl/modules/vision_actor_critic_modules_obj_pred_recurrent.py`
- Current A2 route is Teacher PPO / A2_Base only:
  - Experiment config: `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml`
  - Stage0-2 variant: `gr00t/rl/config/exp/wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml`
  - Observation config: `gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`
  - Trainer config: `gr00t/rl/config/trainer/trl_a2_base_api.yaml`
  - Trainer/source: `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`
- Current A2 Teacher high-level contract:
  - Policy output: `12D = 5D a2_base_command_raw [x, y, yaw, pitch, roll] + 6D Piper arm_j1..j6 + 1D gripper primitive`
  - Trainer rollout action: `24D = 12D high-level + 12D frozen A2_Base leg action`
  - Env final simulator command: `20D = 12D legs + 6D Piper arm + 2D gripper joints`
  - Teacher actor/critic obs are currently `133D/138D`, with A2-specific `hand_force -> 6D arm_body7/8 force`, `hand_handle_transform -> gripper_handle_transform 18D`, `a2_base_command_raw`, `a2_base_command`, `delta_actions` as 6D Piper arm raw delta only.
- Current A2 student/vision status:
  - `scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md` marks `Student DAgger/vision policy` as `TODO`.
  - Origin `teacher_actor_path` points to a G1/HOMIE checkpoint and must not be reused for A2.
  - Origin camera route assumes `d435_link`; A2_Piper URDF/config currently does not expose a `d435_link`.
  - A2 `door_open_a2_base.py::_get_obs_dof_pos_non_finger()` and `_get_obs_dof_vel_non_finger()` still use G1-style `[:, :-14]` slicing and are not acceptable as final A2 student proprioception terms.
  - A2 `_get_obs_target_obj_pos()` currently reads `head_target_frame_transformer`; this is not a validated A2 student object-prediction source.

## Full Target Architecture

The final A2+Piper Phase2 route should include all of the following, not just a smoke-only subset:

1. **A2 Teacher checkpoint dependency**
   - `teacher_actor_path` points to a trained A2 Teacher PPO checkpoint generated from the A2 route.
   - Teacher actor load must fail-fast if checkpoint action dim, obs dim, running mean/std state, recurrent architecture or config sidecar does not match the active A2 Teacher contract.
   - Teacher inference uses A2 `teacher_obs` and outputs only the 12D high-level action. Frozen A2_Base leg actions are derived separately, not learned by the student.

2. **A2 student experiment/config route**
   - Add an A2-specific experiment config such as `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`.
   - Defaults must use A2 env/robot/reward/obs/trainer routes:
     - `/env: door_open_a2_base`
     - `/robot: A2_Piper/a2_piper`
     - `/rewards: wbmanip/reward_door_open_a2_base`
     - `/obs: wbmanip/door_open_a2_base_dagger`
     - `/trainer: trl_distill_obj_pred_a2_base_api`
   - Preserve student training features from origin where still valid: DAgger BC loss, teacher rollout ratio/curriculum, ResNet18 + LSTM, optional object prediction, camera/domain randomization, save/eval/export workflow.

3. **A2 distillation trainer**
   - Add A2-specific trainer source, e.g. `gr00t/rl/trl/trainer/distill_trainer_obj_pred_a2_base_api.py`.
   - Do not inherit or call HOMIE-specific trainer logic for final A2 route.
   - Reuse the frozen A2_Base loading and `_a2_base_actions()` semantics from `ppo_trainer_a2_base_api.py`.
   - During rollout:
     - Student emits 12D high-level action.
     - Frozen A2_Base consumes `a2_base_obs` plus high-level base command and produces 12D leg action.
     - Env receives 24D rollout action.
   - During BC loss:
     - Compare only student 12D high-level action against teacher 12D high-level action.
     - Do not include frozen A2_Base leg action in learnable BC loss.
   - Preserve recurrent hidden-state reset behavior for both teacher and student.
   - Keep fail-fast checks for obs/action leading shape, recurrent padding/unsplit layout, A2_Base obs dim, A2_Base action dim, checkpoint keys and config drift.

4. **A2 student observation contract**
   - Add `gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml`.
   - `teacher_obs` must match A2 Teacher actor input contract exactly in term order, dim, scale, noise policy and history semantics.
   - `actor_obs` must be redesigned as A2 student proprioception + compact task state, not copied from G1 `door_open_homie_dagger.yaml`.
   - Student `actor_obs` should include A2-specific equivalents for:
     - base orientation/angular velocity cues,
     - A2 leg/arm/gripper proprioception using name-based A2 DOF groups,
     - previous high-level/student action or A2 parity action surface as appropriate,
     - processed `a2_base_command`,
     - stage/complete terms only if they are intended to be available to the deployed student.
   - Remove or replace G1-only terms:
     - `dof_pos_non_finger`,
     - `dof_vel_non_finger`,
     - `b_homie_commands`,
     - HOMIE lower-body observation names,
     - G1 finger/hand-specific assumptions.
   - Keep `a2_base_obs: 1620D` available for frozen A2_Base inference in the trainer; do not blindly feed it into student actor unless explicitly designed.

5. **Vision/camera route**
   - Enable `vision_obs: rgb_image` through IsaacLab `TiledCameraCfg`.
   - Replace origin `camera_attached_link: d435_link` with a validated A2 body or a new explicit camera mount link.
   - If adding a camera mount, use IsaacLab high-level scene/sensor config where possible; avoid low-level USD edits unless there is no high-level API route.
   - Validate camera extrinsics against the A2+Piper task: door/handle/pregrasp region should be visible during approach, grasp and open stages.
   - Fail-fast when camera link/body is missing, camera output shape is wrong, or RGB data is not available.
   - Keep image augmentation/domain randomization only after base camera rendering is verified.

6. **Object prediction auxiliary target**
   - If keeping `obj_pred_loss`, define an A2-specific `gt_obj_pos` target source.
   - Do not reuse `head_target_frame_transformer` / `head_link` without validation.
   - Prefer target semantics aligned with A2 task: handle/grasp target or pregrasp target in a clearly documented source frame.
   - If object prediction is not part of the final design, explicitly disable it and document the reason; do not leave stale G1 target config active.

7. **Network architecture**
   - Student actor can initially preserve origin `VisionRecurrentActorObjPred` / ResNet18 + LSTM structure if dimensions are adapted.
   - Output dim must be A2 high-level 12D.
   - Running mean/std, recurrent hidden dim/layers and MLP hidden dims should be aligned with A2 Teacher route unless there is a documented reason to diverge.
   - Any architecture change must update checkpoint loading, eval, export and memory.

8. **Evaluation/export route**
   - `eval_agent_trl.py` must be able to load the A2 student checkpoint and restore the A2 student config sidecar.
   - Eval rollout must compose 12D student high-level + 12D frozen A2_Base action into the expected 24D env action.
   - Video/eval diagnostics should support student camera route and still report stage/reward/completion metrics.
   - ONNX/export path, if used, must export the A2 student policy semantics rather than HOMIE-specific command/action assumptions.

9. **Training/eval validation gates**
   - Hydra compose for A2 student config.
   - Static obs/action dim check: teacher obs, student actor obs, vision obs, `gt_obj_pos`, A2_Base obs, 12D student action, 24D rollout action.
   - Teacher checkpoint load smoke with A2 checkpoint.
   - Camera reset/render smoke with `num_envs=1`.
   - One-step trainer rollout smoke verifying teacher action, student action, A2_Base leg action and env action composition.
   - Short DAgger train smoke with cameras on.
   - Student eval smoke from produced checkpoint.
   - Only after these pass should full-scale Phase2 training be treated as ready.

## Design Guardrails

- Full A2 adaptation means replacing G1/HOMIE assumptions, not wrapping them with fallback compatibility.
- Follow fail-fast style: missing camera link, obs key mismatch, dim drift, teacher checkpoint mismatch, target frame mismatch and A2_Base metadata mismatch should raise immediately.
- Do not add fallback to G1/HOMIE checkpoint, `d435_link`, `head_link`, G1 finger slicing or HOMIE lower-body models.
- Use structured configs and name-based A2 DOF/body groups; avoid positional slicing unless the slice is explicitly derived from validated A2 config.
- Any IsaacLab scene/sensor implementation should use IsaacLab high-level APIs first. If low-level USD is required, document why in code review and memory.

## TODO Summary

- 2026-07-08 15:11 HKT - Implement the full A2+Piper Phase2 Student Distillation route: A2 teacher checkpoint dependency, A2 student experiment/obs/trainer configs, A2 distill trainer using frozen A2_Base, A2-specific student proprioception, validated A2 camera route, optional A2 object prediction target, eval/export support and staged validation gates.

## DONE Summary

- 2026-07-08 15:11 HKT - Created the independent planning memory entry for full A2+Piper Phase2 Student Distillation adaptation.

## Recommended Next Files To Read

- `memory/a2-piper/worktree-routing/description.md`
- `memory/a2-piper/doorman-door-training-goal/description.md`
- `scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md`
- `gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml`
- `gr00t/rl/config/obs/wbmanip/door_open_homie_dagger.yaml`
- `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml`
- `gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`
- `gr00t/rl/trl/trainer/distill_trainer.py`
- `gr00t/rl/trl/trainer/distill_trainer_obj_pred_homie_api.py`
- `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`
