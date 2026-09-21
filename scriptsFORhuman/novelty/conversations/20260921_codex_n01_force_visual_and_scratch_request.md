# Codex：施力方向可视化与N01从头训练

2026-09-21 HKT。来源：Owner阅读v1.0 plan后的可见消息。下面保存原文，不含工具输出或内部推理。

## Owner原文

我阅读了v1.0的plan，当前有以下问题/建议：
1. 要求：可视化一下当前脉冲推力的施力方向覆盖范围。画面配合实际handle演示
2. 问题：当前是准备使用v29 baseline的已有训练结果作warm-start吗？ 我的想法反而是N01从头开始。

## 本轮落实

使用C002实际采样的B05七族参数和当前夹爪CAD绘制交互方向图，明确仅三条射线、掌部质心施力、无角度散布，几何示意不作为物理失抓结果。

Planner确认v1.0采用C002 warm-start，并独立采纳本轮scratch方向，更新为[plan v1.1](../../v29/a2_piper_v29_n01_plan.md)：取消C002高层权重/RMS继承与T_shared，两Teacher同一随机初始化独立训练；保留冻结A2_Base。每臂6000 update作为新的首轮固定结束点，取代旧warm-start短预算；GPU2授权不变，额外GPU另行申请。详细取舍见[说明](../documents/20260921_n01_scratch_and_force_directions.md)。

本planner未启动方法实现、仿真或训练监督。
