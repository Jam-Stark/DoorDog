# A2_Piper Development Memory

本 subsystem 记录 A2_Piper branch/worktree 的开发约定、robot migration、reward design、workspace routing、experiment progress 与当前 TODO/DONE。不要把这些施工状态写入 `origin-reference`。

## Entries

- [worktree-routing/description.md](worktree-routing/description.md): A2_Piper active implementation worktree 与 doorman baseline/reference worktree 的使用约定。
- [doorman-door-training-goal/description.md](doorman-door-training-goal/description.md): 长期目标：基于 Doorman door-opening workflow 替换为用户自己的 robot，并设计/适配 observation、action、reward、env config、training/eval workflow 以完成开门任务训练。
- [push-open-door-optimization/description.md](push-open-door-optimization/description.md): 2026-07-21 16:27 HKT — v15 formal 4×1024 seed0 run已到step3000，但launcher natural exit未独立记录；step2500为selected release（canonical 16/16且四项redline优于step3000）。M27 selected-release 48-door为47/48，seed1/2仅supplementary、非statistical proof；step3000 seed2 14/16使endpoint strict 48-door report fail-fast未生成。下一scope为`door_open_lr`左右镜像的left-workspace GUI/smoke，mass/in-out/student保持独立future。
- [reward-implementation-goal/description.md](reward-implementation-goal/description.md): A2+Piper Doorman reward implementation 近期目标与工程约束，stage0-5 reward code work + transition conditions 已 static PASS，剩余全部是 runtime/smoke 验证项。
- [quicktest-merge/description.md](quicktest-merge/description.md): 记录 2026-06-25 从 quickTEST branch 合并回 A2_Piper 主线的内容清单、A/B/C 分类与 6-stage 影响边界。
- [stage0-2-grasp-terminal/description.md](stage0-2-grasp-terminal/description.md): `quickTEST` 分支的 stage0-2-only Teacher PPO quick test，记录 stage2 grasp completion 作为 terminal success 的实验目标、config 边界与验证 TODO。
- [phase2-student-distillation-a2-piper/description.md](phase2-student-distillation-a2-piper/description.md): Doorman paper Phase2 Student Distillation / DAgger vision policy 的完整 A2+Piper 替代/适配计划，覆盖 A2 teacher checkpoint、student obs/action、vision camera、A2_Base trainer compose、object prediction、eval/export 与 validation gates。
- [phase3-student-bootstrapping/description.md](phase3-student-bootstrapping/description.md): Doorman paper Phase3 Student Bootstrapping / GRPO fine-tuning finding，记录其用途、当前 G1/A2 framework 未实现完整 Phase3 的核查结论，以及未来 A2+Piper Phase3 route 边界。
- [static-visual-alignment/description.md](static-visual-alignment/description.md): 使用 full Isaac Sim GUI experience 静态观察 A2_Piper 与 door 的相对位置/朝向，并记录 preview script 调整边界与命令规范。
- [door-asset-openio-sign/description.md](door-asset-openio-sign/description.md): 静态核查 door asset 中 doorOpenIO 字段对 door 构造、hinge joint sign、reward routing 的实际影响。
- [door-asset-randomization-baseline/description.md](door-asset-randomization-baseline/description.md): 记录当前 Doorman/G1 与 A2 training scene 的固定 `right-hinge + out-opening` baseline，以及后续 door asset randomization / push-pull mixed task 的施工边界。

## Update Rules

- 先读对应 entry 的 `description.md`。
- 需要判断当前施工状态时，再读同 entry 的 `TODO.md` 和 `DONE.md`。
- A2_Piper 的 robot/reward/env config/training experiment 进度记录在本 subsystem 或后续同级 subsystem。
- `/home/baoquanc/workspace/GR00T-VisualSim2Real` 是 doorman baseline/reference worktree，默认只读参考，不在其中实施 A2_Piper 改动。
- Timestamp 使用 `YYYY-MM-DD HH:MM HKT`。
