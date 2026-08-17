# A2+Piper Pull v5.5 — Residual Terminal-Hold Adapter(梯子第二 rung):Addendum

**Plan ID:** `a2_piper_pull_v5_5_residual_terminal_hold_adapter`
**Date:** 2026-08-17 HKT
**性质:** 本文件是长期 TODO §11 三 rung 梯子**第二 rung 的 planner(用户侧)正式契约**,兑现 v5.4 addendum §0.2 预裁决。v5 科学契约(P3 定义、DV、invariant 1–11、G1–G13、停止条件、warm-start、reward 冻结)**原文有效**;v5.1 G8 bank(191 态)、v5.2 门侧/override/双源实现(static-accepted、未运行)、v5.3 P0 表征、v5.4 Stage A receipt 与 21 常数表均为既有资产,原样复用不重写。冲突时本文件优先。
**GPU 授权:** GPU 4、5、6、7;其余禁用。
**产出落点:** 延用 `scriptsFORhuman/pull_v5/`,新报告 `PULL_V5_5_ROUND_REPORT.md`(英文)。

---

## 0. Planner 裁决与设计依据(全部引用 v5.4 实测)

1. **v5.4 收官追认:** Stage A GO(44 traces/352 trajectories/75,200 rows,判据先于数据)、Stage B valid FAIL(共享修正 −0.3672668934 rad 后 16/16 corrected rows 数值误差 max 0.0900/0.0588 rad,但全部 `trim_step_cap_exceeded`、`terminal_hold_steps=0`、无 DONE)、零 G3 消耗、下游 fail-closed NOT_RUN——全部如实。`v5_4_planner_architecture_decision.json` 与 v5.3 adjudication 保持 immutable。
2. **为什么是学习型闭环(rung 2),不是 scheduler v2:**
   - **通道无精细权威区间:** |u|<0.8 为死区/偏置主导(A4 fallback `+0.05` 的 realized rate 竟为 **−0.031 rad/s**,单向、与命令符号无关);|u|≥0.8 即 ≥0.15 rad/s 粗档。开环/简单反馈可粗放置(0.09 rad!)但不存在"可控小速率"实现受控进入并冻结。
   - **A3 因果检验 FAIL(决定性):** waypoint miss 与 yaw 误差 point-biserial=−0.0334、miss−hit 差 −0.030 rad——**XY 终点保持是与 yaw 无关的独立失效模式**(v5.2 waypoint 7–12/16)。yaw-only 修复永远到不了 anchor 的 16/16 双判据。**因此 adapter 必须同时接管平面 XY+yaw 三维终点保持。**
3. **架构定义:** residual terminal-hold adapter = 小型学习策略,运行于 **frozen HOMIE 之上的高层 base-command 通道**(residual 是相对 HOMIE 栈而言)。在 adapter-active 窗口内**独占写入** `applied[:,0:3]`(XY+yaw 三维,与 v5.4 scheduler 同一写入路径;base slice 其余索引保持原逻辑),脚本侧 base 命令生成在该窗口停用。**Frozen 不动:** HOMIE checkpoint、pull actor(v4-B seed1 step750)、pull 任务 reward/stage topology/optimizer 策略、0.05 m/0.15 rad 阈值、S1–S4 目标定义、G8 bank。
4. **Terminal-hold 语义(明确以免歧义):** rule-5/v5.2 判的是 **terminal current-state 保持(状态判据)**,不要求命令静默。adapter 在 terminal 保持窗口**全程 active 闭环站保**是合法且正是本架构的意义;v5.3 zero-command hold 是能力探针判据,不是 anchor 规则。v5.2 r4 active-hold 失败源于 P 控制器陷死区——学习型控制器可穿透死区(高频大幅抖动是允许的控制策略)。
5. **fail-closed 链(在 v5.4 机制上延长,不重写):** `v5_5_planner_architecture_decision.json`(记录 rung-2 激活、引用 v5.4 artifact 与 Stage B receipt、`fine_tune_deferred=true`)→ T1 训练 gate receipt → T2 rehearsal PASS → T3 G3 anchor PASS → 门侧/P3/P4(v5.2 gates)。缺环拒绝 launch。
6. **rung 3 不预授权:** 若本轮 adapter 被证伪(T1 gate 不达、rehearsal 双 FAIL、或 anchor 3×FAIL),按 G11 收官并**返回 planner 重新裁决**;worker 不得自行启动 HOMIE fine-tune。

## 1. T0 — Adapter 任务与 harness(静态验收)

- **新任务命名空间(只增不改):** `pull_v5_5_adapter_holdtrack`(config/YAML 新文件;pull 任务既有 YAML/reward/stage 文件一行不改)。open-field fixture 复用,无门资产,natural reset yaw≈π(与 bank/anchor 一致)。
- **Episode 结构:** natural reset → **随机脚本前奏**(五族,复用既有 primitive/scheduler 机械):`near_rest`(无前奏)/`coarse_neg`(u=−2,随机时长 ≤4 s)/`coarse_pos`(u=+2,同)/`straight_minus_x` 行走/`side_step` 行走 → **handoff** → adapter 相:目标 = 当前位姿 ⊕ 随机偏移(‖dxy‖∈[0,0.5] m、dyaw∈[−0.6,+0.6] rad,覆盖 v5.2/v5.4 实测 post-transit 离散度并留 ≥2× 裕量;允许课程化从小到大,但 gate 评测必须用全量程分布)。
- **成功判据(与 anchor 同构):** 连续 **K=100 步(2 s)** current-state 同时满足 ‖xy err‖≤0.05 m 且 |yaw err|≤0.15 rad → DONE;adapter 相预算 ≤350 步(250 步内首次入容差 + 100 步保持),超时 FAIL。
- **观测(非特权):** base 系目标误差 (dx,dy,wrapped dyaw)、root 平面线速度、yaw rate、projected gravity、上一步 adapter 动作。**动作:** 3 维 tanh 有界:yaw∈[−2,+2](注册通道上限),XY 界取既有 primitive 生成器注册命令范围(worker 从现行常数引用并写入 receipt)。
- **Reward(仅限 adapter 任务,预注册后冻结):** 归一化误差 dense 项 −(‖exy‖/0.05 + |eyaw|/0.15)、入容差 bonus、连续保持递增 bonus、DONE 终末 bonus、小幅动作变化率(Δa)惩罚;**不惩罚动作幅值本身**(死区穿透需要大幅抖动)。scale 于 T0 静态验收一并冻结,此后不改。
- 训练行/评测行/rehearsal 行一律 `record_class=interface_characterization` 或等价 locomotion 诊断类,`scientific_denominator_included=false`;与门侧科学分母绝对隔离。

## 2. T1 — Adapter 训练与 gate(GPU4)

- **PPO from scratch**(小 MLP,新 optimizer;不加载任何既有 actor/critic/optimizer 状态),256 env,≤750 batches,seed0 单 seed;checkpoint 每 250。独立 tmux `pull_v5_5_adapter_train`,tee 进 `logs_rl/.../pull_v5_5_adapter/`。
- **Gate 评测(每 checkpoint):** held-out 80 episodes = 五族 × 16,全量程偏移分布。**进入 T2 的判据:任一 checkpoint 达 per-family ≥15/16 且 overall ≥77/80。**
- **Plateau 预案:** 750 batches 无 checkpoint 达标 → 允许**一次**证据定向延展(续训至 ≤1500,或由 gate 评测遥测定向的单项课程/reward-scale 调整 + ≤750 重训,二选一);仍不达 → G11 收官,返回 planner(§0.6)。
- 达标 checkpoint 即冻结为版本化资产;后续 rehearsal/anchor/门侧 receipt 必须记录其路径与 step。

## 3. T2 — Rehearsal(GPU4,diagnostic,不占 G3)

- 2 cell,镜像 v5.4 双目标并加 XY 维:cell-A 净转 −2.5 rad + 0.3 m 平移到达后站保;cell-B 净转 +1.0 rad + 0.3 m。每 cell 8 env。
- **PASS 判据:** 8/8 env 达成注册 DONE(100 步 current-state 保持,阈值原文),terminal 行取 `env.step` 返回 dones。
- FAIL → 一次由 rehearsal trace 定向的修正(handoff/窗口常数或指向具体未覆盖初始条件族的单次补训)+ 单次复跑;**仍 FAIL → G11 收官,返回 planner**。

## 4. T3 — Anchor 与条件下游

1. **S1–S4 narrow anchor 复跑**,判据原文(每序列 16/16 terminal current-state waypoint 0.05 m + yaw 0.15 rad;rule-5 语义)。adapter 于各序列 terminal 相 active(handoff 钩子挂既有 S1–S4 phase 机械)。新开 G3 计数 ≤3;attempt 间仅允许 receipt 定向的常数/handoff 修正;仅当 receipt 指认具体未覆盖初始条件族时允许一次定向补训。
2. **任一序列 PASS** → rule-5 admitted subset 进门侧:**原样恢复 v5.2 addendum §1–§2 全部下游**(三桶 → G1/G2 → P3 2×2(GPU4–7)→ 条件 P4 → 双源 eval),门侧定位 primitive 同样 adapter-active;所有 gate 按 v5.2 预注册语义执行,代码不重写。
3. **3×FAIL** → G3/G11 如实收官,返回 planner;附全部 adapter 训练曲线、gate/rehearsal/anchor receipts。

## 5. Invariant 12(新增,运行期核验)

**`adapter_active` provenance:** adapter 仅允许在 locomotion probe 相(anchor primitive、门侧定位 primitive)active;**永不**出现在 P3/P4 训练动作、任何 canonical/natural DV episode 行。每 receipt 行记录 `adapter_active` 布尔 + adapter checkpoint 路径/step;双源 eval 与 P3/P4 侧运行期断言 adapter 未挂载。invariant 1–11 原文不变。

## 6. 排程

```text
T0  v5_5_planner_architecture_decision.json + adapter 任务/harness + 静态验收(~1–2 h)
T1  adapter 训练 ≤750 batches + gate 评测(GPU4,~3–4 h;plateau 预案再 +≤4 h)
T2  rehearsal 2 cell(GPU4,~0.5–1 h)
T3  anchor 复跑(GPU4,G3 ≤3,单次 ~30 min)
T4  (条件)v5.2 门侧三桶 → G1/G2 → P3(GPU4–7)→ P4 → 双源 eval,照 v5.2 排程
T5  render + 英文报告 + memory(adapter 判定为 durable fact)+ 两级 TODO(§11 rung-2 状态)+ commit/push
```
预算:仅 T0–T3+T5 约 7–10 h;若 T4 解锁,全轮 13–19 h。等待纪律照旧:训练 sleep 3600 递进(允许一次至 20h 级),探针/rehearsal 900–1800;禁止轮询;等待期派子 agent 值守。

## 7. Review 纪律

一轮 formal review,重点点名:(a) **adapter 隔离**——仅新增文件,pull 任务 reward/stage/actor/optimizer/阈值零改动;(b) invariant 12 实现与运行期断言;(c) 训练/评测/rehearsal 行与科学分母隔离;(d) gate/rehearsal/anchor 判据预注册且 fail-closed 链逐级生效;(e) 观测非特权、动作界引用注册常数。**FAIL findings = 定向修复 + runtime 验收,不停轮、不二轮**(durable 契约)。

## 8. 交付物

1. feat(a2) 小步 commit(runtime-proven 即提交)+ push。
2. `scriptsFORhuman/pull_v5/PULL_V5_5_ROUND_REPORT.md`(英文):adapter 任务规格与 reward 表、训练曲线摘要、gate 评测五族矩阵、rehearsal receipt、anchor 逐序列 receipt、invariant 12 审计;若 T4 运行,按 v5.2 报告格式续接;G1–G13 日志与 invariant 表照 v5.4 报告格式。不写哈希。
3. 落点:训练 `logs_rl/.../pull_v5_5_adapter/`;gate/rehearsal 前缀 `v5_5_adapter_`/`v5_5_char_`;anchor 前缀 `v5_5_`;门侧/P3/P4 照 v5.2 惯例。
4. `logs_eval/a2_piper_pull_v5/v5_5_planner_architecture_decision.json`(§0.5)。
5. Memory 更新(adapter 能力判定为 durable fact;若证伪,记录返回 planner 语义)+ 两级 TODO 勾稽(§11 rung-2 → 执行结果)。

## 9. 执行纪律(coding role,全程有效)

- fail-fast:isaaclab/训练代码禁止为"健壮性"加保护性 fallback;问题必须在运行中暴露;崩溃读 traceback 修根因,不吞异常。
- 先功能后护栏:不新增测试/护栏/兼容层,除非该功能已实际出错;settle/anchor/invariant 校验属功能正确性。
- 严控审计:review 一轮(§7);严控编译/diff/路径检查次数;禁止重复串行 fixture 修复、sandbox loopback、过保守检查。
- 非安全攻防项目,禁止过度防御;禁止为基本不可能的 case 写防御;禁止计算/写入任何哈希(含 SHA256);rubric 不过度机械化。
- 等待一律大块 sleep 或派子 agent 值守;禁止轮询;工具调用并行批量。
- 上下文压缩重启后不重复回应旧指令,跟紧最新进度。
