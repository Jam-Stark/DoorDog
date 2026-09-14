# Pull G0完成 — 2026-09-14 m5

**PULL_G0_PASS：计划PG1–PG8范围内的工程接线验收完成。** 接下来按原授权启动三scratch PA格；不把5batch结果解释为opening能力。

P2已先完成18条natural诊断并封存。MERGED/140mm/38.76°/新reset/D17/pull bundle按输入应用；contact_a3及m5三姿态匹配D37沿用原有效证据，不重复运行。固定pull事件/ready/Stage4、无K及A2_Base不变。

本次真实smoke actor/critic133/138，256env×5batch完成并保存full model_step_000005.pt。随后双侧实际natural64完成：每侧completed/terminal/per-env records均64，归约均VALID，bundle及camera字段存在。终止皆stage_overtime，K5/D/E4–E7均0，margin=NOT_OBSERVED。晚阶段事件未出现，零事件门映射与名义投影不证明释放或光学能力；相机阈值仅报告。原三seed endpoint仍未开始。

此前工程故障全部保留：关闭接口吞异常、natural注册冲突、flat robot引用、smoke保存250、flat评估环境数256、归约器引用非实际driver字段。按Owner D013明确的自主工程修复权限处理，无降门/裁剪数据/新增fallback。原256评估标INVALID_NUM_ENVS，正确64评估使用新输出，未多跑训练。G0累计10 batches≤32。

证据：G0_ACCEPTANCE_20260914.json；evidence/g0_attempt3_20260914训练；evidence/g0_eval64_20260914评估；旧evidence/g0的contact和PG7。链路运行、checkpoint、eval有效性与科学终点分别报告。PG8是此短链路的实际接线证明，正式milestone watcher与原三seed聚合继续在PA实际运行中完成。
