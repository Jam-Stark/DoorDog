# A2+Piper 远期工作 TODO(跨版本长效清单)

维护规则:每轮新 plan 落成时核对本清单一次;完成/否决的条目移入文末归档区并注明依据;新远期项随发现追加。时间戳 HKT。
创建:2026-07-21;最近更新:2026-08-18(v24 收口归档与 owner insight 补充;规则 16-18 入册;下一轮场地决策待 owner)。

## Worktree 分工(2026-08-16 起)

- **推门主 worktree(本仓库)= novelty 引擎**:force-feasibility / arm-base 力耦合联动研究主线;同时产出对"推拉门"通用的 posture / arm-base 协同能力与接口(posture command 语义、gate 机制、E-region certificate 工具链保持 task-agnostic,供拉门 worktree 复用)。
- **拉门 worktree(并行)**:in/out 拉门任务稳定路线探索(原 C.4 场地;lr 镜像工程随之移交)。
- **蒸馏 worktree(并行)**:student distillation 稳定路线探索(teacher 在推门任务已到天花板,原 D 表入场条件实质满足)。
- GPU lease 是外部动态调度事实,worktree 间分配以用户当轮指令为准,不写 durable memory。

---

## A. 已排期(进行中的 round)

| 条目 | 排期 | 出处 |
|---|---|---|
| **下一轮场地决策(owner)**:force-feasibility 主线迁移拉门 worktree(A,推荐)/ 既有 F3′ checkpoints 上的 RQ3 measurement-only 池化大 N 评估(B,轻量,需新 scope 注册)/ v25-push E1 密度导向设计(C)。v24 已交付可迁移资产:friction Branch A 基建(per-env τ_s/τ_d/c_v)、行为 E 区分类器、certificate/gate 工具链、五个跨 worktree schema | **待 owner 决策** | v24 收口(2026-08-18) |
| LT-23-12 源码版本隔离重构 + 根目录垃圾清理(用户自查清单已有) | 轮间窗口 | v23 owner 决策:mid-round 禁清理 |

## B. 下一批候选(状态更新 2026-08-16)

| 条目 | 前置/触发 | 出处与要点 |
|---|---|---|
| ~~真实 Piper 限位改造(调弱到真实规格)~~ **已被 v23 supersede**:effort ladder 100→20 N·m 零样本全无退化(`LADDER_INCONCLUSIVE`,矩阵冻结 40)——sim 内 arm 力矩不是约束;实机规格标定保留为 LT-23-01 | 已收口 | v23 F2 receipt |
| **door_open_lr 左右镜像** | **移交拉门 worktree**(in/out 任务自带出生侧镜像工程) | memory `door-asset-randomization-baseline` |
| ~~弹簧上限 >12 N·m~~ **已被 v22/v23 否决**:25/30 N·m 探针 below resolution,spring/drive 轴死亡;阻力轴改走 joint friction(A 表 v24 P1) | 已收口 | v22 `higher_torque_probe` + v23 H4 |

## C. Research 主线路线图(force-feasibility-aware policy)

依据:`scriptsFORhuman/force_feasible/` 三份讨论(方向:力可行域内偏好 arm 余量大/base 干预小的构型;`u_base = u_user + gate(s)·u_assist`;主任务 + tie-breaker 分层)。

1. **[v16] tie-breaker 哲学落地**:M29 姿态经济 = "最小 base 干预"第一实例;v15 的 80% 饱和为 baseline 对照数据。
2. **[v17] 实验底座为真**:真实 Piper 限位(B 表第一项)→ arm 饱和可测 → feasibility 信号有物理意义。
3. **[v17/v18] gate/base-assist 机制入场**:在真实限位 + 强弹簧/重门桶上实现 gate(s) 与 arm-margin reward;判读 = gate 只在饱和桶打开(v15 教训:无载荷 regime 学 gate 是噪声)。
4. **[v18+] 拉门(in/out)新任务**:摩擦/钩传力、手指 10N effort 硬上限 → 天然 finger-limited regime,force-feasible 的第二实验场。工程边界见 memory `door-asset-randomization-baseline` in/out 决策(出生侧镜像、staging 符号、穿行方向、doorOpenIO 进 obs——是新任务不是开关)。
5. 论文实验设计:baseline(无 tie-breaker)vs 本方法,指标 = force tracking 达标下的 arm 饱和时间/base 位移/`v_user` 违背(force_feasible 文档已列)。
6. **[v23 校准] C.2/C.3 证据更新**:v23 证明 sim 内 arm effort 不是约束(20 N·m 零样本无退化)、drive 门模型表达不了力边界、chronic RP0 与 FULL 全面平价——"实验底座为真"的缺口在门侧摩擦(LT-23-02/v24 P1),不在 arm 限位;gate 机制(C.3/LT-23-08)入场条件改为"friction 门上 E1 certificate 成立"。
7. **[v24+ novelty] arm-base 力耦合测量与建模**:高 arm wrench 下的足底反力 / frozen locomotion 抗滑耦合从未被进入过(v23 rescue latch 仅 52/256 触发)。friction 门建立力负载后先做测量级研究(反作用力路径、姿态-足底力分布、locomotion 补偿行为),再决定 coupling critic(LT-23-06/07)的监督数据形态;1280 个 forward-intervention episode 的基础设施已在 v23 建成。
8. **[跨 worktree novelty] push↔pull 通用 posture/协同接口**:posture command 语义、gate 输入(force/progress/margin history,不含任务特有量)、E-region certificate 工具链保持 task-agnostic;推门 worktree 产出的 gate/coupling 机制以"拉门 worktree 可直接复用"为验收条件之一。
9. **[叙事定位,2026-08-16 晚修订] 论文主张按证据等级表述**:"roll/pitch 的可达性/协调作用"有中等证据(v22 P0-B acute 37/40 + atlas);"roll/pitch 的力价值"为 `UNRESOLVED`,由 v24 RQ3 在 friction-calibrated E1 上做终裁(四分支预注册,负结果同样成文)。"minimal base intervention" 的力通道候选主角是 bracing(body-assist)与 planar 站位——作为工作假设而非已证结论。

## D. 停车场(有明确入场条件,暂不排期)

| 条目 | 入场条件 | 出处 |
|---|---|---|
| student distillation(Phase2 vision policy) | teacher 行为定稿(预计 v17 后) | memory `phase2-student-distillation-a2-piper` |
| multi-seed 重训 basin 验证(≥2 seed 全程重训) | 大版本行为定稿时 | v13.1 决策树遗留;历史上 scratch 3/4 落错 basin |
| latch/handle 几何进一步 randomization(hook 概率、handle 长径、latch 行程) | lr 镜像之后 | v13 §2.5、门生成器已有参数 |
| privileged obs 加门动力学参数(输入层扩展手术保 warm-start) | 仅当分桶显示策略对门参数自适应失败 | v14 plan M20.4(v14/v15 均未触发) |
| Phase3 student bootstrapping / GRPO | distillation 之后 | memory `phase3-student-bootstrapping` |

## E. 维护性挂账(小,勿丢)

- [ ] formal launcher natural-exit 复核习惯化(v13.1 起多轮 NOT RECORDED);
- [ ] git push(截至 v15 交付 push_status=NOT PUSHED);
- [ ] j8 开限位长期观察项(v15 ~11%,健康;真实限位改造后重新定基线);
- [ ] `temp_delete.diff` / 历史 untracked 清理(用户自查);
- [ ] eval 汇报:strict_trace_topology FAIL 时(缺 env trace)在报告中给出缺失原因归类(v15 step500/1000/2000 曾出现)。
- [ ] 若未来宣布任何正式 release:v20 G4@2500 仅有 Route A 证据,Route B(pooled48/holdout64/final analysis)未跑(2026-08-16 自 A 表降级挂账);
- [ ] v23 保留物 POST-v23 复核:F8 失败尝试日志、78 个非 episode0 render 额外媒体、6 个已撤销 GPU 兼容 diff 的记录(轮间窗口与 LT-23-12 一并处理)。

## 归档(已完成/已否决)

- [x] 2026-08-18:**规则 16（measurement-vitals admission）**——任何 calibration/eval population 必须先用同一 checkpoint 在 easy/sham cell 复现已知基线体征；只有体征 PASS 后，派生 denominator、partition 与 typed terminal 才可解释。零分母不是自动的“分母不足”，且零分母终局必须附体征 PASS。该规则由 base_v24 P2 r10 的 0/288 grasp 仪器特征触发，并由 r12 sham 16/16 与 post-F3 64/64 source-vitals-valid population 完成闭环。
- [x] 2026-08-18:**规则 17（参数域量级锚）**——任何 parameter-domain freeze 必须携带仓库内已验证证据的 magnitude anchor，并明确锚只校准量级、不自动声明物理等价。base_v24 r13 以 v22 可解 `24 N·m` drive-resistance face 为量级锚，将 friction `tau_s` 从 null 域 `[0,1]` 升至稳定的 `{2,5,10,20} N·m`，P1-lite 四档 breakaway literal containment 全过。
- [x] 2026-08-18:**规则 18（派生量 gate 有效性）**——gate 若依赖 derived quantity 的单调性/可识别性，必须先证明该假设；未证明或被行为自适应混杂时，该量只能 report-only。base_v24 r13 的 modeled `tau_req=I*theta_ddot+c*omega+k*theta+tau_f` 因 policy 随摩擦升高而减速，只得到 matched strict `47/96`，而物理 breakaway 与行为 progress 梯度均强通过；该预测子因此降级为 `MODELED_TAU_MATCHED_ORDERING_CONFOUNDED_BY_SPEED_ADAPTATION`。
- [x] 2026-08-18:**base_v24 最终收口 (`V24_E1_DENOMINATOR_INSUFFICIENT_FINAL`)**——Owner 裁决 friction 轴为 `V24_FRICTION_AXIS_DISCRIMINATIVE_BEHAVIORAL`；行为 E 区冻结 `delta=[0.02,0.04] rad`、clip/util floors `0.40/0.50`、ladder `40/20/25 N·m`。F3-prime 四个 `4096×500` cell 全 exit0，四 checkpoint Rule16 sham 均 16/16；P10/cap20 各 32 episode 的 sustained-E1 为 `4/1/8/4`，三 cell 低于注册 `8`，故合法终局且禁止再修 gate。P3/Wave1/Route/RQ3/Wave2 不准入；friction 轴非 null，RQ3 posture force value 保持 `UNRESOLVED_NOT_ADMITTED`。
- [x] 2026-08-18:**base_v24 owner 终裁补充(insight 层,配套上一行)**——(1) **E1-per-cell 准入 gate 与被检假设混杂**:同一批 P10/cap20 边界门上,FULL cells 的 E0 计数 20/23(of 32)vs RP0 cells 仅 5/12,RP0 的 E1+near-E2 与 unclassified 均约两倍——若 posture 真有助于处理边界负载,FULL 就*应该* E1 稀少;对称的 ≥8/cell 要求在结构上惩罚"假设为真"。**未来 E 区准入必须锚定在门/场景侧(policy-free)或以 RP0 侧为密度参照,不得对全部 policy cell 施加对称密度要求**(规则 18 的姊妹教训)。该 E0 不对称本身是 RQ3 方向性的初步描述证据(混杂:RP0 仅 500-batch 适应 + unclassified 不对称,不升级为因果)。(2) **容量估计器退化为 RQ4 finding**:min-over-joints 方向性余量在 358/384 加载窗口塌缩而门照常打开(`CAPACITY_ESTIMATOR_LOWER_BOUND_DEGENERATE`)——"arm 在名义方向性容量之外靠什么完成开门"是耦合研究的直接素材;RQ4 measurement-only 收口 `V24_COUPLING_FORWARD_PROXY_ONLY` + `V24_COUPLING_CRITIC_UNCALIBRATED`(32 FULL-RP0 配对)。(3) 可迁移资产:friction Branch A 基建、行为 E 区分类器、certificate/ladder 工具链、五 schema——对 in/out 门即插即用;场地决策见 A 表。
- [x] 2026-08-16:**v23 收口(`V23_RESEARCH_PASS_NO_RELEASE`,负结果高信息量;本行 2026-08-16 晚经双 pro 评审与本地复核修订,取代同日早版过强表述)**——16/16 cell rc0。typed 终局:H1 `INHERITANCE_NOT_SUPPORTED`(**仅收窄到 output-head-only**:F1 用 head-reset 替代了真 scratch,深层 recurrent/visitation 继承未裁决);H2 `INCONCLUSIVE`(D0 RP0−FULL 跨 seed 变号,G2-s0 pooled −5 超 margin;goal 层替代性强烈提示但未过预注册门槛);H3/H5 `UNADJUDICATED`(realized 分类 0/768:**已实锤 root cause = 单位面 bug**,classifier atlas 的 `*_native` 字段实为 degree 面数值,=源生值×57.2958(180/π),755/768 因此 NO_ATLAS_MATCH);H4 `E2_NOT_ESTABLISHED`+`DOOR_MODEL_INSUFFICIENT`(atlas confirmed_E2=0)。**行为层不平价**(holdout 复算):FULL crossing-while-holding 506/512 vs RP0 471/512;release 记录缺失 191/1024 且强烈随策略分布(D0 FULL 缺 85 vs D0 RP0 缺 9 = FULL 抓着过门不触发 release 事件);hinge@release 全部聚在 1.60 latch(release 行为由固定阈值经济主导,非自主选择)。effort ladder:`LADDER_INCONCLUSIVE`→冻结 40 N·m;**正确表述为"被选 stable-grasp 短窗 progress 探针对 20-100 N·m 不具判别力"(clipping 尾部随 cap 降低单调增长 1/16→7/16 而中位 progress 不变),不是"任务力矩需求≤20 N·m"**。scratch pilot:stage2 12/16、stable grasp 0/16;Branch B `OBSERVABILITY_BLOCKED`(checkpoint 不含 `staged_reset_buf`)——且 staged-reset bank 为策略自举填充,scratch 到不了晚期 stage 则 bank 永空,**结构性无法 bootstrap scratch**。沉淀规则:**规则 13**(成功率天花板下 success-rate 轴无区分力,测量轴换力学量/行为质量);**规则 14**(分层按 realized telemetry 且必须单位面统一,intended bucket 只作抽样器);**规则 15**(reducer/gate 只准执行已授权判据;acute 探针标签 policy-relative,不得当门属性)。姿态定位:**可达性/协调作用中等证据支持;力价值 `UNRESOLVED`,由 v24 RQ3 在 friction-calibrated E1 上终裁**。posthoc 修复只能产出 DESCRIPTIVE 结论,不得追溯升级 H3/H5 为因果 pass。
- [x] 2026-08-16:v20 遗留 A 表两行处置——"真实 arm 限位轮 + θ_send rider"被 v21B(theta ladder DV1 未达带)与 v23(effort ladder null)合并 supersede;"release 时补 v20 Route B"降级入 E 挂账。
- [x] 2026-08-08(补录):**v22 收口(NO_RELEASE)**——labels `RESEARCH_PASS / RANDOMIZATION_BOUNDARY_IDENTIFIED / POSTURE_CONDITIONALLY_USEFUL / BODY_ASSIST_UNSAFE / HOLD_OPEN_DOMINANT`;三候选 pooled goal 46-47/48 但 clearance 29/9/16 of 48;H3/H4 hinge 类 unrealized(25/30 N·m below resolution);posture gate `REPORT_ONLY_INSUFFICIENT_DENOMINATOR`;P0-B 独立标签 37/40 POSTURE_NEEDED(acute)。
- [x] 2026-08-04(补录):**v21B 收口(`COMPLETED_SCIENTIFIC_NO_RELEASE`)**——R10 census right-censored(heavy 门 raw PD 需求 62.5% ≥100 N·m)→ ARM_REALISTIC 未获训练,F3 回退 ARM_V20 + theta ladder;torque authority `ESTIMATE_ONLY`;Route-B pooled48 科学判定 FAIL,candidate set 空。
- [x] 2026-08-01:**v19 收口(负结果,高信息量)**——70 ckpt/55 valid 中 hinge_at_crossing_p50 上限 0.7869、0/55 ≥0.9;release ceiling 提高被"base-drag"满足(root_x@release p50 0.686)。云端 pro 模型诊断获背书并沉淀两条设计规则:**规则 11**(行为要求写在正确的物理事件上——三轮都约束了 at-release/at-stage-flip,用户要的是 at-crossing)、**规则 12**(round 汇总表必须含本 round 因变量)。
- [x] 2026-08-01 19:06 HKT:**v20 Route-A 因变量读出关闭**——70/70 checkpoint、1120/1120 records/traces、740908 trace rows strict-valid，fallback eval 0。约束 goal≥15/16 下 winner 为 G4 step2500：hinge_at_crossing p50/p95=`1.0160/1.0628rad`、root_x_at_release p50/p95=`0.4717/0.6680m`、held_hinge_max p50/p95=`1.2911/1.3617rad`，相对 v19 `+0.2291rad`，预注册标签 `PARTIAL_EFFECT`。winner 5 episodes×3 cameras=15 MP4 full decode，crossing 前目视门已宽开 `YES_5_OF_5`；160kg/11.4905N·m case crossing 前 hinge=`0.9999rad`。因此“无 cell 移动”制度化 fallback 未触发；Route B strict DAG/pooled48/holdout64/final analysis 保持 NOT RUN。
- [x] 2026-08-01:v20 R2/R3 完成训练(7 组×10 ckpt)与 Route A eval(1120 records,任务健康保持);其后因变量读出与 winner render 已由上一条关闭。

- [x] 2026-07-20:M18 静态可达性图路线否决——能力探针必须匹配可指令自由度,策略本体是最高保真仪器(见 m23_conclusion.md §3)。
- [x] 2026-07-21:"重门 body-assist 涌现"假说否决(推门=形封闭,12 N·m 内 arm 全覆盖;过线前 body 接触 0/10066)——force-feasible 机制改走 C 表路线。
- [x] 2026-07-21:round2(弹簧/高度/站位带)完成于 v15,47/48;round1(回弹动力学+站位自学)完成于 v14。
- [x] 2026-07-22:mass 轴 80–160 完成于 v16(全桶 100% goal,B ckpt2000 为 release);v16 三项行为 shaping 全败并诊断同根(定标未按实测决算 + stage 边界收益断层),重做于 v17 M34/M35。
- [x] 2026-07-22:设计规则第三例沉淀——"stage 边界收益断层":凡跨 stage 的行为目标,其收益项作用域必须覆盖边界两侧,否则策略在边界处理性弃行为(v13 门挡房租、v15 gate 死区、v16 送门无薪同族)。
- [x] 2026-07-24:**push-wide-then-release 于 v17 解决**——6-cell factorial 干净归因:制度(阈值 1.35/1.25)与计价(事件制)均必要、合用充分且可复制(G6);release=G5 ckpt2500,48/48 全桶,松手后接触 47/48→1/48。M36 gain probe PASS(15/16 零样本)→ v18 采纳。posture 经济第二次失败(λ×10 付 12% 收入仍 98-100% 使用)→ 价格弹性假说否决,转 P2 判别探针;scratch 重训仅在"习惯性"判定后立项。

## [POST-v23 — DO NOT IMPLEMENT IN V23 CORE]

更新时间:2026-08-10 HKT。以下 LT-23-01..13 是 v23 之后的 long-term
scope，**当前均未在 v23 core 实现**；本节不是完成项，也不改变上面的历史
条目。

状态更新 2026-08-16:**LT-23-02 已晋升为 v24 主线**(见 A 表);LT-23-12 排入 v24/v25 轮间窗口;LT-23-06 shadow 版随 v24 Wave 2 视 friction E1 certificate 结果入场;LT-23-10 维持 E2 certificate 前置(v24 P1 若建立 E2 即解锁);其余维持 long-term。

1. **LT-23-01 真实 PiPER capability calibration**：测量各关节连续/峰值
   扭矩、torque-speed curve、current/thermal limit、实机静态与持续推力，
   修正 URDF effort，并校准 Kp、action scale、effort clipping；验收为仿真
   torque utilization 与实机电流/负载趋势对齐。
2. **LT-23-02 真实 hinge friction model**：独立实现并随机化 Coulomb
   friction、stiction、breakaway torque、velocity-dependent friction、
   hysteresis 与 latch release discontinuity；不得用 damping 代替静摩擦。
3. **LT-23-03 Dynamics oracle 与 system identification**：critic/oracle
   使用 `[m,I,c,k,tau_max,tau_breakaway,mu,tau_arm_limit]`，actor 使用
   history-estimated latent；对照 critic-only privilege、oracle actor upper
   bound、history-estimator actor。
4. **LT-23-04 三分支 factorized actor**：shared recurrent trunk 下分出
   navigation(vx/vy/yaw)、posture(roll/pitch)、manipulation(arm+gripper)
   heads，并分别保存 log_prob、ratio、KL、entropy、clipfrac、advantage。
5. **LT-23-05 Matched intervention runner**：支持 exact simulator state
   clone、recurrent history clone、common random numbers、control-step
   horizon、safe neutral posture、safe neutral arm hold 与 four-branch rollout。
6. **LT-23-06 Intervention-supervised coupling critic**：实现
   `Q_C(z,a_nav,a_posture,a_arm)`，监督 posture-arm、nav-arm interaction，
   必要时加入 triplet residual。
7. **LT-23-07 Counterfactual branch PPO**：为 navigation、posture、arm
   分别生成 counterfactual advantage；禁止 joint ratio 乘 branch-specific
   advantage。
8. **LT-23-08 Learned sparse posture gate**：实现 `a_phi=g_t Δphi_t`，gate
   由 dynamics/history/coupling value 决定；E0 自动关闭、E1 适度开启、E2
   输出低-confidence 或 body-assist request，不用目标高度硬编码标签。
9. **LT-23-09 Handoff/downstream critic**：预测 stage 结束状态对后续完整
   成功的价值，覆盖 stage farming、bad transition、提前 release、门开但无法
   穿过，以及不适合下一阶段的 grasp/arm margin。
10. **LT-23-10 Body-assist curriculum**：仅在 E2 certificate 建立后实施，
    包括 trunk/front-thigh candidate contacts、safe contact-region mask、
    contact force/velocity limits、strict force-failure gate、ordinary-door
    negative curriculum 与 arm+posture rescue 对照。
11. **LT-23-11 Student dynamics/coupling distillation**：student 不接收
    door mass/damping ground truth，而从 RGB、proprioception、force/history、
    hinge visual motion 学习 teacher 的 dynamics latent、posture mode、
    release/hold strategy。
12. **LT-23-12 源码版本隔离重构**：将 `door_open_a2_base.py` 按版本抽出
    evidence/gate 模块并保留固定 hook 面；全部历史 checkpoint 必须可加载、
    可复评。测试、runner、launcher 按版本归入 `scriptsFORhuman/vNN/`，此后
    每个版本只允许 additive、config-gated 接入。
13. **LT-23-13 active anti-rebound gripper bracing/re-contact**：研究并验证
    gripper 在门回弹阶段的主动 bracing/re-contact 策略；保持为 post-v23
    long-term 项，未进入 v23 core。
