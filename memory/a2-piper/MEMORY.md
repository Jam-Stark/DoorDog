# A2_Piper Development Memory

本 subsystem 记录 A2_Piper branch/worktree 的开发约定、robot migration、reward design、workspace routing、experiment progress 与当前 TODO/DONE。不要把这些施工状态写入 `origin-reference`。

## Entries

- [worktree-routing/description.md](worktree-routing/description.md): A2_Piper active implementation worktree 与 doorman baseline/reference worktree 的使用约定。
- [doorman-door-training-goal/description.md](doorman-door-training-goal/description.md): 长期目标：基于 Doorman door-opening workflow 替换为用户自己的 robot，并设计/适配 observation、action、reward、env config、training/eval workflow 以完成开门任务训练。
- [push-open-door-optimization/description.md](push-open-door-optimization/description.md): 2026-07-28 06:43 HKT — v19七组1×4096/2500 formal均natural exit0且W&B finished；70-checkpoint M22与selected-endpoint pooled48、G3/G7 render和final analysis已关闭。七组goal/crossing均48/48、overspeed均0，但carry G1/G2/G6 held p50均低于1.45、G7 plateau低于1.5；按预注册规则选择G3 no-carry fallback，所有组full judgement及render行为门均FAIL，48-door不构成statistical proof。
- [log-layout/description.md](log-layout/description.md): A2_Piper formal/smoke/launcher/eval artifact canonical path contract；v17–v19 已按 version 与 experiment family 完成迁移，未来输出必须直接落到该结构。
- [base-v21b-ablation/description.md](base-v21b-ablation/description.md): base_v21B arm-effort ablation 的 telemetry repair、right-censored census/F3 promotion、formal/exact70/pooled48 closure；科学终态 `COMPLETED_SCIENTIFIC_NO_RELEASE`，无 release。
- [base-v22-posture-clearance/description.md](base-v22-posture-clearance/description.md): base_v22 revision-3 conditional posture / clearance / hinge randomization / body-assist 轮次已关闭为 scientific no-release；记录三候选 Route A/B/render、causal probes 与 §17 taxonomy。
- [base-v23-force-feasibility/description.md](base-v23-force-feasibility/description.md): 2026-08-15 23:40 HKT — base_v23 已完成 16-cell formal、四轮 Route-A、Route-B、holdout64、render 与 final analysis；终态 `V23_RESEARCH_PASS_NO_RELEASE`，H1 negative、H2/H3/H5 typed inconclusive、H4 E2 boundary not established。
- [base-v24-friction-force-boundary/description.md](base-v24-friction-force-boundary/description.md): base_v24 post-F3 分支已完成；P2 终局 `V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3`，P3/science waves 不准入；RQ4 以 `V24_COUPLING_FORWARD_PROXY_ONLY` / critic uncalibrated 收口。
- [reward-implementation-goal/description.md](reward-implementation-goal/description.md): A2+Piper Doorman reward implementation 近期目标与工程约束，stage0-5 reward code work + transition conditions 已 static PASS，剩余全部是 runtime/smoke 验证项。
- [quicktest-merge/description.md](quicktest-merge/description.md): 记录 2026-06-25 从 quickTEST branch 合并回 A2_Piper 主线的内容清单、A/B/C 分类与 6-stage 影响边界。
- [stage0-2-grasp-terminal/description.md](stage0-2-grasp-terminal/description.md): `quickTEST` 分支的 stage0-2-only Teacher PPO quick test，记录 stage2 grasp completion 作为 terminal success 的实验目标、config 边界与验证 TODO。
- [phase2-student-distillation-a2-piper/description.md](phase2-student-distillation-a2-piper/description.md): Doorman paper Phase2 Student Distillation / DAgger vision policy 的完整 A2+Piper 替代/适配计划，覆盖 A2 teacher checkpoint、student obs/action、vision camera、A2_Base trainer compose、object prediction、eval/export 与 validation gates。
- [phase3-student-bootstrapping/description.md](phase3-student-bootstrapping/description.md): Doorman paper Phase3 Student Bootstrapping / GRPO fine-tuning finding，记录其用途、当前 G1/A2 framework 未实现完整 Phase3 的核查结论，以及未来 A2+Piper Phase3 route 边界。
- [static-visual-alignment/description.md](static-visual-alignment/description.md): 使用 full Isaac Sim GUI experience 静态观察 A2_Piper 与 door 的相对位置/朝向，并记录 preview script 调整边界与命令规范。
- [door-asset-openio-sign/description.md](door-asset-openio-sign/description.md): 静态核查 door asset 中 doorOpenIO 字段对 door 构造、hinge joint sign、reward routing 的实际影响。
- [door-asset-randomization-baseline/description.md](door-asset-randomization-baseline/description.md): 记录当前 Doorman/G1 与 A2 training scene 的固定 `right-hinge + out-opening` baseline，以及后续 door asset randomization / push-pull mixed task 的施工边界。

## Update Rules

- 先读对应 entry 的 `description.md`。
- 需要判断当前施工状态时，再读同 entry 的 `TODO.md` 和 `DONE.md`。
- A2_Piper 的 robot/reward/env config/training experiment 进度记录在本 subsystem 或后续同级 subsystem。
- `/home/baoquanc/workspace/GR00T-VisualSim2Real` 是 doorman baseline/reference worktree，默认只读参考，不在其中实施 A2_Piper 改动。
- Timestamp 使用 `YYYY-MM-DD HH:MM HKT`。
