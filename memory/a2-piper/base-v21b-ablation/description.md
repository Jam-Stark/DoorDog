---
name: base-v21b-ablation
scope: A2+Piper base_v21B arm-effort ablation from pretest through formal training and Route-A/Route-B scientific adjudication
status: completed
last_updated: 2026-08-04 03:36 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v21b-ablation/description.md
  - memory/a2-piper/base-v21b-ablation/TODO.md
  - memory/a2-piper/base-v21b-ablation/DONE.md
read_when:
  - auditing base_v21B training/evaluation provenance or interpreting its scientific terminal state
  - planning a separately approved successor experiment after the F5 no-release outcome
---

# base_v21B Arm-Effort Ablation

## Purpose

本 entry 保存 `base_v21B` arm-effort ablation 的 durable provenance、formal/eval closure 与科学终态。它不替代后续新实验的 scope；本轮已完成，不能把无 release 结果改写成可用 release 或硬件结论。

## Current State

- 2026-08-04 03:36 HKT - R25 修复 episode-boundary telemetry handoff，并将 validator 的 typed-N/A 与 base-vs-strict 语义分开；提交 `72f3171843cb495b075486cc7ec6703f02753706`、tree `807bfe322ee23359dd04370e4dc3ec7f40252301`。targeted suite 为 `36 passed, 4 skipped`；四个 `pxr` lifecycle tests 因本地缺少 `pxr` 未运行，后续 smoke/formal runtime evidence 覆盖相关 runtime surface，不能把该 static skip 写成 static PASS。
- R10 preformal census 位于 `logs_eval/base_v21B/preformal_20260802_r10`：source lock SHA-256 `6ee27b52d4d6a6c3fbb95e7341debdbc79eafd07fb5d3ac74b137340081133ca`；canonical16/heavy16 各一次 GPU0、W&B offline、natural exit 0。raw-unclipped heavy bucket 的 `>=100 N·m` 为 `7792/12463=0.6252106234453984`，因此 terminal 为 `CENSUS_RIGHT_CENSORED`、selection `N/A`、telemetry authority `ESTIMATE_ONLY`；census SHA-256 `10064789700cd3716bb047e5bc063bff07c15359a6d310bc29a6f63bf0c73d23`。
- R3 F3 promotion 位于 `logs_eval/base_v21B/f3_promotion_20260802_r3`：B1–B7 均为 `ARM_V20 [100]*6`，theta ladder 依次为 `0.90/1.20/1.05/1.15/1.25/1.20/1.25`；adaptation SHA-256 `77b62185350d2f0ad935cb0a9395bc9a0cb42f9966972ab5fba936170476798a`，materialization SHA-256 `a30aabbd1b04fa8a918a668fbf4b48361c1cbb5d1f743b5f78a035ad476e294d`。
- R27 是唯一受理的 B4 replacement smoke：GPU3、W&B online、64 env、10 iteration、save10，natural exit 0；strict rows `1..10`、coverage/finite/identity 与 step10 checkpoint 均 PASS。SMOKE_PASS SHA-256 `4d1526b3421214f5b505cdb449eaa78c523db27d8ab611185b30cca540887ff4`；其后 signed cleanup 删除全部 smoke roots，receipt SHA-256 `9da6ca006acc2c02fa23ec95f666a618b7e9b39dd82dbca588673b5bc4efd685`。
- R16 approved replacement smoke PASS 后，正式 B1–B7 训练以 env4096、2500 iterations、save250、W&B online 各运行一次；`R17_FORMAL_COMPLETION.json`（`logs_eval/base_v21B/postformal_20260803_route_a_exact70_r16/`）为 `FORMAL_COMPLETION_PASS`，覆盖 7 cells、70 checkpoints 至 step2500，SHA-256 `4dcf03c55e4dbc9f3bedb9a0a9a4372de77f8490f29ca44436155eccf2a4d93f`。GPU7 未分配；没有 task GPU process remains。
- Route-A immutable exact70 queue SHA-256 `4e9128d3a60b9e90a5344b14b8e6daca5b10997ea40795bc3c31de70887707e0`；R20 metrics SHA-256 `72df6ca2b0e5202c63248ec7324bdc94262bf7d071bc356887ce7a307210938a`；R22 selection SHA-256 `d443ec81cd893d92820f301f6f13338bcc6e73e21e7c6180fac7f462734f1bad`。Route-A release-eligible cells 为 B1/B2/B3/B4/B6/B7，B5 为 mechanism-only/nonpromotable。
- Route-B exact pooled48 的 B1/B2/B4/B5/B6/B7 共 288 valid episodes，科学判定 FAIL；B3 在一个 valid seed 后触发 fail-fast runtime evidence failure，没有 exact48，未 retry 或 adjudicate。candidate set 为空，预注册 F5 因此禁止 release freeze、holdout64 与 render。
- 最终 `V21B_ROUTE_B.json` SHA-256 `96202b3d839f4cc71783c8a1b5595d322a601816612abbbbb94e7c9d1e0845be`，R31 terminal SHA-256 `1090b151f128d66b5dc08a41aa10d0f32a783558768d3a22f856cda2e2d6e680`；runtime status PASS、scientific terminal 为 `COMPLETED_SCIENTIFIC_NO_RELEASE`。实际 pooled runtime 仅使用 physical GPUs 0–2（政策允许 0–3）。

## Evidence Boundary

`effort_limit` 的降低是 physics treatment；本轮只能表述 estimated commanded PD effort saturation 与 configured limit 的关系，authority 为 `ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE`。不能声称测得 true applied PhysX joint torque，且 `real_hardware_force_claim=false`；不能提出 real-hardware force-feasibility 结论。R10 的 right-censor 触发 F3 promotion，不能用其选择 `ARM_REALISTIC`。DV1 中 B2/B6 mechanism crossing p50 高于 preregistered bands，未获 named success label；DV2 为 `N/A CENSUS_RIGHT_CENSORED`，DV3 为 `N/A THETA_ONLY_FALLBACK_F3`，DV4 未测试且同为 N/A。

## TODO Summary

- 2026-08-04 03:36 HKT - 本 approved scope 无剩余 execution item。任何 successor experiment 必须重新定义并取得单独 approval；不得修补或外推 B3 fail-fast evidence，也不得绕过 F5 创建 release freeze、holdout64 或 render。

## DONE Summary

- 2026-08-04 03:36 HKT - R25 telemetry handoff/validator repair、R24 failure roots 精确清理、R10 census/R3 F3 promotion、R27 replacement smoke 与 signed cleanup 均完成。
- 2026-08-04 03:36 HKT - R16/R17 正式训练完成：7 cells、70 checkpoints 至 step2500；Route-A exact70、R20 analysis 与 R22 selection 完成。
- 2026-08-04 03:36 HKT - Route-B pooled48/F5 closing 完成，科学终态 `COMPLETED_SCIENTIFIC_NO_RELEASE`；无 release freeze、holdout64 或 render。
