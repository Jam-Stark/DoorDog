# DONE

- 2026-09-06 — Wave A归档提交1fa2b1e；Wave B接线通过并已启动六格。
  R2 32-batch smoke实际走过bank capture/promotion/reset；P02/P05 native readback均匹配。
  L1首轮ListConfig解析失败在actor加载前，保持实验合同不变于新root各重启一次，原失败保留。
  两个L1训练root均已观测到4096 env和0/2/5 native摩擦桶；六格均已strict actor/RMS加载。

- 2026-09-06 — Wave A六格各3000 batches全部PASS/0；六个milestones共4608 episodes，exact64/侧、integrity0。
  endpoint `QUALITY_UNRESOLVED`，冻结 `RECIPE_A=C`、`CARRIER_A=C_S21 step3000`；没有中途checkpoint替换。
  LEFT/RIGHT clean分别为C_S21 51/41、C_S22 0/39、Q1_S21 5/40、Q1_S22 17/20、Q2_S21 18/21、Q2_S22 16/39。
  所有正式评估、训练及Wave A调度器receipt已封存PASS，未增加预算或更新binding。

- 2026-09-05 — 首个预授权本地提交 `52933a3` 已完成，包含 G0、v27.0、Wave A 合同与启动设施；未 push。

- 2026-09-05 20:15 HKT — G0 与 v27.0 完成。三候选 DEV 共 768 episodes、integrity0；
  最终 NO_QUALIFIED_CANDIDATE，CONF 未运行；18 QA 回合/54 videos 与候选 manifest v1 完整。
  Owner 批准 K 现有 artifact 的 CPU-only 重判，原 INVALID 保留，无训练/DEV 重跑。
  Wave A 已按固定六格/GPU2–7启动，strict actor/RMS load 与首批训练读数均正常。

- 2026-09-05 18:01 HKT — 完成指定 authority/memory/v26-8 closure/plan/执行路径读取。
  三个历史候选已复制至新 v27 inputs，原 checkpoint/config 与副本摘要一致。
  Wave A 六格实际 CPU resolved config 为 STATIC_PASS；C 相对历史 source 的行为参数无漂移，
  Q1/Q2 的差异限定于登记的 G5 overlay。尚未运行正式训练或评估。

- 2026-09-07：Wave B两endpoint冻结；Q_B=DOMAIN_NOT_CONVERGED、RECIPE_B=current、Q_R=UNRESOLVED。固定shadow estimator已完成一次，输出与证据路径见runtime shadow_estimator_cpu_evidence.json。
