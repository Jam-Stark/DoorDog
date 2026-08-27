# DoorDog A2+PiPER `base_v26` Acquisition Supplement

**Owner decision:** 2026-08-23 01:19 HKT  
**Status:** completed; no Teacher/Student handoff  
**Parent phase:** `base_v26`  
**Resolved phase name:** `v26-1`  
**Classification:** v26 增补任务，不创建 v27、不改变 Student binding  
**Successor plan:** `scriptsFORhuman/v26_2/a2_piper_base_v26_2_pull_derived_plan_20260825.md`

## 1. Outcome first

v26 的后续先恢复 scratch acquisition 的“站远后用 arm reach”课程，再处理成熟
抓握与完整开门链路。实施顺序固定为：

```text
0.70 m handle-relative stand-off acquisition
→ scratch gripper 80/3, velocity iterations 1
→ 双侧 natural-start 重复形成 strict control-step K=5 grasp
→ policy-only 切换 800/25, velocity iterations 2
→ 继续 v13/v13.1 unlatch / hold-and-drive / release / handoff
```

这条路线属于现有 v26 的 acquisition repair，不是新 experiment phase。增补已经
按本合同完成实现、真实 Isaac Sim smoke、四格 scratch、双侧 natural-start Route A、
policy-only actuator continuation 与最终机械定位。最终恢复了双侧 strict K5/Stage3
acquisition，但没有形成 Stage3 unlatch 或 full goal。

## 2. 为什么需要这个增补

### 2.1 v26 计划中的 `0.70 m` 没有进入实际配置

v26 R1 plan §5 写的是“Stage0 staging target 约位于把手前方 `0.70 m`”，但
`base_v26_common_scratch_lr.yaml` 没有显式覆盖 staging band。正式保存配置实际
继承 `door_open_a2_base.yaml`：

```yaml
a2_stage0_staging_x_min: 0.55
a2_stage0_staging_x_max: 0.60
a2_stage0_staging_y_tol: 0.15
```

LR S1 natural holdout 的 Stage0→1 standoff 中位数约为 `0.591 m`。进入 Stage2
后，现有 forward-creep penalty 只有在 root 穿过 `x_min - deadband = 0.50 m`
之后才开始收费；render 中 LEFT/RIGHT 又继续向门移动约 `13.2/10.9 cm`。因此
policy 可以主要依赖 base 缩短距离，而不必及早形成 arm reach。

### 2.2 Stage2 的直接失败是主动开合，不是偶发 contact noise

LR S1 render 的 Stage2 已到把手附近并多次形成 bilateral contact，但 policy 每
`2–3` 个 control steps 主动给出 open primitive，导致最长 strict grasp streak
LEFT/RIGHT 只有 `3/2`。这说明需要同时修复 scratch basin 与 close persistence，
不能通过把 `K=5` 降为 `K=2/3` 接受当前坏行为。

### 2.3 v26 错把 post-warm-start 的 `800/25` 当成 scratch-proven

历史正向链路实际是：

- v12_C scratch 使用固定 `0.70 m` staging、gripper `80/3`、PhysX velocity
  iterations `1`，形成当时最好的 Stage2 acquisition；加入 control-step `K=5`
  gate 后自然评估 `16/16` 进入 Stage3，首次通过约 `15–26` steps；
- v13_A 从 v12_C step3000 做 policy-only warm-start，随后才切换 `800/25`、
  velocity iterations `2`，并完成 full chain；
- v13_B 说明成熟行为在 `80/3` 下 retention margin 不足，但没有证明 scratch
  从 batch 0 使用 `800/25` 更容易发现 grasp。

所以 `800/25` 是成熟 acquisition 之后的 retention/full-chain capability，不是已
验证的 scratch discovery setting。

## 3. 增补任务的实现合同

### A. 恢复 scratch stand-off anchor

在 v26 scratch config 中显式写入以 `0.70 m` 为中心的窄 staging band。第一版
使用：

```yaml
a2_stage0_staging_x_min: 0.68
a2_stage0_staging_x_max: 0.72
a2_stage0_staging_y_tol: 0.15
```

当前 band API 允许 `x_min == x_max`，但 transition 使用区间 membership；把上下界
都写成 `0.70` 会要求浮点位置精确相等，不适合作为 rollout gate。因此使用窄 band
表达历史 fixed `0.70 m` anchor，而不是恢复已删除的 offset compatibility path。

保留现有 Stage0→1 arm-default 与 physical base-still gate。同步把 Stage1/2
forward-creep deadband 从 `0.05` 收紧到 `0.02 m`，使 policy 在进入 Stage1 后不能
无代价地继续靠 base 吞掉 arm reach 距离。此项只改变 stand-off economics，不锁死
FULL action topology，也不 scripted arm trajectory。

### B. Scratch actuator setting

从随机初始化开始时显式采用：

```text
arm_j7/j8 stiffness: 80
arm_j7/j8 damping: 3
effort: 10/10
PhysX velocity iterations: 1
```

保留 TCP source offset `0.085 m`。不要同时 sweep effort、TCP、handle height 或
door load；历史已表明这些变量一起变化会把 acquisition basin 的结论混在一起。

### C. Strict grasp 与 close persistence

- 保留 `a2_grasp_gate_mode: control_streak` 与 `K=5`；
- 保留 bilateral force、opposite squeeze、force window 与 over-force semantics；
- 保留现有 Stage2 dense tracking、close-gate open penalty 与 base-creep penalty；
- 首轮不强制 close，先判断 `0.70 m + 80/3` 是否恢复自然 arm reach / close；
- 若仍稳定复现每 `2–3` steps 主动 opening，才启用 v13 M7 提议的 close-gate-only
  forced-close curriculum `100–200` iterations，且在候选评估前移除。M7 是历史
  proposed lever，不得记录成已验证结论。

### D. Actuator continuation

只有在 LEFT 与 RIGHT natural-start 都重复出现真实 `K=5` grasp、而不是单帧
bilateral contact 后，才从最佳 acquisition checkpoint 做一次 policy-only continuation：

```text
80/3, velocity iterations 1
→ 800/25, velocity iterations 2
```

critic、optimizer、scheduler、RMS 与 staged-reset buffer 全部 fresh；只继承 actor
policy/LSTM。随后继续既有 v13/v13.1 Stage3 base unlock、unlatch-hold、
hold-and-drive、release latch 与 target-root handoff。

## 4. 保持冻结的边界

以下内容不因本增补改变：

- v26 LEFT/RIGHT exact distribution 与 privileged Teacher handedness slots；
- door-relative natural start `0.90–1.40 m / ±0.25 m / ±0.30 rad`；
- FULL posture、planar action channel、six-stage observation/action topology；
- R0 friction/load/handle-height contract；
- strict Stage2 success semantics；
- v13/v13.1 full-chain reward bridge；
- Student 继续绑定 RIGHT-only G7，直到新的 bilateral Teacher 真正 qualified。

不使用以下捷径：降低 `K=5`、恢复 history-3、直接 warm-start G7、把 six-stage
裁成 three-stage、扩大到 v15 mature-policy `[0.50, 0.80]` staging band、提前进入
R1 load、或用 side-scripted arm action。

## 5. 后续执行顺序与停止条件

1. 只实现 stand-off、creep deadband 与 scratch actuator 三项显式 config；不先改
   reward function 或 state machine。
2. 做一次最小 LEFT/RIGHT runtime smoke，确认 Stage0→1 standoff 聚集在
   `0.68–0.72 m`、base-still gate 生效、真实 action/observation shape 不变。
3. 运行 scratch acquisition，并用 natural-start checkpoint eval 判断 arm reach、
   close ratio、bilateral contact 与 strict streak；staged-reset Stage3 occupancy 不能
   代替这一证据。
4. 双侧 natural `K=5` acquisition 成立后才做 `800/25` policy-only continuation。
5. 未出现双侧 repeated natural grasp 前不进入 R1；未出现双侧 repeated natural
   goal 前不更新 Teacher/Student handoff。

若 `0.70 m + 80/3` 仍不能恢复 arm reach，本增补停在 acquisition diagnosis，下一
个单因素才是 close persistence curriculum；不得一轮同时加入更多 physics/reward
变化。

## 6. Evidence routes

- v26 saved config:
  `logs_rl/by_batch/base_v26_r0_20260821/V26_LR_S1/config.yaml`
- v26 render traces:
  `logs_eval/base_v26/render_20260822/LR_S1_STEP4000_RENDER/{left,right}/stage2_step_trace.json`
- v12 positive scratch config:
  `logs_rl/a2_piper_full_stage_a2_base/base_v12_C_v10A_scratch_stability1-20260716_004404/config.yaml`
- early v0–v9 retrospective:
  `scriptsFORhuman/v0_to_v11/a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md`
- v13 acquisition/full-chain plan:
  `scriptsFORhuman/v13/a2_piper_base_v13_optimization_plan_20260716.md`
- v15 staging correction:
  `scriptsFORhuman/v15/a2_piper_base_v15_optimization_plan_20260720.md`

## 7. Execution closure

### 7.1 Scratch acquisition

- LEFT/RIGHT 1-env smoke 均完成真实 rollout、PPO update 与 checkpoint；
- 64-env bilateral 10-batch smoke side count 精确 `32/32`，Stage0→1 standoff
  `p50=0.7091 m`、`p95=0.7132 m`；
- LR S0、LR S1、LEFT S0、RIGHT S0 四格均以 4096 env 完成 4000/4000 batches、
  natural exit0 与 run-receipt PASS；每格 1,048,576,000 timesteps；
- 17 checkpoints × 64 LEFT + 64 RIGHT 的 Route A 共 2,176 natural episodes。
  `LR_S1_STEP3000` 是唯一双侧 repeated-K5 acquisition leader：LEFT `3/64`、
  RIGHT `2/64` 到 Stage3；全矩阵 goal 为 0。

因此准入 policy-only actuator continuation；因为 natural K5 已恢复，M7
forced-close 未启用；因为 full goal 为 0，R1 未准入。

### 7.2 Policy-only continuation

continuation 从 `LR_S1_STEP3000` 只继承 actor MLP/std/LSTM，显式使用
`policy_only_load_actor_rms: false`，使 actor RMS、critic、optimizer、
scheduler、trainer state、environment 与 staged-reset buffers 全部 fresh。
64-env smoke 记录 `actor_rms_loaded=False` 并完成更新。

正式 continuation 保留一进程 × 4096 env 的 proven v26 topology，采用
`800/25`、velocity iterations 2，完成 3000/3000 batches、exit0 与
786,432,000 timesteps。七个 checkpoint 的 896 个 natural episodes 中，
`CONT_STEP2000` 最平衡：LEFT `64/64`、RIGHT `61/64` 到 Stage3，但双侧
goal 均为 0。

### 7.3 Final localization and handoff

`CONT_STEP2000` 的 Stage3 trace 中 close primitive、bilateral contact 和
squeeze window 都已保持，contact stability 为 LEFT `0.9689` / RIGHT
`0.9666`；但 handle-joint max 仅 LEFT `0.0001305 rad` / RIGHT
`0.036833 rad`，hinge max 仅 `0.002131/0.002110 rad`，Stage3 episodes
全部 overtime。

最终 typed boundary 是
`V26_ACQUISITION_RECOVERED_STAGE3_UNLATCH_EXPLORATION_BLOCKED`。增补闭环，
但 R1、Teacher handoff 与 Student rebinding 均不准入；现有 RIGHT-only G7
Student binding 保持不变。

执行证据：

- scratch formal:
  `logs_rl/by_batch/base_v26_acquisition_supplement_20260823/formal/`
- scratch Route A:
  `logs_eval/base_v26/acquisition_supplement_20260823/route_a_summary.json`
- formal continuation:
  `logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/`
- continuation Route A:
  `logs_eval/base_v26/acquisition_supplement_20260823/continuation_route_a_summary.json`
