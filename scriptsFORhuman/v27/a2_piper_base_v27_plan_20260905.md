# `base_v27`：bilateral Teacher hardening 与单次失抓恢复环 pilot 预注册计划

日期：2026-09-05 HKT
状态：`PLAN_FROZEN_NOT_IMPLEMENTED`
Owner 授权：GPU0–7 全部可用；v27.0 与 Wave A/B/C 按 §9 自主推进；四个本地 commit 点预授权；push、Teacher/Student/G7 binding 更新、hardware 未授权。
上游：v26-8 r3a closure（`scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904_wave1_r3a.md`）；v26 已由 Owner 裁定收尾，资格认定作为 v27.0。
路线依据：`scriptsFORhuman/a2_piper_longterm_TODO.md` R 节（2026-09-05 裁定）。
run_id：`v27_bilateral_hardening_20260905`

本文件是 v27 的 authority。Codex 开工 prompt 与本文件冲突时以本文件为准；本文件与当前 source / resolved config 冲突时，以 source 为准并回报，不得静默改判。同目录 `-Astra` 后缀文件是另一模型的独立提案，仅供对照，不是 authority。

---

## 0. 结论与范围

### 0.1 四个问题

| 问题 | 内容 | 性质 | Wave |
|---|---|---|---|
| Q_A | LEFT 行为对齐：把 LEFT 的"松手后身体顶门"改为与 RIGHT 同等的干净完成 | 工程可靠性 | A |
| Q_B | 门侧负载/摩擦分布收敛：mass 80–160 kg + native hinge friction，建立"困难门"层并埋方向 1 的测量 | 工程可靠性 + v28 入口 | B |
| Q_R | 单次失抓恢复环 pilot：显式恢复状态 + 失效边界快照采样是否优于同 RNN 同预算的普通扰动训练 | **方法问题（本阶段唯一 novelty）** | B |
| Q_C | seed 与从零可靠性：最终配方 from scratch 3 seed；K scaffold-decay 以修正 guard 做对照 | 工程可靠性 + 回答 Owner 的 curriculum 主张 | C |

v27.0（资格认定）是 v26 的收尾动作，只评估不训练，与 Wave A 并行。

### 0.2 novelty 定位

v27 的方法问题只有 Q_R。它针对当前 `StagedTaskBase` 只允许 stage 单调上升、失抓只能等 overtime 的结构缺陷；正确抽象是带返回边的有向图，而不是树。可检验的区别在"训练分布与重入语义的配套"：R1 只加运行时恢复环，R2 再加失效边界快照采样；若 R1 已与 R2 相当，则显式采样无附加收益，如实关闭。方向 1（交互状态估计）在 v27.2 只做 report-only telemetry 与离线 shadow estimator；方向 3（coupling critic）不进入。

### 0.3 与 Astra 提案的主要差异

Wave 之间解耦并行（Astra 为全串行门控）；恢复 pilot 只依赖研究父策略，不等 scratch 门；scratch 阶段加入 K 修正 guard 对照以回答 Owner 的原始主张；资格候选集含 K_S2（它是完整评估过的 checkpoint，`K_REGRESSED` 是对 curriculum 方法的判定，不是对该 checkpoint 的否定）。

---

## 1. 输入事实

### 1.1 候选与研究父策略

全部为 v26-8 r3a step3000：
`logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/{C_S2,W_S2,K_S2}/model_step_003000.pt`。
SHA-256 在 G0 冻结写入 source lock。**研究父策略固定 C_S2**（无干预的对照谱系）；Teacher 候选按 §3 规则从三者中选。S1 谱系（LEFT 靠 arm_j4 顶限位完成、RIGHT 差）不进入候选。

### 1.2 endpoint 计数（D / S3+ / S4+ / open_hold / S5+ / complete，每侧 64）

| Cell | LEFT | RIGHT |
|---|---|---|
| C_S2 | 57/64/64/64/64/64 | 54/64/64/64/64/64 |
| W_S2 | 63/64/64/64/64/64 | 50/64/64/64/64/64 |
| K_S2 | 52/64/64/64/63/60 | 45/63/63/63/63/63 |

### 1.3 行为质量（从 endpoint trace 只读统计，v27.0 须按 §2 定义正式复算）

| Cell / 侧 | complete | 握着门穿过 | 松手后身体撞门（集数，力峰 p95） | 超速/低姿终止 | 集长 p50 | arm_j4 限位占比 |
|---|---:|---:|---|---:|---:|---:|
| C_S2 LEFT | 64 | 0 | 21 集，585 N | 0 | 815 | 0.4% |
| C_S2 RIGHT | 64 | 64 | 5 集，62 N | 0 | 485 | 0% |
| W_S2 LEFT | 64 | 0 | 16 集，227 N | 0 | 581 | 3.0% |
| W_S2 RIGHT | 64 | 64 | 0 | 0 | 428 | 0% |
| K_S2 LEFT | 60 | 61 | 10 集，635 N | 4 | 446 | 0% |
| K_S2 RIGHT | 63 | 62 | 0 | 0 | 412 | 0% |

RIGHT 已是 v19/v25 式干净路径；LEFT 在 hinge 约 1.2 rad 处松手再以身体顶门。这是 Q_A 的目标现象。

### 1.4 当前制度与域（v26-8 resolved）

`a2_v26_door_weight_range [80,120]`、`a2_v26_door_handle_height_range [0.85,0.95]`、handle drive `U(1,3) N·m`（asset 侧）、
`a2_v24_friction_enabled false`、`a2_stage4_release_hinge_threshold 1.2`、`a2_door_body_contact_penalty_mode linear_v15`
（`penalty_a2_door_body_contact` scale 为 0）、`a2_corridor_enabled false`、`near_closed 0.1`、Stage3→4 `0.25`、Stage4→5 `1.0472`、
`staged_reset_ratios [0.5,0.1,0.1,0.1,0.1,0.1]`。

### 1.5 历史先例

- v17 G5（`gr00t/rl/config/ablation/wbmanip/base_v17_G5_full_m34_m35_hinge125.yaml`）：`event_v17` 计价（5 N / 200 / 2）+ corridor 制度 + release 阈值 1.40，六格因子实验证明制度与计价均必要、合用充分，松手后身体接触 47/48→1/48。
- v16：mass 80–160 kg 全桶 100% goal。v24：native hinge friction backend 与 per-env τ_s/τ_d/c_v 基建，P02/P05/P10/P20 profile。
- v25：RIGHT 32/32、LEFT 0/32；posture 主要帮助 reach/grasp 几何。
- v26-8 K：`K_REGRESSED` 由 RIGHT durable −16/−9 触发；但 S4+ 仅 −3/−1，Stage4 停留缩短到对照的 1/3–1/2，K_S2 LEFT 握门穿过 61/64。guard 用了机制本要减少的量（规则 19）。

---

## 2. 统一评估合同

所有 natural 评估：固定侧、`enable_staged_reset=false`、first-episode-only、`rewards.reward_penalty_curriculum=false`、
`env.config.a2_v26_8_penalty_driver=null`、`a2_v27_recovery_enabled` 按 §5.2、checkpoint-adjacent config、`full` load、exact N/side。
新建 `v27_reduce.py`，exact N 参数化，字段：

- 到达计数（沿用 v26-8 定义）：`D`（handle≥0.6 连续≥25 步）、`S3+/S4+/S5+`、`open_hold`（hinge≥0.25 且 both_contact 连续≥25 步）、`complete`。
- **`clean_complete`**：同一 episode 同时满足 complete；首次 crossing 时 hinge ≥ 1.0472 rad；从首次进入 Stage3 到终止，door body-panel 非手接触合力峰值 ≤ 5 N；无 `low_height` / `upper_dof_overspeed` 终止。
- `hold_through`（`crossing_while_holding`）、`post_release_body_force_p95`、`first_crossing_hinge_p50`、`episode_length_p50`、
  `arm_j4_limit_residence_step_share`、`terminal_reasons`、`integrity_violations`。
- Q_R 专用（§5.2）：`loss_events`、`regrasp_success`、`recovered_complete`、`recovered_clean_complete`、ITT 计数。

门槛（工程接受线，不是总体概率声明）：

```text
64 样本门 : 每侧 complete ≥ 60，clean_complete ≥ 56，low_height+overspeed 终止 ≤ 2
128 样本门: 每侧 complete ≥ 120，clean_complete ≥ 112，终止 ≤ 4
NO_REGRESS(arm 对 C): 每侧 complete ≥ C − 4，D 与 S4+ ≥ C − 8
```

固定 eval seed：DEV `270001`、CONF `270101`、domain probe `270201`、final `270303`；训练不读取任何 eval manifest。
render：每候选每侧按预定 episode id 取 3 集，只做 QA 不做统计。

---

## 3. v27.0 资格认定（v26 收尾；GPU0–1，只评估）

**G0**：SHA 冻结；`v27_reduce.py` 与单元测试（clean_complete 布尔、ITT 分母、strata 分组、exact N）；用现有 r3a trace 做 CPU 端到端解析；一次 64-env targeted runtime smoke。

**Q0-DEV**：C_S2 / W_S2 / K_S2 各 LEFT/RIGHT exact128（seed 270001，共 768 集），按 128 样本门评；每候选每侧 render 3 集。

**选择规则（先于结果冻结）**：C 过则选 C；否则 W 过选 W；否则 K 过选 K；均不过 → `NO_QUALIFIED_CANDIDATE`。不得看完 CONF 再换候选。

**Q0-CONF**：仅选中候选，seed 270101 exact128/side → `BILATERAL_TEACHER_QUALIFIED_SIM` 或 `QUALIFICATION_NOT_CONFIRMED`。

**产出**：`scriptsFORhuman/v27/a2_piper_base_v27_teacher_candidate_manifest_<date>.json`（候选路径、SHA、DEV/CONF 数字、render 路径、typed outcome）。它**不是** Teacher binding；Teacher manifest 与 Student G7 binding 是否更新由 Owner 单独裁决。两种结果都完成 v27.0，都不阻塞 Wave A。

---

## 4. Wave A：v27.1 LEFT 行为对齐（Q_A；GPU2–7）

### 4.1 合同与三条 arm

共享：source = C_S2 step3000，`policy_only` + `policy_only_load_actor_rms=true`，critic/optimizer/scheduler/staged bank fresh；4096 env；3000 batches；save 250；milestones 500/1000/1500/2000/2500/3000 各 LEFT/RIGHT exact64 natural；PPO seeds 21/22。

| Arm | 唯一差异 | 依据 |
|---|---|---|
| `C` | 无 | 对照 |
| `Q1` | `a2_door_body_contact_penalty_mode: event_v17` + 三个 event 参数（5.0 / 200.0 / 2.0）+ `penalty_a2_door_body_contact` 取 v17 G5 文件中的 scale | 计价单独作用 |
| `Q2` | Q1 + v17 G5 制度：`a2_corridor_enabled: true`、G5 文件中的全部 corridor/latch 键与对应 corridor reward scale、`a2_stage4_release_hinge_threshold: 1.40` | 制度 + 计价 |

Q1/Q2 的具体键值由 worker 从 G5 文件逐键读取并列入 contract；若 G5 中 `penalty_a2_door_body_contact` 为 0 或键名不同，以 v17 resolved 语义为准并回报，不得自拟数值。除上述键外，reward 数值、stage 判据、capability、loader 一律不改。

| Cell | GPU | Cell | GPU |
|---|---:|---|---:|
| `C_S21` | 2 | `C_S22` | 5 |
| `Q1_S21` | 3 | `Q1_S22` | 6 |
| `Q2_S21` | 4 | `Q2_S22` | 7 |

### 4.2 路由（endpoint step3000）

```text
QUALITY_ALREADY_PASS      : C 两 seed 两侧均过 64 样本门                         -> RECIPE_A = C
QUALITY_ALIGNED(Q1)       : Q1 两 seed 两侧过 64 样本门，NO_REGRESS(Q1)，且 LEFT clean_complete 两 seed 均值 ≥ C + 8  -> RECIPE_A = Q1
QUALITY_ALIGNED(Q2)       : 同上条件对 Q2 成立而 Q1 不成立                       -> RECIPE_A = Q2
（Q1、Q2 同时成立取 Q1：改动更小）
QUALITY_UNRESOLVED        : 其余                                               -> RECIPE_A = C（后续 wave 不阻塞）
附加标签 Q_HARMFUL_RIGHT   : 任一 Q arm 的 RIGHT complete ≤ C − 8
```

研究载体 `CARRIER_A` = RECIPE_A 的 seed21 endpoint（不因 seed22 更好而换）。

---

## 5. Wave B（Wave A endpoint 冻结后自动启动；两条并行）

### 5.1 v27.2 门侧负载/摩擦分布（Q_B；GPU2–4）

**probe（报告，不路由）**：CARRIER_A 在 P02 与 P05（`a2_v24_friction_enabled=true`，backend `native_joint_friction_v1`，static 2/5 N·m，dynamic 0.75×static，viscous 0）各 exact32/side（seed 270201），核对 friction 参数 readback。

| Arm | 域 |
|---|---|
| `L0` | 当前域（mass 80–120，friction off） |
| `L1` | `a2_v26_door_weight_range [80,160]` + per-env static friction 从 {0, 2, 5} N·m 均匀选取（dynamic 0.75×static，viscous 0），利用 v24 per-env τ_s/τ_d/c_v 基建 |

若 per-env friction 选择在现有 backend 上一天内不可实现，默认分支 L1' = mass 80–160 + 固定 P02，记录并继续。

Cells：`L0_S31`（GPU2）、`L1_S31`（GPU3）、`L1_S32`（GPU4）；source = CARRIER_A，`policy_only` + RMS，3000 batches；milestones 1000/2000/3000。每个 milestone 每格三层评估：`nominal`（friction off，mass 80–120）、`P02`（2 N·m，mass 80–160）、`P05`（5 N·m，mass 80–160）各 exact64/side。

```text
DOMAIN_CONVERGED     : L1 两 seed 在三层两侧均过 64 样本门，且 nominal complete ≥ L0 − 4/侧   -> RECIPE_B = L1 域
DOMAIN_PARTIAL       : L1 两 seed 在 nominal 与 P02 过门、P05 未过                              -> RECIPE_B = L1 域（P05 作压力层报告）
DOMAIN_NOT_CONVERGED : 其余                                                                   -> RECIPE_B = 当前域
```

**方向 1 的测量（report-only，不改 actor）**：所有 L 格评估 trace 记录 arm joint pos/vel/target、estimated effort、base IMU（projected gravity、lin/ang vel）、hand force、hinge 角与速度；closure 附一份离线 shadow estimator（CPU，history window → static friction / mass 的回归或分类，train/heldout 按 episode 划分），只报告可辨识性（heldout R²/准确率），作为 N-02 的入口证据。

### 5.2 v27.4 单次失抓恢复环 pilot（Q_R；GPU5–7）

**语义（`a2_v27_recovery_*` 键，缺失即关闭路径 bit-identical）**：

- 触发（非计划失抓）：处于 Stage3 或 Stage4，本 episode 已达成过 K5，`both_contact` 连续 `a2_v27_recovery_loss_steps=10` 步为假，root 未 crossing（`root_x_rel ≤ 0`），且 release latch（`a2_stage4_release_hinge_threshold`）未触发。
- 进入 REGRASP：`stage_buf := 2`（观测、reward 门控、advance 条件全部复用现有 Stage2 机制），`time_in_stage_buf := 0`，episode 时钟、门/latch/机器人物理状态、RNN history 一律不动；`current_max_stage_buf` 保留高水位。`stage` / `transition` / `success_save_time` 对不高于高水位的 stage **不再支付**（高水位 mask）；Stage2 抓握 shaping 项按当前把手位姿正常支付。
- 退出：Stage2→3 用现有 K5 gate；重新进入 Stage3 后若 hinge 已越过 0.25 且 grasp streak 满足，现有 Stage3→4 条件自然生效。恢复窗口 `a2_v27_recovery_window_steps=300`，超时不额外惩罚，episode 总时限不变。每 episode 允许一次恢复（pilot 范围）。
- 训练扰动：`a2_v27_perturb_prob=0.2`，在本 episode 首次满足"K5 已达成、Stage3/4、未 crossing"时把 gripper primitive 强制 open `a2_v27_perturb_steps=4` 步，随后完全交还 policy；记录命令、接触与时间。
- R2 的失效边界 bank：REGRASP 进入时刻的物理快照（含门/latch）按侧均衡存入 bank（复用 staged-reset snapshot 机制，新增一个 bucket）；`a2_v27_recovery_bank_reset_share=0.2` 的 reset 从 bank 取样，其余按原 `staged_reset_ratios`。

| Arm | 运行时 | 训练 reset 来源 | 扰动 |
|---|---|---|---|
| `R0` | 现有单调状态机 | 原 staged reset | 有 |
| `R1` | 恢复环 | 原 staged reset | 有 |
| `R2` | 恢复环 | 80% 原分布 + 20% 失效边界 bank | 有 |

source = C_S2 step3000（研究父策略；不等 Wave A 结果），seed 41，1500 batches，GPU5/6/7；milestones 500/1000/1500。

**评估**：nominal exact64/side（不注入）；注入 exact64/side（首次满足条件时强制 open 6 步，与训练的 4 步不同）；sham exact64/side（条件满足但不注入）。注入评估的 ITT 分母为全部 64 集；未触发条件的集记 `NOT_TRIGGERED`。`regrasp_success` = 失抓后 300 步内重新达成 K5。

```text
RECOVERY_PILOT_PROMISING : R2 注入下两侧 regrasp_success ≥ 32/64 且 recovered_clean_complete ≥ 16/64，
                           nominal complete ≥ R0 − 4/侧，且 R2 − R1 的 regrasp_success ≥ 8/侧
RECOVERY_RUNTIME_ONLY    : R1 满足上一行的前两项而 R2 − R1 < 8（收益来自状态机，不来自边界采样）
RECOVERY_NO_BENEFIT      : R1、R2 均 regrasp_success < 32/64
RECOVERY_HARMFUL         : 任一 R1/R2 的 nominal complete ≤ R0 − 8/侧
```

---

## 6. Wave C：v27.3 seed 与从零可靠性（Q_C；GPU2–7；Wave A、B endpoint 后自动启动）

`RECIPE_C` = v26-7 common 合同 + RECIPE_A overlay + RECIPE_B 域。全部 `checkpoint: null`、`full`、`auto_load_latest false`，6000 batches，save 250，milestones 1000/2000/3000/4000/5000/6000 各 exact64/side（RECIPE_B 为 L1 域时按三层评估）。

| Arm | seeds | GPU | 说明 |
|---|---|---|---|
| `SC` | 201/202/203 | 2/3/4 | RECIPE_C from scratch |
| `SK` | 211/212/213 | 5/6/7 | RECIPE_C + v26-8 K 配置（§4.3 全部键、16 项名单、driver 不变）from scratch |

```text
SC: SCRATCH_3SEED_ESTABLISHED（3/3 seed 在 endpoint 两侧过 64 样本门）/ SCRATCH_SEED_UNSTABLE（1–2/3）/ SCRATCH_NOT_ESTABLISHED（0/3）
SK 对 SC（guard 用 S4+/open_hold，不用 D）:
  K_SCRATCH_SUPERIOR    : SK 过门 seed 数 > SC，或相同且 ≥2 个 seed 的首次过门 milestone 早 ≥1000，且每 seed 两侧 S4+/open_hold ≥ 同 seed 号 SC − 8
  K_SCRATCH_NONINFERIOR : 过门 seed 数相同且 S4+/open_hold 在 −8 内
  K_SCRATCH_INFERIOR    : 其余
```

预算固定，不追加救援 seed，不挑中途 best 作 endpoint；六格跑满。

---

## 7. v27.5 收口

- 最终确认：对 SC 中首个过门的 seed（并列取最小 seed 号）与 v27.0 选中候选各做 exact128/side（seed 270303，RECIPE_B 分层），写入候选 manifest 第二版；Teacher/G7 binding 仍由 Owner 裁决。
- closure：`scriptsFORhuman/v27/a2_piper_base_v27_execution_closure_<date>.md`：v27.0 资格、Q_A/Q_B/Q_R/Q_C typed outcomes、逐格逐侧表与配对差、shadow estimator 可辨识性、未运行事项、证据等级、changed paths、资源状态。
- 若 `RECOVERY_PILOT_PROMISING` 或 `RECOVERY_RUNTIME_ONLY`：closure 附 v28 提案骨架（N-01 多 seed 确认 × N-02 history latent 的 2×2）；不自动运行。
- memory：新建 `memory/a2-piper/base-v27-bilateral-hardening/`（description/TODO/DONE），v26 entry 状态改为 closed；按 wave 更新。

---

## 8. 实现范围（最小充分）

1. `gr00t/rl/config/ablation/wbmanip/base_v27_*.yaml`：common、Wave A 六格、Wave B 六格、Wave C 六格、eval overlays（strata、perturb 模式）。
2. `gr00t/rl/envs/door/door_open_a2_base.py`：`a2_v27_recovery_*`（REGRASP 转移、高水位 mask、bank bucket、扰动注入、telemetry）与 per-env friction 选择（若需要）；键缺失时默认路径 bit-identical；不改 reward 函数数值与 stage 判据。
3. `scriptsFORhuman/v27/`：`v27_orchestrate.sh`、`v27_train_cell.sh`、`v27_eval_cell.sh`、`v27_eval_lane.sh`、`v27_reduce.py`、`v27_verify.py`、`v27_shadow_estimator.py`（CPU）；以 v26-8 r3a 脚本为模板，receipt 显式 proxy env，`P0_ASSETS` preflight。
4. `gr00t/rl/tests/test_a2_v27_*.py`：clean_complete/ITT/strata、REGRASP 转移与高水位 mask、bank 取样比例、扰动注入步数、friction readback、legacy 路径 bit-identical。
5. 禁止：改 v26-x 脚本或 artifact；改 trainer loader；改 reward 函数逻辑；为测试在核心路径加 hook；fallback/宽容分支。

---

## 9. 自主决策权与失败预案（Codex Main 无需等待 Owner 的事项）

1. policy 读数产生前的失败（基础设施、代理、资产、harness 断言、接线缺陷）：自主修复并重启，上限 2 次/格，只需通知；修复带 contract lock diff，实验合同零改动。
2. policy 读数产生后的非零退出：停该格、其余继续、不重跑、不等待。
3. milestone 读数只汇报不审批；§3–§6 的 typed outcome、RECIPE 选择与 wave 转换按预注册条件自动执行；启动下一 wave 前通知 Owner，Owner 未在启动前否决即继续。
4. 默认分支：Q_A 未决 → RECIPE_A=C；per-env friction 不可行 → L1'；Q_B 未收敛 → RECIPE_B=当前域；Q_R 任何结果都不影响 Wave C。
5. 预授权四个本地 commit 点：v27.0 完成 + Wave A G0 后；Wave A endpoint 后；Wave B 两个 endpoint 后；closure 后。不 push。
6. 必须等 Owner 的四类事：改预注册阈值或路由；超出 §10 预算；改 reward/stage/loader 语义超出 §8；Teacher/Student/G7 binding、hardware。
7. 向 Owner 提问后若 12 小时内无回复且 plan 有默认分支，按默认分支继续并记录。
8. GPU 上其他任务的显存占用只记录不处置；任何 GPU 可用性以启动时实际余量为准。

---

## 10. 资源与时间

```text
v27.0  : GPU0–1 评估 768 + 256 集 + render ≈ 4–6 h（与 Wave A 并行）
Wave A : 6 × 3000 batches ≈ 20 h；6 milestones × 12 lane
Wave B : 3 × 3000 + 3 × 1500 batches ≈ 20 h；L 格每 milestone 6 lane，R 格 nominal/注入/sham
Wave C : 6 × 6000 batches ≈ 40 h；6 milestones × 12（或 36）lane
总训练上限 67,500 batches；另允许每个 wave 一次 ≤32 batch 接线 smoke。
```

任一格非零退出即停止该格并保留证据：不重跑、不放宽阈值、不中途改 config、不追加预算。

---

## 11. 结论边界

- v27 对 Q_A/Q_B/Q_C 给 experiment 证据，对 Q_R 只给 pilot 证据（单 seed，不构成方法获胜）。
- 不构成 hardware、sim-to-real 或部署证据；Teacher/G7 binding 由 Owner 裁决。
- `QUALITY_UNRESOLVED`、`DOMAIN_NOT_CONVERGED`、`SCRATCH_SEED_UNSTABLE`、`RECOVERY_NO_BENEFIT` 都是合法结果，不是追加预算的理由。
- 方向 1 的可辨识性只由 shadow estimator 报告，不外推为"策略已实时适应"。

---

## 12. 交付物

训练 receipt（source lock、SHA、proxy env、preflight）；每 milestone reducer；候选 manifest 两版；closure；memory 三文件；四个本地 commit；changed paths 清单。
