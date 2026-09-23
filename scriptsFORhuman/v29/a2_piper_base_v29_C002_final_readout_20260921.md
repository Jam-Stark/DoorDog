# v29 C002：首轮训练与最终自然评估验收

2026-09-21 HKT；PLANNER，D072。候选 `C002` / `v29-c002-baseline`，完整B05，seed291。依据D060执行合同、D061 loss可观测性例外及D066通信规则。正式决定见[D072 JSON](../../.ai/runtime/v29_baseline_team/D072_C002_FINAL_DELIVERY_ACCEPTANCE.json)，worker交付见[FINAL_DELIVERY](../../.ai/runtime/runs/v29-c002-push-seed291-natural-final/FINAL_DELIVERY.md)。

**验收结论：冻结C002实现及本轮训练/评估交付接受并关闭；策略尚未展示整任务成功，最终64个自然首episode为0/64。** 保留D056/D060的实现验收范围，不将工程执行成功写成策略质量PASS或完整任务Teacher资格。已知B08另行保持OPEN。

## 执行与实际证据

| 项目 | 已核对事实 | 结论边界 |
|---|---|---|
| 正式训练 | GPU0、4096 env、scratch、seed291、6000 batch，实际命令/cwd/worker与D060一致；2026-09-21 03:15:17 HKT exit0，163653.914s＝45.4594h，低于48h | 按合同完成，没有重启/追加seed或新预算 |
| final checkpoint | 精确 `model_step_006000.pt`，worker CPU读回global_step6000、actor/value张量有限；后续实际full load成功 | Main没有重复载入权重；有限final张量不证明全程loss有限 |
| terminal capture | Main读原始end.json，phase=end、global_step6000、4096 env/metadata；worker begin/end参数比较不变 | 关闭D060此前“终点capture只检查过接线”的证据缺口；未重复全表核对 |
| 最终评估 | 03:17:09–03:29:12 HKT，GPU0串行、一次64 env/64自然首episode，exit0，723.228s，低于1200s | 实际命令与D060一致；非staged评估，没有额外运行 |
| 观察条件 | 实际runtime config为full loader、auto_load_latest=false、seed291、staged reset=false、reward penalty curriculum=false、penalty driver=null；无render/camera | 不把训练staged日志当自然评估 |
| 实际加载 | 原始v29_checkpoint_load.json确认actor/value strict、无缺失/多余key、actor RMS、optimizer、scheduler、trainer step6000均加载 | environment loader后执行自然reset；不称为精确物理/阶段episode恢复 |

训练终点打印mean reward93.26352、entropy12.92680，LEFT历史最高Stage5、RIGHT Stage3，goal计数打印0；它们包含staged reset及聚合口径，不能换算成自然成功率。数值loss仍为 **NOT_OBSERVED**。

## 64个自然首episode的结果

一个只读runtime reviewer从原始per-env records和metrics独立核算：env_id 0–63各一次、全部seed291，按terminal diagnostics的env_id对应完成顺序，逐行stage/goal一致。

| 门侧 | episode数 | 最高Stage2 | 最高Stage4 | 最高Stage5 | goal | 终止 |
|---|---:|---:|---:|---:|---:|---|
| LEFT | 32 | 2 | 27 | 3 | 0 | 32个stage_overtime |
| RIGHT | 32 | 32 | 0 | 0 | 0 | 32个stage_overtime |
| 合计 | 64 | 34 | 27 | 3 | 0 | 64个stage_overtime |

episode长度为827×34、1129×27、1430×3，分别对应最高Stage2、4、5。LEFT另有6个crossing-while-holding记录、10个有实际release字段的记录；RIGHT均为0。它们是不同描述性事件，不是任务完成。

因此可以说：本样本LEFT多数已推进到后段，而RIGHT全部停在Stage2；不能据此单独归因B05某一族、镜像、B08、奖励或具体物理机制。0/64是此次有限样本的观测，不是总体成功概率精确为零的估计。

## 域覆盖与限制

实际导出把手高度0.900659–1.199442m，门重33.9657–158.6098kg。Main按已批准C002三档质量范围和hinge drive maxForce为0/正值，从导出的连续值重建mass×closer分组：每侧六格均为5–6个，与worker汇总一致。这里明确是派生分组，原记录没有直接的bucket/closer标签。

最终逐集导出没有B05 family或逐门最大开角字段，不能声称实际七族各自的结果或按最大开角分组的效果。训练4096的实际域覆盖证据保留原范围，不替代这64例的缺失标签。这份逐集导出也不能直接冒充D067要求的完整A64共同metadata表；GPU1最终评估仍遵循原已批准配对/独立分布规则，禁止截取训练4096表前64。

原始1.34GB逐步trace保留，本轮没有展开新的诊断研究。没有新仿真、训练、评估、渲染、source审计或测试。

## 收尾与未决项

D060这一轮实现/执行交付结束，GPU0本任务租约的实际关闭记录见D072。GPU1 HA-C001为独立任务，保持D067合同及持久化等待；本结论不改变其候选或预算。

[baseline TODO B08](a2_piper_base_v29_baseline_TODO.md)仍为高优先级OPEN：Stage0逐步覆盖六维arm累计target，已确认但未修复。此次结果没有证明它是0/64或左右差异的单一原因。后续修复/诊断、额外seed及N01/N02实施均需各自明确范围；本次不追加运行，也不更换既有Teacher/G7绑定。

原始证据入口：[训练读回](../../.ai/runtime/runs/v29-c002-push-seed291-train/final_train_readout.json)、[评估读回](../../.ai/runtime/runs/v29-c002-push-seed291-natural-final/final_eval_readout.json)、[逐env记录](../../logs_eval/base_v29/push_baseline_C002_seed291/natural_final/a2_v14_per_env_records.json)、[metrics](../../logs_eval/base_v29/push_baseline_C002_seed291/natural_final/metrics_eval.json)、[实际加载记录](../../logs_eval/base_v29/push_baseline_C002_seed291/natural_final/v29_checkpoint_load.json)。
