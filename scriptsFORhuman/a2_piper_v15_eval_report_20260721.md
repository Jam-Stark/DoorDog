# A2+Piper base_v15 终点评估与 release 交付报告

日期：2026-07-21 HKT
依据：`a2_piper_base_v15_optimization_plan_20260720.md`、`a2_piper_v15_m23_conclusion.md`
结论：**release 选择 step2500，不选择训练末点 step3000；M26 high-water 保持 `false`。**

## 1. 训练与 checkpoint provenance

- Formal run：`logs_rl/a2_piper_full_stage_a2_base/base_v15_main-20260721_003001/`
- Warm start：v14 release `model_step_002000.pt`，`policy_only`
- 训练配置：seed0，4 ranks × 1024 env/rank，3000 batches
- 训练日志到达 `ETA: 0.0s` 并写出 `model_step_003000.pt`；本次没有独立的 launcher shell exit-code 记录，因此不把 launcher natural exit 写成已验证事实。
- `model_step_003000.pt`：CPU load PASS，`global_step=3000`、`max_steps=3000`，267 个 tensor 全部 finite；SHA256 `a6785cf68f3f7138a38bea63f60c70ddd007fa5a369ddf093856fd5debd626c3`。
- `model_step_002500.pt`：CPU load PASS，`global_step=2500`、`max_steps=3000`，267 个 tensor 全部 finite；SHA256 `3b55e3e2fdfabfaa1ea5cdc8933a6488c5b712634a48ab1c6d6e73f14d4a2de5`。

## 2. Plan-required iter500/1000/2000 trajectory

三条均使用 canonical seed0、16 env、0.80–1.10 inclusive height grid、oracle/forced-close/video 关闭。它们是 checkpoint 轨迹证据；strict FAIL 不等于 eval launcher crash。

| Checkpoint | Process status | Goal / crossing | Overall redline（bilateral / coasting / hinge p95 / over-force） | Plan gate | Strict artifact |
| --- | --- | ---: | --- | --- | --- |
| step500 | natural exit 0 | 14 / 14 | 99.760019% / 0.239981% / 0.298094 / 0.503960% | 轻桶 6/7，light no-worse FAIL | FAIL：env0/1 停在 stage0，无 stage2 trace |
| step1000 | natural exit 0 | 15 / 15 | 99.656610% / 0.343390% / 0.347951 / 0.784891% | 中桶 4/5、重桶 stage4 4/4；数值 gate 达标 | FAIL：env0 停在 stage1，无 stage2 trace |
| step2000 | log 到 `Finished evaluation`；exit code 未独立捕获 | 15 / 15 | 98.554854% / 1.445146% / 0.317549 / 0.183187% | 重桶 3/4 goal，达到至少半数 | FAIL：env11 停在 stage0，standoff null 且无 stage2 trace |

step1000/2000 的 heavy doors 已进入 stage4，且 heavy j8 exact-open usage 分别为 12.17% / 10.79%；不满足“重桶 stage3→4 全卡且 j8 钉死”的启用条件，因此 high-water 始终保持 `false`。step2500 是本轮首个同时获得 16/16 outcome 与完整 strict 16-env trace topology 的候选。

## 3. Mandatory midpoint/endpoint redline

口径与 v14 release 完全相同：canonical seed0、16 env、first episode、stage3/4、50 Hz；`bilateral` 是 stage3/4 双侧接触帧率，`coasting` 是 `hinge_vel>0.1 rad/s` 且非双侧接触的 stage3/4 帧率。

| Candidate checkpoint | goal / complete | crossing while holding | bilateral positive-motion | coasting | hinge velocity p95 | over-force | Runtime/artifact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| v15 step2500 | 16 / 16 | 16 / 16 | 99.923940% | 0.000000% | 0.300512 rad/s | 0.076060% | PASS / `base_v15_main_ckpt2500_matched_scalar_trace_16env_seed0_heightgrid_20260721` |
| v15 step3000 | 16 / 16 | 16 / 16 | 99.007009% | 0.973520% | 0.307862 rad/s | 0.428349% | PASS / `base_v15_main_ckpt3000_matched_scalar_trace_16env_seed0_heightgrid_20260721` |
| v14 reference step2000 | 16 / 16 | 16 / 16 | 95.947605% | 4.011461% | 0.491563 rad/s | 0.000000% | matched PASS |
| v14 comparator step3000 | 16 / 16 | 14 / 16 | 94.710327% | 5.289673% | 0.548683 rad/s | 0.293871% | matched PASS |

### Release decision

- 选择：`model_step_002500.pt`。
- 原因：step2500 与 step3000 的 canonical goal、complete、crossing 全部相同；step2500 在 bilateral、coasting、hinge velocity p95、over-force 四项行为质量红线上全部更好。step3000 reward mean 从 `221.259940` 增至 `223.957834`，但不覆盖红线退化。
- step3000 另有 supplementary seed2 回归：14/16 goal、14/16 crossing；一个 env 在 stage0 因 `upper_dof_overspeed` 终止，另一个在 stage2 overtime。前者没有 stage2 trace，因此 endpoint 三 seed 严格 M27 report 按既定 topology fail-fast，未生成 endpoint 48-door 聚合。
- 本报告不重跑 seed2 挑选更有利结果，也不放宽 report schema。

## 4. Selected-release M27 three-seed report

Artifact：`logs_eval/base_v15/base_v15_main_ckpt2500_m27_three_seed_48door_20260721/`

- Reporter natural exit 0，JSON/CSV/Markdown schema validation PASS。
- seed0 是 canonical；seed1/2 仅为 supplementary，不构成 multi-seed statistical proof。
- Overall：47/48 goal，48/48 stage3，47/48 stage4/stage5。
- Per seed：seed0 16/16，seed1 15/16，seed2 16/16 goal/stage5/crossing。

| Bucket | N | Goal / stage5 | body-contact usage | j8 open-limit | staging standoff p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| hinge `[2.5,5.5)` | 15 | 14 / 14 | 1.209054% | 11.443835% | 0.696856 m |
| hinge `[5.5,8.5)` | 15 | 15 / 15 | 1.813503% | 11.064820% | 0.636170 m |
| hinge `[8.5,12.0]` | 18 | 18 / 18 | 2.095663% | 11.438828% | 0.710410 m |
| height `[0.80,0.95)` | 24 | 24 / 24 | 2.266115% | 10.266422% | 0.660785 m |
| height `[0.95,1.10]` | 24 | 23 / 23 | 1.230130% | 12.421120% | 0.709247 m |

解释：

- 重桶 18/18 goal，超过“至少半数”要求；高把手桶 23/24 goal，超过“至少半数”要求。
- 轻桶 j8 open-limit 11.44%，低于 25% observation line。
- body-contact usage 从轻桶 1.21% 上升到重桶 2.10%，方向与接触经济学预期一致；绝对使用率仍低，因此只称为 **directional stratification**，不称统计显著或因果证明。
- pooled panel force 中 body share=1.0、arm-body0..8 panel share=0.0；这里不包含 gripper-handle 力，不能解释为“手臂没有出力”。
- 重桶 staging standoff p50 0.710 m，且各桶均出现 >0.60 m，说明放宽后的 band 没有全部贴住 x_min。
- 高把手 stage2 pitch usage 49.62%，roll usage 100%；physical pitch/roll 的 absolute p95 都为 0.4 rad，说明 policy 实际消费了 M23 勘误指出的可指令姿态自由度。

## 5. Endpoint eval status

Checkpoint：`model_step_003000.pt`

| Seed | Runtime | Goal / crossing | Hinge range | Strict trace/report status |
| --- | --- | ---: | ---: | --- |
| 0 | natural exit 0 | 16 / 16 | 3.110–9.859 N·m | PASS；all env trace topology |
| 1 | natural exit 0 | 16 / 16 | 2.536–11.160 N·m | PASS；all env trace topology |
| 2 | natural exit 0 | 14 / 16 | 4.174–11.388 N·m | FAIL；env2 未进入 stage2，strict trace topology 不完整 |

seed2 的 runtime process 本身完成 16 episodes 并自然退出 0；FAIL 指 evidence/report acceptance，不是 launcher crash。

## 6. Render evidence

Selected release strong-spring render：

- Artifact：`logs_eval/base_v15/base_v15_main_ckpt2500_render_2env_3cam_seed2_heightbounds_strongspring_20260721/`
- natural exit 0；2/2 goal/stage5/complete/crossing-holding。
- env0：height 0.80 m，hinge 11.206553 N·m，805 episode steps / 806 video frames。
- env1：height 1.10 m，hinge 8.611655 N·m，782 episode steps / 783 video frames。
- default/handle_top/handle_side 共 6 个 MP4，无 `.writing`；全帧 OpenCV decode PASS，1280×720@20 fps。

Complementary light render：

- Artifact：`logs_eval/base_v15/base_v15_main_ckpt2500_render_2env_3cam_seed0_heightbounds_20260721/`
- hinge 5.929052 / 4.948398 N·m；2/2 goal/stage5/complete/crossing-holding；6 个 MP4 全帧 decode PASS。

定性抽帧显示：强门 env0 有身体/腿靠近 panel 的姿态，crossing 时 gripper 仍围绕 handle；轻门终点门洞清晰。视频只提供定性支持，不替代 scalar/trace，也不证明 body contact 的因果贡献或“绝无碰撞”。

## 7. M23 attachment and decision-tree closure

- M23 policy-driven artifact：`logs_eval/base_v15/base_v15_m23_policyprobe_h105_110_16env_seed0_20260720/`。
- 1.05–1.10 m：16/16 goal、16/16 stage5、15/16 crossing-holding。
- scripted r39 仅为 supplementary/lower-bound；108-cell scripted grid **NOT RUN**。
- stage0 `base-still` 修正已进入 v15 candidate，standoff 在推进前记录。

Decision：

- v15 round 2 的 canonical goal/crossing、重桶、高把手、j8、staging、render gates 通过。
- supplementary 仍有 seed1 单门失败，step3000 又出现 seed2 两门回归；因此 release 固定为 step2500，不把 3000 末点升级为 release。
- heavy bucket 没有 stage3→4 全卡，M26 high-water 保持默认 `false`。
- 下一轮可进入 plan 的 round 3：`door_open_lr` 左右镜像；先做左侧 workspace GUI/smoke，再决定训练。mass 冲击轴、in/out 拉门与 student distillation 保持后续独立 scope。

## 8. Tooling note

首次运行 M27 reporter 时，合法 float32 上界 `1.100000023841858` 被零容差 `[0.80,1.10]` 检查拒绝。修复只给最终 height 上界增加 `1e-7` 表示容差，保留原值；`1.1001` 与 hinge `12.0001` 仍 fail-fast。targeted suite `8 passed`、CODE_QUALITY PASS，随后完整 48-door reporter runtime PASS。
