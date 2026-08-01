# scriptsFORhuman 目录索引

本目录按“训练批次优先、专题其次”组织。版本化 plan、诊断脚本、report 工具与同批 evidence 放在对应版本目录；跨版本专题材料按主题归档。

## 训练批次

- [v0_to_v11/](v0_to_v11/)：base v0–v11 历史优化总报告与 v8→v9 hold-handle 诊断。
- [v13/](v13/)：base v13 优化 plan、前置诊断脚本与 gate warning 工具。
- [v13_1/](v13_1/)：base v13.1 优化 plan。
- [v14/](v14/)：base v14 randomization plan、M20 bucket reporter 与 reachability evidence。
- [v15/](v15/)：base v15 优化 plan、M23 evidence、M27 bucket reporter、eval template 与最终评估报告。
- [v16/](v16/)：base v16 优化 plan 与 M27 bucket reporter。
- [v17/](v17/)：base v17 优化 plan 与 M27 bucket reporter。
- [v18/](v18/)：base v18 优化 plan、P2 probe 与 slip reporter。
- [v19/](v19/)：base v19 优化 plan、M22/endpoint/render/final analysis 工具。
- [v20/](v20/)：base v20 原始优化 plan、P1 preflight/evidence 与 report 工具。
- [v20_R1/](v20_R1/)：base v20_R1 优化 plan、B0 reference、admission 与 runner 工具。
- [v20_R2/](v20_R2/)：base v20_R2 admission/execution plan、workflow 工具与 schemas。

v16 起的 optimization/admission plan 均归档在对应版本目录。为保持已签发 plan SHA、source lock 与历史 eval provenance 有效，移动后的 plan 正文及 `v20_R2/a2_piper_base_v20_R2_plan_lock_20260730.json` 保持逐字节不变；其中记录的原始 self/reference path 属于历史身份，不作为当前定位路径。跨版本 handoff、change log、活跃 worker prompt 与长期 TODO 保留在本目录顶层。

## 专题

- [Reward/](Reward/)：G1 Doorman stage0–5 reward/completion adaptation 与 staged transition correctness 文档。
- [gripper_zone/](gripper_zone/)：A2+PiPER gripper comfort-zone 说明与配图。

## 跨版本参考

- [g1_doorman_policy_stack_a2_adaptation_map.md](g1_doorman_policy_stack_a2_adaptation_map.md)
- [g1_doorman_teacher_privileged_obs_a2_adaptation_map.md](g1_doorman_teacher_privileged_obs_a2_adaptation_map.md)
