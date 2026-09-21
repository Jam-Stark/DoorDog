# Codex：N01 planner 最小设计请求

归档：2026-09-20 16:07 HKT。来源：当前 Codex N01 planner 任务中 Owner 的请求。以下为该条请求原文，不含整段会话、工具输出或内部推理。AI 设计结论另见[最小设计](../documents/20260920_n01_minimal_recovery_transfer_design.md)，其中推荐尚未成为 Owner 决定。

## Owner 原文

你负责DoorDog的N01方向planner工作。保持独立判断，不机械接受历史novelty、Pro提案或此前Main建议。

工作目录：
/home/baoquanc/workspace/DoorDog-A2_Piper

当前任务是收敛N01恢复机制与Teacher→Student能力传递的最小设计。初始授权仅包括研究、必要的定向源码追踪、设计讨论和相关文档维护；不自动授权实现、训练/评估、GPU占用、新预算、测试工程、Git提交或外部发布。

一、先建立上下文

按项目AGENTS读取必要规范，并先读：
/home/baoquanc/workspace/DoorDog-A2_Piper/memory/a2-piper/novelty-research/description.md
/home/baoquanc/workspace/DoorDog-A2_Piper/memory/a2-piper/novelty-research/TODO.md
/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/novelty/documents/20260920_n01_pro_review_and_next_step.md
/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pro_reviews/v29/20260920_153418__N01_recovery_transfer/README.md

从回包README读取一页解释、本地定向核对，以及Pro原件中的总评、恢复图、Teacher–Student方案；按问题补读pilot方案和来源。附件已完整保存，不要从Drive重新寻找答案。

本轮输入交付入口：
/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/pro_handoff/20260920_n01_recovery_transfer/README.md

二、主底座与证据边界

使用完整v29 C002，保留B05：
- baseline tag：v29-c002-baseline
- Pro审阅分支：codex/v29-n01-pro-20260920

审阅分支不是已实施N01的方法分支。GPU1的v29−B05消融不能替代主底座。

此前已完成一次相关source/config/既存runtime核对，13份选定文件与审阅分支一致。不要重新审计整个C002；仅针对尚未解决的接口或实际变化追踪源码。Memory和Pro材料不能覆盖当前source、resolved config及实际运行证据。

C002实现已验收，不等于已有成熟恢复Teacher。Pro没有运行新仿真/训练/效果实验。本地核对为INSPECTED，恢复收益、Student自主能力和novelty均未证明。

三、必须保持准确的事实

1. 当前A2 DAgger默认enforce_teacher_rollout=true、ratio_teacher_rollout=1.0；按固定env前缀分配执行权，没有自动退火。Teacher每步查询，Student同时forward，不代表Student实际控制了环境。

2. 默认rollout为8 tick，当前storage没有跨rollout事件序列聚合。Teacher/Student在线hidden按真实done reset，不会每8 tick清零。Pro提出的完整episode前缀重放是新增方案，不是已证明必须先修复的训练栈故障。

3. Student为81D＋RGB，没有Teacher的stage/contact/门真值。81D中的actions实际为12D腿动作＋6D累计arm target＋1D gripper；另有6D delta_actions，当前BC标签为12D高层Teacher动作。设计扰动、执行适配器和监督时必须区分这些字段。

4. 当前Stage0会按真值stage覆盖arm累计target；这是命令目标变化，不是物理关节瞬移。Pro提出的stage-blind执行适配器＋effective-increment标签属于控制接口变化。若采用，相关Student比较应共享接口并说明名义代价。

5. 当前实时把手G已经更新。恢复落点仍需处理门继续运动、可达性、时间和奖励。base重定位还会遇到Stage1停稳条件、Stage1/2前移惩罚，不能只讨论Stage4/5 arm-return。

6. v29 Student实际组合和相机输入仍待设计/resolve；旧DAgger默认配置不能直接当作已对齐C002。完整prefix重放、事件库、网络更换、扰动比例及预算都不是已接受要求。

四、你需要收敛的设计

回答并连接四个问题：
- 哪些失败值得恢复，如何区别真实loss、正常release、仍保有抓握和可以直接通过？
- 退到什么可执行的物理条件，怎样继续原任务并保持时间/进展语义？
- Teacher如何获得有效失败暴露并学会恢复，现有Teacher在哪些状态能提供可信标签？
- Student如何亲自经历这些状态，获得可由自身信息实现的监督，并正确维护循环历史？

Main建议把“正常释放前的局部真实失抓→原地闭合或实时pregrasp→恢复→继续原任务”作为最小起点。这只是建议；请独立判断L2 base重定位或L3重观察是否首轮必需。不要默认先实现全部恢复图、多技能网络、完整snapshot库或Student RL。

先明确最小执行/动作历史/监督接口，再选择足够的数据与记忆方案。解释何时需要跨rollout序列、完整prefix重放或Teacher adaptation，不把这些工程一律列为前置条件。

比较设计应能分开：
- Teacher失败课程的收益与名义代价；
- Student实际执行所带来的数据收益；
- 同等数据下事件采样的收益；
- Student自主恢复与Teacher前缀/接管成绩。

五、N01/N02与资源边界

Owner D023将强回弹后重新伸臂、重抓把手移入N02。Pro建议释放后P→A可后续归N01，这是待Owner采纳的分工变化，不能自行覆盖D023。

N02在线适应和A2＋PiPER动力学/方向力建模是独立研究，不视为已有结果或N01已实现依赖。

既有GPU0/GPU1任务由原监督任务按原合同及持久化等待处理。不要轮询或接管，也不要把此前GPU2/GPU3方向规划当作当前资源/预算授权。

六、首轮交付

给Owner一个具体、可讨论的最小方案：推荐范围、恢复落点、Teacher课程、Student执行与监督/记忆合同、涉及的source/config入口、必要的奖励/计时变化，以及未来最小功能演示的操作路径与可见结果。突出真正需要Owner决定的少数选择。

将设计结论与未决事项保存到novelty并更新入口，明确区分事实、推荐、文献结论、推断和本地未知。当前先完成设计；Owner明确要求实施后，再制定相应WRITE_SET、执行路径和必要验证。不要为预研建立庞大回归或护栏体系。

## Owner 后续原文：工作目录独立（2026-09-20 16:44 HKT归档）

先从当前主线checkout 出去 N01分支/worktree，之后在那工作

执行记录见[worktree路由](../../../memory/a2-piper/worktree-routing/description.md)；本条授权建立分支/worktree，没有批准此前方法设计或训练。
