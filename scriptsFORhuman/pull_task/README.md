# pull_task — A2+Piper 拉门 (pull-door, `door_open_io="in"`) 任务文档目录

拉门任务（长期 TODO 表 C 第 4 项：finger-limited 的 force-feasibility 第二实验场）的全部规划文档集中于此。创建：2026-08-03 HKT。

## 阅读顺序（worker 从这里开始）

1. **`a2_piper_pull_v0_worker_execution_split_20260803.md`** — **执行入口，冲突时以此为准**。包含：
   - §2 对云端方案的三条 binding amendments（P1 push 侧 known-good anchor 硬门槛；P1 fixture 质量 = 120 kg 按 resolved config；freeze-guard 前置到 build order 第 3 步）；
   - §3 **WORKER 1** 任务（主线 `A2_Piper` worktree：归档 tag + 删除旧 pull 分支/worktree → commit/push 本目录 → 切 `codex/a2-piper-pull-v0-20260803` + worktree `DoorDog-A2_Piper_pull_v0` → 同步 worktree-routing memory → 完工汇报）；
   - §4 **WORKER 2** 任务（新 pull worktree：15 步 amended build order → P0 admission → P1 机制矩阵 → P2 W/S 初始化实验）；
   - §5 留给用户的 5 条人类决策。
2. **`a2_piper_pull_v0_tensile_feasibility_v1_20260803.md`** — 云端 pro 模型的完整方案原文（逐字归档，已 PASS 采纳为主骨架）。三处被 amendment 修订的位置已就地加 `[AMENDED — …]` 标注，标注指回 split 文档。事件漏斗 E0–E7 定义、change inventory（§E）、phase 结构（§F）、fork 表（§G）均以此为准（除非 split 文档另有规定）。
3. **`a2_piper_pull_door_worktree_cut_and_round_design_20260803.md`** — 本地 planner 的独立分析（peer analysis）。与云端方案独立推导、结论大部分收敛；保留作交叉验证参考与后续云端 audit 轮的输入。其中的 change inventory line anchors 以 `7ba69e5` 为锚（grep symbol，勿信行号）。

## 权限/执行分层

- **Worker 1**（主线 worktree，git 手术，不写代码）：只执行 split 文档 §3。
- **Worker 2**（新 pull worktree）：只执行 split 文档 §4；永不修改主线与 push 线的 config/receipt/log；不碰 v21-B 的 GPU/tmux；GPU7 未授权。

## 关键事实速查

- Warm-start 候选：`logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G4-20260731_004712/model_step_002500.pt`，sha256 `f000f13e…a806d`（split 文档含全值）。
- Resolved v20 G4 真值（2026-08-03 本机核实）：`a2_door_weight_range: [80, 160]`；finger effort 45 N（repo yaml 的 10 N 不是训练真值，rule 10）。
- 旧 pull 分支 `codex/a2-piper-pull-door`（v10 时代，从未仿真）：Worker 1 打 tag `archive/pull-door-v10-static-20260714` 后删除；只移植 direction contract 等设计思想，不 rebase 代码。

## 后续本轮产物落点

- Worker 2 的 evidence/manifest/receipt 落 `scriptsFORhuman/pull_v0/`（云端方案 §D.2/E.9 的 namespace 约定）；本目录（`pull_task/`）只放规划/裁决层文档。
- 训练/评估 artifact：`logs_rl/a2_piper_full_stage_a2_pull/`、`logs_eval/a2_piper_pull_v0/`。
