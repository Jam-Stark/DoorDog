# A2+Piper 远期工作 TODO(跨版本长效清单)

维护规则:每轮新 plan 落成时核对本清单一次;完成/否决的条目移入文末归档区并注明依据;新远期项随发现追加。时间戳 HKT。
创建:2026-07-21;最近更新:2026-08-01(v20 因变量读出关闭)。

---

## A. 已排期(进行中的 round)

| 条目 | 排期 | 出处 |
|---|---|---|
| 真实 Piper arm 限位轮(force_feasible 边界前置)**+ θ_send 统一 rider**:corridor-latch 的 `hinge≥1.0` 分支、send-curriculum 目标、crossing gate 合并为单一 θ_send≈1.25–1.30。预注册预测:crossing p50 追随 θ_send(v20 全部 send cell 钉在 1.00–1.02 = 该分支即下一 pay boundary,阈值贴靠第 5 例);盯 heavy-tail stage_overtime(160kg/11.5N·m case 已现:送门耗时,时间预算而非力是重门边际约束) | **下一轮** | v20 收口读出(SEND_METRICS):send curriculum 为唯一有效成分(G3 +0.207;G2 经济学单独 +0.026 无效;arm-tie 无增量;G6/G7 复制,seed 差 −0.018) |
| 若宣布正式 release:补 Route B(pooled48/holdout64/final analysis)——G4@2500 目前仅 Route A 证据(goal 15/16) | release 决策时 | v20 Route B 未跑 |

## B. 下一批候选(v17)

| 条目 | 前置/触发 | 出处与要点 |
|---|---|---|
| **真实 Piper 限位改造(arm 关节侧,方向:调弱到真实规格)** | v18 候选(gripper 侧已在 v17 M36 先行) | v15 诊断:sim 手臂 effort ~100N 级"超人"是 force-feasible 底座前置;改造后重跑弹簧/mass 分桶确认 arm 饱和为真 |
| **door_open_lr 左右镜像** | 行为塑形轮(v16)结束后 | v14/v15 plan round3 原定;memory `door-asset-randomization-baseline` 已预分析 plumbing(handle-relative 可镜像);先 GUI/smoke 验左侧 workspace |
| 弹簧上限 >12 N·m | **仅在真实限位改造之后**(否则死轴) | v15 plan §1.5;v15 实测 12 N·m 内 arm-through-handle 全覆盖 |

## C. Research 主线路线图(force-feasibility-aware policy)

依据:`scriptsFORhuman/force_feasible/` 三份讨论(方向:力可行域内偏好 arm 余量大/base 干预小的构型;`u_base = u_user + gate(s)·u_assist`;主任务 + tie-breaker 分层)。

1. **[v16] tie-breaker 哲学落地**:M29 姿态经济 = "最小 base 干预"第一实例;v15 的 80% 饱和为 baseline 对照数据。
2. **[v17] 实验底座为真**:真实 Piper 限位(B 表第一项)→ arm 饱和可测 → feasibility 信号有物理意义。
3. **[v17/v18] gate/base-assist 机制入场**:在真实限位 + 强弹簧/重门桶上实现 gate(s) 与 arm-margin reward;判读 = gate 只在饱和桶打开(v15 教训:无载荷 regime 学 gate 是噪声)。
4. **[v18+] 拉门(in/out)新任务**:摩擦/钩传力、手指 10N effort 硬上限 → 天然 finger-limited regime,force-feasible 的第二实验场。工程边界见 memory `door-asset-randomization-baseline` in/out 决策(出生侧镜像、staging 符号、穿行方向、doorOpenIO 进 obs——是新任务不是开关)。
5. 论文实验设计:baseline(无 tie-breaker)vs 本方法,指标 = force tracking 达标下的 arm 饱和时间/base 位移/`v_user` 违背(force_feasible 文档已列)。

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

## 归档(已完成/已否决)

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

更新时间:2026-08-10 HKT。以下 LT-23-01..12 是 v23 之后的 long-term
scope，**当前均未在 v23 core 实现**；本节不是完成项，也不改变上面的历史
条目。

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
12. **LT-23-12 active anti-rebound gripper bracing/re-contact**：研究并验证
    gripper 在门回弹阶段的主动 bracing/re-contact 策略；保持为 post-v23
    long-term 项，未进入 v23 core。
