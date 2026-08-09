---
name: base-v23-force-feasibility
scope: A2+Piper base_v23 P0 force-feasibility calibration, certificate, and D1 admission boundary
status: interim_typed_adjudication_formal_no_go
last_updated: 2026-08-10 03:37 HKT
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

本 entry 保存 `base_v23` P0 的可复用 calibration / force-feasibility 事实及其 admission 边界。当前结论是 `INTERIM_TYPED_ADJUDICATION / FORMAL_NO-GO`：已有的 measured records 只能支持 P0 preparation，不支持 D1 freeze、D1-lite/F3、formal 8×2 training、H1--H5 或最终 release/goal claim。

## Hard Boundaries

- `confirmed_E2=false`。R49 A8 certificate 与 R54 A0 D1 capability-source branch 是不同 producer，不得合并成 E2 或 D1 PASS。
- P0.4 的 atlas/external outputs 是 `MEASURED_RAW`；其 D1 zones/mixture 仍 `NOT_FROZEN`，不得把 raw brackets 重标为 P0.4/D1 完成。
- R54 reducer 仅输出 `a2_piper_v23_d1_capability_source_incomplete_v1` / `D1_CAPABILITY_SOURCE_INCOMPLETE`；`d1_freeze_written=false`，没有 zones、capacity 或 schedules。
- R53 缺少 `a2_v23_p05_seed` 时，strict consumer 应 fail-fast。R54 只加入 exact integer override；没有 coercion、fallback 或 alternate D1 source/rule。
- R21 的 `RUNTIME_VERIFIED` RP0 contract 仅证明其自身 64-env runtime / resume contract；不能替代 R54 P05 raw dimensions 3/4 的 direct proof，该 proof 仍为 `INCONCLUSIVE`。

## Measured Facts and Typed Adjudication

- P0.2 `a2_piper_v23_effort_freeze_v1`：`MEASURED_FREEZE`，selected effort `40 N*m`，`LADDER_INCONCLUSIVE`；12 runs / 192 records。
- P0.4 raw atlas/external producers：A0/A1 positive bracket `(10,15]`；A2/A3/A7 `(25,30]`；A4/A5/A6 `(15,20]`；A8 `(30,40]`；negative sign is `RIGHT_CENSORED`。
- P0.5 bands 已冻结：stable grasp `20`；progress `0.02--0.04 rad` per `25--40` steps；clipped utilization `0.9`、fraction `0.3`；rescue `0.10--0.15 rad/window`。
- R49 A8 certificate branch：pair `PASS`（15 `PREFIX_EQUAL`，env5 `NO_RESCUE_LATCH`）；bundle `READY_FOR_CERTIFICATE`；certificate `COMPLETED_TYPED_NEGATIVE` has `identity_count=16`, `pass_count=0`, 15 `COMPLETED_TYPED_NEGATIVE`, and env5 `RESCUE_NOT_EXECUTED`, with `confirmed_E2=false`。这是完成的 scientific negative，不是 D1 admission。
- R50 A0 source freeze：`CAPABILITY_SOURCE_FROZEN` at effort `40 N*m`。Requested damping/stiffness/max force/mass 为 `50 / 2 / 4.5 / 120`，native readback 为 `2864.7890625 / 114.59156036376953 / 4.5 / 119.99999237060547`。
- R54 FULL / ACUTE producers 均 runtime `rc0`，各 exact16 finite records；valid windows 分别为 FULL `15/16`（env5 missing）与 ACUTE `1/16`（仅 env12）。Canonical reduce `rc2`，保留 exact16/no-subset，而没有 D1 freeze。
- P0.6 common reward 已由 concrete warm/FULL/D0 config 实际 compose：v22 conditional terms 撤三留三，`penalty_a2_posture_command_l1=0`。R68 GPU0 short smoke 为 runtime `rc0`、16 completed episodes、3,590 finite numeric metric values。R72 六个 fresh sequential GPU0 stage pass 均正常完成 16 episodes，capture counts 为 `16/16/16/16/16/13`；canonical stationary-rent audit 为 `COMPLETE`、`missing_stages=[]`。该结论只验证 zero-action same-step audit contract 与 reward composition，不是 policy-quality / long-horizon stationarity / formal-training claim。

## Canonical Evidence

- P0.2: `logs_eval/base_v23/p0/r33_p02_effort_freeze_20260809/effort_freeze.json`
- P0.4 raw atlas/external: `logs_eval/base_v23/p0/r26_p02_p04_p05_runtime_20260809/p04/door_atlas_raw.json` and `door_external_torque_threshold.json`
- P0.5 bands: `logs_eval/base_v23/p0/r35_p05_cert_20260809/p05_bands.json`
- R49 certificate: `logs_eval/base_v23/p0/r49_p05_reduction_20260809/feasibility_certificate.json` (pair/bundle siblings)
- R50 source freeze: `logs_eval/base_v23/p0/r50_p05_d1_source_20260809/a0_capability_source_freeze.json`
- R54 FULL input: `logs_eval/base_v23/p0/r54_p05_d1_source_runtime_20260810/runs/full/a2_v23_p05_episode_records.json`
- R54 ACUTE input: `logs_eval/base_v23/p0/r54_p05_d1_source_runtime_20260810/runs/acute_rp0/a2_v23_p05_episode_records.json`
- R54 reduction: `logs_eval/base_v23/p0/r54_p05_d1_reduction_20260810/d1_capability_source_incomplete.json`
- R21 RP0 contract: `logs_eval/base_v23/p0/a2_piper_v23_p07_rp0_contract_r21.json`
- R68 P0.6 short smoke: `logs_eval/base_v23/p0/r68_p06_reward_runtime_20260810/smoke/`
- R72 P0.6 stationary-rent audit: `logs_eval/base_v23/p0/reward/stationary_rent_audit.json` (six pass receipts under `logs_eval/base_v23/p0/r72_p06_stationary_rent_runtime_20260810/passes/`)
- Human-readable adjudication: `scriptsFORhuman/v23/V23_P0_INTERIM_REPORT_20260810.md`

## Validation Status

- R51 Isaac review, R52 code/goal candidate gates, and R54 seed-code gate are `PASS` review evidence.
- R54 FULL/ACUTE producer commands have runtime `rc0`; the canonical reducer's `rc2` is an expected typed incomplete scientific result, not runtime PASS for D1 admission.
- R68 and R72 are targeted IsaacSim evaluator runtime evidence for P0.6 only. R72 RUN/REDUCE both returned `rc0`; all reward/action numeric values were finite and no retry, training, P0.9, D1, or render command ran.

## DONE Summary

P0.2 effort freeze, P0.4 raw producer outputs, P0.5 bands, R49 typed-negative certificate, R50 A0 source freeze, R54 exact16 producer plus typed incomplete reduction, P0.6 common-reward/stationary-rent runtime, and the separate R21 RP0 contract have verified receipts. These are completed sub-results only.

## TODO Summary

Partial A0/D0 P0.8 plumbing/state bank, conditional D0 P0.9 smokes, and D0 P0.10 pilot remain. D1 admission/formal work remains blocked by the R54 stable-window result; direct R54 raw-dimension 3/4 proof remains `INCONCLUSIVE`.
