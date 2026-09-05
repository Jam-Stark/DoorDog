# DoorDog base_v26-2：Stage2 夹爪极限环、Stage3 无把手创建的独立诊断与最小可证伪优化计划

## 0. Source lock、审阅范围与证据边界

- Main source lock：`https://github.com/Jam-Stark/DoorDog`，branch `A2_Piper`，commit `e6310042348d24fbe8bb8bdc6ecd70e226fc3e32`。
- Pull comparison source lock：同一 remote，branch `codex/a2-piper-pull-v0-20260803`，commit `5a31f1acc5528c5697abc357fe8b2a861a692fdd`。
- Worker bundle：`worker_delivery__source_and_configs.zip`、`worker_delivery__plots_and_evidence.zip`、`worker_delivery__logs_and_metrics.zip`、`worker_delivery__other_evidence.zip`，以及 bundle index/manifest/handoff。
- 本审阅没有安装或运行 IsaacLab、Isaac Sim、CUDA 训练，也没有访问未打包的本地 checkpoint、巨型逐步 trace、本地 process/GPU/hardware 状态。本文中的运行结论只来自 bundle 内已经序列化的 JSON/YAML/JSONL/log/video/source snapshot。
- 数值阈值与预算均是**云端建议的诊断设计**，不是自动升级的本地科学硬门槛。最终命令、资源分配、noise floor、准入线与 release/binding 由本地 AI 结合 `.ai/PROJECT.md`、真实 resolved config、机器资源和当前生产状态审定。

## 1. Insights 与 findings

### 1.1 核心结论

1. **selected render 的 Stage2 close/open limit cycle 不是 close gate 抖动。** LEFT 的 close gate 在 trace 前 6 个 control step 为 false，随后 464 步持续为 true；RIGHT 前 5 步 false，随后 453 步持续为 true。两侧 gate 都只有一次 false→true 转换。真正反复切换的是 actor 输出的 gripper primitive。

2. **当前 gripper action 是“连续策略输出、二值植物命令”的不连续接口。** `gripper_primitive > 0` 直接映射到 full-open target `[0.035,-0.035]`，否则映射到 full-close `[0,0]`；raw magnitude 不改变物理 target，却继续影响 close/open reward、action-limit penalty、动作历史和 PPO。没有 hysteresis、debounce 或 target slew。因此零点两侧的策略变化不是“小幅夹力微调”，而是全开/全关模式切换。

3. **selected render 已形成非常清晰的 K5 边缘周期吸引子。** LEFT 有 187 次 sign transition（188 个 sign runs），RIGHT 183 次（184 个 runs）；close runs 的 median/max 都是 4/4 control steps。LEFT 93 次由 close 转 open 的事件中，90 次发生在前一时刻 squeeze streak=3、2 次发生在 streak=4；RIGHT 91 次中有 90 次发生在 streak=3。两侧所有 bilateral-contact step 都发生在 close command 下，open command 下为零。该周期把接触维持在 K5 之前，恰好不触发 Stage2 completion。

4. **Stage2 周期不是简单“没接触”。** LEFT/RIGHT 分别有 280/271 个 bilateral-contact control steps，分成 93/91 个 runs；最长只有 4/3，低于 K5。问题是持续性被 action mode 翻转切断，而不是接触完全不可达。

5. **Stage2 当前 reward economics 对停留吸引子是宽容的。** selected episode 中，即使从未得到 contact-stability，LEFT 仍累计约：handle-center 56.03、approach 28.01、grasp-target 27.82、grasp 9.60、close-command 7.25、both/opposite/window 各 5.60、stage 10.86；open-command penalty 仅约 -0.69。RIGHT 同型。它不证明 actor“有意识规避 K5”，但证明一个 sub-K5 周期可以持续获得大量 dense income，且单步 open pulse 的即时成本很小。

6. **64-env 的 Stage3 总体阻断与 selected Stage2 极限环是两个层次。** W_STEP0750 natural Route A 已有 LEFT 32/64、RIGHT 36/64 进入 Stage3，并积累 LEFT 3782、RIGHT 4343 个 K5 steps；两侧 Stage3 terminal contact-force median 约为 10.1/8.8 N 和 10.4/7.7 N，terminal primitive median 均为明确 close。也就是说，population 中大量 episode 已跨过 Stage2 持续接触门槛；它们仍没有创建可保持的把手角。

7. **Stage3 depression reward 有“速度收入不等于状态创建”的 source-level credit defect。** `_get_a2_stage3_handle_depression_raw_and_active()` 直接用 `handle_vel + normalized_handle_pos`，在 Stage3+K5 时支付。W_STEP0750 的 Stage3 episode 中，LEFT 每 episode 平均获得约 59.47 raw income、RIGHT 38.35；活跃约 118/121 control steps。可是 LEFT per-episode max handle median 仅 `6.4e-10 rad`、最大 `1.64e-4 rad`，终态均值近零；RIGHT median `3.33e-4 rad`、最大 `2.87e-3 rad`，终态均值 `2.08e-4 rad`。这直接证明 reward 可以在没有 durable handle state 的情况下大量为正。最可能的物理解释是 control-step endpoint velocity 采到了弹簧/接触往返中的正相位，或正负运动在 decimated physics substeps 内相消；缺少 substep min/max 与 net delta，尚不能把具体 alias 路径升级为已证事实。

8. **这不是 reward registration 或 telemetry binding 失败。** depression active 只发生在 Stage3+K5，`active_outside_stage3`、`active_without_k5`、`raw_nonzero_while_inactive`、`stage4_below_threshold_on_first_admission` 均为 0；income 为正且 integrity 计数为 0。问题在 reward 的物理语义，而不是注册缺失。

9. **R→W 在本轮没有被暴露。** Resolved-matrix proof 表明 R→W 唯一 causal leaf 是 `a2_stage3_unlatch_near_closed_hinge_threshold: 0.1→0.25`。R_STEP0750 与 W_STEP0750 的全部 population metrics 完全相同，且没有 episode 达到 hinge 0.1。W 所修改的 reward wall 从未被访问，因此当前应裁定 `WALL_REMOVAL_NOT_REACHED`，不是 W 已证伪，更不是 W 已支持。

10. **A→W 明确不是单因素。** A→R 改 depression reward，R→W 再改 near-closed threshold；A→W 同时跨 creation-credit 与 wall 两个机制。任何把 A→W 写成“只改一个因素”的叙述都应拒绝。

11. **U-probe 反驳“门资产静态锁死”。** 在当前 fixture 中，外部把手角设为 0.5 rad 时 hinge max 约 0.0478 rad，0.6 rad 时约 0.1443 rad；latch withdrawal 同步增加。当前 policy 从未接近该把手区间，因此主阻断发生在 handle creation/force transmission，而不是 hinge 永久不可动。

12. **历史正路径的共同规律是先建立 creation，再移 wall/handoff。** single-RIGHT 路径中，v12_C 加 K5 仅解决 admission，16/16 进 Stage3但 hinge 仍近零；v13_A 以成熟 warm actor 为源，同时改变 K5、800/25、velocity iterations=2、Stage3 base unlock、raw handle reward→grasp-gated unlatch/hold、Stage3→4 grasp requirement，随后 16/16 到 Stage4；v13.1 再解决 release/target-root handoff，达到 seed0 canonical 16/16 goal。Pull 路径中，v1-R 先用 creation reward 产生稳定 handle rotation，v2-W 才在同一成熟 actor 上做 0.1→0.25 wall removal。当前 v26-2 则从 `CONT_STEP2000` 直接学习可被 velocity farming 的 depression 信号，尚未取得真实 creation 就进入 W；这是明确的 lineage/stage-order mismatch。

### 1.2 审阅判定

- **Stage2 selected-render verdict：** `GRIPPER_MODE_LIMIT_CYCLE_AT_K5_EDGE`，高置信；其主导可观测机制是 actor raw sign oscillation + hard binary target mapping + sub-K5 reward rent。close gate chatter 不支持。
- **Stage3 population verdict：** `RETENTION_WITHOUT_HANDLE_CREATION`，高置信；contact/K5 retention 已存在，persistent handle state 为零或 noise-scale。
- **Reward verdict：** `HANDLE_VELOCITY_CREDIT_WITHOUT_STATE_CREATION`，source semantics 直接支持；具体是否为 physics-substep alias、弹簧反弹或接触几何往返，需要新增 trace 才能区分。
- **Wall verdict：** `WALL_REMOVAL_NOT_REACHED`，不是 W 的科学正/负结论。
- **Fixture verdict：** `STATIC_FIXTURE_LOCK_NOT_SUPPORTED`。
- **Teacher/Student binding：** 本轮没有任何 bilateral-natural goal evidence，不应更新绑定。

## 2. 证据、推断、未知项与本地专属验证

### 2.1 Worker bundle/remote source 直接支持的事实

| 事实 | 直接证据 |
|---|---|
| Main/pull source locks | `CLOUD_PRO_INPUT_GUIDE.md`、`PULL_REPO_SOURCE_LOCK.md`、remote commits |
| W selected 两侧 Stage2 overtime | selected metrics/video/step trace |
| Gate 只切换一次 | 用 trace 中 offsets/alignment 按 resolved tolerance 独立重算 |
| Gripper sign 高频切换；close run 上限 4 | `stage2_5_step_trace.json` |
| bilateral contact 与 close command 完全共现；open 时为零 | 同上 |
| Stage2 dense reward 可在 sub-K5 周期累积 | 同上末行 `reward_episode_sums` |
| R/W750 的 Stage3 entry 32/64、36/64，Stage4/handle/hinge门槛全零 | `wave1_mechanism.json` |
| R/W 的 K5、contact 与 depression income 为正，integrity 为零 | 同上 |
| R/W metrics 完全一致；R→W 仅 threshold leaf | `resolved_matrix_proof.json` + mechanism JSON |
| 当前 reward 使用 `handle_vel + handle_pos` | `door_open_a2_base.py:15338-15404` |
| 当前 action 以 raw sign 选 full-open/full-close | pull snapshot `gr00t/rl/envs/base_task/a2_base.py:545-582`；该 shared base task 与 bundled resolved runtime contract 对齐 |
| actor 看到 door position、force、stage、last action、transform 等；没有显式 K5 remaining、mapped mode、high-water、handle-axis work | resolved W actor obs 与 source |
| 当前 gripper Kp/Kd 800/25、velocity iterations 2、j7/j8 effort limits 10/10 | resolved W |
| U-probe 在 handle 0.5/0.6 rad 时产生 hinge response | `u_probe_receipt.json` |
| v13 与 pull-v1/v2 的历史结果 | bundled memory、plans、round reports |

### 2.2 有证据支撑、但仍是推断的机制

1. **Actor 的 4-close/1-open 周期是 learned equilibrium。** Trace 极强地支持周期结构，但 bundle 没有 policy mean/log-std、sample seed、LSTM hidden state；因此不能确定它是 deterministic mean limit cycle、stochastic sampling、RNN state oscillator，还是三者共同作用。
2. **Actor 在规避 Stage3 低价值。** Reward economics 与 open pulse 时序支持这一解释，但没有 counterfactual value/Q 或固定 action rollout，不能写成已证“策略故意卡门槛”。
3. **Stage3 reward income 来自 alias/往返。** position 与 income 的矛盾支持；缺少每个 0.02 s control interval 内 4 个 physics step 的 handle min/max、start/end 和 contact impulse，无法确定 alias 发生在哪一层。
4. **力主要没有形成把手轴力矩。** 持续 normal contact 与零 handle motion 支持；现有 trace 只有 body/handle force vector，没有 contact point、lever arm 或 handle-axis resultant torque/work，故不能直接证明。
5. **10 N effort cap 可能限制 force transmission。** 这是 plausible bottleneck，不是已证主因。v13 同样有 10 N cap但在特定 lineage/behavior 下可创建动作；pull 使用 45 N 和更硬 gains，但还同时改了 geometry、hook/friction、reward、load-bearing mask，不能直接归因到 45 N。
6. **缺少显式 K5 progress/actuator mode 可能加剧 observability。** Actor 有 history、contact、DOF、last raw action，可间接推断；需要 observation ablation 或 oracle field 才能定因。

### 2.3 当前未知项

- policy mean/log-std 与 sampled action 的关系；LSTM hidden/cell 是否出现周期。
- j7/j8 实际 applied effort/torque、saturation ratio、target tracking error 的 control-step/substep轨迹。
- contact point、handle-local normal/tangent force、`(r×F)·axis`、positive handle work。
- 四个 physics substeps 内把手运动是否先正后负；endpoint velocity 是否稳定代表净运动。
- 使用 full checkpoint eval 时 actor/critic/RMS/optimizer 的确切恢复事实是否与本地当前 runner 一致；bundle 中 W training source 是 `policy_only + actor RMS=true`，后续实验必须显式保持。
- 当前本地 HEAD 是否已经包含更新、生产 checkpoint 是否仍可用、GPU budget、真实命令与 Hydra override 语法。
- 实机 Piper 的有效夹力/摩擦/电流限制。官方手册给两指夹爪额定 40 N、最大 50 N，但该值不能等同为仿真中每个 prismatic joint 的 40/50 N hard limit。

### 2.4 必须由本地 AI 验证

- 所有新 eval override、state capture 与 torque/work trace 能否在当前 IsaacLab API 中实现。
- natural bilateral 64-env eval 的 seed/scenario matching、runtime、显存与 checkpoint load receipts。
- effort-limit probe 对 simulator stability、overspeed、penetration 和 actual torque 的影响。
- 新 monotone creation reward 的量纲、scale 和 local noise floor。
- 是否保留 staged reset、各 stage snapshot 可恢复性、训练吞吐和资源预算。
- 任何 release、Teacher/Student binding、sim-to-real safety 判定。

## 3. Selected render：Stage2 close/open limit cycle 的机制审计

### 3.1 Gate 不是 oscillator

Resolved W 的 close gate 条件为：

- `|x| < 0.020 m`
- `|y| < 0.022 m`
- `|z| < 0.015 m`
- opening alignment ≥ 0.9
- approach alignment ≥ 0.9
- 当前 stage=2

按这些条件重算：

| Side | Trace records | Gate false | Gate true | Gate transitions |
|---|---:|---:|---:|---:|
| LEFT | 470 | 6 | 464 | 1 |
| RIGHT | 458 | 5 | 453 | 1 |

因此，Stage1/open-target shaping 与 Stage2/close-target shaping 没有反复互相抢占。`_reward_pregrasp_gripper_dof_pos_l1()` 在 gate 内明确返回零，让 Stage2 close rewards 接管；source 与 runtime 一致。

### 3.2 Action interface 把一个连续维变成 mode switch

`_step_a2_base()`：

```python
gripper_target = torch.where(
    gripper_primitive > 0.0,
    open_target,
    close_target,
)
```

其后按 `action_scale=0.25` 转为 joint target action。结果是：

- `+0.001` 与 `+2.0` 对 plant 都是同一个 full-open target；
- `-0.001` 与 `-2.0` 对 plant 都是同一个 full-close target；
- 但 raw magnitude 继续进入 close/open reward、limit penalty 与 observation history。

selected trace 中正/负 raw 并非围绕零的小噪声：

- LEFT positive mean约 1.34，negative mean约 -1.17；
- RIGHT positive mean约 1.37，negative mean约 -1.12。

所以这是明确的 mode alternation，而非数值误差。

### 3.3 K5-edge 周期

| Side | Sign transitions | Sign runs | Close count in gate | Open count in gate | Close-run median/max | Bilateral steps | Bilateral runs | Longest bilateral run |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LEFT | 187 | 188 | 371 | 93 | 4/4 | 280 | 93 | 4 |
| RIGHT | 183 | 184 | 362 | 91 | 4/4 | 271 | 91 | 3 |

关键时序：

- LEFT 的 open transitions：前一 streak=3 有 90 次，=4 有 2 次，=2 有 1 次；
- RIGHT：前一 streak=3 有 90 次，=1 有 1 次；
- bilateral contact under open：两侧都是 0；
- contact-stability reward：两侧都是 0。

这给出一个几乎机械式的 trace：close 数步形成双侧接触 → 在 K5 之前发 full-open → streak 清零 → 再 full-close。视频只作为定性复核；定量结论来自 control-step trace。

### 3.4 可能的成因排序

1. **高：action semantics 与 Stage2 completion 不匹配。** Completion 在 `a2_stage2_completion_close_gate_required=false` 时只要求 K5 contact history，不要求当前 close command/close progress；actor 可以用 open pulse重置接触，且没有 mode hysteresis。
2. **高：dense reward 的 sub-K5 stationary rent。** handle-center/approach/grasp/contact component 每步继续支付；open penalty权重 -0.4，小于多个正项总和。
3. **中：policy learned to regulate excessive squeeze。** Open pulse可能是对即将增大的 contact force/overforce 的反馈，而不一定是“规避 transition”。现有 trace 没有 action distribution与 next-step force causal probe。
4. **中：RNN/observation timing。** Actor看到历史 raw action、DOF/contact，可能学到4-step oscillator；也可能因 control delay形成闭环极限环。
5. **低：gate chatter。** 直接反证。
6. **低：contact sensor完全失效。** 大量 bilateral signal直接反证。

## 4. Population Stage3：retention 存在但 handle creation 为零

### 4.1 现象分层

W_STEP0750 natural bilateral：

| Side | Stage3+ | Stage4+ | K5 steps | bilateral/opposite/window steps | depression raw/scaled income | handle≥0.3 | hinge≥0.1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| LEFT | 32/64 | 0/64 | 3782 | 3942/3942/3942 | 1903.10 / 228.37 | 0 | 0 |
| RIGHT | 36/64 | 0/64 | 4343 | 4523/4523/4523 | 1380.64 / 165.68 | 0 | 0 |

这不是 Stage2 selected render 的简单放大版。Population 已经具备：

- Stage3 occupancy；
- K5 retention；
- bilateral/opposite squeeze；
- force-window；
- close command；
- 非零 depression reward。

缺的是：

- persistent handle angle；
- handle high-water进入解锁区；
- hinge creation；
- Stage4 admission。

### 4.2 Reward-credit 错位

当前 raw：

```python
raw = clamp(handle_vel + clamp(handle_pos, 0, 0.785398)/0.785398, -1, 1)
raw *= Stage3_and_K5
```

该定义把两类不同事件混在一起：

- **creation：** 把手相对历史高水位真正增加；
- **retention：** 已有角度被保持；
- **oscillation velocity：** 某一采样时刻速度为正，但一个 control interval/episode 后没有净状态。

W750 的 raw income 很大，而 position high-water仅 noise-scale，说明当前 reward 主要没有在教“创建并保留状态”。这是本轮最需要先修的 credit seam。

### 4.3 Contact 不等于 load-bearing moment

现有 terminal force约 7–11 N/指，且 opposite squeeze 成立；但把手旋转需要围绕 joint axis 的 moment：

```text
tau_handle = Σ ((contact_point - handle_axis_origin) × contact_force) · handle_axis
work_positive = relu(tau_handle * delta_handle_angle)
```

若两指主要产生互相抵消的法向夹持，或 contact point 靠近轴线，force norm 很大仍可 `tau_handle≈0`。当前 trace 没有 contact point与轴向 moment，因此“力够/不够”不能只看 force norm。

### 4.4 Actuator 不能先验定罪或开脱

- 当前 resolved W：Kp/Kd 800/25、velocity iterations2、j7/j8 effort cap 10/10。
- v13_A/v13.1 在相同 10 N cap 下通过成熟 lineage、reward/base/handoff bundle 创建并完成 single-RIGHT 行为，说明 10 N 并非普遍不可能。
- Pull 路径使用 45 N、1300/32、pull hook/friction 与 tensile proof mask；这些共同变化使 45 N 不能被单独归因。
- 官方 Piper 手册的额定40 N/最大50 N是硬件级夹爪规格背景，不应直接映射成当前 simulation per-joint cap或本地硬门槛。

因此正确做法是 **10→20→40 的 eval-only 单因素 capacity ladder**，并同时测实际 torque/work；不是直接复制 45 N。

## 5. 历史机制对照

### 5.1 single-RIGHT：v12_C → v13_A → v13.1

| 版本 | 主要变化 | 直接结果 | 可迁移机制 | 不可当作单因素的部分 |
|---|---|---|---|---|
| v12_C + eval-only K5 patch | 只修 control-step K5 admission | 16/16 进Stage3；首过 16/20.5/27 steps；Stage3 bilateral/stability约99.815%/98.692%；hinge max mean约0.000918 | 持续接触门槛必须以 control step定义；admission 与 creation要分开 | 仍无 creation |
| v13_A | mature v12_C warm actor；K5；800/25；velocity iters2；Stage3 base unlock；raw handle6→0；unlatch3/hold8；Stage3→4 require grasp | 0/16 goal；16/16 Stage4；4/16 Stage5；hinge p50约1.28；positive-motion bilateral99.949% | 成熟 grasp lineage、actuator response、base/arm coordination、grasp-gated retention | A 是多因素 bundle，不能把成功归到 Kp、reward或base中任一个 |
| v13.1 | warm v13_A；release threshold1.2；release后 income suppression；target-root handoff与frame economics | endpoint seed0 canonical 16/16 goal/stage5/complete | 先 creation/opening，再单独优化 release/handoff | single-RIGHT、single canonical seed，不是bilateral proof |

### 5.2 Pull：pull-v0 → v1-R → v2-W

| 版本 | 主要变化 | 直接结果 | 可迁移机制 | Pull-specific 机制 |
|---|---|---|---|---|
| pull-v0 P4 | 从 mature push lineage warm；45N、1300/32、pull geometry/hook/friction；report-only gate | 没有物理 Stage3→4 | warm lineage与事件漏斗 | pull接触几何、tensile条件 |
| pull-v1 A/B | gate repair；再加 unlatch/hold | A/B 仍在noise scale | 先验证gate与reward integrity | pull panel-clear、event graph |
| pull-v1 R | 在B上加 `pull_door_handle=6`，且受load-bearing条件约束 | seed0 step500 15/16 stable unlatch；step750 13/16，handle≈0.785、hinge max0.1006；seed1 late弱效应2/16 | **必须先获得creation证据，才能讨论wall**；creation reward可做受物理事件约束的局部信用 | E2 tensile-capture/proof mask不适用于push法向压柄 |
| pull-v2 W | 从v1-R seed0 step750 warm；唯一reward变化0.1→0.25 | Wave1 true Stage3→4 seed0 10/16、seed1 6/16；relay可到15/16、16/16 | wall removal应从已经访问旧wall的actor开始 | latch/tensile/pull方向特有 |

### 5.3 当前 v26-2 与正路径的关键差异

1. v26-2 source `CONT_STEP2000` 是 bilateral-natural acquisition continuation，不是已证明会创建 handle 的 mature actor。
2. R 的 depression reward没有load-bearing或durable-state语义，而是 sampled velocity+position。
3. R 已学到 Stage3 occupancy/retention和可获利 velocity signal，却没有 creation。
4. W 在没有 hinge 0.1 exposure 时被启动，顺序早于机制前提。
5. A→W 跨两个因素；不得作为wall因果比较。

## 6. Bottleneck 分类

| 类别 | 判定 | 证据强度 | 结论 |
|---|---|---:|---|
| Source registration bug | 否 | 高 | reward active且integrity为0 |
| Source reward semantics defect | 是 | 高 | sampled velocity可在无durable state时支付 |
| Telemetry semantics defect | 是，轻度 | 高 | `unlatch_hold_active_steps` 对任何微小正handle_pos都可活跃，不代表0.3/0.6 creation |
| Action semantics bottleneck | 是 | 高 | continuous raw sign→binary full target，无hysteresis/slew |
| Stage2 reward-credit bottleneck | 是 | 高 | sub-K5周期仍获大量dense rent；open penalty小 |
| Stage3 reward-credit bottleneck | 是 | 高 | velocity income与handle high-water脱钩 |
| Contact acquisition bottleneck | selected 是；population 否 | 高 | selected被open pulse切断；Stage3 population已K5持续 |
| Force-transmission geometry | 可能 | 中 | force norm充分但无角度；缺moment/work trace |
| Actuator capacity | 可能 | 中低 | 10N是候选，但历史反例与多因素pull对照阻止直接归因 |
| Observability | 可能的放大因素 | 中低 | actor可间接观察，但缺K5 remaining/mapped mode/high-water/work |
| Lineage/distribution shift | 是 | 高 | 当前source未有creation证据，正路径都从成熟creation actor继续 |
| Wall threshold | 当前不是主因 | 高 | 从未访问0.1 wall |
| Static door lock | 不支持 | 高 | U-probe反证 |

## 7. GPU 前必须修的 source/telemetry seam

### 7.1 把 creation 与 retention 分开

**文件：** `gr00t/rl/envs/door/door_open_a2_base.py`

**现有函数：** `_get_a2_stage3_handle_depression_raw_and_active()`、`_reward_a2_stage3_handle_depression()`。

建议新增 per-env control-step state：

- `handle_pos_prev_control`
- `handle_highwater`
- `handle_delta_net = pos_t - pos_{t-1}`
- `handle_delta_highwater = relu(max(highwater_prev,pos_t)-highwater_prev)`

最小替代 reward 候选：

```text
creation_income = normalized_positive_highwater_increment * Stage3 * K5
retention_income = clamp(handle_pos / handle_norm, 0, 1) * Stage3 * K5
```

本轮单因素 retraining 应只替换 depression raw 的语义；`unlatch_hold`继续作为 retention。不要同时改wall、actuator、base、staged reset或PPO。

必须新增 invariant：

```text
creation_reward_nonzero_without_positive_highwater_delta == 0
```

`highwater` 必须在 episode reset 和相应 stage-reset restore 时正确恢复/初始化。如何与 staged snapshot serialization结合由本地 AI核对，不可假设普通 Python buffer会自动进入 snapshot。

### 7.2 细化 Stage3 telemetry

同文件的 eval diagnostic/trace seam：`_capture_a2_eval_stage2_step_trace()` 及其 field producer。新增：

- handle position start/end/min/max per control interval；physics-substep values或至少 min/max；
- endpoint velocity与finite-difference `delta_pos/control_dt`；
- high-water与delta-highwater；
- thresholded bins：`handle_ge_local_noise`、`>=0.03`、`>=0.1`、`>=0.3`、`>=0.6`，其中0.03/0.1仅建议诊断线，需本地按noise floor校准；
- j7/j8 target、position、velocity、applied effort/torque、effort saturation；
- contact point、handle-frame force、resultant handle-axis torque、positive/negative work；
- mapped gripper mode/target，而不只 raw primitive；
- K5 streak与remaining；
- reset source：natural/staged/intervention；
- reward creation/retention/velocity旧信号分别记录。

把目前名为 `unlatch_hold_active_steps` 的指标保留作“reward active”审计，但不要再把它解释成物理解锁；增加显式 thresholded physical metrics。

### 7.3 增加 policy-side trace

**文件：** `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`，eval action sample/warp/step路径。

环境只能看到 sampled action；需要 trainer 导出：

- actor distribution mean、std/logstd；
- pre/post delta、post warp、最终 env raw action；
- gripper scalar的 sample seed/episode step；
- recurrent hidden/cell norm，必要时只记录norm和有限摘要，避免巨型artifact；
- checkpoint load facts、actor RMS loaded、source checkpoint identity。

这能区分 deterministic mean oscillator、sampling-induced flip与RNN hidden-state cycle。

### 7.4 不建议第一步修改的 seam

- 不先把 `a2_stage2_completion_close_gate_required` 改为 true：这会改变任务定义，却不能解释 actor为何每4步open，也可能只把Stage2卡得更死。
- 不先加入部署期 gripper hysteresis：它可作为 oracle诊断，但直接训练/部署改法会把 policy credit与controller workaround混在一起。
- 不先改 0.1→0.25 wall：当前未暴露。
- 不先复制 pull tensile mask：push的load-bearing方向不同。
- 不同时改Kp/Kd、effort、friction、reward与source actor。

## 8. 最小、可证伪、bilateral-natural 优化计划

### 8.1 总原则

- 每个行为结论都按 LEFT/RIGHT 分开报告。
- 先做 eval-only mechanism intervention，再训练。
- 所有训练 cell 明确 source actor、load mode、actor RMS contract。
- 每次只改一个因果因素；路径、run name等非行为叶子除外。
- 计算预算写为 env/batch/episode，不写云端臆测的GPU小时。
- admission是继续下一层的证据条件，不是release gate。
- 每层都给 typed negative outcome，失败即停，不开放式扫参。

### 8.2 单因素矩阵

| ID | 单因素 | Source actor / load-RMS | 固定项 | 建议预算 | 必须 trace | Admission（继续条件） | Stop / typed outcome |
|---|---|---|---|---:|---|---|---|
| T0 | 仅增加trace并离线重算，不改行为 | 复用现有 W_STEP0750 artifacts | 全部 | CPU/static | policy/plant字段schema；旧velocity收入vs高水位收入 | 新字段可定义、旧trace上高水位creation≈0且旧收入>0 | `TRACE_SEAM_INSUFFICIENT` 或 `VELOCITY_CREDIT_ALIAS_REPRODUCED` |
| E1 | Stage2 gate内强制持续close；其余11维action不变 | W_STEP0750 full eval；沿用checkpoint内RMS；明确load receipt | reward/physics/source/scenario | 1 selected episode/side render + 64 natural episodes/side | 原policy raw、override后mode、K5、force、overforce | selected两侧max streak≥5；population Stage3 entry增加且无明显overspeed/overforce恶化 | 成功：`STAGE2_LIMIT_CYCLE_CAUSAL_CONFIRMATION`；失败：`CLOSE_HOLD_NO_K5` |
| E2 | 仅Stage3/4 forced-close | 同E1 | 其余不变 | 64/side；只对自然进入Stage3者判读 | mapped mode、K5、handle highwater、torque/work | 若仍无creation则排除Stage3 open chatter为主因 | `STAGE3_CLOSE_NOT_CAUSAL` 或 `STAGE3_OPEN_CHATTER_CAUSAL` |
| F10 | current effort cap 10（control） | W_STEP0750 full eval | Kp/Kd800/25、reward、wall全固定 | 64/side | actual effort/saturation、axis torque/work | 基线校准 | 控制行 |
| F20 | 只把j7/j8 effort cap 10→20 | 同F10 | 同上 | 64/side | 同上 | bilateral retained highwater/axis work相对F10同向增加，安全指标不劣化 | `EFFORT_CAP_LOAD_BEARING_EFFECT` 或 `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_20` |
| F40 | 只把cap 10→40 | 同F10 | 同上 | 64/side | 同上 | 同F20；选择最小有效cap | `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`。45 N最多作为后续探索点，不是硬门槛 |
| M0 | 旧 sampled-velocity depression | `CONT_STEP2000`；`policy_only`；`policy_only_load_actor_rms=true`；新critic/optimizer | actuator用F ladder前预先确定并在M0/M1相同；wall0.1；其余固定 | 2 seeds ×4096 env ×250 batches pilot；125/250各64/side eval | old raw、highwater、work、load facts | control | — |
| M1 | 只把 depression raw 换为 monotone high-water creation | 与M0完全同源/同load | 同M0 | 同M0；满足admission才续至750 | creation invariant、handle highwater、axis work | 两seed、两侧出现超本地noise的可保持creation；不要求pilot直接Stage4 | 无creation：`MONOTONE_CREDIT_NO_CREATION`；alias消失但机械仍堵：`REWARD_ALIAS_REMOVED_MECHANICS_BLOCKED` |
| P1 | 在M1上只加push-specific soft handle-axis work credit/weight | 最佳admitted M1 actor，`policy_only + actor RMS=true` | 不引入pull tensile hard mask | 2 seeds×4096×250 pilot | torque/work→highwater时序 | work先于且预测creation，两侧同向 | `PUSH_LOAD_BEARING_CREDIT_NOT_CAUSAL` |
| W1 | 只改 near-closed 0.1→0.25 | **必须**从已经在自然eval中访问0.1附近且有creation的同一actor出发；policy-only+对应RMS | creation reward/actuator/physics固定 | 2 seeds×4096×250，必要时续 | 0.08–0.105与0.105–0.25 dwell、Stage4 | 旧cell确有0.1 wall exposure；W1增加跨band/Stage4 | 未暴露：`WALL_REMOVAL_NOT_REACHED`；有效：`PUSH_WALL_REMOVAL_SUPPORTED` |
| L0（可选诊断） | 历史 v13.1 actor直接在当前bilateral-natural eval | 本地解析旧checkpoint真实load/RMS；不得猜 | 不训练 | 64/side | source identity、mirror transform、creation | 只做lineage鉴别 | 右成左败：`MIRROR_LINEAGE_SHIFT`；双成：`V26_SOURCE_LINEAGE_REGRESSION`；双败：`ENVIRONMENT_OR_CONTRACT_DRIFT` |

### 8.3 E1 的实现要求

不要把 gripper 从 episode 开始就全程close。建议 evaluator-only 条件：

```text
if stage==2 and close_gate:
    mapped_gripper_mode = CLOSE
else:
    mapped_gripper_mode = policy
```

若 gate 暂时丢失，可设最多2个 control-step 的诊断性保持，但该值需预注册并单独记录；最干净的首轮是严格 gate 内覆盖。环境 trace 同时保留 policy raw 和 override后的plant mode。E1是机制干预，不是候选部署controller。

判读：

- 若 selected 两侧立刻K5并进Stage3，说明 Stage2主因被因果确认；
- 若仍无K5，转向 contact geometry/actuator tracking，不训练任何wall/reward；
- 若K5解决但Stage3仍无creation，明确分层为 `CONTACT_STABILIZED_NO_HANDLE_CREATION`。

### 8.4 F ladder 的判读

只改 `dof_effort_limit_list` 对应 arm_j7/j8 两叶，Kp/Kd保持800/25。不要把 10→40 与 800/25→1300/32 合并。

正结果必须同时满足：

- actual effort/saturation确实改变；
- handle-axis torque/work改变；
- durable highwater改变；
- LEFT/RIGHT方向至少同向；
- 没有明显 penetration、overspeed、overforce/fall退化。

只有force norm增加而axis torque/highwater不增加，应判 `MORE_SQUEEZE_WITHOUT_LOAD_BEARING`，不准入训练。

### 8.5 M0/M1 reward credit pilot

选择 `CONT_STEP2000` 作为共同source，是为了避开R/W已经学到的velocity-farming attractor，同时保持当前v26 lineage。加载合同必须与 bundled v26-2一致：

```yaml
checkpoint_load_mode: policy_only
policy_only_load_actor_rms: true
```

Trainer source表明 `true` 时会 strict-load完整actor state（含running_mean_std），critic/optimizer按policy-only训练路径重新建立。所有cell必须导出load facts。

建议pilot继续条件不是“达到45°”，而是：

- creation reward invariant全零违规；
- 至少在本地calibrated noise floor以上出现重复、可保持的positive highwater；
- 两seed中两侧方向一致；
- K5 retention不被破坏。

`0.03 rad`可作为云端建议的观察band，但不得自动成为本地硬门槛。U-probe的0.5/0.6 rad是fixture response参考，不应要求250-batch pilot直接达到。

### 8.6 P1 push-specific load-bearing credit

仅当 M1 已清除 alias但仍无creation，且新增trace显示 axis torque/work不足或与highwater有预测关系时执行。

不要复用 pull 的 E2 tensile mask。Push 可用 soft、可观测的局部物理量，例如：

```text
positive_axis_work = relu(tau_handle_axis * delta_handle_angle)
load_bearing_quality = smooth_clip(tau_handle_axis / tau_norm)
```

它应作为creation credit的soft辅助或诊断weight，而非本地硬gate。对照M1/P1保持同source、同RMS、同reward其余项、同actuator。

### 8.7 W1 的启动前提

只有当旧threshold=0.1的actor在natural bilateral中出现：

- 真实handle creation；
- hinge接近/进入0.08–0.105 band；
- old unlatch reward在越过0.1后发生可见income cliff；

才启动0.25 cell。否则停止并记录 `WALL_REMOVAL_NOT_REACHED`。这正是pull-v2有效而当前push-W无信息的差别。

## 9. Admission、stop condition 与 typed negative outcomes

### 9.1 机制级 admission，不等于release

1. `Stage2 admission`：E1能把selected两侧带到K5；natural population Stage3 entry提升；没有严重安全退化。
2. `Creation admission`：durable highwater超过本地noise并可保持；creation reward严格绑定highwater；不要求立即过0.3/0.6。
3. `Load-bearing admission`：axis torque/work与creation有前后关系；不是只有force norm变大。
4. `Wall admission`：旧0.1 band确实被访问且存在income cliff。
5. `Teacher binding admission`：本轮不定义新硬线；至少应有重复的 bilateral-natural full-goal evidence、source/load/RMS/provenance完整，最终由本地Owner/AI决定。

### 9.2 Stop tree

```text
E1 forced-close
├─ 仍无K5 -> CLOSE_HOLD_NO_K5 -> 停，查几何/actuator tracking
└─ K5恢复
   └─ Stage3仍无creation -> CONTACT_STABILIZED_NO_HANDLE_CREATION
      ├─ F ladder有axis-work与creation效应 -> 最小有效cap进入M0/M1
      └─ F ladder无效 -> ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE

M0 vs M1
├─ M1 creation reward仍可无highwater获利 -> CREATION_REWARD_INTEGRITY_BUG，修复重跑
├─ alias消失且有creation -> MONOTONE_CREATION_CREDIT_SUPPORTED
└─ alias消失但无creation -> REWARD_ALIAS_REMOVED_MECHANICS_BLOCKED
   └─ 仅有trace支持时做P1，否则停

W1
├─ 旧0.1从未被访问 -> WALL_REMOVAL_NOT_REACHED
├─ 被访问且W1跨band/Stage4提升 -> PUSH_WALL_REMOVAL_SUPPORTED
└─ 被访问但无提升 -> WALL_NOT_DOMINANT_AFTER_CREATION
```

这些typed negative结果都是有效结论，不应因“没有成功”而继续无界扫参。

## 10. 阶段验收与 QA 结论

### 10.1 已通过

- Source locks与bundle provenance足以做静态/机器可读证据诊断。
- v26-2 A/C/R/W resolved causal leaves有proof；A→W已标记非单因素。
- Route A natural bilateral eval覆盖24个cell×checkpoint×side结果；R/W750的retention与无creation分层明确。
- Depression reward注册、active mask与integrity telemetry闭合。
- U-probe足以排除简单static lock叙事。
- selected render有可解码video与control-step trace；gate/action/contact/reward可重算。

### 10.2 未通过 / 不应声称

- Stage2 selected policy没有通过K5。
- R/W没有handle creation、Stage4、hinge0.1或goal。
- W wall removal没有机制暴露，不能作因果结论。
- bilateral-natural push没有继承single-RIGHT v13.1的完成能力。
- 45 N或pull tensile mask没有在本地push中被单因素验证。
- 当前artifact不能证明actual effort saturation、handle-axis torque/work或physics-substep alias。
- 不应更新Teacher/Student binding。

### 10.3 本地执行前需复核

- 当前本地HEAD/diff与source lock差异；不得reset/stash/discard较新工作。
- `.ai/PROJECT.md` command registry和正确Hydra override形式。
- W_STEP0750与CONT_STEP2000 checkpoint仍在、可load、RMS contract一致。
- 新trace不会制造不可接受I/O或显存开销；优先env0或少量env的mechanism trace，population只保留scalar/terminal聚合。
- staged reset highwater state的snapshot/restore语义。
- 力矩/接触点API在当前IsaacLab版本中的真实字段。

## 11. One more thing：可形成 research novelty 的方向

### 11.1 Event-time anti-alias credit for articulated contact

当前证据暴露了一个比“再调一个reward”更一般的问题：在 200 Hz physics、4x decimation、50 Hz policy 的弹簧接触系统中，policy可从 endpoint joint velocity 获得正信用，却不创建任何持久关节状态。可以把研究问题写成：

> 如何把 contact-rich articulated manipulation 的奖励从采样速度，重构为 control-interval 内的 durable state creation、retention 与 physically load-bearing work，并避免 decimation alias？

方法可以包含：

- interval start/end/min/max；
- monotone high-water potential；
- creation/retention分头；
- handle-axis positive work；
- anti-alias consistency loss：endpoint velocity应与finite-difference delta匹配，否则不付creation income。

这比单独把 `handle_vel` 换成 `delta_pos` 更有研究性，也可推广到latch、drawer、valve、spring-loaded switch。

### 11.2 Causal mechanism trace 与 counterfactual coupling

把以下链对齐：

```text
policy distribution -> sampled raw action -> mapped actuator mode/target
-> applied torque/contact moment -> state highwater -> stage handoff
```

再用 E1/F ladder 这类 matched intervention生成counterfactual标签，可以训练未来的 base-arm coupling/handoff critic。此前项目中的 coupling/handoff critic设想是研究假说；本轮证据表明必须先清洁 creation label，否则critic只会学习可被farming的velocity return。

### 11.3 Bilateral canonical load-bearing representation

LEFT/RIGHT应把 contact point、force、handle axis、arm/base action变换到统一handle-local canonical frame，学习 side-invariant：

- axis torque；
- tangential work；
- reach/moment-arm margin；
- creation probability。

这样既能诊断 mirror asymmetry，也能把“bilateral-natural”从简单数据混合提升为可检验的物理不变性。当前RIGHT的noise-scale handle highwater略高于LEFT，但远不足以支持行为差异结论；canonical trace可判断是镜像几何、actor lineage还是传感/坐标符号造成。

### 11.4 与 DoorMan/RoboDuet 的边界

- DoorMan 的 staged reset通过重加权occupancy帮助下游stage探索，但它不修正错误的local bridge credit；在当前系统里，它甚至可能增加 exploit-state occupancy。应把 staged reset保留为探索工具，与anti-alias creation credit正交消融。
- RoboDuet是可协同训练的loco/arm双策略框架；当前DoorDog仍是一个12D高层recurrent actor加冻结A2 low-level locomotion policy。不要把现状误写成两套PPO或把普通centralized critic当核心novelty。
- 更强的论文线是：**clean event-time creation labels + intervention-supervised base/arm coupling + handoff-state quality**，而不是“增加一个critic head”。

## 12. 关键 source map

- `main_repo_snapshot/gr00t/rl/config/ablation/wbmanip/base_v26_2_pull_derived.yaml`：source checkpoint、policy-only、actor RMS、750 batch。
- `.../base_v26_2_A_RAW0_DEP0_T010.yaml`、`C...`、`R...`、`W...`：A/C/R/W causal leaves。
- `main_runtime_evidence/.../resolved_wave1/resolved_matrix_proof.json`：pairwise proof，A→W非单因素。
- `main_repo_snapshot/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v26_acquisition.yaml`：Stage2/3 reward scales。
- `main_repo_snapshot/gr00t/rl/envs/door/door_open_a2_base.py:14400-14539`：Stage2 gate/shaping。
- 同文件 `14833-15136`：Stage2 close/open/contact rewards。
- 同文件 `15328-15420`：push/depression/unlatch reward。
- 同文件 `16935-16991`：Stage2 completion；close gate requirement为config条件。
- `pull_repo_snapshot/gr00t/rl/envs/base_task/a2_base.py:545-582`：gripper raw sign→binary target。
- `main_repo_snapshot/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:6956-7025`：policy-only actor/RMS load contract。
- `main_runtime_evidence/.../selected_render/W_STEP0750/{left,right}/stage2_5_step_trace.json`：selected mechanism trace。
- `main_runtime_evidence/.../wave1_mechanism.json`：population funnel/mechanism。
- `main_runtime_evidence/.../u_probe_receipt.json`：fixture response。
- `main_repo_snapshot/memory/a2-piper/push-open-door-optimization/description.md`：v12/v13/v13.1 lineage evidence。
- `pull_repo_snapshot/scriptsFORhuman/pull_v1/PULL_V1_ROUND_REPORT.md`、`pull_v2/PULL_V2_ROUND_REPORT.md`：pull creation→wall lineage。

