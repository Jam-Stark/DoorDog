# base_v27 开工 prompt — Astra

以下正文由 Owner 选择 Astra 方案后下发；本文件不是当前会话已经启动训练的记录。完整 plan 与本 prompt 一并交付，不与另一独立方案静默混合。

---

你是 /home/baoquanc/workspace/DoorDog-A2_Piper 的 Codex Main。执行 scriptsFORhuman/v27/a2_piper_base_v27_plan_20260905-Astra.md，把 v26 收尾资格整理作为 v27.0，随后按门推进 LEFT 功能质量、门侧负载/摩擦分布、seed与真scratch可靠性，最后才条件开启单次失抓恢复环pilot。

先读 AGENTS.md、.ai/ROLE.md、.ai/PROJECT.md、.ai/WORKFLOW.md、.codex/AGENTS.md；再读 .ai/SCIENTIFIC_ENGINEERING.md、.ai/LONG_RUNNING_TASKS.md、MEMORY.md、memory/a2-piper/MEMORY.md、base-v26-scratch-bilateral-teacher 的description/TODO、v26-8 r3a closure；随后通读 Astra novelty route、长期TODO-Astra和v27 plan全文。委托时按 .codex/TEAM.md 使用最少必要 focused agent，默认不用ultra。不要重复完成的v26实现/门/训练。

当前source/resolved config与runtime事实优先；发现与plan冲突时明确记录，不静默篡改实验定义。历史v26-8保持C_ENTRY_EMERGED/C_CONSOLIDATED、W_NOT_DIFFERENT、K_REGRESSED，Wave2未运行。附件关于K_S2 LEFT“1500后一直60+”是错误概括；实际complete为1/0/63/60。不能把候选资格动作当成重判v26。

v27.0只在新root做质量开发集与单候选独立确认；C_S2固定research parent，C/W质量候选，K诊断不选。没有合格候选也是合法结果，不更新G7或Student manifest。complete、clean_complete、crossing_while_holding、strict K5分别按plan定义，不用高complete替代行为质量。

基础实现：新v27 config/runner/reducer，保持native 135/140/12 LSTM/观测/动作语义与loader。v27.1仅C/Q两臂，Q启用既有event_v17 body-contact bundle，不改旧reward函数；seeds101/102/103每格3000。v27.2只在门通过后做相同native backend的L0=P02、L1=P02/P05，seed111各3000。v27.3只有domain通过后做高层policy真scratch seeds201/202/203各6000；不能注入teacher bank或把head-reset称scratch。

v27.4只有三seed确认后才运行R0/R1/R2各1000，单次失抓恢复、同扰动和预算，不加critic或body-assist。保持物理状态/episode时钟/RNN历史，分开active skill与历史max_stage，不能reset伪装recovery。R0单调状态机，R1运行时恢复，R2额外恢复边界采样；一seed只能给pilot结论，不自动启动v28。

准确预算与每阶段门以plan为准：正式训练最多45000 batches，另至多基础/恢复各32-batch smoke。注册milestone自动exact64双侧分域评估；确认集独立且exact128。不改v26固定64reducer来凑128；不在确认集失败后换候选重测。

所有长跑独立tmux，自动orchestrator负责checkpoint/eval/reducer/receipt。记录必要显式proxy环境和真实effective load/config，不新增哈希设施，不泄漏凭据。GPU使用执行时Owner批准的分配，允许与已协调任务共存；不要终止他人任务。确认首个有效更新及自动流程后按事件/长间隔等待，不逐iteration手工轮询；每个注册milestone及失败/结束汇报。

非零退出停该cell，保留证据；invalid与学不会分开。禁止fallback、broad catch、缺失数据补零、放宽门槛、原root重跑、额外seed或超预算救援。必要修复在最小scope中记录cause/fix；超出合同的重训需新授权。只做与新功能相匹配的少量检查，不反复审计历史路径。

Owner采纳此prompt授权plan范围的本地实现、条件模拟训练/eval及必要milestone memory更新；不含commit/push、Teacher/G7/Student handoff、任何hardware，也不含修改v26旧artifact或其他任务。新的阶段机制与quality规则只能落在v27命名空间。

交付带-Astra后缀closure、各typed outcome、所有未运行项、证据等级、changed paths。失败分支同样如实收口，v26不因此重新打开。结束确认自己的writer/tmux/lease已关闭；提出需要的后续选择，不自行跑v28或提交Git。
