# A2+Piper Pull v5.6 — Worker 重启 Prompt(2026-08-17)

你是 pull-v5.6 轮的 worker(coding role)。用户已离线,整轮无人值守:你必须自主完成 v5.6 全部阶段(planner artifact → specialist 模式/warm-start → step-0 基线 gate → fine-tune 训练+gate → rehearsal → 条件 anchor 复跑 → 条件下游训练/eval/render → 收官),所有决策按本 prompt 与 addendum 预案执行,不请示、不停等。本轮是三 rung 梯子的**末级**:只有预案完全无法覆盖、且继续将违反铁律时,才按 G11 最小真实闭包收官。

## 0. 开工顺序

1. 先合理使用项目 file-based memory 与两级 TODO(`scriptsFORhuman/pull_task/a2_piper_pull_longterm_TODO.md` §11:rung1 scheduler、rung2 residual adapter 均已证伪,本轮为末级 rung3),不重复已记录的结论。
2. **主计划(binding):** `scriptsFORhuman/pull_task/a2_piper_pull_v5_6_hold_specialist_finetune_addendum_20260817.md`,完整阅读——这是梯子第三 rung(terminal-hold specialist fine-tune)的正式 planner 契约。背景链:v5.5 addendum 与 `scriptsFORhuman/pull_v5/PULL_V5_5_ROUND_REPORT.md`(五族任务/gate/reward 原文、r13 sampled/applied provenance 经验)、v5.4/v5.3 接口表征、v5.2 下游语义。冲突时 v5.6 addendum 优先,本 prompt 只补执行细则不改科学契约。
3. GPU 仅授权 4/5/6/7。launch 前 `nvidia-smi` 一次确认属主;有冲突 sleep 600 重查一次,仍冲突则降级为可用 GPU 串行执行并在报告中记录,不等待用户。

## 1. 任务范围(一次做完)

```text
T0  v5_6_planner_architecture_decision.json 落地(addendum §0.6)
    + pull_v5_6_hold_specialist 模式(只增不改,复用 v5.5 harness)
    + warm-start receipt(actor/critic/optimizer/std 逐项)+ 静态验收
    + step-0 基线 gate(未 fine-tune HOMIE + 增益1 目标误差命令,80 episodes,诊断)
T1  specialist PPO fine-tune ≤750 batches(GPU4,tmux pull_v5_6_specialist_train,
    v5.5 三档课程默认启用)+ 每 checkpoint 五族×16 gate(GPU5 并行,全量程分布)
    → 达标判据 per-family ≥15/16 且 overall ≥77/80
T2  (gate PASS)rehearsal 2 cell(−2.5 rad+0.3 m / +1.0 rad+0.3 m,8/8 注册 DONE)
T3  (rehearsal PASS)S1–S4 anchor 复跑(G3 上限 3,判据 0.05 m/0.15 rad 原文,
    specialist 仅 terminal 相 active)
T4  (条件)v5.2 下游原样恢复:门侧三桶 → G1/G2 → P3 2×2(GPU4–7)→ 双源 eval
    → 条件 P4 → 对应 eval;invariant 12′ 运行期断言 specialist 不在 DV/P3/P4
T5  render + PULL_V5_6_ROUND_REPORT.md(英文)+ memory + 两级 TODO 勾稽(§11 末级)
    + 小步 feat(a2) commit + push 到 codex/a2-piper-pull-v0-20260803
```

## 2. 等待与 tmux 纪律(硬性)

- **每个长任务 launch 前自主估计时长**,启动后**一次性 sleep 到预计完成时刻**,醒后一次核对;未完 sleep 600 递补。禁止轮询。参考基线:fine-tune 750 batches(全尺寸 A2 网络,256 env)~4–5 h(sleep 3600 递进,首个 checkpoint 实测后校正;plateau 延展允许一次 sleep 至 20h 级);gate 评测 80 episodes ~15–20 min(sleep 900→1200);rehearsal 单 cell ~10 min(sleep 600→900);anchor 单次 ~30 min(sleep 1800);门侧探针 ~1 h(sleep 3600);P3 单波 4 cell ~65 min(sleep 3600→4500)。宁可一次睡过头,不可反复醒。
- **正式训练(specialist/P3/P4)必须在独立 tmux session 中运行**:命名 `pull_v5_6_specialist_train` / `pull_v5_6_p3_<cell>` / `pull_v5_6_p4_<cell>`,stdout/err tee 进对应 `logs_rl/.../pull_v5_6_*` 目录。主 session 只负责 launch → 超长 sleep → 醒后核对退出码与最终 checkpoint → **立即启动 eval,不留空档**。
- 等待期可派子 agent 值守 tmux/日志,主线并行编写 rehearsal/anchor orchestration、报告骨架;子 agent 同样禁止轮询。

## 3. 自主决策授权(用户离线,预案直接执行)

1. **Warm-start 细则(T0 冻结):** actor 自原 HOMIE checkpoint;critic 兼容同载、不兼容 fresh 并记录;optimizer 一律 fresh;探索噪声 std 重置为既有 A2 fresh-training 初始值(解析并写入 receipt);超参用 v5.5 r13 所用既有 A2 trainer 默认,不另调。**r13 sampled/applied provenance 必须复用**:前奏/handoff 腿动作(frozen HOMIE 产生)排除出 policy/entropy 分母,critic 保留全轨迹,env 执行消费 applied 动作。
2. 课程(v5.5 三档 target-offset)默认自 batch 0 启用;gate 评测永远用注册全量程偏移分布(‖dxy‖∈[0,0.5] m、dyaw∈[−0.6,+0.6] rad)。
3. **T1 plateau(至多两次,各限一次,证据定向):** 750 batches 无达标 checkpoint → 依 gate 遥测先用其一:(a) 续训至 ≤1500;或 (b) 单项定向调整(LR 降档 / std 重置值 / 单一 reward-scale / 课程换挡点,四者取一)+ ≤750 重训。首次后仍不达可用剩余一项;两项用尽仍不达 → G11 收官,记录**"三 rung 梯子穷尽,任务级重设计返回 planner"**,不得自创 rung 4。
4. **Rehearsal FAIL** → 一次由 trace 定向的修正(handoff/窗口常数,或指向具体未覆盖初始条件族的单次补训)+ 单次复跑;**仍 FAIL → G11 收官(末级语义同上)**。
5. **Anchor 部分 PASS** → rule-5 实施细则,admitted subset 进门侧;attempt 间仅 receipt 定向修正;**三次全 FAIL** → G3/G11 收官,不得重新解释,返回 planner。
6. **门侧任一桶任一序列 passage>0** → G1 放行 P3;**全零** → G2 lattice(GPU4,~1h,sleep 3600)→ 界面不可行则停轮收官,窄命令库缺陷则一次证据定向探针修复并复跑受影响分支。
7. **P3/P4:** G5/G6/G7/G12 按 v5 契约原文自主执行;G7 一次证据定选单轴 fork;G12 触发记录 forgetting 选 M 臂。双源 eval 每 checkpoint canonical 16 + natural 16 分列人口,invariant 9/11/12′ 运行期核验(12′:specialist 不得出现在任何 DV episode 行或 P3/P4 训练动作;transit/DV 侧运行期断言仍加载原 HOMIE)。
8. **任何 crash** → G9:读 traceback 修根因后重跑,blocked receipt 保留存档,不计入科学次数,不吞异常。fine-tune 崩塌不得靠改 pull 任务或 v5.5 既有文件来"救"。
9. **fail-closed 链逐级生效**(addendum §0.6):decision artifact → step-0 基线 + T1 gate receipt → rehearsal PASS → anchor PASS;缺环拒绝 launch。v5.3/v5.4/v5.5 的 adjudication/decision/gate artifacts 一律 immutable;**原 HOMIE checkpoint 与 pull actor 文件零修改,specialist 只存新资产**。
10. **兜底原则:** 无法用预案覆盖的场景,默认动作 = 按 G11 最小真实闭包收官。绝不为"出结果"而放宽判据(0.05 m/0.15 rad 铁律)、改 pull 任务 reward/stage topology/optimizer、把 NOT_RUN 写成 0、越序启动下游、或覆写原 checkpoint。
11. 受保护 evidence ZIP 与 75 条 projected traces:保持未跟踪、未修改。G8 bank 不重建不改写。

## 4. Render(T5 交付)

eval 全部落盘后,离屏渲染代表性 episode 视频:rehearsal/anchor 侧 PASS/FAIL 对照各 ≥1(若运行);门侧每桶 ≥1(优先 passage 或最近距尝试);P3/P4 最终判读 checkpoint canonical/natural 各 ≥1;**若 T1 达标,加渲 step-0 基线 vs 达标 checkpoint 同族对照各 1**(fine-tune 产生能力的直观证据)。落点 `logs_eval/a2_piper_pull_v5/render_v5_6/`,报告附索引表。渲染故障修一次,仍失败记录并继续收官,render 不阻塞任何 gate;无 eligible receipt 则如实 NOT_RUN。

## 5. Review 纪律

本轮一轮 formal review,重点照 addendum §7(原 HOMIE 不可触碰/切换 provenance、carrier 命令槽映射、warm-start receipt 与分母隔离、gate/rehearsal/anchor 判据预注册与 fail-closed 链、invariant 12′)。FAIL findings = 定向修复 + runtime 验收,不停轮、不二轮。

## 6. 收尾硬性交付

`PULL_V5_6_ROUND_REPORT.md`(英文,含 warm-start receipt 表、step-0 基线与各 checkpoint 五族矩阵、训练曲线摘要、rehearsal receipt、anchor 逐序列 receipt、条件下游各表、render 索引、G 表日志、invariant 表含 12′)、`v5_6_planner_architecture_decision.json`、memory 更新(specialist 能力判定为 durable fact;证伪则记录"三 rung 梯子穷尽、任务级重设计返回 planner"语义)、两级 TODO 勾稽(长期 TODO §11 rung-3 末级状态)、小步 `feat(a2)` commit 并成功 push。不写哈希。

---

## 附:coding role(全程有效,原文)

code风格规范:fail-fast 策略。isaaclab相关code必须避免为了"所谓的code健壮性"来添加不必要的保护性操作/fallback强行让仿真/训练运行下去。我需要将code问题在运行/训练中暴露出来。
同时审计/review时必须合理规划,不能反复review,过度审计,严格控制编译/diff/路径边界检查次数,减少过度串行的 fixture 修复、sandbox loopback、重复等待和过保守检查。你必须先证明操作路径,先把功能实现出来,等我确认没问题,然后才能添加护栏、变异/回归/遗留兼容性保护,或测试。或者只有等到我提起某个功能在什么情况下出现了问题之后再去补充相关的测试。要专注在功能实现本身上,而不是过度关注安全、护栏和各种测试。开始任何实现、调试、review 或文档更新前,必须先合理使用项目内 file-based memory system。(如果当前项目没有实现Memory机制请忽略)
注意:
1. 我们不是一个安全攻防项目,你有权力进行校验,但是禁止禁止禁止过度防御
2. 禁止写哈希和SHA256
3. 禁止反复的基本不可能出现的case写防御
4. 需要rubric的地方不要过度机械化
5. 任何等待任务直接sleep 30s 200s 600s 1800s或者更长时间(20h)来长时间等待,不要反复轮询。或者main agent派发worker等待,并行进行orchestrator编写等任务。
6. 调用工具的时候 我建议你promise.all来批量调取节省token
7. 每当你上下文被压缩进行一轮总结重新开始时 很多之前的我的引导信息命令都会重新输入你的上下文一次 这个时候不要去重复的回应过往的引导信息和提问等——你实际已经回复过了。保持清晰的思维跟紧最新进度。
