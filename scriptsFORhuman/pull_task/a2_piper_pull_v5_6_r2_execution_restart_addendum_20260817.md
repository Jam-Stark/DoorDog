# A2+Piper Pull v5.6-r2 — Execution Restart(同一科学契约,第二次执行):Addendum

**Plan ID:** `a2_piper_pull_v5_6_terminal_hold_specialist_finetune`(不变)
**Execution revision:** r2
**Date:** 2026-08-17 HKT
**性质:** v5.6 科学契约(`a2_piper_pull_v5_6_hold_specialist_finetune_addendum_20260817.md`)**原文继续 binding**——本文件不改任何科学数值/判据/预算,只修执行语义并新增 T0.5。冲突时优先序:本文件 > v5.6 addendum > v5.6 worker prompt。
**GPU 授权:** 4/5/6/7 不变。

---

## 0. Planner 裁决

1. **r1 收官追认:** add-only specialist 实现、warm-start receipt(eager actor 严格重建 `1620→256→128→25`/`1645→512→256→128→12`、fresh critic/optimizer/scheduler、std 1.0、CPU round-trip PASS)为**有效既有资产,r2 原样复用不重写**。step-0 三次 G9(root 依次缺 `experiment_dir`/`output_dir`/`multi_gpu`)后按 G11 最小真实闭包、全部 NOT_RUN 如实标注、immutable 边界零违反、唯一 formal review FAIL 保持——闭包纪律全部追认。
2. **定性:** 这是 **infrastructure BLOCKED,不是科学结果**。根因单一:手工 versioned warm asset 目录无 config.yaml → eval wrapper 落入"读当前 compose"分支 → v5.6 eval exp 的 root schema 不完整,缺字段逐个在 runtime 暴露。rung 3 能力问题分毫未测,**三 rung 梯子未穷尽**,r1 报告 §10 的"任务级重设计"分支不成立、不触发。
3. **G9 语义更正(本契约 durable):** G9 对 infrastructure root-cause 修复**没有次数上限**。"三次上限"是从 v5.1 特定子路径(Source B 三次后按 G8 改道)误迁移的,不是 v5.6 契约条款。G11 的真实触发条件只有两个:(a) 预案完全无法覆盖且继续将违反铁律;(b) **同一根因在完成本文件 T0.5 证明后仍然复发**(说明证明方法本身失效,才回 planner)。
4. **Step-0 语义澄清(消除 r1 歧义):** step-0 必须**执行并产出有效 `STEP0_GATE.json`** 才能进 T1(执行是 fail-closed 链环节);但其**能力计数是诊断值**——即使 0/80 也不阻塞 T1(v5.6 addendum §1"诊断,不 gate 后续"的本意)。

## 1. T0.5 — Eval wrapper root schema 一次性证明(新增,置于 step-0 之前)

1. **源码枚举,禁止逐字段 runtime 试错:** 通读 `gr00t/rl/eval_agent_trl.py` 及 step-0 入口实际调用路径,枚举**全部 root 级 `config.<key>` 读写**(已确认:`experiment_dir` L567、`output_dir` L624、`multi_gpu` L698;`eval_output_dir`、`meta.yaml` 依赖等相邻机制一并核对),把 `pull_v5_6_hold_specialist_eval.yaml` 的 root schema 补齐到完整集合。枚举结果逐项列入报告(字段 → 源码行 → compose 中的提供方式)。
2. **Micro-smoke 边界证明:** 用小规模(≤8 env、短步数)跑一次与 step-0 完全同构的入口命令,证明 Hydra 组合 → IsaacSim 启动 → task construction → 首批 receipt 行的全链;通过后才启动真正的 80-env step-0。该边界已烧掉三次尝试,micro-smoke 是功能证明,不属过度防御;其产物标 diagnostic、不进任何科学计数。
3. **预案(二选一,择路后报告记录理由):** 若枚举补齐后 micro-smoke 仍暴露 wrapper 对 checkpoint-config 分支的硬预期,切换备用路线——给 warm asset 目录仿真训练 run 布局(config.yaml/meta.yaml,内容取一次真实 v5.6 train compose 的保存态),走 v5.5 gate 已在 runtime 证明的分支。
4. T0.5 全程 CPU/轻量;不动 v5.5/pull 任务既有文件;不改科学契约任何数值。**本 revision 不开新 formal review**(v5.6 轮的唯一 formal review 已消耗且 verdict FAIL 定案);T0.5 改动走定向静态验收 + micro-smoke runtime 验收。

## 2. 恢复链条(T0.5 之后,照 v5.6 addendum 原文)

`T0.5 → step-0(80 env,GPU5)→ T1 fine-tune ≤750(GPU4,课程默认启用)+ 每 250 gate(GPU5)→ [plateau 两选项] → T2 rehearsal → T3 anchor(G3≤3)→ 条件 T4 门侧/G1/G2/P3/P4/双源 eval → T5 render+收官`

判据、预算、plateau 两选项、rehearsal/anchor/门侧/P3/P4 预案、invariant 12′、末级语义(证伪才是"梯子穷尽")全部照 v5.6 addendum §1–§8 与 v5.6 worker prompt §3 原文执行,不重复抄写。

## 3. 交付与 immutable

1. 新报告 `scriptsFORhuman/pull_v5/PULL_V5_6_R2_ROUND_REPORT.md`(英文,引用 r1 报告;r1 报告与三份 runner log **immutable 保留**);T0.5 枚举表 + micro-smoke receipt + 择路理由必须入报告。
2. receipts 落原 `v5_6_*` 路径惯例;warm asset 与 `WARM_START.json` 复用不重做(除非 T0.5 择备用路线需在其目录**新增**配套文件——只增不改)。
3. memory + 两级 TODO 勾稽(rung-3 状态从 BLOCKED 更新为 r2 执行结果);小步 feat(a2) commit + push。不写哈希。
4. Immutable 重申:原 HOMIE checkpoint 与 pull actor 文件、0.05 m/0.15 rad、v5.3/v5.4/v5.5 全部 adjudication/decision/gate artifacts、受保护 ZIP 与 75 traces、G8 bank、r1 blocked evidence。
