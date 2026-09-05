# `base_v26-8`：bilateral Stage3→4 opening/hold 与 scaffold-decay curriculum 预注册计划

日期：2026-09-03 HKT
状态：`PLAN_FROZEN_NOT_IMPLEMENTED`
Owner 授权：GPU0–7 全部可用于 v26-8；Wave 1 与满足分支条件的 Wave 2 均已授权；Git commit/push 未授权。
上游：`scriptsFORhuman/v26_7/a2_piper_base_v26_7_bilateral_native_unlatch_plan_20260902.md`（已关闭，endpoint 冻结）
run_id：`v26_8_bilateral_opening_scaffold_decay_20260903`

本文件是 v26-8 的 authority。Codex 开工 prompt 与本文件冲突时以本文件为准；本文件与当前 source /
resolved config 冲突时，以 source 为准并回报，不得静默改判。

---

## 1. 目标

v26-8 回答两个问题，各自独立预注册，互不借用证据：

**Q_A（继续 v26-7 的下一步）**：在 v26-7 建立的双侧 unlatch 基础上，把 **bilateral Stage3→4
opening/hold** 变成双侧可重复能力。Stage4→5 release 与 through 只报告、不路由。

**Q_K（Owner 提出的训练方法）**：把已有的 `reward_penalty_curriculum` 机制改造为
**scaffold-decay curriculum**（侧感知、natural-start、以"当前目标 transition 的到达率"为 driver），
检验它在 mastery 之后能否在不回退 unlatch/opening 的前提下改善下游，并检验它在 mastery 之前是否严格惰性。

两个问题共用一套 warm-start 源、评估协议与 reducer；Q_A 的干预轴是 W（wall alignment），Q_K 的干预轴是 K。

---

## 2. 立论与证据基础（均为已核实事实，非推断）

### 2.1 v26-7 endpoint 决定了本阶段的起点

Q05 endpoint = step3000（`2/3 seed BILATERAL_UNLATCH_SUPPORTED`）。对本阶段有用的三个格：

| Cell | LEFT D/S3+/S4+/S5+/complete | RIGHT D/S3+/S4+/S5+/complete | 对 v26-8 的角色 |
|---|---:|---:|---|
| Q05_S1 | 62/64/62/62/62 | 64/64/64/18/4 | 双侧已到 Stage4：测 **consolidation**（Stage4→5、complete）与 K 的 decay 行为 |
| Q05_S2 | 60/60/0/0/0 | 57/64/64/21/0 | LEFT 有 unlatch 无 opening：测 **Stage3→4 entry**；K 应保持惰性 |
| Q05_S0 | 0/0/0/0/0 | 64/64/64/0/0 | LEFT 停在 Stage2 属 discovery 问题，本阶段两条轴都不针对它，**不纳入** |

### 2.2 Stage3→4 的收入几何：一堵墙后面还有一道谷

resolved config（Q05_S1）：

```text
a2_stage3_unlatch_near_closed_hinge_threshold = 0.1    # unlatch_hold 只在 hinge < 0.1 付钱
a2_stage3_to4_door_hinge_threshold           = 0.25   # Stage4 入场要求 hinge > 0.25 且 grasp streak
a2_stage3_to4_requires_grasp_streak          = True
a2_stage4_to5_door_hinge_threshold           = 1.0472 # Stage5 入场：hinge > 1.0472、handle < 0.2、root_x_rel > 0
```

`a2_stage3_unlatch_hold`（scale 3.0）在 hinge 越过 0.1 后归零；Stage4 的 `hold_and_drive`（8.0）、
`target_root_distance`（12.0）要等 hinge 越过 0.25 才开始。**hinge ∈ [0.1, 0.25) 是两头都不付钱的谷**，
而 v26-6 Wave A 的 trace 已证明策略会把 handle 按在 >0.6 rad、hinge ≤0.011 上吃 hold 租金到超时。
W 轴把 `near_closed` 阈值从 0.1 提到 0.25，使 hold 收入恰好延续到 Stage4 入场线，消除这道谷。
这是 v26-6 Wave B 已注册的 B1 轴（`base_v26_6_waveB_B1.yaml`），pull-v2-W 在 pull 侧有创建 Stage4 的先例；
v26-2 在 push 侧未能检验它，因为当时没有 creation。现在 LEFT 已有 durable 60/64，首次具备检验条件。

### 2.3 curriculum 机制的真实行为（source 与 runtime 证据）

- `legged_robot_base._compute_reward`：`reward_penalty_reward_names` 内的项乘同一个全局标量
  `reward_penalty_scale`；其余项不受影响。
- 更新在每次 `reset_envs_idx` 回调执行一次。4096 env 下几乎每个 control step 都有 reset；
  `degree=1e-4` 时从 1.0 衰到 0.2 需约 16,000 次更新，即约 250 个 iteration（64 步/iteration）。
- 现有两种 driver 都是全 env 均值，含 staged reset 从 Stage1–5 起步的 env，且不分侧。
  v26-7 训练日志：`average_goal_reached` 全程最大 0.26（Q05_S1），其余五格 ≤0.05；
  `average_stage_reached` 在 LEFT 停留 Stage2 的 Q05_S0 仍为 3.42。因此 **原版 goal-rate 配置在
  本阶段完全惰性，原版 stage 配置会在 LEFT 尚未学会时撤脚手架**。两者都不能直接用。
- `reward_penalty_scale` 不写入 checkpoint；eval 时若开启也会随 reset 更新。
- `log_dict["reward_penalty_scale"]` 记录的是 clip 前被原地乘过的张量（termination_level 在日志里
  出现 1.0001 正是同一 alias）。
- A2 env 已有 `_a2_v26_episode_start_stage`（每 env 本 episode 起始 stage）与 `door_open_lr`
  （LEFT=+1，RIGHT=−1），侧感知 natural-start driver 所需状态已在。

### 2.4 参照 single-RIGHT 的问题拆分顺序

v12_C 建立 Stage3 admission → v13_A 以成熟 actor warm-start 建立 Stage4 opening → v13.1 单独解决 release。
v26-8 处于 v13_A 的位置：先双侧 opening/hold，release/through 作为后一层报告。不加载任何单 RIGHT
checkpoint，不改回 RIGHT-only 分布，不整包复制 v13_A/v13.1 的 reward bundle。

### 2.5 本阶段不动的轴

`a2_stage2_squeeze_force_min=0.5`（Q05 值）、capability bundle、offset 修复、reward scale 数值、
Stage2→3 收入悬崖的定价、K5、URDF 限位、actuator/physics。S0 source 与 Q20 source 不进入本阶段。

---

## 3. 源 checkpoint 选择规则（先于任何 outcome 冻结）

规则：**取最新冻结 endpoint 中双侧 Stage4/Stage5 覆盖最多、且同时包含一个 downstream-positive seed
与一个 unlatch-without-opening seed 的 config，逐 seed 使用其 endpoint checkpoint。** 不按 goal 挑格。

据此选定 Q05 step3000：Q20 endpoint 少 1000 batches 且 `squeeze_min` 不同，若纳入会引入第二个选择轴。
Q05_S1 的 `complete=62` 是非路由观察，不是选它的理由；它作为 source 只因它是 S1 seed 的冻结 endpoint。

| Source | 路径（repo-relative） | SHA-256 |
|---|---|---|
| `SRC_S1` | `logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S1/model_step_003000.pt` | `a683257213aaba82b583924d841235f772182f53113e513e16c8d27bcb394df1` |
| `SRC_S2` | `logs_rl/by_batch/base_v26/v26_7_bilateral_native_unlatch_20260902/train/Q05_S2/model_step_003000.pt` | `0b2f739f020b056adb2fb47105fdb5bc00d1d1189ef331d42332b3e0740e54ec` |

reducer 必须核对 resolved `checkpoint` 路径与文件 SHA-256 与上表一致，否则该格 `V26_8_INVALID`。

---

## 4. Wave 1 矩阵与自变量

### 4.1 共享合同（六格相同）

```text
defaults: /ablation/wbmanip/base_v26_7_common           # 继承 bilateral、offset fix、capability bundle、squeeze 0.5
checkpoint: <SRC_S1 | SRC_S2>
checkpoint_load_mode: policy_only
policy_only_load_actor_rms: true                         # 与 v26-2 warm lineage 相同合同：actor MLP/std/LSTM + actor RMS strict 加载；
                                                         # critic、optimizer、scheduler、trainer state、env、staged-reset buffers fresh
auto_load_latest: false
seed: <1 | 2>（与 source seed 一致）
env.config.a2_v26_side_permutation_seed: <seed>
num_envs: 4096      algo.trl.num_total_batches: 3000      callbacks.model_save.save_frequency: 250
enable_staged_reset: true（训练）   PhysX velocity iterations 2
```

选 `policy_only` 而非 `full` 的理由：训练循环从 1 计数，checkpoint 编号无歧义；这是仓库有 runtime
先例的 warm-start 合同；LR scheduler 为 `constant`，fresh scheduler 无副作用。三条 arm 共用同一合同，
warm-start 瞬态是公共项，不进入 arm 间比较。

### 4.2 三条 arm

| Arm | 唯一差异 | 针对 |
|---|---|---|
| `C` | 无 | 对照：v26-7 endpoint 在同一合同下继续训练 3000 |
| `W` | `env.config.a2_stage3_unlatch_near_closed_hinge_threshold: 0.1 → 0.25` | Q_A：Stage3→4 entry |
| `K` | `rewards.reward_penalty_curriculum: true` + §4.3 的全部 K 键 | Q_K：scaffold decay |

### 4.3 K 轴精确定义

config（新增键均以 `a2_v26_8_` 前缀，缺失或类型错误 fail-fast）：

```text
rewards.reward_penalty_curriculum: true
rewards.reward_initial_penalty_scale: 1.0
rewards.reward_min_penalty_scale: 0.2
rewards.reward_max_penalty_scale: 1.0
rewards.reward_penalty_degree: -0.0001
rewards.reward_penalty_reward_names: <§4.4 的 16 项，整体替换历史名单>
env.config.a2_v26_8_penalty_driver: side_min_natural_stage_reach_rate
env.config.a2_v26_8_penalty_driver_target_stage: 4
env.config.a2_v26_8_penalty_driver_level_down_rate: 0.5
env.config.a2_v26_8_penalty_driver_level_up_rate: 0.7
env.config.a2_v26_8_penalty_curriculum_trace_enabled: true
```

driver 定义（每次 curriculum 更新时计算）：

```text
对 side s ∈ {LEFT, RIGHT}:
  N_s  = 该侧、且"上一已结束 episode 起始 stage == 0"（natural start）的 env 数
  r_s  = 这些 env 中 last_max_stage ≥ target_stage(4) 的比例
driver = min(r_LEFT, r_RIGHT)
driver > level_up(0.7)   -> scale *= (1 + degree) = 0.9999   （衰减）
driver < level_down(0.5) -> scale *= (1 - degree) = 1.0001   （恢复）
否则维持；随后 clip 到 [0.2, 1.0]
任一侧 N_s == 0 时跳过本次更新（run 初期合法可达），并计数
```

不变量：`start_stage` 与 `max_stage` 必须来自**同一已结束 episode**，不得把新 episode 的起始 stage
与旧 episode 的 max stage 配对；driver 开启时禁止同时设置 `reward_penalty_level_*_ave_stage` 或依赖
goal-rate 路径（冲突即 fail-fast）；`reward_penalty_reward_names` 中每一项必须存在于 zero-pop 后的
`reward_scales`（历史名单里的 `push_door_handle` 这类零 scale 项即 fail-fast，不再静默忽略）。

telemetry：每次更新 append 一行 JSONL 到 run 目录 `a2_v26_8_penalty_curriculum_trace.jsonl`，字段至少为
`update_index, common_step, scale_before, scale_after, driver_left, driver_right, natural_sample_left,
natural_sample_right, skipped`；`log_dict` 记录 **clip 后** 的 `reward_penalty_scale` 与 `driver_left/right/min`
（修正 alias）。

eval：所有 arm 的 eval lane 追加 `++rewards.reward_penalty_curriculum=false`，reward telemetry 跨 arm 可比；
routing 只用 stage 计数，与 scale 无关。

### 4.4 `reward_penalty_reward_names`（v26-8 冻结名单，16 项）

原则：只放当前目标 transition（Stage3→4）之前的脚手架；不放定义目标 transition 的驱动项；不放安全惩罚
与稀疏里程碑。名单随目标 transition 变化，每个 stage plan 冻结一份。

```yaml
rewards:
  reward_penalty_reward_names:
    # Stage0/1 approach & pregrasp
    - walk_to_door                      # 5.0
    - gripper_handle_orientation        # 3.0
    - pregrasp_gripper_dof_pos_l1       # 0.5
    - pregrasp_target_distance          # 6.0
    # Stage2 grasp shaping（Stage2→3 悬崖的主要来源）
    - grasp_target_distance             # 3.0
    - grasp                             # 0.2
    - a2_stage2_close_command           # 1.0
    - a2_stage2_close_progress          # 0.5
    - a2_stage2_handle_center_y         # 6.0
    - a2_stage2_handle_approach_xz      # 3.0
    - a2_stage2_both_contact            # 1.0
    - a2_stage2_opposite_squeeze        # 1.0
    - a2_stage2_squeeze_force_window    # 1.0
    - a2_stage2_contact_stability       # 1.0
    # Stage3 creation 与 hold 租金
    - a2_stage3_handle_creation         # 6.0
    - a2_stage3_unlatch_hold            # 3.0
```

明确排除：`push_door_hinge`、`a2_stage3_stage4_hold_and_drive`、`a2_stage3_stage4_keep_close_command`、
四个 `a2_stage3_stage4_*` 接触项、`target_root_distance`、`a2_stage4_grasp_target_distance_mild`、
`dont_push_door_handle`（Stage4/5 release 侧项）；全部 `penalty_*`、`limits_*`、`orientation_control`、
`termination`；`stage`、`complete`、`success_save_time`、`ref_dof_legs`。

与 DoorMan 原版名单的差别是有意的：原版含 `push_door_hinge`/`target_root_distance`，因其只在 goal 率过 0.7
后触发；v26-8 的目标就是 opening/hold，这两项必须保持全额。

### 4.5 六格与 GPU 绑定（沿用 v26-7 已验证 binding）

| Cell | GPU | source | seed | arm |
|---|---:|---|---:|---|
| `C_S1` | 2 | SRC_S1 | 1 | C |
| `W_S1` | 3 | SRC_S1 | 1 | W |
| `K_S1` | 4 | SRC_S1 | 1 | K |
| `C_S2` | 5 | SRC_S2 | 2 | C |
| `W_S2` | 6 | SRC_S2 | 2 | W |
| `K_S2` | 7 | SRC_S2 | 2 | K |

GPU0–1 专用于前置门与 milestone 评估。每格独立 tmux + run receipt，`CUDA_VISIBLE_DEVICES` 限单卡、
进程内 `cuda:0`，与 `v26_7_train_cell.sh` 相同。同一 source 的三格是 **paired design**：起点权重相同，
只差 arm 与 PPO 采样噪声；比较一律按 source 配对，不跨 source 混合。

---

## 5. 实现范围

允许的改动（最小充分）：

1. `gr00t/rl/envs/door/door_open_a2_base.py`：v26-8 driver 的 `_update_reward_penalty_curriculum` override
   分支（仅在 `a2_v26_8_penalty_driver` 设置时生效）、`last_episode_start_stage` 配对缓冲、名单校验、
   JSONL trace、clip 后记录。默认路径（键缺失）行为必须与现在 bit-identical。
2. `gr00t/rl/config/ablation/wbmanip/base_v26_8_common.yaml` 与六个 cell yaml
   `base_v26_8_{C,W,K}_S{1,2}.yaml`。
3. `scriptsFORhuman/v26_8/`：`v26_8_orchestrate.sh`（static / g0 / g1-launch|finalize / train-launch /
   milestone-launch|finalize 500…3000 / closure）、`v26_8_train_cell.sh`、`v26_8_eval_cell.sh`（复用 v26-7
   评估参数，增加 curriculum-off 覆盖与 step 集合）、`v26_8_eval_lane.sh`、`v26_8_reduce.py`、
   `v26_8_verify.py`、`v26_8_g1_reduce.py`。可复制 v26-7 同名脚本再改，不得就地改 v26-7 脚本。
4. `gr00t/rl/tests/test_a2_v26_8_*.py`：CPU 单元测试（§6 G0）。
5. memory：`memory/a2-piper/base-v26-scratch-bilateral-teacher/` 的 description/TODO/DONE，按里程碑更新。

禁止：改 v26-7 任何 artifact、脚本或 reducer；改 reward 函数逻辑或 scale 数值；改 stage 判据；
改 trainer 加载路径；引入通用"逐 stage 权重/逻辑控制器"；为 eval 或测试在核心路径加 test hook；
任何 fallback/宽容分支。

---

## 6. 前置门（未通过不得启动六格）

### 6.1 G0 — 静态与 INSPECTED

- 追踪并列出所有消费 `a2_stage3_unlatch_near_closed_hinge_threshold` 的 reward/telemetry 项；W 的
  预期语义是"hold 收入延续到 0.25"，若还有别的消费者，写入 plan 附录再启动，不改阈值取值。
- 确认 16 项名单在两个 source 的 resolved `reward_scales` 中全部非零。
- 确认 eval 组合来源为 checkpoint-adjacent config，且 `++rewards.reward_penalty_curriculum=false` 生效。
- 确认 `policy_only` 加载对 legacy actor state 走 strict + inherited RMS 分支；运行时 load receipt 须显示
  `actor_rms_loaded: true`、strict。
- 单元测试 PASS：(a) hysteresis 更新在合成 driver 序列上衰减/恢复/clip 正确；(b) 同一 episode 的
  `start_stage`/`max_stage` 配对不变量；(c) 名单含零 scale 或未知项时 fail-fast；(d) driver 键缺失时
  legacy 路径 bit-identical；(e) scale==1.0 时开启 curriculum 与关闭的 `rew_buf` 完全相等。
- `git rev-parse HEAD`、`git status --short` 与全部 v26-8 改动文件的 SHA-256 写入 source lock。

### 6.2 G1 — K 接线的 runtime smoke（GPU0）

64-env、≤5 batch、`K_S1` config、`enable_staged_reset=true`：训练进程 exit 0；trace JSONL 存在且每行
schema 合法；`scale_after` 全程 1.0；两侧 `natural_sample_*` 在首批 episode 结束后 >0；`log_dict` 出现
clip 后 scale 与 driver。G1 只证明接线，不证明 decay 会发生；decay 的行为证据来自 Wave 1 的 `K_S1`。

---

## 7. 评估与读数

milestones：本地 step `500 / 1000 / 1500 / 2000 / 2500 / 3000`，每个 milestone 对六格做 LEFT/RIGHT exact64
natural 评估（`enable_staged_reset=false`，first-episode-only），12 lane 在 GPU0–1 上完成，与训练并行。
step500 同时作为 warm-start 合同的 sanity 读数（见 §8.4）。

reducer 逐格逐侧输出（在 v26-7 字段之上新增）：

```text
沿用：episodes, durable_depression(D), stage3_admission(S3+), stage4_episodes(S4+), stage5_episodes(S5+),
      goal_episodes(complete), terminal_reasons, k5_pass_rate, press_handle_contact_force_p50,
      over_force_step_share, arm_j4_p95, arm_j4_limit_residence_step_share, integrity_violations
新增：open_hold_episodes      = 连续 ≥25 control step 满足 door_hinge_joint_pos ≥ 0.25 且 both_contact == true 的 episode 数
      hinge_highwater_p50/p95 = 每 episode max(door_hinge_joint_pos) 的 p50/p95
      stage4_dwell_p50        = Stage4 内停留步数 p50（time_in_stage 于 Stage4 的最大值）
      release_hinge_p50       = S5+ episode 的 hinge_at_release p50（无 S5+ 时为 null，不造默认值）
K 专用（训练侧，读 trace JSONL）：scale_min, first_update_below_0.95, share_of_updates_below_0.5,
      reversal_count（穿越 0.5 的方向翻转次数）, skipped_updates
配对差：同 source 下 arm − C 的 D/S4+/open_hold/S5+/complete 逐侧差值
```

`Sx+` 与 `open_hold` 都是到达/保持计数，不是通过率，不得在文字里升格。

---

## 8. 预注册路由与终止规则

### 8.1 Q_A（Stage3→4 entry，在 SRC_S2 上判）与 consolidation（在 SRC_S1 上判）

endpoint = 本地 step3000。所有阈值按 exact64 计数：

```text
ENTRY_MET(cell)   := LEFT S4+ ≥ 16 且 LEFT open_hold ≥ 8 且 RIGHT S4+ ≥ 48
CONSOL_MET(cell)  := min-side S5+ ≥ 32 且 min-side open_hold ≥ 32 且两侧 D ≥ 32
NO_REGRESS(arm)   := 两个 source 上，arm 的每侧 D 与 S4+ 均 ≥ C − 8
```

W 的 typed outcome：

```text
W_STAGE34_SUPPORTED     : ENTRY_MET(W_S2) 且 (W_S2.LEFT S4+ − C_S2.LEFT S4+) ≥ 8 且 NO_REGRESS(W)
W_NOT_DIFFERENT         : |W_S2.LEFT S4+ − C_S2.LEFT S4+| < 8 且 NO_REGRESS(W)
W_REGRESSED             : NO_REGRESS(W) 不成立
W_HARMFUL_DOWNSTREAM    : 附加标签；W_S1 的 min-side S5+ ≤ C_S1 − 8
```

C 本身的报告标签（不是干预结论）：`C_ENTRY_EMERGED` 若 ENTRY_MET(C_S2)；`C_CONSOLIDATED` 若 CONSOL_MET(C_S1)。
若 C 自己达到 ENTRY_MET，W 只能得到 `W_NOT_DIFFERENT` 或 `W_REGRESSED`，不得改写为 supported。

### 8.2 Q_K（curriculum）

先判机制，再判结果：

```text
K_ENGAGED(cell)   := trace 中 scale_min < 0.95
K_INERT(cell)     := 未 ENGAGED
K_DRIVER_MISMATCH : 报告标签；某 milestone 该格 scale < 0.95 而同 milestone eval 的 min-side S4+ < 32
预期：K_S1 ENGAGED、K_S2 INERT。若 K_S2 ENGAGED 且 eval 未见 LEFT S4+ ≥ 32 -> K_DRIVER_INVALID，K 结论作废
```

在 ENGAGED 的格上（预期 K_S1）与 C 配对：

```text
K_SUPPORTED   : min-side S5+ ≥ C + 8 且 NO_REGRESS(K)（两侧 D、S4+ ≥ C − 8）
K_NEUTRAL     : NO_REGRESS(K) 且 |min-side S5+ − C| < 8
K_REGRESSED   : NO_REGRESS(K) 不成立
K_OSCILLATING : 附加标签；reversal_count ≥ 3
```

在 INERT 的格上（预期 K_S2）：`K_IDENTITY_HOLDS` 若 K_S2 与 C_S2 的每侧 D/S4+ 差值 < 8；否则
`K_IDENTITY_VIOLATED`（scale 全程 1.0 却与 C 显著不同，说明实现改变了默认语义，整轮 K 作废并交回）。

### 8.3 提前失败终止（逐格）

```text
连续两个 milestone 两侧 D 均 < 8            -> 该格 ARM_COLLAPSED，停止该格，保留证据，不重跑
任一格训练非零退出                          -> 停止该格，保留失败证据，不重跑、不放宽、不改 config
K 格 driver 校验 fail-fast 退出              -> 同上，并立即交回 Owner
```

其余情况六格跑满 3000，无提前成功终止；预算固定，避免 v26-7 早停后 receipt 语义冲突。

### 8.4 warm-start sanity（step500，报告，不路由）

C 格两侧 D 与 S4+ 若均 ≥ source − 16，记 `WARM_START_RETAINED`；否则记 `WARM_START_TRANSIENT`
并在 step1000 复查。这只用于解释早期读数，不改任何 outcome。

### 8.5 完整性

每格每侧 exact64、`integrity_violations = 0`；resolved config 满足 §3 的 checkpoint 路径与 SHA-256、
§4.1 合同、arm 专属键（W 阈值 0.25；K 全部键与 16 项名单；C 两者皆无）、seed 与 cell 名一致；
K 格 trace JSONL 存在。任一不满足即该格 `V26_8_INVALID`。

---

## 9. Wave 2（条件分支，Wave 1 closure 冻结后自主启动）

Wave 1 六格 endpoint reducer 冻结并写入 handoff 后，按下列条件自主启动；不满足的分支记 `NOT_RUN`。
启动前必须把 Wave 1 closure 与分支判定通知 Owner；Owner 未在启动前否决即继续。

**B1 — scratch 可靠性（Owner 训练方法主张的直接检验）**
条件：K 无 `K_REGRESSED`、无 `K_DRIVER_INVALID`、无 `K_IDENTITY_VIOLATED`。
内容：from scratch（`checkpoint: null`, `full`, v26-7 common 合同）+ K；若 `W_STAGE34_SUPPORTED` 则再加 W。
seed S0/S1/S2，6000 batches，GPU2–4；milestone 1000/2000/3000 与 **v26-7 Q05 同 seed 冻结 milestone**
（已落盘，同一评估协议）配对比较，4000/5000/6000 报告。
```text
SCRATCH_BUNDLE_NONINFERIOR : ≥2/3 seed 在 step3000 满足 每侧 D ≥ v26-7 − 8 且 min-side S4+ ≥ v26-7 − 8
SCRATCH_BUNDLE_SUPERIOR    : NONINFERIOR 且 ≥2/3 seed min-side S4+ ≥ v26-7 + 8
SCRATCH_BUNDLE_INFERIOR    : 其余
```

**B2 — 组合**
条件：`W_STAGE34_SUPPORTED` 且 `K_SUPPORTED`。
内容：KW continuation × {SRC_S1, SRC_S2}，3000 batches，GPU5–6，与 Wave 1 的 W、K、C 同 source 配对；
判 `KW_ADDITIVE / KW_INTERFERING / KW_NEUTRAL`（min-side S5+ 相对 max(W,K) 的 ±8）。

B1 与 B2 可并行；评估仍在 GPU0–1。

---

## 10. 资源与时间

```text
Wave 1：实现+G0/G1 约 4–8 h；训练 3000 iteration × 约 20–23 s + 场景构建约 7 min ≈ 17–20 h，六格并行；
        每 milestone 12 lane 评估约 32 min（双卡）；closure 约 2 h。
Wave 2：B1 约 34 h（6000 batches）；B2 约 19 h；并行。
```

任一格非零退出即停止该格并保留证据：不重跑、不放宽阈值、不中途改 config、不追加预算。
GPU0–7 之外的设备不触碰。任何长跑必须有 tmux + run receipt（`.ai/LONG_RUNNING_TASKS.md`）。

---

## 11. 结论边界

- 本阶段对 Q_A 与 Q_K 各给出 experiment 证据；两者不互为证据。
- **不**构成 Teacher/Student handoff 或 G7 binding 更新的依据；**不**构成 hardware、sim-to-real 或部署证据。
- `complete` 在本阶段只报告。Q05_S1 源上的 LEFT 62 complete 是非路由观察，continuation 中它的走向只记录。
- S0 seed 的 LEFT discovery 问题不在本阶段范围；若 Wave 1 结论支持，下一阶段（v26-9）处理 Stage2→3 悬崖。
- `W_STAGE34_SUPPORTED` 只证明在 warm-start continuation 下 hold 收入对齐 Stage4 入场线有效；scratch
  下的有效性由 B1 单独回答。
- K 的任何结论都限定在本名单、本 driver、本阈值；不外推为"curriculum 普遍有效"。
- 不能把 Wave 1 的 winner checkpoint 直接声明为 Teacher；checkpoint selection rule 属于下一阶段的 plan。

---

## 12. 交付物与 closure 清单

1. 六格训练 receipt（含 source SHA-256、load receipt、source lock）；K 格 trace JSONL。
2. 六个 milestone 的 `reducer.json`（schema `a2_piper_base_v26_8_milestone_reducer_v1`）与 endpoint reducer。
3. `scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_<date>.md`：逐格 D/S3+/S4+/open_hold/S5+/complete
   表、配对差、K scale 轨迹、typed outcomes、Wave 2 分支判定、未运行事项、证据等级。
4. memory 三文件按里程碑更新；Wave 2 若运行，另附 closure。
5. Git：未授权 commit/push；closure 时向 Owner 提出 commit 请求并列出 changed paths。

---

## 13. 附录（2026-09-03 22:33 HKT）：G1 infra 失败的根因与 r2 relaunch 协议

### 13.1 已确认的根因（RUNTIME 级）

- G1 `K_S1` 在 `spawn_ground_plane` 打开
  `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Environments/Grid/default_environment.usd`
  时抛 `FileNotFoundError`；同一进程在 56 s 时对同域 `NVIDIA/Materials/Base/*.mdl` 的全部拉取也失败。
  失败早于 trainer 构造与 policy load，`policy_step_executed=false`。
- 本机 tmux server（pid 2692622，2026-07-31 启动）的全局环境固定为
  `http_proxy/https_proxy=http://127.0.0.1:18888`；当前只有 `127.0.0.1:18889` 在监听。
  `.ai/scripts/run_supervisor.py` 用 `tmux new-session -d` 启动 run.sh，不显式传 env，因此 Isaac 进程继承了
  指向已死代理的环境。v26-7 用同一 wrapper 在 2026-09-02 成功，说明代理端口在 09-02 与 09-03 13:48 UTC 之间变更。
- 复现：在一个新建 tmux session 中 `env` 显示 18888，对上述 USD 的 `curl -sI` 退出码 7（connection refused）；
  在当前 shell（18889）与不走代理时均返回 HTTP 200。资产本身可达。
- 附带 hazard：Isaac python 进程在场景构造异常后以 0 退出；`v26_8_capture_train.py` 依靠"strict policy-load 成功行"
  才把它判为失败。该守卫必须保留，receipt 应同时记录 `isaac_process_returncode` 与 wrapper returncode。

### 13.2 失败分类（补充 §8.3，不改其余规则）

```text
INFRA_FAILURE_BEFORE_POLICY_LOAD := 异常发生在 Isaac scene construction / 远程资产 / 网络 / 代理，
                                    且 policy_step_executed=false、无 checkpoint、无 K trace、无 load receipt
```

该类失败不属于 §8.3 的科学性非零退出：没有任何策略读数产生，不存在"结果不合意就重跑"的选择性风险。
允许 **一次** relaunch，条件全部满足：

1. 根因写入 closure 或本附录（已完成）；
2. 启动环境显式化：orchestrator 的 `launch()` 把启动 shell 当前的 `http_proxy/https_proxy/HTTP_PROXY/HTTPS_PROXY/no_proxy/NO_PROXY`
   以 `env KEY=VALUE` 形式前置进 receipt 记录的 command，使每个 run.sh 的网络环境可从 receipt 复现；
3. 资产 preflight `P0_ASSETS`：每次 launch 前，在与 tmux session **相同** 的环境变量下对
   `Isaac/Environments/Grid/default_environment.usd` 与 `NVIDIA/Materials/Base/Wood/Ash.mdl` 各做一次
   `curl -sI --max-time 20`，两者均 HTTP 200 才允许启动 Isaac；否则以 `INFRA_ASSET_UNREACHABLE` 停在 Isaac 之前。
   preflight 本身可无限次重试，它不是实验；
4. 实验合同零改动：六格 config、K 代码、plan 阈值、名单、源 checkpoint 均不变；source lock 只允许 orchestrator /
   supervisor 相关文件出现 diff，且逐文件列出；
5. 新 attempt 使用新的 output root 与 run_id 后缀 `_r2`；失败的 `G1_k_wiring` 与 receipt 原样保留为证据。

同一规则适用于 Wave 1 / Wave 2 的训练格：**仅当** 失败满足 `INFRA_FAILURE_BEFORE_POLICY_LOAD` 时允许一次
relaunch；一旦 policy step 已执行，任何非零退出仍按 §8.3 停止该格、不重跑。

### 13.3 r2 流程

`P0_ASSETS` PASS → G1 r2（GPU0）→ PASS 后按 §4–§8 直接进入 Wave 1，不需再次审批。
G1 r2 若再次失败且不属于 `INFRA_FAILURE_BEFORE_POLICY_LOAD`，停止并交回 Owner。

---

## 14. 附录（2026-09-04 HKT）：跨侧 pending-window 语义与 G1 r3

### 14.1 r2 暴露的 source/runtime 事实

G1 r2 已排除 proxy、asset、scene construction 与 checkpoint load 问题：K_S1 strict policy-only +
actor RMS 成功，执行 5 batches 并写出 checkpoint。失败只发生在 G1 wiring reducer：35 次 curriculum
update 中 LEFT 有 natural sample 的 row 为 12、RIGHT 为 22，但同一 row 双侧同时有 sample 为 0，
因此 35/35 skipped、scale 始终 1.0。

当前调用顺序是：Door `_reset_tasks_callback` 先记录本次结束 episode，父类随后在**每一次异步 reset
callback** 调用 `_update_reward_penalty_curriculum`。r2 source 在每次记录前对整张
`_a2_v26_8_last_episode_valid` 清零，因此 update 只能消费本次 reset cohort；LEFT/RIGHT episode 在不同
control step 结束时，合法证据被当作缺侧样本丢弃。这不是 start/max 错配，也不是 policy 读数失败。

### 14.2 唯一获准的语义修订

本附录只 supersede §4.3 中 `N_s/r_s` 的**跨 reset 聚合与消费窗口**，不改任何实验变量：

```text
record(completed episodes):
  继续从同一已结束 episode 配对读取 start_stage 与 max_stage；只接收 start_stage == 0。
  对 side s 累积 pending_N_s += 1；若 max_stage >= 4，则 pending_R_s += 1。

curriculum update:
  若任一侧 pending_N_s == 0：skipped=true，scale 不变，两个 side 的 pending_N/pending_R 均保留。
  若两侧 pending_N_s > 0：r_s = pending_R_s / pending_N_s，driver=min(r_LEFT,r_RIGHT)，
  完全沿用 0.5/0.7、degree=-0.0001 与 [0.2,1.0] clip；本次决策后原子清零两侧 pending counters。
```

不变量：每个 natural episode 在结束时只累积一次；缺侧 skip 不消费任何一侧；一次 bilateral decision
后两侧窗口同时清零，因此 episode 不会跨 decision 重复使用。per-env last-episode snapshot 继续仅承担
same-episode pairing 证据。trace 的 `natural_sample_left/right` 改为当前 pending window 的 denominator，
并增加 `natural_reached_left/right` 与 `consumed`；`consumed == !skipped`。其余 trace/reducer 字段不变。

允许改动严格限于：

1. `door_open_a2_base.py` 的上述 pending numerator/denominator 累积与原子消费；
2. `test_a2_v26_8_penalty_curriculum.py` 的交错双侧保留、聚合、单次消费证明；
3. 本 plan 附录、r3 source-lock verifier 与 orchestrator 的 `_r3` roots/gates。

禁止改动六格 YAML、driver target、hysteresis 阈值、degree/floor/ceiling、16 项名单、reward/stage 逻辑、
source checkpoint、trainer loader、eval/reducer 判据。r3 contract lock 必须以 r2 `STATIC_PASS` source lock
为 baseline，逐文件列出上述 allowlist，并证明其余 locked files byte-identical。

### 14.3 r3 gate 与后续流程

Owner 明确授权一次 G1 r3；它是对 pre-Wave1 wiring implementation 的窄修复验证，不把 r2 结果重解释为
PASS。使用全新 run/output/receipt/tmux root 后缀 `_r3`，旧 attempt/r2 artifact 原样保留。执行：

```text
r3 source/contract lock → G0 r3 unit gate → P0_ASSETS → G1 r3 (GPU0)
```

G1 r3 仍使用 64 env、K_S1、≤5 batches；除原 §6.2 条件外，必须至少出现一行
`natural_sample_left > 0 && natural_sample_right > 0 && skipped == false`，证明 pending window 被消费。
G1 r3 PASS 后直接按 §4–§9 进入 `_r3` Wave 1，不需再次审批。若 G1 r3 非零退出，立即停止并交回 Owner；
不得再 relaunch、改阈值/config 或扩预算。

本授权不包含新的 Git commit 或 push。

---

## 15. 附录（2026-09-04 HKT）：G1 transition verifier 与 r3 artifact 重裁

### 15.1 r3 新事实

r3 的授权窄修已按 §14 生效：35 行 trace 中有 10 行双侧 pending window 被消费。update 31 的窗口为
LEFT `1/1`、RIGHT `1/1` 到 Stage4，故 `driver=min(1.0,1.0)=1.0 > 0.7`，当前 source 按冻结公式将
float32 scale 从 `1.0` 更新为 `0.9998999834060669`。Isaac child、capture wrapper、strict load、5 batches
与 checkpoint 均 PASS；外层 `FAIL/1` 唯一来自旧 G1 reducer 的 `scale_after == 1.0` 断言。

该断言与 §6.2“G1 只证明 wiring，不证明 decay outcome”冲突：一旦 pending 聚合恢复，5-batch 内完全可能
合法触发一次 driver。把正确 engagement 判为 wiring failure 既不能验证公式，也会阻断 Wave 1。

### 15.2 G1 判据的最小修订

Owner 已授权自主合理修复以继续 v26-8。本节 supersede §6.2 与 §14.3 中“G1 全程 scale==1.0”的部分；
其余 G1、实验与路由合同不变。新 G1 trace verifier 对**每一行**严格检查：

1. `natural_reached_s` 与 `natural_sample_s` 为整数且 `0 <= reached <= sample`；
2. `driver_s == null` 当且仅当 `sample_s == 0`，否则精确等于 `reached_s / sample_s`；
3. 任一侧缺样本时 `skipped=true, consumed=false, scale_after==scale_before`；
4. 双侧都有样本时 `skipped=false, consumed=true`，以冻结 0.5/0.7、degree=-0.0001 在 torch float32
   中复算更新并 clip 到 `[0.2,1.0]`，`scale_after` 必须与复算值精确相等；
5. 相邻行满足 `next.scale_before == previous.scale_after`，至少一行 bilateral consumed；
6. strict policy-only + actor RMS load receipt、5-batch checkpoint、四项 log telemetry 仍必须存在。

这不是放宽：旧 reducer 只接受常数 1.0，新 reducer 同时拒绝错误的不变、错误的变化、缺侧消费、重复消费、
分子/分母/driver 不一致或非 float32 冻结公式。G1 仍不用于判定 K 的 experiment outcome；K engagement、
benefit/regression 仍只由 Wave 1 milestone/endpoint reducer 决定。

### 15.3 不重跑的 r3 reducer-only adjudication

r3 Isaac artifact 已完整且 immutable，不做 stochastic relaunch。保留原
`.ai/runtime/runs/v26_8_g1_wiring_r3/RUN_RECEIPT.json` 的 `FAIL/1`；用新 source lock 下的 amended reducer
对同一 trace/config/load/checkpoint 做一次 CPU-only readjudication，并以独立 receipt 记录命令和结果。
只有 amended reducer 以 `--readjudication` 写出新的
`g1_readjudication.json: G1_READJUDICATION_PASS` 且 reducer-only receipt PASS，才准入 Wave 1；原本缺失的
`g1_wiring.json` 保持缺失，避免把历史 outer gate 伪写为直接 PASS。

新 source/delta lock 与 G0 使用独立 `_r3a` runtime/eval root。r3a allowlist 仅为：本 plan、
`v26_8_g1_reduce.py`、对应新 unit test、`v26_8_orchestrate.sh` 与 r3a verifier；§14 core 与六格 config
必须相对 r3 source lock byte-identical。Wave 1 train/eval/receipt/tmux 使用新 `_r3a` root，G1 evidence
引用 immutable `_r3/G1_k_wiring`。readjudication PASS 后直接启动 Wave 1；不需再跑 G1 Isaac。
orchestrator 只提供 `g1-readjudication-launch/finalize` 的 CPU-only 路径；r3a 不提供 Isaac G1 relaunch。

本 amendment 不授权新的 Git commit/push，不改 reward、stage、阈值、scale、config、source checkpoint、
trainer loader、Wave 1 eval/reducer 或 route 判据。
