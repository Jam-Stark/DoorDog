# v29 总体安排

更新：2026-09-19 01:25 HKT。D030–D031：Owner授权完整baseline worker与planner离线自主协调；planner逐项验收后批准首轮GPU0训练。

状态：baseline方案已确认，进入worker完整实现与planner验收阶段。本文保留总体方向；当前首轮开训权按D030–D031由planner在验收后绑定具体命令/预算，仅GPU0。

**当前职责（D030–D031）**：worker team负责整个baseline实现、最后修正及训练监督；planner负责逐项严格验收、方案裁定和GPU0开训批准。Owner离线期间双方自主通过turn/steer或queue沟通。B04/B05方案完成保持，与实现/验收状态分开；完整[worker prompt](a2_piper_base_v29_worker_start_prompt.md)和[验收合同](a2_piper_base_v29_acceptance_and_coordination.md)为当前执行入口。

## 阶段方向与 GPU 分工

| 任务 | 方向 | 计划使用的物理 GPU |
|---|---|---|
| 1 | 建立稳定、优秀的 v29 push baseline，以 2 个 seed 检查稳定性 | 0、1 |  UPDATE：GPU0跑baseline，GPU1跑baseline default handle ablation
| 2 | 在 v29 推进失抓恢复 N01 | 2 |
| 3 | 在 v29 推进交互历史适应 N02 | 3 |
| 4 | 将 baseline 的适用改动同步到 `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`，以 2 个 seed 检查 pull 稳定性 | 4、5 |
| — | 根据任务 1–4 的进展动态分配 | 6 | UPDATE：GPU6 分给了pull分支跑baseline，
| — | 监控、eval 与其他任务灵活使用 | 7 |

上表仍是后续阶段方向，不表示GPU当前空闲或被本任务占用。最新授权先由planner完整验收后批准GPU0首轮baseline；GPU1第二seed和其他分支不自动启动。seed291/4096env/6000batches是提交默认，最终精确配方/预算/ETA由planner根据当前证据批准。

## 基础版本与独立工作时机

- 当前逐项讨论并维护[baseline TODO](a2_piper_base_v29_baseline_TODO.md)。Owner于2026-09-18要求开始落地[baseline plan](a2_piper_base_v29_baseline_plan.md)：先收录B01/B06/B07及已有基础决定，整体clean后完成全文与执行安排；B01讨论确认不等于物理代码已实施。
- **B02安排变更（D020）**：当前baseline不做B02，保留现有实体latch/mimic；B04按两份Pro反馈形成独立于B02的baseline设计。其他baseline项确定后，再从共同baseline版本单开apply B02分支做ablation（建议名`codex/v29-apply-b02`）。当前未创建分支，未分配额外GPU/预算；具体B02改动组与共同对照设置届时确定。B02分支时机以其他baseline项确定为准，N01/N02的既有启动条件分别保留。
- **N02讨论范围补充（D023）**：强回弹时重新伸臂扶门（首版限定重新抓把手）及相应奖励/回臂协调留N02讨论，不作为baseline前置。baseline已精确回退D021收入关闭；B04继续原生最大角随机化计划。N02仍在baseline落地后独立分支开展，未新增预算/GPU占用；N01原有议题不自动取消。
- N01/N02 已由本次 Owner 决定纳入 v29 大方向，取代此前“是否纳入 v29 尚未决定”的状态；旧 pilot/shadow 的证据限制仍然成立。
- N01/N02 涉及 Doorman 范式、状态机或网络等较大变化，按 Owner 要求等待任务 1 的 v29 baseline 落地后，再 checkout 到各自独立 branch/worktree 开展工作。先期研究讨论可以并行，当前不创建分支/worktree、不修改方法实现。
- pull 承接共同 baseline 改进；同步时分别辨认共同 obs/action/capability 与 pull 的任务动力学/阶段语义。当前只记录方向，尚未修改 pull 工作区。
- 当前已授权worker完整实现与监督、planner验收/修正反馈/最终审批。正式训练仍以planner对当前候选发出的GPU0 TRAIN_APPROVED为准；无需Owner在线重复审批日常进展。

## 当前讨论入口

六项初始议题完整登记在 [baseline TODO](a2_piper_base_v29_baseline_TODO.md)。已经实施的 Stage5 reward、handle 高度和腕机/reset 决定继续见 [V29-D001–D003](a2_piper_base_v29_decision_log.md)，不重新当成待实施建议。
