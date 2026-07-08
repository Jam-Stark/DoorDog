# TODO

- 2026-07-08 15:11 HKT - Implement full A2+Piper Phase2 Student Distillation route, not a minimum viable skeleton:
  - Add A2 student experiment config such as `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`.
  - Add A2 student obs config such as `gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml`.
  - Add A2 trainer config such as `gr00t/rl/config/trainer/trl_distill_obj_pred_a2_base_api.yaml`.
  - Add A2-specific distill trainer source such as `gr00t/rl/trl/trainer/distill_trainer_obj_pred_a2_base_api.py`.
  - Load A2 Teacher PPO checkpoint via `teacher_actor_path` and fail-fast on obs/action/config mismatch.
  - Preserve teacher-student semantics: teacher/student learnable action is 12D A2 high-level action; frozen A2_Base produces 12D leg action for env rollout; BC loss compares only 12D high-level action.
  - Replace G1/HOMIE student obs terms with A2-specific proprioception/task terms and remove stale `dof_pos_non_finger`, `dof_vel_non_finger`, `b_homie_commands`, HOMIE observation names and G1 finger/hand assumptions from the final A2 student route.
  - Validate and implement A2 camera route for `vision_obs: rgb_image`; do not reuse `d435_link` unless the A2 asset/config explicitly adds and validates that link.
  - Define or explicitly disable A2 object prediction target; do not keep unvalidated `head_target_frame_transformer` / `head_link` semantics.
  - Ensure eval/export can load A2 student checkpoint and compose 12D student action with frozen A2_Base action into 24D env action.
  - Run staged validation: Hydra compose, static dim checks, teacher checkpoint load smoke, camera render smoke, one-step trainer rollout, short DAgger train smoke and student eval smoke.
