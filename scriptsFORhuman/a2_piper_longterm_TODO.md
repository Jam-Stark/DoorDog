# A2+Piper 远期工作 TODO(跨版本长效清单)

维护规则:每轮新 plan 落成时核对本清单一次;完成/否决的条目移入文末归档区并注明依据;新远期项随发现追加。时间戳 HKT。
创建:2026-07-21,base_v16 计划落成时(源:v14/v15 plan 的 round3/future 段 + v15 诊断新增)。

---

## A. 已排期(进行中的 round)

| 条目 | 排期 | 出处 |
|---|---|---|
| 姿态经济正则(force-feasible 主线第一实例) | **v16 M29** | v15 诊断:pitch/roll 80% 钉限幅 |
| 穿行送门 + 非线性 body 计价 + 甩门红线分相化 | **v16 M30/M31** | v15 诊断:松手后 40/48 被门撞、451N |
| 门重轴 80–160 kg(冲击/回摆动量) | **v16 M32** | v15 plan §1.5 保险分支 + round3 原定 mass 轴 |

## B. 下一批候选(v17)

| 条目 | 前置/触发 | 出处与要点 |
|---|---|---|
| **真实 Piper effort/velocity 限位改造** | v16 收敛后单独一轮(动执行器,影响全局,不与行为塑形混跑) | v15 诊断:sim 手臂 effort ~100N 级是"超人",这是"重门不重"的根因,也是 force-feasible 研究的实验底座前置。改造后重跑弹簧/mass 分桶,确认 arm 饱和成为真实现象 |
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

- [x] 2026-07-20:M18 静态可达性图路线否决——能力探针必须匹配可指令自由度,策略本体是最高保真仪器(见 m23_conclusion.md §3)。
- [x] 2026-07-21:"重门 body-assist 涌现"假说否决(推门=形封闭,12 N·m 内 arm 全覆盖;过线前 body 接触 0/10066)——force-feasible 机制改走 C 表路线。
- [x] 2026-07-21:round2(弹簧/高度/站位带)完成于 v15,47/48;round1(回弹动力学+站位自学)完成于 v14。
