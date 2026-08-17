# DONE

- 2026-07-03 20:53 HKT - 修复 full 6-stage entry 的 A2/G1 reset path mismatch blocker。

  (1) `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml` 新增 `env.config.reset_from_dataset.enabled=False`。

  (2) Rationale: `ResetFromDataset._reset_from_dataset_enabled()` 在缺少 `enabled` key 时默认 `True`，会让 A2_Piper full training 误加载 `${HOME}/projects/LAFAN-G1` 并用 G1 motion dof/body names 映射 A2 robot，重现 stage0-2 早期已诊断过的 fail-fast mismatch。

  (3) Hydra resolved full exp 验证：`reset_from_dataset.enabled=False`，`max_stage_time=[250,100,100,100,100,200]`，trainer 仍为 `trl_a2_base_api`，project 仍为 `a2_piper_open_door_a2_base`。本轮未跑 PPO/IsaacSim smoke。

- 2026-06-25 20:30 HKT - 完成 `quickTEST` branch fast-forward merge 到 `A2_Piper`：A2_Piper HEAD 推进到 `34e06b7`，无冲突。
- 2026-06-25 20:30 HKT - 完成 C 类文件删除：`gr00t/rl/config/exp/wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml`、`memory/a2-piper/stage0-2-grasp-terminal/` 目录（description.md / TODO.md / DONE.md）。
- 2026-06-25 20:30 HKT - 完成 `memory/a2-piper/MEMORY.md` 更新：删除 `stage0-2-grasp-terminal` route 行，新增 `quicktest-merge` route 行。
- 2026-06-25 20:30 HKT - 完成新建 `memory/a2-piper/quicktest-merge/` memory entry（description.md / TODO.md / DONE.md），记录合并内容清单、A/B/C 分类与 6-stage 影响边界。
- 2026-06-25 20:30 HKT - 完成 `memory/a2-piper/reward-implementation-goal/` 更新：补充 stage2 contact history gate、stage2 close shaping rewards、pregrasp_gripper_dof_pos_l1 stage-aware target、penalty_base_roll_pitch_l2 已从 quickTEST 合并回主线。
- 2026-06-25 20:30 HKT - 完成 `memory/a2-piper/doorman-door-training-goal/` 更新：补充通用 bugfix（OrderedTargetFrameTransformer、A2_Base init、ResetFromDataset、PPO recurrent unsplit、eval rendering/diagnostics、staged_task_base last-stage complete gate、toolbar patch、JSON serialization fix）已合并回主线。
