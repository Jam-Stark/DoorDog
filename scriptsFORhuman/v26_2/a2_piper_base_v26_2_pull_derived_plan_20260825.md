# DoorDog A2+PiPER `base_v26-2` Pull-derived Unlock Creation Plan

**Owner input:** 2026-08-25 03:37 HKT  
**Status:** planned; not implemented or run  
**Parent:** completed `v26-1` acquisition supplement  
**Source actor:** `CONT_STEP2000`  
**Replaces:** raw-handle-removal-only v26-2 plan  

## 1. Outcome first

Pull-v1/v2 的本机完整证据改变了 v26-2 的优先假设。v26-2 不再首测
`push_door_handle: 6→0`；它复现 pull 实际形成 unlock 能力的两步因果链：

```text
A → R：在稳定抓握后增加 handle angle/velocity creation signal，scale 0 → 6
R → W：保持 scale6，仅把 unlatch near-closed 0.1 → 0.25
```

当前 push 实现不能直接视为 pull-R：pull 的 `pull_door_handle` 虽然也是
`handle_velocity + normalized_handle_position`，但还乘了 tensile-capture /
load-bearing mask；当前 `push_door_handle` 在 Stage3 没有 grasp/load-bearing gate。
因此 v26-2 新增 push 专用、strict K5-gated 的 handle-depression creation term，
并关闭同 cell 中的 ungated raw term，避免两份 scale6 叠加。

v26-2 不是随机 actor scratch。实际 pull lineage 是：

```text
base_v20_R3_G4 step2500
→ policy-only pull-v0 P4 step2500
→ policy-only pull-v1-R step750
→ policy-only pull-v2-W Wave1 step750
→ policy-only Wave2 relay step750
```

v26-1 scratch 的 bilateral natural acquisition 在 step1000/2000 仍不足，直到
step3000 才重复出现双侧 Stage3。若在 1000–1500 预算下随机初始化，Stage3 reward
很可能没有足够 natural denominator。v26-2 因此从已经具备 LEFT/RIGHT Stage3
能力的 `CONT_STEP2000` 继承 actor/LSTM/RMS，同时重建 critic、optimizer、scheduler、
trainer 与 environment；这与 pull 的实际 policy-only 路线一致。

## 2. Pull evidence verified on this machine

### 2.1 v1-R created handle depression

Pull-v1 A/B 与 R 使用同一 warm actor、256 env、750 batches；R 相对 B 的关键
reward 差异是 `pull_door_handle: 0→6`。实际 16-episode eval：

| Cell | seed/step | stable unlatch | handle max | valid-hold hinge Δ max |
|---|---|---:|---:|---:|
| v1-A/B | 两 seed / 全 checkpoint | 基本 `0/16` | 多为噪声/孤立 excursion | `≤0.002201` |
| v1-R | seed0 / 500 | `15/16` | `0.785398` | `0.026866` |
| v1-R | seed0 / 750 | `13/16` | `0.785398` | `0.100607` |
| v1-R | seed1 / 750 | `2/16` | `0.700337` | `0.002172` |

结论边界：handle creation signal 在 pull task 中具有真实行为效应，但 v1-R 尚未
稳定越过 0.25 rad Stage3→4 gate，而且存在 seed sensitivity。

### 2.2 v2-W removed the 0.1→0.25 reward wall

Pull-v2-W 相对 v1-R 的唯一 reward-seam 改动是：

```yaml
a2_stage3_unlatch_near_closed_hinge_threshold: 0.1 -> 0.25
```

Wave1 step750 true Stage3→4 为 seed0 `10/16`、seed1 `6/16`；从最佳 Wave1
checkpoint relay 后，Wave2 seed0 的 step250/500/750 为 `13/16,14/16,15/16`，
seed1 为 `11/16,16/16,16/16`。`0.105–0.25` hinge band 中的
`unlatch_hold` active steps 从 v1 构造性的 0 变成 Wave1 seed0/seed1 step750 的
`1643/1046`，与真实 Stage4 crossing 同时成立。

这证明 threshold 变化在 pull lineage 中拆除了 reward wall；不证明 pull 的
gripper `45 N`、`1300/32` actuator、hook/friction 或 tensile action geometry 能无条件
外推到当前 push v26。

### 2.3 Source-semantic difference

Pull 当前执行函数：

```text
(handle_velocity + normalized_handle_position).clamp(-1, 1)
× (E2 tensile capture reached
   and capture valid
   and control proof active/valid)
```

Current push raw function只有第一行，没有 K5/load-bearing mask。两者 nominal scale
都是 6，不代表 credit routing 等价。这也是 v26-2 必须新增 gated term、而不是只
保留现有 `push_door_handle=6` 的原因。

原始证据：

- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v1/PULL_V1_ROUND_REPORT.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v2/PULL_V2_ROUND_REPORT.md`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v2/PULL_V2_ANALYSIS.json`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/scriptsFORhuman/pull_v2/PULL_V2_WAVE2_ANALYSIS.json`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_pull.py`
- `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_wave1_seed1/config.yaml`

## 3. Minimal push-side implementation

新增一个 v26-2 reward term，建议名称：

```text
a2_stage3_handle_depression
```

其 Stage3 raw semantics 固定为：

```text
handle_signal = clamp(
    handle_joint_velocity
    + clamp(handle_joint_position, 0, 0.785398) / 0.785398,
    -1,
    1,
)

reward = handle_signal × (current control-step grasp streak >= 5)
```

约束：

- 只在 Stage3 执行；Stage3→4 threshold 本身是 `0.25 rad`，因此不会越过 release
  后继续支付；
- mask 必须复用当前 strict control-step K5 的 runtime tensor，不新增 history 或
  瞬时 contact shortcut；
- raw/scaled component、active-step count、per-active-step income 必须进入现有
  reward/trace telemetry；
- v26-2 treatment 中 `push_door_handle=0`，不与新 term 重复；
- `a2_stage3_unlatch_hold=3` 继续使用现有 K5 × handle position × near-closed；
- 不改 `push_door_hinge=6`、`hold_and_drive=8` 或 success/state semantics。

不要把 pull-only E2 tensile proof、hook、latch-event graph 整体移植到 push task；
push 已有 strict K5 与 bilateral force/squeeze predicate，v26-2 只移植 reward creation
principle 和 wall removal。

## 4. Wave1 four-cell matched matrix

四格都从同一 checkpoint、同一 seed、同一 rollout topology 开始：

```text
logs_rl/by_batch/base_v26_acquisition_supplement_20260823/
continuation/V26A_LR_S1_POLICY800/model_step_002000.pt
```

| Cell / GPU | raw `push_door_handle` | gated depression | near-closed | 对比含义 |
|---|---:|---:|---:|---|
| `V26_2_C_RAW6_T010` / GPU0 | 6 | 0 | 0.1 | 当前 v26 semantics control |
| `V26_2_A_RAW0_DEP0_T010` / GPU1 | 0 | 0 | 0.1 | pull v1-B analog，无 handle creation |
| `V26_2_R_RAW0_DEP6_T010` / GPU2 | 0 | 6 | 0.1 | A→R 隔离 gated handle creation |
| `V26_2_W_RAW0_DEP6_T025` / GPU3 | 0 | 6 | 0.25 | R→W 隔离 reward-wall removal |

共同 contract：

- `checkpoint_load_mode: policy_only`；显式
  `policy_only_load_actor_rms: true`；
- actor MLP/std/LSTM/RMS inherited；critic、optimizer、scheduler、trainer step、
  environment/staged-reset buffers fresh；
- seed `1`、side permutation seed `1`；
- single process × 4096 env/cell，bilateral exact `2048/2048`；
- `800/25`、PhysX velocity iterations 2、4 mini-batches；
- Wave1 `750` batches，save `250`；checkpoint 250/500/750；
- GPU0–3 四格并发，各自独立 tmux、output root 与 run receipt。

三个合法的 matched readout：

1. `A→R`：gated handle creation 是否创造稳定下压；
2. `R→W`：0.25 是否让已形成的下压继续传递到 hinge/Stage4；
3. `C↔R`：同为 nominal scale6，ungated current raw 与 K5-gated creation 的行为和
   income routing 是否不同。

不得把 `A→W` 当成单因素因果结论，因为它同时改变 creation signal 和 threshold。

## 5. Frozen v26-1 capability

除表中两项 reward/threshold 外保持 `CONT_STEP2000` resolved behavior：

- bilateral LEFT/RIGHT、natural-start ranges、R0 door distribution；
- `0.68–0.72 m` staging 与 `0.02 m` creep deadband；
- Stage0–2 reach/grasp reward scales；
- strict control-step K5、bilateral contact/opposite squeeze/force window；
- Stage2/3 close、keep-close/contact scales；
- Stage3 base unlock、FULL posture/planar action topology、stage timers；
- handle norm `0.6`、Stage3→4 hinge threshold `0.25`；
- hinge6、unlatch3、hold-and-drive8、release/handoff 与 goal semantics；
- `800/25` actuator 与 v26 R0 friction/load/height。

不改 gripper effort、arm gains、TCP、door mass/friction、stage transition、K5、
forced-close、staged-reset ratios 或 Student binding。

## 6. Wave1 evaluation and admission

每个 checkpoint 对 LEFT/RIGHT 各跑 64 natural episodes；训练态 staged reset 仅诊断。
每侧必须报告：

- Stage3+/Stage4/Stage5/goal counts；
- K5、negative close、bilateral/opposite/window/stability；
- stable handle `>=0.3`、handle `>=0.6` 的 episode counts；
- hinge max `>=0.1`、`>=0.25` 的 episode counts；
- hinge `(0.1,0.25)` dwell steps，以及其中 `unlatch_hold` active steps；
- raw/scaled handle-depression income与 active-step mean；
- timeout/termination 与 integrity violations。

Wave2 relay admission：

- W 保留 bilateral acquisition：每侧至少 `32/64` natural Stage3+；并且
- W 在每侧至少 2 episodes 达真实 Stage4 (`hinge>=0.25`)，或每侧至少 2 episodes
  同时具备 stable handle `>=0.6` 与 hinge `>=0.1`；并且
- 四项 integrity 为 0，W 的正信号不能只来自 staged snapshots。

若 R 有 handle creation、W 又显著增加 `(0.1,0.25)` active dwell / Stage4，分别记录
A→R 和 R→W 为 supported。若 C 与 R 都改善但无分离，只能证明 scale6 有效，不能
宣称 gating 更优。

## 7. Conditional Wave2 relay

只有 W 通过 admission 才执行：从最佳 W checkpoint policy-only relay 两格，仍保留
actor RMS：

| Cell | GPU | seed | batches |
|---|---:|---:|---:|
| `V26_2_W_RELAY_S0` | 0 | 0 | 750 |
| `V26_2_W_RELAY_S1` | 1 | 1 | 750 |

GPU2–3 可并行跑两侧 eval。relay checkpoint 仍保存 250/500/750；每格每侧 64
natural episodes。最长单条 lineage 是 Wave1 750 + relay 750 = `1500` batches；
禁止自动扩展到 2000/3000/4000。

稳定 unlock 的强证据是 selected relay checkpoint 在 LEFT/RIGHT 都有多数 natural
episodes 达真实 Stage4，目标至少 `48/64` 每侧，同时 K5/contact integrity 保持。
双侧 repeated Stage4 只准入 full-chain diagnosis；只有双侧 repeated natural goal
才能进入 R1 或更新 Teacher/Student handoff。

## 8. Stop and typed outcomes

- W 未保留 bilateral Stage3：`NOT_ADMITTED_ACQUISITION_REGRESSION`，不 relay。
- R 未创造 repeated handle depression：`HANDLE_CREATION_NOT_SUPPORTED`。
- R 有 handle、W 未增加 hinge band/Stage4：`WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH`。
- W Wave1 positive、relay 双 seed 不稳定：`SUPPORTED_BUT_SEED_UNSTABLE`。
- relay 双 seed、双侧 natural Stage4 稳定：`V26_2_UNLOCK_CAPABILITY_PASS`。
- goal 仍为 0：unlock PASS 也不能称 Teacher qualified。

到上述 stop 后关闭 v26-2，不在同一阶段追加 actuator/physics/reward sweep。

## 9. Execution order and resources

1. 静态 trace current/pull reward path并实现最小 gated term/telemetry。
2. 复用 pull-v2 U-probe fixture 对当前 door asset 做一次确定性 latch calibration；只确认
   handle norm≈0.6 与 hinge noise，不由 probe 选择训练 winner。
3. Hydra/resolved-config diff：A→R 只有 gated scale，R→W 只有 threshold。
4. 一次 64-env W smoke，真实 rollout/PPO update/checkpoint；对 C/A/R 用同一
   construction guard / component probe，不重复四次长 smoke。
5. GPU0–3 并发 Wave1 750；使用 `.ai/scripts/run_supervisor.py` 与独立 tmux/receipt。
6. 全 checkpoint bilateral natural eval、trace/analysis；按 admission 决定是否 relay。
7. 若 relay，GPU0–1 两 seed 750，GPU2–3 eval；否则直接 negative close。
8. selected candidate 做 matched LEFT/RIGHT render，更新 plan closure 和 memory。

Wave1 按 v26 约 `20.3 s/update` 预计约 4.2 小时墙钟；conditional relay 另约
4.2 小时。初始 Wave1 需要 GPU0–3；relay training 只需 GPU0–1。

## 10. Execution closure — 2026-08-25 10:54 HKT

完整执行证据与失败归档见
`a2_piper_base_v26_2_execution_closure_20260825.md`。

- exact `CONT_STEP2000` policy-only + actor RMS lineage、C/A/R/W resolved matrix、
  current-asset U-probe 与 64-env W smoke 均完成；
- C/A/R/W Wave1 均完成 750/750、exit0、receipt PASS，250/500/750 checkpoints
  齐全；
- 24/24 个 checkpoint-side bilateral natural Route A 均完成 exact64 episodes，
  expanded trace 与 terminal telemetry 对账通过，四项 integrity 全为 0；
- W_STEP0750 保留 bilateral Stage3：LEFT `32/64`、RIGHT `36/64`，但两侧
  Stage4、stable handle>=0.6∧hinge>=0.1 均为 0；
- A→R 为 `HANDLE_CREATION_NOT_SUPPORTED`；R→W 为
  `WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH`；A→W 未作单因素结论；
- W 未通过第二 admission gate，`relay_allowed=false`，conditional relay 按合同
  未执行；本阶段 typed stop 为 `HANDLE_CREATION_NOT_SUPPORTED`；
- selected `W_STEP0750` matched LEFT/RIGHT natural render 已完成，两个 episode
  都停在 Stage2、无 goal；
- 无 repeated bilateral natural goal，Teacher/Student handoff 与 binding 不变。

阶段状态更新为 `v26_2_complete_not_admitted`。不在本阶段追加 actuator/physics/
reward sweep、forced-close、K5 relaxation、R1 或更长 lineage。
