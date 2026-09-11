# Codex：v28 意图、novelty 进度与原讨论定位

整理时间：2026-09-10 22:06 HKT。

任务：[检查 v28 意图](codex://threads/01a08b91-ad2e-7212-9b04-42ed58ccb111)。

来源：`/home/baoquanc/.codex/sessions/2026/09/10/rollout-2026-09-10T21-46-15-01a08b91-ad2e-7212-9b04-42ed58ccb111.jsonl`。范围为本次建立讨论区之前的人类可读对话；不含工具输出、内部推理或环境指令。这是 2026-09-10 的状态回顾，AI 建议不等于 Owner 已批准的新实验。

---

## 2026-09-10 21:46:26 HKT · Owner · 源行 10

你check下v28的意图


---

## 2026-09-10 21:46:30 HKT · AI · 源行 13

我先看项目 memory 和 v28 的相关记录，确认它要解决什么问题、预期改动是什么。


---

## 2026-09-10 21:47:04 HKT · AI · 源行 33

看过 memory、v28 主计划、当前配置和最新讨论记录。**v28 的核心意图是：把相机安装后的实体约束和适合视觉学习的动作行为纳入训练，重新建立双侧开门 Teacher，为后续 Student 蒸馏准备基础。**

具体有四部分：

1. **更新机器人模型**：纳入安装件质量、碰撞体及腕机支架，让 Teacher 学会避开相机与门板的碰撞。旧 RIGHT 抓握轨迹存在塔架穿板的几何证据。
2. **统一默认姿态与动作语义**：默认臂姿态改为 `[0, 0.10, -0.10, 0, -0.52, 1.57]`，同时限制累积动作目标不越过物理关节限位，解决目标积累过头后难以回位的问题。
3. **让动作适合后续视觉学习**：增加腕部运动、塔架接触和释放后回位奖励。**当前 Teacher 不读取相机图像**；相机可见率只是报告指标。
4. **重新验证双侧能力**：主体是从零训练 3 个 seed，再做独立 DEV/CONF 资格评估；warm-start 按条件探测。通过后产出候选，不自动替换 G7。

依据：[v28 主计划](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md)。

**最新讨论正在调整“哪些东西需要现在定下来”：**你提出先用较大的碰撞包络训练 Teacher，把实际相机高度、俯角延后到蒸馏前确定。这符合分阶段推进的方向，但目前仍记录为 `PROPOSED`，尚未正式修改计划。相应地，“大包络下训练失败”也不能直接解释成“小尺寸最终硬件不可行”。见[最新讨论记录](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/v28_progress_for_planner_20260910.md)。

当前仍是 **G0 暂停、未通过**：安装件异常接触尚未解决，合并版和裁切版待选，G1 与正式训练未启动。本次仅只读核对，没有改动文件或运行仿真。

---

## 2026-09-10 21:48:32 HKT · Owner · 源行 40

那关于novelty 的选择和推进呢，目前情况怎么样


---

## 2026-09-10 21:48:37 HKT · AI · 源行 43

我查一下 novelty 的候选、已做的取舍，以及它们和 v28／v29 的衔接记录。


---

## 2026-09-10 21:49:24 HKT · AI · 源行 60

**目前 novelty 的路线已经选过，但还没有得到“方法有效”的确认；实际推进停在恢复环 pilot 和历史信息的离线测量，后续方法实验已顺延到 v29。** v28 当前承担的是重建实验基线。

| 方向 | 已选定位 | 当前推进情况 |
|---|---|---|
| **N-01：失抓恢复图＋失效边界采样** | 最近期的方法切口 | v27 已实现并做 pilot，结论为 **`UNRESOLVED`** |
| **N-02：交互历史驱动的状态估计／在线适应** | 后续科学主线 | 已做离线 shadow estimator，尚未接入 actor |
| **N-06：arm–base coupling critic／联动奖励** | 暂缓 | 尚无充分证据支持进入方法实现 |
| **N-07b：面向视觉蒸馏的 Teacher shaping** | 新增候选 | v28 只训练带 camera bundle 的版本，配对消融和蒸馏尚未做 |

这些是项目已有的[路线裁定](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO.md:16)，并非已经证明的论文创新。

**N-01 已经推进过，但实验没有回答清楚问题。**  
要检验的是：“显式恢复状态＋失效边界采样”，能否优于同 RNN、同预算的普通扰动训练。三组分别是普通流程、仅恢复环、恢复环＋边界采样。

目前有两个具体问题：

- “仅恢复环”组被读取器误判后停在 step644，缺少完整 endpoint，三组比较不完整。
- 完整训练的 R2，在注入评估中左右侧只产生 **5/64、2/64 次失抓**；恢复后 clean complete 为 **0/64、1/64**。扰动没有充分制造要研究的失败场景。

因此既不能宣布恢复图有效，也不能据此否定它。登记的下一步是**先重新设计失抓扰动与事件定义，再决定多 seed 确认**。[恢复实验结论](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_b_r_step1500_readout_20260907.md:747)

**N-02 有初步信号，但距离在线适应还很远。**  
目标已从“准确估计门重”改成“估计对控制有用的状态”，包括有效阻力、回弹趋势、抓握可信度，以及近期动作能否推动开门。离线 estimator 的 heldout friction／mass R² 为 **0.156／0.331**：历史里有一些信息，但解释能力有限；没有改变 actor，也没有验证 episode 内阻力变化时的适应能力。[离线结果](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_shadow_estimator_readout_20260907.md)

**当前排期是：v28 建立新模型上的可靠 Teacher → v29 继续 N-01／N-02。** 原先设想过“恢复图 × history latent”的 2×2 消融，但前置证据还不足，不能直接当成已经可以开跑的实验。N-07b 则等待 Teacher 资格通过及 Student 配对蒸馏预算。[延期登记](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/a2_piper_base_v28_deferred_register.md:12)

我的判断是：**方向没有丢，但目前工程基线占据了推进重心，novelty 尚未形成闭环。** 下一阶段最需要补上的，是一个能稳定触发失抓、区分恢复方法收益的小实验；N-02 则需要先明确可部署观测输入和具体适应任务，再谈 latent 架构。

---

## 2026-09-10 21:57:40 HKT · Owner · 源行 67

关于novelty的裁定，我当初是在哪个对话讨论过？帮我找一下，claude code和codex来着


---

## 2026-09-10 21:57:47 HKT · AI · 源行 70

我会查 Codex 的任务记录和本地 Claude Code 会话记录，用 novelty 裁定中的关键词定位当时的讨论。


---

## 2026-09-10 21:58:39 HKT · AI · 源行 98

已找到 Claude Code 中你提出三条 novelty 想法的原话，时间是北京时间 9 月 5 日凌晨。你后来还补充说“Astra 模型完成了同样任务，文档带 -Astra 后缀”。我继续定位对应的 Codex 任务标题和 Claude 会话名称。


---

## 2026-09-10 21:59:45 HKT · AI · 源行 119

找到了，**是 2026 年 9 月 5 日凌晨，你同时交给 Claude Code 和 Codex/Astra 的那轮讨论**。以下时间均为北京时间。

**Codex： [执行 base_v26-8 训练评估流程](codex://threads/01a06769-5a89-7780-8705-c7035834dd29)**

- **9 月 5 日 03:28**，你在这个任务最后一轮提出三条 novelty 想法。
- 你明确要求：“另一个并行任务也在进行同样的工作，所以你产出的文档要附带 **-Astra 后缀**……双向参考两边的建议。”
- 产出：[Novelty 独立判断 -Astra](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_novelty_route_20260905-Astra.md)。

**Claude Code：原名 `Main` 的规划会话**

- 会话 ID：`e09e9a1e-287d-44ec-8975-3e4afdc682c4`
- 后来标题变为以 **“Claude Code continuation prompt：完成 base_v26-7 最终总结，并裁定下一阶段入口”** 开头的 `(Branch)`。
- **9 月 5 日 03:19 起**，你提出同样三条想法；**04:01** 补充让它参考 Astra，但必须独立思考。
- **08:27** 给出“novelty 路线裁定”，并更新无后缀的长期 TODO。这就是目前 [R 节路线裁定](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO.md:16)的来源。
- [直接查看原会话裁定记录](/home/baoquanc/.claude/projects/-home-baoquanc-workspace-DoorDog-A2-Piper/e09e9a1e-287d-44ec-8975-3e4afdc682c4.jsonl:672)。

两边都能用这句原话定位：

> “需要你考虑v27乃至以后的novelty路线，这是我现在的三点novelty路线想法……判断哪个适合切换为现在的方向？哪个可以放在远程TODO？哪个不合适？”

Claude 另一个分支会话 `592fc504-dd4b-49f2-9996-843c39c4fc68` 也保存了同一段讨论和最终裁定。

