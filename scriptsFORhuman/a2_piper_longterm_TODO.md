# A2+Piper 远期工作 TODO(跨版本长效清单)

维护规则:每轮新 plan 落成时核对本清单一次;完成/否决的条目移入文末归档区并注明依据;新远期项随发现追加。时间戳 HKT。
创建:2026-07-21;最近更新:2026-08-11 00:03 HKT (pull-v3 release-then-cross G2 closure)。

---

## A. 已排期(进行中的 round)

| 条目 | 排期 | 出处 |
|---|---|---|
| 真实 Piper arm 限位轮(force_feasible 边界前置)**+ θ_send 统一 rider**:corridor-latch 的 `hinge≥1.0` 分支、send-curriculum 目标、crossing gate 合并为单一 θ_send≈1.25–1.30。预注册预测:crossing p50 追随 θ_send(v20 全部 send cell 钉在 1.00–1.02 = 该分支即下一 pay boundary,阈值贴靠第 5 例);盯 heavy-tail stage_overtime(160kg/11.5N·m case 已现:送门耗时,时间预算而非力是重门边际约束) | **下一轮** | v20 收口读出(SEND_METRICS):send curriculum 为唯一有效成分(G3 +0.207;G2 经济学单独 +0.026 无效;arm-tie 无增量;G6/G7 复制,seed 差 −0.018) |
| pull-v4 frame-neighborhood/path-distribution 候选:从 v3 已观测的 release+−X motion 继续解决 frame-approach=0；保留 v3 through-frame 谓词、release mask、corridor scales 与六项 invariant，先预登记 frame 邻域收入/路径设计，不回改 v3 scale | **下一轮候选** | pull-v3 G2(c):六格 E6/E7/complete 全零；早期格 release 与 −X motion 同现，但 frame-approach/passage/detour 全零 |
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

- [x] 2026-08-11 00:03 HKT:**pull-v3 release-then-cross 收口(G2 科学负结果)**——C1–C7、D0-lite、64×50 smoke、双 seed 256×750 Wave1 与六个 16-episode checkpoint eval 均完成；Stage4 admission=`16/15/15,16/16/16`，六项 invariant 全零，但 E6/E7/complete 每格均为 `0/16`。早期 checkpoint 发生 deliberate release+−X motion，frame-approach/passage/detour 仍全零，故不跑 Wave2/seed2且不改 scale；G10 因 post-release recontact max `18` 触发，仅勾稽 pull 线 arm-brace 期货。
- [x] 2026-08-10 09:32 HKT:**pull-v2 wall-removal / unlatch calibration 收口**——canonical U-probe `theta*=0.6rad`、latch threshold=`0.02292371541261673`；唯一 reward 改动 `near_closed 0.1→0.25` 后，Wave1 两 seed 触发 G1，Wave2 六格 true Stage4=`13/16,14/16,15/16,11/16,16/16,16/16`，四项 invariant 全零。原 pull-v1 force-transfer/seed-sensitivity attribution 已由该单轴实验闭合；下一 scope 转 traversal/V1-C。
- [x] 2026-08-01:**v19 收口(负结果,高信息量)**——70 ckpt/55 valid 中 hinge_at_crossing_p50 上限 0.7869、0/55 ≥0.9;release ceiling 提高被"base-drag"满足(root_x@release p50 0.686)。云端 pro 模型诊断获背书并沉淀两条设计规则:**规则 11**(行为要求写在正确的物理事件上——三轮都约束了 at-release/at-stage-flip,用户要的是 at-crossing)、**规则 12**(round 汇总表必须含本 round 因变量)。
- [x] 2026-08-01 19:06 HKT:**v20 Route-A 因变量读出关闭**——70/70 checkpoint、1120/1120 records/traces、740908 trace rows strict-valid，fallback eval 0。约束 goal≥15/16 下 winner 为 G4 step2500：hinge_at_crossing p50/p95=`1.0160/1.0628rad`、root_x_at_release p50/p95=`0.4717/0.6680m`、held_hinge_max p50/p95=`1.2911/1.3617rad`，相对 v19 `+0.2291rad`，预注册标签 `PARTIAL_EFFECT`。winner 5 episodes×3 cameras=15 MP4 full decode，crossing 前目视门已宽开 `YES_5_OF_5`；160kg/11.4905N·m case crossing 前 hinge=`0.9999rad`。因此“无 cell 移动”制度化 fallback 未触发；Route B strict DAG/pooled48/holdout64/final analysis 保持 NOT RUN。
- [x] 2026-08-01:v20 R2/R3 完成训练(7 组×10 ckpt)与 Route A eval(1120 records,任务健康保持);其后因变量读出与 winner render 已由上一条关闭。

- [x] 2026-07-20:M18 静态可达性图路线否决——能力探针必须匹配可指令自由度,策略本体是最高保真仪器(见 m23_conclusion.md §3)。
- [x] 2026-07-21:"重门 body-assist 涌现"假说否决(推门=形封闭,12 N·m 内 arm 全覆盖;过线前 body 接触 0/10066)——force-feasible 机制改走 C 表路线。
- [x] 2026-07-21:round2(弹簧/高度/站位带)完成于 v15,47/48;round1(回弹动力学+站位自学)完成于 v14。
- [x] 2026-07-22:mass 轴 80–160 完成于 v16(全桶 100% goal,B ckpt2000 为 release);v16 三项行为 shaping 全败并诊断同根(定标未按实测决算 + stage 边界收益断层),重做于 v17 M34/M35。
- [x] 2026-07-22:设计规则第三例沉淀——"stage 边界收益断层":凡跨 stage 的行为目标,其收益项作用域必须覆盖边界两侧,否则策略在边界处理性弃行为(v13 门挡房租、v15 gate 死区、v16 送门无薪同族)。
- [x] 2026-07-24:**push-wide-then-release 于 v17 解决**——6-cell factorial 干净归因:制度(阈值 1.35/1.25)与计价(事件制)均必要、合用充分且可复制(G6);release=G5 ckpt2500,48/48 全桶,松手后接触 47/48→1/48。M36 gain probe PASS(15/16 零样本)→ v18 采纳。posture 经济第二次失败(λ×10 付 12% 收入仍 98-100% 使用)→ 价格弹性假说否决,转 P2 判别探针;scratch 重训仅在"习惯性"判定后立项。
