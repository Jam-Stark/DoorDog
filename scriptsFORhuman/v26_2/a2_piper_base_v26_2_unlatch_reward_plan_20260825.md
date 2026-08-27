# DoorDog A2+PiPER `base_v26-2` Unlatch Reward Experiment

**Owner decision:** 2026-08-25 03:20 HKT  
**Status:** SUPERSEDED at 2026-08-25 03:37 HKT; do not execute  
**Superseded by:** `a2_piper_base_v26_2_pull_derived_plan_20260825.md`  
**Parent:** `v26-1` acquisition supplement  
**Source candidate:** `CONT_STEP2000`  
**Scientific question:** 在不破坏 bilateral natural K5 grasp 的前提下，移除未受
真实抓握约束的 raw handle reward，是否能把 Stage3 credit 转向真实下压把手与解锁？

> Pull-v1/v2 的本机 source、resolved config 与 experiment evidence 证明：
> handle creation signal 是必要正向项，随后还要拆除 `near_closed=0.1` reward wall。
> 因此本文件原来的 raw-removal-only 假设不再是 v26-2 执行合同，仅保留为历史。

## 1. Historical outcome (superseded)

`v26-1` 已经解决“base 与门保持距离、arm reach、双侧 natural strict K5 grasp”；
当前失败点不是 close persistence，而是 Stage3 handle depression / unlatch。
`CONT_STEP2000` 的 natural Route A 为 LEFT `64/64`、RIGHT `61/64` 到 Stage3，
Stage3 contact stability 为 `0.9689/0.9666`，但 handle-joint max 仅
`0.0001305/0.036833 rad`、hinge max 仅 `0.002131/0.002110 rad`，所有 goal
为 0。

v26-2 采用一个 matched two-cell reward experiment：

| Cell | GPU | `push_door_handle` | `a2_stage3_unlatch_hold` | 作用 |
|---|---:|---:|---:|---|
| `V26_2_C0_RAW6_GATED3` | 0 | 6.0 | 3.0 | matched continuation control |
| `V26_2_T0_RAW0_GATED3` | 1 | 0.0 | 3.0 | 唯一 reward intervention |

T0 不是“把所有 Stage3 reward 调大”，而是删除可在未形成真实 K5 时支付、且能从
绝对 handle position 租金获利的 raw term，只保留现有 K5-conditioned、near-closed
的 unlatch credit。C0 与 T0 除这一 scale 外必须完全相同。

每个 cell 训练最多 `2000` iterations，checkpoint 每 `250` 保存。`1000` 是关键
判读点，不是预设收敛终点；不安排 `4000`，也不因 endpoint 晚于最佳 checkpoint
而继续加跑。

## 2. 为什么不是机械设成 1000

以下数字来自实际保存的训练日志，不是计划值：

| Run / iteration | avg stage | goal rate | Stage3 frac | Stage4 frac | handle p50 | hinge mean | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| v13_A / 1000 | 2.9322 | 0 | 0.3534 | 0 | 0.0003 | 0.0005 | 尚未机械突破 |
| v13_A / 1500 | 2.9011 | 0 | 0.3572 | 0 | 0.0003 | 0.0003 | 仅 handle p95 到 0.0367 |
| v13_A / 2000 | 3.2548 | 0 | 0.2867 | 0.1181 | 0.4655 | 0.0661 | 开始形成 unlatch / Stage4 |
| v13_A / 2500 | 3.9211 | 0 | 0.1552 | 0.6538 | 0.6477 | 0.5437 | 多数进入 Stage4 |
| v13.1 / 500 | 4.3669 | 0.3698 | 0.0922 | 0.5174 | 0.6374 | 0.7745 | 成熟 warm-start 很快恢复 goal |
| v13.1 / 1000 | 4.5097 | 0.5370 | 0.0882 | 0.4818 | 0.6557 | 0.9023 | 已明显收敛 |

v26-1 的训练态 Stage3 occupancy 在 1000 已到 LEFT/RIGHT
`0.4257/0.3378`，但同 checkpoint 的 natural Route A 只有 `1/64`、`0/64`
进入 Stage3；到 1500 为 `54/64`、`4/64`，2000 才到 `64/64`、`61/64`。
2500 又变为 `37/64`、`63/64`，说明更长训练并不单调改善双侧自然链路。

因此日志支持以下边界：

- 约 1000 iterations 常是成熟 continuation 的收敛/行为显现区间；
- 1000 不能替代 natural-start 验证，也不是所有 reward surgery 的终点；
- 2000 足以覆盖 v13_A 的首次机械突破与 v26-1 的双侧 natural acquisition；
- 保存 250 间隔并选择最佳 checkpoint，比固定使用最后一个 checkpoint 更重要。

原始证据：

- `logs_rl/a2_piper_full_stage_a2_base/base_v13_A_main-20260716_225345/.wandb/wandb/run-20260716_225404-n3r1hyzq/files/output.log`
- `logs_rl/a2_piper_full_stage_a2_base/base_v13_1_main-20260717_202500/.wandb/wandb/run-20260717_202518-mbsobrwn/files/output.log`
- `logs_eval/base_v26/acquisition_supplement_20260823/continuation_progress.json`
- `logs_eval/base_v26/acquisition_supplement_20260823/continuation_route_a_summary.json`

## 3. Reward hypothesis and execution binding

当前 raw term `push_door_handle` 在 Stage3 直接使用：

```text
handle_joint_velocity + normalized_absolute_handle_joint_position
```

它没有 K5 grasp gate。v26-1 连续 Stage3 trace 中，即使 handle joint 接近 0，
该项仍持续支付；这会允许 policy 从 contact/jitter/绝对位置获得 reward，而不必真正
下压把手。

保留的 `a2_stage3_unlatch_hold` 则是：

```text
(control-step streak >= 5)
× clamp(handle_position / 0.6, 0, 1)
× (hinge_position < 0.1)
```

它将 credit 绑定到真实 bilateral hold 与 near-closed unlatch 区间。历史 v13_A /
v13.1 的成功 reward bundle 也使用 `push_door_handle=0`、
`a2_stage3_unlatch_hold=3`、`a2_stage3_stage4_hold_and_drive=8`、
`push_door_hinge=6`。

首轮不把 `a2_stage3_unlatch_hold` 从 3 加到 6：当前 handle position 基本为 0，
单纯放大零信号不能先证明 credit routing；C0→T0 先隔离 raw reward rent。
若 T0 保留 K5 但到 2000 仍无真实 handle/hinge progress，v26-2 应以 negative
mechanism result 关闭，再单独设计 K5-conditioned positive-velocity / delta-position
reward，不在本轮中途改 scale 或代码。

## 4. Frozen load and rollout contract

两个 cell 都从同一 checkpoint 开始：

```text
logs_rl/by_batch/base_v26_acquisition_supplement_20260823/
continuation/V26A_LR_S1_POLICY800/model_step_002000.pt
```

共同配置：

- `checkpoint_load_mode: policy_only`；
- 显式 `policy_only_load_actor_rms: true`；
- actor MLP/std/LSTM 与 actor observation RMS 继承；critic、optimizer、scheduler、
  trainer global step、environment 与 staged-reset buffers fresh；
- `auto_load_latest: false`，两个 cell 使用不同的新 experiment directory；
- seed `1`、side permutation seed `1`；
- single process × 4096 env，bilateral exact `2048/2048`；
- 1 GPU/cell、`num_mini_batches: 4`、gripper `800/25`、PhysX velocity
  iterations `2`；
- `num_total_batches: 2000`、save frequency `250`。

这里选择继承 actor RMS，是为了从成熟 `CONT_STEP2000` 直接比较 reward credit，
避免重复 v26-1 fresh-RMS continuation 在前 1000 左右经历的 acquisition transient。
两 cell 的 load contract 完全匹配，因此不会把 RMS 差异归因成 reward 效果。

以下保持冻结：

- LEFT/RIGHT exact bilateral distribution 与 natural-start ranges；
- `0.68–0.72 m` staging、`0.02 m` forward-creep deadband；
- strict control-step K5、force/opposite-squeeze/window/over-force semantics；
- Stage2/3 close、contact 与 keep-close rewards；
- Stage3 base unlock、FULL posture/planar action topology、stage timers；
- `push_door_hinge=6`、`unlatch_hold=3`、`hold_and_drive=8`；
- R0 friction/load/handle-height、release/handoff 与 success semantics。

禁止同时启用 M7 forced-close、降低 K5、调整 arm effort/TCP/door physics、进入 R1
load、修改 stage transition 或引入 scripted action。

## 5. GPU and long-run allocation

正式训练只需要两张 GPU：

- GPU0：C0 control；
- GPU1：T0 treatment；
- GPU2–3：训练不需要，可保持空闲；训练完成后可用于并行 LEFT/RIGHT Route A。

按 v26 已观察到的约 `20.3 s/update`，2000 iterations 预计约 11 小时/cell；两格
并发时墙钟仍约 11 小时。必须各自在独立 tmux session 中运行，并落 run receipt；
使用 `.ai/scripts/run_supervisor.py` 的 prepare/launch/status/finalize 路径记录 exact
command、checkpoint lineage、GPU、输出、停止条件与 eval 状态。不要为了占满
GPU0–3 再添加无假设的 cells。

## 6. Minimal implementation and proof order

1. 新建共同 v26-2 continuation ablation 与 C0/T0 reward override；resolved config
   必须证明两 cell 只有 `push_door_handle` 一项不同。
2. 每 cell 做一次最小真实 Isaac Sim rollout/PPO-update/checkpoint smoke，确认
   policy-only load、`actor_rms_loaded=True`、reward scale 与 action/observation shape。
3. 正式以 4096 env 启动 C0/T0；formal startup 必须 fail-fast 验证 side count
   `2048/2048`、checkpoint 非空与输出目录不重用。
4. 保存 `250/500/750/1000/1250/1500/1750/2000`；训练途中不改 reward。
5. 对 `250/500/1000/1500/2000` 做每侧 64 episodes natural Route A。训练态
   staged occupancy 只用于诊断，不能用于 winner 或 handoff。
6. 对 1000、1500、2000 以及最终候选导出 Stage3 trace；给最终候选做 matched
   LEFT/RIGHT render。
7. 按所有 checkpoint 的 natural 结果选候选，不能默认选择 step2000。

## 7. Evidence and decision rules

每侧至少报告：

- Stage3+、Stage4、Stage5、goal episode counts；
- strict K5、negative close primitive、both-contact、opposite-squeeze、force-window、
  contact stability；
- per-episode handle-joint max 与达到 `0.1/0.6 rad` 的 counts；
- per-episode hinge max 与达到 `0.1/0.25 rad` 的 counts；其中 `0.25 rad` 是当前
  Stage3→4 threshold；
- Stage3-active 每 control step 的 raw-handle、unlatch-hold、hold-and-drive reward
  payout，避免只看累计 episode reward；
- timeout/termination 原因与 selected checkpoint 的视频行为。

不构造单一加权分数。先判断 acquisition 是否保留，再判断机械进展：

- **Retention fail**：T0 的 natural K5/Stage3 链路明显丢失且没有更强 mechanical
  progress；拒绝 T0。
- **No causal separation**：C0/T0 都改善或都不改善，且 bilateral handle/hinge
  counts 无稳定分离；不得把继续训练效果归因给 reward removal。
- **Mechanism positive**：T0 保留双侧 repeated K5，并在 LEFT/RIGHT 都重复出现
  hinge `>=0.1 rad`；这是 unlatch exploration 的正证据。
- **Stage4 positive**：T0 在 LEFT/RIGHT 都至少 2 个 natural episodes 达 Stage4
  (`hinge >= 0.25 rad`)；允许以最佳 checkpoint 继续 full-chain diagnosis。
- **Teacher gate**：只有双侧 repeated natural full goal 才能更新 Teacher/Student
  handoff 或进入 R1；Stage4 positive 不能替代 full-goal gate。

1000 checkpoint 用于回答“是否已经进入收敛/机械突破区间”；无论结果如何，不得在
同一个 run 中途改 reward。2000 是本轮硬停止点。若没有 causal/mechanism positive，
关闭 v26-2 并提交 trace-based next hypothesis，不自动扩到 3000/4000。

## 8. Expected artifacts

建议新路径：

```text
gr00t/rl/config/ablation/wbmanip/base_v26_2_*.yaml
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v26_2_*.yaml
scriptsFORhuman/v26_2/
logs_rl/by_batch/base_v26_2_unlatch_reward_20260825/{smoke,formal}/
logs_eval/base_v26_2/unlatch_reward_20260825/
```

最终必须落：resolved config、runtime log、run receipt、checkpoint census、natural
Route A summary、Stage3 mechanism trace、matched render、结论与 memory closure。
未发生 full goal 时不得生成 qualified Teacher manifest。
