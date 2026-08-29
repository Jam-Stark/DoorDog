# DoorDog A2+PiPER `base_v26-3` Event-time Creation Plan

**日期：** 2026-08-27 19:26 HKT  
**状态：** `OWNER_APPROVED_FOR_AUTONOMOUS_EXECUTION`；本文件落盘时尚未实现或运行  
**父阶段：** `v26-2_complete_not_admitted`  
**主仓 source lock：** `Jam-Stark/DoorDog` / `A2_Piper` / commit
`e6310042348d24fbe8bb8bdc6ecd70e226fc3e32`  
**Pull 对照：** `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0` / branch
`codex/a2-piper-pull-v0-20260803` / commit
`5a31f1acc5528c5697abc357fe8b2a861a692fdd`  
**Cloud review：**
`scriptsFORhuman/pro_reviews/20260827-162429-HKT__e6310042348d/e6310042348d/FULL_REVIEW.md`  
**获批资源：** physical GPU0–3；Worker 自主排程，Owner 将离线  

## 1. Outcome first

v26-3 不是继续扫 `near_closed 0.1→0.25`，也不是把 pull 的 45 N、hook、friction
或 tensile proof 搬进 push。它先修复 v26-2 已由本地日志直接证明的 credit defect：

```text
Stage3∧K5 中旧 handle_vel + handle_pos reward 获得大量收入
但 episode handle high-water 仍接近零
=> velocity credit 不等于 durable handle state creation
```

v26-3 的主因果问题是：

> 用 control-interval monotone handle high-water increment 替换可被往返运动获利的
> endpoint-velocity credit，能否在同一 bilateral-natural lineage 中创建并保持真实
> handle depression？

主训练矩阵正好使用四张卡：

| GPU | Cell | seed | Stage3 credit | near-closed |
|---:|---|---:|---|---:|
| 0 | `V26_3_M0_OLD_S0` | 0 | 旧 velocity+position，scale6 | 0.1 |
| 1 | `V26_3_M0_OLD_S1` | 1 | 旧 velocity+position，scale6 | 0.1 |
| 2 | `V26_3_M1_CREATE_S0` | 0 | monotone high-water creation，scale6 | 0.1 |
| 3 | `V26_3_M1_CREATE_S1` | 1 | monotone high-water creation，scale6 | 0.1 |

四格都从 `CONT_STEP2000` 以 policy-only + actor RMS 加载，critic、optimizer、
scheduler、trainer state、environment 和 staged-reset state fresh。每格 4096 env、
bilateral exact 2048/2048、750 batches，save 125/250/500/750。M0→M1 只改变 Stage3
credit semantics；wall、actuator、K5、stage machine、physics 和 PPO 都冻结。

若 M1 创建真实 handle state并暴露旧0.1 cliff，才进入wall-removal；若M1清除alias但
仍无creation，只有在axis-work信号可识别时才进入push-specific load-bearing。其余情况
按typed outcome关闭v26-3，不无界扫参。

## 2. 本地消化 Cloud Pro 的裁决

### 2.1 直接采用

- selected render 的 Stage2 问题与 population Stage3 问题分层处理；前者是
  `GRIPPER_MODE_LIMIT_CYCLE_AT_K5_EDGE`，后者是
  `STAGE3_CONTACT_RETENTION_WITHOUT_HANDLE_CREATION`。
- 保留 E1 Stage2 close-gate-only 和 E2 Stage3/4 forced-close 两个 eval-only
  counterfactual；它们是机制诊断，不自动变成部署 controller。
- creation 与 retention 分开：新 reward 只支付 monotone high-water increment；现有
  `a2_stage3_unlatch_hold` 继续承担 retention。
- 先获得 creation，再讨论 0.1 wall；wall 未被访问时写
  `WALL_REMOVAL_NOT_REACHED`。
- effort、contact moment/work、substep alias 都作为本地条件诊断，不从 force norm
  或 nominal limit 直接作物理结论。
- 保留 event-time anti-alias credit、causal mechanism trace 和 bilateral canonical
  load-bearing representation 作为本阶段 research insight。

### 2.2 按本地 source/runtime 修改

- 当前 evaluator 实际把 deterministic `policy_model.action_mean` 送入 A2 action
  路径；`rollout()` 的 sampled action 不用于最终 A2 plant action。因此拒绝
  “sampling-induced flip” 作为当前解释，只追踪 mean、mapped mode、override 后 action
  和可选的 LSTM state summary。
- reward registry 会把非零 scale 乘 control `dt`。新 creation raw 必须为：

  ```text
  relu(highwater_t - highwater_{t-1}) / (0.785398 * control_dt)
  ```

  这样 `raw × scale6 × dt` 的 episode sum 才等于 `6 × normalized creation`。
  Cloud 文档中的裸 `normalized Δhighwater` 不能原样进入当前 registry。
- 当前详细诊断已经能给出 contact average position、friction/normal force、finger axes、
  joint target/position/velocity、gain/effort limit、PD saturation 和 computed/applied effort
  estimates。v26-3 复用它，不重写一套大 telemetry。
- 当前 runtime 明确不能读取真实 implicit-drive force；computed/applied effort 是 estimate。
  F ladder 的正负结论只能使用 config/readback、estimate、tracking/contact 和 state effect，
  不能写成 actual PhysX torque proof。
- effort ladder 先以 16 natural episodes/side 做 capacity diagnosis，出现方向一致的
  state effect 才扩为 exact64；不把 Cloud 的 64/rung 自动升级为本地硬预算。
- 不用 Cloud 建议的 0.03 rad 作硬 creation gate。阈值由本阶段 D0 与当前 fixture 的
  local noise/baseline ceiling 在看到训练结果前冻结。

### 2.3 拒绝自动执行

- 不直接改到 45 N 或 `1300/32`；不把硬件额定夹力映射成仿真单关节 effort limit。
- 不复制 pull-only E2 tensile mask、hook/friction、panel-clear event graph。
- 不在 creation 前启动 `near_closed=0.25`。
- 不把 E1 forced-close 当作最终 policy capability 或 natural evaluation。
- 不自动运行历史 v13.1 L0；较新的 v25 G7 已证明当前 fixture RIGHT goal、LEFT fail，
  L0 只有在新证据冲突时才是 lineage diagnosis。
- 不因 Stage4/unlock 更新 Teacher/Student binding；必须有 repeated bilateral-natural
  full goals。

## 3. 已冻结的本地事实与纠正后的 v26-2 终态

- v26-2 W750 natural exact64/side：LEFT Stage3 `32/64`、RIGHT `36/64`；Stage4、
  goal、handle>=0.3、hinge>=0.1 全为 0。
- Stage3∧K5 steps LEFT/RIGHT 为 `3782/4343`；旧 depression raw income 为
  `1903.10/1380.64`，integrity violations 为 0。
- Stage3 episode handle high-water median接近零，max LEFT/RIGHT 仅约
  `0.000164/0.002868 rad`。因此 durable label 为
  `HANDLE_VELOCITY_CREDIT_WITHOUT_STATE_CREATION`。
- R/W metrics 完全相同且 hinge 从未到 0.1；历史文本中的
  `WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH` 在 v26-3 语境中纠正为
  `WALL_REMOVAL_NOT_REACHED`。这是一项科学解释修正，不改写原始 artifacts。
- selected W750 render 的 gate 基本持续为 true，deterministic actor mean 反复发
  full-close/full-open；contact run 最长 4/3 control steps，K5=0。门本体没有反复开合。
- 当前 asset U-probe 在 handle 0.5/0.6 rad 时产生 hinge 约 0.0478/0.1443 rad；
  `STATIC_FIXTURE_LOCK_NOT_SUPPORTED`。
- single-RIGHT 与 pull 的正历史都遵循 creation→wall/handoff 顺序，但它们是不同
  lineage/geometry，不构成当前 bilateral push 的单因素证明。

## 4. Scope

### 4.1 本阶段必须完成

1. 新 creation state/reward/telemetry 与 staged-reset binding。
2. E1 close-gate-only evaluator selector；复用现有 E2 Stage3/4 forced-close。
3. focused source tests、Hydra/resolved matrix proof、真实 Isaac runtime smoke。
4. D0/E1/E2/D3 四卡 diagnostic wave。
5. M0/M1 × seed0/1 四卡 750-batch main wave。
6. 所有 main checkpoints 的 LEFT/RIGHT exact64 natural Route A 与 mechanism analysis。
7. 按证据自动决定是否执行 F、P 或 W conditional wave，并完整评估实际执行的分支。
8. selected natural render、source/config/checkpoint provenance、typed closure、memory 更新。
9. 只有达到本文件 Teacher 条件时才更新 handoff manifest；否则明确保持 G7 binding。

### 4.2 不做

- 不训练 A2_Base low-level locomotion；不改 12D high-level action topology。
- 不降低 strict control-step K5，不改 Stage3→4 0.25 transition。
- 不把 Stage2 forced-close intervention混入 M0/M1 main causal seam。
- 不同时改 actuator、reward、wall、friction、TCP、door mass 或 staged-reset ratios。
- 不做 R1 load mixture、Student training、GRPO、hardware run。
- 不创建兼容旧 v26-2 telemetry 的 fallback；v26-3 使用清晰的新 schema。
- 不 commit/push；除非 Owner 之后在当前任务中另行明确授权。

## 5. Frozen common lineage

Source actor：

```text
logs_rl/by_batch/base_v26_acquisition_supplement_20260823/
continuation/V26A_LR_S1_POLICY800/model_step_002000.pt
```

Main M0/M1 common contract：

- `checkpoint_load_mode: policy_only`；`policy_only_load_actor_rms: true`；
- inherited：actor MLP/std/LSTM/actor observation RMS；
- fresh：critic、optimizer、scheduler、trainer step、environment、history、staged snapshots；
- seed/side-permutation seed分别为 0/0 与 1/1；
- 4096 env，bilateral exact 2048/2048；
- `800/25`，PhysX velocity iterations2，4 mini-batches；
- 750 batches；checkpoint 125/250/500/750；
- `near_closed=0.1`、handle norm0.6、Stage3→4 hinge0.25；
- v26 R0 door distribution、K5、stage rewards、planar/posture topology均不变；
- actuator effort默认保持当前 resolved 10/10。只有 §10 F ladder先形成可解释证据，
  才能在 M0/M1 启动前把四格共同冻结到最小有效 tested cap；不得训练中途改变。

## 6. Source implementation contract

### 6.1 新 reward term

新增独立 term，建议名称：

```text
a2_stage3_handle_creation
```

旧 `a2_stage3_handle_depression` 保留原语义，只供 M0 与旧 evidence 对照。M1 中旧
term scale0，新 term scale6。不要就地改旧函数，否则 M0→M1 不再是可复核因素。

每个 control step 在 physics refresh 之后、reward 和 stage advance之前只更新一次：

```text
pos_t = clamp(handle_joint_position, 0, 0.785398)
highwater_t = max(highwater_prev, pos_t)
delta_highwater = relu(highwater_t - highwater_prev)
active = (pre-advance stage == Stage3) and current authoritative strict K5
creation_raw = delta_highwater / (0.785398 * control_dt) * active
```

约束：

- high-water 在所有 stage 都推进，防止 Stage3 entry 对已经存在的角度追溯支付；
- reward helper只读取本步 cache，不能再次推进 state；telemetry也只读同一 cache；
- raw不得 clip 成会破坏 creation integral 的固定上限；若 runtime 暴露异常量级，
  直接 fail fast定位 timebase/source，而不是 silent clipping；
- `scaled = raw × configured_scale × control_dt`；
- `creation_reward_nonzero_without_positive_highwater_delta == 0`；
- active 仅 Stage3∧current strict K5，Stage4/release 后不支付；
- M0/M1 的 `a2_stage3_unlatch_hold`、hinge/hold-and-drive reward不变。

### 6.2 Reset 与 staged reset

创建并注册至少以下 device-local per-env state：

```text
handle_pos_prev_control
handle_highwater
handle_highwater_prev
handle_delta_net
handle_delta_highwater
creation_raw_cached
creation_active_cached
```

- natural episode reset按 reset 后真实 articulation position初始化，首控制步不得产生
  reset-spike income；
- 使用现有 `StagedTaskBase._register_buffer_to_track` 进入 snapshot store/load；
- snapshot恢复必须让 physical handle state、prev/highwater 和第一步 derivative一致；
- restore 后首步若没有新 high-water，creation income必须为0；
- source test与真实 staged-reset smoke都要覆盖，不假设普通 tensor 自动被 snapshot。

### 6.3 v26-3 telemetry

Population terminal/scalar必须包含：

- stage3/4/5/goal、termination reason、natural/staged source；
- K5/bilateral/opposite/window/stability steps；
- handle/hinge max、handle terminal、high-water max；
- local-noise threshold crossings和连续保持步数；
- old depression raw/scaled income；creation raw/scaled income；active steps；
- `delta_pos/control_dt` 与 endpoint velocity 的 episode discrepancy summary；
- hinge 0.08–0.105、0.105–0.25 dwell与unlatch active；
- creation integrity counters、timeout与reset-spike counters。

Expanded step trace只用于 selected env/diagnostic，至少含：

```text
handle_pos_prev/current
handle_velocity_endpoint
handle_delta_net
handle_delta_net/control_dt
highwater_prev/current/delta
old_depression_raw
creation_raw/scaled/active
strict_k5/stage/hinge
policy_action_mean_gripper
mapped_gripper_mode/target
post_forced_override_gripper
episode_index/first_episode_active
```

只有 control-step trace仍无法区分 endpoint alias/弹簧回弹时，才对 1 env/side 添加
physics-substep handle min/max；不把 substep trace扩到64/4096 env。

详细 contact/effort 优先复用 `a2_hold_diagnostic_contact_detail_enabled=true`。只有本地
IsaacLab API 确认 contact point 与 handle axis frame 可用时，才新增 canonical
`estimated_handle_axis_moment` / `positive_axis_work`。不可用则写 `INCONCLUSIVE`，
不制造 force proxy。

### 6.4 E1 evaluator selector

在现有 forced-close evaluator上增加唯一新 selector：

```text
if stage == Stage2 and current close_gate:
    plant gripper primitive = configured negative close value
else:
    plant gripper primitive = deterministic policy mean
```

- 不加 hysteresis、debounce、2-step hold或episode-wide close；
- trace同时保存原 policy mean和override后的plant action；
- E1只用于诊断，不进入 natural capability count；
- E2继续使用当前 Stage3/4 forced-close，无需重写。

## 7. Focused test and construction gate

先实现最小功能，再一次性添加与本阶段直接相关的 focused tests；不增加 broad
compatibility/fuzz/defensive suite。

### 7.1 Pure/source tests

1. high-water单调、无新增时不重复收租；正increment积分正确。
2. control_dt变化时 episode scaled creation integral不变。
3. Stage3/K5 mask、Stage4/release不支付。
4. natural reset首步无spike；staged store/load后无伪creation。
5. reward helper与telemetry读取同一cache，不发生双更新。
6. E1只在Stage2∧close_gate覆盖gripper一维，其余11维及gate外action不变。
7. terminal与expanded trace reducer对 creation income/high-water/dwell精确对账。

### 7.2 Static/resolved proof

- relevant Python `py_compile` 一次；v26-3 shell `bash -n` 一次；
- Hydra compose真实 M0/M1 × seed0/1 resolved configs；
- verifier必须证明 M0→M1 只有 old/new reward scale、对应 telemetry binding 和
  identity/output leaves；seed0→seed1只有 seed/side permutation/identity；
- load proof必须显示 policy-only actor RMS true与其余state fresh；
- config、reward registry与 env mirror leaves一致；zero-scale term不会进入 registry。

### 7.3 Real Isaac construction gate

1. 1 env/side natural eval：新trace有限、timebase正确、behavior-neutral D0可运行。
2. staged-reset smoke：真实snapshot store/load，restore 后无creation spike。
3. D/E完成并冻结最终common actuator后，跑64-env M1 smoke：至少1次真实 rollout +
   PPO update + checkpoint；验证reward支付、optimizer step和saved resolved config。

任何 source/config/integrity failure先修复并重跑相同 smoke；不得带着坏 telemetry进入
formal。Construction gate只证明路径可运行，不证明policy质量。

## 8. Diagnostic Wave D/E — GPU0–3

共同 source为 v26-2 `W_STEP0750` full checkpoint：

```text
logs_rl/by_batch/base_v26_2_pull_derived_20260825/wave1/W/model_step_000750.pt
```

使用 checkpoint保存的actor/RMS；
所有 episode natural start，LEFT/RIGHT分开。四条 lane并发：

| GPU | Lane | episodes | intervention | 目的 |
|---:|---|---:|---|---|
| 0 | D0 | 64/side | instrumentation only | 复现old income/high-water gap，冻结local baseline ceiling |
| 1 | E1 | 64/side + 1 render/side | Stage2 close-gate-only | 因果确认selected K5-edge limit cycle |
| 2 | E2 | 64/side | existing Stage3/4 forced-close | 排除/确认Stage3 open chatter |
| 3 | D3 | 16/side | existing detailed contact/effort | tracking、estimate saturation、contact geometry诊断 |

D0 前另以当前 fixture 做短 zero-command readback，得到 handle zero-state excursion。
在看到 M0/M1 结果之前，为每侧冻结：

```text
handle_creation_reference_side =
    max(D0 natural Stage3∧K5 episode handle high-water ceiling,
        zero-command readback excursion)
```

Durable creation event定义为：natural episode 中handle超过该side reference，随后在
同一 episode 内至少连续5个control steps保持在reference以上。0.03/0.1/0.3/0.6
仍作为报告band，不替代该本地reference。

判读：

- E1恢复K5/Stage3：`STAGE2_LIMIT_CYCLE_CAUSAL_CONFIRMATION`；否则
  `CLOSE_HOLD_NO_K5`。无论结果，M0/M1不使用E1 override。
- E2仍无creation：`STAGE3_CLOSE_NOT_CAUSAL`；若明显增加durable creation：
  `STAGE3_OPEN_CHATTER_CAUSAL`，但仍不把forced-close计作natural capability。
- D3若只能给estimate，明确写estimate；不得声称actual torque。

## 9. Main Training Wave M — GPU0–3

四格按§1一次并发跑满750，不在250停下来等待Owner。每格独立：

- tmux session、supervisor receipt、output root、resolved config、train log；
- exact physical GPU binding；4096 env与2048/2048 side runtime count；
- checkpoint 125/250/500/750；process exit与checkpoint validation分开；
- 不自动续到1000/1500，不以latest table替代冻结checkpoint。

输出根：

```text
logs_rl/by_batch/base_v26_3_event_time_creation_20260827/main/<CELL>/
logs_eval/base_v26/v26_3_event_time_creation_20260827/main/<CELL>/<STEP>/<SIDE>/
```

主因果 readout：

1. M0 old income与durable creation是否仍脱钩；
2. M1 creation income是否严格等于真实 high-water increments；
3. M1相对matched M0是否提高每侧 durable creation episode count、high-water分布、
   handle dwell和后续hinge；
4. 两seed方向是否一致；Stage3/K5 retention是否保留。

M1 creation admission：

- 全部creation/reset/stage integrity counters为0；
- 每个seed、每侧至少 `2/64` natural episodes满足冻结的durable event；
- M1两seed各侧均高于对应M0，不能只靠单episode peak；
- 不要求在250或750直接达到handle0.6/Stage4。

若只有一侧或一个seed成立，结果为 `MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`；可执行
本文件定义的诊断/conditional branch，但不能声称bilateral creation supported。

## 10. Conditional capacity Wave F

F不是默认训练前置。仅在D3显示以下全部条件时执行：

- 当前10/10 limit下存在持续target tracking error或estimate saturation；
- contact geometry/axis方向可解释；
- 没有证据表明只是两指互相挤压而不形成handle-axis effect。

先并发 eval-only F10/F20/F40（GPU0/1/2，16 natural episodes/side），GPU3跑reducer和
selected detailed replay。只改j7/j8 effort cap；Kp/Kd800/25、reward、wall、policy、
physics全部固定。

若较高cap同时产生方向一致的tracking改善、estimated axis effect和durable high-water，
且没有明显penetration/overspeed/overforce/fall，扩为exact64/side并选择最小有效cap。
否则保留10并记录：

- 仅force norm增加：`MORE_SQUEEZE_WITHOUT_LOAD_BEARING`；
- tested range无creation effect：`ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`；
- actual drive force不可读：相应物理量 `INCONCLUSIVE`。

如果F在M wave之前完成并准入，M0/M1四格共同使用所选cap；若M已启动，不得中途改，
F只能为下一conditional wave提供冻结值。

## 11. Conditional push load-bearing Wave P

只有 M1 完全清除velocity farming但没有bilateral creation，且D3/M trace已证明一个
可识别、side-canonical、先于high-water的positive handle-axis work信号时执行。

- 不用 pull tensile hard mask；
- 新项只能是soft local credit，单位、normalizer和scale在训练前由现有trace冻结；
- 若contact point/axis API不支持或effect不可识别，写
  `PUSH_LOAD_BEARING_SIGNAL_INCONCLUSIVE`，不运行P。

P wave四格：从同一selected M1 checkpoint policy-only + actor RMS启动，fresh其余state；
GPU0/1为creation-only P0 seed0/1，GPU2/3为creation+soft-axis-work P1 seed0/1，
4096 env、750/save125/250/500/750。P0→P1只改变soft work credit。

P positive要求work先于且预测durable high-water、两seed/两侧方向一致。否则按
`PUSH_LOAD_BEARING_CREDIT_NOT_CAUSAL` 关闭，不继续改变friction/hook/geometry。

## 12. Conditional wall-removal Wave W

只有一个natural bilateral actor已同时满足：

1. repeated durable handle creation；
2. hinge访问0.08–0.105 band；
3. old `near_closed=0.1` 的 unlatch income在越过边界后出现可见cliff；

才运行W。若1成立但2/3不成立，直接写 `WALL_REMOVAL_NOT_REACHED`。

W wave四格从同一creation-qualified checkpoint policy-only +对应actor RMS启动：

| GPU | Cell | seed | near-closed |
|---:|---|---:|---:|
| 0 | W0_S0 | 0 | 0.1 |
| 1 | W0_S1 | 1 | 0.1 |
| 2 | W1_S0 | 0 | 0.25 |
| 3 | W1_S1 | 1 | 0.25 |

4096 env、750、save125/250/500/750；W0→W1唯一行为leaf是threshold。creation
reward、actuator、physics、K5、stage machine均冻结。结果：

- W1增加0.105–0.25 dwell/Stage4：`PUSH_WALL_REMOVAL_SUPPORTED`；
- 已暴露旧wall但W1无提升：`WALL_NOT_DOMINANT_AFTER_CREATION`；
- 未暴露：`WALL_REMOVAL_NOT_REACHED`。

没有额外无界relay。最长新增lineage为 M750 + conditional P750 + conditional W750；
P未执行时最长为1500。每个conditional wave只有满足前置证据才能消耗预算。

## 13. All-checkpoint natural evaluation

M以及实际执行的P/W每个125/250/500/750 checkpoint都做：

- LEFT exact64 natural first episodes；
- RIGHT exact64 natural first episodes；
- 无 staged start、forced-close、hold oracle或action override；
- full-load相邻saved config，eval ablation只改natural scenario/eval输出，不覆盖reward、
  threshold或actuator semantics；
- raw evaluator output、terminal records、expanded selected trace、metadata、reducer结果齐全。

每侧至少报告：

- Stage3/4/5/goal、timeout/termination；
- K5/contact/opposite/window/stability；
- handle high-water、terminal、durable event、dwell；
- fixed diagnostic bands 0.03/0.1/0.3/0.6；
- hinge 0.08/0.1/0.25、band dwell、unlatch active；
- old/creation/work raw/scaled income与active denominator；
- finite-difference vs endpoint velocity discrepancy；
- reset/source/reward integrity；
- source/config/checkpoint/load/RMS/control_dt provenance。

Analyzer必须从trace/terminal直接归约，不以training occupancy、latest table或单个render
代替natural mechanism evidence。

## 14. Selected render and Teacher boundary

每个实际wave只渲染其selected checkpoint：LEFT/RIGHT各1个natural first episode，
同checkpoint同scenario contract；保存main/handle视角和receipt。非零physical GPU渲染时
只暴露该卡，进程内使用 `cuda:0`。

Teacher/Student binding只在以下条件全部满足时允许更新：

- 至少两个独立seed lineage在LEFT和RIGHT都有repeated natural full goals；
- selected checkpoint额外完成LEFT/RIGHT exact128 holdout，goal不是孤立事件；
- 无forced-close/oracle/staged start；source/load/RMS/integrity完整；
- selected render行为与metrics一致；
- 当前manifest明确记录旧G7→新Teacher的理由与已知边界。

若只有handle creation或Stage4，状态最多是 `V26_3_MECHANISM_PASS_NO_TEACHER`；G7
binding保持不变。R1 load consolidation仍需另按现有v26合同准入，不在本阶段自动运行。

## 15. GPU0–3 autonomous schedule

Worker 不需逐gate等待Owner，按依赖关系保持四卡队列：

1. implementation/static后先完成1-env与staged-reset smoke，再四卡并发D0/E1/E2/D3。
2. 立即归约D3；若§10前置成立，在M之前完成F10/F20/F40并冻结四格共同actuator，
   否则明确保留10/10。
3. 用最终common actuator完成64-env M1 PPO/checkpoint smoke；通过后GPU0–3分别启动
   M0S0/M0S1/M1S0/M1S1，跑满750。
4. main训练结束后四条eval lane各绑定一个cell，依次跑125/250/500/750的L/R。
5. main analysis决定P/W条件分支；每个正式四格wave继续四卡并发。
6. conditional训练时，空闲卡用于已经完成checkpoint的eval；不得让eval和4096 train
   抢同一GPU或output root。
7. render使用一张sole-visible卡；其余卡可继续独立eval。

已知v26 runtime在多Isaac进程下训练应让GPU0–3都可见，并用
`ACCELERATE_TORCH_DEVICE=cuda:N`绑定physical N；不要重用曾失败的sole-visible
training binding。render则相反：唯一可见physical N、进程内`cuda:0`。

所有超过30分钟的job必须独立tmux + `.ai/scripts/run_supervisor.py` receipt。开始前领取
GPU、IsaacSim和output-root lease；结束后释放。等待用有意义的长间隔，不高频轮询。

## 16. Required v26-3 launch surface

Worker 实现并在smoke后登记实际可用命令。建议最小入口：

```text
scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh
scriptsFORhuman/v26_3/run_base_v26_3_train_cell.sh
scriptsFORhuman/v26_3/run_base_v26_3_eval_lane.sh
scriptsFORhuman/v26_3/run_base_v26_3_diagnostic_lane.sh
scriptsFORhuman/v26_3/v26_3_verify_resolved_matrix.py
scriptsFORhuman/v26_3/v26_3_analyze_mechanism.py
```

Orchestrator至少提供：

```bash
bash scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh diagnostics --gpus 0,1,2,3
bash scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh main --gpus 0,1,2,3
bash scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh main-eval --gpus 0,1,2,3
bash scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh conditional --gpus 0,1,2,3
bash scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh final-eval --gpus 0,1,2,3
bash scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh render --gpu 0
bash scriptsFORhuman/v26_3/orchestrate_base_v26_3.sh closure
```

这些是待实现的合同，不是本文件落盘时已验证的命令。Worker必须先用当前Hydra/source
证明实际入口并在`.ai/PROJECT.md`补充已验证command registry，再正式运行；不得因为
文档命令拼写错误改用silent fallback。

## 17. Typed closure tree

- construction/runtime坏：`V26_3_NOT_ADMITTED_RUNTIME_INTEGRITY`。
- D0不能复现old income/high-water gap：`V26_3_BASELINE_DRIFT_INCONCLUSIVE`。
- E1无K5：`CLOSE_HOLD_NO_K5`；E1有K5：
  `STAGE2_LIMIT_CYCLE_CAUSAL_CONFIRMATION`。
- M1仍可无delta获利：`CREATION_REWARD_INTEGRITY_BUG`，修复相同实现后重跑；不进入P/W。
- M1清除alias但无creation：`REWARD_ALIAS_REMOVED_MECHANICS_BLOCKED`。
- M1只单side/单seed：`MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`。
- M1双seed双侧creation：`MONOTONE_CREATION_CREDIT_SUPPORTED`。
- effort仅增 squeeze：`MORE_SQUEEZE_WITHOUT_LOAD_BEARING`。
- P信号不可识别：`PUSH_LOAD_BEARING_SIGNAL_INCONCLUSIVE`；P无效：
  `PUSH_LOAD_BEARING_CREDIT_NOT_CAUSAL`。
- wall未访问：`WALL_REMOVAL_NOT_REACHED`；有效：
  `PUSH_WALL_REMOVAL_SUPPORTED`；暴露但无效：
  `WALL_NOT_DOMINANT_AFTER_CREATION`。
- 机制改善但无双侧goal：`V26_3_MECHANISM_PASS_NO_TEACHER`。
- repeated bilateral natural goal满足§14：`V26_3_BILATERAL_TEACHER_CANDIDATE`。

所有分支都必须生成最终closure。`NOT_SUPPORTED`、`INCONCLUSIVE`、`NOT_ADMITTED`
是有效阶段结果，不因Owner离线继续无界修改reward/actuator/physics或增加训练预算。

## 18. Artifacts and execution closure

最终至少落地：

- implementation/config/launcher与focused tests；
- source-lock、resolved matrix、load/RMS、runtime count proofs；
- D/E diagnostic raw outputs与analysis；
- M全部receipts/checkpoints/Route A/mechanism analysis；
- 实际执行的F/P/W完整receipts/eval；未执行分支写`NOT_RUN`及前置未满足原因；
- selected bilateral natural render；
- `a2_piper_base_v26_3_execution_closure_20260827.md`；
- 本文件状态/closure段、memory description/TODO/DONE/router；
- Teacher manifest只按§14更新；否则明确unchanged。

不单独打artifact bundle，除非Owner之后明确要求。保留已有dirty/untracked内容，不reset、
stash、discard或覆盖他人工作。阶段结束前报告active tmux/process/lease并释放本阶段资源。

## 19. Execution closure（2026-08-28 03:25 HKT）

状态：`v26_3_complete_not_admitted`。本plan与handoff已按canonical budget自主执行完毕；
完整验收见`a2_piper_base_v26_3_execution_closure_20260827.md`。

- implementation、focused test、natural/staged construction、D0/E1/E2/D3、bounded F、
  common-cap PPO smoke、四格M750、all-checkpoint bilateral-natural eval、conditional
  closure、selected render与memory同步均已执行；没有运行SUPERSEDED旧方案。
- D0复现old velocity-income/high-water gap；E1为
  `STAGE2_LIMIT_CYCLE_CAUSAL_CONFIRMATION`，E2为`STAGE3_CLOSE_NOT_CAUSAL`。
- F10/F20/F40提高tracking authority但不创建durable state，关闭为
  `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`，main冻结10/10。
- 四格formal均750/750 PASS；32组LEFT/RIGHT exact64 natural evidence对账完整，
  integrity=0。M1_S0/S1的RIGHT creation为8/64、13/64，但LEFT均0，最终main为
  `MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`。
- P为`NOT_RUN / PUSH_LOAD_BEARING_SIGNAL_INCONCLUSIVE`；W为
  `NOT_RUN / WALL_REMOVAL_NOT_REACHED`，没有增加conditional formal wave预算。
- selected `M1_S1_STEP0750` bilateral natural render PASS，视觉行为与RIGHT-only
  creation/LEFT failure一致。所有natural goal为0，exact128 Teacher holdout不准入；
  manifest与Student G7 binding不变，Teacher boundary为
  `V26_3_MECHANISM_PASS_NO_TEACHER`。
- physical GPU0–3按合同使用，GPU4–7未使用；未commit/push，未生成artifact bundle。
- 所有v26-3 tmux/process/lease已退出或释放；team task为COMPLETED，coordination ledger
  已archive/deactivate。execution closure与memory description/TODO/DONE/router已同步。
