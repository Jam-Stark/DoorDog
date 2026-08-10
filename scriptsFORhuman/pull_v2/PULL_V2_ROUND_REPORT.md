# A2+Piper Pull v2 Round Report

**Plan:** `a2_piper_pull_v2_wall_removal_and_unlatch_calibration`
**Branch:** `codex/a2-piper-pull-v0-20260803`
**Status:** COMPLETE
**Evidence identity:** path-bound；本报告不包含任何 hash。

## 1. 结论

Pull-v2 证实了 v1 的 `near_closed=0.1` reward wall 是 Stage3→4 的主阻碍。唯一 reward 改动是把 `a2_stage3_unlatch_near_closed_hinge_threshold` 从 `0.1` 调到 `0.25`；`UNLATCH_NORM=0.6`、速度 norm、`dont_push_door_handle`、`target_root_distance`、Stage3→4 物理 gate 均未改变。

Wave1 两个 seed 都触发 G1：seed0 step750 的真实 Stage3→4 为 `10/16`、valid-hold hinge Δ max 为 `0.749745 rad`；seed1 step750 为 `6/16`、`0.492656 rad`。最直接的墙读数也从 v1 的 `0.105–0.25` band 恒零变为 Wave1 的 `1997/1193` 个 dwell step，且该区间 `unlatch_hold` active step 为 `1643/1046`。墙已被拆除，不是均值波动造成的假阳性。

按 G1 从 Wave1 seed0 step750 relay 训练 Wave2 后，六个 checkpoint 全部出现真实 Stage4：seed0 为 `13/16、14/16、15/16`，seed1 为 `11/16、16/16、16/16`。step750 hinge Δ max 达 `2.527259/2.617994 rad`。因此 pull-v2 已完成“冲真 Stage4 占据”的 stopping condition；下一轮 v3 应进入 traversal（V1-C 域），不在本轮继续改 reward。

Wave1 和 Wave2 共 12 个 accepted cell、192 个 terminal episode；四项完整性 invariant 在每个 cell 都为零。A0 未触发，因为 G3 为 false。

## 2. 实验与证据边界

- V2-W 从 v1-R seed0 step750 `policy_only` warm start；每个 formal cell 为 256 env × 750 batch，checkpoint 250/500/750。
- Wave1：V2-W seed0/seed1 并行运行于物理 GPU6/GPU7。
- Wave2：选 Wave1 seed0 step750 为最佳 checkpoint，再 relay 750 batch × 2 seed，仍为 GPU6/GPU7 并行。
- 每个 checkpoint 使用 full load、16 env、每 env 一个 terminal episode，并启用 `stage2_5_step_trace.json`。
- `true_stage3_to4_rate` 使用物理谓词直判；Stage4 label 只作 invariant/占据辅助，不替代物理 DV。
- Stage4 是锁存状态。“低于 gate 的 Stage4 快照”因此定义为每个 env 的首次 `stage>=4` 准入快照；越过 gate 后门回摆而仍处于锁存 Stage4 的 trace row 不属于假准入。

## 3. U-probe 解锁标定

Canonical receipt：`scriptsFORhuman/pull_v2/PULL_V2_U_PROBE_UNLATCH_CALIBRATION.json`。探针使用确定性的标准 fixture（0.95×2.05 m、120 kg、right/out、无墙无地板、门参数随机化冻结），无机器人参与；handle 每个角度钳制 200 step，hinge 目标 150°、effort limit 20 N·m。

| θ (rad) | latch (m) | hinge max (rad) |
|---:|---:|---:|
| 0.000 | 0.000002468 | 0.001942541 |
| 0.100 | 0.003830731 | 0.001946197 |
| 0.200 | 0.007641913 | 0.001949718 |
| 0.300 | 0.011461634 | 0.001953385 |
| 0.400 | 0.015282259 | 0.001955498 |
| 0.500 | 0.019753739 | 0.048451886 |
| 0.600 | 0.022923715 | 0.129359171 |
| 0.700 | 0.026744625 | 0.129355833 |
| 0.785 | 0.029999895 | 0.129352406 |

`theta*=0.6 rad`，因此回填 `a2_pull_e3_latch_threshold_m=0.02292371541261673`。G5 未触发（`theta*≤0.7`）；G6 未触发（θ=0 时 hinge max 仅 `0.001943 rad`，未超过 `0.05 rad`）。这与 latch 咬合空隙证据一致。

第一次探针 receipt `PULL_V2_U_PROBE_UNLATCH_CALIBRATION_ATTEMPT1_SAMPLED_INVALID.json` 使用了随机抽样 fixture，不能作为可复现标定，已明确标记 invalid 并由上述 canonical receipt 取代。实现也从 AppLauncher import-order 错误和 teardown hang 的实际 traceback/行为修到自然退出；没有加入 silent fallback。

## 4. 主对比表

`hinge Δ` 为 valid-hold episode median/max；Stable 和 Relock 分别按 handle-based/latch-based 给出。`Inv=0` 表示四项 invariant 分别为零。

| Wave/cell | Seed | Step | True S3→4 | +hinge/valid hold | hinge Δ med/max (rad) | Stable H/L | Relock H/L | dwell .105–.25 / active | Integrity |
|---|---:|---:|---:|---:|---|---|---|---:|---|
| v1-R baseline | 0 | 750 | 0/16 | 16/16 | .012801/.100607 | 13/16 / N/S | N/S | 0 / 0 | Inv=0 |
| Wave1 | 0 | 250 | 0/16 | 16/16 | .034635/.146152 | 14/16 / 14/16 | 1/16 / 10/16 | 122 / 133 | Inv=0 |
| Wave1 | 0 | 500 | 0/16 | 16/16 | .049263/.100114 | 16/16 / 16/16 | 0/16 / 4/16 | 0 / 1 | Inv=0 |
| Wave1 | 0 | 750 | 10/16 | 16/16 | .409046/.749745 | 15/16 / 15/16 | 6/16 / 10/16 | 1997 / 1643 | Inv=0 |
| Wave1 | 1 | 250 | 0/16 | 16/16 | .034921/.104995 | 16/16 / 16/16 | 1/16 / 9/16 | 0 / 14 | Inv=0 |
| Wave1 | 1 | 500 | 0/16 | 16/16 | .066869/.246345 | 15/16 / 15/16 | 0/16 / 3/16 | 597 / 624 | Inv=0 |
| Wave1 | 1 | 750 | 6/16 | 16/16 | .217618/.492656 | 16/16 / 16/16 | 1/16 / 5/16 | 1193 / 1046 | Inv=0 |
| Wave2 relay | 0 | 250 | 13/16 | 16/16 | 1.056963/1.379278 | 15/16 / 15/16 | 4/16 / 12/16 | 737 / 477 | Inv=0 |
| Wave2 relay | 0 | 500 | 14/16 | 16/16 | 1.380086/1.887876 | 14/16 / 14/16 | 0/16 / 11/16 | 425 / 440 | Inv=0 |
| Wave2 relay | 0 | 750 | 15/16 | 16/16 | 1.726028/2.527259 | 15/16 / 15/16 | 1/16 / 9/16 | 454 / 472 | Inv=0 |
| Wave2 relay | 1 | 250 | 11/16 | 16/16 | .502807/.910342 | 16/16 / 15/16 | 2/16 / 12/16 | 1809 / 1854 | Inv=0 |
| Wave2 relay | 1 | 500 | 16/16 | 16/16 | 1.445209/2.217627 | 16/16 / 16/16 | 1/16 / 15/16 | 602 / 625 | Inv=0 |
| Wave2 relay | 1 | 750 | 16/16 | 16/16 | 1.805521/2.617994 | 16/16 / 16/16 | 1/16 / 11/16 | 540 / 562 | Inv=0 |

`N/S` 表示 v1 baseline 没有序列化 latch-based 指标。v1 baseline 的 dwell `0/0` 来自其构造性 reward wall：`near_closed=0.1` 时 `(0.1,0.25)` 内 `unlatch_hold` 不可能 active；v1 报告也记录该 band 为恒零墙签名。

## 5. Hinge dwell 直方图

计数来自所有 finite control-step trace；bins 精确为 `<0.02`、`0.02–0.08`、`0.08–0.105`、`0.105–0.25`、`≥0.25`。

| Wave | Seed | Step | <.02 | .02–.08 | .08–.105 | .105–.25 | ≥.25 | finite total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Wave1 | 0 | 250 | 6395 | 819 | 133 | 122 | 0 | 7469 |
| Wave1 | 0 | 500 | 6660 | 920 | 72 | 0 | 0 | 7652 |
| Wave1 | 0 | 750 | 2679 | 511 | 280 | 1997 | 2745 | 8212 |
| Wave1 | 1 | 250 | 6941 | 568 | 115 | 0 | 0 | 7624 |
| Wave1 | 1 | 500 | 5892 | 912 | 111 | 597 | 0 | 7512 |
| Wave1 | 1 | 750 | 3272 | 1885 | 288 | 1193 | 1659 | 8297 |
| Wave2 | 0 | 250 | 1755 | 596 | 90 | 737 | 5287 | 8465 |
| Wave2 | 0 | 500 | 1643 | 280 | 156 | 425 | 6063 | 8567 |
| Wave2 | 0 | 750 | 1065 | 265 | 86 | 454 | 6817 | 8687 |
| Wave2 | 1 | 250 | 2205 | 805 | 215 | 1809 | 3629 | 8663 |
| Wave2 | 1 | 500 | 1351 | 413 | 118 | 602 | 6754 | 9238 |
| Wave2 | 1 | 750 | 1059 | 444 | 112 | 540 | 7134 | 9289 |

Wave1 中 `.105–.25` band 已在两个 seed 脱离恒零；Wave2 则每个 checkpoint 都有该 band，同时 `≥.25` 成为主占据区。这是 wall-removal 假说最早、最直接且最终被 Stage4 DV 交叉确认的证据。

## 6. 完整性 invariant

| Invariant | Wave1 六格 | Wave2 六格 | 结果 |
|---|---:|---:|---|
| 假 E4 | 0 | 0 | PASS |
| 首次 Stage4 准入快照低于 hinge gate | 0 | 0 | PASS |
| `dont_push_door_handle` 在真实 Stage4 前激活 | 0 | 0 | PASS |
| `target_root_distance` 在 `aperture_ready` 前激活 | 0 | 0 | PASS |

Wave1 step750 的首次 Stage4 准入为 seed0 `10`、seed1 `6`；Wave2 六格依次为 `13、14、15、11、16、16`，所有准入快照均高于 `0.25 rad`。

第一次 Wave1 analyzer 把 Stage4 锁存后的门回摆 row 也逐步计入“低于 gate Stage4”，产生 `358/166` 的假 invariant failure。trace 时序证明 E4 在有效 crossing 的 stage3 row 出现，下一 row 进入 Stage4；后续 Stage4 可因门回摆低于 0.25。分析器修为“每 env 首次 Stage4 准入快照”后，在同一份不可变 eval 上重算为全零；producer、gate、训练和 eval 均无需重跑。

## 7. C1–C4、smoke 与运行闭环

1. C1：新增 v2 plan-id guard 和 base dispatch；v0/v1 路径未改。
2. C2：V2-W 从 v1-R fork，warm checkpoint 指向 v1-R seed0 step750；唯一 reward 改动为 `near_closed 0.1→0.25`。
3. C3：E3 使用标定后的 `latch≥0.02292371541261673 ∧ stable_contact`；handle/latch 双口径 stable-unlatch/relock 进入 terminal 与 step telemetry。E4 和 Stage3→4 物理 gate 不变。
4. C4：新增 path-bound U-probe、训练、全 checkpoint eval、orchestration、fail-closed analysis 和报告脚本，均位于 `scriptsFORhuman/pull_v2/`。

唯一 smoke 位于 `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_smoke_seed0/`，64 env × 50 batch，step50/last 均存在，resolved plan id 与 `near_closed=0.25` 生效。该 smoke 发生在 canonical deterministic U-probe 回填之前，因此 resolved latch threshold 是 sampled attempt 的 `0.02245621755719185`；smoke 的 acceptance 只要求训练路径和 `near_closed=0.25`，且 latch threshold 只影响 E3 telemetry，不影响 reward 或 Stage3→4 gate，故按“smoke 一次”纪律不重跑。Wave1/Wave2 formal resolved config 均使用 canonical `0.02292371541261673`。

Wave1 seed0 完整训练约 3h03m并产出 250/500/750；seed1 约 3h05m，进程自然消失且 checkpoints 完整，但 detached launch 没保留精确 OS exit code，故该 training exit 证据标记 INCONCLUSIVE、没有为了补 exit code 重训。六个 Wave1 eval 均 exit0。Wave2 seed0/seed1 均捕获 natural exit0，三个 checkpoint 完整；六个 Wave2 eval 均 exit0 且每格 16 terminal。

唯一一轮 code/IsaacLab review 找到并定向修复了 seed forwarding、E3 predicate、analyzer fail-closed/口径、U-probe fixture/GPU binding、Wave1 并发与 Wave2/G4 输出冲突。按用户规定没有第二轮 broad review；后续只对实际受影响路径做了 Hydra/static check、canonical U-probe、smoke、两轮训练/eval 和分析。

## 8. 自主预案日志

| Rule | Evidence | 决定 |
|---|---|---|
| G1 | Wave1 两 seed 均有 true S3→4；hinge Δ max `.749745/.492656` | 触发。选择 Wave1 seed0 step750 relay，执行 Wave2 双 seed。 |
| G2 | Wave1 已越过 0.25 且出现真实 Stage4，不是停在 `.105–.25` 的新平台 | 未触发。 |
| G3 | 两 seed 均显著改善 | 未触发；停止 A0，状态 `NOT_TRIGGERED`。 |
| G4 | 两 seed 结论同为 G1 | 未触发，不补 seed2。 |
| G5 | `theta*=0.6≤0.7` | 未触发。 |
| G6 | θ=0 时 hinge max `.001943<.05` | 未触发；canonical deterministic fixture 与咬合证据一致。 |
| G7 | U-probe 先暴露 import-order/teardown；训练未出现需重启的 traceback | 探针修根因；formal cell 无训练重启。 |
| G8 | GPU6/7 可用且 lease 不冲突 | 两轮都并行执行，无串行 fallback。 |
| G9 | 所有 formal cell <6h | 未触发；Wave2 没有被砍。 |

## 9. 交付物与下一步

- Source/config：v2 guard/dispatch、latch E3 telemetry、V2-W YAML、base threshold key。
- U-probe：`scriptsFORhuman/pull_v2/run_u_probe_unlatch_calibration.py` 与 canonical/invalid-attempt receipts。
- 编排：`run_pull_v2_training.py`、`run_pull_v2_eval_all_checkpoints.py`、`run_pull_v2_orchestration.py`、`analyze_pull_v2.py`。
- Analysis：`PULL_V2_ANALYSIS.json`（Wave1）与 `PULL_V2_WAVE2_ANALYSIS.json`（Wave2）。
- Training：`logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_{smoke_seed0,wave1_seed0,wave1_seed1,wave2_relay_seed0,wave2_relay_seed1}/`。
- Eval：`logs_eval/a2_piper_pull_v2/W_{wave1,wave2_relay}_seed{0,1}_step{250,500,750}/`。

Pull-v2 的 durable 结论是：`near_closed=0.1` reward wall 被拆后，原 v1-R actor 可以学习可靠的真实 Stage4 占据；下一 round 进入 traversal/V1-C 域，保留当前 latch 标定、单轴 reward 改动和四项 invariant，不再在 v2 内追加 reward seam。
