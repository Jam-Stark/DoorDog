# v29 总体安排

更新：2026-09-18 15:08 HKT。记录：-codex planner；方向与资源安排：-owner。

状态：Owner 已确定阶段方向与 GPU 分工；baseline 正在逐项讨论。本文记录总体安排，不是正式训练方案、实验矩阵或启动脚本。

## 阶段方向与 GPU 分工

| 任务 | 方向 | 计划使用的物理 GPU |
|---|---|---|
| 1 | 建立稳定、优秀的 v29 push baseline，以 2 个 seed 检查稳定性 | 0、1 |
| 2 | 在 v29 推进失抓恢复 N01 | 2 |
| 3 | 在 v29 推进交互历史适应 N02 | 3 |
| 4 | 将 baseline 的适用改动同步到 `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`，以 2 个 seed 检查 pull 稳定性 | 4、5 |
| — | 根据任务 1–4 的进展动态分配 | 6 |
| — | 监控、eval 与其他任务灵活使用 | 7 |

这是本阶段的计划分工，不表示 GPU 当前已空闲或已占用，也未指定训练批数、seed 编号、运行时长或资格规则。继承配置里的 6000 batches / seed291 不自动补成上述安排的实验合同。

## 基础版本与独立工作时机

- 当前逐项讨论并维护[baseline TODO](a2_piper_base_v29_baseline_TODO.md)。Owner于2026-09-18要求开始落地[baseline plan](a2_piper_base_v29_baseline_plan.md)：先收录B01/B06/B07及已有基础决定，整体clean后完成全文与执行安排；B01讨论确认不等于物理代码已实施。
- N01/N02 已由本次 Owner 决定纳入 v29 大方向，取代此前“是否纳入 v29 尚未决定”的状态；旧 pilot/shadow 的证据限制仍然成立。
- N01/N02 涉及 Doorman 范式、状态机或网络等较大变化，按 Owner 要求等待任务 1 的 v29 baseline 落地后，再 checkout 到各自独立 branch/worktree 开展工作。先期研究讨论可以并行，当前不创建分支/worktree、不修改方法实现。
- pull 承接共同 baseline 改进；同步时分别辨认共同 obs/action/capability 与 pull 的任务动力学/阶段语义。当前只记录方向，尚未修改 pull 工作区。
- 本轮授权工作为讨论、定向研究和文档维护；训练、评估与代码实施在后续具体决定形成后推进。

## 当前讨论入口

六项初始议题完整登记在 [baseline TODO](a2_piper_base_v29_baseline_TODO.md)。已经实施的 Stage5 reward、handle 高度和腕机/reset 决定继续见 [V29-D001–D003](a2_piper_base_v29_decision_log.md)，不重新当成待实施建议。
