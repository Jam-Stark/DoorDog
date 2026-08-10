---
name: base-v23-force-feasibility
scope: A2+Piper base_v23 P0 force-feasibility calibration, certificate, and D1 admission boundary
status: formal_admission_prerequisites_complete_pending_A1
last_updated: 2026-08-10 21:22 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v23-force-feasibility/description.md
  - memory/a2-piper/base-v23-force-feasibility/TODO.md
  - memory/a2-piper/base-v23-force-feasibility/DONE.md
read_when:
  - implementing, executing, or adjudicating any base_v23 P0 node
  - deciding D1 admission, P0.8--P0.10 continuation, or formal v23 training eligibility
---

# base_v23 Force Feasibility

## Purpose

本 entry 保存 `base_v23` P0 的可复用 calibration / force-feasibility 事实及其 admission 边界。历史 R54 的 `INTERIM_TYPED_ADJUDICATION / FORMAL_NO-GO` 只保留为其 capability-source reducer 的 typed result；owner 的 `OPTION_2_PLUS_3_COMBINED` 已用 physics-first D1/D1-lite 与 P0.8 preformal-v2 取代该 admission gate。R238 已完成最后一项 D1-FULL `64×10` bucket-plumbing prerequisite，下一步为 A1；这只完成 TRAINING_PASS plumbing，不是 formal-training、policy-quality 或 release claim。

## Hard Boundaries

- `confirmed_E2=false`。R49 A8 certificate 与 R54 A0 D1 capability-source branch 是不同 producer，不得合并成 E2 或 D1 PASS。
- P0.4 的 atlas/external outputs 保持 `MEASURED_RAW`；R190 只以其 measured positive brackets 形成 provisional D1/D1-lite freeze，不得重标 raw outputs 或将该 scoped freeze 升格为 formal admission/release。
- R54 reducer 仅输出历史 `a2_piper_v23_d1_capability_source_incomplete_v1` / `D1_CAPABILITY_SOURCE_INCOMPLETE`；`d1_freeze_written=false`，没有 zones、capacity 或 schedules。它保留不改，但其 symmetric policy-window admission rule 已由 owner `OPTION_2_PLUS_3_COMBINED` supersede，不能阻塞 R190 physics-first D1 freeze。
- R53 缺少 `a2_v23_p05_seed` 时，strict consumer 应 fail-fast。R54 只加入 exact integer override；没有 coercion、fallback 或 alternate D1 source/rule。
- R21 的 `RUNTIME_VERIFIED` RP0 contract 仅证明其自身 64-env runtime / resume contract；不能替代 R54 P05 raw dimensions 3/4 的 direct proof，该 proof 仍为 `INCONCLUSIVE`。
- R78 仍只完成 bounded partial A0/D0 P0.8 source plumbing，且其 historical `p08_overall_status=PARTIAL_INCOMPLETE` 不改；P0.8 preformal-v2 仅在 R78 plumbing 加四个 trigger records 的 revised gate 下 complete，不证明 exact state clone、recurrent restore、D1, formal admission 或 release。
- R190 physics-first receipt 已完成 provisional D1/D1-lite freeze：它以 scripted door-side positive atlas bracket 与 matrix-wide effort `40 N*m` 比较，绑定不变的 R35 P0.5 bands；normal zones 为 E0 `A0/A1`、E1 `A4/A5/A6/A2/A3/A7`、near-E2 `A8`，lite E1 为 `A4/A5/A6`，`confirmed_E2=false`。normal schedule 为 `100/0/0 -> 60/40/0 -> 30/60/10`，lite schedule 为 `100/0/0 -> 65/35/0 -> 40/55/5`。这只是 provisional curriculum freeze，不是 formal admission 或 release。
- P0.8 preformal-v2 已完成：R78 source plumbing 不变，加上四个 one-env forward trigger records。ACUTE 在 episode-start step `0` switch；BASE0 observed stable-grasp high-water step `180`、switch `181`；rescue 与 oracle 都 observed typed-failure latch step `530`、switch `531`。rescue 仅证明 configured six-joint solver-limit request/readback，不是 actual PhysX torque。该 gate 不证明 causal effect、policy quality、exact state clone 或 recurrent restore，也不令 formal admission/release 为 true。
- R112 只完成 D0 P0.9 四型 smoke；canonical receipt 虽有 `p010_d0_full_pilot_admission=true`，但 `d1_admission=false`、`formal_admission=false`、`release_receipt=false`，不能提升为 policy-quality 或 formal claim。
- R170/R173 的 P0.1/P0.3 runtime typed adjudication 只证明 telemetry timing/authority、controller identity、action→articulation mapping、effort clipping 与 FULL checkpoint load；computed/applied 均是由 PRE state 导出的 POST actuator estimate，actual PhysX drive torque 仍 `UNKNOWN/ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE`。R31/R33 legacy evidence 未获升级；R161/R164/R169 保持 prior typed F8 failures。
- P0.10 terminal adjudication 是 operational `NO-GO`，scientific result 为 Branch B 未测量的 `INCONCLUSIVE`；它不构成 Branch B outcome、D1、formal admission、policy quality、release 或 goal success。F1 已完成 bounded head-reset implementation 与 two-type runtime smoke，但并未 adjudicate Branch B；此前 D1 blocked 时 G7/G8 未 launch，这不是对已完成 prerequisite 后 A1 的否定。
- Formal 8×2 的 active conjunction R190 physics-first receipt、`P0_8_PREFORMAL_COMPLETE` receipt 与 R238 D1-FULL `64×10` bucket-plumbing receipt 已全部完成，故 A1 可开始；R238 的 `formal_admission=false` / `policy_quality_claim=false` 与 excluded release claim 仍必须保留，不能把 prerequisite completion 写成 formal-training、policy 或 release PASS。Physical GPU0/GPU1 是仅有的 v23 runtime resources，GPU2--7 excluded；Route B complete intervention suite、holdout64 与 render 仍 pending。

## Measured Facts and Typed Adjudication

- P0.2 `a2_piper_v23_effort_freeze_v1`：`MEASURED_FREEZE`，selected effort `40 N*m`，`LADDER_INCONCLUSIVE`；12 runs / 192 records。
- P0.4 raw atlas/external producers：A0/A1 positive bracket `(10,15]`；A2/A3/A7 `(25,30]`；A4/A5/A6 `(15,20]`；A8 `(30,40]`；negative sign is `RIGHT_CENSORED`。
- P0.5 bands 已冻结：stable grasp `20`；progress `0.02--0.04 rad` per `25--40` steps；clipped utilization `0.9`、fraction `0.3`；rescue `0.10--0.15 rad/window`。
- R49 A8 certificate branch：pair `PASS`（15 `PREFIX_EQUAL`，env5 `NO_RESCUE_LATCH`）；bundle `READY_FOR_CERTIFICATE`；certificate `COMPLETED_TYPED_NEGATIVE` has `identity_count=16`, `pass_count=0`, 15 `COMPLETED_TYPED_NEGATIVE`, and env5 `RESCUE_NOT_EXECUTED`, with `confirmed_E2=false`。这是完成的 scientific negative，不是 D1 admission。
- R50 A0 source freeze：`CAPABILITY_SOURCE_FROZEN` at effort `40 N*m`。Requested damping/stiffness/max force/mass 为 `50 / 2 / 4.5 / 120`，native readback 为 `2864.7890625 / 114.59156036376953 / 4.5 / 119.99999237060547`。
- R54 FULL / ACUTE producers 均 runtime `rc0`，各 exact16 finite records；valid windows 分别为 FULL `15/16`（env5 missing）与 ACUTE `1/16`（仅 env12）。Canonical reduce `rc2`，保留 exact16/no-subset，而没有 D1 freeze。
- P0.6 common reward 已由 concrete warm/FULL/D0 config 实际 compose：v22 conditional terms 撤三留三，`penalty_a2_posture_command_l1=0`。R68 GPU0 short smoke 为 runtime `rc0`、16 completed episodes、3,590 finite numeric metric values。R72 六个 fresh sequential GPU0 stage pass 均正常完成 16 episodes，capture counts 为 `16/16/16/16/16/13`；canonical stationary-rent audit 为 `COMPLETE`、`missing_stages=[]`。该结论只验证 zero-action same-step audit contract 与 reward composition，不是 policy-quality / long-horizon stationarity / formal-training claim。
- R78 partial A0/D0 P0.8：单次 fresh GPU0 warm/FULL/D0 evaluator runtime `rc0`，正常完成 16 个 first episodes；16 份 physical readback 与 R50 A0 source geometry 及 requested/native door parameters 一致。Stages `2/3/4` 全覆盖，reducer 输出 3 个 state-bank entries 与 `3×5=15` 个 bindings；仅 FULL 是 captured source rollout，四个 alternative modes 均未执行。Canonical receipt 为 `PARTIAL_A0_D0_PLUMBING_RUNTIME_VERIFIED`，`p09_d0_smoke_admission=true`，同时 overall P0.8 仍 `PARTIAL_INCOMPLETE`。
- R112 D0 P0.9：WARM_FULL/GPU0、WARM_RP0/GPU1、SCRATCH_FULL/GPU2、SCRATCH_RP0/GPU3 各 single-attempt 运行 `64 env × 10 batch`，runner/child 均 `rc0`。四份 step-10 checkpoint 均通过 schema、`global_step=10` 与 finiteness validation；AppLauncher/Torch/Isaac/Kit Vulkan 设备证据匹配，task PID 未使用 GPU4--7。CPU-only REDUCE `rc0`，canonical status 为 `P0_9_D0_FOUR_TYPE_SMOKES_RUNTIME_VERIFIED`，仅准入 D0 P0.10 FULL pilot。
- R228→R238 D1-FULL gate：R228 在 pre-optimizer 阶段 fail-fast 暴露缺失的 v22 measured height-nominal config；R231 以 source-backed v22 G1/smoke config 补齐该 exact input，R233 在 physical GPU0/logical `cuda:0` 完成 G5 `v22_warm` / D1 / FULL 的 `64 env × 10 batch` RUN（`num_mini_batches=1`、finite step-10 checkpoint）。R235 修复 reducer 对 explicit-zero 的处理，R238 strict REDUCE 写出 canonical receipt。该结果是 D1 bucket/plumbing `TRAINING_PASS`，不是 policy quality、formal training 或 release evidence。
- R170/R173 P0.1/P0.3：FULL exact16 runtime 产生 `45,776` joined phase frames，覆盖 `PRE_ACTUATOR_COMPUTE/PRE` 与 `POST_PHYSICS/POST`。P0.1 computed/applied 均为 PRE state 导出的 POST actuator estimate，actual PhysX drive torque remains `UNKNOWN/ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE`。P0.3 有 16 个 controller identities，live action→articulation permutation 为 `[0,4,9,2,6,11,1,5,10,3,7,12,8,13,14,15,16,17,18,19]`；arm slots `[12,13,14,15,16,17]` 对应 articulation IDs `[8,13,14,15,16,17]`，执行 `effort40` clipping，且为 FULL checkpoint load。该结果仅 P0.1/P0.3，D1/formal/release 均为 false。
- P0.10 terminal R160：top status `P0_10_SCRATCH_ADMISSION_NO_GO_BRANCH_A_FAILED_BRANCH_B_OBSERVABILITY_BLOCKED`；Branch A 是有效 measured fail，evaluated/stage2/stable-grasp counts 为 `16/12/0`。Branch B 为 `UNMEASURED_OBSERVABILITY_BLOCKED`，policy outcome `UNADJUDICATED`：checkpoint 缺少 `staged_reset_buf` / `staged_reset_num_samples`，且 canonical16 没有 `stage>=3` birth-stage source。scientific outcome 是 `P0_10_SCIENTIFIC_INCONCLUSIVE_BRANCH_B_UNMEASURED`，并触发 F1 marker `V23_SCRATCH_CURRICULUM_INSUFFICIENT_PILOT`。
- P0.10 F1 R177/R180--R182：`warm_head_reset` 在 strict post-policy-only-load 后，只 reset actor final rows `[3:5]` 的 weight/bias 及 `std[3:5]=0.8`，使用 local seed/device generator；其余 actor rows、LSTM、RMS 以及 fresh critic/optimizer state 保持既定状态。G3/G4/G7/G8 route `warm_head_reset`，G1/G2/G5/G6 保持 warm；D1 blocked 时 G7/G8 仍 unlaunched。R180 `HR_FULL_D0`（physical0/logical0）与 R181 `HR_RP0_D0`（physical1/logical0）各 natural `rc0`、no retry、`64×10`，均有 finite step-10 checkpoint。R182 canonical aggregate 为 `P0_10_F1_D0_HEAD_RESET_TWO_TYPE_SMOKES_RUNTIME_VERIFIED`、`f1_smoke_complete=true`、`p010_f1_status=COMPLETE`，但 D1/formal/release 均 false。

## Canonical Evidence

- P0.2: `logs_eval/base_v23/p0/r33_p02_effort_freeze_20260809/effort_freeze.json`
- P0.4 raw atlas/external: `logs_eval/base_v23/p0/r26_p02_p04_p05_runtime_20260809/p04/door_atlas_raw.json` and `door_external_torque_threshold.json`
- P0.5 bands: `logs_eval/base_v23/p0/r35_p05_cert_20260809/p05_bands.json`
- R49 certificate: `logs_eval/base_v23/p0/r49_p05_reduction_20260809/feasibility_certificate.json` (pair/bundle siblings)
- R50 source freeze: `logs_eval/base_v23/p0/r50_p05_d1_source_20260809/a0_capability_source_freeze.json`
- R54 FULL input: `logs_eval/base_v23/p0/r54_p05_d1_source_runtime_20260810/runs/full/a2_v23_p05_episode_records.json`
- R54 ACUTE input: `logs_eval/base_v23/p0/r54_p05_d1_source_runtime_20260810/runs/acute_rp0/a2_v23_p05_episode_records.json`
- R54 reduction: `logs_eval/base_v23/p0/r54_p05_d1_reduction_20260810/d1_capability_source_incomplete.json`
- R190 physics-first D1/D1-lite receipt: `logs_eval/base_v23/p0/p04_d1_physics_first_20260810/p04_d1_physics_first.json`
- P0.8 preformal-v2 canonical receipt: `logs_eval/base_v23/p0/interventions/preformal_v2/p08_preformal_v2_receipt.json`
- R233 D1-FULL raw: `logs_rl/a2_piper_full_stage_a2_base_smoke/base_v23/d1_full_64x10_r233/d1_full_64x10_raw.json`
- R238 D1-FULL canonical receipt: `logs_eval/base_v23/p0/d1_full_64x10/d1_full_64x10_receipt.json`
- R21 RP0 contract: `logs_eval/base_v23/p0/a2_piper_v23_p07_rp0_contract_r21.json`
- R68 P0.6 short smoke: `logs_eval/base_v23/p0/r68_p06_reward_runtime_20260810/smoke/`
- R72 P0.6 stationary-rent audit: `logs_eval/base_v23/p0/reward/stationary_rent_audit.json` (six pass receipts under `logs_eval/base_v23/p0/r72_p06_stationary_rent_runtime_20260810/passes/`)
- R78 partial P0.8 runtime: `logs_eval/base_v23/p0/r78_p08_a0_d0_runtime_20260810/`
- R78 partial P0.8 canonical receipt: `logs_eval/base_v23/p0/state_bank/state_bank_plan.json`
- R112 P0.9 four-type runs: `logs_rl/a2_piper_full_stage_a2_base_smoke/base_v23/r112/{warm_full,warm_rp0,scratch_full,scratch_rp0}/`
- R112 P0.9 canonical receipt: `logs_eval/base_v23/p0/p09_d0_type_smoke_receipt.json`
- R170/R173 P0.1/P0.3 runtime typed adjudication: `logs_eval/base_v23/p0/r170_p01_p03_runtime_20260810/p01_p03_typed_adjudication.json`
- R160 P0.10 terminal adjudication: `logs_eval/base_v23/p0/p010_scratch_full_d0_terminal_adjudication.json`
- R182 P0.10 F1 canonical receipt: `logs_eval/base_v23/p0/p010_f1_head_reset_d0_type_smoke_receipt.json`
- Human-readable adjudication: `scriptsFORhuman/v23/V23_P0_INTERIM_REPORT_20260810.md`

## Validation Status

- R51 Isaac review, R52 code/goal candidate gates, and R54 seed-code gate are `PASS` review evidence.
- R54 FULL/ACUTE producer commands have runtime `rc0`; the canonical reducer's `rc2` is an expected typed incomplete scientific result, not runtime PASS for D1 admission.
- R68 and R72 are targeted IsaacSim evaluator runtime evidence for P0.6 only. R72 RUN/REDUCE both returned `rc0`; all reward/action numeric values were finite and no retry, training, P0.9, D1, or render command ran.
- R77 code/IsaacLab frozen-candidate reviews and R78 targeted GPU0 runtime QA are `PASS` for the bounded partial P0.8 node. R78 RUN returned `rc0` once; there was no retry, separate REDUCE, training, P0.9, D1, formal evaluation, or render command.
- R113 code review is `PASS` for candidate `v23-p09-r112@cacd155-m1u2`. R114--R117 each ran exactly one assigned P0.9 type and returned runner/child `rc0`; the single R112 REDUCE returned `rc0`. This is runtime smoke evidence only, not policy-quality or formal admission.
- R148 goal/candidate gate, R167/R171 code-quality, and R168/R171 IsaacLab reviews are `PASS` for the frozen P0.10/P0.1/P0.3 source candidate. R160 terminal P0.10 CPU adjudication returned its expected typed `rc2`; R172 R170 producer runtime returned natural `rc0` once with exact16; R173 CPU reducer returned `rc0` with `P0_1_P0_3_RUNTIME_TYPED_ADJUDICATION`. These are scoped validation provenance, not actual-torque, Branch-B, D1, formal, release, policy-quality, or goal-success evidence.
- R178 code-quality and R179 IsaacLab reviews are `PASS` for F1 semantics. R180/R181 each performed one natural `rc0` two-type runtime smoke, and R182 CPU reduce returned natural `rc0` with schema `a2_piper_v23_f1_head_reset_d0_receipt_v1`. This validates bounded F1 implementation/runtime-smoke completion only; Branch B, P0.8 overall, D1, formal, H1--H5, release, policy quality, and goal success remain unproved.

- R190 physics candidate `V23-R190-C1` has code-review `PASS` and independent runtime-evidence QA `PASS`. Its canonical `a2_piper_v23_p04_d1_physics_first_v1` receipt is `P0_4_D1_PHYSICS_FIRST_FREEZE_ADMITTED`; policy records are auxiliary (FULL `15/16`, ACUTE `1/16` sparse expected), and R54 is not an active completeness gate.
- P0.8 source candidate `V23-R191-C5` has code-review and IsaacLab-review `PASS`; R206/R207 four-trigger runtime lanes and R207 C4 `REDUCE_ONLY` are `PASS`. Canonical `a2_piper_v23_p08_preformal_v2_receipt_v1` is `P0_8_PREFORMAL_COMPLETE`, has four records/no incomplete reasons and `p08_preformal_gate=true`, while `formal_admission=false` and `release_receipt=false`.
- `V23-R232-D1-C1` code-quality and IsaacLab reviews are `PASS`; R233 RUN is reviewed training/plumbing evidence `PASS`; `V23-R237-REDUCE-C1` code-quality and R238 strict REDUCE runtime QA are `PASS`. Canonical `a2_piper_v23_d1_full_64x10_receipt_v1` status is `D1_FULL_64X10_BUCKET_PLUMBING_RUNTIME_VERIFIED`, with `formal_admission=false`, `policy_quality_claim=false`, and no release receipt.

## DONE Summary

P0.2 effort freeze, P0.4 raw producer outputs, P0.5 bands, R49 typed-negative certificate, R50 A0 source freeze, historical R54 exact16 producer plus typed incomplete reduction, R190 physics-first D1/D1-lite freeze, P0.6 common-reward/stationary-rent runtime, the separate R21 RP0 contract, R78 plumbing plus P0.8 preformal-v2 four-trigger closure, R112 D0 P0.9 four-type smokes, R170/R173 P0.1/P0.3 runtime typed adjudication, R160 P0.10 terminal adjudication, R177/R180--R182 F1 head-reset two-type smokes, and R238 D1-FULL bucket-plumbing gate have verified receipts. Formal-admission prerequisites are complete, while formal training, policy quality, and release remain unproved.

## TODO Summary

Formal-admission prerequisites are complete. Next execute A1 as two GPU0/GPU1 slices—G1/G3 D0 then G5/G7 D1—followed by Route A; Route B full interventions, holdout64, render, and final analysis remain pending.
