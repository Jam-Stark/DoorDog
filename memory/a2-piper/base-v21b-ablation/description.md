---
name: base-v21b-ablation
scope: A2+Piper base_v21B arm-effort ablation pretest, smoke, formal-training startup, and subsequent adjudication
status: active
last_updated: 2026-08-02 15:19 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v21b-ablation/description.md
  - memory/a2-piper/base-v21b-ablation/TODO.md
  - memory/a2-piper/base-v21b-ablation/DONE.md
read_when:
  - continuing base_v21B training, validating its artifacts, or performing DV analysis/adjudication
  - changing base_v21B telemetry, census, promotion, smoke, or formal-launch contracts
---

# base_v21B Arm-Effort Ablation

## Purpose

本 entry 保存 `base_v21B` arm-effort ablation 的 durable provenance、已完成 pretest/smoke/formal-startup evidence 与后续收尾边界。它不替代 live training heartbeat；正式训练完成前不得从 startup prefix 推断最终训练或科学结论。

## Current State

- 2026-08-02 15:19 HKT - R25 修复 episode-boundary telemetry handoff，并将 validator 的 typed-N/A 与 base-vs-strict 语义分开；提交 `72f3171843cb495b075486cc7ec6703f02753706`、tree `807bfe322ee23359dd04370e4dc3ec7f40252301`。targeted suite 为 `36 passed, 4 skipped`；四个 `pxr` lifecycle tests 因本地缺少 `pxr` 未运行，后续 smoke/formal startup 覆盖 runtime surface，不能把该 static skip 写成 static PASS。
- R10 preformal census 位于 `logs_eval/base_v21B/preformal_20260802_r10`：source lock SHA-256 `6ee27b52d4d6a6c3fbb95e7341debdbc79eafd07fb5d3ac74b137340081133ca`；canonical16/heavy16 各一次 GPU0、W&B offline、natural exit 0。raw-unclipped heavy bucket 的 `>=100 N·m` 为 `7792/12463=0.6252106234453984`，因此 terminal 为 `CENSUS_RIGHT_CENSORED`、selection `N/A`、telemetry authority `ESTIMATE_ONLY`；census SHA-256 `10064789700cd3716bb047e5bc063bff07c15359a6d310bc29a6f63bf0c73d23`。
- R3 F3 promotion 位于 `logs_eval/base_v21B/f3_promotion_20260802_r3`：B1–B7 均为 `ARM_V20 [100]*6`，theta ladder 依次为 `0.90/1.20/1.05/1.15/1.25/1.20/1.25`；adaptation SHA-256 `77b62185350d2f0ad935cb0a9395bc9a0cb42f9966972ab5fba936170476798a`，materialization SHA-256 `a30aabbd1b04fa8a918a668fbf4b48361c1cbb5d1f743b5f78a035ad476e294d`。
- R27 是唯一受理的 B4 replacement smoke：GPU3、W&B online、64 env、10 iteration、save10，natural exit 0；strict rows `1..10`、coverage/finite/identity 与 step10 checkpoint 均 PASS。SMOKE_PASS SHA-256 `4d1526b3421214f5b505cdb449eaa78c523db27d8ab611185b30cca540887ff4`；其后 signed cleanup 删除全部 smoke roots，receipt SHA-256 `9da6ca006acc2c02fa23ec95f666a618b7e9b39dd82dbca588673b5bc4efd685`。
- R28 正式 B1–B7 已各启动一次：GPU0–6、env4096、2500 iterations、save250、W&B online，独立 detached tmux session `base_v21B_formal_v1`；GPU7 未分配。authoritative strict rows `1..50` 的 finite/coverage/identity 对七组均 PASS，startup artifact `logs_eval/base_v21B/f3_promotion_20260802_r3/V21B_R28_STARTUP_50_PASS.json` SHA-256 `f6cf89264f1bbfc93980aeeee64e28088b0a18e970d4770505da62fa58af3388`。15:19 HKT 时 session 有 7 个 alive panes、`attached=0`，训练继续向 iteration 2500 运行。此证据仅为 `STARTUP_50_PASS`，不是 `TRAINING_PASS` 或 formal completion。
- 本地 W&B IDs：B1–B7 分别为 `7ypsbo6c`、`9exiwh60`、`r2lrzmns`、`dkn0k5bl`、`n6gpk9sf`、`1jo8je2e`、`849ux5py`；entity/project/URL 未经 API 验证，不能从 IDs 推断 remote final state。

## Evidence Boundary

`effort_limit` 的降低是 physics treatment；本轮只能表述 estimated commanded PD effort saturation 与 configured limit 的关系，不能声称测得 true applied PhysX joint torque，也不能提出 real-hardware force-feasibility 结论。R10 的 right-censor 触发 F3 promotion，不能用其选择 `ARM_REALISTIC`。

## TODO Summary

- 2026-08-02 15:19 HKT - 持续监测并验证 B1–B7 全部 natural exit 至 iteration 2500、save250/final checkpoint、可解析时的 W&B final state/URLs；不得杀掉或关闭当前 tmux session。
- 2026-08-02 15:19 HKT - 在训练完成证据齐全后，按已批准 plan 执行 DV analyses/adjudication；不得把 prefix50 外推为 formal completion。

## DONE Summary

- 2026-08-02 15:19 HKT - R25 telemetry handoff/validator repair 与 static gates 完成；R24 failure roots 已精确清理。
- 2026-08-02 15:19 HKT - R10 census 与 R3 F3 promotion 完成，right-censored outcome 正确走 F3。
- 2026-08-02 15:19 HKT - R27 replacement smoke 与 signed cleanup 完成；R28 formal launch/startup50 PASS 后 tmux detached 且 training continues。
