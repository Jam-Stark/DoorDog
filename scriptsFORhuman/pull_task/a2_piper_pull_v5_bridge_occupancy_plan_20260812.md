# A2+Piper Pull v5 — Bridge Occupancy + Release Persistence:执行方案

**Plan ID:** `a2_piper_pull_v5_bridge_occupancy_and_release_persistence`
**Date:** 2026-08-12 HKT
**Authority chain:** 本文件 > v4 方案 > 外部评审(`scriptsFORhuman/pull_v4/pro—feedback/`,采纳条目见 §0)> 更早方案。冲突以本文件为准。
**GPU 授权:** GPU 4、5、6、7 专用;其余禁用。
**执行模式:** worker session 全自主(用户离线);预案 §6。
**v5 临时文件边界:** 所有 v5 的 runner/receipt/state bank 构建脚本/报告放**新建目录 `scriptsFORhuman/pull_v5/`**;state bank 二进制落 `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/`。

**North Star 不变:** release-then-cross,从门框内穿过,全身清出至 −X。
**本轮停止条件(采纳外部评审表述):** **first reproducible frame passage,且必须同时来自 canonical 起点与 natural 起点两个来源**。release 计数上升或欧氏门框距离缩小不再算进展。

---

## 0. 绑定本轮的合流诊断(本机全部核实)

1. **占据问题(外部评审 Rank 1,采纳为主刀):** Stage 4 从 hinge 0.25 一直包到 E6;staged reset 只在 stage advance 采快照,训练 mass 永远落在早期开门态,release/收臂/对框/过门段占据为零。这解释了 v3、v4 两轮 750-batch 只动次级行为。**再跑 monolithic 750-batch 信息价值低,禁止。**
2. **release 不持久(外部评审 Fact D):** 58.6% 的 G6 release episode 终态重新双侧抓回,release 后门中位关回 0.589 rad。`deliberate_release` 是一步接触转换标签,不是持久技能。v5 一切 release 口径改用 **K-step 无把手接触 streak**(项目自家 debounce 惯用法)。
3. **L1 proximity 效应不成立:** paired B−A 门框距离 +0.0175 m(B 更远);直线指向 midpoint 的向量场无法编码"先避门扇再居中"的非单调路径。L1 保留(release frequency 效应成立)但不再作为 proximity 手段;waypoint 方案为预登记 fork(§6 G7)。
4. **recontact ≠ regrasp:** `post_release_recontact_count` 计 body/arm-panel 接触转换。longterm TODO #1 的证据标注本轮修正;brace 不升格。
5. **closer race 是 FRAME_ALIGN 段的硬约束**(release 后门关回 0.589 rad 中位):canonical states 与 DV 都按 `hinge_drive_max_force` 分层(2.5–5 / 5–9 / 9–12 N·m 三桶)。
6. **"持杆贴框"雏形保留:** G6 中最近的 episode(0.4136 m)横向已居中但仍持杆——natural E5 handoff 态是天然 FRAME_ALIGN 起点,必须进 state bank。
7. **方法学债(本机证实):** `checkpoint_load_mode: policy_only` 与 `algo.config.load_optimizer: true` 并存;evidence zip 缺 step_traces(194/500 MB);R1 v2 渲染无成片。P0 清偿。

## 1. 冻结决定

| 项 | 值 |
|---|---|
| Warm-start actor | `pull_v4_B_wave1_seed1/model_step_000750.pt`(B 臂 release 3/16 最高的那只;若 worker 核对后 seed0/750 的 frame_approach 收入更优可改选,择一并记录理由) |
| P3 训练拓扑 | 256 env × **250 batches**,save 50(短 cell:起点已在瓶颈上,外部评审建议 100–250) |
| Reward | = v4-B 全套(door_wide 0、frame_approach 6.0、其余同 v3);**本轮不改任何 scale** |
| v5 新配置键 | canonical reset 注入开关/比例、release streak K(=25 步 ≈0.5 s)、干预 override 开关;全部进 guard v5 契约 |
| `load_optimizer` | v5 全部配置显式 `false`(消除歧义),并出 runtime load receipt |
| 时长先验 | 250-batch cell ≈ 65 min;探针/捕获各 ≤1 h;全轮含实现预计 8–11 h |

## 2. P0 — 债务清偿与仪器(无训练,≤1 GPU)

**P0-a load receipt。** 读 loader 的 `policy_only` 分支,训练启动时打印/落盘实际 loaded/reset 项(actor/critic/optimizer/scheduler)。若发现 v1–v4 实际加载了 optimizer,**如实写入报告的方法学节**(影响 relay 解读),不回改历史结论。
**P0-b staged-reset buffer census 工具。** 对给定训练 config 跑 64×50 smoke 并周期性 dump 各 stage 快照数、来源、hinge/root/接触/arm 状态分布。先对 v4-B config 出一份 census(量化"占据问题"的现状基线),P3 期间对新机制复用。
**P0-c evidence zip 修复。** 按 v4 handoff 规范的 Tier-3 清单把 step_traces 补进 zip(重建 `a2_piper_pull_v1_to_v4_evidence_20260811.zip`,≤500 MB),manifest 补落 `scriptsFORhuman/pull_v4/EVIDENCE_ZIP_MANIFEST.md`。
**P0-d memory/TODO 修正。** 外部评审 §3.3 的 7 条 metric 语义搬进 memory;longterm TODO #1 的证据标注按 §0.4 改写;记录外部评审包路径。

## 3. P1/P2 — 两个判别探针(并行,各 1 GPU)

**P1 — canonical post-release 可行性探针(no-learning,占据假说的裁决实验)。**
1. **State bank 构建(mixture,两源):**
   - 源 A(动力学一致,优先):冻结 v4-B actor 跑 ~200 episodes,在 E5 后若干步用现有 snapshot 机制捕获完整 sim 状态(含"持杆贴框"态与已 release 态),按 closer 三桶分层存 bank;
   - 源 B(手造补充):脚本构造 hinge 1.6–2.1、gripper 开、无把手接触、arm tuck、root 从实测分布采样,settle ≥50 步且校验稳定(倒地/穿模即弃)。
   - Bank 规模 ≥64 态,记录每态 provenance。
2. **Known-good anchor(rule 5,先过再谈门):** 同一 scripted base-command 库(直线 −X 多速、转身-前行、侧移-穿越、圆弧,全部只经 commandable homie 接口)在**远离门的开阔地**必须完成 waypoint 到达,anchor 不过则修库,库 3 次不过 = 探针实现缺陷,停。
3. **门侧执行:** 从 bank 各态回放命令库,量测 frame_passage、panel 接触、过门瞬间门角、命令跟踪误差;按 closer 桶分层报告。
**判读:** 任一桶 passage>0 → 占据假说坐实,进 P3;全零(anchor PASS 前提下)→ 转 G2 的 locomotion lattice。

**P2 — 冻结 actor release+tuck 干预(1 GPU,~30 min)。**
冻结 v4-B checkpoint,paired fixtures 两组对照:对照组原样;干预组在 hinge≥1.6 ∧ aperture 后触发 **1 s 的 arm/gripper override**(张开 + 收臂到默认位),base 命令保持策略输出。量测:持续无接触率、+1 s/+2 s 门角保持、门框距离、E6。
**判读:** 干预显著改善 → release persistence 是绑定约束(P3 的 streak 口径加权重);无改善 → base 路线是绑定约束(G7 waypoint fork 升位)。

## 4. P3 — 占据重加权训练(2×2,GPU4–7 一波)

**机制(最小 diff 路线,优先):** 复用现有 staged-reset 机构——把 bank 态**注入 stage-4 快照 buffer**(v13 方案 §1.6 已确认直接写 `staged_reset_buf` 张量 + `staged_reset_num_samples` 架构可行),调 stage-4 reset ratio 实现占据重加权。若 per-env 索引布局抵抗注入,fallback 为独立 reset provider(读 bank,按概率替换 reset 状态)。**不在本轮做 stage 机拆分**(大 diff 留给 traversal 打通后的正规化轮)。

**矩阵:**

| Cell | GPU | canonical 注入占比 p | Seed |
|---|---|---:|---:|
| M-s0 | 4 | 0.5(混合) | 0 |
| M-s1 | 5 | 0.5 | 1 |
| C-s0 | 6 | 0.9(重注入) | 0 |
| C-s1 | 7 | 0.9 | 1 |

共同:warm §1、250 batches、save 50。**telemetry 必须逐 episode 标注 reset_source(natural / bank_natural_e5 / bank_constructed),canonical 起点 episode 永不计入 natural-start DV 行**(新 invariant 9)。

**Eval(双源):** 每 checkpoint 两组各 16 episodes——(i) canonical 起点(从 bank 采样),(ii) natural 起点(常规 reset 全程)。主 DV 按两源分列。

## 5. DV 与 invariant

**主 DV:** `frame_passage_rate`(canonical 起点)与 `frame_passage_rate`(natural 起点);E6/E7/complete。
**次级:** `persistent_release_rate`(K=25 streak)、release→regrasp 率(终态双侧接触,正式化外部评审口径)、+1 s/+2 s 门角保持、门框距离(仅作诊断)、panel 接触、closer 三桶分层全套、C 臂 natural-start 开门保持度(E4/E5 对照 v4-B 基线,测灾难遗忘)。
**Invariant(任何非零 = bug 修复重跑):** 承袭八项 + **9. canonical 起点 episode 计入 natural-start DV = 0**;**10. bank 状态 settle 校验失败仍入 bank = 0**。

## 6. 预案(worker 全权)

| # | 触发 | 响应 |
|---|---|---|
| G1 | P1 任一桶 passage>0 | 占据假说坐实,进 P3 |
| G2 | P1 全零且 anchor PASS | 跑 locomotion lattice(外部评审 Rank 4:20–50 态 × 命令网格,记录 requested/realized/滑移/饱和)。lattice 证明接口不可行 → **停轮报告**(residual policy 是用户决策,超界);接口可行但命令库太窄 → 扩库一次重探 |
| G3 | P1 anchor 失败 | 探针实现缺陷,修复重 anchor,3 次上限 |
| G4 | P2 干预显著改善 | release persistence 绑定确认;P3 判读时 streak 指标权重升为主 |
| G5 | P3 任一 cell canonical-start passage>0 | 选最佳 cell 续训(P4:同配置 +250–500 batch,2 seed,GPU 富余时并行 natural-start 巩固);natural-start 也 >0 → **停止条件达成**,渲染 QA 可选收尾 |
| G6 | canonical>0 但 natural=0 | handoff gap:P4 改为 p 退火(0.9→0.5→0.3)续训 |
| G7 | P3 全零 | 按 P2 证据择一预登记 fork 单轴执行一次:waypoint potentials(外部评审 Rank 3,panel-yield→frame-entry→clear 三相位势差)或 maintenance→potential 改造(Rank 5);均无据则负结果收官 |
| G8 | bank 手造态大量 settle 失败 | 退到纯源 A(natural E5 snapshot)bank,报告记录 |
| G9 | 训练/探针崩溃 | 读 traceback 修根因,同 cell 3 次弃 |
| G10 | GPU4–7 部分被占 | 保 P1+P2 优先,P3 降级串行 |
| G11 | 总进度超时 | 最小闭环 = P0+P1+P2+报告(两个探针本身即是可发表的判别结果) |
| G12 | C 臂 natural-start 开门显著退化 | 灾难遗忘记录,结论偏向 M 臂;不加正则拯救 |

## 7. 交付物

1. 代码/配置 commit(`feat(a2): …` 小步)+ push。
2. `scriptsFORhuman/pull_v5/`:state bank 构建/census/probe/intervention/eval runner + `PULL_V5_ROUND_REPORT.md`(P1/P2 判别结果、census 前后对照、2×2 双源 DV 表含 v4-B 基线行、closer 分层、invariant 10 项、预案日志、load receipt 结论)。不写哈希(P0-c 的 zip 除外——zip 本身也不写哈希,以路径+manifest 绑定)。
3. state bank + provenance 清单;训练 `logs_rl/.../pull_v5_*`;eval `logs_eval/a2_piper_pull_v5/`。
4. memory 更新(metric 语义 7 条、占据规律、外部评审指针)+ 两级 TODO 勾稽(含 TODO #1 证据标注修正)。

## 8. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback 强行让仿真跑下去;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:先证明操作路径;不新增测试/护栏/兼容层,除非该功能已实际出错。bank 的 settle 校验属功能正确性,不属过度防御。
- 严控审计:review 至多一轮;严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 非安全攻防项目,禁止过度防御;禁止为基本不可能的 case 写防御;禁止计算/写入任何哈希(含 SHA256);rubric 不过度机械化。
- 等待一律大块 sleep(600s/1800s/3600s/更长)或派子 agent 值守;禁止轮询。
- 工具调用并行批量;上下文压缩重启后不重复回应旧指令,跟紧最新进度。
