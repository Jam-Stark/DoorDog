# a2_piper base_v24 方案 R1(2026-08-16)

代号:**Friction-Calibrated Force Boundary, Posture Final Adjudication & Coupling Groundwork**
状态:R1(取代 `a2_piper_base_v24_draft_20260816.md`;综合 pro2(主)/pro1(辅)评审与本地验证,裁量记录见 `a2_piper_v23_final_adjudication_20260816.md`)。
资源:**GPU0-3(4× A6000)**。预期终局:`V24_RESEARCH_PASS_NO_RELEASE` 家族。

## 0. 已修订的叙事前提(约束全方案用语)

1. v23 姿态结论 = `力价值 UNRESOLVED;可达性/协调作用中等支持`;不写"非必需/平价"。
2. effort 结论 = `旧探针不具判别力`;40 N·m 是 F2 fallback,不是物理最优,friction 门上重标定。
3. v23 posthoc 只产 DESCRIPTIVE 结论;H3/H5 不追溯升级。
4. H1 只关闭 output-head-only;v24 不重开 init 轴。

## 1. 研究问题(预注册)

- **RQ1** friction/breakaway 能否建立可反事实救援验证的 E1(及 held-out E2)?
- **RQ2** policy 是否按 realized load 改变行为(hold/fling、posture duty、release timing、arm saturation、foot slip)?
- **RQ3** roll/pitch 力价值终裁(四分支:`FORCE_RESOURCE_SUPPORTED / REACH_RESOURCE_ONLY / SUBSTITUTABLE_BY_PLANAR / UNRESOLVED`,另保留 `DELETERIOUS`)——任一分支都是干净结论,负结果直接成文(论文叙事两版均已备好,见 pro1 §8.5)。
- **RQ4** arm→trunk→base→leg→foot 的力耦合测量与 shadow coupling critic 监督形态(不进 PPO)。
- **RQ5** 最小 gated posture 是否选择性开启(E0 关、E1 开、mechanics 不劣)。

## 2. Phase 0 — v23 欠账清偿与冻结(零 GPU,~1 天)

1. **`DoorMechanicsUnitContractV1`**:全项目唯一单位契约(rad 面为准;USD degree 面读回必须显式换算并带 surface 标签)。57.3× bug 的修复 = 所有比较归一到同一面,禁止 exact tuple match。
2. **v23 posthoc(DESCRIPTIVE)**:连续 realized 重分层(CI+OOD 拒绝,typed 残余,无 ≥90% 硬 gate);1280 干预 episode 裁决(**剂量��计**:D_φ/D_base/D_effort,零剂量出分母;标签 `FORWARD_INTERVENTION_DESCRIPTIVE_ONLY`);posture/clearance 补算(saturation dwell/FP_φ/S_φ、**hold-through-crossing 作为一等行为类别**、release 缺失模式)。产物 `V23_POSTHOC_ANALYSIS.{json,md}`。
3. **warm-start 机械选点**:v23 FULL candidates,顺序=证据有效→零 unsafe→holdout goal→pooled→clearance→D1 覆盖→低 posture 病理→时间;provisional=`A1_G7_seed0_step1500`(48/48,63/64,D1-trained),posthoc 后重排冻结。
4. **兼容冻结**:v22/v23 checkpoint 在 `friction=off, gate=off` 下可加载、determinstic obs batch 动作一致;actor 输入/输出维度 Wave 1 不变。
5. **foot GRF feature-detect**:脚部 ContactSensor 可得则接;否则 `FOOT_FORCE_SOURCE_UNAVAILABLE`,不填零。
6. 命名债:v24 全部 config/receipt 用 `head_reset`/真实语义命名。

## 3. Phase 1 — joint friction(Branch A 已确认可用,~1-1.5 天)

- **实现**:door.py 经 IsaacLab `write_joint_friction_coefficient_to_sim(τ_s, τ_d, c_v)`(`articulation.py:871`,per-env per-joint,IsaacSim 5.1 `staticFrictionEffort` 族)接 hinge;additive + `a2_v24_*` gated,默认关。Branch B proxy(Stribeck 形式,pro1 §4.1B)仅在 probe 失败时启用并显式命名 `V24_BREAKAWAY_PROXY`。
- **单位/语义 probe(第一个测试)**:door-only torque ramp,实测突破阈值 == 请求 τ_s(容差内)→ 冻结单位语义;失败则按 <5.0 load-proportional 语义分支处理或转 proxy。
- **物理验收 A-I**(pro1 §4.3):breakaway 单调、kinetic 平台速度无关、区别于 damping、被动性(τ_f·ω≤0+容差)、无 chatter、dt 鲁棒、与 mass/damping/stiffness 正交稳定、staged-reset 往返、legacy path 复现历史。允许一次参数域收缩,二次失败 `V24_FRICTION_NUMERICALLY_UNSTABLE` 停轮。
- **随机化轴**:主=τ_s、ρ=τ_d/τ_s、c_v;副=mass/stiffness/damping/handle height(标定期固定或分层,pro2 §5.7 的 handle-height 混杂教训);先 1D τ_s 扫,再 τ_s×ρ,后稀疏正交。数值范围由 probe 定,不搬外部论文。

## 4. Phase 2 — 机器人侧容量与 E 区(~0.5 天)

- 方向性容量:g=J^T t̂,F_max,dir=min_i m_i/|g_i|,τ_avail,dir=r_handle·F_max,dir(authority=`ESTIMATE_ONLY_DIRECTIONAL_MARGIN`);λ=τ_req/(τ_avail,dir+ε) 无量纲 load ratio。
- friction 门上重跑 ladder(围绕 λ 归一选 rung),冻结 `tau_hi / tau_boundary / tau_rescue` 三 profile;全矩阵统一 tau_boundary。若降 cap 至安全下界仍不改变 load-bearing mechanics → `V24_ARM_COMMAND_PATH_NOT_BINDING`,审计 actuator/command path,不再堆小数字。
- E 区语义与 certificate(pro1 §6):E2 五条件 + **directional load-bearing clipping**(不用 any_joint_clipped)+ typed 失败排除(GEOMETRY/GRASP/DIRECTION/SLIP/PATHOLOGY);confirmed E2 只进 held-out;阈值 P0 定标后冻结。

## 5. Phase 3 — 历史零样本 friction 扫描(GO/NO-GO,~0.5 天)

v22/v23 checkpoints 零样本跑 `DF0-sham / DF1-E0 / E1-low / E1-high / E2 候选`:
- 验证 additive path 无回归(DF0-sham vs feature-disabled parity);
- 确认旧 policy 出现**连续 mechanics 退化**(breakaway latency↑、hinge work↓、saturation↑);
- 冻结 E1 范围与 DF1 mixture(curriculum 形状沿 v23,比例 P0 冻结;D1-lite 同步冻结);
- 全 friction 域无退化 → `V24_FRICTION_AXIS_NONDISCRIMINATIVE`,**停训练波,升级 owner 决策场地**(全方案唯一请示点);
- E1 存在但分母不足 → marginal-E1 pilot 层(4 cell 短程,pro1 §6.4),晋升或 `V24_E1_DENOMINATOR_INSUFFICIENT` 关闭。

## 6. Wave 1 — science factorial(GPU0-3,两串行 sub-wave,各 ~18h)

| Sub-wave | GPU0-3 | Seed |
|---|---|---|
| S0 | DF0-sham/FULL、DF0-sham/RP0、DF1/FULL、DF1/RP0 | 0 |
| S1 | 同上 | 1 |

统一 warm-start/common reward(沿 v23 冻结版)/tau_boundary/4096 env/2500 batches/save250;RP0 沿 v23 分布级 mask;per-code-path `64×10` smoke 后 launch;长 sleep 自估时长惯例沿 v23 worker prompt。
**Route A**:10 ckpt × canonical16 + realized 连续分类;选点 = mechanics-lexicographic(integrity→safety→E1 分母→high-effort hinge progress→foot slip/support→saturation→grasp retention→clearance/release→goal guardrail→time);保留全 checkpoint 曲线 + matched-step 对比(pro1 §1.8-3)。
**Route B**:pooled48 + realized 分层 + 干预套件(FULL/ACUTE_RP0/BASE0/HIGHER_EFFORT(tau_rescue)/ORACLE_ASSIST,全部带剂量审计,标 `FORWARD_PREFIX_LOCAL_CAUSAL_ESTIMATE`)+ holdout64 + confirmed-E2 held-out suite + render(reviewer 八问,pro1 §12.4)。

## 7. RQ3 终裁设计(三层证据 + 中介分离)

1. chronic FULL vs RP0(E1 stable-grasp windows 为主分析集,pregrasp/reach 单独报告);
2. acute matched posture-off(剂量≥阈值才计入);
3. planar-compensated 解释层。
Reach mediators(EE pose error/joint margin/manipulability/grasp)与 force outcomes(breakaway/hinge work/saturation/rescue/foot 力再分配)分开;判读矩阵与五个 typed 结论沿 pro1 §8.4。统计:seed-wise 方向+paired bootstrap+exact counts;margin 由 P0 噪声底冻结。

## 8. RQ4 — 耦合测量与 shadow critic

telemetry 契约(arm/base/feet/door 四组,pro1 §9;缺源 typed);事件窗(grasp/high-wrench onset/low-progress onset/intervention/release);2×2 matched forward(base neutral × arm safe-hold),Δ_cpl 向量目标(hinge work/breakaway/saturation/slip/stability/clearance);shadow critic 多头回归+sign+ranking+calibration,分层验收,不进 PPO。typed:`V24_COUPLING_SIGNAL_IDENTIFIED / NOT_IDENTIFIED / FORWARD_PROXY_ONLY / CRITIC_(UN)CALIBRATED`。

## 9. Wave 2 — gated posture(conditional,入场=E1 established)

- **2a(默认,≈0 训练成本)**:监督 gate(标签=E1 干预效用,pro1 §11.5;输入=`ForceFeasibilityGateInputV1`,允许/禁止清单沿 pro1 §11.3,任务无关)对冻结 Wave-1 FULL checkpoint 做 eval-time 包裹,测选择性与 mechanics 非劣。
- **2b(条件:2a 有选择性 + 预算)**:pro2 的 Bernoulli×Gaussian 分布正确 gate PPO,DF1 × 2 seed(GPU0-1 并行,~18h);K_gate dwell 采样,gate 正则只作 tie-breaker。
- 否决"冻结 gate 下继续 PPO"中间态(executed≠optimized)。
- typed:`V24_GATED_POSTURE_SELECTIVE / ALWAYS_ON / ALWAYS_OFF / MECHANICS_DEGRADED / INCONCLUSIVE`。

## 10. 指标与 guardrail

主轴=mechanics(方向性 margin/load-bearing clipping/high-effort hinge progress/λ/rescue/foot slip/support/work)+posture(ΔJ_φ/S_φ/FP_φ/dwell/planar 补偿/RP0 实际姿态)+行为质量(clearance/**hold-through vs QUIET_HOLD_RELEASE vs CONTROLLED_FLING vs UNSAFE_RELEASE 四分类,含 no-release-event 一等类别**/release 速度/body 距离/时间);guardrail=goal/stage/crossing/fall,以 v23 实测基线差值+CI 报告,不设普适 5pp。

## 11. 预案与停止规则

- F1 friction 数值不稳:收缩一次→仍不稳停轮 typed。
- F2 axis nondiscriminative(Phase 3):停训练,升级 owner(唯一请示点)。
- F3 E1 分母不足:marginal-E1 pilot 一次→仍不足 typed 关闭 science wave,RQ4 测量与 posthoc 仍交付。
- F4 训练崩溃:沿 v23(首更新前 1 次重启;有进展不重启,末尾补跑)。
- F5 gate 不选择性:关闭 Wave 2,不 retune 重试。
- E2 建立→只解锁 v25 body-assist 规划;E2 未建立→不阻塞 RQ3/RQ4。
- 不可越过:NaN/能量注入/摩擦符号错误/身份腐坏/staged-reset 腐坏/missing→0/E2 进训练/hidden control/事后改阈值。

## 12. 资源与日程(GPU0-3)

P0 ~1d → P1 ~1-1.5d → P2+P3 ~1d → Wave1 2×18h+RouteA(~0.5d)→ RouteB+干预+holdout+render ~1d → Wave2a ~0.5d(+2b 18h 条件性)→ 收尾 0.5d ≈ **7-9 天**。worker 惯例(长 sleep 自估、批量工具、fail-fast、无 hash 仪式、additive+config-gated、新文件进 `scriptsFORhuman/v24/`)全部沿 v23 worker prompt 与 owner 决策。

## 13. 交付物与接口

`V23_POSTHOC_ANALYSIS`、`V24_FRICTION_BACKEND_RECEIPT`、`V24_FRICTION_STABILITY_REPORT`、`V24_DOOR_REQUIREMENT_SURROGATE`、`V24_ARM_HINGE_CAPACITY_ATLAS`、`V24_E_REGION_FREEZE`、`V24_WAVE1_FINAL_ANALYSIS`、`V24_POSTURE_VALUE_ADJUDICATION`、`V24_COUPLING_DATASET_SCHEMA`+`REPORT`、`V24_GATE_PILOT_ANALYSIS`、`V24_FINAL_ANALYSIS`;跨 worktree 五 schema:`ManipulationAxisSpecV1 / ForceFeasibilityGateInputV1 / RealizedMechanicsRecordV1 / ERegionCertificateV1 / ForwardInterventionRecordV2`(不含 push/pull ID,符号 canonical 化,拉门 worktree import 复用;不承诺 gate 权重零样本迁移)。memory 新 entry + ledger 每节点同步。

## Owner D-v2 addendum (2026-08-17)

本附录由 `scriptsFORhuman/v24/DoorDog_v24_owner_decision_d_gate_revision_20260817.md` 的 `OWNER_GATE_REVISION_D_V2 + CONTINUE_FROM_P2` 明确授权，且不改写本文件此前任何字节或章节。它 supersede 了 R1 §3 中要求不可测 solver friction torque 的 literal D gate；历史 A–G、H/I receipts 与 `V24_P1_FINAL_ADJUDICATION.json` 保持 immutable。

- **Admission and typed outcomes.** Existing A/B/C/E/F/G/H/I passing facts remain valid only when read from their actual receipt schema fields. A complete D-v2 PASS yields `V24_FRICTION_MODEL_VALID_BEHAVIORAL` and admits P2/P3; a complete D-v2 scientific FAIL yields `V24_FRICTION_ENERGY_ACCOUNTING_FAIL` and admits neither. A malformed or incomplete execution raises and emits no scientific verdict.
- **Authority boundary.** D-v2 uses no solver-applied friction-torque field: `solver_friction_torque_component=UNAVAILABLE_NOT_USED`, `actual_generalized_torque_claim=false`, friction parameters and any modeled torque are `MODELED_FROM_PARAMS`, command work is `COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE`, state is `HIGH_LEVEL_ARTICULATION_DATA`, and stiffness is `CONFIGURED_HIGH_LEVEL_RAD_SURFACE_READBACK`.
- **Fresh trajectories and model.** The executable `D_V2_ENERGY` producer uses seed `24017`, `cuda:0`, signs `[-1,+1]`, 20 zero-command stationarity steps followed by an exact state rewrite, then 100 command steps at `sign*2.0 Nm` and 100 zero-command steps at `dt=0.005`. It completes both fresh F00 trajectories before freezing tolerance and before either F10 trajectory, then completes both F10 trajectories. The modeled inertia is explicit `I_model=(1/3)*120*0.95^2=36.1 kg*m^2` with authority `MODELED_FROM_PARAMS_UNIFORM_PANEL_EDGE`; no `default_inertia` is used. The high-level rad-surface configuration is stiffness `6.0 N*m/rad`, damping `0`, position target/theta_ref/theta_initial `0.5 rad`, and velocity target `0`, each required to match readback exactly.
- **Energy and tolerance rules.** For every interval the producer samples state before the command, sets a constant effort target, executes `scene.write_data_to_sim -> sim.step -> scene.update`, samples post-state, and records `dW=tau_cmd*(theta_next-theta)`, `E=.5*36.1*omega^2+.5*6*(theta-.5)^2`, `dD=dW-(E_next-E)`, with `D` initialized at zero and accumulated. All joules must be finite. The caller supplies the append-only tolerance path; `tol_step=2*noise_step+1e-12 J` and `tol_cum=2*noise_cumulative+1e-12 J` are frozen from F00 only and never recomputed from F10. F10 per-sign PASS requires finite traces, exact readbacks, signed angle motion `>=1e-4 rad`, signed velocity `>=1e-3 rad/s`, every `D>=-tol_cum`, every `dD>=-tol_step`, and `D_final>tol_cum`; overall PASS requires both signs.
- **Artifacts.** The only new evidence paths are `logs_eval/base_v24/p1/friction_backend/d_v2_energy_r1_gpu0/{D_V2_TOLERANCE_FREEZE.json,D_V2_ENERGY_RECEIPT.json}` and `logs_eval/base_v24/p1/final_adjudication/d_v2_r1/V24_P1_D_V2_FINAL_ADJUDICATION.json`; producer and adjudicator use append-only no-overwrite writers and leave all historical receipts unchanged.
