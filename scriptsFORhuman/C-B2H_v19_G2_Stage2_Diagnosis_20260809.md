# C-B2H v19 fixed-G2 多 seed 与 Stage2 诊断批次报告

**日期：** 2026-08-09 HKT

**评估对象：** ToeOut6 / pitch−50° / step8000 C-B2H Student，与 matched true-action Teacher

**口径：** 16 env、每 env 一次完整 episode；正式指标优先，diagnose/render replay 只用于定位与敏感性检查

## 技术结论：视觉迁移成立，当前不应启动泛化续训

- **fixed-G2 正式基线已经把问题从 Stage0 收敛到少量、非稳定的后续失败。** true-action Teacher 在 seed0、seed1 均为 `16/16`；pure Student 在 seed0/1/2 分别为 `13/16`、`16/16`、`13/16`，合计 `42/48 = 87.5%`。
- **matched Stage2 证据把 seed0 的精确失败定位为 bilateral contact / squeeze continuity，而不是 contract drift、没有闭合指令或夹爪无法物理闭合。** env4 的 Student 出现 close command、physical stable close、双侧接触与 squeeze window，但有效连续 streak 最多只有 `2`，未达到 contract 要求的 `5`；同 case Teacher 在 `t=160` 达到 streak `5` 并完成 Stage2。
- **C-B2H 双 D435 视觉路径与 camera migration 在本批次可以接受。** env4/env6/env9 的左右并排视频中，handle 在两路 D435 内持续可见；遮挡是夹爪/手臂靠近 handle 时的局部 self-occlusion，不是整段视野丢失或 camera blind spot。
- **停止条件是“不 full retrain，也不启动 generic 1–2k continuation”。** 同 seed0 的正式、diagnose 与 render replay 在 `13/16`、`14/16`、`15/16` 之间变化，env9 甚至从 formal success 变为 render replay 的 Stage2 timeout；failure set 也不跨 seed 稳定。若后续 finetune，只应是针对 Stage2 contact-continuity 的 DAgger/closed-loop 数据方案，并先单独提交 `HIGH_RISK` brief。

以上是 bounded diagnostic closure，不是 determinism、general policy、deployment 或 physical-camera validation PASS。

## 1. 评估口径与 fixed-G2 contract

本报告的 `goal` 分母是每个 seed 的 `16` 个 randomized cases，每个 env 只统计第一条完成 episode。Student 是 `enforce_teacher_rollout=false / ratio=0.0` 的 pure Student；Teacher 是 `enforce_teacher_rollout=true / ratio=1.0` 的 true-action route。所有评估均为 `training_performed=false`、`optimizer_step_count=0`。

sealed G2 Stage0 predicate 为：

```text
0.50 <= dx <= 0.80
abs(dy) < 0.15          # strict y boundary
arm max deviation < 0.10
physical base command norm <= 0.10
```

seed0 Teacher evidence 还确认 high-level action source 为 `gt_actions`、Student rollout calls 为 `0`，且 16 个 env 都发生 Stage0→1 transition。核心证据：

- [Teacher seed0 G2 replay summary](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_g2contract_20260809/teacher_seed0_gpu4_retry02/g2_contract_teacher_replay_summary.json)
- [Teacher seed1 formal metrics](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_g2contract_multiseed_20260809/teacher_seed1_gpu4/formal_teacher_metrics.json)
- [Student seed0 formal metrics](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_g2contract_20260809/student_seed0_gpu5/formal_student_metrics.json)
- [Student seed1 formal metrics](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_g2contract_multiseed_20260809/student_seed1_gpu4/formal_student_metrics.json)
- [Student seed2 formal metrics](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_g2contract_multiseed_20260809/student_seed2_gpu5_retry03/formal_student_metrics.json)

## 2. 多 seed 正式基线：Student 为 42/48，失败集合不重叠

### Teacher true-action ceiling

| Seed | Goal | Max-stage / terminal | 结论 |
| ---: | ---: | --- | --- |
| 0 | `16/16` | 全部 stage5 / `complete` | fixed-G2 true-action PASS |
| 1 | `16/16` | 全部 stage5 / `complete` | fixed-G2 true-action PASS |

Teacher 的 `32/32` 说明 fixed-G2 与后续 stage contracts 能在这两个 matched seeds 上闭合；它不构成更多 seed 或 general policy ceiling 的证明。

### Student formal baseline

| Seed | Goal | Failure env | Failure max stage | Failure terminal |
| ---: | ---: | --- | --- | --- |
| 0 | `13/16` | `{4, 6, 9}` | `2, 2, 2` | 全部 `stage_overtime` |
| 1 | `16/16` | `{}` | — | — |
| 2 | `13/16` | `{8, 12, 14}` | `2, 1, 0` | 全部 `stage_overtime` |
| **合计** | **`42/48 = 87.5%`** | **6 个 failure** | — | — |

seed0 与 seed2 的 failure env **没有交集**。因此当前证据支持“少量 stochastic / non-stable failures”，不支持把某几个 randomized cases 解释为固定 hard negatives，也不支持把 `64 env` 或 step8000 本身判为根因。

## 3. 同 seed0 replay variation：正式指标优先

| 运行 | Goal | Failure 摘要 | 证据角色 |
| --- | ---: | --- | --- |
| fixed-G2 formal baseline | `13/16` | env4/6/9 均 Stage2 timeout | 正式 baseline |
| R3 diagnose | `14/16` | env4 Stage2、env9 Stage4 timeout | diagnosis sensitivity |
| R4 diagnose | `15/16` | 仅 env4 Stage2 timeout | matched trace source |
| R4 formal | `15/16` | 仅 env4 Stage2 timeout | R4 正式复核 |

对应证据：

- [R3 diagnose metrics](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/student_seed0_gpu5/metrics_eval.json)
- [R4 diagnose summary](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/student_seed0_gpu5_retry02/student_stage2_diagnostic.json)
- [R4 formal metrics](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/student_seed0_formal_r4_gpu4/formal_student_metrics.json)

R4 render 进一步给出反例：env9 在 R4 formal 中是 stage5 / `complete`，但 render replay 变为 Stage2 / `stage_overtime`。因此视频只能解释“这一次 replay 看到了什么”，不能覆盖 formal 指标，也不能把 same-seed replay 说成 deterministic。

## 4. Matched Stage2：差异只落在连续双侧接触/挤压力

`t` 是 trace 中 `stage2_completion_actual_time_in_stage` 的 control-step 计数；Stage2 完成要求连续 streak `5`。

| Env | Student R4 diagnose | Teacher matched diagnose | 判读 |
| ---: | --- | --- | --- |
| 4 | max streak `2`；无 Stage2 completion | streak `5`，`t=160` 完成 | Student 有事件但不能连续维持 |
| 6 | streak `5`，`t=108` 完成 | streak `5`，`t=151` 完成 | Student 不弱于 Teacher 的该次完成路径 |
| 9 | streak `5`，`t=219` 完成 | streak `5`，`t=161` 完成 | Student 能完成，但更慢且 replay 敏感 |

matched traces：

- [Student R4 Stage2 trace](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/student_seed0_gpu5_retry02/stage2_step_trace.json)
- [Teacher matched Stage2 trace](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/teacher_seed0_gpu4/stage2_step_trace.json)
- [Teacher matched terminal metrics](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/teacher_seed0_gpu4/metrics_eval.json)

Student 与 Teacher trace 的静态 Stage2 contract 完全一致：

```text
gate_mode                  control_streak
history_length             5
required_streak            5
contact_force_threshold    1.0
squeeze_force_window       [0.5, 20.0]
over_force_threshold       40.0
close_command_threshold    -0.2
close_progress_threshold   0.45
```

Teacher `16/16` 且三项 matched cases 都通过同一 contract，排除了“Student 被不同 Stage2 gate 阻挡”的 contract drift 解释。env4 Student trace 中至少一次出现 close command、physical stable close、both-contact、sufficient/opposite squeeze 和 squeeze-window；但这些条件只形成最大连续 streak `2`，没有达到 `5`。因此 exact failure 是 **bilateral contact / squeeze continuity**，不是 close command 缺失、夹爪不闭合或阈值只对 Student 改变。

## 5. Render 目视：handle 可见，遮挡是局部 self-occlusion

| Env | 左右 D435 并排视频 | Replay outcome | 目视结论 |
| ---: | --- | --- | --- |
| 4 | [side-by-side env4](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/renders/env04_student_gpu4/policy_camera_videos/d435_left_right_side_by_side_env0004.mp4) | Stage2 timeout | handle 在两路均可见；夹爪接近时局部遮挡 |
| 6 | [side-by-side env6](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/renders/env06_student_gpu5/policy_camera_videos/d435_left_right_side_by_side_env0006.mp4) | stage5 / complete | handle 可跟踪；完整通过 |
| 9 | [side-by-side env9](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/renders/env09_student_gpu5/policy_camera_videos/d435_left_right_side_by_side_env0009.mp4) | formal success → replay Stage2 timeout | handle 仍在两路视野内；结果发生 replay drift |

render metadata：

- [env4 render metadata](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/renders/env04_student_gpu4/selected_render_metadata.json)
- [env6 render metadata](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/renders/env06_student_gpu5/selected_render_metadata.json)
- [env9 render metadata](../logs_eval/by_batch/cb2h_v19_toeout6_pitch50_stage2diag_20260809/renders/env09_student_gpu5/selected_render_metadata.json)

三段 side-by-side 分别为 `432×384 @ 20 fps`；env4/env6/env9 为 `452/641/452` frames。逐段均检查了全程均匀抽帧。共同现象是 handle 没有从左右 D435 同时消失，主要视觉干扰来自抓取邻域内的 arm/gripper 自遮挡。因此本批次支持 C-B2H visual path/camera migration 已成功，不支持把 env4 的 Stage2 continuity failure 归因于全局 handle visibility。该结论仍不替代 real-camera calibration、latency、exposure、mechanical clearance 或 deployment 验证。

## 6. G2 propagation audit：训练路径已继承 band，不需要外部 mutation

### 当前 Student/distillation worktree

以下 training/default configs 都直接声明 `0.50 / 0.80 / 0.15`，不是依赖运行时修补：

- [base env config](../gr00t/rl/config/env/door_open_a2_base.yaml)
- [C-B2H v19 config](../gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm.yaml)
- [P2 B1 config](../gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_p2_b1.yaml)
- [P2 B2 config](../gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_p2_b2.yaml)

[A2 env implementation](../gr00t/rl/envs/door/door_open_a2_base.py) 对 A2 route 原生计算 x-band、strict y tolerance、arm deviation 与 physical base-still predicate；[ToeOut6 eval runner](../gr00t/rl/scripts/run_a2_toeout6_student_eval.py) 还显式注入并验证相同三项 effective config。结论是当前训练与评估路径继承 fixed-G2 contract，没有残留的 A2 `.70` point gate，也不需要修改外部 worktree 才能维持本批次行为。

### A2-Piper mainline 与 separate scope

[A2-Piper mainline default config](../../DoorDog-A2_Piper/gr00t/rl/config/env/door_open_a2_base.yaml) 已经使用 band contract，只是当前默认较窄：`0.55 <= dx <= 0.60`、`abs(dy) < 0.15`。所以 mainline 不存在需要紧急修复的坏 point gate，本批次不做 external mutation。

`hold_handle` / non-A2 branch 仍保留 `non_a2_stage0_staging_x_offset: 0.70`，并围绕该 offset 使用原有 strict `0.1m` point-distance gate；这是 separate scope，不应借本次 A2 G2 closure 顺手改写。

### Trainer import 应独立提交

[train_agent_trl.py](../gr00t/rl/train_agent_trl.py) 的 `import math` 是已有 DDP proof 路径调用 `math.isfinite` 所必需；它与 G2/Stage2 semantics 无关，应作为 standalone commit 处理，避免和 env/runner candidate 混在同一语义提交中。本报告不修改 trainer。

## 7. 不确定性与证据边界

- Teacher 只覆盖 seed0/1，Student 只覆盖 seed0/1/2；每个 env 只有一条正式 episode。`42/48` 是这组三 seed 的描述性结果，不是置信区间或 general policy claim。
- same-seed replays 已观察到 `13/16 → 14/16 → 15/16`，env9 还出现 formal success → render Stage2 timeout。任何后续比较都必须继续保留 formal batch 与 replay sensitivity 的区分。
- failure env 在 seed0 与 seed2 无交集，现阶段没有 stable hard-negative set；单个 env render 不能建立因果归因。
- 视觉检查支持“handle 可见、局部遮挡”，但不证明 feature encoder 实际利用了每个像素，也不证明实机相机链路。
- 本批次没有 evidence 把 `64 env`、step8000、训练总预算或某个 door randomization 字段识别为根因。

## 8. 决策与下一步

1. **接受 C-B2H visual path/camera migration 的本批次结论。** 不回退 camera layout，不再把泛化 visibility 当作当前 Stage2 首要假设。
2. **不启动 full retrain，不启动 generic 1–2k continuation。** 当前 evidence 没有给出这种追加预算能修复 non-stable contact continuity 的可检验机制。
3. **如需 finetune，只考虑 targeted Stage2 contact-continuity / DAgger。** 训练数据应聚焦 Student 闭环进入 Stage2 后的 bilateral contact、opposite squeeze 与连续 streak 恢复，而不是再次采集大量 Teacher-only 通用轨迹。
4. **finetune 前必须另行提交并批准 `HIGH_RISK` brief。** brief 至少要固定训练资源/成本、case sampling、Student-controlled rollout 比例、formal multi-seed acceptance、matched Stage2 trace 指标与停止条件；本报告不授权训练。

需要后续回答的唯一关键问题是：针对 Student 闭环 Stage2 状态采集的 DAgger 数据，能否在新的 formal multi-seed batch 中稳定提高 streak continuity，同时不损害现有 `42/48` 的其他 stage 表现。在该问题获得独立批准前，本批次到此关闭。
