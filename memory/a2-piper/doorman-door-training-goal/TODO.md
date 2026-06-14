# TODO

- 2026-06-12 18:02 HKT - 后续训练阶段需在 preview 基础上设计 training-grade A2_Piper kinematics/collision/control mapping，并决定是否复用/替换现有 simulator `robot.asset.usd_file` loader。
- 2026-06-12 22:41 HKT - 后续 observation 目标：在已完成 `a2_base_obs` low-level adapter 之外，继续设计 training-grade A2_Piper task observation，覆盖 Piper arm/gripper proprioception、EE/handle/door state、door/handle task frame、normalization 与 actor/critic obs contract。
- 2026-06-13 21:15 HKT - Observation migration workflow TODO：每个 A2_Base obs field 实现前，先从 LMP manager-based training source `lmp_manager_env_cfg.py` 及其 helper 中确认训练时计算/更新逻辑，再给出 DoorDog 当前 direct path 的实现方案；长期协作 subagent Bella 负责辅助提取/总结这部分来源逻辑。
- 2026-06-12 16:59 HKT - 设计 door-opening reward spec，覆盖 approach、handle interaction、door progress、success condition、termination、penalty 与 reward weights。
- 2026-06-12 18:02 HKT - 在 preview-only env 之后继续接入并验证 training env config、training config、smoke test 与 eval workflow，形成可重复的训练入口。
- 2026-06-12 23:17 HKT - 后续 train smoke 若遇到 Hydra/import/checkpoint resume 指向旧 `homie` entrypoint 的错误，先按 action entrypoint rename 记录检查命令、config defaults、`_target_`、log/checkpoint metadata 是否仍引用旧名。
- 2026-06-12 19:35 HKT - 后续若 `door_open_a2_base.py::_reset_root_states` 的 Doorman stage-0 hardcoded x/y/yaw bounds 改动，需同步更新 A2_Piper preview local constants 与 README，避免 placement bounds preview 漂移。
- 2026-06-14 17:48 HKT - 后续由 main/user 在可交互 full GUI Isaac Sim session 运行 `smoke_a2_base_flat_walk.py`，观察 flat-ground A2_Base stability、root velocity tracking 与 action norm；本 worker 仅做 py_compile、`--help`、metadata/policy fake inference 等非 GUI 验证，不启动 full GUI。
