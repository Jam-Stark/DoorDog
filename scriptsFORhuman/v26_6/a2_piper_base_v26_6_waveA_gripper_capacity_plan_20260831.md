# A2+PiPER `base_v26-6` Wave A — 夹爪保持能力 eval-only A/B

**预注册时间：** 2026-08-31（运行前冻结）
**状态：** PREREGISTERED
**上游：** `v26-5 wave2 R1 R15`，typed route `KILL_RESIDUAL_ACQUISITION_REGRESSION`
**性质：** eval-only，单因素，不训练、不改 reward、不改 threshold、不改 policy

## 1. 立论

R15 的 runtime 证据表明"policy 学不会下压 handle 解锁"这个描述不成立：
`R15_S1/model_step_000250` 在 RIGHT 的 64 条自然 episode 中有 16 条把 handle
压到 `0.785398 rad` 硬限位。真正的边界是**压下去之后握不住**——handle 被回位
弹簧顶回，`arm_j8` 被撬到 `-0.035` 全开限位，latch 重新咬合，hinge 全体停在
`≤ 0.0024 rad`。

按门本身的 handle 回位扭矩 `door_handle_drive_max_force` 分层（同一 checkpoint、
同一 seed、同一 eval）：

| `handle_drive_max_force` | n | `max_handle_rad ≥ 0.3` |
|---|---:|---:|
| `[1.0, 1.6)` | 21 | 15 |
| `[1.6, 2.2)` | 27 | 1 |
| `[2.2, 3.0]` | 16 | 0 |

训练门分布是 `handle_drive_max_force_range=(1.0, 3.0)`。policy 观测不到该参数，
因此这条锐利分界只能解释为执行能力上限。

同一 door asset 家族上的历史正对照 `logs_eval/base_v19/G3_m22/
base_v19_G3_m22_targeted_repair_r4_20260727/model_step_002500/seed0`：16/16 env
到 stage5，`max_handle_rad` 为 `0.594–0.785`，`max_hinge` 为 `1.34–2.09 rad`，
其中包含 `drvF = 2.77 / 2.75 / 2.50 / 2.43` 四扇门。

下压期间 handle 接触力：

| lineage | 合力 p50 | 受力手指 |
|---|---:|---:|
| v19 G3 step2500 | `28.6 N` | `~21.6 N` |
| v26-5 R15 S1 RIGHT | `16.8 N` | `~10.5 N`（钉在 effort limit） |

## 2. 已核对的 resolved-config 差异

| 项 | v18–v25 与 pull（解锁成立） | v26 → v26-5（从未成立） |
|---|---|---|
| `robot.dof_effort_limit_list` arm_j7/j8 | `45.0 / 45.0` | `10.0 / 10.0` |
| `robot.control.stiffness` arm_j7/j8 | `1300.0` | `80.0` → `800.0` |
| `robot.control.damping` arm_j7/j8 | `32.0` | `3.0` → `25.0` |
| `env.config.a2_m39_gripper_material_enabled` | `true`（指垫 static `1.1` / dynamic `0.9`） | `false` |
| `env.config.a2_stage2_squeeze_force_max` | `30.0` | `20.0` |
| `env.config.a2_stage2_over_force_threshold` | `55.0` | `40.0` |
| `dof_effort_limit_list` arm_j1–j6 | `40.0`（v25） | `100.0` |

证据路径：`logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/V25_FULL_S0/config.yaml`
与 `logs_rl/by_batch/base_v26_acquisition_supplement_20260823/formal/V26A_LR_S1/config.yaml`。
v26 从未覆盖 `dof_effort_limit_list`，直接继承 `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml`
的 `10.0 / 10.0`。`Kp × 最大几何行程 = 800 × 0.035 = 28 N`，被 `10 N` cap 截断；
`1300 × 0.035 = 45.5 N`，不被截断。

`a2_stage2_squeeze_force_max` 与 `a2_stage2_over_force_threshold` 只进入
`a2_stage2_squeeze_force_window` / `a2_stage3_stage4_squeeze_force_window` 奖励
与 `penalty_a2_*_over_force`；K5 gate 的谓词是
`both_contact & sufficient_squeeze(> squeeze_min) & opposite_squeeze`（源：
`door_open_a2_base.py::_update_a2_grasp_control_streaks` 与
`_get_a2_stage2_contact_squeeze_masks`），不含上界与 over-force。因此提高夹持力
不改变 K5 gate 语义，但若不同步放开上界，reward 会反向惩罚被放开的能力。

v26-3 §10 的 F effort ladder 之所以得出 `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`，
是因为它是 eval-only、使用在 `10 N` 下训练出的 checkpoint、且按计划"只改 j7/j8
effort cap"，保持 `over_force_threshold=40`、M39 关闭。该结论不构成容量证据，本
wave 不继承它作为禁令。

## 3. 本 wave 唯一自变量

`GRIPPER_CAPABILITY_BUNDLE`（仅 `restored` 臂启用）：

```text
++robot.dof_effort_limit_list=[...,100.0,100.0,100.0,100.0,100.0,100.0,45.0,45.0]
++robot.control.stiffness.arm_j7=1300.0
++robot.control.stiffness.arm_j8=1300.0
++robot.control.damping.arm_j7=32.0
++robot.control.damping.arm_j8=32.0
++env.config.a2_m39_gripper_material_enabled=true
++env.config.a2_stage2_squeeze_force_max=30.0
++env.config.a2_stage2_over_force_threshold=55.0
```

刻意偏离 v25 精确 parity 的一项：保持 `a2_stage2_squeeze_force_min=0.5`（v25 为
`2.0`）。抬高下界会收紧 K5 gate 谓词本身，属于第二个自变量，本 wave 不引入。
arm_j1–j6 effort 保持 v26 的 `100.0`，同理。

其余全部冻结：checkpoint、seed、num_envs、episode 数、reward scale、
`a2_stage3_unlatch_near_closed_hinge_threshold=0.1`、stage threshold、door 分布、
K5、observation、residual actor 结构、`enable_staged_reset=false`。

## 4. 单元

checkpoint 固定为
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260831_r15/train/R15_S1/model_step_000250.pt`，
seed `1`，每格 exact 64 自然 episode。

| cell | GPU | arm | side | 作用 |
|---|---:|---|---|---|
| `control/right` | 6 | control | right | 决定性复现对照；与 R15 retry1 现有 artifact 比对 |
| `restored/right` | 4 | restored | right | **主读数** |
| `restored/left` | 5 | restored | left | 探索性 |

输出根：`logs_eval/base_v26/v26_6_waveA_gripper_capacity_20260831/`。
launcher 在输出根已存在时失败退出，不覆盖既有 artifact。

LEFT 的对照（`R15_S1_STEP0250/left`）在 control 下三个分层全为 `0/64`，即 LEFT
本来就没有下压行为。因此 LEFT **不能**用来测容量，只作为"单纯加力是否诱发下压"
的探索观察，不参与 typed route。

## 5. 预冻结对照数值

`R15_S1_STEP0250`，来自 `formal_eval_retry1`：

```text
RIGHT  drvF[1.0,1.6): 15/21   [1.6,2.2): 1/27   [2.2,3.0]: 0/16   合计 16/64
LEFT   drvF[1.0,1.6):  0/21   [1.6,2.2): 0/27   [2.2,3.0]: 0/16   合计  0/64
RIGHT  Stage3 admission 60/64、K5>0 60/64、hinge>=0.1 0/64
LEFT   Stage3 admission 64/64、K5>0 64/64、hinge>=0.1 0/64
```

## 6. 完整性门

1. `control/right` 与 `restored/right` 的 per-env
   `(door_handle_drive_max_force, door_weight, door_handle_height, door_open_lr)`
   必须逐项 exact 相等，否则 `DOOR_SAMPLING_NOT_MATCHED` 直接失败；
2. `control/right` 与既有 `formal_eval_retry1/R15_S1_STEP0250/right` 的门参数向量
   必须 exact 相等；`max_handle_rad` 向量差异作为决定性复现观察记录，不作硬门；
3. 各格 `integrity_violations` 必须为 `0`。

## 7. 预注册 typed outcome

主读数为 `restored/right` 在 `drvF > 1.6` 分层（n=43，control 为 `1/43`）中
`max_handle_rad ≥ 0.3` 的 episode 数，记为 `H`；Stage3 admission 记为 `S`。

```text
S < 48/64                    -> TREATMENT_GRASP_GATE_REGRESSION（容量问题 inconclusive，
                                升级为无策略的 scripted 夹持探针）
S >= 48/64 且 H >= 22        -> GRIPPER_CAPACITY_CONFIRMED
S >= 48/64 且 5 <= H < 22    -> GRIPPER_CAPACITY_PARTIAL
S >= 48/64 且 H < 5          -> GRIPPER_CAPACITY_NOT_CONFIRMED
```

同时报告但不参与路由：`≥0.6` 分层计数、`max_hinge ≥ 0.1 / ≥ 0.25` 计数、
下压期 handle 接触力 p50、over-force 步占比、contact stability、LEFT 全部读数。

## 8. 结论边界

本 wave 只能对"在固定 policy 下，夹爪能力是否是 handle 保持的因果瓶颈"给出
runtime 证据。它**不**证明：

- 重训后能形成稳定双侧 unlatch；
- Stage4 / goal 可达；
- `a2_stage3_unlatch_hold` 在 `hinge < 0.1` 上的驻留收入不再是障碍；
- LEFT/RIGHT 的 `BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET` 已解决；
- 任何 hardware / sim-to-real 结论。

policy 是在 `10 N` 下训练的，`restored` 臂下的 Stage0–2 行为存在分布外风险；
因此只有阳性结果是强证据，阴性结果按 §7 升级为无策略探针，不据此宣称容量无因果。

## 9. 执行关闭 — 2026-08-31

三格 supervisor 均 `PASS/0`，reducer 为
`logs_eval/base_v26/v26_6_waveA_gripper_capacity_20260831/reducer.json`。

完整性门全部通过：三格门参数向量与冻结对照 exact 相等；`control/right` 复跑与
`formal_eval_retry1/R15_S1_STEP0250/right` 的 per-env `max_handle_rad`
**bit-exact**（`max_abs_delta = 0.0`），因此 A/B 是构造上匹配的单因素比较；
各格 integrity violations 为 `0`。

Typed route：**`GRIPPER_CAPACITY_CONFIRMED`**（`H = 28 ≥ 22`，`S = 63 ≥ 48`）。

| cell | `[1.0,1.6)` | `[1.6,2.2)` | `[2.2,3.0]` | 合计 ≥0.3 | 合计 ≥0.6 | Stage3 准入 |
|---|---:|---:|---:|---:|---:|---:|
| `control/right` | 15/21 | 1/27 | 0/16 | 16/64 | 16/64 | 60/64 |
| `restored/right` | 20/21 | 23/27 | 5/16 | 48/64 | 44/64 | 63/64 |
| `restored/left` | 0/21 | 0/27 | 0/16 | 0/64 | 0/64 | 62/64 |

支撑量：下压期 handle 接触力 p50 `16.8 N → 33.0 N`（p90 `19.8 → 37.7`，v19 参照
`28.6 N`）；最长持续下压 p50 `0 → 91` control step、max `72 → 235`；下压步数
`1160 → 5898`；over-force 步占比 `0`；Stage3 准入 `60 → 63`。

因此 `drvF ≤ 1.6 N·m` 的锐利边界由夹爪执行能力造成，v26-3 的
`ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE` 在本证据下不成立为容量结论。

### 9.1 恢复能力后仍未解决的部分

Stage4、goal、`hinge ≥ 0.1` 在三格中仍全为 `0`；`max_hinge` 由 `0.0024` 升到
`0.0111 rad`，全部 64 条 episode 终止原因均为 `stage_overtime`。44 条 episode 把
handle 稳定按在 `> 0.6 rad` 长达 p50 `64`、max `187` control step，门却不动，且
Stage2 滞留中位数为 `408` control step。

per-step 收入分解（`restored/right`，n=26110 / 3307）：

```text
                                         stage2 滞留   stage3 按住>0.6
a2_stage2_handle_center_y                   0.11876  ->   0.00000
a2_stage2_handle_approach_xz                0.05861  ->   0.00000
grasp_target_distance                       0.05722  ->   0.03888
a2_stage3_unlatch_hold                      0.00000  ->   0.05991
a2_stage3_handle_creation                   0.00000  ->   0.01919
a2_stage3_stage4_hold_and_drive             0.00000  ->   0.00626
push_door_hinge                             0.00000  ->   0.00275
合计                                        0.28939  ->   0.19655   (-0.09283)
```

即：Stage2→Stage3 存在 `-0.093/step` 的收入悬崖，且 Stage3 内最大项
`a2_stage3_unlatch_hold`（`0.0599/step`）以 `hinge < 0.1` 为条件——把门推开会摧毁
它，而替代它的 `push_door_hinge + hold_and_drive` 合计仅 `0.0090/step`。这与本项目
已四次记录的 stationary rent / income cliff 同形。

门本身在解锁后是自由的：v26-3 U-probe 在 handle `0.5 / 0.6 rad` 时得到 hinge
`0.0478 / 0.1443 rad`（`STATIC_FIXTURE_LOCK_NOT_SUPPORTED`），且本 wave 中
`door_body_panel_normal_force_total` 在保持期为 `0`，说明机器人根本没有施加开门力。

`restored/left` 三个分层仍为 `0/64`，与预注册一致：LEFT 本就没有下压行为，单纯加力
不诱发它，该轴属于 v26-4 的 `BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`。

## 10. 后续（本 wave 不执行，需另行批准）

1. Wave B：从 `CONT_STEP2000` 用 `GRIPPER_CAPABILITY_BUNDLE` 双 seed 重训 750
   batches，全 checkpoint 双侧 exact64 natural eval；
2. Wave C（条件）：若 durable 下压成立但 hinge 仍停在 `< 0.1`，启用 pull-v2-W
   已注册的 `a2_stage3_unlatch_near_closed_hinge_threshold: 0.1 -> 0.25`；
3. Stage2→Stage3 收入悬崖（Stage2 滞留每步约 `0.294`，Stage3 保持每步约 `0.141`）
   作为独立 axis，另行设计。
