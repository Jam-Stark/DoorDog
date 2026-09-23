# Owner：v29 LEFT/RIGHT动态分配初步研究请求

2026-09-21 HKT；Codex任务“v29 planner”；仅本轮请求摘录，不是完整对话。此前B08公共开发修复已完成，现有GPU0/GPU1训练仍使用各自原冻结源码。

> 继续讨论， 从 v29 baseline训练和baseline B05-ablation 训练 的当前结果来看， LEFT/RIGHT的训练优势处于随机状态？ baseline训练下来看的趋势是 LEFT表现比RIGHT好，而B05-ablation表现下来又是 RIGHT优于LEFT？ 而无论是LEFT/RIGHT的卡点都是stage3处缺少抓握后下压解锁的成功案例。那么我在想要不要引入动态 LEFT/RIGHT分配机制？ 你先独立思考/研究，给我一个初步判断

本轮授权为独立研究及初步判断，不是动态分配实现、实验或更改当前训练合同的授权。分析见[初步判断](../documents/20260921_v29_bilateral_curriculum_initial_judgment.md)。

## 后续Owner决定与问题摘录

> 1. 同意先把弱侧 Stage3 的失败拆清楚：没压下、压下后门不动，还是门动了但握持不满足晋级条件。

> 2. 我查看了子agent “V29 bilateral sampling path” 的回复，认为一下几点很可能是潜在原因？

Owner引用该子任务关于“v29未启用v27 recovery bank、bank按env保存、PPO统一batch及全局advantage标准化”的段落，并要求：

> 用大白话解释下v27 recovery bank的作用，和这里PPO为什么没有进行per-side normalization 或 weighting？

引用范围仅为本轮可见请求；上段对长源码引文作明确摘要，不冒充逐字原文。

## Owner追加跨分支与v28归因请求

> 我查看了pull分支，那边却没有这边baseline展现出来的LEFT/RIGHT 训练失衡问题

Owner指定pull step4000的left_a4/right_a1两份a2_v14_per_env_records.json，链接保留在[跨分支归因报告](../documents/20260921_cross_branch_bilateral_attribution.md)。

> 所以请你先进一步根据v29 baseline，B05-ablation，甚至v28的eval结构，进一步分析LEFT/RIGHT 训练中失衡的问题归因。 我记得v28初期也是LEFT/RIGHT 失衡，但是后续随着iteration增长，后续LEFT/RIGHT都能到达goal了。
