# `pull_v26_8_backbone`：pull 分支迁入主线 v26-7/v26-8 bilateral backbone 的预注册计划

日期：2026-09-05 HKT
状态：`PLAN_FROZEN_NOT_IMPLEMENTED`
执行机：pull 训练机（4×RTX3090 24 GB），worktree `DoorDog-A2_Piper_pull_v0`，branch `codex/a2-piper-pull-v0-20260803`
参考机：推门主线 `DoorDog-A2_Piper`，branch `codex/v26-5-bilateral-stage5`，commit `aa8a05f` 及其后的 v26-8 r3a 未提交改动
run_id：`pull_v26_8_backbone_20260905`
canonical 副本：本文件位于 pull 分支 `scriptsFORhuman/pull_task/`；推门主线 `scriptsFORhuman/pull_v26_8_alignment/` 下有一份同内容副本供对照，冲突时以 pull 分支副本为准。

本文件是本阶段的 authority。Codex 开工 prompt 与本文件冲突时以本文件为准；本文件与 pull 分支当前 source /
resolved config 冲突时，以 source 为准并回报，不得静默改判。推门主线的 checkpoint、artifact 与本机 GPU 状态
对 pull 机不可见，本文件引用的主线数字只作机制依据，不作 pull 的实验证据。

---

## 1. 目标

**一个网络（单一 plain LSTM actor）在 pull（door_open_io=in）任务上，从随机初始化同时学会 LEFT 与 RIGHT
镜像门的 handle 下压解锁（Stage0→3），并在同一批训练里报告 Stage3→4 opening（E4）与 E5–E7。**

预注册路由只判 bilateral unlatch；opening 与 full chain（E7）只报告、不参与路由。本阶段不产出 pull Teacher，
不更新任何 handoff，不做 hardware。

---

## 2. 立论与已核实事实

### 2.1 分叉事实：不合并，只移植机制

主线与 pull 的 merge-base 是 2026-08-03 的 `4aec9fe`（pull-v0 plan 采纳点）。此后主线在 `gr00t/rl` 新增约 25k 行
（v22–v26），pull 新增约 26k 行（v0–v6.1、LR grasp、LR full）。`door_open_a2_base.py` 两侧都有必须保留的执行路径，
**禁止整文件覆盖或 git merge**；只以函数、配置项、脚本为单位移植 §3 清单。

### 2.2 pull LEFT 解锁失败的第一嫌疑：grasp 目标姿态未镜像（与主线 v26-5/v26-6 同类缺陷）

pull 的 handle/pregrasp `FrameCfg.offset.rot` 由 `_get_a2_grasp_target_orientation_wxyz()` 返回
（`door_open_a2_base.py:25380/25388`），pull 子类把它固定为常量
`A2_PULL_V0_TARGET_ORIENTATION_WXYZ = (-0.5, -0.5, 0.5, 0.5)`（`a2_pull_v0_guard.py:29`，
`door_open_a2_pull.py:1242`），对所有 env 相同，**side-independent**。

按 M = diag(1, −1, 1) 做镜像共轭，(w,x,y,z) → (w,−x,y,−z)：pull 常量的镜像值为 `(-0.5, 0.5, 0.5, -0.5)`，
两者点积为 0，相对旋转 **180.00°**。主线 v26-7 plan §2.3 对 push 常量 `(0.5,0.5,0.5,0.5)` 的推导结果相同
（代数 180.00°，runtime 实测 178.64°），修复后 LEFT 从结构性 0 变为 61–63/64 durable。

pull 自己的证据与该解释一致：bilateral winner 的 LEFT handle≥0.3 为 11/16（能摸到把手），handle≥0.6/latch/E3
只有 2/16，RIGHT 为 15/16；H4–H12 只在 LEFT 侧加 residual、reward、snapshot、task-space 变体，LEFT E4 全部为 0。
pull 已有的 `handle_send_y = -door_open_lr * y`（`door_open_a2_pull.py:5646`）与 H14 canonical features 只镜像了
指标与 actor 输入，**没有镜像物理抓握目标**。

这是强嫌疑，不是已证事实：pull 机上的 G1 gate（§4.2）必须用 runtime 证明修复后 LEFT 目标相对 authored 值偏 180°、
RIGHT bit-identical，才能启动矩阵。

### 2.3 夹爪能力：pull 已有 45 N bundle，缺 squeeze/over-force 窗口

pull 的 finger profile 为 `V20_G4_45N_KP1300_KD32`，`dof_effort_limit_list[-2:]=[45,45]`、arm_j7/j8 Kp/Kd `1300/32`、
`a2_m39_gripper_material_enabled=true`，与主线 v26-6 `GRIPPER_CAPABILITY_BUNDLE` 一致。差异在窗口：pull 继承
`a2_stage2_squeeze_force_max=20`、`a2_stage2_over_force_threshold=40`；主线 v26-6 Wave A 证明 over-force 40 会惩罚
下压所需的握力（v26-3 F ladder 因此得出错误结论），v26-7 使用 `30/55`。本阶段对齐为 `30/55`，`squeeze_force_min=0.5`
（主线 Q05 值，v26-7/v26-8 全部成功格所用）。

### 2.4 Observation 与 actor 结构：pull 多了 2 维，且机制进入了 actor

主线 actor_obs 为 135-D、critic 140-D（`gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`）。pull 的 LR 训练配置
（`door_open_a2_pull_lr_grasp_terminal_lstm.yaml`）在 actor 与 critic 末尾各追加 `z_a2_pull_v6_release_mode`（2 维），
即 137/142-D；pull base obs yaml 还登记了 `a2_pull_h10_gate_info`(8)、`z_a2_pull_v6_hinge_velocity`(1)、
`z_a2_pull_e3_latched`(1)、`z_a2_pull_v61_post_release_control`(1) 的 dims/scales。pull 的 actor 类链为
`PullV6NativeBilateralActor ← PullV6PostReleaseObsOverrideActor ← PullV6ReleaseModeActor`，带
`release_mode_gripper_mean_override` 与 `post_release_obs_override` 模块——v6"送门过身"的 release 机制已进入 actor 结构。

`privileged_door_info`（含 `door_open_io` 第 8 槽）两侧完全一致，pull 的 IO 信息从 episode 开始就在主线 schema 内，
不需要额外观测。

对齐决定：**新 backbone 使用主线 135/140-D 观测与 plain LSTM actor（`door_open_a2_base_lstm` 的 actor `_target_`），
不带任何 override 模块，不追加 release-mode 观测。** pull 的 release/send-past-body 机制只能存在于 reward、stage 判据
与 telemetry；若 Stage≥4 将来确需 release-mode 信号进入 actor，须另开 plan 并同步主线 schema，不在本阶段决定。

### 2.5 Stage 语义的分叉点

| 层 | 共享主线语义 | pull 专属（保留） |
|---|---|---|
| Stage0–2 | approach/staging、pregrasp、strict grasp、K5 | `door_open_io=in` 的出生侧（+X、yaw=π）、travel −X、tensile 事件 E2 作为**报告项** |
| Stage2→3 gate | `grasp_completion`（主线 K5 admission，v26-7 已证明可从零建立） | `tensile_proof` 改为报告，不作 gate（见 §2.7 例外） |
| Stage3 unlatch | handle 下压、durable 定义（≥0.6 rad 连续 ≥25 步）、`a2_stage3_unlatch_hold` 语义 | `pull_door_handle` 的 income 模式与 mask 保持 pull 现值 |
| Stage3→4 及之后 | 只共享 stage 编号与 telemetry 词义 | E4 positive hinge retained、panel clear、E5–E7、send-past-body reward 全套保留 |

Owner 的原则"分叉出现在 Stage3 之后"在本表中落实为：Stage0–3 的观测、能力、目标几何、gate 与 unlatch 定义与主线相同；
Stage3→4 起的行为目标按 pull 自己的物理保留。

### 2.6 硬件与规模

pull 机为 4×RTX3090 24 GB。历史 4096-env 运行在 v6 staged-reset buffer 单次申请 29.66 GiB 时 OOM；n1024 可运行。
本阶段 `num_envs` 由 §4.1 的 memory smoke 冻结为 **2048 或 1024**，三格统一；GPU0 评估，GPU1–3 训练。

### 2.7 本阶段不动的轴

pull Stage3+ 的 reward 数值与 17 项 send-past-body 项、E 事件定义、`a2_pull_direction` 合同、finger/hook/friction
profile、`add_walls=false`、door weight range、主线 K curriculum（`K_REGRESSED`，不移植）、主线 W 轴（留给 §7）。

例外：若 P0 trace 证明 Stage3 的 `pull_door_handle` / `pull_door_hinge` income 被 `tensile_proof`/E2 mask 完全归零
（即 gate 改为 `grasp_completion` 后 Stage3 没有任何 handle 收入），则 Stage2→3 gate 保持 `tensile_proof`，E2 同时
作为 gate 与报告项；该决定在 G0 前做出并写入 contract，不得两种 gate 都跑成矩阵。

---

## 3. 移植清单（以函数、配置项、脚本为单位）

1. **镜像目标修复（核心）**：从主线移植 `a2_v26_6_mirror_quat_wxyz`（通用公式 (w,x,y,z)→(w,−x,y,−z)，对 pull 常量
   同样适用）、`_a2_v26_6_side_mirrored_offset_quaternions`（按 USD `doorOpenLR` customData 逐 env 镜像，RIGHT 保持
   authored）、开关 `a2_v26_6_side_mirrored_handle_offset_enabled`（对 all-RIGHT eval 必须是合法 no-op；per-env
   `doorOpenLR ∉ {−1,+1}` fail-fast），以及测试 `gr00t/rl/tests/test_a2_v26_6_handle_offset_mirror.py`。pull 的
   `_get_a2_grasp_target_orientation_wxyz` guard 只校验 config 常量，与 per-env 镜像不冲突；兼容性由 G1 证明。
2. **能力窗口**：`a2_stage2_squeeze_force_min 0.5`、`a2_stage2_squeeze_force_max 30`、`a2_stage2_over_force_threshold 55`；
   其余 finger/M39 保持 pull 现值。
3. **观测与 actor**：新建 `gr00t/rl/config/exp/wbmanip/door_open_a2_pull_v26_backbone_lstm.yaml`：defaults 取
   `door_open_a2_pull_lstm`，obs 覆盖为主线 135/140-D 列表（不含任何 `z_a2_pull_*`、`a2_pull_h10_gate_info`），actor
   `_target_` 与主线 `door_open_a2_base_lstm` 相同，`freeze_running_mean_std=false`。
4. **训练范式**：新建 `gr00t/rl/config/ablation/wbmanip/pull_v26_8_backbone_common.yaml` 与三个 seed cell yaml：
   `checkpoint: null`、`checkpoint_load_mode: full`、`auto_load_latest: false`；`a2_door_open_lr_distribution: bilateral`
   与 `a2_door_open_lr_permutation_seed=<seed>`（pull 已有 selector，不移植主线 `a2_v26_door_open_lr`）；
   `staged_reset_ratios [0.5,0.1,0.1,0.1,0.1,0.1]` 且**不使用** pull 的 `schedule_dict` 课程；`a2_pull_stage2_to3_gate_mode`
   按 §2.5/§2.7；PhysX velocity iterations 2；`save_frequency 250`；`num_envs` 与 batches 按 §5。
5. **脚本**：新建 `scriptsFORhuman/pull_v26_8/`：`orchestrate.sh`（static / g0 / g1-launch|finalize / train-launch /
   milestone-launch|finalize / closure）、`train_cell.sh`、`eval_cell.sh`、`eval_lane.sh`、`reduce.py`、`verify.py`、
   `g1_reduce.py`、`p0_assets.py`。以主线 `scriptsFORhuman/v26_7/` 与 `v26_8/` 同名脚本为模板（Owner 随 plan 一并提供），
   receipt command 显式写入 proxy env，启动 Isaac 前做资产 preflight。不得修改任何 `pull_lr_*`、`pull_v6*` 历史脚本或 artifact。
6. **reducer 字段**：逐格逐侧 `D / S3+ / S4+ / open_hold / S5+ / complete`（主线定义）并列 pull 事件计数
   `K5 / E2 / E3 / E4 / E5 / E6 / E7`；`arm_j4_p95`、`arm_j4_limit_residence_step_share`（`abs(1.745−q4)<1e-3`）、
   `press_handle_contact_force_p50`、`over_force_step_share`、`integrity_violations`、`terminal_reasons`。E 标签与
   stage 编号的映射在 reducer 合同里显式写出，不得猜等价。

禁止：改 reward 函数逻辑或数值、改 E 事件定义、改 trainer loader、移植 K driver、引入 fallback/宽容分支、为测试在核心
路径加 hook。

---

## 4. 前置门（未通过不得启动三格）

### 4.1 G0 — 静态与 memory smoke

- source lock：`git rev-parse HEAD`、`git status --short`、全部本阶段改动文件 SHA-256。
- 单元测试 PASS：镜像四元数（pull 常量 → 180.00°）、all-RIGHT no-op、per-env `doorOpenLR` fail-fast、obs 维度 135/140、
  三格 resolved config 满足 §3 合同（能力窗口、gate、bilateral、seed 与 cell 名一致、无 `z_a2_pull_*` 进 actor）。
- memory smoke：`num_envs=2048`、bilateral、staged reset on、5 batch；exit 0 且峰值显存留有 ≥2 GB 余量则冻结 2048；
  否则用 1024 重跑一次 smoke；两者都不过则停止交回。smoke 不进入统计。
- P0 trace：列出 `a2_stage3_unlatch_near_closed_hinge_threshold`、`tensile_proof`/E2 mask、`pull_door_handle` income
  mode 的全部消费者；按 §2.7 决定 gate；写入 contract。

### 4.2 G1 — 镜像目标 runtime wiring（GPU0）

64-env、≤5 batch、bilateral、`a2_v26_6_side_mirrored_handle_offset_enabled=true`，dump `target_quat_source_handle`：
LEFT 目标相对 authored 常量偏 `180.00° ± 0.05°`，RIGHT 与 authored bit-identical，integrity 0，进程 exit 0。
再以 `enabled=true` 跑一次 all-RIGHT 64-env eval 构造（zero LEFT clone），必须是合法 no-op。

### 4.3 G2 — 旧 winner 体征（可选）

若 `logs_rl/a2_piper_pull_lr_grasp/pull_lr_grasp_h450_xseg_resume_seed2/model_step_000250.pt` 在 pull 机存在，
用它的**原配置**做双侧 exact32 natural 评估，只复现 K5 体征；缺文件记 `REMOTE_ARTIFACT_UNAVAILABLE`，不阻塞。
该 checkpoint 是 137-D override actor，**不能**作为新 backbone 的 warm-start 源。

---

## 5. Wave 1 矩阵

| Cell | GPU | seed | 说明 |
|---|---:|---:|---|
| `P_S0` | 1 | 0 | from scratch，§3 合同 |
| `P_S1` | 2 | 1 | 同上 |
| `P_S2` | 3 | 2 | 同上 |

GPU0 专用于 G1/G2 与 milestone 评估。每格独立 tmux + run receipt，`CUDA_VISIBLE_DEVICES` 限单卡、进程内 `cuda:0`。

预算：`num_envs=2048` 时 `num_total_batches=4000`，milestones `500/1000/1500/2000/2500/3000/3500/4000`；
`num_envs=1024` 时 `6000`，milestones 每 750。两种情形样本量都接近主线 v26-7 Q05 endpoint（3000×4096×64）。
每个 milestone 三格 LEFT/RIGHT exact64 natural（`enable_staged_reset=false`，first-episode-only），GPU0 串行。
**不早停**：三格跑满预算，unlatch endpoint 按 §6.1 记录首次达标 milestone；后续 milestone 继续报告 opening 与 full chain。

---

## 6. 预注册路由与终止规则

### 6.1 unlatch（路由）

逐 seed、以 durable depression 计数：

```text
LEFT >= 8/64 且 RIGHT >= 32/64   -> BILATERAL_UNLATCH_SUPPORTED
LEFT >= 8/64 且 RIGHT <  32/64   -> LEFT_RECOVERED_RIGHT_REGRESSED
LEFT == 0    且 RIGHT >= 32/64   -> LEFT_STILL_STRUCTURALLY_ZERO
其余                             -> BILATERAL_UNLATCH_NOT_LEARNED
```

任一 milestone 有 ≥2/3 seed 为 `BILATERAL_UNLATCH_SUPPORTED` → 记录 `PULL_BILATERAL_UNLATCH_SUPPORTED@step`，
该 milestone 为 unlatch endpoint（用于 §7 的 warm-start 源），训练不停止。预算用尽仍未达 → 按最终 milestone 的多数
seed outcome 定名（`PULL_LEFT_STILL_STRUCTURALLY_ZERO` / `PULL_BILATERAL_UNLATCH_NOT_LEARNED`）。

### 6.2 opening 与 full chain（报告标签）

```text
PULL_OPENING_EMERGED     : 任一 seed 两侧 E4 >= 16/64（同一 milestone）
PULL_OPENING_BILATERAL   : >= 2/3 seed 两侧 E4 >= 32/64
PULL_FULL_CHAIN_OBSERVED : 任一 seed 两侧 E7 >= 8/64
```

### 6.3 失败终止

```text
G1 不过                                        -> 停止，交回 Owner（说明镜像修复与 pull guard 冲突或存在第二缺陷）
任一格训练非零退出（policy 已产生读数后）          -> 停该格、保留证据、不重跑；其余继续
policy 读数产生前的 infra 失败（资产/代理/harness） -> 自主修复并 relaunch，上限 2 次，新 root，实验合同零改动
样本量达主线 step2000 等价点时三格 LEFT S3+ 全为 0 且 RIGHT D 全 < 32
                                               -> PULL_BACKBONE_NOT_LEARNED，停止全部并交回（说明 §2.2 之外还有缺陷）
```

### 6.4 完整性

每格每侧 exact64；`integrity_violations=0`；resolved config 满足 §3 合同；seed 与 cell 名一致；镜像开关为 true；
任一不满足即该格 `PULL_V26_8_INVALID`。

---

## 7. Wave 2（条件分支，自主启动，启动前通知 Owner）

前提：Wave 1 得到 `PULL_BILATERAL_UNLATCH_SUPPORTED@step`。

- **若未出现 `PULL_OPENING_EMERGED`**：W 轴。从 unlatch endpoint 的两个支持 seed 各自 checkpoint `policy_only` +
  `policy_only_load_actor_rms=true` 接续，唯一差异 `a2_stage3_unlatch_near_closed_hinge_threshold 0.1 → 0.25`
  （pull-v2-W 先例、主线 v26-8 W 轴），配对 C（阈值不变）：4 格，GPU0 评估，3000 batches（2048 env）；
  判 `W_OPENING_SUPPORTED`（W 两侧 E4 ≥ C+8 且两侧 D ≥ C−8）/ `W_NOT_DIFFERENT` / `W_REGRESSED`。
- **若已出现 `PULL_OPENING_EMERGED`**：不加轴，从最终 milestone 的两个最佳 seed 各自 continuation 3000 batches，
  目标是 E5–E7 报告；判 `PULL_FULL_CHAIN_BILATERAL`（≥2 seed 两侧 E7 ≥ 32/64）或 `PULL_FULL_CHAIN_PARTIAL`。

Wave 2 的 warm-start 合同、评估协议与 reducer 与 Wave 1 相同；不得从中途 checkpoint 按 E7 事后挑源。

---

## 8. 自主决策权与失败预案（Codex Main 无需等待 Owner 的事项）

1. policy 读数产生前的失败（基础设施、代理、资产、harness 断言、接线缺陷）：自主修复并重启，上限 2 次，只需通知；
   修复必须带 contract lock diff，实验合同零改动。
2. policy 读数产生后的非零退出：停该格、其余继续、不重跑、不等待。
3. milestone 读数只汇报不审批；§6 typed outcome 与 §7 分支按预注册条件自动执行。
4. `num_envs` 2048/1024 的选择由 G0 smoke 决定，不等待。
5. §2.7 的 gate 例外由 P0 trace 决定并写入 contract，不等待。
6. 预授权三个本地 commit 点：G0/G1 通过后、Wave 1 endpoint 冻结后、closure 后；不 push。
7. 必须等 Owner 的四类事：改预注册阈值或路由；超出 §5/§7 预算；改 reward/E 事件/loader 语义；任何 Teacher/handoff/
   hardware 动作。
8. 向 Owner 提问后若约定时限内无回复且 plan 有默认分支，按默认分支继续并记录。

---

## 9. 结论边界

- 本阶段只回答"几何修复 + 能力窗口对齐 + 主线 backbone 后，pull 单一条件策略能否原生学会双侧 unlatch，并报告 opening/E7"。
- 不构成 pull Teacher、Student、hardware 或 sim-to-real 证据；不改任何主线结论。
- `PULL_BACKBONE_NOT_LEARNED` 不证明条件策略在 pull 上不可行；它表明 §2.2 之外还有缺陷，下一步应做 P0 级几何/接触 trace，
  而不是回到 residual/head 扫描。
- 与推门主线合并为单一 push/pull policy 是后续（主线 longterm TODO N-03）事项，前提是本阶段建立 pull 双侧全链路。

---

## 10. 交付物

1. 三格训练 receipt（含 source lock、resolved config、num_envs 决定、proxy env、资产 preflight）。
2. 每个 milestone 的 `reducer.json`（schema `a2_piper_pull_v26_8_backbone_reducer_v1`）与 endpoint reducer。
3. `scriptsFORhuman/pull_v26_8/a2_piper_pull_v26_8_backbone_closure_<date>.md`：逐格逐侧主线字段 + E 事件表、
   typed outcomes、Wave 2 判定、未运行事项、证据等级、changed paths。
4. memory：`memory/a2-piper/pull-lr-full-stage/` 的 description/TODO/DONE 按里程碑更新；新建 entry 只在 Owner 批准后。
5. Git：三个预授权 commit 点本地提交；不 push。
