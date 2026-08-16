# A2+Piper Pull v5.4 — H-D 处置:Measured-Model Terminal-Yaw Scheduler + Anchor 复跑:Addendum

**Plan ID:** `a2_piper_pull_v5_4_terminal_yaw_scheduler`
**Date:** 2026-08-16 HKT
**性质:** 本文件是 v5.3 H-D/G11 收官后的 **planner(用户侧)architecture decision 文件**,依长期 TODO §11 parked 条款正式重新开门。v5 科学契约(P3 定义、DV、invariant 1–11、G1–G13、停止条件、warm-start、reward 冻结)**原文有效**;v5.1 F1–F5/G8 bank(191 态)、v5.2 T0 门侧/override/双源实现(static-accepted、未运行)、v5.3 P0 表征 44 traces 与三项 review 修复均为既有资产,原样复用不重写。冲突时本文件优先。
**GPU 授权:** GPU 4、5、6、7;其余禁用。
**产出落点:** 延用 `scriptsFORhuman/pull_v5/`,新报告 `PULL_V5_4_ROUND_REPORT.md`(英文)。

---

## 0. Planner 裁决(本文件的法律地位)

1. **v5.3 收官全部追认:** 44/44 表征 cell 完整;H-D 裁决忠实于预注册判据(`u=-2` 三档两秒 hold drift −0.226979/−0.219226/−0.216827 rad,8/8 超 0.15);三项 review finding 定向修复 + bounded 验收;下游如实 NOT_RUN;review verdict 保持 FAIL 不改写。`logs_eval/a2_piper_pull_v5/v5_3_p0_adjudication.json` 为 immutable,不得编辑。
2. **Architecture decision(取代"residual vs fine-tune"二选一,三段梯子):**
   - **判据核心事实(全部来自 v5.3 P0 实测):** H-D 命中的 zero-command drift 只出现在**大负命令停止段**(u=−2 → ≈−0.22 rad;u=−0.8,T1 → −0.154)。近静止/小命令 hold drift ≤0.02 rad;u=+2 停止漂移 +0.033…+0.039;u=+0.8 为 −0.039…−0.063 —— 均值口径全部在 0.15 门槛内。终点 hold 的不可行是"负大命令急停"这一 **regime 的属性,不是全 regime 属性**;而终点接近方向与停止时机是探针侧可规划量。
   - **第一段(本轮):** 零训练、纯测量模型的 **terminal-yaw scheduler**——即原 H-A"模型化 rate 命令+到达即停"与 H-C"实测标定/死区/延迟裕量"的合体,加方向偏好与 aim-off。GO/NO-GO 由既有 trace 的 CPU 挖掘按 §1 预登记判据裁定,不预烧 GPU、不占 G3。
   - **第二段(预裁决):** 若 Stage A NO-GO、rehearsal 双 FAIL、或 anchor 3×FAIL → **residual terminal-hold adapter 即为已裁决的下一架构**(v5.5 契约由 planner 另发;worker 不得自行启动训练)。
   - **第三段(无限期后置):** HOMIE fine-tune。理由:v1–v5 全部证据链建立在 frozen HOMIE 上的 provenance 连续性;HOMIE 训练栈在本 repo 的可得性未证;XY tracking(anchor waypoint 现最好 12/16)回归风险。仅当 residual 路线也被证伪后再议。
   - 长期 TODO §11 的 parked 条款由本文件解锁,收轮时按上述三段梯子改写其状态。
3. **fail-closed 链(沿用 v5.3 gate 机制,不重写):** worker 先落地 `logs_eval/a2_piper_pull_v5/v5_4_planner_architecture_decision.json`,记录本文件 plan-id、v5.3 adjudication 文件路径引用、`decision=MODEL_BASED_SCHEDULER_FIRST`、`residual_precommitted=true`、`fine_tune_deferred=true`。下游 admission 逐级要求:该 artifact → Stage A GO receipt → Stage B rehearsal PASS → G3 anchor PASS;缺任一环,orchestration 拒绝对应 launch。
4. **铁律不变:** 0.05 m / 0.15 rad 不得放宽;reward scale、stage topology、optimizer 策略、训练动作、HOMIE checkpoint、受保护 ZIP 与 75 条 projected traces 一律不动。

## 1. Stage A — v5.3 trace 挖掘与可行性裁决(CPU-only,不开 GPU,不占 G3)

**数据源:** 44 条 `logs_eval/a2_piper_pull_v5/v5_3_char_*/characterization_trace.json`(50 Hz 逐步 `phase`/`realized_world_yaw_pre/post`/`yaw_velocity_rad_s`/`root_motion_xy_world`);v5.2 anchor receipts(`logs_eval/a2_piper_pull_v5/pull_v5_2_p1_anchor_probe/`)作 A3 相关性数据源。**注意:accepted P0 traces 中 `terminal_after_step` 为已知 stale 语义(review finding,修复只覆盖后续运行),分析一律忽略该列。**

- **A1 停止剖面:** 每 (sign,|u|,T) cell 逐 env 计算:cutoff→hold 末总漂移、settle 时间(最后一个 `|yaw_velocity|>0.05 rad/s` 的 hold 步)、settle 后残余漂移。报告 per-env min/median/max;**禁止以均值替代 worst-case**。
- **A2 平稳性:** hold 段最后 1 s 的 max |yaw(t)−yaw(end)|;判定负侧漂移是有限瞬态(finite transient)还是持续 rate(u=−2 三档 hold 末是否仍在转)。该值给出"2 s 平稳漂移上界"。
- **A3 XY 与耦合:** hold 段逐 env 平面漂移 worst-case vs 0.05 m;coupling cells 的 walking-phase yaw bias per primitive;v5.2 receipts 中 waypoint-miss episode 与 terminal |yaw err| 的相关(miss 是否集中于高 yaw 误差,即修好 yaw 可望连带修 XY)。
- **A4 预登记 GO/NO-GO(判据先于跑数固定):** GO 当且仅当存在 trim 方向 d 与幅值 u*∈已测档位,使
  (i) per-env worst |stop_drift(d,u*) − median_stop_drift(d,u*)| + A2 平稳漂移上界 ≤ **0.10 rad**(为 0.15 门槛留 ≥0.05 margin);
  (ii) settle 时间 ≤ 2 s;
  (iii) hold 段 XY 漂移 per-env worst ≤ 0.03 m,**或** A3 显示 v5.2 waypoint-miss 集中于高 yaw 误差。
  产出 `scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json` + 报告章节。**NO-GO → 跳过 Stage B/C,按 G11 收官,§0.2 第二段预裁决即刻记录生效。**

## 2. Stage B — scheduler 实现 + rehearsal(若 GO)

- **修改范围严格限定:** 仅探针侧 yaw 命令生成(`applied[:,2]` 的调度/写入,替换原闭环 P-误差映射)与 phase 排程(何时走 XY、何时 stationary yaw trim、cutoff 时机)。**冻结不动:** 0.05 m/0.15 rad 阈值、waypoint/yaw 目标定义、`a2_hold_base_relief_command` 内部实现、reward、stage topology、optimizer 策略、训练动作、HOMIE checkpoint。
- **调度形(三相,常数逐项引用 A1/A2 实测数,常数表进报告,禁止自由旋钮):**
  (a) **coarse:** |u|=u_coarse(取已测档,预期 2.0)按测得 gain 计划转角,cutoff 提前量 = 该 (方向,u) 的 median stop-drift;**负向 coarse 必须计划性 undershoot,保证余差落在 trim 方向一侧**;|初始 err| 小于 A1 定义的 trim-reachable 带(≈0.3 rad)时跳过 coarse。
  (b) **settle:** 零 yaw 命令等待 ≥ A1 settle 时间。
  (c) **trim:** 仅 A4 选出的方向 d(按现有均值预期为正向)、幅值 u* 的脉宽微调(单步 ≈ rate×0.02 s),每脉冲带 aim-off;|predicted err| ≤ 0.10 rad 且 rate settled 后进 terminal 零保持,XY 按冻结生成器输出。
- **Rehearsal(diagnostic class,GPU4,≤2 cell,不占 G3,行打标 `interface_characterization`):** open-field 合成目标,建议净转角 −2.5 rad 与 +1.0 rad 各一;判据:**8/8 env terminal 2 s |yaw err| ≤ 0.15 rad 且 mean ≤ 0.10**。FAIL → 允许一次由 rehearsal trace 定向的常数修正 + 单次复跑;**仍 FAIL → 视同 NO-GO 收官,不得进 anchor**。
- 实现崩溃属 G9(修根因重跑,不计次)。

## 3. Stage C — anchor 复跑与条件下游

1. **复跑 S1–S4 narrow anchor**,判据原文不变(每序列 16/16 terminal current-state waypoint 0.05 m + yaw 0.15 rad;v5.2 rule-5 语义,无 historical latch)。新开 G3 计数,上限 3 次;每次修正必须由 receipt 证据定向。
2. **任一序列 PASS** → rule-5 admitted subset 进门侧:**原样恢复 v5.2 addendum §1–§2 全部下游**(三桶门侧探针 → G1/G2 → P3 2×2(GPU4–7)→ 条件 P4 → 双源 eval、invariant 9/11 运行期核验),所有 gate 按 v5.2 预注册语义执行,代码不重写、只运行。
3. **三次仍 FAIL** → 按 G3/G11 如实收官;不得重新解释为门侧结论;§0.2 第二段预裁决记录生效,连同 Stage A/B/C 全部 scheduler traces 一并上报,等待 v5.5 residual 契约。

## 4. 排程

```text
T0  v5_4_planner_architecture_decision.json 落地 + Stage A trace 挖掘(CPU,~1–2 h)→ GO/NO-GO
T1  (GO)Stage B scheduler 实现 + 静态验收 + rehearsal(GPU4,~1–2 h)
T2  Stage C anchor 复跑(GPU4,G3 上限 3 次,单次 ~30 min)
T3  (条件)v5.2 门侧三桶 → G1/G2 → P3(GPU4–7)→ P4 → 双源 eval,照 v5.2 排程
T4  render + 英文报告 + memory(scheduler 判定为 durable fact;若预裁决生效,记录激活语义)
    + 两级 TODO 勾稽(长期 TODO §11 按 §0.2 改写)+ commit/push
```
预算:仅 T0–T2+T4 约 3–5 h;若 T3 解锁,全轮 8–11 h。等待纪律照旧:launch 后大块 sleep(训练 3600、探针/rehearsal 900–1800),醒后一次核对,未完 sleep 600 递补;禁止轮询;等待期派子 agent 值守。

## 5. Review 纪律

本轮允许一轮 review,重点点名:(a) Stage A 统计如实——per-env worst-case 不得以均值替代,GO/NO-GO 判据先于数据固定;(b) scheduler 常数与 A1/A2 receipt 的逐项可追溯;(c) 修改范围边界——仅探针侧 yaw 调度/排程,生成器内部与阈值未动;(d) rehearsal/表征行与科学分母的隔离;(e) fail-closed 链逐级生效。**FAIL findings = 定向修复 + runtime 验收,不停轮、不二轮**(durable 契约)。

## 6. 交付物

1. 代码/配置 commit(`feat(a2): …` 小步,runtime-proven 即提交)+ push。
2. `scriptsFORhuman/pull_v5/PULL_V5_4_ROUND_REPORT.md`(英文):Stage A per-env 统计表与 GO/NO-GO 判据回放、scheduler 常数表(逐项引用实测)、rehearsal receipt、anchor 逐序列 receipt;若 T3 运行,按 v5.2 报告格式续接门侧/P3/P4/双源表;G1–G13 决策日志与 11-invariant 表照 v5.3 报告格式。不写哈希。
3. Eval 落点 `logs_eval/a2_piper_pull_v5/`(rehearsal 前缀 `v5_4_char_`,anchor 前缀 `v5_4_`);训练(若跑)`logs_rl/.../pull_v5_4_*`。
4. `logs_eval/a2_piper_pull_v5/v5_4_planner_architecture_decision.json`(§0.3)。
5. Memory 更新 + 两级 TODO 勾稽(长期 TODO §11 状态按 §0.2 三段梯子改写)。

## 7. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:不新增测试/护栏/兼容层,除非该功能已实际出错;settle/anchor/invariant 校验属功能正确性。
- 严控审计:review 一轮(§5);严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 非安全攻防项目,禁止过度防御;禁止为基本不可能的 case 写防御;禁止计算/写入任何哈希(含 SHA256);rubric 不过度机械化。
- 等待一律大块 sleep 或派子 agent 值守;禁止轮询;工具调用并行批量。
- 上下文压缩重启后不重复回应旧指令,跟紧最新进度。
