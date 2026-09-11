# Claude Code novelty 裁定原文摘录

原回答时间：2026-09-05 08:27 HKT。状态：历史规划裁定，不是实验成功声明。

来源：[完整讨论片段](../conversations/20260905_claude_novelty_route.md)，最终回答源行 672。这里只摘录“二、novelty 路线裁定”；未改写原判断。其“v28 入口”排期已被 2026-09-09 的 v29 顺延决定取代，见 [当前状态](20260910_novelty_status.md)。

## 二、novelty 路线裁定

| 你的想法 | 裁定 | 一句话理由 |
|---|---|---|
| 1. 放弃 force-feasible，改为本体感知实时估门、按门难度分层行为 | **远期主线，v28 入口；v27.2 先埋测量** | 同意放弃 certificate 那套准入机器，但目标要从"精确辨识 mass/hinge drive"改成"对控制有用的交互状态估计"，用 action-conditioned history latent 做，用 episode 内参数变化检验。前提是先有真实存在"arm 单独不够"的门域，这正是 v27.2 要建的。 |
| 2. 瀑布改树、push/pull 合一、repair 分支、可被打断 | **拆开：失抓重抓环现在切入（v27.4）；push/pull 合一与多次打断远期；按外部条件长策略树不合适** | v26-7 已证明单一条件化 actor 覆盖两侧，树比它更不通用。当前框架 stage 只能单调上升，失抓只能等超时，这是 sim-to-real 的主要失败面，也是 pull 回弹场景的必需能力。正确抽象是带返回边的有向图；方法问题是显式恢复状态加失效边界采样是否优于同预算普通扰动训练。 |
| 3. arm–base 联动 critic / 动力学 / reward | **当前不合适，带入场条件进停车场** | v22 到 v25 四轮结论：当前门域 arm 单独够用，posture 帮的是几何不是力，body-assist 不安全。没有 arm 单独失败的 regime，学联动只会造出看起来联动的动作，无法证伪。入场条件是 v27.2 或 v28 门域出现 arm-only 失败层且测得可预测的 interaction residual。 |

Astra 的判断与我大体一致，差别在我把方向 1 的测量提前进 v27.2、把 K 的第二次检验放进 v27.3、把资格候选集保留 K_S2。

**长期 TODO 已更新**（`scriptsFORhuman/a2_piper_longterm_TODO.md`）：新增 R 节路线裁定；Worktree 分工改写；A 表换成 v27 与 pull 排期；B 表的左右镜像项收口；C 节 force-feasibility 路线图降级为背景并加第 10 条；D 停车场新增 N-01 到 N-06 与 K 二次检验、否决策略树；归档补 v25、v26 收口与规则 19 到 21（guard 与机制目标正交、收益谷、长跑环境显式化）。

