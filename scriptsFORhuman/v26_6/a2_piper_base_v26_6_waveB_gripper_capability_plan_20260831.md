# A2+PiPER `base_v26-6` Wave B — 夹爪能力 × unlatch 墙移除 四格矩阵

**预注册时间：** 2026-08-31（四格启动前冻结）
**状态：** PREREGISTERED
**上游：** Wave A，typed route `GRIPPER_CAPACITY_CONFIRMED`
**上游合同：** `a2_piper_base_v26_6_waveA_gripper_capacity_plan_20260831.md`

## 1. 立论

Wave A 已用固定 policy 的 eval-only 单因素 A/B 证明夹爪执行能力是 handle 保持的
因果瓶颈，但同时暴露两件事：

1. 恢复能力后 44/64 episode 能把 handle 按在 `>0.6 rad` 达 p50 `64`、max `187`
   control step，`hinge` 仍 `≤0.0111`，64/64 `stage_overtime`；
2. per-step 收入为 Stage2 滞留 `0.28939` vs Stage3 按住 `0.19655`，且 Stage3 内最大项
   `a2_stage3_unlatch_hold`（`0.0599/step`）以 `hinge < 0.1` 为条件，替代它的
   `push_door_hinge + hold_and_drive` 只有 `0.0090/step`。

Wave A 用的是在 `10 N` 下训练、从未在恢复能力下更新过的 policy，因此"门不动"既可能
是没学过，也可能是收入结构不允许。Wave B 用一次四格 matched 矩阵同时回答。

## 2. 矩阵与唯一自变量

四格全部从 `logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/
V26A_LR_S1_POLICY800/model_step_002000.pt`（`CONT_STEP2000`）以
`policy_only` + `policy_only_load_actor_rms=true` 启动，基座 selector 为
`base_v26_4_C0_CANONICAL_OFF`（v26-4/v26-5 共同祖先，plain recurrent actor，
未采用 v26-5 的 geometry target 与 residual actor；前者 typed 为
`ACQUISITION_INCONCLUSIVE`，后者为 `KILL_RESIDUAL_ACQUISITION_REGRESSION`）。

| cell | GPU | seed | `GRIPPER_CAPABILITY_BUNDLE` | `a2_stage3_unlatch_near_closed_hinge_threshold` |
|---|---:|---:|---|---:|
| `B0_S0` | 4 | 0 | 启用 | `0.1` |
| `B0_S1` | 5 | 1 | 启用 | `0.1` |
| `B1_S0` | 6 | 0 | 启用 | `0.25` |
| `B1_S1` | 7 | 1 | 启用 | `0.25` |

`B0 → B1` 的 config 差异**只有一个键**（selector `base_v26_6_waveB_B1.yaml` 只覆盖
`a2_stage3_unlatch_near_closed_hinge_threshold`），因此该轴是单因素。
`GRIPPER_CAPABILITY_BUNDLE` 相对 v26-4 C0 的差异与 Wave A 完全一致：
effort `45/45 N`、Kp/Kd `1300/32`、`a2_m39_gripper_material_enabled=true`、
squeeze 上界 `30`、over-force `55`；`a2_stage2_squeeze_force_min` 保持 `0.5`。

其余全部冻结：reward scale（`push_door_handle=0`、`a2_stage3_handle_creation=6`、
`unlatch_hold=3`、`push_door_hinge=6`、`hold_and_drive=8`）、
`a2_stage3_to4_door_hinge_threshold=0.25`、K5、door 分布、staged reset、
`800/25 → 1300/32` 只作用于 j7/j8、PhysX velocity iterations 2、
4096 env、750 batches、save 250。

Wave B **不**改 Stage2→Stage3 的收入悬崖；v19 在同样的悬崖下做成过全链，因此该轴
留作独立 wave，避免与本矩阵混杂。

## 3. 准入前置

64-env × 2-batch smoke（`v26_6_waveB_smoke.sh`，B0 selector，GPU4）已完成
`PASS/0`，产出 `model_step_000002.pt`，runtime 注册了 `m39_gripper_material`
startup event，saved config 为 `45/45`、`1300/32`、M39 `true`、窗口 `30/55`。
artifact：`logs_rl/by_batch/base_v26/v26_6_waveB_gripper_capability_20260831/smoke/B0`。

每个训练 cell 在真实训练前先写 `resolved_config.yaml` 并对
capability bundle 与 near-closed seam 做 fail-fast 断言。

## 4. 评估

每格 3 个 checkpoint（`250/500/750`）× LEFT/RIGHT × exact 64 natural episode，
共 24 次评估，`enable_staged_reset=false`，first-episode-only。每格在自己的
checkpoint-adjacent config 下评估，因此 near-closed 随 cell 走；stage transition
不依赖该阈值，读数因此可比。

## 5. 预注册读数与阈值

以 `step750` 为 endpoint。durable 下压定义为**连续 `≥25` 个 control step 保持
`handle ≥ 0.6 rad`**（Wave A 中 restored/right 的 p50 为 64 step，10 N 对照为 0）。

```text
DURABLE_MIN   = 32/64 每侧      （durable 下压门）
STAGE4_MIN    =  2/64 每侧      （unlock 门，hinge>=0.25 触发的 stage4）
```

typed route（按顺序判定）：

```text
任一完整性失败                                     -> WAVE_B_INVALID
B0/B1 均无任一侧 durable 下压 >= 32                -> DURABLE_DEPRESSION_NOT_LEARNED
B1 双侧 stage4 >= 2 且 B0 未达                     -> WALL_REMOVAL_CAUSAL_BILATERAL_STAGE4
B0 或 B1 双侧 stage4 >= 2                          -> BILATERAL_STAGE4_SUPPORTED
B1 有 stage4 且 B0 无                              -> WALL_REMOVAL_DIRECTIONAL_STAGE4_UNSTABLE
B0 或 B1 有任一 stage4                             -> STAGE4_SEED_OR_SIDE_UNSTABLE
其余                                               -> DEPRESSION_LEARNED_STAGE4_NOT_REACHED
```

完整性：每格每侧 exact 64 episode；`integrity_violations` 为 `0`；四格
resolved config 必须满足 capability bundle 与各自的 near-closed 值，seed 与 cell 名
一致。任一不满足即 `WAVE_B_INVALID`。

同时报告但不参与路由：按 `door_handle_drive_max_force` 的三分层 durable 下压与
`hinge≥0.25` 计数、`hinge≥0.1`、stage5/goal、终止原因分布、durable run 长度分位。

## 6. 结论边界

- `WALL_REMOVAL_CAUSAL_BILATERAL_STAGE4` 只对"在恢复夹爪能力后，`0.1→0.25` 是否
  造成 Stage4"给出 experiment 证据，不构成 goal、Teacher 准入或 hardware 证据。
- `DEPRESSION_LEARNED_STAGE4_NOT_REACHED` 不证明墙无因果；它表明在 750 batches、
  当前 Stage2→3 收入悬崖下未跨过，下一步应处理收入结构而非继续加力。
- LEFT 侧若持续落后于 RIGHT，归入 v26-4 `BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`，
  不在本 wave 内解释。
- 本 wave 不更新 Teacher/Student handoff 与 G7 binding。

## 7. 资源与停止条件

GPU4–7，每格独立 tmux 与 run receipt，`CUDA_VISIBLE_DEVICES` 限定单卡、进程内
`cuda:0`。按 v26 实测约 `20.3 s/update` 估计每格约 4.4 小时墙钟，四格并发；
随后 24 次评估在同四卡上分批完成。任一格非零退出即停止该格并保留失败证据，
不重跑、不放宽阈值、不中途改 config。
