# DoorDog A2+PiPER base_v24 最终裁决（2026-08-17）

## 结论

base_v24 在 Phase 1 结束，最终 typed result 为：

`V24_FRICTION_AUTHORITY_INSUFFICIENT`

这不是 `V24_FRICTION_MODEL_VALID`。A–C、E–I 在各自限定语义内通过；D 的行为耗散 proxy 通过，但 preregistered literal `tau_friction * omega <= tolerance` 需要 solver friction torque component，而许可的 IsaacLab high-level API 只提供 friction property write/readback，不提供该 generalized friction-torque component。因此不得把行为 proxy 升格为 literal D PASS，也不得声称测得 actual generalized torque。

按 R1 admission gate，只有 `V24_FRICTION_MODEL_VALID` 才能进入 P2/P3。故 P2、P3、Wave 1、Route A/B、RQ3/RQ4、shadow critic、Wave 2a/2b 均不执行。Phase 3 未到达，所以唯一 user decision point `V24_FRICTION_AXIS_NONDISCRIMINATIVE` 未触发，无需请示 owner。

## P0 收口

- 单位契约与 v23 descriptive posthoc 已在 `fce6d68` 完成。
- checkpoint/start freeze 已在 `5227a9b` 完成，选择 `A1_G7_seed0_step1500`：`logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt`。
- P0 runtime compatibility 在 physical GPU0 通过：current 与 direct pre-friction baseline 对 7,326 个 first-episode rows 比较，actor observation 133-D、raw action mean 12-D、post-environment/final 24-D action 的 max absolute difference 全为 `0.0`；done 与 terminal facts exact。
- friction/gate/D1/warm-head-reset 均关闭，16 个 reset receipt 均为 `DEFAULT_OFF_NO_WRITE`。
- current public `contact_sensor` 提供 finite `(16,4)` 的 `FL/RL/FR/RR` foot vertical force；baseline 无新 getter，诚实记录 `FOOT_FORCE_SOURCE_UNAVAILABLE`，无 numeric payload、无 zero fill。

## P1 A–I 裁决

| Gate | 结果 | 边界 |
|---|---|---|
| A breakaway | PASS | F00/F05 `[0,0.5] Nm`，F10 `[0.5,1.0] Nm`，literal containment |
| B kinetic plateau | PASS | 注册的 spread/direction-asymmetry limits 内 |
| C damping distinction | PASS | friction/damping directional ratios 通过 |
| D passivity | AUTHORITY_INSUFFICIENT | behavior proxy PASS；literal component unavailable |
| E chatter | PASS | first-breakaway 后无注册的 chatter failure |
| F timestep | PASS_QUALITATIVE_ONLY | base/fine qualitative classification 一致 |
| G orthogonality | PASS | A0/A1/A4/A5/A8/F10，scaled distance `3.11e-08–2.26e-07 <= 1e-4` |
| H reset persistence | PASS | 10 ordinary + 6 legitimate nonzero staged resets |
| I legacy/default-off | PASS | 7,326 rows exact/zero-diff compatibility |

H 使用 native profile `1.0/0.75/0.0`。每个 reset env 先经 public Articulation API 写入并读回 distinct sentinel，再进入真实 production `reset_envs_idx`；super state writers 完成后重新施加 configured profile 并读回。16 个 terminal receipts 中 10 个 ordinary、6 个真实 stage>0 snapshot（env `2/4/5/7/8/13`，stage `4/4/3/4/5/4`，sample count 均为 `1`），全部通过。

parameter-range freeze 记为 `NOT_PERFORMED_STOPPED_AT_P1_AUTHORITY_GATE`；不能把未进入 P2 的范围解释成 directional-capacity 或 E-region freeze。

## 证据

- P1A unit probe：`logs_eval/base_v24/p1/friction_backend/torque_ramp_r4_gpu0/TORQUE_RAMP.json`
- A–G：`logs_eval/base_v24/p1/friction_backend/a_g_acceptance_r9_gpu0/P1_A_G_RECEIPT.json`
- H/I combined receipt：`logs_eval/base_v24/p0/runtime_compatibility/r6/P0_P1_RUNTIME_COMPATIBILITY_RECEIPT.json`
- H raw trace：`logs_eval/base_v24/p1/reset_persistence/r6/producer_runtime/current-h-trace.json`
- independent QA：`logs_eval/base_v24/p0/runtime_compatibility/r6/QA_SEMANTIC_VALIDATION.json`
- final typed receipt：`logs_eval/base_v24/p1/final_adjudication/r1/V24_P1_FINAL_ADJUDICATION.json`

QA1–QA5 的失败目录保留为 implementation/runtime failure provenance；它们均未产出可用于科学裁决的完整 receipt。最终通过的是 R8-QA6，产品实现提交为 `f45473b`。

## 未声明事项

- 不声明 `MODEL_VALID`、actual generalized torque、P2/P3 admission、training/release success 或 causal posture value。
- 不执行训练波，不 push。
- 现有用户修改的 `scriptsFORhuman/a2_piper_longterm_TODO.md` 保持不变；本轮 ledger 单独记录在 v24 路径。
