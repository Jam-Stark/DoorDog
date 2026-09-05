# base_v26-8 r3 execution closure

日期：2026-09-04 01:20 HKT  
run_id：`v26_8_bilateral_opening_scaffold_decay_20260903_r3`  
终态：`V26_8_NOT_ADMITTED_G1_R3_SCALE_ASSERTION_AFTER_VALID_CONSUMPTION`

## Result

Owner 授权的 plan §14 pending-window 窄修、r3 source lock、G0 与 G1 r3 已执行。改动严格限于跨侧
natural episode 聚合/消费、对应测试、plan amendment 和 `_r3` orchestration；六格 config、driver
target、0.5/0.7、degree/floor/ceiling、16 项名单、reward/stage、source checkpoint、trainer 与
eval/Wave1 reducer 均未改变。

r3 pending-window 语义在 runtime 生效：35 条 trace 中产生 10 次双侧原子消费，首个在 update 2。
但 update 31 的 pending window 为 LEFT `1/1`、RIGHT `1/1` 到 Stage4，冻结 driver 取 min=1.0，按
`driver > 0.7` 正确把 scale 从 1.0 衰减到 float32 `0.9998999834060669`。现行 G1 reducer 仍按 §6.2
要求全部 `scale_after == 1.0`，因此精确 fail-fast：`G1 scale changed at trace row 31`，外层 receipt
`FAIL/1`。

该失败在 strict policy load 与 5 batches 之后，不是 infra；也不能在结果出现后自行放宽 G1 判据。
因此没有启动 Wave 1、milestone 或 Wave 2，没有 r4/relaunch，也没有修改 source/config。

## Typed outcomes

| Gate / branch | Outcome | Evidence |
|---|---|---|
| r3 delta lock | `R3_CONTRACT_PASS` | r2 baseline 23 files；19 unchanged、4 allowlisted changes |
| G0 r3 | `STATIC_PASS / TEST_PASS / REVIEW_PASS` | 7 tests；独立 IsaacLab semantic review PASS |
| P0_ASSETS | `P0_ASSETS_PASS` | 两项冻结资产均 HTTP 200，proxy env 显式进入 receipt command |
| pending aggregation | `RUNTIME_PASS` | 10 rows `consumed=true`、双侧 sample 非零，消费后窗口清零并重新累计 |
| G1 r3 | `G1_FAIL_SCALE_ASSERTION` | row31 scale `1.0 → 0.9998999834060669`，违反现行 G1 全 1.0 断言 |
| Q_A / Q_K | `NOT_RUN` | G1 未准入 |
| Wave 1 | `NOT_RUN` | 没有创建 train root 或 train receipts |
| Wave 2 B1 / B2 | `NOT_RUN` | 没有 Wave 1 endpoint typed outcome |

## Source and gate evidence

- r3 source lock：
  `scriptsFORhuman/v26_8/runtime_logs/v26_8_bilateral_opening_scaffold_decay_20260903_r3/source_lock.json`，
  `STATIC_PASS`，Git HEAD `aa8a05fbbba62600ee2ac87cd1ad16f1bffa03e5`。
- r3 delta lock：同目录 `r3_contract_lock.json`，`R3_CONTRACT_PASS`；allowlist 仅为
  `door_open_a2_base.py`、对应 v26-8 test、plan §14、orchestrator。
- G0：
  `logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3/G0_static_unit/g0_unit.json`，
  `G0_PASS`；CPU tests `7 passed`。
- G1 supervisor receipt：`.ai/runtime/runs/v26_8_g1_wiring_r3/RUN_RECEIPT.json`，`FAIL/1`；
  command 显式记录六项 proxy env。
- process/load receipts：Isaac child 0、capture wrapper 0、policy load observed，actor RMS loaded、strict、
  state key `policy_state_dict`，SRC_S1 SHA-256 匹配。
- checkpoint：`G1_k_wiring/K_S1_smoke/model_step_000005.pt`，存在。
- machine-readable adjudication：
  `logs_eval/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3/G1_k_wiring/g1_failure.json`。

证据等级：aggregation 为 `RUNTIME_PASS`；G1 gate 为 `RUNTIME_FAIL_AFTER_POLICY_LOAD_AND_5_BATCHES`；
没有 Wave 1 experiment evidence。

## Trace adjudication

| Metric | Value |
|---|---:|
| trace rows | 35 |
| skipped rows | 25 |
| consumed bilateral rows | 10 |
| rows with both pending denominators > 0 | 10 |
| first bilateral consume | update 2 / common_step 19 |
| first scale change | update 31 / common_step 289 |
| row31 LEFT rate | 1/1 = 1.0 |
| row31 RIGHT rate | 1/1 = 1.0 |
| row31 scale | 1.0 → 0.9998999834060669 |

r2 的“永远缺一侧”已被修正；r3 的失败不是 pending aggregation 缺陷，而是修复后 driver 在 5-batch
smoke 内真实 engagement 与旧 `scale==1.0` wiring 假设冲突。是否 amendment G1 gate、以及能否对现有
r3 artifact 作非选择性重新裁定，属于 Owner 的新决定，不能由本 closure 静默处理。

## Milestones, reversals, and unrun items

step500–3000 全部未运行，故逐格 D/S3+/S4+/open_hold/S5+/complete、同 source arm−C、K milestone
trajectory、integrity 与 train receipt 均为 `NOT_RUN`，不是 0/64。Q05_S1 source LEFT
`complete=62/64` 仍只是既有非路由观察；没有新 continuation 读数可比较。

未运行：Wave 1 六格、六个 milestone、endpoint reducer、Wave 2 B1/B2、Teacher/Student handoff、G7、
hardware、push。

## Changed paths and Git

本次未获新 commit 授权，未 commit/push。相对 `aa8a05f` 的阶段内改动包括：

- `gr00t/rl/envs/door/door_open_a2_base.py`
- `gr00t/rl/tests/test_a2_v26_8_penalty_curriculum.py`
- `scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md`
- `scriptsFORhuman/v26_8/v26_8_orchestrate.sh`
- `scriptsFORhuman/v26_8/v26_8_r3_verify.py`
- 本 r3 closure 与 r3 runtime roots
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/{description,TODO,DONE}.md`

r1/r2 runtime artifacts、v26-7、六格 YAML、reward/stage/trainer/eval/reducer、Teacher/Student/G7 均未修改。
Owner 之前授权的两个 commit `e3d496b`、`aa8a05f` 保持不变；未 push。

## Resource closure and Owner decision

收尾释放全部 v26-8 r3 leases，确认无 v26-8 writer/tmux/Isaac process。机器上的独立低显存 sim2sim
进程不属于本阶段，按 Owner 授权未干预。

恢复需要 Owner 明确决定：保持现行 G1 scale gate 并接受本终止 closure，或另行 amendment G1 wiring
判据。任何后续运行、现有 artifact 重裁或 commit 都不在本次授权中。
