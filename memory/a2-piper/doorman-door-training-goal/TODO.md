# TODO

- 2026-06-14 18:27 HKT - A2_Piper USD physics/control plant 已对齐 LMP Stage1；剩余 training-grade kinematics/collision mapping TODO 收窄为 door-task contact body selection、Piper EE/handle frame、arm/gripper contact semantics 与 reward/observation 侧验证。
- 2026-06-14 18:37 HKT - Door policy observation/action TODO：基于已成功的 A2_Base locomotion layer，设计 training-grade A2_Piper door-opening task observation 与 high-level action surface，覆盖 Piper arm/gripper proprioception、EE/handle/door state、door/handle task frame、normalization、actor/critic obs contract、base command、arm command 与 gripper primitive 的 policy interface。
- 2026-06-13 21:15 HKT - Observation migration workflow TODO：每个 A2_Base obs field 实现前，先从 LMP manager-based training source `lmp_manager_env_cfg.py` 及其 helper 中确认训练时计算/更新逻辑，再给出 DoorDog 当前 direct path 的实现方案；长期协作 subagent Bella 负责辅助提取/总结这部分来源逻辑。
- 2026-06-14 18:37 HKT - A2+Piper reward adaptation TODO：将原 G1/HOMIE-oriented door reward 改为适配 A2+Piper，重新设计/替换 approach、Piper EE/handle interaction、gripper/contact semantics、door progress、success condition、termination、safety penalty 与 reward weights。
- 2026-06-14 20:54 HKT - Stage0 reward migration TODO：以后设计 A2+Piper stage0 reward/transition 时，优先参考 `scriptsFORhuman/g1_doorman_stage0_reward_transition.md` 中的 G1 baseline 表格，并逐项替换 G1 upper-body/finger/HOMIE-specific terms。
- 2026-06-12 18:02 HKT - 在 preview-only env 之后继续接入并验证 training env config、training config、smoke test 与 eval workflow，形成可重复的训练入口。
- 2026-06-12 23:17 HKT - 后续 train smoke 若遇到 Hydra/import/checkpoint resume 指向旧 `homie` entrypoint 的错误，先按 action entrypoint rename 记录检查命令、config defaults、`_target_`、log/checkpoint metadata 是否仍引用旧名。
- 2026-06-12 19:35 HKT - 后续若 `door_open_a2_base.py::_reset_root_states` 的 Doorman stage-0 hardcoded x/y/yaw bounds 改动，需同步更新 A2_Piper preview local constants 与 README，避免 placement bounds preview 漂移。
