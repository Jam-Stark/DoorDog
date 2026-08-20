# v23 最终裁决(Final Adjudication,2026-08-16)

依据:v23 全部生产 artifacts + 双 pro 评审(pro2 为主、pro1 为辅)+ 本地生产环境独立验证。本文件取代此前所有关于 v23 结论的非 typed 表述;ledger 归档行已同步修订。

---

## 1. 本地验证记录(本轮新做,全部在生产环境复算)

| # | 论断 | 验证结果 |
|---|---|---|
| V1 | 0/768 分类失败原因分布 | ✅ 755 `UNCLASSIFIED_NO_ATLAS_MATCH` + 13 `UNCLASSIFIED_NO_TRACE`(`V23_STRATIFIED_EVAL.json`) |
| V2 | pro1 的单位面假设 | ✅ **实锤为 root cause**:classifier atlas(`door_external_torque_threshold.json`)的 `hinge_damping_native=2864.789` = 50×57.2958(180/π);`hinge_stiffness_native` 114.59/343.77/1718.87 = 2/6/30×57.2958——字段名写 `_native` 实装 degree 面(USD 角驱动惯例),与源生 rad 面数值 exact-match 必然失配 |
| V3 | pro2 的 holdout 行为分解 | ✅ 逐数吻合:D0 FULL 248 goal/250 cross、D0 RP0 249/235、D1 FULL 235/256、D1 RP0 229/236;FULL crossing-while-holding **506/512** vs RP0 **471/512** |
| V4 | release 遥测非随机缺失 | ✅ 缺失 191/1024,且强烈随策略分布:**D0 FULL 缺 85 条 vs D0 RP0 仅缺 9 条**(比 pro2 的表述更尖锐)——FULL=抓着过门、release 事件常不触发;RP0=早松手、事件几乎全记录。hinge@release 四组中位数全部在 1.604-1.606(固定 1.60 latch 主导) |
| V5 | scratch pilot 与 F1 | ✅ stage2 12/16、stable grasp 0/16、stage≥3 0/16;Branch B `OBSERVABILITY_BLOCKED`(checkpoint `env_state_dict` 缺 `staged_reset_buf/staged_reset_num_samples`) |
| V6 | effort ladder | ✅ `LADDER_INCONCLUSIVE`→40 N·m F2 冻结(final analysis P0 段);两 pro 独立复算的 clipping 尾部单调增长(1/16→7/16)与中位 progress 不变互为交叉验证,采信 |
| V7 | 摩擦 API feature detection(v24 前置) | ✅ **Branch A 可用**:IsaacSim 5.1.0 + omni.physx 107.3 bindings 含 `staticFrictionEffort`;本地 IsaacLab 0.54.4 已有 `Articulation.write_joint_friction_coefficient_to_sim(static, dynamic, viscous)`,经 `root_physx_view.set_dof_friction_properties` 支持 **per-env per-joint 张量级设置**(`articulation.py:871-945`),语义=静摩擦(静止最大阻力 effort)+动摩擦(运动中常值)+粘性项 |

## 2. v23 typed 终局(修订版,与正式报告一致)

- **H1** `V23_WARM_START_INHERITANCE_NOT_SUPPORTED` —— **范围收窄**:F1 后 init 轴是 warm vs head-reset,故只否定了 **output-head-only 继承**;深层 recurrent/visitation 继承未裁决且 v24 不重开该轴(接受 pro1 修订)。
- **H2** `INCONCLUSIVE` —— D0 RP0−FULL 跨 seed 变号,G2-s0 pooled −5 超 3 门 margin。我保留一条本地判断:G2-s0 的 −5 与其自身 holdout(+1)和 seed1(+1)矛盾,更像单次训练偏弱;goal 层替代性是**强提示**,但正式结论就是 inconclusive,不再写"平价"。
- **H3/H5** `UNADJUDICATED` —— root cause 已定位(V2 单位面 bug),v24 P0 用统一单位契约做 **DESCRIPTIVE posthoc**;不得追溯升级为因果 pass(接受双 pro 的预注册纪律)。
- **H4** `V23_E2_BOUNDARY_NOT_ESTABLISHED` + `V23_DOOR_MODEL_INSUFFICIENT_FOR_E2` —— 干净负结果,维持。

## 3. 新 findings(本轮裁决新增,超出双 pro 已写内容)

1. **行为不平价的最强单一证据是 release 遥测缺失的策略相关结构**(V4):FULL 与 RP0 学到了两种可辨识的过门策略(hold-through vs release-early),goal 看不见,telemetry 缺失模式反而看见了。v24 必须把 "no-release-event/hold-through-crossing" 从 telemetry 缺失升格为一等行为类别。
2. **staged-reset 自举死锁**(V5 引申):snapshot bank 由策略自身到达晚期 stage 的状态在线填充——scratch 到不了 stage3,bank 永空,staged reset 结构性无法 bootstrap scratch。这才是历史 scratch 全败的机制级解释;任何未来 scratch 议程都必须先建外部 reset 数据集(DoorMan 式)。与 v24 无关(init 轴关闭),入 ledger 备查。
3. **57.3× 单位面教训升级规则 14**:分层不仅要按 realized telemetry,还必须"单一单位契约"(`DoorMechanicsUnitContractV1`),任何跨 artifact 数值比较前先归一到同一面。v22 P0-D 只验证了"请求→runtime 一致",没有验证"runtime 读回→分析面一致",这个缝隙漏过了 0/768。
4. **摩擦 Branch A 已确认可用**(V7):双 pro 最大的 `UNKNOWN` 已消除,v24 Phase 1 默认走 native 路线,proxy 降为 fallback;IsaacLab 文档同时警示 <5.0 与 ≥5.0 语义不同(load-proportional μ vs 三参数模型),v24 概率上不需要碰旧语义,但 probe 必须实测 τ_s 的单位语义(torque ramp 突破阈值 == 请求值)。

## 4. 对双 pro 的 agreement / disagreement

**接受(并已写入 ledger/v24 方案)**:三条叙事修正(RP0 平价→inconclusive+行为不平价;≤20 N·m→探针不具判别力;H1→output-head-only);posthoc=DESCRIPTIVE;连续 realized 分类+CI+OOD 拒绝(不设 ≥90% 硬 gate);λ 无量纲 load ratio 与方向性容量(J^T);干预剂量审计与 `FORWARD_PREFIX_LOCAL_CAUSAL_ESTIMATE` 降级;训练前历史 checkpoint 零样本 friction 扫描(nondiscriminative 早退);mechanics-lexicographic 选点;RQ3 四/五分支预注册;`ForceFeasibilityGateInputV1`/`ManipulationAxisSpecV1` 接口;marginal-E1 pilot 层;`V24_ARM_COMMAND_PATH_NOT_BINDING` 审计分支;DF0-sham 与 feature-disabled parity 分离;config 命名债修正(不再有 scratch 字样)。

**不完全接受 / 我的裁量**:
1. **gate 机制两 pro 冲突**(pro2:Bernoulli×Gaussian 分布正确版;pro1:先监督训练、冻结后再 PPO)。裁量:v24 走**更小的两级阶梯**——Wave 2a 用监督 gate 对冻结 FULL checkpoint 做 **eval-time 零样本包裹**(无任何 PPO 正确性问题,成本≈0);仅当 2a 显示选择性且预算允许,才做 2b = pro2 的分布正确 Bernoulli-gate PPO(2 cell)。pro1 的"冻结 gate 下继续 PPO"中间态被否决——它恰好落进 pro2 警告的 executed≠optimized 陷阱。
2. **pro2 对 G2-s0 −5 的权重**:保留"单次训练偏弱"的本地注记(见 H2),不影响 typed 结论。
3. **pro1 的 `A1_G7_seed0_step1500` warm 候选**:接受为 provisional,但最终由 P0 posthoc 的 mechanics 指标按机械规则重排后冻结(pro1 自己的规则也如此要求)。

## 5. 一句话终局

> v23 的科学贡献是三个被测量的"不存在":当前门模型不存在可表达的力边界、当前探针不存在对 arm effort 的判别力、当前成功率轴不存在对机制的区分力——加上一个被实锤的工具链单位缝隙。v24 的全部设计都从这四个"不存在"出发。
