# Base v8 → Base v9 Hold-Handle Diagnostic（2026-07-10）

> **Historical report / superseded next steps（2026-07-13）**：本文件保留 v8→v9 的 D0–D3、formal A–D 与 construction provenance。后续 oracle、static clamp、O0/preflight、matched-clean 诊断已经完成并停止；当前总结果、base_v0→v9 经验与训练/eval/render 命令转至 [`a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md`](a2_piper_push_open_door_optimization_base_v0_to_v9_20260713.md)。下文原 `Next Steps` 仅表示 2026-07-10 当时的历史计划，不再是 active TODO。

## Technical Summary

结论先行：`base_v9` 的 B hold-handle route 四组 formal training 和 matched eval 已完成，但“全程握住门把手”仍未实现。四组 policy 约 99% 时间下发 close command，stage3/4 contact stability 却只有约 `0~0.107%`，接触继续由 `arm_body8` 单侧主导，且 `arm_j6` / arm workspace bottleneck 仍存在。这把下一步从 reward/base ablation 转向 read-only exact geometry diagnosis；在核对 finger/handle 的 collider、closing axis、closed aperture 与 bilateral reachability 前，不应进入 v10 code 或长训练。

四组都完成 step1000 / `262,144,000` timesteps，logged values finite、无 runtime error，但 training goal metric 均为 0。Matched scalar eval 各取 16 个 first episodes，A/B/C/D 均为 `0/16 goal_reached` 且全部 `stage_overtime`。Locked A/B 明显强于 current unlocked C/D；A 是 single-seed provisional best，B 的 true terminal hinge 接近且 rebound 更低，是 close runner-up。该排序不是 final/statistical winner，也不支持“所有 base mobility 都无效”的泛化结论。

2026-07-10 的 D0-D3 是设计 `base_v9` 的 historical diagnostic evidence，不再是当前 policy-performance 结论：

- `D0` 在 threshold `0.174533` 时 8/8 提前进入 stage4，door 随后回弹；stage4 全程只有 `arm_body8` 单侧接触，base 几乎不动。
- `D1` 在训练时 threshold `0.6` 下 8/8 留在 stage3，door 能稳定推到约 `0.257 rad`，但 `arm_j6` 在 8/8 成为 limiting joint，直接暴露 arm-only workspace bottleneck。
- `D2` 在 D0 上强制 gripper close 没有增加 bilateral/stable contact，只带来很小 door 增益并恶化 TCP slip，证明“下发 close target”不是“握住 handle”。

## Base v9 Formal Training and Matched Eval（2026-07-11）

| Config | Exact training dir | Budget / runtime status |
|---|---|---|
| A | [`base_v9_A-20260710_212238`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_A-20260710_212238) | step1000 / `262,144,000` timesteps；finite；无 runtime error；training goal=0 |
| B | [`base_v9_B-20260710_212247`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_B-20260710_212247) | step1000 / `262,144,000` timesteps；finite；无 runtime error；training goal=0 |
| C | [`base_v9_C-20260710_212256`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_C-20260710_212256) | step1000 / `262,144,000` timesteps；finite；无 runtime error；training goal=0 |
| D | [`base_v9_D-20260710_212303`](../logs_rl/a2_piper_full_stage_a2_base/base_v9_D-20260710_212303) | step1000 / `262,144,000` timesteps；finite；无 runtime error；training goal=0 |

Scalar/trace primary 统一使用 step1000、16 env、每 env 的 first episode：

| Config | Goal / terminal | Hinge mean max | True terminal | Rebound `max-end` | Max-stage distribution | Contact stability |
|---|---|---:|---:|---:|---|---:|
| A | `0/16`, all `stage_overtime` | `1.806586` | `1.473302` | `0.333284` | `{4:3,5:13}` | `~0.107%` |
| B | `0/16`, all `stage_overtime` | `1.608041` | `1.450195` | `0.157847` | `{2:1,4:1,5:14}` | `0%` |
| C | `0/16`, all `stage_overtime` | `1.060336` | `0.906377` | `0.153958` | `{3:3,4:11,5:2}` | `~0.105%` |
| D | `0/16`, all `stage_overtime` | `0.122457` | `0.116454` | `0.006004` | `{3:16}` | `0%` |

关键判断：A/B 的 door progress 与 stage progression 都明显强于 C/D，说明 current stage3-unlocked implementation 在这个 seed/config 下没有带来预期改善。A 的最大与 terminal hinge 最高，因此暂列 provisional best；B 的 terminal 仅略低但 rebound 更小，是 close runner-up。四组都没有 goal，且 bilateral stability 几乎为 0，所以不能把 door angle 排序解释为握持成功。

四组 close command ratio 均约 `99%`，却仍是 `arm_body8` dominance；这说明 failure 已不是“policy 没有尝试闭合”这么简单。当前最值得检验的是 `FrameTransformer` source/target、`grasp_target` prim pose、`arm_body7/8` finger colliders、handle collider/contact surfaces、finger closing axis、closed aperture 与 bilateral reachability 是否几何一致。几何 root cause 目前仍是 hypothesis，不应在诊断前写成已证实结论。

### Qualified A/B Rendering

- A/B env3/env5 都只显示 pivot-area brief push/contact，随后 detach，没有形成可见的全程双侧夹持。
- B env3 出现约 `91.8N` doorframe event；B env5 在 stage2 jam，这两项是 candidate-specific qualitative guardrail。
- B 生成 48 个预期 episode0 artifacts。A 有 48 个有效 episode0 artifacts，但另外多出 3 个 env0 episode1 terminal-only artifacts，因此 A render **strict total-count FAIL**；不能把它记录为 matched render strict PASS。
- Scalar/trace 是 primary comparison；render 只用于解释接触位置、detach、doorframe event 与 jam，不参与 success-rate 或严格 matched-count 统计。

## Historical D0-D3 Provenance and Scope

| Item | Control |
|---|---|
| Policy | [`base_v8 A` ckpt1000](../logs_rl/a2_piper_full_stage_a2_base/base_v8_A_release_after_open-20260708_215459/model_step_001000.pt)，三组完全相同、frozen |
| Sampling | D0/D1/D2 各 8 env，单 seed，每 env 1 episode，no-render |
| D0 | [A' threshold diagnostic](../logs_eval/base_v8/base_v8_A_ckpt1000_D0_diag_Aprime_8env_20260710)：threshold `0.174533`，forced-close off |
| D1 | [A training-threshold diagnostic](../logs_eval/base_v8/base_v8_A_ckpt1000_D1_diag_AtrainThreshold_8env_20260710)：threshold `0.6`，forced-close off |
| D2 | [Forced-close intervention](../logs_eval/base_v8/base_v8_A_ckpt1000_D2_diag_forcedClose_8env_20260710)：threshold `0.174533`，stage3/4 gripper primitive 强制 `-1.0` |
| D3 | [Default-off regression](../logs_eval/base_v8/base_v8_A_ckpt1000_D3_defaultOffRegression_2env_20260710)：2 env，diagnostics/forced-close 均 off |

指标口径：`hinge max/end` 是先取每个 env 的 episode 最大值/terminal 值再跨 env 求 mean；`base physical linear command` 是 action routing 后的 base linear command norm，不等同于 measured root velocity；`normalized arm margin` 是 joint 到 soft limit 的最小归一化余量，小于 0 表示越界；`bilateral/stability` 使用当前 handle-contact force 与 history predicate；`TCP slip` 指 TCP/source 相对 handle target 的距离恶化。

Diagnostic implementation 把 stage3→4 threshold 收敛为 env config single source of truth，并为 legacy A2 checkpoint 做显式 migration；expanded trace 与 forced-close 都是 eval-only opt-in，修正了 first-episode isolation 和 action timing。Static/config tests、Oracle review 与 D0-D3 runtime 均 PASS。D3 2/2 正常结束并到达 max stage4，且未生成 `a2_eval_diagnostic_metadata.json`，验证 default-off path 没有污染普通 eval。

后续 construction validation 也已完成：common B hold route、strict `a2_stage3_base_unlocked`、四份 ablation config 与 `checkpoint_load_mode=policy_only` 已通过 independent review、source compile、`git diff --check`、四组 Hydra compose 和 actual A ckpt1000 strict actor load。2-rank startup smoke 使用 2 GPUs、每 rank 4 env，成功注册 B reward terms 并完成一个 PPO batch / 64 timesteps；batch 完成后的 linger cleanup 才人工 `SIGINT`。1-env legacy eval 在显式补入 missing `a2_stage3_base_unlocked=false` 后自然完成，runtime config 记录 `checkpoint_load_mode: full`、flag `false` 且恢复 step1000。上述 smoke 只验证 code/config/load routing，不代表 `base_v9` policy performance。

## D0 / D1 / D2 Controlled Comparison

| Run | Changed factor | Stage outcome | Door hinge | Base / arm | Handle grasp signal |
|---|---|---|---|---|---|
| D0 | threshold `0.174533` | 8/8 stage4 overtime | mean max/end `0.1872/0.1282 rad`，明显回弹 | stage3/4 base command 约 `0.0026/0.0060 m/s`；root 为 millimeter-level | stage4 1616/1616 frames 为 `arm_body8`-only single contact；bilateral/stability 为 0 |
| D1 | threshold `0.6` | 8/8 留在 stage3 | mean max/end `0.2570/0.2568 rad`，无回弹 | root 仍为 millimeter-level；stage3 min arm margin `<0.05` 占 `34.3%`、越出 soft limit 占 `4.49%`；8/8 limiting joint=`arm_j6` | 未进入 stage4，不能检验 stage4 retention |
| D2 | D0 + forced close `-1.0` | 8/8 stage4 overtime | 相对 D0，mean max/end 仅 `+0.0147/+0.0187 rad` | root motion 不变；TCP distance/slip 更差 | 全 trace bilateral ratio 与 D0 同为 `0.137%`；stability=0、stage4 bilateral=0；2 env 脱离 handle 后仍空 close |

D0 还有一个关键 reward-design signal：stage3 在几乎全是单侧接触时，当前 diagnostic reward decomposition 仍约为 `+0.336/step`。也就是说，policy 不需要形成 bilateral stable grasp，也能持续得到较高 stage3 shaping；仅强化同类 keep-close scale 可能继续放大错误 proxy。

## Findings by Evidence Strength

### Descriptive

D0 复现了用户关心的 precursor：gripper/handle 可持续接触，但 gripper 没有真正闭合，base 也没有随门运动。进入 stage4 后发生 reward/stage distribution switch，现有 frozen A policy 丢失 door progress。

### Diagnostic

D1 把 transition 延后后，door 不再回弹，并继续推到约 `0.257 rad`；与此同时 `arm_j6` 系统性逼近 soft limit。最合理的诊断是：当前 stage3 policy 依赖 arm 单独完成门运动，base locomotion 没有承担扩大 workspace 的职责。`0.6` 本身也不适合作为 v9 默认，因为它让 policy 在 transition 前先耗尽 arm workspace。

### Causal Intervention

D2 直接覆盖 gripper primitive，但 bilateral contact、stability 和 root motion不变。它只证明 forced-close command 在当前几何/contact 状态下不充分；不能据此声称经过重新训练的 continuous aperture 或 hold reward 永远无效。当前足以排除的是：把 forced-close、Kp、effort 或 keep-close scale 当作 v9 首轮主变量。

## Limitations

- `base_v9` formal comparison 只有一个 training seed；16-env first-episode scalar eval 能做 bounded ranking，不能给出 statistical winner 或泛化 success rate。
- 四组都是 `0/16 goal` / `stage_overtime`。A/B 的更高 door angle 是 relative progress，不是 task success，更不是 hold success。
- A rendering 多出 3 个 env0 episode1 terminal-only artifacts，strict total-count FAIL；A/B render 只能作为 qualitative evidence，不能覆盖 matched scalar/trace primary。
- `arm_body8` dominance、close command 与低 contact stability 支持 geometry diagnosis 的优先级，但尚未证明具体 root cause。必须核对 transform、collider、contact surface、closing axis/aperture 与 bilateral reachability 后才能下结论。
- Current unlocked C/D 较弱只描述本轮 `a2_stage3_base_unlocked` 语义、seed 与 config；不能据此声称所有 base mobility 或 locomotion assistance 都无效。
- D0/D1/D2 只有 8 env、单 seed、每 env 1 episode；它们是 bounded diagnosis，不是 success-rate estimate。
- 三组 historical D0-D2 复用 frozen A policy。特别是 D0/D2 把在 threshold `0.6` 训练过的 policy 提前切到 stage4，包含明确的 out-of-training-distribution stage switch；这些 run 适合解释设计来源，不应与已经 retrain 的 v9 scalar 混为同一证据层级。
- Soft-limit margin 是 joint-space proxy，不等于完整 Cartesian manipulability、torque reserve 或 self-collision margin。

## Implemented and Evaluated Base v9 2×2

四组共同 invariants：保留 B hold-handle bundle，即 stage3/4 的 handle orientation、grasp/contact-retention 语义持续 active，stage4 使用 mild target distance，并加入 keep-close / open-command penalty / bilateral contact / opposite squeeze / squeeze-force window / contact stability / over-force penalty 七项 hold terms；doorframe scale 对齐 B route，`penalty_a2_stage4_arm_default_pose_l1` 保持 `0.0`。Gripper primitive、actuator gain/effort、stage2 completion 与 workspace-margin shaping均不改。全部从同一个 A ckpt1000 做 policy-only initialization，训练/eval budget 和 seeds 严格一致。

| Config | Stage3→4 threshold | Stage3 base | Purpose |
|---|---:|---|---|
| [`base_v9_A`](../gr00t/rl/config/ablation/wbmanip/base_v9_A.yaml) | `0.174533` | locked current | 早 transition control；复现 D0 路由但允许 retraining 适应 B hold bundle |
| [`base_v9_B`](../gr00t/rl/config/ablation/wbmanip/base_v9_B.yaml) | `0.25` | locked current | threshold main effect；尽量在 D1 的 workspace plateau 前 transition |
| [`base_v9_C`](../gr00t/rl/config/ablation/wbmanip/base_v9_C.yaml) | `0.174533` | unlocked | stage3 base main effect，检验早 transition 下 base mobility 是否改善 retention |
| [`base_v9_D`](../gr00t/rl/config/ablation/wbmanip/base_v9_D.yaml) | `0.25` | unlocked | 联合候选：延后 transition，同时让 base 随门移动 |

`unlocked` 的单变量定义应保持窄：移除 stage3 `penalty_not_standing_still=-15`，并移除 `_stage_3_reward_condition()` 中 `base physical command norm <= 0.1` 的 base-still gate；stage1/2 stillness gates 与 B hold reward terms 保持不变，不要同时改 arm pose 或 gripper dynamics。

解释方式：A↔B 与 C↔D 是 threshold effect；A↔C 与 B↔D 是 base-unlock effect。Observed result 是 locked A/B 明显强于 unlocked C/D，且 A/B 的 terminal hinge 接近、B rebound 更低；但所有组的 bilateral stability 与 goal 都失败，因此这一轮没有产生 hold-handle winner。Primary metrics 是 terminal hinge、rebound `max-end`、stage3/4 bilateral stability、stage progression/goal；guardrails 是 min arm margin、door-frame contact、base roll/pitch、TCP slip 与 root displacement。

### Warm-Start and Runtime Semantics

- `checkpoint_load_mode` 默认 `full`。Formal training 明确传 `policy_only` 时只 strict-load actor 权重；critic、optimizer、scheduler、global step、env curriculum 与 staged snapshots 不从 ckpt 恢复。
- Eval 总是 normalize 到 `full`，以恢复 checkpoint step 与普通 eval semantics。Legacy A2 saved config 缺少 `a2_stage3_base_unlocked` 时显式 migration 到 `false`，最终值写入 eval `.hydra/runtime_config.yaml`。
- Formal matched resource contract 是每组 2 processes、每 rank `num_envs=2048`，即每组 4096 total env；四组可分别绑定 GPU `0,1` / `2,3` / `4,5` / `6,7`。
- `2048 env/GPU` 是用户参考命令 `4 processes × 1024 env/rank` 的 2 倍 per-GPU load。若启动时 OOM，应先报告并统一重定资源方案，不要只降低某一组 env count 破坏 matched comparison。
- 2-rank 4-env/rank smoke 和 1-env legacy eval 只证明 startup、reward registration、checkpoint routing 与一个 PPO batch 可执行，不应据此声称 reward 或 success rate 改善。

## Explicit Non-Recommendations

- 不把 forced-close、gripper Kp/effort 或更大 keep-close scale 作为首轮 factor。
- 不直接采用 threshold `0.6`；D1 已显示它把 arm 推到 workspace boundary。
- 不直接把 `0.174533` 当最终答案；D0 显示 frozen policy 的 early stage switch 会回弹。
- 不恢复 stage4 arm default-pose reward；它与继续推门/握持目标冲突。
- 不把 workspace-margin shaping 当作当前 immediate fix。先完成 exact geometry diagnosis；只有 geometry/contact reachability 合理且 `arm_j6` saturation 仍持续，才做第二轮 single-variable A/B。
- 不因 C/D 较弱就宣布所有 base mobility 无效，也不把 A 的 single-seed scalar lead 写成 final/statistical winner。
- 不把 scratch B ckpt1000 的 stage2 acquisition failure 与本轮 stage3/4 hold ablation 混为同一因素。

## Historical Next Steps（superseded 2026-07-13）

以下条目保留当时决策来源；当前不再继续扩展 `base_v9` geometry/oracle/O±/matched-clean 诊断。新的 active direction 是另行制定并审批 `base_v10` RL optimization/retraining plan。

1. Read-only 核对 `piper_gripper_handle_frame_transformer` 的 source prim、source offset、target prim、target offset、`target_pos_source` / `source_quat_w` 语义，并把 `grasp_target` prim 的实际 pose 对到同一坐标系。
2. Exact 检查 `arm_body7/8` finger collider 的 shape/extent/orientation、handle collider 与有效 contact surfaces；确认当前 handle 是否在两指可接触区域，而不是只在 `arm_body8` 外侧/末端相交。
3. 量化 finger closing axis、open/closed aperture、joint sign/limits 与 handle 横截面，判断 bilateral reachability。必要时用静态 GUI/geometry measurement 验证，但本阶段不改 product code/config。
4. 只有 geometry diagnosis 给出可证伪 root cause 后，才形成 v10 plan 并重新走 user approval gate；此前不启动长训练。
5. Workspace-margin shaping deferred 到 geometry/contact reachability 确认之后。若 geometry 合理而 `arm_j6` workspace saturation 仍是独立 blocker，再设计 single-variable ablation。
