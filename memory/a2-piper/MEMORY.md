# A2_Piper Development Memory

本 subsystem 记录 A2_Piper branch/worktree 的开发约定、robot migration、reward design、workspace routing、experiment progress 与当前 TODO/DONE。不要把这些施工状态写入 `origin-reference`。

## Entries

- [worktree-routing/description.md](worktree-routing/description.md): A2_Piper active implementation worktree 与 doorman baseline/reference worktree 的使用约定。
- [doorman-door-training-goal/description.md](doorman-door-training-goal/description.md): 长期目标：基于 Doorman door-opening workflow 替换为用户自己的 robot，并设计/适配 observation、action、reward、env config、training/eval workflow 以完成开门任务训练。
- [push-open-door-optimization/description.md](push-open-door-optimization/description.md): 2026-07-28 06:43 HKT — v19七组1×4096/2500 formal均natural exit0且W&B finished；70-checkpoint M22与selected-endpoint pooled48、G3/G7 render和final analysis已关闭。七组goal/crossing均48/48、overspeed均0，但carry G1/G2/G6 held p50均低于1.45、G7 plateau低于1.5；按预注册规则选择G3 no-carry fallback，所有组full judgement及render行为门均FAIL，48-door不构成statistical proof。
- [log-layout/description.md](log-layout/description.md): A2_Piper formal/smoke/launcher/eval artifact canonical path contract；v17–v19 已按 version 与 experiment family 完成迁移，未来输出必须直接落到该结构。
- [base-v21b-ablation/description.md](base-v21b-ablation/description.md): base_v21B arm-effort ablation 的 telemetry repair、right-censored census/F3 promotion、replacement smoke 与 formal startup50 evidence；formal training 仍在运行。
- [reward-implementation-goal/description.md](reward-implementation-goal/description.md): A2+Piper Doorman reward implementation 近期目标与工程约束，stage0-5 reward code work + transition conditions 已 static PASS，剩余全部是 runtime/smoke 验证项。
- [quicktest-merge/description.md](quicktest-merge/description.md): 记录 2026-06-25 从 quickTEST branch 合并回 A2_Piper 主线的内容清单、A/B/C 分类与 6-stage 影响边界。
- [stage0-2-grasp-terminal/description.md](stage0-2-grasp-terminal/description.md): `quickTEST` 分支的 stage0-2-only Teacher PPO quick test，记录 stage2 grasp completion 作为 terminal success 的实验目标、config 边界与验证 TODO。
- [phase2-student-distillation-a2-piper/description.md](phase2-student-distillation-a2-piper/description.md): Doorman paper Phase2 Student Distillation / DAgger vision policy 的完整 A2+Piper 替代/适配计划，覆盖 A2 teacher checkpoint、student obs/action、vision camera、A2_Base trainer compose、object prediction、eval/export 与 validation gates。
- [phase3-student-bootstrapping/description.md](phase3-student-bootstrapping/description.md): Doorman paper Phase3 Student Bootstrapping / GRPO fine-tuning finding，记录其用途、当前 G1/A2 framework 未实现完整 Phase3 的核查结论，以及未来 A2+Piper Phase3 route 边界。
- [static-visual-alignment/description.md](static-visual-alignment/description.md): 使用 full Isaac Sim GUI experience 静态观察 A2_Piper 与 door 的相对位置/朝向，并记录 preview script 调整边界与命令规范。
- [door-asset-openio-sign/description.md](door-asset-openio-sign/description.md): 静态核查 door asset 中 doorOpenIO 字段对 door 构造、hinge joint sign、reward routing 的实际影响。
- [door-asset-randomization-baseline/description.md](door-asset-randomization-baseline/description.md): 记录当前 Doorman/G1 与 A2 training scene 的固定 `right-hinge + out-opening` baseline，以及后续 door asset randomization / push-pull mixed task 的施工边界。
- [pull-open-door-task/description.md](pull-open-door-task/description.md): 2026-08-29 HKT — pull-v6.1 quality→population stage closed `QUALITY_PASS__POPULATION_INCONCLUSIVE`. r6an remains the sole strict-natural E7 winner; formal 64-episode baseline is E5/clean/frame/E6/E7=`41/5/3/2/1`. Integrated, grouped-output, and one B-focus P revision increased E5 at best to `47/64` but produced no E6/E7, so no population checkpoint was promoted and hardware is `NOT_RUN`.
- [pull-lr-bilateral-grasp/description.md](pull-lr-bilateral-grasp/description.md): 2026-08-30 HKT — pull Stage0–2 exact LEFT/RIGHT asset mirroring and bilateral acquisition closed with winner `pull_lr_grasp_h450_xseg_resume_seed2/model_step_000250.pt`; two independent fixed-side64 evals give strict K5 LEFT/RIGHT=`125/128` each, and both raw sides have verified five-view successful renders. Full Stage3–5 bilateral pull remains `NOT_RUN`.
- [pull-lr-full-stage/description.md](pull-lr-full-stage/description.md): 2026-08-30 15:04 HKT — full Stage3–5 LR-mirrored route；rebase retry 25/25 PASS，Gate B rejected，LEFT E4/E5仍0，single H3 handle-income intervention pending；bilateral Stage5/E7/goal `NOT_RUN`。

## Update Rules

- 先读对应 entry 的 `description.md`。
- 需要判断当前施工状态时，再读同 entry 的 `TODO.md` 和 `DONE.md`。
- A2_Piper 的 robot/reward/env config/training experiment 进度记录在本 subsystem 或后续同级 subsystem。
- `/home/baoquanc/workspace/GR00T-VisualSim2Real` 是 doorman baseline/reference worktree，默认只读参考，不在其中实施 A2_Piper 改动。
- Timestamp 使用 `YYYY-MM-DD HH:MM HKT`。
