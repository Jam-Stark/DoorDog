# Cloud Pro 决策 Prompt：解锁 base_v20 的 P1_PHYSICAL_BLOCKER

你是 DoorDog `A2_Piper` 的独立方案决策者。请审阅随附证据包，并对
`scriptsFORhuman/a2_piper_base_v20_optimization_plan_20260728.md` 作一次明确、
可执行且有停止条件的方案裁决。你的任务是修改 v20 方案，不是继续调参、
替当前失败补写 PASS，也不是直接实现代码。

## 已冻结事实（不得重新解释为 PASS）

- P1 原门槛：先以 F0、必要时以 F1（平面位移不超过 `0.10 m`、yaw 不超过
  `0.15 rad`）选择 `theta_send >= 0.90 rad`，固定 pooled48 至少 `46/48`
  strict-valid feasible episodes。
- 已批准的唯一有限修复 `P1_TX1_TRANSACTIONAL_REFERENCE` 已在 commit
  `365667110b2e64b335dcf3517361245331db604e` 完成；closure/docs commit 为
  `282ab4a`。
- 静态 admission 仅为 STATIC PASS：targeted P1 `39 passed`、全部 base_v20
  CPU `98 passed`、Python compile、`git diff --check`、resolved Hydra compose
  均通过。
- 唯一获准的 `F1 / 0.90 rad / seed0 / 4-env` smoke 已在物理 GPU0 运行。
  canonical capture `4/4`，但 `ARC_PROBE_REACHED 0/4`；结果为
  `2 ARC_PROBE_ROOT_BOUND + 2 ARC_PROBE_OVERSPEED`，最大 hinge 约为
  `0.014 / 0.036 / 0.031 / 0.006 rad`。
- transaction audit 对所有 sample PASS；无 root-plane crossing、无 dead settle
  state、无 traceback/runtime exception/non-finite failure。因此该次有限修复
  已完成其诊断目的，但没有达到物理可行性门槛。
- 按预注册 one-shot stop rule，P1 已正式关闭为 `P1_PHYSICAL_BLOCKER`。
  这表示“当前 geometry/control interface 未过门槛”，不等价于证明纯几何上
  永远不可达。
- 未运行 pooled48、P2 或 G1–G7；`FORMAL TRAINING READY = false`。
- 所有未来任务只能使用物理 GPU0–6；GPU7 正被其他任务占用，严禁使用。

关键校验值：

```text
resolved Hydra config SHA256 = 2823acc622a977526872e477e7f6a65605e57df2fa969545922c58cb36012ba9
checkpoint SHA256            = b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d
adjudication JSON SHA256      = fc8c0fd83c3cea88fa4c808ba96cea48e7164dd11cac76a64b6f082be29a640b
runtime summary SHA256        = 70e46893475e7e16d61161925f1eff7e9809d797f30e0b2499c3f0717513d39e
```

## 必须审阅的材料

1. `scriptsFORhuman/v20/P1_HANDOFF_20260729.md`
2. `scriptsFORhuman/a2_piper_base_v20_optimization_plan_20260728.md`
3. `gr00t/rl/envs/door/door_open_a2_base.py`
4. `scriptsFORhuman/v20/a2_piper_v20_arc_feasibility.py`
5. `gr00t/rl/tests/test_a2_v20_arc_feasibility.py`
6. `logs_eval/base_v20/preflight/p1_tx1_smoke_commit3656671_20260729/` 中的
   adjudication、per-env records、Hydra resolved config、runtime summary、logs
   与 step traces
7. 包内两个 Git patches，以及两个 `.orig` 调查快照（仅作前后对照）

## 你必须在三个决定中只选一个

### A. `REVISE_V20_BEHAVIOR_CLAIM`

承认原有 arm-led send/`theta_send >= 0.90 rad` 科学主张不再是正式训练的
硬门槛；给出替代的、可测量的行为主张和新 gate。不能把删除或降低 P1
伪装成 `P1 PASS`，必须标明被放弃/降级的原 claim，并说明 v20 此后是正式
release matrix 还是 exploratory matrix。

### B. `APPROVE_NEW_GEOMETRY_CONTROL_SCOPE`

保留原科学门槛，但把下一步定义为一个全新的、一次性的 geometry/control
investigation，而不是延长已经关闭的 P1_TX1。必须给出唯一 root-cause hypothesis、
精确文件/函数/config 改动、禁止项、4-env admission、是否允许 pooled48、资源
预算和 one-shot stop rule。不得建议 open-ended gain/lead/threshold sweep，不得
放宽真实 joint/root/action limits，也不得靠 silent fallback 让 probe 继续。

### C. `TERMINATE_BASE_V20_AS_DESIGNED`

判定原 v20 scientific design 在当前约束下不应继续；保持 G1–G7 禁止启动，
并列出以后重新立项所需的新证据，而不是继续消费本方案预算。

“跳过 P1 且不修改方案就直接训练”不是合法选项。若你认为可训练，必须先
选择 A 并完整改写 scientific claim、gate、factorial interpretation 和发布口径。

## 必须逐项给出的方案修改

请引用原计划的具体章节/条目，至少覆盖：P1、P2、M45–M49、C2、G1–G7、
GPU mapping、正式训练启动条件与失败停止条件。对每项说明 `KEEP / REWRITE /
REMOVE`，给出替换文字或足够精确的 patch-style prose。还必须说明：

- 哪些原结论仍可由现有证据支持，哪些必须撤回；
- 新门槛的物理/统计理由，以及如何防止“先看结果再改门槛”；
- 最小 acceptance matrix（STATIC、RUNTIME、POLICY 分开）；
- 是否需要新增代码、只改 plan，或终止方案；
- 允许的 GPU、环境数、seed、最长运行次数和 artifact 路径；
- 下一次失败后的明确终止状态，禁止无限迭代；
- 在什么唯一条件下 `FORMAL TRAINING READY` 才能变为 `true`。

保持 fail-fast；优先 IsaacLab high-level API。明确区分 `STATIC PASS`、
`RUNTIME PASS`、`POLICY PASS`、`STRICT_INVALID` 与 `INCONCLUSIVE`。不要把 hinge
运动本身当成 strict feasibility，也不要从 invalid control trajectory 推导纯几何
不可能。

## 强制输出格式

先输出下列 decision block，不能含糊或给多个并列推荐：

```text
DECISION = REVISE_V20_BEHAVIOR_CLAIM | APPROVE_NEW_GEOMETRY_CONTROL_SCOPE | TERMINATE_BASE_V20_AS_DESIGNED
P1_STATUS = P1_PHYSICAL_BLOCKER
ORIGINAL_V20_CLAIM = RETAIN | REVISE | ABANDON
FORMAL_TRAINING_READY_NOW = false
G1_G7_MAY_LAUNCH_NOW = no
LEGAL_PHYSICAL_GPUS = 0-6 only
NEXT_APPROVED_SCOPE = <one bounded sentence, or NONE>
NEXT_STOPPING_CONDITION = <one falsifiable sentence>
```

随后只输出：

1. `EVIDENCE INTERPRETATION`
2. `PLAN PATCH TABLE`
3. `ACCEPTANCE AND RESOURCE MATRIX`
4. `ONE-SHOT STOP RULE`
5. `TRAINING-READINESS TRANSITION`
6. `RISKS / CLAIMS ABANDONED`

若材料不足以支持 A 或 B，请选择 C；不要以“需要更多探索”为由创建无限循环。
