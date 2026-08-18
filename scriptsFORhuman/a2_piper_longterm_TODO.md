# A2+Piper 远期工作 TODO(跨版本长效清单)

维护规则:每轮新 plan 落成时核对本清单一次;完成/否决的条目移入文末归档区并注明依据;新远期项随发现追加。时间戳 HKT。
创建:2026-07-21;最近更新:2026-08-16(v23 收口归档;v24 friction/force-feasibility 轮排期;三 worktree 分工记录)。

## Worktree 分工(2026-08-16 起)

- **推门主 worktree(本仓库)= novelty 引擎**:force-feasibility / arm-base 力耦合联动研究主线;同时产出对"推拉门"通用的 posture / arm-base 协同能力与接口(posture command 语义、gate 机制、E-region certificate 工具链保持 task-agnostic,供拉门 worktree 复用)。
- **拉门 worktree(并行)**:in/out 拉门任务稳定路线探索(原 C.4 场地;lr 镜像工程随之移交)。
- **蒸馏 worktree(并行)**:student distillation 稳定路线探索(teacher 在推门任务已到天花板,原 D 表入场条件实质满足)。
- GPU lease 是外部动态调度事实,worktree 间分配以用户当轮指令为准,不写 durable memory。

---

## A. 已排期(进行中的 round)

| 条目 | 排期 | 出处 |
|---|---|---|
| **v24 P0:v23 分析层欠账清偿(零 GPU)**——修 realized-dynamics 分类器(v23 为 0/768 unclassified)、裁决 1280 个 forward-intervention episodes(ΔJ_φ)、从 step trace 计算各 cell posture saturation dwell / FP_φ / S_φ 与 clearance×posture 预注册分析,把 H1 行为版 / H3 / H5 真正关闭;同时按机械规则选出 v24 warm-start | **v24 前置,先于任何训练** | v23 final analysis:H3/H5 `INCONCLUSIVE_REALIZED_DYNAMICS_UNCLASSIFIED`、干预裁决 `PENDING` |
| **v24 P1:LT-23-02 hinge friction retrofit(晋升为 v24 主线)**——PhysX joint friction(Coulomb 常阻力矩)+ breakaway 语义接入 door.py per-env randomization;physics 探针验证准静态阻力、单调响应与数值稳定;重建 atlas / effort ladder / E0-E2 certificate | **v24 主线** | v23 `V23_DOOR_MODEL_INSUFFICIENT_FOR_E2`(drive 模型 damping/stiffness/max_force≤24 表达不了力边界);joint friction 机制 PhysX/IsaacLab 已有(robot 侧 `dof_joint_friction_list` 即是),door hinge 只差 plumbing |
| LT-23-12 源码版本隔离重构 + 根目录垃圾清理(用户自查清单已有) | v24/v25 轮间窗口 | v23 owner 决策:mid-round 禁清理 |

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
9. **[叙事修正] 论文主张按 v23/v22 证据定位**:"minimal base intervention" 的力通道主角候选是 bracing(body-assist)与 planar 站位;roll/pitch 在当前几何是可达性资源(v22 atlas:抓稳后 neutral 方向性容量近最优)——机制设计与实验叙事据此定位,不把 posture 硬写成力资源。

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
- [x] 2026-08-16:**v23 收口(`V23_RESEARCH_PASS_NO_RELEASE`,三重负结果高信息量)**——16/16 cell rc0;H1 继承不支持(head-reset 250 步复满分,goal 差全在噪声);**RP0 全面平价**(8 RP0 cell ≈ 8 FULL cell,D0 与 D1 皆是,chronic 禁姿态零代价)→ 0.4 pitch 降级为"免费动作"非问题;H4 `E2_BOUNDARY_NOT_ESTABLISHED` + `DOOR_MODEL_INSUFFICIENT`(atlas confirmed_E2=0);effort ladder 100→20 零样本无退化(`LADDER_INCONCLUSIVE`,冻结 40)→ 指令侧饱和是 Kp 增益伪影,任务执行力矩需求 ≤20 N·m。H2/H3/H5 因分析层欠账 typed inconclusive(数据在盘,v24 P0 清偿)。沉淀规则:**规则 13**(成功率天花板下 success-rate 轴对变体无区分力,测量轴必须换行为质量/力学量);**规则 14**(E 区/桶分层必须按 realized dynamics telemetry,intended bucket 只作抽样器——v22 bucket MISMATCH 与 v23 0/768 同源);**规则 15**(reducer/gate 只准执行已授权判据;acute 探针标签是 policy-relative 的,不得当门属性用)。
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
