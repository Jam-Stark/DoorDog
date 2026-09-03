# Claude Code continuation prompt：完成 `base_v26-7` 最终总结，并裁定下一阶段入口

你现在在 `/home/baoquanc/workspace/DoorDog-A2_Piper` 接续一个因 API timeout 中断的
Claude Code session。你接替的是旧 session 的 Owner-facing scientific adjudicator 角色，
不是重新执行 v26-7 的 worker。先恢复旧 session 的论证链，再直接完成它没有回答完的最后请求。

旧 session 对话导出：

`/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_7/claude_history/2026-09-03-142829-local-command-caveatcaveat-the-messages-below.txt`

旧 session 的最后一个 Owner 请求是：

> 由你做最后 v26-7 阶段的总结：定性当前是否满足 v26-7 阶段前的讨论目标；说明
> LEFT/RIGHT 情况下的 max Stage+；裁定能否进入下一步，依旧参照 single-RIGHT 的
> 成功路径，继续优化后续推门行为。

旧 session 已开始读取 endpoint artifact，但汇总脚本先后因 step2000 reducer 没有较晚加入的
`arm_j4_limit_residence_step_share` 字段、部分读数为 `null` 而报错，随后 API timeout。
这不是新的实验失败。不要沿着这两个临时汇总错误继续调试，更不要重跑仿真或训练；直接从冻结
reducer 的已有字段完成总结。

## 1. 工作范围与成功标准

本轮先完成一个只读、证据匹配的阶段判决：

1. 回答 v26-7 是否达成它在启动前冻结的目标；
2. 用 endpoint 数据完整说明 LEFT/RIGHT 各自达到的最高 Stage+，既给逐 cell 数字，也给总体定性；
3. 区分“可以进入下一轮后续推门优化”与“已经证明完整开门/可以更新 Teacher、Student、G7”；
4. 若可以进入下一轮，说明怎样参照 single-RIGHT 正路径，以及下一轮首先应该解决哪个 stage transition；
5. 明确指出当前证据尚不能支持的结论。

先在对话中交付最终总结和裁定。Owner 此请求没有授权新的训练、评估、render、core/config 修改、
Teacher/Student handoff 更新、Git commit 或 push。不要为了阶段总结重新激活 team state、lease、
candidate freeze 或长跑。该任务是 tightly coupled 的只读综合，没有独立 writer lane。

## 2. 必读顺序

先遵守仓库根 `AGENTS.md`，并按项目要求读取最小 file-based memory。随后按以下顺序核对：

1. `.ai/ROLE.md`
2. `.ai/PROJECT.md`
3. `.ai/WORKFLOW.md`
4. `MEMORY.md`
5. `memory/a2-piper/MEMORY.md`
6. `memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md`
7. 上述旧 session 对话导出，尤其最后约 270 行
8. `scriptsFORhuman/v26_7/a2_piper_base_v26_7_bilateral_native_unlatch_plan_20260902.md`
   的 §1、§2.5、§5、§6、§8
9. `logs_eval/base_v26/v26_7_bilateral_native_unlatch_20260902/milestones/step2000/reducer.json`
10. `logs_eval/base_v26/v26_7_bilateral_native_unlatch_20260902/milestones/step3000/reducer.json`
11. `scriptsFORhuman/v26_7/a2_piper_base_v26_7_goal_anomaly_appendix_20260903.md`
12. `memory/a2-piper/push-open-door-optimization/description.md`
13. 需要核对 single-RIGHT 历史时，再读：
    - `scriptsFORhuman/a2_piper_project_handoff_20260725.md`
    - `scriptsFORhuman/pro_reviews/20260827-162429-HKT__e6310042348d/e6310042348d/FULL_REVIEW.md`
      的 single-RIGHT `v12_C → v13_A → v13.1` 部分

source truth 顺序保持为：当前 source/resolved config → runtime artifact → file-based memory →
plan/history。Memory 中尚未清理的旧 TODO 不能覆盖已冻结的 v26-7 endpoint 与 closure。

## 3. 已冻结事实：不要重新裁决或重复审计

- `v26_7_terminal_candidate_r1` 是被 Owner 拒绝的历史候选，不是终态。
- `v26_7_terminal_candidate_r2` 已完成 technical closure，Owner 已接受 durable route。
- Q20 endpoint 固定为 step2000；Q05 endpoint 固定为 step3000。
- 两个 config 都按 plan §6.2 达到 `2/3 seed` 的
  `BILATERAL_UNLATCH_SUPPORTED`，因此 step4000/5000/6000 合规未运行。
- G1 PASS：LEFT offset 镜像约 180°，RIGHT bit-identical，integrity 0。
- G2 PASS：24/24 exact64，offset 修复前的 Wave B endpoint LEFT durable 全为 0。
- Q05 endpoint receipts 为 PASS/0。
- Q20 的历史 receipt FAIL/1 来自提前成功停止后，旧 post-loop 仍索要 step2750–6000
  checkpoints；它已带 endpoint note，不改变 step2000 科学 endpoint，也不回写历史 receipt。
- 无活跃 v26-7 process、tmux、writer 或排他 lease；team state 已归档为 `INACTIVE`。
- 未 commit、未 push；Teacher/Student handoff 与 G7 未更新。
- goal 异常只读核查已经完成，不要再审一次：
  - Q05_S1 LEFT `complete=62/64`；
  - `PASS_NO_MIRROR_DEFECT_FOUND`；
  - `PASS_NO_THRESHOLD_EVIDENCE`；
  - LEFT complete terminal hinge 没有系统性小于 RIGHT；
  - arm_j4 限位主要发生在 Stage4，与 complete terminal 不重合；
  - 该现象保留为 policy/trajectory-side observation，按 plan §8 不进入 v26-7 route，
    也不升级成稳定 goal 能力证据。
- Q05_S2 LEFT step3000 的 durable `60/64`、arm_j4 p95 `1.314685`、限位驻留
  `0.0110%` 已否定“LEFT durable 必须顶限位”。Q05_S0 LEFT durable `0/64`、p95
  `1.142730`、限位 `0%` 支持探索/Stage2→3 收入结构分支，而不是机械撞限。

## 4. Endpoint 的完整 Stage+ 事实表

统一按 `D / S3+ / S4+ / S5+ / complete` 报告。这里的 `Sx+` 是达到该 stage 的 episode
数，不要把它写成稳定通过率或下一阶段的预注册 route。

### Q05，冻结 endpoint = step3000

| Cell | LEFT D/S3+/S4+/S5+/complete | RIGHT D/S3+/S4+/S5+/complete | LEFT max | RIGHT max |
|---|---:|---:|---|---|
| Q05_S0 | `0/0/0/0/0` | `64/64/64/0/0` | Stage2 | Stage4 |
| Q05_S1 | `62/64/62/62/62` | `64/64/64/18/4` | complete | complete |
| Q05_S2 | `60/60/0/0/0` | `57/64/64/21/0` | Stage3 | Stage5 |

### Q20，冻结 endpoint = step2000

| Cell | LEFT D/S3+/S4+/S5+/complete | RIGHT D/S3+/S4+/S5+/complete | LEFT max | RIGHT max |
|---|---:|---:|---|---|
| Q20_S0 | `0/0/0/0/0` | `64/64/2/0/0` | Stage2 | Stage4 |
| Q20_S1 | `61/64/64/3/0` | `63/64/63/0/0` | Stage5 | Stage4 |
| Q20_S2 | `63/64/63/7/0` | `64/64/61/0/0` | Stage5 | Stage4 |

由此需要给出的总体定性至少包括：

- LEFT 的最高观测是 complete，RIGHT 的最高观测也是 complete；两者出现在同一
  Q05_S1 actor/checkpoint，但数量强烈不对称（LEFT 62、RIGHT 4）。
- 除 Q05_S1 外，LEFT 在 Q20_S1/S2 到过 Stage5，RIGHT 在 Q05_S2 到过 Stage5；
  其他多数组合最多到 Stage4，两个 S0 LEFT 仍停在 Stage2。
- 因而“后续推门/穿门通路已被偶发访问”成立；“双侧、跨 seed 稳定 Stage5/complete”不成立。
- v26-7 的预注册目标止于 Stage0→Stage3 的 bilateral unlatch。不能因为以上 Stage4/5/complete
  读数存在，就改写 plan §8 的结论边界。

如果你用临时只读命令重算，只需打印上述 reducer 原始字段；不要修改 reducer、补写缺失字段或
为 `null` 制造默认假数据。

## 5. 对“是否满足阶段前讨论目标”的正确问题边界

冻结 plan §1 的目标不是完整开门，而是：

> 一个网络（单一 actor）在 Stage0→Stage3 上同时学会 LEFT 与 RIGHT 镜像门的 handle
> 下压解锁。Stage4/Stage5 只报告、不参与路由。

因此最终答复应明确采用两层结论：

1. **对 v26-7 的 scoped target：满足。** Q20 在 step2000、Q05 在 step3000 都以
   `2/3 seed` 达到预注册 bilateral durable threshold；它证明几何 offset 修复与恢复夹爪
   capability 后，单一 side-conditioned actor 可以原生学到双侧 unlatch，旧的 LEFT
   结构性全零已经被突破。
2. **对完整推门/走过门任务：尚未满足。** Stage4/5/complete 没有作为本轮 route 注册，
   也没有跨 config、跨 seed、双侧形成稳定证据；S0 LEFT 仍为 0，说明探索/收入结构与
   seed stability 仍是现实问题。Teacher/Student/G7 继续不准入。

不要把“所有 LEFT 都恢复”“双侧已经对称”“goal 已解决”写进结论。

## 6. 下一步裁定：参照 single-RIGHT，但不要退回 single-RIGHT

Owner 问的是能否进入下一阶段研究。预期要作出明确裁定，而不是只说“需要更多数据”：

- **可以进入下一阶段的后续推门优化。** v26-7 已经建立这个入口所需的 bilateral unlatch
  foundation；继续把预算花在证明 handle 能否下压，信息增益已经很低。
- 这里的“可以进入”只表示可以新开一个预注册的 research/training stage，不表示当前 checkpoint
  已可发布为 Teacher，亦不授权你在本轮直接启动新阶段。
- single-RIGHT 历史应作为机制正对照和 stage ordering 参考：
  `v12_C` 先建立 Stage3 admission，`v13_A` 再通过成熟 actor、Stage3 base unlock、
  grasp-gated unlatch/hold-and-drive 与 Stage3→4 grasp requirement 建立开门，随后
  `v13.1` 单独解决 release/target-root handoff 才得到完整 goal。
- 参照的是这条“先稳定 creation/unlatch → 再 Stage3→4 推门并保持 → 最后 release/Stage4→5/
  through”的问题拆分，不是直接加载旧 single-RIGHT checkpoint，不是把 bilateral door distribution
  改回 RIGHT-only，也不是不核对 resolved config 就整包复制 v13_A/v13.1。
- 下一阶段第一优先级应是把已偶发出现的 **bilateral Stage3→4 opening/hold** 变成跨 seed、双侧
  可重复能力；release、Stage4→5 与 final through 应在 opening foundation 通过后作为后一层处理。
- v26-7 endpoint 中已有多个 downstream-positive cell，但 Stage4/5/complete 在本轮是非路由观察。
  不得静默用 Q05_S1 的 `62 complete` 事后挑 checkpoint 并声称它是正式 winner。若下一阶段需要
  选择 source checkpoint，应在新 plan 中显式冻结 selection rule，比较 Q20 step2000 与 Q05
  step3000 的 bilateral downstream coverage、seed stability、arm_j4 行为和 resolved config；
  选择规则必须先于新的 outcome route，不能用 goal anomaly 倒推 winner。

## 7. 最终答复格式

直接用中文给 Owner 一个可以据此决策的总结，建议结构：

1. **一句话裁定**：v26-7 scoped target 是否通过；能否进入下一阶段；完整任务是否已通过。
2. **阶段前目标逐项对照**：几何、夹爪能力、single actor bilateral unlatch、seed/config route、
   未覆盖边界。
3. **LEFT/RIGHT max Stage+ 表**：使用 §4 的 endpoint 表，不混用非 endpoint milestone。
4. **如何解释不对称**：区分 reachability、policy/trajectory observation、seed stability 与
   preregistered capability。
5. **下一步建议**：说明 single-RIGHT 参考链、建议先做 Stage3→4，再做 release/through；
   给出下一阶段应先冻结的最小问题和 checkpoint-selection 原则，但不要未经授权写实现 plan
   或启动实验。
6. **证据边界与状态**：experiment/INSPECTED 证据；无 hardware；无 active process；未更新
   Teacher/Student/G7；未 commit/push。

不要把 worker 的 closure 文本原样复述一遍。Owner 已经知道 v26-7 关闭；你的价值是回答“原目标
是否完成、两侧分别走到哪里、为什么现在可以/不可以转入后续推门优化”。
