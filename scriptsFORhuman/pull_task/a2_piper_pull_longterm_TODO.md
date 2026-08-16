# A2+Piper Pull 线 Longterm TODO

创建:2026-08-10 HKT(v2 收口、v3 立项时)。本表只放 pull 任务线的跨轮期货;当轮方案不引用则不生效。逐条格式:动机 → 触发条件 → 大致做法。主线全局 TODO 见 `scriptsFORhuman/a2_piper_longterm_TODO.md`。

## 1. 门回弹时 arm 重新伸出抵住门板(用户指定,2026-08-10)

- **动机:** 当前门资产 closer 关门慢(max_force/damping = 0.05–0.24 rad/s,全关 11–52 s),release-then-cross 窗口从容,回弹撞击不构成现实失败模式。但更强 closer/更快回弹的资产变体下,release 后 arm 收回默认姿态、门扇回摆撞上正在过门的机器人将成为主要失败模式。期望行为:**穿门过程中检测到门回摆逼近时,arm 重新伸出抵住门板(brace),身体继续通过,清出后收臂**。
- **触发:** 仅在 direct observation 证明强 closer/回摆确实威胁通过、且有效 G2 lattice 达成后，才可单独立项；v3/v4 的 post-release recontact tails 不是 brace 触发证据。
- **v3/v4/v5/v5.1/v5.2 语义勾稽(2026-08-15 03:08 HKT):** v3 seed0 step500 max=`18`、median=`0`（其余格 max≤`1`）；v4 base 六格 max=`10`、最大单格 median=`0`，G6 六格 max=`108`、最大单格 median=`3`。这些数只表示 deliberate-release 后 body/arm-to-panel 的 contact-transition tails，不测 handle regrasp、arm re-extension 或 learned brace；G6 的 E6/E7/complete 仍未改变。v5 固定此解释。v5.1 P2 的显式 release+tuck intervention把 K25 从 `3/16` 提到 `16/16`，但 +2s hinge retention 仅 `5/16`、E6/frame passage 仍 `0/16`；它证明的是 release persistence 与 reclosure/base route 的耦合，不是 arm re-extension、regrasp 或 learned brace。v5.2 三次都停在 natural open-field anchor，门侧 release+tuck、reclosure race 与 G2 均 NOT_RUN；因此 anchor 的 HOMIE yaw failure 不是 direct door-reclosure threat，更不是 brace 触发证据。第 1 条触发条件仍未满足。
- **做法要点:** brace 仍是未实现的 future skill；需要直接的回摆威胁/arm intervention telemetry 和单独授权。不可把现有 panel-contact transition 计数转换为 regrasp 或 brace 行为结论。

## 2. add_walls=True 受限空间 pull(hardening 轮)

- **动机:** 当前无墙,−Y 侧绕行空间无限大,base 避让/绕arc 自由度不现实(worktree 设计文档 R8 已标注为 known optimism)。v3 用 frame_passage 谓词防绕门,但物理上仍是开阔地。
- **触发:** pull 基本 E7/complete 稳定后的第一个泛化 hardening 轮。
- **做法要点:** `add_walls=True` 作为独立因子单开一轮;预期 base-yield 走廊收窄,C3(swing-arc-aware 目标结构)问题真正显形;不与其他因子混跑。

## 3. Mixed push/pull 训练(方向可观测)

- **动机:** v0 起 pull 全部符号为常量;mixed 需要 `doorOpenIO` 成为 live obs 通道、per-env 方向张量、按 IO 分层的 eval。
- **触发:** pull-only 达成稳定 E7 + 用户批准观测契约变更(涉及 checkpoint 手术或重训)。
- **做法要点:** 云端 v0 方案 §F.9 五条前置全部满足后单开一轮;评估必须按 IO 分层,不许平均掩盖单向失败。

## 4. Hook 任务域裁决 + hook × finger-effort 机制景观补测

- **动机:** P1 scripted 探针退役后,hook × effort{10,45} × friction 的 load-to-loss 景观从未补测;当前训练 hook p=0.5 随机、结果被平均。钩形把手是否属于主任务族仍是 open decision(云端方案 §H-4)。
- **触发:** 用户裁决 hook 域;或 policy-as-probe 方式可行时(用成熟 pull checkpoint 分层 eval hook on/off)。
- **做法要点:** 用成熟 checkpoint 做 hook 分层 eval 即可获得大部分景观,无需复活 scripted 探针。

## 5. 手指力真实性:10 N URDF vs 45 N resolved 的硬件锚定

- **动机:** 45 N 是 v20 训练态,10 N 是 URDF 标称;二者都是 simulator profile(云端方案 §H-3)。finger-limited 可行性边界是 force_feasible 论文的第二实验场,至今未测。
- **触发:** 用户给出硬件真值;或 pull E7 稳定后做 10 N zero-shot/adaptation 对照。
- **做法要点:** 先 45 N→10 N zero-shot 分层 eval(rule 9),再按需 bounded adaptation;若 10 N 不可行,负结果照登,不许放宽门物理来救。

## 6. 左开门(door_open_lr="left")对称性验证

- **动机:** 全部 pull 证据在 right 上;direction contract 与 latch/mimic 的 lr 分支从未在 left 上运行验证(latch mimic 的 LocalRot0 翻转分支尤其)。
- **触发:** pull right 线收敛后的廉价泛化检查。
- **做法要点:** U-probe(left fixture)+ 成熟 checkpoint zero-shot 分层 eval 起步。

## 7. Latch 机制的两个未量化边界

- **动机:** v2 U-probe 已定 θ*=0.6 rad、20 N·m 拉不动锁死门;但 (a) 凸轮硬过框的力阈值上界未测(push 侧 attempt20 证明存在);(b) 部分松把手(θ<0.6)时门在中途回锁/卡滞的动力学未表征(v2 latch-based relock 计数 9–15/16 说明策略常在 0.6 线附近骑行)。
- **触发:** 任何把 handle-hold 精度当作瓶颈的轮次;或强 closer 变体轮。
- **做法要点:** 扩展 U-probe:力 sweep 至凸轮过框;θ 骑线动态 sweep。

## 8. Route B(pooled48/holdout64)pull 版

- **动机:** 项目史上 Route B 从未运行;pull 达成稳定 E7 后需要泛化证据才能升 release 级claim。
- **触发:** E7/complete 在 canonical 上稳定 + 用户批准。
- **做法要点:** 复用 v21 机制,阈值按 pull 实测重切(anti-block doctrine),不继承 push 数值。

## 9. RGB/student 蒸馏 pull 版

- **动机:** pull 存在把手遮挡与相机运动反向问题(云端方案 §C-10),teacher 收敛前无意义。
- **触发:** pull teacher 稳定 + 蒸馏管线排期。

## 10. force_feasible 论文 DV 的 pull 侧正式测量

- **动机:** 论文主张 minimal base intervention(u_base = u_user + gate(s)·u_assist);pull 是 finger/workspace 双约束场。v3 起已含 base path/reversal 遥测,但从未做过"力可行 vs base 介入"的正式归因。
- **触发:** pull E7 稳定后,与第 5 条(10 N profile)合并设计一轮。
- **做法要点:** 以 10 N/45 N × 固定几何的分层对照读 base 介入量变化,直接喂论文 DV。

## 11. HOMIE 世界坐标 waypoint + terminal yaw-hold interface (2026-08-16 16:58 HKT — v5.3 H-D)

- **已完成的接口表征:** v5.3 P0 完成 `44/44` cells×`8` env，diagnostic `interface_characterization` 不入 scientific denominator，T1/T2/T4 exact windows=`150/200/300` steps。`u=-2` 在 T1/T2/T4 的两秒 zero-command hold drift mean=`-0.226979/-0.219226/-0.216827 rad`，每 cell `8/8` 超 absolute `0.15 rad`；`u=-0.8,T1` mean=`-0.154359 rad`、`5/8` 超。frozen HOMIE 在 high-|u| 区域 rate-like 但 asymmetric，终点 hold 不合格，选 H-D；它不能解释为 door-side passage zero。
- **停车与触发:** P1 mapping fix、anchor、door buckets、G2、P3/P4、dual-source eval/render 均 `NOT_RUN`，无 passage denominator。下一次门侧 occupancy/traversal round 前此项保持 parked；只有用户以新 approved contract 选择 residual yaw adapter/policy 或 HOMIE fine-tune 时才能重新进入。不得放宽 immutable `0.05 m/0.15 rad`。
- **边界:** v5.2 terminal-current-state rule-5 与 v5.1 S1/S2 initialization latch 事实仍为 version-scoped。唯一 formal review 仍 `FAIL`；H-D fail-closed artifact、dones-derived terminal telemetry、independent declared-versus-actual provenance 已 targeted-fixed/runtime-accepted，不构成第二轮 reviewer PASS。
