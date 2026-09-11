# Codex / Astra：三条 novelty 路线独立讨论

整理时间：2026-09-10 22:06 HKT。

来源：`/home/baoquanc/.codex/sessions/2026/09/03/rollout-2026-09-03T21-15-52-01a06769-5a89-7780-8705-c7035834dd29.jsonl`。

任务：[执行 base_v26-8 训练评估流程](codex://threads/01a06769-5a89-7780-8705-c7035834dd29)。Owner 明确要求独立比较并为产出加 `-Astra` 后缀。

范围：下列时间段的人类可读 user/assistant 原文；不含工具调用、工具输出、内部推理及系统指令。保留同段中的 pull/v27 上下文和重复发送，不把摘录写成完整会话。时间为 HKT（UTC+8），每条注明源 JSONL 行号；原文中的旧路径与当时判断原样保留，当前入口见 [README](../README.md)。

---

## 2026-09-05 03:28:02 HKT · Owner · 源行 5472

<environment_context>
  <current_date>2026-09-05</current_date>
  <timezone>Asia/Shanghai</timezone>
  <filesystem><workspace_roots><root>/home/baoquanc/workspace/DoorDog-A2_Piper</root><root>/home/baoquanc/.codex/visualizations/2026/09/03/01a06769-5a89-7780-8705-c7035834dd29</root></workspace_roots><permission_profile type="disabled"><file_system type="unrestricted" /></permission_profile></filesystem>
  <subagents>
    - v26_8_baseline_counts: Archimedes
    - v26_8_endpoint_route_check: Lorentz
    - v26_8_g1_r3_runtime_qa: Euclid
    - v26_8_r3_pattern_audit: Jason
    - v26_8_wave1_r3a_step500_wait: Schrodinger
  </subagents>
</environment_context>

---

## 2026-09-05 03:28:03 HKT · Owner · 源行 5477


# Files pasted by the user:

## "核对完成。我独立重算了 r3a endpoint 的六格计数与配对差，和 closure 一致；另外从 trace 抽了几项 closure 没有列的行为质量…": /home/baoquanc/.codex/attachments/f151d922-76b2-4126-8816-cf84c55431b7/pasted-text.txt

## My request:
首先我同意v26阶段可以收尾的判断。这个收尾动作算作v27的第一步吧。 接下来需要你做三件事：1 另一个pull任务同样困于加入handle LEFT/RIGHT后一直抓握/下压解锁失败，我希望你将v26-8的结果迁移过去。workspace/DoorDog-A2_Piper_pull_v0 worktree是pull分支的code（训练在另一台机器，所以你看不到之前失败产出，需要的话可以发送message/request到codex://threads/01a05113-6e6d-70e0-a017-a733d25d1641 这是另一台机器上的负责codex session），我希望你同样重塑一下pull分支，和当前主线使用一样的v26-8 backbone训练框架/范式。还有pull分支为了开门行为好像修改了observation？我认为pull分支和推门主线应该在这些保持一致，分叉应该是出现在stage3之后？ 这里需要你给出pull分支那边的修改方案和同样的开工prompt（我也是交给pull分支训练机器上的codex团队）  2 （最重要的）需要你考虑v27乃至以后的novelty路线，这是我现在的三点novelty路线想法，请你保持独立思考，判断哪个适合切换为现在的方向？哪个可以放在远程TODO？哪个不合适？ 然后需要你更新scriptsFORhuman/a2_piper_longterm_TODO.md 这个文档
  1. 放弃/修改 force feasible路线，转为 根据 本体感知，去实时调整开门行为。 比如能够根据arm/base 在开门中的本体感知，policy能够知道门的情况（估计mass，hinge drive。。）从而调整自己的行为，也算延续之前的路线，能够自动判断门的属性还有实时的力交互调整行为。普通门：
                      *   近中性姿态 - roll/pitch～0
                      *   arm主导开门
                      *   可控甩门 或 quiet 握持开门
                      *
                      * 困难门：
                      *   有条件 roll/pitch
                      *   根据 阻尼/回弹力 选择 甩门 或 握持开门
                      *
                      * 极限门：
                      *   arm + 姿态辅助失败
                      *   -> trunk/髋关节 辅助
  2. 考虑在 doorman提出的这个 我称之为 “瀑布式”的stage 训练框架上做点新东西。比如将其改成树形式，根据外部条件（比如handle这里LEFT/RIGHT） 来实现policy学习多任务。 这里考虑能不能将pull/push合并到让一个policy学会。或者每个stage增加一个repair环节（比如stage0/1站错位置进入repair分支调整，stage2/3抓空后学习再次尝试重新抓，而不是等待over time 去reset了）  跟进一步可以训练一个 “可被打断”  的policy，比如开门过程中有外部因素干扰导致gripper脱离handle，policy能够重新抓回等。
  3. 还有就是关于arm和base 联动方面，现在好像没有reward/penalty或者动力学建模去指导policy如何通过roll/pitch去更好的增强arm在方面的能力，也没有验证过这个方法有效，之前阶段证明了在当前door的设置下，arm单独就能完成开门任务。是否设计加入一个cirtic负责给联动行为打分？或者给一些动力学建模/耦合指导/reward？3 在2的novelty路线基础上，我同意v27阶段做 LEFT 行为对齐和负载与摩擦分布收敛还有 seed 与从零可靠性。 考虑好2的novelty方向后，落地v27阶段plan和开工prompt。

ps：另一个并行任务也在进行同样的工作，所以你产出的文档要附带 -Astra 后缀用于区分，finish后我会双向参考两边的建议。


---

## 2026-09-05 03:28:17 HKT · AI · 源行 5480

我会先核对你附上的分析和现有 memory，再并行梳理 pull 分支差异、三条 novelty 路线的证据。最终交付带 `-Astra` 后缀的 pull 修改方案与开工 prompt、长期 TODO 修订版，以及 v27 plan 与开工 prompt；这轮以方案和文档为交付。


---

## 2026-09-05 03:32:51 HKT · AI · 源行 5545

我已读到 pull 负责会话的历史记录。先纠正附件中的一个关键概括：K_S2 的 LEFT 在 step1500/2000 的 complete 只有 1/0，不能说三组从 step1500 起都持续稳定。这个事实不影响 v26 收尾，但 v27 的候选资格验证必须独立成立，不能直接把终点高计数当作可靠性证明。


---

## 2026-09-05 03:34:16 HKT · AI · 源行 5595

文献核对发现一个会改变选题定位的事实：CoRL 2024 已有同一策略处理推/拉、左右门，并在交互中估计门属性的工作。因此，“本体感知估门参数”或“推拉合一”本身不足以作为 novelty。我倾向把近期方法重点放在“失抓后能重新进入任务的循环技能图”，把负载自适应作为后续扩展；额外 coupling critic 暂不进入 v27。接下来用报告技能把这些证据、边界和执行条件整理成独立的 Astra 文档。


---

## 2026-09-05 03:39:44 HKT · AI · 源行 5656

pull 的检查结果更具体了：主干 native 路径与 push 都是 135-D actor / 140-D critic、12-D action；主要风险来自后来增加的专用 actor/head 和 Stage3 接管时序，而非必须换一套 observation。方案会统一接口，但保留出生时就必须正确的 pull 几何、开向和 tensile gate——这些不能等到 Stage3 后才分叉。


---

## 2026-09-05 03:47:24 HKT · AI · 源行 5687

六份 Astra 文档已写好，正在做最后的路径与合同一致性核对。v27 被拆成可提前收口的几段：资格确认 → 单一质量干预 → 摩擦分布 → 三 seed 真 scratch → 条件恢复 pilot。基础门未过就停止后续实验；coupling critic 和推拉联训没有混进首轮预算。


---

## 2026-09-05 03:49:14 HKT · AI · 源行 5715

已完成六份 `-Astra` 文档，事实、提案和未验证事项已分开。

我的核心判断：

- **近期选方向 2**：做“失抓—重抓—继续开门”的循环技能图，而不是简单按左右分树。
- **方向 1 放中期主线**：估计对控制有用的交互状态，不预先承诺精确辨识 mass/hinge 参数。
- **方向 3 暂缓**：先证明姿态带来的实际收益，再考虑 coupling critic；body-assist 留远期。

关键文献边界：推拉统一、交互估门属性、重试恢复已有先例；新意必须落实到机制及同预算对照，不能仅靠功能名称。[最近邻工作](https://arxiv.org/abs/2409.04882)

交付：

- [Novelty 独立判断](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_novelty_route_20260905-Astra.md)
- [长期 TODO 修订版](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO-Astra.md)
- Pull：[修改方案](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pull_v26_8_alignment/a2_piper_pull_backbone_plan_20260905-Astra.md) · [开工 prompt](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pull_v26_8_alignment/a2_piper_pull_backbone_start_prompt_20260905-Astra.md)
- v27：[执行 plan](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_plan_20260905-Astra.md) · [开工 prompt](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_start_prompt_20260905-Astra.md)

Pull 建议统一 native obs/action/backbone，但开向、入手几何及 tensile gate 必须从早期保持正确，不能全部推迟到 Stage3 后分叉。

本轮仅新增文档；保留无后缀 TODO 供你合并两方建议。未修改训练代码、启动训练或 commit；只读 agent 已结束，未新增 tmux/lease。

